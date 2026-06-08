# Latest Handoff - IB3A-RC v1k2 Motion and Artifact QA

Date: 2026-06-07

## Current Status

IB3A-RC has completed the qixing_lengshuikeng full26 sequence through:

- v1d3-v1i evidence and classification layer
- v1j display trajectory layer
- v1k minimal horizontal calibrated activity dataset layer
- v1k2 calibrated motion dataset layer
- v1k2a motion artifact classification and HTML QA layer

Relevant commits:

- `581f511 Add IB3A-RC full-batch candidate labeling and wrong-route QA`
- `0b04c81 Add IB3A-RC display trajectory refit layer`
- `70e8ffe Add IB3A-RC calibrated activity dataset horizontal layer`
- `5076517 Add IB3A-RC calibrated motion and artifact QA layers`

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
- generates HTML QA decisions, review reasons, and backend usage hints

v1k2a does not fix upstream summit-anchor rules. It identifies artifacts for review.

## Full26 Evidence

### v1k2

Script:

- `scripts/ib3_activity_environment/ib3a_rc_build_calibrated_motion_v1k2.py`

Output root:

- `outputs/ib3a_rc_calibrated_motion_v1k2_qixing_lengshuikeng_duplicate_policy_full26_qa`

Evidence:

- PASS / FAIL = 26 / 0
- total rows = 345,979
- CSV / summary JSON / provenance JSON = 26 / 26 / 26
- row count and row order preserved
- protected fields changed = 0
- v1k SHA-256 unchanged
- non-representative speed rows = 0
- route_class / wrong-route / connector / off-target mismatch = 0
- heart_rate_bpm mismatch = 0
- forbidden elevation / NLSC / facility / radar / THCI fields = 0

Duplicate timestamp policy:

- timestamp groups = 215,259
- duplicate groups = 58,973
- representative rows = 215,259
- non-representative rows = 130,720
- mixed route/source/membership groups = 449 / 449 / 449
- mixed wrong-route groups = 0

Movement summary:

- `MOVING` = 97,331 rows / 103,192 sec
- `SLOW_MOVING` = 26,612 rows / 28,146 sec
- `STOPPED` = 11,877 rows / 12,322 sec
- `WRONG_ROUTE_MOVING` = 1,089 rows / 1,090 sec
- `OFF_TARGET_MOVING` = 0 rows / 0 sec
- `LOW_CONFIDENCE_REVIEW` = 52,240 rows / 55,022 sec
- `DUPLICATE_TIMESTAMP_NON_REPRESENTATIVE` = 130,720 rows
- `TIME_INVALID` = 26 rows
- `GPS_DRIFT_SUSPECTED` = 1,529 rows

Route-class distance distribution:

- `MAINLINE_CORE` = 105,522.54 m
- `OFF_TARGET` = 20,213.07 m
- `MAINLINE_SUMMIT_STAY` = 5,605.17 m
- `CONNECTOR` = 2,852.81 m
- `WRONG_ROUTE` = 834.27 m

### v1k2a

Scripts:

- `scripts/ib3_activity_environment/ib3a_rc_classify_motion_artifacts_v1k2a.py`
- `scripts/ib3_activity_environment/ib3a_rc_plot_motion_artifacts_v1k2a.py`
- `scripts/ib3_activity_environment/ib3a_rc_plot_calibrated_motion_v1k2.py`

Output root:

- `outputs/ib3a_rc_calibrated_motion_artifacts_v1k2a_qixing_lengshuikeng_full26_qa`

HTML root:

- `outputs/ib3a_rc_calibrated_motion_artifacts_v1k2a_qixing_lengshuikeng_html`

Evidence:

- PASS / FAIL = 26 / 0
- protected fields changed = 0
- input SHA-256 unchanged
- forbidden new columns = none

Top artifact cases:

- `44_1` = 196 artifacts, 156 summit artifacts
- `45_1` = 147 artifacts, 124 summit artifacts
- `23_1` = 125 artifacts, 52 summit artifacts
- `36_1` = 83 artifacts, 37 summit artifacts
- `28_1` = 82 artifacts, 55 summit artifacts
- `42_1` = 81 artifacts, 29 summit artifacts
- `48_1` = 75 artifacts, 29 summit artifacts
- `46_1` = 74 artifacts, 22 summit artifacts

## Backend Usage Rules

Normal speed / fitness analytics should use rows satisfying:

- `motion_representative_flag = True`
- `time_interval_valid = True`
- `motion_artifact_flag = False`
- `movement_state in [MOVING, SLOW_MOVING, STOPPED]`
- `backend_use_policy = ANALYTICS_READY`
- `route_class in [MAINLINE_CORE, CONNECTOR, MAINLINE_SUMMIT_STAY]`

Rows should be preserved as behavior/QA evidence, but should not be used as normal speed-model input, when they are:

- `OFF_TARGET`
- `WRONG_ROUTE`
- `GPS_DRIFT_SUSPECTED`
- `DUPLICATE_TIMESTAMP_NON_REPRESENTATIVE`
- `LOW_CONFIDENCE_REVIEW`
- `UNKNOWN_REVIEW`
- `motion_artifact_flag = True`

## Known Issue / Future Improvement

### 44_1 Fragmented Summit Anchor Activation

Observation:

- `44_1` has the highest artifact count: 196 artifacts and 156 summit artifacts.
- Episode review showed summit-anchor episodes are fragmented.
- Each summit-anchor episode has small raw-distance delta, mostly under 20 m.
- Calibrated distance can jump when the trajectory repeatedly switches between `REVIEWED_SUMMIT_ANCHOR` and `OSM_MAINLINE_CANDIDATE_PROJECTION`.

Interpretation:

- This is not clear evidence that the entire downhill segment was swallowed by summit anchor.
- It is better interpreted as fragmented summit-anchor activation / summit-anchor-mainline oscillation.
- v1k2a correctly detects this as motion artifact.

Future fix:

- Do not fix this in v1k2a.
- Future `v1e2` / `v1h2` should implement summit-anchor episode smoothing, hysteresis, and possibly `SUMMIT_VICINITY_MOVING`.

## Remaining Working Tree Items

Keep outside this documentation closeout:

- `folder_inventory_depth4.csv`: inventory artifact; do not include
- `folder_role_audit_depth4.csv`: inventory artifact; do not include
- `configs/risk_semantics/ib3a_rc_v1l_osm_facility_radar_evidence_catalog_v1.csv`: separate v1l work
- `scripts/ib3_activity_environment/ib3a_rc_label_transition_continuity_v1f_before_v1f2_patch.py`: backup; do not include
- `scripts/ib3_activity_environment/ib3a_rc_plot_motion_artifacts_v1k2a.py.before_qa_decision_patch`: backup; delete or ignore
- old v1h/v1h2 plotting scripts: archive/delete review required

## Next Development

Next recommended stage:

- v1k3 calibrated elevation, slope, and cumulative gain/loss

Still deferred:

- v1l OSM facility interaction / THCI radar evidence
- IB3F-RC activity-level feature aggregation
- IB3H-RC formal model inclusion gate
- v1e2 / v1h2 summit-anchor smoothing / hysteresis
