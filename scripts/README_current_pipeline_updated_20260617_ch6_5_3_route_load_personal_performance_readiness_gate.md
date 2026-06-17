# README current pipeline update — CH6.5.3 route-load personal-performance readiness gate v1

Script:
- scripts/make_ch6_5_3_route_load_personal_performance_readiness_gate_v1.py

Output root:
- outputs/report_figures/ch6_5_3_route_load_personal_performance_readiness_gate_v1

Inputs:
- CH6.5.1 personal/activity behavior profile v1.1
- CH6.5.2 weather-adjusted behavior context v1
- CH6.8 personal route-load readiness review v1.1

Audit:
- PASS_CH6_5_3_ROUTE_LOAD_PERSONAL_PERFORMANCE_READINESS_GATE_V1_DESCRIPTIVE_ONLY

Latest summary:
- activity_count: 25
- gate_rows: 25
- activity_summary_rows: 25
- group_summary_rows: 1
- window_summary_rows: 21
- source_files_available_n: 4
- source_files_expected_n: 4

Sanity:
- CH6.5.1 windows: 2054
- CH6.5.2 weather windows: 2054
- CH6.5.1 / CH6.5.2 window count match: PASS
- CH6.8 readiness join: READINESS_JOINED_BY_ACTIVITY, 25 / 25
- gate status: READINESS_REVIEW_GATE_WEATHER_BEHAVIOR_AND_CH6_8_REVIEW_REQUIRED, 25 / 25

Interpretation:
All activities fall into the same descriptive readiness review gate because route-load behavior response, conservative weather context, and CH6.8 readiness review are all present. This is a review-gate flag, not an unsuitable-route decision.

Boundary:
This is descriptive evidence only. It is not ability scoring, ranking, classing, THCI, radar, final hiking risk, route suitability score, go/no-go decision, medical diagnosis, or causality evidence.
