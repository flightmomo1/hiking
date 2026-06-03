# -*- coding: utf-8 -*-
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# =========================================================
# A. Matplotlib font settings
# =========================================================

def setup_chinese_font():
    preferred_keywords = [
        "Arial Unicode",
        "PingFang",
        "Heiti",
        "STHeiti",
        "Songti",
        "Noto Sans CJK",
        "Noto Serif CJK",
        "Microsoft JhengHei",
        "Microsoft YaHei",
        "SimHei",
    ]

    available_fonts = fm.fontManager.ttflist

    for keyword in preferred_keywords:
        for font in available_fonts:
            if keyword.lower() in font.name.lower():
                matplotlib.rcParams["font.family"] = [font.name]
                matplotlib.rcParams["axes.unicode_minus"] = False
                print(f"使用中文字型：{font.name}")
                return font.name

    matplotlib.rcParams["font.family"] = ["DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False
    print("警告：找不到中文字型，暫用 DejaVu Sans，中文可能無法正常顯示。")
    return "DejaVu Sans"


setup_chinese_font()


# =========================================================
# B. Paths
# =========================================================
BASE_DIR = Path("/Users/iddmini/Documents/115_Motion改造/FY115_登山/115_osm")

GPX_PATH = Path(
    "/Users/iddmini/Documents/115_Motion改造/FY115_登山/gpx/"
    "冷水坑上-七星山東峰-主峰-下小油坑.gpx"
)

ENV_DIR = BASE_DIR / "ib3_environment_output"

WEATHER_SUMMARY_CSV = ENV_DIR / "qixing_weather_summary_by_station.csv"
WATER_SUMMARY_CSV = ENV_DIR / "qixing_water_summary_by_station.csv"

OUT_DIR = ENV_DIR
OUT_PNG_FULL = OUT_DIR / "qixing_environment_station_matching_map_full.png"
OUT_PNG_BRIEF = OUT_DIR / "qixing_environment_station_matching_map_brief.png"


# =========================================================
# C. Station coordinate fallback
# =========================================================
# 優先順序：
# 1. 使用 summary CSV 內的 lat/lon 或 latitude/longitude 欄位
# 2. 若 CSV 沒有座標，使用下列 fallback
#
# 注意：
# 這裡的座標若為暫填，正式簡報或報告前建議改由
# weather_observations / water_level_observations / station metadata 自動帶入。
STATION_COORDS_FALLBACK = {
    # -----------------------------------------------------
    # Weather stations
    # -----------------------------------------------------
    "466930": (25.1621, 121.5446),  # 陽明山，暫填；請以資料庫站點座標為準
    "466910": (25.1826, 121.5297),  # 鞍部，暫填
    "C0AC40": (25.1750, 121.5220),  # 大屯山，暫填
    "A0A460": (25.1370, 121.5400),  # 文化大學，暫填
    "C0AH40": (25.1300, 121.5650),  # 平等，暫填

    # -----------------------------------------------------
    # Hydro stations
    # -----------------------------------------------------
    # 若 qixing_water_summary_by_station.csv 已有 latitude/longitude，
    # 下列可不補。
    #
    # 若跑圖時出現「缺少經緯度」，再把實際座標補進來。
    #
    # "1140H179": (lat, lon),  # 磺溪橋_北
    # "1140H180": (lat, lon),  # 中和橋_北
    # "1140H175": (lat, lon),  # 薇閣_北
    # "1140H162": (lat, lon),  # 三和橋
    # "1010H006": (lat, lon),  # 新磺溪橋(即時)
}

# =========================================================
# C2. Plot display settings
# =========================================================
MAX_LABEL_WEATHER_BRIEF = 5
MAX_LABEL_WATER_BRIEF = 3

# brief 版：全部測站都畫點，但只標示距離最近的幾個站，避免圖面太擠
ENABLE_BRIEF_LABEL_LIMIT = True



# =========================================================
# D. Utility
# =========================================================
def ensure_exists(fp: Path):
    if not fp.exists():
        raise FileNotFoundError(f"找不到檔案：{fp.resolve()}")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    return out


def read_gpx_points(gpx_path: Path) -> pd.DataFrame:
    """
    Read GPX track points and return DataFrame with lat/lon.
    Supports GPX with namespace and simple GPX without namespace.
    """
    ensure_exists(gpx_path)

    tree = ET.parse(gpx_path)
    root = tree.getroot()

    pts = []

    # GPX 1.1 namespace
    ns = {"gpx": "http://www.topografix.com/GPX/1/1"}

    for trkpt in root.findall(".//gpx:trkpt", ns):
        lat = float(trkpt.attrib["lat"])
        lon = float(trkpt.attrib["lon"])
        pts.append((lat, lon))

    # fallback: GPX without namespace
    if not pts:
        for trkpt in root.findall(".//trkpt"):
            lat = float(trkpt.attrib["lat"])
            lon = float(trkpt.attrib["lon"])
            pts.append((lat, lon))

    if not pts:
        raise ValueError(f"GPX 中找不到 trkpt：{gpx_path}")

    return pd.DataFrame(pts, columns=["lat", "lon"])


def find_coord_columns(df: pd.DataFrame):
    """
    Try to find latitude / longitude columns.
    """
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

    return lat_col, lon_col


def attach_station_coords(df: pd.DataFrame, label: str) -> pd.DataFrame:
    """
    Attach lat/lon to station summary DataFrame.
    If lat/lon columns exist, use them.
    Otherwise fallback to STATION_COORDS_FALLBACK by station_id.
    """
    df = normalize_columns(df)

    lat_col, lon_col = find_coord_columns(df)

    # Case 1: CSV already has coordinates
    if lat_col and lon_col:
        df["lat"] = pd.to_numeric(df[lat_col], errors="coerce")
        df["lon"] = pd.to_numeric(df[lon_col], errors="coerce")
        return df.dropna(subset=["lat", "lon"]).copy()

    # Case 2: fallback by station_id
    if "station_id" not in df.columns:
        raise ValueError(f"{label} CSV 找不到 station_id 欄位，無法對應測站座標。")

    lats = []
    lons = []
    missing = []

    for sid in df["station_id"].astype(str):
        if sid in STATION_COORDS_FALLBACK:
            lat, lon = STATION_COORDS_FALLBACK[sid]
            lats.append(lat)
            lons.append(lon)
        else:
            lats.append(None)
            lons.append(None)
            missing.append(sid)

    df["lat"] = lats
    df["lon"] = lons

    if missing:
        print(f"\n[{label}] 以下測站缺少經緯度，將不繪製：")
        for sid in sorted(set(missing)):
            print(" -", sid)

    return df.dropna(subset=["lat", "lon"]).copy()


def station_label(row) -> str:
    """
    Build station annotation label.
    """
    name = str(row.get("station_name", "")).strip()
    sid = str(row.get("station_id", "")).strip()

    if name and sid:
        label = f"{name}{sid}"
    elif sid:
        label = sid
    else:
        label = name

    if "dist_to_route_center_km" in row and pd.notna(row["dist_to_route_center_km"]):
        label += f'{float(row["dist_to_route_center_km"]):.1f} km'

    return label


# =========================================================
# E. Plot
# =========================================================
def plot_station_matching_map(
    route: pd.DataFrame,
    weather: pd.DataFrame,
    water: pd.DataFrame,
    out_png: Path,
    mode: str = "full",
):
    fig, ax = plt.subplots(figsize=(11, 8))

    # -----------------------------------------------------
    # GPX route
    # -----------------------------------------------------
    ax.plot(
        route["lon"],
        route["lat"],
        linewidth=3,
        label="GPX 路線",
    )

    # -----------------------------------------------------
    # Route center
    # -----------------------------------------------------
    center_lat = route["lat"].mean()
    center_lon = route["lon"].mean()

    ax.scatter(
        center_lon,
        center_lat,
        marker="x",
        s=140,
        linewidths=2.5,
        label="路線中心",
    )

    ax.annotate(
        "路線中心",
        (center_lon, center_lat),
        xytext=(8, 8),
        textcoords="offset points",
        fontsize=10,
        fontweight="bold",
    )

    # -----------------------------------------------------
    # Weather stations
    # -----------------------------------------------------
    if not weather.empty:
        ax.scatter(
            weather["lon"],
            weather["lat"],
            marker="o",
            s=95,
            label="氣象站",
        )

        weather_to_label = weather.copy()

        if mode == "brief" and ENABLE_BRIEF_LABEL_LIMIT:
            if "dist_to_route_center_km" in weather_to_label.columns:
                weather_to_label = (
                    weather_to_label
                    .sort_values("dist_to_route_center_km")
                    .head(MAX_LABEL_WEATHER_BRIEF)
                )

        for _, r in weather_to_label.iterrows():
            ax.annotate(
                station_label(r),
                (r["lon"], r["lat"]),
                xytext=(7, 7),
                textcoords="offset points",
                fontsize=9 if mode == "full" else 8,
            )

    # -----------------------------------------------------
    # Hydro stations
    # -----------------------------------------------------
    if not water.empty:
        ax.scatter(
            water["lon"],
            water["lat"],
            marker="^",
            s=95,
            label="水文站",
        )

        water_to_label = water.copy()

        if mode == "brief" and ENABLE_BRIEF_LABEL_LIMIT:
            if "dist_to_route_center_km" in water_to_label.columns:
                water_to_label = (
                    water_to_label
                    .sort_values("dist_to_route_center_km")
                    .head(MAX_LABEL_WATER_BRIEF)
                )

        for _, r in water_to_label.iterrows():
            ax.annotate(
                station_label(r),
                (r["lon"], r["lat"]),
                xytext=(7, -24),
                textcoords="offset points",
                fontsize=9 if mode == "full" else 8,
            )

    # -----------------------------------------------------
    # Axis / style
    # -----------------------------------------------------
    if mode == "brief":
        title = "GPX 路線周邊主要氣象／水文測站"
    else:
        title = "七星山 GPX 路線與氣象／水文測站對應（完整測站版）"

    ax.set_title(
        title,
        fontsize=16,
        fontweight="bold",
        pad=16,
    )

    ax.set_xlabel("經度 Longitude")
    ax.set_ylabel("緯度 Latitude")
    ax.grid(True, alpha=0.3)
    ax.set_aspect("equal")
    ax.legend(loc="best")

    # -----------------------------------------------------
    # Auto zoom
    # -----------------------------------------------------
    lon_series = [route["lon"]]
    lat_series = [route["lat"]]

    if not weather.empty:
        lon_series.append(weather["lon"])
        lat_series.append(weather["lat"])

    if not water.empty:
        lon_series.append(water["lon"])
        lat_series.append(water["lat"])

    all_lon = pd.concat(lon_series)
    all_lat = pd.concat(lat_series)

    pad_lon = (all_lon.max() - all_lon.min()) * 0.15
    pad_lat = (all_lat.max() - all_lat.min()) * 0.15

    if pad_lon == 0:
        pad_lon = 0.01
    if pad_lat == 0:
        pad_lat = 0.01

    ax.set_xlim(all_lon.min() - pad_lon, all_lon.max() + pad_lon)
    ax.set_ylim(all_lat.min() - pad_lat, all_lat.max() + pad_lat)

    fig.tight_layout()
    fig.savefig(out_png, dpi=300)
    plt.close(fig)


# =========================================================
# F. Main
# =========================================================
def main():
    ensure_exists(GPX_PATH)
    ensure_exists(WEATHER_SUMMARY_CSV)
    ensure_exists(WATER_SUMMARY_CSV)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("GPX:", GPX_PATH.resolve())
    print("weather summary:", WEATHER_SUMMARY_CSV.resolve())
    print("water summary:", WATER_SUMMARY_CSV.resolve())

    route = read_gpx_points(GPX_PATH)

    weather_raw = pd.read_csv(WEATHER_SUMMARY_CSV)
    water_raw = pd.read_csv(WATER_SUMMARY_CSV)

    weather = attach_station_coords(weather_raw, label="weather")
    water = attach_station_coords(water_raw, label="water")

    print("\n=== route ===")
    print(f"points: {len(route)}")
    print(f"lat range: {route['lat'].min():.6f} ~ {route['lat'].max():.6f}")
    print(f"lon range: {route['lon'].min():.6f} ~ {route['lon'].max():.6f}")

    print("\n=== weather stations plotted ===")
    if weather.empty:
        print("(none)")
    else:
        cols = [
            "station_id",
            "station_name",
            "lat",
            "lon",
            "dist_to_route_center_km",
        ]
        cols = [c for c in cols if c in weather.columns]
        print(weather[cols].to_string(index=False))

    print("\n=== hydro stations plotted ===")
    if water.empty:
        print("(none)")
    else:
        cols = [
            "station_id",
            "station_name",
            "river_name",
            "lat",
            "lon",
            "dist_to_route_center_km",
        ]
        cols = [c for c in cols if c in water.columns]
        print(water[cols].to_string(index=False))

    plot_station_matching_map(
        route=route,
        weather=weather,
        water=water,
        out_png=OUT_PNG_FULL,
        mode="full",
    )

    plot_station_matching_map(
        route=route,
        weather=weather,
        water=water,
        out_png=OUT_PNG_BRIEF,
        mode="brief",
    )

    print("\n完成！")
    print("full PNG:", OUT_PNG_FULL.resolve())
    print("brief PNG:", OUT_PNG_BRIEF.resolve())


if __name__ == "__main__":
    main()