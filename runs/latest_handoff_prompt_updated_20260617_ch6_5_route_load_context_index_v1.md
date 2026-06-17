# Latest Handoff Prompt — CH6.5 Route-Load Context Index v1

Continue from:

- repo: `D:\mountain_work\115_osm`
- branch: verify with `git branch --show-current`
- package: CH6.5 route-load context index v1

## Completed in This Handoff

Verified script:

- `scripts\make_ch6_5_route_load_context_index_v1.py`

Verified output root:

- `outputs\report_figures\ch6_5_route_load_context_index_v1`

Verified outputs:

| file | size bytes |
|---|---:|
| `route_load_behavior_response_candidate_windows_v1.csv` | 1121985 |
| `route_load_context_activity_summary_v1.csv` | 9330 |
| `route_load_context_index_run_report_v1.md` | 2350 |
| `route_load_context_windows_v1.csv` | 1885498 |

## Method Role

This package builds descriptive route-load context evidence from existing 50 m route-load / behavior-response windows.

The route-load context index uses route, terrain, and map-derived factors only. Behavior response and weather context are descriptive overlays and are not used to compute the index.

Candidate windows indicate high/very-high route-load context plus observed behavior response signals. They are review candidates only.

## Do Not Change

Do not overwrite:

- `outputs\report_figures\ch6_5_route_load_context_index_v1`

unless intentionally creating a newer version.

Do not modify Word/docx files in this handoff.

Do not rerun upstream IB0/IB1/IB2/IB3 stages unless a future change explicitly requires it.

## Boundary

Do not generate or infer:

- ability score;
- ability rank;
- ability class;
- THCI score;
- radar score;
- final hiking risk score;
- route suitability score;
- automatic suitable/unsuitable decision;
- automatic go/no-go decision;
- weather causality.

Weather context is descriptive only. Missing weather is not zero-filled.

Behavior response does not feed back into route-load context calculation.

## Suggested Commit Scope

Include:

- `scripts\make_ch6_5_route_load_context_index_v1.py`
- `outputs\report_figures\ch6_5_route_load_context_index_v1`
- current README / changelog / CURRENT_INDEX / handoff documentation for this package

Do not include:

- `scripts\make_ch6_5_route_surface_event_behavior_profile_with_ib3d_events_v1_5.py`
- `scripts\make_ch6_5_route_surface_event_behavior_profile_with_ib3d_events_v1_5_1.py`
- CH6.7 scripts / outputs
- CH6.8 scripts / outputs
- CH6 report figure scripts
- older single-activity profile prototypes
- `_handoff_6_2_method_files`

## Suggested Commit Message

`Add CH6.5 route-load context index evidence`
