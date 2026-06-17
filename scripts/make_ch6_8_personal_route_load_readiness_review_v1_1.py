#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Build CH6.8 personal route-load readiness review v1.1.

Boundary:
- Descriptive evidence gate only.
- This script compares route-load context, completion evidence, HR lifecycle,
  HR effort, weather/planning context, and IB3C event-based HR recovery evidence.
- It does not judge whether a person or team is suitable for a route.
- It is not ability scoring, not route suitability scoring, not THCI/radar scoring,
  not cardiopulmonary diagnosis, and not final hiking risk assessment.
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

BOUNDARY = (
    "Descriptive personal route-load readiness review evidence only. "
    "Completion time, route-load context, planning caution, weather context, HR effort, "
    "HR lifecycle, and IB3C event-based HR recovery are descriptive evidence. "
    "This output is not a cardiopulmonary diagnosis, not ability scoring, "
    "not route suitability scoring, not THCI/radar scoring, and not a final hiking risk assessment."
)

DEFAULT_INPUTS = {
    "hr_recovery_activity_summary": (
        "outputs/report_figures/ch6_7_hr_recovery_from_ib3c_events_v1_1/"
        "activity_hr_recovery_activity_summary_from_ib3c_v1_1.csv"
    ),
    "hr_lifecycle_summary": (
        "outputs/report_figures/ch6_7_hr_lifecycle_recovery_profile_v2/"
        "activity_hr_lifecycle_summary_v2.csv"
    ),
    "completion_conclusion": (
        "outputs/report_figures/ch6_7_completion_feasibility_review_v1_1/"
        "completion_feasibility_conclusion_v1_1.csv"
    ),
    "completion_group_summary": (
        "outputs/report_figures/ch6_7_completion_feasibility_review_v1_1/"
        "completion_feasibility_group_summary_v1_1.csv"
    ),
    "completion_hr_effort_context": (
        "outputs/report_figures/ch6_7_completion_feasibility_review_v1_1/"
        "completion_hr_effort_context_v1_1.csv"
    ),
    "planning_context_route_windows": (
        "outputs/report_figures/ch6_7_planning_context_fusion_v1_1/"
        "planning_context_route_windows_v1_1.csv"
    ),
    "route_load_context_windows": (
        "outputs/report_figures/ch6_5_route_load_context_index_v1/"
        "route_load_context_windows_v1.csv"
    ),
}

DEFAULT_OUTPUT_ROOT = (
    "outputs/report_figures/ch6_8_personal_route_load_readiness_review_v1_1"
)

FORBIDDEN_OUTPUT_COLUMNS = {
    "ability_score",
    "ability_rank",
    "ability_class",
    "thci_score",
    "radar_score",
    "final_hiking_risk_score",
    "route_suitability_score",
    "personal_fitness_score",
    "cardiopulmonary_fitness_score",
    "suitability_score",
}


def read_csv(path: Path, required: bool = True) -> pd.DataFrame:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return pd.DataFrame()
    if path.stat().st_size == 0:
        if required:
            raise pd.errors.EmptyDataError(f"Empty CSV: {path}")
        return pd.DataFrame()
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def safe_text(v) -> str:
    if pd.isna(v):
        return ""
    return str(v)


def has_text(v, pattern: str) -> bool:
    return pattern in safe_text(v)


def bool_from_any(s: pd.Series) -> bool:
    if s.empty:
        return False
    return bool(s.fillna(False).astype(bool).any())


def mode_text(s: pd.Series) -> str:
    vals = [
        str(v)
        for v in s.dropna().tolist()
        if str(v).strip() and str(v).strip().lower() != "nan"
    ]
    if not vals:
        return ""
    return pd.Series(vals).mode().iloc[0]


def ensure_activity_id(df: pd.DataFrame, name: str) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        return out
    if "activity_id_short" not in out.columns:
        raise ValueError(f"{name} missing activity_id_short")
    out["activity_id_short"] = out["activity_id_short"].astype(str)
    return out


