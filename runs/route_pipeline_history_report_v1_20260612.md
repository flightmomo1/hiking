# Route Pipeline History Report v1

- 日期：2026-06-12
- 分支：codex/route-pipeline-history-report-v1
- 範圍：read-only pipeline history report
- 對象：七星山冷水坑、七星山小油坑、絹絲瀑布、中華科大九五峰
- 目的：整理 IA1→IB2D route pipeline 的歷史執行脈絡、正式 evidence、NLSC tile assignment 與目前缺口
- 本文件不修改 pipeline、不覆蓋 outputs、不宣稱任意活動匯入後可自動選 NLSC 圖號

## 1. Pipeline history summary

| Stage | Role | Historical script / evidence | Status summary |
|---|---|---|---|
| IA1 refreshed OSM raw | Refresh route-buffer OSM raw layers; not route definition | `scripts/ia_osm/ia1_osm_fetch_raw_friendly_cli_qixing_schema.py` | Four formal cases converged |
| IB0 route match | Build OSM candidate and matched route set near activity | historical `ib0_gpx_to_osm_route_v1_cli_updated.py` evidence | Four formal cases converged |
| IB0C anchors | Historical/QA start-via-end landmark anchors | `ib0c_anchor_from_landmarks_v1_2_cli_updated.py` | Qixing/Juansi converged; Zhonghua treated as QA/WARN |
| IB0A control-point projection | Project route control points onto IB0 candidates | `ib0a_project_control_points_to_osm_candidates.py` | Partial because no formal PASS/WARN/FAIL gate |
| IB0A-2 route-axis component QA | Verify anchors/control points are on connected route-axis component | `ib0a2_route_axis_anchor_component_qa.py` | PASS for four cases |
| IB0B mainline | Extract ordered route axis from control-point sequence | `ib0b_route_mainline_extract_abtest_v1_cli_updated_control_point_constrained.py` | Converged for four cases |
| IB0D trimmed mainline | Formal trimmed route axis with self-near QA | `ib0d_v1_3b_control_points_only_contract_qa.py` | L/X/Z accepted WARN; J PASS; all safe for IB1 |
| IB1A route profile | Build 1D route distance/elevation profile | `ib1a_build_route_elevation_profile_cli_updated.py` | PASS for four cases |
| IB1C OSM semantics | Add OSM semantic context along route profile | `ib1c_enrich_route_profile_semantics_cli_updated.py` | PASS for four cases |
| IB1C semantic risk | Audit/apply semantic risk mapping | `ib1c_audit...cli_updated.py`, `ib1c_apply...cli_updated.py` | Earlier WARNs resolved after v1.2 mapping coverage |
| IB1G NLSC contour window | Compute contour/terrain window evidence along route axis | `ib1g_v2_compute_contour_window_features_cli_updated_v1_1.py` | PASS for four cases when correct tile is provided |
| IB1E OSM + NLSC terrain | Merge OSM semantic risk and NLSC terrain evidence by route distance | `ib1e_enrich_route_profile_with_contour_window_terrain_cli_updated.py` | PASS for four cases; match rate 1.0 |
| IB2 route risk | Baseline route risk scoring | `ib2_v2_route_risk_scoring_cli_updated.py` | PASS for four cases |
| IB2D route risk / radar | Offline map, segments, and radar visualization | `ib2d_plot_route_risk_offline_map_cli_updated.py` | PASS for four cases |

## 2. Actual connection logic

IA1 refreshes OSM raw layers within the activity route buffer. It is a map-data refresh step, not route definition.

IB0 reads the activity trace and IA1 `osm_highway_raw.geojson` to produce route candidates and route-match evidence.

IB0C provides historical landmark anchors and QA context. In v1.3b, the formal route-axis authority moved to `configs/route_definitions/route_control_points_v1_3b.csv`.

The formal v1.3b route-axis chain is:

    IB0 candidates
        ↓
    IB0A control-point projection
        ↓
    IB0A-2 route-axis anchor/component QA
        ↓
    IB0B control-point constrained ordered mainline
        ↓
    IB0D trimmed formal mainline

IB0D output then feeds two downstream branches:

    IB0D trimmed mainline
        ↓
    IB1A route profile

and:

    IB0D trimmed mainline
        ↓
    IB1G NLSC contour window

IB1C enriches the IB1A profile with OSM semantics and semantic risk.  
IB1E merges IB1C semantic risk with IB1G contour-window terrain evidence.  
IB2 scores route risk from IB1E.  
IB2D renders route risk, map, segments, and radar.

## 3. Case history

### 3.1 Qixing Lengshuikeng Main Peak

Case:

    qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b

Historical GPX:

    activity_input/gpx/qixing_lengshuikeng_main_peak_20260523/冷水坑到七星山主峰.gpx

Notes:

    - IB0B corrected ascent/descent required-way behavior to preserve return-branch evidence.
    - Formal IB0D route length was approximately 4187.39 m.
    - IB0D produced accepted WARN because same-entry/self-near behavior was expected.
    - Downstream IB1/IB2/IB2D passed.

NLSC tile:

    97233NW

### 3.2 Qixing Xiaoyoukeng Main Peak

Case:

    qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b

Historical GPX:

    activity_input/gpx/qixing_xiaoyoukeng_main_peak_20260315/小油坑七星山主峰.gpx

Notes:

    - Historical trim-leading handling removed trailhead spur behavior.
    - v1.3b control-points-only route length was approximately 3245.06 m.
    - IB0D WARN was accepted.
    - Earlier semantic mapping WARNs were resolved after mapping coverage updates.

NLSC tile:

    97233NW

