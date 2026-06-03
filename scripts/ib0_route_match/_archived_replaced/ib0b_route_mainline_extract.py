# =========================================================
# ib0b_route_mainline_extract.py
# 從 pruned OSM segments 抽取主幹路徑
# 使用 ib0c anchors + GPX interval anchors
# =========================================================

from pathlib import Path
import xml.etree.ElementTree as ET

import geopandas as gpd
from shapely.geometry import LineString, Point
import networkx as nx
import folium


# =========================================================
# 0. 路徑設定
# =========================================================
IN_FP = Path("ib0_gpx_osm_match_output/qixing_gpx_osm_matched_pruned.geojson")
ANCHOR_FP = Path("ib0c_anchor_output/qixing_route_anchors.geojson")

GPX_DIR = Path("/Users/iddmini/Documents/115_Motion改造/FY115_登山/gpx")
GPX_NAME = "冷水坑上-七星山東峰-主峰-下小油坑.gpx"
GPX_FP = GPX_DIR / GPX_NAME

OUT_DIR = Path("ib0b_output")
OUT_DIR.mkdir(exist_ok=True)

OUT_FP = OUT_DIR / "qixing_mainline.geojson"
OUT_HTML_FP = OUT_DIR / "qixing_mainline_map.html"
OUT_ORDERED_PATH_FP = OUT_DIR / "qixing_mainline_ordered_path.geojson"


# =========================================================
# 1. 參數設定
# =========================================================
GPX_ANCHOR_INTERVAL_M = 30.0

# 是否啟用 snap link
# 先設 False，避免上下緣被錯誤接起來
ENABLE_SNAP_LINK = False
SNAP_TOLERANCE_M = 15.0
SNAP_LINK_WEIGHT = 0.30

MIN_ANCHOR_SPACING_M = 15.0


# =========================================================
# 2. 輸入檢查
# =========================================================
if not IN_FP.exists():
    raise FileNotFoundError(f"找不到 pruned route：{IN_FP.resolve()}，請先執行 ib0a")

if not ANCHOR_FP.exists():
    raise FileNotFoundError(f"找不到 anchors：{ANCHOR_FP.resolve()}，請先執行 ib0c")

if not GPX_FP.exists():
    raise FileNotFoundError(f"找不到 GPX：{GPX_FP.resolve()}")


# =========================================================
# 3. 工具函式
# =========================================================
def parse_gpx_line(gpx_fp: Path) -> LineString:
    tree = ET.parse(gpx_fp)
    root = tree.getroot()

    if root.tag.startswith("{"):
        uri = root.tag.split("}")[0].strip("{")
        ns = {"gpx": uri}
        trkpt_xpath = ".//gpx:trkpt"
    else:
        ns = {}
        trkpt_xpath = ".//trkpt"

    pts = []

    for trkpt in root.findall(trkpt_xpath, ns):
        lat = float(trkpt.attrib["lat"])
        lon = float(trkpt.attrib["lon"])
        pts.append((lon, lat))

    if len(pts) < 2:
        raise ValueError("GPX 點數不足，無法建立 LineString")

    return LineString(pts)


def line_to_nodes(line):
    coords = list(line.coords)
    return tuple(coords[0]), tuple(coords[-1])


def nearest_segment_node(gdf_m, pt_m):
    min_dist = float("inf")
    best_idx = None

    for idx, row in gdf_m.iterrows():
        geom = row.geometry
        d = geom.distance(pt_m)

        if d < min_dist:
            min_dist = d
            best_idx = idx

    geom = gdf_m.loc[best_idx].geometry

    if geom.geom_type == "MultiLineString":
        geom = list(geom.geoms)[0]

    coords = list(geom.coords)
    n1 = tuple(coords[0])
    n2 = tuple(coords[-1])

    if Point(n1).distance(pt_m) < Point(n2).distance(pt_m):
        return n1
    else:
        return n2


def make_gpx_interval_points(gpx_line_m: LineString, interval_m: float):
    total_len = gpx_line_m.length

    pts = []
    d = interval_m

    while d < total_len:
        pts.append(gpx_line_m.interpolate(d))
        d += interval_m

    return pts


def node_distance(a, b):
    return Point(a).distance(Point(b))


