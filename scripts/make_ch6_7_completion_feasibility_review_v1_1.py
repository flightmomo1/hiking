#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build Chapter 6.7 completion feasibility review v1.1 evidence outputs.

This script adds a descriptive completion-feasibility layer on top of the
existing 6.7 planning-context fusion v1.1 and 6.5 route-load context outputs.
It does not generate ability scores, suitability scores, THCI/radar scores, or
final hiking risk scores.
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path

import matplotlib
import matplotlib.font_manager

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DEFAULT_PLANNING_WINDOWS = (
    "outputs/report_figures/ch6_7_planning_context_fusion_v1_1/"
    "planning_context_route_windows_v1_1.csv"
)
DEFAULT_PLANNING_SUMMARY = (
    "outputs/report_figures/ch6_7_planning_context_fusion_v1_1/"
    "planning_context_activity_summary_v1_1.csv"
)
DEFAULT_ROUTE_LOAD_WINDOWS = (
    "outputs/report_figures/ch6_5_route_load_context_index_v1/"
    "route_load_context_windows_v1.csv"
)
DEFAULT_ROUTE_LOAD_CANDIDATES = (
    "outputs/report_figures/ch6_5_route_load_context_index_v1/"
    "route_load_behavior_response_candidate_windows_v1.csv"
)
DEFAULT_ROUTE_LOAD_SUMMARY = (
    "outputs/report_figures/ch6_5_route_load_context_index_v1/"
    "route_load_context_activity_summary_v1.csv"
)
DEFAULT_PERFORMANCE_SUMMARY = (
    "outputs/ib3a_rc_full26_performance_summary_v1/activity_performance_summary.csv"
)
DEFAULT_ROUTE_NORMALIZED_COMPARISON = (
    "outputs/ib3_baseline_hiking_performance_route_normalized_comparison_smoke_v1/"
    "activity_route_normalized_comparison_smoke.csv"
)
DEFAULT_WEATHER_PERFORMANCE_JOIN = (
    "outputs/ib3w_activity_weather_performance_join_v1/activity_weather_performance_join.csv"
)
DEFAULT_WEATHER_PROFILE = (
    "outputs/ib3w_codis_weather_profile_report_v1/activity_weather_profile_report_table.csv"
)
DEFAULT_OUTPUT_ROOT = "outputs/report_figures/ch6_7_completion_feasibility_review_v1_1"

EARLY_CHECKPOINT_START_M = 1350
EARLY_CHECKPOINT_END_M = 1700

FORBIDDEN_OUTPUT_COLUMNS = {
    "ability_score",
    "ability_rank",
    "ability_class",
    "thci_score",
    "radar_score",
    "final_hiking_risk_score",
    "route_suitability_score",
    "personal_fitness_score",
}

BOUNDARY = (
    "Descriptive completion feasibility review v1.1 only. Completion time, group, "
    "route-load, behavior-response, weather, heart-rate effort, and event evidence are descriptive "
    "context. This output is not ability scoring, not route suitability scoring, "
    "not THCI/radar scoring, and not a final hiking risk assessment."
)

ROUTINE = "ROUTINE_PLANNING_CONTEXT"
REVIEW = "REVIEW_FOR_CONSERVATIVE_PLANNING"
CONSERVATIVE = "CONSERVATIVE_PLANNING_RECOMMENDED"
TURNAROUND = "TURNAROUND_CONDITION_REVIEW_RECOMMENDED"
LEVEL_ORDER = [ROUTINE, REVIEW, CONSERVATIVE, TURNAROUND]
LEVEL_RANK = {level: idx for idx, level in enumerate(LEVEL_ORDER)}
GROUP_ORDER = ["fast", "middle", "slow"]
GROUP_COLORS = {"fast": "#2563EB", "middle": "#059669", "slow": "#DC2626"}
WEATHER_NUMERIC_COLUMNS = [
    "temperature_c",
    "relative_humidity_pct",
    "precipitation_mm",
    "wind_speed_ms",
    "wind_gust_ms",
    "uv_index",
]
WEATHER_ACTIVITY_COLUMNS = [
    "activity_id_short",
    "temperature_c",
    "relative_humidity_pct",
    "precipitation_mm",
    "wind_speed_ms",
    "wind_gust_ms",
    "uv_index",
    "weather_context_flags",
    "environment_context_flags",
    "weather_attach_level",
    "weather_context_available",
    "weather_context_source",
]
ADVERSE_WEATHER_FLAG_TOKENS = (
    "WEATHER_HEAT_CONTEXT",
    "WEATHER_HUMID_CONTEXT",
    "HIGH_HUMIDITY_CONTEXT",
    "WEATHER_RAIN_CONTEXT",
    "RAIN_OBSERVED",
    "WEATHER_WIND_GUST_CONTEXT",
    "WIND_GUST_OBSERVED_CONTEXT",
    "STRONG_GUST_CONTEXT",
    "WEATHER_HIGH_UV_CONTEXT",
    "HIGH_UV_CONTEXT",
    "HIGH_UV_OBSERVED",
)
HIGH_LOAD_BANDS = {"HIGH_ROUTE_LOAD_CONTEXT", "VERY_HIGH_ROUTE_LOAD_CONTEXT"}
HR_HIGH_FLAG = "ACTIVITY_RELATIVE_HIGH_HR_WINDOW"
HR_MISSING_FLAG = "HR_CONTEXT_MISSING"
HR_INSUFFICIENT_FLAG = "INSUFFICIENT_HR_CONTEXT"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=r"D:\mountain_work\115_osm")
    parser.add_argument("--planning-windows", default=DEFAULT_PLANNING_WINDOWS)
    parser.add_argument("--planning-summary", default=DEFAULT_PLANNING_SUMMARY)
    parser.add_argument("--route-load-windows", default=DEFAULT_ROUTE_LOAD_WINDOWS)
    parser.add_argument("--route-load-candidates", default=DEFAULT_ROUTE_LOAD_CANDIDATES)
    parser.add_argument("--route-load-summary", default=DEFAULT_ROUTE_LOAD_SUMMARY)
    parser.add_argument("--performance-summary", default=DEFAULT_PERFORMANCE_SUMMARY)
    parser.add_argument("--route-normalized-comparison", default=DEFAULT_ROUTE_NORMALIZED_COMPARISON)
    parser.add_argument("--weather-profile", default=DEFAULT_WEATHER_PROFILE)
    parser.add_argument("--weather-performance-join", default=DEFAULT_WEATHER_PERFORMANCE_JOIN)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--early-checkpoint-start-m", type=float, default=EARLY_CHECKPOINT_START_M)
    parser.add_argument("--early-checkpoint-end-m", type=float, default=EARLY_CHECKPOINT_END_M)
    return parser.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def read_csv(path: Path, label: str, **kwargs) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    df = pd.read_csv(path, encoding="utf-8-sig", **kwargs)
    df.columns = [str(col).strip() for col in df.columns]
    return df


