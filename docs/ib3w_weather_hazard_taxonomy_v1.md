# IB3W Weather Hazard Taxonomy v1

## Purpose

This document defines the first formal taxonomy for weather-related and environment-triggered hiking hazard contexts in the IB3W layer.

IB3W weather hazard taxonomy is a **context contract**, not a final hiking risk score.

This layer defines:
- what weather/environment hazard families exist;
- which observable variables may support each family;
- which outputs should remain proxy/context only;
- which hazards are outside direct weather observation and require another data layer.

This document does not define THCI scoring, final route risk, user risk, rescue priority, or safety recommendation thresholds.

---

## Core boundary

IB3W weather/environment context must preserve the following principles:

1. Missing remains missing.
2. Observed zero remains observed zero.
3. No missing weather values may be imputed as zero.
4. Proxy layers must not claim true physical states when only indirect observations exist.
5. Weather context is not yet a hiking risk score.
6. Weather-triggered secondary hazards must be separated from direct meteorological observations.
7. Non-weather hazards, such as earthquakes, must be represented in a separate geohazard layer.

---

## Hazard families

### 1. Heat stress context

Covers:
- heat exposure
- hot sun
- muggy heat
- dehydration tendency
- heat exhaustion / heat stroke proxy

Candidate variables:
- temperature_c
- relative_humidity_pct
- sunshine_duration_min
- wind_speed_ms
- uv_index
- route exposure / shade context, if later joined

Typical derived contexts:
- heat_stress_proxy
- humid_heat_proxy
- dehydration_context
- wbgt_like_proxy

Boundary:
- This is not a medical diagnosis.
- User-specific heat tolerance is not included in v1.

---

### 2. Cold and wet exposure context

Covers:
- cold stress
- wet cold
- wind chill
- hypothermia-prone conditions

Candidate variables:
- temperature_c
- wind_speed_ms
- wind_gust_ms
- precipitation_mm / precipitation_1hr_mm / precipitation_10min_mm
- relative_humidity_pct
- hours_since_last_observed_rain

Typical derived contexts:
- cold_stress_proxy
- wind_chill_proxy
- wet_cold_exposure_proxy

Boundary:
- Hypothermia is not determined by temperature alone.
- Clothing, fatigue, exposure duration, and individual physiology are not included in v1.

---

### 3. Precipitation and surface wetness context

Covers:
- current rain
- recent rain
- antecedent rain
- local surface wetness possibility
- slippery surface proxy

Candidate variables:
- precipitation_mm
- precipitation_10min_mm
- precipitation_1hr_mm
- lookback precipitation context
- hours_since_last_observed_rain
- temperature_c
- relative_humidity_pct
- wind_speed_ms
- sunshine_duration_min, when available
- terrain/surface context, if later joined

Current IB3W related layers:
- antecedent precipitation context
- surface wetness proxy
- sunshine drying context

Boundary:
- Surface wetness proxy is not true soil moisture.
- Rainfall amount should not be treated as cumulative unless the source semantics are proven.
- Light recent rain should not be amplified into persistent wetness without supporting evidence.

---

### 4. Wind exposure context

Covers:
- strong wind
- gust exposure
- ridge wind
- summit wind
- balance and equipment handling issues
- wind-enhanced cold exposure

Candidate variables:
- wind_speed_ms
- wind_gust_ms
- wind_direction_deg
- route exposure / ridge / summit / open terrain context, if later joined

Typical derived contexts:
- wind_exposure_proxy
- ridge_wind_context
- wind_chill_enhancement_context

Boundary:
- Station wind may not represent local ridge gusts.
- Route exposure join is required before making segment-level claims.

---

### 5. Visibility and navigation degradation context

Covers:
- fog
- mist
- low cloud
- low visibility
- route-finding degradation
- increased wrong-turn /迷航 possibility

Candidate variables:
- visibility_m
- weather text
- relative_humidity_pct
- temperature_c
- dew point proxy, if later available
- route complexity / junction density, if later joined

Typical derived contexts:
- low_visibility_proxy
- navigation_degradation_proxy
- fog_mist_context

Boundary:
- Low visibility is not the same as actual迷航.
- Actual迷航 requires activity behavior or route deviation analysis.

---

### 6. Convective storm and lightning context

Covers:
- thunderstorm
- lightning
- short-duration heavy rain
- sudden gusts
- rapid weather deterioration

