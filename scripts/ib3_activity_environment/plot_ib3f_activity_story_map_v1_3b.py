"""Build an offline interactive IB3F activity story map for qixing review."""

from __future__ import annotations

import bisect
import csv
import html
import json
import math
from pathlib import Path
from typing import Any


CASE_ID = "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b"
ROUTE_FOLDER = "qixing_lengshuikeng"
ACTIVITY_IDS = ["37_1", "33_1", "15_1"]

IB3F_ROOT = Path("outputs/ib3f_activity_route_features_v1_3b_qixing_repaired_review")
IB3A2_ROOT = Path("outputs/ib3a2_on_route_activity_filter_v1_3b_qixing_via_corridor_repair_candidate")
ROUTE_PROFILE_ROOT = Path("outputs/ib1_route_profile_v1_3b_qixing_via_corridor_repair_candidate")
ROUTE_RISK_ROOT = Path("outputs/ib2_v2_route_risk_v1_3b_contract_qa")
CORRIDOR_DEFINITION_CSV = Path("configs/risk_semantics/qixing_branch_corridor_definition_v1_3b.csv")
OUT_HTML = IB3F_ROOT / "_batch_summary" / "ib3f_activity_story_map_qixing_repaired_review_v2.html"

CONTROL_POINTS = {
    "via_up": {"lat": 25.165082087184047, "lon": 121.55966911100028, "label": "via_up"},
    "via_down": {"lat": 25.16487469519971, "lon": 121.55963745345083, "label": "via_down"},
    "summit": {"lat": 25.17069791627356, "lon": 121.5534529370406, "dist_m": 1919.0, "label": "summit"},
}

STATE_COLORS = {
    "on_route_reliable": "#16a34a",
    "off_route_projection_only": "#dc2626",
    "near_route_low_confidence": "#f59e0b",
    "branch_ambiguous_projection": "#7c3aed",
}
PHASE_COLORS = {
    "ascent": "#2563eb",
    "summit_self_near": "#db2777",
    "descent": "#059669",
    "unknown": "#64748b",
    "excluded": "#94a3b8",
}
RISK_COLORS = {
    "low": "#22c55e",
    "moderate": "#f59e0b",
    "high": "#dc2626",
    "unknown": "#64748b",
}


def require_file(path: Path, label: str) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    return path


def read_csv(path: Path) -> list[dict[str, str]]:
    require_file(path, path.name)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def to_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def to_bool(value: Any) -> bool:
    return str(value).lower() in {"true", "1", "yes", "y"}


def load_route() -> list[dict[str, Any]]:
    path = ROUTE_PROFILE_ROOT / CASE_ID / f"{CASE_ID}_route_profile.csv"
    rows = read_csv(path)
    route = []
    for row in rows:
        lat = to_float(row.get("lat"))
        lon = to_float(row.get("lon"))
        dist = to_float(row.get("dist_m"))
        if lat is None or lon is None or dist is None:
            continue
        route.append(
            {
                "lat": lat,
                "lon": lon,
                "dist_m": dist,
                "ele": to_float(row.get("ele_smooth"), to_float(row.get("ele_gpx_m"), 0.0)),
            }
        )
    route.sort(key=lambda r: r["dist_m"])
    return route


def load_risk() -> tuple[list[float], list[dict[str, Any]]]:
    path = ROUTE_RISK_ROOT / CASE_ID / f"{CASE_ID}_route_risk_v2.csv"
    rows = read_csv(path)
    risk = []
    for row in rows:
        dist = to_float(row.get("dist_m"))
        if dist is None:
            continue
        risk.append(
            {
                "dist_m": dist,
                "risk_band": row.get("risk_band") or "unknown",
                "risk_score": to_float(row.get("risk_score"), 0.0),
            }
        )
    risk.sort(key=lambda r: r["dist_m"])
    return [r["dist_m"] for r in risk], risk


def nearest_by_dist(distances: list[float], rows: list[dict[str, Any]], dist: float | None) -> dict[str, Any]:
    if dist is None or not distances:
        return {}
    i = bisect.bisect_left(distances, dist)
    candidates = []
    if i < len(rows):
        candidates.append(rows[i])
    if i > 0:
        candidates.append(rows[i - 1])
    if not candidates:
        return {}
    return min(candidates, key=lambda row: abs(row["dist_m"] - dist))


