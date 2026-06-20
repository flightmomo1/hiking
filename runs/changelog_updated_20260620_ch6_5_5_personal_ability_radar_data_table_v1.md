# Changelog - CH6.5.5 Personal Ability Radar Data Table v1

## 2026-06-20

Added the first governed personal ability radar data table.

## Added Script

`scripts/make_ch6_5_5_personal_ability_radar_data_table_v1.py`

## Added Output Root

`outputs/report_figures/ch6_5_5_personal_ability_radar_data_table_v1`

## Added Outputs

- `personal_ability_radar_data_table_v1.csv`
- `personal_ability_radar_data_table_audit_v1.csv`
- `personal_ability_radar_data_table_report_v1.html`

## Key Result

The axis contract has been converted into a per-activity, per-axis governed data table.

The table contains:

- `participant_id`
- `activity_id_short`
- `axis_id`
- `axis_output_mode`
- `axis_value_allowed`
- `axis_value`
- `axis_annotation`
- `evidence_source`
- `required_gate_status`
- `missing_evidence_reason`
- `interpretation_boundary`

## Governance Result

- Numeric axis rows: 0
- Limited proxy axis rows: 52
- Limited proxy value rows: 50
- Descriptive annotation value violations: 0
- Missing evidence value violations: 0
- Missing evidence zero-fill violations: 0

Audit:

`PASS_CH6_5_5_PERSONAL_ABILITY_RADAR_DATA_TABLE_V1_GOVERNED_TABLE_ONLY`

## Boundary

No radar score, ability score, rank, class, THCI score, final hiking risk score, route suitability score, go/no-go decision, medical diagnosis, or causality claim was produced.