Candidate variables:
- weather text
- precipitation_10min_mm
- precipitation_1hr_mm
- wind_gust_ms
- radar echo, if later available
- lightning observations or warnings, if later available
- official weather warnings, if later available

Typical derived contexts:
- thunderstorm_context
- lightning_exposure_context
- short_duration_heavy_rain_context

Boundary:
- Lightning cannot be inferred reliably from rain alone.
- If lightning observation is unavailable, the context must remain unavailable or warning-based only.

---

### 7. Hydrologic and slope response context

Covers:
- creek rise
- stream crossing hazard
- slope failure
- landslide
- debris flow
- falling soil/rock triggered by rainfall

Candidate variables:
- precipitation_10min_mm
- precipitation_1hr_mm
- 24h / 72h antecedent precipitation context
- water level observations
- stream / waterway proximity
- slope
- geology / landslide / debris-flow susceptibility data, if later available

Typical derived contexts:
- hydrologic_response_context
- stream_crossing_risk_proxy
- slope_failure_context
- debris_flow_context

Boundary:
- This is secondary hazard context, not direct meteorological observation.
- Requires terrain and hydrology joins before route-segment claims.
- Missing water-level observations must not be treated as safe/zero.

---

### 8. Weather system context

Covers:
- typhoon influence
- front passage
- northeast monsoon
- pressure trend
- synoptic-scale weather deterioration

Candidate variables:
- pressure_hpa
- pressure trend
- wind direction shift
- official weather warnings
- weather text
- regional forecast context, if later available

Typical derived contexts:
- synoptic_weather_context
- weather_system_hazard_context
- monsoon_wet_cold_context
- typhoon_outer_band_context

Boundary:
- Single-station weather rows are insufficient for full synoptic classification.
- Official warning or external forecast products may be required.

---

### 9. Air quality and respiratory burden context

Covers:
- PM2.5
- AQI
- ozone
- smoke / haze
- respiratory burden during exertion

Candidate variables:
- AQI
- PM2.5
- PM10
- O3
- smoke / haze text, if available

Typical derived contexts:
- air_quality_context
- respiratory_burden_proxy

Boundary:
- This is not purely weather.
- It may require EPA or air-quality station data outside the current weather DB.

---

### 10. Non-weather geohazard context

Covers:
- earthquake
- recent shaking
- rockfall
- slope weakening
- trail closure
- post-earthquake landslide susceptibility

Candidate variables:
- earthquake event data
- intensity map
- recent earthquake time
- landslide inventory
- rockfall / debris-flow susceptibility
- trail closure announcements

Typical derived contexts:
- geohazard_context
- post_earthquake_slope_instability_context
- trail_closure_context

Boundary:
- Earthquake is not meteorological and cannot be derived from weather DB.
- It must be handled by a separate non-weather geohazard layer.

---

## Current IB3W implementation coverage

Current implemented layers:

1. Weather-sensitive feature gate
2. Weather-sensitive feature vector
3. Antecedent precipitation context
4. Surface wetness proxy
5. Sunshine drying context

Currently covered hazard families:
- precipitation and surface wetness context
- partial drying context
- partial heat/cold/wind variables as inputs, but not formal hazard contexts yet

Not yet implemented:
- heat stress context
- cold and wet exposure context
- wind exposure context
- visibility/navigation context
- convective storm/lightning context
- hydrologic/slope response context
- weather system context
- air quality context
- non-weather geohazard context

---

## Recommended next implementation order

1. Visibility and navigation degradation context
2. Wind exposure context
3. Cold and wet exposure context
4. Heat stress context
5. Hydrologic and slope response context
6. Convective storm and lightning context
7. Weather system context
8. Air quality context
9. Non-weather geohazard context

Reasoning:
- Visibility, wind, cold/wet, and heat can reuse existing weather observations.
- Hydrologic/slope response requires terrain/hydrology joins.
- Lightning, weather system, air quality, and earthquake require additional external data sources.

---

## Contract summary

IB3W weather hazard taxonomy v1 defines the hazard vocabulary and implementation boundaries only.

It must not be used as:
- final hiking risk score;
- THCI score;
- medical diagnosis;
- landslide prediction;
- lightning detection;
- soil moisture model;
- route closure judgment.

It may be used as:
- design contract for future IB3W context scripts;
- QA checklist for weather context coverage;
- vocabulary for downstream feature vectors;
- evidence layer for later risk integration.
