# Latest Handoff - IB3A-RC v1l Backend Enriched Dataset and Visual QA

Date: 2026-06-10

## Current Status

IB3A-RC has completed the `qixing_lengshuikeng` full26 sequence through v1l-1 backend enriched dataset and visual QA.

Current branch:

- `codex/ib3-qixing-lengshuikeng-v1l-facility-radar-evidence`

Latest v1l commits:

- `6b7fe30 Add IB3A-RC v1l OSM facility radar evidence catalog`
- `0cfead2 Add IB3A-RC v1l backend enriched dataset and visual QA`

Remote:

- pushed to `origin/codex/ib3-qixing-lengshuikeng-v1l-facility-radar-evidence`

## Correct Pipeline Interpretation

IB3A-RC is an activity candidate-route branch. It is not downstream of `IB0B mainline`.

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
→ IB3K-RC v1k3
→ IB3K-RC v1k4
→ IB3K-RC v1k5
→ IB3A-RC v1l
```

## Layer Roles

### v1l-0 OSM Facility / Radar Evidence Catalog

- adds global evidence catalog:
  - `configs/risk_semantics/ib3a_rc_v1l_osm_facility_radar_evidence_catalog_v1.csv`
- schema QA:
  - rows = 55
  - unique layer names = 55
  - formal candidates = 27
  - required fields missing = 0

### v1l-1 Backend Enriched Dataset

- creates row-level backend-facing enriched CSV
- preserves v1k5 row order and upstream fields
- provides backend schema baseline
- does not yet perform OSM semantic/facility spatial joins

### v1l-1 Visual QA

- read-only visual QA for backend enriched CSV
- 2D split:
  - pre-calibration raw GPS
  - post-calibration calibrated/display
- 1D elevation with route-class overlays
- shows route class, movement state, source/confidence/policy counts
- produces full26 HTML reports

## Full26 Evidence

### v1l-1 Backend Enriched CSV

Script:

- `scripts/ib3_activity_environment/ib3a_rc_build_backend_activity_enriched_v1l.py`

Output root:

- `outputs/ib3a_rc_backend_activity_enriched_v1l_qixing_lengshuikeng_full26`

Result:

- full26 PASS
- files = 26
- required backend schema field missing count = 0 for all files
- status = `PASS_BACKEND_SCHEMA_BASELINE`
- status = `PASS_ROW_LEVEL_HANDOFF_READY`

### v1l-1 Visual QA

Script:

- `scripts/ib3_activity_environment/ib3a_rc_plot_backend_activity_enriched_v1l.py`

Output root:

- `outputs/ib3a_rc_backend_activity_enriched_visual_qa_v1l_qixing_lengshuikeng_full26_routeclass_1d`

Result:

- full26 PASS / FAIL = 26 / 0
- HTML generated = 26 / 26
- summary CSV generated
- summary JSON generated
- `37_1` 2D wrong-route and 1D elevation route-class overlay checked manually
- status = `PASS_FULL26_ROUTECLASS_1D_VISUAL_QA`

## Backend Handoff

v1l-1 is ready for backend handoff as a row-level schema baseline.

Backend engineers can proceed with:

- table schema design
- API response schema design
- raw/calibrated/display trace rendering
- route-class-aware activity QA
- basic speed/elevation/gain/loss analytics
- row-level model filtering

Important columns:

- `raw_lat`, `raw_lon`
- `calibrated_lat`, `calibrated_lon`
- `display_lat`, `display_lon`
- `raw_elevation_m`, `calibrated_elevation_m`
- `calibrated_speed_mps`, `calibrated_step_distance_m`
- `route_class`, `movement_state`, `backend_use_policy`
- `horizontal_calibration_source`, `horizontal_calibration_confidence`
- `calibration_review_required`
- `motion_artifact_flag`, `elevation_artifact_flag`
- `agg_total_gain_m`, `agg_total_loss_m`
- `osm_semantic_join_method`
- `radar_physical_fitness_hint`, `radar_navigation_hint`

## Important Caveat

v1l-1 is not the final OSM/radar evidence dataset.

Expected current limitations:

- `osm_joined=0`
- OSM semantic join not implemented
- facility proximity not implemented
- hazard proximity not implemented
- radar evidence is not formal scoring
- THCI recomputation not implemented

These are deferred to v1l-2.

## Recommended Next Step

Proceed to:

```text
v1l-2 OSM semantic / facility / hazard proximity join
```

v1l-2 should use the v1l-0 catalog and v1l-1 backend CSV as inputs.

## Remaining Working Tree Items

Keep outside current v1l-1 closeout:

- `folder_inventory_depth4.csv`
- `folder_role_audit_depth4.csv`
- `scripts/ib3_activity_environment/ib3a_rc_label_transition_continuity_v1f_before_v1f2_patch.py`
- `scripts/ib3_activity_environment/ib3a_rc_plot_mainline_membership_v1h.py`
- `scripts/ib3_activity_environment/ib3a_rc_plot_mainline_membership_with_ib0d_overlay_v1h2.py`

## Commit Guidance

Documentation commit should include only:

- `runs/CURRENT_INDEX_updated_20260610_ib3a_rc_v1l_backend_enriched.md`
- `runs/changelog_updated_20260610_ib3a_rc_v1l_backend_enriched.md`
- `runs/latest_handoff_prompt_updated_20260610_ib3a_rc_v1l_backend_enriched.md`
- `scripts/README_current_pipeline_updated_20260610_ib3a_rc_v1l_backend_enriched.md`

Do not use `git add .`.
