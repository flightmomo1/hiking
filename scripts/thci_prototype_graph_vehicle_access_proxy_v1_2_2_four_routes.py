# -*- coding: utf-8 -*-
"""Prototype graph/feature-based vehicle access proxy for THCI support axis v1.2.2.

This script builds candidate vehicle-access evidence only. It does not modify
official scoring scripts, risk semantics config, or existing v1.2 outputs.
"""

from __future__ import annotations

import csv
import json
import math
import py_compile
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pyproj import Transformer
from shapely.geometry import mapping, shape
from shapely.ops import nearest_points, transform, unary_union


PROJECT_ROOT = Path(__file__).resolve().parents[1]

ROUTES = [
    "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b",
    "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b",
    "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b",
    "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b",
]

IB0D_ROOT = PROJECT_ROOT / "outputs" / "ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa"
IB1C_ROOT = PROJECT_ROOT / "outputs" / "ib1c_route_profile_semantics_v1_3b_contract_qa"
OSM_RAW_ROOT = PROJECT_ROOT / "osm_raw_output"
V12_ROOT = PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_2_support_updated"
OUT_DIR = PROJECT_ROOT / "outputs" / "thci_support_vehicle_access_proxy_v1_2_2_prototype"

SUMMARY_CSV = OUT_DIR / "four_route_vehicle_access_proxy_v1_2_2.csv"
SUMMARY_MD = OUT_DIR / "four_route_vehicle_access_proxy_v1_2_2_summary.md"

VEHICLE_HIGHWAYS = {
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "unclassified",
    "residential",
    "living_street",
    "service",
    "track",
    "road",
}

EXCLUDED_HIGHWAYS = {
    "footway",
    "path",
    "steps",
    "pedestrian",
    "cycleway",
    "bridleway",
    "corridor",
    "platform",
    "construction",
    "proposed",
}

BLOCKING_ACCESS_VALUES = {"no", "private", "customers", "permit", "destination"}
MAX_ACCESS_DISTANCE_M = 500.0
ACCESS_POINT_CLUSTER_M = 100.0
TRAILHEAD_LINK_DISTANCE_M = 150.0


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


def load_geometry_collection(path: Path):
    data = read_json(path)
    geometries = []
    if data.get("type") == "FeatureCollection":
        for feature in data.get("features", []):
            geom = feature.get("geometry")
            if geom:
                geometries.append(shape(geom))
    elif data.get("type") == "Feature":
        geometries.append(shape(data["geometry"]))
    else:
        geometries.append(shape(data))
    if not geometries:
        raise ValueError(f"No geometries found: {path}")
    return unary_union(geometries), data


