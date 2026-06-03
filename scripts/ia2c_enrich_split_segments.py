from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd


"""
ia2c_enrich_split_segments.py

定位：
- ia 系列第二階段的 segment-level 高程 enrich 腳本
- 讀取 ia2b 切好的 20m segment
- 重新計算每個 segment 的 elevation / contour / slope 特徵

主要功能：
1. 讀取 ia2b 產出的 20m segment GeoJSON
2. 使用國土測繪 25K 圖資（ContourL, ElevP）
3. 對每個小段重新計算坡度與高程相關欄位
4. 輸出供 iii.py 使用的高解析度 segment elevation enrich 結果

注意：
- 本腳本只保留高程用途
- 水文 / 橋梁 / 其他語意資訊，後續應優先由 OSM 層提供
- 本腳本不直接輸出最終 difficulty / risk / ETA
"""


# =========================================================
# 0. 路徑設定
# =========================================================
BASE_DIR = Path("/Users/iddmini/Documents/osm路況研究/112年經建版地形圖數值資料檔(比例尺二萬五千分之一)(SHP檔)/112年經建版地形圖數值資料檔(比例尺二萬五千分之一)(SHP檔)_/圖檔")

TILE = "97233NW"
VEC_DIR = BASE_DIR / TILE / "向量25K"

SEGMENT_FP = Path("segment_output/97233NW_segments_20m.geojson")

CONTOUR_FP = VEC_DIR / "ContourL.shp"
ELEV_FP = VEC_DIR / "ElevP.shp"

OUT_DIR = Path("segment_enriched_output")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_FP = OUT_DIR / f"{TILE}_segments_20m_elevation_enriched.geojson"


# =========================================================
# 1. 檔案檢查
# =========================================================
required_files = {
    "SEGMENT_FP": SEGMENT_FP,
    "CONTOUR_FP": CONTOUR_FP,
    "ELEV_FP": ELEV_FP,
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


def count_unique_contours_per_segment(seg_m: gpd.GeoDataFrame, contour_m: gpd.GeoDataFrame, elev_field: str):
    if seg_m.empty:
        seg_m["contour_cross_n"] = pd.Series(dtype=int)
        seg_m["contour_unique_elev_n"] = pd.Series(dtype=int)
        seg_m["elev_gain_est_m"] = pd.Series(dtype=float)
        seg_m["contour_interval_m"] = pd.Series(dtype=float)
        return seg_m

    if contour_m.empty or elev_field is None:
        seg_m["contour_cross_n"] = 0
        seg_m["contour_unique_elev_n"] = 0
        seg_m["elev_gain_est_m"] = np.nan
        seg_m["contour_interval_m"] = np.nan
        return seg_m

    joined = gpd.sjoin(
        seg_m[["geometry"]].copy(),
        contour_m[[elev_field, "geometry"]].copy(),
        how="left",
        predicate="intersects",
    )

    cross_counts = joined.groupby(joined.index).size()
    unique_elev_counts = joined.groupby(joined.index)[elev_field].nunique(dropna=True)

    seg_m["contour_cross_n"] = seg_m.index.to_series().map(cross_counts).fillna(0).astype(int)
    seg_m["contour_unique_elev_n"] = seg_m.index.to_series().map(unique_elev_counts).fillna(0).astype(int)

    contour_vals = contour_m[elev_field].dropna().sort_values().unique()
    if len(contour_vals) >= 2:
        diffs = np.diff(contour_vals)
        diffs = diffs[diffs > 0]
        contour_interval = float(pd.Series(diffs).mode().iloc[0]) if len(diffs) > 0 else np.nan
    else:
        contour_interval = np.nan

    seg_m["contour_interval_m"] = contour_interval
    seg_m["elev_gain_est_m"] = (
        seg_m["contour_unique_elev_n"] * contour_interval
        if pd.notna(contour_interval) else np.nan
    )

    return seg_m


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


# =========================================================
# 3. 讀取資料
# =========================================================
segments = read_layer(SEGMENT_FP)
contours = read_layer(CONTOUR_FP)
elev_pts = read_layer(ELEV_FP)

if segments.empty:
    raise FileNotFoundError(f"找不到或為空：{SEGMENT_FP}")

contour_elev_field = guess_elev_field(contours)
elevp_field = guess_elev_field(elev_pts)

print("Contour 欄位：", contour_elev_field)
print("ElevP 欄位：", elevp_field)

if contour_elev_field is None:
    print("警告：Contour 無法辨識高程欄位，slope 相關欄位將為空值。")


# =========================================================
# 4. 投影到公尺座標
# =========================================================
seg_m, metric_crs = ensure_metric(segments)
contours_m = contours.to_crs(metric_crs) if not contours.empty else contours
elev_pts_m = elev_pts.to_crs(metric_crs) if not elev_pts.empty else elev_pts


# =========================================================
# 5. 基本欄位更新
# =========================================================
seg_m["segment_len_m"] = seg_m.geometry.length
seg_m["analysis_unit"] = "segment_20m_recomputed_elevation_only"
seg_m["feature_status"] = "recomputed_on_segment_elevation_only"
seg_m["elevp_available"] = 0 if elev_pts_m.empty else 1


# =========================================================
# 6. 重新用 contour 計算 segment 坡度
# =========================================================
seg_m = count_unique_contours_per_segment(seg_m, contours_m, contour_elev_field)

seg_m["slope_est_mean"] = (
    seg_m["elev_gain_est_m"] / seg_m["segment_len_m"]
).clip(lower=0, upper=1.0)  #contour noise 可能產生負 slope

seg_m["slope_est_mean"] = seg_m["slope_est_mean"].replace([np.inf, -np.inf], np.nan)
seg_m["slope_band"] = seg_m["slope_est_mean"].apply(classify_slope_band)

if not contours_m.empty:
    seg_buf20 = seg_m.copy()
    seg_buf20["geometry"] = seg_buf20.geometry.buffer(20)

    join_dense = gpd.sjoin(
        seg_buf20[["geometry"]].copy(),
        contours_m[["geometry"]].copy(),
        how="left",
        predicate="intersects",
    )
    contour_density = join_dense.groupby(join_dense.index).size()
    seg_m["contour_density_20m"] = seg_m.index.to_series().map(contour_density).fillna(0).astype(int)
else:
    seg_m["contour_density_20m"] = 0


# =========================================================
# 7. 輸出
# =========================================================
seg_out = seg_m.to_crs(segments.crs if segments.crs is not None else "EPSG:4326")

seg_out["pipeline_stage"] = "ia2c_segment_elevation_enrich"
seg_out["source_name"] = "NLSC_25K_contour"
seg_out["tile_id"] = TILE

seg_out["elevation_source"] = "contour_estimation"

seg_out.to_file(OUT_FP, driver="GeoJSON")

print("\n完成！")
print("輸出檔案：", OUT_FP.resolve())

print("\n新增 / 重算欄位：")
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
    "elevp_available",
])

print("\n摘要：")
print("segments:", len(seg_m))
print("\n--- slope_band ---")
print(seg_m["slope_band"].value_counts(dropna=False))