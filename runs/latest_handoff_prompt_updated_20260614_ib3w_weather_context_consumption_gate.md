# Latest Handoff Prompt - IB3W Weather Context Consumption Gate

Date: 2026-06-14

## Branch

Current branch:

- codex/ib3w-weather-context-consumption-gate-v1

Latest commit:

- e0019fd Add IB3W weather context consumption gate policy

Base commit:

- cbc577d Document IB3W weather time-effect closeout

## What was completed

This branch added the first formal IB3W downstream consumption gate policy.

The purpose is to prevent downstream layers from directly turning IB3W weather context evidence into THCI, radar, final hiking risk, or medical judgment without explicit authorization.

## Added files

- configs/weather_context/ib3w_weather_context_consumption_gate_policy_v1.csv
- docs/ib3w_weather_context_consumption_gate_policy_v1.md
- outputs/ib3w_weather_context_consumption_gate_policy_v1/ib3w_weather_context_consumption_gate_policy_v1.csv
- outputs/ib3w_weather_context_consumption_gate_policy_v1/ib3w_weather_context_consumption_gate_policy_v1.md
- outputs/ib3w_weather_context_consumption_gate_policy_v1/ib3w_weather_context_consumption_gate_policy_summary_v1.csv

## Gate decisions

The policy defines five downstream-consumption decisions:

- ALLOW_CONTEXT_ONLY
- ALLOW_PROXY_REVIEW_ONLY
- BLOCK_SCORE_WEATHER_UNAVAILABLE
- BLOCK_SCORE_ZERO_FALLBACK
- BLOCK_SCORE_UNSUPPORTED_DIRECT_CLAIM

## Evidence summary

The policy summary reports:

- gate_row_count = 11
- allow_context_only_count = 2
- allow_proxy_review_only_count = 4
- block_weather_unavailable_count = 2
- block_zero_fallback_count = 1
- block_unsupported_direct_claim_count = 2
- zero_fallback_policy_present = True
- weather_unavailable_policy_present = True
- proxy_review_policy_present = True
- final_score_boundary_present = True

## Core interpretation

IB3W remains a Weather / Hydro Context Evidence Layer.

It is not:

- THCI
- radar score
- final hiking risk
- medical diagnosis
- behavior interpretation
- route risk computation

Downstream layers must pass a consumption gate before using IB3W weather context.

## THCI / radar version boundary

This gate is independent of THCI formula versions.

If THCI or radar changes weights, formulas, display axes, or aggregation rules, this gate does not need to change unless the weather-context consumption authorization changes.

THCI formula change does not automatically imply IB3W consumption gate change.

Only weather-context consumption rule change implies IB3W consumption gate review.

## Missingness boundary

Missing remains missing.

Observed zero remains observed zero.

Missing weather values must not be imputed as zero.

If zero_fallback_true_count is greater than zero, downstream weather-context consumption must be blocked.

## Proxy boundary

Proxy-only contexts may be consumed only as review-only evidence.

Examples include:

- surface wetness proxy
- fog / low-cloud proxy
- wet-cold proxy
- heat / humid proxy when source support is limited
- hydrologic response proxy

Proxy evidence must not be presented as direct observation.

## Recommended next step

Do not immediately write scoring logic.

The next safe implementation step is a downstream adapter / validator that reads the representative IB3W feature outputs and emits gate status fields without computing THCI or final risk.
