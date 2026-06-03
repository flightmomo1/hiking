from pathlib import Path
import geopandas as gpd
import folium
import pandas as pd


"""
ib0a_prune_matched_osm_route.py

定位：
- ib0 的第一輪主路徑收斂腳本
- 讀取 ib0 輸出的 matched OSM route
- 依幾何接近程度與 matching 指標去除明顯雜支

主要功能：
1. 讀取 ib0 的 qixing_gpx_osm_matched.geojson
2. 只保留 selected == 1 的路段
3. 依 route_role 採用不同 pruning 門檻
4. 輸出 pruned matched route 與 QA 地圖

注意：
- 本版只做第一輪 pruning
- 尚未加入完整拓樸連續性 / graph shortest path
- 後續若仍有雜支，再做 ib0b continuity 版
"""


# =========================================================
# 0. 路徑設定
# =========================================================
# INPUT_FP = Path("ib0_gpx_osm_match_output/qixing_gpx_osm_matched.geojson")

# OUT_DIR = Path("ib0_gpx_osm_match_output")
# OUT_DIR.mkdir(parents=True, exist_ok=True)

# OUT_FP = OUT_DIR / "qixing_gpx_osm_matched_pruned.geojson"
# OUT_HTML_FP = OUT_DIR / "qixing_gpx_osm_matched_pruned_map.html"
# OUT_CSV_FP = OUT_DIR / "qixing_gpx_osm_matched_pruned_summary.csv"

# =========================================================
# 0. 路徑設定
# =========================================================

# 專案根目錄：與 ib0 保持一致
PROJECT_ROOT = Path(r"C:\mountain_work\115_osm")

# =========================================================
# 0-1. Activity / Route 設定
# =========================================================
ROUTE_ID = "juansi_waterfall_fitcsv_20260503"
ACTIVITY_TYPE = "fit_csv"
ACTIVITY_NAME = "3.csv"

ACTIVITY_DIR = PROJECT_ROOT / "activity_input" / "csv" / "juansi_waterfall"
ACTIVITY_FP = ACTIVITY_DIR / ACTIVITY_NAME

# =========================================================
# 0-2. Ia1 dataset metadata：與 ib0 保持一致
# =========================================================
IA1_VERSION = "v1.2"
IA1_DATASET_ID = "qixing_lengshuikeng_xiaoyoukeng_v1_2_success_20260511"
IA1_SNAPSHOT_TAG = "success_20260511"

# =========================================================
# 0-2. Ib0a 輸入 / 輸出設定
# =========================================================
IB0_STAGE = "ib0_route_match"
IB0A_STAGE = "ib0a_prune"

IB0_OUT_DIR = PROJECT_ROOT / "outputs" / IB0_STAGE / ROUTE_ID
OUT_DIR = PROJECT_ROOT / "outputs" / IB0A_STAGE / ROUTE_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)

INPUT_FP = IB0_OUT_DIR / f"{ROUTE_ID}_activity_osm_matched.geojson"

OUT_FLAG_FP = OUT_DIR / f"{ROUTE_ID}_activity_osm_matched_with_prune_flag.geojson"
OUT_FP = OUT_DIR / f"{ROUTE_ID}_activity_osm_matched_pruned.geojson"
OUT_HTML_FP = OUT_DIR / f"{ROUTE_ID}_activity_osm_matched_pruned_map.html"
OUT_CSV_FP = OUT_DIR / f"{ROUTE_ID}_activity_osm_matched_pruned_summary.csv"

# =========================================================
# 1. pruning 參數
# =========================================================
# # trail 核心段：稍微寬鬆-> 收嚴
# TRAIL_MAX_DISTANCE_M = 8.0 #18.0
# TRAIL_MIN_OVERLAP_RATIO = 0.85 #0.35
# TRAIL_MIN_MATCH_SCORE = 0.85 #0.50

# # 入口 / 接駁道路：較嚴格-> 更嚴格
# APPROACH_MAX_DISTANCE_M = 5.0 #12.0
# APPROACH_MIN_OVERLAP_RATIO = 0.85 #0.45
# APPROACH_MIN_MATCH_SCORE = 0.85 #0.58

