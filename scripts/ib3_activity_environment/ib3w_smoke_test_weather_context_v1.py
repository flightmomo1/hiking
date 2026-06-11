#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IB3W weather context smoke test v1.

Purpose:
- Read one small v1l2 activity CSV.
- Infer activity time window from timestamp_s.
- Find nearest weather / water candidate stations.
- Check whether trusted observations exist in the activity window.
- Emit MISSING / NO_SOURCE / OBSERVED without zero-valued normal fallback.

Non-goals:
- No full pipeline.
- No formal IB3W joined dataset.
- No IB3M behavior analysis.
- No route risk / radar / THCI adjustment.
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
    activity_id: str
    route_folder: str
    case_id: str
    start_time: datetime
    end_time: datetime
    representative_lat: float
    representative_lon: float
    representative_ele_m: Optional[float]
    rows_read: int
    timestamp_epoch_used: str


@dataclass
class StationCandidate:
    source: str
    dataset_code: str
    station_id: str
    station_name: str
    latitude: float
    longitude: float
    elevation_m: Optional[float]
    latest_obs_time: Optional[datetime]
    route_distance_m: float
    table_name: str


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
    """Infer whether timestamp_s is Unix epoch or Garmin/FIT epoch.

    Many FIT-derived datasets use Garmin epoch seconds since 1989-12-31.
    If Unix conversion produces an implausibly old activity but Garmin looks plausible,
    use Garmin epoch.
    """
    unix_dt = UNIX_EPOCH + timedelta(seconds=value)
    garmin_dt = GARMIN_EPOCH + timedelta(seconds=value)

    if 2015 <= unix_dt.year <= 2035:
        return unix_dt, "unix"
    if 2015 <= garmin_dt.year <= 2035:
        return garmin_dt, "garmin_fit"
    return unix_dt, "unix_fallback"


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


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * r * math.asin(math.sqrt(a))


