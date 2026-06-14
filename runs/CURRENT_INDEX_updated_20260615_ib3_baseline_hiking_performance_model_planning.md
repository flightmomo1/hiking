# CURRENT INDEX - IB3 Baseline Hiking Performance Model Planning

Date: 2026-06-15

## Workspace

- `D:\mountain_work\115_osm`

## Branch

- `codex/ib3-baseline-hiking-performance-model-planning-v1`

## Completed foundation

- `45085f1fcc4ec11f6178541e43477087b2f02b38 Document IB3W activity weather performance join closeout`
- Activity performance summary: 26 activities, `PASS_ACTIVITY_PERFORMANCE_SUMMARY_ONLY`
- Weather profile: 27 activities and 243 observed weather values
- Descriptive join: 26 matched activities, `PASS_DESCRIPTIVE_ACTIVITY_WEATHER_PERFORMANCE_JOIN_ONLY`

## Planning artifacts

- `docs/ib3_baseline_hiking_performance_model_planning_v1.md`
- `configs/hiking_performance/ib3_baseline_hiking_performance_feature_contract_v1.csv`

The feature contract inventories five conceptual layers:

1. Route / terrain demand
2. Activity performance
3. Weather context
4. Data quality / usability
5. Individual ability estimate

The fifth layer is conceptual only. No individual ability feature or score is
computed in this branch.

## Boundary

- This is a planning / contract branch only.
- No ability, THCI, radar, or final hiking risk score is computed.
- Weather labels are not direct penalties.
- Missing values are not hard-filled as zero.
- Data-quality gates must precede any future estimate.

## Next branch

- `codex/ib3-baseline-hiking-performance-model-smoke-v1`

The next branch should remain a descriptive smoke prototype and must not be
productionized directly.
