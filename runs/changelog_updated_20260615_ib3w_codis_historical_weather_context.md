# Changelog Update - IB3W CODiS Historical Weather Context

Date: 2026-06-15

## Workspace

- `D:\mountain_work\115_osm`

## Completed commits

- `d82dc54 Add IB3W CODiS historical weather ingest`
- `a9dfaf0 Add IB3W CODiS fallback merge prototype`
- `b4e3d65 Add IB3W CODiS multistation weather ingest`
- `f62aaff Add IB3W CODiS multistation fallback merge`
- `82a04f4 Add IB3W CODiS merged weather distribution profile`
- `76ea085 Add IB3W CODiS weather profile report`

## Added data coverage

Historical CODiS input root:

- `weather/codis/`

Added coverage for 40 raw CSV files:

- 4 stations x 10 dates
- `466910` 鞍部
- `C0AC40` 大屯山
- `466930` 竹子湖
- `C0AH40` 平等

## Added multistation ingest

Output:

- `outputs/ib3w_codis_historical_weather_multistation_ingest_v1/`

Validated result:

- `input_file_count = 40`
- `station_count = 4`
- `station_date_count = 40`
- `expected_row_count = 960`
- `normalized_row_count = 960`
- `zero_fallback_true_count = 0`
- `scoring_authorized_count = 0`
- `production_scoring_authorized_count = 0`
- `ingest_conclusion = PASS`

## Added multistation fallback merge

Output:

- `outputs/ib3w_codis_multistation_fallback_merge_v1/`

Validated result:

- `input_evidence_row_count = 351`
- `original_unavailable_count = 345`
- `codis_merged_observed_count = 237`
- `remaining_unavailable_count = 108`
- `original_observed_preserved_count = 6`
- `original_observed_modified_count = 0`
- `pressure_hpa` recovered from raw CODiS `StnPres`
- `zero_fallback_true_count = 0`
- `thci_scoring_authorized_count = 0`
- `radar_scoring_authorized_count = 0`
- `final_hiking_risk_scoring_authorized_count = 0`
- `production_scoring_authorized_count = 0`
- `merge_conclusion = PASS`

The merge intentionally leaves these variables missing:

- `precipitation_10min_mm`
- `precipitation_1hr_mm`
- `visibility_m`
- `weather`

## Added distribution profile

Output:

- `outputs/ib3w_codis_merged_context_weather_distribution_v1/`

Result:

- 27 activities
- 243 observed weather rows
- 9 observed weather variables per activity
- 237 CODiS historical rows
- 6 same-day direct rows
- scoring authorization remains false

## Added HTML report

Output:

- `outputs/ib3w_codis_weather_profile_report_v1/`

Files:

- `ib3w_codis_weather_profile_report.html`
- `activity_weather_profile_report_table.csv`
- `weather_profile_report_summary.csv`

Result:

- 27 activities
- 243 observed weather values
- 26 CODiS-only activities
- 1 Direct/Mixed activity
- 14 high-humidity activities
- 2 rain-observed activities
- 25 no-rain-observed activities
- maximum wind gust = 14.7 m/s

## Boundary preserved

- This is an IB3W weather evidence/profile layer.
- No THCI, radar, final hiking risk, or production scoring is authorized.
- Missing weather is not hard-filled as zero.
- HTML descriptive tags are not risk scores.
- CODiS `StnPres` remains station pressure evidence.
- Downstream scoring requires the gate/validator.

## Next sequence

1. `codex/ib3a-rc-full26-performance-summary-v1`
2. `codex/ib3w-activity-weather-performance-join-v1`
