# README Current Pipeline - CH6.5.5 Personal Ability Radar Axis Contract v1

## Component

CH6.5.5 personal ability radar axis contract v1.

## Script

`scripts/make_ch6_5_5_personal_ability_radar_axis_contract_v1.py`

## Outputs

Output root:

`outputs/report_figures/ch6_5_5_personal_ability_radar_axis_contract_v1`

Files:

- `personal_ability_radar_axis_contract_v1.csv`
- `personal_ability_radar_axis_evidence_inventory_v1.csv`
- `personal_ability_radar_axis_contract_audit_v1.csv`
- `personal_ability_radar_axis_contract_report_v1.html`

## Purpose

This component consolidates completed evidence layers into a radar-axis governance contract.

It defines:

- which axes may appear in a future personal hiking ability radar chart
- whether an axis may be numeric, proxy, descriptive-only, or missing-evidence
- which evidence sources support each axis
- which consumption gates are required
- which uses are explicitly disallowed

## Current Contract Summary

- Candidate axes: 11
- Numeric axes: 0
- Limited proxy axes: 2
- Descriptive annotation axes: 5
- Missing evidence annotation axes: 4
- Evidence inventory found: 12 / 12

## Contract Boundary

This is not a scoring layer.

It must not compute or authorize:

- radar scores
- ability scores
- ability ranks
- ability classes
- THCI scores
- final hiking risk scores
- route suitability scores
- go/no-go decisions
- medical diagnoses
- causality claims

Missing evidence must remain missing / insufficient evidence. Do not zero-fill missing evidence.
