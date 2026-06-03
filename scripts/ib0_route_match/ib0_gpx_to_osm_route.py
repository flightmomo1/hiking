from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import geopandas as gpd
import osmnx as ox
import folium
from shapely.geometry import LineString


"""
ib0_gpx_to_osm_route.py

定位：
- 讀取已知 GPX 路線
- 從 OSM 中找出最可能對應的路段集合
- 輸出 matched OSM route，作為後續切段與高程分析的主體

主要功能：
1. 讀取 GPX 並建立 route geometry
2. 抓取 GPX 附近的 OSM 路網
3. 以距離、重疊比例、highway 語意進行初步 matching
4. 輸出 matched GeoJSON 與 QA 地圖

注意：
- 本版為 rule-based 初版，不是完整 graph-based map matching
- 後續可再加入連續性與圖論修正
"""


# =========================================================
# 0. 路徑設定
# =========================================================
GPX_DIR = Path("/Users/iddmini/Documents/115_Motion改造/FY115_登山/gpx")
GPX_NAME = "冷水坑上-七星山東峰-主峰-下小油坑.gpx"
GPX_FP = GPX_DIR / GPX_NAME

OUT_DIR = Path("ib0_gpx_osm_match_output")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CANDIDATE_GEOJSON_FP = OUT_DIR / "qixing_gpx_osm_candidates.geojson"
MATCHED_GEOJSON_FP = OUT_DIR / "qixing_gpx_osm_matched.geojson"
QA_HTML_FP = OUT_DIR / "qixing_gpx_osm_matched_map.html"
SUMMARY_CSV_FP = OUT_DIR / "qixing_gpx_osm_match_summary.csv"


# =========================================================
# 1. 參數設定
# =========================================================
GPX_BUFFER_FETCH_M = 60
GPX_BUFFER_MATCH_M = 30
MAX_DISTANCE_M = 20
MIN_OVERLAP_RATIO = 0.30
MATCH_SCORE_THRESHOLD = 0.55

# 放寬候選集：先保留較多可能路型，再交給 GPX 距離與重疊判斷
ALLOWED_HIGHWAY = [
    # trail core
    "path",
    "footway",
    "steps",
    "track",
    "pedestrian",
    # approach / road
    "service",
    "unclassified",
    "residential",
    "living_street",
    "road",
    "tertiary",
    "tertiary_link",
]

SEMANTIC_SCORE_MAP = {
    # trail core
    "path": 1.00,
    "steps": 0.95,
    "footway": 0.85,
    "track": 0.75,
    "pedestrian": 0.60,
    # approach / road
    "service": 0.45,
    "unclassified": 0.40,
    "residential": 0.35,
    "living_street": 0.35,
    "road": 0.30,
    "tertiary": 0.25,
    "tertiary_link": 0.20,
}


# =========================================================
# 2. 工具函式
# =========================================================
def parse_gpx_track(gpx_fp: Path) -> LineString:
    """
    解析 GPX，將所有 trkpt 串成一條 LineString。
    假設此 GPX 主要只有一條主路線。
    """
    if not gpx_fp.exists():
        raise FileNotFoundError(f"找不到 GPX：{gpx_fp}")

    tree = ET.parse(gpx_fp)
    root = tree.getroot()

    ns = {}
    if root.tag.startswith("{"):
        uri = root.tag.split("}")[0].strip("{")
        ns = {"gpx": uri}
        trkpt_xpath = ".//gpx:trkpt"
    else:
        trkpt_xpath = ".//trkpt"

    pts = []
    for trkpt in root.findall(trkpt_xpath, ns):
        lat = float(trkpt.attrib["lat"])
        lon = float(trkpt.attrib["lon"])
        pts.append((lon, lat))

    if len(pts) < 2:
        raise ValueError("GPX 軌跡點不足，無法建立路線")

    return LineString(pts)


def normalize_highway_value(v):
    if isinstance(v, list):
        return v[0] if len(v) > 0 else None
    return v


def get_semantic_score(highway_value):
    hw = normalize_highway_value(highway_value)
    return SEMANTIC_SCORE_MAP.get(hw, 0.10)


def classify_route_role(hw):
    hw = normalize_highway_value(hw)

    if hw in {"path", "footway", "steps", "track", "pedestrian"}:
        return "trail_core"
    elif hw in {"service", "unclassified", "residential", "living_street", "road", "tertiary", "tertiary_link"}:
        return "approach_or_road"
    else:
        return "other"


def get_center_latlon(line_wgs84: LineString):
    centroid = line_wgs84.centroid
    return centroid.y, centroid.x


def classify_selected(row):
    cond1 = row["distance_to_gpx_m"] <= MAX_DISTANCE_M
    cond2 = row["overlap_ratio"] >= MIN_OVERLAP_RATIO
    cond3 = row["match_score"] >= MATCH_SCORE_THRESHOLD
    return int((cond1 and cond2) or cond3)


