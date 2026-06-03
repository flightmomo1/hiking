from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from html import escape

import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString, MultiLineString, Point


def read_csv_required(fp: Path, name: str) -> pd.DataFrame:
    if not fp.exists():
        raise FileNotFoundError(f"{name} not found: {fp}")
    return pd.read_csv(fp, low_memory=False)


def find_lat_lon_cols(df: pd.DataFrame) -> tuple[str, str]:
    candidates = [
        ("lat", "lon"),
        ("latitude", "longitude"),
        ("position_lat_deg", "position_long_deg"),
        ("position_lat", "position_long"),
        ("gps_lat", "gps_lon"),
        ("raw_lat", "raw_lon"),
    ]
    for lat_col, lon_col in candidates:
        if lat_col in df.columns and lon_col in df.columns:
            return lat_col, lon_col
    raise ValueError("Cannot find lat/lon columns.")


def find_first_existing(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def downsample_df(df: pd.DataFrame, max_n: int) -> pd.DataFrame:
    if len(df) <= max_n:
        return df.copy()
    step = max(1, len(df) // max_n)
    return df.iloc[::step].copy()


def downsample_points(points: list[list[float]], max_n: int) -> list[list[float]]:
    if len(points) <= max_n:
        return points
    step = max(1, len(points) // max_n)
    return points[::step]


def extract_route_line_coords(route_geojson_fp: Path, max_points: int) -> list[list[float]]:
    if not route_geojson_fp.exists():
        return []

    gdf = gpd.read_file(route_geojson_fp)
    if gdf.empty:
        return []

    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    point_rows = gdf[gdf.geometry.geom_type == "Point"].copy()
    if len(point_rows) >= 2:
        dist_col = find_first_existing(point_rows, ["dist_m", "route_dist_m"])
        if dist_col:
            point_rows[dist_col] = pd.to_numeric(point_rows[dist_col], errors="coerce")
            point_rows = point_rows.sort_values(dist_col)

        coords = [[geom.y, geom.x] for geom in point_rows.geometry if isinstance(geom, Point)]
        return downsample_points(coords, max_points)

    coords = []
    for geom in gdf.geometry:
        if geom is None:
            continue
        if isinstance(geom, LineString):
            coords.extend([[y, x] for x, y in geom.coords])
        elif isinstance(geom, MultiLineString):
            for line in geom.geoms:
                coords.extend([[y, x] for x, y in line.coords])

    return downsample_points(coords, max_points)


def safe_value(v):
    if pd.isna(v):
        return None
    if isinstance(v, (int, float, str, bool)):
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        return v
    try:
        if hasattr(v, "item"):
            return v.item()
    except Exception:
        pass
    return str(v)


def make_sample_records(df: pd.DataFrame, lat_col: str, lon_col: str, max_points: int) -> list[dict]:
    work = df.copy()

    work[lat_col] = pd.to_numeric(work[lat_col], errors="coerce")
    work[lon_col] = pd.to_numeric(work[lon_col], errors="coerce")
    work = work.dropna(subset=[lat_col, lon_col]).copy()

    work = downsample_df(work, max_points).copy()

    # Detect usable columns
    elapsed_col = find_first_existing(work, ["elapsed_sec", "time_sec", "timestamp"])
    hr_col = find_first_existing(work, ["heart_rate_bpm", "heart_rate", "hr_bpm"])
    offset_col = find_first_existing(work, [
        "offset_to_mainline_m",
        "offset_m",
        "nearest_mainline_offset_m",
        "nearest_route_offset_m",
    ])

    keep_cols = [
        elapsed_col,
        hr_col,
        offset_col,
        "activity_id",
        "distance_m",
        "reliable_route_dist_m",
        "projected_route_dist_m",
        "route_dist_m",
        "route_context_dist_m",
        "route_context_join_dist_diff_m",
        "route_context_ele_smooth",
        "route_context_slope_band_window_nlsc",
        "route_context_osm_terrain_combined_risk_score",
        "route_context_osm_terrain_combined_risk_band",
        "route_context_osm_highway",
        "route_context_osm_surface",
        "usable_on_route",
        "excluded_reason",
        "route_context_match_status",
    ]
    keep_cols = [c for c in keep_cols if c is not None and c in work.columns]

    records = []
    for i, (_, row) in enumerate(work.iterrows()):
        match_status = str(row.get("route_context_match_status", ""))
        model_status = str(row.get("route_context_model_status", ""))
        model_status_v1c = str(row.get("route_context_model_status_v1c", ""))

        # Prefer v1c status, then v1b status, then raw match status.
        if model_status_v1c and model_status_v1c != "nan":
            status = model_status_v1c
        elif model_status and model_status != "nan":
            status = model_status
        else:
            status = match_status

        if status == "matched_core_clean":
            color = "#1f78b4"      # blue
        elif status == "matched_core_refit_from_anchors":
            color = "#00a6a6"      # cyan / teal
        elif status == "matched_core":
            color = "#1f78b4"      # v1b blue
        elif status == "matched_low_confidence_offset":
            color = "#fdae61"      # yellow/orange
        elif status == "no_activity_route_dist":
            color = "#e66101"      # orange
        elif status in {"unmatched", "off_branch_or_excluded"}:
            color = "#d7191c"      # red
        elif match_status == "matched":
            color = "#1f78b4"
        else:
            color = "#999999"

        rec = {
            "sample_id": i,
            "lat": float(row[lat_col]),
            "lon": float(row[lon_col]),
            "status": status,
            "route_context_match_status": match_status,
            "route_context_model_status": model_status,
            "color": color,
        }

        for c in keep_cols:
            rec[c] = safe_value(row[c])

        # Normalized aliases for JS profile
        rec["_x"] = safe_value(row[elapsed_col]) if elapsed_col else i
        rec["_hr"] = safe_value(row[hr_col]) if hr_col else None
        rec["_offset"] = safe_value(row[offset_col]) if offset_col else None
        rec["_ele"] = safe_value(row["route_context_ele_smooth"]) if "route_context_ele_smooth" in row.index else None

        records.append(rec)

    return records


def js_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, allow_nan=False)


def build_svg_panel_js(
    panel_id: str,
    title: str,
    y_key: str,
    y_label: str,
    records_var: str = "records",
) -> str:
    # JS function call creates the SVG in browser.
    return f"""
      <div class="profile-panel">
        <h3>{escape(title)}</h3>
        <div id="{panel_id}" class="svg-holder"></div>
      </div>
      <script>
        createSvgPanel("{panel_id}", "{escape(title)}", "{y_key}", "{escape(y_label)}", {records_var});
      </script>
    """


def build_html(
    records: list[dict],
    route_coords: list[list[float]],
    route_folder: str,
    activity_id: str,
    out_fp: Path,
    source_rows: int,
) -> None:
    matched = sum(1 for r in records if r.get("status") == "matched")
    no_dist = sum(1 for r in records if r.get("status") == "no_activity_route_dist")
    unmatched = sum(1 for r in records if r.get("status") == "unmatched")

    # Center
    if records:
        center_lat = sorted([r["lat"] for r in records])[len(records) // 2]
        center_lon = sorted([r["lon"] for r in records])[len(records) // 2]
    else:
        center_lat, center_lon = 25.0, 121.0

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Linked QA: {escape(route_folder)} {escape(activity_id)}</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    body {{
      font-family: Arial, "Microsoft JhengHei", sans-serif;
      margin: 0;
      padding: 0;
      background: #f7f7f7;
    }}
    .section {{
      margin: 12px;
      padding: 12px;
      background: white;
      border: 1px solid #ddd;
      border-radius: 8px;
    }}
    #map {{
      width: 100%;
      height: 620px;
      border: 1px solid #ccc;
    }}
    .summary {{
      line-height: 1.5;
      font-size: 14px;
    }}
    .legend span {{
      display: inline-block;
      margin-right: 18px;
    }}
    .dot {{
      display: inline-block;
      width: 10px;
      height: 10px;
      border-radius: 50%;
      margin-right: 4px;
    }}
    .svg-holder {{
      overflow-x: auto;
      border: 1px solid #ddd;
      background: #fff;
    }}
    .profile-panel h3 {{
      margin-bottom: 6px;
    }}
    .info-box {{
      white-space: pre-wrap;
      font-family: Consolas, monospace;
      font-size: 13px;
      background: #fafafa;
      border: 1px solid #ddd;
      padding: 10px;
      max-height: 260px;
      overflow-y: auto;
    }}
    circle.profile-point {{
      cursor: pointer;
    }}
  </style>
</head>
<body>
  <div class="section summary">
    <h2>activity_points_osm_nlsc_corrected_v1 linked QA</h2>
    <div><b>route_folder</b>: {escape(route_folder)}</div>
    <div><b>activity_id</b>: {escape(activity_id)}</div>
    <div><b>source_rows</b>: {source_rows}</div>
    <div><b>sampled_records</b>: {len(records)}</div>
    <div><b>matched sampled</b>: {matched}</div>
    <div><b>no_activity_route_dist sampled</b>: {no_dist}</div>
    <div><b>unmatched sampled</b>: {unmatched}</div>
    <div class="legend">
      <span><i class="dot" style="background:#1f78b4"></i>matched</span>
      <span><i class="dot" style="background:#e66101"></i>no_activity_route_dist</span>
      <span><i class="dot" style="background:#d7191c"></i>unmatched</span>
    </div>
    <p>
      Hover or click profile points to move the map highlight marker.
      Click map points to inspect the same record in the info box.
      This is a downsampled QA view; CSV remains the source of truth.
    </p>
  </div>

  <div class="section">
    <h3>1. Linked 2D map</h3>
    <div id="map"></div>
  </div>

  <div class="section">
    <h3>2. Selected point info</h3>
    <div id="info" class="info-box">Hover or click a profile point / map point.</div>
  </div>

  <div class="section">
    <h3>3. Linked profiles</h3>
    <div id="profile-container"></div>
  </div>

<script>
const records = {js_json(records)};
const routeCoords = {js_json(route_coords)};

const map = L.map('map', {{ preferCanvas: true }}).setView([{center_lat}, {center_lon}], 15);
L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap contributors'
}}).addTo(map);

