from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd
import geopandas as gpd
import folium
from shapely.geometry import Point, LineString


"""
ib0c_anchor_from_landmarks.py

目的：
- 從 GPX + OSM landmarks 自動產生 route anchors
- 產生 START / VIA / END 三個 anchor
- 後續供 ib0b_route_mainline_extract.py 使用

Anchor 規則：
1. START：
   GPX 起點附近優先找 trailhead，其次 guidepost，最後 fallback 到 GPX 起點

2. VIA：
   GPX 最高點附近優先找 peak，其次 guidepost，最後 fallback 到 GPX 最高點

3. END：
   GPX 終點附近優先找 trailhead，其次 guidepost，最後 fallback 到 GPX 終點

注意：
- 使用者輸入 GPX 為 lat/lon
- shapely Point 內部仍維持 Point(lon, lat)
"""


# =========================================================
# 0. 路徑設定
# =========================================================

# 專案根目錄
PROJECT_ROOT = Path(r"C:\mountain_work\115_osm")

# =========================================================
# 0-1. Activity / Route 設定
# =========================================================
ROUTE_ID = "juansi_waterfall_fitcsv_20260503"
ROUTE_GROUP = "juansi_waterfall"
ACTIVITY_TYPE = "fit_csv"
ACTIVITY_NAME = "3.csv"

ACTIVITY_ROOT = PROJECT_ROOT / "activity_input"
ACTIVITY_FP = ACTIVITY_ROOT / "csv" / ROUTE_GROUP / ACTIVITY_NAME

# =========================================================
# 0-2. Ia1 dataset metadata
# =========================================================
IA1_VERSION = "v1.2"
IA1_DATASET_ID = "qixing_lengshuikeng_xiaoyoukeng_v1_2_success_20260511"
IA1_SNAPSHOT_TAG = "success_20260511"

IA1_DIR = PROJECT_ROOT / "osm_raw_output" / IA1_DATASET_ID

# =========================================================
# 0-3. 上游 ib0a prune 輸入
# =========================================================
IB0A_STAGE = "ib0a_prune"
IB0A_OUT_DIR = PROJECT_ROOT / "outputs" / IB0A_STAGE / ROUTE_ID
IB0A_PRUNED_FP = IB0A_OUT_DIR / f"{ROUTE_ID}_activity_osm_matched_pruned.geojson"

# =========================================================
# 0-4. ib0c 輸出
# =========================================================
IB0C_STAGE = "ib0c_anchor"
OUT_DIR = PROJECT_ROOT / "outputs" / IB0C_STAGE / ROUTE_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_GEOJSON_FP = OUT_DIR / f"{ROUTE_ID}_route_anchors.geojson"
OUT_CSV_FP = OUT_DIR / f"{ROUTE_ID}_route_anchors_summary.csv"
OUT_HTML_FP = OUT_DIR / f"{ROUTE_ID}_route_anchors_map.html"


# =========================================================
# 1. landmark 檔案路徑
# =========================================================
TRAILHEAD_FP = IA1_DIR / "osm_trailhead_raw.geojson"
PEAK_FP = IA1_DIR / "osm_peak_raw.geojson"
GUIDEPOST_FP = IA1_DIR / "osm_guidepost_raw.geojson"


# =========================================================
# 2. anchor 搜尋半徑設定
# =========================================================
START_TRAILHEAD_RADIUS_M = 200
START_GUIDEPOST_RADIUS_M = 120

END_TRAILHEAD_RADIUS_M = 200
END_GUIDEPOST_RADIUS_M = 120

VIA_PEAK_RADIUS_M = 300
VIA_GUIDEPOST_RADIUS_M = 150


# =========================================================
# 3. 工具函式
# =========================================================
def read_optional_geojson(fp: Path, layer_name: str) -> gpd.GeoDataFrame:
    if not fp.exists():
        print(f"找不到 landmark 檔案，略過：{layer_name} -> {fp}")
        return gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs="EPSG:4326")

    gdf = gpd.read_file(fp)

    if gdf.empty:
        print(f"landmark 空圖層：{layer_name} -> {fp}")
        return gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs="EPSG:4326")

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")

    gdf = gdf.to_crs("EPSG:4326")
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()

    print(f"讀取 landmark：{layer_name} -> {fp}，筆數：{len(gdf)}")
    return gdf

    if gdf.empty:
        print(f"landmark 空圖層：{fp}")
        return gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs="EPSG:4326")

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")

    gdf = gdf.to_crs("EPSG:4326")
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()

    print(f"讀取 landmark：{fp}，筆數：{len(gdf)}")
    return gdf


