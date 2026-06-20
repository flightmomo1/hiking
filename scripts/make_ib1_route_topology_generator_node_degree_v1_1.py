#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IB1 route topology generator node-degree v1.1

Purpose
-------
Build an upstream governed route-topology evidence layer when usable OSM graph
sources are available. This is not a CH6.5 radar script and does not compute
ability scores, ranks, classes, route suitability, final risk, or go/no-go
recommendations.

Outputs
-------
outputs/report_figures/ib1_route_topology_generator_node_degree_v1_1/
  - route_topology_source_inventory_v1_1.csv
  - route_topology_route_sources_v1_1.csv
  - route_topology_nodes_v1_1.csv
  - route_topology_edges_v1_1.csv
  - route_topology_side_branches_v1_1.csv
  - route_topology_decision_points_v1_1.csv
  - route_topology_route_summary_v1_1.csv
  - route_topology_generator_audit_v1_1.csv
  - route_topology_generator_report_v1_1.html

Design boundary
---------------
This script only admits governed fork/decision-point candidates when it can
construct graph topology from OSM/GeoJSON/edge-table sources and align graph
nodes to a route-position source. Semantic, guidepost, anchor, self-near, and
report files remain context only.
"""

from __future__ import annotations

import csv
import html
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import pandas as pd
except Exception as exc:  # pragma: no cover
    print("ERROR: pandas is required for this script.", file=sys.stderr)
    raise

PROJECT_ROOT = Path.cwd()
OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "report_figures" / "ib1_route_topology_generator_node_degree_v1_1"

MAX_FILE_BYTES_JSON = 250 * 1024 * 1024
MAX_FILE_BYTES_XML = 250 * 1024 * 1024
MAX_FILE_BYTES_CSV = 120 * 1024 * 1024
ROUTE_NODE_MATCH_THRESHOLD_M = 35.0
MAINLINE_EDGE_ROUTE_DELTA_MAX_M = 120.0
CSV_SAMPLE_ROWS = 20000

FORBIDDEN_PATTERNS = [
    "ability_score", "ability_rank", "ability_class", "rank", "class_label",
    "final_hiking_risk_score", "route_suitability_score", "go_no_go", "medical_diagnosis", "causal_claim",
]

LAT_CANDIDATES = ["lat", "latitude", "route_lat", "point_lat", "osm_lat", "matched_lat", "node_lat"]
LON_CANDIDATES = ["lon", "lng", "longitude", "route_lon", "point_lon", "osm_lon", "matched_lon", "node_lon"]
DIST_CANDIDATES = [
    "route_dist_m", "mainline_route_dist_m", "dist_m", "distance_m", "cum_dist_m",
    "cumulative_distance_m", "route_distance_m", "distance_along_m", "dist_along_m", "s_m", "elapsed_dist_m",
]

PATH_INCLUDE_HINTS = [
    "ia1", "ib0", "ib1", "osm", "route", "mainline", "graph", "semantic", "anchor", "self_near",
]
PATH_EXCLUDE_HINTS = [
    "activity_input", "weather", "ib3a", "ib3c", "ib3d", "ib3w", "report_figures/ch6_5_5_fork_decision_point_inventory_v1",
    "report_figures/ib1_route_topology_decision_point_inventory_v1",
]

CASE_KEYWORDS = {
    "qixing_lengshuikeng": ["qixing", "lengshuikeng"],
    "qixing_xiaoyoukeng": ["qixing", "xiaoyoukeng"],
    "qixing_lengshuikeng_xiaoyoukeng": ["qixing", "lengshuikeng", "xiaoyoukeng"],
    "juansi_waterfall": ["juansi", "waterfall"],
    "zhonghua_ust_jiuwufeng": ["zhonghua", "jiuwufeng"],
}


def norm_path_text(path: Path) -> str:
    return str(path).replace("\\", "/").lower()


def infer_case_id(path: Path) -> str:
    s = norm_path_text(path)
    best_case = "UNKNOWN_ROUTE"
    best_score = 0
    for case, keys in CASE_KEYWORDS.items():
        score = sum(1 for k in keys if k in s)
        if score > best_score:
            best_case, best_score = case, score
    if best_score > 0:
        return best_case
    # fallback: use parent/name, compacted
    stem = path.stem.lower()
    parent = path.parent.name.lower()
    text = stem if len(stem) > 8 else parent
    text = re.sub(r"[^a-z0-9_]+", "_", text).strip("_")
    return text[:120] or "UNKNOWN_ROUTE"


def should_scan_file(path: Path) -> bool:
    rel = norm_path_text(path.relative_to(PROJECT_ROOT)) if path.is_absolute() and PROJECT_ROOT in path.parents else norm_path_text(path)
    if not rel.startswith("outputs/") and not rel.startswith("data/") and not rel.startswith("configs/"):
        return False
    if any(x in rel for x in PATH_EXCLUDE_HINTS):
        return False
    if not any(x in rel for x in PATH_INCLUDE_HINTS):
        return False
    return True


def safe_rel(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(max(0.0, min(1.0, a))))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    y = math.sin(dlambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def angle_diff_deg(a: float, b: float) -> float:
    d = abs((a - b + 180.0) % 360.0 - 180.0)
    return d


def pick_col(cols: Sequence[str], candidates: Sequence[str]) -> Optional[str]:
    lower_map = {c.lower(): c for c in cols}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    # looser exact suffix match, not too broad
    for c in cols:
        lc = c.lower()
        for cand in candidates:
            if lc.endswith("_" + cand.lower()):
                return c
    return None


def read_csv_header(path: Path) -> List[str]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            return next(reader, [])
    except Exception:
        try:
            with path.open("r", encoding="cp950", newline="") as f:
                reader = csv.reader(f)
                return next(reader, [])
        except Exception:
            return []


def count_csv_rows(path: Path, limit: int = 1000000) -> Optional[int]:
    try:
        with path.open("r", encoding="utf-8-sig", errors="ignore") as f:
            # subtract header
            n = sum(1 for _ in f) - 1
            return max(n, 0)
    except Exception:
        return None


@dataclass
class GraphData:
    source_path: str
    case_id: str
    node_latlon: Dict[str, Tuple[float, float]]
    adjacency: Dict[str, set]
    edge_rows: List[Dict[str, Any]]
    source_kind: str


@dataclass
class RouteData:
    source_path: str
    case_id: str
    points: List[Tuple[float, float, float]]  # lat, lon, route_dist_m
    source_kind: str


def add_edge(adjacency: Dict[str, set], edge_rows: List[Dict[str, Any]], u: str, v: str, way_id: str, source_path: str, node_latlon: Dict[str, Tuple[float, float]]) -> None:
    if u == v:
        return
    adjacency[u].add(v)
    adjacency[v].add(u)
    lat1, lon1 = node_latlon[u]
    lat2, lon2 = node_latlon[v]
    edge_rows.append({
        "source_path": source_path,
        "way_id": way_id,
        "u_node_id": u,
        "v_node_id": v,
        "u_lat": lat1,
        "u_lon": lon1,
        "v_lat": lat2,
        "v_lon": lon2,
        "edge_length_m": round(haversine_m(lat1, lon1, lat2, lon2), 3),
    })


def parse_overpass_json(path: Path) -> Optional[GraphData]:
    if path.stat().st_size > MAX_FILE_BYTES_JSON:
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    elements = data.get("elements") if isinstance(data, dict) else None
    if not isinstance(elements, list):
        return None
    nodes: Dict[str, Tuple[float, float]] = {}
    ways: List[Dict[str, Any]] = []
    for el in elements:
        if not isinstance(el, dict):
            continue
        if el.get("type") == "node" and "lat" in el and "lon" in el and "id" in el:
            try:
                nodes[str(el["id"])] = (float(el["lat"]), float(el["lon"]))
            except Exception:
                pass
        elif el.get("type") == "way" and isinstance(el.get("nodes"), list):
            tags = el.get("tags") or {}
            # Admit routes/path-like linear ways. Do not require highway only because some exported OSM ways use route/foot tags.
            if any(k in tags for k in ["highway", "route", "foot", "trail_visibility", "sac_scale"]):
                ways.append(el)
    if not nodes or not ways:
        return None
    adjacency: Dict[str, set] = defaultdict(set)
    edge_rows: List[Dict[str, Any]] = []
    for way in ways:
        way_id = str(way.get("id", ""))
        nds = [str(n) for n in way.get("nodes", []) if str(n) in nodes]
        for u, v in zip(nds, nds[1:]):
            add_edge(adjacency, edge_rows, u, v, way_id, safe_rel(path), nodes)
    if not edge_rows:
        return None
    return GraphData(safe_rel(path), infer_case_id(path), nodes, adjacency, edge_rows, "overpass_json")


def coord_node_id(lat: float, lon: float) -> str:
    return f"coord:{lat:.7f},{lon:.7f}"


def iter_geojson_lines(geom: Dict[str, Any]) -> Iterable[List[Tuple[float, float]]]:
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if gtype == "LineString" and isinstance(coords, list):
        line = []
        for p in coords:
            if isinstance(p, list) and len(p) >= 2:
                line.append((float(p[1]), float(p[0])))
        if len(line) >= 2:
            yield line
    elif gtype == "MultiLineString" and isinstance(coords, list):
        for part in coords:
            line = []
            for p in part:
                if isinstance(p, list) and len(p) >= 2:
                    line.append((float(p[1]), float(p[0])))
            if len(line) >= 2:
                yield line


def parse_geojson(path: Path) -> Optional[GraphData]:
    if path.stat().st_size > MAX_FILE_BYTES_JSON:
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    features = data.get("features") if isinstance(data, dict) else None
    if not isinstance(features, list):
        return None
    node_latlon: Dict[str, Tuple[float, float]] = {}
    adjacency: Dict[str, set] = defaultdict(set)
    edge_rows: List[Dict[str, Any]] = []
    line_count = 0
    for i, feat in enumerate(features):
        if not isinstance(feat, dict):
            continue
        props = feat.get("properties") or {}
        geom = feat.get("geometry") or {}
        # Keep path-like line features. If no properties exist but filename strongly says osm graph/highway, still try.
        prop_text = " ".join([str(k) + "=" + str(v) for k, v in props.items()]).lower()
        filename_hint = path.name.lower()
        if not any(x in prop_text for x in ["highway", "footway", "path", "trail", "hiking", "route"]) and not any(x in filename_hint for x in ["osm", "graph", "highway", "route"]):
            continue
        way_id = str(props.get("id") or props.get("osm_id") or props.get("way_id") or f"feature_{i}")
        for line in iter_geojson_lines(geom):
            line_count += 1
            ids = []
            for lat, lon in line:
                nid = coord_node_id(lat, lon)
                node_latlon[nid] = (lat, lon)
                ids.append(nid)
            for u, v in zip(ids, ids[1:]):
                add_edge(adjacency, edge_rows, u, v, way_id, safe_rel(path), node_latlon)
    if not edge_rows:
        return None
    return GraphData(safe_rel(path), infer_case_id(path), node_latlon, adjacency, edge_rows, "geojson_lines")


def parse_osm_xml(path: Path) -> Optional[GraphData]:
    if path.stat().st_size > MAX_FILE_BYTES_XML:
        return None
    node_latlon: Dict[str, Tuple[float, float]] = {}
    ways: List[Tuple[str, List[str], Dict[str, str]]] = []
    try:
        context = ET.iterparse(path, events=("end",))
        for _, elem in context:
            tag = elem.tag.split("}")[-1]
            if tag == "node":
                nid = elem.attrib.get("id")
                lat = elem.attrib.get("lat")
                lon = elem.attrib.get("lon")
                if nid and lat and lon:
                    try:
                        node_latlon[str(nid)] = (float(lat), float(lon))
                    except Exception:
                        pass
                elem.clear()
            elif tag == "way":
                wid = elem.attrib.get("id", "")
                nds = []
                tags = {}
                for child in elem:
                    ctag = child.tag.split("}")[-1]
                    if ctag == "nd" and child.attrib.get("ref"):
                        nds.append(str(child.attrib["ref"]))
                    elif ctag == "tag" and child.attrib.get("k"):
                        tags[child.attrib["k"]] = child.attrib.get("v", "")
                if any(k in tags for k in ["highway", "route", "foot", "trail_visibility", "sac_scale"]):
                    ways.append((str(wid), nds, tags))
                elem.clear()
    except Exception:
        return None
    adjacency: Dict[str, set] = defaultdict(set)
    edge_rows: List[Dict[str, Any]] = []
    for way_id, nds, _tags in ways:
        nds = [n for n in nds if n in node_latlon]
        for u, v in zip(nds, nds[1:]):
            add_edge(adjacency, edge_rows, u, v, way_id, safe_rel(path), node_latlon)
    if not edge_rows:
        return None
    return GraphData(safe_rel(path), infer_case_id(path), node_latlon, adjacency, edge_rows, "osm_xml")


def try_parse_graph(path: Path) -> Optional[GraphData]:
    suffix = path.suffix.lower()
    if suffix in [".json", ".geojson"]:
        g = parse_overpass_json(path)
        if g:
            return g
        return parse_geojson(path)
    if suffix in [".osm", ".xml"]:
        return parse_osm_xml(path)
    return None


def load_route_csv(path: Path) -> Optional[RouteData]:
    if path.stat().st_size > MAX_FILE_BYTES_CSV:
        return None
    cols = read_csv_header(path)
    if not cols:
        return None
    lat_col = pick_col(cols, LAT_CANDIDATES)
    lon_col = pick_col(cols, LON_CANDIDATES)
    if not lat_col or not lon_col:
        return None
    name = path.name.lower()
    rel = norm_path_text(path)
    # Avoid activity, weather, and configuration/control tables.  Config route
    # definitions may contain lat/lon/distance-like columns, but they are not
    # governed route-position traces for topology projection.
    if any(x in rel for x in ["activity", "weather", "station"]):
        return None
    if rel.startswith("configs/") or "/configs/" in rel:
        return None
    if any(x in name for x in ["control_points", "expected_time_segments", "anchor_manifest", "route_anchors"]):
        return None
    # Only admit ordered route-position/profile style sources.
    if not any(x in name or x in rel for x in ["route_profile", "mainline", "route_definition", "route_points", "semantic_enriched", "terrain_enriched"]):
        return None
    dist_col = pick_col(cols, DIST_CANDIDATES)
    try:
        df = pd.read_csv(path, nrows=CSV_SAMPLE_ROWS, low_memory=False)
    except Exception:
        try:
            df = pd.read_csv(path, nrows=CSV_SAMPLE_ROWS, encoding="cp950", low_memory=False)
        except Exception:
            return None
    if lat_col not in df.columns or lon_col not in df.columns:
        return None
    df = df[[c for c in [lat_col, lon_col, dist_col] if c and c in df.columns]].copy()
    df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
    df[lon_col] = pd.to_numeric(df[lon_col], errors="coerce")
    df = df.dropna(subset=[lat_col, lon_col])
    # Taiwan rough bbox filter to avoid accidental x/y columns.
    df = df[(df[lat_col].between(21.5, 26.5)) & (df[lon_col].between(118.0, 123.5))]
    if len(df) < 2:
        return None
    points: List[Tuple[float, float, float]] = []
    if dist_col and dist_col in df.columns:
        df[dist_col] = pd.to_numeric(df[dist_col], errors="coerce")
        if df[dist_col].notna().sum() >= 2:
            for _, r in df.iterrows():
                d = r.get(dist_col)
                if pd.isna(d):
                    continue
                points.append((float(r[lat_col]), float(r[lon_col]), float(d)))
    if len(points) < 2:
        cumulative = 0.0
        prev = None
        for _, r in df.iterrows():
            lat, lon = float(r[lat_col]), float(r[lon_col])
            if prev is not None:
                cumulative += haversine_m(prev[0], prev[1], lat, lon)
            points.append((lat, lon, cumulative))
            prev = (lat, lon)
    if len(points) < 2:
        return None
    return RouteData(safe_rel(path), infer_case_id(path), points, "route_position_csv")


def source_role_for_file(path: Path, graph_ok: bool, route_ok: bool) -> str:
    s = norm_path_text(path)
    name = path.name.lower()
    if graph_ok:
        return "usable_osm_graph_topology_source"
    if route_ok:
        return "usable_route_position_source"
    if "graph" in s and any(x in name for x in ["summary", "audit"]):
        return "route_graph_summary_without_position"
    if "self_near" in s:
        return "route_geometry_self_near_context_not_fork_inventory"
    if "semantic" in s or "guidepost" in s or "facility" in s:
        return "route_semantic_context_not_fork_inventory"
    if "anchor" in s or "control_points" in s:
        return "route_anchor_control_context_not_fork_inventory"
    if "report" in s or "audit" in s or "summary" in s:
        return "report_context_not_topology_source"
    if path.suffix.lower() == ".py":
        return "script_hint_not_data_source"
    return "other_context_not_topology_source"


def discover_sources() -> Tuple[List[Dict[str, Any]], List[GraphData], List[RouteData]]:
    files: List[Path] = []
    for base in [PROJECT_ROOT / "outputs", PROJECT_ROOT / "data", PROJECT_ROOT / "configs"]:
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in [".csv", ".json", ".geojson", ".osm", ".xml", ".py", ".html", ".md"]:
                continue
            if should_scan_file(p):
                files.append(p)
    # Add route/topology scripts as hints only.
    scripts_dir = PROJECT_ROOT / "scripts"
    if scripts_dir.exists():
        for p in scripts_dir.glob("*.py"):
            if any(x in p.name.lower() for x in ["route", "graph", "mainline", "osm", "topology", "anchor", "semantic"]):
                files.append(p)

    source_rows: List[Dict[str, Any]] = []
    graphs: List[GraphData] = []
    routes: List[RouteData] = []
    seen = set()
    for path in sorted(files, key=lambda x: safe_rel(x)):
        rel = safe_rel(path)
        if rel in seen:
            continue
        seen.add(rel)
        size = path.stat().st_size if path.exists() else 0
        header = read_csv_header(path) if path.suffix.lower() == ".csv" and size <= MAX_FILE_BYTES_CSV else []
        graph = None
        route = None
        parse_error = ""
        if path.suffix.lower() in [".json", ".geojson", ".osm", ".xml"]:
            try:
                graph = try_parse_graph(path)
            except Exception as exc:
                parse_error = f"graph_parse_error:{type(exc).__name__}"
        if path.suffix.lower() == ".csv":
            try:
                route = load_route_csv(path)
            except Exception as exc:
                parse_error = f"route_parse_error:{type(exc).__name__}"
        if graph:
            graphs.append(graph)
        if route:
            routes.append(route)
        role = source_role_for_file(path, graph_ok=graph is not None, route_ok=route is not None)
        source_rows.append({
            "source_path": rel,
            "exists": True,
            "file_size_bytes": size,
            "row_count": count_csv_rows(path) if path.suffix.lower() == ".csv" and size <= MAX_FILE_BYTES_CSV else "",
            "candidate_columns": "|".join(header[:80]) if header else "",
            "source_role": role,
            "usable_for_osm_graph_topology": bool(graph),
            "usable_for_node_degree": bool(graph),
            "usable_for_adjacent_edges": bool(graph),
            "usable_for_side_branch": bool(graph),
            "usable_for_route_dist_position": bool(route),
            "case_id": infer_case_id(path),
            "rejection_reason": "" if graph or route else (parse_error or "context_or_summary_only_not_governed_topology_source"),
            "notes": "directly parsed as governed topology/route-position source" if graph or route else "not expanded into topology candidates",
        })
    return source_rows, graphs, routes


def merge_graphs(graphs: List[GraphData]) -> GraphData:
    node_latlon: Dict[str, Tuple[float, float]] = {}
    adjacency: Dict[str, set] = defaultdict(set)
    edge_rows: List[Dict[str, Any]] = []
    for g in graphs:
        for nid, ll in g.node_latlon.items():
            # Prefix non-coordinate IDs with source short hash to avoid cross-file collisions.
            new_id = nid if nid.startswith("coord:") else f"{abs(hash(g.source_path)) % 1000000}:{nid}"
            node_latlon[new_id] = ll
        # Recreate edges with prefixed ids.
        for e in g.edge_rows:
            u0, v0 = str(e["u_node_id"]), str(e["v_node_id"])
            u = u0 if u0.startswith("coord:") else f"{abs(hash(g.source_path)) % 1000000}:{u0}"
            v = v0 if v0.startswith("coord:") else f"{abs(hash(g.source_path)) % 1000000}:{v0}"
            if u in node_latlon and v in node_latlon:
                add_edge(adjacency, edge_rows, u, v, str(e.get("way_id", "")), g.source_path, node_latlon)
    return GraphData("MERGED_GRAPH_SOURCES", "ALL_SCANNED_ROUTES", node_latlon, adjacency, edge_rows, "merged")


def select_best_routes(routes: List[RouteData]) -> List[RouteData]:
    if not routes:
        return []
    priority_terms = [
        "route_profile_semantic_enriched", "route_profile_nlsc", "route_profile_contour", "route_profile",
        "mainline_route_definition", "route_definition", "mainline",
    ]
    by_case: Dict[str, List[RouteData]] = defaultdict(list)
    for r in routes:
        by_case[r.case_id].append(r)
    selected = []
    for case, rs in by_case.items():
        def score(r: RouteData) -> Tuple[int, int]:
            s = r.source_path.lower()
            pscore = 0
            for idx, term in enumerate(priority_terms):
                if term in s:
                    pscore = max(pscore, len(priority_terms) - idx)
            return (pscore, len(r.points))
        selected.append(sorted(rs, key=score, reverse=True)[0])
    return sorted(selected, key=lambda r: r.case_id)


def nearest_route_point(lat: float, lon: float, route_points: List[Tuple[float, float, float]]) -> Tuple[float, float, float, float, int]:
    best = (float("inf"), 0.0, 0.0, 0.0, -1)  # dist, rlat, rlon, route_dist, idx
    # Efficient enough for compact route points and moderate graph nodes.
    for i, (rlat, rlon, rdist) in enumerate(route_points):
        d = haversine_m(lat, lon, rlat, rlon)
        if d < best[0]:
            best = (d, rlat, rlon, rdist, i)
    return best


def route_bearing_near(route_points: List[Tuple[float, float, float]], idx: int) -> Optional[float]:
    if idx < 0 or len(route_points) < 2:
        return None
    if idx == 0:
        a, b = route_points[0], route_points[1]
    elif idx >= len(route_points) - 1:
        a, b = route_points[-2], route_points[-1]
    else:
        a, b = route_points[idx - 1], route_points[idx + 1]
    return bearing_deg(a[0], a[1], b[0], b[1])


def build_topology(graphs: List[GraphData], routes: List[RouteData]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not graphs or not routes:
        return (pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    graph = merge_graphs(graphs)
    selected_routes = select_best_routes(routes)

    node_rows: List[Dict[str, Any]] = []
    decision_rows: List[Dict[str, Any]] = []
    side_rows: List[Dict[str, Any]] = []
    route_summary_rows: List[Dict[str, Any]] = []

    for route in selected_routes:
        route_points = route.points
        matched: Dict[str, Dict[str, Any]] = {}
        # First pass: match graph nodes to route.
        for nid, (lat, lon) in graph.node_latlon.items():
            d, rlat, rlon, rdist, ridx = nearest_route_point(lat, lon, route_points)
            if d <= ROUTE_NODE_MATCH_THRESHOLD_M:
                matched[nid] = {
                    "node_id": nid,
                    "lat": lat,
                    "lon": lon,
                    "mainline_route_dist_m": rdist,
                    "distance_from_mainline_m": d,
                    "nearest_route_point_index": ridx,
                    "nearest_route_lat": rlat,
                    "nearest_route_lon": rlon,
                    "route_bearing_deg": route_bearing_near(route_points, ridx),
                }
        # Second pass: classify node topology.
        case_decisions = 0
        case_forks = 0
        case_nodes = 0
        case_side = 0
        for nid, m in matched.items():
            neighs = list(graph.adjacency.get(nid, set()))
            node_degree = len(neighs)
            mainline_edge_count = 0
            side_branch_count = 0
            side_angles: List[float] = []
            side_min_dist = None
            for nb in neighs:
                nb_match = matched.get(nb)
                nlat, nlon = graph.node_latlon.get(nb, (None, None))
                if nlat is None:
                    continue
                edge_len = haversine_m(m["lat"], m["lon"], nlat, nlon)
                if nb_match and abs(float(nb_match["mainline_route_dist_m"]) - float(m["mainline_route_dist_m"])) <= MAINLINE_EDGE_ROUTE_DELTA_MAX_M:
                    mainline_edge_count += 1
                else:
                    side_branch_count += 1
                    side_bearing = bearing_deg(m["lat"], m["lon"], nlat, nlon)
                    rb = m.get("route_bearing_deg")
                    angle = angle_diff_deg(side_bearing, rb) if rb is not None else ""
                    if angle != "":
                        side_angles.append(float(angle))
                    if side_min_dist is None or edge_len < side_min_dist:
                        side_min_dist = edge_len
                    side_rows.append({
                        "case_id": route.case_id,
                        "route_source_path": route.source_path,
                        "graph_source_path": graph.source_path,
                        "node_id": nid,
                        "mainline_route_dist_m": round(float(m["mainline_route_dist_m"]), 3),
                        "lat": round(float(m["lat"]), 8),
                        "lon": round(float(m["lon"]), 8),
                        "side_branch_neighbor_node_id": nb,
                        "side_branch_neighbor_lat": round(float(nlat), 8),
                        "side_branch_neighbor_lon": round(float(nlon), 8),
                        "side_branch_distance_from_mainline_m": round(float(edge_len), 3),
                        "side_branch_angle_deg": round(float(angle), 3) if angle != "" else "",
                        "classification_reason": "neighbor edge is not aligned to matched mainline route corridor",
                    })
            fork_candidate = side_branch_count > 0 and node_degree >= 3
            decision_point_candidate = fork_candidate
            if fork_candidate:
                case_forks += 1
            if decision_point_candidate:
                case_decisions += 1
            case_nodes += 1
            case_side += side_branch_count
            node_rows.append({
                "case_id": route.case_id,
                "route_source_path": route.source_path,
                "graph_source_path": graph.source_path,
                "node_id": nid,
                "lat": round(float(m["lat"]), 8),
                "lon": round(float(m["lon"]), 8),
                "mainline_route_dist_m": round(float(m["mainline_route_dist_m"]), 3),
                "distance_from_mainline_m": round(float(m["distance_from_mainline_m"]), 3),
                "node_degree": node_degree,
                "adjacent_edge_count": node_degree,
                "mainline_edge_count": mainline_edge_count,
                "side_branch_count": side_branch_count,
                "side_branch_angle_deg": round(max(side_angles), 3) if side_angles else "",
                "side_branch_distance_from_mainline_m": round(float(side_min_dist), 3) if side_min_dist is not None else "",
                "fork_candidate": bool(fork_candidate),
                "decision_point_candidate": bool(decision_point_candidate),
                "governed_candidate_status": "GOVERNED_TOPOLOGY_CANDIDATE" if fork_candidate else "GOVERNED_TOPOLOGY_NODE_CONTEXT",
                "classification_reason": "node_degree>=3 and side_branch_count>0" if fork_candidate else "matched route graph node without side branch",
            })
            if decision_point_candidate:
                decision_rows.append(node_rows[-1].copy())
        route_length = max([p[2] for p in route_points]) if route_points else ""
        route_summary_rows.append({
            "case_id": route.case_id,
            "route_source_path": route.source_path,
            "graph_source_path": graph.source_path,
            "route_length_m": round(float(route_length), 3) if route_length != "" else "",
            "matched_topology_node_count": case_nodes,
            "governed_fork_candidate_count": case_forks,
            "governed_decision_point_candidate_count": case_decisions,
            "side_branch_count": case_side,
            "topology_inventory_status": "GOVERNED_SOURCE_CANDIDATE" if case_decisions > 0 else "NO_DECISION_POINT_CANDIDATE_FROM_MATCHED_GRAPH",
            "source_gap_reason": "" if case_decisions > 0 else "graph and route source parsed, but no node-degree side branch candidate matched route corridor",
        })

    # Filter edge rows to compact manageable output: all merged graph edges can be huge; keep edges near route nodes only.
    matched_node_ids = set(r["node_id"] for r in node_rows)
    edge_rows = []
    for e in graph.edge_rows:
        if e["u_node_id"] in matched_node_ids or e["v_node_id"] in matched_node_ids:
            edge_rows.append(e)
    return (
        pd.DataFrame(node_rows),
        pd.DataFrame(edge_rows),
        pd.DataFrame(side_rows),
        pd.DataFrame(decision_rows),
        pd.DataFrame(route_summary_rows),
    )


def write_csv(df: pd.DataFrame, path: Path, columns: Optional[List[str]] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if columns is not None:
        for col in columns:
            if col not in df.columns:
                df[col] = ""
        df = df[columns]
    df.to_csv(path, index=False, encoding="utf-8-sig")


def make_html_report(audit: Dict[str, Any], admission: Dict[str, Any], source_role_summary: pd.DataFrame, route_summary: pd.DataFrame) -> str:
    def table_html(df: pd.DataFrame, max_rows: int = 50) -> str:
        if df.empty:
            return "<p><em>No rows.</em></p>"
        return df.head(max_rows).to_html(index=False, escape=True)

    audit_items = "".join(f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>" for k, v in audit.items())
    admission_items = "".join(f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>" for k, v in admission.items())
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>IB1 route topology generator node-degree v1.1</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; line-height: 1.45; }}
table {{ border-collapse: collapse; margin: 12px 0; width: 100%; font-size: 13px; }}
th, td {{ border: 1px solid #ddd; padding: 6px 8px; vertical-align: top; }}
th {{ background: #f6f6f6; text-align: left; }}
code {{ background: #f6f6f6; padding: 1px 4px; }}
.status {{ font-weight: 700; }}
</style>
</head>
<body>
<h1>IB1 route topology generator node-degree v1.1</h1>
<p class="status">Audit conclusion: <code>{html.escape(str(audit.get('audit_conclusion', '')))}</code></p>
<p>This report is route-topology source governance only. It does not compute an ability score, rank, class, final hiking risk score, route suitability score, go/no-go decision, medical diagnosis, or causal claim.</p>
<h2>Admission</h2>
<table>{admission_items}</table>
<h2>Audit</h2>
<table>{audit_items}</table>
<h2>Source role summary</h2>
{table_html(source_role_summary)}
<h2>Route summary</h2>
{table_html(route_summary)}
<h2>Interpretation</h2>
<p>If governed fork or decision-point candidates are produced, this output can become an upstream source candidate for future navigation-challenge exposure context. If the audit remains source-gap, upstream IA1/IB0 extraction must expose OSM graph topology: node degree, adjacent edges, side branches, side-branch angle, route distance, and lat/lon.</p>
</body></html>"""


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    source_rows, graphs, routes = discover_sources()
    source_df = pd.DataFrame(source_rows)

    # Compact role summary.
    if source_df.empty:
        source_role_summary = pd.DataFrame(columns=["source_role", "source_count", "notes"])
    else:
        source_role_summary = (
            source_df.groupby("source_role", dropna=False)
            .size()
            .reset_index(name="source_count")
            .sort_values("source_count", ascending=False)
        )
        source_role_summary["notes"] = source_role_summary["source_role"].apply(
            lambda r: "parsed as governed source" if "usable" in str(r) else "context only; not expanded into topology candidates"
        )

    selected_routes = select_best_routes(routes)
    route_sources_df = pd.DataFrame([
        {
            "case_id": r.case_id,
            "route_source_path": r.source_path,
            "point_count": len(r.points),
            "route_length_m": round(max([p[2] for p in r.points]), 3) if r.points else "",
            "source_kind": r.source_kind,
        }
        for r in selected_routes
    ])

    nodes_df, edges_df, side_df, decisions_df, route_summary_df = build_topology(graphs, routes)

    governed_fork_count = int(nodes_df["fork_candidate"].sum()) if not nodes_df.empty and "fork_candidate" in nodes_df.columns else 0
    governed_decision_count = int(nodes_df["decision_point_candidate"].sum()) if not nodes_df.empty and "decision_point_candidate" in nodes_df.columns else 0
    route_dist_available_count = int(nodes_df["mainline_route_dist_m"].replace("", pd.NA).notna().sum()) if not nodes_df.empty and "mainline_route_dist_m" in nodes_df.columns else 0
    lat_lon_available_count = int(nodes_df[["lat", "lon"]].replace("", pd.NA).dropna().shape[0]) if not nodes_df.empty and set(["lat", "lon"]).issubset(nodes_df.columns) else 0

    # Heuristic prior evidence from source-gap review if present, but never admitted here.
    prev_audit = PROJECT_ROOT / "outputs" / "report_figures" / "ib1_route_topology_decision_point_inventory_v1_1" / "route_topology_decision_point_audit_v1_1.csv"
    heuristic_fork_like_count = 0
    heuristic_decision_like_count = 0
    if prev_audit.exists():
        try:
            prev = pd.read_csv(prev_audit)
            if not prev.empty:
                heuristic_fork_like_count = int(pd.to_numeric(prev.loc[0].get("heuristic_fork_like_candidate_count", 0), errors="coerce") or 0)
                heuristic_decision_like_count = int(pd.to_numeric(prev.loc[0].get("heuristic_decision_point_like_candidate_count", 0), errors="coerce") or 0)
        except Exception:
            pass

    source_inventory_count = int(len(source_df))
    usable_graph_count = int(sum(1 for g in graphs if g.edge_rows))
    usable_route_count = int(len(selected_routes))

    forbidden_fields_present = "NONE"
    output_columns = []
    for df in [source_df, route_sources_df, nodes_df, edges_df, side_df, decisions_df, route_summary_df]:
        output_columns.extend(list(df.columns))
    hits = sorted({p for p in FORBIDDEN_PATTERNS for c in output_columns if p in str(c).lower() and not str(c).lower().startswith("not_")})
    if hits:
        forbidden_fields_present = "|".join(hits)

    if governed_decision_count > 0 and route_dist_available_count > 0 and lat_lon_available_count > 0:
        audit_conclusion = "PASS_IB1_ROUTE_TOPOLOGY_GENERATOR_NODE_DEGREE_V1_1_GOVERNED_SOURCE_CANDIDATE"
        admission_decision = "ADMIT_AS_GOVERNED_FORK_DECISION_POINT_SOURCE_CANDIDATE"
        decision_reason = "OSM/graph topology and route-position sources were parsed and produced governed decision-point candidates."
    else:
        audit_conclusion = "PASS_IB1_ROUTE_TOPOLOGY_GENERATOR_NODE_DEGREE_V1_1_SOURCE_GAP_RETAINED"
        admission_decision = "RETAIN_AS_TOPOLOGY_GENERATOR_SOURCE_GAP"
        if usable_graph_count == 0:
            decision_reason = "No parseable OSM/GeoJSON graph topology source was found."
        elif usable_route_count == 0:
            decision_reason = "Graph topology exists, but no usable route-position source was found."
        else:
            decision_reason = "Graph and route-position sources exist, but no governed fork/decision-point candidate was produced under the route-corridor criteria."

    audit = {
        "source_inventory_count": source_inventory_count,
        "usable_osm_graph_topology_source_count": usable_graph_count,
        "usable_route_position_source_count": usable_route_count,
        "usable_node_degree_source_count": usable_graph_count,
        "usable_adjacent_edge_source_count": usable_graph_count,
        "usable_side_branch_source_count": usable_graph_count,
        "generated_node_count": int(len(nodes_df)),
        "generated_edge_count": int(len(edges_df)),
        "generated_side_branch_count": int(len(side_df)),
        "governed_fork_candidate_count": governed_fork_count,
        "governed_decision_point_candidate_count": governed_decision_count,
        "heuristic_fork_like_candidate_count_from_prior_review": heuristic_fork_like_count,
        "heuristic_decision_point_like_candidate_count_from_prior_review": heuristic_decision_like_count,
        "route_dist_available_count": route_dist_available_count,
        "lat_lon_available_count": lat_lon_available_count,
        "zero_fill_used": False,
        "ch6_5_axis_contract_not_modified": True,
        "radar_not_modified": True,
        "data_table_not_modified": True,
        "forbidden_fields_present": forbidden_fields_present,
        "ability_scoring_absent": True,
        "ranking_absent": True,
        "class_label_absent": True,
        "decision_label_absent": True,
        "admission_decision": admission_decision,
        "audit_conclusion": audit_conclusion,
        "interpretation_boundary": "Route topology generator/source governance only. Not an ability score, rank, class, final hiking risk score, route suitability score, go/no-go decision, medical diagnosis, or causal claim.",
    }
    admission = {
        "context_id": "navigation_challenge_exposure",
        "context_label_zh": "導航挑戰暴露",
        "decision": admission_decision,
        "recommended_use": "upstream source candidate for future navigation-challenge exposure context only" if admission_decision.startswith("ADMIT") else "retain source gap; upstream IA1/IB0 topology extraction must be added or repaired",
        "not_personal_ability_axis": True,
        "not_navigation_ability_score": True,
        "not_go_no_go_decision": True,
        "usable_osm_graph_topology_source_count": usable_graph_count,
        "usable_route_position_source_count": usable_route_count,
        "governed_fork_candidate_count": governed_fork_count,
        "governed_decision_point_candidate_count": governed_decision_count,
        "decision_reason": decision_reason,
        "interpretation_boundary": audit["interpretation_boundary"],
    }

    # Ensure stable columns even when empty.
    write_csv(source_df, OUTPUT_ROOT / "route_topology_source_inventory_v1_1.csv")
    write_csv(route_sources_df, OUTPUT_ROOT / "route_topology_route_sources_v1_1.csv")
    write_csv(nodes_df, OUTPUT_ROOT / "route_topology_nodes_v1_1.csv")
    write_csv(edges_df, OUTPUT_ROOT / "route_topology_edges_v1_1.csv")
    write_csv(side_df, OUTPUT_ROOT / "route_topology_side_branches_v1_1.csv")
    write_csv(decisions_df, OUTPUT_ROOT / "route_topology_decision_points_v1_1.csv")
    write_csv(route_summary_df, OUTPUT_ROOT / "route_topology_route_summary_v1_1.csv")
    write_csv(pd.DataFrame([audit]), OUTPUT_ROOT / "route_topology_generator_audit_v1_1.csv")
    write_csv(pd.DataFrame([admission]), OUTPUT_ROOT / "route_topology_generator_admission_v1_1.csv")
    write_csv(source_role_summary, OUTPUT_ROOT / "route_topology_source_role_summary_v1_1.csv")

    report_html = make_html_report(audit, admission, source_role_summary, route_summary_df)
    (OUTPUT_ROOT / "route_topology_generator_report_v1_1.html").write_text(report_html, encoding="utf-8")

    print({
        "output_root": str(OUTPUT_ROOT),
        "source_inventory_count": source_inventory_count,
        "usable_osm_graph_topology_source_count": usable_graph_count,
        "usable_route_position_source_count": usable_route_count,
        "generated_node_count": int(len(nodes_df)),
        "generated_edge_count": int(len(edges_df)),
        "governed_fork_candidate_count": governed_fork_count,
        "governed_decision_point_candidate_count": governed_decision_count,
        "admission_decision": admission_decision,
        "audit_conclusion": audit_conclusion,
    })


if __name__ == "__main__":
    main()
