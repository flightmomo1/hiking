# Latest Handoff Prompt - IB3 Baseline Hiking Performance Model v0 Design

Date: 2026-06-15

## Workspace

- `D:\mountain_work\115_osm`

## Current branch

- `codex/ib3-baseline-hiking-performance-model-v0-design-v1`

## Completed foundation

- Activity performance summary
- CODiS weather profile
- Descriptive activity-weather join
- Baseline performance planning contract
- Baseline performance smoke metrics
- Smoke closeout

Recent commits:

- `45085f1fcc4ec11f6178541e43477087b2f02b38`
- `b04d47bf3bb3b2c28cc02dc7c85d10d494a3db20`
- `b39854e026de4329850f6a75649c7d1183c34163`
- `85733798a1c36371225fa7e99b62462bd5f7ce2c`

## Read first

- `docs/ib3_baseline_hiking_performance_model_v0_design_v1.md`
- `configs/hiking_performance/ib3_baseline_hiking_performance_model_v0_rule_contract_v1.csv`
- `configs/hiking_performance/ib3_baseline_hiking_performance_model_v0_output_contract_v1.csv`

## Design summary

The v0 design separates input evidence, data-quality gating, comparable
activity grouping, route-normalized indicators, weather-context
interpretation, and a future ability-estimate candidate layer.

The usable activity concept requires matched evidence, a ready-type quality
gate, sufficient analytics coverage, acceptable review burden, positive route
distance and duration, and an approved comparable route family.

Different route forms, including Xiaoyoukeng cross-route activities, require a
separate comparable group rather than direct inclusion in the Lengshuikeng
full26 baseline.

## Non-negotiable boundary

- No ability score or ranking is generated.
- No THCI, radar, or final hiking risk score is generated.
- Candidate metrics remain descriptive.
- Weather flags remain context and are not direct penalties.
- Missing weather remains missing.
- Review-only activities do not enter a formal future estimate.
- All rule scoring flags are false.
- All future outputs are marked not generated and not scoring-authorized.

## Recommended continuation

Build a contract-validation and grouping smoke that reports usable,
review-only, excluded, and comparable sets. Do not emit a formal hiking ability
score or production ranking.
