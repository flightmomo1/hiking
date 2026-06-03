# IA1 to IB0D v1.3b route-axis convergence audit

Audit date: 2026-06-01

Scope:

```text
IA1 / OSM raw refresh
IB0 / activity-to-OSM candidates
IB0C / route anchors
IB0A / control point projection
IB0A-2 / route-axis anchor component QA
IB0B / control-points-only route-axis extraction
IB0B / route-definition points exporter
IB0D / v1.3b control-points-only contract QA
```

Formal cases:

```text
qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b
qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b
juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b
zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b
```

## Bottom line

IB0D v1.3b control-points-only contract QA completed.

IB1A / IB1C / IB1G / IB1E can proceed using:

```text
outputs\ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa\
```

Important caveat: IB0A is marked `PARTIAL`, not `CONVERGED`, because the projection outputs are present and clean but the stage does not yet emit an explicit PASS/WARN/FAIL gate.

## Machine-readable outputs

```text
outputs\ib0_route_axis_v1_3b_convergence_audit\ib0_route_axis_v1_3b_stage_convergence_audit.csv
outputs\ib0_route_axis_v1_3b_convergence_audit\ib0_route_axis_v1_3b_case_convergence_audit.csv
outputs\ib0_route_axis_v1_3b_convergence_audit\ib0_route_axis_v1_3b_convergence_summary.md
folder_inventory_depth4.csv
```

## Stage status

| stage | official_status | qa_gate | handoff |
|---|---:|---|---|
| IA1 / OSM raw refresh | CONVERGED | manifest/layer summary exists | Use `osm_raw_output\<case_id>` for IB0. |
| IB0 / activity-to-OSM candidates | CONVERGED | match summary exists | Use `outputs\ib0_route_match\<case_id>` candidates. |
| IB0C / route anchors | WARN | anchor manifest exists; not formal v1.3b trim authority | `outputs\ib0c_anchor` is legacy / QA reference only. |
| IB0A / control point projection | PARTIAL | no explicit PASS/WARN/FAIL gate | Add an IB0A summary gate. |
| IB0A-2 / route-axis anchor component QA | CONVERGED | explicit `status: PASS` in summary | Control points are on connected candidate graph component. |
| IB0B / control-points-only route-axis extraction | CONVERGED | summary plus downstream IB0D contract QA | Official route-axis root for IB0D. |
| IB0B / route-definition points exporter | CONVERGED | projection/order/offset validated by IB0D | `route_definition_control_points_used` is route-axis authority. |
| IB0D / v1.3b control-points-only contract QA | CONVERGED | explicit contract QA summary | Safe for IB1A / IB1C / IB1G / IB1E. |

## Stage details

### IA1 / OSM raw refresh

```text
official_status: CONVERGED
official_script: scripts\ia_osm\ia1_osm_fetch_raw_friendly_cli_qixing_schema.py
official_input_root_or_files: activity_input + configs route/case definitions
official_output_root: osm_raw_output\<case_id>
required_outputs: osm_raw_fetch_manifest.csv, osm_raw_layer_summary.csv, osm_highway_raw.geojson, osm_raw_layers_map.html
case_coverage: 4/4
qa_gate: manifest/layer summary exists
qa_result_by_case: 4/4 have required raw refresh outputs
known_warnings: none found in this audit
known_failures: none
legacy_roots_do_not_use: osm_raw_output_v1_1; archived raw folders
next_stage_input: outputs\ib0_route_match\<case_id>
handoff_note: use case-level v1.3b roots under osm_raw_output.
```

### IB0 / activity-to-OSM candidates

```text
official_status: CONVERGED
official_script: current IB0 route-match runner under scripts\ib0_route_match\
official_input_root_or_files: osm_raw_output\<case_id>; activity_input
official_output_root: outputs\ib0_route_match\<case_id>
required_outputs: activity_osm_candidates.geojson, activity_osm_matched.geojson, activity_osm_matched_map.html, activity_osm_match_summary.csv, activity_osm_match_run_summary.txt
case_coverage: 4/4
qa_gate: match summary exists
qa_result_by_case: 4/4 candidate roots present; selected_n > 0 in summaries
known_warnings: none blocking route-axis convergence
known_failures: none
legacy_roots_do_not_use: outputs\ib0b_mainline; outputs\ib0b_output
next_stage_input: outputs\ib0c_anchor\<case_id> and IB0A projection inputs
handoff_note: use ib0_candidates outputs, not old matched/pruned roots, for v1.3b route-axis branch.
```

