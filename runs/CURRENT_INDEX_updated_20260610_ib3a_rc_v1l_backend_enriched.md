# Current Index - 2026-06-10 IB3A-RC v1l Backend Enriched Dataset and Visual QA

## Current Branch

- `codex/ib3-qixing-lengshuikeng-v1l-facility-radar-evidence`
- Remote tracking: `origin/codex/ib3-qixing-lengshuikeng-v1l-facility-radar-evidence`

## Current Commits

Upstream closed commits:

- `581f511` - IB3A-RC v1d3-v1i full-batch candidate labeling and wrong-route QA
- `0b04c81` - IB3A-RC v1j display trajectory refit
- `70e8ffe` - IB3A-RC v1k minimal horizontal calibrated activity dataset
- `5076517` - IB3A-RC calibrated motion and artifact QA layers
- `855f5a3` - IB3A-RC calibrated elevation and gain-loss layer
- `bf4fcf6` - IB3A-RC elevation visual QA plotter
- `c289ac3` - IB3A-RC aggregated elevation supplement layer

Current v1l commits:

- `6b7fe30` - Add IB3A-RC v1l OSM facility radar evidence catalog
- `0cfead2` - Add IB3A-RC v1l backend enriched dataset and visual QA

## Route Formal Branch vs Activity RC Branch

IB3A-RC remains an activity candidate-route branch, not a downstream consumer of `IB0B mainline`.

```text
IA1 refreshed OSM raw
→ IB0 route match
→ IB0C anchors
→ IB0A control point projection
→ IB0A-2 route-axis anchor/component QA
    ├─→ IB0B mainline → IB0D → IB1/IB2 route formal products
    └─→ IB0-CAND adapter → candidate_route_points.csv → IB3A-RC activity calibrated dataset
```

## Current Scripts

v1l backend and visual QA:

- `scripts/ib3_activity_environment/ib3a_rc_build_backend_activity_enriched_v1l.py`
- `scripts/ib3_activity_environment/ib3a_rc_plot_backend_activity_enriched_v1l.py`

v1l evidence catalog:

- `configs/risk_semantics/ib3a_rc_v1l_osm_facility_radar_evidence_catalog_v1.csv`

## Current Full26 Roots

Input root for v1l-1:

- `outputs/ib3a_rc_calibrated_elevation_v1k5_supplement_only_qixing_lengshuikeng_full26_qa`

v1l-1 backend CSV output root:

- `outputs/ib3a_rc_backend_activity_enriched_v1l_qixing_lengshuikeng_full26`

v1l-1 visual QA output root:

- `outputs/ib3a_rc_backend_activity_enriched_visual_qa_v1l_qixing_lengshuikeng_full26_routeclass_1d`

## Current Convergence

### v1l-0 Catalog

- rows = 55
- unique `layer_name` = 55
- formal candidates = 27
- required fields missing = 0
- status = `PASS_SCHEMA_QA`

### v1l-1 Backend Enriched CSV

- full26 backend schema check: PASS
- files = 26
- pass = 26
- fail = 0
- required backend columns missing = 0 for all 26 CSV files
- status = `PASS_BACKEND_SCHEMA_BASELINE`
- status = `PASS_ROW_LEVEL_HANDOFF_READY`

### v1l-1 Visual QA

- full26 visual QA generation: PASS
- activity HTML generated = 26 / 26
- summary CSV / JSON generated
- `37_1` route-class overlay check: PASS
- 2D wrong-route and 1D elevation wrong-route marker alignment: PASS
- status = `PASS_FULL26_ROUTECLASS_1D_VISUAL_QA`

## v1l-1 Scope

v1l-1 is a backend-facing row-level schema baseline and visual QA layer.

It provides:

- raw activity coordinates and elevation
- calibrated horizontal coordinates
- display coordinates
- calibrated elevation
- calibrated speed and step distance
- v1k5 gain/loss totals
- route class
- movement state
- backend use policy
- horizontal calibration source / confidence / review evidence
- artifact and review flags
- placeholder OSM semantic / radar hint columns for downstream v1l-2 compatibility

It does not yet perform:

- OSM semantic spatial join
- facility / hazard proximity join
- route risk radar scoring
- THCI recomputation
- formal activity/model inclusion gate
- activity-level feature aggregation

## Backend Handoff Interpretation

v1l-1 CSV files can be used by backend engineers for database/API schema design, row-level trace rendering, raw vs calibrated comparison, basic speed/elevation/gain-loss analytics, and model-row filtering.

OSM semantic / facility / radar evidence remains deferred to v1l-2.

## Working Tree Classification

Do not include in this closeout unless explicitly requested:

- `folder_inventory_depth4.csv`
- `folder_role_audit_depth4.csv`
- `scripts/ib3_activity_environment/ib3a_rc_label_transition_continuity_v1f_before_v1f2_patch.py`
- `scripts/ib3_activity_environment/ib3a_rc_plot_mainline_membership_v1h.py`
- `scripts/ib3_activity_environment/ib3a_rc_plot_mainline_membership_with_ib0d_overlay_v1h2.py`
- generated `outputs/`

## Next Recommended Stage

- document v1l-1 convergence in `runs/` and `scripts/README`
- proceed to v1l-2 OSM semantic / facility / hazard proximity join
