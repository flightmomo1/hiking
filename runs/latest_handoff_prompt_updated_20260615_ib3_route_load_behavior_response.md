# Latest handoff - IB3 route load behavior response evidence

## Summary

The first 6.5.1 evidence layer is complete.

It builds a descriptive route-distance-window dataset for comparing:

- route-load evidence
- hiker behavior-response evidence
- OSM / facility exposure evidence
- weather context evidence

## Key commits

- `3b4fb65 Add IB3 route load behavior response fixture smoke`
- `8b839cf Add IB3 route load behavior response full25 evidence`
- `070be50 Add IB3 route load behavior full25 descriptive review`

## Full25 evidence

- usable activities: 25
- review-only excluded: `6_1`
- route-distance behavior windows: 2054
- activity summaries: 25
- audit: `PASS_ROUTE_LOAD_BEHAVIOR_RESPONSE_FULL25_DESCRIPTIVE_ONLY`

## Descriptive review conclusions

The full25 evidence can support descriptive 6.5.1 method text, with limitations.

Safe to write:

- use usability-gated activities
- build 50m route-distance windows
- describe route-load evidence using route profile and IB2 terrain / effort / exposure evidence
- describe behavior response using speed, low-speed point ratio, stopped point ratio, and HR percentiles
- treat OSM / facility proximity as exposure evidence
- treat weather as activity-level context

Do not write:

- ability scores, ranks, or classes
- causal claims
- facility use claims from proximity
- uphill/downhill or single-pass reaction claims
- window-level weather causality claims
- IB2 risk evidence as personal ability labels

## Known limitations

- `route_phase` is `UNKNOWN` in all full25 windows.
- `elapsed_time_span_sec` is not a pass-through time.
- `stopped_ratio` and `low_speed_ratio` are point ratios, not time ratios.
- `calibrated_slope_pct_*` is not suitable as the main route-load source in this layer.
- `nearest_environment_feature_distance_m_min` has no discrimination value in full25.

## Boundary

This layer is descriptive evidence for route-load behavior response only. It does not generate or authorize scoring, ranking, THCI, radar, or final risk.
