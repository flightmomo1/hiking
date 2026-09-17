#!/usr/bin/env python3
"""Render a self-contained offline HTML QA report for Route Axis elevation fusion.

This renderer is intentionally read-only: it visualizes production artifacts and
source geometry without recomputing or modifying the fused elevation profile.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html as html_lib
import io
import json
import math
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Rectangle
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString
from shapely.ops import linemerge


PROFILE_REQUIRED = {
    "dist_m",
    "ele_gpx_m",
    "ele_gpx_shape_m",
    "nlsc_vertical_offset_m",
    "ele_fused_m",
    "shape_smoothing_method",
    "shape_smoothing_scale_m",
    "absolute_vertical_reference",
    "calibration_model",
    "calibration_lambda",
    "elevation_fusion_method",
}

ANCHOR_REQUIRED = {
    "route_dist_m",
    "gpx_dist_m",
    "gpx_to_route_axis_m",
    "contour_z_m",
    "gpx_ele_interp_m",
    "nlsc_minus_gpx_m",
}


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Render an offline HTML QA report for Route Axis elevation fusion."
    )
    ap.add_argument("--case-id", required=True)
    ap.add_argument("--route-axis", required=True)
    ap.add_argument("--gpx", required=True)
    ap.add_argument("--contour", required=True)
    ap.add_argument("--anchors", required=True)
    ap.add_argument("--fused-profile", required=True)
    ap.add_argument("--fusion-grid", required=True)
    ap.add_argument("--analysis-crs", required=True)
    ap.add_argument("--contour-buffer-m", type=float, default=100.0)
    ap.add_argument("--title")
    ap.add_argument("--output-html", required=True)
    return ap.parse_args()


def require_file(value: str, label: str) -> Path:
    path = Path(value)
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")
    return path


def require_columns(df: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"{label} missing columns: {missing}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def read_gpx(path: Path) -> tuple[LineString, dict[str, object]]:
    root = ET.parse(path).getroot()
    points: list[tuple[float, float]] = []
    elevations = 0
    timestamps = 0
    extensions = 0
    for elem in root.iter():
        name = local_name(elem.tag)
        if name == "trkpt":
            points.append((float(elem.attrib["lon"]), float(elem.attrib["lat"])))
            children = {local_name(child.tag) for child in elem}
            elevations += int("ele" in children)
            timestamps += int("time" in children)
            extensions += int("extensions" in children)
    if len(points) < 2:
        raise ValueError(f"GPX needs at least two trkpt elements: {path}")
    return LineString(points), {
        "creator": root.attrib.get("creator", "UNKNOWN"),
        "gpx_version": root.attrib.get("version", "UNKNOWN"),
        "track_points": len(points),
        "elevation_points": elevations,
        "timestamp_points": timestamps,
        "point_extensions": extensions,
    }


def as_single_line(geometries: gpd.GeoSeries) -> LineString:
    union = geometries.union_all()
    merged = linemerge(union) if union.geom_type != "LineString" else union
    if merged.geom_type != "LineString":
        raise ValueError(
            "Route Axis must resolve to one ordered LineString; got " + merged.geom_type
        )
    if merged.is_empty or not merged.is_valid:
        raise ValueError("Route Axis geometry is empty or invalid")
    return merged


def fig_uri(fig: plt.Figure) -> str:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=155, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    payload = base64.b64encode(buffer.getvalue()).decode("ascii")
    return "data:image/png;base64," + payload


def fmt(value: object, digits: int = 2) -> str:
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "UNKNOWN"
    if isinstance(value, (float, np.floating)):
        return f"{float(value):,.{digits}f}"
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    return str(value)


def scalar_text(df: pd.DataFrame, column: str, fallback: str = "UNKNOWN") -> str:
    values = df[column].dropna().astype(str).unique().tolist() if column in df else []
    return values[0] if len(values) == 1 else fallback


def scalar_number(df: pd.DataFrame, column: str) -> float:
    values = pd.to_numeric(df[column], errors="coerce").dropna().unique()
    return float(values[0]) if len(values) == 1 else float("nan")


def elevation_travel(values: np.ndarray) -> tuple[float, float]:
    delta = np.diff(values)
    return float(delta[delta > 0].sum()), float(-delta[delta < 0].sum())


def source_rows(paths: list[tuple[str, Path]]) -> list[dict[str, str]]:
    rows = []
    seen: set[Path] = set()
    for role, path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        rows.append(
            {
                "role": role,
                "path": str(path),
                "bytes": str(path.stat().st_size),
                "sha256": sha256(path),
            }
        )
    return rows


def html_table(headers: list[str], rows: list[list[object]]) -> str:
    head = "".join(f"<th>{html_lib.escape(h)}</th>" for h in headers)
    body = []
    for row in rows:
        cells = "".join(
            f"<td>{html_lib.escape(str(value))}</td>" for value in row
        )
        body.append(f"<tr>{cells}</tr>")
    return f"<div class='table-wrap'><table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"


def make_profile_figure(profile: pd.DataFrame, anchors: pd.DataFrame) -> str:
    x = profile["dist_m"].to_numpy(float)
    fig, ax = plt.subplots(figsize=(13.5, 5.3))
    ax.plot(x, profile["ele_gpx_m"], color="#a0a7b1", lw=0.8, alpha=0.75, label="GPX raw <ele>")
    ax.plot(x, profile["ele_gpx_shape_m"], color="#2463a8", lw=1.4, label="GPX smoothed shape")
    ax.plot(x, profile["ele_fused_m"], color="#d35400", lw=2.0, label="Fused elevation")
    ax.scatter(
        anchors["route_dist_m"], anchors["contour_z_m"],
        s=26, color="#16826c", edgecolor="white", linewidth=0.5,
        zorder=5, label="NLSC contour anchors",
    )
    ax.set(xlabel="Route Axis chainage (m)", ylabel="Elevation (m)")
    ax.grid(True, alpha=0.2)
    ax.legend(ncol=4, loc="upper left", frameon=False)
    ax.margins(x=0)
    fig.tight_layout()
    return fig_uri(fig)


def make_offset_figure(profile: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(13.5, 3.6))
    ax.plot(
        profile["dist_m"], profile["nlsc_vertical_offset_m"],
        color="#7c3aed", lw=2.0,
    )
    ax.axhline(0, color="#202631", lw=0.8, alpha=0.5)
    ax.set(xlabel="Route Axis chainage (m)", ylabel="NLSC vertical offset (m)")
    ax.grid(True, alpha=0.2)
    ax.margins(x=0)
    fig.tight_layout()
    return fig_uri(fig)


def make_residual_figure(profile: pd.DataFrame, anchors: pd.DataFrame) -> tuple[str, np.ndarray]:
    fused = np.interp(
        anchors["route_dist_m"].to_numpy(float),
        profile["dist_m"].to_numpy(float),
        profile["ele_fused_m"].to_numpy(float),
    )
    residual = fused - anchors["contour_z_m"].to_numpy(float)
    fig, ax = plt.subplots(figsize=(13.5, 4.0))
    ax.axhspan(-10, 10, color="#facc15", alpha=0.13, label="±10 m")
    ax.axhspan(-5, 5, color="#22c55e", alpha=0.14, label="±5 m")
    colors = np.where(np.abs(residual) <= 5, "#16826c", np.where(np.abs(residual) <= 10, "#d97706", "#c0392b"))
    ax.vlines(anchors["route_dist_m"], 0, residual, color=colors, alpha=0.6, lw=1)
    ax.scatter(anchors["route_dist_m"], residual, c=colors, s=25, zorder=3)
    ax.axhline(0, color="#202631", lw=0.9)
    ax.set(xlabel="Route Axis chainage (m)", ylabel="Fused minus contour (m)")
    ax.grid(True, axis="x", alpha=0.18)
    ax.margins(x=0)
    ax.legend(loc="upper left", frameon=False, ncol=2)
    fig.tight_layout()
    return fig_uri(fig), residual


def make_grid_figure(
    grid: pd.DataFrame,
    selected_window: float,
    selected_lambda: float,
) -> str:
    window_col = next((c for c in ["window_m", "shape_smoothing_scale_m", "selected_window_m"] if c in grid), None)
    lambda_col = next((c for c in ["lambda", "calibration_lambda", "selected_lambda"] if c in grid), None)
    metric_col = next((c for c in ["anchor_mae_m", "mae_m", "anchor_MAE_m"] if c in grid), None)
    if not all([window_col, lambda_col, metric_col]):
        fig, ax = plt.subplots(figsize=(11, 2.2))
        ax.axis("off")
        ax.text(0.5, 0.5, "Fusion grid columns are available in the source table but no recognized MAE matrix was found.", ha="center", va="center")
        return fig_uri(fig)
    pivot = grid.pivot_table(index=window_col, columns=lambda_col, values=metric_col, aggfunc="first").sort_index().sort_index(axis=1)
    values = pivot.to_numpy(float)
    fig, ax = plt.subplots(figsize=(10.5, 5.5))
    image = ax.imshow(values, aspect="auto", cmap="viridis_r")
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            if np.isfinite(values[i, j]):
                ax.text(j, i, f"{values[i, j]:.2f}", ha="center", va="center", fontsize=8, color="white" if values[i, j] > np.nanmedian(values) else "black")
    ax.set_xticks(range(len(pivot.columns)), [fmt(v, 2) for v in pivot.columns])
    ax.set_yticks(range(len(pivot.index)), [fmt(v, 0) for v in pivot.index])
    if math.isfinite(selected_window) and math.isfinite(selected_lambda):
        row = np.flatnonzero(np.isclose(pivot.index.to_numpy(float), selected_window))
        col = np.flatnonzero(np.isclose(pivot.columns.to_numpy(float), selected_lambda))
        if len(row) == 1 and len(col) == 1:
            ax.add_patch(
                Rectangle(
                    (col[0] - 0.5, row[0] - 0.5),
                    1,
                    1,
                    fill=False,
                    edgecolor="#ef4444",
                    linewidth=3,
                    label="Selected production setting",
                )
            )
            ax.legend(loc="upper left", bbox_to_anchor=(0, 1.12), frameon=False)
    ax.set(xlabel="Calibration lambda", ylabel="Smoothing window (m)")
    fig.colorbar(image, ax=ax, label="Anchor MAE (m)")
    fig.tight_layout()
    return fig_uri(fig)


def make_geometry_figure(
    route_m: LineString,
    gpx_m: LineString,
    contours_m: gpd.GeoDataFrame,
    anchors: pd.DataFrame,
    residual: np.ndarray,
    analysis_crs: str,
) -> tuple[str, int]:
    distances = np.clip(anchors["route_dist_m"].to_numpy(float), 0, route_m.length)
    anchor_points = [route_m.interpolate(value) for value in distances]
    fig, ax = plt.subplots(figsize=(11.5, 7.5))
    if not contours_m.empty:
        contours_m.plot(ax=ax, color="#a98252", linewidth=0.45, alpha=0.35)
    gx, gy = gpx_m.xy
    rx, ry = route_m.xy
    ax.plot(gx, gy, color="#2f80ed", lw=1.1, alpha=0.8, linestyle="--", label="GPX geometry")
    ax.plot(rx, ry, color="#161b22", lw=2.2, label="Route Axis")
    px = [point.x for point in anchor_points]
    py = [point.y for point in anchor_points]
    limit = max(10.0, float(np.nanmax(np.abs(residual))))
    scatter = ax.scatter(px, py, c=residual, cmap="coolwarm", norm=TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit), s=30, edgecolor="white", linewidth=0.4, zorder=5, label="Anchor projected to Route Axis")
    ax.scatter([rx[0]], [ry[0]], marker="o", s=60, color="#16a34a", edgecolor="white", zorder=6, label="Start")
    ax.scatter([rx[-1]], [ry[-1]], marker="s", s=60, color="#dc2626", edgecolor="white", zorder=6, label="End")
    fig.colorbar(scatter, ax=ax, label="Fused minus contour (m)", shrink=0.75)
    ax.set_aspect("equal", adjustable="datalim")
    ax.set(xlabel=f"Easting ({analysis_crs})", ylabel=f"Northing ({analysis_crs})")
    ax.grid(True, alpha=0.12)
    ax.legend(loc="best", frameon=True, fontsize=8)
    fig.tight_layout()
    return fig_uri(fig), int(len(contours_m))


def main() -> None:
    args = parse_args()
    if args.contour_buffer_m < 0:
        raise ValueError("--contour-buffer-m must be >= 0")

    route_path = require_file(args.route_axis, "Route Axis")
    gpx_path = require_file(args.gpx, "GPX")
    contour_path = require_file(args.contour, "NLSC contour")
    anchors_path = require_file(args.anchors, "anchors")
    profile_path = require_file(args.fused_profile, "fused profile")
    grid_path = require_file(args.fusion_grid, "fusion grid")

    profile = pd.read_csv(profile_path)
    anchors = pd.read_csv(anchors_path)
    grid = pd.read_csv(grid_path)
    require_columns(profile, PROFILE_REQUIRED, "fused profile")
    require_columns(anchors, ANCHOR_REQUIRED, "anchors")
    for column in ["dist_m", "ele_gpx_m", "ele_gpx_shape_m", "nlsc_vertical_offset_m", "ele_fused_m"]:
        profile[column] = pd.to_numeric(profile[column], errors="raise")
    for column in ANCHOR_REQUIRED:
        anchors[column] = pd.to_numeric(anchors[column], errors="raise")
    if profile.empty or anchors.empty:
        raise ValueError("Profile and anchors must both be non-empty")

    route_gdf = gpd.read_file(route_path)
    if route_gdf.empty or route_gdf.crs is None:
        raise ValueError("Route Axis is empty or has no CRS")
    route_m = as_single_line(route_gdf.to_crs(args.analysis_crs).geometry)

    gpx_wgs84, gpx_meta = read_gpx(gpx_path)
    gpx_m = gpd.GeoSeries([gpx_wgs84], crs="EPSG:4326").to_crs(args.analysis_crs).iloc[0]

    contour_gdf = gpd.read_file(contour_path)
    if contour_gdf.crs is None:
        raise ValueError("Contour source has no CRS")
    contour_m_all = contour_gdf.to_crs(args.analysis_crs)
    corridor = route_m.buffer(args.contour_buffer_m)
    contour_m = contour_m_all.loc[contour_m_all.geometry.intersects(corridor)].copy()
    contour_m.geometry = contour_m.geometry.intersection(corridor)
    contour_m = contour_m.loc[~contour_m.geometry.is_empty].copy()

    smoothing_scale = scalar_number(profile, "shape_smoothing_scale_m")
    calibration_lambda = scalar_number(profile, "calibration_lambda")

    profile_fig = make_profile_figure(profile, anchors)
    offset_fig = make_offset_figure(profile)
    residual_fig, residual = make_residual_figure(profile, anchors)
    grid_fig = make_grid_figure(grid, smoothing_scale, calibration_lambda)
    map_fig, nearby_contour_n = make_geometry_figure(
        route_m, gpx_m, contour_m, anchors, residual, args.analysis_crs
    )

    dist = profile["dist_m"].to_numpy(float)
    fused = profile["ele_fused_m"].to_numpy(float)
    gain, loss = elevation_travel(fused)
    abs_residual = np.abs(residual)
    route_delta = float(dist[-1] - route_m.length)
    monotonic = bool(np.all(np.diff(dist) >= 0))
    timestamp_complete = int(gpx_meta["timestamp_points"]) == int(gpx_meta["track_points"])
    sensor_origin = scalar_text(profile, "elevation_sensor_origin")
    absolute_reference = scalar_text(profile, "absolute_vertical_reference")
    smoothing_method = scalar_text(profile, "shape_smoothing_method")
    calibration_model = scalar_text(profile, "calibration_model")
    fusion_method = scalar_text(profile, "elevation_fusion_method")

    contour_bundle = sorted(
        path for path in contour_path.parent.glob(contour_path.stem + ".*") if path.is_file()
    )
    sources = source_rows(
        [
            ("Route Axis", route_path),
            ("GPX", gpx_path),
            ("Direct contour anchors", anchors_path),
            ("Fused profile", profile_path),
            ("Fusion audit grid", grid_path),
        ]
        + [("NLSC contour bundle", path) for path in contour_bundle]
    )

    checks = [
        ("Profile distance monotonic", monotonic, "Route Axis chainage must not run backward"),
        ("Profile end matches Route Axis", abs(route_delta) <= 1e-6, f"delta = {route_delta:.12g} m"),
        ("GPX elevation complete", int(gpx_meta["elevation_points"]) == int(gpx_meta["track_points"]), f"{gpx_meta['elevation_points']} / {gpx_meta['track_points']}"),
        ("Absolute reference declared", absolute_reference != "UNKNOWN", absolute_reference),
        ("Anchors available", len(anchors) > 0, f"{len(anchors)} anchors"),
    ]
    overall = all(passed for _, passed, _ in checks)

    cards = [
        ("Route length", f"{route_m.length:,.2f} m"),
        ("Profile samples", f"{len(profile):,}"),
        ("NLSC anchors", f"{len(anchors):,}"),
        ("Selected shape scale", f"{smoothing_scale:g} m" if math.isfinite(smoothing_scale) else "UNKNOWN"),
        ("Calibration lambda", f"{calibration_lambda:g}" if math.isfinite(calibration_lambda) else "UNKNOWN"),
        ("Elevation start / end", f"{fused[0]:.2f} / {fused[-1]:.2f} m"),
        ("Gain / loss", f"+{gain:.2f} / −{loss:.2f} m"),
        ("Anchor MAE / P90", f"{abs_residual.mean():.2f} / {np.quantile(abs_residual, 0.9):.2f} m"),
    ]
    card_html = "".join(
        f"<div class='card'><div class='card-label'>{html_lib.escape(label)}</div><div class='card-value'>{html_lib.escape(value)}</div></div>"
        for label, value in cards
    )
    check_html = "".join(
        f"<tr><td><span class='pill {'pass' if passed else 'fail'}'>{'PASS' if passed else 'FAIL'}</span></td><td>{html_lib.escape(label)}</td><td>{html_lib.escape(detail)}</td></tr>"
        for label, passed, detail in checks
    )
    source_table = html_table(
        ["Role", "Path", "Bytes", "SHA256"],
        [[row["role"], row["path"], row["bytes"], row["sha256"]] for row in sources],
    )
    provenance_table = html_table(
        ["Field", "Value"],
        [
            ["Case ID", args.case_id],
            ["Route chainage authority", "Route Axis"],
            ["Route analysis CRS", args.analysis_crs],
            ["GPX creator", gpx_meta["creator"]],
            ["GPX elevation source", "gpx_trkpt_ele"],
            ["Elevation sensor origin", sensor_origin],
            ["GPX timestamps", f"{gpx_meta['timestamp_points']} / {gpx_meta['track_points']}"],
            ["Stationary detection", "AVAILABLE" if timestamp_complete else "UNAVAILABLE"],
            ["Shape method", smoothing_method],
            ["Shape scale", fmt(smoothing_scale, 2) + " m"],
            ["Absolute vertical reference", absolute_reference],
            ["Calibration model", calibration_model],
            ["Calibration lambda", fmt(calibration_lambda, 2)],
            ["Fusion method", fusion_method],
            ["Nearby contours shown", nearby_contour_n],
            ["Contour display corridor", fmt(args.contour_buffer_m, 1) + " m"],
        ],
    )

    title = args.title or f"{args.case_id} — Route Axis Elevation Fusion QA"
    generated = datetime.now(timezone.utc).isoformat()
    payload = {
        "case_id": args.case_id,
        "overall_pass": overall,
        "route_axis_length_m": route_m.length,
        "profile_rows": len(profile),
        "anchor_rows": len(anchors),
        "selected_window_m": smoothing_scale,
        "selected_lambda": calibration_lambda,
        "anchor_mae_m": float(abs_residual.mean()),
        "anchor_p90_m": float(np.quantile(abs_residual, 0.9)),
        "anchor_max_m": float(abs_residual.max()),
        "fused_gain_m": gain,
        "fused_loss_m": loss,
        "generated_at_utc": generated,
    }

    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html_lib.escape(title)}</title>
<style>
:root{{--ink:#18202a;--muted:#637083;--line:#dbe2ea;--paper:#fff;--bg:#f4f7fa;--accent:#d35400;--good:#13795b;--bad:#b42318}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}}
main{{max-width:1440px;margin:auto;padding:28px}} header{{display:flex;justify-content:space-between;gap:24px;align-items:flex-end;margin-bottom:18px}}
h1{{font-size:26px;margin:0 0 4px}} h2{{font-size:18px;margin:0 0 14px}} .muted{{color:var(--muted)}}
.status{{font-weight:750;font-size:14px;padding:8px 12px;border-radius:999px;background:{'#dcfce7' if overall else '#fee2e2'};color:{'#166534' if overall else '#991b1b'}}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:10px;margin:16px 0}}
.card,.panel{{background:var(--paper);border:1px solid var(--line);border-radius:12px;box-shadow:0 1px 2px #1522380d}}
.card{{padding:14px}} .card-label{{font-size:12px;color:var(--muted)}} .card-value{{font-size:19px;font-weight:700;margin-top:3px}}
.panel{{padding:18px;margin:14px 0}} .plot{{width:100%;display:block;border-radius:8px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}} @media(max-width:900px){{.grid{{grid-template-columns:1fr}} header{{display:block}} .status{{display:inline-block;margin-top:10px}}}}
.table-wrap{{overflow:auto}} table{{border-collapse:collapse;width:100%;font-size:12px}} th,td{{border-bottom:1px solid var(--line);padding:8px;text-align:left;vertical-align:top}} th{{background:#f8fafc;position:sticky;top:0}}
.pill{{display:inline-block;padding:2px 7px;border-radius:99px;font-weight:700;font-size:11px}} .pill.pass{{background:#dcfce7;color:#166534}} .pill.fail{{background:#fee2e2;color:#991b1b}}
.note{{border-left:4px solid #f59e0b;background:#fff8e7;padding:12px 14px;margin:8px 0}} code{{word-break:break-all}} footer{{color:var(--muted);font-size:12px;margin:22px 0}}
</style></head><body><main>
<header><div><h1>{html_lib.escape(title)}</h1><div class="muted">Read-only QA renderer · generated {html_lib.escape(generated)}</div></div><div class="status">{'OVERALL PASS' if overall else 'CHECK REQUIRED'}</div></header>
<section class="cards">{card_html}</section>
<section class="panel"><h2>Contract checks</h2><div class="table-wrap"><table><thead><tr><th>Status</th><th>Check</th><th>Evidence</th></tr></thead><tbody>{check_html}</tbody></table></div></section>
<section class="panel"><h2>Elevation profile</h2><img class="plot" src="{profile_fig}" alt="Raw GPX, smoothed GPX, fused profile, and NLSC anchors"></section>
<section class="grid"><div class="panel"><h2>Vertical calibration offset</h2><img class="plot" src="{offset_fig}" alt="NLSC vertical offset"></div><div class="panel"><h2>Anchor residual</h2><img class="plot" src="{residual_fig}" alt="Fused minus contour residual"></div></section>
<section class="grid"><div class="panel"><h2>Route geometry and contour context</h2><img class="plot" src="{map_fig}" alt="Route Axis, GPX, anchors, and nearby NLSC contours"><p class="muted">Contour geometry is clipped to the configured display corridor. Anchor symbols are projected to Route Axis chainage for display; they are not the original GPX × contour crossing coordinates.</p></div><div class="panel"><h2>Fusion parameter audit grid</h2><img class="plot" src="{grid_fig}" alt="Fusion parameter grid"><p class="muted">The red outline marks the selected production setting. This grid is diagnostic evidence: the selected 50 m scale and lambda 0.5 are testcase-specific and are not chosen solely by minimum in-sample MAE.</p></div></section>
<section class="grid"><div class="panel"><h2>Provenance</h2>{provenance_table}</div><div class="panel"><h2>Interpretation limits</h2>
<div class="note"><b>GPX sensor origin:</b> {html_lib.escape(sensor_origin)}. Decimal smoothing output does not create new sensor precision.</div>
<ul><li>Route Axis owns route order and chainage; GPX geometry is validation and elevation evidence only.</li><li>NLSC contour crossings are calibration anchors, not hard vertical constraints or point-by-point terrain truth.</li><li>Missing GPX timestamps make time-based stationary-jitter detection unavailable.</li><li>Low-frequency vertical calibration may slightly affect near-flat grades; local direction logic needs an explicit minimum-grade threshold.</li><li>The fused profile is terrain/elevation evidence, not a hiking-risk score.</li></ul></div></section>
<section class="panel"><h2>Input identity</h2>{source_table}</section>
<section class="panel"><h2>Machine-readable summary</h2><pre>{html_lib.escape(json.dumps(payload, ensure_ascii=False, indent=2))}</pre></section>
<footer>All figures are embedded. This report needs no CDN, map tile service, Plotly, or Folium runtime after generation.</footer>
</main></body></html>"""

    output = Path(args.output_html)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    print("=" * 78)
    print("ROUTE AXIS ELEVATION FUSION QA HTML")
    print("=" * 78)
    print("case_id:", args.case_id)
    print("overall_pass:", overall)
    print("route_axis_length_m:", route_m.length)
    print("profile_rows:", len(profile))
    print("anchor_rows:", len(anchors))
    print("nearby_contours_shown:", nearby_contour_n)
    print("anchor_mae_m:", float(abs_residual.mean()))
    print("anchor_p90_m:", float(np.quantile(abs_residual, 0.9)))
    print("output_html:", output)


if __name__ == "__main__":
    main()
