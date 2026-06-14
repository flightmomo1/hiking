# CURRENT INDEX - IB3 Baseline Hiking Performance Model v0 Design

Date: 2026-06-15

## Workspace

- `D:\mountain_work\115_osm`

## Branch

- `codex/ib3-baseline-hiking-performance-model-v0-design-v1`

## Evidence chain

```text
IB3A-RC full26 activity performance summary
-> IB3W CODiS weather profile
-> activity x weather performance descriptive join
-> baseline performance planning contract
-> baseline performance smoke metrics
```

Recent commits:

- `45085f1fcc4ec11f6178541e43477087b2f02b38`
- `b04d47bf3bb3b2c28cc02dc7c85d10d494a3db20`
- `b39854e026de4329850f6a75649c7d1183c34163`
- `85733798a1c36371225fa7e99b62462bd5f7ce2c`

## Design artifacts

- `docs/ib3_baseline_hiking_performance_model_v0_design_v1.md`
- `configs/hiking_performance/ib3_baseline_hiking_performance_model_v0_rule_contract_v1.csv`
- `configs/hiking_performance/ib3_baseline_hiking_performance_model_v0_output_contract_v1.csv`

## Model layers

1. Input evidence layer
2. Data quality gate layer
3. Comparable activity set layer
4. Route-normalized performance layer
5. Weather-context interpretation layer
6. Ability estimate candidate layer

## Boundary

- Design and contract only
- No ability score or rank
- No THCI, radar, or final hiking risk score
- Candidate metrics are not scores
- Weather context is not a direct penalty
- Quality gating precedes any future estimate
- No model output is generated in this branch

## Future implementation direction

The next implementation should validate usable, review-only, excluded, and
comparable activity sets before considering an estimate. It must preserve
auditable grouping reasons and must not productionize a formal score directly.
