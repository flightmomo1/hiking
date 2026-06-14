# IB3W Weather Context Consumption Gate Policy v1

## Purpose

This document defines how downstream layers are allowed to consume IB3W weather / hydro context evidence.

The consumption gate is not a scoring model.

It does not compute:

- THCI
- final radar score
- final hiking risk score
- medical diagnosis
- behavior interpretation

It only decides whether weather context evidence may be consumed as:

- context-only evidence;
- proxy / review-only evidence;
- blocked evidence.

## Upstream contracts

This gate depends on the existing IB3W contract stack:

- `docs/ib3w_weather_observation_availability_contract_v1.md`
- `runs/ib3w_environment_feature_contract_v1_20260613.md`
- `configs/weather_context/ib3w_weather_context_schema_v1.csv`
- `configs/weather_context/ib3w_environment_window_status_policy_v1.csv`
- `configs/weather_context/ib3w_weather_time_effect_semantics_v1.csv`
- `docs/ib3w_weather_time_effect_semantics_v1.md`

## Gate outputs

The gate uses the following consumption decisions:

| consumption_gate | Meaning |
|---|---|
| `ALLOW_CONTEXT_ONLY` | Observed weather variables may be consumed as context evidence only. |
| `ALLOW_PROXY_REVIEW_ONLY` | Proxy or time-effect-derived context may be shown as review-only evidence with explicit boundary fields. |
| `BLOCK_SCORE_WEATHER_UNAVAILABLE` | Weather evidence is unavailable; downstream score consumption must be blocked. |
| `BLOCK_SCORE_ZERO_FALLBACK` | Zero fallback was detected; weather context consumption must be blocked. |
| `BLOCK_SCORE_UNSUPPORTED_DIRECT_CLAIM` | A direct claim is unsupported by available source evidence; downstream consumption must be blocked. |

## Core rule

IB3W is the Weather / Hydro Context Evidence Layer.

It is not itself:

- route risk;
- THCI;
- final radar score;
- final hiking risk score;
- medical diagnosis;
- behavior analysis.

Downstream layers may consume IB3W only after passing the appropriate consumption gate.

## Allowed consumption

### Observed direct context

If representative weather features are available and `zero_fallback_true_count = 0`, downstream consumers may use observed variables as context evidence only.

Allowed:

- report observed temperature context;
- report observed relative humidity context;
- report observed mean wind context;
- report observed precipitation signal context;
- preserve missing variables as missing.

Not allowed:

- compute final weather-sensitive score directly from this gate;
- infer missing variables;
- treat missing weather as normal weather.

### Partial observed variables

If some variables are available and others are missing, downstream may consume only the available variables.

Allowed:

- consume `available_weather_variable_set`;
- preserve `missing_weather_variable_set`.

Not allowed:

- fill missing variables;
- treat partial data as full data.

### Proxy-only contexts

Proxy-only contexts may be consumed only as review-only evidence.

Examples:

- surface wetness proxy;
- fog / low-cloud proxy;
- wet-cold proxy;
- heat / humid proxy when thresholds or source support are limited;
- hydrologic response proxy.

Required:

- explicit `time_effect_type`;
- explicit direct-observation status;
- explicit claim-boundary field.

Not allowed:

- claim direct observation;
- compute final risk directly from proxy evidence.

## Blocking conditions

### No representative weather rows

If representative station rows are unavailable, downstream score consumption must be blocked.

Reason:

No weather evidence is not normal weather.

### All primary rows missing

If primary rows exist but all relevant values are missing, downstream score consumption must be blocked.

Reason:

All missing evidence must remain missing.

### Zero fallback detected

If `zero_fallback_true_count > 0`, downstream consumption must be blocked.

Reason:

Missing-to-zero fallback invalidates weather context evidence.

### Unsupported direct claim

If a script claims direct WBGT, UV, sunshine, visibility, weather text, gust, short-duration rain, heat illness, THCI, or final risk without supported source evidence, downstream consumption must be blocked.

Reason:

Unsupported direct claims must not propagate.

## Time-effect gate interpretation

The gate must respect time-effect semantics.

### Near-real-time state

Examples:

- temperature;
- relative humidity;
- mean wind;
- pressure when station-specific availability exists.

Allowed:

- route-window environmental background.

Not allowed:

- medical diagnosis;
- final risk score.

### Interval accumulation or observed rain signal

Example:

- raw `precipitation_mm`.

Allowed:

- recent rain context;
- antecedent precipitation support.

Not allowed:

- claim current rain at `obs_time`;
- claim rain intensity without source interval support.

### Antecedent lookback context

Examples:

- 6h rain lookback;
- 24h rain lookback;
- 72h rain lookback;
- 7d rain lookback;
- hours since last observed rain.

Allowed:

- preceding weather background;
- conservative support for delayed-effect proxy review.

Not allowed:

- direct current rain claim;
- direct wet trail claim;
- direct soil moisture claim;
- direct stream surge claim;
- direct slope instability claim.

### Delayed-response proxy

Examples:

- surface wetness proxy;
- hydrologic response proxy.

Allowed:

- review-only context.

Not allowed:

- direct observation claim;
- unsafe crossing claim without direct hydrologic evidence;
- final risk score.

## Machine-readable policy

The machine-readable policy is:

- `configs/weather_context/ib3w_weather_context_consumption_gate_policy_v1.csv`

## THCI / radar version boundary

This gate is independent of THCI formula versions.

If THCI or radar changes scoring weights, scoring formulas, display axes, or downstream aggregation rules, this gate does not need to change unless the weather-context consumption authorization changes.

This gate should change only when:

- downstream THCI / radar requires a new IB3W weather input type;
- a proxy-only context becomes authorized for formal scoring;
- missing-weather consumption rules change;
- a new external weather / hydro source makes an unsupported direct observation field supported.

In short:

THCI formula change does not automatically imply IB3W consumption gate change.

Only weather-context consumption rule change implies IB3W consumption gate review.

## Documentation boundary

This policy is a gate contract.

It does not add new weather observations.
It does not mutate the weather database.
It does not authorize final THCI, radar, or hiking risk scoring.