def parse_gpx_points(gpx_fp: Path) -> gpd.GeoDataFrame:
    if not gpx_fp.exists():
        raise FileNotFoundError(f"找不到 GPX：{gpx_fp}")

    tree = ET.parse(gpx_fp)
    root = tree.getroot()

    if root.tag.startswith("{"):
        uri = root.tag.split("}")[0].strip("{")
        ns = {"gpx": uri}
        trkpt_xpath = ".//gpx:trkpt"
        ele_tag = "gpx:ele"
        time_tag = "gpx:time"
    else:
        ns = {}
        trkpt_xpath = ".//trkpt"
        ele_tag = "ele"
        time_tag = "time"

    rows = []

    for i, trkpt in enumerate(root.findall(trkpt_xpath, ns)):
        lat = float(trkpt.attrib["lat"])
        lon = float(trkpt.attrib["lon"])

        ele_elem = trkpt.find(ele_tag, ns)
        time_elem = trkpt.find(time_tag, ns)

        ele = float(ele_elem.text) if ele_elem is not None and ele_elem.text else None
        t = time_elem.text if time_elem is not None else None

        rows.append({
            "gpx_idx": i,
            "lat": lat,
            "lon": lon,
            "ele_gpx_m": ele,
            "time_raw": t,
            "geometry": Point(lon, lat),
        })

    if len(rows) < 2:
        raise ValueError("GPX 點數不足")

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    return gdf

def parse_fit_csv_points(csv_fp: Path) -> gpd.GeoDataFrame:
    if not csv_fp.exists():
        raise FileNotFoundError(f"找不到 CSV：{csv_fp}")

    df = pd.read_csv(csv_fp, low_memory=False)

    lat_col = "record.position_lat[semicircles]"
    lon_col = "record.position_long[semicircles]"

    if lat_col not in df.columns or lon_col not in df.columns:
        raise ValueError(
            f"CSV 找不到 FIT semicircles 經緯度欄位，目前欄位為：{list(df.columns)}"
        )

    use_cols = [lat_col, lon_col]

    ele_col = None
    for c in [
        "record.enhanced_altitude[m]",
        "record.altitude[m]",
        "record.enhanced_altitude",
        "record.altitude",
    ]:
        if c in df.columns:
            ele_col = c
            use_cols.append(c)
            break

    time_col = None
    for c in [
        "record.timestamp[s]",
        "record.timestamp",
        "timestamp",
        "time",
    ]:
        if c in df.columns:
            time_col = c
            use_cols.append(c)
            break

    df = df[use_cols].copy()
    df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
    df[lon_col] = pd.to_numeric(df[lon_col], errors="coerce")
    df = df.dropna(subset=[lat_col, lon_col])

    semicircle_to_deg = 180 / (2 ** 31)
    df["lat"] = df[lat_col] * semicircle_to_deg
    df["lon"] = df[lon_col] * semicircle_to_deg

    df = df[
        (df["lat"].between(-90, 90)) &
        (df["lon"].between(-180, 180))
    ].copy()

    if ele_col:
        df["ele_gpx_m"] = pd.to_numeric(df[ele_col], errors="coerce")
    else:
        df["ele_gpx_m"] = None

    if time_col:
        df["time_raw"] = df[time_col].astype(str)
    else:
        df["time_raw"] = None

    if len(df) < 2:
        raise ValueError("CSV 有效經緯度點不足，無法建立路線")

    rows = []
    last_xy = None

    for i, row in df.reset_index(drop=True).iterrows():
        lon = float(row["lon"])
        lat = float(row["lat"])
        xy = (lon, lat)

        # 去除連續重複點
        if last_xy is not None and xy == last_xy:
            continue

        last_xy = xy

        rows.append({
            "activity_idx": len(rows),
            "lat": lat,
            "lon": lon,
            "ele_gpx_m": row["ele_gpx_m"],
            "time_raw": row["time_raw"],
            "geometry": Point(lon, lat),
        })

    if len(rows) < 2:
        raise ValueError("CSV 去除重複點後有效點不足")

    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")


def load_activity_points(activity_fp: Path, activity_type: str) -> gpd.GeoDataFrame:
    activity_type = activity_type.lower().strip()

    if activity_type == "gpx":
        return parse_gpx_points(activity_fp)

    if activity_type == "fit_csv":
        return parse_fit_csv_points(activity_fp)

    raise ValueError(f"不支援的 ACTIVITY_TYPE：{activity_type}")


def get_name(row):
    for c in ["name", "name_display", "ref", "description"]:
        if c in row and pd.notna(row[c]):
            return str(row[c])
    return ""


