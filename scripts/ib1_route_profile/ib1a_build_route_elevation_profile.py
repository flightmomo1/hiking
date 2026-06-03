# =========================================================
# ib1a_build_route_elevation_profile.py
# 建立主路線距離—高程剖面
# 輸入 ib0d trimmed ordered path + ib0b mainline segments + GPX 高程
# 輸出 route profile CSV / GeoJSON / elevation PNG / QA map
# =========================================================

import matplotlib.pyplot as plt
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd
import geopandas as gpd
import folium
from shapely.geometry import Point


# =========================================================
# 0. 路徑設定
# =========================================================
# CASE_ID = "qixing_xiaoyoukeng_roundtrip_joyhike"
# CASE_NAME = "七星山小油坑進出 Joyhike"

CASE_ID = "juansi_waterfall_fitcsv_20260503"
CASE_NAME = "絹絲瀑布 FIT CSV 20260503"
ACTIVITY_TYPE = "fit_csv"
# ib0d v1.1 輸出的 trimmed ordered path

# 注意：
# ORDERED_PATH_FP 才是 ib1a 真正用來建立 route distance axis 的線。
# MAINLINE_FP 只作為 QA map 背景參考，不參與距離軸取樣。

ORDERED_PATH_FP = (
    Path("outputs")
    / "ib0d_trimmed_mainline"
    / CASE_ID
    / f"{CASE_ID}_mainline_ordered_path_trimmed.geojson"
)

MAINLINE_FP = (
    Path("outputs")
    / "ib0b_mainline"
    / CASE_ID
    / f"{CASE_ID}_mainline.geojson"
)

ACTIVITY_CSV_FP = (
    Path("activity_input")
    / "csv"
    / "juansi_waterfall"
    / "3.csv"
)

OUT_DIR = Path("outputs") / "ib1_route_profile" / CASE_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_CSV = OUT_DIR / f"{CASE_ID}_route_profile.csv"
OUT_GEOJSON = OUT_DIR / f"{CASE_ID}_route_profile_points.geojson"
OUT_HTML = OUT_DIR / f"{CASE_ID}_route_profile_map.html"
OUT_PROFILE_PNG = OUT_DIR / f"{CASE_ID}_route_elevation_profile.png"

# =========================================================
# 1. 參數
# =========================================================
SAMPLE_INTERVAL_M = 1.0

# 高程平滑視窗，以公尺定義
SMOOTH_WINDOW_M = 41.0

# QA map 不要每 1 m 都畫 marker，避免 HTML 太大
QA_MARKER_INTERVAL_M = 1.0

# =========================================================
# 2. 工具函式
# =========================================================
def _text_by_localname(elem, localname: str):
    """
    不管 XML namespace，往下搜尋所有子孫節點的 tag localname。
    例如 {namespace}ele、ele、或被包在 extensions 裡的 ele 都可以嘗試抓到。
    """
    for child in elem.iter():
        tag = child.tag
        if "}" in tag:
            tag = tag.split("}", 1)[1]

        if tag == localname:
            if child.text is not None:
                return child.text.strip()

    return None


def parse_gpx_points(gpx_fp: Path) -> gpd.GeoDataFrame:
    tree = ET.parse(gpx_fp)
    root = tree.getroot()

    rows = []

    # 不依賴 namespace，直接找所有 localname = trkpt 的節點
    trkpts = []
    for elem in root.iter():
        tag = elem.tag
        if "}" in tag:
            tag = tag.split("}", 1)[1]
        if tag == "trkpt":
            trkpts.append(elem)

    for i, trkpt in enumerate(trkpts):
        lat = float(trkpt.attrib["lat"])
        lon = float(trkpt.attrib["lon"])

        ele_text = _text_by_localname(trkpt, "ele")
        time_raw = _text_by_localname(trkpt, "time")

        ele = float(ele_text) if ele_text is not None and ele_text != "" else None

        rows.append({
            "gpx_idx": i,
            "lat": lat,
            "lon": lon,
            "ele_gpx_m": ele,
            "time_raw": time_raw,
            "geometry": Point(lon, lat),
        })

    if len(rows) < 2:
        raise ValueError("GPX 點數不足")

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")

    ele_valid_n = gdf["ele_gpx_m"].notna().sum()
    print("GPX elevation valid points:", ele_valid_n, "/", len(gdf))

    if ele_valid_n == 0:
        print("警告：GPX trkpt 沒有 ele，高程欄位將為空。")
        print("後續請使用 NLSC / contour 高程補齊 elevation profile。")

    return gdf

