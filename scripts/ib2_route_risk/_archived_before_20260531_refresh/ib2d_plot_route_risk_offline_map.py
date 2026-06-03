# -*- coding: utf-8 -*-
from pathlib import Path
import os
import shutil

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from PIL import Image, ImageOps
from shapely.geometry import LineString


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CASE_ID = os.environ.get("CASE_ID", "qixing_xiaoyoukeng_main_peak_20260315")
CASE_NAME_BY_ID = {
    "juansi_waterfall_fitcsv_20260503": "絹絲瀑布 FIT CSV 20260503",
    "qixing_xiaoyoukeng_main_peak_20260315": "小油坑七星山主峰 GPX 20260315",
    "qixing_lengshuikeng_main_peak_20260523": "冷水坑到七星山主峰 GPX 20260523",
}
CASE_NAME = os.environ.get("CASE_NAME", CASE_NAME_BY_ID.get(CASE_ID, CASE_ID))

mpl.rcParams["font.sans-serif"] = [
    "Microsoft JhengHei",
    "Microsoft YaHei",
    "Noto Sans CJK TC",
    "Arial Unicode MS",
    "DejaVu Sans",
]
mpl.rcParams["axes.unicode_minus"] = False

RISK_CSV_CANDIDATES = [
    PROJECT_ROOT / "outputs" / "ib2_v2_route_risk" / CASE_ID / f"{CASE_ID}_route_risk_v2.csv",
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
]

PROFILE_GEOJSON_CANDIDATES = [
    PROJECT_ROOT
    / "outputs"
    / "ib1e_route_profile_contour_window_terrain"
    / CASE_ID
    / f"{CASE_ID}_route_profile_contour_window_terrain_enriched.geojson",
    PROJECT_ROOT / "outputs" / "ib1_route_profile" / CASE_ID / f"{CASE_ID}_route_profile_points.geojson",
]

CONTOUR_FILE = PROJECT_ROOT / "nlsc_raw" / "97233NW" / "向量25K" / "ContourL.shp"
OSM_RAW_DIR = PROJECT_ROOT / "osm_raw_output" / CASE_ID
OUT_DIR = PROJECT_ROOT / "outputs" / "ib2d_route_risk_offline_map" / CASE_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_PNG = OUT_DIR / f"{CASE_ID}_route_risk_offline_map.png"
OUT_SEG_GEOJSON = OUT_DIR / f"{CASE_ID}_route_risk_offline_segments.geojson"
OUT_RADAR_PNG = OUT_DIR / f"{CASE_ID}_route_challenge_radar.png"
OUT_COMBINED_PNG = OUT_DIR / f"{CASE_ID}_route_risk_offline_map_with_radar.png"
RADAR_SOURCE = (
    PROJECT_ROOT
    / "outputs"
    / "ib2e_route_challenge_index"
    / CASE_ID
    / f"{CASE_ID}_route_challenge_radar.png"
)

ROUTE_BUFFER_M = float(os.environ.get("ROUTE_BUFFER_M", "350"))
DPI = int(os.environ.get("IB2D_DPI", "140"))

RISK_COLOR = {
    "low": "#4CAF50",
    "moderate": "#F2C037",
    "high": "#F57C00",
    "very_high": "#D93A3A",
    "unknown": "#9E9E9E",
}
RISK_LEVEL = {"unknown": 0, "low": 1, "moderate": 2, "high": 3, "very_high": 4}

POINT_LAYERS = {
    "trailhead": ("osm_trailhead_raw.geojson", "^", "#1B5E20", "登山口 trailhead"),
    "peak": ("osm_peak_raw.geojson", "*", "#6A1B9A", "山頂 peak"),
    "guidepost": ("osm_guidepost_raw.geojson", "P", "#1565C0", "指標 guidepost"),
    "shelter": ("osm_shelter_raw.geojson", "s", "#795548", "涼亭 shelter"),
    "bench": ("osm_bench_raw.geojson", "v", "#8D6E63", "長椅 bench"),
    "drinking_water": ("osm_drinking_water_raw.geojson", "o", "#0097A7", "飲水 drinking water"),
    "toilets": ("osm_toilets_raw.geojson", "D", "#455A64", "廁所 toilets"),
    "information": ("osm_information_office_raw.geojson", "X", "#EF6C00", "資訊 information"),
}

