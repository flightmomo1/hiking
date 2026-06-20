# README Update — CH6.5 Route-Load Context Index v1

## Working Directory

`D:\mountain_work\115_osm`

## Purpose

This update records the CH6.5 route-load context index v1 evidence package.

The package creates descriptive 50 m route-window evidence from existing activity route-load / behavior-response windows. The route-load context index is derived from route, terrain, and map-derived factors only. Observed behavior-response flags are kept as descriptive overlays and candidate-window filters; they do not feed back into the route-load context index.

## Current Script

`D:\mountain_work\115_osm\scripts\make_ch6_5_route_load_context_index_v1.py`

## Current Output Root

`outputs\report_figures\ch6_5_route_load_context_index_v1`

## Output Inventory

Verified local output files:

| file | size bytes | role |
|---|---:|---|
| `route_load_context_windows_v1.csv` | 1885498 | per-activity 50 m route-window route-load context evidence |
| `route_load_context_activity_summary_v1.csv` | 9330 | activity-level summary of route-load context and candidate windows |
| `route_load_behavior_response_candidate_windows_v1.csv` | 1121985 | candidate windows combining high/very-high route-load context with observed behavior response signals |
| `route_load_context_index_run_report_v1.md` | 2350 | run report and boundary statement |

## Method Summary

The route-load context index uses these route / terrain / map-derived factors:

- vertical range context;
- calibrated slope context, with vertical-range fallback when slope is missing;
- IB2 effort evidence;
- IB2 terrain evidence;
- near-steps ratio.

The index output is written as `route_load_context_index_0_100` and `route_load_context_band`.

Candidate windows are selected only when:

1. route-load context is high or very high; and
2. an observed behavior-response signal is present.

Candidate windows are review evidence only. They are not causality claims and not final risk assessment.

## Boundary

This package is descriptive route-load context evidence only.

It does not generate or authorize:

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

Weather context is descriptive only and is not used to compute the route-load context index. Missing weather is not filled as zero, no-rain, calm, normal, or safe evidence.

Behavior-response fields are not used to compute route-load context. They are only retained for descriptive overlay and candidate-window review.

## Relationship to Adjacent CH6.5 Outputs

This package should be kept as the CH6.5 route-load context evidence table layer.

It is separate from:

- IB3D event route-window bridge v1;
- v2.2.7 review-safe single-activity surface profile outputs;
- route-surface event behavior profile v1.5 / v1.5.1 prototype figures.

## Recommended Version Decision

`route_load_context_index_v1` is recommended to retain as a formal descriptive evidence package because it supplies the route-window context layer used downstream by CH6.7 planning context fusion.

## Recommended Commit Scope

Include:

- `scripts\make_ch6_5_route_load_context_index_v1.py`
- `outputs\report_figures\ch6_5_route_load_context_index_v1`
- this README / changelog / CURRENT_INDEX / handoff documentation set

Do not include:

- `scripts\make_ch6_5_route_surface_event_behavior_profile_with_ib3d_events_v1_5.py`
- `scripts\make_ch6_5_route_surface_event_behavior_profile_with_ib3d_events_v1_5_1.py`
- CH6.7 scripts and outputs
- CH6.8 scripts and outputs
- CH6 report figure scripts
- older single-activity profile prototypes
- `_handoff_6_2_method_files`
