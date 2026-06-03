from __future__ import annotations

import argparse
from pathlib import Path

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

    # Case A: route profile points GeoJSON
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

    # Case B: LineString / MultiLineString GeoJSON
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


def add_sample_points(
    m: folium.Map,
    df: pd.DataFrame,
    lat_col: str,
    lon_col: str,
    color: str,
    layer_name: str,
    max_points: int,
    radius: int = 3,
) -> None:
    sample = downsample_df(df, max_points)

    fg = folium.FeatureGroup(name=f"{layer_name} sampled {len(sample)} / {len(df)}")

    for _, row in sample.iterrows():
        folium.CircleMarker(
            location=[row[lat_col], row[lon_col]],
            radius=radius,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.75,
            opacity=0.75,
            tooltip=layer_name,
        ).add_to(fg)

    fg.add_to(m)


def plot_light_map(
    corrected_fp: Path,
    route_geojson_fp: Path,
    route_folder: str,
    activity_id: str,
    out_dir: Path,
    max_track_points: int,
    max_route_points: int,
    max_marker_points: int,
) -> Path:
    df = read_csv_required(corrected_fp, "corrected activity points")
    lat_col, lon_col = find_lat_lon_cols(df)

    df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
    df[lon_col] = pd.to_numeric(df[lon_col], errors="coerce")
    df = df.dropna(subset=[lat_col, lon_col]).copy()

    if df.empty:
        raise ValueError("No valid lat/lon rows found.")

    center_lat = df[lat_col].median()
    center_lon = df[lon_col].median()

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=15,
        tiles="OpenStreetMap",
        prefer_canvas=True,
    )

    # Route axis: simplified line only, no GeoJSON properties.
    route_coords = extract_route_line_coords(route_geojson_fp, max_route_points)
    if len(route_coords) >= 2:
        folium.PolyLine(
            locations=route_coords,
            color="#111111",
            weight=4,
            opacity=0.8,
            tooltip="simplified IB1E route axis",
        ).add_to(m)

    # Raw activity GPS track: downsampled line.
    track_points = df[[lat_col, lon_col]].values.tolist()
    track_points = downsample_points(track_points, max_track_points)

    if len(track_points) >= 2:
        folium.PolyLine(
            locations=track_points,
            color="#777777",
            weight=2,
            opacity=0.55,
            tooltip="downsampled raw GPS track",
        ).add_to(m)

    matched = df[df["route_context_match_status"] == "matched"].copy()
    no_dist = df[df["route_context_match_status"] == "no_activity_route_dist"].copy()
    unmatched = df[df["route_context_match_status"] == "unmatched"].copy()

    add_sample_points(
        m,
        matched,
        lat_col,
        lon_col,
        color="#1f78b4",
        layer_name="matched route-context points",
        max_points=max_marker_points,
        radius=3,
    )

    add_sample_points(
        m,
        no_dist,
        lat_col,
        lon_col,
        color="#e66101",
        layer_name="no_activity_route_dist / excluded observed points",
        max_points=max_marker_points,
        radius=3,
    )

    if len(unmatched) > 0:
        add_sample_points(
            m,
            unmatched,
            lat_col,
            lon_col,
            color="#d7191c",
            layer_name="unmatched route-context points",
            max_points=max_marker_points,
            radius=4,
        )

    # Start / end markers only.
    first = df.iloc[0]
    last = df.iloc[-1]

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
      <b>Light QA: activity_points_osm_nlsc_corrected_v1</b><br>
      route_folder: {route_folder}<br>
      activity_id: {activity_id}<br>
      rows: {len(df)}<br>
      matched: {len(matched)}<br>
      no_activity_route_dist: {len(no_dist)}<br>
      unmatched: {len(unmatched)}<br>
      markers per layer max: {max_marker_points}
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    folium.LayerControl(collapsed=False).add_to(m)

    out_root = out_dir / route_folder / activity_id
    out_root.mkdir(parents=True, exist_ok=True)

    out_fp = out_root / f"{route_folder}_{activity_id}_activity_points_osm_nlsc_corrected_qa_map_light.html"
    m.save(out_fp)

    return out_fp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Lightweight QA map for activity_points_osm_nlsc_corrected_v1."
    )

    parser.add_argument("--route-folder", default="qixing_lengshuikeng")
    parser.add_argument("--activity-id", required=True)
    parser.add_argument("--corrected-fp", required=True)
    parser.add_argument("--route-geojson-fp", required=True)
    parser.add_argument(
        "--out-dir",
        default=r"outputs\activity_points_osm_nlsc_corrected_v1_qa_map_light",
    )
    parser.add_argument("--max-track-points", type=int, default=600)
    parser.add_argument("--max-route-points", type=int, default=600)
    parser.add_argument("--max-marker-points", type=int, default=120)

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    out_fp = plot_light_map(
        corrected_fp=Path(args.corrected_fp),
        route_geojson_fp=Path(args.route_geojson_fp),
        route_folder=args.route_folder,
        activity_id=args.activity_id,
        out_dir=Path(args.out_dir),
        max_track_points=args.max_track_points,
        max_route_points=args.max_route_points,
        max_marker_points=args.max_marker_points,
    )

    print("Light QA map written:")
    print(out_fp)


if __name__ == "__main__":
    main()
