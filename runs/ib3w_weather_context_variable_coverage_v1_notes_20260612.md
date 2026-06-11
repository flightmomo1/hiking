# IB3W Weather Context Variable Coverage v1 Notes

- 日期：2026-06-12
- 分支：codex/ib3w-weather-context-variable-coverage-v1
- 上游基底：5ca313b Add IB3W temporal coverage audit
- 本分支範圍：variable-level coverage audit for existing Top-N station candidates
- 非本分支範圍：正式 IB3W joined dataset、完整 pipeline、IB3M 行為分析、route risk / radar / THCI 調整

## 1. 本分支目的

上一段 temporal coverage v1 已能判斷 station-level temporal availability：

    station_records_outside_tolerance

但 station-level coverage 仍不足以支援正式 IB3W adapter，因為同一個測站可能：

- 有 obs_time，但某個變數全部為 null。
- 有 temperature，但沒有 rainfall。
- 有 wind_speed，但資料時間不在 activity/tolerance window 內。
- water station 有 rows，但 water_level_m 可能缺值。

本分支新增 variable-level coverage audit，用來拆分：

    precipitation_1hr
    wind_speed
    temperature
    water_level

並確認每個變數自己的有效值覆蓋情形。

## 2. 新增設定檔

新增 case config：

    configs/weather_context/ib3w_variable_coverage_smoke_cases_v1.csv

測試 case：

    qixing_lengshuikeng_33_1_variable_coverage

活動輸入：

    outputs\ib3a_rc_backend_activity_enriched_v1l2_osm_radar_evidence_qixing_lengshuikeng_full26\qixing_lengshuikeng_33_1_backend_activity_enriched_v1l2_osm_radar_evidence.csv

Weather temporal coverage candidates input：

    outputs\ib3w_weather_context_temporal_coverage_v1\ib3w_station_candidates_weather_temporal_coverage.csv

Water temporal coverage candidates input：

    outputs\ib3w_weather_context_temporal_coverage_v1\ib3w_station_candidates_water_temporal_coverage.csv

天候 SQLite DB：

    C:\mountain_work\115_osm\weather\tw_weather_2026-05-01.sqlite3

參數：

    tolerance_hours = 3
    expected_interval_minutes = 10

## 3. 新增腳本

新增腳本：

    scripts/ib3_activity_environment/ib3w_variable_coverage_audit_v1.py

腳本功能：

- 讀取上一段 temporal coverage v1 的 Top-N weather candidates。
- 讀取上一段 temporal coverage v1 的 Top-N water candidates。
- 重新讀取 activity CSV，推估 activity start/end。
- 對每個候選站回查 DB。
- 對每個變數分別計算有效值 coverage。
- 區分 station-level availability 與 variable-level availability。
- 不產生正式 joined dataset。
- 不對缺資料補 0、calm、normal、unchanged。

## 4. Variable-level 狀態分類

本版使用下列 variable coverage status：

    OBSERVED_IN_ACTIVITY
        activity window 內有該變數有效值。

    OBSERVED_IN_TOLERANCE
        activity window 內沒有，但 tolerance window 內有該變數有效值。

    OUTSIDE_TOLERANCE
        station 有該變數有效值，但都在 tolerance window 外。

    NULL_VALUE_ONLY
        station 有 rows，但該變數全部是 null / blank。

    NO_STATION_RECORDS
        該 station 在 DB 中沒有任何 rows。

    NO_VARIABLE_COLUMN
        資料表沒有該變數欄位。

## 5. Audited variables

Weather variables：

    precipitation_1hr = precipitation_1hr_mm
    wind_speed = wind_speed_ms
    temperature = temperature_c

Water variables：

    water_level = water_level_m

## 6. QA 執行命令

執行命令：

    python scripts\ib3_activity_environment\ib3w_variable_coverage_audit_v1.py `
      --case-config configs\weather_context\ib3w_variable_coverage_smoke_cases_v1.csv `
      --out-dir outputs\ib3w_weather_context_variable_coverage_v1

輸出：

    outputs\ib3w_weather_context_variable_coverage_v1\ib3w_weather_variable_coverage.csv
    outputs\ib3w_weather_context_variable_coverage_v1\ib3w_water_variable_coverage.csv
    outputs\ib3w_weather_context_variable_coverage_v1\ib3w_variable_coverage_summary.html

