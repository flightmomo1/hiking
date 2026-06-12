# IB3W Water Candidate Elevation v1 Notes

- 日期：2026-06-12
- 分支：codex/ib3w-water-candidate-elevation-v1
- 上游基底：78edb48 Document route pipeline history and NLSC tile status
- 本分支範圍：對 route-scoped water candidates 執行 station elevation lookup、neighbor tile review 與 finalization
- 非本分支範圍：weather/hydro fusion、water observation value join、route risk / radar / THCI 調整

## 1. Purpose

本分支將前面 weather station candidate elevation 的流程套用到 water candidates。

流程：

    route-scoped water candidates
        ↓
    primary tile elevation lookup
        ↓
    neighbor tile review
        ↓
    final water station elevation table

本分支仍是 elevation evidence layer，不是 hydrology fusion。

## 2. Script

新增：

    scripts\ib3_activity_environment\ib3w_finalize_water_candidate_station_elevation_v1.py

此腳本一次完成：

    1. primary tile lookup
    2. neighbor tile review
    3. finalization

## 3. Inputs

Case:

    qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b

Water candidates:

    outputs\ib3w_route_scoped_station_selection_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\water_station_candidates.csv

Tile mapping:

    configs\nlsc\case_level_nlsc_tile_mapping_v1.csv

Available NLSC contour tiles:

    nlsc_raw\97233NW\向量25K\ContourL.shp
    nlsc_raw\97233SW\向量25K\ContourL.shp

## 4. Command

    .\.venv\Scripts\python.exe scripts\ib3_activity_environment\ib3w_finalize_water_candidate_station_elevation_v1.py `
      --case-id qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b `
      --water-candidates-csv outputs\ib3w_route_scoped_station_selection_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\water_station_candidates.csv `
      --tile-mapping-csv configs\nlsc\case_level_nlsc_tile_mapping_v1.csv `
      --nlsc-root nlsc_raw `
      --out-dir outputs\ib3w_water_candidate_elevation_v1

## 5. Outputs

Output folder:

    outputs\ib3w_water_candidate_elevation_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b

Generated files:

    water_station_candidates_elevation_lookup.csv
    water_station_candidates_neighbor_tile_review_trials.csv
    water_station_candidates_neighbor_tile_review_best.csv
    water_station_candidates_elevation_final.csv
    water_station_candidates_elevation_summary.csv

Outputs are QA evidence and are not committed.

## 6. QA result

Summary:

    water_candidate_rows = 66

    primary_acceptable = 6
    primary_need_neighbor_tile_review = 60
    primary_lookup_failed = 0

    neighbor_tile_trials = 120
    neighbor_best_rows = 60
    neighbor_tile_improved = 50

    final_rows = 66
    final_acceptable = 23
    final_low_confidence_review_required = 43
    final_review_required = 0
    final_lookup_failed = 0
    final_elevation_missing = 0
    final_review_required_total = 43

    final_good_confidence = 14
    final_moderate_confidence = 9
    final_low_confidence = 43

    final_source_primary_tile_lookup = 6
    final_source_neighbor_tile_review_recommended = 60

    final_tile_97233NW = 16
    final_tile_97233SW = 50

    zero_fallback_used = False

## 7. Interpretation

本分支完成 route-scoped water candidates 的 station elevation finalization。

結果顯示：

    66 筆 water candidate stations 全部有 final station elevation。
    23 筆達 FINAL_ACCEPTABLE。
    43 筆為 FINAL_LOW_CONFIDENCE_REVIEW_REQUIRED。
    primary tile lookup 只有 6 筆可接受。
    60 筆需要 neighbor tile review。
    neighbor tile review 改善 50 筆。
    final tile 分布為 97233NW = 16、97233SW = 50。
    未使用 zero fallback。

此結果與 weather candidate elevation 結果一致：primary route tile 不足以支撐所有候選站高程，neighbor tile review 是必要 QA step。

## 8. Boundary

本分支不宣稱 66 筆 water candidate elevation 全部同等可信。

本分支只宣稱：

    1. 所有 water candidates 均有 final elevation value。
    2. final source / final tile / final confidence / final status 已明確標記。
    3. low-confidence rows 未被偽裝成 acceptable。
    4. 未使用 zero fallback。
    5. 尚未進行 hydrology observation join 或 weather/hydro fusion。

## 9. Next step

下一支建議：

    codex/ib3w-weather-water-elevation-inventory-v1

目標：

    整理 weather candidates 與 water candidates 的 final elevation evidence。
    比較 weather / water final acceptable ratio。
    建立後續 weather/hydro context fusion 前的 evidence inventory。
    仍不做 observation join 或 fusion。
