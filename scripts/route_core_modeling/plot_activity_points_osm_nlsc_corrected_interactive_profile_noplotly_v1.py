from __future__ import annotations

import argparse
from pathlib import Path
from html import escape

import pandas as pd
import geopandas as gpd
import folium
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
        dist_col = None
        for c in ["dist_m", "route_dist_m"]:
            if c in point_rows.columns:
                dist_col = c
                break
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


def build_map_html(
    df: pd.DataFrame,
    route_geojson_fp: Path,
    route_folder: str,
    activity_id: str,
    max_track_points: int,
    max_route_points: int,
    max_marker_points: int,
) -> str:
    lat_col, lon_col = find_lat_lon_cols(df)

    work = df.copy()
    work[lat_col] = pd.to_numeric(work[lat_col], errors="coerce")
    work[lon_col] = pd.to_numeric(work[lon_col], errors="coerce")
    work = work.dropna(subset=[lat_col, lon_col]).copy()

    center_lat = work[lat_col].median()
    center_lon = work[lon_col].median()

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=15,
        tiles="OpenStreetMap",
        prefer_canvas=True,
        control_scale=True,
    )

    route_coords = extract_route_line_coords(route_geojson_fp, max_route_points)
    if len(route_coords) >= 2:
        folium.PolyLine(
            locations=route_coords,
            color="#111111",
            weight=4,
            opacity=0.8,
            tooltip="simplified IB1E route axis",
        ).add_to(m)

    track_points = work[[lat_col, lon_col]].values.tolist()
    track_points = downsample_points(track_points, max_track_points)
    if len(track_points) >= 2:
        folium.PolyLine(
            locations=track_points,
            color="#777777",
            weight=2,
            opacity=0.55,
            tooltip="downsampled raw GPS track",
        ).add_to(m)

    matched = work[work["route_context_match_status"] == "matched"].copy()
    no_dist = work[work["route_context_match_status"] == "no_activity_route_dist"].copy()
    unmatched = work[work["route_context_match_status"] == "unmatched"].copy()

    def add_points(layer_df: pd.DataFrame, color: str, layer_name: str, radius: int = 3) -> None:
        sample = downsample_df(layer_df, max_marker_points)
        fg = folium.FeatureGroup(name=f"{layer_name} sampled {len(sample)} / {len(layer_df)}")

        for _, row in sample.iterrows():
            tooltip_parts = []
            for c in [
                "elapsed_sec",
                "heart_rate_bpm",
                "reliable_route_dist_m",
                "offset_to_mainline_m",
                "route_context_ele_smooth",
                "route_context_slope_band_window_nlsc",
                "route_context_osm_terrain_combined_risk_band",
                "excluded_reason",
            ]:
                if c in row.index:
                    tooltip_parts.append(f"{c}: {row[c]}")

            folium.CircleMarker(
                location=[row[lat_col], row[lon_col]],
                radius=radius,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.75,
                opacity=0.75,
                tooltip="<br>".join(tooltip_parts),
            ).add_to(fg)

        fg.add_to(m)

    add_points(matched, "#1f78b4", "matched route-context points", 3)
    add_points(no_dist, "#e66101", "no_activity_route_dist / excluded observed points", 3)
    if len(unmatched) > 0:
        add_points(unmatched, "#d7191c", "unmatched route-context points", 4)

    first = work.iloc[0]
    last = work.iloc[-1]

    folium.Marker(
        [first[lat_col], first[lon_col]],
        popup="activity start",
        tooltip="activity start",
        icon=folium.Icon(color="green", icon="play"),
    ).add_to(m)

    folium.Marker(
        [last[lat_col], last[lon_col]],
        popup="activity end",
        tooltip="activity end",
        icon=folium.Icon(color="red", icon="stop"),
    ).add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    return m.get_root().render()


