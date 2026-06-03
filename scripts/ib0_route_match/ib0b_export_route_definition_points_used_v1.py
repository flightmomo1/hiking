# -*- coding: utf-8 -*-
"""
IB0B companion exporter:
Export route-definition control points projected onto the IB0B ordered mainline.

Purpose
-------
After IB0B builds the ordered mainline, this script records where each
route-definition control point lies on the ordered path.

Inputs
------
- --control-points-fp:
  Per-case route definition control points CSV exported from route_control_points_v1_3b.csv.

- --control-points-projection-fp:
  IB0A top-k projection CSV.

- --ordered-path-fp:
  IB0B ordered mainline GeoJSON.

Outputs
-------
<case_id>_route_definition_control_points_used_<input_stage>.csv
<case_id>_route_definition_control_points_used_<input_stage>.geojson
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, LineString, MultiLineString


PROJECT_ROOT = Path(r"C:\mountain_work\115_osm")


def resolve_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    p = Path(value)
    if p.is_absolute():
        return p
    return PROJECT_ROOT / p


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--case-id", required=True)
    ap.add_argument("--control-points-fp", required=True)
    ap.add_argument("--control-points-projection-fp", required=True)
    ap.add_argument("--ordered-path-fp", required=True)
    ap.add_argument("--out-dir", default="outputs/ib0b_mainline_route_definition_v1_3b")
    ap.add_argument("--input-stage", default="ib0_candidates")
    ap.add_argument("--anchor-to-line-warn-m", type=float, default=30.0)
    return ap.parse_args()


def require_file(fp: Path, label: str) -> Path:
    if not fp.exists():
        raise FileNotFoundError(f"Missing {label}: {fp.resolve()}")
    return fp


def get_single_linestring(gdf: gpd.GeoDataFrame) -> LineString:
    if gdf.empty:
        raise ValueError("ordered path GeoDataFrame is empty")

    geom = gdf.geometry.iloc[0]

    if geom is None or geom.is_empty:
        raise ValueError("ordered path geometry is empty")

    if geom.geom_type == "LineString":
        return geom

    if geom.geom_type == "MultiLineString":
        coords = []
        for part in geom.geoms:
            part_coords = list(part.coords)
            if not coords:
                coords.extend(part_coords)
            else:
                if coords[-1] == part_coords[0]:
                    coords.extend(part_coords[1:])
                else:
                    coords.extend(part_coords)
        return LineString(coords)

    raise ValueError(f"Unsupported ordered path geometry type: {geom.geom_type}")


def parse_matched_id(text: str, key: str) -> str:
    if text is None:
        return ""
    m = re.search(rf"{re.escape(key)}=([^;]+)", str(text))
    if not m:
        return ""
    return m.group(1)


def truthy(value) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def main() -> None:
    args = parse_args()

    control_fp = require_file(resolve_path(args.control_points_fp), "control points CSV")
    projection_fp = require_file(resolve_path(args.control_points_projection_fp), "IB0A projection CSV")
    ordered_fp = require_file(resolve_path(args.ordered_path_fp), "IB0B ordered path GeoJSON")
    out_dir = resolve_path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    out_csv = out_dir / f"{args.case_id}_route_definition_control_points_used_{args.input_stage}.csv"
    out_geojson = out_dir / f"{args.case_id}_route_definition_control_points_used_{args.input_stage}.geojson"

    cps = pd.read_csv(control_fp)
    proj = pd.read_csv(projection_fp)

    if "candidate_rank" in proj.columns:
        proj_rank1 = proj[proj["candidate_rank"].astype(str) == "1"].copy()
    else:
        proj_rank1 = proj.copy()

    # One rank-1 projection per control_id.
    proj_rank1 = proj_rank1.drop_duplicates(subset=["control_id"], keep="first")

    ordered = gpd.read_file(ordered_fp)
    if ordered.crs is None:
        ordered = ordered.set_crs("EPSG:4326")

    metric_crs = ordered.estimate_utm_crs()
    ordered_m = ordered.to_crs(metric_crs)
    ordered_line_m = get_single_linestring(ordered_m)
    ordered_len_m = float(ordered_line_m.length)

    rows = []

    for _, cp in cps.sort_values("order").iterrows():
        control_id = str(cp.get("control_id", ""))
        cp_lat = float(cp["lat"])
        cp_lon = float(cp["lon"])

        cp_wgs = gpd.GeoSeries([Point(cp_lon, cp_lat)], crs="EPSG:4326")
        cp_m = cp_wgs.to_crs(metric_crs).iloc[0]

        route_dist_m = float(ordered_line_m.project(cp_m))
        snap_m = ordered_line_m.interpolate(route_dist_m)
        offset_m = float(cp_m.distance(snap_m))

        snap_wgs = gpd.GeoSeries([snap_m], crs=metric_crs).to_crs("EPSG:4326").iloc[0]

        p = proj_rank1[proj_rank1["control_id"].astype(str) == control_id]
        p_row = p.iloc[0] if not p.empty else None

        matched_id_text = "" if p_row is None else str(p_row.get("matched_id_text", ""))
        osm_way_id_current = parse_matched_id(matched_id_text, "osm_way_id")
        osm_id_current = parse_matched_id(matched_id_text, "osm_id")

        projection_ok = "" if p_row is None else p_row.get("projection_ok", "")
        projection_offset_to_osm_m = "" if p_row is None else p_row.get("offset_to_osm_m", "")

        route_action = str(cp.get("route_action", ""))
        required = str(cp.get("required", ""))

        included_in_required_way = (
            route_action == "required_way"
            or truthy(required)
            or str(cp.get("control_role", "")) in {"ascent_via", "descent_via"}
        )

        rows.append(
            {
                "case_id": args.case_id,
                "control_id": control_id,
                "control_role": cp.get("control_role", ""),
                "phase": cp.get("phase", ""),
                "name": cp.get("name", ""),
                "lat": cp_lat,
                "lon": cp_lon,
                "required": required,
                "order": cp.get("order", ""),
                "route_action": route_action,
                "note": cp.get("note", ""),

                "projection_ok": projection_ok,
                "projection_offset_to_osm_m": projection_offset_to_osm_m,
                "matched_id_text": matched_id_text,
                "osm_way_id_current": osm_way_id_current,
                "osm_id_current": osm_id_current,
                "highway": "" if p_row is None else p_row.get("highway", ""),
                "name_osm": "" if p_row is None else p_row.get("name_osm", ""),
                "route_role": "" if p_row is None else p_row.get("route_role", ""),
                "match_score": "" if p_row is None else p_row.get("match_score", ""),
                "overlap_ratio": "" if p_row is None else p_row.get("overlap_ratio", ""),

                "projected_lat": float(snap_wgs.y),
                "projected_lon": float(snap_wgs.x),
                "projected_route_dist_m": route_dist_m,
                "nearest_ordered_path_offset_m": offset_m,
                "ordered_path_length_m": ordered_len_m,
                "included_in_required_way": included_in_required_way,
                "route_point_warning": "offset_gt_warn_threshold" if offset_m > args.anchor_to_line_warn_m else "",
                "geometry": Point(float(snap_wgs.x), float(snap_wgs.y)),
            }
        )

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")

    csv_cols = [c for c in gdf.columns if c != "geometry"]
    gdf[csv_cols].to_csv(out_csv, index=False, encoding="utf-8-sig")
    gdf.to_file(out_geojson, driver="GeoJSON")

    print("IB0B route-definition control points exported")
    print(f"case_id: {args.case_id}")
    print(f"ordered_path: {ordered_fp.resolve()}")
    print(f"control_points: {control_fp.resolve()}")
    print(f"projection: {projection_fp.resolve()}")
    print(f"output CSV: {out_csv.resolve()}")
    print(f"output GeoJSON: {out_geojson.resolve()}")

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
