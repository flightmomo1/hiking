# =========================================================
# activity_loader.py
#
# 目的：
# - 統一讀取 GPX / FIT CSV / generic CSV 活動資料
# - 輸出標準化 GeoDataFrame
#
# 標準欄位：
# activity_idx
# lat
# lon
# ele_m
# time_raw
# distance_m
# speed_mps
# heart_rate_bpm
# cadence_rpm
# source_type
# geometry
# =========================================================

from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point


# =========================================================
# 工具函式
# =========================================================
def _norm_col_name(c) -> str:
    return str(c).strip().lower()


def _to_numeric_series(s):
    return pd.to_numeric(s, errors="coerce")


def _empty_optional_cols(df: pd.DataFrame) -> pd.DataFrame:
    optional_cols = [
        "ele_m",
        "time_raw",
        "distance_m",
        "speed_mps",
        "heart_rate_bpm",
        "cadence_rpm",
    ]

    for c in optional_cols:
        if c not in df.columns:
            df[c] = pd.NA

    return df


def _to_activity_gdf(df: pd.DataFrame, source_type: str) -> gpd.GeoDataFrame:
    required = ["lat", "lon"]

    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"活動資料缺少必要欄位：{missing}")

    df = _empty_optional_cols(df)

    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df["ele_m"] = pd.to_numeric(df["ele_m"], errors="coerce")
    df["distance_m"] = pd.to_numeric(df["distance_m"], errors="coerce")
    df["speed_mps"] = pd.to_numeric(df["speed_mps"], errors="coerce")
    df["heart_rate_bpm"] = pd.to_numeric(df["heart_rate_bpm"], errors="coerce")
    df["cadence_rpm"] = pd.to_numeric(df["cadence_rpm"], errors="coerce")

    df = df.dropna(subset=["lat", "lon"]).copy()

    # 基本經緯度範圍檢查
    df = df[
        (df["lat"].between(-90, 90))
        & (df["lon"].between(-180, 180))
    ].copy()

    if len(df) < 2:
        raise ValueError("活動資料有效 GPS 點數不足")

    df = df.reset_index(drop=True)
    df["activity_idx"] = df.index
    df["source_type"] = source_type

    gdf = gpd.GeoDataFrame(
        df[
            [
                "activity_idx",
                "lat",
                "lon",
                "ele_m",
                "time_raw",
                "distance_m",
                "speed_mps",
                "heart_rate_bpm",
                "cadence_rpm",
                "source_type",
            ]
        ].copy(),
        geometry=[Point(lon, lat) for lon, lat in zip(df["lon"], df["lat"])],
        crs="EPSG:4326",
    )

    return gdf


# =========================================================
# GPX parser
# =========================================================
def load_gpx_points(gpx_fp: Path) -> gpd.GeoDataFrame:
    if not gpx_fp.exists():
        raise FileNotFoundError(f"找不到 GPX：{gpx_fp.resolve()}")

    ns = {
        "gpx": "http://www.topografix.com/GPX/1/1",
    }

    tree = ET.parse(gpx_fp)
    root = tree.getroot()

    rows = []

    # 同時支援有 namespace / 無 namespace
    trkpts = root.findall(".//gpx:trkpt", ns)
    if not trkpts:
        trkpts = root.findall(".//trkpt")

    for i, pt in enumerate(trkpts):
        lat = pt.attrib.get("lat")
        lon = pt.attrib.get("lon")

        ele_node = pt.find("gpx:ele", ns)
        if ele_node is None:
            ele_node = pt.find("ele")

        time_node = pt.find("gpx:time", ns)
        if time_node is None:
            time_node = pt.find("time")

        rows.append({
            "lat": lat,
            "lon": lon,
            "ele_m": ele_node.text if ele_node is not None else pd.NA,
            "time_raw": time_node.text if time_node is not None else pd.NA,
            "distance_m": pd.NA,
            "speed_mps": pd.NA,
            "heart_rate_bpm": pd.NA,
            "cadence_rpm": pd.NA,
        })

    df = pd.DataFrame(rows)

    gdf = _to_activity_gdf(df, source_type="gpx")

    print("GPX activity points:", len(gdf))
    print("GPX elevation valid points:", gdf["ele_m"].notna().sum(), "/", len(gdf))

    return gdf


