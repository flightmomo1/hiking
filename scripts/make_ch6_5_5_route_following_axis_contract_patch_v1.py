#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build CH6.5.5 route-following axis contract patch v1.

This script applies the governed route-following stability proxy admission to a
copy of the CH6.5.5 personal ability radar axis contract.

It creates a v1_1 contract layer and a patch record only. It does not modify the
original v1 contract, the existing radar plot, or the existing data table. It
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


DEFAULT_CONTRACT_PATH = (
    "outputs/report_figures/ch6_5_5_personal_ability_radar_axis_contract_v1/"
    "personal_ability_radar_axis_contract_v1.csv"
)
DEFAULT_INVENTORY_PATH = (
    "outputs/report_figures/ch6_5_5_personal_ability_radar_axis_contract_v1/"
    "personal_ability_radar_axis_evidence_inventory_v1.csv"
)
DEFAULT_ADMISSION_ROOT = "outputs/report_figures/ch6_5_5_route_following_stability_proxy_admission_v1_1"
DEFAULT_OUTPUT_ROOT = "outputs/report_figures/ch6_5_5_route_following_axis_contract_patch_v1"

ADMISSION_DECISION_FILE = "route_following_stability_proxy_admission_decision_v1_1.csv"
ADMISSION_AUDIT_FILE = "route_following_stability_proxy_admission_audit_v1_1.csv"

BOUNDARY = (
    "CH6.5.5 route-following axis contract patch v1 is a governed contract patch layer only. "
    "It upgrades route_following_stability to a limited proxy axis in a new v1_1 contract copy "
    "after the route-following proxy admission review. It does not upgrade deviation_correction_ability. "
    "It does not compute or authorize ability scores, ability ranks, ability classes, THCI scores, "
    "final hiking risk scores, route suitability scores, go/no-go decisions, medical diagnoses, "
    "or causality claims."
)

PATCH_PASS = "PASS_CH6_5_5_ROUTE_FOLLOWING_AXIS_CONTRACT_PATCH_V1_GOVERNED_CONTRACT_LAYER"
PATCH_REVIEW = "REVIEW_REQUIRED_CH6_5_5_ROUTE_FOLLOWING_AXIS_CONTRACT_PATCH_V1"

