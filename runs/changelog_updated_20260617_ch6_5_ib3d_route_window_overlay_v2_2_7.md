# Changelog — CH6.5 IB3D Route-Window Overlay and v2.2.7 Review-Safe Profiles

## Added

- Added `make_ch6_5_ib3d_event_route_window_bridge_v1.py`.
- Added `make_ch6_5_ib3d_event_route_window_bridge_preview_png_v1.py`.
- Added `make_ch6_single_activity_surface_profile_v2_2_7_ib3d_review_safe_status.py`.
- Added CH6.5 IB3D event route-window bridge outputs.
- Added CH6.5 single-activity surface profile v2.2.7 IB3D review-safe status outputs.

## IB3D Event Route-Window Bridge v1

Output root:

`outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1`

Local closeout inventory:

- CSV files: 51
- PNG files: 4
- MD files: 1

Key outputs:

- `ib3d_event_route_window_bridge_summary.csv`
- `ib3d_event_route_window_bridge_run_report.md`
- `ib3d_event_route_window_bridge_preview_all.png`
- activity preview PNGs for `20_1`, `37_1`, and `9_1`
- per-activity mapping review CSVs
- per-activity route-window overlay CSVs

## v2.2.7 Single-Activity Surface Profiles

Output root:

`outputs\report_figures\ch6_single_activity_surface_profiles_v2_2_7_ib3d_review_safe_status`

Local closeout inventory:

- CSV files: 51
- PNG files: 50
- MD files: 51

Key outputs:

- `ch6_5_single_activity_surface_profiles_v2_2_7_ib3d_review_safe_status_master_run_report.md`
- `ib3d_overlay_drawable_diagnosis_full25.csv`
- per-activity CSV / PNG / MD / run-report outputs
- per-activity shelter context zone CSVs
- top-level copied PNGs for report/reference use

## Method Decision

This package is a display and annotation bridge.

The IB3D event bridge translates elapsed-time event intervals into route-window overlays. The v2.2.7 profile layer displays those annotations with review-safe status on single-activity surface profiles.

This makes IB3D/event context visible in Chapter 6.5 figures without using those events as causal evidence or as route-load evidence.

## Boundary

This changelog records descriptive visualization/evidence outputs only.

No evidence recalculation, ability scoring, ability ranking, ability class generation, THCI scoring, radar scoring, route suitability scoring, final hiking risk scoring, or automatic go/no-go decision was added.

The output does not infer:

- event causality from route-load, surface, slope, weather, or OSM proximity;
- actual facility use from OSM proximity;
- personal ability from event overlays;
- final risk from event overlays.

IB3D/event annotation remains route-window/profile annotation evidence only.
