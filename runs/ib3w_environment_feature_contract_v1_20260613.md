# IB3W Environment Feature Contract v1

Date: 2026-06-13
Branch: codex/ib3w-environment-feature-contract-doc-v1
Upstream: codex/ib3w-representative-environment-features-v1

## 1. Purpose

This document fixes the consumption contract for the IB3W weather / environment feature chain.

This is documentation-only. It does not modify scripts, outputs, weather DB content, station policy, representative feature aggregation, risk scoring, or THCI scoring.

## 2. Evidence chain

Current chain:

- weather observation availability audit
- GPX positive smoke test
- activity environment window adapter
- environment window review report
- station elevation evidence patch
- station representativeness policy
- representative environment features
- representative environment features HTML report

Relevant commits:

- af4a796 Add IB3W activity weather observation availability audit
- 816e0ee Add IB3W GPX weather observation smoke test
- a846600 Add IB3W activity environment window adapter
- ba68b0f Add IB3W environment window review report
- e7fabd0 Add station elevation evidence to IB3W environment window review report
- bc5d49b Add IB3W station representativeness policy review
- 0f14c22 Add IB3W representative environment features
- 61a8d36 Add IB3W representative environment features review report

## 3. Authoritative outputs

Adapter output:
- outputs/ib3w_activity_environment_window_adapter_v1/

Environment review output:
- outputs/ib3w_environment_window_review_report_v1/

Station representativeness policy output:
- outputs/ib3w_station_representativeness_policy_v1/

Representative environment features output:
- outputs/ib3w_representative_environment_features_v1/

Preferred downstream input:
- outputs/ib3w_representative_environment_features_v1/activity_representative_environment_features.csv

## 4. Primary representative station set

Current primary mountain representative candidates:

| station_id | station_name |
|---|---|
| 466930 | 陽明山 |
| 466910 | 鞍部 |
| C0AC40 | 大屯山 |
| A0A460 | 文化大學 |

Canonical station ID string:

466910|466930|A0A460|C0AC40

Primary representative candidate does not mean final weather fusion.

## 5. Excluded stations

Documented counterexample:

| station_id | station_name | reason |
|---|---|---|
| CAA020 | 國一S026K | road/highway station; observation availability does not imply mountain-route representativeness |

Road/highway stations excluded from mountain representative selection:

| station_id | station_name |
|---|---|
| CAA010 | 國一N013K |
| CAB020 | 國一S006K |
| CAB010 | 國一S001K |

## 6. Current representative feature conclusions

Backend 2024 full26:

- NO_PRIMARY_REPRESENTATIVE_ROWS = 26
- zero_fallback_true_count = 0

Interpretation:

The 2024 backend activities do not have primary representative station rows from the current weather DB observation window.

Downstream rule:

- Do not synthesize weather values for these 26 activities.
- Do not fill missing values with zero.
- Do not treat absence of primary representative rows as benign weather.

GPX 2026 positive case:

- PRIMARY_REPRESENTATIVE_FEATURES_AVAILABLE_PARTIAL = 1
- primary_station_count_present_in_activity_window = 4
- primary_observed_row_count = 22
- primary_missing_row_count = 18
- zero_fallback_true_count = 0

Representative observed features:

- precipitation_mm_primary_observed_station_count = 4
- precipitation_mm_primary_value_mean_of_station_means = 0.0
- temperature_c_primary_value_mean_of_station_means = 19.6708
- relative_humidity_pct_primary_value_mean_of_station_means = 92.4792
- wind_speed_ms_primary_value_max = 5.6

Critical distinction:

- precipitation 0.0 = observed zero precipitation
- precipitation 0.0 != missing-to-zero fallback

## 7. Missingness contract

Mandatory rule:

- Missing remains missing.

Allowed zero:

- Only observed zero precipitation may remain zero.

Forbidden conversions:

- Missing precipitation to 0
- Missing wind speed to 0
- Missing humidity to 0
- Missing temperature to 0
- Missing pressure to 0
- Missing visibility to 0

QA gate:

- zero_fallback_true_count must remain 0

If any downstream layer produces zero_fallback_true_count greater than 0, that layer must be blocked until reviewed.

## 8. Variable availability contract

For the 2026 GPX positive case, primary stations currently provide observed values for:

- precipitation_mm
- temperature_c
- relative_humidity_pct
- wind_speed_ms
- wind_direction_deg

Currently missing or partial variables include:

- precipitation_10min_mm
- precipitation_1hr_mm
- visibility_m
- weather
- pressure_hpa partial

Partial representative features are valid, but only observed variables may be consumed.

## 9. Downstream consumption rule

Downstream IB3 risk / THCI experiments must gate by:

- representative_feature_status
- zero_fallback_true_count

Suggested interpretation:

| representative_feature_status | downstream meaning |
|---|---|
| NO_PRIMARY_REPRESENTATIVE_ROWS | WEATHER_FEATURE_UNAVAILABLE_DO_NOT_SCORE |
| PRIMARY_REPRESENTATIVE_FEATURES_AVAILABLE_PARTIAL | WEATHER_FEATURE_AVAILABLE_PARTIAL_SCORE_ALLOWED_FOR_OBSERVED_VARIABLES_ONLY |
| PRIMARY_REPRESENTATIVE_FEATURES_AVAILABLE_FULL | reserved for future complete coverage |
| PRIMARY_REPRESENTATIVE_ROWS_ALL_MISSING | block or review |
| POLICY_QA_FAILED_ZERO_FALLBACK | block |

## 10. Explicit non-goals

This contract does not authorize:

- risk score computation
- THCI integration
- station fusion weighting
- weather DB mutation
- adapter mutation
- NLSC elevation mutation
- manual weather value filling
- missing-to-zero imputation

## 11. Recommended next step

Next implementation should be a read-only gate layer:

IB3W weather-sensitive activity feature gate v1

Suggested outputs:

- activity_id
- representative_feature_status
- weather_sensitive_feature_gate
- weather_sensitive_feature_gate_reason
- zero_fallback_true_count
- available_weather_variable_set
- missing_weather_variable_set
