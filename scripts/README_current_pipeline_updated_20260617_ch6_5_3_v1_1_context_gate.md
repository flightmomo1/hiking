# README current pipeline update — CH6.5.3 v1.1 route-load personal-performance context gate

Script:
- scripts/make_ch6_5_3_route_load_personal_performance_context_gate_v1_1.py

Output root:
- outputs/report_figures/ch6_5_3_route_load_personal_performance_readiness_gate_v1_1

Role:
CH6.5.3 v1.1 is a semantic relabel patch over CH6.5.3 v1. It changes the primary interpretation from review-required wording to neutral context-completeness wording.

Current interpretation:
- context gate: confirms whether route-load, behavior, weather, and readiness context are complete enough for comparison
- attention layer: separately marks relative within-group attention-review flags

Latest audit:
- PASS_CH6_5_3_ROUTE_LOAD_PERSONAL_PERFORMANCE_CONTEXT_GATE_V1_1_DESCRIPTIVE_ONLY

Latest summary:
- activity_count: 25
- context_gate_rows: 25
- context_summary_rows: 1
- attention_summary_rows: 4
- context_complete_activities_n: 25
- source_files_available_n: 5
- source_files_expected_n: 5

Context gate:
- READINESS_CONTEXT_COMPLETE_ROUTE_LOAD_BEHAVIOR_WEATHER_READY_FOR_COMPARISON: 25 activities

Relative attention levels:
- CONTEXT_COMPLETE_NO_RELATIVE_ATTENTION_FLAG: 6
- SINGLE_FACTOR_RELATIVE_ATTENTION_REVIEW: 8
- MODERATE_RELATIVE_ATTENTION_REVIEW: 4
- MULTI_FACTOR_RELATIVE_ATTENTION_REVIEW: 7

Important interpretation:
Route-load, slower movement, higher heart-rate demand, pauses, and recovery needs can be normal hiking responses on a loaded uphill route. They should not be interpreted as warnings by themselves.

Boundary:
This is descriptive evidence only. It is not ability scoring, ranking, classing, THCI, radar, final hiking risk, route suitability score, go/no-go decision, medical diagnosis, or causality evidence.
