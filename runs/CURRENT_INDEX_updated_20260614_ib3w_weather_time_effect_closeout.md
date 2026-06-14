# Current Index - 2026-06-14 IB3W Weather Time-effect Closeout

## Current Branch

- `codex/ib3w-weather-time-effect-docs-closeout-v1`

## Current Latest Commit Before This Documentation Branch

- `3e07da1 Add IB3W weather time-effect semantics index`

## Recent IB3W Commit Chain

- `29bdc25 Add IB3W wet-cold exposure context`
- `46faaba Add IB3W heat humid stress context`
- `69ca2bc Inventory IB3W heat humid route-window candidates`
- `86466e1 Add IB3W heat humid route-window context`
- `db893eb Add IB3W route-window weather context summary report`
- `3e07da1 Add IB3W weather time-effect semantics index`

## Current IB3W Role

IB3W is the Weather / Hydro Context Evidence Layer.

It provides contextual weather/hydrology evidence for later downstream interpretation.

It is not:

- final route risk
- final radar score
- THCI
- activity behavior analysis
- medical diagnosis
- final hiking risk score

## Authoritative Existing Contracts

Existing IB3W weather contracts remain valid:

- `docs/ib3w_weather_observation_availability_contract_v1.md`
- `runs/ib3w_environment_feature_contract_v1_20260613.md`
- `configs/weather_context/ib3w_weather_context_schema_v1.csv`
- `configs/weather_context/ib3w_environment_window_status_policy_v1.csv`

New time-effect index:

- `configs/weather_context/ib3w_weather_time_effect_semantics_v1.csv`
- `docs/ib3w_weather_time_effect_semantics_v1.md`

## Current Evidence Outputs

Route-window weather context summary:

- `outputs/ib3w_route_window_weather_context_summary_report_v1/`

Weather time-effect semantics index evidence:

- `outputs/ib3w_weather_time_effect_semantics_index_v1/`

## Route-window Summary Result

Activity:

- `qixing_lengshuikeng_xiaoyoukeng_20260410_biji_gpx`

Route-window rows:

- 16

Route-window trend:

- temperature mean delta = +2.1947°C
- relative humidity mean delta = -4.8948 percentage points
- wind speed mean delta = +0.7 m/s

Heat/humid support:

- heat_index_computed_window_count = 0
- daytime_heat_window_positive_count = 0
- all_windows_heat_humid_not_supported = True

Zero fallback:

- zero_fallback_true_total = 0

## Antecedent Weather Background

- 6h rain lookback = 0.5
- 24h rain lookback = 0.5
- 72h rain lookback = 7.5
- 7d rain lookback = 61.0
- last observed rain time = 2026-04-10T16:00:00+00:00
- last observed rain station = C0AC40
- hours since last observed rain = 5.596

Interpretation:

This is preceding weather background. It cannot directly claim current rain, observed wet trail, soil moisture, stream surge, or slope instability.

## Time-effect Semantics

The time-effect index defines:

| category | meaning |
|---|---|
| `INSTANT_OR_NEAR_REAL_TIME_STATE` | near-real-time station state |
| `INTERVAL_ACCUMULATION_OR_OBSERVED_RAIN_SIGNAL_ENDING_AT_OBS_TIME` | observed rain signal associated with obs_time |
| `ANTECEDENT_LOOKBACK_CONTEXT` | pre-activity or pre-window lookback background |
| `DELAYED_RESPONSE_PROXY` | delayed response proxy, review-only unless direct observation exists |
| `NOT_OBSERVED_PROXY_ONLY` | direct target unavailable; proxy only |
| `UNAVAILABLE_DIRECT_SHORT_DURATION_RAIN_IN_CURRENT_DB` | direct short-duration rain unavailable |

## Protected Semantics

- Missing remains missing.
- Observed zero remains observed zero.
- Missing-to-zero fallback is forbidden.
- `0.0` precipitation may only mean observed zero when source explicitly reports it.
- Weather context is not THCI.
- Weather context is not final hiking risk.
- No direct WBGT, UV, sunshine, visibility, weather text, wind gust, 10-minute rain, or 1-hour rain claims are supported by the current DB.

## Working Tree Guidance

Do not include unless explicitly requested:

- `folder_inventory_depth4.csv`
- `folder_role_audit_depth4.csv`
- unrelated generated outputs
- experimental scripts outside current documentation scope

## Next Recommended Stage

After this documentation closeout:

1. Keep IB3W contracts stable.
2. Use the time-effect index when future route-window, hydrologic, wetness, heat/humid, or wet-cold scripts emit boundary fields.
3. Defer final THCI / radar / behavior-model integration until weather context consumption gates are explicitly accepted.
