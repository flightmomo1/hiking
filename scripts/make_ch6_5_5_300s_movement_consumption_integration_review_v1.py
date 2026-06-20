#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build CH6.5.5 300s movement consumption integration review v1.

This script inventories downstream scripts that may reference CH6.5.5 300-second
movement evidence and reviews whether they also reference the QA gate consumption
policy.

It is an integration review only. It does not compute radar scores, ability
scores, ability ranks, ability classes, THCI scores, final hiking risk scores,
route suitability scores, go/no-go decisions, medical diagnoses, or causality
claims.
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_CONSUMPTION_ROOT = "outputs/report_figures/ch6_5_5_300s_movement_qa_gate_consumption_v1"
DEFAULT_STUDY_ROOT = "outputs/report_figures/ch6_5_5_movement_300s_corrected_data_study_v1_1"
DEFAULT_OUTPUT_ROOT = "outputs/report_figures/ch6_5_5_300s_movement_consumption_integration_review_v1"

BOUNDARY = (
    "CH6.5.5 300s movement consumption integration review v1 is an integration "
    "review layer only. It inventories scripts that may reference 300s movement "
    "evidence and checks whether they consume the QA gate policy. It does not "
    "compute or authorize radar scores, ability scores, ability ranks, ability "
    "classes, THCI scores, final hiking risk scores, route suitability scores, "
    "go/no-go decisions, medical diagnoses, or causality claims."
)

PASS = "PASS_CH6_5_5_300S_MOVEMENT_CONSUMPTION_INTEGRATION_REVIEW_V1_DESCRIPTIVE_ONLY"
REVIEW = "REVIEW_REQUIRED_CH6_5_5_300S_MOVEMENT_CONSUMPTION_INTEGRATION_REVIEW_V1"

SCRIPT_GLOBS = [
    "scripts/make_ch6_5_5_*.py",
    "scripts/make_ch6_5_*.py",
    "scripts/make_ch6_*.py",
]

EVIDENCE_TOKENS = [
    "movement_300s",
    "300s_movement",
    "horizontal_300s",
    "vertical_300s",
    "hr_at_representative_300s",
    "movement_hr_ascent",
    "movement_hr_pause_recovery",
    "ch6_5_5_movement_300s_corrected_data_study",
]

CONSUMPTION_TOKENS = [
    "movement_300s_consumption_gate_policy_v1",
    "movement_300s_consumption_activity_summary_v1",
    "movement_300s_consumption_window_review_v1",
    "ch6_5_5_300s_movement_qa_gate_consumption_v1",
    "route_continuity_300s_gate",
    "positive_delta_artifact_guard",
]

SELF_COMPONENT_TOKENS = [
    "corrected_data_study_v1",
    "corrected_data_study_v1_1",
    "evidence_admission_review_v1",
    "qa_gate_consumption_v1",
    "consumption_integration_review_v1",
]

FORBIDDEN_OUTPUT_COLUMN_PATTERNS = [
    "radar_score",
    "ability_score",
    "ability_rank",
    "ability_class",
    "go_no_go",
    "medical_diagnosis",
    "causality_claim",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=r"D:\mountain_work\115_osm")
    parser.add_argument("--consumption-root", default=DEFAULT_CONSUMPTION_ROOT)
    parser.add_argument("--study-root", default=DEFAULT_STUDY_ROOT)
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


def contains_any(text: str, tokens: list[str]) -> bool:
    lower = text.lower()
    return any(t.lower() in lower for t in tokens)


def matched_tokens(text: str, tokens: list[str]) -> str:
    lower = text.lower()
    hits = [t for t in tokens if t.lower() in lower]
    return "|".join(hits) if hits else "NONE"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except UnicodeDecodeError:
        return path.read_text(encoding="cp950", errors="replace")


def collect_scripts(root: Path) -> list[Path]:
    found: dict[str, Path] = {}
    for pattern in SCRIPT_GLOBS:
        for p in root.glob(pattern):
            if p.is_file():
                found[str(p.relative_to(root)).replace("\\", "/")] = p
    return [found[k] for k in sorted(found)]


