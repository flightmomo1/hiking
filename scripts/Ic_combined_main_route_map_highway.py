import geopandas as gpd
import pandas as pd
import folium
from shapely.geometry import Point, mapping

# === 1. 讀取完整圖資（I_osm_ways.geojson）===
gdf = gpd.read_file("I_osm_ways.geojson")
gdf["name"] = gdf["name"].astype(str)

# ✅ 建立字串格式的 way_id_str 欄位
gdf["way_id_str"] = gdf["way_id"].astype(str)

# === 2. 選取主路線段 ===
route_names = ["七星山步道冷水坑線", "七星山登山步道東峰線", "七星山步道主峰-東峰稜線"]
named_routes = gdf[gdf["name"].isin(route_names)].copy()

manual_ids_str = ["('way', 1228094366)", "('way', 230730601)", "('way', 492257358)",
                   "('way', 1227504496)"]
nan_clean = gdf[gdf["way_id_str"].isin(manual_ids_str)].copy()
nan_clean["name"] = nan_clean.index.map(lambda i: f"段號：{i}")

# === 3. 合併段落並建立標記欄位 ===
combined = pd.concat([named_routes, nan_clean], ignore_index=False)
combined = gpd.GeoDataFrame(combined, crs=gdf.crs)

combined["source_type"] = combined["name"].apply(lambda x: "nan" if str(x).startswith("段號：") else "named")
combined["orig_index"] = combined.index
combined["orig_name"] = combined["name"]
combined["bridge_flag"] = combined["bridge"].isin(["yes", "covered"])
combined["steps_flag"] = combined["highway"].astype(str).str.lower() == "steps"

# ✅ 中心點（使用 union_all 避免棄用警告）
center_geom = combined.to_crs(epsg=4326).geometry.union_all().centroid
center_point = [center_geom.y, center_geom.x]

# ✅ 保留字串格式 way_id_str 欄位
combined["way_id"] = combined["way_id_str"]

# === 4. 輸出 GeoJSON ===
combined.to_file("Ic_combined_main_route_segments.geojson", driver="GeoJSON")

# === 6. 建立 folium 地圖 ===
m = folium.Map(location=center_point, zoom_start=15, tiles="CartoDB positron")

# === 7. 依 highway_category 分層顯示 ===
# ✅ 用 gdf 作為繪圖來源（含完整欄位）
type_groups = combined.groupby("highway_category")

color_map = {
    'road': 'gray',
    'trail': 'green',
    'track': 'brown',
    'steps': 'purple',
    'service': 'blue',
    'non-walkable': 'black',
    'pedestrian': 'orange',
    'others': 'red'
}

for cat, group in type_groups:
    fg = folium.FeatureGroup(name=f"{cat}（{len(group)}）", show=True)
    for _, row in group.iterrows():
        coords = list(mapping(row.geometry)["coordinates"])
        color = color_map.get(cat, 'blue')

        popup_text = f"""\
<b>way_id:</b> {row.way_id}<br>
<b>name:</b> {row.get('name_display', row.get('name', ''))}<br>
<b>highway:</b> {row.get('highway_raw', row.get('highway', ''))}<br>
<b>surface:</b> {row.get('surface', '')}<br>
<b>lanes:</b> {row.get('lanes', '')}<br>
<b>cycleway:both:</b> {row.get('cycleway:both', '')}<br>
<b>bridge:</b> {row.get('bridge', '')}<br>
<b>bridge:structure:</b> {row.get('bridge:structure', '')}<br>
<b>version:</b> {row.get('version', '')}<br>
<b>changeset:</b> {row.get('changeset', '')}<br>
<b>timestamp:</b> {row.get('timestamp', '')}<br>
<b>user:</b> {row.get('user', '')}<br>
<b>uid:</b> {row.get('uid', '')}
"""
        popup = folium.Popup(popup_text, max_width=400)

        if row.geometry.geom_type == "MultiLineString":
            for line in row.geometry:
                folium.PolyLine([(lat, lon) for lon, lat in line.coords],
                                color=color, weight=2, popup=popup).add_to(fg)
        else:
            folium.PolyLine([(lat, lon) for lon, lat in coords],
                            color=color, weight=2, popup=popup).add_to(fg)
    fg.add_to(m)

# === 7b. 顯示 bridge = yes 的段落（單獨圖層） ===
bridge_group = combined[combined['bridge'].notnull()]
fg_bridge = folium.FeatureGroup(name=f"橋段（{len(bridge_group)}）", show=True)

for _, row in bridge_group.iterrows():
    coords = list(mapping(row.geometry)["coordinates"])
    popup_text = f"""\
<b>way_id:</b> {row.way_id}<br>
<b>name:</b> {row.get('name', '')}<br>
<b>highway:</b> {row.get('highway_raw', row.get('highway', ''))}<br>
<b>bridge:</b> {row.get('bridge', '')}<br>
<b>surface:</b> {row.get('surface', '')}
"""
    popup = folium.Popup(popup_text, max_width=400)
    color = 'red'

    if row.geometry.geom_type == "MultiLineString":
        for line in row.geometry:
            folium.PolyLine([(lat, lon) for lon, lat in line.coords],
                            color=color, weight=3, popup=popup).add_to(fg_bridge)
    else:
        folium.PolyLine([(lat, lon) for lon, lat in coords],
                        color=color, weight=3, popup=popup).add_to(fg_bridge)

fg_bridge.add_to(m)

# === 8. 加入圖層控制與輸出 ===
folium.LayerControl(collapsed=False).add_to(m)
m.save("Ic_combined_main_route_segments_map.html")

print("✅ 主路線輸出完成！")
print(f"📦 總段數：{len(combined)}（命名：{len(named_routes)}，無名段：{len(nan_clean)}）")