# =========================================================
# 4. 讀資料
# =========================================================
gdf = gpd.read_file(IN_FP).to_crs(epsg=4326)
anchors = gpd.read_file(ANCHOR_FP).to_crs(epsg=4326)

metric_crs = gdf.estimate_utm_crs()
gdf_m = gdf.to_crs(metric_crs)

gpx_line = parse_gpx_line(GPX_FP)

gpx_gdf = gpd.GeoDataFrame(
    [{"geometry": gpx_line}],
    geometry="geometry",
    crs="EPSG:4326",
)

gpx_line_m = gpx_gdf.to_crs(metric_crs).geometry.iloc[0]


# =========================================================
# 5. 讀 ib0c anchors
# =========================================================
start_pt = anchors.loc[anchors["anchor_role"] == "start"].geometry.iloc[0]
via_pt = anchors.loc[anchors["anchor_role"] == "via"].geometry.iloc[0]
end_pt = anchors.loc[anchors["anchor_role"] == "end"].geometry.iloc[0]

start_pt_m = gpd.GeoSeries([start_pt], crs="EPSG:4326").to_crs(metric_crs).iloc[0]
via_pt_m = gpd.GeoSeries([via_pt], crs="EPSG:4326").to_crs(metric_crs).iloc[0]
end_pt_m = gpd.GeoSeries([end_pt], crs="EPSG:4326").to_crs(metric_crs).iloc[0]


# =========================================================
# 6. 建 graph
# =========================================================
G = nx.Graph()

def split_line_to_segments(line):
    coords = list(line.coords)
    segments = []

    for i in range(len(coords) - 1):
        seg = LineString([coords[i], coords[i + 1]])
        segments.append(seg)

    return segments


for idx, row in gdf_m.iterrows():
    geom = row.geometry

    if geom is None or geom.is_empty:
        continue

    lines = list(geom.geoms) if geom.geom_type == "MultiLineString" else [geom]

    for line in lines:
        segments = split_line_to_segments(line)

        for seg in segments:
            coords = list(seg.coords)
            start = tuple(coords[0])
            end = tuple(coords[1])

            score = row.get("match_score", 0.5)
            dist = row.get("distance_to_gpx_m", 999)
            overlap = row.get("overlap_ratio", 0)

            cost = (
                0.05 * (1.0 - score) +
                0.65 * min(dist / 30.0, 1.0) +
                0.30 * (1.0 - overlap)
            )

            # GPX corridor 懲罰保留
            cost += 0.15 * min(dist, 50)

            # 暫時不要 hard continue，避免 graph 被切斷
            # if dist > 25:
            #     continue

            G.add_edge(start, end, weight=cost, idx=idx, snap_link=0)

print(f"輸入 segments: {len(gdf)}")
print(f"Graph nodes: {len(G.nodes)}")
print(f"Graph edges before snapping: {len(G.edges)}")


# =========================================================
# 7. Optional snap link
# =========================================================
if ENABLE_SNAP_LINK:
    nodes = list(G.nodes)

    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            d = node_distance(nodes[i], nodes[j])

            if d <= SNAP_TOLERANCE_M:
                if not G.has_edge(nodes[i], nodes[j]):
                    G.add_edge(
                        nodes[i],
                        nodes[j],
                        weight=SNAP_LINK_WEIGHT,
                        idx=-1,
                        snap_link=1,
                    )

print(f"ENABLE_SNAP_LINK: {ENABLE_SNAP_LINK}")
print(f"Graph edges after snapping: {len(G.edges)}")


# =========================================================
# 8. 建立 ordered anchors
# =========================================================
gpx_interval_pts_m = make_gpx_interval_points(gpx_line_m, GPX_ANCHOR_INTERVAL_M)

anchor_points_m = []

# ib0c start
anchor_points_m.append(("start", start_pt_m))

# GPX interval anchors
for i, pt in enumerate(gpx_interval_pts_m):
    anchor_points_m.append((f"gpx_{i:03d}", pt))

# ib0c via / end
anchor_points_m.append(("via", via_pt_m))
anchor_points_m.append(("end", end_pt_m))

# 依 GPX progress 排序
anchor_ranked = []

for role, pt in anchor_points_m:
    progress_m = gpx_line_m.project(pt)
    anchor_ranked.append((role, pt, progress_m))

