# Changelog - IB3 route profile ascent feature patch

## 2026-06-15

Added elevation gain aggregation QA and route-profile-based ascent feature patch.

### Added

- `scripts/ib3_activity_environment/ib3_baseline_hiking_performance_elevation_gain_aggregation_qa_v1.py`
- `outputs/ib3_baseline_hiking_performance_elevation_gain_aggregation_qa_v1/activity_elevation_gain_aggregation_qa.csv`
- `outputs/ib3_baseline_hiking_performance_elevation_gain_aggregation_qa_v1/elevation_gain_aggregation_qa_audit.csv`
- `outputs/ib3_baseline_hiking_performance_elevation_gain_aggregation_qa_v1/elevation_gain_aggregation_qa_report.html`

- `scripts/ib3_activity_environment/ib3_baseline_hiking_performance_route_profile_ascent_features_v1.py`
- `outputs/ib3_baseline_hiking_performance_route_profile_ascent_features_v1/activity_route_profile_ascent_features.csv`
- `outputs/ib3_baseline_hiking_performance_route_profile_ascent_features_v1/route_profile_ascent_feature_audit.csv`
- `outputs/ib3_baseline_hiking_performance_route_profile_ascent_features_v1/route_profile_ascent_feature_report.html`

### Decision

Activity-point cumulative gain/loss is blocked for downstream model use.

Route-profile-based ascent/descent is the corrected feature direction for hiking completion-time modeling.

### Boundary

No ability score, ability rank, ability class, THCI score, radar score, or final hiking risk score is generated or authorized.
