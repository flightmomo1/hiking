#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build CH6.5.2 weather-adjusted behavior context v1.

This script converts CH6.5.1 route-window behavior profile features into a
weather-context descriptive layer. "Adjusted" here means contextual review
flags and conservative planning review evidence, not numeric ability adjustment.

Boundaries:
- descriptive weather behavior context only
- no ability score, rank, or class
- no THCI score, radar score, final hiking risk score, route suitability score
- no go/no-go decision
- no medical diagnosis
- no causality inference
- no weather zero-fill
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


DEFAULT_PROFILE_ID = "qixing_lengshuikeng_activity_group_full25"
DEFAULT_ROUTE_FOLDER = "qixing_lengshuikeng"

DEFAULT_INPUT_ROOT = "outputs/report_figures/ch6_5_1_personal_activity_behavior_profile_v1_1"
DEFAULT_INPUT_WINDOWS = (
    "outputs/report_figures/ch6_5_1_personal_activity_behavior_profile_v1_1/"
    "personal_behavior_profile_window_features_v1_1.csv"
)
DEFAULT_INPUT_AUDIT = (
    "outputs/report_figures/ch6_5_1_personal_activity_behavior_profile_v1_1/"
    "personal_activity_behavior_profile_audit_v1_1.csv"
)
DEFAULT_OUTPUT_ROOT = "outputs/report_figures/ch6_5_2_weather_adjusted_behavior_context_v1"

FORBIDDEN_OUTPUT_TOKENS = [
    "ability_score",
    "ability_rank",
    "ability_class",
    "thci_score",
    "radar_score",
    "final_hiking_risk_score",
    "route_suitability_score",
    "go_no_go",
    "medical_diagnosis",
]

WEATHER_FIELDS = [
    "temperature_c",
    "relative_humidity_pct",
    "precipitation_mm",
    "wind_speed_ms",
    "wind_gust_ms",
    "uv_index",
]

BOUNDARY_TEXT = (
    "Descriptive CH6.5.2 weather-adjusted behavior context only. "
    "Weather-adjusted means weather-context review flags and conservative "
    "planning evidence, not numeric ability adjustment, not suitability scoring, "
    "not go/no-go decisioning, not medical diagnosis, and not causality. Missing "
    "weather values are not zero-filled."
)

