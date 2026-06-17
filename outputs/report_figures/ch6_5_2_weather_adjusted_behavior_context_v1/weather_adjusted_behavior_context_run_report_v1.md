# CH6.5.2 Weather-Adjusted Behavior Context v1

- profile_id: `qixing_lengshuikeng_activity_group_full25`
- route_folder: `qixing_lengshuikeng`
- activity_count: `25`
- windows_n: `2054`
- route_load_phase_summary_rows: `21`
- activity_summary_rows: `25`
- conservative_planning_rows: `25`
- audit_conclusion: `PASS_CH6_5_2_WEATHER_ADJUSTED_BEHAVIOR_CONTEXT_V1_DESCRIPTIVE_ONLY`

## Method

- Uses CH6.5.1 v1.1 route-window features as input.
- Adds weather-context review classes and conservative planning review flags.
- Weather-adjusted means contextual evidence only, not numeric ability adjustment.
- Missing weather is retained as a review class and is not zero-filled.

## Weather thresholds

- warm temperature review starts at `24.0` °C.
- heat review starts at `28.0` °C.
- humidity review starts at `80.0` % RH.
- very-humid review starts at `85.0` % RH.
- rain observed review uses precipitation > `0.0` mm.
- wind-gust review starts at `10.0` m/s.
- moderate UV review starts at `6.0`.
- high UV review starts at `8.0`.

These thresholds are transparent descriptive review heuristics for planning evidence, not safety standards or physiological diagnosis.

## Sources

- ch6_5_1_window_features: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_1_personal_activity_behavior_profile_v1_1\personal_behavior_profile_window_features_v1_1.csv` exists=True bytes=2877039
- ch6_5_1_audit: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_1_personal_activity_behavior_profile_v1_1\personal_activity_behavior_profile_audit_v1_1.csv` exists=True bytes=961

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
- no weather zero-fill

## Data Quality Checks

- source_files_available: PASS (2/2)
- window_rows_present: PASS (weather context windows generated)
- weather_context_available_ratio: PASS (weather fields are carried forward without zero-fill)
- weather_missing_not_imputed: PASS (missing weather remains a review class and is not imputed)
- weather_zero_fill_absent: PASS (script does not fill missing weather with 0, no-rain, safe, or normal values)
- forbidden_columns_absent: PASS (NONE)
- interpretation_boundary_present: PASS (interpretation_boundary field generated in profile outputs)
