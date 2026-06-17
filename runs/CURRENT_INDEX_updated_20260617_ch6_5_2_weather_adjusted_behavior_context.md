# CURRENT INDEX update — CH6.5.2 weather-adjusted behavior context v1

Current recommended evidence:
- script: scripts/make_ch6_5_2_weather_adjusted_behavior_context_v1.py
- output root: outputs/report_figures/ch6_5_2_weather_adjusted_behavior_context_v1

Key outputs:
- weather_adjusted_behavior_context_windows_v1.csv
- weather_adjusted_behavior_context_profile_summary_v1.csv
- weather_adjusted_behavior_context_route_load_phase_summary_v1.csv
- weather_adjusted_behavior_context_activity_summary_v1.csv
- weather_conservative_planning_review_flags_v1.csv
- weather_adjusted_behavior_context_data_quality_v1.csv
- weather_adjusted_behavior_context_audit_v1.csv
- weather_adjusted_behavior_context_run_report_v1.md

Audit result:
- PASS_CH6_5_2_WEATHER_ADJUSTED_BEHAVIOR_CONTEXT_V1_DESCRIPTIVE_ONLY

Interpretation:
Use as descriptive weather-context evidence for planning review. All 2054 windows triggered conservative weather review mainly because the attached weather context is consistently humid.

Boundary:
Not ability scoring, ranking, classing, THCI, radar, final hiking risk, route suitability score, go/no-go decision, medical diagnosis, or causality evidence. Missing weather is not zero-filled.
