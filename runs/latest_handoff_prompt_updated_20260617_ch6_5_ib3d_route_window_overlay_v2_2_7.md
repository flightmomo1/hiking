# Latest Handoff Prompt — CH6.5 IB3D Route-Window Overlay and v2.2.7 Review-Safe Profiles

Continue from:

- repo: `D:\mountain_work\115_osm`
- branch: verify with `git branch --show-current`
- package: CH6.5 IB3D route-window overlay / v2.2.7 review-safe profile outputs

## Completed in This Handoff

### 1. IB3D event route-window bridge v1

Scripts:

- `scripts\make_ch6_5_ib3d_event_route_window_bridge_v1.py`
- `scripts\make_ch6_5_ib3d_event_route_window_bridge_preview_png_v1.py`

Output root:

`outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1`

Closeout inventory:

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

### 2. CH6.5 single-activity surface profile v2.2.7 IB3D review-safe status

Script:

`scripts\make_ch6_single_activity_surface_profile_v2_2_7_ib3d_review_safe_status.py`

Output root:

`outputs\report_figures\ch6_single_activity_surface_profiles_v2_2_7_ib3d_review_safe_status`

Closeout inventory:

- CSV files: 51
- PNG files: 50
- MD files: 51

Key outputs:

- `ch6_5_single_activity_surface_profiles_v2_2_7_ib3d_review_safe_status_master_run_report.md`
- `ib3d_overlay_drawable_diagnosis_full25.csv`
- per-activity profile CSV / PNG / MD / run-report outputs
- per-activity shelter context zone CSVs
- top-level copied profile PNGs

## Interpretation

This package bridges IB3D elapsed-time event intervals into route-window/profile visualization.

Use this package to explain:

- event-to-route-window overlay availability;
- event mapping review status;
- drawable overlay coverage;
- single-activity surface/profile visual context;
- shelter/facility context zones as OSM proximity references.

## Do Not Change

Do not overwrite or modify these outputs unless intentionally creating a new version:

- `outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1`
- `outputs\report_figures\ch6_single_activity_surface_profiles_v2_2_7_ib3d_review_safe_status`

Do not modify Word/docx files in this handoff.

Do not rerun large upstream pipeline stages unless a future change explicitly requires it.

## Boundary

Do not generate or infer:

- personal ability score;
- personal ability rank;
- personal ability class;
- route suitability score;
- THCI score;
- radar score;
- final hiking risk score;
- automatic go/no-go decision;
- causality from weather, route-load, slope, surface, OSM proximity, or IB3D event overlays;
- actual facility use from OSM proximity.

IB3D/event annotation is route-window/profile annotation evidence only. It is not route-load evidence and not causality evidence.

## Suggested Local Verification

```powershell
Set-Location D:\mountain_work\115_osm

Get-ChildItem outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1 -File |
  Group-Object Extension |
  Select-Object Name, Count |
  Format-Table -AutoSize

Get-ChildItem outputs\report_figures\ch6_single_activity_surface_profiles_v2_2_7_ib3d_review_safe_status -Recurse -File |
  Group-Object Extension |
  Select-Object Name, Count |
  Format-Table -AutoSize

Get-ChildItem outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1 |
  Where-Object { $_.Name -match "summary|audit|diagnosis|run_report|preview" } |
  Select-Object Name, Length |
  Format-Table -AutoSize

Get-ChildItem outputs\report_figures\ch6_single_activity_surface_profiles_v2_2_7_ib3d_review_safe_status |
  Where-Object { $_.Name -match "summary|audit|diagnosis|run_report|master" } |
  Select-Object Name, Length |
  Format-Table -AutoSize
```

Expected verification:

- bridge output root: 51 CSV, 4 PNG, 1 MD
- v2.2.7 output root: 51 CSV, 50 PNG, 51 MD
- bridge summary / run report / preview files present
- v2.2.7 master run report and drawable diagnosis present

## Suggested Commit Scope

Include:

- `scripts\make_ch6_5_ib3d_event_route_window_bridge_v1.py`
- `scripts\make_ch6_5_ib3d_event_route_window_bridge_preview_png_v1.py`
- `scripts\make_ch6_single_activity_surface_profile_v2_2_7_ib3d_review_safe_status.py`
- `outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1`
- `outputs\report_figures\ch6_single_activity_surface_profiles_v2_2_7_ib3d_review_safe_status`
- current README / changelog / handoff / CURRENT_INDEX documentation for this package

Do not include:

- older CH6.5 surface-profile prototypes;
- CH6.7 scripts;
- CH6.8 scripts;
- `_handoff_6_2_method_files`.

## Suggested Commit Message

`Add CH6.5 IB3D route-window overlay and v2.2.7 profiles`
