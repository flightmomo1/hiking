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


def load_route_points(route_geojson_fp: Path, max_route_points: int) -> tuple[list[list[float]], pd.DataFrame]:
    gdf = gpd.read_file(route_geojson_fp)

    if gdf.empty:
        return [], pd.DataFrame()

    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    point_rows = gdf[gdf.geometry.geom_type == "Point"].copy()

    if len(point_rows) >= 2:
        dist_col = find_first_existing(point_rows, ["dist_m", "route_dist_m"])
        if dist_col is None:
            raise ValueError("Route GeoJSON point layer has no dist_m / route_dist_m column.")

        point_rows[dist_col] = pd.to_numeric(point_rows[dist_col], errors="coerce")
        point_rows = point_rows.dropna(subset=[dist_col]).sort_values(dist_col).copy()

        point_rows["__route_dist_m"] = point_rows[dist_col]
        point_rows["__lat"] = point_rows.geometry.y
        point_rows["__lon"] = point_rows.geometry.x

        coords = point_rows[["__lat", "__lon"]].values.tolist()
        if len(coords) > max_route_points:
            step = max(1, len(coords) // max_route_points)
            coords_sampled = coords[::step]
        else:
            coords_sampled = coords

        return coords_sampled, point_rows[["__route_dist_m", "__lat", "__lon"]].copy()

    coords = []
    for geom in gdf.geometry:
        if geom is None:
            continue
        if isinstance(geom, LineString):
            coords.extend([[y, x] for x, y in geom.coords])
        elif isinstance(geom, MultiLineString):
            for line in geom.geoms:
                coords.extend([[y, x] for x, y in line.coords])

    if len(coords) > max_route_points:
        step = max(1, len(coords) // max_route_points)
        coords = coords[::step]

    return coords, pd.DataFrame()


def nearest_route_target(route_points: pd.DataFrame, route_dist_m: float) -> tuple[float | None, float | None, float | None]:
    if route_points.empty or pd.isna(route_dist_m):
        return None, None, None

    dist = pd.to_numeric(route_points["__route_dist_m"], errors="coerce")
    idx = (dist - float(route_dist_m)).abs().idxmin()

    return (
        safe_value(route_points.loc[idx, "__lat"]),
        safe_value(route_points.loc[idx, "__lon"]),
        safe_value(route_points.loc[idx, "__route_dist_m"]),
    )


def make_records(df: pd.DataFrame, route_points: pd.DataFrame, max_sample_points: int) -> list[dict]:
    lat_col, lon_col = find_lat_lon_cols(df)

    work = df.copy()
    work[lat_col] = pd.to_numeric(work[lat_col], errors="coerce")
    work[lon_col] = pd.to_numeric(work[lon_col], errors="coerce")
    work = work.dropna(subset=[lat_col, lon_col]).copy()

    # Keep all refit points, and sample other statuses.
    if "route_context_model_status_v1f" in work.columns:
        status_col = "route_context_model_status_v1f"
    elif "route_context_model_status_v1e" in work.columns:
        status_col = "route_context_model_status_v1e"
    elif "route_context_model_status_v1d" in work.columns:
        status_col = "route_context_model_status_v1d"
    else:
        status_col = "route_context_model_status_v1c"

    refit = work[work[status_col].astype(str).isin([
        "matched_core_refit_from_anchors",
        "matched_core_refit_to_summit",
        "matched_core_recovered_from_isolated_branch_ambiguous",
        "matched_core_recovered_from_route_corridor_ambiguity",
    ])].copy()
    lowconf = work[work[status_col].astype(str).eq("matched_low_confidence_offset")].copy()
    clean = work[work[status_col].astype(str).eq("matched_core_clean")].copy()
    nodist = work[work[status_col].astype(str).eq("no_activity_route_dist")].copy()

    clean_s = downsample_df(clean, max(80, max_sample_points // 5))
    nodist_s = downsample_df(nodist, max(80, max_sample_points // 5))
    lowconf_s = downsample_df(lowconf, max(120, max_sample_points // 4))

    combined = pd.concat([clean_s, nodist_s, lowconf_s, refit], ignore_index=True, sort=False)

    records = []

    for i, row in combined.iterrows():
        status = str(row.get("route_context_model_status_v1f", row.get("route_context_model_status_v1e", row.get("route_context_model_status_v1d", row.get("route_context_model_status_v1c", "")))))
        color = "#999999"

        if status == "matched_core_clean":
            color = "#1f78b4"
        elif status == "matched_core_refit_from_anchors":
            color = "#00a6a6"
        elif status == "matched_core_refit_to_summit":
            color = "#7b3294"
        elif status == "matched_core_recovered_from_isolated_branch_ambiguous":
            color = "#2ca25f"
        elif status == "matched_core_recovered_from_route_corridor_ambiguity":
            color = "#006d2c"
        elif status == "matched_low_confidence_offset":
            color = "#fdae61"
        elif status == "no_activity_route_dist":
            color = "#e66101"
        elif status in {"unmatched", "off_branch_or_excluded"}:
            color = "#d7191c"

        refit_lat, refit_lon, refit_route_dist = (None, None, None)

        if status in {
            "matched_core_refit_from_anchors",
            "matched_core_refit_to_summit",
            "matched_core_recovered_from_isolated_branch_ambiguous",
        }:
            if "route_dist_refit_m_v1f" in row.index and pd.notna(row.get("route_dist_refit_m_v1f")):
                route_dist_refit = pd.to_numeric(pd.Series([row.get("route_dist_refit_m_v1f")]), errors="coerce").iloc[0]
            elif "route_dist_refit_m_v1e" in row.index and pd.notna(row.get("route_dist_refit_m_v1e")):
                route_dist_refit = pd.to_numeric(pd.Series([row.get("route_dist_refit_m_v1e")]), errors="coerce").iloc[0]
            elif "route_dist_refit_m_v1d" in row.index and pd.notna(row.get("route_dist_refit_m_v1d")):
                route_dist_refit = pd.to_numeric(pd.Series([row.get("route_dist_refit_m_v1d")]), errors="coerce").iloc[0]
            else:
                route_dist_refit = pd.to_numeric(pd.Series([row.get("route_dist_refit_m")]), errors="coerce").iloc[0]
            refit_lat, refit_lon, refit_route_dist = nearest_route_target(route_points, route_dist_refit)

        rec = {
            "sample_id": int(i),
            "lat": float(row[lat_col]),
            "lon": float(row[lon_col]),
            "status": status,
            "color": color,
            "refit_lat": refit_lat,
            "refit_lon": refit_lon,
            "refit_route_dist_m": refit_route_dist,
        }

        keep_cols = [
            "activity_id",
            "elapsed_sec",
            "heart_rate_bpm",
            "distance_m",
            "reliable_route_dist_m",
            "route_dist_refit_m",
            "route_dist_refit_method",
            "offset_m",
            "route_context_dist_m",
            "route_context_ele_smooth",
            "route_context_model_status_v1c",
            "route_context_model_usable_v1c",
            "route_context_model_reason_v1c",
            "route_context_model_status_v1d",
            "route_context_model_usable_v1d",
            "route_context_model_reason_v1d",
            "route_dist_refit_m_v1d",
            "route_dist_refit_method_v1d",
            "route_context_model_status_v1e",
            "route_context_model_usable_v1e",
            "route_context_model_reason_v1e",
            "route_dist_refit_m_v1e",
            "route_dist_refit_method_v1e",
            "isolated_orange_recovery_applied_v1e",
            "isolated_orange_recovery_block_reason_v1e",
            "route_context_model_status_v1f",
            "route_context_model_usable_v1f",
            "route_context_model_reason_v1f",
            "route_dist_refit_m_v1f",
            "route_dist_refit_method_v1f",
            "route_corridor_recovery_applied_v1f",
            "route_corridor_recovery_block_reason_v1f",
            "summit_route_dist_m_v1d",
            "summit_route_dist_delta_m_v1d",
            "summit_aware_refit_applied",
            "route_dist_refit_prev_anchor_route_dist_m",
            "route_dist_refit_next_anchor_route_dist_m",
            "route_dist_refit_anchor_gap_sec",
            "route_dist_refit_anchor_gap_route_m",
            "excluded_reason",
        ]

        for c in keep_cols:
            if c in row.index:
                rec[c] = safe_value(row[c])

        records.append(rec)

    return records


def js_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, allow_nan=False)


def build_html(records: list[dict], route_coords: list[list[float]], route_folder: str, activity_id: str, source_rows: int, out_fp: Path) -> None:
    center_lat = sorted([r["lat"] for r in records])[len(records) // 2] if records else 25.0
    center_lon = sorted([r["lon"] for r in records])[len(records) // 2] if records else 121.0

    refit_count = sum(1 for r in records if r["status"] == "matched_core_refit_from_anchors")
    lowconf_count = sum(1 for r in records if r["status"] == "matched_low_confidence_offset")

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Refit target QA: {escape(route_folder)} {escape(activity_id)}</title>
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
      height: 720px;
      border: 1px solid #ccc;
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
  </style>
</head>
<body>
  <div class="section">
    <h2>Refit target QA: original GPS point → fitted mainline target</h2>
    <div><b>route_folder</b>: {escape(route_folder)}</div>
    <div><b>activity_id</b>: {escape(activity_id)}</div>
    <div><b>source_rows</b>: {source_rows}</div>
    <div><b>sampled_records</b>: {len(records)}</div>
    <div><b>refit sampled / all refit</b>: {refit_count}</div>
    <div><b>low confidence sampled</b>: {lowconf_count}</div>
    <div class="legend">
      <span><i class="dot" style="background:#1f78b4"></i>matched_core_clean</span>
      <span><i class="dot" style="background:#00a6a6"></i>anchor refit original point</span>
      <span><i class="dot" style="background:#7b3294"></i>summit refit original point</span>
      <span><i class="dot" style="background:#2ca25f"></i>v1e isolated orange recovery</span>
      <span><i class="dot" style="background:#006d2c"></i>v1f route-corridor recovery</span>
      <span><i class="dot" style="background:#084081"></i>refit target on mainline / summit</span>
      <span><i class="dot" style="background:#fdae61"></i>low confidence not refit</span>
      <span><i class="dot" style="background:#e66101"></i>no activity route dist</span>
    </div>
    <p>
      Cyan dashed lines connect original GPS drift points to their refit target on the mainline.
      This is for QA; the CSV remains the source of truth.
    </p>
  </div>

  <div class="section">
    <div id="map"></div>
  </div>

  <div class="section">
    <h3>Selected point info</h3>
    <div id="info" class="info-box">Click a point or refit line.</div>
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
  }}).addTo(map).bindTooltip('standard route axis');
}}

function formatRecord(r) {{
  const keys = [
    'sample_id',
    'activity_id',
    'elapsed_sec',
    'heart_rate_bpm',
    'distance_m',
    'reliable_route_dist_m',
    'route_dist_refit_m',
    'refit_route_dist_m',
    'route_dist_refit_method',
    'offset_m',
    'route_context_dist_m',
    'route_context_ele_smooth',
    'route_context_model_status_v1c',
    'route_context_model_usable_v1c',
    'route_context_model_reason_v1c',
    'route_context_model_status_v1d',
    'route_context_model_usable_v1d',
    'route_context_model_reason_v1d',
    'route_dist_refit_m_v1d',
    'route_dist_refit_method_v1d',
    'route_context_model_status_v1e',
    'route_context_model_usable_v1e',
    'route_context_model_reason_v1e',
    'route_dist_refit_m_v1e',
    'route_dist_refit_method_v1e',
    'isolated_orange_recovery_applied_v1e',
    'isolated_orange_recovery_block_reason_v1e',
    'route_context_model_status_v1f',
    'route_context_model_usable_v1f',
    'route_context_model_reason_v1f',
    'route_dist_refit_m_v1f',
    'route_dist_refit_method_v1f',
    'route_corridor_recovery_applied_v1f',
    'route_corridor_recovery_block_reason_v1f',
    'summit_route_dist_m_v1d',
    'summit_route_dist_delta_m_v1d',
    'summit_aware_refit_applied',
    'route_dist_refit_prev_anchor_route_dist_m',
    'route_dist_refit_next_anchor_route_dist_m',
    'route_dist_refit_anchor_gap_sec',
    'route_dist_refit_anchor_gap_route_m',
    'excluded_reason'
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

let highlightMarker = null;
function showHighlight(lat, lon) {{
  if (!highlightMarker) {{
    highlightMarker = L.circleMarker([lat, lon], {{
      radius: 10,
      color: '#ffff00',
      weight: 4,
      fill: false,
      opacity: 1
    }}).addTo(map);
  }} else {{
    highlightMarker.setLatLng([lat, lon]);
  }}
}}

for (const r of records) {{
  const marker = L.circleMarker([r.lat, r.lon], {{
    radius: (
      r.status === 'matched_core_refit_from_anchors' ||
      r.status === 'matched_core_refit_to_summit' ||
      r.status === 'matched_core_recovered_from_isolated_branch_ambiguous' ||
      r.status === 'matched_core_recovered_from_route_corridor_ambiguity'
    ) ? 6 : 4,
    color: r.color,
    fillColor: r.color,
    fillOpacity: 0.78,
    opacity: 0.8,
    weight: 1
  }}).addTo(map);

  marker.bindTooltip(
    'status: ' + r.status +
    '<br>elapsed: ' + (r.elapsed_sec ?? '') +
    '<br>offset_m: ' + (r.offset_m ?? '') +
    '<br>route_dist_refit_m: ' + (r.route_dist_refit_m_v1d ?? r.route_dist_refit_m ?? '')
  );

  marker.on('mouseover', () => showHighlight(r.lat, r.lon));
  marker.on('click', () => {{
    showHighlight(r.lat, r.lon);
    setInfo(r);
  }});

  if ((r.status === 'matched_core_refit_from_anchors' || r.status === 'matched_core_refit_to_summit') && r.refit_lat !== null && r.refit_lon !== null) {{
    const line = L.polyline([[r.lat, r.lon], [r.refit_lat, r.refit_lon]], {{
      color: '#00a6a6',
      weight: 2,
      opacity: 0.75,
      dashArray: '5,5'
    }}).addTo(map);

    const target = L.circleMarker([r.refit_lat, r.refit_lon], {{
      radius: 5,
      color: '#084081',
      fillColor: '#084081',
      fillOpacity: 0.85,
      opacity: 0.85,
      weight: 1
    }}).addTo(map);

    line.on('click', () => {{
      showHighlight(r.refit_lat, r.refit_lon);
      setInfo(r);
    }});

    target.bindTooltip(
      'refit target on mainline' +
      '<br>elapsed: ' + (r.elapsed_sec ?? '') +
      '<br>route_dist_refit_m: ' + (r.route_dist_refit_m_v1d ?? r.route_dist_refit_m ?? '') +
      '<br>nearest_route_dist: ' + (r.refit_route_dist_m ?? '')
    );

    target.on('click', () => {{
      showHighlight(r.refit_lat, r.refit_lon);
      setInfo(r);
    }});
  }}
}}
</script>
</body>
</html>
"""

    out_fp.write_text(html, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="QA map showing original GPS drift points and refit target positions on mainline.")
    parser.add_argument("--route-folder", default="qixing_lengshuikeng")
    parser.add_argument("--activity-id", required=True)
    parser.add_argument("--corrected-fp", required=True)
    parser.add_argument("--route-geojson-fp", required=True)
    parser.add_argument("--out-dir", default=r"outputs\activity_points_osm_nlsc_corrected_v1c_refit_target_qa")
    parser.add_argument("--max-route-points", type=int, default=500)
    parser.add_argument("--max-sample-points", type=int, default=1200)
    args = parser.parse_args()

    corrected_fp = Path(args.corrected_fp)
    route_geojson_fp = Path(args.route_geojson_fp)
    out_dir = Path(args.out_dir)

    df = read_csv_required(corrected_fp, "v1c corrected activity points")
    route_coords, route_points = load_route_points(route_geojson_fp, args.max_route_points)

    records = make_records(df, route_points, args.max_sample_points)

    out_root = out_dir / args.route_folder / args.activity_id
    out_root.mkdir(parents=True, exist_ok=True)

    out_fp = out_root / f"{args.route_folder}_{args.activity_id}_activity_points_osm_nlsc_corrected_refit_target_qa.html"

    build_html(
        records=records,
        route_coords=route_coords,
        route_folder=args.route_folder,
        activity_id=args.activity_id,
        source_rows=len(df),
        out_fp=out_fp,
    )

    print("Refit target QA written:")
    print(out_fp)


if __name__ == "__main__":
    main()
