# Latest Handoff Prompt - IB3W CODiS Historical Weather Context

Date: 2026-06-15

## Workspace and branch

Workspace:

- `D:\mountain_work\115_osm`

Closeout branch:

- `codex/ib3w-codis-historical-weather-context-closeout-v1`

Implementation tip before closeout:

- `76ea085 Add IB3W CODiS weather profile report`

## Completed chain

- `d82dc54 Add IB3W CODiS historical weather ingest`
- `a9dfaf0 Add IB3W CODiS fallback merge prototype`
- `b4e3d65 Add IB3W CODiS multistation weather ingest`
- `f62aaff Add IB3W CODiS multistation fallback merge`
- `82a04f4 Add IB3W CODiS merged weather distribution profile`
- `76ea085 Add IB3W CODiS weather profile report`

## What is complete

The CODiS historical weather chain now covers 40 raw hourly files under
`weather/codis/`: four stations across ten dates.

Stations:

- `466910` 鞍部
- `C0AC40` 大屯山
- `466930` 竹子湖
- `C0AH40` 平等

The multistation ingest output is:

- `outputs/ib3w_codis_historical_weather_multistation_ingest_v1/`

It normalized all expected observations:

- 40 input files
- 4 stations
- 40 station-date groups
- 960 expected rows
- 960 normalized rows
- 0 zero-fallback rows
- 0 scoring-authorized rows
- `PASS`

The multistation merge output is:

- `outputs/ib3w_codis_multistation_fallback_merge_v1/`

It produced:

- 351 input evidence rows
- 345 originally unavailable rows
- 237 CODiS historical observed merges
- 108 remaining unavailable rows
- 6 original direct observations preserved
- 0 original direct observations modified
- 0 zero-fallback rows
- 0 THCI, radar, final-risk, or production-scoring authorizations
- `PASS`

`pressure_hpa` was recovered from raw CODiS `StnPres`. It is station pressure,
not sea-level pressure.

The following variables remain unavailable and must remain missing:

- `precipitation_10min_mm`
- `precipitation_1hr_mm`
- `visibility_m`
- `weather`

## Profile artifacts

Distribution output:

- `outputs/ib3w_codis_merged_context_weather_distribution_v1/`

Summary:

- 27 activities
- 243 observed rows
- 27 activities x 9 observed weather variables
- 237 `OBSERVED_HISTORICAL_CODIS`
- 6 `SAME_DAY_DIRECT_OBSERVATION`
- scoring authorization remains false

HTML report output:

- `outputs/ib3w_codis_weather_profile_report_v1/`

Files:

- `ib3w_codis_weather_profile_report.html`
- `activity_weather_profile_report_table.csv`
- `weather_profile_report_summary.csv`

Report summary:

- 27 activities
- 243 observed weather values
- 26 CODiS-only activities
- 1 Direct/Mixed activity
- 14 high-humidity activities
- 2 rain-observed activities
- 25 no-rain-observed activities
- maximum wind gust = 14.7 m/s

## Non-negotiable boundary

- This is IB3W weather evidence/profile layer only.
- Do not treat descriptive HTML tags as risk scores.
- Do not authorize THCI, radar, or final hiking risk scoring from these artifacts.
- Do not hard-fill missing weather as zero.
- Do not reinterpret CODiS `StnPres` as sea-level pressure.
- Any scoring consumer must first pass the weather gate/validator.

## Recommended continuation

First:

- `codex/ib3a-rc-full26-performance-summary-v1`

Then:

- `codex/ib3w-activity-weather-performance-join-v1`
