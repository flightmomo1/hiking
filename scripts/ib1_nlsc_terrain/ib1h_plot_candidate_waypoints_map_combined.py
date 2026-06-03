# =========================================================
# ib1h_plot_candidate_waypoints_map.py
#
# 目的：
# - 讀取 Prototype A projected candidate waypoints
# - 支援 risk / scenic / combined waypoint set
# - 讀取 Prototype A risk zones GeoJSON
# - 繪製中繼點推薦地圖
# - 依 waypoint_type / 複合 waypoint_type 顯示不同顏色與角色說明
# =========================================================

from pathlib import Path

import pandas as pd
import geopandas as gpd
import folium


# =========================================================
# 0. Case 設定
# =========================================================
CASE_ID = "juansi_waterfall_fitcsv_20260503"
CASE_NAME = "絹絲瀑布 FIT CSV 20260503"
MODEL_VERSION = "prototype_A_terrain_dominant_v1"

# 可選：
# - "risk": 原 risk-zone waypoint projected map
# - "scenic": scenic / destination waypoint projected map
# - "combined": risk + scenic combined waypoint projected map
WAYPOINT_SET = "combined"

OUT_DIR = Path("outputs") / "prototype_A_terrain_dominant" / CASE_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)

WAYPOINT_FILES = {
    "risk": {
        "geojson": OUT_DIR / f"{CASE_ID}_prototype_A_candidate_waypoints_projected.geojson",
        "map": OUT_DIR / f"{CASE_ID}_prototype_A_candidate_waypoints_map.html",
        "title": "Prototype A Risk-Zone Candidate Waypoints",
    },
    "scenic": {
        "geojson": OUT_DIR / f"{CASE_ID}_prototype_A_scenic_candidate_waypoints_projected.geojson",
        "map": OUT_DIR / f"{CASE_ID}_prototype_A_scenic_candidate_waypoints_map.html",
        "title": "Prototype A Scenic Candidate Waypoints",
    },
    "combined": {
        "geojson": OUT_DIR / f"{CASE_ID}_prototype_A_candidate_waypoints_combined_projected.geojson",
        "map": OUT_DIR / f"{CASE_ID}_prototype_A_candidate_waypoints_combined_map.html",
        "title": "Prototype A Combined Candidate Waypoints",
    },
}

if WAYPOINT_SET not in WAYPOINT_FILES:
    raise ValueError(f"未知 WAYPOINT_SET: {WAYPOINT_SET}")

WAYPOINT_GEOJSON = WAYPOINT_FILES[WAYPOINT_SET]["geojson"]
OUT_MAP_HTML = WAYPOINT_FILES[WAYPOINT_SET]["map"]
MAP_TITLE = WAYPOINT_FILES[WAYPOINT_SET]["title"]

RISK_ZONE_GEOJSON = (
    OUT_DIR / f"{CASE_ID}_prototype_A_risk_zones.geojson"
)


# =========================================================
# 1. 顏色與圖示設定
# =========================================================
RISK_ZONE_COLORS = {
    "low": "#2ecc71",
    "moderate": "#f1c40f",
    "high": "#e67e22",
    "very_high": "#e74c3c",
    "unknown": "#95a5a6",
}

RISK_ZONE_WEIGHTS = {
    "low": 4,
    "moderate": 5,
    "high": 7,
    "very_high": 8,
    "unknown": 4,
}

WAYPOINT_COLORS = {
    # risk-zone waypoints
    "start_precheck": "#2c3e50",
    "recovery": "#27ae60",
    "recovery_decision": "#8e44ad",
    "rest_candidate": "#3498db",
    "conditional_check": "#e67e22",
    "conditional_check|pacing": "#d35400",
    "pacing": "#f1c40f",
    "final_push": "#c0392b",

    # scenic / destination waypoints
    "destination_stop": "#1f77b4",
    "viewpoint_stop": "#16a085",
    "guide_map_stop": "#6c5ce7",
    "scenic_stop": "#e84393",
    "tourism_stop": "#fd79a8",

    "unknown": "#7f8c8d",
}

