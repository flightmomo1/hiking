from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd


ROUTE_FOLDER = "qixing_lengshuikeng"
CASE_ID = "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b"
ACTIVITY_IDS = ["37_1", "33_1", "15_1"]

SEQUENCE_ROOT = Path("outputs/ib3a_sequence_mapmatched_activity_v1_3b_qixing_via_corridor_repair_candidate")
IB3A2_ROOT = Path("outputs/ib3a2_on_route_activity_filter_v1_3b_qixing_via_corridor_repair_candidate")
ROUTE_PROFILE_ROOT = Path("outputs/ib1_route_profile_v1_3b_qixing_via_corridor_repair_candidate")
OUT_ROOT = Path("outputs/ib3_route_choice_inference_v1_3b_qixing_repaired_formal_review")

VIA_UP = {"label": "via_up", "lat": 25.165082087184047, "lon": 121.55966911100028}
VIA_DOWN = {"label": "via_down", "lat": 25.16487469519971, "lon": 121.55963745345083}

# Planning-confirmed summit from repaired candidate route profile max smoothed elevation.
SUMMIT = {
    "label": "summit",
    "dist_m": 1919.0,
    "lat": 25.17069791627356,
    "lon": 121.5534529370406,
    "ele_smooth": 1111.3024,
}

PROXIMITY_THRESHOLDS_M = [30, 50, 80]
BRANCH_RATIO_THRESHOLD = 1.5
MIN_BRANCH_EVIDENCE_ROWS = 8
HIGH_AMBIGUITY_RATIO = 0.12
SUMMIT_REACHED_DISTANCE_M = 100.0


def haversine_m(lat1: pd.Series, lon1: pd.Series, lat2: float, lon2: float) -> pd.Series:
    r = 6371008.8
    lat1_rad = pd.to_numeric(lat1, errors="coerce").map(math.radians)
    lon1_rad = pd.to_numeric(lon1, errors="coerce").map(math.radians)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = (dlat / 2).map(lambda x: math.sin(x) ** 2) + lat1_rad.map(math.cos) * math.cos(lat2_rad) * (dlon / 2).map(lambda x: math.sin(x) ** 2)
    return 2 * r * a.map(lambda x: math.asin(math.sqrt(x)) if pd.notna(x) else math.nan)


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False)


def sequence_path(activity_id: str) -> Path:
    return SEQUENCE_ROOT / ROUTE_FOLDER / f"{activity_id}_mapmatched.csv"


def labeled_path(activity_id: str) -> Path:
    return IB3A2_ROOT / ROUTE_FOLDER / f"{ROUTE_FOLDER}_{activity_id}_mapmatched_activity_labeled.csv"


def route_profile_path() -> Path:
    return ROUTE_PROFILE_ROOT / CASE_ID / f"{CASE_ID}_route_profile.csv"


def to_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin(["true", "1", "yes", "y"])


def value_counts_dict(series: pd.Series) -> dict[str, int]:
    if series.empty:
        return {}
    counts = series.astype("string").fillna("<NA>").value_counts(dropna=False).sort_index()
    return {str(k): int(v) for k, v in counts.items()}


def add_distance_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["dist_to_via_up_m"] = haversine_m(out["lat"], out["lon"], VIA_UP["lat"], VIA_UP["lon"])
    out["dist_to_via_down_m"] = haversine_m(out["lat"], out["lon"], VIA_DOWN["lat"], VIA_DOWN["lon"])
    out["dist_to_summit_m"] = haversine_m(out["lat"], out["lon"], SUMMIT["lat"], SUMMIT["lon"])
    return out


