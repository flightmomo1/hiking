# IB3 Baseline Hiking Performance Model v0 Design v1

Date: 2026-06-15

## Purpose

This document defines the data boundaries, review gates, comparison concepts,
and future output contract for a baseline hiking performance model v0. It is a
design artifact, not a model implementation.

## Model boundary

- This branch designs model v0 only.
- No ability score is computed in this branch.
- No ability rank is computed in this branch.
- No THCI score is computed.
- No radar score is computed.
- No final hiking risk score is computed.
- Weather context is explanatory context, not a direct penalty.
- Data quality gate must precede any future ability estimate.
- Candidate metrics are not scores.

No weights, coefficients, composite formulas, production thresholds, personal
ratings, or rankings are implemented here.

## Current evidence chain

```text
IB3A-RC full26 activity performance summary
-> IB3W CODiS weather profile
-> activity x weather performance descriptive join
-> baseline performance planning contract
-> baseline performance smoke metrics
```

Recent commits:

- `45085f1fcc4ec11f6178541e43477087b2f02b38`
  `Document IB3W activity weather performance join closeout`
- `b04d47bf3bb3b2c28cc02dc7c85d10d494a3db20`
  `Plan IB3 baseline hiking performance model`
- `b39854e026de4329850f6a75649c7d1183c34163`
  `Add IB3 baseline hiking performance smoke metrics`
- `85733798a1c36371225fa7e99b62462bd5f7ce2c`
  `Document IB3 baseline hiking performance smoke closeout`

Current smoke evidence contains 26 activity rows. Twenty-five are marked
`READY_FOR_DESCRIPTIVE_MODEL_SMOKE`; one is marked
`REVIEW_LOW_ANALYTICS_READY_RATIO`. These labels describe usability only.

## Model v0 layers

### 1. Input evidence layer

Responsibility:

- Preserve activity performance, route and terrain, weather context, data
  quality, source provenance, and missingness.
- Accept only fields defined by reviewed upstream contracts.

Boundary:

- Must not reinterpret missing values as zero.
- Must not treat descriptive weather flags or smoke metrics as scores.

### 2. Data quality gate layer

Responsibility:

- Decide whether an activity is usable, review-only, or excluded from a future
  estimate.
- Review join status, analytics-ready coverage, calibration review burden,
  movement review burden, route distance, and duration.

Boundary:

- A gate outcome is not an ability judgment.
- Thresholds require a separate reviewed implementation contract.

### 3. Comparable activity set layer

Responsibility:

- Group activities only when route family, start and end conditions, distance,
  elevation demand, and terrain demand are sufficiently comparable.
- Preserve separate cross-route groups where route form differs.

Boundary:

- Different route types must not be pooled merely to increase sample count.
- Review-only activities must not enter a formal ability estimate.

### 4. Route-normalized performance layer

Responsibility:

- Summarize duration, speed, climb, movement, stopping, and heart-rate context
  relative to route demand.
- Retain the original activity-level values behind every summary.

Boundary:

- Candidate indicators remain descriptive.
- No single indicator is an ability score or ranking basis.

### 5. Weather-context interpretation layer

Responsibility:

- Stratify or annotate comparable performance observations by temperature,
  humidity, rain, wind gust, UV, and weather evidence coverage.
- Test whether performance shifts systematically inside a comparable group.

Boundary:

- Weather flags are not direct deductions.
- No weather adjustment is permitted without sufficient samples and a
  separately reviewed, auditable rule.

### 6. Ability estimate candidate layer

Responsibility:

- Define the future shape of an estimate, including scope, sample support,
  comparable group, quality summary, context coverage, confidence, and review
  note.

Boundary:

- This branch does not generate any ability-estimate value.
- A future estimate must not be emitted when usable or comparable evidence is
  insufficient.

## Future usable activity set

The usable activity set gate is designed here but not executed.

Conceptual requirements:

