# =========================================================
# ib1g_plot_prototype_A_risk_zones_map.py
#
# 目的：
# - 讀取 Prototype A risk zones
# - 讀取 ib1e combined risk profile GeoJSON
# - 依照 dist_m 將 profile points 切成連續 risk zone
# - 在 folium map 上畫出 low / moderate / high 風險區間線段
# =========================================================

from pathlib import Path

import pandas as pd
import geopandas as gpd
import folium
from shapely.geometry import LineString


# =========================================================
# 0. Case 設定
# =========================================================
CASE_ID = "juansi_waterfall_fitcsv_20260503"
CASE_NAME = "絹絲瀑布 FIT CSV 20260503"
MODEL_VERSION = "prototype_A_terrain_dominant_v1"

ZONE_CSV = (
    Path("outputs")
    / "prototype_A_terrain_dominant"
    / CASE_ID
    / f"{CASE_ID}_prototype_A_risk_zones.csv"
)

PROFILE_GEOJSON = (
    Path("outputs")
    / "ib1e_osm_nlsc_terrain_risk"
    / CASE_ID
    / f"{CASE_ID}_osm_nlsc_terrain_risk_profile.geojson"
)

OUT_DIR = Path("outputs") / "prototype_A_terrain_dominant" / CASE_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_MAP_HTML = OUT_DIR / f"{CASE_ID}_prototype_A_risk_zones_map.html"
OUT_ZONE_GEOJSON = OUT_DIR / f"{CASE_ID}_prototype_A_risk_zones.geojson"


# =========================================================
# 1. 參數
# =========================================================
RISK_COLORS = {
    "low": "#2ecc71",
    "moderate": "#f1c40f",
    "high": "#e67e22",
    "very_high": "#e74c3c",
    "unknown": "#95a5a6",
}

RISK_WEIGHTS = {
    "low": 4,
    "moderate": 6,
    "high": 8,
    "very_high": 9,
    "unknown": 4,
}

# 每條 zone 線段中，若點太多，全部畫也可接受；3973 points 很小。
MIN_POINTS_PER_ZONE_LINE = 2


# =========================================================
# 2. 工具函式
# =========================================================
def norm_text(v):
    if pd.isna(v):
        return "unknown"
    text = str(v).strip().lower()
    if text in {"", "nan", "none", "<na>", "na", "null"}:
        return "unknown"
    return text


def color_for_band(band):
    return RISK_COLORS.get(norm_text(band), RISK_COLORS["unknown"])


def weight_for_band(band):
    return RISK_WEIGHTS.get(norm_text(band), RISK_WEIGHTS["unknown"])


def make_zone_line(points_gdf):
    """
    將 zone 內 profile points 按 dist_m 排序後連成 LineString。
    """
    g = points_gdf.sort_values("dist_m")

    coords = [(geom.x, geom.y) for geom in g.geometry if geom is not None]

    if len(coords) < MIN_POINTS_PER_ZONE_LINE:
        return None

    return LineString(coords)


def format_pct(v):
    try:
        return f"{float(v) * 100:.1f}%"
    except Exception:
        return ""


def format_float(v, nd=3):
    try:
        return f"{float(v):.{nd}f}"
    except Exception:
        return ""


# =========================================================
# 3. 檢查輸入
# =========================================================
for fp in [ZONE_CSV, PROFILE_GEOJSON]:
    if not fp.exists():
        raise FileNotFoundError(f"找不到輸入檔：{fp.resolve()}")


# =========================================================
# 4. 讀資料
# =========================================================
zone_df = pd.read_csv(ZONE_CSV, low_memory=False)
profile_gdf = gpd.read_file(PROFILE_GEOJSON).to_crs("EPSG:4326")

if "dist_m" not in profile_gdf.columns:
    raise ValueError("profile GeoJSON 缺少 dist_m 欄位")

required_zone_cols = [
    "zone_id",
    "zone_risk_group",
    "start_dist_m",
    "end_dist_m",
    "length_m",
    "mean_combined_risk",
    "max_combined_risk",
    "dominant_slope_band",
    "hydrology_present_ratio",
    "zone_main_reason",
    "suggested_warning_text",
]

missing = [c for c in required_zone_cols if c not in zone_df.columns]
if missing:
    raise ValueError(f"zone CSV 缺少必要欄位：{missing}")

print("case:", CASE_ID)
print("zones:", len(zone_df))
print("profile points:", len(profile_gdf))


# =========================================================
# 5. 建立 zone GeoDataFrame
# =========================================================
zone_features = []

for _, zone in zone_df.iterrows():
    start_m = float(zone["start_dist_m"])
    end_m = float(zone["end_dist_m"])

    pts = profile_gdf[
        (profile_gdf["dist_m"] >= start_m)
        & (profile_gdf["dist_m"] <= end_m)
    ].copy()

    line = make_zone_line(pts)

    if line is None:
        print(f"zone {zone['zone_id']} skipped: not enough points")
        continue

    rec = zone.to_dict()
    rec["geometry"] = line
    rec["point_n_from_profile"] = len(pts)
    zone_features.append(rec)