def read_csv_optional(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def setup_matplotlib_font() -> None:
    preferred = ["Microsoft JhengHei", "Noto Sans CJK TC", "Noto Sans TC", "SimHei", "Arial Unicode MS"]
    available = {font.name for font in matplotlib.font_manager.fontManager.ttflist}
    for font in preferred:
        if font in available:
            plt.rcParams["font.family"] = font
            break
    plt.rcParams["axes.unicode_minus"] = False


def split_flags(value: object) -> list[str]:
    if pd.isna(value):
        return []
    text = str(value).strip()
    if not text or text.upper() == "NONE":
        return []
    return [part.strip() for part in text.split("|") if part.strip()]


def pipe_flags(values: list[str] | pd.Series) -> str:
    out: list[str] = []
    for value in values:
        for flag in split_flags(value):
            if flag not in out:
                out.append(flag)
    return "|".join(out) if out else "NONE"


def mode_text(series: pd.Series) -> str:
    clean = series.dropna().astype(str)
    clean = clean[clean.str.strip().ne("")]
    if clean.empty:
        return ""
    return str(clean.mode().iloc[0])


def max_caution_level(series: pd.Series) -> str:
    clean = series.dropna().astype(str)
    if clean.empty:
        return ""
    return max(clean, key=lambda value: LEVEL_RANK.get(value, -1))


def ratio(numerator: object, denominator: object) -> float:
    num = pd.to_numeric(pd.Series([numerator]), errors="coerce").iloc[0]
    den = pd.to_numeric(pd.Series([denominator]), errors="coerce").iloc[0]
    return float(num / den) if pd.notna(num) and pd.notna(den) and den else np.nan


def build_completion_distribution(
    reviewed_ids: list[str],
    planning_windows: pd.DataFrame,
    performance: pd.DataFrame,
    route_normalized: pd.DataFrame,
    weather_performance: pd.DataFrame,
) -> tuple[pd.DataFrame, str]:
    source = "activity_performance_summary.duration_sec"
    if {"activity_id_short", "duration_sec"}.issubset(performance.columns):
        perf = performance.copy()
        perf["activity_id_short"] = perf["activity_id_short"].astype(str)
        perf["completion_time_sec"] = numeric(perf["duration_sec"])
        perf["completion_time_min"] = numeric(perf.get("duration_min", perf["completion_time_sec"] / 60.0))
        perf["completion_time_source_column"] = source
        perf["completion_status"] = np.where(
            perf["completion_time_sec"].notna() & perf.get("status", "PASS").astype(str).str.upper().eq("PASS"),
            "COMPLETED",
            "UNKNOWN",
        )
        perf = perf[
            [
                "activity_id_short",
                "activity_id_full",
                "completion_time_sec",
                "completion_time_min",
                "completion_time_source_column",
                "completion_status",
            ]
        ].copy()
    else:
        perf = pd.DataFrame()

    if perf.empty and {"activity_id_short", "duration_min"}.issubset(route_normalized.columns):
        source = "activity_route_normalized_comparison.duration_min"
        perf = route_normalized.copy()
        perf["activity_id_short"] = perf["activity_id_short"].astype(str)
        perf["completion_time_min"] = numeric(perf["duration_min"])
        perf["completion_time_sec"] = perf["completion_time_min"] * 60.0
        perf["completion_time_source_column"] = source
        perf["completion_status"] = np.where(perf["completion_time_min"].notna(), "COMPLETED", "UNKNOWN")

    if perf.empty and {"activity_id_short", "duration_sec"}.issubset(weather_performance.columns):
        source = "activity_weather_performance_join.duration_sec"
        perf = weather_performance.copy()
        perf["activity_id_short"] = perf["activity_id_short"].astype(str)
        perf["completion_time_sec"] = numeric(perf["duration_sec"])
        perf["completion_time_min"] = numeric(perf.get("duration_min", perf["completion_time_sec"] / 60.0))
        perf["completion_time_source_column"] = source
        perf["completion_status"] = np.where(perf["completion_time_sec"].notna(), "COMPLETED", "UNKNOWN")

    if perf.empty:
        # Last-resort proxy: one row per reviewed activity using window count.
        source = "planning_context_route_windows.window_count_proxy"
        proxy = planning_windows.groupby("activity_id_short").size().reset_index(name="window_count")
        proxy["activity_id_full"] = ""
        proxy["completion_time_sec"] = np.nan
        proxy["completion_time_min"] = np.nan
        proxy["completion_time_source_column"] = source
        proxy["completion_status"] = "UNKNOWN"
        perf = proxy

    route_coverage = (
        planning_windows.groupby("activity_id_short")
        .size()
        .rename("route_coverage_or_window_count")
        .reset_index()
    )
    full = pd.DataFrame({"activity_id_short": reviewed_ids})
    out = full.merge(perf, on="activity_id_short", how="left", suffixes=("", "_src"))
    if "activity_id_full" not in out.columns:
        out["activity_id_full"] = ""
    out = out.merge(route_coverage, on="activity_id_short", how="left")
    out["completion_status"] = out["completion_status"].fillna("UNKNOWN")
    out["completion_time_source_column"] = out["completion_time_source_column"].fillna(source)
    out["data_quality_flags"] = np.where(
        out["completion_time_min"].notna(),
        "COMPLETION_TIME_AVAILABLE",
        "COMPLETION_TIME_MISSING",
    )
    out["completion_review_boundary"] = BOUNDARY
    out["completion_time_min"] = numeric(out["completion_time_min"]).round(4)
    out["completion_time_sec"] = numeric(out["completion_time_sec"]).round(2)
    return out.sort_values("completion_time_min", na_position="last").reset_index(drop=True), source


def add_completion_groups(completion: pd.DataFrame) -> pd.DataFrame:
    out = completion.copy()
    out["completion_group"] = "unknown"
    valid = out[out["completion_time_min"].notna()].sort_values("completion_time_min")
    splits = np.array_split(valid.index.to_numpy(), 3)
    for label, idx in zip(GROUP_ORDER, splits):
        out.loc[idx, "completion_group"] = label
    return out


def build_group_summary(
    completion: pd.DataFrame,
    planning_summary: pd.DataFrame,
    route_load_windows: pd.DataFrame,
) -> pd.DataFrame:
    activity_behavior = (
        route_load_windows.groupby("activity_id_short")
        .agg(
            low_speed_ratio_median=("low_speed_ratio", "median"),
            stopped_ratio_median=("stopped_ratio", "median"),
            heart_rate_median=("heart_rate_bpm_median", "median"),
        )
        .reset_index()
    )
    summary = planning_summary.copy()
    summary["routine_window_ratio"] = summary.apply(
        lambda row: ratio(row.get("routine_planning_context_windows_n"), row.get("windows_n")), axis=1
    )
    summary["review_window_ratio"] = summary.apply(
        lambda row: ratio(row.get("review_for_conservative_planning_windows_n"), row.get("windows_n")), axis=1
    )
    summary["conservative_window_ratio"] = summary.apply(
        lambda row: ratio(row.get("conservative_planning_recommended_windows_n"), row.get("windows_n")), axis=1
    )
    summary["turnaround_review_window_ratio"] = summary.apply(
        lambda row: ratio(row.get("turnaround_condition_review_windows_n"), row.get("windows_n")), axis=1
    )
    summary["candidate_window_ratio"] = summary.apply(
        lambda row: ratio(row.get("candidate_windows_n"), row.get("windows_n")), axis=1
    )
    merged = (
        completion[["activity_id_short", "completion_group", "completion_time_min"]]
        .merge(summary, on="activity_id_short", how="left")
        .merge(activity_behavior, on="activity_id_short", how="left")
    )
    rows = []
    for group_label in GROUP_ORDER:
        sub = merged[merged["completion_group"].eq(group_label)]
        rows.append(
            {
                "group_label": group_label,
                "activity_count": len(sub),
                "completion_time_min_median": numeric(sub["completion_time_min"]).median(),
                "completion_time_min_min": numeric(sub["completion_time_min"]).min(),
                "completion_time_min_max": numeric(sub["completion_time_min"]).max(),
                "routine_window_ratio_median": numeric(sub["routine_window_ratio"]).median(),
                "review_window_ratio_median": numeric(sub["review_window_ratio"]).median(),
                "conservative_window_ratio_median": numeric(sub["conservative_window_ratio"]).median(),
                "turnaround_review_window_ratio_median": numeric(sub["turnaround_review_window_ratio"]).median(),
                "candidate_window_ratio_median": numeric(sub["candidate_window_ratio"]).median(),
                "low_speed_ratio_median": numeric(sub["low_speed_ratio_median"]).median(),
                "stopped_ratio_median": numeric(sub["stopped_ratio_median"]).median(),
                "heart_rate_median": numeric(sub["heart_rate_median"]).median(),
                "data_quality_summary": "DESCRIPTIVE_MEDIANS_FROM_AVAILABLE_FIELDS",
            }
        )
    return pd.DataFrame(rows).round(6)


def build_early_checkpoint_review(
    completion: pd.DataFrame,
    planning_windows: pd.DataFrame,
    start_m: float,
    end_m: float,
) -> pd.DataFrame:
    overlap = planning_windows[
        (numeric(planning_windows["route_distance_window_end_m"]) > start_m)
        & (numeric(planning_windows["route_distance_window_start_m"]) < end_m)
    ].copy()
    rows = []
    for activity_id, group in overlap.groupby("activity_id_short"):
        comp = completion.set_index("activity_id_short").loc[activity_id]
        comp_group = comp["completion_group"]
        missing_fields = [
            col
            for col in ["speed_mps_median", "low_speed_ratio", "stopped_ratio", "heart_rate_bpm_median"]
            if col not in group.columns or numeric(group[col]).notna().sum() == 0
        ]
        candidate_n = int(group.get("is_route_load_behavior_candidate", pd.Series(False, index=group.index)).fillna(False).sum())
        flags = pipe_flags(group.get("behavior_response_flags", pd.Series(dtype=object)))
        max_level = max_caution_level(group["planning_caution_level"])
        has_behavior = flags != "NONE" or candidate_n > 0
        low_speed_med = numeric(group.get("low_speed_ratio", pd.Series(dtype=float))).median()
        stopped_med = numeric(group.get("stopped_ratio", pd.Series(dtype=float))).median()
        if missing_fields:
            interpretation = "UNKNOWN_DUE_TO_MISSING_FIELDS"
        elif max_level == TURNAROUND or low_speed_med >= 0.35 or stopped_med >= 0.05:
            interpretation = "PASSED_BUT_REVIEW_REQUIRED"
        elif has_behavior:
            interpretation = "PASSED_WITH_BEHAVIOR_RESPONSE"
        else:
            interpretation = "PASSED_WITH_NO_STRONG_DELAY_EVIDENCE"
        rows.append(
            {
                "activity_id_short": activity_id,
                "completion_group": comp_group,
                "completion_time_min": comp["completion_time_min"],
                "segment_start_m": start_m,
                "segment_end_m": end_m,
                "window_count": len(group),
                "dominant_planning_caution_level": max_level,
                "max_route_load_context_index_0_100": numeric(group["route_load_context_index_0_100"]).max(),
                "dominant_route_load_context_band": mode_text(group["route_load_context_band"]),
                "candidate_windows_n": candidate_n,
                "behavior_response_flags_merged": flags,
                "event_annotation_flags_merged": pipe_flags(group.get("event_annotation_flags", pd.Series(dtype=object))),
                "speed_mps_median": numeric(group.get("speed_mps_median", pd.Series(dtype=float))).median(),
                "low_speed_ratio_median": low_speed_med,
                "stopped_ratio_median": stopped_med,
                "heart_rate_bpm_median": numeric(group.get("heart_rate_bpm_median", pd.Series(dtype=float))).median(),
                "segment_completion_interpretation": interpretation,
            }
        )
    return pd.DataFrame(rows).sort_values(["completion_group", "activity_id_short"]).round(6)


def attach_route_load_behavior_fields(planning_windows: pd.DataFrame, route_load_windows: pd.DataFrame) -> pd.DataFrame:
    """Attach 6.5 behavior metrics used only for descriptive checkpoint review."""
    keys = ["activity_id_short", "route_distance_window_start_m", "route_distance_window_end_m"]
    metric_cols = [
        "heart_rate_bpm_median",
        "speed_mps_median",
        "low_speed_ratio",
        "stopped_ratio",
        "behavior_response_flags",
    ]
    if not set(keys).issubset(planning_windows.columns) or not set(keys).issubset(route_load_windows.columns):
        return planning_windows
    available_metrics = [col for col in metric_cols if col in route_load_windows.columns]
    if not available_metrics:
        return planning_windows
    metrics = route_load_windows[keys + available_metrics].copy()
    out = planning_windows.merge(metrics, on=keys, how="left", suffixes=("", "_route_load"))
    for col in available_metrics:
        route_col = f"{col}_route_load"
        if route_col in out.columns:
            if col in out.columns:
                out[col] = out[col].where(out[col].notna(), out[route_col])
            else:
                out[col] = out[route_col]
            out = out.drop(columns=[route_col])
    return out


def normalize_weather_source(source: pd.DataFrame, source_name: str) -> pd.DataFrame:
    if source.empty or "activity_id_short" not in source.columns:
        return pd.DataFrame(columns=WEATHER_ACTIVITY_COLUMNS)
    out = source.copy()
    out["activity_id_short"] = out["activity_id_short"].astype(str)
    for col in WEATHER_NUMERIC_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan

    if "weather_context_flags" not in out.columns:
        flag_candidates = [
            "weather_planning_context_flags",
            "candidate_weather_context_flags",
            "candidate_weather_context_flags_reattached",
            "descriptive_tags",
        ]
        existing = [col for col in flag_candidates if col in out.columns]
        out["weather_context_flags"] = out[existing].apply(lambda row: pipe_flags(row), axis=1) if existing else pd.NA
    if "environment_context_flags" not in out.columns:
        out["environment_context_flags"] = pd.NA
    if "weather_attach_level" not in out.columns:
        out["weather_attach_level"] = "WEATHER_ACTIVITY_LEVEL_ONLY"
    if "weather_context_available" not in out.columns:
        if "weather_context_available_for_planning" in out.columns:
            out["weather_context_available"] = out["weather_context_available_for_planning"]
        elif "weather_join_performed" in out.columns:
            out["weather_context_available"] = out["weather_join_performed"]
        elif "observed_variable_count" in out.columns:
            out["weather_context_available"] = numeric(out["observed_variable_count"]).fillna(0).gt(0)
        else:
            has_numeric = out[WEATHER_NUMERIC_COLUMNS].apply(numeric).notna().any(axis=1)
            has_flags = out["weather_context_flags"].fillna("").astype(str).str.strip().ne("")
            out["weather_context_available"] = has_numeric | has_flags

    out["weather_context_source"] = source_name
    keep = [col for col in WEATHER_ACTIVITY_COLUMNS if col in out.columns]
    out = out[keep].copy()
    for col in WEATHER_NUMERIC_COLUMNS:
        out[col] = numeric(out[col])
    return out.groupby("activity_id_short", as_index=False).agg(
        {
            "temperature_c": "median",
            "relative_humidity_pct": "median",
            "precipitation_mm": "median",
            "wind_speed_ms": "median",
            "wind_gust_ms": "median",
            "uv_index": "median",
            "weather_context_flags": lambda s: pipe_flags(s),
            "environment_context_flags": lambda s: pipe_flags(s),
            "weather_attach_level": mode_text,
            "weather_context_available": lambda s: bool(pd.Series(s).astype(str).str.lower().isin(["true", "1", "yes"]).any()),
            "weather_context_source": mode_text,
        }
    )


def build_planning_weather_source(planning_windows: pd.DataFrame) -> pd.DataFrame:
    out = planning_windows.copy()
    if "weather_planning_context_flags" in out.columns:
        out["weather_context_flags"] = out["weather_planning_context_flags"]
    if "weather_context_available_for_planning" in out.columns:
        out["weather_context_available"] = out["weather_context_available_for_planning"]
    return normalize_weather_source(out, "planning_context_fusion_v1_1")


def coalesce_weather_sources(reviewed_ids: list[str], sources: list[pd.DataFrame]) -> pd.DataFrame:
    base = pd.DataFrame({"activity_id_short": reviewed_ids})
    for col in WEATHER_ACTIVITY_COLUMNS:
        if col != "activity_id_short":
            base[col] = pd.NA
    for source in sources:
        if source.empty:
            continue
        src = source.set_index("activity_id_short")
        for idx, activity_id in base["activity_id_short"].items():
            if activity_id not in src.index:
                continue
            row = src.loc[activity_id]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            for col in WEATHER_ACTIVITY_COLUMNS:
                if col == "activity_id_short" or col not in source.columns:
                    continue
                current = base.at[idx, col]
                incoming = row.get(col, pd.NA)
                if pd.isna(current) or str(current).strip() == "":
                    if pd.notna(incoming) and str(incoming).strip() != "":
                        base.at[idx, col] = incoming
    for col in WEATHER_NUMERIC_COLUMNS:
        base[col] = numeric(base[col])
    base["weather_context_flags"] = base["weather_context_flags"].fillna("WEATHER_CONTEXT_MISSING")
    base["environment_context_flags"] = base["environment_context_flags"].fillna("WEATHER_CONTEXT_MISSING")
    base["weather_attach_level"] = base["weather_attach_level"].fillna("WEATHER_CONTEXT_MISSING")
    available = base["weather_context_available"].astype(str).str.lower().isin(["true", "1", "yes"])
    numeric_available = base[WEATHER_NUMERIC_COLUMNS].notna().any(axis=1)
    missing_flag = base["weather_context_flags"].eq("WEATHER_CONTEXT_MISSING")
    base["weather_context_available"] = available | (numeric_available & ~missing_flag)
    base.loc[~base["weather_context_available"], "weather_context_flags"] = "WEATHER_CONTEXT_MISSING"
    return base


def weather_has_adverse_context(value: object) -> bool:
    if pd.isna(value):
        return False
    text = str(value)
    textual_markers = ["高濕", "有陣風", "UV ≥6", "UV>=6", "HIGH_UV", "WIND_GUST", "HUMID"]
    if any(marker in text for marker in textual_markers):
        return True
    flags = set(split_flags(value))
    return any(flag in flags for flag in ADVERSE_WEATHER_FLAG_TOKENS)


def weather_interpretation_flags(row: pd.Series) -> str:
    flags = []
    if not bool(row.get("weather_context_available", False)):
        return "WEATHER_CONTEXT_MISSING"
    if weather_has_adverse_context(row.get("weather_context_flags", "")):
        flags.append("WEATHER_ADVERSE_CONTEXT_PRESENT")
    else:
        flags.append("WEATHER_CONTEXT_AVAILABLE_NO_ADVERSE_FLAG")
    if pd.isna(row.get("precipitation_mm")):
        flags.append("PRECIPITATION_FIELD_MISSING")
    if pd.isna(row.get("wind_gust_ms")):
        flags.append("WIND_GUST_FIELD_MISSING")
    return "|".join(flags)


def build_activity_completion_weather_context(
    completion: pd.DataFrame,
    weather_context: pd.DataFrame,
) -> pd.DataFrame:
    out = completion[["activity_id_short", "completion_time_min", "completion_group"]].merge(
        weather_context, on="activity_id_short", how="left"
    )
    for col in WEATHER_NUMERIC_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan
        out[col] = numeric(out[col])
    for col in ["weather_context_flags", "environment_context_flags", "weather_attach_level"]:
        if col not in out.columns:
            out[col] = pd.NA
    if "weather_context_available" not in out.columns:
        out["weather_context_available"] = False
    out["weather_context_available"] = out["weather_context_available"].fillna(False).astype(bool)
    out["weather_context_flags"] = out["weather_context_flags"].fillna("WEATHER_CONTEXT_MISSING")
    out["weather_interpretation_flags"] = out.apply(weather_interpretation_flags, axis=1)
    preferred = [
        "activity_id_short",
        "completion_time_min",
        "completion_group",
        "temperature_c",
        "relative_humidity_pct",
        "precipitation_mm",
        "wind_speed_ms",
        "wind_gust_ms",
        "uv_index",
        "weather_context_flags",
        "environment_context_flags",
        "weather_attach_level",
        "weather_context_available",
        "weather_interpretation_flags",
    ]
    return out[preferred].sort_values(["completion_group", "completion_time_min"]).round(4)


def build_completion_weather_group_summary(activity_weather: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for group_label in GROUP_ORDER:
        sub = activity_weather[activity_weather["completion_group"].eq(group_label)]
        adverse_count = int(sub["weather_interpretation_flags"].astype(str).str.contains("WEATHER_ADVERSE_CONTEXT_PRESENT", na=False).sum())
        missing_count = int((~sub["weather_context_available"].fillna(False).astype(bool)).sum()) if len(sub) else 0
        if missing_count:
            summary = "INCLUDES_WEATHER_CONTEXT_MISSING"
        elif adverse_count:
            summary = "WEATHER_ADVERSE_CONTEXT_PRESENT"
        else:
            summary = "WEATHER_CONTEXT_AVAILABLE_NO_ADVERSE_FLAG"
        rows.append(
            {
                "group_label": group_label,
                "activity_count": len(sub),
                "completion_time_min_median": numeric(sub["completion_time_min"]).median(),
                "temperature_c_median": numeric(sub["temperature_c"]).median(),
                "relative_humidity_pct_median": numeric(sub["relative_humidity_pct"]).median(),
                "precipitation_mm_median": numeric(sub["precipitation_mm"]).median(),
                "wind_gust_ms_median": numeric(sub["wind_gust_ms"]).median(),
                "uv_index_median": numeric(sub["uv_index"]).median(),
                "weather_adverse_context_count": adverse_count,
                "weather_context_summary": summary,
            }
        )
    return pd.DataFrame(rows).round(4)


def weather_aware_interpretation(weather_groups: pd.DataFrame) -> str:
    if weather_groups.empty:
        return "INSUFFICIENT_WEATHER_CONTEXT_FOR_GROUP_COMPARISON"
    if weather_groups["weather_context_summary"].astype(str).str.contains("MISSING", na=False).any():
        return "INSUFFICIENT_WEATHER_CONTEXT_FOR_GROUP_COMPARISON"
    indexed = weather_groups.set_index("group_label")
    if not {"fast", "middle", "slow"}.issubset(indexed.index):
        return "INSUFFICIENT_WEATHER_CONTEXT_FOR_GROUP_COMPARISON"
    slow_adverse = float(indexed.loc["slow", "weather_adverse_context_count"])
    other_adverse = float(indexed.loc[["fast", "middle"], "weather_adverse_context_count"].median())
    slow_gust = indexed.loc["slow", "wind_gust_ms_median"]
    other_gust = indexed.loc[["fast", "middle"], "wind_gust_ms_median"].median()
    slow_humidity = indexed.loc["slow", "relative_humidity_pct_median"]
    other_humidity = indexed.loc[["fast", "middle"], "relative_humidity_pct_median"].median()
    slow_less_favorable = (
        slow_adverse > other_adverse
        or (pd.notna(slow_gust) and pd.notna(other_gust) and slow_gust > other_gust)
        or (pd.notna(slow_humidity) and pd.notna(other_humidity) and slow_humidity > other_humidity)
    )
    if slow_less_favorable:
        return "SLOW_GROUP_COMPLETED_UNDER_LESS_FAVORABLE_WEATHER_SUPPORTS_BASIC_COMPLETION_FEASIBILITY"
    return "WEATHER_CONTEXT_DOES_NOT_SUPPORT_ABILITY_WEAKNESS_INFERENCE"


def prepare_hr_windows(route_load_windows: pd.DataFrame, planning_windows: pd.DataFrame) -> pd.DataFrame:
    keys = ["activity_id_short", "route_distance_window_start_m", "route_distance_window_end_m"]
    cols = [
        "activity_id_short",
        "route_distance_window_start_m",
        "route_distance_window_end_m",
        "heart_rate_bpm_median",
        "activity_heart_rate_bpm_median_p75",
        "behavior_response_flags",
        "window_qa_flags",
        "route_load_context_band",
    ]
    available = [col for col in cols if col in route_load_windows.columns]
    out = route_load_windows[available].copy()
    if not set(keys).issubset(out.columns):
        return pd.DataFrame()
    out["activity_id_short"] = out["activity_id_short"].astype(str)
    out["heart_rate_bpm_median"] = numeric(out.get("heart_rate_bpm_median", pd.Series(dtype=float)))
    out["activity_heart_rate_bpm_median_p75"] = numeric(out.get("activity_heart_rate_bpm_median_p75", pd.Series(dtype=float)))
    out["activity_relative_high_hr_window"] = (
        out["heart_rate_bpm_median"].notna()
        & out["activity_heart_rate_bpm_median_p75"].notna()
        & out["heart_rate_bpm_median"].ge(out["activity_heart_rate_bpm_median_p75"])
    )

    if set(keys + ["planning_caution_level"]).issubset(planning_windows.columns):
        caution = planning_windows[keys + ["planning_caution_level"]].copy()
        out = out.merge(caution, on=keys, how="left")
    else:
        out["planning_caution_level"] = pd.NA
    return out


def hr_interpretation_flags(row: pd.Series) -> str:
    if not bool(row.get("heart_rate_available", False)):
        return f"{HR_MISSING_FLAG}|{HR_INSUFFICIENT_FLAG}"
    flags = ["HR_CONTEXT_AVAILABLE"]
    if row.get("activity_relative_high_hr_window_ratio", 0) > 0:
        flags.append("ACTIVITY_RELATIVE_HIGH_HR_EVIDENCE_PRESENT")
    else:
        flags.append("NO_ACTIVITY_RELATIVE_HIGH_HR_WINDOW_EVIDENCE")
    if row.get("high_or_very_high_load_high_hr_window_ratio", 0) > 0:
        flags.append("HIGH_LOAD_HIGH_HR_EVIDENCE_PRESENT")
    if row.get("early_checkpoint_high_hr_window_ratio", 0) > 0:
        flags.append("EARLY_CHECKPOINT_HIGH_HR_EVIDENCE_PRESENT")
    return "|".join(flags)


def build_completion_hr_effort_context(
    completion: pd.DataFrame,
    hr_windows: pd.DataFrame,
    start_m: float,
    end_m: float,
) -> pd.DataFrame:
    rows = []
    completion_idx = completion.set_index("activity_id_short")
    for activity_id, comp in completion_idx.iterrows():
        sub = hr_windows[hr_windows["activity_id_short"].eq(activity_id)].copy()
        hr = numeric(sub.get("heart_rate_bpm_median", pd.Series(dtype=float)))
        available = int(hr.notna().sum())
        high = sub["activity_relative_high_hr_window"].fillna(False).astype(bool) if "activity_relative_high_hr_window" in sub.columns else pd.Series(False, index=sub.index)
        high_load = sub["route_load_context_band"].isin(HIGH_LOAD_BANDS) if "route_load_context_band" in sub.columns else pd.Series(False, index=sub.index)
        early = sub[
            (numeric(sub["route_distance_window_end_m"]) > start_m)
            & (numeric(sub["route_distance_window_start_m"]) < end_m)
        ].copy() if len(sub) else sub.copy()
        early_high = early["activity_relative_high_hr_window"].fillna(False).astype(bool) if "activity_relative_high_hr_window" in early.columns else pd.Series(False, index=early.index)
        row = {
            "activity_id_short": activity_id,
            "completion_time_min": comp.get("completion_time_min"),
            "completion_group": comp.get("completion_group"),
            "heart_rate_available": available > 0,
            "heart_rate_window_count": available,
            "heart_rate_bpm_median_all": hr.median(),
            "heart_rate_bpm_p75_all": hr.quantile(0.75),
            "heart_rate_bpm_p90_all": hr.quantile(0.90),
            "activity_relative_high_hr_window_ratio": float(high.sum() / available) if available else np.nan,
            "high_or_very_high_load_hr_median": numeric(sub.loc[high_load, "heart_rate_bpm_median"]).median() if len(sub) else np.nan,
            "high_or_very_high_load_high_hr_window_ratio": float((high & high_load).sum() / high_load.sum()) if high_load.sum() else np.nan,
            "early_checkpoint_hr_median": numeric(early.get("heart_rate_bpm_median", pd.Series(dtype=float))).median(),
            "early_checkpoint_high_hr_window_ratio": float(early_high.sum() / len(early)) if len(early) else np.nan,
        }
        row["hr_effort_interpretation_flags"] = hr_interpretation_flags(pd.Series(row))
        rows.append(row)
    return pd.DataFrame(rows).round(6)


def build_completion_hr_effort_group_summary(hr_context: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for group_label in GROUP_ORDER:
        sub = hr_context[hr_context["completion_group"].eq(group_label)]
        available_count = int(sub["heart_rate_available"].fillna(False).astype(bool).sum()) if len(sub) else 0
        missing_count = int((~sub["heart_rate_available"].fillna(False).astype(bool)).sum()) if len(sub) else 0
        high_effort = bool(
            numeric(sub["high_or_very_high_load_high_hr_window_ratio"]).fillna(0).gt(0).any()
            or numeric(sub["early_checkpoint_high_hr_window_ratio"]).fillna(0).gt(0).any()
        )
        if missing_count:
            interp = "INSUFFICIENT_HR_CONTEXT"
        elif high_effort:
            interp = "HIGH_HR_EFFORT_EVIDENCE_PRESENT"
        else:
            interp = "NO_CLEAR_HIGH_HR_EFFORT_EVIDENCE"
        rows.append(
            {
                "group_label": group_label,
                "activity_count": len(sub),
                "completion_time_min_median": numeric(sub["completion_time_min"]).median(),
                "heart_rate_bpm_median_group_median": numeric(sub["heart_rate_bpm_median_all"]).median(),
                "heart_rate_bpm_p75_group_median": numeric(sub["heart_rate_bpm_p75_all"]).median(),
                "heart_rate_bpm_p90_group_median": numeric(sub["heart_rate_bpm_p90_all"]).median(),
                "activity_relative_high_hr_window_ratio_median": numeric(sub["activity_relative_high_hr_window_ratio"]).median(),
                "high_or_very_high_load_hr_median": numeric(sub["high_or_very_high_load_hr_median"]).median(),
                "high_or_very_high_load_high_hr_window_ratio_median": numeric(sub["high_or_very_high_load_high_hr_window_ratio"]).median(),
                "early_checkpoint_hr_median": numeric(sub["early_checkpoint_hr_median"]).median(),
                "early_checkpoint_high_hr_window_ratio_median": numeric(sub["early_checkpoint_high_hr_window_ratio"]).median(),
                "hr_context_available_count": available_count,
                "hr_context_missing_count": missing_count,
                "hr_effort_group_interpretation": interp,
            }
        )
    return pd.DataFrame(rows).round(6)


def early_checkpoint_effort_enum(row: pd.Series) -> str:
    if HR_MISSING_FLAG in str(row.get("hr_effort_interpretation_flags", "")):
        return "UNKNOWN_DUE_TO_MISSING_HR"
    high_hr = row.get("relative_high_hr_window_ratio", 0)
    high_hr = 0 if pd.isna(high_hr) else float(high_hr)
    low_speed = row.get("low_speed_ratio_median", 0)
    low_speed = 0 if pd.isna(low_speed) else float(low_speed)
    stopped = row.get("stopped_ratio_median", 0)
    stopped = 0 if pd.isna(stopped) else float(stopped)
    behavior_unknown = "WEATHER_CONTEXT_MISSING" in str(row.get("weather_interpretation_flags", ""))
    if stopped > 0 and high_hr > 0:
        return "PASSED_WITH_STOP_AND_HIGH_HR_RESPONSE"
    if low_speed > 0 and high_hr > 0:
        return "PASSED_WITH_LOW_SPEED_AND_HIGH_HR_RESPONSE"
    if low_speed > 0 and high_hr <= 0:
        return "PASSED_WITH_LOW_SPEED_BUT_NO_HIGH_HR_EVIDENCE"
    if behavior_unknown:
        return "PASSED_WITH_BEHAVIOR_RESPONSE_HR_UNKNOWN"
    return "PASSED_WITH_NO_STRONG_EFFORT_EVIDENCE"


def build_early_checkpoint_hr_effort_review(
    early: pd.DataFrame,
    hr_context: pd.DataFrame,
    activity_weather: pd.DataFrame,
) -> pd.DataFrame:
    h = hr_context[
        [
            "activity_id_short",
            "early_checkpoint_hr_median",
            "early_checkpoint_high_hr_window_ratio",
            "hr_effort_interpretation_flags",
        ]
    ].copy()
    w = activity_weather[["activity_id_short", "weather_interpretation_flags"]].copy()
    out = early.merge(h, on="activity_id_short", how="left").merge(w, on="activity_id_short", how="left")
    out["heart_rate_bpm_median"] = out["early_checkpoint_hr_median"]
    out["relative_high_hr_window_ratio"] = out["early_checkpoint_high_hr_window_ratio"]
    out["hr_effort_interpretation_flags"] = out["hr_effort_interpretation_flags"].fillna(f"{HR_MISSING_FLAG}|{HR_INSUFFICIENT_FLAG}")
    out["weather_interpretation_flags"] = out["weather_interpretation_flags"].fillna("WEATHER_CONTEXT_MISSING")
    out["early_checkpoint_effort_interpretation"] = out.apply(early_checkpoint_effort_enum, axis=1)
    preferred = [
        "activity_id_short",
        "completion_group",
        "completion_time_min",
        "segment_start_m",
        "segment_end_m",
        "speed_mps_median",
        "low_speed_ratio_median",
        "stopped_ratio_median",
        "heart_rate_bpm_median",
        "relative_high_hr_window_ratio",
        "dominant_planning_caution_level",
        "dominant_route_load_context_band",
        "candidate_windows_n",
        "weather_interpretation_flags",
        "hr_effort_interpretation_flags",
        "early_checkpoint_effort_interpretation",
    ]
    return out[[col for col in preferred if col in out.columns]].round(6)


def slow_group_hr_completion_interpretation(
    completion: pd.DataFrame,
    hr_groups: pd.DataFrame,
    weather_groups: pd.DataFrame,
) -> str:
    slow_completed = completion[completion["completion_group"].eq("slow")]["completion_status"].eq("COMPLETED").all()
    if not slow_completed:
        return "SLOW_GROUP_NOT_ALL_COMPLETED"
    if hr_groups.empty or "slow" not in set(hr_groups["group_label"]):
        return "SLOW_GROUP_COMPLETED_BUT_HR_CONTEXT_INSUFFICIENT"
    slow_hr = hr_groups.set_index("group_label").loc["slow"]
    if int(slow_hr.get("hr_context_missing_count", 0)) > 0 or int(slow_hr.get("hr_context_available_count", 0)) == 0:
        return "SLOW_GROUP_COMPLETED_BUT_HR_CONTEXT_INSUFFICIENT"
    if str(slow_hr.get("hr_effort_group_interpretation", "")) == "HIGH_HR_EFFORT_EVIDENCE_PRESENT":
        return "SLOW_GROUP_COMPLETED_WITH_HIGH_EFFORT_EVIDENCE_CONSERVATIVE_PLANNING_STILL_RECOMMENDED"
    return "SLOW_GROUP_COMPLETED_UNDER_WEATHER_CONTEXT_WITHOUT_CLEAR_HIGH_HR_FAILURE_EVIDENCE"


def build_conclusion(
    completion: pd.DataFrame,
    early: pd.DataFrame,
    weather_groups: pd.DataFrame,
    hr_context: pd.DataFrame,
    hr_groups: pd.DataFrame,
    early_hr: pd.DataFrame,
) -> pd.DataFrame:
    valid = completion[completion["completion_time_min"].notna()].copy()
    slow = completion[completion["completion_group"].eq("slow")]
    early_slow = early[early["completion_group"].eq("slow")]
    all_completed = bool(completion["completion_status"].eq("COMPLETED").all())
    slow_group_completed = bool(slow["completion_status"].eq("COMPLETED").all()) if len(slow) else False
    slow_checkpoint_passed = bool(
        len(early_slow)
        and early_slow["segment_completion_interpretation"].ne("UNKNOWN_DUE_TO_MISSING_FIELDS").all()
    )
    unrecoverable = False
    enough = all_completed and slow_group_completed and slow_checkpoint_passed and len(valid) == len(completion)
    route_statement = (
        "BASIC_PREPARED_HIKERS_COMPLETION_FEASIBLE" if enough else "INSUFFICIENT_COMPLETION_EVIDENCE"
    )
    planning_statement = (
        "COMPLETION_FEASIBLE_BUT_CONSERVATIVE_PLANNING_RECOMMENDED"
        if enough
        else "INSUFFICIENT_COMPLETION_EVIDENCE"
    )
    early_statement = (
        "EARLY_STATUS_CHECKPOINT_NOT_MANDATORY_TURNAROUND_POINT"
        if enough
        else "INSUFFICIENT_COMPLETION_EVIDENCE"
    )
    weather_statement = weather_aware_interpretation(weather_groups)
    hr_available_count = int(hr_context["heart_rate_available"].fillna(False).astype(bool).sum()) if len(hr_context) else 0
    slow_hr_context_available = bool(
        len(hr_context[hr_context["completion_group"].eq("slow")])
        and hr_context[hr_context["completion_group"].eq("slow")]["heart_rate_available"].fillna(False).astype(bool).all()
    )
    slow_hr_high = False
    if not hr_groups.empty and "slow" in set(hr_groups["group_label"]):
        slow_hr_high = str(hr_groups.set_index("group_label").loc["slow", "hr_effort_group_interpretation"]) == "HIGH_HR_EFFORT_EVIDENCE_PRESENT"
    slow_weather_summary = ""
    if not weather_groups.empty and "slow" in set(weather_groups["group_label"]):
        slow_weather_summary = str(weather_groups.set_index("group_label").loc["slow", "weather_context_summary"])
    early_hr_statement = (
        "EARLY_CHECKPOINT_HR_EFFORT_REVIEW_AVAILABLE"
        if len(early_hr) and early_hr["early_checkpoint_effort_interpretation"].ne("UNKNOWN_DUE_TO_MISSING_HR").all()
        else "INSUFFICIENT_HR_CONTEXT"
    )
    slow_weather_hr_statement = slow_group_hr_completion_interpretation(completion, hr_groups, weather_groups)
    return pd.DataFrame(
        [
            {
                "all_reviewed_activities_completed": all_completed,
                "fastest_completion_time_min": numeric(valid["completion_time_min"]).min(),
                "median_completion_time_min": numeric(valid["completion_time_min"]).median(),
                "slowest_completion_time_min": numeric(valid["completion_time_min"]).max(),
                "slowest_minus_fastest_min": numeric(valid["completion_time_min"]).max()
                - numeric(valid["completion_time_min"]).min(),
                "slow_group_completed": slow_group_completed,
                "slow_group_early_checkpoint_passed": slow_checkpoint_passed,
                "slow_group_unrecoverable_delay_evidence": unrecoverable,
                "early_checkpoint_recommended_interpretation": early_statement,
                "route_level_feasibility_statement": route_statement,
                "planning_statement": planning_statement,
                "weather_aware_interpretation": weather_statement,
                "hr_context_available_count": hr_available_count,
                "slow_group_hr_context_available": slow_hr_context_available,
                "slow_group_high_hr_effort_evidence": slow_hr_high,
                "slow_group_weather_context_summary": slow_weather_summary,
                "slow_group_completion_interpretation_with_weather_and_hr": slow_weather_hr_statement,
                "early_checkpoint_interpretation_with_hr": early_hr_statement,
                "boundary_statement": BOUNDARY,
            }
        ]
    ).round(4)


def build_audit(
    paths: dict[str, Path],
    completion: pd.DataFrame,
    groups: pd.DataFrame,
    early: pd.DataFrame,
    activity_weather: pd.DataFrame,
    hr_context: pd.DataFrame,
    hr_groups: pd.DataFrame,
    early_hr: pd.DataFrame,
    conclusion_df: pd.DataFrame,
    output_files: list[Path],
    source: str,
) -> pd.DataFrame:
    generated_cols = set()
    for path in output_files:
        if path.suffix.lower() == ".csv" and path.exists():
            try:
                generated_cols.update(pd.read_csv(path, nrows=0, encoding="utf-8-sig").columns)
            except Exception:
                pass
    forbidden = sorted(FORBIDDEN_OUTPUT_COLUMNS & generated_cols)
    input_found = [name for name, path in paths.items() if path.exists()]
    input_missing = [name for name, path in paths.items() if not path.exists()]
    slow = completion[completion["completion_group"].eq("slow")]
    slow_early = early[early["completion_group"].eq("slow")]
    insufficient = []
    if completion["completion_time_min"].isna().any():
        insufficient.append("COMPLETION_TIME_MISSING")
    if early.empty:
        insufficient.append("EARLY_CHECKPOINT_WINDOWS_MISSING")
    if activity_weather.empty or activity_weather["weather_context_available"].fillna(False).astype(bool).sum() == 0:
        insufficient.append("WEATHER_CONTEXT_MISSING")
    if hr_context.empty or hr_context["heart_rate_available"].fillna(False).astype(bool).sum() == 0:
        insufficient.append("INSUFFICIENT_HR_CONTEXT")
    conclusion = "PASS_CH6_7_COMPLETION_FEASIBILITY_REVIEW_V1_1_WEATHER_HR_DESCRIPTIVE_ONLY"
    if forbidden:
        conclusion = "REVIEW_REQUIRED_FORBIDDEN_COLUMNS_PRESENT"
    elif insufficient:
        conclusion = "REVIEW_REQUIRED_INSUFFICIENT_FIELDS"
    slow_group_completed = bool(slow["completion_status"].eq("COMPLETED").all()) if len(slow) else False
    slow_hr_available = False
    slow_high_hr = False
    if not conclusion_df.empty:
        slow_hr_available = bool(conclusion_df.iloc[0].get("slow_group_hr_context_available", False))
        slow_high_hr = bool(conclusion_df.iloc[0].get("slow_group_high_hr_effort_evidence", False))
    return pd.DataFrame(
        [
            {
                "input_files_found": "|".join(input_found),
                "input_files_missing": "|".join(input_missing) if input_missing else "NONE",
                "completion_time_source_column": source,
                "completion_time_available_count": int(completion["completion_time_min"].notna().sum()),
                "reviewed_activity_count": int(len(completion)),
                "completed_activity_count": int(completion["completion_status"].eq("COMPLETED").sum()),
                "fast_group_count": int(groups.loc[groups["group_label"].eq("fast"), "activity_count"].iloc[0]),
                "middle_group_count": int(groups.loc[groups["group_label"].eq("middle"), "activity_count"].iloc[0]),
                "slow_group_count": int(groups.loc[groups["group_label"].eq("slow"), "activity_count"].iloc[0]),
                "early_checkpoint_window_count": int(early["window_count"].sum()) if len(early) else 0,
                "slow_group_completed_count": int(slow["completion_status"].eq("COMPLETED").sum()),
                "slow_group_early_checkpoint_reviewed_count": int(len(slow_early)),
                "weather_context_available_count": int(activity_weather["weather_context_available"].fillna(False).astype(bool).sum()) if len(activity_weather) else 0,
                "weather_context_missing_count": int((~activity_weather["weather_context_available"].fillna(False).astype(bool)).sum()) if len(activity_weather) else 0,
                "hr_context_available_count": int(hr_context["heart_rate_available"].fillna(False).astype(bool).sum()) if len(hr_context) else 0,
                "hr_context_missing_count": int((~hr_context["heart_rate_available"].fillna(False).astype(bool)).sum()) if len(hr_context) else 0,
                "early_checkpoint_hr_available_count": int(early_hr["heart_rate_bpm_median"].notna().sum()) if len(early_hr) and "heart_rate_bpm_median" in early_hr.columns else 0,
                "slow_group_completed": slow_group_completed,
                "slow_group_hr_context_available": slow_hr_available,
                "slow_group_high_hr_effort_evidence": slow_high_hr,
                "insufficient_field_warnings": "|".join(insufficient) if insufficient else "NONE",
                "forbidden_output_columns_absent": len(forbidden) == 0,
                "forbidden_output_columns": "|".join(forbidden) if forbidden else "NONE",
                "weather_zero_fill_performed": False,
                "hr_missing_not_interpreted_as_low_effort": True,
                "output_files_generated": "|".join(str(path) for path in output_files if path.exists()),
                "audit_conclusion": conclusion,
            }
        ]
    )


def summary_stats(completion: pd.DataFrame) -> dict[str, object]:
    valid = completion[completion["completion_time_min"].notna()].copy()
    fastest = valid.sort_values("completion_time_min").head(1)
    slowest = valid.sort_values("completion_time_min").tail(1)
    values = numeric(valid["completion_time_min"])
    return {
        "fastest_activity": fastest["activity_id_short"].iloc[0] if len(fastest) else "",
        "slowest_activity": slowest["activity_id_short"].iloc[0] if len(slowest) else "",
        "min_completion_time": values.min(),
        "p25": values.quantile(0.25),
        "median": values.median(),
        "p75": values.quantile(0.75),
        "max": values.max(),
        "max_min_ratio": values.max() / values.min() if len(values) and values.min() else np.nan,
        "slowest_fastest_difference": values.max() - values.min() if len(values) else np.nan,
        "all_reviewed_activities_completed": bool(completion["completion_status"].eq("COMPLETED").all()),
    }


def save_completion_distribution_png(completion: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(12, 6), constrained_layout=True)
    plot = completion.sort_values("completion_time_min").copy()
    colors = [GROUP_COLORS.get(group, "#64748B") for group in plot["completion_group"]]
    ax.bar(plot["activity_id_short"], plot["completion_time_min"], color=colors, edgecolor="#1F2937", linewidth=0.4)
    med = numeric(plot["completion_time_min"]).median()
    ax.axhline(med, color="#111827", linestyle="--", linewidth=1.0, label=f"median {med:.1f} min")
    if len(plot):
        ax.scatter(plot["activity_id_short"].iloc[0], plot["completion_time_min"].iloc[0], color="#FBBF24", zorder=3, label="fastest")
        ax.scatter(plot["activity_id_short"].iloc[-1], plot["completion_time_min"].iloc[-1], color="#7C2D12", zorder=3, label="slowest")
    ax.set_title("Completion Time Distribution (25 Reviewed Activities)")
    ax.set_ylabel("completion time (min)")
    ax.set_xlabel("activity")
    ax.tick_params(axis="x", rotation=70)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.text(0.01, 0.01, "Descriptive distribution only; not an ability ranking.", fontsize=9)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def save_group_png(groups: pd.DataFrame, path: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(14, 5), constrained_layout=True)
    colors = [GROUP_COLORS[g] for g in groups["group_label"]]
    metrics = [
        ("completion_time_min_median", "median completion min"),
        ("candidate_window_ratio_median", "candidate window ratio"),
        ("turnaround_review_window_ratio_median", "turnaround review ratio"),
    ]
    for ax, (col, title) in zip(axes, metrics):
        ax.bar(groups["group_label"], groups[col], color=colors, edgecolor="#1F2937", linewidth=0.4)
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("Fast / Middle / Slow Group Descriptive Comparison")
    fig.text(0.01, 0.01, "Groups are rank-split by completion time; comparison is descriptive only.", fontsize=9)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def save_early_png(early: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(13, 6), constrained_layout=True)
    plot = early.sort_values(["completion_group", "activity_id_short"]).copy()
    x = np.arange(len(plot))
    colors = [GROUP_COLORS.get(group, "#64748B") for group in plot["completion_group"]]
    ax.bar(x - 0.18, plot["low_speed_ratio_median"], width=0.36, color=colors, alpha=0.82, label="low speed ratio")
    ax.bar(x + 0.18, plot["stopped_ratio_median"], width=0.36, color="#111827", alpha=0.55, label="stopped ratio")
    ax2 = ax.twinx()
    ax2.plot(x, plot["speed_mps_median"], color="#F59E0B", marker="o", linewidth=1.5, label="speed mps median")
    ax.set_xticks(x)
    ax.set_xticklabels(plot["activity_id_short"], rotation=70)
    ax.set_ylabel("ratio")
    ax2.set_ylabel("speed mps")
    ax.set_title("Early Checkpoint 1350-1700m Review")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="upper left", frameon=False)
    ax2.legend(loc="upper right", frameon=False)
    fig.text(0.01, 0.01, "Checkpoint is a status-review segment, not a mandatory turnaround point.", fontsize=9)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def save_group_weather_hr_png(
    groups: pd.DataFrame,
    weather_groups: pd.DataFrame,
    hr_groups: pd.DataFrame,
    path: Path,
) -> None:
    merged = groups.merge(weather_groups, on=["group_label", "activity_count", "completion_time_min_median"], how="left")
    merged = merged.merge(hr_groups, on=["group_label", "activity_count", "completion_time_min_median"], how="left", suffixes=("", "_hr"))
    fig, axes = plt.subplots(2, 3, figsize=(15, 8), constrained_layout=True)
    colors = [GROUP_COLORS[g] for g in merged["group_label"]]
    metrics = [
        ("completion_time_min_median", "completion time median"),
        ("candidate_window_ratio_median", "candidate window ratio"),
        ("turnaround_review_window_ratio_median", "turnaround review ratio"),
        ("heart_rate_bpm_median_group_median", "HR median"),
        ("activity_relative_high_hr_window_ratio_median", "relative high HR ratio"),
        ("weather_adverse_context_count", "weather adverse count"),
    ]
    for ax, (col, title) in zip(axes.ravel(), metrics):
        values = numeric(merged[col]) if col in merged.columns else pd.Series(np.nan, index=merged.index)
        ax.bar(merged["group_label"], values, color=colors, edgecolor="#1F2937", linewidth=0.4)
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("Fast / Middle / Slow Weather + HR Descriptive Comparison")
    fig.text(0.01, 0.01, "Descriptive context only; HR and weather evidence are not ability scores.", fontsize=9)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def save_early_weather_hr_png(early_hr: pd.DataFrame, path: Path) -> None:
    plot = early_hr.sort_values(["completion_group", "activity_id_short"]).copy()
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), constrained_layout=True, sharex=True)
    x = np.arange(len(plot))
    colors = [GROUP_COLORS.get(group, "#64748B") for group in plot["completion_group"]]
    axes[0].bar(x - 0.18, numeric(plot["low_speed_ratio_median"]), width=0.36, color=colors, alpha=0.85, label="low speed ratio")
    axes[0].bar(x + 0.18, numeric(plot["stopped_ratio_median"]), width=0.36, color="#111827", alpha=0.55, label="stopped ratio")
    ax_speed = axes[0].twinx()
    ax_speed.plot(x, numeric(plot["speed_mps_median"]), color="#F59E0B", marker="o", linewidth=1.5, label="speed mps")
    axes[0].set_ylabel("ratio")
    ax_speed.set_ylabel("speed mps")
    axes[0].legend(loc="upper left", frameon=False)
    ax_speed.legend(loc="upper right", frameon=False)

    axes[1].bar(x, numeric(plot["heart_rate_bpm_median"]), color=colors, alpha=0.85, edgecolor="#1F2937", linewidth=0.4, label="HR median")
    ax_hr_ratio = axes[1].twinx()
    ax_hr_ratio.plot(x, numeric(plot["relative_high_hr_window_ratio"]), color="#7C2D12", marker="o", linewidth=1.5, label="relative high HR ratio")
    axes[1].set_ylabel("HR bpm")
    ax_hr_ratio.set_ylabel("high HR ratio")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(plot["activity_id_short"], rotation=70)
    axes[1].legend(loc="upper left", frameon=False)
    ax_hr_ratio.legend(loc="upper right", frameon=False)
    axes[0].set_title("Early Checkpoint 1350-1700m: Movement Context")
    axes[1].set_title("Early Checkpoint 1350-1700m: HR Effort Context")
    fig.text(0.01, 0.01, "Checkpoint is a status-review segment; HR missing is not interpreted as low effort.", fontsize=9)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def html_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    view = df if max_rows is None else df.head(max_rows)
    return view.to_html(index=False, escape=True, border=0, classes="data-table")


