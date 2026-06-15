# IB3 Route Load Behavior Response Full25 Review Addendum v1

## Purpose

This addendum records the descriptive-use boundaries for the existing full25
route-load and behavior-response evidence. It does not modify or recalculate
the source evidence.

Source scope:

- `outputs/ib3_personal_hiking_features_route_load_comparison_full25_v1/activity_route_load_behavior_response_windows.csv`
- `outputs/ib3_personal_hiking_features_route_load_comparison_full25_v1/activity_route_load_behavior_response_summary.csv`
- `outputs/ib3_personal_hiking_features_route_load_comparison_full25_v1/activity_route_load_behavior_response_full25_audit.csv`
- `configs/personal_hiking_features/ib3_route_load_behavior_response_schema_v1.csv`
- `docs/ib3_route_load_behavior_response_schema_v1.md`

Reviewed scope:

- usable activity summaries: 25
- 50m route-window rows: 2054
- source audit: `PASS_ROUTE_LOAD_BEHAVIOR_RESPONSE_FULL25_DESCRIPTIVE_ONLY`

## Primary decision

The full25 evidence can support descriptive analysis of behavior response,
route-load evidence, mapped environment/facility exposure, and activity-level
weather context.

It cannot support personal ability ranking, ability classification, causal
inference, facility-use claims, or weather-attributed route-window effects.

## Route phase and elapsed-span limits

- All route windows have `route_phase=UNKNOWN`.
- The evidence cannot distinguish ascent, descent, or a single directional pass.
- `elapsed_time_span_sec` is an aggregation span and must not be interpreted as
  route-window traversal time.

## Route-load evidence

Use these fields as the primary descriptive route-load evidence:

- `route_profile_elevation_min_m`
- `route_profile_elevation_max_m`
- `route_profile_elevation_range_m`
- `ib2_terrain_evidence_median`
- `ib2_effort_evidence_median`
- `ib2_exposure_evidence_median`
- `ib2_risk_band_evidence`

`calibrated_slope_pct_median` and `calibrated_slope_pct_p75_abs` are secondary
review-only context because coverage is incomplete and slope review flags are
prevalent.

`route_load_context_band` is a rule-derived evidence label. It is not an
ability class or formal risk score. The recommended future name is
`route_load_evidence_rule_label`.

## Behavior-response naming

- `stopped_ratio` is a sampled-point ratio, not a time ratio.
- `low_speed_ratio` is a sampled-point ratio, not a time ratio.
- Recommended future names are `stopped_point_ratio` and
  `low_speed_point_ratio`.

Speed percentiles and heart-rate percentiles remain descriptive context only.

## OSM and facility exposure

- Feature-specific `near_*_ratio` fields represent mapped proximity exposure.
- Proximity does not prove actual facility use.
- `nearest_environment_feature_distance_m_min` has no useful discrimination
  because all reviewed values are zero.
- `near_road_ratio` has no comparative variation because road exposure is
  positive for all windows.
- `near_cliff_ratio` has no comparative variation because cliff exposure is
  zero for all windows.

## Weather context

Weather fields are attached at activity level and repeated across route
windows. They may be used for descriptive activity-level stratification, but
not as window-level instantaneous weather and not to explain a single-window
speed or heart-rate change.

Missing weather must remain missing and must never be hard-filled as zero.

## Safe 6.5.1 methodology statements

- **FULL25_DESCRIPTIVE_ANALYSIS_SCOPE**: Use as the evidence basis for 6.5.1 with all review boundaries retained.
- **POINT_RATIO_NAMING**: Use stopped_point_ratio and low_speed_point_ratio in future contracts; define the denominator explicitly in 6.5.1.
- **PRIMARY_ROUTE_LOAD_EVIDENCE**: Use these fields as the primary route-load evidence in 6.5.1.
- **ROUTE_LOAD_RULE_LABEL**: Rename to route_load_evidence_rule_label in a future contract.
- **OSM_FACILITY_EXPOSURE_BOUNDARY**: Write exposure, proximity, or mapped context; never write facility use.
- **WEATHER_CONTEXT_LEVEL**: Use for descriptive stratification only; do not attribute single-window speed changes to weather.
- **QA_FLAG_PREVALENCE**: Report QA prevalence alongside descriptive findings.
- **NONCANONICAL_ROUTE_BOUNDARY**: Retain counts as review evidence only.
- **LEGACY_AND_SCORING_BOUNDARY**: Carry the explicit zero-generation boundary into 6.5.1.

## Conclusions that are not supported

- **ROUTE_PHASE_LIMITATION**: Full25 evidence cannot distinguish ascent, descent, or a single directional pass through a route window.
- **ELAPSED_SPAN_LIMITATION**: It is an aggregation span, not route-window traversal time.
- **SLOPE_EVIDENCE_LIMITATION**: Calibrated slope must not be the primary 6.5.1 route-load source.
- **NEAREST_ENVIRONMENT_DISTANCE_LIMITATION**: The generic minimum distance cannot distinguish environment exposure.
- **ROAD_CLIFF_EXPOSURE_LIMITATION**: All-positive or all-zero exposure has no within-dataset contrast.
- **SCHEMA_FULL25_ALIGNMENT**: The full25 artifact must not be represented as fully covered by the fixture contract.
- **CAUSAL_AND_PERSONAL_INFERENCE_BOUNDARY**: Do not infer causality, personal ability, personal risk, or actual facility use.

## Explicit engineering boundary

This addendum does not generate or authorize:

- ability score
- ability rank
- ability class
- THCI score
- radar score
- final hiking risk score

IB2 risk evidence remains route evidence and must not become a personal ability
label. Legacy gain fields remain blocked as route-load sources.
