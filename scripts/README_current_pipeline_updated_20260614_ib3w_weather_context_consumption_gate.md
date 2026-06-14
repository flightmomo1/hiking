# README Update - IB3W Weather Context Consumption Gate

Date: 2026-06-14

## Current IB3W consumption gate status

The current IB3W weather-context consumption gate branch is:

- codex/ib3w-weather-context-consumption-gate-v1

Current commit:

- e0019fd Add IB3W weather context consumption gate policy

## What this layer does

The consumption gate defines how downstream modules may consume IB3W weather context evidence.

It distinguishes:

- observed context that may be shown as context-only evidence;
- proxy context that must remain review-only;
- unavailable weather evidence that must block score consumption;
- zero-fallback evidence that must block consumption;
- unsupported direct claims that must block consumption.

## What this layer does not do

This layer does not calculate:

- THCI
- radar score
- final hiking risk
- medical diagnosis
- behavior interpretation
- route risk

## Main policy files

- configs/weather_context/ib3w_weather_context_consumption_gate_policy_v1.csv
- docs/ib3w_weather_context_consumption_gate_policy_v1.md

## Evidence files

- outputs/ib3w_weather_context_consumption_gate_policy_v1/ib3w_weather_context_consumption_gate_policy_v1.csv
- outputs/ib3w_weather_context_consumption_gate_policy_v1/ib3w_weather_context_consumption_gate_policy_v1.md
- outputs/ib3w_weather_context_consumption_gate_policy_v1/ib3w_weather_context_consumption_gate_policy_summary_v1.csv

## Gate values

- ALLOW_CONTEXT_ONLY
- ALLOW_PROXY_REVIEW_ONLY
- BLOCK_SCORE_WEATHER_UNAVAILABLE
- BLOCK_SCORE_ZERO_FALLBACK
- BLOCK_SCORE_UNSUPPORTED_DIRECT_CLAIM

## Downstream rule

Downstream modules must not consume IB3W weather context as score input unless the gate explicitly allows the intended use.

Context-only evidence must remain context-only.

Proxy review-only evidence must remain review-only.

Blocked evidence must not be used for THCI, radar, final hiking risk, or medical diagnosis.

## THCI / radar version boundary

This gate is independent of THCI formula versions.

THCI formula changes do not automatically imply IB3W consumption gate changes.

IB3W gate review is needed only when weather-context consumption authorization changes.

## Current implementation boundary

This update is policy-first.

No scoring script was added.

No downstream score was computed.

No missing weather value was imputed as zero.
