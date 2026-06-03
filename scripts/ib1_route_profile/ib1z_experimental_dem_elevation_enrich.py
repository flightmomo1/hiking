from pathlib import Path
import geopandas as gpd
import pandas as pd
import numpy as np
import folium

"""
ib1_osm_route_elevation_enrich.py

目的：
- 對 ib0a_pruned 的主路徑掛 GIS 高程
- 計算 slope（基礎版）
- 輸出可供 ib0b 使用的 route-elevation 資料

符合 schema：
- elev_gis_m
- slope_gis
- segment_len_m
- slope_band
"""

# =========================================================
# 0. 路徑設定
# =========================================================
ROUTE_FP = Path("ib0_gpx_osm_match_output/qixing_gpx_osm_matched_pruned.geojson")

ELEV_FP = Path("/Users/iddmini/Documents/osm路況研究/.../ElevP.shp")  # ←改成你的路徑

OUT_DIR = Path("ib1_output")
OUT_DIR.mkdir(exist_ok=True)

OUT_FP = OUT_DIR / "qixing_route_elevation.geojson"
OUT_HTML = OUT_DIR / "qixing_route_elevation_map.html"


# =========================================================
# 1. 讀檔
# =========================================================
route = gpd.read_file(ROUTE_FP)
elevp = gpd.read_file(ELEV_FP)

print("route:", len(route))
print("elevp:", len(elevp))

if route.crs is None:
    route = route.set_crs("EPSG:4326")

# =========================================================
# 2. 投影（分析用）
# =========================================================
metric_crs = route.estimate_utm_crs()

route = route.to_crs(metric_crs)
elevp = elevp.to_crs(metric_crs)

print("analysis CRS:", metric_crs)

# =========================================================
# 3. 高程欄位偵測
# =========================================================
z_candidates = ["zv2", "Z", "elev", "height"]

z_col = None
for c in z_candidates:
    if c in elevp.columns:
        z_col = c
        break

if z_col is None:
    raise ValueError("找不到高程欄位")

print("使用高程欄位:", z_col)

# =========================================================
# 4. 建立空間索引（加速）
# =========================================================
elev_sindex = elevp.sindex

def get_nearest_elev(geom):
    possible = list(elev_sindex.nearest(geom.bounds, 1))
    return elevp.iloc[possible][z_col].values[0]

# =========================================================
# 5. 計算 segment 長度
# =========================================================
route["segment_len_m"] = route.geometry.length

# =========================================================
# 6. 取得高程（用 centroid）
# =========================================================
route["elev_gis_m"] = route.geometry.centroid.apply(get_nearest_elev)

# =========================================================
# 7. 計算 slope（簡化版）
# =========================================================
route = route.reset_index(drop=True)

route["elev_next"] = route["elev_gis_m"].shift(-1)

route["slope_gis"] = (
    (route["elev_next"] - route["elev_gis_m"])
    / route["segment_len_m"]
)

# 最後一筆補 0
route["slope_gis"] = route["slope_gis"].fillna(0)

# =========================================================
# 8. slope 分類
# =========================================================
def slope_to_band(s):
    if s < 0.03:
        return "flat"
    elif s < 0.08:
        return "gentle"
    elif s < 0.15:
        return "moderate"
    else:
        return "steep"

route["slope_band"] = route["slope_gis"].apply(slope_to_band)

# =========================================================
# 9. 補 schema 欄位
# =========================================================
route["analysis_unit"] = "route_segment"
route["feature_status"] = "elevation_enriched"

# =========================================================
# 10. 輸出 GeoJSON
# =========================================================
route_out = route.to_crs("EPSG:4326")
route_out.to_file(OUT_FP, driver="GeoJSON")

print("輸出:", OUT_FP.resolve())

# =========================================================
# 11. QA 地圖
# =========================================================
center = route_out.geometry.unary_union.centroid
center = [center.y, center.x]

m = folium.Map(location=center, zoom_start=14, tiles="CartoDB positron")

def style(feature):
    band = feature["properties"]["slope_band"]

    color_map = {
        "flat": "green",
        "gentle": "yellow",
        "moderate": "orange",
        "steep": "red"
    }

    return {
        "color": color_map.get(band, "gray"),
        "weight": 4,
        "opacity": 0.9
    }

folium.GeoJson(
    route_out,
    style_function=style,
    tooltip=folium.GeoJsonTooltip(
        fields=[
            "osm_way_id",
            "elev_gis_m",
            "slope_gis",
            "slope_band"
        ]
    )
).add_to(m)

folium.LayerControl().add_to(m)

m.save(OUT_HTML)

print("QA 地圖:", OUT_HTML.resolve())

# =========================================================
# 12. 統計輸出
# =========================================================
print("\n=== slope_band 統計 ===")
print(route["slope_band"].value_counts())