# IB3W Station Metadata Elevation v1 Notes

- 日期：2026-06-12
- 分支：codex/ib3w-station-metadata-elevation-v1
- 上游基底：5c0eee7 Document IB3W weather context consolidation
- 本分支範圍：station metadata extraction and elevation gap audit
- 非本分支範圍：DEM/NLSC terrain lookup、station ranking 改寫、formal adapter、row-level weather join、imputation、route risk / radar / THCI 調整

## 1. 本分支目的

IB3W consolidation 已確認 formal adapter 前需要 station metadata elevation enrichment。

本分支先建立 station metadata elevation cache 的前置盤點：

- 從 weather SQLite DB 抽出 unique weather / water stations。
- 保留 station_id、station_name、latitude、longitude、source、dataset_code。
- 檢查 DB 是否已有 elevation 欄位可用。
- 若沒有 DB elevation，標記為 NEED_TERRAIN_LOOKUP。
- 輸出 station metadata cache 與 summary。
- 不執行 DEM/NLSC terrain lookup。

## 2. 新增 policy

新增：

    configs/weather_context/ib3w_station_metadata_elevation_policy_v1.csv

定義欄位：

    source
    station_type
    dataset_code
    station_id
    station_name
    latitude
    longitude
    db_elevation_m
    terrain_lookup_elevation_m
    elevation_source
    elevation_lookup_status
    needs_terrain_lookup
    metadata_source_table
    metadata_status
    notes

v1 允許：

    elevation_source = terrain_lookup_pending
    elevation_lookup_status = NEED_TERRAIN_LOOKUP

表示該測站有座標，但 DB 沒有 elevation，需要後續 DEM/NLSC lookup。

## 3. 新增腳本

新增：

    scripts/ib3_activity_environment/ib3w_build_station_metadata_elevation_v1.py

腳本功能：

- 讀取 SQLite DB。
- 從 weather_observations 抽 weather stations。
- 從 water_level_observations 抽 water stations。
- 從 wra_station_metadata 抽 water station metadata。
- 自動偵測常見欄位名稱。
- 產出 station metadata elevation cache。
- 產出 status summary。
- 產出 HTML report。

本版不查 DEM/NLSC，只做 metadata extraction 與 elevation gap audit。

## 4. QA 執行命令

執行命令：

    .\.venv\Scripts\python.exe scripts\ib3_activity_environment\ib3w_build_station_metadata_elevation_v1.py `
      --weather-db weather\tw_weather_2026-05-01.sqlite3 `
      --out-dir outputs\ib3w_station_metadata_elevation_v1

注意：

- 使用 project venv。
- 系統 python 無 pandas，曾出現 ModuleNotFoundError: No module named 'pandas'。
- 改用 .\.venv\Scripts\python.exe 後成功。

## 5. QA outputs

輸出：

    outputs\ib3w_station_metadata_elevation_v1\ib3w_station_metadata_elevation_v1.csv
    outputs\ib3w_station_metadata_elevation_v1\ib3w_station_metadata_elevation_summary_v1.csv
    outputs\ib3w_station_metadata_elevation_v1\ib3w_station_metadata_elevation_v1.html

outputs 僅作 QA 證據，不 commit。

## 6. QA 結果摘要

執行結果：

    station_rows = 1483
    db_elevation_available_rows = 0
    need_terrain_lookup_rows = 1483

Summary：

    cwa weather weather_observations NEED_TERRAIN_LOOKUP true = 652
    wra water water_level_observations NEED_TERRAIN_LOOKUP true = 360
    wra water wra_station_metadata NEED_TERRAIN_LOOKUP true = 471

## 7. 重要發現

本輪最重要發現：

    DB elevation available = 0

也就是目前 weather / water SQLite DB 可提供 station lat/lon，但沒有任何可直接使用的 station elevation。

因此，IB3W formal adapter 若要計算：

    selected_station_elevation_m
    elevation_delta_m

必須另接 terrain elevation source。

目前所有 station rows 都標記為：

    elevation_lookup_status = NEED_TERRAIN_LOOKUP
    needs_terrain_lookup = true

## 8. 關於 weather station elevation

前面曾推測 weather_observations 可能含 elevation_m。

本分支實測結果顯示：

    weather_observations extracted station rows = 652
    DB_ELEVATION_AVAILABLE = 0
    NEED_TERRAIN_LOOKUP = 652

因此在目前這份 DB 內，weather station elevation 也不能視為已存在。

## 9. 關於 water station metadata

water stations 來源包含：

    water_level_observations = 360
    wra_station_metadata = 471

v1 先保留兩個來源的 station metadata rows。

已知限制：

- water_level_observations 與 wra_station_metadata 可能有重複 station_id。
- 兩表座標或 metadata 來源可能略有差異。
- v1 不做 final station registry dedup。
- 後續 formal station metadata registry 應定義 source priority 與 coordinate conflict handling。

## 10. 本分支結論

本分支完成：

    station metadata extraction
    elevation gap audit
    station metadata cache schema
    all stations marked NEED_TERRAIN_LOOKUP

本分支未完成：

    DEM/NLSC lookup
    station elevation interpolation
    station ranking 改寫
    formal adapter 整合
    elevation_delta_m 實算

## 11. 下一步建議

下一段建議開：

    codex/ib3w-station-terrain-elevation-lookup-v1

目標：

- 選定正式 terrain elevation source。
- 讀取 station metadata cache。
- 依 station lat/lon 查 terrain elevation。
- 輸出 terrain_lookup_elevation_m。
- 產生 elevation_lookup_status：
    TERRAIN_ELEVATION_FOUND
    TERRAIN_ELEVATION_MISSING
    OUTSIDE_TERRAIN_COVERAGE
- 保留 db_elevation_m 與 terrain_lookup_elevation_m 的來源差異。
- 不修改 station ranking，先只補 metadata cache。

完成 terrain lookup 後，再進：

    codex/ib3w-weather-context-formal-adapter-v1

由 formal adapter 使用 enriched station metadata。
