# README update - IB3 route profile ascent feature contract

## Purpose

This update records the formal feature contract for replacing unreliable activity-point gain/loss fields with route-profile-based ascent/descent features.

## Effective files

- `configs/hiking_performance/ib3_route_profile_ascent_feature_contract_v1.csv`
- `docs/ib3_route_profile_ascent_feature_contract_v1.md`

## Use in completion-time modeling

Use:

- `route_profile_ascent_m`
- `route_profile_descent_m`
- `route_profile_ascent_m_per_km`
- `route_profile_ascent_rate_m_per_hour`
- `duration_min_per_100m_route_profile_ascent`

Do not use:

- `calibrated_cumulative_gain_m`
- `calibrated_cumulative_loss_m`
- `agg_total_gain_m`
- `agg_total_loss_m`
- `candidate_gain_m_per_km`
- `candidate_gain_rate_m_per_hour`
- `candidate_duration_min_per_100m_gain`

## Boundary

This is a feature-use contract only. It does not generate or authorize ability scores, ability ranks, ability classes, THCI scores, radar scores, or final hiking risk scores.
