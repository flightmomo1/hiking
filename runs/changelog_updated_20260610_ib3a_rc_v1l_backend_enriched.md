# Changelog - 2026-06-10 IB3A-RC v1l Backend Enriched Dataset and Visual QA

## Completed Engineering Nodes

### v1l-0 OSM Facility / Radar Evidence Catalog

Commit:

- `6b7fe30 Add IB3A-RC v1l OSM facility radar evidence catalog`

Added:

- `configs/risk_semantics/ib3a_rc_v1l_osm_facility_radar_evidence_catalog_v1.csv`

QA result:

- rows = 55
- unique layer names = 55
- formal candidates = 27
- required-field missing count = 0
- status = `PASS_SCHEMA_QA`

The catalog defines OSM / facility / hazard layers, radar axis mapping, evidence type, risk direction, and interaction hints for future v1l-2 joins.

### v1l-1 Backend Enriched Dataset and Visual QA

Commit:

- `0cfead2 Add IB3A-RC v1l backend enriched dataset and visual QA`

Added scripts:

- `scripts/ib3_activity_environment/ib3a_rc_build_backend_activity_enriched_v1l.py`
- `scripts/ib3_activity_environment/ib3a_rc_plot_backend_activity_enriched_v1l.py`

## v1l-1 Builder

Input root:

- `outputs/ib3a_rc_calibrated_elevation_v1k5_supplement_only_qixing_lengshuikeng_full26_qa`

Output root:

- `outputs/ib3a_rc_backend_activity_enriched_v1l_qixing_lengshuikeng_full26`

Role:

- create row-level backend-facing enriched CSV files
- preserve upstream rows and row order
- preserve raw activity fields
- preserve calibrated horizontal, motion, elevation, and gain/loss fields
- add backend schema aliases and compatibility columns
- add placeholder OSM / radar evidence columns for v1l-2 compatibility

Full26 result:

- PASS / FAIL = 26 / 0
- required backend schema fields present = 26 / 26
- files = 26
- `osm_joined=0` expected at v1l-1 because OSM semantic / facility joins are deferred to v1l-2

Status:

```text
PASS_BACKEND_SCHEMA_BASELINE
PASS_ROW_LEVEL_HANDOFF_READY
```

## v1l-1 Visual QA Plotter

Input root:

- `outputs/ib3a_rc_backend_activity_enriched_v1l_qixing_lengshuikeng_full26`

Output root:

- `outputs/ib3a_rc_backend_activity_enriched_visual_qa_v1l_qixing_lengshuikeng_full26_routeclass_1d`

Report contents:

- summary metrics
- route class counts
- movement state counts
- horizontal calibration source / confidence counts
- backend policy counts
- 2D pre-calibration raw GPS path
- 2D post-calibration calibrated/display path
- 1D raw vs calibrated elevation
- 1D elevation route-class overlay
- 1D speed and step distance
- 1D slope
- 1D total gain/loss
- QA focus row table

Full26 result:

- PASS / FAIL = 26 / 0
- HTML generated = 26 / 26
- summary CSV / JSON generated
- `37_1` wrong-route route-class overlay checked manually
- 2D wrong-route red segment and 1D elevation wrong-route marker alignment checked manually

Status:

```text
PASS_FULL26_ROUTECLASS_1D_VISUAL_QA
PASS_FULL26_HTML_GENERATION
```

## v1l-1 Design Decisions

### Backend Schema Baseline

v1l-1 is a backend schema baseline. It is meant for backend engineers to begin database/API integration and row-level activity trace handling.

It is not yet the final OSM/radar evidence dataset.

### OSM / Facility / Radar Deferred

v1l-1 intentionally leaves semantic / facility join fields as placeholder or not-joined evidence. Formal OSM semantic join, facility proximity, hazard proximity, and radar evidence construction are deferred to v1l-2.

Expected current behavior:

- `osm_joined=0`
- `osm_semantic_join_method = NOT_JOINED_V1L1_SCHEMA_ONLY`
- radar hint fields exist for compatibility but are not formal scores

### Visual QA Split

The v1l visual QA plotter uses separated 2D views:

- pre-calibration: raw GPS path
- post-calibration: calibrated + display path

The 1D elevation chart includes route-class overlays so wrong-route / off-target evidence can be inspected in time/elevation space.

## Backend Handoff Fields

Important backend fields include:

- `raw_lat`
- `raw_lon`
- `calibrated_lat`
- `calibrated_lon`
- `display_lat`
- `display_lon`
- `raw_elevation_m`
- `calibrated_elevation_m`
- `calibrated_speed_mps`
- `calibrated_step_distance_m`
- `route_class`
- `movement_state`
- `backend_use_policy`
- `horizontal_calibration_source`
- `horizontal_calibration_confidence`
- `calibration_review_required`
- `motion_artifact_flag`
- `elevation_artifact_flag`
- `agg_total_gain_m`
- `agg_total_loss_m`
- `osm_semantic_join_method`
- `radar_physical_fitness_hint`
- `radar_navigation_hint`

## Next Stage

Recommended next stage:

- `v1l-2` OSM semantic / facility / hazard proximity join

Deferred:

- formal THCI/radar scoring
- activity-level feature aggregation
- formal activity/model inclusion gate
- route-phase-aware IB1E profile candidate selection
- summit-anchor smoothing / hysteresis
