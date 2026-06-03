# -*- coding: utf-8 -*-
"""
IB3A0: Fast activity-vs-mainline screening.

Purpose
-------
Before full IB3A sequence mapmatching, quickly classify each activity GPS row
against an already-built trimmed mainline:

- on_mainline
- near_mainline_low_confidence
- off_mainline
- post_route_candidate
- invalid_gps

This script does NOT replace IB3A sequence mapmatching. It is a lightweight
pre-screening / segmentation tool so that only mainline-like activity segments
need to enter full mapmatching.

Example
-------
python scripts/ib3_activity_environment/ib3a0_screen_activity_against_mainline.py ^
  --case-id qixing_lengshuikeng_main_peak_20260523 ^
  --route-folder qixing_lengshuikeng ^
  --activity-id 37_1 ^
  --activity-fp activity_input/csv/qixing_lengshuikeng/37_1.csv
"""

from __future__ import annotations

import argparse
import html
import math
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import CRS
from shapely.geometry import LineString, Point


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--case-id", required=True, help="Route case id.")
    parser.add_argument("--route-folder", required=True, help="Route folder, e.g. qixing_lengshuikeng.")
    parser.add_argument("--activity-id", required=True, help="Activity id, e.g. 37_1.")

    parser.add_argument(
        "--mainline-fp",
        type=Path,
        default=None,
        help=(
            "Trimmed mainline GeoJSON. Default: "
            "outputs/ib0d_trimmed_mainline/<case-id>/<case-id>_mainline_ordered_path_trimmed.geojson"
        ),
    )
    parser.add_argument(
        "--activity-fp",
        type=Path,
        default=None,
        help=(
            "Activity CSV. If omitted, the script searches common activity_input / outputs locations."
        ),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("outputs/ib3a0_activity_mainline_screening"),
        help="Output root.",
    )

    parser.add_argument("--on-mainline-m", type=float, default=20.0)
    parser.add_argument("--near-mainline-m", type=float, default=50.0)
    parser.add_argument("--post-route-tail-m", type=float, default=120.0)
    parser.add_argument("--min-segment-duration-sec", type=float, default=10.0)
    parser.add_argument("--min-segment-rows", type=int, default=5)

    parser.add_argument(
        "--metric-crs",
        default=None,
        help="Metric CRS such as EPSG:32651. If omitted, infer UTM from mainline centroid.",
    )
    parser.add_argument(
        "--map-point-step",
        type=int,
        default=10,
        help="Draw every Nth activity point in HTML map.",
    )
    parser.add_argument(
        "--no-map",
        action="store_true",
        help="Skip debug HTML map output.",
    )

    return parser.parse_args()


def require_file(path: Path, label: str) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path.resolve()}")
    return path


