import argparse
import csv
import json
import py_compile
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

try:
    from fitparse import FitFile
except Exception as exc:  # pragma: no cover - handled at runtime
    FitFile = None
    FITPARSE_IMPORT_ERROR = exc
else:
    FITPARSE_IMPORT_ERROR = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INVENTORY_DIR = PROJECT_ROOT / "outputs" / "route_onboarding_inventory_butterfly_hehuan_v1"
SEED_DIR = PROJECT_ROOT / "outputs" / "route_seed_preparation_butterfly_hehuan_v1"

BUTTERFLY_CASE = "taichung_guguan_butterfly_valley_waterfall_20260630"
FIT12_CASE = "hehuan_north_peak_roundtrip_fit12_seed_v1"
FIT11_CASE = "hehuan_north_peak_reflector_fit11_review_v1"

INPUTS = {
    "butterfly_gpx": {
        "case_id": BUTTERFLY_CASE,
        "route_name": "Taichung Guguan Butterfly Valley Waterfall",
        "path": PROJECT_ROOT / "activity_input" / "gpx" / "台中谷關 蝴蝶谷瀑布.gpx",
        "source_type": "GPX activity trace",
        "kind": "gpx",
    },
    "hehuan_fit12": {
        "case_id": FIT12_CASE,
        "route_name": "Hehuan North Peak roundtrip FIT 12",
        "path": PROJECT_ROOT / "activity_input" / "fit" / "12" / "12-合歡山北峰來回.fit",
        "source_type": "FIT-derived activity trace",
        "kind": "fit",
    },
    "hehuan_fit11": {
        "case_id": FIT11_CASE,
        "route_name": "Hehuan North Peak reflector FIT 11 review",
        "path": PROJECT_ROOT / "activity_input" / "fit" / "11" / "11-合歡山北峰-反射板.fit",
        "source_type": "FIT-derived activity trace",
        "kind": "fit",
    },
}


