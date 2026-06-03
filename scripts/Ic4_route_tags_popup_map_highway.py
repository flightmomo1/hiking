import geopandas as gpd
import pandas as pd
import folium
from shapely.geometry import mapping

# === 檔案設定 ===
route_path = "Ic_combined_main_route_segments.geojson"
tag_path = "Ic2_osm_way_tag_results.csv"
node_path = "Ic3_osm_nodes.geojson"
output_geojson = "Ic4_combined_with_tags_with_wayid.geojson"
output_map = "Ic4_route_tags_popup_map_highway.html"

# === 資料正規化：統一 way_id 欄位名稱與型態 ===
def normalize_way_id(df):
    # 嘗試自動找適合欄位，並轉為字串
    for key in ['way_id', 'way_id_str', 'way_id_std', 'id']:
        if key in df.columns:
            df = df.copy()
            df["way_id"] = df[key].astype(str)
            return df
    raise Exception("缺少 way_id/way_id_str/way_id_std/id 欄位！")

# === 1. 讀主路線段 ===
gdf = gpd.read_file(route_path)
gdf = normalize_way_id(gdf)

# === 2. 讀 tag ===
tags_df = pd.read_csv(tag_path, dtype=str)
tags_df = normalize_way_id(tags_df)

# === 3. 合併 tags（確保所有欄位型態一致） ===
merge_cols = [
    "way_id", "version", "changeset", "timestamp", "user", "uid",
    "highway", "surface", "trail_visibility", "bridge", "node_ids_str"
]
gdf = gdf.merge(tags_df[merge_cols], on="way_id", how="left", suffixes=("", "_api"))

# === 4. highway 分類 ===
def classify_highway(hw):
    hw = str(hw).lower()
    if hw in ["tertiary", "residential", "unclassified", "primary", "living_street", "road"]:
        return "road"
    elif hw in ["footway", "path", "trail"]:
        return "trail"
    elif hw == "service":
        return "service"
    elif hw == "steps":
        return "steps"
    elif hw == "track":
        return "track"
    elif hw in ["milestone", "bus_stop"]:
        return "non-walkable"
    elif hw == "pedestrian":
        return "pedestrian"
    else:
        return "others"
gdf["highway_category"] = gdf["highway"].apply(classify_highway)

# === 5. 儲存合併結果 ===
gdf.to_file(output_geojson, driver="GeoJSON")
print(f"✅ 已儲存：{output_geojson}")

# === 6. 地圖中心 ===
center_geom = gdf.to_crs(epsg=4326).geometry.union_all().centroid
center_point = [center_geom.y, center_geom.x]
m = folium.Map(location=center_point, zoom_start=15, tiles="CartoDB positron")

color_map = {
    'road': 'gray', 'trail': 'green', 'track': 'brown', 'steps': 'purple',
    'service': 'blue', 'non-walkable': 'black', 'pedestrian': 'orange', 'others': 'red'
}

# === 7. 主路線圖層 ===
for cat, group in gdf.groupby("highway_category"):
    fg = folium.FeatureGroup(name=f"{cat}（{len(group)}）", show=True)
    for _, row in group.iterrows():
        coords = list(mapping(row.geometry)["coordinates"])
        color = color_map.get(cat, 'blue')
        popup_text = f"""\
<b>way_id:</b> {row.way_id}<br>
<b>name:</b> {row.get('name', '')}<br>
<b>highway:</b> {row.get('highway', '')}<br>
<b>surface:</b> {row.get('surface', '')}<br>
<b>trail_visibility:</b> {row.get('trail_visibility', '')}<br>
<b>bridge:</b> {row.get('bridge', '')}<br>
<b>version:</b> {row.get('version', '')}<br>
<b>changeset:</b> {row.get('changeset', '')}<br>
<b>timestamp:</b> {row.get('timestamp', '')}<br>
<b>user:</b> {row.get('user', '')}<br>
<b>uid:</b> {row.get('uid', '')}<br>
<b>node_ids:</b> {row.get('node_ids_str', '')}
"""
        popup = folium.Popup(popup_text, max_width=420)
        if row.geometry.geom_type == "MultiLineString":
            for line in row.geometry:
                folium.PolyLine([(lat, lon) for lon, lat in line.coords],
                                color=color, weight=3, popup=popup).add_to(fg)
        else:
            folium.PolyLine([(lat, lon) for lon, lat in coords],
                            color=color, weight=3, popup=popup).add_to(fg)
    fg.add_to(m)

# === 8. 橋段圖層 ===
bridge_group = gdf[gdf['bridge'].fillna('').str.lower().isin(['yes','covered','movable','suspension'])]
fg_bridge = folium.FeatureGroup(name=f"橋段（{len(bridge_group)}）", show=True)
for _, row in bridge_group.iterrows():
    coords = list(mapping(row.geometry)["coordinates"])
    popup_text = f"""\
<b>way_id:</b> {row.way_id}<br>
<b>name:</b> {row.get('name', '')}<br>
<b>highway:</b> {row.get('highway', '')}<br>
<b>bridge:</b> {row.get('bridge', '')}<br>
<b>surface:</b> {row.get('surface', '')}<br>
<b>node_ids:</b> {row.get('node_ids_str', '')}
"""
    popup = folium.Popup(popup_text, max_width=420)
    color = 'red'
    if row.geometry.geom_type == "MultiLineString":
        for line in row.geometry:
            folium.PolyLine([(lat, lon) for lon, lat in line.coords],
                            color=color, weight=4, popup=popup).add_to(fg_bridge)
    else:
        folium.PolyLine([(lat, lon) for lon, lat in coords],
                        color=color, weight=4, popup=popup).add_to(fg_bridge)
fg_bridge.add_to(m)

# === 9. 節點圖層 ===
try:
    nodes_gdf = gpd.read_file(node_path)
    nodes_gdf = normalize_way_id(nodes_gdf)
    fg_nodes = folium.FeatureGroup(name=f"節點（{len(nodes_gdf)}）", show=False)
    for _, node in nodes_gdf.iterrows():
        geom = node.geometry
        if geom is None or geom.is_empty:
            continue  # 跳過無效幾何點
        lat, lon = node.geometry.y, node.geometry.x
        popup = f"<b>node_id:</b> {node.get('node_id','')}<br><b>way_id:</b> {node.get('way_id','')}"
        folium.CircleMarker(
            location=[lat, lon], radius=3, color="red", fill=True, fill_opacity=0.85, popup=popup
        ).add_to(fg_nodes)
    fg_nodes.add_to(m)
except Exception as e:
    print(f"⚠️ 節點圖層讀取失敗：{e}")

folium.LayerControl(collapsed=False).add_to(m)
m.save(output_map)
print(f"✅ Ic4 互動地圖輸出完成！")