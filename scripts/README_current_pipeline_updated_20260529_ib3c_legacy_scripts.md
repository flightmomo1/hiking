# 115_osm Current Pipeline README  
# 115_osm 目前流程交接文件

> 本文件是 `115_osm / 山力分析 Prototype A` 的主流程交接文件，用於記錄目前正式 pipeline、腳本版本、輸出路徑、已知問題與下一步工作。  
> This document is the main handoff README for the `115_osm / Mountain Analysis Prototype A` project. It records the current official pipeline, script versions, output paths, known issues, and next work items.

> 使用方式：開新 GPT 分頁時，建議先貼 `runs/latest_handoff_prompt.md`；若需要完整架構，再補貼本文件。  
> Usage: For a new GPT session, paste `runs/latest_handoff_prompt.md` first. Paste this README only when the full pipeline structure is needed.


---

### 冷水坑七星山主峰 GPX 20260523：正式標準主線已升級為 forced-required-way 版本

`qixing_lengshuikeng_main_peak_20260523` 已完成強制必經路段縫合（forced required-way stitching）正式化。新版正式路線軸長度為 `4187.39 m`，取代舊版約 `4147.63 m` 的主線。

本次修正目的，是解決 IB0B 標準主線抽取時，只納入上山側必經路段、但漏選下山側必經路段的問題。

#### 路線控制點與 required way

```text
via_up / ascent_via:
  required_way_id = 15
  in_mainline = True

via_down / descent_via:
  required_way_id = 116
  in_mainline = True
```

正式 IB0B 驗證：

```text
required_way_ids: 116,15
selected_required_way_ids: 116,15
missing_required_way_ids: (none)
required_way_all_present_in_input: True
required_way_all_present_in_mainline: True
ordered path length m: 4187.39
```

#### 正式輸出流程

目前正式輸出已完成：

```text
IB0B 強制必經路段縫合（forced required-way stitching）
→ IB0D 修剪與自近鄰 QA（trim / self-near QA）
→ IB1A 路線剖面（route profile）
→ IB1C OSM 語意補值（OSM semantic enrichment）
→ IB1C OSM 語意風險稽核／套用（semantic risk audit/apply）
→ IB1G NLSC 等高線視窗（NLSC contour window）
→ IB1E OSM + NLSC 地形整合（terrain enrichment）
→ IB1E 剖面圖／地圖輸出（profile/map plot）
→ IB2D 離線風險地圖（offline map）
```

正式輸出資料夾：

```text
outputs\ib0b_mainline\qixing_lengshuikeng_main_peak_20260523\
outputs\ib0d_trimmed_mainline\qixing_lengshuikeng_main_peak_20260523\
outputs\ib1_route_profile\qixing_lengshuikeng_main_peak_20260523\
outputs\ib1c_route_profile_semantics\qixing_lengshuikeng_main_peak_20260523\
outputs\ib1c_osm_semantic_audit\qixing_lengshuikeng_main_peak_20260523\
outputs\ib1c_osm_semantic_risk\qixing_lengshuikeng_main_peak_20260523\
outputs\ib1g_contour_window_features\qixing_lengshuikeng_main_peak_20260523\
outputs\ib1e_route_profile_contour_window_terrain\qixing_lengshuikeng_main_peak_20260523\
outputs\ib1e_osm_nlsc_terrain_risk_plot\qixing_lengshuikeng_main_peak_20260523\
outputs\ib2d_route_risk_offline_map\qixing_lengshuikeng_main_peak_20260523\
```

#### 目前正式結果摘要

```text
IB0D trimmed_len_m: 4187.392949094119
IB0D route_point_count: 4189
IB0D self_near_zone_count: 3

IB1A route_len_m: 4187.39
IB1A cum_gain_m: 463.02
IB1A cum_loss_m: 464.29

IB1E contour_window_match_status:
  matched 4189

IB1E dist_to_contour_window_mid_m max:
  10.00 m

IB1E osm_terrain_combined_risk_band:
  moderate 2458
  low      1731

IB2D segment risk_band:
  moderate 2470
  low      1718
```

#### 重要備註

舊正式輸出已備份於：

```text
outputs\_backup_before_forced_required_way_20260529_002919\qixing_lengshuikeng_main_peak_20260523\
```

風險閾值本次未調整。新版主線仍保留入口／回程附近的「極陡坡（very_steep）+ 水文（waterway）+ 水文地形放大分數（hydro_terrain_amplifier_score）= 0.45」訊號，但目前整合風險分數約為 `0.3995`，略低於 high 閾值 `0.40`，因此仍歸類為 moderate。此現象暫記為地形—水文高風險候選現象（terrain-hydro high candidate），待多條路線比較後再校準。


#### forced-required-way route axis 責任邊界：標準路線不等於每筆活動實際路徑

本次 `IB0B forced-required-way stitching` 的定位，是建立「標準路線軸（standard route axis）」，用於後續 IB1A / IB1C / IB1G / IB1E / IB2D 的路線層級風險分析。它不代表每一筆活動軌跡都實際通過所有 required ways。

```text
forced-required-way route axis 用於標準路線定義與路線層級風險分析，不代表每一筆活動都實際通過所有 required ways。
活動層級 mapmatching 應以實際軌跡為主；若活動軌跡未走標準 required-way branch，後續 IB3A / IB3C 應以 branch-aware / behavior-aware 方式判斷實際通過分支、停留、繞行與再接回主線事件。
```

工程責任邊界：

```text
IB0B:
  forced-required-way 是 standard route definition constraint。
  目標是產生我們指定的正式標準路線。

IB1A / IB1C / IB1G / IB1E / IB2D:
  使用 standard route axis 做路線剖面、OSM 語意、NLSC 地形與路線風險分析。

IB3A / IB3A2 / IB3B2:
  應注意活動資料不一定完全遵守 standard route axis。
  若活動實際未走標準 required-way branch，可能出現 off-route、branch ambiguity、endpoint artifact 或 on-route profile 空白。

IB3C:
  後續應補上活動行為事件偵測，將低速、停留、離線、繞行、心率恢復、導航確認、設施或景點停留視為可解釋的活動行為，而不是單純視為無效資料。
```

因此，冷水坑 forced-required-way 正式主線目前仍保留作為標準路線；活動層差異由後續 IB3A / IB3C 的 branch-aware 與 behavior-aware 判斷處理。


### IB3C activity behavior event detection 規劃

後續建議新增：

```text
scripts\ib3_activity_environment\ib3c_detect_activity_behavior_events.py
```

IB3C 不取代 IB3A / IB3A2，而是新增活動行為解釋層：

```text
IB3A:
  活動點壓回 route axis，建立 sequence mapmatching。

IB3A2:
  判斷哪些資料可用於主線速度 / 心率模型。

IB3C:
  解讀低速、停留、離線、繞行、心率恢復、導航確認、景點停留、設施停留、天候影響等活動行為事件。
```

第一版判斷因子：

```text
速度 < X m/s
+ 持續時間 > Y1 / Y2 / Y3
+ 心率狀態
+ OSM 設施 / 路面 / 路線語意
+ NLSC 地形 / 坡度 / 風險段
+ on-route / off-route 狀態
+ 天候狀況 / 天候敏感度
→ 判斷停留原因與風險意義
```

