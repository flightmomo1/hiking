# CURRENT INDEX — IB3 baseline hiking performance weather numeric reattach closeout

## Working directory

`D:\mountain_work\115_osm`

## Current branch

`codex/ib3-baseline-hiking-performance-weather-numeric-reattach-closeout-v1`

## Latest completed evidence commit

`9af7f7d Add IB3 weather numeric reattach and gain-rate sanity check`

## Upstream chain

- `50ee06f` Add IB3 baseline hiking performance v0 usability gate smoke
- `317c664` Document IB3 baseline hiking performance v0 usability gate smoke closeout
- `2373298` Add IB3 route-normalized performance comparison smoke
- `9af7f7d` Add IB3 weather numeric reattach and gain-rate sanity check

## Active evidence root

`outputs/ib3_baseline_hiking_performance_weather_numeric_reattach_v1`

## Key outputs

- `activity_route_normalized_comparison_weather_reattached.csv`
- `weather_numeric_reattach_gain_rate_sanity.csv`
- `weather_numeric_reattach_audit.csv`
- `weather_numeric_reattach_report.html`

## Closeout status

Weather numeric reattach is complete.

- comparison rows: 25
- join rows: 26
- output rows: 25
- matched weather numeric reattach: 25
- missing join count: 0
- audit: `PASS_WEATHER_NUMERIC_REATTACH_DESCRIPTIVE_ONLY`

## Important QA finding

Gain-rate sanity check shows the route/elevation gain indicators are not yet ready for ability estimation.

- `GAIN_RATE_LOW_REVIEW|GAIN_PER_KM_LOW_REVIEW`: 23
- `GAIN_RATE_PLAUSIBILITY_UNREVIEWED|GAIN_PER_KM_PLAUSIBILITY_UNREVIEWED`: 2

This suggests an elevation gain aggregation / duration denominator / route-distance semantics issue requiring QA before any ability model uses gain-related features.

## Engineering boundary

This closeout does not authorize:

- ability score
- ability rank
- ability class
- THCI scoring
- radar scoring
- final hiking risk scoring

Weather numeric values are descriptive context only. Gain-rate sanity flags are QA flags only, not ability judgments.
