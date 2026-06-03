# -*- coding: utf-8 -*-
from pathlib import Path
import sqlite3
import xml.etree.ElementTree as ET
import math

import pandas as pd
import numpy as np


# =========================================================
# A. Input / Output
# =========================================================

# SCENARIO_NAME = "actual_gpx_9stations"
# USE_ACTIVITY_GPX_TIME = True  # True：依 GPX 活動時間自動產生時間窗；False：使用下方手動指定時間窗
SCENARIO_NAME = "scenario_0430_9stations"
USE_ACTIVITY_GPX_TIME = False

DB_PATH = Path(
    "/Users/iddmini/Documents/115_Motion改造/FY115_登山/weather/"
    "tw_weather_2026-05-01.sqlite3"
)

# 活動 GPX：用來自動抓活動時間窗
ACTIVITY_GPX = Path(
    "/Users/iddmini/Documents/115_Motion改造/FY115_登山/gpx/"
    "冷水坑上-七星山東峰-主峰-下小油坑.gpx"
)

IN_WEATHER_STATIONS_CSV = Path(
    "ib3_environment_output/qixing_nearby_weather_stations.csv"
)

IN_WATER_STATIONS_CSV = Path(
    "ib3_environment_output/qixing_nearby_water_stations.csv"
)

OUT_DIR = Path("ib3_environment_output") / SCENARIO_NAME

OUT_WEATHER_WINDOW_CSV = OUT_DIR / "qixing_weather_window.csv"
OUT_WEATHER_SUMMARY_CSV = OUT_DIR / "qixing_weather_summary_by_station.csv"

OUT_WATER_WINDOW_CSV = OUT_DIR / "qixing_water_window.csv"
OUT_WATER_SUMMARY_CSV = OUT_DIR / "qixing_water_summary_by_station.csv"

OUT_ENV_METADATA_CSV = OUT_DIR / "qixing_environment_window_metadata.csv"

OUT_WEATHER_STATION_CANDIDATES_CSV = (
    OUT_DIR / "qixing_weather_station_candidates.csv"
)

OUT_WEATHER_STATION_COVERAGE_CSV = (
    OUT_DIR / "qixing_weather_station_coverage_summary.csv"
)


# =========================================================
# B. Time window
# =========================================================
# True：依 GPX 活動時間自動產生時間窗
# False：使用下方手動指定時間窗
# USE_ACTIVITY_GPX_TIME 已在 A. Input / Output 區設定，這裡不要重複設定

# 活動前後 buffer
PRE_ACTIVITY_HOURS = 3
POST_ACTIVITY_HOURS = 1

# 手動模式：氣象資料 obs_time 多為 UTC: +00:00
MANUAL_WEATHER_START_TIME = "2026-04-29T16:00:00+00:00"
MANUAL_WEATHER_END_TIME = "2026-04-30T15:59:59+00:00"

# 手動模式：水位資料 obs_time 多為台灣時間: +08:00
MANUAL_WATER_START_TIME = "2026-04-30T00:00:00+08:00"
MANUAL_WATER_END_TIME = "2026-04-30T23:59:59+08:00"


# =========================================================
# C. Fallback normal baseline
# =========================================================
# 查不到活動時間窗資料時，不讓流程中斷。
# 這裡的 normal baseline 不是宣稱當天天氣正常，
# 而是「缺資料時不額外加權」的基準條件。
ENABLE_FALLBACK_NORMAL = True

FALLBACK_REASON_NO_WEATHER = "no_weather_data_in_activity_window"
FALLBACK_REASON_NO_WATER = "no_water_data_in_activity_window"

FALLBACK_WEATHER_ROW = {
    "station_id": "FALLBACK_NORMAL",
    "station_name": "Normal baseline",
    "n_obs": 0,
    "first_obs_time": "",
    "last_obs_time": "",

    # 風險中性：降雨 0、風速 0、濕度 0，避免 ib3c 在未改前誤加權
    "temperature_mean_c": 20.0,
    "temperature_min_c": 20.0,
    "temperature_max_c": 20.0,

    "humidity_mean_pct": 0.0,
    "humidity_min_pct": 0.0,
    "humidity_max_pct": 0.0,

    "pressure_mean_hpa": np.nan,

    "wind_speed_mean_ms": 0.0,
    "wind_speed_max_ms": 0.0,
    "wind_gust_max_ms": 0.0,

    "precipitation_sum_mm": 0.0,
    "precipitation_max_mm": 0.0,
    "precipitation_10min_max_mm": 0.0,
    "precipitation_1hr_max_mm": 0.0,

    "visibility_min_m": np.nan,
    "visibility_mean_m": np.nan,

    "uv_index_max": np.nan,

    "dist_to_route_center_km": np.nan,
    "latitude": np.nan,
    "longitude": np.nan,
    "county_name": "",
    "town_name": "",

    "weather_available": 0,
    "fallback_used": 1,
    "fallback_reason": FALLBACK_REASON_NO_WEATHER,
}

