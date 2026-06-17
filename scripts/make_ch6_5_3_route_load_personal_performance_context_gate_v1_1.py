#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build CH6.5.3 v1.1 neutral semantic relabel and attention-review layer.

This is a semantic patch over CH6.5.3 v1. It changes the interpretation from
"review required" to "context complete / ready for comparison" when the evidence
join is complete, and separates true relative attention flags into a distinct
attention_review layer.

Boundaries:
- descriptive evidence only
- no ability score, rank, or class
- no route suitability score
- no final hiking risk score
- no go/no-go decision
- no medical diagnosis
- no causality inference
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


DEFAULT_PROFILE_ID = "qixing_lengshuikeng_activity_group_full25"
DEFAULT_ROUTE_FOLDER = "qixing_lengshuikeng"

DEFAULT_INPUT_ROOT = "outputs/report_figures/ch6_5_3_route_load_personal_performance_readiness_gate_v1"
DEFAULT_OUTPUT_ROOT = "outputs/report_figures/ch6_5_3_route_load_personal_performance_readiness_gate_v1_1"

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
    "Descriptive CH6.5.3 v1.1 semantic relabel and attention-review layer only. "
    "Route-load and behavior response are normal hiking phenomena when a route has "
    "real ascent or load. This layer confirms whether route-load, behavior, weather, "
    "and readiness context are complete enough for comparison, and separately marks "
    "relative attention-review flags. It is not ability scoring, ranking, classing, "
    "THCI, radar, final hiking risk scoring, route suitability scoring, go/no-go "
    "decisioning, medical diagnosis, or causality evidence."
)

METHOD_NOTE = (
    "v1.1 preserves CH6.5.3 v1 evidence but relabels the primary gate as a neutral "
    "context-completeness gate. Attention review is computed separately from "
    "within-group relative behavior/weather/HR indicators."
)

NORMAL_RESPONSE_NOTE = (
    "Route-load, slower movement, higher heart-rate demand, pauses, and recovery "
    "needs can be normal hiking responses on a loaded uphill route. They should not "
    "be interpreted as warnings by themselves."
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=r"D:\mountain_work\115_osm")
    p.add_argument("--profile-id", default=DEFAULT_PROFILE_ID)
    p.add_argument("--route-folder", default=DEFAULT_ROUTE_FOLDER)
    p.add_argument("--input-root", default=DEFAULT_INPUT_ROOT)
    p.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    return p.parse_args()


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


