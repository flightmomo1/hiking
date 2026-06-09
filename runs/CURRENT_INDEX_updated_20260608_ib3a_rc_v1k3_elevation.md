# Current Index - 2026-06-08 IB3A-RC v1k3 Elevation and Gain-Loss

## Current Commits

Core engineering commits now closed in this branch:

- `581f511` - IB3A-RC v1d3-v1i full-batch candidate labeling and wrong-route QA
- `0b04c81` - IB3A-RC v1j display trajectory refit
- `70e8ffe` - IB3A-RC v1k minimal horizontal calibrated activity dataset
- `5076517` - IB3A-RC calibrated motion and artifact QA layers
- `855f5a3` - IB3A-RC calibrated elevation and gain-loss layer

Documentation commits already present before this node:

- `1d0ad7c` - Document IB3A-RC v1k horizontal convergence
- `3da979f` - Document IB3A-RC v1k2 motion convergence

## Route Formal Branch vs Activity RC Branch

The RC branch remains an activity candidate-route branch. It is not a downstream consumer of `IB0B mainline`.

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
→ IB3B-RC v1j display trajectory QA
→ IB3K-RC v1k horizontal calibrated activity dataset
→ IB3K-RC v1k2 calibrated motion dataset
→ IB3G-RC v1k2a motion artifact QA
→ IB3K-RC v1k3 calibrated elevation / slope / cumulative gain-loss
```

## Current Scripts

Evidence and classification:

- `scripts/ib3_activity_environment/ib3a_rc_select_candidate_route_v1.py`
- `scripts/ib3_activity_environment/ib3a_rc_apply_summit_anchor_stabilization_v1e.py`
- `scripts/ib3_activity_environment/ib3a_rc_label_transition_continuity_v1f.py`
- `scripts/ib3_activity_environment/ib3a_rc_detect_off_target_route_v1g.py`
- `scripts/ib3_activity_environment/ib3a_rc_consolidate_off_target_zones_v1g2.py`
- `scripts/ib3_activity_environment/ib3a_rc_label_mainline_membership_v1h.py`
- `scripts/ib3_activity_environment/ib3a_rc_apply_manual_wrong_route_seed_v1i.py`

Display and calibrated dataset:

- `scripts/ib3_activity_environment/ib3a_rc_build_display_trajectory_refit_v1j.py`
- `scripts/ib3_activity_environment/ib3a_rc_build_calibrated_activity_dataset_v1k.py`
- `scripts/ib3_activity_environment/ib3a_rc_build_calibrated_motion_v1k2.py`
- `scripts/ib3_activity_environment/ib3a_rc_classify_motion_artifacts_v1k2a.py`
- `scripts/ib3_activity_environment/ib3a_rc_build_calibrated_elevation_v1k3.py`

Plot / QA scripts currently available from earlier nodes:

- `scripts/ib3_activity_environment/ib3a_rc_plot_calibrated_motion_v1k2.py`
- `scripts/ib3_activity_environment/ib3a_rc_plot_motion_artifacts_v1k2a.py`

Route-level review config:

- `configs/ib3_review/qixing_lengshuikeng_wrong_route_way_review_v1.csv`

## Current Full26 Roots

- v1d3: `outputs/ib3a_rc_candidate_selection_v1d3_qixing_lengshuikeng_full26_candidate_stability_smoke`
- v1i: `outputs/ib3a_rc_candidate_selection_v1i_qixing_lengshuikeng_full26_manual_wrong_route_qa`
- v1j: `outputs/ib3a_rc_display_trajectory_refit_v1j_qixing_lengshuikeng_full26_review`
- v1k: `outputs/ib3a_rc_calibrated_activity_dataset_v1k_qixing_lengshuikeng_horizontal_full26`
- v1k2: `outputs/ib3a_rc_calibrated_motion_v1k2_qixing_lengshuikeng_duplicate_policy_full26_qa`
- v1k2a: `outputs/ib3a_rc_calibrated_motion_artifacts_v1k2a_qixing_lengshuikeng_full26_qa`
- v1k3: `outputs/ib3a_rc_calibrated_elevation_v1k3_join_hard_gate_full26_qa`

## Current Convergence

- v1d3-v1i full26 evidence/classification: complete
- v1j full26 display trajectory: PASS 26/26
- v1k minimal horizontal dataset: PASS 26/26
- v1k2 calibrated motion dataset: PASS 26/26
- v1k2a motion artifact classification: PASS 26/26
- v1k3 calibrated elevation / slope / cumulative gain-loss: PASS 26/26
- total rows: 345,979
- protected-field changes: 0 across v1k/v1k2/v1k2a/v1k3 audits
- v1k source SHA-256 unchanged during v1k2
- v1k2 source SHA-256 unchanged during v1k2a
- v1k2a source SHA-256 unchanged during v1k3
- forbidden facility / radar / THCI fields in v1k3: 0

## v1k3 Scope

v1k3 adds conservative calibrated elevation and gain-loss features:

- `calibrated_elevation_m`
- `calibrated_elevation_source`
- `calibrated_elevation_confidence`
- `calibrated_elevation_review_required`
- `elevation_lookup_method`
- `elevation_join_dist_m`
- `elevation_profile_dist_m`
- `elevation_profile_ele_smooth_m`
- `elevation_profile_ambiguous_flag`
- `elevation_profile_dist_jump_flag`
- `calibrated_delta_elevation_m`
- `calibrated_slope_pct`
- `elevation_step_valid`
- `calibrated_cumulative_gain_m`
- `calibrated_cumulative_loss_m`
- `elevation_artifact_flag`
- `gain_loss_excluded_reason`

Inputs:

- v1k2a calibrated motion artifact CSV
- IB1E route profile contour-window terrain enriched CSV

Policy:

- `MAINLINE_CORE`, `MAINLINE_SUMMIT_STAY`, and `CONNECTOR` use calibrated lat/lon spatial nearest join to IB1E route profile.
- `WRONG_ROUTE` uses raw elevation fallback.
- `OFF_TARGET` / raw GPS fallback uses raw elevation fallback.
- Profile ambiguity is soft QA evidence.
- Profile distance jump is soft QA evidence unless paired with suspicious join distance or elevation delta.
- `elevation_join_dist_m > 10m` is hard-excluded from slope/gain-loss.
- Elevation artifact rows are labeled and excluded from slope/gain-loss.

## v1k3 Full26 QA Highlights

Output root:

- `outputs/ib3a_rc_calibrated_elevation_v1k3_join_hard_gate_full26_qa`

Full26 result:

- PASS / FAIL = 26 / 0
- total rows = 345,979
- row count and order preserved
- protected fields changed = 0
- input SHA-256 unchanged = True for all 26 activities

Review-focus activities:

- `30_1`: high cumulative gain/loss (`gain=193.34`, `loss=214.29`)
- `38_1`: high cumulative gain/loss (`gain=147.55`, `loss=185.75`)
- `44_1`: highest join hard-excluded rows (`191`)
- `15_1`: highest elevation artifact rows (`45`)
- `36_1`: low slope-valid rows (`29`) and elevated artifact rows (`24`)

## Layer Boundary

- v1j is a display-only trajectory selection layer.
- v1k is a horizontal calibrated activity dataset skeleton.
- v1k2 adds calibrated horizontal distance, speed, and movement state.
- v1k2a classifies horizontal motion artifacts.
- v1k3 adds calibrated elevation, conservative slope, and cumulative gain/loss.
- v1k3 does not produce visual QA HTML/PNG.
- v1k3 does not add OSM facility/radar evidence or THCI recomputation.
- v1k3 is not route-phase-aware; it uses spatial nearest join plus conservative review gates.

## Backend Training Filters

Normal speed / fitness analytics should use:

- `motion_representative_flag = True`
- `time_interval_valid = True`
- `motion_artifact_flag = False`
- `movement_state in [MOVING, SLOW_MOVING, STOPPED]`
- `backend_use_policy = ANALYTICS_READY`
- `route_class in [MAINLINE_CORE, CONNECTOR, MAINLINE_SUMMIT_STAY]`

Normal elevation / slope / gain-loss analytics should additionally use:

- `elevation_step_valid = True`
- `elevation_artifact_flag = False`
- `calibrated_elevation_review_required = False` where strict high-confidence elevation is required
- `gain_loss_excluded_reason` is empty or does not contain hard exclusion reasons

Behavior / QA evidence should preserve but exclude from normal model training when rows are:

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

## Working Tree Classification

Do not include in this closeout unless explicitly requested:

- inventory CSV modifications
- generated outputs
- `scripts/ib3_activity_environment/ib3a_rc_build_calibrated_elevation_v1k3.py.before_profile_ambiguity_patch`
- `scripts/ib3_activity_environment/ib3a_rc_label_transition_continuity_v1f_before_v1f2_patch.py`
- old v1h/v1h2 plotting scripts

Handle separately:

- v1l facility/radar catalog
- v1k3d or v1k4 elevation visual QA plotter

## Next Recommended Stage

Design and implement a separate elevation visual QA layer:

- recommended name: `IB3K-RC v1k3d elevation QA plotter` or `IB3K-RC v1k4 elevation visual QA`
- produce elevation timeline PNG/HTML
- mark join hard-excluded rows
- mark profile ambiguity / profile distance jump
- mark elevation artifacts
- show route-class / movement-state background bands

Do not include facility/radar evidence or THCI recomputation in that visual QA layer.
