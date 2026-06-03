# IB2D v1.3b contract QA route risk offline map

Run date: 2026-06-01

IB2D role:

```text
route-level baseline risk visualization
```

Formal IB2D visualization input root:

```text
outputs\ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa\
```

Do not use as formal IB2D input:

```text
outputs\ib1e_route_profile_contour_window_terrain\
outputs\ib1e_osm_nlsc_terrain_risk\
outputs\ib1e_route_profile_contour_window_terrain_forced_required_way_test\
```

## Runner

```text
scripts\ib2d_run_v1_3b_contract_qa_offline_maps.py
```

Command:

```powershell
.\.venv\Scripts\python.exe scripts\ib2d_run_v1_3b_contract_qa_offline_maps.py
```

The runner wraps the existing IB2D offline map CLI and passes v1.3b contract QA input/output roots. It does not redesign the IB2D plotting workflow.

## Script Selection

| stage | script_path | input_root | output_root | needs modification for new IB1E root |
|---|---|---|---|---|
| IB2D route risk offline map | `scripts\ib2_route_risk\ib2d_plot_route_risk_offline_map_cli_updated.py` | `outputs\ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa\<case_id>\*_route_profile_contour_window_terrain_enriched.csv/.geojson` | `outputs\ib2d_route_risk_offline_map_v1_3b_contract_qa\<case_id>\` | No; the new runner passes `--risk-csv`, `--risk-geojson`, `--profile-geojson`, `--contour-fp`, and `--out-dir`. |
| IB2D v1.3b batch QA | `scripts\ib2d_run_v1_3b_contract_qa_offline_maps.py` | v1.3b IB1E output root | `outputs\ib2d_route_risk_offline_map_v1_3b_contract_qa\` | New wrapper for formal contract QA execution and validation. |

## Input Contract

IB1E / IB2D formal risk sources:

```text
OSM semantics
OSM semantic risk mapping
OSM hydrology / hydro terrain amplifier
NLSC contour / terrain / slope features
terrain baseline risk
```

IB2D reads the v1.3b IB1E enriched route profile as the formal visualization input. This file is not treated as a narrow IB1E-only dependency; it is the consolidated carrier for the upstream IB1 baseline risk contract:

```text
IB1A route profile
IB1C OSM semantics
IB1C semantic risk score / band
IB1G NLSC contour window features
IB1E OSM + NLSC terrain enrichment
hydrology / hydro terrain amplifier
```

Confirmed fields include:

```text
dist_m / lat / lon / ele_smooth / cum_gain_m / cum_loss_m
osm_highway / route_semantic_class / surface_class
osm_semantic_risk_score / osm_semantic_risk_band
slope_band_window_nlsc / contour_density_20m_nlsc_window
terrain_window_risk_score
hydrology_flags / hydrology_risk_score / hydro_terrain_amplifier_score
osm_terrain_combined_risk_score / osm_terrain_combined_risk_band
```

Pre-IB2D dependency audit confirms:

```text
configs\ supports OSM semantic risk mapping.
nlsc_raw\ supports IB1G / IB1E contour window terrain features.
outputs\ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa\ is valid as IB2D baseline risk input.
```

Terrain / hydro baseline weights are carried in the IB1E summary and enriched profile.

Environment / weather adjustment is not formally integrated in IB2D:

```text
weather_mode = not_integrated_at_ib2d
weather_scope = future_ib3_activity_layer
observed_weather_adjustment_present = False
```

Weather data is not an IB2D blocker. Weather can be inventoried, but it belongs to future IB3 activity-level observed behavior / weather context, such as IB3C or activity-level risk exposure. Do not describe these IB2D outputs as observed-weather-adjusted risk maps.

## Output Root

```text
outputs\ib2d_route_risk_offline_map_v1_3b_contract_qa\
```

Each case outputs:

```text
<case_id>_route_risk_offline_map.png
<case_id>_route_risk_offline_segments.geojson
<case_id>_route_challenge_radar.png
<case_id>_route_risk_offline_map_with_radar.png
<case_id>_ib2d_summary.txt
```

Batch summary:

```text
outputs\ib2d_route_risk_offline_map_v1_3b_contract_qa\_batch_summary\ib2d_v1_3b_contract_qa_case_summary.csv
outputs\ib2d_route_risk_offline_map_v1_3b_contract_qa\_batch_summary\ib2d_v1_3b_contract_qa_stage_summary.md
outputs\ib2d_route_risk_offline_map_v1_3b_contract_qa\_batch_summary\ib2d_v1_3b_contract_qa_run_log.txt
```

## Stage Status

```text
IB2D route risk offline map PASS
```

Case status:

```text
qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b PASS
qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b  PASS
juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b       PASS
zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b  PASS
```

## QA Result

All four cases have:

```text
input_contract_components_complete = True
pre_ib2d_dependency_audit_pass = True
weather_mode = not_integrated_at_ib2d
weather_scope = future_ib3_activity_layer
PNG map present
segment GeoJSON present
radar PNG present
combined map + radar PNG present
case summary present
segment risk_band present
missing_risk_band_count = 0
missing_geometry_count = 0
risk geometry coverage ratio within 0.98-1.02
```

Risk band segment counts:

| case_id | low | moderate | high | very_high | coverage_ratio |
|---|---:|---:|---:|---:|---:|
| qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b | 1718 | 2470 | 0 | 0 | 0.992420 |
| qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b | 784 | 1499 | 963 | 0 | 0.994848 |
| juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b | 899 | 2750 | 47 | 0 | 0.998339 |
| zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b | 3152 | 2296 | 0 | 0 | 0.998151 |

## Decision

IB2D v1.3b route risk offline map is complete.

The v1.3b route-level risk visualization checkpoint can be established using:

```text
outputs\ib2d_route_risk_offline_map_v1_3b_contract_qa\
```

The remaining upstream WARN is IB1C semantic mapping coverage below 1.0 for three cases. It does not block the IB2D visualization checkpoint.

Observed environment / weather risk adjustment remains a future IB3 activity-layer integration step.
