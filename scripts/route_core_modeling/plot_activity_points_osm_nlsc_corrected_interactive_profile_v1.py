from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import geopandas as gpd
import folium
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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

    raise ValueError(
        "Cannot find lat/lon columns. Tried: "
        + ", ".join([f"{a}/{b}" for a, b in candidates])
    )


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

    if work.empty:
        raise ValueError("No valid lat/lon rows found.")

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

    def add_points(layer_df: pd.DataFrame, color: str, layer_name: str, radius: int = 3):
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

    add_points(matched, "#1f78b4", "matched route-context points", radius=3)
    add_points(no_dist, "#e66101", "no_activity_route_dist / excluded observed points", radius=3)

    if len(unmatched) > 0:
        add_points(unmatched, "#d7191c", "unmatched route-context points", radius=4)

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

    title_html = f"""
    <div style="
        position: fixed;
        top: 12px;
        left: 50px;
        z-index: 9999;
        background: white;
        padding: 10px 14px;
        border: 1px solid #999;
        border-radius: 6px;
        font-size: 14px;
        line-height: 1.45;
    ">
      <b>Map QA</b><br>
      route_folder: {route_folder}<br>
      activity_id: {activity_id}<br>
      rows: {len(work)}<br>
      matched: {len(matched)}<br>
      no_activity_route_dist: {len(no_dist)}<br>
      unmatched: {len(unmatched)}
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))
    folium.LayerControl(collapsed=False).add_to(m)

    return m.get_root().render()


def build_profile_html(df: pd.DataFrame, route_folder: str, activity_id: str, max_profile_points: int) -> str:
    work = df.copy()

    # x-axis preference
    x_col = None
    for c in ["elapsed_sec", "timestamp", "time_sec"]:
        if c in work.columns:
            x_col = c
            break

    if x_col is None:
        work["row_index"] = range(len(work))
        x_col = "row_index"

    for c in [
        x_col,
        "route_context_ele_smooth",
        "heart_rate_bpm",
        "offset_to_mainline_m",
        "reliable_route_dist_m",
        "projected_route_dist_m",
    ]:
        if c in work.columns:
            work[c] = pd.to_numeric(work[c], errors="coerce")

    work = downsample_df(work, max_profile_points)

    matched = work[work["route_context_match_status"] == "matched"].copy()
    no_dist = work[work["route_context_match_status"] == "no_activity_route_dist"].copy()
    unmatched = work[work["route_context_match_status"] == "unmatched"].copy()

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        subplot_titles=[
            "Route-context elevation over activity time",
            "Heart rate over activity time",
            "Offset to mainline over activity time",
        ],
    )

    def hover_text(layer: pd.DataFrame) -> list[str]:
        texts = []
        for _, row in layer.iterrows():
            parts = []
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
                    parts.append(f"{c}: {row[c]}")
            texts.append("<br>".join(parts))
        return texts

    def add_layer(layer: pd.DataFrame, name: str, color: str):
        if len(layer) == 0:
            return

        if "route_context_ele_smooth" in layer.columns:
            fig.add_trace(
                go.Scattergl(
                    x=layer[x_col],
                    y=layer["route_context_ele_smooth"],
                    mode="markers",
                    name=f"{name} elevation",
                    marker=dict(size=5, color=color),
                    text=hover_text(layer),
                    hoverinfo="text",
                ),
                row=1,
                col=1,
            )

        if "heart_rate_bpm" in layer.columns:
            fig.add_trace(
                go.Scattergl(
                    x=layer[x_col],
                    y=layer["heart_rate_bpm"],
                    mode="markers",
                    name=f"{name} HR",
                    marker=dict(size=5, color=color),
                    text=hover_text(layer),
                    hoverinfo="text",
                ),
                row=2,
                col=1,
            )

        if "offset_to_mainline_m" in layer.columns:
            fig.add_trace(
                go.Scattergl(
                    x=layer[x_col],
                    y=layer["offset_to_mainline_m"],
                    mode="markers",
                    name=f"{name} offset",
                    marker=dict(size=5, color=color),
                    text=hover_text(layer),
                    hoverinfo="text",
                ),
                row=3,
                col=1,
            )

    add_layer(matched, "matched", "#1f78b4")
    add_layer(no_dist, "no_activity_route_dist", "#e66101")
    add_layer(unmatched, "unmatched", "#d7191c")

    fig.update_layout(
        title=f"Interactive profile QA: {route_folder} / {activity_id}",
        height=850,
        hovermode="closest",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )

    fig.update_xaxes(title_text=x_col, row=3, col=1)
    fig.update_yaxes(title_text="elevation m", row=1, col=1)
    fig.update_yaxes(title_text="HR bpm", row=2, col=1)
    fig.update_yaxes(title_text="offset m", row=3, col=1)

    return fig.to_html(full_html=False, include_plotlyjs="cdn")


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

    profile_html = build_profile_html(
        df=df,
        route_folder=route_folder,
        activity_id=activity_id,
        max_profile_points=max_profile_points,
    )

    matched = int((df["route_context_match_status"] == "matched").sum())
    no_dist = int((df["route_context_match_status"] == "no_activity_route_dist").sum())
    unmatched = int((df["route_context_match_status"] == "unmatched").sum())

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Interactive QA: {route_folder} {activity_id}</title>
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
      height: 680px;
      border: 1px solid #ccc;
    }}
  </style>
</head>
<body>
  <div class="section note">
    <h2>activity_points_osm_nlsc_corrected_v1 interactive QA</h2>
    <div><b>route_folder</b>: {route_folder}</div>
    <div><b>activity_id</b>: {activity_id}</div>
    <div><b>rows</b>: {len(df)}</div>
    <div><b>matched</b>: {matched}</div>
    <div><b>no_activity_route_dist</b>: {no_dist}</div>
    <div><b>unmatched</b>: {unmatched}</div>
    <p>
      Map and profile are both downsampled for QA performance. Use the CSV as the source of truth.
      Matched points have route-context elevation / terrain / OSM context.
      no_activity_route_dist points are preserved observed activity points and are not force-corrected onto route context.
    </p>
  </div>

  <div class="section">
    <h3>1. Lightweight 2D map QA</h3>
    <iframe srcdoc="{map_html.replace('"', '&quot;')}"></iframe>
  </div>

  <div class="section">
    <h3>2. Interactive profile QA</h3>
    {profile_html}
  </div>
</body>
</html>
"""

    out_root = out_dir / route_folder / activity_id
    out_root.mkdir(parents=True, exist_ok=True)

    out_fp = out_root / f"{route_folder}_{activity_id}_activity_points_osm_nlsc_corrected_interactive_profile_qa.html"
    out_fp.write_text(html, encoding="utf-8")

    return out_fp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactive map + profile QA for activity_points_osm_nlsc_corrected_v1."
    )

    parser.add_argument("--route-folder", default="qixing_lengshuikeng")
    parser.add_argument("--activity-id", required=True)
    parser.add_argument("--corrected-fp", required=True)
    parser.add_argument("--route-geojson-fp", required=True)
    parser.add_argument(
        "--out-dir",
        default=r"outputs\activity_points_osm_nlsc_corrected_v1_interactive_profile_qa",
    )
    parser.add_argument("--max-track-points", type=int, default=400)
    parser.add_argument("--max-route-points", type=int, default=400)
    parser.add_argument("--max-marker-points", type=int, default=80)
    parser.add_argument("--max-profile-points", type=int, default=1200)

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

    print("Interactive profile QA written:")
    print(out_fp)


if __name__ == "__main__":
    main()