建議預設值：

```text
X  = 0.30 m/s
Y1 = 15 sec    → short_pause / micro_pause
Y2 = 60 sec    → rest_or_navigation_check
Y3 = 180 sec   → extended_rest_or_detour
```

天候資料需自第一版預留三種模式：

```text
weather_mode = baseline
weather_mode = scenario
weather_mode = observed
```

IB3C 事件輸出可包含：

```text
event_id
activity_id
event_type
event_subtype
start_elapsed_sec
end_elapsed_sec
duration_sec
start_route_dist_m
end_route_dist_m
route_dist_span_m
mean_speed_mps
median_offset_m
max_offset_m
on_route_ratio
off_route_ratio
mean_hr_bpm
max_hr_bpm
hr_start_bpm
hr_end_bpm
hr_delta_bpm
hr_recovery_slope_bpm_per_min
nearest_facility_type
nearest_facility_dist_m
route_semantic_context
surface_context
terrain_risk_context
weather_context
weather_event_modifier
activity_risk_context
candidate_reason
confidence
```

建議事件類型：

```text
moving_on_route
short_pause
navigation_check
facility_rest
scenic_stop
recovery_stop
high_hr_recovery_stop
off_route_detour
off_route_rest
route_uncertainty_stop
route_rejoin
terminal_artifact
unknown_stationary
```


### 既有 IB3C 相關腳本盤點：legacy / supporting scripts

目前已存在數支名稱含 `ib3c` 的舊腳本或環境風險支援腳本。這些腳本可作為新版 IB3C 的素材，但不應直接視為新版 `activity behavior event detection` 已完成。

```text
ib3c_overlay_activity_with_route_risk.py
  定位：舊版 activity × route risk overlay。
  功能：將 IB3A mapmatched activity 依 route_dist_m 疊合到 IB2/IB2_v3 route segment risk。
  可保留作為新版 IB3C 的 route-risk context join 基礎。
  尚缺：low-speed / stationary block detection、duration tier、HR recovery interpretation、OSM/NLSC/weather context event classification。

ib3c_plot_gpx_station_map.py
  定位：weather / hydro station QA visualization。
  功能：繪製 GPX route、路線中心、氣象站、水文站與測站標籤。
  屬於環境資料視覺化輔助工具，不是活動行為事件偵測核心。
  後續可歸入 IB3 environment QA map。

ib3c_apply_environment_risk_adjustment.py
  定位：route-level weather / hydro adjusted risk。
  功能：將 weather summary、fused route weather、water summary 與 OSM semantic sensitivity 結合，產生 environment_adjusted_risk_score / band。
  可提供新版 IB3C 的 environment risk context。
  不直接判斷活動停留事件。

ib3c2_compare_weather_trend_adjustment.py
  定位：weather trend adjustment A/B comparison。
  功能：比較 original weather adjustment 與 trend compensation adjustment，處理雨量 0 但高濕、霧雨、前期雨或資料更新頻率粗造成的濕滑低估。
  屬於天候修正方法 QA / comparison，不放在新版 IB3C 第一版主流程。
```

新版 IB3C 主腳本建議仍新增：

```text
scripts\ib3_activity_environment\ib3c_detect_activity_behavior_events.py
```

第一版主腳本應從既有 `point overlay` 升級為：

```text
point overlay
→ low-speed / stationary block detection
→ duration-tier event segmentation
→ HR status / recovery interpretation
→ on-route / off-route / terminal-artifact context
→ OSM / NLSC / route-risk / weather context join
→ event-level classification and summary
```



## 0. 最新狀態摘要 / Latest Status Update — 2026-05-26 evening

本次更新重點是把七星山兩條 GPX case 從 `ib0` 到 `ib1e` 重新接通，並修正兩個會影響後續風險軸的重要問題：

1. 小油坑開頭雜支問題：`ib0d v1.2 trim_leading` 已移除登山口前約 503 m leading spur。  
2. NLSC contour window 距離軸壓縮問題：`ib1g v1.1 true route-axis distance` 已修正原本用 chord length 累積造成尾段缺覆蓋的問題。  
3. OSM semantic risk mapping 已補齊 `surface=paving_stones` 與 `highway=service`，兩條七星山 audit coverage 均為 `1.000`。  
4. CSV 編碼統一改為 Windows / Excel 友善的 UTF-8 with BOM (`utf-8-sig`)。

目前七星山正式 active cases：

```text
qixing_xiaoyoukeng_main_peak_20260315
小油坑七星山主峰 GPX 20260315

qixing_lengshuikeng_main_peak_20260523
冷水坑到七星山主峰 GPX 20260523
```

七星山目前完成階段：

```text
ib0  activity → OSM route match
ib0c activity + OSM landmarks → route anchors
ib0b matched OSM segments + anchors → ordered mainline
ib0d v1.2 trim_leading → trimmed mainline
ib1a route elevation profile
ib1c route profile semantic enrichment
ib1c OSM semantic risk audit / apply
ib1g v1.1 NLSC contour window features
ib1e OSM + NLSC contour-window terrain enrichment
```

目前下一步：

```text
1. CLI 化 / 重跑 ib1e_plot_osm_nlsc_terrain_risk_profile.py
2. 接 ib2_v2_route_risk_scoring.py
3. 接 ib2a / ib2_v3 / ib2b / ib2c
4. 最後接 ib2d_plot_route_risk_offline_map.py
```

七星山最新核心結果：

```text
小油坑 qixing_xiaoyoukeng_main_peak_20260315
- ib0d / ib1a route_len_m: 3330.24
- ib1a points: 3332
- cum_gain_m / cum_loss_m: 336.24 / 341.08
- ib1c OSM semantic risk mean: 0.174377
- ib1c risk bands: low 1755, moderate 1577
- ib1g v1.1 dist_mid max: 3325.12
- ib1e contour alignment: matched 3332 / 3332, max align diff 10.00 m
- ib1e combined risk bands: low 599, moderate 1699, high 1034

冷水坑 qixing_lengshuikeng_main_peak_20260523
- ib0d / ib1a route_len_m: 4147.63
- ib1a points: 4149
- cum_gain_m / cum_loss_m: 487.78 / 481.85
- ib1c OSM semantic risk mean: 0.092847
- ib1c risk bands: low 4149
- ib1g v1.1 dist_mid max: 4143.81
- ib1e contour alignment: matched 4149 / 4149, max align diff 10.00 m
- ib1e combined risk bands: low 984, moderate 3036, high 129
```


## 1. 目前穩定流程 / Current Stable Flow

本文件用來記錄 `115_osm` 專案目前可穩定執行的流程、正式腳本版本、輸出資料夾，以及下一步開發方向。

This document records the current stable pipeline, official script versions, output folders, and next development steps for the `115_osm` project.

目前主要案例 / Current cases:

- Case ID: `juansi_waterfall_fitcsv_20260315` is not used. The official small-oil-pit case is `qixing_xiaoyoukeng_main_peak_20260315`.
- Case ID: `qixing_xiaoyoukeng_main_peak_20260315`
  - Case name: `小油坑七星山主峰 GPX 20260315`
  - Latest completed stage: `ib1e_route_profile_contour_window_terrain`
