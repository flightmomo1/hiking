# IB3W Route-Scoped Station Selection Elevation Join v1 Notes

- 日期：2026-06-12
- 分支：codex/ib3w-route-scoped-station-selection-elevation-join-v1
- 上游基底：d79acfe Add IB3W route-scoped station selection
- 本分支範圍：將舊 qixing weather station NLSC contour IDW elevation prototype join 回 route-scoped weather candidates
- 非本分支範圍：正式 full station elevation lookup、water station elevation、weather/hydro fusion、temporal coverage、variable coverage、formal adapter、route risk / radar / THCI 調整

## 1. 本分支目的

上一分支已完成 route-scoped station selection：

    global station registry 1483 rows
        ↓
    qixing_lengshuikeng route-scoped selection
        ↓
    weather candidates 48
    water candidates 66

但 station registry 目前尚未有 station elevation，因此 weather candidates 的：

    station_elevation_status = MISSING
    elevation_delta_status = STATION_ELEVATION_MISSING

本分支先回收舊 qixing prototype：

    outputs\ib3_environment_output\qixing_weather_station_elevation_from_nslc.csv

將其中的 weather station elevation join 回 route-scoped weather candidates。

## 2. 新增腳本

新增：

    scripts/ib3_activity_environment/ib3w_join_route_station_elevation_v1.py

腳本功能：

- 讀取 route-scoped weather_station_candidates.csv。
- 讀取 qixing_weather_station_elevation_from_nslc.csv。
- 以 station_id join。
- 補回 station_elevation_m。
- 補回 prototype elevation provenance。
- 計算 elevation_delta_m。
- 計算 elevation_delta_signed_m。
- 輸出 enriched weather candidates。
- 不做 weather fusion。
- 不修改 global station registry。

## 3. Inputs

Weather candidates：

    outputs\ib3w_route_scoped_station_selection_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\weather_station_candidates.csv

Prototype station elevation：

    outputs\ib3_environment_output\qixing_weather_station_elevation_from_nslc.csv

Prototype elevation rows：

    9

Prototype station ids：

    466930 陽明山
    466910 鞍部
    C0AC40 大屯山
    A0A460 文化大學
    C0AH40 平等
    C0A9C0 天母
    C0A870 五指山
    C0AI40 石牌
    C0A940 金山

## 4. QA command

執行命令：

    $weatherCandidates = "outputs\ib3w_route_scoped_station_selection_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\weather_station_candidates.csv"
    $stationElevation = "outputs\ib3_environment_output\qixing_weather_station_elevation_from_nslc.csv"

    .\.venv\Scripts\python.exe scripts\ib3_activity_environment\ib3w_join_route_station_elevation_v1.py `
      --weather-candidates-csv $weatherCandidates `
      --station-elevation-csv $stationElevation `
      --route-id qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b `
      --out-dir outputs\ib3w_route_scoped_station_selection_elevation_join_v1

## 5. QA outputs

輸出：

    outputs\ib3w_route_scoped_station_selection_elevation_join_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\weather_station_candidates_elevation_joined.csv
    outputs\ib3w_route_scoped_station_selection_elevation_join_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\weather_station_elevation_join_summary.csv
    outputs\ib3w_route_scoped_station_selection_elevation_join_v1\qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b\weather_station_elevation_join_summary.html

outputs 僅作 QA，不 commit。

## 6. QA result

執行結果：

    weather_candidates = 48
    station_elevation_rows = 9
    joined = 9
    no_match = 39

Summary：

    JOINED = 9
    NO_MATCH = 39

JOINED candidate rank range：

    min_candidate_rank = 1
    max_candidate_rank = 12

NO_MATCH candidate rank range：

    min_candidate_rank = 8
    max_candidate_rank = 48

## 7. Joined examples

成功補上 station elevation 的前幾筆：

    1 466930 陽明山
      station_elevation_m = 609.6678201514454
      route_nearest_elevation_m = 939.975594869474
      station_elevation_status = AVAILABLE_PROTOTYPE
      prototype_elevation_confidence = good

    2 466910 鞍部
      station_elevation_m = 839.7501276913617
      route_nearest_elevation_m = 1110.9902701028964
      station_elevation_status = AVAILABLE_PROTOTYPE
      prototype_elevation_confidence = good

    3 C0AC40 大屯山
      station_elevation_m = 1079.728443331852
      route_nearest_elevation_m = 1110.9902701028964
      station_elevation_status = AVAILABLE_PROTOTYPE
      prototype_elevation_confidence = good

## 8. Expected NO_MATCH examples

以下 route-scoped candidates 保持 MISSING 是合理結果，因為舊 9-station prototype 不含這些 station：

    C0A860 大坪
    C0A770 科教館
    C0A9F0 內湖
    466900 淡水
    C0A980 社子
    CAA020 國一S026K

## 9. Important interpretation

本分支不是正式 full station elevation lookup。

本分支只證明：

    route-scoped weather candidates
        ↓
    可回收舊 qixing NLSC contour IDW elevation prototype
        ↓
    可補 station elevation
        ↓
    可計算 station-route elevation delta

舊 qixing_weather_station_elevation_from_nslc.csv 仍只能視為：

    qixing route-scoped weather station elevation prototype

不可視為：

    formal global station elevation registry

## 10. Known limitations

v1 limitations：

- 只處理 weather candidates。
- 不處理 water candidates。
- 只 join 舊 qixing 9-station prototype。
- 尚未建立 full station terrain lookup。
- 尚未將 station elevation 回寫 global station registry。
- 尚未處理 C0A860 大坪、C0A770 科教館等 missing station elevation。
- 尚未做 temporal coverage。
- 尚未做 variable coverage。
- 尚未做 weather fusion。
- 尚未做 hydro watershed relation。

## 11. Next step

下一段建議：

    codex/ib3w-route-scoped-weather-context-fusion-v1

但在正式 fusion 前，需先決定是否要：

    A. 先做 full station terrain lookup
    B. 還是先用 joined 9 stations 做 prototype fusion smoke test

較穩健建議：

    先做 full station terrain lookup 或至少 route-candidate terrain lookup，
    再進 weather context fusion。
