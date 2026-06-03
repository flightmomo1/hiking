from pathlib import Path
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString, MultiLineString
from shapely.ops import linemerge, unary_union


"""
ib3a_mapmatch_highfreq_activity.py

定位：
- 高頻活動軌跡 map matching
- 適用於 1Hz GPX / 手機軌跡 / FIT 轉 CSV
- 將原始活動點投影回 ib0b / OSM 主幹路線
- 建立穩定的 route_dist_m，用於後續速度、停留、ETA、風險 overlay

輸入：
1. ib0b_output/qixing_mainline_ordered_path.geojson
2. GPX 檔，或 FIT 轉出的 CSV

輸出：
1. ib3a_mapmatched_activity_output/qixing_activity_mapmatched.csv
2. ib3a_mapmatched_activity_output/qixing_activity_mapmatched.geojson

核心欄位：
- raw_lat / raw_lon / raw_ele_m
- matched_lat / matched_lon
- raw_route_dist_m
- route_dist_m
- offset_to_mainline_m
- delta_route_dist_m
- speed_route_mps
- is_off_route
- match_quality
"""


# =========================================================
# 0. 路徑設定
# =========================================================
MAINLINE_FP = Path("ib1c_route_profile_semantic_output/qixing_route_profile_semantic_enriched.geojson")

# 二選一：
# 1) GPX
ACTIVITY_GPX_FP = Path("/Users/iddmini/Documents/115_Motion改造/FY115_登山/gpx/冷水坑上-七星山東峰-主峰-下小油坑.gpx")

# 2) CSV，若你已經把 FIT/GPX 轉成 CSV，可使用這個
# CSV 欄位建議至少包含：time, lat, lon, ele
ACTIVITY_CSV_FP = Path("activity_input/qixing_activity_points.csv")

OUT_DIR = Path("ib3a_mapmatched_activity_output")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_CSV = OUT_DIR / "qixing_activity_mapmatched.csv"
OUT_GEOJSON = OUT_DIR / "qixing_activity_mapmatched.geojson"


# =========================================================
# 1. 參數
# =========================================================
NOW_UTC = datetime.now(timezone.utc).isoformat()

MAX_CANDIDATE_DIST_M = 40.0
OFF_ROUTE_DIST_M = 50.0

BACKTRACK_TOL_M = 10.0
MAX_SPEED_MPS = 3.0

STOP_SPEED_MPS = 0.20

MIN_DT_S = 0.5
MAX_DT_S_FOR_SPEED = 10.0


# =========================================================
# 2. 工具函式
# =========================================================
def parse_gpx_points(gpx_fp: Path) -> pd.DataFrame:
    """
    以 ElementTree 解析 GPX，不依賴 gpxpy。
    支援 trkpt lat/lon/ele/time。
    """
    tree = ET.parse(gpx_fp)
    root = tree.getroot()

    # GPX namespace
    ns = {}
    if root.tag.startswith("{"):
        uri = root.tag.split("}")[0].strip("{")
        ns = {"gpx": uri}
        trkpt_path = ".//gpx:trkpt"
    else:
        trkpt_path = ".//trkpt"

    rows = []

    for pt in root.findall(trkpt_path, ns):
        lat = pt.attrib.get("lat")
        lon = pt.attrib.get("lon")

        if lat is None or lon is None:
            continue

        ele = None
        time = None

        ele_node = pt.find("gpx:ele", ns) if ns else pt.find("ele")
        time_node = pt.find("gpx:time", ns) if ns else pt.find("time")

        if ele_node is not None and ele_node.text is not None:
            try:
                ele = float(ele_node.text)
            except Exception:
                ele = np.nan

        if time_node is not None and time_node.text is not None:
            time = time_node.text

        rows.append(
            {
                "time": time,
                "raw_lat": float(lat),
                "raw_lon": float(lon),
                "raw_ele_m": ele,
            }
        )

    if not rows:
        raise ValueError(f"GPX 沒有解析到 trkpt：{gpx_fp}")

    df = pd.DataFrame(rows)

    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], errors="coerce", utc=True)

    return df


