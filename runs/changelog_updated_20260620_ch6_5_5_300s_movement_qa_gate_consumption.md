# Changelog - CH6.5.5 300s Movement QA Gate Consumption

## 2026-06-20

Added CH6.5.5 300s movement QA gate consumption v1.

## Added Script

`scripts/make_ch6_5_5_300s_movement_qa_gate_consumption_v1.py`

## Added Output Root

`outputs/report_figures/ch6_5_5_300s_movement_qa_gate_consumption_v1`

## Added Output Files

- `movement_300s_consumption_gate_policy_v1.csv`
- `movement_300s_consumption_activity_summary_v1.csv`
- `movement_300s_consumption_window_review_v1.csv`
- `movement_300s_consumption_audit_v1.csv`
- `movement_300s_consumption_report_v1.html`

## Audit Result

`PASS_CH6_5_5_300S_MOVEMENT_QA_GATE_CONSUMPTION_V1_DESCRIPTIVE_ONLY`

## Key Result

The component materializes the two admitted QA items from the 300s movement admission review:

- `route_continuity_300s_gate`
- `positive_delta_artifact_guard`

These are now explicit downstream consumption prerequisites before any 300s movement evidence is referenced.

## Counts

- Baseline activities: 25
- Extra source activity: `6_1`
- Window review rows: 7340
- Horizontal consumable windows: 14
- Vertical consumable windows: 45
- HR context consumable windows: 56

## Boundary

This commit does not promote 300s horizontal or vertical evidence into a standalone radar axis.

No score, rank, class, THCI, final hiking risk, route suitability, go/no-go, medical diagnosis, or causality claim was produced.