# =========================================================
# 3. 讀取 GPX
# =========================================================
gpx_line = parse_gpx_track(GPX_FP)
gpx_gdf = gpd.GeoDataFrame(
    [{"route_name": GPX_NAME, "geometry": gpx_line}],
    geometry="geometry",
    crs="EPSG:4326",
)

print("GPX 載入成功：", GPX_FP)
print("GPX 點數（近似）：", len(list(gpx_line.coords)))

center_lat, center_lon = get_center_latlon(gpx_line)

metric_crs = gpx_gdf.estimate_utm_crs()
gpx_gdf_m = gpx_gdf.to_crs(metric_crs)
gpx_line_m = gpx_gdf_m.geometry.iloc[0]
gpx_buffer_fetch = gpx_line_m.buffer(GPX_BUFFER_FETCH_M)
gpx_buffer_match = gpx_line_m.buffer(GPX_BUFFER_MATCH_M)


# =========================================================
# 4. 抓 OSM 候選路段
# =========================================================
tags = {"highway": True}

print("從 OSM 下載候選路段中...")
gdf_osm = ox.features_from_point(
    (center_lat, center_lon),
    tags=tags,
    dist=2500,
)

if gdf_osm.empty:
    raise ValueError("OSM 查無資料")

gdf_osm = gdf_osm[gdf_osm.geometry.type.isin(["LineString", "MultiLineString"])].copy()

if gdf_osm.crs is None:
    gdf_osm = gdf_osm.set_crs("EPSG:4326")

gdf_osm["highway_norm"] = gdf_osm["highway"].apply(normalize_highway_value)
gdf_osm["route_role"] = gdf_osm["highway_norm"].apply(classify_route_role)

gdf_osm = gdf_osm[gdf_osm["highway_norm"].isin(ALLOWED_HIGHWAY)].copy()

if gdf_osm.empty:
    raise ValueError("過濾後無符合條件的 OSM 候選路段")

gdf_osm_m = gdf_osm.to_crs(metric_crs)

# 只保留與 fetch buffer 相交者
gdf_osm_m = gdf_osm_m[gdf_osm_m.intersects(gpx_buffer_fetch)].copy()

if gdf_osm_m.empty:
    raise ValueError("GPX 附近無候選 OSM 路段")


# =========================================================
# 5. 計算 matching 特徵
# =========================================================
print("計算 matching 特徵中...")

gdf_osm_m["segment_len_m"] = gdf_osm_m.geometry.length
gdf_osm_m["distance_to_gpx_m"] = gdf_osm_m.geometry.distance(gpx_line_m)

intersections = gdf_osm_m.geometry.intersection(gpx_buffer_match)
gdf_osm_m["overlap_len_m"] = intersections.length
gdf_osm_m["overlap_ratio"] = (
    gdf_osm_m["overlap_len_m"] / gdf_osm_m["segment_len_m"]
).replace([np.inf, -np.inf], np.nan).fillna(0)

gdf_osm_m["semantic_score"] = gdf_osm_m["highway_norm"].apply(get_semantic_score)

# 距離分數：越近越高
gdf_osm_m["distance_score"] = 1 - np.clip(
    gdf_osm_m["distance_to_gpx_m"] / GPX_BUFFER_MATCH_M, 0, 1
)

# 綜合分數
gdf_osm_m["match_score"] = (
    0.45 * gdf_osm_m["distance_score"] +
    0.35 * gdf_osm_m["overlap_ratio"] +
    0.20 * gdf_osm_m["semantic_score"]
)

gdf_osm_m["selected"] = gdf_osm_m.apply(classify_selected, axis=1)

# 補欄位
if isinstance(gdf_osm_m.index, pd.MultiIndex):
    gdf_osm_m["osm_element_type"] = gdf_osm_m.index.get_level_values(0).astype(str)
    gdf_osm_m["osm_id"] = gdf_osm_m.index.get_level_values(1)
    gdf_osm_m["osm_way_id"] = (
        gdf_osm_m["osm_element_type"] + ":" + gdf_osm_m["osm_id"].astype(str)
    )
else:
    gdf_osm_m["osm_element_type"] = "unknown"
    gdf_osm_m["osm_id"] = gdf_osm_m.index
    gdf_osm_m["osm_way_id"] = gdf_osm_m["osm_id"].astype(str)

if "name" not in gdf_osm_m.columns:
    gdf_osm_m["name"] = None

gdf_osm_m["name"] = gdf_osm_m["name"].fillna("")


