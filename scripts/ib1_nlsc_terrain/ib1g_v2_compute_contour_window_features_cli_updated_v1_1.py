from pathlib import Path
import argparse
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.ops import substring


# =========================================================
# 設定
# =========================================================
PROJECT_ROOT = Path("C:/mountain_work/115_osm")


def resolve_path(value, project_root=PROJECT_ROOT):
    if value is None:
        return None
    p = Path(value)
    if p.is_absolute():
        return p
    return project_root / p


def parse_args():
    parser = argparse.ArgumentParser(
        description="ib1g: compute NLSC contour window terrain features along an ib0d trimmed mainline"
    )
    parser.add_argument("--case-id", default="juansi_waterfall_fitcsv_20260503")
    parser.add_argument("--case-name", default=None)
    parser.add_argument(
        "--route-line-fp",
        default=None,
        help=(
            "ib0d trimmed ordered path GeoJSON. "
            "Default: outputs/ib0d_trimmed_mainline/<case-id>/<case-id>_mainline_ordered_path_trimmed.geojson"
        ),
    )
    parser.add_argument(
        "--contour-fp",
        default=None,
        help="NLSC contour shapefile path. Default: nlsc_raw/97233NW/向量25K/ContourL.shp",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Output folder. Default: outputs/ib1g_contour_window_features/<case-id>",
    )
    parser.add_argument("--tile", default="97233NW")
    parser.add_argument("--segment-len-m", type=float, default=20.0)
    parser.add_argument("--window-radius-m", type=float, default=50.0)
    parser.add_argument("--density-buffer-m", type=float, default=20.0)
    return parser.parse_args()


args = parse_args()

CASE_ID = args.case_id
CASE_NAME = args.case_name or args.case_id

if args.route_line_fp is None:
    MAINLINE_FP = (
        PROJECT_ROOT
        / "outputs"
        / "ib0d_trimmed_mainline"
        / CASE_ID
        / f"{CASE_ID}_mainline_ordered_path_trimmed.geojson"
    )
else:
    MAINLINE_FP = resolve_path(args.route_line_fp)

TILE = args.tile

if args.contour_fp is None:
    CONTOUR_FP = (
        PROJECT_ROOT
        / "nlsc_raw"
        / TILE
        / "向量25K"
        / "ContourL.shp"
    )
else:
    CONTOUR_FP = resolve_path(args.contour_fp)

if args.out_dir is None:
    OUT_DIR = (
        PROJECT_ROOT
        / "outputs"
        / "ib1g_contour_window_features"
        / CASE_ID
    )
else:
    OUT_DIR = resolve_path(args.out_dir)

OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_CSV = OUT_DIR / f"{CASE_ID}_contour_window_features.csv"
OUT_GEOJSON = OUT_DIR / f"{CASE_ID}_contour_window_features.geojson"

SEGMENT_LEN = args.segment_len_m
WINDOW_RADIUS = args.window_radius_m
DENSITY_BUFFER = args.density_buffer_m

NOW = datetime.now(timezone.utc).isoformat()


# =========================================================
# 工具
# =========================================================
def guess_elev_col(gdf):
    for c in gdf.columns:
        if any(k in c.lower() for k in ["elev", "z", "height"]):
            return c
    raise ValueError("找不到高程欄位")


def split_line_with_axis(line, step):
    """
    Split a route line by along-line distance.

    Important:
    - dist_start / dist_end / dist_mid use the true curvilinear route-axis distance.
    - geometry is extracted with shapely.ops.substring, so segment length follows the original
      line instead of a straight chord between two interpolated points.

    The previous chord-based implementation compressed the distance axis on curved paths,
    which caused ib1g dist_mid to stop too early and created ib1e unmatched tail sections.
    """
    total = float(line.length)

    pts = list(np.arange(0, total, step))

    if len(pts) == 0 or pts[0] != 0:
        pts.insert(0, 0.0)

    if pts[-1] < total:
        pts.append(total)

    segs = []

    for i in range(len(pts) - 1):
        p0 = float(pts[i])
        p1 = float(pts[i + 1])

        if p1 <= p0:
            continue

        seg_geom = substring(line, p0, p1)

        if seg_geom is None or seg_geom.is_empty:
            continue

        segs.append({
            "geometry": seg_geom,
            "dist_start_local": p0,
            "dist_end_local": p1,
            "dist_mid_local": (p0 + p1) / 2.0,
            "seg_len_axis_m": p1 - p0,
            "seg_len_geom_m": float(seg_geom.length),
        })

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


