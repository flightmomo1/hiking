# 115_osm Current Pipeline README  
# 115_osm 目前流程交接文件

> 本文件是 `115_osm / 山力分析 Prototype A` 的主流程交接文件，用於記錄目前正式 pipeline、腳本版本、輸出路徑、已知問題與下一步工作。  
> This document is the main handoff README for the `115_osm / Mountain Analysis Prototype A` project. It records the current official pipeline, script versions, output paths, known issues, and next work items.

> 使用方式：開新 GPT 分頁時，建議先貼 `runs/latest_handoff_prompt.md`；若需要完整架構，再補貼本文件。  
> Usage: For a new GPT session, paste `runs/latest_handoff_prompt.md` first. Paste this README only when the full pipeline structure is needed.

---

## 1. 目前穩定流程 / Current Stable Flow

本文件用來記錄 `115_osm` 專案目前可穩定執行的流程、正式腳本版本、輸出資料夾，以及下一步開發方向。

This document records the current stable pipeline, official script versions, output folders, and next development steps for the `115_osm` project.

目前主要案例 / Current case:

- Case ID: `juansi_waterfall_fitcsv_20260503`
- Case name: `絹絲瀑布 FIT CSV 20260503`
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

目前正式採用版本 / Current official script versions:

| Stage | 中文說明 | Official script |
|---|---|---|
| Ia1 | OSM 原始語意圖層抓取 | `scripts\ia_osm\ia1_osm_fetch_raw_v1_2.py` |
| ib0 | GPX / FIT CSV 對齊 OSM 路線 | `scripts\ib0_route_match\ib0_gpx_to_osm_route_v1.py` |
| ib0b | 主幹路線抽取 | `scripts\ib0_route_match\ib0b_route_mainline_extract_abtest_v1.py` |
| ib0c | 從 landmarks 產生起終點 anchors | `scripts\ib0_route_match\ib0c_anchor_from_landmarks_v1.2.py` |
| ib0d | 依 anchors 裁切 ordered mainline | `scripts\ib0_route_match\ib0d_trim_ordered_mainline_by_anchors_v1.1.py` |
| ib1g | NLSC 等高線視窗特徵計算 | `scripts\ib1_nlsc_terrain\ib1g_v2_compute_contour_window_features.py` |
| ib1h | NLSC contour window profile 視覺化 | `scripts\ib1_route_profile\ib1h_v2_plot_contour_window_profile.py` |
| ib2 | 舊版 route risk scoring v2 | `scripts\ib2_route_risk\ib2_v2_route_risk_scoring.py` |
| ib2 | 舊版 route segment risk v3 | `scripts\ib2_route_risk\ib2_v3_route_segment_risk.py` |
| ib2b | 舊版 route segment risk profile 視覺化 | `scripts\ib2_route_risk\ib2b_v2_plot_route_segment_risk_profile.py` |
| ib3d | 活動風險時間線報告 | `scripts\ib3_activity_environment\ib3d_v2_plot_activity_risk_timeline_report.py` |

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

目前 `juansi_waterfall_fitcsv_20260503` 的 Prototype A 主流程如下：

Current Prototype A pipeline for `juansi_waterfall_fitcsv_20260503`:

```text
ia1_osm_fetch_raw_v1_2.py
↓
ib0_gpx_to_osm_route_v1.py
↓
ib0a_prune_matched_osm_route.py
↓
ib0b_route_mainline_extract_abtest_v1.py
↓
ib0c_anchor_from_landmarks_v1.2.py
↓
ib0d_trim_ordered_mainline_by_anchors_v1.1.py
↓
ib1a_build_route_elevation_profile.py
↓
ib1c_enrich_route_profile_semantics.py
↓
ib1c_audit_osm_semantic_risk_mapping.py
↓
ib1c_apply_osm_semantic_risk_mapping.py
↓
ib1c_plot_osm_semantic_risk_profile.py
↓
ib1g_v2_compute_contour_window_features.py
↓
ib1e_combine_osm_semantic_and_nlsc_terrain_risk.py
↓
ib1e_plot_osm_nlsc_terrain_risk_profile.py
↓
ib1f_summarize_prototype_A_risk_segments.py
↓
ib1g_merge_prototype_A_risk_zones.py
↓
ib1g_plot_prototype_A_risk_zones_map.py
↓
ib1h_generate_candidate_waypoints_from_risk_zones.py
↓
ib1h_project_candidate_waypoints_to_route.py
↓
ib1h_plot_candidate_waypoints_map.py
```

