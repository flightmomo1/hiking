# IB3W Route Candidate Terrain Elevation Lookup v1 Notes

- 日期：2026-06-12
- 分支：codex/ib3w-route-candidate-terrain-elevation-lookup-v1
- 上游基底：dd6484d Add case-level NLSC tile mapping config
- 本分支範圍：針對 route-scoped weather candidate stations，使用 case-level NLSC tile mapping 與 ContourL.shp 進行 station elevation lookup
- 非本分支範圍：water station elevation lookup、neighbor tile automatic fallback、weather/hydro fusion、route risk / radar / THCI 調整

## 1. Purpose

本分支將先前的 case-level NLSC tile mapping config 接到 IB3W route-scoped weather station candidates。

流程：

    case_id
        ↓
    configs\nlsc\case_level_nlsc_tile_mapping_v1.csv
        ↓
    nlsc_tile
        ↓
    nlsc_raw/{tile}/向量25K/ContourL.shp
        ↓
    station point -> contour IDW elevation lookup

## 2. Script

新增：

    scripts\ib3_activity_environment\ib3w_lookup_route_candidate_station_elevation_v1b.py

說明：

    此腳本由 v1.py 複製並 patch 而來。
    原 v1.py 在 Windows 環境被其他 process 鎖定，因此本分支保留 v1b 作為正式提交腳本。
    v1b 加入 elevation_review_status 與 summary review counts。

## 3. Inputs

Case:

    qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b

Tile mapping:

    configs\nlsc\case_level_nlsc_tile_mapping_v1.csv

Weather candidates:

    outputs\ib3w_route_scoped_station_selection_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\weather_station_candidates.csv

Contour source:

    nlsc_raw\97233NW\向量25K\ContourL.shp

Contour elevation field:

    zv2

## 4. Command

    .\.venv\Scripts\python.exe scripts\ib3_activity_environment\ib3w_lookup_route_candidate_station_elevation_v1b.py `
      --case-id qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b `
      --tile-mapping-csv configs\nlsc\case_level_nlsc_tile_mapping_v1.csv `
      --weather-candidates-csv outputs\ib3w_route_scoped_station_selection_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\weather_station_candidates.csv `
      --nlsc-root nlsc_raw `
      --out-dir outputs\ib3w_route_candidate_terrain_elevation_lookup_v1

## 5. Outputs

Output folder:

    outputs\ib3w_route_candidate_terrain_elevation_lookup_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b

Generated files:

    weather_station_candidates_elevation_lookup.csv
    weather_station_candidates_elevation_lookup_summary.csv

Outputs are QA evidence and are not committed.

## 6. QA result

Summary:

    input_weather_candidates = 48
    output_rows = 48
    nlsc_tile = 97233NW
    elevation_lookup_ok = 48
    no_valid_contours = 0
    good_confidence = 6
    moderate_confidence = 2
    low_confidence = 40
    station_elevation_missing = 0
    acceptable = 8
    need_neighbor_tile_review = 40
    review_required = 0
    lookup_failed = 0
    zero_fallback_used = False

Review status distribution:

    ACCEPTABLE = 8
    NEED_NEIGHBOR_TILE_REVIEW = 40

## 7. Interpretation

本分支成功完成：

    route-level primary tile station elevation lookup

但結果顯示：

    48 筆 weather candidate stations 都能以 97233NW ContourL.shp 算出 station_elevation_m。
    其中只有 8 筆達 good/moderate confidence。
    另外 40 筆為 low confidence，且 nearest_contour_distance_m 大於 1000m，因此標記為 NEED_NEIGHBOR_TILE_REVIEW。

此設計避免 downstream weather/hydro fusion 將 low-confidence station elevation 誤視為同等可信。

## 8. Review status policy

v1b 新增：

    elevation_review_status

規則：

    elevation_lookup_status != ELEVATION_LOOKUP_OK
        -> LOOKUP_FAILED

    elevation_confidence in good / moderate
        -> ACCEPTABLE

    elevation_confidence = low and nearest_contour_distance_m > 1000
        -> NEED_NEIGHBOR_TILE_REVIEW

    otherwise
        -> REVIEW_REQUIRED

## 9. Boundary

本分支不宣稱所有 48 個 weather stations 的 elevation 都正式可信。

本分支只宣稱：

    1. case-level tile mapping 可成功驅動 route-level primary tile lookup。
    2. 所有 weather candidate rows 都有 station_elevation_m。
    3. review status 可正確區分可接受與需 neighbor tile review 的 rows。
    4. 未使用 zero fallback。

## 10. Next step

下一支建議：

    codex/ib3w-route-candidate-neighbor-tile-review-v1

目標：

    對 NEED_NEIGHBOR_TILE_REVIEW rows 掃描可用 NLSC tiles。
    比較 97233NW / 97233SW 或其他 available ContourL.shp。
    選 nearest_contour_distance_m 較小且 confidence 較佳者。
    仍不做 weather/hydro fusion。