def parse_activity_csv_points(csv_fp: Path) -> gpd.GeoDataFrame:
    """
    讀取活動 CSV，轉成與 GPX parser 相同欄位格式：
    gpx_idx / lat / lon / ele_gpx_m / time_raw / geometry

    支援：
    1. 一般 CSV: lat/lon/elevation/time
    2. FIT CSV: record.position_lat[semicircles] / record.position_long[semicircles]
    """
    if not csv_fp.exists():
        raise FileNotFoundError(f"找不到活動 CSV：{csv_fp.resolve()}")

    df = pd.read_csv(csv_fp, low_memory=False)

    if df.empty:
        raise ValueError(f"活動 CSV 為空：{csv_fp.resolve()}")

    print("CSV 原始欄位數:", len(df.columns))

    # -----------------------------------------------------
    # A. FIT CSV 格式：semicircles
    # -----------------------------------------------------
    fit_lat_col = "record.position_lat[semicircles]"
    fit_lon_col = "record.position_long[semicircles]"

    if fit_lat_col in df.columns and fit_lon_col in df.columns:
        print("偵測到 FIT CSV semicircles 座標欄位")

        small = pd.DataFrame()

        small["lat_raw"] = pd.to_numeric(df[fit_lat_col], errors="coerce")
        small["lon_raw"] = pd.to_numeric(df[fit_lon_col], errors="coerce")

        # FIT semicircles → degrees
        small["lat"] = small["lat_raw"] * 180.0 / (2 ** 31)
        small["lon"] = small["lon_raw"] * 180.0 / (2 ** 31)

        # 高程優先用 enhanced_altitude，再退回 altitude
        if "record.enhanced_altitude[m]" in df.columns:
            small["ele_gpx_m"] = pd.to_numeric(
                df["record.enhanced_altitude[m]"],
                errors="coerce"
            )
        elif "record.altitude[m]" in df.columns:
            small["ele_gpx_m"] = pd.to_numeric(
                df["record.altitude[m]"],
                errors="coerce"
            )
        else:
            small["ele_gpx_m"] = None

        # 時間欄位
        if "record.timestamp[s]" in df.columns:
            small["time_raw"] = df["record.timestamp[s]"]
        elif "timestamp" in df.columns:
            small["time_raw"] = df["timestamp"]
        else:
            small["time_raw"] = None

        df2 = small.dropna(subset=["lat", "lon"]).copy()

    # -----------------------------------------------------
    # B. 一般 CSV 格式：lat/lon
    # -----------------------------------------------------
    else:
        print("未偵測到 FIT semicircles，改用一般 lat/lon 欄位解析")

        rename_map = {}

        for c in df.columns:
            lc = str(c).strip().lower()

            if lc in ["lat", "latitude"]:
                rename_map[c] = "lat"
            elif lc in ["lon", "lng", "longitude"]:
                rename_map[c] = "lon"
            elif lc in ["ele", "elev", "elevation", "alt", "altitude", "height"]:
                rename_map[c] = "ele_gpx_m"
            elif lc in ["time", "timestamp", "datetime", "date_time"]:
                rename_map[c] = "time_raw"

        df = df.rename(columns=rename_map)

        required_cols = ["lat", "lon"]
        missing = [c for c in required_cols if c not in df.columns]

        if missing:
            print("CSV 欄位：", list(df.columns))
            raise ValueError(f"活動 CSV 缺少必要欄位：{missing}")

        if "ele_gpx_m" not in df.columns:
            df["ele_gpx_m"] = None

        if "time_raw" not in df.columns:
            df["time_raw"] = None

        df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
        df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
        df["ele_gpx_m"] = pd.to_numeric(df["ele_gpx_m"], errors="coerce")

        df2 = df.dropna(subset=["lat", "lon"]).copy()

    # -----------------------------------------------------
    # C. 共通檢查與輸出
    # -----------------------------------------------------
    if len(df2) < 2:
        raise ValueError("活動 CSV 有效 GPS 點數不足")

    # 基本座標合理性檢查，避免 semicircles 轉換錯誤
    df2 = df2[
        (df2["lat"].between(-90, 90)) &
        (df2["lon"].between(-180, 180))
    ].copy()

    if len(df2) < 2:
        raise ValueError("活動 CSV 經緯度範圍檢查後有效點數不足")

    df2 = df2.reset_index(drop=True)
    df2["gpx_idx"] = df2.index

    gdf = gpd.GeoDataFrame(
        df2[["gpx_idx", "lat", "lon", "ele_gpx_m", "time_raw"]].copy(),
        geometry=[Point(lon, lat) for lon, lat in zip(df2["lon"], df2["lat"])],
        crs="EPSG:4326",
    )

    ele_valid_n = gdf["ele_gpx_m"].notna().sum()

    print("CSV activity points:", len(gdf))
    print("CSV elevation valid points:", ele_valid_n, "/", len(gdf))
    print("lat range:", round(gdf["lat"].min(), 6), "~", round(gdf["lat"].max(), 6))
    print("lon range:", round(gdf["lon"].min(), 6), "~", round(gdf["lon"].max(), 6))

    if ele_valid_n == 0:
        print("警告：CSV 沒有可用高程欄位，後續需由 NLSC / contour 補齊 elevation profile。")

    return gdf


