import geopandas as gpd
import folium
from shapely.geometry import LineString, Point
import pandas as pd
import networkx as nx
from tqdm import tqdm

# === 參數設定 ===
distance_steps = [2, 4, 6, 8]  # 補橋距離閾值漸進式嘗試（公尺）
source_epsg = 3826
start_latlon = (25.166216347028858, 121.56332374819574)
segment_file = "If3_final_segments_with_ic4_details.geojson"
ic4_path = "Ic4_combined_with_tags_with_wayid.geojson"  # 用於產生節點

print("📦 讀取原始段落圖資...")
segments = gpd.read_file(segment_file).to_crs(epsg=source_epsg)
segments["way_id"] = segments["way_id"].astype(str)

print("📦 讀取 Ic4 原始路線圖資...")
gdf_ic4 = gpd.read_file(ic4_path).to_crs(epsg=source_epsg)
gdf_ic4["way_id"] = gdf_ic4["way_id"].astype(str)

# --- 從 Ic4 建立節點資料集（由線端點抽出） ---
print("🔍 從 Ic4 建立節點資料集（線段端點）...")
nodes_list = []
for idx, row in gdf_ic4.iterrows():
    geom = row.geometry
    if geom is None:
        continue
    if geom.geom_type == "LineString":
        coords = list(geom.coords)
        nodes_list.append({"node_id": f"{row['way_id']}_start", "way_id": row["way_id"], "geometry": Point(coords[0])})
        nodes_list.append({"node_id": f"{row['way_id']}_end", "way_id": row["way_id"], "geometry": Point(coords[-1])})
    elif geom.geom_type == "MultiLineString":
        for part_idx, part in enumerate(geom.geoms):
            coords = list(part.coords)
            nodes_list.append({"node_id": f"{row['way_id']}_start_{part_idx}", "way_id": row["way_id"], "geometry": Point(coords[0])})
            nodes_list.append({"node_id": f"{row['way_id']}_end_{part_idx}", "way_id": row["way_id"], "geometry": Point(coords[-1])})

nodes = gpd.GeoDataFrame(nodes_list, crs=gdf_ic4.crs)

# --- 補齊 segments 屬性（bridge, highway, surface） ---
ic_sub = gdf_ic4[["way_id", "bridge", "highway", "surface"]].drop_duplicates(subset="way_id").set_index("way_id")

segments = segments.set_index("way_id")
segments["bridge"] = segments.index.map(ic_sub["bridge"]).fillna("no")
segments["highway"] = segments.index.map(ic_sub["highway"]).fillna("road")
segments["surface"] = segments.index.map(ic_sub["surface"]).fillna("")
segments = segments.reset_index()

# --- 找最近節點函數 ---
def find_nearest_node_id(pt, nodes_gdf, max_dist=5):
    dists = nodes_gdf.geometry.distance(pt)
    min_idx = dists.idxmin()
    if dists[min_idx] <= max_dist:
        return nodes_gdf.loc[min_idx, "node_id"]
    else:
        return None

# --- 建立所有段落端點 GeoDataFrame ---
print("🔍 建立所有段落端點...")
endpoints = []
for idx, row in segments.iterrows():
    if row.geometry is None:
        continue
    coords = list(row.geometry.coords)
    endpoints.append((idx, Point(coords[0])))
    endpoints.append((idx, Point(coords[-1])))
end_gdf = gpd.GeoDataFrame(endpoints, columns=["seg_idx", "geometry"], geometry="geometry", crs=segments.crs)

# --- 建立初始拓撲圖 (防止補重複橋段) ---
temp_graph = nx.Graph()
for idx, row in segments.iterrows():
    if row.geometry is None:
        continue
    coords = list(row.geometry.coords)
    pt1 = (round(coords[0][0], 6), round(coords[0][1], 6))
    pt2 = (round(coords[-1][0], 6), round(coords[-1][1], 6))
    temp_graph.add_edge(pt1, pt2)

# --- 找出起點對應節點 ---
target_proj = gpd.GeoSeries([Point(start_latlon[1], start_latlon[0])], crs=4326).to_crs(source_epsg).iloc[0]
start_node = min(temp_graph.nodes, key=lambda pt: Point(pt).distance(target_proj))
print(f"🚀 使用起點: {start_node}")

# --- 漸進式補橋演算法 ---
print("🔗 漸進式補橋算法...")
bridges = []
used_pairs = set()
for threshold in distance_steps:
    print(f"➔ 嘗試補橋距離: {threshold}m")
    for i, row1 in tqdm(end_gdf.iterrows(), total=len(end_gdf), leave=False):
        for j, row2 in end_gdf.iterrows():
            if j <= i or row1["seg_idx"] == row2["seg_idx"]:
                continue
            pt1, pt2 = row1.geometry, row2.geometry
            node1 = (round(pt1.x, 6), round(pt1.y, 6))
            node2 = (round(pt2.x, 6), round(pt2.y, 6))
            pair_key = tuple(sorted([row1["seg_idx"], row2["seg_idx"]]))
            if pair_key in used_pairs or nx.has_path(temp_graph, node1, node2):
                continue
            if node1 == start_node or node2 == start_node:
                continue
            if pt1.distance(pt2) <= threshold:
                bridges.append({
                    "geometry": LineString([pt1, pt2]),
                    "way_id": f"bridge_{len(bridges)+1:03d}",
                    "source_type": "bridge",
                    "bridge": "yes",
                    "highway": "bridge",
                    "surface": ""
                })
                used_pairs.add(pair_key)
                temp_graph.add_edge(node1, node2)

