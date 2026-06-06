# IB3 Script Registry v1

Date: 2026-06-06

## 1. Registry Purpose

This registry defines the lifecycle, role, and intended use of scripts under
`scripts/ib3_activity_environment/`.

Its goals are:

- keep formal pipeline entrypoints distinct from review and research tools;
- prevent backup, prototype, and experimental scripts from becoming implicit dependencies;
- document replacement and archive decisions before files are moved or removed;
- require explicit input/output contracts for future IB3 scripts;
- keep review evidence separate from point-level truth and feature facts.

Current IB3 responsibility boundaries:

- IB3A = geometry projection and sequence map-match;
- IB3A2 = point-level reliability and `usable_on_route` truth;
- IB3B / IB3B2 = activity visual QA;
- IB3F = activity-level feature facts;
- IB3G = local movement review evidence, currently experimental;
- IB3H = downstream activity usability gate, currently deferred;
- IB3R = route-choice and repaired-baseline review tools.

## 2. Lifecycle Status Definitions

| Status | Definition |
|---|---|
| `formal` | Current supported pipeline entrypoint with an explicit input/output contract and validated outputs. |
| `review` | Read-only audit or visual QA tool. It may produce review evidence but must not silently alter formal upstream truth. |
| `experimental` | Research implementation whose rules or thresholds are not converged. It must not be a default formal dependency. |
| `prototype` | Early or route-specific implementation retained for exploration. It may have incomplete CLI/root contracts. |
| `deprecated` | Superseded implementation that should not be used for current results. |
| `archive-candidate` | Historical snapshot, backup, or replaced script that should eventually move to an archive location after review. |

## 3. Current Formal / Review Entrypoints

| Script | Layer | Status | Role | CLI | Known inputs | Known outputs | Notes |
|---|---|---|---|---|---|---|---|
| `ib3a_sequence_mapmatch_standardized_activity_folder_cli.py` | IB3A | formal | Sequence-aware activity map-match | Yes | standardized activity manifest/root, route profile, optional prior map-match | sequence map-matched activity root | Current v1.3b route-profile override and `--case-id` capable entrypoint. |
| `ib3a2_filter_mapmatched_activity_on_route.py` | IB3A2 | formal | Point-level reliability, `usable_on_route`, exclusions, excursions | Yes | sequence/map-matched activity root | labeled, on-route, excursions CSVs | `usable_on_route` remains point reliability truth. |
| `ib3f_extract_activity_route_features_v1_3b.py` | IB3F | formal | Activity-level feature extraction | Yes | IB3A, IB3A2, IB1E context, IB2 risk, optional THCI | per-activity feature CSV/JSON and batch summaries | Feature facts only; does not force route choice. |
| `ib3b2_plot_activity_profile_1d_2d.py` | IB3B2 | review | Integrated 1D/2D activity visual QA | Yes | IB3A, IB3A2, route profile/context, optional corridor config | PNG, HTML, plot CSV, summary | Supports current/custom roots and corridor overlay. |
| `plot_ib3f_activity_story_map_v1_3b.py` | IB3F visual | review | Per-activity story map and lightweight batch index | Yes | IB3F, IB3A2, route profile/risk, corridor config | one HTML per activity and batch index | Review/formal candidate committed as `c959ce9`; not route-choice classification. |
| `plot_ib3f_qixing_repaired_review_feature_summary_v1_3b.py` | IB3F visual | review | Qixing IB3F feature summary HTML | No | qixing repaired IB3F root | feature review HTML | Route-specific review helper. |
| `ib3a_plot_mapmatched_activity_debug_map_cli.py` | IB3A visual | review | Map-match debug visualization | Yes | map-matched activity and route profile | debug maps | Retain as a debug tool; defaults still reference legacy roots. |
| `ib3a0_screen_activity_against_mainline.py` | IB3A0 | review | Fast activity-vs-mainline screening | Yes | activity CSV and IB0D mainline | screening outputs | Pre-map-match review utility, not a formal downstream dependency. |

## 4. Qixing Route-Choice Review Scripts

All scripts in this section are review-only. Qixing automatic route-choice
classification remains unreliable and must not be forced into a canonical label.

