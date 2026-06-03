from pathlib import Path
import geopandas as gpd
import folium

INPUT_FP = Path("contour_enriched_output/97233NW_road_contour_enriched.geojson")
OUT_FP = Path("contour_enriched_output/97233NW_road_contour_enriched_qa_map.html")


if not INPUT_FP.exists():
    raise FileNotFoundError(f"找不到輸入檔：{INPUT_FP.resolve()}，請先執行 ia2")

def color_by_slope_band(v: str) -> str:
    mapping = {
        "flat": "magenta",
        "gentle": "lime",
        "moderate": "orange",
        "steep": "red",
        "very_steep": "darkred",
        "unknown": "blue",
    }
    return mapping.get(v, "blue")


gdf = gpd.read_file(INPUT_FP)

if gdf.empty:
    raise ValueError(f"輸入檔為空：{INPUT_FP}")

if gdf.crs is None:
    gdf = gdf.set_crs("EPSG:4326")

metric_crs = gdf.estimate_utm_crs()
gdf_metric = gdf.to_crs(metric_crs)

center_geom_metric = (
    gdf_metric.geometry.union_all().centroid
    if hasattr(gdf_metric.geometry, "union_all")
    else gdf_metric.geometry.unary_union.centroid
)

center_series = gpd.GeoSeries([center_geom_metric], crs=metric_crs).to_crs("EPSG:4326")
center = [center_series.iloc[0].y, center_series.iloc[0].x]

gdf_wgs84 = gdf.to_crs("EPSG:4326")

print("rows:", len(gdf_wgs84))
print("geom types:", gdf_wgs84.geom_type.value_counts().to_dict())

m = folium.Map(
    location=center,
    zoom_start=14,
    tiles="CartoDB positron",
    width="100%",
    height="800px",
)

fg_slope = folium.FeatureGroup(name="DEBUG_slope_band", show=True)

for _, row in gdf_wgs84.iterrows():
    geom = row.geometry
    slope_color = color_by_slope_band(row.get("slope_band"))

    if geom is None or geom.is_empty:
        continue

    if geom.geom_type == "LineString":
        coords = [(lat, lon) for lon, lat in geom.coords]
        folium.PolyLine(
            locations=coords,
            color=slope_color,
            weight=14,
            opacity=1.0,
        ).add_to(fg_slope)

    elif geom.geom_type == "MultiLineString":
        for line in geom.geoms:
            coords = [(lat, lon) for lon, lat in line.coords]
            folium.PolyLine(
                locations=coords,
                color=slope_color,
                weight=14,
                opacity=1.0,
            ).add_to(fg_slope)

fg_slope.add_to(m)
folium.LayerControl(collapsed=False).add_to(m)

m.save(OUT_FP)

print("完成：", OUT_FP.resolve())
print("地圖中心：", center)
print("使用投影 CRS：", metric_crs)