- Case ID: `qixing_lengshuikeng_main_peak_20260523`
  - Case name: `冷水坑到七星山主峰 GPX 20260523`
  - Latest completed stage: `ib1e_route_profile_contour_window_terrain`
- Reference / legacy validated case: `juansi_waterfall_fitcsv_20260503`
- Model version: `prototype_A_terrain_dominant_v1`

目前穩定輸出 / Current stable output:

```text
Prototype A:
OSM semantic risk
+ NLSC contour window terrain risk
+ hydro-terrain amplifier
→ route risk zones
→ candidate waypoints
```

目前 Prototype A 的定位：

```text
路線客觀負荷與路線關卡辨識模型
Route demand and route challenge extraction model
```

Prototype A 目前不是最終的個人安全模型，而是用來辨識路線上的高風險區間、路線關卡、恢復點、決策點與候選中繼點。

Prototype A is not yet a final personal safety model. It is currently used to identify risk zones, route challenge sections, recovery points, decision points, and candidate waypoints.

---

## 2. 專案根目錄 / Project Root

所有指令建議都從以下目錄執行：

All commands should be executed from the following project root:

```powershell
cd "C:\mountain_work\115_osm"
```

使用本專案的 Python 虛擬環境：

Use the project virtual environment:

```powershell
& ".\.venv\Scripts\python.exe" "<script_path>"
```

例如：

Example:

```powershell
& ".\.venv\Scripts\python.exe" ".\scripts\ib1_nlsc_terrain\ib1h_plot_candidate_waypoints_map.py"
```

---

## 3. 正式腳本版本原則 / Official Script Version Policy

當多個腳本名稱相近時，請依照以下原則選用：

When multiple scripts have similar names, use the following rules:

```text
1. 優先使用 scripts 下分類資料夾內的腳本。
   Prefer scripts inside categorized folders under scripts\.

2. 若有版本號，例如 _v1_2、_v1.1、v2、abtest_v1，通常優先檢查版本號較新的腳本。
   If version-suffixed scripts exist, such as _v1_2, _v1.1, v2, or abtest_v1, verify and prefer the latest stable version.

3. 不要直接使用 scripts 根目錄下的 duplicate 腳本，除非已明確確認。
   Do not use root-level duplicate scripts unless explicitly verified.

4. 每次正式納入 pipeline 的腳本，都要在本 README 記錄。
   Every script officially adopted into the pipeline should be recorded in this README.
```

Script maintenance preference:

```text
When updating existing scripts, preserve the user's original Chinese comments,
section structure, naming style, and notebook-like explanation wherever possible.
Prefer targeted fixes and case/path adaptation over rewriting the script into a
new English framework unless explicitly requested.
```

Encoding / Windows display rule:

```text
When writing text or Markdown outputs from Python, use encoding="utf-8".
When writing CSV outputs from Python, use encoding="utf-8-sig" for Windows / Excel friendliness.
When reading Chinese text files in PowerShell, use Get-Content -Encoding UTF8.
If UTF-8 reads still show mojibake, treat the source .py / .md / .txt content as already corrupted and repair the original text in UTF-8, instead of treating it as only a PowerShell display issue.
Example repair: CASE_NAME should be "絹絲瀑布 FIT CSV 20260503", not mojibake text.
```

Important CSV note:

```text
For user-facing CSV files with Traditional Chinese text, prefer UTF-8 with BOM
(`encoding="utf-8-sig"` in Python). This is especially important for files that
may be opened directly in Excel, such as config\nlsc_tile_activity_mapping.csv.
If a CSV has already been overwritten with question marks or mojibake, repair the
source content itself, then rewrite with utf-8-sig.
```

目前正式採用版本 / Current official script versions:

| Stage | 中文說明 | Official script / current preferred version |
|---|---|---|
| Ia1 | OSM 原始語意圖層抓取；v1.3 增加 scenic / destination / facility raw layers | `scripts\ia_osm\ia1_osm_fetch_raw_v1_3.py` |
| ib0 | GPX / FIT CSV / CSV 三位一體 activity → OSM route match | `scripts\ib0_route_match\ib0_gpx_to_osm_route_v1_cli_updated.py` |
| ib0c | activity + OSM landmarks → start / via / end anchors | `scripts\ib0_route_match\ib0c_anchor_from_landmarks_v1_2_cli_updated.py` |
| ib0b | matched OSM segments + anchors → ordered mainline | `scripts\ib0_route_match\ib0b_route_mainline_extract_abtest_v1_cli_updated.py` |
| ib0d | ordered mainline + anchors → trimmed mainline；same-entry route 可用 `trim_leading` | `scripts\ib0_route_match\ib0d_trim_ordered_mainline_by_anchors_v1_2_cli_updated.py` |
| ib1a | trimmed mainline + activity elevation → route elevation profile | `scripts\ib1_route_profile\ib1a_build_route_elevation_profile_cli_updated.py` |
| ib1c | route profile + OSM raw semantic layers → semantic enriched profile | `scripts\ib1_route_profile\ib1c_enrich_route_profile_semantics_cli_updated.py` |
| ib1c audit | semantic enriched profile + mapping table → mapping coverage audit | `scripts\ib1_osm_semantics\ib1c_audit_osm_semantic_risk_mapping_cli_updated.py` |
| ib1c apply | semantic enriched profile + mapping table → OSM semantic risk profile | `scripts\ib1_osm_semantics\ib1c_apply_osm_semantic_risk_mapping_cli_updated.py` |
| ib1g | ib0d trimmed mainline + NLSC ContourL.shp → contour window terrain features；v1.1 修正 true route-axis distance | `scripts\ib1_nlsc_terrain\ib1g_v2_compute_contour_window_features_cli_updated_v1_1.py` |
| ib1e | ib1c OSM semantic risk + ib1g contour window terrain → OSM + NLSC terrain enriched profile | `scripts\ib1_nlsc_terrain\ib1e_enrich_route_profile_with_contour_window_terrain_cli_updated.py` |
| ib1e plot | OSM + NLSC terrain enriched profile → PNG / HTML risk profile QA | `scripts\ib1_nlsc_terrain\ib1e_plot_osm_nlsc_terrain_risk_profile.py` currently needs CLI check/update |
| ib1i | GPX/FIT elevation vs NLSC contour-window QA validation | `scripts\ib1_nlsc_terrain\ib1i_validate_gpx_vs_contour.py` |
| ib1f | Prototype A 風險路段摘要 | `scripts\ib1_nlsc_terrain\ib1f_summarize_prototype_A_risk_segments.py` |
| ib1g zones | 連續風險區合併與地圖 | `scripts\ib1_nlsc_terrain\ib1g_merge_prototype_A_risk_zones.py`, `scripts\ib1_nlsc_terrain\ib1g_plot_prototype_A_risk_zones_map.py` |
| ib1h | risk / scenic / facility candidate waypoint 產生、合併、投影與地圖 | `scripts\ib1_nlsc_terrain\ib1h_generate_candidate_waypoints_from_risk_zones.py`, `ib1h_generate_scenic_candidate_waypoints_from_osm.py`, `ib1h_merge_risk_and_scenic_candidate_waypoints.py`, `ib1h_project_candidate_waypoints_to_route.py`, `ib1h_plot_candidate_waypoints_map.py` |
| ib2 | 舊版 route risk scoring v2 | `scripts\ib2_route_risk\ib2_v2_route_risk_scoring.py` |
| ib2 | 舊版 route segment risk v3 | `scripts\ib2_route_risk\ib2_v3_route_segment_risk.py` |
| ib2b | 舊版 route segment risk profile 視覺化 | `scripts\ib2_route_risk\ib2b_v2_plot_route_segment_risk_profile.py` |
| ib2d | NLSC contour + OSM POI + route risk offline QA map | `scripts\ib2_route_risk\ib2d_plot_route_risk_offline_map.py` |
| ib3a | high-frequency activity map matching to route distance axis | `scripts\ib3_activity_environment\ib3a_mapmatch_highfreq_activity.py` |
| ib3b | mapmatched activity profile QA visualization | `scripts\ib3_activity_environment\ib3b_plot_mapmatched_activity_profile.py` |
| ib3 batch | Juansi Waterfall multi-activity ib3a → ib3b batch runner | `scripts\ib3_activity_environment\ib3_batch_run_juansi_activities.py` |
| ib3d | 活動風險時間線報告 | `scripts\ib3_activity_environment\ib3d_v2_plot_activity_risk_timeline_report.py` |

