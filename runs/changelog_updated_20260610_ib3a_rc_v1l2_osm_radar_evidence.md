# Changelog - 2026-06-10 IB3A-RC v1l-2 OSM / Facility / Radar Evidence Join

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

The catalog defines OSM / facility / hazard layers, radar axis mapping, evidence type, risk direction, and interaction hints for downstream evidence joins.

### v1l-1 Backend Enriched Dataset and Visual QA

Commit:

- `0cfead2 Add IB3A-RC v1l backend enriched dataset and visual QA`

Added scripts:

- `scripts/ib3_activity_environment/ib3a_rc_build_backend_activity_enriched_v1l.py`
- `scripts/ib3_activity_environment/ib3a_rc_plot_backend_activity_enriched_v1l.py`

Input root:

- `outputs/ib3a_rc_calibrated_elevation_v1k5_supplement_only_qixing_lengshuikeng_full26_qa`

Output root:

- `outputs/ib3a_rc_backend_activity_enriched_v1l_qixing_lengshuikeng_full26`

Visual QA output root:

- `outputs/ib3a_rc_backend_activity_enriched_visual_qa_v1l_qixing_lengshuikeng_full26_routeclass_1d`

Full26 result:

- PASS / FAIL = 26 / 0
- backend CSV files = 26 / 26
- required backend schema fields present = 26 / 26 files
- HTML generated = 26 / 26
- `osm_joined=0` expected at v1l-1 because OSM semantic / facility joins are deferred to v1l-2

Status:

```text
PASS_BACKEND_SCHEMA_BASELINE
PASS_ROW_LEVEL_HANDOFF_READY
PASS_FULL26_ROUTECLASS_1D_VISUAL_QA
```

### v1l-2 OSM / Facility / Radar Evidence Join

Commit:

- `9084cff Add IB3A-RC v1l2 OSM radar evidence join builder`

Added script:

- `scripts/ib3_activity_environment/ib3a_rc_build_backend_activity_enriched_v1l2_osm_radar_evidence.py`

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

Role:

- read v1l-1 row-level backend CSV files
- preserve all v1l-1 rows and columns
- join IB2 route-side OSM semantic / facility / hazard / route-risk evidence by `elevation_profile_dist_m`
- populate OSM semantic fields, proximity fields, IB2 risk fields, and radar evidence hint fields
- keep WRONG_ROUTE and OFF_TARGET rows unjoined to avoid forcing off-route behavior onto canonical route evidence
- output CSV as UTF-8 with BOM for Windows / Excel Chinese compatibility

Full26 result:

- PASS / FAIL = 26 / 0
- rows total = 345,979
- join eligible rows = 248,183
- joined rows = 248,183
- eligible join coverage = 100%
- WRONG_ROUTE not joined = 1,435
- OFF_TARGET not joined = 96,361

Preservation QA:

- files = 26
- pass = 26
- fail = 0
- v1l-1 columns = 290
- v1l-2 columns = 341
- missing v1l-1 columns in v1l-2 = 0
- row count preserved for all 26 activities

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

Status:

```text
PASS_OSM_RADAR_EVIDENCE_JOIN
PASS_WITH_EXPECTED_SOURCE_LIMITS
PASS_V1L1_TO_V1L2_PRESERVATION_QA
PASS_CSV_CHINESE_ENCODING
COMMITTED_AND_PUSHED
```

## v1l-2 Join Policy

Eligible route classes:

- `MAINLINE_CORE`
- `MAINLINE_SUMMIT_STAY`
- `CONNECTOR`

Join key:

- `v1l-1.elevation_profile_dist_m → IB2.dist_m` nearest join
- default max join distance = 2.0 m

Not joined by design:

- `WRONG_ROUTE`
- `OFF_TARGET`

Reason:

- these rows are behavior / QA evidence and should not inherit canonical mainline OSM / route-risk evidence.

## Source-Level Observations

The current IB2 route-risk source provides strong OSM semantic, route risk, steps, guidepost, waterway, peak, shelter, toilet, and road-related evidence coverage.

Observed zero coverage for `near_cliff`, `near_handrail`, and `near_water_source` is treated as a source-level observation, not a v1l-2 failure.

## Deferred

- final formal radar score
- THCI recomputation
- activity-level feature aggregation
- formal activity/model inclusion gate
- route-phase-aware IB1E profile candidate selection
- summit-anchor smoothing / hysteresis