def svg_panel(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str,
    y_label: str,
    max_points: int,
) -> str:
    if y_col not in df.columns:
        return f"<h3>{escape(title)}</h3><p>Missing column: {escape(y_col)}</p>"

    work = df.copy()
    work[x_col] = pd.to_numeric(work[x_col], errors="coerce")
    work[y_col] = pd.to_numeric(work[y_col], errors="coerce")
    work = work.dropna(subset=[x_col, y_col]).copy()

    if work.empty:
        return f"<h3>{escape(title)}</h3><p>No valid data.</p>"

    work = downsample_df(work, max_points)

    x_min, x_max = float(work[x_col].min()), float(work[x_col].max())
    y_min, y_max = float(work[y_col].min()), float(work[y_col].max())

    if x_max == x_min:
        x_max = x_min + 1
    if y_max == y_min:
        y_max = y_min + 1

    width = 1200
    height = 280
    left = 70
    right = 20
    top = 30
    bottom = 45
    plot_w = width - left - right
    plot_h = height - top - bottom

    def sx(x):
        return left + (float(x) - x_min) / (x_max - x_min) * plot_w

    def sy(y):
        return top + (y_max - float(y)) / (y_max - y_min) * plot_h

    circles = []
    for _, row in work.iterrows():
        status = str(row.get("route_context_match_status", ""))
        color = "#1f78b4" if status == "matched" else "#e66101"
        if status == "unmatched":
            color = "#d7191c"

        tooltip_parts = []
        for c in [
            "elapsed_sec",
            "heart_rate_bpm",
            "reliable_route_dist_m",
            "projected_route_dist_m",
            "offset_to_mainline_m",
            "route_context_ele_smooth",
            "route_context_slope_band_window_nlsc",
            "route_context_osm_terrain_combined_risk_band",
            "excluded_reason",
            "route_context_match_status",
        ]:
            if c in row.index:
                tooltip_parts.append(f"{c}: {row[c]}")
        tooltip = escape("\n".join(tooltip_parts))

        circles.append(
            f'<circle cx="{sx(row[x_col]):.2f}" cy="{sy(row[y_col]):.2f}" r="3.2" '
            f'fill="{color}" fill-opacity="0.75"><title>{tooltip}</title></circle>'
        )

    # simple polyline for matched values only
    matched = work[work["route_context_match_status"] == "matched"].copy()
    line_pts = []
    for _, row in matched.iterrows():
        line_pts.append(f"{sx(row[x_col]):.2f},{sy(row[y_col]):.2f}")

    polyline = ""
    if len(line_pts) >= 2:
        polyline = (
            f'<polyline points="{" ".join(line_pts)}" fill="none" '
            f'stroke="#1f78b4" stroke-width="1.5" stroke-opacity="0.45"/>'
        )

    return f"""
    <div class="profile-panel">
      <h3>{escape(title)}</h3>
      <svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">
        <rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>
        <line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="#333"/>
        <line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="#333"/>
        <text x="10" y="{top+15}" font-size="12">{escape(y_label)}</text>
        <text x="{left}" y="{height-12}" font-size="12">{escape(x_col)}</text>
        <text x="{left}" y="{top-8}" font-size="12">y max: {y_max:.2f}</text>
        <text x="{left}" y="{height-bottom+18}" font-size="12">x min: {x_min:.2f}</text>
        <text x="{width-170}" y="{height-bottom+18}" font-size="12">x max: {x_max:.2f}</text>
        {polyline}
        {''.join(circles)}
      </svg>
    </div>
    """


def build_profile_html(df: pd.DataFrame, max_profile_points: int) -> str:
    work = df.copy()

    x_col = None
    for c in ["elapsed_sec", "timestamp", "time_sec"]:
        if c in work.columns:
            x_col = c
            break

    if x_col is None:
        work["row_index"] = range(len(work))
        x_col = "row_index"

    return "\n".join([
        svg_panel(work, x_col, "route_context_ele_smooth", "Route-context elevation", "elevation m", max_profile_points),
        svg_panel(work, x_col, "heart_rate_bpm", "Heart rate", "HR bpm", max_profile_points),
        svg_panel(work, x_col, "offset_to_mainline_m", "Offset to mainline", "offset m", max_profile_points),
    ])


