# Changelog — CH6.7 Planning, Completion, and HR Context Evidence

## Added

- Added CH6.7 completion feasibility review v1 and v1.1 scripts and outputs.
- Added CH6.7 HR lifecycle recovery profile v2 script and outputs.
- Added CH6.7 planning context fusion v1 and v1.1 scripts and outputs.
- Added CH6.7 planning context fusion report v1.1 script and outputs.
- Added documentation for the CH6.7 planning/completion/HR context evidence package.

## Completion Feasibility Review

Scripts:

- `scripts\make_ch6_7_completion_feasibility_review_v1.py`
- `scripts\make_ch6_7_completion_feasibility_review_v1_1.py`

Output roots:

- `outputs\report_figures\ch6_7_completion_feasibility_review_v1`
- `outputs\report_figures\ch6_7_completion_feasibility_review_v1_1`

Local inventory:

- v1: 7 CSV, 1 HTML, 1 MD, 3 PNG
- v1.1: 10 CSV, 1 HTML, 1 MD, 3 PNG

Important v1.1 outputs:

- `completion_feasibility_conclusion_v1_1.csv`
- `completion_feasibility_group_summary_v1_1.csv`
- `completion_feasibility_review_audit_v1_1.csv`
- `completion_feasibility_review_report_v1_1.html`
- `completion_feasibility_review_run_report_v1_1.md`
- `completion_hr_effort_context_v1_1.csv`
- `completion_hr_effort_group_summary_v1_1.csv`

Decision:

- v1.1 is current recommended for completion feasibility and HR-effort-aware planning context.
- v1 remains retained as an earlier descriptive baseline.

## HR Lifecycle Recovery Profile v2

Scripts:

- `scripts\make_ch6_7_hr_lifecycle_recovery_profile_v2.py`
- `scripts\make_ch6_7_hr_lifecycle_recovery_profile_v2_before_plotfix.py`

Output root:

`outputs\report_figures\ch6_7_hr_lifecycle_recovery_profile_v2`

Local inventory:

- 6 CSV
- 1 HTML
- 1 MD
- 10 PNG

Important outputs:

- `activity_hr_lifecycle_audit_v2.csv`
- `activity_hr_lifecycle_summary_v2.csv`
- `activity_hr_lifecycle_report_v2.html`
- `activity_hr_lifecycle_run_report_v2.md`
- `activity_hr_recovery_phase_summary_v2.csv`

Decision:

- v2 is current recommended for HR lifecycle review and report-facing HR context.
- The `before_plotfix` script is retained as traceability for plot-fix iteration.

## Planning Context Fusion v1.1

Scripts:

- `scripts\make_ch6_7_planning_context_fusion_v1.py`
- `scripts\make_ch6_7_planning_context_fusion_v1_1.py`
- `scripts\make_ch6_7_planning_context_fusion_report_v1_1.py`

Output roots:

- `outputs\report_figures\ch6_7_planning_context_fusion_v1`
- `outputs\report_figures\ch6_7_planning_context_fusion_v1_1`
- `outputs\report_figures\ch6_7_planning_context_fusion_report_v1_1`

Local inventory:

- v1: 4 CSV, 1 MD
- v1.1: 4 CSV, 1 MD
- report v1.1: 1 HTML, 4 PNG

Important v1.1 outputs:

- `planning_context_route_windows_v1_1.csv`
- `planning_context_activity_summary_v1_1.csv`
- `planning_context_fusion_audit_v1_1.csv`
- `planning_context_fusion_run_report_v1_1.md`
- `planning_context_fusion_report_v1_1.html`
- `planning_context_fusion_report_v1_1.png`

Decision:

- v1.1 is current recommended planning context fusion output.
- v1 remains a baseline.
- report v1.1 is current recommended presentation layer.

## Boundary

This changelog records descriptive planning evidence additions only.

No cardiopulmonary diagnosis, ability scoring, ability ranking, ability class generation, route suitability scoring, THCI scoring, radar scoring, final hiking risk scoring, or automatic go/no-go decision was added.

Weather context is descriptive background. Missing weather is not zero-filled. OSM proximity is not interpreted as actual facility use. Planning caution levels are descriptive labels, not final risk or ability labels.
