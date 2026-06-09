# Latest Handoff - IB3A-RC v1k3 Elevation and Gain-Loss

Date: 2026-06-08

## Current Status

IB3A-RC has completed the qixing_lengshuikeng full26 sequence through:

- v1d3-v1i evidence and classification layer
- v1j display trajectory layer
- v1k minimal horizontal calibrated activity dataset layer
- v1k2 calibrated motion dataset layer
- v1k2a motion artifact classification layer
- v1k3 calibrated elevation / slope / cumulative gain-loss layer

Relevant commits:

- `581f511 Add IB3A-RC full-batch candidate labeling and wrong-route QA`
- `0b04c81 Add IB3A-RC display trajectory refit layer`
- `70e8ffe Add IB3A-RC calibrated activity dataset horizontal layer`
- `5076517 Add IB3A-RC calibrated motion and artifact QA layers`
- `855f5a3 Add IB3A-RC calibrated elevation and gain-loss layer`

## Correct Pipeline Interpretation

IB3A-RC is not downstream of `IB0B mainline`. It branches earlier from candidate route evidence.

Formal route branch:

```text
IA1 refreshed OSM raw
→ IB0 route match
→ IB0C anchors
→ IB0A control point projection
→ IB0A-2 route-axis anchor/component QA
→ IB0B mainline
→ IB0D trimmed mainline
→ IB1A route profile
→ IB1C OSM semantics
→ IB1C semantic risk
→ IB1G NLSC contour window
→ IB1E OSM + NLSC terrain
→ IB2D route risk / radar
```

Activity RC branch:

```text
IA1 refreshed OSM raw
→ IB0 route match
→ IB0C anchors
→ IB0A control point projection
→ IB0A-2 route-axis anchor/component QA
→ IB0-CAND adapter
→ candidate_route_points.csv
→ IB3A-RC v1d3-v1i
→ IB3B-RC v1j
→ IB3K-RC v1k
→ IB3K-RC v1k2
→ IB3G-RC v1k2a
→ IB3K-RC v1k3
```

## Layer Roles

### v1d3-v1i

- v1d3: candidate projection, context/policy, and movement stability evidence
- v1e: summit anchor stabilization
- v1f: transition continuity evidence
- v1g/v1g2: off-target detection and zone consolidation
- v1h: mainline, connector, and non-mainline membership
- v1i: route-level manual wrong-route labeling

The route-level wrong-route config is:

- `configs/ib3_review/qixing_lengshuikeng_wrong_route_way_review_v1.csv`

### v1j

v1j is display-only:

- produces `display_lat` / `display_lon`
- records display coordinate source and reason
- produces raw-vs-display QA
- does not modify v1d3-v1i
- does not produce calibrated speed, distance, elevation, or movement state

### v1k Minimal Horizontal

v1k is the first backend-facing calibrated dataset skeleton:

- produces `calibrated_lat` / `calibrated_lon`
- records horizontal calibration source, confidence, distance, and review status
- preserves route class, connector, off-target, and wrong-route semantics
- produces backend use policy
- does not calculate speed, distance, elevation, movement state, GPS drift, NLSC, facility/radar evidence, or THCI

### v1k2 Calibrated Motion

v1k2 extends v1k into calibrated horizontal motion:

- duplicate timestamp representative policy
- `calibrated_step_distance_m`
- `calibrated_horizontal_distance_m`
- `calibrated_speed_mps`
- `movement_state`
- GPS drift suspicion and low-confidence review states

v1k2 keeps all original rows. Duplicate timestamp non-representative rows are preserved but do not produce speed.

### v1k2a Motion Artifact QA

v1k2a is a review layer:

- classifies speed and distance artifacts
- explains source transition jumps
- explains summit-anchor transition jumps
- explains raw-fallback transition jumps
- records backend usage hints

v1k2a does not fix upstream summit-anchor rules. It identifies artifacts for review.

### v1k3 Calibrated Elevation

v1k3 extends v1k2a into calibrated elevation and conservative gain/loss:

- joins calibrated lat/lon to IB1E route profile by spatial nearest
- falls back to raw elevation for wrong-route and off-target rows
- produces `calibrated_elevation_m`
- produces `calibrated_delta_elevation_m`
- produces conservative `calibrated_slope_pct`
- produces `calibrated_cumulative_gain_m` / `calibrated_cumulative_loss_m`
- labels elevation profile ambiguity and distance jumps
- hard-excludes high join-distance rows from slope/gain-loss
- labels elevation artifacts
- preserves all upstream rows and fields

## Full26 Evidence

### v1k3

Script:

- `scripts/ib3_activity_environment/ib3a_rc_build_calibrated_elevation_v1k3.py`

Commit:

- `855f5a3 Add IB3A-RC calibrated elevation and gain-loss layer`

