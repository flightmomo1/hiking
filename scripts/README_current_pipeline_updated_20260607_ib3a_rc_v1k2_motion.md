# Current Pipeline Update - IB3A-RC v1k2 Motion and Artifact QA

Date: 2026-06-07

## Current Status

The qixing_lengshuikeng IB3A-RC full26 activity flow is converged through calibrated horizontal motion and motion artifact QA:

1. v1d3-v1i evidence/classification
2. v1j display trajectory
3. v1k minimal horizontal calibrated activity dataset
4. v1k2 calibrated motion dataset
5. v1k2a motion artifact classification and HTML QA

Commits:

- `581f511 Add IB3A-RC full-batch candidate labeling and wrong-route QA`
- `0b04c81 Add IB3A-RC display trajectory refit layer`
- `70e8ffe Add IB3A-RC calibrated activity dataset horizontal layer`
- `5076517 Add IB3A-RC calibrated motion and artifact QA layers`

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
| v1k2a | Motion artifact QA | Adds artifact type/reason and HTML QA decision |

## v1k2 Calibrated Motion Full26

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

### Duplicate Timestamp Representative Policy

| Metric | Count |
|---|---:|
| total rows | 345,979 |
| timestamp groups | 215,259 |
| duplicate groups | 58,973 |
| representative rows | 215,259 |
| non-representative rows | 130,720 |
| mixed route/source/membership groups | 449 / 449 / 449 |
| mixed wrong-route groups | 0 |

Policy:

- all rows are preserved
- one representative row is selected per timestamp group
- only representative rows produce speed/distance
- non-representative rows are retained as `DUPLICATE_TIMESTAMP_NON_REPRESENTATIVE`

### Movement State Summary

| Movement state | Rows / duration |
|---|---:|
| `MOVING` | 97,331 rows / 103,192 sec |
| `SLOW_MOVING` | 26,612 rows / 28,146 sec |
| `STOPPED` | 11,877 rows / 12,322 sec |
| `WRONG_ROUTE_MOVING` | 1,089 rows / 1,090 sec |
| `OFF_TARGET_MOVING` | 0 rows / 0 sec |
| `LOW_CONFIDENCE_REVIEW` | 52,240 rows / 55,022 sec |
| `DUPLICATE_TIMESTAMP_NON_REPRESENTATIVE` | 130,720 rows |
| `TIME_INVALID` | 26 rows |
| `GPS_DRIFT_SUSPECTED` | 1,529 rows |

### Route-Class Distance Distribution

| Route class | Distance |
|---|---:|
| `MAINLINE_CORE` | 105,522.54 m |
| `OFF_TARGET` | 20,213.07 m |
| `MAINLINE_SUMMIT_STAY` | 5,605.17 m |
| `CONNECTOR` | 2,852.81 m |
| `WRONG_ROUTE` | 834.27 m |

## v1k2a Motion Artifact Classification Full26

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

Artifact type examples:

- `SUMMIT_ANCHOR_TRANSITION_JUMP`
- `SOURCE_TRANSITION_JUMP`
- `RAW_FALLBACK_TRANSITION_JUMP`
- `CALIBRATED_SPEED_OUTLIER`
- `DISTANCE_JUMP`

Top artifact activities:

| Activity | Artifacts | Summit artifacts |
|---|---:|---:|
| `44_1` | 196 | 156 |
| `45_1` | 147 | 124 |
| `23_1` | 125 | 52 |
| `36_1` | 83 | 37 |
| `28_1` | 82 | 55 |
| `42_1` | 81 | 29 |
| `48_1` | 75 | 29 |
| `46_1` | 74 | 22 |

## Example QA Decision: 23_1

HTML QA decision:

- `PASS_WITH_SUMMIT_ANCHOR_TRANSITION_ARTIFACT`

Review reasons:

