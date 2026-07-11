# -*- coding: utf-8 -*-
"""THCI support axis access-exit destination and spacing audit v1.2.4.

Audit/candidate outputs only. This script does not modify official THCI
scoring scripts, risk semantics config, or score outputs.
"""

from __future__ import annotations

import csv
import json
import math
import os
import py_compile
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

try:
    from pyproj import Transformer
    from shapely.geometry import LineString, Point, mapping, shape
    from shapely.ops import transform
except ModuleNotFoundError:
    venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
        os.execv(str(venv_python), [str(venv_python), __file__, *sys.argv[1:]])
    raise


ROUTES = [
    "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b",
    "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b",
    "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b",
    "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b",
]

IB0D_ROOT = PROJECT_ROOT / "outputs" / "ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa"
IB1C_ROOT = PROJECT_ROOT / "outputs" / "ib1c_route_profile_semantics_v1_3b_contract_qa"
V123_ROOT = PROJECT_ROOT / "outputs" / "thci_support_access_exit_connectivity_v1_2_3_prototype"
V122_ROOT = PROJECT_ROOT / "outputs" / "thci_support_vehicle_access_proxy_v1_2_2_prototype"
OUT_DIR = PROJECT_ROOT / "outputs" / "thci_support_access_exit_destination_spacing_v1_2_4_audit"

DETAIL_CSV = OUT_DIR / "four_route_access_exit_destination_spacing_v1_2_4.csv"
SUMMARY_CSV = OUT_DIR / "four_route_access_exit_spacing_summary_v1_2_4.csv"
SUMMARY_MD = OUT_DIR / "four_route_access_exit_destination_spacing_v1_2_4_summary.md"

ENDPOINT_WINDOW_M = 250.0
SELF_NEAR_SPATIAL_M = 30.0
SELF_NEAR_ROUTE_GAP_M = 500.0
ROUTE_SAMPLE_STEP_M = 25.0

PUBLIC_ROAD_HIGHWAYS = {
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "unclassified",
    "residential",
    "living_street",
    "road",
}
SERVICE_TRACK_HIGHWAYS = {"service", "track"}
RESTRICTED_ACCESS = {"no", "private", "permit", "customers", "delivery", "destination"}