def nearest_landmark(pt_m, landmark_m, max_dist_m: float):
    if landmark_m.empty:
        return None

    dists = landmark_m.geometry.distance(pt_m)
    min_idx = dists.idxmin()
    min_dist = float(dists.loc[min_idx])

    if min_dist <= max_dist_m:
        row = landmark_m.loc[min_idx]
        return {
            "geometry": row.geometry,
            "anchor_name": get_name(row),
            "distance_to_gpx_m": min_dist,
        }

    return None


def make_anchor_row(anchor_role, anchor_source, anchor_name, distance_to_gpx_m, geom_m, ref_geom_m):
    return {
        "anchor_role": anchor_role,
        "anchor_source": anchor_source,
        "anchor_name": anchor_name,
        "distance_to_gpx_m": distance_to_gpx_m,
        "ref_lon": ref_geom_m.x,
        "ref_lat": ref_geom_m.y,
        "geometry": geom_m,
    }


def choose_start_end_anchor(role, ref_pt_m, trailhead_m, guidepost_m):
    if role == "start":
        trail_radius = START_TRAILHEAD_RADIUS_M
        guide_radius = START_GUIDEPOST_RADIUS_M
    else:
        trail_radius = END_TRAILHEAD_RADIUS_M
        guide_radius = END_GUIDEPOST_RADIUS_M

    hit = nearest_landmark(ref_pt_m, trailhead_m, trail_radius)
    if hit is not None:
        return make_anchor_row(
            role,
            "trailhead",
            hit["anchor_name"],
            hit["distance_to_gpx_m"],
            hit["geometry"],
            ref_pt_m,
        )

    hit = nearest_landmark(ref_pt_m, guidepost_m, guide_radius)
    if hit is not None:
        return make_anchor_row(
            role,
            "guidepost",
            hit["anchor_name"],
            hit["distance_to_gpx_m"],
            hit["geometry"],
            ref_pt_m,
        )

    return make_anchor_row(
        role,
        "fallback_gpx_point",
        "",
        0.0,
        ref_pt_m,
        ref_pt_m,
    )


def choose_via_anchor(ref_pt_m, peak_m, guidepost_m):
    hit = nearest_landmark(ref_pt_m, peak_m, VIA_PEAK_RADIUS_M)
    if hit is not None:
        return make_anchor_row(
            "via",
            "peak",
            hit["anchor_name"],
            hit["distance_to_gpx_m"],
            hit["geometry"],
            ref_pt_m,
        )

    hit = nearest_landmark(ref_pt_m, guidepost_m, VIA_GUIDEPOST_RADIUS_M)
    if hit is not None:
        return make_anchor_row(
            "via",
            "guidepost",
            hit["anchor_name"],
            hit["distance_to_gpx_m"],
            hit["geometry"],
            ref_pt_m,
        )

    return make_anchor_row(
        "via",
        "fallback_gpx_peak",
        "",
        0.0,
        ref_pt_m,
        ref_pt_m,
    )


# =========================================================
# 4. 讀 activity points
# =========================================================
activity_points = load_activity_points(ACTIVITY_FP, ACTIVITY_TYPE)

print("活動軌跡載入成功：", ACTIVITY_FP)
print("活動資料類型：", ACTIVITY_TYPE)
print("活動點數：", len(activity_points))

if not IB0A_PRUNED_FP.exists():
    raise FileNotFoundError(f"找不到 ib0a pruned route：{IB0A_PRUNED_FP}")

print("ib0a pruned route input：", IB0A_PRUNED_FP)

metric_crs = activity_points.estimate_utm_crs()
activity_m = activity_points.to_crs(metric_crs)

activity_start_m = activity_m.geometry.iloc[0]
activity_end_m = activity_m.geometry.iloc[-1]

if activity_m["ele_gpx_m"].notna().any():
    peak_idx = activity_m["ele_gpx_m"].idxmax()
    activity_peak_m = activity_m.loc[peak_idx].geometry
    activity_peak_source = "activity_max_elevation"
else:
    peak_idx = len(activity_m) // 2
    activity_peak_m = activity_m.geometry.iloc[peak_idx]
    activity_peak_source = "activity_midpoint_no_elevation"

print("Activity peak source:", activity_peak_source)
print("Activity peak idx:", peak_idx)


# =========================================================
# 5. 讀 OSM landmarks
# =========================================================
trailheads = read_optional_geojson(TRAILHEAD_FP, "trailhead")
peaks = read_optional_geojson(PEAK_FP, "peak")
guideposts = read_optional_geojson(GUIDEPOST_FP, "guidepost")

trailheads_m = trailheads.to_crs(metric_crs) if not trailheads.empty else trailheads
peaks_m = peaks.to_crs(metric_crs) if not peaks.empty else peaks
guideposts_m = guideposts.to_crs(metric_crs) if not guideposts.empty else guideposts