# # 若 route_role 不明，採保守
# OTHER_MAX_DISTANCE_M = 5.0 #10.0
# OTHER_MIN_OVERLAP_RATIO = 0.85 #0.50
# OTHER_MIN_MATCH_SCORE = 0.85 #0.60

#ib0a只做輕度 pruning，不要太早決定主線。
# =========================================================
# 1. pruning 參數
# =========================================================
# trail 核心段：輕度 pruning，避免誤殺正確路線
TRAIL_MAX_DISTANCE_M = 12.0
TRAIL_MIN_OVERLAP_RATIO = 0.60
TRAIL_MIN_MATCH_SCORE = 0.60

# 近距離保留條件：避免長 OSM way 因 overlap ratio 偏低被誤刪
TRAIL_NEAR_DISTANCE_KEEP_M = 2.0
TRAIL_NEAR_MIN_OVERLAP_RATIO = 0.15
TRAIL_NEAR_MIN_MATCH_SCORE = 0.65
TRAIL_NEAR_MIN_SEGMENT_LEN_M = 80.0

# 入口 / 接駁道路：仍較嚴格，但不要過度收斂
APPROACH_MAX_DISTANCE_M = 10.0
APPROACH_MIN_OVERLAP_RATIO = 0.65
APPROACH_MIN_MATCH_SCORE = 0.65

# 若 route_role 不明，採保守
OTHER_MAX_DISTANCE_M = 10.0
OTHER_MIN_OVERLAP_RATIO = 0.65
OTHER_MIN_MATCH_SCORE = 0.65

# =========================================================
# 2. 工具函式
# =========================================================
def get_prune_keep(row):
    role = row.get("route_role", "other")
    dist = row.get("distance_to_gpx_m", None)
    overlap = row.get("overlap_ratio", None)
    score = row.get("match_score", None)

    if pd.isna(dist) or pd.isna(overlap) or pd.isna(score):
        return 0

    if role == "trail_core":
        segment_len = row.get("segment_len_m", 0)

        keep_by_normal_rule = (
            (dist <= TRAIL_MAX_DISTANCE_M) and
            (overlap >= TRAIL_MIN_OVERLAP_RATIO) and
            (score >= TRAIL_MIN_MATCH_SCORE)
        )

        keep_by_near_long_way_rule = (
            (dist <= TRAIL_NEAR_DISTANCE_KEEP_M) and
            (overlap >= TRAIL_NEAR_MIN_OVERLAP_RATIO) and
            (score >= TRAIL_NEAR_MIN_MATCH_SCORE) and
            (segment_len >= TRAIL_NEAR_MIN_SEGMENT_LEN_M)
        )

        keep = keep_by_normal_rule or keep_by_near_long_way_rule
        return int(keep)

    #再加「短支線刪除」規則
    elif role == "approach_or_road":
        # 先刪短小且重疊不足的可疑支線
        if row.get("segment_len_m", 0) < 25 and overlap < 0.65:
            return 0

        keep = (
            (dist <= APPROACH_MAX_DISTANCE_M) and
            (overlap >= APPROACH_MIN_OVERLAP_RATIO) and
            (score >= APPROACH_MIN_MATCH_SCORE)
        )
        return int(keep)

    else:
        keep = (
            (dist <= OTHER_MAX_DISTANCE_M) and
            (overlap >= OTHER_MIN_OVERLAP_RATIO) and
            (score >= OTHER_MIN_MATCH_SCORE)
        )
        return int(keep)


def style_pruned(feature):
    kept = feature["properties"].get("prune_keep", 0)
    role = feature["properties"].get("route_role", "other")

    if kept == 1:
        if role == "trail_core":
            return {"color": "red", "weight": 5, "opacity": 0.9}
        elif role == "approach_or_road":
            return {"color": "orange", "weight": 4, "opacity": 0.9}
        else:
            return {"color": "purple", "weight": 4, "opacity": 0.9}
    else:
        return {"color": "gray", "weight": 2, "opacity": 0.35}


