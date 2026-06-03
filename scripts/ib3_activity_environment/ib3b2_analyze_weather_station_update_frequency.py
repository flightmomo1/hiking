# -*- coding: utf-8 -*-
from pathlib import Path
import sqlite3
import os
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd


# =========================================================
# A. Input / Output
# =========================================================
DB_PATH = Path(
    "/Users/iddmini/Documents/115_Motion改造/FY115_登山/weather/"
    "tw_weather_2026-05-01.sqlite3"
)

ACTIVITY_GPX = Path(
    "/Users/iddmini/Documents/115_Motion改造/FY115_登山/gpx/"
    "冷水坑上-七星山東峰-主峰-下小油坑.gpx"
)

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent

SCENARIO_NAME = os.environ.get("SCENARIO_NAME", "actual_gpx_9stations")

ENV_BASE_DIR = BASE_DIR / "ib3_environment_output"
SCENARIO_ENV_DIR = ENV_BASE_DIR / SCENARIO_NAME

# 測站清單仍可用共用檔案，因為 nearby stations 是路線固定資料
IN_WEATHER_STATIONS_CSV = ENV_BASE_DIR / "qixing_nearby_weather_stations.csv"

# metadata 要讀情境資料夾，才能分辨 actual / 4/30 manual window
IN_ENV_METADATA_CSV = SCENARIO_ENV_DIR / "qixing_environment_window_metadata.csv"

OUT_DIR = SCENARIO_ENV_DIR

OUT_UPDATE_PROFILE_CSV = OUT_DIR / "qixing_weather_station_update_profile.csv"
OUT_TREND_FEATURES_CSV = OUT_DIR / "qixing_weather_trend_features.csv"
OUT_QUALITY_SUMMARY_CSV = OUT_DIR / "qixing_weather_data_quality_summary.csv"

# =========================================================
# B. Analysis parameters
# =========================================================
PREFERRED_WEATHER_STATIONS = [
    "466930",  # 陽明山
    "466910",  # 鞍部
    "C0AC40",  # 大屯山
    "A0A460",  # 文化大學
    "C0AH40",  # 平等
]

# 趨勢分析時間窗
TRAIL_WETNESS_PRE_HOURS = 12       # 活動前 12 小時，用於判斷路面濕滑背景
RAIN_LAG_POST_HOURS = 2            # 活動後 2 小時，用於判斷雨量延遲反映
PROFILE_LOOKBACK_DAYS = 14         # 更新頻率用活動前 14 天到活動後 2 小時估計

# 資料品質門檻
LONG_GAP_MULTIPLIER = 2.5
MIN_OBS_FOR_UPDATE_PROFILE = 5

# 濕度 / 風速 / 降雨判斷門檻
HUMIDITY_HIGH_PCT = 90.0
HUMIDITY_VERY_HIGH_PCT = 95.0
RAIN_OBS_THRESHOLD_MM = 0.1
WINDY_THRESHOLD_MS = 6.0

# 氣壓趨勢判斷門檻
# 注意：不跨測站比較絕對氣壓，只看同一測站於活動窗內的變化。
PRESSURE_DROP_HPA_THRESHOLD = 1.5
PRESSURE_DROP_RATE_HPA_PER_HR_THRESHOLD = 0.8

# 風向資料判斷門檻
MIN_WIND_DIRECTION_VALID_COUNT = 3


# =========================================================
# C. SQLite columns
# =========================================================
WEATHER_QUERY_COLS = [
    "station_id",
    "station_name",
    "obs_time",
    "latitude",
    "longitude",
    "county_name",
    "town_name",
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
    "visibility_m",
    "uv_index",
    "qc_flag",
]


# =========================================================
# D. Utility
# =========================================================
def ensure_exists(fp: Path):
    if not fp.exists():
        raise FileNotFoundError(f"找不到檔案：{fp.resolve()}")


def strip_namespace(tag):
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def parse_gpx_time_range(gpx_path: Path):
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

    return min(times), max(times)