def aggregate_planning_context(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["activity_id_short"])

    out = df.copy()
    out = ensure_activity_id(out, "planning_context_route_windows")

    for c in [
        "route_load_context_index_0_100",
        "point_count",
        "temperature_c",
        "relative_humidity_pct",
        "precipitation_mm",
        "wind_gust_ms",
        "uv_index",
        "behavior_response_signal_flag_count",
    ]:
        if c in out.columns:
            out[c] = numeric(out[c])
        else:
            out[c] = np.nan

    for c in [
        "route_load_context_band",
        "planning_caution_level",
        "planning_caution_reason_flags",
        "weather_planning_context_flags",
        "environment_context_flags",
        "behavior_response_planning_flags",
        "event_annotation_flags",
        "terminal_artifact_review_flag",
        "window_qa_flags",
    ]:
        if c not in out.columns:
            out[c] = ""

    out["is_high_route_load_window"] = out["route_load_context_band"].isin(
        ["HIGH_ROUTE_LOAD_CONTEXT", "VERY_HIGH_ROUTE_LOAD_CONTEXT"]
    )
    out["is_very_high_route_load_window"] = out["route_load_context_band"].eq(
        "VERY_HIGH_ROUTE_LOAD_CONTEXT"
    )
    out["is_conservative_planning_window"] = out["planning_caution_level"].eq(
        "CONSERVATIVE_PLANNING_RECOMMENDED"
    )
    out["is_review_planning_window"] = out["planning_caution_level"].str.contains(
        "REVIEW", na=False
    )
    out["weather_humid_context"] = out["weather_planning_context_flags"].str.contains(
        "WEATHER_HUMID_CONTEXT|HIGH_HUMIDITY_CONTEXT", na=False, regex=True
    )
    out["weather_wind_context"] = out["weather_planning_context_flags"].str.contains(
        "WEATHER_WIND_GUST_CONTEXT|WIND_GUST_OBSERVED_CONTEXT|STRONG_GUST_CONTEXT",
        na=False,
        regex=True,
    )
    out["weather_high_uv_context"] = out["weather_planning_context_flags"].str.contains(
        "WEATHER_HIGH_UV_CONTEXT|HIGH_UV_CONTEXT", na=False, regex=True
    )
    out["weather_rain_context"] = out["weather_planning_context_flags"].str.contains(
        "RAIN|PRECIP", na=False, regex=True
    ) & ~out["weather_planning_context_flags"].str.contains("NO_RAIN", na=False)

    out["has_event_annotation"] = ~out["event_annotation_flags"].fillna("").isin(["", "NONE"])

    def agg(g: pd.DataFrame) -> pd.Series:
        n = len(g)
        high_count = int(g["is_high_route_load_window"].sum())
        cons_count = int(g["is_conservative_planning_window"].sum())
        review_count = int(g["is_review_planning_window"].sum())
        return pd.Series({
            "planning_window_count": n,
            "planning_high_route_load_window_count": high_count,
            "planning_very_high_route_load_window_count": int(g["is_very_high_route_load_window"].sum()),
            "planning_high_route_load_window_ratio": high_count / n if n else np.nan,
            "planning_conservative_window_count": cons_count,
            "planning_conservative_window_ratio": cons_count / n if n else np.nan,
            "planning_review_window_count": review_count,
            "planning_review_window_ratio": review_count / n if n else np.nan,
            "planning_route_load_index_median": g["route_load_context_index_0_100"].median(),
            "planning_route_load_index_p75": g["route_load_context_index_0_100"].quantile(0.75),
            "weather_humid_context_present": bool(g["weather_humid_context"].any()),
            "weather_wind_context_present": bool(g["weather_wind_context"].any()),
            "weather_high_uv_context_present": bool(g["weather_high_uv_context"].any()),
            "weather_rain_context_present": bool(g["weather_rain_context"].any()),
            "temperature_c_median": g["temperature_c"].median(),
            "relative_humidity_pct_median": g["relative_humidity_pct"].median(),
            "precipitation_mm_max": g["precipitation_mm"].max(),
            "wind_gust_ms_max": g["wind_gust_ms"].max(),
            "uv_index_max": g["uv_index"].max(),
            "behavior_response_signal_flag_count_sum": numeric(g["behavior_response_signal_flag_count"]).sum(),
            "event_annotation_window_count": int(g["has_event_annotation"].sum()),
            "dominant_planning_caution_level": mode_text(g["planning_caution_level"]),
            "dominant_route_load_context_band": mode_text(g["route_load_context_band"]),
        })

    return out.groupby("activity_id_short", as_index=False).apply(agg).reset_index(drop=True)


