#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
IB3K-RC v1k5 supplement-only elevation visual QA plotter.

Input:
- v1k5 supplement-only calibrated elevation CSV:
  outputs/.../<route_folder>/<activity_id>/*_calibrated_elevation_v1k5.csv

Output:
- per-activity HTML visual QA report
- batch summary CSV / JSON

Scope:
- Read-only visualization.
- Does not modify v1k5 CSV / JSON.
- Highlights supplement steps, review-only steps, baseline vs total gain/loss, join distance,
  profile-distance jumps, and elevation artifacts.
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
    parser = argparse.ArgumentParser(
        description="Build IB3K-RC v1k5 supplement-only elevation visual QA HTML reports."
    )
    parser.add_argument("--route-folder", required=True)
    parser.add_argument("--activity-id", default="")
    parser.add_argument("--activity-ids", default="")
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--max-line-points", type=int, default=2400)
    parser.add_argument("--max-marker-points", type=int, default=700)
    return parser.parse_args()


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
    if v is None:
        return False
    return str(v).strip().lower() in {"true", "1", "yes", "y"}


def fmt(v: Any, ndigits: int = 3) -> str:
    f = to_float(v)
    if f is None:
        return ""
    return f"{f:.{ndigits}f}".rstrip("0").rstrip(".")


def read_csv(fp: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    with fp.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    return rows, fieldnames


def write_csv(fp: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    fp.parent.mkdir(parents=True, exist_ok=True)
    with fp.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def find_input_csv(input_root: Path, route_folder: str, activity_id: str) -> Path:
    folder = input_root / route_folder / activity_id
    expected = folder / f"{route_folder}_{activity_id}_calibrated_elevation_v1k5.csv"
    if expected.exists():
        return expected

    matches = list(folder.glob("*_calibrated_elevation_v1k5.csv"))
    if len(matches) == 1:
        return matches[0]

    raise FileNotFoundError(f"Cannot find v1k5 CSV for {route_folder}/{activity_id}: {folder}")


def downsample(points: List[Tuple[float, float, Dict[str, str]]], max_n: int) -> List[Tuple[float, float, Dict[str, str]]]:
    if len(points) <= max_n:
        return points
    step = max(1, math.ceil(len(points) / max_n))
    return points[::step]


def extent(vals: List[float], pad_ratio: float = 0.05) -> Tuple[float, float]:
    if not vals:
        return 0.0, 1.0
    lo = min(vals)
    hi = max(vals)
    if not math.isfinite(lo) or not math.isfinite(hi):
        return 0.0, 1.0
    if lo == hi:
        return lo - 1.0, hi + 1.0
    pad = (hi - lo) * pad_ratio
    return lo - pad, hi + pad


def svg_scale(
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
    sx = left + ((x - xmin) / (xmax - xmin)) * plot_w if xmax != xmin else left
    sy = top + (1.0 - ((y - ymin) / (ymax - ymin))) * plot_h if ymax != ymin else top + plot_h / 2
    return sx, sy


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
    stroke_width: float = 1.5,
) -> str:
    coords = []
    for x, y, _ in points:
        sx, sy = svg_scale(x, y, xmin, xmax, ymin, ymax, width, height, left, right, top, bottom)
        coords.append(f"{sx:.1f},{sy:.1f}")
    if not coords:
        return ""
    return f'<polyline points="{" ".join(coords)}" fill="none" stroke="{stroke}" stroke-width="{stroke_width}" opacity="0.9"/>'


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
    radius: float = 3.4,
    opacity: float = 0.9,
) -> str:
    out = []
    for x, y, row in points:
        sx, sy = svg_scale(x, y, xmin, xmax, ymin, ymax, width, height, left, right, top, bottom)
        title = html.escape(
            "idx={idx} t={t} route={route} move={move} "
            "ele={ele} supp_id={sid} supp_delta={sdelta} supp_slope={sslope} "
            "supp_reason={sreason}".format(
                idx=row.get("raw_point_index", ""),
                t=row.get("elapsed_sec", ""),
                route=row.get("route_class", ""),
                move=row.get("movement_state", ""),
                ele=row.get("calibrated_elevation_m", ""),
                sid=row.get("agg_supplement_step_id", ""),
                sdelta=row.get("agg_supplement_delta_elevation_m", ""),
                sslope=row.get("agg_supplement_slope_pct", ""),
                sreason=row.get("agg_supplement_step_reason", ""),
            )
        )
        out.append(
            f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="{radius}" fill="{fill}" opacity="{opacity}">'
            f"<title>{title}</title></circle>"
        )
    return "\n".join(out)


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
    y_label: str,
) -> str:
    plot_w = width - left - right
    plot_h = height - top - bottom
    x0, y0 = left, top + plot_h

    grid = []
    for i in range(6):
        frac = i / 5
        y = top + frac * plot_h
        val = ymax - frac * (ymax - ymin)
        grid.append(f'<line x1="{left}" x2="{left + plot_w}" y1="{y:.1f}" y2="{y:.1f}" stroke="#e5e7eb" stroke-width="1"/>')
        grid.append(f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="#374151">{val:.1f}</text>')

    for i in range(6):
        frac = i / 5
        x = left + frac * plot_w
        val = xmin + frac * (xmax - xmin)
        grid.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{top}" y2="{top + plot_h}" stroke="#f3f4f6" stroke-width="1"/>')
        grid.append(f'<text x="{x:.1f}" y="{height - 14}" text-anchor="middle" font-size="11" fill="#374151">{val:.0f}</text>')

    return f"""
<text x="{width/2:.1f}" y="24" text-anchor="middle" font-size="16" font-weight="700" fill="#111827">{html.escape(title)}</text>
<text x="{width/2:.1f}" y="{height - 2}" text-anchor="middle" font-size="12" fill="#374151">elapsed_sec</text>
<text x="18" y="{height/2:.1f}" transform="rotate(-90 18 {height/2:.1f})" text-anchor="middle" font-size="12" fill="#374151">{html.escape(y_label)}</text>
{''.join(grid)}
<line x1="{x0}" x2="{left + plot_w}" y1="{y0}" y2="{y0}" stroke="#111827" stroke-width="1.2"/>
<line x1="{left}" x2="{left}" y1="{top}" y2="{top + plot_h}" stroke="#111827" stroke-width="1.2"/>
"""


def build_chart_svg(
    title: str,
    line_sets: List[Tuple[str, str, List[Tuple[float, float, Dict[str, str]]]]],
    marker_sets: List[Tuple[str, str, List[Tuple[float, float, Dict[str, str]]]]],
    y_label: str,
    max_line_points: int,
    max_marker_points: int,
) -> str:
    width, height = 1180, 380
    left, right, top, bottom = 72, 24, 42, 42

    all_points = []
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

    svg_parts = [
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" role="img">',
        axes_svg(title, xmin, xmax, ymin, ymax, width, height, left, right, top, bottom, y_label),
    ]

    legend = []
    for label, color, pts in line_sets:
        pts2 = downsample(pts, max_line_points)
        svg_parts.append(polyline_svg(pts2, xmin, xmax, ymin, ymax, width, height, left, right, top, bottom, color))
        legend.append((label, color, "line", len(pts)))

    for label, color, pts in marker_sets:
        pts2 = downsample(pts, max_marker_points)
        svg_parts.append(marker_svg(pts2, xmin, xmax, ymin, ymax, width, height, left, right, top, bottom, color))
        legend.append((label, color, "dot", len(pts)))

    lx = left + 8
    ly = top + 16
    for i, (label, color, kind, n) in enumerate(legend):
        y = ly + i * 18
        if kind == "line":
            svg_parts.append(f'<line x1="{lx}" x2="{lx + 22}" y1="{y}" y2="{y}" stroke="{color}" stroke-width="2"/>')
        else:
            svg_parts.append(f'<circle cx="{lx + 11}" cy="{y}" r="4" fill="{color}" opacity="0.85"/>')
        svg_parts.append(f'<text x="{lx + 30}" y="{y + 4}" font-size="12" fill="#111827">{html.escape(label)} ({n})</text>')

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def point_series(rows: List[Dict[str, str]], x_col: str, y_col: str) -> List[Tuple[float, float, Dict[str, str]]]:
    pts = []
    for row in rows:
        x = to_float(row.get(x_col))
        y = to_float(row.get(y_col))
        if x is None or y is None:
            continue
        pts.append((x, y, row))
    return pts


def filter_points(rows: List[Dict[str, str]], x_col: str, y_col: str, predicate) -> List[Tuple[float, float, Dict[str, str]]]:
    pts = []
    for row in rows:
        if not predicate(row):
            continue
        x = to_float(row.get(x_col))
        y = to_float(row.get(y_col))
        if x is None or y is None:
            continue
        pts.append((x, y, row))
    return pts


def html_table(rows: List[Dict[str, str]], cols: List[str], max_rows: int = 80) -> str:
    out = ['<table class="qa-table">']
    out.append("<thead><tr>" + "".join(f"<th>{html.escape(c)}</th>" for c in cols) + "</tr></thead>")
    out.append("<tbody>")
    for row in rows[:max_rows]:
        out.append("<tr>" + "".join(f"<td>{html.escape(str(row.get(c, '')))}</td>" for c in cols) + "</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def final_value(rows: List[Dict[str, str]], col: str) -> str:
    for r in reversed(rows):
        v = str(r.get(col, "")).strip()
        if v != "":
            return v
    return ""


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
    out_html = out_activity_dir / f"{route_folder}_{activity_id}_calibrated_elevation_visual_qa_v1k5.html"

    total_rows = len(rows)
    valid_supp_rows = [r for r in rows if r.get("agg_supplement_step_valid") == "True"]
    review_supp_rows = [r for r in rows if r.get("agg_supplement_step_review_only") == "True"]
    candidate_supp_rows = [
        r for r in rows
        if str(r.get("agg_supplement_step_id", "")).strip() != ""
    ]
    artifact_rows = [r for r in rows if to_bool(r.get("elevation_artifact_flag"))]
    profile_jump_rows = [r for r in rows if to_bool(r.get("elevation_profile_dist_jump_flag"))]
    join_hard_rows = [r for r in rows if "ELEVATION_JOIN_DIST_GT_10M_HARD_EXCLUDED" in r.get("gain_loss_excluded_reason", "")]

    route_counts = Counter(r.get("route_class", "") for r in rows)
    movement_counts = Counter(r.get("movement_state", "") for r in rows)
    source_counts = Counter(r.get("calibrated_elevation_source", "") for r in rows)

    baseline_gain = final_value(rows, "calibrated_cumulative_gain_m")
    baseline_loss = final_value(rows, "calibrated_cumulative_loss_m")
    supplemental_gain = final_value(rows, "agg_supplemental_gain_m")
    supplemental_loss = final_value(rows, "agg_supplemental_loss_m")
    total_gain = final_value(rows, "agg_total_gain_m")
    total_loss = final_value(rows, "agg_total_loss_m")

    cal_ele = point_series(rows, "elapsed_sec", "calibrated_elevation_m")
    raw_ele = point_series(rows, "elapsed_sec", "raw_elevation_m")
    join_dist = point_series(rows, "elapsed_sec", "elevation_join_dist_m")
    supp_delta = point_series(rows, "elapsed_sec", "agg_supplement_delta_elevation_m")
    supp_slope = point_series(rows, "elapsed_sec", "agg_supplement_slope_pct")
    total_gain_line = point_series(rows, "elapsed_sec", "agg_total_gain_m")
    total_loss_line = point_series(rows, "elapsed_sec", "agg_total_loss_m")

    valid_supp_ele_pts = filter_points(rows, "elapsed_sec", "calibrated_elevation_m", lambda r: r.get("agg_supplement_step_valid") == "True")
    review_supp_ele_pts = filter_points(rows, "elapsed_sec", "calibrated_elevation_m", lambda r: r.get("agg_supplement_step_review_only") == "True")
    artifact_ele_pts = filter_points(rows, "elapsed_sec", "calibrated_elevation_m", lambda r: to_bool(r.get("elevation_artifact_flag")))
    join_hard_ele_pts = filter_points(rows, "elapsed_sec", "calibrated_elevation_m", lambda r: "ELEVATION_JOIN_DIST_GT_10M_HARD_EXCLUDED" in r.get("gain_loss_excluded_reason", ""))

    elevation_chart = build_chart_svg(
        title=f"{activity_id} v1k5 supplement markers on elevation",
        line_sets=[
            ("calibrated elevation", "#2563eb", cal_ele),
            ("raw elevation", "#9ca3af", raw_ele),
        ],
        marker_sets=[
            ("supplement valid step", "#16a34a", valid_supp_ele_pts),
            ("supplement review only", "#f97316", review_supp_ele_pts),
            ("elevation artifact", "#dc2626", artifact_ele_pts),
            ("join >10m hard excluded", "#7c3aed", join_hard_ele_pts),
        ],
        y_label="elevation_m",
        max_line_points=max_line_points,
        max_marker_points=max_marker_points,
    )

    delta_chart = build_chart_svg(
        title=f"{activity_id} v1k5 supplement delta elevation",
        line_sets=[
            ("supplement delta elevation", "#0891b2", supp_delta),
        ],
        marker_sets=[
            ("supplement valid step", "#16a34a", filter_points(rows, "elapsed_sec", "agg_supplement_delta_elevation_m", lambda r: r.get("agg_supplement_step_valid") == "True")),
            ("supplement review only", "#f97316", filter_points(rows, "elapsed_sec", "agg_supplement_delta_elevation_m", lambda r: r.get("agg_supplement_step_review_only") == "True")),
        ],
        y_label="delta_elevation_m",
        max_line_points=max_line_points,
        max_marker_points=max_marker_points,
    )

    slope_chart = build_chart_svg(
        title=f"{activity_id} v1k5 supplement slope",
        line_sets=[
            ("supplement slope", "#7c3aed", supp_slope),
        ],
        marker_sets=[
            ("supplement valid step", "#16a34a", filter_points(rows, "elapsed_sec", "agg_supplement_slope_pct", lambda r: r.get("agg_supplement_step_valid") == "True")),
            ("supplement review only", "#f97316", filter_points(rows, "elapsed_sec", "agg_supplement_slope_pct", lambda r: r.get("agg_supplement_step_review_only") == "True")),
        ],
        y_label="slope_pct",
        max_line_points=max_line_points,
        max_marker_points=max_marker_points,
    )

    gain_loss_chart = build_chart_svg(
        title=f"{activity_id} v1k5 total gain/loss timeline",
        line_sets=[
            ("agg total gain", "#16a34a", total_gain_line),
            ("agg total loss", "#dc2626", total_loss_line),
        ],
        marker_sets=[],
        y_label="meters",
        max_line_points=max_line_points,
        max_marker_points=max_marker_points,
    )

    join_chart = build_chart_svg(
        title=f"{activity_id} elevation join distance",
        line_sets=[
            ("join distance", "#f97316", join_dist),
        ],
        marker_sets=[
            ("join >10m hard excluded", "#dc2626", filter_points(rows, "elapsed_sec", "elevation_join_dist_m", lambda r: "ELEVATION_JOIN_DIST_GT_10M_HARD_EXCLUDED" in r.get("gain_loss_excluded_reason", ""))),
        ],
        y_label="join_dist_m",
        max_line_points=max_line_points,
        max_marker_points=max_marker_points,
    )

    supplement_cols = [
        "raw_point_index",
        "elapsed_sec",
        "route_class",
        "movement_state",
        "calibrated_elevation_m",
        "raw_elevation_m",
        "agg_supplement_step_valid",
        "agg_supplement_step_review_only",
        "agg_supplement_step_id",
        "agg_supplement_step_reason",
        "agg_supplement_duration_sec",
        "agg_supplement_horizontal_distance_m",
        "agg_supplement_delta_elevation_m",
        "agg_supplement_slope_pct",
        "agg_supplemental_gain_m",
        "agg_supplemental_loss_m",
        "agg_total_gain_m",
        "agg_total_loss_m",
    ]

    route_count_html = "".join(
        f"<li><code>{html.escape(k)}</code>: {v}</li>" for k, v in sorted(route_counts.items())
    )
    movement_count_html = "".join(
        f"<li><code>{html.escape(k)}</code>: {v}</li>" for k, v in movement_counts.most_common()
    )
    source_count_html = "".join(
        f"<li><code>{html.escape(k)}</code>: {v}</li>" for k, v in source_counts.most_common()
    )

    html_text = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(route_folder)} {html.escape(activity_id)} v1k5 supplement visual QA</title>
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
h1, h2 {{ margin: 0.2em 0; }}
.small {{ color: #6b7280; font-size: 13px; }}
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
<h1>{html.escape(route_folder)} / {html.escape(activity_id)} - v1k5 supplement visual QA</h1>
<div class="small">Input: <code>{html.escape(str(in_fp))}</code></div>
<div class="small">This report is read-only. v1k5 supplement-only totals preserve v1k3 baseline and add supplemental gain/loss only.</div>
</div>

<div class="card grid">
  <div class="metric"><div class="label">Rows</div><div class="value">{total_rows}</div></div>
  <div class="metric"><div class="label">Baseline gain/loss</div><div class="value">{html.escape(fmt(baseline_gain))} / {html.escape(fmt(baseline_loss))}</div></div>
  <div class="metric"><div class="label">Supplement gain/loss</div><div class="value">{html.escape(fmt(supplemental_gain))} / {html.escape(fmt(supplemental_loss))}</div></div>
  <div class="metric"><div class="label">Total gain/loss</div><div class="value">{html.escape(fmt(total_gain))} / {html.escape(fmt(total_loss))}</div></div>
  <div class="metric"><div class="label">Supplement candidates</div><div class="value">{len(candidate_supp_rows)}</div></div>
  <div class="metric"><div class="label">Supplement valid steps</div><div class="value">{len(valid_supp_rows)}</div></div>
  <div class="metric"><div class="label">Supplement review-only</div><div class="value">{len(review_supp_rows)}</div></div>
  <div class="metric"><div class="label">Profile jumps / artifacts</div><div class="value">{len(profile_jump_rows)} / {len(artifact_rows)}</div></div>
</div>

<div class="card">
<h2>Route-class counts</h2>
<ul>{route_count_html}</ul>
<h2>Movement-state counts</h2>
<ul>{movement_count_html}</ul>
<h2>Elevation-source counts</h2>
<ul>{source_count_html}</ul>
</div>

<div class="card">{elevation_chart}</div>
<div class="card">{delta_chart}</div>
<div class="card">{slope_chart}</div>
<div class="card">{gain_loss_chart}</div>
<div class="card">{join_chart}</div>

<div class="card">
<h2>Supplement step rows</h2>
<p class="small">Rows shown when a v1k5 supplement candidate step was finalized. Limited to first 80 rows.</p>
{html_table(candidate_supp_rows, supplement_cols, 80)}
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
        "baseline_v1k3_cumulative_gain_m": baseline_gain,
        "baseline_v1k3_cumulative_loss_m": baseline_loss,
        "supplemental_gain_m": supplemental_gain,
        "supplemental_loss_m": supplemental_loss,
        "agg_total_gain_m": total_gain,
        "agg_total_loss_m": total_loss,
        "supplement_candidate_steps": len(candidate_supp_rows),
        "supplement_valid_steps": len(valid_supp_rows),
        "supplement_review_only_steps": len(review_supp_rows),
        "elevation_artifact_rows": len(artifact_rows),
        "profile_dist_jump_rows": len(profile_jump_rows),
        "elevation_join_hard_excluded_rows": len(join_hard_rows),
        "route_class_counts": dict(route_counts),
        "movement_state_counts": dict(movement_counts),
        "elevation_source_counts": dict(source_counts),
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

    for activity_id in activity_ids:
        try:
            summary = process_activity(
                route_folder=route_folder,
                activity_id=activity_id,
                input_root=input_root,
                out_dir=out_dir,
                max_line_points=args.max_line_points,
                max_marker_points=args.max_marker_points,
            )
            summaries.append(summary)
            print(
                f"[PASS] {activity_id}: "
                f"rows={summary['rows']} "
                f"supp_steps={summary['supplement_valid_steps']} "
                f"review_steps={summary['supplement_review_only_steps']} "
                f"base={summary['baseline_v1k3_cumulative_gain_m']}/{summary['baseline_v1k3_cumulative_loss_m']} "
                f"supp={summary['supplemental_gain_m']}/{summary['supplemental_loss_m']} "
                f"html={summary['output_html']}"
            )
        except Exception as exc:
            fail_n += 1
            summary = {
                "activity_id": activity_id,
                "status": "FAIL",
                "rows": 0,
                "input_csv": "",
                "output_html": "",
                "baseline_v1k3_cumulative_gain_m": "",
                "baseline_v1k3_cumulative_loss_m": "",
                "supplemental_gain_m": "",
                "supplemental_loss_m": "",
                "agg_total_gain_m": "",
                "agg_total_loss_m": "",
                "supplement_candidate_steps": "",
                "supplement_valid_steps": "",
                "supplement_review_only_steps": "",
                "elevation_artifact_rows": "",
                "profile_dist_jump_rows": "",
                "elevation_join_hard_excluded_rows": "",
                "route_class_counts": {},
                "movement_state_counts": {},
                "elevation_source_counts": {},
                "error": str(exc),
            }
            summaries.append(summary)
            print(f"[FAIL] {activity_id}: {exc}")

    batch_dir = out_dir / "_batch_summary"
    batch_dir.mkdir(parents=True, exist_ok=True)
    batch_csv = batch_dir / f"{route_folder}_v1k5_elevation_visual_qa_summary.csv"
    batch_json = batch_dir / f"{route_folder}_v1k5_elevation_visual_qa_summary.json"

    csv_rows: List[Dict[str, Any]] = []
    for s in summaries:
        row = dict(s)
        row["route_class_counts"] = json.dumps(row.get("route_class_counts", {}), ensure_ascii=False)
        row["movement_state_counts"] = json.dumps(row.get("movement_state_counts", {}), ensure_ascii=False)
        row["elevation_source_counts"] = json.dumps(row.get("elevation_source_counts", {}), ensure_ascii=False)
        csv_rows.append(row)

    fieldnames = list(csv_rows[0].keys()) if csv_rows else []
    write_csv(batch_csv, csv_rows, fieldnames)
    batch_json.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"summary_csv={batch_csv}")
    print(f"summary_json={batch_json}")
    print("status=PASS" if fail_n == 0 else f"status=FAIL fail_n={fail_n}")

    return 0 if fail_n == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
