# README Current Pipeline Update: IB3W Weather Context Adapter v1

- 日期：2026-06-11
- 分支：codex/ib3w-weather-context-adapter-v1
- 上游基底：d5b4acb Document IB3W weather context source inventory

## 目的

本文件記錄 IB3W weather context adapter contract。此分支只建立介面與政策文件，不建立正式 weather/activity join。

IB3W 位於 calibrated activity backend dataset 與後續 behavior analysis 之間：

    IB3A-RC v1l2 calibrated activity backend dataset
    -> IB3W weather context layer
    -> IB3M behavior analysis

## 上游活動資料集參考

    outputs\ib3a_rc_backend_activity_enriched_v1l2_osm_radar_evidence_qixing_lengshuikeng_full26

## 天候資料庫參考

    C:\mountain_work\115_osm\weather\tw_weather_2026-05-01.sqlite3

sidecar files：

    C:\mountain_work\115_osm\weather\tw_weather_2026-05-01.sqlite3-wal
    C:\mountain_work\115_osm\weather\tw_weather_2026-05-01.sqlite3-shm

## 已檢查 schema tables

    weather_observations
    water_level_observations
    wra_station_metadata
    air_quality_observations
    source_status
    ingest_runs
    service_heartbeats
    location_admin_lookup

## 重要 contract rules

Weather data 是 optional contextual evidence，不是 hard dependency。

禁止解讀：

    missing weather = normal weather
    missing rainfall = 0 mm
    missing wind = calm
    missing hydro = unchanged water level

舊版 zero-valued "normal baseline" 是 rewrite boundary，不可重用為 observed weather。

`0 mm` rainfall 只有在可信觀測資料明確回報該時間窗無降雨時才成立。

`INFERRED_FROM_BEHAVIOR` 保留給後續 hypothesis layer，不可混入 v1 OBSERVED / IMPUTED context。

## 本分支新增 deliverables

    runs/ib3w_weather_context_adapter_v1_notes_20260611.md
    configs/weather_context/ib3w_station_candidate_policy_v1.csv
    configs/weather_context/ib3w_environment_window_status_policy_v1.csv
    scripts/README_current_pipeline_updated_20260611_ib3w_weather_context_adapter.md

## Non-goals

本分支不做：

- 跑完整 pipeline
- 掃大型 outputs
- commit outputs
- 建立正式 IB3W joined dataset
- 建立 production join script
- 執行 IB3M behavior analysis
- 調整 IB2 route risk
- 調整 radar evidence
- 調整 THCI score

## 下一個合理分支

建議下一個分支：

    codex/ib3w-weather-context-smoke-test-v1

建議範圍：

    small schema-driven smoke test
    station candidate ranking prototype
    single route/activity environment window extraction
    no zero fallback verification
    no formal joined dataset
