# Current Index - 2026-06-07 IB3A-RC v1k2 Motion and Artifact QA

## Current Commits

- `581f511` - IB3A-RC v1d3-v1i full-batch candidate labeling and wrong-route QA
- `0b04c81` - IB3A-RC v1j display trajectory refit
- `70e8ffe` - IB3A-RC v1k minimal horizontal calibrated activity dataset
- `5076517` - IB3A-RC calibrated motion and artifact QA layers

## Route Formal Branch vs Activity RC Branch

The RC branch is not a downstream consumer of `IB0B mainline`.

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
- v1k2a HTML: `outputs/ib3a_rc_calibrated_motion_artifacts_v1k2a_qixing_lengshuikeng_html`

## Current Convergence

- v1d3-v1i full26 evidence/classification: complete
- v1j full26 display trajectory: PASS 26/26
- v1k minimal horizontal dataset: PASS 26/26
- v1k2 calibrated motion dataset: PASS 26/26
- v1k2a motion artifact classification: PASS 26/26
- total rows: 345,979
- protected-field changes: 0 across v1k/v1k2/v1k2a audits
- v1k source SHA-256 unchanged during v1k2
- v1k2 source SHA-256 unchanged during v1k2a
- forbidden elevation / NLSC / facility / radar / THCI fields: 0

## Layer Boundary

- v1j is a display-only trajectory selection layer.
- v1k is a horizontal calibrated activity dataset skeleton.
- v1k2 adds calibrated horizontal distance, speed, and movement state.
- v1k2a classifies motion artifacts and produces HTML QA decisions.
- v1k2/v1k2a do not perform NLSC elevation lookup, facility/radar evidence, or THCI recomputation.
- Wrong-route, connector, off-target, raw fallback, duplicate timestamp, and artifact semantics remain explicit.

## Backend Training Filters

Normal speed / fitness analytics should use:

- `motion_representative_flag = True`
- `time_interval_valid = True`
- `motion_artifact_flag = False`
- `movement_state in [MOVING, SLOW_MOVING, STOPPED]`
- `backend_use_policy = ANALYTICS_READY`
- `route_class in [MAINLINE_CORE, CONNECTOR, MAINLINE_SUMMIT_STAY]`

Behavior / QA evidence should preserve but exclude from normal speed model:

- `OFF_TARGET`
- `WRONG_ROUTE`
- `GPS_DRIFT_SUSPECTED`
- `DUPLICATE_TIMESTAMP_NON_REPRESENTATIVE`
- `LOW_CONFIDENCE_REVIEW`
- `UNKNOWN_REVIEW`
- `motion_artifact_flag = True`

## Working Tree Classification

Do not include in this closeout unless explicitly requested:

- inventory CSV modifications
- generated outputs
- `scripts/ib3_activity_environment/ib3a_rc_label_transition_continuity_v1f_before_v1f2_patch.py`
- `scripts/ib3_activity_environment/ib3a_rc_plot_motion_artifacts_v1k2a.py.before_qa_decision_patch`

Handle separately:

- v1l facility/radar catalog
- old v1h/v1h2 plotting scripts

## Next Recommended Stage

Design and implement v1k3:

- calibrated elevation
- calibrated delta elevation
- calibrated slope
- cumulative gain/loss
- elevation source/confidence/review flags

Do not include facility/radar evidence or THCI recomputation in v1k3.
