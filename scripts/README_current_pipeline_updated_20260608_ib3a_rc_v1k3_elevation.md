# Current Pipeline Update - IB3A-RC v1k3 Elevation and Gain-Loss

Date: 2026-06-08

## Current Status

The qixing_lengshuikeng IB3A-RC full26 activity flow is converged through calibrated elevation and conservative gain/loss:

1. v1d3-v1i evidence/classification
2. v1j display trajectory
3. v1k minimal horizontal calibrated activity dataset
4. v1k2 calibrated motion dataset
5. v1k2a motion artifact classification
6. v1k3 calibrated elevation / slope / cumulative gain-loss

Commits:

- `581f511 Add IB3A-RC full-batch candidate labeling and wrong-route QA`
- `0b04c81 Add IB3A-RC display trajectory refit layer`
- `70e8ffe Add IB3A-RC calibrated activity dataset horizontal layer`
- `5076517 Add IB3A-RC calibrated motion and artifact QA layers`
- `855f5a3 Add IB3A-RC calibrated elevation and gain-loss layer`

## Branching Context

IB3A-RC should be treated as an activity candidate-route branch, not as a downstream consumer of `IB0B mainline`.

```text
IA1 refreshed OSM raw
→ IB0 route match
→ IB0C anchors
→ IB0A control point projection
→ IB0A-2 route-axis anchor/component QA
    ├─→ IB0B mainline → IB0D → IB1/IB2 route formal products
    └─→ IB0-CAND adapter → candidate_route_points.csv → IB3A-RC activity calibrated dataset
```

The formal route branch produces route profile, semantics, terrain, and radar/risk products. The activity RC branch uses candidate route evidence to classify actual activity behavior and produce backend-facing calibrated activity data.

## IB3A-RC Stage Map

| Stage | Role | Output behavior |
|---|---|---|
| v1d3 | Candidate projection, context/policy, stability evidence | Creates candidate projection coordinates |
| v1e | Summit anchor stabilization | Adds reviewed summit anchor coordinates |
| v1f | Transition continuity evidence | Labels/evidence only |
| v1g | Off-target detection | Labels/evidence only |
| v1g2 | Off-target zone consolidation | Labels/evidence only |
| v1h | Mainline/connector/non-mainline membership | Classification only |
| v1i | Route-level wrong-route rules | Classification and training exclusion only |
| v1j | Display trajectory selection | Adds display coordinates only |
| v1k | Minimal horizontal calibrated dataset | Adds calibrated horizontal coordinates and backend policy |
| v1k2 | Calibrated motion dataset | Adds calibrated distance, speed, and movement state |
| v1k2a | Motion artifact QA | Adds artifact type/reason and review flags |
| v1k3 | Calibrated elevation / gain-loss | Adds elevation, slope, gain/loss, and elevation review gates |

## v1k3 Calibrated Elevation Full26

Script:

- `scripts/ib3_activity_environment/ib3a_rc_build_calibrated_elevation_v1k3.py`

Commit:

- `855f5a3 Add IB3A-RC calibrated elevation and gain-loss layer`

Input root:

- `outputs/ib3a_rc_calibrated_motion_artifacts_v1k2a_qixing_lengshuikeng_full26_qa`

IB1E route profile input:

- `outputs/ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa/qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b/qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b_route_profile_contour_window_terrain_enriched.csv`

Output root:

- `outputs/ib3a_rc_calibrated_elevation_v1k3_join_hard_gate_full26_qa`

Evidence:

- PASS / FAIL = 26 / 0
- total rows = 345,979
- CSV / summary JSON / provenance JSON = 26 / 26 / 26
- row count and row order preserved
- protected fields changed = 0
- v1k2a input SHA-256 unchanged
- forbidden facility / radar / THCI fields = 0
- v1k3 visual QA HTML/PNG not produced in this node

## v1k3 Field Additions

