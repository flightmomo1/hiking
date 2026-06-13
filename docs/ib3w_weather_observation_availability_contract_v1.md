# IB3W Weather Observation Availability Contract v1

## Purpose

This document records the observed field availability of the current IB3W weather database:

`weather/tw_weather_2026-05-01.sqlite3`

The contract is based on the `weather_observations` table and the current primary mountain representative stations used for the Qixing / Lengshuikeng / Xiaoyoukeng weather context chain.

Primary stations:

| station_id | station_name |
|---|---|
| 466910 | 鞍部 |
| 466930 | 陽明山 |
| A0A460 | 文化大學 |
| C0AC40 | 大屯山 |

This contract defines which fields are currently usable for IB3W primary-station evidence, which fields are partially usable, and which fields must be treated as unavailable even though they exist in the schema.

---

## Core principle

A column existing in the database schema does not imply that it contains usable observations.

IB3W scripts must follow these rules:

1. Missing remains missing.
2. Observed zero remains observed zero.
3. Missing weather values must not be imputed as zero.
4. Fields with 0% observed availability must not be used as if they were direct observations.
5. Proxy models must explicitly state when a direct target field is unavailable.
6. Weather context is not a final hiking risk score.
7. Weather context is not THCI unless explicitly integrated later.

---

## Current usable field groups

### Reliable primary-station fields

The following fields are available at high ratios for the primary mountain stations and may be used as direct primary-station evidence:

| field | availability pattern | recommended use |
|---|---|---|
| `temperature_c` | high availability across all primary stations | temperature, heat/cold context, dew point proxy |
| `relative_humidity_pct` | high availability across all primary stations | humidity, saturation proxy, drying limiter |
| `wind_speed_ms` | high availability across all primary stations | wind exposure proxy, drying context, wet-cold modifier |
| `wind_direction_deg` | high availability across all primary stations | wind direction context, future exposure analysis |
| `precipitation_mm` | high availability across all primary stations | observed rain signal, antecedent precipitation context |

### Partially available primary-station fields

| field | availability pattern | recommended use |
|---|---|---|
| `pressure_hpa` | available for 陽明山 and 大屯山; unavailable for 鞍部 and 文化大學 | partial pressure context only; station-specific QA required |

### Unavailable direct-observation fields

The following fields are present in the database schema but have 0% observed availability in the current overall database audit and at the primary mountain stations:

| field | consequence |
|---|---|
| `weather` | no direct weather-text classification such as fog, rain, thunderstorm, cloudy |
| `wind_gust_ms` | no direct gust evidence; use mean wind only |
| `precipitation_10min_mm` | no direct short-duration 10-minute rainfall evidence |
| `precipitation_1hr_mm` | no direct hourly rainfall evidence |
| `sunshine_duration_min` | no direct sunshine/drying evidence |
| `visibility_m` | no direct visibility evidence |
| `uv_index` | no direct UV exposure evidence |

---

## Primary station availability summary

| station_id | station_name | total_rows | temperature_c | relative_humidity_pct | pressure_hpa | wind_speed_ms | wind_direction_deg | precipitation_mm | weather | wind_gust_ms | precipitation_10min_mm | precipitation_1hr_mm | sunshine_duration_min | visibility_m | uv_index |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 466910 | 鞍部 | 3932 | 98.78% | 98.75% | 0.00% | 98.68% | 98.58% | 91.79% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |
| 466930 | 陽明山 | 3937 | 98.63% | 98.58% | 98.53% | 98.40% | 98.40% | 98.40% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |
| A0A460 | 文化大學 | 3933 | 98.35% | 98.32% | 0.00% | 98.25% | 98.22% | 98.17% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |
| C0AC40 | 大屯山 | 698 | 99.57% | 99.43% | 99.28% | 98.85% | 98.71% | 98.71% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |

---

## Overall database availability summary

Total rows in `weather_observations`: 1,140,566

| field | available_rows | overall_status |
|---|---:|---|
| `temperature_c` | 1,070,449 | available |
| `relative_humidity_pct` | 1,066,342 | available |
| `pressure_hpa` | 396,718 | partial |
| `wind_speed_ms` | 1,068,731 | available |
| `wind_direction_deg` | 1,067,656 | available |
| `precipitation_mm` | 1,062,947 | available |
| `weather` | 0 | unavailable |
| `wind_gust_ms` | 0 | unavailable |
| `precipitation_10min_mm` | 0 | unavailable |
| `precipitation_1hr_mm` | 0 | unavailable |
| `sunshine_duration_min` | 0 | unavailable |
| `visibility_m` | 0 | unavailable |
| `uv_index` | 0 | unavailable |

