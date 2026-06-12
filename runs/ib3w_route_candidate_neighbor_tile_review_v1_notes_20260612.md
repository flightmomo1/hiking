# IB3W Route Candidate Neighbor Tile Review v1 Notes

- 日期：2026-06-12
- 分支：codex/ib3w-route-candidate-neighbor-tile-review-v1
- 上游基底：5ad3f03 Add IB3W route candidate terrain elevation lookup
- 本分支範圍：針對上一支標記為 NEED_NEIGHBOR_TILE_REVIEW 的 weather candidate stations，掃描可用 NLSC ContourL.shp tiles 並比較 station elevation lookup quality
- 非本分支範圍：water station elevation lookup、正式 station elevation merge、weather/hydro fusion、route risk / radar / THCI 調整

## 1. Purpose

上一支分支完成 route-level primary tile elevation lookup，但 48 個 weather candidates 中有 40 個被標記為：

    NEED_NEIGHBOR_TILE_REVIEW

原因是 primary tile 97233NW 的 nearest_contour_distance_m 過大，雖然能算出 station_elevation_m，但可信度偏低。

本分支針對這 40 筆進行 neighbor tile review。

## 2. Script

新增：

    scripts\ib3_activity_environment\ib3w_review_neighbor_tile_station_elevation_v1.py

此腳本讀取上一支輸出的：

    outputs\ib3w_route_candidate_terrain_elevation_lookup_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\weather_station_candidates_elevation_lookup.csv

並篩選：

    elevation_review_status = NEED_NEIGHBOR_TILE_REVIEW

再掃描：

    nlsc_raw\*\向量25K\ContourL.shp

目前可用 tiles：

    97233NW
    97233SW

## 3. Method

對每一個待 review 的 station candidate：

    station point
        ×
    each available NLSC tile ContourL.shp
        ↓
    contour IDW elevation lookup
        ↓
    compare confidence and nearest_contour_distance_m

選擇規則：

    1. ELEVATION_LOOKUP_OK 優先
    2. confidence rank 較高者優先
       good > moderate > low > none
    3. nearest_contour_distance_m 較小者優先

## 4. Command

    .\.venv\Scripts\python.exe scripts\ib3_activity_environment\ib3w_review_neighbor_tile_station_elevation_v1.py `
      --case-id qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b `
      --input-csv outputs\ib3w_route_candidate_terrain_elevation_lookup_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\weather_station_candidates_elevation_lookup.csv `
      --nlsc-root nlsc_raw `
      --out-dir outputs\ib3w_route_candidate_neighbor_tile_review_v1

## 5. Outputs

Output folder:

    outputs\ib3w_route_candidate_neighbor_tile_review_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b

Generated files:

    weather_station_candidates_neighbor_tile_review_trials.csv
    weather_station_candidates_neighbor_tile_review_best.csv
    weather_station_candidates_neighbor_tile_review_summary.csv

Outputs are QA evidence and are not committed.

## 6. QA result

Summary:

    input_rows = 48
    review_status_filter = NEED_NEIGHBOR_TILE_REVIEW
    review_rows = 40
    available_tile_count = 2
    tile_trials = 80
    best_rows = 40
    neighbor_tile_improved = 31
    primary_tile_remains_best_or_tied = 9
    best_good_confidence = 6
    best_moderate_confidence = 5
    best_low_confidence = 29
    best_missing_elevation = 0
    zero_fallback_used = False
    tiles_scanned = 97233NW|97233SW

Recommended tile distribution:

    97233SW = 28
    97233NW = 12

Review result distribution:

    NEIGHBOR_TILE_IMPROVED = 31
    PRIMARY_TILE_REMAINS_BEST_OR_TIED = 9

Recommended confidence distribution:

    good = 6
    moderate = 5
    low = 29

## 7. Interpretation

本分支證實：

    Primary tile-only station elevation lookup 不足以支撐所有 route-scoped weather station candidates。

在 40 筆 NEED_NEIGHBOR_TILE_REVIEW rows 中：

    31 筆透過 neighbor tile review 找到更佳 tile result。
    28 筆最終推薦 97233SW。
    12 筆仍推薦 97233NW。
    11 筆可提升至 good/moderate confidence。
    29 筆仍維持 low confidence。

這表示 neighbor tile review 可以顯著改善 station elevation lookup，但仍需要保留 confidence gate，避免 downstream weather/hydro fusion 將 low-confidence elevation 視為正式可信高程。

## 8. Boundary

本分支只做 review 與 best tile recommendation。

本分支不覆蓋上一支 primary tile lookup output。
本分支不產出正式 station elevation final table。
本分支不做 weather/hydro fusion。
本分支不調整 route risk、radar 或 THCI。
本分支未使用 zero fallback。

## 9. Next step

下一支建議：

    codex/ib3w-route-candidate-elevation-finalize-v1

目標：

    合併 primary tile lookup 與 neighbor tile review。
    產出 weather_station_candidates_elevation_final.csv。
    對 ACCEPTABLE rows 保留 primary result。
    對 NEED_NEIGHBOR_TILE_REVIEW rows 採用 neighbor review recommended result。
    仍保留 elevation_confidence 與 elevation_final_status。
    仍不做 weather/hydro fusion。
