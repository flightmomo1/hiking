#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build CH6.5.5 personal ability radar data table v1.

This script converts the personal ability radar axis contract plus activity/person
evidence into a governed radar data table.

It does not create a radar plot. It does not compute radar scores, ability scores,
ability ranks, ability classes, THCI scores, final hiking risk scores, route
suitability scores, go/no-go decisions, medical diagnoses, or causality claims.
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_AXIS_CONTRACT_ROOT = "outputs/report_figures/ch6_5_5_personal_ability_radar_axis_contract_v1"
DEFAULT_OUTPUT_ROOT = "outputs/report_figures/ch6_5_5_personal_ability_radar_data_table_v1"

BOUNDARY = (
    "CH6.5.5 personal ability radar data table v1 is a governed data-table layer only. "
    "It converts an axis contract and activity/person evidence into per-activity per-axis "
    "rows for future visualization. It does not create a radar plot and does not compute or "
    "authorize radar scores, ability scores, ability ranks, ability classes, THCI scores, "
    "final hiking risk scores, route suitability scores, go/no-go decisions, medical diagnoses, "
    "or causality claims."
)

PASS = "PASS_CH6_5_5_PERSONAL_ABILITY_RADAR_DATA_TABLE_V1_GOVERNED_TABLE_ONLY"
REVIEW = "REVIEW_REQUIRED_CH6_5_5_PERSONAL_ABILITY_RADAR_DATA_TABLE_V1"

FORBIDDEN_OUTPUT_PATTERNS = [
    "radar_score",
    "ability_score",
    "ability_rank",
    "ability_class",
    "go_no_go",
    "medical_diagnosis",
    "causality_claim",
]

ACTIVITY_SOURCE_CANDIDATES = [
    "outputs/report_figures/ch6_5_5_personal_profile_metadata_join_v0_2/personal_profile_metadata_join_v0_2.csv",
    "outputs/report_figures/**/personal_profile_metadata_join_v0_2.csv",
]