def classify_script(path: Path, text: str) -> dict[str, Any]:
    name = path.name
    rel = str(path).replace("\\", "/")

    references_evidence = contains_any(text, EVIDENCE_TOKENS)
    references_consumption = contains_any(text, CONSUMPTION_TOKENS)
    is_self_component = contains_any(name, SELF_COMPONENT_TOKENS) or contains_any(rel, SELF_COMPONENT_TOKENS)

    if is_self_component:
        integration_status = "SELF_COMPONENT_OK"
        reason = "Script is part of the study, admission review, QA gate consumption, or this integration review layer."
    elif references_evidence and references_consumption:
        integration_status = "INTEGRATED_WITH_CONSUMPTION_GATE"
        reason = "Script references 300s movement evidence and also references consumption gate policy."
    elif references_evidence and not references_consumption:
        integration_status = "GAP_REVIEW_REQUIRED_EVIDENCE_WITHOUT_CONSUMPTION_GATE"
        reason = "Script references 300s movement evidence but does not reference the QA gate consumption policy."
    else:
        integration_status = "NO_300S_MOVEMENT_EVIDENCE_REFERENCE"
        reason = "No 300s movement evidence reference detected by token scan."

    return {
        "script_path": rel,
        "script_name": name,
        "references_300s_movement_evidence": references_evidence,
        "references_consumption_gate_policy": references_consumption,
        "self_component": is_self_component,
        "matched_evidence_tokens": matched_tokens(text, EVIDENCE_TOKENS),
        "matched_consumption_tokens": matched_tokens(text, CONSUMPTION_TOKENS),
        "integration_status": integration_status,
        "integration_reason": reason,
        "allowed_use": "integration_review_only",
        "disallowed_use": "score_rank_class_or_decision_generation",
        "interpretation_boundary": BOUNDARY,
    }


