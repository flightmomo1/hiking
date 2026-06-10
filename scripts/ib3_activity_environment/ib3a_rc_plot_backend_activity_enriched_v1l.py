#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
IB3A-RC v1l backend activity enriched visual QA plotter.

Purpose:
- Read v1l backend activity enriched CSV.
- Generate per-activity HTML reports for raw vs calibrated data QA.
- Provide 1D timelines and 2D trajectory comparison.
- Generate batch summary CSV / JSON.

Scope:
- Read-only.
- Does not modify v1l CSV.
- Does not require basemap / Leaflet.
- Does not compute formal radar score.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build IB3A-RC v1l backend enriched visual QA HTML reports."
    )
    p.add_argument("--route-folder", required=True)
    p.add_argument("--activity-id", default="")
    p.add_argument("--activity-ids", default="")
    p.add_argument("--input-root", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--max-line-points", type=int, default=2600)
    p.add_argument("--max-marker-points", type=int, default=800)
    return p.parse_args()


def read_csv(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    return rows, fields


def write_csv(path: Path, rows: List[Dict[str, Any]], fields: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip()
    if s == "" or s.lower() in {"nan", "none", "null"}:
        return None
    try:
        f = float(s)
    except Exception:
        return None
    if not math.isfinite(f):
        return None
    return f


def to_bool(v: Any) -> bool:
    return str(v).strip().lower() in {"true", "1", "yes", "y"}


def first_nonempty(row: Dict[str, str], cols: List[str], default: str = "") -> str:
    for c in cols:
        v = row.get(c)
        if v is not None and str(v).strip() != "":
            return str(v)
    return default


def fmt(v: Any, ndigits: int = 3) -> str:
    f = to_float(v)
    if f is None:
        return ""
    return f"{f:.{ndigits}f}".rstrip("0").rstrip(".")


def final_value(rows: List[Dict[str, str]], col: str) -> str:
    for r in reversed(rows):
        v = str(r.get(col, "")).strip()
        if v != "":
            return v
    return ""


def extent(vals: List[float], pad_ratio: float = 0.05) -> Tuple[float, float]:
    vals2 = [v for v in vals if math.isfinite(v)]
    if not vals2:
        return 0.0, 1.0
    lo = min(vals2)
    hi = max(vals2)
    if lo == hi:
        return lo - 1.0, hi + 1.0
    pad = (hi - lo) * pad_ratio
    return lo - pad, hi + pad


def downsample(points: List[Tuple[float, float, Dict[str, str]]], max_n: int) -> List[Tuple[float, float, Dict[str, str]]]:
    if len(points) <= max_n:
        return points
    step = max(1, math.ceil(len(points) / max_n))
    return points[::step]


def find_input_csv(input_root: Path, route_folder: str, activity_id: str) -> Path:
    folder = input_root / route_folder / activity_id
    expected = folder / f"{route_folder}_{activity_id}_backend_activity_enriched_v1l.csv"
    if expected.exists():
        return expected

    matches = sorted(folder.glob("*_backend_activity_enriched_v1l.csv"))
    if len(matches) == 1:
        return matches[0]

    raise FileNotFoundError(f"Cannot find v1l enriched CSV for {route_folder}/{activity_id}: {folder}")


def point_series(rows: List[Dict[str, str]], x_col: str, y_col: str) -> List[Tuple[float, float, Dict[str, str]]]:
    pts: List[Tuple[float, float, Dict[str, str]]] = []
    for r in rows:
        x = to_float(r.get(x_col))
        y = to_float(r.get(y_col))
        if x is None or y is None:
            continue
        pts.append((x, y, r))
    return pts


def filter_points(rows: List[Dict[str, str]], x_col: str, y_col: str, predicate) -> List[Tuple[float, float, Dict[str, str]]]:
    pts: List[Tuple[float, float, Dict[str, str]]] = []
    for r in rows:
        if not predicate(r):
            continue
        x = to_float(r.get(x_col))
        y = to_float(r.get(y_col))
        if x is None or y is None:
            continue
        pts.append((x, y, r))
    return pts


def svg_xy(
    x: float,
    y: float,
    xmin: float,
    xmax: float,
    ymin: float,
    ymax: float,
    width: int,
    height: int,
    left: int,
    right: int,
    top: int,
    bottom: int,
) -> Tuple[float, float]:
    plot_w = width - left - right
    plot_h = height - top - bottom
    sx = left + ((x - xmin) / (xmax - xmin)) * plot_w if xmax != xmin else left + plot_w / 2
    sy = top + (1.0 - ((y - ymin) / (ymax - ymin))) * plot_h if ymax != ymin else top + plot_h / 2
    return sx, sy


def axes_svg(
    title: str,
    xmin: float,
    xmax: float,
    ymin: float,
    ymax: float,
    width: int,
    height: int,
    left: int,
    right: int,
    top: int,
    bottom: int,
    x_label: str,
    y_label: str,
) -> str:
    plot_w = width - left - right
    plot_h = height - top - bottom
    parts: List[str] = []

    parts.append(f'<text x="{width/2:.1f}" y="24" text-anchor="middle" font-size="16" font-weight="700" fill="#111827">{html.escape(title)}</text>')

    for i in range(6):
        frac = i / 5
        y = top + frac * plot_h
        val = ymax - frac * (ymax - ymin)
        parts.append(f'<line x1="{left}" x2="{left+plot_w}" y1="{y:.1f}" y2="{y:.1f}" stroke="#e5e7eb" stroke-width="1"/>')
        parts.append(f'<text x="{left-8}" y="{y+4:.1f}" text-anchor="end" font-size="11" fill="#374151">{val:.5f}</text>')

    for i in range(6):
        frac = i / 5
        x = left + frac * plot_w
        val = xmin + frac * (xmax - xmin)
        parts.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{top}" y2="{top+plot_h}" stroke="#f3f4f6" stroke-width="1"/>')
        parts.append(f'<text x="{x:.1f}" y="{height-14}" text-anchor="middle" font-size="11" fill="#374151">{val:.5f}</text>')

    parts.append(f'<line x1="{left}" x2="{left+plot_w}" y1="{top+plot_h}" y2="{top+plot_h}" stroke="#111827" stroke-width="1.2"/>')
    parts.append(f'<line x1="{left}" x2="{left}" y1="{top}" y2="{top+plot_h}" stroke="#111827" stroke-width="1.2"/>')
    parts.append(f'<text x="{width/2:.1f}" y="{height-2}" text-anchor="middle" font-size="12" fill="#374151">{html.escape(x_label)}</text>')
    parts.append(f'<text x="18" y="{height/2:.1f}" transform="rotate(-90 18 {height/2:.1f})" text-anchor="middle" font-size="12" fill="#374151">{html.escape(y_label)}</text>')

    return "\n".join(parts)


def polyline_svg(
    points: List[Tuple[float, float, Dict[str, str]]],
    xmin: float,
    xmax: float,
    ymin: float,
    ymax: float,
    width: int,
    height: int,
    left: int,
    right: int,
    top: int,
    bottom: int,
    stroke: str,
    width_px: float = 1.8,
    opacity: float = 0.9,
    dasharray: str = "",
) -> str:
    coords: List[str] = []
    for x, y, _ in points:
        sx, sy = svg_xy(x, y, xmin, xmax, ymin, ymax, width, height, left, right, top, bottom)
        coords.append(f"{sx:.1f},{sy:.1f}")
    if not coords:
        return ""
    dash = f' stroke-dasharray="{dasharray}"' if dasharray else ""
    return f'<polyline points="{" ".join(coords)}" fill="none" stroke="{stroke}" stroke-width="{width_px}" opacity="{opacity}"{dash}/>'


def marker_svg(
    points: List[Tuple[float, float, Dict[str, str]]],
    xmin: float,
    xmax: float,
    ymin: float,
    ymax: float,
    width: int,
    height: int,
    left: int,
    right: int,
    top: int,
    bottom: int,
    fill: str,
    radius: float = 3.5,
    opacity: float = 0.9,
) -> str:
    out: List[str] = []
    for x, y, r in points:
        sx, sy = svg_xy(x, y, xmin, xmax, ymin, ymax, width, height, left, right, top, bottom)
        title = html.escape(
            "idx={idx} t={t} route={route} move={move} "
            "hsrc={hsrc} hconf={hconf} ele={ele} raw_ele={raw_ele} review={review}".format(
                idx=r.get("raw_point_index", ""),
                t=r.get("elapsed_sec", ""),
                route=r.get("route_class", ""),
                move=r.get("movement_state", ""),
                hsrc=r.get("horizontal_calibration_source", ""),
                hconf=r.get("horizontal_calibration_confidence", ""),
                ele=r.get("calibrated_elevation_m", ""),
                raw_ele=r.get("raw_elevation_m", ""),
                review=r.get("calibration_review_required", ""),
            )
        )
        out.append(
            f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="{radius}" fill="{fill}" opacity="{opacity}">'
            f"<title>{title}</title></circle>"
        )
    return "\n".join(out)


def build_1d_chart(
    title: str,
    line_sets: List[Tuple[str, str, List[Tuple[float, float, Dict[str, str]]]]],
    marker_sets: List[Tuple[str, str, List[Tuple[float, float, Dict[str, str]]]]],
    y_label: str,
    max_line_points: int,
    max_marker_points: int,
) -> str:
    width, height = 1180, 380
    left, right, top, bottom = 76, 24, 42, 42

    all_points: List[Tuple[float, float, Dict[str, str]]] = []
    for _, _, pts in line_sets:
        all_points.extend(pts)
    for _, _, pts in marker_sets:
        all_points.extend(pts)

    if not all_points:
        return f"<p>No plottable points for {html.escape(title)}.</p>"

    xs = [p[0] for p in all_points]
    ys = [p[1] for p in all_points]
    xmin, xmax = extent(xs, 0.01)
    ymin, ymax = extent(ys, 0.08)

    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" role="img">']
    parts.append(axes_svg(title, xmin, xmax, ymin, ymax, width, height, left, right, top, bottom, "elapsed_sec", y_label))

    legend: List[Tuple[str, str, str, int]] = []

    for label, color, pts in line_sets:
        pts2 = downsample(pts, max_line_points)
        parts.append(polyline_svg(pts2, xmin, xmax, ymin, ymax, width, height, left, right, top, bottom, color))
        legend.append((label, color, "line", len(pts)))

    for label, color, pts in marker_sets:
        pts2 = downsample(pts, max_marker_points)
        parts.append(marker_svg(pts2, xmin, xmax, ymin, ymax, width, height, left, right, top, bottom, color))
        legend.append((label, color, "dot", len(pts)))

    lx = left + 8
    ly = top + 16
    for i, (label, color, kind, n) in enumerate(legend):
        y = ly + i * 18
        if kind == "line":
            parts.append(f'<line x1="{lx}" x2="{lx+22}" y1="{y}" y2="{y}" stroke="{color}" stroke-width="2"/>')
        else:
            parts.append(f'<circle cx="{lx+11}" cy="{y}" r="4" fill="{color}" opacity="0.85"/>')
        parts.append(f'<text x="{lx+30}" y="{y+4}" font-size="12" fill="#111827">{html.escape(label)} ({n})</text>')

    parts.append("</svg>")
    return "\n".join(parts)


def path_series(rows: List[Dict[str, str]], lon_col: str, lat_col: str) -> List[Tuple[float, float, Dict[str, str]]]:
    pts: List[Tuple[float, float, Dict[str, str]]] = []
    for r in rows:
        lon = to_float(r.get(lon_col))
        lat = to_float(r.get(lat_col))
        if lon is None or lat is None:
            continue
        pts.append((lon, lat, r))
    return pts


def build_2d_chart(
    title: str,
    path_sets: List[Tuple[str, str, List[Tuple[float, float, Dict[str, str]]], float, float, str]],
    marker_sets: List[Tuple[str, str, List[Tuple[float, float, Dict[str, str]]]]],
    max_line_points: int,
    max_marker_points: int,
) -> str:
    width, height = 880, 680
    left, right, top, bottom = 70, 28, 44, 50

    all_points: List[Tuple[float, float, Dict[str, str]]] = []
    for _, _, pts, _, _, _ in path_sets:
        all_points.extend(pts)
    for _, _, pts in marker_sets:
        all_points.extend(pts)

    if not all_points:
        return f"<p>No 2D path points for {html.escape(title)}.</p>"

    xs = [p[0] for p in all_points]
    ys = [p[1] for p in all_points]
    xmin, xmax = extent(xs, 0.02)
    ymin, ymax = extent(ys, 0.02)

    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" role="img">']
    parts.append(axes_svg(title, xmin, xmax, ymin, ymax, width, height, left, right, top, bottom, "longitude", "latitude"))

    legend: List[Tuple[str, str, str, int]] = []

    for label, color, pts, opacity, line_width, dasharray in path_sets:
        pts2 = downsample(pts, max_line_points)
        parts.append(
            polyline_svg(
                pts2, xmin, xmax, ymin, ymax,
                width, height, left, right, top, bottom,
                color, line_width, opacity, dasharray
            )
        )
        legend.append((label, color, "line", len(pts)))

    for label, color, pts in marker_sets:
        pts2 = downsample(pts, max_marker_points)
        parts.append(marker_svg(pts2, xmin, xmax, ymin, ymax, width, height, left, right, top, bottom, color, 3.5, 0.85))
        legend.append((label, color, "dot", len(pts)))

    lx = left + 8
    ly = top + 16
    for i, (label, color, kind, n) in enumerate(legend):
        y = ly + i * 18
        if kind == "line":
            parts.append(f'<line x1="{lx}" x2="{lx+22}" y1="{y}" y2="{y}" stroke="{color}" stroke-width="2"/>')
        else:
            parts.append(f'<circle cx="{lx+11}" cy="{y}" r="4" fill="{color}" opacity="0.85"/>')
        parts.append(f'<text x="{lx+30}" y="{y+4}" font-size="12" fill="#111827">{html.escape(label)} ({n})</text>')

    parts.append("</svg>")
    return "\n".join(parts)


def html_table(rows: List[Dict[str, str]], cols: List[str], max_rows: int = 80) -> str:
    parts = ['<table class="qa-table">']
    parts.append("<thead><tr>" + "".join(f"<th>{html.escape(c)}</th>" for c in cols) + "</tr></thead>")
    parts.append("<tbody>")
    for r in rows[:max_rows]:
        parts.append("<tr>" + "".join(f"<td>{html.escape(str(r.get(c, '')))}</td>" for c in cols) + "</tr>")
    parts.append("</tbody></table>")
    return "\n".join(parts)


def count_nonempty(rows: List[Dict[str, str]], col: str) -> int:
    return sum(1 for r in rows if str(r.get(col, "")).strip() != "")


def count_true(rows: List[Dict[str, str]], col: str) -> int:
    return sum(1 for r in rows if to_bool(r.get(col)))


def count_nonzero(rows: List[Dict[str, str]], col: str) -> int:
    return sum(1 for r in rows if (to_float(r.get(col)) or 0.0) != 0.0)


def process_activity(
    route_folder: str,
    activity_id: str,
    input_root: Path,
    out_dir: Path,
    max_line_points: int,
    max_marker_points: int,
) -> Dict[str, Any]:
    in_fp = find_input_csv(input_root, route_folder, activity_id)
    rows, fields = read_csv(in_fp)

    out_activity_dir = out_dir / route_folder / activity_id
    out_activity_dir.mkdir(parents=True, exist_ok=True)
    out_html = out_activity_dir / f"{route_folder}_{activity_id}_backend_activity_enriched_visual_qa_v1l.html"

    total_rows = len(rows)

    route_counts = Counter(r.get("route_class", "") for r in rows)
    move_counts = Counter(r.get("movement_state", "") for r in rows)
    hsrc_counts = Counter(r.get("horizontal_calibration_source", "") for r in rows)
    hconf_counts = Counter(r.get("horizontal_calibration_confidence", "") for r in rows)
    backend_counts = Counter(r.get("backend_use_policy", "") for r in rows)

    raw_ele = point_series(rows, "elapsed_sec", "raw_elevation_m")
    cal_ele = point_series(rows, "elapsed_sec", "calibrated_elevation_m")
    speed = point_series(rows, "elapsed_sec", "calibrated_speed_mps")
    step_dist = point_series(rows, "elapsed_sec", "calibrated_step_distance_m")
    slope = point_series(rows, "elapsed_sec", "calibrated_slope_pct")
    gain = point_series(rows, "elapsed_sec", "agg_total_gain_m")
    loss = point_series(rows, "elapsed_sec", "agg_total_loss_m")

    review_ele = filter_points(rows, "elapsed_sec", "calibrated_elevation_m", lambda r: to_bool(r.get("calibration_review_required")))
    motion_artifact_ele = filter_points(rows, "elapsed_sec", "calibrated_elevation_m", lambda r: to_bool(r.get("motion_artifact_flag")))
    elevation_artifact_ele = filter_points(rows, "elapsed_sec", "calibrated_elevation_m", lambda r: to_bool(r.get("elevation_artifact_flag")))
    wrong_route_ele = filter_points(rows, "elapsed_sec", "calibrated_elevation_m", lambda r: r.get("route_class") == "WRONG_ROUTE")
    off_target_ele = filter_points(rows, "elapsed_sec", "calibrated_elevation_m", lambda r: r.get("route_class") == "OFF_TARGET")
    supplement_ele = filter_points(rows, "elapsed_sec", "calibrated_elevation_m", lambda r: to_bool(r.get("agg_supplement_step_valid")))

    raw_path = path_series(rows, "raw_lon", "raw_lat")
    cal_path = path_series(rows, "calibrated_lon", "calibrated_lat")
    display_path = path_series(rows, "display_lon", "display_lat")

    review_path = [(to_float(r.get("calibrated_lon")), to_float(r.get("calibrated_lat")), r) for r in rows if to_bool(r.get("calibration_review_required"))]
    review_path = [(x, y, r) for x, y, r in review_path if x is not None and y is not None]

    wrong_path = [(to_float(r.get("calibrated_lon")), to_float(r.get("calibrated_lat")), r) for r in rows if r.get("route_class") == "WRONG_ROUTE"]
    wrong_path = [(x, y, r) for x, y, r in wrong_path if x is not None and y is not None]

    off_path = [(to_float(r.get("calibrated_lon")), to_float(r.get("calibrated_lat")), r) for r in rows if r.get("route_class") == "OFF_TARGET"]
    off_path = [(x, y, r) for x, y, r in off_path if x is not None and y is not None]

    ele_chart = build_1d_chart(
        f"{activity_id} 1D elevation: raw vs calibrated",
        [
            ("raw elevation", "#9ca3af", raw_ele),
            ("calibrated elevation", "#2563eb", cal_ele),
        ],
        [
            ("wrong route", "#dc2626", wrong_route_ele),
            ("off target", "#7c3aed", off_target_ele),
            ("supplement step", "#16a34a", supplement_ele),
            ("calibration review", "#f97316", review_ele),
            ("motion artifact", "#f97316", motion_artifact_ele),
            ("elevation artifact", "#9333ea", elevation_artifact_ele),
        ],
        "elevation_m",
        max_line_points,
        max_marker_points,
    )

    speed_chart = build_1d_chart(
        f"{activity_id} 1D motion: speed and step distance",
        [
            ("calibrated speed mps", "#0891b2", speed),
            ("step distance m", "#16a34a", step_dist),
        ],
        [
            ("motion artifact", "#dc2626", filter_points(rows, "elapsed_sec", "calibrated_speed_mps", lambda r: to_bool(r.get("motion_artifact_flag")))),
            ("wrong route", "#f97316", filter_points(rows, "elapsed_sec", "calibrated_speed_mps", lambda r: r.get("route_class") == "WRONG_ROUTE")),
        ],
        "speed_or_distance",
        max_line_points,
        max_marker_points,
    )

    slope_chart = build_1d_chart(
        f"{activity_id} 1D slope",
        [
            ("calibrated slope pct", "#7c3aed", slope),
        ],
        [
            ("supplement step", "#16a34a", filter_points(rows, "elapsed_sec", "calibrated_slope_pct", lambda r: to_bool(r.get("agg_supplement_step_valid")))),
            ("elevation artifact", "#dc2626", filter_points(rows, "elapsed_sec", "calibrated_slope_pct", lambda r: to_bool(r.get("elevation_artifact_flag")))),
        ],
        "slope_pct",
        max_line_points,
        max_marker_points,
    )

    gain_loss_chart = build_1d_chart(
        f"{activity_id} 1D total gain/loss",
        [
            ("agg total gain", "#16a34a", gain),
            ("agg total loss", "#dc2626", loss),
        ],
        [],
        "meters",
        max_line_points,
        max_marker_points,
    )

    raw_review_path = [
        (to_float(r.get("raw_lon")), to_float(r.get("raw_lat")), r)
        for r in rows
        if to_bool(r.get("calibration_review_required"))
    ]
    raw_review_path = [(x, y, r) for x, y, r in raw_review_path if x is not None and y is not None]

    raw_wrong_path = [
        (to_float(r.get("raw_lon")), to_float(r.get("raw_lat")), r)
        for r in rows
        if r.get("route_class") == "WRONG_ROUTE"
    ]
    raw_wrong_path = [(x, y, r) for x, y, r in raw_wrong_path if x is not None and y is not None]

    raw_off_path = [
        (to_float(r.get("raw_lon")), to_float(r.get("raw_lat")), r)
        for r in rows
        if r.get("route_class") == "OFF_TARGET"
    ]
    raw_off_path = [(x, y, r) for x, y, r in raw_off_path if x is not None and y is not None]


    map_chart_pre = build_2d_chart(
        f"{activity_id} 2D path (pre-calibration): raw GPS",
        [
            ("raw path", "#9ca3af", raw_path, 0.90, 2.2, ""),
        ],
        [
            ("raw calibration review", "#f97316", raw_review_path),
            ("raw wrong route", "#dc2626", raw_wrong_path),
            ("raw off target", "#7c3aed", raw_off_path),
        ],
        max_line_points,
        max_marker_points,
    )


    map_chart_post = build_2d_chart(
        f"{activity_id} 2D path (post-calibration): calibrated + display",
        [
            ("display path", "#16a34a", display_path, 0.65, 2.0, "6 4"),
            ("calibrated path", "#2563eb", cal_path, 0.98, 2.8, ""),
        ],
        [
            ("calibration review", "#f97316", review_path),
            ("wrong route", "#dc2626", wrong_path),
            ("off target", "#7c3aed", off_path),
        ],
        max_line_points,
        max_marker_points,
    )

    route_counts_html = "".join(f"<li><code>{html.escape(k)}</code>: {v}</li>" for k, v in sorted(route_counts.items()))
    move_counts_html = "".join(f"<li><code>{html.escape(k)}</code>: {v}</li>" for k, v in move_counts.most_common())
    hsrc_counts_html = "".join(f"<li><code>{html.escape(k)}</code>: {v}</li>" for k, v in hsrc_counts.most_common())
    hconf_counts_html = "".join(f"<li><code>{html.escape(k)}</code>: {v}</li>" for k, v in hconf_counts.most_common())
    backend_counts_html = "".join(f"<li><code>{html.escape(k)}</code>: {v}</li>" for k, v in backend_counts.most_common())

    focus_rows = [
        r for r in rows
        if to_bool(r.get("calibration_review_required"))
        or to_bool(r.get("motion_artifact_flag"))
        or to_bool(r.get("elevation_artifact_flag"))
        or r.get("route_class") in {"WRONG_ROUTE", "OFF_TARGET", "UNKNOWN_REVIEW"}
        or to_bool(r.get("agg_supplement_step_valid"))
    ]

    table_cols = [
        "raw_point_index",
        "elapsed_sec",
        "raw_lat",
        "raw_lon",
        "calibrated_lat",
        "calibrated_lon",
        "display_lat",
        "display_lon",
        "raw_elevation_m",
        "calibrated_elevation_m",
        "route_class",
        "movement_state",
        "backend_use_policy",
        "horizontal_calibration_source",
        "horizontal_calibration_confidence",
        "calibration_review_required",
        "motion_artifact_flag",
        "elevation_artifact_flag",
        "agg_supplement_step_valid",
        "osm_semantic_join_method",
        "radar_physical_fitness_hint",
        "radar_navigation_hint",
    ]

    html_text = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(route_folder)} {html.escape(activity_id)} v1l backend enriched visual QA</title>
<style>
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
  margin: 24px;
  color: #111827;
  background: #f9fafb;
}}
.card {{
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 18px;
  margin: 16px 0;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}}
