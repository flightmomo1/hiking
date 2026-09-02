from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET

import folium
import geopandas as gpd
import networkx as nx
import osmnx as ox
import pandas as pd
import requests
from osmnx._errors import InsufficientResponseError
from shapely.geometry import LineString, Point, box, mapping, shape
from shapely.ops import unary_union


PROJECT_ROOT = Path("D:/mountain_work/115_osm")

VERSION = "v1.5.6-qa-cleanup-relation-semantics"
STATUS = (
    "GPX probe first + NLSC 0.125deg theoretical tile authority with conflict blocking + 500m tile fetch buffer + "
    "formal TILE_FULL PBF vs ROUTE_ANALYSIS_SUBSET separation + smart semantic relation completion + "
    "OSM element/id preservation QA + hiking/foot relation-member enrichment onto analysis highway ways + "
    "relation entity-vs-membership QA semantics + explicit TILE_FULL/ROUTE_ANALYSIS map/output labels + "
    "local-first PBF tile cache + explicit-only network fallback + finite governed Overpass retry + Qixing v1.3 semantic outputs"
)

PROJECT_USER_AGENT_NAME = "OutdoorEdge-MountainRouteRisk/0.2"
DEFAULT_GEOFABRIK_TAIWAN_URL = "https://download.geofabrik.de/asia/taiwan-latest.osm.pbf"
OSM_ATTRIBUTION = "© OpenStreetMap contributors"
OSM_LICENSE = "ODbL 1.0"
OSM_COPYRIGHT_URL = "https://www.openstreetmap.org/copyright"
DATASET_INDEX_SCHEMA = "mountain-osm-dataset-index/v1"
NLSC_TILE_INDEX_SCHEMA = "mountain-nlsc-tile-index/v2"
NLSC_TILE_DATASET_PROFILE = "nlsc-tile-v3-smart-semantic-relations-foot-retained"
TILE_QA_SCHEMA = "mountain-osm-tile-qa/v2"
NLSC_TILE_SIZE_DEG = 0.125
NLSC_TILE_ID_RE = re.compile(r"(?P<parent>\d{5})(?P<quad>SW|SE|NW|NE)", re.IGNORECASE)

EXPECTED_LAYERS = {
    "highway": "osm_highway_raw.geojson",
    "waterway": "osm_waterway_raw.geojson",
    "water_area": "osm_water_area_raw.geojson",
    "wetland": "osm_wetland_raw.geojson",
    "cliff": "osm_cliff_raw.geojson",
    "scree": "osm_scree_raw.geojson",
    "bare_rock": "osm_bare_rock_raw.geojson",
    "landslide": "osm_landslide_raw.geojson",
    "safety_rope": "osm_safety_rope_raw.geojson",
    "assisted_trail": "osm_assisted_trail_raw.geojson",
    "handrail": "osm_handrail_raw.geojson",
    "rungs": "osm_rungs_raw.geojson",
    "ladder": "osm_ladder_raw.geojson",
    "via_ferrata": "osm_via_ferrata_raw.geojson",
    "street_lamp": "osm_street_lamp_raw.geojson",
    "trailhead": "osm_trailhead_raw.geojson",
    "peak": "osm_peak_raw.geojson",
    "guidepost": "osm_guidepost_raw.geojson",
    "shelter": "osm_shelter_raw.geojson",
    "alpine_hut": "osm_alpine_hut_raw.geojson",
    "wilderness_hut": "osm_wilderness_hut_raw.geojson",
    "bench": "osm_bench_raw.geojson",
    "picnic_table": "osm_picnic_table_raw.geojson",
    "picnic_site": "osm_picnic_site_raw.geojson",
    "drinking_water": "osm_drinking_water_raw.geojson",
    "toilets": "osm_toilets_raw.geojson",
    "visitor_centre": "osm_visitor_centre_raw.geojson",
    "information_office": "osm_information_office_raw.geojson",
    "viewpoint": "osm_viewpoint_raw.geojson",
    "tourism": "osm_tourism_raw.geojson",
    "waterfall": "osm_waterfall_raw.geojson",
    "barrier": "osm_barrier_raw.geojson",
    "emergency": "osm_emergency_raw.geojson",
    "man_made": "osm_man_made_raw.geojson",
    "protected_area": "osm_protected_area_raw.geojson",
    "national_park": "osm_national_park_raw.geojson",
    "route_information": "osm_route_information_raw.geojson",
    "route_marker": "osm_route_marker_raw.geojson",
    "board_map": "osm_board_map_raw.geojson",
    "guide_map_attraction": "osm_guide_map_attraction_raw.geojson",
    "warning_notice": "osm_warning_notice_raw.geojson",
    "defibrillator": "osm_defibrillator_raw.geojson",
    "fire_hydrant": "osm_fire_hydrant_raw.geojson",
    "milestone": "osm_milestone_raw.geojson",
    "survey_point": "osm_survey_point_raw.geojson",
    "summit_board": "osm_summit_board_raw.geojson",
    "monitoring_station": "osm_monitoring_station_raw.geojson",
    "obstacle": "osm_obstacle_raw.geojson",
    "overgrown": "osm_overgrown_raw.geojson",
    "hazard": "osm_hazard_raw.geojson",
    "hiking_route": "osm_hiking_route_raw.geojson",
    "foot_route": "osm_foot_route_raw.geojson",
    "spring": "osm_spring_raw.geojson",
    "hot_spring": "osm_hot_spring_raw.geojson",
    "volcano": "osm_volcano_raw.geojson",
    "generic_context": "osm_generic_context_raw.geojson",
}

PROTECT_COLS = [
    "osm_type",
    "osm_id",
    "name",
    "highway",
    "highway_norm",
    "route_class_raw",
    "highway_family",
    "walk_relevance",
    "route_role",
    "matching_semantic_score",
    "foot",
    "access",
    "bicycle",
    "horse",
    "motor_vehicle",
    "vehicle",
    "surface",
    "tracktype",
    "smoothness",
    "sac_scale",
    "trail_visibility",
    "trail_difficulty_hint",
    "bridge",
    "ford",
    "has_bridge",
    "has_ford",
    "incline",
    "incline_raw",
    "lit",
    "natural",
    "waterway",
    "water",
    "wetland",
    "seasonal",
    "intermittent",
    "safety_rope",
    "safety_rope_side",
    "assisted_trail",
    "handrail",
    "handrail:left",
    "handrail:right",
    "rungs",
    "man_made",
    "via_ferrata_scale",
    "height",
    "length",
    "step_count",
    "step_count_raw",
    "is_steps",
    "layer",
    "layer_raw",
    "layer_norm",
    "level",
    "tunnel",
    "covered",
    "embankment",
    "cutting",
    "location",
    "vertical_context",
    "base_difficulty_source",
    "ele",
    "ref",
    "operator",
    "information",
    "distance",
    "network",
    "informal",
    "wikidata",
    "wikipedia",
    "tourism",
    "attraction",
    "description",
    "image",
    "mapillary",
    "url",
    "amenity",
    "leisure",
    "building",
    "shelter_type",
    "drinking_water",
    "toilets",
    "toilets:wheelchair",
    "wheelchair",
    "opening_hours",
    "website",
    "phone",
    "email",
    "barrier",
    "locked",
    "emergency",
    "board_type",
    "board:title",
    "map_type",
    "direction_east",
    "direction_west",
    "direction_north",
    "direction_south",
    "defibrillator:location:zh",
    "hear_aed:defibrillator:location",
    "hear_aed:site:name",
    "hear_aed:site:description",
    "survey_point",
    "monitoring:gps",
    "monitoring:weather",
    "mtb:scale",
    "mtb:scale:uphill",
    "trailblazed",
    "trailblazed:visibility",
    "trail_marking",
    "osmc:symbol",
    "route",
    "hazard",
    "obstacle",
    "overgrown",
    "condition",
    "check_date",
    "fixme",
    "disused",
    "abandoned",
    "type",
    "route_ref",
    "network:type",
    "symbol",
    "colour",
    "material",
    "width",
    "est_width",
    "access:conditional",
    "foot:conditional",
    "seasonal:conditional",
    "fee",
    "boundary",
    "protect_class",
    "protection_title",
    "related_law",
    "ownership",
    "designation",
    "scenic_source_hint",
    "member_way_name",
    "route_relation_id",
    "route_relation_route",
    "route_relation_name",
    "route_relation_ref",
    "route_relation_network",
    "route_relation_osmc_symbol",
    "route_relation_symbol",
    "route_relation_colour",
    "route_relation_member_role",
    "route_relation_member_sequence",
    "geometry",
    "route_id",
    "osm_dataset_id",
    "source_name",
    "source_kind",
    "source_url",
    "source_dataset_id",
    "source_sha256",
    "osm_base_timestamp",
    "coverage_status",
    "attribution",
    "license",
    "fetched_at",
    "pipeline_stage",
    "script_version",
    "script_status",
]

