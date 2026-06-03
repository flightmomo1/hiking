import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import Point
from tqdm import tqdm
from scipy.interpolate import griddata

# === 路徑設定 ===
contour_path = "/Users/iddmini/Documents/114_山力分析_山/97233NW/向量25K/ContourL.shp"  # 含 zv2 欄位
dem_output_path = "Il2_dem_data.npz"
dem_png_output_path = "Il2_dem_preview.png"

# === 參數設定 ===
sampling_interval = 5       # 等高線補點間隔（公尺）
dem_resolution = 2        # DEM 格網解析度（公尺）

# === 載入等高線 ===
print("📥 載入等高線圖層...")
contours = gpd.read_file(contour_path).to_crs(epsg=3826)

# === 補點 ===
print("📐 等高線補點中...")
elevation_points = []
for _, row in tqdm(contours.iterrows(), total=len(contours), desc="補點中"):
    elev = row["zv2"]
    line = row.geometry
    length = line.length
    n = max(int(length // sampling_interval), 2)
    for i in range(n):
        pt = line.interpolate(i / (n - 1), normalized=True)
        elevation_points.append((pt.x, pt.y, elev))

# === 格網範圍與建立 ===
print("🧭 建立格網範圍與插值資料...")
points = np.array([(x, y) for x, y, z in elevation_points])
values = np.array([z for x, y, z in elevation_points])
xmin, ymin, xmax, ymax = contours.total_bounds
grid_x, grid_y = np.meshgrid(
    np.arange(xmin, xmax, dem_resolution),
    np.arange(ymin, ymax, dem_resolution)
)

# === 分批插值並顯示進度條 ===
print("📊 正在格網插值（griddata）...")
grid_z = np.empty_like(grid_x)
for i in tqdm(range(grid_x.shape[0]), desc="插值中"):
    xi = np.column_stack([grid_x[i, :], grid_y[i, :]])
    grid_z[i, :] = griddata(points, values, xi, method="cubic", fill_value=np.nan)

# === 儲存 DEM ===
np.savez_compressed(dem_output_path, grid_x=grid_x, grid_y=grid_y, grid_z=grid_z)
print(f"✅ DEM 已儲存：{dem_output_path}")

# === 畫圖 ===
plt.figure(figsize=(10, 8))
plt.contourf(grid_x, grid_y, grid_z, levels=50, cmap="terrain")
plt.colorbar(label="Elevation (m)")
plt.title("DEM 預覽圖（全域等高線）")
plt.xlabel("X")
plt.ylabel("Y")
plt.tight_layout()
plt.savefig(dem_png_output_path, dpi=300)
plt.close()
print(f"✅ DEM 預覽圖已儲存：{dem_png_output_path}")