def nearest_gpx_elevation(sample_pt_m, gpx_m):
    dists = gpx_m.geometry.distance(sample_pt_m)
    idx = dists.idxmin()
    row = gpx_m.loc[idx]

    return {
        "nearest_gpx_idx": int(row["gpx_idx"]),
        "nearest_gpx_dist_m": float(dists.loc[idx]),
        "ele_gpx_m": row["ele_gpx_m"],
        "time_raw": row["time_raw"],
    }


def slope_band(slope_pct):
    if pd.isna(slope_pct):
        return "unknown"

    abs_slope = abs(slope_pct)

    if abs_slope < 3:
        return "flat"
    elif abs_slope < 8:
        return "gentle"
    elif abs_slope < 15:
        return "moderate"
    elif abs_slope < 25:
        return "steep"
    else:
        return "very_steep"


# =========================================================
# 3. 檢查輸入
# =========================================================
if not ORDERED_PATH_FP.exists():
    raise FileNotFoundError(
        f"找不到 ordered path：{ORDERED_PATH_FP.resolve()}，請先執行 ib0d"
    )

if not MAINLINE_FP.exists():
    raise FileNotFoundError(
        f"找不到 mainline segments：{MAINLINE_FP.resolve()}，請先執行 ib0b"
    )

if ACTIVITY_TYPE == "fit_csv":
    if not ACTIVITY_CSV_FP.exists():
        raise FileNotFoundError(f"找不到活動 CSV：{ACTIVITY_CSV_FP.resolve()}")
else:
    raise ValueError(f"目前此測試版只支援 ACTIVITY_TYPE='fit_csv'，目前為：{ACTIVITY_TYPE}")


# =========================================================
# 4. 讀資料
# =========================================================
mainline = gpd.read_file(MAINLINE_FP).to_crs("EPSG:4326")
ordered_path = gpd.read_file(ORDERED_PATH_FP).to_crs("EPSG:4326")
if ACTIVITY_TYPE == "fit_csv":
    gpx = parse_activity_csv_points(ACTIVITY_CSV_FP)
else:
    raise ValueError(f"不支援的 ACTIVITY_TYPE：{ACTIVITY_TYPE}")

if mainline.empty:
    raise ValueError("mainline 為空")

metric_crs = mainline.estimate_utm_crs()
mainline_m = mainline.to_crs(metric_crs)
gpx_m = gpx.to_crs(metric_crs)

print("mainline segments:", len(mainline))
print("GPX points:", len(gpx))
print("metric CRS:", metric_crs)


# =========================================================
# 5. 使用 ordered path（正確順序）
# =========================================================
ordered_path_m = ordered_path.to_crs(metric_crs)

route_line_m = ordered_path_m.geometry.iloc[0]

route_len_m = route_line_m.length
print(f"route length m: {route_len_m:.2f}")


# =========================================================
# 6. 沿主線等距取樣
# =========================================================
sample_rows = []

d = 0.0
sample_idx = 0

while d <= route_len_m:
    pt_m = route_line_m.interpolate(d)
    gpx_info = nearest_gpx_elevation(pt_m, gpx_m)

    sample_rows.append({
        "sample_idx": sample_idx,
        "dist_m": float(d),
        "ele_gpx_m": gpx_info["ele_gpx_m"],
        "nearest_gpx_idx": gpx_info["nearest_gpx_idx"],
        "nearest_gpx_dist_m": gpx_info["nearest_gpx_dist_m"],
        "time_raw": gpx_info["time_raw"],
        "geometry": pt_m,
    })

    d += SAMPLE_INTERVAL_M
    sample_idx += 1