FALLBACK_WATER_ROW = {
    "station_id": "FALLBACK_NORMAL",
    "station_name": "Normal baseline",
    "river_name": "",

    "n_obs": 0,
    "first_obs_time": "",
    "last_obs_time": "",

    # 風險中性：水位變化與波動為 0
    "water_level_mean_m": 0.0,
    "water_level_min_m": 0.0,
    "water_level_max_m": 0.0,
    "water_level_range_m": 0.0,
    "water_level_first_m": 0.0,
    "water_level_last_m": 0.0,
    "water_level_change_m": 0.0,

    "valid_check_result_ratio": np.nan,

    "dist_to_route_center_km": np.nan,
    "latitude": np.nan,
    "longitude": np.nan,
    "county_name": "",
    "town_name": "",

    "hydro_available": 0,
    "fallback_used": 1,
    "fallback_reason": FALLBACK_REASON_NO_WATER,
}


# =========================================================
# D. Preferred stations
# =========================================================
PREFERRED_WEATHER_STATIONS = [
    "466930",  # 陽明山
    "466910",  # 鞍部
    "C0AC40",  # 大屯山
    "A0A460",  # 文化大學
    "C0AH40",  # 平等
]

PREFERRED_WATER_STATIONS = [
    "1140H179",  # 磺溪橋_北
    "1140H180",  # 中和橋_北
    "1140H175",  # 薇閣_北
    "1140H162",  # 三和橋
    "1010H006",  # 新磺溪橋(即時)
]

# =========================================================
# D2. Dynamic weather station search
# =========================================================
ENABLE_DYNAMIC_WEATHER_STATION_SEARCH = True    #false是5版本; true是動態版本

WEATHER_STATION_SEARCH_RADIUS_KM_INITIAL = 6.0
WEATHER_STATION_SEARCH_RADIUS_KM_MAX = 20.0
WEATHER_STATION_SEARCH_RADIUS_STEP_KM = 3.0

MIN_WEATHER_STATION_COUNT = 8
MAX_WEATHER_STATION_COUNT = 12

ENABLE_WEATHER_QUADRANT_BALANCE = True


# =========================================================
# E. Columns
# =========================================================
WEATHER_COLS = [
    "source",
    "dataset_code",
    "station_id",
    "station_name",
    "obs_time",
    "ingested_at",
    "latitude",
    "longitude",
    "county_name",
    "town_name",
    "elevation_m",
    "weather",
    "temperature_c",
    "relative_humidity_pct",
    "pressure_hpa",
    "wind_speed_ms",
    "wind_direction_deg",
    "wind_gust_ms",
    "precipitation_mm",
    "precipitation_10min_mm",
    "precipitation_1hr_mm",
    "sunshine_duration_min",
    "visibility_m",
    "uv_index",
    "qc_flag",
]

WATER_COLS = [
    "source",
    "dataset_code",
    "station_id",
    "observatory_identifier",
    "station_name",
    "obs_time",
    "ingested_at",
    "latitude",
    "longitude",
    "river_name",
    "county_name",
    "town_name",
    "water_level_m",
    "check_result",
    "check_desc",
    "voltage",
    "qc_flag",
]


# =========================================================
# F. Utility
# =========================================================
def ensure_exists(fp: Path):
    if not fp.exists():
        raise FileNotFoundError(f"找不到檔案：{fp.resolve()}")


def strip_namespace(tag):
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def parse_gpx_time_range(gpx_path: Path):
    """
    讀 GPX trkpt time，回傳 UTC start/end Timestamp。
    """
    ensure_exists(gpx_path)

    tree = ET.parse(gpx_path)
    root = tree.getroot()

    times = []

    for elem in root.iter():
        if strip_namespace(elem.tag) != "trkpt":
            continue

        for child in elem:
            if strip_namespace(child.tag) == "time" and child.text:
                t = pd.to_datetime(child.text, errors="coerce", utc=True)
                if pd.notna(t):
                    times.append(t)

    if not times:
        raise ValueError(f"GPX 中沒有可用時間欄位：{gpx_path}")

    start_time = min(times)
    end_time = max(times)

    return start_time, end_time

