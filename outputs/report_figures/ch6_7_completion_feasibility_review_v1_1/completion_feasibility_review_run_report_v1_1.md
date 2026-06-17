# CH6.7 Completion Feasibility Review v1.1 Run Report

## Summary

- fastest_activity: `33_1`
- slowest_activity: `48_1`
- min_completion_time: `109.3667`
- p25: `125.8167`
- median: `138.35`
- p75: `169.75`
- max: `192.7833`
- max_min_ratio: `1.7627239369936187`
- slowest_fastest_difference: `83.4166`
- all_reviewed_activities_completed: `True`

## Conclusion

- all_reviewed_activities_completed: `True`
- fastest_completion_time_min: `109.3667`
- median_completion_time_min: `138.35`
- slowest_completion_time_min: `192.7833`
- slowest_minus_fastest_min: `83.4166`
- slow_group_completed: `True`
- slow_group_early_checkpoint_passed: `True`
- slow_group_unrecoverable_delay_evidence: `False`
- early_checkpoint_recommended_interpretation: `EARLY_STATUS_CHECKPOINT_NOT_MANDATORY_TURNAROUND_POINT`
- route_level_feasibility_statement: `BASIC_PREPARED_HIKERS_COMPLETION_FEASIBLE`
- planning_statement: `COMPLETION_FEASIBLE_BUT_CONSERVATIVE_PLANNING_RECOMMENDED`
- weather_aware_interpretation: `SLOW_GROUP_COMPLETED_UNDER_LESS_FAVORABLE_WEATHER_SUPPORTS_BASIC_COMPLETION_FEASIBILITY`
- hr_context_available_count: `25`
- slow_group_hr_context_available: `True`
- slow_group_high_hr_effort_evidence: `True`
- slow_group_weather_context_summary: `WEATHER_ADVERSE_CONTEXT_PRESENT`
- slow_group_completion_interpretation_with_weather_and_hr: `SLOW_GROUP_COMPLETED_WITH_HIGH_EFFORT_EVIDENCE_CONSERVATIVE_PLANNING_STILL_RECOMMENDED`
- early_checkpoint_interpretation_with_hr: `EARLY_CHECKPOINT_HR_EFFORT_REVIEW_AVAILABLE`
- boundary_statement: `Descriptive completion feasibility review v1.1 only. Completion time, group, route-load, behavior-response, weather, heart-rate effort, and event evidence are descriptive context. This output is not ability scoring, not route suitability scoring, not THCI/radar scoring, and not a final hiking risk assessment.`

## Audit

- input_files_found: `planning_windows|planning_summary|route_load_windows|route_load_candidates|route_load_summary|performance_summary|route_normalized_comparison|weather_profile|weather_performance_join`
- input_files_missing: `NONE`
- completion_time_source_column: `activity_performance_summary.duration_sec`
- completion_time_available_count: `25`
- reviewed_activity_count: `25`
- completed_activity_count: `25`
- fast_group_count: `9`
- middle_group_count: `8`
- slow_group_count: `8`
- early_checkpoint_window_count: `175`
- slow_group_completed_count: `8`
- slow_group_early_checkpoint_reviewed_count: `8`
- weather_context_available_count: `25`
- weather_context_missing_count: `0`
- hr_context_available_count: `25`
- hr_context_missing_count: `0`
- early_checkpoint_hr_available_count: `25`
- slow_group_completed: `True`
- slow_group_hr_context_available: `True`
- slow_group_high_hr_effort_evidence: `True`
- insufficient_field_warnings: `NONE`
- forbidden_output_columns_absent: `True`
- forbidden_output_columns: `NONE`
- weather_zero_fill_performed: `False`
- hr_missing_not_interpreted_as_low_effort: `True`
- output_files_generated: `D:\mountain_work\115_osm\outputs\report_figures\ch6_7_completion_feasibility_review_v1_1\completion_time_distribution_v1_1.csv|D:\mountain_work\115_osm\outputs\report_figures\ch6_7_completion_feasibility_review_v1_1\completion_feasibility_group_summary_v1_1.csv|D:\mountain_work\115_osm\outputs\report_figures\ch6_7_completion_feasibility_review_v1_1\activity_completion_weather_context_v1_1.csv|D:\mountain_work\115_osm\outputs\report_figures\ch6_7_completion_feasibility_review_v1_1\completion_weather_group_summary_v1_1.csv|D:\mountain_work\115_osm\outputs\report_figures\ch6_7_completion_feasibility_review_v1_1\completion_hr_effort_context_v1_1.csv|D:\mountain_work\115_osm\outputs\report_figures\ch6_7_completion_feasibility_review_v1_1\completion_hr_effort_group_summary_v1_1.csv|D:\mountain_work\115_osm\outputs\report_figures\ch6_7_completion_feasibility_review_v1_1\early_checkpoint_segment_review_v1_1.csv|D:\mountain_work\115_osm\outputs\report_figures\ch6_7_completion_feasibility_review_v1_1\early_checkpoint_hr_effort_review_v1_1.csv|D:\mountain_work\115_osm\outputs\report_figures\ch6_7_completion_feasibility_review_v1_1\completion_feasibility_conclusion_v1_1.csv|D:\mountain_work\115_osm\outputs\report_figures\ch6_7_completion_feasibility_review_v1_1\completion_time_distribution_v1_1.png|D:\mountain_work\115_osm\outputs\report_figures\ch6_7_completion_feasibility_review_v1_1\fast_middle_slow_group_weather_hr_comparison_v1_1.png|D:\mountain_work\115_osm\outputs\report_figures\ch6_7_completion_feasibility_review_v1_1\early_checkpoint_1350_1700m_weather_hr_review_v1_1.png`
- audit_conclusion: `PASS_CH6_7_COMPLETION_FEASIBILITY_REVIEW_V1_1_WEATHER_HR_DESCRIPTIVE_ONLY`

## Boundaries

- descriptive completion feasibility review only
- no Word/docx output was generated
- no v2.2.7 surface-profile output was modified
- no 6.5 route-load output was modified
- no 6.7 planning context fusion v1/v1.1 output was modified
- no commit was created
