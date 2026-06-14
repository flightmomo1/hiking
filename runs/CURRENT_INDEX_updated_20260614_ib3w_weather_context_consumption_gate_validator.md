# CURRENT INDEX - IB3W Weather Context Consumption Gate Validator

Date: 2026-06-14

## Current branch

- codex/ib3w-weather-context-consumption-gate-validator-v1

## Current commit

- 23eb479 Add IB3W weather context consumption gate validator

## Role

This branch implements the IB3W weather context consumption gate validator.

The validator applies the consumption-gate policy to representative IB3W weather features and emits downstream-consumption evidence.

## Active implementation

Script:

- scripts/ib3_activity_environment/ib3w_weather_context_consumption_gate_validator_v1.py

Inputs:

- configs/weather_context/ib3w_weather_context_consumption_gate_policy_v1.csv
- outputs/ib3w_representative_environment_features_v1/activity_representative_environment_features.csv

Outputs:

- outputs/ib3w_weather_context_consumption_gate_validator_v1/activity_weather_context_consumption_gate.csv
- outputs/ib3w_weather_context_consumption_gate_validator_v1/activity_weather_context_consumption_gate_summary.csv

## Current result

The current validator result is:

- activity_count = 27
- ALLOW_CONTEXT_ONLY = 1
- BLOCK_SCORE_WEATHER_UNAVAILABLE = 26
- zero_fallback_true_count_total = 0
- context_consumption_allowed_count = 1
- downstream_score_allowed_count = 0
- thci_authorized_count = 0
- radar_authorized_count = 0
- final_hiking_risk_authorized_count = 0
- medical_diagnosis_authorized_count = 0
- validator_conclusion = PASS_POLICY_PRESENT

## Gate meaning

ALLOW_CONTEXT_ONLY means observed weather variables may be consumed only as context evidence.

BLOCK_SCORE_WEATHER_UNAVAILABLE means weather evidence is unavailable and downstream score consumption must be blocked.

BLOCK_SCORE_ZERO_FALLBACK means missing-to-zero fallback was detected and downstream consumption must be blocked.

BLOCK_SCORE_UNSUPPORTED_DIRECT_CLAIM means a direct weather or risk claim is unsupported and must not propagate.

## Current interpretation

The validator confirms that 26 activities do not have primary representative weather rows.

Those rows are blocked from weather-score consumption.

The validator confirms that 1 activity has partial representative weather features.

That row is context-only and not score-authorized.

## Boundary

The validator does not authorize:

- THCI
- radar score
- final hiking risk
- medical diagnosis
- behavior interpretation
- route risk scoring

## Missingness rule

Missing remains missing.

Observed zero remains observed zero.

No missing weather value is imputed as zero.

## Current recommendation

Treat 23eb479 as the current IB3W validator implementation commit.

Downstream modules should consume the validator outputs instead of reading representative weather context directly.
