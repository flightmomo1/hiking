# Chapter 6.5 single-activity route surface and behavior profile v2.2.7 speed threshold pause focus: 42_1

## Inputs

- canonical route evidence: `D:\mountain_work\115_osm\outputs\ib2_v2_route_risk_v1_3b_contract_qa\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b_route_risk_v2.csv`
- behavior windows: `D:\mountain_work\115_osm\outputs\ib3_personal_hiking_features_route_load_comparison_full25_v1\activity_route_load_behavior_response_windows.csv`
- selected activity_id_short: `42_1`

## What this version fixes

- Uses true route-axis 1 m surface / path ribbon from the canonical route evidence, where available.
- Filters behavior data to one `activity_id_short` before aggregation.
- Keeps slope next to heart rate, then speed, then low/stop ratios.
- Marks route events and single-activity stop/slow candidates in the same spatial background panel.
- Does not compute cross-activity IQR for the selected-activity figure.

## Surface distribution

- step: 2593 m
- footway: 1511 m
- path_trail: 0 m
- road: 84 m
- unknown_other: 0 m

## Event markers

- rest_candidate: 18
- guidepost: 11
- peak: 7
- waterway: 4
- shelter: 2
- trailhead: 2

## Shelter context zones

- shelter_context_zone_count: 2
- raw_near_shelter_run_count: 4
- interpretation: shelter context zones merge adjacent OSM near_shelter proximity runs for presentation; they do not represent physical facility counts, first-visible points, or confirmed use.

| zone_id | role | zone_m | marker_m | raw_runs_m |
|---|---|---:|---:|---|
| SHELTER_CONTEXT_ZONE_1 | OUTBOUND_SHELTER_CONTEXT_ZONE | 550-782 | 747 | 550-619|669-782 |
| SHELTER_CONTEXT_ZONE_2 | RETURN_SHELTER_CONTEXT_ZONE | 3414-3638 | 3604 | 3414-3518|3569-3638 |

## Behavior summary

- rows: 84
- route phase values: UNKNOWN

## Boundaries

- This figure is descriptive only.
- Surface type is a route-axis spatial distribution.
- Behavior indicators are selected-activity window summaries, not instantaneous 1 m observations.
- The 0.7 m/s dashed line in the speed panel is visual reference only and does not recalculate behavior features.
- `route_phase=UNKNOWN` cannot support ascent/descent comparison.
- Weather remains activity-level background context, not pointwise weather.
- OSM proximity is exposure evidence, not proof of facility use.
- Shelter context zones are merged report-level proximity zones; they are not physical shelter counts or first-visible points.
- Rest candidate is a stop/slow candidate, not a confirmed rest point.
- No ability score, rank, class, THCI, radar, or final hiking risk score is generated.

## Audit

- conclusion: `PASS_CH6_5_SINGLE_ACTIVITY_SURFACE_PROFILE_V2_2_5_SPEED_THRESHOLD_PAUSE_FOCUS`