WAYPOINT_ICONS = {
    # risk-zone waypoints
    "start_precheck": "play",
    "recovery": "heart",
    "recovery_decision": "flag",
    "rest_candidate": "pause",
    "conditional_check": "exclamation-sign",
    "conditional_check|pacing": "warning-sign",
    "pacing": "dashboard",
    "final_push": "forward",

    # scenic / destination waypoints
    "destination_stop": "star",
    "viewpoint_stop": "camera",
    "guide_map_stop": "info-sign",
    "scenic_stop": "picture",
    "tourism_stop": "map-marker",

    "unknown": "map-marker",
}

# 複合 waypoint_type 的優先順序。
# 例如 destination_stop|guide_map_stop|scenic_stop 會用 destination_stop 的顏色與 icon。
WAYPOINT_PRIORITY = [
    "destination_stop",
    "viewpoint_stop",
    "guide_map_stop",
    "scenic_stop",
    "tourism_stop",
    "recovery_decision",
    "recovery",
    "conditional_check|pacing",
    "conditional_check",
    "rest_candidate",
    "pacing",
    "final_push",
    "start_precheck",
]


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


def split_waypoint_type(v) -> list[str]:
    text = norm_text(v)
    if text == "unknown":
        return []
    return [x.strip() for x in text.split("|") if x.strip()]


def primary_waypoint_type(v) -> str:
    parts = split_waypoint_type(v)

    for key in WAYPOINT_PRIORITY:
        if key in parts:
            return key

    # 保留 conditional_check|pacing 這種整體 key 的相容性
    text = norm_text(v)
    if text in WAYPOINT_COLORS:
        return text

    return parts[0] if parts else "unknown"


def color_for_risk_group(v):
    return RISK_ZONE_COLORS.get(norm_text(v), RISK_ZONE_COLORS["unknown"])


def weight_for_risk_group(v):
    return RISK_ZONE_WEIGHTS.get(norm_text(v), RISK_ZONE_WEIGHTS["unknown"])


def color_for_waypoint_type(v):
    key = primary_waypoint_type(v)
    return WAYPOINT_COLORS.get(key, WAYPOINT_COLORS["unknown"])


def icon_for_waypoint_type(v):
    key = primary_waypoint_type(v)
    return WAYPOINT_ICONS.get(key, WAYPOINT_ICONS["unknown"])


def format_float(v, nd=3):
    try:
        if pd.isna(v):
            return ""
        return f"{float(v):.{nd}f}"
    except Exception:
        return ""


def format_dist(v):
    try:
        if pd.isna(v):
            return ""
        return f"{float(v):.0f} m"
    except Exception:
        return ""


def format_pct(v):
    try:
        if pd.isna(v):
            return ""
        return f"{float(v) * 100:.1f}%"
    except Exception:
        return ""


def safe_text(v):
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    if pd.isna(v):
        return ""
    return str(v)


def get_first_existing(row, keys, default=""):
    for key in keys:
        if key in row and not pd.isna(row.get(key)):
            value = row.get(key)
            if str(value).strip() not in {"", "nan", "None", "<NA>"}:
                return value
    return default


