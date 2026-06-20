#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build CH6.5.5 personal ability radar axis contract v1.

This script consolidates existing evidence layers into a governance contract for
a future personal hiking ability radar chart.

It does not compute radar scores, ability scores, ability ranks, ability classes,
THCI scores, final hiking risk scores, route suitability scores, go/no-go
decisions, medical diagnoses, or causality claims.
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_OUTPUT_ROOT = "outputs/report_figures/ch6_5_5_personal_ability_radar_axis_contract_v1"

BOUNDARY = (
    "CH6.5.5 personal ability radar axis contract v1 is an axis-governance layer only. "
    "It defines whether each proposed personal hiking ability axis may appear in a future "
    "radar chart and under what evidence / gate conditions. It does not compute or authorize "
    "radar scores, ability scores, ability ranks, ability classes, THCI scores, final hiking "
    "risk scores, route suitability scores, go/no-go decisions, medical diagnoses, or "
    "causality claims."
)

PASS = "PASS_CH6_5_5_PERSONAL_ABILITY_RADAR_AXIS_CONTRACT_V1_GOVERNANCE_ONLY"
REVIEW = "REVIEW_REQUIRED_CH6_5_5_PERSONAL_ABILITY_RADAR_AXIS_CONTRACT_V1"

FORBIDDEN_OUTPUT_PATTERNS = [
    "radar_score",
    "ability_score",
    "ability_rank",
    "ability_class",
    "go_no_go",
    "medical_diagnosis",
    "causality_claim",
]

