# =========================================================
# ib1e_plot_osm_terrain_risk_profile.py
#
# 目的：
# - 讀取 ib1e_enrich_route_profile_with_contour_window_terrain.py 輸出
# - 繪製 OSM semantic risk + NLSC terrain risk + hydro-terrain amplifier
# - 輸出 profile PNG 與 QA map
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

PROJECT_ROOT = Path("C:/mountain_work/115_osm")

INPUT_CSV = (
    PROJECT_ROOT
    / "outputs"
    / "ib1e_route_profile_contour_window_terrain"
    / CASE_ID
    / f"{CASE_ID}_route_profile_contour_window_terrain_enriched.csv"
)

INPUT_GEOJSON = (
    PROJECT_ROOT
    / "outputs"
    / "ib1e_route_profile_contour_window_terrain"
    / CASE_ID
    / f"{CASE_ID}_route_profile_contour_window_terrain_enriched.geojson"
)

OUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "ib1e_osm_terrain_risk_plot"
    / CASE_ID
)
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_PROFILE_PNG = OUT_DIR / f"{CASE_ID}_osm_terrain_risk_profile.png"
OUT_MAP_HTML = OUT_DIR / f"{CASE_ID}_osm_terrain_risk_map.html"


# =========================================================
# 1. 欄位設定
# =========================================================
DIST_COL = "dist_m"

ELEVATION_CANDIDATES = [
    "ele_smooth",
    "ele_gpx_m",
    "ele_m",
]

SCORE_COLS = [
    "osm_semantic_risk_score",
    "terrain_window_risk_score",
    "hydro_terrain_amplifier_score",
    "osm_terrain_combined_risk_score",
]

BAND_COL = "osm_terrain_combined_risk_band"

QA_MARKER_INTERVAL_M = 20.0

RISK_BAND_COLORS = {
    "low": "#2ecc71",
    "moderate": "#f1c40f",
    "high": "#e67e22",
    "very_high": "#e74c3c",
}

SLOPE_BAND_COLORS = {
    "flat": "#2ecc71",
    "gentle": "#a3e635",
    "moderate": "#f1c40f",
    "steep": "#e67e22",
    "very_steep": "#e74c3c",
    "unknown": "#bdc3c7",
}


# =========================================================
# 2. 工具函式
# =========================================================
def choose_elevation_col(df):
    for col in ELEVATION_CANDIDATES:
        if col in df.columns:
            return col
    return None


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


def build_runs(df, col):
    values = df[col].fillna("unknown").astype(str).tolist()

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


def draw_slope_band(ax, plot_df, runs):
    for s, e, value in runs:
        x0 = float(plot_df.loc[s, DIST_COL])
        x1 = float(plot_df.loc[e, DIST_COL])

        if e + 1 < len(plot_df):
            x1 = float(plot_df.loc[e + 1, DIST_COL])

        color = SLOPE_BAND_COLORS.get(str(value), "#bdc3c7")

        ax.broken_barh(
            [(x0, max(0.1, x1 - x0))],
            (0, 1),
            facecolors=color,
        )

    ax.set_yticks([0.5])
    ax.set_yticklabels(["NLSC slope"])
    ax.set_ylim(0, 1)
    ax.grid(False)


# =========================================================
# 3. 檢查輸入
# =========================================================
for fp in [INPUT_CSV, INPUT_GEOJSON]:
    if not fp.exists():
        raise FileNotFoundError(f"找不到輸入檔：{fp.resolve()}")


# =========================================================
# 4. 讀資料
# =========================================================
df = pd.read_csv(INPUT_CSV, low_memory=False)
gdf = gpd.read_file(INPUT_GEOJSON).to_crs("EPSG:4326")

if len(df) != len(gdf):
    raise ValueError(f"CSV / GeoJSON 筆數不一致：csv={len(df)}, geojson={len(gdf)}")

if DIST_COL not in df.columns:
    raise ValueError(f"找不到距離欄位：{DIST_COL}")

for col in SCORE_COLS:
    if col not in df.columns:
        raise ValueError(f"找不到 score 欄位：{col}")

elev_col = choose_elevation_col(df)

print("case:", CASE_ID)
print("rows:", len(df))
print("elevation_col:", elev_col)

for col in SCORE_COLS:
    print(f"{col} min/mean/max:", df[col].min(), df[col].mean(), df[col].max())


# =========================================================
# 5. 整理視覺化欄位
# =========================================================
plot_df = df.copy().reset_index(drop=True)

if "slope_band_window_nlsc" not in plot_df.columns:
    plot_df["slope_band_window_nlsc"] = "unknown"

slope_runs = build_runs(plot_df, "slope_band_window_nlsc")


# =========================================================
# 6. Profile PNG
# =========================================================
fig, axes = plt.subplots(
    4,
    1,
    figsize=(16, 11),
    sharex=True,
    gridspec_kw={"height_ratios": [4.0, 3.0, 2.0, 0.55]},
)

ax_elev = axes[0]
ax_scores = axes[1]
ax_amp = axes[2]
ax_slope = axes[3]

# Elevation
if elev_col:
    ax_elev.plot(
        plot_df[DIST_COL],
        plot_df[elev_col],
        linewidth=1.5,
        label=elev_col,
    )
    ax_elev.set_ylabel("Elevation (m)")
else:
    ax_elev.plot(plot_df[DIST_COL], [0] * len(plot_df), linewidth=1.0)
    ax_elev.set_ylabel("Elevation N/A")

ax_elev.set_title(f"{CASE_ID} - OSM + NLSC Terrain Risk Profile")
ax_elev.grid(True, alpha=0.3)
ax_elev.legend(loc="upper right")

