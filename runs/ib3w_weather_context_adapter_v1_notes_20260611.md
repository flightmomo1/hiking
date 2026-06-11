# IB3W Weather Context Adapter v1 Notes

- 日期：2026-06-11
- 分支：codex/ib3w-weather-context-adapter-v1
- 上游基底：d5b4acb Document IB3W weather context source inventory
- 本分支範圍：adapter contract、station candidate policy、environment window status policy
- 非本分支範圍：完整 pipeline、正式 IB3W joined dataset、IB3M 行為分析、route risk / radar / THCI 調整

## 1. Pipeline 位置

IB3W 位於 row-level calibrated activity backend dataset 與後續行為分析之間：

    IB3A-RC v1l2 calibrated activity backend dataset
    -> IB3W weather context layer
    -> IB3M behavior analysis

上游活動資料集參考：

    outputs\ib3a_rc_backend_activity_enriched_v1l2_osm_radar_evidence_qixing_lengshuikeng_full26

天候 SQLite DB：

    C:\mountain_work\115_osm\weather\tw_weather_2026-05-01.sqlite3

檢查時確認 sidecar files 存在：

    C:\mountain_work\115_osm\weather\tw_weather_2026-05-01.sqlite3-wal
    C:\mountain_work\115_osm\weather\tw_weather_2026-05-01.sqlite3-shm

## 2. SQLite schema 低成本檢查結果

SQLite CLI 可用：

    sqlite3 version 3.51.1

已發現 tables：

    air_quality_observations
    ingest_runs
    location_admin_lookup
    service_heartbeats
    source_status
    weather_observations
    water_level_observations
    wra_station_metadata

## 3. Source tables 與 IB3W 用途

### 3.1 weather_observations

主要天候觀測時序表。

重要欄位：

    source
    dataset_code
    station_id
    station_name
    obs_time
    ingested_at
    latitude
    longitude
    county_name
    town_name
    village_name
    elevation_m
    weather
    temperature_c
    relative_humidity_pct
    pressure_hpa
    wind_speed_ms
    wind_direction_deg
    wind_gust_ms
    precipitation_mm
    precipitation_10min_mm
    precipitation_1hr_mm
    sunshine_duration_min
    visibility_m
    uv_index
    qc_flag
    raw_payload

IB3W 解讀：

- 若活動時間窗內有可信觀測紀錄，可作為 OBSERVED weather context。
- 可用 `obs_time` 與 `ingested_at` 檢查 coverage 與 recency。
- 可支援雨量、風速、風向、陣風、溫度、濕度、氣壓、能見度、UV 與天氣文字。
- `precipitation_mm = 0` 只有在可信紀錄明確回報 0 時才成立。
- 缺少 precipitation 欄位或紀錄，不可解讀為 0 mm。
- 缺少 wind 欄位或紀錄，不可解讀為 calm。

### 3.2 water_level_observations

主要水文／水位觀測時序表。

重要欄位：

    source
    dataset_code
    station_id
    observatory_identifier
    station_name
    obs_time
    ingested_at
    latitude
    longitude
    location_address
    river_name
    county_name
    town_name
    village_name
    water_level_m
    check_result
    check_desc
    voltage
    qc_flag
    raw_payload

IB3W 解讀：

- 若活動時間窗內有可信水位紀錄，可作為 OBSERVED hydrology context。
- `water_level_m` 可提供溪流、水位敏感路段的環境背景。
- 缺少水位資料，不可解讀為 water level unchanged。
- `check_result`、`check_desc`、`voltage`、`qc_flag` 應作為品質判斷依據。

### 3.3 wra_station_metadata

水利署測站 metadata。

重要欄位：

    station_id
    observatory_identifier
    station_name
    river_name
    location_address
    twd97_x
    twd97_y
    latitude
    longitude
    raw_payload
    refreshed_at

IB3W 解讀：

