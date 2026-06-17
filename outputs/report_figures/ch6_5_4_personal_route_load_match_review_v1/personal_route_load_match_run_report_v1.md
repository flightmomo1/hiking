# CH6.5.4 Personal Route-Load Match Review v1

- profile_id: `qixing_lengshuikeng_activity_group_full25`
- route_folder: `qixing_lengshuikeng`
- activity_count: `25`
- match_rows: `25`
- match_level_count: `4`
- group_summary_rows: `4`
- dimension_summary_rows: `14`
- reference_threshold_rows: `7`
- audit_conclusion: `PASS_CH6_5_4_PERSONAL_ROUTE_LOAD_MATCH_REVIEW_V1_DESCRIPTIVE_ONLY`

## Method

- Uses CH6.5.3 v1.1 context gate as upstream context.
- Compares each activity to the current activity-group reference ranges.
- Flags indicate relative match-review context only; they are not scores or suitability decisions.

## Sources

- ch6_5_3_v1_1_context_gate: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_3_route_load_personal_performance_readiness_gate_v1_1\route_load_personal_performance_context_gate_v1_1.csv` exists=True bytes=62298
- ch6_5_3_v1_1_activity_attention: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_3_route_load_personal_performance_readiness_gate_v1_1\route_load_personal_performance_activity_attention_review_v1_1.csv` exists=True bytes=93625
- ch6_5_3_v1_1_audit: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_3_route_load_personal_performance_readiness_gate_v1_1\route_load_personal_performance_context_gate_audit_v1_1.csv` exists=True bytes=1136
- ch6_5_3_v1_1_data_quality: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_3_route_load_personal_performance_readiness_gate_v1_1\route_load_personal_performance_context_gate_data_quality_v1_1.csv` exists=True bytes=1127

## Match review distribution

- PERSONAL_ROUTE_LOAD_MATCH_MODERATE_ATTENTION: activities=3; windows=245
- PERSONAL_ROUTE_LOAD_MATCH_MULTI_FACTOR_ATTENTION: activities=4; windows=336
- PERSONAL_ROUTE_LOAD_MATCH_REFERENCE_RANGE: activities=6; windows=497
- PERSONAL_ROUTE_LOAD_MATCH_SINGLE_FACTOR_ATTENTION: activities=12; windows=976

## Data quality

- source_files_available: PASS (4/4)
- match_rows_present: PASS (per-activity personal route-load match review rows generated)
- context_ready_for_comparison: PASS (ready_n=25;total=25)
- match_review_level_differentiation: PASS (PERSONAL_ROUTE_LOAD_MATCH_MODERATE_ATTENTION|PERSONAL_ROUTE_LOAD_MATCH_MULTI_FACTOR_ATTENTION|PERSONAL_ROUTE_LOAD_MATCH_REFERENCE_RANGE|PERSONAL_ROUTE_LOAD_MATCH_SINGLE_FACTOR_ATTENTION)
- reference_thresholds_generated: PASS (expected=7)
- forbidden_columns_absent: PASS (NONE)
- interpretation_boundary_present: PASS (interpretation_boundary generated in outputs)

## Normal-response note

Route-load, slower movement, higher heart-rate demand, pauses, and recovery needs can be normal hiking responses on a loaded uphill route. CH6.5.4 only marks relative within-group match-review context; it does not call normal load response abnormal.

## Boundary

Descriptive CH6.5.4 personal route-load match review only. This layer compares each activity against the current activity-group reference ranges for route-load exposure, movement behavior, heart-rate context, and weather-behavior overlap. It is not an ability score, ability rank, ability class, THCI, radar, final hiking risk score, route suitability score, go/no-go decision, medical diagnosis, or causality evidence.
