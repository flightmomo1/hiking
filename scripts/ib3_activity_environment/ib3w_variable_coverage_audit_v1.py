#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IB3W variable coverage audit v1.

Purpose:
- Read existing IB3W Top-N station candidate temporal coverage CSVs.
- Audit variable-level coverage for each candidate station.
- Distinguish station-level availability from variable-level availability.
- Keep missing contextual evidence as missing; do not synthesize normal fallback.

Variables:
- weather: precipitation_1hr_mm, wind_speed_ms, temperature_c
- water: water_level_m

Non-goals:
- No production joined dataset.
- No full pipeline.
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
from typing import Any, Dict, List, Optional, Tuple


GARMIN_EPOCH = datetime(1989, 12, 31, tzinfo=timezone.utc)
UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


@dataclass
class ActivityWindow:
    case_id: str
    activity_id: str
    route_folder: str
    start_time: datetime
    end_time: datetime
    rows_read: int
    timestamp_epoch_used: str


VARIABLES = {
    "weather": [
        ("precipitation_1hr", "precipitation_1hr_mm"),
        ("wind_speed", "wind_speed_ms"),
        ("temperature", "temperature_c"),
    ],
    "water": [
        ("water_level", "water_level_m"),
    ],
}


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
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def infer_timestamp(value: float) -> Tuple[datetime, str]:
    unix_dt = UNIX_EPOCH + timedelta(seconds=value)
    garmin_dt = GARMIN_EPOCH + timedelta(seconds=value)

    if 2015 <= unix_dt.year <= 2035:
        return unix_dt, "unix"
    if 2015 <= garmin_dt.year <= 2035:
        return garmin_dt, "garmin_fit"
    return unix_dt, "unix_fallback"


def read_activity_window(input_csv: Path, case_id: str, route_folder: str, activity_id: str) -> ActivityWindow:
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    epoch_used: Optional[str] = None
    rows_read = 0

    with input_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "timestamp_s" not in reader.fieldnames:
            raise RuntimeError("Activity CSV missing timestamp_s.")

        for row in reader:
            rows_read += 1
            ts_value = to_float(row.get("timestamp_s"))
            if ts_value is None:
                continue

            ts_dt, epoch = infer_timestamp(ts_value)
            if epoch_used is None:
                epoch_used = epoch

            start = ts_dt if start is None or ts_dt < start else start
            end = ts_dt if end is None or ts_dt > end else end

    if start is None or end is None:
        raise RuntimeError("Could not infer activity time window.")

    return ActivityWindow(
        case_id=case_id,
        activity_id=activity_id,
        route_folder=route_folder,
        start_time=start,
        end_time=end,
        rows_read=rows_read,
        timestamp_epoch_used=epoch_used or "unknown",
    )


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    cols = set()
    for row in conn.execute(f"PRAGMA table_info({table_name})"):
        cols.add(str(row[1]))
    return cols


def fetch_variable_records(
    conn: sqlite3.Connection,
    table_name: str,
    source: str,
    dataset_code: str,
    station_id: str,
    variable_column: str,
) -> List[Tuple[datetime, Optional[float]]]:
    sql = f"""
    SELECT obs_time, {variable_column}
    FROM {table_name}
    WHERE source = ?
      AND dataset_code = ?
      AND station_id = ?
    ORDER BY obs_time
    """
    records: List[Tuple[datetime, Optional[float]]] = []
    for obs_time, value in conn.execute(sql, (source, dataset_code, station_id)):
        dt = parse_iso_dt(obs_time)
        if dt is None:
            continue
        records.append((dt, to_float(value)))
    records.sort(key=lambda x: x[0])
    return records


def value_stats(values: List[float]) -> Dict[str, Any]:
    if not values:
        return {
            "valid_value_min": "",
            "valid_value_max": "",
            "valid_value_mean": "",
            "valid_value_first": "",
            "valid_value_last": "",
        }
    return {
        "valid_value_min": min(values),
        "valid_value_max": max(values),
        "valid_value_mean": round(sum(values) / len(values), 6),
        "valid_value_first": values[0],
        "valid_value_last": values[-1],
    }