LINE_LAYERS = {
    "nearby_path": ("osm_highway_raw.geojson", "--", "#8F8F8F", "附近步道 nearby paths"),
    "cliff": ("osm_cliff_raw.geojson", "--", "#8B0000", "崖線 cliff"),
    "waterway": ("osm_waterway_raw.geojson", "-", "#1976D2", "水系 waterway"),
    "handrail": ("osm_handrail_raw.geojson", ":", "#6D4C41", "扶手 handrail"),
    "safety_rope": ("osm_safety_rope_raw.geojson", "-.", "#5D4037", "輔助繩 safety rope"),
}

AREA_LAYERS = {
    "scree": ("osm_scree_raw.geojson", "#D7CCC8", "#8D6E63", "碎石 scree"),
    "wetland": ("osm_wetland_raw.geojson", "#B2DFDB", "#00897B", "濕地 wetland"),
    "water_area": ("osm_water_area_raw.geojson", "#BBDEFB", "#1976D2", "水域 water area"),
    "bare_rock": ("osm_bare_rock_raw.geojson", "#BDBDBD", "#757575", "裸岩 bare rock"),
}


def first_existing(candidates, label):
    for fp in candidates:
        if fp.exists():
            print(f"{label}: {fp}")
            return fp
    raise FileNotFoundError(
        f"Missing {label}. Tried:\n" + "\n".join(str(fp) for fp in candidates)
    )


def norm_band(v):
    if pd.isna(v):
        return "unknown"
    s = str(v).strip().lower()
    return s if s in RISK_COLOR else "unknown"


def pick_band(a, b):
    a = norm_band(a)
    b = norm_band(b)
    return a if RISK_LEVEL[a] >= RISK_LEVEL[b] else b


def read_layer(fp, crs):
    if not fp.exists():
        return gpd.GeoDataFrame(geometry=[], crs=crs)
    try:
        gdf = gpd.read_file(fp)
    except Exception as exc:
        print(f"layer read failed: {fp} | {exc}")
        return gpd.GeoDataFrame(geometry=[], crs=crs)
    if gdf.empty:
        return gpd.GeoDataFrame(geometry=[], crs=crs)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    return gdf.to_crs(crs)


def build_segments(points):
    rows = []
    points = points.sort_values("dist_m").reset_index(drop=True)
    for i in range(len(points) - 1):
        r1 = points.iloc[i]
        r2 = points.iloc[i + 1]
        if r1.geometry is None or r2.geometry is None:
            continue
        if r1.geometry.is_empty or r2.geometry.is_empty:
            continue
        rows.append(
            {
                "seg_id": i,
                "seg_start_dist": float(r1["dist_m"]),
                "seg_end_dist": float(r2["dist_m"]),
                "risk_band": pick_band(r1["risk_band"], r2["risk_band"]),
                "risk_score_smooth": pd.to_numeric(
                    pd.Series([r1.get("risk_score_smooth"), r2.get("risk_score_smooth")]),
                    errors="coerce",
                ).mean(),
                "geometry": LineString([r1.geometry, r2.geometry]),
            }
        )
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=points.crs)


def add_scale_bar(ax, length_m=250):
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    x0 = xlim[0] + (xlim[1] - xlim[0]) * 0.06
    y0 = ylim[0] + (ylim[1] - ylim[0]) * 0.06
    ax.plot([x0, x0 + length_m], [y0, y0], color="black", lw=3, zorder=30)
    ax.plot([x0, x0], [y0 - 12, y0 + 12], color="black", lw=2, zorder=30)
    ax.plot([x0 + length_m, x0 + length_m], [y0 - 12, y0 + 12], color="black", lw=2, zorder=30)
    ax.text(x0 + length_m / 2, y0 + 22, f"{length_m} m", ha="center", va="bottom", fontsize=9)


def add_north_arrow(ax):
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    x = xlim[0] + (xlim[1] - xlim[0]) * 0.06
    y = ylim[1] - (ylim[1] - ylim[0]) * 0.10
    ax.annotate("N", xy=(x, y + 90), xytext=(x, y), ha="center", fontsize=14, arrowprops=dict(arrowstyle="-|>", lw=1.8, color="black"))


