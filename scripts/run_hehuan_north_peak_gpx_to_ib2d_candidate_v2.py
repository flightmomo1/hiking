from __future__ import annotations

import argparse
import csv
import json
import math
import py_compile
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASE_ID = "hehuan_north_peak_garmin_with_waypoints_v1"
CASE_NAME = "Hehuan North Peak Garmin GPX with waypoints candidate"
SOURCE_GPX = PROJECT_ROOT / "activity_input" / "gpx" / "hehuan_north_garmin_with_waypoints.gpx"
FIT12_REVIEW = PROJECT_ROOT / "activity_input" / "fit" / "12" / "12-合歡山北峰來回.fit"
FIT11_REVIEW = PROJECT_ROOT / "activity_input" / "fit" / "11" / "11-合歡山北峰-反射板.fit"
ROUTE_CONTROL_POINTS_FP = PROJECT_ROOT / "configs" / "route_definitions" / "route_control_points_v1_3b.csv"
ROUTE_EXPECTED_TIME_FP = PROJECT_ROOT / "configs" / "route_definitions" / "route_expected_time_segments_v1_3b.csv"

INSPECTION_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "hehuan_north_peak_gpx_onboarding_to_ib2d_v2"
    / "00_gpx_seed_inspection"
)
CANDIDATE_ROOT = PROJECT_ROOT / "outputs" / "route_onboarding_candidate_runs_v2" / CASE_ID
PREVIOUS_V1_ROOT = PROJECT_ROOT / "outputs" / "route_onboarding_candidate_runs_v1" / CASE_ID


@dataclass
class TrackPoint:
    index: int
    lat: float
    lon: float
    ele: float | None
    time: str | None


@dataclass
class Waypoint:
    index: int
    name: str
    lat: float
    lon: float
    ele: float | None
    desc: str


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def read_text_lossless(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def extract_tag(block: str, tag: str) -> str:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", block, flags=re.S)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    # The source GPX has a few malformed waypoint name end tags like ?/name>.
    m = re.search(rf"<{tag}>(.*?)(?:</?wpt>|<desc>|[\r\n])", block, flags=re.S)
    if m:
        return re.sub(r"\s+", " ", m.group(1).replace("</name", "").replace("/name>", "")).strip()
    return ""


def parse_source_gpx(path: Path) -> tuple[list[TrackPoint], list[Waypoint], str | None]:
    text = read_text_lossless(path)
    parse_error = None
    try:
        import xml.etree.ElementTree as ET

        ET.parse(path)
    except Exception as exc:
        parse_error = str(exc)

    track_points: list[TrackPoint] = []
    for idx, m in enumerate(
        re.finditer(
            r'<trkpt\s+lat="([-0-9.]+)"\s+lon="([-0-9.]+)"[^>]*>(.*?)</trkpt>',
            text,
            flags=re.S,
        )
    ):
        block = m.group(3)
        ele = extract_tag(block, "ele")
        time = extract_tag(block, "time")
        track_points.append(
            TrackPoint(
                index=idx,
                lat=float(m.group(1)),
                lon=float(m.group(2)),
                ele=float(ele) if ele else None,
                time=time or None,
            )
        )

    waypoints: list[Waypoint] = []
    for idx, m in enumerate(
        re.finditer(
            r'<wpt\s+lat="([-0-9.]+)"\s+lon="([-0-9.]+)"[^>]*>(.*?)(?=</wpt>|<wpt\s+lat=|<trk>)',
            text,
            flags=re.S,
        )
    ):
        block = m.group(3)
        ele = extract_tag(block, "ele")
        name = extract_tag(block, "name") or f"waypoint_{idx + 1:02d}"
        desc = extract_tag(block, "desc")
        waypoints.append(
            Waypoint(
                index=idx,
                name=name,
                lat=float(m.group(1)),
                lon=float(m.group(2)),
                ele=float(ele) if ele else None,
                desc=desc,
            )
        )
    return track_points, waypoints, parse_error


def cumulative_distances(points: list[TrackPoint]) -> list[float]:
    distances = [0.0]
    total = 0.0
    for prev, cur in zip(points, points[1:]):
        total += haversine_m(prev.lat, prev.lon, cur.lat, cur.lon)
        distances.append(total)
    return distances


def gain_loss(points: list[TrackPoint]) -> tuple[float, float]:
    gain = 0.0
    loss = 0.0
    prev = None
    for point in points:
        if point.ele is None:
            continue
        if prev is not None:
            delta = point.ele - prev
            if delta > 0:
                gain += delta
            elif delta < 0:
                loss += -delta
        prev = point.ele
    return gain, loss


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_case_rows(path: Path, case_id: str) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle) if row.get("case_id", "").strip() == case_id]


def read_formal_control_points() -> list[dict[str, Any]]:
    rows = load_case_rows(ROUTE_CONTROL_POINTS_FP, CASE_ID)
    if len(rows) != 5:
        raise RuntimeError(f"Expected 5 formal Hehuan control points, found {len(rows)}")
    ordered = sorted(rows, key=lambda row: int(float(row.get("order") or 0)))
    roles = [row.get("control_role", "") for row in ordered]
    expected_roles = ["start", "ascent_via", "turnaround", "descent_via", "end"]
    if roles != expected_roles:
        raise RuntimeError(f"Formal control point roles are not out-and-back ordered: {roles}")
    return ordered


