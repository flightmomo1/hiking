# IB3W Weather Context Consolidation v1 Notes

- 日期：2026-06-12
- 分支：codex/ib3w-weather-context-consolidation-v1
- 上游基底：f6ec72e Add IB3W adapter batch context summary
- 本分支範圍：IB3W QA ladder consolidation、formal adapter schema、pipeline positioning
- 非本分支範圍：新增處理腳本、row-level weather join、imputation、route risk / radar / THCI 調整

## 1. Consolidation 目的

IB3W 從 source inventory 到 adapter-batch-v1 已完成一條 QA ladder。這些腳本用來拆解 weather / hydro context 的資料語意，而不是全部作為正式 production pipeline 主入口。

本分支目的：

- 收斂目前 IB3W 腳本角色。
- 明確區分 QA prototype 與未來 formal adapter。
- 固化 no-zero-fallback rule。
- 定義 formal adapter activity-level context summary schema。
- 明確 station metadata elevation enrichment 應放的位置。
- 為下一段 formal adapter consolidation 做準備。

## 2. 已完成 IB3W 分支鏈

目前 IB3W 已完成：

    85c2fc3 smoke test v1
    a7b1563 station ranking v1
    5ca313b temporal coverage v1
    ea9c800 variable coverage v1
    df967d4 adapter row context summary v1
    f6ec72e adapter batch context summary v1

這條鏈的目的不是擴散永久腳本，而是建立可稽核的 weather context QA ladder。

## 3. QA ladder 角色整理

### 3.1 source inventory / schema contract

目的：

- 確認 weather DB / water DB 的表格與欄位。
- 確認 source_status。
- 確認 observation time range。
- 確認 rainfall / wind / temperature / water_level 可用欄位。

定位：

    data source inventory
    design evidence
    not production adapter

### 3.2 adapter contract / policy

目的：

- 定義 missing contextual evidence 的狀態。
- 明確禁止 zero-valued normal fallback。

核心規則：

    missing rainfall != 0 mm
    missing wind != calm
    missing temperature != normal
    missing water level != unchanged

定位：

    formal policy contract
    must be preserved by production adapter

### 3.3 smoke test v1

腳本：

    scripts/ib3_activity_environment/ib3w_smoke_test_weather_context_v1.py

目的：

- 對單一 activity 做最小 weather/water context check。
- 驗證 missing data remains MISSING。
- 驗證 zero_fallback_detected_count = 0。

定位：

    regression smoke test
    not production adapter

### 3.4 station ranking v1

腳本：

    scripts/ib3_activity_environment/ib3w_rank_weather_station_candidates_v1.py

目的：

- 找 weather Top-N station candidates。
- 找 water Top-N station candidates。
- 輸出 distance、source_status、初版 ranking_score。
- 建立 station candidate evidence。

定位：

    station candidate prototype
    logic should be absorbed into formal adapter

### 3.5 temporal coverage v1

腳本：

    scripts/ib3_activity_environment/ib3w_temporal_coverage_audit_v1.py

目的：

- 對 Top-N station candidates 回查 observation time series。
- 區分 station 是否有資料。
- 區分資料是否在 activity / tolerance window 內。
- 輸出 station-level temporal relation。

定位：

    station-level temporal coverage audit
    logic should be absorbed into formal adapter

### 3.6 variable coverage v1

腳本：

    scripts/ib3_activity_environment/ib3w_variable_coverage_audit_v1.py

目的：

- 將 station-level availability 拆成 variable-level availability。
- 分別檢查 precipitation_1hr、wind_speed、temperature、water_level。
- 區分 OUTSIDE_TOLERANCE、NULL_VALUE_ONLY、NO_STATION_RECORDS、NO_VARIABLE_COLUMN。

定位：

    core formal adapter logic candidate
    must be preserved in production adapter

### 3.7 adapter row context summary v1

腳本：

    scripts/ib3_activity_environment/ib3w_adapter_row_context_summary_v1.py

目的：

- 將 variable coverage audit rows 收斂成 activity-level context summary。
- 產出正式 context_status：
    OBSERVED
    MISSING
    NO_SOURCE
    UNKNOWN

定位：

    first activity-level adapter prototype
    should guide formal adapter schema

### 3.8 adapter batch context summary v1

腳本：

    scripts/ib3_activity_environment/ib3w_adapter_batch_context_summary_v1.py

目的：

- 讀取 one or more adapter-row context summaries。
- 合併 batch-level context rows。
- 產出 context_status / audit_status / variable_status counts。
- 驗證 required variables 與 zero_fallback。

定位：

    batch wrapper prototype
    QA/regression tool
    not final production adapter

## 4. Formal adapter 收斂方向

下一階段不應繼續新增大量分散 QA 腳本，而應收斂成正式 IB3W adapter 主入口。

建議正式主入口：

    scripts/ib3_activity_environment/ib3w_build_activity_context_v1.py

或未來搬移到：

    scripts/ib3_weather_context/ib3w_build_activity_context_v1.py

正式主入口應整合：

