#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IB3A-RC v1g2 off-target zone QA HTML.

Review-only visual QA:
- Reads v1g point-level target-route labels
- Reads v1g2 consolidated off-target zones
- Draws raw GPS points and highlights off-target zones
- Does NOT modify upstream CSVs or labels.
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


def project_points(rows: list[dict[str, str]], width: int = 1100, height: int = 820, pad: int = 50):
    pts = []
    for r in rows:
        lat = to_float(r.get("lat"))
        lon = to_float(r.get("lon"))
        if lat is not None and lon is not None:
            pts.append((lat, lon))

    if not pts:
        raise ValueError("No valid lat/lon points.")

    min_lat = min(p[0] for p in pts)
    max_lat = max(p[0] for p in pts)
    min_lon = min(p[1] for p in pts)
    max_lon = max(p[1] for p in pts)

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

    return xy, {"width": width, "height": height}


def polyline_svg(points: list[tuple[float, float]], stroke: str, width: float, opacity: float = 1.0) -> str:
    if len(points) < 2:
        return ""
    d = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polyline points="{d}" fill="none" stroke="{stroke}" stroke-width="{width}" opacity="{opacity}"/>'


def zone_for_elapsed(zones: list[dict[str, str]], elapsed_sec: float) -> dict[str, str] | None:
    for z in zones:
        start = to_float(z.get("start_elapsed_sec"))
        end = to_float(z.get("end_elapsed_sec"))
        if start is None or end is None:
            continue
        if start <= elapsed_sec <= end:
            return z
    return None


def color_for_point(row: dict[str, str], zone: dict[str, str] | None) -> str:
    status = row.get("target_route_status", "")
    zone_type = zone.get("zone_type", "") if zone else ""

    if zone_type == "OFF_TARGET_APPROACH_LOWCONF_ZONE":
        return "#ef4444"  # red
    if zone_type == "OFF_TARGET_APPROACH_OR_SERVICE_ZONE":
        return "#f97316"  # orange
    if zone_type == "OFF_TARGET_BRANCH_ZONE":
        return "#a855f7"  # purple

    if status == "ON_TARGET_SUMMIT_STAY":
        return "#facc15"  # yellow
    if status == "ON_TARGET_CONNECTOR":
        return "#06b6d4"  # cyan
    if status == "ON_TARGET_ROUTE":
        return "#374151"  # dark gray

    if status.startswith("OFF_"):
        return "#dc2626"

    return "#6b7280"


def main() -> int:
    parser = argparse.ArgumentParser(description="Plot IB3A-RC v1g2 off-target zone QA HTML.")
    parser.add_argument("--route-folder", required=True)
    parser.add_argument("--activity-id", required=True)
    parser.add_argument("--point-csv", required=True)
    parser.add_argument("--zone-csv", required=True)
    parser.add_argument("--summary-json", required=False)
    parser.add_argument("--out-html", required=True)
    args = parser.parse_args()

    point_csv = Path(args.point_csv)
    zone_csv = Path(args.zone_csv)
    out_html = Path(args.out_html)

    points = read_csv_rows(point_csv)
    zones = read_csv_rows(zone_csv)

    summary = {}
    if args.summary_json and Path(args.summary_json).exists():
        summary = json.loads(Path(args.summary_json).read_text(encoding="utf-8"))

    xy, bounds = project_points(points)

    raw_xy = []
    circles = []
    status_counts: dict[str, int] = {}
    zone_point_counts: dict[str, int] = {}

    for r in points:
        lat = to_float(r.get("lat"))
        lon = to_float(r.get("lon"))
        elapsed = to_float(r.get("elapsed_sec"))
        if lat is None or lon is None or elapsed is None:
            continue

        x, y = xy(lat, lon)
        raw_xy.append((x, y))

        zone = zone_for_elapsed(zones, elapsed)
        status = r.get("target_route_status", "")
        zone_type = zone.get("zone_type", "") if zone else ""

        status_counts[status] = status_counts.get(status, 0) + 1
        if zone_type:
            zone_point_counts[zone_type] = zone_point_counts.get(zone_type, 0) + 1

        color = color_for_point(r, zone)

        radius = 2.0
        opacity = 0.45
        if zone:
            radius = 3.0
            opacity = 0.82
        elif status == "ON_TARGET_SUMMIT_STAY":
            radius = 2.8
            opacity = 0.85
        elif status == "ON_TARGET_CONNECTOR":
            radius = 2.6
            opacity = 0.75

        title = (
            f"elapsed={r.get('elapsed_sec','')}\\n"
            f"status={status}\\n"
            f"label={r.get('target_route_label','')}\\n"
            f"episode={r.get('target_route_episode_id','')}\\n"
            f"zone={zone.get('zone_id','') if zone else ''}\\n"
            f"zone_type={zone_type}\\n"
            f"context={r.get('candidate_context','')}\\n"
            f"transition={r.get('transition_type','')}\\n"
            f"dist={r.get('nearest_distance_m','')}"
        )

        circles.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{color}" opacity="{opacity}">'
            f'<title>{html.escape(title)}</title></circle>'
        )

    raw_line = polyline_svg(raw_xy, "#111827", 1.0, 0.38)

    zone_rows_html = []
    for z in zones:
        zone_type = z.get("zone_type", "")
        color = {
            "OFF_TARGET_APPROACH_LOWCONF_ZONE": "#ef4444",
            "OFF_TARGET_APPROACH_OR_SERVICE_ZONE": "#f97316",
            "OFF_TARGET_BRANCH_ZONE": "#a855f7",
        }.get(zone_type, "#6b7280")

        zone_rows_html.append(
            "<tr>"
            f"<td>{html.escape(z.get('zone_id',''))}</td>"
            f"<td><span style='display:inline-block;width:10px;height:10px;background:{color};border-radius:50%;'></span> {html.escape(zone_type)}</td>"
            f"<td>{html.escape(z.get('start_elapsed_sec',''))}–{html.escape(z.get('end_elapsed_sec',''))}</td>"
            f"<td>{html.escape(z.get('duration_sec',''))}</td>"
            f"<td>{html.escape(z.get('episodes_n',''))}</td>"
            f"<td>{html.escape(z.get('points_n',''))}</td>"
            f"<td>{html.escape(z.get('component_status_counts',''))}</td>"
            f"<td>{html.escape(z.get('component_context_counts',''))}</td>"
            f"<td>{html.escape(z.get('nearest_distance_median_of_medians_m',''))}</td>"
            f"<td>{html.escape(z.get('nearest_distance_max_m',''))}</td>"
            f"<td>{html.escape(z.get('zone_quality_flag',''))}</td>"
            "</tr>"
        )

    status_counts_html = "".join(
        f"<tr><td>{html.escape(k)}</td><td>{v}</td></tr>"
        for k, v in sorted(status_counts.items())
    )

    zone_point_counts_html = "".join(
        f"<tr><td>{html.escape(k)}</td><td>{v}</td></tr>"
        for k, v in sorted(zone_point_counts.items())
    )

    summary_html = ""
    if summary:
        summary_html = "".join(
            f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>"
            for k, v in summary.items()
            if k not in {"zone_type_counts", "zone_quality_counts"}
        )

    html_text = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8"/>
