# Latest handoff - IB3 route profile ascent feature patch

## Summary

Elevation gain QA found that activity-point cumulative gain/loss severely underestimates ascent for 1Hz slow hiking data. The main cause is over-exclusion by `STEP_DISTANCE_LT_3M` and related elevation-step validity rules.

This does not mean OSM/NLSC route/elevation alignment failed. `calibrated_elevation_m` reaches the correct route elevation range. The issue is the activity-point gain aggregation rule.

## Evidence

Elevation gain aggregation QA:

- input activities: 26
- usable activities: 25
- aggregate gain below 50% elevation range: 25
- route profile ascent candidate available: 26
- audit: `PASS_ELEVATION_GAIN_AGGREGATION_QA_DESCRIPTIVE_ONLY`

Route profile ascent feature patch:

- base rows: 25
- matched elevation QA: 25
- missing elevation QA: 0
- legacy gain features blocked: 25
- route-profile ascent feature ready: 25
- audit: `PASS_ROUTE_PROFILE_ASCENT_FEATURE_PATCH_DESCRIPTIVE_CONTRACT_REQUIRED`

## Outputs

- `outputs/ib3_baseline_hiking_performance_elevation_gain_aggregation_qa_v1/activity_elevation_gain_aggregation_qa.csv`
- `outputs/ib3_baseline_hiking_performance_elevation_gain_aggregation_qa_v1/elevation_gain_aggregation_qa_audit.csv`
- `outputs/ib3_baseline_hiking_performance_elevation_gain_aggregation_qa_v1/elevation_gain_aggregation_qa_report.html`
- `outputs/ib3_baseline_hiking_performance_route_profile_ascent_features_v1/activity_route_profile_ascent_features.csv`
- `outputs/ib3_baseline_hiking_performance_route_profile_ascent_features_v1/route_profile_ascent_feature_audit.csv`
- `outputs/ib3_baseline_hiking_performance_route_profile_ascent_features_v1/route_profile_ascent_feature_report.html`

## Next step

Prepare a backend handoff note:

- Explain the old gain fields are blocked.
- Explain the corrected route-profile ascent/descent feature direction.
- State that the feature patch is ready for contract review, but not yet authorized for model scoring.
