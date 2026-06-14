# README Update - IB3 Baseline Hiking Performance Model Planning

Date: 2026-06-15

## Current pipeline position

The pipeline currently provides:

- IB3A-RC full26 activity performance evidence
- IB3W CODiS weather profile evidence
- A descriptive activity performance x weather context join
- A baseline hiking performance feature contract

The implementation does not yet provide a hiking ability model.

## Planning inputs

- `outputs/ib3w_activity_weather_performance_join_v1/activity_weather_performance_join.csv`
- `outputs/ib3w_activity_weather_performance_join_v1/activity_weather_performance_join_audit.csv`
- `outputs/ib3a_rc_full26_performance_summary_v1/activity_performance_summary.csv`
- `outputs/ib3w_codis_weather_profile_report_v1/activity_weather_profile_report_table.csv`

## Planning outputs

- `docs/ib3_baseline_hiking_performance_model_planning_v1.md`
- `configs/hiking_performance/ib3_baseline_hiking_performance_feature_contract_v1.csv`

## Conceptual layers

1. Route / terrain demand
2. Activity performance
3. Weather context
4. Data quality / usability
5. Individual ability estimate

Route demand describes route difficulty context. Activity performance describes
the observed activity. Weather is an environmental comparison context, not an
automatic penalty. Data quality determines eligibility. Any individual ability
estimate must use multiple comparable and quality-passed activities.

## Authorization boundary

- Planning / contract only
- No ability score
- No THCI score
- No radar score
- No final hiking risk score
- No direct conversion of weather labels to penalties
- No missing-value zero fill
- All feature rows have `scoring_allowed_in_this_branch = False`

## Future prototype direction

The next descriptive prototype may examine:

- Route-normalized completion time
- Route-normalized moving speed
- Climb-adjusted performance
- Heart-rate-aware effort context
- Weather-context-aware comparison
- Quality-gated usable activity sets

It must first test whether performance shifts under comparable route demand and
different weather contexts. It must not treat high humidity, rain, or gust
labels as direct deductions.

## Recommended next branch

- `codex/ib3-baseline-hiking-performance-model-smoke-v1`

This should remain a smoke / descriptive prototype before any production model
or individual ability score is considered.
