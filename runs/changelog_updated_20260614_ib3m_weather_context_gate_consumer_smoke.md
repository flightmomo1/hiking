# Changelog Update - IB3M Weather Context Gate Consumer Smoke

Date: 2026-06-14

## Added

Commit:

- ee3e316 Add IB3M weather context gate consumer smoke

Branch:

- codex/ib3m-weather-context-gate-consumer-smoke-v1

## Files added

- scripts/ib3_activity_environment/ib3m_weather_context_gate_consumer_smoke_v1.py
- outputs/ib3m_weather_context_gate_consumer_smoke_v1/ib3m_weather_context_gate_consumer_smoke_results.csv
- outputs/ib3m_weather_context_gate_consumer_smoke_v1/ib3m_weather_context_gate_consumer_smoke_summary.csv

## Purpose

Added a consumer smoke test for downstream IB3M / THCI / radar-style consumption of IB3W weather context gate outputs.

The smoke test verifies that blocked weather rows are refused by score consumers and that context-only rows remain non-scoring context.

## Inputs

- outputs/ib3w_weather_context_consumption_gate_validator_v1/activity_weather_context_consumption_gate.csv
- outputs/ib3w_weather_context_consumption_gate_validator_v1/activity_weather_context_consumption_gate_summary.csv

## Outputs

- ib3m_weather_context_gate_consumer_smoke_results.csv
- ib3m_weather_context_gate_consumer_smoke_summary.csv

## Result

The committed run produced:

- 27 total activities
- 27 smoke-pass rows
- 0 smoke-fail rows
- 26 REFUSE_SCORE_CONSUMPTION rows
- 1 ALLOW_NON_SCORING_CONTEXT_ONLY row
- 0 downstream score violations
- 0 THCI authorization violations
- 0 radar authorization violations
- 0 final hiking risk authorization violations
- PASS conclusion

## Boundary preserved

The smoke test does not compute:

- THCI
- radar
- final hiking risk
- medical diagnosis
- behavior interpretation
- route risk

## Status

This is a consumer smoke / evidence commit.

It validates downstream refusal behavior.

It does not modify production THCI, radar, or route-risk scripts.
