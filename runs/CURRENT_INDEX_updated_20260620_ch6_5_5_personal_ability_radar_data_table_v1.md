# CURRENT INDEX - CH6.5.5 Personal Ability Radar Data Table v1

## Status

Current branch:

`codex/ch6-5-5-personal-ability-radar-data-table-v1`

Latest committed result:

`e05d70e Add CH6.5.5 personal ability radar data table`

Upstream axis contract branch:

`codex/ch6-5-5-personal-ability-radar-axis-contract-v1`

Upstream axis contract commit:

`49adf55 Document CH6.5.5 personal ability radar axis contract`

## Current Effective Component

Script:

`scripts/make_ch6_5_5_personal_ability_radar_data_table_v1.py`

Input contract root:

`outputs/report_figures/ch6_5_5_personal_ability_radar_axis_contract_v1`

Output root:

`outputs/report_figures/ch6_5_5_personal_ability_radar_data_table_v1`

Primary output:

`personal_ability_radar_data_table_v1.csv`

## Data Table Summary

- Activity count: 26
- Axis count: 11
- Data table rows: 286
- Numeric axis rows: 0
- Limited proxy axis rows: 52
- Limited proxy value rows: 50
- Descriptive annotation rows: 130
- Missing evidence annotation rows: 104

## Governance Checks

- `DESCRIPTIVE_ANNOTATION` rows do not carry numeric values.
- `MISSING_EVIDENCE_ANNOTATION` rows do not carry numeric values.
- Missing evidence is not zero-filled.
- Extra source activity `6_1` is explicitly marked as `EXTRA_SOURCE_ACTIVITY_NOT_IN_RADAR_BASELINE`.
- Extra source proxy rows are blocked by `baseline_population_gate=BLOCKED_EXTRA_SOURCE`.

Audit conclusion:

`PASS_CH6_5_5_PERSONAL_ABILITY_RADAR_DATA_TABLE_V1_GOVERNED_TABLE_ONLY`

## Boundary

This data table does not compute or authorize radar scores, ability scores, ranks, classes, THCI scores, final hiking risk scores, route suitability scores, go/no-go decisions, medical diagnoses, or causality claims.

## Recommended Next Step

Proceed to:

`codex/ch6-5-5-personal-ability-radar-plot-v1`

The plot must be a governed preview using limited proxy axes plus annotations, not a formal ability-score radar chart.
