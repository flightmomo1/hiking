# IB3W Weather Context Temporal Coverage v1 Notes

- 日期：2026-06-11
- 分支：codex/ib3w-weather-context-temporal-coverage-v1
- 上游基底：a7b1563 Add IB3W weather station ranking QA
- 本分支範圍：temporal coverage audit for existing Top-N station candidates
- 非本分支範圍：正式 IB3W joined dataset、完整 pipeline、IB3M 行為分析、route risk / radar / THCI 調整

## 1. 本分支目的

上一段 station ranking v1 已建立：

    weather Top-10 candidate ranking
    water Top-10 candidate ranking

但上一段仍只知道：

    activity_time_coverage_ratio = 0.0
    temporal_relation = no_observation_in_window

尚未清楚說明：

- station 是否本身有資料。
- station 資料是在活動前、活動後，或與活動時間窗重疊。
- station 最近觀測與 activity window 差幾分鐘。
- 無觀測是因為 station 無資料，還是 station 有資料但不在 tolerance window 內。

本分支新增 temporal coverage audit，用來補足候選測站的時間可用性證據。

## 2. 新增設定檔

新增 case config：

    configs/weather_context/ib3w_temporal_coverage_smoke_cases_v1.csv

測試 case：

    qixing_lengshuikeng_33_1_temporal_coverage

活動輸入：

    outputs\ib3a_rc_backend_activity_enriched_v1l2_osm_radar_evidence_qixing_lengshuikeng_full26\qixing_lengshuikeng_33_1_backend_activity_enriched_v1l2_osm_radar_evidence.csv

Weather candidates input：

    outputs\ib3w_weather_context_station_ranking_v1\ib3w_station_candidates_weather.csv

Water candidates input：

    outputs\ib3w_weather_context_station_ranking_v1\ib3w_station_candidates_water.csv

天候 SQLite DB：

    C:\mountain_work\115_osm\weather\tw_weather_2026-05-01.sqlite3

參數：

    tolerance_hours = 3
    expected_interval_minutes = 10

## 3. 新增腳本

新增腳本：

    scripts/ib3_activity_environment/ib3w_temporal_coverage_audit_v1.py

腳本功能：

- 讀取上一段 station ranking v1 產出的 Top-N weather candidates。
- 讀取上一段 station ranking v1 產出的 Top-N water candidates。
- 重新讀取 activity CSV，推估 activity start/end。
- 對每個候選站回查 DB 中該 station 的完整 obs_time 序列。
- 補上 refined temporal coverage 欄位。
- 不產生正式 joined dataset。
- 不對缺資料補 0、calm、normal、unchanged。

## 4. 新增 temporal coverage 欄位

本版新增或補強欄位：

    activity_start_time_refined
    activity_end_time_refined
    activity_duration_minutes
    tolerance_window_start
    tolerance_window_end
    tolerance_window_minutes
    expected_interval_minutes
    station_has_any_records
    station_total_obs_records_recount
    station_first_obs_time
    station_last_obs_time
    records_in_activity_window
    records_in_tolerance_window_recount
    station_has_records_in_tolerance_window
    coverage_expected_points
    coverage_observed_points
    coverage_ratio_estimated
    temporal_relation_refined
    nearest_obs_time
    nearest_obs_relation
    nearest_obs_gap_minutes
    nearest_obs_gap_abs_minutes
    latest_obs_before_activity
    latest_obs_before_gap_minutes
    earliest_obs_after_activity
    earliest_obs_after_gap_minutes
    zero_fallback_detected

## 5. Refined temporal relation 定義

本版使用：

    overlaps_activity
        activity window 內有觀測紀錄。

    records_in_tolerance_only
        activity window 內沒有觀測，但 tolerance window 內有觀測。

    station_records_outside_tolerance
        station 本身有觀測紀錄，但不在 activity/tolerance window 內。

    no_station_records
        該 station 在 DB 中沒有任何觀測紀錄。

本輪結果主要落在：

    station_records_outside_tolerance

代表候選站存在且有資料，但資料時間與 activity window 不重疊。

## 6. QA 執行命令

執行命令：

    python scripts\ib3_activity_environment\ib3w_temporal_coverage_audit_v1.py `
      --case-config configs\weather_context\ib3w_temporal_coverage_smoke_cases_v1.csv `
      --out-dir outputs\ib3w_weather_context_temporal_coverage_v1

