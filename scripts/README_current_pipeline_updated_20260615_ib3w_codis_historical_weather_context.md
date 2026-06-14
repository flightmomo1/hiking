# README Update - IB3W CODiS Historical Weather Context

Date: 2026-06-15

## Workspace

- `D:\mountain_work\115_osm`

## Pipeline status

The IB3W CODiS historical weather context chain is complete through normalized
multistation ingest, fallback merge, activity-level distribution profiling, and
HTML reporting.

Implementation commits:

- `d82dc54 Add IB3W CODiS historical weather ingest`
- `a9dfaf0 Add IB3W CODiS fallback merge prototype`
- `b4e3d65 Add IB3W CODiS multistation weather ingest`
- `f62aaff Add IB3W CODiS multistation fallback merge`
- `82a04f4 Add IB3W CODiS merged weather distribution profile`
- `76ea085 Add IB3W CODiS weather profile report`

## Data flow

Raw CODiS CSV:

- `weather/codis/`
- 4 stations x 10 dates = 40 files

Stations:

- `466910` 鞍部
- `C0AC40` 大屯山
- `466930` 竹子湖
- `C0AH40` 平等

Multistation normalized observations:

- `outputs/ib3w_codis_historical_weather_multistation_ingest_v1/`

Merged fallback context:

- `outputs/ib3w_codis_multistation_fallback_merge_v1/`

Weather distribution profile:

- `outputs/ib3w_codis_merged_context_weather_distribution_v1/`

HTML profile report:

- `outputs/ib3w_codis_weather_profile_report_v1/`

## Ingest contract

The multistation ingest processed:

- 40 input files
- 4 stations
- 40 station-date groups
- 960 expected hourly rows
- 960 normalized hourly rows

Quality and authorization:

- `zero_fallback_true_count = 0`
- `scoring_authorized_count = 0`
- `production_scoring_authorized_count = 0`
- `ingest_conclusion = PASS`

## Merge contract

The multistation fallback merge processed:

- 351 evidence rows
- 345 originally unavailable rows
- 237 CODiS historical observed replacements
- 108 remaining unavailable rows
- 6 original direct rows preserved
- 0 original direct rows modified

`pressure_hpa` is recovered from raw CODiS `StnPres`. This is station pressure
evidence and must not be labeled as sea-level pressure.

The following unsupported variables remain missing:

- `precipitation_10min_mm`
- `precipitation_1hr_mm`
- `visibility_m`
- `weather`

Merge quality and authorization:

- `zero_fallback_true_count = 0`
- `thci_scoring_authorized_count = 0`
- `radar_scoring_authorized_count = 0`
- `final_hiking_risk_scoring_authorized_count = 0`
- `production_scoring_authorized_count = 0`
- `merge_conclusion = PASS`

## Profile contract

Distribution profile:

- `activity_count = 27`
- `observed_row_count = 243`
- 9 observed weather variables for each activity
- `OBSERVED_HISTORICAL_CODIS = 237`
- `SAME_DAY_DIRECT_OBSERVATION = 6`
- `scoring_authorized = False`

HTML report files:

- `ib3w_codis_weather_profile_report.html`
- `activity_weather_profile_report_table.csv`
- `weather_profile_report_summary.csv`

HTML report summary:

- `activity_count = 27`
- `observed_weather_value_count = 243`
- CODiS-only `activity_count = 26`
- Direct/Mixed `activity_count = 1`
- `high_humidity_activity_count = 14`
- `rain_observed_activity_count = 2`
- `no_rain_observed_activity_count = 25`
- `max_wind_gust_ms = 14.7`

## Engineering boundary

- This is IB3W weather evidence/profile layer only.
- It does not authorize THCI scoring, radar scoring, or final hiking risk scoring.
- Missing weather must not be hard-filled as zero.
- Descriptive tags in the HTML report are not risk scores.
- CODiS `StnPres` is station pressure evidence, not sea-level pressure.
- A downstream consumer must use the weather gate/validator before scoring consumption.

## Recommended next work

1. Build `codex/ib3a-rc-full26-performance-summary-v1`.
2. Then build `codex/ib3w-activity-weather-performance-join-v1`.
