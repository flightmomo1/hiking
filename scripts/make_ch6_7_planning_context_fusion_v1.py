#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build Chapter 6.7 planning context fusion v1 evidence tables.

This script fuses existing descriptive evidence for Chapter 6.7 planning
context. It does not create ability, suitability, THCI, radar, or final-risk
scores. Route-load context remains route/terrain/map-derived; behavior,
weather, and event annotations are context evidence only.
"""

from __future__ import annotations

import argparse
import glob
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


DEFAULT_ROUTE_LOAD_WINDOWS = (
    "outputs/report_figures/ch6_5_route_load_context_index_v1/"
    "route_load_context_windows_v1.csv"
)
DEFAULT_ROUTE_LOAD_CANDIDATES = (
    "outputs/report_figures/ch6_5_route_load_context_index_v1/"
    "route_load_behavior_response_candidate_windows_v1.csv"
)
DEFAULT_ROUTE_LOAD_ACTIVITY_SUMMARY = (
    "outputs/report_figures/ch6_5_route_load_context_index_v1/"
    "route_load_context_activity_summary_v1.csv"
)
DEFAULT_IB2_ROUTE_RISK = (
    "outputs/ib2_v2_route_risk_v1_3b_contract_qa/"
    "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b/"
    "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b_route_risk_v2.csv"
)
DEFAULT_WEATHER_PROFILE = (
    "outputs/ib3w_codis_weather_profile_report_v1/"
    "activity_weather_profile_report_table.csv"
)
DEFAULT_WEATHER_PERFORMANCE_JOIN = (
    "outputs/ib3w_activity_weather_performance_join_v1/"
    "activity_weather_performance_join.csv"
)
DEFAULT_EVENT_OVERLAY_GLOB = (
    "outputs/report_figures/ch6_5_ib3d_event_route_window_bridge_v1/"
    "activity_*_ib3d_event_route_window_overlay.csv"
)
DEFAULT_OUTPUT_ROOT = "outputs/report_figures/ch6_7_planning_context_fusion_v1"

WINDOW_M = 50

FORBIDDEN_OUTPUT_COLUMNS = (
    "ability_score",
    "ability_rank",
    "ability_class",
    "thci_score",
    "radar_score",
    "final_hiking_risk_score",
    "route_suitability_score",
    "personal_fitness_score",
)

ROUTINE = "ROUTINE_PLANNING_CONTEXT"
REVIEW = "REVIEW_FOR_CONSERVATIVE_PLANNING"
CONSERVATIVE = "CONSERVATIVE_PLANNING_RECOMMENDED"
TURNAROUND = "TURNAROUND_CONDITION_REVIEW_RECOMMENDED"

BOUNDARY = (
    "Descriptive planning context evidence only. This is not ability scoring, "
    "not route suitability scoring, not THCI/radar scoring, and not a final "
    "hiking risk assessment. Weather is activity-level context unless an "
    "explicit safe route-window source is used. OSM proximity is not proof of "
    "facility use. IB3D/event annotations are not causality evidence."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=r"D:\mountain_work\115_osm")
    parser.add_argument("--route-load-windows", default=DEFAULT_ROUTE_LOAD_WINDOWS)
    parser.add_argument("--route-load-candidates", default=DEFAULT_ROUTE_LOAD_CANDIDATES)
    parser.add_argument("--route-load-activity-summary", default=DEFAULT_ROUTE_LOAD_ACTIVITY_SUMMARY)
    parser.add_argument("--ib2-route-risk", default=DEFAULT_IB2_ROUTE_RISK)
    parser.add_argument("--weather-profile", default=DEFAULT_WEATHER_PROFILE)
    parser.add_argument("--weather-performance-join", default=DEFAULT_WEATHER_PERFORMANCE_JOIN)
    parser.add_argument("--event-overlay-glob", default=DEFAULT_EVENT_OVERLAY_GLOB)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
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


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def pipe_flags(flags: Iterable[str]) -> str:
    out = []
    for flag in flags:
        if flag is None:
            continue
        text = str(flag).strip()
        if text and text.upper() != "NONE" and text.lower() != "nan":
            out.append(text)
    unique = list(dict.fromkeys(out))
    return "|".join(unique) if unique else "NONE"


def split_flags(value: object) -> list[str]:
    if pd.isna(value):
        return []
    text = str(value).strip()
    if not text or text.upper() == "NONE":
        return []
    return [part.strip() for part in text.split("|") if part.strip()]


def mode_text(series: pd.Series) -> str:
    clean = series.dropna().astype(str)
    clean = clean[clean.str.strip().ne("")]
    if clean.empty:
        return ""
    return str(clean.mode().iloc[0])


def boolish(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(["true", "1", "yes", "y"])


def normalize_activity_short(value: object) -> str:
    text = "" if pd.isna(value) else str(value).strip()
    if not text:
        return ""
    parts = text.split("_")
    if len(parts) >= 2 and parts[-1].isdigit() and parts[-2].isdigit():
        return f"{parts[-2]}_{parts[-1]}"
    return text


def route_load_flags(row: pd.Series) -> str:
    flags: list[str] = []
    band = str(row.get("route_load_context_band", ""))
    if band == "HIGH_ROUTE_LOAD_CONTEXT":
        flags.append("ROUTE_LOAD_HIGH_CONTEXT")
    elif band == "VERY_HIGH_ROUTE_LOAD_CONTEXT":
        flags.extend(["ROUTE_LOAD_HIGH_CONTEXT", "ROUTE_LOAD_VERY_HIGH_CONTEXT"])
    for flag in split_flags(row.get("route_load_context_reason_flags", "")):
        flags.append(flag)
    return pipe_flags(flags)


def behavior_planning_flags(value: object) -> str:
    mapped: list[str] = []
    for flag in split_flags(value):
        if flag == "SPEED_BELOW_LOW_SPEED_THRESHOLD":
            mapped.append("BEHAVIOR_LOW_SPEED_RESPONSE")
        elif flag == "STOP_RATIO_OBSERVED":
            mapped.append("BEHAVIOR_STOP_RESPONSE")
        elif flag == "ACTIVITY_RELATIVE_HIGH_HR_WINDOW":
            mapped.append("BEHAVIOR_RELATIVE_HIGH_HR_RESPONSE")
        elif flag == "LOW_SPEED_RATIO_HIGH":
            mapped.append("BEHAVIOR_LOW_SPEED_RATIO_HIGH")
        elif flag == "HR_MISSING":
            mapped.append("HR_MISSING_QA_ONLY")
    return pipe_flags(mapped)


def weather_flags(row: pd.Series) -> str:
    flags = ["WEATHER_ACTIVITY_LEVEL_ONLY"]
    env_flags = split_flags(row.get("environment_context_flags", ""))
    if not env_flags:
        env_flags = split_flags(row.get("weather_context_flags", ""))
    if not env_flags:
        flags.append("WEATHER_CONTEXT_MISSING")
    for flag in env_flags:
        upper = flag.upper()
        if "HIGH_HUMIDITY" in upper:
            flags.append("WEATHER_HUMID_CONTEXT")
        if "RAIN_OBSERVED" in upper:
            flags.append("WEATHER_RAIN_CONTEXT")
        if "GUST" in upper or "WIND" in upper:
            flags.append("WEATHER_WIND_GUST_CONTEXT")
        if "HIGH_UV" in upper:
            flags.append("WEATHER_HIGH_UV_CONTEXT")
        if "HEAT" in upper:
            flags.append("WEATHER_HEAT_CONTEXT")
        if "MISSING" in upper:
            flags.append("WEATHER_CONTEXT_MISSING")
    return pipe_flags(flags)


def aggregate_ib2_route_risk(ib2: pd.DataFrame) -> pd.DataFrame:
    if "dist_m" not in ib2.columns:
        raise KeyError("IB2 route risk CSV must contain dist_m.")
    work = ib2.copy()
    work["dist_m"] = numeric(work["dist_m"])
    work = work[work["dist_m"].notna()].copy()
    work["route_distance_window_start_m"] = (np.floor(work["dist_m"] / WINDOW_M) * WINDOW_M).astype(int)
    work["route_distance_window_end_m"] = work["route_distance_window_start_m"] + WINDOW_M

    def any_flag(col: str, group: pd.DataFrame) -> bool:
        if col not in group.columns:
            return False
        return bool(boolish(group[col]).any())

    rows = []
    for (start, end), group in work.groupby(["route_distance_window_start_m", "route_distance_window_end_m"]):
        risk_band = mode_text(group["risk_band"]) if "risk_band" in group.columns else ""
        terrain = numeric(group["terrain_score"]).median() if "terrain_score" in group.columns else np.nan
        effort = numeric(group["effort_score"]).median() if "effort_score" in group.columns else np.nan
        exposure = numeric(group["exposure_score"]).median() if "exposure_score" in group.columns else np.nan
        support_flags = "|".join(sorted(set("|".join(group.get("support_flags", pd.Series(dtype=str)).fillna("").astype(str)).split("|")) - {""}))
        weather_sensitive = "|".join(sorted(set("|".join(group.get("weather_sensitive_flags", pd.Series(dtype=str)).fillna("").astype(str)).split("|")) - {""}))
        navigation_flags = []
        if "navigation_risk_score" in group.columns and numeric(group["navigation_risk_score"]).fillna(0).max() > 0:
            navigation_flags.append("NAVIGATION_RISK_CONTEXT")
        if "navigation_support_score" in group.columns and numeric(group["navigation_support_score"]).fillna(0).min() < 0:
            navigation_flags.append("NAVIGATION_SUPPORT_GAP_CONTEXT")

        route_flags = []
        if risk_band.lower() in {"high", "very_high", "very high"}:
            route_flags.append("IB2_ROUTE_RISK_HIGH_CONTEXT")
        if pd.notna(terrain) and terrain >= 0.75:
            route_flags.append("IB2_TERRAIN_CONTEXT_HIGH")
        if pd.notna(exposure) and exposure >= 0.5:
            route_flags.append("IB2_EXPOSURE_CONTEXT")
        if support_flags and support_flags != "none":
            route_flags.append("IB2_SUPPORT_CONTEXT")
        if navigation_flags:
            route_flags.append("IB2_NAVIGATION_CONTEXT")
        if weather_sensitive and weather_sensitive != "none":
            route_flags.append("IB2_WEATHER_SENSITIVE_ROUTE_EXPOSURE_CONTEXT")
        if any_flag("near_waterway", group):
            route_flags.append("WATERWAY_PROXIMITY_CONTEXT")
        if any_flag("near_shelter", group):
            route_flags.append("SHELTER_PROXIMITY_CONTEXT")
        if any_flag("near_guidepost", group):
            route_flags.append("GUIDEPOST_PROXIMITY_CONTEXT")

        rows.append(
            {
                "route_distance_window_start_m": int(start),
                "route_distance_window_end_m": int(end),
                "ib2_route_point_count": int(len(group)),
                "ib2_route_risk_context_band": risk_band.upper() if risk_band else "",
                "ib2_terrain_score_median": terrain,
                "ib2_effort_score_median": effort,
                "ib2_exposure_score_median": exposure,
                "ib2_support_flags": support_flags if support_flags else "NONE",
                "ib2_weather_sensitive_route_exposure_flags": weather_sensitive if weather_sensitive else "NONE",
                "ib2_route_context_flags": pipe_flags(route_flags),
                "surface_class_mode": mode_text(group["surface_class"]) if "surface_class" in group.columns else "",
                "route_semantic_class_mode": mode_text(group["route_semantic_class"]) if "route_semantic_class" in group.columns else "",
            }
        )
    return pd.DataFrame(rows)


def load_weather_activity(root: Path, profile_path: Path, performance_path: Path) -> pd.DataFrame:
    frames = []
    if profile_path.exists():
        profile = read_csv(profile_path, "weather profile")
        profile["activity_id_short"] = profile.get("activity_id_short", profile.get("activity_id", "")).apply(normalize_activity_short)
        profile = profile.add_prefix("weather_profile_")
        profile = profile.rename(columns={"weather_profile_activity_id_short": "activity_id_short"})
        frames.append(profile)
    if performance_path.exists():
        perf = read_csv(performance_path, "weather performance join")
        perf["activity_id_short"] = perf.get("activity_id_short", perf.get("activity_id_full", "")).apply(normalize_activity_short)
        keep = [
            "activity_id_short",
            "join_status",
            "weather_join_performed",
            "descriptive_context_note",
            "authorization_note",
        ]
        keep = [col for col in keep if col in perf.columns]
        perf = perf[keep].add_prefix("weather_join_")
        perf = perf.rename(columns={"weather_join_activity_id_short": "activity_id_short"})
        frames.append(perf)
    if not frames:
        return pd.DataFrame(columns=["activity_id_short"])
    out = frames[0]
    for frame in frames[1:]:
        out = out.merge(frame, on="activity_id_short", how="outer")
    return out


def load_event_overlays(root: Path, pattern: str) -> pd.DataFrame:
    full_pattern = str(resolve(root, pattern))
    files = sorted(glob.glob(full_pattern))
    frames = []
    for file in files:
        df = pd.read_csv(file, encoding="utf-8-sig")
        df.columns = [str(col).strip() for col in df.columns]
        if "activity_id_short" not in df.columns:
            continue
        frames.append(df)
    if not frames:
        return pd.DataFrame(
            columns=[
                "activity_id_short",
                "route_distance_window_start_m",
                "route_distance_window_end_m",
                "event_annotation_flags",
                "event_annotation_types",
                "event_annotation_boundary",
                "terminal_artifact_review_flag",
            ]
        )
    overlay = pd.concat(frames, ignore_index=True)
    for col in [
        "route_distance_window_start_m",
        "route_distance_window_end_m",
        "high_hr_recovery_stop_count",
        "short_pause_count",
        "off_route_rest_ratio",
        "terminal_artifact_ratio",
    ]:
        if col in overlay.columns:
            overlay[col] = numeric(overlay[col])

    records = []
    valid_status = {"ROUTE_WINDOW_OVERLAY_READY", "ROUTE_WINDOW_OVERLAY_READY_WITH_EVENT_REVIEW"}
    for _, row in overlay.iterrows():
        flags: list[str] = []
        types: list[str] = []
        status = str(row.get("event_overlay_status", ""))
        if status not in valid_status:
            continue
        if row.get("high_hr_recovery_stop_count", 0) > 0:
            flags.append("EVENT_HIGH_HR_RECOVERY_STOP")
            types.append("high_hr_recovery_stop")
        if row.get("short_pause_count", 0) > 0:
            flags.append("EVENT_SHORT_PAUSE")
            types.append("short_pause")
        if row.get("off_route_rest_ratio", 0) > 0:
            flags.append("EVENT_OFF_ROUTE_REST")
            types.append("off_route_rest")
        terminal_review = bool(row.get("terminal_artifact_ratio", 0) > 0)
        if terminal_review:
            flags.append("TERMINAL_ARTIFACT_REVIEW_ONLY")
            types.append("terminal_artifact_review_only")
        if status == "ROUTE_WINDOW_OVERLAY_READY_WITH_EVENT_REVIEW":
            flags.append("EVENT_REVIEW_REQUIRED")

        records.append(
            {
                "activity_id_short": str(row["activity_id_short"]),
                "route_distance_window_start_m": int(row["route_window_start_m"] if "route_window_start_m" in row else row["route_distance_window_start_m"]),
                "route_distance_window_end_m": int(row["route_window_end_m"] if "route_window_end_m" in row else row["route_distance_window_end_m"]),
                "event_annotation_flags": pipe_flags(flags),
                "event_annotation_types": pipe_flags(types),
                "event_annotation_boundary": (
                    "IB3D event annotation is route-window evidence bridged from elapsed-time intervals. "
                    "It is annotation only, not route-load evidence, not causality, and not used to compute planning caution level."
                ),
                "terminal_artifact_review_flag": terminal_review,
            }
        )
    if not records:
        return pd.DataFrame()
    out = pd.DataFrame(records)
    # One row per activity/window, merging duplicate overlay files if any.
    grouped = []
    for keys, group in out.groupby(["activity_id_short", "route_distance_window_start_m", "route_distance_window_end_m"]):
        grouped.append(
            {
                "activity_id_short": keys[0],
                "route_distance_window_start_m": keys[1],
                "route_distance_window_end_m": keys[2],
                "event_annotation_flags": pipe_flags(flag for value in group["event_annotation_flags"] for flag in split_flags(value)),
                "event_annotation_types": pipe_flags(flag for value in group["event_annotation_types"] for flag in split_flags(value)),
                "event_annotation_boundary": group["event_annotation_boundary"].iloc[0],
                "terminal_artifact_review_flag": bool(group["terminal_artifact_review_flag"].any()),
            }
        )
    return pd.DataFrame(grouped)


def caution_level(row: pd.Series) -> tuple[str, str]:
    route_band = str(row.get("route_load_context_band", ""))
    is_candidate = bool(row.get("is_route_load_behavior_candidate", False))
    flags = split_flags(row.get("planning_context_flags", ""))
    ib2_weather_or_support = any(
        flag in flags
        for flag in [
            "IB2_SUPPORT_CONTEXT",
            "IB2_SUPPORT_GAP_CONTEXT",
            "IB2_NAVIGATION_CONTEXT",
            "IB2_EXPOSURE_CONTEXT",
            "IB2_WEATHER_SENSITIVE_ROUTE_EXPOSURE_CONTEXT",
            "WEATHER_RAIN_CONTEXT",
            "WEATHER_WIND_GUST_CONTEXT",
            "WEATHER_HIGH_UV_CONTEXT",
            "WEATHER_HUMID_CONTEXT",
            "WATERWAY_PROXIMITY_CONTEXT",
        ]
    )
    reasons: list[str] = []
    if route_band == "VERY_HIGH_ROUTE_LOAD_CONTEXT" and is_candidate and ib2_weather_or_support:
        reasons.extend(["VERY_HIGH_ROUTE_LOAD_CONTEXT", "ROUTE_LOAD_BEHAVIOR_CANDIDATE", "IB2_OR_WEATHER_CONTEXT_PRESENT"])
        return TURNAROUND, pipe_flags(reasons)
    if route_band == "VERY_HIGH_ROUTE_LOAD_CONTEXT" or is_candidate or (
        route_band == "HIGH_ROUTE_LOAD_CONTEXT" and ib2_weather_or_support
    ):
        if route_band == "VERY_HIGH_ROUTE_LOAD_CONTEXT":
            reasons.append("VERY_HIGH_ROUTE_LOAD_CONTEXT")
        if is_candidate:
            reasons.append("ROUTE_LOAD_BEHAVIOR_CANDIDATE")
        if ib2_weather_or_support:
            reasons.append("IB2_OR_WEATHER_CONTEXT_PRESENT")
        return CONSERVATIVE, pipe_flags(reasons)
    if route_band == "HIGH_ROUTE_LOAD_CONTEXT" or any(flag.startswith("IB2_") for flag in flags):
        reasons.append("HIGH_ROUTE_OR_IB2_CONTEXT")
        return REVIEW, pipe_flags(reasons)
    return ROUTINE, "NONE"


def build_route_windows(
    windows: pd.DataFrame,
    candidates: pd.DataFrame,
    ib2_agg: pd.DataFrame,
    weather_activity: pd.DataFrame,
    events: pd.DataFrame,
) -> pd.DataFrame:
    out = windows.copy()
    key = ["activity_id_short", "route_distance_window_start_m", "route_distance_window_end_m"]
    out["activity_id_short"] = out["activity_id_short"].astype(str)
    for col in ["route_distance_window_start_m", "route_distance_window_end_m"]:
        out[col] = numeric(out[col]).astype(int)

    cand = candidates[key + ["candidate_window_label", "candidate_window_boundary"]].copy()
    cand["is_route_load_behavior_candidate"] = True
    out = out.merge(cand, on=key, how="left")
    out["is_route_load_behavior_candidate"] = out["is_route_load_behavior_candidate"].fillna(False).astype(bool)
    out["candidate_window_label"] = out["candidate_window_label"].fillna("")
    out["candidate_window_boundary"] = out["candidate_window_boundary"].fillna("")

    out = out.merge(
        ib2_agg,
        on=["route_distance_window_start_m", "route_distance_window_end_m"],
        how="left",
    )
    out = out.merge(weather_activity, on="activity_id_short", how="left")
    if not events.empty:
        out = out.merge(events, on=key, how="left")
    else:
        out["event_annotation_flags"] = "NONE"
        out["event_annotation_types"] = "NONE"
        out["event_annotation_boundary"] = ""
        out["terminal_artifact_review_flag"] = False

    out["event_annotation_flags"] = out.get("event_annotation_flags", "NONE").fillna("NONE")
    out["event_annotation_types"] = out.get("event_annotation_types", "NONE").fillna("NONE")
    out["terminal_artifact_review_flag"] = out.get("terminal_artifact_review_flag", False).fillna(False).astype(bool)

    out["route_load_evidence_flags"] = out.apply(route_load_flags, axis=1)
    out["behavior_response_planning_flags"] = out["behavior_response_flags"].apply(behavior_planning_flags)
    out["weather_attach_level"] = "WEATHER_ACTIVITY_LEVEL_ONLY"
    out["weather_planning_context_flags"] = out.apply(weather_flags, axis=1)
    out["weather_context_available_for_planning"] = out["weather_planning_context_flags"].str.contains("WEATHER_CONTEXT_MISSING") == False

    out["route_load_evidence_boundary"] = (
        "Route-load context is route/terrain/map-derived evidence only; not ability score and not final risk."
    )
    out["weather_context_boundary"] = (
        "Weather context is attached as activity-level background unless explicitly safe route-window evidence exists; no zero-fill."
    )
    out["planning_context_flags"] = out.apply(
        lambda row: pipe_flags(
            split_flags(row.get("route_load_evidence_flags", ""))
            + split_flags(row.get("ib2_route_context_flags", ""))
            + split_flags(row.get("weather_planning_context_flags", ""))
            + split_flags(row.get("behavior_response_planning_flags", ""))
            + ["ROUTE_PHASE_UNKNOWN" if str(row.get("route_phase", "")).upper() == "UNKNOWN" else ""]
            + ["OSM_PROXIMITY_NOT_USAGE"]
        ),
        axis=1,
    )
    levels = out.apply(caution_level, axis=1)
    out["planning_caution_level"] = [item[0] for item in levels]
    out["planning_caution_reason_flags"] = [item[1] for item in levels]
    out["planning_caution_boundary"] = (
        "Planning caution level is a descriptive enum for planning review only; it is not a numeric score, "
        "not suitability scoring, and not final hiking risk."
    )
    out["planning_context_boundary"] = BOUNDARY

    # Keep columns explicit and avoid accidental forbidden score columns.
    preferred = [
        "activity_id_short",
        "activity_id_full",
        "route_distance_window_start_m",
        "route_distance_window_end_m",
        "route_phase",
        "point_count",
        "route_load_context_index_0_100",
        "route_load_context_band",
        "route_load_context_reason_flags",
        "route_load_evidence_flags",
        "ib2_route_context_flags",
        "ib2_route_risk_context_band",
        "ib2_terrain_score_median",
        "ib2_effort_score_median",
        "ib2_exposure_score_median",
        "ib2_support_flags",
        "ib2_weather_sensitive_route_exposure_flags",
        "surface_class_mode",
        "route_semantic_class_mode",
        "weather_attach_level",
        "weather_context_available_for_planning",
        "weather_planning_context_flags",
        "weather_context_boundary",
        "environment_context_flags",
        "temperature_c",
        "relative_humidity_pct",
        "precipitation_mm",
        "wind_speed_ms",
        "wind_gust_ms",
        "uv_index",
        "behavior_response_flags",
        "behavior_response_planning_flags",
        "behavior_response_signal_flag_count",
        "is_route_load_behavior_candidate",
        "candidate_window_label",
        "candidate_window_boundary",
        "event_annotation_flags",
        "event_annotation_types",
        "event_annotation_boundary",
        "terminal_artifact_review_flag",
        "planning_context_flags",
        "planning_caution_level",
        "planning_caution_reason_flags",
        "planning_caution_boundary",
        "window_qa_flags",
        "route_load_evidence_boundary",
        "planning_context_boundary",
    ]
    return out[[col for col in preferred if col in out.columns]].copy()


def build_segments(route_windows: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for activity_id, group in route_windows.sort_values(
        ["activity_id_short", "route_distance_window_start_m"]
    ).groupby("activity_id_short"):
        current = None
        for _, row in group.iterrows():
            level = str(row["planning_caution_level"])
            start = int(row["route_distance_window_start_m"])
            end = int(row["route_distance_window_end_m"])
            if current is None or level != current["dominant_planning_caution_level"] or start != current["segment_end_m"]:
                if current is not None:
                    rows.append(current)
                current = {
                    "activity_id_short": activity_id,
                    "segment_start_m": start,
                    "segment_end_m": end,
                    "segment_window_count": 1,
                    "dominant_planning_caution_level": level,
                    "_indices": [row.name],
                }
            else:
                current["segment_end_m"] = end
                current["segment_window_count"] += 1
                current["_indices"].append(row.name)
        if current is not None:
            rows.append(current)

    segs = []
    for item in rows:
        sub = route_windows.loc[item.pop("_indices")]
        segs.append(
            {
                **item,
                "max_route_load_context_index_0_100": numeric(sub["route_load_context_index_0_100"]).max(),
                "dominant_route_load_context_band": mode_text(sub["route_load_context_band"]),
                "route_load_evidence_flags_merged": pipe_flags(flag for value in sub["route_load_evidence_flags"] for flag in split_flags(value)),
                "weather_planning_context_flags_merged": pipe_flags(flag for value in sub["weather_planning_context_flags"] for flag in split_flags(value)),
                "behavior_response_planning_flags_merged": pipe_flags(flag for value in sub["behavior_response_planning_flags"] for flag in split_flags(value)),
                "event_annotation_flags_merged": pipe_flags(flag for value in sub["event_annotation_flags"] for flag in split_flags(value)),
                "planning_context_flags_merged": pipe_flags(flag for value in sub["planning_context_flags"] for flag in split_flags(value)),
                "planning_caution_reason_flags_merged": pipe_flags(flag for value in sub["planning_caution_reason_flags"] for flag in split_flags(value)),
                "segment_boundary": BOUNDARY,
            }
        )
    return pd.DataFrame(segs)


def build_activity_summary(route_windows: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for activity_id, group in route_windows.groupby("activity_id_short"):
        counts = group["planning_caution_level"].value_counts()
        windows_n = len(group)
        caution_n = int(windows_n - counts.get(ROUTINE, 0))
        rows.append(
            {
                "activity_id_short": activity_id,
                "windows_n": windows_n,
                "candidate_windows_n": int(group["is_route_load_behavior_candidate"].sum()),
                "routine_planning_context_windows_n": int(counts.get(ROUTINE, 0)),
                "review_for_conservative_planning_windows_n": int(counts.get(REVIEW, 0)),
                "conservative_planning_recommended_windows_n": int(counts.get(CONSERVATIVE, 0)),
                "turnaround_condition_review_windows_n": int(counts.get(TURNAROUND, 0)),
                "max_route_load_context_index_0_100": numeric(group["route_load_context_index_0_100"]).max(),
                "median_route_load_context_index_0_100": numeric(group["route_load_context_index_0_100"]).median(),
                "planning_caution_window_ratio": round(caution_n / windows_n, 6) if windows_n else np.nan,
                "turnaround_condition_review_window_ratio": round(counts.get(TURNAROUND, 0) / windows_n, 6) if windows_n else np.nan,
                "weather_attach_level": "WEATHER_ACTIVITY_LEVEL_ONLY",
                "weather_context_available_for_planning": bool(group["weather_context_available_for_planning"].any()),
                "event_annotation_windows_n": int(group["event_annotation_flags"].fillna("NONE").ne("NONE").sum()),
                "summary_boundary": BOUNDARY,
            }
        )
    return pd.DataFrame(rows).sort_values("activity_id_short").reset_index(drop=True)


def build_audit(route_windows: pd.DataFrame, summary: pd.DataFrame, segments: pd.DataFrame, candidates: pd.DataFrame, ib2_agg: pd.DataFrame, event_ann: pd.DataFrame) -> pd.DataFrame:
    generated_cols = set(route_windows.columns) | set(summary.columns) | set(segments.columns)
    forbidden = sorted(col for col in FORBIDDEN_OUTPUT_COLUMNS if col in generated_cols)
    ib2_joined = int(route_windows["ib2_route_context_flags"].notna().sum()) if "ib2_route_context_flags" in route_windows.columns else 0
    weather_attached = int(route_windows["weather_attach_level"].notna().sum()) if "weather_attach_level" in route_windows.columns else 0
    event_joined = int(route_windows["event_annotation_flags"].fillna("NONE").ne("NONE").sum())
    terminal_count = int(route_windows["terminal_artifact_review_flag"].fillna(False).sum())
    conclusion = "PASS_CH6_7_PLANNING_CONTEXT_FUSION_V1_DESCRIPTIVE_ONLY"
    if forbidden:
        conclusion = "REVIEW_REQUIRED_FORBIDDEN_COLUMNS_PRESENT"
    return pd.DataFrame(
        [
            {
                "route_window_row_count": len(route_windows),
                "activity_summary_row_count": len(summary),
                "caution_segment_row_count": len(segments),
                "candidate_join_count": int(route_windows["is_route_load_behavior_candidate"].sum()),
                "input_candidate_row_count": len(candidates),
                "ib2_route_risk_aggregation_rows": len(ib2_agg),
                "ib2_join_coverage": round(ib2_joined / len(route_windows), 6) if len(route_windows) else np.nan,
                "weather_attach_coverage": round(weather_attached / len(route_windows), 6) if len(route_windows) else np.nan,
                "event_annotation_join_coverage": round(event_joined / len(route_windows), 6) if len(route_windows) else np.nan,
                "planning_caution_level_distribution": " | ".join(
                    f"{k}:{v}" for k, v in route_windows["planning_caution_level"].value_counts().sort_index().items()
                ),
                "missing_weather_count": int(route_windows["weather_planning_context_flags"].str.contains("WEATHER_CONTEXT_MISSING", na=False).sum()),
                "terminal_artifact_review_only_count": terminal_count,
                "weather_zero_fill_performed": False,
                "forbidden_output_columns_absent": len(forbidden) == 0,
                "forbidden_output_columns": pipe_flags(forbidden),
                "route_phase_unknown_ascent_descent_comparison_performed": False,
                "audit_conclusion": conclusion,
            }
        ]
    )


def write_report(path: Path, audit: pd.DataFrame, inputs: dict[str, Path], route_windows: pd.DataFrame) -> None:
    dist = route_windows["planning_caution_level"].value_counts().sort_index()
    lines = [
        "# CH6.7 Planning Context Fusion v1 Run Report",
        "",
        "## Inputs",
        "",
    ]
    for name, value in inputs.items():
        lines.append(f"- {name}: `{value}`")
    lines.extend(
        [
            "",
            "## Output Summary",
            "",
        ]
    )
    for field, value in audit.iloc[0].items():
        lines.append(f"- {field}: `{value}`")
    lines.extend(["", "## Planning Caution Level Distribution", ""])
    lines.extend(f"- {k}: {int(v)}" for k, v in dist.items())
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- descriptive planning context evidence only",
            "- not ability scoring",
            "- not route suitability scoring",
            "- not final hiking risk assessment",
            "- not THCI / radar score",
            "- route-load context index remains route/terrain/map-derived",
            "- behavior response is evidence only and does not compute route-load index",
            "- weather is activity-level context unless explicitly window-level and safely joined",
            "- no weather zero-fill",
            "- IB3D/event evidence is annotation only and must not be interpreted as causality",
            "- OSM proximity must not be interpreted as actual facility use",
            "- terminal artifact is review-only and not used for planning caution level",
            "- route_phase UNKNOWN is not used for ascent/descent ability comparison",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    root = Path(args.root)
    output_root = resolve(root, args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    paths = {
        "route_load_windows": resolve(root, args.route_load_windows),
        "route_load_candidates": resolve(root, args.route_load_candidates),
        "route_load_activity_summary": resolve(root, args.route_load_activity_summary),
        "ib2_route_risk": resolve(root, args.ib2_route_risk),
        "weather_profile": resolve(root, args.weather_profile),
        "weather_performance_join": resolve(root, args.weather_performance_join),
        "event_overlay_glob": resolve(root, args.event_overlay_glob),
    }

    windows = read_csv(paths["route_load_windows"], "route-load windows")
    candidates = read_csv(paths["route_load_candidates"], "route-load candidates")
    ib2 = read_csv(paths["ib2_route_risk"], "IB2 route risk", low_memory=False)
    ib2_agg = aggregate_ib2_route_risk(ib2)
    weather_activity = load_weather_activity(root, paths["weather_profile"], paths["weather_performance_join"])
    events = load_event_overlays(root, args.event_overlay_glob)

    route_windows = build_route_windows(windows, candidates, ib2_agg, weather_activity, events)
    segments = build_segments(route_windows)
    summary = build_activity_summary(route_windows)
    audit = build_audit(route_windows, summary, segments, candidates, ib2_agg, events)

    route_windows_csv = output_root / "planning_context_route_windows_v1.csv"
    summary_csv = output_root / "planning_context_activity_summary_v1.csv"
    segments_csv = output_root / "planning_caution_segments_v1.csv"
    audit_csv = output_root / "planning_context_fusion_audit_v1.csv"
    report_md = output_root / "planning_context_fusion_run_report_v1.md"

    route_windows.to_csv(route_windows_csv, index=False, encoding="utf-8-sig")
    summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")
    segments.to_csv(segments_csv, index=False, encoding="utf-8-sig")
    audit.to_csv(audit_csv, index=False, encoding="utf-8-sig")
    write_report(report_md, audit, paths, route_windows)

    result = {
        "script_path": str(Path(__file__).resolve()),
        "output_root": str(output_root),
        "route_window_row_count": int(len(route_windows)),
        "activity_summary_row_count": int(len(summary)),
        "caution_segment_row_count": int(len(segments)),
        "candidate_join_count": int(route_windows["is_route_load_behavior_candidate"].sum()),
        "ib2_join_coverage": float(audit.iloc[0]["ib2_join_coverage"]),
        "weather_attach_coverage": float(audit.iloc[0]["weather_attach_coverage"]),
        "event_annotation_join_coverage": float(audit.iloc[0]["event_annotation_join_coverage"]),
        "planning_caution_level_distribution": str(audit.iloc[0]["planning_caution_level_distribution"]),
        "terminal_artifact_review_only_count": int(audit.iloc[0]["terminal_artifact_review_only_count"]),
        "audit_conclusion": str(audit.iloc[0]["audit_conclusion"]),
        "outputs": [str(route_windows_csv), str(summary_csv), str(segments_csv), str(audit_csv), str(report_md)],
    }
    print(result)


if __name__ == "__main__":
    main()
