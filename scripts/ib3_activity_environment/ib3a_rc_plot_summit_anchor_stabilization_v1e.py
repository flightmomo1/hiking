#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IB3A-RC v1e summit anchor stabilization QA HTML.

Review-only visual QA:
- Reads *_candidate_point_summit_anchor_stabilized.csv
- Draws raw GPS points
- Highlights anchor_stabilized_flag=True points
- Draws summit anchor / refit point
- Does NOT modify any upstream or CSV outputs.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path
from typing import Any


def to_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y", "t"}


def read_csv_rows(fp: Path) -> list[dict[str, str]]:
    if not fp.exists():
        raise FileNotFoundError(fp)
    with fp.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def project_points(rows: list[dict[str, str]], width: int = 1000, height: int = 760, pad: int = 50):
    pts = []
    for r in rows:
        lat = to_float(r.get("lat"))
        lon = to_float(r.get("lon"))
        if lat is None or lon is None:
            continue
        pts.append((lat, lon))

    refit_pts = []
    for r in rows:
        if not parse_bool(r.get("anchor_stabilized_flag", "")):
            continue
        lat = to_float(r.get("anchor_refit_lat"))
        lon = to_float(r.get("anchor_refit_lon"))
        if lat is not None and lon is not None:
            refit_pts.append((lat, lon))

    all_pts = pts + refit_pts
    if not all_pts:
        raise ValueError("No valid lat/lon points.")

    min_lat = min(p[0] for p in all_pts)
    max_lat = max(p[0] for p in all_pts)
    min_lon = min(p[1] for p in all_pts)
    max_lon = max(p[1] for p in all_pts)

    if max_lat == min_lat:
        max_lat += 0.00001
        min_lat -= 0.00001
    if max_lon == min_lon:
        max_lon += 0.00001
        min_lon -= 0.00001

    def xy(lat: float, lon: float) -> tuple[float, float]:
        x = pad + (lon - min_lon) / (max_lon - min_lon) * (width - pad * 2)
        y = height - pad - (lat - min_lat) / (max_lat - min_lat) * (height - pad * 2)
        return x, y

    return xy, {
        "min_lat": min_lat,
        "max_lat": max_lat,
        "min_lon": min_lon,
        "max_lon": max_lon,
        "width": width,
        "height": height,
        "pad": pad,
    }


def polyline_svg(points: list[tuple[float, float]], stroke: str, width: float, opacity: float = 1.0, dash: str = "") -> str:
    if len(points) < 2:
        return ""
    d = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<polyline points="{d}" fill="none" stroke="{stroke}" stroke-width="{width}" opacity="{opacity}"{dash_attr}/>'


def main() -> int:
    parser = argparse.ArgumentParser(description="Plot IB3A-RC v1e summit anchor stabilization QA HTML.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--summary-json", required=False)
    parser.add_argument("--activity-id", required=True)
    parser.add_argument("--route-folder", required=True)
    parser.add_argument("--out-html", required=True)
    args = parser.parse_args()

    input_csv = Path(args.input_csv)
    rows = read_csv_rows(input_csv)

    summary = {}
    if args.summary_json and Path(args.summary_json).exists():
        summary = json.loads(Path(args.summary_json).read_text(encoding="utf-8"))

    xy, bounds = project_points(rows)

    raw_points = []
    stabilized_points = []
    unstabilized_near_points = []
    refit_points = []

    for r in rows:
        lat = to_float(r.get("lat"))
        lon = to_float(r.get("lon"))
        if lat is None or lon is None:
            continue

        x, y = xy(lat, lon)
        raw_points.append((x, y))

        dist = to_float(r.get("anchor_distance_m"))
        is_stab = parse_bool(r.get("anchor_stabilized_flag", ""))

        if is_stab:
            stabilized_points.append((x, y, r))
            refit_lat = to_float(r.get("anchor_refit_lat"))
            refit_lon = to_float(r.get("anchor_refit_lon"))
            if refit_lat is not None and refit_lon is not None:
                refit_points.append((*xy(refit_lat, refit_lon), r))
        elif dist is not None and dist <= 50:
            unstabilized_near_points.append((x, y, r))

    # one refit/anchor point is enough for display
    anchor_x = anchor_y = None
    anchor_name = ""
    anchor_way = ""
    if refit_points:
        anchor_x, anchor_y, rr = refit_points[0]
        anchor_name = rr.get("anchor_name", "")
        anchor_way = rr.get("anchor_refit_osm_way_id", "")

    # summary values
    stab_count = len(stabilized_points)
    raw_count = len(raw_points)
    near_count = stab_count + len(unstabilized_near_points)

    elapsed_vals = [to_float(r.get("elapsed_sec")) for _, _, r in stabilized_points]
    elapsed_vals = [v for v in elapsed_vals if v is not None]
    dist_vals = [to_float(r.get("anchor_distance_m")) for _, _, r in stabilized_points]
    dist_vals = [v for v in dist_vals if v is not None]

    def fmt(v):
        return "" if v is None else f"{v:.3f}"

    elapsed_min = min(elapsed_vals) if elapsed_vals else None
    elapsed_max = max(elapsed_vals) if elapsed_vals else None
    dist_min = min(dist_vals) if dist_vals else None
    dist_max = max(dist_vals) if dist_vals else None
    dist_avg = sum(dist_vals) / len(dist_vals) if dist_vals else None

    context_counts = {}
    policy_counts = {}
    for _, _, r in stabilized_points:
        context_counts[r.get("candidate_context", "")] = context_counts.get(r.get("candidate_context", ""), 0) + 1
        policy_counts[r.get("training_use_policy", "")] = policy_counts.get(r.get("training_use_policy", ""), 0) + 1

    raw_svg = polyline_svg(raw_points, "#444444", 1.3, 0.7)

    near_circles = []
    for x, y, r in unstabilized_near_points:
        near_circles.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.0" fill="#9ca3af" opacity="0.55"><title>near summit but not stabilized elapsed={html.escape(r.get("elapsed_sec",""))} dist={html.escape(r.get("anchor_distance_m",""))}</title></circle>')

    stab_circles = []
    for x, y, r in stabilized_points:
        title = (
            f"SUMMIT_STAY_DRIFT\\n"
            f"idx={r.get('raw_point_index','')} elapsed={r.get('elapsed_sec','')}\\n"
            f"dist={r.get('anchor_distance_m','')}m\\n"
            f"context={r.get('candidate_context','')}\\n"
            f"policy={r.get('training_use_policy','')}\\n"
            f"refit_way={r.get('anchor_refit_osm_way_id','')}"
        )
        stab_circles.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="#e11d48" opacity="0.85"><title>{html.escape(title)}</title></circle>')

    anchor_svg = ""
    if anchor_x is not None and anchor_y is not None:
        anchor_svg = f'''
        <circle cx="{anchor_x:.1f}" cy="{anchor_y:.1f}" r="9" fill="#facc15" stroke="#111827" stroke-width="2"/>
        <text x="{anchor_x + 12:.1f}" y="{anchor_y - 12:.1f}" font-size="14" font-weight="bold" fill="#111827">
          {html.escape(anchor_name)} anchor / way {html.escape(anchor_way)}
        </text>
        '''

    summary_rows = f"""
    <tr><th>activity_id</th><td>{html.escape(args.activity_id)}</td></tr>
    <tr><th>raw points drawn</th><td>{raw_count}</td></tr>
    <tr><th>near summit rows (&lt;=50m)</th><td>{near_count}</td></tr>
    <tr><th>anchor_stabilized rows</th><td>{stab_count}</td></tr>
    <tr><th>elapsed range</th><td>{fmt(elapsed_min)} – {fmt(elapsed_max)} sec</td></tr>
    <tr><th>duration</th><td>{fmt((elapsed_max - elapsed_min) if elapsed_min is not None and elapsed_max is not None else None)} sec</td></tr>
    <tr><th>anchor distance min/max/avg</th><td>{fmt(dist_min)} / {fmt(dist_max)} / {fmt(dist_avg)} m</td></tr>
    <tr><th>anchor refit way</th><td>{html.escape(anchor_way)}</td></tr>
    <tr><th>context counts</th><td>{html.escape(str(context_counts))}</td></tr>
    <tr><th>policy counts</th><td>{html.escape(str(policy_counts))}</td></tr>
    """

    html_text = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8"/>
