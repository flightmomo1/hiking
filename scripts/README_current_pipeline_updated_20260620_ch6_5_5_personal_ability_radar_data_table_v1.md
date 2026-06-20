# README Current Pipeline - CH6.5.5 Personal Ability Radar Data Table v1

## Component

CH6.5.5 personal ability radar data table v1.

## Script

`scripts/make_ch6_5_5_personal_ability_radar_data_table_v1.py`

## Inputs

Axis contract root:

`outputs/report_figures/ch6_5_5_personal_ability_radar_axis_contract_v1`

Required input files:

- `personal_ability_radar_axis_contract_v1.csv`
- `personal_ability_radar_axis_contract_audit_v1.csv`

Supporting evidence inputs are resolved from completed evidence layers.

## Outputs

Output root:

`outputs/report_figures/ch6_5_5_personal_ability_radar_data_table_v1`

Output files:

- `personal_ability_radar_data_table_v1.csv`
- `personal_ability_radar_data_table_audit_v1.csv`
- `personal_ability_radar_data_table_report_v1.html`

## Purpose

This component converts the radar axis contract plus activity/person evidence into a governed radar data table.

It is the data contract for future visualization.

## Current Result

- Activities: 26
- Axes: 11
- Rows: 286
- Numeric axes: 0
- Limited proxy axis rows: 52
- Limited proxy values: 50
- Descriptive annotation rows: 130
- Missing evidence annotation rows: 104

## Governance Rules

- `NUMERIC_AXIS` may carry numeric values, but currently there are no numeric axes.
- `LIMITED_PROXY_AXIS` may carry proxy values only with explicit proxy labeling.
- `DESCRIPTIVE_ANNOTATION` must not carry numeric values.
- `MISSING_EVIDENCE_ANNOTATION` must not carry numeric values and must not be zero-filled.
- Extra source rows must not enter formal baseline proxy output.

## Contract Boundary

This is not a scoring layer and not a radar plot layer.

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