EVIDENCE_FILES = {
    "axis_contract": [
        "outputs/report_figures/ch6_5_5_personal_ability_radar_axis_contract_v1/personal_ability_radar_axis_contract_v1.csv",
    ],
    "axis_evidence_inventory": [
        "outputs/report_figures/ch6_5_5_personal_ability_radar_axis_contract_v1/personal_ability_radar_axis_evidence_inventory_v1.csv",
    ],
    "axis_contract_audit": [
        "outputs/report_figures/ch6_5_5_personal_ability_radar_axis_contract_v1/personal_ability_radar_axis_contract_audit_v1.csv",
    ],
    "movement_300s_activity_coverage": [
        "outputs/report_figures/ch6_5_5_300s_movement_evidence_admission_review_v1/movement_300s_admission_activity_coverage_v1.csv",
    ],
    "movement_300s_consumption_activity_summary": [
        "outputs/report_figures/ch6_5_5_300s_movement_qa_gate_consumption_v1/movement_300s_consumption_activity_summary_v1.csv",
    ],
    "movement_300s_consumption_audit": [
        "outputs/report_figures/ch6_5_5_300s_movement_qa_gate_consumption_v1/movement_300s_consumption_audit_v1.csv",
    ],
    "radar_baseline_axis_table": [
        "outputs/script_inputs/ch6_5_5_radar_v1_axis_refinement_input_pack_v1/radar_baseline/personal_activity_performance_radar_report_safe_axis_table_v1_terrain_axis.csv",
        "outputs/report_figures/**/personal_activity_performance_radar_report_safe_axis_table_v1_terrain_axis.csv",
    ],
    "pacing_movement_stability_axis": [
        "outputs/report_figures/ch6_5_5_pacing_movement_stability_axis_v1/pacing_movement_stability_axis_v1.csv",
        "outputs/report_figures/**/pacing_movement_stability_axis*.csv",
    ],
    "terrain_movement_efficiency_axis": [
        "outputs/report_figures/**/terrain_movement_efficiency_axis_update*.csv",
        "outputs/report_figures/**/terrain_movement_efficiency*axis*.csv",
        "outputs/report_figures/**/terrain_movement_efficiency*admission*audit*.csv",
    ],
    "route_load_readiness_review": [
        "outputs/report_figures/ch6_8_personal_route_load_readiness_review_v1_1/personal_route_load_readiness_review_v1_1.csv",
        "outputs/report_figures/**/personal_route_load_readiness_review*.csv",
    ],
    "weather_context_summary": [
        "outputs/report_figures/ch6_report_figures_v1_2/ch6_4_weather_context_summary_v1_2.csv",
        "outputs/report_figures/**/ch6_4_weather_context_summary*.csv",
    ],
    "hr_lifecycle_summary": [
        "outputs/report_figures/**/activity_hr_lifecycle_summary*.csv",
        "outputs/report_figures/**/activity_hr_recovery_activity_summary*.csv",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=r"D:\mountain_work\115_osm")
    parser.add_argument("--axis-contract-root", default=DEFAULT_AXIS_CONTRACT_ROOT)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    p = Path(value)
    return p if p.is_absolute() else root / p


def find_first(root: Path, patterns: list[str]) -> Path | None:
    for pattern in patterns:
        if "**" in pattern:
            hits = sorted(root.glob(pattern))
            hits = [h for h in hits if h.is_file()]
            if hits:
                return hits[0]
        else:
            p = resolve(root, pattern)
            if p.exists() and p.is_file():
                return p
    return None


def read_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def read_csv_optional(path: Path | None) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame()
    try:
        return read_csv(path, str(path))
    except Exception:
        return pd.DataFrame()


def to_num(value: Any) -> float:
    try:
        if pd.isna(value):
            return np.nan
        return float(value)
    except Exception:
        return np.nan


def as_blank_if_nan(value: Any) -> Any:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return value


def first_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lower_map = {str(c).lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in lower_map:
            return lower_map[c.lower()]
    return None


def load_evidence_map(root: Path) -> dict[str, tuple[Path | None, pd.DataFrame]]:
    out: dict[str, tuple[Path | None, pd.DataFrame]] = {}
    for key, patterns in EVIDENCE_FILES.items():
        p = find_first(root, patterns)
        out[key] = (p, read_csv_optional(p))
    return out


def rel_path(root: Path, path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(root))
    except Exception:
        return str(path)


def build_activity_table(root: Path, evidence: dict[str, tuple[Path | None, pd.DataFrame]]) -> pd.DataFrame:
    profile_path = find_first(root, ACTIVITY_SOURCE_CANDIDATES)
    profile = read_csv_optional(profile_path)
    cov_path, cov = evidence.get("movement_300s_activity_coverage", (None, pd.DataFrame()))

    rows: list[dict[str, Any]] = []

    def append_rows(src: pd.DataFrame, source_path: Path | None, default_status: str) -> None:
        if src.empty:
            return
        activity_col = first_col(src, ["activity_id_short", "activity_id", "activity"])
        if activity_col is None:
            return
        participant_col = first_col(
            src,
            [
                "participant_id",
                "participant_id_short",
                "person_id",
                "subject_id",
                "user_id",
                "athlete_id",
                "member_id",
                "participant_code",
                "profile_id",
            ],
        )
        for _, r in src.iterrows():
            activity = str(r.get(activity_col, "")).strip()
            if not activity:
                continue
            if participant_col is not None and str(r.get(participant_col, "")).strip():
                participant = str(r.get(participant_col, "")).strip()
                participant_source = participant_col
            else:
                participant = activity
                participant_source = "fallback_activity_id_short"

            status = str(r.get("study_population_status", "")).strip() or default_status
            rows.append({
                "participant_id": participant,
                "participant_id_source": participant_source,
                "activity_id_short": activity,
                "study_population_status": status,
                "activity_source": rel_path(root, source_path),
            })

    append_rows(profile, profile_path, "RADAR_BASELINE_ACTIVITY")
    append_rows(cov, cov_path, "")

    if not rows:
        raise RuntimeError("No activity/person source available.")

    out = pd.DataFrame(rows)
    if not cov.empty and "activity_id_short" in cov.columns and "study_population_status" in cov.columns:
        status_map = cov.set_index(cov["activity_id_short"].astype(str))["study_population_status"].astype(str).to_dict()
        out["study_population_status"] = out.apply(
            lambda r: status_map.get(str(r["activity_id_short"]), r["study_population_status"]) or "RADAR_BASELINE_ACTIVITY",
            axis=1,
        )

    out["population_sort"] = np.where(out["study_population_status"].eq("RADAR_BASELINE_ACTIVITY"), 0, 1)
    out = out.sort_values(["population_sort", "participant_id", "activity_id_short", "activity_source"], kind="mergesort")
    out = out.drop_duplicates(subset=["activity_id_short"], keep="first").drop(columns=["population_sort"])
    return out.reset_index(drop=True)


def lookup_activity_row(df: pd.DataFrame, activity_id_short: str) -> dict[str, Any]:
    if df.empty:
        return {}
    activity_col = first_col(df, ["activity_id_short", "activity_id", "activity"])
    if activity_col is None:
        return {}
    hit = df[df[activity_col].astype(str).eq(str(activity_id_short))]
    if hit.empty:
        return {}
    return hit.iloc[0].to_dict()


def find_proxy_value(
    df: pd.DataFrame,
    activity_id_short: str,
    axis_id: str,
    axis_label_zh: str,
) -> tuple[Any, str, str]:
    """Best-effort proxy value extraction.

    Returns (value, unit, source_field). If no confident numeric field is found,
    returns ("", "", "").
    """
    if df.empty:
        return "", "", ""

    activity_col = first_col(df, ["activity_id_short", "activity_id", "activity"])
    if activity_col is not None:
        candidate = df[df[activity_col].astype(str).eq(str(activity_id_short))].copy()
    else:
        candidate = df.copy()

    if candidate.empty:
        return "", "", ""

    axis_col = first_col(df, ["axis_id", "axis", "axis_name", "axis_label_zh", "axis_label"])
    if axis_col is not None:
        axis_hit = candidate[
            candidate[axis_col].astype(str).str.contains(axis_id, case=False, na=False)
            | candidate[axis_col].astype(str).str.contains(axis_label_zh, case=False, na=False)
        ]
        if not axis_hit.empty:
            candidate = axis_hit

    value_candidates = [
        "axis_value",
        "proxy_value",
        "axis_group_relative_index_0_100",
        "normalized_value",
        "index_value",
        "value",
    ]

    for col in value_candidates:
        c = first_col(candidate, [col])
        if c is not None:
            vals = pd.to_numeric(candidate[c], errors="coerce").dropna()
            if len(vals):
                return float(vals.iloc[0]), "proxy_index_0_100", c

    axis_tokens = {
        "terrain_movement_efficiency": ["terrain", "efficiency"],
        "pacing_movement_stability": ["pacing", "stability"],
    }.get(axis_id, [])

    if axis_tokens:
        for c in candidate.columns:
            lower = str(c).lower()
            if all(t in lower for t in axis_tokens):
                vals = pd.to_numeric(candidate[c], errors="coerce").dropna()
                if len(vals):
                    return float(vals.iloc[0]), "proxy_index_0_100", c

    return "", "", ""


def annotation_for_axis(
    root: Path,
    axis: dict[str, Any],
    activity: dict[str, Any],
    evidence: dict[str, tuple[Path | None, pd.DataFrame]],
) -> tuple[str, str, str]:
    axis_id = str(axis.get("axis_id", ""))
    activity_id = str(activity.get("activity_id_short", ""))

    movement_cov_path, movement_cov = evidence.get("movement_300s_activity_coverage", (None, pd.DataFrame()))
    movement_cons_path, movement_cons = evidence.get("movement_300s_consumption_activity_summary", (None, pd.DataFrame()))
    route_path, route_load = evidence.get("route_load_readiness_review", (None, pd.DataFrame()))
    weather_path, weather = evidence.get("weather_context_summary", (None, pd.DataFrame()))
    hr_path, hr = evidence.get("hr_lifecycle_summary", (None, pd.DataFrame()))

    cov_row = lookup_activity_row(movement_cov, activity_id)
    cons_row = lookup_activity_row(movement_cons, activity_id)
    route_row = lookup_activity_row(route_load, activity_id)
    weather_row = lookup_activity_row(weather, activity_id)
    hr_row = lookup_activity_row(hr, activity_id)

    if axis_id == "endurance_sustained_movement":
        h_count = as_blank_if_nan(cov_row.get("horizontal_300s_valid_window_count", ""))
        h_p90 = as_blank_if_nan(cov_row.get("horizontal_300s_route_speed_p90_mps", ""))
        c_count = as_blank_if_nan(cons_row.get("horizontal_consumable_window_count", ""))
        text = (
            "300s horizontal evidence is descriptive only. "
            f"valid_windows={h_count}; consumable_windows={c_count}; p90_speed_mps={h_p90}."
        )
        return text, rel_path(root, movement_cov_path), "horizontal_300s_valid_window_count|horizontal_300s_route_speed_p90_mps|horizontal_consumable_window_count"

    if axis_id == "uphill_load_tolerance":
        v_count = as_blank_if_nan(cov_row.get("vertical_300s_valid_window_count", ""))
        v_vam = as_blank_if_nan(cov_row.get("vertical_300s_vam_p90_mph", ""))
        v_gain = as_blank_if_nan(cov_row.get("vertical_300s_gain_p90_m", ""))
        c_count = as_blank_if_nan(cons_row.get("vertical_consumable_window_count", ""))
        text = (
            "300s vertical evidence is descriptive only. "
            f"valid_windows={v_count}; consumable_windows={c_count}; p90_vam_mph={v_vam}; p90_gain_m={v_gain}."
        )
        return text, rel_path(root, movement_cov_path), "vertical_300s_valid_window_count|vertical_300s_vam_p90_mph|vertical_300s_gain_p90_m|vertical_consumable_window_count"

    if axis_id == "hr_load_management_recovery":
        if hr_row:
            text = "HR lifecycle / recovery evidence exists for this activity; retained as non-medical context only."
        else:
            text = "HR lifecycle / recovery evidence is not available for this activity; retain as annotation only."
        return text, rel_path(root, hr_path), "activity_hr_lifecycle_summary|activity_hr_recovery"

    if axis_id == "weather_performance_maintenance":
        if weather_row:
            text = "Weather context evidence exists; retained as limited proxy / descriptive context only."
        else:
            text = "Weather context is available at summary level but not resolved to this activity row; retain as descriptive annotation."
        return text, rel_path(root, weather_path), "weather_context_summary"

    if axis_id == "autonomous_completion_readiness":
        if route_row:
            gate = as_blank_if_nan(route_row.get("readiness_review_gate", ""))
            completion = as_blank_if_nan(route_row.get("completion_time_min", ""))
            text = (
                "Route-load readiness / completion context exists; it is not proof of autonomous self-sufficiency. "
                f"readiness_review_gate={gate}; completion_time_min={completion}."
            )
        else:
            text = "Completion/readiness context not resolved to this activity row; retain as descriptive annotation."
        return text, rel_path(root, route_path), "personal_route_load_readiness_review|completion_time_min|readiness_review_gate"

    missing_reason = str(axis.get("missing_evidence_reason", "")).strip()
    if missing_reason:
        return missing_reason, str(axis.get("primary_evidence_source", "")), str(axis.get("primary_evidence_fields", ""))

    return str(axis.get("allowed_use", "")), str(axis.get("primary_evidence_source", "")), str(axis.get("primary_evidence_fields", ""))


def gate_status_for_axis(
    axis: dict[str, Any],
    activity: dict[str, Any],
    evidence: dict[str, tuple[Path | None, pd.DataFrame]],
) -> str:
    axis_id = str(axis.get("axis_id", ""))
    required = str(axis.get("required_consumption_gates", "")).strip()
    activity_id = str(activity.get("activity_id_short", ""))
    population = str(activity.get("study_population_status", ""))

    cons = evidence.get("movement_300s_consumption_activity_summary", (None, pd.DataFrame()))[1]
    cons_row = lookup_activity_row(cons, activity_id)

    parts = []
    if "baseline_population_gate" in required:
        parts.append("baseline_population_gate=PASS" if population == "RADAR_BASELINE_ACTIVITY" else "baseline_population_gate=BLOCKED_EXTRA_SOURCE")

    if "route_continuity_300s_gate" in required:
        h = to_num(cons_row.get("horizontal_consumable_window_count", np.nan))
        v = to_num(cons_row.get("vertical_consumable_window_count", np.nan))
        total = 0
        if not np.isnan(h):
            total += int(h)
        if not np.isnan(v):
            total += int(v)
        if axis_id == "endurance_sustained_movement":
            pass_gate = (not np.isnan(h)) and h > 0
            parts.append(f"route_continuity_300s_gate={'PASS_HORIZONTAL' if pass_gate else 'NO_CONSUMABLE_HORIZONTAL_WINDOW'}")
        elif axis_id == "uphill_load_tolerance":
            pass_gate = (not np.isnan(v)) and v > 0
            parts.append(f"route_continuity_300s_gate={'PASS_VERTICAL' if pass_gate else 'NO_CONSUMABLE_VERTICAL_WINDOW'}")
        else:
            parts.append(f"route_continuity_300s_gate=POLICY_ACTIVE_CONSUMABLE_WINDOWS_{total}")

    if "positive_delta_artifact_guard" in required:
        v = to_num(cons_row.get("vertical_consumable_window_count", np.nan))
        blocked = to_num(cons_row.get("positive_delta_artifact_blocked_window_count", np.nan))
        if not np.isnan(v) and v > 0:
            parts.append("positive_delta_artifact_guard=PASS_VERTICAL_CONSUMABLE")
        elif not np.isnan(blocked) and blocked > 0:
            parts.append("positive_delta_artifact_guard=BLOCKED_ARTIFACT_REVIEW")
        else:
            parts.append("positive_delta_artifact_guard=NO_VERTICAL_CONSUMABLE_WINDOW")

    if "hr_validity_gate" in required:
        hr_count = to_num(cons_row.get("hr_context_consumable_window_count", np.nan))
        parts.append("hr_validity_gate=CONTEXT_AVAILABLE" if not np.isnan(hr_count) and hr_count > 0 else "hr_validity_gate=NO_ACTIVITY_LEVEL_HR_CONTEXT")

    if "weather_context_gate" in required:
        parts.append("weather_context_gate=SUMMARY_CONTEXT_ONLY")

    return "|".join(parts) if parts else "NO_REQUIRED_GATE"


def build_data_table(
    root: Path,
    contract: pd.DataFrame,
    activities: pd.DataFrame,
    evidence: dict[str, tuple[Path | None, pd.DataFrame]],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    baseline_axis = evidence.get("radar_baseline_axis_table", (None, pd.DataFrame()))[1]
    pacing_axis = evidence.get("pacing_movement_stability_axis", (None, pd.DataFrame()))[1]
    terrain_axis = evidence.get("terrain_movement_efficiency_axis", (None, pd.DataFrame()))[1]

    for _, a in activities.iterrows():
        activity = a.to_dict()
        for _, x in contract.iterrows():
            axis = x.to_dict()
            axis_id = str(axis.get("axis_id", ""))
            axis_mode = str(axis.get("axis_output_mode", ""))
            permission = str(axis.get("radar_output_permission", ""))

            axis_value_allowed = axis_mode in {"NUMERIC_AXIS", "LIMITED_PROXY_AXIS"}
            axis_value: Any = ""
            axis_unit = ""
            value_source_field = ""

            if axis_mode == "LIMITED_PROXY_AXIS":
                if axis_id == "terrain_movement_efficiency":
                    value, unit, field = find_proxy_value(terrain_axis, activity["activity_id_short"], axis_id, str(axis.get("axis_label_zh", "")))
                    if value == "":
                        value, unit, field = find_proxy_value(baseline_axis, activity["activity_id_short"], axis_id, str(axis.get("axis_label_zh", "")))
                    axis_value, axis_unit, value_source_field = value, unit, field
                elif axis_id == "pacing_movement_stability":
                    value, unit, field = find_proxy_value(pacing_axis, activity["activity_id_short"], axis_id, str(axis.get("axis_label_zh", "")))
                    if value == "":
                        value, unit, field = find_proxy_value(baseline_axis, activity["activity_id_short"], axis_id, str(axis.get("axis_label_zh", "")))
                    axis_value, axis_unit, value_source_field = value, unit, field

            annotation, evidence_source, evidence_fields = annotation_for_axis(root, axis, activity, evidence)

            if axis_mode == "LIMITED_PROXY_AXIS":
                if axis_value == "":
                    annotation = f"LIMITED_PROXY_AXIS; proxy value not confidently extracted in v1; {annotation}"
                else:
                    annotation = f"LIMITED_PROXY_AXIS; proxy_value_source_field={value_source_field}; {annotation}"
            elif axis_mode in {"DESCRIPTIVE_ANNOTATION", "MISSING_EVIDENCE_ANNOTATION", "EXCLUDED_FROM_RADAR"}:
                axis_value_allowed = False
                axis_value = ""
                axis_unit = ""
                if axis_mode == "MISSING_EVIDENCE_ANNOTATION":
                    annotation = str(axis.get("missing_evidence_reason", "")) or annotation

            rows.append({
                "participant_id": activity.get("participant_id", ""),
                "activity_id_short": activity.get("activity_id_short", ""),
                "study_population_status": activity.get("study_population_status", ""),
                "axis_id": axis_id,
                "axis_label_zh": axis.get("axis_label_zh", ""),
                "axis_status": axis.get("axis_status", ""),
                "axis_output_mode": axis_mode,
                "radar_output_permission": permission,
                "axis_value_allowed": bool(axis_value_allowed and axis_value != ""),
                "axis_value": axis_value,
                "axis_value_unit": axis_unit,
                "axis_annotation": annotation,
                "evidence_source": evidence_source,
                "evidence_fields": evidence_fields,
                "required_gate_status": gate_status_for_axis(axis, activity, evidence),
                "fallback_status": axis.get("fallback_status", ""),
                "missing_evidence_reason": axis.get("missing_evidence_reason", ""),
                "allowed_use": axis.get("allowed_use", ""),
                "disallowed_use": axis.get("disallowed_use", ""),
                "interpretation_boundary": BOUNDARY,
            })

    return pd.DataFrame(rows)


def build_audit(contract_audit: pd.DataFrame, activities: pd.DataFrame, table: pd.DataFrame) -> pd.DataFrame:
    forbidden_cols = [c for c in table.columns if any(p in c.lower() for p in FORBIDDEN_OUTPUT_PATTERNS)]

    descriptive_value_violation = int(
        ((table["axis_output_mode"].astype(str).eq("DESCRIPTIVE_ANNOTATION")) & (table["axis_value"].astype(str).str.len() > 0)).sum()
    )
    missing_value_violation = int(
        ((table["axis_output_mode"].astype(str).eq("MISSING_EVIDENCE_ANNOTATION")) & (table["axis_value"].astype(str).str.len() > 0)).sum()
    )
    missing_zero_violation = int(
        ((table["axis_output_mode"].astype(str).eq("MISSING_EVIDENCE_ANNOTATION")) & (table["axis_value"].astype(str).eq("0"))).sum()
    )
    limited_proxy_rows = table[table["axis_output_mode"].astype(str).eq("LIMITED_PROXY_AXIS")]
    limited_proxy_value_count = int(limited_proxy_rows["axis_value"].astype(str).str.len().gt(0).sum()) if not limited_proxy_rows.empty else 0

    review_reasons: list[str] = []
    if contract_audit.empty:
        review_reasons.append("MISSING_AXIS_CONTRACT_AUDIT")
    elif not str(contract_audit.iloc[0].get("audit_conclusion", "")).startswith("PASS_"):
        review_reasons.append("AXIS_CONTRACT_AUDIT_NOT_PASS")
    if forbidden_cols:
        review_reasons.append("FORBIDDEN_OUTPUT_FIELD_PRESENT")
    if descriptive_value_violation:
        review_reasons.append("DESCRIPTIVE_ANNOTATION_HAS_AXIS_VALUE")
    if missing_value_violation:
        review_reasons.append("MISSING_EVIDENCE_HAS_AXIS_VALUE")
    if missing_zero_violation:
        review_reasons.append("MISSING_EVIDENCE_ZERO_FILL_DETECTED")

    row = {
        "activity_count": int(len(activities)),
        "radar_data_table_row_count": int(len(table)),
        "axis_count": int(table["axis_id"].nunique()) if not table.empty else 0,
        "numeric_axis_row_count": int(table["axis_output_mode"].astype(str).eq("NUMERIC_AXIS").sum()) if not table.empty else 0,
        "limited_proxy_axis_row_count": int(table["axis_output_mode"].astype(str).eq("LIMITED_PROXY_AXIS").sum()) if not table.empty else 0,
        "limited_proxy_axis_value_count": limited_proxy_value_count,
        "descriptive_annotation_row_count": int(table["axis_output_mode"].astype(str).eq("DESCRIPTIVE_ANNOTATION").sum()) if not table.empty else 0,
        "missing_evidence_annotation_row_count": int(table["axis_output_mode"].astype(str).eq("MISSING_EVIDENCE_ANNOTATION").sum()) if not table.empty else 0,
        "descriptive_annotation_value_violation_count": descriptive_value_violation,
        "missing_evidence_value_violation_count": missing_value_violation,
        "missing_evidence_zero_fill_violation_count": missing_zero_violation,
        "zero_fill_used": False,
        "forbidden_score_rank_class_fields_present": bool(forbidden_cols),
        "forbidden_fields": "|".join(forbidden_cols) if forbidden_cols else "NONE",
        "radar_scoring_absent": True,
        "ability_scoring_absent": True,
        "ranking_absent": True,
        "class_label_absent": True,
        "decision_label_absent": True,
        "diagnosis_absent": True,
        "causal_claim_absent": True,
        "audit_conclusion": REVIEW if review_reasons else PASS,
        "review_reasons": "|".join(review_reasons) if review_reasons else "NONE",
        "interpretation_boundary": BOUNDARY,
    }
    return pd.DataFrame([row])


def write_html(out_path: Path, audit: pd.DataFrame, table: pd.DataFrame) -> None:
    def render_table(df: pd.DataFrame, cols: list[str], n: int = 120) -> str:
        if df.empty:
            return "<p>No rows.</p>"
        use = [c for c in cols if c in df.columns]
        return df[use].head(n).to_html(index=False, escape=True, classes="data")

    conclusion = audit.iloc[0]["audit_conclusion"] if not audit.empty else REVIEW
    body = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CH6.5.5 Personal Ability Radar Data Table v1</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2933; }}
h1, h2 {{ margin-bottom: 8px; }}
.boundary {{ border-left: 4px solid #687078; padding: 8px 12px; background: #f5f7f8; }}
.status {{ font-weight: 700; }}
table.data {{ border-collapse: collapse; font-size: 12px; margin: 12px 0 24px; }}
table.data th, table.data td {{ border: 1px solid #d6dde3; padding: 5px 7px; vertical-align: top; }}
table.data th {{ background: #eef2f5; }}
</style>
</head>
<body>
<h1>CH6.5.5 Personal Ability Radar Data Table v1</h1>
<p class="status">{html.escape(str(conclusion))}</p>
<p class="boundary">{html.escape(BOUNDARY)}</p>

<h2>Audit</h2>
{render_table(audit, list(audit.columns), 5)}

<h2>Data Table Preview</h2>
{render_table(table, ["participant_id", "activity_id_short", "axis_id", "axis_label_zh", "axis_output_mode", "axis_value_allowed", "axis_value", "axis_value_unit", "axis_annotation", "required_gate_status", "fallback_status"], 80)}
</body>
</html>
"""
    out_path.write_text(body, encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    out_root = resolve(root, args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)

    evidence = load_evidence_map(root)

    contract_path = resolve(root, f"{args.axis_contract_root}/personal_ability_radar_axis_contract_v1.csv")
    contract_audit_path = resolve(root, f"{args.axis_contract_root}/personal_ability_radar_axis_contract_audit_v1.csv")

    contract = read_csv(contract_path, "axis contract v1")
    contract_audit = read_csv(contract_audit_path, "axis contract audit v1")

    activities = build_activity_table(root, evidence)
    table = build_data_table(root, contract, activities, evidence)
    audit = build_audit(contract_audit, activities, table)

    outputs = {
        "data_table": out_root / "personal_ability_radar_data_table_v1.csv",
        "audit": out_root / "personal_ability_radar_data_table_audit_v1.csv",
        "html": out_root / "personal_ability_radar_data_table_report_v1.html",
    }

    table.to_csv(outputs["data_table"], index=False, encoding="utf-8-sig")
    audit.to_csv(outputs["audit"], index=False, encoding="utf-8-sig")
    write_html(outputs["html"], audit, table)

    print({
        "output_root": str(out_root),
        "activity_count": int(audit.iloc[0]["activity_count"]),
        "radar_data_table_row_count": int(audit.iloc[0]["radar_data_table_row_count"]),
        "axis_count": int(audit.iloc[0]["axis_count"]),
        "limited_proxy_axis_value_count": int(audit.iloc[0]["limited_proxy_axis_value_count"]),
        "descriptive_annotation_value_violation_count": int(audit.iloc[0]["descriptive_annotation_value_violation_count"]),
        "missing_evidence_value_violation_count": int(audit.iloc[0]["missing_evidence_value_violation_count"]),
        "missing_evidence_zero_fill_violation_count": int(audit.iloc[0]["missing_evidence_zero_fill_violation_count"]),
        "audit_conclusion": str(audit.iloc[0]["audit_conclusion"]),
        "outputs": {k: str(v) for k, v in outputs.items()},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
