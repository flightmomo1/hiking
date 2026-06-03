# -*- coding: utf-8 -*-
from pathlib import Path
import sqlite3
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point


DB_PATH = Path(
    "/Users/iddmini/Documents/115_Motion改造/FY115_登山/weather/"
    "tw_weather_2026-05-01.sqlite3"
)

ROUTE_GEOJSON = Path(
    "ib1c_route_profile_semantic_output/qixing_route_profile_semantic_enriched.geojson"
)

OUT_DIR = Path("ib3_environment_output")

OUT_WEATHER_CSV = OUT_DIR / "qixing_nearby_weather_stations.csv"
OUT_WATER_CSV = OUT_DIR / "qixing_nearby_water_stations.csv"
OUT_SUMMARY_CSV = OUT_DIR / "qixing_nearby_environment_stations_summary.csv"

SEARCH_RADIUS_KM = 20


def safe_union(geo_series):
    if hasattr(geo_series, "union_all"):
        return geo_series.union_all()
    return geo_series.unary_union


def load_route_center():
    if not ROUTE_GEOJSON.exists():
        raise FileNotFoundError(f"找不到路線 GeoJSON：{ROUTE_GEOJSON.resolve()}")

    route_gdf = gpd.read_file(ROUTE_GEOJSON)

    if route_gdf.empty:
        raise ValueError(f"路線資料為空：{ROUTE_GEOJSON}")

    if route_gdf.crs is None:
        route_gdf = route_gdf.set_crs("EPSG:4326")

    route_gdf = route_gdf.to_crs("EPSG:4326")

    metric_crs = route_gdf.estimate_utm_crs()
    route_m = route_gdf.to_crs(metric_crs)

    route_union = safe_union(route_m.geometry)
    route_center_m = route_union.centroid

    route_center_wgs84 = (
        gpd.GeoSeries([route_center_m], crs=metric_crs)
        .to_crs("EPSG:4326")
        .iloc[0]
    )

    return route_center_m, route_center_wgs84, metric_crs


def read_weather_stations(conn):
    sql = """
    SELECT
        station_id,
        station_name,
        latitude,
        longitude,
        county_name,
        town_name,
        elevation_m,
        COUNT(*) AS obs_count,
        MIN(obs_time) AS first_obs_time,
        MAX(obs_time) AS last_obs_time
    FROM weather_observations
    WHERE latitude IS NOT NULL
      AND longitude IS NOT NULL
    GROUP BY
        station_id,
        station_name,
        latitude,
        longitude,
        county_name,
        town_name,
        elevation_m
    """
    return pd.read_sql_query(sql, conn)


def read_water_stations(conn):
    sql = """
    SELECT
        station_id,
        station_name,
        latitude,
        longitude,
        river_name,
        county_name,
        town_name,
        COUNT(*) AS obs_count,
        MIN(obs_time) AS first_obs_time,
        MAX(obs_time) AS last_obs_time,
        MIN(water_level_m) AS water_level_min_m,
        MAX(water_level_m) AS water_level_max_m
    FROM water_level_observations
    WHERE latitude IS NOT NULL
      AND longitude IS NOT NULL
    GROUP BY
        station_id,
        station_name,
        latitude,
        longitude,
        river_name,
        county_name,
        town_name
    """
    return pd.read_sql_query(sql, conn)


def add_distance_to_route_center(df, route_center_m, metric_crs):
    if df.empty:
        return df

    gdf = gpd.GeoDataFrame(
        df.copy(),
        geometry=[
            Point(lon, lat)
            for lon, lat in zip(df["longitude"], df["latitude"])
        ],
        crs="EPSG:4326",
    )

    gdf_m = gdf.to_crs(metric_crs)
    gdf_m["dist_to_route_center_m"] = gdf_m.geometry.distance(route_center_m)
    gdf_m["dist_to_route_center_km"] = gdf_m["dist_to_route_center_m"] / 1000.0

    nearby = gdf_m[
        gdf_m["dist_to_route_center_km"] <= SEARCH_RADIUS_KM
    ].copy()

    nearby = nearby.sort_values("dist_to_route_center_km").reset_index(drop=True)

    nearby_wgs84 = nearby.to_crs("EPSG:4326")
    nearby_wgs84["latitude"] = nearby_wgs84.geometry.y
    nearby_wgs84["longitude"] = nearby_wgs84.geometry.x

    return pd.DataFrame(nearby_wgs84.drop(columns="geometry"))


