# -*- coding: utf-8 -*-
from pathlib import Path
import math
import os
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd


# =========================================================
# A. Input / Output
# =========================================================
BASE_DIR = Path("/Users/iddmini/Documents/115_Motion改造/FY115_登山/115_osm")

GPX_PATH = Path(
    "/Users/iddmini/Documents/115_Motion改造/FY115_登山/gpx/"
    "冷水坑上-七星山東峰-主峰-下小油坑.gpx"
)

SCENARIO_NAME = os.environ.get("SCENARIO_NAME", "actual_gpx_9stations")

ENV_BASE_DIR = BASE_DIR / "ib3_environment_output"
ENV_DIR = ENV_BASE_DIR / SCENARIO_NAME

WEATHER_WINDOW_CSV = ENV_DIR / "qixing_weather_window.csv"
WEATHER_SUMMARY_CSV = ENV_DIR / "qixing_weather_summary_by_station.csv"

STATION_ELEVATION_CSV = ENV_DIR / "qixing_weather_station_elevation_from_nslc.csv"

OUT_STATION_FUSION_CSV = ENV_DIR / "qixing_route_weather_fusion_by_station.csv"
OUT_ROUTE_FUSED_SUMMARY_CSV = ENV_DIR / "qixing_route_weather_fused_summary.csv"


# =========================================================
# B. Fusion parameters
# =========================================================
DISTANCE_POWER = 1.5
MIN_DISTANCE_KM = 0.3

# 觀測筆數權重，避免低頻站與高頻站同權
ENABLE_OBS_COUNT_WEIGHT = True

# 海拔差異權重，避免平地或遠距低海拔站過度影響山區估計
ENABLE_ELEVATION_WEIGHT = True
ELEVATION_SCALE_M = 1200.0

# 溫度垂直遞減率，約 6.5°C / 1000 m
LAPSE_RATE_C_PER_M = 0.0065

# 氣壓尺度高度，簡化 barometric correction
PRESSURE_SCALE_HEIGHT_M = 8434.0


# =========================================================
# C. Utility
# =========================================================
def ensure_exists(fp: Path):
    if not fp.exists():
        raise FileNotFoundError(f"找不到檔案：{fp.resolve()}")


