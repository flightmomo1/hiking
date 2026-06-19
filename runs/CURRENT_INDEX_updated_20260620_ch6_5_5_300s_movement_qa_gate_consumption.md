# CURRENT INDEX - CH6.5.5 300s Movement QA Gate Consumption

## Status

Current branch:

`codex/ch6-5-5-300s-movement-qa-gate-consumption`

Latest committed result:

`080d9e3 Add CH6.5.5 300s movement QA gate consumption`

Upstream admission review branch:

`codex/ch6-5-5-300s-movement-evidence-admission-review`

Upstream admission review commit:

`d35947c Document CH6.5.5 300s movement admission review`

## Current Effective Component

Script:

`scripts/make_ch6_5_5_300s_movement_qa_gate_consumption_v1.py`

Input study root:

`outputs/report_figures/ch6_5_5_movement_300s_corrected_data_study_v1_1`

Input admission review root:

`outputs/report_figures/ch6_5_5_300s_movement_evidence_admission_review_v1`

Output root:

`outputs/report_figures/ch6_5_5_300s_movement_qa_gate_consumption_v1`

## Outputs

- `movement_300s_consumption_gate_policy_v1.csv`
- `movement_300s_consumption_activity_summary_v1.csv`
- `movement_300s_consumption_window_review_v1.csv`
- `movement_300s_consumption_audit_v1.csv`
- `movement_300s_consumption_report_v1.html`

## Audit Summary

Audit conclusion:

`PASS_CH6_5_5_300S_MOVEMENT_QA_GATE_CONSUMPTION_V1_DESCRIPTIVE_ONLY`

Key counts:

- Baseline activities: 25
- Extra source activity: `6_1`
- Window review rows: 7340
- Horizontal consumable windows: 14
- Vertical consumable windows: 45
- HR context consumable windows: 56
- Route continuity gate policy active: True
- Positive-delta artifact guard policy active: True

## Effective Policy

Admitted downstream consumption prerequisites:

- `route_continuity_300s_gate`
- `positive_delta_artifact_guard`

Retained only as descriptive supporting evidence:

- Horizontal 300s movement evidence
- Vertical 300s movement evidence
- HR context at representative 300s windows

## Boundary

This component does not compute or authorize radar scores, ability scores, ability ranks, ability classes, THCI scores, final hiking risk scores, route suitability scores, go/no-go decisions, medical diagnoses, or causality claims.

## Recommended Next Step

Downstream report or radar-adjacent components may reference 300s movement evidence only after consuming this QA gate layer.
