# -*- coding: utf-8 -*-
from pathlib import Path
import math
import os

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point


# =========================================================
# A. Input / Output
# =========================================================
BASE_DIR = Path("/Users/iddmini/Documents/115_Motion改造/FY115_登山/115_osm")
PROJECT_ROOT = Path("/Users/iddmini/Documents/115_Motion改造/FY115_登山")

SCENARIO_NAME = os.environ.get("SCENARIO_NAME", "actual_gpx_9stations")

ENV_BASE_DIR = BASE_DIR / "ib3_environment_output"
ENV_DIR = ENV_BASE_DIR / SCENARIO_NAME

WEATHER_SUMMARY_CSV = ENV_DIR / "qixing_weather_summary_by_station.csv"

OUT_STATION_ELEVATION_CSV = (
    ENV_DIR / "qixing_weather_station_elevation_from_nslc.csv"
)

# ---------------------------------------------------------
# NSLC contour SHP
# ---------------------------------------------------------
# 若自動搜尋找不到，請把完整 SHP 路徑填在這裡，例如：
# CONTOUR_SHP_PATH = Path("/Users/iddmini/.../某某等高線.shp")
CONTOUR_SHP_PATH = Path(
    "/Users/iddmini/Documents/osm路況研究/112年經建版地形圖數值資料檔(比例尺二萬五千分之一)(SHP檔)/112年經建版地形圖數值資料檔(比例尺二萬五千分之一)(SHP檔)_/圖檔/97233NW/向量25K/ContourL.shp"
)

# 自動搜尋範圍
CONTOUR_SEARCH_ROOTS = [
    BASE_DIR,
    PROJECT_ROOT,
]

# 如果 SHP 沒有 CRS，先假設為 TWD97 / TM2 zone 121
# 台灣常見：EPSG:3826
DEFAULT_CONTOUR_CRS_IF_MISSING = "EPSG:3826"

# 統一轉成公尺座標系計算距離
TARGET_METRIC_CRS = "EPSG:3826"


# =========================================================
# B. Elevation estimation settings
# =========================================================
SEARCH_RADII_M = [500, 1000, 2000, 5000]

MAX_CONTOURS_USED = 12
MIN_CONTOURS_REQUIRED = 2

IDW_POWER = 2.0
MIN_DISTANCE_M = 1.0

ELEVATION_CONFIDENCE_GOOD_DISTANCE_M = 300
ELEVATION_CONFIDENCE_OK_DISTANCE_M = 1000


# =========================================================
# C. Utility
# =========================================================
def ensure_exists(fp: Path):
    if not fp.exists():
        raise FileNotFoundError(f"找不到檔案：{fp.resolve()}")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    return out


def find_coord_columns(df: pd.DataFrame):
    lat_candidates = [
        "lat",
        "latitude",
        "station_lat",
        "station_latitude",
        "緯度",
    ]

    lon_candidates = [
        "lon",
        "lng",
        "longitude",
        "station_lon",
        "station_lng",
        "station_longitude",
        "經度",
    ]

    lat_col = next((c for c in lat_candidates if c in df.columns), None)
    lon_col = next((c for c in lon_candidates if c in df.columns), None)

    if lat_col is None or lon_col is None:
        raise ValueError(
            "找不到測站經緯度欄位。需要 lat/lon 或 latitude/longitude。"
        )

    return lat_col, lon_col


def auto_find_contour_shp():
    if CONTOUR_SHP_PATH is not None:
        fp = Path(CONTOUR_SHP_PATH)
        ensure_exists(fp)
        return fp

    candidates = []

    keyword_scores = [
        ("contour", 20),
        ("contours", 20),
        ("等高", 20),
        ("elev", 15),
        ("elevation", 15),
        ("height", 10),
        ("nslc", 10),
        ("25k", 5),
    ]

    for root in CONTOUR_SEARCH_ROOTS:
        root = Path(root)
        if not root.exists():
            continue

        for shp in root.rglob("*.shp"):
            name = shp.name.lower()
            score = 0

            for keyword, s in keyword_scores:
                if keyword.lower() in name:
                    score += s

            # 排除明顯不是等高線的圖層
            bad_keywords = [
                "road",
                "river",
                "water",
                "building",
                "boundary",
                "行政",
                "道路",
                "水系",
                "建物",
            ]
            if any(k in name for k in bad_keywords):
                score -= 20

            if score > 0:
                candidates.append((score, shp))

    candidates = sorted(candidates, key=lambda x: x[0], reverse=True)

    if not candidates:
        raise FileNotFoundError(
            "自動搜尋找不到疑似 NSLC 等高線 SHP。"
            "請手動設定 CONTOUR_SHP_PATH。"
        )

    print("\n=== contour SHP candidates ===")
    for score, shp in candidates[:10]:
        print(f"score={score:>3}  {shp}")

    selected = candidates[0][1]
    print("\n使用等高線 SHP:", selected)

    return selected