print("case:", CASE_ID)
print("case_name:", CASE_NAME)
print("route line:", MAINLINE_FP.resolve())
print("contour:", CONTOUR_FP.resolve())
print("out_dir:", OUT_DIR.resolve())
print("segment_len_m:", SEGMENT_LEN)
print("window_radius_m:", WINDOW_RADIUS)
print("density_buffer_m:", DENSITY_BUFFER)

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
dist_offset = 0.0
idx = 0

for _, row in mainline.iterrows():
    line = row.geometry

    if line is None or line.is_empty:
        continue

    # Explode MultiLineString-like geometry defensively.
    if line.geom_type == "MultiLineString":
        lines_to_process = list(line.geoms)
    else:
        lines_to_process = [line]

    for part in lines_to_process:
        for seg_info in split_line_with_axis(part, SEGMENT_LEN):
            dist_start = dist_offset + seg_info["dist_start_local"]
            dist_end = dist_offset + seg_info["dist_end_local"]
            dist_mid = dist_offset + seg_info["dist_mid_local"]

            segments.append({
                "geometry": seg_info["geometry"],
                "seg_id": idx,
                "dist_start": dist_start,
                "dist_end": dist_end,
                "dist_mid": dist_mid,
                # Keep legacy column name for downstream scripts.
                "seg_len": seg_info["seg_len_axis_m"],
                "seg_len_axis_m": seg_info["seg_len_axis_m"],
                "seg_len_geom_m": seg_info["seg_len_geom_m"],
            })

            idx += 1

        dist_offset += float(part.length)

seg_gdf = gpd.GeoDataFrame(segments, geometry="geometry", crs=metric)

print("mainline axis length m:", round(dist_offset, 2))
print("contour segments:", len(seg_gdf))
if len(seg_gdf) > 0:
    print("dist_mid min/max:", round(float(seg_gdf["dist_mid"].min()), 2), round(float(seg_gdf["dist_mid"].max()), 2))
    print("seg_len_axis sum:", round(float(seg_gdf["seg_len_axis_m"].sum()), 2))
    print("seg_len_geom sum:", round(float(seg_gdf["seg_len_geom_m"].sum()), 2))


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
seg_gdf["pipeline_stage"] = "ib1g_v2_compute_contour_window_features"
seg_gdf["case_id"] = CASE_ID
seg_gdf["case_name"] = CASE_NAME
seg_gdf["derived_at"] = NOW
seg_gdf["segment_len_m"] = SEGMENT_LEN
seg_gdf["window_radius_m"] = WINDOW_RADIUS
seg_gdf["density_buffer_m"] = DENSITY_BUFFER
seg_gdf["elevation_source"] = "nlsc_contour_window"
seg_gdf["route_line_fp"] = str(MAINLINE_FP)
seg_gdf["contour_fp"] = str(CONTOUR_FP)
seg_gdf["nlsc_tile"] = TILE
seg_gdf["distance_axis_method"] = "shapely_substring_true_axis_v1_1"


# =========================================================
# 輸出
# =========================================================
out = seg_gdf.to_crs("EPSG:4326")

out.to_file(OUT_GEOJSON, driver="GeoJSON")
out.drop(columns="geometry").to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

print("完成")
print(OUT_CSV)

print("\n=== slope_band_window ===")
print(out["slope_band_window"].value_counts())

print("\n=== elev_range ===")
print(out["elev_range"].describe())
