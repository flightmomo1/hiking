# CURRENT INDEX - IB3W Weather Context Consumption Gate

Date: 2026-06-14

## Current branch

- codex/ib3w-weather-context-consumption-gate-v1

## Current commit

- e0019fd Add IB3W weather context consumption gate policy

## Role

This branch adds the current IB3W downstream consumption gate policy.

The policy defines whether weather context evidence may be consumed by downstream modules.

It does not calculate scores.

## Active artifacts

Machine-readable policy:

- configs/weather_context/ib3w_weather_context_consumption_gate_policy_v1.csv

Human-readable policy:

- docs/ib3w_weather_context_consumption_gate_policy_v1.md

Evidence outputs:

- outputs/ib3w_weather_context_consumption_gate_policy_v1/ib3w_weather_context_consumption_gate_policy_v1.csv
- outputs/ib3w_weather_context_consumption_gate_policy_v1/ib3w_weather_context_consumption_gate_policy_v1.md
- outputs/ib3w_weather_context_consumption_gate_policy_v1/ib3w_weather_context_consumption_gate_policy_summary_v1.csv

## Gate vocabulary

- ALLOW_CONTEXT_ONLY
- ALLOW_PROXY_REVIEW_ONLY
- BLOCK_SCORE_WEATHER_UNAVAILABLE
- BLOCK_SCORE_ZERO_FALLBACK
- BLOCK_SCORE_UNSUPPORTED_DIRECT_CLAIM

## Gate meaning

ALLOW_CONTEXT_ONLY means observed weather variables may be used as context evidence only.

ALLOW_PROXY_REVIEW_ONLY means proxy or delayed-response context may be used only as review-only evidence.

BLOCK_SCORE_WEATHER_UNAVAILABLE means weather evidence is unavailable and downstream score use must be blocked.

BLOCK_SCORE_ZERO_FALLBACK means missing-to-zero fallback was detected and downstream consumption must be blocked.

BLOCK_SCORE_UNSUPPORTED_DIRECT_CLAIM means a direct weather / risk claim is unsupported and must not propagate.

## Summary counts

- gate_row_count = 11
- ALLOW_CONTEXT_ONLY = 2
- ALLOW_PROXY_REVIEW_ONLY = 4
- BLOCK_SCORE_WEATHER_UNAVAILABLE = 2
- BLOCK_SCORE_ZERO_FALLBACK = 1
- BLOCK_SCORE_UNSUPPORTED_DIRECT_CLAIM = 2

## Upstream dependencies

The gate depends on the existing IB3W contracts:

- weather observation availability contract
- representative environment feature contract
- weather context schema
- environment window status policy
- weather time-effect semantics index

## Boundary

This gate does not authorize:

- THCI
- radar score
- final hiking risk
- medical diagnosis
- behavior interpretation
- route risk scoring

## THCI / radar version boundary

This gate is independent of THCI formula versions.

THCI or radar formula changes do not automatically require IB3W gate changes.

IB3W gate changes are required only when downstream weather-context consumption authorization changes.

## Current recommendation

Treat e0019fd as the current IB3W consumption-gate policy commit.

Do not allow downstream scoring modules to consume IB3W weather context unless the gate status allows the specific use.
