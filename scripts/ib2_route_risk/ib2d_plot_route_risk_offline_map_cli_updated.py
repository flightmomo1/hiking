# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from PIL import Image, ImageOps
from shapely.geometry import LineString


PROJECT_ROOT = Path(__file__).resolve().parents[2]

mpl.rcParams["font.sans-serif"] = [
    "Microsoft JhengHei",
    "Microsoft YaHei",
    "Noto Sans CJK TC",
    "Arial Unicode MS",
    "DejaVu Sans",
]
mpl.rcParams["axes.unicode_minus"] = False

ROUTE_BUFFER_M = 350.0
DPI = 140

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
    "peak": ("osm_peak_raw.geojson", "*", "#6A1B9A", "山峰 peak"),
    "guidepost": ("osm_guidepost_raw.geojson", "P", "#1565C0", "指標 guidepost"),
    "shelter": ("osm_shelter_raw.geojson", "s", "#795548", "避難/休憩 shelter"),
    "bench": ("osm_bench_raw.geojson", "v", "#8D6E63", "座椅 bench"),
    "drinking_water": ("osm_drinking_water_raw.geojson", "o", "#0097A7", "飲水 drinking water"),
    "toilets": ("osm_toilets_raw.geojson", "D", "#455A64", "廁所 toilets"),
    "information": ("osm_information_office_raw.geojson", "X", "#EF6C00", "資訊 information"),
}

LINE_LAYERS = {
    "nearby_path": ("osm_highway_raw.geojson", "--", "#8F8F8F", "鄰近路徑 nearby paths"),
    "cliff": ("osm_cliff_raw.geojson", "--", "#8B0000", "崖線 cliff"),
    "waterway": ("osm_waterway_raw.geojson", "-", "#1976D2", "水系 waterway"),
    "handrail": ("osm_handrail_raw.geojson", ":", "#6D4C41", "扶手 handrail"),
    "safety_rope": ("osm_safety_rope_raw.geojson", "-.", "#5D4037", "安全繩 safety rope"),
}