def load_activity_time_window():
    """
    優先讀 ib3b 產生的 metadata。

    支援兩種模式：
    1. 真實活動模式：
       metadata 有 activity_start_utc / activity_end_utc
       → 使用 GPX 活動時間

    2. 情境模式：
       metadata 沒有有效 activity_start_utc / activity_end_utc
       但有 weather_start_time / weather_end_time
       → 使用 weather window 作為情境分析時間窗

    3. fallback：
       metadata 不存在或時間不可用
       → 直接從 GPX 讀取活動時間
    """
    if IN_ENV_METADATA_CSV.exists():
        meta = pd.read_csv(IN_ENV_METADATA_CSV)

        if not meta.empty:
            row = meta.iloc[0]

            # -------------------------------------------------
            # 1. 優先使用真實活動時間
            # -------------------------------------------------
            activity_start = pd.to_datetime(
                row.get("activity_start_utc"),
                errors="coerce",
                utc=True,
            )
            activity_end = pd.to_datetime(
                row.get("activity_end_utc"),
                errors="coerce",
                utc=True,
            )

            if pd.notna(activity_start) and pd.notna(activity_end):
                return activity_start, activity_end, "environment_metadata_activity_time"

            # -------------------------------------------------
            # 2. 若沒有活動時間，改用 weather window 作為情境時間窗
            #    這是給 ib3x bad_weather_0430 情境使用
            # -------------------------------------------------
            weather_start = pd.to_datetime(
                row.get("weather_start_time"),
                errors="coerce",
                utc=True,
            )
            weather_end = pd.to_datetime(
                row.get("weather_end_time"),
                errors="coerce",
                utc=True,
            )

            if pd.notna(weather_start) and pd.notna(weather_end):
                return weather_start, weather_end, "environment_metadata_weather_window"

    # ---------------------------------------------------------
    # 3. metadata 不可用時，回頭讀 GPX
    # ---------------------------------------------------------
    activity_start, activity_end = parse_gpx_time_range(ACTIVITY_GPX)
    return activity_start, activity_end, "activity_gpx"


def load_selected_weather_stations():
    ensure_exists(IN_WEATHER_STATIONS_CSV)

    df = pd.read_csv(IN_WEATHER_STATIONS_CSV)

    if df.empty:
        raise ValueError(f"測站清單為空：{IN_WEATHER_STATIONS_CSV}")

    df["station_id"] = df["station_id"].astype(str)

    selected = df[df["station_id"].isin(PREFERRED_WEATHER_STATIONS)].copy()

    if selected.empty:
        selected = df.head(5).copy()
        print("警告：找不到 preferred stations，改用距離最近前 5 站。")

    selected = selected.sort_values("dist_to_route_center_km").reset_index(drop=True)

    return selected


def to_numeric_safe(df, cols):
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def query_weather_observations(conn, station_ids, start_time, end_time):
    if not station_ids:
        return pd.DataFrame(columns=WEATHER_QUERY_COLS)

    placeholders = ",".join(["?"] * len(station_ids))
    col_sql = ", ".join(WEATHER_QUERY_COLS)

    sql = f"""
    SELECT
        {col_sql}
    FROM weather_observations
    WHERE station_id IN ({placeholders})
      AND obs_time >= ?
      AND obs_time <= ?
    ORDER BY station_id, obs_time
    """

    params = station_ids + [start_time, end_time]
    return pd.read_sql_query(sql, conn, params=params)


def classify_update_frequency(median_gap_min, obs_count):
    if pd.isna(median_gap_min) or obs_count < MIN_OBS_FOR_UPDATE_PROFILE:
        return "insufficient_data"

    if median_gap_min <= 12:
        return "10min"
    if median_gap_min <= 20:
        return "15min"
    if median_gap_min <= 35:
        return "30min"
    if median_gap_min <= 75:
        return "hourly"

    return "irregular_or_sparse"


def pct_duration_condition(df, condition_col):
    """
    用相鄰觀測時間差估計某條件維持的時間比例。
    若時間差不可用，退化成 point ratio。
    """
    if df.empty or condition_col not in df.columns:
        return np.nan

    g = df.sort_values("obs_time_dt").copy()

    if len(g) < 2:
        return float(g[condition_col].mean())

    g["next_time"] = g["obs_time_dt"].shift(-1)
    g["duration_to_next_min"] = (
        g["next_time"] - g["obs_time_dt"]
    ).dt.total_seconds() / 60.0

    valid = g["duration_to_next_min"].notna() & (g["duration_to_next_min"] > 0)

    if valid.sum() == 0:
        return float(g[condition_col].mean())

    total_min = g.loc[valid, "duration_to_next_min"].sum()

    if total_min <= 0:
        return float(g[condition_col].mean())

    cond_min = g.loc[valid & g[condition_col], "duration_to_next_min"].sum()
    return float(cond_min / total_min)


def safe_first_valid(series):
    s = series.dropna()
    if s.empty:
        return np.nan
    return s.iloc[0]


def safe_last_valid(series):
    s = series.dropna()
    if s.empty:
        return np.nan
    return s.iloc[-1]

def normalize_degree_0_360(deg):
    if pd.isna(deg):
        return np.nan
    return float(deg) % 360.0


def circular_mean_degree(series):
    """
    計算風向角度的向量平均。

    注意：
    不能直接用算術平均，因為 350° 和 10° 的平均不應該是 180°。
    """
    s = pd.to_numeric(series, errors="coerce").dropna()

    # 只保留合理角度
    s = s[(s >= 0) & (s <= 360)]

    if s.empty:
        return np.nan

    radians = np.deg2rad(s % 360.0)

    sin_mean = np.sin(radians).mean()
    cos_mean = np.cos(radians).mean()

    if np.isclose(sin_mean, 0.0) and np.isclose(cos_mean, 0.0):
        return np.nan

    mean_rad = np.arctan2(sin_mean, cos_mean)
    mean_deg = np.rad2deg(mean_rad) % 360.0

    return float(mean_deg)


