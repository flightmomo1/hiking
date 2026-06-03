from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import geopandas as gpd
import folium


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


def safe_float(v):
    try:
        if pd.isna(v):
            return None
        return float(v)
    except Exception:
        return None


def compact(v, max_len: int = 80) -> str:
    if pd.isna(v):
        return ""
    s = str(v)
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s



def sanitize_gdf_for_folium(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Folium serializes GeoDataFrame through __geo_interface__.
    Pandas Timestamp / NA / mixed object values can break json.dumps().
    Convert all non-geometry properties into JSON-safe scalar values.
    """
    out = gdf.copy()

    for col in out.columns:
        if col == out.geometry.name:
            continue

        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].astype(str)
            continue

        def _safe(v):
            if pd.isna(v):
                return None

            # pandas Timestamp / datetime-like
            if hasattr(v, "isoformat"):
                try:
                    return v.isoformat()
                except Exception:
                    pass

            # numpy / pandas scalar values
            try:
                if hasattr(v, "item"):
                    return v.item()
            except Exception:
                pass

            # keep simple scalar values
            if isinstance(v, (str, int, float, bool)):
                return v

            return str(v)

        out[col] = out[col].apply(_safe)

    return out


def make_popup(row: pd.Series) -> str:
    fields = [
        "activity_id",
        "elapsed_sec",
        "timestamp",
        "heart_rate_bpm",
        "usable_on_route",
        "excluded_reason",
        "reliable_route_dist_m",
        "projected_route_dist_m",
        "offset_to_mainline_m",
        "route_context_match_status",
        "route_context_join_dist_diff_m",
        "route_context_ele_smooth",
        "route_context_slope_band_window_nlsc",
        "route_context_osm_terrain_combined_risk_score",
        "route_context_osm_terrain_combined_risk_band",
        "route_context_osm_highway",
        "route_context_osm_surface",
    ]

    lines = []
    for f in fields:
        if f in row.index:
            lines.append(f"<b>{f}</b>: {compact(row[f])}")

    return "<br>".join(lines)


def add_route_context_layer(m: folium.Map, route_geojson_fp: Path) -> None:
    if not route_geojson_fp.exists():
        return

    gdf = gpd.read_file(route_geojson_fp)

    if gdf.empty:
        return

    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    # Make all GeoJSON properties JSON-serializable for Folium.
    gdf = sanitize_gdf_for_folium(gdf)

    def style_fn(feature):
        props = feature.get("properties", {})
        band = props.get("osm_terrain_combined_risk_band") or props.get("risk_band") or ""

        color = "#444444"
        weight = 4

        if band == "high":
            color = "#d73027"
        elif band == "moderate":
            color = "#fc8d59"
        elif band == "low":
            color = "#91bfdb"

        return {
            "color": color,
            "weight": weight,
            "opacity": 0.75,
        }

    folium.GeoJson(
        gdf,
        name="IB1E route context / standard route axis",
        style_function=style_fn,
        tooltip=folium.GeoJsonTooltip(
            fields=[
                c for c in [
                    "dist_m",
                    "route_dist_m",
                    "osm_terrain_combined_risk_band",
                    "osm_terrain_combined_risk_score",
                    "slope_band_window_nlsc",
                    "osm_highway",
                    "osm_surface",
                ]
                if c in gdf.columns
            ],
            aliases=None,
            sticky=False,
        ),
    ).add_to(m)


def plot_qa_map(
    corrected_fp: Path,
    route_geojson_fp: Path,
    route_folder: str,
    activity_id: str,
    out_dir: Path,
    max_points_per_layer: int,
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

    m = folium.Map(location=[center_lat, center_lon], zoom_start=15, tiles="OpenStreetMap")

    add_route_context_layer(m, route_geojson_fp)

    # Raw track line
    track_points = df[[lat_col, lon_col]].dropna().values.tolist()
    if len(track_points) >= 2:
        folium.PolyLine(
            locations=track_points,
            color="#777777",
            weight=2,
            opacity=0.55,
            tooltip="raw activity GPS track",
        ).add_to(m)

    matched = df[df["route_context_match_status"] == "matched"].copy()
    no_dist = df[df["route_context_match_status"] == "no_activity_route_dist"].copy()
    unmatched = df[df["route_context_match_status"] == "unmatched"].copy()

    def sample_layer(layer_df: pd.DataFrame) -> pd.DataFrame:
        if len(layer_df) <= max_points_per_layer:
            return layer_df
        step = max(1, len(layer_df) // max_points_per_layer)
        return layer_df.iloc[::step].copy()

    matched_s = sample_layer(matched)
    no_dist_s = sample_layer(no_dist)
    unmatched_s = sample_layer(unmatched)

    matched_fg = folium.FeatureGroup(name=f"matched usable route-context points ({len(matched)})")
    for _, row in matched_s.iterrows():
        folium.CircleMarker(
            location=[row[lat_col], row[lon_col]],
            radius=3,
            color="#1f78b4",
            fill=True,
            fill_color="#1f78b4",
            fill_opacity=0.75,
            opacity=0.75,
            popup=folium.Popup(make_popup(row), max_width=450),
        ).add_to(matched_fg)
    matched_fg.add_to(m)

    no_dist_fg = folium.FeatureGroup(name=f"no activity route dist / excluded observed points ({len(no_dist)})")
    for _, row in no_dist_s.iterrows():
        folium.CircleMarker(
            location=[row[lat_col], row[lon_col]],
            radius=3,
            color="#e66101",
            fill=True,
            fill_color="#e66101",
            fill_opacity=0.75,
            opacity=0.75,
            popup=folium.Popup(make_popup(row), max_width=450),
        ).add_to(no_dist_fg)
    no_dist_fg.add_to(m)

    if len(unmatched) > 0:
        unmatched_fg = folium.FeatureGroup(name=f"unmatched route context points ({len(unmatched)})")
        for _, row in unmatched_s.iterrows():
            folium.CircleMarker(
                location=[row[lat_col], row[lon_col]],
                radius=4,
                color="#d7191c",
                fill=True,
                fill_color="#d7191c",
                fill_opacity=0.9,
                opacity=0.9,
                popup=folium.Popup(make_popup(row), max_width=450),
            ).add_to(unmatched_fg)
        unmatched_fg.add_to(m)

    # Start / end markers
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
      <b>activity_points_osm_nlsc_corrected_v1 QA</b><br>
      route_folder: {route_folder}<br>
      activity_id: {activity_id}<br>
      rows: {len(df)}<br>
      matched: {len(matched)}<br>
      no_activity_route_dist: {len(no_dist)}<br>
      unmatched: {len(unmatched)}
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    folium.LayerControl(collapsed=False).add_to(m)

    out_root = out_dir / route_folder / activity_id
    out_root.mkdir(parents=True, exist_ok=True)

    out_fp = out_root / f"{route_folder}_{activity_id}_activity_points_osm_nlsc_corrected_qa_map.html"
    m.save(out_fp)

    return out_fp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot QA map for activity_points_osm_nlsc_corrected_v1."
    )

    parser.add_argument("--route-folder", default="qixing_lengshuikeng")
    parser.add_argument("--activity-id", required=True)
    parser.add_argument("--corrected-fp", required=True)
    parser.add_argument("--route-geojson-fp", required=True)
    parser.add_argument(
        "--out-dir",
        default=r"outputs\activity_points_osm_nlsc_corrected_v1_qa_map",
    )
    parser.add_argument(
        "--max-points-per-layer",
        type=int,
        default=2500,
        help="Downsample display points per layer for HTML performance.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    out_fp = plot_qa_map(
        corrected_fp=Path(args.corrected_fp),
        route_geojson_fp=Path(args.route_geojson_fp),
        route_folder=args.route_folder,
        activity_id=args.activity_id,
        out_dir=Path(args.out_dir),
        max_points_per_layer=args.max_points_per_layer,
    )

    print("QA map written:")
    print(out_fp)


if __name__ == "__main__":
    main()
