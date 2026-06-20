# Changelog — CH6.5.5 300s Movement Evidence Admission Review

## 2026-06-20

Added CH6.5.5 300s movement evidence admission review.

## Added Script

`scripts/make_ch6_5_5_300s_movement_evidence_admission_review_v1.py`

## Added Evidence Outputs

Output root:

`outputs/report_figures/ch6_5_5_300s_movement_evidence_admission_review_v1`

Files:

- `movement_300s_admission_axis_decision_v1.csv`
- `movement_300s_admission_activity_coverage_v1.csv`
- `movement_300s_admission_audit_v1.csv`
- `movement_300s_admission_review_report_v1.html`

## Audit Result

Audit conclusion:

`PASS_CH6_5_5_300S_MOVEMENT_EVIDENCE_ADMISSION_REVIEW_V1_DESCRIPTIVE_ONLY`

Key counts:

- Baseline activities: 25
- Extra source activities: 1 (`6_1`)
- Horizontal evidence activities: 6
- Vertical evidence activities: 6
- Both horizontal and vertical evidence activities: 2
- Standalone axis admitted count: 0
- QA gate or guard admitted count: 2

## Admission Results

Not admitted as standalone radar axes:

- `horizontal_300s_route_speed_p90_mps`
- `vertical_300s_vam_p90_mph`
- `vertical_300s_gain_p90_m`
- `combined_horizontal_vertical_300s_evidence`

Retained as supporting context:

- `hr_at_representative_300s_windows`

Admitted as QA gate / guard:

- `route_continuity_300s_gate`
- `positive_delta_artifact_guard`

## Boundary

No score, rank, class, THCI, final hiking risk, route suitability, go/no-go, medical diagnosis, or causality claim was produced.
