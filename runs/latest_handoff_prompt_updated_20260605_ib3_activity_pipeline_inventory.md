# Latest Handoff - IB3 Activity Pipeline Inventory

Date: 2026-06-05

## Current Version Position

- THCI v1.0c = current recommended display/scoring version.
- THCI v1.0b = previous recommended baseline, preserved.
- Qixing repaired baseline is usable with `remap_review_note`.
- Qixing route-choice automatic classification is not reliable; keep `route_choice_review_required = true`.
- IB3F first implementation exists for qixing repaired review smoke.
- Next stage: extend IB3F from qixing repaired review smoke to broader formal / multi-activity batch.

## Current Route-Level Pipeline

IA1 refreshed OSM raw -> IB0 route match -> IB0C anchors -> IB0A control point projection -> IB0A-2 route-axis anchor/component QA -> IB0B mainline -> IB0D trimmed mainline -> IB1A route profile -> IB1C OSM semantics -> IB1C semantic risk -> IB1G NLSC contour window -> IB1E OSM + NLSC terrain -> IB2 / IB2D route risk / offline map -> THCI v1.0c official display.

## Current IB3 Pipeline

Current activity projection / QA scripts:

- `scripts/ib3_activity_environment/ib3a_sequence_mapmatch_standardized_activity_folder_cli.py`
- `scripts/ib3_activity_environment/ib3a2_filter_mapmatched_activity_on_route.py`
- `scripts/ib3_activity_environment/ib3b2_plot_activity_profile_1d_2d.py`
- `scripts/audit_ib3_qixing_lengshuikeng_v1_3b_thci_v1_0c_smoke_test.ps1`
- `scripts/audit_ib3_v1_3b_thci_v1_0c_multiactivity_smoke.ps1`

## Qixing Repaired Baseline

The previous formal qixing_lengshuikeng route baseline had via corridor route-axis local oscillation / connector bounce.

- repair layer = IB0D local loop pruning candidate
- pruned ranges = 626-788 m and 3442-3608 m
- downstream candidate revalidation completed
- rawdata safety = `PASS_RAWDATA_SAFE_REMAP_REVIEW_REQUIRED`
- promotion gate = `PASS_WITH_REMAP_REVIEW_NOTE`
- repaired baseline usable with `remap_review_note`
- previous formal roots are preserved
- THCI v1.0c has not yet been recomputed for repaired root

Relevant commits:

- `4cdfc8e Add qixing via corridor route-axis repair diagnostics`
- `e11d4c7 Add qixing via corridor pruning rawdata safety audit`
- `5fc10a9 Add qixing via corridor repaired baseline review gates`

## Qixing Route-Choice Review

- v1 point-proximity inference and v2 corridor-geometry inference completed.
- raw GPS vs projected QA completed.
- final status = `AUTOMATIC_CLASSIFICATION_NOT_RELIABLE_REVIEW_REQUIRED`
- `route_choice_review_required = true`
- Do not force canonical branch classification.

Relevant commit:

- `265fccd Add qixing route-choice review workflow`

## IB3B2 Visual QA

`ib3b2_plot_activity_profile_1d_2d.py` now supports current root overrides and corridor overlay:

- `--route-context-root`
- `--route-profile-root`
- `--corridor-definition-csv`

Relevant commit:

- `3b7a561 Enhance IB3B2 activity profile visual QA roots and corridor overlay`

## IB3F First Implementation

Relevant commit:

- `ca126f5 Add IB3F qixing repaired review feature smoke`

Scripts:

- `scripts/ib3_activity_environment/ib3f_extract_activity_route_features_v1_3b.py`
- `scripts/audit_ib3f_qixing_repaired_review_smoke_v1_3b.ps1`
- `scripts/ib3_activity_environment/plot_ib3f_qixing_repaired_review_feature_summary_v1_3b.py`
- `scripts/ib3_activity_environment/plot_ib3f_activity_story_map_v1_3b.py`

Status:

- `IB3F_QIXING_REPAIRED_REVIEW_SMOKE_STATUS = PASS_WITH_REVIEW_CASE`
- `37_1` / `33_1` = `PASS_REVIEW_READY`
- `15_1` = `REVIEW_REQUIRED_LOW_ON_ROUTE_RATIO`
- speed / HR available for all three activities
- route risk join coverage = 1.0 for all three activities

## Qixing Local Movement Review Diagnostics

Relevant commit:

- `96da026 Add qixing local movement review diagnostics`

Scripts:

- `scripts/ib3_activity_environment/audit_ib3f_qixing_37_1_descent_wrong_branch_candidate_v1_3b.py`
- `scripts/ib3_activity_environment/audit_ib3a2_qixing_repaired_threshold_sensitivity_v1_3b.py`
- `scripts/ib3_activity_environment/audit_ib3a2_qixing_wrong_branch_evidence_v1_3b.py`

37_1 descent local segment:

- `WRONG_BRANCH_EVIDENCE_STATUS = POSSIBLE_WRONG_BRANCH_REVIEW`
- heading_diff_median = 113.72 deg
- heading_diff_p90 = 165.04 deg
- offset remains low, so this does not justify changing the formal IB3A2 threshold
- recommendation: keep formal `usable_on_route` unchanged; add future review-only `local_movement_review_required` / `possible_wrong_branch_review` flag

## Recommended Next Action

Extend IB3F activity feature extraction:

- do not continue forcing qixing route-choice classification
- do not overwrite previous formal v1.3b roots
- do not recompute THCI for repaired root until explicitly requested
- extend IB3F from qixing repaired review smoke to broader formal / multi-activity batch
- future enhancement: integrate local movement review flags into IB3F feature outputs and story map
