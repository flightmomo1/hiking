# Changelog - 2026-06-07 IB3A-RC v1k2 Motion and Artifact QA

## Completed Engineering Nodes

### v1d3-v1i Evidence and Classification

Commit:

- `581f511 Add IB3A-RC full-batch candidate labeling and wrong-route QA`

This node includes candidate projection and context, summit stabilization, transition evidence, off-target detection, zone consolidation, mainline membership, and route-level wrong-route rules.

### v1j Display Trajectory

Commit:

- `0b04c81 Add IB3A-RC display trajectory refit layer`

The qixing_lengshuikeng full26 run passed with 345,979 rows. v1j adds display coordinates and raw-vs-display QA only. It does not create calibrated fields.

### v1k Minimal Horizontal Dataset

Commit:

- `70e8ffe Add IB3A-RC calibrated activity dataset horizontal layer`

The qixing_lengshuikeng full26 run passed:

- PASS / FAIL / SKIPPED = 26 / 0 / 0
- total rows = 345,979
- calibrated CSV / summary / provenance = 26 / 26 / 26
- row count and order preserved
- protected fields changed = 0
- v1i/v1j hashes unchanged
- raw alias mismatch = 0
- unresolved rows = 0
- forbidden columns = 0
- semantic mismatch checks = 0

### v1k2 Calibrated Motion Dataset

Commit:

- `5076517 Add IB3A-RC calibrated motion and artifact QA layers`

v1k2 adds calibrated horizontal motion fields on top of v1k without modifying v1k/v1j/v1i outputs.

Script:

- `scripts/ib3_activity_environment/ib3a_rc_build_calibrated_motion_v1k2.py`

Output root:

- `outputs/ib3a_rc_calibrated_motion_v1k2_qixing_lengshuikeng_duplicate_policy_full26_qa`

Full26 result:

- PASS / FAIL = 26 / 0
- total rows = 345,979
- calibrated motion CSV / summary JSON / provenance JSON = 26 / 26 / 26
- row count and order preserved
- protected fields changed = 0
- v1k SHA-256 unchanged
- non-representative speed rows = 0
- route_class / wrong-route / connector / off-target mismatch = 0
- heart_rate_bpm mismatch = 0
- forbidden elevation / NLSC / facility / radar / THCI fields = 0

Duplicate timestamp policy:

- total rows = 345,979
- timestamp groups = 215,259
- duplicate groups = 58,973
- representative rows = 215,259
- non-representative rows = 130,720
- mixed route/source/membership groups = 449 / 449 / 449
- mixed wrong-route groups = 0

Movement state summary:

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

### v1k2a Motion Artifact Classification and HTML QA

Commit:

- `5076517 Add IB3A-RC calibrated motion and artifact QA layers`

v1k2a classifies speed and distance artifacts detected in v1k2. It is a QA/review layer and does not modify the v1k2 source outputs.

Scripts:

- `scripts/ib3_activity_environment/ib3a_rc_classify_motion_artifacts_v1k2a.py`
- `scripts/ib3_activity_environment/ib3a_rc_plot_motion_artifacts_v1k2a.py`
- `scripts/ib3_activity_environment/ib3a_rc_plot_calibrated_motion_v1k2.py`

Output roots:

- artifact CSV/summary: `outputs/ib3a_rc_calibrated_motion_artifacts_v1k2a_qixing_lengshuikeng_full26_qa`
- HTML QA: `outputs/ib3a_rc_calibrated_motion_artifacts_v1k2a_qixing_lengshuikeng_html`

Full26 result:

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

Example HTML QA decision for `23_1`:

- QA decision = `PASS_WITH_SUMMIT_ANCHOR_TRANSITION_ARTIFACT`
- 125 speed/artifact rows require review
- 52 artifacts are summit-anchor transition related
- 6,242 rows are `OFF_TARGET` and should not be treated as mainline training data
- raw/calibrated distance ratio = 0.801, so distance divergence review is recommended
- 4 calibrated step-distance jumps exceed 20 m
- 2,035 rows are `LOW_CONFIDENCE_REVIEW`

## v1k2 / v1k2a Boundaries Preserved

- Raw activity data was not overwritten.
- v1d3-v1i, v1j, and v1k outputs remain immutable inputs.
- Heart-rate values remain raw and were not spatially refit.
- Wrong-route rows remain outside canonical mainline.
- Connector rows remain distinct from `MAINLINE_CORE`.
- Off-target rows remain behavior/QA evidence and are not mainline training rows.
- Duplicate timestamp rows are preserved; only representative rows produce motion speed/distance.
- Motion artifact rows are preserved and labeled, not silently deleted.
- No calibrated elevation, NLSC lookup, facility/radar evidence, or THCI recomputation was performed.
- Legacy automatic usable recovery remains excluded.

## Backend Usage Policy

Normal speed / fitness analytics should use rows satisfying all of the following:

- `motion_representative_flag = True`
- `time_interval_valid = True`
- `motion_artifact_flag = False`
- `movement_state in [MOVING, SLOW_MOVING, STOPPED]`
- `backend_use_policy = ANALYTICS_READY`
- `route_class in [MAINLINE_CORE, CONNECTOR, MAINLINE_SUMMIT_STAY]`

Behavior / QA evidence should be preserved but not used as normal speed-model input when rows are:

- `OFF_TARGET`
- `WRONG_ROUTE`
- `GPS_DRIFT_SUSPECTED`
- `DUPLICATE_TIMESTAMP_NON_REPRESENTATIVE`
- `LOW_CONFIDENCE_REVIEW`
- `UNKNOWN_REVIEW`
- `motion_artifact_flag = True`

## Known Issue: Fragmented Summit Anchor Activation

`44_1` exposed fragmented summit anchor activation near the summit.

Interpretation:

- This is not clear evidence that the entire downhill segment was swallowed by summit anchor.
- Episode review showed each summit-anchor episode has small raw-distance delta, mostly under 20 m.
- However, calibrated distance can jump when the trajectory repeatedly transitions between `REVIEWED_SUMMIT_ANCHOR` and `OSM_MAINLINE_CANDIDATE_PROJECTION`.
- v1k2a correctly detects this as summit-anchor transition artifact.

Future fix:

- Do not fix this in v1k2a.
- Future `v1e2` / `v1h2` should implement summit-anchor episode smoothing, hysteresis, and possibly `SUMMIT_VICINITY_MOVING`.

## Next Stage

Next planned stage:

- `v1k3` calibrated elevation / slope / cumulative gain-loss

Deferred:

- `v1l` OSM facility interaction / THCI radar evidence
- `IB3F-RC` activity-level feature aggregation
- `IB3H-RC` formal model inclusion gate
- `v1e2` / `v1h2` summit-anchor smoothing / hysteresis
