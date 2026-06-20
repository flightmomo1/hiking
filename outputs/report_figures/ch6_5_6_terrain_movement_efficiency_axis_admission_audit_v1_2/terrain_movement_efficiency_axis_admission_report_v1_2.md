# CH6.5.6 Terrain Movement Efficiency Axis Admission Audit v1.2

- axis_admission_decision: `ADMIT_TO_RADAR_V1_DESCRIPTIVE_SUPPORTED_AXIS_WITH_BOUNDARY`
- recommended_axis_id: `terrain_movement_efficiency`
- recommended_axis_label_zh: `地形移動維持（描述性）`
- gate_pass_count: `13` / `13`
- failed_gate_ids: `NONE`
- source_input_path: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_route_load_context_index_v1\route_load_context_windows_v1.csv`

## Boundary

CH6.5.6 terrain movement efficiency axis admission audit is governance review only. It decides whether a descriptive evidence axis may enter the next radar revision. It does not compute or authorize ability scores, ability ranks, ability classes, THCI scores, radar scores, final hiking risk scores, route suitability scores, go/no-go decisions, medical diagnoses, or causality claims.

## Radar Update Recommendation

Use terrain_movement_efficiency_axis_update_v1.csv to replace the previous missing-evidence terrain movement efficiency axis in the next radar revision. Keep route-following stability missing until separate route-following evidence exists.

If admitted, the axis may replace the previous missing-evidence terrain movement efficiency axis in the next radar revision as descriptive terrain movement maintenance context only. Route-following stability remains missing until separate on-route / wrong-branch / deviation-recovery evidence is available.

## Gate Detail

| gate_id | gate_status | gate_name | observed_value | required_value | notes |
|---|---|---|---|---|---|
| G01 | PASS | CH6.5.6 audit conclusion is PASS | PASS_CH6_5_6_TERRAIN_MOVEMENT_EFFICIENCY_EVIDENCE_V1_DESCRIPTIVE_ONLY | PASS_CH6_5_6_TERRAIN_MOVEMENT_EFFICIENCY_EVIDENCE_V1_DESCRIPTIVE_ONLY | Evidence layer must pass before radar admission. |
| G02 | PASS | No zero-fill used | zero_fill_used=False; weather_zero_fill_used=False | Both False | Missing evidence must not become zero, no-rain, normal, calm, or safe evidence. |
| G03 | PASS | No forbidden scoring / decision output | ability_score_generated=False; ability_rank_generated=False; ability_class_generated=False; route_suitability_score_generated=False; go_no_go_generated=False | All False | Admission does not authorize scoring, ranking, suitability, or go/no-go output. |
| G04 | PASS | Audit issues are none | NONE | NONE | Any audit issue must be resolved before admission. |
| G05 | PASS | Expected activity coverage | activity_rows=25; axis_update_rows=25 | 25 activity rows and 25 axis rows | Radar axis should cover the current full25 activity set. |
| G06 | PASS | All rows have supported terrain movement evidence | supported=25; limited=0; insufficient=0 | supported=25; limited=0; insufficient=0 | This admits the axis as supported for the current activity set. |
| G07 | PASS | Context groups meet minimum window threshold | context_group_count=3; min_window_count=39.0 | Each context group >= 20 windows | Small groups remain caution notes, but are acceptable if above threshold. |
| G08 | PASS | Axis index has useful variation | unique_n=25; min=4.0; max=100.0 | >=5 unique values within 0-100 | Radar axis should not be flat or out of range. |
| G09 | PASS | Lower/reference/higher labels all appear | HIGHER_TERRAIN_MOVEMENT_MAINTENANCE_CONTEXT\|LOWER_TERRAIN_MOVEMENT_MAINTENANCE_CONTEXT_REVIEW\|REFERENCE_TERRAIN_MOVEMENT_MAINTENANCE_CONTEXT | Contains lower, reference, and higher context labels | Labels support interpretation; they are not ability classes. |
| G10 | PASS | Upstream provenance is documented | input_found=True; route_window_found=True | full25 input and route-window evidence documented | v1.2 checks run report, CURRENT_INDEX, README, and CH6.5.6 source inventory. |
| G11 | PASS | Upstream route/terrain/map-derived factors are documented | route_terrain_factor_docs=True | vertical range, slope, IB2 effort, IB2 terrain, near-steps | Axis must be grounded in terrain/surface context, not only speed. |
| G12 | PASS | Weather boundary is documented | weather_boundary_docs=True | weather descriptive only, not included in index, no zero-fill | Weather context cannot be hidden route-load or ability evidence. |
| G13 | PASS | Upstream non-score boundary is documented | upstream_boundary_docs=True | descriptive and not score/rank/final risk | The radar admission inherits the same non-scoring boundary. |

## Context Notes

| note_id | note_type | subject | window_count | activity_count | note |
|---|---|---|---|---|---|
| CONTEXT_HIGH_ROUTE_LOAD_OR_SLOPE_CONTEXT | SMALL_CONTEXT_GROUP_CAUTION | HIGH_ROUTE_LOAD_OR_SLOPE_CONTEXT | 39 | 19 | Smallest context group. It passes the minimum window threshold but should be reported with caution. |
| CONTEXT_LOW_INFORMATION_MIXED_CONTEXT | REFERENCE_CONTEXT_NOTE | LOW_INFORMATION_MIXED_CONTEXT | 531 | 25 | Mixed or lower-information context retained for descriptive comparison. |
| CONTEXT_STEPS_CONTEXT | ROUTE_CHARACTERISTIC_NOTE | STEPS_CONTEXT | 1484 | 25 | Dominant route context; consistent with step/stair-heavy route sections. Not ability evidence by itself. |
| LABEL_HIGHER_TERRAIN_MOVEMENT_MAINTENANCE_CONTEXT | ACTIVITY_LABEL_DISTRIBUTION | HIGHER_TERRAIN_MOVEMENT_MAINTENANCE_CONTEXT |  | 7 | Activities: 14_1\|15_1\|30_1\|33_1\|35_1\|41_1\|45_1. Label is descriptive group-relative context, not ability class. |
| LABEL_LOWER_TERRAIN_MOVEMENT_MAINTENANCE_CONTEXT_REVIEW | ACTIVITY_LABEL_DISTRIBUTION | LOWER_TERRAIN_MOVEMENT_MAINTENANCE_CONTEXT_REVIEW |  | 7 | Activities: 16_1\|23_1\|28_1\|42_1\|43_1\|46_1\|48_1. Label is descriptive group-relative context, not ability class. |
| LABEL_REFERENCE_TERRAIN_MOVEMENT_MAINTENANCE_CONTEXT | ACTIVITY_LABEL_DISTRIBUTION | REFERENCE_TERRAIN_MOVEMENT_MAINTENANCE_CONTEXT |  | 11 | Activities: 13_1\|20_1\|29_1\|36_1\|37_1\|38_1\|3_1\|40_1\|44_1\|8_1\|9_1. Label is descriptive group-relative context, not ability class. |
| RADAR_UPDATE_RECOMMENDATION | RADAR_GOVERNANCE | terrain_movement_efficiency |  |  | If admitted, the axis may replace the previous missing-evidence terrain movement efficiency axis in the next radar revision as descriptive terrain movement maintenance context only. Route-following stability remains missing until separate on-route / wrong-branch / deviation-recovery evidence is available. |