if (routeCoords.length > 1) {{
  L.polyline(routeCoords, {{
    color: '#111111',
    weight: 4,
    opacity: 0.8
  }}).addTo(map).bindTooltip('simplified IB1E route axis');
}}

const trackCoords = records.map(r => [r.lat, r.lon]);
if (trackCoords.length > 1) {{
  L.polyline(trackCoords, {{
    color: '#777777',
    weight: 2,
    opacity: 0.55
  }}).addTo(map).bindTooltip('sampled raw activity track');
}}

let highlightMarker = null;
let mapMarkers = {{}};

function formatRecord(r) {{
  const keys = [
    'sample_id',
    'activity_id',
    'elapsed_sec',
    'timestamp',
    'heart_rate_bpm',
    'distance_m',
    'reliable_route_dist_m',
    'projected_route_dist_m',
    'route_dist_m',
    'route_context_dist_m',
    'route_context_join_dist_diff_m',
    'offset_m',
    'offset_to_mainline_m',
    'route_context_ele_smooth',
    'route_context_slope_band_window_nlsc',
    'route_context_osm_terrain_combined_risk_score',
    'route_context_osm_terrain_combined_risk_band',
    'route_context_osm_highway',
    'route_context_osm_surface',
    'usable_on_route',
    'excluded_reason',
    'route_context_match_status'
  ];

  let lines = [];
  for (const k of keys) {{
    if (r[k] !== undefined && r[k] !== null) {{
      lines.push(k + ': ' + r[k]);
    }}
  }}
  return lines.join('\\n');
}}

