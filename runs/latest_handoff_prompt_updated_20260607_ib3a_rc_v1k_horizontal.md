# Latest Handoff - IB3A-RC v1k Minimal Horizontal

Date: 2026-06-07

## Current Status

IB3A-RC has completed the qixing_lengshuikeng full26 sequence through:

- v1d3-v1i evidence and classification layer
- v1j display trajectory layer
- v1k minimal horizontal calibrated activity dataset layer

Relevant commits:

- `581f511 Add IB3A-RC full-batch candidate labeling and wrong-route QA`
- `0b04c81 Add IB3A-RC display trajectory refit layer`
- `70e8ffe Add IB3A-RC calibrated activity dataset horizontal layer`

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

### v1k Minimal

v1k is the first backend-facing calibrated dataset skeleton:

- produces `calibrated_lat` / `calibrated_lon`
- records horizontal calibration source, confidence, distance, and review status
- preserves route class, connector, off-target, and wrong-route semantics
- produces backend use policy
- does not calculate speed, distance, elevation, movement state, GPS drift, NLSC, facility/radar evidence, or THCI

## Full26 Evidence

### v1j

- PASS / FAIL / SKIPPED = 26 / 0 / 0
- total rows = 345,979
- row preservation = PASS
- protected fields changed = 0
- v1i SHA-256 unchanged
- calibrated columns created = 0

Output root:

- `outputs/ib3a_rc_display_trajectory_refit_v1j_qixing_lengshuikeng_full26_review`

### v1k Minimal Horizontal

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

Output root:

- `outputs/ib3a_rc_calibrated_activity_dataset_v1k_qixing_lengshuikeng_horizontal_full26`

## v1k Full26 Distribution

Horizontal calibration source:

- `OSM_MAINLINE_CANDIDATE_PROJECTION`: 228,338
- `RAW_GPS_FALLBACK`: 96,361
- `REVIEWED_SUMMIT_ANCHOR`: 16,714
- `OSM_CONNECTOR_PROJECTION`: 3,131
- `OSM_WRONG_ROUTE_CANDIDATE_PROJECTION`: 1,435

Route class:

- `MAINLINE_CORE`: 228,338
- `OFF_TARGET`: 96,361
- `MAINLINE_SUMMIT_STAY`: 16,714
- `CONNECTOR`: 3,131
- `WRONG_ROUTE`: 1,435

Backend use policy:

- `ANALYTICS_READY`: 248,183
- `BEHAVIOR_ANALYTICS_ONLY_OFF_TARGET`: 96,361
- `BEHAVIOR_ANALYTICS_ONLY_WRONG_ROUTE`: 1,435

Calibration status:

- `CALIBRATED_HIGH_CONFIDENCE`: 249,618
- `RAW_FALLBACK_REVIEW_REQUIRED`: 96,361

## Important Boundaries

- Raw data is preserved and never overwritten.
- Wrong-route rows must not be pulled back to canonical mainline.
- Connector rows must not become `MAINLINE_CORE`.
- Off-target and low-confidence rows use raw GPS fallback or a review-required policy.
- Legacy v1c-v1h recovery that automatically sets usable rows to true must not flow back into the current pipeline.
- v1j and v1k must not modify v1d3-v1i outputs.
- THCI has not been recomputed as part of v1j or v1k.

## Remaining Working Tree Items

Keep outside this documentation closeout:

- `folder_inventory_depth4.csv`: inventory artifact; do not include
- `folder_role_audit_depth4.csv`: inventory artifact; do not include
- `configs/risk_semantics/ib3a_rc_v1l_osm_facility_radar_evidence_catalog_v1.csv`: separate v1l work
- `scripts/ib3_activity_environment/ib3a_rc_label_transition_continuity_v1f_before_v1f2_patch.py`: backup; do not include
- old v1h/v1h2 plotting scripts: archive/delete review required

## Next Development

Next recommended stage: v1k2 calibrated distance, speed, and movement-state design.

Candidate v1k2 fields:

- `calibrated_step_distance_m`
- `calibrated_horizontal_distance_m`
- `calibrated_speed_mps`
- `movement_state`
- `gps_drift_suspected`
- low-speed uncertainty fields

Still deferred:

- NLSC elevation calibration
- facility/radar evidence
- THCI recomputation

