# IB3W Route-Scoped Station Selection / Terrain Elevation Lookup v1 Notes

- 日期：2026-06-12
- 分支：codex/ib3w-station-terrain-elevation-lookup-v1
- 上游基底：af2b1da Add IB3W station metadata elevation audit
- 本分支範圍：route-scoped station selection design, station terrain elevation lookup positioning, qixing 9-station prototype interpretation
- 非本分支範圍：正式 1483 station DEM/NLSC lookup、station ranking 改寫、formal weather adapter、row-level weather join、imputation、route risk / radar / THCI 調整

## 1. 背景

上一分支建立 station metadata elevation cache，確認：

    station_rows = 1483
    db_elevation_available_rows = 0
    need_terrain_lookup_rows = 1483

這代表 weather / water DB 目前有測站座標，但沒有可直接使用的 DB elevation。

原先下一步直覺是對 1483 筆 station 做 terrain elevation lookup。

但重新釐清需求後，正式 pipeline 不應直接把 1483 個全域測站全部拿去做天候融合。

使用者原始設計是：

    根據匯入的路段，選出相對應測站，再做天候資料融合運算。

因此，qixing 只抓到 9 個 weather stations 並不是錯，而是 route-scoped station candidate set 的 prototype。

## 2. 核心修正

IB3W 應拆成兩層：

### 2.1 Global station registry

全域測站庫：

    weather stations
    water stations
    station_id
    station_name
    station_type
    source
    latitude
    longitude
    station_elevation_m
    station_elevation_source
    source/variable availability

這一層可包含 1483 station rows。

用途：

    station metadata cache
    不直接做 route weather fusion
    不代表每條路線都要使用全部 1483 stations

### 2.2 Route-scoped station candidates

路線選站層：

    imported route
        ↓
    route geometry / route corridor
        ↓
    route buffer
        ↓
    candidate station search
        ↓
    route-specific candidate ranking

用途：

    每條匯入路線產生自己的 weather / hydro candidate station set

例如：

    qixing route -> 9 weather stations
    another route -> another station candidate set

## 3. 舊 qixing 9-station prototype 的正確定位

本輪 discovery 找到：

    outputs\ib3_environment_output\qixing_weather_station_elevation_from_nslc.csv
    outputs\ib3_environment_output\actual_gpx_9stations\qixing_weather_station_elevation_from_nslc.csv
    outputs\ib3_environment_output\scenario_0430_9stations\qixing_weather_station_elevation_from_nslc.csv

其中 main copy 與 actual_gpx_9stations copy hash 相同。

主要檔案欄位包含：

    station_id
    station_name
    station_lat
    station_lon
    dist_to_route_center_km
    station_quadrant
    station_elevation_m
    elevation_source
    elevation_confidence
    elevation_search_radius_m
    n_contours_used
    nearest_contour_distance_m
    nearest_contour_elevation_m
    contour_elevation_min_m
    contour_elevation_max_m
    contour_elevation_std_m
    contour_shp
    contour_elevation_field

範例：

    466930 陽明山 station_elevation_m = 609.6678201514454
    466910 鞍部 station_elevation_m = 839.7501276913617
    C0AC40 大屯山 station_elevation_m = 1079.728443331852
    A0A460 文化大學 station_elevation_m = 399.92819274875615
    C0AH40 平等 station_elevation_m = 404.91372549578614

elevation_source：

    nslc_contour_idw

判斷：

    這不是錯誤的 9 station cache。
    它是 route-scoped station candidate + elevation prototype。
    它不能當成 full global station elevation cache。
    它可以回收為 route-scoped station selection 的設計依據。

## 4. 不應把 qixing 9 stations 當成全域 station cache

qixing_weather_station_elevation_from_nslc.csv 不能直接作為 formal IB3W station registry，原因：

- 僅涵蓋七星山附近 weather stations。
- 約 9 筆 station，不涵蓋 1483 station metadata cache。
- 不涵蓋 full water stations。
- contour_shp 使用 user-local absolute path：
    /Users/iddmini/Documents/...
- 尚未處理任意匯入路線。
- 尚未處理多圖幅 selection。
- 尚未定義 portable terrain source path。
- 尚未定義 formal candidate ranking rule。

