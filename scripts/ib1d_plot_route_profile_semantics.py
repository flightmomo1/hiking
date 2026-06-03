# =========================================================
# ib1d_plot_route_profile_semantics.py
# 平面 2D 地圖 + 高程剖面語意色帶圖
# 讀取 ib1c semantic enriched profile
# =========================================================

from pathlib import Path

import pandas as pd
import geopandas as gpd
import folium
import matplotlib.pyplot as plt
from matplotlib.patches import Patch


# =========================================================
# 0. 路徑設定
# =========================================================
SEMANTIC_CSV = Path("ib1c_route_profile_semantic_output/qixing_route_profile_semantic_enriched.csv")
SEMANTIC_GEOJSON = Path("ib1c_route_profile_semantic_output/qixing_route_profile_semantic_enriched.geojson")
MAINLINE_FP = Path("ib0b_output/qixing_mainline.geojson")

OUT_DIR = Path("ib1d_route_profile_semantic_plot_output")
OUT_DIR.mkdir(exist_ok=True)

OUT_MAP = OUT_DIR / "qixing_route_semantic_map.html"
OUT_PROFILE_PNG = OUT_DIR / "qixing_route_semantic_profile.png"


# =========================================================
# 1. 參數
# =========================================================
ELEVATION_COL = "ele_gpx_m"   # 可改 "ele_smooth"

FLAG_COLORS = {
    "normal": "#ecf0f1",
    "none": "#ecf0f1",

    # technical
    "steps": "#e74c3c",
    "safety_rope": "#2ecc71",
    "handrail": "#27ae60",
    "ladder": "#8e44ad",
    "rungs": "#8d6e63",
    "via_ferrata": "#000000",
    "assisted_trail": "#ff00ff",

    # hazard
    "cliff": "#c0392b",
    "landslide": "#7f0000",
    "scree": "#d35400",
    "bare_rock": "#a0522d",

    # hydrology
    "waterway": "#3498db",
    "water_area": "#5dade2",
    "wetland": "#16a085",

    # facility/rest/support
    "shelter": "#008b8b",
    "alpine_hut": "#000080",
    "wilderness_hut": "#483d8b",
    "bench": "#f39c12",
    "picnic_table": "#a0522d",
    "picnic_site": "#cd853f",
    "drinking_water": "#00bfff",
    "toilets": "#8b008b",
    "visitor_centre": "#8b0000",
    "information_office": "#800000",
    "trailhead": "#00008b",
    "peak": "#dc143c",
    "guidepost": "#5f9ea0",
}

CATEGORY_COLS = [
    "technical_flags",
    "safety_flags",
    "hazard_flags",
    "hydrology_flags",
    "landmark_flags",
    "facility_flags",
    "rest_flags",
    "support_flags",
]


# =========================================================
# 2. 工具函式
# =========================================================
def first_flag(value: str) -> str:
    if pd.isna(value):
        return "none"
    text = str(value)
    if not text:
        return "none"
    return text.split("|")[0]


def color_for_flag(value: str) -> str:
    flag = first_flag(value)
    return FLAG_COLORS.get(flag, "#bdc3c7")


def has_any_flag(row, cols):
    for c in cols:
        v = str(row.get(c, "none"))
        if v not in ["normal", "none", "", "nan"]:
            return True
    return False


def build_runs(df, col):
    runs = []
    start_idx = 0
    values = df[col].fillna("none").astype(str).tolist()

    for i in range(1, len(values)):
        if values[i] != values[start_idx]:
            runs.append((start_idx, i - 1, values[start_idx]))
            start_idx = i

    runs.append((start_idx, len(values) - 1, values[start_idx]))
    return runs


def style_mainline(feat):
    role = feat["properties"].get("mainline_role", "")

    if role == "approach":
        return {"color": "orange", "weight": 5, "opacity": 0.85}

    if role == "trail_core":
        return {"color": "red", "weight": 5, "opacity": 0.9}

    return {"color": "purple", "weight": 4, "opacity": 0.8}


