# CURRENT INDEX - CH6.5.5 300s Movement Consumption Integration Review

## Status

Current branch:

`codex/ch6-5-5-300s-movement-consumption-integration-review`

Latest committed result:

`5796c96 Add CH6.5.5 300s movement consumption integration review`

Upstream QA gate consumption branch:

`codex/ch6-5-5-300s-movement-qa-gate-consumption`

Upstream QA gate consumption commit:

`385c980 Document CH6.5.5 300s movement QA gate consumption`

## Current Effective Component

Script:

`scripts/make_ch6_5_5_300s_movement_consumption_integration_review_v1.py`

Input root:

`outputs/report_figures/ch6_5_5_300s_movement_qa_gate_consumption_v1`

Output root:

`outputs/report_figures/ch6_5_5_300s_movement_consumption_integration_review_v1`

## Outputs

- `movement_300s_integration_script_inventory_v1.csv`
- `movement_300s_integration_consumption_gap_review_v1.csv`
- `movement_300s_integration_audit_v1.csv`
- `movement_300s_integration_review_report_v1.html`

## Audit Summary

Audit conclusion:

`PASS_CH6_5_5_300S_MOVEMENT_CONSUMPTION_INTEGRATION_REVIEW_V1_DESCRIPTIVE_ONLY`

Key counts:

- Scanned scripts: 19
- Scripts referencing 300s movement evidence: 5
- Scripts referencing consumption gate policy: 3
- Self component scripts: 5
- Consumption gate gaps: 0

## Result

No downstream script was detected that references 300s movement evidence without also consuming the QA gate policy, except self components that are part of the study / admission / consumption / integration layers.

## Boundary

This integration review does not compute or authorize radar scores, ability scores, ability ranks, ability classes, THCI scores, final hiking risk scores, route suitability scores, go/no-go decisions, medical diagnoses, or causality claims.

## Recommended Next Step

Proceed to personal ability radar axis contract v1.
