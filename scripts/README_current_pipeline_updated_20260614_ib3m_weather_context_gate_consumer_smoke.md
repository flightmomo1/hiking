# README Update - IB3M Weather Context Gate Consumer Smoke

Date: 2026-06-14

## Current smoke status

Current branch:

- codex/ib3m-weather-context-gate-consumer-smoke-v1

Current commit:

- ee3e316 Add IB3M weather context gate consumer smoke

## What this smoke test does

The smoke test verifies downstream consumer behavior for IB3W weather context gate outputs.

It checks that:

- BLOCK_SCORE_WEATHER_UNAVAILABLE rows refuse score consumption;
- ALLOW_CONTEXT_ONLY rows remain non-scoring context;
- THCI, radar, final hiking risk, and medical diagnosis are not authorized by the IB3W gate.

## Script

- scripts/ib3_activity_environment/ib3m_weather_context_gate_consumer_smoke_v1.py

## Inputs

- outputs/ib3w_weather_context_consumption_gate_validator_v1/activity_weather_context_consumption_gate.csv
- outputs/ib3w_weather_context_consumption_gate_validator_v1/activity_weather_context_consumption_gate_summary.csv

## Outputs

- outputs/ib3m_weather_context_gate_consumer_smoke_v1/ib3m_weather_context_gate_consumer_smoke_results.csv
- outputs/ib3m_weather_context_gate_consumer_smoke_v1/ib3m_weather_context_gate_consumer_smoke_summary.csv

## Current summary

- activity_count = 27
- smoke_pass_count = 27
- smoke_fail_count = 0
- block_weather_unavailable_count = 26
- allow_context_only_count = 1
- refuse_score_consumption_count = 26
- allow_non_scoring_context_only_count = 1
- downstream_score_allowed_violation_count = 0
- thci_authorization_violation_count = 0
- radar_authorization_violation_count = 0
- final_hiking_risk_authorization_violation_count = 0
- consumer_smoke_conclusion = PASS

## What this smoke test does not do

It does not compute:

- THCI
- radar score
- final hiking risk
- medical diagnosis
- behavior interpretation
- route risk

## Downstream rule

Downstream modules should not consume IB3W weather context directly.

They should first read validator gate outputs.

Blocked rows must not be scored.

Context-only rows must remain non-scoring context.

## Current implementation boundary

This smoke test validates downstream behavior only.

It is not a final scoring model.