AREA_LAYERS = {
    "scree": ("osm_scree_raw.geojson", "#D7CCC8", "#8D6E63", "碎石坡 scree"),
    "wetland": ("osm_wetland_raw.geojson", "#B2DFDB", "#00897B", "濕地 wetland"),
    "water_area": ("osm_water_area_raw.geojson", "#BBDEFB", "#1976D2", "水域 water area"),
    "bare_rock": ("osm_bare_rock_raw.geojson", "#BDBDBD", "#757575", "裸岩 bare rock"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot ib2d offline route risk map with OSM/NLSC context and radar inset."
    )
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--case-name", default=None)
    parser.add_argument("--risk-csv", default=None)
    parser.add_argument("--risk-geojson", default=None)
    parser.add_argument("--profile-geojson", default=None)
    parser.add_argument("--osm-raw-dir", default=None)
    parser.add_argument(
        "--contour-fp",
        default=None,
        help="Defaults to nlsc_raw/97233SW/向量25K/ContourL.shp.",
    )
    parser.add_argument("--out-dir", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def default_risk_csv(case_id: str) -> Path:
    return PROJECT_ROOT / "outputs" / "ib2_v2_route_risk" / case_id / f"{case_id}_route_risk_v2.csv"


def default_risk_geojson(case_id: str) -> Path:
    return PROJECT_ROOT / "outputs" / "ib2_v2_route_risk" / case_id / f"{case_id}_route_risk_v2.geojson"


def default_profile_geojson(case_id: str) -> Path:
    return (
        PROJECT_ROOT
        / "outputs"
        / "ib1e_route_profile_contour_window_terrain"
        / case_id
        / f"{case_id}_route_profile_contour_window_terrain_enriched.geojson"
    )


def default_osm_raw_dir(case_id: str) -> Path:
    return PROJECT_ROOT / "osm_raw_output" / case_id


def default_contour_fp() -> Path:
    return PROJECT_ROOT / "nlsc_raw" / "97233SW" / "向量25K" / "ContourL.shp"


def default_out_dir(case_id: str) -> Path:
    return PROJECT_ROOT / "outputs" / "ib2d_route_risk_offline_map" / case_id


def norm_band(v) -> str:
    if pd.isna(v):
        return "unknown"
    s = str(v).strip().lower()
    return s if s in RISK_COLOR else "unknown"


def pick_band(a, b) -> str:
    a = norm_band(a)
    b = norm_band(b)
    return a if RISK_LEVEL[a] >= RISK_LEVEL[b] else b


def numeric_col(df: pd.DataFrame, col: str, default=0.0) -> pd.Series:
    if col in df.columns:
        source = df[col]
    else:
        source = pd.Series(default, index=df.index)
    return pd.to_numeric(source, errors="coerce").fillna(default)


def ensure_risk_aliases(risk_df: pd.DataFrame) -> pd.DataFrame:
    risk_df = risk_df.copy()
    if "risk_band" not in risk_df.columns:
        if "osm_terrain_combined_risk_band" in risk_df.columns:
            risk_df["risk_band"] = risk_df["osm_terrain_combined_risk_band"]
        else:
            risk_df["risk_band"] = "unknown"
    risk_df["risk_band"] = risk_df["risk_band"].map(norm_band)

    if "risk_score" not in risk_df.columns:
        if "osm_terrain_combined_risk_score" in risk_df.columns:
            risk_df["risk_score"] = numeric_col(risk_df, "osm_terrain_combined_risk_score")
        else:
            risk_df["risk_score"] = 0.0
    else:
        risk_df["risk_score"] = numeric_col(risk_df, "risk_score")

    if "risk_score_raw" not in risk_df.columns:
        risk_df["risk_score_raw"] = numeric_col(risk_df, "osm_terrain_combined_risk_score_raw", np.nan)
        risk_df["risk_score_raw"] = risk_df["risk_score_raw"].fillna(risk_df["risk_score"])
    else:
        risk_df["risk_score_raw"] = numeric_col(risk_df, "risk_score_raw")

    if "risk_score_smooth" not in risk_df.columns:
        risk_df["risk_score_smooth"] = risk_df["risk_score"].rolling(9, center=True, min_periods=2).mean()
    else:
        risk_df["risk_score_smooth"] = numeric_col(risk_df, "risk_score_smooth", np.nan)
        if risk_df["risk_score_smooth"].isna().all():
            risk_df["risk_score_smooth"] = risk_df["risk_score"].rolling(9, center=True, min_periods=2).mean()
        risk_df["risk_score_smooth"] = risk_df["risk_score_smooth"].fillna(risk_df["risk_score"])

    for col in ["effort_score", "exposure_score", "terrain_score"]:
        risk_df[col] = numeric_col(risk_df, col, 0.0)
    if "effort_slope_band" not in risk_df.columns:
        slope_col = next(
            (
                c
                for c in ["slope_band_window", "slope_band_window_nlsc", "terrain_slope_band_window", "slope_band"]
                if c in risk_df.columns
            ),
            None,
        )
        risk_df["effort_slope_band"] = risk_df[slope_col].astype(str) if slope_col else "unknown"

    required = [
        "dist_m",
        "lat",
        "lon",
        "risk_score",
        "risk_score_raw",
        "risk_score_smooth",
        "risk_band",
        "effort_score",
        "exposure_score",
        "terrain_score",
        "effort_slope_band",
    ]
    missing = [col for col in required if col not in risk_df.columns]
    if missing:
        raise KeyError(f"risk CSV missing required columns after aliasing: {missing}")
    return risk_df


def read_layer(fp: Path, crs) -> gpd.GeoDataFrame:
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


def load_points(profile_geojson: Path, risk_geojson: Path) -> gpd.GeoDataFrame:
    source = profile_geojson if profile_geojson.exists() else risk_geojson
    if not source.exists():
        raise FileNotFoundError(f"Missing profile/risk GeoJSON: {profile_geojson} | {risk_geojson}")
    points = gpd.read_file(source)
    if points.crs is None:
        points = points.set_crs("EPSG:4326")
    return points.to_crs("EPSG:4326")


def build_segments(points: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
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
                "effort_score": pd.to_numeric(
                    pd.Series([r1.get("effort_score"), r2.get("effort_score")]),
                    errors="coerce",
                ).mean(),
                "exposure_score": pd.to_numeric(
                    pd.Series([r1.get("exposure_score"), r2.get("exposure_score")]),
                    errors="coerce",
                ).mean(),
                "terrain_score": pd.to_numeric(
                    pd.Series([r1.get("terrain_score"), r2.get("terrain_score")]),
                    errors="coerce",
                ).mean(),
                "geometry": LineString([r1.geometry.coords[0], r2.geometry.coords[0]]),
            }
        )
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=points.crs)