Important version notes:

```text
ib0d v1.2:
  Use --same-entry-policy trim_leading for Qixing same-entry routes.
  This removes the leading spur before the trailhead anchor while preserving the out-and-back route.

ib1g v1.1:
  Use true route-axis distance with shapely substring.
  Do not use the older chord-length accumulation output for ib1e alignment.

CSV encoding:
  All user-facing CSVs with Chinese text should be written as utf-8-sig.
```

---

## 4. Prototype A 模型定義 / Prototype A Model Definition

模型版本 / Model version:

```text
prototype_A_terrain_dominant_v1
```

模型定位：

```text
以 NLSC 地形為主導，結合 OSM 語意與水文地形放大因子的路線風險 prototype。
```

English summary:

```text
A terrain-dominant route risk prototype combining OSM semantic risk, NLSC contour-derived terrain risk, and hydro-terrain amplification.
```

輸入資料 / Inputs:

```text
1. ib1c OSM semantic risk profile
2. ib1g NLSC contour window terrain features
```

核心分數 / Core scores:

```text
osm_semantic_risk_score
terrain_window_risk_score
hydro_terrain_amplifier_score
osm_terrain_combined_risk_score
```

目前權重 / Current weights:

```text
OSM semantic:             0.35
NLSC terrain window:      0.45
Hydro-terrain amplifier:  0.20
```

模型解釋：

```text
OSM semantic risk：
描述路線型態、鋪面材質、水文鄰近、可辨識度、設施與支援環境。

NLSC contour window terrain risk：
描述局部地形起伏、坡度、高程變化與等高線密集程度。

Hydro-terrain amplifier：
當 waterway / wetland 與陡地形、鋪石路面、階梯等條件重疊時，用來放大水文與地形交互風險。
```

English summary:

```text
OSM semantic risk describes route semantics, surface, hydrology proximity, visibility, facilities, and support context.

NLSC contour window terrain risk describes local terrain steepness, elevation variation, and contour-derived terrain complexity.

Hydro-terrain amplifier increases risk when waterway or wetland proximity overlaps with steep terrain or weather-sensitive surface conditions.
```

---

## 5. 目前正式 Pipeline 順序 / Official Pipeline Order

### 5.1 七星山目前正式已完成流程 / Current Qixing completed pipeline

目前兩條七星山 GPX (`qixing_xiaoyoukeng_main_peak_20260315`, `qixing_lengshuikeng_main_peak_20260523`) 已完成到 `ib1e`：

```text
ib0_gpx_to_osm_route_v1_cli_updated.py
↓
ib0c_anchor_from_landmarks_v1_2_cli_updated.py
↓
ib0b_route_mainline_extract_abtest_v1_cli_updated.py
↓
ib0d_trim_ordered_mainline_by_anchors_v1_2_cli_updated.py
↓
ib1a_build_route_elevation_profile_cli_updated.py
↓
ib1c_enrich_route_profile_semantics_cli_updated.py
↓
ib1c_audit_osm_semantic_risk_mapping_cli_updated.py
↓
ib1c_apply_osm_semantic_risk_mapping_cli_updated.py
↓
ib1g_v2_compute_contour_window_features_cli_updated_v1_1.py
↓
ib1e_enrich_route_profile_with_contour_window_terrain_cli_updated.py
```

目前下一步：

```text
ib1e_plot_osm_nlsc_terrain_risk_profile.py
↓
ib2_v2_route_risk_scoring.py
↓
ib2a_plot_route_risk_profile.py
↓
ib2_v3_route_segment_risk.py
↓
ib2b_v2_plot_route_segment_risk_profile.py
↓
ib2c_plot_route_risk_map_2d.py
↓
ib2d_plot_route_risk_offline_map.py
```

### 5.2 Prototype A / Juansi reference pipeline

`juansi_waterfall_fitcsv_20260503` 仍可作為 reference / legacy validated case。若要重跑，請依照分類資料夾內正式腳本版本，避免使用 `scripts\` 根目錄 duplicate scripts。

---


## 6. 目前 Prototype A 輸出 / Current Prototype A Outputs

主要輸出資料夾：

Main output folder:

```text
outputs\prototype_A_terrain_dominant\juansi_waterfall_fitcsv_20260503
```

重要輸出檔案：

Important output files:

```text
juansi_waterfall_fitcsv_20260503_prototype_A_risk_segments_100m.csv
juansi_waterfall_fitcsv_20260503_prototype_A_high_risk_segments.csv
juansi_waterfall_fitcsv_20260503_prototype_A_risk_zones.csv
juansi_waterfall_fitcsv_20260503_prototype_A_high_risk_zones.csv
juansi_waterfall_fitcsv_20260503_prototype_A_risk_zones.geojson
juansi_waterfall_fitcsv_20260503_prototype_A_risk_zones_map.html
juansi_waterfall_fitcsv_20260503_prototype_A_candidate_waypoints_by_distance.csv
juansi_waterfall_fitcsv_20260503_prototype_A_candidate_waypoints_projected.csv
juansi_waterfall_fitcsv_20260503_prototype_A_candidate_waypoints_projected.geojson
juansi_waterfall_fitcsv_20260503_prototype_A_candidate_waypoints_map.html
juansi_waterfall_fitcsv_20260503_prototype_A_scenic_candidate_waypoints_by_distance.csv
juansi_waterfall_fitcsv_20260503_prototype_A_scenic_candidate_waypoints.geojson
juansi_waterfall_fitcsv_20260503_prototype_A_candidate_waypoints_combined_by_distance.csv
juansi_waterfall_fitcsv_20260503_prototype_A_candidate_waypoints_combined_projected.csv
juansi_waterfall_fitcsv_20260503_prototype_A_candidate_waypoints_combined_projected.geojson
juansi_waterfall_fitcsv_20260503_prototype_A_candidate_waypoints_combined_map.html
```

目前 risk zones 結果：

Current risk zone result:

```text
high zones:      2
moderate zones:  5
low zones:       3
```

主要高風險區間：

Key high-risk zones:

```text
0–1500 m
1600–2100 m
```

目前候選中繼點：

Current candidate waypoints:

```text
risk-zone candidate waypoints: 12
combined waypoints after scenic/facility merge: 20
combined projection: completed
combined HTML map: completed
```

Waypoint semantic families:

```text
User display layers:
- display: destination
- display: viewpoint
- display: facility
- display: named scenic

