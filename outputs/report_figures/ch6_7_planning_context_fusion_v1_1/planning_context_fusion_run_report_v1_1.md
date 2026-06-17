# CH6.7 Planning Context Fusion v1.1 Rule-Calibrated Run Report

## Inputs

- route_load_windows: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_route_load_context_index_v1\route_load_context_windows_v1.csv`
- route_load_candidates: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_route_load_context_index_v1\route_load_behavior_response_candidate_windows_v1.csv`
- route_load_activity_summary: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_route_load_context_index_v1\route_load_context_activity_summary_v1.csv`
- ib2_route_risk: `D:\mountain_work\115_osm\outputs\ib2_v2_route_risk_v1_3b_contract_qa\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b_route_risk_v2.csv`
- weather_profile: `D:\mountain_work\115_osm\outputs\ib3w_codis_weather_profile_report_v1\activity_weather_profile_report_table.csv`
- weather_performance_join: `D:\mountain_work\115_osm\outputs\ib3w_activity_weather_performance_join_v1\activity_weather_performance_join.csv`
- event_overlay_glob: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1\activity_*_ib3d_event_route_window_overlay.csv`
- v1_route_windows: `D:\mountain_work\115_osm\outputs\report_figures\ch6_7_planning_context_fusion_v1\planning_context_route_windows_v1.csv`

## Output Summary

- route_window_row_count: `2054`
- activity_summary_row_count: `25`
- caution_segment_row_count: `979`
- candidate_join_count: `958`
- input_candidate_row_count: `958`
- ib2_route_risk_aggregation_rows: `84`
- ib2_join_coverage: `1.0`
- weather_attach_coverage: `1.0`
- event_annotation_join_coverage: `0.274586`
- routine_planning_context_count: `494`
- lower_or_moderate_escalated_by_weather_only_count: `0`
- event_only_escalation_count: `0`
- weather_metadata_only_escalation_count: `0`
- slope_fallback_only_escalation_count: `0`
- planning_caution_level_distribution: `CONSERVATIVE_PLANNING_RECOMMENDED:498 | REVIEW_FOR_CONSERVATIVE_PLANNING:414 | ROUTINE_PLANNING_CONTEXT:494 | TURNAROUND_CONDITION_REVIEW_RECOMMENDED:648`
- v1_planning_caution_level_distribution: `CONSERVATIVE_PLANNING_RECOMMENDED:498 | REVIEW_FOR_CONSERVATIVE_PLANNING:908 | TURNAROUND_CONDITION_REVIEW_RECOMMENDED:648`
- missing_weather_count: `0`
- terminal_artifact_review_only_count: `16`
- weather_zero_fill_performed: `False`
- forbidden_output_columns_absent: `True`
- forbidden_output_columns: `NONE`
- route_phase_unknown_ascent_descent_comparison_performed: `False`
- audit_conclusion: `PASS_CH6_7_PLANNING_CONTEXT_FUSION_V1_1_RULE_CALIBRATED_DESCRIPTIVE_ONLY`

## Planning Caution Level Distribution

- CONSERVATIVE_PLANNING_RECOMMENDED: 498
- REVIEW_FOR_CONSERVATIVE_PLANNING: 414
- ROUTINE_PLANNING_CONTEXT: 494
- TURNAROUND_CONDITION_REVIEW_RECOMMENDED: 648

## Boundaries

- descriptive planning context evidence only
- v1.1 calibrates planning caution rules so weather metadata, event annotations, and slope fallback QA do not escalate caution levels by themselves
- IB2_WEATHER_SENSITIVE_ROUTE_EXPOSURE_CONTEXT is retained as route context evidence but is not a standalone escalation trigger in v1.1
- not ability scoring
- not route suitability scoring
- not final hiking risk assessment
- not THCI / radar score
- route-load context index remains route/terrain/map-derived
- behavior response is evidence only and does not compute route-load index
- weather is activity-level context unless explicitly window-level and safely joined
- no weather zero-fill
- IB3D/event evidence is annotation only and must not be interpreted as causality
- OSM proximity must not be interpreted as actual facility use
- terminal artifact is review-only and not used for planning caution level
- route_phase UNKNOWN is not used for ascent/descent ability comparison
