# CURRENT INDEX - IB3 Baseline Hiking Performance Model Smoke

Date: 2026-06-15

## Working directory

- `D:\mountain_work\115_osm`

## Current branch

- `codex/ib3-baseline-hiking-performance-model-smoke-closeout-v1`

## Completed commit chain

- `45085f1fcc4ec11f6178541e43477087b2f02b38 Document IB3W activity weather performance join closeout`
- `b04d47bf3bb3b2c28cc02dc7c85d10d494a3db20 Plan IB3 baseline hiking performance model`
- `b39854e026de4329850f6a75649c7d1183c34163 Add IB3 baseline hiking performance smoke metrics`

## Inputs

- `outputs/ib3w_activity_weather_performance_join_v1/activity_weather_performance_join.csv`
- `outputs/ib3w_activity_weather_performance_join_v1/activity_weather_performance_join_audit.csv`
- `configs/hiking_performance/ib3_baseline_hiking_performance_feature_contract_v1.csv`

## Outputs

- `outputs/ib3_baseline_hiking_performance_model_smoke_v1/activity_baseline_performance_smoke_features.csv`
- `outputs/ib3_baseline_hiking_performance_model_smoke_v1/activity_baseline_performance_smoke_audit.csv`
- `outputs/ib3_baseline_hiking_performance_model_smoke_v1/activity_baseline_performance_smoke_report.html`

## Smoke result

- `input_join_row_count = 26`
- `output_feature_row_count = 26`
- `candidate_metric_count = 9`
- `feature_contract_all_scoring_disallowed = True`
- Data-quality gate distribution:
  - `READY_FOR_DESCRIPTIVE_MODEL_SMOKE = 25`
  - `REVIEW_LOW_ANALYTICS_READY_RATIO = 1`
- `audit_conclusion = PASS_BASELINE_PERFORMANCE_SMOKE_DESCRIPTIVE_ONLY`

## Descriptive candidate metrics

- `route_dist_covered_km`
- `candidate_duration_min_per_km`
- `candidate_median_speed_kmh`
- `candidate_gain_m_per_km`
- `candidate_duration_min_per_100m_gain`
- `candidate_gain_rate_m_per_hour`
- `candidate_hr_median_context`
- `candidate_weather_context_flags`
- `candidate_data_quality_gate`

These fields are descriptive candidate performance metrics. They are not
scores, ranks, or validated individual ability estimates.

## Engineering boundary

- This stage produces descriptive candidate performance metrics only.
- This is not a production hiking ability model.
- No ability score or ability rank is generated.
- No THCI, radar, or final hiking risk scoring is performed.
- Candidate weather-context flags must not be converted directly into penalties.
- The candidate data-quality gate is a future model usability gate, not an ability rating.
- `READY_FOR_DESCRIPTIVE_MODEL_SMOKE` does not mean good ability.
- `REVIEW_LOW_ANALYTICS_READY_RATIO` does not mean poor ability.

## Recommended next step

- `codex/ib3-baseline-hiking-performance-model-v0-design-v1`

The next branch should design the model v0 data contract and reviewable rules
without productionizing or generating a formal hiking ability score. It should
define:

- Usable activity set
- Comparable activity group
- Route-normalized performance indicators
- Weather-context-aware comparison
- Quality gate before ability estimation
- Review-only cases
