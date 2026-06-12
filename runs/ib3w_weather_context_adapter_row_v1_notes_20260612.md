# IB3W Weather Context Adapter Row v1 Notes

- 日期：2026-06-12
- 分支：codex/ib3w-weather-context-adapter-row-v1
- 上游基底：ea9c800 Add IB3W variable coverage audit
- 本分支範圍：activity-level context summary adapter prototype
- 非本分支範圍：正式 row-level weather join、完整 pipeline、IB3M 行為分析、route risk / radar / THCI 調整

## 1. 本分支目的

前面 IB3W 已完成四段 QA ladder：

    1. smoke test v1
       驗證 missing 不補 0 / calm / normal / unchanged

    2. station ranking v1
       建立 weather / water Top-N candidate ranking

    3. temporal coverage v1
       補齊 station-level temporal availability

    4. variable coverage v1
       拆出 variable-level availability

本分支將 variable-level coverage audit 收斂成第一版 adapter context summary。

本版仍不建立正式 row-level weather join，而是先產出 activity-level context summary：

    每個 activity × 每個 context variable 一列

## 2. 新增設定檔

新增 case config：

    configs/weather_context/ib3w_adapter_row_smoke_cases_v1.csv

測試 case：

    qixing_lengshuikeng_33_1_adapter_row

活動輸入：

    outputs\ib3a_rc_backend_activity_enriched_v1l2_osm_radar_evidence_qixing_lengshuikeng_full26\qixing_lengshuikeng_33_1_backend_activity_enriched_v1l2_osm_radar_evidence.csv

Weather variable coverage input：

    outputs\ib3w_weather_context_variable_coverage_v1\ib3w_weather_variable_coverage.csv

Water variable coverage input：

    outputs\ib3w_weather_context_variable_coverage_v1\ib3w_water_variable_coverage.csv

## 3. 新增腳本

新增腳本：

    scripts/ib3_activity_environment/ib3w_adapter_row_context_summary_v1.py

腳本功能：

- 讀取 variable coverage audit output。
- 依 context variable 分組。
- 為每個 context variable 選出最佳候選站。
- 將 variable-level audit status 收斂為正式 context_status。
- 輸出 activity-level context summary CSV。
- 輸出 HTML QA report。
- 不建立 row-level weather join。
- 不進行 imputation。
- 不補 0、calm、normal、unchanged。

## 4. Formal context_status mapping

本版正式 context_status：

    OBSERVED
    MISSING
    NO_SOURCE
    UNKNOWN

Mapping rule：

    OBSERVED_IN_ACTIVITY  -> OBSERVED
    OBSERVED_IN_TOLERANCE -> OBSERVED

    OUTSIDE_TOLERANCE -> MISSING
    NULL_VALUE_ONLY   -> MISSING

    NO_STATION_RECORDS -> NO_SOURCE
    NO_VARIABLE_COLUMN -> NO_SOURCE

    others -> UNKNOWN

## 5. Candidate selection rule

每個 context variable 會從 variable coverage rows 中選出最佳候選。

排序依據：

    status_priority
    audit_priority
    nearest_valid_obs_gap_abs_minutes
    route_distance_m
    candidate_rank
    valid_records_in_activity
    valid_records_in_tolerance
    variable_valid_records_total

目前 selection rule：

    status_priority,audit_priority,nearest_gap,distance,candidate_rank

因此本版不是單純選最近測站，而是優先考量該變數的可用性與時間距離。

## 6. QA 執行命令

執行命令：

    python scripts\ib3_activity_environment\ib3w_adapter_row_context_summary_v1.py `
      --case-config configs\weather_context\ib3w_adapter_row_smoke_cases_v1.csv `
      --out-dir outputs\ib3w_weather_context_adapter_row_v1

輸出：

    outputs\ib3w_weather_context_adapter_row_v1\ib3w_activity_context_summary_v1.csv
    outputs\ib3w_weather_context_adapter_row_v1\ib3w_activity_context_summary_v1.html