def classify_wind_direction_data_status(valid_count):
    if pd.isna(valid_count) or int(valid_count) <= 0:
        return "no_wind_direction_data"

    if int(valid_count) < MIN_WIND_DIRECTION_VALID_COUNT:
        return "insufficient_wind_direction_data"

    return "valid"



# =========================================================
# E. Update frequency analysis
# =========================================================
def build_update_profile(df, selected_stations, profile_start, profile_end):
    if df.empty:
        return pd.DataFrame()

    gdf = df.copy()

    gdf["obs_time_dt"] = pd.to_datetime(
        gdf["obs_time"],
        errors="coerce",
        utc=True,
    )

    gdf = gdf[gdf["obs_time_dt"].notna()].copy()
    gdf = gdf.sort_values(["station_id", "obs_time_dt"]).reset_index(drop=True)

    rows = []

    profile_span_min = (
        profile_end - profile_start
    ).total_seconds() / 60.0

    for station_id, g in gdf.groupby("station_id", dropna=False):
        g = g.sort_values("obs_time_dt").copy()

        gaps_min = g["obs_time_dt"].diff().dt.total_seconds() / 60.0
        gaps_valid = gaps_min.dropna()
        gaps_valid = gaps_valid[gaps_valid > 0]

        obs_count = len(g)

        median_gap = gaps_valid.median() if not gaps_valid.empty else np.nan
        mean_gap = gaps_valid.mean() if not gaps_valid.empty else np.nan
        min_gap = gaps_valid.min() if not gaps_valid.empty else np.nan
        max_gap = gaps_valid.max() if not gaps_valid.empty else np.nan
        p90_gap = gaps_valid.quantile(0.90) if not gaps_valid.empty else np.nan

        if pd.notna(median_gap) and median_gap > 0:
            expected_obs = int(np.floor(profile_span_min / median_gap)) + 1
            data_completeness_ratio = obs_count / expected_obs if expected_obs > 0 else np.nan
            long_gap_threshold = max(median_gap * LONG_GAP_MULTIPLIER, median_gap + 10)
            long_gap_count = int((gaps_valid > long_gap_threshold).sum())
        else:
            expected_obs = np.nan
            data_completeness_ratio = np.nan
            long_gap_threshold = np.nan
            long_gap_count = np.nan

        station_name = (
            g["station_name"].dropna().iloc[0]
            if "station_name" in g.columns and g["station_name"].notna().any()
            else ""
        )

        rows.append(
            {
                "station_id": str(station_id),
                "station_name": station_name,
                "obs_count": obs_count,
                "profile_start_time": profile_start.isoformat(),
                "profile_end_time": profile_end.isoformat(),
                "first_obs_time": g["obs_time"].min(),
                "last_obs_time": g["obs_time"].max(),

                "median_update_interval_min": median_gap,
                "mean_update_interval_min": mean_gap,
                "min_update_interval_min": min_gap,
                "max_update_interval_min": max_gap,
                "p90_update_interval_min": p90_gap,

                "expected_obs_count": expected_obs,
                "data_completeness_ratio": data_completeness_ratio,
                "long_gap_threshold_min": long_gap_threshold,
                "long_gap_count": long_gap_count,

                "likely_update_frequency_class": classify_update_frequency(
                    median_gap,
                    obs_count,
                ),
            }
        )

    out = pd.DataFrame(rows)

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

    out = out.merge(selected[keep], on="station_id", how="left")
    out = out.sort_values("dist_to_route_center_km").reset_index(drop=True)

    return out


