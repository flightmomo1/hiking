# IB3W Reuse IB1G NLSC Tile / Contour Source v1 Notes

- 日期：2026-06-12
- 分支：codex/ib3w-reuse-ib1g-nlsc-tile-selector-v1
- 上游基底：76016ad Add IB3W route-scoped station elevation join
- 本分支範圍：盤點 IB1G/IB1E/IB3B3 既有 NLSC contour source 與 station elevation lookup 機制
- 非本分支範圍：正式 station terrain elevation lookup、weather/hydro fusion、temporal coverage、variable coverage、formal adapter、route risk / radar / THCI 調整

## 1. 背景

目前 IB3W 已完成：

    global station registry
        ↓
    route-scoped station selection
        ↓
    qixing weather station prototype elevation join

但只有舊 qixing prototype 中的 9 個 weather stations 有 station elevation。

使用者指出：

    其他測站應先判斷隸屬 NLSC 哪個圖號，
    再依該圖號的等高線資料補測站高程。

同時，IB1G / IB1E 在 route profile terrain enrichment 時，應已經有 NLSC contour source 使用機制。

本分支因此先盤點既有腳本，不重新發明 tile selector。

## 2. Relevant scripts

本輪搜尋找到三組相關腳本。

### 2.1 IB1G / IB1E contour window terrain

主要腳本：

    scripts\ib1_nlsc_terrain\ib1g_v2_compute_contour_window_features_cli_updated.py
    scripts\ib1_nlsc_terrain\ib1e_enrich_route_profile_with_contour_window_terrain_cli_updated.py

IB1G 用途：

    compute NLSC contour window terrain features along an ib0d trimmed mainline

IB1G 目前有：

    --tile
    --contour-fp
    --segment-len-m
    --window-radius-m
    --density-buffer-m

IB1G 預設：

    --tile 97233NW

若未提供 --contour-fp，會組成：

    PROJECT_ROOT\nlsc_raw\{tile}\向量25K\ContourL.shp

也就是：

    nlsc_raw/{tile}/向量25K/ContourL.shp

## 3. IB1G finding

IB1G 目前不是完整自動 tile selector。

較精準定位是：

    IB1G is a route contour-window computation tool with a tile/contour-fp input contract.

它支援：

    1. 使用 --tile 指定 NLSC tile。
    2. 使用 --contour-fp 直接指定 contour shapefile。
    3. 使用 project-relative nlsc_raw/{tile}/向量25K/ContourL.shp 作為預設 contour source。
    4. 將輸出記錄 nlsc_tile、contour_fp、elevation_source = nlsc_contour_window。

它尚未在此腳本中完成：

    station lat/lon -> tile id
    arbitrary point -> tile id
    multi-tile automatic lookup
    tile candidate scoring

因此 IB3W 不應直接假設 IB1G 已有完整 station tile selector。

## 4. IB3B3 station elevation prototype

主要腳本：

    scripts\ib3_activity_environment\ib3b3_estimate_station_elevation_from_nslc_contours.py

此腳本應是舊 qixing station elevation prototype 的來源或近親。

它目前包含 station point elevation lookup 的核心演算法。

### 4.1 Hard-coded prototype limitation

IB3B3 目前有硬寫：

    BASE_DIR = /Users/iddmini/Documents/115_Motion改造/FY115_登山/115_osm
    PROJECT_ROOT = /Users/iddmini/Documents/115_Motion改造/FY115_登山
    CONTOUR_SHP_PATH = .../圖檔/97233NW/向量25K/ContourL.shp

因此它不是正式可攜 Windows pipeline script。

### 4.2 Useful reusable logic

IB3B3 已有可回收邏輯：

    station lat/lon 欄位偵測
    contour shapefile discovery
    contour elevation field detection
    CRS fallback
    station point GeoDataFrame conversion
    contour loading
    IDW elevation estimation
    confidence rule
    provenance output

