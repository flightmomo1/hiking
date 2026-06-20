# Latest Handoff Prompt - CH6.5.5 Personal Ability Radar Data Table v1

Continue from:

`D:\mountain_work\115_osm`

Current completed branch:

`codex/ch6-5-5-personal-ability-radar-data-table-v1`

Latest commit:

`e05d70e Add CH6.5.5 personal ability radar data table`

The branch has been pushed to origin.

## Completed Work

Built the first governed personal ability radar data table.

Main script:

`scripts/make_ch6_5_5_personal_ability_radar_data_table_v1.py`

Output root:

`outputs/report_figures/ch6_5_5_personal_ability_radar_data_table_v1`

Key outputs:

- `personal_ability_radar_data_table_v1.csv`
- `personal_ability_radar_data_table_audit_v1.csv`
- `personal_ability_radar_data_table_report_v1.html`

## Current Data Table State

- Activity count: 26
- Axis count: 11
- Rows: 286
- Numeric axis rows: 0
- Limited proxy axis rows: 52
- Limited proxy value rows: 50
- Descriptive annotation rows: 130
- Missing evidence annotation rows: 104
- Audit: PASS

## Important Rules Preserved

- `MISSING_EVIDENCE_ANNOTATION` is not zero-filled.
- `DESCRIPTIVE_ANNOTATION` does not carry hidden numeric values.
- `LIMITED_PROXY_AXIS` is explicitly labeled as proxy.
- Extra source activity `6_1` is blocked by baseline population gate.

## Recommended Next Branch

`codex/ch6-5-5-personal-ability-radar-plot-v1`

## Recommended Next Task

Build a governed radar preview.

The plot should:

- only draw `LIMITED_PROXY_AXIS` rows where `axis_value_allowed=True`
- show descriptive annotations separately
- show missing evidence reasons separately
- clearly label proxy axes
- avoid presenting the figure as a formal ability-score radar chart
