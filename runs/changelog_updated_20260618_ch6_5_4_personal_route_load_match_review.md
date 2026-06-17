# Changelog update — 2026-06-18 — CH6.5.4 personal route-load match review v1

Added CH6.5.4 personal route-load match review v1.

New script:
- scripts/make_ch6_5_4_personal_route_load_match_review_v1.py

New output root:
- outputs/report_figures/ch6_5_4_personal_route_load_match_review_v1

Purpose:
- consume CH6.5.3 v1.1 context-complete route-load / behavior / weather / readiness evidence
- compare each activity against current activity-group reference ranges
- generate relative within-group route-load match-review levels
- keep suitability / go-no-go wording out of the evidence layer

Latest run:
- activity_count: 25
- match_rows: 25
- match_review_level_count: 4
- group_summary_rows: 4
- dimension_summary_rows: 14
- reference_threshold_rows: 7
- context_ready_for_comparison_n: 25
- source_files_available_n: 4
- source_files_expected_n: 4
- audit_conclusion: PASS_CH6_5_4_PERSONAL_ROUTE_LOAD_MATCH_REVIEW_V1_DESCRIPTIVE_ONLY

Match review level distribution:
- PERSONAL_ROUTE_LOAD_MATCH_REFERENCE_RANGE: 6
- PERSONAL_ROUTE_LOAD_MATCH_SINGLE_FACTOR_ATTENTION: 12
- PERSONAL_ROUTE_LOAD_MATCH_MODERATE_ATTENTION: 3
- PERSONAL_ROUTE_LOAD_MATCH_MULTI_FACTOR_ATTENTION: 4

Boundary:
Descriptive evidence only. No ability score, ability rank, ability class, THCI score, radar score, final hiking risk score, route suitability score, go/no-go decision, medical diagnosis, or causality inference is generated.
