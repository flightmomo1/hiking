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

| Stage | 中文說明 | Official script |
|---|---|---|
| Ia1 | OSM 原始語意圖層抓取；v1.3 增加 scenic / destination / facility raw layers | `scripts\ia_osm\ia1_osm_fetch_raw_v1_3.py` |
| ib0 | GPX / FIT CSV 對齊 OSM 路線 | `scripts\ib0_route_match\ib0_gpx_to_osm_route_v1.py` |
| ib0b | 主幹路線抽取 | `scripts\ib0_route_match\ib0b_route_mainline_extract_abtest_v1.py` |
| ib0c | 從 landmarks 產生起終點 anchors | `scripts\ib0_route_match\ib0c_anchor_from_landmarks_v1.2.py` |
| ib0d | 依 anchors 裁切 ordered mainline | `scripts\ib0_route_match\ib0d_trim_ordered_mainline_by_anchors_v1.1.py` |
| ib1g | NLSC 等高線視窗特徵計算 | `scripts\ib1_nlsc_terrain\ib1g_v2_compute_contour_window_features.py` |
| ib1h | NLSC contour window profile 視覺化 | `scripts\ib1_route_profile\ib1h_v2_plot_contour_window_profile.py` |
| ib1i | GPX/FIT elevation vs NLSC contour-window QA validation | `scripts\ib1_nlsc_terrain\ib1i_validate_gpx_vs_contour.py` |
| ib1h | risk-zone candidate waypoint 產生 | `scripts\ib1_nlsc_terrain\ib1h_generate_candidate_waypoints_from_risk_zones.py` |
| ib1h | OSM scenic / destination / facility candidate waypoint 產生 | `scripts\ib1_nlsc_terrain\ib1h_generate_scenic_candidate_waypoints_from_osm.py` |
| ib1h | risk + scenic/facility candidate waypoint 合併 | `scripts\ib1_nlsc_terrain\ib1h_merge_risk_and_scenic_candidate_waypoints.py` |
| ib1h | candidate waypoint 投影到 route profile | `scripts\ib1_nlsc_terrain\ib1h_project_candidate_waypoints_to_route.py` |
| ib1h | combined candidate waypoint map；display / observe / debug 圖層 | `scripts\ib1_nlsc_terrain\ib1h_plot_candidate_waypoints_map.py` |
| ib2 | 舊版 route risk scoring v2 | `scripts\ib2_route_risk\ib2_v2_route_risk_scoring.py` |
| ib2 | 舊版 route segment risk v3 | `scripts\ib2_route_risk\ib2_v3_route_segment_risk.py` |
| ib2b | 舊版 route segment risk profile 視覺化 | `scripts\ib2_route_risk\ib2b_v2_plot_route_segment_risk_profile.py` |
| ib2d | NLSC contour + OSM POI + route risk offline QA map | `scripts\ib2_route_risk\ib2d_plot_route_risk_offline_map.py` |
| ib3a | high-frequency activity map matching to route distance axis | `scripts\ib3_activity_environment\ib3a_mapmatch_highfreq_activity.py` |
| ib3b | mapmatched activity profile QA visualization | `scripts\ib3_activity_environment\ib3b_plot_mapmatched_activity_profile.py` |
| ib3 batch | Juansi Waterfall multi-activity ib3a → ib3b batch runner | `scripts\ib3_activity_environment\ib3_batch_run_juansi_activities.py` |
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
ia1_osm_fetch_raw_v1_3.py
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
ib1i_validate_gpx_vs_contour.py
↓
ib1f_summarize_prototype_A_risk_segments.py
↓
ib1g_merge_prototype_A_risk_zones.py
↓
ib1g_plot_prototype_A_risk_zones_map.py
↓
ib1h_generate_candidate_waypoints_from_risk_zones.py
↓
ib1h_generate_scenic_candidate_waypoints_from_osm.py
↓
ib1h_merge_risk_and_scenic_candidate_waypoints.py
↓
ib1h_project_candidate_waypoints_to_route.py
↓
ib1h_plot_candidate_waypoints_map.py
↓
ib2d_plot_route_risk_offline_map.py
↓
ib3a_mapmatch_highfreq_activity.py
↓
ib3b_plot_mapmatched_activity_profile.py
↓
ib3_batch_run_juansi_activities.py
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

5. 整合天氣風險放大。
   Integrate weather amplification.

6. 以 ib3b profile PNG / plot CSV 人工檢查 ib3a route_core 品質，再整合個人能力與 HR response model：
   使用 display / observe waypoints 作為 ETA checkpoint 與停留行為觀測節點。
   Use ib3a core outputs and ib3b QA profile as the activity input check for ib3c / ib3d / waypoint observation, then integrate personal capability and HR response models using display / observe waypoints as ETA checkpoints and behavior-observation nodes.

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

## 12. ib2d Multi-Case Offline Map + THCI Radar Integration

Update date: 2026-05-26 Asia/Taipei

`scripts\ib2_route_risk\ib2d_plot_route_risk_offline_map.py` has been updated from a single hard-coded case script into a `CASE_ID`-aware visualization step.

Supported verified cases:

```text
juansi_waterfall_fitcsv_20260503
qixing_xiaoyoukeng_main_peak_20260315
qixing_lengshuikeng_main_peak_20260523
```

Run pattern:

```powershell
$env:CASE_ID='qixing_xiaoyoukeng_main_peak_20260315'
& .\.venv\Scripts\python.exe .\scripts\ib2_route_risk\ib2d_plot_route_risk_offline_map.py
```

Inputs are selected from each case folder:

```text
outputs\ib1_route_profile\<CASE_ID>\<CASE_ID>_route_profile_points.geojson
outputs\ib1c_route_profile_semantics\<CASE_ID>\<CASE_ID>_route_profile_semantic_enriched.geojson
outputs\ib1e_osm_nlsc_terrain_risk\<CASE_ID>\<CASE_ID>_osm_nlsc_terrain_risk_profile.csv
osm_raw_output\<CASE_ID>\*.geojson
nlsc_raw\97233NW\向量25K\ContourL.shp
```

Outputs are written into each route's ib2d folder:

```text
outputs\ib2d_route_risk_offline_map\<CASE_ID>\
<CASE_ID>_route_risk_offline_map.png
<CASE_ID>_route_risk_offline_segments.geojson
<CASE_ID>_route_challenge_radar.png
<CASE_ID>_route_risk_offline_map_with_radar.png
```

`<CASE_ID>_route_challenge_radar.png` is copied from the ib2e THCI output folder when available. `<CASE_ID>_route_risk_offline_map_with_radar.png` is a combined presentation image with the ib2d offline risk map on the left and the THCI hexagonal radar chart on the right.

Latest verified ib2d segment counts:

```text
juansi_waterfall_fitcsv_20260503:
  points: 3973
  segments: 3972
  high: 2173
  moderate: 1395
  low: 404

qixing_xiaoyoukeng_main_peak_20260315:
  points: 2323
  segments: 2322
  high: 680
  moderate: 1004
  low: 638

qixing_lengshuikeng_main_peak_20260523:
  points: 1979
  segments: 1978
  high: 514
  moderate: 1015
  low: 449
```

Optional OSM layers such as `osm_safety_rope_raw.geojson` and `osm_ladder_raw.geojson` may be missing for some cases. The script treats missing optional layers as zero features and still produces the ib2d outputs.