function setInfo(r) {{
  document.getElementById('info').textContent = formatRecord(r);
}}

function showHighlight(r, pan=false) {{
  const latlng = [r.lat, r.lon];

  if (!highlightMarker) {{
    highlightMarker = L.circleMarker(latlng, {{
      radius: 9,
      color: '#ffff00',
      weight: 4,
      fill: false,
      opacity: 1.0
    }}).addTo(map);
  }} else {{
    highlightMarker.setLatLng(latlng);
  }}

  if (pan) {{
    map.panTo(latlng);
  }}

  setInfo(r);
}}

for (const r of records) {{
  const marker = L.circleMarker([r.lat, r.lon], {{
    radius: 4,
    color: r.color,
    fillColor: r.color,
    fillOpacity: 0.75,
    opacity: 0.75,
    weight: 1
  }}).addTo(map);

  marker.on('mouseover', () => showHighlight(r, false));
  marker.on('click', () => showHighlight(r, true));
  marker.bindTooltip(
    'sample_id: ' + r.sample_id +
    '<br>status: ' + r.status +
    '<br>elapsed: ' + (r.elapsed_sec ?? '') +
    '<br>HR: ' + (r.heart_rate_bpm ?? '') +
    '<br>ele: ' + (r.route_context_ele_smooth ?? '')
  );

  mapMarkers[r.sample_id] = marker;
}}