# =========================================================
# F. Trend feature analysis
# =========================================================
def summarize_station_trend(
    station_id,
    station_df,
    selected_stations,
    activity_start,
    activity_end,
    wetness_start,
    lag_end,
):
    g = station_df.copy()

    g["obs_time_dt"] = pd.to_datetime(
        g["obs_time"],
        errors="coerce",
        utc=True,
    )
    g = g[g["obs_time_dt"].notna()].copy()
    g = g.sort_values("obs_time_dt").reset_index(drop=True)

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
        "visibility_m",
        "uv_index",
    ]
    g = to_numeric_safe(g, numeric_cols)

    activity_mask = (
        (g["obs_time_dt"] >= activity_start)
        & (g["obs_time_dt"] <= activity_end)
    )

    pre_wetness_mask = (
        (g["obs_time_dt"] >= wetness_start)
        & (g["obs_time_dt"] < activity_start)
    )

    post_lag_mask = (
        (g["obs_time_dt"] > activity_end)
        & (g["obs_time_dt"] <= lag_end)
    )

    activity_g = g[activity_mask].copy()
    pre_g = g[pre_wetness_mask].copy()
    post_g = g[post_lag_mask].copy()

    # rain fields
    rain_cols = [
        c for c in [
            "precipitation_mm",
            "precipitation_10min_mm",
            "precipitation_1hr_mm",
        ]
        if c in g.columns
    ]

    def rain_sum(df_part):
        if df_part.empty:
            return 0.0
        vals = []
        for c in rain_cols:
            s = pd.to_numeric(df_part[c], errors="coerce")
            if c == "precipitation_mm":
                vals.append(s.sum(min_count=1))
        if not vals:
            return np.nan
        return float(np.nanmax(vals))

    def rain_max(df_part):
        if df_part.empty:
            return 0.0
        max_vals = []
        for c in rain_cols:
            s = pd.to_numeric(df_part[c], errors="coerce")
            if s.notna().any():
                max_vals.append(s.max())
        if not max_vals:
            return np.nan
        return float(np.nanmax(max_vals))

    activity_rain_sum = rain_sum(activity_g)
    pre_rain_sum = rain_sum(pre_g)
    post_rain_sum = rain_sum(post_g)
    full_rain_sum = rain_sum(g)

    activity_rain_max = rain_max(activity_g)
    pre_rain_max = rain_max(pre_g)
    post_rain_max = rain_max(post_g)

    rain_observed_activity = (
        pd.notna(activity_rain_sum)
        and activity_rain_sum >= RAIN_OBS_THRESHOLD_MM
    )

    rain_observed_pre = (
        pd.notna(pre_rain_sum)
        and pre_rain_sum >= RAIN_OBS_THRESHOLD_MM
    )

    rain_observed_post = (
        pd.notna(post_rain_sum)
        and post_rain_sum >= RAIN_OBS_THRESHOLD_MM
    )

    # humidity
    humidity_activity = (
        activity_g["relative_humidity_pct"]
        if "relative_humidity_pct" in activity_g.columns
        else pd.Series(dtype=float)
    )

    humidity_mean = humidity_activity.mean() if not humidity_activity.empty else np.nan
    humidity_max = humidity_activity.max() if not humidity_activity.empty else np.nan
    humidity_first = safe_first_valid(humidity_activity)
    humidity_last = safe_last_valid(humidity_activity)
    humidity_delta = (
        humidity_last - humidity_first
        if pd.notna(humidity_first) and pd.notna(humidity_last)
        else np.nan
    )

    activity_g["humidity_above_90"] = (
        activity_g["relative_humidity_pct"] >= HUMIDITY_HIGH_PCT
        if "relative_humidity_pct" in activity_g.columns
        else False
    )
    activity_g["humidity_above_95"] = (
        activity_g["relative_humidity_pct"] >= HUMIDITY_VERY_HIGH_PCT
        if "relative_humidity_pct" in activity_g.columns
        else False
    )

    humidity_above_90_ratio = pct_duration_condition(activity_g, "humidity_above_90")
    humidity_above_95_ratio = pct_duration_condition(activity_g, "humidity_above_95")

    # temperature
    temp_activity = (
        activity_g["temperature_c"]
        if "temperature_c" in activity_g.columns
        else pd.Series(dtype=float)
    )

    temp_mean = temp_activity.mean() if not temp_activity.empty else np.nan
    temp_min = temp_activity.min() if not temp_activity.empty else np.nan
    temp_max = temp_activity.max() if not temp_activity.empty else np.nan
    temp_first = safe_first_valid(temp_activity)
    temp_last = safe_last_valid(temp_activity)
    temp_delta = (
        temp_last - temp_first
        if pd.notna(temp_first) and pd.notna(temp_last)
        else np.nan
    )

    # wind
    wind_activity = (
        activity_g["wind_speed_ms"]
        if "wind_speed_ms" in activity_g.columns
        else pd.Series(dtype=float)
    )

    wind_mean = wind_activity.mean() if not wind_activity.empty else np.nan
    wind_max = wind_activity.max() if not wind_activity.empty else np.nan
    wind_first = safe_first_valid(wind_activity)
    wind_last = safe_last_valid(wind_activity)
    wind_delta = (
        wind_last - wind_first
        if pd.notna(wind_first) and pd.notna(wind_last)
        else np.nan
    )

    wind_gust_max = (
        activity_g["wind_gust_ms"].max()
        if "wind_gust_ms" in activity_g.columns
        else np.nan
    )

    # wind direction
    wind_direction_activity = (
        activity_g["wind_direction_deg"]
        if "wind_direction_deg" in activity_g.columns
        else pd.Series(dtype=float)
    )

    wind_direction_valid = pd.to_numeric(
        wind_direction_activity,
        errors="coerce",
    ).dropna()

    wind_direction_valid = wind_direction_valid[
        (wind_direction_valid >= 0)
        & (wind_direction_valid <= 360)
    ]

    wind_direction_valid_count = int(len(wind_direction_valid))

    wind_direction_vector_mean = circular_mean_degree(wind_direction_valid)

    wind_direction_arithmetic_mean = (
        float(wind_direction_valid.mean())
        if wind_direction_valid_count > 0
        else np.nan
    )

    wind_direction_data_status = classify_wind_direction_data_status(
        wind_direction_valid_count
    )


    # pressure
    pressure_activity = (
        activity_g["pressure_hpa"]
        if "pressure_hpa" in activity_g.columns
        else pd.Series(dtype=float)
    )

    pressure_mean = pressure_activity.mean() if not pressure_activity.empty else np.nan
    pressure_min = pressure_activity.min() if not pressure_activity.empty else np.nan
    pressure_max = pressure_activity.max() if not pressure_activity.empty else np.nan
    pressure_first = safe_first_valid(pressure_activity)
    pressure_last = safe_last_valid(pressure_activity)

    pressure_delta = (
        pressure_last - pressure_first
        if pd.notna(pressure_first) and pd.notna(pressure_last)
        else np.nan
    )

    pressure_drop = (
        max(0.0, pressure_first - pressure_last)
        if pd.notna(pressure_first) and pd.notna(pressure_last)
        else np.nan
    )

    activity_duration_hr = (
        (activity_end - activity_start).total_seconds() / 3600.0
        if pd.notna(activity_start) and pd.notna(activity_end)
        else np.nan
    )

    pressure_drop_rate = (
        pressure_drop / activity_duration_hr
        if pd.notna(pressure_drop)
        and pd.notna(activity_duration_hr)
        and activity_duration_hr > 0
        else np.nan
    )

    pressure_drop_flag = int(
        pd.notna(pressure_drop)
        and pressure_drop >= PRESSURE_DROP_HPA_THRESHOLD
    )

    pressure_drop_rate_flag = int(
        pd.notna(pressure_drop_rate)
        and pressure_drop_rate >= PRESSURE_DROP_RATE_HPA_PER_HR_THRESHOLD
    )
    
    # update gap within analysis window
    gaps_min = g["obs_time_dt"].diff().dt.total_seconds() / 60.0
    gaps_valid = gaps_min.dropna()
    gaps_valid = gaps_valid[gaps_valid > 0]
    median_gap = gaps_valid.median() if not gaps_valid.empty else np.nan
    max_gap = gaps_valid.max() if not gaps_valid.empty else np.nan

    # status / hint
    weather_trend_hint = infer_weather_trend_hint(
        activity_rain_sum=activity_rain_sum,
        pre_rain_sum=pre_rain_sum,
        post_rain_sum=post_rain_sum,
        humidity_mean=humidity_mean,
        humidity_max=humidity_max,
        humidity_above_95_ratio=humidity_above_95_ratio,
        wind_max=wind_max,
        median_gap=median_gap,
        activity_obs_count=len(activity_g),
        pressure_drop_hpa=pressure_drop,
        pressure_drop_rate_hpa_per_hr=pressure_drop_rate,
    )


    rain_data_status = infer_rain_data_status(
        activity_rain_sum=activity_rain_sum,
        pre_rain_sum=pre_rain_sum,
        post_rain_sum=post_rain_sum,
        humidity_mean=humidity_mean,
        humidity_above_95_ratio=humidity_above_95_ratio,
        median_gap=median_gap,
        activity_obs_count=len(activity_g),
    )

    selected = selected_stations.copy()
    selected["station_id"] = selected["station_id"].astype(str)
    selected_row = selected[selected["station_id"] == str(station_id)]

    if selected_row.empty:
        dist_to_route_center_km = np.nan
    else:
        dist_to_route_center_km = selected_row["dist_to_route_center_km"].iloc[0]

    station_name = (
        g["station_name"].dropna().iloc[0]
        if "station_name" in g.columns and g["station_name"].notna().any()
        else ""
    )

    return {
        "station_id": str(station_id),
        "station_name": station_name,
        "dist_to_route_center_km": dist_to_route_center_km,

        "analysis_window_start": wetness_start.isoformat(),
        "activity_start": activity_start.isoformat(),
        "activity_end": activity_end.isoformat(),
        "analysis_window_end": lag_end.isoformat(),

        "obs_count_analysis_window": len(g),
        "obs_count_activity_window": len(activity_g),
        "median_update_interval_min_in_window": median_gap,
        "max_gap_min_in_window": max_gap,

        "rain_sum_mm_activity": activity_rain_sum,
        "rain_sum_mm_pre_wetness": pre_rain_sum,
        "rain_sum_mm_post_lag": post_rain_sum,
        "rain_sum_mm_full_analysis": full_rain_sum,

        "rain_max_mm_activity": activity_rain_max,
        "rain_max_mm_pre_wetness": pre_rain_max,
        "rain_max_mm_post_lag": post_rain_max,

        "rain_observed_activity_flag": int(bool(rain_observed_activity)),
        "rain_observed_pre_wetness_flag": int(bool(rain_observed_pre)),
        "rain_observed_post_lag_flag": int(bool(rain_observed_post)),

        "humidity_mean_pct_activity": humidity_mean,
        "humidity_max_pct_activity": humidity_max,
        "humidity_delta_pct_activity": humidity_delta,
        "humidity_above_90_ratio_activity": humidity_above_90_ratio,
        "humidity_above_95_ratio_activity": humidity_above_95_ratio,

        "temperature_mean_c_activity": temp_mean,
        "temperature_min_c_activity": temp_min,
        "temperature_max_c_activity": temp_max,
        "temperature_delta_c_activity": temp_delta,

        "wind_speed_mean_ms_activity": wind_mean,
        "wind_speed_max_ms_activity": wind_max,
        "wind_speed_delta_ms_activity": wind_delta,
        "wind_gust_max_ms_activity": wind_gust_max,

        "wind_direction_vector_mean_deg_activity": wind_direction_vector_mean,
        "wind_direction_arithmetic_mean_deg_activity": wind_direction_arithmetic_mean,
        "wind_direction_valid_count_activity": wind_direction_valid_count,
        "wind_direction_data_status": wind_direction_data_status,

        "pressure_mean_hpa_activity": pressure_mean,
        "pressure_min_hpa_activity": pressure_min,
        "pressure_max_hpa_activity": pressure_max,
        "pressure_first_hpa_activity": pressure_first,
        "pressure_last_hpa_activity": pressure_last,
        "pressure_delta_hpa_activity": pressure_delta,
        "pressure_drop_hpa_activity": pressure_drop,
        "pressure_drop_rate_hpa_per_hr": pressure_drop_rate,
        "pressure_drop_flag_activity": pressure_drop_flag,
        "pressure_drop_rate_flag_activity": pressure_drop_rate_flag,

        "rain_data_status": rain_data_status,
        "weather_trend_hint": weather_trend_hint,
    }