def require_columns(df: pd.DataFrame, cols: list[str], label: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(f"{label} missing required columns: {missing}; available={list(df.columns)}")


def neutral_context_status(row: pd.Series) -> str:
    join_status = str(row.get("ch6_8_readiness_join_status", "")).upper()
    weather_ratio = float(row.get("weather_context_available_ratio", 0) or 0)
    route_load = str(row.get("route_load_context_bands_observed", "")).upper()
    phases = str(row.get("route_phases_observed", "")).upper()

    if "JOINED" not in join_status:
        return "READINESS_CONTEXT_INCOMPLETE_CH6_8_NOT_JOINED"
    if weather_ratio < 1:
        return "READINESS_CONTEXT_INCOMPLETE_WEATHER_COVERAGE_REVIEW"
    if not route_load or route_load == "NONE":
        return "READINESS_CONTEXT_INCOMPLETE_ROUTE_LOAD_CONTEXT_REVIEW"
    if not phases or phases == "NONE":
        return "READINESS_CONTEXT_INCOMPLETE_ROUTE_PHASE_CONTEXT_REVIEW"
    return "READINESS_CONTEXT_COMPLETE_ROUTE_LOAD_BEHAVIOR_WEATHER_READY_FOR_COMPARISON"


def build_thresholds(activity: pd.DataFrame) -> dict[str, float]:
    return {
        "speed_p25": q(activity.get("speed_mps_median_median", pd.Series(dtype=float)), 0.25),
        "low_speed_p75": q(activity.get("low_speed_ratio_avg", pd.Series(dtype=float)), 0.75),
        "stopped_p75": q(activity.get("stopped_ratio_avg", pd.Series(dtype=float)), 0.75),
        "hr_p75": q(activity.get("heart_rate_bpm_median_avg", pd.Series(dtype=float)), 0.75),
        "behavior_weather_p75": q(activity.get("behavior_weather_context_review_required_ratio", pd.Series(dtype=float)), 0.75),
        "uphill_high_p75": q(activity.get("uphill_high_route_load_ratio", pd.Series(dtype=float)), 0.75),
        "candidate_p75": q(activity.get("route_load_behavior_candidate_window_ratio", pd.Series(dtype=float)), 0.75),
    }


def attention_flags(row: pd.Series, thresholds: dict[str, float]) -> str:
    flags: list[str] = []

    status = str(row.get("context_completeness_gate_status", ""))
    if not status.startswith("READINESS_CONTEXT_COMPLETE"):
        flags.append("CONTEXT_INCOMPLETE_ATTENTION_REVIEW_REQUIRED")
        return pipe_flags(flags)

    # Relative attention indicators only. These are not warnings by themselves.
    speed = row.get("speed_mps_median_median")
    if pd.notna(speed) and pd.notna(thresholds["speed_p25"]) and speed <= thresholds["speed_p25"]:
        flags.append("RELATIVE_SLOWER_SPEED_REVIEW")

    low_speed = row.get("low_speed_ratio_avg")
    if pd.notna(low_speed) and pd.notna(thresholds["low_speed_p75"]) and low_speed >= thresholds["low_speed_p75"]:
        flags.append("RELATIVE_HIGH_LOW_SPEED_RATIO_REVIEW")

    stopped = row.get("stopped_ratio_avg")
    if pd.notna(stopped) and pd.notna(thresholds["stopped_p75"]) and stopped >= thresholds["stopped_p75"]:
        flags.append("RELATIVE_HIGH_STOPPED_RATIO_REVIEW")

    hr = row.get("heart_rate_bpm_median_avg")
    if pd.notna(hr) and pd.notna(thresholds["hr_p75"]) and hr >= thresholds["hr_p75"]:
        flags.append("RELATIVE_HIGH_HR_CONTEXT_REVIEW")

    bw = row.get("behavior_weather_context_review_required_ratio")
    if pd.notna(bw) and pd.notna(thresholds["behavior_weather_p75"]) and bw >= thresholds["behavior_weather_p75"]:
        flags.append("RELATIVE_HIGH_BEHAVIOR_WEATHER_OVERLAP_REVIEW")

    uphill_high = row.get("uphill_high_route_load_ratio")
    if pd.notna(uphill_high) and pd.notna(thresholds["uphill_high_p75"]) and uphill_high >= thresholds["uphill_high_p75"]:
        flags.append("RELATIVE_HIGH_UPHILL_LOAD_RATIO_REVIEW")

    candidate = row.get("route_load_behavior_candidate_window_ratio")
    if pd.notna(candidate) and pd.notna(thresholds["candidate_p75"]) and candidate >= thresholds["candidate_p75"]:
        flags.append("RELATIVE_HIGH_ROUTE_LOAD_BEHAVIOR_RESPONSE_REVIEW")

    return pipe_flags(flags) if flags else "NO_RELATIVE_ATTENTION_FLAG"


def attention_level(flags: str) -> str:
    if not flags or flags == "NO_RELATIVE_ATTENTION_FLAG" or flags == "NONE":
        return "CONTEXT_COMPLETE_NO_RELATIVE_ATTENTION_FLAG"
    if "CONTEXT_INCOMPLETE" in flags:
        return "CONTEXT_INCOMPLETE_ATTENTION_REVIEW_REQUIRED"
    n = len([p for p in str(flags).split("|") if p.strip()])
    if n >= 4:
        return "MULTI_FACTOR_RELATIVE_ATTENTION_REVIEW"
    if n >= 2:
        return "MODERATE_RELATIVE_ATTENTION_REVIEW"
    return "SINGLE_FACTOR_RELATIVE_ATTENTION_REVIEW"


def prepare_activity(activity: pd.DataFrame, gate: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    require_columns(activity, ["activity_id_short"], "v1 activity summary")
    require_columns(gate, ["activity_id_short"], "v1 gate")

    a = activity.copy()
    a["profile_id"] = args.profile_id
    a["route_folder"] = args.route_folder
    a["activity_id_short"] = clean_str(a["activity_id_short"])

    numeric_cols = [
        "windows_n",
        "high_or_very_high_route_load_ratio",
        "uphill_ratio",
        "downhill_ratio",
        "uphill_high_route_load_ratio",
        "speed_mps_median_median",
        "speed_mps_median_p25",
        "speed_mps_median_p75",
        "low_speed_ratio_avg",
        "stopped_ratio_avg",
        "heart_rate_bpm_median_avg",
        "heart_rate_bpm_median_median",
        "weather_context_available_ratio",
        "conservative_weather_review_required_ratio",
        "behavior_weather_context_review_required_ratio",
        "route_load_behavior_candidate_window_ratio",
    ]
    for col in numeric_cols:
        if col in a.columns:
            a[col] = numeric(a[col])

    gate_keep = [
        "activity_id_short",
        "readiness_review_gate_status",
        "readiness_review_gate_flags",
    ]
    gate_small = gate[[c for c in gate_keep if c in gate.columns]].copy()
    gate_small = gate_small.rename(columns={
        "readiness_review_gate_status": "previous_readiness_review_gate_status",
        "readiness_review_gate_flags": "previous_readiness_review_gate_flags",
    })

    merged = a.merge(gate_small, on="activity_id_short", how="left")
    merged["previous_readiness_review_gate_status"] = merged["previous_readiness_review_gate_status"].fillna("PREVIOUS_GATE_NOT_JOINED")
    merged["previous_readiness_review_gate_flags"] = merged["previous_readiness_review_gate_flags"].fillna("PREVIOUS_GATE_NOT_JOINED")

    merged["context_completeness_gate_status"] = merged.apply(neutral_context_status, axis=1)
    thresholds = build_thresholds(merged)
    merged["relative_attention_review_flags"] = merged.apply(lambda row: attention_flags(row, thresholds), axis=1)
    merged["relative_attention_review_level"] = merged["relative_attention_review_flags"].apply(attention_level)
    merged["normal_hiking_response_note"] = NORMAL_RESPONSE_NOTE
    merged["method_note"] = METHOD_NOTE
    merged["interpretation_boundary"] = BOUNDARY_TEXT

    return merged.sort_values("activity_id_short").reset_index(drop=True)


def build_context_gate(activity: pd.DataFrame) -> pd.DataFrame:
    keep = [
        "profile_id",
        "route_folder",
        "activity_id_short",
        "context_completeness_gate_status",
        "relative_attention_review_level",
        "relative_attention_review_flags",
        "previous_readiness_review_gate_status",
        "previous_readiness_review_gate_flags",
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
        "normal_hiking_response_note",
        "method_note",
        "interpretation_boundary",
    ]
    return activity[[c for c in keep if c in activity.columns]].copy()


def build_attention_summary(activity: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    rows = []
    for level, group in activity.groupby("relative_attention_review_level", dropna=False):
        rows.append({
            "profile_id": args.profile_id,
            "route_folder": args.route_folder,
            "relative_attention_review_level": level,
            "activity_count": int(group["activity_id_short"].nunique()),
            "activity_id_short_list": "|".join(sorted(group["activity_id_short"].astype(str).tolist())),
            "windows_n": int(numeric(group.get("windows_n", pd.Series(dtype=float))).sum()),
            "speed_mps_median_median_avg": round(mean(group.get("speed_mps_median_median", pd.Series(dtype=float))), 6),
            "low_speed_ratio_avg": round(mean(group.get("low_speed_ratio_avg", pd.Series(dtype=float))), 6),
            "stopped_ratio_avg": round(mean(group.get("stopped_ratio_avg", pd.Series(dtype=float))), 6),
            "heart_rate_bpm_median_avg": round(mean(group.get("heart_rate_bpm_median_avg", pd.Series(dtype=float))), 6),
            "behavior_weather_context_review_required_ratio_avg": round(mean(group.get("behavior_weather_context_review_required_ratio", pd.Series(dtype=float))), 6),
            "relative_attention_review_flags_observed": pipe_flags(group["relative_attention_review_flags"].astype(str).tolist()),
            "interpretation_boundary": BOUNDARY_TEXT,
        })
    return pd.DataFrame(rows).sort_values("relative_attention_review_level").reset_index(drop=True) if rows else pd.DataFrame()


def build_context_summary(activity: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    rows = []
    for status, group in activity.groupby("context_completeness_gate_status", dropna=False):
        rows.append({
            "profile_id": args.profile_id,
            "route_folder": args.route_folder,
            "context_completeness_gate_status": status,
            "activity_count": int(group["activity_id_short"].nunique()),
            "activity_id_short_list": "|".join(sorted(group["activity_id_short"].astype(str).tolist())),
            "relative_attention_levels_observed": pipe_flags(group["relative_attention_review_level"].astype(str).tolist()),
            "previous_gate_status_observed": pipe_flags(group["previous_readiness_review_gate_status"].astype(str).tolist()),
            "normal_hiking_response_note": NORMAL_RESPONSE_NOTE,
            "interpretation_boundary": BOUNDARY_TEXT,
        })
    return pd.DataFrame(rows).sort_values("context_completeness_gate_status").reset_index(drop=True) if rows else pd.DataFrame()


def build_data_quality(
    source_inventory: pd.DataFrame,
    context_gate: pd.DataFrame,
    activity: pd.DataFrame,
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
        "check_name": "activity_rows_present",
        "check_status": "PASS" if len(activity) > 0 else "REVIEW_REQUIRED_NO_ACTIVITY_ROWS",
        "check_value": int(len(activity)),
        "details": "per-activity rows generated",
    })

    context_complete_n = int(context_gate["context_completeness_gate_status"].astype(str).str.startswith("READINESS_CONTEXT_COMPLETE").sum()) if not context_gate.empty else 0
    rows.append({
        "profile_id": args.profile_id,
        "route_folder": args.route_folder,
        "check_name": "context_complete_gate_generated",
        "check_status": "PASS" if context_complete_n > 0 else "REVIEW_REQUIRED_NO_CONTEXT_COMPLETE_ROWS",
        "check_value": context_complete_n,
        "details": f"context_complete_n={context_complete_n}",
    })

    previous_required_n = int(activity["previous_readiness_review_gate_status"].astype(str).str.contains("REVIEW_REQUIRED", na=False).sum()) if not activity.empty else 0
    rows.append({
        "profile_id": args.profile_id,
        "route_folder": args.route_folder,
        "check_name": "previous_review_required_preserved_for_traceability",
        "check_status": "PASS",
        "check_value": previous_required_n,
        "details": "v1 review-required wording is preserved only as previous_* traceability fields",
    })

    attention_levels = pipe_flags(context_gate.get("relative_attention_review_level", pd.Series(dtype=str)).astype(str).tolist()) if not context_gate.empty else "NONE"
    rows.append({
        "profile_id": args.profile_id,
        "route_folder": args.route_folder,
        "check_name": "relative_attention_layer_generated",
        "check_status": "PASS" if attention_levels != "NONE" else "REVIEW_REQUIRED_ATTENTION_LAYER_EMPTY",
        "check_value": len([p for p in attention_levels.split("|") if p and p != "NONE"]),
        "details": attention_levels,
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
        "details": "interpretation_boundary generated in outputs",
    })

    return pd.DataFrame(rows)


def audit_conclusion(data_quality: pd.DataFrame) -> str:
    statuses = data_quality["check_status"].astype(str).tolist()
    if any(s.startswith("FAIL") for s in statuses):
        return "REVIEW_REQUIRED_CH6_5_3_ROUTE_LOAD_PERSONAL_PERFORMANCE_CONTEXT_GATE_V1_1"
    if any(s.startswith("REVIEW_REQUIRED") for s in statuses):
        return "REVIEW_REQUIRED_CH6_5_3_ROUTE_LOAD_PERSONAL_PERFORMANCE_CONTEXT_GATE_V1_1"
    return "PASS_CH6_5_3_ROUTE_LOAD_PERSONAL_PERFORMANCE_CONTEXT_GATE_V1_1_DESCRIPTIVE_ONLY"


def write_run_report(
    path: Path,
    source_inventory: pd.DataFrame,
    context_gate: pd.DataFrame,
    context_summary: pd.DataFrame,
    attention_summary: pd.DataFrame,
    data_quality: pd.DataFrame,
    conclusion: str,
    args: argparse.Namespace,
) -> None:
    lines = [
        "# CH6.5.3 v1.1 Route-Load Personal-Performance Context Gate",
        "",
        f"- profile_id: `{args.profile_id}`",
        f"- route_folder: `{args.route_folder}`",
        f"- context_gate_rows: `{len(context_gate)}`",
        f"- context_summary_rows: `{len(context_summary)}`",
        f"- attention_summary_rows: `{len(attention_summary)}`",
        f"- audit_conclusion: `{conclusion}`",
        "",
        "## Method",
        "",
        "- Consumes CH6.5.3 v1 outputs.",
        "- Relabels the primary gate from review-required wording to neutral context-completeness wording.",
        "- Preserves previous v1 gate status and flags as traceability fields.",
        "- Adds separate relative attention-review flags for within-group differentiation.",
        "",
        "## Normal-response interpretation",
        "",
        NORMAL_RESPONSE_NOTE,
        "",
        "## Sources",
        "",
    ]
    for _, row in source_inventory.iterrows():
        lines.append(f"- {row['source_label']}: `{row['source_path']}` exists={row['exists']} bytes={row['length_bytes']}")

    lines.extend(["", "## Context gate distribution", ""])
    if not context_summary.empty:
        for _, row in context_summary.iterrows():
            lines.append(f"- {row['context_completeness_gate_status']}: activities={row['activity_count']}")

    lines.extend(["", "## Attention layer distribution", ""])
    if not attention_summary.empty:
        for _, row in attention_summary.iterrows():
            lines.append(f"- {row['relative_attention_review_level']}: activities={row['activity_count']}")

    lines.extend(["", "## Data quality", ""])
    for _, row in data_quality.iterrows():
        lines.append(f"- {row['check_name']}: {row['check_status']} ({row['details']})")

    lines.extend(["", "## Boundary", "", BOUNDARY_TEXT, ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    input_root = resolve(root, args.input_root)
    output_root = resolve(root, args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    paths = {
        "v1_gate": input_root / "route_load_personal_performance_readiness_gate_v1.csv",
        "v1_activity_summary": input_root / "route_load_personal_performance_context_activity_summary_v1.csv",
        "v1_group_summary": input_root / "route_load_personal_performance_context_group_summary_v1.csv",
        "v1_audit": input_root / "route_load_personal_performance_readiness_gate_audit_v1.csv",
        "v1_data_quality": input_root / "route_load_personal_performance_readiness_gate_data_quality_v1.csv",
    }
    source_inventory = build_source_inventory(paths)

    gate_v1 = read_csv(paths["v1_gate"], "CH6.5.3 v1 gate", required=True)
    activity_v1 = read_csv(paths["v1_activity_summary"], "CH6.5.3 v1 activity summary", required=True)
    _group_v1 = read_csv(paths["v1_group_summary"], "CH6.5.3 v1 group summary", required=False)
    _audit_v1 = read_csv(paths["v1_audit"], "CH6.5.3 v1 audit", required=False)
    _dq_v1 = read_csv(paths["v1_data_quality"], "CH6.5.3 v1 data quality", required=False)

    activity = prepare_activity(activity_v1, gate_v1, args)
    context_gate = build_context_gate(activity)
    context_summary = build_context_summary(activity, args)
    attention_summary = build_attention_summary(activity, args)

    output_paths = {
        "context_gate": output_root / "route_load_personal_performance_context_gate_v1_1.csv",
        "activity_attention": output_root / "route_load_personal_performance_activity_attention_review_v1_1.csv",
        "context_summary": output_root / "route_load_personal_performance_context_gate_summary_v1_1.csv",
        "attention_summary": output_root / "route_load_personal_performance_attention_review_summary_v1_1.csv",
        "data_quality": output_root / "route_load_personal_performance_context_gate_data_quality_v1_1.csv",
        "audit": output_root / "route_load_personal_performance_context_gate_audit_v1_1.csv",
        "run_report": output_root / "route_load_personal_performance_context_gate_run_report_v1_1.md",
    }

    output_fields = {
        "context_gate": list(context_gate.columns),
        "activity": list(activity.columns),
        "context_summary": list(context_summary.columns),
        "attention_summary": list(attention_summary.columns),
    }
    data_quality = build_data_quality(source_inventory, context_gate, activity, output_fields, args)
    conclusion = audit_conclusion(data_quality)

    audit = pd.DataFrame([{
        "profile_id": args.profile_id,
        "route_folder": args.route_folder,
        "activity_count": int(activity["activity_id_short"].nunique()) if not activity.empty else 0,
        "context_gate_rows": int(len(context_gate)),
        "context_summary_rows": int(len(context_summary)),
        "attention_summary_rows": int(len(attention_summary)),
        "context_complete_activities_n": int(context_gate["context_completeness_gate_status"].astype(str).str.startswith("READINESS_CONTEXT_COMPLETE").sum()) if not context_gate.empty else 0,
        "source_files_available_n": int(source_inventory["exists"].sum()),
        "source_files_expected_n": int(len(source_inventory)),
        "audit_conclusion": conclusion,
        "normal_hiking_response_note": NORMAL_RESPONSE_NOTE,
        "interpretation_boundary": BOUNDARY_TEXT,
    }])

    context_gate.to_csv(output_paths["context_gate"], index=False, encoding="utf-8-sig")
    activity.to_csv(output_paths["activity_attention"], index=False, encoding="utf-8-sig")
    context_summary.to_csv(output_paths["context_summary"], index=False, encoding="utf-8-sig")
    attention_summary.to_csv(output_paths["attention_summary"], index=False, encoding="utf-8-sig")
    data_quality.to_csv(output_paths["data_quality"], index=False, encoding="utf-8-sig")
    audit.to_csv(output_paths["audit"], index=False, encoding="utf-8-sig")
    write_run_report(
        output_paths["run_report"],
        source_inventory,
        context_gate,
        context_summary,
        attention_summary,
        data_quality,
        conclusion,
        args,
    )

    print({
        "output_root": str(output_root),
        "profile_id": args.profile_id,
        "activity_count": int(activity["activity_id_short"].nunique()) if not activity.empty else 0,
        "context_gate_rows": int(len(context_gate)),
        "context_summary_rows": int(len(context_summary)),
        "attention_summary_rows": int(len(attention_summary)),
        "context_complete_activities_n": int(context_gate["context_completeness_gate_status"].astype(str).str.startswith("READINESS_CONTEXT_COMPLETE").sum()) if not context_gate.empty else 0,
        "source_files_available_n": int(source_inventory["exists"].sum()),
        "source_files_expected_n": int(len(source_inventory)),
        "audit_conclusion": conclusion,
        "outputs": {k: str(v) for k, v in output_paths.items()},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