設定：

    DEFAULT_CONTOUR_CRS_IF_MISSING = EPSG:3826
    TARGET_METRIC_CRS = EPSG:3826
    SEARCH_RADII_M = [500, 1000, 2000, 5000]
    MAX_CONTOURS_USED = 12
    MIN_CONTOURS_REQUIRED = 2
    IDW_POWER = 2.0
    MIN_DISTANCE_M = 1.0
    ELEVATION_CONFIDENCE_GOOD_DISTANCE_M = 300
    ELEVATION_CONFIDENCE_OK_DISTANCE_M = 1000

輸出欄位：

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

## 5. Contract decision

正式 IB3W station terrain elevation lookup 應該複用：

    IB1G contour source path contract
        nlsc_raw/{tile}/向量25K/ContourL.shp

以及：

    IB3B3 station point IDW elevation algorithm

但不應複用 IB3B3 的：

    hard-coded Mac path
    fixed 97233NW
    scenario-specific qixing_weather_summary_by_station.csv
    fixed output under ib3_environment_output

## 6. Required missing layer

目前缺的是：

    route candidate station -> NLSC contour tile/source selection wrapper

也就是：

    route-scoped weather/water candidates
        ↓
    station lat/lon
        ↓
    candidate ContourL.shp inventory
        ↓
    select matching or nearest valid contour source
        ↓
    apply IB3B3 IDW elevation algorithm
        ↓
    output station_elevation_m and provenance

此 wrapper 不應直接寫死 97233NW。

## 7. Recommended next branch

下一段建議：

    codex/ib3w-route-candidate-terrain-elevation-lookup-v1

範圍：

- 讀取 route-scoped weather candidates。
- 讀取 route-scoped water candidates。
- 建立或讀取 nlsc_raw ContourL.shp inventory。
- 對每個 candidate station 選 contour source。
- 套用 IB3B3 IDW 演算法。
- 輸出 weather/water candidate elevation lookup result。
- 不做 weather/hydro fusion。
- 不改 route risk / radar / THCI。

## 8. Implementation recommendation

正式 lookup script 應設計為：

    scripts\ib3_activity_environment\ib3w_lookup_route_candidate_station_elevation_v1.py

建議 CLI：

    --weather-candidates-csv
    --water-candidates-csv
    --nlsc-root
    --route-id
    --out-dir
    --max-search-radius-m

其中：

    --nlsc-root 預設可為 nlsc_raw

Contour source discovery：

    {nlsc-root}\*\向量25K\ContourL.shp

station lookup rule v1：

    1. 先找 station 點位落在 contour layer total_bounds 內的 tile。
    2. 若多 tile 命中，選 nearest contour distance 最小者。
    3. 若無 tile bounds 命中，可用 route tile fallback 或 nearest tile fallback，但需標記 FALLBACK_TILE。
    4. 若沒有 ContourL.shp，標記 TILE_NOT_FOUND。
    5. 若 ContourL.shp 無有效高程欄位，標記 NO_ELEVATION_FIELD。
    6. 若 IDW 找不到有效 contours，標記 LOOKUP_FAILED。

Status 建議：

    ELEVATION_LOOKUP_OK
    TILE_NOT_FOUND
    OUTSIDE_TILE_BOUNDS
    NO_ELEVATION_FIELD
    NO_VALID_CONTOURS
    LOOKUP_FAILED

## 9. Conclusion

本分支確認：

    1. IB1G 有 tile / contour-fp input contract，但不是完整 station tile selector。
    2. IB1G 正式 contour source path 是 nlsc_raw/{tile}/向量25K/ContourL.shp。
    3. IB3B3 已有 station point -> contour IDW elevation algorithm。
    4. IB3B3 目前是 qixing prototype，不是正式 pipeline script。
    5. IB3W 應新增 route-candidate station terrain elevation lookup wrapper。
    6. 下一步應針對 route candidates 補 weather/water station elevation，再進 weather/hydro fusion。
