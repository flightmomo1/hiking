#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CH6.5.5 pacing / movement stability axis v1.

Build a replacement descriptive evidence layer for the radar axis
`pacing_movement_stability` using the CH6.5.5 radar v1 axis-refinement
input pack.

Primary input:
  outputs/script_inputs/ch6_5_5_radar_v1_axis_refinement_input_pack_v1/
    primary_window_evidence/route_load_context_windows_v1.csv

Window key:
  activity_id_short + route_distance_window_start_m + route_distance_window_end_m

All component indices are converted to higher-is-better:
  - lower speed variability -> higher score
  - less low-speed clustering -> higher score
  - less stopped clustering -> higher score
  - less late-stage degradation -> higher score
  - better high-route-load speed maintenance -> higher score

Boundary:
  Descriptive axis evidence only. Missing component evidence is not zero-filled.
  No ability score/rank/class, THCI score, radar score, final hiking risk score,
  route suitability score, go/no-go decision, medical diagnosis, or causality
  claim is generated.
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_INPUT_PACK = "outputs/script_inputs/ch6_5_5_radar_v1_axis_refinement_input_pack_v1"
DEFAULT_OUTPUT_ROOT = "outputs/report_figures/ch6_5_5_pacing_movement_stability_axis_v1"

BOUNDARY = (
    "CH6.5.5 pacing / movement stability axis v1 is descriptive route-window evidence only. "
    "It uses route-distance-window normalized evidence and converts component metrics into "
    "higher-is-better group-relative indices. Missing component evidence is not zero-filled. "
    "It does not compute or authorize ability scores, ability ranks, ability classes, THCI scores, "
    "radar scores, final hiking risk scores, route suitability scores, go/no-go decisions, "
    "medical diagnoses, or causality claims."
)

AXIS_ID = "pacing_movement_stability"
AXIS_LABEL_ZH = "配速／移動穩定性"

REQUIRED_COLUMNS = [
    "activity_id_short",
    "route_distance_window_start_m",
    "route_distance_window_end_m",
    "speed_mps_median",
    "low_speed_ratio",
    "stopped_ratio",
    "route_load_context_index_0_100",
]

COMPONENT_WEIGHTS = {
    "speed_variability_inverse_index": 0.25,
    "low_speed_clustering_inverse_index": 0.20,
    "stopped_clustering_inverse_index": 0.20,
    "late_stage_degradation_inverse_index": 0.20,
    "high_route_load_speed_maintenance_index": 0.15,
}

