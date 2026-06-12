from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


STATUS_COLOR = {
    "FINAL_ACCEPTABLE": "#2ca25f",
    "FINAL_LOW_CONFIDENCE_REVIEW_REQUIRED": "#fdae61",
    "FINAL_REVIEW_REQUIRED": "#de2d26",
    "FINAL_LOOKUP_FAILED": "#de2d26",
    "FINAL_ELEVATION_MISSING": "#756bb1",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="IB3W v1: plot weather/water station elevation evidence in 1D + 2D HTML."
    )
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--route-profile-csv", required=True)
    parser.add_argument("--weather-final-csv", required=True)
    parser.add_argument("--water-final-csv", required=True)
    parser.add_argument(
        "--out-dir",
        default="outputs/ib3w_station_elevation_map_v1",
    )
    return parser.parse_args()


def ensure_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def to_float(value, default=None):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def normalize_route(route_csv: Path) -> pd.DataFrame:
    route = pd.read_csv(route_csv)

    required = ["dist_m", "lat", "lon"]
    missing = [c for c in required if c not in route.columns]
    if missing:
        raise ValueError(f"route profile missing columns: {missing}")

    elevation_col = None
    for c in ["ele_smooth", "ele_gpx_m", "elevation_m", "elevation"]:
        if c in route.columns:
            elevation_col = c
            break

    if elevation_col is None:
        raise ValueError("route profile needs one elevation column, e.g. ele_smooth or ele_gpx_m")

    keep = [
        "sample_idx",
        "dist_m",
        "lat",
        "lon",
        elevation_col,
        "slope_pct",
        "slope_band_window_nlsc",
        "terrain_risk_score",
        "osm_terrain_combined_risk_score",
        "osm_semantic_risk_score",
    ]
    keep = [c for c in keep if c in route.columns]

    out = route[keep].copy()
    out["route_elevation_m"] = pd.to_numeric(out[elevation_col], errors="coerce")
    out["dist_m"] = pd.to_numeric(out["dist_m"], errors="coerce")
    out["lat"] = pd.to_numeric(out["lat"], errors="coerce")
    out["lon"] = pd.to_numeric(out["lon"], errors="coerce")
    out = out.dropna(subset=["dist_m", "lat", "lon", "route_elevation_m"]).copy()
    out = out.sort_values("dist_m").reset_index(drop=True)
    return out


