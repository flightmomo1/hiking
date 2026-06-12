#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IB3W route-scoped station candidate selection v1.

Purpose:
- Select weather/water station candidates for one imported route.
- Use global station metadata cache as station registry.
- Use IB1E route profile enriched CSV as route geometry/terrain source.
- Compute nearest route point, distance_to_route_m, nearest_route_km.
- Split weather and water candidates.
- Do NOT perform weather/hydro fusion.
- Do NOT perform temporal coverage audit.
- Do NOT modify route risk, radar, THCI, or formal adapter outputs.

This script is intentionally route-scoped.
The global station registry is a candidate source, not the fusion input itself.
"""

from __future__ import annotations

import argparse
import csv
import html
import math
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


EARTH_RADIUS_M = 6371008.8


def parse_float(value: object) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        if text.lower() in {"nan", "none", "null"}:
            return None
        return float(text)
    except ValueError:
        return None


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def load_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: List[Dict[str, object]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def candidate_role(rank: int) -> str:
    if rank <= 3:
        return "primary"
    if rank <= 10:
        return "secondary"
    if rank <= 20:
        return "fallback"
    return "excluded"


def route_elevation_from_row(row: Dict[str, str]) -> Tuple[Optional[float], str]:
    """
    Prefer ele_smooth because IB1E route profile keeps activity/route elevation continuity.
    Also preserve NLSC window midpoint if available as route terrain context.
    """
    ele_smooth = parse_float(row.get("ele_smooth"))
    if ele_smooth is not None:
        return ele_smooth, "ele_smooth"

    ele_gpx = parse_float(row.get("ele_gpx_m"))
    if ele_gpx is not None:
        return ele_gpx, "ele_gpx_m"

    elev_min = parse_float(row.get("elev_min_nlsc_window"))
    elev_max = parse_float(row.get("elev_max_nlsc_window"))
    if elev_min is not None and elev_max is not None:
        return (elev_min + elev_max) / 2.0, "nlsc_window_mid"

    return None, "missing"


def build_route_points(route_rows: List[Dict[str, str]]) -> List[Dict[str, object]]:
    points: List[Dict[str, object]] = []
    for row in route_rows:
        lat = parse_float(row.get("lat"))
        lon = parse_float(row.get("lon"))
        if lat is None or lon is None:
            continue

        dist_m = parse_float(row.get("dist_m"))
        if dist_m is None:
            dist_m = parse_float(row.get("profile_dist_m"))

        route_ele, route_ele_source = route_elevation_from_row(row)

        elev_min = parse_float(row.get("elev_min_nlsc_window"))
        elev_max = parse_float(row.get("elev_max_nlsc_window"))
        elev_range = parse_float(row.get("elev_range_nlsc_window"))

        points.append(
            {
                "case_id": row.get("case_id", ""),
                "case_name": row.get("case_name", ""),
                "sample_idx": row.get("sample_idx", ""),
                "lat": lat,
                "lon": lon,
                "dist_m": dist_m,
                "route_elevation_m": route_ele,
                "route_elevation_source": route_ele_source,
                "elev_min_nlsc_window": elev_min,
                "elev_max_nlsc_window": elev_max,
                "elev_range_nlsc_window": elev_range,
                "terrain_elevation_source": row.get("terrain_elevation_source", ""),
                "contour_window_match_status": row.get("contour_window_match_status", ""),
                "osm_way_name": row.get("osm_way_name", ""),
                "osm_highway": row.get("osm_highway", ""),
                "surface_class": row.get("surface_class", ""),
                "route_semantic_class": row.get("route_semantic_class", ""),
                "weather_sensitive_flags": row.get("weather_sensitive_flags", ""),
                "hydrology_flags": row.get("hydrology_flags", ""),
            }
        )

    if not points:
        raise ValueError("No valid route points with lat/lon were found.")

    return points


def nearest_route_point(station_lat: float, station_lon: float, route_points: List[Dict[str, object]]) -> Tuple[float, Dict[str, object]]:
    best_dist = float("inf")
    best_point: Optional[Dict[str, object]] = None

    for point in route_points:
        d = haversine_m(station_lat, station_lon, float(point["lat"]), float(point["lon"]))
        if d < best_dist:
            best_dist = d
            best_point = point

    if best_point is None:
        raise ValueError("No nearest route point could be computed.")

    return best_dist, best_point


def station_elevation(row: Dict[str, str]) -> Tuple[Optional[float], str, str]:
    terrain_ele = parse_float(row.get("terrain_lookup_elevation_m"))
    if terrain_ele is not None:
        return terrain_ele, "terrain_lookup_elevation_m", "AVAILABLE"

    db_ele = parse_float(row.get("db_elevation_m"))
    if db_ele is not None:
        return db_ele, "db_elevation_m", "AVAILABLE"

    return None, row.get("elevation_source", "missing") or "missing", "MISSING"


def build_candidates(
    station_rows: List[Dict[str, str]],
    route_points: List[Dict[str, object]],
    route_id: str,
    max_distance_m: Optional[float],
) -> List[Dict[str, object]]:
    candidates: List[Dict[str, object]] = []

    for station in station_rows:
        st_lat = parse_float(station.get("latitude"))
        st_lon = parse_float(station.get("longitude"))
        if st_lat is None or st_lon is None:
            continue

        dist_to_route_m, point = nearest_route_point(st_lat, st_lon, route_points)

        if max_distance_m is not None and dist_to_route_m > max_distance_m:
            # Keep out-of-buffer records as excluded? For v1, exclude from output to keep QA compact.
            continue

        st_ele, st_ele_source, st_ele_status = station_elevation(station)
        route_ele = point.get("route_elevation_m")
        elevation_delta_m: Optional[float] = None
        if st_ele is not None and route_ele is not None:
            elevation_delta_m = abs(float(st_ele) - float(route_ele))

        nearest_route_km: Optional[float] = None
        if point.get("dist_m") is not None:
            nearest_route_km = float(point["dist_m"]) / 1000.0

        candidates.append(
            {
                "route_id": route_id,
                "route_case_id": point.get("case_id", ""),
                "route_case_name": point.get("case_name", ""),
                "source": station.get("source", ""),
                "station_type": station.get("station_type", ""),
                "dataset_code": station.get("dataset_code", ""),
                "station_id": station.get("station_id", ""),
                "station_name": station.get("station_name", ""),
                "station_latitude": st_lat,
                "station_longitude": st_lon,
                "station_elevation_m": st_ele,
                "station_elevation_source": st_ele_source,
                "station_elevation_status": st_ele_status,
                "distance_to_route_m": dist_to_route_m,
                "nearest_route_km": nearest_route_km,
                "nearest_route_sample_idx": point.get("sample_idx", ""),
                "nearest_route_latitude": point.get("lat"),
                "nearest_route_longitude": point.get("lon"),
                "route_nearest_elevation_m": route_ele,
                "route_nearest_elevation_source": point.get("route_elevation_source", ""),
                "elevation_delta_m": elevation_delta_m,
                "elevation_delta_status": "AVAILABLE" if elevation_delta_m is not None else "STATION_ELEVATION_MISSING",
                "terrain_elevation_source": point.get("terrain_elevation_source", ""),
                "contour_window_match_status": point.get("contour_window_match_status", ""),
                "elev_min_nlsc_window": point.get("elev_min_nlsc_window"),
                "elev_max_nlsc_window": point.get("elev_max_nlsc_window"),
                "elev_range_nlsc_window": point.get("elev_range_nlsc_window"),
                "osm_way_name": point.get("osm_way_name", ""),
                "osm_highway": point.get("osm_highway", ""),
                "surface_class": point.get("surface_class", ""),
                "route_semantic_class": point.get("route_semantic_class", ""),
                "weather_sensitive_flags": point.get("weather_sensitive_flags", ""),
                "hydrology_flags": point.get("hydrology_flags", ""),
                "elevation_lookup_status": station.get("elevation_lookup_status", ""),
                "needs_terrain_lookup": station.get("needs_terrain_lookup", ""),
                "metadata_source_table": station.get("metadata_source_table", ""),
                "metadata_status": station.get("metadata_status", ""),
                "selection_scope": "route_scoped",
                "fusion_scope": "not_fused_v1",
            }
        )

    candidates.sort(
        key=lambda r: (
            str(r.get("station_type", "")),
            float(r.get("distance_to_route_m") or 1e18),
            str(r.get("station_id", "")),
            str(r.get("metadata_source_table", "")),
        )
    )

    by_type_rank: Dict[str, int] = {}
    for row in candidates:
        station_type = str(row.get("station_type", "unknown"))
        by_type_rank[station_type] = by_type_rank.get(station_type, 0) + 1
        rank = by_type_rank[station_type]
        row["candidate_rank"] = rank
        row["candidate_role"] = candidate_role(rank)

    return candidates


def summarize(candidates: List[Dict[str, object]], route_id: str, max_distance_m: Optional[float]) -> List[Dict[str, object]]:
    groups: Dict[Tuple[str, str], Dict[str, object]] = {}
    for row in candidates:
        station_type = str(row.get("station_type", "unknown"))
        role = str(row.get("candidate_role", "unknown"))
        key = (station_type, role)
        g = groups.setdefault(
            key,
            {
                "route_id": route_id,
                "station_type": station_type,
                "candidate_role": role,
                "candidate_count": 0,
                "min_distance_to_route_m": None,
                "max_distance_to_route_m": None,
                "max_distance_filter_m": max_distance_m if max_distance_m is not None else "",
                "selection_scope": "route_scoped",
                "fusion_scope": "not_fused_v1",
            },
        )
        d = float(row.get("distance_to_route_m") or 0.0)
        g["candidate_count"] = int(g["candidate_count"]) + 1
        if g["min_distance_to_route_m"] is None or d < float(g["min_distance_to_route_m"]):
            g["min_distance_to_route_m"] = d
        if g["max_distance_to_route_m"] is None or d > float(g["max_distance_to_route_m"]):
            g["max_distance_to_route_m"] = d

    return sorted(groups.values(), key=lambda r: (str(r["station_type"]), str(r["candidate_role"])))


def write_html(path: Path, title: str, summary_rows: List[Dict[str, object]], top_weather: List[Dict[str, object]], top_water: List[Dict[str, object]]) -> None:
    def table(rows: List[Dict[str, object]], cols: List[str]) -> str:
        head = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
        body_parts = []
        for row in rows:
            tds = "".join(html.escape("" if row.get(c) is None else str(row.get(c))) for c in cols)
            # fix td wrapping
            tds = "".join(f"<td>{html.escape('' if row.get(c) is None else str(row.get(c)))}</td>" for c in cols)
            body_parts.append(f"<tr>{tds}</tr>")
        return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body_parts)}</tbody></table>"

    summary_cols = ["route_id", "station_type", "candidate_role", "candidate_count", "min_distance_to_route_m", "max_distance_to_route_m"]
    candidate_cols = [
        "candidate_rank",
        "candidate_role",
        "station_id",
        "station_name",
        "source",
        "distance_to_route_m",
        "nearest_route_km",
        "route_nearest_elevation_m",
        "station_elevation_status",
        "elevation_delta_status",
        "metadata_source_table",
    ]

    doc = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; }}
table {{ border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 13px; }}
th, td {{ border: 1px solid #ddd; padding: 6px 8px; vertical-align: top; }}
th {{ background: #f4f4f4; text-align: left; }}
code {{ background: #f4f4f4; padding: 2px 4px; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<p>IB3W route-scoped station candidate selection v1. This is not weather/hydro fusion.</p>
<h2>Summary</h2>
{table(summary_rows, summary_cols)}
<h2>Top weather candidates</h2>
{table(top_weather, candidate_cols)}
<h2>Top water candidates</h2>
{table(top_water, candidate_cols)}
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Select route-scoped IB3W station candidates.")
    parser.add_argument("--station-registry-csv", required=True, help="IB3W station metadata/elevation registry CSV.")
    parser.add_argument("--route-profile-csv", required=True, help="IB1E route profile enriched CSV.")
    parser.add_argument("--route-id", required=True, help="Route id for output naming.")
    parser.add_argument("--out-dir", required=True, help="Output directory.")
    parser.add_argument("--max-distance-m", type=float, default=None, help="Optional max distance filter from station to route.")
    args = parser.parse_args()

    station_csv = Path(args.station_registry_csv)
    route_csv = Path(args.route_profile_csv)
    out_dir = Path(args.out_dir)

    station_rows = load_csv_rows(station_csv)
    route_rows = load_csv_rows(route_csv)
    route_points = build_route_points(route_rows)

    candidates = build_candidates(
        station_rows=station_rows,
        route_points=route_points,
        route_id=args.route_id,
        max_distance_m=args.max_distance_m,
    )

    fieldnames = [
        "route_id",
        "route_case_id",
        "route_case_name",
        "source",
        "station_type",
        "dataset_code",
        "station_id",
        "station_name",
        "station_latitude",
        "station_longitude",
        "station_elevation_m",
        "station_elevation_source",
        "station_elevation_status",
        "distance_to_route_m",
        "nearest_route_km",
        "nearest_route_sample_idx",
        "nearest_route_latitude",
        "nearest_route_longitude",
        "route_nearest_elevation_m",
        "route_nearest_elevation_source",
        "elevation_delta_m",
        "elevation_delta_status",
        "terrain_elevation_source",
        "contour_window_match_status",
        "elev_min_nlsc_window",
        "elev_max_nlsc_window",
        "elev_range_nlsc_window",
        "osm_way_name",
        "osm_highway",
        "surface_class",
        "route_semantic_class",
        "weather_sensitive_flags",
        "hydrology_flags",
        "elevation_lookup_status",
        "needs_terrain_lookup",
        "metadata_source_table",
        "metadata_status",
        "selection_scope",
        "fusion_scope",
        "candidate_rank",
        "candidate_role",
    ]

    weather = [r for r in candidates if str(r.get("station_type")) == "weather"]
    water = [r for r in candidates if str(r.get("station_type")) == "water"]
    summary_rows = summarize(candidates, args.route_id, args.max_distance_m)

    route_dir = out_dir / args.route_id
    write_csv(route_dir / "weather_station_candidates.csv", weather, fieldnames)
    write_csv(route_dir / "water_station_candidates.csv", water, fieldnames)
    write_csv(route_dir / "route_station_candidates_all.csv", candidates, fieldnames)

    summary_fields = [
        "route_id",
        "station_type",
        "candidate_role",
        "candidate_count",
        "min_distance_to_route_m",
        "max_distance_to_route_m",
        "max_distance_filter_m",
        "selection_scope",
        "fusion_scope",
    ]
    write_csv(route_dir / "route_station_candidate_summary.csv", summary_rows, summary_fields)

    write_html(
        route_dir / "route_station_candidate_summary.html",
        f"IB3W route-scoped station candidates: {args.route_id}",
        summary_rows,
        weather[:20],
        water[:20],
    )

    print("IB3W route-scoped station candidates written")
    print(f"route_id: {args.route_id}")
    print(f"route_points: {len(route_points)}")
    print(f"station_rows: {len(station_rows)}")
    print(f"candidate_rows: {len(candidates)}")
    print(f"weather_candidates: {len(weather)}")
    print(f"water_candidates: {len(water)}")
    print(f"out_dir: {route_dir}")


if __name__ == "__main__":
    main()
