# Current Index - 2026-06-05 IB3 Activity Pipeline Inventory

## Current Formal Route / THCI Position

- Route-level formal v1.3b roots remain the baseline route and route-risk layer.
- THCI v1.0c is the current recommended display/scoring version.
- THCI v1.0c has not yet been recomputed for qixing repaired root.

## Current IB3 Activity Roots

Current v1.3b / THCI v1.0c IB3 roots:

- `outputs/ib3a_sequence_mapmatched_activity_v1_3b_thci_v1_0c`
- `outputs/ib3a2_on_route_activity_filter_v1_3b_thci_v1_0c`
- `outputs/ib3_activity_profile_visual_qa_v1_3b_thci_v1_0c`

Qixing repair candidate / review roots:

- `outputs/ib0d_trimmed_mainline_v1_3b_qixing_via_corridor_repair_candidate`
- `outputs/ib1_route_profile_v1_3b_qixing_via_corridor_repair_candidate`
- `outputs/ib1e_route_profile_contour_window_terrain_v1_3b_qixing_via_corridor_repair_candidate`
- `outputs/ib3a_sequence_mapmatched_activity_v1_3b_qixing_via_corridor_repair_candidate`
- `outputs/ib3a2_on_route_activity_filter_v1_3b_qixing_via_corridor_repair_candidate`
- `outputs/ib3_activity_profile_visual_qa_v1_3b_qixing_via_corridor_repair_candidate`
- `outputs/qixing_via_corridor_repaired_formal_visual_review_v1_3b`
- `outputs/ib3_route_choice_inference_conclusion_v1_3b_qixing`
- `outputs/ib3f_activity_route_features_v1_3b_qixing_repaired_review`
- `outputs/ib3a2_qixing_wrong_branch_evidence_v1_3b`
- `outputs/ib3a2_qixing_repaired_threshold_sensitivity_v1_3b`

## Current Scripts

THCI:

- `scripts/thci_compute_axis_scores_v1_0c.py`
- `scripts/thci_plot_radar_v1_0c.py`
- `scripts/audit_thci_v1_0c_official_display_convergence.ps1`
- `scripts/ib2d_plot_route_risk_offline_map_with_thci_v1_0b.py`

IB3A / IB3A2 / IB3B:

- `scripts/ib3_activity_environment/ib3a_sequence_mapmatch_standardized_activity_folder_cli.py`
- `scripts/ib3_activity_environment/ib3a2_filter_mapmatched_activity_on_route.py`
- `scripts/ib3_activity_environment/ib3b2_plot_activity_profile_1d_2d.py`
- `scripts/ib3_activity_environment/ib3f_extract_activity_route_features_v1_3b.py`
- `scripts/audit_ib3f_qixing_repaired_review_smoke_v1_3b.ps1`
- `scripts/ib3_activity_environment/plot_ib3f_qixing_repaired_review_feature_summary_v1_3b.py`
- `scripts/ib3_activity_environment/plot_ib3f_activity_story_map_v1_3b.py`

Qixing repair and route-choice review:

- `scripts/audit_qixing_lengshuikeng_via_corridor_route_axis_oscillation_v1_3b.py`
- `scripts/diagnose_qixing_lengshuikeng_via_corridor_repair_plan_v1_3b.py`
- `scripts/ib0d_prune_qixing_via_corridor_local_loop_candidate_v1_3b.py`
- `scripts/audit_qixing_via_corridor_pruning_activity_rawdata_safety_v1_3b.py`
- `scripts/audit_qixing_via_corridor_repair_candidate_formal_review_v1_3b.ps1`
- `scripts/audit_qixing_via_corridor_repair_candidate_promotion_gate_v1_3b.ps1`
- `scripts/plot_qixing_via_corridor_repaired_formal_before_after_html_v1_3b.py`
- `configs/risk_semantics/qixing_branch_corridor_definition_v1_3b.csv`
- `scripts/ib3_activity_environment/plot_qixing_branch_corridor_definition_qa_v1_3b.py`
- `scripts/ib3_activity_environment/ib3_route_choice_inference_qixing_v1_3b.py`
- `scripts/ib3_activity_environment/ib3_route_choice_inference_qixing_geometry_v2_v1_3b.py`
- `scripts/ib3_activity_environment/plot_qixing_raw_gps_vs_projected_route_choice_qa_v1_3b.py`
- `scripts/ib3_activity_environment/audit_qixing_route_choice_inference_conclusion_v1_3b.ps1`
- `scripts/ib3_activity_environment/audit_ib3f_qixing_37_1_descent_wrong_branch_candidate_v1_3b.py`
- `scripts/ib3_activity_environment/audit_ib3a2_qixing_repaired_threshold_sensitivity_v1_3b.py`
- `scripts/ib3_activity_environment/audit_ib3a2_qixing_wrong_branch_evidence_v1_3b.py`

## Boundary Notes

- Qixing repaired baseline is usable with `remap_review_note`.
- Promotion gate = `PASS_WITH_REMAP_REVIEW_NOTE`.
- Route-choice status = `AUTOMATIC_CLASSIFICATION_NOT_RELIABLE_REVIEW_REQUIRED`.
- Keep `route_choice_review_required = true`.
- Do not force canonical branch classification.
- Do not overwrite previous formal v1.3b roots.
- IB3F qixing repaired review smoke status = `PASS_WITH_REVIEW_CASE`.
- 37_1 local movement review status = `POSSIBLE_WRONG_BRANCH_REVIEW`.
- Local movement evidence does not justify changing formal IB3A2 threshold; future work should add review-only flags.

## Next Recommended Stage

Extend IB3F activity feature extraction:

- `scripts/ib3_activity_environment/ib3f_extract_activity_route_features_v1_3b.py`

This consumes IB3A sequence, IB3A2 on-route labels, IB1E route context, IB2 route risk, and optional THCI v1.0c context snapshot.

Next step: extend from qixing repaired review smoke to broader formal / multi-activity batch, then integrate local movement review flags into IB3F feature outputs and story map.
