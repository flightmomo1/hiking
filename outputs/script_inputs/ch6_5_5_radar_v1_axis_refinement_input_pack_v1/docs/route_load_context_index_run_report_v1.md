# Chapter 6.5 Route Load Context Index v1

- input_csv: `D:\mountain_work\115_osm\outputs\ib3_personal_hiking_features_route_load_comparison_full25_v1\activity_route_load_behavior_response_windows.csv`
- output_root: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_route_load_context_index_v1`
- window_row_count: `2054`
- activity_summary_row_count: `25`
- candidate_window_row_count: `958`
- audit_conclusion: `PASS_ROUTE_LOAD_CONTEXT_INDEX_V1_DESCRIPTIVE_ONLY`
- audit_issues: `NONE`

## Method

- `route_load_context_index_0_100` uses route-load base factors only.
- Factors: vertical range, slope context, IB2 effort evidence, IB2 terrain evidence, and near-steps ratio.
- Behavior response is not used to compute route-load context index.
- Weather context is descriptive only and is not included in the index.
- No weather zero-fill is performed.
- `route_phase=UNKNOWN` is not used for ascent/descent comparison.

## Boundaries

- descriptive route-load context evidence only
- no ability score
- no ability rank
- no ability class
- no THCI score
- no radar score
- no final hiking risk score
- candidate windows are not causality claims
- candidate windows are not ability labels

## Band Distribution

- HIGH_ROUTE_LOAD_CONTEXT: 450
- LOWER_ROUTE_LOAD_CONTEXT: 555
- MODERATE_ROUTE_LOAD_CONTEXT: 353
- VERY_HIGH_ROUTE_LOAD_CONTEXT: 696

## Environment Context Flags Top Values

- NO_RAIN_CONTEXT|WIND_GUST_OBSERVED_CONTEXT|HIGH_UV_CONTEXT: 906
- HIGH_HUMIDITY_CONTEXT|NO_RAIN_CONTEXT|WIND_GUST_OBSERVED_CONTEXT|HIGH_UV_CONTEXT: 818
- HIGH_HUMIDITY_CONTEXT|NO_RAIN_CONTEXT|WIND_GUST_OBSERVED_CONTEXT|STRONG_GUST_CONTEXT|HIGH_UV_CONTEXT: 165
- HIGH_HUMIDITY_CONTEXT|RAIN_OBSERVED_CONTEXT|WIND_GUST_OBSERVED_CONTEXT|HIGH_UV_CONTEXT: 84
- HIGH_HUMIDITY_CONTEXT|RAIN_OBSERVED_CONTEXT|WIND_GUST_OBSERVED_CONTEXT|STRONG_GUST_CONTEXT: 81

## Candidate Window Rule

- route_load_context_band is HIGH_ROUTE_LOAD_CONTEXT or VERY_HIGH_ROUTE_LOAD_CONTEXT
- and at least one observed behavior response signal exists
- HR_MISSING alone is retained as a QA flag but is not treated as a behavior response signal for candidate selection

## Outputs

- `route_load_context_windows_v1.csv`
- `route_load_context_activity_summary_v1.csv`
- `route_load_behavior_response_candidate_windows_v1.csv`
