# README Update - IB3 Baseline Hiking Performance Model v0 Design

Date: 2026-06-15

## Pipeline position

The evidence pipeline now supports design of a baseline hiking performance
model v0. It does not yet implement an ability model.

Completed evidence chain:

```text
IB3A-RC full26 activity performance summary
-> IB3W CODiS weather profile
-> activity x weather performance descriptive join
-> baseline performance planning contract
-> baseline performance smoke metrics
```

## Design contracts

- `docs/ib3_baseline_hiking_performance_model_v0_design_v1.md`
- `configs/hiking_performance/ib3_baseline_hiking_performance_model_v0_rule_contract_v1.csv`
- `configs/hiking_performance/ib3_baseline_hiking_performance_model_v0_output_contract_v1.csv`

## Model v0 architecture

1. Input evidence layer
2. Data quality gate layer
3. Comparable activity set layer
4. Route-normalized performance layer
5. Weather-context interpretation layer
6. Ability estimate candidate layer

## Usable and comparable evidence

A future usable activity must pass reviewed join and quality gates, retain
positive route distance and duration, and belong to an approved comparable
route family. Review-only activities remain visible but do not enter a formal
estimate.

Comparable groups require similar route family, start and end conditions,
distance, elevation, and terrain demand. Cross-route activities require a
separate group.

## Indicator interpretation

Route-normalized duration, speed, climb, heart-rate, moving, and stopped
contexts remain descriptive. No single candidate metric is an ability score.

Weather context may support stratified comparison only. High humidity, rain,
wind gust, and high UV are not direct deductions. Missing weather is not zero.

## Authorization boundary

- Model v0 design only
- No generated ability score
- No generated ability ranking
- No THCI, radar, or final hiking risk scoring
- Rule contract scoring is disabled
- Output generation is disabled
- Output scoring is disabled

## Future output concept

The output contract reserves fields for estimate status and scope, comparable
group, usable and review counts, route-normalized summary, weather coverage,
quality summary, confidence, and review note. No values are generated in this
branch.

## Recommended continuation

Build a contract-validation and comparable-group smoke first. It should report
eligibility and grouping evidence without producing a formal hiking ability
score or ranking.
