import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from shapely.ops import split
import numpy as np
import folium
import re

# === 你直接貼 node_id / way_id 對在這裡 ===
raw_str = """
node_id: 675814711
way_id: 1228094366
"""

# --- robust way_id 轉純數字（for tuple/str/int都支援） ---
def normalize_wayid(val):
    s = str(val)
    m = re.search(r'(\d+)', s)
    return m.group(1) if m else s

# === 檔案設定 ===
way_file = "If_remaining_segments.geojson"  # 已剔除不想要路段的檔案
node_file = "Ic3_osm_nodes.geojson"
output_file = "If2_split_by_nodes.geojson"
output_map = "If2_split_by_nodes_map.html"

excluded_way_ids = set([
    "1228094366_1"
])

# === 目標節點/way組合 ===
split_targets = []
matches = re.findall(r"node_id:\s*(\d+)\s*way_id:\s*(\d+)", raw_str)
for node_id, way_id in matches:
    split_targets.append((str(node_id), str(way_id)))  # 轉成 str

# === 讀資料，way_id 自動正規化 ===
gdf = gpd.read_file(way_file)
nodes = gpd.read_file(node_file)
nodes["node_id"] = nodes["node_id"].astype(str)

wayid_col_candidates = [c for c in gdf.columns if "way_id" in c or c == "id"]
if len(wayid_col_candidates) == 0:
    print("⚠️ 警告：找不到 way_id 或 id 欄位，跳過分割動作。")
    # 直接匯出原檔並建立空地圖
    gdf.to_file(output_file, driver="GeoJSON")
    m = folium.Map(location=[25.0, 121.5], zoom_start=8)
    folium.LayerControl(collapsed=False).add_to(m)
    m.save(output_map)
    print(f"✅ 完成所有分割，輸出：{output_file}")
    print(f"✅ 地圖輸出：{output_map}")
    exit(0)

wayid_col = wayid_col_candidates[0]
gdf["way_id_norm"] = gdf[wayid_col].apply(normalize_wayid)
nodes["way_id_norm"] = nodes["way_id"].apply(normalize_wayid)

# 分類 highway 類型，與 If.py 保持一致
def classify_hw(hw):
    hw = str(hw).lower()
    if hw in ["path", "trail", "footway"]:
        return "trail"
    if hw == "road":
        return "road"
    if hw == "steps":
        return "steps"
    if hw == "service":
        return "service"
    if hw == "track":
        return "track"
    return "others"

if "highway_category" not in gdf.columns:
    gdf["highway_category"] = gdf["highway"].apply(classify_hw)

color_map = {
    'road': 'gray',
    'trail': 'green',
    'track': 'brown',
    'steps': 'purple',
    'service': 'blue',
    'others': 'red'
}

# 防錯：補 bridge 欄位
if "bridge" not in gdf.columns:
    gdf["bridge"] = None

def is_bridge(val):
    return str(val).lower() in ["yes", "covered"]

# --- 分割路段 ---
way_to_nodes = {}
for node_id, way_id in split_targets:
    way_to_nodes.setdefault(normalize_wayid(way_id), []).append(node_id)

new_records = []
drop_way_ids = set()
for way_id_norm, node_id_list in way_to_nodes.items():
    line_row = gdf[gdf["way_id_norm"] == way_id_norm]
    if line_row.empty:
        print(f"❌ 找不到 way_id {way_id_norm}")
        continue
    line = line_row.geometry.iloc[0]
    node_coords = []
    for nid in node_id_list:
        node_row = nodes[(nodes["node_id"] == nid) & (nodes["way_id_norm"] == way_id_norm)]
        if node_row.empty:
            print(f"❌ 找不到 node_id {nid} (way_id={way_id_norm})")
            continue
        node_coords.append((float(node_row.geometry.x.iloc[0]), float(node_row.geometry.y.iloc[0])))
    if not node_coords:
        continue
    distances = [line.project(Point(x, y)) for x, y in node_coords]
    sort_idx = np.argsort(distances)
    sorted_points = [Point(node_coords[i]) for i in sort_idx]
    segs = [line]
    for pt in sorted_points:
        segs_new = []
        for s in segs:
            splitted = split(s, pt)
            if len(splitted.geoms) == 1:
                segs_new.append(splitted.geoms[0])
            else:
                segs_new.extend(splitted.geoms)
        segs = segs_new
    for i, seg in enumerate(segs, 1):
        row = line_row.iloc[0].copy()
        row["geometry"] = seg
        row["way_id"] = f"{line_row[wayid_col].iloc[0]}_{i}"
        row["way_id_norm"] = f"{way_id_norm}_{i}"
        new_records.append(row)
    drop_way_ids.add(way_id_norm)

gdf_keep = gdf[~gdf["way_id_norm"].isin(drop_way_ids)].copy()

if new_records:
    new_gdf = gpd.GeoDataFrame(new_records, geometry="geometry")
    new_gdf = new_gdf.set_crs(gdf.crs, allow_override=True)
    result_gdf = pd.concat([gdf_keep, new_gdf]).reset_index(drop=True)
    result_gdf = gpd.GeoDataFrame(result_gdf, geometry="geometry", crs=gdf.crs)
else:
    result_gdf = gdf_keep.copy()

# 先剔除粗篩時排除路段，避免在地圖顯示
result_gdf_filtered = result_gdf[~result_gdf["way_id_norm"].isin(excluded_way_ids)].copy()

result_gdf_filtered.to_file(output_file, driver="GeoJSON")
print(f"✅ 完成所有分割，輸出：{output_file}")