def strip_namespace(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def read_gpx_points(gpx_path: Path) -> pd.DataFrame:
    """
    Read GPX trkpt lat/lon/ele.
    """
    ensure_exists(gpx_path)

    tree = ET.parse(gpx_path)
    root = tree.getroot()

    rows = []

    for elem in root.iter():
        if strip_namespace(elem.tag) != "trkpt":
            continue

        lat = float(elem.attrib["lat"])
        lon = float(elem.attrib["lon"])

        ele = np.nan
        for child in elem:
            if strip_namespace(child.tag) == "ele" and child.text:
                ele = pd.to_numeric(child.text, errors="coerce")

        rows.append(
            {
                "lat": lat,
                "lon": lon,
                "ele_m": ele,
            }
        )

    if not rows:
        raise ValueError(f"GPX 中找不到 trkpt：{gpx_path}")

    return pd.DataFrame(rows)


def to_numeric_safe(df: pd.DataFrame, cols):
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def weighted_mean(values, weights):
    v = pd.to_numeric(values, errors="coerce")
    w = pd.to_numeric(weights, errors="coerce")

    mask = v.notna() & w.notna() & (w > 0)

    if not mask.any():
        return np.nan

    return float(np.average(v[mask], weights=w[mask]))


def circular_mean_deg(deg_values, weights=None):
    """
    Weighted circular mean for wind direction.
    0/360 wrapping is handled.
    """
    deg = pd.to_numeric(deg_values, errors="coerce")

    if weights is None:
        weights = pd.Series(np.ones(len(deg)), index=deg.index)
    else:
        weights = pd.to_numeric(weights, errors="coerce")

    mask = deg.notna() & weights.notna() & (weights > 0)

    if not mask.any():
        return np.nan

    rad = np.deg2rad(deg[mask])
    w = weights[mask]

    sin_sum = np.sum(np.sin(rad) * w)
    cos_sum = np.sum(np.cos(rad) * w)

    angle = math.degrees(math.atan2(sin_sum, cos_sum))

    if angle < 0:
        angle += 360.0

    return float(angle)


def estimate_route_pressure_from_station(
    station_pressure_hpa,
    station_elev_m,
    route_elev_m,
):
    """
    Adjust station pressure to route elevation using exponential approximation.
    If elevation is missing, return raw station pressure.
    """
    if pd.isna(station_pressure_hpa):
        return np.nan

    if pd.isna(station_elev_m) or pd.isna(route_elev_m):
        return station_pressure_hpa

    delta_z = float(route_elev_m) - float(station_elev_m)

    return float(station_pressure_hpa) * math.exp(-delta_z / PRESSURE_SCALE_HEIGHT_M)


def estimate_route_temperature_from_station(
    station_temperature_c,
    station_elev_m,
    route_elev_m,
):
    """
    Adjust station temperature to route elevation using lapse rate.
    If elevation is missing, return raw station temperature.
    """
    if pd.isna(station_temperature_c):
        return np.nan

    if pd.isna(station_elev_m) or pd.isna(route_elev_m):
        return station_temperature_c

    delta_z = float(route_elev_m) - float(station_elev_m)

    return float(station_temperature_c) - LAPSE_RATE_C_PER_M * delta_z


# =========================================================
# D. Build station-level summary
# =========================================================
def build_station_summary_from_window(weather_window: pd.DataFrame) -> pd.DataFrame:
    if weather_window.empty:
        return pd.DataFrame()

    df = weather_window.copy()

    numeric_cols = [
        "latitude",
        "longitude",
        "elevation_m",
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

    df = to_numeric_safe(df, numeric_cols)

    rows = []

    for station_id, g in df.groupby("station_id", dropna=False):
        g = g.copy()

        wind_dir = circular_mean_deg(
            g["wind_direction_deg"],
            weights=g["wind_speed_ms"].fillna(0) + 0.1,
        )

        row = {
            "station_id": str(station_id),
            "station_name": (
                g["station_name"].dropna().iloc[0]
                if "station_name" in g.columns and g["station_name"].notna().any()
                else ""
            ),

            "latitude": g["latitude"].mean(),
            "longitude": g["longitude"].mean(),
            "station_elevation_m": g["elevation_m"].mean(),

            "n_obs": len(g),

            "temperature_mean_c": g["temperature_c"].mean(),
            "humidity_mean_pct": g["relative_humidity_pct"].mean(),
            "pressure_mean_hpa": g["pressure_hpa"].mean(),

            "wind_speed_mean_ms": g["wind_speed_ms"].mean(),
            "wind_speed_max_ms": g["wind_speed_ms"].max(),
            "wind_gust_max_ms": g["wind_gust_ms"].max(),
            "wind_direction_mean_deg": wind_dir,

            "precipitation_sum_mm": g["precipitation_mm"].sum(min_count=1),
            "precipitation_max_mm": g["precipitation_mm"].max(),
            "precipitation_10min_max_mm": g["precipitation_10min_mm"].max(),
            "precipitation_1hr_max_mm": g["precipitation_1hr_mm"].max(),

            "visibility_min_m": g["visibility_m"].min(),
            "visibility_mean_m": g["visibility_m"].mean(),

            "uv_index_max": g["uv_index"].max(),
        }

        rows.append(row)

    return pd.DataFrame(rows)


def merge_station_metadata(station_summary: pd.DataFrame, weather_summary_csv: Path):
    """
    Merge distance/quadrant from qixing_weather_summary_by_station.csv if available.
    """
    if station_summary.empty:
        return station_summary

    if not weather_summary_csv.exists():
        return station_summary

    meta = pd.read_csv(weather_summary_csv)
    meta["station_id"] = meta["station_id"].astype(str)

    keep = [
        "station_id",
        "dist_to_route_center_km",
        "station_quadrant",
        "county_name",
        "town_name",
    ]
    keep = [c for c in keep if c in meta.columns]

    out = station_summary.copy()
    out["station_id"] = out["station_id"].astype(str)

    out = out.merge(
        meta[keep].drop_duplicates("station_id"),
        on="station_id",
        how="left",
    )

    return out


def merge_station_elevation_from_nslc(station_summary: pd.DataFrame) -> pd.DataFrame:
    if not STATION_ELEVATION_CSV.exists():
        print("警告：找不到測站海拔 CSV，將使用 weather_window 內 elevation_m。")
        return station_summary

    elev = pd.read_csv(STATION_ELEVATION_CSV)
    elev["station_id"] = elev["station_id"].astype(str)

    keep = [
        "station_id",
        "station_elevation_m",
        "elevation_confidence",
        "elevation_source",
        "nearest_contour_distance_m",
        "n_contours_used",
    ]
    keep = [c for c in keep if c in elev.columns]

    out = station_summary.copy()
    out["station_id"] = out["station_id"].astype(str)

    # 若原本 station_elevation_m 是 NaN，用 NSLC 估算值補上
    out = out.merge(
        elev[keep].drop_duplicates("station_id"),
        on="station_id",
        how="left",
        suffixes=("", "_nslc"),
    )

    if "station_elevation_m_nslc" in out.columns:
        out["station_elevation_m"] = out["station_elevation_m"].combine_first(
            out["station_elevation_m_nslc"]
        )
        out = out.drop(columns=["station_elevation_m_nslc"])

    return out

# =========================================================
# E. Fusion
# =========================================================
def compute_station_weights(stations: pd.DataFrame, route_elev_m) -> pd.DataFrame:
    out = stations.copy()

    if "dist_to_route_center_km" not in out.columns:
        out["dist_to_route_center_km"] = np.nan

    # 若沒有距離，給較低權重，但不讓它直接消失
    dist = pd.to_numeric(out["dist_to_route_center_km"], errors="coerce")
    dist = dist.fillna(dist.max() if dist.notna().any() else 10.0)
    dist = dist.clip(lower=MIN_DISTANCE_KM)

    out["distance_weight"] = 1.0 / (dist ** DISTANCE_POWER)

    if ENABLE_OBS_COUNT_WEIGHT and "n_obs" in out.columns:
        n = pd.to_numeric(out["n_obs"], errors="coerce").fillna(0)
        max_n = max(float(n.max()), 1.0)
        out["obs_count_weight"] = np.sqrt(n / max_n).clip(lower=0.1)
    else:
        out["obs_count_weight"] = 1.0

    if ENABLE_ELEVATION_WEIGHT and pd.notna(route_elev_m):
        elev = pd.to_numeric(out["station_elevation_m"], errors="coerce")
        elev_delta = (elev - route_elev_m).abs()
        out["elevation_delta_m"] = elev_delta
        out["elevation_weight"] = np.exp(-elev_delta / ELEVATION_SCALE_M)
        out["elevation_weight"] = out["elevation_weight"].fillna(0.5)
    else:
        out["elevation_delta_m"] = np.nan
        out["elevation_weight"] = 1.0

    out["raw_weight"] = (
        out["distance_weight"]
        * out["obs_count_weight"]
        * out["elevation_weight"]
    )

    total = out["raw_weight"].sum()

    if total > 0:
        out["fusion_weight"] = out["raw_weight"] / total
    else:
        out["fusion_weight"] = 1.0 / len(out)

    return out


def build_route_fused_weather(stations_weighted: pd.DataFrame, route_info: dict):
    if stations_weighted.empty:
        return pd.DataFrame()

    df = stations_weighted.copy()
    w = df["fusion_weight"]

    route_elev_m = route_info["route_mean_elevation_m"]

    # -----------------------------------------------------
    # Elevation-corrected station estimates
    # -----------------------------------------------------
    df["temperature_route_est_c"] = [
        estimate_route_temperature_from_station(
            r["temperature_mean_c"],
            r["station_elevation_m"],
            route_elev_m,
        )
        for _, r in df.iterrows()
    ]

    df["pressure_route_est_hpa"] = [
        estimate_route_pressure_from_station(
            r["pressure_mean_hpa"],
            r["station_elevation_m"],
            route_elev_m,
        )
        for _, r in df.iterrows()
    ]

    # -----------------------------------------------------
    # Route-level fused values
    # -----------------------------------------------------
    route_temperature_c = weighted_mean(df["temperature_route_est_c"], w)
    route_humidity_pct = weighted_mean(df["humidity_mean_pct"], w)
    route_pressure_hpa = weighted_mean(df["pressure_route_est_hpa"], w)

    route_wind_speed_mean_ms = weighted_mean(df["wind_speed_mean_ms"], w)
    route_wind_speed_max_ms = df["wind_speed_max_ms"].max()
    route_wind_gust_max_ms = df["wind_gust_max_ms"].max()

    route_wind_direction_deg = circular_mean_deg(
        df["wind_direction_mean_deg"],
        weights=w,
    )

    route_precipitation_weighted_sum_mm = weighted_mean(
        df["precipitation_sum_mm"],
        w,
    )

    route_precipitation_max_station_mm = df["precipitation_sum_mm"].max()
    route_precipitation_1hr_max_station_mm = df["precipitation_1hr_max_mm"].max()
    route_precipitation_10min_max_station_mm = df["precipitation_10min_max_mm"].max()

    route_visibility_min_m = df["visibility_min_m"].min()
    route_visibility_mean_m = weighted_mean(df["visibility_mean_m"], w)

    row = {
        "fusion_method": "distance_obs_elevation_weighted",
        "station_count": len(df),

        "route_center_lat": route_info["route_center_lat"],
        "route_center_lon": route_info["route_center_lon"],
        "route_mean_elevation_m": route_info["route_mean_elevation_m"],
        "route_min_elevation_m": route_info["route_min_elevation_m"],
        "route_max_elevation_m": route_info["route_max_elevation_m"],

        "route_temperature_est_c": route_temperature_c,
        "route_humidity_est_pct": route_humidity_pct,
        "route_pressure_est_hpa": route_pressure_hpa,

        "route_wind_speed_mean_est_ms": route_wind_speed_mean_ms,
        "route_wind_speed_max_station_ms": route_wind_speed_max_ms,
        "route_wind_gust_max_station_ms": route_wind_gust_max_ms,
        "route_wind_direction_est_deg": route_wind_direction_deg,

        "route_precipitation_weighted_sum_mm": route_precipitation_weighted_sum_mm,
        "route_precipitation_max_station_mm": route_precipitation_max_station_mm,
        "route_precipitation_1hr_max_station_mm": route_precipitation_1hr_max_station_mm,
        "route_precipitation_10min_max_station_mm": route_precipitation_10min_max_station_mm,

        "route_visibility_min_station_m": route_visibility_min_m,
        "route_visibility_mean_est_m": route_visibility_mean_m,

        "nearest_station_km": df["dist_to_route_center_km"].min()
        if "dist_to_route_center_km" in df.columns
        else np.nan,

        "farthest_station_km": df["dist_to_route_center_km"].max()
        if "dist_to_route_center_km" in df.columns
        else np.nan,

        "max_station_weight": df["fusion_weight"].max(),
    }

    return pd.DataFrame([row]), df


# =========================================================
# F. Main
# =========================================================
def main():
    ensure_exists(GPX_PATH)
    ensure_exists(WEATHER_WINDOW_CSV)

    OUT_STATION_FUSION_CSV.parent.mkdir(parents=True, exist_ok=True)

    route = read_gpx_points(GPX_PATH)

    route_info = {
        "route_center_lat": route["lat"].mean(),
        "route_center_lon": route["lon"].mean(),
        "route_mean_elevation_m": route["ele_m"].mean(),
        "route_min_elevation_m": route["ele_m"].min(),
        "route_max_elevation_m": route["ele_m"].max(),
    }

    weather_window = pd.read_csv(WEATHER_WINDOW_CSV)

    station_summary = build_station_summary_from_window(weather_window)
    station_summary = merge_station_metadata(station_summary, WEATHER_SUMMARY_CSV)
    station_summary = merge_station_elevation_from_nslc(station_summary)

    station_weighted = compute_station_weights(
        station_summary,
        route_info["route_mean_elevation_m"],
    )

    route_fused_summary, station_fusion_detail = build_route_fused_weather(
        station_weighted,
        route_info,
    )

    station_fusion_detail.to_csv(
        OUT_STATION_FUSION_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    route_fused_summary.to_csv(
        OUT_ROUTE_FUSED_SUMMARY_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    print("\n完成！")
    print("station fusion CSV:", OUT_STATION_FUSION_CSV.resolve())
    print("route fused summary CSV:", OUT_ROUTE_FUSED_SUMMARY_CSV.resolve())
    print("scenario:", SCENARIO_NAME)
    
    print("\n=== route info ===")
    print(pd.DataFrame([route_info]).T.to_string(header=False))

    print("\n=== station fusion weights ===")
    show_cols = [
        "station_id",
        "station_name",
        "station_quadrant",
        "dist_to_route_center_km",
        "station_elevation_m",
        "elevation_delta_m",
        "n_obs",
        "distance_weight",
        "obs_count_weight",
        "elevation_weight",
        "fusion_weight",
        "temperature_mean_c",
        "temperature_route_est_c",
        "pressure_mean_hpa",
        "pressure_route_est_hpa",
        "humidity_mean_pct",
        "wind_speed_mean_ms",
        "precipitation_sum_mm",
    ]
    show_cols = [c for c in show_cols if c in station_fusion_detail.columns]
    print(station_fusion_detail[show_cols].to_string(index=False))

    print("\n=== route fused weather summary ===")
    print(route_fused_summary.T.to_string(header=False))


if __name__ == "__main__":
    main()