# README current pipeline update - IB3W weather context consolidation

- 日期：2026-06-12
- 分支：codex/ib3w-weather-context-consolidation-v1
- 上游基底：f6ec72e Add IB3W adapter batch context summary

## IB3W Current Position

IB3W is the Weather / Hydro Context Evidence Layer.

It is intended to provide activity-level contextual evidence for:

- precipitation_1hr
- wind_speed
- temperature
- water_level

IB3W does not replace route risk, terrain risk, THCI, radar, or activity behavior analysis.

## Completed IB3W QA Ladder

Current completed QA/prototype chain:

1. smoke test v1
   - commit: 85c2fc3
   - verifies no zero-valued normal fallback

2. station ranking v1
   - commit: a7b1563
   - generates weather/water Top-N station candidates

3. temporal coverage v1
   - commit: 5ca313b
   - audits station-level temporal availability

4. variable coverage v1
   - commit: ea9c800
   - audits variable-level availability

5. adapter row context summary v1
   - commit: df967d4
   - converts variable coverage into activity-level context_status

6. adapter batch context summary v1
   - commit: f6ec72e
   - combines one or more activity-level context summaries into batch QA counts

## Current Formal Boundary

The current IB3W outputs should be treated as QA/prototype evidence.

The formal adapter should eventually consolidate the following into one main activity-level context builder:

- activity window extraction
- representative location extraction
- station candidate ranking
- station metadata / elevation enrichment
- temporal coverage audit
- variable coverage audit
- context_status mapping
- activity-level context summary output

## Required Context Variables

The required IB3W context variables are:

- precipitation_1hr
- wind_speed
- temperature
- water_level

## Formal Context Status

The formal adapter should output:

- OBSERVED
- MISSING
- NO_SOURCE
- UNKNOWN

Detailed audit_status should remain visible and not be collapsed away.

## No-zero-fallback Rule

The following assumptions are forbidden:

- missing rainfall = 0 mm
- missing wind = calm
- missing temperature = normal
- missing water level = unchanged

Missing or null contextual evidence must remain missing evidence.

## Station Elevation Status

Current state:

- weather station elevation_m can be used when available in DB.
- water station elevation_m is not available in the current DB schema.
- station lat/lon to DEM/NLSC elevation lookup has not yet been formalized.

Recommended next step before formal adapter:

    codex/ib3w-station-metadata-elevation-v1

Purpose:

- extract unique weather/water stations
- enrich station metadata with elevation
- create station metadata cache
- use elevation_delta_m in formal station ranking

## Recommended Next Branch

Recommended next branch:

    codex/ib3w-station-metadata-elevation-v1

Then:

    codex/ib3w-weather-context-formal-adapter-v1

The formal adapter should still avoid row-level weather join until activity-level context summary is stable across multiple activities.
