# Current Index - 2026-06-07 IB3A-RC v1k Minimal Horizontal

## Current Commits

- `581f511` - IB3A-RC v1d3-v1i full-batch candidate labeling and wrong-route QA
- `0b04c81` - IB3A-RC v1j display trajectory refit
- `70e8ffe` - IB3A-RC v1k minimal horizontal calibrated activity dataset

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

Route-level review config:

- `configs/ib3_review/qixing_lengshuikeng_wrong_route_way_review_v1.csv`

## Current Full26 Roots

- v1d3: `outputs/ib3a_rc_candidate_selection_v1d3_qixing_lengshuikeng_full26_candidate_stability_smoke`
- v1i: `outputs/ib3a_rc_candidate_selection_v1i_qixing_lengshuikeng_full26_manual_wrong_route_qa`
- v1j: `outputs/ib3a_rc_display_trajectory_refit_v1j_qixing_lengshuikeng_full26_review`
- v1k: `outputs/ib3a_rc_calibrated_activity_dataset_v1k_qixing_lengshuikeng_horizontal_full26`

## Current Convergence

- v1d3-v1i full26 evidence/classification: complete
- v1j full26 display trajectory: PASS 26/26
- v1k minimal horizontal dataset: PASS 26/26
- total rows: 345,979
- unresolved rows: 0
- forbidden columns: 0
- protected-field changes: 0

## Layer Boundary

- v1j is a display-only trajectory selection layer.
- v1k is a horizontal calibrated dataset skeleton.
- v1k does not yet calculate speed, distance, elevation, movement state, GPS drift, NLSC, facilities, radar, or THCI.
- Wrong-route, connector, off-target, and raw fallback semantics remain explicit.

## Working Tree Classification

Do not include in this closeout:

- inventory CSV modifications
- v1f before-patch backup
- generated outputs

Handle separately:

- v1l facility/radar catalog
- old v1h/v1h2 plotting scripts

## Next Recommended Stage

Design v1k2:

- calibrated step and horizontal distance
- calibrated speed
- movement state
- GPS drift suspicion
- low-speed uncertainty

Do not begin NLSC elevation, facility/radar evidence, or THCI recomputation as part of v1k2 horizontal planning.