def read_gpx_points_for_center(gpx_path: Path):
    """
    Read GPX track points for calculating route center.
    """
    ensure_exists(gpx_path)

    tree = ET.parse(gpx_path)
    root = tree.getroot()

    pts = []

    for elem in root.iter():
        if strip_namespace(elem.tag) != "trkpt":
            continue

        try:
            lat = float(elem.attrib["lat"])
            lon = float(elem.attrib["lon"])
            pts.append((lat, lon))
        except Exception:
            continue

    if not pts:
        raise ValueError(f"GPX 中沒有可用 trkpt 座標：{gpx_path}")

    return pd.DataFrame(pts, columns=["lat", "lon"])


def build_time_windows():
    """
    回傳：
    - activity_start_utc
    - activity_end_utc
    - weather_start_time / weather_end_time: UTC +00:00 字串
    - water_start_time / water_end_time: Asia/Taipei +08:00 字串
    """
    if USE_ACTIVITY_GPX_TIME:
        activity_start_utc, activity_end_utc = parse_gpx_time_range(ACTIVITY_GPX)

        weather_start = activity_start_utc - pd.Timedelta(hours=PRE_ACTIVITY_HOURS)
        weather_end = activity_end_utc + pd.Timedelta(hours=POST_ACTIVITY_HOURS)

        water_start = weather_start.tz_convert("Asia/Taipei")
        water_end = weather_end.tz_convert("Asia/Taipei")

        time_source = "activity_gpx"

    else:
        activity_start_utc = pd.NaT
        activity_end_utc = pd.NaT

        weather_start = pd.to_datetime(MANUAL_WEATHER_START_TIME, utc=True)
        weather_end = pd.to_datetime(MANUAL_WEATHER_END_TIME, utc=True)

        water_start = pd.to_datetime(MANUAL_WATER_START_TIME)
        water_end = pd.to_datetime(MANUAL_WATER_END_TIME)

        time_source = "manual"

    return {
        "time_source": time_source,

        "activity_start_utc": activity_start_utc,
        "activity_end_utc": activity_end_utc,

        "weather_start_time": weather_start.isoformat(),
        "weather_end_time": weather_end.isoformat(),

        "water_start_time": water_start.isoformat(),
        "water_end_time": water_end.isoformat(),

        "pre_activity_hours": PRE_ACTIVITY_HOURS if USE_ACTIVITY_GPX_TIME else np.nan,
        "post_activity_hours": POST_ACTIVITY_HOURS if USE_ACTIVITY_GPX_TIME else np.nan,
    }


def load_selected_stations(csv_path: Path, preferred_ids, fallback_n=5):
    df = pd.read_csv(csv_path)
    if df.empty:
        raise ValueError(f"測站清單為空：{csv_path}")

    df["station_id"] = df["station_id"].astype(str)

    selected = df[df["station_id"].isin(preferred_ids)].copy()

    if selected.empty:
        selected = df.head(fallback_n).copy()
        print(f"警告：{csv_path.name} 找不到 preferred stations，改用距離最近前 {fallback_n} 站。")

    selected = selected.sort_values("dist_to_route_center_km").reset_index(drop=True)

    return selected


def query_window(conn, table_name, keep_cols, station_ids, start_time, end_time):
    if not station_ids:
        return pd.DataFrame(columns=keep_cols)

    placeholders = ",".join(["?"] * len(station_ids))
    col_sql = ", ".join(keep_cols)

    sql = f"""
    SELECT
        {col_sql}
    FROM {table_name}
    WHERE station_id IN ({placeholders})
      AND obs_time >= ?
      AND obs_time <= ?
    ORDER BY station_id, obs_time
    """

    params = station_ids + [start_time, end_time]
    return pd.read_sql_query(sql, conn, params=params)


def to_numeric_safe(df, cols):
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def haversine_km(lat1, lon1, lat2, lon2):
    """
    Calculate great-circle distance between two lat/lon points in kilometers.
    """
    r = 6371.0088

    lat1 = math.radians(float(lat1))
    lon1 = math.radians(float(lon1))
    lat2 = math.radians(float(lat2))
    lon2 = math.radians(float(lon2))

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return r * c


