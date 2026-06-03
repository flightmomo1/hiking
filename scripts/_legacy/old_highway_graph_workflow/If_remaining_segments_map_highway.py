import geopandas as gpd
import pandas as pd
import folium
from shapely.geometry import mapping

input_path = "Ic4_combined_with_tags_with_wayid.geojson"
ic3_node_path = "Ic3_osm_nodes.geojson"
output_geojson = "If_remaining_segments.geojson"
output_map = "If_remaining_segments_map_highway.html"

excluded_way_ids = ["('way', 720961392)"]

def normalize_way_id(df):
    print(f"DataFrame 欄位：{list(df.columns)}")  # 除錯用
    for candidate in ['way_id', 'way_id_str', 'way_id_std', 'id']:
        if candidate in df.columns:
            print(f"使用欄位：{candidate}")
            df['way_id_norm'] = df[candidate].astype(str)
            return df
    raise Exception("缺少 way_id/way_id_str/way_id_std/id 欄位！")

gdf = gpd.read_file(input_path)
gdf = normalize_way_id(gdf)

nodes = gpd.read_file(ic3_node_path)
nodes_keep = nodes.copy()  # 全部節點保留

filtered = gdf[~gdf["way_id_norm"].isin(excluded_way_ids)].copy()
filtered_way_ids = set(filtered["way_id_norm"])

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

if "highway_category" not in filtered.columns:
    filtered["highway_category"] = filtered["highway"].apply(classify_hw)

color_map = {
    'road': 'gray', 'trail': 'green', 'track': 'brown', 'steps': 'purple',
    'service': 'blue', 'others': 'red'
}

# 防錯補 bridge 欄位
if "bridge" not in filtered.columns:
    filtered["bridge"] = None

def is_bridge(val):
    return str(val).lower() in ["yes", "covered"]

bridge_group = filtered[filtered["bridge"].apply(is_bridge)]
other_group = filtered[~filtered["bridge"].apply(is_bridge)]

center_geom = filtered.to_crs(epsg=4326).geometry.union_all().centroid
center_point = [center_geom.y, center_geom.x]
m = folium.Map(location=center_point, zoom_start=15, tiles="CartoDB positron")

# 繪製非橋段
type_groups = other_group.groupby("highway_category")
for cat, group in type_groups:
    fg = folium.FeatureGroup(name=f"{cat}（{len(group)}）", show=True)
    for _, row in group.iterrows():
        coords = list(mapping(row.geometry)["coordinates"])
        color = color_map.get(cat, 'blue')
        popup_lines = []
        for col in [
            "way_id_norm", "name", "highway", "surface", "bridge", "steps",
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

# 繪製橋段
fg_bridge = folium.FeatureGroup(name=f"橋段（{len(bridge_group)}）", show=True)
for _, row in bridge_group.iterrows():
    coords = list(mapping(row.geometry)["coordinates"])
    popup_lines = []
    for col in [
        "way_id_norm", "name", "highway", "surface", "bridge", "steps",
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

# 繪製全部節點
fg_nodes = folium.FeatureGroup(name=f"節點（{len(nodes_keep)}）", show=False)
for _, node in nodes_keep.iterrows():
    lat, lon = node.geometry.y, node.geometry.x
    popup = f"<b>node_id:</b> {node.get('node_id','')}<br><b>way_id:</b> {node.get('way_id','')}"
    folium.CircleMarker(
        location=[lat, lon], radius=3, color="red", fill=True, fill_opacity=0.85,
        popup=popup, tooltip=node.get("node_id","")
    ).add_to(fg_nodes)
fg_nodes.add_to(m)

filtered.drop(columns=["way_id_norm"], errors="ignore").to_file(output_geojson, driver="GeoJSON")
folium.LayerControl(collapsed=False).add_to(m)
m.save(output_map)
print(f"✅ 地圖輸出：{output_map}")
print(f"✅ GeoJSON 輸出：{output_geojson}")