if sample_rows[-1]["dist_m"] < route_len_m:
    pt_m = route_line_m.interpolate(route_len_m)
    gpx_info = nearest_gpx_elevation(pt_m, gpx_m)

    sample_rows.append({
        "sample_idx": sample_idx,
        "dist_m": float(route_len_m),
        "ele_gpx_m": gpx_info["ele_gpx_m"],
        "nearest_gpx_idx": gpx_info["nearest_gpx_idx"],
        "nearest_gpx_dist_m": gpx_info["nearest_gpx_dist_m"],
        "time_raw": gpx_info["time_raw"],
        "geometry": pt_m,
    })

profile_m = gpd.GeoDataFrame(sample_rows, geometry="geometry", crs=metric_crs)

smooth_window_n = max(3, int(round(SMOOTH_WINDOW_M / SAMPLE_INTERVAL_M)))

# rolling window 建議用奇數，center=True 比較對稱
if smooth_window_n % 2 == 0:
    smooth_window_n += 1

print("sample interval m:", SAMPLE_INTERVAL_M)
print("smooth window n:", smooth_window_n)
print("smooth window approx m:", smooth_window_n * SAMPLE_INTERVAL_M)

# =========================================================
# 6b. 高程平滑（rolling median + mean）
# =========================================================

# 先轉 numeric
profile_m["ele_gpx_m"] = pd.to_numeric(profile_m["ele_gpx_m"], errors="coerce")

# median 去除尖峰
profile_m["ele_med"] = profile_m["ele_gpx_m"].rolling(
    window=smooth_window_n, center=True, min_periods=1
).median()

# mean 平滑曲線
profile_m["ele_smooth"] = profile_m["ele_med"].rolling(
    window=smooth_window_n, center=True, min_periods=1
).mean()



# =========================================================
# 7. 計算坡度、累積爬升 / 下降
# =========================================================
# 6b有寫過，可以省略
#profile_m["ele_gpx_m"] = pd.to_numeric(profile_m["ele_gpx_m"], errors="coerce")

profile_m["delta_dist_m"] = profile_m["dist_m"].diff()
#profile_m["delta_ele_m"] = profile_m["ele_gpx_m"].diff()
profile_m["delta_ele_m"] = profile_m["ele_smooth"].diff()

profile_m["slope_pct"] = (
    profile_m["delta_ele_m"] / profile_m["delta_dist_m"] * 100
)

profile_m.loc[profile_m["delta_dist_m"] <= 0, "slope_pct"] = None

profile_m["slope_band"] = profile_m["slope_pct"].apply(slope_band)

profile_m["gain_m"] = profile_m["delta_ele_m"].apply(
    lambda x: x if pd.notna(x) and x > 0 else 0
)

profile_m["loss_m"] = profile_m["delta_ele_m"].apply(
    lambda x: -x if pd.notna(x) and x < 0 else 0
)

profile_m["cum_gain_m"] = profile_m["gain_m"].cumsum()
profile_m["cum_loss_m"] = profile_m["loss_m"].cumsum()


# =========================================================
# 8. 轉回 WGS84 與輸出
# =========================================================
profile = profile_m.to_crs("EPSG:4326")
profile["lat"] = profile.geometry.y
profile["lon"] = profile.geometry.x

has_elevation = profile["ele_gpx_m"].notna().any()
profile["elevation_source"] = "gpx_trkpt_ele" if has_elevation else "none"
profile["needs_nlsc_elevation"] = not has_elevation

profile.to_file(OUT_GEOJSON, driver="GeoJSON")

csv_cols = [
    "sample_idx",
    "dist_m",
    "lat",
    "lon",
    "ele_gpx_m",
    "delta_dist_m",
    "delta_ele_m",
    "slope_pct",
    "slope_band",
    "gain_m",
    "loss_m",
    "cum_gain_m",
    "cum_loss_m",
    "nearest_gpx_idx",
    "nearest_gpx_dist_m",
    "time_raw",
    "ele_smooth",
    "elevation_source",
    "needs_nlsc_elevation",
]

profile[csv_cols].to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

print("\n完成！")
print("profile CSV:", OUT_CSV.resolve())
print("profile GeoJSON:", OUT_GEOJSON.resolve())

has_elevation = profile["ele_gpx_m"].notna().any()