TO_M = Transformer.from_crs("EPSG:4326", "EPSG:3826", always_xy=True)
TO_WGS = Transformer.from_crs("EPSG:3826", "EPSG:4326", always_xy=True)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def norm(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text in {"", "<NA>", "nan", "None", "null"}:
        return ""
    return text.lower()


def clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text in {"", "<NA>", "nan", "None", "null"}:
        return ""
    return text


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(out):
        return default
    return out


def route_case_dir(case_id: str) -> Path:
    return IB0D_ROOT / case_id


def route_line_path(case_id: str) -> Path:
    case_dir = route_case_dir(case_id)
    candidates = [
        case_dir / f"{case_id}_trimmed_mainline.geojson",
        case_dir / f"{case_id}_mainline_ordered_path_trimmed.geojson",
        case_dir / "mainline_ordered_path_trimmed.geojson",
    ]
    for path in candidates:
        if path.exists():
            return path
    matches = sorted(case_dir.glob("*mainline*.geojson")) or sorted(case_dir.glob("*.geojson"))
    if not matches:
        raise FileNotFoundError(f"No mainline GeoJSON found for {case_id}")
    return matches[0]


def route_points_path(case_id: str) -> Path:
    case_dir = route_case_dir(case_id)
    candidates = [case_dir / "route_points.csv", case_dir / f"{case_id}_mainline_ordered_path_trimmed_route_points.csv"]
    for path in candidates:
        if path.exists():
            return path
    matches = sorted(case_dir.glob("*route_points.csv"))
    if not matches:
        raise FileNotFoundError(f"No route_points.csv found for {case_id}")
    return matches[0]


def trim_summary_path(case_id: str) -> Path:
    case_dir = route_case_dir(case_id)
    candidates = [case_dir / "trim_summary.csv", case_dir / f"{case_id}_mainline_trim_summary.csv"]
    for path in candidates:
        if path.exists():
            return path
    matches = sorted(case_dir.glob("*trim_summary.csv"))
    if not matches:
        raise FileNotFoundError(f"No trim_summary.csv found for {case_id}")
    return matches[0]


def load_route_points(case_id: str) -> list[dict[str, Any]]:
    path = route_points_path(case_id)
    points = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            lon = safe_float(row.get("lon"), math.nan)
            lat = safe_float(row.get("lat"), math.nan)
            dist = safe_float(row.get("route_dist_m", row.get("dist_m")), math.nan)
            if math.isfinite(lon) and math.isfinite(lat) and math.isfinite(dist):
                x, y = TO_M.transform(lon, lat)
                points.append({"route_position_m": dist, "lon": lon, "lat": lat, "point_m": Point(x, y)})
    if not points:
        raise ValueError(f"No usable route points for {case_id}")
    return points


def load_route_line_m(case_id: str, route_points: list[dict[str, Any]]) -> LineString:
    coords = [(item["point_m"].x, item["point_m"].y) for item in route_points]
    if len(coords) >= 2:
        return LineString(coords)

    data = read_json(route_line_path(case_id))
    geoms = []
    if data.get("type") == "FeatureCollection":
        for feature in data.get("features", []):
            if feature.get("geometry"):
                geoms.append(shape(feature["geometry"]))
    elif data.get("type") == "Feature":
        geoms.append(shape(data["geometry"]))
    else:
        geoms.append(shape(data))
    if not geoms:
        raise ValueError(f"No route geometry found for {case_id}")
    geom = geoms[0]
    if geom.geom_type == "MultiLineString":
        coords = []
        for part in geom.geoms:
            coords.extend(list(part.coords))
        geom = LineString(coords)
    return transform(TO_M.transform, geom)


def load_trim_summary(case_id: str) -> dict[str, str]:
    with trim_summary_path(case_id).open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return rows[0] if rows else {}


def access_nodes_path(case_id: str) -> Path:
    return V123_ROOT / case_id / f"{case_id}_access_exit_nodes_v1_2_3.geojson"


def load_v123_nodes(case_id: str) -> list[dict[str, Any]]:
    data = read_json(access_nodes_path(case_id))
    nodes = []
    for feature in data.get("features", []):
        props = dict(feature.get("properties") or {})
        props["geometry"] = feature.get("geometry")
        nodes.append(props)
    return nodes


def load_v122_clusters(case_id: str) -> dict[str, dict[str, Any]]:
    path = V122_ROOT / case_id / f"{case_id}_vehicle_access_points_v1_2_2.geojson"
    if not path.exists():
        return {}
    data = read_json(path)
    out = {}
    for feature in data.get("features", []):
        props = dict(feature.get("properties") or {})
        out[str(props.get("cluster_id", ""))] = props
    return out


def load_ib1c_rows(case_id: str) -> list[dict[str, Any]]:
    path = IB1C_ROOT / case_id / f"{case_id}_route_profile_semantic_enriched.csv"
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append(row)
    return rows


def nearest_ib1c_row(rows: list[dict[str, Any]], route_position_m: float) -> dict[str, Any]:
    if not rows:
        return {}
    return min(rows, key=lambda row: abs(safe_float(row.get("dist_m"), 0.0) - route_position_m))


def raw_feature_from_source(props: dict[str, Any]) -> dict[str, Any]:
    source_file = clean(props.get("source_file"))
    source_index = props.get("source_feature_index")
    if not source_file or source_index in {None, ""}:
        return {}
    path = Path(source_file)
    if not path.exists():
        path = PROJECT_ROOT / source_file
    if not path.exists():
        return {}
    try:
        data = read_json(path)
        feature = data.get("features", [])[int(float(source_index))]
    except (ValueError, IndexError, KeyError, TypeError):
        return {}
    raw_props = dict(feature.get("properties") or {})
    raw_props["_geometry"] = feature.get("geometry")
    return raw_props


def node_point_wgs(props: dict[str, Any]) -> Point | None:
    geom = props.get("geometry")
    if geom:
        try:
            point = shape(geom)
            if point.geom_type == "Point":
                return point
        except Exception:
            pass
    lon = safe_float(props.get("access_point_lon"), math.nan)
    lat = safe_float(props.get("access_point_lat"), math.nan)
    if math.isfinite(lon) and math.isfinite(lat):
        return Point(lon, lat)
    return None


def nearest_route_position(
    props: dict[str, Any],
    route_points: list[dict[str, Any]],
    route_line_m: LineString,
) -> tuple[float, float, Point]:
    old_route_m = safe_float(props.get("nearest_route_km"), math.nan) * 1000.0
    route_lon = safe_float(props.get("nearest_route_point_lon"), math.nan)
    route_lat = safe_float(props.get("nearest_route_point_lat"), math.nan)
    if math.isfinite(route_lon) and math.isfinite(route_lat):
        rx, ry = TO_M.transform(route_lon, route_lat)
        ref = Point(rx, ry)
        best_gap = min(item["point_m"].distance(ref) for item in route_points)
        close_candidates = [
            item for item in route_points if item["point_m"].distance(ref) <= max(best_gap + 1.0, 30.0)
        ]
        if math.isfinite(old_route_m):
            nearest = min(close_candidates, key=lambda item: abs(item["route_position_m"] - old_route_m))
        else:
            nearest = min(close_candidates, key=lambda item: item["point_m"].distance(ref))
        return nearest["route_position_m"], nearest["point_m"].distance(ref), nearest["point_m"]

    point_wgs = node_point_wgs(props)
    if point_wgs is not None:
        point_m = transform(TO_M.transform, point_wgs)
        pos = route_line_m.project(point_m)
        snapped = route_line_m.interpolate(pos)
        return pos, snapped.distance(point_m), snapped

    return 0.0, math.inf, route_line_m.interpolate(0.0)


def destination_label(highway: str, amenity: str, way_name: str, route_case: str) -> str:
    highway_n = norm(highway)
    amenity_n = norm(amenity)
    name_n = norm(way_name)
    case_n = norm(route_case)
    if amenity_n in {"parking", "parking_space"}:
        return "connects_to_parking"
    if "campus" in name_n or "university" in name_n or "campus" in case_n or "zhonghua_ust" in case_n:
        if highway_n in PUBLIC_ROAD_HIGHWAYS | SERVICE_TRACK_HIGHWAYS:
            return "connects_to_campus_road"
    if highway_n in SERVICE_TRACK_HIGHWAYS:
        return "connects_to_service_track"
    if highway_n in PUBLIC_ROAD_HIGHWAYS and way_name:
        return "connects_to_named_road"
    if highway_n in PUBLIC_ROAD_HIGHWAYS:
        return "connects_to_named_road"
    return "unknown_destination"

def node_role(
    route_position_m: float,
    route_len_m: float,
    highway: str,
    amenity: str,
    ib1c: dict[str, Any],
    reason: str,
) -> str:
    endpoint_gap = min(route_position_m, max(route_len_m - route_position_m, 0.0))
    highway_n = norm(highway)
    amenity_n = norm(amenity)
    if endpoint_gap <= ENDPOINT_WINDOW_M or "route_endpoint" in norm(reason):
        return "route_endpoint"
    if amenity_n == "parking":
        return "parking_access"
    if clean(ib1c.get("near_trailhead")) == "1" or "trailhead" in norm(reason):
        return "trailhead"
    if highway_n in SERVICE_TRACK_HIGHWAYS:
        return "service_track_access"
    if highway_n in PUBLIC_ROAD_HIGHWAYS:
        return "road_crossing"
    return "review_only"


def review_flag(
    destination: str,
    highway: str,
    access: str,
    motor_vehicle: str,
    vehicle: str,
    confidence: float,
    distance_to_route_m: float,
) -> str:
    access_values = {norm(access), norm(motor_vehicle), norm(vehicle)}
    if access_values & RESTRICTED_ACCESS:
        return "possible_private_or_restricted"
    if destination == "unknown_destination":
        return "destination_unknown"
    if confidence < 0.75 or distance_to_route_m > 75.0 or norm(highway) in SERVICE_TRACK_HIGHWAYS:
        return "spatial_only_not_graph_connected"
    return "destination_confirmed"


def spacing_metrics(route_len_m: float, positions: list[float]) -> dict[str, Any]:
    positions = sorted(max(0.0, min(route_len_m, pos)) for pos in positions)
    gaps = [positions[i + 1] - positions[i] for i in range(len(positions) - 1)]

    if not positions:
        return {
            "connected_exit_count": 0,
            "exit_positions_m": [],
            "exit_gap_along_route_m": [],
            "max_exit_gap_along_route_m": route_len_m,
            "mean_exit_gap_along_route_m": "",
            "max_distance_to_nearest_exit_along_route_m": route_len_m,
            "route_fraction_farther_than_500m_from_exit": 1.0 if route_len_m > 500 else max(0.0, (route_len_m - 500.0) / route_len_m),
            "route_fraction_farther_than_1000m_from_exit": 1.0 if route_len_m > 1000 else max(0.0, (route_len_m - 1000.0) / route_len_m),
            "route_fraction_farther_than_1500m_from_exit": 1.0 if route_len_m > 1500 else max(0.0, (route_len_m - 1500.0) / route_len_m),
            "longest_no_exit_segment_start_m": 0.0,
            "longest_no_exit_segment_end_m": route_len_m,
            "longest_no_exit_segment_length_m": route_len_m,
        }

    segments = []
    segments.append((0.0, positions[0], positions[0], "edge"))
    for a, b in zip(positions, positions[1:]):
        segments.append((a, b, b - a, "internal"))
    segments.append((positions[-1], route_len_m, route_len_m - positions[-1], "edge"))
    longest = max(segments, key=lambda item: item[2])

    def far_fraction(threshold: float) -> float:
        if route_len_m <= 0:
            return 0.0
        far_len = 0.0
        far_len += max(0.0, positions[0] - threshold)
        far_len += max(0.0, route_len_m - positions[-1] - threshold)
        for a, b in zip(positions, positions[1:]):
            far_len += max(0.0, (b - a) - 2.0 * threshold)
        return max(0.0, min(1.0, far_len / route_len_m))

    max_nearest = max(
        [positions[0], route_len_m - positions[-1], *[(b - a) / 2.0 for a, b in zip(positions, positions[1:])]]
    )
    return {
        "connected_exit_count": len(positions),
        "exit_positions_m": positions,
        "exit_gap_along_route_m": gaps,
        "max_exit_gap_along_route_m": max(gaps) if gaps else 0.0,
        "mean_exit_gap_along_route_m": (sum(gaps) / len(gaps)) if gaps else 0.0,
        "max_distance_to_nearest_exit_along_route_m": max_nearest,
        "route_fraction_farther_than_500m_from_exit": far_fraction(500.0),
        "route_fraction_farther_than_1000m_from_exit": far_fraction(1000.0),
        "route_fraction_farther_than_1500m_from_exit": far_fraction(1500.0),
        "longest_no_exit_segment_start_m": longest[0],
        "longest_no_exit_segment_end_m": longest[1],
        "longest_no_exit_segment_length_m": longest[2],
    }


def mark_self_near_reviews(records: list[dict[str, Any]]) -> None:
    for row in records:
        row["self_near_review"] = False
        row["self_near_review_peer_exit_ids"] = ""
    for i, a in enumerate(records):
        peers = []
        pa = a.get("_point_m")
        if pa is None:
            continue
        for j, b in enumerate(records):
            if i == j:
                continue
            pb = b.get("_point_m")
            if pb is None:
                continue
            spatial_gap = pa.distance(pb)
            route_gap = abs(float(a["exit_route_position_m"]) - float(b["exit_route_position_m"]))
            if spatial_gap <= SELF_NEAR_SPATIAL_M and route_gap >= SELF_NEAR_ROUTE_GAP_M:
                peers.append(str(b["exit_id"]))
        if peers:
            a["self_near_review"] = True
            a["self_near_review_peer_exit_ids"] = "|".join(peers)


def analyze_case(case_id: str) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any]]:
    route_points = load_route_points(case_id)
    route_line_m = load_route_line_m(case_id, route_points)
    route_len_m = max(item["route_position_m"] for item in route_points)
    trim_summary = load_trim_summary(case_id)
    ib1c_rows = load_ib1c_rows(case_id)
    v123_nodes = load_v123_nodes(case_id)
    v122_clusters = load_v122_clusters(case_id)

    node_records = []
    features = []
    for idx, node in enumerate(v123_nodes, start=1):
        cluster = v122_clusters.get(str(node.get("cluster_id", "")), {})
        merged = {**cluster, **node}
        raw = raw_feature_from_source(cluster)
        route_pos, snap_gap_m, snapped_m = nearest_route_position(merged, route_points, route_line_m)
        ratio = route_pos / route_len_m if route_len_m > 0 else 0.0
        ib1c = nearest_ib1c_row(ib1c_rows, route_pos)

        way_id = clean(raw.get("osm_id")) or clean(cluster.get("source_feature_index")) or clean(merged.get("feature_id"))
        way_name = clean(cluster.get("name")) or clean(raw.get("name")) or clean(ib1c.get("osm_way_name"))
        amenity = clean(merged.get("amenity")) or clean(raw.get("amenity"))
        highway = clean(merged.get("highway")) or clean(raw.get("highway"))
        if not highway and norm(amenity) not in {"parking", "parking_space"}:
            highway = clean(ib1c.get("osm_highway"))
        access = clean(merged.get("access")) or clean(raw.get("access"))
        motor_vehicle = clean(merged.get("motor_vehicle")) or clean(raw.get("motor_vehicle"))
        vehicle = clean(merged.get("vehicle")) or clean(raw.get("vehicle"))
        confidence = safe_float(merged.get("access_exit_confidence_score"), 0.0)
        distance_to_route_m = safe_float(merged.get("distance_to_route_m"), math.inf)
        destination = destination_label(highway, amenity, way_name, case_id)
        role = node_role(
            route_pos,
            route_len_m,
            highway,
            amenity,
            ib1c,
            clean(merged.get("connectivity_review_reason")),
        )
        flag = review_flag(destination, highway, access, motor_vehicle, vehicle, confidence, distance_to_route_m)
        graph_status = "spatial_candidate_not_graph_verified"

        lon, lat = TO_WGS.transform(snapped_m.x, snapped_m.y)
        point_wgs = node_point_wgs(merged) or Point(lon, lat)
        point_m = transform(TO_M.transform, point_wgs)
        exit_id = f"{case_id}__exit_{idx:02d}"
        record = {
            "case_id": case_id,
            "audit_version": "v1.2.4",
            "audit_status": "candidate_audit_not_official_score",
            "exit_id": exit_id,
            "source_v1_2_3_cluster_id": clean(merged.get("cluster_id")),
            "source_v1_2_3_feature_id": clean(merged.get("feature_id")),
            "node_role": role,
            "exit_route_position_m": round(route_pos, 3),
            "exit_route_position_ratio": round(ratio, 6),
            "nearest_osm_way_id": way_id,
            "nearest_osm_way_name": way_name,
            "nearest_osm_highway_type": highway,
            "nearest_osm_access_tag": access,
            "nearest_osm_motor_vehicle_tag": motor_vehicle,
            "nearest_osm_vehicle_tag": vehicle,
            "destination_label": destination,
            "review_flag": flag,
            "graph_connectivity_status": graph_status,
            "spatial_candidate_not_graph_verified": True,
            "distance_to_route_m": round(distance_to_route_m, 3) if math.isfinite(distance_to_route_m) else "",
            "route_snap_gap_m": round(snap_gap_m, 3) if math.isfinite(snap_gap_m) else "",
            "access_exit_confidence": clean(merged.get("access_exit_confidence")),
            "access_exit_confidence_score": confidence,
            "connectivity_review_reason_v1_2_3": clean(merged.get("connectivity_review_reason")),
            "nearest_ib1c_dist_m": clean(ib1c.get("dist_m")),
            "nearest_ib1c_near_trailhead": clean(ib1c.get("near_trailhead")),
            "nearest_ib1c_nearby_named_features": clean(ib1c.get("nearby_named_features")),
            "access_point_lon": point_wgs.x,
            "access_point_lat": point_wgs.y,
            "_point_m": point_m,
        }
        node_records.append(record)

    mark_self_near_reviews(node_records)
    positions = [float(row["exit_route_position_m"]) for row in node_records]
    metrics = spacing_metrics(route_len_m, positions)
    exit_positions = [round(value, 3) for value in metrics["exit_positions_m"]]
    exit_gaps = [round(value, 3) for value in metrics["exit_gap_along_route_m"]]
    summary = {
        "case_id": case_id,
        "audit_version": "v1.2.4",
        "audit_status": "candidate_audit_not_official_score",
        "route_len_m": round(route_len_m, 3),
        "trim_mode": clean(trim_summary.get("trim_mode")),
        "self_near_pair_count": clean(trim_summary.get("self_near_pair_count")),
        "connected_exit_count": metrics["connected_exit_count"],
        "exit_positions_m": json.dumps(exit_positions, ensure_ascii=False),
        "exit_gap_along_route_m": json.dumps(exit_gaps, ensure_ascii=False),
        "max_exit_gap_along_route_m": round(metrics["max_exit_gap_along_route_m"], 3),
        "mean_exit_gap_along_route_m": round(float(metrics["mean_exit_gap_along_route_m"]), 3)
        if metrics["mean_exit_gap_along_route_m"] != ""
        else "",
        "max_distance_to_nearest_exit_along_route_m": round(metrics["max_distance_to_nearest_exit_along_route_m"], 3),
        "route_fraction_farther_than_500m_from_exit": round(metrics["route_fraction_farther_than_500m_from_exit"], 6),
        "route_fraction_farther_than_1000m_from_exit": round(metrics["route_fraction_farther_than_1000m_from_exit"], 6),
        "route_fraction_farther_than_1500m_from_exit": round(metrics["route_fraction_farther_than_1500m_from_exit"], 6),
        "longest_no_exit_segment_start_m": round(metrics["longest_no_exit_segment_start_m"], 3),
        "longest_no_exit_segment_end_m": round(metrics["longest_no_exit_segment_end_m"], 3),
        "longest_no_exit_segment_length_m": round(metrics["longest_no_exit_segment_length_m"], 3),
        "self_near_review_exit_count": sum(1 for row in node_records if row["self_near_review"]),
        "spatial_candidate_not_graph_verified_count": sum(
            1 for row in node_records if row["spatial_candidate_not_graph_verified"]
        ),
    }

    for row in node_records:
        row["exit_gap_to_previous_m"] = ""
        row["exit_gap_to_next_m"] = ""
    ordered = sorted(node_records, key=lambda row: float(row["exit_route_position_m"]))
    for i, row in enumerate(ordered):
        if i > 0:
            row["exit_gap_to_previous_m"] = round(
                float(row["exit_route_position_m"]) - float(ordered[i - 1]["exit_route_position_m"]), 3
            )
        if i + 1 < len(ordered):
            row["exit_gap_to_next_m"] = round(
                float(ordered[i + 1]["exit_route_position_m"]) - float(row["exit_route_position_m"]), 3
            )

    for row in node_records:
        props = {k: v for k, v in row.items() if k != "_point_m"}
        features.append(
            {
                "type": "Feature",
                "properties": props,
                "geometry": {"type": "Point", "coordinates": [row["access_point_lon"], row["access_point_lat"]]},
            }
        )

    geojson = {
        "type": "FeatureCollection",
        "name": f"{case_id}_access_exit_destination_spacing_nodes_v1_2_4",
        "features": features,
    }
    debug = {
        "case_id": case_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "audit_version": "v1.2.4",
        "audit_status": "candidate_audit_not_official_score",
        "inputs": {
            "v1_2_3_nodes": str(access_nodes_path(case_id)),
            "v1_2_2_access_points": str(V122_ROOT / case_id / f"{case_id}_vehicle_access_points_v1_2_2.geojson"),
            "route_line_geojson": str(route_line_path(case_id)),
            "route_points_csv": str(route_points_path(case_id)),
            "trim_summary_csv": str(trim_summary_path(case_id)),
            "ib1c_semantic_enriched_csv": str(
                IB1C_ROOT / case_id / f"{case_id}_route_profile_semantic_enriched.csv"
            ),
        },
        "guardrails": [
            "audit/candidate outputs only",
            "did not modify official scoring scripts",
            "did not modify risk_semantics config",
            "did not recompute THCI scores",
            "route positions preserve ordered route_points and do not dissolve out-and-back geometry",
        ],
        "thresholds": {
            "endpoint_window_m": ENDPOINT_WINDOW_M,
            "self_near_spatial_m": SELF_NEAR_SPATIAL_M,
            "self_near_route_gap_m": SELF_NEAR_ROUTE_GAP_M,
        },
        "summary": summary,
        "nodes": [{k: v for k, v in row.items() if k != "_point_m"} for row in node_records],
    }
    return node_records, summary, geojson, debug


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key.startswith("_"):
                continue
            if key not in columns:
                columns.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in columns})