def load_features(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = read_json(path)
    if data.get("type") != "FeatureCollection":
        return []
    return list(data.get("features", []))


def metric_transformers():
    to_m = Transformer.from_crs("EPSG:4326", "EPSG:3826", always_xy=True)
    to_wgs = Transformer.from_crs("EPSG:3826", "EPSG:4326", always_xy=True)
    return to_m, to_wgs


def lower_is_riskier_deficit(density_per_km: float) -> float:
    points = [(2.0, 0.0), (1.0, 0.25), (0.5, 0.5), (0.2, 0.75), (0.0, 1.0)]
    if density_per_km >= 2.0:
        return 0.0
    if density_per_km <= 0.0:
        return 1.0
    for (x_hi, y_hi), (x_lo, y_lo) in zip(points, points[1:]):
        if x_lo <= density_per_km <= x_hi:
            return y_hi + (x_hi - density_per_km) / (x_hi - x_lo) * (y_lo - y_hi)
    return 1.0


def is_vehicle_feature(props: dict[str, Any]) -> tuple[bool, str]:
    highway = norm(props.get("highway") or props.get("highway_norm"))
    amenity = norm(props.get("amenity"))
    access = norm(props.get("access"))
    motor_vehicle = norm(props.get("motor_vehicle"))
    vehicle = norm(props.get("vehicle"))

    if amenity == "parking":
        return True, "amenity=parking"

    if highway in EXCLUDED_HIGHWAYS:
        return False, f"excluded_highway={highway}"
    if highway not in VEHICLE_HIGHWAYS:
        return False, f"non_vehicle_highway={highway or 'missing'}"
    if motor_vehicle in BLOCKING_ACCESS_VALUES or vehicle in BLOCKING_ACCESS_VALUES:
        return False, f"blocked_vehicle_access={motor_vehicle or vehicle}"
    if access in {"private", "no"} and highway not in {"service", "track"}:
        return False, f"blocked_access={access}"
    return True, f"vehicle_highway={highway}"


def stable_feature_id(feature: dict[str, Any], source_file: Path, idx: int) -> str:
    props = feature.get("properties") or {}
    osm_id = norm(props.get("osm_id"))
    osm_type = norm(props.get("osm_type"))
    if osm_id:
        return f"{osm_type}:{osm_id}"
    return f"{source_file.name}:{idx}"


def route_length_km(route_m) -> float:
    return float(route_m.length) / 1000.0


def nearest_route_km(route_m, nearest_on_route_m) -> float:
    try:
        return float(route_m.project(nearest_on_route_m)) / 1000.0
    except Exception:
        return 0.0


def collect_candidate_features(case_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Path]:
    raw_dir = OSM_RAW_ROOT / case_id
    if not raw_dir.exists():
        raise FileNotFoundError(raw_dir)

    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    candidate_files = [raw_dir / "osm_highway_raw.geojson"]
    candidate_files.extend(sorted(raw_dir.glob("*parking*.geojson")))
    candidate_files.extend(sorted(raw_dir.glob("osm_generic_context_raw.geojson")))

    seen_files: set[Path] = set()
    for file_path in candidate_files:
        if file_path in seen_files or not file_path.exists():
            continue
        seen_files.add(file_path)
        for idx, feature in enumerate(load_features(file_path), start=1):
            props = feature.get("properties") or {}
            geom = feature.get("geometry")
            if not geom:
                continue
            ok, reason = is_vehicle_feature(props)
            record = {
                "feature": feature,
                "source_file": file_path,
                "source_feature_index": idx,
                "lineage_reason": reason,
                "feature_id": stable_feature_id(feature, file_path, idx),
            }
            if ok:
                included.append(record)
            else:
                highway = norm(props.get("highway") or props.get("highway_norm"))
                if highway in EXCLUDED_HIGHWAYS:
                    excluded.append(record)

    return included, excluded, raw_dir


def collect_trailheads(case_id: str) -> list[dict[str, Any]]:
    path = OSM_RAW_ROOT / case_id / "osm_trailhead_raw.geojson"
    out = []
    for idx, feature in enumerate(load_features(path), start=1):
        if feature.get("geometry"):
            out.append(
                {
                    "feature": feature,
                    "source_file": path,
                    "source_feature_index": idx,
                    "feature_id": stable_feature_id(feature, path, idx),
                    "lineage_reason": "trailhead_linked_to_vehicle_access_if_near_vehicle_feature",
                }
            )
    return out


def previous_v12_proxy(case_id: str) -> tuple[float, float]:
    path = V12_ROOT / case_id / f"{case_id}_thci_axis_score_summary_v1_2_support_updated.json"
    data = read_json(path)
    detail = data.get("support_v1_2_detail", {})
    return (
        safe_float(detail.get("vehicle_accessible_branch_density_proxy")),
        safe_float(detail.get("vehicle_access_deficit_score")),
    )


def cluster_access_points(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clusters: list[dict[str, Any]] = []
    for item in sorted(points, key=lambda p: (p["nearest_route_km"], p["distance_to_route_m"])):
        assigned = False
        for cluster in clusters:
            if abs(item["nearest_route_km"] - cluster["nearest_route_km"]) * 1000.0 <= ACCESS_POINT_CLUSTER_M:
                cluster["members"].append(item)
                if item["distance_to_route_m"] < cluster["distance_to_route_m"]:
                    cluster.update({k: v for k, v in item.items() if k != "members"})
                assigned = True
                break
        if not assigned:
            new_cluster = dict(item)
            new_cluster["members"] = [item]
            clusters.append(new_cluster)
    return clusters


def analyze_case(case_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    to_m, to_wgs = metric_transformers()
    route_path = route_line_path(case_id)
    route_geom_wgs, _ = load_geometry_collection(route_path)
    route_m = transform(to_m.transform, route_geom_wgs)
    route_km = route_length_km(route_m)

    vehicle_features, excluded_features, raw_dir = collect_candidate_features(case_id)
    trailheads = collect_trailheads(case_id)

    feature_points: list[dict[str, Any]] = []
    nearest_distance = math.inf

    for record in vehicle_features:
        geom_wgs = shape(record["feature"]["geometry"])
        geom_m = transform(to_m.transform, geom_wgs)
        dist_m = float(geom_m.distance(route_m))
        if dist_m > MAX_ACCESS_DISTANCE_M:
            continue
        nearest_on_feature, nearest_on_route = nearest_points(geom_m, route_m)
        route_lon, route_lat = transform(to_wgs.transform, nearest_on_route).coords[0]
        feat_lon, feat_lat = transform(to_wgs.transform, nearest_on_feature).coords[0]
        nearest_km = nearest_route_km(route_m, nearest_on_route)
        nearest_distance = min(nearest_distance, dist_m)
        props = record["feature"].get("properties") or {}
        feature_points.append(
            {
                "type": "vehicle_feature",
                "feature_id": record["feature_id"],
                "stationary_id": record["feature_id"],
                "source_file": str(record["source_file"]),
                "source_feature_index": record["source_feature_index"],
                "name": props.get("name") or "",
                "highway": props.get("highway") or props.get("highway_norm") or "",
                "amenity": props.get("amenity") or "",
                "access": props.get("access") or "",
                "motor_vehicle": props.get("motor_vehicle") or "",
                "vehicle": props.get("vehicle") or "",
                "distance_to_route_m": dist_m,
                "nearest_route_km": nearest_km,
                "nearest_route_lat": route_lat,
                "nearest_route_lon": route_lon,
                "access_point_lat": feat_lat,
                "access_point_lon": feat_lon,
                "lineage": record["lineage_reason"],
                "geometry": nearest_on_feature,
            }
        )

    # Add trailheads only when they are close to an accepted vehicle access feature.
    vehicle_point_geoms_m = [transform(to_m.transform, p["geometry"]) for p in feature_points]
    for record in trailheads:
        geom_wgs = shape(record["feature"]["geometry"])
        geom_m = transform(to_m.transform, geom_wgs)
        if vehicle_point_geoms_m:
            min_vehicle_d = min(float(geom_m.distance(vg)) for vg in vehicle_point_geoms_m)
        else:
            min_vehicle_d = math.inf
        dist_route = float(geom_m.distance(route_m))
        if min_vehicle_d > TRAILHEAD_LINK_DISTANCE_M or dist_route > MAX_ACCESS_DISTANCE_M:
            continue
        _, nearest_on_route = nearest_points(geom_m, route_m)
        route_lon, route_lat = transform(to_wgs.transform, nearest_on_route).coords[0]
        feat_lon, feat_lat = geom_wgs.coords[0] if hasattr(geom_wgs, "coords") else transform(to_wgs.transform, geom_m.centroid).coords[0]
        props = record["feature"].get("properties") or {}
        feature_points.append(
            {
                "type": "trailhead_linked",
                "feature_id": record["feature_id"],
                "source_file": str(record["source_file"]),
                "source_feature_index": record["source_feature_index"],
                "name": props.get("name") or "",
                "highway": props.get("highway") or "",
                "amenity": props.get("amenity") or "",
                "access": props.get("access") or "",
                "motor_vehicle": props.get("motor_vehicle") or "",
                "vehicle": props.get("vehicle") or "",
                "distance_to_route_m": dist_route,
                "nearest_route_km": nearest_route_km(route_m, nearest_on_route),
                "nearest_route_lat": route_lat,
                "nearest_route_lon": route_lon,
                "access_point_lat": feat_lat,
                "access_point_lon": feat_lon,
                "lineage": f"trailhead within {min_vehicle_d:.1f}m of accepted vehicle feature",
                "geometry": geom_wgs,
            }
        )

    clusters = cluster_access_points(feature_points)
    vehicle_branch_count = len([p for p in feature_points if p["type"] == "vehicle_feature"])
    exit_or_access_point_count = len(clusters)
    density = vehicle_branch_count / route_km if route_km > 0 else 0.0
    candidate_deficit = lower_is_riskier_deficit(density)
    old_density, old_deficit = previous_v12_proxy(case_id)

    row = {
        "case_id": case_id,
        "route_km": route_km,
        "vehicle_accessible_branch_count": vehicle_branch_count,
        "vehicle_accessible_branch_count_per_km": density,
        "nearest_vehicle_access_distance_m": "" if not math.isfinite(nearest_distance) else nearest_distance,
        "exit_or_access_point_count": exit_or_access_point_count,
        "candidate_vehicle_access_deficit_v1_2_2": candidate_deficit,
        "v1_2_old_vehicle_accessible_branch_density_proxy": old_density,
        "v1_2_old_vehicle_access_deficit_score": old_deficit,
        "vehicle_access_points_geojson": str(OUT_DIR / case_id / f"{case_id}_vehicle_access_points_v1_2_2.geojson"),
        "access_point_lineage": "osm_highway_raw vehicle highways plus linked trailheads; pure footway/path/steps excluded",
        "prototype_status": "candidate_review_only_not_official",
    }

    geojson_features = []
    for idx, cluster in enumerate(clusters, start=1):
        representative = {k: v for k, v in cluster.items() if k not in {"geometry", "members"}}
        representative["cluster_id"] = idx
        representative["cluster_member_count"] = len(cluster["members"])
        representative["cluster_member_ids"] = "|".join(m["feature_id"] for m in cluster["members"])
        geojson_features.append(
            {
                "type": "Feature",
                "properties": representative,
                "geometry": mapping(cluster["geometry"]),
            }
        )

    access_geojson = {
        "type": "FeatureCollection",
        "name": f"{case_id}_vehicle_access_points_v1_2_2",
        "features": geojson_features,
    }

    debug = {
        "case_id": case_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "route_line_geojson": str(route_path),
        "osm_raw_dir": str(raw_dir),
        "included_vehicle_feature_count_within_distance": vehicle_branch_count,
        "excluded_pedestrian_feature_count_seen": len(excluded_features),
        "excluded_highway_values": sorted(EXCLUDED_HIGHWAYS),
        "included_highway_values": sorted(VEHICLE_HIGHWAYS),
        "max_access_distance_m": MAX_ACCESS_DISTANCE_M,
        "trailhead_link_distance_m": TRAILHEAD_LINK_DISTANCE_M,
        "cluster_distance_m": ACCESS_POINT_CLUSTER_M,
        "summary_row": row,
        "included_points": [
            {k: v for k, v in item.items() if k != "geometry"} for item in feature_points
        ],
        "excluded_examples": [
            {
                "feature_id": item["feature_id"],
                "source_file": str(item["source_file"]),
                "lineage_reason": item["lineage_reason"],
            }
            for item in excluded_features[:50]
        ],
        "guardrails": [
            "did not modify official scoring",
            "did not modify risk_semantics config",
            "did not overwrite existing v1.2 outputs",
            "candidate proxy only",
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
        "# THCI Support Vehicle Access Proxy v1.2.2 Prototype",
        "",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This is a candidate prototype only, not official THCI scoring.",
        "",
        "Guardrails:",
        "- Did not modify official scoring.",
        "- Did not modify risk semantics config.",
        "- Did not overwrite existing v1.2 outputs.",
        "",
        "## Candidate Proxy",
        "",
        "| Route | vehicle branches | branches/km | nearest vehicle access m | access/exit points | candidate deficit | old v1.2 proxy | old v1.2 deficit |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        nearest = row["nearest_vehicle_access_distance_m"]
        nearest_text = "" if nearest == "" else f"{float(nearest):.3f}"
        lines.append(
            "| {case} | {count} | {density:.3f} | {nearest} | {access_count} | {deficit:.3f} | {old_density:.3f} | {old_deficit:.3f} |".format(
                case=row["case_id"],
                count=row["vehicle_accessible_branch_count"],
                density=row["vehicle_accessible_branch_count_per_km"],
                nearest=nearest_text,
                access_count=row["exit_or_access_point_count"],
                deficit=row["candidate_vehicle_access_deficit_v1_2_2"],
                old_density=row["v1_2_old_vehicle_accessible_branch_density_proxy"],
                old_deficit=row["v1_2_old_vehicle_access_deficit_score"],
            )
        )

    lines.extend(
        [
            "",
            "## Feature Rules",
            "",
            "Vehicle-accessible features included:",
            "",
            "`motorway`, `trunk`, `primary`, `secondary`, `tertiary`, `unclassified`, `residential`, `living_street`, `service`, `track`, `road`, plus `amenity=parking` when present.",
            "",
            "Features excluded:",
            "",
            "`footway`, `path`, `steps`, `pedestrian`, `cycleway`, `bridleway`, `corridor`, `platform`, `construction`, `proposed`.",
            "",
            "Trailheads are not treated as vehicle roads by themselves. They are included only when close to an accepted vehicle-access feature.",
            "",
            "## Difference From v1.2 Old Proxy",
            "",
            "The old v1.2 proxy was route-profile sample density near `near_highway` or `near_trailhead`, which produced values around 1000. This prototype counts OSM vehicle-accessible features within a route buffer and normalizes by route length.",
            "",
        ]
    )

    if zhonghua:
        lines.extend(
            [
                "## Zhonghua UST / Jiuwufeng",
                "",
                "Candidate result:",
                f"- vehicle_accessible_branch_count: {zhonghua['vehicle_accessible_branch_count']}",
                f"- vehicle_accessible_branch_count_per_km: {zhonghua['vehicle_accessible_branch_count_per_km']:.3f}",
                f"- exit_or_access_point_count: {zhonghua['exit_or_access_point_count']}",
                f"- candidate_vehicle_access_deficit_v1_2_2: {zhonghua['candidate_vehicle_access_deficit_v1_2_2']:.3f}",
                "",
                "This prototype suggests Zhonghua has multiple nearby vehicle-access features/access points. That argues against treating vehicle access as max-deficit, but the access point quality still needs human review because OSM `service`/`track` may include restricted or practically unsuitable roads.",
                "",
            ]
        )

    lines.extend(
        [
            "## Recommendation",
            "",
            "Do not promote this directly to official support scoring yet. It is a better candidate than the v1.2 sample-density proxy, but formal v1.2.2 should validate true graph connectivity, road access permissions, trailhead-road linkage, and alternative exit semantics.",
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
        write_json(case_dir / f"{case_id}_vehicle_access_points_v1_2_2.geojson", access_geojson)
        write_json(case_dir / f"{case_id}_vehicle_access_proxy_debug_v1_2_2.json", debug)

    write_csv(SUMMARY_CSV, rows)
    compile_info = py_compile_result()
    git_status = git_status_short()
    SUMMARY_MD.write_text(build_report(rows, compile_info, git_status), encoding="utf-8")

    print("summary_csv:", SUMMARY_CSV)
    print("summary_md:", SUMMARY_MD)
    print("py_compile:", compile_info["status"])
    for row in rows:
        print(
            f"{row['case_id']}: count={row['vehicle_accessible_branch_count']} "
            f"density={row['vehicle_accessible_branch_count_per_km']:.3f} "
            f"deficit={row['candidate_vehicle_access_deficit_v1_2_2']:.3f}"
        )
    return 0 if compile_info["returncode"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
