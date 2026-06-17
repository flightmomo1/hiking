# Changelog — CH6.5 Route-Load Context Index v1

## Added

- Added `scripts\make_ch6_5_route_load_context_index_v1.py`.
- Added CH6.5 route-load context index v1 output root:
  - `outputs\report_figures\ch6_5_route_load_context_index_v1`

## Output Files

Verified output files:

- `route_load_context_windows_v1.csv`
- `route_load_context_activity_summary_v1.csv`
- `route_load_behavior_response_candidate_windows_v1.csv`
- `route_load_context_index_run_report_v1.md`

## Method

The script builds a descriptive route-load context evidence layer from existing 50 m activity route-load / behavior-response windows.

The route-load context index uses route, terrain, and map-derived factors only:

- vertical range;
- slope context;
- IB2 effort evidence;
- IB2 terrain evidence;
- near-steps ratio.

Observed behavior response is retained separately and is not used to compute the route-load context index.

Candidate windows are defined as high/very-high route-load context windows with observed behavior-response signal. Candidate windows are review evidence only.

## Boundary

No ability score, ability rank, ability class, THCI score, radar score, final hiking risk score, route suitability score, or automatic go/no-go decision was added.

Weather context remains descriptive and is not used to compute the index. Missing weather is not zero-filled.

Behavior response does not feed back into route-load calculation.