注意：outputs 僅作 QA 證據，不 commit。

## 7. QA 結果摘要

執行結果：

    weather_variable_rows = 30
    water_variable_rows = 10
    zero_fallback_detected_count = 0

Weather status counts：

    NULL_VALUE_ONLY = 10
    OUTSIDE_TOLERANCE = 20

Water status counts：

    OUTSIDE_TOLERANCE = 10

依變數交叉統計：

    precipitation_1hr, NULL_VALUE_ONLY = 10
    wind_speed, OUTSIDE_TOLERANCE = 10
    temperature, OUTSIDE_TOLERANCE = 10
    water_level, OUTSIDE_TOLERANCE = 10

## 8. Rank 1 weather variable evidence

Weather rank 1：

    station_id = 466930
    station_name = 陽明山

Variable result：

    precipitation_1hr
        variable_coverage_status = NULL_VALUE_ONLY
        variable_valid_records_total = 0
        variable_valid_records_in_activity = 0
        variable_valid_records_in_tolerance = 0

    wind_speed
        variable_coverage_status = OUTSIDE_TOLERANCE
        variable_valid_records_total = 3874
        variable_valid_records_in_activity = 0
        variable_valid_records_in_tolerance = 0

    temperature
        variable_coverage_status = OUTSIDE_TOLERANCE
        variable_valid_records_total = 3883
        variable_valid_records_in_activity = 0
        variable_valid_records_in_tolerance = 0

Interpretation：

    陽明山測站雖然有 wind_speed / temperature 有效值，但都不在 activity/tolerance window 內。
    precipitation_1hr 則為 NULL_VALUE_ONLY，不能解讀為 0 mm rainfall。

## 9. Rank 1 water variable evidence

Water rank 1：

    station_id = 1140H179
    station_name = 磺溪橋_北

Variable result：

    water_level
        variable_coverage_status = OUTSIDE_TOLERANCE
        variable_valid_records_total = 2732
        variable_valid_records_in_activity = 0
        variable_valid_records_in_tolerance = 0

Interpretation：

    磺溪橋_北水位站有 water_level 有效值，但不在 activity/tolerance window 內。
    因此不可視為 activity 當下水位觀測。

## 10. zero fallback 驗證

本輪再次驗證：

    missing rainfall 不補 0 mm
    missing wind 不補 calm
    missing temperature 不補 normal
    missing water level 不補 unchanged

特別是 precipitation_1hr：

    NULL_VALUE_ONLY 不等於 0 mm rainfall

這是正式 IB3W adapter 必須保留的邊界。

## 11. 本輪結論

IB3W variable coverage v1 通過核心驗證：

    station-level availability is not enough
    variable-level availability must be audited separately
    missing/null variable values remain missing evidence
    zero-valued normal fallback was not produced

本分支仍不建立正式 joined dataset，也不調整 route risk / radar / THCI。

## 12. 已知限制

本版仍是 variable-level audit，不是正式 adapter：

- 只 audit temporal coverage v1 產出的 Top-N candidates。
- 不處理完整 candidate pool。
- 不建立正式 activity-weather joined dataset。
- coverage_expected_points 仍以 expected_interval_minutes 粗估。
- 尚未根據 source/dataset 的實際觀測頻率自動推估 expected interval。
- 尚未將 variable-level coverage 回寫 station ranking score。
- 尚未產出正式 context_status：OBSERVED / MISSING / NO_SOURCE / UNKNOWN。
- 尚未建立 row-level activity weather context join。

## 13. 後續建議

下一段建議主題：

    codex/ib3w-weather-context-adapter-row-v1

建議處理：

- 將 station ranking、temporal coverage、variable coverage 整合成 row-level adapter prototype。
- 對單一 activity 產出 per-activity context summary。
- 產出正式 context_status 欄位：
    OBSERVED
    MISSING
    NO_SOURCE
    UNKNOWN
- 仍不做 imputation。
- 仍不補 0 / calm / normal / unchanged。
- 仍不調整 route risk / radar / THCI。
