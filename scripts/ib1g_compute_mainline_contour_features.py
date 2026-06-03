from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import geopandas as gpd


# =========================================================
# ib1g_compute_mainline_contour_features.py
# 主線直接對齊 NLSC ContourL，不經 RoadL
# =========================================================

# -------------------------
# 0. 路徑設定
# -------------------------
MAINLINE_PATH_FP = Path("ib0b_output/qixing_mainline_ordered_path.geojson")

BASE_DIR = Path("/Users/iddmini/Documents/osm路況研究/112年經建版地形圖數值資料檔(比例尺二萬五千分之一)(SHP檔)/112年經建版地形圖數值資料檔(比例尺二萬五千分之一)(SHP檔)_/圖檔")
TILE = "97233NW"
VEC_DIR = BASE_DIR / TILE / "向量25K"

CONTOUR_FP = VEC_DIR / "ContourL.shp"

OUT_DIR = Path("ib1g_mainline_contour_output")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_GEOJSON = OUT_DIR / "qixing_mainline_contour_features.geojson"
OUT_CSV = OUT_DIR / "qixing_mainline_contour_features.csv"

# -------------------------
# 1. 參數
# -------------------------
SEGMENT_LENGTH_M = 20.0
CONTOUR_BUFFER_M = 3.0
DENSITY_BUFFER_M = 20.0

NOW_UTC = datetime.now(timezone.utc).isoformat()


# =========================================================
# 2. 工具函式
# =========================================================
def guess_elev_field(gdf):
    candidates = [
        "ELEV", "Elev", "elev", "ELEVATION", "elevation",
        "HEIGHT", "Height", "height", "Z", "z", "zv2",
        "Contour", "CONTOUR"
    ]

    cols_lower = {c.lower(): c for c in gdf.columns}

    for c in candidates:
        if c.lower() in cols_lower:
            return cols_lower[c.lower()]

    for c in gdf.columns:
        if pd.api.types.is_numeric_dtype(gdf[c]):
            cl = c.lower()
            if any(k in cl for k in ["elev", "height", "contour", "z"]):
                return c

    return None


def split_linestring_by_length(line, seg_len):
    if line is None or line.is_empty:
        return []

    total_len = line.length
    if total_len <= 0:
        return []

    parts = []
    start = 0.0

    while start < total_len:
        end = min(start + seg_len, total_len)

        p0 = line.interpolate(start)
        p1 = line.interpolate(end)
        seg = type(line)([p0, p1])

        if not seg.is_empty and seg.length > 1.0:
            parts.append(seg)

        if np.isclose(end, total_len):
            break

        start = end

    return parts


def explode_lines(gdf):
    rows = []

    for idx, row in gdf.iterrows():
        geom = row.geometry

        if geom is None or geom.is_empty:
            continue

        if geom.geom_type == "LineString":
            geoms = [geom]
        elif geom.geom_type == "MultiLineString":
            geoms = list(geom.geoms)
        else:
            continue

        for part_id, line in enumerate(geoms):
            new_row = row.copy()
            new_row.geometry = line
            new_row["mainline_part_id"] = part_id
            rows.append(new_row)

    if not rows:
        raise ValueError("主線沒有可用 LineString / MultiLineString geometry")

    return gpd.GeoDataFrame(rows, geometry="geometry", crs=gdf.crs)


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
# 3. 檢查輸入
# =========================================================
for fp in [MAINLINE_PATH_FP, CONTOUR_FP]:
    if not fp.exists():
        raise FileNotFoundError(f"找不到輸入檔：{fp.resolve()}")


# =========================================================
# 4. 讀資料
# =========================================================
mainline = gpd.read_file(MAINLINE_PATH_FP)
contours = gpd.read_file(CONTOUR_FP)

if mainline.empty:
    raise ValueError("mainline ordered path 為空")

if contours.empty:
    raise ValueError("ContourL 為空")

if mainline.crs is None:
    mainline = mainline.set_crs("EPSG:4326")

if contours.crs is None:
    contours = contours.set_crs("EPSG:4326")

contour_elev_col = guess_elev_field(contours)
if contour_elev_col is None:
    raise ValueError("找不到 ContourL 高程欄位")

print("mainline:", len(mainline))
print("contours:", len(contours))
print("contour elev field:", contour_elev_col)


# =========================================================
# 5. 投影到公尺座標
# =========================================================
metric_crs = mainline.estimate_utm_crs()

mainline_m = mainline.to_crs(metric_crs)
contours_m = contours.to_crs(metric_crs)

print("metric CRS:", metric_crs)


# =========================================================
# 6. 主線切成 20m segments
# =========================================================
mainline_lines = explode_lines(mainline_m)

segment_rows = []
global_seq = 0
cum_dist = 0.0

