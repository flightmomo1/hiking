from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import time
import xml.etree.ElementTree as ET

import folium
import geopandas as gpd
import osmnx as ox
import pandas as pd
from osmnx._errors import InsufficientResponseError
from shapely.geometry import LineString


PROJECT_ROOT = Path("C:/mountain_work/115_osm")

VERSION = "v1.4.5-friendly-qixing-route-buffer-v1.3-schema"
STATUS = "GPX route-buffer polygon + simplified Overpass poly query + cache-aware + optional Overpass status skip + Qixing v1.3 route semantics restored + mixed OSM feature safe normalization"

DEFAULT_USER_AGENT = (
    "115_osm_route_risk/0.1 "
    "(research prototype; local pipeline; contact: please-configure-email)"
)

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
    "geometry",
    "route_id",
    "osm_dataset_id",
    "source_name",
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
        description="Friendly ia1 OSM raw fetcher: GPX route-buffer polygon, grouped Overpass query, cache-aware outputs."
    )
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--activity-fp", required=True)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--buffer-m", type=float, default=700.0)
    parser.add_argument(
        "--buffer-simplify-m",
        type=float,
        default=15.0,
        help="Simplify the metric route-buffer polygon before sending it to Overpass.",
    )
    parser.add_argument("--overpass-url", default=None)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--retry", type=int, default=2)
    parser.add_argument("--sleep-sec", type=float, default=5.0)
    parser.add_argument(
        "--tag-profile",
        choices=["core", "pipeline"],
        default="pipeline",
        help="core fetches only highway; pipeline fetches grouped route/hydro/terrain/technical/POI layers.",
    )
    parser.add_argument("--no-map", action="store_true")
    parser.add_argument(
        "--no-overpass-rate-limit",
        action="store_true",
        help="Skip OSMnx Overpass /status preflight; useful when a public mirror's status endpoint is slow.",
    )
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


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


def route_buffer_geometry(line: LineString, buffer_m: float, simplify_m: float = 15.0):
    route_gdf = gpd.GeoDataFrame([{"geometry": line}], geometry="geometry", crs="EPSG:4326")
    metric_crs = route_gdf.estimate_utm_crs()
    buffered = route_gdf.to_crs(metric_crs).geometry.iloc[0].buffer(buffer_m)
    if simplify_m and simplify_m > 0:
        buffered = buffered.simplify(simplify_m, preserve_topology=True)
    return gpd.GeoSeries([buffered], crs=metric_crs).to_crs("EPSG:4326").iloc[0]


def geometry_bbox(geometry) -> tuple[float, float, float, float]:
    west, south, east, north = geometry.bounds
    return (west, south, east, north)


def route_buffer_bbox(line: LineString, buffer_m: float) -> tuple[float, float, float, float]:
    buffered_wgs84 = route_buffer_geometry(line, buffer_m)
    west, south, east, north = buffered_wgs84.bounds
    return (west, south, east, north)


def configure_osmnx(args: argparse.Namespace) -> None:
    ox.settings.use_cache = True
    ox.settings.cache_folder = str(PROJECT_ROOT / "osmnx_cache")
    ox.settings.log_console = True
    ox.settings.requests_timeout = args.timeout
    ox.settings.http_user_agent = args.user_agent
    ox.settings.requests_kwargs = {}
    ox.settings.overpass_rate_limit = not args.no_overpass_rate_limit
    ox.settings.overpass_settings = f"[out:json][timeout:{args.timeout}]"
    if args.overpass_url:
        ox.settings.overpass_url = args.overpass_url


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
                    "route": "hiking",
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


def fetch_features(query_geometry, tags: dict, retry: int, sleep_sec: float) -> gpd.GeoDataFrame:
    last_error = None
    for attempt in range(1, retry + 2):
        try:
            return ox.features_from_polygon(query_geometry, tags=tags)
        except InsufficientResponseError:
            return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
        except Exception as exc:
            last_error = exc
            if attempt <= retry:
                wait = sleep_sec * attempt
                print(f"Overpass fetch failed on attempt {attempt}: {exc}. retry in {wait:.1f}s")
                time.sleep(wait)
    raise RuntimeError(f"Overpass fetch failed after {retry + 1} attempts: {last_error}") from last_error


def fetch_grouped_features(
    query_geometry,
    groups: list[tuple[str, dict[str, bool | str | list[str]]]],
    retry: int,
    sleep_sec: float,
) -> gpd.GeoDataFrame:
    frames = []
    for group_name, tags in groups:
        print(f"Fetching OSM group: {group_name} tags={tags}")
        try:
            gdf = fetch_features(query_geometry, tags, retry=retry, sleep_sec=sleep_sec)
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
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    combined = pd.concat(frames)
    if isinstance(combined.index, pd.MultiIndex):
        combined = combined[~combined.index.duplicated(keep="first")]
    else:
        combined = combined.drop_duplicates(subset=["geometry"], keep="first")
    return gpd.GeoDataFrame(combined, geometry="geometry", crs=frames[0].crs)


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


