# IB3 Baseline Hiking Performance Model Planning v1

Date: 2026-06-15

## Purpose

This document defines a reviewable data contract and conceptual architecture
for a future baseline hiking performance model. It does not implement a model.

Primary planning input:

- `outputs/ib3w_activity_weather_performance_join_v1/activity_weather_performance_join.csv`

Supporting evidence:

- `outputs/ib3w_activity_weather_performance_join_v1/activity_weather_performance_join_audit.csv`
- `outputs/ib3a_rc_full26_performance_summary_v1/activity_performance_summary.csv`
- `outputs/ib3w_codis_weather_profile_report_v1/activity_weather_profile_report_table.csv`

The joined evidence contains 26 matched activities. The weather profile has 27
activities; the weather-only unmatched activity is
`qixing_lengshuikeng_xiaoyoukeng_20260410_biji_gpx`.

## Model boundary

- This is a planning / contract branch only.
- No ability score is computed.
- No THCI score is computed.
- No radar score is computed.
- No final hiking risk score is computed.
- Weather descriptive labels must not be directly converted into penalties.
- Missing values must not be hard-filled as zero.
- Data quality gates must precede any future ability estimate.

No production model, coefficient, weighting rule, ranking, threshold, or
individual score is defined in this branch.

## Conceptual layers

### 1. Route / terrain demand

Route and terrain demand describe the difficulty background of the route
itself. Candidate evidence includes distance covered, slope distributions,
terrain risk-band distribution, and route-phase distribution. These features
must be interpreted as demand context, not as evidence that an individual has
high or low ability.

### 2. Activity performance

Activity performance describes what the person actually did during one
activity. Candidate evidence includes elapsed duration, moving and stopped
time, calibrated speed, heart-rate context, and calibrated elevation gain and
loss. Performance values are meaningful only after route demand, observation
coverage, and data quality are considered.

### 3. Weather context

Weather context describes environmental conditions during the activity.
Temperature, humidity, pressure, wind, precipitation, sunshine, and UV are
comparison covariates. They are not automatically risks and are not direct
ability penalties. Descriptive labels such as high humidity, rain observed, or
wind gust observed must remain evidence labels.

### 4. Data quality / usability

Data quality determines whether an activity is eligible for a future model.
Readiness ratios, review-required ratios, quality flags, join status, observed
weather coverage, and unavailable weather counts must be evaluated before
model fitting or inference. Missing values remain missing; zero is not a
generic substitute.

### 5. Individual ability estimate

An individual ability estimate may be considered only after comparable route
demand, usable activity evidence, weather context, and explicit quality gates
are available. The estimate should be based on multiple activities and
auditable comparison rules. A single activity must not be treated as a stable
individual ability score.

## Feature contract

The feature inventory is defined in:

- `configs/hiking_performance/ib3_baseline_hiking_performance_feature_contract_v1.csv`

The contract records source provenance, type, unit, nullability, missing-data
policy, conceptual role, and possible future use. Every row has
`scoring_allowed_in_this_branch = False`.

`route_dist_covered_m` appears in two conceptual roles:

- Activity output describing completed route distance
- Route-demand denominator for future normalization

This multi-role reference does not authorize duplicate scoring.

## Future baseline performance model direction

A future descriptive and auditable prototype may explore:

- Route-normalized completion time
- Route-normalized moving speed
- Climb-adjusted performance
- Heart-rate-aware effort context
- Weather-context-aware comparison
- Quality-gated usable activity set

The prototype should begin with transparent activity-level tables,
distributions, matched comparisons, and exclusion reasons. It should not begin
with a composite score.

High humidity, rain, and strong wind gusts must not be direct deductions. The
first analytical question is whether performance shifts systematically across
different weather contexts under the same or similar route demand. That
requires comparable routes, sufficient repeated activities, and quality-passed
records.

Any future individual ability estimate must therefore require:

- Multiple activities
- Comparable route or terrain demand
- Explicitly passed data-quality gates
- Preserved missingness
- Reviewable weather-context adjustment or stratification
- Documented uncertainty and sample support

## Proposed smoke-stage outputs

The next prototype may produce descriptive evidence such as:

- Eligible and excluded activity lists with reasons
- Route-demand strata
- Route-normalized descriptive metrics
- Weather-context comparison groups
- Per-feature missingness and usability summaries
- Multi-activity support counts

It must not emit a production score or claim validated individual ability.

## Recommended next branch

- `codex/ib3-baseline-hiking-performance-model-smoke-v1`

That branch should remain a smoke / descriptive prototype. It should validate
the contract and quality gates before any productionization decision.