- 可支援水文測站位置查詢。
- 可支援 hydrology station candidate discovery。
- 目前沒有 elevation 欄位，因此水文測站的 elevation compatibility 需要外部資料補強。

### 3.4 air_quality_observations

空氣品質與輔助風場欄位。

重要欄位：

    source
    dataset_code
    site_id
    site_name
    county
    obs_time
    ingested_at
    latitude
    longitude
    county_name
    town_name
    village_name
    aqi
    status
    pollutant
    pm25_ugm3
    pm10_ugm3
    o3_ppb
    co_ppm
    so2_ppb
    no2_ppb
    nox_ppb
    no_ppb
    wind_speed_ms
    wind_direction_deg
    qc_flag
    raw_payload

IB3W 解讀：

- 可作為 optional air-quality context。
- wind 欄位可作為輔助資訊，但不應預設取代 weather station。
- v1 不用 air quality 直接調整 route risk。

### 3.5 source_status

資料來源狀態表。

重要欄位：

    source
    schedule_mode
    next_due_at
    last_started_at
    last_finished_at
    last_success_at
    last_status
    last_error_message
    updated_at

IB3W 解讀：

- 可支援 source recency 與 source reliability 檢查。
- 若 `last_success_at` 過舊、`last_status` 失敗、或 `last_error_message` 非空，應降低品質或直接 gate。

### 3.6 ingest_runs

資料匯入歷史。

重要欄位：

    id
    source
    dataset_code
    started_at
    finished_at
    status
    rows_written
    error_message

IB3W 解讀：

- 可支援 dataset freshness、row availability 與 ingest 成功狀態檢查。
- `rows_written = 0` 不能直接代表沒有天氣，只能代表該次 ingest 寫入筆數為 0。
- 失敗或部分失敗的 ingest run 應降低品質信心。

### 3.7 service_heartbeats

服務 heartbeat。

IB3W 解讀：

- 只作 operational monitoring。
- 不可當成直接天候證據。

### 3.8 location_admin_lookup

行政區查詢表。

IB3W 解讀：

- 可支援 route/activity point 的行政區查詢。
- 可協助用 county/town/village 找候選測站。
- 不可當成直接天候證據。

## 4. Adapter contract

IB3W adapter v1 應輸出 contextual evidence records，而不是 risk-adjusted scores。

建議最小輸出概念：

    activity_id
    route_folder
    case_id
    context_variable
    context_status
    source
    dataset_code
    station_id
    station_name
    obs_time_start
    obs_time_end
    activity_time_start
    activity_time_end
    coverage_ratio
    recency_minutes
    route_distance_m
    elevation_delta_m
    quality_flag
    quality_score
    value_min
    value_max
    value_mean
    value_last
    unit
    evidence_level
    notes

adapter 必須保留 source 與 quality 欄位，讓後續模組自行決定是否使用。

## 5. Context status contract

v1 允許狀態：

    OBSERVED
    IMPUTED
    MISSING
    UNKNOWN
    NO_SOURCE

保留給後續 hypothesis layer：

    INFERRED_FROM_BEHAVIOR

`INFERRED_FROM_BEHAVIOR` 不可混入 v1 observed/imputed context。它屬於後續 IB3W/IB3M hypothesis layer。

## 6. No-zero-fallback rules

以下解讀禁止使用：

    missing weather = normal weather
    missing rainfall = 0 mm
    missing wind = calm
    missing hydro = unchanged water level
    missing source = safe condition

舊版 zero-valued "normal baseline" 是 rewrite boundary，不可繼續作為 observed weather。

`0 mm` rainfall 只有在可信觀測資料明確回報活動時間窗內無降雨時才成立。

## 7. Station candidate selection policy

測站候選排序應考慮：

1. route distance
2. activity time coverage
3. update recency
4. elevation compatibility
5. source quality
6. variable availability
7. administrative locality match

