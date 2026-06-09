# Current Pipeline Update - IB3A-RC v1k4 Elevation Visual QA

Date: 2026-06-09

## Current Status

The qixing_lengshuikeng IB3A-RC full26 activity flow is converged through calibrated elevation visual QA:

1. v1d3-v1i evidence/classification
2. v1j display trajectory
3. v1k minimal horizontal calibrated activity dataset
4. v1k2 calibrated motion dataset
5. v1k2a motion artifact classification
6. v1k3 calibrated elevation / slope / cumulative gain-loss
7. v1k4 elevation visual QA plotter

Commits:

- `581f511 Add IB3A-RC full-batch candidate labeling and wrong-route QA`
- `0b04c81 Add IB3A-RC display trajectory refit layer`
- `70e8ffe Add IB3A-RC calibrated activity dataset horizontal layer`
- `5076517 Add IB3A-RC calibrated motion and artifact QA layers`
- `855f5a3 Add IB3A-RC calibrated elevation and gain-loss layer`
- `b24f205 Document IB3A-RC v1k3 elevation convergence`
- `bf4fcf6 Add IB3A-RC elevation visual QA plotter`

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
| v1k4 | Elevation visual QA | Adds read-only HTML QA reports and batch visual QA summary |

## v1k4 Elevation Visual QA Full26

Script:

- `scripts/ib3_activity_environment/ib3a_rc_plot_calibrated_elevation_v1k4.py`

Commit:

- `bf4fcf6 Add IB3A-RC elevation visual QA plotter`

Input root:

- `outputs/ib3a_rc_calibrated_elevation_v1k3_join_hard_gate_full26_qa`

Output root:

- `outputs/ib3a_rc_calibrated_elevation_visual_qa_v1k4_qixing_lengshuikeng_full26`

Batch summary:

- `outputs/ib3a_rc_calibrated_elevation_visual_qa_v1k4_qixing_lengshuikeng_full26/_batch_summary/qixing_lengshuikeng_v1k4_elevation_visual_qa_summary.csv`
- `outputs/ib3a_rc_calibrated_elevation_visual_qa_v1k4_qixing_lengshuikeng_full26/_batch_summary/qixing_lengshuikeng_v1k4_elevation_visual_qa_summary.json`

Evidence:

- PASS / FAIL = 26 / 0
- full26 HTML generated for 26 / 26 activities
- batch summary CSV / JSON generated
- manual visual smoke checked: `44_1`, `30_1`, `38_1`, `37_1`
- HTML readable and useful for elevation / join distance / profile distance / QA focus row inspection
- v1k4 does not modify v1k3 CSV / JSON outputs
- v1k4 does not recompute elevation, slope, gain, or loss

## v1k4 Report Contents

Each per-activity HTML report includes:

- summary metrics
- route-class counts
- elevation-source counts
- calibrated elevation vs raw elevation timeline
- elevation join-distance timeline
- calibrated delta elevation timeline
- joined IB1E profile-distance timeline
- elevation artifact markers
- join-distance hard-exclusion markers
- profile-distance jump markers
- valid slope / gain-loss step markers
- QA focus row table

The report is a read-only visual QA layer. It is intended to help reviewers locate suspicious regions quickly, not to change upstream classification or elevation calculations.

## Full26 QA Review Focus

### Highest join hard-excluded rows

| Activity | Rows |
|---|---:|
| `44_1` | 191 |
| `30_1` | 127 |
| `6_1` | 98 |
| `45_1` | 88 |
| `35_1` | 76 |
| `15_1` | 73 |

### Highest cumulative gain/loss

| Activity | Gain m | Loss m | Slope-valid rows |
|---|---:|---:|---:|
| `30_1` | 193.337 | 214.293 | 527 |
| `38_1` | 147.551 | 185.752 | 490 |
| `23_1` | 45.600 | 40.668 | 107 |
| `35_1` | 48.419 | 37.350 | 60 |
| `29_1` | 34.854 | 49.429 | 73 |

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

- `44_1` remains the highest join hard-exclusion case and is useful for route-phase / summit-transition visual QA.
- `30_1` and `38_1` remain high cumulative gain/loss review cases.
- `15_1`, `30_1`, and `36_1` remain elevation artifact review cases.
- `37_1` shows that low slope-valid rows can under-count continuous low-speed descent.

## Visual Finding: 37_1 Valid-Step Conservative Bias

Manual visual QA on `37_1` showed:

