from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import geopandas as gpd


# =========================================================
# 設定
# =========================================================
CASE_ID = "qixing_xiaoyoukeng_roundtrip_joyhike"
CASE_NAME = "七星山小油坑進出 Joyhike"

# 使用 ib0d v1.1 裁切後的 ordered path
MAINLINE_FP = (
    Path("ib0d_output")
    / CASE_ID
    / "qixing_mainline_ordered_path_trimmed.geojson"
)

# 本機 NLSC 25K 等高線路徑
BASE_DIR = Path("C:/mountain_work/115_osm")
TILE = "97233NW"
CONTOUR_FP = BASE_DIR / TILE / "向量25K" / "ContourL.shp"

OUT_DIR = Path("ib1g_v2_output") / CASE_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_CSV = OUT_DIR / "qixing_contour_window_features.csv"
OUT_GEOJSON = OUT_DIR / "qixing_contour_window_features.geojson"

SEGMENT_LEN = 20.0
WINDOW_RADIUS = 50.0
DENSITY_BUFFER = 20.0

NOW = datetime.now(timezone.utc).isoformat()


# =========================================================
# 工具
# =========================================================
def guess_elev_col(gdf):
    for c in gdf.columns:
        if any(k in c.lower() for k in ["elev", "z", "height"]):
            return c
    raise ValueError("找不到高程欄位")


def split_line(line, step):
    total = line.length

    pts = list(np.arange(0, total, step))

    if len(pts) == 0 or pts[0] != 0:
        pts.insert(0, 0)

    if pts[-1] < total:
        pts.append(total)

    segs = []

    for i in range(len(pts) - 1):
        p0 = pts[i]
        p1 = pts[i + 1]

        if p1 <= p0:
            continue

        seg = type(line)([
            line.interpolate(p0),
            line.interpolate(p1),
        ])

        segs.append(seg)

    return segs

def classify_slope(s):
    if pd.isna(s): return "unknown"
    if s < 0.05: return "flat"
    if s < 0.1: return "gentle"
    if s < 0.2: return "moderate"
    if s < 0.35: return "steep"
    return "very_steep"


# =========================================================
# 輸入檢查
# =========================================================
if not MAINLINE_FP.exists():
    raise FileNotFoundError(f"找不到 mainline：{MAINLINE_FP.resolve()}，請先執行 ib0d")

if not CONTOUR_FP.exists():
    raise FileNotFoundError(f"找不到 NLSC contour：{CONTOUR_FP.resolve()}")


# =========================================================
# 讀資料
# =========================================================
mainline = gpd.read_file(MAINLINE_FP)
contours = gpd.read_file(CONTOUR_FP)

if mainline.crs is None:
    mainline = mainline.set_crs("EPSG:4326")

metric = mainline.estimate_utm_crs()

mainline = mainline.to_crs(metric)
contours = contours.to_crs(metric)

z_col = guess_elev_col(contours)


# =========================================================
# 切主線
# =========================================================
segments = []
dist = 0
idx = 0

for _, row in mainline.iterrows():
    line = row.geometry
    for seg in split_line(line, SEGMENT_LEN):
        seg_len = seg.length

        segments.append({
            "geometry": seg,
            "seg_id": idx,
            "dist_mid": dist + seg_len/2,
            "seg_len": seg_len
        })

        dist += seg_len
        idx += 1

seg_gdf = gpd.GeoDataFrame(segments, geometry="geometry", crs=metric)


# =========================================================
# 建 spatial index
# =========================================================
contours_sindex = contours.sindex


# =========================================================
# 主計算（window）
# =========================================================
elev_min = []
elev_max = []
density = []

for _, row in seg_gdf.iterrows():
    geom = row.geometry
    mid = geom.centroid

    # window
    window = mid.buffer(WINDOW_RADIUS)

    idxs = list(contours_sindex.intersection(window.bounds))
    subset = contours.iloc[idxs]

    subset = subset[subset.intersects(window)]

    if subset.empty:
        elev_min.append(np.nan)
        elev_max.append(np.nan)
        density.append(0)
        continue

    vals = subset[z_col].dropna()

    if len(vals) == 0:
        elev_min.append(np.nan)
        elev_max.append(np.nan)
    else:
        elev_min.append(vals.min())
        elev_max.append(vals.max())

    # density（20m buffer）
    d_buf = geom.buffer(DENSITY_BUFFER)
    idxs2 = list(contours_sindex.intersection(d_buf.bounds))
    subset2 = contours.iloc[idxs2]
    subset2 = subset2[subset2.intersects(d_buf)]

    density.append(len(subset2))


seg_gdf["elev_min"] = elev_min
seg_gdf["elev_max"] = elev_max

seg_gdf["elev_range"] = seg_gdf["elev_max"] - seg_gdf["elev_min"]

seg_gdf["slope_window"] = (
    seg_gdf["elev_range"] / (WINDOW_RADIUS * 2)
)

seg_gdf["slope_band_window"] = seg_gdf["slope_window"].apply(classify_slope)

seg_gdf["contour_density_20m"] = density


# =========================================================
# metadata
# =========================================================
seg_gdf["pipeline_stage"] = "ib1g_v2"
seg_gdf["case_id"] = CASE_ID
seg_gdf["case_name"] = CASE_NAME
seg_gdf["derived_at"] = NOW
seg_gdf["segment_len_m"] = SEGMENT_LEN
seg_gdf["window_radius_m"] = WINDOW_RADIUS
seg_gdf["density_buffer_m"] = DENSITY_BUFFER
seg_gdf["elevation_source"] = "nlsc_contour_window"


# =========================================================
# 輸出
# =========================================================
out = seg_gdf.to_crs("EPSG:4326")

out.to_file(OUT_GEOJSON, driver="GeoJSON")
out.drop(columns="geometry").to_csv(OUT_CSV, index=False)

print("完成")
print(OUT_CSV)

print("\n=== slope_band_window ===")
print(out["slope_band_window"].value_counts())

print("\n=== elev_range ===")
print(out["elev_range"].describe())