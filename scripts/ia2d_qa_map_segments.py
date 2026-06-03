from pathlib import Path
import geopandas as gpd
import folium


"""
ia2d_qa_map_segments_light.py

定位：
- ia 系列第二階段的輕量 QA 地圖腳本
- 專門用來檢查 ia2c 高程專用版的 20m segment 結果
- 以低負載方式視覺化全量 segment 的坡度分布

設計原則：
1. 不使用 popup，避免大量 JS / HTML 導致瀏覽器失敗
2. 不逐筆 PolyLine，改用 GeoJson 一次載入
3. 僅保留必要欄位，減少 HTML 體積
4. 以全量 QA 為目的，不做細部互動 debug

輸入：
- segment_enriched_output/97233NW_segments_20m_elevation_enriched.geojson

輸出：
- segment_enriched_output/97233NW_segments_20m_elevation_enriched_map_light.html
"""


# =========================================================
# 0. 基本設定
# =========================================================
INPUT_FP = Path("segment_enriched_output/97233NW_segments_20m_elevation_enriched.geojson")
OUT_FP = Path("segment_enriched_output/97233NW_segments_20m_elevation_enriched_map_light.html")


# =========================================================
# 1. 顏色規則
# =========================================================
def color_by_slope_band(v):
    return {
        "flat": "#808080",       # gray
        "gentle": "#008000",     # green
        "moderate": "#ffa500",   # orange
        "steep": "#ff0000",      # red
        "very_steep": "#8b0000", # darkred
        "unknown": "#0000ff",    # blue
    }.get(v, "#0000ff")


# =========================================================
# 2. 讀取資料
# =========================================================

if not INPUT_FP.exists():
    raise FileNotFoundError(f"找不到輸入檔：{INPUT_FP.resolve()}，請先執行 ia2c")

gdf = gpd.read_file(INPUT_FP)

if gdf.empty:
    raise ValueError(f"輸入檔為空：{INPUT_FP}")

if gdf.crs is None:
    gdf = gdf.set_crs("EPSG:4326")


# =========================================================
# 3. 嚴謹計算地圖中心
# =========================================================
metric_crs = gdf.estimate_utm_crs()
gdf_m = gdf.to_crs(metric_crs)

center_geom = (
    gdf_m.geometry.union_all().centroid
    if hasattr(gdf_m.geometry, "union_all")
    else gdf_m.geometry.unary_union.centroid
)

center = gpd.GeoSeries([center_geom], crs=metric_crs).to_crs("EPSG:4326")
center = [center.iloc[0].y, center.iloc[0].x]


# =========================================================
# 4. 轉回顯示座標系並精簡欄位
# =========================================================
gdf = gdf.to_crs("EPSG:4326")

# 只保留必要欄位，降低 HTML 體積
keep_cols = [
    "analysis_unit",
    "feature_status",
    "segment_len_m",
    "contour_cross_n",
    "contour_unique_elev_n",
    "contour_interval_m",
    "elev_gain_est_m",
    "slope_est_mean",
    "slope_band",
    "contour_density_20m",
    "elevp_available",
    "geometry",
    "tile_id",
]

existing_cols = [c for c in keep_cols if c in gdf.columns]
gdf = gdf[existing_cols].copy()


# =========================================================
# 5. 建立地圖
# =========================================================
m = folium.Map(
    location=center,
    zoom_start=14,
    tiles="CartoDB positron",
    width="100%",
    height="800px",
)

folium.GeoJson(
    data=gdf.__geo_interface__,
    name="slope_band",
    style_function=lambda feat: {
        "color": color_by_slope_band(feat["properties"].get("slope_band")),
        "weight": 2,
        "opacity": 0.8,
    },
).add_to(m)

folium.LayerControl(collapsed=False).add_to(m)


# =========================================================
# 6. 輸出
# =========================================================
m.save(OUT_FP)

print("完成：", OUT_FP.resolve())
print("segments:", len(gdf))
print("center:", center)
print("使用投影 CRS：", metric_crs)

if "slope_band" in gdf.columns:
    print("\n--- slope_band ---")
    print(gdf["slope_band"].value_counts(dropna=False))