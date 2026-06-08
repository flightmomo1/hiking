#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IB3A-RC v1k2 calibrated motion QA HTML plot.

Display-only QA script:
- Reads v1k2 calibrated motion CSV.
- Produces HTML with speed timeline, movement states, route class/source markers,
  GPS drift, speed outliers, distance jumps, and raw-vs-calibrated distance summary.
- Does NOT modify upstream outputs.
- Uses Python standard library only.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median


def to_float(v, default=None):
    try:
        if v is None:
            return default
        s = str(v).strip()
        if s == "":
            return default
        x = float(s)
        if math.isnan(x):
            return default
        return x
    except Exception:
        return default


def truth(v) -> bool:
    return str(v).strip().lower() in {"true", "1", "yes", "y", "t"}


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        return list(r), list(r.fieldnames or [])


def pct(values, q):
    vals = sorted([v for v in values if v is not None and not math.isnan(v)])
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return vals[lo]
    return vals[lo] * (hi - pos) + vals[hi] * (pos - lo)


def fmt_num(v, digits=3, suffix=""):
    if v is None:
        return ""
    try:
        return f"{float(v):,.{digits}f}{suffix}"
    except Exception:
        return html.escape(str(v))


def esc(v):
    return html.escape("" if v is None else str(v))


def color_for(value: str) -> str:
    palette = {
        "MOVING": "#2e7d32",
        "SLOW_MOVING": "#8bc34a",
        "STOPPED": "#1565c0",
        "GPS_DRIFT_SUSPECTED": "#d32f2f",
        "LOW_CONFIDENCE_REVIEW": "#f9a825",
        "UNKNOWN_REVIEW": "#6d4c41",
        "WRONG_ROUTE_MOVING": "#c2185b",
        "OFF_TARGET_MOVING": "#ef6c00",
        "TIME_INVALID": "#424242",
        "DUPLICATE_TIMESTAMP_NON_REPRESENTATIVE": "#bdbdbd",
        "MAINLINE_CORE": "#2e7d32",
        "MAINLINE_SUMMIT_STAY": "#1976d2",
        "CONNECTOR": "#00897b",
        "WRONG_ROUTE": "#c2185b",
        "OFF_TARGET": "#ef6c00",
        "OSM_MAINLINE_CANDIDATE_PROJECTION": "#2e7d32",
        "REVIEWED_SUMMIT_ANCHOR": "#1976d2",
        "OSM_CONNECTOR_PROJECTION": "#00897b",
        "OSM_WRONG_ROUTE_CANDIDATE_PROJECTION": "#c2185b",
        "RAW_GPS_FALLBACK": "#ef6c00",
    }
    return palette.get(str(value), "#757575")


def make_summary(rows):
    speeds = [to_float(r.get("calibrated_speed_mps")) for r in rows]
    speeds = [v for v in speeds if v is not None]
    total_rows = len(rows)
    rep_rows = sum(truth(r.get("motion_representative_flag")) for r in rows)
    nonrep_rows = sum(r.get("duplicate_group_motion_role") == "non_representative" for r in rows)
    speed_outliers = sum((to_float(r.get("calibrated_speed_mps")) or 0) > 5 for r in rows)
    drift_rows = sum(truth(r.get("gps_drift_suspected")) for r in rows)
    dist_jumps = sum((to_float(r.get("calibrated_step_distance_m")) or 0) > 20 for r in rows)
    time_invalid = sum(r.get("movement_state") == "TIME_INVALID" for r in rows)

    last_cal = None
    for r in rows:
        v = to_float(r.get("calibrated_horizontal_distance_m"))
        if v is not None:
            last_cal = v

    raw_vals = [to_float(r.get("raw_distance_m")) for r in rows if to_float(r.get("raw_distance_m")) is not None]
    raw_delta = None
    if raw_vals:
        raw_delta = max(raw_vals) - min(raw_vals)

    ratio = None
    if raw_delta is not None and last_cal not in (None, 0):
        ratio = raw_delta / last_cal

    return {
        "total_rows": total_rows,
        "representative_rows": rep_rows,
        "non_representative_rows": nonrep_rows,
        "calibrated_distance_m": last_cal,
        "raw_distance_delta_m": raw_delta,
        "raw_calibrated_ratio": ratio,
        "speed_p50": pct(speeds, 0.50),
        "speed_p95": pct(speeds, 0.95),
        "speed_p99": pct(speeds, 0.99),
        "speed_max": max(speeds) if speeds else None,
        "speed_outlier_rows_gt5": speed_outliers,
        "gps_drift_rows": drift_rows,
        "distance_jump_rows_gt20": dist_jumps,
        "time_invalid_rows": time_invalid,
    }