# =========================================================
# 3. 檢查輸入
# =========================================================
for fp in [SEMANTIC_CSV, SEMANTIC_GEOJSON, MAINLINE_FP]:
    if not fp.exists():
        raise FileNotFoundError(f"找不到檔案：{fp.resolve()}")


# =========================================================
# 4. 讀資料
# =========================================================
df = pd.read_csv(SEMANTIC_CSV)
gdf = gpd.read_file(SEMANTIC_GEOJSON).to_crs("EPSG:4326")
mainline = gpd.read_file(MAINLINE_FP).to_crs("EPSG:4326")

if ELEVATION_COL not in df.columns:
    raise ValueError(f"找不到高程欄位：{ELEVATION_COL}")

for col in CATEGORY_COLS:
    if col not in df.columns:
        df[col] = "none"
    if col not in gdf.columns:
        gdf[col] = df[col].values

print("profile points:", len(df))


# =========================================================
# 5. 平面 2D QA 地圖
# =========================================================
center = [gdf.geometry.y.mean(), gdf.geometry.x.mean()]

m = folium.Map(
    location=center,
    zoom_start=14,
    tiles="CartoDB positron",
    width="100%",
    height="800px",
)

folium.GeoJson(
    mainline,
    name="mainline",
    style_function=style_mainline,
    tooltip=folium.GeoJsonTooltip(
        fields=[c for c in ["osm_way_id", "name", "highway_norm", "mainline_role"] if c in mainline.columns],
        aliases=[c for c in ["osm_way_id", "name", "highway_norm", "mainline_role"] if c in mainline.columns],
    ),
).add_to(m)

# 所有 profile points 淡灰
fg_all = folium.FeatureGroup(name="profile points all", show=False)

for _, row in gdf.iterrows():
    folium.CircleMarker(
        location=[row.geometry.y, row.geometry.x],
        radius=2,
        color="#999999",
        fill=True,
        fill_opacity=0.35,
    ).add_to(fg_all)

fg_all.add_to(m)

# 有語意旗標的 profile points
fg_sem = folium.FeatureGroup(name="semantic points", show=True)

for _, row in gdf.iterrows():
    if not has_any_flag(row, CATEGORY_COLS):
        continue

    primary_color = "#333333"

    if str(row.get("hazard_flags", "normal")) not in ["normal", "none"]:
        primary_color = color_for_flag(row.get("hazard_flags"))
    elif str(row.get("technical_flags", "normal")) not in ["normal", "none"]:
        primary_color = color_for_flag(row.get("technical_flags"))
    elif str(row.get("hydrology_flags", "normal")) not in ["normal", "none"]:
        primary_color = color_for_flag(row.get("hydrology_flags"))
    elif str(row.get("facility_flags", "none")) != "none":
        primary_color = color_for_flag(row.get("facility_flags"))
    elif str(row.get("rest_flags", "none")) != "none":
        primary_color = color_for_flag(row.get("rest_flags"))
    elif str(row.get("support_flags", "none")) != "none":
        primary_color = color_for_flag(row.get("support_flags"))
    elif str(row.get("landmark_flags", "none")) != "none":
        primary_color = color_for_flag(row.get("landmark_flags"))

    popup = (
        f"<pre>"
        f"idx: {row.get('sample_idx', '')}\n"
        f"dist_m: {row.get('dist_m', '')}\n"
        f"ele: {row.get(ELEVATION_COL, '')}\n"
        f"technical: {row.get('technical_flags', '')}\n"
        f"safety: {row.get('safety_flags', '')}\n"
        f"hazard: {row.get('hazard_flags', '')}\n"
        f"hydrology: {row.get('hydrology_flags', '')}\n"
        f"landmark: {row.get('landmark_flags', '')}\n"
        f"facility: {row.get('facility_flags', '')}\n"
        f"rest: {row.get('rest_flags', '')}\n"
        f"support: {row.get('support_flags', '')}\n"
        f"nearby: {row.get('nearby_named_features', '')}"
        f"</pre>"
    )

    folium.CircleMarker(
        location=[row.geometry.y, row.geometry.x],
        radius=5,
        color=primary_color,
        fill=True,
        fill_opacity=0.9,
        popup=folium.Popup(popup, max_width=420),
    ).add_to(fg_sem)

