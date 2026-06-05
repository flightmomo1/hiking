# Latest Handoff - IB3 Activity Pipeline Inventory

Date: 2026-06-05

## Current Version Position

- THCI v1.0c = current recommended display/scoring version.
- THCI v1.0b = previous recommended baseline, preserved.
- Qixing repaired baseline is usable with `remap_review_note`.
- Qixing route-choice automatic classification is not reliable; keep `route_choice_review_required = true`.
- Next stage: build IB3F activity feature extraction.

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

## Recommended Next Action

Start IB3F activity feature extraction:

- do not continue forcing qixing route-choice classification
- do not overwrite previous formal v1.3b roots
- do not recompute THCI for repaired root until explicitly requested
- use IB3A / IB3A2 / IB3B evidence as the input basis for IB3F