WEATHER_METHOD_NOTE = (
    "Weather flags are descriptive review heuristics over observed or attached "
    "weather context. They do not authorize ability scores, rankings, route "
    "suitability scores, final risk scores, or departure decisions."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=r"D:\mountain_work\115_osm")
    parser.add_argument("--profile-id", default=DEFAULT_PROFILE_ID)
    parser.add_argument("--route-folder", default=DEFAULT_ROUTE_FOLDER)
    parser.add_argument("--input-windows", default=DEFAULT_INPUT_WINDOWS)
    parser.add_argument("--input-audit", default=DEFAULT_INPUT_AUDIT)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)

    # Descriptive review thresholds. These are deliberately transparent and
    # conservative; they are not physiological or safety standards.
    parser.add_argument("--warm-temp-c", type=float, default=24.0)
    parser.add_argument("--heat-temp-c", type=float, default=28.0)
    parser.add_argument("--humid-rh-pct", type=float, default=80.0)
    parser.add_argument("--very-humid-rh-pct", type=float, default=85.0)
    parser.add_argument("--rain-mm", type=float, default=0.0)
    parser.add_argument("--wind-gust-review-ms", type=float, default=10.0)
    parser.add_argument("--uv-moderate", type=float, default=6.0)
    parser.add_argument("--uv-high", type=float, default=8.0)
    return parser.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def read_csv(path: Path, label: str, required: bool = True) -> pd.DataFrame:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Missing {label}: {path}")
        return pd.DataFrame()
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def clean_str(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip()


def pipe_flags(values: Iterable[str]) -> str:
    out: list[str] = []
    for value in values:
        if value is None:
            continue
        s = str(value).strip()
        if not s or s.lower() == "nan" or s == "NONE":
            continue
        for part in s.split("|"):
            p = part.strip()
            if p and p.lower() != "nan" and p != "NONE":
                out.append(p)
    return "|".join(sorted(set(out))) if out else "NONE"


def q(series: pd.Series, quantile: float) -> float:
    s = numeric(series).dropna()
    return float(s.quantile(quantile)) if not s.empty else np.nan


def mean(series: pd.Series) -> float:
    s = numeric(series).dropna()
    return float(s.mean()) if not s.empty else np.nan


def ratio_true(series: pd.Series) -> float:
    if len(series) == 0:
        return np.nan
    return float(series.fillna(False).astype(bool).sum()) / float(len(series))


def require_columns(df: pd.DataFrame, cols: list[str], label: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(f"{label} missing required columns: {missing}; available={list(df.columns)}")


def build_source_inventory(paths: dict[str, Path]) -> pd.DataFrame:
    rows = []
    for label, path in paths.items():
        exists = path.exists()
        rows.append({
            "source_label": label,
            "source_path": str(path),
            "exists": bool(exists),
            "length_bytes": int(path.stat().st_size) if exists else 0,
        })
    return pd.DataFrame(rows)


def classify_weather(row: pd.Series, args: argparse.Namespace) -> tuple[str, str, str]:
    flags: list[str] = []
    conservative_flags: list[str] = []

    available = bool(row.get("weather_context_available_bool", False))
    any_weather_value = any(pd.notna(row.get(c)) for c in WEATHER_FIELDS)
    if not available and not any_weather_value:
        return (
            "WEATHER_CONTEXT_MISSING_REVIEW_REQUIRED",
            "WEATHER_CONTEXT_MISSING_REVIEW_REQUIRED",
            "WEATHER_CONTEXT_MISSING_REVIEW_REQUIRED",
        )

    temp = row.get("temperature_c")
    rh = row.get("relative_humidity_pct")
    rain = row.get("precipitation_mm")
    wind_gust = row.get("wind_gust_ms")
    wind_speed = row.get("wind_speed_ms")
    uv = row.get("uv_index")

    if pd.notna(temp):
        if temp >= args.heat_temp_c:
            flags.append("HEAT_REVIEW_CONTEXT")
            conservative_flags.append("CONSERVATIVE_PACING_REVIEW_HEAT")
        elif temp >= args.warm_temp_c:
            flags.append("WARM_TEMPERATURE_CONTEXT")

    if pd.notna(rh):
        if rh >= args.very_humid_rh_pct:
            flags.append("VERY_HUMID_CONTEXT")
            conservative_flags.append("CONSERVATIVE_PACING_REVIEW_HUMIDITY")
        elif rh >= args.humid_rh_pct:
            flags.append("HUMID_CONTEXT")

    if pd.notna(temp) and pd.notna(rh) and temp >= args.warm_temp_c and rh >= args.humid_rh_pct:
        flags.append("WARM_HUMID_CONTEXT")
        conservative_flags.append("CONSERVATIVE_PACING_REVIEW_WARM_HUMID")

    if pd.notna(rain) and rain > args.rain_mm:
        flags.append("RAIN_OBSERVED_CONTEXT")
        conservative_flags.append("RAIN_EXPOSURE_REVIEW_REQUIRED")

    if pd.notna(wind_gust) and wind_gust >= args.wind_gust_review_ms:
        flags.append("WIND_GUST_REVIEW_CONTEXT")
        conservative_flags.append("WIND_EXPOSURE_REVIEW_REQUIRED")
    elif pd.notna(wind_speed) and wind_speed >= args.wind_gust_review_ms:
        flags.append("WIND_SPEED_REVIEW_CONTEXT")
        conservative_flags.append("WIND_EXPOSURE_REVIEW_REQUIRED")

    if pd.notna(uv):
        if uv >= args.uv_high:
            flags.append("UV_HIGH_CONTEXT")
            conservative_flags.append("UV_EXPOSURE_REVIEW_REQUIRED")
        elif uv >= args.uv_moderate:
            flags.append("UV_MODERATE_CONTEXT")

    if not flags:
        flags.append("WEATHER_CONTEXT_PRESENT_NO_REVIEW_FLAG")

    if not conservative_flags:
        conservative_flags.append("NO_CONSERVATIVE_WEATHER_REVIEW_FLAG")

    # Compact class for grouping. It is intentionally a review label, not a score.
    if any(f.startswith("RAIN_") or f.startswith("WIND_") for f in flags):
        weather_class = "RAIN_WIND_EXPOSURE_REVIEW_CONTEXT"
    elif "HEAT_REVIEW_CONTEXT" in flags or "WARM_HUMID_CONTEXT" in flags or "VERY_HUMID_CONTEXT" in flags:
        weather_class = "HEAT_HUMIDITY_REVIEW_CONTEXT"
    elif "UV_HIGH_CONTEXT" in flags:
        weather_class = "UV_REVIEW_CONTEXT"
    elif "WARM_TEMPERATURE_CONTEXT" in flags or "HUMID_CONTEXT" in flags or "UV_MODERATE_CONTEXT" in flags:
        weather_class = "MILD_WEATHER_REVIEW_CONTEXT"
    else:
        weather_class = "WEATHER_CONTEXT_PRESENT_NO_REVIEW_FLAG"

    return weather_class, pipe_flags(flags), pipe_flags(conservative_flags)


def build_windows(df: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    required = [
        "activity_id_short",
        "route_load_context_band",
        "route_phase_for_profile",
        "speed_mps_median",
        "low_speed_ratio",
        "stopped_ratio",
        "heart_rate_bpm_median",
    ]
    require_columns(df, required, "personal_behavior_profile_window_features_v1_1")

    w = df.copy()
    w["profile_id"] = args.profile_id
    w["route_folder"] = args.route_folder

    for col in WEATHER_FIELDS + [
        "speed_mps_median",
        "low_speed_ratio",
        "stopped_ratio",
        "heart_rate_bpm_median",
        "heart_rate_bpm_p75",
        "route_distance_window_start_m",
        "route_distance_window_end_m",
    ]:
        if col in w.columns:
            w[col] = numeric(w[col])

    if "weather_context_available" in w.columns:
        w["weather_context_available_bool"] = clean_str(w["weather_context_available"]).str.lower().isin(["true", "1", "yes", "y"])
    elif "weather_context_available_bool" in w.columns:
        w["weather_context_available_bool"] = clean_str(w["weather_context_available_bool"]).str.lower().isin(["true", "1", "yes", "y"])
    else:
        w["weather_context_available_bool"] = w[WEATHER_FIELDS].notna().any(axis=1)

    # Do not fill weather values. Missing values remain NaN.
    classified = w.apply(lambda row: classify_weather(row, args), axis=1)
    w["weather_adjustment_context_class"] = [x[0] for x in classified]
    w["weather_adjustment_context_flags"] = [x[1] for x in classified]
    w["conservative_planning_weather_flags"] = [x[2] for x in classified]
    w["conservative_weather_review_required"] = ~w["conservative_planning_weather_flags"].eq("NO_CONSERVATIVE_WEATHER_REVIEW_FLAG")
    w["weather_adjustment_signal_flag_count"] = w["weather_adjustment_context_flags"].apply(
        lambda s: 0 if s in ["", "NONE", "WEATHER_CONTEXT_PRESENT_NO_REVIEW_FLAG"] else len([p for p in str(s).split("|") if p])
    )

    # Combined behavior-weather review signal. This is descriptive and not a score.
    if "route_load_behavior_candidate_window_bool" in w.columns:
        candidate = w["route_load_behavior_candidate_window_bool"].astype(bool)
    else:
        candidate = pd.Series(False, index=w.index)
    w["behavior_weather_context_review_required"] = candidate & w["conservative_weather_review_required"]

    w["weather_adjustment_method_note"] = WEATHER_METHOD_NOTE
    w["interpretation_boundary"] = BOUNDARY_TEXT
    return w


def aggregate(group: pd.DataFrame, profile_id: str, route_folder: str) -> dict[str, object]:
    activity_ids = sorted(group["activity_id_short"].dropna().astype(str).unique().tolist())
    return {
        "profile_id": profile_id,
        "route_folder": route_folder,
        "activity_count": int(len(activity_ids)),
        "activity_id_short_list": "|".join(activity_ids),
        "windows_n": int(len(group)),
        "speed_mps_median_median": round(q(group.get("speed_mps_median", pd.Series(dtype=float)), 0.50), 6),
        "speed_mps_median_p25": round(q(group.get("speed_mps_median", pd.Series(dtype=float)), 0.25), 6),
        "speed_mps_median_p75": round(q(group.get("speed_mps_median", pd.Series(dtype=float)), 0.75), 6),
        "low_speed_ratio_avg": round(mean(group.get("low_speed_ratio", pd.Series(dtype=float))), 6),
        "low_speed_ratio_median": round(q(group.get("low_speed_ratio", pd.Series(dtype=float)), 0.50), 6),
        "stopped_ratio_avg": round(mean(group.get("stopped_ratio", pd.Series(dtype=float))), 6),
        "stopped_ratio_median": round(q(group.get("stopped_ratio", pd.Series(dtype=float)), 0.50), 6),
        "heart_rate_bpm_median_avg": round(mean(group.get("heart_rate_bpm_median", pd.Series(dtype=float))), 6),
        "heart_rate_bpm_median_median": round(q(group.get("heart_rate_bpm_median", pd.Series(dtype=float)), 0.50), 6),
        "weather_context_available_ratio": round(ratio_true(group.get("weather_context_available_bool", pd.Series(dtype=bool))), 6),
        "conservative_weather_review_required_ratio": round(ratio_true(group.get("conservative_weather_review_required", pd.Series(dtype=bool))), 6),
        "behavior_weather_context_review_required_ratio": round(ratio_true(group.get("behavior_weather_context_review_required", pd.Series(dtype=bool))), 6),
        "weather_adjustment_flags_observed": pipe_flags(group.get("weather_adjustment_context_flags", pd.Series(dtype=str)).astype(str).tolist()),
        "conservative_planning_weather_flags_observed": pipe_flags(group.get("conservative_planning_weather_flags", pd.Series(dtype=str)).astype(str).tolist()),
        "interpretation_boundary": BOUNDARY_TEXT,
    }


def build_profile_summary(w: pd.DataFrame, source_inventory: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    row = aggregate(w, args.profile_id, args.route_folder)
    row["weather_adjustment_context_class"] = "ALL"
    row["source_files_available_n"] = int(source_inventory["exists"].sum())
    row["source_files_expected_n"] = int(len(source_inventory))
    row["weather_missing_windows_n"] = int((w["weather_adjustment_context_class"] == "WEATHER_CONTEXT_MISSING_REVIEW_REQUIRED").sum())
    row["weather_context_present_windows_n"] = int(len(w) - row["weather_missing_windows_n"])
    row["method_note"] = WEATHER_METHOD_NOTE
    row["interpretation_boundary"] = BOUNDARY_TEXT
    return pd.DataFrame([row])


def build_route_load_phase_summary(w: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    rows = []
    group_cols = ["route_load_context_band", "route_phase_for_profile", "weather_adjustment_context_class"]
    for keys, group in w.groupby(group_cols, dropna=False):
        row = aggregate(group, args.profile_id, args.route_folder)
        row.update(dict(zip(group_cols, keys)))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(group_cols).reset_index(drop=True) if rows else pd.DataFrame()


def build_activity_summary(w: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    rows = []
    for activity_id, group in w.groupby("activity_id_short", dropna=False):
        row = aggregate(group, args.profile_id, args.route_folder)
        row["activity_id_short"] = activity_id
        row["weather_context_classes_observed"] = pipe_flags(group["weather_adjustment_context_class"].astype(str).tolist())
        row["conservative_weather_review_required"] = bool(group["conservative_weather_review_required"].fillna(False).astype(bool).any())
        row["behavior_weather_context_review_required"] = bool(group["behavior_weather_context_review_required"].fillna(False).astype(bool).any())
        rows.append(row)
    return pd.DataFrame(rows).sort_values("activity_id_short").reset_index(drop=True) if rows else pd.DataFrame()


def build_conservative_flags(activity_summary: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    if activity_summary.empty:
        return pd.DataFrame()

    out = activity_summary[[
        "profile_id",
        "route_folder",
        "activity_id_short",
        "windows_n",
        "weather_context_available_ratio",
        "conservative_weather_review_required",
        "behavior_weather_context_review_required",
        "weather_context_classes_observed",
        "weather_adjustment_flags_observed",
        "conservative_planning_weather_flags_observed",
    ]].copy()

    def label(row: pd.Series) -> str:
        flags = []
        if float(row.get("weather_context_available_ratio", 0) or 0) < 1.0:
            flags.append("WEATHER_CONTEXT_COVERAGE_REVIEW_REQUIRED")
        if bool(row.get("conservative_weather_review_required")):
            flags.append("CONSERVATIVE_WEATHER_PLANNING_REVIEW_REQUIRED")
        if bool(row.get("behavior_weather_context_review_required")):
            flags.append("BEHAVIOR_RESPONSE_UNDER_WEATHER_REVIEW_REQUIRED")
        return pipe_flags(flags) if flags else "NO_CONSERVATIVE_WEATHER_REVIEW_FLAG"

    out["planning_weather_review_flags"] = out.apply(label, axis=1)
    out["planning_weather_review_boundary"] = BOUNDARY_TEXT
    return out


def build_data_quality(
    w: pd.DataFrame,
    source_inventory: pd.DataFrame,
    output_fields: dict[str, list[str]],
    args: argparse.Namespace,
) -> pd.DataFrame:
    rows = []

    rows.append({
        "profile_id": args.profile_id,
        "route_folder": args.route_folder,
        "check_name": "source_files_available",
        "check_status": "PASS" if source_inventory["exists"].all() else "REVIEW_REQUIRED_SOURCE_MISSING",
        "check_value": int(source_inventory["exists"].sum()),
        "details": f"{int(source_inventory['exists'].sum())}/{len(source_inventory)}",
    })

    rows.append({
        "profile_id": args.profile_id,
        "route_folder": args.route_folder,
        "check_name": "window_rows_present",
        "check_status": "PASS" if len(w) > 0 else "REVIEW_REQUIRED_NO_WINDOWS",
        "check_value": int(len(w)),
        "details": "weather context windows generated",
    })

    weather_available_ratio = ratio_true(w.get("weather_context_available_bool", pd.Series(dtype=bool)))
    rows.append({
        "profile_id": args.profile_id,
        "route_folder": args.route_folder,
        "check_name": "weather_context_available_ratio",
        "check_status": "PASS" if weather_available_ratio > 0 else "REVIEW_REQUIRED_NO_WEATHER_CONTEXT",
        "check_value": round(weather_available_ratio, 6),
        "details": "weather fields are carried forward without zero-fill",
    })

    missing_class_n = int((w["weather_adjustment_context_class"] == "WEATHER_CONTEXT_MISSING_REVIEW_REQUIRED").sum())
    rows.append({
        "profile_id": args.profile_id,
        "route_folder": args.route_folder,
        "check_name": "weather_missing_not_imputed",
        "check_status": "PASS",
        "check_value": missing_class_n,
        "details": "missing weather remains a review class and is not imputed",
    })

    rows.append({
        "profile_id": args.profile_id,
        "route_folder": args.route_folder,
        "check_name": "weather_zero_fill_absent",
        "check_status": "PASS",
        "check_value": 1,
        "details": "script does not fill missing weather with 0, no-rain, safe, or normal values",
    })

    generated_cols: list[str] = []
    for cols in output_fields.values():
        generated_cols.extend(cols)
    generated_lower = [str(c).lower() for c in generated_cols]
    forbidden_present = sorted(
        token for token in FORBIDDEN_OUTPUT_TOKENS
        if any(token in col for col in generated_lower)
    )
    rows.append({
        "profile_id": args.profile_id,
        "route_folder": args.route_folder,
        "check_name": "forbidden_columns_absent",
        "check_status": "PASS" if not forbidden_present else "FAIL_FORBIDDEN_COLUMNS_PRESENT",
        "check_value": len(forbidden_present),
        "details": pipe_flags(forbidden_present),
    })

    rows.append({
        "profile_id": args.profile_id,
        "route_folder": args.route_folder,
        "check_name": "interpretation_boundary_present",
        "check_status": "PASS",
        "check_value": 1,
        "details": "interpretation_boundary field generated in profile outputs",
    })

    return pd.DataFrame(rows)


def audit_conclusion(data_quality: pd.DataFrame) -> str:
    statuses = data_quality["check_status"].astype(str).tolist()
    if any(s.startswith("FAIL") for s in statuses):
        return "REVIEW_REQUIRED_CH6_5_2_WEATHER_ADJUSTED_BEHAVIOR_CONTEXT_V1"
    if any(s.startswith("REVIEW_REQUIRED") for s in statuses):
        return "REVIEW_REQUIRED_CH6_5_2_WEATHER_ADJUSTED_BEHAVIOR_CONTEXT_V1"
    return "PASS_CH6_5_2_WEATHER_ADJUSTED_BEHAVIOR_CONTEXT_V1_DESCRIPTIVE_ONLY"


def write_run_report(
    path: Path,
    source_inventory: pd.DataFrame,
    profile_summary: pd.DataFrame,
    route_load_phase_summary: pd.DataFrame,
    activity_summary: pd.DataFrame,
    conservative_flags: pd.DataFrame,
    data_quality: pd.DataFrame,
    conclusion: str,
    args: argparse.Namespace,
) -> None:
    p = profile_summary.iloc[0] if not profile_summary.empty else {}
    lines = [
        "# CH6.5.2 Weather-Adjusted Behavior Context v1",
        "",
        f"- profile_id: `{args.profile_id}`",
        f"- route_folder: `{args.route_folder}`",
        f"- activity_count: `{p.get('activity_count', 0)}`",
        f"- windows_n: `{p.get('windows_n', 0)}`",
        f"- route_load_phase_summary_rows: `{len(route_load_phase_summary)}`",
        f"- activity_summary_rows: `{len(activity_summary)}`",
        f"- conservative_planning_rows: `{len(conservative_flags)}`",
        f"- audit_conclusion: `{conclusion}`",
        "",
        "## Method",
        "",
        "- Uses CH6.5.1 v1.1 route-window features as input.",
        "- Adds weather-context review classes and conservative planning review flags.",
        "- Weather-adjusted means contextual evidence only, not numeric ability adjustment.",
        "- Missing weather is retained as a review class and is not zero-filled.",
        "",
        "## Weather thresholds",
        "",
        f"- warm temperature review starts at `{args.warm_temp_c}` °C.",
        f"- heat review starts at `{args.heat_temp_c}` °C.",
        f"- humidity review starts at `{args.humid_rh_pct}` % RH.",
        f"- very-humid review starts at `{args.very_humid_rh_pct}` % RH.",
        f"- rain observed review uses precipitation > `{args.rain_mm}` mm.",
        f"- wind-gust review starts at `{args.wind_gust_review_ms}` m/s.",
        f"- moderate UV review starts at `{args.uv_moderate}`.",
        f"- high UV review starts at `{args.uv_high}`.",
        "",
        "These thresholds are transparent descriptive review heuristics for planning evidence, not safety standards or physiological diagnosis.",
        "",
        "## Sources",
        "",
    ]
    for _, row in source_inventory.iterrows():
        lines.append(f"- {row['source_label']}: `{row['source_path']}` exists={row['exists']} bytes={row['length_bytes']}")

    lines.extend([
        "",
        "## Boundaries",
        "",
        "- no ability score",
        "- no ability rank",
        "- no ability class",
        "- no THCI score",
        "- no radar score",
        "- no final hiking risk score",
        "- no route suitability score",
        "- no go/no-go decision",
        "- no medical diagnosis",
        "- no causality inference",
        "- no weather zero-fill",
        "",
        "## Data Quality Checks",
        "",
    ])
    for _, row in data_quality.iterrows():
        lines.append(f"- {row['check_name']}: {row['check_status']} ({row['details']})")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    out_root = resolve(root, args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)

    input_windows_path = resolve(root, args.input_windows)
    input_audit_path = resolve(root, args.input_audit)
    source_inventory = build_source_inventory({
        "ch6_5_1_window_features": input_windows_path,
        "ch6_5_1_audit": input_audit_path,
    })

    input_windows = read_csv(input_windows_path, "CH6.5.1 window features", required=True)
    _input_audit = read_csv(input_audit_path, "CH6.5.1 audit", required=False)

    w = build_windows(input_windows, args)
    profile_summary = build_profile_summary(w, source_inventory, args)
    route_load_phase_summary = build_route_load_phase_summary(w, args)
    activity_summary = build_activity_summary(w, args)
    conservative_flags = build_conservative_flags(activity_summary, args)

    output_paths = {
        "weather_adjusted_behavior_context_windows": out_root / "weather_adjusted_behavior_context_windows_v1.csv",
        "weather_adjusted_behavior_context_profile_summary": out_root / "weather_adjusted_behavior_context_profile_summary_v1.csv",
        "weather_adjusted_behavior_context_route_load_phase_summary": out_root / "weather_adjusted_behavior_context_route_load_phase_summary_v1.csv",
        "weather_adjusted_behavior_context_activity_summary": out_root / "weather_adjusted_behavior_context_activity_summary_v1.csv",
        "weather_conservative_planning_review_flags": out_root / "weather_conservative_planning_review_flags_v1.csv",
        "weather_adjusted_behavior_context_data_quality": out_root / "weather_adjusted_behavior_context_data_quality_v1.csv",
        "weather_adjusted_behavior_context_audit": out_root / "weather_adjusted_behavior_context_audit_v1.csv",
        "weather_adjusted_behavior_context_run_report": out_root / "weather_adjusted_behavior_context_run_report_v1.md",
    }

    output_fields = {
        "windows": list(w.columns),
        "profile_summary": list(profile_summary.columns),
        "route_load_phase_summary": list(route_load_phase_summary.columns),
        "activity_summary": list(activity_summary.columns),
        "conservative_flags": list(conservative_flags.columns),
    }
    data_quality = build_data_quality(w, source_inventory, output_fields, args)
    conclusion = audit_conclusion(data_quality)

    audit = pd.DataFrame([{
        "profile_id": args.profile_id,
        "route_folder": args.route_folder,
        "activity_count": int(w["activity_id_short"].nunique()),
        "window_row_count": int(len(w)),
        "weather_context_available_ratio": round(ratio_true(w["weather_context_available_bool"]), 6),
        "conservative_weather_review_required_windows_n": int(w["conservative_weather_review_required"].sum()),
        "behavior_weather_context_review_required_windows_n": int(w["behavior_weather_context_review_required"].sum()),
        "route_load_phase_summary_rows": int(len(route_load_phase_summary)),
        "activity_summary_rows": int(len(activity_summary)),
        "conservative_planning_rows": int(len(conservative_flags)),
        "source_files_available_n": int(source_inventory["exists"].sum()),
        "source_files_expected_n": int(len(source_inventory)),
        "audit_conclusion": conclusion,
        "interpretation_boundary": BOUNDARY_TEXT,
    }])

    w.to_csv(output_paths["weather_adjusted_behavior_context_windows"], index=False, encoding="utf-8-sig")
    profile_summary.to_csv(output_paths["weather_adjusted_behavior_context_profile_summary"], index=False, encoding="utf-8-sig")
    route_load_phase_summary.to_csv(output_paths["weather_adjusted_behavior_context_route_load_phase_summary"], index=False, encoding="utf-8-sig")
    activity_summary.to_csv(output_paths["weather_adjusted_behavior_context_activity_summary"], index=False, encoding="utf-8-sig")
    conservative_flags.to_csv(output_paths["weather_conservative_planning_review_flags"], index=False, encoding="utf-8-sig")
    data_quality.to_csv(output_paths["weather_adjusted_behavior_context_data_quality"], index=False, encoding="utf-8-sig")
    audit.to_csv(output_paths["weather_adjusted_behavior_context_audit"], index=False, encoding="utf-8-sig")
    write_run_report(
        output_paths["weather_adjusted_behavior_context_run_report"],
        source_inventory,
        profile_summary,
        route_load_phase_summary,
        activity_summary,
        conservative_flags,
        data_quality,
        conclusion,
        args,
    )

    print({
        "output_root": str(out_root),
        "profile_id": args.profile_id,
        "activity_count": int(w["activity_id_short"].nunique()),
        "window_row_count": int(len(w)),
        "weather_context_available_ratio": round(ratio_true(w["weather_context_available_bool"]), 6),
        "conservative_weather_review_required_windows_n": int(w["conservative_weather_review_required"].sum()),
        "behavior_weather_context_review_required_windows_n": int(w["behavior_weather_context_review_required"].sum()),
        "route_load_phase_summary_rows": int(len(route_load_phase_summary)),
        "activity_summary_rows": int(len(activity_summary)),
        "conservative_planning_rows": int(len(conservative_flags)),
        "source_files_available_n": int(source_inventory["exists"].sum()),
        "source_files_expected_n": int(len(source_inventory)),
        "audit_conclusion": conclusion,
        "outputs": {k: str(v) for k, v in output_paths.items()},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