def counter_table(title, counter: Counter):
    rows = "".join(
        f"<tr><td>{esc(k)}</td><td class='num'>{v:,}</td></tr>"
        for k, v in counter.most_common()
    )
    return f"""
    <h3>{esc(title)}</h3>
    <table>
      <tr><th>Value</th><th>Rows</th></tr>
      {rows}
    </table>
    """


def build_speed_svg(rows, width=1200, height=280):
    reps = [r for r in rows if truth(r.get("motion_representative_flag"))]
    pts = []
    for r in reps:
        x = to_float(r.get("elapsed_sec"))
        y = to_float(r.get("calibrated_speed_mps"))
        if x is not None and y is not None:
            pts.append((x, y, r))

    if not pts:
        return "<p>No valid speed points.</p>"

    min_x = min(p[0] for p in pts)
    max_x = max(p[0] for p in pts)
    if max_x <= min_x:
        max_x = min_x + 1

    speed_vals = [p[1] for p in pts]
    y_cap = max(1.0, min(max(speed_vals), max(6.0, (pct(speed_vals, 0.99) or 1.0) * 1.2)))
    left, right, top, bottom = 55, 20, 20, 35
    plot_w = width - left - right
    plot_h = height - top - bottom

    def sx(t):
        return left + (t - min_x) / (max_x - min_x) * plot_w

    def sy(v):
        vv = max(0.0, min(v, y_cap))
        return top + (1.0 - vv / y_cap) * plot_h

    # line path
    points = " ".join(f"{sx(t):.1f},{sy(v):.1f}" for t, v, _ in pts)

    # outlier/drift dots
    dots = []
    for t, v, r in pts:
        cls_color = "#d32f2f" if v > 5 or truth(r.get("gps_drift_suspected")) else color_for(r.get("movement_state"))
        radius = 3.5 if v > 5 or truth(r.get("gps_drift_suspected")) else 1.8
        label = (
            f"elapsed={t}, speed={v:.3f}, state={r.get('movement_state')}, "
            f"route={r.get('route_class')}, source={r.get('horizontal_calibration_source')}, "
            f"step={r.get('calibrated_step_distance_m')}, drift={r.get('gps_drift_suspected')}"
        )
        dots.append(
            f"<circle cx='{sx(t):.1f}' cy='{sy(v):.1f}' r='{radius}' fill='{cls_color}'>"
            f"<title>{esc(label)}</title></circle>"
        )

    # horizontal reference lines
    grid = []
    for val in [0.1, 0.35, 5.0]:
        if val <= y_cap:
            y = sy(val)
            grid.append(f"<line x1='{left}' x2='{width-right}' y1='{y:.1f}' y2='{y:.1f}' stroke='#999' stroke-dasharray='4 4'/>")
            grid.append(f"<text x='5' y='{y+4:.1f}' font-size='11'>{val} m/s</text>")

    return f"""
    <h3>Calibrated speed timeline</h3>
    <svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">
      <rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/>
      <line x1="{left}" x2="{width-right}" y1="{height-bottom}" y2="{height-bottom}" stroke="#333"/>
      <line x1="{left}" x2="{left}" y1="{top}" y2="{height-bottom}" stroke="#333"/>
      {''.join(grid)}
      <polyline fill="none" stroke="#444" stroke-width="1.2" points="{points}"/>
      {''.join(dots)}
      <text x="{left}" y="{height-8}" font-size="11">elapsed_sec {min_x:.0f} → {max_x:.0f}</text>
      <text x="{width-170}" y="14" font-size="11">y cap = {y_cap:.2f} m/s</text>
    </svg>
    """


def build_lane_svg(rows, field, title, width=1200, lane_h=22):
    reps = [r for r in rows if truth(r.get("motion_representative_flag"))]
    if not reps:
        return f"<h3>{esc(title)}</h3><p>No representative rows.</p>"

    xs = [to_float(r.get("elapsed_sec")) for r in reps if to_float(r.get("elapsed_sec")) is not None]
    if not xs:
        return f"<h3>{esc(title)}</h3><p>No elapsed_sec.</p>"

    min_x, max_x = min(xs), max(xs)
    if max_x <= min_x:
        max_x = min_x + 1

    values = []
    seen = set()
    for r in reps:
        v = r.get(field, "")
        if v not in seen:
            seen.add(v)
            values.append(v)

    left, right = 210, 20
    top = 20
    height = top + lane_h * len(values) + 25
    plot_w = width - left - right

    def sx(t):
        return left + (t - min_x) / (max_x - min_x) * plot_w

    val_to_y = {v: top + i * lane_h for i, v in enumerate(values)}

    rects = []
    for r in reps:
        t = to_float(r.get("elapsed_sec"))
        if t is None:
            continue
        v = r.get(field, "")
        y = val_to_y.get(v, top)
        color = color_for(v)
        w = 2.0
        label = f"elapsed={t}, {field}={v}, route={r.get('route_class')}, source={r.get('horizontal_calibration_source')}, state={r.get('movement_state')}"
        rects.append(f"<rect x='{sx(t):.1f}' y='{y:.1f}' width='{w}' height='{lane_h-4}' fill='{color}'><title>{esc(label)}</title></rect>")

    labels = []
    for v, y in val_to_y.items():
        labels.append(f"<text x='5' y='{y+14:.1f}' font-size='11'>{esc(v)}</text>")

    return f"""
    <h3>{esc(title)}</h3>
    <svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">
      <rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/>
      {''.join(labels)}
      {''.join(rects)}
      <line x1="{left}" x2="{width-right}" y1="{height-18}" y2="{height-18}" stroke="#333"/>
    </svg>
    """