只用距離選測站不足以支援山區路線，因為較近但低海拔或資料過舊的測站，可能不如稍遠但較新、海拔較相近、品質較穩定的測站。

## 8. Environment window extraction contract

對每個活動時間窗，adapter 應：

1. 找候選資料來源與測站。
2. 檢查活動時間窗內或容許 tolerance window 內的觀測紀錄。
3. 計算 coverage 與 recency。
4. 套用 source 與 QC gating。
5. 指派 context status。
6. 匯出包含品質欄位的 contextual evidence。
7. 不從缺資料合成 normal weather。

狀態指派：

    OBSERVED:
      可信來源在活動時間窗或容許時間窗內，有 target variable 的實際觀測紀錄。

    IMPUTED:
      使用明確方法估算，且必須保留 method、source、quality metadata。

    MISSING:
      相關來源或測站存在，但目標時間窗缺少必要紀錄或變數。

    UNKNOWN:
      schema/source 存在，但品質或語意不足以判斷。

    NO_SOURCE:
      對該 route/activity window 與 target variable 找不到合適來源或測站。

## 9. Prototype script reuse notes

### ib3b0_inspect_weather_database_schema.py

可作為 DB schema inventory / source adapter reference。

### ib3a_find_nearby_environment_stations.py

概念上可重用於 station discovery，但排序邏輯需改為 route distance、coverage、recency、elevation compatibility、quality、variable availability。

### ib3b_extract_environment_window.py

window extraction 核心概念可保留，但任何 zero-valued normal fallback 必須移除。缺資料應輸出 MISSING / UNKNOWN / NO_SOURCE，而不是合成正常天候。

### ib3b2_analyze_weather_station_update_frequency.py

高價值，可作為 temporal quality 與 antecedent-weather feature 設計參考。

### ib3b4_fuse_route_weather_conditions.py

可作 route-level aggregation 參考，但匯出前必須加入 source/quality gating。

### ib3e_extract_route_microclimate_terrain_features.py

可作 static terrain susceptibility input，但應與 observed weather context 分離。

### 暫緩腳本

以下腳本 v1 先暫緩，避免太早進入 risk adjustment 或 scenario output：

    ib3c_apply_environment_risk_adjustment.py
    ib3c2_compare_weather_trend_adjustment.py
    ib3d_plot_environment_adjusted_risk_profile.py
    ib3f_apply_weather_terrain_microclimate_interaction.py
    ib3x_run_bad_weather_scenario_0430.py
    thci_diagnose_weather_sensitivity_v1_0b.py
    thci_diagnose_weather_hydrology_topography_v1_0c_review.py

## 10. Smoke-test design

後續 smoke test 可只檢查單一路線／單一活動時間窗。

允許：

- 小量讀取 weather/hydro rows。
- 驗證 station candidate ranking 欄位。
- 驗證 OBSERVED / MISSING / NO_SOURCE 狀態指派。
- 驗證沒有 zero fallback。
- 驗證沒有改 route risk、radar、THCI。

禁止：

- 跑完整 pipeline。
- 掃大型 outputs。
- 建立正式 joined dataset。
- 做 IB3M behavior analysis。
- 調整 risk score。
- 調整 radar 或 THCI。

## 11. v1 non-goals

IB3W adapter v1 不做：

- final IB3W joined activity dataset
- full v1l2 to IB3W join
- infer weather from behavior
- adjust IB2 route risk
- adjust THCI
- adjust radar evidence
- classify behavior events
- treat missing data as normal conditions

## 12. Commit boundary

本分支預期 deliverables：

    runs/ib3w_weather_context_adapter_v1_notes_20260611.md
    configs/weather_context/ib3w_station_candidate_policy_v1.csv
    configs/weather_context/ib3w_environment_window_status_policy_v1.csv
    scripts/README_current_pipeline_updated_20260611_ib3w_weather_context_adapter.md

不要 stage 既有無關 working-tree changes。
