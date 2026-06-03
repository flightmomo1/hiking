import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from scipy.interpolate import griddata
import matplotlib
from tqdm import tqdm

matplotlib.rcParams["font.sans-serif"] = ["AppleGothic"]
matplotlib.rcParams["axes.unicode_minus"] = False

# === 參數設定 ===
contour_path = "/Users/iddmini/Documents/114_山力分析_山/97233NW/向量25K/ContourL.shp"
elev_col = "zv2"
output_npz = "Il1c_dem_data_with_closed_areas.npz"
output_dem_full_png = "Il1c_dem_interpolated.png"
output_dem_limited_png = "Il1c_dem_with_closed_areas.png"
output_zones_png = "Il1c_closed_area_zones.png"
buffer_dist = 3.0  # <<< ✅ 可調整：封閉區緩衝距離（單位：公尺）

# === 1. 讀取等高線 ===
gdf = gpd.read_file(contour_path)
gdf[elev_col] = pd.to_numeric(gdf[elev_col], errors="coerce")
gdf = gdf[gdf.geometry.type == "LineString"]
gdf = gdf[gdf[elev_col].notnull()]
gdf = gdf.to_crs(epsg=3826)

# === 2. 擷取節點作為 DEM 插值點 ===
sample_points, sample_values = [], []
for _, row in gdf.iterrows():
    coords = list(row.geometry.coords)
    z = row[elev_col]
    for x, y in coords:
        sample_points.append((x, y))
        sample_values.append(z)
sample_points = np.array(sample_points)
sample_values = np.array(sample_values)

# === 3. 建立封閉等高線區域 ===
print(f"🛡️ 建立封閉高程區 (buffer={buffer_dist}m)...")
closed_polygons, polygon_elevs = [], []
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
print("✅ 建立封閉區塊數量:", len(zone_gdf))

# === 可視化封閉區塊 ===
plt.figure(figsize=(10, 8))
zone_gdf.plot(column="min_elev", cmap="terrain", legend=True)
plt.title("封閉等高線區域分布")
plt.xlabel("X")
plt.ylabel("Y")
plt.tight_layout()
plt.savefig(output_zones_png, dpi=300)
plt.close()

# === 4. 建立插值 DEM 網格 ===
minx, miny, maxx, maxy = gdf.total_bounds
grid_x, grid_y = np.mgrid[minx:maxx:500j, miny:maxy:500j]
grid_z = griddata(sample_points, sample_values, (grid_x, grid_y), method="cubic")

# === 5. 保留原始插值圖（未限制） ===
plt.figure(figsize=(10, 8))
plt.imshow(grid_z.T, extent=(minx, maxx, miny, maxy), origin="lower", cmap="terrain")
plt.colorbar(label="Elevation (m)")
plt.title("原始 DEM 插值（未限制）")
plt.xlabel("X (m)")
plt.ylabel("Y (m)")
plt.tight_layout()
plt.savefig(output_dem_full_png, dpi=300)
plt.close()

# === 6. 限制封閉區內不得低於 min_elev ===
print("📐 套用封閉區高程限制...")
for idx, row in tqdm(zone_gdf.iterrows(), total=len(zone_gdf), desc="封閉區 DEM 限制"):
    polygon: Polygon = row.geometry
    min_elev = row["min_elev"]
    pts = np.vstack((grid_x.ravel(), grid_y.ravel())).T
    pts_gdf = gpd.GeoSeries([Point(x, y) for x, y in pts], crs=3826)
    mask = pts_gdf.within(polygon).values
    inside_idx = np.where(mask)[0]
    for i in inside_idx:
        ix = i // grid_x.shape[1]
        iy = i % grid_x.shape[1]
        if np.isnan(grid_z[ix, iy]) or grid_z[ix, iy] < min_elev:
            grid_z[ix, iy] = min_elev

# === 7. 儲存 DEM 數據與結果圖 ===
np.savez_compressed(output_npz, grid_x=grid_x, grid_y=grid_y, grid_z=grid_z)
print(f"✅ 儲存 DEM：{output_npz}")

plt.figure(figsize=(10, 8))
plt.imshow(grid_z.T, extent=(minx, maxx, miny, maxy), origin="lower", cmap="terrain")
plt.colorbar(label="Elevation (m)")
plt.title("限制封閉區後 DEM")
plt.xlabel("X")
plt.ylabel("Y")
plt.tight_layout()
plt.savefig(output_dem_limited_png, dpi=300)
plt.close()
print(f"✅ 儲存 DEM 圖像：{output_dem_limited_png}")