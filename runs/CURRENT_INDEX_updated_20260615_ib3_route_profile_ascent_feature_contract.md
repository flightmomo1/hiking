# CURRENT INDEX - IB3 route profile ascent feature contract

## Branch
`codex/ib3-baseline-hiking-performance-route-profile-ascent-feature-contract-v1`

## Commits

- `af513b3 Add IB3 elevation gain aggregation QA`
- `db93cb9 Add IB3 route profile ascent feature patch`
- `b0747d9 Document IB3 route profile ascent feature patch closeout`
- `697fa48 Add IB3 route profile ascent feature contract`

## Current effective contract

The route-profile-based ascent/descent feature direction is now formally documented for completion-time model feature review.

Primary contract files:

- `configs/hiking_performance/ib3_route_profile_ascent_feature_contract_v1.csv`
- `docs/ib3_route_profile_ascent_feature_contract_v1.md`

## Model-use decision

Allowed for contract review:

- `route_profile_ascent_m`
- `route_profile_descent_m`
- `route_profile_ascent_m_per_km`
- `route_profile_ascent_rate_m_per_hour`
- `duration_min_per_100m_route_profile_ascent`

Blocked legacy gain fields:

- `calibrated_cumulative_gain_m`
- `calibrated_cumulative_loss_m`
- `agg_total_gain_m`
- `agg_total_loss_m`
- `candidate_gain_m_per_km`
- `candidate_gain_rate_m_per_hour`
- `candidate_duration_min_per_100m_gain`

## Boundary

This contract defines feature-use boundaries for future hiking completion-time modeling only.

It does not compute or authorize ability scores, ability ranks, ability classes, THCI scores, radar scores, or final hiking risk scores.