# =========================================================
# FIT CSV parser：Garmin semicircles
# =========================================================
def load_fit_csv_points(csv_fp: Path) -> gpd.GeoDataFrame:
    if not csv_fp.exists():
        raise FileNotFoundError(f"找不到 FIT CSV：{csv_fp.resolve()}")

    df = pd.read_csv(csv_fp, low_memory=False)

    if df.empty:
        raise ValueError(f"FIT CSV 為空：{csv_fp.resolve()}")

    fit_lat_col = "record.position_lat[semicircles]"
    fit_lon_col = "record.position_long[semicircles]"

    if fit_lat_col not in df.columns or fit_lon_col not in df.columns:
        raise ValueError(
            "未偵測到 FIT CSV semicircles 欄位："
            f"{fit_lat_col}, {fit_lon_col}"
        )

    out = pd.DataFrame()

    lat_raw = pd.to_numeric(df[fit_lat_col], errors="coerce")
    lon_raw = pd.to_numeric(df[fit_lon_col], errors="coerce")

    out["lat"] = lat_raw * 180.0 / (2 ** 31)
    out["lon"] = lon_raw * 180.0 / (2 ** 31)

    if "record.enhanced_altitude[m]" in df.columns:
        out["ele_m"] = pd.to_numeric(df["record.enhanced_altitude[m]"], errors="coerce")
    elif "record.altitude[m]" in df.columns:
        out["ele_m"] = pd.to_numeric(df["record.altitude[m]"], errors="coerce")
    else:
        out["ele_m"] = pd.NA

    if "record.timestamp[s]" in df.columns:
        out["time_raw"] = df["record.timestamp[s]"]
    elif "timestamp" in df.columns:
        out["time_raw"] = df["timestamp"]
    else:
        out["time_raw"] = pd.NA

    if "record.distance[m]" in df.columns:
        out["distance_m"] = pd.to_numeric(df["record.distance[m]"], errors="coerce")
    else:
        out["distance_m"] = pd.NA

    if "record.enhanced_speed[m/s]" in df.columns:
        out["speed_mps"] = pd.to_numeric(df["record.enhanced_speed[m/s]"], errors="coerce")
    elif "record.speed[m/s]" in df.columns:
        out["speed_mps"] = pd.to_numeric(df["record.speed[m/s]"], errors="coerce")
    else:
        out["speed_mps"] = pd.NA

    if "record.heart_rate[bpm]" in df.columns:
        out["heart_rate_bpm"] = pd.to_numeric(df["record.heart_rate[bpm]"], errors="coerce")
    else:
        out["heart_rate_bpm"] = pd.NA

    if "record.cadence[rpm]" in df.columns:
        out["cadence_rpm"] = pd.to_numeric(df["record.cadence[rpm]"], errors="coerce")
    else:
        out["cadence_rpm"] = pd.NA

    gdf = _to_activity_gdf(out, source_type="fit_csv")

    print("FIT CSV activity points:", len(gdf))
    print("FIT CSV elevation valid points:", gdf["ele_m"].notna().sum(), "/", len(gdf))
    print("lat range:", round(gdf["lat"].min(), 6), "~", round(gdf["lat"].max(), 6))
    print("lon range:", round(gdf["lon"].min(), 6), "~", round(gdf["lon"].max(), 6))

    return gdf


# =========================================================
# Generic CSV parser：一般 lat/lon CSV
# =========================================================
def load_generic_csv_points(csv_fp: Path) -> gpd.GeoDataFrame:
    if not csv_fp.exists():
        raise FileNotFoundError(f"找不到 CSV：{csv_fp.resolve()}")

    df = pd.read_csv(csv_fp, low_memory=False)

    if df.empty:
        raise ValueError(f"CSV 為空：{csv_fp.resolve()}")

    rename_map = {}

    for c in df.columns:
        lc = _norm_col_name(c)

        if lc in ["lat", "latitude"]:
            rename_map[c] = "lat"
        elif lc in ["lon", "lng", "longitude"]:
            rename_map[c] = "lon"
        elif lc in ["ele", "elev", "elevation", "alt", "altitude", "height"]:
            rename_map[c] = "ele_m"
        elif lc in ["time", "timestamp", "datetime", "date_time"]:
            rename_map[c] = "time_raw"
        elif lc in ["distance", "distance_m", "dist_m"]:
            rename_map[c] = "distance_m"
        elif lc in ["speed", "speed_mps", "speed_m/s"]:
            rename_map[c] = "speed_mps"
        elif lc in ["heart_rate", "hr", "heart_rate_bpm"]:
            rename_map[c] = "heart_rate_bpm"
        elif lc in ["cadence", "cadence_rpm"]:
            rename_map[c] = "cadence_rpm"

    out = df.rename(columns=rename_map).copy()

    gdf = _to_activity_gdf(out, source_type="csv")

    print("Generic CSV activity points:", len(gdf))
    print("Generic CSV elevation valid points:", gdf["ele_m"].notna().sum(), "/", len(gdf))

    return gdf


# =========================================================
# Public API
# =========================================================
def load_activity_points(activity_fp, activity_type: str = "auto") -> gpd.GeoDataFrame:
    """
    統一活動資料入口。

    activity_type:
    - auto
    - gpx
    - fit_csv
    - csv
    """
    fp = Path(activity_fp)

    if activity_type is None:
        activity_type = "auto"

    activity_type = str(activity_type).lower().strip()

    if activity_type == "auto":
        suffix = fp.suffix.lower()

        if suffix == ".gpx":
            activity_type = "gpx"
        elif suffix == ".csv":
            # 先嘗試 FIT CSV，再退回 generic CSV
            try:
                return load_fit_csv_points(fp)
            except Exception as e:
                print(f"FIT CSV parser failed, fallback to generic CSV: {e}")
                return load_generic_csv_points(fp)
        else:
            raise ValueError(f"auto 模式不支援此副檔名：{suffix}")

    if activity_type == "gpx":
        return load_gpx_points(fp)

    if activity_type in ["fit_csv", "fitcsv"]:
        return load_fit_csv_points(fp)

    if activity_type == "csv":
        return load_generic_csv_points(fp)

    raise ValueError(f"不支援的 activity_type：{activity_type}")


if __name__ == "__main__":
    print("activity_loader.py is a shared module. Import load_activity_points() from scripts.")