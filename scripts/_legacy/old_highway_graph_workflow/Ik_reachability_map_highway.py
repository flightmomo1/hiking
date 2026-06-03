import geopandas as gpd
import pandas as pd
import networkx as nx
from shapely.geometry import Point, LineString
import folium

# 參數設定
ij_path = "Ij_combined_segments.geojson"    # 補橋後完整路網
output_geojson = "Ik_reachable_segments.geojson"
output_csv = "Ik_reachable_route.csv"
output_map = "Ik_reachable_map.html"
start_latlon = (25.166216347028858, 121.56332374819574)     # 起點經緯度

# 讀取路網資料（已包含橋段與屬性）
gdf = gpd.read_file(ij_path).to_crs(epsg=4326)

# 建立投影版本計算距離用（更準確）
gdf_proj = gdf.to_crs(epsg=3826)
target_pt_proj = Point(start_latlon[1], start_latlon[0])
target_pt_proj = gpd.GeoSeries([target_pt_proj], crs=4326).to_crs(epsg=3826).iloc[0]

# 找起點最近端點節點（投影距離）
min_dist = float('inf')
start_node = None

nodes = set()
for geom in gdf.geometry:
    coords = list(geom.coords)
    # 精度提高到9位小數避免誤判
    nodes.add((round(coords[0][0],9), round(coords[0][1],9)))
    nodes.add((round(coords[-1][0],9), round(coords[-1][1],9)))

for node in nodes:
    pt = Point(node)
    pt_proj = gpd.GeoSeries([pt], crs=4326).to_crs(epsg=3826).iloc[0]
    dist = pt_proj.distance(target_pt_proj)
    if dist < min_dist:
        min_dist = dist
        start_node = node

print(f"使用起點節點：{start_node}")

# 建立圖論，邊帶 key 為邊所在索引
G = nx.Graph()
for idx, row in gdf.iterrows():
    coords = list(row.geometry.coords)
    pt1 = (round(coords[0][0],9), round(coords[0][1],9))
    pt2 = (round(coords[-1][0],9), round(coords[-1][1],9))
    G.add_edge(pt1, pt2, key=idx)

# DFS 走訪，鄰居依投影距離排序以保持路徑連續性
visited_edges = set()
visited_nodes = set()
order = []

def dfs(node):
    visited_nodes.add(node)
    neighbors = list(G.neighbors(node))
    node_proj = gpd.GeoSeries([Point(node)], crs=4326).to_crs(epsg=3826).iloc[0]
    neighbors_proj = {nbr: gpd.GeoSeries([Point(nbr)], crs=4326).to_crs(epsg=3826).iloc[0] for nbr in neighbors}
    neighbors.sort(key=lambda nbr: neighbors_proj[nbr].distance(node_proj))
    for neighbor in neighbors:
        edge_key = G.edges[node, neighbor]['key']
        if edge_key not in visited_edges:
            visited_edges.add(edge_key)
            order.append(edge_key)
            if neighbor not in visited_nodes:
                dfs(neighbor)

dfs(start_node)

# 依走訪順序編碼 ik_seq，先預設-1
gdf['ik_seq'] = -1
for seq, idx in enumerate(order):
    gdf.at[idx, 'ik_seq'] = seq

# 補 ik_source 欄位（來源類型）
if "source_type" in gdf.columns:
    gdf["ik_source"] = gdf["source_type"]
else:
    gdf["ik_source"] = "unknown"

# 過濾只保留可達路段並依 ik_seq 排序
gdf_reachable = gdf[gdf['ik_seq'] >= 0].sort_values('ik_seq').reset_index(drop=True)

# ==== 調整線段方向，讓路段起點接前一段終點，確保連續性 ====
from shapely.geometry import Point as ShapelyPoint
for i in range(1, len(gdf_reachable)):
    prev_end = list(gdf_reachable.loc[i-1].geometry.coords)[-1]
    curr_coords = list(gdf_reachable.loc[i].geometry.coords)
    dist_start = ShapelyPoint(curr_coords[0]).distance(ShapelyPoint(prev_end))
    dist_end = ShapelyPoint(curr_coords[-1]).distance(ShapelyPoint(prev_end))
    if dist_start > dist_end:
        # 反轉線段方向
        gdf_reachable.at[i, "geometry"] = LineString(curr_coords[::-1])

# 輸出
gdf_reachable.to_file(output_geojson, driver="GeoJSON")
gdf_reachable.to_csv(output_csv, index=False)

# 繪圖
m = folium.Map(location=[start_latlon[0], start_latlon[1]], zoom_start=16)

# 分層圖層字典
fgs = {
    "橋樑段": folium.FeatureGroup(name="🌉 橋樑段", show=True),
    "階梯段": folium.FeatureGroup(name="🪜 階梯段", show=True),
    "一般段": folium.FeatureGroup(name="🚶 一般段", show=True),
}

color_map = {
    "yes": "red",   # 以 bridge 欄位判斷
    "steps": "orange",
    "default": "blue",
}

# 擴充 surface 顏色（可依需求增減）
surface_colors = {
    "paving_stones": "saddlebrown",
    "sett": "saddlebrown",
    "wood": "brown",
    "gravel": "gray",
    "road": "gray",
    "service": "blue",
    "track": "brown",
    "trail": "green",
    "footway": "green",
}

for _, row in gdf_reachable.iterrows():
    coords = [(lat, lon) for lon, lat in row.geometry.coords]  # folium 要 (lat, lon)
    bridge_flag = str(row.get("bridge", "")).lower() == "yes"
    highway = str(row.get("highway", "")).lower()
    surface = str(row.get("surface", "")).lower()

    if bridge_flag:
        color = color_map["yes"]
        layer = fgs["橋樑段"]
    elif highway == "steps":
        color = color_map["steps"]
        layer = fgs["階梯段"]
    else:
        color = surface_colors.get(surface, color_map["default"])
        layer = fgs["一般段"]

    popup_text = (
        f"way_id: {row.get('way_id')}\n"
        f"ik_seq: {row.get('ik_seq')}\n"
        f"highway: {row.get('highway')}\n"
        f"bridge: {row.get('bridge')}\n"
        f"surface: {row.get('surface')}\n"
        f"source_type: {row.get('ik_source')}\n"
    )
    popup = folium.Popup(popup_text, max_width=300)
    folium.PolyLine(coords, color=color, weight=4, popup=popup).add_to(layer)

    # 加入序號標記於中點
    midpoint = row.geometry.interpolate(0.5, normalized=True)
    folium.map.Marker(
        [midpoint.y, midpoint.x],
        icon=folium.DivIcon(
            html=f"""<div style="font-size: 12px; color: black; font-weight: bold; background-color: white; border-radius: 3px; padding: 2px;">{row['ik_seq']}</div>"""
        )
    ).add_to(layer)

for fg in fgs.values():
    fg.add_to(m)

folium.Marker(location=[start_latlon[0], start_latlon[1]], popup="起點", icon=folium.Icon(color="green")).add_to(m)
folium.LayerControl(collapsed=False).add_to(m)

m.save(output_map)
print(f"✅ 完成輸出：{output_geojson}, {output_csv}, {output_map}")