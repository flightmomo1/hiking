# CURRENT_INDEX - 115_osm / 山力分析 Prototype A

Updated: 2026-06-01 16:46:15 Asia/Taipei

This file is the current effective entry point. Historical evidence should be kept in time-sortable `runs/freeze_*` folders.

## Current Effective Freeze

`runs/freeze_20260601_164615_ib2_ib2d_v1_3b_clean_pass`

Status: `clean PASS`

Checkpoint:

`v1.3b route-level baseline risk visualization checkpoint`

## Effective Pipeline

```text
IA1 refreshed OSM raw
-> IB0 route match
-> IB0C anchors (legacy / QA reference only)
-> IB0A control point projection
-> IB0A-2 route-axis anchor/component QA
-> IB0B mainline / control-points-only route-axis
-> IB0D trimmed mainline contract QA
-> IB1A route profile
-> IB1C OSM semantics
-> IB1C semantic risk
-> IB1G NLSC contour window
-> IB1E OSM + NLSC terrain / hydro baseline
-> IB2_v2 route risk scoring
-> IB2D offline route risk map / radar
```

## Current Formal Roots

Activity source:

```text
input_root = activity_input/
used_by = IA1 OSM raw refresh + IB0 route match
role = official upstream activity track source
```

NLSC terrain source:

```text
raw_root = nlsc_raw/
formal_contour_fp_pattern = nlsc_raw/<tile>/向量25K/ContourL.shp
used_by = IB1G / IB1E / IB2D
role = official baseline terrain / contour source
```

NLSC 1/25,000 tile selector:

```text
route geometry / GPS bbox
-> candidate 1/25,000 tile
-> nlsc_raw/<tile>/向量25K/ContourL.shp
-> route buffer intersection + valid elevation count validation
```

NLSC specification basis:

```text
source = 113年度「臺灣地區經建版地形圖」製圖作業工作總報告書
map_scales = 1/25,000; 1/50,000; 1/100,000
project_contour_source = nlsc_raw/<tile>/向量25K/ContourL.shp = 1/25,000
tile_extent = 7'30" x 7'30"
projection = transverse Mercator, 2-degree zone, central meridian 121E
horizontal_datum = TWD97
vertical_datum = TWVD2001
contour_spec_1_25000 = index 50m; primary 10m; intermediate 5m
```

Config source:

```text
config_root = configs/
reference_config_root = config/
nlsc_tile_activity_mapping_reference = config/nlsc_tile_activity_mapping.csv
route_definition_config = configs/route_definitions/route_control_points_v1_3b.csv
expected_time_segments_config = configs/route_definitions/route_expected_time_segments_v1_3b.csv
semantic_risk_mapping_available_current = configs/risk_semantics/osm_semantic_risk_mapping_v1_2_updated.csv
semantic_risk_mapping_used_by_existing_ib1_run_log = configs/risk_semantics/osm_semantic_risk_mapping_v1.csv
semantic_risk_mapping_v1_current_root_exists = false
semantic_risk_mapping_v1_archived_copy = configs/risk_semantics/_archived_before_20260531_refresh/osm_semantic_risk_mapping_v1.csv
```

Semantic mapping status:

```text
v1_existing_ib1_outputs = PASS/WARN evidence generated before v1 was archived
v1_2_updated_coverage_audit = 4/4 cases mapping_coverage_rate = 1.0
v1_2_updated_formal_apply_status = audit completed; formal IB1C risk rerun not recorded in current clean PASS freeze
```

IA1 OSM raw refresh:

```text
script_root = scripts/ia_osm/
official_script = scripts/ia_osm/ia1_osm_fetch_raw_friendly_cli_qixing_schema.py
activity_input_root = activity_input/
output_root = osm_raw_output/
```

IB0 family shared script root:

```text
script_root = scripts/ib0_route_match/
```

IB0 route match:

```text
official_script = scripts/ib0_route_match/ib0_gpx_to_osm_route.py
activity_input_root = activity_input/
osm_input_root = osm_raw_output/
output_root = outputs/ib0_route_match/
```

IB0C anchors:

```text
official_script = scripts/ib0_route_match/ib0c_anchor_from_landmarks_v1_2_cli_updated.py
output_root = outputs/ib0c_anchor/
status = WARN / legacy / QA reference only
formal_trim_authority = false
```

IB0A control point projection:

```text
official_script = scripts/ib0_route_match/ib0a_project_control_points_to_osm_candidates.py
output_root = outputs/ib0a_control_points_osm_projection/
status = CONVERGED by external audit evidence
note = built-in script summary gate still recommended for future reruns
```

IB0A-2 route-axis anchor/component QA:

```text
official_script = scripts/ib0_route_match/ib0a2_route_axis_anchor_component_qa.py
output_root = outputs/ib0a2_route_axis_anchor_component_qa/
```

IB0B control-points-only route-axis:

```text
official_script = scripts/ib0_route_match/ib0b_route_mainline_extract_abtest_v1_cli_updated_control_point_constrained.py
route_definition_exporter = scripts/ib0_route_match/ib0b_export_route_definition_points_used_v1_2_phase_aware.py
output_root = outputs/ib0b_mainline_route_definition_v1_3b_control_points_only/
formal_route_axis_authority = IB0B ordered_path + route_definition_control_points_used
```

IB0D control-points-only contract QA:

```text
official_script = scripts/ib0_route_match/ib0d_v1_3b_control_points_only_contract_qa.py
output_root = outputs/ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa/
formal_ib1_input_root = outputs/ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa/
status = CONVERGED / reviewed PASS-WARN gate
```