def add_metadata(gdf: gpd.GeoDataFrame, case_id: str, fetched_at: str) -> gpd.GeoDataFrame:
    gdf = gdf.copy()
    if isinstance(gdf.index, pd.MultiIndex):
        gdf = gdf.reset_index()
    for col in ["element_type", "osmid"]:
        if col in gdf.columns:
            pass
    if "osm_type" not in gdf.columns and "element_type" in gdf.columns:
        gdf["osm_type"] = gdf["element_type"]
    if "osm_id" not in gdf.columns and "osmid" in gdf.columns:
        gdf["osm_id"] = gdf["osmid"]
    gdf["route_id"] = case_id
    gdf["osm_dataset_id"] = case_id
    gdf["source_name"] = "OpenStreetMap"
    gdf["fetched_at"] = fetched_at
    gdf["pipeline_stage"] = "ia1_osm_fetch_raw_friendly"
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


def write_map(route_line: LineString, layers: dict[str, gpd.GeoDataFrame], out_fp: Path) -> None:
    center = route_line.centroid
    m = folium.Map(location=[center.y, center.x], zoom_start=15, tiles="CartoDB positron")
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
    configure_osmnx(args)

    case_id = args.case_id
    activity_fp = resolve_path(args.activity_fp)
    out_dir = resolve_path(args.out_dir) if args.out_dir else PROJECT_ROOT / "osm_raw_output" / case_id
    out_dir.mkdir(parents=True, exist_ok=True)

    highway_fp = out_dir / EXPECTED_LAYERS["highway"]
    manifest_fp = out_dir / "osm_raw_fetch_manifest.csv"
    if highway_fp.exists() and manifest_matches_current_version(manifest_fp) and not args.force_refresh:
        print(f"Existing OSM raw output found, skip fetch: {out_dir}")
        print("Use --force-refresh to fetch again.")
        return

    route_line = parse_gpx_line(activity_fp)
    query_geometry = route_buffer_geometry(route_line, args.buffer_m, simplify_m=args.buffer_simplify_m)
    bbox = geometry_bbox(query_geometry)
    fetched_at = datetime.now(timezone.utc).isoformat()

    print("CASE_ID:", case_id)
    print("activity_fp:", activity_fp)
    print("out_dir:", out_dir)
    print("bbox west,south,east,north:", bbox)
    print("buffer_m:", args.buffer_m)
    print("buffer_simplify_m:", args.buffer_simplify_m)
    print("overpass_url:", ox.settings.overpass_url)
    print("user_agent:", args.user_agent)

    raw = fetch_grouped_features(
        query_geometry,
        osm_tag_groups(args.tag_profile),
        retry=args.retry,
        sleep_sec=args.sleep_sec,
    )
    if raw.empty:
        raise RuntimeError("Overpass returned no features for this GPX route-buffer polygon.")

    raw = raw[raw.geometry.notna()].copy()
    if raw.crs is None:
        raw = raw.set_crs("EPSG:4326")
    raw = add_metadata(raw, case_id, fetched_at)
    raw = normalize_highway(raw)

    masks = layer_masks(raw)
    layer_summary = []
    written_layers = {}
    for layer_name, filename in EXPECTED_LAYERS.items():
        layer = raw[masks.get(layer_name, pd.Series(False, index=raw.index))].copy()
        layer = prepare_layer_for_output(layer_name, layer)
        count = write_layer(layer, out_dir / filename)
        written_layers[layer_name] = layer
        layer_summary.append(
            {
                "route_id": case_id,
                "osm_dataset_id": case_id,
                "layer_name": layer_name,
                "filename": filename,
                "feature_count": count,
                "bbox_west": bbox[0],
                "bbox_south": bbox[1],
                "bbox_east": bbox[2],
                "bbox_north": bbox[3],
                "buffer_m": args.buffer_m,
                "buffer_simplify_m": args.buffer_simplify_m,
                "fetched_at": fetched_at,
                "overpass_url": ox.settings.overpass_url,
                "script_version": VERSION,
                "script_status": STATUS,
            }
        )
        print(f"{filename}: {count}")

    summary_df = pd.DataFrame(layer_summary)
    summary_df.to_csv(out_dir / "osm_raw_layer_summary.csv", index=False, encoding="utf-8-sig")
    summary_df.to_csv(manifest_fp, index=False, encoding="utf-8-sig")
    export_tag_summary(written_layers.get("generic_context", raw.iloc[0:0].copy()), out_dir / "osm_generic_tag_summary.csv")

    if not args.no_map:
        write_map(route_line, written_layers, out_dir / "osm_raw_layers_map.html")

    if not highway_fp.exists() or summary_df.loc[summary_df["layer_name"].eq("highway"), "feature_count"].iloc[0] == 0:
        raise RuntimeError("Core layer osm_highway_raw.geojson is empty; downstream route matching cannot continue.")

    print("Done:", out_dir)


if __name__ == "__main__":
    main()
