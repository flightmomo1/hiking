# IB3W Weather Context Adapter Batch v1 Notes

- 日期：2026-06-12
- 分支：codex/ib3w-weather-context-adapter-batch-v1
- 上游基底：df967d4 Add IB3W adapter row context summary
- 本分支範圍：batch wrapper for activity-level IB3W context summaries
- 非本分支範圍：station ranking recomputation、temporal coverage recomputation、variable coverage recomputation、row-level weather join、imputation、route risk / radar / THCI 調整

## 1. 本分支目的

前一段 adapter-row-v1 已能將單一 activity 的 variable coverage 結果收斂成 activity-level context summary。

本分支新增 adapter-batch-v1，用來：

- 讀取一個或多個 adapter-row context summary。
- 合併成 batch-level context summary。
- 輸出每個 activity 的 context QA summary。
- 統計 context_status counts。
- 統計 audit_status counts。
- 統計 variable × context_status × audit_status counts。
- 驗證 zero_fallback_detected_count 仍為 0。

本版仍不建立 row-level weather join，也不重新計算 station ranking / temporal coverage / variable coverage。

## 2. 新增設定檔

新增 case config：

    configs/weather_context/ib3w_adapter_batch_smoke_cases_v1.csv

測試 case：

    qixing_lengshuikeng_33_1_adapter_batch

輸入 adapter-row context summary：

    outputs\ib3w_weather_context_adapter_row_v1\ib3w_activity_context_summary_v1.csv

## 3. 新增腳本

新增腳本：

    scripts/ib3_activity_environment/ib3w_adapter_batch_context_summary_v1.py

腳本功能：

- 讀取 batch case config。
- 讀取每個 case 指定的 adapter-row context summary CSV。
- 合併 context rows。
- 依 activity_id 產出 activity-level QA summary。
- 檢查 required context variables 是否齊全：
    precipitation_1hr
    wind_speed
    temperature
    water_level
- 統計 context_status。
- 統計 audit_status。
- 統計 context_variable × context_status × audit_status。
- 輸出 batch HTML QA report。
- 不做 imputation。
- 不做 row-level join。

## 4. QA 執行命令

執行命令：

    python scripts\ib3_activity_environment\ib3w_adapter_batch_context_summary_v1.py `
      --case-config configs\weather_context\ib3w_adapter_batch_smoke_cases_v1.csv `
      --out-dir outputs\ib3w_weather_context_adapter_batch_v1

輸出：

    outputs\ib3w_weather_context_adapter_batch_v1\ib3w_batch_activity_context_summary_v1.csv
    outputs\ib3w_weather_context_adapter_batch_v1\ib3w_batch_activity_context_status_summary_v1.csv
    outputs\ib3w_weather_context_adapter_batch_v1\ib3w_batch_context_status_counts_v1.csv
    outputs\ib3w_weather_context_adapter_batch_v1\ib3w_batch_audit_status_counts_v1.csv
    outputs\ib3w_weather_context_adapter_batch_v1\ib3w_batch_variable_status_counts_v1.csv
    outputs\ib3w_weather_context_adapter_batch_v1\ib3w_adapter_batch_context_summary_v1.html

注意：outputs 僅作 QA 證據，不 commit。

## 5. QA 結果摘要

執行結果：

    batch_cases = 1
    activities = 1
    context_rows = 4
    context_status_counts = {'MISSING': 4}
    audit_status_counts = {'NULL_VALUE_ONLY': 1, 'OUTSIDE_TOLERANCE': 3}
    zero_fallback_detected_count = 0

Batch context rows：

    precipitation_1hr
        context_status = MISSING
        audit_status = NULL_VALUE_ONLY
        selected_station_id = 466930
        selected_station_name = 陽明山

    wind_speed
        context_status = MISSING
        audit_status = OUTSIDE_TOLERANCE
        selected_station_id = C0A9C0
        selected_station_name = 天母

    temperature
        context_status = MISSING
        audit_status = OUTSIDE_TOLERANCE
        selected_station_id = C0A9C0
        selected_station_name = 天母

    water_level
        context_status = MISSING
        audit_status = OUTSIDE_TOLERANCE
        selected_station_id = 1140H077
        selected_station_name = 大直橋

## 6. Activity QA summary

Activity：

    qixing_lengshuikeng_33_1

Summary：

    context_rows = 4
    required_variables_present = precipitation_1hr,temperature,water_level,wind_speed
    required_variables_missing = blank
    observed_count = 0
    missing_count = 4
    no_source_count = 0
    zero_fallback_detected_count = 0

Batch activity status：

    PASS_CONTEXT_SUMMARY_READY

## 7. Variable status counts

本輪 variable status counts：

    precipitation_1hr | MISSING | NULL_VALUE_ONLY = 1
    temperature | MISSING | OUTSIDE_TOLERANCE = 1
    water_level | MISSING | OUTSIDE_TOLERANCE = 1
    wind_speed | MISSING | OUTSIDE_TOLERANCE = 1

## 8. zero fallback 驗證

本輪再次驗證：

    zero_fallback_detected_count = 0

也就是 batch wrapper 沒有改變 adapter-row-v1 的 no-zero-fallback rule：

    missing rainfall 不補 0 mm
    missing wind 不補 calm
    missing temperature 不補 normal
    missing water level 不補 unchanged

## 9. 本輪結論

IB3W adapter-batch-v1 成功將單一 activity-level context summary 包成 batch-level QA view。

此版本完成的是：

    adapter-row context summary -> batch context summary -> batch QA counts

尚未完成的是：

    full station ranking / temporal coverage / variable coverage / adapter summary 一體化正式 adapter

## 10. 已知限制

本版仍是 batch wrapper，不是正式 production adapter：

- 目前只測試 1 個 activity。
- 只讀既有 adapter-row context summary output。
- 不重新計算 station ranking。
- 不重新計算 temporal coverage。
- 不重新計算 variable coverage。
- 不建立 row-level weather join。
- 不建立正式 IB3W unified adapter。
- 尚未處理多活動正式 batch case。
- 尚未測出 OBSERVED / NO_SOURCE / UNKNOWN 狀態。
- 尚未處理 station elevation metadata enrichment。

## 11. 後續收斂方向

adapter-batch-v1 完成後，IB3W 不建議再繼續新增更多分散 QA 腳本。

下一段建議進入 consolidation：

    codex/ib3w-weather-context-consolidation-v1

收斂目標：

- 將 station ranking、temporal coverage、variable coverage、adapter summary 合併為正式 IB3W adapter 主入口。
- 建立少數正式入口腳本。
- 將目前 QA ladder 保留為 evidence / regression tools。
- 補 station metadata elevation enrichment，尤其是 water stations。
- 仍不做 imputation。
- 仍不改 route risk / radar / THCI。