### 3.3 Juansi Waterfall to Lengshuikeng

Case:

    juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b

Historical route-buffer GPX:

    activity_input/gpx/juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3c/juansi_waterfall_fitcsv_3_routebuffer_source.gpx

Notes:

    - Although the case name contains `fitcsv`, the IA1/IB0 refresh branch used a derived GPX route-buffer source.
    - IB0D was the only one of the four major cases with direct PASS.
    - Formal length was approximately 3695.54 m.
    - Downstream IB1/IB2/IB2D completed.

NLSC tile:

    97233NW

### 3.4 Zhonghua UST / Jiuwufeng

Case:

    zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b

Historical GPX:

    activity_input/gpx/zhonghua_ust_jiuwufeng_roundtrip_biji/中華科大_九五峰_折返_中華科大_route.gpx

Notes:

    - IB0C start/end once used `fallback_gpx_point`, so IB0C should be treated as QA context rather than trim authority.
    - Formal route entry was moved to the trail-core way through control-point config.
    - IB0B/IB0D route length was approximately 5447.78 m.
    - IB0D same-entry WARN was accepted.
    - After NLSC tile correction, downstream IB2/IB2D passed.

NLSC tile:

    97233SW

## 4. NLSC tile conclusion

Historical and formalized tile assignment:

| Case family | Tile |
|---|---|
| Qixing Lengshuikeng | 97233NW |
| Qixing Xiaoyoukeng | 97233NW |
| Juansi Waterfall / Lengshuikeng | 97233NW |
| Zhonghua UST / Jiuwufeng | 97233SW |

Important correction:

    Zhonghua UST / Jiuwufeng must use 97233SW, not 97233NW.

Historical wrong-tile symptoms for Zhonghua when 97233NW was used:

    valid elevation = 0
    slope_unknown_ratio = 1.0
    slope_band_window = unknown
    contour_density_20m = 0
    terrain elevation fields = null
    terrain risk min/mean/max = 0

After correcting to 97233SW:

    valid elevation = 73
    slope_unknown_ratio = 0.0
    terrain risk became non-null
    IB2 / IB2D passed

Current formalized config:

    configs/nlsc/case_level_nlsc_tile_mapping_v1.csv

Important interpretation:

    `case_level_nlsc_tile_mapping_v1.csv` is a case-level formalization of historical tile evidence.
    It is not proof that arbitrary imported activity records can automatically select NLSC tiles.

## 5. Evidence categories

### Formal pipeline evidence

    - v1.3b contract QA roots
    - per-case CSV / GeoJSON / map outputs
    - IB0 route-axis convergence audit
    - IB1 contract QA outputs
    - IB2 / IB2D batch summaries
    - route control-point config

### QA / diagnostic evidence

    - IB0A-2 component QA
    - IB0D self-near QA
    - semantic mapping audit
    - tile intersection / tile assignment audit
    - Zhonghua tile correction before/after evidence

### Archived / historical handoff evidence

    - runs/_archived_replaced/changelog_updated_20260526_qixing.md
    - runs/_archived_replaced/latest_handoff_prompt_updated_20260527_zhonghua.md
    - historical README / handoff / changelog snapshots

### Prototype / review-only evidence

    - old prototype terrain-dominant roots
    - legacy non-contract roots
    - IB1I GPX-vs-contour diagnostics
    - plotting-only outputs
    - THCI version-comparison outputs

These can support historical interpretation, but they are not the v1.3b route-axis contract authority.

## 6. Current formal pipeline status

The current formal route baseline is:

    IB0D v1.3b contract QA
        ↓
    IB1 contract QA
        ↓
    IB2 / IB2D contract QA

The four major cases have completed the formal route pipeline through route risk / map / radar.

Accepted IB0D WARNs are mostly same-entry or self-near route-structure issues. They are not blocking failures.

Zhonghua UST / Jiuwufeng became clean downstream after correcting NLSC tile usage to 97233SW.

## 7. Current limitation: no arbitrary activity-import NLSC tile selector yet

The current pipeline can do:

    known case_id
        ↓
    case-level tile mapping
        ↓
    known NLSC tile
        ↓
    ContourL.shp terrain/elevation processing

The current pipeline cannot yet do:

    arbitrary imported GPX/FIT/CSV activity
        ↓
    automatic route/activity geometry analysis
        ↓
    automatic NLSC tile coverage selection
        ↓
    automatic case-level tile mapping generation

Therefore:

    IB1G accepts `--tile` / `--contour-fp`, but it is not itself a general-purpose NLSC tile selector.

A future selector should compute:

    - activity or route bbox
    - route buffer
    - candidate NLSC tile coverage
    - valid contour/elevation coverage
    - nearest-contour QA
    - single-tile or multi-tile requirement
    - manual review requirement

## 8. Relationship to IB3W

IB3W weather/hydro context should not modify the existing route baseline.

Correct relationship:

    IA1→IB2D establishes route geometry, OSM semantics, NLSC terrain, and route risk baseline.
        ↓
    IB3W adds weather/hydro context evidence on top of known route/case context.

The recent IB3W weather station elevation work currently does:

    route-scoped weather station candidates
        ↓
    primary tile elevation lookup
        ↓
    neighbor tile review
        ↓
    final station elevation table

This is evidence-layer enrichment, not route-risk recalculation.

## 9. Key caution

Do not describe the current system as:

    "匯入活動紀錄即可自動對應 NLSC 圖號"

The accurate description is:

    "對於已建立 case-level mapping 的正式路線，系統可讀取對應 NLSC 圖號並完成地形或 station elevation evidence；但任意活動匯入後自動選圖號的通用 selector 尚未完成。"