# --- 地圖中心點 ---
if not result_gdf_filtered.empty:
    projected = result_gdf_filtered.to_crs(epsg=3826)
    centroid_3826 = projected.geometry.centroid.union_all().centroid
    centroid_gdf = gpd.GeoSeries([centroid_3826], crs="EPSG:3826").to_crs(epsg=4326)
    center = centroid_gdf.iloc[0]
    m = folium.Map(location=[center.y, center.x], zoom_start=16, tiles="CartoDB positron")
else:
    m = folium.Map(location=[25.0, 121.5], zoom_start=8, tiles="CartoDB positron")

# --- 繪製非橋段 ---
type_groups = result_gdf_filtered[~result_gdf_filtered["bridge"].apply(is_bridge)].groupby("highway_category")
for cat, group in type_groups:
    fg = folium.FeatureGroup(name=f"{cat}（{len(group)}）", show=True)
    for _, row in group.iterrows():
        coords = []
        if row.geometry.geom_type == "LineString":
            coords = list(row.geometry.coords)
        elif row.geometry.geom_type == "MultiLineString":
            for line in row.geometry:
                coords.extend(list(line.coords))
        color = color_map.get(cat, 'blue')
        popup_lines = []
        for col in [
            "way_id", "name", "highway", "surface", "bridge", "steps",
            "trail_visibility", "sac_scale", "version", "timestamp", "user", "uid"
        ]:
            val = row.get(col)
            if pd.notnull(val) and val != "":
                popup_lines.append(f"<b>{col}:</b> {val}")
        node_ids_str = row.get("node_ids_str", "")
        if pd.notnull(node_ids_str) and node_ids_str != "":
            node_ids = node_ids_str.split(";")
            node_id_chunks = [';'.join(node_ids[i:i+8]) for i in range(0, len(node_ids), 8)]
            popup_lines.append(f"<b>node_ids:</b><br>" + "<br>".join(node_id_chunks))
        popup_text = "<br>".join(popup_lines)
        if row.geometry.geom_type == "MultiLineString":
            for line in row.geometry:
                folium.PolyLine([(lat, lon) for lon, lat in line.coords], color=color, weight=2, popup=folium.Popup(popup_text, max_width=500)).add_to(fg)
        else:
            folium.PolyLine([(lat, lon) for lon, lat in coords], color=color, weight=2, popup=folium.Popup(popup_text, max_width=500)).add_to(fg)
    fg.add_to(m)

# --- 繪製橋段 ---
fg_bridge = folium.FeatureGroup(name=f"橋段（{len(result_gdf_filtered[result_gdf_filtered['bridge'].apply(is_bridge)])}）", show=True)
for _, row in result_gdf_filtered[result_gdf_filtered["bridge"].apply(is_bridge)].iterrows():
    coords = []
    if row.geometry.geom_type == "LineString":
        coords = list(row.geometry.coords)
    elif row.geometry.geom_type == "MultiLineString":
        for line in row.geometry:
            coords.extend(list(line.coords))
    popup_lines = []
    for col in [
        "way_id", "name", "highway", "surface", "bridge", "steps",
        "trail_visibility", "sac_scale", "version", "timestamp", "user", "uid"
    ]:
        val = row.get(col)
        if pd.notnull(val) and val != "":
            popup_lines.append(f"<b>{col}:</b> {val}")
    node_ids_str = row.get("node_ids_str", "")
    if pd.notnull(node_ids_str) and node_ids_str != "":
        node_ids = node_ids_str.split(";")
        node_id_chunks = [';'.join(node_ids[i:i+8]) for i in range(0, len(node_ids), 8)]
        popup_lines.append(f"<b>node_ids:</b><br>" + "<br>".join(node_id_chunks))
    popup_text = "<br>".join(popup_lines)
    if row.geometry.geom_type == "MultiLineString":
        for line in row.geometry:
            folium.PolyLine([(lat, lon) for lon, lat in line.coords], color="red", weight=3, popup=folium.Popup(popup_text, max_width=500)).add_to(fg_bridge)
    else:
        folium.PolyLine([(lat, lon) for lon, lat in coords], color="red", weight=3, popup=folium.Popup(popup_text, max_width=500)).add_to(fg_bridge)
fg_bridge.add_to(m)

# --- 繪製全部節點 ---
fg_allnodes = folium.FeatureGroup(name=f"節點（{len(nodes)}）", show=False)
for _, row in nodes.iterrows():
    folium.CircleMarker(
        location=[row.geometry.y, row.geometry.x],
        radius=3,
        color="orange",
        fill=True,
        fill_opacity=0.7,
        popup=folium.Popup(f"<b>node_id:</b> {row['node_id']}<br><b>way_id:</b> {row['way_id']}", max_width=250),
        tooltip=row['node_id']
    ).add_to(fg_allnodes)
fg_allnodes.add_to(m)

# --- 分割用節點圖層 ---
used_nodes = nodes[nodes["node_id"].isin([nid for nid, _ in split_targets])]
fg_splitted_nodes = folium.FeatureGroup(name=f"分割節點（{len(used_nodes)}）", show=True)
for _, row in used_nodes.iterrows():
    folium.CircleMarker(
        location=[row.geometry.y, row.geometry.x],
        radius=5,
        color='red',
        fill=True,
        fill_opacity=0.95,
        popup=folium.Popup(f"<b>node_id:</b> {row['node_id']}<br><b>way_id:</b> {row['way_id']}", max_width=250),
        tooltip=row['node_id']
    ).add_to(fg_splitted_nodes)
fg_splitted_nodes.add_to(m)

# 圖層控制
folium.LayerControl(collapsed=False).add_to(m)
m.save(output_map)
print(f"✅ 地圖輸出：{output_map}")