function createSvgPanel(parentId, title, yKey, yLabel, recs) {{
  const parent = document.getElementById(parentId);
  const valid = recs.filter(r => r._x !== null && r[yKey] !== undefined && r[yKey] !== null);

  if (valid.length === 0) {{
    parent.innerHTML = '<p>No valid data for ' + yKey + '</p>';
    return;
  }}

  const width = 1200;
  const height = 260;
  const left = 70;
  const right = 20;
  const top = 25;
  const bottom = 42;
  const plotW = width - left - right;
  const plotH = height - top - bottom;

  const xs = valid.map(r => Number(r._x)).filter(v => !Number.isNaN(v));
  const ys = valid.map(r => Number(r[yKey])).filter(v => !Number.isNaN(v));

  let xMin = Math.min(...xs);
  let xMax = Math.max(...xs);
  let yMin = Math.min(...ys);
  let yMax = Math.max(...ys);

  if (xMin === xMax) xMax = xMin + 1;
  if (yMin === yMax) yMax = yMin + 1;

  function sx(x) {{
    return left + (Number(x) - xMin) / (xMax - xMin) * plotW;
  }}

  function sy(y) {{
    return top + (yMax - Number(y)) / (yMax - yMin) * plotH;
  }}

  const svgNS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(svgNS, 'svg');
  svg.setAttribute('width', width);
  svg.setAttribute('height', height);
  svg.setAttribute('viewBox', `0 0 ${{width}} ${{height}}`);

  const bg = document.createElementNS(svgNS, 'rect');
  bg.setAttribute('x', 0);
  bg.setAttribute('y', 0);
  bg.setAttribute('width', width);
  bg.setAttribute('height', height);
  bg.setAttribute('fill', '#ffffff');
  svg.appendChild(bg);

  function line(x1, y1, x2, y2, color='#333') {{
    const el = document.createElementNS(svgNS, 'line');
    el.setAttribute('x1', x1);
    el.setAttribute('y1', y1);
    el.setAttribute('x2', x2);
    el.setAttribute('y2', y2);
    el.setAttribute('stroke', color);
    svg.appendChild(el);
  }}

  line(left, top, left, height-bottom);
  line(left, height-bottom, width-right, height-bottom);

  const label = document.createElementNS(svgNS, 'text');
  label.setAttribute('x', 8);
  label.setAttribute('y', top + 14);
  label.setAttribute('font-size', 12);
  label.textContent = yLabel;
  svg.appendChild(label);

  const ymaxLabel = document.createElementNS(svgNS, 'text');
  ymaxLabel.setAttribute('x', left);
  ymaxLabel.setAttribute('y', top - 7);
  ymaxLabel.setAttribute('font-size', 12);
  ymaxLabel.textContent = 'y max: ' + yMax.toFixed(2);
  svg.appendChild(ymaxLabel);

  const xminLabel = document.createElementNS(svgNS, 'text');
  xminLabel.setAttribute('x', left);
  xminLabel.setAttribute('y', height - 12);
  xminLabel.setAttribute('font-size', 12);
  xminLabel.textContent = 'x min: ' + xMin.toFixed(2);
  svg.appendChild(xminLabel);

  const xmaxLabel = document.createElementNS(svgNS, 'text');
  xmaxLabel.setAttribute('x', width - 170);
  xmaxLabel.setAttribute('y', height - 12);
  xmaxLabel.setAttribute('font-size', 12);
  xmaxLabel.textContent = 'x max: ' + xMax.toFixed(2);
  svg.appendChild(xmaxLabel);

  const matched = valid.filter(r => r.status === 'matched');
  if (matched.length >= 2) {{
    const poly = document.createElementNS(svgNS, 'polyline');
    poly.setAttribute('points', matched.map(r => `${{sx(r._x).toFixed(2)}},${{sy(r[yKey]).toFixed(2)}}`).join(' '));
    poly.setAttribute('fill', 'none');
    poly.setAttribute('stroke', '#1f78b4');
    poly.setAttribute('stroke-width', '1.5');
    poly.setAttribute('stroke-opacity', '0.45');
    svg.appendChild(poly);
  }}

  for (const r of valid) {{
    const c = document.createElementNS(svgNS, 'circle');
    c.setAttribute('cx', sx(r._x));
    c.setAttribute('cy', sy(r[yKey]));
    c.setAttribute('r', 4);
    c.setAttribute('fill', r.color);
    c.setAttribute('fill-opacity', 0.75);
    c.setAttribute('class', 'profile-point');

    const titleEl = document.createElementNS(svgNS, 'title');
    titleEl.textContent = formatRecord(r);
    c.appendChild(titleEl);

    c.addEventListener('mouseover', () => showHighlight(r, false));
    c.addEventListener('click', () => showHighlight(r, true));

    svg.appendChild(c);
  }}

  parent.appendChild(svg);
}}