ROUTE_AXIS = "route_following_stability"
DEVIATION_AXIS = "deviation_correction_ability"

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
    parser.add_argument("--contract-path", default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--inventory-path", default=DEFAULT_INVENTORY_PATH)
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


def boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def first_row(df: pd.DataFrame, axis_id: str) -> dict[str, Any]:
    hit = df[df["axis_id"].astype(str).eq(axis_id)] if "axis_id" in df.columns else pd.DataFrame()
    return hit.iloc[0].to_dict() if not hit.empty else {}


def normalize_blank(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value)


def add_axis_value_allowed(contract: pd.DataFrame) -> pd.DataFrame:
    out = contract.copy()
    out["axis_value_allowed"] = out["axis_output_mode"].astype(str).isin(["NUMERIC_AXIS", "LIMITED_PROXY_AXIS"])
    return out


def build_patched_contract(
    contract_v1: pd.DataFrame,
    decision: pd.DataFrame,
    admission_decision_path: Path,
    root: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if "axis_id" not in contract_v1.columns:
        raise ValueError("Contract v1 is missing axis_id")

    patched = contract_v1.copy()
    decision_route = first_row(decision, ROUTE_AXIS)
    decision_deviation = first_row(decision, DEVIATION_AXIS)
    old_route = first_row(contract_v1, ROUTE_AXIS)

    if not decision_route:
        raise ValueError("Admission decision is missing route_following_stability")
    if not old_route:
        raise ValueError("Contract v1 is missing route_following_stability")

    route_mask = patched["axis_id"].astype(str).eq(ROUTE_AXIS)
    evidence_source = rel_path(root, admission_decision_path)
    evidence_fields = normalize_blank(decision_route.get("evidence_fields"))
    admission_decision = normalize_blank(decision_route.get("admission_decision"))
    proxy_basis = normalize_blank(decision_route.get("proxy_basis"))
    review_reasons = normalize_blank(decision_route.get("review_reasons")) or "NONE"

    route_boundary = (
        "Route-following stability is admitted in contract v1_1 as a governed limited proxy only. "
        "It is not an ability score, ability rank, ability class, THCI score, final hiking risk score, "
        "route suitability score, go/no-go decision, medical diagnosis, or causality claim."
    )

    patched.loc[route_mask, "axis_status"] = "LIMITED_PROXY"
    patched.loc[route_mask, "axis_output_mode"] = "LIMITED_PROXY_AXIS"
    patched.loc[route_mask, "radar_output_permission"] = "GOVERNED_LIMITED_PROXY_PREVIEW_ONLY"
    patched.loc[route_mask, "evidence_maturity"] = "ROUTE_FOLLOWING_LIMITED_PROXY_ADMITTED_V1_1"
    patched.loc[route_mask, "primary_evidence_source"] = f"route_following_stability_proxy_admission_v1_1:{evidence_source}"
    patched.loc[route_mask, "primary_evidence_fields"] = evidence_fields
    patched.loc[route_mask, "supporting_evidence_sources"] = normalize_blank(decision_route.get("evidence_source"))
    patched.loc[route_mask, "required_consumption_gates"] = "baseline_population_gate|route_issue_event_quality_gate|extra_source_exclusion_gate"
    patched.loc[route_mask, "fallback_status"] = "GOVERNED_LIMITED_PROXY_PREVIEW_ONLY"
    patched.loc[route_mask, "missing_evidence_reason"] = ""
    patched.loc[route_mask, "allowed_use"] = "limited proxy radar preview with explicit proxy label and admission boundary"
    patched.loc[route_mask, "disallowed_use"] = "ability score|ability rank|ability class|final risk score|route suitability score|go/no-go decision"
    patched.loc[route_mask, "interpretation_boundary"] = route_boundary

    patched = add_axis_value_allowed(patched)

    new_route = first_row(patched, ROUTE_AXIS)
    patch_row = {
        "axis_id": ROUTE_AXIS,
        "axis_label_zh": normalize_blank(old_route.get("axis_label_zh")),
        "old_axis_status": normalize_blank(old_route.get("axis_status")),
        "new_axis_status": normalize_blank(new_route.get("axis_status")),
        "old_axis_output_mode": normalize_blank(old_route.get("axis_output_mode")),
        "new_axis_output_mode": normalize_blank(new_route.get("axis_output_mode")),
        "old_radar_output_permission": normalize_blank(old_route.get("radar_output_permission")),
        "new_radar_output_permission": normalize_blank(new_route.get("radar_output_permission")),
        "axis_value_allowed": boolish(new_route.get("axis_value_allowed")),
        "patch_reason": (
            "Route-following proxy admission v1_1 recommends upgrading route_following_stability "
            "from missing-evidence annotation to governed limited proxy axis candidate. "
            f"proxy_basis={proxy_basis}; review_reasons={review_reasons}."
        ),
        "evidence_source": evidence_source,
        "evidence_fields": evidence_fields,
        "admission_decision": admission_decision,
        "deviation_correction_ability_retained_decision": normalize_blank(decision_deviation.get("admission_decision")),
        "interpretation_boundary": route_boundary,
    }
    return patched, pd.DataFrame([patch_row])


def build_inventory_v1_1(
    inventory_v1: pd.DataFrame,
    admission_decision_path: Path,
    admission_audit_path: Path,
    admission_decision: pd.DataFrame,
    root: Path,
) -> pd.DataFrame:
    inv = inventory_v1.copy()
    evidence_id = "route_following_stability_proxy_admission_v1_1"
    row = {
        "evidence_id": evidence_id,
        "evidence_found": True,
        "evidence_path": rel_path(root, admission_decision_path),
        "row_count": int(len(admission_decision)),
        "column_count": int(len(admission_decision.columns)),
        "columns": "|".join(map(str, admission_decision.columns[:80])),
        "supporting_audit_path": rel_path(root, admission_audit_path),
        "interpretation_boundary": BOUNDARY,
    }

    if "supporting_audit_path" not in inv.columns:
        inv["supporting_audit_path"] = ""

    if "evidence_id" in inv.columns and inv["evidence_id"].astype(str).eq(evidence_id).any():
        idx = inv.index[inv["evidence_id"].astype(str).eq(evidence_id)]
        for key, value in row.items():
            inv.loc[idx, key] = value
    else:
        inv = pd.concat([inv, pd.DataFrame([row])], ignore_index=True)

    return inv


def build_audit(
    contract_v1_1: pd.DataFrame,
    contract_patch: pd.DataFrame,
    inventory_v1_1: pd.DataFrame,
    admission_audit: pd.DataFrame,
) -> pd.DataFrame:
    route = first_row(contract_v1_1, ROUTE_AXIS)
    deviation = first_row(contract_v1_1, DEVIATION_AXIS)
    forbidden_cols = [
        c for c in list(contract_v1_1.columns) + list(contract_patch.columns) + list(inventory_v1_1.columns)
        if any(token in str(c).lower() for token in FORBIDDEN_COLUMN_TOKENS)
    ]

    limited_proxy_count = int(contract_v1_1["axis_output_mode"].astype(str).eq("LIMITED_PROXY_AXIS").sum())
    missing_count = int(contract_v1_1["axis_output_mode"].astype(str).eq("MISSING_EVIDENCE_ANNOTATION").sum())
    numeric_count = int(contract_v1_1["axis_output_mode"].astype(str).eq("NUMERIC_AXIS").sum())

    admission_pass = (
        not admission_audit.empty
        and str(admission_audit.iloc[0].get("audit_conclusion", "")).strip()
        == "PASS_CH6_5_5_ROUTE_FOLLOWING_STABILITY_PROXY_ADMISSION_V1_1_GOVERNED_LIMITED_PROXY_CANDIDATE"
    )

    review_reasons: list[str] = []
    if int(len(contract_v1_1)) != 11:
        review_reasons.append("AXIS_COUNT_NOT_11")
    if str(route.get("axis_output_mode", "")) != "LIMITED_PROXY_AXIS":
        review_reasons.append("ROUTE_FOLLOWING_NOT_LIMITED_PROXY")
    if str(deviation.get("axis_output_mode", "")) != "MISSING_EVIDENCE_ANNOTATION":
        review_reasons.append("DEVIATION_CORRECTION_WAS_CHANGED")
    if numeric_count != 0:
        review_reasons.append("NUMERIC_AXIS_PRESENT")
    if limited_proxy_count != 3:
        review_reasons.append("LIMITED_PROXY_AXIS_COUNT_NOT_3")
    if missing_count != 3:
        review_reasons.append("MISSING_EVIDENCE_AXIS_COUNT_NOT_3")
    if forbidden_cols:
        review_reasons.append("FORBIDDEN_OUTPUT_FIELD_PRESENT")
    if not admission_pass:
        review_reasons.append("ADMISSION_AUDIT_NOT_PASS")

    row = {
        "axis_count": int(len(contract_v1_1)),
        "route_following_stability_patched": str(route.get("axis_output_mode", "")) == "LIMITED_PROXY_AXIS",
        "route_following_old_output_mode": normalize_blank(contract_patch.iloc[0].get("old_axis_output_mode")) if not contract_patch.empty else "",
        "route_following_new_output_mode": normalize_blank(route.get("axis_output_mode")),
        "deviation_correction_ability_output_mode": normalize_blank(deviation.get("axis_output_mode")),
        "numeric_axis_count": numeric_count,
        "limited_proxy_axis_count": limited_proxy_count,
        "missing_evidence_annotation_axis_count": missing_count,
        "evidence_inventory_row_count": int(len(inventory_v1_1)),
        "route_following_proxy_admission_evidence_found": bool(
            inventory_v1_1["evidence_id"].astype(str).eq("route_following_stability_proxy_admission_v1_1").any()
            if "evidence_id" in inventory_v1_1.columns else False
        ),
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
        "admission_audit_conclusion": normalize_blank(admission_audit.iloc[0].get("audit_conclusion")) if not admission_audit.empty else "",
        "audit_conclusion": PATCH_REVIEW if review_reasons else PATCH_PASS,
        "review_reasons": "|".join(review_reasons) if review_reasons else "NONE",
        "interpretation_boundary": BOUNDARY,
    }
    return pd.DataFrame([row])


def write_html(
    out_path: Path,
    audit: pd.DataFrame,
    patch: pd.DataFrame,
    contract_v1_1: pd.DataFrame,
    admission_decision: pd.DataFrame,
) -> None:
    def table(df: pd.DataFrame, cols: list[str], n: int = 20) -> str:
        if df.empty:
            return "<p>No rows.</p>"
        use = [c for c in cols if c in df.columns]
        return df[use].head(n).to_html(index=False, escape=True, classes="data")

    route = contract_v1_1[contract_v1_1["axis_id"].astype(str).eq(ROUTE_AXIS)]
    deviation = contract_v1_1[contract_v1_1["axis_id"].astype(str).eq(DEVIATION_AXIS)]
    conclusion = audit.iloc[0]["audit_conclusion"] if not audit.empty else PATCH_REVIEW

    body = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CH6.5.5 Route-Following Axis Contract Patch v1</title>
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
<h1>CH6.5.5 Route-Following Axis Contract Patch v1</h1>
<p class="status">{html.escape(str(conclusion))}</p>
<p class="boundary">{html.escape(BOUNDARY)}</p>

<h2>Patch Summary</h2>
{table(patch, ["axis_id", "old_axis_output_mode", "new_axis_output_mode", "new_radar_output_permission", "admission_decision", "patch_reason"], 5)}

<h2>Audit</h2>
{table(audit, list(audit.columns), 5)}

<h2>Route-Following Patch Detail</h2>
{table(route, ["axis_id", "axis_label_zh", "axis_status", "axis_output_mode", "radar_output_permission", "axis_value_allowed", "primary_evidence_source", "required_consumption_gates", "allowed_use", "disallowed_use"], 5)}

<h2>Deviation Correction Retained</h2>
{table(deviation, ["axis_id", "axis_label_zh", "axis_status", "axis_output_mode", "radar_output_permission", "missing_evidence_reason"], 5)}

<h2>Admission Decision</h2>
{table(admission_decision, ["axis_id", "current_axis_output_mode", "recommended_axis_output_mode", "admission_decision", "proxy_basis", "review_reasons"], 10)}
</body>
</html>
"""
    out_path.write_text(body, encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    contract_path = resolve(root, args.contract_path)
    inventory_path = resolve(root, args.inventory_path)
    admission_root = resolve(root, args.admission_root)
    admission_decision_path = admission_root / ADMISSION_DECISION_FILE
    admission_audit_path = admission_root / ADMISSION_AUDIT_FILE
    out_root = resolve(root, args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)

    contract_v1 = read_csv(contract_path, "personal ability radar axis contract v1")
    inventory_v1 = read_csv(inventory_path, "personal ability radar axis evidence inventory v1")
    admission_decision = read_csv(admission_decision_path, "route-following admission decision v1_1")
    admission_audit = read_csv(admission_audit_path, "route-following admission audit v1_1")

    contract_v1_1, contract_patch = build_patched_contract(
        contract_v1,
        admission_decision,
        admission_decision_path,
        root,
    )
    inventory_v1_1 = build_inventory_v1_1(
        inventory_v1,
        admission_decision_path,
        admission_audit_path,
        admission_decision,
        root,
    )
    audit = build_audit(contract_v1_1, contract_patch, inventory_v1_1, admission_audit)

    outputs = {
        "patch": out_root / "personal_ability_radar_axis_contract_patch_v1.csv",
        "contract_v1_1": out_root / "personal_ability_radar_axis_contract_v1_1.csv",
        "inventory_v1_1": out_root / "personal_ability_radar_axis_evidence_inventory_v1_1.csv",
        "audit": out_root / "personal_ability_radar_axis_contract_patch_audit_v1.csv",
        "html": out_root / "personal_ability_radar_axis_contract_patch_report_v1.html",
    }

    contract_patch.to_csv(outputs["patch"], index=False, encoding="utf-8-sig")
    contract_v1_1.to_csv(outputs["contract_v1_1"], index=False, encoding="utf-8-sig")
    inventory_v1_1.to_csv(outputs["inventory_v1_1"], index=False, encoding="utf-8-sig")
    audit.to_csv(outputs["audit"], index=False, encoding="utf-8-sig")
    write_html(outputs["html"], audit, contract_patch, contract_v1_1, admission_decision)

    route = first_row(contract_v1_1, ROUTE_AXIS)
    deviation = first_row(contract_v1_1, DEVIATION_AXIS)
    print({
        "output_root": str(out_root),
        "audit_conclusion": str(audit.iloc[0]["audit_conclusion"]),
        "route_following_stability_old_mode": str(contract_patch.iloc[0]["old_axis_output_mode"]),
        "route_following_stability_new_mode": str(route.get("axis_output_mode", "")),
        "deviation_correction_ability_mode": str(deviation.get("axis_output_mode", "")),
        "axis_count": int(audit.iloc[0]["axis_count"]),
        "limited_proxy_axis_count": int(audit.iloc[0]["limited_proxy_axis_count"]),
        "missing_evidence_annotation_axis_count": int(audit.iloc[0]["missing_evidence_annotation_axis_count"]),
        "outputs": {k: str(v) for k, v in outputs.items()},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
