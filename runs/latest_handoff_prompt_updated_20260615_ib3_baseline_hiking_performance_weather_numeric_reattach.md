# Handoff — IB3 baseline hiking performance weather numeric reattach closeout

## Summary

Weather numeric context has been reattached to the route-normalized comparison smoke output.

Latest evidence commit:

`9af7f7d Add IB3 weather numeric reattach and gain-rate sanity check`

## Inputs

- `outputs/ib3_baseline_hiking_performance_route_normalized_comparison_smoke_v1/activity_route_normalized_comparison_smoke.csv`
- `outputs/ib3_baseline_hiking_performance_route_normalized_comparison_smoke_v1/route_normalized_comparison_smoke_audit.csv`
- `outputs/ib3w_activity_weather_performance_join_v1/activity_weather_performance_join.csv`

## Outputs

- `outputs/ib3_baseline_hiking_performance_weather_numeric_reattach_v1/activity_route_normalized_comparison_weather_reattached.csv`
- `outputs/ib3_baseline_hiking_performance_weather_numeric_reattach_v1/weather_numeric_reattach_gain_rate_sanity.csv`
- `outputs/ib3_baseline_hiking_performance_weather_numeric_reattach_v1/weather_numeric_reattach_audit.csv`
- `outputs/ib3_baseline_hiking_performance_weather_numeric_reattach_v1/weather_numeric_reattach_report.html`

## Result

- comparison rows: 25
- weather join rows: 26
- weather numeric reattached rows: 25
- partial reattach rows: 0
- missing join count: 0
- audit conclusion: `PASS_WEATHER_NUMERIC_REATTACH_DESCRIPTIVE_ONLY`

## Known issue

The gain-related indicators are not yet model-ready.

Current sanity distribution:

- 23 rows: `GAIN_RATE_LOW_REVIEW|GAIN_PER_KM_LOW_REVIEW`
- 2 rows: `GAIN_RATE_PLAUSIBILITY_UNREVIEWED|GAIN_PER_KM_PLAUSIBILITY_UNREVIEWED`

The next technical step should be elevation gain aggregation QA, not ability scoring.

## Recommended next branch

`codex/ib3-baseline-hiking-performance-elevation-gain-aggregation-qa-v1`

Recommended goal:

- inspect where `candidate_gain_m_per_km` and `candidate_gain_rate_m_per_hour` come from
- compare calibrated cumulative gain against route elevation profile / per-point elevation deltas
- determine whether total duration, moving duration, stopped time, or route coverage denominator is responsible
- keep all outputs descriptive and QA-only

## Boundary

Do not compute ability score, ability rank, ability class, THCI score, radar score, or final hiking risk score in the next step.
