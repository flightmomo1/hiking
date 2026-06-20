# README Current Pipeline - CH6.5.5 Route-Following Radar v1.1

## Component

CH6.5.5 route-following radar v1.1 closure.

This is a documentation-level pipeline record for the governed limited proxy radar preview that includes `route_following_stability`.

## Pipeline Chain

```text
route-following proxy admission
-> axis contract patch
-> data table patch
-> personal ability radar plot v1.1
```

## 1. Route-Following Proxy Admission

Branch:

`codex/ch6-5-5-route-following-stability-proxy-v1`

Commit:

`257ec4a Add CH6.5.5 route following stability proxy admission`

Output root:

`outputs/report_figures/ch6_5_5_route_following_stability_proxy_admission_v1_1`

Audit conclusion:

`PASS_CH6_5_5_ROUTE_FOLLOWING_STABILITY_PROXY_ADMISSION_V1_1_GOVERNED_LIMITED_PROXY_CANDIDATE`

Key result:

- Baseline detector coverage: 25/25.
- 18 baseline activities have mid-activity route issue burden.
- 7 baseline activities have only `terminal_artifact`, so they are detector-covered and not missing evidence.
- Extra source `6_1` is blocked.

## 2. Axis Contract Patch

Branch:

`codex/ch6-5-5-route-following-axis-contract-patch-v1`

Commit:

`fdccb57 Add CH6.5.5 route following axis contract patch`

Output root:

`outputs/report_figures/ch6_5_5_route_following_axis_contract_patch_v1`

Key result:

- `route_following_stability` was upgraded from `MISSING_EVIDENCE_ANNOTATION` to `LIMITED_PROXY_AXIS`.
- `deviation_correction_ability` remained `MISSING_EVIDENCE_ANNOTATION`.
- `limited_proxy_axis_count = 3`.
- `numeric_axis_count = 0`.

## 3. Data Table Patch

Branch:

`codex/ch6-5-5-route-following-data-table-patch-v1`

Commit:

`9e74c05 Add CH6.5.5 route following data table patch`

Output root:

`outputs/report_figures/ch6_5_5_route_following_data_table_patch_v1`

Primary data table:

`outputs/report_figures/ch6_5_5_route_following_data_table_patch_v1/personal_ability_radar_data_table_v1_1.csv`

Key result:

- `row_count = 286`
- `activity_count = 26`
- `axis_count = 11`
- `limited_proxy_axis_row_count = 78`
- `limited_proxy_axis_value_count = 75`
- `route_following_baseline_value_count = 25`
- `route_following_extra_source_value_count = 0`
- `zero_fill_used = False`

## 4. Radar Plot v1.1

Branch:

`codex/ch6-5-5-personal-ability-radar-plot-v1-1`

Commit:

`16a9b24 Add CH6.5.5 personal ability radar plot v1.1`

Output root:

`outputs/report_figures/ch6_5_5_personal_ability_radar_plot_v1_1`

Key outputs:

- `personal_ability_radar_plot_ready_table_v1_1.csv`
- `personal_ability_radar_plot_index_v1_1.csv`
- `personal_ability_radar_annotation_summary_v1_1.csv`
- `personal_ability_radar_plot_audit_v1_1.csv`
- `personal_ability_radar_plot_report_v1_1.html`
- `plots/personal_ability_radar_preview_<activity_id>_v1_1.png`

Key result:

- `plotted_baseline_activity_count = 25`
- `plotted_extra_source_activity_count = 0`
- `limited_proxy_axis_count = 3`
- `plotted_axis_count_per_baseline_activity_min = 3`
- `plotted_axis_count_per_baseline_activity_max = 3`
- `generated_plot_count = 25`

Audit conclusion:

`PASS_CH6_5_5_PERSONAL_ABILITY_RADAR_PLOT_V1_1_GOVERNED_LIMITED_PROXY_PREVIEW`

## Current Limited Proxy Axes

- `terrain_movement_efficiency`
- `pacing_movement_stability`
- `route_following_stability`

## Governance Rules

- The radar v1.1 output is a governed limited proxy radar preview.
- It is not a formal ability score, ability rank, or ability class.
- It does not produce a THCI score, final hiking risk score, route suitability score, go/no-go decision, medical diagnosis, or causality claim.
- Only `LIMITED_PROXY_AXIS` rows with admitted values may be plotted.
- `DESCRIPTIVE_ANNOTATION` rows remain annotation-only.
- `MISSING_EVIDENCE_ANNOTATION` rows remain missing evidence and must not be zero-filled.
- `route_following_stability` is a limited proxy axis only.
- `deviation_correction_ability` remains blocked until a formal deviation-start -> correction/rejoin event-chain review exists.
- Extra source `6_1` is not included in baseline plot output.

## Do Not Infer

Do not infer `deviation_correction_ability` from route issue keywords alone.

Do not convert the preview into:

- ability score
- ability rank
- ability class
- THCI score
- final hiking risk score
- route suitability score
- go/no-go decision
- medical diagnosis
- causality claim
