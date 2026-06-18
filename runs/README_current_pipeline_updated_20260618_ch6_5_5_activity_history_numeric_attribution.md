# README current pipeline update — CH6.5.5 activity-history numeric attribution

## Scope

This update documents the CH6.5.5 personal route-load / activity-history review layer.

The layer was built to support a personal activity performance radar and route-demand match workflow while preserving the core interpretation boundary:

> Descriptive CH6.5.5 personal activity-history evidence only. Actual hiking activity history is primary evidence; HR zone is secondary context; non-standard estimated VO2max and subjective Qixing difficulty are tertiary supporting context only and do not promote an activity into strain candidate by themselves. This is not an ability score, ability rank, ability class, final hiking risk score, route suitability score, go/no-go decision, medical diagnosis, or causality evidence.

## Evidence hierarchy

| Evidence tier | Role | Notes |
|---|---|---|
| Primary | Actual hiking activity history | speed, low-speed ratio, stopped ratio, route-load behavior response, behavior-weather overlap, uphill-load exposure context |
| Secondary | HR zone / HR output context | sex-age estimated HRmax; high HR is not strain by itself |
| Tertiary | estimated VO2max / subjective Qixing difficulty | non-standard and/or subjective context only; not used to promote candidates |

## v0.4 activity-history-primary relabel

Output root:

`outputs/report_figures/ch6_5_5_activity_history_primary_relabel_v0_4`

Audit summary:

| metric | value |
|---|---:|
| activity_count | 25 |
| primary_activity_history_candidate_rows | 7 |
| single_factor_behavior_review_rows | 5 |
| hr_context_rows | 15 |
| profile_context_only_rows | 5 |
| profile_promotion_used | False |

Audit conclusion:

`PASS_CH6_5_5_ACTIVITY_HISTORY_PRIMARY_RELABEL_V0_4_DESCRIPTIVE_ONLY`

## v0.5 numeric attribution

Output root:

`outputs/report_figures/ch6_5_5_activity_history_numeric_attribution_v0_5`

Audit summary:

| metric | value |
|---|---:|
| attribution_scope_rows | 12 |
| primary_candidate_rows_in_scope | 7 |
| single_factor_review_rows_in_scope | 5 |
| metric_attribution_long_rows | 72 |
| triggered_metric_rows | 38 |
| threshold_metric_rules_n | 6 |
| profile_promotion_used | False |

Audit conclusion:

`PASS_CH6_5_5_ACTIVITY_HISTORY_NUMERIC_ATTRIBUTION_V0_5_DESCRIPTIVE_ONLY`

## v0.5 attribution groups

| numeric_attribution_label_v0_5                   | suggested_report_case_role                 |   activity_count | activity_id_short_list   |
|:-------------------------------------------------|:-------------------------------------------|-----------------:|:-------------------------|
| MODERATE_NUMERIC_ATTRIBUTION_SUPPORTED           | REPORT_SECONDARY_CASE_CANDIDATE            |                3 | 23_1|38_1|9_1            |
| MULTI_FACTOR_NUMERIC_ATTRIBUTION_STRONG          | REPORT_PRIMARY_CASE_CANDIDATE              |                4 | 42_1|43_1|46_1|48_1      |
| SINGLE_FACTOR_BEHAVIOR_NUMERIC_TRIGGER_CONFIRMED | NUMERIC_DETAIL_REVIEW_NOT_PRIMARY_CASE_YET |                1 | 16_1                     |
| SINGLE_FACTOR_HR_PLUS_MOVEMENT_NUMERIC_REVIEW    | NUMERIC_DETAIL_REVIEW_NOT_PRIMARY_CASE_YET |                4 | 28_1|37_1|44_1|8_1       |

## Numeric trigger summary

| numeric_attention_flag                                | numeric_attention_domain    |   activity_count | activity_id_short_list             |
|:------------------------------------------------------|:----------------------------|-----------------:|:-----------------------------------|
| NUMERIC_HIGH_BEHAVIOR_WEATHER_OVERLAP_GE_P75          | weather_behavior_overlap    |                7 | 23_1|38_1|42_1|43_1|46_1|48_1|9_1  |
| NUMERIC_HIGH_LOW_SPEED_RATIO_GE_P75                   | movement_degradation        |                7 | 28_1|42_1|43_1|46_1|48_1|8_1|9_1   |
| NUMERIC_HIGH_ROUTE_LOAD_BEHAVIOR_RESPONSE_GE_P75      | route_load_behavior         |                7 | 23_1|38_1|42_1|43_1|46_1|48_1|9_1  |
| NUMERIC_HIGH_STOPPED_RATIO_GE_P75                     | movement_degradation        |                7 | 16_1|37_1|42_1|43_1|44_1|46_1|48_1 |
| NUMERIC_HIGH_UPHILL_LOAD_EXPOSURE_GE_P75_CONTEXT_ONLY | route_load_exposure_context |                3 | 23_1|38_1|46_1                     |
| NUMERIC_SLOWER_SPEED_LE_P25                           | movement_degradation        |                7 | 23_1|38_1|42_1|43_1|46_1|48_1|9_1  |

