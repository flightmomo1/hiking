#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
import html
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
    if membership == "MAINLINE_SUMMIT_STAY" and is_true(row.get("anchor_stabilized_flag", "")):
        lat = to_float(row.get("anchor_refit_lat"))
        lon = to_float(row.get("anchor_refit_lon"))
        if lat is not None and lon is not None:
            return lat, lon, "anchor_refit"

    return to_float(row.get("lat")), to_float(row.get("lon")), "raw_latlon"


def collect_latlon(rows: list[dict[str, str]], display: bool = False) -> list[tuple[float, float]]:
    pts = []
    for r in rows:
        if display:
            lat, lon, _ = get_display_latlon(r)
        else:
            lat = to_float(r.get("lat"))
            lon = to_float(r.get("lon"))
        if lat is not None and lon is not None:
            pts.append((lat, lon))
    return pts


def make_projector(points: list[tuple[float, float]], width: int = 1200, height: int = 880, pad: int = 55):
    if not points:
        raise ValueError("No valid points.")

    min_lat = min(p[0] for p in points)
    max_lat = max(p[0] for p in points)
    min_lon = min(p[1] for p in points)
    max_lon = max(p[1] for p in points)

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


def polyline(points: list[tuple[float, float]], color: str, width: float, opacity: float) -> str:
    if len(points) < 2:
        return ""
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}" opacity="{opacity}"/>'


def point_style(row: dict[str, str]) -> tuple[str, float, float]:
    wrong_label = row.get("wrong_route_label", "")
    membership = row.get("mainline_membership", "")

    if wrong_label == "WRONG_ROUTE_CANDIDATE_EPISODE":
        return "#ff0000", 4.6, 0.95
    if wrong_label == "WRONG_ROUTE_SHORT_EVIDENCE":
        return "#ff8c00", 4.2, 0.95
    if membership == "MAINLINE_SUMMIT_STAY":
        return "#facc15", 3.8, 0.90
    if membership == "CONNECTOR":
        return "#06b6d4", 3.0, 0.82
    if membership.startswith("NON_MAINLINE"):
        return "#dc2626", 3.0, 0.78
    if membership == "MAINLINE_CORE":
        return "#374151", 2.0, 0.44

    return "#6b7280", 2.0, 0.45


