# IB3 Route Profile Ascent Feature Contract v1

## Purpose

This contract defines the replacement feature direction for hiking completion-time modeling after elevation gain aggregation QA.

The old activity-point cumulative gain/loss fields are not reliable for 1Hz slow hiking activity data because normal uphill movement can be over-excluded by `STEP_DISTANCE_LT_3M`, duplicate timestamp handling, stop/stall handling, and related step-validity gates.

The corrected feature direction is to represent route ascent/descent demand from the OSM/NLSC-aligned route profile rather than raw activity-point elevation delta accumulation.

## Primary decision

Use route-profile-based ascent/descent for route demand.

Do not use activity-point cumulative gain/loss as model features.

## Contract-ready fields

The following fields are contract-review ready for completion-time model feature design:

- `route_profile_ascent_m`
- `route_profile_descent_m`
- `route_profile_ascent_m_per_km`
- `route_profile_ascent_rate_m_per_hour`
- `duration_min_per_100m_route_profile_ascent`
- `route_profile_gain_feature_status`
- `legacy_gain_features_blocked`

## Required downstream rule

Before the completion-time model consumes route-profile gain features, downstream code must check:

- `legacy_gain_features_blocked=True`
- `route_profile_gain_feature_status=ROUTE_PROFILE_ASCENT_FEATURE_READY_DESCRIPTIVE_CONTRACT_PATCH`

## Blocked legacy fields

The following fields must not be used as model inputs:

- `calibrated_cumulative_gain_m`
- `calibrated_cumulative_loss_m`
- `agg_total_gain_m`
- `agg_total_loss_m`
- `candidate_gain_m_per_km`
- `candidate_gain_rate_m_per_hour`
- `candidate_duration_min_per_100m_gain`

If retained in outputs, they are traceability evidence only.

## Input evidence

Elevation gain aggregation QA:

- `outputs/ib3_baseline_hiking_performance_elevation_gain_aggregation_qa_v1/activity_elevation_gain_aggregation_qa.csv`
- `outputs/ib3_baseline_hiking_performance_elevation_gain_aggregation_qa_v1/elevation_gain_aggregation_qa_audit.csv`

Route-profile ascent feature patch:

- `outputs/ib3_baseline_hiking_performance_route_profile_ascent_features_v1/activity_route_profile_ascent_features.csv`
- `outputs/ib3_baseline_hiking_performance_route_profile_ascent_features_v1/route_profile_ascent_feature_audit.csv`

## Boundary

This contract does not compute or authorize:

- ability scores
- ability ranks
- ability classes
- THCI scores
- radar scores
- final hiking risk scores

This contract only defines feature-use boundaries for future hiking completion-time modeling.
