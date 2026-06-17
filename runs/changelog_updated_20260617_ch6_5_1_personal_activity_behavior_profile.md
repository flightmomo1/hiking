# Changelog update — 2026-06-17 — CH6.5.1 personal activity behavior profile v1.1

Added CH6.5.1 personal/activity-group behavior profile evidence.

New script:

- `scripts/make_ch6_5_1_personal_activity_behavior_profile_v1_1.py`

New output root:

- `outputs/report_figures/ch6_5_1_personal_activity_behavior_profile_v1_1`

Latest run result:

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

Notes:

v1.1 supersedes v1 because it adds recovered route-context phase from signed `calibrated_slope_pct_median`.

Recovered phases:

- `UPHILL_ROUTE_CONTEXT`
- `DOWNHILL_ROUTE_CONTEXT`
- `LOW_SLOPE_OR_MIXED_ROUTE_CONTEXT`
- `SLOPE_MISSING_REVIEW_REQUIRED`

`SLOPE_MISSING_REVIEW_REQUIRED` is retained and not imputed.

Boundary:

This is descriptive evidence only. No ability score, ability rank, ability class, THCI score, radar score, final hiking risk score, route suitability score, go/no-go decision, medical diagnosis, or causality inference is generated.