## Report case candidates

### Primary case candidates

|   activity_id_short |   participant_id | numeric_attribution_label_v0_5          |   numeric_attention_flag_count |   movement_degradation_flag_count | numeric_attention_flags                                                                                                                                                                                                                               | hr_median_zone_sex_age_est   | tertiary_profile_context_signal                                      |
|--------------------:|-----------------:|:----------------------------------------|-------------------------------:|----------------------------------:|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:-----------------------------|:---------------------------------------------------------------------|
|                46_1 |               46 | MULTI_FACTOR_NUMERIC_ATTRIBUTION_STRONG |                              6 |                                 3 | NUMERIC_HIGH_BEHAVIOR_WEATHER_OVERLAP_GE_P75|NUMERIC_HIGH_LOW_SPEED_RATIO_GE_P75|NUMERIC_HIGH_ROUTE_LOAD_BEHAVIOR_RESPONSE_GE_P75|NUMERIC_HIGH_STOPPED_RATIO_GE_P75|NUMERIC_HIGH_UPHILL_LOAD_EXPOSURE_GE_P75_CONTEXT_ONLY|NUMERIC_SLOWER_SPEED_LE_P25 | ZONE3_70_80_PCT_HRMAX        | LOWER_ESTIMATED_VO2MAX_CONTEXT                                       |
|                42_1 |               42 | MULTI_FACTOR_NUMERIC_ATTRIBUTION_STRONG |                              5 |                                 3 | NUMERIC_HIGH_BEHAVIOR_WEATHER_OVERLAP_GE_P75|NUMERIC_HIGH_LOW_SPEED_RATIO_GE_P75|NUMERIC_HIGH_ROUTE_LOAD_BEHAVIOR_RESPONSE_GE_P75|NUMERIC_HIGH_STOPPED_RATIO_GE_P75|NUMERIC_SLOWER_SPEED_LE_P25                                                       | ZONE4_80_90_PCT_HRMAX        | LOWER_ESTIMATED_VO2MAX_CONTEXT                                       |
|                43_1 |               43 | MULTI_FACTOR_NUMERIC_ATTRIBUTION_STRONG |                              5 |                                 3 | NUMERIC_HIGH_BEHAVIOR_WEATHER_OVERLAP_GE_P75|NUMERIC_HIGH_LOW_SPEED_RATIO_GE_P75|NUMERIC_HIGH_ROUTE_LOAD_BEHAVIOR_RESPONSE_GE_P75|NUMERIC_HIGH_STOPPED_RATIO_GE_P75|NUMERIC_SLOWER_SPEED_LE_P25                                                       | ZONE3_70_80_PCT_HRMAX        | LOWER_ESTIMATED_VO2MAX_CONTEXT|SELF_REPORTED_HIGH_DIFFICULTY_CONTEXT |
|                48_1 |               48 | MULTI_FACTOR_NUMERIC_ATTRIBUTION_STRONG |                              5 |                                 3 | NUMERIC_HIGH_BEHAVIOR_WEATHER_OVERLAP_GE_P75|NUMERIC_HIGH_LOW_SPEED_RATIO_GE_P75|NUMERIC_HIGH_ROUTE_LOAD_BEHAVIOR_RESPONSE_GE_P75|NUMERIC_HIGH_STOPPED_RATIO_GE_P75|NUMERIC_SLOWER_SPEED_LE_P25                                                       | ZONE2_60_70_PCT_HRMAX        | PROFILE_CONTEXT_REFERENCE_OR_MISSING                                 |

### Secondary case candidates

|   activity_id_short |   participant_id | numeric_attribution_label_v0_5         |   numeric_attention_flag_count |   movement_degradation_flag_count | numeric_attention_flags                                                                                                                                                         | hr_median_zone_sex_age_est   | tertiary_profile_context_signal                                       |
|--------------------:|-----------------:|:---------------------------------------|-------------------------------:|----------------------------------:|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:-----------------------------|:----------------------------------------------------------------------|
|                 9_1 |                9 | MODERATE_NUMERIC_ATTRIBUTION_SUPPORTED |                              4 |                                 2 | NUMERIC_HIGH_BEHAVIOR_WEATHER_OVERLAP_GE_P75|NUMERIC_HIGH_LOW_SPEED_RATIO_GE_P75|NUMERIC_HIGH_ROUTE_LOAD_BEHAVIOR_RESPONSE_GE_P75|NUMERIC_SLOWER_SPEED_LE_P25                   | ZONE3_70_80_PCT_HRMAX        | HIGHER_ESTIMATED_VO2MAX_CONTEXT|SELF_REPORTED_HIGH_DIFFICULTY_CONTEXT |
|                23_1 |               23 | MODERATE_NUMERIC_ATTRIBUTION_SUPPORTED |                              4 |                                 1 | NUMERIC_HIGH_BEHAVIOR_WEATHER_OVERLAP_GE_P75|NUMERIC_HIGH_ROUTE_LOAD_BEHAVIOR_RESPONSE_GE_P75|NUMERIC_HIGH_UPHILL_LOAD_EXPOSURE_GE_P75_CONTEXT_ONLY|NUMERIC_SLOWER_SPEED_LE_P25 | ZONE3_70_80_PCT_HRMAX        | HIGHER_ESTIMATED_VO2MAX_CONTEXT                                       |
|                38_1 |               38 | MODERATE_NUMERIC_ATTRIBUTION_SUPPORTED |                              4 |                                 1 | NUMERIC_HIGH_BEHAVIOR_WEATHER_OVERLAP_GE_P75|NUMERIC_HIGH_ROUTE_LOAD_BEHAVIOR_RESPONSE_GE_P75|NUMERIC_HIGH_UPHILL_LOAD_EXPOSURE_GE_P75_CONTEXT_ONLY|NUMERIC_SLOWER_SPEED_LE_P25 | ZONE2_60_70_PCT_HRMAX        | LOWER_ESTIMATED_VO2MAX_CONTEXT                                        |