def classify_station_quadrant(route_lat, route_lon, station_lat, station_lon):
    """
    Classify station position relative to route center.
    """
    dlat = float(station_lat) - float(route_lat)
    dlon = float(station_lon) - float(route_lon)

    if dlat >= 0 and dlon >= 0:
        return "NE"
    if dlat >= 0 and dlon < 0:
        return "NW"
    if dlat < 0 and dlon >= 0:
        return "SE"
    return "SW"


def query_weather_station_candidates(
    conn,
    route_center_lat,
    route_center_lon,
    profile_start_utc,
    profile_end_utc,
):
    """
    Search all weather stations in weather_observations and rank them by distance
    to route center and data availability.
    """
    sql = """
    SELECT
        station_id,
        station_name,
        AVG(latitude) AS latitude,
        AVG(longitude) AS longitude,
        AVG(elevation_m) AS elevation_m,
        COUNT(*) AS obs_count,
        MIN(obs_time) AS first_obs_time,
        MAX(obs_time) AS last_obs_time
    FROM weather_observations
    WHERE obs_time >= ?
      AND obs_time <= ?
      AND latitude IS NOT NULL
      AND longitude IS NOT NULL
    GROUP BY station_id, station_name
    """

    df = pd.read_sql_query(
        sql,
        conn,
        params=[
            profile_start_utc.isoformat(),
            profile_end_utc.isoformat(),
        ],
    )

    if df.empty:
        return df

    df["station_id"] = df["station_id"].astype(str)

    df["dist_to_route_center_km"] = [
        haversine_km(
            route_center_lat,
            route_center_lon,
            r["latitude"],
            r["longitude"],
        )
        for _, r in df.iterrows()
    ]

    df["station_quadrant"] = [
        classify_station_quadrant(
            route_center_lat,
            route_center_lon,
            r["latitude"],
            r["longitude"],
        )
        for _, r in df.iterrows()
    ]

    df = df.sort_values(
        ["dist_to_route_center_km", "obs_count"],
        ascending=[True, False],
    ).reset_index(drop=True)

    return df


def select_weather_stations_dynamic(candidates_df, preferred_station_ids):
    """
    Select weather stations by:
    1. Keeping preferred stations
    2. Adding nearby stations within expanding radius
    3. Trying to cover missing quadrants
    4. Capping total station count
    """
    if candidates_df.empty:
        return candidates_df

    candidates = candidates_df.copy()
    candidates["station_id"] = candidates["station_id"].astype(str)

    selected_ids = []

    # 1. keep preferred stations first
    candidate_ids = set(candidates["station_id"])

    for sid in preferred_station_ids:
        sid = str(sid)
        if sid in candidate_ids and sid not in selected_ids:
            selected_ids.append(sid)

    # 2. radius expansion
    radius = WEATHER_STATION_SEARCH_RADIUS_KM_INITIAL

    while radius <= WEATHER_STATION_SEARCH_RADIUS_KM_MAX:
        within_radius = candidates[
            candidates["dist_to_route_center_km"] <= radius
        ].copy()

        for sid in within_radius["station_id"].tolist():
            sid = str(sid)

            if sid not in selected_ids:
                selected_ids.append(sid)

            if len(selected_ids) >= MIN_WEATHER_STATION_COUNT:
                break

        if len(selected_ids) >= MIN_WEATHER_STATION_COUNT:
            break

        radius += WEATHER_STATION_SEARCH_RADIUS_STEP_KM

    # 3. quadrant balance
    if ENABLE_WEATHER_QUADRANT_BALANCE:
        selected_df_tmp = candidates[
            candidates["station_id"].isin(selected_ids)
        ].copy()

        existing_quadrants = set(
            selected_df_tmp["station_quadrant"].dropna().astype(str)
        )

        for q in ["NE", "NW", "SE", "SW"]:
            if q in existing_quadrants:
                continue

            q_candidates = candidates[
                candidates["station_quadrant"] == q
            ].sort_values("dist_to_route_center_km")

            if not q_candidates.empty:
                sid = str(q_candidates.iloc[0]["station_id"])
                if sid not in selected_ids:
                    selected_ids.append(sid)

    # 4. cap max stations by distance
    selected = candidates[candidates["station_id"].isin(selected_ids)].copy()

    selected = selected.sort_values("dist_to_route_center_km").head(
        MAX_WEATHER_STATION_COUNT
    )

    return selected.reset_index(drop=True)


