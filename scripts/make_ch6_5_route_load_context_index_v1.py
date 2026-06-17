#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build Chapter 6.5 route load context index v1 evidence tables.

This script creates descriptive route-load context evidence from existing
50 m activity route-load/behavior windows. The route-load context index uses
only route, terrain, and map-derived factors. Behavior response flags are
derived separately and never feed back into the route-load index.

Boundaries:
- descriptive route-load context evidence only
- no ability score, ability rank, ability class
- no THCI score, radar score, or final hiking risk score
- no weather zero-fill
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


DEFAULT_INPUT_CSV = (
    "outputs/ib3_personal_hiking_features_route_load_comparison_full25_v1/"
    "activity_route_load_behavior_response_windows.csv"
)
DEFAULT_OUTPUT_ROOT = (
    "outputs/report_figures/ch6_5_route_load_context_index_v1"
)

LOW_SPEED_THRESHOLD_MPS = 0.7

ROUTE_LOAD_WEIGHTS = {
    "vertical_load_norm": 0.30,
    "slope_load_norm": 0.20,
    "ib2_effort_load_norm": 0.25,
    "terrain_load_norm": 0.15,
    "steps_surface_load_norm": 0.10,
}

PROHIBITED_OUTPUT_TOKENS = (
    "ability_score",
    "ability_rank",
    "ability_class",
    "thci_score",
    "radar_score",
    "final_hiking_risk_score",
)

BOUNDARY_TEXT = (
    "Descriptive route-load context evidence only. The index uses route, "
    "terrain, and map-derived factors only; behavior response and weather "
    "context are descriptive overlays and are not used to compute the index. "
    "No ability score, rank, class, THCI score, radar score, or final hiking "
    "risk score is generated."
)

CANDIDATE_BOUNDARY = (
    "Candidate window means high/very-high route-load context plus an observed "
    "behavior response flag. It is not causality, not ability scoring, and not "
    "a final risk assessment."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=r"D:\mountain_work\115_osm")
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def clip01(series: pd.Series) -> pd.Series:
    return numeric(series).clip(lower=0, upper=1)


def pipe_flags(flags: Iterable[str]) -> str:
    clean = [str(flag) for flag in flags if str(flag)]
    return "|".join(clean) if clean else "NONE"


def require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise KeyError(f"Missing required input columns: {missing}")


def normalize_by_global_max(series: pd.Series) -> pd.Series:
    values = numeric(series)
    max_value = values.max(skipna=True)
    if pd.isna(max_value) or max_value <= 0:
        return pd.Series(0.0, index=series.index)
    return (values / float(max_value)).clip(lower=0, upper=1)


def route_load_band(value: float) -> str:
    if pd.isna(value):
        return "ROUTE_LOAD_CONTEXT_MISSING"
    if value < 35:
        return "LOWER_ROUTE_LOAD_CONTEXT"
    if value < 60:
        return "MODERATE_ROUTE_LOAD_CONTEXT"
    if value < 80:
        return "HIGH_ROUTE_LOAD_CONTEXT"
    return "VERY_HIGH_ROUTE_LOAD_CONTEXT"


def build_environment_flags(row: pd.Series) -> tuple[str, bool]:
    available_raw = row.get("weather_context_available", "")
    available = str(available_raw).strip().lower() in {"true", "1", "yes", "y"}
    flags_raw = row.get("weather_context_flags", "")
    flags = "" if pd.isna(flags_raw) else str(flags_raw).strip()
    if flags and flags.lower() != "nan":
        return flags, True
    if available:
        return "WEATHER_CONTEXT_AVAILABLE_NO_FLAGS", True
    return "WEATHER_CONTEXT_MISSING", False


