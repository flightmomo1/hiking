from pathlib import Path
import math
import html
import pandas as pd
import geopandas as gpd
import folium


# =========================================================
# 0. 基本設定
# =========================================================
INPUT_FP = Path("contour_enriched_output/97233NW_road_contour_enriched.geojson")
OUT_FP = Path("contour_enriched_output/97233NW_road_contour_enriched_map_safe_popup.html")


# =========================================================
# 1. 工具函式
# =========================================================
def safe_text(v):
    if pd.isna(v):
        return ""
    if isinstance(v, float):
        if math.isfinite(v):
            return f"{v:.3f}"
        return ""
    return str(v)


def safe_html_text(v):
    return html.escape(safe_text(v), quote=True)


def color_by_slope_band(v: str) -> str:
    mapping = {
        "flat": "gray",
        "gentle": "green",
        "moderate": "orange",
        "steep": "red",
        "very_steep": "darkred",
        "unknown": "blue",
    }
    return mapping.get(v, "blue")


def build_popup_html(row) -> str:
    # 先用較短、穩定的 popup，避免太長太複雜
    fields = [
        "name",
        "tile_id",
        "analysis_unit",
        "feature_status",
        "segment_len_m",
        "slope_est_mean",
        "slope_band",
        "near_water_m",
        "near_bridge_m",
        "near_water_20m",
        "water_risk_hint_rule",
    ]

    lines = []
    for f in fields:
        if f in row.index:
            key_html = html.escape(str(f), quote=True)
            val_html = safe_html_text(row.get(f))
            lines.append(f"{key_html}: {val_html}")

    # 用 pre 純文字，最穩
    body = "\n".join(lines)
    return f"<pre style='margin:0; white-space:pre-wrap; font-size:12px;'>{body}</pre>"


def make_popup_from_html(popup_html: str):
    iframe = folium.IFrame(html=popup_html, width=320, height=220)
    return folium.Popup(iframe, max_width=340)


def add_lines_to_group(feature_group, geom, color, weight, opacity, popup_html):
    """
    注意：
    這裡不重用 popup 物件。
    每條線都建立新的 popup，避免 MultiLineString / 多筆重複綁定造成 JS 壞掉。
    """
    if geom is None or geom.is_empty:
        return

    if geom.geom_type == "LineString":
        coords = [(lat, lon) for lon, lat in geom.coords]
        popup = make_popup_from_html(popup_html)
        folium.PolyLine(
            locations=coords,
            color=color,
            weight=weight,
            opacity=opacity,
            popup=popup,
        ).add_to(feature_group)

    elif geom.geom_type == "MultiLineString":
        for line in geom.geoms:
            coords = [(lat, lon) for lon, lat in line.coords]
            popup = make_popup_from_html(popup_html)
            folium.PolyLine(
                locations=coords,
                color=color,
                weight=weight,
                opacity=opacity,
                popup=popup,
            ).add_to(feature_group)


# =========================================================
# 2. 讀檔
# =========================================================

if not INPUT_FP.exists():
    raise FileNotFoundError(f"找不到輸入檔：{INPUT_FP.resolve()}，請先執行 ia2")

gdf = gpd.read_file(INPUT_FP)


if gdf.empty:
    raise ValueError(f"輸入檔為空：{INPUT_FP}")

if gdf.crs is None:
    gdf = gdf.set_crs("EPSG:4326")


# =========================================================
# 3. 嚴謹計算地圖中心
# =========================================================
metric_crs = gdf.estimate_utm_crs()
gdf_metric = gdf.to_crs(metric_crs)

center_geom_metric = (
    gdf_metric.geometry.union_all().centroid
    if hasattr(gdf_metric.geometry, "union_all")
    else gdf_metric.geometry.unary_union.centroid
)

center_series = gpd.GeoSeries([center_geom_metric], crs=metric_crs).to_crs("EPSG:4326")
center = [center_series.iloc[0].y, center_series.iloc[0].x]

# folium 顯示仍使用 WGS84
gdf_wgs84 = gdf.to_crs("EPSG:4326")


# =========================================================
# 4. debug 資訊
# =========================================================
print("rows:", len(gdf_wgs84))
print("geom types:", gdf_wgs84.geom_type.value_counts().to_dict())
print("slope_band:", gdf_wgs84["slope_band"].value_counts(dropna=False).to_dict())


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

fg_slope = folium.FeatureGroup(name="slope_band", show=True)
fg_water_high = folium.FeatureGroup(name="water_risk_high (rule)", show=True)
fg_bridge = folium.FeatureGroup(name="has_bridge_15m", show=False)
fg_water_near = folium.FeatureGroup(name="near_water_20m", show=False)


# =========================================================
# 6. 畫圖層
# =========================================================
draw_count = 0
high_water_count = 0
bridge_count = 0
near_water_count = 0

for _, row in gdf_wgs84.iterrows():
    geom = row.geometry
    popup_html = build_popup_html(row)

    slope_color = color_by_slope_band(row.get("slope_band"))

    add_lines_to_group(
        feature_group=fg_slope,
        geom=geom,
        color=slope_color,
        weight=8,
        opacity=0.9,
        popup_html=popup_html,
    )
    draw_count += 1

    if row.get("water_risk_hint_rule") == "high":
        add_lines_to_group(
            feature_group=fg_water_high,
            geom=geom,
            color="blue",
            weight=10,
            opacity=0.95,
            popup_html=popup_html,
        )
        high_water_count += 1

    if row.get("has_bridge_15m") == 1:
        add_lines_to_group(
            feature_group=fg_bridge,
            geom=geom,
            color="black",
            weight=10,
            opacity=0.95,
            popup_html=popup_html,
        )
        bridge_count += 1

    if row.get("near_water_20m") == 1:
        add_lines_to_group(
            feature_group=fg_water_near,
            geom=geom,
            color="cyan",
            weight=9,
            opacity=0.95,
            popup_html=popup_html,
        )
        near_water_count += 1


# =========================================================
# 7. 加圖層控制
# =========================================================
fg_slope.add_to(m)
fg_water_high.add_to(m)
fg_bridge.add_to(m)
fg_water_near.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)


# =========================================================
# 8. 輸出
# =========================================================
m.save(OUT_FP)

print("完成：", OUT_FP.resolve())
print("地圖中心：", center)
print("使用投影 CRS：", metric_crs)
print("draw_count:", draw_count)
print("high_water_count:", high_water_count)
print("bridge_count:", bridge_count)
print("near_water_count:", near_water_count)