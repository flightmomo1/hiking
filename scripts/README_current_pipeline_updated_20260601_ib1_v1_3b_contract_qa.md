# IB1 v1.3b contract QA pipeline

Run date: 2026-06-01

Formal IB1 input root:

```text
outputs\ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa\
```

Do not use as formal IB1 input:

```text
outputs\ib0d_trimmed_mainline\
outputs\ib0d_trimmed_mainline_v1_3b_control_points_only\
outputs\ib0c_anchor
```

## Runner

```text
scripts\ib1_run_v1_3b_contract_qa_pipeline.py
```

Command:

```powershell
.\.venv\Scripts\python.exe scripts\ib1_run_v1_3b_contract_qa_pipeline.py
```

The runner wraps existing CLI scripts and only supplies v1.3b contract QA input/output roots. It does not redesign the pipeline.

## Dry Inventory / Script Selection

| stage | script_path | input_root | output_root | needs modification for new IB0D root |
|---|---|---|---|---|
| IB1A route profile | `scripts\ib1_route_profile\ib1a_build_route_elevation_profile_cli_updated.py` | `outputs\ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa\<case_id>\mainline_ordered_path_trimmed.geojson` | `outputs\ib1_route_profile_v1_3b_contract_qa\` | No; runner passes `--ordered-path-fp` and `--out-dir`. |
| IB1C OSM semantic enrichment | `scripts\ib1_route_profile\ib1c_enrich_route_profile_semantics_cli_updated.py` | `outputs\ib1_route_profile_v1_3b_contract_qa\` + `osm_raw_output\<case_id>` | `outputs\ib1c_route_profile_semantics_v1_3b_contract_qa\` | No; runner passes profile CSV/GeoJSON and `--out-dir`. |
| IB1C OSM semantic risk audit | `scripts\ib1_osm_semantics\ib1c_audit_osm_semantic_risk_mapping_cli_updated.py` | `outputs\ib1c_route_profile_semantics_v1_3b_contract_qa\` | `outputs\ib1c_osm_semantic_audit_v1_3b_contract_qa\` | No. |
| IB1C OSM semantic risk apply | `scripts\ib1_osm_semantics\ib1c_apply_osm_semantic_risk_mapping_cli_updated.py` | `outputs\ib1c_route_profile_semantics_v1_3b_contract_qa\` | `outputs\ib1c_osm_semantic_risk_v1_3b_contract_qa\` | No. |
| IB1G NLSC contour window features | `scripts\ib1_nlsc_terrain\ib1g_v2_compute_contour_window_features_cli_updated_v1_1.py` | IB0D route line + selected `nlsc_raw\<tile>\向量25K\ContourL.shp` | `outputs\ib1g_contour_window_features_v1_3b_contract_qa\` | No; runner passes `--route-line-fp`, selected `--contour-fp`, selected `--tile`, and `--out-dir`. |
| IB1E OSM + NLSC terrain enrichment | `scripts\ib1_nlsc_terrain\ib1e_enrich_route_profile_with_contour_window_terrain_cli_updated.py` | IB1C risk + IB1G contour window | `outputs\ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa\` | No. |
| IB1E plot | `scripts\ib1_nlsc_terrain\ib1e_plot_osm_nlsc_terrain_risk_profile.py` | IB1E enriched CSV/GeoJSON | `outputs\ib1e_osm_nlsc_terrain_risk_plot_v1_3b_contract_qa\` | No. |

The older `ib1e_combine_osm_semantic_and_nlsc_terrain_risk.py` hard-codes legacy paths and was not used as formal runner.

## NLSC Tile Selection

Specification basis:

```text
113 年度「臺灣地區經建版地形圖」製圖作業工作總報告書
```

Applied assumptions:

```text
1. 經建版地形圖包含 1/25,000、1/50,000、1/100,000。
2. 本專案 nlsc_raw\<tile>\向量25K\ContourL.shp 對應 1/25,000 圖資。
3. 1/25,000 圖幅經緯度範圍為 7'30" x 7'30"。
4. 投影為橫麥卡脫 TM 投影，經差二度分帶；臺灣地區中央子午線 121°E。
5. 大地基準採 TWD97，高程基準採 TWVD2001。
6. 1/25,000 等高線規格：計曲線 50m、首曲線 10m、間曲線 5m。
```

Selector definition:

```text
route geometry / GPS bbox
-> candidate 1/25,000 tile
-> nlsc_raw\<tile>\向量25K\ContourL.shp
-> route buffer intersection + valid elevation count validation
```

The v1.3b runner no longer defaults every IB1G case to `97233NW`.

## Output roots

```text
outputs\ib1_route_profile_v1_3b_contract_qa\
outputs\ib1c_route_profile_semantics_v1_3b_contract_qa\
outputs\ib1c_osm_semantic_audit_v1_3b_contract_qa\
outputs\ib1c_osm_semantic_risk_v1_3b_contract_qa\
outputs\ib1g_contour_window_features_v1_3b_contract_qa\
outputs\ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa\
outputs\ib1e_osm_nlsc_terrain_risk_plot_v1_3b_contract_qa\
outputs\ib1_v1_3b_contract_qa_pipeline_summary\
```

## Summary outputs

```text
outputs\ib1_v1_3b_contract_qa_pipeline_summary\ib1_v1_3b_stage_summary.csv
outputs\ib1_v1_3b_contract_qa_pipeline_summary\ib1_v1_3b_case_summary.csv
outputs\ib1_v1_3b_contract_qa_pipeline_summary\ib1_v1_3b_pipeline_summary.md
outputs\ib1_v1_3b_contract_qa_pipeline_summary\ib1_v1_3b_contract_qa_run_log.txt
```

## Stage status

```text
IB1A route profile                 PASS
IB1C OSM semantic enrichment       PASS
IB1C OSM semantic risk audit/apply WARN
IB1G NLSC contour window features  PASS
IB1E OSM + NLSC terrain enrichment PASS
```

IB1C semantic risk is `WARN` because three cases have mapping coverage below 1.0:

```text
qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b  0.933333
juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b       0.954545
zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b  0.950000
```

The WARN is non-blocking for IB2D in this run because risk score/band outputs exist, IB1E terrain enrichment completed, contour match rate is 1.0, and no blocking issue is present.

## Case status

```text
qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b PASS
qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b  WARN
juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b       WARN
zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b  WARN
```

All four cases have:

```text
ib2_ready = True
contour_match_rate = 1.0
max_dist_to_contour_window_mid_m = 10.0
```

## Decision

IB1A / IB1C / IB1G / IB1E v1.3b contract QA pipeline is complete with accepted WARN in IB1C semantic risk mapping coverage.

Next formal input root for IB2D:

```text
outputs\ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa\
```

Recommended follow-up:

```text
Review unmapped semantic values in outputs\ib1c_osm_semantic_audit_v1_3b_contract_qa\ before tightening IB1C risk to PASS-only.
```
