# CURRENT INDEX - IB3W CODiS Historical Weather Context

Date: 2026-06-15

## Workspace

- `D:\mountain_work\115_osm`

## Current branch

- `codex/ib3w-codis-historical-weather-context-closeout-v1`

## Scope

This closeout records the completed IB3W CODiS historical weather evidence and
profile chain. The chain normalizes historical observations, merges supported
weather variables into previously unavailable context rows, profiles the
result, and publishes an HTML review artifact.

## Completed commit chain

- `d82dc54 Add IB3W CODiS historical weather ingest`
- `a9dfaf0 Add IB3W CODiS fallback merge prototype`
- `b4e3d65 Add IB3W CODiS multistation weather ingest`
- `f62aaff Add IB3W CODiS multistation fallback merge`
- `82a04f4 Add IB3W CODiS merged weather distribution profile`
- `76ea085 Add IB3W CODiS weather profile report`

## Raw CODiS inputs

Root:

- `weather/codis/`

Coverage:

- 4 stations
- 10 dates
- 40 raw CODiS hourly CSV files

Stations:

- `466910` - 鞍部
- `C0AC40` - 大屯山
- `466930` - 竹子湖
- `C0AH40` - 平等

## Multistation ingest

Output root:

- `outputs/ib3w_codis_historical_weather_multistation_ingest_v1/`

Result:

- `input_file_count = 40`
- `station_count = 4`
- `station_date_count = 40`
- `expected_row_count = 960`
- `normalized_row_count = 960`
- `zero_fallback_true_count = 0`
- `scoring_authorized_count = 0`
- `production_scoring_authorized_count = 0`
- `ingest_conclusion = PASS`

## Multistation fallback merge

Output root:

- `outputs/ib3w_codis_multistation_fallback_merge_v1/`

Result:

- `input_evidence_row_count = 351`
- `original_unavailable_count = 345`
- `codis_merged_observed_count = 237`
- `remaining_unavailable_count = 108`
- `original_observed_preserved_count = 6`
- `original_observed_modified_count = 0`
- `pressure_hpa` was recovered from raw CODiS `StnPres`
- `zero_fallback_true_count = 0`
- `thci_scoring_authorized_count = 0`
- `radar_scoring_authorized_count = 0`
- `final_hiking_risk_scoring_authorized_count = 0`
- `production_scoring_authorized_count = 0`
- `merge_conclusion = PASS`

Variables that remain unavailable and must stay missing:

- `precipitation_10min_mm`
- `precipitation_1hr_mm`
- `visibility_m`
- `weather`

## Weather distribution profile

Output root:

- `outputs/ib3w_codis_merged_context_weather_distribution_v1/`

Result:

- `activity_count = 27`
- `observed_row_count = 243`
- 27 activities x 9 observed weather variables
- `OBSERVED_HISTORICAL_CODIS = 237`
- `SAME_DAY_DIRECT_OBSERVATION = 6`
- `scoring_authorized = False`

## HTML report

Output root:

- `outputs/ib3w_codis_weather_profile_report_v1/`

Files:

- `ib3w_codis_weather_profile_report.html`
- `activity_weather_profile_report_table.csv`
- `weather_profile_report_summary.csv`

Result:

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
- CODiS station pressure from `StnPres` is station pressure evidence, not sea-level pressure.
- A downstream consumer must use the gate/validator before scoring consumption.

## Recommended next steps

1. `codex/ib3a-rc-full26-performance-summary-v1`
2. `codex/ib3w-activity-weather-performance-join-v1`
