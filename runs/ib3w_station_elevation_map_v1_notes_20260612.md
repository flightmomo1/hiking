# IB3W Station Elevation 1D/2D Map v1 Notes

- 日期：2026-06-12
- 分支：codex/ib3w-station-elevation-map-v1
- 上游基底：933bdf5 Document IB3W weather and water elevation inventory
- 本分支範圍：將 weather / water candidate station elevation final evidence 繪製為 1D + 2D HTML report
- 非本分支範圍：weather/hydro observation join、weather/hydro fusion、route risk / radar / THCI 調整

## 1. Purpose

本分支產出 route-scoped station elevation evidence 的視覺化檢查圖。

目的：

1. 在 1D route distance axis 上檢查 station elevation 與 route profile 的相對位置。
2. 在 2D map 上檢查 weather / water station 空間分布。
3. 顯示 station-to-route connector，協助判斷候選站是否離路線過遠。
4. 顯示 final status / final confidence / final NLSC tile，避免 low-confidence station elevation 被誤用。

## 2. Script

新增：

    scripts\ib3_activity_environment\ib3w_plot_station_elevation_1d_2d_html_v1.py

## 3. Inputs

Case:

    qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b

Route profile:

    outputs\ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b_route_profile_contour_window_terrain_enriched.csv

Weather final elevation:

    outputs\ib3w_route_candidate_elevation_finalize_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\weather_station_candidates_elevation_final.csv

Water final elevation:

    outputs\ib3w_water_candidate_elevation_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\water_station_candidates_elevation_final.csv

## 4. Outputs

Output folder:

    outputs\ib3w_station_elevation_map_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b

Generated files:

    station_elevation_1d_2d_report.html
    station_elevation_plot_data.csv
    station_elevation_map_summary.csv

Outputs are visual QA artifacts and are not committed.

## 5. QA result

Summary:

    route_rows = 4189
    station_rows = 114
    weather_rows = 48
    water_rows = 66
    final_acceptable = 42
    final_low_confidence_review_required = 72
    tile_97233NW = 36
    tile_97233SW = 78
    zero_fallback_used = False

## 6. Visualization design

1D panel:

- X axis: route distance
- Y axis: elevation
- Route line: IB1E route elevation profile
- Weather stations: circle markers
- Water stations: square markers
- Marker color: elevation_final_status

2D panel:

- Route polyline
- Weather station points
- Water station points
- Station-to-route connector lines
- Nearest route projection points
- Tooltip fields:
  - station_id
  - station_name
  - station_group
  - nearest_route_km
  - distance_to_route_m
  - station_elevation_m_final
  - elevation_final_status
  - elevation_final_confidence
  - elevation_final_nlsc_tile
  - elevation_final_source

## 7. Interpretation

本分支完成 weather / water station elevation evidence 的 1D + 2D visual QA。

此圖可協助辨識：

1. 哪些測站距離路線過遠。
2. 哪些測站雖然有 final elevation，但仍為 low-confidence。
3. 哪些測站 final tile 被切到 97233SW。
4. weather / water candidate 是否過度集中在台北盆地側。
5. station elevation evidence 是否適合作為後續 fusion context。

## 8. Boundary

本分支只做視覺化與 QA。

本分支不做：

- weather observation join
- hydrology observation join
- weather/hydro fusion
- route risk recalculation
- radar / THCI adjustment
- missing weather / hydro imputation

本分支不宣稱：

    low-confidence station elevation 可以作為同等可信 evidence。

## 9. Note

HTML 內嵌 1D SVG 與 station/route data。  
2D map 使用 Leaflet 與 OpenStreetMap tile，因此開啟 HTML 時若要顯示底圖需有網路連線；即使無網路，1D 圖與嵌入資料仍可檢視。
