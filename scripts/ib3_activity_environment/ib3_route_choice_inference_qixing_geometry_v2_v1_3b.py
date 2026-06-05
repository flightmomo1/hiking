from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pyproj import Transformer


ROUTE_FOLDER = "qixing_lengshuikeng"
CASE_ID = "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b"
ACTIVITY_IDS = ["37_1", "33_1", "15_1"]

CORRIDOR_CSV = Path("configs/risk_semantics/qixing_branch_corridor_definition_v1_3b.csv")
ROUTE_PROFILE_ROOT = Path("outputs/ib1_route_profile_v1_3b_qixing_via_corridor_repair_candidate")
SEQUENCE_ROOT = Path("outputs/ib3a_sequence_mapmatched_activity_v1_3b_qixing_via_corridor_repair_candidate")
IB3A2_ROOT = Path("outputs/ib3a2_on_route_activity_filter_v1_3b_qixing_via_corridor_repair_candidate")
OUT_ROOT = Path("outputs/ib3_route_choice_inference_v2_geometry_qixing_repaired_formal_review")

SUMMIT = {"dist_m": 1919.0, "lat": 25.17069791627356, "lon": 121.5534529370406}
THRESHOLDS_M = [20, 30, 50]
PRIMARY_THRESHOLD_M = 30
MATCH_RATIO_DIFF_THRESHOLD = 0.15
MEDIAN_MARGIN_THRESHOLD_M = 10.0
MIN_BRANCH_EVIDENCE_RATIO = 0.02
HIGH_AMBIGUITY_RATIO = 0.25
SUMMIT_NEAR_DISTANCE_M = 100.0

TRANSFORMER = Transformer.from_crs("EPSG:4326", "EPSG:3826", always_xy=True)


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False)


def route_profile_path() -> Path:
    return ROUTE_PROFILE_ROOT / CASE_ID / f"{CASE_ID}_route_profile.csv"


def sequence_path(activity_id: str) -> Path:
    return SEQUENCE_ROOT / ROUTE_FOLDER / f"{activity_id}_mapmatched.csv"


def labeled_path(activity_id: str) -> Path:
    return IB3A2_ROOT / ROUTE_FOLDER / f"{ROUTE_FOLDER}_{activity_id}_mapmatched_activity_labeled.csv"