SEMANTIC_SCORE_MAP = {
    "path": 1.00,
    "steps": 0.95,
    "footway": 0.85,
    "track": 0.75,
    "pedestrian": 0.60,
    "service": 0.45,
    "unclassified": 0.40,
    "residential": 0.35,
    "living_street": 0.35,
    "road": 0.30,
    "tertiary": 0.25,
    "tertiary_link": 0.20,
    "ladder": 0.70,
    "via_ferrata": 0.80,
}



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "IA1 OSM source manager: GPX-first NLSC theoretical tile authority, local legacy/PBF coverage QA, "
            "reusable tile cache, and explicit governed network fallback."
        )
    )
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--activity-fp", required=True)
    parser.add_argument("--out-dir", default=None)

    # Analysis/query corridor. Keep this compatible with the existing IA1/IB0 pipeline.
    parser.add_argument("--buffer-m", type=float, default=700.0)
    parser.add_argument(
        "--buffer-simplify-m",
        type=float,
        default=15.0,
        help="Simplify the metric route-buffer polygon before querying/parsing.",
    )

    # Source selection.
    parser.add_argument(
        "--source",
        choices=["auto", "local", "overpass"],
        default="auto",
        help=(
            "auto: prefer data/ local PBF and only fall back to Overpass; "
            "local: never use network Overpass; overpass: explicitly use Overpass."
        ),
    )
    parser.add_argument(
        "--data-dir",
        default="data/osm",
        help="Shared OSM data root. Relative paths are resolved under PROJECT_ROOT.",
    )
    parser.add_argument(
        "--dataset-index",
        default=None,
        help="Dataset index JSON. Default: <data-dir>/osm_dataset_index.json",
    )
    parser.add_argument(
        "--pbf-fp",
        action="append",
        default=None,
        help="Explicit local parent .osm.pbf candidate. Can be repeated.",
    )
    # NLSC theoretical tile authority. The raw NLSC geometry is used only to locate a tile on the
    # 0.125-degree grid; the actual feature bounds are never used as the authoritative tile extent.
    parser.add_argument(
        "--nlsc-raw-dir",
        default="nlsc_raw",
        help="NLSC raw root used to discover tile IDs and infer their theoretical 0.125-degree grid cells.",
    )
    parser.add_argument(
        "--nlsc-tile-index",
        default=None,
        help="Cached NLSC theoretical tile index CSV. Default: <data-dir>/tile_index/nlsc_tile_index.csv",
    )
    parser.add_argument(
        "--rebuild-nlsc-tile-index",
        action="store_true",
        help="Rebuild the cached NLSC theoretical tile index from --nlsc-raw-dir.",
    )
    parser.add_argument(
        "--tile-fetch-buffer-m",
        type=float,
        default=500.0,
        help="Metric safety buffer around the union of intersecting NLSC theoretical tiles.",
    )
    parser.add_argument(
        "--dataset-buffer-m",
        type=float,
        default=20000.0,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--dataset-buffer-simplify-m",
        type=float,
        default=250.0,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--allow-unvalidated-shared",
        action="store_true",
        help=(
            "Allow a route-area PBF created for another case even if its basic connectivity QA is not PASS. "
            "Default is conservative: cross-case route-area reuse requires PASS."
        ),
    )
    parser.add_argument(
        "--coverage-anchor-count",
        type=int,
        default=9,
        help=(
            "Number of distance-based GPX route anchor points used to prefilter local OSM datasets before "
            "the final full-buffer coverage test. Cardinal extreme track points are added automatically."
        ),
    )

    # Osmium/local PBF tooling.
    parser.add_argument("--osmium-bin", default="osmium")
    parser.add_argument(
        "--osmium-extract-strategy",
        choices=["complete_ways", "smart"],
        default="smart",
        help="Tile extraction strategy. v1.5.3 defaults to smart for semantic relation completeness.",
    )
    parser.add_argument(
        "--relation-completion-profile",
        choices=["semantic", "multipolygon", "all", "none"],
        default="semantic",
        help=(
            "Smart-extract relation completion profile. semantic completes multipolygon plus hiking/foot route and "
            "protected-area boundary relations; multipolygon completes only multipolygons; all completes all relation "
            "types and can greatly enlarge a tile; none keeps smart defaults only."
        ),
    )
    parser.add_argument(
        "--write-tile-full-highway-geojson",
        action="store_true",
        help=(
            "Optional diagnostic export of all highway ways in the selected TILE_FULL semantic PBF plus a full-tile "
            "highway QA HTML map. This can be large; the authoritative TILE_FULL data remains the PBF even when off."
        ),
    )

    parser.add_argument(
        "--sync-taiwan-pbf",
        action="store_true",
        help="Explicitly refresh/download a Geofabrik Taiwan snapshot before source selection.",
    )
    parser.add_argument("--geofabrik-url", default=DEFAULT_GEOFABRIK_TAIWAN_URL)
    parser.add_argument(
        "--sync-max-age-days",
        type=float,
        default=7.0,
        help="When --sync-taiwan-pbf is set, keep a recent local Taiwan snapshot until this age.",
    )
    parser.add_argument("--download-timeout", type=int, default=1800)

    # Overpass: small/occasional fallback only.
    parser.add_argument(
        "--overpass-url",
        action="append",
        default=None,
        help=(
            "Overpass base URL, e.g. https://overpass-api.de/api. Can be repeated for explicitly configured "
            "fallback endpoints. No mirror list is hard-coded."
        ),
    )
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--contact",
        default=os.environ.get("OUTDOOR_EDGE_OSM_CONTACT"),
        help=(
            "Valid project contact email or URL for network requests. "
            "Can also be set with OUTDOOR_EDGE_OSM_CONTACT. Required before Overpass is used."
        ),
    )
    parser.add_argument(
        "--user-agent",
        default=None,
        help="Full User-Agent override. Placeholder contact strings are rejected for Overpass.",
    )
    parser.add_argument("--retry", type=int, default=2, help="Retries per Overpass endpoint after first attempt.")
    parser.add_argument("--sleep-sec", type=float, default=5.0, help="Base backoff for 5xx/network errors.")
    parser.add_argument(
        "--rate-limit-wait-sec",
        type=float,
        default=30.0,
        help="Minimum wait for HTTP 429/406. Must be >=30 for public Overpass use.",
    )
    parser.add_argument("--max-backoff-sec", type=float, default=120.0)
    parser.add_argument("--max-status-wait-sec", type=float, default=300.0)
    parser.add_argument(
        "--no-overpass-rate-limit",
        action="store_true",
        help="Skip bounded /status preflight. Sequential execution and HTTP backoff remain enforced.",
    )
    parser.add_argument(
        "--overpass-lock-file",
        default=None,
        help="Single-process lock path. Default: <data-dir>/.overpass.lock",
    )
    parser.add_argument(
        "--allow-overpass-fallback",
        action="store_true",
        help=(
            "Explicitly allow --source auto to fall back to public Overpass when no local source covers the route. "
            "Default v1.5.4 behavior is offline/local-first and does not send network requests."
        ),
    )
    parser.add_argument(
        "--no-overpass-fallback",
        action="store_true",
        help="Deprecated compatibility flag. v1.5.4 already disables auto Overpass fallback by default.",
    )
    parser.add_argument(
        "--legacy-output-root",
        action="append",
        default=None,
        help=(
            "Legacy IA1 output root to scan for osm_raw_fetch_manifest.csv bundles. Can be repeated. "
            "Default: osm_raw_output and osm_raw_output_v1_1."
        ),
    )

    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument(
        "--force-refresh-reason",
        default=None,
        help="Required whenever --force-refresh is used; recorded in manifests for auditability.",
    )
    parser.add_argument(
        "--tag-profile",
        choices=["core", "pipeline"],
        default="pipeline",
        help="core fetches only highway; pipeline includes route/hydro/terrain/technical/POI context.",
    )
    parser.add_argument("--no-map", action="store_true")

    # Basic connectivity QA for shared route-area reuse. This QA never edits OSM geometry.
    parser.add_argument("--qa-route-sample-m", type=float, default=50.0)
    parser.add_argument("--qa-route-max-distance-m", type=float, default=80.0)
    parser.add_argument("--qa-route-near-ratio", type=float, default=0.90)
    parser.add_argument("--qa-node-snap-m", type=float, default=5.0)

    args = parser.parse_args()
    if args.rate_limit_wait_sec < 30:
        parser.error("--rate-limit-wait-sec must be >= 30 seconds.")
    if args.retry < 0:
        parser.error("--retry must be >= 0.")
    if args.force_refresh and not (args.force_refresh_reason or "").strip():
        parser.error("--force-refresh requires --force-refresh-reason <reason>.")
    if args.buffer_m <= 0 or args.tile_fetch_buffer_m < 0:
        parser.error("--buffer-m must be > 0 and --tile-fetch-buffer-m must be >= 0.")
    if args.coverage_anchor_count < 3:
        parser.error("--coverage-anchor-count must be >= 3.")
    return args


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def portable_path(path: Path) -> str:
    path = path.resolve()
    try:
        return str(path.relative_to(PROJECT_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def parse_gpx_line(gpx_fp: Path) -> LineString:
    tree = ET.parse(gpx_fp)
    root = tree.getroot()
    ns = {}
    if root.tag.startswith("{"):
        ns = {"gpx": root.tag.split("}")[0].strip("{")}
        trkpt_xpath = ".//gpx:trkpt"
    else:
        trkpt_xpath = ".//trkpt"

    coords = []
    for trkpt in root.findall(trkpt_xpath, ns):
        coords.append((float(trkpt.attrib["lon"]), float(trkpt.attrib["lat"])))

    deduped = []
    for coord in coords:
        if not deduped or coord != deduped[-1]:
            deduped.append(coord)

    if len(deduped) < 2:
        raise ValueError(f"GPX has too few track points: {gpx_fp}")
    return LineString(deduped)


def build_gpx_route_probe(line: LineString, anchor_count: int = 9) -> dict:
    """Build a small, auditable GPX fingerprint before touching the OSM dataset index.

    The anchor points are only a conservative *prefilter*. A dataset is accepted as FULL
    only after the complete analysis/dataset buffer polygon is covered. This avoids the
    unsafe shortcut of deciding coverage from only start/end/midpoint coordinates.
    """
    route_gdf = gpd.GeoDataFrame([{"geometry": line}], geometry="geometry", crs="EPSG:4326")
    metric_crs = route_gdf.estimate_utm_crs()
    metric_line = route_gdf.to_crs(metric_crs).geometry.iloc[0]
    route_length_m = float(metric_line.length)

    route_samples_metric = []
    for i in range(anchor_count):
        fraction = i / (anchor_count - 1)
        route_samples_metric.append((fraction, metric_line.interpolate(route_length_m * fraction)))

    route_samples_wgs = gpd.GeoSeries(
        [pt for _, pt in route_samples_metric], crs=metric_crs
    ).to_crs("EPSG:4326")

    anchors = []
    for (fraction, _), pt in zip(route_samples_metric, route_samples_wgs):
        anchors.append(
            {
                "label": f"route_{fraction * 100:.1f}pct",
                "kind": "distance_sample",
                "fraction": round(float(fraction), 6),
                "lon": float(pt.x),
                "lat": float(pt.y),
            }
        )

    coords = list(line.coords)
    extremes = {
        "westmost": min(coords, key=lambda c: c[0]),
        "eastmost": max(coords, key=lambda c: c[0]),
        "southmost": min(coords, key=lambda c: c[1]),
        "northmost": max(coords, key=lambda c: c[1]),
    }
    for label, (lon, lat) in extremes.items():
        anchors.append(
            {
                "label": label,
                "kind": "track_extreme",
                "fraction": None,
                "lon": float(lon),
                "lat": float(lat),
            }
        )

    # Deduplicate overlapping anchors (common for out-and-back routes where start=end).
    deduped = []
    seen = set()
    for anchor in anchors:
        key = (round(anchor["lon"], 7), round(anchor["lat"], 7))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(anchor)

    return {
        "track_vertex_count": len(coords),
        "route_length_m": route_length_m,
        "route_bbox": list(geometry_bbox(line)),
        "anchors": deduped,
    }


def probe_anchor_points(probe: dict) -> list[Point]:
    return [Point(float(a["lon"]), float(a["lat"])) for a in probe.get("anchors", [])]


def write_gpx_route_probe(
    probe: dict,
    out_fp: Path,
    *,
    case_id: str,
    activity_fp: Path,
    analysis_geometry,
    dataset_geometry,
    nlsc_tiles: list[str] | None = None,
    nlsc_tile_theoretical_geometry=None,
    tile_fetch_buffer_m: float | None = None,
) -> None:
    payload = {
        "schema": "mountain-gpx-route-probe/v1",
        "case_id": case_id,
        "activity_fp": portable_path(activity_fp),
        "generated_at": utc_now_iso(),
        **probe,
        "analysis_bbox": list(geometry_bbox(analysis_geometry)),
        "dataset_search_bbox": list(geometry_bbox(dataset_geometry)),
        "nlsc_tiles": list(nlsc_tiles or []),
        "nlsc_tile_authority": "NLSC_THEORETICAL_GRID" if nlsc_tiles else None,
        "nlsc_tile_theoretical_bbox": (
            list(geometry_bbox(nlsc_tile_theoretical_geometry))
            if nlsc_tile_theoretical_geometry is not None else None
        ),
        "tile_fetch_buffer_m": tile_fetch_buffer_m,
        "coverage_decision_rule": (
            "GPX anchors are a prefilter; ANALYSIS_FULL requires full GPX analysis buffer coverage; "
            "TILE_FULL requires full NLSC theoretical tile union plus metric fetch buffer coverage"
        ),
        "script_version": VERSION,
    }
    atomic_write_json(out_fp, payload)


def print_gpx_route_probe(probe: dict) -> None:
    anchors = probe.get("anchors", [])
    print("GPX ROUTE PROBE")
    print("  track vertices:", probe.get("track_vertex_count"))
    print("  route length km:", round(float(probe.get("route_length_m", 0.0)) / 1000.0, 3))
    print("  route bbox west,south,east,north:", tuple(probe.get("route_bbox", [])))
    print("  coverage anchors:", len(anchors))
    for anchor in anchors:
        print(
            f"    {anchor['label']}: "
            f"lon={anchor['lon']:.7f}, lat={anchor['lat']:.7f}"
        )


def route_buffer_geometry(line: LineString, buffer_m: float, simplify_m: float = 15.0):
    route_gdf = gpd.GeoDataFrame([{"geometry": line}], geometry="geometry", crs="EPSG:4326")
    metric_crs = route_gdf.estimate_utm_crs()
    buffered = route_gdf.to_crs(metric_crs).geometry.iloc[0].buffer(buffer_m)
    if simplify_m and simplify_m > 0:
        buffered = buffered.simplify(simplify_m, preserve_topology=True)
    return gpd.GeoSeries([buffered], crs=metric_crs).to_crs("EPSG:4326").iloc[0]


def geometry_bbox(geometry) -> tuple[float, float, float, float]:
    west, south, east, north = geometry.bounds
    return (float(west), float(south), float(east), float(north))


def route_buffer_bbox(line: LineString, buffer_m: float) -> tuple[float, float, float, float]:
    return geometry_bbox(route_buffer_geometry(line, buffer_m))



def metric_buffer_geometry(geometry, buffer_m: float, simplify_m: float = 0.0):
    """Buffer arbitrary EPSG:4326 geometry in a local metric CRS, then return EPSG:4326."""
    gdf = gpd.GeoDataFrame([{"geometry": geometry}], geometry="geometry", crs="EPSG:4326")
    metric_crs = gdf.estimate_utm_crs()
    buffered = gdf.to_crs(metric_crs).geometry.iloc[0].buffer(buffer_m)
    if simplify_m and simplify_m > 0:
        buffered = buffered.simplify(simplify_m, preserve_topology=True)
    return gpd.GeoSeries([buffered], crs=metric_crs).to_crs("EPSG:4326").iloc[0]


def _extract_nlsc_tile_id(text: str) -> str | None:
    match = NLSC_TILE_ID_RE.search(str(text))
    if not match:
        return None
    return f"{match.group('parent')}{match.group('quad').upper()}"


def _snap_point_to_theoretical_tile(lon: float, lat: float) -> tuple[float, float, float, float]:
    """Return the theoretical 0.125deg cell containing a representative point.

    Actual NLSC feature bounds are deliberately NOT used as tile extents. A representative
    point only locates the tile on the fixed theoretical grid.
    """
    eps = 1e-10
    west = math.floor((float(lon) + eps) / NLSC_TILE_SIZE_DEG) * NLSC_TILE_SIZE_DEG
    south = math.floor((float(lat) + eps) / NLSC_TILE_SIZE_DEG) * NLSC_TILE_SIZE_DEG
    west = round(west, 9)
    south = round(south, 9)
    return (west, south, round(west + NLSC_TILE_SIZE_DEG, 9), round(south + NLSC_TILE_SIZE_DEG, 9))


def _parent_origin_from_quadrant(tile_id: str, cell_bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    quad = tile_id[-2:].upper()
    west, south, _east, _north = cell_bbox
    parent_west = west - (NLSC_TILE_SIZE_DEG if quad in {"SE", "NE"} else 0.0)
    parent_south = south - (NLSC_TILE_SIZE_DEG if quad in {"NW", "NE"} else 0.0)
    return (round(parent_west, 9), round(parent_south, 9))


def _quadrant_bbox(parent_west: float, parent_south: float, quad: str) -> tuple[float, float, float, float]:
    quad = quad.upper()
    west = parent_west + (NLSC_TILE_SIZE_DEG if quad in {"SE", "NE"} else 0.0)
    south = parent_south + (NLSC_TILE_SIZE_DEG if quad in {"NW", "NE"} else 0.0)
    return (
        round(west, 9),
        round(south, 9),
        round(west + NLSC_TILE_SIZE_DEG, 9),
        round(south + NLSC_TILE_SIZE_DEG, 9),
    )


def _vector_reference_candidates(tile_root: Path) -> list[Path]:
    preferred = []
    for name in ["ContourL.shp", "contourl.shp"]:
        preferred.extend(tile_root.rglob(name))
    others = []
    for pattern in ["*.shp", "*.gpkg", "*.geojson"]:
        others.extend(tile_root.rglob(pattern))
    seen = set()
    ordered = []
    for fp in preferred + others:
        key = str(fp.resolve())
        if key in seen:
            continue
        seen.add(key)
        ordered.append(fp)
    return ordered


def _representative_point_from_vector(fp: Path) -> tuple[float, float] | None:
    try:
        gdf = gpd.read_file(fp)
        if gdf.empty or gdf.geometry is None:
            return None
        gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
        if gdf.empty:
            return None
        if gdf.crs is None:
            # User-verified NLSC raw batches are EPSG:4326. Refuse to guess a different CRS.
            gdf = gdf.set_crs("EPSG:4326")
        elif gdf.crs.to_string().upper() != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        minx, miny, maxx, maxy = map(float, gdf.total_bounds)
        if not all(math.isfinite(v) for v in [minx, miny, maxx, maxy]):
            return None
        return ((minx + maxx) / 2.0, (miny + maxy) / 2.0)
    except Exception:
        return None


def build_nlsc_tile_index(nlsc_raw_dir: Path, index_fp: Path) -> pd.DataFrame:
    """Build a cached tile-ID -> theoretical bbox index from local NLSC raw assets.

    Safety rule: actual feature bounds are only used to obtain one representative point and
    locate the tile on the fixed 0.125deg grid. The authoritative bbox is reconstructed from
    the theoretical grid and the SW/SE/NW/NE quadrant, never from shapefile feature extent.
    """
    if not nlsc_raw_dir.exists():
        raise RuntimeError(f"NLSC raw directory not found: {nlsc_raw_dir}")

    tile_roots: dict[str, Path] = {}
    for path in nlsc_raw_dir.rglob("*"):
        tile_id = _extract_nlsc_tile_id(path.name)
        if tile_id:
            current = tile_roots.get(tile_id)
            if current is None or len(path.parts) < len(current.parts):
                tile_roots[tile_id] = path if path.is_dir() else path.parent

    if not tile_roots:
        raise RuntimeError(
            f"No NLSC tile IDs like 97233SW were found under {nlsc_raw_dir}. "
            "IA1 will not guess tile numbering without a local tile authority index."
        )

    parent_origins: dict[str, list[tuple[float, float, str, str]]] = {}
    tile_reference: dict[str, str] = {}
    for tile_id, tile_root in sorted(tile_roots.items()):
        representative = None
        reference_fp = None
        for fp in _vector_reference_candidates(tile_root):
            representative = _representative_point_from_vector(fp)
            if representative is not None:
                reference_fp = fp
                break
        if representative is None:
            continue
        cell_bbox = _snap_point_to_theoretical_tile(*representative)
        parent_origin = _parent_origin_from_quadrant(tile_id, cell_bbox)
        parent = tile_id[:5]
        parent_origins.setdefault(parent, []).append(
            (parent_origin[0], parent_origin[1], tile_id, str(reference_fp) if reference_fp else "")
        )
        if reference_fp:
            tile_reference[tile_id] = portable_path(reference_fp)

    resolved_parent: dict[str, tuple[float, float]] = {}
    parent_status: dict[str, str] = {}
    parent_issue: dict[str, str | None] = {}
    conflicts = []
    for parent, candidates in parent_origins.items():
        counts: dict[tuple[float, float], int] = {}
        for west, south, _tile_id, _ref in candidates:
            counts[(west, south)] = counts.get((west, south), 0) + 1
        best = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        resolved_parent[parent] = best
        if len(counts) > 1:
            conflicts.append((parent, counts))
            parent_status[parent] = "CONFLICT"
            parent_issue[parent] = "NLSC_PARENT_ORIGIN_CONFLICT: " + json.dumps(
                {f"{k[0]:.6f},{k[1]:.6f}": v for k, v in counts.items()},
                ensure_ascii=False,
                sort_keys=True,
            )
        else:
            parent_status[parent] = "VALID"
            parent_issue[parent] = None

    if conflicts:
        for parent, counts in conflicts:
            print(
                f"WARNING: NLSC parent tile origin conflict {parent}: {counts}; "
                "records will be indexed for QA but BLOCKED as Tile Authority until resolved."
            )

    rows = []
    unresolved = []
    for tile_id, tile_root in sorted(tile_roots.items()):
        parent = tile_id[:5]
        origin = resolved_parent.get(parent)
        if origin is None:
            unresolved.append(tile_id)
            continue
        bbox = _quadrant_bbox(origin[0], origin[1], tile_id[-2:])
        rows.append(
            {
                "schema": NLSC_TILE_INDEX_SCHEMA,
                "tile_id": tile_id,
                "parent_tile": parent,
                "quadrant": tile_id[-2:].upper(),
                "min_lon": bbox[0],
                "min_lat": bbox[1],
                "max_lon": bbox[2],
                "max_lat": bbox[3],
                "tile_size_deg": NLSC_TILE_SIZE_DEG,
                "authority": "NLSC_THEORETICAL_GRID",
                "authority_status": parent_status.get(parent, "UNRESOLVED"),
                "authority_issue": parent_issue.get(parent),
                "inference": "representative_point_snapped_to_0.125deg_grid_then_quadrant_reconstruction",
                "reference_file": tile_reference.get(tile_id),
                "tile_root": portable_path(tile_root),
            }
        )

    if not rows:
        raise RuntimeError(
            f"NLSC tile IDs were found under {nlsc_raw_dir}, but no readable vector layer could anchor the theoretical grid."
        )
    if unresolved:
        print("WARNING: NLSC tile IDs unresolved because no sibling in the same parent had readable geometry:", unresolved)

    df = pd.DataFrame(rows).drop_duplicates(subset=["tile_id"], keep="first").sort_values("tile_id")
    index_fp.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(index_fp, index=False, encoding="utf-8-sig")
    print(f"NLSC theoretical tile index written: {index_fp} tiles={len(df)}")
    return df


def load_nlsc_tile_index(nlsc_raw_dir: Path, index_fp: Path, rebuild: bool = False) -> pd.DataFrame:
    required_v2 = {"tile_id", "min_lon", "min_lat", "max_lon", "max_lat", "authority_status"}
    if index_fp.exists() and not rebuild:
        df = pd.read_csv(index_fp, dtype={"tile_id": "string", "parent_tile": "string", "quadrant": "string"})
        # v1.5.3 schema adds authority_status so old majority-consensus indexes are never silently trusted.
        if not required_v2.issubset(df.columns) or ("schema" in df.columns and not df["schema"].eq(NLSC_TILE_INDEX_SCHEMA).all()):
            print(f"NLSC tile index schema/status is legacy; rebuilding for conflict-safe authority: {index_fp}")
            df = build_nlsc_tile_index(nlsc_raw_dir, index_fp)
    else:
        df = build_nlsc_tile_index(nlsc_raw_dir, index_fp)
    missing = required_v2 - set(df.columns)
    if missing:
        raise RuntimeError(f"Invalid NLSC tile index {index_fp}; missing columns: {sorted(missing)}")
    for col in ["min_lon", "min_lat", "max_lon", "max_lat"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["min_lon", "min_lat", "max_lon", "max_lat"]).copy()
    df["tile_id"] = df["tile_id"].astype("string").str.upper()
    df["authority_status"] = df["authority_status"].fillna("UNRESOLVED").astype("string").str.upper()
    return df


def find_nlsc_tiles_for_route_bbox(route_bbox: tuple[float, float, float, float], tile_index: pd.DataFrame) -> list[dict]:
    route_box = box(*route_bbox)
    matches = []
    blocked = []
    for row in tile_index.itertuples(index=False):
        tile_bbox = (float(row.min_lon), float(row.min_lat), float(row.max_lon), float(row.max_lat))
        tile_geom = box(*tile_bbox)
        if tile_geom.intersects(route_box):
            status = str(getattr(row, "authority_status", "UNRESOLVED")).upper()
            issue = getattr(row, "authority_issue", None)
            item = {
                "tile_id": str(row.tile_id),
                "bbox": tile_bbox,
                "geometry": tile_geom,
                "authority_status": status,
                "authority_issue": None if pd.isna(issue) else str(issue),
            }
            if status != "VALID":
                blocked.append(item)
            else:
                matches.append(item)
    if blocked:
        details = "; ".join(
            f"{m['tile_id']} status={m['authority_status']} issue={m.get('authority_issue')}" for m in blocked
        )
        raise RuntimeError(
            "NLSC_TILE_AUTHORITY_BLOCKED: GPX intersects one or more NLSC tile records whose parent origin is "
            f"not validated. Resolve/rebuild the authority index before any OSM download/extraction. {details}"
        )
    matches.sort(key=lambda item: item["tile_id"])
    if not matches:
        raise RuntimeError(
            f"NLSC_TILE_INDEX_COVERAGE_GAP: route bbox {route_bbox} does not intersect any VALID indexed NLSC theoretical tile."
        )
    union = unary_union([m["geometry"] for m in matches])
    if not union.covers(route_box):
        raise RuntimeError(
            "NLSC_TILE_INDEX_COVERAGE_GAP: intersecting VALID tile records do not fully cover the GPX bbox. "
            "Rebuild/extend the NLSC tile index before downloading OSM."
        )
    return matches


def build_nlsc_tile_geometry(tile_matches: list[dict], buffer_m: float) -> tuple[object, object]:
    theoretical_union = unary_union([item["geometry"] for item in tile_matches])
    fetch_geometry = metric_buffer_geometry(theoretical_union, buffer_m) if buffer_m > 0 else theoretical_union
    return theoretical_union, fetch_geometry


def default_legacy_roots(args: argparse.Namespace) -> list[Path]:
    if args.legacy_output_root:
        return [resolve_path(x) for x in args.legacy_output_root]
    return [PROJECT_ROOT / "osm_raw_output", PROJECT_ROOT / "osm_raw_output_v1_1"]


def _legacy_manifest_row(manifest_fp: Path) -> dict | None:
    try:
        df = pd.read_csv(manifest_fp)
    except Exception as exc:
        print(f"WARNING: invalid legacy manifest skipped {manifest_fp}: {exc}")
        return None
    if df.empty:
        return None
    row = df.iloc[0].to_dict()
    try:
        bbox = (
            float(row.get("bbox_west")),
            float(row.get("bbox_south")),
            float(row.get("bbox_east")),
            float(row.get("bbox_north")),
        )
    except Exception:
        return None
    if not all(math.isfinite(v) for v in bbox):
        return None
    return {"row": row, "bbox": bbox}


def discover_legacy_bundles(args: argparse.Namespace, *, current_out_dir: Path | None = None) -> list[dict]:
    bundles = []
    seen_manifest = set()
    for root_rank, root in enumerate(default_legacy_roots(args)):
        if not root.exists():
            continue
        for manifest_fp in root.rglob("osm_raw_fetch_manifest.csv"):
            key = str(manifest_fp.resolve())
            if key in seen_manifest:
                continue
            seen_manifest.add(key)
            bundle_dir = manifest_fp.parent
            if current_out_dir is not None and bundle_dir.resolve() == current_out_dir.resolve():
                # Current case output may be partial/stale while IA1 is running. It is examined separately only via history.
                pass
            parsed = _legacy_manifest_row(manifest_fp)
            if parsed is None:
                continue
            row = parsed["row"]
            route_id = str(row.get("route_id") or "").strip()
            dataset_id = str(row.get("osm_dataset_id") or "").strip()
            folder_name = bundle_dir.name
            identity_match = (not route_id) or folder_name == route_id or folder_name.startswith(route_id + "_")
            archived = "_archived_before_" in str(bundle_dir).lower()
            core_fp = bundle_dir / EXPECTED_LAYERS["highway"]
            if not core_fp.exists():
                continue
            bundles.append(
                {
                    "kind": "legacy_bundle",
                    "bundle_dir": bundle_dir,
                    "manifest_fp": manifest_fp,
                    "folder_name": folder_name,
                    "route_id": route_id,
                    "dataset_id": dataset_id or route_id or folder_name,
                    "coverage_bbox": parsed["bbox"],
                    "coverage_geometry": box(*parsed["bbox"]),
                    "buffer_m": row.get("buffer_m"),
                    "fetched_at": row.get("fetched_at"),
                    "script_version": row.get("script_version"),
                    "identity_match": bool(identity_match),
                    "identity_status": "OK" if identity_match else "DATASET_IDENTITY_MISMATCH",
                    "archived": archived,
                    "root_rank": root_rank,
                }
            )
    return bundles


def classify_legacy_coverage(bundle: dict, analysis_geometry, tile_fetch_geometry) -> dict:
    cov = bundle.get("coverage_geometry")
    return {
        **bundle,
        "analysis_coverage": coverage_state(analysis_geometry, cov),
        "tile_coverage": coverage_state(tile_fetch_geometry, cov),
    }


def choose_legacy_bundle(bundles: list[dict], analysis_geometry, tile_fetch_geometry) -> tuple[dict | None, list[dict]]:
    classified = [classify_legacy_coverage(b, analysis_geometry, tile_fetch_geometry) for b in bundles]
    eligible = [
        b for b in classified
        if b["analysis_coverage"] == "FULL" and b.get("identity_match") and not b.get("archived")
    ]
    if not eligible:
        eligible = [
            b for b in classified
            if b["analysis_coverage"] == "FULL" and b.get("identity_match")
        ]
    if not eligible:
        return None, classified
    eligible.sort(
        key=lambda b: (
            0 if b.get("tile_coverage") == "FULL" else 1,
            0 if not b.get("archived") else 1,
            b.get("root_rank", 99),
            float(b["coverage_geometry"].area),
            str(b.get("fetched_at") or ""),
        )
    )
    return eligible[0], classified


def print_local_coverage_report(
    *,
    tile_ids: list[str],
    tile_theoretical_geometry,
    tile_fetch_geometry,
    indexed_analysis: str,
    indexed_tile: str,
    legacy_rows: list[dict],
) -> None:
    print("NLSC TILE AUTHORITY")
    print("  tiles:", ", ".join(tile_ids))
    print("  theoretical bbox west,south,east,north:", geometry_bbox(tile_theoretical_geometry))
    print("  OSM fetch bbox west,south,east,north:", geometry_bbox(tile_fetch_geometry))
    print("LOCAL COVERAGE QA")
    print("  indexed analysis coverage:", indexed_analysis)
    print("  indexed tile coverage:", indexed_tile)
    relevant = [r for r in legacy_rows if r.get("analysis_coverage") != "NONE" or r.get("tile_coverage") != "NONE"]
    if not relevant:
        print("  legacy IA1 bundles: NONE")
        return
    for row in sorted(relevant, key=lambda r: (r.get("analysis_coverage") != "FULL", r.get("archived"), r.get("folder_name"))):
        print(
            "  legacy:",
            row.get("folder_name"),
            f"analysis={row.get('analysis_coverage')}",
            f"tile={row.get('tile_coverage')}",
            f"identity={row.get('identity_status')}",
            f"archived={row.get('archived')}",
        )


def load_features_from_legacy_bundle(bundle: dict, query_geometry) -> gpd.GeoDataFrame:
    bundle_dir = Path(bundle["bundle_dir"])
    frames = []
    for _layer_name, filename in EXPECTED_LAYERS.items():
        fp = bundle_dir / filename
        if not fp.exists():
            continue
        try:
            gdf = gpd.read_file(fp)
        except Exception as exc:
            print(f"WARNING: legacy layer skipped {fp}: {exc}")
            continue
        if gdf.empty:
            continue
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")
        elif gdf.crs.to_string().upper() != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        gdf = gdf[gdf.geometry.notna()].copy()
        try:
            gdf = gdf[gdf.geometry.intersects(query_geometry)].copy()
        except Exception:
            pass
        if not gdf.empty:
            frames.append(gdf)
    if not frames:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    combined = pd.concat(frames, ignore_index=True, sort=False)
    gdf = gpd.GeoDataFrame(combined, geometry="geometry", crs="EPSG:4326")
    if {"osm_type", "osm_id"}.issubset(gdf.columns):
        valid_id = gdf["osm_type"].notna() & gdf["osm_id"].notna()
        with_id = gdf[valid_id].drop_duplicates(subset=["osm_type", "osm_id"], keep="first")
        without_id = gdf[~valid_id].copy()
        if not without_id.empty:
            without_id["_geom_key"] = without_id.geometry.apply(lambda geom: geom.wkb_hex if geom is not None else "")
            without_id = without_id.drop_duplicates(subset=["_geom_key"], keep="first").drop(columns=["_geom_key"])
        gdf = gpd.GeoDataFrame(pd.concat([with_id, without_id], ignore_index=True, sort=False), geometry="geometry", crs="EPSG:4326")
    return gdf

def build_user_agent(args: argparse.Namespace, require_contact: bool = False) -> str:
    if args.user_agent:
        ua = args.user_agent.strip()
    elif args.contact:
        ua = f"{PROJECT_USER_AGENT_NAME} (research; contact: {args.contact.strip()})"
    else:
        ua = f"{PROJECT_USER_AGENT_NAME} (local-pbf-pipeline)"

    lowered = ua.lower()
    placeholders = {"please-configure", "example.com", "your-email", "todo-contact", "contact-here"}
    if require_contact and (not args.contact and not args.user_agent):
        raise RuntimeError(
            "Overpass requires identifiable contact information. Provide --contact <email-or-project-url> "
            "or set OUTDOOR_EDGE_OSM_CONTACT."
        )
    if require_contact and any(token in lowered for token in placeholders):
        raise RuntimeError(f"Refusing placeholder User-Agent for Overpass: {ua}")
    if require_contact and args.user_agent and "contact:" not in lowered:
        raise RuntimeError(
            "Custom --user-agent for Overpass must include a 'contact:' field with a real email or project URL."
        )
    return ua


def configure_osmnx(args: argparse.Namespace, user_agent: str) -> None:
    # OSMnx remains the feature parser, but IA1 owns public Overpass retry behavior.
    ox.settings.use_cache = True
    ox.settings.cache_folder = str(PROJECT_ROOT / "osmnx_cache")
    ox.settings.log_console = True
    ox.settings.requests_timeout = args.timeout
    ox.settings.http_user_agent = user_agent
    ox.settings.requests_kwargs = {}
    ox.settings.overpass_rate_limit = False
    ox.settings.overpass_settings = f"[out:json][timeout:{args.timeout}]"
    if args.overpass_url:
        ox.settings.overpass_url = normalize_overpass_base(args.overpass_url[0])


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def atomic_write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def load_dataset_index(index_fp: Path) -> dict:
    if not index_fp.exists():
        return {"schema": DATASET_INDEX_SCHEMA, "updated_at": utc_now_iso(), "datasets": []}
    try:
        payload = json.loads(index_fp.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Invalid OSM dataset index: {index_fp}: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("datasets"), list):
        raise RuntimeError(f"Invalid OSM dataset index schema: {index_fp}")
    payload.setdefault("schema", DATASET_INDEX_SCHEMA)
    return payload


def save_dataset_index(index_fp: Path, index: dict) -> None:
    index["schema"] = DATASET_INDEX_SCHEMA
    index["updated_at"] = utc_now_iso()
    atomic_write_json(index_fp, index)


def upsert_dataset(index: dict, entry: dict) -> None:
    datasets = index.setdefault("datasets", [])
    for i, current in enumerate(datasets):
        if current.get("dataset_id") == entry.get("dataset_id"):
            merged = dict(current)
            merged.update(entry)
            datasets[i] = merged
            return
    datasets.append(entry)


def resolve_indexed_path(value: str | None) -> Path | None:
    if not value:
        return None
    return resolve_path(value)


def _find_key_recursive(obj, target: str):
    if isinstance(obj, dict):
        if target in obj:
            return obj[target]
        for key, value in obj.items():
            if str(key).endswith(target):
                return value
            found = _find_key_recursive(value, target)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_key_recursive(item, target)
            if found is not None:
                return found
    return None


def osmium_executable(osmium_bin: str) -> str | None:
    candidate = Path(osmium_bin)
    if candidate.exists():
        return str(candidate)
    return shutil.which(osmium_bin)


def require_osmium(args: argparse.Namespace) -> str:
    exe = osmium_executable(args.osmium_bin)
    if not exe:
        raise RuntimeError(
            "Local .osm.pbf processing requires osmium-tool. Install osmium and/or provide --osmium-bin. "
            "IA1 will not silently treat a PBF as usable without being able to inspect/extract it."
        )
    return exe


def run_command(cmd: list[str], *, timeout: int | None = None) -> subprocess.CompletedProcess:
    shown = " ".join(str(x) for x in cmd)
    print(f"RUN: {shown}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {shown}\nSTDOUT:\n{result.stdout[-4000:]}\nSTDERR:\n{result.stderr[-4000:]}"
        )
    return result


def parse_bbox_value(value) -> tuple[float, float, float, float] | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        # data.bbox may be [[west,south],[east,north]] or [west,south,east,north]
        if len(value) == 4 and all(isinstance(x, (int, float)) for x in value):
            return tuple(float(x) for x in value)  # type: ignore[return-value]
        if len(value) >= 1 and isinstance(value[0], (list, tuple)):
            first = value[0]
            if len(value) == 2 and len(first) == 2 and len(value[1]) == 2:
                return (float(first[0]), float(first[1]), float(value[1][0]), float(value[1][1]))
            if len(first) == 4:
                return tuple(float(x) for x in first)  # type: ignore[return-value]
    if isinstance(value, str):
        nums = re.findall(r"-?\d+(?:\.\d+)?", value)
        if len(nums) >= 4:
            return tuple(float(x) for x in nums[:4])  # type: ignore[return-value]
    return None


def osmium_file_info(pbf_fp: Path, args: argparse.Namespace, extended: bool = False) -> dict:
    osmium = require_osmium(args)
    cmd = [osmium, "fileinfo", "-j", "--no-crc"]
    if extended:
        cmd.append("-e")
    cmd.append(str(pbf_fp))
    result = run_command(cmd, timeout=args.download_timeout)
    try:
        payload = json.loads(result.stdout)
    except Exception as exc:
        raise RuntimeError(f"Could not parse osmium fileinfo JSON for {pbf_fp}: {exc}") from exc

    bbox_value = _find_key_recursive(payload, "boxes")
    bbox = parse_bbox_value(bbox_value)
    if bbox is None and extended:
        bbox = parse_bbox_value(_find_key_recursive(payload, "bbox"))

    base_ts = _find_key_recursive(payload, "osmosis_replication_timestamp")
    if base_ts is None:
        base_ts = _find_key_recursive(payload, "timestamp.last")

    return {"raw": payload, "bbox": bbox, "osm_base_timestamp": base_ts}


def write_coverage_geojson(geometry, out_fp: Path, properties: dict | None = None) -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": properties or {},
                "geometry": mapping(geometry),
            }
        ],
    }
    atomic_write_json(out_fp, payload)


