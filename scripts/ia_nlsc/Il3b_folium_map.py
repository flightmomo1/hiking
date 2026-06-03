import geopandas as gpd
import folium
from folium import LayerControl
from folium.plugins import Fullscreen
from tqdm import tqdm

# === 參數設定 ===
geojson_path = "Il3b_closed_zones_with_stats.geojson"
output_html = "Il3b_closed_zones_stats_map.html"
value_col = "hit_count"

# === 讀取資料 ===
print("📥 讀取 GeoJSON...")
gdf = gpd.read_file(geojson_path)

# 排除空幾何
gdf = gdf[gdf.geometry.is_valid & ~gdf.geometry.is_empty]
if gdf.empty:
    raise ValueError("❌ GeoDataFrame 為空，請確認 GeoJSON 是否正確")

# === 建立 folium 地圖 ===
center = [gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()]
m = folium.Map(location=center, zoom_start=15, tiles="CartoDB positron")
Fullscreen().add_to(m)

# === 加入分層顏色分類 ===
print("🎨 加入區域圖層（含 hit count 分級）...")
def get_color(count):
    if count < 10:
        return "#FFEDA0"
    elif count < 100:
        return "#FEB24C"
    else:
        return "#F03B20"

for _, row in tqdm(gdf.iterrows(), total=len(gdf), desc="繪製區域"):
    count = row[value_col]
    elev = row.get("min_elev", "N/A")
    color = get_color(count)

    gj = folium.GeoJson(
        data=row.geometry.__geo_interface__,
        style_function=lambda feat, col=color: {
            "fillColor": col,
            "color": "black",
            "weight": 0.3,
            "fillOpacity": 0.6,
        },
        tooltip=folium.Tooltip(f"最低高程: {elev} m<br>命中點數: {count}")
    )
    gj.add_to(m)

# === 加入圖層控制 ===
LayerControl(collapsed=False).add_to(m)

# === 儲存 HTML 地圖 ===
print(f"💾 儲存地圖至：{output_html}")
m.save(output_html)
print("✅ 完成！請開啟 HTML 檢視")