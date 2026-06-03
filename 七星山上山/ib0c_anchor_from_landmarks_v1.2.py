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
# 0. Route / Case 設定
# =========================================================
ROUTE_ID = "qixing_lengshuikeng_xiaoyoukeng"
CASE_ID = "qixing_xiaoyoukeng_roundtrip_joyhike"

GPX_DIR = Path("gpx")
GPX_NAME = "七星山 (小油坑進出)_Joyhike.gpx"
GPX_FP = GPX_DIR / GPX_NAME

IA1_DIR = Path("osm_raw_output") / ROUTE_ID

OUT_DIR = Path("ib0c_anchor_output") / CASE_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_GEOJSON_FP = OUT_DIR / f"{CASE_ID}_route_anchors.geojson"
OUT_CSV_FP = OUT_DIR / f"{CASE_ID}_route_anchors.csv"
OUT_HTML_FP = OUT_DIR / f"{CASE_ID}_route_anchors_map.html"


# =========================================================
# 1. landmark 檔案名稱
# =========================================================
TRAILHEAD_NAME = "osm_trailhead_raw.geojson"
PEAK_NAME = "osm_peak_raw.geojson"
GUIDEPOST_NAME = "osm_guidepost_raw.geojson"
LANDMARK_DIR = Path("osm_raw_output/qixing_lengshuikeng_xiaoyoukeng")


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
def find_file(filename: str) -> Path | None:
    """
    優先讀取目前路線的 Ia1 v1.2 輸出資料夾。
    避免 rglob 抓到其他路線，例如大坑資料夾。
    """

    preferred = LANDMARK_DIR / filename
    if preferred.exists():
        return preferred

    # fallback：如果目前路線資料夾沒有，再檢查舊版根目錄輸出
    legacy = Path("osm_raw_output") / filename
    if legacy.exists():
        return legacy

    print(f"找不到目前路線 landmark：{preferred}")
    return None


def read_optional_geojson(filename: str) -> gpd.GeoDataFrame:
    fp = find_file(filename)

    if fp is None:
        print(f"找不到 landmark 檔案，略過：{filename}")
        return gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs="EPSG:4326")

    gdf = gpd.read_file(fp)

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
# 4. 讀 GPX
# =========================================================
gpx_points = parse_gpx_points(GPX_FP)

print("GPX 載入成功：", GPX_FP)
print("GPX 點數：", len(gpx_points))

metric_crs = gpx_points.estimate_utm_crs()
gpx_m = gpx_points.to_crs(metric_crs)

gpx_start_m = gpx_m.geometry.iloc[0]
gpx_end_m = gpx_m.geometry.iloc[-1]

if gpx_m["ele_gpx_m"].notna().any():
    peak_idx = gpx_m["ele_gpx_m"].idxmax()
    gpx_peak_m = gpx_m.loc[peak_idx].geometry
    gpx_peak_source = "gpx_max_elevation"
else:
    peak_idx = len(gpx_m) // 2
    gpx_peak_m = gpx_m.geometry.iloc[peak_idx]
    gpx_peak_source = "gpx_midpoint_no_elevation"

print("GPX peak source:", gpx_peak_source)
print("GPX peak idx:", peak_idx)


# =========================================================
# 5. 讀 OSM landmarks
# =========================================================
trailheads = read_optional_geojson(TRAILHEAD_NAME)
peaks = read_optional_geojson(PEAK_NAME)
guideposts = read_optional_geojson(GUIDEPOST_NAME)

trailheads_m = trailheads.to_crs(metric_crs) if not trailheads.empty else trailheads
peaks_m = peaks.to_crs(metric_crs) if not peaks.empty else peaks
guideposts_m = guideposts.to_crs(metric_crs) if not guideposts.empty else guideposts


# =========================================================
# 6. 選 anchors
# =========================================================
anchor_rows = []

anchor_rows.append(
    choose_start_end_anchor("start", gpx_start_m, trailheads_m, guideposts_m)
)

anchor_rows.append(
    choose_via_anchor(gpx_peak_m, peaks_m, guideposts_m)
)

anchor_rows.append(
    choose_start_end_anchor("end", gpx_end_m, trailheads_m, guideposts_m)
)

anchors_m = gpd.GeoDataFrame(anchor_rows, geometry="geometry", crs=metric_crs)
anchors = anchors_m.to_crs("EPSG:4326")

# ref_lon/ref_lat 目前是 metric 座標，另轉成 WGS84 ref point
ref_points_m = gpd.GeoSeries(
    [gpx_start_m, gpx_peak_m, gpx_end_m],
    crs=metric_crs,
)
ref_points_wgs = ref_points_m.to_crs("EPSG:4326")

anchors["ref_lon"] = [p.x for p in ref_points_wgs]
anchors["ref_lat"] = [p.y for p in ref_points_wgs]

anchors["anchor_lon"] = anchors.geometry.x
anchors["anchor_lat"] = anchors.geometry.y


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
gpx_line = LineString(list(gpx_points.geometry.apply(lambda p: (p.x, p.y))))
center = [gpx_points.geometry.y.mean(), gpx_points.geometry.x.mean()]

m = folium.Map(
    location=center,
    zoom_start=14,
    tiles="CartoDB positron",
    width="100%",
    height="800px",
)

folium.PolyLine(
    [(lat, lon) for lon, lat in gpx_line.coords],
    color="black",
    weight=3,
    opacity=0.8,
    tooltip="GPX route",
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

# ---------------------------------------------------------
# 若 start / end / via 座標重疊，只在 QA 地圖顯示時做微小偏移
# 注意：不改 anchors.geometry，避免影響 ib0b 的真實 anchor 座標
# ---------------------------------------------------------
DISPLAY_OFFSET = {
    "start": (0.000035, -0.000035),  # lat offset, lon offset
    "via":   (0.000000,  0.000000),
    "end":   (-0.000035, 0.000035),
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

    role = row["anchor_role"]
    lat_offset, lon_offset = DISPLAY_OFFSET.get(role, (0.0, 0.0))

    display_lat = row.geometry.y + lat_offset
    display_lon = row.geometry.x + lon_offset

    folium.Marker(
        location=[display_lat, display_lon],
        tooltip=f"{row['anchor_role']} - {row['anchor_source']}",
        popup=folium.Popup(f"<pre>{popup_text}</pre>", max_width=350),
        icon=folium.Icon(
            color=color_map.get(row["anchor_role"], "gray"),
            icon=icon_map.get(row["anchor_role"], "info-sign"),
        )
    ).add_to(m)

    # 顯示偏移線：讓使用者知道 marker 是從真實 anchor 位置偏移出來的
    if lat_offset != 0.0 or lon_offset != 0.0:
        folium.PolyLine(
            locations=[
                [row.geometry.y, row.geometry.x],
                [display_lat, display_lon],
            ],
            color=color_map.get(role, "gray"),
            weight=1,
            opacity=0.7,
            dash_array="3, 3",
            tooltip=f"{role} display offset only",
        ).add_to(m)

folium.LayerControl(collapsed=False).add_to(m)
m.save(OUT_HTML_FP)

print("Anchor QA 地圖：", OUT_HTML_FP.resolve())