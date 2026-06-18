# CURRENT INDEX update — 20260618_ch6_5_5_activity_history_numeric_attribution

## Current effective entry points

### CH6.5.5 v0.4 activity-history-primary relabel

Script:

`scripts/make_ch6_5_5_activity_history_primary_relabel_v0_4.py`

Output root:

`outputs/report_figures/ch6_5_5_activity_history_primary_relabel_v0_4`

Primary output:

`personal_activity_history_primary_full_context_v0_4.csv`

Audit:

`personal_activity_history_primary_audit_v0_4.csv`

### CH6.5.5 v0.5 activity-history numeric attribution

Script:

`scripts/make_ch6_5_5_activity_history_numeric_attribution_v0_5.py`

Output root:

`outputs/report_figures/ch6_5_5_activity_history_numeric_attribution_v0_5`

Primary outputs:

- `personal_activity_history_numeric_attribution_v0_5.csv`
- `personal_activity_history_numeric_attribution_metric_long_v0_5.csv`
- `personal_activity_history_numeric_attribution_summary_v0_5.csv`
- `personal_activity_history_numeric_attribution_flag_summary_v0_5.csv`
- `personal_activity_history_numeric_attribution_thresholds_v0_5.csv`
- `personal_activity_history_numeric_attribution_audit_v0_5.csv`

## Current interpretation

Use v0.5 as the current explanation layer for CH6.5.5 candidate/review reasons.

Do not use estimated VO2max or subjective difficulty as primary evidence.

Do not interpret high HR alone as strain.

## Current candidate groups

| numeric_attribution_label_v0_5                   | suggested_report_case_role                 |   activity_count | activity_id_short_list   |
|:-------------------------------------------------|:-------------------------------------------|-----------------:|:-------------------------|
| MODERATE_NUMERIC_ATTRIBUTION_SUPPORTED           | REPORT_SECONDARY_CASE_CANDIDATE            |                3 | 23_1|38_1|9_1            |
| MULTI_FACTOR_NUMERIC_ATTRIBUTION_STRONG          | REPORT_PRIMARY_CASE_CANDIDATE              |                4 | 42_1|43_1|46_1|48_1      |
| SINGLE_FACTOR_BEHAVIOR_NUMERIC_TRIGGER_CONFIRMED | NUMERIC_DETAIL_REVIEW_NOT_PRIMARY_CASE_YET |                1 | 16_1                     |
| SINGLE_FACTOR_HR_PLUS_MOVEMENT_NUMERIC_REVIEW    | NUMERIC_DETAIL_REVIEW_NOT_PRIMARY_CASE_YET |                4 | 28_1|37_1|44_1|8_1       |

## Boundary

Descriptive CH6.5.5 personal activity-history evidence only. Actual hiking activity history is primary evidence; HR zone is secondary context; non-standard estimated VO2max and subjective Qixing difficulty are tertiary supporting context only and do not promote an activity into strain candidate by themselves. This is not an ability score, ability rank, ability class, final hiking risk score, route suitability score, go/no-go decision, medical diagnosis, or causality evidence.
