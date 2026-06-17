# CH6.5.3 v1.1 Route-Load Personal-Performance Context Gate

- profile_id: `qixing_lengshuikeng_activity_group_full25`
- route_folder: `qixing_lengshuikeng`
- context_gate_rows: `25`
- context_summary_rows: `1`
- attention_summary_rows: `4`
- audit_conclusion: `PASS_CH6_5_3_ROUTE_LOAD_PERSONAL_PERFORMANCE_CONTEXT_GATE_V1_1_DESCRIPTIVE_ONLY`

## Method

- Consumes CH6.5.3 v1 outputs.
- Relabels the primary gate from review-required wording to neutral context-completeness wording.
- Preserves previous v1 gate status and flags as traceability fields.
- Adds separate relative attention-review flags for within-group differentiation.

## Normal-response interpretation

Route-load, slower movement, higher heart-rate demand, pauses, and recovery needs can be normal hiking responses on a loaded uphill route. They should not be interpreted as warnings by themselves.

## Sources

- v1_gate: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_3_route_load_personal_performance_readiness_gate_v1\route_load_personal_performance_readiness_gate_v1.csv` exists=True bytes=51923
- v1_activity_summary: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_3_route_load_personal_performance_readiness_gate_v1\route_load_personal_performance_context_activity_summary_v1.csv` exists=True bytes=71515
- v1_group_summary: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_3_route_load_personal_performance_readiness_gate_v1\route_load_personal_performance_context_group_summary_v1.csv` exists=True bytes=1396
- v1_audit: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_3_route_load_personal_performance_readiness_gate_v1\route_load_personal_performance_readiness_gate_audit_v1.csv` exists=True bytes=912
- v1_data_quality: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_3_route_load_personal_performance_readiness_gate_v1\route_load_personal_performance_readiness_gate_data_quality_v1.csv` exists=True bytes=1308

## Context gate distribution

- READINESS_CONTEXT_COMPLETE_ROUTE_LOAD_BEHAVIOR_WEATHER_READY_FOR_COMPARISON: activities=25

## Attention layer distribution

- CONTEXT_COMPLETE_NO_RELATIVE_ATTENTION_FLAG: activities=6
- MODERATE_RELATIVE_ATTENTION_REVIEW: activities=4
- MULTI_FACTOR_RELATIVE_ATTENTION_REVIEW: activities=7
- SINGLE_FACTOR_RELATIVE_ATTENTION_REVIEW: activities=8

## Data quality

- source_files_available: PASS (5/5)
- activity_rows_present: PASS (per-activity rows generated)
- context_complete_gate_generated: PASS (context_complete_n=25)
- previous_review_required_preserved_for_traceability: PASS (v1 review-required wording is preserved only as previous_* traceability fields)
- relative_attention_layer_generated: PASS (CONTEXT_COMPLETE_NO_RELATIVE_ATTENTION_FLAG|MODERATE_RELATIVE_ATTENTION_REVIEW|MULTI_FACTOR_RELATIVE_ATTENTION_REVIEW|SINGLE_FACTOR_RELATIVE_ATTENTION_REVIEW)
- forbidden_columns_absent: PASS (NONE)
- interpretation_boundary_present: PASS (interpretation_boundary generated in outputs)

## Boundary

Descriptive CH6.5.3 v1.1 semantic relabel and attention-review layer only. Route-load and behavior response are normal hiking phenomena when a route has real ascent or load. This layer confirms whether route-load, behavior, weather, and readiness context are complete enough for comparison, and separately marks relative attention-review flags. It is not ability scoring, ranking, classing, THCI, radar, final hiking risk scoring, route suitability scoring, go/no-go decisioning, medical diagnosis, or causality evidence.