def build_weather_station_coverage_summary(selected_weather_stations):
    if selected_weather_stations.empty:
        return pd.DataFrame()

    coverage = (
        selected_weather_stations
        .groupby("station_quadrant")
        .agg(
            station_count=("station_id", "count"),
            nearest_station_km=("dist_to_route_center_km", "min"),
            farthest_station_km=("dist_to_route_center_km", "max"),
        )
        .reset_index()
    )

    all_quadrants = pd.DataFrame(
        {"station_quadrant": ["NE", "NW", "SE", "SW"]}
    )

    coverage = all_quadrants.merge(
        coverage,
        on="station_quadrant",
        how="left",
    )

    coverage["station_count"] = coverage["station_count"].fillna(0).astype(int)

    return coverage

def summarize_weather(df, selected_stations):
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["obs_time_dt"] = pd.to_datetime(df["obs_time"], errors="coerce", utc=True)

    numeric_cols = [
        "temperature_c",
        "relative_humidity_pct",
        "pressure_hpa",
        "wind_speed_ms",
        "wind_direction_deg",
        "wind_gust_ms",
        "precipitation_mm",
        "precipitation_10min_mm",
        "precipitation_1hr_mm",
        "sunshine_duration_min",
        "visibility_m",
        "uv_index",
    ]
    df = to_numeric_safe(df, numeric_cols)

    rows = []

    for station_id, g in df.groupby("station_id", dropna=False):
        g = g.sort_values("obs_time_dt")

        row = {
            "station_id": str(station_id),
            "station_name": g["station_name"].dropna().iloc[0] if g["station_name"].notna().any() else "",
            "n_obs": len(g),
            "first_obs_time": g["obs_time"].min(),
            "last_obs_time": g["obs_time"].max(),

            "temperature_mean_c": g["temperature_c"].mean(),
            "temperature_min_c": g["temperature_c"].min(),
            "temperature_max_c": g["temperature_c"].max(),

            "humidity_mean_pct": g["relative_humidity_pct"].mean(),
            "humidity_min_pct": g["relative_humidity_pct"].min(),
            "humidity_max_pct": g["relative_humidity_pct"].max(),

            "pressure_mean_hpa": g["pressure_hpa"].mean(),

            "wind_speed_mean_ms": g["wind_speed_ms"].mean(),
            "wind_speed_max_ms": g["wind_speed_ms"].max(),
            "wind_gust_max_ms": g["wind_gust_ms"].max(),

            "precipitation_sum_mm": g["precipitation_mm"].sum(min_count=1),
            "precipitation_max_mm": g["precipitation_mm"].max(),
            "precipitation_10min_max_mm": g["precipitation_10min_mm"].max(),
            "precipitation_1hr_max_mm": g["precipitation_1hr_mm"].max(),

            "visibility_min_m": g["visibility_m"].min(),
            "visibility_mean_m": g["visibility_m"].mean(),

            "uv_index_max": g["uv_index"].max(),

            "weather_available": 1,
            "fallback_used": 0,
            "fallback_reason": "",
        }

        rows.append(row)

    summary = pd.DataFrame(rows)

    selected = selected_stations.copy()
    selected["station_id"] = selected["station_id"].astype(str)

    keep = [
        "station_id",
        "dist_to_route_center_km",
        "station_quadrant",
        "latitude",
        "longitude",
        "county_name",
        "town_name",
    ]
    keep = [c for c in keep if c in selected.columns]

    summary = summary.merge(
        selected[keep],
        on="station_id",
        how="left",
    )

    summary = summary.sort_values("dist_to_route_center_km").reset_index(drop=True)
    return summary


