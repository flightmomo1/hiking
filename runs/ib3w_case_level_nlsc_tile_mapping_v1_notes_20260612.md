# Case-level NLSC Tile Mapping v1 Notes

- 日期：2026-06-12
- 分支：codex/ib3w-case-level-nlsc-tile-mapping-v1
- 上游基底：3e145f7 Document IB3W case-level NLSC tile mapping evidence
- 本分支範圍：建立 case_id / route_id 對應 NLSC tile 的正式 config
- 非本分支範圍：station elevation lookup、weather/hydro fusion、route risk / radar / THCI 調整

## 1. Purpose

IB1G / IB1E 在執行 NLSC contour window terrain enrichment 時，需要正確的 NLSC tile。

先前發現：

- IB1G 主腳本有 `--tile` 與 `--contour-fp`，但不是完整自動 tile selector。
- IB1G 預設 tile 為 `97233NW`。
- 中華科大九五峰 case 曾經錯用 `97233NW`，導致 terrain lookup failure。
- archived changelog / handoff 已記錄中華科大九五峰應使用 `97233SW`。
- 因此需要把 case-level NLSC tile mapping 從歷史文件提升成正式 config。

## 2. New config

新增：

    configs\nlsc\case_level_nlsc_tile_mapping_v1.csv

欄位：

    case_id
    route_family
    nlsc_tile
    contour_relative_path
    tile_source
    tile_status
    notes

## 3. Known mappings

目前納入：

    qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b -> 97233NW
    qixing_lengshuikeng_xiaoyoukeng_gpx_osmrefresh_v1_3b -> 97233NW
    qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b -> 97233NW
    juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b -> 97233NW
    zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b -> 97233SW

## 4. Zhonghua correction

中華科大九五峰 case 的正式 tile 是：

    97233SW

不是：

    97233NW

錯用 `97233NW` 的 evidence：

    elev_min = null
    elev_max = null
    elev_range = null
    slope_window = null
    slope_band_window = unknown
    contour_density_20m = 0

因此本 config 將中華科大標記為：

    tile_status = CONFIRMED_CORRECTED
    tile_source = archived_changelog_handoff_correction

## 5. Downstream use

此 config 後續應供以下流程共用：

    IB1G contour window feature computation
    IB1E route profile terrain enrichment
    IB3W route candidate station terrain elevation lookup

IB3W station elevation lookup 應先讀此 mapping：

    case_id / route_id
        ↓
    nlsc_tile
        ↓
    nlsc_raw/{tile}/向量25K/ContourL.shp
        ↓
    station point IDW elevation lookup

若 station 不在該 tile bounds 或查無有效 contours，才進入 neighbor tile / contour inventory fallback。

## 6. Boundary

本 config 不是 weather/hydro context result。

它只定義：

    route case -> NLSC contour tile

不得在本層推論：

    rainfall
    wind
    temperature
    water level
    route risk score
    radar score
    THCI score

## 7. Next step

下一支建議：

    codex/ib3w-route-candidate-terrain-elevation-lookup-v1

該分支可讀取本 config，並把 route-scoped weather/water station candidates 補上 terrain elevation。
