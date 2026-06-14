# Changelog Update - IB3 Baseline Hiking Performance Model Smoke

Date: 2026-06-15

## Working directory

- `D:\mountain_work\115_osm`

## Completed commits

- `45085f1fcc4ec11f6178541e43477087b2f02b38 Document IB3W activity weather performance join closeout`
- `b04d47bf3bb3b2c28cc02dc7c85d10d494a3db20 Plan IB3 baseline hiking performance model`
- `b39854e026de4329850f6a75649c7d1183c34163 Add IB3 baseline hiking performance smoke metrics`

## Inputs used

- `outputs/ib3w_activity_weather_performance_join_v1/activity_weather_performance_join.csv`
- `outputs/ib3w_activity_weather_performance_join_v1/activity_weather_performance_join_audit.csv`
- `configs/hiking_performance/ib3_baseline_hiking_performance_feature_contract_v1.csv`

## Added smoke evidence

- `outputs/ib3_baseline_hiking_performance_model_smoke_v1/activity_baseline_performance_smoke_features.csv`
- `outputs/ib3_baseline_hiking_performance_model_smoke_v1/activity_baseline_performance_smoke_audit.csv`
- `outputs/ib3_baseline_hiking_performance_model_smoke_v1/activity_baseline_performance_smoke_report.html`

Result:

- `input_join_row_count = 26`
- `output_feature_row_count = 26`
- `candidate_metric_count = 9`
- `feature_contract_all_scoring_disallowed = True`
- `READY_FOR_DESCRIPTIVE_MODEL_SMOKE = 25`
- `REVIEW_LOW_ANALYTICS_READY_RATIO = 1`
- `audit_conclusion = PASS_BASELINE_PERFORMANCE_SMOKE_DESCRIPTIVE_ONLY`

## Descriptive fields added

- `route_dist_covered_km`
- `candidate_duration_min_per_km`
- `candidate_median_speed_kmh`
- `candidate_gain_m_per_km`
- `candidate_duration_min_per_100m_gain`
- `candidate_gain_rate_m_per_hour`
- `candidate_hr_median_context`
- `candidate_weather_context_flags`
- `candidate_data_quality_gate`

These are candidate metrics and context fields, not scores.

## Boundary preserved

- No formal hiking ability model was productionized.
- No ability score or rank was generated.
- No THCI, radar, or final hiking risk scoring was performed.
- Weather-context flags remain descriptive rather than penalty terms.
- The quality gate indicates usability, not ability.
- `READY` is not evidence of good ability.
- `LOW_ANALYTICS_REVIEW` is not evidence of poor ability.

## Recommended next work

- `codex/ib3-baseline-hiking-performance-model-v0-design-v1`

The next stage should define the usable activity set, comparable groups,
route-normalized indicators, weather-aware comparisons, quality gates, and
review-only cases. It must remain a design stage and must not emit a formal
hiking ability score.