def summarize_water(df, selected_stations):
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["obs_time_dt"] = pd.to_datetime(df["obs_time"], errors="coerce")

    numeric_cols = [
        "water_level_m",
        "voltage",
    ]
    df = to_numeric_safe(df, numeric_cols)

    rows = []

    for station_id, g in df.groupby("station_id", dropna=False):
        g = g.sort_values("obs_time_dt")

        first_level = g["water_level_m"].dropna().iloc[0] if g["water_level_m"].notna().any() else None
        last_level = g["water_level_m"].dropna().iloc[-1] if g["water_level_m"].notna().any() else None

        if first_level is not None and last_level is not None:
            water_level_change_m = last_level - first_level
        else:
            water_level_change_m = None

        row = {
            "station_id": str(station_id),
            "station_name": g["station_name"].dropna().iloc[0] if g["station_name"].notna().any() else "",
            "river_name": g["river_name"].dropna().iloc[0] if g["river_name"].notna().any() else "",

            "n_obs": len(g),
            "first_obs_time": g["obs_time"].min(),
            "last_obs_time": g["obs_time"].max(),

            "water_level_mean_m": g["water_level_m"].mean(),
            "water_level_min_m": g["water_level_m"].min(),
            "water_level_max_m": g["water_level_m"].max(),
            "water_level_range_m": g["water_level_m"].max() - g["water_level_m"].min(),
            "water_level_first_m": first_level,
            "water_level_last_m": last_level,
            "water_level_change_m": water_level_change_m,

            "valid_check_result_ratio": (
                (g["check_result"].astype(str) == "1").mean()
                if "check_result" in g.columns
                else None
            ),

            "hydro_available": 1,
            "fallback_used": 0,
            "fallback_reason": "",
        }

        rows.append(row)

    summary = pd.DataFrame(rows)

    selected = selected_stations.copy()
    selected["station_id"] = selected["station_id"].astype(str)

    keep = [
        "station_id",
        "dist_to_route_center_km",
        "latitude",
        "longitude",
        "county_name",
        "town_name",
    ]
    keep = [c for c in keep if c in selected.columns]

    summary = summary.merge(
        selected[keep],
        on="station_id",
        how="left",
    )

    summary = summary.sort_values("dist_to_route_center_km").reset_index(drop=True)
    return summary


def build_fallback_weather_summary():
    return pd.DataFrame([FALLBACK_WEATHER_ROW.copy()])


def build_fallback_water_summary():
    return pd.DataFrame([FALLBACK_WATER_ROW.copy()])


def build_environment_metadata(
    time_info,
    weather_df,
    water_df,
    weather_summary,
    water_summary,
):
    weather_obs_count = len(weather_df)
    water_obs_count = len(water_df)

    weather_available = 1 if weather_obs_count > 0 else 0
    hydro_available = 1 if water_obs_count > 0 else 0

    if weather_available and hydro_available:
        environment_data_mode = "observed"
        environment_data_warning = ""
        fallback_used = 0
        fallback_reason = ""

    elif weather_available or hydro_available:
        environment_data_mode = "partial"
        missing = []
        if not weather_available:
            missing.append("weather_missing")
        if not hydro_available:
            missing.append("hydro_missing")
        environment_data_warning = ",".join(missing)
        fallback_used = 1 if ENABLE_FALLBACK_NORMAL else 0
        fallback_reason = "partial_environment_data"

    else:
        environment_data_mode = "fallback_normal"
        environment_data_warning = "weather_and_hydro_missing"
        fallback_used = 1 if ENABLE_FALLBACK_NORMAL else 0
        fallback_reason = "no_environment_data_in_activity_window"

    row = {
        "time_source": time_info["time_source"],
        "activity_gpx": str(ACTIVITY_GPX) if USE_ACTIVITY_GPX_TIME else "",
        "activity_start_utc": time_info["activity_start_utc"],
        "activity_end_utc": time_info["activity_end_utc"],

        "weather_start_time": time_info["weather_start_time"],
        "weather_end_time": time_info["weather_end_time"],

        "water_start_time": time_info["water_start_time"],
        "water_end_time": time_info["water_end_time"],

        "pre_activity_hours": time_info["pre_activity_hours"],
        "post_activity_hours": time_info["post_activity_hours"],

        "weather_observation_count": weather_obs_count,
        "hydro_observation_count": water_obs_count,

        "weather_available": weather_available,
        "hydro_available": hydro_available,

        "environment_data_mode": environment_data_mode,
        "environment_data_warning": environment_data_warning,

        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,

        "weather_summary_rows": len(weather_summary),
        "water_summary_rows": len(water_summary),
    }

    return pd.DataFrame([row])


