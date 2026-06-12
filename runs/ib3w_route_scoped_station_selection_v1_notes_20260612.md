# IB3W Route-Scoped Station Selection v1 Notes

- 日期：2026-06-12
- 分支：codex/ib3w-route-scoped-station-selection-v1
- 上游基底：da7b7a3 Document IB3W route-scoped station selection design
- 本分支範圍：route-scoped weather/water station candidate selection
- 非本分支範圍：weather/hydro fusion、temporal coverage、variable coverage、formal adapter、route risk / radar / THCI 調整

## 1. 本分支目的

前一分支已定義 IB3W 應區分：

    global station registry
    route-scoped station candidates

本分支實作第一版 route-scoped station candidate selection。

目標：

- 讀取 global station metadata cache。
- 讀取指定 route profile / route terrain source。
- 計算 station 到 route 的最近距離。
- 取得 nearest_route_km。
- 取得 route_nearest_elevation_m。
- 分 weather / water station 輸出候選清單。
- 不做 weather/hydro fusion。
- 不做 temporal coverage。
- 不改 route risk / radar / THCI。

## 2. 新增腳本

新增：

    scripts/ib3_activity_environment/ib3w_select_route_scoped_station_candidates_v1.py

腳本功能：

- 讀取 station registry CSV。
- 讀取 IB1E route profile enriched CSV。
- 使用 route sampled lat/lon points 作為 route geometry。
- 使用 haversine distance 計算 station 到 route sampled points 的最近距離。
- 取得 nearest route point。
- 輸出：
    - weather_station_candidates.csv
    - water_station_candidates.csv
    - route_station_candidates_all.csv
    - route_station_candidate_summary.csv
    - route_station_candidate_summary.html

## 3. Input

Station registry：

    outputs\ib3w_station_metadata_elevation_v1\ib3w_station_metadata_elevation_v1.csv

Route source：

    outputs\ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b_route_profile_contour_window_terrain_enriched.csv

Route source 已確認欄位：

    case_id
    case_name
    sample_idx
    dist_m
    lat
    lon
    ele_smooth
    elevation_source
    profile_dist_m
    elev_min_nlsc_window
    elev_max_nlsc_window
    terrain_dist_mid_m
    terrain_elevation_source
    contour_window_match_status

Station registry 已確認欄位：

    source
    station_type
    dataset_code
    station_id
    station_name
    latitude
    longitude
    terrain_lookup_elevation_m
    elevation_lookup_status
    needs_terrain_lookup

## 4. Candidate role rule

v1 使用簡單 rank rule：

    rank <= 3      primary
    rank 4-10      secondary
    rank 11-20     fallback
    rank > 20      excluded

Ranking key：

    station_type
    distance_to_route_m
    station_id
    metadata_source_table

## 5. QA command

執行命令：

    $stationCsv = "outputs\ib3w_station_metadata_elevation_v1\ib3w_station_metadata_elevation_v1.csv"
    $routeCsv = "outputs\ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b_route_profile_contour_window_terrain_enriched.csv"

    .\.venv\Scripts\python.exe scripts\ib3_activity_environment\ib3w_select_route_scoped_station_candidates_v1.py `
      --station-registry-csv $stationCsv `
      --route-profile-csv $routeCsv `
      --route-id qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b `
      --max-distance-m 20000 `
      --out-dir outputs\ib3w_route_scoped_station_selection_v1

## 6. QA outputs

輸出：

    outputs\ib3w_route_scoped_station_selection_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\weather_station_candidates.csv
    outputs\ib3w_route_scoped_station_selection_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\water_station_candidates.csv
    outputs\ib3w_route_scoped_station_selection_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\route_station_candidates_all.csv
    outputs\ib3w_route_scoped_station_selection_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\route_station_candidate_summary.csv
    outputs\ib3w_route_scoped_station_selection_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\route_station_candidate_summary.html

outputs 僅作 QA，不 commit。

## 7. QA 結果

執行結果：

    route_points = 4189
    station_rows = 1483
    candidate_rows = 114
    weather_candidates = 48
    water_candidates = 66

Summary：

    water primary = 3
    water secondary = 7
    water fallback = 10
    water excluded = 46

    weather primary = 3
    weather secondary = 7
    weather fallback = 10
    weather excluded = 28

## 8. Weather candidates

Weather primary：

    1 466930 陽明山 distance_to_route_m = 1301.0108617245264
    2 466910 鞍部 distance_to_route_m = 2728.571459100834
    3 C0AC40 大屯山 distance_to_route_m = 3172.350600929062

Weather secondary includes：

    A0A460 文化大學
    C0AH40 平等
    C0A9C0 天母
    C0A870 五指山
    C0A860 大坪
    C0AI40 石牌
    C0A770 科教館

此結果可重現舊 qixing 9-station prototype 的核心 weather station set。

## 9. Water candidates

Water primary：

    1 1140H179 磺溪橋_北 distance_to_route_m = 6031.95846517841
    2 1140H180 中和橋_北 distance_to_route_m = 6276.44904801149
    3 1140H177 婆婆橋_北 distance_to_route_m = 6451.329844221528

Water secondary includes：

    1140H175 薇閣_北
    1140H162 三和橋
    1010H001 金山
    1140H181 望星橋_北
    1140H074 洲美(2)
    1140H077 大直橋
    1010H006 新磺溪橋(即時)

## 10. Known limitations

v1 limitations：

- 使用 route sampled points，而非 true polyline segment distance。
- 尚未做 station duplicate resolution。
- 尚未使用 station terrain elevation。
- elevation_delta_m 皆無法計算。
- station_elevation_status 目前為 MISSING。
- elevation_delta_status 目前為 STATION_ELEVATION_MISSING。
- 尚未做 temporal coverage。
- 尚未做 variable coverage。
- 尚未做 hydro watershed / river-system relation。
- 尚未做 weather/hydro fusion。

這些限制是刻意保留，避免本分支變成半套 fusion。

## 11. 結論

本分支成功驗證：

    global station registry 1483 rows
        ↓
    route-scoped selection for qixing_lengshuikeng
        ↓
    114 candidate rows within 20 km
        ↓
    weather 48 candidates
    water 66 candidates

這證明正式 pipeline 應該保留：

    global station registry
    route-scoped station selection
    weather/hydro fusion

三層分離。

下一段建議：

    codex/ib3w-route-scoped-station-selection-elevation-join-v1

範圍：

- 回收 qixing_weather_station_elevation_from_nslc.csv 的 station_elevation_m。
- 先針對 weather candidates join station elevation。
- 計算 elevation_delta_m。
- 不做 weather fusion。
