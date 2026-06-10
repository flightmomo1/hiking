# Latest Handoff - IB3A-RC v1l-2 OSM / Facility / Radar Evidence Join

Date: 2026-06-10

## Current Status

IB3A-RC has completed the `qixing_lengshuikeng` full26 sequence through v1l-2 OSM / facility / radar evidence join.

Current branch:

- `codex/ib3-qixing-lengshuikeng-v1l2-osm-radar-evidence-join`

Latest commit:

- `9084cff Add IB3A-RC v1l2 OSM radar evidence join builder`

Remote:

- pushed to `origin/codex/ib3-qixing-lengshuikeng-v1l2-osm-radar-evidence-join`

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
→ IB3B-RC v1j display trajectory
→ IB3K-RC v1k horizontal calibrated activity dataset
→ IB3K-RC v1k2 calibrated motion dataset
→ IB3G-RC v1k2a motion artifact QA
→ IB3K-RC v1k3 calibrated elevation / slope / cumulative gain-loss
→ IB3K-RC v1k4 elevation visual QA
→ IB3K-RC v1k5 aggregated low-speed elevation supplement
→ IB3A-RC v1l-1 backend enriched dataset / visual QA
→ IB3A-RC v1l-2 OSM semantic / facility / radar evidence join
```

## Layer Roles

### v1l-0 OSM Facility / Radar Evidence Catalog

- defines the evidence vocabulary and radar axis mapping
- catalog:
  - `configs/risk_semantics/ib3a_rc_v1l_osm_facility_radar_evidence_catalog_v1.csv`
- QA:
  - rows = 55
  - unique layer names = 55
  - formal candidates = 27
  - required fields missing = 0
  - status = `PASS_SCHEMA_QA`

### v1l-1 Backend Enriched Dataset

- creates row-level backend-facing enriched CSV
- preserves v1k5 row order and upstream fields
- provides backend schema baseline
- leaves OSM / facility / radar evidence as schema placeholders

### v1l-1 Visual QA

- read-only visual QA for backend enriched CSV
- 2D split:
  - pre-calibration raw GPS
  - post-calibration calibrated/display
- 1D elevation with route-class overlays
- produces full26 HTML reports

### v1l-2 OSM / Facility / Radar Evidence Join

- reads v1l-1 backend CSVs
- uses IB2 route risk v2 as the route-side evidence source
- joins eligible activity rows by `elevation_profile_dist_m → IB2.dist_m`
- adds OSM route semantics
- adds facility / hazard / support proximity evidence
- adds IB2 route risk evidence
- adds radar-ready evidence hint columns
- preserves all v1l-1 rows and columns
- does not compute final radar / THCI score

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

### v1l-2 OSM / Facility / Radar Evidence Join

Script:

- `scripts/ib3_activity_environment/ib3a_rc_build_backend_activity_enriched_v1l2_osm_radar_evidence.py`

Input root:

- `outputs/ib3a_rc_backend_activity_enriched_v1l_qixing_lengshuikeng_full26`

Route evidence source:

- `outputs/ib2_v2_route_risk_v1_3b_contract_qa/qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b/qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b_route_risk_v2.csv`

Output root:

- `outputs/ib3a_rc_backend_activity_enriched_v1l2_osm_radar_evidence_qixing_lengshuikeng_full26`

Result:

- full26 PASS / FAIL = 26 / 0
- rows total = 345,979
- join eligible rows = 248,183
- joined rows = 248,183
- eligible join coverage = 100%
- WRONG_ROUTE not joined = 1,435
- OFF_TARGET not joined = 96,361
- status = `PASS_OSM_RADAR_EVIDENCE_JOIN`

Preservation QA:

- files = 26
- pass = 26
- fail = 0
- v1l-1 columns = 290
- v1l-2 columns = 341
- missing v1l-1 columns in v1l-2 = 0
- row count preserved for all 26 activities
- CSV Chinese encoding = OK after `utf-8-sig`
- status = `PASS_V1L1_TO_V1L2_PRESERVATION_QA`

## Join Policy

Joined route classes:

- `MAINLINE_CORE`
- `MAINLINE_SUMMIT_STAY`
- `CONNECTOR`

Not joined by design:

- `WRONG_ROUTE`
- `OFF_TARGET`

Reason:

- off-route behavior should not inherit canonical mainline route-side evidence.

## Backend Handoff

v1l-2 is ready as the primary row-level backend handoff dataset when OSM / route-side risk evidence is required.

Backend engineers can use:

- all v1l-1 raw / calibrated / display / motion / elevation / route-class fields
- `v1l2_join_status`
- `v1l2_join_reason`
- `v1l2_ib2_dist_m`
- OSM semantic fields
- facility / hazard / support proximity fields
- IB2 route-risk fields
- radar evidence hint fields

v1l-1 should be kept as the baseline reference and debug comparison dataset.

## Important Caveat

v1l-2 is radar-evidence-ready but not final-score-ready.

Still not implemented:

- final formal radar score
- THCI recomputation
- activity-level feature aggregation
- formal activity/model inclusion gate

## Remaining Working Tree Items

Keep outside current v1l-2 closeout:

- `folder_inventory_depth4.csv`
- `folder_role_audit_depth4.csv`
- `scripts/ib3_activity_environment/ib3a_rc_label_transition_continuity_v1f_before_v1f2_patch.py`
- `scripts/ib3_activity_environment/ib3a_rc_plot_mainline_membership_v1h.py`
- `scripts/ib3_activity_environment/ib3a_rc_plot_mainline_membership_with_ib0d_overlay_v1h2.py`

## Commit Guidance

Documentation commit should include only the updated documentation files:

- `runs/CURRENT_INDEX_updated_20260610_ib3a_rc_v1l2_osm_radar_evidence.md`
- `runs/changelog_updated_20260610_ib3a_rc_v1l2_osm_radar_evidence.md`
- `runs/latest_handoff_prompt_updated_20260610_ib3a_rc_v1l2_osm_radar_evidence.md`
- `scripts/README_current_pipeline_updated_20260610_ib3a_rc_v1l2_osm_radar_evidence.md`

Do not use `git add .`.
