# Current Pipeline Update - IB3A-RC v1l Backend Enriched Dataset and Visual QA

Date: 2026-06-10

## Current Status

The `qixing_lengshuikeng` IB3A-RC full26 activity flow is converged through the v1l backend enriched dataset and visual QA layer.

Current v1l commits:

- `6b7fe30 Add IB3A-RC v1l OSM facility radar evidence catalog`
- `0cfead2 Add IB3A-RC v1l backend enriched dataset and visual QA`

Remote:

- pushed to `origin/codex/ib3-qixing-lengshuikeng-v1l-facility-radar-evidence`

## Purpose of v1l

v1l introduces the backend-facing enriched activity dataset layer.

Its purpose is to provide a row-level activity data product that backend engineers can use for:

- database schema design
- API schema design
- row-level activity trace rendering
- raw vs calibrated trace comparison
- route-class-aware QA
- basic speed/elevation/gain/loss analytics
- row filtering for model input

v1l-1 is not the final OSM/radar evidence dataset. It is a schema baseline and visual QA layer.

## v1l-0 Evidence Catalog

Catalog:

- `configs/risk_semantics/ib3a_rc_v1l_osm_facility_radar_evidence_catalog_v1.csv`

Commit:

- `6b7fe30 Add IB3A-RC v1l OSM facility radar evidence catalog`

QA:

- rows = 55
- unique `layer_name` = 55
- formal candidates = 27
- required fields missing = 0
- status = `PASS_SCHEMA_QA`

## v1l-1 Backend Enriched Builder

Script:

- `scripts/ib3_activity_environment/ib3a_rc_build_backend_activity_enriched_v1l.py`

Commit:

- `0cfead2 Add IB3A-RC v1l backend enriched dataset and visual QA`

Input root:

- `outputs/ib3a_rc_calibrated_elevation_v1k5_supplement_only_qixing_lengshuikeng_full26_qa`

Output root:

- `outputs/ib3a_rc_backend_activity_enriched_v1l_qixing_lengshuikeng_full26`

Role:

- read v1k5 row-level activity CSVs
- preserve row count and row order
- preserve raw activity fields
- preserve calibrated horizontal / motion / elevation / gain-loss fields
- add backend schema aliases and compatibility columns
- add placeholder OSM/radar evidence fields for v1l-2 compatibility

Full26 QA:

- PASS / FAIL = 26 / 0
- backend CSV files = 26 / 26
- required backend fields present = 26 / 26 files
- status = `PASS_BACKEND_SCHEMA_BASELINE`
- status = `PASS_ROW_LEVEL_HANDOFF_READY`

Required backend fields checked:

- `raw_lat`, `raw_lon`
- `calibrated_lat`, `calibrated_lon`
- `display_lat`, `display_lon`
- `raw_elevation_m`, `calibrated_elevation_m`
- `route_class`, `movement_state`, `backend_use_policy`
- `horizontal_calibration_source`, `horizontal_calibration_confidence`
- `calibrated_speed_mps`, `calibrated_step_distance_m`
- `agg_total_gain_m`, `agg_total_loss_m`
- `osm_semantic_join_method`
- `radar_physical_fitness_hint`, `radar_navigation_hint`

## v1l-1 Visual QA Plotter

Script:

- `scripts/ib3_activity_environment/ib3a_rc_plot_backend_activity_enriched_v1l.py`

Input root:

- `outputs/ib3a_rc_backend_activity_enriched_v1l_qixing_lengshuikeng_full26`

Output root:

- `outputs/ib3a_rc_backend_activity_enriched_visual_qa_v1l_qixing_lengshuikeng_full26_routeclass_1d`

Batch summary:

