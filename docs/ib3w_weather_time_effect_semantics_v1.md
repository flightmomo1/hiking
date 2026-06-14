# IB3W Weather Time-effect Semantics v1

## Purpose

This document adds a small integration index for the IB3W weather / environment feature chain.

It does **not** replace the existing contracts:

- `docs/ib3w_weather_observation_availability_contract_v1.md`
- `runs/ib3w_environment_feature_contract_v1_20260613.md`
- `configs/weather_context/ib3w_weather_context_schema_v1.csv`
- `configs/weather_context/ib3w_environment_window_status_policy_v1.csv`

The purpose is to classify weather/environment features by their **time-effect semantics** so downstream scripts do not confuse:

- near-real-time state;
- interval accumulation;
- antecedent lookback context;
- delayed-response proxy;
- unavailable direct observation fields.

## Core rule

IB3W scripts must not treat all weather fields as the same kind of time signal.

A route-window join answers:

> When the hiker passed this route segment, what weather/environment evidence is relevant to that time window?

Different variables answer this in different ways.

## Time-effect types

| time_effect_type | Meaning |
|---|---|
| `INSTANT_OR_NEAR_REAL_TIME_STATE` | Near-real-time station observation around `obs_time`, suitable for route-window context. |
| `INSTANT_OR_NEAR_REAL_TIME_STATE_OR_SHORT_INTERVAL_SUMMARY` | Near-real-time or short-interval summary such as mean wind. |
| `INTERVAL_ACCUMULATION_OR_OBSERVED_RAIN_SIGNAL_ENDING_AT_OBS_TIME` | Observed rain signal associated with `obs_time`; treat conservatively as rain that occurred before or up to the observation time unless the source interval is proven. |
| `ANTECEDENT_LOOKBACK_CONTEXT` | Feature summarizes observations before activity start or before a target window. |
| `DELAYED_RESPONSE_PROXY` | Proxy for conditions whose effect may persist or lag after the observed event. |
| `NOT_OBSERVED_PROXY_ONLY` | Direct target observation is unavailable; only a proxy or review-only condition may be emitted. |
| `UNAVAILABLE_DIRECT_SHORT_DURATION_RAIN_IN_CURRENT_DB` | Direct 10-minute or 1-hour rainfall intensity is unavailable in the current DB. |

## Field-family interpretation

### Temperature

`temperature_c` is near-real-time state evidence.

Allowed:
- route-window temperature background;
- heat/cold context input.

Not allowed:
- claim long-term climate normal;
- claim heat illness or cold injury by temperature alone.

### Relative humidity

`relative_humidity_pct` is near-real-time state evidence.

Allowed:
- route-window humidity background;
- drying limiter;
- saturation proxy input.

Not allowed:
- claim actual fog;
- claim observed low visibility;
- claim wet trail or heat illness by humidity alone.

### Mean wind

`wind_speed_ms` and `wind_direction_deg` are near-real-time or short-interval wind-state evidence.

Allowed:
- station-level wind background;
- drying, wet-cold, and exposure proxy input.

Not allowed:
- claim route-point measured wind field;
- claim gust exposure from mean wind;
- ignore terrain shielding/exposure if making route-level wind claims.

### Precipitation

`precipitation_mm` is an observed rain signal associated with observation time.

Allowed:
- recent rain context;
- antecedent precipitation context;
- last observed rain timing;
- support for conservative delayed-effect proxies.

Not allowed:
- interpret as instantaneous rain rate at `obs_time`;
- treat raw `precipitation_mm` as cumulative rainfall unless proven;
- impute missing rain as 0.

### Antecedent rain

`rain_lookback_6h`, `rain_lookback_24h`, `rain_lookback_72h`, `rain_lookback_7d`, and `hours_since_last_observed_rain` are lookback context.

Allowed:
- activity-preceding weather background;
- support for surface wetness / hydrologic response proxy review.

Not allowed:
- directly claim observed wet trail;
- directly claim soil moisture;
- directly claim stream surge;
- directly claim slope instability.

### Surface wetness and hydrologic response

These are delayed-response proxies unless direct water, soil, or trail observations exist.

Allowed:
- conservative review-only proxy context.

Not allowed:
- claim direct observation of wet trail, soil moisture, stream surge, or unstable slope.

### Water level

If `water_level_m` is introduced later, water level itself should be treated as near-real-time state evidence.

However, the cause of water-level change may be delayed upstream or antecedent rainfall.

Allowed:
- near-real-time water-level background if direct water-level observations are available;
- hydrologic response context with explicit source and representativeness review.

Not allowed:
- infer that rain happened at the same route-window time solely from elevated water level.

## Relationship to existing contracts

This index depends on the existing IB3W contracts:

1. Observation availability decides whether a field can be used as direct evidence.
2. Environment window status decides whether a value is observed, missing, no-source, no-variable, or proxy-only.
3. Environment feature contract decides whether downstream consumers may score, block, or review.
4. This document decides how to interpret the time-effect of each feature family.

## Mandatory boundary

This index does not authorize:

- missing-to-zero imputation;
- weather DB mutation;
- station fusion weighting;
- direct WBGT claims;
- direct UV claims;
- direct sunshine claims;
- heat illness or medical judgment;
- THCI scoring;
- final hiking risk scoring.

## Machine-readable table

The machine-readable companion file is:

`configs/weather_context/ib3w_weather_time_effect_semantics_v1.csv`