---

## Consequences for IB3W hazard contexts

### Supported with current primary-station data

The following contexts can be built from current primary-station weather observations:

1. Antecedent precipitation context
2. Surface wetness proxy
3. Drying context using temperature, humidity, and wind
4. Fog / low-cloud condition proxy using humidity saturation and estimated dew point depression
5. Wet-cold exposure proxy
6. Heat / humid heat proxy
7. Mean-wind exposure proxy
8. Partial pressure trend context, limited to stations with `pressure_hpa`

### Not directly supported with current database

The following contexts cannot be directly observed from the current DB:

1. Direct fog observation
2. Direct low visibility observation
3. Direct weather text classification
4. Direct sunshine duration
5. Direct UV exposure
6. Direct wind gust exposure
7. Direct 10-minute rainfall intensity
8. Direct 1-hour rainfall intensity
9. Direct thunderstorm or lightning observation

These may only be represented as:
- unavailable;
- proxy-only;
- review-only;
- external-data-required.

---

## Required output boundary for future scripts

When a script uses a proxy because direct fields are unavailable, it must include explicit claim-boundary fields.

Examples:

| proxy topic | required boundary field |
|---|---|
| fog / low cloud | `actual_fog_claim_status = NOT_CLAIMED_NO_DIRECT_VISIBILITY_OR_WEATHER_TEXT` |
| low visibility | `direct_visibility_observation_status = VISIBILITY_M_UNAVAILABLE_IN_CURRENT_DB` |
| weather text | `weather_text_observation_status = WEATHER_TEXT_UNAVAILABLE_IN_CURRENT_DB` |
| sunshine | `sunshine_context_status = SUNSHINE_CONTEXT_MISSING_OR_UNAVAILABLE` |
| UV | `uv_context_status = UV_INDEX_UNAVAILABLE_IN_CURRENT_DB` |
| wind gust | `wind_gust_context_status = WIND_GUST_UNAVAILABLE_IN_CURRENT_DB` |
| short-duration rain | `short_duration_rain_context_status = SHORT_DURATION_RAIN_UNAVAILABLE_IN_CURRENT_DB` |
| final risk | `thci_or_final_risk_status = NOT_COMPUTED_CONTEXT_ONLY` |

---

## Current implemented layer interpretation

### Antecedent precipitation context

Allowed:
- use `precipitation_mm` as observed raw precipitation signal;
- evaluate recent and antecedent rain windows;
- preserve source semantics.

Not allowed:
- treat raw `precipitation_mm` as cumulative rainfall unless proven;
- impute missing rain as zero.

### Surface wetness proxy

Allowed:
- combine observed rain, last rain timing, humidity, temperature, and wind;
- output conservative wetness proxy status.

Not allowed:
- claim true soil moisture;
- over-amplify light rain into persistent wetness without supporting evidence.

### Sunshine drying context

Allowed:
- report that sunshine direct observation is unavailable;
- use temperature, humidity, and wind as partial drying evidence.

Not allowed:
- treat missing `sunshine_duration_min` as zero sunshine.

### Fog / low-cloud condition proxy

Allowed:
- estimate dew point depression from temperature and RH;
- use humidity saturation, wind class, activity timing, and surface wetness as condition proxy.

Not allowed:
- claim actual fog;
- claim actual low visibility;
- claim actual迷航;
- use `visibility_m` or `weather` as if observed, because current DB availability is 0%.

---

## Recommended next implementation order after this contract

1. `ib3w_wet_cold_exposure_context_v1`
2. `ib3w_heat_humid_stress_context_v1`
3. `ib3w_mean_wind_exposure_context_v1`
4. `ib3w_pressure_trend_context_v1`
5. `ib3w_external_visibility_weather_source_inventory_v1`
6. `ib3w_external_short_duration_rain_source_inventory_v1`
7. `ib3w_external_sunshine_uv_source_inventory_v1`

The next script should prefer fields that are currently well supported by the weather DB:
- temperature
- relative humidity
- wind speed
- wind direction
- precipitation
- partial pressure

---

## Contract summary

The current IB3W weather DB is suitable for:

- temperature context;
- humidity context;
- mean wind context;
- wind direction context;
- precipitation context;
- partial pressure context;
- proxy-only fog / low-cloud condition inference.

The current IB3W weather DB is not suitable for direct claims about:

- observed fog;
- observed visibility;
- observed weather text;
- sunshine duration;
- UV exposure;
- wind gust;
- 10-minute rainfall intensity;
- 1-hour rainfall intensity;
- lightning;
- thunderstorm;
- actual navigation failure;
- THCI or final hiking risk score.