def build_distance_svg(rows, width=1200, height=260):
    reps = [r for r in rows if truth(r.get("motion_representative_flag"))]
    pts = []
    raw_pts = []
    for r in reps:
        t = to_float(r.get("elapsed_sec"))
        cal = to_float(r.get("calibrated_horizontal_distance_m"))
        raw = to_float(r.get("raw_distance_m"))
        if t is not None and cal is not None:
            pts.append((t, cal))
        if t is not None and raw is not None:
            raw_pts.append((t, raw))

    if not pts:
        return "<p>No distance points.</p>"

    min_x = min(t for t, _ in pts)
    max_x = max(t for t, _ in pts)
    if max_x <= min_x:
        max_x = min_x + 1

    raw_base = raw_pts[0][1] if raw_pts else 0.0
    raw_norm = [(t, v - raw_base) for t, v in raw_pts]
    max_y = max([v for _, v in pts] + [v for _, v in raw_norm]) or 1.0

    left, right, top, bottom = 55, 20, 20, 35
    plot_w = width - left - right
    plot_h = height - top - bottom

    def sx(t):
        return left + (t - min_x) / (max_x - min_x) * plot_w

    def sy(v):
        return top + (1.0 - v / max_y) * plot_h

    cal_points = " ".join(f"{sx(t):.1f},{sy(v):.1f}" for t, v in pts)
    raw_points = " ".join(f"{sx(t):.1f},{sy(v):.1f}" for t, v in raw_norm)

    return f"""
    <h3>Raw vs calibrated cumulative distance</h3>
    <svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">
      <rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/>
      <line x1="{left}" x2="{width-right}" y1="{height-bottom}" y2="{height-bottom}" stroke="#333"/>
      <line x1="{left}" x2="{left}" y1="{top}" y2="{height-bottom}" stroke="#333"/>
      <polyline fill="none" stroke="#1565c0" stroke-width="1.5" points="{cal_points}"/>
      <polyline fill="none" stroke="#ef6c00" stroke-width="1.2" stroke-dasharray="5 4" points="{raw_points}"/>
      <text x="{left+10}" y="16" font-size="12" fill="#1565c0">calibrated_horizontal_distance_m</text>
      <text x="{left+290}" y="16" font-size="12" fill="#ef6c00">raw_distance_m normalized</text>
      <text x="5" y="{top+5}" font-size="11">{max_y:.0f} m</text>
    </svg>
    """


def build_event_table(rows, title, predicate, limit=60):
    selected = [r for r in rows if predicate(r)]
    if not selected:
        return f"<h3>{esc(title)}</h3><p>None.</p>"

    body = []
    for r in selected[:limit]:
        body.append(
            "<tr>"
            f"<td>{esc(r.get('raw_point_index'))}</td>"
            f"<td>{esc(r.get('elapsed_sec'))}</td>"
            f"<td>{esc(r.get('calibrated_speed_mps'))}</td>"
            f"<td>{esc(r.get('calibrated_step_distance_m'))}</td>"
            f"<td>{esc(r.get('movement_state'))}</td>"
            f"<td>{esc(r.get('route_class'))}</td>"
            f"<td>{esc(r.get('horizontal_calibration_source'))}</td>"
            f"<td>{esc(r.get('gps_drift_reason'))}</td>"
            "</tr>"
        )

    return f"""
    <h3>{esc(title)} ({len(selected):,} rows, first {min(limit, len(selected))})</h3>
    <table>
      <tr>
        <th>raw_point_index</th><th>elapsed_sec</th><th>speed</th><th>step_m</th>
        <th>movement_state</th><th>route_class</th><th>source</th><th>reason</th>
      </tr>
      {''.join(body)}
    </table>
    """