<title>IB3A-RC v1e Summit Anchor QA - {html.escape(args.activity_id)}</title>
<style>
body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; color: #111827; }}
h1 {{ margin-bottom: 4px; }}
.note {{ color: #4b5563; margin-bottom: 16px; }}
.legend span {{ display: inline-block; margin-right: 18px; }}
.box {{ border: 1px solid #d1d5db; border-radius: 10px; padding: 14px; margin: 16px 0; }}
table {{ border-collapse: collapse; font-size: 14px; }}
th, td {{ border: 1px solid #d1d5db; padding: 6px 10px; text-align: left; }}
th {{ background: #f3f4f6; }}
svg {{ background: #f9fafb; border: 1px solid #d1d5db; border-radius: 10px; }}
code {{ background: #f3f4f6; padding: 2px 4px; border-radius: 4px; }}
</style>
</head>
<body>
<h1>IB3A-RC v1e Summit Anchor Stabilization QA - {html.escape(args.activity_id)}</h1>
<div class="note">
Review-only visualization. This does not modify candidate_context, training_use_policy, usable_on_route, or upstream outputs.
</div>

<div class="box">
<h2>What to check</h2>
<ol>
<li>Dark gray raw GPS should remain intact.</li>
<li>Red points should cluster only around the summit stay / drift area.</li>
<li>Yellow anchor should be at the summit target.</li>
<li>Red points should be stabilized to <code>summit_stay_drift</code>, not interpreted as route-choice changes.</li>
</ol>
</div>

<div class="box legend">
<h2>Legend</h2>
<span><svg width="16" height="10"><line x1="0" y1="5" x2="16" y2="5" stroke="#444" stroke-width="2"/></svg> raw GPS</span>
<span><svg width="16" height="10"><circle cx="8" cy="5" r="4" fill="#9ca3af"/></svg> near summit, not stabilized</span>
<span><svg width="16" height="10"><circle cx="8" cy="5" r="4" fill="#e11d48"/></svg> summit_stay_drift stabilized</span>
<span><svg width="16" height="10"><circle cx="8" cy="5" r="5" fill="#facc15" stroke="#111827"/></svg> summit anchor / refit point</span>
</div>

<div class="box">
<h2>Summit anchor view</h2>
<svg width="{bounds['width']}" height="{bounds['height']}" viewBox="0 0 {bounds['width']} {bounds['height']}">
{raw_svg}
{''.join(near_circles)}
{''.join(stab_circles)}
{anchor_svg}
</svg>
</div>

<div class="box">
<h2>Summary</h2>
<table>
{summary_rows}
</table>
</div>

<div class="box">
<h2>Files</h2>
<p>Input CSV: <code>{html.escape(str(input_csv))}</code></p>
<p>Summary JSON: <code>{html.escape(str(args.summary_json or ""))}</code></p>
</div>
</body>
</html>
"""

    out_html = Path(args.out_html)
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(html_text, encoding="utf-8")

    print(f"wrote: {out_html}")
    print(f"anchor_stabilized_rows: {stab_count}")
    print(f"anchor_way: {anchor_way}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
