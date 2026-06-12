# IB3W Missing NLSC Tile Diagnosis v1 Notes

- 日期：2026-06-12
- 分支：codex/ib3w-missing-nlsc-tile-diagnosis-v1
- 上游基底：313c6cc Document IB3W station weather role policy
- 本分支範圍：診斷 station elevation low-confidence rows 是否可能受 NLSC tile coverage 影響
- 非本分支範圍：重新 elevation lookup、weather/hydro fusion、route risk / radar / THCI 調整

## 1. Purpose

本分支診斷 IB3W station elevation low-confidence rows 是否可能是 NLSC 圖幅覆蓋不足或舊結果未重跑造成。

前一版 station elevation map 中共有：

    station_rows = 114
    low_confidence_rows = 72

## 2. Script

新增：

    scripts\ib3_activity_environment\ib3w_diagnose_missing_nlsc_tiles_v1.py

## 3. Inputs

Case:

    qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b

Station plot CSV:

    outputs\ib3w_station_elevation_map_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\station_elevation_plot_data.csv

NLSC root:

    nlsc_raw

## 4. Current NLSC tiles

目前本機 nlsc_raw 已包含：

    97233NE
    97233NW
    97233SE
    97233SW

這表示 97233 東半側圖幅已補齊。

## 5. Diagnosis result

Low-confidence rows:

    72

Coordinate extent:

    lat_min = 24.987386
    lat_max = 25.283129
    lon_min = 121.403946
    lon_max = 121.740806

Station group:

    water = 43
    weather = 29

Current final tile in old output:

    97233NW = 22
    97233SW = 50

Longitude region:

    WEST_SIDE_OR_BASIN_WEST = 34
    CENTRAL_97233_CORRIDOR = 9
    EAST_SIDE_CANDIDATE_97233E = 17
    FAR_EAST_KEELUNG_REVIEW = 12

Latitude region:

    SOUTH_BASIN = 13
    CENTRAL_BASIN_YANGMINGSHAN_EDGE = 44
    NORTH_COAST_EDGE = 11
    FAR_NORTH_COAST_REVIEW = 4

Diagnosis flags:

    LOW_CONFIDENCE_NOT_EXPLAINED_BY_PRIMARY_TILE_GAP = 56
    SUSPECT_EAST_NEIGHBOR_REVIEW_AFTER_PRIMARY_TILES = 12
    SUSPECT_NORTH_NEIGHBOR_REVIEW_AFTER_PRIMARY_TILES = 4

## 6. Interpretation

目前 station_elevation_plot_data.csv 仍反映舊的 station elevation finalization 結果。

雖然目前 nlsc_raw 已有 97233NE/NW/SE/SW 四張圖，但舊 finalization 很可能只基於早期可用圖幅或舊的 neighbor review 結果。

因此，72 筆 low-confidence 不應直接被當成 station low relevance。更合理的下一步是重新執行 station elevation lookup / neighbor tile review / finalization，讓 97233NE 與 97233SE 真的參與計算。

## 7. Recommended next branch

建議下一支：

    codex/ib3w-rerun-station-elevation-with-expanded-nlsc-tiles-v1

目標：

    重新以 97233NE / 97233NW / 97233SE / 97233SW 四張圖幅執行 weather/water station elevation review。
    重新產出 weather / water final elevation outputs。
    再重新產出 station elevation 1D/2D map。
    比較 rerun 前後 low-confidence rows 是否下降。

## 8. Boundary

本分支只做診斷，不做：

    - 新 elevation lookup
    - weather observation join
    - hydrology observation join
    - weather/hydro fusion
    - route risk recalculation
    - radar / THCI adjustment
    - missing value imputation

Zero fallback:

    False