| Script | Status | Role | CLI | Known inputs | Known outputs | Notes |
|---|---|---|---|---|---|---|
| `ib3_route_choice_inference_qixing_v1_3b.py` | review | Point-proximity route-choice inference | No | repaired sequence, IB3A2, route profile | v1 route-choice review root | Low-confidence method retained as evidence. |
| `ib3_route_choice_inference_qixing_geometry_v2_v1_3b.py` | review | Corridor geometry route-choice inference | No | repaired sequence, IB3A2, route profile, corridor config | v2 geometry review root | Produces review-required results, not formal labels. |
| `plot_qixing_branch_corridor_definition_qa_v1_3b.py` | review | Corridor definition visual QA | No | route profile/semantics and corridor config | corridor QA HTML/PNG/summary | Used to review manually defined corridor ranges. |
| `plot_qixing_raw_gps_vs_projected_route_choice_qa_v1_3b.py` | review | Raw GPS vs projected route-choice QA | No | standardized activity, repaired IB3A/IB3A2, route profile, corridor config | raw/projected QA root | Confirms projection is not silently forcing a canonical path. |
| `audit_qixing_route_choice_inference_conclusion_v1_3b.ps1` | review | Consolidated route-choice conclusion audit | No | v1/v2/raw GPS/corridor evidence | conclusion audit root | Final status keeps manual review required. |
| `audit_ib3a2_qixing_repaired_threshold_sensitivity_v1_3b.py` | review | Review-only threshold sensitivity | No | repaired sequence, IB3A2, route profile | threshold sensitivity root | Does not modify formal IB3A2 thresholds. |
| `audit_ib3a2_qixing_wrong_branch_evidence_v1_3b.py` | review | Local wrong-branch evidence audit | No | repaired sequence, IB3A2, route profile | wrong-branch evidence root | Supports review flags, not formal wrong-branch truth. |
| `audit_ib3f_qixing_37_1_descent_wrong_branch_candidate_v1_3b.py` | review | Diagnose possible false on-route segment | No | repaired sequence/IB3A2, IB3F, route profile/risk | IB3F diagnostic root | Route-specific local movement evidence. |

## 5. Older IB3A / IB3B Tools

| Script | Status | Role | CLI | Notes / Recommendation |
|---|---|---|---|---|
| `ib3a_mapmatch_standardized_activity_folder_cli.py` | deprecated | Older non-sequence folder map-match | Yes | Superseded by sequence map-match for current work. |
| `ib3a_mapmatch_highfreq_activity.py` | prototype | High-frequency activity map-match | Yes | Retain only for historical/prototype use. |
| `ib3a_mapmatch_highfreq_activity_backup_20260524.py` | archive-candidate | Backup of high-frequency map-match | No | Timestamped backup; should not remain a current entrypoint. |
| `ib3a_sequence_mapmatch_standardized_activity_folder_cli_before_batch_20260529_175527.py` | archive-candidate | Pre-batch sequence map-match snapshot | Yes | Replaced by the current sequence script. |
| `ib3_batch_run_juansi_activities.py` | prototype | Juansi activity batch wrapper | Yes | Route-specific wrapper; not current formal batch orchestration. |
| `ib3b_plot_mapmatched_activity_profile.py` | deprecated | Older activity profile plot | Yes | Superseded by IB3B2 1D/2D visual QA. |
| `ib3b_build_segment_activity_environment_features_cli.py` | prototype | Segment activity/environment feature builder | Yes | Uses older v1.1 context/risk defaults; not current IB3F. |
| `ib3b_extract_environment_window.py` | prototype | Environment window extraction | No | No current formal contract. |
| `ib3b2_plot_activity_profile_1d_2d_with_events_v1.py` | prototype | IB3B2 board with IB3C event overlays | Yes | Depends on legacy event roots; hold until IB3C is redesigned. |
| `ib3a_find_nearby_environment_stations.py` | experimental | Nearby environment station search | No | Weather/environment research utility. |
| `ib3a_find_nearby_weather_stations.py` | experimental | Nearby weather station search | No | Weather/environment research utility. |
| `ib3b0_inspect_weather_database_schema.py` | experimental | Weather database schema inspection | No | Research utility, not activity pipeline. |
| `ib3b2_analyze_weather_station_update_frequency.py` | experimental | Weather station update analysis | No | Research utility. |
| `ib3b3_estimate_station_elevation_from_nslc_contours.py` | experimental | Estimate station elevation | No | Research utility. |
| `ib3b4_fuse_route_weather_conditions.py` | experimental | Route/weather condition fusion | No | Research utility. |

## 6. Legacy IB3C / IB3D Behavior Branch

These scripts predate the current v1.3b/IB3F contract or depend on forced-route
v4b roots. They must not be described as current formal IB3 behavior outputs.

