# README Current Pipeline - CH6.5.5 300s Movement QA Gate Consumption

## Component

CH6.5.5 300s movement QA gate consumption v1.

## Script

`scripts/make_ch6_5_5_300s_movement_qa_gate_consumption_v1.py`

## Inputs

Study evidence root:

`outputs/report_figures/ch6_5_5_movement_300s_corrected_data_study_v1_1`

Required study files:

- `movement_300s_window_candidates_v1_1.csv`

Admission review root:

`outputs/report_figures/ch6_5_5_300s_movement_evidence_admission_review_v1`

Required admission review files:

- `movement_300s_admission_axis_decision_v1.csv`
- `movement_300s_admission_activity_coverage_v1.csv`
- `movement_300s_admission_audit_v1.csv`

## Outputs

Output root:

`outputs/report_figures/ch6_5_5_300s_movement_qa_gate_consumption_v1`

Output files:

- `movement_300s_consumption_gate_policy_v1.csv`
- `movement_300s_consumption_activity_summary_v1.csv`
- `movement_300s_consumption_window_review_v1.csv`
- `movement_300s_consumption_audit_v1.csv`
- `movement_300s_consumption_report_v1.html`

## Purpose

This component materializes downstream consumption rules for 300-second movement evidence.

It consumes the previous admission review and marks which rows may be referenced as descriptive supporting evidence after QA gates are applied.

## Active Consumption Gates

Required for horizontal or vertical 300s movement evidence:

- `route_continuity_300s_gate`

Required for vertical 300s movement evidence:

- `positive_delta_artifact_guard`

Required for formal downstream consumption:

- baseline population gate: only `RADAR_BASELINE_ACTIVITY` rows may enter formal downstream tables.

## Allowed Use

Allowed:

- descriptive supporting evidence
- QA gate / guard
- HR context only after movement evidence is already gated

Disallowed:

- standalone radar axis
- radar score
- ability score
- ability rank
- ability class
- route suitability score
- go/no-go decision
- medical diagnosis
- causality claim

## Audit

Audit conclusion:

`PASS_CH6_5_5_300S_MOVEMENT_QA_GATE_CONSUMPTION_V1_DESCRIPTIVE_ONLY`

## Contract Boundary

This script is not a scoring layer.

Missing evidence must remain missing / insufficient evidence. Do not zero-fill missing evidence.