def build_combined_html(
    corrected_fp: Path,
    route_geojson_fp: Path,
    route_folder: str,
    activity_id: str,
    out_dir: Path,
    max_track_points: int,
    max_route_points: int,
    max_marker_points: int,
    max_profile_points: int,
) -> Path:
    df = read_csv_required(corrected_fp, "corrected activity points")

    map_html = build_map_html(
        df=df,
        route_geojson_fp=route_geojson_fp,
        route_folder=route_folder,
        activity_id=activity_id,
        max_track_points=max_track_points,
        max_route_points=max_route_points,
        max_marker_points=max_marker_points,
    )

    profile_html = build_profile_html(df, max_profile_points=max_profile_points)

    matched = int((df["route_context_match_status"] == "matched").sum())
    no_dist = int((df["route_context_match_status"] == "no_activity_route_dist").sum())
    unmatched = int((df["route_context_match_status"] == "unmatched").sum())

    map_srcdoc = escape(map_html, quote=True)

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Interactive QA no-plotly: {escape(route_folder)} {escape(activity_id)}</title>
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
    .note {{
      line-height: 1.5;
      font-size: 14px;
    }}
    iframe {{
      width: 100%;
      height: 620px;
      border: 1px solid #ccc;
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
  <div class="section note">
    <h2>activity_points_osm_nlsc_corrected_v1 interactive QA no-plotly</h2>
    <div><b>route_folder</b>: {escape(route_folder)}</div>
    <div><b>activity_id</b>: {escape(activity_id)}</div>
    <div><b>rows</b>: {len(df)}</div>
    <div><b>matched</b>: {matched}</div>
    <div><b>no_activity_route_dist</b>: {no_dist}</div>
    <div><b>unmatched</b>: {unmatched}</div>
    <div class="legend">
      <span><i class="dot" style="background:#1f78b4"></i>matched</span>
      <span><i class="dot" style="background:#e66101"></i>no_activity_route_dist</span>
      <span><i class="dot" style="background:#d7191c"></i>unmatched</span>
    </div>
    <p>
      Map and profile are downsampled for QA performance. Hover SVG points to inspect values.
      CSV remains the source of truth.
    </p>
  </div>

  <div class="section">
    <h3>1. Lightweight 2D map QA</h3>
    <iframe srcdoc="{map_srcdoc}"></iframe>
  </div>

  <div class="section">
    <h3>2. SVG profile QA</h3>
    {profile_html}
  </div>
</body>
</html>
"""

    out_root = out_dir / route_folder / activity_id
    out_root.mkdir(parents=True, exist_ok=True)

    out_fp = out_root / f"{route_folder}_{activity_id}_activity_points_osm_nlsc_corrected_interactive_profile_qa_noplotly.html"
    out_fp.write_text(html, encoding="utf-8")

    return out_fp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="No-plotly interactive map + SVG profile QA for activity_points_osm_nlsc_corrected_v1."
    )
    parser.add_argument("--route-folder", default="qixing_lengshuikeng")
    parser.add_argument("--activity-id", required=True)
    parser.add_argument("--corrected-fp", required=True)
    parser.add_argument("--route-geojson-fp", required=True)
    parser.add_argument(
        "--out-dir",
        default=r"outputs\activity_points_osm_nlsc_corrected_v1_interactive_profile_qa_noplotly",
    )
    parser.add_argument("--max-track-points", type=int, default=300)
    parser.add_argument("--max-route-points", type=int, default=300)
    parser.add_argument("--max-marker-points", type=int, default=60)
    parser.add_argument("--max-profile-points", type=int, default=1000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    out_fp = build_combined_html(
        corrected_fp=Path(args.corrected_fp),
        route_geojson_fp=Path(args.route_geojson_fp),
        route_folder=args.route_folder,
        activity_id=args.activity_id,
        out_dir=Path(args.out_dir),
        max_track_points=args.max_track_points,
        max_route_points=args.max_route_points,
        max_marker_points=args.max_marker_points,
        max_profile_points=args.max_profile_points,
    )

    print("No-plotly interactive profile QA written:")
    print(out_fp)


if __name__ == "__main__":
    main()
