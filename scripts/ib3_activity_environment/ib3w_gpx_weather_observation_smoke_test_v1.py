from __future__ import annotations

from pathlib import Path
from datetime import datetime
import argparse
import sqlite3
import xml.etree.ElementTree as ET
from math import radians, sin, cos, sqrt, atan2

import pandas as pd


DEFAULT_GPX = Path(
    r"D:\mountain_work\115_osm\activity_input\gpx\qixing_lengshuikeng_xiaoyoukeng_gpx\冷水坑上-七星山東峰-主峰-下小油坑.gpx"
)
DEFAULT_WEATHER_DB = Path("weather/tw_weather_2026-05-01.sqlite3")
DEFAULT_OUTPUT_CASE = "qixing_lengshuikeng_xiaoyoukeng_20260410_biji_gpx"
DEFAULT_OUT_ROOT = Path("outputs/ib3w_gpx_weather_observation_smoke_test_v1")


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlambda / 2) ** 2
    return 2 * r * atan2(sqrt(a), sqrt(1 - a))


def parse_gpx_track(gpx_path: Path) -> tuple[list[tuple[float, float]], list[datetime]]:
    ns = {"g": "http://www.topografix.com/GPX/1/1"}
    root = ET.parse(gpx_path).getroot()

    points: list[tuple[float, float]] = []
    times: list[datetime] = []

    for trkpt in root.findall(".//g:trkpt", ns):
        lat = float(trkpt.attrib["lat"])
        lon = float(trkpt.attrib["lon"])
        t_node = trkpt.find("g:time", ns)

        if t_node is None or not t_node.text:
            continue

        t = datetime.fromisoformat(t_node.text.replace("Z", "+00:00"))
        points.append((lat, lon))
        times.append(t)

    if not times:
        raise RuntimeError(f"No GPX trackpoint time found: {gpx_path}")

    return points, times


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def build_bbox(points: list[tuple[float, float]], pad_deg: float) -> dict[str, float]:
    lat_values = [p[0] for p in points]
    lon_values = [p[1] for p in points]

    return {
        "lat_min": min(lat_values) - pad_deg,
        "lat_max": max(lat_values) + pad_deg,
        "lon_min": min(lon_values) - pad_deg,
        "lon_max": max(lon_values) + pad_deg,
    }


def query_all_taiwan_weather_window(
    conn: sqlite3.Connection,
    start_utc: str,
    end_utc: str,
) -> pd.DataFrame:
    q = """
    SELECT
      COUNT(*) AS obs_n,
      COUNT(DISTINCT station_id) AS station_n,
      MIN(obs_time) AS min_obs_time,
      MAX(obs_time) AS max_obs_time
    FROM weather_observations
    WHERE obs_time IS NOT NULL
      AND obs_time >= ?
      AND obs_time <= ?
    """
    return pd.read_sql_query(q, conn, params=[start_utc, end_utc])


def query_nearby_weather_stations(
    conn: sqlite3.Connection,
    start_utc: str,
    end_utc: str,
    bbox: dict[str, float],
) -> pd.DataFrame:
    q = """
    SELECT
      station_id,
      station_name,
      county_name,
      town_name,
      latitude,
      longitude,
      elevation_m,
      COUNT(*) AS obs_n,
      MIN(obs_time) AS min_obs_time,
      MAX(obs_time) AS max_obs_time,
      SUM(CASE WHEN precipitation_mm IS NOT NULL THEN 1 ELSE 0 END) AS precipitation_nonnull_n,
      SUM(CASE WHEN precipitation_mm = 0 THEN 1 ELSE 0 END) AS precipitation_zero_n,
      SUM(CASE WHEN precipitation_mm > 0 THEN 1 ELSE 0 END) AS precipitation_positive_n,
      SUM(CASE WHEN temperature_c IS NOT NULL THEN 1 ELSE 0 END) AS temperature_nonnull_n,
      SUM(CASE WHEN relative_humidity_pct IS NOT NULL THEN 1 ELSE 0 END) AS humidity_nonnull_n,
      SUM(CASE WHEN pressure_hpa IS NOT NULL THEN 1 ELSE 0 END) AS pressure_nonnull_n,
      SUM(CASE WHEN wind_speed_ms IS NOT NULL THEN 1 ELSE 0 END) AS wind_speed_nonnull_n
    FROM weather_observations
    WHERE obs_time IS NOT NULL
      AND obs_time >= ?
      AND obs_time <= ?
      AND latitude BETWEEN ? AND ?
      AND longitude BETWEEN ? AND ?
    GROUP BY
      station_id,
      station_name,
      county_name,
      town_name,
      latitude,
      longitude,
      elevation_m
    """
    return pd.read_sql_query(
        q,
        conn,
        params=[
            start_utc,
            end_utc,
            bbox["lat_min"],
            bbox["lat_max"],
            bbox["lon_min"],
            bbox["lon_max"],
        ],
    )


