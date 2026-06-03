from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd


"""
ia2_enrich_segments_contour.py

定位：
- ia 系列第二支腳本
- 使用國土測繪 25K contour / elev / bridge / hydrology 圖層
- 以路段為主體建立 terrain and hydrology enrich features

主要功能：
1. 讀取國土測繪 25K 圖資（RoadL, ContourL, ElevP, BridgeL, LakeA, WaterfallL/P）
2. 以 RoadL 為主體，建立 segment-level 地形與水文特徵
3. 估算 slope 近似、等高線密度、水文鄰近、橋梁修正等欄位
4. 輸出供 iii.py 使用的 enriched segment GeoJSON

注意：
- 本腳本不是 DEM 原生處理，而是 contour-derived terrain enrich
- 本腳本不直接輸出最終 difficulty / risk / ETA
- 本版本分析單位仍為原始 RoadL 幾何，不是切短後的 segment
"""


# =========================================================
# 0. 路徑設定
# =========================================================
BASE_DIR = Path("/Users/iddmini/Documents/osm路況研究/112年經建版地形圖數值資料檔(比例尺二萬五千分之一)(SHP檔)/112年經建版地形圖數值資料檔(比例尺二萬五千分之一)(SHP檔)_/圖檔")

TILE = "97233NW"
VEC_DIR = BASE_DIR / TILE / "向量25K"

ROAD_FP = VEC_DIR / "RoadL.shp"
CONTOUR_FP = VEC_DIR / "ContourL.shp"
ELEV_FP = VEC_DIR / "ElevP.shp"
BRIDGE_FP = VEC_DIR / "BridgeL.shp"
LAKE_FP = VEC_DIR / "LakeA.shp"
WATERFALL_L_FP = VEC_DIR / "WaterfallL.shp"
WATERFALL_P_FP = VEC_DIR / "WaterfallP.shp"

OUT_DIR = Path("contour_enriched_output")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_FP = OUT_DIR / f"{TILE}_road_contour_enriched.geojson"

ROUTE_ID = "qixing_lengshuikeng_xiaoyoukeng"
SOURCE_NAME = "NLSC_25K_contour"
NOW_UTC = datetime.now(timezone.utc).isoformat()

# =========================================================
# 1. 檔案檢查
# =========================================================
required_files = {
    "ROAD_FP": ROAD_FP,
    "CONTOUR_FP": CONTOUR_FP,
    "ELEV_FP": ELEV_FP,
    "BRIDGE_FP": BRIDGE_FP,
    "LAKE_FP": LAKE_FP,
    "WATERFALL_L_FP": WATERFALL_L_FP,
    "WATERFALL_P_FP": WATERFALL_P_FP,
}

print("=== input file check ===")
for name, fp in required_files.items():
    print(f"{name}: {fp} -> {'OK' if fp.exists() else 'MISSING'}")
print("========================\n")


# =========================================================
# 2. 工具函式
# =========================================================
def empty_gdf(crs="EPSG:4326"):
    return gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs=crs)


def read_layer(fp: Path) -> gpd.GeoDataFrame:
    if not fp.exists():
        print(f"查無檔案，略過：{fp}")
        return empty_gdf()

    gdf = gpd.read_file(fp)

    if gdf.empty:
        print(f"空圖層，略過：{fp}")
        return empty_gdf()

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")

    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    return gdf


def ensure_metric(gdf: gpd.GeoDataFrame, metric_crs=None):
    if gdf.empty:
        return gdf, metric_crs

    if metric_crs is None:
        metric_crs = gdf.estimate_utm_crs()

    return gdf.to_crs(metric_crs), metric_crs


def guess_elev_field(gdf: gpd.GeoDataFrame) -> str | None:
    """
    自動猜測高程欄位。
    先找常見名稱，再退一步從數值欄位中找像 elev/z/contour 的名稱。
    這版可抓到像 zv2 這種欄位。
    """
    candidates = [
        "ELEV", "Elev", "elev", "ELEVATION", "elevation",
        "HEIGHT", "Height", "height", "Z", "z", "Contour", "CONTOUR"
    ]
    cols_lower = {c.lower(): c for c in gdf.columns}

    for c in candidates:
        if c.lower() in cols_lower:
            return cols_lower[c.lower()]

    numeric_cols = []
    for c in gdf.columns:
        if pd.api.types.is_numeric_dtype(gdf[c]):
            numeric_cols.append(c)

    for c in numeric_cols:
        cl = c.lower()
        if any(k in cl for k in ["elev", "height", "contour", "z"]):
            return c

    return None


def nearest_distance(left_gdf: gpd.GeoDataFrame, right_gdf: gpd.GeoDataFrame, out_col: str):
    if left_gdf.empty:
        left_gdf[out_col] = pd.Series(dtype=float)
        return left_gdf

    if right_gdf.empty:
        left_gdf[out_col] = np.nan
        return left_gdf

    union = (
        right_gdf.geometry.union_all()
        if hasattr(right_gdf.geometry, "union_all")
        else right_gdf.geometry.unary_union
    )
    left_gdf[out_col] = left_gdf.geometry.distance(union)
    return left_gdf