輸出：

    outputs\ib3w_weather_context_temporal_coverage_v1\ib3w_station_candidates_weather_temporal_coverage.csv
    outputs\ib3w_weather_context_temporal_coverage_v1\ib3w_station_candidates_water_temporal_coverage.csv
    outputs\ib3w_weather_context_temporal_coverage_v1\ib3w_temporal_coverage_summary.html

注意：outputs 僅作 QA 證據，不 commit。

## 7. QA 結果摘要

Weather candidates：

    weather_candidates = 10
    temporal_relation_refined = station_records_outside_tolerance × 10
    zero_fallback_detected = false × 10

Water candidates：

    water_candidates = 10
    temporal_relation_refined = station_records_outside_tolerance × 10
    zero_fallback_detected = false × 10

整體：

    zero_fallback_detected_count = 0

## 8. Rank 1 weather temporal evidence

Weather rank 1：

    station_id = 466930
    station_name = 陽明山
    temporal_relation_refined = station_records_outside_tolerance
    nearest_obs_relation = after_activity
    nearest_obs_time = 2026-03-24T12:10:00+00:00
    nearest_obs_gap_minutes = -830007.533
    nearest_obs_gap_abs_minutes = 830007.533
    latest_obs_before_activity = blank
    latest_obs_before_gap_minutes = blank
    earliest_obs_after_activity = 2026-03-24T12:10:00+00:00
    earliest_obs_after_gap_minutes = 830007.533
    station_first_obs_time = 2026-03-24T12:10:00+00:00
    station_last_obs_time = 2026-04-30T23:30:00+00:00

Interpretation：

    陽明山測站有資料，但最近觀測在 activity 之後，且距離 activity window 約 830007.533 分鐘。
    因此不可視為 activity 當下觀測。

## 9. Rank 1 water temporal evidence

Water rank 1：

    station_id = 1140H179
    station_name = 磺溪橋_北
    temporal_relation_refined = station_records_outside_tolerance
    nearest_obs_relation = after_activity
    nearest_obs_time = 2026-03-24T11:40:00+00:00
    nearest_obs_gap_minutes = -829977.533
    nearest_obs_gap_abs_minutes = 829977.533
    latest_obs_before_activity = blank
    latest_obs_before_gap_minutes = blank
    earliest_obs_after_activity = 2026-03-24T11:40:00+00:00
    earliest_obs_after_gap_minutes = 829977.533
    station_first_obs_time = 2026-03-24T11:40:00+00:00
    station_last_obs_time = 2026-04-30T23:20:00+00:00

Interpretation：

    磺溪橋_北水位站有資料，但最近觀測在 activity 之後，且距離 activity window 約 829977.533 分鐘。
    因此不可視為 activity 當下水位觀測。

## 10. zero fallback 驗證

本輪再次驗證：

    missing rainfall 不補 0 mm
    missing wind 不補 calm
    missing temperature 不補 normal
    missing water level 不補 unchanged

即使 station 本身有資料，只要 activity/tolerance window 內無可信觀測，仍維持 missing evidence。

## 11. 已知限制

本版仍是 temporal coverage audit，不是正式 adapter：

- 只 audit station ranking v1 產出的 Top-N candidates。
- 不處理完整 candidate pool。
- 不建立正式 activity-weather joined dataset。
- coverage_expected_points 目前以 expected_interval_minutes 粗估。
- 尚未依不同 source/dataset 的實際觀測頻率自動推估 expected interval。
- 尚未處理多變數分別 coverage，例如 rainfall coverage、wind coverage、temperature coverage 分開統計。
- 尚未將 temporal coverage 回寫 ranking score。

## 12. 後續建議

下一段建議主題：

    codex/ib3w-weather-context-variable-coverage-v1

建議處理：

- weather variables 分別統計：
    precipitation_1hr
    wind_speed
    temperature

- water variables 分別統計：
    water_level

- 分別輸出：
    variable_records_in_activity_window
    variable_records_in_tolerance_window
    variable_coverage_ratio_estimated
    variable_nearest_obs_time
    variable_temporal_relation_refined

- 不再只用 station-level obs_time coverage。
- 保留 no-zero-fallback rule。
- 仍不建立正式 joined dataset。
