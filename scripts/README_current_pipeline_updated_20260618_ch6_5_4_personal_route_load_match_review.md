# README current pipeline update — CH6.5.4 personal route-load match review v1

Script:
- scripts/make_ch6_5_4_personal_route_load_match_review_v1.py

Output root:
- outputs/report_figures/ch6_5_4_personal_route_load_match_review_v1

Role:
CH6.5.4 consumes CH6.5.3 v1.1 context-complete evidence and turns it into a per-activity personal route-load match review.

Current interpretation:
- compares each activity against the current activity-group reference ranges
- dimensions include route-load exposure, movement behavior, heart-rate context, and weather-behavior overlap
- flags indicate relative within-group match-review context only

Latest audit:
- PASS_CH6_5_4_PERSONAL_ROUTE_LOAD_MATCH_REVIEW_V1_DESCRIPTIVE_ONLY

Latest summary:
- activity_count: 25
- match_rows: 25
- match_review_level_count: 4
- group_summary_rows: 4
- dimension_summary_rows: 14
- reference_threshold_rows: 7
- context_ready_for_comparison_n: 25
- source_files_available_n: 4
- source_files_expected_n: 4

Match review level distribution:
- PERSONAL_ROUTE_LOAD_MATCH_REFERENCE_RANGE: 6
- PERSONAL_ROUTE_LOAD_MATCH_SINGLE_FACTOR_ATTENTION: 12
- PERSONAL_ROUTE_LOAD_MATCH_MODERATE_ATTENTION: 3
- PERSONAL_ROUTE_LOAD_MATCH_MULTI_FACTOR_ATTENTION: 4

Reference metrics:
- speed_mps_median_median
- low_speed_ratio_avg
- stopped_ratio_avg
- heart_rate_bpm_median_avg
- uphill_high_route_load_ratio
- route_load_behavior_candidate_window_ratio
- behavior_weather_context_review_required_ratio

Important interpretation:
Route-load, slower movement, higher heart-rate demand, pauses, and recovery needs can be normal hiking responses on a loaded uphill route. CH6.5.4 only marks relative within-group match-review context; it does not call normal load response abnormal.

Boundary:
This is descriptive evidence only. It is not ability scoring, ranking, classing, THCI, radar, final hiking risk, route suitability score, go/no-go decision, medical diagnosis, or causality evidence.
