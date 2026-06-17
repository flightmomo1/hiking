# README current pipeline update — CH6.5.2 weather-adjusted behavior context v1

Script:
- scripts/make_ch6_5_2_weather_adjusted_behavior_context_v1.py

Output root:
- outputs/report_figures/ch6_5_2_weather_adjusted_behavior_context_v1

Audit:
- PASS_CH6_5_2_WEATHER_ADJUSTED_BEHAVIOR_CONTEXT_V1_DESCRIPTIVE_ONLY

Latest summary:
- activity_count: 25
- window_row_count: 2054
- weather_context_available_ratio: 1.0
- conservative_weather_review_required_windows_n: 2054
- behavior_weather_context_review_required_windows_n: 958
- route_load_phase_summary_rows: 21
- activity_summary_rows: 25
- conservative_planning_rows: 25
- source_files_available_n: 2
- source_files_expected_n: 2

Weather sanity:
- temperature_c min/avg/max: 22 / 24.417 / 25.9
- relative_humidity_pct min/avg/max: 88 / 90.781 / 100
- precipitation_mm min/avg/max: 0 / 1.796 / 44.5
- wind_speed_ms min/avg/max: 1.4 / 2.425 / 4.8
- wind_gust_ms min/avg/max: 5.8 / 7.875 / 14.7
- uv_index min/avg/max: 1 / 7.838 / 11

Interpretation:
All windows triggered conservative weather review mainly because the attached weather context is consistently humid, with additional UV, rain, and wind exposure contexts.

Boundary:
This is descriptive evidence only. It is not ability scoring, ranking, classing, THCI, radar, final hiking risk, route suitability score, go/no-go decision, medical diagnosis, or causality evidence. Missing weather is not zero-filled.