def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"找不到資料庫：{DB_PATH.resolve()}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    route_center_m, route_center_wgs84, metric_crs = load_route_center()

    print("route center lat/lon:", route_center_wgs84.y, route_center_wgs84.x)
    print("metric CRS:", metric_crs)
    print("search radius km:", SEARCH_RADIUS_KM)

    conn = sqlite3.connect(DB_PATH)

    try:
        weather_stations = read_weather_stations(conn)
        water_stations = read_water_stations(conn)
    finally:
        conn.close()

    nearby_weather = add_distance_to_route_center(
        weather_stations,
        route_center_m,
        metric_crs,
    )

    nearby_water = add_distance_to_route_center(
        water_stations,
        route_center_m,
        metric_crs,
    )

    # -----------------------------------------------------
    # Weather output
    # -----------------------------------------------------
    weather_cols = [
        "station_id",
        "station_name",
        "county_name",
        "town_name",
        "latitude",
        "longitude",
        "elevation_m",
        "dist_to_route_center_km",
        "obs_count",
        "first_obs_time",
        "last_obs_time",
    ]

    if not nearby_weather.empty:
        nearby_weather[weather_cols].to_csv(
            OUT_WEATHER_CSV,
            index=False,
            encoding="utf-8-sig",
        )
    else:
        pd.DataFrame(columns=weather_cols).to_csv(
            OUT_WEATHER_CSV,
            index=False,
            encoding="utf-8-sig",
        )

    # -----------------------------------------------------
    # Water output
    # -----------------------------------------------------
    water_cols = [
        "station_id",
        "station_name",
        "river_name",
        "county_name",
        "town_name",
        "latitude",
        "longitude",
        "dist_to_route_center_km",
        "obs_count",
        "first_obs_time",
        "last_obs_time",
        "water_level_min_m",
        "water_level_max_m",
    ]

    if not nearby_water.empty:
        nearby_water[water_cols].to_csv(
            OUT_WATER_CSV,
            index=False,
            encoding="utf-8-sig",
        )
    else:
        pd.DataFrame(columns=water_cols).to_csv(
            OUT_WATER_CSV,
            index=False,
            encoding="utf-8-sig",
        )

    # -----------------------------------------------------
    # Combined summary
    # -----------------------------------------------------
    summary_rows = []

    if not nearby_weather.empty:
        for _, row in nearby_weather.head(10).iterrows():
            summary_rows.append(
                {
                    "type": "weather",
                    "station_id": row["station_id"],
                    "station_name": row["station_name"],
                    "river_name": "",
                    "county_name": row.get("county_name", ""),
                    "town_name": row.get("town_name", ""),
                    "dist_to_route_center_km": row["dist_to_route_center_km"],
                    "obs_count": row["obs_count"],
                    "first_obs_time": row["first_obs_time"],
                    "last_obs_time": row["last_obs_time"],
                }
            )

    if not nearby_water.empty:
        for _, row in nearby_water.head(10).iterrows():
            summary_rows.append(
                {
                    "type": "water",
                    "station_id": row["station_id"],
                    "station_name": row["station_name"],
                    "river_name": row.get("river_name", ""),
                    "county_name": row.get("county_name", ""),
                    "town_name": row.get("town_name", ""),
                    "dist_to_route_center_km": row["dist_to_route_center_km"],
                    "obs_count": row["obs_count"],
                    "first_obs_time": row["first_obs_time"],
                    "last_obs_time": row["last_obs_time"],
                }
            )

    summary = pd.DataFrame(summary_rows)
    if not summary.empty:
        summary = summary.sort_values(
            ["type", "dist_to_route_center_km"]
        ).reset_index(drop=True)

    summary.to_csv(
        OUT_SUMMARY_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    print("\n完成！")
    print("weather stations CSV:", OUT_WEATHER_CSV.resolve())
    print("water stations CSV:", OUT_WATER_CSV.resolve())
    print("summary CSV:", OUT_SUMMARY_CSV.resolve())

    print("\n=== nearby weather stations ===")
    if nearby_weather.empty:
        print(f"在 {SEARCH_RADIUS_KM} km 內找不到氣象站")
    else:
        print(nearby_weather[weather_cols].head(30).to_string(index=False))

    print("\n=== nearby water stations ===")
    if nearby_water.empty:
        print(f"在 {SEARCH_RADIUS_KM} km 內找不到水位站")
    else:
        print(nearby_water[water_cols].head(30).to_string(index=False))


if __name__ == "__main__":
    main()