def popup_html(row):
    return (
        f"<pre>"
        f"osm_way_id: {row.get('osm_way_id', '')}\n"
        f"name: {row.get('name', '')}\n"
        f"highway: {row.get('highway_norm', '')}\n"
        f"route_role: {row.get('route_role', '')}\n"
        f"distance_to_gpx_m: {row.get('distance_to_gpx_m', float('nan')):.3f}\n"
        f"overlap_ratio: {row.get('overlap_ratio', float('nan')):.3f}\n"
        f"match_score: {row.get('match_score', float('nan')):.3f}\n"
        f"prune_keep: {row.get('prune_keep', 0)}"
        f"</pre>"
    )


# =========================================================
# 3. 讀檔
# =========================================================
print("準備讀取 INPUT_FP：", INPUT_FP.resolve())

if not INPUT_FP.exists():
    raise FileNotFoundError(f"找不到輸入檔：{INPUT_FP.resolve()}")

print("輸入檔存在，開始 gpd.read_file...")
gdf = gpd.read_file(INPUT_FP)
print("gpd.read_file 完成")

if gdf.empty:
    raise ValueError(f"輸入檔為空：{INPUT_FP}")

if gdf.crs is None:
    gdf = gdf.set_crs("EPSG:4326")

print("讀取成功：", INPUT_FP.resolve())
print("輸入筆數：", len(gdf))

# 保守起見，若輸入還含 selected=0，先再過濾一次
if "selected" in gdf.columns:
    print("偵測到 selected 欄位，開始過濾 selected == 1...")
    before_n = len(gdf)
    gdf = gdf[gdf["selected"] == 1].copy()
    print(f"selected 過濾完成：{before_n} -> {len(gdf)}")

if gdf.empty:
    raise ValueError("selected == 1 過濾後無資料")


# =========================================================
# 4. 第一輪 pruning
# =========================================================
gdf["prune_keep"] = gdf.apply(get_prune_keep, axis=1)

# =========================================================
# 4a. metadata：保留 ib0a pruning 參數，方便專利 / 實驗追溯
# =========================================================
gdf["pipeline_stage_ib0a"] = "ib0a_prune_matched_osm_route"

# 與 ib0 metadata 對齊；若 ib0 已有同名欄位，這裡統一補正
gdf["route_id"] = ROUTE_ID
gdf["ia1_version"] = IA1_VERSION
gdf["ia1_dataset_id"] = IA1_DATASET_ID
gdf["ia1_snapshot_tag"] = IA1_SNAPSHOT_TAG
gdf["ib0a_input_source"] = str(INPUT_FP)

# 若 ib0 已輸出 activity_type / activity_source / gpx_source，保留原值；
# 若沒有，補空字串，避免不同批次輸出欄位不一致
if "activity_type" not in gdf.columns:
    gdf["activity_type"] = ACTIVITY_TYPE

if "activity_source" not in gdf.columns:
    gdf["activity_source"] = ACTIVITY_NAME

if "gpx_source" not in gdf.columns:
    gdf["gpx_source"] = ACTIVITY_NAME

if "osm_source" not in gdf.columns:
    gdf["osm_source"] = ""

# ib0a pruning 參數
gdf["trail_max_distance_m"] = TRAIL_MAX_DISTANCE_M
gdf["trail_min_overlap_ratio"] = TRAIL_MIN_OVERLAP_RATIO
gdf["trail_min_match_score"] = TRAIL_MIN_MATCH_SCORE

gdf["trail_near_distance_keep_m"] = TRAIL_NEAR_DISTANCE_KEEP_M
gdf["trail_near_min_overlap_ratio"] = TRAIL_NEAR_MIN_OVERLAP_RATIO
gdf["trail_near_min_match_score"] = TRAIL_NEAR_MIN_MATCH_SCORE
gdf["trail_near_min_segment_len_m"] = TRAIL_NEAR_MIN_SEGMENT_LEN_M

gdf["approach_max_distance_m"] = APPROACH_MAX_DISTANCE_M
gdf["approach_min_overlap_ratio"] = APPROACH_MIN_OVERLAP_RATIO
gdf["approach_min_match_score"] = APPROACH_MIN_MATCH_SCORE