EVIDENCE_CATALOG = {
    "radar_baseline_axis_table_v1_terrain_axis": [
        "outputs/script_inputs/ch6_5_5_radar_v1_axis_refinement_input_pack_v1/radar_baseline/personal_activity_performance_radar_report_safe_axis_table_v1_terrain_axis.csv",
        "outputs/report_figures/ch6_5_5_personal_activity_performance_radar_report_safe_v1_terrain_axis/personal_activity_performance_radar_report_safe_axis_table_v1_terrain_axis.csv",
        "outputs/report_figures/**/personal_activity_performance_radar_report_safe_axis_table_v1_terrain_axis.csv",
    ],
    "pacing_movement_stability_axis_v1": [
        "outputs/report_figures/ch6_5_5_pacing_movement_stability_axis_v1/pacing_movement_stability_axis_v1.csv",
        "outputs/report_figures/**/pacing_movement_stability_axis*.csv",
    ],
    "pacing_movement_stability_axis_admission_audit": [
        "outputs/report_figures/ch6_5_5_pacing_movement_stability_axis_admission_audit_v1/pacing_movement_stability_axis_admission_audit_v1.csv",
        "outputs/report_figures/**/pacing_movement_stability*admission*audit*.csv",
    ],
    "terrain_movement_efficiency_axis_admission": [
        "outputs/report_figures/ch6_5_6_terrain_movement_efficiency_axis_admission_audit_v1_2/terrain_movement_efficiency_axis_admission_audit_v1_2.csv",
        "outputs/report_figures/**/terrain_movement_efficiency*admission*audit*.csv",
        "outputs/report_figures/**/terrain_movement_efficiency*axis*.csv",
    ],
    "personal_profile_metadata_join": [
        "outputs/report_figures/ch6_5_5_personal_profile_metadata_join_v0_2/personal_profile_metadata_join_v0_2.csv",
        "outputs/report_figures/**/personal_profile_metadata_join*.csv",
    ],
    "route_load_match_review": [
        "outputs/report_figures/ch6_8_personal_route_load_readiness_review_v1_1/personal_route_load_readiness_review_v1_1.csv",
        "outputs/report_figures/ch6_8_personal_route_load_readiness_review_v1/personal_route_load_readiness_review_v1.csv",
        "outputs/report_figures/**/personal_route_load_readiness_review*.csv",
        "outputs/report_figures/ch6_5_route_load_context_index_v1/route_load_context_activity_summary_v1.csv",
        "outputs/report_figures/**/route_load_context_activity_summary*.csv",
        "outputs/report_figures/ch6_5_4_personal_route_load_match_review_v1/personal_route_load_match_review_v1.csv",
        "outputs/report_figures/**/personal_route_load_match*review*.csv",
    ],
    "weather_behavior_context": [
        "outputs/report_figures/ch6_report_figures_v1_2/ch6_4_weather_context_summary_v1_2.csv",
        "outputs/report_figures/ch6_report_figures_v1/ch6_4_weather_context_summary.csv",
        "outputs/report_figures/**/ch6_4_weather_context_summary*.csv",
        "outputs/report_figures/ch6_5_2_weather_adjusted_behavior_context_v1/weather_adjusted_behavior_context_v1.csv",
        "outputs/report_figures/**/weather*behavior*context*.csv",
        "outputs/report_figures/**/activity_completion_weather_context*.csv",
    ],
    "movement_300s_admission_review": [
        "outputs/report_figures/ch6_5_5_300s_movement_evidence_admission_review_v1/movement_300s_admission_axis_decision_v1.csv",
    ],
    "movement_300s_qa_gate_consumption": [
        "outputs/report_figures/ch6_5_5_300s_movement_qa_gate_consumption_v1/movement_300s_consumption_gate_policy_v1.csv",
    ],
    "movement_300s_consumption_integration_review": [
        "outputs/report_figures/ch6_5_5_300s_movement_consumption_integration_review_v1/movement_300s_integration_audit_v1.csv",
    ],
    "completion_feasibility_review": [
        "outputs/report_figures/ch6_8_personal_route_load_readiness_review_v1_1/personal_route_load_readiness_review_v1_1.csv",
        "outputs/report_figures/ch6_8_personal_route_load_readiness_review_v1/personal_route_load_readiness_review_v1.csv",
        "outputs/report_figures/**/personal_route_load_readiness_review*.csv",
        "outputs/report_figures/ch6_7_completion_feasibility_review_v1_1/completion_feasibility_conclusion_v1_1.csv",
        "outputs/report_figures/**/completion_feasibility*conclusion*.csv",
        "outputs/report_figures/**/completion_feasibility*review*audit*.csv",
    ],
    "hr_lifecycle_recovery_profile": [
        "outputs/report_figures/ch6_7_hr_lifecycle_recovery_profile_v2/activity_hr_lifecycle_summary_v2.csv",
        "outputs/report_figures/**/activity_hr_lifecycle_summary*.csv",
        "outputs/report_figures/**/activity_hr_recovery*.csv",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=r"D:\mountain_work\115_osm")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    p = Path(value)
    return p if p.is_absolute() else root / p


def find_first(root: Path, patterns: list[str]) -> Path | None:
    for pattern in patterns:
        p = resolve(root, pattern)
        if "**" in pattern:
            hits = sorted(root.glob(pattern))
            hits = [h for h in hits if h.is_file()]
            if hits:
                return hits[0]
        elif p.exists() and p.is_file():
            return p
    return None


def read_csv_optional(path: Path | None) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception:
        return pd.DataFrame()


def safe_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def evidence_inventory(root: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for evidence_id, patterns in EVIDENCE_CATALOG.items():
        p = find_first(root, patterns)
        df = read_csv_optional(p)
        rows.append({
            "evidence_id": evidence_id,
            "evidence_found": p is not None,
            "evidence_path": str(p.relative_to(root)) if p else "",
            "row_count": int(len(df)) if not df.empty else 0,
            "column_count": int(len(df.columns)) if not df.empty else 0,
            "columns": "|".join(map(str, df.columns[:80])) if not df.empty else "",
            "interpretation_boundary": BOUNDARY,
        })
    return pd.DataFrame(rows)


def evidence_path(inv: pd.DataFrame, evidence_id: str) -> str:
    hit = inv[inv["evidence_id"].astype(str).eq(evidence_id)]
    if hit.empty:
        return ""
    return str(hit.iloc[0].get("evidence_path", ""))


def source_list(inv: pd.DataFrame, ids: list[str]) -> str:
    pairs = []
    for eid in ids:
        p = evidence_path(inv, eid)
        pairs.append(f"{eid}:{p}" if p else f"{eid}:MISSING")
    return " | ".join(pairs)


def build_axis_contract(inv: pd.DataFrame) -> pd.DataFrame:
    route_gate = "route_continuity_300s_gate"
    artifact_guard = "positive_delta_artifact_guard"
    baseline_gate = "baseline_population_gate"
    hr_gate = "hr_validity_gate"
    weather_gate = "weather_context_gate"

    rows: list[dict[str, Any]] = [
        {
            "axis_id": "endurance_sustained_movement",
            "axis_label_zh": "持續耐力",
            "axis_domain": "activity_performance",
            "axis_status": "DESCRIPTIVE_ONLY",
            "axis_output_mode": "DESCRIPTIVE_ANNOTATION",
            "evidence_maturity": "LIMITED_COVERAGE_300S_EVIDENCE",
            "radar_output_permission": "ALLOW_TEXT_ANNOTATION_ONLY",
            "primary_evidence_source": source_list(inv, ["movement_300s_admission_review"]),
            "primary_evidence_fields": "horizontal_300s_route_speed_p90_mps|horizontal_300s_valid_window_count|admission_status",
            "supporting_evidence_sources": source_list(inv, ["movement_300s_qa_gate_consumption", "movement_300s_consumption_integration_review", "personal_profile_metadata_join"]),
            "required_consumption_gates": "|".join([baseline_gate, route_gate]),
            "fallback_status": "RETAIN_AS_DESCRIPTIVE_SUPPORTING_EVIDENCE",
            "missing_evidence_reason": "Horizontal 300s evidence covers only limited baseline activities; admission review did not admit it as standalone radar axis.",
            "allowed_use": "text annotation describing limited sustained-movement evidence",
            "disallowed_use": "numeric radar axis value|standalone ability ranking|score generation",
        },
        {
            "axis_id": "uphill_load_tolerance",
            "axis_label_zh": "上坡負荷承受力",
            "axis_domain": "activity_performance",
            "axis_status": "DESCRIPTIVE_ONLY",
            "axis_output_mode": "DESCRIPTIVE_ANNOTATION",
            "evidence_maturity": "LIMITED_COVERAGE_VERTICAL_300S_EVIDENCE",
            "radar_output_permission": "ALLOW_TEXT_ANNOTATION_ONLY",
            "primary_evidence_source": source_list(inv, ["movement_300s_admission_review"]),
            "primary_evidence_fields": "vertical_300s_vam_p90_mph|vertical_300s_gain_p90_m|vertical_300s_valid_window_count|admission_status",
            "supporting_evidence_sources": source_list(inv, ["movement_300s_qa_gate_consumption", "hr_lifecycle_recovery_profile", "personal_profile_metadata_join"]),
            "required_consumption_gates": "|".join([baseline_gate, route_gate, artifact_guard, hr_gate]),
            "fallback_status": "RETAIN_AS_DESCRIPTIVE_VERTICAL_CONTEXT",
            "missing_evidence_reason": "Vertical 300s evidence covers limited baseline activities and is not admitted as standalone radar axis.",
            "allowed_use": "text annotation describing limited uphill-load evidence",
            "disallowed_use": "numeric radar axis value|standalone ability ranking|score generation|medical diagnosis",
        },
        {
            "axis_id": "terrain_movement_efficiency",
            "axis_label_zh": "地形移動效率",
            "axis_domain": "terrain_response",
            "axis_status": "SUPPORTED_LIMITED",
            "axis_output_mode": "LIMITED_PROXY_AXIS",
            "evidence_maturity": "SUPPORTED_TERRAIN_MOVEMENT_EVIDENCE",
            "radar_output_permission": "ALLOW_LIMITED_PROXY_WITH_LABEL",
            "primary_evidence_source": source_list(inv, ["terrain_movement_efficiency_axis_admission", "radar_baseline_axis_table_v1_terrain_axis"]),
            "primary_evidence_fields": "terrain_movement_efficiency|terrain movement evidence status|axis admission status",
            "supporting_evidence_sources": source_list(inv, ["route_load_match_review", "movement_300s_qa_gate_consumption"]),
            "required_consumption_gates": "|".join([baseline_gate, route_gate]),
            "fallback_status": "LIMITED_PROXY_IF_PRIMARY_AXIS_PRESENT",
            "missing_evidence_reason": "If terrain movement evidence file is absent, show as insufficient instead of zero.",
            "allowed_use": "limited proxy radar axis with clear evidence label",
            "disallowed_use": "final ability score|rank|class",
        },
        {
            "axis_id": "pacing_movement_stability",
            "axis_label_zh": "穩定移動能力",
            "axis_domain": "activity_history",
            "axis_status": "SUPPORTED_LIMITED",
            "axis_output_mode": "LIMITED_PROXY_AXIS",
            "evidence_maturity": "SUPPORTED_ACTIVITY_HISTORY",
            "radar_output_permission": "ALLOW_LIMITED_PROXY_WITH_LABEL",
            "primary_evidence_source": source_list(inv, ["pacing_movement_stability_axis_v1", "pacing_movement_stability_axis_admission_audit"]),
            "primary_evidence_fields": "pacing_movement_stability|activity_history_status|axis admission status",
            "supporting_evidence_sources": source_list(inv, ["movement_300s_qa_gate_consumption", "hr_lifecycle_recovery_profile"]),
            "required_consumption_gates": "|".join([baseline_gate, route_gate]),
            "fallback_status": "LIMITED_PROXY_IF_PRIMARY_AXIS_PRESENT",
            "missing_evidence_reason": "If pacing / movement stability evidence is absent, show as insufficient instead of zero.",
            "allowed_use": "limited proxy radar axis with activity-history label",
            "disallowed_use": "final ability score|rank|class",
        },
        {
            "axis_id": "hr_load_management_recovery",
            "axis_label_zh": "HR負荷管理與恢復能力",
            "axis_domain": "physiological_context",
            "axis_status": "SUPPORTED_LIMITED",
            "axis_output_mode": "DESCRIPTIVE_ANNOTATION",
            "evidence_maturity": "HR_CONTEXT_AVAILABLE_NOT_MEDICAL",
            "radar_output_permission": "ALLOW_TEXT_ANNOTATION_ONLY",
            "primary_evidence_source": source_list(inv, ["hr_lifecycle_recovery_profile"]),
            "primary_evidence_fields": "hr_lifecycle|hr_recovery|hr_context|estimated_hrmax_percent",
            "supporting_evidence_sources": source_list(inv, ["personal_profile_metadata_join", "movement_300s_qa_gate_consumption"]),
            "required_consumption_gates": "|".join([baseline_gate, hr_gate]),
            "fallback_status": "TEXT_CONTEXT_ONLY",
            "missing_evidence_reason": "HR evidence depends on device validity and estimated HRmax; it should not be a medical or standalone ability axis.",
            "allowed_use": "load-management annotation and evidence context",
            "disallowed_use": "medical diagnosis|standalone ability axis|rank|class",
        },
        {
            "axis_id": "weather_performance_maintenance",
            "axis_label_zh": "天候條件下表現維持",
            "axis_domain": "environment_response",
            "axis_status": "LIMITED_PROXY",
            "axis_output_mode": "DESCRIPTIVE_ANNOTATION",
            "evidence_maturity": "LIMITED_PROXY_ACTIVITY_WEATHER_CONTEXT",
            "radar_output_permission": "ALLOW_TEXT_ANNOTATION_ONLY",
            "primary_evidence_source": source_list(inv, ["weather_behavior_context"]),
            "primary_evidence_fields": "weather context|weather adjusted behavior|activity weather context",
            "supporting_evidence_sources": source_list(inv, ["personal_profile_metadata_join", "completion_feasibility_review"]),
            "required_consumption_gates": "|".join([baseline_gate, weather_gate]),
            "fallback_status": "LIMITED_PROXY_OR_INSUFFICIENT_IF_WEATHER_CONTEXT_MISSING",
            "missing_evidence_reason": "Weather evidence remains context / proxy and does not isolate weather tolerance as a personal ability.",
            "allowed_use": "weather-context annotation",
            "disallowed_use": "weather tolerance score|go/no-go decision|risk score",
        },
        {
            "axis_id": "route_following_stability",
            "axis_label_zh": "路線跟隨穩定性",
            "axis_domain": "navigation_behavior",
            "axis_status": "INSUFFICIENT_EVIDENCE",
            "axis_output_mode": "MISSING_EVIDENCE_ANNOTATION",
            "evidence_maturity": "QA_GATE_AVAILABLE_BUT_NOT_ABILITY_AXIS",
            "radar_output_permission": "SHOW_AS_INSUFFICIENT_EVIDENCE",
            "primary_evidence_source": source_list(inv, ["movement_300s_qa_gate_consumption"]),
            "primary_evidence_fields": "route_continuity_300s_gate",
            "supporting_evidence_sources": source_list(inv, ["movement_300s_consumption_integration_review"]),
            "required_consumption_gates": "|".join([baseline_gate, route_gate]),
            "fallback_status": "INSUFFICIENT_EVIDENCE",
            "missing_evidence_reason": "Route continuity is admitted as QA gate only, not as route-following ability evidence.",
            "allowed_use": "missing-evidence annotation and QA gate explanation",
            "disallowed_use": "numeric route-following ability axis|navigation score|rank",
        },
        {
            "axis_id": "deviation_correction_ability",
            "axis_label_zh": "偏離修正能力",
            "axis_domain": "navigation_behavior",
            "axis_status": "INSUFFICIENT_EVIDENCE",
            "axis_output_mode": "MISSING_EVIDENCE_ANNOTATION",
            "evidence_maturity": "NO_FORMAL_DEVIATION_RECOVERY_FIELD",
            "radar_output_permission": "SHOW_AS_INSUFFICIENT_EVIDENCE",
            "primary_evidence_source": "",
            "primary_evidence_fields": "",
            "supporting_evidence_sources": source_list(inv, ["route_load_match_review"]),
            "required_consumption_gates": "|".join([baseline_gate, route_gate]),
            "fallback_status": "INSUFFICIENT_EVIDENCE",
            "missing_evidence_reason": "No formal field currently measures deviation, correction latency, backtracking, or rejoin behavior.",
            "allowed_use": "missing-evidence annotation",
            "disallowed_use": "numeric deviation-correction ability axis|navigation score|rank",
        },
        {
            "axis_id": "risk_response_experience",
            "axis_label_zh": "風險應對經驗",
            "axis_domain": "risk_behavior",
            "axis_status": "INSUFFICIENT_EVIDENCE",
            "axis_output_mode": "MISSING_EVIDENCE_ANNOTATION",
            "evidence_maturity": "NO_FORMAL_RISK_RESPONSE_OUTCOME_FIELD",
            "radar_output_permission": "SHOW_AS_INSUFFICIENT_EVIDENCE",
            "primary_evidence_source": "",
            "primary_evidence_fields": "",
            "supporting_evidence_sources": source_list(inv, ["route_load_match_review", "completion_feasibility_review"]),
            "required_consumption_gates": baseline_gate,
            "fallback_status": "INSUFFICIENT_EVIDENCE",
            "missing_evidence_reason": "Current evidence does not formally observe risk recognition, avoidance, fallback, or decision behavior.",
            "allowed_use": "missing-evidence annotation",
            "disallowed_use": "risk handling score|safety decision|go/no-go decision",
        },
        {
            "axis_id": "autonomous_completion_readiness",
            "axis_label_zh": "自主完成能力",
            "axis_domain": "completion_behavior",
            "axis_status": "LIMITED_PROXY",
            "axis_output_mode": "DESCRIPTIVE_ANNOTATION",
            "evidence_maturity": "COMPLETION_CONTEXT_AVAILABLE_NOT_SELF_SUFFICIENCY",
            "radar_output_permission": "ALLOW_TEXT_ANNOTATION_ONLY",
            "primary_evidence_source": source_list(inv, ["completion_feasibility_review"]),
            "primary_evidence_fields": "completion feasibility|completion context|route load completion review",
            "supporting_evidence_sources": source_list(inv, ["route_load_match_review", "personal_profile_metadata_join"]),
            "required_consumption_gates": baseline_gate,
            "fallback_status": "LIMITED_PROXY_OR_INSUFFICIENT_IF_COMPLETION_CONTEXT_MISSING",
            "missing_evidence_reason": "Completion evidence does not prove autonomous navigation, supply, equipment, or team-support independence.",
            "allowed_use": "completion-context annotation",
            "disallowed_use": "self-sufficiency score|route suitability score|go/no-go decision",
        },
        {
            "axis_id": "supply_equipment_support",
            "axis_label_zh": "補給／裝備支援",
            "axis_domain": "support_preparedness",
            "axis_status": "INSUFFICIENT_EVIDENCE",
            "axis_output_mode": "MISSING_EVIDENCE_ANNOTATION",
            "evidence_maturity": "NO_PERSONAL_SUPPLY_EQUIPMENT_DATA",
            "radar_output_permission": "SHOW_AS_INSUFFICIENT_EVIDENCE",
            "primary_evidence_source": "",
            "primary_evidence_fields": "",
            "supporting_evidence_sources": "",
            "required_consumption_gates": "",
            "fallback_status": "INSUFFICIENT_EVIDENCE",
            "missing_evidence_reason": "No personal supply, equipment, hydration, nutrition, packing, or support data is available.",
            "allowed_use": "missing-evidence annotation",
            "disallowed_use": "equipment readiness score|preparedness class|go/no-go decision",
        },
    ]

    for row in rows:
        row["interpretation_boundary"] = BOUNDARY

    return pd.DataFrame(rows)


def build_audit(contract: pd.DataFrame, inv: pd.DataFrame) -> pd.DataFrame:
    columns = list(contract.columns) + list(inv.columns)
    forbidden = [c for c in columns if any(p in c.lower() for p in FORBIDDEN_OUTPUT_PATTERNS)]

    review_reasons: list[str] = []
    if contract.empty:
        review_reasons.append("EMPTY_AXIS_CONTRACT")
    if forbidden:
        review_reasons.append("FORBIDDEN_FIELD_PRESENT")

    numeric_count = int(contract["axis_output_mode"].astype(str).eq("NUMERIC_AXIS").sum()) if not contract.empty else 0
    proxy_count = int(contract["axis_output_mode"].astype(str).eq("LIMITED_PROXY_AXIS").sum()) if not contract.empty else 0
    text_count = int(contract["axis_output_mode"].astype(str).eq("DESCRIPTIVE_ANNOTATION").sum()) if not contract.empty else 0
    missing_count = int(contract["axis_output_mode"].astype(str).eq("MISSING_EVIDENCE_ANNOTATION").sum()) if not contract.empty else 0
    excluded_count = int(contract["axis_output_mode"].astype(str).eq("EXCLUDED_FROM_RADAR").sum()) if not contract.empty else 0

    row = {
        "axis_count": int(len(contract)),
        "numeric_axis_count": numeric_count,
        "limited_proxy_axis_count": proxy_count,
        "descriptive_annotation_axis_count": text_count,
        "missing_evidence_annotation_axis_count": missing_count,
        "excluded_axis_count": excluded_count,
        "evidence_catalog_count": int(len(inv)),
        "evidence_found_count": int(inv["evidence_found"].sum()) if not inv.empty else 0,
        "zero_fill_used": False,
        "forbidden_score_rank_class_fields_present": bool(forbidden),
        "forbidden_fields": "|".join(forbidden) if forbidden else "NONE",
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


def write_html(out_path: Path, audit: pd.DataFrame, contract: pd.DataFrame, inv: pd.DataFrame) -> None:
    def table(df: pd.DataFrame, cols: list[str], n: int = 120) -> str:
        if df.empty:
            return "<p>No rows.</p>"
        use = [c for c in cols if c in df.columns]
        return df[use].head(n).to_html(index=False, escape=True, classes="data")

    conclusion = audit.iloc[0]["audit_conclusion"] if not audit.empty else REVIEW

    body = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CH6.5.5 Personal Ability Radar Axis Contract v1</title>
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
<h1>CH6.5.5 Personal Ability Radar Axis Contract v1</h1>
<p class="status">{html.escape(str(conclusion))}</p>
<p class="boundary">{html.escape(BOUNDARY)}</p>

<h2>Audit</h2>
{table(audit, list(audit.columns), 5)}

<h2>Axis Contract</h2>
{table(contract, ["axis_id", "axis_label_zh", "axis_domain", "axis_status", "axis_output_mode", "evidence_maturity", "radar_output_permission", "required_consumption_gates", "fallback_status", "missing_evidence_reason", "allowed_use", "disallowed_use"], 80)}

<h2>Evidence Inventory</h2>
{table(inv, ["evidence_id", "evidence_found", "evidence_path", "row_count", "column_count"], 80)}
</body>
</html>
"""
    out_path.write_text(body, encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    out_root = resolve(root, args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)

    inv = evidence_inventory(root)
    contract = build_axis_contract(inv)
    audit = build_audit(contract, inv)

    outputs = {
        "contract": out_root / "personal_ability_radar_axis_contract_v1.csv",
        "evidence_inventory": out_root / "personal_ability_radar_axis_evidence_inventory_v1.csv",
        "audit": out_root / "personal_ability_radar_axis_contract_audit_v1.csv",
        "html": out_root / "personal_ability_radar_axis_contract_report_v1.html",
    }

    contract.to_csv(outputs["contract"], index=False, encoding="utf-8-sig")
    inv.to_csv(outputs["evidence_inventory"], index=False, encoding="utf-8-sig")
    audit.to_csv(outputs["audit"], index=False, encoding="utf-8-sig")
    write_html(outputs["html"], audit, contract, inv)

    print({
        "output_root": str(out_root),
        "axis_count": int(audit.iloc[0]["axis_count"]),
        "numeric_axis_count": int(audit.iloc[0]["numeric_axis_count"]),
        "limited_proxy_axis_count": int(audit.iloc[0]["limited_proxy_axis_count"]),
        "descriptive_annotation_axis_count": int(audit.iloc[0]["descriptive_annotation_axis_count"]),
        "missing_evidence_annotation_axis_count": int(audit.iloc[0]["missing_evidence_annotation_axis_count"]),
        "evidence_found_count": int(audit.iloc[0]["evidence_found_count"]),
        "audit_conclusion": str(audit.iloc[0]["audit_conclusion"]),
        "outputs": {k: str(v) for k, v in outputs.items()},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
