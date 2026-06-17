# Current Index — CH6.7 Planning, Completion, and HR Context Evidence

## Working Directory

`D:\mountain_work\115_osm`

## Branch

Verify with:

`git branch --show-current`

Recent related branch context:

`codex/ib3-route-load-behavior-story-report-v1`

## Current Recommended Layers

### 1. Completion feasibility review

Current recommended version: `v1.1`

Scripts:

- `D:\mountain_work\115_osm\scripts\make_ch6_7_completion_feasibility_review_v1.py`
- `D:\mountain_work\115_osm\scripts\make_ch6_7_completion_feasibility_review_v1_1.py`

Output roots:

- current: `outputs\report_figures\ch6_7_completion_feasibility_review_v1_1`
- retained baseline: `outputs\report_figures\ch6_7_completion_feasibility_review_v1`

Effective v1.1 outputs:

- `activity_completion_weather_context_v1_1.csv`
- `completion_feasibility_conclusion_v1_1.csv`
- `completion_feasibility_group_summary_v1_1.csv`
- `completion_feasibility_review_audit_v1_1.csv`
- `completion_feasibility_review_report_v1_1.html`
- `completion_feasibility_review_run_report_v1_1.md`
- `completion_hr_effort_context_v1_1.csv`
- `completion_hr_effort_group_summary_v1_1.csv`
- `completion_time_distribution_v1_1.csv`
- `completion_time_distribution_v1_1.png`
- `completion_weather_group_summary_v1_1.csv`

Status:

- v1.1 is current recommended.
- v1 is retained as baseline.

### 2. HR lifecycle recovery profile

Current recommended version: `v2`

Scripts:

- `D:\mountain_work\115_osm\scripts\make_ch6_7_hr_lifecycle_recovery_profile_v2.py`
- `D:\mountain_work\115_osm\scripts\make_ch6_7_hr_lifecycle_recovery_profile_v2_before_plotfix.py`

Output root:

`outputs\report_figures\ch6_7_hr_lifecycle_recovery_profile_v2`

Effective outputs:

- `activity_hr_lifecycle_audit_v2.csv`
- `activity_hr_lifecycle_summary_v2.csv`
- `activity_hr_lifecycle_report_v2.html`
- `activity_hr_lifecycle_run_report_v2.md`
- `activity_hr_recovery_phase_summary_v2.csv`
- profile PNGs and route-window median PNGs

Status:

- v2 is current recommended.
- `before_plotfix` is retained for traceability.

### 3. Planning context fusion

Current recommended version: `v1.1`

Scripts:

- `D:\mountain_work\115_osm\scripts\make_ch6_7_planning_context_fusion_v1.py`
- `D:\mountain_work\115_osm\scripts\make_ch6_7_planning_context_fusion_v1_1.py`
- `D:\mountain_work\115_osm\scripts\make_ch6_7_planning_context_fusion_report_v1_1.py`

Output roots:

- current: `outputs\report_figures\ch6_7_planning_context_fusion_v1_1`
- retained baseline: `outputs\report_figures\ch6_7_planning_context_fusion_v1`
- report: `outputs\report_figures\ch6_7_planning_context_fusion_report_v1_1`

Effective v1.1 outputs:

- `planning_context_route_windows_v1_1.csv`
- `planning_context_activity_summary_v1_1.csv`
- `planning_context_fusion_audit_v1_1.csv`
- `planning_context_fusion_run_report_v1_1.md`
- `planning_context_fusion_report_v1_1.html`
- `planning_context_fusion_report_v1_1.png`

Status:

- v1.1 is current recommended.
- v1 is retained as baseline.
- report v1.1 is current report-facing presentation layer.

## Package Role

This package is the CH6.7 descriptive planning evidence chain. It connects CH6.5 route-load / behavior evidence to CH6.8 personal route-load readiness review.

It supports report-level planning discussion about:

- completion feasibility;
- slow / middle / fast completion groups;
- weather and HR effort background;
- early checkpoint interpretation;
- HR lifecycle and recovery context;
- route-window planning caution context.

## Interpretation Boundary

This current index does not authorize:

- cardiopulmonary diagnosis;
- ability score;
- ability rank;
- ability class;
- route suitability score;
- THCI score;
- radar score;
- final hiking risk score;
- automatic suitable/unsuitable decision;
- automatic go/no-go decision;
- weather causality inference;
- OSM proximity as actual facility use.

Planning caution labels and completion/HR context are descriptive evidence only.

## Recommended Next Action

Commit scripts, outputs, and documentation as a single CH6.7 planning/completion/HR context package if staged scope checks pass.

Suggested commit message:

`Add CH6.7 planning completion and HR context evidence`