def add_scale_bar(ax, length_m=250) -> None:
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    x0 = xlim[0] + (xlim[1] - xlim[0]) * 0.06
    y0 = ylim[0] + (ylim[1] - ylim[0]) * 0.06
    ax.plot([x0, x0 + length_m], [y0, y0], color="black", lw=3, zorder=30)
    ax.plot([x0, x0], [y0 - 12, y0 + 12], color="black", lw=2, zorder=30)
    ax.plot([x0 + length_m, x0 + length_m], [y0 - 12, y0 + 12], color="black", lw=2, zorder=30)
    ax.text(x0 + length_m / 2, y0 + 22, f"{length_m} m", ha="center", va="bottom", fontsize=9)


def add_north_arrow(ax) -> None:
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    x = xlim[0] + (xlim[1] - xlim[0]) * 0.06
    y = ylim[1] - (ylim[1] - ylim[0]) * 0.10
    ax.annotate(
        "N",
        xy=(x, y + 90),
        xytext=(x, y),
        ha="center",
        fontsize=14,
        arrowprops=dict(arrowstyle="-|>", lw=1.8, color="black"),
    )


def pick_elevation_col(df: pd.DataFrame) -> str | None:
    candidates = [
        "ele_smooth",
        "ele_gpx_m",
        "elevation_m",
        "elev_m",
        "ele_m",
        "elevation",
        "elev",
        "ele",
        "height",
    ]
    for col in candidates:
        if col in df.columns:
            values = pd.to_numeric(df[col], errors="coerce")
            if values.notna().any():
                return col
    return None


def plot_elevation_profile(ax, merged: gpd.GeoDataFrame) -> None:
    profile = merged.sort_values("dist_m").copy()
    elev_col = pick_elevation_col(profile)
    if elev_col is None:
        ax.axis("off")
        ax.text(
            0.5,
            0.5,
            "Elevation profile unavailable",
            ha="center",
            va="center",
            transform=ax.transAxes,
            fontsize=11,
            color="#666666",
        )
        return

    dist_km = pd.to_numeric(profile["dist_m"], errors="coerce") / 1000.0
    elev_m = pd.to_numeric(profile[elev_col], errors="coerce")
    valid = dist_km.notna() & elev_m.notna()
    profile = profile.loc[valid].reset_index(drop=True)
    dist_km = dist_km.loc[valid].reset_index(drop=True)
    elev_m = elev_m.loc[valid].reset_index(drop=True)
    if len(profile) < 2:
        ax.axis("off")
        return

    ymin = float(elev_m.min())
    ymax = float(elev_m.max())
    pad = max(8.0, (ymax - ymin) * 0.08)
    ax.fill_between(dist_km, elev_m, ymin - pad, color="#ECEFF1", alpha=0.95, zorder=0)
    ax.plot(dist_km, elev_m, color="#78909C", linewidth=1.0, alpha=0.8, zorder=1)

    for i in range(len(profile) - 1):
        band = pick_band(profile.loc[i, "risk_band"], profile.loc[i + 1, "risk_band"])
        ax.plot(
            [dist_km.iloc[i], dist_km.iloc[i + 1]],
            [elev_m.iloc[i], elev_m.iloc[i + 1]],
            color=RISK_COLOR[band],
            linewidth=2.4,
            solid_capstyle="round",
            zorder=2,
        )

    ax.scatter(dist_km.iloc[0], elev_m.iloc[0], s=34, c="#2E7D32", edgecolors="white", linewidths=0.7, zorder=4)
    ax.scatter(dist_km.iloc[-1], elev_m.iloc[-1], s=34, c="#C62828", edgecolors="white", linewidths=0.7, zorder=4)
    ax.set_xlim(float(dist_km.min()), float(dist_km.max()))
    ax.set_ylim(ymin - pad, ymax + pad)
    ax.set_xlabel("距離 (km)")
    ax.set_ylabel("高程 (m)")
    ax.set_title("高程剖面圖", fontsize=12, pad=8)
    ax.grid(True, color="#D7DEE2", linewidth=0.7, alpha=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def radar_mean_score(df: pd.DataFrame, candidates: list[str]) -> float:
    for col in candidates:
        if col in df.columns:
            return float(numeric_col(df, col, 0.0).clip(0, 1).mean() * 100.0)
    return 0.0


def write_fallback_radar(risk_df: pd.DataFrame, case_name: str, out_radar_png: Path) -> None:
    axes = [
        ("體力難度", ["effort_score", "route_effort_risk_score"]),
        ("技術難度", ["technical_risk_score"]),
        ("基礎危害", ["exposure_score"]),
        ("地形壓力", ["terrain_score", "terrain_window_risk_score"]),
        ("濕滑敏感", ["surface_slip_risk_score"]),
        ("水文敏感", ["hydrology_risk_score", "hydro_terrain_amplifier_score"]),
    ]
    values = [radar_mean_score(risk_df, cols) for _, cols in axes]
    labels = [f"{label}\n{value:.0f}" for (label, _), value in zip(axes, values)]

    angles = np.linspace(0, 2 * np.pi, len(values), endpoint=False).tolist()
    plot_values = values + values[:1]
    plot_angles = angles + angles[:1]

    fig = plt.figure(figsize=(6.2, 6.2), dpi=DPI)
    ax = fig.add_subplot(111, polar=True)
    ax.plot(plot_angles, plot_values, color="#1565C0", linewidth=2.2)
    ax.fill(plot_angles, plot_values, color="#64B5F6", alpha=0.28)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=8)
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=10)
    ax.grid(color="#B0BEC5", linewidth=0.8)
    ax.set_title(f"{case_name}\n六軸風險雷達圖", fontsize=13, pad=24)
    fig.tight_layout()
    fig.savefig(out_radar_png, facecolor="white")
    plt.close(fig)