IB2 / IB2D formal input:

```text
outputs/ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa/
```

IB2 scoring output:

```text
outputs/ib2_v2_route_risk_v1_3b_contract_qa/
```

IB2D visualization output:

```text
outputs/ib2d_route_risk_offline_map_v1_3b_contract_qa/
```

## Current Evidence

IA1 convergence audit:

```text
outputs/ia1_convergence_audit_v1_3b/ia1_v1_3b_case_convergence_audit.csv
outputs/ia1_convergence_audit_v1_3b/ia1_v1_3b_stage_convergence_audit.csv
outputs/ia1_convergence_audit_v1_3b/ia1_v1_3b_convergence_summary.md
```

IB0 route match convergence audit:

```text
outputs/ib0_route_match_convergence_audit_v1_3b/ib0_route_match_v1_3b_case_convergence_audit.csv
outputs/ib0_route_match_convergence_audit_v1_3b/ib0_route_match_v1_3b_stage_convergence_audit.csv
outputs/ib0_route_match_convergence_audit_v1_3b/ib0_route_match_v1_3b_convergence_summary.md
```

IB0C anchor convergence audit:

```text
outputs/ib0c_anchor_convergence_audit_v1_3b/ib0c_anchor_v1_3b_case_convergence_audit.csv
outputs/ib0c_anchor_convergence_audit_v1_3b/ib0c_anchor_v1_3b_stage_convergence_audit.csv
outputs/ib0c_anchor_convergence_audit_v1_3b/ib0c_anchor_v1_3b_convergence_summary.md
```

IB0A control point projection convergence audit:

```text
outputs/ib0a_control_points_projection_convergence_audit_v1_3b/ib0a_control_points_projection_v1_3b_case_convergence_audit.csv
outputs/ib0a_control_points_projection_convergence_audit_v1_3b/ib0a_control_points_projection_v1_3b_stage_convergence_audit.csv
outputs/ib0a_control_points_projection_convergence_audit_v1_3b/ib0a_control_points_projection_v1_3b_convergence_summary.md
```

IB0D reviewed PASS/WARN convergence audit:

```text
outputs/ib0d_convergence_audit_v1_3b_reviewed_pass_warn/ib0d_v1_3b_reviewed_pass_warn_case_convergence_audit.csv
outputs/ib0d_convergence_audit_v1_3b_reviewed_pass_warn/ib0d_v1_3b_reviewed_pass_warn_stage_convergence_audit.csv
outputs/ib0d_convergence_audit_v1_3b_reviewed_pass_warn/ib0d_v1_3b_reviewed_pass_warn_convergence_summary.md
```

IB1A route profile convergence audit:

```text
outputs/ib1_v1_3b_contract_qa_pipeline_summary/ib1a_v1_3b_route_profile_convergence_audit.csv
```

Folder role audit:

```text
folder_inventory_depth4.csv
folder_role_audit_depth4.csv
```

AI engineer handoff dataset:

```text
outputs/ai_engineer_handoff_dataset_v1/
```

Frozen copy:

```text
runs/freeze_20260601_164615_ib2_ib2d_v1_3b_clean_pass/handoff_dataset/ai_engineer_handoff_dataset_v1/
```

Case summary:

```text
outputs/ib2d_route_risk_offline_map_v1_3b_contract_qa/_batch_summary/ib2_v1_3b_contract_qa_case_summary.csv
```

Stage summary:

```text
outputs/ib2d_route_risk_offline_map_v1_3b_contract_qa/_batch_summary/ib2d_v1_3b_contract_qa_stage_summary.md
```

NLSC tile assignment:

```text
outputs/ib2d_route_risk_offline_map_v1_3b_contract_qa/_batch_summary/ib2d_v1_3b_contract_qa_tile_assignment.csv
```

Zhonghua tile correction before/after:

```text
outputs/ib2d_route_risk_offline_map_v1_3b_contract_qa/_batch_summary/zhonghua_tile_correction_before_after_summary.csv
```

## Document Roles

`changelog`: permanent historical record.

`handoff`: snapshot of the handoff state at that time.

`README`: contract/status for that checkpoint.

`CURRENT_INDEX`: current effective entry point.

`summary CSV`: acceptance evidence.

## Boundary Notes

Weather is not integrated at IB2D:

```text
weather_mode = not_integrated_at_ib2d
weather_scope = future_ib3_activity_layer
```

IB2D is route-level baseline risk visualization. Observed weather belongs to a future IB3 activity layer.

Do not use these legacy roots as formal current inputs:

```text
osm_raw_output_v1_1/
outputs/ib0d_trimmed_mainline/
outputs/ib0d_trimmed_mainline_v1_3b_control_points_only/
outputs/ib0c_anchor/
outputs/ib1e_route_profile_contour_window_terrain/
outputs/ib1e_osm_nlsc_terrain_risk/
outputs/ib2_v2_route_risk/
outputs/ib2d_route_risk_offline_map/
```

Reference/future roots:

```text
config/nlsc_tile_activity_mapping.csv = NLSC tile mapping reference only; formal selector uses route bbox + contour intersection + valid elevation count
weather/ = future IB3 observed weather source; not integrated at IB2D
outputs/ib3*/ = future/history activity layer outputs, not current IA1-IB2D formal checkpoint
outputs/ib4*/ and outputs/model_*/ = experimental/model artifacts, not current IA1-IB2D formal checkpoint
```
