# Current Pipeline Update - IB3A-RC v1k5 聚合式低速高程補充層

Date: 2026-06-09

## 目前狀態

`qixing_lengshuikeng` 的 IB3A-RC full26 活動流程已延伸至聚合式低速高程補充層（aggregated low-speed elevation supplement layer）。

目前收束鏈如下：

1. v1d3-v1i evidence / classification
2. v1j display trajectory
3. v1k minimal horizontal calibrated activity dataset
4. v1k2 calibrated motion dataset
5. v1k2a motion artifact classification
6. v1k3 calibrated elevation / slope / cumulative gain-loss
7. v1k4 elevation visual QA
8. v1k5 aggregated low-speed elevation supplement

相關 commit：

- `855f5a3 Add IB3A-RC calibrated elevation and gain-loss layer`
- `b24f205 Document IB3A-RC v1k3 elevation convergence`
- `bf4fcf6 Add IB3A-RC elevation visual QA plotter`
- `54a3df1 Document IB3A-RC v1k4 elevation visual QA`
- `c289ac3 Add IB3A-RC aggregated elevation supplement layer`

## 分支脈絡

目前分支：

- `codex/ib3-qixing-lengshuikeng-v1k5-aggregated-elevation-step`

v1k5 是從 v1k4 visual QA 收束點延伸出來的 activity RC 分支節點。它不是 IB0B / IB0D formal route branch 的替代品，也不是 route profile 的重新建模。

整體角色仍維持：

```text
IA1 refreshed OSM raw
→ IB0 route match
→ IB0C anchors
→ IB0A control point projection
→ IB0A-2 route-axis anchor/component QA
    ├─→ IB0B mainline → IB0D → IB1/IB2 route formal products
    └─→ IB0-CAND adapter → candidate_route_points.csv → IB3A-RC activity calibrated dataset
```

IB3A-RC 的任務是處理「實際活動軌跡」的 candidate-route evidence、wrong-route / off-target / connector / summit-stay 分類，以及後端可用的 calibrated activity dataset。

## IB3A-RC Stage Map

| Stage | 角色 | 輸出行為 |
|---|---|---|
| v1d3 | 候選路線投影、context / policy、stability evidence | 產生 candidate projection coordinates |
| v1e | 山頂錨點穩定化（summit anchor stabilization） | 加入 reviewed summit anchor coordinates |
| v1f | 轉換連續性 evidence（transition continuity evidence） | labels / evidence only |
| v1g | off-target 偵測 | labels / evidence only |
| v1g2 | off-target zone consolidation | labels / evidence only |
| v1h | mainline / connector / non-mainline membership | classification only |
| v1i | route-level wrong-route rules | classification and training exclusion only |
| v1j | display trajectory selection | 加入 display coordinates |
| v1k | minimal horizontal calibrated dataset | 加入 calibrated horizontal coordinates 與 backend policy |
| v1k2 | calibrated motion dataset | 加入 calibrated distance、speed、movement state |
| v1k2a | motion artifact QA | 加入 artifact type / reason / review flags |
| v1k3 | calibrated elevation / gain-loss | 加入 elevation、slope、gain/loss、elevation review gates |
| v1k4 | elevation visual QA | 產生 read-only HTML QA reports |
| v1k5 | aggregated low-speed elevation supplement | 加入低速小步距高程補充欄位與 visual QA |

## v1k5 的目的

v1k3 的設計偏保守。它會在逐列高程變化計算中排除 `calibrated_step_distance_m < 3m` 的 step，以避免 GPS 微震盪、停留抖動與短距離雜訊被誤算成爬升或下降。

這個策略是安全的，但在某些低速連續移動段會造成高程 gain/loss 低估。

最明顯案例是 `37_1`：

- v1k4 visual QA 顯示高程曲線確實有連續下降趨勢。
- 但 v1k3 因為多數 per-row step distance 小於 3m，使有效 slope / gain-loss rows 過少。
- 因此 cumulative loss 可能被低估。

v1k5 的任務是補這類「可信的低速連續高程變化」，而不是重新計算整條活動軌跡。

## 設計決策：supplement-only layer

v1k5 採用 supplement-only 設計。

也就是：

```text
v1k3 cumulative gain/loss = baseline
v1k5 supplemental gain/loss = conservative low-speed supplement
v1k5 total gain/loss = v1k3 baseline + v1k5 supplement
```

v1k5 不覆蓋 v1k3 欄位，也不重新計算整條路的累積爬升與下降。

這個決策是為了避免早期實驗版出現的 over-accumulation 問題：

- 第一版重新聚合整條路，導致補量過大。
- 第二版即使提高門檻，仍可能因長段聚合放大高程累積。
- supplement-only 版只針對 v1k3 已排除、且具備可信條件的低速小步距段進行補充。

## 腳本

Builder：

- `scripts/ib3_activity_environment/ib3a_rc_build_calibrated_elevation_v1k5.py`

Visual QA plotter：

- `scripts/ib3_activity_environment/ib3a_rc_plot_calibrated_elevation_v1k5.py`

Commit：

- `c289ac3 Add IB3A-RC aggregated elevation supplement layer`