### IB0C / route anchors

```text
official_status: WARN
official_script: scripts\ib0_route_match\ib0c_anchor_from_landmarks_v1_2_cli_updated.py
official_input_root_or_files: osm_raw_output\<case_id>; activity_input
official_output_root: outputs\ib0c_anchor\<case_id>
required_outputs: anchor_manifest.csv, route_anchors.csv, route_anchors.geojson, route_anchors_map.html
case_coverage: 4/4
qa_gate: anchor manifest exists; no formal v1.3b trim authority
qa_result_by_case: 4/4 present
known_warnings: zhonghua start/end use fallback_gpx_point; IB0C is legacy/QA reference only for v1.3b control-points-only
known_failures: none blocking because IB0D no longer uses IB0C as trim authority
legacy_roots_do_not_use: outputs\ib0c_anchor as IB0D trim authority
next_stage_input: outputs\ib0a_control_points_osm_projection\<case_id>; outputs\ib0b_route_definition_inputs_v1_3b\<case_id>
handoff_note: do not treat IB0C anchors as formal IB0D trim authority in v1.3b.
```

### IB0A / control point projection

```text
official_status: PARTIAL
official_script: scripts\ib0_route_match\ib0a_project_control_points_to_osm_candidates.py
official_input_root_or_files: configs\route_definitions\route_control_points_v1_3b.csv; outputs\ib0_route_match\<case_id>
official_output_root: outputs\ib0a_control_points_osm_projection\<case_id>
required_outputs: control_points_projected_to_osm_topk.csv, control_points_projected_to_osm_summary.txt, control_points_projected_to_osm_map.html
case_coverage: 4/4
qa_gate: no explicit PASS/WARN/FAIL gate
qa_result_by_case: projection_ok true for all grouped control points; max per-control min offset <= 9.423 m
known_warnings: outputs validate cleanly, but summary lacks explicit status
known_failures: none found
legacy_roots_do_not_use: outputs\ib0a_control_points_osm_projection\_archived_before_20260531_refresh
next_stage_input: outputs\ib0a2_route_axis_anchor_component_qa\<case_id>; outputs\ib0b_mainline_route_definition_v1_3b_control_points_only
handoff_note: add an IB0A summary gate that writes PASS/WARN/FAIL and validates required control roles.
```

### IB0A-2 / route-axis anchor component QA

```text
official_status: CONVERGED
official_script: scripts\ib0_route_match\ib0a2_route_axis_anchor_component_qa.py
official_input_root_or_files: outputs\ib0_route_match\<case_id>; outputs\ib0b_route_definition_inputs_v1_3b\<case_id>
official_output_root: outputs\ib0a2_route_axis_anchor_component_qa\<case_id>
required_outputs: ib0a2_route_axis_anchor_component_qa.csv, ib0a2_route_axis_anchor_component_pairs.csv, ib0a2_route_axis_anchor_component_qa_summary.txt
case_coverage: 4/4
qa_gate: explicit status in summary
qa_result_by_case: 4/4 status PASS; all adjacent control pairs connected; components_after_snap=1
known_warnings: none
known_failures: none
legacy_roots_do_not_use: none identified
next_stage_input: outputs\ib0b_mainline_route_definition_v1_3b_control_points_only
handoff_note: control points are on connected candidate graph component; start/end route-axis is separated from activity start/end where needed; trail_core component is valid.
```

### IB0B / control-points-only route-axis extraction

