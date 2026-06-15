# CURRENT INDEX - IB3 route profile ascent feature patch

## Branch
`codex/ib3-baseline-hiking-performance-route-profile-ascent-features-v1`

## Commits
- `af513b3 Add IB3 elevation gain aggregation QA`
- `db93cb9 Add IB3 route profile ascent feature patch`

## Current conclusion

The elevation gain aggregation issue has been isolated and a corrected route-profile-based ascent feature patch has been added.

The old activity-point gain fields remain blocked:

- `calibrated_cumulative_gain_m`
- `calibrated_cumulative_loss_m`
- `agg_total_gain_m`
- `agg_total_loss_m`
- `candidate_gain_m_per_km`
- `candidate_gain_rate_m_per_hour`
- `candidate_duration_min_per_100m_gain`

The replacement route-demand feature direction is:

- `route_profile_ascent_m`
- `route_profile_descent_m`
- `route_profile_ascent_m_per_km`
- `route_profile_ascent_rate_m_per_hour`
- `duration_min_per_100m_route_profile_ascent`

## Boundary

This is still a descriptive / feature-contract patch. It does not authorize ability scores, ability ranks, ability classes, THCI scores, radar scores, or final hiking risk scores.

`route_profile_gain_feature_model_ready=False`

`feature_contract_patch_required=True`