.grid {{
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}}
.metric {{
  background: #f3f4f6;
  border-radius: 10px;
  padding: 12px;
}}
.metric .label {{ color: #6b7280; font-size: 12px; }}
.metric .value {{ font-size: 22px; font-weight: 700; }}
.small {{ color: #6b7280; font-size: 13px; }}
.qa-table {{
  border-collapse: collapse;
  width: 100%;
  font-size: 12px;
}}
.qa-table th, .qa-table td {{
  border: 1px solid #e5e7eb;
  padding: 4px 6px;
  vertical-align: top;
}}
.qa-table th {{
  background: #f3f4f6;
  position: sticky;
  top: 0;
}}
code {{ background: #f3f4f6; padding: 1px 4px; border-radius: 4px; }}
</style>
</head>
<body>
<div class="card">
<h1>{html.escape(route_folder)} / {html.escape(activity_id)} - v1l backend enriched visual QA</h1>
<div class="small">Input: <code>{html.escape(str(in_fp))}</code></div>
<div class="small">Read-only QA report. 1D timelines + 2D raw/calibrated/display path comparison.</div>
</div>

<div class="card grid">
  <div class="metric"><div class="label">Rows</div><div class="value">{total_rows}</div></div>
  <div class="metric"><div class="label">Raw lat/lon coverage</div><div class="value">{count_nonempty(rows, "raw_lat")} / {count_nonempty(rows, "raw_lon")}</div></div>
  <div class="metric"><div class="label">Cal lat/lon coverage</div><div class="value">{count_nonempty(rows, "calibrated_lat")} / {count_nonempty(rows, "calibrated_lon")}</div></div>
  <div class="metric"><div class="label">Elevation coverage</div><div class="value">{count_nonempty(rows, "calibrated_elevation_m")}</div></div>
  <div class="metric"><div class="label">Calibration review</div><div class="value">{count_true(rows, "calibration_review_required")}</div></div>
  <div class="metric"><div class="label">Motion artifacts</div><div class="value">{count_true(rows, "motion_artifact_flag")}</div></div>
  <div class="metric"><div class="label">Elevation artifacts</div><div class="value">{count_true(rows, "elevation_artifact_flag")}</div></div>
  <div class="metric"><div class="label">OSM joined</div><div class="value">{sum(1 for r in rows if r.get("osm_semantic_join_method") != "NOT_JOINED_V1L1_SCHEMA_ONLY")}</div></div>
  <div class="metric"><div class="label">Final gain/loss</div><div class="value">{html.escape(fmt(final_value(rows, "agg_total_gain_m")))} / {html.escape(fmt(final_value(rows, "agg_total_loss_m")))}</div></div>
  <div class="metric"><div class="label">Supplement steps</div><div class="value">{count_true(rows, "agg_supplement_step_valid")}</div></div>
  <div class="metric"><div class="label">Radar fitness nonzero</div><div class="value">{count_nonzero(rows, "radar_physical_fitness_hint")}</div></div>
  <div class="metric"><div class="label">Radar navigation nonzero</div><div class="value">{count_nonzero(rows, "radar_navigation_hint")}</div></div>
</div>

<div class="card">
<h2>Class / policy counts</h2>
<h3>route_class</h3>
<ul>{route_counts_html}</ul>
<h3>movement_state</h3>
<ul>{move_counts_html}</ul>
<h3>horizontal_calibration_source</h3>
<ul>{hsrc_counts_html}</ul>
<h3>horizontal_calibration_confidence</h3>
<ul>{hconf_counts_html}</ul>
<h3>backend_use_policy</h3>
<ul>{backend_counts_html}</ul>
</div>

<div class="card">
<h2>2D Path QA - Pre-calibration</h2>
{map_chart_pre}
</div>

<div class="card">
<h2>2D Path QA - Post-calibration</h2>
{map_chart_post}
</div>

<div class="card">{ele_chart}</div>
<div class="card">{speed_chart}</div>
<div class="card">{slope_chart}</div>
<div class="card">{gain_loss_chart}</div>

<div class="card">
<h2>QA focus rows</h2>
<p class="small">Rows include review-required, artifact, wrong-route/off-target/unknown-review, or supplement-step rows. Limited to first 80 rows.</p>
{html_table(focus_rows, table_cols, 80)}
</div>
</body>
</html>
"""
    out_html.write_text(html_text, encoding="utf-8")

    summary = {
        "activity_id": activity_id,
        "status": "PASS",
        "rows": total_rows,
        "input_csv": str(in_fp),
        "output_html": str(out_html),
        "raw_lat_nonempty": count_nonempty(rows, "raw_lat"),
        "raw_lon_nonempty": count_nonempty(rows, "raw_lon"),
        "calibrated_lat_nonempty": count_nonempty(rows, "calibrated_lat"),
        "calibrated_lon_nonempty": count_nonempty(rows, "calibrated_lon"),
        "display_lat_nonempty": count_nonempty(rows, "display_lat"),
        "display_lon_nonempty": count_nonempty(rows, "display_lon"),
        "calibrated_elevation_nonempty": count_nonempty(rows, "calibrated_elevation_m"),
        "calibration_review_required_n": count_true(rows, "calibration_review_required"),
        "motion_artifact_n": count_true(rows, "motion_artifact_flag"),
        "elevation_artifact_n": count_true(rows, "elevation_artifact_flag"),
        "supplement_step_n": count_true(rows, "agg_supplement_step_valid"),
        "osm_joined_n": sum(1 for r in rows if r.get("osm_semantic_join_method") != "NOT_JOINED_V1L1_SCHEMA_ONLY"),
        "radar_physical_fitness_nonzero_n": count_nonzero(rows, "radar_physical_fitness_hint"),
        "radar_navigation_nonzero_n": count_nonzero(rows, "radar_navigation_hint"),
        "route_class_counts": dict(route_counts),
        "movement_state_counts": dict(move_counts),
        "horizontal_calibration_source_counts": dict(hsrc_counts),
        "horizontal_calibration_confidence_counts": dict(hconf_counts),
        "backend_use_policy_counts": dict(backend_counts),
    }
    return summary


def main() -> int:
    args = parse_args()
    route_folder = args.route_folder
    input_root = Path(args.input_root)
    out_dir = Path(args.out_dir)

    if args.activity_ids.strip():
        activity_ids = [x.strip() for x in args.activity_ids.split(",") if x.strip()]
    elif args.activity_id.strip():
        activity_ids = [args.activity_id.strip()]
    else:
        raise ValueError("Provide --activity-id or --activity-ids")

    summaries: List[Dict[str, Any]] = []
    fail_n = 0

    for aid in activity_ids:
        try:
            s = process_activity(
                route_folder=route_folder,
                activity_id=aid,
                input_root=input_root,
                out_dir=out_dir,
                max_line_points=args.max_line_points,
                max_marker_points=args.max_marker_points,
            )
            summaries.append(s)
            print(
                f"[PASS] {aid}: rows={s['rows']} "
                f"raw={s['raw_lat_nonempty']}/{s['raw_lon_nonempty']} "
                f"cal={s['calibrated_lat_nonempty']}/{s['calibrated_lon_nonempty']} "
                f"ele={s['calibrated_elevation_nonempty']} "
                f"review={s['calibration_review_required_n']} "
                f"osm_joined={s['osm_joined_n']} "
                f"html={s['output_html']}"
            )
        except Exception as exc:
            fail_n += 1
            s = {
                "activity_id": aid,
                "status": "FAIL",
                "rows": 0,
                "error": str(exc),
            }
            summaries.append(s)
            print(f"[FAIL] {aid}: {exc}")

    batch_dir = out_dir / "_batch_summary"
    batch_dir.mkdir(parents=True, exist_ok=True)

    csv_rows: List[Dict[str, Any]] = []
    for s in summaries:
        row = dict(s)
        for k in [
            "route_class_counts",
            "movement_state_counts",
            "horizontal_calibration_source_counts",
            "horizontal_calibration_confidence_counts",
            "backend_use_policy_counts",
        ]:
            if k in row:
                row[k] = json.dumps(row[k], ensure_ascii=False)
        csv_rows.append(row)

    fieldnames: List[str] = []
    for r in csv_rows:
        for k in r.keys():
            if k not in fieldnames:
                fieldnames.append(k)

    summary_csv = batch_dir / f"{route_folder}_v1l_backend_activity_enriched_visual_qa_summary.csv"
    summary_json = batch_dir / f"{route_folder}_v1l_backend_activity_enriched_visual_qa_summary.json"

    write_csv(summary_csv, csv_rows, fieldnames)
    summary_json.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"summary_csv={summary_csv}")
    print(f"summary_json={summary_json}")
    print("status=PASS" if fail_n == 0 else f"status=FAIL fail_n={fail_n}")

    return 0 if fail_n == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
