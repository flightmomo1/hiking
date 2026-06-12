# IB3W Weather / Water Elevation Inventory v1 Notes

- 日期：2026-06-12
- 分支：codex/ib3w-weather-water-elevation-inventory-v1
- 上游基底：51ba9a9 Add IB3W water candidate elevation finalization
- 本分支範圍：整理 weather / water candidate final elevation evidence inventory
- 非本分支範圍：weather observation join、hydrology observation join、weather/hydro fusion、route risk / radar / THCI 調整

## 1. Purpose

本分支彙整目前 IB3W weather candidates 與 water candidates 的 station elevation final evidence。

目的不是產生新的 elevation lookup，也不是進行 weather/hydro fusion，而是確認後續 fusion 前可用 evidence 的品質分布。

## 2. Inputs

Case:

    qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b

Weather final elevation:

    outputs\ib3w_route_candidate_elevation_finalize_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\weather_station_candidates_elevation_final.csv

Weather summary:

    outputs\ib3w_route_candidate_elevation_finalize_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\weather_station_candidates_elevation_final_summary.csv

Water final elevation:

    outputs\ib3w_water_candidate_elevation_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\water_station_candidates_elevation_final.csv

Water summary:

    outputs\ib3w_water_candidate_elevation_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\water_station_candidates_elevation_summary.csv

## 3. Weather candidate elevation inventory

Weather candidate rows:

    48

Final status distribution:

    FINAL_ACCEPTABLE = 19
    FINAL_LOW_CONFIDENCE_REVIEW_REQUIRED = 29

Final confidence distribution:

    good = 12
    moderate = 7
    low = 29

Final tile distribution:

    97233NW = 20
    97233SW = 28

Final source distribution:

    primary_tile_lookup = 8
    neighbor_tile_review_recommended = 40

Zero fallback:

    False

## 4. Water candidate elevation inventory

Water candidate rows:

    66

Final status distribution:

    FINAL_ACCEPTABLE = 23
    FINAL_LOW_CONFIDENCE_REVIEW_REQUIRED = 43

Final confidence distribution:

    good = 14
    moderate = 9
    low = 43

Final tile distribution:

    97233NW = 16
    97233SW = 50

Final source distribution:

    primary_tile_lookup = 6
    neighbor_tile_review_recommended = 60

Zero fallback:

    False

## 5. Combined inventory

Combined candidate rows:

    114

Combined final status distribution:

    FINAL_ACCEPTABLE = 42
    FINAL_LOW_CONFIDENCE_REVIEW_REQUIRED = 72

Combined final confidence distribution:

    good = 26
    moderate = 16
    low = 72

Combined tile distribution:

    97233NW = 36
    97233SW = 78

Zero fallback:

    False

## 6. Interpretation

目前 weather / water station elevation evidence 已完成 inventory。

結果顯示：

    weather candidates 共 48 筆，其中 19 筆達 FINAL_ACCEPTABLE。
    water candidates 共 66 筆，其中 23 筆達 FINAL_ACCEPTABLE。
    合併共 114 筆 candidates，其中 42 筆達 FINAL_ACCEPTABLE。
    其餘 72 筆為 FINAL_LOW_CONFIDENCE_REVIEW_REQUIRED。
    未使用 zero fallback。

此 inventory 證實：

    1. route-scoped weather / water candidates 都已有 final station elevation value。
    2. final tile / final source / final confidence / final status 已被明確標記。
    3. neighbor tile review 對大量 candidates 是必要的。
    4. low-confidence rows 不應被 downstream fusion 視為同等可信 elevation evidence。

## 7. Downstream usage guidance

後續 weather/hydro context fusion 可以使用：

    FINAL_ACCEPTABLE rows

作為較可信 station elevation context。

後續 weather/hydro context fusion 必須保留：

    FINAL_LOW_CONFIDENCE_REVIEW_REQUIRED rows

但不可將其視為同等可信的高程校正依據。

建議 downstream 欄位：

    station_elevation_context_status
    station_elevation_context_confidence
    station_elevation_context_review_required
    station_elevation_context_source

## 8. Boundary

本分支不做：

    - weather observation join
    - hydrology observation join
    - rainfall / wind / temperature / water-level fusion
    - route risk recalculation
    - radar / THCI adjustment
    - missing weather or hydro value imputation

本分支也不宣稱：

    任意活動匯入後已可自動選 NLSC 圖號。

目前仍是：

    known case-level route context
        ↓
    route-scoped station candidates
        ↓
    station elevation evidence inventory

## 9. Next step

下一支建議：

    codex/ib3w-context-fusion-readiness-v1

目標：

    盤點 weather/water observation availability、station elevation confidence、temporal coverage audit、variable coverage audit、adapter row context summary。
    建立正式 fusion 前的 readiness table。
    仍不做 actual weather/hydro fusion。
