#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IB3W station candidate ranking v1.

Purpose:
- Rank Top-N weather and water station candidates for a single smoke-test activity.
- Provide transparent ranking evidence before building any formal IB3W joined dataset.
- Keep missing weather/water as missing evidence; do not synthesize zero-valued normal fallback.

Non-goals:
- No full pipeline.
- No production IB3W join.
- No IB3M behavior analysis.
- No route risk / radar / THCI adjustment.
- Outputs are QA only and should not be committed.
"""

from __future__ import annotations

import argparse
import csv
import html
import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


GARMIN_EPOCH = datetime(1989, 12, 31, tzinfo=timezone.utc)
UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


@dataclass
class ActivityWindow:
    case_id: str
    activity_id: str
    route_folder: str
    start_time: datetime
    end_time: datetime
    representative_lat: float
    representative_lon: float
    representative_ele_m: Optional[float]
    rows_read: int
    timestamp_epoch_used: str


def to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_iso_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def infer_timestamp(value: float) -> Tuple[datetime, str]:
    unix_dt = UNIX_EPOCH + timedelta(seconds=value)
    garmin_dt = GARMIN_EPOCH + timedelta(seconds=value)

    if 2015 <= unix_dt.year <= 2035:
        return unix_dt, "unix"
    if 2015 <= garmin_dt.year <= 2035:
        return garmin_dt, "garmin_fit"
    return unix_dt, "unix_fallback"


def pick_first_float(row: Dict[str, str], names: Iterable[str]) -> Optional[float]:
    for name in names:
        if name in row:
            value = to_float(row.get(name))
            if value is not None:
                return value
    return None


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * r * math.asin(math.sqrt(a))


def read_activity_window(input_csv: Path, case_id: str, route_folder: str, activity_id: str) -> ActivityWindow:
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    epoch_used: Optional[str] = None

    lat_values: List[float] = []
    lon_values: List[float] = []
    ele_values: List[float] = []
    rows_read = 0

    with input_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "timestamp_s" not in reader.fieldnames:
            raise RuntimeError("Activity CSV missing timestamp_s.")

        for row in reader:
            rows_read += 1

            ts_value = to_float(row.get("timestamp_s"))
            if ts_value is not None:
                ts_dt, epoch = infer_timestamp(ts_value)
                if epoch_used is None:
                    epoch_used = epoch
                start = ts_dt if start is None or ts_dt < start else start
                end = ts_dt if end is None or ts_dt > end else end

            lat = pick_first_float(row, ["calibrated_lat", "display_lat", "lat", "raw_lat"])
            lon = pick_first_float(row, ["calibrated_lon", "display_lon", "lon", "raw_lon"])
            ele = pick_first_float(row, ["calibrated_elevation_m", "terrain_elevation_m", "ele_m", "raw_elevation_m"])

            if lat is not None and lon is not None:
                lat_values.append(lat)
                lon_values.append(lon)
            if ele is not None:
                ele_values.append(ele)

    if start is None or end is None:
        raise RuntimeError("Could not infer activity time window.")
    if not lat_values or not lon_values:
        raise RuntimeError("Could not infer representative location.")

    return ActivityWindow(
        case_id=case_id,
        activity_id=activity_id,
        route_folder=route_folder,
        start_time=start,
        end_time=end,
        representative_lat=sum(lat_values) / len(lat_values),
        representative_lon=sum(lon_values) / len(lon_values),
        representative_ele_m=(sum(ele_values) / len(ele_values) if ele_values else None),
        rows_read=rows_read,
        timestamp_epoch_used=epoch_used or "unknown",
    )


def get_source_status(conn: sqlite3.Connection) -> Dict[str, Dict[str, str]]:
    result: Dict[str, Dict[str, str]] = {}
    sql = """
    SELECT source, schedule_mode, last_success_at, last_status, updated_at
    FROM source_status
    """
    for source, schedule_mode, last_success_at, last_status, updated_at in conn.execute(sql):
        result[str(source)] = {
            "schedule_mode": str(schedule_mode or ""),
            "last_success_at": str(last_success_at or ""),
            "last_status": str(last_status or ""),
            "updated_at": str(updated_at or ""),
        }
    return result


def temporal_relation_and_gap(activity: ActivityWindow, obs_min: Optional[datetime], obs_max: Optional[datetime]) -> Tuple[str, str, str]:
    if obs_min is None or obs_max is None:
        return "no_observation_in_window", "", ""

    act_start = activity.start_time
    act_end = activity.end_time
    obs_min_utc = obs_min.astimezone(timezone.utc)
    obs_max_utc = obs_max.astimezone(timezone.utc)

    if obs_max_utc < act_start:
        signed_gap = (act_start - obs_max_utc).total_seconds() / 60.0
        return "before_activity", round(signed_gap, 3), round(abs(signed_gap), 3)

    if obs_min_utc > act_end:
        signed_gap = (act_start - obs_min_utc).total_seconds() / 60.0
        return "after_activity", round(signed_gap, 3), round(abs(signed_gap), 3)

    return "overlaps_activity_window", 0.0, 0.0


def value_stats(values: List[Optional[float]]) -> Tuple[int, str, str, str, str]:
    valid = [v for v in values if v is not None]
    if not valid:
        return 0, "", "", "", ""
    return len(valid), min(valid), max(valid), round(sum(valid) / len(valid), 6), valid[-1]


def rank_score(
    route_distance_m: float,
    coverage_ratio: float,
    absolute_temporal_gap_minutes: Optional[float],
    elevation_delta_m: Optional[float],
    source_status_ok: bool,
    variable_available: bool,
) -> float:
    distance_score = max(0.0, 1.0 - min(route_distance_m, 20000.0) / 20000.0)
    coverage_score = max(0.0, min(coverage_ratio, 1.0))

    if absolute_temporal_gap_minutes is None:
        temporal_score = 0.0
    else:
        temporal_score = max(0.0, 1.0 - min(absolute_temporal_gap_minutes, 1440.0) / 1440.0)

    if elevation_delta_m is None:
        elevation_score = 0.5
    else:
        elevation_score = max(0.0, 1.0 - min(elevation_delta_m, 1000.0) / 1000.0)

    source_score = 1.0 if source_status_ok else 0.0
    variable_score = 1.0 if variable_available else 0.0

    return round(
        0.25 * distance_score
        + 0.25 * coverage_score
        + 0.20 * temporal_score
        + 0.10 * elevation_score
        + 0.10 * source_score
        + 0.10 * variable_score,
        6,
    )


def rank_weather_candidates(
    conn: sqlite3.Connection,
    activity: ActivityWindow,
    top_n: int,
    tolerance_hours: float,
    bounding_margin_deg: float,
) -> List[Dict[str, Any]]:
    source_status = get_source_status(conn)
    window_start = activity.start_time - timedelta(hours=tolerance_hours)
    window_end = activity.end_time + timedelta(hours=tolerance_hours)

    sql = """
    SELECT
      source,
      dataset_code,
      station_id,
      COALESCE(station_name, '') AS station_name,
      latitude,
      longitude,
      elevation_m,
      MIN(obs_time) AS all_obs_min,
      MAX(obs_time) AS all_obs_max,
      COUNT(*) AS total_rows
    FROM weather_observations
    WHERE latitude IS NOT NULL
      AND longitude IS NOT NULL
      AND latitude BETWEEN ? AND ?
      AND longitude BETWEEN ? AND ?
    GROUP BY source, dataset_code, station_id
    """
    params = (
        activity.representative_lat - bounding_margin_deg,
        activity.representative_lat + bounding_margin_deg,
        activity.representative_lon - bounding_margin_deg,
        activity.representative_lon + bounding_margin_deg,
    )

    rows: List[Dict[str, Any]] = []

    for row in conn.execute(sql, params):
        source = str(row[0])
        dataset_code = str(row[1])
        station_id = str(row[2])
        station_name = str(row[3])
        lat = float(row[4])
        lon = float(row[5])
        ele = float(row[6]) if row[6] is not None else None
        all_obs_min = parse_iso_dt(row[7])
        all_obs_max = parse_iso_dt(row[8])
        total_rows = int(row[9])

        distance_m = haversine_m(activity.representative_lat, activity.representative_lon, lat, lon)
        elevation_delta = abs(ele - activity.representative_ele_m) if ele is not None and activity.representative_ele_m is not None else None

        obs_sql = """
        SELECT
          obs_time,
          precipitation_1hr_mm,
          wind_speed_ms,
          temperature_c,
          COALESCE(qc_flag, '') AS qc_flag
        FROM weather_observations
        WHERE source = ?
          AND dataset_code = ?
          AND station_id = ?
          AND obs_time BETWEEN ? AND ?
        ORDER BY obs_time
        """
        obs_params = (source, dataset_code, station_id, window_start.isoformat(), window_end.isoformat())
        obs_rows = list(conn.execute(obs_sql, obs_params))

        obs_times = [parse_iso_dt(r[0]) for r in obs_rows]
        obs_times_valid = [t for t in obs_times if t is not None]
        obs_min = min(obs_times_valid) if obs_times_valid else None
        obs_max = max(obs_times_valid) if obs_times_valid else None

        precip_count, precip_min, precip_max, precip_mean, precip_last = value_stats([to_float(r[1]) for r in obs_rows])
        wind_count, wind_min, wind_max, wind_mean, wind_last = value_stats([to_float(r[2]) for r in obs_rows])
        temp_count, temp_min, temp_max, temp_mean, temp_last = value_stats([to_float(r[3]) for r in obs_rows])

        coverage_ratio = 1.0 if obs_rows else 0.0
        relation, signed_gap, abs_gap = temporal_relation_and_gap(activity, obs_min, obs_max)
        abs_gap_float = float(abs_gap) if abs_gap != "" else None

        status = source_status.get(source, {})
        source_status_ok = status.get("last_status", "").lower() == "success"
        variable_available = any([precip_count, wind_count, temp_count])

        score = rank_score(distance_m, coverage_ratio, abs_gap_float, elevation_delta, source_status_ok, variable_available)

        rows.append({
            "case_id": activity.case_id,
            "activity_id": activity.activity_id,
            "candidate_type": "weather",
            "source": source,
            "dataset_code": dataset_code,
            "station_id": station_id,
            "station_name": station_name,
            "latitude": lat,
            "longitude": lon,
            "elevation_m": ele if ele is not None else "",
            "route_distance_m": round(distance_m, 3),
            "activity_start_time": activity.start_time.isoformat(),
            "activity_end_time": activity.end_time.isoformat(),
            "window_tolerance_hours": tolerance_hours,
            "obs_rows_in_tolerance_window": len(obs_rows),
            "obs_time_min_in_window": obs_min.isoformat() if obs_min else "",
            "obs_time_max_in_window": obs_max.isoformat() if obs_max else "",
            "all_obs_time_min": all_obs_min.isoformat() if all_obs_min else "",
            "all_obs_time_max": all_obs_max.isoformat() if all_obs_max else "",
            "total_station_rows": total_rows,
            "activity_time_coverage_ratio": coverage_ratio,
            "temporal_relation": relation,
            "signed_temporal_gap_minutes": signed_gap,
            "absolute_temporal_gap_minutes": abs_gap,
            "elevation_delta_m": round(elevation_delta, 3) if elevation_delta is not None else "",
            "source_last_status": status.get("last_status", ""),
            "source_last_success_at": status.get("last_success_at", ""),
            "precipitation_1hr_available_count": precip_count,
            "wind_speed_available_count": wind_count,
            "temperature_available_count": temp_count,
            "precipitation_1hr_mean": precip_mean,
            "wind_speed_mean": wind_mean,
            "temperature_mean": temp_mean,
            "variable_available": str(variable_available).lower(),
            "ranking_score": score,
            "ranking_reason": "distance+coverage+temporal_gap+elevation+source_status+variable_availability",
            "zero_fallback_detected": "false",
            "notes": "Ranking evidence only; no formal IB3W joined dataset.",
        })

    rows.sort(key=lambda r: (-float(r["ranking_score"]), float(r["route_distance_m"])))
    for idx, row in enumerate(rows[:top_n], start=1):
        row["candidate_rank"] = idx
    return rows[:top_n]


def rank_water_candidates(
    conn: sqlite3.Connection,
    activity: ActivityWindow,
    top_n: int,
    tolerance_hours: float,
    bounding_margin_deg: float,
) -> List[Dict[str, Any]]:
    source_status = get_source_status(conn)
    window_start = activity.start_time - timedelta(hours=tolerance_hours)
    window_end = activity.end_time + timedelta(hours=tolerance_hours)

    sql = """
    SELECT
      source,
      dataset_code,
      station_id,
      COALESCE(station_name, '') AS station_name,
      latitude,
      longitude,
      MIN(obs_time) AS all_obs_min,
      MAX(obs_time) AS all_obs_max,
      COUNT(*) AS total_rows
    FROM water_level_observations
    WHERE latitude IS NOT NULL
      AND longitude IS NOT NULL
      AND latitude BETWEEN ? AND ?
      AND longitude BETWEEN ? AND ?
    GROUP BY source, dataset_code, station_id
    """
    params = (
        activity.representative_lat - bounding_margin_deg,
        activity.representative_lat + bounding_margin_deg,
        activity.representative_lon - bounding_margin_deg,
        activity.representative_lon + bounding_margin_deg,
    )

    rows: List[Dict[str, Any]] = []

    for row in conn.execute(sql, params):
        source = str(row[0])
        dataset_code = str(row[1])
        station_id = str(row[2])
        station_name = str(row[3])
        lat = float(row[4])
        lon = float(row[5])
        all_obs_min = parse_iso_dt(row[6])
        all_obs_max = parse_iso_dt(row[7])
        total_rows = int(row[8])

        distance_m = haversine_m(activity.representative_lat, activity.representative_lon, lat, lon)

        obs_sql = """
        SELECT
          obs_time,
          water_level_m,
          COALESCE(qc_flag, check_result, check_desc, '') AS quality_flag
        FROM water_level_observations
        WHERE source = ?
          AND dataset_code = ?
          AND station_id = ?
          AND obs_time BETWEEN ? AND ?
        ORDER BY obs_time
        """
        obs_params = (source, dataset_code, station_id, window_start.isoformat(), window_end.isoformat())
        obs_rows = list(conn.execute(obs_sql, obs_params))

        obs_times = [parse_iso_dt(r[0]) for r in obs_rows]
        obs_times_valid = [t for t in obs_times if t is not None]
        obs_min = min(obs_times_valid) if obs_times_valid else None
        obs_max = max(obs_times_valid) if obs_times_valid else None

        water_count, water_min, water_max, water_mean, water_last = value_stats([to_float(r[1]) for r in obs_rows])

        coverage_ratio = 1.0 if obs_rows else 0.0
        relation, signed_gap, abs_gap = temporal_relation_and_gap(activity, obs_min, obs_max)
        abs_gap_float = float(abs_gap) if abs_gap != "" else None

        status = source_status.get(source, {})
        source_status_ok = status.get("last_status", "").lower() == "success"
        variable_available = water_count > 0

        score = rank_score(distance_m, coverage_ratio, abs_gap_float, None, source_status_ok, variable_available)

        rows.append({
            "case_id": activity.case_id,
            "activity_id": activity.activity_id,
            "candidate_type": "water",
            "source": source,
            "dataset_code": dataset_code,
            "station_id": station_id,
            "station_name": station_name,
            "latitude": lat,
            "longitude": lon,
            "elevation_m": "",
            "route_distance_m": round(distance_m, 3),
            "activity_start_time": activity.start_time.isoformat(),
            "activity_end_time": activity.end_time.isoformat(),
            "window_tolerance_hours": tolerance_hours,
            "obs_rows_in_tolerance_window": len(obs_rows),
            "obs_time_min_in_window": obs_min.isoformat() if obs_min else "",
            "obs_time_max_in_window": obs_max.isoformat() if obs_max else "",
            "all_obs_time_min": all_obs_min.isoformat() if all_obs_min else "",
            "all_obs_time_max": all_obs_max.isoformat() if all_obs_max else "",
            "total_station_rows": total_rows,
            "activity_time_coverage_ratio": coverage_ratio,
            "temporal_relation": relation,
            "signed_temporal_gap_minutes": signed_gap,
            "absolute_temporal_gap_minutes": abs_gap,
            "elevation_delta_m": "",
            "source_last_status": status.get("last_status", ""),
            "source_last_success_at": status.get("last_success_at", ""),
            "water_level_available_count": water_count,
            "water_level_mean": water_mean,
            "variable_available": str(variable_available).lower(),
            "ranking_score": score,
            "ranking_reason": "distance+coverage+temporal_gap+source_status+variable_availability",
            "zero_fallback_detected": "false",
            "notes": "Ranking evidence only; WRA metadata lacks elevation_m in current schema.",
        })

    rows.sort(key=lambda r: (-float(r["ranking_score"]), float(r["route_distance_m"])))
    for idx, row in enumerate(rows[:top_n], start=1):
        row["candidate_rank"] = idx
    return rows[:top_n]


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_html(path: Path, weather_rows: List[Dict[str, Any]], water_rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    def table_html(rows: List[Dict[str, Any]]) -> str:
        if not rows:
            return "<p>No rows.</p>"
        headers = list(rows[0].keys())
        th = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
        body = []
        for row in rows:
            td = "".join(f"<td>{html.escape(str(row.get(h, '')))}</td>" for h in headers)
            body.append(f"<tr>{td}</tr>")
        return f"<table><thead><tr>{th}</tr></thead><tbody>{''.join(body)}</tbody></table>"

    doc = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>IB3W Station Candidate Ranking v1</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 12px; margin-bottom: 32px; }}
th, td {{ border: 1px solid #ccc; padding: 4px 6px; vertical-align: top; }}
th {{ background: #f2f2f2; position: sticky; top: 0; }}
code {{ background: #f5f5f5; padding: 2px 4px; }}
</style>
</head>
<body>
<h1>IB3W Station Candidate Ranking v1</h1>
<p>This QA report ranks Top-N weather and water station candidates. It does not create a formal joined dataset.</p>
<p>Safety rule: <code>zero_fallback_detected=false</code> for candidate rows.</p>
<h2>Weather candidates</h2>
{table_html(weather_rows)}
<h2>Water candidates</h2>
{table_html(water_rows)}
</body>
</html>
"""
    path.write_text(doc, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-config", default="configs/weather_context/ib3w_station_ranking_smoke_cases_v1.csv")
    parser.add_argument("--out-dir", default="outputs/ib3w_weather_context_station_ranking_v1")
    args = parser.parse_args()

    case_config = Path(args.case_config)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    weather_all: List[Dict[str, Any]] = []
    water_all: List[Dict[str, Any]] = []

    with case_config.open("r", encoding="utf-8-sig", newline="") as f:
        cases = list(csv.DictReader(f))

    for case in cases:
        top_n = int(case.get("top_n") or 10)
        tolerance_hours = float(case.get("tolerance_hours") or 3)
        bounding_margin_deg = float(case.get("bounding_margin_deg") or 0.35)

        activity = read_activity_window(
            input_csv=Path(case["input_csv"]),
            case_id=case["case_id"],
            route_folder=case["route_folder"],
            activity_id=case["activity_id"],
        )

        conn = sqlite3.connect(case["weather_db"])
        try:
            weather_all.extend(rank_weather_candidates(conn, activity, top_n, tolerance_hours, bounding_margin_deg))
            water_all.extend(rank_water_candidates(conn, activity, top_n, tolerance_hours, bounding_margin_deg))
        finally:
            conn.close()

    weather_csv = out_dir / "ib3w_station_candidates_weather.csv"
    water_csv = out_dir / "ib3w_station_candidates_water.csv"
    html_path = out_dir / "ib3w_station_ranking_summary.html"

    write_csv(weather_csv, weather_all)
    write_csv(water_csv, water_all)
    write_html(html_path, weather_all, water_all)

    zero_fallback_count = 0
    for row in weather_all + water_all:
        if str(row.get("zero_fallback_detected", "")).lower() == "true":
            zero_fallback_count += 1

    print("IB3W station ranking QA written")
    print(f"Weather CSV: {weather_csv}")
    print(f"Water CSV: {water_csv}")
    print(f"HTML: {html_path}")
    print(f"weather_candidates: {len(weather_all)}")
    print(f"water_candidates: {len(water_all)}")
    print(f"zero_fallback_detected_count: {zero_fallback_count}")


if __name__ == "__main__":
    main()