def variable_status_and_metrics(
    activity: ActivityWindow,
    records: List[Tuple[datetime, Optional[float]]],
    tolerance_hours: float,
    expected_interval_minutes: float,
    variable_column_exists: bool,
) -> Dict[str, Any]:
    window_start = activity.start_time - timedelta(hours=tolerance_hours)
    window_end = activity.end_time + timedelta(hours=tolerance_hours)

    if not variable_column_exists:
        return {
            "variable_coverage_status": "NO_VARIABLE_COLUMN",
            "station_total_records": "",
            "variable_valid_records_total": "",
            "variable_valid_records_in_activity": "",
            "variable_valid_records_in_tolerance": "",
            "variable_null_or_blank_records_total": "",
            "variable_coverage_expected_points": "",
            "variable_coverage_observed_points": "",
            "variable_coverage_ratio_estimated": "",
            "variable_nearest_valid_obs_time": "",
            "variable_nearest_valid_obs_relation": "no_variable_column",
            "variable_nearest_valid_obs_gap_minutes": "",
            "variable_nearest_valid_obs_gap_abs_minutes": "",
            "variable_latest_valid_before_activity": "",
            "variable_latest_valid_before_gap_minutes": "",
            "variable_earliest_valid_after_activity": "",
            "variable_earliest_valid_after_gap_minutes": "",
            "variable_first_valid_obs_time": "",
            "variable_last_valid_obs_time": "",
            "zero_fallback_detected": "false",
        }

    if not records:
        return {
            "variable_coverage_status": "NO_STATION_RECORDS",
            "station_total_records": 0,
            "variable_valid_records_total": 0,
            "variable_valid_records_in_activity": 0,
            "variable_valid_records_in_tolerance": 0,
            "variable_null_or_blank_records_total": 0,
            "variable_coverage_expected_points": "",
            "variable_coverage_observed_points": 0,
            "variable_coverage_ratio_estimated": 0.0,
            "variable_nearest_valid_obs_time": "",
            "variable_nearest_valid_obs_relation": "no_station_records",
            "variable_nearest_valid_obs_gap_minutes": "",
            "variable_nearest_valid_obs_gap_abs_minutes": "",
            "variable_latest_valid_before_activity": "",
            "variable_latest_valid_before_gap_minutes": "",
            "variable_earliest_valid_after_activity": "",
            "variable_earliest_valid_after_gap_minutes": "",
            "variable_first_valid_obs_time": "",
            "variable_last_valid_obs_time": "",
            "zero_fallback_detected": "false",
        }

    valid_records = [(t, v) for t, v in records if v is not None]
    null_records = [(t, v) for t, v in records if v is None]

    valid_in_activity = [(t, v) for t, v in valid_records if activity.start_time <= t <= activity.end_time]
    valid_in_tolerance = [(t, v) for t, v in valid_records if window_start <= t <= window_end]
    valid_before = [(t, v) for t, v in valid_records if t < activity.start_time]
    valid_after = [(t, v) for t, v in valid_records if t > activity.end_time]

    tolerance_window_minutes = (window_end - window_start).total_seconds() / 60.0
    expected_points = max(1, int(math.floor(tolerance_window_minutes / expected_interval_minutes)) + 1)
    observed_points = len(valid_in_tolerance)
    coverage_ratio = round(min(1.0, observed_points / expected_points), 6)

    if not valid_records:
        status = "NULL_VALUE_ONLY"
    elif valid_in_activity:
        status = "OBSERVED_IN_ACTIVITY"
    elif valid_in_tolerance:
        status = "OBSERVED_IN_TOLERANCE"
    else:
        status = "OUTSIDE_TOLERANCE"

    latest_before = valid_before[-1] if valid_before else None
    earliest_after = valid_after[0] if valid_after else None

    latest_before_gap = (
        round((activity.start_time - latest_before[0]).total_seconds() / 60.0, 3)
        if latest_before is not None
        else ""
    )
    earliest_after_gap = (
        round((earliest_after[0] - activity.end_time).total_seconds() / 60.0, 3)
        if earliest_after is not None
        else ""
    )

    if valid_in_activity:
        nearest_time, nearest_value = min(
            valid_in_activity,
            key=lambda x: abs((x[0] - activity.start_time).total_seconds()),
        )
        nearest_relation = "in_activity"
        signed_gap = 0.0
        abs_gap = 0.0
    elif latest_before is not None and earliest_after is not None:
        before_gap = (activity.start_time - latest_before[0]).total_seconds() / 60.0
        after_gap = (earliest_after[0] - activity.end_time).total_seconds() / 60.0
        if abs(before_gap) <= abs(after_gap):
            nearest_time, nearest_value = latest_before
            nearest_relation = "before_activity"
            signed_gap = round(before_gap, 3)
            abs_gap = round(abs(before_gap), 3)
        else:
            nearest_time, nearest_value = earliest_after
            nearest_relation = "after_activity"
            signed_gap = round(-after_gap, 3)
            abs_gap = round(abs(after_gap), 3)
    elif latest_before is not None:
        before_gap = (activity.start_time - latest_before[0]).total_seconds() / 60.0
        nearest_time, nearest_value = latest_before
        nearest_relation = "before_activity"
        signed_gap = round(before_gap, 3)
        abs_gap = round(abs(before_gap), 3)
    elif earliest_after is not None:
        after_gap = (earliest_after[0] - activity.end_time).total_seconds() / 60.0
        nearest_time, nearest_value = earliest_after
        nearest_relation = "after_activity"
        signed_gap = round(-after_gap, 3)
        abs_gap = round(abs(after_gap), 3)
    else:
        nearest_time = None
        nearest_value = None
        nearest_relation = "no_valid_variable_records"
        signed_gap = ""
        abs_gap = ""

    valid_values = [v for _, v in valid_records if v is not None]
    stats = value_stats(valid_values)

    return {
        "variable_coverage_status": status,
        "station_total_records": len(records),
        "variable_valid_records_total": len(valid_records),
        "variable_valid_records_in_activity": len(valid_in_activity),
        "variable_valid_records_in_tolerance": len(valid_in_tolerance),
        "variable_null_or_blank_records_total": len(null_records),
        "variable_coverage_expected_points": expected_points,
        "variable_coverage_observed_points": observed_points,
        "variable_coverage_ratio_estimated": coverage_ratio,
        "variable_nearest_valid_obs_time": nearest_time.isoformat() if nearest_time else "",
        "variable_nearest_valid_obs_relation": nearest_relation,
        "variable_nearest_valid_obs_gap_minutes": signed_gap,
        "variable_nearest_valid_obs_gap_abs_minutes": abs_gap,
        "variable_nearest_valid_obs_value": nearest_value if nearest_value is not None else "",
        "variable_latest_valid_before_activity": latest_before[0].isoformat() if latest_before else "",
        "variable_latest_valid_before_gap_minutes": latest_before_gap,
        "variable_latest_valid_before_value": latest_before[1] if latest_before else "",
        "variable_earliest_valid_after_activity": earliest_after[0].isoformat() if earliest_after else "",
        "variable_earliest_valid_after_gap_minutes": earliest_after_gap,
        "variable_earliest_valid_after_value": earliest_after[1] if earliest_after else "",
        "variable_first_valid_obs_time": valid_records[0][0].isoformat() if valid_records else "",
        "variable_last_valid_obs_time": valid_records[-1][0].isoformat() if valid_records else "",
        "zero_fallback_detected": "false",
        **stats,
    }


