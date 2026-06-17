# Latest Handoff Prompt — CH6.7 Planning, Completion, and HR Context Evidence

Continue from:

- repo: `D:\mountain_work\115_osm`
- branch: verify with `git branch --show-current`
- package: CH6.7 planning / completion / HR context evidence

## Completed in This Handoff

### 1. Completion feasibility review v1 / v1.1

Scripts:

- `scripts\make_ch6_7_completion_feasibility_review_v1.py`
- `scripts\make_ch6_7_completion_feasibility_review_v1_1.py`

Output roots:

- `outputs\report_figures\ch6_7_completion_feasibility_review_v1`
- `outputs\report_figures\ch6_7_completion_feasibility_review_v1_1`

Local output inventory:

- v1: 7 CSV, 1 HTML, 1 MD, 3 PNG
- v1.1: 10 CSV, 1 HTML, 1 MD, 3 PNG

Important v1.1 outputs:

- `activity_completion_weather_context_v1_1.csv`
- `completion_feasibility_conclusion_v1_1.csv`
- `completion_feasibility_group_summary_v1_1.csv`
- `completion_feasibility_review_audit_v1_1.csv`
- `completion_feasibility_review_report_v1_1.html`
- `completion_feasibility_review_run_report_v1_1.md`
- `completion_hr_effort_context_v1_1.csv`
- `completion_hr_effort_group_summary_v1_1.csv`
- `completion_time_distribution_v1_1.csv`
- `completion_weather_group_summary_v1_1.csv`

Version note:

- v1.1 is current recommended.
- v1 is retained as baseline.

### 2. HR lifecycle recovery profile v2

Scripts:

- `scripts\make_ch6_7_hr_lifecycle_recovery_profile_v2.py`
- `scripts\make_ch6_7_hr_lifecycle_recovery_profile_v2_before_plotfix.py`

Output root:

`outputs\report_figures\ch6_7_hr_lifecycle_recovery_profile_v2`

Local output inventory:

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

Version note:

- v2 is current recommended for HR lifecycle context.
- `before_plotfix` is retained as traceability.

### 3. Planning context fusion v1 / v1.1 and report v1.1

Scripts:

- `scripts\make_ch6_7_planning_context_fusion_v1.py`
- `scripts\make_ch6_7_planning_context_fusion_v1_1.py`
- `scripts\make_ch6_7_planning_context_fusion_report_v1_1.py`

Output roots:

- `outputs\report_figures\ch6_7_planning_context_fusion_v1`
- `outputs\report_figures\ch6_7_planning_context_fusion_v1_1`
- `outputs\report_figures\ch6_7_planning_context_fusion_report_v1_1`

Local output inventory:

- planning fusion v1: 4 CSV, 1 MD
- planning fusion v1.1: 4 CSV, 1 MD
- planning fusion report v1.1: 1 HTML, 4 PNG

Important outputs:

- `planning_context_route_windows_v1_1.csv`
- `planning_context_activity_summary_v1_1.csv`
- `planning_context_fusion_audit_v1_1.csv`
- `planning_context_fusion_run_report_v1_1.md`
- `planning_context_fusion_report_v1_1.html`
- `planning_context_fusion_report_v1_1.png`

Version note:

- v1.1 is current recommended planning context fusion output.
- v1 is retained as baseline.
- report v1.1 is current presentation layer.

## Interpretation

This CH6.7 package supports report-level statements about:

- completion feasibility under observed historical cases;
- conservative planning and HR effort context;
- early checkpoint status review;
- planning caution windows and segments;
- weather/HR/context background for planning discussion.

It feeds CH6.8 personal route-load readiness review as descriptive evidence.

## Do Not Change

Do not overwrite or modify these outputs unless intentionally creating a new version:

- `outputs\report_figures\ch6_7_completion_feasibility_review_v1_1`
- `outputs\report_figures\ch6_7_hr_lifecycle_recovery_profile_v2`
- `outputs\report_figures\ch6_7_planning_context_fusion_v1_1`
- `outputs\report_figures\ch6_7_planning_context_fusion_report_v1_1`

Do not modify Word/docx files in this handoff.

Do not rerun large upstream pipeline stages unless a future change explicitly requires it.

## Boundary

Do not generate or infer:

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
- weather causality;
- actual facility use from OSM proximity.

## Suggested Local Verification

```powershell
Set-Location D:\mountain_work\115_osm

$outputRoots = @(
  "outputs\report_figures\ch6_7_completion_feasibility_review_v1",
  "outputs\report_figures\ch6_7_completion_feasibility_review_v1_1",
  "outputs\report_figures\ch6_7_hr_lifecycle_recovery_profile_v2",
  "outputs\report_figures\ch6_7_planning_context_fusion_v1",
  "outputs\report_figures\ch6_7_planning_context_fusion_v1_1",
  "outputs\report_figures\ch6_7_planning_context_fusion_report_v1_1"
)

foreach ($root in $outputRoots) {
  if (Test-Path $root) {
    "=== $root ==="
    Get-ChildItem $root -Recurse -File |
      Group-Object Extension |
      Select-Object Name, Count |
      Format-Table -AutoSize
  }
}
```

Expected inventory:

- completion feasibility v1: 7 CSV, 1 HTML, 1 MD, 3 PNG
- completion feasibility v1.1: 10 CSV, 1 HTML, 1 MD, 3 PNG
- HR lifecycle v2: 6 CSV, 1 HTML, 1 MD, 10 PNG
- planning fusion v1: 4 CSV, 1 MD
- planning fusion v1.1: 4 CSV, 1 MD
- planning fusion report v1.1: 1 HTML, 4 PNG

## Suggested Commit Scope

Include:

- `scripts\make_ch6_7_completion_feasibility_review_v1.py`
- `scripts\make_ch6_7_completion_feasibility_review_v1_1.py`
- `scripts\make_ch6_7_hr_lifecycle_recovery_profile_v2.py`
- `scripts\make_ch6_7_hr_lifecycle_recovery_profile_v2_before_plotfix.py`
- `scripts\make_ch6_7_planning_context_fusion_v1.py`
- `scripts\make_ch6_7_planning_context_fusion_v1_1.py`
- `scripts\make_ch6_7_planning_context_fusion_report_v1_1.py`
- all six CH6.7 output roots listed above
- current README / changelog / handoff / CURRENT_INDEX documentation for this package

Do not include:

- CH6.5 route-load context index;
- CH6.5 route-surface behavior profile v1.5/v1.5.1;
- CH6.8 readiness scripts;
- CH6 report figure scripts;
- older single-activity profile prototypes;
- `_handoff_6_2_method_files`.

## Suggested Commit Message

`Add CH6.7 planning completion and HR context evidence`