| Field group | Fields |
|---|---|
| Calibrated elevation | `calibrated_elevation_m`, `calibrated_elevation_source`, `calibrated_elevation_confidence`, `calibrated_elevation_review_required` |
| Join diagnostics | `elevation_lookup_method`, `elevation_reference_id`, `elevation_join_dist_m`, `elevation_profile_dist_m`, `elevation_profile_ele_smooth_m` |
| Profile ambiguity | `elevation_profile_ambiguous_flag`, `elevation_profile_ambiguity_reason`, `elevation_profile_candidate_count_10m`, `elevation_profile_candidate_dist_range_m`, `elevation_profile_dist_jump_flag` |
| Slope and gain/loss | `calibrated_delta_elevation_m`, `calibrated_slope_pct`, `elevation_step_valid`, `calibrated_cumulative_gain_m`, `calibrated_cumulative_loss_m` |
| Review/exclusion | `slope_review_required`, `elevation_artifact_flag`, `elevation_artifact_reason`, `gain_loss_excluded_reason` |

## v1k3 Elevation Source Policy

| Route class / source | Elevation behavior |
|---|---|
| `MAINLINE_CORE` | IB1E route profile spatial nearest using `calibrated_lat/lon` |
| `MAINLINE_SUMMIT_STAY` | IB1E summit route profile spatial nearest |
| `CONNECTOR` | IB1E connector review spatial nearest |
| `WRONG_ROUTE` | raw elevation fallback |
| `OFF_TARGET` / `RAW_GPS_FALLBACK` | raw elevation fallback |
| unknown route class | raw elevation fallback with review status |

## v1k3 Conservative QA Gates

| Gate | Behavior |
|---|---|
| Profile candidates within 10 m span >100 m route distance | soft QA evidence |
| Small-step row with profile distance jump >100 m | soft QA evidence |
| Profile distance jump with suspicious join distance or elevation delta | hard exclusion from slope/gain-loss |
| `elevation_join_dist_m > 10m` | hard exclusion from slope/gain-loss |
| absolute elevation delta >10 m | elevation artifact; hard exclusion from slope/gain-loss |
| step distance <3 m | slope review; excluded from valid slope |
| non-representative timestamp row | preserved but excluded from slope/gain-loss |
| motion artifact row | preserved but excluded from slope/gain-loss |

## Full26 QA Review Focus

### Highest cumulative gain/loss

| Activity | Gain m | Loss m | Slope-valid rows |
|---|---:|---:|---:|
| `30_1` | 193.34 | 214.29 | 527 |
| `38_1` | 147.55 | 185.75 | 490 |
| `23_1` | 45.60 | 40.67 | 107 |
| `35_1` | 48.42 | 37.35 | 60 |

### Highest join hard-excluded rows

| Activity | Rows |
|---|---:|
| `44_1` | 191 |
| `30_1` | 127 |
| `6_1` | 98 |
| `45_1` | 88 |
| `35_1` | 76 |
| `15_1` | 73 |

### Highest elevation artifact rows

| Activity | Rows |
|---|---:|
| `15_1` | 45 |
| `30_1` | 42 |
| `36_1` | 24 |
| `42_1` | 18 |
| `38_1` | 13 |

### Lowest slope-valid rows

| Activity | Rows |
|---|---:|
| `36_1` | 29 |
| `37_1` | 43 |
| `15_1` | 45 |
| `41_1` | 49 |
| `6_1` | 51 |

Interpretation:

- `30_1` and `38_1` have high cumulative gain/loss but also many slope-valid rows, so they are review focus rather than failure.
- `15_1`, `30_1`, and `36_1` have elevated artifact counts and should remain QA focus.
- `44_1` has the highest high-join-distance hard exclusions and remains a route-phase / transition QA focus.
- Low slope-valid rows are expected because v1k3 is intentionally conservative.

## Backend Use Rules

Normal speed / fitness analytics should use rows satisfying:

