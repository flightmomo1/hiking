#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build CH6.5.5 route-following data table patch v1.

This script applies the governed route-following stability limited-proxy
admission to a copy of the CH6.5.5 personal ability radar data table.

It creates a v1_1 data-table layer and a patch record only. It does not modify
the original data table v1, original axis contract v1, or any radar plot. It
does not compute ability scores, ability ranks, ability classes, THCI scores,
final hiking risk scores, route suitability scores, go/no-go decisions, medical
diagnoses, or causality claims.
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_DATA_TABLE_PATH = (
    "outputs/report_figures/ch6_5_5_personal_ability_radar_data_table_v1/"
    "personal_ability_radar_data_table_v1.csv"
)
DEFAULT_CONTRACT_V1_1_PATH = (
    "outputs/report_figures/ch6_5_5_route_following_axis_contract_patch_v1/"
    "personal_ability_radar_axis_contract_v1_1.csv"
)
DEFAULT_ADMISSION_ROOT = "outputs/report_figures/ch6_5_5_route_following_stability_proxy_admission_v1_1"
DEFAULT_OUTPUT_ROOT = "outputs/report_figures/ch6_5_5_route_following_data_table_patch_v1"

ACTIVITY_SUMMARY_FILE = "route_following_stability_proxy_activity_summary_v1_1.csv"
ADMISSION_DECISION_FILE = "route_following_stability_proxy_admission_decision_v1_1.csv"

ROUTE_AXIS = "route_following_stability"
DEVIATION_AXIS = "deviation_correction_ability"

PASS = "PASS_CH6_5_5_ROUTE_FOLLOWING_DATA_TABLE_PATCH_V1_GOVERNED_TABLE_LAYER"
REVIEW = "REVIEW_REQUIRED_CH6_5_5_ROUTE_FOLLOWING_DATA_TABLE_PATCH_V1"

BOUNDARY = (
    "CH6.5.5 route-following data table patch v1 is a governed data-table patch layer only. "
    "It upgrades route_following_stability rows in a v1_1 data-table copy to a limited proxy "
    "using route-following proxy admission evidence. It does not upgrade deviation_correction_ability. "
    "It does not compute or authorize ability scores, ability ranks, ability classes, THCI scores, "
    "final hiking risk scores, route suitability scores, go/no-go decisions, medical diagnoses, "
    "or causality claims."
)

ROUTE_BOUNDARY = (
    "Route-following stability is represented in data table v1_1 as a governed limited proxy only. "
    "It is not an ability score, ability rank, ability class, THCI score, final hiking risk score, "
    "route suitability score, go/no-go decision, medical diagnosis, or causality claim."
)

FORBIDDEN_COLUMN_TOKENS = [
    "ability_score",
    "ability_rank",
    "ability_class",
    "thci_score",
    "final_hiking_risk_score",
    "route_suitability_score",
    "go_no_go",
    "medical_diagnosis",
    "causality_claim",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=r"D:\mountain_work\115_osm")
    parser.add_argument("--data-table-path", default=DEFAULT_DATA_TABLE_PATH)
    parser.add_argument("--contract-v1-1-path", default=DEFAULT_CONTRACT_V1_1_PATH)
    parser.add_argument("--admission-root", default=DEFAULT_ADMISSION_ROOT)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    p = Path(value)
    return p if p.is_absolute() else root / p


def read_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def rel_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except Exception:
        return str(path)


def blank(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value)


def boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def first_row(df: pd.DataFrame, axis_id: str) -> dict[str, Any]:
    hit = df[df["axis_id"].astype(str).eq(axis_id)] if "axis_id" in df.columns else pd.DataFrame()
    return hit.iloc[0].to_dict() if not hit.empty else {}


def to_number(value: Any) -> float | None:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def format_proxy_value(value: Any) -> str:
    n = to_number(value)
    if n is None:
        return ""
    return f"{n:.2f}"


def build_activity_lookup(activity_summary: pd.DataFrame) -> dict[str, dict[str, Any]]:
    if "activity_id" not in activity_summary.columns:
        raise ValueError("Activity summary is missing activity_id")
    return {
        str(row["activity_id"]): row.to_dict()
        for _, row in activity_summary.iterrows()
    }


def build_decision_lookup(decision: pd.DataFrame) -> dict[str, dict[str, Any]]:
    if "axis_id" not in decision.columns:
        return {}
    return {str(row["axis_id"]): row.to_dict() for _, row in decision.iterrows()}