gdf["other_max_distance_m"] = OTHER_MAX_DISTANCE_M
gdf["other_min_overlap_ratio"] = OTHER_MIN_OVERLAP_RATIO
gdf["other_min_match_score"] = OTHER_MIN_MATCH_SCORE

gdf_pruned = gdf[gdf["prune_keep"] == 1].copy()

print("第一輪 pruning 後筆數：", len(gdf_pruned))


# =========================================================
# 5. 輸出 GeoJSON
# =========================================================
# gdf.to_file(OUT_DIR / "qixing_gpx_osm_matched_with_prune_flag.geojson", driver="GeoJSON")
# gdf_pruned.to_file(OUT_FP, driver="GeoJSON")

# print("含 prune flag 輸出：", (OUT_DIR / "qixing_gpx_osm_matched_with_prune_flag.geojson").resolve())
# print("pruned route 輸出：", OUT_FP.resolve())

print("開始輸出 with prune flag GeoJSON...")
gdf.to_file(OUT_FLAG_FP, driver="GeoJSON")
print("with prune flag GeoJSON 輸出完成：", OUT_FLAG_FP.resolve())

print("開始輸出 pruned GeoJSON...")
gdf_pruned.to_file(OUT_FP, driver="GeoJSON")
print("pruned GeoJSON 輸出完成：", OUT_FP.resolve())

# =========================================================
# 6. 輸出摘要 CSV

# =========================================================
summary_rows = []

for (role, hw), sub in gdf.groupby(["route_role", "highway_norm"], dropna=False):
    summary_rows.append({
        "pipeline_stage": "ib0a_prune_matched_osm_route",
        "route_id": ROUTE_ID,
        "ia1_version": IA1_VERSION,
        "ia1_dataset_id": IA1_DATASET_ID,
        "ia1_snapshot_tag": IA1_SNAPSHOT_TAG,

        "activity_type": sub["activity_type"].iloc[0] if "activity_type" in sub.columns and len(sub) > 0 else "",
        "activity_source": sub["activity_source"].iloc[0] if "activity_source" in sub.columns and len(sub) > 0 else "",
        "gpx_source": sub["gpx_source"].iloc[0] if "gpx_source" in sub.columns and len(sub) > 0 else "",
        "osm_source": sub["osm_source"].iloc[0] if "osm_source" in sub.columns and len(sub) > 0 else "",

        "ib0a_input_source": str(INPUT_FP),

        "trail_max_distance_m": TRAIL_MAX_DISTANCE_M,
        "trail_min_overlap_ratio": TRAIL_MIN_OVERLAP_RATIO,
        "trail_min_match_score": TRAIL_MIN_MATCH_SCORE,

        "trail_near_distance_keep_m": TRAIL_NEAR_DISTANCE_KEEP_M,
        "trail_near_min_overlap_ratio": TRAIL_NEAR_MIN_OVERLAP_RATIO,
        "trail_near_min_match_score": TRAIL_NEAR_MIN_MATCH_SCORE,
        "trail_near_min_segment_len_m": TRAIL_NEAR_MIN_SEGMENT_LEN_M,

        "approach_max_distance_m": APPROACH_MAX_DISTANCE_M,
        "approach_min_overlap_ratio": APPROACH_MIN_OVERLAP_RATIO,
        "approach_min_match_score": APPROACH_MIN_MATCH_SCORE,

        "other_max_distance_m": OTHER_MAX_DISTANCE_M,
        "other_min_overlap_ratio": OTHER_MIN_OVERLAP_RATIO,
        "other_min_match_score": OTHER_MIN_MATCH_SCORE,

        "route_role": role,
        "highway_norm": hw,
        "matched_n": len(sub),
        "kept_n": int(sub["prune_keep"].sum()),
        "mean_distance_to_gpx_m": sub["distance_to_gpx_m"].mean(),
        "mean_overlap_ratio": sub["overlap_ratio"].mean(),
        "mean_match_score": sub["match_score"].mean(),
    })

