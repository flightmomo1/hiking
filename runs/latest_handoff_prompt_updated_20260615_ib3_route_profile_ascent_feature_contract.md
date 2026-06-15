# Latest handoff - IB3 route profile ascent feature contract

## Summary

The route-profile ascent/descent replacement direction has been formalized into a feature contract.

The old activity-point cumulative gain/loss fields remain blocked because elevation gain aggregation QA showed they severely underestimate ascent for 1Hz slow hiking data.

The corrected completion-time feature direction is route-profile-based route demand.

## Effective contract files

- `configs/hiking_performance/ib3_route_profile_ascent_feature_contract_v1.csv`
- `docs/ib3_route_profile_ascent_feature_contract_v1.md`

## Required downstream gate

Before downstream completion-time model consumption, check:

- `legacy_gain_features_blocked=True`
- `route_profile_gain_feature_status=ROUTE_PROFILE_ASCENT_FEATURE_READY_DESCRIPTIVE_CONTRACT_PATCH`

## Backend guidance

Use route profile ascent/descent for route demand.

Do not use raw activity-point cumulative gain/loss as model features.

## Boundary

This is a feature contract for completion-time model design. It does not authorize scoring, ranking, THCI, radar, or final hiking risk.
