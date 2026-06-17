#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build CH6.5.3 route-load × personal-performance readiness review gate v1.

This script fuses:
- CH6.5.1 personal/activity behavior profile
- CH6.5.2 weather-adjusted behavior context
- CH6.8 personal route-load readiness review

The output is a descriptive review gate layer. It is not an ability score,
not a route suitability score, not a final hiking risk score, and not a
go/no-go decision.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


DEFAULT_PROFILE_ID = "qixing_lengshuikeng_activity_group_full25"
DEFAULT_ROUTE_FOLDER = "qixing_lengshuikeng"

DEFAULT_CH6_5_1_WINDOWS = (
    "outputs/report_figures/ch6_5_1_personal_activity_behavior_profile_v1_1/"
    "personal_behavior_profile_window_features_v1_1.csv"
)
DEFAULT_CH6_5_2_WINDOWS = (
    "outputs/report_figures/ch6_5_2_weather_adjusted_behavior_context_v1/"
    "weather_adjusted_behavior_context_windows_v1.csv"
)
DEFAULT_CH6_8_READINESS = (
    "outputs/report_figures/ch6_8_personal_route_load_readiness_review_v1_1/"
    "personal_route_load_readiness_review_v1_1.csv"
)
DEFAULT_CH6_8_AUDIT = (
    "outputs/report_figures/ch6_8_personal_route_load_readiness_review_v1_1/"
    "personal_route_load_readiness_audit_v1_1.csv"
)
DEFAULT_OUTPUT_ROOT = (
    "outputs/report_figures/ch6_5_3_route_load_personal_performance_readiness_gate_v1"
)

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

BOUNDARY_TEXT = (
    "Descriptive CH6.5.3 route-load × personal-performance readiness review "
    "gate only. This layer fuses behavior, weather, and readiness review "
    "context, but it is not ability scoring, not ranking, not classing, not "
    "THCI, not radar, not final hiking risk scoring, not route suitability "
    "scoring, not go/no-go decisioning, not medical diagnosis, and not "
    "causality evidence."
)

METHOD_NOTE = (
    "The review gate is a descriptive evidence join across CH6.5.1 behavior "
    "profile, CH6.5.2 weather-context review, and CH6.8 readiness review. "
    "It creates review flags and grouped summaries only."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=r"D:\mountain_work\115_osm")
    parser.add_argument("--profile-id", default=DEFAULT_PROFILE_ID)
    parser.add_argument("--route-folder", default=DEFAULT_ROUTE_FOLDER)
    parser.add_argument("--ch6-5-1-windows", default=DEFAULT_CH6_5_1_WINDOWS)
    parser.add_argument("--ch6-5-2-windows", default=DEFAULT_CH6_5_2_WINDOWS)
    parser.add_argument("--ch6-8-readiness", default=DEFAULT_CH6_8_READINESS)
    parser.add_argument("--ch6-8-audit", default=DEFAULT_CH6_8_AUDIT)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
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


def boolish(series: pd.Series) -> pd.Series:
    return clean_str(series).str.lower().isin(["true", "1", "yes", "y"])


def pipe_flags(values: Iterable[object]) -> str:
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


def detect_activity_col(df: pd.DataFrame) -> str | None:
    candidates = [
        "activity_id_short",
        "activity_id",
        "activity",
        "input_activity_id",
        "activity_name",
    ]
    lower_map = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in lower_map:
            return lower_map[c.lower()]
    for c in df.columns:
        lc = c.lower()
        if "activity" in lc and ("id" in lc or "short" in lc):
            return c
    return None


