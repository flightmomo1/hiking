# Current Index — CH6.5 Route-Load Context Index v1

## Working Directory

`D:\mountain_work\115_osm`

## Current Recommended Component

### CH6.5 route-load context index v1

Script:

`D:\mountain_work\115_osm\scripts\make_ch6_5_route_load_context_index_v1.py`

Output root:

`outputs\report_figures\ch6_5_route_load_context_index_v1`

Effective outputs:

- `route_load_context_windows_v1.csv`
- `route_load_context_activity_summary_v1.csv`
- `route_load_behavior_response_candidate_windows_v1.csv`
- `route_load_context_index_run_report_v1.md`

## Role in the Pipeline

This layer provides CH6.5 route-window descriptive context for downstream CH6.7 planning context fusion.

It is a route-load context evidence table layer, not a visualization-only prototype.

## Current Interpretation

Use this package when the report needs to describe where higher route-load context appears along the standardized route and whether observed behavior-response signals co-occur in those windows.

Do not interpret candidate windows as causality. Do not interpret them as personal ability labels or final risk labels.

## Boundary

This current index does not authorize:

- ability score;
- ability rank;
- ability class;
- THCI score;
- radar score;
- final hiking risk score;
- route suitability score;
- automatic suitable/unsuitable decision;
- automatic go/no-go decision;
- weather causality inference.

Weather context is descriptive only and not used to compute the route-load context index.

## Relationship to Other CH6.5 Outputs

Already retained separately:

- CH6.5 IB3D route-window bridge v1
- CH6.5 v2.2.7 review-safe single-activity profiles

Separate prototype / non-current layer:

- CH6.5 route-surface event behavior profile with IB3D events v1.5 / v1.5.1

## Recommended Commit Message

`Add CH6.5 route-load context index evidence`