summary_df = pd.DataFrame(summary_rows).sort_values(
    by=["kept_n", "matched_n"],
    ascending=[False, False]
)
summary_df.to_csv(OUT_CSV_FP, index=False, encoding="utf-8-sig")

print("摘要輸出：", OUT_CSV_FP.resolve())


# =========================================================
# 7. QA 地圖
# =========================================================
# 用資料中心點開圖
metric_crs = gdf.estimate_utm_crs()
gdf_m = gdf.to_crs(metric_crs)

center_geom = (
    gdf_m.geometry.union_all().centroid
    if hasattr(gdf_m.geometry, "union_all")
    else gdf_m.geometry.unary_union.centroid
)
center = gpd.GeoSeries([center_geom], crs=metric_crs).to_crs("EPSG:4326")
center = [center.iloc[0].y, center.iloc[0].x]

m = folium.Map(
    location=center,
    zoom_start=14,
    tiles="CartoDB positron",
    width="100%",
    height="800px",
)

fg_all = folium.FeatureGroup(name="matched_with_prune_flag", show=True)
fg_kept = folium.FeatureGroup(name="pruned_kept_only", show=True)

for _, row in gdf.iterrows():
    geom = row.geometry
    popup = folium.Popup(popup_html(row), max_width=350)

    color = "red" if row.get("prune_keep", 0) == 1 and row.get("route_role", "") == "trail_core" else \
            "orange" if row.get("prune_keep", 0) == 1 and row.get("route_role", "") == "approach_or_road" else \
            "gray"

    weight = 5 if row.get("prune_keep", 0) == 1 else 2
    opacity = 0.9 if row.get("prune_keep", 0) == 1 else 0.35

    if geom.geom_type == "LineString":
        coords = [(lat, lon) for lon, lat in geom.coords]
        folium.PolyLine(
            coords,
            color=color,
            weight=weight,
            opacity=opacity,
            popup=popup,
        ).add_to(fg_all)

    elif geom.geom_type == "MultiLineString":
        for line in geom.geoms:
            coords = [(lat, lon) for lon, lat in line.coords]
            folium.PolyLine(
                coords,
                color=color,
                weight=weight,
                opacity=opacity,
                popup=popup,
            ).add_to(fg_all)

for _, row in gdf_pruned.iterrows():
    geom = row.geometry
    popup = folium.Popup(popup_html(row), max_width=350)

    color = "red" if row.get("route_role", "") == "trail_core" else "orange"
    weight = 5
    opacity = 0.95

    if geom.geom_type == "LineString":
        coords = [(lat, lon) for lon, lat in geom.coords]
        folium.PolyLine(
            coords,
            color=color,
            weight=weight,
            opacity=opacity,
            popup=popup,
        ).add_to(fg_kept)

    elif geom.geom_type == "MultiLineString":
        for line in geom.geoms:
            coords = [(lat, lon) for lon, lat in line.coords]
            folium.PolyLine(
                coords,
                color=color,
                weight=weight,
                opacity=opacity,
                popup=popup,
            ).add_to(fg_kept)

fg_all.add_to(m)
fg_kept.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)

print("開始儲存 QA HTML...")
m.save(OUT_HTML_FP)
print("QA HTML 儲存完成：", OUT_HTML_FP.resolve())


# =========================================================
# 8. 終端摘要
# =========================================================
print("\n=== prune summary ===")
print("Route ID:", ROUTE_ID)
print("Ia1 version:", IA1_VERSION)
print("Ia1 dataset:", IA1_DATASET_ID)
print("Ia1 snapshot:", IA1_SNAPSHOT_TAG)
print("Ib0a input:", INPUT_FP)
print("原 matched 筆數：", len(gdf))
print("pruned 保留筆數：", len(gdf_pruned))

print("\n--- kept route_role distribution ---")
if not gdf_pruned.empty:
    print(gdf_pruned["route_role"].value_counts(dropna=False))
else:
    print("無保留資料")

print("\n--- kept highway distribution ---")
if not gdf_pruned.empty:
    print(gdf_pruned["highway_norm"].value_counts(dropna=False))
else:
    print("無保留資料")