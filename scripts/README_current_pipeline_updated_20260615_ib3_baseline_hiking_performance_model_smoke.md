# README Update - IB3 Baseline Hiking Performance Model Smoke

Date: 2026-06-15

## Working directory

- `D:\mountain_work\115_osm`

## Pipeline status

The pipeline is complete through a descriptive baseline hiking performance
smoke. It has not reached a production hiking ability model.

Completed chain:

- `45085f1fcc4ec11f6178541e43477087b2f02b38 Document IB3W activity weather performance join closeout`
- `b04d47bf3bb3b2c28cc02dc7c85d10d494a3db20 Plan IB3 baseline hiking performance model`
- `b39854e026de4329850f6a75649c7d1183c34163 Add IB3 baseline hiking performance smoke metrics`

## Input contract

- `outputs/ib3w_activity_weather_performance_join_v1/activity_weather_performance_join.csv`
- `outputs/ib3w_activity_weather_performance_join_v1/activity_weather_performance_join_audit.csv`
- `configs/hiking_performance/ib3_baseline_hiking_performance_feature_contract_v1.csv`

## Smoke artifacts

- `outputs/ib3_baseline_hiking_performance_model_smoke_v1/activity_baseline_performance_smoke_features.csv`
- `outputs/ib3_baseline_hiking_performance_model_smoke_v1/activity_baseline_performance_smoke_audit.csv`
- `outputs/ib3_baseline_hiking_performance_model_smoke_v1/activity_baseline_performance_smoke_report.html`

Validated contract:

- `input_join_row_count = 26`
- `output_feature_row_count = 26`
- `candidate_metric_count = 9`
- `feature_contract_all_scoring_disallowed = True`
- `READY_FOR_DESCRIPTIVE_MODEL_SMOKE = 25`
- `REVIEW_LOW_ANALYTICS_READY_RATIO = 1`
- `audit_conclusion = PASS_BASELINE_PERFORMANCE_SMOKE_DESCRIPTIVE_ONLY`

## Candidate metric contract

- `route_dist_covered_km`
- `candidate_duration_min_per_km`
- `candidate_median_speed_kmh`
- `candidate_gain_m_per_km`
- `candidate_duration_min_per_100m_gain`
- `candidate_gain_rate_m_per_hour`
- `candidate_hr_median_context`
- `candidate_weather_context_flags`
- `candidate_data_quality_gate`

All candidate metrics are descriptive evidence. They are not model scores.

## Authorization boundary

- This is not the production hiking ability model.
- `ability_score_generated = False`
- `ability_rank_generated = False`
- `thci_scoring_authorized = False`
- `radar_scoring_authorized = False`
- `final_hiking_risk_scoring_authorized = False`
- Weather-context flags must not be converted directly into deductions.
- The data-quality gate is a future model usability gate, not an ability grade.
- `READY` does not mean good ability.
- `LOW_ANALYTICS_REVIEW` does not mean poor ability.

## Recommended next branch

- `codex/ib3-baseline-hiking-performance-model-v0-design-v1`

The next branch should design the model v0 data contract and rules without
productionization or formal scoring. It should define:

- Usable activity set
- Comparable activity group
- Route-normalized performance indicators
- Weather-context-aware comparison
- Quality gate before ability estimation
- Review-only cases
