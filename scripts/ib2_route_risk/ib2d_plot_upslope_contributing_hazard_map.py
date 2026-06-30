# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap, Normalize
from PIL import Image, ImageOps


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DPI = 150
MAP_BUFFER_M = 1000.0

mpl.rcParams["font.sans-serif"] = [
    "Microsoft JhengHei",
    "Microsoft YaHei",
    "Noto Sans CJK TC",
    "Arial Unicode MS",
    "DejaVu Sans",
]
mpl.rcParams["axes.unicode_minus"] = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot upslope contributing-area hazard proxy map and radar."
    )
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--case-name", default=None)
    parser.add_argument("--hazard-csv", default=None)
    parser.add_argument("--hazard-geojson", default=None)
    parser.add_argument("--contour-fp", default=None)
    parser.add_argument("--collapse-mask-fp", default=None)
    parser.add_argument("--watercourse-fp", default=None)
    parser.add_argument("--out-dir", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def default_hazard_dir(case_id: str) -> Path:
    return PROJECT_ROOT / "outputs" / "ib1g3_upslope_contributing_area_hazard_proxy" / case_id


def default_hazard_csv(case_id: str) -> Path:
    return default_hazard_dir(case_id) / f"{case_id}_upslope_contributing_area_hazard_proxy.csv"


def default_hazard_geojson(case_id: str) -> Path:
    return default_hazard_dir(case_id) / f"{case_id}_upslope_contributing_area_hazard_proxy.geojson"


def default_out_dir(case_id: str) -> Path:
    return PROJECT_ROOT / "outputs" / "ib2d_upslope_contributing_hazard_map" / case_id


def read_optional_layer(path: Path | None, crs) -> gpd.GeoDataFrame:
    if path is None or not path.exists():
        return gpd.GeoDataFrame(geometry=[], crs=crs)
    try:
        gdf = gpd.read_file(path)
    except Exception as exc:
        print(f"WARNING: could not read {path}: {exc}")
        return gpd.GeoDataFrame(geometry=[], crs=crs)
    if gdf.empty:
        return gpd.GeoDataFrame(geometry=[], crs=crs)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:3826")
    return gdf.to_crs(crs)


def estimate_metric_crs(gdf: gpd.GeoDataFrame):
    try:
        return gdf.estimate_utm_crs()
    except Exception:
        return "EPSG:3826"


def subset_to_buffer(gdf: gpd.GeoDataFrame, area) -> gpd.GeoDataFrame:
    if gdf.empty:
        return gdf
    try:
        return gdf[gdf.intersects(area)].copy()
    except Exception:
        return gdf.iloc[0:0].copy()


def line_segments_for_collection(gdf: gpd.GeoDataFrame) -> list[np.ndarray]:
    segments: list[np.ndarray] = []
    for geom in gdf.geometry:
        if geom is None or geom.is_empty:
            continue
        geoms = geom.geoms if geom.geom_type == "MultiLineString" else [geom]
        for line in geoms:
            if line.geom_type != "LineString":
                continue
            coords = np.asarray(line.coords)
            if len(coords) >= 2:
                segments.append(coords[:, :2])
    return segments


def score_series(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df.get(col, 0.0), errors="coerce").fillna(0.0).clip(0, 1)


def build_hotspot_table(df: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    data = df.copy()
    score_col = "upslope_contributing_hazard_score"
    data[score_col] = pd.to_numeric(data[score_col], errors="coerce").fillna(0.0)
    threshold = max(0.78, float(data[score_col].quantile(0.90)))
    hot = data[data[score_col] >= threshold].copy()
    if hot.empty:
        hot = data.nlargest(10, score_col).copy()
        threshold = float(hot[score_col].min())

    groups = []
    current = []
    last_end = None
    for _, row in hot.sort_values("dist_start").iterrows():
        start = float(row["dist_start"])
        end = float(row["dist_end"])
        if last_end is None or start <= last_end + 25.0:
            current.append(row)
        else:
            groups.append(pd.DataFrame(current))
            current = [row]
        last_end = end
    if current:
        groups.append(pd.DataFrame(current))

    rows = []
    for idx, group in enumerate(groups, start=1):
        rows.append(
            {
                "rank": idx,
                "dist_start_m": float(group["dist_start"].min()),
                "dist_end_m": float(group["dist_end"].max()),
                "length_m": float(group["dist_end"].max() - group["dist_start"].min()),
                "mean_score": float(group[score_col].mean()),
                "max_score": float(group[score_col].max()),
                "mean_max_source_relief_m": float(group["max_source_relief_m"].mean()),
                "max_source_relief_m": float(group["max_source_relief_m"].max()),
                "mean_fall_gradient": float(group["max_source_fall_gradient"].mean()),
                "max_fall_gradient": float(group["max_source_fall_gradient"].max()),
                "mean_source_count": float(group["contributing_source_count"].mean()),
                "mean_sector_count": float(group["contributing_sector_count"].mean()),
            }
        )
    table = pd.DataFrame(rows)
    if not table.empty:
        table = table.sort_values(["mean_score", "max_score", "length_m"], ascending=False).reset_index(drop=True)
        table["rank"] = np.arange(1, len(table) + 1)
    return table, threshold


def write_hotspot_markdown(case_name: str, table: pd.DataFrame, threshold: float, out_fp: Path) -> None:
    lines = [
        f"# {case_name} upslope contributing hazard hotspots",
        "",
        (
            "This is a relative hotspot list from the broad upslope contributing-area proxy. "
            "It uses higher NLSC contour sources up to 1000 m from the trail and does not model "
            "true rockfall physics, DEM aspect, or debris-flow runout."
        ),
        "",
        f"Hotspot threshold: score >= {threshold:.3f}",
        "",
    ]
    if table.empty:
        lines.append("No hotspot sections found.")
    else:
        lines.append("| rank | distance km | length m | mean score | max score | max relief m | max fall gradient |")
        lines.append("|---:|---:|---:|---:|---:|---:|---:|")
        for _, row in table.iterrows():
            lines.append(
                "| {rank:.0f} | {start:.2f}-{end:.2f} | {length:.0f} | {mean:.3f} | {maxs:.3f} | {relief:.0f} | {grad:.2f} |".format(
                    rank=row["rank"],
                    start=row["dist_start_m"] / 1000.0,
                    end=row["dist_end_m"] / 1000.0,
                    length=row["length_m"],
                    mean=row["mean_score"],
                    maxs=row["max_score"],
                    relief=row["max_source_relief_m"],
                    grad=row["max_fall_gradient"],
                )
            )
    out_fp.write_text("\n".join(lines) + "\n", encoding="utf-8")


def plot_map(
    case_name: str,
    hazard_gdf: gpd.GeoDataFrame,
    hazard_df: pd.DataFrame,
    contours: gpd.GeoDataFrame,
    collapse: gpd.GeoDataFrame,
    watercourse: gpd.GeoDataFrame,
    hotspots: pd.DataFrame,
    out_fp: Path,
) -> None:
    fig = plt.figure(figsize=(14, 10), dpi=DPI)
    gs = fig.add_gridspec(2, 1, height_ratios=[4.2, 1.25], hspace=0.16)
    ax = fig.add_subplot(gs[0])
    profile_ax = fig.add_subplot(gs[1])

    cmap = LinearSegmentedColormap.from_list("upslope_hazard", ["#F5D76E", "#F28E2B", "#C9252D"])
    norm = Normalize(vmin=0.70, vmax=0.85)

    if not contours.empty:
        contours.plot(ax=ax, color="#B7B7B7", linewidth=0.35, alpha=0.50, zorder=1)
    if not collapse.empty:
        collapse.plot(ax=ax, facecolor="#8D5A2B", edgecolor="#5D3218", alpha=0.35, linewidth=0.5, zorder=2)
    if not watercourse.empty:
        watercourse.plot(ax=ax, color="#2D8FCB", linewidth=1.4, alpha=0.85, zorder=3)

    segments = line_segments_for_collection(hazard_gdf)
    values = pd.to_numeric(hazard_gdf["upslope_contributing_hazard_score"], errors="coerce").fillna(0.0).to_numpy()
    collection = LineCollection(segments, cmap=cmap, norm=norm, linewidths=5.5, zorder=5, capstyle="round")
    collection.set_array(values[: len(segments)])
    ax.add_collection(collection)

    first = hazard_gdf.geometry.iloc[0]
    last = hazard_gdf.geometry.iloc[-1]
    start_xy = np.asarray(first.coords[0])[:2]
    end_xy = np.asarray(last.coords[-1])[:2]
    ax.scatter([start_xy[0]], [start_xy[1]], marker="^", s=90, color="#15603A", edgecolor="white", zorder=7, label="start")
    ax.scatter([end_xy[0]], [end_xy[1]], marker="s", s=75, color="#4A3F35", edgecolor="white", zorder=7, label="end")

    for _, row in hotspots.head(5).iterrows():
        segs = hazard_gdf[
            (hazard_gdf["dist_start"] >= row["dist_start_m"])
            & (hazard_gdf["dist_end"] <= row["dist_end_m"])
        ]
        if not segs.empty:
            segs.plot(ax=ax, color="#6E0015", linewidth=8.5, alpha=0.55, zorder=6)

    minx, miny, maxx, maxy = hazard_gdf.total_bounds
    padx = max((maxx - minx) * 0.08, 80)
    pady = max((maxy - miny) * 0.08, 80)
    ax.set_xlim(minx - padx, maxx + padx)
    ax.set_ylim(miny - pady, maxy + pady)
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(f"{case_name} - upslope rockfall/debris source proxy", fontsize=16, weight="bold")
    ax.set_xlabel("TWD97 / metric coordinate")
    ax.set_ylabel("TWD97 / metric coordinate")
    ax.grid(color="#EAEAEA", linewidth=0.6)
    cbar = fig.colorbar(collection, ax=ax, fraction=0.032, pad=0.012)
    cbar.set_label("Hazard proxy score")
    ax.legend(loc="upper right", frameon=True)

    d_km = pd.to_numeric(hazard_df["dist_mid"], errors="coerce") / 1000.0
    score = pd.to_numeric(hazard_df["upslope_contributing_hazard_score"], errors="coerce")
    profile_ax.plot(d_km, score, color="#8B1E2D", linewidth=1.7)
    profile_ax.fill_between(d_km, 0.70, score, where=score >= 0.70, color="#F28E2B", alpha=0.22)
    for _, row in hotspots.head(8).iterrows():
        profile_ax.axvspan(row["dist_start_m"] / 1000.0, row["dist_end_m"] / 1000.0, color="#C9252D", alpha=0.20)
    profile_ax.set_ylim(0.68, max(0.86, float(score.max()) + 0.01))
    profile_ax.set_xlim(0, float(pd.to_numeric(hazard_df["dist_end"], errors="coerce").max()) / 1000.0)
    profile_ax.set_xlabel("Distance from trailhead (km)")
    profile_ax.set_ylabel("Hazard score")
    profile_ax.grid(color="#E6E6E6", linewidth=0.6)

    fig.savefig(out_fp, bbox_inches="tight")
    plt.close(fig)


def plot_radar(case_name: str, df: pd.DataFrame, out_fp: Path) -> None:
    metrics = [
        ("Higher relief", np.clip(pd.to_numeric(df["max_source_relief_m"], errors="coerce") / 500.0, 0, 1).mean()),
        ("Fall gradient", np.clip(pd.to_numeric(df["max_source_fall_gradient"], errors="coerce") / 1.0, 0, 1).mean()),
        ("Source density", score_series(df, "source_presence_score").mean()),
        ("Direction spread", score_series(df, "directional_concentration_score").mean()),
        ("Collapse mask", score_series(df, "collapse_mask_score").mean()),
        ("Water channel", score_series(df, "watercourse_channel_score").mean()),
    ]
    labels = [m[0] for m in metrics]
    values = [float(m[1]) for m in metrics]
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    values_closed = values + values[:1]
    angles_closed = angles + angles[:1]

    fig = plt.figure(figsize=(7.8, 7.8), dpi=DPI)
    ax = fig.add_subplot(111, polar=True)
    ax.plot(angles_closed, values_closed, color="#9F1D35", linewidth=2.2)
    ax.fill(angles_closed, values_closed, color="#D94854", alpha=0.25)
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["25", "50", "75", "100"], fontsize=9)
    ax.set_ylim(0, 1)
    ax.set_title(f"{case_name}\nIB2D-style radar: upslope hazard factors", fontsize=14, weight="bold", pad=24)
    ax.grid(color="#D8D8D8")
    fig.savefig(out_fp, bbox_inches="tight")
    plt.close(fig)


def combine_images(map_fp: Path, radar_fp: Path, out_fp: Path) -> None:
    map_img = Image.open(map_fp).convert("RGB")
    radar_img = Image.open(radar_fp).convert("RGB")
    radar_img = ImageOps.contain(radar_img, (int(map_img.width * 0.34), int(map_img.height * 0.58)))

    pad = 34
    canvas = Image.new("RGB", (map_img.width + radar_img.width + pad * 3, map_img.height + pad * 2), "white")
    canvas.paste(map_img, (pad, pad))
    x = map_img.width + pad * 2
    y = pad + (map_img.height - radar_img.height) // 2
    canvas.paste(radar_img, (x, y))
    canvas.save(out_fp)


def main() -> None:
    args = parse_args()
    case_id = args.case_id
    case_name = args.case_name or case_id
    hazard_csv = resolve_path(args.hazard_csv) if args.hazard_csv else default_hazard_csv(case_id)
    hazard_geojson = resolve_path(args.hazard_geojson) if args.hazard_geojson else default_hazard_geojson(case_id)
    out_dir = resolve_path(args.out_dir) if args.out_dir else default_out_dir(case_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(hazard_csv)
    gdf = gpd.read_file(hazard_geojson)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    metric_crs = estimate_metric_crs(gdf)
    gdf_m = gdf.to_crs(metric_crs)
    route_area = gdf_m.geometry.union_all().buffer(MAP_BUFFER_M)

    contour_fp = resolve_path(args.contour_fp) if args.contour_fp else resolve_path(df["contour_fp"].dropna().iloc[0])
    collapse_fp = resolve_path(args.collapse_mask_fp) if args.collapse_mask_fp else resolve_path(df["collapse_mask_fp"].dropna().iloc[0])
    watercourse_fp = resolve_path(args.watercourse_fp) if args.watercourse_fp else resolve_path(df["watercourse_fp"].dropna().iloc[0])

    contours = subset_to_buffer(read_optional_layer(contour_fp, metric_crs), route_area)
    collapse = subset_to_buffer(read_optional_layer(collapse_fp, metric_crs), route_area)
    watercourse = subset_to_buffer(read_optional_layer(watercourse_fp, metric_crs), route_area)

    hotspots, threshold = build_hotspot_table(df)
    hotspot_csv = out_dir / f"{case_id}_upslope_contributing_hazard_hotspots.csv"
    hotspot_md = out_dir / f"{case_id}_upslope_contributing_hazard_hotspots.md"
    hotspots.to_csv(hotspot_csv, index=False, encoding="utf-8-sig")
    write_hotspot_markdown(case_name, hotspots, threshold, hotspot_md)

    map_fp = out_dir / f"{case_id}_upslope_contributing_hazard_map.png"
    radar_fp = out_dir / f"{case_id}_upslope_contributing_hazard_radar.png"
    combined_fp = out_dir / f"{case_id}_upslope_contributing_hazard_map_with_radar.png"
    plot_map(case_name, gdf_m, df, contours, collapse, watercourse, hotspots, map_fp)
    plot_radar(case_name, df, radar_fp)
    combine_images(map_fp, radar_fp, combined_fp)

    summary = {
        "case_id": case_id,
        "case_name": case_name,
        "rows": int(len(df)),
        "score_min": float(pd.to_numeric(df["upslope_contributing_hazard_score"], errors="coerce").min()),
        "score_mean": float(pd.to_numeric(df["upslope_contributing_hazard_score"], errors="coerce").mean()),
        "score_max": float(pd.to_numeric(df["upslope_contributing_hazard_score"], errors="coerce").max()),
        "hotspot_threshold": threshold,
        "hotspot_count": int(len(hotspots)),
        "map_png": str(map_fp),
        "radar_png": str(radar_fp),
        "combined_png": str(combined_fp),
        "hotspot_csv": str(hotspot_csv),
        "hotspot_md": str(hotspot_md),
    }
    pd.DataFrame([summary]).to_csv(
        out_dir / f"{case_id}_upslope_contributing_hazard_map_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print("DONE")
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
