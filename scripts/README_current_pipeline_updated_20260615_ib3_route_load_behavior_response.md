# README update - IB3 route load behavior response evidence

## Purpose

This update documents the first 6.5.1 evidence layer for personal hiking feature construction and route-load comparison.

The layer creates route-distance-window evidence for describing how hiker behavior-response metrics vary alongside route-load, OSM/facility exposure, and weather context evidence.

## Effective outputs

- `outputs/ib3_personal_hiking_features_route_load_comparison_full25_v1/activity_route_load_behavior_response_windows.csv`
- `outputs/ib3_personal_hiking_features_route_load_comparison_full25_v1/activity_route_load_behavior_response_summary.csv`
- `outputs/ib3_personal_hiking_features_route_load_comparison_full25_v1/activity_route_load_behavior_response_full25_audit.csv`
- `outputs/ib3_personal_hiking_features_route_load_comparison_full25_v1/activity_route_load_behavior_response_full25_report.html`
- `outputs/ib3_personal_hiking_features_route_load_comparison_full25_review_v1/activity_route_load_behavior_response_full25_descriptive_review.csv`
- `outputs/ib3_personal_hiking_features_route_load_comparison_full25_review_v1/activity_route_load_behavior_response_full25_descriptive_review_report.html`
- `docs/ib3_route_load_behavior_response_full25_review_addendum_v1.md`

## Safe use

This layer may be used to describe:

- 50m route-distance windows
- route-load evidence
- behavior-response evidence
- OSM / facility exposure evidence
- activity-level weather context

## Limitations

- `route_phase` is not usable for uphill/downhill separation in the current full25 output.
- `elapsed_time_span_sec` is not a pass-through time.
- stopped and low-speed ratios are point ratios.
- facility proximity is exposure evidence only.
- weather fields are activity-level context only.
- IB2 risk evidence is route evidence, not personal ability evidence.

## Boundary

This layer does not generate or authorize:

- ability scores
- ability ranks
- ability classes
- THCI scores
- radar scores
- final hiking risk scores