def render_html(route, activity_id, rows, fields, out_html: Path):
    summary = make_summary(rows)
    movement_counts = Counter(r.get("movement_state", "") for r in rows)
    route_counts = Counter(r.get("route_class", "") for r in rows)
    source_counts = Counter(r.get("horizontal_calibration_source", "") for r in rows)
    role_counts = Counter(r.get("duplicate_group_motion_role", "") for r in rows)

    summary_rows = "".join(
        f"<tr><td>{esc(k)}</td><td class='num'>{fmt_num(v, 3)}</td></tr>"
        for k, v in summary.items()
    )

    html_text = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>v1k2 motion QA - {esc(route)} {esc(activity_id)}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; line-height: 1.35; }}
table {{ border-collapse: collapse; margin: 12px 0 24px 0; font-size: 13px; }}
th, td {{ border: 1px solid #ccc; padding: 4px 7px; vertical-align: top; }}
th {{ background: #f2f2f2; }}
.num {{ text-align: right; font-family: Consolas, monospace; }}
code {{ background: #f5f5f5; padding: 1px 4px; }}
.section {{ margin-top: 28px; }}
.warning {{ background: #fff8e1; border-left: 4px solid #f9a825; padding: 8px 12px; }}
</style>
</head>
<body>
<h1>IB3A-RC v1k2 calibrated motion QA</h1>
<p><b>Route:</b> {esc(route)}<br/>
<b>Activity:</b> {esc(activity_id)}</p>

<div class="warning">
This is a QA visualization only. It does not modify v1k2 outputs.
Non-representative duplicate timestamp rows are retained but should not produce speed.
</div>

<h2>Summary</h2>
<table>
<tr><th>Metric</th><th>Value</th></tr>
{summary_rows}
</table>

{counter_table("Movement state counts", movement_counts)}
{counter_table("Route class counts", route_counts)}
{counter_table("Horizontal source counts", source_counts)}
{counter_table("Duplicate group motion role counts", role_counts)}

<div class="section">
{build_speed_svg(rows)}
</div>

<div class="section">
{build_distance_svg(rows)}
</div>

<div class="section">
{build_lane_svg(rows, "movement_state", "Movement state timeline")}
</div>

<div class="section">
{build_lane_svg(rows, "route_class", "Route class timeline")}
</div>

<div class="section">
{build_lane_svg(rows, "horizontal_calibration_source", "Horizontal calibration source timeline")}
</div>

<div class="section">
{build_event_table(rows, "Speed outliers > 5 m/s", lambda r: (to_float(r.get("calibrated_speed_mps")) or 0) > 5)}
</div>

<div class="section">
{build_event_table(rows, "Distance jumps > 20 m", lambda r: (to_float(r.get("calibrated_step_distance_m")) or 0) > 20)}
</div>

<div class="section">
{build_event_table(rows, "GPS drift suspected", lambda r: truth(r.get("gps_drift_suspected")))}
</div>

</body>
</html>
"""
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(html_text, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--route-folder", required=True)
    ap.add_argument("--activity-ids", required=True, help="Comma-separated activity IDs")
    ap.add_argument("--input-root", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    route = args.route_folder
    ids = [x.strip() for x in args.activity_ids.split(",") if x.strip()]
    root = Path(args.input_root)
    out_dir = Path(args.out_dir)

    batch_rows = []
    failed = []

    for aid in ids:
        csv_path = root / route / aid / f"{route}_{aid}_calibrated_motion_v1k2.csv"
        if not csv_path.exists():
            print(f"[MISSING] {aid}: {csv_path}")
            failed.append((aid, "missing input"))
            continue

        rows, fields = read_csv(csv_path)
        html_path = out_dir / route / aid / f"{route}_{aid}_calibrated_motion_v1k2_qa.html"
        render_html(route, aid, rows, fields, html_path)

        s = make_summary(rows)
        batch_rows.append({
            "activity_id": aid,
            "rows": len(rows),
            "qa_html": str(html_path),
            **s,
        })
        print(f"[PASS] {aid}: {html_path}")

    summary_dir = out_dir / "_batch_summary"
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_csv = summary_dir / f"{route}_v1k2_motion_qa_html_summary.csv"

    if batch_rows:
        fieldnames = list(batch_rows[0].keys())
        with summary_csv.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(batch_rows)

    summary_json = summary_dir / f"{route}_v1k2_motion_qa_html_summary.json"
    summary_json.write_text(
        json.dumps(
            {
                "route_folder": route,
                "activities": batch_rows,
                "failed": failed,
                "status": "PASS" if not failed else "FAIL",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"summary_csv={summary_csv}")
    print(f"summary_json={summary_json}")
    print(f"status={'PASS' if not failed else 'FAIL'}")


if __name__ == "__main__":
    main()