### Numeric-detail review, not primary cases yet

|   activity_id_short |   participant_id | numeric_attribution_label_v0_5                   |   numeric_attention_flag_count |   movement_degradation_flag_count | numeric_attention_flags             | hr_median_zone_sex_age_est   | tertiary_profile_context_signal                                      |
|--------------------:|-----------------:|:-------------------------------------------------|-------------------------------:|----------------------------------:|:------------------------------------|:-----------------------------|:---------------------------------------------------------------------|
|                16_1 |               16 | SINGLE_FACTOR_BEHAVIOR_NUMERIC_TRIGGER_CONFIRMED |                              1 |                                 1 | NUMERIC_HIGH_STOPPED_RATIO_GE_P75   | ZONE3_70_80_PCT_HRMAX        | PROFILE_CONTEXT_REFERENCE_OR_MISSING                                 |
|                28_1 |               28 | SINGLE_FACTOR_HR_PLUS_MOVEMENT_NUMERIC_REVIEW    |                              1 |                                 1 | NUMERIC_HIGH_LOW_SPEED_RATIO_GE_P75 | ZONE4_80_90_PCT_HRMAX        | SELF_REPORTED_LOW_DIFFICULTY_CONTEXT                                 |
|                37_1 |               37 | SINGLE_FACTOR_HR_PLUS_MOVEMENT_NUMERIC_REVIEW    |                              1 |                                 1 | NUMERIC_HIGH_STOPPED_RATIO_GE_P75   | ZONE4_80_90_PCT_HRMAX        | LOWER_ESTIMATED_VO2MAX_CONTEXT|SELF_REPORTED_LOW_DIFFICULTY_CONTEXT  |
|                44_1 |               44 | SINGLE_FACTOR_HR_PLUS_MOVEMENT_NUMERIC_REVIEW    |                              1 |                                 1 | NUMERIC_HIGH_STOPPED_RATIO_GE_P75   | ZONE4_80_90_PCT_HRMAX        | HIGHER_ESTIMATED_VO2MAX_CONTEXT|SELF_REPORTED_LOW_DIFFICULTY_CONTEXT |
|                 8_1 |                8 | SINGLE_FACTOR_HR_PLUS_MOVEMENT_NUMERIC_REVIEW    |                              1 |                                 1 | NUMERIC_HIGH_LOW_SPEED_RATIO_GE_P75 | ZONE4_80_90_PCT_HRMAX        | PROFILE_CONTEXT_REFERENCE_OR_MISSING                                 |

## Output files

### v0.4

- `personal_activity_history_primary_full_context_v0_4.csv`
- `personal_activity_history_primary_strain_candidate_v0_4.csv`
- `personal_activity_history_single_factor_behavior_review_v0_4.csv`
- `personal_activity_history_hr_output_context_v0_4.csv`
- `personal_profile_context_only_v0_4.csv`
- `personal_activity_history_primary_summary_v0_4.csv`
- `personal_activity_history_profile_context_summary_v0_4.csv`
- `personal_activity_history_primary_audit_v0_4.csv`

### v0.5

- `personal_activity_history_numeric_attribution_v0_5.csv`
- `personal_activity_history_numeric_attribution_metric_long_v0_5.csv`
- `personal_activity_history_numeric_attribution_summary_v0_5.csv`
- `personal_activity_history_numeric_attribution_flag_summary_v0_5.csv`
- `personal_activity_history_numeric_attribution_thresholds_v0_5.csv`
- `personal_activity_history_numeric_attribution_audit_v0_5.csv`

## Next recommended work

1. Add 300s rolling movement output:
   - vertical_gain_300s_m
   - horizontal_dist_300s_m
   - VAM_300s
   - late-vs-early 300s degradation
2. Build personal activity performance radar v0 from available evidence only.
3. Keep missing axes as `INSUFFICIENT_EVIDENCE`; do not zero-fill.