def build_script_inventory(root: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for p in collect_scripts(root):
        text = read_text(p)
        rows.append(classify_script(p.relative_to(root), text))
    return pd.DataFrame(rows)


def build_gap_review(inventory: pd.DataFrame) -> pd.DataFrame:
    if inventory.empty:
        return pd.DataFrame()

    rows = inventory[
        inventory["integration_status"].astype(str).eq("GAP_REVIEW_REQUIRED_EVIDENCE_WITHOUT_CONSUMPTION_GATE")
    ].copy()

    if rows.empty:
        return pd.DataFrame([{
            "gap_status": "NO_CONSUMPTION_GATE_GAP_DETECTED",
            "script_path": "NONE",
            "review_recommendation": "No downstream script requiring remediation was detected by token scan.",
            "required_action": "NONE",
            "interpretation_boundary": BOUNDARY,
        }])

    out_rows: list[dict[str, Any]] = []
    for _, r in rows.iterrows():
        out_rows.append({
            "gap_status": "GAP_REVIEW_REQUIRED",
            "script_path": r["script_path"],
            "matched_evidence_tokens": r["matched_evidence_tokens"],
            "matched_consumption_tokens": r["matched_consumption_tokens"],
            "review_recommendation": (
                "Inspect this script. If it consumes CH6.5.5 300s movement evidence downstream, "
                "require movement_300s_consumption_gate_policy_v1 and related activity/window "
                "consumption outputs before using the evidence."
            ),
            "required_action": "ADD_CONSUMPTION_GATE_OR_MARK_AS_SELF_STUDY_CONTEXT",
            "interpretation_boundary": BOUNDARY,
        })
    return pd.DataFrame(out_rows)


def build_audit(
    consumption_audit: pd.DataFrame,
    inventory: pd.DataFrame,
    gap_review: pd.DataFrame,
    output_columns: list[str],
) -> pd.DataFrame:
    forbidden = [
        c for c in output_columns
        if any(p in c.lower() for p in FORBIDDEN_OUTPUT_COLUMN_PATTERNS)
    ]

    gap_count = int(
        inventory["integration_status"].astype(str).eq(
            "GAP_REVIEW_REQUIRED_EVIDENCE_WITHOUT_CONSUMPTION_GATE"
        ).sum()
    ) if not inventory.empty else 0

    evidence_ref_count = int(inventory["references_300s_movement_evidence"].sum()) if not inventory.empty else 0
    consumption_ref_count = int(inventory["references_consumption_gate_policy"].sum()) if not inventory.empty else 0
    self_count = int(inventory["self_component"].sum()) if not inventory.empty else 0

    review_reasons: list[str] = []
    if consumption_audit.empty:
        review_reasons.append("MISSING_CONSUMPTION_AUDIT")
    elif not str(consumption_audit.iloc[0].get("audit_conclusion", "")).startswith("PASS_"):
        review_reasons.append("CONSUMPTION_AUDIT_NOT_PASS")
    if gap_count > 0:
        review_reasons.append("DOWNSTREAM_CONSUMPTION_GATE_GAP_REVIEW_REQUIRED")
    if forbidden:
        review_reasons.append("FORBIDDEN_OUTPUT_FIELD_PRESENT")

    row = {
        "consumption_audit_conclusion": consumption_audit.iloc[0].get("audit_conclusion", "") if not consumption_audit.empty else "",
        "scanned_script_count": int(len(inventory)),
        "self_component_script_count": self_count,
        "scripts_referencing_300s_movement_evidence_count": evidence_ref_count,
        "scripts_referencing_consumption_gate_policy_count": consumption_ref_count,
        "consumption_gate_gap_count": gap_count,
        "gap_review_row_count": int(len(gap_review)),
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


def write_html(out_path: Path, audit: pd.DataFrame, inventory: pd.DataFrame, gap_review: pd.DataFrame) -> None:
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
<title>CH6.5.5 300s Movement Consumption Integration Review v1</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2933; }}
h1, h2 {{ margin-bottom: 8px; }}
.boundary {{ border-left: 4px solid #687078; padding: 8px 12px; background: #f5f7f8; }}
.status {{ font-weight: 700; }}
table.data {{ border-collapse: collapse; font-size: 12px; margin: 12px 0 24px; }}
table.data th, table.data td {{ border: 1px solid #d6dde3; padding: 5px 7px; }}
table.data th {{ background: #eef2f5; }}
</style>
</head>
<body>
<h1>CH6.5.5 300s Movement Consumption Integration Review v1</h1>
<p class="status">{html.escape(str(conclusion))}</p>
<p class="boundary">{html.escape(BOUNDARY)}</p>

<h2>Audit</h2>
{table(audit, list(audit.columns), 5)}

<h2>Consumption Gap Review</h2>
{table(gap_review, ["gap_status", "script_path", "matched_evidence_tokens", "matched_consumption_tokens", "review_recommendation", "required_action"], 80)}

<h2>Script Inventory</h2>
{table(inventory, ["script_path", "references_300s_movement_evidence", "references_consumption_gate_policy", "self_component", "integration_status", "matched_evidence_tokens", "matched_consumption_tokens"], 160)}
</body>
</html>
"""
    out_path.write_text(body, encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    consumption_root = resolve(root, args.consumption_root)
    out_root = resolve(root, args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)

    consumption_audit = read_csv(
        consumption_root / "movement_300s_consumption_audit_v1.csv",
        "movement 300s consumption audit v1",
    )

    inventory = build_script_inventory(root)
    gap_review = build_gap_review(inventory)
    output_columns = list(inventory.columns) + list(gap_review.columns)
    audit = build_audit(consumption_audit, inventory, gap_review, output_columns)

    outputs = {
        "script_inventory": out_root / "movement_300s_integration_script_inventory_v1.csv",
        "gap_review": out_root / "movement_300s_integration_consumption_gap_review_v1.csv",
        "audit": out_root / "movement_300s_integration_audit_v1.csv",
        "html": out_root / "movement_300s_integration_review_report_v1.html",
    }

    inventory.to_csv(outputs["script_inventory"], index=False, encoding="utf-8-sig")
    gap_review.to_csv(outputs["gap_review"], index=False, encoding="utf-8-sig")
    audit.to_csv(outputs["audit"], index=False, encoding="utf-8-sig")
    write_html(outputs["html"], audit, inventory, gap_review)

    print({
        "output_root": str(out_root),
        "scanned_script_count": int(audit.iloc[0]["scanned_script_count"]),
        "scripts_referencing_300s_movement_evidence_count": int(audit.iloc[0]["scripts_referencing_300s_movement_evidence_count"]),
        "scripts_referencing_consumption_gate_policy_count": int(audit.iloc[0]["scripts_referencing_consumption_gate_policy_count"]),
        "consumption_gate_gap_count": int(audit.iloc[0]["consumption_gate_gap_count"]),
        "audit_conclusion": str(audit.iloc[0]["audit_conclusion"]),
        "outputs": {k: str(v) for k, v in outputs.items()},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