const container = document.getElementById('profile-container');

function addPanelDiv(id, title) {{
  const panel = document.createElement('div');
  panel.className = 'profile-panel';
  const h3 = document.createElement('h3');
  h3.textContent = title;
  const holder = document.createElement('div');
  holder.id = id;
  holder.className = 'svg-holder';
  panel.appendChild(h3);
  panel.appendChild(holder);
  container.appendChild(panel);
}}

addPanelDiv('ele-panel', 'Route-context elevation');
createSvgPanel('ele-panel', 'Route-context elevation', 'route_context_ele_smooth', 'elevation m', records);

addPanelDiv('hr-panel', 'Heart rate');
createSvgPanel('hr-panel', 'Heart rate', 'heart_rate_bpm', 'HR bpm', records);

addPanelDiv('offset-panel', 'Offset to mainline');
createSvgPanel('offset-panel', 'Offset to mainline', 'offset_m', 'offset m', records);
</script>
</body>
</html>
"""

    out_fp.write_text(html, encoding="utf-8")


def build_linked_qa(
    corrected_fp: Path,
    route_geojson_fp: Path,
    route_folder: str,
    activity_id: str,
    out_dir: Path,
    max_route_points: int,
    max_sample_points: int,
) -> Path:
    df = read_csv_required(corrected_fp, "corrected activity points")
    lat_col, lon_col = find_lat_lon_cols(df)

    source_rows = len(df)
    records = make_sample_records(df, lat_col, lon_col, max_sample_points)
    route_coords = extract_route_line_coords(route_geojson_fp, max_route_points)

    out_root = out_dir / route_folder / activity_id
    out_root.mkdir(parents=True, exist_ok=True)

    out_fp = out_root / f"{route_folder}_{activity_id}_activity_points_osm_nlsc_corrected_linked_qa.html"

    build_html(
        records=records,
        route_coords=route_coords,
        route_folder=route_folder,
        activity_id=activity_id,
        out_fp=out_fp,
        source_rows=source_rows,
    )

    return out_fp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Linked map/profile QA for activity_points_osm_nlsc_corrected_v1."
    )
    parser.add_argument("--route-folder", default="qixing_lengshuikeng")
    parser.add_argument("--activity-id", required=True)
    parser.add_argument("--corrected-fp", required=True)
    parser.add_argument("--route-geojson-fp", required=True)
    parser.add_argument(
        "--out-dir",
        default=r"outputs\activity_points_osm_nlsc_corrected_v1_linked_qa",
    )
    parser.add_argument("--max-route-points", type=int, default=300)
    parser.add_argument("--max-sample-points", type=int, default=900)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    out_fp = build_linked_qa(
        corrected_fp=Path(args.corrected_fp),
        route_geojson_fp=Path(args.route_geojson_fp),
        route_folder=args.route_folder,
        activity_id=args.activity_id,
        out_dir=Path(args.out_dir),
        max_route_points=args.max_route_points,
        max_sample_points=args.max_sample_points,
    )

    print("Linked QA written:")
    print(out_fp)


if __name__ == "__main__":
    main()