注意：outputs 僅作 QA 證據，不 commit。

## 7. QA 結果摘要

執行結果：

    context_rows = 4
    context_status_counts = {'MISSING': 4}
    audit_status_counts = {'NULL_VALUE_ONLY': 1, 'OUTSIDE_TOLERANCE': 3}
    zero_fallback_detected_count = 0

Formal context summary：

    precipitation_1hr
        context_status = MISSING
        audit_status = NULL_VALUE_ONLY
        selected_station_id = 466930
        selected_station_name = 陽明山
        selected_candidate_rank = 1
        selected_route_distance_m = 1589.969
        valid_records_in_activity = 0

    wind_speed
        context_status = MISSING
        audit_status = OUTSIDE_TOLERANCE
        selected_station_id = C0A9C0
        selected_station_name = 天母
        selected_candidate_rank = 6
        selected_route_distance_m = 5937.988
        valid_records_in_activity = 0

    temperature
        context_status = MISSING
        audit_status = OUTSIDE_TOLERANCE
        selected_station_id = C0A9C0
        selected_station_name = 天母
        selected_candidate_rank = 6
        selected_route_distance_m = 5937.988
        valid_records_in_activity = 0

    water_level
        context_status = MISSING
        audit_status = OUTSIDE_TOLERANCE
        selected_station_id = 1140H077
        selected_station_name = 大直橋
        selected_candidate_rank = 7
        selected_route_distance_m = 9220.717
        valid_records_in_activity = 0

## 8. Interpretation

本輪 activity-level context summary 顯示：

    precipitation_1hr = MISSING
    wind_speed = MISSING
    temperature = MISSING
    water_level = MISSING

但 missing reason 不同：

    precipitation_1hr 是 NULL_VALUE_ONLY
    wind_speed / temperature / water_level 是 OUTSIDE_TOLERANCE

這表示：

- precipitation_1hr 在候選測站中沒有有效 rainfall value，不能解讀為 0 mm。
- wind_speed 有有效值，但不在 activity/tolerance window 內，不能解讀為 calm。
- temperature 有有效值，但不在 activity/tolerance window 內，不能解讀為 normal。
- water_level 有有效值，但不在 activity/tolerance window 內，不能解讀為 unchanged。

## 9. zero fallback 驗證

本輪再次驗證：

    zero_fallback_detected_count = 0

也就是：

    missing rainfall 不補 0 mm
    missing wind 不補 calm
    missing temperature 不補 normal
    missing water level 不補 unchanged

## 10. 本輪結論

IB3W adapter-row-v1 成功將前面 QA ladder 收斂成 activity-level context summary。

此版本已能輸出正式 context_status，但仍保留底層 audit_status，避免 MISSING 變成黑盒。

本版完成的是：

    variable coverage -> selected station -> context_status summary

尚未完成的是：

    context_status summary -> row-level activity/weather join

## 11. 已知限制

本版仍是 adapter prototype，不是正式 production adapter：

- 只處理單一 activity smoke case。
- 只讀既有 variable coverage outputs。
- 未直接整合 station ranking / temporal coverage / variable coverage 的完整流程。
- 未建立 row-level weather context join。
- 未將 context_status 寫回每一筆 activity row。
- 未建立正式 schema version 欄位。
- 未處理多活動 batch。
- 未建立 pytest / CI 驗證。
- candidate selection rule 仍是 prototype。
- 尚未將 NO_SOURCE / UNKNOWN 情境完整測出。

## 12. 後續建議

下一段建議主題：

    codex/ib3w-weather-context-adapter-batch-v1

建議處理：

- 將 adapter-row-v1 擴展為 batch smoke。
- 至少支援多個 activity cases。
- 輸出 batch-level context summary。
- 保留 context_status / audit_status。
- 驗證不同 activity 是否能出現不同狀態：
    OBSERVED
    MISSING
    NO_SOURCE
    UNKNOWN
- 仍不做 row-level join。
- 仍不做 imputation。
- 仍不改 route risk / radar / THCI。