def count_values(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        v = r.get(field, "")
        out[v] = out.get(v, 0) + 1
    return out


def table_rows(counts: dict[str, int]) -> str:
    return "".join(
        f"<tr><td>{html.escape(str(k))}</td><td>{v}</td></tr>"
        for k, v in sorted(counts.items())
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route-folder", required=True)
    parser.add_argument("--activity-id", required=True)
    parser.add_argument("--wrong-route-csv", required=True)
    parser.add_argument("--episode-csv", required=True)
    parser.add_argument("--ib0d-route-points-csv", required=True)
    parser.add_argument("--out-html", required=True)
    args = parser.parse_args()

    rows = read_csv_rows(Path(args.wrong_route_csv))
    episodes = read_csv_rows(Path(args.episode_csv))
    ib0d_rows = read_csv_rows(Path(args.ib0d_route_points_csv))

    raw_pts = collect_latlon(rows, display=False)
    display_pts = collect_latlon(rows, display=True)

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
    wrong_rows = [r for r in rows if r.get("wrong_route_flag") == "True"]

    for r in rows:
        lat, lon, display_source = get_display_latlon(r)
        if lat is None or lon is None:
            continue

        x, y = xy(lat, lon)
        color, radius, opacity = point_style(r)

        title = (
            f"elapsed={r.get('elapsed_sec','')}\\n"
            f"display_source={display_source}\\n"
            f"wrong_route_flag={r.get('wrong_route_flag','')}\\n"
            f"wrong_route_label={r.get('wrong_route_label','')}\\n"
            f"wrong_route_decision={r.get('wrong_route_review_decision','')}\\n"
            f"candidate_way_id={r.get('candidate_way_id','')}\\n"
            f"nearest_osm_way_id={r.get('nearest_osm_way_id','')}\\n"
            f"nearest_way_name={r.get('nearest_way_name','')}\\n"
            f"membership={r.get('mainline_membership','')}\\n"
            f"mainline_training_before={r.get('mainline_training_flag','')}\\n"
            f"mainline_training_after_v1i={r.get('mainline_training_flag_after_v1i','')}\\n"
            f"non_mainline_after_v1i={r.get('non_mainline_type_after_v1i','')}\\n"
            f"manual_reason={r.get('manual_wrong_route_review_reason','')}"
        )

        circles.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{color}" opacity="{opacity}">'
            f'<title>{html.escape(title)}</title></circle>'
        )

    episode_rows_html = ""
    for e in episodes:
        episode_rows_html += (
            "<tr>"
            f"<td>{html.escape(e.get('wrong_route_episode_id',''))}</td>"
            f"<td>{html.escape(e.get('wrong_route_label',''))}</td>"
            f"<td>{html.escape(e.get('candidate_way_id',''))}</td>"
            f"<td>{html.escape(e.get('nearest_way_name',''))}</td>"
            f"<td>{html.escape(e.get('start_elapsed_sec',''))}–{html.escape(e.get('end_elapsed_sec',''))}</td>"
            f"<td>{html.escape(e.get('duration_sec',''))}</td>"
            f"<td>{html.escape(e.get('points_n',''))}</td>"
            f"<td>{html.escape(e.get('mainline_membership_counts',''))}</td>"
            "</tr>"
        )

    html_text = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8"/>
<title>IB3A-RC v1i Manual Wrong-route QA - {html.escape(args.activity_id)}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 24px; color: #111827; }}
.box {{ border: 1px solid #d1d5db; border-radius: 10px; padding: 14px; margin: 16px 0; }}
svg {{ background: #f9fafb; border: 1px solid #d1d5db; border-radius: 10px; }}
table {{ border-collapse: collapse; font-size: 13px; width: 100%; }}
td, th {{ border: 1px solid #d1d5db; padding: 5px 8px; vertical-align: top; }}
th {{ background: #f3f4f6; }}
.legend span {{ display: inline-block; margin-right: 16px; margin-bottom: 6px; }}
code {{ background: #f3f4f6; padding: 3px 5px; border-radius: 4px; }}
</style>
</head>
<body>
<h1>IB3A-RC v1i Manual Wrong-route QA - {html.escape(args.activity_id)}</h1>

<div class="box">
<h2>What to check</h2>
<ol>
<li>亮粉紅粗線是 IB0D formal mainline。</li>
<li>亮紅大點應標出主要錯路 episode：way_105 / 七星山登山步道苗圃線 / elapsed 4204–5150。</li>
<li>橘色大點應只是一小段 short evidence：way_99 / 七星山登山步道七星公園線 / elapsed 6732–6733。</li>
<li>錯路標記不應吃到 summit stay、connector 或正常 IB0D 主線。</li>
<li>亮紅錯路點 hover 時，mainline_training_after_v1i 應為 False。</li>
</ol>
</div>

<div class="box legend">
<h2>Legend</h2>
<span><span style="display:inline-block;width:32px;height:6px;background:#ff00ff;"></span> IB0D formal mainline</span>
<span><span style="display:inline-block;width:32px;height:3px;background:#9ca3af;"></span> raw GPS trace</span>
<span><span style="display:inline-block;width:12px;height:12px;background:#374151;border-radius:50%;"></span> MAINLINE_CORE</span>
<span><span style="display:inline-block;width:12px;height:12px;background:#facc15;border-radius:50%;"></span> SUMMIT_STAY</span>
<span><span style="display:inline-block;width:12px;height:12px;background:#06b6d4;border-radius:50%;"></span> CONNECTOR</span>
<span><span style="display:inline-block;width:12px;height:12px;background:#ff0000;border-radius:50%;"></span> WRONG_ROUTE_CANDIDATE_EPISODE</span>
<span><span style="display:inline-block;width:12px;height:12px;background:#ff8c00;border-radius:50%;"></span> WRONG_ROUTE_SHORT_EVIDENCE</span>
</div>

<div class="box">
<h2>Map</h2>
<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">
{polyline(raw_xy, "#9ca3af", 1.0, 0.30)}
{''.join(circles)}
{polyline(ib0d_xy, "#ffffff", 11.0, 1.0)}
{polyline(ib0d_xy, "#ff00ff", 6.0, 1.0)}
</svg>
</div>

<div class="box">
<h2>Wrong-route episodes</h2>
<table>
<tr>
<th>Episode</th><th>Label</th><th>Candidate way</th><th>Way name</th>
<th>Elapsed</th><th>Duration</th><th>Points</th><th>Original membership</th>
</tr>
{episode_rows_html}
</table>
</div>

<div class="box">
<h2>Counts</h2>
<h3>Wrong route labels</h3>
<table><tr><th>Label</th><th>Count</th></tr>{table_rows(count_values(wrong_rows, "wrong_route_label"))}</table>
<h3>Mainline training after v1i</h3>
<table><tr><th>Flag</th><th>Count</th></tr>{table_rows(count_values(rows, "mainline_training_flag_after_v1i"))}</table>
</div>

<div class="box">
<h2>Files</h2>
<p>Wrong-route CSV: <code>{html.escape(args.wrong_route_csv)}</code></p>
<p>Episode CSV: <code>{html.escape(args.episode_csv)}</code></p>
<p>IB0D route points CSV: <code>{html.escape(args.ib0d_route_points_csv)}</code></p>
<p>Rows read: <code>{len(rows)}</code></p>
<p>Wrong-route rows: <code>{len(wrong_rows)}</code></p>
<p>Episodes: <code>{len(episodes)}</code></p>
</div>

</body>
</html>
"""

    out_html = Path(args.out_html)
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(html_text, encoding="utf-8")

    print(f"wrote: {out_html}")
    print(f"rows: {len(rows)}")
    print(f"wrong_route_rows: {len(wrong_rows)}")
    print(f"episodes: {len(episodes)}")
    print(f"wrong_route_label_counts: {count_values(wrong_rows, 'wrong_route_label')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
