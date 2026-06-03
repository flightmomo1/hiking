# =========================================================
# ib1c_plot_osm_semantic_risk_profile.py
#
# 目的：
# - 讀取 ib1c_apply_osm_semantic_risk_mapping.py 產出的 OSM semantic risk profile
# - 繪製：
#   1. 距離—高程—OSM semantic risk score 剖面圖
#   2. conditional factor / weather sensitive / needs NLSC 語意色帶
#   3. 2D QA map
# =========================================================

from pathlib import Path

import pandas as pd
import geopandas as gpd
import folium
import matplotlib.pyplot as plt
from matplotlib.patches import Patch


# =========================================================
# 0. Case 設定
# =========================================================
CASE_ID = "juansi_waterfall_fitcsv_20260503"
CASE_NAME = "絹絲瀑布 FIT CSV 20260503"

RISK_CSV = (
    Path("outputs")
    / "ib1c_osm_semantic_risk"
    / CASE_ID
    / f"{CASE_ID}_osm_semantic_risk_profile.csv"
)

RISK_GEOJSON = (
    Path("outputs")
    / "ib1c_osm_semantic_risk"
    / CASE_ID
    / f"{CASE_ID}_osm_semantic_risk_profile.geojson"
)

OUT_DIR = Path("outputs") / "ib1c_osm_semantic_risk_plot" / CASE_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_PROFILE_PNG = OUT_DIR / f"{CASE_ID}_osm_semantic_risk_profile.png"
OUT_MAP_HTML = OUT_DIR / f"{CASE_ID}_osm_semantic_risk_map.html"


# =========================================================
# 1. 參數
# =========================================================
ELEVATION_COL_CANDIDATES = [
    "ele_smooth",
    "ele_gpx_m",
]

RISK_SCORE_COL = "osm_semantic_risk_score"
RISK_BAND_COL = "osm_semantic_risk_band"

QA_MARKER_INTERVAL_M = 20.0

RISK_BAND_COLORS = {
    "low": "#2ecc71",
    "moderate": "#f1c40f",
    "high": "#e67e22",
    "very_high": "#e74c3c",
}

FLAG_COLORS = {
    "none": "#ecf0f1",
    "normal": "#ecf0f1",
    "blank": "#ecf0f1",

    "bridge": "#8e44ad",
    "weather_sensitive": "#3498db",
    "needs_nlsc": "#16a085",
    "needs_activity": "#f39c12",

    "waterway": "#3498db",
    "wetland": "#16a085",
    "surface": "#95a5a6",
    "steps": "#e74c3c",
    "sett": "#7f8c8d",
    "wood": "#8d6e63",
}


# =========================================================
# 2. 工具函式
# =========================================================
def first_token(value):
    if pd.isna(value):
        return "none"

    text = str(value).strip()

    if text == "":
        return "none"

    # 例如 surface=sett|hydrology_flags:waterway
    first = text.split("|")[0].strip()

    if not first:
        return "none"

    return first


def classify_factor(value):
    """
    將 flags 字串壓成簡報用類別。
    """
    text = "" if pd.isna(value) else str(value).strip()

    if text == "":
        return "none"

    if "bridge=yes" in text:
        return "bridge"

    if "waterway" in text:
        return "waterway"

    if "wetland" in text:
        return "wetland"

    if "highway=steps" in text:
        return "steps"

    if "surface=wood" in text:
        return "wood"

    if "surface=sett" in text:
        return "sett"

    if "surface=" in text:
        return "surface"

    return first_token(text)


def color_for_factor(value):
    cls = classify_factor(value)
    return FLAG_COLORS.get(cls, "#bdc3c7")


def build_runs(df, col):
    """
    將連續相同值壓成色帶區段。
    回傳 [(start_idx, end_idx, value), ...]
    """
    values = df[col].fillna("none").astype(str).tolist()

    if not values:
        return []

    runs = []
    start_idx = 0

    for i in range(1, len(values)):
        if values[i] != values[start_idx]:
            runs.append((start_idx, i - 1, values[start_idx]))
            start_idx = i

    runs.append((start_idx, len(values) - 1, values[start_idx]))
    return runs