def project_lonlat(lon: pd.Series | np.ndarray, lat: pd.Series | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x, y = TRANSFORMER.transform(np.asarray(lon, dtype=float), np.asarray(lat, dtype=float))
    return np.asarray(x, dtype=float), np.asarray(y, dtype=float)


def haversine_m(lat1: pd.Series, lon1: pd.Series, lat2: float, lon2: float) -> pd.Series:
    r = 6371008.8
    lat1r = pd.to_numeric(lat1, errors="coerce").map(math.radians)
    lon1r = pd.to_numeric(lon1, errors="coerce").map(math.radians)
    lat2r = math.radians(lat2)
    lon2r = math.radians(lon2)
    dlat = lat2r - lat1r
    dlon = lon2r - lon1r
    a = (dlat / 2).map(lambda x: math.sin(x) ** 2) + lat1r.map(math.cos) * math.cos(lat2r) * (dlon / 2).map(lambda x: math.sin(x) ** 2)
    return 2 * r * a.map(lambda x: math.asin(math.sqrt(x)) if pd.notna(x) else math.nan)


def build_corridor_polylines(route: pd.DataFrame, config: pd.DataFrame) -> dict[str, dict[str, Any]]:
    route = route.copy()
    route["x_m"], route["y_m"] = project_lonlat(route["lon"], route["lat"])
    route_dist = pd.to_numeric(route["dist_m"], errors="coerce")
    corridors: dict[str, dict[str, Any]] = {}
    for _, row in config.iterrows():
        seg = route[route_dist.between(float(row["start_dist_m"]), float(row["end_dist_m"]), inclusive="both")].copy()
        if len(seg) < 2:
            continue
        corridors[str(row["corridor_id"])] = {
            "id": str(row["corridor_id"]),
            "role": str(row["corridor_role"]),
            "start_dist_m": float(row["start_dist_m"]),
            "end_dist_m": float(row["end_dist_m"]),
            "threshold_m": float(row["threshold_m"]),
            "weight": float(row["weight"]),
            "review_note": str(row["review_note"]),
            "points": seg[["x_m", "y_m", "dist_m", "lat", "lon"]].copy(),
        }
    return corridors


def point_to_polyline_distance(points_xy: np.ndarray, line_xy: np.ndarray) -> np.ndarray:
    if len(line_xy) < 2:
        return np.full(len(points_xy), np.nan)
    best = np.full(len(points_xy), np.inf, dtype=float)
    px = points_xy[:, 0]
    py = points_xy[:, 1]
    for i in range(len(line_xy) - 1):
        ax, ay = line_xy[i]
        bx, by = line_xy[i + 1]
        vx = bx - ax
        vy = by - ay
        denom = vx * vx + vy * vy
        if denom <= 0:
            dist = np.hypot(px - ax, py - ay)
        else:
            t = ((px - ax) * vx + (py - ay) * vy) / denom
            t = np.clip(t, 0, 1)
            cx = ax + t * vx
            cy = ay + t * vy
            dist = np.hypot(px - cx, py - cy)
        best = np.minimum(best, dist)
    return best


def attach_corridor_distances(df: pd.DataFrame, corridors: dict[str, dict[str, Any]]) -> pd.DataFrame:
    out = df.copy()
    out["x_m"], out["y_m"] = project_lonlat(out["lon"], out["lat"])
    points_xy = out[["x_m", "y_m"]].to_numpy(dtype=float)
    for key in ["via_up_corridor", "via_down_corridor", "via_up_ambiguous_window", "via_down_ambiguous_window"]:
        if key not in corridors:
            out[f"dist_to_{key}_m"] = np.nan
            continue
        line = corridors[key]["points"][["x_m", "y_m"]].to_numpy(dtype=float)
        out[f"dist_to_{key}_m"] = point_to_polyline_distance(points_xy, line)
    out["distance_margin_m"] = out["dist_to_via_down_corridor_m"] - out["dist_to_via_up_corridor_m"]
    out["nearest_corridor"] = np.where(
        out["dist_to_via_up_corridor_m"] <= out["dist_to_via_down_corridor_m"],
        "via_up_corridor",
        "via_down_corridor",
    )
    return out


def to_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin(["true", "1", "yes", "y"])


def sort_activity(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in ["elapsed_sec", "timestamp_s", "row_index"] if c in df.columns]
    return df.sort_values(cols, kind="stable").copy()


def split_phases(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, bool, str]:
    ordered = sort_activity(df)
    ordered["dist_to_summit_point_m"] = haversine_m(ordered["lat"], ordered["lon"], SUMMIT["lat"], SUMMIT["lon"])
    summit_idx = int(pd.to_numeric(ordered["dist_to_summit_point_m"], errors="coerce").idxmin())
    min_summit_dist = float(pd.to_numeric(ordered.loc[[summit_idx], "dist_to_summit_point_m"], errors="coerce").iloc[0])
    summit_reached = min_summit_dist <= SUMMIT_NEAR_DISTANCE_M
    split_method = "closest_raw_gps_to_summit"

    if not summit_reached and "summit_reached_flag" in ordered.columns and to_bool(ordered["summit_reached_flag"]).any():
        summit_reached = True
        summit_idx = int(ordered[to_bool(ordered["summit_reached_flag"])].index.min())
        split_method = "summit_reached_flag"
    elif not summit_reached and "candidate_phase" in ordered.columns and (ordered["candidate_phase"].astype(str) == "summit_self_near").any():
        summit_reached = True
        summit_idx = int(ordered[ordered["candidate_phase"].astype(str) == "summit_self_near"].index.min())
        split_method = "candidate_phase_summit_self_near"
    elif not summit_reached and "route_dist_m" in ordered.columns:
        summit_idx = int((pd.to_numeric(ordered["route_dist_m"], errors="coerce") - SUMMIT["dist_m"]).abs().idxmin())
        split_method = "nearest_route_dist_to_summit"

    summit_pos = ordered.index.get_loc(summit_idx)
    summit_near = ordered[pd.to_numeric(ordered["dist_to_summit_point_m"], errors="coerce") <= SUMMIT_NEAR_DISTANCE_M].copy()
    ascent = ordered.iloc[: summit_pos + 1].copy()
    descent = ordered.iloc[summit_pos + 1 :].copy()
    return ascent, descent, summit_near, summit_reached, split_method


def phase_metrics(phase: pd.DataFrame, prefix: str) -> dict[str, Any]:
    out: dict[str, Any] = {f"{prefix}_rows_n": int(len(phase))}
    if phase.empty:
        for branch in ["via_up", "via_down"]:
            for threshold in THRESHOLDS_M:
                out[f"{prefix}_{branch}_match_ratio_{threshold}m"] = 0.0
            out[f"{prefix}_{branch}_distance_median_m"] = None
            out[f"{prefix}_{branch}_distance_p90_m"] = None
        out[f"{prefix}_corridor_distance_margin_median"] = None
        out[f"{prefix}_corridor_distance_margin_p25"] = None
        out[f"{prefix}_corridor_distance_margin_p75"] = None
        out[f"{prefix}_ambiguous_corridor_ratio"] = 0.0
        out[f"{prefix}_branch_ambiguous_rows_n"] = 0
        out[f"{prefix}_off_route_rows_n"] = 0
        out[f"{prefix}_low_confidence_rows_n"] = 0
        return out

    n = len(phase)
    up = pd.to_numeric(phase["dist_to_via_up_corridor_m"], errors="coerce")
    down = pd.to_numeric(phase["dist_to_via_down_corridor_m"], errors="coerce")
    margin = pd.to_numeric(phase["distance_margin_m"], errors="coerce")
    for branch, vals in [("via_up", up), ("via_down", down)]:
        for threshold in THRESHOLDS_M:
            out[f"{prefix}_{branch}_match_ratio_{threshold}m"] = float((vals <= threshold).sum() / n)
        out[f"{prefix}_{branch}_distance_median_m"] = float(vals.median()) if vals.notna().any() else None
        out[f"{prefix}_{branch}_distance_p90_m"] = float(vals.quantile(0.90)) if vals.notna().any() else None
    out[f"{prefix}_corridor_distance_margin_median"] = float(margin.median()) if margin.notna().any() else None
    out[f"{prefix}_corridor_distance_margin_p25"] = float(margin.quantile(0.25)) if margin.notna().any() else None
    out[f"{prefix}_corridor_distance_margin_p75"] = float(margin.quantile(0.75)) if margin.notna().any() else None
    ambig = (
        (pd.to_numeric(phase.get("dist_to_via_up_ambiguous_window_m", pd.Series(np.nan, index=phase.index)), errors="coerce") <= 50)
        | (pd.to_numeric(phase.get("dist_to_via_down_ambiguous_window_m", pd.Series(np.nan, index=phase.index)), errors="coerce") <= 50)
    )
    out[f"{prefix}_ambiguous_corridor_ratio"] = float(ambig.sum() / n)
    state = phase.get("route_progress_state", pd.Series("", index=phase.index)).astype("string")
    out[f"{prefix}_branch_ambiguous_rows_n"] = int((state == "branch_ambiguous_projection").sum())
    out[f"{prefix}_off_route_rows_n"] = int((state == "off_route_projection_only").sum())
    out[f"{prefix}_low_confidence_rows_n"] = int((state == "near_route_low_confidence").sum())
    return out


def infer_branch(metrics: dict[str, Any], prefix: str) -> tuple[str, str, float]:
    rows = int(metrics.get(f"{prefix}_rows_n", 0) or 0)
    if rows <= 0:
        return "unknown", "empty phase", 0.0
    up30 = float(metrics[f"{prefix}_via_up_match_ratio_30m"])
    down30 = float(metrics[f"{prefix}_via_down_match_ratio_30m"])
    margin = metrics.get(f"{prefix}_corridor_distance_margin_median")
    margin = float(margin) if margin is not None and not pd.isna(margin) else 0.0
    ambiguity_ratio = (
        float(metrics.get(f"{prefix}_branch_ambiguous_rows_n", 0) or 0)
        + float(metrics.get(f"{prefix}_off_route_rows_n", 0) or 0) * 0.25
        + float(metrics.get(f"{prefix}_low_confidence_rows_n", 0) or 0) * 0.25
    ) / max(rows, 1)

    if max(up30, down30) < MIN_BRANCH_EVIDENCE_RATIO:
        return "unknown", f"weak corridor evidence at 30m: via_up={up30:.3f}, via_down={down30:.3f}", 0.0

    diff = up30 - down30
    if diff >= MATCH_RATIO_DIFF_THRESHOLD and margin >= MEDIAN_MARGIN_THRESHOLD_M:
        conf = min(1.0, 0.5 + abs(diff) + min(abs(margin) / 100.0, 0.35))
        return "via_up", f"via_up ratio/margin support: up30={up30:.3f}, down30={down30:.3f}, margin={margin:.1f}m", conf
    if -diff >= MATCH_RATIO_DIFF_THRESHOLD and margin <= -MEDIAN_MARGIN_THRESHOLD_M:
        conf = min(1.0, 0.5 + abs(diff) + min(abs(margin) / 100.0, 0.35))
        return "via_down", f"via_down ratio/margin support: up30={up30:.3f}, down30={down30:.3f}, margin={margin:.1f}m", conf

    if ambiguity_ratio >= HIGH_AMBIGUITY_RATIO:
        return "ambiguous", f"high ambiguity/off-route weighted ratio={ambiguity_ratio:.3f}; up30={up30:.3f}, down30={down30:.3f}, margin={margin:.1f}m", 0.25

    if abs(diff) < MATCH_RATIO_DIFF_THRESHOLD and abs(margin) < MEDIAN_MARGIN_THRESHOLD_M:
        return "same_corridor", f"corridor ratios/margin not separable: up30={up30:.3f}, down30={down30:.3f}, margin={margin:.1f}m", 0.35
    return "mixed", f"mixed corridor evidence: up30={up30:.3f}, down30={down30:.3f}, margin={margin:.1f}m", 0.35


def sequence_and_match(ascent_branch: str, descent_branch: str, summit_reached: bool) -> tuple[str, str]:
    if not summit_reached:
        return "partial", "partial"
    if ascent_branch in {"same_corridor", "mixed", "ambiguous"} or descent_branch in {"same_corridor", "mixed", "ambiguous"}:
        return "ambiguous", "unknown"
    if ascent_branch == "unknown" or descent_branch == "unknown":
        return "partial", "unknown"
    if ascent_branch == "via_up" and descent_branch == "via_down":
        return "via_up_to_summit_to_via_down", "true"
    if ascent_branch == "via_down" and descent_branch == "via_up":
        return "via_down_to_summit_to_via_up", "false"
    if ascent_branch == "via_up" and descent_branch == "via_up":
        return "via_up_out_and_back", "false"
    if ascent_branch == "via_down" and descent_branch == "via_down":
        return "via_down_out_and_back", "false"
    return "ambiguous", "unknown"


def confidence(ascent_conf: float, descent_conf: float, review_required: bool) -> str:
    if review_required:
        return "low"
    score = min(ascent_conf, descent_conf)
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def analyze_activity(activity_id: str, corridors: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], pd.DataFrame]:
    seq = read_csv(sequence_path(activity_id))
    labeled = read_csv(labeled_path(activity_id)) if labeled_path(activity_id).exists() else pd.DataFrame()
    if not labeled.empty and "row_index" in seq.columns and "row_index" in labeled.columns:
        cols = [c for c in ["row_index", "usable_on_route", "excluded_reason", "segment_role"] if c in labeled.columns]
        seq = seq.merge(labeled[cols], on="row_index", how="left")
    seq = attach_corridor_distances(seq, corridors)
    ascent, descent, summit_near, summit_reached, split_method = split_phases(seq)
    for part, label in [(ascent, "ascent"), (descent, "descent"), (summit_near, "summit_near")]:
        seq.loc[part.index, "phase_split_label"] = label
    seq["phase_split_label"] = seq["phase_split_label"].fillna("unknown")

    ascent_metrics = phase_metrics(ascent, "ascent")
    descent_metrics = phase_metrics(descent, "descent")
    ascent_branch, ascent_note, ascent_conf = infer_branch(ascent_metrics, "ascent")
    descent_branch, descent_note, descent_conf = infer_branch(descent_metrics, "descent")
    actual_sequence, canonical_match = sequence_and_match(ascent_branch, descent_branch, summit_reached)
    review_required = (
        ascent_branch in {"same_corridor", "mixed", "ambiguous", "unknown"}
        or descent_branch in {"same_corridor", "mixed", "ambiguous", "unknown"}
        or not summit_reached
    )
    route_choice_confidence = confidence(ascent_conf, descent_conf, review_required)
    ambiguous_corridor_ratio = float(
        (
            (pd.to_numeric(seq["dist_to_via_up_ambiguous_window_m"], errors="coerce") <= 50)
            | (pd.to_numeric(seq["dist_to_via_down_ambiguous_window_m"], errors="coerce") <= 50)
        ).sum()
        / max(len(seq), 1)
    )

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
        "route_choice_review_required": review_required,
        "ascent_via_up_match_ratio_20m": ascent_metrics["ascent_via_up_match_ratio_20m"],
        "ascent_via_up_match_ratio_30m": ascent_metrics["ascent_via_up_match_ratio_30m"],
        "ascent_via_up_match_ratio_50m": ascent_metrics["ascent_via_up_match_ratio_50m"],
        "ascent_via_down_match_ratio_20m": ascent_metrics["ascent_via_down_match_ratio_20m"],
        "ascent_via_down_match_ratio_30m": ascent_metrics["ascent_via_down_match_ratio_30m"],
        "ascent_via_down_match_ratio_50m": ascent_metrics["ascent_via_down_match_ratio_50m"],
        "descent_via_up_match_ratio_20m": descent_metrics["descent_via_up_match_ratio_20m"],
        "descent_via_up_match_ratio_30m": descent_metrics["descent_via_up_match_ratio_30m"],
        "descent_via_up_match_ratio_50m": descent_metrics["descent_via_up_match_ratio_50m"],
        "descent_via_down_match_ratio_20m": descent_metrics["descent_via_down_match_ratio_20m"],
        "descent_via_down_match_ratio_30m": descent_metrics["descent_via_down_match_ratio_30m"],
        "descent_via_down_match_ratio_50m": descent_metrics["descent_via_down_match_ratio_50m"],
        "ascent_corridor_distance_margin_median": ascent_metrics["ascent_corridor_distance_margin_median"],
        "descent_corridor_distance_margin_median": descent_metrics["descent_corridor_distance_margin_median"],
        "ambiguous_corridor_ratio": ambiguous_corridor_ratio,
        "evidence_summary": evidence_summary,
    }
    evidence_cols = [
        "timestamp_s",
        "elapsed_sec",
        "lat",
        "lon",
        "phase_split_label",
        "dist_to_via_up_corridor_m",
        "dist_to_via_down_corridor_m",
        "distance_margin_m",
        "nearest_corridor",
        "route_dist_m",
        "reliable_route_dist_m",
        "route_progress_state",
        "candidate_phase",
        "offset_m",
    ]
    evidence = seq[[c for c in evidence_cols if c in seq.columns]].copy()
    return summary, evidence