註：上方 pipeline 僅列出腳本檔名，正式路徑請以「正式採用版本表」與 `scripts\` 分類資料夾為準。

Note: The pipeline order above lists script names only. Official paths should follow the official script version table and categorized folders under `scripts\`.

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
12 candidate waypoints
projection_match_ok: 12 / 12
```

Waypoint types:

```text
start_precheck
recovery_decision
recovery
rest_candidate
conditional_check
conditional_check|pacing
pacing
final_push
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

### 8.4 景觀 / 目的地中繼點尚未納入 / Scenic and destination waypoints not yet included

目前 waypoint generation 是根據 risk zones 產生。

Current waypoint generation is risk-zone based.

尚未納入：

It does not yet include:

```text
scenic_stop
destination_stop
viewpoint_stop
waterfall viewpoint
guide map attraction
```

未來應新增 scenic waypoint source：

Future scenic waypoint sources:

```text
OSM scenic / tourism / information POI
manual scenic seed CSV
guide map facilities
```

---

## 9. ib2d 角色 / Role of ib2d

`ib2d_plot_route_risk_offline_map.py` 目前應視為 QA / visualization layer。

`ib2d_plot_route_risk_offline_map.py` should currently be treated as a QA / visualization layer.

它不是目前 Prototype A waypoint pipeline 的必要前置步驟。

It is not required before the current Prototype A waypoint pipeline.

未來 ib2d 可以升級整合：

Future ib2d may be upgraded to combine:

```text
OSM POI
NLSC contour lines
Prototype A risk zones
Prototype A candidate waypoints
```

---

## 10. 下一步工作 / Next Work Items

建議下一步：

Recommended next steps:

```text
1. 新增 scenic / destination waypoint source。
   Add scenic / destination waypoint source.

2. 擴充 OSM scenic POI extraction，例如 waterfall / viewpoint / information_board / tourism。
   Add OSM scenic POI extraction: waterfall / viewpoint / information_board / tourism.

3. 改善 pacing waypoint 顯示：
   pacing + high risk / very_steep → pacing_caution / heart_rate_caution.
   Improve pacing waypoint display.

4. 修正 zone boundary assignment。
   Fix zone boundary assignment.

5. 整合天氣風險放大。
   Integrate weather amplification.

6. 整合個人能力與 HR response model。
   Integrate personal capability and HR response model.

7. 每次 GPT session 結束時更新：
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

## 12. Qixing Main Peak GPX Case OSM Layer Normalization

Update date: 2026-05-25 Asia/Taipei

Two new GPX routes have been organized as route-level CASE_ID folders:

```text
activity_input\gpx\qixing_xiaoyoukeng_main_peak_20260315\小油坑七星山主峰.gpx
activity_input\gpx\qixing_lengshuikeng_main_peak_20260523\冷水坑到七星山主峰.gpx
```

Both routes use NLSC 25K tile:

```text
nlsc_tile_id: 97233NW
contour: nlsc_raw\97233NW\向量25K\ContourL.shp
mapping file: config\nlsc_tile_activity_mapping.csv
```

Important data lineage rule:

```text
Each CASE_ID should have its own osm_raw_output\<CASE_ID>\*.geojson folder.
The Qixing main peak routes may be derived from the existing Qixing OSM source
dataset, but downstream scripts should read the per-CASE_ID OSM folders, not
silently read qixing_lengshuikeng_xiaoyoukeng_v1_2_success_20260511.
```

Planned / current normalization script:

```text
scripts\ib2e_prepare_qixing_case_osm_layers.py
```

Expected OSM output folders:

```text
osm_raw_output\qixing_xiaoyoukeng_main_peak_20260315
osm_raw_output\qixing_lengshuikeng_main_peak_20260523
```

This is required so the THCI radar axes that depend on OSM facilities and
terrain/landform layers have clean, per-route provenance:

```text
technical_difficulty_score
baseline_hazard_score
navigation_risk_score
support_deficit_score
weather_sensitivity_score
```