```text
official_status: CONVERGED
official_script: scripts\ib0_route_match\ib0b_route_mainline_extract_abtest_v1_cli_updated_control_point_constrained.py
official_input_root_or_files: outputs\ib0_route_match\<case_id>; outputs\ib0a_control_points_osm_projection\<case_id>; outputs\ib0b_route_definition_inputs_v1_3b\<case_id>
official_output_root: outputs\ib0b_mainline_route_definition_v1_3b_control_points_only
required_outputs: ordered_path, mainline, debug_segments, map, summary, route_definition_control_points_used csv+geojson
case_coverage: 4/4
qa_gate: summary plus downstream IB0D contract QA
qa_result_by_case: 4/4 expected route-axis lengths match; control points project in route order
known_warnings: coldwater has required-way QA, present and accepted
known_failures: none
legacy_roots_do_not_use: outputs\ib0b_mainline_route_definition_v1_3b; outputs\ib0b_mainline; outputs\ib0b_output
next_stage_input: outputs\ib0b_mainline_route_definition_v1_3b_control_points_only
handoff_note: official route-axis root for IB0D v1.3b.
```

Expected ordered path lengths verified:

```text
qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b  4187.392949
qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b   3245.056611
juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b        3695.539299
zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b   5447.777653
```

### IB0B / route-definition points exporter

```text
official_status: CONVERGED
official_script: scripts\ib0_route_match\ib0b_export_route_definition_points_used_v1_2_phase_aware.py
official_input_root_or_files: configs\route_definitions\route_control_points_v1_3b.csv; IB0B ordered_path
official_output_root: outputs\ib0b_mainline_route_definition_v1_3b_control_points_only
required_outputs: route_definition_control_points_used_ib0_candidates.csv, route_definition_control_points_used_ib0_candidates.geojson
case_coverage: 4/4
qa_gate: projection_ok/order/offset validated by IB0D contract QA
qa_result_by_case: 4/4 route_definition_control_points_used files present; projection_ok true; projected order monotonic
known_warnings: none
known_failures: none
legacy_roots_do_not_use: older exporter v1/v1_1 outputs if regenerated outside official root
next_stage_input: outputs\ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa
handoff_note: this exporter output is the route-axis control point authority.
```

### IB0D / v1.3b control-points-only contract QA

```text
official_status: CONVERGED
official_script: scripts\ib0_route_match\ib0d_v1_3b_control_points_only_contract_qa.py
official_input_root_or_files: outputs\ib0b_mainline_route_definition_v1_3b_control_points_only
official_output_root: outputs\ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa
required_outputs: ib0d_v1_3b_contract_qa_summary_all.csv plus per-case route_points.csv, trim_summary.csv, qa_summary.txt, qa_map.html
case_coverage: 4/4
qa_gate: explicit contract QA summary
qa_result_by_case: 1 PASS, 3 reviewed WARN; unexpected_self_near_pair_count=0; safe_for_ib1=True for all
known_warnings: same-entry routes use keep_full policy; self_near_pair_count high but expected
known_failures: none
legacy_roots_do_not_use: outputs\ib0d_trimmed_mainline_v1_3b_control_points_only; outputs\ib0d_trimmed_mainline
next_stage_input: outputs\ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa
handoff_note: IB0D v1.3b contract QA completed; IB1A / IB1C / IB1G / IB1E can proceed.
```

IB0D case status:

```text
juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b       PASS
qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b WARN
qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b  WARN
zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b  WARN
```

WARN acceptance criteria verified:

```text
same-entry route uses keep_full policy
self_near_pair_count high but explainable as expected same-entry/summit self-near
unexpected_self_near_pair_count = 0
safe_for_ib1a_ib1c_ib1g_ib1e = True
```

## Final answers

```text
1. IA1 是否收束？CONVERGED
2. IB0 是否收束？CONVERGED
3. IB0C 是否收束？WARN
4. IB0A 是否收束？PARTIAL
5. IB0A-2 是否收束？CONVERGED
6. IB0B 是否收束？CONVERGED
7. IB0D 是否收束？CONVERGED
8. 哪些階段只有 WARN？IB0C has WARN; IB0D has accepted case-level WARN but stage is CONVERGED.
9. 是否可進 IB1A / IB1C / IB1G / IB1E？YES
10. 下一階段正式 input root？outputs\ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa\
```

Required follow-up:

```text
IB0A needs a formal summary gate to move from PARTIAL to CONVERGED.
```
