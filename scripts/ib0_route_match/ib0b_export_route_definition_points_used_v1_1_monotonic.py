# -*- coding: utf-8 -*-
"""
IB0B companion exporter v1.1:
Export route-definition control points projected onto the IB0B ordered mainline
with order-aware monotonic route-distance assignment.

Why monotonic?
--------------
For same-entry / out-and-back routes, the same coordinate may appear twice on
the ordered route axis. A nearest-point projection alone will map both start
and end to the first occurrence. This version assigns route distances in
control-point order, so end can map to the route tail.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, LineString


PROJECT_ROOT = Path(r"C:\mountain_work\115_osm")


def resolve_path(value):
    if value is None:
        return None
    p = Path(value)
    if p.is_absolute():
        return p
    return PROJECT_ROOT / p


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--case-id", required=True)
    ap.add_argument("--control-points-fp", required=True)
    ap.add_argument("--control-points-projection-fp", required=True)
    ap.add_argument("--ordered-path-fp", required=True)
    ap.add_argument("--out-dir", default="outputs/ib0b_mainline_route_definition_v1_3b")
    ap.add_argument("--input-stage", default="ib0_candidates")
    ap.add_argument("--sample-step-m", type=float, default=2.0)
    ap.add_argument("--anchor-to-line-warn-m", type=float, default=30.0)
    return ap.parse_args()


def require_file(fp: Path, label: str) -> Path:
    fp = resolve_path(fp)
    if not fp.exists():
        raise FileNotFoundError(f"Missing {label}: {fp.resolve()}")
    return fp


def normalize_id_text(text: str, key: str) -> str:
    if text is None:
        return ""
    m = re.search(rf"{re.escape(key)}=([^;]+)", str(text))
    return m.group(1) if m else ""


def truthy(value) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def ordered_geometry_to_line(gdf: gpd.GeoDataFrame) -> LineString:
    geoms = []
    for geom in gdf.geometry:
        if geom is None or geom.is_empty:
            continue
        if geom.geom_type == "LineString":
            geoms.append(geom)
        elif geom.geom_type == "MultiLineString":
            geoms.extend(list(geom.geoms))

    if not geoms:
        raise ValueError("No line geometry found in ordered path.")

    coords = []
    for line in geoms:
        line_coords = list(line.coords)
        if not line_coords:
            continue
        if not coords:
            coords.extend(line_coords)
        else:
            if coords[-1] == line_coords[0]:
                coords.extend(line_coords[1:])
            else:
                coords.extend(line_coords)

    return LineString(coords)


def make_samples(line: LineString, step_m: float):
    length = float(line.length)
    if length <= 0:
        raise ValueError("Ordered path length is zero.")

    dists = []
    d = 0.0
    while d < length:
        dists.append(d)
        d += step_m
    dists.append(length)

    pts = [line.interpolate(d) for d in dists]
    return dists, pts


def find_best_monotonic_dist(
    cp_point_m: Point,
    sample_dists,
    sample_pts,
    min_dist_m: float,
    max_dist_m: float,
):
    best = None

    for d, p in zip(sample_dists, sample_pts):
        if d < min_dist_m or d > max_dist_m:
            continue
        offset = cp_point_m.distance(p)
        if best is None or offset < best[1]:
            best = (d, offset, p)

    if best is None:
        # fallback: nearest among all samples, but mark by caller via impossible range if needed
        for d, p in zip(sample_dists, sample_pts):
            offset = cp_point_m.distance(p)
            if best is None or offset < best[1]:
                best = (d, offset, p)

    return best


def main():
    args = parse_args()

    control_fp = require_file(args.control_points_fp, "control points CSV")
    projection_fp = require_file(args.control_points_projection_fp, "IB0A projection CSV")
    ordered_fp = require_file(args.ordered_path_fp, "IB0B ordered path GeoJSON")
    out_dir = resolve_path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cps = pd.read_csv(control_fp).sort_values("order").reset_index(drop=True)
    proj = pd.read_csv(projection_fp)
    if "candidate_rank" in proj.columns:
        proj = proj[proj["candidate_rank"].astype(str) == "1"].copy()
    proj = proj.drop_duplicates(subset=["control_id"], keep="first")

    ordered = gpd.read_file(ordered_fp)
    if ordered.crs is None:
        ordered = ordered.set_crs("EPSG:4326")

    metric_crs = ordered.estimate_utm_crs()
    ordered_m = ordered.to_crs(metric_crs)
    line_m = ordered_geometry_to_line(ordered_m)
    length_m = float(line_m.length)

    sample_dists, sample_pts = make_samples(line_m, args.sample_step_m)

    n = len(cps)
    rows = []
    prev_dist = 0.0

    for i, cp in cps.iterrows():
        control_id = str(cp.get("control_id", ""))
        role = str(cp.get("control_role", ""))
        phase = str(cp.get("phase", ""))
        order = float(cp.get("order", i + 1))

        cp_pt_wgs = gpd.GeoSeries(
            [Point(float(cp["lon"]), float(cp["lat"]))],
            crs="EPSG:4326",
        )
        cp_pt_m = cp_pt_wgs.to_crs(metric_crs).iloc[0]

        # Monotonic search window.
        # First point can use route head; last point should use route tail.
        if i == 0:
            min_d = 0.0
            max_d = min(length_m, length_m * 0.15)
        elif i == n - 1:
            min_d = max(prev_dist, length_m * 0.85)
            max_d = length_m
        else:
            min_d = prev_dist
            # Give each remaining control point enough room.
            remaining = max(1, n - i - 1)
            max_d = length_m

        best_d, offset_m, snap_m = find_best_monotonic_dist(
            cp_pt_m,
            sample_dists,
            sample_pts,
            min_d,
            max_d,
        )

        # Ensure strict forward progress except for very close duplicates.
        if best_d < prev_dist:
            best_d = prev_dist
            snap_m = line_m.interpolate(best_d)
            offset_m = cp_pt_m.distance(snap_m)

        prev_dist = best_d

        snap_wgs = gpd.GeoSeries([snap_m], crs=metric_crs).to_crs("EPSG:4326").iloc[0]

        p = proj[proj["control_id"].astype(str) == control_id]
        p_row = p.iloc[0] if not p.empty else None

        matched_id_text = "" if p_row is None else str(p_row.get("matched_id_text", ""))
        route_action = str(cp.get("route_action", ""))
        required = str(cp.get("required", ""))

        included_in_required_way = (
            route_action == "required_way"
            or truthy(required)
            or role in {"ascent_via", "descent_via"}
        )

        rows.append(
            {
                "case_id": args.case_id,
                "control_id": control_id,
                "control_role": role,
                "phase": phase,
                "name": cp.get("name", ""),
                "lat": cp.get("lat", ""),
                "lon": cp.get("lon", ""),
                "required": required,
                "order": order,
                "route_action": route_action,
                "note": cp.get("note", ""),
                "projection_ok": "" if p_row is None else p_row.get("projection_ok", ""),
                "projection_offset_to_osm_m": "" if p_row is None else p_row.get("offset_to_osm_m", ""),
                "matched_id_text": matched_id_text,
                "osm_way_id_current": normalize_id_text(matched_id_text, "osm_way_id"),
                "osm_id_current": normalize_id_text(matched_id_text, "osm_id"),
                "highway": "" if p_row is None else p_row.get("highway", ""),
                "name_osm": "" if p_row is None else p_row.get("name_osm", ""),
                "route_role": "" if p_row is None else p_row.get("route_role", ""),
                "match_score": "" if p_row is None else p_row.get("match_score", ""),
                "overlap_ratio": "" if p_row is None else p_row.get("overlap_ratio", ""),
                "projected_lat": float(snap_wgs.y),
                "projected_lon": float(snap_wgs.x),
                "projected_route_dist_m": best_d,
                "nearest_ordered_path_offset_m": offset_m,
                "ordered_path_length_m": length_m,
                "included_in_required_way": included_in_required_way,
                "projection_method": "order_aware_monotonic_sampled",
                "route_point_warning": "offset_gt_warn_threshold" if offset_m > args.anchor_to_line_warn_m else "",
                "geometry": Point(float(snap_wgs.x), float(snap_wgs.y)),
            }
        )

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")

    out_csv = out_dir / f"{args.case_id}_route_definition_control_points_used_{args.input_stage}.csv"
    out_geojson = out_dir / f"{args.case_id}_route_definition_control_points_used_{args.input_stage}.geojson"

    gdf.drop(columns=["geometry"]).to_csv(out_csv, index=False, encoding="utf-8-sig")
    gdf.to_file(out_geojson, driver="GeoJSON")

    print("IB0B route-definition control points exported v1.1 monotonic")
    print("case_id:", args.case_id)
    print("ordered_path_length_m:", length_m)
    print("output CSV:", out_csv.resolve())
    print("output GeoJSON:", out_geojson.resolve())
    print("")
    print(
        gdf[
            [
                "control_id",
                "control_role",
                "phase",
                "route_action",
                "name",
                "projected_route_dist_m",
                "nearest_ordered_path_offset_m",
                "osm_way_id_current",
                "included_in_required_way",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