## 輸入與輸出

v1k5 builder input root：

- `outputs/ib3a_rc_calibrated_elevation_v1k3_join_hard_gate_full26_qa`

v1k5 builder output root：

- `outputs/ib3a_rc_calibrated_elevation_v1k5_supplement_only_qixing_lengshuikeng_full26_qa`

v1k5 visual QA output root：

- `outputs/ib3a_rc_calibrated_elevation_visual_qa_v1k5_supplement_only_qixing_lengshuikeng_full26`

batch summary：

- `outputs/ib3a_rc_calibrated_elevation_visual_qa_v1k5_supplement_only_qixing_lengshuikeng_full26/_batch_summary/qixing_lengshuikeng_v1k5_elevation_visual_qa_summary.csv`
- `outputs/ib3a_rc_calibrated_elevation_visual_qa_v1k5_supplement_only_qixing_lengshuikeng_full26/_batch_summary/qixing_lengshuikeng_v1k5_elevation_visual_qa_summary.json`

## v1k5 補充條件

v1k5 只補「低速小步距、但高程趨勢可信」的片段。

row 必須符合：

- `route_class in [MAINLINE_CORE, MAINLINE_SUMMIT_STAY, CONNECTOR]`
- `movement_state in [MOVING, SLOW_MOVING]`
- `elevation_step_valid != True`
- `gain_loss_excluded_reason` 包含 `STEP_DISTANCE_LT_3M`
- `motion_representative_flag = True`
- `time_interval_valid = True`
- `motion_artifact_flag = False`
- `elevation_artifact_flag = False`
- 有有效的 `calibrated_elevation_m`
- 有有效的 `elapsed_sec`

排除：

- `WRONG_ROUTE`
- `OFF_TARGET`
- `UNKNOWN_REVIEW`
- `STOPPED`
- `elevation_profile_dist_jump_flag = True`
- v1k3 hard exclusion：
  - `ELEVATION_JOIN_DIST_GT_10M_HARD_EXCLUDED`
  - `PROFILE_DISTANCE_JUMP_HARD_EXCLUDED`
  - `ELEVATION_ARTIFACT_DELTA_GT_10M`

聚合 step 成立條件：

- aggregated horizontal distance >= 15 m
- duration >= 10 sec
- absolute elevation delta >= 2 m
- absolute slope <= 45%

若 slope 超過門檻，該 step 會標記為 review-only，不納入 supplemental gain/loss。

## v1k5 新增欄位

v1k5 只 append 新欄位，保留 v1k3 所有欄位與 row order。

主要新增欄位：

- `agg_supplement_step_valid`
- `agg_supplement_step_review_only`
- `agg_supplement_step_id`
- `agg_supplement_step_reason`
- `agg_supplement_start_raw_point_index`
- `agg_supplement_end_raw_point_index`
- `agg_supplement_start_elapsed_sec`
- `agg_supplement_end_elapsed_sec`
- `agg_supplement_duration_sec`
- `agg_supplement_horizontal_distance_m`
- `agg_supplement_start_elevation_m`
- `agg_supplement_end_elevation_m`
- `agg_supplement_delta_elevation_m`
- `agg_supplement_slope_pct`
- `agg_supplemental_gain_m`
- `agg_supplemental_loss_m`
- `agg_total_gain_m`
- `agg_total_loss_m`
- `agg_supplement_excluded_reason`

## full26 QA 結果

v1k5 builder full26：

- PASS / FAIL = 26 / 0
- 沒有任何 activity 的 gain/loss supplement delta 超過 30 m
- 高 gain/loss review case `30_1` 與 `38_1` 補充量為 0
- artifact / ambiguity focus case `15_1`、`23_1`、`35_1`、`29_1`、`6_1` 補充量為 0
- `37_1`、`36_1`、`3_1` 有合理補充，並已進行 visual smoke inspection

v1k5 visual QA full26：

- PASS / FAIL = 26 / 0
- 26 / 26 activities 均產生 HTML
- batch summary CSV / JSON 正常產生
- manual visual smoke checked：
  - `37_1`
  - `36_1`
  - `3_1`
  - `30_1`
  - `38_1`

## 關鍵 full26 補充結果

| Activity | v1k3 baseline gain/loss | v1k5 supplement gain/loss | v1k5 total gain/loss | 判讀 |
|---|---:|---:|---:|---|
| `37_1` | 46.201 / 12.541 | 12.498 / 11.084 | 58.699 / 23.625 | 合理補回低速連續下降低估 |
| `36_1` | 24.527 / 21.912 | 12.156 / 16.015 | 36.683 / 37.927 | 補量較高，但 visual QA 合理 |
| `3_1` | 16.902 / 25.902 | 14.727 / 14.151 | 31.629 / 40.053 | 補量較高，但 visual QA 合理 |
| `30_1` | 193.337 / 214.293 | 0 / 0 | unchanged | 高 gain/loss case 未被補爆 |
| `38_1` | 147.551 / 185.752 | 0 / 0 | unchanged | 高 gain/loss case 未被補爆 |
| `15_1` | 20.624 / 11.541 | 0 / 0 | unchanged | artifact-focus case 未補充 |