def add_nearest_distance(
    stations: pd.DataFrame,
    points: list[tuple[float, float]],
) -> pd.DataFrame:
    if stations.empty:
        stations["nearest_gpx_dist_m"] = []
        return stations

    nearest: list[float] = []

    for _, s in stations.iterrows():
        station_lat = float(s["latitude"])
        station_lon = float(s["longitude"])
        d = min(
            haversine_m(station_lat, station_lon, lat, lon)
            for lat, lon in points
        )
        nearest.append(round(d, 1))

    stations = stations.copy()
    stations["nearest_gpx_dist_m"] = nearest

    # Positive smoke test only. Do not use this as final station selection policy.
    stations["representative_candidate_hint"] = stations.apply(
        lambda r: (
            "LIKELY_REPRESENTATIVE_MOUNTAIN_OR_NEARBY_STATION"
            if float(r["nearest_gpx_dist_m"]) <= 5000 and int(r["obs_n"]) >= 2
            else "LOWER_PRIORITY_DISTANCE_OR_OBS_COUNT"
        ),
        axis=1,
    )

    stations["zero_fallback_used"] = False
    stations["audit_policy"] = (
        "observed_zero_precipitation_is_kept_as_observed_zero; "
        "missing_is_not_converted_to_zero"
    )

    return stations.sort_values(["nearest_gpx_dist_m", "obs_n"])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="IB3W GPX weather observation positive smoke test."
    )
    parser.add_argument("--gpx", type=Path, default=DEFAULT_GPX)
    parser.add_argument("--weather-db", type=Path, default=DEFAULT_WEATHER_DB)
    parser.add_argument("--output-case", default=DEFAULT_OUTPUT_CASE)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    parser.add_argument("--bbox-pad-deg", type=float, default=0.20)
    args = parser.parse_args()

    gpx_path = args.gpx
    weather_db = args.weather_db
    out_dir = args.out_root / args.output_case
    out_dir.mkdir(parents=True, exist_ok=True)

    out_summary = out_dir / "gpx_weather_observation_smoke_summary.csv"
    out_stations = out_dir / "gpx_weather_observation_nearby_stations.csv"

    if not gpx_path.exists():
        raise FileNotFoundError(f"GPX not found: {gpx_path}")

    if not weather_db.exists():
        raise FileNotFoundError(f"Weather DB not found: {weather_db}")

    points, times = parse_gpx_track(gpx_path)
    start_utc_dt = min(times)
    end_utc_dt = max(times)
    start_utc = start_utc_dt.isoformat()
    end_utc = end_utc_dt.isoformat()
    duration_min = round((end_utc_dt - start_utc_dt).total_seconds() / 60.0, 2)

    bbox = build_bbox(points, args.bbox_pad_deg)

    conn = sqlite3.connect(weather_db)

    if not table_exists(conn, "weather_observations"):
        raise RuntimeError("weather_observations table not found.")

    all_weather = query_all_taiwan_weather_window(conn, start_utc, end_utc)
    nearby = query_nearby_weather_stations(conn, start_utc, end_utc, bbox)
    nearby = add_nearest_distance(nearby, points)

    conn.close()

    all_obs_n = int(all_weather["obs_n"].iloc[0] or 0)
    all_station_n = int(all_weather["station_n"].iloc[0] or 0)
    nearby_station_n = int(len(nearby))
    nearby_with_precip_n = int((nearby["precipitation_nonnull_n"] > 0).sum()) if len(nearby) else 0
    nearby_with_temp_n = int((nearby["temperature_nonnull_n"] > 0).sum()) if len(nearby) else 0
    nearby_with_humidity_n = int((nearby["humidity_nonnull_n"] > 0).sum()) if len(nearby) else 0
    nearby_precip_positive_station_n = int((nearby["precipitation_positive_n"] > 0).sum()) if len(nearby) else 0

    if nearby_station_n > 0:
        nearest_station = nearby.iloc[0]
        nearest_station_id = nearest_station["station_id"]
        nearest_station_name = nearest_station["station_name"]
        nearest_gpx_dist_m = nearest_station["nearest_gpx_dist_m"]
    else:
        nearest_station_id = ""
        nearest_station_name = ""
        nearest_gpx_dist_m = ""

    summary = pd.DataFrame(
        [
            {
                "output_case": args.output_case,
                "gpx_path": str(gpx_path),
                "weather_db_path": str(weather_db),
                "gpx_track_points_with_time": len(times),
                "activity_start_utc": start_utc,
                "activity_end_utc": end_utc,
                "activity_duration_min": duration_min,
                "weather_observation_table_found": True,
                "all_taiwan_matching_obs_n": all_obs_n,
                "all_taiwan_matching_station_n": all_station_n,
                "all_taiwan_matching_min_obs_time": all_weather["min_obs_time"].iloc[0],
                "all_taiwan_matching_max_obs_time": all_weather["max_obs_time"].iloc[0],
                "bbox_pad_deg": args.bbox_pad_deg,
                "bbox_lat_min": bbox["lat_min"],
                "bbox_lat_max": bbox["lat_max"],
                "bbox_lon_min": bbox["lon_min"],
                "bbox_lon_max": bbox["lon_max"],
                "nearby_station_n": nearby_station_n,
                "nearby_with_precipitation_n": nearby_with_precip_n,
                "nearby_with_temperature_n": nearby_with_temp_n,
                "nearby_with_humidity_n": nearby_with_humidity_n,
                "nearby_precipitation_positive_station_n": nearby_precip_positive_station_n,
                "nearest_station_id": nearest_station_id,
                "nearest_station_name": nearest_station_name,
                "nearest_gpx_dist_m": nearest_gpx_dist_m,
                "weather_data_status": (
                    "MATCHING_WEATHER_OBSERVATIONS_FOUND"
                    if all_obs_n > 0 and nearby_station_n > 0
                    else "NO_MATCHING_WEATHER_OBSERVATIONS"
                ),
                "precipitation_interpretation": (
                    "Observed zero precipitation is evidence from raw observations, not fallback."
                    if nearby_with_precip_n > 0 and nearby_precip_positive_station_n == 0
                    else "Precipitation has positive or missing observations; inspect station rows."
                ),
                "zero_fallback_used": False,
                "audit_policy": (
                    "missing_remains_missing; observed_zero_only_if_raw_observation_is_zero"
                ),
            }
        ]
    )

    summary.to_csv(out_summary, index=False, encoding="utf-8-sig")
    nearby.to_csv(out_stations, index=False, encoding="utf-8-sig")

    print("wrote:", out_summary)
    print("wrote:", out_stations)
    print()
    print(summary.to_string(index=False))
    print()
    print("=== nearest stations ===")
    if len(nearby):
        print(
            nearby[
                [
                    "station_id",
                    "station_name",
                    "county_name",
                    "town_name",
                    "nearest_gpx_dist_m",
                    "obs_n",
                    "precipitation_nonnull_n",
                    "precipitation_zero_n",
                    "precipitation_positive_n",
                    "temperature_nonnull_n",
                    "humidity_nonnull_n",
                    "representative_candidate_hint",
                    "zero_fallback_used",
                ]
            ]
            .head(20)
            .to_string(index=False)
        )
    else:
        print("NO_NEARBY_WEATHER_STATIONS_IN_ACTIVITY_WINDOW")


if __name__ == "__main__":
    main()
