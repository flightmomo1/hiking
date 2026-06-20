# Latest Handoff Prompt - CH6.5.5 300s Movement QA Gate Consumption

Continue from:

`D:\mountain_work\115_osm`

Current completed branch:

`codex/ch6-5-5-300s-movement-qa-gate-consumption`

Latest commit:

`080d9e3 Add CH6.5.5 300s movement QA gate consumption`

The branch has been pushed to origin.

## Completed Work

CH6.5.5 300s movement QA gate consumption v1 has been completed.

Main script:

`scripts/make_ch6_5_5_300s_movement_qa_gate_consumption_v1.py`

Output root:

`outputs/report_figures/ch6_5_5_300s_movement_qa_gate_consumption_v1`

Key outputs:

- `movement_300s_consumption_gate_policy_v1.csv`
- `movement_300s_consumption_activity_summary_v1.csv`
- `movement_300s_consumption_window_review_v1.csv`
- `movement_300s_consumption_audit_v1.csv`
- `movement_300s_consumption_report_v1.html`

## Input Evidence

Study evidence root:

`outputs/report_figures/ch6_5_5_movement_300s_corrected_data_study_v1_1`

Admission review root:

`outputs/report_figures/ch6_5_5_300s_movement_evidence_admission_review_v1`

Admission review conclusion:

`300s horizontal / vertical movement evidence is not admitted as standalone radar axis. Route continuity and positive-delta artifact guard are admitted as QA gate / guard.`

## QA Gate Consumption Result

The following policies are active:

- `route_continuity_300s_gate`
- `positive_delta_artifact_guard`

Consumption counts:

- Baseline activities: 25
- Extra source activity: `6_1`
- Window review rows: 7340
- Horizontal consumable windows: 14
- Vertical consumable windows: 45
- HR context consumable windows: 56

## Boundary

Do not convert these outputs into radar scores, ability scores, ranks, classes, THCI scores, final hiking risk scores, route suitability scores, go/no-go decisions, medical diagnoses, or causality claims.

## Suggested Next Branch

Possible next branch:

`codex/ch6-5-5-300s-movement-consumption-integration-review`

Suggested task:

Review downstream components that reference 300s movement evidence and require them to consume the QA gate policy before using horizontal, vertical, or HR context evidence.