def infer_weather_trend_hint(
    activity_rain_sum,
    pre_rain_sum,
    post_rain_sum,
    humidity_mean,
    humidity_max,
    humidity_above_95_ratio,
    wind_max,
    median_gap,
    activity_obs_count,
    pressure_drop_hpa=np.nan,
    pressure_drop_rate_hpa_per_hr=np.nan,
):
    if activity_obs_count < 2:
        return "data_insufficient"

    if pd.notna(activity_rain_sum) and activity_rain_sum >= RAIN_OBS_THRESHOLD_MM:
        return "rain_observed"

    if (
        (pd.isna(activity_rain_sum) or activity_rain_sum < RAIN_OBS_THRESHOLD_MM)
        and pd.notna(post_rain_sum)
        and post_rain_sum >= RAIN_OBS_THRESHOLD_MM
    ):
        return "rain_lag_suspected"

    if (
        pd.notna(pre_rain_sum)
        and pre_rain_sum >= RAIN_OBS_THRESHOLD_MM
        and (pd.isna(activity_rain_sum) or activity_rain_sum < RAIN_OBS_THRESHOLD_MM)
    ):
        return "wet_trail_from_prior_rain"

    if (
        pd.notna(humidity_above_95_ratio)
        and humidity_above_95_ratio >= 0.5
        and (pd.isna(activity_rain_sum) or activity_rain_sum < RAIN_OBS_THRESHOLD_MM)
    ):
        return "possible_mist_or_drizzle"

    # 氣壓下降 + 高濕：優先判定為天候轉壞疑慮
    # 這要放在 humid_no_measured_rain 前面，
    # 否則高濕條件會先被 humid_no_measured_rain 吃掉。
    if (
        (
            pd.notna(pressure_drop_hpa)
            and pressure_drop_hpa >= PRESSURE_DROP_HPA_THRESHOLD
        )
        or (
            pd.notna(pressure_drop_rate_hpa_per_hr)
            and pressure_drop_rate_hpa_per_hr >= PRESSURE_DROP_RATE_HPA_PER_HR_THRESHOLD
        )
    ) and (
        pd.notna(humidity_mean)
        and humidity_mean >= HUMIDITY_HIGH_PCT
    ):
        return "weather_deterioration_suspected"

    if (
        pd.notna(humidity_mean)
        and humidity_mean >= HUMIDITY_HIGH_PCT
        and (pd.isna(activity_rain_sum) or activity_rain_sum < RAIN_OBS_THRESHOLD_MM)
    ):
        return "humid_no_measured_rain"

    if pd.notna(wind_max) and wind_max >= WINDY_THRESHOLD_MS:
        return "windy_exposed"

    if pd.notna(median_gap) and median_gap >= 50:
        return "coarse_update_frequency"

    return "stable_no_measured_rain"