## 5. 正式 pipeline 修正版

建議 IB3W pipeline 修正為：

    Route import
        ↓
    IB0 / IB1 route standardization
        ↓
    IB1E / IB1G route terrain profile
        ↓
    IB3W-S0 Global station registry with terrain elevation
        ↓
    IB3W-S1 Route-scoped station candidate selection
        ↓
    IB3W-S2 Weather / hydro temporal coverage
        ↓
    IB3W-S3 Variable-level context fusion
        ↓
    IB3W-S4 Activity-level / route-level weather context summary
        ↓
    IB3M or future decision layer

## 6. Global station registry 的角色

Global station registry 應該做：

- 整理全域 weather/water station metadata。
- 補 station terrain elevation。
- 維護 station source / variable availability。
- 提供後續 route-scoped selection 查詢。

Global station registry 不應該做：

- 對單一路線做天候融合。
- 將全部 1483 station 丟進 route fusion。
- 根據單一路線直接調整 route risk / radar / THCI。

## 7. Route-scoped station selection 的角色

Route-scoped station selection 應該做：

- 依匯入路線 geometry 選站。
- 依 route buffer 找附近測站。
- 計算 distance_to_route_m。
- 計算 nearest_route_km。
- 計算 route_nearest_elevation_m。
- 計算 elevation_delta_m。
- 分 weather / hydro station_type 分別排序。
- 保留 candidate_rank / candidate_role。
- 輸出 route-specific station candidate set。

輸出例：

    outputs/ib3w_route_station_candidates_v1/{route_id}/weather_station_candidates.csv
    outputs/ib3w_route_station_candidates_v1/{route_id}/water_station_candidates.csv

## 8. Weather / hydro fusion 的角色

Weather / hydro fusion 應只使用 route-scoped station candidates。

不應直接吃全台 1483 station registry。

不同變數應有不同融合邏輯：

### temperature

可考慮：

- distance_to_route_m
- elevation_delta_m
- temporal coverage
- variable coverage

### wind_speed

可考慮：

- distance_to_route_m
- station elevation
- route exposure
- ridge / open terrain context
- temporal coverage

### precipitation_1hr

可考慮：

- distance_to_route_m
- rain station availability
- temporal coverage
- spatial coverage

注意：

    missing rainfall 不可補 0 mm。

### water_level

不可只靠直線距離。

後續應考慮：

- watershed / river system relation
- drainage basin
- downstream/upstream relation
- station type

## 9. 新增 policy

新增：

    configs/weather_context/ib3w_route_scoped_station_selection_policy_v1.csv

目的：

- 明確區分 global station registry 與 route-scoped candidate set。
- 定義 route-scoped station selection 欄位。
- 明確記錄 qixing 9-station prototype 的定位。
- 固化「weather/hydro fusion 使用 route-scoped candidates，不直接使用全部 1483 stations」的設計原則。

## 10. 本分支結論

本分支結論：

    1. 使用者原始設計方向正確。
    2. qixing 9 stations 是 route-scoped candidate prototype，不是錯誤。
    3. 1483 station metadata cache 是 global station registry，不應直接全部丟進 fusion。
    4. 正式 IB3W 應增加 route-scoped station selection layer。
    5. station terrain elevation lookup 應支援 global registry，也應供 route-scoped candidate ranking 使用。
    6. weather/hydro fusion 應針對 route-specific candidate set 執行。
    7. 目前分支先完成 design / policy，不新增半套 lookup script。

## 11. 下一步建議

下一段建議：

    codex/ib3w-route-scoped-station-selection-v1

範圍：

- 讀取 station registry metadata cache。
- 讀取指定 route geometry / route profile。
- 對 route buffer 內 station 做候選選取。
- 產出 route-specific weather/water station candidate CSV。
- 先不做 weather fusion。
- 先不改 formal adapter。
- 不改 route risk / radar / THCI。

再下一段：

    codex/ib3w-weather-hydro-context-fusion-v1

範圍：

- 使用 route-scoped candidates。
- 執行 weather/hydro temporal + variable context fusion。
- 保留 no-zero-fallback rule。
