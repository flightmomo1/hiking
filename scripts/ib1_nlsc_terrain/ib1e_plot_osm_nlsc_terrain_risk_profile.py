# -*- coding: utf-8 -*-
from pathlib import Path
import argparse
import os

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_path(value, project_root=PROJECT_ROOT):
    if value is None:
        return None

    p = Path(value)
    if p.is_absolute():
        return p

    return project_root / p


def parse_args():
    parser = argparse.ArgumentParser(
        description="Plot ib1e OSM + NLSC terrain risk profile and map"
    )

    parser.add_argument(
        "--case-id",
        default=os.environ.get("CASE_ID", "qixing_xiaoyoukeng_main_peak_20260315"),
        help="Case ID, e.g. qixing_lengshuikeng_main_peak_20260523",
    )
    parser.add_argument(
        "--case-name",
        default=os.environ.get("CASE_NAME", None),
        help="Human-readable case name. Default: same as case-id.",
    )
    parser.add_argument(
        "--input-csv",
        default=None,
        help="Input ib1e enriched CSV. If omitted, use default output path by case-id.",
    )
    parser.add_argument(
        "--input-geojson",
        default=None,
        help="Input ib1e enriched GeoJSON. If omitted, use default output path by case-id.",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Output directory. If omitted, use outputs/ib1e_osm_nlsc_terrain_risk_plot/<case-id>.",
    )

    return parser.parse_args()


args = parse_args()

CASE_ID = args.case_id
CASE_NAME = args.case_name or CASE_ID

mpl.rcParams["font.sans-serif"] = [
    "Microsoft JhengHei",
    "Microsoft YaHei",
    "Noto Sans CJK TC",
    "Arial Unicode MS",
    "DejaVu Sans",
]
mpl.rcParams["axes.unicode_minus"] = False


def first_existing(candidates, label):
    for fp in candidates:
        if fp.exists():
            print(f"{label}: {fp}")
            return fp
    raise FileNotFoundError(
        f"Missing {label}. Tried:\n" + "\n".join(str(fp) for fp in candidates)
    )


if args.input_csv is not None:
    INPUT_CSV = resolve_path(args.input_csv)
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Missing input CSV: {INPUT_CSV.resolve()}")
    print(f"input CSV: {INPUT_CSV}")
else:
    INPUT_CSV = first_existing(
        [
            PROJECT_ROOT
            / "outputs"
            / "ib1e_route_profile_contour_window_terrain"
            / CASE_ID
            / f"{CASE_ID}_route_profile_contour_window_terrain_enriched.csv",
            PROJECT_ROOT
            / "outputs"
            / "ib1e_osm_nlsc_terrain_risk"
            / CASE_ID
            / f"{CASE_ID}_osm_nlsc_terrain_risk_profile.csv",
        ],
        "input CSV",
    )

if args.input_geojson is not None:
    INPUT_GEOJSON = resolve_path(args.input_geojson)
    if not INPUT_GEOJSON.exists():
        raise FileNotFoundError(f"Missing input GeoJSON: {INPUT_GEOJSON.resolve()}")
    print(f"input GeoJSON: {INPUT_GEOJSON}")
else:
    INPUT_GEOJSON = first_existing(
        [
            PROJECT_ROOT
            / "outputs"
            / "ib1e_route_profile_contour_window_terrain"
            / CASE_ID
            / f"{CASE_ID}_route_profile_contour_window_terrain_enriched.geojson",
            PROJECT_ROOT
            / "outputs"
            / "ib1e_osm_nlsc_terrain_risk"
            / CASE_ID
            / f"{CASE_ID}_osm_nlsc_terrain_risk_profile.geojson",
        ],
        "input GeoJSON",
    )

if args.out_dir is not None:
    OUT_DIR = resolve_path(args.out_dir)
else:
    OUT_DIR = (
        PROJECT_ROOT / "outputs" / "ib1e_osm_nlsc_terrain_risk_plot" / CASE_ID
    )
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PROFILE_PNG = OUT_DIR / f"{CASE_ID}_osm_nlsc_terrain_risk_profile.png"
OUT_MAP_HTML = OUT_DIR / f"{CASE_ID}_osm_nlsc_terrain_risk_map.html"

SCORE_COLS = [
    "osm_semantic_risk_score",
    "terrain_window_risk_score",
    "hydro_terrain_amplifier_score",
    "osm_terrain_combined_risk_score",
]
RISK_BAND_COL = "osm_terrain_combined_risk_band"
SLOPE_BAND_COL = "slope_band_window_nlsc"

RISK_COLORS = {
    "low": "#4CAF50",
    "moderate": "#F2C037",
    "high": "#F57C00",
    "very_high": "#D93A3A",
    "unknown": "#9E9E9E",
}

SLOPE_COLORS = {
    "flat": "#4CAF50",
    "gentle": "#A5D6A7",
    "moderate": "#F2C037",
    "steep": "#F57C00",
    "very_steep": "#D93A3A",
    "unknown": "#9E9E9E",
}


def norm_band(v):
    if pd.isna(v):
        return "unknown"
    s = str(v).strip().lower()
    return s if s else "unknown"