# =========================================================
# 6. 輸出 GeoJSON
# =========================================================
candidate_cols = [
    "osm_element_type",
    "osm_id",
    "osm_way_id",
    "name",
    "highway",
    "highway_norm",
    "route_role",
    "segment_len_m",
    "distance_to_gpx_m",
    "overlap_len_m",
    "overlap_ratio",
    "semantic_score",
    "distance_score",
    "match_score",
    "selected",
    "geometry",
]

existing_candidate_cols = [c for c in candidate_cols if c in gdf_osm_m.columns]

gdf_candidates = gdf_osm_m[existing_candidate_cols].copy().to_crs("EPSG:4326")
gdf_matched = gdf_candidates[gdf_candidates["selected"] == 1].copy()

gdf_candidates.to_file(CANDIDATE_GEOJSON_FP, driver="GeoJSON")
gdf_matched.to_file(MATCHED_GEOJSON_FP, driver="GeoJSON")

print("候選路段輸出：", CANDIDATE_GEOJSON_FP.resolve())
print("匹配路段輸出：", MATCHED_GEOJSON_FP.resolve())


# =========================================================
# 7. 輸出 summary csv
# =========================================================
summary_rows = []

for (role, hw), sub in gdf_candidates.groupby(["route_role", "highway_norm"]):
    summary_rows.append({
        "route_role": role,
        "highway_norm": hw,
        "candidate_n": len(sub),
        "selected_n": int(sub["selected"].sum()),
        "mean_distance_to_gpx_m": sub["distance_to_gpx_m"].mean(),
        "mean_overlap_ratio": sub["overlap_ratio"].mean(),
        "mean_match_score": sub["match_score"].mean(),
    })

summary_df = pd.DataFrame(summary_rows).sort_values(
    by=["selected_n", "candidate_n"],
    ascending=[False, False]
)
summary_df.to_csv(SUMMARY_CSV_FP, index=False, encoding="utf-8-sig")

print("摘要輸出：", SUMMARY_CSV_FP.resolve())


# =========================================================
# 8. 建立 QA 地圖
# =========================================================
print("建立 QA 地圖中...")

m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=14,
    tiles="CartoDB positron",
    width="100%",
    height="800px",
)

# GPX 圖層
fg_gpx = folium.FeatureGroup(name="GPX route", show=True)
gpx_coords = [(lat, lon) for lon, lat in gpx_line.coords]
folium.PolyLine(
    gpx_coords,
    color="blue",
    weight=4,
    opacity=0.9,
    tooltip="GPX route",
).add_to(fg_gpx)
fg_gpx.add_to(m)

# OSM 候選圖層
fg_osm = folium.FeatureGroup(name="OSM candidates / matched", show=True)

for _, row in gdf_candidates.iterrows():
    geom = row.geometry

    popup_text = (
        f"osm_way_id: {row.get('osm_way_id', '')}\n"
        f"name: {row.get('name', '')}\n"
        f"highway: {row.get('highway_norm', '')}\n"
        f"route_role: {row.get('route_role', '')}\n"
        f"distance_to_gpx_m: {row.get('distance_to_gpx_m', np.nan):.3f}\n"
        f"overlap_ratio: {row.get('overlap_ratio', np.nan):.3f}\n"
        f"semantic_score: {row.get('semantic_score', np.nan):.3f}\n"
        f"match_score: {row.get('match_score', np.nan):.3f}\n"
        f"selected: {row.get('selected', 0)}"
    )
    popup = folium.Popup(f"<pre>{popup_text}</pre>", max_width=350)

    color = "red" if row.get("selected", 0) == 1 else "gray"
    weight = 5 if row.get("selected", 0) == 1 else 2
    opacity = 0.9 if row.get("selected", 0) == 1 else 0.5

    if geom.geom_type == "LineString":
        coords = [(lat, lon) for lon, lat in geom.coords]
        folium.PolyLine(
            coords,
            color=color,
            weight=weight,
            opacity=opacity,
            popup=popup,
        ).add_to(fg_osm)

    elif geom.geom_type == "MultiLineString":
        for line in geom.geoms:
            coords = [(lat, lon) for lon, lat in line.coords]
            folium.PolyLine(
                coords,
                color=color,
                weight=weight,
                opacity=opacity,
                popup=popup,
            ).add_to(fg_osm)

fg_osm.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)
m.save(QA_HTML_FP)

print("QA 地圖輸出：", QA_HTML_FP.resolve())


# =========================================================
# 9. 終端摘要
# =========================================================
print("\n=== match summary ===")
print("候選路段數：", len(gdf_candidates))
print("入選路段數：", len(gdf_matched))

print("\n--- selected route_role distribution ---")
if not gdf_matched.empty:
    print(gdf_matched["route_role"].value_counts(dropna=False))
else:
    print("無入選路段")

print("\n--- selected highway distribution ---")
if not gdf_matched.empty:
    print(gdf_matched["highway_norm"].value_counts(dropna=False))
else:
    print("無入選路段")