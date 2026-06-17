#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Build CH6.7 event-based HR recovery evidence from IB3C phase3c behavior events v1.1.

Boundary:
- Descriptive HR recovery evidence only.
- This script summarizes IB3C behavior events and HR recovery interpretation.
- It is not a cardiopulmonary diagnosis.
- It is not ability scoring, route suitability scoring, THCI/radar scoring,
  or final hiking risk assessment.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

BOUNDARY = (
    "Descriptive IB3C event-based HR recovery evidence only. "
    "HR drop, HR recovery slope, recovery level, recovery interpretation, "
    "route-core/off-route/terminal event status, weather/event context, and movement behavior "
    "are descriptive evidence. This output is not a cardiopulmonary diagnosis, "
    "not ability scoring, not route suitability scoring, not THCI/radar scoring, "
    "and not a final hiking risk assessment."
)

DEFAULT_EVENT_ROOT = (
    "outputs/ib3c_activity_behavior_events_adaptive_speed_v1_phase3c_recovery_interpretation_26batch/"
    "qixing_lengshuikeng"
)

DEFAULT_OUTPUT_ROOT = "outputs/report_figures/ch6_7_hr_recovery_from_ib3c_events_v1_1"

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
}


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.stat().st_size == 0:
        raise pd.errors.EmptyDataError(f"Empty CSV: {path}")
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def safe_text(v) -> str:
    if pd.isna(v):
        return ""
    return str(v)


def parse_activity_id_from_path(path: Path, df: pd.DataFrame | None = None) -> str:
    if df is not None and "activity_id" in df.columns and df["activity_id"].notna().any():
        raw = str(df["activity_id"].dropna().iloc[0])
        m = re.search(r"(\d+_\d+)", raw)
        if m:
            return m.group(1)
        return raw

    for part in reversed(path.parts):
        m = re.fullmatch(r"(\d+_\d+)", part)
        if m:
            return m.group(1)

    m = re.search(r"_(\d+_\d+)_ib3c_behavior_events\.csv$", path.name)
    if m:
        return m.group(1)

    return path.stem