def pick_first_float(row: Dict[str, str], names: Iterable[str]) -> Optional[float]:
    for name in names:
        if name in row:
            value = to_float(row.get(name))
            if value is not None:
                return value
    return None


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
        required = {"timestamp_s"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise RuntimeError(f"Activity CSV missing required fields: {sorted(missing)}")

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
        raise RuntimeError("Could not infer activity time window from timestamp_s.")
    if not lat_values or not lon_values:
        raise RuntimeError("Could not infer representative activity location.")

    return ActivityWindow(
        activity_id=activity_id,
        route_folder=route_folder,
        case_id=case_id,
        start_time=start,
        end_time=end,
        representative_lat=sum(lat_values) / len(lat_values),
        representative_lon=sum(lon_values) / len(lon_values),
        representative_ele_m=(sum(ele_values) / len(ele_values) if ele_values else None),
        rows_read=rows_read,
        timestamp_epoch_used=epoch_used or "unknown",
    )


def nearest_weather_station(conn: sqlite3.Connection, lat: float, lon: float) -> Optional[StationCandidate]:
    sql = """
    SELECT
      source,
      dataset_code,
      station_id,
      COALESCE(station_name, '') AS station_name,
      latitude,
      longitude,
      elevation_m,
      MAX(obs_time) AS latest_obs_time
    FROM weather_observations
    WHERE latitude IS NOT NULL
      AND longitude IS NOT NULL
    GROUP BY source, dataset_code, station_id
    """
    best: Optional[StationCandidate] = None
    for row in conn.execute(sql):
        obs_time = parse_iso_dt(row[7])
        dist = haversine_m(lat, lon, float(row[4]), float(row[5]))
        cand = StationCandidate(
            source=str(row[0]),
            dataset_code=str(row[1]),
            station_id=str(row[2]),
            station_name=str(row[3]),
            latitude=float(row[4]),
            longitude=float(row[5]),
            elevation_m=(float(row[6]) if row[6] is not None else None),
            latest_obs_time=obs_time,
            route_distance_m=dist,
            table_name="weather_observations",
        )
        if best is None or cand.route_distance_m < best.route_distance_m:
            best = cand
    return best


def nearest_water_station(conn: sqlite3.Connection, lat: float, lon: float) -> Optional[StationCandidate]:
    sql = """
    SELECT
      source,
      dataset_code,
      station_id,
      COALESCE(station_name, '') AS station_name,
      latitude,
      longitude,
      NULL AS elevation_m,
      MAX(obs_time) AS latest_obs_time
    FROM water_level_observations
    WHERE latitude IS NOT NULL
      AND longitude IS NOT NULL
    GROUP BY source, dataset_code, station_id
    """
    best: Optional[StationCandidate] = None
    for row in conn.execute(sql):
        obs_time = parse_iso_dt(row[7])
        dist = haversine_m(lat, lon, float(row[4]), float(row[5]))
        cand = StationCandidate(
            source=str(row[0]),
            dataset_code=str(row[1]),
            station_id=str(row[2]),
            station_name=str(row[3]),
            latitude=float(row[4]),
            longitude=float(row[5]),
            elevation_m=None,
            latest_obs_time=obs_time,
            route_distance_m=dist,
            table_name="water_level_observations",
        )
        if best is None or cand.route_distance_m < best.route_distance_m:
            best = cand
    return best


def fetch_records_for_station(
    conn: sqlite3.Connection,
    table_name: str,
    station_id: str,
    variable_column: str,
) -> List[Tuple[datetime, Optional[float], Optional[str]]]:
    qc_col = "qc_flag"
    if table_name == "water_level_observations":
        qc_expr = "COALESCE(qc_flag, check_result, check_desc, '')"
    else:
        qc_expr = "COALESCE(qc_flag, '')"

    sql = f"""
    SELECT obs_time, {variable_column}, {qc_expr} AS quality_flag
    FROM {table_name}
    WHERE station_id = ?
    ORDER BY obs_time
    """
    records: List[Tuple[datetime, Optional[float], Optional[str]]] = []
    for obs_time_raw, value_raw, qc_raw in conn.execute(sql, (station_id,)):
        obs_dt = parse_iso_dt(obs_time_raw)
        if obs_dt is None:
            continue
        value = to_float(value_raw)
        records.append((obs_dt, value, str(qc_raw) if qc_raw is not None else ""))
    return records


def summarize_variable(
    conn: sqlite3.Connection,
    activity: ActivityWindow,
    candidate: Optional[StationCandidate],
    context_variable: str,
    variable_column: str,
    unit: str,
    tolerance_hours: float,
) -> Dict[str, Any]:
    if candidate is None:
        return {
            "case_id": activity.case_id,
            "activity_id": activity.activity_id,
            "route_folder": activity.route_folder,
            "context_variable": context_variable,
            "context_status": "NO_SOURCE",
            "source": "",
            "dataset_code": "",
            "station_id": "",
            "station_name": "",
            "obs_rows": 0,
            "activity_time_start": activity.start_time.isoformat(),
            "activity_time_end": activity.end_time.isoformat(),
            "obs_time_min": "",
            "obs_time_max": "",
            "coverage_ratio": "",
            "recency_minutes": "",
            "route_distance_m": "",
            "elevation_delta_m": "",
            "value_min": "",
            "value_max": "",
            "value_mean": "",
            "value_last": "",
            "unit": unit,
            "quality_flag": "NO_SOURCE",
            "zero_fallback_detected": "false",
            "timestamp_epoch_used": activity.timestamp_epoch_used,
            "notes": "No candidate station found; no zero fallback applied.",
        }

    tolerance = timedelta(hours=tolerance_hours)
    window_start = activity.start_time - tolerance
    window_end = activity.end_time + tolerance

    records = fetch_records_for_station(conn, candidate.table_name, candidate.station_id, variable_column)
    records_in_window = [
        (obs_dt, value, qc)
        for obs_dt, value, qc in records
        if window_start <= obs_dt.astimezone(timezone.utc) <= window_end
    ]
    valid_values = [(obs_dt, value, qc) for obs_dt, value, qc in records_in_window if value is not None]

    status = "MISSING"
    notes = "Candidate station exists, but no non-null trusted observed value was found in activity tolerance window; no zero fallback applied."
    quality_flag = "MISSING_OBSERVED_VALUE"

    values = [v for _, v, _ in valid_values]
    obs_rows = len(records_in_window)

    if values:
        status = "OBSERVED"
        notes = "Observed values found in activity tolerance window."
        quality_flag = ";".join(sorted(set(qc for _, _, qc in valid_values if qc))) or "OBSERVED"

    obs_time_min = min((dt for dt, _, _ in records_in_window), default=None)
    obs_time_max = max((dt for dt, _, _ in records_in_window), default=None)

    latest_obs_time = obs_time_max or candidate.latest_obs_time
    recency_minutes = ""
    if latest_obs_time is not None:
        recency_minutes = round((activity.start_time - latest_obs_time.astimezone(timezone.utc)).total_seconds() / 60.0, 3)

    elevation_delta_m = ""
    if candidate.elevation_m is not None and activity.representative_ele_m is not None:
        elevation_delta_m = round(abs(candidate.elevation_m - activity.representative_ele_m), 3)

    return {
        "case_id": activity.case_id,
        "activity_id": activity.activity_id,
        "route_folder": activity.route_folder,
        "context_variable": context_variable,
        "context_status": status,
        "source": candidate.source,
        "dataset_code": candidate.dataset_code,
        "station_id": candidate.station_id,
        "station_name": candidate.station_name,
        "obs_rows": obs_rows,
        "activity_time_start": activity.start_time.isoformat(),
        "activity_time_end": activity.end_time.isoformat(),
        "obs_time_min": obs_time_min.isoformat() if obs_time_min else "",
        "obs_time_max": obs_time_max.isoformat() if obs_time_max else "",
        "coverage_ratio": 1.0 if values else 0.0,
        "recency_minutes": recency_minutes,
        "route_distance_m": round(candidate.route_distance_m, 3),
        "elevation_delta_m": elevation_delta_m,
        "value_min": min(values) if values else "",
        "value_max": max(values) if values else "",
        "value_mean": round(sum(values) / len(values), 6) if values else "",
        "value_last": values[-1] if values else "",
        "unit": unit,
        "quality_flag": quality_flag,
        "zero_fallback_detected": "false",
        "timestamp_epoch_used": activity.timestamp_epoch_used,
        "notes": notes,
    }


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        raise RuntimeError("No rows to write.")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_html(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = list(rows[0].keys()) if rows else []
    th = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body_rows = []
    for row in rows:
        tds = "".join(f"<td>{html.escape(str(row.get(h, '')))}</td>" for h in headers)
        body_rows.append(f"<tr>{tds}</tr>")

    doc = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>IB3W Weather Context Smoke Test v1</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
th, td {{ border: 1px solid #ccc; padding: 4px 6px; vertical-align: top; }}
th {{ background: #f2f2f2; position: sticky; top: 0; }}
code {{ background: #f5f5f5; padding: 2px 4px; }}
</style>
</head>
<body>
<h1>IB3W Weather Context Smoke Test v1</h1>
<p>Purpose: verify context status assignment and no-zero-fallback behavior for a single activity window.</p>
<p>Expected safety rule: <code>zero_fallback_detected=false</code> for all rows.</p>
<table>
<thead><tr>{th}</tr></thead>
<tbody>
{''.join(body_rows)}
</tbody>
</table>
</body>
</html>
"""
    path.write_text(doc, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--case-config",
        default="configs/weather_context/ib3w_smoke_test_cases_v1.csv",
    )
    parser.add_argument(
        "--out-dir",
        default="outputs/ib3w_weather_context_smoke_test_v1",
    )
    args = parser.parse_args()

    case_config = Path(args.case_config)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_rows: List[Dict[str, Any]] = []

    with case_config.open("r", encoding="utf-8-sig", newline="") as f:
        cases = list(csv.DictReader(f))

    for case in cases:
        input_csv = Path(case["input_csv"])
        weather_db = case["weather_db"]
        tolerance_hours = float(case.get("tolerance_hours") or 3)

        activity = read_activity_window(
            input_csv=input_csv,
            case_id=case["case_id"],
            route_folder=case["route_folder"],
            activity_id=case["activity_id"],
        )

        conn = sqlite3.connect(weather_db)
        try:
            weather_station = nearest_weather_station(
                conn,
                activity.representative_lat,
                activity.representative_lon,
            )
            water_station = nearest_water_station(
                conn,
                activity.representative_lat,
                activity.representative_lon,
            )

            all_rows.append(
                summarize_variable(
                    conn,
                    activity,
                    weather_station,
                    "precipitation_1hr",
                    "precipitation_1hr_mm",
                    "mm",
                    tolerance_hours,
                )
            )
            all_rows.append(
                summarize_variable(
                    conn,
                    activity,
                    weather_station,
                    "wind_speed",
                    "wind_speed_ms",
                    "m/s",
                    tolerance_hours,
                )
            )
            all_rows.append(
                summarize_variable(
                    conn,
                    activity,
                    weather_station,
                    "temperature",
                    "temperature_c",
                    "degC",
                    tolerance_hours,
                )
            )
            all_rows.append(
                summarize_variable(
                    conn,
                    activity,
                    water_station,
                    "water_level",
                    "water_level_m",
                    "m",
                    tolerance_hours,
                )
            )
        finally:
            conn.close()

    summary_csv = out_dir / "ib3w_smoke_test_context_summary.csv"
    summary_html = out_dir / "ib3w_smoke_test_context_summary.html"

    write_csv(summary_csv, all_rows)
    write_html(summary_html, all_rows)

    zero_fallback_count = sum(1 for row in all_rows if str(row.get("zero_fallback_detected")).lower() == "true")

    print("IB3W smoke test written")
    print(f"CSV: {summary_csv}")
    print(f"HTML: {summary_html}")
    print(f"rows: {len(all_rows)}")
    print(f"zero_fallback_detected_count: {zero_fallback_count}")


if __name__ == "__main__":
    main()