print("\n=== profile summary ===")
print("points:", len(profile))
print("route_len_m:", round(route_len_m, 2))
print("has_gpx_elevation:", has_elevation)

if has_elevation:
    print("cum_gain_m:", round(profile["cum_gain_m"].iloc[-1], 2))
    print("cum_loss_m:", round(profile["cum_loss_m"].iloc[-1], 2))
else:
    print("cum_gain_m: N/A，GPX trkpt 無高程")
    print("cum_loss_m: N/A，GPX trkpt 無高程")
    print("note: 本檔案僅建立 route distance axis；高程需由 NLSC / contour 模組補齊。")

print("\n--- slope_band ---")
print(profile["slope_band"].value_counts(dropna=False))


# =========================================================
# 8b. 輸出距離—海拔示意圖
# =========================================================
plt.figure(figsize=(10, 4))

if has_elevation:
    plt.plot(
        profile["dist_m"],
        profile["ele_gpx_m"],
        linewidth=1,
        label="GPX raw elevation"
    )

    plt.plot(
        profile["dist_m"],
        profile["ele_smooth"],
        linewidth=2,
        label="GPX smoothed elevation"
    )

    plt.ylabel("Elevation (m)")
    plt.title("Qixing Route Elevation Profile")
    plt.legend()
else:
    plt.plot(
        profile["dist_m"],
        [0] * len(profile),
        linewidth=1,
        label="Route distance axis only"
    )

    plt.ylabel("Elevation unavailable")
    plt.title("Qixing Route Distance Axis - GPX trkpt has no elevation")
    plt.legend()

plt.xlabel("Distance (m)")
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(OUT_PROFILE_PNG, dpi=200)
plt.close()

print("profile PNG:", OUT_PROFILE_PNG.resolve())


# =========================================================
# 9. QA 地圖
# =========================================================
center = [profile.geometry.y.mean(), profile.geometry.x.mean()]

m = folium.Map(
    location=center,
    zoom_start=14,
    tiles="CartoDB positron",
    width="100%",
    height="800px",
)

# ib0b mainline segments：僅作背景參考，避免誤認為正式取樣線
folium.GeoJson(
    mainline,
    name="ib0b mainline segments reference",
    style_function=lambda feat: {
        "color": "gray",
        "weight": 3,
        "opacity": 0.35,
    },
).add_to(m)

# ib0d trimmed ordered path：ib1a 真正使用的正式取樣線
folium.GeoJson(
    ordered_path,
    name="ib0d trimmed ordered path used by ib1a",
    style_function=lambda feat: {
        "color": "black",
        "weight": 4,
        "opacity": 0.9,
    },
).add_to(m)

# profile points：QA map 只每 QA_MARKER_INTERVAL_M 畫一點，避免 HTML 太大
profile_qa = profile[
    (profile["dist_m"] % QA_MARKER_INTERVAL_M < SAMPLE_INTERVAL_M)
    | (profile["sample_idx"] == 0)
    | (profile["sample_idx"] == profile["sample_idx"].max())
].copy()

print("QA marker points:", len(profile_qa))

for _, row in profile_qa.iterrows():
    slope_val = row["slope_pct"]
    slope_text = "nan" if pd.isna(slope_val) else f"{slope_val:.2f}"

    if has_elevation:
        cum_gain_text = f"{row['cum_gain_m']:.1f}"
        cum_loss_text = f"{row['cum_loss_m']:.1f}"
    else:
        cum_gain_text = "N/A"
        cum_loss_text = "N/A"

    popup = (
        f"<pre>"
        f"idx: {row['sample_idx']}\n"
        f"dist_m: {row['dist_m']:.1f}\n"
        f"ele_gpx_m: {row['ele_gpx_m']}\n"
        f"slope_pct: {slope_text}\n"
        f"slope_band: {row['slope_band']}\n"
        f"cum_gain_m: {cum_gain_text}\n"
        f"cum_loss_m: {cum_loss_text}\n"
        f"nearest_gpx_dist_m: {row['nearest_gpx_dist_m']:.1f}"
        f"</pre>"
    )

    folium.CircleMarker(
        location=[row.geometry.y, row.geometry.x],
        radius=3,
        color="blue",
        fill=True,
        fill_opacity=0.7,
        popup=folium.Popup(popup, max_width=300),
    ).add_to(m)

folium.LayerControl(collapsed=False).add_to(m)
m.save(OUT_HTML)

print("QA map:", OUT_HTML.resolve())