# IB3W weather context source inventory + schema migration v1

- date: 2026-06-11
- branch: `codex/ib3w-weather-context-source-inventory-v1`
- status: FORMAL_INVENTORY_DRAFT_READY
- scope: source inventory, schema migration boundary, and v1 interface planning only
- not in scope: full pipeline execution, large output scan, behavior analysis, radar/THCI scoring, route-risk adjustment, executable join script

## 1. Pipeline position

IB3W is inserted between the calibrated activity backend dataset and behavior/event analysis:

```text
IB3A RC backend activity enriched v1l2
  -> IB3W weather context layer
  -> IB3M behavior analysis
```

The current upstream input reference is:

```text
outputs\ib3a_rc_backend_activity_enriched_v1l2_osm_radar_evidence_qixing_lengshuikeng_full26
```

This upstream dataset is treated as the row-level calibrated activity dataset and already contains calibrated activity track, OSM semantic evidence, NLSC/calibrated elevation, IB2 route-risk evidence, radar evidence hints, `route_class`, `movement_state`, and `backend_use_policy`.

IB3W should add environmental context without changing the semantics of the calibrated activity rows. It should not overwrite activity quality, route risk, radar evidence, or behavior labels.

## 2. Weather / hydrology source location

Primary local weather data folder:

```text
C:\mountain_work\115_osm\weather
```

Primary SQLite database:

```text
C:\mountain_work\115_osm\weather\tw_weather_2026-05-01.sqlite3
```

SQLite sidecar files observed / expected for active or recently used SQLite WAL mode:

```text
C:\mountain_work\115_osm\weather\tw_weather_2026-05-01.sqlite3-wal
C:\mountain_work\115_osm\weather\tw_weather_2026-05-01.sqlite3-shm
```

The sidecar files should not be treated as independent weather sources. They belong to the SQLite database runtime state.

## 3. Design principles

Weather data is optional contextual evidence, not a hard dependency.

The IB3W layer must preserve uncertainty explicitly:

- missing weather does not mean normal weather
- missing rainfall does not mean `0 mm`
- missing wind does not mean calm
- missing hydrology does not mean water level unchanged
- `0 mm` rainfall is valid only when a trusted source explicitly reports no rainfall during the relevant activity/window interval

The old zero-valued “normal baseline” fallback is a rewrite boundary. It must not be carried forward as observed weather evidence.

## 4. Weather context types

Recommended IB3W context type vocabulary:

| context_type | v1 use | meaning |
|---|---:|---|
| `OBSERVED` | yes | Directly sourced weather/hydrology observation from a trusted station/source within accepted temporal and spatial quality gates. |
| `IMPUTED` | yes | Estimated context derived from nearby/related sources using explicit interpolation, station ranking, or temporal carry-forward rules. Must retain method and confidence. |
| `MISSING` | yes | No acceptable source or observation is available. This is an explicit state, not equivalent to normal weather. |
| `INFERRED_FROM_BEHAVIOR` | no | Reserved for future IB3W/IB3M hypothesis layer where behavior anomalies may suggest environmental conditions. Must not be mixed with observed or imputed context in v1. |

`INFERRED_FROM_BEHAVIOR` is excluded from v1 observed/imputed context. It should remain a later hypothesis-layer concept because using activity behavior to infer weather can create circular reasoning if the same behavior is later analyzed by IB3M.

## 5. Existing prototype script inventory and migration decision

| script | v1 decision | migration note |
|---|---|---|
| `ib3x_inspect_weather_sqlite.py` | reference | Useful low-level DB inspection reference. Should be superseded by formal DB schema inventory. |
| `ib3b0_inspect_weather_database_schema.py` | reuse/refactor | Good candidate for IB3W DB schema inventory and source adapter reference. Keep read-only behavior. |
| `ib3a_find_nearby_weather_stations.py` | defer/merge | Weather-only station discovery can be merged into environment-station candidate discovery. |
| `ib3a_find_nearby_environment_stations.py` | rewrite for v1 | Rebuild as station candidate discovery using route distance, coverage, recency, elevation similarity, variable support, and source quality ranking. |
| `ib3b_extract_environment_window.py` | rewrite boundary | Core window extraction idea is useful, but any zero-valued normal fallback must be removed. Missing observations must output `MISSING`, `UNKNOWN`, or `NO_SOURCE` states. |
| `ib3b2_analyze_weather_station_update_frequency.py` | reuse/refactor | High value for temporal quality, station recency, cadence, antecedent-weather features, and confidence scoring. |
| `ib3b4_fuse_route_weather_conditions.py` | refactor later | Useful route-level aggregation base, but must add source/quality gates and context type handling before use. |
| `ib3c_apply_environment_risk_adjustment.py` | defer | Do not adjust route risk in v1 inventory/schema migration. Avoid premature risk-score coupling. |
| `ib3c2_compare_weather_trend_adjustment.py` | defer | Keep as later comparison/regression reference only. |
| `ib3e_extract_route_microclimate_terrain_features.py` | reuse/refactor | Useful static terrain susceptibility input for later weather-terrain interaction. Should not imply observed weather. |
| `ib3f_apply_weather_terrain_microclimate_interaction.py` | defer | Segment-level weather-terrain interaction reference. Not needed for v1 inventory. |
| `ib3d_plot_environment_adjusted_risk_profile.py` | defer | Visualization of adjusted risk should wait until IB3W interface and quality gates are stable. |
| `ia2_nlsc_contour_hydrology_enrich.py` | reference | Static hydrology/terrain enrichment reference. Must separate mapped hydro features from observed hydrologic state. |
| `thci_diagnose_weather_sensitivity_v1_0b.py` | defer | THCI weather sensitivity diagnosis is downstream of IB3W. Not part of v1 source inventory. |
| `thci_diagnose_weather_hydrology_topography_v1_0c_review.py` | defer | Review-only diagnostic reference for later weather/hydrology/topography interaction. |
| `ib3x_run_bad_weather_scenario_0430.py` | regression reference | Keep as regression scenario after IB3W interface is modularized. Do not run in v1 inventory branch. |

