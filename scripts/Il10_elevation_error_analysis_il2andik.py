import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import LineString, MultiLineString, Point
from scipy.interpolate import RegularGridInterpolator
from matplotlib import font_manager

# === 字體設定（macOS 中文黑體）===
font_path = "/System/Library/Fonts/STHeiti Light.ttc"
plt.rcParams['font.family'] = font_manager.FontProperties(fname=font_path).get_name()

# === 檔案路徑設定 ===
contour_path = "/Users/iddmini/Documents/114_山力分析_山/97233NW/向量25K/ContourL.shp"
dem_npz_path = "Il2_dem_data.npz"
ik_path = "Ik_ordered_segments.geojson"
output_error_png = "Il10_elevation_error_comparison_il2.png"

# === 1. 載入 DEM ===
print("📥 載入 DEM...")
dem = np.load(dem_npz_path)
grid_x = dem["grid_x"]
grid_y = dem["grid_y"]
grid_z = dem["grid_z"]

# === 建立 DEM 插值器（注意 grid_z 需轉置）===
x_vals = grid_x[0, :]
y_vals = grid_y[:, 0]
interp_func = RegularGridInterpolator((x_vals, y_vals), grid_z.T, bounds_error=False, fill_value=np.nan)

# === 2. 載入 Ik 路段並擷取中點 ===
print("📥 載入 Ik 路段...")
gdf = gpd.read_file(ik_path)
if gdf.crs is None or gdf.crs.to_epsg() != 3826:
    print("🌐 轉換為 EPSG:3826...")
    gdf = gdf.to_crs(epsg=3826)

midpoints = []
for geom in gdf.geometry:
    if isinstance(geom, LineString):
        midpoint = geom.interpolate(0.5, normalized=True)
        midpoints.append(midpoint)

mid_gdf = gpd.GeoDataFrame({"geometry": midpoints}, crs=gdf.crs)
mid_gdf["x"] = mid_gdf.geometry.x
mid_gdf["y"] = mid_gdf.geometry.y
coords = np.vstack([mid_gdf["x"], mid_gdf["y"]]).T
mid_gdf["true_elev"] = interp_func(coords)
mid_gdf["dem_elev"] = mid_gdf["true_elev"]  # 若有外部高程來源可替換此欄位
mid_gdf["error"] = mid_gdf["dem_elev"] - mid_gdf["true_elev"]

# === 3. 載入 ContourL 節點並擷取高程 ===
print("📥 載入 ContourL 節點...")
contour_gdf = gpd.read_file(contour_path)
if contour_gdf.crs is None or contour_gdf.crs.to_epsg() != 3826:
    contour_gdf = contour_gdf.to_crs(epsg=3826)

contour_points = []
contour_z = []

for _, row in contour_gdf.iterrows():
    elev = row.get("zv2", None)
    if elev is None or not isinstance(elev, (float, int)):
        continue
    geom = row.geometry
    if isinstance(geom, LineString):
        coords = geom.coords
    elif isinstance(geom, MultiLineString):
        coords = []
        for part in geom.geoms:
            coords.extend(part.coords)
    else:
        continue
    for pt in coords:
        contour_points.append(Point(pt))
        contour_z.append(elev)

# === 建立 GeoDataFrame 並插值 DEM 高度 ===
contour_pt_gdf = gpd.GeoDataFrame(geometry=contour_points, crs=contour_gdf.crs)
contour_pt_gdf["x"] = contour_pt_gdf.geometry.x
contour_pt_gdf["y"] = contour_pt_gdf.geometry.y
contour_pt_gdf["true_elev"] = contour_z
coords_contour = np.vstack([contour_pt_gdf["x"], contour_pt_gdf["y"]]).T
contour_pt_gdf["dem_elev"] = interp_func(coords_contour)
contour_pt_gdf["error"] = contour_pt_gdf["dem_elev"] - contour_pt_gdf["true_elev"]

# === 4. 統計誤差 ===
valid_mid = mid_gdf.dropna(subset=["dem_elev", "true_elev"])
valid_contour = contour_pt_gdf.dropna(subset=["dem_elev", "true_elev"])
errors_mid = valid_mid["error"].values
errors_contour = valid_contour["error"].values

print(f"\n✅ Ik 路段中點樣本數：{len(errors_mid)}")
print(f"📊 中點誤差 - 平均：{np.mean(errors_mid):.4f} m，標準差：{np.std(errors_mid):.4f} m")

print(f"\n✅ Contour 節點樣本數：{len(errors_contour)}")
print(f"📊 等高線誤差 - 平均：{np.mean(errors_contour):.4f} m，標準差：{np.std(errors_contour):.4f} m")

# === 5. 繪圖比較誤差分布 ===
combined_errors = np.concatenate([errors_mid, errors_contour])
hist_range = (np.min(combined_errors), np.max(combined_errors))

plt.figure(figsize=(12, 6))
plt.hist(errors_mid, bins=50, range=hist_range, alpha=0.5, label=f'Ik中點 (n={len(errors_mid)})', color='skyblue', edgecolor='gray')
plt.hist(errors_contour, bins=50, range=hist_range, alpha=0.5, label=f'等高線節點 (n={len(errors_contour)})', color='orange', edgecolor='gray')
plt.axvline(np.mean(errors_mid), color="blue", linestyle="--", label=f"Ik 平均：{np.mean(errors_mid):.2f} m")
plt.axvline(np.mean(errors_contour), color="darkorange", linestyle="--", label=f"Contour 平均：{np.mean(errors_contour):.2f} m")

# 可選：對數 y 軸更好觀察樣本數差異
plt.yscale('log')
plt.title("Il2 DEM 高程誤差分布比較（對數尺度）")
plt.xlabel("誤差（DEM 插值值 - 實際高度）[m]")
plt.ylabel("樣本數（對數）")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig(output_error_png, dpi=300)
plt.close()

print(f"\n✅ 已儲存誤差圖：{output_error_png}")