# IB3W Weather Context Station Ranking v1 Notes

- 日期：2026-06-11
- 分支：codex/ib3w-weather-context-station-ranking-v1
- 上游基底：85c2fc3 Add IB3W weather context smoke test
- 本分支範圍：Top-N station candidate ranking QA
- 非本分支範圍：正式 IB3W joined dataset、完整 pipeline、IB3M 行為分析、route risk / radar / THCI 調整

## 1. 本分支目的

上一段 smoke test v1 已驗證：

    missing contextual evidence remains MISSING
    zero-valued normal fallback was not produced

本分支將 station selection 從：

    nearest station only

升級成：

    Top-N station candidate ranking

此分支只產生候選測站 ranking evidence，不建立正式 weather/activity joined dataset。

## 2. 新增設定檔

新增 case config：

    configs/weather_context/ib3w_station_ranking_smoke_cases_v1.csv

測試 case：

    qixing_lengshuikeng_33_1_station_ranking

活動輸入：

    outputs\ib3a_rc_backend_activity_enriched_v1l2_osm_radar_evidence_qixing_lengshuikeng_full26\qixing_lengshuikeng_33_1_backend_activity_enriched_v1l2_osm_radar_evidence.csv

天候 SQLite DB：

    C:\mountain_work\115_osm\weather\tw_weather_2026-05-01.sqlite3

Ranking 參數：

    top_n = 10
    tolerance_hours = 3
    bounding_margin_deg = 0.35

## 3. 新增腳本

新增腳本：

    scripts/ib3_activity_environment/ib3w_rank_weather_station_candidates_v1.py

腳本功能：

- 讀取單一 station ranking smoke case。
- 從 activity CSV 的 `timestamp_s` 推估活動時間窗。
- 從 calibrated/display/raw lat/lon 推估代表位置。
- 在代表位置附近 bounding box 搜尋候選 weather stations。
- 在代表位置附近 bounding box 搜尋候選 water-level stations。
- 產出 weather Top-N candidates。
- 產出 water Top-N candidates。
- 保留 ranking evidence 欄位。
- 不建立正式 joined dataset。
- 不進行 IB3M behavior analysis。
- 不調整 route risk、radar、THCI。
- 不產生 zero-valued normal fallback。

## 4. Ranking evidence 欄位

本版 ranking evidence 包含：

    candidate_rank
    candidate_type
    source
    dataset_code
    station_id
    station_name
    latitude
    longitude
    elevation_m
    route_distance_m
    activity_start_time
    activity_end_time
    window_tolerance_hours
    obs_rows_in_tolerance_window
    obs_time_min_in_window
    obs_time_max_in_window
    all_obs_time_min
    all_obs_time_max
    total_station_rows
    activity_time_coverage_ratio
    temporal_relation
    signed_temporal_gap_minutes
    absolute_temporal_gap_minutes
    elevation_delta_m
    source_last_status
    source_last_success_at
    variable_available
    ranking_score
    ranking_reason
    zero_fallback_detected
    notes

Weather candidates 另包含：

    precipitation_1hr_available_count
    wind_speed_available_count
    temperature_available_count
    precipitation_1hr_mean
    wind_speed_mean
    temperature_mean

Water candidates 另包含：

    water_level_available_count
    water_level_mean

## 5. QA 執行命令

執行命令：

    python scripts\ib3_activity_environment\ib3w_rank_weather_station_candidates_v1.py `
      --case-config configs\weather_context\ib3w_station_ranking_smoke_cases_v1.csv `
      --out-dir outputs\ib3w_weather_context_station_ranking_v1

輸出：

    outputs\ib3w_weather_context_station_ranking_v1\ib3w_station_candidates_weather.csv
    outputs\ib3w_weather_context_station_ranking_v1\ib3w_station_candidates_water.csv
    outputs\ib3w_weather_context_station_ranking_v1\ib3w_station_ranking_summary.html

注意：outputs 僅作 QA 證據，不 commit。

## 6. QA 結果摘要

執行結果：

    weather_candidates = 10
    water_candidates = 10
    zero_fallback_detected_count = 0

Weather Top-10 最近候選測站：

    1. 466930 陽明山       route_distance_m = 1589.969
    2. 466910 鞍部         route_distance_m = 3454.557
    3. C0AC40 大屯山       route_distance_m = 3846.506
    4. A0A460 文化大學     route_distance_m = 3959.430
    5. C0AH40 平等         route_distance_m = 4566.529
    6. C0A9C0 天母         route_distance_m = 5937.988
    7. C0A870 五指山       route_distance_m = 6292.378
    8. C0AI40 石牌         route_distance_m = 7368.989
    9. C0A860 大坪         route_distance_m = 7405.046
    10. C0A770 科教館      route_distance_m = 8960.322

Water Top-10 最近候選測站：

    1. 1140H179 磺溪橋_北       route_distance_m = 6299.792
    2. 1140H180 中和橋_北       route_distance_m = 6572.847
    3. 1140H177 婆婆橋_北       route_distance_m = 6681.325
    4. 1140H175 薇閣_北         route_distance_m = 6785.633
    5. 1140H162 三和橋          route_distance_m = 7202.717
    6. 1140H181 望星橋_北       route_distance_m = 7605.837
    7. 1140H077 大直橋          route_distance_m = 9220.717
    8. 1010H006 新磺溪橋(即時) route_distance_m = 9605.967
    9. 1140H143 竹圍捷運站_新   route_distance_m = 10577.700
    10. 1010H007 磺溪河口       route_distance_m = 10585.442

## 7. Coverage 結果

本輪 Top-N candidates 均為：

    activity_time_coverage_ratio = 0.0
    temporal_relation = no_observation_in_window

這代表候選測站存在，但 activity tolerance window 內沒有對應觀測紀錄。

因此本輪 ranking score 實際上主要由下列因素主導：

    route_distance_m
    source_last_status
    variable availability outside the activity window / station-level existence

這是合理的 smoke-test 結果，因為本分支目標是先輸出候選測站 ranking evidence，而不是建立正式 weather/activity join。

## 8. zero fallback 驗證

Weather candidates：

    zero_fallback_detected = false × 10

Water candidates：

    zero_fallback_detected = false × 10

本輪未產生：

    missing rainfall -> 0 mm
    missing wind -> calm
    missing temperature -> normal
    missing water level -> unchanged

## 9. 已知限制

本版仍是 station ranking smoke implementation，限制如下：

- coverage 目前只以 tolerance window 內有無 rows 粗略表示。
- ranking score 仍是初版加權公式。
- 若 activity window 與 DB observation window 不重疊，coverage 會全部為 0。
- `temporal_relation = no_observation_in_window` 時，temporal gap 欄位會留空。
- water station metadata 目前沒有 elevation_m，因此 water ranking 無法評估 elevation_delta_m。
- 尚未輸出 rejected candidates 或完整 candidate pool。
- 尚未建立 production IB3W joined dataset。

## 10. 後續建議

下一段建議主題：

    codex/ib3w-weather-context-temporal-coverage-v1

建議處理：

- 將 temporal gap 拆成：
    signed_temporal_gap_minutes
    absolute_temporal_gap_minutes
    temporal_relation
- 即使 activity window 內沒有 obs，也要計算 station latest observation 與 activity start/end 的時間距離。
- 區分：
    before_activity
    after_activity
    overlaps_activity_window
    no_station_records
    no_records_in_tolerance_window
- 改善 coverage_ratio，不只用 0/1。
- 保留 no-zero-fallback rule。
- 仍不建立正式 joined dataset。
