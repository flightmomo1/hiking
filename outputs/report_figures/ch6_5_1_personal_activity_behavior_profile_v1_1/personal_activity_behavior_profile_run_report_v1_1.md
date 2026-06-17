# CH6.5.1 Personal Activity Behavior Profile v1.1

- profile_id: `qixing_lengshuikeng_activity_group_full25`
- route_folder: `qixing_lengshuikeng`
- activity_count: `25`
- route_load_phase_profile_rows: `11`
- phase_summary_rows: `4`
- activity_summary_rows: `25`
- band_summary_rows: `3`
- audit_conclusion: `PASS_CH6_5_1_PERSONAL_ACTIVITY_BEHAVIOR_PROFILE_V1_1_DESCRIPTIVE_ONLY`

## Route Phase Recovery

- `route_phase_original` is retained from input and may be UNKNOWN.
- `route_phase_for_profile` is recovered from `calibrated_slope_pct_median`.
- Uphill threshold: `>= +3%`.
- Downhill threshold: `<= -3%`.
- Missing signed slope remains `SLOPE_MISSING_REVIEW_REQUIRED` and is not imputed.
- The recovered phase is descriptive route context only and must not be interpreted as strict uphill/downhill ability or causality.

## Sources

- behavior_windows: `D:\mountain_work\115_osm\outputs\ib3_personal_hiking_features_route_load_comparison_full25_v1\activity_route_load_behavior_response_windows.csv` exists=True bytes=1177153
- route_load_context_activity_summary: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_route_load_context_index_v1\route_load_context_activity_summary_v1.csv` exists=True bytes=9330
- route_load_behavior_candidate_windows: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_route_load_context_index_v1\route_load_behavior_response_candidate_windows_v1.csv` exists=True bytes=1121985
- hr_recovery_activity_summary: `D:\mountain_work\115_osm\outputs\report_figures\ch6_7_hr_recovery_from_ib3c_events_v1_1\activity_hr_recovery_activity_summary_from_ib3c_v1_1.csv` exists=True bytes=14653
- completion_feasibility_conclusion: `D:\mountain_work\115_osm\outputs\report_figures\ch6_7_completion_feasibility_review_v1_1\completion_feasibility_conclusion_v1_1.csv` exists=True bytes=1401
- completion_hr_effort_context: `D:\mountain_work\115_osm\outputs\report_figures\ch6_7_completion_feasibility_review_v1_1\completion_hr_effort_context_v1_1.csv` exists=True bytes=5956
- personal_route_load_readiness_review: `D:\mountain_work\115_osm\outputs\report_figures\ch6_8_personal_route_load_readiness_review_v1_1\personal_route_load_readiness_review_v1_1.csv` exists=True bytes=66363

## Method

- Uses existing 50 m route-window activity behavior evidence.
- Aggregates historical speed, low-speed, stopped, and HR response by route-load context band and recovered route-context phase.
- HR recovery evidence is used only as descriptive recovery evidence, not as medical diagnosis.
- Weather context is descriptive only; missing weather is not zero-filled.

## Boundaries

- no ability score
- no ability rank
- no ability class
- no THCI score
- no radar score
- no final hiking risk score
- no route suitability score
- no go/no-go decision
- no medical diagnosis
- no causality inference

## Data Quality Checks

- activity_coverage_count: PASS (13_1|14_1|15_1|16_1|20_1|23_1|28_1|29_1|30_1|33_1|35_1|36_1|37_1|38_1|3_1|40_1|41_1|42_1|43_1|44_1|45_1|46_1|48_1|8_1|9_1)
- route_load_context_band_domain: PASS (NONE)
- route_phase_for_profile_domain: PASS (NONE)
- uphill_downhill_windows_present: PASS (uphill=360;downhill=498)
- slope_missing_ratio_review: PASS_WITH_SLOPE_MISSING_REVIEW (SLOPE_MISSING is retained as separate review phase and is not imputed.)
- weather_zero_fill_absent: PASS (script does not fill missing weather with zero/no-rain/safe values)
- source_files_available: PASS (7/7)
- forbidden_columns_absent: PASS (NONE)
- interpretation_boundary_present: PASS (interpretation_boundary field generated in profile outputs)