def infer_rain_data_status(
    activity_rain_sum,
    pre_rain_sum,
    post_rain_sum,
    humidity_mean,
    humidity_above_95_ratio,
    median_gap,
    activity_obs_count,
):
    if activity_obs_count < 2:
        return "rain_data_insufficient"

    if pd.notna(activity_rain_sum) and activity_rain_sum >= RAIN_OBS_THRESHOLD_MM:
        return "observed_rain"

    if pd.notna(post_rain_sum) and post_rain_sum >= RAIN_OBS_THRESHOLD_MM:
        return "rain_lag_suspected"

    if pd.notna(pre_rain_sum) and pre_rain_sum >= RAIN_OBS_THRESHOLD_MM:
        return "prior_rain_wet_trail"

    if (
        pd.notna(humidity_above_95_ratio)
        and humidity_above_95_ratio >= 0.5
    ):
        return "suspected_wet_high_humidity"

    if (
        pd.notna(humidity_mean)
        and humidity_mean >= HUMIDITY_HIGH_PCT
    ):
        return "humid_no_measured_rain"

    if pd.notna(median_gap) and median_gap >= 50:
        return "rain_data_uncertain_coarse_update"

    return "no_observed_rain"


def build_trend_features(weather_df, selected_stations, activity_start, activity_end):
    wetness_start = activity_start - pd.Timedelta(hours=TRAIL_WETNESS_PRE_HOURS)
    lag_end = activity_end + pd.Timedelta(hours=RAIN_LAG_POST_HOURS)

    rows = []

    if weather_df.empty:
        return pd.DataFrame()

    for station_id, g in weather_df.groupby("station_id", dropna=False):
        row = summarize_station_trend(
            station_id=station_id,
            station_df=g,
            selected_stations=selected_stations,
            activity_start=activity_start,
            activity_end=activity_end,
            wetness_start=wetness_start,
            lag_end=lag_end,
        )
        rows.append(row)

    out = pd.DataFrame(rows)
    out = out.sort_values("dist_to_route_center_km").reset_index(drop=True)

    return out


