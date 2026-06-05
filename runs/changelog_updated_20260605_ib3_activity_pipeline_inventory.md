# Changelog - 2026-06-05 IB3 Activity Pipeline Inventory

## Added Documentation Scope

This update records the current IB3 activity pipeline inventory and qixing repaired baseline status.

## Current Recommended Display / Scoring Version

- THCI v1.0c remains the current recommended display/scoring version.
- THCI v1.0c has not yet been recomputed for the qixing repaired root.

## Qixing Repaired Baseline Status

- Previous formal qixing_lengshuikeng route baseline showed via corridor route-axis local oscillation / connector bounce.
- Repair layer = IB0D local loop pruning candidate.
- Pruned ranges = 626-788 m and 3442-3608 m.
- Downstream candidate revalidation completed through IB1A / IB1C / IB1G / IB1E / IB2 / IB2D / IB3 sequence / IB3A2 / IB3B2 visual QA.
- Rawdata safety = `PASS_RAWDATA_SAFE_REMAP_REVIEW_REQUIRED`.
- Promotion gate = `PASS_WITH_REMAP_REVIEW_NOTE`.
- Repaired baseline is usable with `remap_review_note`.
- Previous formal roots are preserved and should not be silently overwritten.

Relevant commits:

- `4cdfc8e Add qixing via corridor route-axis repair diagnostics`
- `e11d4c7 Add qixing via corridor pruning rawdata safety audit`
- `5fc10a9 Add qixing via corridor repaired baseline review gates`

## Qixing Route-Choice Review

- v1 point-proximity inference completed.
- v2 corridor-geometry inference completed.
- raw GPS vs projected QA completed.
- final status = `AUTOMATIC_CLASSIFICATION_NOT_RELIABLE_REVIEW_REQUIRED`.
- `route_choice_review_required = true`.
- Do not force canonical branch classification for qixing_lengshuikeng activities.

Relevant commit:

- `265fccd Add qixing route-choice review workflow`

## IB3B2 Visual QA Enhancement

- `scripts/ib3_activity_environment/ib3b2_plot_activity_profile_1d_2d.py` supports current route context/profile root overrides.
- It supports `--corridor-definition-csv`.
- It can show corridor overlay in 1D panels and 2D route board.

Relevant commit:

- `3b7a561 Enhance IB3B2 activity profile visual QA roots and corridor overlay`

## IB3F First Implementation

- Added first IB3F activity route feature extraction smoke for qixing repaired review.
- `IB3F_QIXING_REPAIRED_REVIEW_SMOKE_STATUS = PASS_WITH_REVIEW_CASE`.
- `37_1` / `33_1` = `PASS_REVIEW_READY`.
- `15_1` = `REVIEW_REQUIRED_LOW_ON_ROUTE_RATIO`.
- Speed / HR available for all three.
- Route risk join coverage = 1.0 for all three.

Relevant commit:

- `ca126f5 Add IB3F qixing repaired review feature smoke`

Scripts:

- `scripts/ib3_activity_environment/ib3f_extract_activity_route_features_v1_3b.py`
- `scripts/audit_ib3f_qixing_repaired_review_smoke_v1_3b.ps1`
- `scripts/ib3_activity_environment/plot_ib3f_qixing_repaired_review_feature_summary_v1_3b.py`
- `scripts/ib3_activity_environment/plot_ib3f_activity_story_map_v1_3b.py`

## Qixing Local Movement Review Diagnostics

- Added local movement diagnostics for 37_1 descent visual wrong-branch review.
- `WRONG_BRANCH_EVIDENCE_STATUS = POSSIBLE_WRONG_BRANCH_REVIEW`.
- heading_diff_median = 113.72 deg.
- heading_diff_p90 = 165.04 deg.
- Offset remains low, so this does not justify changing the formal IB3A2 threshold.
- Recommendation: keep formal `usable_on_route` unchanged; add review-only `local_movement_review_required` / `possible_wrong_branch_review` flag in future.

Relevant commit:

- `96da026 Add qixing local movement review diagnostics`

Scripts:

- `scripts/ib3_activity_environment/audit_ib3f_qixing_37_1_descent_wrong_branch_candidate_v1_3b.py`
- `scripts/ib3_activity_environment/audit_ib3a2_qixing_repaired_threshold_sensitivity_v1_3b.py`
- `scripts/ib3_activity_environment/audit_ib3a2_qixing_wrong_branch_evidence_v1_3b.py`

## Next Stage

Next engineering step: extend IB3F from qixing repaired review smoke to broader formal / multi-activity batch.

Future enhancement: integrate local movement review flags into IB3F feature outputs and story map.

Do not treat legacy v1b-v1h recovery or old IB3C adaptive behavior scripts as current formal IB3.