def draw_band(ax, plot_df, runs, label):
    for s, e, value in runs:
        x0 = float(plot_df.loc[s, "dist_m"])
        x1 = float(plot_df.loc[e, "dist_m"])

        if e + 1 < len(plot_df):
            x1 = float(plot_df.loc[e + 1, "dist_m"])

        ax.broken_barh(
            [(x0, max(0.1, x1 - x0))],
            (0, 1),
            facecolors=color_for_factor(value),
        )

    ax.set_yticks([0.5])
    ax.set_yticklabels([label])
    ax.set_ylim(0, 1)
    ax.grid(False)


def risk_color(score):
    if pd.isna(score):
        return "#999999"

    score = float(score)

    if score < 0.20:
        return RISK_BAND_COLORS["low"]
    if score < 0.40:
        return RISK_BAND_COLORS["moderate"]
    if score < 0.65:
        return RISK_BAND_COLORS["high"]

    return RISK_BAND_COLORS["very_high"]


def choose_elevation_col(df):
    for c in ELEVATION_COL_CANDIDATES:
        if c in df.columns:
            return c

    return None


# =========================================================
# 3. 檢查輸入
# =========================================================
for fp in [RISK_CSV, RISK_GEOJSON]:
    if not fp.exists():
        raise FileNotFoundError(f"找不到輸入檔：{fp.resolve()}")


# =========================================================
# 4. 讀資料
# =========================================================
df = pd.read_csv(RISK_CSV, low_memory=False)
gdf = gpd.read_file(RISK_GEOJSON).to_crs("EPSG:4326")

if len(df) != len(gdf):
    raise ValueError(f"CSV 與 GeoJSON 筆數不一致：csv={len(df)}, geojson={len(gdf)}")

if "dist_m" not in df.columns:
    raise ValueError("找不到 dist_m 欄位")

if RISK_SCORE_COL not in df.columns:
    raise ValueError(f"找不到 {RISK_SCORE_COL} 欄位")

elevation_col = choose_elevation_col(df)

print("case:", CASE_ID)
print("rows:", len(df))
print("elevation_col:", elevation_col)
print("risk score min/mean/max:", df[RISK_SCORE_COL].min(), df[RISK_SCORE_COL].mean(), df[RISK_SCORE_COL].max())


# =========================================================
# 5. 建立視覺化用欄位
# =========================================================
plot_df = df.copy().reset_index(drop=True)

for col in [
    "conditional_factor_flags",
    "weather_sensitive_flags",
    "needs_nlsc_flags",
    "needs_activity_flags",
]:
    if col not in plot_df.columns:
        plot_df[col] = ""

plot_df["conditional_display"] = plot_df["conditional_factor_flags"].apply(classify_factor)
plot_df["weather_display"] = plot_df["weather_sensitive_flags"].apply(classify_factor)
plot_df["nlsc_display"] = plot_df["needs_nlsc_flags"].apply(classify_factor)
plot_df["activity_display"] = plot_df["needs_activity_flags"].apply(classify_factor)

conditional_runs = build_runs(plot_df, "conditional_display")
weather_runs = build_runs(plot_df, "weather_display")
nlsc_runs = build_runs(plot_df, "nlsc_display")
activity_runs = build_runs(plot_df, "activity_display")


# =========================================================
# 6. 距離—高程—OSM semantic risk profile
# =========================================================
fig, axes = plt.subplots(
    5,
    1,
    figsize=(16, 11),
    sharex=True,
    gridspec_kw={"height_ratios": [4.5, 2.0, 0.45, 0.45, 0.45]},
)

ax_elev = axes[0]
ax_risk = axes[1]
ax_cond = axes[2]
ax_weather = axes[3]
ax_nlsc = axes[4]

# 高程
if elevation_col:
    ax_elev.plot(
        plot_df["dist_m"],
        plot_df[elevation_col],
        linewidth=1.5,
        label=elevation_col,
    )
    ax_elev.set_ylabel("Elevation (m)")
else:
    ax_elev.plot(
        plot_df["dist_m"],
        [0] * len(plot_df),
        linewidth=1.0,
        label="distance axis only",
    )
    ax_elev.set_ylabel("Elevation N/A")

ax_elev.set_title(f"{CASE_NAME} - OSM Semantic Risk Profile")
ax_elev.grid(True, alpha=0.3)
ax_elev.legend(loc="upper right")

# risk score
ax_risk.plot(
    plot_df["dist_m"],
    plot_df[RISK_SCORE_COL],
    linewidth=1.5,
    label=RISK_SCORE_COL,
)

ax_risk.fill_between(
    plot_df["dist_m"],
    0,
    plot_df[RISK_SCORE_COL],
    alpha=0.25,
)

