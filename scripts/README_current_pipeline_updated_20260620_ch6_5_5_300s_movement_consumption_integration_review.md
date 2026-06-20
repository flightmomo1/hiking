# README Current Pipeline - CH6.5.5 300s Movement Consumption Integration Review

## Component

CH6.5.5 300s movement consumption integration review v1.

## Script

`scripts/make_ch6_5_5_300s_movement_consumption_integration_review_v1.py`

## Inputs

QA gate consumption root:

`outputs/report_figures/ch6_5_5_300s_movement_qa_gate_consumption_v1`

Required input:

- `movement_300s_consumption_audit_v1.csv`

## Outputs

Output root:

`outputs/report_figures/ch6_5_5_300s_movement_consumption_integration_review_v1`

Output files:

- `movement_300s_integration_script_inventory_v1.csv`
- `movement_300s_integration_consumption_gap_review_v1.csv`
- `movement_300s_integration_audit_v1.csv`
- `movement_300s_integration_review_report_v1.html`

## Purpose

This component inventories downstream scripts that may reference CH6.5.5 300s movement evidence and reviews whether they also reference the QA gate consumption policy.

## Result

No unresolved downstream consumption gate gap was detected.

Audit conclusion:

`PASS_CH6_5_5_300S_MOVEMENT_CONSUMPTION_INTEGRATION_REVIEW_V1_DESCRIPTIVE_ONLY`

## Contract Boundary

This script is not a scoring layer.

It must not compute or authorize:

- radar scores
- ability scores
- ability ranks
- ability classes
- THCI scores
- final hiking risk scores
- route suitability scores
- go/no-go decisions
- medical diagnoses
- causality claims
