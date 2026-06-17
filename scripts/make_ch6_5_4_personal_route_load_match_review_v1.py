#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build CH6.5.4 personal route-load match review v1.

This layer consumes CH6.5.3 v1.1 context gate outputs and turns the
context-complete evidence into a per-activity route-load match review.

It does NOT judge suitability. It does NOT output an ability score, rank,
class, final hiking risk score, route suitability score, or go/no-go decision.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


DEFAULT_PROFILE_ID = "qixing_lengshuikeng_activity_group_full25"
DEFAULT_ROUTE_FOLDER = "qixing_lengshuikeng"

DEFAULT_CH6_5_3_V1_1_ROOT = (
    "outputs/report_figures/ch6_5_3_route_load_personal_performance_readiness_gate_v1_1"
)
DEFAULT_CONTEXT_GATE = (
    DEFAULT_CH6_5_3_V1_1_ROOT + "/route_load_personal_performance_context_gate_v1_1.csv"
)
DEFAULT_ACTIVITY_ATTENTION = (
    DEFAULT_CH6_5_3_V1_1_ROOT + "/route_load_personal_performance_activity_attention_review_v1_1.csv"
)
DEFAULT_CONTEXT_AUDIT = (
    DEFAULT_CH6_5_3_V1_1_ROOT + "/route_load_personal_performance_context_gate_audit_v1_1.csv"
)
DEFAULT_CONTEXT_DQ = (
    DEFAULT_CH6_5_3_V1_1_ROOT + "/route_load_personal_performance_context_gate_data_quality_v1_1.csv"
)
DEFAULT_OUTPUT_ROOT = "outputs/report_figures/ch6_5_4_personal_route_load_match_review_v1"

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
    "Descriptive CH6.5.4 personal route-load match review only. This layer "
    "compares each activity against the current activity-group reference ranges "
    "for route-load exposure, movement behavior, heart-rate context, and "
    "weather-behavior overlap. It is not an ability score, ability rank, ability "
    "class, THCI, radar, final hiking risk score, route suitability score, "
    "go/no-go decision, medical diagnosis, or causality evidence."
)

NORMAL_RESPONSE_NOTE = (
    "Route-load, slower movement, higher heart-rate demand, pauses, and recovery "
    "needs can be normal hiking responses on a loaded uphill route. CH6.5.4 only "
    "marks relative within-group match-review context; it does not call normal "
    "load response abnormal."
)

METHOD_NOTE = (
    "Uses CH6.5.3 v1.1 context-complete activities as input. Group reference "
    "ranges are based on within-package quartiles; flags indicate relative "
    "attention compared with this activity group, not an external standard."
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=r"D:\mountain_work\115_osm")
    p.add_argument("--profile-id", default=DEFAULT_PROFILE_ID)
    p.add_argument("--route-folder", default=DEFAULT_ROUTE_FOLDER)
    p.add_argument("--context-gate", default=DEFAULT_CONTEXT_GATE)
    p.add_argument("--activity-attention", default=DEFAULT_ACTIVITY_ATTENTION)
    p.add_argument("--context-audit", default=DEFAULT_CONTEXT_AUDIT)
    p.add_argument("--context-data-quality", default=DEFAULT_CONTEXT_DQ)
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