def make_waypoint_popup(row):
    waypoint_id = get_first_existing(
        row,
        ["waypoint_id", "combined_waypoint_id", "scenic_waypoint_id", "primary_waypoint_id"],
    )

    target_dist = get_first_existing(row, ["target_dist_m", "dist_m"], "")
    projected_dist = get_first_existing(row, ["projected_dist_m", "target_dist_m", "dist_m"], "")
    distance_error = get_first_existing(row, ["target_to_projected_dist_error_m", "projected_error_m"], "")

    html = f"""
    <div style="font-family: Arial; font-size: 13px; width: 500px;">
      <b>{MAP_TITLE}</b><br>
      <b>ID:</b> {safe_text(waypoint_id)}<br>
      <b>Name:</b> {safe_text(row.get('name', ''))}<br>
      <b>Type:</b> {safe_text(row.get('waypoint_type', ''))}<br>
      <b>Primary type:</b> {primary_waypoint_type(row.get('waypoint_type', ''))}<br>
      <hr>
      <b>Risk type:</b> {safe_text(row.get('risk_waypoint_type', ''))}<br>
      <b>Scenic type:</b> {safe_text(row.get('scenic_waypoint_type', ''))}<br>
      <b>Contains risk:</b> {safe_text(row.get('contains_risk_waypoint', ''))}<br>
      <b>Contains scenic:</b> {safe_text(row.get('contains_scenic_waypoint', ''))}<br>
      <b>Source layers:</b> {safe_text(row.get('source_layers', ''))}<br>
      <hr>
      <b>Primary role:</b> {safe_text(row.get('primary_role', ''))}<br>
      <b>Secondary roles:</b> {safe_text(row.get('secondary_roles', ''))}<br>
      <hr>
      <b>Target distance:</b> {format_dist(target_dist)}<br>
      <b>Projected distance:</b> {format_dist(projected_dist)}<br>
      <b>Distance error:</b> {format_float(distance_error, 2)} m<br>
      <b>Nearest route offset:</b> {format_float(row.get('nearest_route_offset_m', ''), 2)} m<br>
      <hr>
      <b>Risk zone:</b> zone {safe_text(row.get('projected_zone_id', ''))} / {safe_text(row.get('projected_zone_risk_group', ''))}<br>
      <b>Combined risk:</b> {format_float(row.get('projected_combined_risk_score', ''), 3)}<br>
      <b>Terrain risk:</b> {format_float(row.get('projected_terrain_window_risk_score', ''), 3)}<br>
      <b>Hydro amplifier:</b> {format_float(row.get('projected_hydro_terrain_amplifier_score', ''), 3)}<br>
      <b>Slope band:</b> {safe_text(row.get('projected_slope_band', ''))}<br>
      <b>Hydrology:</b> {safe_text(row.get('projected_hydrology_flags', ''))}<br>
      <b>Surface:</b> {safe_text(row.get('projected_osm_surface', ''))}<br>
      <b>Highway:</b> {safe_text(row.get('projected_osm_highway', ''))}<br>
      <hr>
      <b>Reason:</b><br>
      <pre style="white-space: pre-wrap;">{safe_text(row.get('reason', row.get('recommendation_reason', '')))}</pre>
      <b>Projected note:</b><br>
      <pre style="white-space: pre-wrap;">{safe_text(row.get('projected_note', ''))}</pre>
    </div>
    """
    return html


def make_zone_popup(row):
    html = f"""
    <div style="font-family: Arial; font-size: 13px; width: 430px;">
      <b>Prototype A Risk Zone</b><br>
      <b>zone_id:</b> {safe_text(row.get('zone_id', ''))}<br>
      <b>risk:</b> {safe_text(row.get('zone_risk_group', ''))}<br>
      <b>distance:</b> {format_dist(row.get('start_dist_m', ''))} – {format_dist(row.get('end_dist_m', ''))}<br>
      <b>length:</b> {format_dist(row.get('length_m', ''))}<br>
      <b>mean risk:</b> {format_float(row.get('mean_combined_risk', ''), 3)}<br>
      <b>max risk:</b> {format_float(row.get('max_combined_risk', ''), 3)}<br>
      <b>dominant slope:</b> {safe_text(row.get('dominant_slope_band', ''))}<br>
      <b>hydrology ratio:</b> {format_pct(row.get('hydrology_present_ratio', ''))}<br>
      <hr>
      <b>warning:</b><br>
      <pre style="white-space: pre-wrap;">{safe_text(row.get('suggested_warning_text', ''))}</pre>
    </div>
    """
    return html


