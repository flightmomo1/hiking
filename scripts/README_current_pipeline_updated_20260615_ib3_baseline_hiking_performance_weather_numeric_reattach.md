# README — IB3 baseline hiking performance weather numeric reattach closeout

## Role

This step closes out the weather numeric reattach patch for the IB3 baseline hiking performance route-normalized comparison smoke.

## Script

`scripts/ib3_activity_environment/ib3_baseline_hiking_performance_weather_numeric_reattach_v1.py`

## Output root

`outputs/ib3_baseline_hiking_performance_weather_numeric_reattach_v1`

## Outputs

- `activity_route_normalized_comparison_weather_reattached.csv`
- `weather_numeric_reattach_gain_rate_sanity.csv`
- `weather_numeric_reattach_audit.csv`
- `weather_numeric_reattach_report.html`

## Result

Weather numeric fields were successfully reattached for all 25 comparison rows.

- matched weather numeric reattach: 25 / 25
- missing join: 0
- audit: `PASS_WEATHER_NUMERIC_REATTACH_DESCRIPTIVE_ONLY`

## Known limitation

Gain-rate and gain-per-km indicators are flagged for review in most rows.

This means gain-related features must not be used for ability estimation until elevation gain aggregation QA is completed.

## Non-goals

This step does not produce or authorize:

- ability score
- ability rank
- ability class
- THCI score
- radar score
- final hiking risk score

Weather numeric fields and gain sanity flags are descriptive QA evidence only.
