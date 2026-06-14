# README Update - IB3W Weather Context Consumption Gate Validator

Date: 2026-06-14

## Current validator status

Current branch:

- codex/ib3w-weather-context-consumption-gate-validator-v1

Current commit:

- 23eb479 Add IB3W weather context consumption gate validator

## What this validator does

The validator reads representative IB3W weather-context feature rows and applies the consumption-gate policy.

It emits explicit authorization fields for downstream modules.

## Script

- scripts/ib3_activity_environment/ib3w_weather_context_consumption_gate_validator_v1.py

## Inputs

- configs/weather_context/ib3w_weather_context_consumption_gate_policy_v1.csv
- outputs/ib3w_representative_environment_features_v1/activity_representative_environment_features.csv

## Outputs

- outputs/ib3w_weather_context_consumption_gate_validator_v1/activity_weather_context_consumption_gate.csv
- outputs/ib3w_weather_context_consumption_gate_validator_v1/activity_weather_context_consumption_gate_summary.csv

## Current summary

- activity_count = 27
- ALLOW_CONTEXT_ONLY = 1
- BLOCK_SCORE_WEATHER_UNAVAILABLE = 26
- zero_fallback_true_count_total = 0
- downstream_score_allowed_count = 0
- thci_authorized_count = 0
- radar_authorized_count = 0
- final_hiking_risk_authorized_count = 0
- validator_conclusion = PASS_POLICY_PRESENT

## What this validator does not do

It does not compute:

- THCI
- radar score
- final hiking risk
- medical diagnosis
- behavior interpretation
- route risk

## Downstream rule

Downstream modules should use validator outputs rather than directly consuming representative IB3W feature rows.

Rows with BLOCK_SCORE_WEATHER_UNAVAILABLE must not be used for weather-sensitive scoring.

Rows with ALLOW_CONTEXT_ONLY may be displayed or passed as context evidence only.

No row is currently authorized for THCI, radar, or final hiking risk scoring.

## THCI / radar version boundary

THCI formula changes do not automatically imply IB3W validator changes.

IB3W validator review is required only if weather-context consumption authorization rules or representative feature schema change.

## Current implementation boundary

The validator is a gate validator.

It is not a final scoring model.