# Scores
ax_scores.plot(
    plot_df[DIST_COL],
    plot_df["osm_semantic_risk_score"],
    linewidth=1.2,
    label="OSM semantic risk",
)

ax_scores.plot(
    plot_df[DIST_COL],
    plot_df["terrain_window_risk_score"],
    linewidth=1.2,
    label="NLSC terrain window risk",
)

ax_scores.plot(
    plot_df[DIST_COL],
    plot_df["osm_terrain_combined_risk_score"],
    linewidth=1.8,
    label="Combined OSM+terrain risk",
)

ax_scores.axhline(0.20, linestyle="--", linewidth=0.8, alpha=0.6)
ax_scores.axhline(0.40, linestyle="--", linewidth=0.8, alpha=0.6)
ax_scores.axhline(0.65, linestyle="--", linewidth=0.8, alpha=0.6)

ax_scores.set_ylabel("Risk score")
ax_scores.set_ylim(
    0,
    max(
        0.8,
        float(plot_df["osm_terrain_combined_risk_score"].max()) * 1.15,
    )
)
ax_scores.grid(True, alpha=0.3)
ax_scores.legend(loc="upper right")

# Hydro terrain amplifier
ax_amp.plot(
    plot_df[DIST_COL],
    plot_df["hydro_terrain_amplifier_score"],
    linewidth=1.3,
    label="Hydro-terrain amplifier",
)

ax_amp.fill_between(
    plot_df[DIST_COL],
    0,
    plot_df["hydro_terrain_amplifier_score"],
    alpha=0.25,
)

ax_amp.set_ylabel("Hydro-terrain")
ax_amp.set_ylim(
    0,
    max(0.5, float(plot_df["hydro_terrain_amplifier_score"].max()) * 1.2),
)
ax_amp.grid(True, alpha=0.3)
ax_amp.legend(loc="upper right")

# Slope band
draw_slope_band(ax_slope, plot_df, slope_runs)
ax_slope.set_xlabel("Distance (m)")

legend_handles = [
    Patch(facecolor=color, label=label)
    for label, color in SLOPE_BAND_COLORS.items()
]

ax_slope.legend(
    handles=legend_handles,
    loc="upper right",
    fontsize=8,
    ncol=6,
)

plt.tight_layout()
plt.savefig(OUT_PROFILE_PNG, dpi=200)
plt.close()

print("profile PNG:", OUT_PROFILE_PNG.resolve())


# =========================================================
# 7. QA map
# =========================================================
if DIST_COL not in gdf.columns:
    gdf[DIST_COL] = df[DIST_COL].values

for col in [
    "osm_semantic_risk_score",
    "terrain_window_risk_score",
    "hydro_terrain_amplifier_score",
    "osm_terrain_combined_risk_score",
    "osm_terrain_combined_risk_band",
    "slope_band_window_nlsc",
    "elev_range_nlsc_window",
    "contour_density_20m_nlsc_window",
    "needs_nlsc_flags",
    "weather_sensitive_flags",
]:
    if col not in gdf.columns and col in df.columns:
        gdf[col] = df[col].values

center = [gdf.geometry.y.mean(), gdf.geometry.x.mean()]

m = folium.Map(
    location=center,
    zoom_start=14,
    tiles="CartoDB positron",
    width="100%",
    height="800px",
)

gdf_qa = gdf[
    (gdf[DIST_COL] % QA_MARKER_INTERVAL_M < 1.0)
    | (gdf[DIST_COL] == gdf[DIST_COL].min())
    | (gdf[DIST_COL] == gdf[DIST_COL].max())
].copy()

print("QA marker points:", len(gdf_qa))

for _, row in gdf_qa.iterrows():
    score = row.get("osm_terrain_combined_risk_score", None)
    color = risk_color(score)

    popup = (
        f"<pre>"
        f"dist_m: {row.get(DIST_COL, ''):.1f}\n"
        f"osm_score: {row.get('osm_semantic_risk_score', '')}\n"
        f"terrain_score: {row.get('terrain_window_risk_score', '')}\n"
        f"hydro_amp: {row.get('hydro_terrain_amplifier_score', '')}\n"
        f"combined_score: {row.get('osm_terrain_combined_risk_score', '')}\n"
        f"combined_band: {row.get('osm_terrain_combined_risk_band', '')}\n"
        f"slope_band_nlsc: {row.get('slope_band_window_nlsc', '')}\n"
        f"elev_range_nlsc: {row.get('elev_range_nlsc_window', '')}\n"
        f"contour_density_20m: {row.get('contour_density_20m_nlsc_window', '')}\n"
        f"needs_nlsc: {row.get('needs_nlsc_flags', '')}\n"
        f"weather_sensitive: {row.get('weather_sensitive_flags', '')}"
        f"</pre>"
    )

    folium.CircleMarker(
        location=[row.geometry.y, row.geometry.x],
        radius=4,
        color=color,
        fill=True,
        fill_opacity=0.85,
        popup=folium.Popup(popup, max_width=500),
    ).add_to(m)

folium.LayerControl(collapsed=False).add_to(m)
m.save(OUT_MAP_HTML)

print("QA map:", OUT_MAP_HTML.resolve())


# =========================================================
# 8. Summary
# =========================================================
print("\n=== combined risk band ===")
if "osm_terrain_combined_risk_band" in df.columns:
    print(df["osm_terrain_combined_risk_band"].value_counts(dropna=False))

print("\n=== slope_band_window_nlsc ===")
print(df["slope_band_window_nlsc"].value_counts(dropna=False))

print("\n=== hydro_terrain_amplifier_score ===")
print(df["hydro_terrain_amplifier_score"].describe())

print("\n=== terrain_window_risk_score ===")
print(df["terrain_window_risk_score"].describe())