def patch_route_rows(
    data_v1: pd.DataFrame,
    contract_v1_1: pd.DataFrame,
    activity_summary: pd.DataFrame,
    admission_decision: pd.DataFrame,
    activity_summary_path: Path,
    root: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = data_v1.copy()
    for col in [
        "axis_status",
        "axis_output_mode",
        "radar_output_permission",
        "axis_value_allowed",
        "axis_value",
        "axis_value_unit",
        "axis_annotation",
        "evidence_source",
        "evidence_fields",
        "required_gate_status",
        "fallback_status",
        "missing_evidence_reason",
        "allowed_use",
        "disallowed_use",
        "interpretation_boundary",
    ]:
        if col in data.columns:
            data[col] = data[col].astype(object)
    activity_lookup = build_activity_lookup(activity_summary)
    decision_lookup = build_decision_lookup(admission_decision)
    route_contract = first_row(contract_v1_1, ROUTE_AXIS)
    route_decision = decision_lookup.get(ROUTE_AXIS, {})

    if not route_contract:
        raise ValueError("Contract v1_1 is missing route_following_stability")
    if not route_decision:
        raise ValueError("Admission decision is missing route_following_stability")

    patch_rows: list[dict[str, Any]] = []
    route_mask = data["axis_id"].astype(str).eq(ROUTE_AXIS)

    evidence_source = rel_path(root, activity_summary_path)
    evidence_fields = (
        "detector_file_found|evidence_state|route_issue_event_count|"
        "candidate_proxy_route_following_stability_0_100|terminal_event_rows|non_terminal_event_rows"
    )

    for idx in data.index[route_mask]:
        old = data.loc[idx].to_dict()
        activity_id = str(old.get("activity_id_short", ""))
        summary = activity_lookup.get(activity_id, {})
        population = blank(old.get("study_population_status")) or blank(summary.get("study_population_status"))
        is_baseline = population == "RADAR_BASELINE_ACTIVITY"
        baseline_gate = blank(summary.get("baseline_population_gate"))
        detector_found = boolish(summary.get("detector_file_found"))
        proxy_value = format_proxy_value(summary.get("candidate_proxy_route_following_stability_0_100"))
        admitted = is_baseline and baseline_gate == "PASS" and detector_found and proxy_value != ""

        old_axis_output_mode = blank(old.get("axis_output_mode"))
        old_axis_value_allowed = boolish(old.get("axis_value_allowed"))
        old_axis_value = blank(old.get("axis_value"))

        new_axis_value_allowed = bool(admitted)
        new_axis_value = proxy_value if admitted else ""
        new_gate = (
            f"baseline_population_gate={'PASS' if is_baseline else 'BLOCKED_EXTRA_SOURCE'}|"
            f"detector_file_found={'PASS' if detector_found else 'MISSING'}|"
            f"route_following_proxy_admission={'PASS' if admitted else 'NOT_ADMITTED_FOR_ACTIVITY'}"
        )

        evidence_state = blank(summary.get("evidence_state"))
        event_count = blank(summary.get("route_issue_event_count"))
        terminal_rows = blank(summary.get("terminal_event_rows"))
        non_terminal_rows = blank(summary.get("non_terminal_event_rows"))
        admission_status = blank(summary.get("admission_status"))

        annotation = (
            "LIMITED_PROXY_AXIS; governed route-following proxy preview only. "
            f"evidence_state={evidence_state}; route_issue_event_count={event_count}; "
            f"terminal_event_rows={terminal_rows}; non_terminal_event_rows={non_terminal_rows}; "
            f"admission_status={admission_status}."
        )
        if not admitted:
            annotation += " Proxy value withheld because activity is outside the admitted baseline population or detector evidence is unavailable."

        data.loc[idx, "axis_status"] = "LIMITED_PROXY"
        data.loc[idx, "axis_output_mode"] = "LIMITED_PROXY_AXIS"
        data.loc[idx, "radar_output_permission"] = "GOVERNED_LIMITED_PROXY_PREVIEW_ONLY"
        data.loc[idx, "axis_value_allowed"] = new_axis_value_allowed
        data.loc[idx, "axis_value"] = new_axis_value
        data.loc[idx, "axis_value_unit"] = "0_100_limited_proxy" if admitted else ""
        data.loc[idx, "axis_annotation"] = annotation
        data.loc[idx, "evidence_source"] = evidence_source
        data.loc[idx, "evidence_fields"] = evidence_fields
        data.loc[idx, "required_gate_status"] = new_gate
        data.loc[idx, "fallback_status"] = "GOVERNED_LIMITED_PROXY_PREVIEW_ONLY" if admitted else "BLOCKED_BY_BASELINE_OR_EVIDENCE_GATE"
        data.loc[idx, "missing_evidence_reason"] = ""
        data.loc[idx, "allowed_use"] = "limited proxy radar preview with explicit route-following proxy label"
        data.loc[idx, "disallowed_use"] = "ability score|ability rank|ability class|final risk score|route suitability score|go/no-go decision"
        data.loc[idx, "interpretation_boundary"] = ROUTE_BOUNDARY

        patch_rows.append({
            "participant_id": old.get("participant_id", ""),
            "activity_id_short": activity_id,
            "study_population_status": population,
            "axis_id": ROUTE_AXIS,
            "axis_label_zh": old.get("axis_label_zh", ""),
            "old_axis_output_mode": old_axis_output_mode,
            "new_axis_output_mode": "LIMITED_PROXY_AXIS",
            "old_axis_value_allowed": old_axis_value_allowed,
            "new_axis_value_allowed": new_axis_value_allowed,
            "old_axis_value": old_axis_value,
            "new_axis_value": new_axis_value,
            "axis_value_unit": "0_100_limited_proxy" if admitted else "",
            "patch_reason": (
                "Apply route-following axis contract v1_1 limited proxy admission to data table row. "
                "Baseline activities with detector evidence receive candidate_proxy_route_following_stability_0_100; "
                "extra source activities remain blocked."
            ),
            "evidence_source": evidence_source,
            "evidence_fields": evidence_fields,
            "evidence_state": evidence_state,
            "route_issue_event_count": event_count,
            "terminal_event_rows": terminal_rows,
            "non_terminal_event_rows": non_terminal_rows,
            "admission_status": admission_status,
            "admission_decision": blank(route_decision.get("admission_decision")),
            "interpretation_boundary": ROUTE_BOUNDARY,
        })

    return data, pd.DataFrame(patch_rows)


def build_audit(data_v1: pd.DataFrame, data_v1_1: pd.DataFrame, patch: pd.DataFrame) -> pd.DataFrame:
    route = data_v1_1[data_v1_1["axis_id"].astype(str).eq(ROUTE_AXIS)]
    route_baseline = route[route["study_population_status"].astype(str).eq("RADAR_BASELINE_ACTIVITY")]
    route_extra = route[route["study_population_status"].astype(str).ne("RADAR_BASELINE_ACTIVITY")]
    deviation = data_v1_1[data_v1_1["axis_id"].astype(str).eq(DEVIATION_AXIS)]

    axis_values = data_v1_1["axis_value"].fillna("").astype(str)
    route_values = route["axis_value"].fillna("").astype(str)
    route_baseline_values = route_baseline["axis_value"].fillna("").astype(str)
    route_extra_values = route_extra["axis_value"].fillna("").astype(str)
    deviation_values = deviation["axis_value"].fillna("").astype(str)

    limited_proxy_count = int(data_v1_1["axis_output_mode"].astype(str).eq("LIMITED_PROXY_AXIS").sum())
    limited_proxy_value_count = int(
        (
            data_v1_1["axis_output_mode"].astype(str).eq("LIMITED_PROXY_AXIS")
            & data_v1_1["axis_value"].fillna("").astype(str).str.len().gt(0)
        ).sum()
    )
    missing_count = int(data_v1_1["axis_output_mode"].astype(str).eq("MISSING_EVIDENCE_ANNOTATION").sum())
    forbidden_cols = [
        c for c in list(data_v1_1.columns) + list(patch.columns)
        if any(token in str(c).lower() for token in FORBIDDEN_COLUMN_TOKENS)
    ]

    deviation_retained = (
        not deviation.empty
        and deviation["axis_output_mode"].astype(str).eq("MISSING_EVIDENCE_ANNOTATION").all()
        and deviation_values.str.len().sum() == 0
    )
    extra_blocked = (
        len(route_extra) == 1
        and route_extra_values.str.len().sum() == 0
        and route_extra["required_gate_status"].astype(str).str.contains("BLOCKED_EXTRA_SOURCE", na=False).all()
    )

    review_reasons: list[str] = []
    if int(len(data_v1_1)) != 286:
        review_reasons.append("ROW_COUNT_NOT_286")
    if int(data_v1_1["activity_id_short"].nunique()) != 26:
        review_reasons.append("ACTIVITY_COUNT_NOT_26")
    if int(data_v1_1["axis_id"].nunique()) != 11:
        review_reasons.append("AXIS_COUNT_NOT_11")
    if len(route) != 26:
        review_reasons.append("ROUTE_FOLLOWING_ROW_COUNT_NOT_26")
    if len(route_baseline) != 25:
        review_reasons.append("ROUTE_FOLLOWING_BASELINE_ROW_COUNT_NOT_25")
    if len(route_extra) != 1:
        review_reasons.append("ROUTE_FOLLOWING_EXTRA_ROW_COUNT_NOT_1")
    if int(route_baseline_values.str.len().gt(0).sum()) != 25:
        review_reasons.append("ROUTE_FOLLOWING_BASELINE_VALUE_COUNT_NOT_25")
    if int(route_extra_values.str.len().gt(0).sum()) != 0:
        review_reasons.append("ROUTE_FOLLOWING_EXTRA_VALUE_COUNT_NOT_0")
    if not extra_blocked:
        review_reasons.append("ROUTE_FOLLOWING_EXTRA_SOURCE_NOT_BLOCKED")
    if limited_proxy_count != 78:
        review_reasons.append("LIMITED_PROXY_ROW_COUNT_NOT_78")
    if limited_proxy_value_count != 75:
        review_reasons.append("LIMITED_PROXY_VALUE_COUNT_NOT_75")
    if missing_count != 78:
        review_reasons.append("MISSING_EVIDENCE_ROW_COUNT_NOT_78")
    if not deviation_retained:
        review_reasons.append("DEVIATION_CORRECTION_NOT_RETAINED_AS_MISSING")
    if forbidden_cols:
        review_reasons.append("FORBIDDEN_OUTPUT_FIELD_PRESENT")

    row = {
        "row_count": int(len(data_v1_1)),
        "activity_count": int(data_v1_1["activity_id_short"].nunique()),
        "axis_count": int(data_v1_1["axis_id"].nunique()),
        "route_following_rows": int(len(route)),
        "route_following_baseline_rows": int(len(route_baseline)),
        "route_following_extra_source_rows": int(len(route_extra)),
        "route_following_baseline_value_count": int(route_baseline_values.str.len().gt(0).sum()),
        "route_following_extra_source_value_count": int(route_extra_values.str.len().gt(0).sum()),
        "route_following_extra_source_blocked": bool(extra_blocked),
        "limited_proxy_axis_row_count": limited_proxy_count,
        "limited_proxy_axis_value_count": limited_proxy_value_count,
        "missing_evidence_annotation_row_count": missing_count,
        "deviation_correction_ability_retained_missing": bool(deviation_retained),
        "deviation_correction_ability_output_mode": "MISSING_EVIDENCE_ANNOTATION" if not deviation.empty else "",
        "zero_fill_used": False,
        "forbidden_policy_terms_present": bool(forbidden_cols),
        "forbidden_fields": "|".join(forbidden_cols) if forbidden_cols else "NONE",
        "ability_scoring_absent": True,
        "ranking_absent": True,
        "class_label_absent": True,
        "risk_scoring_absent": True,
        "route_suitability_scoring_absent": True,
        "decision_label_absent": True,
        "diagnosis_absent": True,
        "causal_claim_absent": True,
        "audit_conclusion": REVIEW if review_reasons else PASS,
        "review_reasons": "|".join(review_reasons) if review_reasons else "NONE",
        "interpretation_boundary": BOUNDARY,
    }
    return pd.DataFrame([row])


def write_html(out_path: Path, audit: pd.DataFrame, patch: pd.DataFrame, data_v1_1: pd.DataFrame) -> None:
    def table(df: pd.DataFrame, cols: list[str], n: int = 30) -> str:
        if df.empty:
            return "<p>No rows.</p>"
        use = [c for c in cols if c in df.columns]
        return df[use].head(n).to_html(index=False, escape=True, classes="data")

    route = data_v1_1[data_v1_1["axis_id"].astype(str).eq(ROUTE_AXIS)]
    route_extra = route[route["study_population_status"].astype(str).ne("RADAR_BASELINE_ACTIVITY")]
    deviation = data_v1_1[data_v1_1["axis_id"].astype(str).eq(DEVIATION_AXIS)]
    conclusion = audit.iloc[0]["audit_conclusion"] if not audit.empty else REVIEW

    body = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CH6.5.5 Route-Following Data Table Patch v1</title>
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
<h1>CH6.5.5 Route-Following Data Table Patch v1</h1>
<p class="status">{html.escape(str(conclusion))}</p>
<p class="boundary">{html.escape(BOUNDARY)}</p>

<h2>Patch Summary</h2>
{table(patch, ["activity_id_short", "study_population_status", "old_axis_output_mode", "new_axis_output_mode", "old_axis_value_allowed", "new_axis_value_allowed", "old_axis_value", "new_axis_value", "evidence_state", "route_issue_event_count", "admission_status"], 30)}

<h2>Audit</h2>
{table(audit, list(audit.columns), 5)}

<h2>Route-Following Rows</h2>
{table(route, ["participant_id", "activity_id_short", "study_population_status", "axis_output_mode", "axis_value_allowed", "axis_value", "axis_value_unit", "required_gate_status", "axis_annotation"], 30)}

<h2>Extra Source Blocked</h2>
{table(route_extra, ["participant_id", "activity_id_short", "study_population_status", "axis_value_allowed", "axis_value", "required_gate_status"], 5)}

<h2>Deviation Correction Retained</h2>
{table(deviation, ["participant_id", "activity_id_short", "axis_output_mode", "axis_value_allowed", "axis_value", "missing_evidence_reason"], 30)}
</body>
</html>
"""
    out_path.write_text(body, encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    data_table_path = resolve(root, args.data_table_path)
    contract_path = resolve(root, args.contract_v1_1_path)
    admission_root = resolve(root, args.admission_root)
    activity_summary_path = admission_root / ACTIVITY_SUMMARY_FILE
    admission_decision_path = admission_root / ADMISSION_DECISION_FILE
    out_root = resolve(root, args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)

    data_v1 = read_csv(data_table_path, "personal ability radar data table v1")
    contract_v1_1 = read_csv(contract_path, "personal ability radar axis contract v1_1")
    activity_summary = read_csv(activity_summary_path, "route-following activity summary v1_1")
    admission_decision = read_csv(admission_decision_path, "route-following admission decision v1_1")

    data_v1_1, patch = patch_route_rows(
        data_v1,
        contract_v1_1,
        activity_summary,
        admission_decision,
        activity_summary_path,
        root,
    )
    audit = build_audit(data_v1, data_v1_1, patch)

    outputs = {
        "patch": out_root / "personal_ability_radar_data_table_patch_v1.csv",
        "data_table_v1_1": out_root / "personal_ability_radar_data_table_v1_1.csv",
        "audit": out_root / "personal_ability_radar_data_table_patch_audit_v1.csv",
        "html": out_root / "personal_ability_radar_data_table_patch_report_v1.html",
    }

    patch.to_csv(outputs["patch"], index=False, encoding="utf-8-sig")
    data_v1_1.to_csv(outputs["data_table_v1_1"], index=False, encoding="utf-8-sig")
    audit.to_csv(outputs["audit"], index=False, encoding="utf-8-sig")
    write_html(outputs["html"], audit, patch, data_v1_1)

    print({
        "output_root": str(out_root),
        "audit_conclusion": str(audit.iloc[0]["audit_conclusion"]),
        "row_count": int(audit.iloc[0]["row_count"]),
        "activity_count": int(audit.iloc[0]["activity_count"]),
        "axis_count": int(audit.iloc[0]["axis_count"]),
        "limited_proxy_axis_row_count": int(audit.iloc[0]["limited_proxy_axis_row_count"]),
        "limited_proxy_axis_value_count": int(audit.iloc[0]["limited_proxy_axis_value_count"]),
        "route_following_baseline_value_count": int(audit.iloc[0]["route_following_baseline_value_count"]),
        "route_following_extra_source_value_count": int(audit.iloc[0]["route_following_extra_source_value_count"]),
        "deviation_correction_ability_output_mode": str(audit.iloc[0]["deviation_correction_ability_output_mode"]),
        "outputs": {k: str(v) for k, v in outputs.items()},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