System/background layers:
- observe: risk / behavior
- debug: low priority viewpoint
```

Combined waypoint types include:

```text
destination_stop
viewpoint_stop
guide_map_stop
scenic_stop
shelter_stop
bench_stop
toilets_stop
rest_candidate
recovery
conditional_check
pacing
final_push
```

ib3a mapmatched activity outputs:

```text
script:
scripts\ib3_activity_environment\ib3a_mapmatch_highfreq_activity.py

mainline input:
outputs\ib1_route_profile\juansi_waterfall_fitcsv_20260503\
juansi_waterfall_fitcsv_20260503_route_profile_points.geojson

activity input:
activity_input\csv\juansi_waterfall\3.csv

output folder:
outputs\ib3a_mapmatched_activity\juansi_waterfall_fitcsv_20260503

outputs:
juansi_waterfall_fitcsv_20260503_activity_mapmatched.csv
juansi_waterfall_fitcsv_20260503_activity_mapmatched.geojson
juansi_waterfall_fitcsv_20260503_activity_mapmatched_summary.txt
juansi_waterfall_fitcsv_20260503_activity_mapmatched_core.csv
juansi_waterfall_fitcsv_20260503_activity_mapmatched_core.geojson
```

Current ib3a CLI / batch behavior:

```text
ib3a supports CLI arguments used by the batch runner:
--case-id
--activity-id
--user-id
--activity-fp
--activity-type
--out-dir

When activity_id is provided, outputs are written under:
outputs\ib3a_mapmatched_activity\<CASE_ID>\<ACTIVITY_ID>
with filenames prefixed by <ACTIVITY_ID>.
```

Current activity manifest behavior:

```text
The ib3 batch runner now supports both old FIT CSV manifests and generic
activity file manifests.

Preferred generic manifest columns:
activity_fp
activity_type

Backward-compatible columns:
activity_csv
activity_gpx

activity_type can be:
auto
csv
gpx
```

Current ib3a single-activity QA example / JW003:

```text
FIT CSV dedup: 6097 -> 6063
activity points: 6063
route_core points: 3480
terminal_off_route points: 2583
off_route points: 2583
backtrack_constrained: 2
speed_capped: 373

match_quality:
good: 2814
acceptable: 610
weak: 42
constrained: 14
off_route: 2583

activity_level_qa:
route_dist_min_m: 27.59
route_dist_max_m: 3957.93
route_coverage_ratio: 0.991
route_coverage_group: full_route
speed_capped_ratio: 0.107
speed_quality_group: caution
hr_valid_ratio: 1.000
hr_quality_group: good
activity_quality_group: analysis_ready
```

Interpretation:

```text
The full mapmatched activity output preserves all activity points.
The core output keeps only analysis_scope = route_core and should be preferred by
downstream ib3c / ib3d / waypoint observation stages when route-risk overlay should
ignore terminal off-route tail points.
FIT CSV duplicate rows are removed before mapmatching, so zero-time duplicate records
do not distort route-derived speed or speed_capped QA.
Activity-level QA fields classify route coverage, speed capped ratio, HR validity,
and whether each activity is analysis_ready / partial_route_only / qa_caution / no_hr / no_route_core.
The no_route_core branch is an explicit guard for activities with zero route_core
points, preventing them from being mislabeled as partial_route_only.
```

ib3b mapmatched activity profile QA outputs:

```text
script:
scripts\ib3_activity_environment\ib3b_plot_mapmatched_activity_profile.py

activity core input:
outputs\ib3a_mapmatched_activity\juansi_waterfall_fitcsv_20260503\
juansi_waterfall_fitcsv_20260503_activity_mapmatched_core.csv

optional terrain QA input:
outputs\ib1i_gpx_vs_contour_validation\juansi_waterfall_fitcsv_20260503\
juansi_waterfall_fitcsv_20260503_gpx_vs_contour_validation.csv

output folder:
outputs\ib3b_mapmatched_activity_profile\juansi_waterfall_fitcsv_20260503

outputs:
juansi_waterfall_fitcsv_20260503_mapmatched_activity_profile.png
juansi_waterfall_fitcsv_20260503_mapmatched_activity_profile_plot_data.csv
juansi_waterfall_fitcsv_20260503_mapmatched_activity_profile_summary.txt
```

Current ib3b single-activity QA example / JW003:

```text
ib1i_merged: True
rows: 3480
route_dist_min_m: 27.59
route_dist_max_m: 3957.93

match_quality:
good: 2814
acceptable: 610
weak: 42
constrained: 14

offset_to_mainline_m:
mean: 4.49
max: 49.99

walking_speed_mps:
mean: 0.909
max: 1.717

route_speed_mps_for_plot:
mean: 0.932
max: 2.975

forward_speed_route_mps:
mean: 1.153
max: 3.000

raw_hr_bpm:
mean: 122.18
min: 83
max: 167

is_stationary:
False: 3168
True: 312

route_gpx_quality_flag:
ok: 2155
mismatch: 1325
```

Current ib3b partial-route QA example / JW048:

```text
activity_quality_group: partial_route_only
route_coverage_group: partial_route
route_coverage_ratio: 0.659
route_dist_min_m: 1344.24
route_dist_max_m: 3957.15
speed_quality_group: good
speed_capped_ratio: 0.024
hr_quality_group: good
hr_valid_ratio: 1.000

rows: 832
match_quality:
good: 653
acceptable: 167
weak: 12
```

Interpretation:

```text
ib3b is a QA visualization stage for checking the ib3a route_core activity profile.
It compares activity elevation, route-profile elevation, walking speed, route-axis
speed QA, heart rate, mainline offset, match quality, and ib1i GPX-vs-contour terrain
QA fields. The speed panel uses FIT raw_speed_mps as the primary walking speed when
available. route-axis speed is retained as QA, and speed_capped values are hidden
from the route-speed plot so the line does not falsely stick to MAX_SPEED_MPS.
ib3b now reads ib3a activity-level QA fields and writes them into the PNG overlay,
summary TXT, and plot-data CSV. For partial_route activities, the plot shades
route sections not covered by the activity and marks route_dist_min_m /
route_dist_max_m with vertical guide lines.
```

ib3 batch runner result:

```text
script:
scripts\ib3_activity_environment\ib3_batch_run_juansi_activities.py

manifest:
activity_input\manifests\juansi_waterfall_activities.csv

CLI:
--manifest <manifest_csv>

status output:
outputs\ib3_batch_runs\juansi_waterfall_fitcsv_20260503\
juansi_waterfall_ib3_batch_status.csv

quality summary output:
outputs\ib3_batch_runs\juansi_waterfall_fitcsv_20260503\
juansi_waterfall_ib3a_core_quality_summary.csv

included activities: 16
ib3a ok: 16 / 16
ib3b ok: 16 / 16

activity_quality_group:
analysis_ready: 15
partial_route_only: 1

partial activity:
JW048

no_route_core:
0

skipped_no_route_core behavior:
If ib3a produces an empty core CSV, ib3b is skipped and batch status records
ib3b_status = skipped_no_route_core.