def read_coverage_geometry(entry: dict):
    coverage_fp = resolve_indexed_path(entry.get("coverage_geojson"))
    if coverage_fp and coverage_fp.exists():
        try:
            payload = json.loads(coverage_fp.read_text(encoding="utf-8"))
            if payload.get("type") == "FeatureCollection":
                features = payload.get("features") or []
                if features:
                    return shape(features[0]["geometry"])
            if payload.get("type") == "Feature":
                return shape(payload["geometry"])
            return shape(payload)
        except Exception as exc:
            print(f"WARNING: could not read coverage geometry {coverage_fp}: {exc}")
    bbox_value = entry.get("coverage_bbox")
    bbox_tuple = parse_bbox_value(bbox_value)
    if bbox_tuple:
        return box(*bbox_tuple)
    return None


def coverage_state(required_geometry, coverage_geometry) -> str:
    if coverage_geometry is None or coverage_geometry.is_empty:
        return "UNKNOWN"
    if coverage_geometry.covers(required_geometry):
        return "FULL"
    if coverage_geometry.intersects(required_geometry):
        return "PARTIAL"
    return "NONE"


def dataset_is_existing(entry: dict) -> bool:
    fp = resolve_indexed_path(entry.get("path"))
    return bool(fp and fp.exists())


def route_area_reuse_allowed(entry: dict, case_id: str, allow_unvalidated: bool) -> bool:
    if entry.get("kind") not in {"route_area", "overpass_snapshot"}:
        return True
    if entry.get("created_for_case_id") == case_id:
        return True
    connectivity = ((entry.get("shared_qa") or {}).get("connectivity") or "PENDING").upper()
    return connectivity == "PASS" or allow_unvalidated


def choose_covering_dataset(
    index: dict,
    required_geometry,
    *,
    case_id: str,
    allowed_kinds: set[str] | None = None,
    allow_unvalidated_shared: bool = False,
    anchor_points: list[Point] | None = None,
    required_tile_profile: str | None = None,
) -> tuple[dict | None, str]:
    candidates = []
    best_partial = "NONE"
    for entry in index.get("datasets", []):
        if allowed_kinds and entry.get("kind") not in allowed_kinds:
            continue
        if (
            entry.get("kind") == "nlsc_tile"
            and required_tile_profile is not None
            and entry.get("tile_dataset_profile") != required_tile_profile
        ):
            # v1.5.3 does not silently reuse legacy TILE_FULL extracts that were built with
            # complete_ways / majority-era semantics and may have incomplete route relations.
            continue
        if not dataset_is_existing(entry):
            continue
        if not route_area_reuse_allowed(entry, case_id, allow_unvalidated_shared):
            continue
        cov = read_coverage_geometry(entry)
        if cov is None:
            continue

        # Stage 1: cheap GPX-anchor prefilter. This can reject obvious non-matches,
        # but it can never declare FULL by itself.
        if anchor_points:
            anchor_hits = sum(1 for pt in anchor_points if cov.covers(pt))
            if anchor_hits < len(anchor_points):
                if anchor_hits > 0 or cov.intersects(required_geometry):
                    best_partial = "PARTIAL"
                continue

        # Stage 2: authoritative test. The entire buffered route geometry must be covered.
        state = coverage_state(required_geometry, cov)
        if state == "PARTIAL":
            best_partial = "PARTIAL"
        if state != "FULL":
            continue
        area = float(cov.area) if cov is not None else math.inf
        fetched = entry.get("fetched_at") or ""
        kind_rank_map = {"nlsc_tile": 0, "route_area": 1, "overpass_snapshot": 2}
        kind_rank = kind_rank_map.get(entry.get("kind"), 3)
        candidates.append((kind_rank, area, fetched, entry))
    if not candidates:
        return None, best_partial
    candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=False)
    return candidates[0][3], "FULL"


def register_pbf_if_needed(
    pbf_fp: Path,
    index: dict,
    args: argparse.Namespace,
    *,
    kind: str = "local_pbf",
    source_url: str | None = None,
    dataset_id: str | None = None,
) -> dict | None:
    pbf_fp = pbf_fp.resolve()
    for entry in index.get("datasets", []):
        existing = resolve_indexed_path(entry.get("path"))
        if existing and existing.exists() and existing.resolve() == pbf_fp:
            return entry

    info = osmium_file_info(pbf_fp, args, extended=False)
    if info["bbox"] is None:
        print(f"PBF header has no bounds, performing one extended fileinfo scan: {pbf_fp}")
        info = osmium_file_info(pbf_fp, args, extended=True)
    if info["bbox"] is None:
        print(f"WARNING: cannot register PBF without a usable coverage bbox: {pbf_fp}")
        return None

    digest = sha256_file(pbf_fp)
    dataset_id = dataset_id or f"pbf_{pbf_fp.stem}_{digest[:12]}"
    entry = {
        "dataset_id": dataset_id,
        "kind": kind,
        "path": portable_path(pbf_fp),
        "source_url": source_url,
        "source_dataset_id": None,
        "fetched_at": datetime.fromtimestamp(pbf_fp.stat().st_mtime, timezone.utc).isoformat(),
        "osm_base_timestamp": info.get("osm_base_timestamp"),
        "coverage_bbox": list(info["bbox"]),
        "coverage_geojson": None,
        "buffer_m": None,
        "script_version": VERSION,
        "sha256": digest,
        "license": OSM_LICENSE,
        "attribution": OSM_ATTRIBUTION,
        "shared_qa": {"coverage": "PASS", "connectivity": "NOT_APPLICABLE_RAW_SNAPSHOT"},
    }
    upsert_dataset(index, entry)
    return entry


def discover_local_pbfs(data_dir: Path, index: dict, args: argparse.Namespace) -> None:
    explicit = [resolve_path(p) for p in (args.pbf_fp or [])]
    discovered = []
    for root in [data_dir / "snapshots", data_dir / "route_areas", data_dir / "tiles"]:
        if root.exists():
            discovered.extend(sorted(root.rglob("*.osm.pbf")))

    known_paths = set()
    for entry in index.get("datasets", []):
        fp = resolve_indexed_path(entry.get("path"))
        if fp:
            known_paths.add(str(fp.resolve()))

    for pbf_fp in explicit + discovered:
        if not pbf_fp.exists() or pbf_fp.name.endswith(".semantic.osm.pbf"):
            continue
        if str(pbf_fp.resolve()) in known_paths:
            continue
        try:
            kind = "taiwan_snapshot" if "taiwan" in pbf_fp.name.lower() else "local_pbf"
            register_pbf_if_needed(pbf_fp, index, args, kind=kind)
        except Exception as exc:
            print(f"WARNING: local PBF discovery skipped {pbf_fp}: {exc}")


def latest_taiwan_snapshot(index: dict) -> dict | None:
    entries = [
        e for e in index.get("datasets", [])
        if e.get("kind") == "taiwan_snapshot" and dataset_is_existing(e)
    ]
    if not entries:
        return None
    entries.sort(key=lambda e: e.get("fetched_at") or "", reverse=True)
    return entries[0]


def snapshot_age_days(entry: dict) -> float:
    text = entry.get("fetched_at")
    if not text:
        return math.inf
    try:
        dt = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 86400.0
    except Exception:
        return math.inf