def aggregate_route_load_context(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["activity_id_short"])

    out = ensure_activity_id(df.copy(), "route_load_context_windows")
    for c in [
        "route_load_context_index_0_100",
        "heart_rate_bpm_median",
        "speed_mps_median",
        "low_speed_ratio",
        "stopped_ratio",
        "behavior_response_signal_flag_count",
    ]:
        if c in out.columns:
            out[c] = numeric(out[c])
        else:
            out[c] = np.nan

    if "route_load_context_band" not in out.columns:
        out["route_load_context_band"] = ""

    out["is_high_route_load_window"] = out["route_load_context_band"].isin(
        ["HIGH_ROUTE_LOAD_CONTEXT", "VERY_HIGH_ROUTE_LOAD_CONTEXT"]
    )

    def agg(g: pd.DataFrame) -> pd.Series:
        high = g[g["is_high_route_load_window"]]
        n = len(g)
        return pd.Series({
            "route_load_window_count": n,
            "route_load_high_window_count": int(g["is_high_route_load_window"].sum()),
            "route_load_high_window_ratio": float(g["is_high_route_load_window"].sum()) / n if n else np.nan,
            "route_load_index_median": g["route_load_context_index_0_100"].median(),
            "route_load_index_p75": g["route_load_context_index_0_100"].quantile(0.75),
            "route_load_high_hr_median": high["heart_rate_bpm_median"].median() if len(high) else np.nan,
            "route_load_low_speed_ratio_median": g["low_speed_ratio"].median(),
            "route_load_stopped_ratio_median": g["stopped_ratio"].median(),
            "route_load_behavior_signal_flag_count_sum": numeric(g["behavior_response_signal_flag_count"]).sum(),
        })

    return out.groupby("activity_id_short", as_index=False).apply(agg).reset_index(drop=True)


def normalize_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    t = safe_text(v).strip().lower()
    return t in {"true", "1", "yes", "y"}