for _, row in mainline_lines.iterrows():
    line = row.geometry
    segs = split_linestring_by_length(line, SEGMENT_LENGTH_M)

    for seg in segs:
        new_row = row.copy()
        new_row.geometry = seg

        seg_len = seg.length

        new_row["route_segment_id"] = global_seq
        new_row["dist_start_m"] = cum_dist
        new_row["dist_end_m"] = cum_dist + seg_len
        new_row["dist_mid_m"] = cum_dist + seg_len / 2
        new_row["segment_len_m"] = seg_len

        segment_rows.append(new_row)

        cum_dist += seg_len
        global_seq += 1

route_seg_m = gpd.GeoDataFrame(segment_rows, geometry="geometry", crs=metric_crs)

print("route segments:", len(route_seg_m))
print("route length m:", round(route_seg_m["segment_len_m"].sum(), 2))


# =========================================================
# 7. Contour intersect / density
# =========================================================
# 7a. 線段本身加小 buffer，避免幾何微小偏移導致 miss
route_buf = route_seg_m.copy()
route_buf["geometry"] = route_buf.geometry.buffer(CONTOUR_BUFFER_M)

joined = gpd.sjoin(
    route_buf[["route_segment_id", "geometry"]],
    contours_m[[contour_elev_col, "geometry"]],
    how="left",
    predicate="intersects",
)

cross_counts = joined.groupby("route_segment_id").size()
unique_elev_counts = joined.groupby("route_segment_id")[contour_elev_col].nunique(dropna=True)

route_seg_m["contour_cross_n"] = (
    route_seg_m["route_segment_id"].map(cross_counts).fillna(0).astype(int)
)
route_seg_m["contour_unique_elev_n"] = (
    route_seg_m["route_segment_id"].map(unique_elev_counts).fillna(0).astype(int)
)

# 7b. 估算等高距
contour_vals = contours_m[contour_elev_col].dropna().sort_values().unique()

if len(contour_vals) >= 2:
    diffs = np.diff(contour_vals)
    diffs = diffs[diffs > 0]
    contour_interval = float(pd.Series(diffs).mode().iloc[0]) if len(diffs) else np.nan
else:
    contour_interval = np.nan

route_seg_m["contour_interval_m"] = contour_interval

# 7c. elevation gain proxy
if pd.notna(contour_interval):
    route_seg_m["elev_gain_contour_est_m"] = (
        route_seg_m["contour_unique_elev_n"] * contour_interval
    )
else:
    route_seg_m["elev_gain_contour_est_m"] = np.nan

route_seg_m["slope_contour_est"] = (
    route_seg_m["elev_gain_contour_est_m"] / route_seg_m["segment_len_m"]
).replace([np.inf, -np.inf], np.nan).clip(lower=0, upper=1.0)

route_seg_m["slope_band_contour"] = route_seg_m["slope_contour_est"].apply(classify_slope_band)

# 7d. contour density：20m buffer 內等高線數
density_buf = route_seg_m.copy()
density_buf["geometry"] = density_buf.geometry.buffer(DENSITY_BUFFER_M)

density_join = gpd.sjoin(
    density_buf[["route_segment_id", "geometry"]],
    contours_m[["geometry"]],
    how="left",
    predicate="intersects",
)

density_counts = density_join.groupby("route_segment_id").size()
route_seg_m["contour_density_20m"] = (
    route_seg_m["route_segment_id"].map(density_counts).fillna(0).astype(int)
)


# =========================================================
# 8. metadata
# =========================================================
route_seg_m["analysis_unit"] = "mainline_segment_20m"
route_seg_m["feature_status"] = "computed_directly_from_mainline_and_contour"
route_seg_m["source_name"] = "NLSC_25K_ContourL"
route_seg_m["tile_id"] = TILE
route_seg_m["contour_source_field"] = contour_elev_col
route_seg_m["pipeline_stage"] = "ib1g_compute_mainline_contour_features"
route_seg_m["derived_at"] = NOW_UTC
route_seg_m["segment_length_target_m"] = SEGMENT_LENGTH_M
route_seg_m["contour_intersection_buffer_m"] = CONTOUR_BUFFER_M
route_seg_m["contour_density_buffer_m"] = DENSITY_BUFFER_M


# =========================================================
# 9. 輸出
# =========================================================
out_gdf = route_seg_m.to_crs("EPSG:4326")
out_df = pd.DataFrame(out_gdf.drop(columns="geometry"))

out_gdf.to_file(OUT_GEOJSON, driver="GeoJSON")
out_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

print("\n完成！")
print("GeoJSON:", OUT_GEOJSON.resolve())
print("CSV:", OUT_CSV.resolve())

print("\n=== slope_band_contour ===")
print(out_df["slope_band_contour"].value_counts(dropna=False))

print("\n=== contour_cross_n ===")
print(out_df["contour_cross_n"].describe())

print("\n=== contour_density_20m ===")
print(out_df["contour_density_20m"].describe())