#!/usr/bin/env python
# -*- coding: utf-8 -*-
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


def is_true(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y", "t"}


def read_csv_rows(fp: Path) -> list[dict[str, str]]:
    if not fp.exists():
        raise FileNotFoundError(fp)
    with fp.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def get_display_latlon(row: dict[str, str]) -> tuple[float | None, float | None, str]:
    membership = row.get("mainline_membership", "")
    anchor_flag = is_true(row.get("anchor_stabilized_flag", ""))
    anchor_reason = row.get("anchor_refit_reason", "")

    if membership == "MAINLINE_SUMMIT_STAY" and anchor_flag:
        lat = to_float(row.get("anchor_refit_lat"))
        lon = to_float(row.get("anchor_refit_lon"))
        if lat is not None and lon is not None:
            return lat, lon, f"anchor_refit:{anchor_reason or 'summit'}"

    lat = to_float(row.get("lat"))
    lon = to_float(row.get("lon"))
    return lat, lon, "raw_latlon"


def collect_display_latlon(rows: list[dict[str, str]]) -> list[tuple[float, float]]:
    pts = []
    for r in rows:
        lat, lon, _ = get_display_latlon(r)
        if lat is not None and lon is not None:
            pts.append((lat, lon))
    return pts


def collect_raw_latlon(rows: list[dict[str, str]]) -> list[tuple[float, float]]:
    pts = []
    for r in rows:
        lat = to_float(r.get("lat"))
        lon = to_float(r.get("lon"))
        if lat is not None and lon is not None:
            pts.append((lat, lon))
    return pts


def make_projector(all_points: list[tuple[float, float]], width: int = 1200, height: int = 880, pad: int = 55):
    if not all_points:
        raise ValueError("No valid lat/lon points.")

    min_lat = min(p[0] for p in all_points)
    max_lat = max(p[0] for p in all_points)
    min_lon = min(p[1] for p in all_points)
    max_lon = max(p[1] for p in all_points)

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

    return xy, width, height


def polyline(points: list[tuple[float, float]], color: str, width: float, opacity: float, dash: str = "") -> str:
    if len(points) < 2:
        return ""
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}" opacity="{opacity}"{dash_attr}/>'