# =========================================================
# 3. 檢查輸入
# =========================================================
for fp in [WAYPOINT_GEOJSON, RISK_ZONE_GEOJSON]:
    if not fp.exists():
        raise FileNotFoundError(f"找不到輸入檔：{fp.resolve()}")


# =========================================================
# 4. 讀資料
# =========================================================
wp_gdf = gpd.read_file(WAYPOINT_GEOJSON).to_crs("EPSG:4326")
zone_gdf = gpd.read_file(RISK_ZONE_GEOJSON).to_crs("EPSG:4326")

print("case:", CASE_ID)
print("waypoint_set:", WAYPOINT_SET)
print("waypoint input:", WAYPOINT_GEOJSON)
print("waypoints:", len(wp_gdf))
print("zones:", len(zone_gdf))

if wp_gdf.empty:
    raise ValueError("waypoint GeoJSON 為空")

if "waypoint_id" not in wp_gdf.columns:
    if "combined_waypoint_id" in wp_gdf.columns:
        wp_gdf["waypoint_id"] = wp_gdf["combined_waypoint_id"].astype(str)
    elif "scenic_waypoint_id" in wp_gdf.columns:
        wp_gdf["waypoint_id"] = wp_gdf["scenic_waypoint_id"].astype(str)
    else:
        prefix = {"risk": "WP", "scenic": "SWP", "combined": "CWP"}.get(WAYPOINT_SET, "WP")
        wp_gdf["waypoint_id"] = [f"{prefix}{i + 1:02d}" for i in range(len(wp_gdf))]

center = [
    wp_gdf.geometry.y.mean(),
    wp_gdf.geometry.x.mean(),
]


# =========================================================
# 5. 建立地圖
# =========================================================
m = folium.Map(
    location=center,
    zoom_start=14,
    tiles="CartoDB positron",
    width="100%",
    height="850px",
)

# ---------------------------------------------------------
# 5a. risk zone layers
# ---------------------------------------------------------
zone_layer = folium.FeatureGroup(name="Prototype A risk zones", show=True)
zone_layer.add_to(m)

for _, row in zone_gdf.iterrows():
    risk_group = norm_text(row.get("zone_risk_group", "unknown"))
    color = color_for_risk_group(risk_group)
    weight = weight_for_risk_group(risk_group)

    if row.geometry is None:
        continue

    if row.geometry.geom_type == "LineString":
        lines = [row.geometry]
    elif row.geometry.geom_type == "MultiLineString":
        lines = list(row.geometry.geoms)
    else:
        continue

    for line in lines:
        coords = [(lat, lon) for lon, lat in line.coords]

        folium.PolyLine(
            locations=coords,
            color=color,
            weight=weight,
            opacity=0.65,
            popup=folium.Popup(make_zone_popup(row), max_width=480),
            tooltip=(
                f"zone {row.get('zone_id', '')} | "
                f"{row.get('zone_risk_group', '')} | "
                f"{format_dist(row.get('start_dist_m', ''))}–{format_dist(row.get('end_dist_m', ''))}"
            ),
        ).add_to(zone_layer)


# ---------------------------------------------------------
# 5b. waypoint layers by primary type
# ---------------------------------------------------------
wp_gdf["primary_waypoint_type_for_map"] = wp_gdf["waypoint_type"].apply(primary_waypoint_type)

wp_layers = {}

for wp_type in sorted(wp_gdf["primary_waypoint_type_for_map"].fillna("unknown").astype(str).unique()):
    layer_name = f"waypoint: {wp_type}"
    wp_layers[wp_type] = folium.FeatureGroup(name=layer_name, show=True)
    wp_layers[wp_type].add_to(m)


