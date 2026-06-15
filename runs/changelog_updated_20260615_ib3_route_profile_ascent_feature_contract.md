# Changelog - IB3 route profile ascent feature contract

## 2026-06-15

Added formal route-profile ascent feature contract.

### Added

- `configs/hiking_performance/ib3_route_profile_ascent_feature_contract_v1.csv`
- `docs/ib3_route_profile_ascent_feature_contract_v1.md`

### Decision

Route-profile-based ascent/descent is the corrected route-demand feature direction for hiking completion-time modeling.

Activity-point cumulative gain/loss remains blocked for model consumption.

### Boundary

No ability score, ability rank, ability class, THCI score, radar score, or final hiking risk score is generated or authorized.