ax_risk.axhline(0.20, linestyle="--", linewidth=0.8, alpha=0.6)
ax_risk.axhline(0.40, linestyle="--", linewidth=0.8, alpha=0.6)
ax_risk.axhline(0.65, linestyle="--", linewidth=0.8, alpha=0.6)

ax_risk.set_ylabel("OSM risk")
ax_risk.set_ylim(0, max(0.25, float(plot_df[RISK_SCORE_COL].max()) * 1.2))
ax_risk.grid(True, alpha=0.3)
ax_risk.legend(loc="upper right")

draw_band(ax_cond, plot_df, conditional_runs, "conditional")
draw_band(ax_weather, plot_df, weather_runs, "weather")
draw_band(ax_nlsc, plot_df, nlsc_runs, "needs NLSC")

ax_nlsc.set_xlabel("Distance (m)")

# legend
used_values = set()
for c in ["conditional_display", "weather_display", "nlsc_display", "activity_display"]:
    used_values.update(plot_df[c].dropna().astype(str).unique().tolist())

legend_handles = [
    Patch(facecolor=FLAG_COLORS.get(v, "#bdc3c7"), label=v)
    for v in sorted(used_values)
    if v not in ["none", "normal", ""]
]

if legend_handles:
    ax_risk.legend(handles=legend_handles, loc="upper right", fontsize=8, ncol=4)

plt.tight_layout()
plt.savefig(OUT_PROFILE_PNG, dpi=200)
plt.close()

print("profile PNG:", OUT_PROFILE_PNG.resolve())


# =========================================================
# 7. QA map
# =========================================================
center = [gdf.geometry.y.mean(), gdf.geometry.x.mean()]

m = folium.Map(
    location=center,
    zoom_start=14,
    tiles="CartoDB positron",
    width="100%",
    height="800px",
)

# route points subsample
if "dist_m" not in gdf.columns:
    gdf["dist_m"] = df["dist_m"].values

if RISK_SCORE_COL not in gdf.columns:
    gdf[RISK_SCORE_COL] = df[RISK_SCORE_COL].values

for col in [
    "osm_semantic_risk_band",
    "conditional_factor_flags",
    "weather_sensitive_flags",
    "needs_nlsc_flags",
    "applied_mapping_hits",
]:
    if col not in gdf.columns and col in df.columns:
        gdf[col] = df[col].values

gdf_qa = gdf[
    (gdf["dist_m"] % QA_MARKER_INTERVAL_M < 1.0)
    | (gdf["dist_m"] == gdf["dist_m"].min())
    | (gdf["dist_m"] == gdf["dist_m"].max())
].copy()

print("QA marker points:", len(gdf_qa))

for _, row in gdf_qa.iterrows():
    score = row.get(RISK_SCORE_COL, None)
    color = risk_color(score)

    popup = (
        f"<pre>"
        f"dist_m: {row.get('dist_m', ''):.1f}\n"
        f"osm_risk_score: {row.get(RISK_SCORE_COL, '')}\n"
        f"osm_risk_band: {row.get('osm_semantic_risk_band', '')}\n"
        f"conditional: {row.get('conditional_factor_flags', '')}\n"
        f"weather_sensitive: {row.get('weather_sensitive_flags', '')}\n"
        f"needs_nlsc: {row.get('needs_nlsc_flags', '')}\n"
        f"applied: {row.get('applied_mapping_hits', '')}"
        f"</pre>"
    )

    folium.CircleMarker(
        location=[row.geometry.y, row.geometry.x],
        radius=4,
        color=color,
        fill=True,
        fill_opacity=0.8,
        popup=folium.Popup(popup, max_width=450),
    ).add_to(m)

folium.LayerControl(collapsed=False).add_to(m)
m.save(OUT_MAP_HTML)

print("QA map:", OUT_MAP_HTML.resolve())


# =========================================================
# 8. Summary
# =========================================================
print("\n--- risk band ---")
if RISK_BAND_COL in df.columns:
    print(df[RISK_BAND_COL].value_counts(dropna=False))

print("\n--- conditional display ---")
print(plot_df["conditional_display"].value_counts(dropna=False).head(20))

print("\n--- weather display ---")
print(plot_df["weather_display"].value_counts(dropna=False).head(20))

print("\n--- needs NLSC display ---")
print(plot_df["nlsc_display"].value_counts(dropna=False).head(20))