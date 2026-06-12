# IB3W Route Candidate Elevation Finalize v1 Notes

- 日期：2026-06-12
- 分支：codex/ib3w-route-candidate-elevation-finalize-v1
- 上游基底：3ce06bb Add IB3W neighbor tile station elevation review
- 本分支範圍：合併 primary tile lookup 與 neighbor tile review，產出 weather station candidate elevation final table
- 非本分支範圍：water station elevation finalization、weather/hydro fusion、route risk / radar / THCI 調整

## 1. Purpose

本分支將前兩支的 station elevation evidence 收斂成 final candidate elevation table。

上游 evidence：

    1. Primary tile lookup
       outputs\ib3w_route_candidate_terrain_elevation_lookup_v1\...\weather_station_candidates_elevation_lookup.csv

    2. Neighbor tile review
       outputs\ib3w_route_candidate_neighbor_tile_review_v1\...\weather_station_candidates_neighbor_tile_review_best.csv

本分支產出：

    outputs\ib3w_route_candidate_elevation_finalize_v1\...\weather_station_candidates_elevation_final.csv

## 2. Script

新增：

    scripts\ib3_activity_environment\ib3w_finalize_route_candidate_station_elevation_v1.py

## 3. Finalization rule

Primary lookup rows:

    elevation_review_status = ACCEPTABLE
        -> 使用 primary tile lookup result

Neighbor review rows:

    elevation_review_status = NEED_NEIGHBOR_TILE_REVIEW
        -> 使用 neighbor tile review recommended result

Final status rule:

    final confidence in good / moderate
        -> FINAL_ACCEPTABLE

    final confidence = low
        -> FINAL_LOW_CONFIDENCE_REVIEW_REQUIRED

    lookup failed
        -> FINAL_LOOKUP_FAILED

    elevation missing
        -> FINAL_ELEVATION_MISSING

## 4. Command

    .\.venv\Scripts\python.exe scripts\ib3_activity_environment\ib3w_finalize_route_candidate_station_elevation_v1.py `
      --case-id qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b `
      --primary-csv outputs\ib3w_route_candidate_terrain_elevation_lookup_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\weather_station_candidates_elevation_lookup.csv `
      --neighbor-best-csv outputs\ib3w_route_candidate_neighbor_tile_review_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\weather_station_candidates_neighbor_tile_review_best.csv `
      --out-dir outputs\ib3w_route_candidate_elevation_finalize_v1

## 5. QA result

Summary:

    primary_rows = 48
    neighbor_best_rows = 40
    final_rows = 48

    primary_acceptable_rows = 8
    primary_need_neighbor_tile_review_rows = 40

    final_acceptable = 19
    final_low_confidence_review_required = 29
    final_review_required = 0
    final_lookup_failed = 0
    final_elevation_missing = 0
    final_review_required_total = 29

    final_good_confidence = 12
    final_moderate_confidence = 7
    final_low_confidence = 29

    final_source_primary_tile_lookup = 8
    final_source_neighbor_tile_review_recommended = 40

    final_tile_97233NW = 20
    final_tile_97233SW = 28

    zero_fallback_used = False

## 6. Interpretation

本分支完成 weather station candidates 的 station elevation finalization。

結果顯示：

    48 筆 weather candidate stations 全部有 final station elevation。
    19 筆達 FINAL_ACCEPTABLE。
    29 筆為 FINAL_LOW_CONFIDENCE_REVIEW_REQUIRED。
    20 筆 final tile 為 97233NW。
    28 筆 final tile 為 97233SW。
    未使用 zero fallback。

此結果可作為後續 weather context fusion 的 station elevation evidence，但 downstream 必須保留 final confidence gate。

## 7. Boundary

本分支不宣稱 48 筆 station elevation 全部同等可信。

本分支只宣稱：

    1. 所有 weather station candidates 均有 final elevation value。
    2. final source / final tile / final confidence / final status 已明確標記。
    3. low-confidence rows 未被偽裝成 acceptable。
    4. 未使用 zero fallback。

## 8. Next step

下一支建議：

    codex/ib3w-water-candidate-elevation-v1

目標：

    對 route-scoped water candidates 執行同樣的 primary tile lookup、neighbor tile review、finalization。
    仍不做 weather/hydro fusion。
