# IB2 / IB2D v1.3b contract QA

Run date: 2026-06-01

## Scope

This stage is:

```text
route-level baseline risk visualization
```

Formal mainline:

```text
IB1E v1.3b contract QA output
-> IB2_v2 route risk scoring CLI updated
-> IB2D route risk offline map CLI updated
```

Formal scripts:

```text
scripts\ib2_route_risk\ib2_v2_route_risk_scoring_cli_updated.py
scripts\ib2_route_risk\ib2d_plot_route_risk_offline_map_cli_updated.py
```

`__pycache__` files are execution cache only and are not formal source.

## Weather Boundary

Observed weather is not integrated at IB2D:

```text
weather_mode = not_integrated_at_ib2d
weather_scope = future_ib3_activity_layer
```

Do not describe these outputs as observed-weather-adjusted.

## Risk Sources

```text
IB1C OSM semantic risk
IB1G NLSC contour / terrain window features
IB1E OSM + NLSC terrain / hydro baseline enrichment
IB2_v2 route risk scoring
IB2D offline map + radar visualization
```

## Roots

Input:

```text
outputs\ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa\
```

IB2 scoring output:

```text
outputs\ib2_v2_route_risk_v1_3b_contract_qa\
```

IB2D output:

```text
outputs\ib2d_route_risk_offline_map_v1_3b_contract_qa\
```

Legacy roots are not formal input/output for this run.

## Runner

```text
scripts\ib2_ib2d_run_v1_3b_contract_qa.py
```

Command:

```powershell
.\.venv\Scripts\python.exe scripts\ib2_ib2d_run_v1_3b_contract_qa.py
```

The runner compiles the two formal scripts, assigns NLSC contour tiles by route-buffer intersections, runs IB2 scoring, runs IB2D offline map/radar, and writes batch QA summaries.

## Tile Assignment

```text
outputs\ib2d_route_risk_offline_map_v1_3b_contract_qa\_batch_summary\ib2d_v1_3b_contract_qa_tile_assignment.csv
```

Specification basis:

```text
113 年度「臺灣地區經建版地形圖」製圖作業工作總報告書
```

NLSC / 經建版地形圖 assumptions used by this project:

```text
1. 經建版地形圖包含 1/25,000、1/50,000、1/100,000。
2. 本專案 nlsc_raw\<tile>\向量25K\ContourL.shp 對應 1/25,000 圖資。
3. 1/25,000 圖幅經緯度範圍為 7'30" x 7'30"。
4. 投影為橫麥卡脫 TM 投影，經差二度分帶；臺灣地區中央子午線 121°E。
5. 大地基準採 TWD97，高程基準採 TWVD2001。
6. 1/25,000 等高線規格：計曲線 50m、首曲線 10m、間曲線 5m。
```

NLSC tile selector definition:

```text
route geometry / GPS bbox
-> candidate 1/25,000 tile
-> nlsc_raw\<tile>\向量25K\ContourL.shp
-> route buffer intersection + valid elevation count validation
```

IB1G / IB2D must not default every case to `97233NW`. The selector must choose the per-route candidate tile and hard fail or WARN if no candidate can be validated.

Tile decisions:

```text
冷水坑七星山  97233NW
小油坑七星山  97233NW
絹絲瀑布      97233NW
中華科大九五峰 97233SW
```

Zhonghua tile correction cleanup has been completed. Prior IB1G recorded `97233NW`, but route-buffer contour intersection found `97233NW=0` and `97233SW=73`; Zhonghua IB1G / IB1E / IB2_v2 / IB2D now use `97233SW`.

## Results

```text
IB2_v2 route risk scoring PASS for all four cases.
IB2D offline map / radar PASS for all four cases.
Overall: 4 PASS.
```

Resolved cleanup:

```text
zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b
Before: 97233NW, slope_unknown_ratio = 1.0
After:  97233SW, slope_unknown_ratio = 0.0
```

## Summary Outputs

```text
outputs\ib2d_route_risk_offline_map_v1_3b_contract_qa\_batch_summary\ib2_v1_3b_contract_qa_case_summary.csv
outputs\ib2d_route_risk_offline_map_v1_3b_contract_qa\_batch_summary\ib2d_v1_3b_contract_qa_stage_summary.md
outputs\ib2d_route_risk_offline_map_v1_3b_contract_qa\_batch_summary\ib2d_v1_3b_contract_qa_tile_assignment.csv
outputs\ib2d_route_risk_offline_map_v1_3b_contract_qa\_batch_summary\ib2_ib2d_v1_3b_contract_qa_run_log.txt
```

## Decision

The v1.3b route-level baseline risk visualization checkpoint is established as clean PASS.

Before-after summary:

```text
outputs\ib2d_route_risk_offline_map_v1_3b_contract_qa\_batch_summary\zhonghua_tile_correction_before_after_summary.csv
```