# =========================================================
# G. Main
# =========================================================
def main():
    ensure_exists(DB_PATH)
    ensure_exists(IN_WEATHER_STATIONS_CSV)
    ensure_exists(IN_WATER_STATIONS_CSV)

    if USE_ACTIVITY_GPX_TIME:
        ensure_exists(ACTIVITY_GPX)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    time_info = build_time_windows()

    print("\n=== environment time window ===")
    print("time source:", time_info["time_source"])
    print("activity start UTC:", time_info["activity_start_utc"])
    print("activity end UTC:", time_info["activity_end_utc"])
    print("weather window:", time_info["weather_start_time"], "→", time_info["weather_end_time"])
    print("water window:", time_info["water_start_time"], "→", time_info["water_end_time"])

    # -----------------------------------------------------
    # Weather station selection
    # -----------------------------------------------------
    if ENABLE_DYNAMIC_WEATHER_STATION_SEARCH:
        # 先用 nearby weather stations CSV 估路線中心。
        # 該 CSV 通常已由前一階段依 GPX 路線中心計算距離，
        # 這裡用最近站座標近似取得 route center 不夠精準；
        # 更佳做法是直接由 GPX 幾何計算 route center。
        # 因此這裡改用 weather station CSV 內的 nearest station list
        # 作為 dynamic candidate 搜尋前的輔助來源。
        
        # 下面的csv後面沒用到
        # nearby_weather_for_center = pd.read_csv(IN_WEATHER_STATIONS_CSV)

        # 用 ACTIVITY_GPX 直接算 route center，較穩。
        route_points = read_gpx_points_for_center(ACTIVITY_GPX)
        route_center_lat = route_points["lat"].mean()
        route_center_lon = route_points["lon"].mean()

        conn_tmp = sqlite3.connect(DB_PATH)
        try:
            weather_candidates = query_weather_station_candidates(
                conn=conn_tmp,
                route_center_lat=route_center_lat,
                route_center_lon=route_center_lon,
                profile_start_utc=pd.to_datetime(time_info["weather_start_time"], utc=True),
                profile_end_utc=pd.to_datetime(time_info["weather_end_time"], utc=True),
            )
        finally:
            conn_tmp.close()

        weather_candidates.to_csv(
            OUT_WEATHER_STATION_CANDIDATES_CSV,
            index=False,
            encoding="utf-8-sig",
        )

        weather_selected = select_weather_stations_dynamic(
            weather_candidates,
            PREFERRED_WEATHER_STATIONS,
        )

        coverage_summary = build_weather_station_coverage_summary(
            weather_selected
        )

        coverage_summary.to_csv(
            OUT_WEATHER_STATION_COVERAGE_CSV,
            index=False,
            encoding="utf-8-sig",
        )

    else:
        weather_selected = load_selected_stations(
            IN_WEATHER_STATIONS_CSV,
            PREFERRED_WEATHER_STATIONS,
            fallback_n=5,
        )

        coverage_summary = pd.DataFrame()

    water_selected = load_selected_stations(
        IN_WATER_STATIONS_CSV,
        PREFERRED_WATER_STATIONS,
        fallback_n=5,
    )

    weather_station_ids = weather_selected["station_id"].astype(str).tolist()
    water_station_ids = water_selected["station_id"].astype(str).tolist()

    print("\n=== selected weather stations ===")
    weather_show_cols = [
        "station_id",
        "station_name",
        "station_quadrant",
        "dist_to_route_center_km",
        "obs_count",
        "first_obs_time",
        "last_obs_time",
    ]
    weather_show_cols = [c for c in weather_show_cols if c in weather_selected.columns]
    print(weather_selected[weather_show_cols].to_string(index=False))

    if ENABLE_DYNAMIC_WEATHER_STATION_SEARCH:
        print("\n=== weather station candidates output ===")
        print("candidates CSV:", OUT_WEATHER_STATION_CANDIDATES_CSV.resolve())
        print("coverage CSV:", OUT_WEATHER_STATION_COVERAGE_CSV.resolve())

        print("\n=== weather station quadrant coverage ===")
        if coverage_summary.empty:
            print("(empty)")
        else:
            print(coverage_summary.to_string(index=False))

    print("\n=== selected water stations ===")
    print(
        water_selected[
            [
                "station_id",
                "station_name",
                "river_name",
                "dist_to_route_center_km",
                "obs_count",
                "first_obs_time",
                "last_obs_time",
            ]
        ].to_string(index=False)
    )

    conn = sqlite3.connect(DB_PATH)

    try:
        weather_df = query_window(
            conn=conn,
            table_name="weather_observations",
            keep_cols=WEATHER_COLS,
            station_ids=weather_station_ids,
            start_time=time_info["weather_start_time"],
            end_time=time_info["weather_end_time"],
        )

        water_df = query_window(
            conn=conn,
            table_name="water_level_observations",
            keep_cols=WATER_COLS,
            station_ids=water_station_ids,
            start_time=time_info["water_start_time"],
            end_time=time_info["water_end_time"],
        )

    finally:
        conn.close()

    # -----------------------------------------------------
    # Weather output
    # -----------------------------------------------------
    if weather_df.empty:
        print("\n警告：指定活動時間窗內查無氣象資料")
        pd.DataFrame(columns=WEATHER_COLS).to_csv(
            OUT_WEATHER_WINDOW_CSV,
            index=False,
            encoding="utf-8-sig",
        )

        if ENABLE_FALLBACK_NORMAL:
            weather_summary = build_fallback_weather_summary()
        else:
            weather_summary = pd.DataFrame()
    else:
        weather_df["obs_time_dt"] = pd.to_datetime(
            weather_df["obs_time"],
            errors="coerce",
            utc=True,
        )
        weather_df = weather_df.sort_values(["station_id", "obs_time_dt"]).reset_index(drop=True)
        weather_df.to_csv(OUT_WEATHER_WINDOW_CSV, index=False, encoding="utf-8-sig")
        weather_summary = summarize_weather(weather_df, weather_selected)

    weather_summary.to_csv(OUT_WEATHER_SUMMARY_CSV, index=False, encoding="utf-8-sig")

    # -----------------------------------------------------
    # Water output
    # -----------------------------------------------------
    if water_df.empty:
        print("\n警告：指定活動時間窗內查無水位資料")
        pd.DataFrame(columns=WATER_COLS).to_csv(
            OUT_WATER_WINDOW_CSV,
            index=False,
            encoding="utf-8-sig",
        )

        if ENABLE_FALLBACK_NORMAL:
            water_summary = build_fallback_water_summary()
        else:
            water_summary = pd.DataFrame()
    else:
        water_df["obs_time_dt"] = pd.to_datetime(
            water_df["obs_time"],
            errors="coerce",
        )
        water_df = water_df.sort_values(["station_id", "obs_time_dt"]).reset_index(drop=True)
        water_df.to_csv(OUT_WATER_WINDOW_CSV, index=False, encoding="utf-8-sig")
        water_summary = summarize_water(water_df, water_selected)

    water_summary.to_csv(OUT_WATER_SUMMARY_CSV, index=False, encoding="utf-8-sig")

    # -----------------------------------------------------
    # Metadata output
    # -----------------------------------------------------
    metadata_df = build_environment_metadata(
        time_info=time_info,
        weather_df=weather_df,
        water_df=water_df,
        weather_summary=weather_summary,
        water_summary=water_summary,
    )

    metadata_df.to_csv(OUT_ENV_METADATA_CSV, index=False, encoding="utf-8-sig")

    # -----------------------------------------------------
    # Console summary
    # -----------------------------------------------------
    print("\n完成！")
    print("weather window CSV:", OUT_WEATHER_WINDOW_CSV.resolve())
    print("weather summary CSV:", OUT_WEATHER_SUMMARY_CSV.resolve())
    print("water window CSV:", OUT_WATER_WINDOW_CSV.resolve())
    print("water summary CSV:", OUT_WATER_SUMMARY_CSV.resolve())
    print("environment metadata CSV:", OUT_ENV_METADATA_CSV.resolve())

    print("\n=== environment metadata ===")
    print(metadata_df.T.to_string(header=False))

    print("\n=== weather summary by station ===")
    if weather_summary.empty:
        print("(empty)")
    else:
        cols = [
            "station_id",
            "station_name",
            "station_quadrant",
            "dist_to_route_center_km",
            "n_obs",
            "weather_available",
            "fallback_used",
            "fallback_reason",
            "temperature_mean_c",
            "humidity_mean_pct",
            "wind_speed_mean_ms",
            "wind_speed_max_ms",
            "wind_gust_max_ms",
            "precipitation_sum_mm",
            "precipitation_1hr_max_mm",
            "visibility_min_m",
        ]
        cols = [c for c in cols if c in weather_summary.columns]
        print(weather_summary[cols].to_string(index=False))

    print("\n=== water summary by station ===")
    if water_summary.empty:
        print("(empty)")
    else:
        cols = [
            "station_id",
            "station_name",
            "river_name",
            "dist_to_route_center_km",
            "n_obs",
            "hydro_available",
            "fallback_used",
            "fallback_reason",
            "water_level_mean_m",
            "water_level_min_m",
            "water_level_max_m",
            "water_level_range_m",
            "water_level_change_m",
            "valid_check_result_ratio",
        ]
        cols = [c for c in cols if c in water_summary.columns]
        print(water_summary[cols].to_string(index=False))


if __name__ == "__main__":
    main()