anchor_ranked = sorted(anchor_ranked, key=lambda x: x[2])

# 去除過近 anchor
filtered = []

for role, pt, prog in anchor_ranked:
    if not filtered:
        filtered.append((role, pt, prog))
    else:
        if abs(prog - filtered[-1][2]) >= MIN_ANCHOR_SPACING_M:
            filtered.append((role, pt, prog))

anchor_ranked = filtered

print(f"ordered anchors: {len(anchor_ranked)}")
print("first anchor:", anchor_ranked[0][0], anchor_ranked[0][2])
print("last anchor:", anchor_ranked[-1][0], anchor_ranked[-1][2])


# =========================================================
# 9. anchors 轉 graph nodes
# =========================================================
anchor_nodes = []

for role, pt, progress_m in anchor_ranked:
    node = nearest_segment_node(gdf_m, pt)
    anchor_nodes.append((role, node, progress_m))

# 去除連續重複 node
dedup_anchor_nodes = []

for role, node, progress_m in anchor_nodes:
    if not dedup_anchor_nodes or node != dedup_anchor_nodes[-1][1]:
        dedup_anchor_nodes.append((role, node, progress_m))

anchor_nodes = dedup_anchor_nodes

print(f"anchor nodes after dedup: {len(anchor_nodes)}")


# =========================================================
# 10. 依序 shortest path
# =========================================================
full_path = []

for i in range(len(anchor_nodes) - 1):
    role_a, node_a, prog_a = anchor_nodes[i]
    role_b, node_b, prog_b = anchor_nodes[i + 1]

    if node_a == node_b:
        continue

    try:
        sub_path = nx.shortest_path(G, node_a, node_b, weight="weight")
    except nx.NetworkXNoPath:
        print(f"WARNING: no path between {role_a} and {role_b}")
        continue

    if not full_path:
        full_path.extend(sub_path)
    else:
        full_path.extend(sub_path[1:])

print(f"path length nodes: {len(full_path)}")

# =========================================================
# 10b. 輸出 ordered path：保留真正路徑順序
# =========================================================
if len(full_path) < 2:
    raise ValueError("full_path 節點數不足，無法建立 ordered path")

ordered_line_m = LineString(full_path)

ordered_path_gdf = gpd.GeoDataFrame(
    [{
        "route_id": "qixing",
        "analysis_unit": "ordered_mainline_path",
        "source": "ib0b_full_path",
        "path_node_n": len(full_path),
        "length_m": ordered_line_m.length,
        "geometry": ordered_line_m,
    }],
    geometry="geometry",
    crs=metric_crs,
)

ordered_path_gdf.to_crs("EPSG:4326").to_file(
    OUT_ORDERED_PATH_FP,
    driver="GeoJSON"
)

print(f"ordered path 輸出：{OUT_ORDERED_PATH_FP}")
print(f"ordered path length m: {ordered_line_m.length:.2f}")


# =========================================================
# 11. 還原 segments
# =========================================================
edge_set = set()

for i in range(len(full_path) - 1):
    u = full_path[i]
    v = full_path[i + 1]

    if G.has_edge(u, v):
        data = G.get_edge_data(u, v)
        idx = data.get("idx", -1)
        edge_set.add(idx)

valid_idx = [idx for idx in edge_set if idx != -1]
mainline = gdf.loc[valid_idx].copy()

# # =========================================================
# # 11a. 主幹二次清理：移除離 GPX 過遠的 spur / tail
# #      因為入口 service road 本來就可能不貼 GPX，硬砍會不穩。
# # =========================================================
# mainline = mainline[
#     mainline["distance_to_gpx_m"] < 20
# ].copy()

# print(f"主幹 segments: {len(mainline)}")

# =========================================================
# 11a. 標記 mainline_role：approach / trail_core
# =========================================================
APPROACH_HIGHWAYS = {
    "service",
    "tertiary",
    "secondary",
    "primary",
    "residential",
    "unclassified",
    "road",
}

TRAIL_HIGHWAYS = {
    "footway",
    "steps",
    "path",
    "track",
}