def write_combined_image(out_png: Path, out_radar_png: Path, out_combined_png: Path) -> bool:
    if not out_png.exists() or not out_radar_png.exists():
        return False
    map_img = Image.open(out_png).convert("RGB")
    radar_img = Image.open(out_radar_png).convert("RGB")
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
    canvas.save(out_combined_png, quality=95)
    return True


def plot_map(
    case_id: str,
    case_name: str,
    risk_df: pd.DataFrame,
    points: gpd.GeoDataFrame,
    osm_raw_dir: Path,
    contour_fp: Path,
    out_png: Path,
    out_seg_geojson: Path,
) -> gpd.GeoDataFrame:
    risk_df = risk_df.copy()
    points = points.copy()
    if "dist_m" not in risk_df.columns or "dist_m" not in points.columns:
        raise KeyError("risk CSV and profile/risk GeoJSON must both contain dist_m")

    risk_df["dist_key"] = risk_df["dist_m"].round(3)
    points["dist_key"] = points["dist_m"].round(3)
    keep = [
        "dist_key",
        "risk_band",
        "risk_score_smooth",
        "effort_score",
        "exposure_score",
        "terrain_score",
    ]
    merged = points.merge(risk_df[keep], on="dist_key", how="left")
    merged["risk_band"] = merged["risk_band"].map(norm_band)
    merged["risk_score_smooth"] = numeric_col(merged, "risk_score_smooth", 0.0)
    for col in ["effort_score", "exposure_score", "terrain_score"]:
        merged[col] = numeric_col(merged, col, 0.0)

    merged = gpd.GeoDataFrame(merged, geometry="geometry", crs=points.crs).sort_values("dist_m")
    metric_crs = merged.estimate_utm_crs()
    points_m = merged.to_crs(metric_crs)
    route_line = LineString([geom.coords[0] for geom in points_m.geometry if geom is not None and not geom.is_empty])
    route_buffer = route_line.buffer(ROUTE_BUFFER_M)
    seg_gdf = build_segments(points_m)
    seg_gdf.to_file(out_seg_geojson, driver="GeoJSON")

    contour_m = gpd.GeoDataFrame(geometry=[], crs=metric_crs)
    if contour_fp.exists():
        contour_m = read_layer(contour_fp, metric_crs)
        if not contour_m.empty:
            contour_m = contour_m[contour_m.intersects(route_buffer)].copy()

    fig = plt.figure(figsize=(15, 12), dpi=DPI, constrained_layout=True)
    gs = fig.add_gridspec(
        2,
        2,
        width_ratios=[4.8, 1.4],
        height_ratios=[4.6, 1.25],
        hspace=0.18,
        wspace=0.05,
    )
    ax = fig.add_subplot(gs[0, 0])
    ax_leg = fig.add_subplot(gs[0, 1])
    ax_profile = fig.add_subplot(gs[1, :])

    if not contour_m.empty:
        contour_m.plot(ax=ax, color="#BDBDBD", linewidth=0.45, alpha=0.8, zorder=0)
        elev_col = next((c for c in ["zv2", "elev", "elevation", "height"] if c in contour_m.columns), None)
        if elev_col:
            elev = pd.to_numeric(contour_m[elev_col], errors="coerce")
            major = contour_m[elev.fillna(-999) % 50 == 0]
            if not major.empty:
                major.plot(ax=ax, color="#757575", linewidth=0.75, alpha=0.9, zorder=0)

    for _, (filename, face, edge, _label) in AREA_LAYERS.items():
        layer = read_layer(osm_raw_dir / filename, metric_crs)
        if not layer.empty:
            layer = layer[layer.intersects(route_buffer)]
            if not layer.empty:
                layer.plot(ax=ax, facecolor=face, edgecolor=edge, alpha=0.35, linewidth=0.8, zorder=1)

    for _, (filename, linestyle, color, _label) in LINE_LAYERS.items():
        layer = read_layer(osm_raw_dir / filename, metric_crs)
        if not layer.empty:
            layer = layer[layer.intersects(route_buffer)]
            if not layer.empty:
                layer.plot(ax=ax, color=color, linestyle=linestyle, linewidth=1.2, alpha=0.75, zorder=2)

    seg_gdf.plot(ax=ax, color="#D0D0D0", linewidth=1.0, zorder=3)
    for band in ["low", "moderate", "high", "very_high", "unknown"]:
        sub = seg_gdf[seg_gdf["risk_band"] == band]
        if not sub.empty:
            sub.plot(ax=ax, color=RISK_COLOR[band], linewidth=4.2, alpha=0.95, zorder=5)

    for _, (filename, marker, color, _label) in POINT_LAYERS.items():
        layer = read_layer(osm_raw_dir / filename, metric_crs)
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
    ax.set_title(f"{case_name}\nOffline risk map + OSM context", fontsize=16)
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
    plot_elevation_profile(ax_profile, merged)

    fig.savefig(out_png, dpi=DPI, facecolor="white")
    plt.close(fig)

    print("contour features within buffer:", len(contour_m))
    return seg_gdf


