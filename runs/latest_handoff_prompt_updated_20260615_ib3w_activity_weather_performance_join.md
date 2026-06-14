# Latest Handoff Prompt - IB3W Activity Weather Performance Join

Date: 2026-06-15

## Workspace and completed tip

Working directory:

- `D:\mountain_work\115_osm`

Closeout branch:

- `codex/ib3w-activity-weather-performance-join-closeout-v1`

Latest implementation commit:

- `47aa6d1dca865d072a4c590c0bcc42cf96868e71 Add IB3W activity weather performance join`

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

## Upstream status

Activity performance summary:

- Input root: `outputs/ib3a_rc_backend_activity_enriched_v1l_qixing_lengshuikeng_full26`
- Input status: `PRIMARY_ROOT_USED`
- 26 activities processed
- 0 missing files
- 0 failed files
- `PASS_ACTIVITY_PERFORMANCE_SUMMARY_ONLY`
- The `- 複製` fallback was not used.
- No weather join or THCI, radar, or final-risk scoring occurred at this stage.

Weather profile:

- 27 profile rows
- 27 activities and 243 observed weather values
- 9 weather variables per activity
- 26 CODiS-only activities
- 1 Direct/Mixed activity
- 14 high-humidity activities
- 2 rain-observed activities
- 25 no-rain-observed activities
- Maximum wind gust: 14.7 m/s

## Completed join

Output root:

- `outputs/ib3w_activity_weather_performance_join_v1/`

Files:

- `activity_weather_performance_join.csv`
- `activity_weather_performance_join_audit.csv`
- `activity_weather_performance_join_report.html`

Validated audit:

- `performance_row_count = 26`
- `weather_row_count = 27`
- `matched_row_count = 26`
- `performance_unmatched_count = 0`
- `weather_unmatched_count = 1`
- Unmatched weather activity: `qixing_lengshuikeng_xiaoyoukeng_20260410_biji_gpx`
- Join key: performance `activity_id_short` x weather `activity_id_short`
- `weather_join_performed = True`
- All THCI, radar, final hiking risk, and ability scoring authorizations are false.
- `zero_fallback_used = False`
- `PASS_DESCRIPTIVE_ACTIVITY_WEATHER_PERFORMANCE_JOIN_ONLY`

## Non-negotiable boundary

- This is a descriptive activity performance evidence x weather context evidence join.
- It is not a hiking ability model or ability score.
- It does not perform or authorize THCI, radar, or final hiking risk scoring.
- The HTML report and `descriptive_context_note` are not risk scores or ability scores.
- Missing weather must remain missing and must not be hard-filled as zero.
- Any ability or baseline performance model must be designed in a separate branch.

## Recommended continuation

Branch:

- `codex/ib3-baseline-hiking-performance-model-planning-v1`

Do not calculate a score first. Define an auditable baseline hiking performance
model data contract that explicitly separates:

- Route difficulty and terrain context
- Activity performance
- Weather context
- Data quality
- Individual ability estimate

Weather descriptive labels must not be converted directly into score penalties.
