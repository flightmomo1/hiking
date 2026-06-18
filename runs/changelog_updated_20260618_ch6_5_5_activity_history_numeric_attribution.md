# Changelog update — 20260618_ch6_5_5_activity_history_numeric_attribution

## Added

- CH6.5.5 v0.4 activity-history-primary relabel evidence.
- CH6.5.5 v0.5 activity-history numeric attribution evidence.
- Evidence hierarchy:
  - primary: actual hiking activity history
  - secondary: sex-age HR zone context
  - tertiary: estimated VO2max and subjective difficulty
- Numeric attribution of candidate/review labels using CH6.5.4 reference thresholds.

## Results

### v0.4

- activity_count: 25
- primary_activity_history_candidate_rows: 7
- single_factor_behavior_review_rows: 5
- hr_context_rows: 15
- profile_context_only_rows: 5
- profile_promotion_used: False
- audit_conclusion: `PASS_CH6_5_5_ACTIVITY_HISTORY_PRIMARY_RELABEL_V0_4_DESCRIPTIVE_ONLY`

### v0.5

- attribution_scope_rows: 12
- primary_candidate_rows_in_scope: 7
- single_factor_review_rows_in_scope: 5
- metric_attribution_long_rows: 72
- triggered_metric_rows: 38
- threshold_metric_rules_n: 6
- profile_promotion_used: False
- audit_conclusion: `PASS_CH6_5_5_ACTIVITY_HISTORY_NUMERIC_ATTRIBUTION_V0_5_DESCRIPTIVE_ONLY`

## Interpretation boundary

Descriptive CH6.5.5 personal activity-history evidence only. Actual hiking activity history is primary evidence; HR zone is secondary context; non-standard estimated VO2max and subjective Qixing difficulty are tertiary supporting context only and do not promote an activity into strain candidate by themselves. This is not an ability score, ability rank, ability class, final hiking risk score, route suitability score, go/no-go decision, medical diagnosis, or causality evidence.

## Notes

- High HR controlled output remains separated from route-load strain candidates.
- Non-standard estimated VO2max and subjective Qixing difficulty are retained only as tertiary supporting context.
- v0.5 identifies:
  - 4 primary report case candidates: `42_1`, `43_1`, `46_1`, `48_1`
  - 3 secondary report case candidates: `23_1`, `38_1`, `9_1`
  - 5 numeric-detail review rows: `16_1`, `28_1`, `37_1`, `44_1`, `8_1`