def make_review_flags(row: pd.Series) -> list[str]:
    flags: list[str] = []

    completion_available = pd.notna(row.get("completion_time_min"))
    hr_available = normalize_bool(row.get("heart_rate_available", False))
    lifecycle_hr_coverage = row.get("hr_coverage_ratio", np.nan)

    if not completion_available:
        flags.append("INSUFFICIENT_COMPLETION_HISTORY")
    if not hr_available and (pd.isna(lifecycle_hr_coverage) or lifecycle_hr_coverage < 0.8):
        flags.append("INSUFFICIENT_HR_EVIDENCE")

    if flags:
        return flags

    completion_group = safe_text(row.get("completion_group"))
    if completion_group == "slow":
        flags.append("SLOW_GROUP_COMPLETION_CONTEXT")
        flags.append("CONSERVATIVE_PACING_RECOMMENDED")

    effort_flags = safe_text(row.get("hr_effort_interpretation_flags"))
    early_high_hr_ratio = row.get("early_checkpoint_high_hr_window_ratio", np.nan)
    high_load_high_hr_ratio = row.get("high_or_very_high_load_high_hr_window_ratio", np.nan)
    activity_high_hr_ratio = row.get("activity_relative_high_hr_window_ratio", np.nan)

    route_core_count = row.get("route_core_event_count", np.nan)
    confirmed = row.get("confirmed_hr_recovery_count", np.nan)
    high_no_recovery = row.get("high_hr_pause_without_recovery_count", np.nan)
    no_clear = row.get("no_clear_recovery_event_count", np.nan)
    facility = row.get("route_core_facility_rest_event_count", np.nan)

    # v1.1 change:
    # Early-checkpoint high-HR evidence remains an important flag, but it no longer
    # becomes the primary gate by itself unless it is strong or accompanied by
    # slow completion / high-load HR / limited recovery / no-recovery burden.
    early_hr_flag_present = (
        has_text(effort_flags, "EARLY_CHECKPOINT_HIGH_HR_EVIDENCE_PRESENT")
        or (pd.notna(early_high_hr_ratio) and early_high_hr_ratio > 0)
    )
    if early_hr_flag_present:
        flags.append("EARLY_CHECKPOINT_HIGH_HR_EVIDENCE_PRESENT")

    early_review_strong = pd.notna(early_high_hr_ratio) and early_high_hr_ratio >= 0.75
    early_review_compound = (
        pd.notna(early_high_hr_ratio)
        and early_high_hr_ratio >= 0.50
        and (
            completion_group == "slow"
            or (pd.notna(high_load_high_hr_ratio) and high_load_high_hr_ratio >= 0.30)
            or (pd.notna(route_core_count) and route_core_count <= 0)
            or (
                pd.notna(high_no_recovery)
                and pd.notna(confirmed)
                and high_no_recovery >= confirmed
            )
        )
    )
    if early_review_strong or early_review_compound:
        flags.append("EARLY_CHECKPOINT_REVIEW_REQUIRED")

    if (
        has_text(effort_flags, "HIGH_LOAD_HIGH_HR_EVIDENCE_PRESENT")
        or (pd.notna(high_load_high_hr_ratio) and high_load_high_hr_ratio >= 0.30)
        or (pd.notna(activity_high_hr_ratio) and activity_high_hr_ratio >= 0.30)
    ):
        flags.append("HIGH_LOAD_HIGH_HR_EVIDENCE_PRESENT")
        flags.append("CONSERVATIVE_PACING_RECOMMENDED")

    if pd.notna(route_core_count) and route_core_count <= 0:
        flags.append("HR_RECOVERY_EVIDENCE_LIMITED")

    if pd.notna(facility) and facility > 0:
        flags.append("ON_ROUTE_FACILITY_REST_EVIDENCE_PRESENT")

    if pd.notna(confirmed) and confirmed > 0:
        flags.append("CONFIRMED_HR_RECOVERY_EVIDENCE_PRESENT")

    if pd.notna(high_no_recovery) and high_no_recovery > 0:
        flags.append("HIGH_HR_PAUSE_WITHOUT_RECOVERY_PRESENT")

    if (
        pd.notna(high_no_recovery)
        and pd.notna(confirmed)
        and high_no_recovery >= max(3, confirmed)
    ):
        flags.append("HIGH_HR_NO_RECOVERY_BURDEN_REVIEW")
        flags.append("CONSERVATIVE_PACING_RECOMMENDED")

    if pd.notna(no_clear) and no_clear >= 10:
        flags.append("MANY_NO_CLEAR_RECOVERY_EVENTS")
        flags.append("CONSERVATIVE_PACING_RECOMMENDED")

    planning_conservative_ratio = row.get("planning_conservative_window_ratio", np.nan)
    planning_review_ratio = row.get("planning_review_window_ratio", np.nan)
    high_load_ratio = row.get("route_load_high_window_ratio", np.nan)

    if pd.notna(planning_conservative_ratio) and planning_conservative_ratio >= 0.25:
        flags.append("CONSERVATIVE_PLANNING_WINDOWS_PRESENT")
        flags.append("CONSERVATIVE_PACING_RECOMMENDED")

    if pd.notna(planning_review_ratio) and planning_review_ratio >= 0.25:
        flags.append("PLANNING_REVIEW_WINDOWS_PRESENT")

    if pd.notna(high_load_ratio) and high_load_ratio >= 0.25:
        flags.append("HIGH_ROUTE_LOAD_EXPOSURE_PRESENT")

    weather_present = any(
        normalize_bool(row.get(c, False))
        for c in [
            "weather_humid_context_present",
            "weather_wind_context_present",
            "weather_high_uv_context_present",
            "weather_rain_context_present",
        ]
    )
    if weather_present:
        flags.append("WEATHER_CONTEXT_PRESENT")
        if (
            completion_group == "slow"
            or "HIGH_LOAD_HIGH_HR_EVIDENCE_PRESENT" in flags
            or "EARLY_CHECKPOINT_REVIEW_REQUIRED" in flags
        ):
            flags.append("WEATHER_SENSITIVE_REVIEW_REQUIRED")

    if not flags:
        flags.append("STANDARD_PREP_REASONABLE")

    # Stable order without duplicates.
    seen = set()
    ordered = []
    for f in flags:
        if f not in seen:
            ordered.append(f)
            seen.add(f)
    return ordered