def project_points(items: list[dict[str, Any]]) -> None:
    coords = [(to_float(p.get("lat")), to_float(p.get("lon"))) for p in items]
    coords = [(lat, lon) for lat, lon in coords if lat is not None and lon is not None]
    if not coords:
        return
    lat0 = sum(lat for lat, _ in coords) / len(coords)
    lon0 = sum(lon for _, lon in coords) / len(coords)
    cos_lat = math.cos(math.radians(lat0))
    for p in items:
        lat = to_float(p.get("lat"))
        lon = to_float(p.get("lon"))
        if lat is None or lon is None:
            p["x"] = None
            p["y"] = None
            continue
        p["x"] = (lon - lon0) * 111_320.0 * cos_lat
        p["y"] = -(lat - lat0) * 110_540.0


def attach_risk_to_route(route: list[dict[str, Any]], risk_dist: list[float], risk_rows: list[dict[str, Any]]) -> None:
    for p in route:
        risk = nearest_by_dist(risk_dist, risk_rows, p["dist_m"])
        p["risk_band"] = risk.get("risk_band", "unknown")
        p["risk_score"] = risk.get("risk_score", 0.0)


def interpolate_route_xy(route: list[dict[str, Any]], dist: float | None) -> tuple[float | None, float | None]:
    if dist is None or not route:
        return None, None
    if dist <= route[0]["dist_m"]:
        return route[0].get("x"), route[0].get("y")
    if dist >= route[-1]["dist_m"]:
        return route[-1].get("x"), route[-1].get("y")
    dists = [p["dist_m"] for p in route]
    idx = bisect.bisect_left(dists, dist)
    a = route[max(0, idx - 1)]
    b = route[min(len(route) - 1, idx)]
    span = b["dist_m"] - a["dist_m"]
    if span <= 0:
        return a.get("x"), a.get("y")
    t = (dist - a["dist_m"]) / span
    ax, ay, bx, by = a.get("x"), a.get("y"), b.get("x"), b.get("y")
    if ax is None or ay is None or bx is None or by is None:
        return None, None
    return ax + (bx - ax) * t, ay + (by - ay) * t


def attach_projected_xy(activities: dict[str, list[dict[str, Any]]], route: list[dict[str, Any]]) -> None:
    for points in activities.values():
        for p in points:
            px, py = interpolate_route_xy(route, p.get("route_dist_m"))
            p["projected_x"] = px
            p["projected_y"] = py


