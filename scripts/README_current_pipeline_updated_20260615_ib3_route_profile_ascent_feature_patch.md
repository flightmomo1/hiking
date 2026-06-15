# README update - IB3 route profile ascent feature patch

## Purpose

This update documents the elevation gain aggregation issue and the corrected route-profile-based ascent feature patch.

## Problem

The old gain-related fields are not reliable for 1Hz slow hiking activity data:

- `calibrated_cumulative_gain_m`
- `calibrated_cumulative_loss_m`
- `agg_total_gain_m`
- `agg_total_loss_m`
- `candidate_gain_m_per_km`
- `candidate_gain_rate_m_per_hour`
- `candidate_duration_min_per_100m_gain`

They can be severely underestimated because normal slow uphill progression is frequently excluded by `STEP_DISTANCE_LT_3M` and related step-validity rules.

## Corrected feature direction

Use route-profile-based route demand:

- `route_profile_ascent_m`
- `route_profile_descent_m`
- `route_profile_ascent_m_per_km`
- `route_profile_ascent_rate_m_per_hour`
- `duration_min_per_100m_route_profile_ascent`

## Current status

- Legacy gain features are blocked.
- Route-profile ascent feature patch is available.
- Formal model use still requires feature contract approval.

## Boundary

This layer is descriptive / feature-contract evidence only. It does not generate or authorize ability scores, ability ranks, ability classes, THCI scores, radar scores, or final hiking risk scores.
