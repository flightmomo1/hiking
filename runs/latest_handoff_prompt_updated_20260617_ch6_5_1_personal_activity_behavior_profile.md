# Latest handoff prompt — CH6.5.1 personal activity behavior profile v1.1

Continue from:

- repository root: `D:\mountain_work\115_osm`
- branch: `codex/ch6-5-1-personal-activity-behavior-profile-v1`

Current CH6.5.1 package:

- script: `scripts/make_ch6_5_1_personal_activity_behavior_profile_v1_1.py`
- output root: `outputs/report_figures/ch6_5_1_personal_activity_behavior_profile_v1_1`

Latest audit:

- `PASS_CH6_5_1_PERSONAL_ACTIVITY_BEHAVIOR_PROFILE_V1_1_DESCRIPTIVE_ONLY`

Latest run summary:

- profile_id: `qixing_lengshuikeng_activity_group_full25`
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

Route phase recovery:

- `route_phase_original` is retained from input.
- `route_phase_for_profile` is recovered from signed `calibrated_slope_pct_median`.
- uphill threshold: `>= +3%`
- downhill threshold: `<= -3%`
- missing signed slope remains `SLOPE_MISSING_REVIEW_REQUIRED`.

Important boundary:

This package is descriptive evidence only. It must not be interpreted as ability scoring, ability ranking, ability classing, THCI, radar, final hiking risk, route suitability score, go/no-go decision, medical diagnosis, or causality result.

Recommended next step:

Proceed to CH6.5.2 weather-adjusted behavior context after this package is committed.