- 125 speed/artifact rows require review
- 52 artifacts are summit-anchor transition related
- 6,242 rows are `OFF_TARGET` and should not be treated as mainline training data
- raw/calibrated distance ratio = 0.801, so distance divergence review is recommended
- 4 calibrated step-distance jumps exceed 20 m
- 2,035 rows are `LOW_CONFIDENCE_REVIEW`

## Backend Use Rules

Normal speed / fitness analytics should use rows satisfying:

- `motion_representative_flag = True`
- `time_interval_valid = True`
- `motion_artifact_flag = False`
- `movement_state in [MOVING, SLOW_MOVING, STOPPED]`
- `backend_use_policy = ANALYTICS_READY`
- `route_class in [MAINLINE_CORE, CONNECTOR, MAINLINE_SUMMIT_STAY]`

Rows should be preserved for behavior/QA evidence but not used as normal speed-model input when they are:

- `OFF_TARGET`
- `WRONG_ROUTE`
- `GPS_DRIFT_SUSPECTED`
- `DUPLICATE_TIMESTAMP_NON_REPRESENTATIVE`
- `LOW_CONFIDENCE_REVIEW`
- `UNKNOWN_REVIEW`
- `motion_artifact_flag = True`

## Known Issue: 44_1 Fragmented Summit Anchor Activation

`44_1` exposed a summit-anchor issue:

- It has 196 artifacts and 156 summit artifacts.
- Episode review showed fragmented summit-anchor activation.
- Each summit-anchor episode has small raw-distance delta, mostly under 20 m.
- Calibrated distance can jump when repeatedly switching between `REVIEWED_SUMMIT_ANCHOR` and `OSM_MAINLINE_CANDIDATE_PROJECTION`.

Interpretation:

- This is not clear evidence that the entire downhill segment was swallowed by summit anchor.
- It is better described as summit-anchor/mainline projection oscillation near the summit.
- v1k2a correctly detects this as a motion artifact.

Future fix:

- Do not fix this in v1k2a.
- Future `v1e2` / `v1h2` should implement summit-anchor episode smoothing, hysteresis, and possibly `SUMMIT_VICINITY_MOVING`.

## Protected Semantics

The following boundaries are mandatory:

- raw data is never overwritten
- v1d3-v1i, v1j, and v1k outputs remain immutable inputs
- wrong-route is preserved and is not projected back to canonical mainline
- connector is preserved and is not classified as `MAINLINE_CORE`
- off-target and low-confidence rows use raw fallback or review policy
- duplicate timestamp non-representative rows do not produce speed
- artifact rows are labeled for review, not silently deleted
- legacy recovery must not automatically restore `usable=True`

## Not Implemented in v1k2 / v1k2a

- `calibrated_elevation_m`
- NLSC elevation lookup
- calibrated slope
- cumulative gain/loss
- facility/radar evidence
- THCI recomputation
- formal activity/model inclusion gate

## Remaining Repository Items

Not part of this pipeline node:

- `folder_inventory_depth4.csv`
- `folder_role_audit_depth4.csv`
- `scripts/ib3_activity_environment/ib3a_rc_label_transition_continuity_v1f_before_v1f2_patch.py`
- `scripts/ib3_activity_environment/ib3a_rc_plot_motion_artifacts_v1k2a.py.before_qa_decision_patch`

Separate review:

- `configs/risk_semantics/ib3a_rc_v1l_osm_facility_radar_evidence_catalog_v1.csv`
- old v1h/v1h2 plot scripts

## Next Development Stage

Next stage is v1k3 calibrated elevation / slope / cumulative gain-loss:

- calibrated elevation
- elevation source and confidence
- calibrated delta elevation
- calibrated slope
- cumulative gain/loss
- elevation review flags

Still deferred:

- v1l OSM facility interaction / THCI radar evidence
- IB3F-RC activity-level feature aggregation
- IB3H-RC formal model inclusion gate
- v1e2 / v1h2 summit-anchor smoothing / hysteresis