def build_readiness_context(readiness: pd.DataFrame, profile_id: str, route_folder: str) -> tuple[pd.DataFrame, float, str]:
    if readiness.empty:
        return pd.DataFrame(columns=[
            "activity_id_short",
            "ch6_8_readiness_join_status",
            "ch6_8_readiness_context_flags",
            "ch6_8_readiness_status_observed",
        ]), 0.0, "READINESS_SOURCE_MISSING"

    activity_col = detect_activity_col(readiness)
    if activity_col is None:
        # Keep source available but not activity-joinable.
        flags = pipe_flags(readiness.astype(str).values.ravel().tolist())
        return pd.DataFrame([{
            "activity_id_short": "",
            "ch6_8_readiness_join_status": "READINESS_SOURCE_AVAILABLE_NOT_ACTIVITY_JOINABLE",
            "ch6_8_readiness_context_flags": flags,
            "ch6_8_readiness_status_observed": flags,
        }]), 0.0, "READINESS_SOURCE_AVAILABLE_NOT_ACTIVITY_JOINABLE"

    r = readiness.copy()
    r["activity_id_short"] = clean_str(r[activity_col])
    r = r[r["activity_id_short"] != ""].copy()

    useful_cols = []
    for c in r.columns:
        lc = c.lower()
        if c == "activity_id_short":
            continue
        if any(k in lc for k in ["readiness", "review", "gate", "flag", "status", "conclusion"]):
            if "boundary" not in lc and "path" not in lc:
                useful_cols.append(c)

    if not useful_cols:
        useful_cols = [c for c in r.columns if c != "activity_id_short"]

    rows = []
    for activity_id, group in r.groupby("activity_id_short", dropna=False):
        observed_values = []
        for col in useful_cols:
            observed_values.extend(clean_str(group[col]).tolist())
        flags = pipe_flags(observed_values)
        rows.append({
            "activity_id_short": activity_id,
            "ch6_8_readiness_join_status": "READINESS_JOINED_BY_ACTIVITY",
            "ch6_8_readiness_context_flags": flags if flags != "NONE" else "READINESS_REVIEW_AVAILABLE",
            "ch6_8_readiness_status_observed": flags if flags != "NONE" else "READINESS_REVIEW_AVAILABLE",
        })

    out = pd.DataFrame(rows).sort_values("activity_id_short").reset_index(drop=True)
    return out, 1.0, "READINESS_JOINABLE_BY_ACTIVITY"