# =========================================================
# G. Data quality summary
# =========================================================
def build_data_quality_summary(update_profile, trend_features):
    rows = []

    if update_profile.empty and trend_features.empty:
        return pd.DataFrame(
            [
                {
                    "weather_data_quality": "missing",
                    "dominant_rain_data_status": "rain_data_insufficient",
                    "dominant_weather_trend_hint": "data_insufficient",
                    "nearest_station_update_class": "insufficient_data",
                    "nearest_station_obs_count_activity": 0,
                    "nearest_station_median_update_interval_min": np.nan,
                    "mean_data_completeness_ratio": np.nan,
                    "weather_station_count": 0,
                    "high_confidence_station_count": 0,
                    "rain_lag_suspected_station_count": 0,
                    "suspected_wet_station_count": 0,
                }
            ]
        )

    tf = trend_features.copy()
    up = update_profile.copy()

    nearest = tf.sort_values("dist_to_route_center_km").head(1)

    if nearest.empty:
        nearest_station_id = ""
        nearest_station_obs_count_activity = np.nan
        dominant_rain_data_status = "rain_data_insufficient"
        dominant_weather_trend_hint = "data_insufficient"
    else:
        nearest_row = nearest.iloc[0]
        nearest_station_id = nearest_row.get("station_id", "")
        nearest_station_obs_count_activity = nearest_row.get("obs_count_activity_window", np.nan)
        dominant_rain_data_status = nearest_row.get("rain_data_status", "rain_data_insufficient")
        dominant_weather_trend_hint = nearest_row.get("weather_trend_hint", "data_insufficient")

    if not up.empty:
        up_by_id = up.set_index("station_id")
        if str(nearest_station_id) in up_by_id.index:
            nearest_update_row = up_by_id.loc[str(nearest_station_id)]
            nearest_update_class = nearest_update_row.get("likely_update_frequency_class", "insufficient_data")
            nearest_median_update = nearest_update_row.get("median_update_interval_min", np.nan)
        else:
            nearest_update_class = "insufficient_data"
            nearest_median_update = np.nan

        mean_completeness = up["data_completeness_ratio"].mean()
    else:
        nearest_update_class = "insufficient_data"
        nearest_median_update = np.nan
        mean_completeness = np.nan

    rain_lag_count = int((tf["rain_data_status"] == "rain_lag_suspected").sum()) if not tf.empty else 0
    suspected_wet_count = int(
        tf["rain_data_status"].isin(
            [
                "suspected_wet_high_humidity",
                "humid_no_measured_rain",
                "prior_rain_wet_trail",
            ]
        ).sum()
    ) if not tf.empty else 0

    high_confidence_station_count = int(
        (
            (tf["obs_count_activity_window"] >= 3)
            & (tf["median_update_interval_min_in_window"] <= 20)
        ).sum()
    ) if not tf.empty else 0

    # overall quality
    if high_confidence_station_count >= 2:
        weather_data_quality = "good"
    elif high_confidence_station_count >= 1:
        weather_data_quality = "usable"
    elif len(tf) > 0:
        weather_data_quality = "partial"
    else:
        weather_data_quality = "missing"

    rows.append(
        {
            "weather_data_quality": weather_data_quality,
            "dominant_rain_data_status": dominant_rain_data_status,
            "dominant_weather_trend_hint": dominant_weather_trend_hint,
            "nearest_station_id": nearest_station_id,
            "nearest_station_update_class": nearest_update_class,
            "nearest_station_obs_count_activity": nearest_station_obs_count_activity,
            "nearest_station_median_update_interval_min": nearest_median_update,
            "mean_data_completeness_ratio": mean_completeness,
            "weather_station_count": len(tf),
            "high_confidence_station_count": high_confidence_station_count,
            "rain_lag_suspected_station_count": rain_lag_count,
            "suspected_wet_station_count": suspected_wet_count,
        }
    )

    return pd.DataFrame(rows)


