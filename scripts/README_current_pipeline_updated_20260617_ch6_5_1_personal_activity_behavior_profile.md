# README current pipeline update — CH6.5.1 personal activity behavior profile v1.1

## Scope

This update adds CH6.5.1 personal/activity-group behavior profile evidence.

Current script:

- `scripts/make_ch6_5_1_personal_activity_behavior_profile_v1_1.py`

Current output root:

- `outputs/report_figures/ch6_5_1_personal_activity_behavior_profile_v1_1`

## Role in pipeline

CH6.5.1 converts 50 m route-window activity behavior evidence into a descriptive activity-group behavior profile.

Current profile:

- `qixing_lengshuikeng_activity_group_full25`

The evidence supports descriptive comparison across:

- route-load context band
- recovered route-context phase
- speed response
- low-speed response
- stopped-window response
- heart-rate response
- route-load behavior candidate windows

## Route phase recovery

v1.1 recovers `route_phase_for_profile` from signed `calibrated_slope_pct_median`.

Recovery rule:

- `calibrated_slope_pct_median >= +3%` → `UPHILL_ROUTE_CONTEXT`
- `calibrated_slope_pct_median <= -3%` → `DOWNHILL_ROUTE_CONTEXT`
- otherwise → `LOW_SLOPE_OR_MIXED_ROUTE_CONTEXT`
- missing or unparsable signed slope → `SLOPE_MISSING_REVIEW_REQUIRED`

The original route phase is retained as `route_phase_original`.

## Latest audit result

- activity_count: 25
- window_row_count: 2054
- uphill_windows_n: 360
- downhill_windows_n: 498
- low_slope_or_mixed_windows_n: 120
- slope_missing_windows_n: 1076
- route_load_phase_profile_rows: 11
- phase_summary_rows: 4
- activity_summary_rows: 25
- band_summary_rows: 3
- source_files_available_n: 7
- source_files_expected_n: 7
- audit_conclusion: `PASS_CH6_5_1_PERSONAL_ACTIVITY_BEHAVIOR_PROFILE_V1_1_DESCRIPTIVE_ONLY`

## Boundary

This evidence is descriptive only.

It is not an ability score, ability rank, ability class, THCI score, radar score, final hiking risk score, route suitability score, go/no-go decision, medical diagnosis, or causality result.

Weather context is descriptive only. Missing weather is not zero-filled.

`SLOPE_MISSING_REVIEW_REQUIRED` is retained as a separate review phase and is not imputed.