def classify_mainline_role(row):
    hw = str(row.get("highway_norm", "")).lower()
    role = str(row.get("route_role", "")).lower()

    if hw in APPROACH_HIGHWAYS:
        return "approach"

    if hw in TRAIL_HIGHWAYS:
        return "trail_core"

    if role == "approach_or_road":
        return "approach"

    if role == "trail_core":
        return "trail_core"

    return "unknown"

mainline["mainline_role"] = mainline.apply(classify_mainline_role, axis=1)

print(f"主幹 segments: {len(mainline)}")
print("\n--- mainline_role distribution ---")
print(mainline["mainline_role"].value_counts(dropna=False))

# =========================================================
# 11b. Debug CSV：輸出被選入主幹的 segments
# =========================================================
DEBUG_MAINLINE_CSV = OUT_DIR / "qixing_mainline_debug_segments.csv"

debug_cols = [
    "osm_way_id",
    "name",
    "highway_norm",
    "route_role",
    "mainline_role",
    "distance_to_gpx_m",
    "overlap_ratio",
    "match_score",
]

exist_cols = [c for c in debug_cols if c in mainline.columns]
mainline[exist_cols].to_csv(DEBUG_MAINLINE_CSV, index=False, encoding="utf-8-sig")

print(f"主幹 debug CSV：{DEBUG_MAINLINE_CSV}")

mainline.to_file(OUT_FP, driver="GeoJSON")
print(f"輸出：{OUT_FP}")


# =========================================================
# 11c. QA style helper
# =========================================================
def mainline_style(feat):
    role = feat["properties"].get("mainline_role", "")

    if role == "approach":
        return {
            "color": "orange",
            "weight": 5,
            "opacity": 0.9,
        }

    if role == "trail_core":
        return {
            "color": "red",
            "weight": 5,
            "opacity": 0.95,
        }

    return {
        "color": "purple",
        "weight": 4,
        "opacity": 0.8,
    }

# =========================================================
# 12. QA 地圖
# =========================================================
gdf_wgs84 = gdf.to_crs(epsg=4326)
mainline_wgs84 = mainline.to_crs(epsg=4326)

center_geom = mainline_wgs84.geometry.union_all().centroid
center = [center_geom.y, center_geom.x]

m = folium.Map(
    location=center,
    zoom_start=14,
    tiles="CartoDB positron",
    width="100%",
    height="800px",
)

# 背景：pruned route
folium.GeoJson(
    gdf_wgs84,
    name="pruned_route_background",
    style_function=lambda feat: {
        "color": "gray",
        "weight": 2,
        "opacity": 0.25,
    },
).add_to(m)

# GPX
folium.PolyLine(
    [(lat, lon) for lon, lat in gpx_line.coords],
    color="black",
    weight=3,
    opacity=0.7,
    tooltip="GPX",
).add_to(m)

# mainline
# folium.GeoJson(
#     mainline_wgs84,
#     name="mainline",
#     style_function=lambda feat: {
#         "color": "red",
#         "weight": 5,
#         "opacity": 0.95,
#     },
# ).add_to(m)
folium.GeoJson(
    mainline_wgs84,
    name="mainline",
    style_function=mainline_style,
).add_to(m)

# ib0c anchors
for _, row in anchors.iterrows():
    role = row["anchor_role"]
    color = {"start": "green", "via": "blue", "end": "red"}.get(role, "gray")
    icon = {"start": "play", "via": "flag", "end": "stop"}.get(role, "info-sign")

    folium.Marker(
        location=[row.geometry.y, row.geometry.x],
        tooltip=f"{role} - {row.get('anchor_source', '')}",
        icon=folium.Icon(color=color, icon=icon),
    ).add_to(m)

# GPX interval anchors
anchor_points_wgs = gpd.GeoSeries(
    [pt for _, pt, _ in anchor_ranked],
    crs=metric_crs,
).to_crs("EPSG:4326")

for i, pt in enumerate(anchor_points_wgs):
    folium.CircleMarker(
        location=[pt.y, pt.x],
        radius=2,
        color="purple",
        fill=True,
        fill_opacity=0.5,
        tooltip=f"gpx_anchor_{i}",
    ).add_to(m)

folium.LayerControl(collapsed=False).add_to(m)
m.save(OUT_HTML_FP)

print(f"QA 地圖輸出：{OUT_HTML_FP}")