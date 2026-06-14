# Changelog Update - IB3W Activity Weather Performance Join

Date: 2026-06-15

## Working directory

- `D:\mountain_work\115_osm`

## Completed commits

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

## Inputs joined

Activity performance:

- `outputs/ib3a_rc_full26_performance_summary_v1/activity_performance_summary.csv`
- `outputs/ib3a_rc_full26_performance_summary_v1/activity_performance_summary_audit.csv`

Weather profile:

- `outputs/ib3w_codis_weather_profile_report_v1/activity_weather_profile_report_table.csv`
- `outputs/ib3w_codis_weather_profile_report_v1/weather_profile_report_summary.csv`

## Activity performance status

- Primary input root: `outputs/ib3a_rc_backend_activity_enriched_v1l_qixing_lengshuikeng_full26`
- `PRIMARY_ROOT_USED`
- 26 activities processed
- 0 missing files
- 0 failed files
- `PASS_ACTIVITY_PERFORMANCE_SUMMARY_ONLY`
- The `- 複製` fallback was not used.
- No weather join or scoring authorization was introduced in the performance summary.

## Weather profile status

- 27 weather profile rows
- 243 observed weather values
- 27 activities x 9 weather variables
- 26 CODiS-only activities
- 1 Direct/Mixed activity
- 14 high-humidity activities
- 2 rain-observed activities
- 25 no-rain-observed activities
- Maximum wind gust: 14.7 m/s

## Added descriptive join

Output root:

- `outputs/ib3w_activity_weather_performance_join_v1/`

Files:

- `activity_weather_performance_join.csv`
- `activity_weather_performance_join_audit.csv`
- `activity_weather_performance_join_report.html`

Result:

- `performance_row_count = 26`
- `weather_row_count = 27`
- `matched_row_count = 26`
- `performance_unmatched_count = 0`
- `weather_unmatched_count = 1`
- `weather_unmatched_activity_ids = qixing_lengshuikeng_xiaoyoukeng_20260410_biji_gpx`
- Join key: performance `activity_id_short` x weather `activity_id_short`
- Weather join performed
- No zero fallback
- `PASS_DESCRIPTIVE_ACTIVITY_WEATHER_PERFORMANCE_JOIN_ONLY`

## Boundary preserved

- This is a descriptive evidence join, not a hiking ability model.
- Ability, THCI, radar, and final hiking risk scoring remain unauthorized.
- HTML content and `descriptive_context_note` are not scores.
- Missing weather is not hard-filled as zero.
- A baseline performance or ability model requires a separate design branch.

## Recommended next work

- `codex/ib3-baseline-hiking-performance-model-planning-v1`

The planning stage should define an explainable and auditable data contract
before scoring. Route and terrain context, activity performance, weather
context, data quality, and individual ability estimate must remain distinct.
Weather descriptive labels must not become direct penalty terms.