| Script | Status | Role | CLI | Notes / Recommendation |
|---|---|---|---|---|
| `ib3c_detect_activity_behavior_events.py` | prototype | Fixed-threshold behavior event detection | Yes | Legacy forced-route defaults. |
| `ib3c_detect_activity_behavior_events_adaptive_speed_v1.py` | prototype | Adaptive-speed event detection | Yes | Legacy branch. |
| `ib3c_detect_activity_behavior_events_adaptive_speed_v1_phase3_semantics.py` | archive-candidate | Semantics phase variant | Yes | Iterative experiment naming; archive after review. |
| `ib3c_detect_activity_behavior_events_adaptive_speed_v1_phase3b_hr_delta.py` | archive-candidate | HR-delta phase variant | Yes | Iterative experiment naming; archive after review. |
| `ib3c_detect_activity_behavior_events_adaptive_speed_v1_phase3c_recovery_interpretation.py` | archive-candidate | Recovery interpretation variant | Yes | Iterative experiment naming; archive after review. |
| `ib3c_apply_environment_risk_adjustment.py` | experimental | Environment-adjusted behavior risk | No | No current formal contract. |
| `ib3c_overlay_activity_with_route_risk.py` | prototype | Activity/risk overlay | No | Retain as review prototype. |
| `ib3c_plot_gpx_station_map.py` | experimental | GPX and station map | No | Weather/station research. |
| `ib3c2_compare_weather_trend_adjustment.py` | experimental | Weather trend comparison | No | Research branch. |
| `ib3d_plot_observed_behavior_timeline_v1.py` | prototype | Observed behavior timeline | Yes | Depends on legacy IB3C and forced-route roots. |
| `ib3d_plot_activity_risk_timeline.py` | deprecated | Older activity risk timeline | No | Superseded by later timeline experiments. |
| `ib3d_plot_environment_adjusted_risk_profile.py` | experimental | Environment-adjusted risk profile | No | Research branch. |
| `ib3d_v2_plot_activity_risk_timeline_report.py` | experimental | Risk timeline report v2 | No | No current formal contract. |

## 7. Weather / Microclimate Branch

| Script | Status | Role | CLI | Notes / Recommendation |
|---|---|---|---|---|
| `ib3e_extract_route_microclimate_terrain_features.py` | experimental | Microclimate/terrain feature extraction | No | Not part of the current formal IB3 feature contract. |
| `ib3f_apply_weather_terrain_microclimate_interaction.py` | experimental | Weather/terrain/microclimate interaction | No | Name conflicts with current formal IB3F meaning; rename before future reuse. |
| `ib3x_inspect_weather_sqlite.py` | experimental | Weather SQLite inspection | No | General research utility. |

## 8. Naming Rules

Formal implementation:

```text
ib3<layer>_<verb>_<object>_v<version>.py
```

Examples:

```text
ib3a_sequence_mapmatch_activity_v1_3b.py
ib3a2_filter_on_route_points_v1_3b.py
ib3f_extract_activity_route_features_v1_3b.py
```

Review and visual QA:

```text
audit_ib3<layer>_<scope>_<version>.py
plot_ib3<layer>_<scope>_qa_<version>.py
```

Avoid new current-entrypoint names containing:

```text
backup_<date>
before_batch_<date>
phase3b
phase3c
updated_final
```

Such names indicate an experiment or historical snapshot and should use an
experimental or archive location.

## 9. Experimental Storage Rules

Proposed future location:

```text
scripts/ib3_activity_environment/experimental/
```

Rules:

1. Experimental scripts must not be default dependencies of the formal pipeline.
2. Output roots must contain `experimental`, `review`, or another explicit non-formal marker.
3. The script must state its hypothesis, owner layer, and known limitations.
4. It must not overwrite formal roots or change upstream truth fields.
5. Threshold experiments require comparison evidence before promotion.
6. Experimental outputs may inform review notes but cannot silently drive formal gates.

No scripts are moved by this registry draft.

## 10. Deprecated and Archive Rules

Proposed future location:

```text
scripts/ib3_activity_environment/archive/
```

Before moving a deprecated script, record:

- archived script path;
- replacement script;
- reason for deprecation;
- last known output root;
- whether the script is safe to rerun;
- `do_not_run` status where appropriate.

Deprecated scripts should not appear as runnable current pipeline entrypoints.
Files should not be deleted solely because they are deprecated.

## 11. New Script Commit Criteria

A new IB3 script should be committed only when:

1. Its layer and lifecycle status are explicit.
2. Its function is not already covered by an existing maintained script.
3. It has a documented input and output contract.
4. Formal/review scripts support custom input and output roots where applicable.
5. It does not overwrite upstream or formal roots.
6. `py_compile` or the relevant syntax validation passes.
7. At least two or three representative smoke cases pass.
8. An audit, comparison, or explicit human QA result exists.
9. Review and experimental evidence are not presented as formal truth.
10. The registry and current pipeline documentation identify the entrypoint or hold status.

## 12. Current Hold Notes

- `plot_ib3f_activity_story_map_v1_3b.py`
  - lifecycle: `review`;
  - formal candidate for IB3F visual output;
  - committed as `c959ce9 Enhance IB3F story map batch output`;
  - produces one story map per activity and a lightweight batch index.

- `ib3g_detect_local_movement_review_flags_v1.py`
  - lifecycle: `experimental`;
  - working-tree state at registry drafting: untracked;
  - status: HOLD / not commit-ready;
  - not part of the formal pipeline;
  - must not modify IB3A2 `usable_on_route`;
  - v1b reduces some wrong-branch window sensitivity but remains over-sensitive across the current three qixing activities.

- IB3H activity quality gate
  - implementation deferred until this registry is reviewed;
  - future responsibility: downstream activity usability decision;
  - must consume IB3F facts without redefining IB3A2 point truth;
  - experimental IB3G evidence must remain optional and must not be a default formal gate input.