def primary_gate_from_flags(flags: list[str]) -> str:
    if "INSUFFICIENT_COMPLETION_HISTORY" in flags or "INSUFFICIENT_HR_EVIDENCE" in flags:
        return "INSUFFICIENT_PERSONAL_HISTORY"
    if "EARLY_CHECKPOINT_REVIEW_REQUIRED" in flags:
        return "EARLY_CHECKPOINT_REVIEW_REQUIRED"
    if "CONSERVATIVE_PACING_RECOMMENDED" in flags:
        return "CONSERVATIVE_PACING_RECOMMENDED"
    if "WEATHER_SENSITIVE_REVIEW_REQUIRED" in flags:
        return "WEATHER_SENSITIVE_REVIEW_REQUIRED"
    return "STANDARD_PREP_REASONABLE"

def interpretation_zh(row: pd.Series, flags: list[str], gate: str) -> str:
    activity_id = row.get("activity_id_short", "")
    group = safe_text(row.get("completion_group"))
    completion = row.get("completion_time_min", np.nan)

    if gate == "INSUFFICIENT_PERSONAL_HISTORY":
        return f"{activity_id} 缺少足夠完成或 HR evidence，僅能保留為待補資料案例。"

    base = f"{activity_id} 已有完成紀錄"
    if pd.notna(completion):
        base += f"（{completion:.1f} min"
        if group:
            base += f", {group} group"
        base += "）"

    if gate == "EARLY_CHECKPOINT_REVIEW_REQUIRED":
        return (
            base
            + "，但早期檢核區段存在較高 HR effort 或高負荷反應，建議採早期狀態檢核與保守配速。"
        )

    if gate == "CONSERVATIVE_PACING_RECOMMENDED":
        return (
            base
            + "，具完成可行性 evidence，但高負荷、HR effort、停留恢復或規劃 caution evidence 顯示仍建議保守配速。"
        )

    if gate == "WEATHER_SENSITIVE_REVIEW_REQUIRED":
        return (
            base
            + "，完成 evidence 可用，但天候背景可能影響行程規劃，建議做 weather-sensitive review。"
        )

    return base + "，目前 descriptive evidence 支持標準準備下進行，但仍需依當日天候與隊伍狀態調整。"


