# CURRENT INDEX - CH6.5.5 Route-Following Radar v1.1

## Status

Current documentation branch:

`codex/ch6-5-5-route-following-radar-v1-1-docs`

Base commit:

`16a9b24 Add CH6.5.5 personal ability radar plot v1.1`

This index documents the completed route-following radar v1.1 closure:

`route-following proxy admission -> axis contract patch -> data table patch -> governed limited proxy radar preview`

## Boundary

This is a governed limited proxy radar preview.

It is not a formal ability score, ability rank, or ability class. It does not produce a THCI score, final hiking risk score, route suitability score, go/no-go decision, medical diagnosis, or causality claim.

`route_following_stability` is admitted only as a `LIMITED_PROXY_AXIS`.

`deviation_correction_ability` remains `MISSING_EVIDENCE_ANNOTATION`. It still requires a formal deviation-start -> correction/rejoin event-chain review and must not be upgraded directly from route issue keywords.

Extra source activity `6_1` is blocked from baseline plot output.

## Closure Components

### 1. Route-Following Proxy Admission

Branch:

`codex/ch6-5-5-route-following-stability-proxy-v1`

Commit:

`257ec4a Add CH6.5.5 route following stability proxy admission`

Output root:

`outputs/report_figures/ch6_5_5_route_following_stability_proxy_admission_v1_1`

Audit:

`PASS_CH6_5_5_ROUTE_FOLLOWING_STABILITY_PROXY_ADMISSION_V1_1_GOVERNED_LIMITED_PROXY_CANDIDATE`

Key result:

- Baseline detector coverage: 25/25.
- 18 baseline activities have mid-activity route issue burden.
- 7 baseline activities have only `terminal_artifact`, so they are not missing evidence.
- Extra source `6_1` is blocked.

### 2. Axis Contract Patch

Branch:

`codex/ch6-5-5-route-following-axis-contract-patch-v1`

Commit:

`fdccb57 Add CH6.5.5 route following axis contract patch`

Output root:

`outputs/report_figures/ch6_5_5_route_following_axis_contract_patch_v1`

Key result:

- `route_following_stability` changed from `MISSING_EVIDENCE_ANNOTATION` to `LIMITED_PROXY_AXIS`.
- `deviation_correction_ability` stayed `MISSING_EVIDENCE_ANNOTATION`.
- `limited_proxy_axis_count = 3`.
- `numeric_axis_count = 0`.

### 3. Data Table Patch

Branch:

`codex/ch6-5-5-route-following-data-table-patch-v1`

Commit:

`9e74c05 Add CH6.5.5 route following data table patch`

Output root:

`outputs/report_figures/ch6_5_5_route_following_data_table_patch_v1`

Key result:

- `row_count = 286`
- `activity_count = 26`
- `axis_count = 11`
- `limited_proxy_axis_row_count = 78`
- `limited_proxy_axis_value_count = 75`
- `route_following_baseline_value_count = 25`
- `route_following_extra_source_value_count = 0`
- `zero_fill_used = False`

### 4. Radar Plot v1.1

Branch:

`codex/ch6-5-5-personal-ability-radar-plot-v1-1`

Commit:

`16a9b24 Add CH6.5.5 personal ability radar plot v1.1`

Output root:

`outputs/report_figures/ch6_5_5_personal_ability_radar_plot_v1_1`

Key result:

- `plotted_baseline_activity_count = 25`
- `plotted_extra_source_activity_count = 0`
- `limited_proxy_axis_count = 3`
- `plotted_axis_count_per_baseline_activity_min = 3`
- `plotted_axis_count_per_baseline_activity_max = 3`
- `generated_plot_count = 25`

## Current Effective Radar Preview Inputs

Data table:

`outputs/report_figures/ch6_5_5_route_following_data_table_patch_v1/personal_ability_radar_data_table_v1_1.csv`

Plot output root:

`outputs/report_figures/ch6_5_5_personal_ability_radar_plot_v1_1`

Audit:

`PASS_CH6_5_5_PERSONAL_ABILITY_RADAR_PLOT_V1_1_GOVERNED_LIMITED_PROXY_PREVIEW`

## Current Limited Proxy Axes

- `terrain_movement_efficiency`
- `pacing_movement_stability`
- `route_following_stability`

## Recommended Next Step

If continuing beyond v1.1, the next work should preserve the same governance boundary:

- keep `route_following_stability` labeled as limited proxy
- do not assign missing evidence as zero
- keep `deviation_correction_ability` blocked until formal deviation-start -> correction/rejoin event-chain review exists
- do not convert the preview into a score, rank, class, final risk score, route suitability score, or go/no-go decision