def main() -> None:
    args = parse_args()
    case_id = args.case_id
    case_name = args.case_name or case_id
    risk_csv = resolve_path(args.risk_csv) if args.risk_csv else default_risk_csv(case_id)
    risk_geojson = resolve_path(args.risk_geojson) if args.risk_geojson else default_risk_geojson(case_id)
    profile_geojson = resolve_path(args.profile_geojson) if args.profile_geojson else default_profile_geojson(case_id)
    osm_raw_dir = resolve_path(args.osm_raw_dir) if args.osm_raw_dir else default_osm_raw_dir(case_id)
    contour_fp = resolve_path(args.contour_fp) if args.contour_fp else default_contour_fp()
    out_dir = resolve_path(args.out_dir) if args.out_dir else default_out_dir(case_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    out_png = out_dir / f"{case_id}_route_risk_offline_map.png"
    out_seg_geojson = out_dir / f"{case_id}_route_risk_offline_segments.geojson"
    out_radar_png = out_dir / f"{case_id}_route_challenge_radar.png"
    out_combined_png = out_dir / f"{case_id}_route_risk_offline_map_with_radar.png"
    radar_source = PROJECT_ROOT / "outputs" / "ib2e_route_challenge_index" / case_id / f"{case_id}_route_challenge_radar.png"

    if not risk_csv.exists():
        raise FileNotFoundError(f"Missing risk CSV: {risk_csv}")
    if not osm_raw_dir.exists():
        raise FileNotFoundError(f"Missing OSM raw dir: {osm_raw_dir}")

    risk_df = ensure_risk_aliases(pd.read_csv(risk_csv, low_memory=False, encoding="utf-8-sig"))
    points = load_points(profile_geojson, risk_geojson)
    seg_gdf = plot_map(
        case_id,
        case_name,
        risk_df,
        points,
        osm_raw_dir,
        contour_fp,
        out_png,
        out_seg_geojson,
    )

    if radar_source.exists():
        shutil.copy2(radar_source, out_radar_png)
    else:
        write_fallback_radar(risk_df, case_name, out_radar_png)
    combined = write_combined_image(out_png, out_radar_png, out_combined_png)

    print("case:", case_id)
    print("case_name:", case_name)
    print("risk CSV:", risk_csv)
    print("risk GeoJSON:", risk_geojson)
    print("profile GeoJSON:", profile_geojson)
    print("OSM raw dir:", osm_raw_dir)
    print("contour fp:", contour_fp)
    print("PNG:", out_png)
    print("segment GeoJSON:", out_seg_geojson)
    print("radar PNG:", out_radar_png)
    if combined:
        print("combined map + radar PNG:", out_combined_png)
    print("\n=== segment risk_band ===")
    print(seg_gdf["risk_band"].value_counts(dropna=False))


if __name__ == "__main__":
    main()
