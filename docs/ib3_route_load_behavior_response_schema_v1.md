# IB3 Route Load Behavior Response Schema v1

## Purpose

This schema defines the first descriptive smoke layer for 6.5.1 personal hiking
features and route-load comparison. It verifies that a small set of usable
activities can be grouped into route-distance windows and joined with existing
route-load, behavior, OSM exposure, and weather evidence.

It is not a hiking ability model.

## Fixture scope

The v1 smoke uses three activities that already pass the v0 usability gate:

- `qixing_lengshuikeng_3_1`
- `qixing_lengshuikeng_8_1`
- `qixing_lengshuikeng_9_1`

The fixture is intentionally small. Passing the smoke does not authorize a
full 25-activity run or production modeling.

## Join and window rules

- Activity eligibility comes from
  `activity_v0_usability_gate_smoke.csv`.
- Only `USABLE` or `USABLE_FOR_V0_MODEL_SMOKE` activities are accepted.
- Activity-point evidence comes from the IB3A v1l2 enriched output.
- Canonical route evidence is limited to `MAINLINE_CORE`,
  `MAINLINE_SUMMIT_STAY`, and `CONNECTOR`.
- Point rows must have `v1l2_join_status=JOINED`.
- Route distance uses `v1l2_ib2_dist_m`.
- Windows are grouped by `route_phase` and 50m route-distance bins.
- Weather is attached at activity level. Missing weather remains blank.

## Route-load evidence

Permitted route-load evidence includes:

- calibrated slope
- smoothed route-profile elevation context
- existing IB2 terrain, effort, exposure, and risk-band evidence

IB2 evidence describes the route window. It must not be interpreted as a
personal ability label.

The descriptive `route_load_context_band` is a smoke-only context label:

- high when absolute slope p75 is at least 15 percent, IB2 effort evidence is
  at least 0.6, or the dominant IB2 risk band is high/very high
- moderate when absolute slope p75 is at least 8 percent, IB2 effort evidence
  is at least 0.35, or the dominant IB2 risk band is moderate
- lower otherwise

This context label is not an ability class and must not be used to rank people.

## Behavior evidence

Behavior evidence is limited to descriptive window aggregation:

- valid observed interval duration and elapsed span
- calibrated speed percentiles
- stopped and low-speed ratios
- heart-rate percentiles where available
- source review and QA flags

`READY`, low speed, stopping, or high heart rate must not be translated into an
ability judgment.

## OSM and environment evidence

`near_*` flags and nearest distances are retained as proximity exposure
evidence. Proximity does not prove that a facility was used or that a mapped
hazard affected the hiker.

## Weather boundary

Weather values and context flags may be attached for descriptive comparison.

- Missing weather must remain blank.
- Missing weather must not be filled with zero.
- Weather flags must not be converted into penalties.
- This smoke does not authorize weather-sensitive scoring.

## Blocked legacy gain fields

The following fields must not be read as route-load inputs:

- `calibrated_cumulative_gain_m`
- `calibrated_cumulative_loss_m`
- `agg_total_gain_m`
- `agg_total_loss_m`
- `candidate_gain_m_per_km`
- `candidate_gain_rate_m_per_hour`
- `candidate_duration_min_per_100m_gain`

Route-profile elevation range in a 50m window is context only. It is not
cumulative ascent or descent.

## Prohibited outputs

This smoke must not generate or authorize:

- ability score
- ability rank
- ability class
- THCI score
- radar score
- final hiking risk score

The audit must report zero legacy gain use and zero prohibited score, rank, or
class generation before it can pass.