- calibrated elevation and raw elevation align well
- no visual evidence of global elevation join failure
- join-distance hard exclusions are concentrated near the terminal segment
- profile-distance jumps are frequent, but mostly represent soft route-profile phase ambiguity
- cumulative loss is likely under-counted because valid slope / gain-loss steps are sparse

Targeted row-level inspection showed:

### 3500-4100 sec summit-ish segment

- rows = 601
- `elevation_step_valid = True`: 1 row
- `elevation_step_valid = False`: 600 rows
- dominant exclusion: `STEP_DISTANCE_LT_3M`

### 4100-5500 sec high-elevation post-summit segment

- rows = 1401
- `elevation_step_valid = True`: 2 rows
- `elevation_step_valid = False`: 1399 rows
- dominant exclusions:
  - `STEP_DISTANCE_LT_3M`: 1178 rows
  - `PROFILE_DISTANCE_JUMP_GT_100M_WITH_SMALL_STEP_SOFT;STEP_DISTANCE_LT_3M`: 221 rows

Interpretation:

- The 4100-5500 sec segment visibly descends in elevation, but most per-second calibrated horizontal steps are below 3 m.
- Current v1k3 requires a per-row step distance >=3 m for valid slope / gain-loss contribution.
- Therefore, low-speed continuous descent can be under-counted even when the elevation trend is visually plausible.
- This is not a v1k4 plotter failure. It is a future v1k3b / v1k5 gain-loss policy improvement item.

Future improvement:

- add aggregated low-speed elevation step policy
- accumulate consecutive representative, time-valid, non-artifact rows
- allow small per-second steps to form a valid segment once cumulative horizontal distance or time-window threshold is met
- preserve existing hard gates for high join distance, elevation artifact, and suspicious profile-distance jump

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

Row-level and visual QA showed repeated alternation between early-route and late-route `elevation_profile_dist_m` values. This appears in several activities and is best interpreted as spatial-nearest profile ambiguity around self-near / overlapping route sections.

Examples:

- `30_1`: profile distance around `10` m and `4178` m
- `44_1`: profile distance around `0` m and `4187` m
- `15_1`: profile distance around `180` m and `4009` m
- `36_1`: profile distance around `13` m and `4172` m

Current behavior:

- v1k3 does not solve route phase
- v1k3 labels ambiguity as soft QA evidence
- v1k3 hard-excludes high join-distance / suspicious elevation-delta rows from gain/loss
- v1k4 makes route-profile jumps visible for reviewer inspection
- data is preserved for downstream review

Future fix:

- route-phase-aware IB1E profile candidate selection

## Protected Semantics

The following boundaries are mandatory:

- raw data is never overwritten
- v1d3-v1i, v1j, v1k, v1k2, v1k2a, and v1k3 outputs remain immutable inputs
- wrong-route is preserved and is not projected back to canonical mainline elevation
- connector is preserved and is not classified as `MAINLINE_CORE`
- off-target and low-confidence rows use raw fallback or review policy
- duplicate timestamp non-representative rows do not produce speed/slope
- motion artifact rows are labeled for review, not silently deleted
- elevation artifact rows are labeled for review, not silently deleted
- v1k4 is read-only and does not update source CSV/JSON outputs
- legacy recovery must not automatically restore `usable=True`

## Not Implemented in v1k4

- PNG export
- route-phase-aware elevation join
- correction of v1k3 gain/loss under-counting
- NLSC row-level lookup outside IB1E profile
- facility/radar evidence
- THCI recomputation
- formal activity/model inclusion gate

## Remaining Repository Items

Not part of this pipeline node:

- `folder_inventory_depth4.csv`
- `folder_role_audit_depth4.csv`
- `scripts/ib3_activity_environment/ib3a_rc_label_transition_continuity_v1f_before_v1f2_patch.py`
- old v1h/v1h2 plotting scripts

Separate review:

- `configs/risk_semantics/ib3a_rc_v1l_osm_facility_radar_evidence_catalog_v1.csv`

## Next Development Stage

Recommended next stage:

- document v1k4 convergence in `runs/` and README
- optionally implement v1k3b / v1k5 aggregated low-speed gain/loss policy

Still deferred:

- v1l OSM facility interaction / THCI radar evidence
- IB3F-RC activity-level feature aggregation
- IB3H-RC formal model inclusion gate
- v1e2 / v1h2 summit-anchor smoothing / hysteresis
