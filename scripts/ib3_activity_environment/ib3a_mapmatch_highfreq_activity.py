from pathlib import Path
from datetime import datetime, timezone
import argparse
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
- 適用於 GPX / FIT 轉 CSV / 一般 CSV
- 將原始活動點投影回目前 CASE 的 route distance axis
- 建立穩定 route_dist_m，用於後續速度、停留、ETA、風險 overlay、waypoint observation

目前 CASE：
- juansi_waterfall_fitcsv_20260503
- Prototype A terrain-dominant v1

輸入：
1. outputs/ib1_route_profile/<CASE_ID>/<CASE_ID>_route_profile_points.geojson
2. 113國體測試資料/juansi_waterfall/3.csv 或 activity_input/csv/juansi_waterfall/3.csv 或 GPX

輸出：
1. outputs/ib3a_mapmatched_activity/<CASE_ID>/<CASE_ID>_activity_mapmatched.csv
2. outputs/ib3a_mapmatched_activity/<CASE_ID>/<CASE_ID>_activity_mapmatched.geojson
3. outputs/ib3a_mapmatched_activity/<CASE_ID>/<CASE_ID>_activity_mapmatched_summary.txt

核心欄位：
- time
- raw_lat / raw_lon / raw_ele_m
- raw_hr_bpm / raw_speed_mps（若原始資料存在）
- matched_lat / matched_lon
- raw_route_dist_m
- route_dist_m
- offset_to_mainline_m
- delta_route_dist_m
- speed_route_mps
- forward_speed_route_mps
- is_off_route
- match_quality
"""


# =========================================================
# 0a. CLI arguments
# =========================================================
def parse_cli_args():
    """
    保留原本直接執行單一 case 的用法。
    若由 batch runner 呼叫，則可用 CLI 覆蓋 activity / output 設定。
    """
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--case-id", default=None)
    parser.add_argument("--activity-id", default=None)
    parser.add_argument("--user-id", default=None)
    parser.add_argument("--activity-fp", default=None)
    parser.add_argument("--activity-type", default="auto")
    parser.add_argument("--out-dir", default=None)
    return parser.parse_args()


CLI_ARGS = parse_cli_args()


# =========================================================
# 0. Case / path settings
# =========================================================
CASE_ID = CLI_ARGS.case_id or "juansi_waterfall_fitcsv_20260503"
CASE_NAME = "絹絲瀑布 FIT CSV 20260503"
MODEL_VERSION = "prototype_A_terrain_dominant_v1"
ACTIVITY_ID = CLI_ARGS.activity_id or CASE_ID
USER_ID = CLI_ARGS.user_id or ""
ACTIVITY_TYPE = CLI_ARGS.activity_type or "auto"
ACTIVITY_FP_OVERRIDE = Path(CLI_ARGS.activity_fp) if CLI_ARGS.activity_fp else None
OUTPUT_PREFIX = ACTIVITY_ID if CLI_ARGS.activity_id else CASE_ID

PROJECT_ROOT = Path(r"C:\mountain_work\115_osm")

# 建議使用 ib1a 產生的 route profile points 作為目前 case 的 route distance axis。
MAINLINE_FP = (
    PROJECT_ROOT
    / "outputs"
    / "ib1_route_profile"
    / CASE_ID
    / f"{CASE_ID}_route_profile_points.geojson"
)

# 二選一：GPX 若存在優先；否則使用 FIT CSV。
ACTIVITY_GPX_FP = PROJECT_ROOT / "activity_input" / CASE_ID / f"{CASE_ID}.gpx"

# 目前絹絲瀑布 FIT CSV 原始資料。先保留原始資料夾路徑，再 fallback 到新整理的 activity_input。
ACTIVITY_CSV_CANDIDATES = [
    PROJECT_ROOT / "113國體測試資料" / "juansi_waterfall" / "3.csv",
    PROJECT_ROOT / "activity_input" / "csv" / "juansi_waterfall" / "3.csv",
]

OUT_DIR = (
    Path(CLI_ARGS.out_dir)
    if CLI_ARGS.out_dir
    else PROJECT_ROOT / "outputs" / "ib3a_mapmatched_activity" / CASE_ID
)
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_CSV = OUT_DIR / f"{OUTPUT_PREFIX}_activity_mapmatched.csv"
OUT_GEOJSON = OUT_DIR / f"{OUTPUT_PREFIX}_activity_mapmatched.geojson"
OUT_SUMMARY_TXT = OUT_DIR / f"{OUTPUT_PREFIX}_activity_mapmatched_summary.txt"
OUT_CORE_CSV = OUT_DIR / f"{OUTPUT_PREFIX}_activity_mapmatched_core.csv"
OUT_CORE_GEOJSON = OUT_DIR / f"{OUTPUT_PREFIX}_activity_mapmatched_core.geojson"


# =========================================================
# 1. Parameters
# =========================================================
NOW_UTC = datetime.now(timezone.utc).isoformat()

MAX_CANDIDATE_DIST_M = 40.0
OFF_ROUTE_DIST_M = 50.0

BACKTRACK_TOL_M = 10.0
MAX_SPEED_MPS = 3.0

STOP_SPEED_MPS = 0.20

MIN_DT_S = 0.5
MAX_DT_S_FOR_SPEED = 10.0

SEMICIRCLE_SCALE = 180.0 / (2 ** 31)
GARMIN_EPOCH_OFFSET_S = 631065600


# =========================================================
# 2. Utility functions
# =========================================================
def parse_gpx_points(gpx_fp: Path) -> pd.DataFrame:
    """
    以 ElementTree 解析 GPX，不依賴 gpxpy。
    支援 trkpt lat/lon/ele/time。
    """
    tree = ET.parse(gpx_fp)
    root = tree.getroot()

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
                "raw_hr_bpm": np.nan,
                "raw_speed_mps": np.nan,
            }
        )

    df = pd.DataFrame(rows)

    if df.empty:
        raise ValueError(f"GPX 沒有讀到有效 trkpt: {gpx_fp}")

    df["time"] = pd.to_datetime(df["time"], errors="coerce", utc=True)

    return df


def first_existing_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lower_to_original = {str(c).lower(): c for c in df.columns}

    for c in candidates:
        if c in df.columns:
            return c
        lc = str(c).lower()
        if lc in lower_to_original:
            return lower_to_original[lc]

    return None


def first_existing_file(candidates: list[Path]) -> Path | None:
    for fp in candidates:
        if fp.exists():
            return fp
    return None


def maybe_semicircle_to_degree(series: pd.Series) -> pd.Series:
    """
    Garmin FIT CSV 常用 semicircles。
    若數值超出一般經緯度範圍，視為 semicircles 並轉度。
    """
    s = pd.to_numeric(series, errors="coerce")

    max_abs = s.abs().max(skipna=True)
    if pd.notna(max_abs) and max_abs > 180:
        return s * SEMICIRCLE_SCALE

    return s


def parse_activity_time(series: pd.Series) -> pd.Series:
    """
    支援 ISO 時間與 Garmin FIT seconds。
    FIT CSV 的 record.timestamp[s] 是 Garmin epoch seconds，需要轉成 Unix epoch。
    """
    numeric = pd.to_numeric(series, errors="coerce")

    if numeric.notna().sum() > 0:
        median_value = numeric.dropna().median()
        if median_value > 100000:
            return pd.to_datetime(
                numeric + GARMIN_EPOCH_OFFSET_S,
                unit="s",
                errors="coerce",
                utc=True,
            )

    return pd.to_datetime(series, errors="coerce", utc=True)


def read_activity_points() -> tuple[pd.DataFrame, Path | None, Path | None]:
    """
    優先讀 GPX；若 GPX 不存在，改讀 CSV。
    CSV 支援：
    - lat/lon, latitude/longitude
    - record.position_lat[semicircles] / record.position_long[semicircles]
    - position_lat/position_long Garmin semicircles
    - ele/elevation/altitude/enhanced_altitude
    - timestamp/time/datetime
    - heart_rate
    - speed/enhanced_speed
    """
    if ACTIVITY_FP_OVERRIDE is not None:
        if not ACTIVITY_FP_OVERRIDE.exists():
            raise FileNotFoundError(f"找不到活動輸入檔：{ACTIVITY_FP_OVERRIDE.resolve()}")

        activity_suffix = ACTIVITY_FP_OVERRIDE.suffix.lower()
        activity_type = ACTIVITY_TYPE.lower()

        if activity_type == "gpx" or (activity_type == "auto" and activity_suffix == ".gpx"):
            print("讀取 GPX:", ACTIVITY_FP_OVERRIDE.resolve())
            return parse_gpx_points(ACTIVITY_FP_OVERRIDE), ACTIVITY_FP_OVERRIDE, None

        activity_csv_fp = ACTIVITY_FP_OVERRIDE

    elif ACTIVITY_GPX_FP.exists():
        print("讀取 GPX:", ACTIVITY_GPX_FP.resolve())
        return parse_gpx_points(ACTIVITY_GPX_FP), ACTIVITY_GPX_FP, None

    else:
        activity_csv_fp = first_existing_file(ACTIVITY_CSV_CANDIDATES)

    if activity_csv_fp is not None:
        print("讀取 CSV:", activity_csv_fp.resolve())
        df = pd.read_csv(activity_csv_fp, low_memory=False)

        time_col = first_existing_col(
            df,
            [
                "record.timestamp[s]",
                "record.timestamp",
                "time",
                "timestamp",
                "datetime",
                "date_time",
                "start_time",
            ],
        )

        lat_col = first_existing_col(
            df,
            [
                "record.position_lat[semicircles]",
                "raw_lat",
                "lat",
                "latitude",
                "position_lat",
                "gps_lat",
                "Latitude",
            ],
        )

        lon_col = first_existing_col(
            df,
            [
                "record.position_long[semicircles]",
                "raw_lon",
                "lon",
                "lng",
                "longitude",
                "position_long",
                "position_lon",
                "gps_lon",
                "Longitude",
            ],
        )

        ele_col = first_existing_col(
            df,
            [
                "record.enhanced_altitude[m]",
                "record.altitude[m]",
                "raw_ele_m",
                "ele",
                "elev",
                "elevation",
                "alt",
                "altitude",
                "enhanced_altitude",
            ],
        )

        hr_col = first_existing_col(
            df,
            ["record.heart_rate[bpm]", "heart_rate", "hr", "heartrate", "heart_rate_bpm"],
        )

        speed_col = first_existing_col(
            df,
            [
                "record.enhanced_speed[m/s]",
                "record.speed[m/s]",
                "speed",
                "enhanced_speed",
                "velocity",
                "speed_mps",
            ],
        )

        if lat_col is None or lon_col is None:
            raise ValueError(
                "CSV 缺少經緯度欄位。\n"
                f"目前欄位: {list(df.columns)}"
            )

        out = pd.DataFrame()

        if time_col is not None:
            out["time"] = parse_activity_time(df[time_col])
        else:
            out["time"] = pd.NaT

        out["raw_lat"] = maybe_semicircle_to_degree(df[lat_col])
        out["raw_lon"] = maybe_semicircle_to_degree(df[lon_col])

        if ele_col is not None:
            out["raw_ele_m"] = pd.to_numeric(df[ele_col], errors="coerce")
        else:
            out["raw_ele_m"] = np.nan

        if hr_col is not None:
            out["raw_hr_bpm"] = pd.to_numeric(df[hr_col], errors="coerce")
        else:
            out["raw_hr_bpm"] = np.nan

        if speed_col is not None:
            out["raw_speed_mps"] = pd.to_numeric(df[speed_col], errors="coerce")
        else:
            out["raw_speed_mps"] = np.nan

        # 保留原始列號，方便回查。
        out["source_row_idx"] = df.index

        # 部分 FIT CSV 可能帶有 cumulative distance。
        activity_dist_col = first_existing_col(
            df,
            ["record.distance[m]", "distance", "total_distance", "activity_dist_m", "dist_m"],
        )
        if activity_dist_col is not None:
            out["activity_recorded_dist_m"] = pd.to_numeric(
                df[activity_dist_col],
                errors="coerce",
            )
        else:
            out["activity_recorded_dist_m"] = np.nan

        # 合理經緯度範圍基本檢查。
        out = out[
            out["raw_lat"].between(-90, 90)
            & out["raw_lon"].between(-180, 180)
        ].copy()

        # ---------------------------------------------------------
        # FIT CSV duplicate record cleanup
        # ---------------------------------------------------------
        # 部分 FIT CSV 匯出會產生大量完全重複的 record rows。
        # 若不先去重，後續 delta_time_s 會出現大量 0，
        # route-derived speed 會斷裂、跳動或產生不自然 speed_capped。
        dedup_cols = [
            "time",
            "raw_lat",
            "raw_lon",
            "raw_ele_m",
            "raw_hr_bpm",
            "raw_speed_mps",
            "activity_recorded_dist_m",
        ]

        dedup_cols = [c for c in dedup_cols if c in out.columns]

        before_n = len(out)
        out = out.drop_duplicates(subset=dedup_cols).copy()
        after_n = len(out)

        print(f"FIT CSV dedup: {before_n} -> {after_n}")

        return out, None, activity_csv_fp

    raise FileNotFoundError(
        "找不到活動輸入檔，請放入其中一個：\n"
        f"1. {ACTIVITY_GPX_FP.resolve()}\n"
        + "\n".join(f"{i + 2}. {fp.resolve()}" for i, fp in enumerate(ACTIVITY_CSV_CANDIDATES))
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
        for c in ["dist_m", "profile_dist_m", "cum_dist_m", "distance_m", "sample_idx"]:
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

                candidates.extend(
                    [
                        (d_end_to_start, idx, "append", False),
                        (d_end_to_end, idx, "append", True),
                        (d_start_to_start, idx, "prepend", True),
                        (d_start_to_end, idx, "prepend", False),
                    ]
                )

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
        return "acceptable"
    if constrained or speed_capped:
        return "constrained"
    return "weak"


# =========================================================
# 3. Load mainline
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

print("case:", CASE_ID)
print("mainline:", MAINLINE_FP)
print("mainline rows:", len(mainline))
print("metric CRS:", metric_crs)
print("route length m:", round(route_len_m, 2))
print("CORE CSV:", OUT_CORE_CSV.resolve())
print("CORE GeoJSON:", OUT_CORE_GEOJSON.resolve())


# =========================================================
# 4. Load activity points
# =========================================================
activity, used_activity_gpx_fp, used_activity_csv_fp = read_activity_points()

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
# 5. Project activity points to route axis
# =========================================================
raw_route_dist = []
matched_points_raw = []
offsets = []

for geom in activity_m.geometry:
    s = mainline_line.project(geom)
    p = mainline_line.interpolate(s)
    offset = geom.distance(p)

    raw_route_dist.append(s)
    matched_points_raw.append(p)
    offsets.append(offset)

activity_m["raw_route_dist_m"] = raw_route_dist
activity_m["raw_projected_geometry"] = matched_points_raw
activity_m["offset_to_mainline_m"] = offsets


# =========================================================
# 6. Monotonic distance constraint + speed cap
# =========================================================
route_dist = []
was_backtrack_constrained = []
was_speed_capped = []

prev_s = None
prev_time = None

for _, row in activity_m.iterrows():
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
# 7. Rebuild matched geometry after constraints
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
# 8. Time / speed / status
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


# ---------------------------------------------------------
# analysis_scope
# ---------------------------------------------------------
# route_core:
#   可進入後續 ib3c / ib3d / waypoint observation 的主路線活動點。
# terminal_off_route:
#   已到 route axis 末端附近，但 GPS/活動仍持續；保留作為終點後停留或離線後活動分析。
# off_route:
#   非終點附近的離線點，後續風險 overlay 預設排除。
activity_m["analysis_scope"] = "route_core"

terminal_near_end = (
    activity_m["is_off_route"]
    & (activity_m["route_dist_m"] >= route_len_m - 30.0)
)

activity_m.loc[terminal_near_end, "analysis_scope"] = "terminal_off_route"

activity_m.loc[
    activity_m["is_off_route"] & ~terminal_near_end,
    "analysis_scope"
] = "off_route"

# ---------------------------------------------------------
# Activity-level QA classification
# ---------------------------------------------------------
core_mask = activity_m["analysis_scope"] == "route_core"
core_m = activity_m[core_mask].copy()

if len(core_m) > 0:
    route_dist_min_m = float(core_m["route_dist_m"].min())
    route_dist_max_m = float(core_m["route_dist_m"].max())
    route_coverage_ratio = (route_dist_max_m - route_dist_min_m) / route_len_m
else:
    route_dist_min_m = np.nan
    route_dist_max_m = np.nan
    route_coverage_ratio = 0.0

# 是否涵蓋完整路線：起點與終點都要接近
START_COVERAGE_TOL_M = 100.0
END_COVERAGE_TOL_M = 100.0

if (
    len(core_m) > 0
    and route_dist_min_m <= START_COVERAGE_TOL_M
    and route_dist_max_m >= route_len_m - END_COVERAGE_TOL_M
):
    route_coverage_group = "full_route"
else:
    route_coverage_group = "partial_route"

if len(core_m) > 0 and "speed_capped" in core_m.columns:
    speed_capped_ratio = float(core_m["speed_capped"].astype(bool).mean())
else:
    speed_capped_ratio = np.nan

if pd.isna(speed_capped_ratio):
    speed_quality_group = "unknown"
elif speed_capped_ratio < 0.10:
    speed_quality_group = "good"
elif speed_capped_ratio < 0.20:
    speed_quality_group = "caution"
else:
    speed_quality_group = "poor"

if len(core_m) > 0 and "raw_hr_bpm" in core_m.columns:
    hr_valid_ratio = float(core_m["raw_hr_bpm"].notna().mean())
else:
    hr_valid_ratio = 0.0

if hr_valid_ratio >= 0.95:
    hr_quality_group = "good"
elif hr_valid_ratio > 0:
    hr_quality_group = "partial"
else:
    hr_quality_group = "missing"

if len(core_m) == 0:
    activity_quality_group = "no_route_core"
elif route_coverage_group == "partial_route":
    activity_quality_group = "partial_route_only"
elif speed_quality_group == "poor":
    activity_quality_group = "qa_caution"
elif hr_quality_group == "missing":
    activity_quality_group = "no_hr"
else:
    activity_quality_group = "analysis_ready"





# =========================================================
# 9. Metadata
# =========================================================
activity_m["case_id"] = CASE_ID
activity_m["case_name"] = CASE_NAME
activity_m["activity_id"] = ACTIVITY_ID
activity_m["user_id"] = USER_ID
activity_m["model_version"] = MODEL_VERSION
activity_m["pipeline_stage"] = "ib3a_mapmatch_highfreq_activity"
activity_m["mapmatched_at"] = NOW_UTC
activity_m["mainline_source"] = str(MAINLINE_FP)
activity_m["activity_gpx_source"] = str(used_activity_gpx_fp) if used_activity_gpx_fp else ""
activity_m["activity_csv_source"] = str(used_activity_csv_fp) if used_activity_csv_fp else ""
activity_m["route_length_m"] = route_len_m
activity_m["max_candidate_dist_m"] = MAX_CANDIDATE_DIST_M
activity_m["backtrack_tol_m"] = BACKTRACK_TOL_M
activity_m["max_speed_mps"] = MAX_SPEED_MPS
activity_m["off_route_dist_m"] = OFF_ROUTE_DIST_M
activity_m["route_dist_min_m"] = route_dist_min_m
activity_m["route_dist_max_m"] = route_dist_max_m
activity_m["route_coverage_ratio"] = route_coverage_ratio
activity_m["route_coverage_group"] = route_coverage_group
activity_m["speed_capped_ratio"] = speed_capped_ratio
activity_m["speed_quality_group"] = speed_quality_group
activity_m["hr_valid_ratio"] = hr_valid_ratio
activity_m["hr_quality_group"] = hr_quality_group
activity_m["activity_quality_group"] = activity_quality_group


# =========================================================
# 10. Output
# =========================================================
# GeoJSON 以 matched geometry 為主
out_gdf = activity_m.copy()

# raw geometry / shapely geometry 轉 WKT，避免與輸出 active geometry 欄位衝突
for geom_col in ["geometry", "raw_projected_geometry"]:
    if geom_col in out_gdf.columns:
        out_gdf[f"{geom_col}_wkt"] = out_gdf[geom_col].apply(
            lambda g: g.wkt if g is not None else None
        )
        out_gdf = out_gdf.drop(columns=[geom_col])

# GeoJSON 對 timezone datetime 支援不穩，保留 ISO 字串。
if "time" in out_gdf.columns:
    out_gdf["time_iso"] = out_gdf["time"].astype(str)
    out_gdf = out_gdf.drop(columns=["time"])

out_gdf = gpd.GeoDataFrame(
    out_gdf,
    geometry="matched_geometry",
    crs=metric_crs,
).to_crs("EPSG:4326")

# CSV 不輸出 shapely geometry 欄位
drop_cols = [
    c
    for c in [
        "geometry",
        "raw_projected_geometry",
        "matched_geometry",
    ]
    if c in activity_m.columns
]
out_df = pd.DataFrame(activity_m.drop(columns=drop_cols))

out_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
out_gdf.to_file(OUT_GEOJSON, driver="GeoJSON")
core_df = out_df[out_df["analysis_scope"] == "route_core"].copy()
core_df.to_csv(OUT_CORE_CSV, index=False, encoding="utf-8-sig")

core_gdf = out_gdf[out_gdf["analysis_scope"] == "route_core"].copy()
core_gdf.to_file(OUT_CORE_GEOJSON, driver="GeoJSON")


# =========================================================
# 11. Summary
# =========================================================
summary_lines = [
    "ib3a mapmatch high-frequency activity",
    f"case_id: {CASE_ID}",
    f"case_name: {CASE_NAME}",
    f"activity_id: {ACTIVITY_ID}",
    f"user_id: {USER_ID}",
    f"model_version: {MODEL_VERSION}",
    "",
    f"mainline: {MAINLINE_FP}",
    f"activity_gpx: {used_activity_gpx_fp if used_activity_gpx_fp else ''}",
    f"activity_csv: {used_activity_csv_fp if used_activity_csv_fp else ''}",
    f"output_csv: {OUT_CSV}",
    f"output_geojson: {OUT_GEOJSON}",
    f"output_core_csv: {OUT_CORE_CSV}",
    f"output_core_geojson: {OUT_CORE_GEOJSON}",
    "",
    f"mainline_rows: {len(mainline)}",
    f"activity_points: {len(activity_m)}",
    f"route_length_m: {route_len_m:.2f}",
    f"metric_crs: {metric_crs}",
    "",
    "activity_level_qa:",
    f"  route_dist_min_m: {route_dist_min_m:.2f}" if not np.isnan(route_dist_min_m) else "  route_dist_min_m: NA",
    f"  route_dist_max_m: {route_dist_max_m:.2f}" if not np.isnan(route_dist_max_m) else "  route_dist_max_m: NA",
    f"  route_coverage_ratio: {route_coverage_ratio:.3f}",
    f"  route_coverage_group: {route_coverage_group}",
    f"  speed_capped_ratio: {speed_capped_ratio:.3f}" if not pd.isna(speed_capped_ratio) else "  speed_capped_ratio: NA",
    f"  speed_quality_group: {speed_quality_group}",
    f"  hr_valid_ratio: {hr_valid_ratio:.3f}",
    f"  hr_quality_group: {hr_quality_group}",
    f"  activity_quality_group: {activity_quality_group}",
    "",
    "match_quality:",
    str(activity_m["match_quality"].value_counts(dropna=False)),
    "",
    "analysis_scope:",
    str(activity_m["analysis_scope"].value_counts(dropna=False)),
    "",
    "offset_to_mainline_m:",
    str(activity_m["offset_to_mainline_m"].describe()),
    "",
    "route_dist_m:",
    str(activity_m["route_dist_m"].describe()),
    "",
    "forward_speed_route_mps:",
    str(activity_m["forward_speed_route_mps"].describe()),
    "",
    "constraints:",
    f"backtrack_constrained: {int(activity_m['backtrack_constrained'].sum())}",
    f"speed_capped: {int(activity_m['speed_capped'].sum())}",
    f"off_route: {int(activity_m['is_off_route'].sum())}",
]

OUT_SUMMARY_TXT.write_text("\n".join(summary_lines), encoding="utf-8")


print("\n完成！")
print("CSV:", OUT_CSV.resolve())
print("GeoJSON:", OUT_GEOJSON.resolve())
print("SUMMARY:", OUT_SUMMARY_TXT.resolve())

print("\n=== match_quality ===")
print(activity_m["match_quality"].value_counts(dropna=False))

print("\n=== analysis_scope ===")
print(activity_m["analysis_scope"].value_counts(dropna=False))

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

print("\n=== activity_level_qa ===")
print("route_dist_min_m:", route_dist_min_m)
print("route_dist_max_m:", route_dist_max_m)
print("route_coverage_ratio:", route_coverage_ratio)
print("route_coverage_group:", route_coverage_group)
print("speed_capped_ratio:", speed_capped_ratio)
print("speed_quality_group:", speed_quality_group)
print("hr_valid_ratio:", hr_valid_ratio)
print("hr_quality_group:", hr_quality_group)
print("activity_quality_group:", activity_quality_group)