def py_compile_result() -> dict[str, Any]:
    try:
        py_compile.compile(str(Path(__file__).resolve()), doraise=True)
        return {"status": "PASS", "returncode": 0, "message": ""}
    except Exception as exc:  # pragma: no cover
        return {"status": "FAIL", "returncode": 1, "message": str(exc)}


def git_status_short() -> str:
    proc = subprocess.run(
        ["git", "status", "--short"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return proc.stderr.strip() or proc.stdout.strip()
    return proc.stdout.strip()


def fmt_m(value: Any) -> str:
    if value == "":
        return ""
    return f"{float(value):.1f}"


def build_report(
    node_rows: list[dict[str, Any]],
    summary_rows: list[dict[str, Any]],
    compile_info: dict[str, Any],
    git_status: str,
) -> str:
    by_case: dict[str, list[dict[str, Any]]] = {}
    for row in node_rows:
        by_case.setdefault(row["case_id"], []).append(row)

    lines = [
        "# THCI Support Axis v1.2.4 Access-Exit Destination and Along-Route Spacing Audit",
        "",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Status: audit / candidate only. This is not an official THCI score output.",
        "",
        "Guardrails:",
        "- Did not modify official scoring scripts.",
        "- Did not modify risk_semantics config.",
        "- Did not recompute THCI scores.",
        "- Out-and-back route positions are measured on ordered route_points, not dissolved spatial geometry.",
        "",
        "## Route-Level Spacing",
        "",
        "| Route | exits | route m | positions m | gaps m | max gap m | max nearest m | frac >500m | frac >1000m | frac >1500m | longest no-exit segment m |",
        "|---|---:|---:|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in summary_rows:
        longest = f"{fmt_m(row['longest_no_exit_segment_start_m'])}-{fmt_m(row['longest_no_exit_segment_end_m'])} ({fmt_m(row['longest_no_exit_segment_length_m'])})"
        lines.append(
            "| {case} | {count} | {route_len} | `{positions}` | `{gaps}` | {max_gap} | {max_nearest} | {far500:.3f} | {far1000:.3f} | {far1500:.3f} | {longest} |".format(
                case=row["case_id"],
                count=row["connected_exit_count"],
                route_len=fmt_m(row["route_len_m"]),
                positions=row["exit_positions_m"],
                gaps=row["exit_gap_along_route_m"],
                max_gap=fmt_m(row["max_exit_gap_along_route_m"]),
                max_nearest=fmt_m(row["max_distance_to_nearest_exit_along_route_m"]),
                far500=float(row["route_fraction_farther_than_500m_from_exit"]),
                far1000=float(row["route_fraction_farther_than_1000m_from_exit"]),
                far1500=float(row["route_fraction_farther_than_1500m_from_exit"]),
                longest=longest,
            )
        )

    lines.extend(["", "## Exit Destinations", ""])
    for case_id in ROUTES:
        lines.extend([f"### {case_id}", ""])
        rows = sorted(by_case.get(case_id, []), key=lambda item: float(item["exit_route_position_m"]))
        if not rows:
            lines.extend(["No candidate access-exit nodes from v1.2.3.", ""])
            continue
        lines.append("| exit_id | role | position m | ratio | destination | OSM way | highway | access | review_flag | gap prev/next m |")
        lines.append("|---|---|---:|---:|---|---|---|---|---|---|")
        for row in rows:
            way = row["nearest_osm_way_name"] or row["nearest_osm_way_id"] or "(unnamed)"
            gap_text = f"{row['exit_gap_to_previous_m']}/{row['exit_gap_to_next_m']}"
            lines.append(
                "| {exit_id} | {role} | {pos} | {ratio:.3f} | {dest} | {way} | {highway} | {access} | {flag} | {gap} |".format(
                    exit_id=row["exit_id"].split("__")[-1],
                    role=row["node_role"],
                    pos=fmt_m(row["exit_route_position_m"]),
                    ratio=float(row["exit_route_position_ratio"]),
                    dest=row["destination_label"],
                    way=way,
                    highway=row["nearest_osm_highway_type"],
                    access=row["nearest_osm_access_tag"],
                    flag=row["review_flag"],
                    gap=gap_text,
                )
            )
        lines.append("")

    z_rows = sorted(by_case.get("zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b", []), key=lambda item: float(item["exit_route_position_m"]))
    if len(z_rows) >= 2:
        positions = [float(row["exit_route_position_m"]) for row in z_rows]
        span = max(positions) - min(positions)
        z_summary = next(row for row in summary_rows if row["case_id"] == "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b")
        route_len = float(z_summary["route_len_m"])
        if span >= route_len * 0.4:
            distribution = "分布在路線兩端或相距很遠的 route positions"
        else:
            distribution = "集中在同一段 route positions"
        lines.extend(
            [
                "## Zhonghua UST / Jiuwufeng Connected Review Nodes",
                "",
                f"The 2 connected review nodes are at `{[round(p, 1) for p in positions]}` m along a {route_len:.1f} m route; span is {span:.1f} m, so they are {distribution}.",
                "",
            ]
        )

    spatial_only = [row for row in node_rows if row["spatial_candidate_not_graph_verified"]]
    lines.extend(
        [
            "## Spatial Candidates Not Graph-Verified",
            "",
            "All v1.2.4 rows remain spatial/candidate audit nodes because v1.2.3 did not prove routable graph connectivity to a destination. The rows with the strongest warning flag are:",
            "",
            "| Route | exit_id | destination | review_flag | reason |",
            "|---|---|---|---|---|",
        ]
    )
    for row in spatial_only:
        if row["review_flag"] in {"spatial_only_not_graph_connected", "destination_unknown", "possible_private_or_restricted"}:
            lines.append(
                f"| {row['case_id']} | {row['exit_id'].split('__')[-1]} | {row['destination_label']} | {row['review_flag']} | {row['connectivity_review_reason_v1_2_3']} |"
            )
    if not any(row["review_flag"] in {"spatial_only_not_graph_connected", "destination_unknown", "possible_private_or_restricted"} for row in spatial_only):
        lines.append("| (none) |  |  |  |  |")

    self_near = [row for row in node_rows if row["self_near_review"]]
    lines.extend(["", "## Self-Near Review", ""])
    if self_near:
        for row in self_near:
            lines.append(
                f"- {row['case_id']} {row['exit_id'].split('__')[-1]} is spatially near {row['self_near_review_peer_exit_ids']} but separated along-route; preserve both route positions."
            )
    else:
        lines.append("- No pair of candidate exits is within 30 m spatially while separated by at least 500 m along-route.")

    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "Use v1.2.4 as the next support-axis candidate metric family, especially the along-route spacing and max-distance-to-nearest-exit measures. Do not promote it to official scoring until graph connectivity, access permissions, and usable evacuation destination semantics are validated.",
            "",
            "## py_compile",
            "",
            f"- Status: `{compile_info['status']}`",
            f"- Return code: `{compile_info['returncode']}`",
            f"- Message: `{compile_info.get('message', '')}`",
            "",
            "## git status --short",
            "",
            "```text",
            git_status if git_status else "(clean)",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_nodes: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for case_id in ROUTES:
        case_dir = OUT_DIR / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        nodes, summary, geojson, debug = analyze_case(case_id)
        all_nodes.extend(nodes)
        summaries.append(summary)
        write_json(case_dir / f"{case_id}_access_exit_destination_spacing_nodes_v1_2_4.geojson", geojson)
        write_json(case_dir / f"{case_id}_access_exit_destination_spacing_debug_v1_2_4.json", debug)

    write_csv(DETAIL_CSV, all_nodes)
    write_csv(SUMMARY_CSV, summaries)
    compile_info = py_compile_result()
    git_status = git_status_short()
    SUMMARY_MD.write_text(build_report(all_nodes, summaries, compile_info, git_status), encoding="utf-8-sig")

    print("detail_csv:", DETAIL_CSV)
    print("summary_csv:", SUMMARY_CSV)
    print("summary_md:", SUMMARY_MD)
    print("py_compile:", compile_info["status"])
    for row in summaries:
        print(
            "{case}: exits={count}, max_nearest_m={max_nearest}, longest_no_exit_m={longest}".format(
                case=row["case_id"],
                count=row["connected_exit_count"],
                max_nearest=row["max_distance_to_nearest_exit_along_route_m"],
                longest=row["longest_no_exit_segment_length_m"],
            )
        )
    return 0 if compile_info["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

