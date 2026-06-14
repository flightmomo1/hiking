# CURRENT INDEX - IB3M Weather Context Gate Consumer Smoke

Date: 2026-06-14

## Current branch

- codex/ib3m-weather-context-gate-consumer-smoke-v1

## Current commit

- ee3e316 Add IB3M weather context gate consumer smoke

## Role

This branch verifies that downstream IB3M / THCI / radar-style consumers must honor the IB3W weather context gate.

It is a smoke test.

It is not a scoring model.

## Active implementation

Script:

- scripts/ib3_activity_environment/ib3m_weather_context_gate_consumer_smoke_v1.py

Inputs:

- outputs/ib3w_weather_context_consumption_gate_validator_v1/activity_weather_context_consumption_gate.csv
- outputs/ib3w_weather_context_consumption_gate_validator_v1/activity_weather_context_consumption_gate_summary.csv

Outputs:

- outputs/ib3m_weather_context_gate_consumer_smoke_v1/ib3m_weather_context_gate_consumer_smoke_results.csv
- outputs/ib3m_weather_context_gate_consumer_smoke_v1/ib3m_weather_context_gate_consumer_smoke_summary.csv

## Current result

The current smoke result is:

- activity_count = 27
- smoke_pass_count = 27
- smoke_fail_count = 0
- BLOCK_SCORE_WEATHER_UNAVAILABLE = 26
- ALLOW_CONTEXT_ONLY = 1
- REFUSE_SCORE_CONSUMPTION = 26
- ALLOW_NON_SCORING_CONTEXT_ONLY = 1
- downstream_score_allowed_violation_count = 0
- thci_authorization_violation_count = 0
- radar_authorization_violation_count = 0
- final_hiking_risk_authorization_violation_count = 0
- consumer_smoke_conclusion = PASS

## Consumer rule

BLOCK_SCORE_WEATHER_UNAVAILABLE rows must not enter score consumers.

ALLOW_CONTEXT_ONLY rows may be passed only as non-scoring context.

No current row is authorized for THCI, radar, final hiking risk, or medical diagnosis.

## Boundary

This smoke test does not authorize:

- THCI
- radar score
- final hiking risk
- medical diagnosis
- behavior interpretation
- route risk scoring

## Current recommendation

Treat ee3e316 as the current consumer smoke implementation commit.

Downstream integration should consume IB3W validator gate outputs before considering weather context.