def build_route_load_windows(df: pd.DataFrame) -> pd.DataFrame:
    required = [
        "activity_id_short",
        "route_distance_window_start_m",
        "route_distance_window_end_m",
        "route_phase",
        "route_profile_elevation_range_m",
        "calibrated_slope_pct_p75_abs",
        "ib2_effort_evidence_median",
        "ib2_terrain_evidence_median",
        "near_steps_ratio",
        "weather_context_flags",
        "weather_context_available",
        "heart_rate_bpm_median",
        "speed_mps_median",
        "low_speed_ratio",
        "stopped_ratio",
    ]
    require_columns(df, required)

    out = df.copy()

    out["vertical_load_norm"] = clip01(numeric(out["route_profile_elevation_range_m"]) / 20.0)

    slope_raw = numeric(out["calibrated_slope_pct_p75_abs"])
    slope_from_slope = clip01(slope_raw / 40.0)
    slope_missing = slope_raw.isna()
    out["slope_load_norm"] = slope_from_slope.where(~slope_missing, out["vertical_load_norm"])
    out["slope_load_source"] = np.where(
        slope_missing,
        "SLOPE_LOAD_FALLBACK_VERTICAL_RANGE",
        "CALIBRATED_SLOPE_P75_ABS",
    )

    out["ib2_effort_load_norm"] = normalize_by_global_max(out["ib2_effort_evidence_median"])
    out["terrain_load_norm"] = normalize_by_global_max(out["ib2_terrain_evidence_median"])
    out["steps_surface_load_norm"] = clip01(out["near_steps_ratio"])

    out["route_load_context_index_0_100"] = 100.0 * sum(
        ROUTE_LOAD_WEIGHTS[col] * out[col] for col in ROUTE_LOAD_WEIGHTS
    )
    out["route_load_context_index_0_100"] = out["route_load_context_index_0_100"].round(3)
    out["route_load_context_band"] = out["route_load_context_index_0_100"].apply(route_load_band)

    reason_flags = []
    for _, row in out.iterrows():
        flags: list[str] = []
        if row["vertical_load_norm"] >= 0.75:
            flags.append("VERTICAL_RANGE_HIGH")
        if row["slope_load_norm"] >= 0.75:
            flags.append("SLOPE_HIGH")
        if row["ib2_effort_load_norm"] >= 0.75:
            flags.append("IB2_EFFORT_HIGH")
        if row["terrain_load_norm"] >= 0.75:
            flags.append("TERRAIN_HIGH")
        if row["steps_surface_load_norm"] >= 0.75:
            flags.append("STEPS_SURFACE_HIGH")
        if row["slope_load_source"] == "SLOPE_LOAD_FALLBACK_VERTICAL_RANGE":
            flags.append("SLOPE_LOAD_FALLBACK_VERTICAL_RANGE")
        reason_flags.append(pipe_flags(flags))
    out["route_load_context_reason_flags"] = reason_flags

    env_pairs = out.apply(build_environment_flags, axis=1)
    out["environment_context_flags"] = [pair[0] for pair in env_pairs]
    out["environment_context_available"] = [pair[1] for pair in env_pairs]

    hr = numeric(out["heart_rate_bpm_median"])
    activity_hr_p75 = hr.groupby(out["activity_id_short"]).transform(
        lambda s: s.quantile(0.75) if s.notna().any() else np.nan
    )
    out["activity_heart_rate_bpm_median_p75"] = activity_hr_p75

    behavior_flags = []
    behavior_signal_count = []
    for _, row in out.iterrows():
        flags: list[str] = []
        signal_flags: list[str] = []

        hr_value = row.get("heart_rate_bpm_median", np.nan)
        hr_p75 = row.get("activity_heart_rate_bpm_median_p75", np.nan)
        if pd.isna(hr_value) or pd.isna(hr_p75):
            flags.append("HR_MISSING")
        elif float(hr_value) >= float(hr_p75):
            flags.append("ACTIVITY_RELATIVE_HIGH_HR_WINDOW")
            signal_flags.append("ACTIVITY_RELATIVE_HIGH_HR_WINDOW")

        speed_value = row.get("speed_mps_median", np.nan)
        if pd.notna(speed_value) and float(speed_value) < LOW_SPEED_THRESHOLD_MPS:
            flags.append("SPEED_BELOW_LOW_SPEED_THRESHOLD")
            signal_flags.append("SPEED_BELOW_LOW_SPEED_THRESHOLD")

        low_speed_ratio = row.get("low_speed_ratio", np.nan)
        if pd.notna(low_speed_ratio) and float(low_speed_ratio) >= 0.30:
            flags.append("LOW_SPEED_RATIO_HIGH")
            signal_flags.append("LOW_SPEED_RATIO_HIGH")

        stopped_ratio = row.get("stopped_ratio", np.nan)
        if pd.notna(stopped_ratio) and float(stopped_ratio) > 0.05:
            flags.append("STOP_RATIO_OBSERVED")
            signal_flags.append("STOP_RATIO_OBSERVED")

        behavior_flags.append(pipe_flags(flags))
        behavior_signal_count.append(len(set(signal_flags)))

    out["behavior_response_flags"] = behavior_flags
    out["behavior_response_signal_flag_count"] = behavior_signal_count
    out["route_load_context_boundary"] = BOUNDARY_TEXT

    keep = [
        "schema_version",
        "activity_id_short",
        "activity_id_full",
        "route_distance_window_start_m",
        "route_distance_window_end_m",
        "route_phase",
        "point_count",
        "route_profile_elevation_range_m",
        "calibrated_slope_pct_p75_abs",
        "slope_load_source",
        "ib2_effort_evidence_median",
        "ib2_terrain_evidence_median",
        "near_steps_ratio",
        "vertical_load_norm",
        "slope_load_norm",
        "ib2_effort_load_norm",
        "terrain_load_norm",
        "steps_surface_load_norm",
        "route_load_context_index_0_100",
        "route_load_context_band",
        "route_load_context_reason_flags",
        "weather_context_flags",
        "weather_context_available",
        "environment_context_flags",
        "environment_context_available",
        "temperature_c",
        "relative_humidity_pct",
        "precipitation_mm",
        "wind_speed_ms",
        "wind_gust_ms",
        "uv_index",
        "heart_rate_bpm_median",
        "activity_heart_rate_bpm_median_p75",
        "speed_mps_median",
        "low_speed_ratio",
        "stopped_ratio",
        "behavior_response_flags",
        "behavior_response_signal_flag_count",
        "window_qa_flags",
        "route_load_context_boundary",
    ]
    existing_keep = [col for col in keep if col in out.columns]
    return out[existing_keep].copy()