fg_sem.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)
m.save(OUT_MAP)

print("semantic map:", OUT_MAP.resolve())


# =========================================================
# 6. 高程剖面 + 語意色帶
# =========================================================
plot_df = df.copy()

plot_df["technical_display"] = plot_df["technical_flags"].apply(first_flag)
plot_df["hazard_display"] = plot_df["hazard_flags"].apply(first_flag)
plot_df["hydrology_display"] = plot_df["hydrology_flags"].apply(first_flag)

# facility / rest / support 合成一條 support_display
def combine_support(row):
    for col in ["facility_flags", "rest_flags", "support_flags", "landmark_flags"]:
        v = first_flag(row.get(col, "none"))
        if v not in ["none", "normal"]:
            return v
    return "none"

plot_df["support_display"] = plot_df.apply(combine_support, axis=1)

tech_runs = build_runs(plot_df, "technical_display")
hazard_runs = build_runs(plot_df, "hazard_display")
hydro_runs = build_runs(plot_df, "hydrology_display")
support_runs = build_runs(plot_df, "support_display")

fig, (ax1, ax2, ax3, ax4, ax5) = plt.subplots(
    5,
    1,
    figsize=(16, 10),
    sharex=True,
    gridspec_kw={"height_ratios": [5, 0.5, 0.5, 0.5, 0.5]},
)

# elevation
ax1.plot(
    plot_df["dist_m"],
    plot_df[ELEVATION_COL],
    linewidth=1.6,
    label=ELEVATION_COL,
)

ax1.set_ylabel("Elevation (m)")
ax1.set_title("Qixing Route Semantic Elevation Profile")
ax1.grid(True, alpha=0.3)


def draw_band(ax, runs, label):
    for s, e, value in runs:
        x0 = plot_df.loc[s, "dist_m"]
        x1 = plot_df.loc[e, "dist_m"]

        if e + 1 < len(plot_df):
            x1 = plot_df.loc[e + 1, "dist_m"]

        ax.broken_barh(
            [(x0, x1 - x0)],
            (0, 1),
            facecolors=FLAG_COLORS.get(value, "#bdc3c7"),
        )

    ax.set_yticks([0.5])
    ax.set_yticklabels([label])
    ax.set_ylim(0, 1)
    ax.grid(False)


draw_band(ax2, tech_runs, "technical")
draw_band(ax3, hazard_runs, "hazard")
draw_band(ax4, hydro_runs, "water")
draw_band(ax5, support_runs, "support")
ax5.set_xlabel("Distance (m)")


# legend：只顯示有用到的值
used_values = set()
for col in ["technical_display", "hazard_display", "hydrology_display", "support_display"]:
    used_values.update(plot_df[col].dropna().astype(str).unique().tolist())

legend_handles = [
    Patch(facecolor=FLAG_COLORS.get(v, "#bdc3c7"), label=v)
    for v in sorted(used_values)
    if v not in ["none", "normal"]
]

if legend_handles:
    ax1.legend(handles=legend_handles, loc="upper right", fontsize=8, ncol=3)

plt.tight_layout()
plt.savefig(OUT_PROFILE_PNG, dpi=200)
plt.close()

print("semantic profile PNG:", OUT_PROFILE_PNG.resolve())


# =========================================================
# 7. 摘要
# =========================================================
for col in [
    "technical_flags",
    "safety_flags",
    "hazard_flags",
    "hydrology_flags",
    "landmark_flags",
    "facility_flags",
    "rest_flags",
    "support_flags",
]:
    print(f"\n--- {col} ---")
    print(df[col].value_counts(dropna=False))