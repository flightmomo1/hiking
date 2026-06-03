import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import Point
from tqdm import tqdm
import pandas as pd

# === 參數設定 ===
dem_path = "Il1b_dem_data_with_closed_areas.npz"
contour_path = "/Users/iddmini/Documents/114_山力分析_山/97233NW/向量25K/ContourL.shp"
elev_col = "zv2"
output_csv = "Il2b_closed_zone_stats.csv"
output_png = "Il2b_closed_zone_hits.png"

# === 載入 DEM ===
data = np.load(dem_path)
grid_x = data["grid_x"]
grid_y = data["grid_y"]
grid_z = data["grid_z"]

# === 載入等高線並轉為封閉區 ===
gdf = gpd.read_file(contour_path)
gdf = gdf[gdf.geometry.type == "LineString"]
gdf[elev_col] = pd.to_numeric(gdf[elev_col], errors="coerce")
gdf = gdf[gdf[elev_col].notnull()]
gdf = gdf.to_crs(epsg=3826)

# 建立封閉多邊形區域（與 Il1b 一致）
from shapely.ops import unary_union
closed_polygons = []
polygon_elevs = []
buffer_dist = 0.5
unique_elevs = sorted(gdf[elev_col].unique(), reverse=True)
for elev in tqdm(unique_elevs, desc="封閉區構建"):
    subset = gdf[gdf[elev_col] == elev]
    buffered = subset.buffer(buffer_dist)
    unioned = unary_union(buffered)
    if unioned.geom_type == "Polygon":
        closed_polygons.append(unioned)
        polygon_elevs.append(elev)
    elif unioned.geom_type == "MultiPolygon":
        for poly in unioned.geoms:
            closed_polygons.append(poly)
            polygon_elevs.append(elev)

zone_gdf = gpd.GeoDataFrame({"min_elev": polygon_elevs}, geometry=closed_polygons, crs=3826)

# === 統計每個封閉區有多少 DEM 點落入 ===
print("📊 分析每個封閉區中落入的 DEM 點數...")
all_pts = np.vstack((grid_x.ravel(), grid_y.ravel())).T
all_geoms = [Point(x, y) for x, y in all_pts]
all_gseries = gpd.GeoSeries(all_geoms, crs=3826)

hit_counts = []
for _, row in tqdm(zone_gdf.iterrows(), total=len(zone_gdf), desc="Hit count"):
    polygon = row.geometry
    hits = all_gseries.within(polygon)
    count = hits.sum()
    hit_counts.append(count)

zone_gdf["hit_count"] = hit_counts
zone_gdf = zone_gdf.sort_values(by="hit_count", ascending=False)

# === 儲存統計表 ===
zone_gdf[["min_elev", "hit_count"]].to_csv(output_csv, index=False)
print(f"✅ 已儲存 hit count 統計表：{output_csv}")

# === 繪圖 ===
fig, ax = plt.subplots(figsize=(10, 10))
zone_gdf.plot(column="hit_count", cmap="Reds", legend=True, ax=ax, linewidth=0.3, edgecolor="black")
plt.title("Il1b DEM 命中封閉高程區統計圖")
plt.xlabel("X")
plt.ylabel("Y")
plt.axis("equal")
plt.tight_layout()
plt.savefig(output_png, dpi=300)
plt.close()
print(f"✅ 已儲存圖像：{output_png}")