def near_any_by_buffer(left_gdf: gpd.GeoDataFrame, right_gdf: gpd.GeoDataFrame, buffer_m: float, out_col: str):
    if left_gdf.empty:
        left_gdf[out_col] = pd.Series(dtype="int8")
        return left_gdf

    if right_gdf.empty:
        left_gdf[out_col] = 0
        return left_gdf

    left_buf = left_gdf.copy()
    left_buf["geometry"] = left_buf.geometry.buffer(buffer_m)

    joined = gpd.sjoin(
        left_buf[["geometry"]].copy(),
        right_gdf[["geometry"]].copy(),
        how="left",
        predicate="intersects",
    )
    hit = joined.index_right.notna().groupby(joined.index).any()
    left_gdf[out_col] = left_gdf.index.to_series().map(hit).fillna(False).astype("int8")

    return left_gdf


def count_unique_contours_per_road(roads_m: gpd.GeoDataFrame, contour_m: gpd.GeoDataFrame, elev_field: str):
    """
    每條 road 與多少條不同高程值的等高線相交。
    並推估常見等高距，進而估計高差。
    """
    if roads_m.empty:
        roads_m["contour_cross_n"] = pd.Series(dtype=int)
        roads_m["contour_unique_elev_n"] = pd.Series(dtype=int)
        roads_m["elev_gain_est_m"] = pd.Series(dtype=float)
        roads_m["contour_interval_m"] = pd.Series(dtype=float)
        return roads_m

    if contour_m.empty or elev_field is None:
        roads_m["contour_cross_n"] = 0
        roads_m["contour_unique_elev_n"] = 0
        roads_m["elev_gain_est_m"] = np.nan
        roads_m["contour_interval_m"] = np.nan
        return roads_m

    joined = gpd.sjoin(
        roads_m[["geometry"]].copy(),
        contour_m[[elev_field, "geometry"]].copy(),
        how="left",
        predicate="intersects",
    )

    cross_counts = joined.groupby(joined.index).size()
    unique_elev_counts = joined.groupby(joined.index)[elev_field].nunique(dropna=True)

    roads_m["contour_cross_n"] = roads_m.index.to_series().map(cross_counts).fillna(0).astype(int)
    roads_m["contour_unique_elev_n"] = roads_m.index.to_series().map(unique_elev_counts).fillna(0).astype(int)

    contour_vals = contour_m[elev_field].dropna().sort_values().unique()
    if len(contour_vals) >= 2:
        diffs = np.diff(contour_vals)
        diffs = diffs[diffs > 0]
        contour_interval = float(pd.Series(diffs).mode().iloc[0]) if len(diffs) > 0 else np.nan
    else:
        contour_interval = np.nan

    roads_m["contour_interval_m"] = contour_interval
    roads_m["elev_gain_est_m"] = (
        roads_m["contour_unique_elev_n"] * contour_interval
        if pd.notna(contour_interval) else np.nan
    )

    return roads_m


def classify_slope_band(s):
    if pd.isna(s):
        return "unknown"
    if s < 0.05:
        return "flat"
    elif s < 0.10:
        return "gentle"
    elif s < 0.20:
        return "moderate"
    elif s < 0.35:
        return "steep"
    else:
        return "very_steep"


def compute_water_risk_hint_rule(row):
    near_lake = row.get("near_lake_m", np.nan)
    near_wf = row.get("near_waterfall_m", np.nan)
    has_bridge = row.get("has_bridge_15m", 0)
    slope = row.get("slope_est_mean", np.nan)

    if pd.notna(near_wf) and near_wf <= 20 and not has_bridge:
        return "high"
    if pd.notna(near_lake) and near_lake <= 20 and pd.notna(slope) and slope >= 0.15:
        return "medium"
    if (pd.notna(near_lake) and near_lake <= 40) or (pd.notna(near_wf) and near_wf <= 40):
        return "low"
    return "none"


# =========================================================
# 3. 讀取國土測繪圖層
# =========================================================
roads = read_layer(ROAD_FP)
contours = read_layer(CONTOUR_FP)
elev_pts = read_layer(ELEV_FP)
bridges = read_layer(BRIDGE_FP)
lakes = read_layer(LAKE_FP)
waterfall_l = read_layer(WATERFALL_L_FP)
waterfall_p = read_layer(WATERFALL_P_FP)

if roads.empty:
    raise FileNotFoundError(f"找不到或為空：{ROAD_FP}")

contour_elev_field = guess_elev_field(contours)
elevp_field = guess_elev_field(elev_pts)

print("Contour 欄位：", contour_elev_field)
print("ElevP 欄位：", elevp_field)

if contour_elev_field is None:
    print("警告：Contour 無法辨識高程欄位，slope 相關欄位將為空值。")