quality summary columns include:
core_rows
activity_quality_group
route_coverage_ratio
computed_route_coverage_ratio
speed_capped_ratio
computed_speed_capped_ratio
hr_valid_ratio
computed_hr_valid_ratio
offset / speed / HR statistics
match_quality counts

activity output pattern:
outputs\ib3a_mapmatched_activity\<CASE_ID>\<ACTIVITY_ID>
outputs\ib3b_mapmatched_activity_profile\<CASE_ID>\<ACTIVITY_ID>
```

GPX activity organization:

```text
activity_input\gpx\qixing_xiaoyoukeng_gpx_joyhike\
activity_input\gpx\qixing_lengshuikeng_xiaoyoukeng_gpx\
activity_input\gpx\dakeng_trail_4_gpx_20260503\

manifest:
activity_input\manifests\gpx_activities.csv
```

Current GPX manifest status:

```text
QX001:
case_id = qixing_xiaoyoukeng_gpx_joyhike
activity_fp = activity_input/gpx/qixing_xiaoyoukeng_gpx_joyhike/七星山 (小油坑進出)_Joyhike.gpx
include_flag = 0

QX002:
case_id = qixing_lengshuikeng_xiaoyoukeng_gpx
activity_fp = activity_input/gpx/qixing_lengshuikeng_xiaoyoukeng_gpx/冷水坑上-七星山東峰-主峰-下小油坑.gpx
include_flag = 0

DK001:
case_id = dakeng_trail_4_gpx_20260503
activity_fp = activity_input/gpx/dakeng_trail_4_gpx_20260503/20260503大坑4號步道.gpx
include_flag = 0
```

Reason:

```text
GPX files are organized by route / CASE_ID, but include_flag remains 0 until
each CASE_ID has its own route profile, OSM semantic risk, and NLSC terrain risk
outputs. This prevents a GPX activity from being mapmatched against the wrong
route distance axis.
```

NLSC tile mapping:

```text
config\nlsc_tile_activity_mapping.csv

Encoding:
UTF-8 with BOM / utf-8-sig

Current rows:
qixing_xiaoyoukeng_gpx_joyhike -> 97233NW -> confirmed
qixing_lengshuikeng_xiaoyoukeng_gpx -> 97233NW -> confirmed
dakeng_trail_4_gpx_20260503 -> pending
```

Interpretation:

```text
The two Qixing GPX cases can use:
nlsc_raw\97233NW\向量25K\ContourL.shp

The Dakeng trail 4 GPX case needs its own NLSC 25K tile confirmed before running
the NLSC terrain pipeline.
```

ib2d offline route risk map output:

```text
script:
scripts\ib2_route_risk\ib2d_plot_route_risk_offline_map.py

required preconditions:
0. nlsc_raw\97233NW\向量25K\ContourL.shp
1. osm_raw_output\<CASE_ID>\*.geojson
2. outputs\ib1_route_profile\<CASE_ID>\<CASE_ID>_route_profile_points.geojson
3. outputs\ib1c_route_profile_semantics\<CASE_ID>\<CASE_ID>_route_profile_semantic_enriched.geojson
   or outputs\ib1c_osm_semantic_risk\<CASE_ID>\<CASE_ID>_osm_semantic_risk_profile.geojson
4. outputs\ib1g_contour_window_features\<CASE_ID>\<CASE_ID>_contour_window_features.csv / .geojson
5. outputs\ib1e_osm_nlsc_terrain_risk\<CASE_ID>\<CASE_ID>_osm_nlsc_terrain_risk_profile.csv
   fallback: outputs\ib1e_osm_terrain_risk\<CASE_ID>\<CASE_ID>_osm_terrain_risk_profile.csv
   fallback: outputs\ib1c_osm_semantic_risk\<CASE_ID>\<CASE_ID>_osm_semantic_risk_profile.csv

output folder:
outputs\ib2d_route_risk_offline_map\juansi_waterfall_fitcsv_20260503

outputs:
juansi_waterfall_fitcsv_20260503_route_risk_offline_map.png
juansi_waterfall_fitcsv_20260503_route_risk_offline_segments.geojson
```

Current ib2d result:

```text
latest verified run: 2026-05-25 19:59 Asia/Taipei
DEBUG_MODE: True
DPI: 120
route buffer: 350 m
draw contours: True
draw contour labels: False
risk CSV selected:
outputs\ib1e_osm_nlsc_terrain_risk\juansi_waterfall_fitcsv_20260503\juansi_waterfall_fitcsv_20260503_osm_nlsc_terrain_risk_profile.csv
semantic GeoJSON selected:
outputs\ib1c_route_profile_semantics\juansi_waterfall_fitcsv_20260503\juansi_waterfall_fitcsv_20260503_route_profile_semantic_enriched.geojson
risk score column for map: risk_score_smooth

execution time after route-buffer optimization: about 6 seconds
points: 3973
segments: 3972
metric CRS: EPSG:32651
contour features within buffer: 72

OSM point layers within route buffer:
trailhead: 2
peak: 1
guidepost: 16
shelter: 14
bench: 12
picnic_table: 1
drinking_water: 1
toilets: 4
information_office: 2

OSM area layers within route buffer:
picnic_site: 2
bare_rock: 0
scree: 0
wetland: 2
water_area: 1

OSM line layers within route buffer:
nearby_path_network: 244
cliff: 0
waterway: 105
handrail: 1
safety_rope: 0
ladder: 0

risk_band:
high: 2173
moderate: 1395
low: 404
very_high: 0
very_high runs: none
```

Important ib2d implementation note:

```text
The route buffer is now built from profile points as a LineString buffer.
Do not use unary_union / union_all over thousands of route segments for the map
buffer; that caused 15-minute timeouts before OSM layer plotting started.
The script also uses Microsoft JhengHei / Microsoft YaHei before fallback fonts
so Traditional Chinese titles render correctly on Windows.
Risk legend displays only bands present in the current data.
The nearby_path_network layer reads osm_highway_raw.geojson and filters to walkable
highway classes before plotting; missing safety_rope / ladder layers are optional.
```

---

## 7. 目前模型能回答什麼 / Current Interpretation

Prototype A 目前可以回答：

Prototype A currently answers:

```text
1. 哪些路段是高風險區間？
   Which route sections are high-risk zones?

2. 為什麼這些路段風險高？
   Why are these sections high risk?

3. 風險主要來自 OSM 語意、NLSC 地形，還是水文地形放大？
   Does the risk mainly come from OSM semantics, NLSC terrain, or hydro-terrain amplification?

4. 哪裡適合恢復、檢查條件、調整配速或做推進決策？
   Where should users recover, check conditions, adjust pacing, or make a decision?
```

Prototype A 目前還不能完整回答：

Prototype A does not yet fully answer:

```text
1. 這條路線是否適合特定使用者？
   Whether this route is suitable for a specific user.

2. 使用者是否會爆心率或超出負荷？
   Whether the user will exceed heart-rate or strain thresholds.

3. 今天的天氣是否讓路線不適合行走？
   Whether today's weather makes the route unsafe.

4. 使用者是否應該即時撤退？
   Whether the user should turn back in real time.