@dataclass
class TrackPoint:
    ordered_index: int
    timestamp: str | None
    lat: float
    lon: float
    altitude: float | None = None
    distance: float | None = None
    speed: float | None = None
    heart_rate: float | None = None
    raw_position_lat: Any = None
    raw_position_long: Any = None


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    p1 = radians(lat1)
    p2 = radians(lat2)
    dp = radians(lat2 - lat1)
    dl = radians(lon2 - lon1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * radius * atan2(sqrt(a), sqrt(1 - a))


def iso_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat().replace("+00:00", "Z")
    text = str(value).strip()
    return text or None


def semicircles_to_degrees(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except Exception:
        return None
    # Garmin FIT position fields are normally semicircles. Some decoders can
    # already return degrees; keep plausible degree values as-is.
    if -90 <= number <= 90:
        return number
    return number * 180.0 / (2**31)


def numeric(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def cumulative_distance(points: list[TrackPoint]) -> list[float]:
    distances = [0.0]
    total = 0.0
    for prev, cur in zip(points, points[1:]):
        total += haversine_m(prev.lat, prev.lon, cur.lat, cur.lon)
        distances.append(total)
    return distances


def elevation_gain_loss(points: list[TrackPoint], threshold_m: float = 0.0) -> tuple[float, float]:
    gain = 0.0
    loss = 0.0
    previous = None
    for point in points:
        if point.altitude is None:
            continue
        if previous is not None:
            delta = point.altitude - previous
            if delta > threshold_m:
                gain += delta
            elif delta < -threshold_m:
                loss += abs(delta)
        previous = point.altitude
    return gain, loss


def parse_gpx(path: Path) -> list[TrackPoint]:
    tree = ET.parse(path)
    root = tree.getroot()
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"
    points: list[TrackPoint] = []
    for idx, trkpt in enumerate(root.findall(f".//{ns}trkpt")):
        lat = float(trkpt.attrib["lat"])
        lon = float(trkpt.attrib["lon"])
        ele_node = trkpt.find(f"{ns}ele")
        time_node = trkpt.find(f"{ns}time")
        points.append(
            TrackPoint(
                ordered_index=idx,
                timestamp=time_node.text.strip() if time_node is not None and time_node.text else None,
                lat=lat,
                lon=lon,
                altitude=numeric(ele_node.text) if ele_node is not None else None,
            )
        )
    distances = cumulative_distance(points)
    for point, distance in zip(points, distances):
        point.distance = distance
    return points


def fit_record_rows(path: Path) -> list[dict[str, Any]]:
    if FitFile is None:
        raise RuntimeError(f"fitparse import failed: {FITPARSE_IMPORT_ERROR}")
    fit_file = FitFile(str(path))
    rows: list[dict[str, Any]] = []
    for message in fit_file.get_messages("record"):
        row: dict[str, Any] = {}
        for field in message:
            row[field.name] = field.value
        rows.append(row)
    return rows


def parse_fit(path: Path) -> tuple[list[TrackPoint], list[dict[str, Any]], dict[str, bool]]:
    rows = fit_record_rows(path)
    field_presence = {
        "timestamp": any(row.get("timestamp") is not None for row in rows),
        "position_lat": any(row.get("position_lat") is not None for row in rows),
        "position_long": any(row.get("position_long") is not None for row in rows),
        "enhanced_altitude": any(row.get("enhanced_altitude") is not None for row in rows),
        "distance": any(row.get("distance") is not None for row in rows),
        "enhanced_speed": any(row.get("enhanced_speed") is not None for row in rows),
        "heart_rate": any(row.get("heart_rate") is not None for row in rows),
    }

    points: list[TrackPoint] = []
    for row in rows:
        lat = semicircles_to_degrees(row.get("position_lat"))
        lon = semicircles_to_degrees(row.get("position_long"))
        if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        points.append(
            TrackPoint(
                ordered_index=len(points),
                timestamp=iso_value(row.get("timestamp")),
                lat=lat,
                lon=lon,
                altitude=numeric(row.get("enhanced_altitude") if row.get("enhanced_altitude") is not None else row.get("altitude")),
                distance=numeric(row.get("distance")),
                speed=numeric(row.get("enhanced_speed") if row.get("enhanced_speed") is not None else row.get("speed")),
                heart_rate=numeric(row.get("heart_rate")),
                raw_position_lat=row.get("position_lat"),
                raw_position_long=row.get("position_long"),
            )
        )
    return points, rows, field_presence


def segment_metrics(points: list[TrackPoint]) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    for idx, point in enumerate(points):
        if idx == 0:
            metrics.append({"segment_distance_m": 0.0, "segment_speed_mps": None, "suspect_jump": False, "stationary_review": False})
            continue
        prev = points[idx - 1]
        distance = haversine_m(prev.lat, prev.lon, point.lat, point.lon)
        dt = None
        try:
            if prev.timestamp and point.timestamp:
                prev_dt = datetime.fromisoformat(prev.timestamp.replace("Z", "+00:00"))
                cur_dt = datetime.fromisoformat(point.timestamp.replace("Z", "+00:00"))
                dt = max(0.0, (cur_dt - prev_dt).total_seconds())
        except Exception:
            dt = None
        speed = distance / dt if dt and dt > 0 else None
        metrics.append(
            {
                "segment_distance_m": distance,
                "segment_speed_mps": speed,
                "suspect_jump": distance >= 100.0 or (speed is not None and speed >= 8.0),
                "stationary_review": distance <= 3.0 and (dt is None or dt >= 5.0),
            }
        )
    return metrics


def summarize_points(label: str, case_id: str, path: Path, kind: str, points: list[TrackPoint], field_presence: dict[str, bool] | None = None) -> dict[str, Any]:
    metrics = segment_metrics(points) if points else []
    distances = cumulative_distance(points) if points else []
    for point, distance in zip(points, distances):
        if point.distance is None:
            point.distance = distance
    gain, loss = elevation_gain_loss(points)
    start_end_m = haversine_m(points[0].lat, points[0].lon, points[-1].lat, points[-1].lon) if len(points) >= 2 else None
    route_length_m = distances[-1] if distances else 0.0
    max_jump = max((m["segment_distance_m"] for m in metrics), default=0.0)
    suspect_jump_count = sum(1 for m in metrics if m["suspect_jump"])
    stationary_count = sum(1 for m in metrics if m["stationary_review"])
    out_and_back = bool(points and start_end_m is not None and start_end_m <= max(500.0, route_length_m * 0.15))
    return {
        "label": label,
        "case_id": case_id,
        "source_path": str(path),
        "source_kind": kind,
        "input_exists": path.exists(),
        "read_success": bool(points),
        "point_count": len(points),
        "has_time": any(p.timestamp for p in points),
        "has_elevation": any(p.altitude is not None for p in points),
        "has_distance": any(p.distance is not None for p in points),
        "has_speed": any(p.speed is not None for p in points),
        "has_heart_rate": any(p.heart_rate is not None for p in points),
        "fit_has_timestamp": field_presence.get("timestamp") if field_presence else None,
        "fit_has_position_lat": field_presence.get("position_lat") if field_presence else None,
        "fit_has_position_long": field_presence.get("position_long") if field_presence else None,
        "fit_has_enhanced_altitude": field_presence.get("enhanced_altitude") if field_presence else None,
        "fit_has_distance": field_presence.get("distance") if field_presence else None,
        "fit_has_enhanced_speed": field_presence.get("enhanced_speed") if field_presence else None,
        "fit_has_heart_rate": field_presence.get("heart_rate") if field_presence else None,
        "start_lat": points[0].lat if points else None,
        "start_lon": points[0].lon if points else None,
        "end_lat": points[-1].lat if points else None,
        "end_lon": points[-1].lon if points else None,
        "route_length_estimate_m": route_length_m,
        "distance_min_m": min((p.distance for p in points if p.distance is not None), default=None),
        "distance_max_m": max((p.distance for p in points if p.distance is not None), default=None),
        "elevation_min_m": min((p.altitude for p in points if p.altitude is not None), default=None),
        "elevation_max_m": max((p.altitude for p in points if p.altitude is not None), default=None),
        "elevation_gain_estimate_m": gain,
        "elevation_loss_estimate_m": loss,
        "start_end_distance_m": start_end_m,
        "suspected_out_and_back": out_and_back,
        "stationary_review_count": stationary_count,
        "suspect_jump_count": suspect_jump_count,
        "max_jump_distance_m": max_jump,
        "can_extract_route_seed_gpx": bool(points and len(points) >= 2),
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_gpx(path: Path, name: str, points: list[TrackPoint], source_type: str, official: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="prepare_route_seed_butterfly_hehuan_v1" xmlns="http://www.topografix.com/GPX/1/1">',
        "  <metadata>",
        f"    <name>{escape(name)}</name>",
        f"    <desc>source_type = {escape(source_type)}; official_route = {str(official).lower()}</desc>",
        "  </metadata>",
        f"  <trk><name>{escape(name)}</name><trkseg>",
    ]
    for point in points:
        lines.append(f'    <trkpt lat="{point.lat:.8f}" lon="{point.lon:.8f}">')
        if point.altitude is not None:
            lines.append(f"      <ele>{point.altitude:.2f}</ele>")
        if point.timestamp:
            lines.append(f"      <time>{escape(point.timestamp)}</time>")
        lines.append("    </trkpt>")
    lines.extend(["  </trkseg></trk>", "</gpx>"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def point_rows(points: list[TrackPoint], include_qc: bool = False) -> list[dict[str, Any]]:
    metrics = segment_metrics(points)
    distances = cumulative_distance(points)
    rows: list[dict[str, Any]] = []
    for point, metric, cum_distance in zip(points, metrics, distances):
        row = {
            "ordered_index": point.ordered_index,
            "timestamp": point.timestamp,
            "lat": point.lat,
            "lon": point.lon,
            "altitude": point.altitude,
            "distance": point.distance if point.distance is not None else cum_distance,
            "distance_cumulative_haversine_m": cum_distance,
            "speed": point.speed,
            "heart_rate": point.heart_rate,
        }
        if include_qc:
            row.update(metric)
        rows.append(row)
    return rows


def raw_fit_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wanted = ["timestamp", "position_lat", "position_long", "enhanced_altitude", "distance", "enhanced_speed", "heart_rate"]
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        item = {"record_index": idx}
        for key in wanted:
            item[key] = iso_value(row.get(key)) if key == "timestamp" else row.get(key)
        out.append(item)
    return out


def output_seed_package(case_id: str, route_name: str, source_type: str, points: list[TrackPoint], summary: dict[str, Any], fit_rows: list[dict[str, Any]] | None = None) -> None:
    out_dir = SEED_DIR / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    if fit_rows is not None:
        write_csv(out_dir / "activity_trace_raw_fields.csv", raw_fit_rows(fit_rows))
        write_csv(out_dir / "activity_trace_cleaned.csv", point_rows(points, include_qc=True))
        write_gpx(out_dir / "route_seed_from_fit.gpx", route_name, points, source_type=source_type, official=False)
    else:
        write_gpx(out_dir / "route_seed.gpx", route_name, points, source_type=source_type, official=False)

    write_csv(out_dir / "route_seed_points.csv", point_rows(points))
    with (out_dir / "route_seed_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
    (out_dir / "route_seed_qc.md").write_text(seed_qc_markdown(summary), encoding="utf-8")


def output_coverage(case_id: str) -> dict[str, Any]:
    outputs = PROJECT_ROOT / "outputs"
    osm_raw = PROJECT_ROOT / "osm_raw_output" / case_id
    parents: dict[str, int] = {}
    if outputs.exists():
        for file in outputs.rglob("*"):
            if file.is_file() and case_id in str(file):
                rel = file.relative_to(outputs)
                parent = rel.parts[0] if rel.parts else ""
                parents[parent] = parents.get(parent, 0) + 1
    def has(prefix: str) -> bool:
        return any(parent.lower().startswith(prefix.lower()) for parent in parents)
    return {
        "osm_raw_file_count": sum(1 for _ in osm_raw.glob("*")) if osm_raw.exists() else 0,
        "has_ia1_osm_raw": osm_raw.exists(),
        "has_ib0": has("ib0"),
        "has_ib1": has("ib1"),
        "has_ib2": has("ib2"),
        "has_thci": has("thci"),
        "output_parent_counts": parents,
    }


def seed_qc_markdown(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# Route seed QC - {summary['case_id']}",
            "",
            f"- Source: `{summary['source_path']}`",
            f"- Source kind: `{summary['source_kind']}`",
            f"- Official route: `false`",
            f"- Read success: `{summary['read_success']}`",
            f"- Point count: `{summary['point_count']}`",
            f"- Has time/elevation/distance/speed/HR: `{summary['has_time']}` / `{summary['has_elevation']}` / `{summary['has_distance']}` / `{summary['has_speed']}` / `{summary['has_heart_rate']}`",
            f"- Route length estimate m: `{summary['route_length_estimate_m']:.1f}`",
            f"- Distance range m: `{summary['distance_min_m']}` to `{summary['distance_max_m']}`",
            f"- Elevation min/max m: `{summary['elevation_min_m']}` to `{summary['elevation_max_m']}`",
            f"- Elevation gain/loss estimate m: `{summary['elevation_gain_estimate_m']:.1f}` / `{summary['elevation_loss_estimate_m']:.1f}`",
            f"- Start: `{summary['start_lat']}, {summary['start_lon']}`",
            f"- End: `{summary['end_lat']}, {summary['end_lon']}`",
            f"- Start/end distance m: `{summary['start_end_distance_m']}`",
            f"- Suspected out-and-back: `{summary['suspected_out_and_back']}`",
            f"- Stationary review count: `{summary['stationary_review_count']}`",
            f"- Suspect jump count: `{summary['suspect_jump_count']}`",
            f"- Max jump distance m: `{summary['max_jump_distance_m']:.1f}`",
            "",
            "This seed is an onboarding artifact only and is not an official route or scoring input.",
            "",
        ]
    )


def inventory_markdown(summaries: list[dict[str, Any]], coverages: dict[str, dict[str, Any]], git_status: str) -> str:
    butterfly = summaries[0]
    fit12 = summaries[1]
    fit11 = summaries[2]
    lines = [
        "# Route onboarding inventory: Butterfly Valley GPX and Hehuan North Peak FIT",
        "",
        f"Inventory generated: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}",
        f"Project root: `{PROJECT_ROOT}`",
        "",
        "Constraints observed: no formal scoring script changes, no `risk_semantics` config changes, no existing four-route recompute, no official batch edits, no v1.3 weather-terrain fusion, and no THCI scoring.",
        "",
        "## Input Read Status",
        "",
        "| input | case id | exists | read | points | time | elevation | distance | speed | HR | out-and-back | seed extractable |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in summaries:
        lines.append(
            f"| {item['label']} | `{item['case_id']}` | {item['input_exists']} | {item['read_success']} | {item['point_count']} | {item['has_time']} | {item['has_elevation']} | {item['has_distance']} | {item['has_speed']} | {item['has_heart_rate']} | {item['suspected_out_and_back']} | {item['can_extract_route_seed_gpx']} |"
        )
    lines.extend(
        [
            "",
            "## Butterfly Valley GPX",
            "",
            f"- Input: `{butterfly['source_path']}`",
            f"- Suggested case id: `{BUTTERFLY_CASE}`. If a seed-specific suffix is needed, use `{BUTTERFLY_CASE}_gpx_seed_v1` without changing the existing formal case id.",
            f"- Point count: {butterfly['point_count']}",
            f"- Start/end: `{butterfly['start_lat']}, {butterfly['start_lon']}` -> `{butterfly['end_lat']}, {butterfly['end_lon']}`",
            f"- Length estimate: {butterfly['route_length_estimate_m']:.1f} m",
            f"- Elevation min/max/gain/loss: {butterfly['elevation_min_m']} / {butterfly['elevation_max_m']} / {butterfly['elevation_gain_estimate_m']:.1f} / {butterfly['elevation_loss_estimate_m']:.1f} m",
            f"- Suspected out-and-back: {butterfly['suspected_out_and_back']} (start/end distance {butterfly['start_end_distance_m']:.1f} m)",
            f"- Existing output coverage: IA1={coverages[BUTTERFLY_CASE]['has_ia1_osm_raw']}, IB0={coverages[BUTTERFLY_CASE]['has_ib0']}, IB1={coverages[BUTTERFLY_CASE]['has_ib1']}, IB2={coverages[BUTTERFLY_CASE]['has_ib2']}, THCI={coverages[BUTTERFLY_CASE]['has_thci']}",
            "- Conclusion: can directly serve as a route seed input for onboarding. Existing formal lineage should remain under the existing case id.",
            "",
            "## Hehuan North Peak FIT 12",
            "",
            f"- Input: `{fit12['source_path']}`",
            f"- Suggested case id: `{FIT12_CASE}`",
            f"- Required FIT fields: timestamp={fit12['fit_has_timestamp']}, position_lat={fit12['fit_has_position_lat']}, position_long={fit12['fit_has_position_long']}, enhanced_altitude={fit12['fit_has_enhanced_altitude']}, distance={fit12['fit_has_distance']}, enhanced_speed={fit12['fit_has_enhanced_speed']}, heart_rate={fit12['fit_has_heart_rate']}",
            f"- Point count: {fit12['point_count']}",
            f"- Distance range: {fit12['distance_min_m']} to {fit12['distance_max_m']} m",
            f"- Elevation min/max: {fit12['elevation_min_m']} to {fit12['elevation_max_m']} m",
            f"- Suspected out-and-back: {fit12['suspected_out_and_back']} (start/end distance {fit12['start_end_distance_m']:.1f} m)",
            f"- Stationary review count: {fit12['stationary_review_count']}; suspect jump count: {fit12['suspect_jump_count']}; max jump: {fit12['max_jump_distance_m']:.1f} m",
            "- Conclusion: suitable as the primary FIT-derived route seed candidate, but it remains an activity trace and must not be called an official route.",
            "",
            "## Hehuan North Peak FIT 11",
            "",
            f"- Input: `{fit11['source_path']}`",
            f"- Suggested case id: `{FIT11_CASE}`",
            f"- Required FIT fields: timestamp={fit11['fit_has_timestamp']}, position_lat={fit11['fit_has_position_lat']}, position_long={fit11['fit_has_position_long']}, enhanced_altitude={fit11['fit_has_enhanced_altitude']}, distance={fit11['fit_has_distance']}, enhanced_speed={fit11['fit_has_enhanced_speed']}, heart_rate={fit11['fit_has_heart_rate']}",
            f"- Point count: {fit11['point_count']}",
            f"- Distance range: {fit11['distance_min_m']} to {fit11['distance_max_m']} m",
            f"- Elevation min/max: {fit11['elevation_min_m']} to {fit11['elevation_max_m']} m",
            f"- Suspected out-and-back: {fit11['suspected_out_and_back']} (start/end distance {fit11['start_end_distance_m']:.1f} m)",
            f"- Stationary review count: {fit11['stationary_review_count']}; suspect jump count: {fit11['suspect_jump_count']}; max jump: {fit11['max_jump_distance_m']:.1f} m",
            "- Role judgment: review / variant activity trace, likely reflecting a reflector-board branch or alternate activity context. Do not merge with FIT 12 for the primary seed.",
            "",
            "## Suggested Control Points / Anchors",
            "",
            "- Butterfly Valley: existing start, trail split ascent, waterfall turnaround, trail split descent, end anchors are adequate.",
            "- Hehuan FIT 12: route start/trailhead, early access connector, ridge/distance marker anchors, north peak summit/turnaround, return endpoint.",
            "- Hehuan FIT 11: same anchor vocabulary plus reflector-board/branch point as a review-only anchor.",
            "",
            "## Next Pipeline Recommendation",
            "",
            "- Butterfly Valley: can proceed by referencing existing IA1 -> IB0 -> IB1 -> IB2 lineage; do not rerun or overwrite existing outputs unless explicitly requested.",
            "- Hehuan FIT 12: proceed to IA1 -> IB0 route seed onboarding after anchor proposal/review.",
            "- Hehuan FIT 11: keep as review / variant; do not merge into FIT 12 primary seed.",
            "",
            "## Output Parent Counts For Butterfly Existing Case",
            "",
        ]
    )
    for parent, count in sorted(coverages[BUTTERFLY_CASE]["output_parent_counts"].items()):
        lines.append(f"- `{parent}`: {count}")
    lines.extend(["", "## git status --short", "", "```", git_status.strip(), "```", ""])
    return "\n".join(lines)


def preparation_report(summaries: list[dict[str, Any]], py_compile_result: str, git_status: str) -> str:
    b, f12, f11 = summaries
    return "\n".join(
        [
            "# Route seed preparation report v1",
            "",
            f"Generated: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}",
            "",
            "## Answers",
            "",
            f"1. Three inputs read successfully: Butterfly={b['read_success']}, FIT12={f12['read_success']}, FIT11={f11['read_success']}.",
            f"2. Butterfly can directly serve as route seed: {b['can_extract_route_seed_gpx']} / out-and-back={b['suspected_out_and_back']}.",
            f"3. FIT12 is suitable as the primary FIT-derived route seed candidate: {f12['can_extract_route_seed_gpx']}; it remains an activity trace, not an official route.",
            f"4. FIT11 differs from FIT12 by role and should be treated as a reflector/variant review trace; FIT12 case id is `{FIT12_CASE}`, FIT11 review id is `{FIT11_CASE}`.",
            "5. Recommendation: FIT11 should remain review / variant only and should not be merged into the primary FIT12 route seed.",
            "6. Route seed metrics:",
            "",
            "| case id | points | length m | distance max m | elevation min | elevation max | out-and-back | suspect jumps | max jump m |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            *[
                f"| `{s['case_id']}` | {s['point_count']} | {s['route_length_estimate_m']:.1f} | {s['distance_max_m']} | {s['elevation_min_m']} | {s['elevation_max_m']} | {s['suspected_out_and_back']} | {s['suspect_jump_count']} | {s['max_jump_distance_m']:.1f} |"
                for s in summaries
            ],
            "",
            "7. Needed anchors: Butterfly existing five-anchor out-and-back sequence; Hehuan trailhead/start, ridge or distance markers, north peak summit/turnaround, return endpoint; FIT11 also needs reflector-board branch/review anchor.",
            "8. Next step: Butterfly may reference existing IA1 -> IB0 -> IB1 -> IB2 onboarding lineage. Hehuan FIT12 can proceed to IA1 -> IB0 after anchor review. FIT11 should stay review-only unless later promoted.",
            f"9. py_compile result: `{py_compile_result.strip()}`",
            "10. git status --short:",
            "",
            "```",
            git_status.strip(),
            "```",
            "",
        ]
    )


def current_git_status() -> str:
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return result.stdout or "No output."


def py_compile_self() -> str:
    try:
        py_compile.compile(str(Path(__file__).resolve()), doraise=True)
    except Exception as exc:
        return f"FAIL: {exc}"
    return "PASS"


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare route onboarding inventory and route seeds for Butterfly Valley and Hehuan North Peak.")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    args = parser.parse_args()
    if Path(args.project_root).resolve() != PROJECT_ROOT.resolve():
        raise SystemExit("This script is scoped to the repository root that contains it.")

    INVENTORY_DIR.mkdir(parents=True, exist_ok=True)
    SEED_DIR.mkdir(parents=True, exist_ok=True)

    summaries: list[dict[str, Any]] = []
    coverages: dict[str, dict[str, Any]] = {}

    butterfly_meta = INPUTS["butterfly_gpx"]
    butterfly_points = parse_gpx(butterfly_meta["path"])
    butterfly_summary = summarize_points("butterfly_gpx", butterfly_meta["case_id"], butterfly_meta["path"], butterfly_meta["kind"], butterfly_points)
    summaries.append(butterfly_summary)
    coverages[butterfly_meta["case_id"]] = output_coverage(butterfly_meta["case_id"])
    output_seed_package(butterfly_meta["case_id"], butterfly_meta["route_name"], butterfly_meta["source_type"], butterfly_points, butterfly_summary)

    for key in ["hehuan_fit12", "hehuan_fit11"]:
        meta = INPUTS[key]
        points, raw_rows, field_presence = parse_fit(meta["path"])
        summary = summarize_points(key, meta["case_id"], meta["path"], meta["kind"], points, field_presence=field_presence)
        summaries.append(summary)
        coverages[meta["case_id"]] = output_coverage(meta["case_id"])
        output_seed_package(meta["case_id"], meta["route_name"], meta["source_type"], points, summary, fit_rows=raw_rows)

    inventory_csv_fields = [
        "label", "case_id", "source_path", "source_kind", "input_exists", "read_success", "point_count",
        "has_time", "has_elevation", "has_distance", "has_speed", "has_heart_rate",
        "fit_has_timestamp", "fit_has_position_lat", "fit_has_position_long", "fit_has_enhanced_altitude",
        "fit_has_distance", "fit_has_enhanced_speed", "fit_has_heart_rate",
        "start_lat", "start_lon", "end_lat", "end_lon", "route_length_estimate_m",
        "distance_min_m", "distance_max_m", "elevation_min_m", "elevation_max_m",
        "elevation_gain_estimate_m", "elevation_loss_estimate_m", "start_end_distance_m",
        "suspected_out_and_back", "stationary_review_count", "suspect_jump_count",
        "max_jump_distance_m", "can_extract_route_seed_gpx",
    ]
    git_status = current_git_status()
    write_csv(INVENTORY_DIR / "route_onboarding_inventory_butterfly_hehuan_v1.csv", summaries, inventory_csv_fields)
    (INVENTORY_DIR / "route_onboarding_inventory_butterfly_hehuan_v1.md").write_text(inventory_markdown(summaries, coverages, git_status), encoding="utf-8")

    summary_rows = [
        {
            "case_id": s["case_id"],
            "label": s["label"],
            "source_path": s["source_path"],
            "point_count": s["point_count"],
            "route_length_estimate_m": s["route_length_estimate_m"],
            "distance_max_m": s["distance_max_m"],
            "elevation_min_m": s["elevation_min_m"],
            "elevation_max_m": s["elevation_max_m"],
            "elevation_gain_estimate_m": s["elevation_gain_estimate_m"],
            "elevation_loss_estimate_m": s["elevation_loss_estimate_m"],
            "suspected_out_and_back": s["suspected_out_and_back"],
            "suspect_jump_count": s["suspect_jump_count"],
            "max_jump_distance_m": s["max_jump_distance_m"],
            "seed_output_dir": str(SEED_DIR / s["case_id"]),
            "official_route": False,
        }
        for s in summaries
    ]
    write_csv(SEED_DIR / "route_seed_preparation_summary_v1.csv", summary_rows)

    py_compile_result = py_compile_self()
    (SEED_DIR / "route_seed_preparation_report_v1.md").write_text(
        preparation_report(summaries, py_compile_result=py_compile_result, git_status=git_status),
        encoding="utf-8",
    )

    print(json.dumps({"inventory_dir": str(INVENTORY_DIR), "seed_dir": str(SEED_DIR), "cases": [s["case_id"] for s in summaries]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
