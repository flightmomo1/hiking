#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IB3A-RC v1f2 transition continuity QA HTML.

Review-only visual QA:
- Reads v1d3 candidate_point_stability.csv
- Reads v1f2 candidate_context_segments_v1f_transition_labeled.csv
- Draws raw GPS points by segment transition type
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

    return xy, {
        "width": width,
        "height": height,
        "min_lat": min_lat,
        "max_lat": max_lat,
        "min_lon": min_lon,
        "max_lon": max_lon,
    }


def polyline_svg(points: list[tuple[float, float]], stroke: str, width: float, opacity: float = 1.0, dash: str = "") -> str:
    if len(points) < 2:
        return ""
    d = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<polyline points="{d}" fill="none" stroke="{stroke}" stroke-width="{width}" opacity="{opacity}"{dash_attr}/>'


def segment_for_elapsed(segments: list[dict[str, str]], elapsed_sec: float) -> dict[str, str] | None:
    for s in segments:
        start = to_float(s.get("start_elapsed_sec"))
        end = to_float(s.get("end_elapsed_sec"))
        if start is None or end is None:
            continue
        if start <= elapsed_sec <= end:
            return s
    return None


def color_for_transition(transition_type: str, context: str) -> str:
    if transition_type == "NORMAL_CONNECTOR_MAINLINE_TRANSITION":
        return "#06b6d4"  # cyan
    if transition_type == "MAINLINE_EXIT_TO_APPROACH_LOOP":
        return "#f97316"  # orange
    if transition_type == "APPROACH_LOWCONF_OSCILLATION":
        return "#ef4444"  # red
    if context == "MAINLINE_LIKELY":
        return "#374151"  # dark gray
    if context == "MAINLINE_CONNECTOR_LIKELY":
        return "#0ea5e9"  # blue
    if context == "LOW_CONFIDENCE_CANDIDATE":
        return "#991b1b"  # dark red
    if context == "APPROACH_OR_ROAD":
        return "#fb923c"  # light orange
    if context == "BRANCH_OR_SIDE_TRAIL_LIKELY":
        return "#a855f7"  # purple
    return "#6b7280"


def main() -> int:
    parser = argparse.ArgumentParser(description="Plot IB3A-RC v1f2 transition continuity QA HTML.")
    parser.add_argument("--route-folder", required=True)
    parser.add_argument("--activity-id", required=True)
    parser.add_argument("--point-csv", required=True)
    parser.add_argument("--segments-csv", required=True)
    parser.add_argument("--summary-json", required=False)
    parser.add_argument("--out-html", required=True)
    args = parser.parse_args()

    point_csv = Path(args.point_csv)
    segments_csv = Path(args.segments_csv)
    out_html = Path(args.out_html)

    points = read_csv_rows(point_csv)
    segments = read_csv_rows(segments_csv)
    segments = sorted(segments, key=lambda r: to_float(r.get("start_elapsed_sec"), 0.0) or 0.0)

    summary = {}
    if args.summary_json and Path(args.summary_json).exists():
        summary = json.loads(Path(args.summary_json).read_text(encoding="utf-8"))

    xy, bounds = project_points(points)

    raw_xy = []
    circles = []
    transition_counts: dict[str, int] = {}
    context_counts: dict[str, int] = {}

    for r in points:
        lat = to_float(r.get("lat"))
        lon = to_float(r.get("lon"))
        elapsed = to_float(r.get("elapsed_sec"))
        if lat is None or lon is None or elapsed is None:
            continue

        x, y = xy(lat, lon)
        raw_xy.append((x, y))

        seg = segment_for_elapsed(segments, elapsed)
        if seg is None:
            transition_type = "UNMATCHED_SEGMENT"
            context = r.get("candidate_context", "")
            policy = r.get("training_use_policy", "")
            segment_id = ""
        else:
            transition_type = seg.get("transition_type", "")
            context = seg.get("dominant_candidate_context", "")
            policy = seg.get("dominant_training_policy", "")
            segment_id = seg.get("segment_id", "")

        transition_counts[transition_type] = transition_counts.get(transition_type, 0) + 1
        context_counts[context] = context_counts.get(context, 0) + 1

        color = color_for_transition(transition_type, context)

        # Draw all points lightly; transition points slightly larger.
        radius = 2.0
        opacity = 0.45
        if transition_type == "NORMAL_CONNECTOR_MAINLINE_TRANSITION":
            radius = 3.0
            opacity = 0.85
        elif transition_type == "MAINLINE_EXIT_TO_APPROACH_LOOP":
            radius = 3.2
            opacity = 0.88
        elif transition_type == "APPROACH_LOWCONF_OSCILLATION":
            radius = 2.6
            opacity = 0.65

        title = (
            f"segment={segment_id}\\n"
            f"elapsed={r.get('elapsed_sec','')}\\n"
            f"context={context}\\n"
            f"policy={policy}\\n"
            f"transition={transition_type}\\n"
            f"way={r.get('nearest_candidate_way_id','')}\\n"
            f"dist={r.get('nearest_distance_m','')}"
        )

        circles.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{color}" opacity="{opacity}">'
            f'<title>{html.escape(title)}</title></circle>'
        )

    raw_line = polyline_svg(raw_xy, "#111827", 1.0, 0.45)

    seg_rows_html = []
    for s in segments:
        t = s.get("transition_type", "")
        if t == "NO_SPECIAL_TRANSITION":
            continue
        color = color_for_transition(t, s.get("dominant_candidate_context", ""))
        seg_rows_html.append(
            "<tr>"
            f"<td>{html.escape(s.get('segment_id',''))}</td>"
            f"<td>{html.escape(s.get('start_elapsed_sec',''))}–{html.escape(s.get('end_elapsed_sec',''))}</td>"
            f"<td>{html.escape(s.get('duration_sec',''))}</td>"
            f"<td>{html.escape(s.get('dominant_candidate_context',''))}</td>"
            f"<td>{html.escape(s.get('dominant_training_policy',''))}</td>"
            f"<td>{html.escape(s.get('dominant_candidate_way_id',''))}</td>"
            f"<td>{html.escape(s.get('median_nearest_distance_m',''))}</td>"
            f"<td><span style='display:inline-block;width:10px;height:10px;background:{color};border-radius:50%;'></span> {html.escape(t)}</td>"
            f"<td>{html.escape(s.get('transition_review_level',''))}</td>"
            f"<td>{html.escape(s.get('transition_reason',''))}</td>"
            "</tr>"
        )

    transition_counts_html = "".join(
        f"<tr><td>{html.escape(k)}</td><td>{v}</td></tr>"
        for k, v in sorted(transition_counts.items())
    )

    summary_html = ""
    if summary:
        summary_html = "".join(
            f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>"
            for k, v in summary.items()
            if k not in {"transition_counts"}
        )

    html_text = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8"/>