- `outputs/ib3a_rc_backend_activity_enriched_visual_qa_v1l_qixing_lengshuikeng_full26_routeclass_1d/_batch_summary/qixing_lengshuikeng_v1l_backend_activity_enriched_visual_qa_summary.csv`
- `outputs/ib3a_rc_backend_activity_enriched_visual_qa_v1l_qixing_lengshuikeng_full26_routeclass_1d/_batch_summary/qixing_lengshuikeng_v1l_backend_activity_enriched_visual_qa_summary.json`

Full26 QA:

- PASS / FAIL = 26 / 0
- HTML generated = 26 / 26
- summary CSV / JSON generated
- `37_1` manual route-class visual QA = PASS
- 2D wrong-route red segment and 1D elevation wrong-route marker alignment = PASS

Report contents:

- summary metrics
- route class counts
- movement state counts
- horizontal calibration source counts
- horizontal calibration confidence counts
- backend policy counts
- 2D pre-calibration raw GPS path
- 2D post-calibration calibrated/display path
- 1D raw vs calibrated elevation
- 1D route-class overlay for elevation
- 1D speed and step distance
- 1D slope
- 1D total gain/loss
- QA focus row table

## Backend Use Guidance

v1l-1 CSVs are ready for backend schema and API work.

Backend can use:

- `raw_lat` / `raw_lon` for original GPS trace
- `calibrated_lat` / `calibrated_lon` for calibrated horizontal trace
- `display_lat` / `display_lon` for display trace
- `raw_elevation_m` / `calibrated_elevation_m` for elevation comparison
- `calibrated_speed_mps` and `calibrated_step_distance_m` for motion analytics
- `agg_total_gain_m` / `agg_total_loss_m` for v1k5 gain/loss total
- `route_class`, `movement_state`, `backend_use_policy` for row-level use policy
- `horizontal_calibration_source`, `horizontal_calibration_confidence`, and review flags for QA
- `motion_artifact_flag`, `elevation_artifact_flag` for training exclusion and review
- placeholder `osm_*` and `radar_*` columns for v1l-2 compatibility

## Expected Limitations

v1l-1 intentionally does not implement:

- OSM semantic join
- facility proximity join
- hazard proximity join
- radar evidence scoring
- THCI recomputation
- formal model inclusion gate
- activity-level feature aggregation

Current expected values:

- `osm_joined=0`
- `osm_semantic_join_method = NOT_JOINED_V1L1_SCHEMA_ONLY`
- radar hint fields are compatibility placeholders, not formal scores

## Protected Semantics

- raw data never overwritten
- v1k5 output remains immutable input
- v1l-1 preserves all upstream rows and fields
- wrong-route is preserved and not forced into canonical mainline
- off-target rows remain behavior/QA evidence
- connector remains distinct from `MAINLINE_CORE`
- duplicate timestamp non-representative rows remain preserved
- motion artifact rows remain labeled, not deleted
- elevation artifact rows remain labeled, not deleted
- visual QA plotter is read-only and does not modify CSV / JSON
- v1l-1 does not create formal OSM/radar/THCI scores

## Remaining Repository Items

Not part of this pipeline node and should not be mixed into v1l-1 documentation commit:

- `folder_inventory_depth4.csv`
- `folder_role_audit_depth4.csv`
- `scripts/ib3_activity_environment/ib3a_rc_label_transition_continuity_v1f_before_v1f2_patch.py`
- `scripts/ib3_activity_environment/ib3a_rc_plot_mainline_membership_v1h.py`
- `scripts/ib3_activity_environment/ib3a_rc_plot_mainline_membership_with_ib0d_overlay_v1h2.py`

Generated `outputs/` should also remain untracked unless explicitly required for archival.

## Next Stage

Recommended next stage:

```text
v1l-2 OSM semantic / facility / hazard proximity join
```

v1l-2 should:

- use v1l-0 catalog as evidence contract
- use v1l-1 backend enriched CSV as row-level input
- add OSM route semantics
- add facility and hazard proximity evidence
- build radar-ready evidence basis
- avoid computing final formal radar / THCI score in the first v1l-2 pass