def detect_elevation_field(gdf: gpd.GeoDataFrame):
    """
    自動猜測等高線高程欄位。
    參考既有 ia2_enrich_segments_contour.py 的 guess_elev_field()，
    可抓到像 zv2 這類欄位。
    """
    candidates = [
        "ELEV", "Elev", "elev",
        "ELEVATION", "Elevation", "elevation",
        "HEIGHT", "Height", "height",
        "Z", "z",
        "Contour", "CONTOUR", "contour",
        "contour_m", "CONTOUR_M",
        "高程", "等高線", "標高",
    ]

    cols_lower = {str(c).lower(): c for c in gdf.columns}

    for c in candidates:
        if c.lower() in cols_lower:
            col = cols_lower[c.lower()]
            s = pd.to_numeric(gdf[col], errors="coerce")
            if s.notna().sum() > 0:
                return col

    numeric_cols = []
    for c in gdf.columns:
        if c == "geometry":
            continue

        s = pd.to_numeric(gdf[c], errors="coerce")
        if s.notna().sum() > 0:
            numeric_cols.append(c)

    for c in numeric_cols:
        cl = str(c).lower()
        if any(k in cl for k in ["elev", "height", "contour", "z"]):
            return c

    # fallback：找合理海拔範圍的數值欄位
    numeric_candidates = []
    for c in numeric_cols:
        s = pd.to_numeric(gdf[c], errors="coerce")
        valid = s.dropna()

        if len(valid) == 0:
            continue

        if valid.min() >= -100 and valid.max() <= 5000:
            numeric_candidates.append(
                {
                    "column": c,
                    "valid_count": len(valid),
                    "min": valid.min(),
                    "max": valid.max(),
                    "unique_count": valid.nunique(),
                }
            )

    if numeric_candidates:
        cand_df = pd.DataFrame(numeric_candidates)
        cand_df = cand_df.sort_values(
            ["unique_count", "valid_count"],
            ascending=[False, False],
        )

        print("\n警告：未找到標準高程欄位，改用疑似高程欄位：")
        print(cand_df.head(10).to_string(index=False))

        return cand_df.iloc[0]["column"]

    print("\n=== contour columns ===")
    print(list(gdf.columns))

    raise ValueError(
        "找不到等高線高程欄位。請檢查 ContourL.shp 欄位名稱。"
    )


def load_contours(contour_shp: Path):
    ensure_exists(contour_shp)

    gdf = gpd.read_file(contour_shp)
    if gdf.empty:
        raise ValueError(f"等高線 SHP 為空：{contour_shp}")

    if gdf.crs is None:
        print(
            f"警告：等高線 SHP 沒有 CRS，暫設為 {DEFAULT_CONTOUR_CRS_IF_MISSING}"
        )
        gdf = gdf.set_crs(DEFAULT_CONTOUR_CRS_IF_MISSING)

    elevation_field = detect_elevation_field(gdf)

    gdf["contour_elevation_m"] = pd.to_numeric(
        gdf[elevation_field],
        errors="coerce",
    )

    gdf = gdf.dropna(subset=["contour_elevation_m", "geometry"]).copy()

    # 只保留線或多線
    gdf = gdf[gdf.geometry.type.isin(["LineString", "MultiLineString"])].copy()

    if gdf.empty:
        raise ValueError("等高線資料沒有可用的 LineString / MultiLineString。")

    gdf = gdf.to_crs(TARGET_METRIC_CRS)

    return gdf, elevation_field


def read_weather_stations(weather_summary_csv: Path):
    ensure_exists(weather_summary_csv)

    df = pd.read_csv(weather_summary_csv)
    df = normalize_columns(df)

    if df.empty:
        raise ValueError(f"氣象站 summary 為空：{weather_summary_csv}")

    if "station_id" not in df.columns:
        raise ValueError("weather summary 缺少 station_id 欄位。")

    lat_col, lon_col = find_coord_columns(df)

    df["station_id"] = df["station_id"].astype(str)
    df["station_lat"] = pd.to_numeric(df[lat_col], errors="coerce")
    df["station_lon"] = pd.to_numeric(df[lon_col], errors="coerce")

    df = df.dropna(subset=["station_lat", "station_lon"]).copy()

    gdf = gpd.GeoDataFrame(
        df,
        geometry=[
            Point(lon, lat)
            for lon, lat in zip(df["station_lon"], df["station_lat"])
        ],
        crs="EPSG:4326",
    ).to_crs(TARGET_METRIC_CRS)

    return gdf


