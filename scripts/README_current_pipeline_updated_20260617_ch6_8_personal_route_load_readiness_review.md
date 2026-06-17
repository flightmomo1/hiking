# README Update — CH6.8 Personal Route-Load Readiness Review v1.1

## Working Directory

`D:\mountain_work\115_osm`

## Purpose

This update records the current recommended descriptive evidence chain for moving from Chapter 6.5 route-load / activity behavior evidence and Chapter 6.7 completion / HR context toward a conservative personal route-load readiness review layer.

The current recommended output is a **descriptive readiness evidence gate**. It is not a route suitability judgment and does not decide whether a person or team is suitable or unsuitable for a route.

## Current Recommended Scripts

### CH6.7 HR recovery from IB3C events v1.1

Script:

`skills/scripts or repo script path expected in repo:`

`D:\mountain_work\115_osm\scripts\make_ch6_7_hr_recovery_from_ib3c_events_v1_1.py`

Primary input:

`outputs\ib3c_activity_behavior_events_adaptive_speed_v1_phase3c_recovery_interpretation_26batch\qixing_lengshuikeng\*\*_ib3c_behavior_events.csv`

Output root:

`outputs\report_figures\ch6_7_hr_recovery_from_ib3c_events_v1_1`

Key outputs:

- `activity_hr_recovery_events_from_ib3c_v1_1.csv`
- `activity_hr_recovery_activity_summary_from_ib3c_v1_1.csv`
- `activity_hr_recovery_phase_summary_from_ib3c_v1_1.csv`
- `activity_hr_recovery_group_summary_from_ib3c_v1_1.csv`
- `activity_hr_recovery_from_ib3c_audit_v1_1.csv`
- `activity_hr_recovery_from_ib3c_report_v1_1.html`

Audit summary:

- `event_csv_count`: 26
- `raw_event_rows`: 346
- `standardized_event_rows`: 346
- `activity_count`: 26
- `route_core_event_count`: 316
- `route_core_facility_rest_event_count`: 42
- `activities_with_route_core_events`: 18
- `activities_with_route_core_facility_rest_events`: 15
- `confirmed_hr_recovery_event_count`: 88
- `high_hr_pause_without_recovery_event_count`: 56
- `forbidden_columns_absent`: True
- `audit_conclusion`: `PASS_CH6_7_HR_RECOVERY_FROM_IB3C_EVENTS_V1_1_DESCRIPTIVE_ONLY`

Version decision:

- v1 is retained as a conservative baseline.
- v1.1 is the current recommended HR recovery evidence layer.
- v1.1 adds `ROUTE_CORE_FACILITY_REST_REVIEW_EVENT` and includes on-route `facility_rest` events when `on_route_ratio >= 0.8`.

### CH6.8 personal route-load readiness review v1.1

Script:

`D:\mountain_work\115_osm\scripts\make_ch6_8_personal_route_load_readiness_review_v1_1.py`

Output root:

`outputs\report_figures\ch6_8_personal_route_load_readiness_review_v1_1`

Key outputs:

- `personal_route_load_readiness_review_v1_1.csv`
- `personal_route_load_readiness_group_summary_v1_1.csv`
- `personal_route_load_readiness_input_contract_v1_1.csv`
- `personal_route_load_readiness_audit_v1_1.csv`
- `personal_route_load_readiness_report_v1_1.html`

Audit summary:

- `activity_count`: 26
- `group_summary_rows`: 3
- `standard_prep_reasonable_count`: 0
- `conservative_pacing_recommended_count`: 10
- `early_checkpoint_review_required_count`: 15
- `weather_sensitive_review_required_count`: 0
- `insufficient_personal_history_count`: 1
- `missing_inputs`: empty
- `forbidden_columns_absent`: True
- `audit_conclusion`: `PASS_CH6_8_PERSONAL_ROUTE_LOAD_READINESS_REVIEW_V1_1_DESCRIPTIVE_ONLY`

Version decision:

- v1 is retained as a high-sensitivity smoke version.
- v1.1 is the current recommended readiness review version.
- v1.1 prevents `EARLY_CHECKPOINT_HIGH_HR_EVIDENCE_PRESENT` from automatically becoming the primary gate.
- `EARLY_CHECKPOINT_REVIEW_REQUIRED` is elevated only when early checkpoint HR evidence is strong, or when mid-high early HR evidence is paired with slow completion, high-load HR evidence, limited route-core HR recovery evidence, or high-HR no-recovery burden.

## CH6.8 Inputs

The v1.1 readiness review consumes existing descriptive evidence only:

- `outputs\report_figures\ch6_7_hr_recovery_from_ib3c_events_v1_1\activity_hr_recovery_activity_summary_from_ib3c_v1_1.csv`
- `outputs\report_figures\ch6_7_hr_lifecycle_recovery_profile_v2\activity_hr_lifecycle_summary_v2.csv`
- `outputs\report_figures\ch6_7_completion_feasibility_review_v1_1\completion_feasibility_conclusion_v1_1.csv`
- `outputs\report_figures\ch6_7_completion_feasibility_review_v1_1\completion_feasibility_group_summary_v1_1.csv`
- `outputs\report_figures\ch6_7_completion_feasibility_review_v1_1\completion_hr_effort_context_v1_1.csv`
- `outputs\report_figures\ch6_7_planning_context_fusion_v1_1\planning_context_route_windows_v1_1.csv`
- `outputs\report_figures\ch6_5_route_load_context_index_v1\route_load_context_windows_v1.csv`

## Gate Labels

The current v1.1 primary gate labels are descriptive planning/review labels:

- `EARLY_CHECKPOINT_REVIEW_REQUIRED`
- `CONSERVATIVE_PACING_RECOMMENDED`
- `INSUFFICIENT_PERSONAL_HISTORY`
- `STANDARD_PREP_REASONABLE` is available in the schema but currently has zero activities.
- `WEATHER_SENSITIVE_REVIEW_REQUIRED` can appear in `readiness_review_flags`, but the audit count is primary-gate-only and is currently zero.

## Method Boundary

This update preserves the existing descriptive-only boundary. The CH6.8 readiness review does not generate or authorize:

- cardiopulmonary diagnosis
- personal ability score
- personal ability rank
- personal ability class
- route suitability score
- THCI score
- radar score
- final hiking risk score
- causal claims from weather, OSM proximity, route-load, or IB3C/IB3D event overlays

Weather context remains descriptive background unless explicitly supported by a safe route-window source. Missing weather must not be filled as zero, normal, calm, or no-rain evidence.

## Current Interpretation

CH6.8 v1.1 is suitable for report-level and planning-discussion evidence. It should be presented as a conservative review layer showing whether existing personal activity evidence suggests:

- standard preparation may be sufficient,
- conservative pacing is recommended,
- early checkpoint review should be emphasized,
- or personal history is insufficient.

It should not be presented as an automatic go/no-go or suitable/unsuitable decision.