```

這些需要後續整合：

These require future integration with:

```text
ib3 weather / environment risk
ib4 personal capability model
activity HR / pace / ETA model
```

---

## 8. 已知問題與注意事項 / Known Issues and Notes

### 8.1 根目錄重複腳本 / Root-level duplicate scripts

目前 `scripts\` 根目錄下仍有一些舊版或重複腳本。

There are still duplicate or older scripts directly under `scripts\`.

請優先使用分類資料夾內的腳本：

Prefer categorized-folder scripts:

```text
scripts\ia_osm
scripts\ib0_route_match
scripts\ib1_route_profile
scripts\ib1_osm_semantics
scripts\ib1_nlsc_terrain
scripts\ib2_route_risk
scripts\ib3_activity_environment
scripts\ib4_personal_model
```

除非已明確確認，否則不要使用 root-level duplicate scripts。

Do not use root-level duplicate scripts unless explicitly verified.

---

### 8.2 risk zone 邊界歸屬問題 / Zone boundary assignment

目前 waypoint projection 在 zone 邊界上可能會把點歸到前一段，因為目前邏輯是：

Current rule:

```text
start_dist_m <= dist_m <= end_dist_m
```

未來建議改成：

Future improvement:

```text
start_dist_m <= dist_m < end_dist_m
except for the final zone
```

---

### 8.3 pacing waypoint 顯示語意 / Pacing waypoint display

如果 waypoint 符合：

If a waypoint has:

```text
waypoint_type = pacing
combined risk > 0.40
or slope_band = very_steep
```

建議顯示為：

It should be displayed as:

```text
pacing_caution
or heart_rate_caution
```

---

### 8.4 scenic / destination / facility waypoint 已納入 / Scenic, destination, and facility waypoints included

已完成 OSM scenic / destination / facility waypoint source，來源包含：

Completed OSM scenic / destination / facility waypoint sources:

```text
osm_waterfall_raw.geojson
osm_viewpoint_raw.geojson
osm_tourism_raw.geojson
osm_guide_map_attraction_raw.geojson
osm_bench_raw.geojson
osm_shelter_raw.geojson
osm_picnic_table_raw.geojson
osm_picnic_site_raw.geojson
osm_toilets_raw.geojson
osm_drinking_water_raw.geojson
```

目前 combined waypoint map 採 display / observe / debug 圖層策略：

Current combined waypoint map uses display / observe / debug layers:

```text
display:
  給登山者看的目的地、展望點、具名景點與設施點。

observe:
  系統背景觀測用的風險、配速、恢復、地形休息候選點。

debug:
  低優先或需人工檢查的候選點。
```

---

## 9. ib2d 角色 / Role of ib2d

`ib2d_plot_route_risk_offline_map.py` 目前應視為 QA / visualization layer。

`ib2d_plot_route_risk_offline_map.py` should currently be treated as a QA / visualization layer.

它不是目前 Prototype A waypoint pipeline 的必要前置步驟。

It is not required before the current Prototype A waypoint pipeline.

目前 ib2d 已能穩定輸出：

Current ib2d can produce:

```text
OSM POI
NLSC contour lines
route risk segments
offline PNG map
```

未來 ib2d 可以升級整合 Prototype A risk zones 與 combined candidate waypoints。

Future ib2d may be upgraded to combine Prototype A risk zones and combined candidate waypoints.

---

## 10. 下一步工作 / Next Work Items

建議下一步：

Recommended next steps:

```text
1. 檢查 combined waypoint map 的 display / observe / debug 圖層是否符合產品展示需求。
   Review whether display / observe / debug layers fit the intended user-facing map.

2. 視需要微調 facility 顯示規則：
   bench_stop 是否預設顯示，或僅作 observation layer。
   Fine-tune facility display rules, especially for bench_stop.

3. 改善 pacing waypoint 顯示：
   pacing + high risk / very_steep → pacing_caution / heart_rate_caution.
   Improve pacing waypoint display.

4. 修正 zone boundary assignment。
   Fix zone boundary assignment.

5. 整合天氣風險放大，並為 IB3C 預留 baseline / scenario / observed weather 三種模式。
   Integrate weather amplification and reserve baseline / scenario / observed weather modes for IB3C.

6. 將既有 4 支 IB3C related legacy / supporting scripts 納入盤點：
   ib3c_overlay_activity_with_route_risk.py、ib3c_plot_gpx_station_map.py、ib3c_apply_environment_risk_adjustment.py、ib3c2_compare_weather_trend_adjustment.py。
   Record the four existing IB3C-related legacy / supporting scripts and clarify that they are not yet the new activity behavior event detection layer.

7. 新增 IB3C activity behavior event detection：
   將低速、停留、離線、繞行、導航確認、設施／景點停留與心率恢復視為活動行為事件，並結合 OSM / NLSC / 風險 / 天候上下文。
   Add IB3C activity behavior event detection for low-speed, stationary, off-route, detour, navigation-check, facility/scenic-stop, and HR-recovery events with OSM / NLSC / risk / weather context.

8. 以 ib3b profile PNG / plot CSV 人工檢查 ib3a route_core 品質，再整合個人能力與 HR response model：
   使用 display / observe waypoints 作為 ETA checkpoint 與停留行為觀測節點。
   Use ib3a core outputs and ib3b QA profile as the activity input check for ib3c / ib3d / waypoint observation, then integrate personal capability and HR response models using display / observe waypoints as ETA checkpoints and behavior-observation nodes.

9. 每次 GPT session 結束時更新：
   README_current_pipeline.md、runs/latest_handoff_prompt.md、runs/changelog.md。
   Keep README_current_pipeline.md, runs/latest_handoff_prompt.md, and runs/changelog.md updated at the end of each GPT session.
```
---

## 11. THCI / Route Challenge Index v0

Update date: 2026-05-25 Asia/Taipei

This project now has a first route-level baseline challenge layer:

```text
script:
scripts\ib2e_compute_route_challenge_index.py

model_version:
thci_v0_from_ib1e_profile

default CASE_ID:
juansi_waterfall_fitcsv_20260503

input:
outputs\ib1e_osm_nlsc_terrain_risk\juansi_waterfall_fitcsv_20260503\
juansi_waterfall_fitcsv_20260503_osm_nlsc_terrain_risk_profile.csv

