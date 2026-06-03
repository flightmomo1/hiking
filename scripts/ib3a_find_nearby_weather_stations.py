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

OUT_DIR = Path("ib3_weather_output")
OUT_CSV = OUT_DIR / "qixing_nearby_weather_stations.csv"

SEARCH_RADIUS_KM = 20


def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"找不到天氣資料庫：{DB_PATH.resolve()}")

    if not ROUTE_GEOJSON.exists():
        raise FileNotFoundError(f"找不到路線 GeoJSON：{ROUTE_GEOJSON.resolve()}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------
    # 1. 讀取路線點
    # -----------------------------------------------------
    route_gdf = gpd.read_file(ROUTE_GEOJSON)

    if route_gdf.empty:
        raise ValueError(f"路線資料為空：{ROUTE_GEOJSON}")

    if route_gdf.crs is None:
        route_gdf = route_gdf.set_crs("EPSG:4326")

    route_gdf = route_gdf.to_crs("EPSG:4326")

    metric_crs = route_gdf.estimate_utm_crs()
    route_m = route_gdf.to_crs(metric_crs)

    route_union = route_m.geometry.union_all() if hasattr(route_m.geometry, "union_all") else route_m.geometry.unary_union
    route_center_m = route_union.centroid
    route_center = gpd.GeoSeries([route_center_m], crs=metric_crs).to_crs("EPSG:4326").iloc[0]

    print("route center lat/lon:", route_center.y, route_center.x)
    print("metric CRS:", metric_crs)

    # -----------------------------------------------------
    # 2. 從 weather_observations 抽測站清單
    # -----------------------------------------------------
    conn = sqlite3.connect(DB_PATH)

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

    stations = pd.read_sql_query(sql, conn)
    conn.close()

    if stations.empty:
        raise ValueError("weather_observations 找不到任何有經緯度的測站資料")

    # -----------------------------------------------------
    # 3. 轉 GeoDataFrame 並計算到路線中心距離
    # -----------------------------------------------------
    st_gdf = gpd.GeoDataFrame(
        stations,
        geometry=[
            Point(lon, lat)
            for lon, lat in zip(stations["longitude"], stations["latitude"])
        ],
        crs="EPSG:4326",
    )

    st_m = st_gdf.to_crs(metric_crs)
    st_m["dist_to_route_center_m"] = st_m.geometry.distance(route_center_m)
    st_m["dist_to_route_center_km"] = st_m["dist_to_route_center_m"] / 1000.0

    nearby = st_m[
        st_m["dist_to_route_center_km"] <= SEARCH_RADIUS_KM
    ].copy()

    nearby = nearby.sort_values("dist_to_route_center_km").reset_index(drop=True)

    # 回到 WGS84 方便看經緯度
    nearby_wgs84 = nearby.to_crs("EPSG:4326")
    nearby_wgs84["latitude"] = nearby_wgs84.geometry.y
    nearby_wgs84["longitude"] = nearby_wgs84.geometry.x

    cols = [
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

    nearby_wgs84[cols].to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    print("\n完成！")
    print("nearby station CSV:", OUT_CSV.resolve())

    print("\n=== nearby weather stations ===")
    if nearby_wgs84.empty:
        print(f"在 {SEARCH_RADIUS_KM} km 內找不到測站")
    else:
        print(nearby_wgs84[cols].head(30).to_string(index=False))


if __name__ == "__main__":
    main()