def color_for(row: dict[str, str]) -> str:
    membership = row.get("mainline_membership", "")
    non_type = row.get("non_mainline_type", "")

    if membership == "MAINLINE_CORE":
        return "#374151"
    if membership == "MAINLINE_SUMMIT_STAY":
        return "#facc15"
    if membership == "CONNECTOR":
        return "#06b6d4"
    if non_type == "OFF_TARGET_APPROACH_LOWCONF_ZONE":
        return "#ef4444"
    if non_type == "OFF_TARGET_APPROACH_OR_SERVICE_ZONE":
        return "#f97316"
    if non_type == "OFF_TARGET_BRANCH_ZONE":
        return "#a855f7"
    if membership.startswith("NON_MAINLINE"):
        return "#dc2626"
    return "#6b7280"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route-folder", required=True)
    parser.add_argument("--activity-id", required=True)
    parser.add_argument("--membership-csv", required=True)
    parser.add_argument("--ib0d-route-points-csv", required=True)
    parser.add_argument("--summary-json", required=False)
    parser.add_argument("--out-html", required=True)
    args = parser.parse_args()

    membership_csv = Path(args.membership_csv)
    ib0d_csv = Path(args.ib0d_route_points_csv)
    out_html = Path(args.out_html)

    rows = read_csv_rows(membership_csv)
    ib0d_rows = read_csv_rows(ib0d_csv)

    raw_pts = collect_raw_latlon(rows)
    display_pts = collect_display_latlon(rows)

    ib0d_pts = []
    for r in ib0d_rows:
        lat = to_float(r.get("lat"))
        lon = to_float(r.get("lon"))
        if lat is not None and lon is not None:
            ib0d_pts.append((lat, lon))

    xy, width, height = make_projector(raw_pts + display_pts + ib0d_pts)

    raw_xy = [xy(lat, lon) for lat, lon in raw_pts]
    ib0d_xy = [xy(lat, lon) for lat, lon in ib0d_pts]

    circles = []
    refit_connector_lines = []
    membership_counts: dict[str, int] = {}
    non_type_counts: dict[str, int] = {}
    display_source_counts: dict[str, int] = {}

    for r in rows:
        raw_lat = to_float(r.get("lat"))
        raw_lon = to_float(r.get("lon"))
        lat, lon, display_source = get_display_latlon(r)

        if lat is None or lon is None:
            continue

        x, y = xy(lat, lon)

        membership = r.get("mainline_membership", "")
        non_type = r.get("non_mainline_type", "")

        membership_counts[membership] = membership_counts.get(membership, 0) + 1
        display_source_counts[display_source] = display_source_counts.get(display_source, 0) + 1

        if non_type:
            non_type_counts[non_type] = non_type_counts.get(non_type, 0) + 1

        if display_source.startswith("anchor_refit") and raw_lat is not None and raw_lon is not None:
            rx, ry = xy(raw_lat, raw_lon)
            refit_connector_lines.append(
                f'<line x1="{rx:.1f}" y1="{ry:.1f}" x2="{x:.1f}" y2="{y:.1f}" '
                f'stroke="#facc15" stroke-width="0.8" opacity="0.25" stroke-dasharray="3 3"/>'
            )

        radius = 2.0
        opacity = 0.50

        if membership == "MAINLINE_SUMMIT_STAY":
            radius = 4.0
            opacity = 0.95
        elif membership == "CONNECTOR":
            radius = 3.0
            opacity = 0.85
        elif membership.startswith("NON_MAINLINE"):
            radius = 3.0
            opacity = 0.85

        title = (
            f"elapsed={r.get('elapsed_sec','')}\\n"
            f"display_source={display_source}\\n"
            f"membership={membership}\\n"
            f"non_type={non_type}\\n"
            f"raw_latlon={r.get('lat','')}, {r.get('lon','')}\\n"
            f"anchor_refit={r.get('anchor_refit_lat','')}, {r.get('anchor_refit_lon','')}\\n"
            f"anchor_distance_m={r.get('anchor_distance_m','')}\\n"
            f"anchor_reason={r.get('anchor_refit_reason','')}\\n"
            f"zone={r.get('v1g2_zone_id','')} / {r.get('v1g2_zone_type','')}\\n"
            f"context={r.get('candidate_context','')}\\n"
            f"target_status={r.get('target_route_status','')}\\n"
            f"nearest_dist={r.get('nearest_distance_m','')}"
        )

        circles.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{color_for(r)}" opacity="{opacity}">'
            f'<title>{html.escape(title)}</title></circle>'
        )

    def table_rows(counts: dict[str, int]) -> str:
        return "".join(
            f"<tr><td>{html.escape(k)}</td><td>{v}</td></tr>"
            for k, v in sorted(counts.items())
        )

    summary_text = ""
    if args.summary_json and Path(args.summary_json).exists():
        summary_text = html.escape(Path(args.summary_json).read_text(encoding="utf-8"))

    html_text = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8"/>