def read_activity_points() -> pd.DataFrame:
    """
    優先讀 GPX；若 GPX 不存在，改讀 CSV。
    """
    if ACTIVITY_GPX_FP.exists():
        print("讀取 GPX:", ACTIVITY_GPX_FP.resolve())
        return parse_gpx_points(ACTIVITY_GPX_FP)

    if ACTIVITY_CSV_FP.exists():
        print("讀取 CSV:", ACTIVITY_CSV_FP.resolve())
        df = pd.read_csv(ACTIVITY_CSV_FP)

        # 欄位容錯
        rename_map = {}

        for c in df.columns:
            lc = c.lower()
            if lc in ["lat", "latitude"]:
                rename_map[c] = "raw_lat"
            elif lc in ["lon", "lng", "longitude"]:
                rename_map[c] = "raw_lon"
            elif lc in ["ele", "elev", "elevation", "alt", "altitude"]:
                rename_map[c] = "raw_ele_m"
            elif lc in ["timestamp", "datetime"]:
                rename_map[c] = "time"

        df = df.rename(columns=rename_map)

        for c in ["raw_lat", "raw_lon"]:
            if c not in df.columns:
                raise ValueError(f"CSV 缺少必要欄位：{c}")

        if "raw_ele_m" not in df.columns:
            df["raw_ele_m"] = np.nan

        if "time" in df.columns:
            df["time"] = pd.to_datetime(df["time"], errors="coerce", utc=True)
        else:
            df["time"] = pd.NaT

        return df[["time", "raw_lat", "raw_lon", "raw_ele_m"]].copy()

    raise FileNotFoundError(
        "找不到活動輸入檔，請放入其中一個：\n"
        f"1. {ACTIVITY_GPX_FP.resolve()}\n"
        f"2. {ACTIVITY_CSV_FP.resolve()}"
    )


def extract_single_mainline(gdf: gpd.GeoDataFrame):
    """
    將 mainline GeoDataFrame 整併成單一 LineString。
    支援：
    1. 已排序的 Point profile：依 dist_m / sample_idx / index 串成 LineString
    2. LineString / MultiLineString：嘗試 linemerge；若失敗則依端點近鄰串接
    """

    geom_types = set(gdf.geometry.geom_type.unique())

    # -----------------------------------------------------
    # A. 如果是 profile points，直接依距離欄位排序後串成 LineString
    # -----------------------------------------------------
    if geom_types.issubset({"Point"}):
        sort_col = None
        for c in ["dist_m", "cum_dist_m", "distance_m", "sample_idx"]:
            if c in gdf.columns:
                sort_col = c
                break

        gdf_sorted = gdf.sort_values(sort_col).copy() if sort_col else gdf.copy()

        points = list(gdf_sorted.geometry)

        if len(points) < 2:
            raise ValueError("Point profile 少於 2 點，無法建立 LineString")

        line = LineString(points)

        print("mainline built from ordered profile points")
        print("points:", len(points))
        print("length m:", round(line.length, 2))

        return line

    # -----------------------------------------------------
    # B. LineString / MultiLineString
    # -----------------------------------------------------
    geoms = []

    for geom in gdf.geometry:
        if geom is None or geom.is_empty:
            continue

        if geom.geom_type == "LineString":
            geoms.append(geom)
        elif geom.geom_type == "MultiLineString":
            geoms.extend(list(geom.geoms))

    if not geoms:
        raise ValueError("mainline 沒有可用 LineString / MultiLineString")

    merged = linemerge(unary_union(geoms))

    if isinstance(merged, LineString):
        return merged

    # -----------------------------------------------------
    # C. 若 linemerge 後仍是 MultiLineString，依端點最近方式串接
    # -----------------------------------------------------
    if isinstance(merged, MultiLineString):
        lines = list(merged.geoms)
        print("警告：mainline 無法直接 merge，改用端點近鄰串接")
        print("MultiLineString parts:", len(lines))

        # 從最靠近所有線段端點中最左/最前的一條開始，簡單採最長線起始
        current = max(lines, key=lambda x: x.length)
        remaining = [l for l in lines if l is not current]

        coords = list(current.coords)

        while remaining:
            end_pt = Point(coords[-1])
            start_pt = Point(coords[0])

            candidates = []

            for idx, line in enumerate(remaining):
                line_coords = list(line.coords)

                d_end_to_start = end_pt.distance(Point(line_coords[0]))
                d_end_to_end = end_pt.distance(Point(line_coords[-1]))
                d_start_to_start = start_pt.distance(Point(line_coords[0]))
                d_start_to_end = start_pt.distance(Point(line_coords[-1]))

                candidates.extend([
                    (d_end_to_start, idx, "append", False),
                    (d_end_to_end, idx, "append", True),
                    (d_start_to_start, idx, "prepend", True),
                    (d_start_to_end, idx, "prepend", False),
                ])

            candidates.sort(key=lambda x: x[0])
            _, idx, mode, reverse = candidates[0]

            line = remaining.pop(idx)
            line_coords = list(line.coords)
            if reverse:
                line_coords = list(reversed(line_coords))

            if mode == "append":
                coords.extend(line_coords)
            else:
                coords = line_coords + coords

        line = LineString(coords)

        print("mainline stitched by endpoints")
        print("stitched length m:", round(line.length, 2))

        return line

    raise ValueError(f"無法處理 mainline geometry type: {merged.geom_type}")