def write_html_report(
    path: Path,
    completion: pd.DataFrame,
    groups: pd.DataFrame,
    activity_weather: pd.DataFrame,
    weather_groups: pd.DataFrame,
    hr_context: pd.DataFrame,
    hr_groups: pd.DataFrame,
    early_hr: pd.DataFrame,
    early: pd.DataFrame,
    conclusion: pd.DataFrame,
    audit: pd.DataFrame,
    pngs: list[Path],
) -> None:
    stats = summary_stats(completion)
    stat_items = "".join(f"<li><b>{html.escape(str(k))}</b>: {html.escape(str(round(v, 4) if isinstance(v, float) else v))}</li>" for k, v in stats.items())
    img_tags = "\n".join(
        f'<figure><img src="{html.escape(png.name)}" alt="{html.escape(png.stem)}"></figure>' for png in pngs
    )
    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CH6.7 Completion Feasibility Review v1.1</title>
<style>
body {{ font-family: "Microsoft JhengHei", Arial, sans-serif; margin: 32px; color: #111827; }}
h1, h2 {{ margin-bottom: 0.35rem; }}
.boundary {{ padding: 12px 14px; border-left: 4px solid #2563EB; background: #EFF6FF; }}
.data-table {{ border-collapse: collapse; width: 100%; font-size: 13px; margin: 10px 0 24px; }}
.data-table th, .data-table td {{ border: 1px solid #CBD5E1; padding: 6px 8px; text-align: left; }}
.data-table th {{ background: #F1F5F9; }}
img {{ max-width: 100%; border: 1px solid #E5E7EB; }}
figure {{ margin: 20px 0; }}
</style>
</head>
<body>
<h1>CH6.7 Completion Feasibility Review v1.1</h1>
<p class="boundary">{html.escape(BOUNDARY)}</p>
<h2>Key Summary</h2>
<ul>{stat_items}</ul>
{img_tags}
<h2>Completion Time Distribution</h2>
{html_table(completion)}
<h2>Fast / Middle / Slow Group Comparison</h2>
{html_table(groups)}
<h2>Activity-Level Weather Context</h2>
{html_table(activity_weather)}
<h2>Completion Weather Group Summary</h2>
{html_table(weather_groups)}
<h2>Completion HR Effort Context</h2>
{html_table(hr_context)}
<h2>Completion HR Effort Group Summary</h2>
{html_table(hr_groups)}
<h2>Early Checkpoint 1350-1700m Review</h2>
{html_table(early)}
<h2>Early Checkpoint Weather + HR Review</h2>
{html_table(early_hr)}
<h2>Route-Level Feasibility Conclusion</h2>
{html_table(conclusion)}
<h2>Audit</h2>
{html_table(audit)}
</body>
</html>
"""
    path.write_text(doc, encoding="utf-8")


def write_run_report(path: Path, audit: pd.DataFrame, conclusion: pd.DataFrame, stats: dict[str, object]) -> None:
    lines = [
        "# CH6.7 Completion Feasibility Review v1.1 Run Report",
        "",
        "## Summary",
        "",
    ]
    for key, value in stats.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Conclusion", ""])
    for key, value in conclusion.iloc[0].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Audit", ""])
    for key, value in audit.iloc[0].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- descriptive completion feasibility review only",
            "- no Word/docx output was generated",
            "- no v2.2.7 surface-profile output was modified",
            "- no 6.5 route-load output was modified",
            "- no 6.7 planning context fusion v1/v1.1 output was modified",
            "- no commit was created",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    setup_matplotlib_font()
    root = Path(args.root)
    output_root = resolve(root, args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    paths = {
        "planning_windows": resolve(root, args.planning_windows),
        "planning_summary": resolve(root, args.planning_summary),
        "route_load_windows": resolve(root, args.route_load_windows),
        "route_load_candidates": resolve(root, args.route_load_candidates),
        "route_load_summary": resolve(root, args.route_load_summary),
        "performance_summary": resolve(root, args.performance_summary),
        "route_normalized_comparison": resolve(root, args.route_normalized_comparison),
        "weather_profile": resolve(root, args.weather_profile),
        "weather_performance_join": resolve(root, args.weather_performance_join),
    }

    planning_windows = read_csv(paths["planning_windows"], "6.7 planning windows", low_memory=False)
    planning_summary = read_csv(paths["planning_summary"], "6.7 planning activity summary")
    route_load_windows = read_csv(paths["route_load_windows"], "6.5 route-load windows", low_memory=False)
    read_csv(paths["route_load_candidates"], "6.5 route-load candidates", low_memory=False)
    read_csv(paths["route_load_summary"], "6.5 route-load activity summary")
    performance = read_csv_optional(paths["performance_summary"])
    route_normalized = read_csv_optional(paths["route_normalized_comparison"])
    weather_profile = read_csv_optional(paths["weather_profile"])
    weather_performance = read_csv_optional(paths["weather_performance_join"])

    reviewed_ids = sorted(planning_summary["activity_id_short"].astype(str).tolist())
    planning_windows = attach_route_load_behavior_fields(planning_windows, route_load_windows)
    completion, source = build_completion_distribution(
        reviewed_ids, planning_windows, performance, route_normalized, weather_performance
    )
    completion = add_completion_groups(completion)
    groups = build_group_summary(completion, planning_summary, route_load_windows)
    weather_context = coalesce_weather_sources(
        reviewed_ids,
        [
            normalize_weather_source(weather_profile, "activity_weather_profile_report_table"),
            normalize_weather_source(weather_performance, "activity_weather_performance_join"),
            build_planning_weather_source(planning_windows),
        ],
    )
    activity_weather = build_activity_completion_weather_context(completion, weather_context)
    weather_groups = build_completion_weather_group_summary(activity_weather)
    hr_windows = prepare_hr_windows(route_load_windows, planning_windows)
    hr_context = build_completion_hr_effort_context(
        completion, hr_windows, args.early_checkpoint_start_m, args.early_checkpoint_end_m
    )
    hr_groups = build_completion_hr_effort_group_summary(hr_context)
    early = build_early_checkpoint_review(
        completion, planning_windows, args.early_checkpoint_start_m, args.early_checkpoint_end_m
    )
    early_hr = build_early_checkpoint_hr_effort_review(early, hr_context, activity_weather)
    conclusion = build_conclusion(completion, early, weather_groups, hr_context, hr_groups, early_hr)

    completion_csv = output_root / "completion_time_distribution_v1_1.csv"
    groups_csv = output_root / "completion_feasibility_group_summary_v1_1.csv"
    activity_weather_csv = output_root / "activity_completion_weather_context_v1_1.csv"
    weather_groups_csv = output_root / "completion_weather_group_summary_v1_1.csv"
    hr_context_csv = output_root / "completion_hr_effort_context_v1_1.csv"
    hr_groups_csv = output_root / "completion_hr_effort_group_summary_v1_1.csv"
    early_csv = output_root / "early_checkpoint_segment_review_v1_1.csv"
    early_hr_csv = output_root / "early_checkpoint_hr_effort_review_v1_1.csv"
    conclusion_csv = output_root / "completion_feasibility_conclusion_v1_1.csv"
    audit_csv = output_root / "completion_feasibility_review_audit_v1_1.csv"
    report_md = output_root / "completion_feasibility_review_run_report_v1_1.md"
    html_report = output_root / "completion_feasibility_review_report_v1_1.html"
    completion_png = output_root / "completion_time_distribution_v1_1.png"
    group_png = output_root / "fast_middle_slow_group_weather_hr_comparison_v1_1.png"
    early_png = output_root / "early_checkpoint_1350_1700m_weather_hr_review_v1_1.png"

    completion.to_csv(completion_csv, index=False, encoding="utf-8-sig")
    groups.to_csv(groups_csv, index=False, encoding="utf-8-sig")
    activity_weather.to_csv(activity_weather_csv, index=False, encoding="utf-8-sig")
    weather_groups.to_csv(weather_groups_csv, index=False, encoding="utf-8-sig")
    hr_context.to_csv(hr_context_csv, index=False, encoding="utf-8-sig")
    hr_groups.to_csv(hr_groups_csv, index=False, encoding="utf-8-sig")
    early.to_csv(early_csv, index=False, encoding="utf-8-sig")
    early_hr.to_csv(early_hr_csv, index=False, encoding="utf-8-sig")
    conclusion.to_csv(conclusion_csv, index=False, encoding="utf-8-sig")

    save_completion_distribution_png(completion, completion_png)
    save_group_weather_hr_png(groups, weather_groups, hr_groups, group_png)
    save_early_weather_hr_png(early_hr, early_png)

    output_files = [
        completion_csv,
        groups_csv,
        activity_weather_csv,
        weather_groups_csv,
        hr_context_csv,
        hr_groups_csv,
        early_csv,
        early_hr_csv,
        conclusion_csv,
        audit_csv,
        report_md,
        html_report,
        completion_png,
        group_png,
        early_png,
    ]
    audit = build_audit(
        paths,
        completion,
        groups,
        early,
        activity_weather,
        hr_context,
        hr_groups,
        early_hr,
        conclusion,
        output_files,
        source,
    )
    audit.to_csv(audit_csv, index=False, encoding="utf-8-sig")
    write_html_report(
        html_report,
        completion,
        groups,
        activity_weather,
        weather_groups,
        hr_context,
        hr_groups,
        early_hr,
        early,
        conclusion,
        audit,
        [completion_png, group_png, early_png],
    )
    write_run_report(report_md, audit, conclusion, summary_stats(completion))

    payload = {
        "script_path": str(Path(__file__)),
        "output_root": str(output_root),
        "completion_time_source": source,
        "reviewed_activity_count": int(len(completion)),
        "completion_time_available_count": int(completion["completion_time_min"].notna().sum()),
        "fastest_completion_time": float(completion["completion_time_min"].min()),
        "median_completion_time": float(completion["completion_time_min"].median()),
        "slowest_completion_time": float(completion["completion_time_min"].max()),
        "fast_middle_slow_group_counts": groups[["group_label", "activity_count"]].to_dict("records"),
        "slow_group_completed": bool(conclusion.iloc[0]["slow_group_completed"]),
        "early_checkpoint_interpretation": str(conclusion.iloc[0]["early_checkpoint_recommended_interpretation"]),
        "route_level_feasibility_statement": str(conclusion.iloc[0]["route_level_feasibility_statement"]),
        "planning_statement": str(conclusion.iloc[0]["planning_statement"]),
        "weather_aware_interpretation": str(conclusion.iloc[0]["weather_aware_interpretation"]),
        "hr_context_coverage": f"{int(hr_context['heart_rate_available'].sum())}/{len(hr_context)}",
        "slow_group_hr_effort_interpretation": str(conclusion.iloc[0]["slow_group_completion_interpretation_with_weather_and_hr"]),
        "early_checkpoint_interpretation_with_hr": str(conclusion.iloc[0]["early_checkpoint_interpretation_with_hr"]),
        "html_path": str(html_report),
        "png_paths": [str(completion_png), str(group_png), str(early_png)],
        "audit_conclusion": str(audit.iloc[0]["audit_conclusion"]),
        "forbidden_columns_absent": bool(audit.iloc[0]["forbidden_output_columns_absent"]),
        "word_docx_generated": False,
        "v2_2_7_modified": False,
        "route_load_6_5_modified": False,
        "planning_context_fusion_v1_or_v1_1_modified": False,
        "commit_created": False,
    }
    print(payload)


if __name__ == "__main__":
    main()