def prepare_weather_windows(weather_windows: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    required = [
        "activity_id_short",
        "route_load_context_band",
        "route_phase_for_profile",
        "weather_adjustment_context_class",
        "conservative_weather_review_required",
        "behavior_weather_context_review_required",
    ]
    require_columns(weather_windows, required, "CH6.5.2 weather windows")

    w = weather_windows.copy()
    w["profile_id"] = args.profile_id
    w["route_folder"] = args.route_folder
    w["activity_id_short"] = clean_str(w["activity_id_short"])

    text_cols = [
        "route_load_context_band",
        "route_phase_for_profile",
        "weather_adjustment_context_class",
        "weather_adjustment_context_flags",
        "conservative_planning_weather_flags",
    ]
    for col in text_cols:
        if col in w.columns:
            w[col] = clean_str(w[col])

    for col in [
        "speed_mps_median",
        "low_speed_ratio",
        "stopped_ratio",
        "heart_rate_bpm_median",
        "heart_rate_bpm_p75",
        "temperature_c",
        "relative_humidity_pct",
        "precipitation_mm",
        "wind_speed_ms",
        "wind_gust_ms",
        "uv_index",
    ]:
        if col in w.columns:
            w[col] = numeric(w[col])

    for col in [
        "conservative_weather_review_required",
        "behavior_weather_context_review_required",
        "route_load_behavior_candidate_window_bool",
        "weather_context_available_bool",
    ]:
        if col in w.columns:
            if w[col].dtype == bool:
                continue
            w[col] = boolish(w[col])

    if "route_load_behavior_candidate_window_bool" not in w.columns:
        w["route_load_behavior_candidate_window_bool"] = False

    if "weather_context_available_bool" not in w.columns:
        weather_cols = [
            "temperature_c",
            "relative_humidity_pct",
            "precipitation_mm",
            "wind_speed_ms",
            "wind_gust_ms",
            "uv_index",
        ]
        present_cols = [c for c in weather_cols if c in w.columns]
        w["weather_context_available_bool"] = w[present_cols].notna().any(axis=1) if present_cols else False

    return w


def summarize_activity(group: pd.DataFrame, args: argparse.Namespace) -> dict[str, object]:
    activity_ids = sorted(group["activity_id_short"].dropna().astype(str).unique().tolist())
    route_load_flags = group.get("route_load_context_band", pd.Series(dtype=str)).astype(str)
    phase_flags = group.get("route_phase_for_profile", pd.Series(dtype=str)).astype(str)
    weather_class = group.get("weather_adjustment_context_class", pd.Series(dtype=str)).astype(str)

    high_mask = route_load_flags.isin(["HIGH_ROUTE_LOAD_CONTEXT", "VERY_HIGH_ROUTE_LOAD_CONTEXT"])
    uphill_mask = phase_flags.eq("UPHILL_ROUTE_CONTEXT")
    downhill_mask = phase_flags.eq("DOWNHILL_ROUTE_CONTEXT")

    return {
        "profile_id": args.profile_id,
        "route_folder": args.route_folder,
        "activity_id_short": activity_ids[0] if len(activity_ids) == 1 else "|".join(activity_ids),
        "windows_n": int(len(group)),
        "route_load_context_bands_observed": pipe_flags(route_load_flags.tolist()),
        "route_phases_observed": pipe_flags(phase_flags.tolist()),
        "weather_context_classes_observed": pipe_flags(weather_class.tolist()),
        "high_or_very_high_route_load_windows_n": int(high_mask.sum()),
        "high_or_very_high_route_load_ratio": round(float(high_mask.mean()) if len(group) else np.nan, 6),
        "uphill_windows_n": int(uphill_mask.sum()),
        "uphill_ratio": round(float(uphill_mask.mean()) if len(group) else np.nan, 6),
        "downhill_windows_n": int(downhill_mask.sum()),
        "downhill_ratio": round(float(downhill_mask.mean()) if len(group) else np.nan, 6),
        "uphill_high_route_load_windows_n": int((uphill_mask & high_mask).sum()),
        "uphill_high_route_load_ratio": round(float((uphill_mask & high_mask).mean()) if len(group) else np.nan, 6),
        "speed_mps_median_median": round(q(group.get("speed_mps_median", pd.Series(dtype=float)), 0.50), 6),
        "speed_mps_median_p25": round(q(group.get("speed_mps_median", pd.Series(dtype=float)), 0.25), 6),
        "speed_mps_median_p75": round(q(group.get("speed_mps_median", pd.Series(dtype=float)), 0.75), 6),
        "low_speed_ratio_avg": round(mean(group.get("low_speed_ratio", pd.Series(dtype=float))), 6),
        "stopped_ratio_avg": round(mean(group.get("stopped_ratio", pd.Series(dtype=float))), 6),
        "heart_rate_bpm_median_avg": round(mean(group.get("heart_rate_bpm_median", pd.Series(dtype=float))), 6),
        "heart_rate_bpm_median_median": round(q(group.get("heart_rate_bpm_median", pd.Series(dtype=float)), 0.50), 6),
        "weather_context_available_ratio": round(ratio_true(group.get("weather_context_available_bool", pd.Series(dtype=bool))), 6),
        "conservative_weather_review_required_ratio": round(ratio_true(group.get("conservative_weather_review_required", pd.Series(dtype=bool))), 6),
        "behavior_weather_context_review_required_ratio": round(ratio_true(group.get("behavior_weather_context_review_required", pd.Series(dtype=bool))), 6),
        "route_load_behavior_candidate_window_ratio": round(ratio_true(group.get("route_load_behavior_candidate_window_bool", pd.Series(dtype=bool))), 6),
        "weather_adjustment_flags_observed": pipe_flags(group.get("weather_adjustment_context_flags", pd.Series(dtype=str)).astype(str).tolist()),
        "conservative_planning_weather_flags_observed": pipe_flags(group.get("conservative_planning_weather_flags", pd.Series(dtype=str)).astype(str).tolist()),
    }


def activity_review_flags(row: pd.Series) -> str:
    flags: list[str] = []

    if float(row.get("high_or_very_high_route_load_ratio", 0) or 0) > 0:
        flags.append("HIGH_ROUTE_LOAD_CONTEXT_PRESENT")
    if float(row.get("uphill_high_route_load_ratio", 0) or 0) > 0:
        flags.append("UPHILL_HIGH_ROUTE_LOAD_CONTEXT_PRESENT")
    if float(row.get("route_load_behavior_candidate_window_ratio", 0) or 0) > 0:
        flags.append("ROUTE_LOAD_BEHAVIOR_RESPONSE_WINDOWS_PRESENT")
    if float(row.get("behavior_weather_context_review_required_ratio", 0) or 0) > 0:
        flags.append("BEHAVIOR_RESPONSE_UNDER_WEATHER_CONTEXT_REVIEW_REQUIRED")
    if float(row.get("conservative_weather_review_required_ratio", 0) or 0) > 0:
        flags.append("CONSERVATIVE_WEATHER_PLANNING_REVIEW_REQUIRED")
    if float(row.get("weather_context_available_ratio", 0) or 0) < 1:
        flags.append("WEATHER_CONTEXT_COVERAGE_REVIEW_REQUIRED")

    readiness = str(row.get("ch6_8_readiness_context_flags", "")).upper()
    if not readiness or readiness == "NAN":
        flags.append("CH6_8_READINESS_CONTEXT_MISSING_REVIEW_REQUIRED")
    elif "REVIEW_REQUIRED" in readiness:
        flags.append("CH6_8_READINESS_REVIEW_REQUIRED")
    else:
        flags.append("CH6_8_READINESS_CONTEXT_AVAILABLE")

    return pipe_flags(flags)


def gate_status_from_flags(flags: str) -> str:
    s = str(flags)
    if "CH6_8_READINESS_CONTEXT_MISSING_REVIEW_REQUIRED" in s:
        return "READINESS_REVIEW_GATE_CONTEXT_INCOMPLETE"
    if "BEHAVIOR_RESPONSE_UNDER_WEATHER_CONTEXT_REVIEW_REQUIRED" in s and "CH6_8_READINESS_REVIEW_REQUIRED" in s:
        return "READINESS_REVIEW_GATE_WEATHER_BEHAVIOR_AND_CH6_8_REVIEW_REQUIRED"
    if "BEHAVIOR_RESPONSE_UNDER_WEATHER_CONTEXT_REVIEW_REQUIRED" in s:
        return "READINESS_REVIEW_GATE_WEATHER_BEHAVIOR_REVIEW_REQUIRED"
    if "CONSERVATIVE_WEATHER_PLANNING_REVIEW_REQUIRED" in s or "CH6_8_READINESS_REVIEW_REQUIRED" in s:
        return "READINESS_REVIEW_GATE_CONSERVATIVE_REVIEW_REQUIRED"
    return "READINESS_REVIEW_GATE_CONTEXT_AVAILABLE_NO_ADDITIONAL_FLAG"


def build_activity_summary(
    weather_windows: pd.DataFrame,
    readiness_context: pd.DataFrame,
    args: argparse.Namespace,
) -> pd.DataFrame:
    rows = []
    for activity_id, group in weather_windows.groupby("activity_id_short", dropna=False):
        rows.append(summarize_activity(group, args))

    out = pd.DataFrame(rows)
    if out.empty:
        return out

    out = out.merge(readiness_context, on="activity_id_short", how="left")
    out["ch6_8_readiness_join_status"] = out["ch6_8_readiness_join_status"].fillna("READINESS_NOT_JOINED")
    out["ch6_8_readiness_context_flags"] = out["ch6_8_readiness_context_flags"].fillna("CH6_8_READINESS_CONTEXT_MISSING_REVIEW_REQUIRED")
    out["ch6_8_readiness_status_observed"] = out["ch6_8_readiness_status_observed"].fillna("CH6_8_READINESS_CONTEXT_MISSING_REVIEW_REQUIRED")

    out["readiness_review_gate_flags"] = out.apply(activity_review_flags, axis=1)
    out["readiness_review_gate_status"] = out["readiness_review_gate_flags"].apply(gate_status_from_flags)
    out["method_note"] = METHOD_NOTE
    out["interpretation_boundary"] = BOUNDARY_TEXT

    return out.sort_values("activity_id_short").reset_index(drop=True)


def build_gate_table(activity_summary: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    if activity_summary.empty:
        return pd.DataFrame()

    keep_cols = [
        "profile_id",
        "route_folder",
        "activity_id_short",
        "readiness_review_gate_status",
        "readiness_review_gate_flags",
        "windows_n",
        "route_load_context_bands_observed",
        "route_phases_observed",
        "weather_context_classes_observed",
        "high_or_very_high_route_load_ratio",
        "uphill_high_route_load_ratio",
        "route_load_behavior_candidate_window_ratio",
        "conservative_weather_review_required_ratio",
        "behavior_weather_context_review_required_ratio",
        "ch6_8_readiness_join_status",
        "ch6_8_readiness_context_flags",
        "weather_adjustment_flags_observed",
        "conservative_planning_weather_flags_observed",
        "method_note",
        "interpretation_boundary",
    ]
    return activity_summary[[c for c in keep_cols if c in activity_summary.columns]].copy()


def build_window_summary(weather_windows: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    rows = []
    group_cols = [
        "route_load_context_band",
        "route_phase_for_profile",
        "weather_adjustment_context_class",
    ]
    for keys, group in weather_windows.groupby(group_cols, dropna=False):
        row = summarize_activity(group, args)
        for col, value in zip(group_cols, keys):
            row[col] = value
        row["activity_count"] = int(group["activity_id_short"].nunique())
        row["interpretation_boundary"] = BOUNDARY_TEXT
        rows.append(row)
    return pd.DataFrame(rows).sort_values(group_cols).reset_index(drop=True) if rows else pd.DataFrame()


def build_group_summary(activity_summary: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    if activity_summary.empty:
        return pd.DataFrame()

    rows = []
    for status, group in activity_summary.groupby("readiness_review_gate_status", dropna=False):
        rows.append({
            "profile_id": args.profile_id,
            "route_folder": args.route_folder,
            "readiness_review_gate_status": status,
            "activity_count": int(group["activity_id_short"].nunique()),
            "activity_id_short_list": "|".join(sorted(group["activity_id_short"].astype(str).tolist())),
            "windows_n": int(group["windows_n"].sum()),
            "high_or_very_high_route_load_ratio_avg": round(mean(group["high_or_very_high_route_load_ratio"]), 6),
            "uphill_high_route_load_ratio_avg": round(mean(group["uphill_high_route_load_ratio"]), 6),
            "route_load_behavior_candidate_window_ratio_avg": round(mean(group["route_load_behavior_candidate_window_ratio"]), 6),
            "conservative_weather_review_required_ratio_avg": round(mean(group["conservative_weather_review_required_ratio"]), 6),
            "behavior_weather_context_review_required_ratio_avg": round(mean(group["behavior_weather_context_review_required_ratio"]), 6),
            "readiness_review_gate_flags_observed": pipe_flags(group["readiness_review_gate_flags"].astype(str).tolist()),
            "weather_context_classes_observed": pipe_flags(group["weather_context_classes_observed"].astype(str).tolist()),
            "interpretation_boundary": BOUNDARY_TEXT,
        })

    return pd.DataFrame(rows).sort_values("readiness_review_gate_status").reset_index(drop=True)


def build_data_quality(
    source_inventory: pd.DataFrame,
    ch6_5_1_windows: pd.DataFrame,
    weather_windows: pd.DataFrame,
    activity_summary: pd.DataFrame,
    readiness_join_mode: str,
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
        "check_name": "ch6_5_1_windows_present",
        "check_status": "PASS" if len(ch6_5_1_windows) > 0 else "REVIEW_REQUIRED_CH6_5_1_WINDOWS_MISSING",
        "check_value": int(len(ch6_5_1_windows)),
        "details": "CH6.5.1 behavior windows available",
    })

    rows.append({
        "profile_id": args.profile_id,
        "route_folder": args.route_folder,
        "check_name": "ch6_5_2_weather_windows_present",
        "check_status": "PASS" if len(weather_windows) > 0 else "REVIEW_REQUIRED_CH6_5_2_WINDOWS_MISSING",
        "check_value": int(len(weather_windows)),
        "details": "CH6.5.2 weather windows available",
    })

    same_window_count = len(ch6_5_1_windows) == len(weather_windows)
    rows.append({
        "profile_id": args.profile_id,
        "route_folder": args.route_folder,
        "check_name": "ch6_5_1_ch6_5_2_window_count_match",
        "check_status": "PASS" if same_window_count else "REVIEW_REQUIRED_WINDOW_COUNT_MISMATCH",
        "check_value": int(len(weather_windows) - len(ch6_5_1_windows)),
        "details": f"ch6_5_1={len(ch6_5_1_windows)};ch6_5_2={len(weather_windows)}",
    })

    readiness_missing_n = int(activity_summary["ch6_8_readiness_join_status"].eq("READINESS_NOT_JOINED").sum()) if not activity_summary.empty else 0
    rows.append({
        "profile_id": args.profile_id,
        "route_folder": args.route_folder,
        "check_name": "ch6_8_readiness_activity_join",
        "check_status": "PASS" if readiness_missing_n == 0 and readiness_join_mode == "READINESS_JOINABLE_BY_ACTIVITY" else "REVIEW_REQUIRED_READINESS_JOIN",
        "check_value": readiness_missing_n,
        "details": readiness_join_mode,
    })

    rows.append({
        "profile_id": args.profile_id,
        "route_folder": args.route_folder,
        "check_name": "activity_summary_rows_present",
        "check_status": "PASS" if len(activity_summary) > 0 else "REVIEW_REQUIRED_NO_ACTIVITY_SUMMARY",
        "check_value": int(len(activity_summary)),
        "details": "per-activity review gate rows generated",
    })

    rows.append({
        "profile_id": args.profile_id,
        "route_folder": args.route_folder,
        "check_name": "weather_zero_fill_absent",
        "check_status": "PASS",
        "check_value": 1,
        "details": "weather values are consumed from CH6.5.2; missing weather remains CH6.5.2 responsibility and is not zero-filled here",
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
        "details": "interpretation_boundary field generated in outputs",
    })

    return pd.DataFrame(rows)


def audit_conclusion(data_quality: pd.DataFrame) -> str:
    statuses = data_quality["check_status"].astype(str).tolist()
    if any(s.startswith("FAIL") for s in statuses):
        return "REVIEW_REQUIRED_CH6_5_3_ROUTE_LOAD_PERSONAL_PERFORMANCE_READINESS_GATE_V1"
    if any(s.startswith("REVIEW_REQUIRED") for s in statuses):
        return "REVIEW_REQUIRED_CH6_5_3_ROUTE_LOAD_PERSONAL_PERFORMANCE_READINESS_GATE_V1"
    return "PASS_CH6_5_3_ROUTE_LOAD_PERSONAL_PERFORMANCE_READINESS_GATE_V1_DESCRIPTIVE_ONLY"


def write_run_report(
    path: Path,
    source_inventory: pd.DataFrame,
    activity_summary: pd.DataFrame,
    gate_table: pd.DataFrame,
    group_summary: pd.DataFrame,
    window_summary: pd.DataFrame,
    data_quality: pd.DataFrame,
    conclusion: str,
    args: argparse.Namespace,
) -> None:
    lines = [
        "# CH6.5.3 Route-Load × Personal-Performance Readiness Review Gate v1",
        "",
        f"- profile_id: `{args.profile_id}`",
        f"- route_folder: `{args.route_folder}`",
        f"- activity_summary_rows: `{len(activity_summary)}`",
        f"- gate_rows: `{len(gate_table)}`",
        f"- group_summary_rows: `{len(group_summary)}`",
        f"- window_summary_rows: `{len(window_summary)}`",
        f"- audit_conclusion: `{conclusion}`",
        "",
        "## Method",
        "",
        "- Fuses CH6.5.1 behavior windows, CH6.5.2 weather-context windows, and CH6.8 readiness review.",
        "- Generates descriptive per-activity review-gate flags.",
        "- Does not create numeric readiness score, suitability score, final risk score, or go/no-go decision.",
        "",
        "## Sources",
        "",
    ]

    for _, row in source_inventory.iterrows():
        lines.append(f"- {row['source_label']}: `{row['source_path']}` exists={row['exists']} bytes={row['length_bytes']}")

    lines.extend([
        "",
        "## Review gate distribution",
        "",
    ])
    if not group_summary.empty:
        for _, row in group_summary.iterrows():
            lines.append(
                f"- {row['readiness_review_gate_status']}: "
                f"activities={row['activity_count']}; windows={row['windows_n']}"
            )

    lines.extend([
        "",
        "## Data quality",
        "",
    ])
    for _, row in data_quality.iterrows():
        lines.append(f"- {row['check_name']}: {row['check_status']} ({row['details']})")

    lines.extend([
        "",
        "## Boundary",
        "",
        BOUNDARY_TEXT,
        "",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    out_root = resolve(root, args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)

    paths = {
        "ch6_5_1_behavior_windows": resolve(root, args.ch6_5_1_windows),
        "ch6_5_2_weather_windows": resolve(root, args.ch6_5_2_windows),
        "ch6_8_readiness_review": resolve(root, args.ch6_8_readiness),
        "ch6_8_readiness_audit": resolve(root, args.ch6_8_audit),
    }
    source_inventory = build_source_inventory(paths)

    ch6_5_1_windows = read_csv(paths["ch6_5_1_behavior_windows"], "CH6.5.1 behavior windows", required=True)
    ch6_5_2_weather_windows_raw = read_csv(paths["ch6_5_2_weather_windows"], "CH6.5.2 weather windows", required=True)
    ch6_8_readiness = read_csv(paths["ch6_8_readiness_review"], "CH6.8 readiness review", required=False)
    _ch6_8_audit = read_csv(paths["ch6_8_readiness_audit"], "CH6.8 readiness audit", required=False)

    weather_windows = prepare_weather_windows(ch6_5_2_weather_windows_raw, args)
    readiness_context, _readiness_join_ratio, readiness_join_mode = build_readiness_context(
        ch6_8_readiness,
        args.profile_id,
        args.route_folder,
    )

    activity_summary = build_activity_summary(weather_windows, readiness_context, args)
    gate_table = build_gate_table(activity_summary, args)
    group_summary = build_group_summary(activity_summary, args)
    window_summary = build_window_summary(weather_windows, args)

    output_paths = {
        "gate": out_root / "route_load_personal_performance_readiness_gate_v1.csv",
        "activity_summary": out_root / "route_load_personal_performance_context_activity_summary_v1.csv",
        "group_summary": out_root / "route_load_personal_performance_context_group_summary_v1.csv",
        "window_summary": out_root / "route_load_personal_performance_context_window_summary_v1.csv",
        "data_quality": out_root / "route_load_personal_performance_readiness_gate_data_quality_v1.csv",
        "audit": out_root / "route_load_personal_performance_readiness_gate_audit_v1.csv",
        "run_report": out_root / "route_load_personal_performance_readiness_gate_run_report_v1.md",
    }

    output_fields = {
        "gate": list(gate_table.columns),
        "activity_summary": list(activity_summary.columns),
        "group_summary": list(group_summary.columns),
        "window_summary": list(window_summary.columns),
    }
    data_quality = build_data_quality(
        source_inventory,
        ch6_5_1_windows,
        weather_windows,
        activity_summary,
        readiness_join_mode,
        output_fields,
        args,
    )
    conclusion = audit_conclusion(data_quality)

    audit = pd.DataFrame([{
        "profile_id": args.profile_id,
        "route_folder": args.route_folder,
        "activity_count": int(activity_summary["activity_id_short"].nunique()) if not activity_summary.empty else 0,
        "gate_rows": int(len(gate_table)),
        "activity_summary_rows": int(len(activity_summary)),
        "group_summary_rows": int(len(group_summary)),
        "window_summary_rows": int(len(window_summary)),
        "weather_context_available_activity_ratio_avg": round(mean(activity_summary.get("weather_context_available_ratio", pd.Series(dtype=float))), 6) if not activity_summary.empty else np.nan,
        "conservative_weather_review_required_activity_ratio_avg": round(mean(activity_summary.get("conservative_weather_review_required_ratio", pd.Series(dtype=float))), 6) if not activity_summary.empty else np.nan,
        "behavior_weather_context_review_required_activity_ratio_avg": round(mean(activity_summary.get("behavior_weather_context_review_required_ratio", pd.Series(dtype=float))), 6) if not activity_summary.empty else np.nan,
        "source_files_available_n": int(source_inventory["exists"].sum()),
        "source_files_expected_n": int(len(source_inventory)),
        "audit_conclusion": conclusion,
        "interpretation_boundary": BOUNDARY_TEXT,
    }])

    gate_table.to_csv(output_paths["gate"], index=False, encoding="utf-8-sig")
    activity_summary.to_csv(output_paths["activity_summary"], index=False, encoding="utf-8-sig")
    group_summary.to_csv(output_paths["group_summary"], index=False, encoding="utf-8-sig")
    window_summary.to_csv(output_paths["window_summary"], index=False, encoding="utf-8-sig")
    data_quality.to_csv(output_paths["data_quality"], index=False, encoding="utf-8-sig")
    audit.to_csv(output_paths["audit"], index=False, encoding="utf-8-sig")
    write_run_report(
        output_paths["run_report"],
        source_inventory,
        activity_summary,
        gate_table,
        group_summary,
        window_summary,
        data_quality,
        conclusion,
        args,
    )

    print({
        "output_root": str(out_root),
        "profile_id": args.profile_id,
        "activity_count": int(activity_summary["activity_id_short"].nunique()) if not activity_summary.empty else 0,
        "gate_rows": int(len(gate_table)),
        "activity_summary_rows": int(len(activity_summary)),
        "group_summary_rows": int(len(group_summary)),
        "window_summary_rows": int(len(window_summary)),
        "source_files_available_n": int(source_inventory["exists"].sum()),
        "source_files_expected_n": int(len(source_inventory)),
        "audit_conclusion": conclusion,
        "outputs": {k: str(v) for k, v in output_paths.items()},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