def classify_match_quality(offset_m, constrained, speed_capped, is_off_route):
    if is_off_route:
        return "off_route"
    if offset_m <= 10 and not constrained and not speed_capped:
        return "good"
    if offset_m <= 25:
        return "fair"
    if offset_m <= OFF_ROUTE_DIST_M:
        return "weak"
    return "poor"


# =========================================================
# 3. 讀取 mainline
# =========================================================
if not MAINLINE_FP.exists():
    raise FileNotFoundError(f"找不到 mainline：{MAINLINE_FP.resolve()}")

mainline = gpd.read_file(MAINLINE_FP)

if mainline.empty:
    raise ValueError("mainline GeoJSON 為空")

if mainline.crs is None:
    mainline = mainline.set_crs("EPSG:4326")

metric_crs = mainline.estimate_utm_crs()
mainline_m = mainline.to_crs(metric_crs)

mainline_line = extract_single_mainline(mainline_m)

route_len_m = mainline_line.length

print("mainline rows:", len(mainline))
print("metric CRS:", metric_crs)
print("route length m:", round(route_len_m, 2))


# =========================================================
# 4. 讀取活動點
# =========================================================
activity = read_activity_points()

activity = activity.dropna(subset=["raw_lat", "raw_lon"]).copy()

if activity.empty:
    raise ValueError("活動點為空")

activity = activity.reset_index(drop=True)
activity["activity_idx"] = activity.index

activity_gdf = gpd.GeoDataFrame(
    activity,
    geometry=gpd.points_from_xy(activity["raw_lon"], activity["raw_lat"]),
    crs="EPSG:4326",
)

activity_m = activity_gdf.to_crs(metric_crs)

print("activity points:", len(activity_m))


# =========================================================
# 5. 點對主線投影
# =========================================================
raw_route_dist = []
matched_points = []
offsets = []

for geom in activity_m.geometry:
    s = mainline_line.project(geom)
    p = mainline_line.interpolate(s)
    offset = geom.distance(p)

    raw_route_dist.append(s)
    matched_points.append(p)
    offsets.append(offset)

activity_m["raw_route_dist_m"] = raw_route_dist
activity_m["offset_to_mainline_m"] = offsets


# =========================================================
# 6. 單調距離約束 + 速度上限
# =========================================================
route_dist = []
was_backtrack_constrained = []
was_speed_capped = []

prev_s = None
prev_time = None

for i, row in activity_m.iterrows():
    s_raw = float(row["raw_route_dist_m"])
    t = row["time"] if "time" in activity_m.columns else pd.NaT

    constrained = False
    speed_capped = False

    if prev_s is None:
        s_corr = s_raw
    else:
        # 允許短暫倒退 BACKTRACK_TOL_M
        min_allowed_s = prev_s - BACKTRACK_TOL_M

        if s_raw < min_allowed_s:
            s_corr = min_allowed_s
            constrained = True
        else:
            s_corr = s_raw

        # 速度上限限制，只在時間合理時啟用
        if pd.notna(t) and pd.notna(prev_time):
            dt_s = (t - prev_time).total_seconds()

            if dt_s >= MIN_DT_S:
                max_forward = MAX_SPEED_MPS * dt_s

                if s_corr > prev_s + max_forward:
                    s_corr = prev_s + max_forward
                    speed_capped = True

        s_corr = min(max(s_corr, 0.0), route_len_m)

    route_dist.append(s_corr)
    was_backtrack_constrained.append(constrained)
    was_speed_capped.append(speed_capped)

    prev_s = s_corr
    prev_time = t


activity_m["route_dist_m"] = route_dist
activity_m["backtrack_constrained"] = was_backtrack_constrained
activity_m["speed_capped"] = was_speed_capped


# =========================================================
# 7. 重新產生 matched geometry
# =========================================================
matched_geom = [
    mainline_line.interpolate(float(s))
    for s in activity_m["route_dist_m"]
]

activity_m["matched_geometry"] = matched_geom

matched_gs = gpd.GeoSeries(
    activity_m["matched_geometry"],
    crs=metric_crs,
).to_crs("EPSG:4326")

