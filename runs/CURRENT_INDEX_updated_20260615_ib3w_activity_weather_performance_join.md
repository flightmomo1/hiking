# CURRENT INDEX - IB3W Activity Weather Performance Join

Date: 2026-06-15

## Working directory

- `D:\mountain_work\115_osm`

## Current branch

- `codex/ib3w-activity-weather-performance-join-closeout-v1`

## Scope

This closeout records the completed descriptive join between IB3A-RC activity
performance evidence and IB3W weather context evidence. It does not define or
authorize an ability model, THCI scoring, radar scoring, or final hiking risk
scoring.

## Completed commit chain

- `dfb066aa8c64d5bda6db9118cbff037668fad23a Document IB3W CODiS historical weather context closeout`
- `b87fea2a224170259975183b7db7ce23bb5480f6 Add IB3A-RC full26 activity performance summary`
- `47aa6d1dca865d072a4c590c0bcc42cf96868e71 Add IB3W activity weather performance join`

Earlier weather chain:

- `d82dc54 Add IB3W CODiS historical weather ingest`
- `a9dfaf0 Add IB3W CODiS fallback merge prototype`
- `b4e3d65 Add IB3W CODiS multistation weather ingest`
- `f62aaff Add IB3W CODiS multistation fallback merge`
- `82a04f4 Add IB3W CODiS merged weather distribution profile`
- `76ea085 Add IB3W CODiS weather profile report`

## Completed inputs

Activity performance:

- `outputs/ib3a_rc_full26_performance_summary_v1/activity_performance_summary.csv`
- `outputs/ib3a_rc_full26_performance_summary_v1/activity_performance_summary_audit.csv`

Weather profile:

- `outputs/ib3w_codis_weather_profile_report_v1/activity_weather_profile_report_table.csv`
- `outputs/ib3w_codis_weather_profile_report_v1/weather_profile_report_summary.csv`

## Activity performance summary status

- Input root: `outputs/ib3a_rc_backend_activity_enriched_v1l_qixing_lengshuikeng_full26`
- Input status: `PRIMARY_ROOT_USED`
- Activities processed: 26
- Missing files: 0
- Failed files: 0
- Audit: `PASS_ACTIVITY_PERFORMANCE_SUMMARY_ONLY`
- The `- 複製` fallback was not used.
- Weather join was not performed in the performance summary stage.
- THCI, radar, and final-risk scoring were not authorized.

## Weather profile status

- Weather profile rows: 27
- `activity_count = 27`
- `observed_weather_value_count = 243`
- 27 activities x 9 weather variables
- CODiS-only `activity_count = 26`
- Direct/Mixed `activity_count = 1`
- `high_humidity_activity_count = 14`
- `rain_observed_activity_count = 2`
- `no_rain_observed_activity_count = 25`
- `max_wind_gust_ms = 14.7`

## Join result

Output root:

- `outputs/ib3w_activity_weather_performance_join_v1/`

Files:

- `activity_weather_performance_join.csv`
- `activity_weather_performance_join_audit.csv`
- `activity_weather_performance_join_report.html`

Audit:

- `performance_row_count = 26`
- `weather_row_count = 27`
- `matched_row_count = 26`
- `performance_unmatched_count = 0`
- `weather_unmatched_count = 1`
- `weather_unmatched_activity_ids = qixing_lengshuikeng_xiaoyoukeng_20260410_biji_gpx`
- Join key: performance `activity_id_short` x weather `activity_id_short`
- `weather_join_performed = True`
- `thci_scoring_authorized = False`
- `radar_scoring_authorized = False`
- `final_hiking_risk_scoring_authorized = False`
- `ability_scoring_authorized = False`
- `zero_fallback_used = False`
- `audit_conclusion = PASS_DESCRIPTIVE_ACTIVITY_WEATHER_PERFORMANCE_JOIN_ONLY`

## Engineering boundary

- This stage is a descriptive join of activity performance evidence and weather context evidence.
- It is not a hiking ability model.
- It is not ability scoring.
- It is not THCI scoring.
- It is not radar scoring.
- It is not final hiking risk scoring.
- The HTML report and `descriptive_context_note` are descriptive evidence only and must not be treated as risk scores or ability scores.
- Missing weather must not be hard-filled as zero.
- Any downstream ability or baseline performance model requires a separate model-design branch.

## Recommended next step

- `codex/ib3-baseline-hiking-performance-model-planning-v1`

The next stage should define the baseline hiking performance model data
contract before calculating any score. It must distinguish route difficulty
and terrain context, activity performance, weather context, data quality, and
individual ability estimate. Weather descriptive labels must not be used
directly as penalty terms.