def clean_str(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip()


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def q(series: pd.Series, quantile: float) -> float:
    s = numeric(series).dropna()
    return float(s.quantile(quantile)) if not s.empty else np.nan


def mean(series: pd.Series) -> float:
    s = numeric(series).dropna()
    return float(s.mean()) if not s.empty else np.nan


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


REFERENCE_METRICS = [
    ("speed_mps_median_median", "lower_is_attention", "RELATIVE_SLOWER_SPEED_MATCH_REVIEW"),
    ("low_speed_ratio_avg", "higher_is_attention", "RELATIVE_HIGH_LOW_SPEED_RATIO_MATCH_REVIEW"),
    ("stopped_ratio_avg", "higher_is_attention", "RELATIVE_HIGH_STOPPED_RATIO_MATCH_REVIEW"),
    ("heart_rate_bpm_median_avg", "higher_is_attention", "RELATIVE_HIGH_HR_CONTEXT_MATCH_REVIEW"),
    ("uphill_high_route_load_ratio", "higher_is_attention", "RELATIVE_HIGH_UPHILL_LOAD_EXPOSURE_MATCH_REVIEW"),
    ("route_load_behavior_candidate_window_ratio", "higher_is_attention", "RELATIVE_HIGH_ROUTE_LOAD_BEHAVIOR_RESPONSE_MATCH_REVIEW"),
    ("behavior_weather_context_review_required_ratio", "higher_is_attention", "RELATIVE_HIGH_BEHAVIOR_WEATHER_OVERLAP_MATCH_REVIEW"),
]


def build_reference_thresholds(activity: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    rows = []
    for metric, direction, flag_name in REFERENCE_METRICS:
        vals = numeric(activity[metric]) if metric in activity.columns else pd.Series(dtype=float)
        rows.append({
            "profile_id": args.profile_id,
            "route_folder": args.route_folder,
            "metric": metric,
            "direction": direction,
            "attention_flag_name": flag_name,
            "activity_count_with_value": int(vals.dropna().shape[0]),
            "p25": round(q(vals, 0.25), 6),
            "median": round(q(vals, 0.50), 6),
            "p75": round(q(vals, 0.75), 6),
            "min": round(float(vals.dropna().min()), 6) if not vals.dropna().empty else np.nan,
            "max": round(float(vals.dropna().max()), 6) if not vals.dropna().empty else np.nan,
            "method_note": METHOD_NOTE,
            "interpretation_boundary": BOUNDARY_TEXT,
        })
    return pd.DataFrame(rows)


def lookup_thresholds(ref: pd.DataFrame) -> dict[str, dict[str, float | str]]:
    out: dict[str, dict[str, float | str]] = {}
    for _, row in ref.iterrows():
        out[str(row["metric"])] = {
            "direction": str(row["direction"]),
            "p25": row["p25"],
            "p75": row["p75"],
            "flag": str(row["attention_flag_name"]),
        }
    return out


def metric_flags(row: pd.Series, thresholds: dict[str, dict[str, float | str]]) -> tuple[str, str, str, str]:
    movement_flags: list[str] = []
    load_flags: list[str] = []
    weather_flags: list[str] = []
    hr_flags: list[str] = []

    for metric, meta in thresholds.items():
        if metric not in row.index:
            continue
        value = row.get(metric)
        if pd.isna(value):
            continue
        direction = str(meta["direction"])
        p25 = meta.get("p25")
        p75 = meta.get("p75")
        flag = str(meta["flag"])

        triggered = False
        if direction == "lower_is_attention" and pd.notna(p25) and value <= float(p25):
            triggered = True
        elif direction == "higher_is_attention" and pd.notna(p75) and value >= float(p75):
            triggered = True

        if not triggered:
            continue

        if "SPEED" in flag or "STOPPED" in flag:
            movement_flags.append(flag)
        elif "UPHILL_LOAD" in flag or "ROUTE_LOAD_BEHAVIOR" in flag:
            load_flags.append(flag)
        elif "WEATHER" in flag:
            weather_flags.append(flag)
        elif "HR" in flag:
            hr_flags.append(flag)
        else:
            movement_flags.append(flag)

    return (
        pipe_flags(movement_flags),
        pipe_flags(load_flags),
        pipe_flags(weather_flags),
        pipe_flags(hr_flags),
    )


def match_review_level(flags: str) -> str:
    if not flags or flags == "NONE" or flags == "NO_PERSONAL_ROUTE_LOAD_MATCH_ATTENTION_FLAG":
        return "PERSONAL_ROUTE_LOAD_MATCH_REFERENCE_RANGE"
    parts = [p for p in str(flags).split("|") if p and p != "NONE"]
    n = len(parts)
    if n >= 5:
        return "PERSONAL_ROUTE_LOAD_MATCH_MULTI_FACTOR_ATTENTION"
    if n >= 3:
        return "PERSONAL_ROUTE_LOAD_MATCH_MODERATE_ATTENTION"
    return "PERSONAL_ROUTE_LOAD_MATCH_SINGLE_FACTOR_ATTENTION"


def match_context_status(row: pd.Series) -> str:
    status = str(row.get("context_completeness_gate_status", ""))
    if status.startswith("READINESS_CONTEXT_COMPLETE"):
        return "PERSONAL_ROUTE_LOAD_MATCH_CONTEXT_READY_FOR_COMPARISON"
    return "PERSONAL_ROUTE_LOAD_MATCH_CONTEXT_INCOMPLETE_REVIEW_REQUIRED"


def build_match_review(
    context_gate: pd.DataFrame,
    activity_attention: pd.DataFrame,
    reference: pd.DataFrame,
    args: argparse.Namespace,
) -> pd.DataFrame:
    require_columns(context_gate, ["activity_id_short", "context_completeness_gate_status"], "context gate")
    require_columns(activity_attention, ["activity_id_short"], "activity attention")

    cg = context_gate.copy()
    aa = activity_attention.copy()
    cg["activity_id_short"] = clean_str(cg["activity_id_short"])
    aa["activity_id_short"] = clean_str(aa["activity_id_short"])

    # Activity attention is the richer table. Merge neutral gate columns from context gate.
    gate_cols = [
        "activity_id_short",
        "context_completeness_gate_status",
        "relative_attention_review_level",
        "relative_attention_review_flags",
        "previous_readiness_review_gate_status",
        "previous_readiness_review_gate_flags",
    ]
    gate_small = cg[[c for c in gate_cols if c in cg.columns]].copy()
    merged = aa.merge(gate_small, on="activity_id_short", how="left", suffixes=("", "_from_context_gate"))

    for col in [
        "context_completeness_gate_status",
        "relative_attention_review_level",
        "relative_attention_review_flags",
        "previous_readiness_review_gate_status",
        "previous_readiness_review_gate_flags",
    ]:
        alt = f"{col}_from_context_gate"
        if col not in merged.columns and alt in merged.columns:
            merged[col] = merged[alt]
        elif col in merged.columns and alt in merged.columns:
            merged[col] = merged[col].fillna(merged[alt])

    numeric_cols = [m[0] for m in REFERENCE_METRICS] + [
        "windows_n",
        "high_or_very_high_route_load_ratio",
        "uphill_ratio",
        "downhill_ratio",
        "conservative_weather_review_required_ratio",
        "weather_context_available_ratio",
    ]
    for col in numeric_cols:
        if col in merged.columns:
            merged[col] = numeric(merged[col])

    thresholds = lookup_thresholds(reference)
    flag_tuples = merged.apply(lambda row: metric_flags(row, thresholds), axis=1)
    merged["movement_behavior_match_flags"] = [t[0] for t in flag_tuples]
    merged["route_load_exposure_match_flags"] = [t[1] for t in flag_tuples]
    merged["weather_behavior_overlap_match_flags"] = [t[2] for t in flag_tuples]
    merged["heart_rate_context_match_flags"] = [t[3] for t in flag_tuples]

    merged["personal_route_load_match_review_flags"] = merged.apply(
        lambda row: pipe_flags([
            row.get("movement_behavior_match_flags"),
            row.get("route_load_exposure_match_flags"),
            row.get("weather_behavior_overlap_match_flags"),
            row.get("heart_rate_context_match_flags"),
        ]),
        axis=1,
    )
    merged["personal_route_load_match_review_flags"] = merged["personal_route_load_match_review_flags"].replace(
        {"NONE": "NO_PERSONAL_ROUTE_LOAD_MATCH_ATTENTION_FLAG"}
    )
    merged["personal_route_load_match_review_level"] = merged["personal_route_load_match_review_flags"].apply(match_review_level)
    merged["personal_route_load_match_context_status"] = merged.apply(match_context_status, axis=1)

    merged["normal_hiking_response_note"] = NORMAL_RESPONSE_NOTE
    merged["method_note"] = METHOD_NOTE
    merged["interpretation_boundary"] = BOUNDARY_TEXT

    keep_cols = [
        "profile_id",
        "route_folder",
        "activity_id_short",
        "personal_route_load_match_context_status",
        "personal_route_load_match_review_level",
        "personal_route_load_match_review_flags",
        "movement_behavior_match_flags",
        "route_load_exposure_match_flags",
        "weather_behavior_overlap_match_flags",
        "heart_rate_context_match_flags",
        "context_completeness_gate_status",
        "relative_attention_review_level",
        "relative_attention_review_flags",
        "previous_readiness_review_gate_status",
        "windows_n",
        "route_load_context_bands_observed",
        "route_phases_observed",
        "weather_context_classes_observed",
        "speed_mps_median_median",
        "speed_mps_median_p25",
        "speed_mps_median_p75",
        "low_speed_ratio_avg",
        "stopped_ratio_avg",
        "heart_rate_bpm_median_avg",
        "heart_rate_bpm_median_median",
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
    for col in ["profile_id", "route_folder"]:
        if col not in merged.columns:
            merged[col] = args.profile_id if col == "profile_id" else args.route_folder
    out = merged[[c for c in keep_cols if c in merged.columns]].copy()
    return out.sort_values("activity_id_short").reset_index(drop=True)


def build_group_summary(match: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    rows = []
    for level, group in match.groupby("personal_route_load_match_review_level", dropna=False):
        rows.append({
            "profile_id": args.profile_id,
            "route_folder": args.route_folder,
            "personal_route_load_match_review_level": level,
            "activity_count": int(group["activity_id_short"].nunique()),
            "activity_id_short_list": "|".join(sorted(group["activity_id_short"].astype(str).tolist())),
            "windows_n": int(numeric(group.get("windows_n", pd.Series(dtype=float))).sum()),
            "speed_mps_median_median_avg": round(mean(group.get("speed_mps_median_median", pd.Series(dtype=float))), 6),
            "low_speed_ratio_avg": round(mean(group.get("low_speed_ratio_avg", pd.Series(dtype=float))), 6),
            "stopped_ratio_avg": round(mean(group.get("stopped_ratio_avg", pd.Series(dtype=float))), 6),
            "heart_rate_bpm_median_avg": round(mean(group.get("heart_rate_bpm_median_avg", pd.Series(dtype=float))), 6),
            "uphill_high_route_load_ratio_avg": round(mean(group.get("uphill_high_route_load_ratio", pd.Series(dtype=float))), 6),
            "behavior_weather_context_review_required_ratio_avg": round(mean(group.get("behavior_weather_context_review_required_ratio", pd.Series(dtype=float))), 6),
            "match_flags_observed": pipe_flags(group["personal_route_load_match_review_flags"].astype(str).tolist()),
            "interpretation_boundary": BOUNDARY_TEXT,
        })
    return pd.DataFrame(rows).sort_values("personal_route_load_match_review_level").reset_index(drop=True) if rows else pd.DataFrame()


def build_dimension_summary(match: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    rows = []
    dim_cols = [
        ("movement_behavior_match_flags", "movement_behavior"),
        ("route_load_exposure_match_flags", "route_load_exposure"),
        ("weather_behavior_overlap_match_flags", "weather_behavior_overlap"),
        ("heart_rate_context_match_flags", "heart_rate_context"),
    ]
    for col, dim in dim_cols:
        if col not in match.columns:
            continue
        for flags, group in match.groupby(col, dropna=False):
            rows.append({
                "profile_id": args.profile_id,
                "route_folder": args.route_folder,
                "dimension": dim,
                "dimension_flags": flags if str(flags).strip() else "NONE",
                "activity_count": int(group["activity_id_short"].nunique()),
                "activity_id_short_list": "|".join(sorted(group["activity_id_short"].astype(str).tolist())),
                "interpretation_boundary": BOUNDARY_TEXT,
            })
    return pd.DataFrame(rows).sort_values(["dimension", "activity_count"], ascending=[True, False]).reset_index(drop=True) if rows else pd.DataFrame()


def build_data_quality(
    source_inventory: pd.DataFrame,
    match: pd.DataFrame,
    reference: pd.DataFrame,
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
        "check_name": "match_rows_present",
        "check_status": "PASS" if len(match) > 0 else "REVIEW_REQUIRED_NO_MATCH_ROWS",
        "check_value": int(len(match)),
        "details": "per-activity personal route-load match review rows generated",
    })

    ready_n = int(match["personal_route_load_match_context_status"].astype(str).str.contains("READY_FOR_COMPARISON", na=False).sum()) if not match.empty else 0
    rows.append({
        "profile_id": args.profile_id,
        "route_folder": args.route_folder,
        "check_name": "context_ready_for_comparison",
        "check_status": "PASS" if ready_n == len(match) and len(match) > 0 else "REVIEW_REQUIRED_CONTEXT_NOT_READY_FOR_ALL",
        "check_value": ready_n,
        "details": f"ready_n={ready_n};total={len(match)}",
    })

    level_count = int(match["personal_route_load_match_review_level"].nunique()) if not match.empty else 0
    rows.append({
        "profile_id": args.profile_id,
        "route_folder": args.route_folder,
        "check_name": "match_review_level_differentiation",
        "check_status": "PASS" if level_count >= 2 else "PASS_WITH_SINGLE_MATCH_LEVEL",
        "check_value": level_count,
        "details": pipe_flags(match["personal_route_load_match_review_level"].astype(str).tolist()) if not match.empty else "NONE",
    })

    rows.append({
        "profile_id": args.profile_id,
        "route_folder": args.route_folder,
        "check_name": "reference_thresholds_generated",
        "check_status": "PASS" if len(reference) == len(REFERENCE_METRICS) else "REVIEW_REQUIRED_REFERENCE_THRESHOLDS_INCOMPLETE",
        "check_value": int(len(reference)),
        "details": f"expected={len(REFERENCE_METRICS)}",
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
        return "REVIEW_REQUIRED_CH6_5_4_PERSONAL_ROUTE_LOAD_MATCH_REVIEW_V1"
    if any(s.startswith("REVIEW_REQUIRED") for s in statuses):
        return "REVIEW_REQUIRED_CH6_5_4_PERSONAL_ROUTE_LOAD_MATCH_REVIEW_V1"
    return "PASS_CH6_5_4_PERSONAL_ROUTE_LOAD_MATCH_REVIEW_V1_DESCRIPTIVE_ONLY"


def write_run_report(
    path: Path,
    source_inventory: pd.DataFrame,
    match: pd.DataFrame,
    group_summary: pd.DataFrame,
    dimension_summary: pd.DataFrame,
    reference: pd.DataFrame,
    data_quality: pd.DataFrame,
    conclusion: str,
    args: argparse.Namespace,
) -> None:
    lines = [
        "# CH6.5.4 Personal Route-Load Match Review v1",
        "",
        f"- profile_id: `{args.profile_id}`",
        f"- route_folder: `{args.route_folder}`",
        f"- activity_count: `{match['activity_id_short'].nunique() if not match.empty else 0}`",
        f"- match_rows: `{len(match)}`",
        f"- match_level_count: `{match['personal_route_load_match_review_level'].nunique() if not match.empty else 0}`",
        f"- group_summary_rows: `{len(group_summary)}`",
        f"- dimension_summary_rows: `{len(dimension_summary)}`",
        f"- reference_threshold_rows: `{len(reference)}`",
        f"- audit_conclusion: `{conclusion}`",
        "",
        "## Method",
        "",
        "- Uses CH6.5.3 v1.1 context gate as upstream context.",
        "- Compares each activity to the current activity-group reference ranges.",
        "- Flags indicate relative match-review context only; they are not scores or suitability decisions.",
        "",
        "## Sources",
        "",
    ]
    for _, row in source_inventory.iterrows():
        lines.append(f"- {row['source_label']}: `{row['source_path']}` exists={row['exists']} bytes={row['length_bytes']}")

    lines.extend(["", "## Match review distribution", ""])
    for _, row in group_summary.iterrows():
        lines.append(
            f"- {row['personal_route_load_match_review_level']}: "
            f"activities={row['activity_count']}; windows={row['windows_n']}"
        )

    lines.extend(["", "## Data quality", ""])
    for _, row in data_quality.iterrows():
        lines.append(f"- {row['check_name']}: {row['check_status']} ({row['details']})")

    lines.extend(["", "## Normal-response note", "", NORMAL_RESPONSE_NOTE, "", "## Boundary", "", BOUNDARY_TEXT, ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    output_root = resolve(root, args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    paths = {
        "ch6_5_3_v1_1_context_gate": resolve(root, args.context_gate),
        "ch6_5_3_v1_1_activity_attention": resolve(root, args.activity_attention),
        "ch6_5_3_v1_1_audit": resolve(root, args.context_audit),
        "ch6_5_3_v1_1_data_quality": resolve(root, args.context_data_quality),
    }
    source_inventory = build_source_inventory(paths)

    context_gate = read_csv(paths["ch6_5_3_v1_1_context_gate"], "CH6.5.3 v1.1 context gate", required=True)
    activity_attention = read_csv(paths["ch6_5_3_v1_1_activity_attention"], "CH6.5.3 v1.1 activity attention", required=True)
    _context_audit = read_csv(paths["ch6_5_3_v1_1_audit"], "CH6.5.3 v1.1 audit", required=False)
    _context_dq = read_csv(paths["ch6_5_3_v1_1_data_quality"], "CH6.5.3 v1.1 data quality", required=False)

    reference = build_reference_thresholds(activity_attention, args)
    match = build_match_review(context_gate, activity_attention, reference, args)
    group_summary = build_group_summary(match, args)
    dimension_summary = build_dimension_summary(match, args)

    output_paths = {
        "match_review": output_root / "personal_route_load_match_review_v1.csv",
        "group_summary": output_root / "personal_route_load_match_group_summary_v1.csv",
        "dimension_summary": output_root / "personal_route_load_match_dimension_summary_v1.csv",
        "reference_thresholds": output_root / "personal_route_load_match_reference_thresholds_v1.csv",
        "data_quality": output_root / "personal_route_load_match_data_quality_v1.csv",
        "audit": output_root / "personal_route_load_match_audit_v1.csv",
        "run_report": output_root / "personal_route_load_match_run_report_v1.md",
    }

    output_fields = {
        "match": list(match.columns),
        "group_summary": list(group_summary.columns),
        "dimension_summary": list(dimension_summary.columns),
        "reference": list(reference.columns),
    }
    data_quality = build_data_quality(source_inventory, match, reference, output_fields, args)
    conclusion = audit_conclusion(data_quality)

    audit = pd.DataFrame([{
        "profile_id": args.profile_id,
        "route_folder": args.route_folder,
        "activity_count": int(match["activity_id_short"].nunique()) if not match.empty else 0,
        "match_rows": int(len(match)),
        "match_review_level_count": int(match["personal_route_load_match_review_level"].nunique()) if not match.empty else 0,
        "group_summary_rows": int(len(group_summary)),
        "dimension_summary_rows": int(len(dimension_summary)),
        "reference_threshold_rows": int(len(reference)),
        "context_ready_for_comparison_n": int(match["personal_route_load_match_context_status"].astype(str).str.contains("READY_FOR_COMPARISON", na=False).sum()) if not match.empty else 0,
        "source_files_available_n": int(source_inventory["exists"].sum()),
        "source_files_expected_n": int(len(source_inventory)),
        "audit_conclusion": conclusion,
        "normal_hiking_response_note": NORMAL_RESPONSE_NOTE,
        "interpretation_boundary": BOUNDARY_TEXT,
    }])

    match.to_csv(output_paths["match_review"], index=False, encoding="utf-8-sig")
    group_summary.to_csv(output_paths["group_summary"], index=False, encoding="utf-8-sig")
    dimension_summary.to_csv(output_paths["dimension_summary"], index=False, encoding="utf-8-sig")
    reference.to_csv(output_paths["reference_thresholds"], index=False, encoding="utf-8-sig")
    data_quality.to_csv(output_paths["data_quality"], index=False, encoding="utf-8-sig")
    audit.to_csv(output_paths["audit"], index=False, encoding="utf-8-sig")
    write_run_report(
        output_paths["run_report"],
        source_inventory,
        match,
        group_summary,
        dimension_summary,
        reference,
        data_quality,
        conclusion,
        args,
    )

    print({
        "output_root": str(output_root),
        "profile_id": args.profile_id,
        "activity_count": int(match["activity_id_short"].nunique()) if not match.empty else 0,
        "match_rows": int(len(match)),
        "match_review_level_count": int(match["personal_route_load_match_review_level"].nunique()) if not match.empty else 0,
        "group_summary_rows": int(len(group_summary)),
        "dimension_summary_rows": int(len(dimension_summary)),
        "reference_threshold_rows": int(len(reference)),
        "context_ready_for_comparison_n": int(match["personal_route_load_match_context_status"].astype(str).str.contains("READY_FOR_COMPARISON", na=False).sum()) if not match.empty else 0,
        "source_files_available_n": int(source_inventory["exists"].sum()),
        "source_files_expected_n": int(len(source_inventory)),
        "audit_conclusion": conclusion,
        "outputs": {k: str(v) for k, v in output_paths.items()},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
