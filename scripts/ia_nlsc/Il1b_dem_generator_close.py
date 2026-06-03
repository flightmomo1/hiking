import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from scipy.interpolate import griddata
import matplotlib
from tqdm import tqdm

matplotlib.rcParams["font.sans-serif"] = ["AppleGothic"]
matplotlib.rcParams["axes.unicode_minus"] = False

# === 參數設定 ===
contour_path = "/Users/iddmini/Documents/114_山力分析_山/97233NW/向量25K/ContourL.shp"
elev_col = "zv2"
output_png = "Il1b_dem_with_closed_areas.png"
output_npz = "Il1b_dem_data_with_closed_areas.npz"

# === 1. 讀取等高線並整理 ===
gdf = gpd.read_file(contour_path)
gdf[elev_col] = pd.to_numeric(gdf[elev_col], errors="coerce")
gdf = gdf[gdf.geometry.type == "LineString"]
gdf = gdf[gdf[elev_col].notnull()]
gdf = gdf.to_crs(epsg=3826)

# === 2. 取樣節點與高程 ===
sample_points = []
sample_values = []
for _, row in gdf.iterrows():
    coords = list(row.geometry.coords)
    z = row[elev_col]
    for x, y in coords:
        sample_points.append((x, y))
        sample_values.append(z)
sample_points = np.array(sample_points)
sample_values = np.array(sample_values)

# === 3. 建立封閉高程區域 ===
closed_polygons = []
polygon_elevs = []
buffer_dist = 0.5  # 緩衝距離(公尺)

print("🛡️ 建立封閉高程區...")
unique_elevs = sorted(gdf[elev_col].unique(), reverse=True)
for elev in tqdm(unique_elevs, desc="封閉高程區進度"):
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

# === 4. 建立插值網格 ===
minx, miny, maxx, maxy = gdf.total_bounds
grid_x, grid_y = np.mgrid[minx:maxx:500j, miny:maxy:500j]

# === 5. 進行 cubic 插值 DEM ===
grid_z = griddata(sample_points, sample_values, (grid_x, grid_y), method="cubic")

# === 6. 封閉區域限制 DEM 高程（向量化優化版） ===
print("📐 封閉區域限制 DEM 高程...")
for idx, row in tqdm(zone_gdf.iterrows(), total=len(zone_gdf), desc="封閉區 DEM 限制"):
    polygon: Polygon = row.geometry
    min_elev = row["min_elev"]

    # 建立網格點坐標陣列
    pts = np.vstack((grid_x.ravel(), grid_y.ravel())).T

    # 判斷哪些點在多邊形內（用 GeoPandas 快速判斷）
    pts_gdf = gpd.GeoSeries([Point(x, y) for x, y in pts], crs=3826)
    mask = pts_gdf.within(polygon).values

    # 只調整在多邊形內的點
    inside_idx = np.where(mask)[0]

    for i in inside_idx:
        ix = i // grid_x.shape[1]
        iy = i % grid_x.shape[1]
        if np.isnan(grid_z[ix, iy]) or grid_z[ix, iy] < min_elev:
            grid_z[ix, iy] = min_elev

# === 7. 儲存 DEM 數據 ===
np.savez_compressed(output_npz, grid_x=grid_x, grid_y=grid_y, grid_z=grid_z)
print(f"✅ 已儲存 DEM 數據：{output_npz}")

# === 8. 繪製 DEM 色階圖 ===
plt.figure(figsize=(10, 8))
plt.imshow(grid_z.T, extent=(minx, maxx, miny, maxy),
           origin="lower", cmap="terrain")
plt.colorbar(label="Elevation (m)")
plt.title("封閉高程區域限制的 DEM")
plt.xlabel("X (m)")
plt.ylabel("Y (m)")
plt.tight_layout()
plt.savefig(output_png, dpi=300)
plt.close()
print(f"✅ 已儲存 DEM 圖像：{output_png}")