def build_readiness(
    recovery: pd.DataFrame,
    lifecycle: pd.DataFrame,
    completion_hr: pd.DataFrame,
    planning_agg: pd.DataFrame,
    route_load_agg: pd.DataFrame,
) -> pd.DataFrame:
    frames = []
    for df in [recovery, lifecycle, completion_hr, planning_agg, route_load_agg]:
        if not df.empty and "activity_id_short" in df.columns:
            frames.append(df[["activity_id_short"]].copy())

    if not frames:
        return pd.DataFrame()

    activities = pd.concat(frames, ignore_index=True).drop_duplicates().sort_values("activity_id_short")

    out = activities.copy()

    merge_frames = [
        recovery,
        lifecycle,
        completion_hr,
        planning_agg,
        route_load_agg,
    ]
    for df in merge_frames:
        if df is None or df.empty:
            continue
        out = out.merge(df, on="activity_id_short", how="left")

    for c in [
        "completion_time_min",
        "early_checkpoint_high_hr_window_ratio",
        "high_or_very_high_load_high_hr_window_ratio",
        "activity_relative_high_hr_window_ratio",
        "route_core_event_count",
        "confirmed_hr_recovery_count",
        "high_hr_pause_without_recovery_count",
        "no_clear_recovery_event_count",
        "route_core_facility_rest_event_count",
        "planning_conservative_window_ratio",
        "planning_review_window_ratio",
        "route_load_high_window_ratio",
        "hr_coverage_ratio",
    ]:
        if c in out.columns:
            out[c] = numeric(out[c])
        else:
            out[c] = np.nan

    flags_list = []
    gates = []
    interpretations = []
    for _, row in out.iterrows():
        flags = make_review_flags(row)
        gate = primary_gate_from_flags(flags)
        flags_list.append("|".join(flags))
        gates.append(gate)
        interpretations.append(interpretation_zh(row, flags, gate))

    out["readiness_review_gate"] = gates
    out["readiness_review_flags"] = flags_list
    out["readiness_interpretation_zh"] = interpretations
    out["boundary"] = BOUNDARY

    selected_preferred = [
        "activity_id_short",
        "readiness_review_gate",
        "readiness_review_flags",
        "readiness_interpretation_zh",
        "completion_time_min",
        "completion_group",
        "heart_rate_available",
        "heart_rate_bpm_median_all",
        "activity_relative_high_hr_window_ratio",
        "high_or_very_high_load_hr_median",
        "high_or_very_high_load_high_hr_window_ratio",
        "early_checkpoint_hr_median",
        "early_checkpoint_high_hr_window_ratio",
        "hr_effort_interpretation_flags",
        "hr_median_bpm",
        "hr_p75_bpm",
        "hr_p90_bpm",
        "high_load_hr_median",
        "early_hr_median",
        "middle_hr_median",
        "late_hr_median",
        "hr_drift_late_minus_early_bpm",
        "data_quality_flags",
        "event_count_total",
        "route_core_event_count",
        "route_core_facility_rest_event_count",
        "confirmed_hr_recovery_count",
        "high_hr_pause_without_recovery_count",
        "pause_without_hr_drop_count",
        "possible_recovery_count",
        "strong_recovery_event_count",
        "no_clear_recovery_event_count",
        "hr_drop_bpm_median",
        "hr_drop_bpm_max",
        "hr_recovery_slope_bpm_per_min_median",
        "estimated_recovery_score_median",
        "dominant_recovery_strength_class",
        "dominant_semantic_recovery_interpretation",
        "route_core_recovery_status",
        "planning_window_count",
        "planning_high_route_load_window_count",
        "planning_high_route_load_window_ratio",
        "planning_conservative_window_count",
        "planning_conservative_window_ratio",
        "planning_review_window_count",
        "planning_review_window_ratio",
        "dominant_planning_caution_level",
        "weather_humid_context_present",
        "weather_wind_context_present",
        "weather_high_uv_context_present",
        "weather_rain_context_present",
        "temperature_c_median",
        "relative_humidity_pct_median",
        "precipitation_mm_max",
        "wind_gust_ms_max",
        "uv_index_max",
        "route_load_window_count",
        "route_load_high_window_count",
        "route_load_high_window_ratio",
        "route_load_index_median",
        "route_load_index_p75",
        "route_load_high_hr_median",
        "route_load_low_speed_ratio_median",
        "route_load_stopped_ratio_median",
        "boundary",
    ]

    cols = [c for c in selected_preferred if c in out.columns]
    extra = [c for c in out.columns if c not in cols]
    return out[cols + extra]


