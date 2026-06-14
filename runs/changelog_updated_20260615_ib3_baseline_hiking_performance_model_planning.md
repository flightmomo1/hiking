# Changelog Update - IB3 Baseline Hiking Performance Model Planning

Date: 2026-06-15

## Added

- Baseline hiking performance model planning specification
- Auditable feature contract for activity, route, weather, and data-quality evidence
- Explicit five-layer conceptual architecture
- Future smoke-stage guidance without score implementation

Files:

- `docs/ib3_baseline_hiking_performance_model_planning_v1.md`
- `configs/hiking_performance/ib3_baseline_hiking_performance_feature_contract_v1.csv`

## Evidence basis

- 26 activity performance rows
- 27 weather profile rows
- 26 matched descriptive join rows
- 0 unmatched performance rows
- 1 unmatched weather activity:
  `qixing_lengshuikeng_xiaoyoukeng_20260410_biji_gpx`
- Join audit:
  `PASS_DESCRIPTIVE_ACTIVITY_WEATHER_PERFORMANCE_JOIN_ONLY`

## Contract boundary

- Planning and contract only
- No ability, THCI, radar, or final hiking risk scoring
- No direct weather-label penalties
- No hard-filled missing values
- Data-quality gating required before future modeling
- All feature rows have `scoring_allowed_in_this_branch = False`

## Recommended next work

- `codex/ib3-baseline-hiking-performance-model-smoke-v1`

The next stage should be a descriptive smoke prototype, not a production
ability model.
