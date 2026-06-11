# README current pipeline update — IB3W weather context inventory

- date: 2026-06-11
- branch: `codex/ib3w-weather-context-source-inventory-v1`
- update type: pipeline documentation / schema migration planning
- execution scope: documentation only

## Current upstream activity dataset

The current formal upstream backend activity dataset is:

```text
outputs\ib3a_rc_backend_activity_enriched_v1l2_osm_radar_evidence_qixing_lengshuikeng_full26
```

This is the row-level calibrated activity dataset and is treated as the input boundary for the next environmental context layer.

Expected upstream contents include:

- calibrated activity track
- OSM semantic evidence
- NLSC / calibrated elevation
- IB2 route risk evidence
- radar evidence hints
- `route_class`
- `movement_state`
- `backend_use_policy`

## New pipeline position

The next layer is IB3W weather context:

```text
v1l2 backend activity dataset
  -> IB3W weather context layer
  -> IB3M behavior analysis
```

IB3M behavior analysis should not be started before the IB3W source inventory, context type rules, missing-data semantics, and schema migration boundaries are documented.

## Weather source root

Primary local weather folder:

```text
C:\mountain_work\115_osm\weather
```

Primary SQLite DB:

```text
C:\mountain_work\115_osm\weather\tw_weather_2026-05-01.sqlite3
```

Related SQLite sidecar files:

```text
C:\mountain_work\115_osm\weather\tw_weather_2026-05-01.sqlite3-wal
C:\mountain_work\115_osm\weather\tw_weather_2026-05-01.sqlite3-shm
```

The sidecar files are not independent sources and should not be committed as outputs.

## IB3W design rules

Weather/hydrology data is optional contextual evidence, not a hard dependency.

Missing data must remain missing:

- missing weather does not mean normal weather
- missing rainfall does not mean `0 mm`
- missing wind does not mean calm
- missing hydro does not mean water level unchanged
- `0 mm` is valid only when a trusted source explicitly reports no rainfall during the relevant interval

The old zero-valued “normal baseline” fallback is a rewrite boundary and must not be reused as observed weather.

## IB3W context types

| context_type | current status |
|---|---|
| `OBSERVED` | allowed in v1 |
| `IMPUTED` | allowed in v1 with explicit method/confidence |
| `MISSING` | allowed and required in v1 |
| `INFERRED_FROM_BEHAVIOR` | reserved for later hypothesis layer; excluded from v1 observed/imputed context |

`INFERRED_FROM_BEHAVIOR` must not be mixed with observed/imputed weather context because it can create circular reasoning when IB3M later analyzes behavior.

## Prototype migration status

Reusable / refactor candidates:

- `ib3b0_inspect_weather_database_schema.py`
- `ib3a_find_nearby_environment_stations.py`
- `ib3b_extract_environment_window.py` after removing zero fallback
- `ib3b2_analyze_weather_station_update_frequency.py`
- `ib3b4_fuse_route_weather_conditions.py` after source/quality gating
- `ib3e_extract_route_microclimate_terrain_features.py` as static susceptibility input

Deferred until after IB3W interface stabilizes:

- `ib3c_apply_environment_risk_adjustment.py`
- `ib3c2_compare_weather_trend_adjustment.py`
- `ib3d_plot_environment_adjusted_risk_profile.py`
- `ib3f_apply_weather_terrain_microclimate_interaction.py`
- `thci_diagnose_weather_sensitivity_v1_0b.py`
- `thci_diagnose_weather_hydrology_topography_v1_0c_review.py`
- `ib3x_run_bad_weather_scenario_0430.py`

## Files introduced by this documentation update

```text
runs\ib3w_weather_context_source_inventory_20260611.md
scripts\README_current_pipeline_updated_20260611_ib3w_weather_context_inventory.md
configs\weather_context\ib3w_weather_context_schema_v1.csv
```

## Non-goals for this branch

This branch must not:

- run the full pipeline
- scan large output folders
- create executable join scripts
- mutate route risk score
- create formal radar or THCI scores
- infer weather from behavior
- commit generated outputs
- use `git add .`

## Suggested explicit git add

```powershell
git add `
  runs\ib3w_weather_context_source_inventory_20260611.md `
  scripts\README_current_pipeline_updated_20260611_ib3w_weather_context_inventory.md `
  configs\weather_context\ib3w_weather_context_schema_v1.csv
```
