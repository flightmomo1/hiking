# README Update - IB3W Activity Weather Performance Join

Date: 2026-06-15

## Working directory

- `D:\mountain_work\115_osm`

## Pipeline status

The current evidence pipeline is complete through IB3A-RC full26 activity
performance summarization, IB3W CODiS weather profiling, and a descriptive
activity-weather join.

Recent commits:

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

## Input contracts

Activity performance:

- `outputs/ib3a_rc_full26_performance_summary_v1/activity_performance_summary.csv`
- `outputs/ib3a_rc_full26_performance_summary_v1/activity_performance_summary_audit.csv`

Weather profile:

- `outputs/ib3w_codis_weather_profile_report_v1/activity_weather_profile_report_table.csv`
- `outputs/ib3w_codis_weather_profile_report_v1/weather_profile_report_summary.csv`

## Activity performance contract

- Input root: `outputs/ib3a_rc_backend_activity_enriched_v1l_qixing_lengshuikeng_full26`
- Input status: `PRIMARY_ROOT_USED`
- Activities processed: 26
- Missing files: 0
- Failed files: 0
- Audit: `PASS_ACTIVITY_PERFORMANCE_SUMMARY_ONLY`
- The `- 複製` fallback was not used.
- Weather was not joined in this stage.
- THCI, radar, and final-risk scoring were not authorized.

## Weather profile contract

- `weather profile rows = 27`
- `activity_count = 27`
- `observed_weather_value_count = 243`
- 9 weather variables per activity
- CODiS-only `activity_count = 26`
- Direct/Mixed `activity_count = 1`
- `high_humidity_activity_count = 14`
- `rain_observed_activity_count = 2`
- `no_rain_observed_activity_count = 25`
- `max_wind_gust_ms = 14.7`

## Descriptive join contract

Output root:

- `outputs/ib3w_activity_weather_performance_join_v1/`

Files:

- `activity_weather_performance_join.csv`
- `activity_weather_performance_join_audit.csv`
- `activity_weather_performance_join_report.html`

Join:

- Performance key: `activity_id_short`
- Weather key: `activity_id_short`
- `performance_row_count = 26`
- `weather_row_count = 27`
- `matched_row_count = 26`
- `performance_unmatched_count = 0`
- `weather_unmatched_count = 1`
- Unmatched weather activity: `qixing_lengshuikeng_xiaoyoukeng_20260410_biji_gpx`
- `weather_join_performed = True`
- `zero_fallback_used = False`
- `audit_conclusion = PASS_DESCRIPTIVE_ACTIVITY_WEATHER_PERFORMANCE_JOIN_ONLY`

Authorization:

- `thci_scoring_authorized = False`
- `radar_scoring_authorized = False`
- `final_hiking_risk_scoring_authorized = False`
- `ability_scoring_authorized = False`

## Engineering boundary

- This stage joins activity performance evidence and weather context evidence for descriptive review only.
- It is not a hiking ability model or ability score.
- It is not THCI, radar, or final hiking risk scoring.
- The HTML report and `descriptive_context_note` must not be interpreted as risk scores or ability scores.
- Missing weather must remain missing and must not be hard-filled as zero.
- Downstream ability or baseline performance modeling requires a separate model-design branch.

## Recommended next work

- `codex/ib3-baseline-hiking-performance-model-planning-v1`

The next branch should define a baseline hiking performance model data contract
without calculating scores. The design must separate route difficulty and
terrain context, activity performance, weather context, data quality, and
individual ability estimate. Descriptive weather labels must not be used
directly as deductions.