bridge_gdf = gpd.GeoDataFrame(bridges, geometry="geometry", crs=source_epsg) if bridges else gpd.GeoDataFrame(columns=segments.columns, geometry=[], crs=source_epsg)

# --- 合併所有段落並建立拓撲圖 ---
all_gdf = pd.concat([segments, bridge_gdf], ignore_index=True)

# --- 建立拓撲圖用於 DFS 掃描 ---
graph = nx.Graph()
for idx, row in all_gdf.iterrows():
    if row.geometry is None:
        continue
    coords = list(row.geometry.coords)
    pt1 = (round(coords[0][0], 6), round(coords[0][1], 6))
    pt2 = (round(coords[-1][0], 6), round(coords[-1][1], 6))
    graph.add_edge(pt1, pt2, key=idx)

# --- DFS 掃描順序 ---
visited_edges = set()
visited_nodes = set()
route_seq = []

def dfs(node):
    visited_nodes.add(node)
    for neighbor in graph.neighbors(node):
        edges = graph.get_edge_data(node, neighbor)
        for key in edges:
            if key not in visited_edges:
                visited_edges.add(key)
                route_seq.append(key)
                if neighbor not in visited_nodes:
                    dfs(neighbor)

dfs(start_node)

all_gdf["route_seq"] = -1
for i, idx in enumerate(route_seq):
    all_gdf.loc[idx, "route_seq"] = i

# --- 補齊座標與 node_id ---
all_gdf = all_gdf[all_gdf.geometry.notnull()].copy()
all_gdf["distance_m"] = all_gdf.geometry.length
all_gdf["from_x"] = all_gdf.geometry.apply(lambda g: g.coords[0][0])
all_gdf["from_y"] = all_gdf.geometry.apply(lambda g: g.coords[0][1])
all_gdf["to_x"] = all_gdf.geometry.apply(lambda g: g.coords[-1][0])
all_gdf["to_y"] = all_gdf.geometry.apply(lambda g: g.coords[-1][1])
all_gdf["from_node_id"] = all_gdf.apply(lambda r: find_nearest_node_id(Point(r["from_x"], r["from_y"]), nodes), axis=1)
all_gdf["to_node_id"] = all_gdf.apply(lambda r: find_nearest_node_id(Point(r["to_x"], r["to_y"]), nodes), axis=1)

# --- CRS轉WGS84並輸出 ---
all_gdf = all_gdf.to_crs(epsg=4326)

# --- 欲輸出欄位順序及保留 ---
save_cols = [
    "route_seq", "way_id", "source_type", "bridge", "highway", "surface",
    "from_node_id", "to_node_id", "distance_m", "from_x", "from_y", "to_x", "to_y", "geometry"
]

all_gdf.to_file("Ij_combined_segments.geojson", driver="GeoJSON")
all_gdf.sort_values("route_seq").to_csv("Ij_route_sequence.csv", columns=save_cols, index=False)
print("✅ 已輸出 GeoJSON 和 CSV！")

# --- folium 地圖 ---
print("🖼️ 生成地圖 Ij_bridges_map.html...")
m = folium.Map(location=[start_latlon[0], start_latlon[1]], zoom_start=16,
               tiles="https://tile.opentopomap.org/{z}/{x}/{y}.png",
               attr="Map data © OpenStreetMap, SRTM | Style: OpenTopoMap")

layers = {
    "一般段": {"filter": lambda r: r["bridge"].lower() != "yes" and r["highway"].lower() != "steps", "color": "blue"},
    "階梯段": {"filter": lambda r: r["highway"].lower() == "steps", "color": "orange"},
    "橋樑段": {"filter": lambda r: r["bridge"].lower() == "yes", "color": "red"},
}

for lname, props in layers.items():
    fg = folium.FeatureGroup(name=lname)
    subset = all_gdf[all_gdf.apply(props["filter"], axis=1)]
    for _, row in subset.iterrows():
        coords = [(y, x) for x, y in row.geometry.coords]
        popup_lines = [
            f"<b>way_id:</b> {row['way_id']}",
            f"<b>source_type:</b> {row.get('source_type', '')}",
            f"<b>bridge:</b> {row['bridge']}",
            f"<b>highway:</b> {row['highway']}",
            f"<b>surface:</b> {row['surface']}",
            f"<b>route_seq:</b> {row['route_seq']}",
        ]
        popup = "<br>".join(popup_lines)
        folium.PolyLine(coords, color=props["color"], weight=4, popup=popup).add_to(fg)
    fg.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)
m.save("Ij_bridges_map.html")
print("✅ 地圖已完成：Ij_bridges_map.html")