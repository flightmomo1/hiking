# Latest Handoff Prompt - IB3 Baseline Hiking Performance Model Smoke

Date: 2026-06-15

## Workspace

- `D:\mountain_work\115_osm`

## Completed chain

- `45085f1fcc4ec11f6178541e43477087b2f02b38 Document IB3W activity weather performance join closeout`
- `b04d47bf3bb3b2c28cc02dc7c85d10d494a3db20 Plan IB3 baseline hiking performance model`
- `b39854e026de4329850f6a75649c7d1183c34163 Add IB3 baseline hiking performance smoke metrics`

## Evidence inputs

- `outputs/ib3w_activity_weather_performance_join_v1/activity_weather_performance_join.csv`
- `outputs/ib3w_activity_weather_performance_join_v1/activity_weather_performance_join_audit.csv`
- `configs/hiking_performance/ib3_baseline_hiking_performance_feature_contract_v1.csv`

## Completed smoke outputs

- `outputs/ib3_baseline_hiking_performance_model_smoke_v1/activity_baseline_performance_smoke_features.csv`
- `outputs/ib3_baseline_hiking_performance_model_smoke_v1/activity_baseline_performance_smoke_audit.csv`
- `outputs/ib3_baseline_hiking_performance_model_smoke_v1/activity_baseline_performance_smoke_report.html`

Validated result:

- `input_join_row_count = 26`
- `output_feature_row_count = 26`
- `candidate_metric_count = 9`
- `feature_contract_all_scoring_disallowed = True`
- `READY_FOR_DESCRIPTIVE_MODEL_SMOKE = 25`
- `REVIEW_LOW_ANALYTICS_READY_RATIO = 1`
- `audit_conclusion = PASS_BASELINE_PERFORMANCE_SMOKE_DESCRIPTIVE_ONLY`

## Candidate metrics

- `route_dist_covered_km`
- `candidate_duration_min_per_km`
- `candidate_median_speed_kmh`
- `candidate_gain_m_per_km`
- `candidate_duration_min_per_100m_gain`
- `candidate_gain_rate_m_per_hour`
- `candidate_hr_median_context`
- `candidate_weather_context_flags`
- `candidate_data_quality_gate`

These are descriptive fields, not ability scores, rankings, or risk scores.

## Non-negotiable boundary

- No production hiking ability model exists yet.
- No ability score or ability rank is generated.
- No THCI, radar, or final hiking risk scoring is generated or authorized.
- Weather-context flags are descriptive and must not become direct penalties.
- The data-quality gate indicates future model usability only.
- `READY` does not mean good ability.
- `LOW_ANALYTICS_REVIEW` does not mean poor ability.

## Recommended continuation

- `codex/ib3-baseline-hiking-performance-model-v0-design-v1`

Design a reviewable model v0 contract before implementation. Define the usable
activity set, comparable activity groups, route-normalized indicators,
weather-context-aware comparisons, pre-estimation quality gates, and
review-only cases. Do not productionize or emit a formal ability score.
