# README Current Pipeline — CH6.5.5 300s Movement Evidence Admission Review

## Component

CH6.5.5 300s movement evidence admission review v1.

## Script

`scripts/make_ch6_5_5_300s_movement_evidence_admission_review_v1.py`

## Inputs

Primary input root:

`outputs/report_figures/ch6_5_5_movement_300s_corrected_data_study_v1_1`

Required input files:

- `movement_300s_audit_v1_1.csv`
- `movement_300s_activity_summary_v1_1.csv`
- `movement_300s_window_candidates_v1_1.csv`

## Outputs

Output root:

`outputs/report_figures/ch6_5_5_300s_movement_evidence_admission_review_v1`

Output files:

- `movement_300s_admission_axis_decision_v1.csv`
- `movement_300s_admission_activity_coverage_v1.csv`
- `movement_300s_admission_audit_v1.csv`
- `movement_300s_admission_review_report_v1.html`

## Purpose

This component reviews whether corrected 300-second horizontal movement, vertical ascent, HR context, route continuity, and positive-delta artifact guard evidence is suitable for downstream admission.

It is an admission-review layer, not a scoring layer.

## Decision

Not admitted as standalone radar axes:

- Horizontal 300s route-speed evidence
- Vertical 300s VAM evidence
- Vertical 300s gain evidence
- Combined horizontal + vertical 300s evidence

Admitted as QA gate / guard:

- `route_continuity_300s_gate`
- `positive_delta_artifact_guard`

Retained as supporting context:

- HR at representative 300s windows

## Contract Boundary

This script must not compute or authorize:

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

Missing evidence must remain missing / insufficient evidence. Do not zero-fill missing evidence.