## 視覺 QA 判讀

### `37_1`

`37_1` 是 v1k3 conservative-bias 最明顯的案例。

v1k5 加入 8 個 supplement step：

- supplemental gain = 12.498 m
- supplemental loss = 11.084 m

visual QA 判讀：

- supplement markers 數量少，沒有整段亂補。
- markers 出現在合理的低速高程趨勢段。
- 沒有在 terminal flat section 大量補點。
- delta elevation 約為數公尺級，沒有出現暴衝。
- slope 未超過 45% gate，因此 review-only steps = 0。

判定：

```text
37_1 v1k5 visual smoke: PASS
```

### `36_1`

`36_1` 加入 9 個 supplement step：

- supplemental gain = 12.156 m
- supplemental loss = 16.015 m

visual QA 判讀：

- supplement markers 主要集中在上升段、高點附近與下降段。
- 沒有大量吃進 terminal artifact 區。
- 沒有與 join hard exclusion 區域大規模重疊。
- 補量較高，但仍屬低速小步距保守補充。

判定：

```text
36_1 v1k5 visual smoke: PASS
```

### `3_1`

`3_1` 加入 10 個 supplement step：

- supplemental gain = 14.727 m
- supplemental loss = 14.151 m

visual QA 判讀：

- supplement markers 分布乾淨。
- markers 出現在低速連續高程趨勢區。
- 沒有與 hard-exclusion 區混淆。
- 沒有 elevation artifact 干擾。

判定：

```text
3_1 v1k5 visual smoke: PASS
```

### `30_1` / `38_1`

`30_1` 與 `38_1` 是 v1k3 已知高 gain/loss review case。

v1k5 結果：

- `30_1`: supplement = 0 / 0
- `38_1`: supplement = 0 / 0

判讀：

- v1k5 沒有把已經偏高的 gain/loss case 再補大。
- supplement-only policy 有成功避開高風險或不可信補充段。

判定：

```text
30_1 / 38_1 v1k5 no-supplement check: PASS
```

## 後端使用建議

若需要保守 baseline elevation analytics，使用 v1k3 欄位：

- `calibrated_cumulative_gain_m`
- `calibrated_cumulative_loss_m`

若需要納入低速連續移動補充，使用 v1k5 total 欄位：

- `agg_total_gain_m`
- `agg_total_loss_m`

建議後端同時保留：

- `agg_supplemental_gain_m`
- `agg_supplemental_loss_m`
- `agg_supplement_step_valid`
- `agg_supplement_step_review_only`
- `agg_supplement_step_reason`
- `agg_supplement_excluded_reason`

這樣可以同時提供：

```text
baseline gain/loss
supplemental gain/loss
supplemented total gain/loss
audit trail
```

## Protected Semantics

以下邊界必須維持：

- raw data never overwritten
- v1k3 outputs remain immutable inputs
- v1k5 不覆蓋 v1k3 cumulative gain/loss
- v1k5 只 append supplement 欄位
- wrong-route 不投回 canonical mainline elevation
- off-target 不納入 supplement
- connector 保留，不改成 `MAINLINE_CORE`
- stopped rows 不納入 supplement
- duplicate timestamp non-representative rows 不納入 supplement
- motion artifact rows 不納入 supplement
- elevation artifact rows 不納入 supplement
- hard-excluded rows 不納入 supplement
- review-only supplement steps 不納入 supplemental gain/loss
- visual QA plotter 是 read-only，不修改 CSV / JSON

## v1k5 未處理項目

v1k5 不解決下列問題：

- route-phase-aware elevation join
- full terrain-grade smoothing
- formal activity/model inclusion gate
- facility / radar / THCI evidence
- NLSC row-level lookup beyond IB1E profile-derived elevation
- wrong-route elevation modeling
- summit-anchor hysteresis / smoothing
- v1e2 / v1h2 transition oscillation

v1k5 只處理：

```text
v1k3 因 per-row step_distance < 3m 而保守排除的可信低速連續高程變化
```

## Remaining Repository Items

以下項目不屬於本 pipeline node，不應混入 v1k5 commit：

- `folder_inventory_depth4.csv`
- `folder_role_audit_depth4.csv`
- `configs/risk_semantics/ib3a_rc_v1l_osm_facility_radar_evidence_catalog_v1.csv`
- `scripts/ib3_activity_environment/ib3a_rc_label_transition_continuity_v1f_before_v1f2_patch.py`
- `scripts/ib3_activity_environment/ib3a_rc_plot_mainline_membership_v1h.py`
- `scripts/ib3_activity_environment/ib3a_rc_plot_mainline_membership_with_ib0d_overlay_v1h2.py`

## 下一階段建議

下一階段可二選一：

1. 將 v1k5 定義為後端 gain/loss analytics 的 optional supplement layer。
2. 進入 v1l OSM facility interaction / THCI radar evidence。

仍延後：

- IB3F-RC activity-level feature aggregation
- IB3H-RC formal model inclusion gate
- route-phase-aware IB1E profile candidate selection
- v1e2 / v1h2 summit-anchor smoothing / hysteresis
