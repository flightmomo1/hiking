"""Extract IB3F v1.3b activity route features.

This script is read-only with respect to upstream pipeline outputs. It consumes
IB3A sequence mapmatch, IB3A2 on-route labels, IB1E route context, IB2 route
risk, and optional THCI route-level context to produce deterministic
per-activity feature tables.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_REMAP_REVIEW_NOTE = (
    "projection reversal mixed; branch ambiguity improved; on_route rows not degraded"
)
LOW_SPEED_MPS = 0.3
STOP_SPEED_MPS = 0.2
STOP_MIN_SEC = 10.0
STEEP_SLOPE_PCT = 20.0
JOIN_TOLERANCE_M = 15.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--route-folder", required=True)
    parser.add_argument("--activity-id", action="append", default=[])
    parser.add_argument("--activity-ids", default="")
    parser.add_argument(
        "--sequence-root",
        default="outputs/ib3a_sequence_mapmatched_activity_v1_3b_thci_v1_0c",
    )
    parser.add_argument(
        "--ib3a2-root",
        default="outputs/ib3a2_on_route_activity_filter_v1_3b_thci_v1_0c",
    )
    parser.add_argument(
        "--route-context-root",
        default="outputs/ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa",
    )
    parser.add_argument(
        "--route-risk-root",
        default="outputs/ib2_v2_route_risk_v1_3b_contract_qa",
    )
    parser.add_argument("--thci-root", default="outputs/thci_axis_scores_v1_0c")
    parser.add_argument("--out-dir", default="outputs/ib3f_activity_route_features_v1_3b")
    parser.add_argument("--source-root-type", default="formal")
    return parser.parse_args()


def resolve_activity_ids(args: argparse.Namespace) -> list[str]:
    ids: list[str] = []
    ids.extend(str(x).strip() for x in args.activity_id if str(x).strip())
    if args.activity_ids:
        ids.extend(x.strip() for x in str(args.activity_ids).split(",") if x.strip())
    seen: set[str] = set()
    out: list[str] = []
    for activity_id in ids:
        if activity_id not in seen:
            out.append(activity_id)
            seen.add(activity_id)
    if not out:
        raise ValueError("Provide --activity-id or --activity-ids.")
    return out


def require_file(path: Path, label: str) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    return path


def read_csv(path: Path, label: str) -> pd.DataFrame:
    require_file(path, label)
    return pd.read_csv(path)


def numeric(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype="float64")
    return pd.to_numeric(df[col], errors="coerce")


def text_series(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series("", index=df.index, dtype="object")
    return df[col].fillna("").astype(str)


def bool_series(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(False, index=df.index)
    return text_series(df, col).str.lower().isin(["true", "1", "yes", "y"])


def quantile_or_null(series: pd.Series, q: float) -> float | None:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return None
    return float(clean.quantile(q))


def median_or_null(series: pd.Series) -> float | None:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return None
    return float(clean.median())


def safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return float(numerator) / float(denominator)


def make_duration_weights(df: pd.DataFrame) -> pd.Series:
    if "timestamp_s" in df.columns:
        t = numeric(df, "timestamp_s")
    else:
        t = numeric(df, "elapsed_sec")
    if t.notna().sum() < 2:
        return pd.Series(0.0, index=df.index)
    ordered = df.assign(_time=t).sort_values("_time")
    delta = ordered["_time"].shift(-1) - ordered["_time"]
    delta = delta.where(delta >= 0, 0.0).fillna(0.0)
    delta = delta.clip(lower=0.0, upper=60.0)
    weights = pd.Series(0.0, index=df.index)
    weights.loc[ordered.index] = delta.to_numpy()
    return weights


def count_stop_episodes(speed: pd.Series, weights: pd.Series) -> int:
    stopped = pd.to_numeric(speed, errors="coerce") < STOP_SPEED_MPS
    stopped = stopped.fillna(False).to_numpy()
    w = pd.to_numeric(weights, errors="coerce").fillna(0.0).to_numpy()
    count = 0
    acc = 0.0
    in_stop = False
    for flag, duration in zip(stopped, w):
        if flag:
            acc += float(duration)
            in_stop = True
        elif in_stop:
            if acc >= STOP_MIN_SEC:
                count += 1
            acc = 0.0
            in_stop = False
    if in_stop and acc >= STOP_MIN_SEC:
        count += 1
    return count


def load_route_context(root: Path, case_id: str) -> tuple[pd.DataFrame, Path]:
    path = root / case_id / f"{case_id}_route_profile_contour_window_terrain_enriched.csv"
    df = read_csv(path, "IB1E route context CSV")
    if "dist_m" not in df.columns:
        raise KeyError(f"IB1E route context missing dist_m: {path}")
    return df.sort_values("dist_m").reset_index(drop=True), path


def load_route_risk(root: Path, case_id: str) -> tuple[pd.DataFrame, Path]:
    path = root / case_id / f"{case_id}_route_risk_v2.csv"
    df = read_csv(path, "IB2 route risk CSV")
    if "dist_m" not in df.columns:
        raise KeyError(f"IB2 route risk missing dist_m: {path}")
    return df.sort_values("dist_m").reset_index(drop=True), path


def load_thci(root: Path, case_id: str) -> tuple[dict[str, Any], Path | None]:
    path = root / case_id / f"{case_id}_thci_axis_scores_v1_0c.csv"
    if not path.exists():
        return {}, None
    df = pd.read_csv(path)
    if df.empty:
        return {}, path
    return df.iloc[0].to_dict(), path


def asof_join(
    activity: pd.DataFrame,
    route_df: pd.DataFrame,
    value_cols: list[str],
    prefix: str,
) -> tuple[pd.DataFrame, float]:
    if activity.empty or route_df.empty:
        return activity.copy(), 0.0
    left = activity.copy()
    left["_orig_index"] = np.arange(len(left))
    left["_join_dist_m"] = numeric(left, "route_dist_m")
    right_cols = ["dist_m"] + [c for c in value_cols if c in route_df.columns]
    right = route_df[right_cols].copy()
    right["dist_m"] = pd.to_numeric(right["dist_m"], errors="coerce")
    left = left.dropna(subset=["_join_dist_m"]).sort_values("_join_dist_m")
    right = right.dropna(subset=["dist_m"]).sort_values("dist_m")
    if left.empty or right.empty:
        out = activity.copy()
        return out, 0.0
    joined = pd.merge_asof(
        left,
        right,
        left_on="_join_dist_m",
        right_on="dist_m",
        direction="nearest",
        tolerance=JOIN_TOLERANCE_M,
        suffixes=("", f"_{prefix}"),
    )
    joined[f"{prefix}_join_dist_diff_m"] = (joined["_join_dist_m"] - joined["dist_m"]).abs()
    coverage = float(joined["dist_m"].notna().mean()) if len(joined) else 0.0
    rename = {c: f"{prefix}_{c}" for c in right_cols if c != "dist_m" and c in joined.columns}
    joined = joined.rename(columns=rename)
    out = activity.copy()
    for col in [c for c in joined.columns if c.startswith(f"{prefix}_")]:
        out[col] = pd.Series([pd.NA] * len(out), index=out.index, dtype="object")
        out.loc[joined["_orig_index"], col] = joined[col].to_numpy()
    return out, coverage


def duration_by_phase(df: pd.DataFrame, weights: pd.Series, phase_name: str) -> float:
    phase = text_series(df, "candidate_phase")
    return float(weights[phase == phase_name].sum())


def build_hr_zone_summary(hr: pd.Series) -> str:
    clean = pd.to_numeric(hr, errors="coerce").dropna()
    if clean.empty:
        return "{}"
    zones = {
        "low_lt_120": int((clean < 120).sum()),
        "moderate_120_149": int(((clean >= 120) & (clean < 150)).sum()),
        "high_150_169": int(((clean >= 150) & (clean < 170)).sum()),
        "very_high_ge_170": int((clean >= 170).sum()),
    }
    return json.dumps(zones, ensure_ascii=False, sort_keys=True)


def activity_quality_flag(on_route_ratio: float, risk_cov: float, context_cov: float) -> str:
    if on_route_ratio < 0.6:
        return "REVIEW_REQUIRED_LOW_ON_ROUTE_RATIO"
    if risk_cov < 0.8 or context_cov < 0.8:
        return "REVIEW_REQUIRED_LOW_JOIN_COVERAGE"
    return "PASS_REVIEW_READY"


def summarize_activity(
    *,
    route_folder: str,
    case_id: str,
    activity_id: str,
    source_root_type: str,
    sequence: pd.DataFrame,
    labeled: pd.DataFrame,
    route_context: pd.DataFrame,
    route_risk: pd.DataFrame,
    thci: dict[str, Any],
) -> dict[str, Any]:
    seq_weights = make_duration_weights(sequence)
    labeled_weights = make_duration_weights(labeled)
    duration_source = numeric(sequence, "timestamp_s")
    if duration_source.notna().sum() < 2:
        duration_source = numeric(sequence, "elapsed_sec")
    duration_sec = float(duration_source.max() - duration_source.min()) if duration_source.notna().sum() >= 2 else 0.0

    speed = numeric(sequence, "implied_route_speed_mps")
    speed_available = bool(speed.notna().sum() > 0)
    moving_sec = float(seq_weights[(speed >= STOP_SPEED_MPS).fillna(False)].sum()) if speed_available else 0.0
    stopped_sec = float(seq_weights[(speed < STOP_SPEED_MPS).fillna(False)].sum()) if speed_available else 0.0

    hr = numeric(sequence, "heart_rate_bpm")
    hr_available = bool(hr.notna().sum() > 0)

    progress_state = text_series(labeled, "route_progress_state")
    usable = bool_series(labeled, "usable_on_route")
    total_rows = int(len(labeled))
    on_route_rows = int((progress_state == "on_route_reliable").sum())
    usable_on_route_rows = int(usable.sum())
    off_route_rows = int((progress_state == "off_route_projection_only").sum())
    low_confidence_rows = int((progress_state == "near_route_low_confidence").sum())
    branch_state_rows = int((progress_state == "branch_ambiguous_projection").sum())
    branch_flag_rows = int(bool_series(labeled, "sequence_branch_ambiguity_flag").sum())
    branch_ambiguous_rows = int(max(branch_state_rows, branch_flag_rows))

    joined_risk, risk_coverage = asof_join(
        labeled,
        route_risk,
        ["risk_band", "risk_score", "risk_score_smooth"],
        "risk",
    )
    joined_context, context_coverage = asof_join(
        joined_risk,
        route_context,
        ["slope_pct", "slope_band", "osm_terrain_combined_risk_band"],
        "context",
    )

    risk_band = text_series(joined_context, "risk_risk_band")
    slope_pct = numeric(joined_context, "context_slope_pct")
    risk_weights = labeled_weights.reindex(joined_context.index).fillna(0.0)
    moderate_duration = float(risk_weights[risk_band == "moderate"].sum())
    high_duration = float(risk_weights[risk_band == "high"].sum())
    steep_duration = float(risk_weights[(slope_pct.abs() >= STEEP_SLOPE_PCT).fillna(False)].sum())

    route_choice_review_required = source_root_type == "qixing_repair_candidate"
    remap_review_note = DEFAULT_REMAP_REVIEW_NOTE if route_choice_review_required else ""

    row: dict[str, Any] = {
        "route_folder": route_folder,
        "case_id": case_id,
        "activity_id": activity_id,
        "source_root_type": source_root_type,
        "elapsed_sec": float(numeric(sequence, "elapsed_sec").max()) if "elapsed_sec" in sequence.columns else duration_sec,
        "duration_sec": duration_sec,
        "moving_sec": moving_sec,
        "stopped_sec": stopped_sec,
        "route_dist_min_m": float(numeric(sequence, "route_dist_m").min()),
        "route_dist_max_m": float(numeric(sequence, "route_dist_m").max()),
        "reliable_route_dist_max_m": float(numeric(sequence, "reliable_route_dist_m").max()),
        "ascent_duration_sec": duration_by_phase(sequence, seq_weights, "ascent"),
        "descent_duration_sec": duration_by_phase(sequence, seq_weights, "descent"),
        "summit_near_duration_sec": duration_by_phase(sequence, seq_weights, "summit_self_near"),
        "total_rows": total_rows,
        "on_route_rows": on_route_rows,
        "usable_on_route_rows": usable_on_route_rows,
        "off_route_rows": off_route_rows,
        "low_confidence_rows": low_confidence_rows,
        "branch_ambiguous_rows": branch_ambiguous_rows,
        "on_route_ratio": safe_ratio(on_route_rows, total_rows),
        "off_route_ratio": safe_ratio(off_route_rows, total_rows),
        "branch_ambiguous_ratio": safe_ratio(branch_ambiguous_rows, total_rows),
        "offset_median": median_or_null(numeric(labeled, "offset_m")),
        "offset_p90": quantile_or_null(numeric(labeled, "offset_m"), 0.9),
        "speed_available": speed_available,
        "speed_median_mps": median_or_null(speed),
        "speed_p25_mps": quantile_or_null(speed, 0.25),
        "speed_p75_mps": quantile_or_null(speed, 0.75),
        "low_speed_ratio": safe_ratio(float(seq_weights[(speed < LOW_SPEED_MPS).fillna(False)].sum()), duration_sec)
        if speed_available
        else 0.0,
        "stop_count": count_stop_episodes(speed, seq_weights) if speed_available else 0,
        "hr_available": hr_available,
        "hr_median": median_or_null(hr),
        "hr_p75": quantile_or_null(hr, 0.75),
        "hr_p90": quantile_or_null(hr, 0.9),
        "high_hr_ratio": safe_ratio(int((hr >= 160).sum()), int(hr.notna().sum())) if hr_available else 0.0,
        "hr_zone_summary": build_hr_zone_summary(hr),
        "moderate_risk_duration_sec": moderate_duration,
        "high_risk_duration_sec": high_duration,
        "moderate_risk_ratio": safe_ratio(moderate_duration, duration_sec),
        "high_risk_ratio": safe_ratio(high_duration, duration_sec),
        "steep_slope_duration_sec": steep_duration,
        "steep_slope_ratio": safe_ratio(steep_duration, duration_sec),
        "route_risk_join_coverage_ratio": risk_coverage,
        "route_context_join_coverage_ratio": context_coverage,
        "route_choice_review_required": route_choice_review_required,
        "remap_review_note": remap_review_note,
        "activity_quality_flag": activity_quality_flag(safe_ratio(on_route_rows, total_rows), risk_coverage, context_coverage),
        "thci_context_available": bool(thci),
        "thci_context_source_note": (
            "THCI v1.0c formal baseline context snapshot; qixing repaired root THCI has not been recomputed."
            if source_root_type == "qixing_repair_candidate" and thci
            else "THCI v1.0c context snapshot."
            if thci
            else ""
        ),
    }
    for key, value in thci.items():
        if key.endswith("_score") or key in {"scoring_version", "status"}:
            row[f"thci_{key}"] = value
    return row


def feature_paths(out_dir: Path, route_folder: str, activity_id: str) -> tuple[Path, Path]:
    folder = out_dir / route_folder
    csv_path = folder / f"{route_folder}_{activity_id}_activity_features.csv"
    json_path = folder / f"{route_folder}_{activity_id}_activity_features.json"
    return csv_path, json_path


def write_activity_outputs(row: dict[str, Any], csv_path: Path, json_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([row]).to_csv(csv_path, index=False, encoding="utf-8-sig")
    json_path.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")


def write_batch_outputs(
    rows: list[dict[str, Any]],
    out_dir: Path,
    args: argparse.Namespace,
    source_files: dict[str, str],
) -> tuple[Path, Path]:
    batch_dir = out_dir / "_batch_summary"
    batch_dir.mkdir(parents=True, exist_ok=True)
    summary_csv = batch_dir / "ib3f_activity_route_features_summary.csv"
    contract_json = batch_dir / "ib3f_feature_contract_summary.json"
    pd.DataFrame(rows).to_csv(summary_csv, index=False, encoding="utf-8-sig")
    contract = {
        "feature_contract_version": "ib3f_activity_route_features_v1_3b",
        "case_id": args.case_id,
        "route_folder": args.route_folder,
        "activity_ids": [row["activity_id"] for row in rows],
        "source_root_type": args.source_root_type,
        "input_roots": {
            "sequence_root": args.sequence_root,
            "ib3a2_root": args.ib3a2_root,
            "route_context_root": args.route_context_root,
            "route_risk_root": args.route_risk_root,
            "thci_root": args.thci_root,
        },
        "source_files": source_files,
        "outputs": {
            "batch_summary_csv": str(summary_csv),
            "feature_contract_summary_json": str(contract_json),
        },
        "feature_groups": [
            "identity",
            "time",
            "route_progress",
            "reliability",
            "motion",
            "physiology",
            "terrain_risk_exposure",
            "review_flags",
        ],
        "boundaries": [
            "IB3F does not modify raw activity.",
            "IB3F does not rerun mapmatch.",
            "IB3F does not repair route baseline.",
            "IB3F does not force route-choice classification.",
            "IB3F only extracts features from existing upstream outputs.",
        ],
        "runtime_llm_allowed": False,
    }
    contract_json.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary_csv, contract_json


def main() -> int:
    args = parse_args()
    activity_ids = resolve_activity_ids(args)
    sequence_root = Path(args.sequence_root)
    ib3a2_root = Path(args.ib3a2_root)
    route_context_root = Path(args.route_context_root)
    route_risk_root = Path(args.route_risk_root)
    thci_root = Path(args.thci_root)
    out_dir = Path(args.out_dir)

    route_context, route_context_csv = load_route_context(route_context_root, args.case_id)
    route_risk, route_risk_csv = load_route_risk(route_risk_root, args.case_id)
    thci, thci_csv = load_thci(thci_root, args.case_id)

    rows: list[dict[str, Any]] = []
    source_files: dict[str, str] = {
        "route_context_csv": str(route_context_csv),
        "route_risk_csv": str(route_risk_csv),
        "thci_csv": str(thci_csv) if thci_csv else "",
    }

    for activity_id in activity_ids:
        sequence_csv = sequence_root / args.route_folder / f"{activity_id}_mapmatched.csv"
        labeled_csv = (
            ib3a2_root
            / args.route_folder
            / f"{args.route_folder}_{activity_id}_mapmatched_activity_labeled.csv"
        )
        sequence = read_csv(sequence_csv, f"IB3A sequence CSV for {activity_id}")
        labeled = read_csv(labeled_csv, f"IB3A2 labeled CSV for {activity_id}")
        row = summarize_activity(
            route_folder=args.route_folder,
            case_id=args.case_id,
            activity_id=activity_id,
            source_root_type=args.source_root_type,
            sequence=sequence,
            labeled=labeled,
            route_context=route_context,
            route_risk=route_risk,
            thci=thci,
        )
        csv_path, json_path = feature_paths(out_dir, args.route_folder, activity_id)
        write_activity_outputs(row, csv_path, json_path)
        row["feature_csv"] = str(csv_path)
        row["feature_json"] = str(json_path)
        rows.append(row)
        source_files[f"{activity_id}_sequence_csv"] = str(sequence_csv)
        source_files[f"{activity_id}_labeled_csv"] = str(labeled_csv)
        print(
            f"{activity_id}: activity_quality_flag={row['activity_quality_flag']} "
            f"on_route_ratio={row['on_route_ratio']:.4f} "
            f"speed_available={row['speed_available']} hr_available={row['hr_available']} "
            f"moderate_risk_ratio={row['moderate_risk_ratio']:.4f} "
            f"high_risk_ratio={row['high_risk_ratio']:.4f} "
            f"risk_join_coverage={row['route_risk_join_coverage_ratio']:.4f} "
            f"context_join_coverage={row['route_context_join_coverage_ratio']:.4f}"
        )
        print(f"  feature_csv={csv_path}")
        print(f"  feature_json={json_path}")

    summary_csv, contract_json = write_batch_outputs(rows, out_dir, args, source_files)
    print(f"batch_summary_csv={summary_csv}")
    print(f"feature_contract_summary_json={contract_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