def summarize_groups(review: pd.DataFrame) -> pd.DataFrame:
    if review.empty:
        return pd.DataFrame()

    out = (
        review.groupby("readiness_review_gate", as_index=False)
        .agg(
            activity_count=("activity_id_short", "count"),
            completion_time_min_median=("completion_time_min", "median"),
            route_core_event_count_median=("route_core_event_count", "median"),
            confirmed_hr_recovery_count_median=("confirmed_hr_recovery_count", "median"),
            high_hr_pause_without_recovery_count_median=(
                "high_hr_pause_without_recovery_count",
                "median",
            ),
            early_checkpoint_high_hr_window_ratio_median=(
                "early_checkpoint_high_hr_window_ratio",
                "median",
            ),
            high_load_high_hr_window_ratio_median=(
                "high_or_very_high_load_high_hr_window_ratio",
                "median",
            ),
            planning_conservative_window_ratio_median=(
                "planning_conservative_window_ratio",
                "median",
            ),
        )
    )
    out["boundary"] = BOUNDARY
    return out


def input_contract_rows(input_paths: dict[str, Path], dfs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for name, path in input_paths.items():
        df = dfs.get(name, pd.DataFrame())
        rows.append({
            "input_name": name,
            "path": str(path),
            "exists": path.exists(),
            "rows": len(df) if df is not None else 0,
            "columns": "|".join(df.columns.tolist()) if df is not None and not df.empty else "",
        })
    return pd.DataFrame(rows)


def forbidden_columns_absent(paths: Iterable[Path]) -> bool:
    for path in paths:
        if not path.exists() or path.suffix.lower() != ".csv":
            continue
        try:
            cols = set(pd.read_csv(path, nrows=0, encoding="utf-8-sig").columns)
        except Exception:
            continue
        if cols & FORBIDDEN_OUTPUT_COLUMNS:
            return False
    return True


def write_html_report(
    output_path: Path,
    review: pd.DataFrame,
    group_summary: pd.DataFrame,
    audit: pd.DataFrame,
    input_contract: pd.DataFrame,
    completion_conclusion: pd.DataFrame,
) -> None:
    def table_html(df: pd.DataFrame, max_rows: int = 80) -> str:
        if df is None or df.empty:
            return "<p>No rows.</p>"
        return df.head(max_rows).to_html(index=False, escape=True)

    css = """
    <style>
    body { font-family: Arial, "Noto Sans TC", sans-serif; margin: 24px; color: #111827; }
    h1, h2 { color: #0f172a; }
    .boundary { background: #f8fafc; border-left: 5px solid #64748b; padding: 12px; margin: 16px 0; }
    table { border-collapse: collapse; font-size: 12px; width: 100%; margin-bottom: 24px; }
    th, td { border: 1px solid #d1d5db; padding: 4px 6px; vertical-align: top; }
    th { background: #f1f5f9; }
    code { background: #f1f5f9; padding: 2px 4px; }
    </style>
    """

    html_text = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>CH6.8 Personal Route-Load Readiness Review v1.1</title>
{css}
</head>
<body>
<h1>CH6.8 Personal Route-Load Readiness Review v1.1</h1>
<div class="boundary">{html.escape(BOUNDARY)}</div>

<h2>Audit</h2>
{table_html(audit, 20)}

<h2>Input contract</h2>
{table_html(input_contract, 20)}

<h2>Route-level completion feasibility context</h2>
{table_html(completion_conclusion, 10)}

<h2>Readiness gate group summary</h2>
{table_html(group_summary, 20)}

<h2>Activity readiness review</h2>
{table_html(review, 80)}
</body>
</html>
"""
    output_path.write_text(html_text, encoding="utf-8")


def build_audit(
    script_path: Path,
    output_root: Path,
    review: pd.DataFrame,
    group_summary: pd.DataFrame,
    input_contract: pd.DataFrame,
    output_paths: list[Path],
) -> pd.DataFrame:
    forbidden_absent = forbidden_columns_absent(output_paths)
    missing_inputs = input_contract.loc[~input_contract["exists"], "input_name"].tolist()

    gate_counts = {}
    if not review.empty and "readiness_review_gate" in review.columns:
        gate_counts = review["readiness_review_gate"].value_counts().to_dict()

    conclusion = (
        "PASS_CH6_8_PERSONAL_ROUTE_LOAD_READINESS_REVIEW_V1_1_DESCRIPTIVE_ONLY"
        if review is not None
        and not review.empty
        and forbidden_absent
        and not missing_inputs
        else "FAIL_CH6_8_PERSONAL_ROUTE_LOAD_READINESS_REVIEW_V1_1_REVIEW_REQUIRED"
    )

    return pd.DataFrame([{
        "script_path": str(script_path),
        "output_root": str(output_root),
        "activity_count": len(review) if review is not None else 0,
        "group_summary_rows": len(group_summary) if group_summary is not None else 0,
        "standard_prep_reasonable_count": int(gate_counts.get("STANDARD_PREP_REASONABLE", 0)),
        "conservative_pacing_recommended_count": int(gate_counts.get("CONSERVATIVE_PACING_RECOMMENDED", 0)),
        "early_checkpoint_review_required_count": int(gate_counts.get("EARLY_CHECKPOINT_REVIEW_REQUIRED", 0)),
        "weather_sensitive_review_required_count": int(gate_counts.get("WEATHER_SENSITIVE_REVIEW_REQUIRED", 0)),
        "insufficient_personal_history_count": int(gate_counts.get("INSUFFICIENT_PERSONAL_HISTORY", 0)),
        "missing_inputs": "|".join(missing_inputs),
        "forbidden_columns_absent": forbidden_absent,
        "audit_conclusion": conclusion,
        "boundary": BOUNDARY,
    }])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".", help="Project root, default current directory.")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, help="Output root.")
    for key, default_path in DEFAULT_INPUTS.items():
        parser.add_argument(f"--{key.replace('_', '-')}", default=default_path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    output_root = (project_root / args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    input_paths = {}
    for key in DEFAULT_INPUTS:
        arg_name = key
        path_value = getattr(args, arg_name)
        input_paths[key] = (project_root / path_value).resolve()

    dfs = {name: read_csv(path, required=True) for name, path in input_paths.items()}

    recovery = ensure_activity_id(dfs["hr_recovery_activity_summary"], "hr_recovery_activity_summary")
    lifecycle = ensure_activity_id(dfs["hr_lifecycle_summary"], "hr_lifecycle_summary")
    completion_hr = ensure_activity_id(dfs["completion_hr_effort_context"], "completion_hr_effort_context")

    planning_agg = aggregate_planning_context(dfs["planning_context_route_windows"])
    route_load_agg = aggregate_route_load_context(dfs["route_load_context_windows"])

    review = build_readiness(
        recovery=recovery,
        lifecycle=lifecycle,
        completion_hr=completion_hr,
        planning_agg=planning_agg,
        route_load_agg=route_load_agg,
    )

    group_summary = summarize_groups(review)
    input_contract = input_contract_rows(input_paths, dfs)
    completion_conclusion = dfs["completion_conclusion"].copy()

    review_csv = output_root / "personal_route_load_readiness_review_v1_1.csv"
    group_summary_csv = output_root / "personal_route_load_readiness_group_summary_v1_1.csv"
    input_contract_csv = output_root / "personal_route_load_readiness_input_contract_v1_1.csv"
    audit_csv = output_root / "personal_route_load_readiness_audit_v1_1.csv"
    html_report = output_root / "personal_route_load_readiness_report_v1_1.html"

    review.to_csv(review_csv, index=False, encoding="utf-8-sig")
    group_summary.to_csv(group_summary_csv, index=False, encoding="utf-8-sig")
    input_contract.to_csv(input_contract_csv, index=False, encoding="utf-8-sig")

    output_paths = [review_csv, group_summary_csv, input_contract_csv, audit_csv, html_report]
    audit = build_audit(
        script_path=Path(__file__).resolve(),
        output_root=output_root,
        review=review,
        group_summary=group_summary,
        input_contract=input_contract,
        output_paths=output_paths[:-2],
    )
    audit.to_csv(audit_csv, index=False, encoding="utf-8-sig")

    write_html_report(
        html_report,
        review=review,
        group_summary=group_summary,
        audit=audit,
        input_contract=input_contract,
        completion_conclusion=completion_conclusion,
    )

    result = audit.iloc[0].to_dict()
    result["html_report"] = str(html_report)
    print(result)


if __name__ == "__main__":
    main()