def ensure_columns(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    out = df.copy()
    for c in columns:
        if c not in out.columns:
            out[c] = np.nan
    return out


def classify_route_core_status(row: pd.Series) -> str:
    event_type = safe_text(row.get("event_type"))
    event_subtype = safe_text(row.get("event_subtype"))
    sem = safe_text(row.get("semantic_recovery_interpretation"))
    semantic_candidate = safe_text(row.get("semantic_event_type_candidate"))
    recovery_level = safe_text(row.get("recovery_level"))
    on_route_ratio = row.get("on_route_ratio", np.nan)

    # Always exclude terminal/post-route artifacts from route-core recovery review.
    if event_type == "terminal_artifact" or sem == "terminal_artifact" or recovery_level == "terminal_post_route_stop":
        return "EXCLUDE_TERMINAL_ARTIFACT"

    # Off-route rest is useful observed behavior evidence, but not route-core recovery.
    if event_type == "off_route_rest" or sem == "off_route_event":
        return "OBSERVED_OFF_ROUTE_REST_NOT_ROUTE_CORE"

    # v1.1 change:
    # Include on-route facility/rest-point events in route-core recovery review.
    # These often occur near bench/shelter/toilets/rest POIs and are relevant for pacing/rest planning.
    facility_like = (
        event_type == "facility_rest"
        or event_subtype in {"near_facility_or_rest_poi", "facility_rest"}
        or semantic_candidate in {"facility_rest_with_hr_drop", "facility_rest_without_hr_drop"}
    )
    if facility_like and pd.notna(on_route_ratio) and float(on_route_ratio) >= 0.8:
        return "ROUTE_CORE_FACILITY_REST_REVIEW_EVENT"

    if event_type in {"high_hr_recovery_stop", "short_pause", "recovery_stop"}:
        return "ROUTE_CORE_RECOVERY_REVIEW_EVENT"

    if sem in {
        "confirmed_hr_recovery",
        "high_hr_pause_without_recovery",
        "pause_without_hr_drop",
        "possible_recovery",
    }:
        return "ROUTE_CORE_RECOVERY_REVIEW_EVENT"

    return "NON_ROUTE_CORE_EVENT_RETAINED"


def classify_recovery_strength(row: pd.Series) -> str:
    sem = safe_text(row.get("semantic_recovery_interpretation"))
    effect = safe_text(row.get("hr_recovery_effect"))
    hr_drop = row.get("hr_drop_bpm", np.nan)
    slope = row.get("hr_recovery_slope_bpm_per_min", np.nan)

    if sem == "terminal_artifact":
        return "TERMINAL_ARTIFACT_EXCLUDED"
    if sem == "off_route_event":
        return "OFF_ROUTE_EVENT_RETAINED_NOT_ROUTE_CORE"

    if sem == "confirmed_hr_recovery":
        if pd.notna(hr_drop) and hr_drop >= 10:
            return "CONFIRMED_STRONG_HR_RECOVERY"
        return "CONFIRMED_HR_RECOVERY"

    if sem == "high_hr_pause_without_recovery":
        return "HIGH_HR_PAUSE_WITHOUT_RECOVERY"

    if sem == "pause_without_hr_drop":
        return "PAUSE_WITHOUT_HR_DROP"

    if sem == "possible_recovery":
        return "POSSIBLE_HR_RECOVERY"

    if effect == "hr_recovered":
        return "HR_RECOVERED"
    if effect == "hr_partially_recovered":
        return "PARTIAL_HR_RECOVERY"
    if effect == "hr_increased":
        return "HR_INCREASED_DURING_EVENT"

    if pd.notna(slope) and slope < -10:
        return "HR_DROP_SLOPE_PRESENT"

    return "NO_CLEAR_HR_RECOVERY_INTERPRETATION"


def activity_phase_from_elapsed(start_sec: float, min_sec: float, max_sec: float) -> str:
    if pd.isna(start_sec) or pd.isna(min_sec) or pd.isna(max_sec) or max_sec <= min_sec:
        return "unknown"
    frac = (start_sec - min_sec) / (max_sec - min_sec)
    if frac < 1 / 3:
        return "early"
    if frac < 2 / 3:
        return "middle"
    return "late"


def collect_event_files(event_root: Path) -> list[Path]:
    return sorted(event_root.glob("**/*_ib3c_behavior_events.csv"))


def load_all_events(event_root: Path) -> tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []
    rows: list[pd.DataFrame] = []

    for path in collect_event_files(event_root):
        try:
            df = read_csv(path)
        except pd.errors.EmptyDataError:
            warnings.append(f"SKIPPED_EMPTY_CSV:{path}")
            continue
        except UnicodeDecodeError:
            warnings.append(f"SKIPPED_DECODE_ERROR:{path}")
            continue

        activity_id = parse_activity_id_from_path(path, df)
        df["activity_id_short"] = activity_id
        df["source_csv"] = str(path)
        rows.append(df)

    if not rows:
        return pd.DataFrame(), warnings

    all_events = pd.concat(rows, ignore_index=True)
    return all_events, warnings


def standardize_events(df: pd.DataFrame) -> pd.DataFrame:
    required = [
        "event_id",
        "activity_id_short",
        "activity_id",
        "event_type",
        "event_subtype",
        "event_modifiers",
        "start_elapsed_sec",
        "end_elapsed_sec",
        "duration_sec",
        "duration_tier",
        "start_route_dist_m",
        "end_route_dist_m",
        "route_dist_span_m",
        "mean_speed_mps",
        "min_speed_mps",
        "max_speed_mps",
        "on_route_ratio",
        "off_route_ratio",
        "mean_hr_bpm",
        "max_hr_bpm",
        "hr_start_bpm",
        "hr_end_bpm",
        "hr_delta_bpm",
        "hr_drop_bpm",
        "hr_recovery_slope_bpm_per_min",
        "rest_duration_tier",
        "recovery_level",
        "hr_recovery_effect",
        "estimated_recovery_score",
        "recovery_interpretation",
        "semantic_low_speed_class",
        "semantic_motion_class",
        "semantic_hr_response_class",
        "semantic_event_type_candidate",
        "semantic_hr_delta_class",
        "semantic_recovery_interpretation",
        "route_semantic_context",
        "surface_context",
        "facility_context",
        "rest_context",
        "support_context",
        "hydrology_context",
        "slope_context",
        "terrain_risk_context",
        "terrain_risk_score_mean",
        "weather_mode",
        "weather_scenario_name",
        "weather_context",
        "weather_event_modifier",
        "activity_risk_context",
        "excluded_reason_context",
        "candidate_reason",
        "confidence",
        "points_n",
        "source_csv",
    ]
    out = ensure_columns(df, required)

    numeric_cols = [
        "start_elapsed_sec",
        "end_elapsed_sec",
        "duration_sec",
        "start_route_dist_m",
        "end_route_dist_m",
        "route_dist_span_m",
        "mean_speed_mps",
        "min_speed_mps",
        "max_speed_mps",
        "on_route_ratio",
        "off_route_ratio",
        "mean_hr_bpm",
        "max_hr_bpm",
        "hr_start_bpm",
        "hr_end_bpm",
        "hr_delta_bpm",
        "hr_drop_bpm",
        "hr_recovery_slope_bpm_per_min",
        "estimated_recovery_score",
        "terrain_risk_score_mean",
        "confidence",
        "points_n",
    ]
    for c in numeric_cols:
        out[c] = numeric(out[c])

    # Some sources use hr_delta_bpm as end-start. For recovery, positive drop is more readable.
    if "hr_drop_bpm" in out.columns:
        missing_drop = out["hr_drop_bpm"].isna()
        out.loc[missing_drop, "hr_drop_bpm"] = -out.loc[missing_drop, "hr_delta_bpm"]

    out["route_core_event_status"] = out.apply(classify_route_core_status, axis=1)
    out["recovery_strength_class"] = out.apply(classify_recovery_strength, axis=1)

    minmax = (
        out.groupby("activity_id_short")["start_elapsed_sec"]
        .agg(["min", "max"])
        .rename(columns={"min": "_activity_start_min_sec", "max": "_activity_start_max_sec"})
    )
    out = out.merge(minmax, left_on="activity_id_short", right_index=True, how="left")
    out["activity_phase"] = out.apply(
        lambda r: activity_phase_from_elapsed(
            r.get("start_elapsed_sec"),
            r.get("_activity_start_min_sec"),
            r.get("_activity_start_max_sec"),
        ),
        axis=1,
    )
    out = out.drop(columns=["_activity_start_min_sec", "_activity_start_max_sec"], errors="ignore")

    out["boundary"] = BOUNDARY

    selected = [
        "activity_id_short",
        "event_id",
        "event_type",
        "event_subtype",
        "event_modifiers",
        "activity_phase",
        "start_elapsed_sec",
        "end_elapsed_sec",
        "duration_sec",
        "duration_tier",
        "start_route_dist_m",
        "end_route_dist_m",
        "route_dist_span_m",
        "mean_speed_mps",
        "min_speed_mps",
        "max_speed_mps",
        "on_route_ratio",
        "off_route_ratio",
        "mean_hr_bpm",
        "max_hr_bpm",
        "hr_start_bpm",
        "hr_end_bpm",
        "hr_delta_bpm",
        "hr_drop_bpm",
        "hr_recovery_slope_bpm_per_min",
        "rest_duration_tier",
        "recovery_level",
        "hr_recovery_effect",
        "estimated_recovery_score",
        "semantic_event_type_candidate",
        "semantic_hr_delta_class",
        "semantic_recovery_interpretation",
        "route_core_event_status",
        "recovery_strength_class",
        "route_semantic_context",
        "surface_context",
        "facility_context",
        "rest_context",
        "support_context",
        "hydrology_context",
        "slope_context",
        "terrain_risk_context",
        "terrain_risk_score_mean",
        "weather_mode",
        "weather_scenario_name",
        "weather_context",
        "weather_event_modifier",
        "activity_risk_context",
        "excluded_reason_context",
        "candidate_reason",
        "confidence",
        "points_n",
        "source_csv",
        "boundary",
    ]

    return out[selected].copy()


def mode_text(s: pd.Series) -> str:
    vals = [str(v) for v in s.dropna().tolist() if str(v).strip() and str(v).lower() != "nan"]
    if not vals:
        return ""
    return pd.Series(vals).mode().iloc[0]


ROUTE_CORE_STATUSES = {
    "ROUTE_CORE_RECOVERY_REVIEW_EVENT",
    "ROUTE_CORE_FACILITY_REST_REVIEW_EVENT",
}


def is_route_core_status(s: pd.Series) -> pd.Series:
    return s.isin(ROUTE_CORE_STATUSES)


def summarize_activity(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()

    route_core = is_route_core_status(events["route_core_event_status"])
    route_core_events = events[route_core].copy()

    def agg_activity(g: pd.DataFrame) -> pd.Series:
        rc = g[is_route_core_status(g["route_core_event_status"])]

        confirmed = rc["semantic_recovery_interpretation"].eq("confirmed_hr_recovery").sum()
        high_no = rc["semantic_recovery_interpretation"].eq("high_hr_pause_without_recovery").sum()
        pause_no = rc["semantic_recovery_interpretation"].eq("pause_without_hr_drop").sum()
        possible = rc["semantic_recovery_interpretation"].eq("possible_recovery").sum()

        strong = rc["recovery_strength_class"].eq("CONFIRMED_STRONG_HR_RECOVERY").sum()
        no_clear = rc["recovery_strength_class"].isin(
            ["HIGH_HR_PAUSE_WITHOUT_RECOVERY", "PAUSE_WITHOUT_HR_DROP", "NO_CLEAR_HR_RECOVERY_INTERPRETATION"]
        ).sum()

        if len(rc) == 0:
            if g["route_core_event_status"].isin(
                ["OBSERVED_OFF_ROUTE_REST_NOT_ROUTE_CORE", "EXCLUDE_TERMINAL_ARTIFACT"]
            ).all():
                status = "ONLY_OFF_ROUTE_OR_TERMINAL_EVENTS"
            else:
                status = "NO_ROUTE_CORE_RECOVERY_EVENT"
        elif confirmed > 0 and high_no > 0:
            status = "ROUTE_CORE_RECOVERY_AND_HIGH_HR_NO_RECOVERY_BOTH_PRESENT"
        elif confirmed > 0:
            status = "ROUTE_CORE_HR_RECOVERY_EVIDENCE_AVAILABLE"
        elif high_no > 0:
            status = "ROUTE_CORE_HIGH_HR_PAUSE_WITHOUT_RECOVERY_PRESENT"
        elif pause_no > 0 or possible > 0:
            status = "ROUTE_CORE_PAUSE_EVENTS_PRESENT_NO_CLEAR_RECOVERY"
        else:
            status = "ROUTE_CORE_RECOVERY_OR_FACILITY_REST_REVIEW_EVENT_PRESENT_UNCLASSIFIED"

        return pd.Series({
            "event_count_total": len(g),
            "route_core_event_count": len(rc),
            "confirmed_hr_recovery_count": int(confirmed),
            "high_hr_pause_without_recovery_count": int(high_no),
            "pause_without_hr_drop_count": int(pause_no),
            "possible_recovery_count": int(possible),
            "off_route_rest_count": int(g["event_type"].eq("off_route_rest").sum()),
            "terminal_artifact_count": int(g["event_type"].eq("terminal_artifact").sum()),
            "strong_recovery_event_count": int(strong),
            "no_clear_recovery_event_count": int(no_clear),
            "hr_drop_bpm_median": rc["hr_drop_bpm"].median() if len(rc) else np.nan,
            "hr_drop_bpm_max": rc["hr_drop_bpm"].max() if len(rc) else np.nan,
            "hr_recovery_slope_bpm_per_min_median": rc["hr_recovery_slope_bpm_per_min"].median() if len(rc) else np.nan,
            "estimated_recovery_score_median": rc["estimated_recovery_score"].median() if len(rc) else np.nan,
            "mean_speed_mps_median": rc["mean_speed_mps"].median() if len(rc) else np.nan,
            "on_route_ratio_median": rc["on_route_ratio"].median() if len(rc) else np.nan,
            "dominant_recovery_strength_class": mode_text(rc["recovery_strength_class"]) if len(rc) else "",
            "dominant_semantic_recovery_interpretation": mode_text(rc["semantic_recovery_interpretation"]) if len(rc) else "",
            "route_core_recovery_status": status,
            "boundary": BOUNDARY,
        })

    summary = (
        events.groupby("activity_id_short", as_index=False)
        .apply(agg_activity, include_groups=False)
        .reset_index()
    )

    if "level_0" in summary.columns:
        summary = summary.drop(columns=["level_0"])
    return summary


def summarize_phase(events: pd.DataFrame) -> pd.DataFrame:
    rc = events[is_route_core_status(events["route_core_event_status"])].copy()
    if rc.empty:
        return pd.DataFrame()

    out = (
        rc.groupby(["activity_id_short", "activity_phase"], as_index=False)
        .agg(
            route_core_event_count=("event_id", "count"),
            confirmed_hr_recovery_count=(
                "semantic_recovery_interpretation",
                lambda s: int((s == "confirmed_hr_recovery").sum()),
            ),
            high_hr_pause_without_recovery_count=(
                "semantic_recovery_interpretation",
                lambda s: int((s == "high_hr_pause_without_recovery").sum()),
            ),
            hr_drop_bpm_median=("hr_drop_bpm", "median"),
            hr_drop_bpm_max=("hr_drop_bpm", "max"),
            hr_recovery_slope_bpm_per_min_median=("hr_recovery_slope_bpm_per_min", "median"),
            estimated_recovery_score_median=("estimated_recovery_score", "median"),
            dominant_recovery_strength_class=("recovery_strength_class", mode_text),
        )
    )
    out["boundary"] = BOUNDARY
    return out


def summarize_group(events: pd.DataFrame, activity_summary: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()

    route_core = events[is_route_core_status(events["route_core_event_status"])]
    rows = [{
        "scope": "all_events",
        "activity_count": events["activity_id_short"].nunique(),
        "event_count_total": len(events),
        "route_core_event_count": len(route_core),
        "route_core_facility_rest_event_count": int(
            events["route_core_event_status"].eq("ROUTE_CORE_FACILITY_REST_REVIEW_EVENT").sum()
        ),
        "confirmed_hr_recovery_count": int(
            route_core["semantic_recovery_interpretation"].eq("confirmed_hr_recovery").sum()
        ),
        "high_hr_pause_without_recovery_count": int(
            route_core["semantic_recovery_interpretation"].eq("high_hr_pause_without_recovery").sum()
        ),
        "pause_without_hr_drop_count": int(
            route_core["semantic_recovery_interpretation"].eq("pause_without_hr_drop").sum()
        ),
        "possible_recovery_count": int(
            route_core["semantic_recovery_interpretation"].eq("possible_recovery").sum()
        ),
        "off_route_rest_count": int(events["event_type"].eq("off_route_rest").sum()),
        "terminal_artifact_count": int(events["event_type"].eq("terminal_artifact").sum()),
        "activities_with_route_core_event": route_core["activity_id_short"].nunique(),
        "activities_with_route_core_facility_rest_event": events.loc[
            events["route_core_event_status"].eq("ROUTE_CORE_FACILITY_REST_REVIEW_EVENT"),
            "activity_id_short",
        ].nunique(),
        "activities_with_confirmed_hr_recovery": route_core.loc[
            route_core["semantic_recovery_interpretation"].eq("confirmed_hr_recovery"),
            "activity_id_short",
        ].nunique(),
        "activities_with_high_hr_pause_without_recovery": route_core.loc[
            route_core["semantic_recovery_interpretation"].eq("high_hr_pause_without_recovery"),
            "activity_id_short",
        ].nunique(),
        "route_core_hr_drop_bpm_median": route_core["hr_drop_bpm"].median(),
        "route_core_hr_recovery_slope_bpm_per_min_median": route_core[
            "hr_recovery_slope_bpm_per_min"
        ].median(),
        "route_core_estimated_recovery_score_median": route_core["estimated_recovery_score"].median(),
        "boundary": BOUNDARY,
    }]
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
    events: pd.DataFrame,
    activity_summary: pd.DataFrame,
    phase_summary: pd.DataFrame,
    group_summary: pd.DataFrame,
    audit: pd.DataFrame,
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
<title>CH6.7 HR Recovery From IB3C Events v1.1</title>
{css}
</head>
<body>
<h1>CH6.7 HR Recovery From IB3C Events v1.1</h1>
<div class="boundary">{html.escape(BOUNDARY)}</div>

<h2>Audit</h2>
{table_html(audit, 20)}

<h2>Group summary</h2>
{table_html(group_summary, 20)}

<h2>Activity summary</h2>
{table_html(activity_summary, 80)}

<h2>Phase summary</h2>
{table_html(phase_summary, 120)}

<h2>Route-core event preview</h2>
{table_html(events[is_route_core_status(events["route_core_event_status"])], 120)}

</body>
</html>
"""
    output_path.write_text(html_text, encoding="utf-8")


def build_audit(
    script_path: Path,
    event_root: Path,
    output_root: Path,
    raw_events: pd.DataFrame,
    events: pd.DataFrame,
    activity_summary: pd.DataFrame,
    warnings: list[str],
    output_paths: list[Path],
) -> pd.DataFrame:
    route_core = events[is_route_core_status(events["route_core_event_status"])]
    confirmed = route_core["semantic_recovery_interpretation"].eq("confirmed_hr_recovery")
    high_no = route_core["semantic_recovery_interpretation"].eq("high_hr_pause_without_recovery")
    facility_core = events["route_core_event_status"].eq("ROUTE_CORE_FACILITY_REST_REVIEW_EVENT")

    forbidden_absent = forbidden_columns_absent(output_paths)

    conclusion = (
        "PASS_CH6_7_HR_RECOVERY_FROM_IB3C_EVENTS_V1_1_DESCRIPTIVE_ONLY"
        if len(events) > 0 and forbidden_absent
        else "FAIL_CH6_7_HR_RECOVERY_FROM_IB3C_EVENTS_V1_1_REVIEW_REQUIRED"
    )

    return pd.DataFrame([{
        "script_path": str(script_path),
        "event_root": str(event_root),
        "output_root": str(output_root),
        "event_csv_count": len(collect_event_files(event_root)),
        "raw_event_rows": len(raw_events),
        "standardized_event_rows": len(events),
        "activity_count": events["activity_id_short"].nunique() if not events.empty else 0,
        "route_core_event_count": len(route_core),
        "route_core_facility_rest_event_count": int(facility_core.sum()),
        "confirmed_hr_recovery_event_count": int(confirmed.sum()),
        "high_hr_pause_without_recovery_event_count": int(high_no.sum()),
        "activities_with_route_core_events": route_core["activity_id_short"].nunique() if not route_core.empty else 0,
        "activities_with_route_core_facility_rest_events": events.loc[facility_core, "activity_id_short"].nunique() if facility_core.any() else 0,
        "activities_with_confirmed_hr_recovery": route_core.loc[confirmed, "activity_id_short"].nunique() if not route_core.empty else 0,
        "activities_with_high_hr_pause_without_recovery": route_core.loc[high_no, "activity_id_short"].nunique() if not route_core.empty else 0,
        "activity_summary_rows": len(activity_summary),
        "warnings": "|".join(warnings),
        "forbidden_columns_absent": forbidden_absent,
        "audit_conclusion": conclusion,
        "boundary": BOUNDARY,
    }])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".", help="Project root, default current working directory.")
    parser.add_argument("--event-root", default=DEFAULT_EVENT_ROOT, help="IB3C phase3c event root.")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, help="Output root.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    project_root = Path(args.project_root).resolve()
    event_root = (project_root / args.event_root).resolve()
    output_root = (project_root / args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    raw_events, warnings = load_all_events(event_root)
    events = standardize_events(raw_events) if not raw_events.empty else pd.DataFrame()

    activity_summary = summarize_activity(events)
    phase_summary = summarize_phase(events)
    group_summary = summarize_group(events, activity_summary)

    events_csv = output_root / "activity_hr_recovery_events_from_ib3c_v1_1.csv"
    activity_summary_csv = output_root / "activity_hr_recovery_activity_summary_from_ib3c_v1_1.csv"
    phase_summary_csv = output_root / "activity_hr_recovery_phase_summary_from_ib3c_v1_1.csv"
    group_summary_csv = output_root / "activity_hr_recovery_group_summary_from_ib3c_v1_1.csv"
    audit_csv = output_root / "activity_hr_recovery_from_ib3c_audit_v1_1.csv"
    html_report = output_root / "activity_hr_recovery_from_ib3c_report_v1_1.html"

    events.to_csv(events_csv, index=False, encoding="utf-8-sig")
    activity_summary.to_csv(activity_summary_csv, index=False, encoding="utf-8-sig")
    phase_summary.to_csv(phase_summary_csv, index=False, encoding="utf-8-sig")
    group_summary.to_csv(group_summary_csv, index=False, encoding="utf-8-sig")

    output_paths = [
        events_csv,
        activity_summary_csv,
        phase_summary_csv,
        group_summary_csv,
        audit_csv,
        html_report,
    ]

    audit = build_audit(
        script_path=Path(__file__).resolve(),
        event_root=event_root,
        output_root=output_root,
        raw_events=raw_events,
        events=events,
        activity_summary=activity_summary,
        warnings=warnings,
        output_paths=output_paths[:-2],
    )
    audit.to_csv(audit_csv, index=False, encoding="utf-8-sig")

    write_html_report(html_report, events, activity_summary, phase_summary, group_summary, audit)

    result = audit.iloc[0].to_dict()
    result["html_report"] = str(html_report)
    print(result)


if __name__ == "__main__":
    main()