def load_activity(activity_id: str, risk_dist: list[float], risk_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    path = (
        IB3A2_ROOT
        / ROUTE_FOLDER
        / f"{ROUTE_FOLDER}_{activity_id}_mapmatched_activity_labeled.csv"
    )
    rows = read_csv(path)
    points = []
    for row in rows:
        lat = to_float(row.get("lat"))
        lon = to_float(row.get("lon"))
        if lat is None or lon is None:
            continue
        route_dist = to_float(row.get("route_dist_m"))
        risk = nearest_by_dist(risk_dist, risk_rows, route_dist)
        points.append(
            {
                "activity_id": activity_id,
                "timestamp_s": to_float(row.get("timestamp_s")),
                "elapsed_sec": to_float(row.get("elapsed_sec")),
                "lat": lat,
                "lon": lon,
                "route_dist_m": route_dist,
                "reliable_route_dist_m": to_float(row.get("reliable_route_dist_m")),
                "candidate_phase": row.get("candidate_phase") or "",
                "route_progress_state": row.get("route_progress_state") or "",
                "usable_on_route": to_bool(row.get("usable_on_route")),
                "offset_m": to_float(row.get("offset_m")),
                "implied_route_speed_mps": to_float(row.get("implied_route_speed_mps")),
                "heart_rate_bpm": to_float(row.get("heart_rate_bpm")),
                "risk_band": risk.get("risk_band", "unknown"),
                "risk_score": risk.get("risk_score", 0.0),
            }
        )
    points.sort(key=lambda p: (p["timestamp_s"] is None, p["timestamp_s"] or 0.0))
    return points


def load_features() -> dict[str, dict[str, Any]]:
    out = {}
    for activity_id in ACTIVITY_IDS:
        path = IB3F_ROOT / ROUTE_FOLDER / f"{ROUTE_FOLDER}_{activity_id}_activity_features.csv"
        rows = read_csv(path)
        out[activity_id] = rows[0] if rows else {}
    return out


def load_corridors(route: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not CORRIDOR_DEFINITION_CSV.exists():
        return []
    rows = read_csv(CORRIDOR_DEFINITION_CSV)
    corridors = []
    for row in rows:
        if row.get("case_id") != CASE_ID:
            continue
        start = to_float(row.get("start_dist_m"))
        end = to_float(row.get("end_dist_m"))
        if start is None or end is None:
            continue
        seg = [p for p in route if start <= p["dist_m"] <= end]
        corridors.append(
            {
                "corridor_id": row.get("corridor_id", ""),
                "corridor_role": row.get("corridor_role", ""),
                "start_dist_m": start,
                "end_dist_m": end,
                "points": [{"x": p["x"], "y": p["y"], "dist_m": p["dist_m"]} for p in seg],
            }
        )
    return corridors


def load_data() -> dict[str, Any]:
    route = load_route()
    risk_dist, risk_rows = load_risk()
    attach_risk_to_route(route, risk_dist, risk_rows)
    control_points = [{"id": k, **v} for k, v in CONTROL_POINTS.items()]
    activities = {activity_id: load_activity(activity_id, risk_dist, risk_rows) for activity_id in ACTIVITY_IDS}
    all_items: list[dict[str, Any]] = []
    all_items.extend(route)
    all_items.extend(control_points)
    for points in activities.values():
        all_items.extend(points)
    project_points(all_items)
    attach_projected_xy(activities, route)
    corridors = load_corridors(route)
    features = load_features()
    xs = [p["x"] for p in all_items if p.get("x") is not None]
    ys = [p["y"] for p in all_items if p.get("y") is not None]
    bounds = {
        "min_x": min(xs) if xs else 0,
        "max_x": max(xs) if xs else 1,
        "min_y": min(ys) if ys else 0,
        "max_y": max(ys) if ys else 1,
    }
    return {
        "case_id": CASE_ID,
        "route_folder": ROUTE_FOLDER,
        "activity_ids": ACTIVITY_IDS,
        "route": route,
        "activities": activities,
        "features": features,
        "control_points": control_points,
        "corridors": corridors,
        "bounds": bounds,
        "state_colors": STATE_COLORS,
        "phase_colors": PHASE_COLORS,
        "risk_colors": RISK_COLORS,
    }


def html_page(data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>IB3F activity story map v2 - qixing repaired review</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; color: #172033; background: #f8fafc; }}
    header {{ padding: 18px 22px; background: #0f172a; color: white; }}
    header h1 {{ margin: 0 0 8px; font-size: 22px; }}
    header p {{ margin: 3px 0; color: #cbd5e1; }}
    main {{ display: grid; grid-template-columns: minmax(720px, 1fr) 360px; min-height: calc(100vh - 120px); }}
    #boardWrap {{ position: relative; padding: 16px; }}
    svg {{ width: 100%; height: calc(100vh - 160px); background: white; border: 1px solid #cbd5e1; border-radius: 8px; }}
    aside {{ border-left: 1px solid #cbd5e1; background: white; padding: 16px; overflow: auto; }}
    select, label {{ font-size: 14px; }}
    .controls {{ display: grid; gap: 8px; margin-bottom: 14px; }}
    .checklist {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }}
    .toggle-row {{ display: flex; gap: 14px; flex-wrap: wrap; }}
    .summary table {{ border-collapse: collapse; width: 100%; }}
    .summary td {{ border-bottom: 1px solid #e2e8f0; padding: 5px 3px; font-size: 13px; vertical-align: top; }}
    .summary td:first-child {{ color: #64748b; width: 42%; }}
    .legend {{ display: grid; gap: 5px; margin-top: 12px; font-size: 13px; }}
    .swatch {{ display: inline-block; width: 12px; height: 12px; border-radius: 2px; margin-right: 6px; vertical-align: -1px; }}
    #tooltip {{ position: fixed; pointer-events: none; display: none; max-width: 330px; padding: 8px 10px; border: 1px solid #94a3b8; background: rgba(255,255,255,.97); box-shadow: 0 8px 20px rgba(15,23,42,.18); font-size: 12px; line-height: 1.35; border-radius: 6px; z-index: 10; }}
    .marker-label {{ font-size: 11px; fill: #0f172a; paint-order: stroke; stroke: white; stroke-width: 3px; }}
    .axis-note {{ color: #475569; font-size: 13px; line-height: 1.45; }}
    @media (max-width: 980px) {{ main {{ grid-template-columns: 1fr; }} aside {{ border-left: 0; border-top: 1px solid #cbd5e1; }} svg {{ height: 70vh; }} }}
  </style>
</head>
<body>
  <header>
    <h1>IB3F activity story map v2 - qixing repaired review</h1>
    <p>This page shows how each activity moved along the qixing repaired route baseline.</p>
    <p>It is for activity feature review, not route-choice classification. Route-choice is not forced.</p>
    <p>15_1 is review-required because low on_route_ratio.</p>
  </header>
  <main>
    <section id="boardWrap">
      <svg id="board" aria-label="activity story map"></svg>
      <div id="tooltip"></div>
    </section>
    <aside>
      <div class="controls">
        <label>Activity
          <select id="activitySelect"></select>
        </label>
        <label>Point color
          <select id="colorMode">
            <option value="phase">candidate_phase</option>
            <option value="state">route_progress_state</option>
            <option value="speed">implied_route_speed_mps</option>
            <option value="hr">heart_rate_bpm</option>
            <option value="offset">offset_m</option>
          </select>
        </label>
        <div class="toggle-row">
          <label><input id="rawToggle" type="checkbox" checked> raw GPS trajectory</label>
          <label><input id="projectedToggle" type="checkbox" checked> projected route trajectory</label>
          <label><input id="timeLabelToggle" type="checkbox" checked> time labels</label>
        </div>
        <div class="checklist">
          <label><input type="checkbox" class="stateToggle" value="on_route_reliable" checked> on-route</label>
          <label><input type="checkbox" class="stateToggle" value="off_route_projection_only" checked> off-route</label>
          <label><input type="checkbox" class="stateToggle" value="near_route_low_confidence" checked> low confidence</label>
          <label><input type="checkbox" class="stateToggle" value="branch_ambiguous_projection" checked> branch ambiguous</label>
        </div>
      </div>
      <div class="summary">
        <h2>Feature summary</h2>
        <div id="summaryPanel"></div>
      </div>
      <div class="legend">
        <div><span class="swatch" style="background:#2563eb"></span>ascent phase</div>
        <div><span class="swatch" style="background:#db2777"></span>summit-near phase</div>
        <div><span class="swatch" style="background:#059669"></span>descent phase</div>
        <div><span class="swatch" style="background:#16a34a"></span>usable / on-route reliable</div>
        <div><span class="swatch" style="background:#dc2626"></span>off-route projection only / high risk</div>
        <div><span class="swatch" style="background:#f59e0b"></span>near-route low confidence / moderate risk</div>
        <div><span class="swatch" style="background:#7c3aed"></span>branch ambiguous projection</div>
        <div><span class="swatch" style="background:#334155"></span>raw GPS trajectory</div>
        <div><span class="swatch" style="background:#0284c7"></span>projected route trajectory</div>
      </div>
      <p class="axis-note">Core geometry and activity points are embedded in this HTML. No network basemap is required.</p>
    </aside>
  </main>
<script>
const DATA = {payload};
const svg = document.getElementById('board');
const tooltip = document.getElementById('tooltip');
const activitySelect = document.getElementById('activitySelect');
const colorMode = document.getElementById('colorMode');
const rawToggle = document.getElementById('rawToggle');
const projectedToggle = document.getElementById('projectedToggle');
const timeLabelToggle = document.getElementById('timeLabelToggle');
const summaryPanel = document.getElementById('summaryPanel');
const NS = 'http://www.w3.org/2000/svg';

for (const id of DATA.activity_ids) {{
  const opt = document.createElement('option');
  opt.value = id;
  opt.textContent = id;
  activitySelect.appendChild(opt);
}}

function esc(v) {{
  return String(v ?? '').replace(/[&<>"']/g, s => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[s]));
}}
function fmt(v, d=3) {{
  const n = Number(v);
  return Number.isFinite(n) ? n.toFixed(d) : '';
}}
function sx(x) {{ return x; }}
function sy(y) {{ return y; }}
function make(tag, attrs={{}}) {{
  const el = document.createElementNS(NS, tag);
  for (const [k,v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
}}
function pointsAttr(points) {{
  return points.filter(p => p.x != null && p.y != null).map(p => `${{sx(p.x)}},${{sy(p.y)}}`).join(' ');
}}
function projectedPointsAttr(points) {{
  return points.filter(p => p.projected_x != null && p.projected_y != null).map(p => `${{sx(p.projected_x)}},${{sy(p.projected_y)}}`).join(' ');
}}
function stateVisible(state) {{
  const box = document.querySelector(`.stateToggle[value="${{state}}"]`);
  return box ? box.checked : true;
}}
function speedColor(v) {{
  const n = Number(v);
  if (!Number.isFinite(n)) return '#64748b';
  if (n < 0.3) return '#64748b';
  if (n < 0.8) return '#38bdf8';
  if (n < 1.4) return '#2563eb';
  return '#1e3a8a';
}}
function hrColor(v) {{
  const n = Number(v);
  if (!Number.isFinite(n)) return '#64748b';
  if (n < 120) return '#22c55e';
  if (n < 150) return '#f59e0b';
  if (n < 170) return '#ef4444';
  return '#7f1d1d';
}}
function phaseColor(v) {{
  return DATA.phase_colors[v || 'unknown'] || DATA.phase_colors.unknown || '#64748b';
}}
function offsetColor(v) {{
  const n = Number(v);
  if (!Number.isFinite(n)) return '#64748b';
  if (n <= 10) return '#22c55e';
  if (n <= 30) return '#f59e0b';
  if (n <= 50) return '#ef4444';
  return '#7f1d1d';
}}
function pointColor(p) {{
  const mode = colorMode.value;
  if (mode === 'phase') return phaseColor(p.candidate_phase || 'unknown');
  if (mode === 'speed') return speedColor(p.implied_route_speed_mps);
  if (mode === 'hr') return hrColor(p.heart_rate_bpm);
  if (mode === 'offset') return offsetColor(p.offset_m);
  return DATA.state_colors[p.route_progress_state] || '#64748b';
}}
function riskColor(band) {{ return DATA.risk_colors[band] || DATA.risk_colors.unknown; }}

function labelPoint(text, x, y, fill='#0f172a') {{
  const g = make('g');
  const bg = make('rect', {{x:x+5, y:y-18, width:Math.max(42, text.length * 6.5), height:16, rx:3, fill:'#ffffff', stroke:'#cbd5e1', opacity:0.92}});
  const t = make('text', {{x:x+9, y:y-6, class:'marker-label', fill:fill}});
  t.textContent = text;
  g.appendChild(bg);
  g.appendChild(t);
  svg.appendChild(g);
}}

function drawTimeLabels(points) {{
  if (!timeLabelToggle.checked || !points.length) return;
  const used = new Set();
  for (const p of points) {{
    const elapsed = Number(p.elapsed_sec);
    if (!Number.isFinite(elapsed)) continue;
    const bucket = Math.round(elapsed / 1200) * 1200;
    if (Math.abs(elapsed - bucket) <= 8 && bucket > 0 && !used.has(bucket)) {{
      used.add(bucket);
      labelPoint(`${{Math.round(bucket/60)}} min`, p.x, p.y, '#475569');
    }}
  }}
  const summit = points.find(p => p.candidate_phase === 'summit_self_near');
  if (summit) labelPoint('summit-near', summit.x, summit.y, '#db2777');
}}

function tooltipHtml(p) {{
  return `<b>${{esc(p.activity_id)}}</b><br>` +
    `timestamp_s: ${{fmt(p.timestamp_s,0)}}<br>` +
    `elapsed_sec: ${{fmt(p.elapsed_sec,0)}}<br>` +
    `lat/lon: ${{fmt(p.lat,7)}}, ${{fmt(p.lon,7)}}<br>` +
    `route_dist_m: ${{fmt(p.route_dist_m,2)}}<br>` +
    `reliable_route_dist_m: ${{fmt(p.reliable_route_dist_m,2)}}<br>` +
    `candidate_phase: ${{esc(p.candidate_phase)}}<br>` +
    `route_progress_state: ${{esc(p.route_progress_state)}}<br>` +
    `usable_on_route: ${{esc(p.usable_on_route)}}<br>` +
    `offset_m: ${{fmt(p.offset_m,2)}}<br>` +
    `speed_mps: ${{fmt(p.implied_route_speed_mps,3)}}<br>` +
    `heart_rate_bpm: ${{fmt(p.heart_rate_bpm,0)}}<br>` +
    `risk_band: ${{esc(p.risk_band)}}<br>` +
    `risk_score: ${{fmt(p.risk_score,3)}}`;
}}

function draw() {{
  svg.innerHTML = '';
  const pad = 55;
  const b = DATA.bounds;
  const width = Math.max(1, b.max_x - b.min_x) + pad * 2;
  const height = Math.max(1, b.max_y - b.min_y) + pad * 2;
  svg.setAttribute('viewBox', `${{b.min_x-pad}} ${{b.min_y-pad}} ${{width}} ${{height}}`);

  for (let i = 1; i < DATA.route.length; i++) {{
    const a = DATA.route[i-1], c = DATA.route[i];
    const line = make('line', {{x1:a.x, y1:a.y, x2:c.x, y2:c.y, stroke:riskColor(c.risk_band), 'stroke-width':5, opacity:0.72, 'stroke-linecap':'round'}});
    svg.appendChild(line);
  }}
  const axis = make('polyline', {{points:pointsAttr(DATA.route), fill:'none', stroke:'#0f172a', 'stroke-width':1.2, opacity:0.65}});
  svg.appendChild(axis);

  for (const corridor of DATA.corridors) {{
    if (!corridor.points.length) continue;
    const color = corridor.corridor_role === 'branch_corridor' ? '#0f766e' : corridor.corridor_role === 'ambiguous_corridor' ? '#9333ea' : '#64748b';
    const poly = make('polyline', {{points:pointsAttr(corridor.points), fill:'none', stroke:color, 'stroke-width': corridor.corridor_role === 'branch_corridor' ? 9 : 5, opacity:0.42, 'stroke-dasharray': corridor.corridor_role === 'ambiguous_corridor' ? '5 5' : ''}});
    poly.appendChild(make('title'));
    poly.querySelector('title').textContent = `${{corridor.corridor_id}} ${{corridor.start_dist_m}}-${{corridor.end_dist_m}}m`;
    svg.appendChild(poly);
  }}

  const selected = activitySelect.value || DATA.activity_ids[0];
  const points = DATA.activities[selected] || [];
  const visible = points.filter(p => stateVisible(p.route_progress_state));
  if (rawToggle.checked) {{
    const rawPath = make('polyline', {{points:pointsAttr(points), fill:'none', stroke:'#334155', 'stroke-width':1.7, opacity:0.66}});
    rawPath.appendChild(make('title'));
    rawPath.querySelector('title').textContent = 'raw GPS trajectory by timestamp order';
    svg.appendChild(rawPath);
  }}
  if (projectedToggle.checked) {{
    const projectedPath = make('polyline', {{points:projectedPointsAttr(points), fill:'none', stroke:'#0284c7', 'stroke-width':2.0, opacity:0.78, 'stroke-dasharray':'7 5'}});
    projectedPath.appendChild(make('title'));
    projectedPath.querySelector('title').textContent = 'projected route trajectory by timestamp order';
    svg.appendChild(projectedPath);
  }}
  points.forEach((p, idx) => {{
    if (p.x == null || p.y == null || !stateVisible(p.route_progress_state)) return;
    const r = idx === 0 || idx === points.length - 1 ? 5 : 2.7;
    const circle = make('circle', {{cx:p.x, cy:p.y, r:r, fill:pointColor(p), stroke:'#ffffff', 'stroke-width':0.6, opacity:0.88}});
    circle.addEventListener('mousemove', ev => {{
      tooltip.style.display = 'block';
      tooltip.style.left = `${{ev.clientX + 14}}px`;
      tooltip.style.top = `${{ev.clientY + 14}}px`;
      tooltip.innerHTML = tooltipHtml(p);
    }});
    circle.addEventListener('mouseleave', () => tooltip.style.display = 'none');
    svg.appendChild(circle);
  }});
  drawTimeLabels(points);

  if (points.length) {{
    const start = points[0], end = points[points.length - 1];
    [['start', start, '#22c55e'], ['end', end, '#ef4444']].forEach(([label, p, color]) => {{
      const c = make('circle', {{cx:p.x, cy:p.y, r:7, fill:color, stroke:'#0f172a', 'stroke-width':1.2}});
      svg.appendChild(c);
      const t = make('text', {{x:p.x+8, y:p.y-8, class:'marker-label'}});
      t.textContent = label;
      svg.appendChild(t);
    }});
  }}

  for (const cp of DATA.control_points) {{
    const c = make('circle', {{cx:cp.x, cy:cp.y, r:7, fill:'#f8fafc', stroke:'#0f172a', 'stroke-width':2}});
    svg.appendChild(c);
    const t = make('text', {{x:cp.x+9, y:cp.y+4, class:'marker-label'}});
    t.textContent = cp.label;
    svg.appendChild(t);
  }}
  renderSummary(selected);
}}

function renderSummary(activityId) {{
  const f = DATA.features[activityId] || {{}};
  const rows = [
    ['activity_quality_flag', f.activity_quality_flag],
    ['on_route_ratio', fmt(f.on_route_ratio,4)],
    ['speed_available', f.speed_available],
    ['hr_available', f.hr_available],
    ['moderate_risk_ratio', fmt(f.moderate_risk_ratio,4)],
    ['high_risk_ratio', fmt(f.high_risk_ratio,4)],
    ['route_risk_join_coverage_ratio', fmt(f.route_risk_join_coverage_ratio,4)],
    ['route_choice_review_required', f.route_choice_review_required],
    ['remap_review_note', f.remap_review_note],
  ];
  summaryPanel.innerHTML = '<table>' + rows.map(([k,v]) => `<tr><td>${{esc(k)}}</td><td>${{esc(v)}}</td></tr>`).join('') + '</table>' +
    '<p class="axis-note"><b>Interpretation aid:</b> This map does not force route-choice classification. Use ascent/descent phase and raw GPS trajectory to visually review whether the activity follows via_up or via_down corridor.</p>';
}}

activitySelect.addEventListener('change', draw);
colorMode.addEventListener('change', draw);
rawToggle.addEventListener('change', draw);
projectedToggle.addEventListener('change', draw);
timeLabelToggle.addEventListener('change', draw);
document.querySelectorAll('.stateToggle').forEach(box => box.addEventListener('change', draw));
activitySelect.value = DATA.activity_ids[0];
draw();
</script>
</body>
</html>"""


def main() -> int:
    data = load_data()
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html_page(data), encoding="utf-8")
    print(f"HTML: {OUT_HTML.resolve()}")
    print(f"activities: {', '.join(ACTIVITY_IDS)}")
    print("supports_candidate_phase_coloring: true")
    print("supports_speed_hr_offset_coloring: true")
    print("includes_direction_time_labels: true")
    print("includes_raw_vs_projected_toggle: true")
    print("includes_speed_hr_tooltip: true")
    print("includes_route_progress_layers: true")
    print("includes_feature_summary_panel: true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