def write_combined_image():
    if RADAR_SOURCE.exists():
        shutil.copy2(RADAR_SOURCE, OUT_RADAR_PNG)
    if not OUT_PNG.exists() or not OUT_RADAR_PNG.exists():
        return False
    map_img = Image.open(OUT_PNG).convert("RGB")
    radar_img = Image.open(OUT_RADAR_PNG).convert("RGB")
    target_w = max(720, int(map_img.width * 0.48))
    ratio = target_w / radar_img.width
    radar_img = radar_img.resize((target_w, int(radar_img.height * ratio)), Image.Resampling.LANCZOS)
    pad = 56
    canvas = Image.new(
        "RGB",
        (map_img.width + radar_img.width + pad * 3, max(map_img.height, radar_img.height + pad * 2)),
        "white",
    )
    canvas.paste(map_img, (pad, (canvas.height - map_img.height) // 2))
    radar_box = ImageOps.expand(radar_img, border=1, fill="#D9E1E5")
    canvas.paste(radar_box, (map_img.width + pad * 2, (canvas.height - radar_box.height) // 2))
    canvas.save(OUT_COMBINED_PNG, quality=95)
    return True


def main():
    risk_csv = first_existing(RISK_CSV_CANDIDATES, "risk CSV")
    profile_geojson = first_existing(PROFILE_GEOJSON_CANDIDATES, "profile GeoJSON")

    risk_df = pd.read_csv(risk_csv, low_memory=False, encoding="utf-8-sig")
    points = gpd.read_file(profile_geojson)
    if points.crs is None:
        points = points.set_crs("EPSG:4326")
    points = points.to_crs("EPSG:4326")

    if "dist_m" not in risk_df.columns or "dist_m" not in points.columns:
        raise KeyError("risk CSV and profile GeoJSON must both contain dist_m")
    if "risk_band" not in risk_df.columns:
        if "osm_terrain_combined_risk_band" in risk_df.columns:
            risk_df["risk_band"] = risk_df["osm_terrain_combined_risk_band"]
        else:
            risk_df["risk_band"] = "unknown"
    if "risk_score_smooth" not in risk_df.columns:
        score_col = "risk_score" if "risk_score" in risk_df.columns else "osm_terrain_combined_risk_score"
        risk_df["risk_score_smooth"] = pd.to_numeric(risk_df[score_col], errors="coerce").rolling(9, center=True, min_periods=2).mean()

    risk_df["dist_key"] = risk_df["dist_m"].round(3)
    points["dist_key"] = points["dist_m"].round(3)
    keep = ["dist_key", "risk_band", "risk_score_smooth"]
    merged = points.merge(risk_df[keep], on="dist_key", how="left")
    merged["risk_band"] = merged["risk_band"].map(norm_band)
    merged = gpd.GeoDataFrame(merged, geometry="geometry", crs=points.crs).sort_values("dist_m")

    metric_crs = merged.estimate_utm_crs()
    points_m = merged.to_crs(metric_crs)
    route_line = LineString(list(points_m.geometry))
    route_buffer = route_line.buffer(ROUTE_BUFFER_M)
    seg_gdf = build_segments(points_m)
    seg_gdf.to_file(OUT_SEG_GEOJSON, driver="GeoJSON")

    contour_m = gpd.GeoDataFrame(geometry=[], crs=metric_crs)
    if CONTOUR_FILE.exists():
        contour_m = read_layer(CONTOUR_FILE, metric_crs)
        if not contour_m.empty:
            contour_m = contour_m[contour_m.intersects(route_buffer)].copy()

    fig, (ax, ax_leg) = plt.subplots(
        1,
        2,
        figsize=(15, 10),
        dpi=DPI,
        gridspec_kw={"width_ratios": [4.8, 1.4]},
    )

    if not contour_m.empty:
        contour_m.plot(ax=ax, color="#BDBDBD", linewidth=0.45, alpha=0.8, zorder=0)
        elev_col = next((c for c in ["zv2", "elev", "elevation", "height"] if c in contour_m.columns), None)
        if elev_col:
            major = contour_m[pd.to_numeric(contour_m[elev_col], errors="coerce").fillna(-999) % 50 == 0]
            if not major.empty:
                major.plot(ax=ax, color="#757575", linewidth=0.75, alpha=0.9, zorder=0)

    for _, (filename, face, edge, label) in AREA_LAYERS.items():
        layer = read_layer(OSM_RAW_DIR / filename, metric_crs)
        if not layer.empty:
            layer = layer[layer.intersects(route_buffer)]
            if not layer.empty:
                layer.plot(ax=ax, facecolor=face, edgecolor=edge, alpha=0.35, linewidth=0.8, zorder=1)

    for _, (filename, linestyle, color, label) in LINE_LAYERS.items():
        layer = read_layer(OSM_RAW_DIR / filename, metric_crs)
        if not layer.empty:
            layer = layer[layer.intersects(route_buffer)]
            if not layer.empty:
                layer.plot(ax=ax, color=color, linestyle=linestyle, linewidth=1.2, alpha=0.75, zorder=2)

    seg_gdf.plot(ax=ax, color="#D0D0D0", linewidth=1.0, zorder=3)
    for band in ["low", "moderate", "high", "very_high", "unknown"]:
        sub = seg_gdf[seg_gdf["risk_band"] == band]
        if not sub.empty:
            sub.plot(ax=ax, color=RISK_COLOR[band], linewidth=4.2, alpha=0.95, zorder=5)

    for _, (filename, marker, color, label) in POINT_LAYERS.items():
        layer = read_layer(OSM_RAW_DIR / filename, metric_crs)
        if not layer.empty:
            layer = layer[layer.intersects(route_buffer)]
            if not layer.empty:
                geom = layer.geometry
                if not all(geom.geom_type == "Point"):
                    geom = geom.representative_point()
                ax.scatter(geom.x, geom.y, c=color, marker=marker, s=50, edgecolors="white", linewidths=0.7, zorder=8)

    start = points_m.geometry.iloc[0]
    end = points_m.geometry.iloc[-1]
    ax.scatter(start.x, start.y, s=120, c="#2E7D32", marker="o", edgecolors="white", zorder=10)
    ax.scatter(end.x, end.y, s=120, c="#C62828", marker="s", edgecolors="white", zorder=10)
    ax.text(start.x + 15, start.y + 15, "Start", color="#1B5E20", weight="bold")
    ax.text(end.x + 15, end.y + 15, "End", color="#B71C1C", weight="bold")

    minx, miny, maxx, maxy = route_buffer.bounds
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(f"{CASE_NAME}\nOffline risk map + OSM context", fontsize=16)
    add_north_arrow(ax)
    add_scale_bar(ax, 250)

    ax_leg.axis("off")
    osm_handles = [
        Line2D([0], [0], marker=marker, color="w", label=label, markerfacecolor=color, markersize=8)
        for _, (_, marker, color, label) in POINT_LAYERS.items()
    ]
    line_handles = [
        Line2D([0], [0], color=color, linestyle=linestyle, lw=2, label=label)
        for _, (_, linestyle, color, label) in LINE_LAYERS.items()
    ]
    risk_handles = [
        Line2D([0], [0], color=RISK_COLOR[band], lw=4, label=band)
        for band in ["low", "moderate", "high", "very_high"]
        if band in set(seg_gdf["risk_band"])
    ]
    leg1 = ax_leg.legend(handles=osm_handles + line_handles, title="OSM features", loc="upper left", fontsize=8)
    ax_leg.add_artist(leg1)
    ax_leg.legend(handles=risk_handles, title="Risk band", loc="lower left", fontsize=9)

    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=DPI, facecolor="white")
    plt.close(fig)

    combined = write_combined_image()

    print("case:", CASE_ID)
    print("PNG:", OUT_PNG)
    print("segment GeoJSON:", OUT_SEG_GEOJSON)
    if OUT_RADAR_PNG.exists():
        print("THCI radar PNG:", OUT_RADAR_PNG)
    if combined:
        print("combined map + radar PNG:", OUT_COMBINED_PNG)
    print("\n=== risk_band ===")
    print(seg_gdf["risk_band"].value_counts(dropna=False))
    print("contour features within buffer:", len(contour_m))


if __name__ == "__main__":
    main()
