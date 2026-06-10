# Current Pipeline Update - IB3A-RC v1l-2 OSM / Facility / Radar Evidence Join

Date: 2026-06-10

## Current Status

The `qixing_lengshuikeng` IB3A-RC full26 activity flow is converged through the v1l-2 OSM / facility / radar evidence join layer.

Current branch:

- `codex/ib3-qixing-lengshuikeng-v1l2-osm-radar-evidence-join`

Current commit:

- `9084cff Add IB3A-RC v1l2 OSM radar evidence join builder`

Remote:

- pushed to `origin/codex/ib3-qixing-lengshuikeng-v1l2-osm-radar-evidence-join`

## Purpose of v1l-2

v1l-2 turns the v1l-1 backend schema baseline into a row-level backend dataset with route-side evidence.

It preserves all v1l-1 rows and columns, then adds:

- OSM route semantics
- facility / support proximity evidence
- hazard / terrain-context proximity evidence
- IB2 route risk evidence
- radar-ready evidence hint fields
- join status and join reason fields

v1l-2 does not compute final formal radar score or THCI.

## Upstream Context

### v1l-0 Evidence Catalog

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

### v1l-1 Backend Enriched Builder

Script:

- `scripts/ib3_activity_environment/ib3a_rc_build_backend_activity_enriched_v1l.py`

Commit:

- `0cfead2 Add IB3A-RC v1l backend enriched dataset and visual QA`

Input root:

- `outputs/ib3a_rc_calibrated_elevation_v1k5_supplement_only_qixing_lengshuikeng_full26_qa`

Output root:

- `outputs/ib3a_rc_backend_activity_enriched_v1l_qixing_lengshuikeng_full26`

Full26 QA:

- PASS / FAIL = 26 / 0
- backend CSV files = 26 / 26
- required backend fields present = 26 / 26 files
- status = `PASS_BACKEND_SCHEMA_BASELINE`
- status = `PASS_ROW_LEVEL_HANDOFF_READY`

### v1l-1 Visual QA Plotter

Script:

- `scripts/ib3_activity_environment/ib3a_rc_plot_backend_activity_enriched_v1l.py`

Output root:

- `outputs/ib3a_rc_backend_activity_enriched_visual_qa_v1l_qixing_lengshuikeng_full26_routeclass_1d`

Full26 QA:

- PASS / FAIL = 26 / 0
- HTML generated = 26 / 26
- summary CSV / JSON generated
- `37_1` manual route-class visual QA = PASS
- 2D wrong-route red segment and 1D elevation wrong-route marker alignment = PASS

## v1l-2 Builder

Script:

- `scripts/ib3_activity_environment/ib3a_rc_build_backend_activity_enriched_v1l2_osm_radar_evidence.py`

Commit:

- `9084cff Add IB3A-RC v1l2 OSM radar evidence join builder`

Input root:

- `outputs/ib3a_rc_backend_activity_enriched_v1l_qixing_lengshuikeng_full26`

Route evidence source:

- `outputs/ib2_v2_route_risk_v1_3b_contract_qa/qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b/qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b_route_risk_v2.csv`

Output root:

- `outputs/ib3a_rc_backend_activity_enriched_v1l2_osm_radar_evidence_qixing_lengshuikeng_full26`

Batch summary:

- `outputs/ib3a_rc_backend_activity_enriched_v1l2_osm_radar_evidence_qixing_lengshuikeng_full26/_batch_summary/qixing_lengshuikeng_v1l2_osm_radar_evidence_summary.csv`
- `outputs/ib3a_rc_backend_activity_enriched_v1l2_osm_radar_evidence_qixing_lengshuikeng_full26/_batch_summary/qixing_lengshuikeng_v1l2_osm_radar_evidence_summary.json`
- `outputs/ib3a_rc_backend_activity_enriched_v1l2_osm_radar_evidence_qixing_lengshuikeng_full26/_batch_summary/qixing_lengshuikeng_v1l2_osm_radar_evidence_aggregate.json`

## v1l-2 Join Method

Eligible route classes:

- `MAINLINE_CORE`
- `MAINLINE_SUMMIT_STAY`
- `CONNECTOR`

Join key:

- `elevation_profile_dist_m → IB2.dist_m`
- nearest join
- `--max-join-dist-m 2.0`

Not joined by design:

- `WRONG_ROUTE`
- `OFF_TARGET`

Reason:

- off-route behavior should remain review evidence and should not inherit canonical route-side OSM / radar evidence.

## Full26 QA