<title>IB3A-RC v1h2b IB0D Overlay + Summit Display Refit QA - {html.escape(args.activity_id)}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 24px; color: #111827; }}
.box {{ border: 1px solid #d1d5db; border-radius: 10px; padding: 14px; margin: 16px 0; }}
svg {{ background: #f9fafb; border: 1px solid #d1d5db; border-radius: 10px; }}
table {{ border-collapse: collapse; font-size: 13px; }}
td, th {{ border: 1px solid #d1d5db; padding: 5px 8px; }}
th {{ background: #f3f4f6; }}
.legend span {{ display: inline-block; margin-right: 16px; margin-bottom: 6px; }}
code, pre {{ background: #f3f4f6; padding: 4px; border-radius: 4px; }}
</style>
</head>
<body>
<h1>IB3A-RC v1h2b Mainline Membership + IB0D Overlay + Summit Display Refit QA - {html.escape(args.activity_id)}</h1>

<div class="box">
<h2>What changed from v1h2</h2>
<ol>
<li>亮粉紅粗線仍是 IB0D 正式主線。</li>
<li>MAINLINE_SUMMIT_STAY 且 anchor_stabilized_flag=True 的點，改用 anchor_refit_lat / anchor_refit_lon 顯示。</li>
<li>淡黃色虛線表示 raw summit GPS 點被畫回 anchor refit 位置。</li>
<li>其他點仍使用原始 lat / lon 顯示。</li>
</ol>
</div>

<div class="box legend">
<h2>Legend</h2>
<span><span style="display:inline-block;width:32px;height:6px;background:#ff00ff;"></span> IB0D formal mainline</span>
<span><span style="display:inline-block;width:32px;height:3px;background:#9ca3af;"></span> raw GPS trace</span>
<span><span style="display:inline-block;width:32px;height:2px;border-top:2px dashed #facc15;"></span> summit raw → anchor refit</span>
<span><span style="display:inline-block;width:12px;height:12px;background:#374151;border-radius:50%;"></span> MAINLINE_CORE</span>
<span><span style="display:inline-block;width:12px;height:12px;background:#facc15;border-radius:50%;"></span> SUMMIT_STAY displayed at anchor_refit</span>
<span><span style="display:inline-block;width:12px;height:12px;background:#06b6d4;border-radius:50%;"></span> CONNECTOR</span>
<span><span style="display:inline-block;width:12px;height:12px;background:#ef4444;border-radius:50%;"></span> OFF_TARGET_LOWCONF_ZONE</span>
<span><span style="display:inline-block;width:12px;height:12px;background:#f97316;border-radius:50%;"></span> OFF_TARGET_APPROACH_ZONE</span>
<span><span style="display:inline-block;width:12px;height:12px;background:#a855f7;border-radius:50%;"></span> OFF_TARGET_BRANCH_ZONE</span>
</div>

<div class="box">
<h2>Map</h2>
<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">
{polyline(raw_xy, "#9ca3af", 1.0, 0.30)}
{''.join(refit_connector_lines)}
{''.join(circles)}
{polyline(ib0d_xy, "#ffffff", 11.0, 1.0)}
{polyline(ib0d_xy, "#ff00ff", 6.0, 1.0)}
</svg>
</div>

<div class="box">
<h2>Mainline membership counts</h2>
<table><tr><th>Membership</th><th>Point count</th></tr>{table_rows(membership_counts)}</table>
</div>

<div class="box">
<h2>Display source counts</h2>
<table><tr><th>Display source</th><th>Point count</th></tr>{table_rows(display_source_counts)}</table>
</div>

<div class="box">
<h2>Non-mainline type counts</h2>
<table><tr><th>Type</th><th>Point count</th></tr>{table_rows(non_type_counts)}</table>
</div>

<div class="box">
<h2>Files</h2>
<p>Membership CSV: <code>{html.escape(str(membership_csv))}</code></p>
<p>IB0D route points CSV: <code>{html.escape(str(ib0d_csv))}</code></p>
<p>IB0D route points read: <code>{len(ib0d_rows)}</code></p>
<p>GPS membership rows read: <code>{len(rows)}</code></p>
</div>

<div class="box">
<h2>Summary JSON</h2>
<pre>{summary_text}</pre>
</div>
</body>
</html>
"""

    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(html_text, encoding="utf-8")

    print(f"wrote: {out_html}")
    print(f"points: {len(rows)}")
    print(f"ib0d_route_points: {len(ib0d_rows)}")
    print(f"membership_counts: {membership_counts}")
    print(f"display_source_counts: {display_source_counts}")
    print(f"non_type_counts: {non_type_counts}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