def write_review_html(summary_df: pd.DataFrame, out_html: Path) -> None:
    rows = []
    cols = [
        "activity_id",
        "actual_ascent_branch",
        "actual_descent_branch",
        "actual_branch_sequence",
        "canonical_route_match",
        "route_choice_confidence",
        "route_choice_review_required",
        "ascent_via_up_match_ratio_30m",
        "ascent_via_down_match_ratio_30m",
        "descent_via_up_match_ratio_30m",
        "descent_via_down_match_ratio_30m",
        "ascent_corridor_distance_margin_median",
        "descent_corridor_distance_margin_median",
        "evidence_summary",
    ]
    for _, row in summary_df.iterrows():
        rows.append("<tr>" + "".join(f"<td>{html.escape(str(row[c]))}</td>" for c in cols) + "</tr>")
    out_html.write_text(
        f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>Qixing route-choice v2 geometry review</title>
<style>
body {{ font-family: Arial, 'Microsoft JhengHei', sans-serif; margin: 22px; color: #1f2933; }}
table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
th, td {{ border: 1px solid #d9dee5; padding: 6px; vertical-align: top; }}
th {{ background: #eef2f7; }}
.note {{ padding: 10px; background: #fff8db; border: 1px solid #f3d36b; margin-bottom: 12px; }}
</style>
</head>
<body>
<h1>Qixing route-choice inference v2 geometry corridor review</h1>
<div class="note">Non-canonical route choice is not an error. This v2 prototype uses point-to-corridor-polyline distances and does not use control point pass order.</div>
<table><thead><tr>{''.join(f'<th>{html.escape(c)}</th>' for c in cols)}</tr></thead><tbody>{''.join(rows)}</tbody></table>
</body>
</html>""",
        encoding="utf-8",
    )


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    route = read_csv(route_profile_path())
    config = read_csv(CORRIDOR_CSV)
    if "case_id" in config.columns:
        config = config[config["case_id"].astype(str) == CASE_ID].copy()
    corridors = build_corridor_polylines(route, config)

    rows = []
    evidence_paths: dict[str, str] = {}
    for activity_id in ACTIVITY_IDS:
        summary, evidence = analyze_activity(activity_id, corridors)
        rows.append(summary)
        evidence_path = OUT_ROOT / f"qixing_route_choice_v2_geometry_evidence_{activity_id}.csv"
        evidence.to_csv(evidence_path, index=False, encoding="utf-8-sig")
        evidence_paths[activity_id] = str(evidence_path)

    summary_df = pd.DataFrame(rows)
    summary_csv = OUT_ROOT / "qixing_route_choice_inference_v2_geometry_summary.csv"
    summary_json = OUT_ROOT / "qixing_route_choice_inference_v2_geometry_summary.json"
    review_html = OUT_ROOT / "qixing_route_choice_inference_v2_geometry_review.html"
    summary_df.to_csv(summary_csv, index=False, encoding="utf-8-sig")
    write_review_html(summary_df, review_html)
    payload = {
        "version": "v2_geometry_corridor_v1_3b",
        "case_id": CASE_ID,
        "route_folder": ROUTE_FOLDER,
        "input_roots": {
            "corridor_definition_csv": str(CORRIDOR_CSV),
            "route_profile_root": str(ROUTE_PROFILE_ROOT),
            "sequence_root": str(SEQUENCE_ROOT),
            "ib3a2_root": str(IB3A2_ROOT),
        },
        "summary_csv": str(summary_csv),
        "summary_json": str(summary_json),
        "review_html": str(review_html),
        "evidence_csvs": evidence_paths,
        "thresholds": {
            "primary_threshold_m": PRIMARY_THRESHOLD_M,
            "support_thresholds_m": THRESHOLDS_M,
            "match_ratio_diff_threshold": MATCH_RATIO_DIFF_THRESHOLD,
            "median_margin_threshold_m": MEDIAN_MARGIN_THRESHOLD_M,
        },
        "activities": rows,
        "note": "Prototype only. It does not modify canonical route baseline, repaired roots, activity raw data, THCI, or rerun IB0/IB1/IB2D.",
        "runtime_llm_allowed": False,
    }
    summary_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"summary_csv={summary_csv}")
    print(f"summary_json={summary_json}")
    print(f"review_html={review_html}")
    for row in rows:
        print(
            f"{row['activity_id']}: ascent={row['actual_ascent_branch']}, "
            f"descent={row['actual_descent_branch']}, sequence={row['actual_branch_sequence']}, "
            f"canonical={row['canonical_route_match']}, confidence={row['route_choice_confidence']}, "
            f"review_required={row['route_choice_review_required']}, "
            f"up30/ascent={row['ascent_via_up_match_ratio_30m']:.3f}, down30/ascent={row['ascent_via_down_match_ratio_30m']:.3f}, "
            f"up30/descent={row['descent_via_up_match_ratio_30m']:.3f}, down30/descent={row['descent_via_down_match_ratio_30m']:.3f}, "
            f"margin/ascent={row['ascent_corridor_distance_margin_median']:.3f}, margin/descent={row['descent_corridor_distance_margin_median']:.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