def read_formal_expected_time_segments() -> list[dict[str, Any]]:
    rows = load_case_rows(ROUTE_EXPECTED_TIME_FP, CASE_ID)
    if len(rows) != 4:
        raise RuntimeError(f"Expected 4 formal Hehuan expected-time rows, found {len(rows)}")
    if any(not row.get("case_id", "").strip() for row in rows):
        raise RuntimeError("Formal expected-time rows include blank case_id")
    return rows


def projection_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "rank1_count": 0, "rank1_max_offset_m": "", "rank1_mean_offset_m": ""}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if str(row.get("candidate_rank", "")) in {"1", "1.0"}]
    offsets: list[float] = []
    for row in rows:
        try:
            offsets.append(float(row.get("offset_to_osm_m", "")))
        except ValueError:
            pass
    return {
        "exists": True,
        "rank1_count": len(rows),
        "rank1_max_offset_m": round(max(offsets), 3) if offsets else "",
        "rank1_mean_offset_m": round(sum(offsets) / len(offsets), 3) if offsets else "",
    }


def find_covering_contour(route_line_fp: Path, audit_fp: Path) -> Path | None:
    import geopandas as gpd

    route = gpd.read_file(route_line_fp)
    if route.crs is None:
        route = route.set_crs("EPSG:4326")
    route_wgs84 = route.to_crs("EPSG:4326")
    route_bounds = route_wgs84.total_bounds
    route_geom = route_wgs84.unary_union
    rows = []
    best: tuple[float, Path, list[float]] | None = None
    for shp in (PROJECT_ROOT / "nlsc_raw").rglob("ContourL.shp"):
        try:
            contours = gpd.read_file(shp)
            if contours.empty:
                continue
            bounds = contours.to_crs("EPSG:4326").total_bounds if contours.crs else contours.total_bounds
            intersects_bbox = not (
                bounds[2] < route_bounds[0]
                or bounds[0] > route_bounds[2]
                or bounds[3] < route_bounds[1]
                or bounds[1] > route_bounds[3]
            )
            if intersects_bbox:
                audit_fp.parent.mkdir(parents=True, exist_ok=True)
                audit_fp.write_text(json.dumps({"selected_contour_fp": str(shp), "route_bounds": route_bounds.tolist(), "selected_bounds": bounds.tolist()}, ensure_ascii=False, indent=2), encoding="utf-8")
                return shp
            from shapely.geometry import box

            dist_deg = route_geom.distance(box(*bounds))
            rows.append({"contour_fp": str(shp), "bounds": [float(x) for x in bounds], "distance_degrees": float(dist_deg)})
            if best is None or dist_deg < best[0]:
                best = (float(dist_deg), shp, [float(x) for x in bounds])
        except Exception as exc:
            rows.append({"contour_fp": str(shp), "error": str(exc)})
    audit_fp.parent.mkdir(parents=True, exist_ok=True)
    audit_fp.write_text(
        json.dumps(
            {
                "selected_contour_fp": None,
                "route_bounds": [float(x) for x in route_bounds],
                "nearest_contour": {"distance_degrees": best[0], "contour_fp": str(best[1]), "bounds": best[2]} if best else None,
                "checked": rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return None


def write_sanitized_gpx(path: Path, points: list[TrackPoint], waypoints: list[Waypoint]) -> None:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="run_hehuan_north_peak_gpx_to_ib2d_candidate_v1" xmlns="http://www.topografix.com/GPX/1/1">',
        "  <metadata>",
        f"    <name>{escape(CASE_NAME)}</name>",
        "    <desc>Primary route seed is hehuan_north_garmin_with_waypoints.gpx; sanitized non-overwrite candidate copy for parser compatibility. official_route=false</desc>",
        "  </metadata>",
    ]
    for waypoint in waypoints:
        lines.append(f'  <wpt lat="{waypoint.lat:.8f}" lon="{waypoint.lon:.8f}">')
        if waypoint.ele is not None:
            lines.append(f"    <ele>{waypoint.ele:.2f}</ele>")
        lines.append(f"    <name>{escape(waypoint.name)}</name>")
        if waypoint.desc:
            lines.append(f"    <desc>{escape(waypoint.desc)}</desc>")
        lines.append("  </wpt>")
    lines.append(f"  <trk><name>{escape(CASE_NAME)}</name><trkseg>")
    for point in points:
        lines.append(f'    <trkpt lat="{point.lat:.8f}" lon="{point.lon:.8f}">')
        if point.ele is not None:
            lines.append(f"      <ele>{point.ele:.2f}</ele>")
        if point.time:
            lines.append(f"      <time>{escape(point.time)}</time>")
        lines.append("    </trkpt>")
    lines.extend(["  </trkseg></trk>", "</gpx>"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def nearest_point_index(points: list[TrackPoint], lat: float, lon: float) -> tuple[int, float]:
    best_i = 0
    best_d = float("inf")
    for point in points:
        dist = haversine_m(lat, lon, point.lat, point.lon)
        if dist < best_d:
            best_i = point.index
            best_d = dist
    return best_i, best_d


def propose_control_points(points: list[TrackPoint], waypoints: list[Waypoint], distances: list[float]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(control_id: str, role: str, phase: str, name: str, point: TrackPoint, order: int, required: bool, action: str, note: str) -> None:
        rows.append(
            {
                "case_id": CASE_ID,
                "control_id": control_id,
                "control_role": role,
                "phase": phase,
                "name": name,
                "lat": f"{point.lat:.8f}",
                "lon": f"{point.lon:.8f}",
                "required": str(required).lower(),
                "order": order,
                "route_action": action,
                "note": note,
            }
        )

    add("start_trace_start", "start", "start", "GPX trace start / 小風口起走候選", points[0], 1, False, "trim_anchor", "primary GPX seed first trkpt; keep separate from end for out-and-back")

    sorted_wps = []
    for waypoint in waypoints:
        nearest_idx, nearest_m = nearest_point_index(points, waypoint.lat, waypoint.lon)
        sorted_wps.append((distances[nearest_idx], waypoint, points[nearest_idx], nearest_m))
    sorted_wps.sort(key=lambda item: item[0])

    body_wps = sorted_wps[:-1] if len(sorted_wps) >= 2 else sorted_wps
    # Waypoint 005 is near the return trailhead/end and is kept as evidence, not
    # inserted before the summit in the ordered route axis.
    ascent_order = 2
    ascent_points = []
    for _, waypoint, point, nearest_m in body_wps:
        role = "turnaround" if waypoint.ele and waypoint.ele >= 3400 else "ascent_via"
        if role == "turnaround":
            add(
                "summit_turnaround_waypoint",
                "turnaround",
                "turnaround",
                f"{waypoint.name} / 合歡山北峰 summit candidate",
                point,
                ascent_order,
                False,
                "anchor_only",
                f"from GPX waypoint ele={waypoint.ele}; nearest track offset {nearest_m:.1f} m",
            )
        else:
            cid = f"ascent_wp_{waypoint.index + 1:02d}"
            action = "anchor_only"
            review = ""
            if waypoint.ele and waypoint.ele >= 3300:
                cid = "reflector_or_1p5k_ascent_review"
                review = "; possible reflector / 1.5K high route feature; manual_review_required"
            add(
                cid,
                "ascent_via",
                "ascent",
                waypoint.name,
                point,
                ascent_order,
                False,
                action,
                f"from GPX waypoint ele={waypoint.ele}; nearest track offset {nearest_m:.1f} m{review}",
            )
            ascent_points.append((waypoint, point, nearest_m))
        ascent_order += 1

    # Return anchors mirror ascent waypoints, preserving out-and-back order.
    return_order = ascent_order
    for waypoint, point, nearest_m in reversed(ascent_points):
        cid = f"descent_wp_{waypoint.index + 1:02d}"
        note_extra = ""
        if waypoint.ele and waypoint.ele >= 3300:
            cid = "reflector_or_1p5k_descent_review"
            note_extra = "; same coordinate as ascent review anchor; manual_review_required"
        add(
            cid,
            "descent_via",
            "descent",
            waypoint.name + " return",
            point,
            return_order,
            False,
            "anchor_only",
            f"return-phase duplicate coordinate from GPX waypoint; nearest track offset {nearest_m:.1f} m{note_extra}",
        )
        return_order += 1

    add("end_trace_end", "end", "end", "GPX trace end / 回到登山口候選", points[-1], return_order, False, "trim_anchor", "primary GPX seed final trkpt; keep separate from start for out-and-back")
    return rows


def inspection_outputs(points: list[TrackPoint], waypoints: list[Waypoint], parse_error: str | None, sanitized_gpx: Path, control_points: list[dict[str, Any]]) -> dict[str, Any]:
    distances = cumulative_distances(points)
    gain, loss = gain_loss(points)
    start_end_m = haversine_m(points[0].lat, points[0].lon, points[-1].lat, points[-1].lon)
    out_and_back = start_end_m <= max(500.0, distances[-1] * 0.15)
    summary = {
        "case_id": CASE_ID,
        "source_gpx": str(SOURCE_GPX),
        "sanitized_gpx": str(sanitized_gpx),
        "standard_xml_readable": parse_error is None,
        "parse_error": parse_error or "",
        "track_points": len(points),
        "waypoints": len(waypoints),
        "has_elevation": any(p.ele is not None for p in points),
        "has_time": any(p.time for p in points),
        "route_length_estimate_m": distances[-1],
        "elevation_min_m": min(p.ele for p in points if p.ele is not None),
        "elevation_max_m": max(p.ele for p in points if p.ele is not None),
        "elevation_gain_estimate_m": gain,
        "elevation_loss_estimate_m": loss,
        "start_lat": points[0].lat,
        "start_lon": points[0].lon,
        "end_lat": points[-1].lat,
        "end_lon": points[-1].lon,
        "start_end_distance_m": start_end_m,
        "suspected_out_and_back": out_and_back,
        "primary_seed_suitable": len(points) >= 2 and len(waypoints) >= 4,
    }

    point_rows = []
    for point, dist in zip(points, distances):
        point_rows.append(
            {
                "ordered_index": point.index,
                "timestamp": point.time,
                "lat": point.lat,
                "lon": point.lon,
                "altitude_m": point.ele,
                "distance_cumulative_haversine_m": dist,
            }
        )
    write_csv(INSPECTION_DIR / "hehuan_north_peak_gpx_seed_points_v1.csv", point_rows)

    waypoint_rows = []
    for waypoint in waypoints:
        nearest_idx, nearest_m = nearest_point_index(points, waypoint.lat, waypoint.lon)
        waypoint_rows.append(
            {
                "waypoint_index": waypoint.index,
                "name": waypoint.name,
                "lat": waypoint.lat,
                "lon": waypoint.lon,
                "altitude_m": waypoint.ele,
                "desc": waypoint.desc,
                "nearest_track_index": nearest_idx,
                "nearest_track_offset_m": nearest_m,
                "nearest_track_distance_m": distances[nearest_idx],
            }
        )
    write_csv(INSPECTION_DIR / "hehuan_north_peak_gpx_waypoints_v1.csv", waypoint_rows)
    write_csv(INSPECTION_DIR / "hehuan_north_peak_gpx_seed_inspection_v1.csv", [summary])

    md = "\n".join(
        [
            "# Hehuan North Peak Garmin GPX seed inspection v1",
            "",
            f"Case id: `{CASE_ID}`",
            f"Primary source GPX: `{SOURCE_GPX}`",
            f"Sanitized non-overwrite GPX for parser compatibility: `{sanitized_gpx}`",
            "",
            "The primary source is the Garmin GPX with waypoints. FIT12/FIT11 are review evidence only and are not used as the primary route seed.",
            "",
            "## Readability",
            "",
            f"- Standard XML readable: `{summary['standard_xml_readable']}`",
            f"- Parse error: `{summary['parse_error']}`",
            f"- Track points extracted: `{summary['track_points']}`",
            f"- Waypoints extracted: `{summary['waypoints']}`",
            "",
            "## Route Metrics",
            "",
            f"- Route length estimate: `{summary['route_length_estimate_m']:.1f}` m",
            f"- Elevation min/max: `{summary['elevation_min_m']}` / `{summary['elevation_max_m']}` m",
            f"- Elevation gain/loss estimate: `{summary['elevation_gain_estimate_m']:.1f}` / `{summary['elevation_loss_estimate_m']:.1f}` m",
            f"- Start: `{summary['start_lat']}, {summary['start_lon']}`",
            f"- End: `{summary['end_lat']}, {summary['end_lon']}`",
            f"- Start/end distance: `{summary['start_end_distance_m']:.1f}` m",
            f"- Suspected out-and-back: `{summary['suspected_out_and_back']}`",
            "",
            "## Waypoints",
            "",
            "| index | name | lat | lon | altitude_m | nearest_track_index | offset_m |",
            "|---:|---|---:|---:|---:|---:|---:|",
            *[
                f"| {r['waypoint_index']} | {r['name']} | {float(r['lat']):.8f} | {float(r['lon']):.8f} | {r['altitude_m']} | {r['nearest_track_index']} | {float(r['nearest_track_offset_m']):.1f} |"
                for r in waypoint_rows
            ],
            "",
            "## Suggested Anchors / Control Points",
            "",
            "Use phase-aware out-and-back anchors. Preserve start and end as separate route positions even if spatially close. Waypoints are proposed as ascent/descent via anchors, with the high waypoint as summit/turnaround and the 1.5K/high feature marked for reflector review.",
            "",
            "| order | control_id | role | phase | name | review |",
            "|---:|---|---|---|---|---|",
            *[
                f"| {r['order']} | `{r['control_id']}` | {r['control_role']} | {r['phase']} | {r['name']} | {'manual_review_required' if 'manual_review_required' in r['note'] else ''} |"
                for r in control_points
            ],
            "",
            f"Primary GPX suitable as route seed: `{summary['primary_seed_suitable']}`",
            "",
        ]
    )
    (INSPECTION_DIR / "hehuan_north_peak_gpx_seed_inspection_v1.md").write_text(md, encoding="utf-8")
    return summary


def run_cmd(stage_id: str, cmd: list[str], manifest: list[dict[str, Any]], stop_on_failure: bool = True) -> bool:
    started = datetime.now(timezone.utc).isoformat()
    proc = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    log_dir = CANDIDATE_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_fp = log_dir / f"{stage_id}.log"
    log_fp.write_text(
        "$ " + " ".join(cmd) + "\n\n--- stdout ---\n" + proc.stdout + "\n--- stderr ---\n" + proc.stderr,
        encoding="utf-8",
    )
    status = "PASS" if proc.returncode == 0 else "FAIL"
    manifest.append(
        {
            "stage_id": stage_id,
            "status": status,
            "returncode": proc.returncode,
            "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "command": " ".join(cmd),
            "log_fp": str(log_fp),
            "failure_reason": "" if proc.returncode == 0 else (proc.stderr.strip() or proc.stdout.strip())[-1000:],
        }
    )
    if proc.returncode != 0 and stop_on_failure:
        return False
    return True


def git_status() -> str:
    result = subprocess.run(["git", "status", "--short"], cwd=PROJECT_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    return result.stdout.strip() or "No output."


def compile_status() -> str:
    try:
        py_compile.compile(str(Path(__file__).resolve()), doraise=True)
    except Exception as exc:
        return f"FAIL: {exc}"
    return "PASS"


def write_reports(
    manifest: list[dict[str, Any]],
    inspection: dict[str, Any],
    py_status: str,
    control_points: list[dict[str, Any]],
    expected_segments: list[dict[str, Any]],
) -> None:
    write_csv(CANDIDATE_ROOT / "hehuan_north_peak_gpx_to_ib2d_candidate_manifest_v2.csv", manifest)
    summary_rows = []
    for row in manifest:
        summary_rows.append(
            {
                "stage_id": row["stage_id"],
                "status": row["status"],
                "returncode": row["returncode"],
                "failure_reason": row["failure_reason"],
            }
        )
    write_csv(CANDIDATE_ROOT / "hehuan_north_peak_gpx_to_ib2d_candidate_run_summary_v2.csv", summary_rows)
    by_stage = {row["stage_id"]: row for row in manifest}

    def ok(stage: str) -> str:
        return by_stage.get(stage, {}).get("status", "NOT_RUN")

    stopped = next((row for row in manifest if row["status"] == "FAIL"), None)
    projection_fp = CANDIDATE_ROOT / "03_ib0a" / CASE_ID / f"{CASE_ID}_control_points_projected_to_osm_topk.csv"
    v2_projection = projection_summary(projection_fp)
    v1_projection = projection_summary(PREVIOUS_V1_ROOT / "03_ib0a" / CASE_ID / f"{CASE_ID}_control_points_projected_to_osm_topk.csv")
    ascent_min = sum(int(float(row["expected_time_min"])) for row in expected_segments if row.get("direction") == "ascent")
    descent_min = sum(int(float(row["expected_time_min"])) for row in expected_segments if row.get("direction") == "descent")
    md = "\n".join(
        [
            "# Hehuan North Peak Garmin GPX to IB2D candidate run report v2",
            "",
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            f"Case id: `{CASE_ID}`",
            f"Candidate output root: `{CANDIDATE_ROOT}`",
            "",
            "This is a candidate onboarding run. It is not an official route and is not part of the official four-route batch.",
            "",
            "## Direct Answers",
            "",
            f"1. GPX primary route seed success: `{inspection.get('primary_seed_suitable')}`. A sanitized non-overwrite copy was created for parser compatibility.",
            f"2. Formal control points read: `{len(control_points)}` rows from `{ROUTE_CONTROL_POINTS_FP}`.",
            f"3. Formal Shanghe expected-time segments read: `{len(expected_segments)}` rows from `{ROUTE_EXPECTED_TIME_FP}`; ascent={ascent_min} min; descent={descent_min} min; total={ascent_min + descent_min} min.",
            f"4. IA1 success: `{ok('01_ia1_osm_fetch')}`.",
            f"5. IB0 success: IB0C=`{ok('02_ib0c_anchors')}` / IB0A=`{ok('03_ib0a_control_point_projection')}` / IB0A2=`{ok('04_ib0a2_component_qa')}` / IB0B=`{ok('05_ib0b_mainline')}`.",
            f"6. IB0D success: `{ok('07_ib0d_trimmed_mainline')}`.",
            f"7. IB1A / IB1C / IB1E success: IB1A=`{ok('08_ib1a_route_profile')}` / IB1C=`{ok('09_ib1c_route_profile_semantics')}` / semantic_risk=`{ok('10_ib1c_osm_semantic_risk')}` / IB1G=`{ok('11_ib1g_contour_window_features')}` / IB1E=`{ok('12_ib1e_osm_nlsc_terrain')}`.",
            f"8. IB2D success: `{ok('14_ib2d_candidate_map')}`.",
            f"9. Control point projection v2: rank1_count={v2_projection['rank1_count']}; mean_offset_m={v2_projection['rank1_mean_offset_m']}; max_offset_m={v2_projection['rank1_max_offset_m']}.",
            f"10. Projection comparison against v1: v1_rank1_count={v1_projection['rank1_count']}; v1_mean_offset_m={v1_projection['rank1_mean_offset_m']}; v1_max_offset_m={v1_projection['rank1_max_offset_m']}. v2 uses the 1.4k Bichi junction instead of reflector as the main expected-time via.",
            "11. WARN / REVIEW_REQUIRED: FIT12/FIT11 remain review evidence only; reflector is not a primary expected-time control point. Out-and-back anchors are duplicated by phase.",
            "12. Out-and-back ambiguity: expected; start/end and ascent/descent via are preserved as distinct route positions.",
            f"13. THCI baseline candidate readiness: `{'YES_AFTER_IB2D_QA' if ok('14_ib2d_candidate_map') == 'PASS' else 'NO_STOPPED_BEFORE_IB2D'}`.",
            f"14. Manual review still needed: `{'YES'}`.",
            f"15. py_compile result: `{py_status}`.",
            "16. git status --short:",
            "",
            "```text",
            git_status(),
            "```",
            "",
            "## Stage Summary",
            "",
            "| stage | status | returncode | log |",
            "|---|---|---:|---|",
            *[
                f"| `{row['stage_id']}` | {row['status']} | {row['returncode']} | `{row['log_fp']}` |"
                for row in manifest
            ],
            "",
            "## Stop Condition",
            "",
            (f"Stopped at `{stopped['stage_id']}`: {stopped['failure_reason']}" if stopped else "No failure; candidate run reached final planned stage."),
            "",
            "## Out-And-Back QA Recommendation",
            "",
            "If IB0D fails on `unexpected self-near pairs`, do not bypass it by loosening thresholds blindly. Add an out-and-back-aware QA mode that allows paired ascent/descent proximity only when route-order phase anchors confirm the duplicated corridor.",
            "",
        ]
    )
    (CANDIDATE_ROOT / "hehuan_north_peak_gpx_to_ib2d_candidate_run_report_v2.md").write_text(md, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", action="store_true", help="Allow running with an existing candidate root.")
    args = ap.parse_args()

    INSPECTION_DIR.mkdir(parents=True, exist_ok=True)
    CANDIDATE_ROOT.mkdir(parents=True, exist_ok=True)
    inputs_dir = CANDIDATE_ROOT / "00_inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)

    points, waypoints, parse_error = parse_source_gpx(SOURCE_GPX)
    if len(points) < 2:
        raise RuntimeError("Primary GPX has too few extracted track points")
    distances = cumulative_distances(points)
    sanitized_gpx = inputs_dir / f"{CASE_ID}_sanitized_primary_seed.gpx"
    write_sanitized_gpx(sanitized_gpx, points, waypoints)
    control_points = read_formal_control_points()
    expected_segments = read_formal_expected_time_segments()
    control_points_fp = inputs_dir / f"{CASE_ID}_formal_control_points_v1_3b_v2.csv"
    write_csv(control_points_fp, control_points)
    write_csv(inputs_dir / f"{CASE_ID}_formal_expected_time_segments_v1_3b_v2.csv", expected_segments)
    inspection = inspection_outputs(points, waypoints, parse_error, sanitized_gpx, control_points)

    manifest: list[dict[str, Any]] = [
        {
            "stage_id": "00_gpx_seed_inspection",
            "status": "PASS",
            "returncode": 0,
            "started_at": "",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "command": "internal inspection",
            "log_fp": str(INSPECTION_DIR),
            "failure_reason": "",
        }
    ]

    python = sys.executable
    osm_raw_dir = CANDIDATE_ROOT / "01_ia1_osm_raw"
    # Also mirror IA1 to a case-specific raw root expected by later scripts.
    ia1_cmd = [
        python,
        "scripts/ia_osm/ia1_osm_fetch_raw_friendly_cli_qixing_schema.py",
        "--case-id",
        CASE_ID,
        "--activity-fp",
        str(sanitized_gpx),
        "--out-dir",
        str(osm_raw_dir),
        "--no-map",
    ]
    if not run_cmd("01_ia1_osm_fetch", ia1_cmd, manifest):
        write_reports(manifest, inspection, compile_status(), control_points, expected_segments)
        return

    highway_fp = osm_raw_dir / "osm_highway_raw.geojson"
    ib0c_dir = CANDIDATE_ROOT / "02_ib0c_anchor"
    if not run_cmd(
        "02_ib0c_anchors",
        [
            python,
            "scripts/ib0_route_match/ib0c_anchor_from_landmarks_v1_2_cli_updated.py",
            "--case-id",
            CASE_ID,
            "--case-name",
            CASE_NAME,
            "--activity-fp",
            str(sanitized_gpx),
            "--activity-type",
            "gpx",
            "--osm-raw-dir",
            str(osm_raw_dir),
            "--out-dir",
            str(ib0c_dir),
        ],
        manifest,
    ):
        write_reports(manifest, inspection, compile_status(), control_points, expected_segments)
        return

    # Keep stage subdirectories short enough for Windows path-length limits.
    ib0a_dir = CANDIDATE_ROOT / "03_ib0a"
    (ib0a_dir / CASE_ID).mkdir(parents=True, exist_ok=True)
    if not run_cmd(
        "03_ib0a_control_point_projection",
        [
            python,
            "scripts/ib0_route_match/ib0a_project_control_points_to_osm_candidates.py",
            "--case-id",
            CASE_ID,
            "--control-points-fp",
            str(control_points_fp),
            "--osm-fp",
            str(highway_fp),
            "--out-dir",
            str(ib0a_dir),
            "--no-map",
        ],
        manifest,
    ):
        write_reports(manifest, inspection, compile_status(), control_points, expected_segments)
        return

    ib0a2_dir = CANDIDATE_ROOT / "04_ib0a2"
    if not run_cmd(
        "04_ib0a2_component_qa",
        [
            python,
            "scripts/ib0_route_match/ib0a2_route_axis_anchor_component_qa.py",
            "--case-id",
            CASE_ID,
            "--osm-fp",
            str(highway_fp),
            "--control-points-fp",
            str(control_points_fp),
            "--out-dir",
            str(ib0a2_dir),
        ],
        manifest,
    ):
        write_reports(manifest, inspection, compile_status(), control_points, expected_segments)
        return

    ib0b_dir = CANDIDATE_ROOT / "05_ib0b"
    projection_fp = ib0a_dir / CASE_ID / f"{CASE_ID}_control_points_projected_to_osm_topk.csv"
    ib0c_anchor_fp = ib0c_dir / f"{CASE_ID}_route_anchors.geojson"
    if not run_cmd(
        "05_ib0b_mainline",
        [
            python,
            "scripts/ib0_route_match/ib0b_route_mainline_extract_abtest_v1_cli_updated_control_point_constrained.py",
            "--case-id",
            CASE_ID,
            "--case-name",
            CASE_NAME,
            "--activity-fp",
            str(sanitized_gpx),
            "--activity-type",
            "gpx",
            "--in-fp",
            str(highway_fp),
            "--anchor-fp",
            str(ib0c_anchor_fp),
            "--out-dir",
            str(ib0b_dir),
            "--ia1-dataset-id",
            CASE_ID,
            "--input-stage",
            "ib0_candidates",
            "--route-definition-mode",
            "control_point_constrained",
            "--control-points-fp",
            str(control_points_fp),
            "--control-points-projection-fp",
            str(projection_fp),
            "--control-points-only-anchors",
            "--check-required-ways",
        ],
        manifest,
    ):
        write_reports(manifest, inspection, compile_status(), control_points, expected_segments)
        return

    export_dir = CANDIDATE_ROOT / "06_ib0b_def"
    ordered_path_fp = ib0b_dir / f"{CASE_ID}_mainline_ordered_path_ib0_candidates.geojson"
    if not run_cmd(
        "06_ib0b_export_route_definition",
        [
            python,
            "scripts/ib0_route_match/ib0b_export_route_definition_points_used_v1_2_phase_aware.py",
            "--case-id",
            CASE_ID,
            "--control-points-fp",
            str(control_points_fp),
            "--control-points-projection-fp",
            str(projection_fp),
            "--ordered-path-fp",
            str(ordered_path_fp),
            "--out-dir",
            str(export_dir),
            "--input-stage",
            "ib0_candidates",
        ],
        manifest,
    ):
        write_reports(manifest, inspection, compile_status(), control_points, expected_segments)
        return

    # IB0D expects IB0B-style filenames in its input root.
    ib0d_in = CANDIDATE_ROOT / "07_ib0d_in"
    ib0d_in.mkdir(exist_ok=True)
    for src in [
        ordered_path_fp,
        export_dir / f"{CASE_ID}_route_definition_control_points_used_ib0_candidates.csv",
        export_dir / f"{CASE_ID}_route_definition_control_points_used_ib0_candidates.geojson",
    ]:
        dst = ib0d_in / src.name
        if src.exists() and not dst.exists():
            dst.write_bytes(src.read_bytes())
    ib0d_root = CANDIDATE_ROOT / "07_ib0d"
    if not run_cmd(
        "07_ib0d_trimmed_mainline",
        [
            python,
            "scripts/ib0_route_match/ib0d_v1_3b_control_points_only_contract_qa.py",
            "--case-id",
            CASE_ID,
            "--input-root",
            str(ib0d_in),
            "--out-root",
            str(ib0d_root),
            "--allow-existing-case-dir",
        ],
        manifest,
    ):
        write_reports(manifest, inspection, compile_status(), control_points, expected_segments)
        return

    ib0d_case_dir = ib0d_root / CASE_ID
    trimmed_ordered_path_fp = ib0d_case_dir / "mainline_ordered_path_trimmed.geojson"
    ib1a_dir = CANDIDATE_ROOT / "08_ib1a_route_profile"
    if not run_cmd(
        "08_ib1a_route_profile",
        [
            python,
            "scripts/ib1_route_profile/ib1a_build_route_elevation_profile_cli_updated.py",
            "--case-id",
            CASE_ID,
            "--case-name",
            CASE_NAME,
            "--activity-fp",
            str(sanitized_gpx),
            "--activity-type",
            "gpx",
            "--ordered-path-fp",
            str(trimmed_ordered_path_fp),
            "--mainline-fp",
            str(ib0b_dir / f"{CASE_ID}_mainline_ib0_candidates.geojson"),
            "--out-dir",
            str(ib1a_dir),
        ],
        manifest,
    ):
        write_reports(manifest, inspection, compile_status(), control_points, expected_segments)
        return

    ib1c_sem_dir = CANDIDATE_ROOT / "09_ib1c_route_profile_semantics"
    ib1a_csv = ib1a_dir / f"{CASE_ID}_route_profile.csv"
    ib1a_geojson = ib1a_dir / f"{CASE_ID}_route_profile_points.geojson"
    if not run_cmd(
        "09_ib1c_route_profile_semantics",
        [
            python,
            "scripts/ib1_route_profile/ib1c_enrich_route_profile_semantics_cli_updated.py",
            "--case-id",
            CASE_ID,
            "--case-name",
            CASE_NAME,
            "--profile-csv",
            str(ib1a_csv),
            "--profile-geojson",
            str(ib1a_geojson),
            "--osm-raw-dir",
            str(osm_raw_dir),
            "--out-dir",
            str(ib1c_sem_dir),
        ],
        manifest,
    ):
        write_reports(manifest, inspection, compile_status(), control_points, expected_segments)
        return

    ib1c_risk_dir = CANDIDATE_ROOT / "10_ib1c_osm_semantic_risk"
    if not run_cmd(
        "10_ib1c_osm_semantic_risk",
        [
            python,
            "scripts/ib1_osm_semantics/ib1c_apply_osm_semantic_risk_mapping_cli_updated.py",
            "--case-id",
            CASE_ID,
            "--case-name",
            CASE_NAME,
            "--semantic-csv",
            str(ib1c_sem_dir / f"{CASE_ID}_route_profile_semantic_enriched.csv"),
            "--semantic-geojson",
            str(ib1c_sem_dir / f"{CASE_ID}_route_profile_semantic_enriched.geojson"),
            "--mapping-csv",
            str(PROJECT_ROOT / "configs" / "risk_semantics" / "osm_semantic_risk_mapping_v1_5_support_updated.csv"),
            "--out-dir",
            str(ib1c_risk_dir),
        ],
        manifest,
    ):
        write_reports(manifest, inspection, compile_status(), control_points, expected_segments)
        return

    ib1g_dir = CANDIDATE_ROOT / "11_ib1g_contour_window_features"
    contour_audit_fp = ib1g_dir / "nlsc_contour_coverage_audit_v2.json"
    contour_fp = find_covering_contour(trimmed_ordered_path_fp, contour_audit_fp)
    if contour_fp is None:
        manifest.append(
            {
                "stage_id": "11_ib1g_contour_window_features",
                "status": "FAIL",
                "returncode": 1,
                "started_at": "",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "command": "coverage audit before ib1g_v2_compute_contour_window_features_cli_updated_v1_1.py",
                "log_fp": str(contour_audit_fp),
                "failure_reason": "No local NLSC ContourL.shp covers the Hehuan North route bounds; stop before IB1E/IB2D to avoid fake terrain output.",
            }
        )
        write_reports(manifest, inspection, compile_status(), control_points, expected_segments)
        return

    if not run_cmd(
        "11_ib1g_contour_window_features",
        [
            python,
            "scripts/ib1_nlsc_terrain/ib1g_v2_compute_contour_window_features_cli_updated_v1_1.py",
            "--case-id",
            CASE_ID,
            "--case-name",
            CASE_NAME,
            "--route-line-fp",
            str(trimmed_ordered_path_fp),
            "--contour-fp",
            str(contour_fp),
            "--out-dir",
            str(ib1g_dir),
        ],
        manifest,
    ):
        write_reports(manifest, inspection, compile_status(), control_points, expected_segments)
        return

    ib1e_dir = CANDIDATE_ROOT / "12_ib1e_osm_nlsc_terrain"
    if not run_cmd(
        "12_ib1e_osm_nlsc_terrain",
        [
            python,
            "scripts/ib1_nlsc_terrain/ib1e_enrich_route_profile_with_contour_window_terrain_cli_updated.py",
            "--case-id",
            CASE_ID,
            "--case-name",
            CASE_NAME,
            "--profile-csv",
            str(ib1c_risk_dir / f"{CASE_ID}_osm_semantic_risk_profile.csv"),
            "--profile-geojson",
            str(ib1c_risk_dir / f"{CASE_ID}_osm_semantic_risk_profile.geojson"),
            "--contour-csv",
            str(ib1g_dir / f"{CASE_ID}_contour_window_features.csv"),
            "--contour-geojson",
            str(ib1g_dir / f"{CASE_ID}_contour_window_features.geojson"),
            "--out-dir",
            str(ib1e_dir),
        ],
        manifest,
    ):
        write_reports(manifest, inspection, compile_status(), control_points, expected_segments)
        return

    ib2_dir = CANDIDATE_ROOT / "13_ib2_route_risk_candidate"
    if not run_cmd(
        "13_ib2_route_risk_candidate",
        [
            python,
            "scripts/ib2_route_risk/ib2_v2_route_risk_scoring_cli_updated.py",
            "--case-id",
            CASE_ID,
            "--case-name",
            CASE_NAME,
            "--input-csv",
            str(ib1e_dir / f"{CASE_ID}_route_profile_contour_window_terrain_enriched.csv"),
            "--input-geojson",
            str(ib1e_dir / f"{CASE_ID}_route_profile_contour_window_terrain_enriched.geojson"),
            "--out-dir",
            str(ib2_dir),
        ],
        manifest,
    ):
        write_reports(manifest, inspection, compile_status(), control_points, expected_segments)
        return

    ib2d_dir = CANDIDATE_ROOT / "14_ib2d_route_risk_offline_map_candidate"
    if not run_cmd(
        "14_ib2d_candidate_map",
        [
            python,
            "scripts/ib2_route_risk/ib2d_plot_route_risk_offline_map_cli_updated.py",
            "--case-id",
            CASE_ID,
            "--case-name",
            CASE_NAME,
            "--risk-csv",
            str(ib2_dir / f"{CASE_ID}_route_risk_v2.csv"),
            "--risk-geojson",
            str(ib2_dir / f"{CASE_ID}_route_risk_v2.geojson"),
            "--profile-geojson",
            str(ib1a_geojson),
            "--osm-raw-dir",
            str(osm_raw_dir),
            "--contour-fp",
            str(contour_fp),
            "--out-dir",
            str(ib2d_dir),
        ],
        manifest,
    ):
        write_reports(manifest, inspection, compile_status(), control_points, expected_segments)
        return

    write_reports(manifest, inspection, compile_status(), control_points, expected_segments)


if __name__ == "__main__":
    main()
