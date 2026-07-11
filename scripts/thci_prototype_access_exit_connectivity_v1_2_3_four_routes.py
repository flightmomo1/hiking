# -*- coding: utf-8 -*-
"""Prototype access/exit connectivity review for THCI support axis v1.2.3.

This script creates review metrics only. It does not modify official THCI
scoring scripts, risk semantics config, or existing v1.2 outputs.
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
    from shapely.ops import transform, unary_union
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
V12_ROOT = PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_2_support_updated"
V12_BATCH_ROOT = PROJECT_ROOT / "outputs" / "thci_v1_2_support_updated_four_route_batch_v1"
V122_ROOT = PROJECT_ROOT / "outputs" / "thci_support_vehicle_access_proxy_v1_2_2_prototype"
OUT_DIR = PROJECT_ROOT / "outputs" / "thci_support_access_exit_connectivity_v1_2_3_prototype"

SUMMARY_CSV = OUT_DIR / "four_route_access_exit_connectivity_v1_2_3.csv"
SUMMARY_MD = OUT_DIR / "four_route_access_exit_connectivity_v1_2_3_summary.md"

ENDPOINT_WINDOW_M = 250.0
CLOSE_ROUTE_ACCESS_M = 75.0
TRAILHEAD_ACCESS_M = 200.0
PARKING_ACCESS_M = 250.0
PUBLIC_ROAD_ACCESS_M = 250.0
SERVICE_TRACK_ACCESS_M = 150.0
ROUTE_SAMPLE_STEP_M = 25.0

MAJOR_VEHICLE_HIGHWAYS = {
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

LOW_CONFIDENCE_VEHICLE_HIGHWAYS = {"service", "track"}
BLOCKING_ACCESS_VALUES = {"no", "private", "permit", "customers"}


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


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(out):
        return default
    return out


def route_line_path(case_id: str) -> Path:
    case_dir = IB0D_ROOT / case_id
    candidates = [
        case_dir / f"{case_id}_trimmed_mainline.geojson",
        case_dir / f"{case_id}_mainline_ordered_path_trimmed.geojson",
        case_dir / "mainline_ordered_path_trimmed.geojson",
    ]
    for path in candidates:
        if path.exists():
            return path
    matches = sorted(case_dir.glob("*.geojson"))
    if matches:
        return matches[0]
    raise FileNotFoundError(f"No route line GeoJSON found for {case_id}")


def load_route_line_m(case_id: str):
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
    route_wgs = unary_union(geoms)
    if route_wgs.geom_type == "MultiLineString":
        route_wgs = max(route_wgs.geoms, key=lambda g: g.length)
    to_m = Transformer.from_crs("EPSG:4326", "EPSG:3826", always_xy=True)
    route_m = transform(to_m.transform, route_wgs)
    if not isinstance(route_m, LineString):
        route_m = LineString(list(route_m.coords))
    return route_m


def previous_v12_proxy(case_id: str) -> tuple[float, float]:
    candidates = [
        V12_ROOT / case_id / f"{case_id}_thci_axis_summary_v1_2_support_updated.json",
        V12_ROOT / case_id / f"{case_id}_thci_axis_score_summary_v1_2_support_updated.json",
        V12_BATCH_ROOT / case_id / f"{case_id}_thci_axis_summary_v1_2_support_updated.json",
        V12_BATCH_ROOT / case_id / f"{case_id}_thci_axis_score_summary_v1_2_support_updated.json",
        V12_BATCH_ROOT / case_id / f"{case_id}_thci_v1_2_support_updated_summary.json",
    ]
    path = next((item for item in candidates if item.exists()), None)
    if path is None:
        return 0.0, 0.0
    data = read_json(path)
    support = data.get("support_v1_2_detail") or data.get("support_features") or {}
    sub = data.get("support_v1_2_detail") or data.get("support_subscores") or {}
    return (
        safe_float(support.get("vehicle_accessible_branch_density_proxy"), 0.0),
        safe_float(sub.get("vehicle_access_deficit_score"), 0.0),
    )


def previous_v122_row(case_id: str) -> dict[str, Any]:
    path = V122_ROOT / "four_route_vehicle_access_proxy_v1_2_2.csv"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("case_id") == case_id:
                return row
    return {}


def load_v122_access_clusters(case_id: str) -> list[dict[str, Any]]:
    path = V122_ROOT / case_id / f"{case_id}_vehicle_access_points_v1_2_2.geojson"
    if not path.exists():
        raise FileNotFoundError(path)
    data = read_json(path)
    clusters = []
    for feature in data.get("features", []):
        props = dict(feature.get("properties") or {})
        props["geometry"] = feature.get("geometry")
        clusters.append(props)
    return clusters


def is_blocked_access(props: dict[str, Any]) -> bool:
    return (
        norm(props.get("access")) in BLOCKING_ACCESS_VALUES
        or norm(props.get("motor_vehicle")) in BLOCKING_ACCESS_VALUES
        or norm(props.get("vehicle")) in BLOCKING_ACCESS_VALUES
    )


def classify_access_exit_node(props: dict[str, Any], route_km: float) -> tuple[bool, str, float]:
    distance_m = safe_float(props.get("distance_to_route_m"), math.inf)
    route_m = safe_float(props.get("nearest_route_km"), 0.0) * 1000.0
    highway = norm(props.get("highway"))
    amenity = norm(props.get("amenity"))
    node_type = norm(props.get("type"))
    endpoint_gap_m = min(route_m, max(route_km * 1000.0 - route_m, 0.0))

    if is_blocked_access(props):
        return False, "rejected_blocked_or_private_access_tag", 0.0

    if endpoint_gap_m <= ENDPOINT_WINDOW_M and distance_m <= 500.0:
        return True, "route_endpoint_near_vehicle_feature", 0.78

    if distance_m <= CLOSE_ROUTE_ACCESS_M:
        return True, "direct_low_distance_route_vehicle_access", 0.85

    if node_type == "trailhead_linked" and distance_m <= TRAILHEAD_ACCESS_M:
        return True, "trailhead_linked_to_nearby_vehicle_feature", 0.82

    if amenity == "parking" and distance_m <= PARKING_ACCESS_M:
        return True, "parking_near_route_or_trailhead", 0.80

    if highway in MAJOR_VEHICLE_HIGHWAYS and distance_m <= PUBLIC_ROAD_ACCESS_M:
        return True, f"public_vehicle_road_within_{int(PUBLIC_ROAD_ACCESS_M)}m", 0.70

    if highway in LOW_CONFIDENCE_VEHICLE_HIGHWAYS and distance_m <= SERVICE_TRACK_ACCESS_M:
        return True, f"service_or_track_within_{int(SERVICE_TRACK_ACCESS_M)}m_review_required", 0.55

    return False, "rejected_nearby_feature_without_connectivity_signal", 0.0


def along_route_gap_metrics(route_len_m: float, node_projections_m: list[float]) -> tuple[float, float, float]:
    if route_len_m <= 0:
        return 0.0, 0.0, 0.0
    if not node_projections_m:
        return route_len_m, 1.0, 1.0

    positions = [i * ROUTE_SAMPLE_STEP_M for i in range(int(route_len_m // ROUTE_SAMPLE_STEP_M) + 1)]
    if not positions or positions[-1] < route_len_m:
        positions.append(route_len_m)

    distances = [min(abs(pos - node_pos) for node_pos in node_projections_m) for pos in positions]
    max_gap = max(distances) if distances else route_len_m
    farther_500 = sum(1 for value in distances if value > 500.0) / len(distances)
    farther_1000 = sum(1 for value in distances if value > 1000.0) / len(distances)
    return max_gap, farther_500, farther_1000


def confidence_label(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.55:
        return "medium"
    if score > 0:
        return "low"
    return "none"


def analyze_case(case_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    route_m = load_route_line_m(case_id)
    v122 = previous_v122_row(case_id)
    route_km = safe_float(v122.get("route_km"), 0.0)
    if route_km <= 0:
        route_km = float(route_m.length) / 1000.0
    clusters = load_v122_access_clusters(case_id)

    accepted = []
    rejected = []
    for cluster in clusters:
        is_connected, reason, confidence = classify_access_exit_node(cluster, route_km)
        projection_m = safe_float(cluster.get("nearest_route_km"), 0.0) * 1000.0
        lon = safe_float(cluster.get("access_point_lon"))
        lat = safe_float(cluster.get("access_point_lat"))
        geometry = Point(lon, lat) if lon and lat else None

        record = {
            "case_id": case_id,
            "cluster_id": cluster.get("cluster_id", ""),
            "feature_id": cluster.get("feature_id", ""),
            "highway": cluster.get("highway", ""),
            "amenity": cluster.get("amenity", ""),
            "access": cluster.get("access", ""),
            "motor_vehicle": cluster.get("motor_vehicle", ""),
            "vehicle": cluster.get("vehicle", ""),
            "distance_to_route_m": safe_float(cluster.get("distance_to_route_m"), math.inf),
            "nearest_route_km": safe_float(cluster.get("nearest_route_km"), 0.0),
            "nearest_route_point_lat": cluster.get("nearest_route_lat", ""),
            "nearest_route_point_lon": cluster.get("nearest_route_lon", ""),
            "access_point_lat": lat,
            "access_point_lon": lon,
            "cluster_member_count": cluster.get("cluster_member_count", ""),
            "cluster_member_ids": cluster.get("cluster_member_ids", ""),
            "connectivity_review_reason": reason,
            "access_exit_confidence_score": confidence,
            "access_exit_confidence": confidence_label(confidence),
            "projection_m": projection_m,
            "geometry": geometry,
        }
        if is_connected:
            accepted.append(record)
        else:
            rejected.append(record)

    projections = [item["projection_m"] for item in accepted]
    max_gap, far500, far1000 = along_route_gap_metrics(route_km * 1000.0, projections)
    nearest = min((item["distance_to_route_m"] for item in accepted), default=math.inf)
    confidence_score = sum(item["access_exit_confidence_score"] for item in accepted) / len(accepted) if accepted else 0.0
    old_density, old_deficit = previous_v12_proxy(case_id)

    case_dir = OUT_DIR / case_id
    row = {
        "case_id": case_id,
        "route_km": route_km,
        "v1_2_old_vehicle_accessible_branch_density_proxy": old_density,
        "v1_2_old_vehicle_access_deficit_score": old_deficit,
        "v1_2_2_vehicle_accessible_branch_count": safe_float(v122.get("vehicle_accessible_branch_count"), 0.0),
        "v1_2_2_exit_or_access_point_count": safe_float(v122.get("exit_or_access_point_count"), 0.0),
        "v1_2_2_candidate_vehicle_access_deficit": safe_float(v122.get("candidate_vehicle_access_deficit_v1_2_2"), 0.0),
        "connected_access_exit_count": len(accepted),
        "connected_access_exit_count_per_km": len(accepted) / route_km if route_km > 0 else 0.0,
        "nearest_access_exit_distance_m": "" if not math.isfinite(nearest) else nearest,
        "max_route_gap_to_access_exit_m": max_gap,
        "route_fraction_farther_than_500m_from_access_exit": far500,
        "route_fraction_farther_than_1000m_from_access_exit": far1000,
        "access_exit_confidence_score": confidence_score,
        "access_exit_confidence": confidence_label(confidence_score),
        "rejected_v1_2_2_access_point_count": len(rejected),
        "access_exit_nodes_geojson": str(case_dir / f"{case_id}_access_exit_nodes_v1_2_3.geojson"),
        "prototype_status": "connectivity_review_only_not_official",
    }

    features = []
    for item in accepted:
        props = {k: v for k, v in item.items() if k not in {"geometry", "projection_m"}}
        features.append(
            {
                "type": "Feature",
                "properties": props,
                "geometry": mapping(item["geometry"]) if item["geometry"] else None,
            }
        )
    access_geojson = {
        "type": "FeatureCollection",
        "name": f"{case_id}_access_exit_nodes_v1_2_3",
        "features": features,
    }

    debug = {
        "case_id": case_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "route_line_geojson": str(route_line_path(case_id)),
        "v1_2_2_access_points_source": str(V122_ROOT / case_id / f"{case_id}_vehicle_access_points_v1_2_2.geojson"),
        "review_rules": {
            "endpoint_window_m": ENDPOINT_WINDOW_M,
            "close_route_access_m": CLOSE_ROUTE_ACCESS_M,
            "trailhead_access_m": TRAILHEAD_ACCESS_M,
            "parking_access_m": PARKING_ACCESS_M,
            "public_road_access_m": PUBLIC_ROAD_ACCESS_M,
            "service_track_access_m": SERVICE_TRACK_ACCESS_M,
            "blocked_access_values": sorted(BLOCKING_ACCESS_VALUES),
        },
        "summary_row": row,
        "accepted_nodes": [{k: v for k, v in item.items() if k not in {"geometry"}} for item in accepted],
        "rejected_nodes": [{k: v for k, v in item.items() if k not in {"geometry"}} for item in rejected],
        "guardrails": [
            "did not modify official scoring",
            "did not modify risk_semantics config",
            "did not overwrite existing v1.2 outputs",
            "review metrics only",
        ],
    }
    return row, access_geojson, debug


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


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


def build_report(rows: list[dict[str, Any]], compile_info: dict[str, Any], git_status: str) -> str:
    zhonghua = next((r for r in rows if r["case_id"].startswith("zhonghua_")), None)
    lines = [
        "# THCI Support Access-Exit Connectivity v1.2.3 Prototype",
        "",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This is a review prototype only. It does not produce official THCI support scores.",
        "",
        "Guardrails:",
        "- Did not modify official scoring.",
        "- Did not modify risk semantics config.",
        "- Did not overwrite existing v1.2 outputs.",
        "",
        "## Why v1.2.3 Exists",
        "",
        "- v1.2 old proxy problem: `vehicle_accessible_branch_density_proxy` behaves like route-profile sample density rather than true vehicle-access branch count/km.",
        "- v1.2.1 direction-only problem: fixing only `lower_is_riskier` makes all four routes saturate from `1.0` to `0.0` vehicle-access deficit.",
        "- v1.2.2 feature-density problem: nearby OSM vehicle-like features still make all four candidate deficits `0.0`, so the proxy is too permissive.",
        "- v1.2.3 shifts from density to access/exit connectivity review: route endpoint, trailhead, parking, direct low-distance connection, road class, blocked access tags, and along-route gap metrics.",
        "",
        "## v1.2.3 Review Metrics",
        "",
        "| Route | v1.2.2 access pts | connected exits | exits/km | nearest m | max route gap m | frac >500m | frac >1000m | confidence |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        nearest = row["nearest_access_exit_distance_m"]
        nearest_text = "" if nearest == "" else f"{float(nearest):.1f}"
        lines.append(
            "| {case} | {v122:.0f} | {count} | {density:.3f} | {nearest} | {gap:.1f} | {far500:.3f} | {far1000:.3f} | {conf} |".format(
                case=row["case_id"],
                v122=row["v1_2_2_exit_or_access_point_count"],
                count=row["connected_access_exit_count"],
                density=row["connected_access_exit_count_per_km"],
                nearest=nearest_text,
                gap=row["max_route_gap_to_access_exit_m"],
                far500=row["route_fraction_farther_than_500m_from_access_exit"],
                far1000=row["route_fraction_farther_than_1000m_from_access_exit"],
                conf=row["access_exit_confidence"],
            )
        )

    lines.extend(
        [
            "",
            "## Connectivity Rules",
            "",
            "A v1.2.2 access cluster is kept only when it has a stronger connectivity signal:",
            "- route endpoint within 250m along route and vehicle feature within 500m",
            "- vehicle feature within 75m of the route",
            "- linked trailhead within 200m",
            "- parking within 250m",
            "- major/public vehicle road class within 250m",
            "- service/track within 150m, marked lower-confidence review",
            "",
            "Clusters with `access`, `vehicle`, or `motor_vehicle` tags of `no`, `private`, `permit`, or `customers` are rejected.",
            "",
        ]
    )

    if zhonghua:
        lines.extend(
            [
                "## Zhonghua UST / Jiuwufeng Review",
                "",
                f"v1.2.2 had {zhonghua['v1_2_2_exit_or_access_point_count']:.0f} access/exit clusters. v1.2.3 keeps {zhonghua['connected_access_exit_count']} connected review nodes.",
                f"- nearest_access_exit_distance_m: {zhonghua['nearest_access_exit_distance_m']}",
                f"- max_route_gap_to_access_exit_m: {zhonghua['max_route_gap_to_access_exit_m']:.1f}",
                f"- route_fraction_farther_than_500m_from_access_exit: {zhonghua['route_fraction_farther_than_500m_from_access_exit']:.3f}",
                f"- access_exit_confidence: {zhonghua['access_exit_confidence']}",
                "",
                "This suggests v1.2 may overstate support difficulty if it treats Zhonghua as max vehicle-access deficit, but v1.2.2 also overstated accessibility by counting nearby road-like features too broadly. The remaining v1.2.3 nodes should be manually reviewed before any official scoring change.",
                "",
            ]
        )

    lines.extend(
        [
            "## Recommendation",
            "",
            "Use v1.2.3 as the next candidate basis for replacing `vehicle_accessible_branch_density_proxy`, but do not promote it directly to official scoring yet. The next step should validate real graph connectivity, road access permissions, endpoint/trailhead semantics, and whether an access node is usable as an evacuation exit.",
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
    rows: list[dict[str, Any]] = []
    for case_id in ROUTES:
        case_dir = OUT_DIR / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        row, access_geojson, debug = analyze_case(case_id)
        rows.append(row)
        write_json(case_dir / f"{case_id}_access_exit_nodes_v1_2_3.geojson", access_geojson)
        write_json(case_dir / f"{case_id}_access_exit_connectivity_debug_v1_2_3.json", debug)

    write_csv(SUMMARY_CSV, rows)
    compile_info = py_compile_result()
    git_status = git_status_short()
    SUMMARY_MD.write_text(build_report(rows, compile_info, git_status), encoding="utf-8")

    print("summary_csv:", SUMMARY_CSV)
    print("summary_md:", SUMMARY_MD)
    print("py_compile:", compile_info["status"])
    for row in rows:
        print(
            f"{row['case_id']}: connected={row['connected_access_exit_count']} "
            f"per_km={row['connected_access_exit_count_per_km']:.3f} "
            f"gap={row['max_route_gap_to_access_exit_m']:.1f}m "
            f"far500={row['route_fraction_farther_than_500m_from_access_exit']:.3f}"
        )
    return 0 if compile_info["returncode"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