# =========================================================
# 4. 投影到公尺座標
# =========================================================
roads_m, metric_crs = ensure_metric(roads)
contours_m = contours.to_crs(metric_crs) if not contours.empty else contours
elev_pts_m = elev_pts.to_crs(metric_crs) if not elev_pts.empty else elev_pts
bridges_m = bridges.to_crs(metric_crs) if not bridges.empty else bridges
lakes_m = lakes.to_crs(metric_crs) if not lakes.empty else lakes
waterfall_l_m = waterfall_l.to_crs(metric_crs) if not waterfall_l.empty else waterfall_l
waterfall_p_m = waterfall_p.to_crs(metric_crs) if not waterfall_p.empty else waterfall_p


# =========================================================
# 5. 基本路段特徵
# =========================================================
roads_m["segment_len_m"] = roads_m.geometry.length
roads_m["analysis_unit"] = "roadl_original"
roads_m["feature_status"] = "computed_on_parent_road"
roads_m["elevp_available"] = 0 if elev_pts_m.empty else 1


# =========================================================
# 6. 用 contour 估坡度
# =========================================================
roads_m = count_unique_contours_per_road(roads_m, contours_m, contour_elev_field)

roads_m["slope_est_mean"] = (
    roads_m["elev_gain_est_m"] / roads_m["segment_len_m"]
).clip(upper=1.0)

roads_m["slope_est_mean"] = roads_m["slope_est_mean"].replace([np.inf, -np.inf], np.nan)
roads_m["slope_band"] = roads_m["slope_est_mean"].apply(classify_slope_band)

# 等高線密度：20m buffer 內的等高線數量
if not contours_m.empty:
    roads_buf20 = roads_m.copy()
    roads_buf20["geometry"] = roads_buf20.geometry.buffer(20)

    join_dense = gpd.sjoin(
        roads_buf20[["geometry"]].copy(),
        contours_m[["geometry"]].copy(),
        how="left",
        predicate="intersects",
    )
    contour_density = join_dense.groupby(join_dense.index).size()
    roads_m["contour_density_20m"] = roads_m.index.to_series().map(contour_density).fillna(0).astype(int)
else:
    roads_m["contour_density_20m"] = 0


# =========================================================
# 7. 水文 / 橋梁 enrich
# =========================================================
roads_m = nearest_distance(roads_m, lakes_m, "near_lake_m")
roads_m = nearest_distance(roads_m, waterfall_l_m, "near_waterfall_line_m")
roads_m = nearest_distance(roads_m, waterfall_p_m, "near_waterfall_point_m")
roads_m = nearest_distance(roads_m, bridges_m, "near_bridge_m")

roads_m["near_waterfall_m"] = roads_m[["near_waterfall_line_m", "near_waterfall_point_m"]].min(axis=1)
roads_m["near_water_m"] = roads_m[["near_lake_m", "near_waterfall_m"]].min(axis=1)

roads_m = near_any_by_buffer(roads_m, bridges_m, 15, "has_bridge_15m")
roads_m = near_any_by_buffer(roads_m, lakes_m, 20, "touch_lake_20m")
roads_m = near_any_by_buffer(roads_m, waterfall_l_m, 20, "touch_waterfall_line_20m")
roads_m = near_any_by_buffer(roads_m, waterfall_p_m, 20, "touch_waterfall_point_20m")

roads_m["near_water_20m"] = (
    (roads_m["near_lake_m"] <= 20) |
    (roads_m["near_waterfall_m"] <= 20)
).fillna(False).astype("int8")


# =========================================================
# 8. 風險提示
# =========================================================
roads_m["water_risk_hint_rule"] = roads_m.apply(compute_water_risk_hint_rule, axis=1)



# =========================================================
# 9. 輸出
# =========================================================
roads_out = roads_m.to_crs(roads.crs if roads.crs is not None else "EPSG:4326")

roads_out["tile_id"] = TILE
roads_out["source_name"] = SOURCE_NAME
roads_out["source_updated_at"] = NOW_UTC  # TODO: replace with official dataset timestamp
roads_out["derived_at"] = NOW_UTC
roads_out["pipeline_stage"] = "ia2_nlsc_contour_hydrology_enrich"

# 檔案寫入
roads_out.to_file(OUT_FP, driver="GeoJSON")

print("\n完成！")
print("輸出檔案：", OUT_FP.resolve())

print("\n新增欄位：")
print([
    "analysis_unit",
    "feature_status",
    "segment_len_m",
    "contour_cross_n",
    "contour_unique_elev_n",
    "contour_interval_m",
    "elev_gain_est_m",
    "slope_est_mean",
    "slope_band",
    "contour_density_20m",
    "near_lake_m",
    "near_waterfall_line_m",
    "near_waterfall_point_m",
    "near_waterfall_m",
    "near_water_m",
    "near_bridge_m",
    "has_bridge_15m",
    "touch_lake_20m",
    "touch_waterfall_line_20m",
    "touch_waterfall_point_20m",
    "near_water_20m",
    "water_risk_hint_rule",
    "elevp_available",
])

print("\n摘要：")
print("roads:", len(roads_m))
print("\n--- slope_band ---")
print(roads_m["slope_band"].value_counts(dropna=False))
print("\n--- water_risk_hint_rule ---")
print(roads_m["water_risk_hint_rule"].value_counts(dropna=False))