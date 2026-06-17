# README Update — CH6.5 IB3D Route-Window Overlay and v2.2.7 Review-Safe Profiles

## Working Directory

`D:\mountain_work\115_osm`

## Purpose

This update records the CH6.5 display/evidence package that bridges IB3D elapsed-time behavior events into route-window annotations and renders full25 review-safe single-activity surface profiles.

The package is a **visualization and annotation evidence layer** for Chapter 6.5. It helps explain where observed activity events overlap route-distance windows and route/surface context.

It is not a route-load calculation layer and does not replace canonical CH6.5 route-load context evidence.

## Current Recommended Scripts

### IB3D event route-window bridge v1

Script:

`D:\mountain_work\115_osm\scripts\make_ch6_5_ib3d_event_route_window_bridge_v1.py`

Preview script:

`D:\mountain_work\115_osm\scripts\make_ch6_5_ib3d_event_route_window_bridge_preview_png_v1.py`

Output root:

`outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1`

Output inventory from local closeout check:

- CSV files: 51
- PNG files: 4
- MD files: 1

Key outputs:

- `ib3d_event_route_window_bridge_summary.csv`
- `ib3d_event_route_window_bridge_run_report.md`
- `ib3d_event_route_window_bridge_preview_all.png`
- `activity_20_1_ib3d_event_route_window_overlay_preview.png`
- `activity_37_1_ib3d_event_route_window_overlay_preview.png`
- `activity_9_1_ib3d_event_route_window_overlay_preview.png`
- per-activity `*_ib3d_event_mapping_review.csv`
- per-activity `*_ib3d_event_route_window_overlay.csv`

### CH6.5 single-activity surface profile v2.2.7 IB3D review-safe status

Script:

`D:\mountain_work\115_osm\scripts\make_ch6_single_activity_surface_profile_v2_2_7_ib3d_review_safe_status.py`

Output root:

`outputs\report_figures\ch6_single_activity_surface_profiles_v2_2_7_ib3d_review_safe_status`

Output inventory from local closeout check:

- CSV files: 51
- PNG files: 50
- MD files: 51

Key outputs:

- `ch6_5_single_activity_surface_profiles_v2_2_7_ib3d_review_safe_status_master_run_report.md`
- `ib3d_overlay_drawable_diagnosis_full25.csv`
- per-activity profile CSV/PNG/MD/run-report outputs
- per-activity `*_shelter_context_zones.csv`
- top-level copied profile PNGs for report/reference use

## Method Role

The IB3D bridge maps elapsed-time behavior events into route-distance window annotations. The v2.2.7 profile layer then displays those annotations over the single-activity surface profile.

This supports report interpretation such as:

- where event windows overlap route-distance windows;
- which activity windows have drawable IB3D/event overlays;
- which events should remain review-only;
- how route/surface context, shelter/facility proximity context, and event annotations appear together on a report figure.

## Method Boundary

This package is descriptive visualization and annotation evidence only.

It does not:

- compute route-load context index;
- replace CH6.5 route-load context windows v1;
- replace CH6.7 planning context fusion;
- infer event causality from slope, surface, weather, OSM proximity, or route-load context;
- infer actual facility use from OSM facility/shelter proximity;
- generate personal ability score, rank, or class;
- generate THCI score;
- generate radar score;
- generate route suitability score;
- generate final hiking risk score.

IB3D/event annotations are not route-load evidence. They are observed behavior/event overlays bridged into route-window/profile visual context.

Facility and shelter markers remain OSM proximity/context references, not proof of physical facility count or actual user use.

Weather context, when present in the surrounding evidence chain, remains descriptive background unless a safe route-window weather source explicitly supports window-level interpretation.

## Version Decision

This package can be treated as the current recommended CH6.5 IB3D route-window overlay / v2.2.7 review-safe display package.

Earlier v2.2.x surface profile versions remain useful for debugging and visual iteration, but v2.2.7 is the current report-facing review-safe status output for this package.

## Recommended Commit Scope

Include:

- `scripts\make_ch6_5_ib3d_event_route_window_bridge_v1.py`
- `scripts\make_ch6_5_ib3d_event_route_window_bridge_preview_png_v1.py`
- `scripts\make_ch6_single_activity_surface_profile_v2_2_7_ib3d_review_safe_status.py`
- `outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1`
- `outputs\report_figures\ch6_single_activity_surface_profiles_v2_2_7_ib3d_review_safe_status`
- this README / changelog / current index / handoff documentation set

Do not include unrelated CH6.5 older visual prototypes, CH6.7 scripts, CH6.8 scripts, or `_handoff_6_2_method_files` in the same commit.