for _, row in wp_gdf.iterrows():
    wp_type = primary_waypoint_type(row.get("waypoint_type", "unknown"))
    color = color_for_waypoint_type(row.get("waypoint_type", "unknown"))
    icon_name = icon_for_waypoint_type(row.get("waypoint_type", "unknown"))

    popup_html = make_waypoint_popup(row)

    waypoint_id = get_first_existing(
        row,
        ["waypoint_id", "combined_waypoint_id", "scenic_waypoint_id", "primary_waypoint_id"],
    )

    projected_dist = get_first_existing(row, ["projected_dist_m", "target_dist_m", "dist_m"], "")

    tooltip = (
        f"{waypoint_id} | "
        f"{row.get('waypoint_type', '')} | "
        f"{format_dist(projected_dist)}"
    )

    layer = wp_layers.get(wp_type, list(wp_layers.values())[0])

    folium.Marker(
        location=[row.geometry.y, row.geometry.x],
        popup=folium.Popup(popup_html, max_width=560),
        tooltip=tooltip,
        icon=folium.Icon(
            color="blue",
            icon=icon_name,
            prefix="glyphicon",
        ),
    ).add_to(layer)

    # 外圈依 waypoint type 上色，避免 folium.Icon 顏色選項太少
    folium.CircleMarker(
        location=[row.geometry.y, row.geometry.x],
        radius=8,
        color=color,
        weight=3,
        fill=False,
        opacity=0.95,
    ).add_to(layer)


# ---------------------------------------------------------
# 5c. legend
# ---------------------------------------------------------
legend_html = """
<div style="
    position: fixed;
    bottom: 40px;
    left: 40px;
    width: 350px;
    z-index: 9999;
    background-color: white;
    border: 2px solid #999;
    padding: 10px;
    font-size: 13px;
    font-family: Arial;
">
<b>Prototype A Combined Waypoints</b><br>
<span style="color:#1f77b4;">●</span> destination_stop<br>
<span style="color:#16a085;">●</span> viewpoint_stop<br>
<span style="color:#6c5ce7;">●</span> guide_map_stop<br>
<span style="color:#e84393;">●</span> scenic_stop<br>
<hr>
<b>Risk Waypoints</b><br>
<span style="color:#2c3e50;">●</span> start_precheck<br>
<span style="color:#8e44ad;">●</span> recovery_decision<br>
<span style="color:#27ae60;">●</span> recovery<br>
<span style="color:#3498db;">●</span> rest_candidate<br>
<span style="color:#e67e22;">●</span> conditional_check<br>
<span style="color:#d35400;">●</span> conditional_check|pacing<br>
<span style="color:#f1c40f;">●</span> pacing<br>
<span style="color:#c0392b;">●</span> final_push<br>
<hr>
<b>Risk Zones</b><br>
<span style="color:#2ecc71;">■</span> low<br>
<span style="color:#f1c40f;">■</span> moderate<br>
<span style="color:#e67e22;">■</span> high<br>
<span style="color:#e74c3c;">■</span> very_high<br>
</div>
"""

m.get_root().html.add_child(folium.Element(legend_html))
folium.LayerControl(collapsed=False).add_to(m)

m.save(OUT_MAP_HTML)


# =========================================================
# 6. Summary
# =========================================================
print("\n完成！")
print("waypoint_set:", WAYPOINT_SET)
print("waypoint map:", OUT_MAP_HTML.resolve())

print("\n--- waypoint type ---")
print(wp_gdf["waypoint_type"].value_counts(dropna=False))

print("\n--- primary waypoint type for map ---")
print(wp_gdf["primary_waypoint_type_for_map"].value_counts(dropna=False))

if "projected_zone_risk_group" in wp_gdf.columns:
    print("\n--- projected zone risk group ---")
    print(wp_gdf["projected_zone_risk_group"].value_counts(dropna=False))

preview_cols = [
    "waypoint_id",
    "projected_dist_m",
    "target_dist_m",
    "waypoint_type",
    "primary_waypoint_type_for_map",
    "projected_zone_id",
    "projected_zone_risk_group",
    "projected_combined_risk_score",
    "projected_slope_band",
    "projected_hydrology_flags",
]

preview_cols = [c for c in preview_cols if c in wp_gdf.columns]

print("\n--- waypoint preview ---")
print(wp_gdf[preview_cols])