- `join_status` must be `MATCHED` or an explicitly equivalent reviewed value.
- `candidate_data_quality_gate` must be a ready-type outcome.
- `backend_use_analytics_ready_ratio` must not be below a reviewed threshold.
- `calibration_review_required_ratio` must not exceed a reviewed threshold.
- `movement_review_required_ratio` must not exceed a reviewed threshold.
- `route_dist_covered_m` must be present and greater than zero.
- `duration_min` must be present and greater than zero.
- The activity must belong to the same or an explicitly comparable route
  family.
- Review-only activities must be reported separately and must not enter a
  formal ability estimate.

The smoke thresholds of 0.5 remain prototype usability checks. They are not
automatically adopted as production model thresholds by this design.

## Comparable activity group

A comparable group should require:

- The same route or a documented route family.
- Similar start and end conditions.
- Similar route distance and elevation demand.
- Similar terrain slope and terrain-demand distributions.
- A documented tolerance policy for every grouping dimension.
- Weather context retained for stratified comparison rather than direct
  penalty.

Different route forms, including a Lengshuikeng ascent or descent involving
Xiaoyoukeng, must not be mixed directly into the Lengshuikeng full26 baseline
group. Such activities require a separate cross-route group and explicit
comparability review.

## Route-normalized performance indicators

### `candidate_duration_min_per_km`

Intuition:

- Describes elapsed minutes per kilometer.

Limitations:

- Sensitive to climb, terrain, stopping, route conditions, and activity
  completeness.
- Lower is not automatically better ability.

### `candidate_median_speed_kmh`

Intuition:

- Converts calibrated median movement speed into kilometers per hour.

Limitations:

- Depends on calibration and movement-state quality.
- Does not represent full-route completion efficiency by itself.

### `candidate_gain_m_per_km`

Intuition:

- Describes observed climbing demand per kilometer.

Limitations:

- Primarily a route-demand context, not personal performance.
- Depends on calibrated elevation evidence.

### `candidate_duration_min_per_100m_gain`

Intuition:

- Relates elapsed duration to each 100 meters of observed gain.

Limitations:

- Unstable when gain is small and incomplete when descent or flat distance
  dominates.
- Must remain missing when gain is zero or unavailable.

### `candidate_gain_rate_m_per_hour`

Intuition:

- Describes observed gain per elapsed hour.

Limitations:

- Influenced by distance, terrain, stopping, route completeness, and elevation
  calibration.
- Higher is not automatically better ability.

### Heart-rate-aware effort context

Heart-rate median and percentile evidence can describe observed effort context.
It requires sensor availability and individual calibration. It must not be
compared across people as a direct ability measure.

### Stopped / moving context

Moving and stopped time help explain elapsed duration. Stops may reflect rest,
navigation, observation, congestion, or recording behavior and must not be
treated automatically as underperformance.

### Data-quality context

Analytics-ready, calibration-review, movement-review, join, and weather
coverage evidence determine whether any indicator is usable. Quality context
must be retained with every future summary.

## Weather-context-aware interpretation

- High humidity, rain observed, wind gust, and high UV are context only.
- Weather flags must not be converted directly into penalties.
- Analysis should first test whether performance shifts systematically within
  the same comparable group under a specific weather context.
- Missing weather remains context-incomplete and is never zero-filled.
- A future weather adjustment requires sufficient sample support, documented
  uncertainty, and an auditable reviewed rule.

## Future ability estimate output

The future output concept includes:

- `ability_estimate_status`
- `ability_estimate_scope`
- `comparable_group_id`
- `usable_activity_count`
- `review_activity_count`
- `route_normalized_performance_summary`
- `weather_context_coverage`
- `quality_gate_summary`
- `ability_estimate_confidence`
- `ability_estimate_review_note`

This branch does not generate values for these fields. Their types, nullability,
generation status, and authorization boundary are defined in:

- `configs/hiking_performance/ib3_baseline_hiking_performance_model_v0_output_contract_v1.csv`

## Rule contract

Future rule concepts are defined in:

- `configs/hiking_performance/ib3_baseline_hiking_performance_model_v0_rule_contract_v1.csv`

Every rule has `scoring_allowed_in_this_branch = False`.

## Next engineering step

A future implementation branch should first build a contract-validation and
grouping smoke. It should report usable, review-only, excluded, and comparable
sets without producing a formal hiking ability score or ranking.
