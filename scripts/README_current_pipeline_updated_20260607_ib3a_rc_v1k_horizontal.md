# Current Pipeline Update - IB3A-RC v1k Minimal Horizontal

Date: 2026-06-07

## Current Status

The qixing_lengshuikeng IB3A-RC full26 activity flow is converged through the minimal horizontal calibrated dataset:

1. v1d3-v1i evidence/classification
2. v1j display trajectory
3. v1k minimal horizontal calibrated activity dataset

Commits:

- `581f511 Add IB3A-RC full-batch candidate labeling and wrong-route QA`
- `0b04c81 Add IB3A-RC display trajectory refit layer`
- `70e8ffe Add IB3A-RC calibrated activity dataset horizontal layer`

## IB3A-RC Stage Map

| Stage | Role | Coordinate behavior |
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

## v1j Full26

Script:

- `scripts/ib3_activity_environment/ib3a_rc_build_display_trajectory_refit_v1j.py`

Output root:

- `outputs/ib3a_rc_display_trajectory_refit_v1j_qixing_lengshuikeng_full26_review`

Evidence:

- PASS / FAIL / SKIPPED = 26 / 0 / 0
- total rows = 345,979
- row preservation = PASS
- protected fields changed = 0
- v1i SHA-256 unchanged
- no calibrated columns

v1j is display-only. Raw-vs-display QA must show both traces so reviewers can verify that display refit does not hide real off-target or wrong-route behavior.

## v1k Minimal Horizontal Full26

Script:

- `scripts/ib3_activity_environment/ib3a_rc_build_calibrated_activity_dataset_v1k.py`

Output root:

- `outputs/ib3a_rc_calibrated_activity_dataset_v1k_qixing_lengshuikeng_horizontal_full26`

Evidence:

- PASS / FAIL / SKIPPED = 26 / 0 / 0
- total rows = 345,979
- CSV / summary JSON / provenance JSON = 26 / 26 / 26
- row count and row order preserved
- protected fields changed = 0
- v1i and v1j SHA-256 unchanged
- raw alias mismatch = 0
- unresolved rows = 0
- forbidden columns = 0
- connector / wrong-route / summit / off-target mismatch = 0

### Horizontal Source Distribution

| Source | Rows |
|---|---:|
| `OSM_MAINLINE_CANDIDATE_PROJECTION` | 228,338 |
| `RAW_GPS_FALLBACK` | 96,361 |
| `REVIEWED_SUMMIT_ANCHOR` | 16,714 |
| `OSM_CONNECTOR_PROJECTION` | 3,131 |
| `OSM_WRONG_ROUTE_CANDIDATE_PROJECTION` | 1,435 |

### Route Class Distribution

| Route class | Rows |
|---|---:|
| `MAINLINE_CORE` | 228,338 |
| `OFF_TARGET` | 96,361 |
| `MAINLINE_SUMMIT_STAY` | 16,714 |
| `CONNECTOR` | 3,131 |
| `WRONG_ROUTE` | 1,435 |

### Backend Policy Distribution

| Policy | Rows |
|---|---:|
| `ANALYTICS_READY` | 248,183 |
| `BEHAVIOR_ANALYTICS_ONLY_OFF_TARGET` | 96,361 |
| `BEHAVIOR_ANALYTICS_ONLY_WRONG_ROUTE` | 1,435 |

### Calibration Status Distribution

| Status | Rows |
|---|---:|
| `CALIBRATED_HIGH_CONFIDENCE` | 249,618 |
| `RAW_FALLBACK_REVIEW_REQUIRED` | 96,361 |

## Protected Semantics

The following boundaries are mandatory:

- raw data is never overwritten
- v1d3-v1i and v1j outputs remain immutable inputs
- wrong-route is preserved and is not projected back to canonical mainline
- connector is preserved and is not classified as `MAINLINE_CORE`
- off-target and low-confidence rows use raw fallback or review policy
- legacy recovery must not automatically restore `usable=True`

## Not Implemented in v1k Minimal

- `calibrated_speed_mps`
- `calibrated_step_distance_m`
- `calibrated_horizontal_distance_m`
- `calibrated_elevation_m`
- `movement_state`
- `gps_drift_suspected`
- NLSC elevation lookup
- facility/radar evidence
- THCI recomputation

## Remaining Repository Items

Not part of this pipeline node:

- `folder_inventory_depth4.csv`
- `folder_role_audit_depth4.csv`
- `scripts/ib3_activity_environment/ib3a_rc_label_transition_continuity_v1f_before_v1f2_patch.py`

Separate review:

- `configs/risk_semantics/ib3a_rc_v1l_osm_facility_radar_evidence_catalog_v1.csv`
- old v1h/v1h2 plot scripts

## Next Development Stage

Step 4 is v1k2 calibrated distance, speed, and movement-state design:

- calibrated step distance
- calibrated horizontal distance
- calibrated speed
- movement state
- GPS drift suspicion
- low-speed uncertainty

NLSC elevation, facility/radar evidence, and THCI recomputation remain later independent stages.