# =========================================================
# H. Main
# =========================================================
def main():
    ensure_exists(DB_PATH)
    ensure_exists(IN_WEATHER_STATIONS_CSV)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    activity_start, activity_end, time_source = load_activity_time_window()

    selected_stations = load_selected_weather_stations()
    station_ids = selected_stations["station_id"].astype(str).tolist()

    wetness_start = activity_start - pd.Timedelta(hours=TRAIL_WETNESS_PRE_HOURS)
    lag_end = activity_end + pd.Timedelta(hours=RAIN_LAG_POST_HOURS)

    profile_start = activity_start - pd.Timedelta(days=PROFILE_LOOKBACK_DAYS)
    profile_end = lag_end

    print("\n=== activity time window ===")
    print("scenario:", SCENARIO_NAME)
    print("time source:", time_source)
    print("activity start UTC:", activity_start)
    print("activity end UTC:", activity_end)
    print("wetness start UTC:", wetness_start)
    print("lag end UTC:", lag_end)
    print("profile start UTC:", profile_start)
    print("profile end UTC:", profile_end)

    print("\n=== selected weather stations ===")
    show_cols = [
        "station_id",
        "station_name",
        "dist_to_route_center_km",
        "obs_count",
        "first_obs_time",
        "last_obs_time",
    ]
    show_cols = [c for c in show_cols if c in selected_stations.columns]
    print(selected_stations[show_cols].to_string(index=False))

    conn = sqlite3.connect(DB_PATH)

    try:
        profile_df = query_weather_observations(
            conn=conn,
            station_ids=station_ids,
            start_time=profile_start.isoformat(),
            end_time=profile_end.isoformat(),
        )

        trend_df_raw = query_weather_observations(
            conn=conn,
            station_ids=station_ids,
            start_time=wetness_start.isoformat(),
            end_time=lag_end.isoformat(),
        )

    finally:
        conn.close()

    update_profile = build_update_profile(
        profile_df,
        selected_stations=selected_stations,
        profile_start=profile_start,
        profile_end=profile_end,
    )

    trend_features = build_trend_features(
        trend_df_raw,
        selected_stations=selected_stations,
        activity_start=activity_start,
        activity_end=activity_end,
    )

    quality_summary = build_data_quality_summary(
        update_profile=update_profile,
        trend_features=trend_features,
    )

    update_profile.to_csv(OUT_UPDATE_PROFILE_CSV, index=False, encoding="utf-8-sig")
    trend_features.to_csv(OUT_TREND_FEATURES_CSV, index=False, encoding="utf-8-sig")
    quality_summary.to_csv(OUT_QUALITY_SUMMARY_CSV, index=False, encoding="utf-8-sig")

    print("\n完成！")
    print("update profile CSV:", OUT_UPDATE_PROFILE_CSV.resolve())
    print("trend features CSV:", OUT_TREND_FEATURES_CSV.resolve())
    print("quality summary CSV:", OUT_QUALITY_SUMMARY_CSV.resolve())

    print("\n=== update profile ===")
    if update_profile.empty:
        print("(empty)")
    else:
        cols = [
            "station_id",
            "station_name",
            "dist_to_route_center_km",
            "obs_count",
            "median_update_interval_min",
            "mean_update_interval_min",
            "max_update_interval_min",
            "p90_update_interval_min",
            "data_completeness_ratio",
            "long_gap_count",
            "likely_update_frequency_class",
        ]
        cols = [c for c in cols if c in update_profile.columns]
        print(update_profile[cols].to_string(index=False))

    print("\n=== trend features ===")
    if trend_features.empty:
        print("(empty)")
    else:
        cols = [
            "station_id",
            "station_name",
            "dist_to_route_center_km",
            "obs_count_activity_window",
            "median_update_interval_min_in_window",
            "rain_sum_mm_activity",
            "rain_sum_mm_pre_wetness",
            "rain_sum_mm_post_lag",
            "humidity_mean_pct_activity",
            "humidity_above_95_ratio_activity",
            "wind_speed_max_ms_activity",
            "wind_gust_max_ms_activity",
            "wind_direction_vector_mean_deg_activity",
            "wind_direction_arithmetic_mean_deg_activity",
            "wind_direction_valid_count_activity",
            "wind_direction_data_status",
            "pressure_drop_hpa_activity",
            "pressure_drop_rate_hpa_per_hr",
            "pressure_drop_flag_activity",
            "rain_data_status",
            "weather_trend_hint",
        ]
        cols = [c for c in cols if c in trend_features.columns]
        print(trend_features[cols].to_string(index=False))

    print("\n=== weather data quality summary ===")
    if quality_summary.empty:
        print("(empty)")
    else:
        print(quality_summary.T.to_string(header=False))


if __name__ == "__main__":
    main()