# Current Pipeline Update - IB3 Activity Pipeline Inventory

Date: 2026-06-05

## Current Status

- THCI v1.0c is the current recommended display/scoring version.
- The qixing_lengshuikeng repaired baseline is usable with `remap_review_note`.
- Qixing activity route-choice automatic classification is not reliable.
- `route_choice_review_required = true` remains the correct route-choice status.
- The next stage is IB3F activity feature extraction, not further route-choice forcing.

## Route-Level Formal Pipeline

Current route-level baseline and route-risk flow:

1. IA1 refreshed OSM raw
2. IB0 route match
3. IB0C anchors
4. IB0A control point projection
5. IB0A-2 route-axis anchor/component QA
6. IB0B mainline
7. IB0D trimmed mainline
8. IB1A route profile
9. IB1C OSM semantics
10. IB1C semantic risk
11. IB1G NLSC contour window
12. IB1E OSM + NLSC terrain
13. IB2 / IB2D route risk / offline map
14. THCI v1.0c official display

## THCI Current Recommended Version

Current THCI scripts:

- `scripts/thci_compute_axis_scores_v1_0c.py`
- `scripts/thci_plot_radar_v1_0c.py`
- `scripts/audit_thci_v1_0c_official_display_convergence.ps1`
- `scripts/ib2d_plot_route_risk_offline_map_with_thci_v1_0b.py`

Note: `ib2d_plot_route_risk_offline_map_with_thci_v1_0b.py` keeps the older filename, but its CLI supports `--thci-version v1_0c`.

THCI v1.0c has not yet been recomputed for the qixing repaired root.

## Current Activity Projection / QA Pipeline

Current IB3 activity projection and QA scripts:

- `scripts/ib3_activity_environment/ib3a_sequence_mapmatch_standardized_activity_folder_cli.py`
- `scripts/ib3_activity_environment/ib3a2_filter_mapmatched_activity_on_route.py`
- `scripts/ib3_activity_environment/ib3b2_plot_activity_profile_1d_2d.py`
- `scripts/audit_ib3_qixing_lengshuikeng_v1_3b_thci_v1_0c_smoke_test.ps1`
- `scripts/audit_ib3_v1_3b_thci_v1_0c_multiactivity_smoke.ps1`

## Qixing Repaired Baseline Review Status

The previous formal `qixing_lengshuikeng` route baseline had via corridor route-axis local oscillation / connector bounce.

Repair status:

- repair layer = IB0D local loop pruning candidate
- pruned ranges = 626-788 m and 3442-3608 m
- downstream candidate revalidation completed through IB1A / IB1C / IB1G / IB1E / IB2 / IB2D / IB3 sequence / IB3A2 / IB3B2 visual QA
- rawdata safety = `PASS_RAWDATA_SAFE_REMAP_REVIEW_REQUIRED`
- promotion gate = `PASS_WITH_REMAP_REVIEW_NOTE`
- repaired baseline usable with `remap_review_note`
- previous formal roots preserved
- repaired formal/candidate roots should not silently overwrite previous formal roots
- THCI v1.0c remains pending for the repaired root

Relevant commits:

- `4cdfc8e Add qixing via corridor route-axis repair diagnostics`
- `e11d4c7 Add qixing via corridor pruning rawdata safety audit`
- `5fc10a9 Add qixing via corridor repaired baseline review gates`

## Qixing Route-Choice Review Conclusion

Route-choice review status:

- route-choice v1 point-proximity inference completed
- route-choice v2 corridor-geometry inference completed
- raw GPS vs projected QA completed
- final status = `AUTOMATIC_CLASSIFICATION_NOT_RELIABLE_REVIEW_REQUIRED`
- `route_choice_review_required = true`
- do not force canonical branch classification for qixing_lengshuikeng activities
- non-canonical activity route choice should be treated as actual route-choice variation, not an error

Relevant commit:

- `265fccd Add qixing route-choice review workflow`

## IB3B2 Visual QA Enhancement

`scripts/ib3_activity_environment/ib3b2_plot_activity_profile_1d_2d.py` now supports:

- `--route-context-root`
- `--route-profile-root`
- `--corridor-definition-csv`
- current v1.3b / qixing repair candidate roots
- corridor overlay in 1D panels and 2D route board

Relevant commit:

