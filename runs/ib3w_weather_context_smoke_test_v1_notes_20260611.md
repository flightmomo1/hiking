# IB3W Weather Context Smoke Test v1 Notes

- 日期：2026-06-11
- 分支：codex/ib3w-weather-context-smoke-test-v1
- 上游基底：0a031ae Document IB3W weather context adapter contract
- 本分支範圍：single-case smoke test script、case config、QA summary output verification
- 非本分支範圍：完整 pipeline、正式 IB3W joined dataset、IB3M 行為分析、route risk / radar / THCI 調整

## 1. Smoke Test 目的

本 smoke test 用最小實作驗證 IB3W adapter contract 的幾個核心規則：

- weather data 是 optional contextual evidence，不是 hard dependency。
- missing weather 不等於 normal weather。
- missing rainfall 不等於 0 mm。
- missing wind 不等於 calm。
- missing hydro 不等於 unchanged water level。
- 不可使用舊版 zero-valued normal fallback。
- 不建立正式 IB3W joined dataset。

## 2. 測試 case

測試設定檔：

    configs/weather_context/ib3w_smoke_test_cases_v1.csv

測試活動：

    qixing_lengshuikeng_33_1

活動輸入檔：

    outputs\ib3a_rc_backend_activity_enriched_v1l2_osm_radar_evidence_qixing_lengshuikeng_full26\qixing_lengshuikeng_33_1_backend_activity_enriched_v1l2_osm_radar_evidence.csv

選擇 33_1 的原因：

- v1l2 正式活動資料集中 33_1 檔案相對較小。
- 適合第一輪 smoke test。
- 不需掃描完整 outputs。
- 可從 `timestamp_s`、`calibrated_lat`、`calibrated_lon` 推得 activity window 與代表位置。

## 3. Weather DB 檢查摘要

天候 SQLite DB：

    C:\mountain_work\115_osm\weather\tw_weather_2026-05-01.sqlite3

weather_observations 時間範圍：

    source = cwa
    dataset_code = STA_Weather.LatestObservations
    rows = 1,140,566
    min(obs_time) = 2026-03-24T11:00:00+00:00
    max(obs_time) = 2026-04-30T23:30:00+00:00

water_level_observations 時間範圍：

    source = wra
    dataset_code = 73c4c3de-4045-4765-abeb-89f9f9cd5ff0
    rows = 1,265,845
    min(obs_time) = 2025-12-14T11:50:00+08:00
    max(obs_time) = 2026-05-01T07:40:00+08:00

source_status：

    cwa = success
    wra = success

## 4. 腳本

新增 smoke test 腳本：

    scripts/ib3_activity_environment/ib3w_smoke_test_weather_context_v1.py

腳本功能：

- 讀取單一 smoke test case config。
- 從 v1l2 activity CSV 的 `timestamp_s` 推估活動時間窗。
- 從 `calibrated_lat` / `display_lat` / `lat` 推估代表位置。
- 在活動代表位置附近 bounding box 內尋找 weather / water 候選測站。
- 對下列 context variables 產出 QA summary：

    precipitation_1hr
    wind_speed
    temperature
    water_level

- 若活動時間窗內沒有可信觀測，輸出 MISSING。
- 若沒有候選測站，輸出 NO_SOURCE。
- 不從缺資料合成 0 rainfall、calm wind、normal temperature、unchanged water level。

## 5. QA 輸出

Smoke test 執行命令：

    python scripts\ib3_activity_environment\ib3w_smoke_test_weather_context_v1.py `
      --case-config configs\weather_context\ib3w_smoke_test_cases_v1.csv `
      --out-dir outputs\ib3w_weather_context_smoke_test_v1

輸出檔案：

    outputs\ib3w_weather_context_smoke_test_v1\ib3w_smoke_test_context_summary.csv
    outputs\ib3w_weather_context_smoke_test_v1\ib3w_smoke_test_context_summary.html

注意：outputs 僅作為 QA 證據，不 commit。

## 6. QA 結果

Smoke test 執行結果：

    rows: 4
    zero_fallback_detected_count: 0

context_status group：

    MISSING = 4

zero_fallback_detected group：

    false = 4

逐項結果：

    precipitation_1hr = MISSING
    wind_speed = MISSING
    temperature = MISSING
    water_level = MISSING

這代表腳本成功驗證：

- 沒有活動時間窗內的 rainfall observation 時，不補 0 mm。
- 沒有活動時間窗內的 wind observation 時，不補 calm。
- 沒有活動時間窗內的 temperature observation 時，不補 normal temperature。
- 沒有活動時間窗內的 water level observation 時，不補 unchanged water level。

## 7. recency_minutes 備註

本版 smoke test 的 `recency_minutes` 是 signed gap，用 activity start 減 candidate station 最新觀測時間。

因此出現負值時，代表：

    candidate station latest observation is after activity start

這不影響本輪判定，因為 context status 是由 activity tolerance window 內是否有觀測值決定。本輪所有 target variables 在 activity tolerance window 內均無有效觀測，因此輸出 MISSING。

後續正式 adapter 可考慮把此欄位拆成：

    signed_recency_minutes
    absolute_temporal_gap_minutes
    temporal_relation

以避免 QA 閱讀誤解。

## 8. 本輪結論

IB3W smoke test v1 通過第一個核心驗證：

    missing contextual evidence remains MISSING
    zero-valued normal fallback was not produced

本分支仍不建立正式 joined dataset，也不調整 route risk / radar / THCI。

## 9. 後續建議

下一步可建立：

    codex/ib3w-weather-context-station-ranking-v1

建議範圍：

- 改善 station candidate ranking。
- 明確輸出候選測站 Top-N。
- 加入 coverage、recency、elevation、source quality、variable availability。
- 修正 temporal gap 欄位語意。
- 仍不建立正式 joined dataset。
