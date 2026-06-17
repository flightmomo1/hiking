# Latest handoff prompt — CH6.5.4 personal route-load match review v1

Continue from:
- repository root: D:\mountain_work\115_osm
- branch: codex/ch6-5-4-personal-route-load-match-review-v1

Current CH6.5.4 layer:
- script: scripts/make_ch6_5_4_personal_route_load_match_review_v1.py
- output root: outputs/report_figures/ch6_5_4_personal_route_load_match_review_v1

Upstream:
- CH6.5.3 v1.1 context gate semantic relabel
- outputs/report_figures/ch6_5_3_route_load_personal_performance_readiness_gate_v1_1

Latest audit:
- PASS_CH6_5_4_PERSONAL_ROUTE_LOAD_MATCH_REVIEW_V1_DESCRIPTIVE_ONLY

Latest run summary:
- profile_id: qixing_lengshuikeng_activity_group_full25
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

Interpretation:
CH6.5.4 is a descriptive personal route-load match-review layer. It compares each activity to current activity-group reference ranges for speed, low-speed ratio, stopped ratio, HR context, uphill high-load exposure, route-load behavior response, and behavior-weather overlap.

Boundary:
This package is descriptive evidence only. It must not be interpreted as ability scoring, ranking, classing, THCI, radar, final hiking risk, route suitability score, go/no-go decision, medical diagnosis, or causality result.

Recommended next step:
Review whether CH6.5.4 v1 should remain activity-group-relative only or be extended into a true personal baseline layer when repeated activities per person are available.
