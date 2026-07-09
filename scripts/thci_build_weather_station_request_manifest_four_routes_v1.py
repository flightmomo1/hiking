# -*- coding: utf-8 -*-
"""
Build weather/water station request manifests for four THCI routes.

This wrapper only prepares station/time/field requests. It does not download
weather data, export observation rows from SQLite, run weather-terrain fusion,
run a v1.3 adapter, or run candidate scoring.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import py_compile
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.ops import nearest_points, transform, unary_union


PROJECT_ROOT = Path(__file__).resolve().parents[1]

ROUTES = [
    "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b",
    "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b",
    "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b",
    "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b",
]

OUT_DIR = PROJECT_ROOT / "outputs" / "thci_four_route_weather_station_request_manifest_v1"
DB_PATH = PROJECT_ROOT / "weather" / "tw_weather_2026-05-01.sqlite3"

ROUTE_LINE_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa"
)
ROUTE_PROFILE_DIR = PROJECT_ROOT / "outputs" / "ib1_route_profile_v1_3b_contract_qa"
ROLE_ASSIGNMENT_DIR = PROJECT_ROOT / "outputs" / "ib3w_station_weather_role_assignment_v1"
ROUTE_SCOPED_SELECTION_DIR = (
    PROJECT_ROOT / "outputs" / "ib3w_route_scoped_station_selection_v1"
)

WEATHER_REQUESTED_FIELDS = [
    "observed_at",
    "rain_1h_mm",
    "rain_3h_mm",
    "rain_6h_mm",
    "rain_24h_mm",
    "temperature_c",
    "relative_humidity_pct",
    "wind_speed_mps",
    "wind_direction_deg",
]

WATER_REQUESTED_FIELDS = [
    "observed_at",
    "water_level_m",
    "flow_rate_cms",
    "rainfall_mm",
    "station_status",
]

MANIFEST_COLUMNS = [
    "route_id",
    "station_role",
    "station_id",
    "station_name",
    "station_type",
    "station_lat",
    "station_lon",
    "station_elev_m",
    "distance_to_route_m",
    "nearest_route_point_lat",
    "nearest_route_point_lon",
    "elevation_diff_m",
    "recommended_start_time",
    "recommended_end_time",
    "requested_fields",
    "priority",
    "usage_policy",
    "notes",
]

CANDIDATE_COLUMNS = [
    "route_id",
    "station_group",
    "station_id",
    "station_name",
    "station_type",
    "dataset_code",
    "county_name",
    "town_name",
    "station_lat",
    "station_lon",
    "station_elev_m",
    "distance_to_route_m",
    "nearest_route_point_lat",
    "nearest_route_point_lon",
    "nearest_route_dist_m",
    "nearest_route_elev_m",
    "elevation_diff_m",
    "candidate_rank",
    "candidate_role",
    "usage_policy",
    "metadata_source_table",
    "source_obs_count",
    "source_first_obs_time",
    "source_last_obs_time",
    "notes",
]


@dataclass
class Station:
    station_group: str
    station_id: str
    station_name: str
    station_type: str
    dataset_code: str
    county_name: str
    town_name: str
    lat: float
    lon: float
    elev_m: float | None
    obs_count: int
    first_obs_time: str
    last_obs_time: str
    metadata_source_table: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build four-route weather station request manifests."
    )
    parser.add_argument(
        "--as-of",
        required=True,
        help="Recommended window end time, e.g. 2026-06-27T12:00:00+08:00.",
    )
    parser.add_argument("--lookback-hours", type=float, default=72.0)
    parser.add_argument("--max-distance-km", type=float, default=20.0)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing outputs. Default is no-overwrite skip.",
    )
    return parser.parse_args()


def parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))
    return dt


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def read_geojson_geometry(fp: Path):
    with fp.open("r", encoding="utf-8") as f:
        data = json.load(f)

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
        raise ValueError(f"No geometry found in {fp}")

    return unary_union(geometries)


def find_route_line(case_id: str) -> Path:
    case_dir = ROUTE_LINE_DIR / case_id
    candidates = [
        case_dir / f"{case_id}_trimmed_mainline.geojson",
        case_dir / f"{case_id}_mainline_ordered_path_trimmed.geojson",
        case_dir / "mainline_ordered_path_trimmed.geojson",
    ]
    for fp in candidates:
        if fp.exists():
            return fp

    found = sorted(case_dir.glob("*.geojson")) if case_dir.exists() else []
    if found:
        return found[0]

    raise FileNotFoundError(f"No route line GeoJSON found for {case_id}")


def load_route_profile(case_id: str) -> list[dict[str, Any]]:
    fp = ROUTE_PROFILE_DIR / case_id / f"{case_id}_route_profile.csv"
    if not fp.exists():
        return []

    rows = []
    with fp.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lat = to_float(row.get("lat"))
            lon = to_float(row.get("lon"))
            elev = to_float(row.get("ele_smooth"))
            if elev is None:
                elev = to_float(row.get("ele_gpx_m"))
            dist_m = to_float(row.get("dist_m"))
            if lat is None or lon is None:
                continue
            rows.append({"lat": lat, "lon": lon, "elev_m": elev, "dist_m": dist_m})
    return rows


def nearest_profile_elevation(
    nearest_lon: float,
    nearest_lat: float,
    profile_rows: list[dict[str, Any]],
) -> float | None:
    if not profile_rows:
        return None

    best = None
    best_d2 = None
    for row in profile_rows:
        d2 = (row["lat"] - nearest_lat) ** 2 + (row["lon"] - nearest_lon) ** 2
        if best_d2 is None or d2 < best_d2:
            best = row
            best_d2 = d2

    if best is None:
        return None
    return best.get("elev_m")


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        v = float(text)
    except ValueError:
        return None
    if math.isnan(v):
        return None
    return v


def read_station_metadata(conn: sqlite3.Connection) -> list[Station]:
    weather_sql = """
    SELECT DISTINCT
        station_id,
        station_name,
        dataset_code,
        county_name,
        town_name,
        latitude,
        longitude,
        elevation_m
    FROM weather_observations
    WHERE latitude IS NOT NULL
      AND longitude IS NOT NULL
    """
    water_sql = """
    SELECT DISTINCT
        station_id,
        station_name,
        river_name,
        county_name,
        town_name,
        latitude,
        longitude
    FROM water_level_observations
    WHERE latitude IS NOT NULL
      AND longitude IS NOT NULL
    """

    stations: list[Station] = []
    for row in conn.execute(weather_sql):
        stations.append(
            Station(
                station_group="weather",
                station_id=str(row[0]),
                station_name=str(row[1] or ""),
                station_type="weather",
                dataset_code=str(row[2] or ""),
                county_name=str(row[3] or ""),
                town_name=str(row[4] or ""),
                lat=float(row[5]),
                lon=float(row[6]),
                elev_m=to_float(row[7]),
                obs_count=0,
                first_obs_time="",
                last_obs_time="",
                metadata_source_table="weather_observations",
            )
        )

    for row in conn.execute(water_sql):
        river_name = str(row[2] or "")
        stations.append(
            Station(
                station_group="water",
                station_id=str(row[0]),
                station_name=str(row[1] or ""),
                station_type="water",
                dataset_code=river_name,
                county_name=str(row[3] or ""),
                town_name=str(row[4] or ""),
                lat=float(row[5]),
                lon=float(row[6]),
                elev_m=None,
                obs_count=0,
                first_obs_time="",
                last_obs_time="",
                metadata_source_table="water_level_observations",
            )
        )

    return stations


def load_role_reference(case_id: str) -> dict[str, dict[str, str]]:
    role_fp = ROLE_ASSIGNMENT_DIR / case_id / "station_weather_role_assignment.csv"
    out: dict[str, dict[str, str]] = {}
    if not role_fp.exists():
        return out

    with role_fp.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            station_id = str(row.get("station_id", "")).strip()
            if not station_id:
                continue
            out[station_id] = row
    return out


def load_route_scoped_reference(case_id: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for name in ["weather_station_candidates.csv", "water_station_candidates.csv"]:
        fp = ROUTE_SCOPED_SELECTION_DIR / case_id / name
        if not fp.exists():
            continue
        with fp.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                station_id = str(row.get("station_id", "")).strip()
                if station_id:
                    out[station_id] = row
    return out


def metric_transformers():
    to_m = Transformer.from_crs("EPSG:4326", "EPSG:3826", always_xy=True)
    to_wgs = Transformer.from_crs("EPSG:3826", "EPSG:4326", always_xy=True)
    return to_m, to_wgs


def station_distance_rows(
    case_id: str,
    route_geom,
    route_profile: list[dict[str, Any]],
    stations: list[Station],
    max_distance_km: float,
) -> list[dict[str, Any]]:
    to_m, to_wgs = metric_transformers()
    route_m = transform(to_m.transform, route_geom)
    max_distance_m = max_distance_km * 1000.0

    rows: list[dict[str, Any]] = []
    for station in stations:
        point_m = transform(to_m.transform, Point(station.lon, station.lat))
        distance_m = float(point_m.distance(route_m))
        if distance_m > max_distance_m:
            continue

        _, nearest_m = nearest_points(point_m, route_m)
        nearest_lon, nearest_lat = transform(to_wgs.transform, nearest_m).coords[0]
        route_elev_m = nearest_profile_elevation(nearest_lon, nearest_lat, route_profile)
        elevation_diff_m = None
        if station.elev_m is not None and route_elev_m is not None:
            elevation_diff_m = route_elev_m - station.elev_m

        rows.append(
            {
                "route_id": case_id,
                "station_group": station.station_group,
                "station_id": station.station_id,
                "station_name": station.station_name,
                "station_type": station.station_type,
                "dataset_code": station.dataset_code,
                "county_name": station.county_name,
                "town_name": station.town_name,
                "station_lat": station.lat,
                "station_lon": station.lon,
                "station_elev_m": station.elev_m,
                "distance_to_route_m": distance_m,
                "nearest_route_point_lat": nearest_lat,
                "nearest_route_point_lon": nearest_lon,
                "nearest_route_dist_m": None,
                "nearest_route_elev_m": route_elev_m,
                "elevation_diff_m": elevation_diff_m,
                "metadata_source_table": station.metadata_source_table,
                "source_obs_count": station.obs_count,
                "source_first_obs_time": station.first_obs_time,
                "source_last_obs_time": station.last_obs_time,
            }
        )

    rows.sort(
        key=lambda r: (
            0 if r["station_group"] == "weather" else 1,
            float(r["distance_to_route_m"]),
            str(r["station_id"]),
        )
    )
    return rows


def assign_roles(
    candidates: list[dict[str, Any]],
    role_reference: dict[str, dict[str, str]],
    scoped_reference: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    weather_rows = [r for r in candidates if r["station_group"] == "weather"]
    water_rows = [r for r in candidates if r["station_group"] == "water"]

    for idx, row in enumerate(weather_rows, start=1):
        dist_m = float(row["distance_to_route_m"])
        ref = role_reference.get(row["station_id"], {})
        scoped = scoped_reference.get(row["station_id"], {})

        role = "review_only"
        priority = "P4"
        usage_policy = "review only; do not use as primary fusion source"
        notes = []

        if idx <= 3 and dist_m <= 5000:
            role = "primary_weather"
            priority = "P1"
            usage_policy = "preferred route weather request source"
        elif idx <= 8 and dist_m <= 10000:
            role = "backup_weather"
            priority = "P2"
            usage_policy = "backup route weather request source"
        elif dist_m <= 15000:
            role = "rainfall_reference"
            priority = "P3"
            usage_policy = "rainfall context only; review before route fusion"

        if ref:
            notes.append(
                "prior_role_reference="
                + str(ref.get("station_weather_role", "")).strip()
            )
            policy = str(ref.get("route_context_use_policy", "")).strip()
            if policy:
                notes.append("prior_policy=" + policy)
            if "DO_NOT_USE_AS_PRIMARY" in policy or "AUDIT_ONLY" in policy:
                role = "review_only"
                priority = "P4"
                usage_policy = "prior role assignment says audit/review only"

        if scoped:
            scoped_role = str(scoped.get("candidate_role", "")).strip()
            if scoped_role:
                notes.append("prior_route_scoped_candidate_role=" + scoped_role)

        if row.get("station_elev_m") is None:
            notes.append("station_elev_m unavailable from DB metadata")
        if row.get("nearest_route_elev_m") is None:
            notes.append("route_nearest_elev_m unavailable")

        row["candidate_rank"] = idx
        row["candidate_role"] = role
        row["priority"] = priority
        row["usage_policy"] = usage_policy
        row["notes"] = "; ".join(n for n in notes if n)

    for idx, row in enumerate(water_rows, start=1):
        dist_m = float(row["distance_to_route_m"])
        role = "water_context" if idx <= 5 and dist_m <= 15000 else "review_only"
        priority = "P3" if role == "water_context" else "P4"
        usage_policy = (
            "water/hydrology context only; not a primary weather fusion source"
            if role == "water_context"
            else "review only; too distant or low priority"
        )

        ref = role_reference.get(row["station_id"], {})
        notes = []
        if ref:
            role_ref = str(ref.get("station_weather_role", "")).strip()
            policy = str(ref.get("route_context_use_policy", "")).strip()
            if role_ref:
                notes.append("prior_role_reference=" + role_ref)
            if policy:
                notes.append("prior_policy=" + policy)
        if row.get("station_elev_m") is None:
            notes.append("water station elevation unavailable from DB metadata")
        if dist_m > 15000:
            notes.append("outside preferred water context range")

        row["candidate_rank"] = idx
        row["candidate_role"] = role
        row["priority"] = priority
        row["usage_policy"] = usage_policy
        row["notes"] = "; ".join(n for n in notes if n)

    candidates.sort(
        key=lambda r: (
            {"primary_weather": 0, "backup_weather": 1, "rainfall_reference": 2,
             "water_context": 3, "review_only": 4}.get(r["candidate_role"], 9),
            float(r["distance_to_route_m"]),
            str(r["station_id"]),
        )
    )
    return candidates


def build_manifest_rows(
    candidates: list[dict[str, Any]],
    start_time: str,
    end_time: str,
) -> list[dict[str, Any]]:
    rows = []
    for row in candidates:
        role = row["candidate_role"]
        if role == "review_only" and len([r for r in rows if r["station_role"] == "review_only"]) >= 8:
            continue
        if role != "review_only" or row["station_group"] == "weather":
            fields = (
                WEATHER_REQUESTED_FIELDS
                if row["station_group"] == "weather"
                else WATER_REQUESTED_FIELDS
            )
            rows.append(
                {
                    "route_id": row["route_id"],
                    "station_role": role,
                    "station_id": row["station_id"],
                    "station_name": row["station_name"],
                    "station_type": row["station_type"],
                    "station_lat": row["station_lat"],
                    "station_lon": row["station_lon"],
                    "station_elev_m": row["station_elev_m"],
                    "distance_to_route_m": row["distance_to_route_m"],
                    "nearest_route_point_lat": row["nearest_route_point_lat"],
                    "nearest_route_point_lon": row["nearest_route_point_lon"],
                    "elevation_diff_m": row["elevation_diff_m"],
                    "recommended_start_time": start_time,
                    "recommended_end_time": end_time,
                    "requested_fields": "|".join(fields),
                    "priority": row["priority"],
                    "usage_policy": row["usage_policy"],
                    "notes": row["notes"],
                }
            )
    return rows


def fmt_value(value: Any) -> Any:
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return round(value, 6)
    if value is None:
        return ""
    return value


def write_csv(fp: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with fp.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: fmt_value(row.get(col, "")) for col in columns})


def write_json(fp: Path, payload: dict[str, Any]) -> None:
    with fp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def run_py_compile() -> dict[str, Any]:
    try:
        py_compile.compile(str(Path(__file__).resolve()), doraise=True)
        return {"returncode": 0, "status": "PASS", "message": ""}
    except Exception as exc:  # pragma: no cover - reported in generated audit
        return {"returncode": 1, "status": "FAIL", "message": str(exc)}


def git_status_short() -> str:
    try:
        proc = subprocess.run(
            ["git", "status", "--short"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
    except Exception as exc:  # pragma: no cover
        return f"git status failed: {exc}"
    return proc.stdout.strip()


def build_report(
    route_summaries: list[dict[str, Any]],
    summary_rows: list[dict[str, Any]],
    args: argparse.Namespace,
    py_compile_result: dict[str, Any],
    git_status: str,
) -> str:
    lines = [
        "# THCI Four Route Weather Station Request Manifest v1",
        "",
        f"Generated with `--as-of {args.as_of}` and `--lookback-hours {args.lookback_hours}`.",
        "",
        "Execution guardrails:",
        "- Did not modify scoring scripts.",
        "- Did not modify risk semantics config.",
        "- Did not run weather-terrain fusion.",
        "- Did not run v1.3 adapter or candidate scoring.",
        "- Did not download weather data from WebAPI.",
        "- Did not export observation rows from SQLite.",
        "- Did not generate `rain_factor`, `rain_flags`, or `rainwash_axis_score`.",
        "",
        "## Route Requests",
        "",
    ]

    for route in route_summaries:
        lines.extend(
            [
                f"### {route['route_id']}",
                "",
                f"- Route line: `{route['route_line']}`",
                f"- Recommended window: `{route['recommended_start_time']}` to `{route['recommended_end_time']}`",
                f"- Candidate rows: {route['candidate_count']}",
                f"- Manifest rows: {route['manifest_count']}",
                "",
                "| Priority | Role | Station | Distance m | Elev diff m | Usage |",
                "|---|---|---|---:|---:|---|",
            ]
        )

        route_rows = [
            r for r in summary_rows if r["route_id"] == route["route_id"]
        ]
        for row in route_rows:
            station = f"{row['station_id']} {row['station_name']}".strip()
            lines.append(
                "| {priority} | {role} | {station} | {dist} | {ediff} | {policy} |".format(
                    priority=row["priority"],
                    role=row["station_role"],
                    station=station,
                    dist=fmt_value(row["distance_to_route_m"]),
                    ediff=fmt_value(row["elevation_diff_m"]),
                    policy=row["usage_policy"],
                )
            )
        lines.append("")

    lines.extend(
        [
            "## Requested Fields",
            "",
            "Weather stations:",
            "",
            "`" + ", ".join(WEATHER_REQUESTED_FIELDS) + "`",
            "",
            "Water stations:",
            "",
            "`" + ", ".join(WATER_REQUESTED_FIELDS) + "`",
            "",
            "## Review-Only Policy",
            "",
            "Stations marked `review_only` are included for evidence review only and should not be used as primary fusion sources without human review or stronger lineage.",
            "",
            "Water stations are requestable for hydrology/water context only. They are not primary weather fusion sources.",
            "",
            "## Converting Received Data To route_weather_v1.csv",
            "",
            "After a colleague or WebAPI provides the requested fields, convert the returned station data into a route-specific `route_weather_v1.csv` by preserving station lineage columns, normalizing `observed_at` to timezone-aware ISO timestamps, mapping rainfall fields without inventing missing values, and writing one manifest per route that records source station IDs, requested window, row count, and variable coverage. Only then should weather-terrain fusion be considered.",
            "",
            "## py_compile",
            "",
            f"- Status: `{py_compile_result['status']}`",
            f"- Return code: `{py_compile_result['returncode']}`",
            f"- Message: `{py_compile_result.get('message', '')}`",
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


def output_exists_for_case(case_id: str) -> bool:
    case_dir = OUT_DIR / case_id
    return all(
        [
            (case_dir / f"{case_id}_weather_station_request_manifest_v1.csv").exists(),
            (case_dir / f"{case_id}_weather_station_candidates_v1.csv").exists(),
            (case_dir / f"{case_id}_weather_station_request_lineage_v1.json").exists(),
        ]
    )


def main() -> int:
    args = parse_args()
    as_of = parse_datetime(args.as_of)
    start = as_of - timedelta(hours=float(args.lookback_hours))
    start_time = iso(start)
    end_time = iso(as_of)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not DB_PATH.exists():
        raise FileNotFoundError(f"Weather DB not found: {DB_PATH}")

    with sqlite3.connect(DB_PATH) as conn:
        stations = read_station_metadata(conn)

    all_manifest_rows: list[dict[str, Any]] = []
    route_summaries: list[dict[str, Any]] = []
    skipped_cases: list[str] = []

    for case_id in ROUTES:
        case_dir = OUT_DIR / case_id
        case_dir.mkdir(parents=True, exist_ok=True)

        manifest_fp = case_dir / f"{case_id}_weather_station_request_manifest_v1.csv"
        candidates_fp = case_dir / f"{case_id}_weather_station_candidates_v1.csv"
        lineage_fp = case_dir / f"{case_id}_weather_station_request_lineage_v1.json"

        if not args.overwrite and output_exists_for_case(case_id):
            skipped_cases.append(case_id)
            continue

        route_line_fp = find_route_line(case_id)
        route_geom = read_geojson_geometry(route_line_fp)
        profile_rows = load_route_profile(case_id)
        role_reference = load_role_reference(case_id)
        scoped_reference = load_route_scoped_reference(case_id)

        candidates = station_distance_rows(
            case_id=case_id,
            route_geom=route_geom,
            route_profile=profile_rows,
            stations=stations,
            max_distance_km=float(args.max_distance_km),
        )
        candidates = assign_roles(candidates, role_reference, scoped_reference)
        manifest_rows = build_manifest_rows(candidates, start_time, end_time)

        write_csv(candidates_fp, candidates, CANDIDATE_COLUMNS)
        write_csv(manifest_fp, manifest_rows, MANIFEST_COLUMNS)
        write_json(
            lineage_fp,
            {
                "route_id": case_id,
                "route_line": str(route_line_fp),
                "route_profile_rows": len(profile_rows),
                "weather_db": str(DB_PATH),
                "weather_db_usage": "station metadata only; no observation rows exported",
                "as_of": end_time,
                "lookback_hours": args.lookback_hours,
                "recommended_start_time": start_time,
                "recommended_end_time": end_time,
                "max_distance_km": args.max_distance_km,
                "station_metadata_tables": [
                    "weather_observations grouped by station metadata",
                    "water_level_observations grouped by station metadata",
                ],
                "role_reference_files": {
                    "role_assignment": str(ROLE_ASSIGNMENT_DIR / case_id),
                    "route_scoped_selection": str(ROUTE_SCOPED_SELECTION_DIR / case_id),
                },
                "output_files": {
                    "manifest": str(manifest_fp),
                    "candidates": str(candidates_fp),
                    "lineage": str(lineage_fp),
                },
                "guardrails": [
                    "no WebAPI download",
                    "no SQLite observation row export",
                    "no weather-terrain fusion",
                    "no v1.3 adapter",
                    "no candidate scoring",
                    "no synthetic rain_factor/rain_flags/rainwash_axis_score",
                ],
            },
        )

        all_manifest_rows.extend(manifest_rows)
        route_summaries.append(
            {
                "route_id": case_id,
                "route_line": str(route_line_fp),
                "candidate_count": len(candidates),
                "manifest_count": len(manifest_rows),
                "recommended_start_time": start_time,
                "recommended_end_time": end_time,
                "manifest_fp": str(manifest_fp),
                "candidates_fp": str(candidates_fp),
                "lineage_fp": str(lineage_fp),
                "status": "written",
            }
        )

    summary_fp = OUT_DIR / "thci_four_route_weather_station_request_summary_v1.csv"
    report_fp = OUT_DIR / "thci_four_route_weather_station_request_report_v1.md"

    py_compile_result = run_py_compile()
    git_status = git_status_short()

    if not args.overwrite and summary_fp.exists() and report_fp.exists():
        print(f"skip existing summary/report: {OUT_DIR}")
    else:
        write_csv(summary_fp, all_manifest_rows, MANIFEST_COLUMNS)
        report = build_report(
            route_summaries=route_summaries,
            summary_rows=all_manifest_rows,
            args=args,
            py_compile_result=py_compile_result,
            git_status=git_status,
        )
        report_fp.write_text(report, encoding="utf-8")

    print("output_dir:", OUT_DIR)
    print("routes_written:", len(route_summaries))
    print("routes_skipped:", len(skipped_cases))
    if skipped_cases:
        print("skipped_cases:", ",".join(skipped_cases))
    print("summary:", summary_fp)
    print("report:", report_fp)
    print("py_compile:", py_compile_result["status"])
    return 0 if py_compile_result["returncode"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