def split_ascent_descent(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, int, bool, str]:
    summit_reached = False
    method = "nearest_summit_gps"

    if "summit_reached_flag" in df.columns and to_bool(df["summit_reached_flag"]).any():
        summit_reached = True

    if "dist_to_summit_m" in df.columns and pd.to_numeric(df["dist_to_summit_m"], errors="coerce").notna().any():
        summit_idx = int(pd.to_numeric(df["dist_to_summit_m"], errors="coerce").idxmin())
        min_dist = float(pd.to_numeric(df.loc[[summit_idx], "dist_to_summit_m"], errors="coerce").iloc[0])
        summit_reached = summit_reached or min_dist <= SUMMIT_REACHED_DISTANCE_M
    elif "route_dist_m" in df.columns:
        method = "nearest_summit_route_dist"
        summit_idx = int((pd.to_numeric(df["route_dist_m"], errors="coerce") - SUMMIT["dist_m"]).abs().idxmin())
    elif "candidate_phase" in df.columns and (df["candidate_phase"].astype(str) == "summit_self_near").any():
        method = "candidate_phase_summit_self_near"
        summit_idx = int(df[df["candidate_phase"].astype(str) == "summit_self_near"].index.min())
        summit_reached = True
    else:
        method = "midpoint_fallback"
        summit_idx = int(df.index.min() + len(df) // 2)

    ordered = df.sort_values(["elapsed_sec", "row_index"], kind="stable").copy()
    if summit_idx not in ordered.index:
        summit_idx = int(ordered.index[len(ordered) // 2])
    summit_pos = ordered.index.get_loc(summit_idx)
    ascent = ordered.iloc[: summit_pos + 1].copy()
    descent = ordered.iloc[summit_pos + 1 :].copy()
    return ascent, descent, summit_idx, summit_reached, method


def phase_metrics(phase: pd.DataFrame) -> dict[str, Any]:
    metrics: dict[str, Any] = {"rows_n": int(len(phase))}
    for target in ["via_up", "via_down", "summit"]:
        col = f"dist_to_{target}_m"
        vals = pd.to_numeric(phase[col], errors="coerce") if col in phase.columns else pd.Series(dtype=float)
        metrics[f"{target}_dist_min_m"] = float(vals.min()) if vals.notna().any() else None
        metrics[f"{target}_dist_median_m"] = float(vals.median()) if vals.notna().any() else None
        metrics[f"{target}_dist_p25_m"] = float(vals.quantile(0.25)) if vals.notna().any() else None
        metrics[f"{target}_dist_p75_m"] = float(vals.quantile(0.75)) if vals.notna().any() else None
        metrics[f"{target}_dist_p90_m"] = float(vals.quantile(0.90)) if vals.notna().any() else None
        for threshold in PROXIMITY_THRESHOLDS_M:
            metrics[f"{target}_proximity_rows_{threshold}m"] = int((vals <= threshold).sum()) if vals.notna().any() else 0

    if "route_progress_state" in phase.columns:
        state = phase["route_progress_state"].astype("string")
        metrics["route_progress_state_counts"] = json.dumps(value_counts_dict(state), ensure_ascii=False)
        metrics["branch_ambiguous_rows_n"] = int((state == "branch_ambiguous_projection").sum())
        metrics["off_route_projection_only_rows_n"] = int((state == "off_route_projection_only").sum())
        metrics["near_route_low_confidence_rows_n"] = int((state == "near_route_low_confidence").sum())
    else:
        metrics["route_progress_state_counts"] = "{}"
        metrics["branch_ambiguous_rows_n"] = 0
        metrics["off_route_projection_only_rows_n"] = 0
        metrics["near_route_low_confidence_rows_n"] = 0

    if "candidate_phase" in phase.columns:
        metrics["candidate_phase_counts"] = json.dumps(value_counts_dict(phase["candidate_phase"]), ensure_ascii=False)
    else:
        metrics["candidate_phase_counts"] = "{}"

    if "sequence_branch_ambiguity_flag" in phase.columns:
        metrics["sequence_branch_ambiguity_rows_n"] = int(to_bool(phase["sequence_branch_ambiguity_flag"]).sum())
    else:
        metrics["sequence_branch_ambiguity_rows_n"] = 0

    if "offset_m" in phase.columns:
        offsets = pd.to_numeric(phase["offset_m"], errors="coerce")
        metrics["offset_m_median"] = float(offsets.median()) if offsets.notna().any() else None
        metrics["offset_m_p90"] = float(offsets.quantile(0.90)) if offsets.notna().any() else None
    else:
        metrics["offset_m_median"] = None
        metrics["offset_m_p90"] = None

    if "route_dist_m" in phase.columns:
        route_dist = pd.to_numeric(phase["route_dist_m"], errors="coerce")
        metrics["route_dist_m_min"] = float(route_dist.min()) if route_dist.notna().any() else None
        metrics["route_dist_m_max"] = float(route_dist.max()) if route_dist.notna().any() else None
    else:
        metrics["route_dist_m_min"] = None
        metrics["route_dist_m_max"] = None
    return metrics


def infer_branch(metrics: dict[str, Any]) -> tuple[str, str, float]:
    rows_n = int(metrics.get("rows_n", 0) or 0)
    if rows_n == 0:
        return "unknown", "empty phase", 0.0

    up50 = int(metrics.get("via_up_proximity_rows_50m", 0) or 0)
    down50 = int(metrics.get("via_down_proximity_rows_50m", 0) or 0)
    ambiguous_n = int(metrics.get("branch_ambiguous_rows_n", 0) or 0) + int(metrics.get("sequence_branch_ambiguity_rows_n", 0) or 0)
    ambiguity_ratio = ambiguous_n / rows_n if rows_n else 1.0

    if up50 < MIN_BRANCH_EVIDENCE_ROWS and down50 < MIN_BRANCH_EVIDENCE_ROWS:
        return "unknown", f"insufficient 50m proximity evidence: via_up={up50}, via_down={down50}", 0.0

    if ambiguity_ratio >= HIGH_AMBIGUITY_RATIO:
        return "ambiguous", f"high ambiguity ratio={ambiguity_ratio:.3f}, via_up_50m={up50}, via_down_50m={down50}", max(up50, down50) / max(1, up50 + down50)

    ratio = (up50 + 1) / (down50 + 1)
    if ratio >= BRANCH_RATIO_THRESHOLD:
        conf = min(1.0, ratio / (BRANCH_RATIO_THRESHOLD * 2))
        return "via_up", f"via_up 50m rows dominate: {up50} vs {down50}", conf
    if (1 / ratio) >= BRANCH_RATIO_THRESHOLD:
        conf = min(1.0, (1 / ratio) / (BRANCH_RATIO_THRESHOLD * 2))
        return "via_down", f"via_down 50m rows dominate: {down50} vs {up50}", conf

    if up50 >= MIN_BRANCH_EVIDENCE_ROWS and down50 >= MIN_BRANCH_EVIDENCE_ROWS:
        return "same_corridor", f"via_up/via_down both near and not separable: {up50} vs {down50}", 0.45
    return "mixed", f"mixed weak proximity evidence: via_up={up50}, via_down={down50}", 0.35


def branch_sequence(ascent_branch: str, descent_branch: str, summit_reached: bool) -> tuple[str, str]:
    if not summit_reached:
        return "partial", "partial"
    if ascent_branch in {"ambiguous", "mixed", "same_corridor"} or descent_branch in {"ambiguous", "mixed", "same_corridor"}:
        return "ambiguous", "unknown"
    if ascent_branch == "unknown" or descent_branch == "unknown":
        return "partial", "unknown"
    seq = f"{ascent_branch}_to_summit_to_{descent_branch}"
    if ascent_branch == "via_up" and descent_branch == "via_down":
        return "via_up_to_summit_to_via_down", "true"
    if ascent_branch == "via_down" and descent_branch == "via_up":
        return "via_down_to_summit_to_via_up", "false"
    if ascent_branch == "via_up" and descent_branch == "via_up":
        return "via_up_out_and_back", "false"
    if ascent_branch == "via_down" and descent_branch == "via_down":
        return "via_down_out_and_back", "false"
    return seq, "unknown"


def confidence(ascent_branch: str, descent_branch: str, ascent_conf: float, descent_conf: float, review_required: bool) -> str:
    if review_required:
        return "low"
    score = min(ascent_conf, descent_conf)
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def analyze_activity(activity_id: str) -> tuple[dict[str, Any], pd.DataFrame]:
    seq = read_csv(sequence_path(activity_id))
    labeled = read_csv(labeled_path(activity_id)) if labeled_path(activity_id).exists() else pd.DataFrame()
    df = seq.copy()
    if not labeled.empty and "row_index" in df.columns and "row_index" in labeled.columns:
        labeled_cols = [
            c
            for c in ["row_index", "usable_on_route", "excluded_reason", "segment_role", "route_progress_excluded"]
            if c in labeled.columns
        ]
        df = df.merge(labeled[labeled_cols], on="row_index", how="left")
    df = add_distance_columns(df)
    ascent, descent, summit_idx, summit_reached, split_method = split_ascent_descent(df)
    ascent_metrics = phase_metrics(ascent)
    descent_metrics = phase_metrics(descent)

    ascent_branch, ascent_note, ascent_conf = infer_branch(ascent_metrics)
    descent_branch, descent_note, descent_conf = infer_branch(descent_metrics)
    actual_sequence, canonical_match = branch_sequence(ascent_branch, descent_branch, summit_reached)

    ambiguous_corridor_mask = (
        (
            (pd.to_numeric(df["dist_to_via_up_m"], errors="coerce") <= 80)
            | (pd.to_numeric(df["dist_to_via_down_m"], errors="coerce") <= 80)
        )
        & (
            (df.get("route_progress_state", pd.Series("", index=df.index)).astype("string") == "branch_ambiguous_projection")
            | to_bool(df.get("sequence_branch_ambiguity_flag", pd.Series(False, index=df.index)))
        )
    )
    ambiguous_corridor_rows_n = int(ambiguous_corridor_mask.sum())

    route_choice_review_required = (
        ascent_branch in {"mixed", "ambiguous", "unknown", "same_corridor"}
        or descent_branch in {"mixed", "ambiguous", "unknown", "same_corridor"}
        or not summit_reached
    )
    route_choice_confidence = confidence(ascent_branch, descent_branch, ascent_conf, descent_conf, route_choice_review_required)
    evidence_summary = (
        f"split={split_method}; summit_reached={summit_reached}; "
        f"ascent={ascent_branch} ({ascent_note}); descent={descent_branch} ({descent_note})"
    )

    summary = {
        "activity_id": activity_id,
        "route_folder": ROUTE_FOLDER,
        "case_id": CASE_ID,
        "actual_ascent_branch": ascent_branch,
        "actual_descent_branch": descent_branch,
        "actual_branch_sequence": actual_sequence,
        "canonical_route_match": canonical_match,
        "route_choice_confidence": route_choice_confidence,
        "evidence_summary": evidence_summary,
        "ambiguous_corridor_rows_n": ambiguous_corridor_rows_n,
        "via_up_proximity_rows_ascent_30m": ascent_metrics["via_up_proximity_rows_30m"],
        "via_up_proximity_rows_ascent_50m": ascent_metrics["via_up_proximity_rows_50m"],
        "via_up_proximity_rows_ascent_80m": ascent_metrics["via_up_proximity_rows_80m"],
        "via_down_proximity_rows_ascent_30m": ascent_metrics["via_down_proximity_rows_30m"],
        "via_down_proximity_rows_ascent_50m": ascent_metrics["via_down_proximity_rows_50m"],
        "via_down_proximity_rows_ascent_80m": ascent_metrics["via_down_proximity_rows_80m"],
        "via_up_proximity_rows_descent_30m": descent_metrics["via_up_proximity_rows_30m"],
        "via_up_proximity_rows_descent_50m": descent_metrics["via_up_proximity_rows_50m"],
        "via_up_proximity_rows_descent_80m": descent_metrics["via_up_proximity_rows_80m"],
        "via_down_proximity_rows_descent_30m": descent_metrics["via_down_proximity_rows_30m"],
        "via_down_proximity_rows_descent_50m": descent_metrics["via_down_proximity_rows_50m"],
        "via_down_proximity_rows_descent_80m": descent_metrics["via_down_proximity_rows_80m"],
        "summit_reached": summit_reached,
        "route_choice_review_required": route_choice_review_required,
    }

    evidence_rows = []
    for phase_name, phase_metrics_dict, branch, note in [
        ("ascent", ascent_metrics, ascent_branch, ascent_note),
        ("descent", descent_metrics, descent_branch, descent_note),
    ]:
        row = {
            "activity_id": activity_id,
            "phase": phase_name,
            "inferred_branch": branch,
            "branch_note": note,
        }
        row.update(phase_metrics_dict)
        evidence_rows.append(row)
    evidence = pd.DataFrame(evidence_rows)
    return summary, evidence


def write_html(summary_df: pd.DataFrame, out_html: Path) -> None:
    rows = []
    for _, row in summary_df.iterrows():
        rows.append(
            "<tr>"
            + "".join(
                f"<td>{html.escape(str(row[col]))}</td>"
                for col in [
                    "activity_id",
                    "actual_ascent_branch",
                    "actual_descent_branch",
                    "actual_branch_sequence",
                    "canonical_route_match",
                    "route_choice_confidence",
                    "route_choice_review_required",
                    "evidence_summary",
                ]
            )
            + "</tr>"
        )
    out_html.write_text(
        f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <title>Qixing route-choice inference review</title>
  <style>
    body {{ font-family: Arial, 'Microsoft JhengHei', sans-serif; margin: 24px; color: #1f2933; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
    th, td {{ border: 1px solid #d9dee5; padding: 6px 8px; vertical-align: top; }}
    th {{ background: #eef2f7; }}
    .note {{ margin: 12px 0; padding: 10px; background: #fff8db; border: 1px solid #f3d36b; }}
  </style>
</head>
<body>
  <h1>Qixing route-choice inference prototype</h1>
  <div class="note">Non-canonical route choice is not an error. This prototype only infers actual branch choice from repaired candidate IB3 outputs.</div>
  <table>
    <thead><tr>
      <th>activity_id</th><th>ascent</th><th>descent</th><th>branch_sequence</th><th>canonical_match</th><th>confidence</th><th>review_required</th><th>evidence</th>
    </tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</body>
</html>""",
        encoding="utf-8",
    )


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    profile_csv = route_profile_path()
    if not profile_csv.exists():
        raise FileNotFoundError(f"Missing route profile: {profile_csv}")

    summaries = []
    evidence_paths: dict[str, str] = {}
    for activity_id in ACTIVITY_IDS:
        summary, evidence = analyze_activity(activity_id)
        summaries.append(summary)
        evidence_path = OUT_ROOT / f"qixing_route_choice_evidence_{activity_id}.csv"
        evidence.to_csv(evidence_path, index=False, encoding="utf-8-sig")
        evidence_paths[activity_id] = str(evidence_path)

    summary_df = pd.DataFrame(summaries)
    summary_csv = OUT_ROOT / "qixing_route_choice_inference_summary.csv"
    summary_json = OUT_ROOT / "qixing_route_choice_inference_summary.json"
    review_html = OUT_ROOT / "qixing_route_choice_inference_review.html"

    summary_df.to_csv(summary_csv, index=False, encoding="utf-8-sig")
    write_html(summary_df, review_html)

    payload = {
        "prototype_version": "v1_3b_qixing_repaired_formal_review",
        "route_folder": ROUTE_FOLDER,
        "case_id": CASE_ID,
        "input_roots": {
            "sequence_root": str(SEQUENCE_ROOT),
            "ib3a2_root": str(IB3A2_ROOT),
            "route_profile_root": str(ROUTE_PROFILE_ROOT),
        },
        "control_points": {"via_up": VIA_UP, "via_down": VIA_DOWN, "summit": SUMMIT},
        "summary_csv": str(summary_csv),
        "evidence_csvs": evidence_paths,
        "review_html": str(review_html),
        "activities": summaries,
        "note": "Prototype only. Non-canonical route choice is not treated as an error. Canonical route baseline, repaired formal roots, raw activity data, THCI, IB0/IB1/IB2D were not modified or rerun.",
        "runtime_llm_allowed": False,
    }
    summary_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"summary_csv={summary_csv}")
    print(f"summary_json={summary_json}")
    print(f"review_html={review_html}")
    for row in summaries:
        print(
            f"{row['activity_id']}: ascent={row['actual_ascent_branch']}, "
            f"descent={row['actual_descent_branch']}, sequence={row['actual_branch_sequence']}, "
            f"canonical={row['canonical_route_match']}, confidence={row['route_choice_confidence']}, "
            f"review_required={row['route_choice_review_required']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