activity_m["matched_lon"] = matched_gs.x
activity_m["matched_lat"] = matched_gs.y


# =========================================================
# 8. 時間 / 速度 / 狀態
# =========================================================
activity_m = activity_m.sort_values("activity_idx").reset_index(drop=True)

activity_m["delta_route_dist_m"] = activity_m["route_dist_m"].diff()

if "time" in activity_m.columns:
    activity_m["delta_time_s"] = activity_m["time"].diff().dt.total_seconds()
else:
    activity_m["delta_time_s"] = np.nan

activity_m["speed_route_mps"] = (
    activity_m["delta_route_dist_m"] / activity_m["delta_time_s"]
).replace([np.inf, -np.inf], np.nan)

activity_m["forward_delta_route_dist_m"] = (
    activity_m["delta_route_dist_m"].clip(lower=0)
)

activity_m["forward_speed_route_mps"] = (
    activity_m["forward_delta_route_dist_m"] / activity_m["delta_time_s"]
).replace([np.inf, -np.inf], np.nan)

# 如果時間間隔過大，速度不可信
activity_m.loc[
    activity_m["delta_time_s"] > MAX_DT_S_FOR_SPEED,
    ["speed_route_mps", "forward_speed_route_mps"],
] = np.nan

activity_m["is_stationary"] = (
    activity_m["forward_speed_route_mps"].notna()
    & (activity_m["forward_speed_route_mps"].abs() < STOP_SPEED_MPS)
)

activity_m["is_off_route"] = activity_m["offset_to_mainline_m"] > OFF_ROUTE_DIST_M

activity_m["match_quality"] = [
    classify_match_quality(
        offset_m=row["offset_to_mainline_m"],
        constrained=row["backtrack_constrained"],
        speed_capped=row["speed_capped"],
        is_off_route=row["is_off_route"],
    )
    for _, row in activity_m.iterrows()
]


# =========================================================
# 9. metadata
# =========================================================
activity_m["pipeline_stage"] = "ib3a_mapmatch_highfreq_activity"
activity_m["mapmatched_at"] = NOW_UTC
activity_m["mainline_source"] = str(MAINLINE_FP)
activity_m["route_length_m"] = route_len_m
activity_m["max_candidate_dist_m"] = MAX_CANDIDATE_DIST_M
activity_m["backtrack_tol_m"] = BACKTRACK_TOL_M
activity_m["max_speed_mps"] = MAX_SPEED_MPS


# =========================================================
# 10. 輸出
# =========================================================
# GeoJSON 以 matched geometry 為主
out_gdf = activity_m.copy()

# 原始 raw geometry 先轉成 WKT 字串保存，避免與輸出 geometry 欄位衝突
if "geometry" in out_gdf.columns:
    out_gdf["raw_geometry_wkt"] = out_gdf["geometry"].apply(
        lambda g: g.wkt if g is not None else None
    )
    out_gdf = out_gdf.drop(columns=["geometry"])

out_gdf = gpd.GeoDataFrame(
    out_gdf,
    geometry="matched_geometry",
    crs=metric_crs,
).to_crs("EPSG:4326")

# 不要 rename_geometry("geometry")，GeoPandas 輸出時會自動把 active geometry 寫成 geometry

# CSV 不輸出 shapely geometry 欄位
drop_cols = [c for c in ["geometry", "matched_geometry"] if c in activity_m.columns]
out_df = pd.DataFrame(activity_m.drop(columns=drop_cols))

out_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

out_gdf.to_file(OUT_GEOJSON, driver="GeoJSON")


# =========================================================
# 11. 摘要
# =========================================================
print("\n完成！")
print("CSV:", OUT_CSV.resolve())
print("GeoJSON:", OUT_GEOJSON.resolve())

print("\n=== match_quality ===")
print(activity_m["match_quality"].value_counts(dropna=False))

print("\n=== offset_to_mainline_m ===")
print(activity_m["offset_to_mainline_m"].describe())

print("\n=== route_dist_m ===")
print(activity_m["route_dist_m"].describe())

print("\n=== speed_route_mps ===")
print(activity_m["speed_route_mps"].describe())

print("\n=== forward_speed_route_mps ===")
print(activity_m["forward_speed_route_mps"].describe())

print("\n=== constraints ===")
print("backtrack_constrained:", int(activity_m["backtrack_constrained"].sum()))
print("speed_capped:", int(activity_m["speed_capped"].sum()))
print("off_route:", int(activity_m["is_off_route"].sum()))