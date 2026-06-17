# Chapter 6.5 single-activity profile v2.2.7 speed threshold pause focus run report: 42_1

- route_input_csv: `D:\mountain_work\115_osm\outputs\ib2_v2_route_risk_v1_3b_contract_qa\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b_route_risk_v2.csv`
- behavior_input_csv: `D:\mountain_work\115_osm\outputs\ib3_personal_hiking_features_route_load_comparison_full25_v1\activity_route_load_behavior_response_windows.csv`
- output_directory: `D:\mountain_work\115_osm\outputs\report_figures\ch6_single_activity_surface_profiles_v2_2_7_ib3d_review_safe_status\activity_42_1`
- profile_row_count: 4188
- selected_activity_behavior_summary_row_count: 84
- event_marker_count: 44
- ib3d_event_marker_count: 12
- shelter_context_zone_count: 2
- shelter_raw_proximity_run_count: 4
- shelter_zone_merge_gap_m: 120.0
- speed_plot_cap_mps: 2.5
- low_speed_threshold_mps: 0.7
- low_speed_threshold_visual_only: True
- ib3d_short_pause_band_alpha: 0.18
- audit_conclusion: `PASS_CH6_5_SINGLE_ACTIVITY_SURFACE_PROFILE_V2_2_5_SPEED_THRESHOLD_PAUSE_FOCUS`

## Audit fields

- route_input_csv: `D:\mountain_work\115_osm\outputs\ib2_v2_route_risk_v1_3b_contract_qa\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b_route_risk_v2.csv`
- behavior_input_csv: `D:\mountain_work\115_osm\outputs\ib3_personal_hiking_features_route_load_comparison_full25_v1\activity_route_load_behavior_response_windows.csv`
- activity_id_short: `42_1`
- available_activity_count_in_behavior_csv: `25`
- selected_activity_input_row_count: `84`
- selected_activity_behavior_summary_row_count: `84`
- behavior_bin_m: `50`
- low_speed_threshold_mps: `0.7`
- low_speed_threshold_visual_only: `True`
- ib3d_short_pause_band_alpha: `0.18`
- route_1m_row_count: `4188`
- route_distance_max_m: `4187`
- surface_unknown_other_count: `0`
- route_1m_source_match_missing_count: `0`
- route_1m_source_match_max_offset_m: `0.0`
- slope_source: `slope_pct`
- slope_missing_count: `0`
- route_phase_unknown_row_count_for_selected_activity: `84`
- event_marker_count: `44`
- shelter_context_zone_count: `2`
- shelter_raw_proximity_run_count: `4`
- rest_candidate_count: `18`
- weather_zero_fill_performed_count: `0`
- legacy_gain_field_used_count: `0`
- score_rank_class_generated_count: `0`
- prohibited_generated_columns: ``
- audit_conclusion: `PASS_CH6_5_SINGLE_ACTIVITY_SURFACE_PROFILE_V2_2_5_SPEED_THRESHOLD_PAUSE_FOCUS`

## Outputs

- `D:\mountain_work\115_osm\outputs\report_figures\ch6_single_activity_surface_profiles_v2_2_7_ib3d_review_safe_status\activity_42_1\ch6_5_single_activity_surface_profile_42_1_v2_2_7_ib3d_review_safe_status.png`
- `D:\mountain_work\115_osm\outputs\report_figures\ch6_single_activity_surface_profiles_v2_2_7_ib3d_review_safe_status\activity_42_1\ch6_5_single_activity_surface_profile_42_1_v2_2_7_ib3d_review_safe_status.csv`
- `D:\mountain_work\115_osm\outputs\report_figures\ch6_single_activity_surface_profiles_v2_2_7_ib3d_review_safe_status\activity_42_1\ch6_5_single_activity_surface_profile_42_1_v2_2_7_ib3d_review_safe_status_shelter_context_zones.csv`
- `D:\mountain_work\115_osm\outputs\report_figures\ch6_single_activity_surface_profiles_v2_2_7_ib3d_review_safe_status\activity_42_1\ch6_5_single_activity_surface_profile_42_1_v2_2_7_ib3d_review_safe_status.md`
- `D:\mountain_work\115_osm\outputs\report_figures\ch6_single_activity_surface_profiles_v2_2_7_ib3d_review_safe_status\activity_42_1\ch6_5_single_activity_surface_profile_42_1_v2_2_7_ib3d_review_safe_status_run_report.md`

## Main-figure decision

- Main panel order: spatial background, slope, heart rate, speed, low/stopped point ratios.
- Behavior panels intentionally omit route_load_context_band shading so shelter context zones remain visually unambiguous.
- This is a selected-activity figure, not a cross-activity summary.
