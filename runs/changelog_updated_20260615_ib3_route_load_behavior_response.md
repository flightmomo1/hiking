# Changelog - IB3 route load behavior response evidence

## 2026-06-15

Added 6.5.1 route-load behavior-response evidence layers.

### Added

Fixture smoke:

- `scripts/ib3_activity_environment/ib3_personal_hiking_features_route_load_comparison_smoke_v1.py`
- `configs/personal_hiking_features/ib3_route_load_behavior_response_schema_v1.csv`
- `docs/ib3_route_load_behavior_response_schema_v1.md`
- `outputs/ib3_personal_hiking_features_route_load_comparison_smoke_v1/`

Full25 evidence:

- `scripts/ib3_activity_environment/ib3_personal_hiking_features_route_load_comparison_full25_v1.py`
- `outputs/ib3_personal_hiking_features_route_load_comparison_full25_v1/`

Full25 descriptive review:

- read-only review generator script
- `outputs/ib3_personal_hiking_features_route_load_comparison_full25_review_v1/`
- `docs/ib3_route_load_behavior_response_full25_review_addendum_v1.md`

### Decision

The evidence layer supports descriptive analysis of hiker behavior response against route-load and environmental exposure evidence.

It does not support ability scoring, ability ranking, causal interpretation, facility-use claims, or final risk scoring.

### Boundary

No ability score, ability rank, ability class, THCI score, radar score, or final hiking risk score is generated or authorized.