def enrich_variable_coverage(
    conn: sqlite3.Connection,
    activity: ActivityWindow,
    candidates: List[Dict[str, str]],
    candidate_type: str,
    tolerance_hours: float,
    expected_interval_minutes: float,
) -> List[Dict[str, Any]]:
    table_name = "weather_observations" if candidate_type == "weather" else "water_level_observations"
    cols = table_columns(conn, table_name)
    enriched: List[Dict[str, Any]] = []

    for candidate in candidates:
        source = candidate.get("source", "")
        dataset_code = candidate.get("dataset_code", "")
        station_id = candidate.get("station_id", "")

        for variable_name, variable_column in VARIABLES[candidate_type]:
            exists = variable_column in cols
            records = []
            if exists:
                records = fetch_variable_records(
                    conn=conn,
                    table_name=table_name,
                    source=source,
                    dataset_code=dataset_code,
                    station_id=station_id,
                    variable_column=variable_column,
                )

            metrics = variable_status_and_metrics(
                activity=activity,
                records=records,
                tolerance_hours=tolerance_hours,
                expected_interval_minutes=expected_interval_minutes,
                variable_column_exists=exists,
            )

            out = {
                "case_id": activity.case_id,
                "activity_id": activity.activity_id,
                "candidate_type": candidate_type,
                "candidate_rank": candidate.get("candidate_rank", ""),
                "station_id": station_id,
                "station_name": candidate.get("station_name", ""),
                "source": source,
                "dataset_code": dataset_code,
                "route_distance_m": candidate.get("route_distance_m", ""),
                "station_temporal_relation_refined": candidate.get("temporal_relation_refined", ""),
                "station_coverage_ratio_estimated": candidate.get("coverage_ratio_estimated", ""),
                "variable_name": variable_name,
                "variable_column": variable_column,
                "variable_column_exists": str(exists).lower(),
                "activity_start_time": activity.start_time.isoformat(),
                "activity_end_time": activity.end_time.isoformat(),
                "tolerance_hours": tolerance_hours,
                "expected_interval_minutes": expected_interval_minutes,
            }
            out.update(metrics)
            out["notes"] = "Variable-level coverage audit only; no formal IB3W joined dataset."
            enriched.append(out)

    return enriched


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return

    fieldnames: List[str] = []
    seen = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_html(path: Path, weather_rows: List[Dict[str, Any]], water_rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    focus_cols = [
        "candidate_type",
        "candidate_rank",
        "station_id",
        "station_name",
        "variable_name",
        "variable_coverage_status",
        "variable_valid_records_in_activity",
        "variable_valid_records_in_tolerance",
        "variable_coverage_ratio_estimated",
        "variable_nearest_valid_obs_relation",
        "variable_nearest_valid_obs_time",
        "variable_nearest_valid_obs_gap_abs_minutes",
        "variable_nearest_valid_obs_value",
        "zero_fallback_detected",
    ]

    def table_html(rows: List[Dict[str, Any]]) -> str:
        if not rows:
            return "<p>No rows.</p>"
        headers = [c for c in focus_cols if c in rows[0]]
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
<title>IB3W Variable Coverage Audit v1</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 12px; margin-bottom: 32px; }}
th, td {{ border: 1px solid #ccc; padding: 4px 6px; vertical-align: top; }}
th {{ background: #f2f2f2; }}
code {{ background: #f5f5f5; padding: 2px 4px; }}
</style>
</head>
<body>
<h1>IB3W Variable Coverage Audit v1</h1>
<p>This report audits variable-level coverage for existing Top-N station candidates.</p>
<p>No formal joined dataset is created. Missing weather/water remains missing evidence.</p>
<p>Safety rule: <code>zero_fallback_detected=false</code>.</p>
<h2>Weather variables</h2>
{table_html(weather_rows)}
<h2>Water variables</h2>
{table_html(water_rows)}
</body>
</html>
"""
    path.write_text(doc, encoding="utf-8")


def count_by(rows: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for row in rows:
        value = str(row.get(key, ""))
        result[value] = result.get(value, 0) + 1
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-config", default="configs/weather_context/ib3w_variable_coverage_smoke_cases_v1.csv")
    parser.add_argument("--out-dir", default="outputs/ib3w_weather_context_variable_coverage_v1")
    args = parser.parse_args()

    case_config = Path(args.case_config)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    weather_all: List[Dict[str, Any]] = []
    water_all: List[Dict[str, Any]] = []

    with case_config.open("r", encoding="utf-8-sig", newline="") as f:
        cases = list(csv.DictReader(f))

    for case in cases:
        activity = read_activity_window(
            input_csv=Path(case["input_csv"]),
            case_id=case["case_id"],
            route_folder=case["route_folder"],
            activity_id=case["activity_id"],
        )

        tolerance_hours = float(case.get("tolerance_hours") or 3)
        expected_interval_minutes = float(case.get("expected_interval_minutes") or 10)

        weather_candidates = read_csv_rows(Path(case["weather_candidates_csv"]))
        water_candidates = read_csv_rows(Path(case["water_candidates_csv"]))

        conn = sqlite3.connect(case["weather_db"])
        try:
            weather_all.extend(
                enrich_variable_coverage(
                    conn=conn,
                    activity=activity,
                    candidates=weather_candidates,
                    candidate_type="weather",
                    tolerance_hours=tolerance_hours,
                    expected_interval_minutes=expected_interval_minutes,
                )
            )
            water_all.extend(
                enrich_variable_coverage(
                    conn=conn,
                    activity=activity,
                    candidates=water_candidates,
                    candidate_type="water",
                    tolerance_hours=tolerance_hours,
                    expected_interval_minutes=expected_interval_minutes,
                )
            )
        finally:
            conn.close()

    weather_csv = out_dir / "ib3w_weather_variable_coverage.csv"
    water_csv = out_dir / "ib3w_water_variable_coverage.csv"
    html_path = out_dir / "ib3w_variable_coverage_summary.html"

    write_csv(weather_csv, weather_all)
    write_csv(water_csv, water_all)
    write_html(html_path, weather_all, water_all)

    zero_fallback_count = sum(
        1 for row in weather_all + water_all
        if str(row.get("zero_fallback_detected", "")).lower() == "true"
    )

    print("IB3W variable coverage audit written")
    print(f"Weather CSV: {weather_csv}")
    print(f"Water CSV: {water_csv}")
    print(f"HTML: {html_path}")
    print(f"weather_variable_rows: {len(weather_all)}")
    print(f"water_variable_rows: {len(water_all)}")
    print(f"weather_status_counts: {count_by(weather_all, 'variable_coverage_status')}")
    print(f"water_status_counts: {count_by(water_all, 'variable_coverage_status')}")
    print(f"zero_fallback_detected_count: {zero_fallback_count}")


if __name__ == "__main__":
    main()