# =========================================================
# 6. 選 anchors
# =========================================================
anchor_rows = []

anchor_rows.append(
    choose_start_end_anchor("start", activity_start_m, trailheads_m, guideposts_m)
)

anchor_rows.append(
    choose_via_anchor(activity_peak_m, peaks_m, guideposts_m)
)

anchor_rows.append(
    choose_start_end_anchor("end", activity_end_m, trailheads_m, guideposts_m)
)

anchors_m = gpd.GeoDataFrame(anchor_rows, geometry="geometry", crs=metric_crs)
anchors = anchors_m.to_crs("EPSG:4326")

# ref_lon/ref_lat 目前是 metric 座標，另轉成 WGS84 ref point
ref_points_m = gpd.GeoSeries(
    [activity_start_m, activity_peak_m, activity_end_m],
    crs=metric_crs,
)
ref_points_wgs = ref_points_m.to_crs("EPSG:4326")

anchors["ref_lon"] = [p.x for p in ref_points_wgs]
anchors["ref_lat"] = [p.y for p in ref_points_wgs]

anchors["anchor_lon"] = anchors.geometry.x
anchors["anchor_lat"] = anchors.geometry.y

# =========================================================
# 6a. metadata
# =========================================================
anchors["pipeline_stage"] = "ib0c_anchor_from_landmarks"
anchors["route_id"] = ROUTE_ID
anchors["route_group"] = ROUTE_GROUP
anchors["activity_type"] = ACTIVITY_TYPE
anchors["activity_source"] = str(ACTIVITY_FP)
anchors["ia1_version"] = IA1_VERSION
anchors["ia1_dataset_id"] = IA1_DATASET_ID
anchors["ia1_snapshot_tag"] = IA1_SNAPSHOT_TAG
anchors["ib0a_input_source"] = str(IB0A_PRUNED_FP)
anchors["landmark_source_dir"] = str(IA1_DIR)
anchors["anchor_rule_version"] = "v1.0"
anchors["activity_peak_source"] = activity_peak_source

# =========================================================
# 7. 輸出
# =========================================================
anchors.to_file(OUT_GEOJSON_FP, driver="GeoJSON")
anchors.drop(columns="geometry").to_csv(OUT_CSV_FP, index=False, encoding="utf-8-sig")

print("\n完成！")
print("Anchor GeoJSON：", OUT_GEOJSON_FP.resolve())
print("Anchor CSV：", OUT_CSV_FP.resolve())

print("\n=== anchors ===")
print(anchors[[
    "anchor_role",
    "anchor_source",
    "anchor_name",
    "distance_to_gpx_m",
    "anchor_lat",
    "anchor_lon",
]])


# =========================================================
# 8. QA 地圖
# =========================================================
activity_line = LineString(list(activity_points.geometry.apply(lambda p: (p.x, p.y))))
center = [activity_points.geometry.y.mean(), activity_points.geometry.x.mean()]

m = folium.Map(
    location=center,
    zoom_start=14,
    tiles="CartoDB positron",
    width="100%",
    height="800px",
)

folium.PolyLine(
    [(lat, lon) for lon, lat in activity_line.coords],
    color="black",
    weight=3,
    opacity=0.8,
    tooltip="Activity route",
).add_to(m)

color_map = {
    "start": "green",
    "via": "blue",
    "end": "red",
}

icon_map = {
    "start": "play",
    "via": "flag",
    "end": "stop",
}

for _, row in anchors.iterrows():
    popup_text = (
        f"role: {row['anchor_role']}\n"
        f"source: {row['anchor_source']}\n"
        f"name: {row['anchor_name']}\n"
        f"distance_to_gpx_m: {row['distance_to_gpx_m']:.2f}\n"
        f"anchor_latlon: {row['anchor_lat']:.6f}, {row['anchor_lon']:.6f}\n"
        f"ref_latlon: {row['ref_lat']:.6f}, {row['ref_lon']:.6f}"
    )

    folium.Marker(
        location=[row.geometry.y, row.geometry.x],
        tooltip=f"{row['anchor_role']} - {row['anchor_source']}",
        popup=folium.Popup(f"<pre>{popup_text}</pre>", max_width=350),
        icon=folium.Icon(
            color=color_map.get(row["anchor_role"], "gray"),
            icon=icon_map.get(row["anchor_role"], "info-sign"),
        )
    ).add_to(m)

folium.LayerControl(collapsed=False).add_to(m)
m.save(OUT_HTML_FP)

print("Anchor QA 地圖：", OUT_HTML_FP.resolve())