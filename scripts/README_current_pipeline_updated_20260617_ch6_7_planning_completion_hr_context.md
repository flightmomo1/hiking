# README Update — CH6.7 Planning, Completion, and HR Context Evidence

## Working Directory

`D:\mountain_work\115_osm`

## Purpose

This update records the CH6.7 descriptive evidence package that supports pre-trip planning and in-activity control discussion.

The package integrates three report-facing evidence groups:

1. completion feasibility review v1 / v1.1,
2. HR lifecycle recovery profile v2,
3. planning context fusion v1 / v1.1 and planning context fusion report v1.1.

This package is an upstream descriptive evidence chain for CH6.8 personal route-load readiness review. It does not generate route suitability decisions, ability scores, or final risk scores.

## Current Recommended Components

### CH6.7 completion feasibility review v1.1

Scripts:

- `D:\mountain_work\115_osm\scripts\make_ch6_7_completion_feasibility_review_v1.py`
- `D:\mountain_work\115_osm\scripts\make_ch6_7_completion_feasibility_review_v1_1.py`

Current recommended output root:

`outputs\report_figures\ch6_7_completion_feasibility_review_v1_1`

Retained baseline output root:

`outputs\report_figures\ch6_7_completion_feasibility_review_v1`

Key v1.1 outputs:

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

Local output inventory:

- v1: 7 CSV, 1 HTML, 1 MD, 3 PNG
- v1.1: 10 CSV, 1 HTML, 1 MD, 3 PNG

Current interpretation:

- v1 is retained as an earlier descriptive completion-feasibility layer.
- v1.1 is current recommended because it adds HR-effort context and expanded completion interpretation for planning discussion.

### CH6.7 HR lifecycle recovery profile v2

Scripts:

- `D:\mountain_work\115_osm\scripts\make_ch6_7_hr_lifecycle_recovery_profile_v2.py`
- `D:\mountain_work\115_osm\scripts\make_ch6_7_hr_lifecycle_recovery_profile_v2_before_plotfix.py`

Current output root:

`outputs\report_figures\ch6_7_hr_lifecycle_recovery_profile_v2`

Key outputs:

- `activity_hr_lifecycle_audit_v2.csv`
- `activity_hr_lifecycle_report_v2.html`
- `activity_hr_lifecycle_run_report_v2.md`
- `activity_hr_lifecycle_summary_v2.csv`
- `activity_hr_recovery_phase_summary_v2.csv`
- activity-level HR lifecycle profile PNGs
- route-window median HR profile PNGs

Local output inventory:

- 6 CSV
- 1 HTML
- 1 MD
- 10 PNG

Current interpretation:

The HR lifecycle layer describes heart-rate availability, early/middle/late HR behavior, high-load HR windows, HR drift, recovery phases, and profile-level review evidence. It is not a cardiopulmonary diagnosis and does not produce ability labels.

### CH6.7 planning context fusion v1.1

Scripts:

- `D:\mountain_work\115_osm\scripts\make_ch6_7_planning_context_fusion_v1.py`
- `D:\mountain_work\115_osm\scripts\make_ch6_7_planning_context_fusion_v1_1.py`
- `D:\mountain_work\115_osm\scripts\make_ch6_7_planning_context_fusion_report_v1_1.py`

Current recommended output roots:

- `outputs\report_figures\ch6_7_planning_context_fusion_v1_1`
- `outputs\report_figures\ch6_7_planning_context_fusion_report_v1_1`

Retained baseline output root:

`outputs\report_figures\ch6_7_planning_context_fusion_v1`

Key v1.1 outputs:

- `planning_context_activity_summary_v1_1.csv`
- `planning_context_fusion_audit_v1_1.csv`
- `planning_context_fusion_run_report_v1_1.md`
- `planning_context_route_windows_v1_1.csv`
- `planning_context_fusion_report_v1_1.html`
- `planning_context_fusion_report_v1_1.png`

Local output inventory:

- planning context fusion v1: 4 CSV, 1 MD
- planning context fusion v1.1: 4 CSV, 1 MD
- planning context fusion report v1.1: 1 HTML, 4 PNG

Current interpretation:

Planning context fusion v1.1 combines route-load context, behavior-response evidence, weather/background flags, and planning-caution labels into descriptive planning context. The report v1.1 is a presentation layer for this evidence.

## Method Role

This package provides the report-facing bridge from CH6.5 route-load / behavior evidence toward CH6.8 personal route-load readiness review.

It supports statements such as:

- completion is feasible for the reviewed population under observed historical cases;
- conservative planning remains recommended when slower completion, high HR effort, weather background, or early checkpoint burden appears;
- early checkpoint review can be described without turning it into a mandatory turnaround point;
- planning caution labels are descriptive context labels, not risk scores.

## Method Boundary

This package is descriptive planning evidence only.

It does not generate or authorize:

- cardiopulmonary diagnosis;
- personal ability score;
- personal ability rank;
- personal ability class;
- route suitability score;
- THCI score;
- radar score;
- final hiking risk score;
- automatic suitable/unsuitable decision;
- automatic go/no-go decision;
- causal claims from weather, route-load, OSM proximity, or behavior events.

Weather context remains descriptive background unless explicitly supported by a safe route-window source. Missing weather must not be filled as zero, normal, calm, or no-rain evidence.

OSM proximity remains route/environment context, not evidence of actual facility use.

## Recommended Version Decision

- Completion feasibility review v1.1 is current recommended.
- Completion feasibility review v1 is retained as an earlier baseline.
- HR lifecycle recovery profile v2 is current recommended for HR lifecycle display and review.
- Planning context fusion v1.1 is current recommended.
- Planning context fusion v1 is retained as baseline.
- Planning context fusion report v1.1 is current recommended report-facing presentation layer.

## Recommended Commit Scope

Include:

- `scripts\make_ch6_7_completion_feasibility_review_v1.py`
- `scripts\make_ch6_7_completion_feasibility_review_v1_1.py`
- `scripts\make_ch6_7_hr_lifecycle_recovery_profile_v2.py`
- `scripts\make_ch6_7_hr_lifecycle_recovery_profile_v2_before_plotfix.py`
- `scripts\make_ch6_7_planning_context_fusion_v1.py`
- `scripts\make_ch6_7_planning_context_fusion_v1_1.py`
- `scripts\make_ch6_7_planning_context_fusion_report_v1_1.py`
- the six output roots listed above
- this README / changelog / current index / handoff documentation set

Do not mix with CH6.5 route-load context index, CH6.5 behavior-profile v1.5/v1.5.1, CH6.8 readiness scripts, CH6 report figure scripts, older surface-profile prototypes, or `_handoff_6_2_method_files`.
