import geopandas as gpd
import folium
from shapely.geometry import LineString
import pandas as pd
import re

# 檔案設定
input_path = "If2_split_by_nodes.geojson"           # if3 輸出路線（含流水號）
ic4_path = "Ic4_combined_with_tags_with_wayid.geojson"  # 完整 ic4 原始路線（含節點串）

output_geojson = "If3_final_segments_with_ic4_details.geojson"
output_map = "If3_final_segments_with_ic4_details_map.html"

# 讀取資料
gdf_if3 = gpd.read_file(input_path)
gdf_ic4 = gpd.read_file(ic4_path)

# 去除流水號，還原原始 way_id
def strip_suffix(wid):
    return re.sub(r"_[0-9]+$", "", str(wid))
gdf_if3["way_id_original"] = gdf_if3["way_id"].apply(strip_suffix)

# 確認 ic4 的 way_id 欄位名稱
if "way_id" in gdf_ic4.columns:
    gdf_ic4["way_id_original"] = gdf_ic4["way_id"].astype(str)
else:
    raise ValueError("Ic4 中找不到 'way_id' 欄位")

# 欄位改名避免衝突，先檢查欄位是否存在
cols_to_rename = {}
for col, new_col in [
    ("bridge", "bridge_ic4"),
    ("highway", "highway_ic4"),
    ("surface", "surface_ic4"),
    ("node_ids_str", "node_ids_str_ic4"),
    ("steps", "steps_ic4"),
]:
    if col in gdf_ic4.columns:
      if gdf_ic4[col].notna().sum() == 0:
        print(f"⚠️ 注意：Ic4 的欄位 '{col}' 雖存在，但所有值為空")
      cols_to_rename[col] = new_col
    else:
        print(f"⚠️ 注意：Ic4 沒有欄位 '{col}'，將無法合併此欄位")

gdf_ic4 = gdf_ic4.rename(columns=cols_to_rename)

# 選取實際存在的欄位進行合併
merge_cols = ["way_id_original"]
merge_cols += list(cols_to_rename.values())

gdf_merged = gdf_if3.merge(
    gdf_ic4[merge_cols],
    on="way_id_original", how="left"
)

# 欄位回填，若欄位不存在或合併後全是空值，使用預設值
def fill_default(df, colname, default):
    if colname not in df.columns:
        df[colname] = default
    else:
        df[colname] = df[colname].fillna(default)

fill_default(gdf_merged, "bridge", "no")
fill_default(gdf_merged, "highway", "road")
fill_default(gdf_merged, "surface", "")
fill_default(gdf_merged, "steps", "")

# 節點串解析，欄位存在才解析
def parse_node_ids(s):
    if pd.isna(s) or s == "":
        return []
    return s.split(";")

if "node_ids_str_ic4" in gdf_merged.columns:
    gdf_merged["node_ids"] = gdf_merged["node_ids_str_ic4"].apply(parse_node_ids)
else:
    gdf_merged["node_ids"] = [[] for _ in range(len(gdf_merged))]

# 起訖節點
gdf_merged["start_node"] = gdf_merged["node_ids"].apply(lambda x: x[0] if len(x) > 0 else None)
gdf_merged["end_node"] = gdf_merged["node_ids"].apply(lambda x: x[-1] if len(x) > 0 else None)

# 清理輔助欄位
drop_cols = list(cols_to_rename.values())
drop_cols.append("node_ids_str_ic4")
gdf_merged.drop(columns=[c for c in drop_cols if c in gdf_merged.columns], inplace=True)

# 分類函數（可依需求擴充）
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

gdf_merged["highway_category"] = gdf_merged["highway"].apply(classify_hw)

# 配色表
color_map = {
    'road': 'gray',
    'service': 'blue',
    'steps': 'purple',
    'trail': 'green',
    'track': 'brown',
    'others': 'red',
}

def is_bridge(val):
    return str(val).lower() == "yes"

# 建立地圖中心
if not gdf_merged.empty:
    projected = gdf_merged.to_crs(epsg=3826)
    centroid_3826 = projected.geometry.centroid.union_all().centroid
    centroid_gdf = gpd.GeoSeries([centroid_3826], crs="EPSG:3826").to_crs(epsg=4326)
    center = centroid_gdf.iloc[0]
    m = folium.Map(location=[center.y, center.x], zoom_start=16, tiles="CartoDB positron")
else:
    m = folium.Map(location=[25.0, 121.5], zoom_start=8, tiles="CartoDB positron")

# 建立圖層
fg_bridge = folium.FeatureGroup(name=f"橋段（{len(gdf_merged[gdf_merged['bridge'].apply(is_bridge)])}）", show=True)
fg_road = folium.FeatureGroup(name=f"road（{len(gdf_merged[gdf_merged['highway_category']=='road'])}）", show=True)
fg_service = folium.FeatureGroup(name=f"service（{len(gdf_merged[gdf_merged['highway_category']=='service'])}）", show=True)
fg_steps = folium.FeatureGroup(name=f"steps（{len(gdf_merged[gdf_merged['highway_category']=='steps'])}）", show=True)
fg_trail = folium.FeatureGroup(name=f"trail（{len(gdf_merged[gdf_merged['highway_category']=='trail'])}）", show=True)
fg_others = folium.FeatureGroup(name=f"others（{len(gdf_merged[gdf_merged['highway_category']=='others'])}）", show=False)

for _, row in gdf_merged.iterrows():
    geom = row.geometry
    bridge_flag = is_bridge(row['bridge'])
    hw_cat = row['highway_category']
    color = 'red' if bridge_flag else color_map.get(hw_cat, 'gray')

    target_fg = fg_bridge if bridge_flag else {
        'road': fg_road,
        'service': fg_service,
        'steps': fg_steps,
        'trail': fg_trail,
        'others': fg_others
    }.get(hw_cat, fg_others)

    popup_lines = [
        f"<b>way_id:</b> {row['way_id']}",
        f"<b>bridge:</b> {row['bridge']}",
        f"<b>highway:</b> {row['highway']}",
        f"<b>surface:</b> {row['surface']}",
        f"<b>steps:</b> {row.get('steps', '')}",
        f"<b>起點 node:</b> {row.get('start_node', '')}",
        f"<b>終點 node:</b> {row.get('end_node', '')}",
    ]
    popup = folium.Popup("<br>".join(popup_lines), max_width=400)

    if geom.geom_type == "MultiLineString":
        for line in geom:
            folium.PolyLine(
                locations=[(lat, lon) for lon, lat in line.coords],
                color=color, weight=4,
                popup=popup
            ).add_to(target_fg)
    else:
        folium.PolyLine(
            locations=[(lat, lon) for lon, lat in geom.coords],
            color=color, weight=4,
            popup=popup
        ).add_to(target_fg)

fg_bridge.add_to(m)
fg_road.add_to(m)
fg_service.add_to(m)
fg_steps.add_to(m)
fg_trail.add_to(m)
fg_others.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)

m.save(output_map)
print(f"✅ 地圖輸出：{output_map}")
gdf_merged.to_file(output_geojson, driver="GeoJSON")
print(f"✅ GeoJSON 輸出：{output_geojson}")