def build_runs(df, col):
    values = df[col].fillna("unknown").astype(str).tolist()
    if not values:
        return []
    runs = []
    start = 0
    for i in range(1, len(values)):
        if values[i] != values[start]:
            runs.append((start, i - 1, values[start]))
            start = i
    runs.append((start, len(values) - 1, values[start]))
    return runs


def draw_strip(ax, df, col, colors, label):
    ax.set_ylim(0, 1)
    ax.set_yticks([0.5])
    ax.set_yticklabels([label])
    ax.grid(False)
    for start, end, value in build_runs(df, col):
        x0 = float(df.loc[start, "dist_m"])
        x1 = float(df.loc[end, "dist_m"])
        if end + 1 < len(df):
            x1 = float(df.loc[end + 1, "dist_m"])
        ax.broken_barh(
            [(x0, max(0.1, x1 - x0))],
            (0, 1),
            facecolors=colors.get(norm_band(value), colors["unknown"]),
        )


def main():
    df = pd.read_csv(INPUT_CSV, low_memory=False, encoding="utf-8-sig")
    gdf = gpd.read_file(INPUT_GEOJSON)

    if df.empty:
        raise ValueError(f"Empty input CSV: {INPUT_CSV}")
    if "dist_m" not in df.columns:
        raise KeyError("input CSV must contain dist_m")
    for col in SCORE_COLS:
        if col not in df.columns:
            raise KeyError(f"input CSV missing score column: {col}")

    df = df.sort_values("dist_m").reset_index(drop=True)
    df[RISK_BAND_COL] = (
        df[RISK_BAND_COL].map(norm_band) if RISK_BAND_COL in df.columns else "unknown"
    )
    df[SLOPE_BAND_COL] = (
        df[SLOPE_BAND_COL].map(norm_band) if SLOPE_BAND_COL in df.columns else "unknown"
    )

    elev_col = next((c for c in ["ele_smooth", "ele_gpx_m"] if c in df.columns), None)

    rows = 5 if elev_col else 4
    fig, axes = plt.subplots(
        rows,
        1,
        figsize=(15, 9),
        sharex=True,
        gridspec_kw={"height_ratios": [1.8] + [1.4] * 3 + [0.35] * (rows - 4)},
    )

    ax_i = 0
    if elev_col:
        axes[ax_i].plot(df["dist_m"], df[elev_col], color="#455A64", lw=1.6)
        axes[ax_i].set_ylabel("Elevation (m)")
        axes[ax_i].grid(True, alpha=0.25)
        ax_i += 1

    axes[ax_i].plot(df["dist_m"], df["osm_semantic_risk_score"], label="OSM semantic", lw=1.5)
    axes[ax_i].plot(df["dist_m"], df["terrain_window_risk_score"], label="Terrain window", lw=1.5)
    axes[ax_i].plot(df["dist_m"], df["hydro_terrain_amplifier_score"], label="Hydro amplifier", lw=1.5)
    axes[ax_i].set_ylabel("Component")
    axes[ax_i].set_ylim(0, 1)
    axes[ax_i].grid(True, alpha=0.25)
    axes[ax_i].legend(loc="upper right", ncol=3, fontsize=9)
    ax_i += 1

    axes[ax_i].plot(
        df["dist_m"],
        df["osm_terrain_combined_risk_score"],
        color="black",
        label="combined risk",
        lw=1.8,
    )
    axes[ax_i].set_ylabel("Combined")
    axes[ax_i].set_ylim(0, 1)
    axes[ax_i].grid(True, alpha=0.25)
    axes[ax_i].legend(loc="upper right", fontsize=9)
    ax_i += 1

    draw_strip(axes[ax_i], df, RISK_BAND_COL, RISK_COLORS, "risk band")
    ax_i += 1
    if ax_i < rows:
        draw_strip(axes[ax_i], df, SLOPE_BAND_COL, SLOPE_COLORS, "slope band")

    axes[-1].set_xlabel("Distance (m)")
    fig.suptitle(f"{CASE_NAME}\nOSM + NLSC terrain risk profile", fontsize=16)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(OUT_PROFILE_PNG, dpi=180)
    plt.close(fig)

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    gdf = gdf.to_crs("EPSG:4326")
    if len(gdf) == len(df):
        gdf = gdf.copy()
        gdf[RISK_BAND_COL] = df[RISK_BAND_COL].values

    center = [float(gdf.geometry.y.mean()), float(gdf.geometry.x.mean())]
    fmap = gpd.GeoDataFrame(gdf, geometry="geometry", crs="EPSG:4326")
    import folium

    m = folium.Map(location=center, zoom_start=15, tiles="OpenStreetMap")
    for _, row in fmap.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        band = norm_band(row.get(RISK_BAND_COL, "unknown"))
        folium.CircleMarker(
            location=[geom.y, geom.x],
            radius=2,
            color=RISK_COLORS.get(band, RISK_COLORS["unknown"]),
            fill=True,
            fill_opacity=0.75,
            popup=f"{row.get('dist_m', '')} m / {band}",
        ).add_to(m)
    m.save(str(OUT_MAP_HTML))

    print("case:", CASE_ID)
    print("rows:", len(df))
    print("PNG:", OUT_PROFILE_PNG)
    print("HTML:", OUT_MAP_HTML)
    print(df[RISK_BAND_COL].value_counts(dropna=False))


if __name__ == "__main__":
    main()
