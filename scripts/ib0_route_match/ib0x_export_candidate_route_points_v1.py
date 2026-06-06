"""Export IB0 route-match candidate ways as an IB3A-RC candidate route pool.

This adapter preserves each candidate LineString as an independent route.
It does not assemble ways, refit activities, classify route choice, or modify
IB0 formal outputs.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any


SOURCE_STAGE = "IB0_ROUTE_MATCH_ACTIVITY_OSM_CANDIDATES"
CONTRACT_VERSION = "ib0_candidate_route_pool_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--route-folder", required=True)
    parser.add_argument("--candidate-geojson", required=True)
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def require_file(path: Path, label: str) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    return path


def to_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def to_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_m = 6_371_008.8
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * radius_m * math.asin(min(1.0, math.sqrt(a)))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float | None:
    if lat1 == lat2 and lon1 == lon2:
        return None
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    y = math.sin(dlambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def angular_change_deg(previous: float | None, current: float | None) -> float | None:
    if previous is None or current is None:
        return None
    return abs((current - previous + 180.0) % 360.0 - 180.0)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_candidates(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    require_file(path, "IB0 candidate GeoJSON")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if data.get("type") != "FeatureCollection":
        raise ValueError(f"Expected FeatureCollection: {path}")
    features = data.get("features")
    if not isinstance(features, list):
        raise ValueError(f"FeatureCollection missing features list: {path}")
    return data, features


def make_candidate_way_id(osm_way_id: Any, feature_index: int) -> str:
    value = str(osm_way_id).strip()
    return f"way_{value}" if value else f"feature_{feature_index:04d}"


def export_pool(args: argparse.Namespace) -> dict[str, Any]:
    source_path = Path(args.candidate_geojson)
    source_text = str(source_path)
    source_data, features = load_candidates(source_path)
    out_root = Path(args.out_dir)
    route_dir = out_root / args.route_folder
    summary_dir = out_root / "_candidate_summary"

    way_csv = route_dir / "candidate_way_pool.csv"
    way_geojson = route_dir / "candidate_way_pool.geojson"
    points_csv = route_dir / "candidate_route_points.csv"
    summary_csv = summary_dir / f"{args.route_folder}_candidate_route_pool_summary.csv"
    contract_json = summary_dir / f"{args.route_folder}_candidate_route_pool_contract.json"

    way_rows: list[dict[str, Any]] = []
    point_rows: list[dict[str, Any]] = []
    output_features: list[dict[str, Any]] = []
    geometry_types: Counter[str] = Counter()
    route_role_selected: Counter[str] = Counter()
    highway_selected: Counter[str] = Counter()
    empty_coordinates_n = 0
    unsupported_geometry_n = 0

    for feature_index, feature in enumerate(features):
        properties = dict(feature.get("properties") or {})
        geometry = feature.get("geometry") or {}
        geometry_type = str(geometry.get("type") or "missing")
        coordinates = geometry.get("coordinates") or []
        geometry_types[geometry_type] += 1
        if not coordinates:
            empty_coordinates_n += 1

        osm_way_id = properties.get("osm_way_id", properties.get("osm_id", ""))
        candidate_way_id = make_candidate_way_id(osm_way_id, feature_index)
        selected = to_bool(properties.get("selected"))
        coordinates_count = len(coordinates) if isinstance(coordinates, list) else 0

        way_row = {
            "case_id": args.case_id,
            "route_folder": args.route_folder,
            "candidate_way_id": candidate_way_id,
            "osm_way_id": osm_way_id,
            "name": properties.get("name", ""),
            "highway": properties.get("highway", ""),
            "highway_norm": properties.get("highway_norm", ""),
            "route_role": properties.get("route_role", ""),
            "segment_len_m": properties.get("segment_len_m", ""),
            "distance_to_gpx_m": properties.get(
                "distance_to_gpx_m",
                properties.get("distance_to_activity_m", ""),
            ),
            "overlap_len_m": properties.get("overlap_len_m", ""),
            "overlap_ratio": properties.get("overlap_ratio", ""),
            "semantic_score": properties.get("semantic_score", ""),
            "distance_score": properties.get("distance_score", ""),
            "match_score": properties.get("match_score", ""),
            "selected": selected,
            "geometry_type": geometry_type,
            "coordinates_count": coordinates_count,
            "source_geojson": source_text,
            "source_stage": SOURCE_STAGE,
        }
        way_rows.append(way_row)

        output_properties = dict(properties)
        output_properties.update(
            {
                "candidate_way_id": candidate_way_id,
                "candidate_route_id": candidate_way_id,
                "route_folder": args.route_folder,
                "source_geojson": source_text,
                "source_stage": SOURCE_STAGE,
            }
        )
        output_features.append(
            {
                "type": "Feature",
                "properties": output_properties,
                "geometry": geometry,
            }
        )

        if selected:
            route_role_selected[str(properties.get("route_role") or "")] += 1
            highway_selected[str(properties.get("highway_norm") or "")] += 1

        if geometry_type != "LineString":
            unsupported_geometry_n += 1
            continue
        if not isinstance(coordinates, list) or not coordinates:
            continue

        parsed_coordinates: list[tuple[float, float] | None] = []
        for coordinate in coordinates:
            if not isinstance(coordinate, (list, tuple)) or len(coordinate) < 2:
                parsed_coordinates.append(None)
                continue
            lon = to_float(coordinate[0])
            lat = to_float(coordinate[1])
            parsed_coordinates.append((lat, lon) if lat is not None and lon is not None else None)

        cumulative_m = 0.0
        previous_bearing: float | None = None
        for point_index, coordinate in enumerate(parsed_coordinates):
            if coordinate is None:
                continue
            lat, lon = coordinate
            segment_len_m = 0.0
            bearing = None
            if point_index > 0 and parsed_coordinates[point_index - 1] is not None:
                prev_lat, prev_lon = parsed_coordinates[point_index - 1]
                segment_len_m = haversine_m(prev_lat, prev_lon, lat, lon)
                bearing = bearing_deg(prev_lat, prev_lon, lat, lon)
                cumulative_m += segment_len_m
            point_rows.append(
                {
                    "case_id": args.case_id,
                    "route_folder": args.route_folder,
                    "candidate_route_id": candidate_way_id,
                    "candidate_way_id": candidate_way_id,
                    "osm_way_id": osm_way_id,
                    "route_point_index": point_index,
                    "route_dist_m": cumulative_m,
                    "lat": lat,
                    "lon": lon,
                    "segment_len_m": segment_len_m,
                    "bearing_deg": bearing,
                    "bearing_change_deg": angular_change_deg(previous_bearing, bearing),
                    "name": properties.get("name", ""),
                    "highway": properties.get("highway", ""),
                    "highway_norm": properties.get("highway_norm", ""),
                    "route_role": properties.get("route_role", ""),
                    "match_score": properties.get("match_score", ""),
                    "selected": selected,
                    "source_geojson": source_text,
                    "source_stage": SOURCE_STAGE,
                }
            )
            if bearing is not None:
                previous_bearing = bearing

    way_fields = [
        "case_id",
        "route_folder",
        "candidate_way_id",
        "osm_way_id",
        "name",
        "highway",
        "highway_norm",
        "route_role",
        "segment_len_m",
        "distance_to_gpx_m",
        "overlap_len_m",
        "overlap_ratio",
        "semantic_score",
        "distance_score",
        "match_score",
        "selected",
        "geometry_type",
        "coordinates_count",
        "source_geojson",
        "source_stage",
    ]
    point_fields = [
        "case_id",
        "route_folder",
        "candidate_route_id",
        "candidate_way_id",
        "osm_way_id",
        "route_point_index",
        "route_dist_m",
        "lat",
        "lon",
        "segment_len_m",
        "bearing_deg",
        "bearing_change_deg",
        "name",
        "highway",
        "highway_norm",
        "route_role",
        "match_score",
        "selected",
        "source_geojson",
        "source_stage",
    ]
    write_csv(way_csv, way_rows, way_fields)
    write_csv(points_csv, point_rows, point_fields)
    way_geojson.parent.mkdir(parents=True, exist_ok=True)
    way_geojson.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "name": f"{args.route_folder}_candidate_way_pool",
                "source": source_data.get("name", source_text),
                "features": output_features,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    selected_rows = [row for row in way_rows if row["selected"]]
    top_selected = sorted(
        selected_rows,
        key=lambda row: (
            -(to_float(row.get("match_score")) or float("-inf")),
            str(row.get("osm_way_id", "")),
        ),
    )[:10]
    summary_row = {
        "case_id": args.case_id,
        "route_folder": args.route_folder,
        "contract_version": CONTRACT_VERSION,
        "total_candidate_ways": len(way_rows),
        "selected_candidate_ways": len(selected_rows),
        "candidate_route_points_rows": len(point_rows),
        "non_linestring_geometry_n": unsupported_geometry_n,
        "empty_coordinates_n": empty_coordinates_n,
        "geometry_type_counts": json.dumps(dict(geometry_types), ensure_ascii=False, sort_keys=True),
        "selected_route_role_counts": json.dumps(dict(route_role_selected), ensure_ascii=False, sort_keys=True),
        "selected_highway_norm_counts": json.dumps(dict(highway_selected), ensure_ascii=False, sort_keys=True),
        "top_10_selected_osm_way_ids_by_match_score": json.dumps(
            [
                {
                    "osm_way_id": row["osm_way_id"],
                    "match_score": row["match_score"],
                }
                for row in top_selected
            ],
            ensure_ascii=False,
        ),
        "candidate_way_pool_csv": str(way_csv),
        "candidate_way_pool_geojson": str(way_geojson),
        "candidate_route_points_csv": str(points_csv),
        "source_geojson": source_text,
        "source_stage": SOURCE_STAGE,
    }
    write_csv(summary_csv, [summary_row], list(summary_row.keys()))

    contract = {
        "contract_version": CONTRACT_VERSION,
        "adapter_script": "scripts/ib0_route_match/ib0x_export_candidate_route_points_v1.py",
        "case_id": args.case_id,
        "route_folder": args.route_folder,
        "input": {
            "candidate_geojson": source_text,
            "required_collection_type": "FeatureCollection",
            "supported_geometry_type": "LineString",
            "coordinate_order": "[lon, lat]",
        },
        "output_root": str(out_root),
        "outputs": {
            "candidate_way_pool_csv": str(way_csv),
            "candidate_way_pool_geojson": str(way_geojson),
            "candidate_route_points_csv": str(points_csv),
            "candidate_route_pool_summary_csv": str(summary_csv),
            "candidate_route_pool_contract_json": str(contract_json),
        },
        "identifiers": {
            "candidate_way_id": "way_<osm_way_id>; feature_<index> fallback",
            "candidate_route_id": "equal to candidate_way_id in v1",
        },
        "calculations": {
            "segment_len_m": "haversine distance from previous coordinate within each LineString",
            "route_dist_m": "cumulative distance within each independent candidate way",
            "bearing_deg": "bearing from previous coordinate to current coordinate",
            "bearing_change_deg": "absolute wrapped difference between consecutive bearings",
        },
        "boundaries": [
            "Does not modify IA1.",
            "Does not modify IB0 formal outputs.",
            "Does not modify IB0B or IB0D.",
            "Does not assemble multiple ways into a complete route.",
            "Does not refit IB3 activities.",
            "Does not classify route choice.",
        ],
        "summary": summary_row,
        "runtime_llm_allowed": False,
    }
    contract_json.parent.mkdir(parents=True, exist_ok=True)
    contract_json.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    return contract


def main() -> int:
    args = parse_args()
    contract = export_pool(args)
    summary = contract["summary"]
    print(f"total_candidate_ways={summary['total_candidate_ways']}")
    print(f"selected_candidate_ways={summary['selected_candidate_ways']}")
    print(f"candidate_route_points_rows={summary['candidate_route_points_rows']}")
    print(f"selected_route_role_counts={summary['selected_route_role_counts']}")
    print(f"selected_highway_norm_counts={summary['selected_highway_norm_counts']}")
    print(f"top_10_selected_osm_way_ids_by_match_score={summary['top_10_selected_osm_way_ids_by_match_score']}")
    print(f"non_linestring_geometry_n={summary['non_linestring_geometry_n']}")
    print(f"empty_coordinates_n={summary['empty_coordinates_n']}")
    for name, path in contract["outputs"].items():
        print(f"{name}={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