def normalize_stations(csv_path: Path, station_group: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    required = [
        "station_id",
        "station_name",
        "station_latitude",
        "station_longitude",
        "distance_to_route_m",
        "nearest_route_km",
        "nearest_route_latitude",
        "nearest_route_longitude",
        "station_elevation_m_final",
        "elevation_final_status",
        "elevation_final_confidence",
        "elevation_final_nlsc_tile",
        "elevation_final_source",
        "elevation_final_review_required",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{station_group} final CSV missing columns: {missing}")

    out = df.copy()
    out["station_group"] = station_group
    if "station_type" not in out.columns:
        out["station_type"] = station_group

    numeric_cols = [
        "station_latitude",
        "station_longitude",
        "distance_to_route_m",
        "nearest_route_km",
        "nearest_route_latitude",
        "nearest_route_longitude",
        "station_elevation_m_final",
    ]
    for c in numeric_cols:
        out[c] = pd.to_numeric(out[c], errors="coerce")

    out = out.dropna(
        subset=[
            "station_latitude",
            "station_longitude",
            "nearest_route_km",
            "nearest_route_latitude",
            "nearest_route_longitude",
            "station_elevation_m_final",
        ]
    ).copy()

    keep = [
        "station_group",
        "station_type",
        "candidate_rank",
        "station_id",
        "station_name",
        "station_latitude",
        "station_longitude",
        "distance_to_route_m",
        "nearest_route_km",
        "nearest_route_latitude",
        "nearest_route_longitude",
        "station_elevation_m_final",
        "elevation_final_status",
        "elevation_final_confidence",
        "elevation_final_nlsc_tile",
        "elevation_final_source",
        "elevation_final_review_required",
        "elevation_final_neighbor_tile_review_result",
    ]
    keep = [c for c in keep if c in out.columns]
    return out[keep].copy()


def prepare_station_plot_data(weather: pd.DataFrame, water: pd.DataFrame) -> pd.DataFrame:
    stations = pd.concat([weather, water], ignore_index=True)
    stations["status_color"] = stations["elevation_final_status"].map(STATUS_COLOR).fillna("#636363")
    stations["nearest_route_m"] = stations["nearest_route_km"] * 1000.0
    stations = stations.sort_values(
        ["station_group", "elevation_final_status", "candidate_rank", "station_id"],
        na_position="last",
    ).reset_index(drop=True)
    return stations


def build_1d_svg(route: pd.DataFrame, stations: pd.DataFrame) -> str:
    width = 1200
    height = 420
    margin_left = 70
    margin_right = 30
    margin_top = 30
    margin_bottom = 55

    x_min = float(route["dist_m"].min())
    x_max = float(route["dist_m"].max())

    route_y_values = route["route_elevation_m"].dropna().tolist()
    station_y_values = stations["station_elevation_m_final"].dropna().tolist()
    y_min = min(route_y_values + station_y_values)
    y_max = max(route_y_values + station_y_values)
    pad = max(20.0, (y_max - y_min) * 0.08)
    y_min -= pad
    y_max += pad

    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom

    def sx(x):
        if x_max == x_min:
            return margin_left
        return margin_left + (float(x) - x_min) / (x_max - x_min) * plot_w

    def sy(y):
        if y_max == y_min:
            return margin_top + plot_h / 2
        return margin_top + (y_max - float(y)) / (y_max - y_min) * plot_h

    route_points = []
    for _, r in route.iterrows():
        route_points.append(f"{sx(r['dist_m']):.1f},{sy(r['route_elevation_m']):.1f}")

    grid = []
    for i in range(6):
        frac = i / 5
        y = margin_top + frac * plot_h
        value = y_max - frac * (y_max - y_min)
        grid.append(
            f'<line x1="{margin_left}" x2="{width-margin_right}" y1="{y:.1f}" y2="{y:.1f}" stroke="#eeeeee"/>'
            f'<text x="{margin_left-10}" y="{y+4:.1f}" text-anchor="end" font-size="11" fill="#666">{value:.0f} m</text>'
        )

    x_ticks = []
    for i in range(6):
        frac = i / 5
        x = margin_left + frac * plot_w
        value_km = (x_min + frac * (x_max - x_min)) / 1000.0
        x_ticks.append(
            f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{margin_top}" y2="{margin_top+plot_h}" stroke="#f2f2f2"/>'
            f'<text x="{x:.1f}" y="{height-25}" text-anchor="middle" font-size="11" fill="#666">{value_km:.1f} km</text>'
        )

    station_shapes = []
    for _, s in stations.iterrows():
        x = sx(s["nearest_route_m"])
        y = sy(s["station_elevation_m_final"])
        color = s["status_color"]
        label = (
            f"{s['station_group']} | {s['station_id']} {s['station_name']}\\n"
            f"route km: {s['nearest_route_km']:.3f}\\n"
            f"distance to route: {s['distance_to_route_m']:.1f} m\\n"
            f"station elevation: {s['station_elevation_m_final']:.1f} m\\n"
            f"status: {s['elevation_final_status']}\\n"
            f"confidence: {s['elevation_final_confidence']}\\n"
            f"tile: {s['elevation_final_nlsc_tile']}"
        )
        if s["station_group"] == "weather":
            station_shapes.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{color}" stroke="#222" stroke-width="0.7">'
                f'<title>{label}</title></circle>'
            )
        else:
            station_shapes.append(
                f'<rect x="{x-5:.1f}" y="{y-5:.1f}" width="10" height="10" fill="{color}" stroke="#222" stroke-width="0.7">'
                f'<title>{label}</title></rect>'
            )

    svg = f'''
<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" role="img">
  <rect x="0" y="0" width="{width}" height="{height}" fill="white"/>
  <text x="{margin_left}" y="20" font-size="16" font-weight="600">1D route profile with weather/water station elevation</text>
  {''.join(grid)}
  {''.join(x_ticks)}
  <polyline points="{' '.join(route_points)}" fill="none" stroke="#2b8cbe" stroke-width="2.5"/>
  {''.join(station_shapes)}
  <text x="{width/2:.1f}" y="{height-5}" text-anchor="middle" font-size="12" fill="#333">Route distance</text>
  <text transform="translate(18,{height/2:.1f}) rotate(-90)" text-anchor="middle" font-size="12" fill="#333">Elevation</text>
</svg>
'''
    return svg


def to_records(df: pd.DataFrame, columns: list[str]) -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        row = {}
        for c in columns:
            value = r.get(c)
            if pd.isna(value):
                row[c] = None
            elif isinstance(value, (int, float, str, bool)):
                row[c] = value
            else:
                row[c] = str(value)
        rows.append(row)
    return rows


def build_html(case_id: str, route: pd.DataFrame, stations: pd.DataFrame, svg_1d: str) -> str:
    route_records = to_records(route, ["lat", "lon", "dist_m", "route_elevation_m"])
    station_records = to_records(
        stations,
        [
            "station_group",
            "station_type",
            "candidate_rank",
            "station_id",
            "station_name",
            "station_latitude",
            "station_longitude",
            "distance_to_route_m",
            "nearest_route_km",
            "nearest_route_latitude",
            "nearest_route_longitude",
            "station_elevation_m_final",
            "elevation_final_status",
            "elevation_final_confidence",
            "elevation_final_nlsc_tile",
            "elevation_final_source",
            "elevation_final_review_required",
            "status_color",
        ],
    )

    summary = stations.groupby(["station_group", "elevation_final_status"]).size().reset_index(name="count")
    summary_html = summary.to_html(index=False, escape=True)

    tile_summary = stations.groupby(["station_group", "elevation_final_nlsc_tile"]).size().reset_index(name="count")
    tile_summary_html = tile_summary.to_html(index=False, escape=True)

    status_legend = "".join(
        f'<span class="legend-item"><span class="swatch" style="background:{color}"></span>{status}</span>'
        for status, color in STATUS_COLOR.items()
    )

    html = f'''<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8"/>
  <title>IB3W Station Elevation 1D/2D Report - {case_id}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #222;
      background: #f7f7f7;
    }}
    header {{
      padding: 18px 24px;
      background: #1f2937;
      color: white;
    }}
    main {{
      padding: 18px 24px 40px;
    }}
    section {{
      background: white;
      border: 1px solid #e5e7eb;
      border-radius: 10px;
      padding: 16px;
      margin-bottom: 16px;
      box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }}
    #map {{
      height: 680px;
      border-radius: 8px;
      border: 1px solid #ddd;
    }}
    table {{
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      border: 1px solid #ddd;
      padding: 5px 8px;
    }}
    th {{
      background: #f3f4f6;
    }}
    .legend-item {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      margin-right: 18px;
      font-size: 13px;
    }}
    .swatch {{
      display: inline-block;
      width: 12px;
      height: 12px;
      border: 1px solid #333;
    }}
    .note {{
      color: #555;
      font-size: 13px;
      line-height: 1.55;
    }}
    .pill {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      background: #eef2ff;
      margin-right: 8px;
      font-size: 12px;
    }}
  </style>
</head>
<body>
<header>
  <h1>IB3W Station Elevation 1D + 2D Report</h1>
  <div>{case_id}</div>
</header>
<main>
  <section>
    <h2>Summary</h2>
    <p>
      <span class="pill">Route samples: {len(route)}</span>
      <span class="pill">Stations: {len(stations)}</span>
      <span class="pill">Weather: {int((stations["station_group"] == "weather").sum())}</span>
      <span class="pill">Water: {int((stations["station_group"] == "water").sum())}</span>
    </p>
    <div>{status_legend}</div>
    <h3>Final status</h3>
    {summary_html}
    <h3>Final tile</h3>
    {tile_summary_html}
    <p class="note">
      Circle markers are weather stations. Square markers are water stations.
      Green indicates FINAL_ACCEPTABLE. Orange indicates FINAL_LOW_CONFIDENCE_REVIEW_REQUIRED.
      Connector lines show station point to nearest route projection point.
      This report visualizes station elevation evidence only; it does not perform weather/hydro observation fusion.
    </p>
  </section>

  <section>
    <h2>1D profile</h2>
    {svg_1d}
  </section>

  <section>
    <h2>2D map</h2>
    <div id="map"></div>
  </section>
</main>

<script>
const route = {json.dumps(route_records, ensure_ascii=False)};
const stations = {json.dumps(station_records, ensure_ascii=False)};

const routeLatLngs = route.map(r => [r.lat, r.lon]);
const map = L.map('map');
L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap contributors'
}}).addTo(map);

const routeLine = L.polyline(routeLatLngs, {{
  color: '#2b8cbe',
  weight: 4,
  opacity: 0.9
}}).addTo(map);

const weatherLayer = L.layerGroup().addTo(map);
const waterLayer = L.layerGroup().addTo(map);
const connectorLayer = L.layerGroup().addTo(map);

function popupHtml(s) {{
  return `
    <b>${{s.station_group}} | ${{s.station_id}} ${{s.station_name}}</b><br/>
    candidate rank: ${{s.candidate_rank ?? ""}}<br/>
    route km: ${{Number(s.nearest_route_km).toFixed(3)}}<br/>
    distance to route: ${{Number(s.distance_to_route_m).toFixed(1)}} m<br/>
    station elevation final: ${{Number(s.station_elevation_m_final).toFixed(1)}} m<br/>
    final status: ${{s.elevation_final_status}}<br/>
    confidence: ${{s.elevation_final_confidence}}<br/>
    final tile: ${{s.elevation_final_nlsc_tile}}<br/>
    final source: ${{s.elevation_final_source}}<br/>
    review required: ${{s.elevation_final_review_required}}
  `;
}}

stations.forEach(s => {{
  const markerStyle = {{
    radius: s.station_group === 'weather' ? 6 : 7,
    color: '#222',
    weight: 1,
    fillColor: s.status_color || '#636363',
    fillOpacity: 0.85
  }};

  let marker;
  if (s.station_group === 'weather') {{
    marker = L.circleMarker([s.station_latitude, s.station_longitude], markerStyle);
    marker.addTo(weatherLayer);
  }} else {{
    const d = 0.00035;
    marker = L.rectangle(
      [[s.station_latitude - d, s.station_longitude - d], [s.station_latitude + d, s.station_longitude + d]],
      {{
        color: '#222',
        weight: 1,
        fillColor: s.status_color || '#636363',
        fillOpacity: 0.85
      }}
    );
    marker.addTo(waterLayer);
  }}

  marker.bindPopup(popupHtml(s));

  L.circleMarker([s.nearest_route_latitude, s.nearest_route_longitude], {{
    radius: 2.5,
    color: '#111',
    fillColor: '#111',
    fillOpacity: 0.8,
    weight: 1
  }}).addTo(connectorLayer);

  L.polyline(
    [[s.station_latitude, s.station_longitude], [s.nearest_route_latitude, s.nearest_route_longitude]],
    {{
      color: s.status_color || '#999',
      weight: 1,
      opacity: 0.45,
      dashArray: '3,4'
    }}
  ).addTo(connectorLayer);
}});

L.control.layers(
  {{"Route": routeLine}},
  {{"Weather stations": weatherLayer, "Water stations": waterLayer, "Station-route connectors": connectorLayer}},
  {{collapsed: false}}
).addTo(map);

map.fitBounds(routeLine.getBounds(), {{padding: [30, 30]}});
</script>
</body>
</html>
'''
    return html


def main() -> None:
    args = parse_args()
    case_id = args.case_id

    route_csv = Path(args.route_profile_csv)
    weather_csv = Path(args.weather_final_csv)
    water_csv = Path(args.water_final_csv)
    out_dir = Path(args.out_dir) / case_id
    out_dir.mkdir(parents=True, exist_ok=True)

    ensure_exists(route_csv, "route profile CSV")
    ensure_exists(weather_csv, "weather final CSV")
    ensure_exists(water_csv, "water final CSV")

    route = normalize_route(route_csv)
    weather = normalize_stations(weather_csv, "weather")
    water = normalize_stations(water_csv, "water")
    stations = prepare_station_plot_data(weather, water)

    svg_1d = build_1d_svg(route, stations)
    html = build_html(case_id, route, stations, svg_1d)

    out_html = out_dir / "station_elevation_1d_2d_report.html"
    out_csv = out_dir / "station_elevation_plot_data.csv"
    summary_csv = out_dir / "station_elevation_map_summary.csv"

    out_html.write_text(html, encoding="utf-8")
    stations.to_csv(out_csv, index=False, encoding="utf-8-sig")

    summary = pd.DataFrame([{
        "case_id": case_id,
        "route_rows": int(len(route)),
        "station_rows": int(len(stations)),
        "weather_rows": int((stations["station_group"] == "weather").sum()),
        "water_rows": int((stations["station_group"] == "water").sum()),
        "final_acceptable": int((stations["elevation_final_status"] == "FINAL_ACCEPTABLE").sum()),
        "final_low_confidence_review_required": int((stations["elevation_final_status"] == "FINAL_LOW_CONFIDENCE_REVIEW_REQUIRED").sum()),
        "tile_97233NW": int((stations["elevation_final_nlsc_tile"].astype(str) == "97233NW").sum()),
        "tile_97233SW": int((stations["elevation_final_nlsc_tile"].astype(str) == "97233SW").sum()),
        "zero_fallback_used": False,
    }])
    summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")

    print("IB3W station elevation 1D/2D HTML report written")
    print("case_id:", case_id)
    print("route_csv:", route_csv)
    print("weather_csv:", weather_csv)
    print("water_csv:", water_csv)
    print("out_html:", out_html)
    print("out_csv:", out_csv)
    print("summary_csv:", summary_csv)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