- `3b7a561 Enhance IB3B2 activity profile visual QA roots and corridor overlay`

## IB3F First Implementation

IB3F activity route feature extraction v1.3b has a first qixing repaired review smoke implementation.

Relevant commit:

- `ca126f5 Add IB3F qixing repaired review feature smoke`

Scripts:

- `scripts/ib3_activity_environment/ib3f_extract_activity_route_features_v1_3b.py`
- `scripts/audit_ib3f_qixing_repaired_review_smoke_v1_3b.ps1`
- `scripts/ib3_activity_environment/plot_ib3f_qixing_repaired_review_feature_summary_v1_3b.py`
- `scripts/ib3_activity_environment/plot_ib3f_activity_story_map_v1_3b.py`

Smoke status:

- `IB3F_QIXING_REPAIRED_REVIEW_SMOKE_STATUS = PASS_WITH_REVIEW_CASE`
- `37_1` / `33_1` = `PASS_REVIEW_READY`
- `15_1` = `REVIEW_REQUIRED_LOW_ON_ROUTE_RATIO`
- speed / HR available for all three activities
- route risk join coverage = 1.0 for all three activities

## Qixing Local Movement Review Diagnostics

Local movement review diagnostics were added for the visually suspicious 37_1 descent segment and qixing repaired threshold sensitivity review.

Relevant commit:

- `96da026 Add qixing local movement review diagnostics`

Scripts:

- `scripts/ib3_activity_environment/audit_ib3f_qixing_37_1_descent_wrong_branch_candidate_v1_3b.py`
- `scripts/ib3_activity_environment/audit_ib3a2_qixing_repaired_threshold_sensitivity_v1_3b.py`
- `scripts/ib3_activity_environment/audit_ib3a2_qixing_wrong_branch_evidence_v1_3b.py`

Key result:

- `WRONG_BRANCH_EVIDENCE_STATUS = POSSIBLE_WRONG_BRANCH_REVIEW`
- heading_diff_median = 113.72 deg
- heading_diff_p90 = 165.04 deg
- offset remains low, so this does not justify changing the formal IB3A2 threshold

Recommendation:

- keep formal `usable_on_route` unchanged
- add a future review-only `local_movement_review_required` / `possible_wrong_branch_review` flag

## Current Script Registry

Current maintained groups:

- formal route-level scripts
- THCI scripts
- current IB3A / IB3A2 / IB3B scripts
- qixing-specific review tools
- route-choice review tools
- visual QA tools

## Legacy / Archived Tools

Legacy v1b-v1h activity recovery and older IB3C adaptive speed / behavior scripts are historical reference only. They are not the current formal IB3 pipeline.

## Prototype / Research Tools

Weather, microclimate, and IB4 prototype tools remain research/prototype scripts. They are not the current formal THCI / IB3F pipeline.

## Next Stage: Broader IB3F Activity Feature Extraction

IB3F now exists for qixing repaired review smoke. The next stage is to extend it to broader formal / multi-activity batch usage.

Current script:

- `scripts/ib3_activity_environment/ib3f_extract_activity_route_features_v1_3b.py`

Inputs:

- IB3A sequence root
- IB3A2 on-route root
- IB1E route context root
- IB2 route risk root
- optional THCI v1.0c root

CLI:

- `--case-id`
- `--route-folder`
- `--activity-id` / `--activity-ids`
- `--sequence-root`
- `--ib3a2-root`
- `--route-context-root`
- `--route-risk-root`
- `--thci-root`
- `--out-dir`

Phase 1 output:

- per-activity feature table

Phase 2 output:

- per-segment / per-window feature table

Feature groups:

- route progress
- reliability
- motion
- physiology if available
- terrain exposure
- route risk exposure
- THCI context snapshot
- review flags

## Known Boundaries / Do Not Overwrite Rules

- Do not overwrite previous formal v1.3b roots with qixing repaired roots without explicit review.
- Do not describe the qixing repaired root as THCI v1.0c recomputed.
- Do not force qixing activity route-choice into canonical branch classification.
- Do not turn qixing local movement review diagnostics into formal IB3A2 threshold changes without a separate review.
- Do not treat legacy v1b-v1h activity recovery outputs as current formal IB3.
- Do not treat weather prototype scripts as current THCI / IB3F formal pipeline.
