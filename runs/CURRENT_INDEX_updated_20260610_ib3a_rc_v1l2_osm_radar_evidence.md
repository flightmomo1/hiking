# Current Index - 2026-06-10 IB3A-RC v1l-2 OSM / Facility / Radar Evidence Join

## Current Branch

- `codex/ib3-qixing-lengshuikeng-v1l2-osm-radar-evidence-join`
- Remote tracking: `origin/codex/ib3-qixing-lengshuikeng-v1l2-osm-radar-evidence-join`

## Current Commits

Upstream closed commits:

- `581f511` - IB3A-RC v1d3-v1i full-batch candidate labeling and wrong-route QA
- `0b04c81` - IB3A-RC v1j display trajectory refit
- `70e8ffe` - IB3A-RC v1k minimal horizontal calibrated activity dataset
- `5076517` - IB3A-RC calibrated motion and artifact QA layers
- `855f5a3` - IB3A-RC calibrated elevation and gain-loss layer
- `bf4fcf6` - IB3A-RC elevation visual QA plotter
- `c289ac3` - IB3A-RC aggregated elevation supplement layer

v1l closed commits:

- `6b7fe30` - Add IB3A-RC v1l OSM facility radar evidence catalog
- `0cfead2` - Add IB3A-RC v1l backend enriched dataset and visual QA

Current v1l-2 commit:

- `9084cff Add IB3A-RC v1l2 OSM radar evidence join builder`

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

v1l evidence catalog:

- `configs/risk_semantics/ib3a_rc_v1l_osm_facility_radar_evidence_catalog_v1.csv`

v1l-1 backend and visual QA:

- `scripts/ib3_activity_environment/ib3a_rc_build_backend_activity_enriched_v1l.py`
- `scripts/ib3_activity_environment/ib3a_rc_plot_backend_activity_enriched_v1l.py`

v1l-2 OSM / facility / radar evidence join:

- `scripts/ib3_activity_environment/ib3a_rc_build_backend_activity_enriched_v1l2_osm_radar_evidence.py`

## Current Full26 Roots

v1l-1 input root:

- `outputs/ib3a_rc_calibrated_elevation_v1k5_supplement_only_qixing_lengshuikeng_full26_qa`

v1l-1 backend CSV output root:

- `outputs/ib3a_rc_backend_activity_enriched_v1l_qixing_lengshuikeng_full26`

v1l-1 visual QA output root:

- `outputs/ib3a_rc_backend_activity_enriched_visual_qa_v1l_qixing_lengshuikeng_full26_routeclass_1d`

v1l-2 route evidence source:

- `outputs/ib2_v2_route_risk_v1_3b_contract_qa/qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b/qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b_route_risk_v2.csv`

v1l-2 backend CSV output root:

- `outputs/ib3a_rc_backend_activity_enriched_v1l2_osm_radar_evidence_qixing_lengshuikeng_full26`

## Current Convergence

### v1l-0 Catalog

- rows = 55
- unique `layer_name` = 55
- formal candidates = 27
- required fields missing = 0
- status = `PASS_SCHEMA_QA`

### v1l-1 Backend Enriched CSV

- full26 backend schema check = PASS
- files = 26
- pass = 26
- fail = 0
- required backend columns missing = 0 for all 26 CSV files
- status = `PASS_BACKEND_SCHEMA_BASELINE`
- status = `PASS_ROW_LEVEL_HANDOFF_READY`

### v1l-1 Visual QA

- full26 visual QA generation = PASS
- activity HTML generated = 26 / 26
- summary CSV / JSON generated
- `37_1` route-class overlay check = PASS
- 2D wrong-route and 1D elevation wrong-route marker alignment = PASS
- status = `PASS_FULL26_ROUTECLASS_1D_VISUAL_QA`

### v1l-2 OSM / Facility / Radar Evidence Join

- full26 evidence join = PASS
- files = 26
- pass = 26
- fail = 0
- rows total = 345,979
- join eligible rows = 248,183
- joined rows = 248,183
- eligible join coverage = 100%
- WRONG_ROUTE not joined = 1,435
- OFF_TARGET not joined = 96,361
- status = `PASS_OSM_RADAR_EVIDENCE_JOIN`

### v1l-1 to v1l-2 Preservation QA

- files = 26
- pass = 26
- fail = 0
- v1l-1 columns = 290
- v1l-2 columns = 341
- missing v1l-1 columns in v1l-2 = 0
- row count preserved for all 26 activities
- status = `PASS_V1L1_TO_V1L2_PRESERVATION_QA`

## Current Dataset Interpretation

v1l-1 is a backend-facing row-level schema baseline.

v1l-2 is the backend-facing evidence-enriched row-level dataset. It preserves v1l-1 and adds OSM semantic / facility / hazard / route-risk / radar evidence columns.

Recommended backend use:

- use v1l-1 for baseline schema comparison and debug reference
- use v1l-2 as the primary backend integration dataset when OSM / route-side risk evidence is needed

## Protected Semantics

- raw data never overwritten
- v1k5 and v1l-1 outputs remain immutable inputs
- v1l-2 preserves all v1l-1 rows and columns
- wrong-route is preserved and not forced into canonical mainline evidence
- off-target rows remain behavior / QA evidence
- connector remains distinct from `MAINLINE_CORE`
- duplicate timestamp non-representative rows remain preserved
- motion artifact rows remain labeled, not deleted
- elevation artifact rows remain labeled, not deleted
- v1l-2 does not compute final formal radar / THCI scores

## Working Tree Classification

Do not include unless explicitly requested:

- `folder_inventory_depth4.csv`
- `folder_role_audit_depth4.csv`
- `scripts/ib3_activity_environment/ib3a_rc_label_transition_continuity_v1f_before_v1f2_patch.py`
- `scripts/ib3_activity_environment/ib3a_rc_plot_mainline_membership_v1h.py`
- `scripts/ib3_activity_environment/ib3a_rc_plot_mainline_membership_with_ib0d_overlay_v1h2.py`
- generated `outputs/`

## Next Recommended Stage

- document v1l-2 convergence in `runs/` and `scripts/README`
- decide whether to open PR from `codex/ib3-qixing-lengshuikeng-v1l2-osm-radar-evidence-join`
- proceed to formal radar score / THCI downstream design only after v1l-2 evidence contract is accepted