COMPONENT_META = {
    "speed_variability_inverse_index": {
        "raw_metric": "speed_cv_iqr_over_median",
        "raw_direction": "lower_is_better",
        "description": "Lower robust window-speed variability is more stable.",
    },
    "low_speed_clustering_inverse_index": {
        "raw_metric": "low_speed_high_cluster_max_run_fraction",
        "raw_direction": "lower_is_better",
        "description": "Less consecutive clustering of high low-speed windows is more stable.",
    },
    "stopped_clustering_inverse_index": {
        "raw_metric": "stopped_cluster_max_run_fraction",
        "raw_direction": "lower_is_better",
        "description": "Less consecutive clustering of stopped windows is more stable.",
    },
    "late_stage_degradation_inverse_index": {
        "raw_metric": "late_stage_speed_degradation_ratio",
        "raw_direction": "lower_is_better",
        "description": "Less late-stage speed degradation is more stable.",
    },
    "high_route_load_speed_maintenance_index": {
        "raw_metric": "high_route_load_speed_maintenance_ratio",
        "raw_direction": "higher_is_better",
        "description": "Higher speed maintenance in high route-load windows is more stable.",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=r"D:\mountain_work\115_osm")
    parser.add_argument("--input-pack-root", default=DEFAULT_INPUT_PACK)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--min-windows-per-activity", type=int, default=10)
    parser.add_argument("--min-high-route-load-windows", type=int, default=3)
    parser.add_argument("--low-speed-quantile", type=float, default=0.75)
    parser.add_argument("--route-load-high-quantile", type=float, default=0.75)
    return parser.parse_args()


def resolve(root: Path, path_str: str | Path) -> Path:
    p = Path(path_str)
    return p if p.is_absolute() else root / p


def read_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def as_float(value: Any, default: float = np.nan) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def pipe_join(values) -> str:
    out: list[str] = []
    for value in values:
        if value is None or pd.isna(value):
            continue
        s = str(value).strip()
        if not s or s.upper() == "NONE":
            continue
        for part in s.split("|"):
            part = part.strip()
            if part and part.upper() != "NONE":
                out.append(part)
    return "|".join(sorted(set(out))) if out else "NONE"


def max_true_run_fraction(flags: list[bool]) -> tuple[int, float]:
    if not flags:
        return 0, np.nan
    max_run = 0
    current = 0
    for flag in flags:
        if bool(flag):
            current += 1
            max_run = max(max_run, current)
        else:
            current = 0
    return max_run, max_run / len(flags)


def robust_cv_iqr_over_median(values: pd.Series) -> float:
    vals = pd.to_numeric(values, errors="coerce").dropna()
    vals = vals[vals >= 0]
    if len(vals) < 3:
        return np.nan
    median = vals.median()
    if median <= 0:
        return np.nan
    q75 = vals.quantile(0.75)
    q25 = vals.quantile(0.25)
    return float((q75 - q25) / median)


def group_relative_index(raw: pd.Series, higher_is_better: bool) -> pd.Series:
    values = pd.to_numeric(raw, errors="coerce")
    out = pd.Series(np.nan, index=raw.index, dtype=float)
    valid = values.dropna()
    n = len(valid)
    if n == 0:
        return out
    if n == 1:
        out.loc[valid.index] = 50.0
        return out
    ranks = valid.rank(method="average", ascending=True)
    pct = (ranks - 1) / (n - 1) * 100.0
    out.loc[valid.index] = pct if higher_is_better else 100.0 - pct
    return out.round(3)


def weighted_available_average(row: pd.Series) -> float:
    numerator = 0.0
    denominator = 0.0
    for cid, weight in COMPONENT_WEIGHTS.items():
        value = as_float(row.get(cid, np.nan))
        if pd.notna(value):
            numerator += value * weight
            denominator += weight
    if denominator <= 0:
        return np.nan
    return round(numerator / denominator, 3)


def build_window_evidence(
    windows: pd.DataFrame,
    low_speed_threshold: float,
    stopped_threshold: float,
    high_route_load_threshold: float,
) -> pd.DataFrame:
    df = windows.copy()
    numeric_cols = [
        "route_distance_window_start_m",
        "route_distance_window_end_m",
        "speed_mps_median",
        "low_speed_ratio",
        "stopped_ratio",
        "route_load_context_index_0_100",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values(
        ["activity_id_short", "route_distance_window_start_m", "route_distance_window_end_m"],
        kind="mergesort",
    ).reset_index(drop=True)

    band = df.get("route_load_context_band", pd.Series("", index=df.index)).astype(str)
    df["high_low_speed_window"] = df["low_speed_ratio"].ge(low_speed_threshold)
    df["stopped_window"] = df["stopped_ratio"].gt(0) & df["stopped_ratio"].ge(stopped_threshold)
    df["high_route_load_window"] = (
        df["route_load_context_index_0_100"].ge(high_route_load_threshold)
        | band.str.contains("HIGH", case=False, na=False)
    )

    df["window_order_in_activity"] = df.groupby("activity_id_short").cumcount() + 1
    df["window_count_in_activity"] = df.groupby("activity_id_short")["activity_id_short"].transform("count")
    frac = df["window_order_in_activity"] / df["window_count_in_activity"].replace(0, np.nan)
    df["route_stage_tercile"] = np.select(
        [frac <= 1 / 3, frac <= 2 / 3],
        ["EARLY", "MIDDLE"],
        default="LATE",
    )
    df["pacing_window_boundary"] = BOUNDARY
    return df


def summarize_activity(
    window_evidence: pd.DataFrame,
    min_windows_per_activity: int,
    min_high_route_load_windows: int,
) -> pd.DataFrame:
    rows = []
    for activity_id, g in window_evidence.groupby("activity_id_short", sort=True):
        g = g.sort_values(["route_distance_window_start_m", "route_distance_window_end_m"], kind="mergesort")
        n = len(g)
        speed = pd.to_numeric(g["speed_mps_median"], errors="coerce")
        low = pd.to_numeric(g["low_speed_ratio"], errors="coerce")
        stopped = pd.to_numeric(g["stopped_ratio"], errors="coerce")
        route_load = pd.to_numeric(g["route_load_context_index_0_100"], errors="coerce")

        speed_cv = robust_cv_iqr_over_median(speed)
        low_run, low_run_frac = max_true_run_fraction(g["high_low_speed_window"].fillna(False).tolist())
        stop_run, stop_run_frac = max_true_run_fraction(g["stopped_window"].fillna(False).tolist())

        early_speed = speed[g["route_stage_tercile"].eq("EARLY")].median()
        late_speed = speed[g["route_stage_tercile"].eq("LATE")].median()
        if pd.notna(early_speed) and early_speed > 0 and pd.notna(late_speed):
            late_degradation = max(0.0, 1.0 - (late_speed / early_speed))
        else:
            late_degradation = np.nan

        high = g["high_route_load_window"].fillna(False)
        high_count = int(high.sum())
        non_high_count = int((~high).sum())
        high_speed = speed[high].median() if high_count > 0 else np.nan
        non_high_speed = speed[~high].median() if non_high_count > 0 else np.nan
        overall_speed = speed.median()

        if high_count >= min_high_route_load_windows:
            if pd.notna(non_high_speed) and non_high_speed > 0 and non_high_count >= min_high_route_load_windows:
                high_load_maintenance = high_speed / non_high_speed
                high_load_basis = "HIGH_VS_NON_HIGH_ROUTE_LOAD_SPEED_RATIO"
            elif pd.notna(overall_speed) and overall_speed > 0:
                high_load_maintenance = high_speed / overall_speed
                high_load_basis = "HIGH_ROUTE_LOAD_VS_OVERALL_SPEED_RATIO"
            else:
                high_load_maintenance = np.nan
                high_load_basis = "UNAVAILABLE_NO_VALID_REFERENCE_SPEED"
        else:
            high_load_maintenance = np.nan
            high_load_basis = "UNAVAILABLE_TOO_FEW_HIGH_ROUTE_LOAD_WINDOWS"

        rows.append({
            "activity_id_short": activity_id,
            "window_count": n,
            "activity_has_min_windows": bool(n >= min_windows_per_activity),
            "route_distance_min_m": g["route_distance_window_start_m"].min(),
            "route_distance_max_m": g["route_distance_window_end_m"].max(),
            "speed_mps_median_activity": speed.median(),
            "speed_mps_iqr_activity": speed.quantile(0.75) - speed.quantile(0.25) if speed.notna().sum() >= 3 else np.nan,
            "speed_cv_iqr_over_median": speed_cv,
            "low_speed_ratio_median_activity": low.median(),
            "low_speed_high_window_count": int(g["high_low_speed_window"].sum()),
            "low_speed_high_window_ratio": float(g["high_low_speed_window"].mean()) if n else np.nan,
            "low_speed_high_cluster_max_run_windows": low_run,
            "low_speed_high_cluster_max_run_fraction": low_run_frac,
            "stopped_ratio_median_activity": stopped.median(),
            "stopped_window_count": int(g["stopped_window"].sum()),
            "stopped_window_ratio": float(g["stopped_window"].mean()) if n else np.nan,
            "stopped_cluster_max_run_windows": stop_run,
            "stopped_cluster_max_run_fraction": stop_run_frac,
            "early_speed_mps_median": early_speed,
            "late_speed_mps_median": late_speed,
            "late_stage_speed_degradation_ratio": late_degradation,
            "high_route_load_window_count": high_count,
            "high_route_load_window_ratio": float(high.mean()) if n else np.nan,
            "route_load_context_index_median": route_load.median(),
            "high_route_load_speed_mps_median": high_speed,
            "reference_speed_mps_median_for_high_load": non_high_speed if pd.notna(non_high_speed) else overall_speed,
            "high_route_load_speed_maintenance_ratio": high_load_maintenance,
            "high_route_load_speed_maintenance_basis": high_load_basis,
            "route_load_context_bands_observed": pipe_join(g.get("route_load_context_band", pd.Series(dtype=str))),
            "weather_context_flags_observed": pipe_join(g.get("weather_context_flags", pd.Series(dtype=str))),
            "interpretation_boundary": BOUNDARY,
        })
    return pd.DataFrame(rows)


def build_components(activity_summary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = activity_summary.copy()
    for component_id, meta in COMPONENT_META.items():
        raw_col = meta["raw_metric"]
        higher = meta["raw_direction"] == "higher_is_better"
        df[component_id] = group_relative_index(df[raw_col], higher_is_better=higher)

    rows = []
    for _, row in df.iterrows():
        for component_id, meta in COMPONENT_META.items():
            raw_col = meta["raw_metric"]
            raw_value = row.get(raw_col, np.nan)
            idx_value = row.get(component_id, np.nan)
            available = pd.notna(raw_value) and pd.notna(idx_value)
            rows.append({
                "activity_id_short": row["activity_id_short"],
                "axis_id": AXIS_ID,
                "axis_label_zh": AXIS_LABEL_ZH,
                "component_id": component_id,
                "component_weight": COMPONENT_WEIGHTS[component_id],
                "component_raw_metric": raw_col,
                "component_raw_value": raw_value,
                "component_raw_direction": meta["raw_direction"],
                "component_group_relative_index_0_100": idx_value,
                "component_available": bool(available),
                "component_missing_reason": "" if available else "INSUFFICIENT_COMPONENT_EVIDENCE",
                "component_description": meta["description"],
                "interpretation_boundary": BOUNDARY,
            })
    return df, pd.DataFrame(rows)


def build_axis(component_wide: pd.DataFrame, component_long: pd.DataFrame) -> pd.DataFrame:
    rows = []
    missing_map = (
        component_long.loc[~component_long["component_available"].astype(bool)]
        .groupby("activity_id_short")["component_id"]
        .apply(lambda s: "|".join(map(str, s)))
        .to_dict()
    )
    for _, row in component_wide.iterrows():
        activity_id = row["activity_id_short"]
        axis_value = weighted_available_average(row)
        available_count = int(component_long.loc[
            component_long["activity_id_short"].astype(str).eq(str(activity_id)),
            "component_available",
        ].astype(bool).sum())
        missing_ids = missing_map.get(activity_id, "")
        if available_count >= 4:
            support = "SUPPORTED_PACING_MOVEMENT_STABILITY_EVIDENCE"
        elif available_count >= 3:
            support = "LIMITED_PACING_MOVEMENT_STABILITY_EVIDENCE"
        else:
            support = "INSUFFICIENT_PACING_MOVEMENT_STABILITY_EVIDENCE"
        rows.append({
            "activity_id_short": activity_id,
            "axis_id": AXIS_ID,
            "axis_label_zh": AXIS_LABEL_ZH,
            "axis_group_relative_index_0_100": axis_value,
            "axis_support_status": support,
            "component_available_count": available_count,
            "component_total_count": len(COMPONENT_WEIGHTS),
            "component_missing_ids": missing_ids,
            "axis_component_formula": "weighted average of available higher-is-better component indices; missing components are not zero-filled",
            "axis_component_weights": "|".join(f"{k}:{v}" for k, v in COMPONENT_WEIGHTS.items()),
            "axis_direction": "higher_is_better",
            "axis_source": "input_pack/primary_window_evidence/route_load_context_windows_v1.csv",
            "interpretation_boundary": BOUNDARY,
        })
    out = pd.DataFrame(rows)
    out["axis_group_relative_index_0_100"] = pd.to_numeric(out["axis_group_relative_index_0_100"], errors="coerce").round(3)
    return out


def write_html_report(path: Path, input_pack: Path, output_root: Path, audit: pd.DataFrame, axis: pd.DataFrame, activity: pd.DataFrame, component: pd.DataFrame) -> None:
    def table(df: pd.DataFrame, cols: list[str], max_rows: int = 40) -> str:
        d = df[cols].head(max_rows).copy()
        lines = ["<table><thead><tr>" + "".join(f"<th>{html.escape(c)}</th>" for c in cols) + "</tr></thead><tbody>"]
        for _, r in d.iterrows():
            lines.append("<tr>" + "".join(f"<td>{html.escape('' if pd.isna(r[c]) else str(r[c]))}</td>" for c in cols) + "</tr>")
        lines.append("</tbody></table>")
        return "\n".join(lines)

    axis_sorted = axis.copy()
    axis_sorted["_v"] = pd.to_numeric(axis_sorted["axis_group_relative_index_0_100"], errors="coerce")
    axis_sorted = axis_sorted.sort_values(["_v", "activity_id_short"], kind="mergesort").drop(columns=["_v"])
    audit_row = audit.iloc[0].to_dict()
    text = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>CH6.5.5 Pacing Movement Stability Axis v1</title>
<style>
body {{ font-family: "Microsoft JhengHei", "Noto Sans TC", Arial, sans-serif; margin: 24px; line-height: 1.55; }}
.boundary {{ background: #fff7e6; border-left: 5px solid #d99000; padding: 12px 16px; margin-bottom: 20px; }}
table {{ border-collapse: collapse; width: 100%; margin: 12px 0 24px 0; font-size: 13px; }}
th, td {{ border: 1px solid #ccc; padding: 6px 8px; vertical-align: top; }}
th {{ background: #f2f2f2; }}
code {{ background: #f4f4f4; padding: 2px 4px; border-radius: 4px; }}
</style>
</head>
<body>
<h1>CH6.5.5 配速／移動穩定性軸 v1</h1>
<div class="boundary"><b>Boundary:</b> {html.escape(BOUNDARY)}</div>
<p><b>Input pack:</b> <code>{html.escape(str(input_pack))}</code></p>
<p><b>Output root:</b> <code>{html.escape(str(output_root))}</code></p>
<p><b>Audit conclusion:</b> <code>{html.escape(str(audit_row.get('audit_conclusion', '')))}</code></p>
<h2>Axis Summary（低到高）</h2>
{table(axis_sorted, ['activity_id_short', 'axis_group_relative_index_0_100', 'axis_support_status', 'component_available_count', 'component_missing_ids'])}
<h2>Activity Raw Metrics</h2>
{table(activity.sort_values('activity_id_short'), ['activity_id_short', 'window_count', 'speed_cv_iqr_over_median', 'low_speed_high_cluster_max_run_fraction', 'stopped_cluster_max_run_fraction', 'late_stage_speed_degradation_ratio', 'high_route_load_speed_maintenance_ratio', 'high_route_load_speed_maintenance_basis'])}
<h2>Component Evidence</h2>
{table(component.sort_values(['activity_id_short', 'component_id']), ['activity_id_short', 'component_id', 'component_raw_metric', 'component_raw_value', 'component_raw_direction', 'component_group_relative_index_0_100', 'component_available'])}
</body>
</html>
"""
    path.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    input_pack = resolve(root, args.input_pack_root)
    output_root = resolve(root, args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    primary_path = input_pack / "primary_window_evidence" / "route_load_context_windows_v1.csv"
    manifest_path = input_pack / "input_pack_manifest_v1.csv"
    windows = read_csv(primary_path, "input pack primary route-window evidence")
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in windows.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in route_load_context_windows_v1.csv: {missing_cols}")

    for col in REQUIRED_COLUMNS:
        if col != "activity_id_short":
            windows[col] = pd.to_numeric(windows[col], errors="coerce")

    low_speed_values = pd.to_numeric(windows["low_speed_ratio"], errors="coerce").dropna()
    route_load_values = pd.to_numeric(windows["route_load_context_index_0_100"], errors="coerce").dropna()
    stopped_values = pd.to_numeric(windows["stopped_ratio"], errors="coerce").dropna()
    positive_stopped = stopped_values[stopped_values > 0]

    low_speed_threshold = float(low_speed_values.quantile(args.low_speed_quantile)) if len(low_speed_values) else np.nan
    high_route_load_threshold = float(route_load_values.quantile(args.route_load_high_quantile)) if len(route_load_values) else np.nan
    stopped_threshold = float(positive_stopped.quantile(0.75)) if len(positive_stopped) >= 3 else 0.0

    window_evidence = build_window_evidence(windows, low_speed_threshold, stopped_threshold, high_route_load_threshold)
    activity_summary = summarize_activity(window_evidence, args.min_windows_per_activity, args.min_high_route_load_windows)
    component_wide, component_long = build_components(activity_summary)
    axis = build_axis(component_wide, component_long)

    activity_review = activity_summary.merge(
        axis[["activity_id_short", "axis_group_relative_index_0_100", "axis_support_status", "component_available_count", "component_missing_ids"]],
        on="activity_id_short",
        how="left",
    )

    supported = int(axis["axis_support_status"].eq("SUPPORTED_PACING_MOVEMENT_STABILITY_EVIDENCE").sum())
    limited = int(axis["axis_support_status"].eq("LIMITED_PACING_MOVEMENT_STABILITY_EVIDENCE").sum())
    insufficient = int(axis["axis_support_status"].eq("INSUFFICIENT_PACING_MOVEMENT_STABILITY_EVIDENCE").sum())

    audit_issues = []
    if not manifest_path.exists():
        audit_issues.append("INPUT_PACK_MANIFEST_MISSING")
    if len(window_evidence) == 0:
        audit_issues.append("NO_WINDOW_ROWS")
    if len(axis) == 0:
        audit_issues.append("NO_AXIS_ROWS")
    if insufficient > 0:
        audit_issues.append("INSUFFICIENT_AXIS_ROWS_PRESENT")

    audit_conclusion = "PASS_CH6_5_5_PACING_MOVEMENT_STABILITY_AXIS_V1_DESCRIPTIVE_ONLY" if not audit_issues else "REVIEW_REQUIRED_CH6_5_5_PACING_MOVEMENT_STABILITY_AXIS_V1"

    audit = pd.DataFrame([{
        "input_pack_root": str(input_pack),
        "primary_input_path": str(primary_path),
        "output_root": str(output_root),
        "input_pack_manifest_exists": bool(manifest_path.exists()),
        "window_rows": int(len(window_evidence)),
        "activity_rows": int(activity_summary["activity_id_short"].nunique()),
        "component_rows": int(len(component_long)),
        "axis_rows": int(len(axis)),
        "supported_axis_rows": supported,
        "limited_axis_rows": limited,
        "insufficient_axis_rows": insufficient,
        "low_speed_threshold_q75": round(low_speed_threshold, 6) if pd.notna(low_speed_threshold) else "",
        "stopped_threshold_positive_q75": round(stopped_threshold, 6) if pd.notna(stopped_threshold) else "",
        "high_route_load_threshold_q75": round(high_route_load_threshold, 6) if pd.notna(high_route_load_threshold) else "",
        "min_windows_per_activity": int(args.min_windows_per_activity),
        "min_high_route_load_windows": int(args.min_high_route_load_windows),
        "zero_fill_used": False,
        "weather_zero_fill_used": False,
        "ability_score_generated": False,
        "ability_rank_generated": False,
        "ability_class_generated": False,
        "radar_score_generated": False,
        "route_suitability_score_generated": False,
        "go_no_go_generated": False,
        "medical_diagnosis_generated": False,
        "causality_claim_generated": False,
        "audit_issues": pipe_join(audit_issues),
        "audit_conclusion": audit_conclusion,
        "interpretation_boundary": BOUNDARY,
    }])

    outputs = {
        "window_evidence": output_root / "pacing_movement_stability_window_evidence_v1.csv",
        "activity_summary": output_root / "pacing_movement_stability_activity_summary_v1.csv",
        "component": output_root / "pacing_movement_stability_component_v1.csv",
        "axis": output_root / "pacing_movement_stability_axis_v1.csv",
        "audit": output_root / "pacing_movement_stability_audit_v1.csv",
        "report": output_root / "pacing_movement_stability_report_v1.html",
    }
    window_evidence.to_csv(outputs["window_evidence"], index=False, encoding="utf-8-sig")
    activity_review.to_csv(outputs["activity_summary"], index=False, encoding="utf-8-sig")
    component_long.to_csv(outputs["component"], index=False, encoding="utf-8-sig")
    axis.to_csv(outputs["axis"], index=False, encoding="utf-8-sig")
    audit.to_csv(outputs["audit"], index=False, encoding="utf-8-sig")
    write_html_report(outputs["report"], input_pack, output_root, audit, axis, activity_review, component_long)

    print({
        "output_root": str(output_root),
        "window_rows": int(len(window_evidence)),
        "activity_rows": int(activity_summary["activity_id_short"].nunique()),
        "component_rows": int(len(component_long)),
        "axis_rows": int(len(axis)),
        "supported_axis_rows": supported,
        "limited_axis_rows": limited,
        "insufficient_axis_rows": insufficient,
        "zero_fill_used": False,
        "audit_issues": pipe_join(audit_issues),
        "audit_conclusion": audit_conclusion,
        "outputs": {k: str(v) for k, v in outputs.items()},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