Aggregate:

- cases = 26
- pass = 26
- fail = 0
- rows total = 345,979
- join eligible rows = 248,183
- joined rows = 248,183
- eligible join coverage = 100%
- WRONG_ROUTE not joined = 1,435
- OFF_TARGET not joined = 96,361

Status:

```text
PASS_OSM_RADAR_EVIDENCE_JOIN
```

## v1l-1 to v1l-2 Preservation QA

Result:

- files = 26
- pass = 26
- fail = 0
- v1l-1 rows preserved for every activity
- v1l-1 columns preserved for every activity
- v1l-1 columns = 290
- v1l-2 columns = 341
- missing v1l-1 columns in v1l-2 = 0
- CSV Chinese encoding = OK after UTF-8 with BOM output

Status:

```text
PASS_V1L1_TO_V1L2_PRESERVATION_QA
PASS_CSV_CHINESE_ENCODING
```

## Evidence Coverage

Radar evidence coverage totals:

- physical = 247,511
- technical = 248,183
- base hazard = 248,183
- navigation = 248,183
- support insufficiency = 235,235
- weather sensitivity = 241,972

Proximity evidence coverage totals:

- near cliff = 0
- near handrail = 0
- near guidepost = 56,237
- near shelter = 7,848
- near toilet = 3,195
- near water source = 0
- near steps = 191,191
- near waterway = 16,451
- near peak = 46,618
- near road = 248,183

Interpretation:

- zero cliff / handrail / water-source coverage is a source-level observation for this route evidence source, not a v1l-2 join failure.

## Backend Use Guidance

Use v1l-1 for:

- baseline schema comparison
- debug reference
- raw/calibrated/display activity trace inspection
- row-level QA without route-side OSM evidence

Use v1l-2 for:

- backend integration requiring route-side OSM / risk evidence
- activity trace rendering with route-class and evidence overlays
- radar-evidence-ready API payload design
- route-risk-aware row filtering
- downstream score design and audit

Important v1l-2 fields include:

- `v1l2_join_status`
- `v1l2_join_reason`
- `v1l2_ib2_dist_m`
- `v1l2_ib2_join_dist_m`
- `osm_way_id`
- `osm_name`
- `osm_highway`
- `osm_surface`
- `osm_bridge`
- `osm_sac_scale`
- `nearest_guidepost_dist_m`
- `near_guidepost_flag`
- `nearest_shelter_dist_m`
- `near_shelter_flag`
- `nearest_toilet_dist_m`
- `near_toilet_flag`
- `ib2_risk_score`
- `ib2_risk_band`
- `ib2_risk_reason`
- `radar_physical_fitness_hint`
- `radar_technical_difficulty_hint`
- `radar_base_hazard_hint`
- `radar_navigation_hint`
- `radar_support_insufficiency_hint`
- `radar_weather_sensitivity_hint`
- `radar_evidence_layers`
- `radar_evidence_notes`

## Protected Semantics

- raw data never overwritten
- v1k5 output remains immutable input
- v1l-1 output remains immutable input
- v1l-2 preserves all v1l-1 rows and fields
- wrong-route is preserved and not forced into canonical mainline
- off-target rows remain behavior / QA evidence
- connector remains distinct from `MAINLINE_CORE`
- duplicate timestamp non-representative rows remain preserved
- motion artifact rows remain labeled, not deleted
- elevation artifact rows remain labeled, not deleted
- v1l-2 does not create final formal radar / THCI scores

## Expected Limitations

v1l-2 intentionally does not implement:

- final formal radar scoring
- THCI recomputation
- activity-level feature aggregation
- formal model inclusion gate
- route-phase-aware IB1E profile candidate selection
- summit-anchor smoothing / hysteresis

## Remaining Repository Items

Not part of this pipeline node and should not be mixed into the v1l-2 documentation commit:

- `folder_inventory_depth4.csv`
- `folder_role_audit_depth4.csv`
- `scripts/ib3_activity_environment/ib3a_rc_label_transition_continuity_v1f_before_v1f2_patch.py`
- `scripts/ib3_activity_environment/ib3a_rc_plot_mainline_membership_v1h.py`
- `scripts/ib3_activity_environment/ib3a_rc_plot_mainline_membership_with_ib0d_overlay_v1h2.py`

Generated `outputs/` should remain untracked unless explicitly required for archival.

## Next Stage

Recommended next stage:

```text
formal radar score / THCI downstream design
```

Only proceed after the v1l-2 evidence contract is accepted by backend / downstream consumers.