def build_candidate_windows(windows: pd.DataFrame) -> pd.DataFrame:
    high_load = windows["route_load_context_band"].isin(
        ["HIGH_ROUTE_LOAD_CONTEXT", "VERY_HIGH_ROUTE_LOAD_CONTEXT"]
    )
    has_behavior_signal = numeric(windows["behavior_response_signal_flag_count"]).fillna(0) > 0
    candidates = windows.loc[high_load & has_behavior_signal].copy()
    candidates["candidate_window_label"] = "ROUTE_LOAD_BEHAVIOR_RESPONSE_CANDIDATE"
    candidates["candidate_window_boundary"] = CANDIDATE_BOUNDARY
    return candidates


def build_activity_summary(windows: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    candidate_counts = candidates.groupby("activity_id_short").size()
    rows = []
    for activity_id, group in windows.groupby("activity_id_short", dropna=False):
        band_counts = group["route_load_context_band"].value_counts()
        windows_n = int(len(group))
        high_n = int(band_counts.get("HIGH_ROUTE_LOAD_CONTEXT", 0))
        very_high_n = int(band_counts.get("VERY_HIGH_ROUTE_LOAD_CONTEXT", 0))
        candidate_n = int(candidate_counts.get(activity_id, 0))
        rows.append(
            {
                "activity_id_short": activity_id,
                "windows_n": windows_n,
                "lower_load_windows_n": int(band_counts.get("LOWER_ROUTE_LOAD_CONTEXT", 0)),
                "moderate_load_windows_n": int(band_counts.get("MODERATE_ROUTE_LOAD_CONTEXT", 0)),
                "high_load_windows_n": high_n,
                "very_high_load_windows_n": very_high_n,
                "candidate_windows_n": candidate_n,
                "max_route_load_context_index_0_100": round(
                    float(group["route_load_context_index_0_100"].max(skipna=True)), 3
                ),
                "median_route_load_context_index_0_100": round(
                    float(group["route_load_context_index_0_100"].median(skipna=True)), 3
                ),
                "high_or_very_high_load_ratio": round((high_n + very_high_n) / windows_n, 6)
                if windows_n
                else np.nan,
                "candidate_window_ratio": round(candidate_n / windows_n, 6) if windows_n else np.nan,
                "summary_boundary": BOUNDARY_TEXT,
            }
        )
    return pd.DataFrame(rows).sort_values("activity_id_short").reset_index(drop=True)


def audit_conclusion(windows: pd.DataFrame, candidates: pd.DataFrame) -> tuple[str, list[str]]:
    issues: list[str] = []
    generated_columns = set(windows.columns) | set(candidates.columns)
    prohibited = sorted(token for token in PROHIBITED_OUTPUT_TOKENS if token in generated_columns)
    if prohibited:
        issues.append("PROHIBITED_OUTPUT_COLUMNS_PRESENT:" + "|".join(prohibited))
    if windows["route_load_context_index_0_100"].isna().any():
        issues.append("ROUTE_LOAD_CONTEXT_INDEX_MISSING")
    if not set(windows["route_load_context_band"]).issubset(
        {
            "LOWER_ROUTE_LOAD_CONTEXT",
            "MODERATE_ROUTE_LOAD_CONTEXT",
            "HIGH_ROUTE_LOAD_CONTEXT",
            "VERY_HIGH_ROUTE_LOAD_CONTEXT",
            "ROUTE_LOAD_CONTEXT_MISSING",
        }
    ):
        issues.append("UNEXPECTED_ROUTE_LOAD_CONTEXT_BAND")
    if issues:
        return "REVIEW_REQUIRED_ROUTE_LOAD_CONTEXT_INDEX_V1", issues
    return "PASS_ROUTE_LOAD_CONTEXT_INDEX_V1_DESCRIPTIVE_ONLY", issues


def write_report(
    report_path: Path,
    input_csv: Path,
    output_root: Path,
    windows: pd.DataFrame,
    summary: pd.DataFrame,
    candidates: pd.DataFrame,
    conclusion: str,
    issues: list[str],
) -> None:
    band_dist = windows["route_load_context_band"].value_counts().sort_index()
    env_dist = windows["environment_context_flags"].value_counts().head(20)
    lines = [
        "# Chapter 6.5 Route Load Context Index v1",
        "",
        f"- input_csv: `{input_csv}`",
        f"- output_root: `{output_root}`",
        f"- window_row_count: `{len(windows)}`",
        f"- activity_summary_row_count: `{len(summary)}`",
        f"- candidate_window_row_count: `{len(candidates)}`",
        f"- audit_conclusion: `{conclusion}`",
        f"- audit_issues: `{pipe_flags(issues)}`",
        "",
        "## Method",
        "",
        "- `route_load_context_index_0_100` uses route-load base factors only.",
        "- Factors: vertical range, slope context, IB2 effort evidence, IB2 terrain evidence, and near-steps ratio.",
        "- Behavior response is not used to compute route-load context index.",
        "- Weather context is descriptive only and is not included in the index.",
        "- No weather zero-fill is performed.",
        "- `route_phase=UNKNOWN` is not used for ascent/descent comparison.",
        "",
        "## Boundaries",
        "",
        "- descriptive route-load context evidence only",
        "- no ability score",
        "- no ability rank",
        "- no ability class",
        "- no THCI score",
        "- no radar score",
        "- no final hiking risk score",
        "- candidate windows are not causality claims",
        "- candidate windows are not ability labels",
        "",
        "## Band Distribution",
        "",
    ]
    lines.extend(f"- {band}: {int(count)}" for band, count in band_dist.items())
    lines.extend(["", "## Environment Context Flags Top Values", ""])
    lines.extend(f"- {flag}: {int(count)}" for flag, count in env_dist.items())
    lines.extend(
        [
            "",
            "## Candidate Window Rule",
            "",
            "- route_load_context_band is HIGH_ROUTE_LOAD_CONTEXT or VERY_HIGH_ROUTE_LOAD_CONTEXT",
            "- and at least one observed behavior response signal exists",
            "- HR_MISSING alone is retained as a QA flag but is not treated as a behavior response signal for candidate selection",
            "",
            "## Outputs",
            "",
            "- `route_load_context_windows_v1.csv`",
            "- `route_load_context_activity_summary_v1.csv`",
            "- `route_load_behavior_response_candidate_windows_v1.csv`",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    root = Path(args.root)
    input_csv = resolve(root, args.input_csv)
    output_root = resolve(root, args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_csv, encoding="utf-8-sig")
    df.columns = [str(col).strip() for col in df.columns]

    windows = build_route_load_windows(df)
    candidates = build_candidate_windows(windows)
    summary = build_activity_summary(windows, candidates)
    conclusion, issues = audit_conclusion(windows, candidates)

    windows_csv = output_root / "route_load_context_windows_v1.csv"
    summary_csv = output_root / "route_load_context_activity_summary_v1.csv"
    candidates_csv = output_root / "route_load_behavior_response_candidate_windows_v1.csv"
    report_md = output_root / "route_load_context_index_run_report_v1.md"

    windows.to_csv(windows_csv, index=False, encoding="utf-8-sig")
    summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")
    candidates.to_csv(candidates_csv, index=False, encoding="utf-8-sig")
    write_report(report_md, input_csv, output_root, windows, summary, candidates, conclusion, issues)

    band_distribution = windows["route_load_context_band"].value_counts().sort_index().to_dict()
    print(
        {
            "windows_csv": str(windows_csv),
            "summary_csv": str(summary_csv),
            "candidates_csv": str(candidates_csv),
            "report_md": str(report_md),
            "activity_summary_row_count": int(len(summary)),
            "window_row_count": int(len(windows)),
            "candidate_window_row_count": int(len(candidates)),
            "band_distribution": {str(k): int(v) for k, v in band_distribution.items()},
            "audit_conclusion": conclusion,
        }
    )


if __name__ == "__main__":
    main()