def sync_taiwan_pbf(data_dir: Path, index: dict, args: argparse.Namespace, user_agent: str) -> dict:
    latest = latest_taiwan_snapshot(index)
    if latest and snapshot_age_days(latest) <= args.sync_max_age_days and not args.force_refresh:
        print(
            f"Taiwan PBF snapshot is recent enough ({snapshot_age_days(latest):.2f} days): "
            f"{resolve_indexed_path(latest.get('path'))}"
        )
        return latest

    snapshots_dir = data_dir / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": user_agent, "Accept": "application/octet-stream"}
    print(f"Downloading Taiwan PBF snapshot from: {args.geofabrik_url}")
    try:
        response = requests.get(
            args.geofabrik_url,
            headers=headers,
            stream=True,
            timeout=(20, args.download_timeout),
        )
        response.raise_for_status()
    except Exception as exc:
        if latest:
            print(f"WARNING: Taiwan PBF refresh failed; preserving existing snapshot: {exc}")
            return latest
        raise RuntimeError(f"Taiwan PBF download failed and no local fallback exists: {exc}") from exc

    last_modified = response.headers.get("Last-Modified")
    snapshot_dt = datetime.now(timezone.utc)
    if last_modified:
        try:
            snapshot_dt = parsedate_to_datetime(last_modified).astimezone(timezone.utc)
        except Exception:
            pass
    date_token = snapshot_dt.strftime("%Y%m%d")
    target = snapshots_dir / f"taiwan-{date_token}.osm.pbf"
    temp_fp = target.with_suffix(target.suffix + ".part")

    if target.exists() and not args.force_refresh:
        print(f"Immutable snapshot already exists: {target}")
        entry = register_pbf_if_needed(
            target,
            index,
            args,
            kind="taiwan_snapshot",
            source_url=args.geofabrik_url,
        )
        if entry is None:
            raise RuntimeError(f"Could not register existing snapshot: {target}")
        return entry

    with temp_fp.open("wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_fp, target)

    entry = register_pbf_if_needed(
        target,
        index,
        args,
        kind="taiwan_snapshot",
        source_url=args.geofabrik_url,
    )
    if entry is None:
        raise RuntimeError(f"Downloaded PBF could not be registered: {target}")
    entry["http_last_modified"] = last_modified
    entry["downloaded_at"] = utc_now_iso()
    upsert_dataset(index, entry)
    return entry


def semantic_filter_expressions(profile: str = "pipeline") -> list[str]:
    expressions: list[str] = []
    seen = set()
    for _group_name, tags in osm_tag_groups(profile):
        for key, value in tags.items():
            if value is True:
                expr = f"nwr/{key}"
            elif isinstance(value, str):
                expr = f"nwr/{key}={value}"
            else:
                expr = f"nwr/{key}={','.join(str(v) for v in value)}"
            if expr not in seen:
                seen.add(expr)
                expressions.append(expr)
    return expressions


def ensure_semantic_pbf(route_area_fp: Path, semantic_pbf_fp: Path, filters_fp: Path, args: argparse.Namespace) -> None:
    if semantic_pbf_fp.exists() and not args.force_refresh:
        return
    osmium = require_osmium(args)
    filters = semantic_filter_expressions("pipeline")
    filters_fp.write_text("\n".join(filters) + "\n", encoding="utf-8")
    run_command(
        [
            osmium,
            "tags-filter",
            "-t",
            "-e",
            str(filters_fp),
            "-O",
            "-o",
            str(semantic_pbf_fp),
            str(route_area_fp),
        ],
        timeout=args.download_timeout,
    )


def osmium_relation_strategy_args(args: argparse.Namespace) -> list[str]:
    if args.osmium_extract_strategy != "smart":
        return []
    profile = getattr(args, "relation_completion_profile", "semantic")
    if profile == "none":
        return []
    if profile == "all":
        return ["-S", "types=any"]
    if profile == "multipolygon":
        return ["-S", "types=multipolygon"]
    # Complete only semantic relation families IA1 actually consumes. This avoids the size blow-up
    # of completing every transit/boundary relation touching the tile while preserving hiking/foot routes,
    # multipolygons, and protected-area boundaries.
    return [
        "-S",
        "types=multipolygon,route,boundary",
        "-S",
        "tags=type=multipolygon,route=hiking,route=foot,boundary=protected_area,boundary=national_park",
    ]


def tile_dataset_profile(args: argparse.Namespace) -> str:
    return (
        f"{NLSC_TILE_DATASET_PROFILE}|strategy={args.osmium_extract_strategy}|"
        f"relations={getattr(args, 'relation_completion_profile', 'semantic')}"
    )


def osmium_extract_cmd(
    osmium: str,
    *,
    coverage_fp: Path,
    output_fp: Path,
    input_fp: Path,
    args: argparse.Namespace,
) -> list[str]:
    cmd = [
        osmium,
        "extract",
        "-p",
        str(coverage_fp),
        "-s",
        args.osmium_extract_strategy,
    ]
    cmd.extend(osmium_relation_strategy_args(args))
    cmd.extend(["--set-bounds", "-O", "-o", str(output_fp), str(input_fp)])
    return cmd


def build_route_area_dataset(
    parent_entry: dict,
    route_line: LineString,
    case_id: str,
    data_dir: Path,
    index: dict,
    args: argparse.Namespace,
) -> dict:
    parent_fp = resolve_indexed_path(parent_entry.get("path"))
    if not parent_fp or not parent_fp.exists():
        raise RuntimeError(f"Parent PBF missing: {parent_entry.get('path')}")

    coverage_geometry = route_buffer_geometry(
        route_line,
        args.dataset_buffer_m,
        simplify_m=args.dataset_buffer_simplify_m,
    )
    parent_cov = read_coverage_geometry(parent_entry)
    if coverage_state(coverage_geometry, parent_cov) != "FULL":
        raise RuntimeError(
            "Selected parent PBF does not fully cover the reusable route-area polygon. "
            "Refusing partial local extraction."
        )

    stable_key = (
        f"{parent_entry.get('dataset_id')}|{args.dataset_buffer_m}|"
        + coverage_geometry.wkb_hex
    ).encode("utf-8")
    area_hash = sha256_bytes(stable_key)[:12]
    dataset_id = f"routearea_{area_hash}"
    route_dir = data_dir / "route_areas" / dataset_id
    route_dir.mkdir(parents=True, exist_ok=True)
    route_area_fp = route_dir / f"{dataset_id}.osm.pbf"
    semantic_pbf_fp = route_dir / f"{dataset_id}.semantic.osm.pbf"
    coverage_fp = route_dir / f"{dataset_id}.coverage.geojson"
    filters_fp = route_dir / f"{dataset_id}.filters.txt"

    if not route_area_fp.exists() or args.force_refresh:
        write_coverage_geojson(
            coverage_geometry,
            coverage_fp,
            {
                "dataset_id": dataset_id,
                "source_dataset_id": parent_entry.get("dataset_id"),
                "buffer_m": args.dataset_buffer_m,
            },
        )
        osmium = require_osmium(args)
        cmd = osmium_extract_cmd(
            osmium,
            coverage_fp=coverage_fp,
            output_fp=route_area_fp,
            input_fp=parent_fp,
            args=args,
        )
        run_command(cmd, timeout=args.download_timeout)

    ensure_semantic_pbf(route_area_fp, semantic_pbf_fp, filters_fp, args)
    digest = sha256_file(route_area_fp)
    entry = {
        "dataset_id": dataset_id,
        "kind": "route_area",
        "path": portable_path(route_area_fp),
        "semantic_pbf": portable_path(semantic_pbf_fp),
        "coverage_geojson": portable_path(coverage_fp),
        "coverage_bbox": list(geometry_bbox(coverage_geometry)),
        "source_url": parent_entry.get("source_url"),
        "source_dataset_id": parent_entry.get("dataset_id"),
        "fetched_at": utc_now_iso(),
        "osm_base_timestamp": parent_entry.get("osm_base_timestamp"),
        "buffer_m": args.dataset_buffer_m,
        "script_version": VERSION,
        "sha256": digest,
        "license": OSM_LICENSE,
        "attribution": OSM_ATTRIBUTION,
        "created_for_case_id": case_id,
        "shared_qa": {"coverage": "PASS", "connectivity": "PENDING"},
    }
    upsert_dataset(index, entry)
    return entry



def build_nlsc_tile_dataset(
    parent_entry: dict,
    tile_ids: list[str],
    tile_theoretical_geometry,
    tile_fetch_geometry,
    data_dir: Path,
    index: dict,
    args: argparse.Namespace,
) -> dict:
    parent_fp = resolve_indexed_path(parent_entry.get("path"))
    if not parent_fp or not parent_fp.exists():
        raise RuntimeError(f"Parent PBF missing: {parent_entry.get('path')}")
    parent_cov = read_coverage_geometry(parent_entry)
    if coverage_state(tile_fetch_geometry, parent_cov) != "FULL":
        raise RuntimeError(
            "Selected parent PBF does not fully cover the NLSC tile fetch geometry. Refusing partial extraction."
        )

    tile_token = "__".join(sorted(tile_ids))
    parent_hash = str(parent_entry.get("sha256") or parent_entry.get("dataset_id") or "parent")[:12]
    profile = tile_dataset_profile(args)
    stable_key = (
        f"{parent_entry.get('dataset_id')}|{tile_token}|{args.tile_fetch_buffer_m}|{profile}|"
        + tile_fetch_geometry.wkb_hex
    ).encode("utf-8")
    area_hash = sha256_bytes(stable_key)[:10]
    dataset_id = f"nlsc_{tile_token}_{parent_hash}_{area_hash}"
    tile_dir = data_dir / "tiles" / tile_token / dataset_id
    tile_dir.mkdir(parents=True, exist_ok=True)
    tile_pbf_fp = tile_dir / f"{dataset_id}.osm.pbf"
    semantic_pbf_fp = tile_dir / f"{dataset_id}.semantic.osm.pbf"
    coverage_fp = tile_dir / f"{dataset_id}.coverage.geojson"
    filters_fp = tile_dir / f"{dataset_id}.filters.txt"

    if not tile_pbf_fp.exists() or args.force_refresh:
        write_coverage_geojson(
            tile_fetch_geometry,
            coverage_fp,
            {
                "dataset_id": dataset_id,
                "kind": "nlsc_tile",
                "nlsc_tiles": sorted(tile_ids),
                "tile_authority": "NLSC_THEORETICAL_GRID",
                "tile_theoretical_bbox": list(geometry_bbox(tile_theoretical_geometry)),
                "osm_fetch_bbox": list(geometry_bbox(tile_fetch_geometry)),
                "bbox_buffer_m": args.tile_fetch_buffer_m,
                "source_dataset_id": parent_entry.get("dataset_id"),
                "tile_dataset_profile": profile,
                "extract_strategy": args.osmium_extract_strategy,
                "relation_completion_profile": args.relation_completion_profile,
            },
        )
        osmium = require_osmium(args)
        run_command(
            osmium_extract_cmd(
                osmium,
                coverage_fp=coverage_fp,
                output_fp=tile_pbf_fp,
                input_fp=parent_fp,
                args=args,
            ),
            timeout=args.download_timeout,
        )

    ensure_semantic_pbf(tile_pbf_fp, semantic_pbf_fp, filters_fp, args)
    digest = sha256_file(tile_pbf_fp)
    entry = {
        "dataset_id": dataset_id,
        "kind": "nlsc_tile",
        "path": portable_path(tile_pbf_fp),
        "semantic_pbf": portable_path(semantic_pbf_fp),
        "coverage_geojson": portable_path(coverage_fp),
        "coverage_bbox": list(geometry_bbox(tile_fetch_geometry)),
        "tile_theoretical_bbox": list(geometry_bbox(tile_theoretical_geometry)),
        "nlsc_tiles": sorted(tile_ids),
        "tile_authority": "NLSC_THEORETICAL_GRID",
        "tile_dataset_profile": profile,
        "extract_strategy": args.osmium_extract_strategy,
        "relation_completion_profile": args.relation_completion_profile,
        "bbox_buffer_m": args.tile_fetch_buffer_m,
        "source_url": parent_entry.get("source_url"),
        "source_dataset_id": parent_entry.get("dataset_id"),
        "fetched_at": utc_now_iso(),
        "osm_base_timestamp": parent_entry.get("osm_base_timestamp"),
        "buffer_m": args.tile_fetch_buffer_m,
        "script_version": VERSION,
        "sha256": digest,
        "license": OSM_LICENSE,
        "attribution": OSM_ATTRIBUTION,
        "shared_qa": {
            "coverage": "PASS",
            "connectivity": "NOT_APPLICABLE_TILE_DATASET",
            "relation_completion": (
                "SMART_SEMANTIC_RELATIONS" if args.osmium_extract_strategy == "smart" and args.relation_completion_profile == "semantic"
                else f"{args.osmium_extract_strategy}:{args.relation_completion_profile}"
            ),
        },
    }
    upsert_dataset(index, entry)
    return entry


ROUTE_RELATION_MEMBER_COLUMNS = [
    "route_relation_id",
    "route_relation_route",
    "route_relation_name",
    "route_relation_ref",
    "route_relation_network",
    "route_relation_osmc_symbol",
    "route_relation_symbol",
    "route_relation_colour",
    "route_relation_member_role",
    "route_relation_member_sequence",
    "member_way_id",
]


def empty_route_relation_memberships() -> pd.DataFrame:
    return pd.DataFrame(columns=ROUTE_RELATION_MEMBER_COLUMNS)


def parse_route_relation_memberships_from_osm_xml(xml_fp: Path) -> pd.DataFrame:
    """Parse route=hiking/foot relation membership without losing child tags/members.

    ElementTree streaming must retain relation children until the relation end event.
    Clearing tag/member elements early makes every relation appear tagless/memberless.
    """
    rows: list[dict] = []
    in_relation = False
    relation_id: str | None = None
    relation_tags: dict[str, str | None] = {}
    relation_members: list[tuple[str, str | None, int]] = []

    for event, elem in ET.iterparse(xml_fp, events=("start", "end")):
        if event == "start":
            if elem.tag == "relation":
                in_relation = True
                relation_id = elem.attrib.get("id")
                relation_tags = {}
                relation_members = []
            elif in_relation and elem.tag == "tag":
                key = elem.attrib.get("k")
                if key is not None:
                    relation_tags[key] = elem.attrib.get("v")
            elif in_relation and elem.tag == "member" and elem.attrib.get("type") == "way":
                ref = elem.attrib.get("ref")
                if ref:
                    relation_members.append((ref, elem.attrib.get("role"), len(relation_members)))
            continue

        if elem.tag == "relation":
            route = relation_tags.get("route")
            if route in {"hiking", "foot"}:
                for member_way_id, member_role, member_sequence in relation_members:
                    rows.append(
                        {
                            "route_relation_id": relation_id,
                            "route_relation_route": route,
                            "route_relation_name": relation_tags.get("name"),
                            "route_relation_ref": relation_tags.get("ref"),
                            "route_relation_network": relation_tags.get("network"),
                            "route_relation_osmc_symbol": relation_tags.get("osmc:symbol"),
                            "route_relation_symbol": relation_tags.get("symbol"),
                            "route_relation_colour": relation_tags.get("colour"),
                            "route_relation_member_role": member_role,
                            "route_relation_member_sequence": member_sequence,
                            "member_way_id": member_way_id,
                        }
                    )
            in_relation = False
            relation_id = None
            relation_tags = {}
            relation_members = []
            elem.clear()
        elif not in_relation and elem.tag in {"node", "way"}:
            elem.clear()
        # Do not clear tag/member children while inside a relation.

    if not rows:
        return empty_route_relation_memberships()
    return pd.DataFrame(rows, columns=ROUTE_RELATION_MEMBER_COLUMNS)


def build_route_relation_member_layers(
    raw: gpd.GeoDataFrame,
    memberships: pd.DataFrame,
    tile_relation_entity_counts: dict[str, int | None] | None = None,
) -> tuple[dict[str, gpd.GeoDataFrame], list[dict]]:
    """Join route relation metadata back onto current analysis highway member ways.

    Output is one geometry per relation-member membership. A way may legitimately
    appear multiple times when it belongs to multiple named hiking/foot routes.

    QA semantics are deliberately split:
    - tile_relation_entities: every route relation entity in the TILE_FULL semantic PBF.
    - relations_with_way_members: relation entities represented in the membership table.
    - analysis_touching_relations: relation entities with >=1 member way in this route subset.
    """
    empty = gpd.GeoDataFrame(geometry=[], crs=raw.crs or "EPSG:4326")
    outputs = {"hiking_route": empty.copy(), "foot_route": empty.copy()}
    qa_rows: list[dict] = []
    entity_counts = tile_relation_entity_counts or {}

    def _entity_count(route: str) -> int | None:
        value = entity_counts.get(route)
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    if memberships is None or memberships.empty or raw.empty:
        for route in ("hiking", "foot"):
            with_way = 0 if memberships is None or memberships.empty else int(
                memberships.loc[memberships["route_relation_route"].eq(route), "route_relation_id"].nunique()
            )
            entity_count = _entity_count(route)
            qa_rows.append(
                {
                    "route": route,
                    "tile_relation_entities": entity_count,
                    "relations_with_way_members": with_way,
                    "relations_without_way_members": (
                        max(0, entity_count - with_way) if entity_count is not None else None
                    ),
                    # Backward-compatible v1.5.5 field. It never meant all tile relation entities.
                    "tile_relation_count": with_way,
                    "tile_relation_count_semantics": "RELATIONS_WITH_WAY_MEMBERS_ONLY",
                    "analysis_touching_relation_count": 0,
                    "analysis_unique_member_way_count": 0,
                    "analysis_relation_member_feature_count": 0,
                }
            )
        return outputs, qa_rows

    ways = raw[
        raw.get("osm_type", pd.Series(pd.NA, index=raw.index))
        .astype("string")
        .str.lower()
        .eq("way")
        .fillna(False)
    ].copy()
    if ways.empty or "osm_id" not in ways.columns:
        return outputs, qa_rows

    ways["_osm_id_key"] = (
        ways["osm_id"].astype("string").str.replace(r"\.0$", "", regex=True)
    )

    for route, layer_name in (("hiking", "hiking_route"), ("foot", "foot_route")):
        rel = memberships[memberships["route_relation_route"].eq(route)].copy()
        relations_with_way_members = int(rel["route_relation_id"].nunique()) if not rel.empty else 0
        entity_count = _entity_count(route)
        if rel.empty:
            joined = empty.copy()
        else:
            joined_df = rel.merge(
                ways,
                left_on="member_way_id",
                right_on="_osm_id_key",
                how="inner",
                validate="many_to_one",
            )
            if joined_df.empty:
                joined = empty.copy()
            else:
                joined_df["member_way_name"] = joined_df.get("name", pd.Series(pd.NA, index=joined_df.index))
                joined_df["route"] = joined_df["route_relation_route"]
                joined_df["name"] = joined_df["route_relation_name"].combine_first(joined_df["member_way_name"])
                joined_df["ref"] = joined_df["route_relation_ref"].combine_first(
                    joined_df.get("ref", pd.Series(pd.NA, index=joined_df.index))
                )
                joined_df["network"] = joined_df["route_relation_network"].combine_first(
                    joined_df.get("network", pd.Series(pd.NA, index=joined_df.index))
                )
                joined_df["osmc:symbol"] = joined_df["route_relation_osmc_symbol"].combine_first(
                    joined_df.get("osmc:symbol", pd.Series(pd.NA, index=joined_df.index))
                )
                joined_df["symbol"] = joined_df["route_relation_symbol"].combine_first(
                    joined_df.get("symbol", pd.Series(pd.NA, index=joined_df.index))
                )
                joined_df["colour"] = joined_df["route_relation_colour"].combine_first(
                    joined_df.get("colour", pd.Series(pd.NA, index=joined_df.index))
                )
                joined_df = joined_df.drop(columns=["_osm_id_key"], errors="ignore")
                joined = gpd.GeoDataFrame(joined_df, geometry="geometry", crs=raw.crs or "EPSG:4326")

        outputs[layer_name] = joined
        qa_rows.append(
            {
                "route": route,
                "tile_relation_entities": entity_count,
                "relations_with_way_members": relations_with_way_members,
                "relations_without_way_members": (
                    max(0, entity_count - relations_with_way_members) if entity_count is not None else None
                ),
                # Backward-compatible v1.5.5 field. Use relations_with_way_members in new consumers.
                "tile_relation_count": relations_with_way_members,
                "tile_relation_count_semantics": "RELATIONS_WITH_WAY_MEMBERS_ONLY",
                "analysis_touching_relation_count": int(joined["route_relation_id"].nunique()) if not joined.empty else 0,
                "analysis_unique_member_way_count": int(joined["osm_id"].astype("string").nunique()) if not joined.empty else 0,
                "analysis_relation_member_feature_count": len(joined),
            }
        )

    return outputs, qa_rows

def load_features_from_local_dataset(
    entry: dict,
    query_geometry,
    data_dir: Path,
    args: argparse.Namespace,
) -> tuple[gpd.GeoDataFrame, pd.DataFrame, bool]:
    route_area_fp = resolve_indexed_path(entry.get("path"))
    if not route_area_fp or not route_area_fp.exists():
        raise RuntimeError(f"Local dataset file missing: {entry.get('path')}")

    if entry.get("kind") == "overpass_snapshot":
        gdf = gpd.read_file(route_area_fp)
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")
        if gdf.crs.to_string().upper() != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        # Coverage has already been checked. Clip once more to the current analysis polygon
        # so a reused snapshot behaves like a fresh IA1 route-buffer query.
        gdf = gdf[gdf.geometry.notna()].copy()
        try:
            gdf = gdf[gdf.geometry.intersects(query_geometry)].copy()
        except Exception:
            pass
        return gdf, empty_route_relation_memberships(), False

    semantic_pbf_fp = resolve_indexed_path(entry.get("semantic_pbf"))
    if semantic_pbf_fp is None:
        semantic_pbf_fp = route_area_fp.with_name(route_area_fp.stem + ".semantic.osm.pbf")
        filters_fp = route_area_fp.with_name(route_area_fp.stem + ".filters.txt")
        ensure_semantic_pbf(route_area_fp, semantic_pbf_fp, filters_fp, args)
        entry["semantic_pbf"] = portable_path(semantic_pbf_fp)

    if not semantic_pbf_fp.exists():
        filters_fp = semantic_pbf_fp.with_suffix(".filters.txt")
        ensure_semantic_pbf(route_area_fp, semantic_pbf_fp, filters_fp, args)

    osmium = require_osmium(args)
    with tempfile.TemporaryDirectory(prefix="ia1_osm_xml_") as tmpdir:
        xml_fp = Path(tmpdir) / "semantic.osm"
        run_command(
            [osmium, "cat", "-O", "-f", "osm", "-o", str(xml_fp), str(semantic_pbf_fp)],
            timeout=args.download_timeout,
        )
        try:
            gdf = ox.features_from_xml(xml_fp, polygon=query_geometry)
        except InsufficientResponseError:
            gdf = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
        route_relation_memberships = parse_route_relation_memberships_from_osm_xml(xml_fp)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    return gdf, route_relation_memberships, True


def save_overpass_immutable_snapshot(
    raw: gpd.GeoDataFrame,
    *,
    dataset_id: str,
    case_id: str,
    query_geometry,
    data_dir: Path,
    source_info: dict,
    args: argparse.Namespace,
    index: dict,
) -> tuple[dict, dict]:
    snapshot_dir = data_dir / "overpass_snapshots" / dataset_id
    snapshot_dir.mkdir(parents=True, exist_ok=False)
    snapshot_fp = snapshot_dir / "osm_raw_snapshot.geojson"
    coverage_fp = snapshot_dir / "coverage.geojson"
    manifest_fp = snapshot_dir / "snapshot_manifest.json"

    snapshot_gdf = select_columns(raw)
    snapshot_gdf.to_file(snapshot_fp, driver="GeoJSON")
    digest = sha256_file(snapshot_fp)
    write_coverage_geojson(
        query_geometry,
        coverage_fp,
        {
            "dataset_id": dataset_id,
            "created_for_case_id": case_id,
            "analysis_buffer_m": args.buffer_m,
        },
    )

    entry = {
        "dataset_id": dataset_id,
        "kind": "overpass_snapshot",
        "path": portable_path(snapshot_fp),
        "coverage_geojson": portable_path(coverage_fp),
        "coverage_bbox": list(geometry_bbox(query_geometry)),
        "source_url": source_info.get("source_url"),
        "source_dataset_id": None,
        "fetched_at": source_info.get("fetched_at") or utc_now_iso(),
        "osm_base_timestamp": source_info.get("osm_base_timestamp"),
        "buffer_m": args.buffer_m,
        "script_version": VERSION,
        "sha256": digest,
        "license": OSM_LICENSE,
        "attribution": OSM_ATTRIBUTION,
        "created_for_case_id": case_id,
        "shared_qa": {"coverage": "PASS", "connectivity": "PENDING"},
    }
    upsert_dataset(index, entry)

    manifest = {
        **entry,
        "snapshot_policy": "immutable",
        "tag_profile": args.tag_profile,
        "copyright_url": OSM_COPYRIGHT_URL,
        "force_refresh_source_run": bool(args.force_refresh),
        "force_refresh_reason": args.force_refresh_reason,
    }
    atomic_write_json(manifest_fp, manifest)

    updated_source = dict(source_info)
    updated_source["source_sha256"] = digest
    return entry, updated_source


def normalize_overpass_base(url: str) -> str:
    value = url.strip().rstrip("/")
    for suffix in ("/interpreter", "/status"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
    return value.rstrip("/")


def overpass_endpoints(args: argparse.Namespace) -> list[str]:
    values = args.overpass_url or ["https://overpass-api.de/api"]
    result = []
    for value in values:
        base = normalize_overpass_base(value)
        if base and base not in result:
            result.append(base)
    return result


def parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        dt = parsedate_to_datetime(value).astimezone(timezone.utc)
        return max(0.0, (dt - datetime.now(timezone.utc)).total_seconds())
    except Exception:
        return None


def overpass_status_wait(base_url: str, user_agent: str, args: argparse.Namespace) -> float:
    if args.no_overpass_rate_limit:
        return 0.0
    url = normalize_overpass_base(base_url) + "/status"
    try:
        response = requests.get(url, headers={"User-Agent": user_agent}, timeout=min(20, args.timeout))
        if response.status_code >= 400:
            print(f"WARNING: Overpass status preflight HTTP {response.status_code}; continue with HTTP backoff guards.")
            return 0.0
        text = response.text
    except Exception as exc:
        print(f"WARNING: Overpass status preflight failed: {exc}; continue with HTTP backoff guards.")
        return 0.0

    available = re.search(r"(\d+)\s+slots? available now", text)
    if available and int(available.group(1)) > 0:
        return 0.0
    waits = [int(x) for x in re.findall(r"Slot available after: .+?, in\s+(-?\d+)\s+seconds", text)]
    waits = [x for x in waits if x > 0]
    if not waits:
        return 0.0
    wait = float(min(waits) + 1)
    if wait > args.max_status_wait_sec:
        raise RuntimeError(
            f"Overpass reports next slot in {wait:.0f}s, above --max-status-wait-sec={args.max_status_wait_sec:.0f}. "
            "Prefer local PBF instead of holding the formal pipeline on a busy public instance."
        )
    return wait


@contextmanager
def overpass_process_lock(lock_fp: Path):
    lock_fp.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pid": os.getpid(),
        "created_at": utc_now_iso(),
        "host": os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "unknown",
    }
    try:
        fd = os.open(str(lock_fp), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        detail = ""
        try:
            detail = lock_fp.read_text(encoding="utf-8")
        except Exception:
            pass
        raise RuntimeError(
            f"Another Overpass IA1 process appears to be active. Lock: {lock_fp}. "
            f"Do not run public Overpass in parallel. Lock detail: {detail}"
        ) from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        yield
    finally:
        try:
            lock_fp.unlink()
        except FileNotFoundError:
            pass


def overpass_cache_key(endpoint: str, query: str) -> str:
    return sha256_bytes((normalize_overpass_base(endpoint) + "\n" + query).encode("utf-8"))


def load_overpass_cache(cache_dir: Path, endpoint: str, query: str) -> dict | None:
    key = overpass_cache_key(endpoint, query)
    fp = cache_dir / f"{key}.json"
    if not fp.exists():
        return None
    try:
        payload = json.loads(fp.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("elements"), list):
            return payload
    except Exception:
        return None
    return None


def save_overpass_cache(cache_dir: Path, endpoint: str, query: str, payload: dict) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = overpass_cache_key(endpoint, query)
    atomic_write_json(cache_dir / f"{key}.json", payload)
    atomic_write_json(
        cache_dir / f"{key}.meta.json",
        {
            "endpoint": normalize_overpass_base(endpoint),
            "cached_at": utc_now_iso(),
            "query_sha256": sha256_bytes(query.encode("utf-8")),
            "script_version": VERSION,
        },
    )


def response_has_overpass_runtime_error(payload: dict) -> str | None:
    remark = payload.get("remark")
    if remark:
        return str(remark)
    return None


def post_overpass_json(
    query: str,
    endpoints: list[str],
    *,
    cache_dir: Path,
    user_agent: str,
    args: argparse.Namespace,
) -> tuple[dict, str, bool]:
    last_error = None
    for endpoint in endpoints:
        endpoint = normalize_overpass_base(endpoint)
        if not args.force_refresh:
            cached = load_overpass_cache(cache_dir, endpoint, query)
            if cached is not None:
                return cached, endpoint, True

        for attempt in range(args.retry + 1):
            if attempt > 0:
                print(f"Retry Overpass endpoint={endpoint} attempt={attempt + 1}/{args.retry + 1}")
            try:
                status_wait = overpass_status_wait(endpoint, user_agent, args)
                if status_wait > 0:
                    print(f"Overpass status asks us to wait {status_wait:.0f}s")
                    time.sleep(status_wait)
            except Exception as exc:
                last_error = exc
                print(f"WARNING: {exc}")
                break

            url = endpoint + "/interpreter"
            try:
                response = requests.post(
                    url,
                    data={"data": query},
                    headers={"User-Agent": user_agent, "Accept": "application/json"},
                    timeout=(20, args.timeout),
                )
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
                if attempt >= args.retry:
                    break
                wait = min(args.max_backoff_sec, args.sleep_sec * (2 ** attempt))
                print(f"Overpass network error: {exc}; backoff {wait:.1f}s")
                time.sleep(wait)
                continue

            status = response.status_code
            if status in {429, 406}:
                last_error = RuntimeError(f"Overpass HTTP {status}: {response.text[:500]}")
                if attempt >= args.retry:
                    break
                retry_after = parse_retry_after(response.headers.get("Retry-After")) or 0.0
                wait = max(args.rate_limit_wait_sec, retry_after)
                wait = min(max(wait, 30.0), args.max_status_wait_sec)
                print(f"Overpass HTTP {status}; wait {wait:.0f}s before finite retry")
                time.sleep(wait)
                continue

            if 500 <= status <= 599:
                last_error = RuntimeError(f"Overpass HTTP {status}: {response.text[:500]}")
                if attempt >= args.retry:
                    break
                wait = min(args.max_backoff_sec, args.sleep_sec * (2 ** attempt))
                print(f"Overpass HTTP {status}; exponential backoff {wait:.1f}s")
                time.sleep(wait)
                continue

            if status < 200 or status >= 300:
                raise RuntimeError(f"Overpass non-retryable HTTP {status}: {response.text[:1000]}")

            try:
                payload = response.json()
            except Exception as exc:
                last_error = RuntimeError(f"Overpass returned non-JSON success response: {response.text[:1000]}")
                if attempt >= args.retry:
                    break
                wait = min(args.max_backoff_sec, args.sleep_sec * (2 ** attempt))
                time.sleep(wait)
                continue

            runtime_error = response_has_overpass_runtime_error(payload)
            if runtime_error:
                last_error = RuntimeError(f"Overpass runtime remark: {runtime_error}")
                if attempt >= args.retry:
                    break
                wait = min(args.max_backoff_sec, args.sleep_sec * (2 ** attempt))
                print(f"Overpass returned runtime remark; backoff {wait:.1f}s")
                time.sleep(wait)
                continue

            if not isinstance(payload.get("elements"), list):
                last_error = RuntimeError("Overpass JSON does not contain an elements list.")
                if attempt >= args.retry:
                    break
                time.sleep(min(args.max_backoff_sec, args.sleep_sec * (2 ** attempt)))
                continue

            save_overpass_cache(cache_dir, endpoint, query, payload)
            return payload, endpoint, False

        print(f"Overpass endpoint exhausted finite retries: {endpoint}")

    raise RuntimeError(f"All configured Overpass endpoints failed: {last_error}") from last_error


def fetch_features_governed(
    query_geometry,
    tags: dict,
    *,
    endpoints: list[str],
    cache_dir: Path,
    user_agent: str,
    args: argparse.Namespace,
) -> tuple[gpd.GeoDataFrame, set[str], set[str]]:
    try:
        from osmnx import _overpass as ox_overpass
        from osmnx import features as ox_features
    except Exception as exc:
        raise RuntimeError(f"OSMnx private parser helpers unavailable: {exc}") from exc

    required = ["_make_overpass_polygon_coord_strs", "_create_overpass_features_query"]
    for name in required:
        if not hasattr(ox_overpass, name):
            raise RuntimeError(
                f"OSMnx compatibility check failed: missing {name}. Pin/test the OSMnx version before formal use."
            )
    if not hasattr(ox_features, "_create_gdf"):
        raise RuntimeError("OSMnx compatibility check failed: missing features._create_gdf.")

    response_jsons = []
    used_endpoints: set[str] = set()
    base_timestamps: set[str] = set()
    coord_strs = ox_overpass._make_overpass_polygon_coord_strs(query_geometry)
    for coord_str in coord_strs:
        query = ox_overpass._create_overpass_features_query(coord_str, tags)
        payload, endpoint, from_cache = post_overpass_json(
            query,
            endpoints,
            cache_dir=cache_dir,
            user_agent=user_agent,
            args=args,
        )
        print(
            f"Overpass request source={'cache' if from_cache else 'network'} endpoint={endpoint} "
            f"elements={len(payload.get('elements', []))}"
        )
        response_jsons.append(payload)
        used_endpoints.add(endpoint)
        base_ts = (payload.get("osm3s") or {}).get("timestamp_osm_base")
        if base_ts:
            base_timestamps.add(str(base_ts))

    try:
        gdf = ox_features._create_gdf(iter(response_jsons), query_geometry, tags)
    except InsufficientResponseError:
        gdf = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    return gdf, used_endpoints, base_timestamps


def fetch_grouped_features_governed(
    query_geometry,
    groups: list[tuple[str, dict[str, bool | str | list[str]]]],
    *,
    endpoints: list[str],
    cache_dir: Path,
    lock_fp: Path,
    user_agent: str,
    args: argparse.Namespace,
) -> tuple[gpd.GeoDataFrame, set[str], set[str]]:
    frames = []
    all_endpoints: set[str] = set()
    all_base_timestamps: set[str] = set()
    with overpass_process_lock(lock_fp):
        for group_name, tags in groups:
            print(f"Fetching OSM group sequentially: {group_name} tags={tags}")
            try:
                gdf, used, base_timestamps = fetch_features_governed(
                    query_geometry,
                    tags,
                    endpoints=endpoints,
                    cache_dir=cache_dir,
                    user_agent=user_agent,
                    args=args,
                )
                all_endpoints.update(used)
                all_base_timestamps.update(base_timestamps)
            except Exception:
                if group_name == "route_core":
                    raise
                print(f"WARNING: optional OSM group failed and will be skipped: {group_name}")
                continue

            if gdf.empty:
                print(f"OSM group empty: {group_name}")
                continue

            gdf = gdf.copy()
            gdf["query_group"] = group_name
            frames.append(gdf)
            print(f"OSM group fetched: {group_name} features={len(gdf)}")

    if not frames:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326"), all_endpoints, all_base_timestamps

    combined = pd.concat(frames)
    if isinstance(combined.index, pd.MultiIndex):
        combined = combined[~combined.index.duplicated(keep="first")]
    else:
        combined = combined.drop_duplicates(subset=["geometry"], keep="first")
    return (
        gpd.GeoDataFrame(combined, geometry="geometry", crs=frames[0].crs),
        all_endpoints,
        all_base_timestamps,
    )


def source_descriptor(entry: dict | None, *, source_kind: str, source_url: str | None = None) -> dict:
    if entry:
        return {
            "source_kind": source_kind,
            "dataset_id": entry.get("dataset_id"),
            "source_dataset_id": entry.get("source_dataset_id"),
            "source_url": entry.get("source_url") or source_url,
            "source_sha256": entry.get("sha256"),
            "osm_base_timestamp": entry.get("osm_base_timestamp"),
            "fetched_at": entry.get("fetched_at") or utc_now_iso(),
        }
    return {
        "source_kind": source_kind,
        "dataset_id": None,
        "source_dataset_id": None,
        "source_url": source_url,
        "source_sha256": None,
        "osm_base_timestamp": None,
        "fetched_at": utc_now_iso(),
    }


def _iter_line_geometries(geometry):
    if geometry is None or geometry.is_empty:
        return
    if geometry.geom_type == "LineString":
        yield geometry
    elif hasattr(geometry, "geoms"):
        for part in geometry.geoms:
            yield from _iter_line_geometries(part)


def run_basic_connectivity_qa(
    route_line: LineString,
    highway_gdf: gpd.GeoDataFrame,
    args: argparse.Namespace,
) -> dict:
    qa = {
        "status": "FAIL",
        "reason": None,
        "route_near_ratio": 0.0,
        "route_sample_count": 0,
        "component_count": 0,
        "start_end_same_component": False,
        "start_distance_m": None,
        "end_distance_m": None,
        "thresholds": {
            "sample_m": args.qa_route_sample_m,
            "max_distance_m": args.qa_route_max_distance_m,
            "near_ratio": args.qa_route_near_ratio,
            "node_snap_m": args.qa_node_snap_m,
        },
        "note": "QA only; no OSM geometry/topology is modified or artificially repaired.",
    }
    if highway_gdf.empty:
        qa["reason"] = "no_highway_features"
        return qa

    lines = highway_gdf[highway_gdf.geometry.notna()].copy()
    lines = lines[lines.geometry.geom_type.isin(["LineString", "MultiLineString"])]
    if lines.empty:
        qa["reason"] = "no_highway_line_geometry"
        return qa

    route_gdf = gpd.GeoDataFrame([{"geometry": route_line}], crs="EPSG:4326")
    metric_crs = route_gdf.estimate_utm_crs()
    route_m = route_gdf.to_crs(metric_crs).geometry.iloc[0]
    lines_m = lines.to_crs(metric_crs)
    network_geom = unary_union(list(lines_m.geometry))
    if network_geom.is_empty:
        qa["reason"] = "empty_highway_union"
        return qa

    step = max(5.0, float(args.qa_route_sample_m))
    n = max(2, int(math.ceil(route_m.length / step)) + 1)
    samples = [route_m.interpolate(min(i * step, route_m.length)) for i in range(n)]
    near = [p.distance(network_geom) <= args.qa_route_max_distance_m for p in samples]
    qa["route_sample_count"] = len(samples)
    qa["route_near_ratio"] = float(sum(near) / len(near)) if near else 0.0

    # Node the network at true intersections via unary_union, then use a small transient endpoint
    # quantization only for QA graph connectivity. This does NOT change exported OSM geometry.
    graph = nx.Graph()
    segment_records = []
    snap = max(0.1, float(args.qa_node_snap_m))
    for geom in _iter_line_geometries(network_geom):
        coords = list(geom.coords)
        if len(coords) < 2:
            continue
        a = coords[0]
        b = coords[-1]
        ka = (round(a[0] / snap), round(a[1] / snap))
        kb = (round(b[0] / snap), round(b[1] / snap))
        graph.add_edge(ka, kb, length=float(geom.length))
        segment_records.append((ka, kb, geom))

    components = list(nx.connected_components(graph)) if graph.number_of_nodes() else []
    qa["component_count"] = len(components)
    node_to_component = {}
    for i, comp in enumerate(components):
        for node in comp:
            node_to_component[node] = i

    component_geoms: dict[int, list] = {}
    for ka, kb, geom in segment_records:
        comp_id = node_to_component.get(ka)
        if comp_id is not None:
            component_geoms.setdefault(comp_id, []).append(geom)

    start = Point(route_m.coords[0])
    end = Point(route_m.coords[-1])
    best_start = (math.inf, None)
    best_end = (math.inf, None)
    for comp_id, geoms in component_geoms.items():
        merged = unary_union(geoms)
        ds = start.distance(merged)
        de = end.distance(merged)
        if ds < best_start[0]:
            best_start = (ds, comp_id)
        if de < best_end[0]:
            best_end = (de, comp_id)

    qa["start_distance_m"] = None if math.isinf(best_start[0]) else float(best_start[0])
    qa["end_distance_m"] = None if math.isinf(best_end[0]) else float(best_end[0])
    qa["start_end_same_component"] = bool(
        best_start[1] is not None and best_start[1] == best_end[1]
    )

    distance_ok = (
        qa["start_distance_m"] is not None
        and qa["end_distance_m"] is not None
        and qa["start_distance_m"] <= args.qa_route_max_distance_m
        and qa["end_distance_m"] <= args.qa_route_max_distance_m
    )
    near_ok = qa["route_near_ratio"] >= args.qa_route_near_ratio
    same_component_ok = qa["start_end_same_component"]
    if distance_ok and near_ok and same_component_ok:
        qa["status"] = "PASS"
        qa["reason"] = "route_corridor_connected_to_same_osm_highway_component"
    else:
        qa["reason"] = "route_or_endpoints_not_sufficiently_connected_to_same_osm_highway_component"
    return qa


def update_route_area_connectivity_qa(index: dict, dataset_id: str, qa: dict) -> None:
    for entry in index.get("datasets", []):
        if entry.get("dataset_id") == dataset_id and entry.get("kind") in {"route_area", "overpass_snapshot"}:
            shared = dict(entry.get("shared_qa") or {})
            shared["coverage"] = "PASS"
            shared["connectivity"] = qa.get("status", "PENDING")
            shared["connectivity_checked_at"] = utc_now_iso()
            shared["connectivity_detail"] = qa
            entry["shared_qa"] = shared
            return

def osm_tag_groups(profile: str) -> list[tuple[str, dict[str, bool | str | list[str]]]]:
    groups: list[tuple[str, dict[str, bool | str | list[str]]]] = [
        ("route_core", {"highway": True}),
    ]
    if profile == "core":
        return groups

    groups.extend(
        [
            (
                "hydro",
                {
                    "waterway": True,
                    "natural": ["water", "wetland", "waterfall", "spring", "hot_spring"],
                    "water": True,
                    "wetland": True,
                },
            ),
            (
                "terrain_hazard",
                {
                    "natural": [
                        "cliff",
                        "scree",
                        "bare_rock",
                        "landslide",
                        "peak",
                        "volcano",
                    ],
                },
            ),
            (
                "technical",
                {
                    "safety_rope": True,
                    "assisted_trail": True,
                    "handrail": True,
                    "rungs": True,
                    "highway": ["ladder", "via_ferrata", "street_lamp", "trailhead"],
                },
            ),
            (
                "poi_support",
                {
                    "tourism": True,
                    "amenity": True,
                    "leisure": True,
                    "information": True,
                },
            ),
            (
                "management_context",
                {
                    "route": ["hiking", "foot"],
                    "boundary": ["protected_area", "national_park"],
                    "barrier": True,
                    "emergency": True,
                    "man_made": True,
                    "obstacle": True,
                    "overgrown": True,
                    "hazard": True,
                },
            ),
        ]
    )
    return groups


def first_scalar(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


def normalize_scalar(value):
    if isinstance(value, list):
        return value[0] if value else pd.NA
    return value


def has_osm_value(value) -> bool:
    value = normalize_scalar(value)
    if pd.isna(value):
        return False
    text = str(value).strip().lower()
    return text not in {"", "no", "false", "0", "none", "nan", "<na>", "null"}


def clean_bool_series(gdf: gpd.GeoDataFrame, col: str) -> pd.Series:
    if col not in gdf.columns:
        return pd.Series(False, index=gdf.index)
    return gdf[col].notna()


def eq(gdf: gpd.GeoDataFrame, col: str, value: str) -> pd.Series:
    if col not in gdf.columns:
        return pd.Series(False, index=gdf.index)
    return gdf[col].apply(first_scalar).astype("string").str.lower().eq(value)


def isin(gdf: gpd.GeoDataFrame, col: str, values: set[str]) -> pd.Series:
    if col not in gdf.columns:
        return pd.Series(False, index=gdf.index)
    return gdf[col].apply(first_scalar).astype("string").str.lower().isin(values)


def has_value(gdf: gpd.GeoDataFrame, col: str) -> pd.Series:
    if col not in gdf.columns:
        return pd.Series(False, index=gdf.index)
    text = gdf[col].apply(first_scalar).astype("string").str.strip().str.lower()
    return text.notna() & ~text.isin({"", "no", "false", "0", "none", "nan", "<na>", "null"})


def classify_highway_family(hw):
    hw = normalize_scalar(hw)
    if pd.isna(hw):
        return "unknown"
    hw = str(hw).strip().lower()

    if hw in {"motorway", "motorway_link"}:
        return "motorway_system"
    if hw in {
        "trunk",
        "trunk_link",
        "primary",
        "primary_link",
        "secondary",
        "secondary_link",
        "tertiary",
        "tertiary_link",
        "unclassified",
        "residential",
        "living_street",
        "road",
    }:
        return "road_system"
    if hw == "service":
        return "service_road"
    if hw == "track":
        return "track_system"
    if hw == "steps":
        return "steps"
    if hw == "footway":
        return "footway"
    if hw == "pedestrian":
        return "pedestrian_area"
    if hw == "path":
        return "path"
    if hw == "via_ferrata":
        return "via_ferrata"
    if hw == "ladder":
        return "ladder"
    return "other_highway"


def classify_walk_relevance(hw):
    hw = normalize_scalar(hw)
    if pd.isna(hw):
        return "unknown"
    hw = str(hw).strip().lower()

    if hw in {"motorway", "motorway_link"}:
        return "likely_non_walkable"
    if hw in {"trunk", "trunk_link", "primary", "primary_link"}:
        return "vehicle_dominant"
    if hw in {
        "secondary",
        "secondary_link",
        "tertiary",
        "tertiary_link",
        "unclassified",
        "residential",
        "living_street",
        "road",
        "service",
    }:
        return "mixed_access"
    if hw == "track":
        return "walkable_track"
    if hw == "steps":
        return "stairs"
    if hw == "footway":
        return "footway_priority"
    if hw == "pedestrian":
        return "pedestrian_priority"
    if hw == "path":
        return "hiking_path"
    if hw in {"via_ferrata", "ladder"}:
        return "technical_hiking"
    return "other"


def classify_trail_difficulty(sac):
    sac = normalize_scalar(sac)
    if pd.isna(sac):
        return "unknown"
    s = str(sac).strip().lower()

    if s == "hiking":
        return "easy"
    if s == "mountain_hiking":
        return "moderate"
    if s == "demanding_mountain_hiking":
        return "hard"
    if s == "alpine_hiking":
        return "very_hard"
    return "technical"


def classify_vertical_context(row) -> str:
    if has_osm_value(row.get("bridge")):
        return "bridge"
    if has_osm_value(row.get("tunnel")):
        return "tunnel"
    if has_osm_value(row.get("ford")):
        return "ford"
    if has_osm_value(row.get("embankment")):
        return "embankment"
    if has_osm_value(row.get("cutting")):
        return "cutting"
    if has_osm_value(row.get("covered")):
        return "covered"
    if has_osm_value(row.get("layer")):
        return "layered"
    if has_osm_value(row.get("level")):
        return "level_context"
    return "surface"


def normalize_highway(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Normalize highway-related semantic fields.

    注意：
    - raw 內會混合 highway、POI、barrier、emergency、man_made 等 feature。
    - 沒有 highway 的 feature 不應被歸類成 technical_or_other。
    - highway 缺值時，route_role 標為 non_highway_context。
    """
    gdf = gdf.copy()
    if "highway" not in gdf.columns:
        gdf["highway"] = pd.NA

    # -------------------------------------------------
    # 1. highway 基礎正規化
    # -------------------------------------------------
    gdf["highway_norm"] = (
        gdf["highway"]
        .apply(first_scalar)
        .astype("string")
        .str.lower()
    )

    gdf["route_class_raw"] = gdf["highway"]

    gdf["highway_family"] = (
        gdf["highway"]
        .apply(classify_highway_family)
    )

    gdf["walk_relevance"] = (
        gdf["highway"]
        .apply(classify_walk_relevance)
    )

    # -------------------------------------------------
    # 2. route_role 分類
    #    不要讓 NA 被歸入 technical_or_other
    # -------------------------------------------------
    trail_core_values = {
        "path",
        "footway",
        "steps",
        "track",
        "pedestrian",
    }

    approach_values = {
        "service",
        "unclassified",
        "residential",
        "living_street",
        "road",
        "tertiary",
        "tertiary_link",
    }

    technical_values = {
        "ladder",
        "via_ferrata",
    }

    def classify_route_role(hw):
        if pd.isna(hw):
            return "non_highway_context"

        hw = str(hw).strip().lower()

        if hw in trail_core_values:
            return "trail_core"

        if hw in approach_values:
            return "approach_or_road"

        if hw in technical_values:
            return "technical_route"

        return "other_highway"

    gdf["route_role"] = gdf["highway_norm"].apply(classify_route_role)

    # -------------------------------------------------
    # 3. matching semantic score
    #    非 highway context 給 0.00，比 0.10 更乾淨
    # -------------------------------------------------
    gdf["matching_semantic_score"] = (
        gdf["highway_norm"]
        .map(SEMANTIC_SCORE_MAP)
    )

    gdf.loc[
        gdf["route_role"].eq("non_highway_context"),
        "matching_semantic_score",
    ] = 0.00

    gdf["matching_semantic_score"] = (
        gdf["matching_semantic_score"]
        .fillna(0.10)
    )

    # -------------------------------------------------
    # 4. bridge / ford / vertical context
    # -------------------------------------------------
    bridge_series = gdf.get(
        "bridge",
        pd.Series(pd.NA, index=gdf.index),
    )

    ford_series = gdf.get(
        "ford",
        pd.Series(pd.NA, index=gdf.index),
    )

    layer_series = gdf.get(
        "layer",
        pd.Series(pd.NA, index=gdf.index),
    )

    gdf["has_bridge"] = (
        bridge_series
        .apply(lambda v: bool(has_osm_value(v)))
        .astype("int8")
    )

    gdf["has_ford"] = (
        ford_series
        .apply(lambda v: bool(has_osm_value(v)))
        .astype("int8")
    )

    gdf["layer_raw"] = layer_series

    gdf["layer_norm"] = (
        layer_series
        .apply(first_scalar)
        .astype("string")
    )

    def classify_vertical_context_safe(row):
        has_vertical_tag = any(
            has_osm_value(row.get(col))
            for col in [
                "bridge",
                "tunnel",
                "ford",
                "embankment",
                "cutting",
                "covered",
                "layer",
                "level",
            ]
        )

        if row.get("route_role") == "non_highway_context" and not has_vertical_tag:
            return "non_highway_context"

        return classify_vertical_context(row)

    gdf["vertical_context"] = gdf.apply(
        classify_vertical_context_safe,
        axis=1,
    )

    # -------------------------------------------------
    # 5. difficulty hint
    # -------------------------------------------------
    gdf["base_difficulty_source"] = gdf.apply(
        lambda r: (
            "via_ferrata_scale"
            if has_osm_value(r.get("via_ferrata_scale"))
            else (
                "sac_scale"
                if has_osm_value(r.get("sac_scale"))
                else (
                    "highway"
                    if has_osm_value(r.get("highway"))
                    else "none"
                )
            )
        ),
        axis=1,
    )

    gdf["trail_difficulty_hint"] = (
        gdf.get("sac_scale", pd.Series(pd.NA, index=gdf.index))
        .apply(classify_trail_difficulty)
    )

    gdf["step_count_raw"] = gdf.get(
        "step_count",
        pd.Series(pd.NA, index=gdf.index),
    )

    gdf["incline_raw"] = gdf.get(
        "incline",
        pd.Series(pd.NA, index=gdf.index),
    )

    # -------------------------------------------------
    # 6. steps flag
    #    這裡就是剛剛錯誤的修正點
    # -------------------------------------------------
    gdf["is_steps"] = (
        gdf["highway_norm"]
        .eq("steps")
        .fillna(False)
        .astype("int8")
    )

    return gdf



def add_metadata(
    gdf: gpd.GeoDataFrame,
    case_id: str,
    fetched_at: str,
    *,
    dataset_id: str,
    source_kind: str,
    source_url: str | None,
    source_dataset_id: str | None,
    source_sha256: str | None,
    osm_base_timestamp: str | None,
    coverage_status: str,
) -> gpd.GeoDataFrame:
    gdf = gdf.copy()
    # OSMnx features_from_xml/features_from_* returns a MultiIndex whose
    # current canonical names are ["element", "id"]. Older/alternate
    # pipelines may expose element_type/osmid instead. Preserve either form
    # before select_columns creates protected placeholder columns.
    if isinstance(gdf.index, pd.MultiIndex):
        gdf = gdf.reset_index()
    elif gdf.index.name in {"element", "element_type", "id", "osmid"}:
        gdf = gdf.reset_index()

    if "osm_type" not in gdf.columns:
        for candidate in ("element", "element_type"):
            if candidate in gdf.columns:
                gdf["osm_type"] = gdf[candidate]
                break
    if "osm_id" not in gdf.columns:
        for candidate in ("id", "osmid"):
            if candidate in gdf.columns:
                gdf["osm_id"] = gdf[candidate]
                break

    # Fresh OSMnx/PBF/Overpass products must never silently lose their OSM
    # identity. Legacy IA1 bundles remain readable because some historical
    # exports did not preserve these columns.
    if source_kind in {"local_pbf", "overpass"} and len(gdf):
        type_ok = "osm_type" in gdf.columns and gdf["osm_type"].notna().any()
        id_ok = "osm_id" in gdf.columns and gdf["osm_id"].notna().any()
        if not (type_ok and id_ok):
            raise RuntimeError(
                "OSM_IDENTITY_QA_FAIL: fresh OSM features lost element type/OSM ID. "
                f"columns={list(gdf.columns)} index_names={list(getattr(gdf.index, 'names', []))}"
            )
    gdf["route_id"] = case_id
    gdf["osm_dataset_id"] = dataset_id
    gdf["source_name"] = "OpenStreetMap"
    gdf["source_kind"] = source_kind
    gdf["source_url"] = source_url
    gdf["source_dataset_id"] = source_dataset_id
    gdf["source_sha256"] = source_sha256
    gdf["osm_base_timestamp"] = osm_base_timestamp
    gdf["coverage_status"] = coverage_status
    gdf["attribution"] = OSM_ATTRIBUTION
    gdf["license"] = OSM_LICENSE
    gdf["fetched_at"] = fetched_at
    gdf["pipeline_stage"] = "ia1_osm_fetch_raw_local_first"
    gdf["script_version"] = VERSION
    gdf["script_status"] = STATUS
    return gdf

def select_columns(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf = gdf.copy()
    for col in PROTECT_COLS:
        if col != "geometry" and col not in gdf.columns:
            gdf[col] = pd.NA
    for col in PROTECT_COLS:
        if col in gdf.columns and col != "geometry":
            gdf[col] = gdf[col].apply(normalize_scalar)
    cols = [col for col in PROTECT_COLS if col in gdf.columns]
    if "geometry" not in cols:
        cols.append("geometry")
    return gdf[cols].copy()


def manifest_matches_current_version(manifest_fp: Path) -> bool:
    if not manifest_fp.exists():
        return False
    try:
        manifest = pd.read_csv(manifest_fp)
    except Exception:
        return False
    if "script_version" not in manifest.columns or manifest.empty:
        return False
    return manifest["script_version"].astype("string").eq(VERSION).all()


def layer_masks(gdf: gpd.GeoDataFrame) -> dict[str, pd.Series]:
    """Return v1.3-compatible semantic layer masks.

    The friendly fetcher retrieves broader grouped OSM features once, then splits
    them into the same fine-grained raw layers that the Qixing v1.3 pipeline used.
    """
    false = pd.Series(False, index=gdf.index)
    geom_line = gdf.geometry.geom_type.isin(["LineString", "MultiLineString"])

    information_any = has_value(gdf, "information")
    info_guidepost = eq(gdf, "information", "guidepost")
    info_route_marker = eq(gdf, "information", "route_marker")
    info_board_or_map = isin(gdf, "information", {"board", "map"})
    board_map_type = has_value(gdf, "map_type")
    board_warning_notice = isin(gdf, "board_type", {"warning", "notice"})

    emergency_any = has_value(gdf, "emergency")
    man_made_any = has_value(gdf, "man_made")

    return {
        "highway": clean_bool_series(gdf, "highway") & geom_line,
        "waterway": clean_bool_series(gdf, "waterway") & geom_line,
        "water_area": eq(gdf, "natural", "water") | has_value(gdf, "water"),
        "wetland": eq(gdf, "natural", "wetland") | has_value(gdf, "wetland"),
        "cliff": eq(gdf, "natural", "cliff"),
        "scree": eq(gdf, "natural", "scree"),
        "bare_rock": eq(gdf, "natural", "bare_rock"),
        "landslide": eq(gdf, "natural", "landslide"),
        "safety_rope": has_value(gdf, "safety_rope"),
        "assisted_trail": has_value(gdf, "assisted_trail"),
        "handrail": has_value(gdf, "handrail"),
        "rungs": has_value(gdf, "rungs"),
        "ladder": eq(gdf, "highway", "ladder"),
        "via_ferrata": eq(gdf, "highway", "via_ferrata"),
        "street_lamp": eq(gdf, "highway", "street_lamp"),
        "trailhead": eq(gdf, "highway", "trailhead"),
        "milestone": eq(gdf, "highway", "milestone"),
        "peak": eq(gdf, "natural", "peak"),
        "guidepost": info_guidepost,
        "route_marker": info_route_marker,
        "board_map": info_board_or_map | board_map_type,
        "guide_map_attraction": info_board_or_map | board_map_type,
        "warning_notice": board_warning_notice | has_value(gdf, "hazard"),
        "shelter": eq(gdf, "amenity", "shelter"),
        "alpine_hut": eq(gdf, "tourism", "alpine_hut"),
        "wilderness_hut": eq(gdf, "tourism", "wilderness_hut"),
        "bench": eq(gdf, "amenity", "bench"),
        "picnic_table": eq(gdf, "leisure", "picnic_table"),
        "picnic_site": eq(gdf, "tourism", "picnic_site"),
        "drinking_water": eq(gdf, "amenity", "drinking_water"),
        "toilets": eq(gdf, "amenity", "toilets"),
        "visitor_centre": eq(gdf, "tourism", "visitor_centre") | eq(gdf, "information", "visitor_centre"),
        "information_office": eq(gdf, "tourism", "information") & eq(gdf, "information", "office"),
        "viewpoint": eq(gdf, "tourism", "viewpoint"),
        "tourism": has_value(gdf, "tourism"),
        "waterfall": eq(gdf, "natural", "waterfall") | eq(gdf, "waterway", "waterfall"),
        "barrier": has_value(gdf, "barrier"),
        "emergency": emergency_any,
        "defibrillator": eq(gdf, "emergency", "defibrillator"),
        "fire_hydrant": eq(gdf, "emergency", "fire_hydrant"),
        "man_made": man_made_any,
        "survey_point": eq(gdf, "man_made", "survey_point") | has_value(gdf, "survey_point"),
        "summit_board": eq(gdf, "man_made", "summit_board"),
        "monitoring_station": has_value(gdf, "monitoring:gps") | has_value(gdf, "monitoring:weather"),
        "protected_area": eq(gdf, "boundary", "protected_area"),
        "national_park": eq(gdf, "boundary", "national_park"),
        "route_information": information_any,
        "spring": eq(gdf, "natural", "spring"),
        "hot_spring": eq(gdf, "natural", "hot_spring"),
        "volcano": eq(gdf, "natural", "volcano"),
        "obstacle": has_value(gdf, "obstacle"),
        "overgrown": has_value(gdf, "overgrown"),
        "hazard": has_value(gdf, "hazard"),
        "hiking_route": eq(gdf, "route", "hiking"),
        "foot_route": eq(gdf, "route", "foot"),
        "generic_context": (
            has_value(gdf, "amenity")
            | has_value(gdf, "tourism")
            | information_any
            | has_value(gdf, "natural")
            | man_made_any
            | has_value(gdf, "barrier")
            | emergency_any
            | has_value(gdf, "leisure")
        ),
    }

def prepare_layer_for_output(layer_name: str, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    layer = gdf.copy()
    if layer_name == "guide_map_attraction" and not layer.empty:
        layer["scenic_source_hint"] = "information_board_or_map"
    return layer


def write_layer(gdf: gpd.GeoDataFrame, out_fp: Path) -> int:
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    gdf = select_columns(gdf)
    gdf.to_file(out_fp, driver="GeoJSON")
    return len(gdf)


def _folium_outline(m: folium.Map, geometry, *, name: str, color: str, weight: int = 2, dash_array: str | None = None) -> None:
    if geometry is None or getattr(geometry, "is_empty", True):
        return
    style = {"color": color, "weight": weight, "fillOpacity": 0.0}
    if dash_array:
        style["dashArray"] = dash_array
    folium.GeoJson(
        mapping(geometry),
        name=name,
        style_function=lambda _feature, style=style: style,
    ).add_to(m)


def write_route_analysis_map(
    route_line: LineString,
    layers: dict[str, gpd.GeoDataFrame],
    out_fp: Path,
    *,
    analysis_geometry=None,
    tile_theoretical_geometry=None,
    tile_fetch_geometry=None,
) -> None:
    center = route_line.centroid
    m = folium.Map(location=[center.y, center.x], zoom_start=15, tiles="CartoDB positron")
    _folium_outline(
        m,
        tile_fetch_geometry,
        name="OSM TILE_FULL fetch extent (+buffer)",
        color="#7B1FA2",
        weight=2,
        dash_array="8 6",
    )
    _folium_outline(
        m,
        tile_theoretical_geometry,
        name="NLSC theoretical tile extent",
        color="#1565C0",
        weight=3,
    )
    _folium_outline(
        m,
        analysis_geometry,
        name="ROUTE_ANALYSIS_SUBSET extent",
        color="#FB8C00",
        weight=3,
        dash_array="5 5",
    )
    folium.GeoJson(route_line, name="activity GPX", style_function=lambda _: {"color": "#E53935", "weight": 4}).add_to(m)
    for name, gdf in layers.items():
        if gdf.empty:
            continue
        sample = gdf[gdf.geometry.notna()]
        if sample.empty:
            continue
        folium.GeoJson(sample, name=f"{name} ({len(sample)})").add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    m.save(out_fp)


def write_tile_full_highway_map(
    highway_gdf: gpd.GeoDataFrame,
    out_fp: Path,
    *,
    tile_theoretical_geometry=None,
    tile_fetch_geometry=None,
) -> None:
    focus = tile_theoretical_geometry or tile_fetch_geometry
    if focus is None or getattr(focus, "is_empty", True):
        return
    center = focus.centroid
    m = folium.Map(location=[center.y, center.x], zoom_start=13, tiles="CartoDB positron")
    _folium_outline(m, tile_fetch_geometry, name="OSM TILE_FULL fetch extent (+buffer)", color="#7B1FA2", weight=2, dash_array="8 6")
    _folium_outline(m, tile_theoretical_geometry, name="NLSC theoretical tile extent", color="#1565C0", weight=3)
    if highway_gdf is not None and not highway_gdf.empty:
        sample = highway_gdf[highway_gdf.geometry.notna()].copy()
        if not sample.empty:
            folium.GeoJson(sample, name=f"TILE_FULL highway ways ({len(sample)})").add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    m.save(out_fp)


def parse_osmium_tags_count(stdout: str, *, object_scope: str) -> list[dict]:
    rows = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        try:
            count = int(parts[0])
        except ValueError:
            continue
        key = parts[1].strip().strip('"').replace('""', '"')
        value = parts[2].strip().strip('"').replace('""', '"') if len(parts) >= 3 else None
        rows.append({"object_scope": object_scope, "count": count, "tag_key": key, "tag_value": value})
    return rows


def osmium_tag_match_total(
    osmium: str,
    pbf_fp: Path,
    expression: str,
    *,
    object_type: str | None,
    timeout: int,
) -> int:
    """Return the exact object count for one osmium tags-count expression.

    This is used for entity-level QA. It is intentionally separate from relation-member
    membership parsing because relations with no way members must still count as relations.
    """
    cmd = [osmium, "tags-count"]
    if object_type:
        cmd.extend(["-t", object_type])
    cmd.extend([str(pbf_fp), expression])
    result = run_command(cmd, timeout=timeout)
    return sum(row["count"] for row in parse_osmium_tags_count(result.stdout, object_scope=object_type or "all"))


def write_tile_dataset_qa(entry: dict | None, args: argparse.Namespace) -> dict:
    if not entry or entry.get("kind") != "nlsc_tile":
        return {}
    tile_pbf = resolve_indexed_path(entry.get("path"))
    semantic_pbf = resolve_indexed_path(entry.get("semantic_pbf"))
    if not tile_pbf or not semantic_pbf or not tile_pbf.exists() or not semantic_pbf.exists():
        return {}

    tile_dir = tile_pbf.parent
    qa_dir = tile_dir / "tile_qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    summary_fp = qa_dir / "osm_tile_full_highway_summary.csv"
    manifest_fp = qa_dir / "osm_tile_full_manifest.json"
    expected_geojson = qa_dir / "osm_tile_full_highway_ways.geojson"
    if manifest_fp.exists() and summary_fp.exists() and not args.force_refresh:
        try:
            cached = json.loads(manifest_fp.read_text(encoding="utf-8"))
            cache_schema_ok = cached.get("qa_schema") == TILE_QA_SCHEMA
            relation_qa_ok = isinstance(cached.get("route_relation_entities"), dict)
            optional_map_ok = (not args.write_tile_full_highway_geojson) or expected_geojson.exists()
            if cache_schema_ok and relation_qa_ok and optional_map_ok:
                return cached
        except Exception:
            pass
    osmium = require_osmium(args)

    rows: list[dict] = []
    for scope, obj_type in [("all", None), ("way", "way"), ("node", "node"), ("relation", "relation")]:
        cmd = [osmium, "tags-count"]
        if obj_type:
            cmd.extend(["-t", obj_type])
        cmd.extend(["--sort=name-asc", str(semantic_pbf), "highway=*"])
        result = run_command(cmd, timeout=args.download_timeout)
        rows.extend(parse_osmium_tags_count(result.stdout, object_scope=scope))

    pd.DataFrame(rows, columns=["object_scope", "tag_key", "tag_value", "count"]).to_csv(
        summary_fp, index=False, encoding="utf-8-sig"
    )

    all_total = sum(r["count"] for r in rows if r["object_scope"] == "all")
    way_total = sum(r["count"] for r in rows if r["object_scope"] == "way")
    node_total = sum(r["count"] for r in rows if r["object_scope"] == "node")
    relation_total = sum(r["count"] for r in rows if r["object_scope"] == "relation")

    # Entity-level route QA. Count raw and semantic relation entities independently from
    # member-way enrichment so relations with zero way members are never silently omitted.
    route_relation_entities: dict[str, dict] = {}
    for route in ("hiking", "foot"):
        expression = f"route={route}"
        raw_count = osmium_tag_match_total(
            osmium, tile_pbf, expression, object_type="relation", timeout=args.download_timeout
        )
        semantic_count = osmium_tag_match_total(
            osmium, semantic_pbf, expression, object_type="relation", timeout=args.download_timeout
        )
        route_relation_entities[route] = {
            "raw_relation_entities": raw_count,
            "semantic_relation_entities": semantic_count,
            "semantic_retention_status": "PASS" if raw_count == semantic_count else "FAIL",
        }

    optional_geojson = None
    if args.write_tile_full_highway_geojson:
        highway_pbf = qa_dir / "osm_tile_full_highway_ways.osm.pbf"
        highway_geojson = qa_dir / "osm_tile_full_highway_ways.geojson"
        run_command(
            [osmium, "tags-filter", str(semantic_pbf), "w/highway", "-O", "-o", str(highway_pbf)],
            timeout=args.download_timeout,
        )
        run_command(
            [osmium, "export", str(highway_pbf), "-f", "geojson", "-O", "-o", str(highway_geojson)],
            timeout=args.download_timeout,
        )
        optional_geojson = portable_path(highway_geojson)
        try:
            highway_gdf = gpd.read_file(highway_geojson)
            theoretical_bbox = entry.get("tile_theoretical_bbox")
            fetch_bbox = entry.get("coverage_bbox")
            theoretical_geom = box(*theoretical_bbox) if theoretical_bbox and len(theoretical_bbox) == 4 else None
            fetch_geom = box(*fetch_bbox) if fetch_bbox and len(fetch_bbox) == 4 else None
            write_tile_full_highway_map(
                highway_gdf,
                qa_dir / "osm_tile_full_highway_map.html",
                tile_theoretical_geometry=theoretical_geom,
                tile_fetch_geometry=fetch_geom,
            )
        except Exception as exc:
            print(f"WARNING: TILE_FULL highway GeoJSON exported but HTML QA map could not be written: {exc}")

    qa = {
        "qa_schema": TILE_QA_SCHEMA,
        "data_scope": "TILE_FULL",
        "dataset_id": entry.get("dataset_id"),
        "nlsc_tiles": entry.get("nlsc_tiles"),
        "tile_dataset_profile": entry.get("tile_dataset_profile"),
        "extract_strategy": entry.get("extract_strategy"),
        "relation_completion_profile": entry.get("relation_completion_profile"),
        "tile_theoretical_bbox": entry.get("tile_theoretical_bbox"),
        "osm_fetch_bbox": entry.get("coverage_bbox"),
        "bbox_buffer_m": entry.get("bbox_buffer_m"),
        "raw_pbf": portable_path(tile_pbf),
        "semantic_pbf": portable_path(semantic_pbf),
        "highway_summary_csv": portable_path(summary_fp),
        "highway_tagged_objects_total": all_total,
        "highway_way_total": way_total,
        "highway_node_total": node_total,
        "highway_relation_total": relation_total,
        "route_relation_entities": route_relation_entities,
        "optional_highway_way_geojson": optional_geojson,
        "optional_highway_map": portable_path(qa_dir / "osm_tile_full_highway_map.html") if (qa_dir / "osm_tile_full_highway_map.html").exists() else None,
        "attribution": entry.get("attribution") or OSM_ATTRIBUTION,
        "license": entry.get("license") or OSM_LICENSE,
        "generated_at": utc_now_iso(),
        "script_version": VERSION,
    }
    atomic_write_json(manifest_fp, qa)
    return qa




def export_tag_summary(gdf: gpd.GeoDataFrame, out_csv: Path) -> None:
    ignore_cols = {"geometry", "osm_type", "osm_id"}
    rows = []
    if not gdf.empty:
        for col in gdf.columns:
            if col in ignore_cols:
                continue
            vc = gdf[col].dropna().astype(str).value_counts()
            for value, count in vc.items():
                if str(value).strip().lower() in {"", "nan", "none", "<na>", "null"}:
                    continue
                rows.append({"tag_key": col, "tag_value": value, "count": int(count)})
    pd.DataFrame(rows, columns=["tag_key", "tag_value", "count"]).sort_values(
        ["tag_key", "count"], ascending=[True, False]
    ).to_csv(out_csv, index=False, encoding="utf-8-sig")


def main() -> None:
    args = parse_args()

    case_id = args.case_id
    activity_fp = resolve_path(args.activity_fp)
    if not activity_fp.exists():
        raise FileNotFoundError(activity_fp)

    data_dir = resolve_path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    index_fp = resolve_path(args.dataset_index) if args.dataset_index else data_dir / "osm_dataset_index.json"
    nlsc_raw_dir = resolve_path(args.nlsc_raw_dir)
    nlsc_tile_index_fp = (
        resolve_path(args.nlsc_tile_index)
        if args.nlsc_tile_index
        else data_dir / "tile_index" / "nlsc_tile_index.csv"
    )
    out_dir = resolve_path(args.out_dir) if args.out_dir else PROJECT_ROOT / "osm_raw_output" / case_id
    out_dir.mkdir(parents=True, exist_ok=True)

    highway_fp = out_dir / EXPECTED_LAYERS["highway"]
    manifest_fp = out_dir / "osm_raw_fetch_manifest.csv"
    if highway_fp.exists() and manifest_matches_current_version(manifest_fp) and not args.force_refresh:
        print(f"Existing IA1 output matches current script version, skip: {out_dir}")
        print("Use --force-refresh only with an explicit reason.")
        return

    # ------------------------------------------------------------------
    # Phase 0: GPX first. No OSM network request is possible before this
    # phase completes and the NLSC tile authority is resolved.
    # ------------------------------------------------------------------
    route_line = parse_gpx_line(activity_fp)
    route_probe = build_gpx_route_probe(route_line, anchor_count=args.coverage_anchor_count)
    route_anchor_points = probe_anchor_points(route_probe)
    query_geometry = route_buffer_geometry(route_line, args.buffer_m, simplify_m=args.buffer_simplify_m)
    bbox = geometry_bbox(query_geometry)
    fetched_at = utc_now_iso()

    tile_index = load_nlsc_tile_index(
        nlsc_raw_dir,
        nlsc_tile_index_fp,
        rebuild=args.rebuild_nlsc_tile_index,
    )
    tile_matches = find_nlsc_tiles_for_route_bbox(tuple(route_probe["route_bbox"]), tile_index)
    nlsc_tile_ids = [item["tile_id"] for item in tile_matches]
    tile_theoretical_geometry, tile_fetch_geometry = build_nlsc_tile_geometry(
        tile_matches,
        args.tile_fetch_buffer_m,
    )

    write_gpx_route_probe(
        route_probe,
        out_dir / "gpx_route_probe.json",
        case_id=case_id,
        activity_fp=activity_fp,
        analysis_geometry=query_geometry,
        dataset_geometry=tile_fetch_geometry,
        nlsc_tiles=nlsc_tile_ids,
        nlsc_tile_theoretical_geometry=tile_theoretical_geometry,
        tile_fetch_buffer_m=args.tile_fetch_buffer_m,
    )
    print_gpx_route_probe(route_probe)

    # ------------------------------------------------------------------
    # Phase 1: local inventory first: indexed PBF datasets + legacy IA1
    # semantic bundles. This phase is offline.
    # ------------------------------------------------------------------
    index = load_dataset_index(index_fp)
    local_user_agent = build_user_agent(args, require_contact=False)
    configure_osmnx(args, local_user_agent)

    print("CASE_ID:", case_id)
    print("activity_fp:", activity_fp)
    print("coverage search order: GPX -> NLSC tile authority -> indexed local PBF -> legacy IA1 bundles -> explicit network only")
    print("out_dir:", out_dir)
    print("analysis bbox west,south,east,north:", bbox)
    print("analysis buffer_m:", args.buffer_m)
    print("NLSC tiles:", ", ".join(nlsc_tile_ids))
    print("NLSC theoretical bbox:", geometry_bbox(tile_theoretical_geometry))
    print("tile fetch buffer_m:", args.tile_fetch_buffer_m)
    print("OSM tile fetch bbox:", geometry_bbox(tile_fetch_geometry))
    print("source mode:", args.source)
    print("dataset index:", index_fp)
    print("NLSC tile index:", nlsc_tile_index_fp)

    discover_local_pbfs(data_dir, index, args)
    if args.sync_taiwan_pbf:
        # Explicit network action requested by the operator.
        sync_taiwan_pbf(data_dir, index, args, local_user_agent)
    save_dataset_index(index_fp, index)

    indexed_analysis_entry, indexed_analysis_state = choose_covering_dataset(
        index,
        query_geometry,
        case_id=case_id,
        allowed_kinds={"nlsc_tile", "route_area", "overpass_snapshot"},
        allow_unvalidated_shared=args.allow_unvalidated_shared,
        anchor_points=route_anchor_points,
        required_tile_profile=tile_dataset_profile(args),
    )
    indexed_tile_entry, indexed_tile_state = choose_covering_dataset(
        index,
        tile_fetch_geometry,
        case_id=case_id,
        allowed_kinds={"nlsc_tile", "route_area", "overpass_snapshot"},
        allow_unvalidated_shared=args.allow_unvalidated_shared,
        anchor_points=None,
        required_tile_profile=tile_dataset_profile(args),
    )

    legacy_bundles = discover_legacy_bundles(args, current_out_dir=out_dir)
    legacy_selected, legacy_rows = choose_legacy_bundle(
        legacy_bundles,
        query_geometry,
        tile_fetch_geometry,
    )

    print_local_coverage_report(
        tile_ids=nlsc_tile_ids,
        tile_theoretical_geometry=tile_theoretical_geometry,
        tile_fetch_geometry=tile_fetch_geometry,
        indexed_analysis=indexed_analysis_state,
        indexed_tile=indexed_tile_state,
        legacy_rows=legacy_rows,
    )

    raw: gpd.GeoDataFrame
    source_info: dict
    selected_entry: dict | None = None
    selected_legacy: dict | None = None
    created_snapshot_entry: dict | None = None
    coverage_decision = "NONE"
    overpass_used_endpoints: set[str] = set()
    overpass_base_timestamps: set[str] = set()
    route_relation_memberships = empty_route_relation_memberships()
    route_relation_parse_available = False

    # ------------------------------------------------------------------
    # Phase 2: choose an existing local source. TILE_FULL is preferred,
    # but ANALYSIS_FULL is sufficient for the current route case.
    # ------------------------------------------------------------------
    if args.source in {"auto", "local"}:
        selected_entry = indexed_tile_entry or indexed_analysis_entry
        if selected_entry is not None:
            if indexed_tile_entry is not None and selected_entry.get("dataset_id") == indexed_tile_entry.get("dataset_id"):
                coverage_decision = "TILE_FULL"
            else:
                coverage_decision = "ANALYSIS_FULL"
            print(
                f"LOCAL INDEXED {coverage_decision}: {selected_entry.get('dataset_id')} "
                f"kind={selected_entry.get('kind')}"
            )
            raw, route_relation_memberships, route_relation_parse_available = load_features_from_local_dataset(selected_entry, query_geometry, data_dir, args)
            source_info = source_descriptor(selected_entry, source_kind="local_pbf")
        elif legacy_selected is not None:
            selected_legacy = legacy_selected
            coverage_decision = (
                "TILE_FULL_LEGACY" if legacy_selected.get("tile_coverage") == "FULL" else "ANALYSIS_FULL_LEGACY"
            )
            print(
                f"LOCAL LEGACY {coverage_decision}: {legacy_selected.get('folder_name')} "
                f"route_id={legacy_selected.get('route_id')}"
            )
            raw = load_features_from_legacy_bundle(legacy_selected, query_geometry)
            source_info = {
                "source_kind": "legacy_ia1_bundle",
                "dataset_id": legacy_selected.get("dataset_id"),
                "source_dataset_id": legacy_selected.get("dataset_id"),
                "source_url": None,
                "source_sha256": None,
                "osm_base_timestamp": None,
                "fetched_at": legacy_selected.get("fetched_at") or fetched_at,
            }
        else:
            # No reusable processed dataset. See whether a parent/master PBF can create the
            # authoritative NLSC tile cache locally.
            parent_entry, parent_state = choose_covering_dataset(
                index,
                tile_fetch_geometry,
                case_id=case_id,
                allowed_kinds={"taiwan_snapshot", "local_pbf"},
                allow_unvalidated_shared=True,
                anchor_points=None,
            )
            if parent_entry:
                print(
                    f"LOCAL PARENT TILE COVERAGE FULL: {parent_entry.get('dataset_id')} -> build/reuse NLSC tile cache"
                )
                selected_entry = build_nlsc_tile_dataset(
                    parent_entry,
                    nlsc_tile_ids,
                    tile_theoretical_geometry,
                    tile_fetch_geometry,
                    data_dir,
                    index,
                    args,
                )
                coverage_decision = "TILE_FULL"
                save_dataset_index(index_fp, index)
                raw, route_relation_memberships, route_relation_parse_available = load_features_from_local_dataset(selected_entry, query_geometry, data_dir, args)
                source_info = source_descriptor(selected_entry, source_kind="local_pbf")
            else:
                if parent_state == "PARTIAL" or indexed_analysis_state == "PARTIAL" or indexed_tile_state == "PARTIAL":
                    print("LOCAL COVERAGE PARTIAL: nearby local data exists but does not fully cover the required analysis/tile geometry.")
                else:
                    print("LOCAL COVERAGE NONE: no trusted local dataset fully covers the required analysis buffer.")
                raw = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
                source_info = {}

        if raw.empty and selected_entry is not None:
            raise RuntimeError("Selected local PBF dataset contains no usable features in the current analysis polygon.")
        if raw.empty and selected_legacy is not None:
            raise RuntimeError("Selected legacy IA1 bundle contains no usable features in the current analysis polygon.")

        if selected_entry is None and selected_legacy is None:
            if args.source == "local":
                raise RuntimeError(
                    "--source local requested, but no trusted local dataset provides ANALYSIS_FULL coverage. "
                    "No network request was sent."
                )
            if not args.allow_overpass_fallback:
                raise RuntimeError(
                    "Local coverage is not ANALYSIS_FULL. v1.5.6 default policy is offline/local-first, so no network request was sent. "
                    "To create a durable tile dataset, explicitly use --sync-taiwan-pbf; for a small one-off query, explicitly add "
                    "--allow-overpass-fallback with valid --contact information."
                )
    else:
        raw = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
        source_info = {}

    # ------------------------------------------------------------------
    # Phase 3: Overpass is explicit only. It remains an ANALYSIS-buffer
    # query, not a TILE_FULL authority dataset.
    # ------------------------------------------------------------------
    if selected_entry is None and selected_legacy is None and args.source in {"auto", "overpass"}:
        if args.source == "auto" and not args.allow_overpass_fallback:
            raise RuntimeError("Internal safety guard: auto Overpass fallback was not explicitly allowed.")
        overpass_user_agent = build_user_agent(args, require_contact=True)
        configure_osmnx(args, overpass_user_agent)
        endpoints = overpass_endpoints(args)
        cache_dir = data_dir / "overpass_cache"
        lock_fp = resolve_path(args.overpass_lock_file) if args.overpass_lock_file else data_dir / ".overpass.lock"
        print("OVERPASS EXPLICIT FALLBACK: ANALYSIS route-buffer query only; result is not TILE_FULL")
        print("overpass endpoints:", endpoints)
        print("user_agent:", overpass_user_agent)
        raw, overpass_used_endpoints, overpass_base_timestamps = fetch_grouped_features_governed(
            query_geometry,
            osm_tag_groups(args.tag_profile),
            endpoints=endpoints,
            cache_dir=cache_dir,
            lock_fp=lock_fp,
            user_agent=overpass_user_agent,
            args=args,
        )
        dataset_seed = json.dumps(
            {
                "case_id": case_id,
                "bbox": bbox,
                "buffer_m": args.buffer_m,
                "tag_profile": args.tag_profile,
                "fetched_at": fetched_at,
            },
            sort_keys=True,
        ).encode("utf-8")
        overpass_dataset_id = f"overpass_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{sha256_bytes(dataset_seed)[:10]}"
        source_info = {
            "source_kind": "overpass",
            "dataset_id": overpass_dataset_id,
            "source_dataset_id": None,
            "source_url": ";".join(sorted(overpass_used_endpoints)) or ";".join(endpoints),
            "source_sha256": None,
            "osm_base_timestamp": ";".join(sorted(overpass_base_timestamps)) or None,
            "fetched_at": fetched_at,
        }
        coverage_decision = "ANALYSIS_FULL_QUERY_POLYGON"

    if raw.empty:
        raise RuntimeError("OSM source returned no features for this GPX analysis polygon.")

    raw = raw[raw.geometry.notna()].copy()
    if raw.crs is None:
        raw = raw.set_crs("EPSG:4326")

    dataset_id = source_info.get("dataset_id") or case_id
    raw = add_metadata(
        raw,
        case_id,
        source_info.get("fetched_at") or fetched_at,
        dataset_id=dataset_id,
        source_kind=source_info.get("source_kind") or "unknown",
        source_url=source_info.get("source_url"),
        source_dataset_id=source_info.get("source_dataset_id"),
        source_sha256=source_info.get("source_sha256"),
        osm_base_timestamp=source_info.get("osm_base_timestamp"),
        coverage_status=coverage_decision,
    )
    identity_type_count = int(raw["osm_type"].notna().sum()) if "osm_type" in raw.columns else 0
    identity_id_count = int(raw["osm_id"].notna().sum()) if "osm_id" in raw.columns else 0
    print("OSM_IDENTITY_QA")
    print(f"  osm_type populated: {identity_type_count}/{len(raw)}")
    print(f"  osm_id populated: {identity_id_count}/{len(raw)}")
    raw = normalize_highway(raw)

    if source_info.get("source_kind") == "overpass":
        created_snapshot_entry, source_info = save_overpass_immutable_snapshot(
            raw,
            dataset_id=dataset_id,
            case_id=case_id,
            query_geometry=query_geometry,
            data_dir=data_dir,
            source_info=source_info,
            args=args,
            index=index,
        )
        raw["source_sha256"] = source_info.get("source_sha256")
        save_dataset_index(index_fp, index)

    # TILE_FULL is the durable regional data product. The GeoJSON files below are explicitly
    # ROUTE_ANALYSIS_SUBSET outputs clipped to the current GPX analysis polygon.
    tile_qa = write_tile_dataset_qa(selected_entry, args)

    if tile_qa and isinstance(tile_qa.get("route_relation_entities"), dict):
        print("TILE_RELATION_RETENTION_QA")
        for route in ("hiking", "foot"):
            item = tile_qa["route_relation_entities"].get(route, {})
            print(
                f"  route={route} raw_relation_entities={item.get('raw_relation_entities')} "
                f"semantic_relation_entities={item.get('semantic_relation_entities')} "
                f"retention={item.get('semantic_retention_status')}"
            )

    route_relation_layers: dict[str, gpd.GeoDataFrame] = {}
    route_relation_qa_rows: list[dict] = []
    if route_relation_parse_available:
        tile_relation_entity_counts = {}
        if tile_qa and isinstance(tile_qa.get("route_relation_entities"), dict):
            for route in ("hiking", "foot"):
                item = tile_qa["route_relation_entities"].get(route, {})
                tile_relation_entity_counts[route] = item.get("semantic_relation_entities")
        route_relation_layers, route_relation_qa_rows = build_route_relation_member_layers(
            raw, route_relation_memberships, tile_relation_entity_counts=tile_relation_entity_counts
        )
        relation_summary_fp = out_dir / "osm_route_relation_member_summary.csv"
        pd.DataFrame(route_relation_qa_rows).to_csv(relation_summary_fp, index=False, encoding="utf-8-sig")
        membership_analysis_rows = []
        for layer_name in ("hiking_route", "foot_route"):
            layer = route_relation_layers.get(layer_name)
            if layer is not None and not layer.empty:
                cols = [
                    c for c in [
                        "route_relation_id", "route_relation_route", "route_relation_name",
                        "route_relation_ref", "route_relation_network", "route_relation_osmc_symbol",
                        "route_relation_symbol", "route_relation_colour", "route_relation_member_role",
                        "route_relation_member_sequence", "osm_id", "member_way_name"
                    ] if c in layer.columns
                ]
                membership_analysis_rows.append(pd.DataFrame(layer[cols]).assign(layer_name=layer_name))
        if membership_analysis_rows:
            pd.concat(membership_analysis_rows, ignore_index=True).to_csv(
                out_dir / "osm_route_relation_memberships_analysis.csv",
                index=False,
                encoding="utf-8-sig",
            )
        print("ROUTE_RELATION_MEMBER_QA")
        for row in route_relation_qa_rows:
            print(
                f"  route={row['route']} tile_relation_entities={row['tile_relation_entities']} "
                f"relations_with_way_members={row['relations_with_way_members']} "
                f"relations_without_way_members={row['relations_without_way_members']} "
                f"analysis_touching_relations={row['analysis_touching_relation_count']} "
                f"analysis_unique_member_ways={row['analysis_unique_member_way_count']} "
                f"analysis_membership_features={row['analysis_relation_member_feature_count']}"
            )

    masks = layer_masks(raw)
    layer_summary = []
    written_layers = {}
    tile_theoretical_bbox = geometry_bbox(tile_theoretical_geometry)
    tile_fetch_bbox = geometry_bbox(tile_fetch_geometry)
    nlsc_tile_text = ";".join(nlsc_tile_ids)
    for layer_name, filename in EXPECTED_LAYERS.items():
        if route_relation_parse_available and layer_name in {"hiking_route", "foot_route"}:
            layer = route_relation_layers.get(
                layer_name, gpd.GeoDataFrame(geometry=[], crs=raw.crs or "EPSG:4326")
            ).copy()
        else:
            layer = raw[masks.get(layer_name, pd.Series(False, index=raw.index))].copy()
        layer = prepare_layer_for_output(layer_name, layer)
        count = write_layer(layer, out_dir / filename)
        written_layers[layer_name] = layer
        layer_summary.append(
            {
                "route_id": case_id,
                "osm_dataset_id": dataset_id,
                "source_kind": source_info.get("source_kind"),
                "source_dataset_id": source_info.get("source_dataset_id"),
                "source_url": source_info.get("source_url"),
                "source_sha256": source_info.get("source_sha256"),
                "osm_base_timestamp": source_info.get("osm_base_timestamp"),
                "coverage_status": coverage_decision,
                "data_scope": "ROUTE_ANALYSIS_SUBSET",
                "source_tile_data_scope": "TILE_FULL" if selected_entry and selected_entry.get("kind") == "nlsc_tile" else None,
                "nlsc_tile": nlsc_tile_text,
                "tile_authority": "NLSC_THEORETICAL_GRID",
                "tile_bbox_west": tile_theoretical_bbox[0],
                "tile_bbox_south": tile_theoretical_bbox[1],
                "tile_bbox_east": tile_theoretical_bbox[2],
                "tile_bbox_north": tile_theoretical_bbox[3],
                "osm_fetch_bbox_west": tile_fetch_bbox[0],
                "osm_fetch_bbox_south": tile_fetch_bbox[1],
                "osm_fetch_bbox_east": tile_fetch_bbox[2],
                "osm_fetch_bbox_north": tile_fetch_bbox[3],
                "bbox_buffer_m": args.tile_fetch_buffer_m,
                "layer_name": layer_name,
                "filename": filename,
                "feature_count": count,
                "bbox_west": bbox[0],
                "bbox_south": bbox[1],
                "bbox_east": bbox[2],
                "bbox_north": bbox[3],
                "buffer_m": args.buffer_m,
                "dataset_buffer_m": None,
                "buffer_simplify_m": args.buffer_simplify_m,
                "fetched_at": source_info.get("fetched_at") or fetched_at,
                "overpass_url": ";".join(sorted(overpass_used_endpoints)) if overpass_used_endpoints else None,
                "script_version": VERSION,
                "script_status": STATUS,
                "force_refresh_reason": args.force_refresh_reason,
                "attribution": OSM_ATTRIBUTION,
                "license": OSM_LICENSE,
            }
        )
        print(f"{filename}: {count}")

    summary_df = pd.DataFrame(layer_summary)
    summary_df.to_csv(out_dir / "osm_raw_layer_summary.csv", index=False, encoding="utf-8-sig")
    summary_df.to_csv(manifest_fp, index=False, encoding="utf-8-sig")
    export_tag_summary(
        written_layers.get("generic_context", raw.iloc[0:0].copy()),
        out_dir / "osm_generic_tag_summary.csv",
    )

    highway_layer = written_layers.get("highway", raw.iloc[0:0].copy())
    connectivity_qa = run_basic_connectivity_qa(route_line, highway_layer, args)
    dataset_manifest = {
        "route_id": case_id,
        "osm_dataset_id": dataset_id,
        "source_kind": source_info.get("source_kind"),
        "source_dataset_id": source_info.get("source_dataset_id"),
        "source_url": source_info.get("source_url"),
        "source_sha256": source_info.get("source_sha256"),
        "osm_base_timestamp": source_info.get("osm_base_timestamp"),
        "fetched_at": source_info.get("fetched_at") or fetched_at,
        "data_scope": "ROUTE_ANALYSIS_SUBSET",
        "analysis_bbox": list(bbox),
        "analysis_buffer_m": args.buffer_m,
        "source_tile_data_scope": "TILE_FULL" if selected_entry and selected_entry.get("kind") == "nlsc_tile" else None,
        "source_tile_dataset_profile": selected_entry.get("tile_dataset_profile") if selected_entry else None,
        "source_tile_extract_strategy": selected_entry.get("extract_strategy") if selected_entry else None,
        "source_tile_relation_completion_profile": selected_entry.get("relation_completion_profile") if selected_entry else None,
        "nlsc_tiles": nlsc_tile_ids,
        "tile_authority": "NLSC_THEORETICAL_GRID",
        "tile_theoretical_bbox": list(tile_theoretical_bbox),
        "osm_fetch_bbox": list(tile_fetch_bbox),
        "bbox_buffer_m": args.tile_fetch_buffer_m,
        "tile_full_qa": tile_qa or None,
        "route_relation_member_qa": route_relation_qa_rows or None,
        "route_relation_member_summary_csv": portable_path(out_dir / "osm_route_relation_member_summary.csv") if route_relation_qa_rows else None,
        "route_relation_memberships_analysis_csv": portable_path(out_dir / "osm_route_relation_memberships_analysis.csv") if (out_dir / "osm_route_relation_memberships_analysis.csv").exists() else None,
        "map_outputs": {
            "route_analysis_map": portable_path(out_dir / "osm_route_analysis_layers_map.html") if not args.no_map else None,
            "legacy_route_analysis_map_alias": portable_path(out_dir / "osm_raw_layers_map.html") if not args.no_map else None,
            "tile_full_highway_qa_map": tile_qa.get("optional_highway_map") if tile_qa else None,
        },
        "coverage_status": coverage_decision,
        "script_version": VERSION,
        "script_status": STATUS,
        "attribution": OSM_ATTRIBUTION,
        "license": OSM_LICENSE,
        "copyright_url": OSM_COPYRIGHT_URL,
        "connectivity_qa": connectivity_qa,
        "force_refresh": bool(args.force_refresh),
        "force_refresh_reason": args.force_refresh_reason,
        "legacy_identity_status": selected_legacy.get("identity_status") if selected_legacy else None,
        "legacy_manifest": portable_path(selected_legacy["manifest_fp"]) if selected_legacy else None,
        "osm_base_timestamp_consistency": (
            "SINGLE" if len(overpass_base_timestamps) <= 1 else "MIXED_OVERPASS_RESPONSES"
        ) if source_info.get("source_kind") == "overpass" else "SNAPSHOT_OR_LOCAL",
    }
    atomic_write_json(out_dir / "osm_dataset_manifest.json", dataset_manifest)
    atomic_write_json(out_dir / "osm_dataset_qa.json", connectivity_qa)

    qa_entry = created_snapshot_entry or selected_entry
    if qa_entry and qa_entry.get("kind") in {"route_area", "overpass_snapshot"}:
        update_route_area_connectivity_qa(index, qa_entry.get("dataset_id"), connectivity_qa)
        save_dataset_index(index_fp, index)

    if not args.no_map:
        route_map_fp = out_dir / "osm_route_analysis_layers_map.html"
        write_route_analysis_map(
            route_line,
            written_layers,
            route_map_fp,
            analysis_geometry=query_geometry,
            tile_theoretical_geometry=tile_theoretical_geometry,
            tile_fetch_geometry=tile_fetch_geometry,
        )
        # Backward-compatible alias for existing review links. The formal v1.5.6 name is
        # osm_route_analysis_layers_map.html so TILE_FULL and route-subset semantics are not confused.
        shutil.copy2(route_map_fp, out_dir / "osm_raw_layers_map.html")
        print("MAP_OUTPUTS")
        print("  ROUTE_ANALYSIS:", route_map_fp)
        if tile_qa and tile_qa.get("optional_highway_map"):
            print("  TILE_FULL highway QA:", tile_qa.get("optional_highway_map"))
        else:
            print("  TILE_FULL highway QA: not written (opt-in with --write-tile-full-highway-geojson)")

    if not highway_fp.exists() or summary_df.loc[
        summary_df["layer_name"].eq("highway"), "feature_count"
    ].iloc[0] == 0:
        raise RuntimeError("Core layer osm_highway_raw.geojson is empty; downstream route matching cannot continue.")

    print("DATA_SCOPE: ROUTE_ANALYSIS_SUBSET")
    print("ROUTE_ANALYSIS highway features:", len(highway_layer))
    if tile_qa:
        print("TILE_DATA_SCOPE: TILE_FULL")
        print("TILE highway tagged objects:", tile_qa.get("highway_tagged_objects_total"))
        print("TILE highway ways:", tile_qa.get("highway_way_total"))
        print("TILE relation completion:", tile_qa.get("relation_completion_profile"))
    print("SOURCE:", source_info.get("source_kind"))
    print("DATASET_ID:", dataset_id)
    print("NLSC_TILES:", nlsc_tile_text)
    print("COVERAGE:", coverage_decision)
    print("CONNECTIVITY_QA:", connectivity_qa.get("status"), connectivity_qa.get("reason"))
    print("Done:", out_dir)


if __name__ == "__main__":
    main()