zone_gdf = gpd.GeoDataFrame(zone_features, geometry="geometry", crs="EPSG:4326")

zone_gdf.to_file(OUT_ZONE_GEOJSON, driver="GeoJSON")

print("zone GeoJSON:", OUT_ZONE_GEOJSON.resolve())


# =========================================================
# 6. Folium map
# =========================================================
center = [
    profile_gdf.geometry.y.mean(),
    profile_gdf.geometry.x.mean(),
]

m = folium.Map(
    location=center,
    zoom_start=14,
    tiles="CartoDB positron",
    width="100%",
    height="850px",
)

# 分圖層
layers = {}

for band in ["high", "moderate", "low", "very_high", "unknown"]:
    layers[band] = folium.FeatureGroup(name=f"risk zone: {band}", show=True)
    layers[band].add_to(m)


for _, row in zone_gdf.iterrows():
    band = norm_text(row.get("zone_risk_group", "unknown"))
    color = color_for_band(band)
    weight = weight_for_band(band)

    coords = [(lat, lon) for lon, lat in row.geometry.coords]

    popup_html = f"""
    <div style="font-family: Arial; font-size: 13px; width: 420px;">
      <b>Prototype A Risk Zone</b><br>
      <b>zone_id:</b> {row.get('zone_id', '')}<br>
      <b>risk:</b> {row.get('zone_risk_group', '')}<br>
      <b>distance:</b> {format_float(row.get('start_dist_m', ''), 0)}–{format_float(row.get('end_dist_m', ''), 0)} m<br>
      <b>length:</b> {format_float(row.get('length_m', ''), 0)} m<br>
      <b>mean combined risk:</b> {format_float(row.get('mean_combined_risk', ''), 3)}<br>
      <b>max combined risk:</b> {format_float(row.get('max_combined_risk', ''), 3)}<br>
      <b>dominant slope:</b> {row.get('dominant_slope_band', '')}<br>
      <b>hydrology ratio:</b> {format_pct(row.get('hydrology_present_ratio', ''))}<br>
      <b>main reason:</b><br>
      <pre style="white-space: pre-wrap;">{row.get('zone_main_reason', '')}</pre>
      <b>warning:</b><br>
      <pre style="white-space: pre-wrap;">{row.get('suggested_warning_text', '')}</pre>
    </div>
    """

    folium.PolyLine(
        locations=coords,
        color=color,
        weight=weight,
        opacity=0.88,
        popup=folium.Popup(popup_html, max_width=480),
        tooltip=(
            f"zone {row.get('zone_id', '')} | "
            f"{row.get('zone_risk_group', '')} | "
            f"{format_float(row.get('start_dist_m', ''), 0)}–"
            f"{format_float(row.get('end_dist_m', ''), 0)} m"
        ),
    ).add_to(layers.get(band, layers["unknown"]))

    # zone 起點 marker
    start_point = list(row.geometry.coords)[0]
    folium.CircleMarker(
        location=[start_point[1], start_point[0]],
        radius=4,
        color=color,
        fill=True,
        fill_opacity=0.95,
        popup=folium.Popup(popup_html, max_width=480),
    ).add_to(layers.get(band, layers["unknown"]))


# 加圖例
legend_html = """
<div style="
    position: fixed;
    bottom: 40px;
    left: 40px;
    width: 220px;
    z-index: 9999;
    background-color: white;
    border: 2px solid #999;
    padding: 10px;
    font-size: 13px;
    font-family: Arial;
">
<b>Prototype A Risk Zones</b><br>
<span style="color:#2ecc71;">■</span> low<br>
<span style="color:#f1c40f;">■</span> moderate<br>
<span style="color:#e67e22;">■</span> high<br>
<span style="color:#e74c3c;">■</span> very_high<br>
</div>
"""

m.get_root().html.add_child(folium.Element(legend_html))

folium.LayerControl(collapsed=False).add_to(m)
m.save(OUT_MAP_HTML)

print("zone map:", OUT_MAP_HTML.resolve())


# =========================================================
# 7. Summary
# =========================================================
print("\n--- zone risk group ---")
print(zone_gdf["zone_risk_group"].value_counts(dropna=False))

print("\n--- zone table preview ---")
print(
    zone_gdf[
        [
            "zone_id",
            "zone_risk_group",
            "start_dist_m",
            "end_dist_m",
            "length_m",
            "mean_combined_risk",
            "max_combined_risk",
            "dominant_slope_band",
            "hydrology_present_ratio",
            "point_n_from_profile",
        ]
    ]
)