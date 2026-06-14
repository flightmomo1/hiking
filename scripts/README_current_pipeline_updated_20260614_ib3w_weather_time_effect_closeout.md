# README Current Pipeline Update - IB3W Weather Time-effect Closeout

- Date: 2026-06-14
- Branch: codex/ib3w-weather-time-effect-docs-closeout-v1
- Upstream: 3e07da1 Add IB3W weather time-effect semantics index

## IB3W Current Position

IB3W is the Weather / Hydro Context Evidence Layer.

It sits after calibrated activity / route-window evidence and before downstream behavior, radar, THCI, or model consumption.

Pipeline interpretation:

IB3A-RC / activity backend evidence
-> IB3W weather / hydro context evidence
-> downstream gates / behavior / radar / THCI experiments

IB3W is not itself:

- route risk
- terrain risk
- radar score
- THCI
- behavior analysis
- medical diagnosis
- final hiking risk score

## Current Contract Stack

Existing contracts:

- docs/ib3w_weather_observation_availability_contract_v1.md
- runs/ib3w_environment_feature_contract_v1_20260613.md
- configs/weather_context/ib3w_weather_context_schema_v1.csv
- configs/weather_context/ib3w_environment_window_status_policy_v1.csv

New integration index:

- configs/weather_context/ib3w_weather_time_effect_semantics_v1.csv
- docs/ib3w_weather_time_effect_semantics_v1.md

## Current Evidence Layers

Recent weather-context layers include:

- antecedent precipitation context
- surface wetness proxy
- sunshine drying context
- fog / low-cloud proxy
- wet-cold exposure context
- heat / humid stress context
- heat / humid route-window context
- route-window weather context summary report
- weather time-effect semantics index

## Route-window Weather Context Summary

Commit:

- db893eb Add IB3W route-window weather context summary report

Output root:

- outputs/ib3w_route_window_weather_context_summary_report_v1/

Key result:

- route_window_rows = 16
- temperature increased along activity route/time
- relative humidity decreased along activity route/time
- wind speed slightly increased along activity route/time
- heat index was not computed because threshold/source support was not met
- zero_fallback_true_total = 0

Interpretation:

This is route-window environmental background. It is not final heat risk.

## Time-effect Semantics Index

Commit:

- 3e07da1 Add IB3W weather time-effect semantics index

Output root:

- outputs/ib3w_weather_time_effect_semantics_index_v1/

Purpose:

Classify weather/environment signals by how they relate to time.

Main classes:

- near-real-time state
- short-interval summary
- interval accumulation or observed rain signal ending at observation time
- antecedent lookback context
- delayed-response proxy
- not-observed proxy-only context
- unavailable direct observation fields

## Critical Interpretation Examples

Temperature / humidity:

- may be route-window background when hiker passed the segment
- must not become medical diagnosis

Mean wind:

- may be station-level wind background
- must not become route-point gust or terrain-shielded wind claim

Precipitation:

- is an observed rain signal associated with observation time
- must not be treated as instantaneous current rain
- must not be treated as cumulative rainfall unless source semantics prove it

Antecedent rain:

- is lookback background
- may support conservative wetness / hydrologic proxy review
- must not directly claim observed wet trail, soil moisture, stream surge, or slope instability

Surface wetness / hydrologic response:

- are delayed-response proxies unless direct evidence exists
- must remain review-only if direct observation is unavailable

Water level:

- if introduced later, water level itself is near-real-time hydrologic state
- elevated water level must not imply rain occurred at the same route-window time

## Mandatory Rules

- Missing remains missing.
- Observed zero remains observed zero.
- Missing-to-zero fallback is forbidden.
- Weather context is optional contextual evidence.
- Weather context is not THCI.
- Weather context is not final hiking risk.
- Proxy-only fields must carry explicit claim boundaries.
- Direct WBGT, UV, sunshine, visibility, weather text, gust, 10-minute rain, and 1-hour rain claims remain unsupported by the current DB.

## Recommended Next Step

This branch should close documentation only.

Do not introduce new model logic here.

After this closeout, future scripts should reference:

- ib3w_weather_time_effect_semantics_v1.csv

when emitting route-window, wetness, hydrologic, heat/humid, or wet-cold boundary fields.