<title>IB3A-RC v1g2 Off-target Zone QA - {html.escape(args.activity_id)}</title>
<style>
body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; color: #111827; }}
h1 {{ margin-bottom: 4px; }}
.note {{ color: #4b5563; margin-bottom: 16px; }}
.box {{ border: 1px solid #d1d5db; border-radius: 10px; padding: 14px; margin: 16px 0; }}
svg {{ background: #f9fafb; border: 1px solid #d1d5db; border-radius: 10px; }}
table {{ border-collapse: collapse; font-size: 13px; width: 100%; }}
th, td {{ border: 1px solid #d1d5db; padding: 5px 7px; text-align: left; vertical-align: top; }}
th {{ background: #f3f4f6; }}
.legend span {{ display: inline-block; margin-right: 18px; margin-bottom: 6px; }}
code {{ background: #f3f4f6; padding: 2px 4px; border-radius: 4px; }}
</style>
</head>
<body>
<h1>IB3A-RC v1g2 Off-target Zone QA - {html.escape(args.activity_id)}</h1>
<div class="note">
Review-only visualization. This does not modify candidate_context, training_use_policy, point-level flags, usable_on_route, or upstream outputs.
</div>

<div class="box">
<h2>What to check</h2>
<ol>
<li>Red zone should cover the main off-target approach/low-confidence area after leaving the target route.</li>
<li>Purple or orange short zones should be small review evidence, not large mistaken off-target blocks.</li>
<li>Dark mainline and cyan connector points should remain outside off-target zones.</li>
<li>Yellow summit-stay points should not be swallowed by off-target zones.</li>
</ol>
</div>

<div class="box legend">
<h2>Legend</h2>
<span><span style="display:inline-block;width:12px;height:12px;background:#374151;border-radius:50%;"></span> on target route</span>
<span><span style="display:inline-block;width:12px;height:12px;background:#06b6d4;border-radius:50%;"></span> on target connector</span>
<span><span style="display:inline-block;width:12px;height:12px;background:#facc15;border-radius:50%;"></span> summit stay</span>
<span><span style="display:inline-block;width:12px;height:12px;background:#ef4444;border-radius:50%;"></span> off-target approach/lowconf zone</span>
<span><span style="display:inline-block;width:12px;height:12px;background:#f97316;border-radius:50%;"></span> off-target approach/service zone</span>
<span><span style="display:inline-block;width:12px;height:12px;background:#a855f7;border-radius:50%;"></span> off-target branch zone</span>
</div>

<div class="box">
<h2>Off-target zone map</h2>
<svg width="{bounds['width']}" height="{bounds['height']}" viewBox="0 0 {bounds['width']} {bounds['height']}">
{raw_line}
{''.join(circles)}
</svg>
</div>

<div class="box">
<h2>Target-route status point counts</h2>
<table>
<tr><th>Status</th><th>Point count</th></tr>
{status_counts_html}
</table>
</div>

<div class="box">
<h2>Zone point counts</h2>
<table>
<tr><th>Zone type</th><th>Point count</th></tr>
{zone_point_counts_html}
</table>
</div>

<div class="box">
<h2>Off-target zones</h2>
<table>
<tr>
<th>Zone</th><th>Type</th><th>Elapsed</th><th>Duration</th><th>Episodes</th><th>Points</th>
<th>Status components</th><th>Context components</th><th>Median dist</th><th>Max dist</th><th>Quality</th>
</tr>
{''.join(zone_rows_html)}
</table>
</div>

<div class="box">
<h2>Summary JSON</h2>
<table>
{summary_html}
</table>
</div>

<div class="box">
<h2>Files</h2>
<p>Point CSV: <code>{html.escape(str(point_csv))}</code></p>
<p>Zone CSV: <code>{html.escape(str(zone_csv))}</code></p>
<p>Summary JSON: <code>{html.escape(str(args.summary_json or ""))}</code></p>
</div>
</body>
</html>
"""

    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(html_text, encoding="utf-8")

    print(f"wrote: {out_html}")
    print(f"points: {len(points)}")
    print(f"zones: {len(zones)}")
    print(f"status_counts: {status_counts}")
    print(f"zone_point_counts: {zone_point_counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