def idw_elevation_from_contours(
    station_geom,
    contours_gdf: gpd.GeoDataFrame,
):
    """
    Estimate station elevation from nearby contour lines using IDW.
    """
    sindex = contours_gdf.sindex

    selected = None
    selected_radius = None

    for radius_m in SEARCH_RADII_M:
        buffer_geom = station_geom.buffer(radius_m)

        idx = list(sindex.query(buffer_geom, predicate="intersects"))

        if not idx:
            continue

        cand = contours_gdf.iloc[idx].copy()
        cand["distance_m"] = cand.geometry.distance(station_geom)

        # 理論上 buffer 查到的不一定全部距離 <= radius，保守過濾
        cand = cand[cand["distance_m"] <= radius_m].copy()

        if cand.empty:
            continue

        cand = cand.sort_values("distance_m").head(MAX_CONTOURS_USED)

        if len(cand) >= MIN_CONTOURS_REQUIRED:
            selected = cand
            selected_radius = radius_m
            break

    # 如果所有半徑都不足，取最近的 MAX_CONTOURS_USED 條作為 fallback
    if selected is None:
        distances = contours_gdf.geometry.distance(station_geom)
        cand = contours_gdf.copy()
        cand["distance_m"] = distances
        cand = cand.sort_values("distance_m").head(MAX_CONTOURS_USED)
        selected = cand
        selected_radius = np.nan

    if selected.empty:
        return {
            "station_elevation_m": np.nan,
            "elevation_source": "nslc_contour_failed",
            "elevation_confidence": "none",
            "elevation_search_radius_m": selected_radius,
            "n_contours_used": 0,
            "nearest_contour_distance_m": np.nan,
            "nearest_contour_elevation_m": np.nan,
            "contour_elevation_min_m": np.nan,
            "contour_elevation_max_m": np.nan,
            "contour_elevation_std_m": np.nan,
        }

    selected = selected.copy()

    dist = selected["distance_m"].clip(lower=MIN_DISTANCE_M)
    weights = 1.0 / (dist ** IDW_POWER)

    elev = pd.to_numeric(selected["contour_elevation_m"], errors="coerce")
    valid = elev.notna() & weights.notna() & (weights > 0)

    if not valid.any():
        station_elev = np.nan
    else:
        station_elev = float(np.average(elev[valid], weights=weights[valid]))

    nearest = selected.sort_values("distance_m").iloc[0]
    nearest_dist = float(nearest["distance_m"])
    nearest_elev = float(nearest["contour_elevation_m"])

    if nearest_dist <= ELEVATION_CONFIDENCE_GOOD_DISTANCE_M:
        confidence = "good"
    elif nearest_dist <= ELEVATION_CONFIDENCE_OK_DISTANCE_M:
        confidence = "moderate"
    else:
        confidence = "low"

    return {
        "station_elevation_m": station_elev,
        "elevation_source": "nslc_contour_idw",
        "elevation_confidence": confidence,
        "elevation_search_radius_m": selected_radius,
        "n_contours_used": len(selected),
        "nearest_contour_distance_m": nearest_dist,
        "nearest_contour_elevation_m": nearest_elev,
        "contour_elevation_min_m": float(elev.min()),
        "contour_elevation_max_m": float(elev.max()),
        "contour_elevation_std_m": float(elev.std()) if len(elev.dropna()) > 1 else 0.0,
    }


# =========================================================
# D. Main
# =========================================================
def main():
    contour_shp = auto_find_contour_shp()
    contours, elevation_field = load_contours(contour_shp)

    stations = read_weather_stations(WEATHER_SUMMARY_CSV)

    rows = []

    print("\n=== input ===")
    print("scenario:", SCENARIO_NAME)
    print("weather summary:", WEATHER_SUMMARY_CSV.resolve())
    print("contour shp:", contour_shp.resolve())
    print("contour crs:", contours.crs)
    print("contour elevation field:", elevation_field)
    print("stations:", len(stations))
    print("contours:", len(contours))

    for _, r in stations.iterrows():
        result = idw_elevation_from_contours(
            station_geom=r.geometry,
            contours_gdf=contours,
        )

        row = {
            "station_id": r.get("station_id", ""),
            "station_name": r.get("station_name", ""),
            "station_lat": r.get("station_lat", np.nan),
            "station_lon": r.get("station_lon", np.nan),
            "dist_to_route_center_km": r.get("dist_to_route_center_km", np.nan),
            "station_quadrant": r.get("station_quadrant", ""),
            **result,
            "contour_shp": str(contour_shp),
            "contour_elevation_field": elevation_field,
        }

        rows.append(row)

    out = pd.DataFrame(rows)

    out = out.sort_values("dist_to_route_center_km").reset_index(drop=True)

    OUT_STATION_ELEVATION_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(
        OUT_STATION_ELEVATION_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    print("\n完成！")
    print("station elevation CSV:", OUT_STATION_ELEVATION_CSV.resolve())

    print("\n=== station elevation from NSLC contours ===")
    show_cols = [
        "station_id",
        "station_name",
        "station_quadrant",
        "dist_to_route_center_km",
        "station_elevation_m",
        "elevation_confidence",
        "n_contours_used",
        "nearest_contour_distance_m",
        "nearest_contour_elevation_m",
        "elevation_search_radius_m",
    ]
    show_cols = [c for c in show_cols if c in out.columns]
    print(out[show_cols].to_string(index=False))


if __name__ == "__main__":
    main()