- `motion_representative_flag = True`
- `time_interval_valid = True`
- `motion_artifact_flag = False`
- `movement_state in [MOVING, SLOW_MOVING, STOPPED]`
- `backend_use_policy = ANALYTICS_READY`
- `route_class in [MAINLINE_CORE, CONNECTOR, MAINLINE_SUMMIT_STAY]`

Normal elevation / slope / gain-loss analytics should additionally use rows satisfying:

- `elevation_step_valid = True`
- `elevation_artifact_flag = False`
- no hard exclusion reason in `gain_loss_excluded_reason`
- optionally `calibrated_elevation_review_required = False` for strict high-confidence elevation models

Rows should be preserved for behavior/QA evidence but not used as normal model input when they are:

- `OFF_TARGET`
- `WRONG_ROUTE`
- `GPS_DRIFT_SUSPECTED`
- `DUPLICATE_TIMESTAMP_NON_REPRESENTATIVE`
- `LOW_CONFIDENCE_REVIEW`
- `UNKNOWN_REVIEW`
- `motion_artifact_flag = True`
- `elevation_artifact_flag = True`
- `ELEVATION_JOIN_DIST_GT_10M_HARD_EXCLUDED`
- `PROFILE_DISTANCE_JUMP_HARD_EXCLUDED`

## Known Issue: Route-Profile Phase Ambiguity

Row-level QA showed repeated alternation between early-route and late-route `elevation_profile_dist_m` values. This appears in several activities and is best interpreted as spatial-nearest profile ambiguity around self-near / overlapping route sections.

Examples:

- `30_1`: profile distance around `10` m and `4178` m
- `44_1`: profile distance around `0` m and `4187` m
- `15_1`: profile distance around `180` m and `4009` m
- `36_1`: profile distance around `13` m and `4172` m

Current v1k3 behavior:

- does not solve route phase
- labels ambiguity as soft QA evidence
- hard-excludes high join-distance / suspicious elevation-delta rows from gain/loss
- preserves the data for downstream review

Future fix:

- route-phase-aware IB1E profile candidate selection

## Protected Semantics

The following boundaries are mandatory:

- raw data is never overwritten
- v1d3-v1i, v1j, v1k, v1k2, and v1k2a outputs remain immutable inputs
- wrong-route is preserved and is not projected back to canonical mainline elevation
- connector is preserved and is not classified as `MAINLINE_CORE`
- off-target and low-confidence rows use raw fallback or review policy
- duplicate timestamp non-representative rows do not produce speed/slope
- motion artifact rows are labeled for review, not silently deleted
- elevation artifact rows are labeled for review, not silently deleted
- legacy recovery must not automatically restore `usable=True`

## Not Implemented in v1k3

- v1k3 HTML/PNG visual QA plotter
- route-phase-aware elevation join
- NLSC row-level lookup outside IB1E profile
- facility/radar evidence
- THCI recomputation
- formal activity/model inclusion gate

## Remaining Repository Items

Not part of this pipeline node:

- `folder_inventory_depth4.csv`
- `folder_role_audit_depth4.csv`
- `scripts/ib3_activity_environment/ib3a_rc_build_calibrated_elevation_v1k3.py.before_profile_ambiguity_patch`
- `scripts/ib3_activity_environment/ib3a_rc_label_transition_continuity_v1f_before_v1f2_patch.py`
- old v1h/v1h2 plotting scripts

Separate review:

- `configs/risk_semantics/ib3a_rc_v1l_osm_facility_radar_evidence_catalog_v1.csv`

## Next Development Stage

Next stage is a visual QA layer for elevation:

- recommended name: `IB3K-RC v1k3d elevation QA plotter` or `IB3K-RC v1k4 elevation visual QA`
- calibrated elevation timeline
- slope / gain-loss QA timeline
- join distance and profile distance jump markers
- elevation artifact markers
- route-class / movement-state background bands

Still deferred:

- v1l OSM facility interaction / THCI radar evidence
- IB3F-RC activity-level feature aggregation
- IB3H-RC formal model inclusion gate
- v1e2 / v1h2 summit-anchor smoothing / hysteresis
