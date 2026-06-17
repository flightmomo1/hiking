# Current Index — CH6.5 IB3D Route-Window Overlay and v2.2.7 Review-Safe Profiles

## Working Directory

`D:\mountain_work\115_osm`

## Branch

Verify with:

`git branch --show-current`

Recent related branch context:

`codex/ib3-route-load-behavior-story-report-v1`

## Current Recommended Package

### CH6.5 IB3D event route-window bridge v1

Script:

`D:\mountain_work\115_osm\scripts\make_ch6_5_ib3d_event_route_window_bridge_v1.py`

Preview script:

`D:\mountain_work\115_osm\scripts\make_ch6_5_ib3d_event_route_window_bridge_preview_png_v1.py`

Output root:

`outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1`

Effective outputs:

- `ib3d_event_route_window_bridge_summary.csv`
- `ib3d_event_route_window_bridge_run_report.md`
- `ib3d_event_route_window_bridge_preview_all.png`
- per-activity event mapping review CSVs
- per-activity route-window overlay CSVs
- selected preview PNGs

Closeout inventory:

- CSV: 51
- PNG: 4
- MD: 1

### CH6.5 single-activity surface profile v2.2.7 IB3D review-safe status

Script:

`D:\mountain_work\115_osm\scripts\make_ch6_single_activity_surface_profile_v2_2_7_ib3d_review_safe_status.py`

Output root:

`outputs\report_figures\ch6_single_activity_surface_profiles_v2_2_7_ib3d_review_safe_status`

Effective outputs:

- `ch6_5_single_activity_surface_profiles_v2_2_7_ib3d_review_safe_status_master_run_report.md`
- `ib3d_overlay_drawable_diagnosis_full25.csv`
- per-activity profile CSVs
- per-activity profile PNGs
- per-activity Markdown summaries
- per-activity run reports
- per-activity shelter context zone CSVs
- top-level copied PNGs

Closeout inventory:

- CSV: 51
- PNG: 50
- MD: 51

## Source / Method Relationship

This package sits downstream of the Chapter 6.5 activity behavior / route-load / route-window evidence chain.

The IB3D bridge converts elapsed-time behavior event intervals into route-window overlay annotations. The v2.2.7 profile layer renders those annotations on review-safe single-activity surface profiles.

The package is useful for report figures, QA, and human review.

## Interpretation Boundary

This package does not authorize:

- personal ability score;
- personal ability rank;
- personal ability class;
- route suitability score;
- THCI score;
- radar score;
- final hiking risk score;
- automatic suitable/unsuitable decision;
- causal claims from weather, route-load, slope, surface, OSM proximity, or IB3D events;
- actual facility-use claims from OSM proximity.

IB3D/event annotations are display overlays. They are not route-load evidence, not causal evidence, and not score inputs.

Facility/shelter references are route-axis proximity/context references. They are not proof of physical facility count or actual use.

## Current Recommendation

Treat this as the current recommended CH6.5 IB3D route-window overlay / v2.2.7 review-safe display package.

Do not replace the canonical CH6.5 route-load context index with this package. Use it as a report-facing visual QA and annotation layer.

## Commit Recommendation

Suggested commit message:

`Add CH6.5 IB3D route-window overlay and v2.2.7 profiles`

Stage only this package and its documentation. Do not mix with older CH6.5 prototypes, CH6.7/CH6.8 scripts, or `_handoff_6_2_method_files`.