- activity window extraction
- representative activity location
- station candidate search
- station metadata enrichment
- station temporal coverage
- variable-level coverage
- selected station per variable
- formal context_status output
- QA summary output

正式主入口不應：

- impute missing values
- synthesize zero rainfall
- synthesize calm wind
- synthesize normal temperature
- synthesize unchanged water level
- directly modify route risk / radar / THCI

## 5. Formal adapter output schema

本分支新增：

    configs/weather_context/ib3w_formal_adapter_output_schema_v1.csv

此 schema 定義 activity-level context summary 欄位，作為 formal adapter 的輸出契約。

核心欄位：

    activity_id
    route_folder
    context_variable
    context_status
    audit_status
    selected_station_id
    selected_station_name
    selected_candidate_rank
    selected_route_distance_m
    selected_station_elevation_m
    station_elevation_source
    elevation_delta_m
    activity_start_time_utc
    activity_end_time_utc
    timestamp_epoch_used
    valid_records_in_activity
    valid_records_in_tolerance
    nearest_valid_obs_time
    nearest_valid_obs_gap_abs_minutes
    observed_value_mean
    observed_value_min
    observed_value_max
    observed_value_latest
    zero_fallback_detected
    selection_rule

## 6. Formal context_status

Formal adapter 應使用：

    OBSERVED
    MISSING
    NO_SOURCE
    UNKNOWN

建議 mapping：

    OBSERVED_IN_ACTIVITY  -> OBSERVED
    OBSERVED_IN_TOLERANCE -> OBSERVED

    OUTSIDE_TOLERANCE -> MISSING
    NULL_VALUE_ONLY   -> MISSING

    NO_STATION_RECORDS -> NO_SOURCE
    NO_VARIABLE_COLUMN -> NO_SOURCE

    others -> UNKNOWN

注意：

- MISSING 不等於 normal。
- MISSING 不等於 safe。
- MISSING 不應被 downstream 當成 0、calm、normal、unchanged。
- audit_status 必須保留，避免 MISSING 變成黑盒。

## 7. Station metadata elevation enrichment

目前狀態：

- weather station 若 DB 有 elevation_m，station ranking v1 已可使用。
- water station 目前缺 elevation_m。
- 尚未正式用 station lat/lon 查 DEM/NLSC elevation。
- 尚未建立 station metadata with elevation cache。

後續應新增 station metadata enrichment，但不建議塞在 adapter-row 或 adapter-batch。

建議位置：

    before station ranking
    or inside formal adapter station metadata step

建議未來產物：

    outputs/ib3w_station_metadata_v1/ib3w_station_metadata_with_elevation.csv

建議欄位：

    source
    dataset_code
    station_id
    station_name
    latitude
    longitude
    db_elevation_m
    terrain_lookup_elevation_m
    elevation_source
    elevation_lookup_status

用途：

- 補 water station elevation。
- 統一 weather/water station elevation source。
- 支援 elevation_delta_m。
- 提升 station ranking 品質。

## 8. Production / QA 分流建議

正式 production scripts 應少量化：

    ib3w_build_activity_context_v1.py
    ib3w_build_batch_activity_context_v1.py

QA / regression scripts 可保留：

    ib3w_smoke_test_weather_context_v1.py
    ib3w_rank_weather_station_candidates_v1.py
    ib3w_temporal_coverage_audit_v1.py
    ib3w_variable_coverage_audit_v1.py
    ib3w_adapter_row_context_summary_v1.py
    ib3w_adapter_batch_context_summary_v1.py

長期可以考慮移至：

    scripts/ib3_weather_context/qa/

但本分支不搬檔，避免大範圍變更。

## 9. Pipeline 定位

IB3W 應定位為：

    Weather / Hydro Context Evidence Layer

它不取代：

- IB2D route risk
- IB3F activity features
- IB3M behavior interpretation
- THCI / radar score

IB3W 應輸出 contextual evidence，供後續安全判斷使用。

建議 pipeline 位置：

    IB3A / IB3F activity features
        +
    IB2D route risk / terrain risk
        +
    IB3W weather / hydro context
        ↓
    IB3M or future decision layer

## 10. No-zero-fallback rule

IB3W 必須永久保留：

    missing rainfall != 0 mm
    missing wind != calm
    missing temperature != normal
    missing water level != unchanged

Formal adapter 的所有輸出都必須包含：

    zero_fallback_detected

其值在正常情況下必須為：

    false

若任何流程產生 true，應視為 QA failure。

## 11. 下一步建議

下一段建議：

    codex/ib3w-weather-context-formal-adapter-v1

範圍：

- 建立 formal adapter 主入口。
- 整合現有 station ranking、temporal coverage、variable coverage、context summary 邏輯。
- 仍只輸出 activity-level context summary。
- 仍不做 row-level weather join。
- 仍不做 imputation。
- 仍不改 THCI/radar/route risk。

下一段也可先做：

    codex/ib3w-station-metadata-elevation-v1

範圍：

- 抽 unique weather/water stations。
- 補 station elevation metadata。
- 建立 station metadata cache。
- 再讓 formal adapter 使用。

優先順序建議：

    1. station metadata elevation v1
    2. formal adapter v1