<title>IB3A-RC v1f2 Transition Continuity QA - {html.escape(args.activity_id)}</title>
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
<h1>IB3A-RC v1f2 Transition Continuity QA - {html.escape(args.activity_id)}</h1>
<div class="note">
Review-only visualization. This does not modify candidate_context, training_use_policy, point-level flags, usable_on_route, or upstream outputs.
</div>

<div class="box">
<h2>What to check</h2>
<ol>
<li>Cyan points should appear at normal connector/mainline transitions.</li>
<li>Orange points should mark where mainline exits into approach/service loop.</li>
<li>Red points should remain in approach/low-confidence oscillation zones and should not be treated as training OK.</li>
<li>Long mainline sections should remain dark/neutral, not fully colored as transition.</li>
</ol>
</div>

<div class="box legend">
<h2>Legend</h2>
<span><span style="display:inline-block;width:12px;height:12px;background:#374151;border-radius:50%;"></span> mainline / no special transition</span>
<span><span style="display:inline-block;width:12px;height:12px;background:#06b6d4;border-radius:50%;"></span> normal connector-mainline transition</span>
<span><span style="display:inline-block;width:12px;height:12px;background:#f97316;border-radius:50%;"></span> mainline exit to approach loop</span>
<span><span style="display:inline-block;width:12px;height:12px;background:#ef4444;border-radius:50%;"></span> approach-lowconf oscillation</span>
<span><span style="display:inline-block;width:12px;height:12px;background:#a855f7;border-radius:50%;"></span> branch / side trail</span>
</div>

<div class="box">
<h2>Transition map</h2>
<svg width="{bounds['width']}" height="{bounds['height']}" viewBox="0 0 {bounds['width']} {bounds['height']}">
{raw_line}
{''.join(circles)}
</svg>
</div>

<div class="box">
<h2>Transition point counts</h2>
<table>
<tr><th>Transition type</th><th>Point count</th></tr>
{transition_counts_html}
</table>
</div>

<div class="box">
<h2>Important transition segments</h2>
<table>
<tr>
<th>Segment</th><th>Elapsed</th><th>Duration</th><th>Context</th><th>Policy</th><th>Way</th><th>Median distance</th><th>Transition</th><th>Review level</th><th>Reason</th>
</tr>
{''.join(seg_rows_html)}
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
<p>Segments CSV: <code>{html.escape(str(segments_csv))}</code></p>
<p>Summary JSON: <code>{html.escape(str(args.summary_json or ""))}</code></p>
</div>
</body>
</html>
"""

    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(html_text, encoding="utf-8")

    print(f"wrote: {out_html}")
    print(f"points: {len(points)}")
    print(f"segments: {len(segments)}")
    print(f"transition_counts: {transition_counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