Input root:

- `outputs/ib3a_rc_calibrated_motion_artifacts_v1k2a_qixing_lengshuikeng_full26_qa`

IB1E profile input:

- `outputs/ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa/qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b/qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b_route_profile_contour_window_terrain_enriched.csv`

Output root:

- `outputs/ib3a_rc_calibrated_elevation_v1k3_join_hard_gate_full26_qa`

Evidence:

- PASS / FAIL = 26 / 0
- total rows = 345,979
- row count and row order preserved
- protected fields changed = 0
- input SHA-256 unchanged = True for all 26 activities
- no facility/radar/THCI fields added
- no v1k3 HTML/PNG visual QA outputs produced

## v1k3 QA Summary

### Highest cumulative gain/loss

| Activity | Gain m | Loss m | Slope-valid rows | Interpretation |
|---|---:|---:|---:|---|
| `30_1` | 193.34 | 214.29 | 527 | high but supported by many valid slope rows |
| `38_1` | 147.55 | 185.75 | 490 | high but supported by many valid slope rows |
| `23_1` | 45.60 | 40.67 | 107 | acceptable with review flags |
| `35_1` | 48.42 | 37.35 | 60 | acceptable with review flags |

### Highest join hard-excluded rows

| Activity | Rows |
|---|---:|
| `44_1` | 191 |
| `30_1` | 127 |
| `6_1` | 98 |
| `45_1` | 88 |
| `35_1` | 76 |
| `15_1` | 73 |

### Highest elevation artifacts

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

## Backend Usage Rules

Normal speed / fitness analytics should use rows satisfying:

- `motion_representative_flag = True`
- `time_interval_valid = True`
- `motion_artifact_flag = False`
- `movement_state in [MOVING, SLOW_MOVING, STOPPED]`
- `backend_use_policy = ANALYTICS_READY`
- `route_class in [MAINLINE_CORE, CONNECTOR, MAINLINE_SUMMIT_STAY]`

Normal elevation / slope / gain-loss analytics should additionally use:

- `elevation_step_valid = True`
- `elevation_artifact_flag = False`
- no hard exclusion reason in `gain_loss_excluded_reason`
- optionally `calibrated_elevation_review_required = False` for strict high-confidence elevation-only models

Rows should be preserved as behavior/QA evidence, but should not be used as normal speed/elevation-model input when they are:

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

## Known Issue / Future Improvement

### Route-Profile Phase Ambiguity

Observation:

- Row-level QA showed repeated alternation between early-route and late-route `elevation_profile_dist_m` values in several activities.
- Examples:
  - `30_1`: profile distance around `10` m and `4178` m
  - `44_1`: profile distance around `0` m and `4187` m
  - `15_1`: profile distance around `180` m and `4009` m
  - `36_1`: profile distance around `13` m and `4172` m

Interpretation:

- This is spatial-nearest route-profile phase ambiguity near self-near or overlapping route sections.
- v1k3 does not solve route phase.
- v1k3 controls obvious bad joins through soft review flags and hard exclusion gates.

Future fix:

- Implement route-phase-aware IB1E profile candidate selection.
- Add elevation visual QA plotter before treating slope/gain-loss as fully production-grade training features.

### 44_1 Fragmented Summit Anchor Activation

The earlier v1k2a node already identified `44_1` summit-anchor/mainline oscillation. v1k3 continues to treat `44_1` as a review focus because it has the highest join hard-excluded rows.

Future fix remains:

- Do not fix this in v1k3.
- Future `v1e2` / `v1h2` should implement summit-anchor episode smoothing, hysteresis, and possibly `SUMMIT_VICINITY_MOVING`.

## Remaining Working Tree Items

Keep outside this documentation closeout:

- `folder_inventory_depth4.csv`: inventory artifact; do not include
- `folder_role_audit_depth4.csv`: inventory artifact; do not include
- `configs/risk_semantics/ib3a_rc_v1l_osm_facility_radar_evidence_catalog_v1.csv`: separate v1l work
- `scripts/ib3_activity_environment/ib3a_rc_build_calibrated_elevation_v1k3.py.before_profile_ambiguity_patch`: backup; delete or ignore
- `scripts/ib3_activity_environment/ib3a_rc_label_transition_continuity_v1f_before_v1f2_patch.py`: backup; do not include
- old v1h/v1h2 plotting scripts: archive/delete review required

## Next Development

Next recommended stage:

- `IB3K-RC v1k3d elevation QA plotter` or `IB3K-RC v1k4 elevation visual QA`

Still deferred:

- v1l OSM facility interaction / THCI radar evidence
- IB3F-RC activity-level feature aggregation
- IB3H-RC formal model inclusion gate
- v1e2 / v1h2 summit-anchor smoothing / hysteresis