def infer_metric_crs_from_lonlat(lon: float, lat: float) -> CRS:
    zone = int((lon + 180.0) // 6.0) + 1
    epsg = 32600 + zone if lat >= 0 else 32700 + zone
    return CRS.from_epsg(epsg)


def default_mainline_fp(case_id: str) -> Path:
    return (
        Path("outputs")
        / "ib0d_trimmed_mainline"
        / case_id
        / f"{case_id}_mainline_ordered_path_trimmed.geojson"
    )


def candidate_activity_paths(route_folder: str, activity_id: str) -> list[Path]:
    return [
        Path("activity_input") / "csv" / route_folder / f"{activity_id}.csv",
        Path("activity_input") / "csv" / route_folder / f"{activity_id}_standardized.csv",
        Path("outputs") / "activity_standardized" / route_folder / f"{activity_id}.csv",
        Path("outputs") / "activity_standardized" / route_folder / f"{activity_id}_standardized.csv",
        Path("outputs") / "ib3_standardized_activity" / route_folder / f"{activity_id}.csv",
        Path("outputs") / "ib3_standardized_activity" / route_folder / f"{activity_id}_standardized.csv",
    ]


def infer_activity_fp(route_folder: str, activity_id: str) -> Path:
    for fp in candidate_activity_paths(route_folder, activity_id):
        if fp.exists():
            return fp
    raise FileNotFoundError(
        "Unable to infer activity CSV. Provide --activity-fp explicitly. Tried:\n"
        + "\n".join(str(p) for p in candidate_activity_paths(route_folder, activity_id))
    )


def first_existing_column(df: pd.DataFrame, names: Iterable[str]) -> str | None:
    for name in names:
        if name in df.columns:
            return name
    return None


def normalize_activity_columns(df: pd.DataFrame, source_fp: Path) -> pd.DataFrame:
    out = df.copy()
    out["activity_source_fp"] = str(source_fp)

    lat_col = first_existing_column(out, ["raw_lat", "lat", "latitude", "position_lat"])
    lon_col = first_existing_column(out, ["raw_lon", "lon", "lng", "longitude", "position_long"])

    if lat_col is None or lon_col is None:
        raise KeyError(
            "Activity CSV must contain lat/lon columns. Accepted names: "
            "raw_lat/lat/latitude/position_lat and raw_lon/lon/lng/longitude/position_long"
        )

    out["raw_lat"] = pd.to_numeric(out[lat_col], errors="coerce")
    out["raw_lon"] = pd.to_numeric(out[lon_col], errors="coerce")

    if "row_index" not in out.columns:
        out["row_index"] = np.arange(len(out), dtype=int)
    out["row_index"] = pd.to_numeric(out["row_index"], errors="coerce").fillna(-1).astype(int)

    if "point_index" not in out.columns:
        out["point_index"] = out["row_index"]
    out["point_index"] = pd.to_numeric(out["point_index"], errors="coerce")

    elapsed_col = first_existing_column(out, ["elapsed_sec", "timestamp_s", "time_s", "seconds"])
    if elapsed_col is not None:
        out["elapsed_sec"] = pd.to_numeric(out[elapsed_col], errors="coerce")
    else:
        out["elapsed_sec"] = np.arange(len(out), dtype=float)

    ele_col = first_existing_column(out, ["raw_ele_m", "ele_m", "altitude_m", "enhanced_altitude", "altitude"])
    if ele_col is not None:
        out["raw_ele_m"] = pd.to_numeric(out[ele_col], errors="coerce")
    else:
        out["raw_ele_m"] = np.nan

    hr_col = first_existing_column(out, ["heart_rate_bpm", "heart_rate", "hr", "HR"])
    if hr_col is not None:
        out["heart_rate_bpm"] = pd.to_numeric(out[hr_col], errors="coerce")
    else:
        out["heart_rate_bpm"] = np.nan

    sort_cols = [c for c in ["elapsed_sec", "row_index"] if c in out.columns]
    out = out.sort_values(sort_cols, na_position="last").reset_index(drop=True)

    return out


def read_mainline(mainline_fp: Path, metric_crs: str | None) -> tuple[gpd.GeoDataFrame, LineString, CRS]:
    gdf = gpd.read_file(mainline_fp)
    if gdf.empty:
        raise ValueError(f"Mainline GeoJSON is empty: {mainline_fp}")

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")

    geom = gdf.geometry.iloc[0]
    if geom.geom_type == "MultiLineString":
        line_wgs84 = max(list(geom.geoms), key=lambda g: g.length)
    elif geom.geom_type == "LineString":
        line_wgs84 = geom
    else:
        raise TypeError(f"Unsupported mainline geometry: {geom.geom_type}")

    centroid = gpd.GeoSeries([line_wgs84], crs=gdf.crs).to_crs("EPSG:4326").iloc[0].centroid
    crs_metric = CRS.from_user_input(metric_crs) if metric_crs else infer_metric_crs_from_lonlat(centroid.x, centroid.y)

    line_m = gpd.GeoSeries([line_wgs84], crs=gdf.crs).to_crs(crs_metric).iloc[0]
    mainline_m = gpd.GeoDataFrame(gdf.copy(), geometry=gdf.geometry, crs=gdf.crs).to_crs(crs_metric)

    return mainline_m, line_m, crs_metric


def project_activity_to_mainline(
    activity: pd.DataFrame,
    line_m: LineString,
    crs_metric: CRS,
) -> pd.DataFrame:
    out = activity.copy()
    valid = out["raw_lat"].notna() & out["raw_lon"].notna()

    gdf = gpd.GeoDataFrame(
        out.loc[valid].copy(),
        geometry=[
            Point(lon, lat)
            for lon, lat in zip(out.loc[valid, "raw_lon"], out.loc[valid, "raw_lat"])
        ],
        crs="EPSG:4326",
    ).to_crs(crs_metric)

    projected = []
    offsets = []
    proj_x = []
    proj_y = []

    for pt in gdf.geometry:
        d = float(line_m.project(pt))
        p = line_m.interpolate(d)
        projected.append(d)
        offsets.append(float(pt.distance(p)))
        proj_x.append(p.x)
        proj_y.append(p.y)

    out["valid_gps"] = False
    out["projected_route_dist_m"] = np.nan
    out["offset_m"] = np.nan
    out["projected_x"] = np.nan
    out["projected_y"] = np.nan

    valid_indices = out.index[valid].to_numpy()
    out.loc[valid_indices, "valid_gps"] = True
    out.loc[valid_indices, "projected_route_dist_m"] = projected
    out.loc[valid_indices, "offset_m"] = offsets
    out.loc[valid_indices, "projected_x"] = proj_x
    out.loc[valid_indices, "projected_y"] = proj_y

    return out


def classify_points(
    df: pd.DataFrame,
    route_length_m: float,
    on_mainline_m: float,
    near_mainline_m: float,
    post_route_tail_m: float,
) -> pd.DataFrame:
    out = df.copy()

    state = np.full(len(out), "invalid_gps", dtype=object)

    valid = out["valid_gps"].fillna(False).to_numpy()
    offset = pd.to_numeric(out["offset_m"], errors="coerce")
    dist = pd.to_numeric(out["projected_route_dist_m"], errors="coerce")

    on_mask = valid & offset.le(on_mainline_m).to_numpy()
    near_mask = valid & offset.gt(on_mainline_m).to_numpy() & offset.le(near_mainline_m).to_numpy()
    off_mask = valid & offset.gt(near_mainline_m).to_numpy()

    state[on_mask] = "on_mainline"
    state[near_mask] = "near_mainline_low_confidence"
    state[off_mask] = "off_mainline"

    # Post-route heuristic:
    # If projection is close to the route tail and offset is not on-mainline,
    # it is likely terminal wandering / recording after route completion.
    tail_start = max(0.0, route_length_m - post_route_tail_m)
    post_mask = valid & dist.ge(tail_start).to_numpy() & offset.gt(on_mainline_m).to_numpy()
    state[post_mask] = "post_route_candidate"

    out["screening_state"] = state
    out["usable_for_mainline_candidate"] = out["screening_state"].eq("on_mainline")

    return out


def build_segments(
    points: pd.DataFrame,
    min_segment_duration_sec: float,
    min_segment_rows: int,
) -> pd.DataFrame:
    df = points.copy().reset_index(drop=True)
    if df.empty:
        return pd.DataFrame()

    state = df["screening_state"].fillna("unknown").astype(str)
    run_id = (state != state.shift()).cumsum()

    rows = []
    for sid, g in df.groupby(run_id):
        start = g.iloc[0]
        end = g.iloc[-1]

        elapsed_start = float(start["elapsed_sec"]) if pd.notna(start["elapsed_sec"]) else np.nan
        elapsed_end = float(end["elapsed_sec"]) if pd.notna(end["elapsed_sec"]) else np.nan
        duration = elapsed_end - elapsed_start if np.isfinite(elapsed_start) and np.isfinite(elapsed_end) else np.nan

        state_name = str(start["screening_state"])
        segment_type = {
            "on_mainline": "on_route_segment",
            "near_mainline_low_confidence": "near_route_uncertain_segment",
            "off_mainline": "off_route_segment",
            "post_route_candidate": "post_route_recording",
            "invalid_gps": "invalid_gps_segment",
        }.get(state_name, "unknown_segment")

        rows.append(
            {
                "segment_id": len(rows),
                "screening_state": state_name,
                "segment_type": segment_type,
                "start_row_index": int(start["row_index"]),
                "end_row_index": int(end["row_index"]),
                "start_elapsed_sec": elapsed_start,
                "end_elapsed_sec": elapsed_end,
                "duration_sec": duration,
                "row_count": int(len(g)),
                "start_projected_route_dist_m": float(start["projected_route_dist_m"]) if pd.notna(start["projected_route_dist_m"]) else np.nan,
                "end_projected_route_dist_m": float(end["projected_route_dist_m"]) if pd.notna(end["projected_route_dist_m"]) else np.nan,
                "min_projected_route_dist_m": float(pd.to_numeric(g["projected_route_dist_m"], errors="coerce").min()),
                "max_projected_route_dist_m": float(pd.to_numeric(g["projected_route_dist_m"], errors="coerce").max()),
                "offset_mean_m": float(pd.to_numeric(g["offset_m"], errors="coerce").mean()),
                "offset_p95_m": float(pd.to_numeric(g["offset_m"], errors="coerce").quantile(0.95)),
                "offset_max_m": float(pd.to_numeric(g["offset_m"], errors="coerce").max()),
                "suggested_label": segment_type,
                "is_short_segment": bool(
                    (len(g) < min_segment_rows)
                    or (np.isfinite(duration) and duration < min_segment_duration_sec)
                ),
            }
        )

    seg = pd.DataFrame(rows)

    # Relabel off-route segments that are bounded by on-route segments.
    for i in range(1, len(seg) - 1):
        if seg.loc[i, "segment_type"] == "off_route_segment":
            prev_type = seg.loc[i - 1, "segment_type"]
            next_type = seg.loc[i + 1, "segment_type"]
            if prev_type == "on_route_segment" and next_type == "on_route_segment":
                seg.loc[i, "segment_type"] = "off_route_excursion_return"
                seg.loc[i, "suggested_label"] = "off_route_excursion_return"

    return seg


def write_summary(
    out_fp: Path,
    args: argparse.Namespace,
    mainline_fp: Path,
    activity_fp: Path,
    route_length_m: float,
    points: pd.DataFrame,
    segments: pd.DataFrame,
) -> None:
    state_counts = points["screening_state"].value_counts(dropna=False).to_dict()
    off_segments = int(segments["segment_type"].astype(str).str.contains("off_route").sum()) if not segments.empty else 0
    post_segments = int((segments["segment_type"] == "post_route_recording").sum()) if not segments.empty else 0

    lines = [
        "IB3A0 activity vs mainline screening",
        f"case_id: {args.case_id}",
        f"route_folder: {args.route_folder}",
        f"activity_id: {args.activity_id}",
        f"mainline_fp: {mainline_fp.as_posix()}",
        f"activity_fp: {activity_fp.as_posix()}",
        f"route_length_m: {route_length_m:.3f}",
        f"rows_total: {len(points)}",
        f"valid_gps_rows: {int(points['valid_gps'].sum())}",
        f"on_mainline_rows: {state_counts.get('on_mainline', 0)}",
        f"near_mainline_rows: {state_counts.get('near_mainline_low_confidence', 0)}",
        f"off_mainline_rows: {state_counts.get('off_mainline', 0)}",
        f"post_route_candidate_rows: {state_counts.get('post_route_candidate', 0)}",
        f"segment_count: {len(segments)}",
        f"off_route_segment_count: {off_segments}",
        f"post_route_segment_count: {post_segments}",
        f"max_offset_m: {pd.to_numeric(points['offset_m'], errors='coerce').max():.3f}",
        f"offset_p95_m: {pd.to_numeric(points['offset_m'], errors='coerce').quantile(0.95):.3f}",
        f"route_coverage_min_m: {pd.to_numeric(points['projected_route_dist_m'], errors='coerce').min():.3f}",
        f"route_coverage_max_m: {pd.to_numeric(points['projected_route_dist_m'], errors='coerce').max():.3f}",
        "",
        "screening_state_counts:",
    ]

    for k, v in state_counts.items():
        lines.append(f"- {k}: {v}")

    if not segments.empty:
        lines.extend(["", "segments:"])
        for _, r in segments.iterrows():
            lines.append(
                f"- segment {int(r.segment_id)} {r.segment_type}: "
                f"rows {int(r.start_row_index)}-{int(r.end_row_index)}, "
                f"duration {float(r.duration_sec):.1f}s, "
                f"route_dist {float(r.min_projected_route_dist_m):.1f}-{float(r.max_projected_route_dist_m):.1f}m, "
                f"offset_mean {float(r.offset_mean_m):.1f}m, "
                f"offset_max {float(r.offset_max_m):.1f}m"
            )

    out_fp.write_text("\n".join(lines), encoding="utf-8")


def state_color(state: str) -> str:
    return {
        "on_mainline": "#16a34a",
        "near_mainline_low_confidence": "#d97706",
        "off_mainline": "#dc2626",
        "post_route_candidate": "#7c3aed",
        "invalid_gps": "#64748b",
    }.get(str(state), "#64748b")


def write_debug_map(
    out_fp: Path,
    mainline_wgs84_fp: Path,
    points: pd.DataFrame,
    map_point_step: int,
) -> None:
    try:
        import folium
    except ImportError:
        print("folium not installed; skip HTML map")
        return

    mainline = gpd.read_file(mainline_wgs84_fp)
    if mainline.crs is None:
        mainline = mainline.set_crs("EPSG:4326")
    mainline = mainline.to_crs("EPSG:4326")

    geom = mainline.geometry.iloc[0]
    coords = list(geom.coords) if geom.geom_type == "LineString" else list(max(geom.geoms, key=lambda g: g.length).coords)
    center = [coords[len(coords) // 2][1], coords[len(coords) // 2][0]]

    m = folium.Map(location=center, zoom_start=15, tiles="OpenStreetMap")

    folium.PolyLine(
        locations=[(lat, lon) for lon, lat in coords],
        color="#2563eb",
        weight=4,
        opacity=0.8,
        tooltip="trimmed mainline",
    ).add_to(m)

    sample = points.iloc[:: max(1, int(map_point_step))].copy()
    for _, r in sample.iterrows():
        if not bool(r.get("valid_gps", False)):
            continue
        popup = "<br>".join(
            [
                f"row_index: {html.escape(str(r.get('row_index', '')))}",
                f"elapsed_sec: {html.escape(str(r.get('elapsed_sec', '')))}",
                f"state: {html.escape(str(r.get('screening_state', '')))}",
                f"projected_route_dist_m: {float(r.get('projected_route_dist_m', np.nan)):.1f}",
                f"offset_m: {float(r.get('offset_m', np.nan)):.1f}",
            ]
        )
        folium.CircleMarker(
            location=[float(r["raw_lat"]), float(r["raw_lon"])],
            radius=3,
            color=state_color(str(r["screening_state"])),
            fill=True,
            fill_opacity=0.7,
            opacity=0.8,
            popup=popup,
        ).add_to(m)

    m.save(out_fp)


def main() -> None:
    args = parse_args()

    mainline_fp = args.mainline_fp or default_mainline_fp(args.case_id)
    mainline_fp = require_file(Path(mainline_fp), "trimmed mainline")

    activity_fp = args.activity_fp or infer_activity_fp(args.route_folder, args.activity_id)
    activity_fp = require_file(Path(activity_fp), "activity CSV")

    out_dir = args.out_dir / args.route_folder / args.activity_id
    out_dir.mkdir(parents=True, exist_ok=True)

    mainline_m, line_m, crs_metric = read_mainline(mainline_fp, args.metric_crs)
    route_length_m = float(line_m.length)

    activity = normalize_activity_columns(pd.read_csv(activity_fp, low_memory=False), activity_fp)
    points = project_activity_to_mainline(activity, line_m, crs_metric)
    points = classify_points(
        points,
        route_length_m=route_length_m,
        on_mainline_m=args.on_mainline_m,
        near_mainline_m=args.near_mainline_m,
        post_route_tail_m=args.post_route_tail_m,
    )
    segments = build_segments(
        points,
        min_segment_duration_sec=args.min_segment_duration_sec,
        min_segment_rows=args.min_segment_rows,
    )

    stem = f"{args.route_folder}_{args.activity_id}_activity_mainline_screening"
    out_points = out_dir / f"{stem}_points.csv"
    out_segments = out_dir / f"{stem}_segments.csv"
    out_summary = out_dir / f"{stem}_summary.txt"
    out_map = out_dir / f"{stem}_map.html"

    points.to_csv(out_points, index=False, encoding="utf-8-sig")
    segments.to_csv(out_segments, index=False, encoding="utf-8-sig")
    write_summary(out_summary, args, mainline_fp, activity_fp, route_length_m, points, segments)

    if not args.no_map:
        write_debug_map(out_map, mainline_fp, points, args.map_point_step)

    print("IB3A0 activity mainline screening written")
    print(f"metric CRS: {crs_metric.to_string()}")
    print(f"mainline: {mainline_fp.resolve()}")
    print(f"activity: {activity_fp.resolve()}")
    print(f"points CSV: {out_points.resolve()}")
    print(f"segments CSV: {out_segments.resolve()}")
    print(f"summary TXT: {out_summary.resolve()}")
    if not args.no_map:
        print(f"debug map HTML: {out_map.resolve()}")
    print("screening_state:")
    print(points["screening_state"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