## 6. Required schema migration boundaries

### 6.1 Remove zero-valued normal fallback

Any previous logic that emits synthetic values such as rainfall `0`, wind speed `0`, water level unchanged, or normal weather when source data is absent must be removed or quarantined.

Replacement behavior:

- no station/source found -> `context_type=MISSING`, `missing_reason=NO_SOURCE`
- source exists but no observation in window -> `context_type=MISSING`, `missing_reason=NO_OBSERVATION_IN_WINDOW`
- observation exists but fails quality gate -> `context_type=MISSING`, `missing_reason=FAILED_QUALITY_GATE`
- value estimated from valid related observations -> `context_type=IMPUTED`, with `imputation_method`, `source_count`, and `confidence_score`
- direct valid observation -> `context_type=OBSERVED`

### 6.2 Separate static susceptibility from observed condition

Terrain and hydrology-map features can indicate susceptibility, but not actual weather state. For example, contour/hydrology or terrain exposure can support “rain-sensitive segment” features, but cannot assert rainfall, high water, fog, wind, or wet ground without external evidence.

### 6.3 Avoid behavior-weather circularity in v1

IB3W v1 should not infer weather from slow movement, pause/stall, heart-rate drift, route deviation, or other behavior features. Those belong to a later hypothesis layer and should be clearly marked as `INFERRED_FROM_BEHAVIOR` only after IB3M/IB3W interfaces are separated.

## 7. Proposed v1 output granularity

Recommended first stable granularity:

1. route/activity-level context summary
2. optional time-window context rows aligned to activity windows
3. later segment-level join only after source and temporal quality gates are stable

Do not begin with route-risk adjustment. The first output should be evidence/context, not score mutation.

## 8. Candidate source quality dimensions

Station/source ranking should consider:

- spatial relation to route: nearest point, route-distance coverage, elevation difference, ridge/valley plausibility
- temporal coverage: observation frequency, update gaps, window coverage ratio, antecedent-window coverage
- variable support: rainfall, temperature, humidity, wind, pressure, hydrology/water level if available
- recency and latency
- source reliability and station metadata completeness
- source conflict handling when multiple stations disagree

## 9. Suggested minimal IB3W v1 schema groups

- identity: route, case, activity, window, segment references
- source: source type, station id/name, variable, raw table/column reference
- temporal alignment: observation time, activity/window start/end, temporal gap, coverage ratio
- spatial alignment: route distance, station distance, elevation difference
- value: observed/imputed value, unit, aggregation method
- quality: context type, confidence score, quality flags, missing reason
- provenance: DB path/hash/version if available, script/config version, generated timestamp

A schema draft is placed at:

```text
configs\weather_context\ib3w_weather_context_schema_v1.csv
```

## 10. Acceptance criteria for this branch

This branch is complete when:

- the former draft inventory is upgraded into a formal source inventory document
- v1l2 input reference and weather SQLite DB path are explicitly recorded
- pipeline position is recorded as `v1l2 -> IB3W -> IB3M`
- `INFERRED_FROM_BEHAVIOR` is explicitly excluded from v1 observed/imputed context
- zero-valued normal fallback is documented as a rewrite boundary
- README update records the current pipeline state and non-goals
- optional schema draft exists for future implementation
- no full pipeline run is performed
- no large outputs are scanned or committed
- no executable join script is created

## 11. Recommended explicit git add list

Do not use `git add .`.

Recommended explicit add list for this branch:

```powershell
git add `
  runs\ib3w_weather_context_source_inventory_20260611.md `
  scripts\README_current_pipeline_updated_20260611_ib3w_weather_context_inventory.md `
  configs\weather_context\ib3w_weather_context_schema_v1.csv
```

Optional, only if the original draft is intentionally retained/updated:

```powershell
git add runs\ib3w_weather_context_source_inventory_20260611_draft.md
```