outputs:
outputs\ib2e_route_challenge_index\juansi_waterfall_fitcsv_20260503\
juansi_waterfall_fitcsv_20260503_route_challenge_index_summary.csv
juansi_waterfall_fitcsv_20260503_route_challenge_index_profile.csv
juansi_waterfall_fitcsv_20260503_route_challenge_radar.png
```

THCI means Taiwan Hiking Challenge Index / 全台登山挑戰指數. It is a route baseline score under good hiking conditions. It is not the same as live weather risk and not the same as personal suitability.

Six normalized axes:

```text
physical_difficulty_score       體力難度
technical_difficulty_score      技術難度
baseline_hazard_score           基礎危害
navigation_risk_score           導航風險
support_deficit_score           支援不足
weather_sensitivity_score       天候敏感度
```

Current v0 weights:

```text
route_challenge_index =
0.35 physical_difficulty_score
+ 0.20 technical_difficulty_score
+ 0.20 baseline_hazard_score
+ 0.10 navigation_risk_score
+ 0.10 support_deficit_score
+ 0.05 weather_sensitivity_score
```

Latest verified result for `juansi_waterfall_fitcsv_20260503`:

```text
route_challenge_index: 26.23 / 100
route_challenge_band: moderate
physical_difficulty_score: 40.12
technical_difficulty_score: 1.41
baseline_hazard_score: 17.04
navigation_risk_score: 8.08
support_deficit_score: 53.47
weather_sensitivity_score: 46.94
```

Radar chart note:

```text
The radar output is now a hexagonal radar chart, not the default circular polar plot.
It includes Chinese axis labels, English helper labels, and a note explaining that
THCI is a baseline route challenge score, not condition-adjusted risk or personal suitability.
```

---

## 12. 2026-05-27 Update: OSM Friendly Fetch + Jiuwufeng Roundtrip

Update date: 2026-05-27 Asia/Taipei

### 12.1 OSM friendly fetch direction

Public Overpass should not be treated as a high-volume batch backend. The new recommended `ia1` direction is:

```text
small GPX bbox / route-buffer query
clear User-Agent
cache-aware skip behavior
grouped tag profiles
single-case output folder
eventual local Taiwan OSM extract for full-Taiwan batch ranking
```

New script:

```text
scripts\ia_osm\ia1_osm_fetch_raw_friendly_cli.py
```

Important CLI options:

```text
--case-id
--activity-fp
--buffer-m
--overpass-url
--timeout
--force-refresh
--tag-profile core|pipeline
```

It outputs the same downstream raw layer filenames, such as:

```text
osm_highway_raw.geojson
osm_waterway_raw.geojson
osm_cliff_raw.geojson
osm_peak_raw.geojson
osm_trailhead_raw.geojson
osm_shelter_raw.geojson
```

Current note:

```text
Public Overpass was unstable / timed out during the 2026-05-27 run.
For the Jiuwufeng case, the pipeline used an already-fetched OSM raw layer set copied into the canonical case folder.
For future full-Taiwan ranking, prefer a local Taiwan .osm.pbf extract workflow.
```

### 12.2 Jiuwufeng canonical case

Canonical CASE_ID:

```text
zhonghua_ust_jiuwufeng_roundtrip_biji
```

Input GPX:

```text
activity_input\gpx\zhonghua_ust_jiuwufeng_roundtrip_biji\中華科大至九五峰_上下山合併_route.gpx
```

NLSC tile:

```text
97233SW
nlsc_raw\97233SW\向量25K\ContourL.shp
```

Important note:

```text
ib0b OSM ordered path produced an overlong 30.63 km route for this out-and-back case.
The original merged GPX route is about 13.20 km.
For ib1a and ib1g, use the GPX route GeoJSON as the route axis:

osm_raw_output\zhonghua_ust_jiuwufeng_roundtrip_biji\osm_query_gpx_route.geojson
```

### 12.3 Verified pipeline commands for Jiuwufeng

Core sequence used after OSM raw was available:

```powershell
$case = "zhonghua_ust_jiuwufeng_roundtrip_biji"
$name = "中華科大至九五峰上下山合併 GPX 20260526"
$gpxRoute = ".\osm_raw_output\$case\osm_query_gpx_route.geojson"
$mainline = ".\outputs\ib0b_mainline\$case\${case}_mainline_ib0_matched.geojson"
$contour = ".\nlsc_raw\97233SW\向量25K\ContourL.shp"

python .\scripts\ib1_route_profile\ib1a_build_route_elevation_profile_cli_updated.py `
  --case-id $case --case-name $name `
  --activity-fp ".\activity_input\gpx\$case\中華科大至九五峰_上下山合併_route.gpx" `
  --activity-type gpx `
  --ordered-path-fp $gpxRoute `
  --mainline-fp $mainline

python .\scripts\ib1_route_profile\ib1c_enrich_route_profile_semantics_cli_updated.py --case-id $case --case-name $name
python .\scripts\ib1_osm_semantics\ib1c_audit_osm_semantic_risk_mapping_cli_updated.py --case-id $case --case-name $name
python .\scripts\ib1_osm_semantics\ib1c_apply_osm_semantic_risk_mapping_cli_updated.py --case-id $case --case-name $name

python .\scripts\ib1_nlsc_terrain\ib1g_v2_compute_contour_window_features_cli_updated_v1_1.py `
  --case-id $case --case-name $name `
  --route-line-fp $gpxRoute `
  --contour-fp $contour `
  --tile 97233SW

python .\scripts\ib1_nlsc_terrain\ib1e_enrich_route_profile_with_contour_window_terrain_cli_updated.py --case-id $case --case-name $name

$env:CASE_ID = $case
python .\scripts\ib1_nlsc_terrain\ib1e_plot_osm_nlsc_terrain_risk_profile.py
python .\scripts\ib2_route_risk\ib2_v2_route_risk_scoring.py
python .\scripts\ib2_route_risk\ib2a_plot_route_risk_profile.py
python .\scripts\ib2_route_risk\ib2_v3_route_segment_risk.py
python .\scripts\ib2_route_risk\ib2b_v2_plot_route_segment_risk_profile.py
python .\scripts\ib2_route_risk\ib2c_plot_route_risk_map_2d.py
python .\scripts\ib2_route_risk\ib2d_plot_route_risk_offline_map.py
```

### 12.4 Jiuwufeng verified outputs

Final route profile:

```text
route_len_m: 13202.42
profile points: 13204
cum_gain_m: 4298.67
cum_loss_m: 4298.67
```

ib1e combined risk bands:

```text
moderate 6965
low      5079
high     1160
```

ib2 segment risk:

```text
segments: 133
moderate 83
high     27
low      23
```

ib2d point/segment map band counts:

```text
moderate 6990
low      5027
high     1186
```

THCI:

```text
route_challenge_index: 31.60 / 100
route_challenge_band: moderate
```

Important outputs:

```text
outputs\ib2d_route_risk_offline_map\zhonghua_ust_jiuwufeng_roundtrip_biji\
  zhonghua_ust_jiuwufeng_roundtrip_biji_route_risk_offline_map.png
  zhonghua_ust_jiuwufeng_roundtrip_biji_route_risk_offline_segments.geojson
  zhonghua_ust_jiuwufeng_roundtrip_biji_route_challenge_radar.png
  zhonghua_ust_jiuwufeng_roundtrip_biji_route_risk_offline_map_with_radar.png

outputs\ib2e_route_challenge_index\zhonghua_ust_jiuwufeng_roundtrip_biji\
  zhonghua_ust_jiuwufeng_roundtrip_biji_route_challenge_index_summary.csv
  zhonghua_ust_jiuwufeng_roundtrip_biji_route_challenge_index_profile.csv
  zhonghua_ust_jiuwufeng_roundtrip_biji_route_challenge_radar.png
```

### 12.5 THCI input path compatibility

`scripts\ib2e_compute_route_challenge_index.py` now prefers the newer ib1e output:

```text
outputs\ib1e_route_profile_contour_window_terrain\<CASE_ID>\
<CASE_ID>_route_profile_contour_window_terrain_enriched.csv
```

and falls back to the legacy path:

```text
outputs\ib1e_osm_nlsc_terrain_risk\<CASE_ID>\
<CASE_ID>_osm_nlsc_terrain_risk_profile.csv
```
