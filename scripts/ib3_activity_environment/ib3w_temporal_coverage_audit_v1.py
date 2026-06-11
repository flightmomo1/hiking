#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IB3W temporal coverage audit v1.

Purpose:
- Read existing IB3W Top-N station candidate CSVs.
- Add temporal availability evidence for each candidate station.
- Clarify whether records are before activity, after activity, overlapping, or absent.
- Keep missing contextual evidence as missing; do not synthesize normal fallback.

Non-goals:
- No full pipeline.
- No production joined dataset.
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
    case_id: str
    activity_id: str
    route_folder: str
    start_time: datetime
    end_time: datetime
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


def fetch_station_obs_times(
    conn: sqlite3.Connection,
    table_name: str,
    source: str,
    dataset_code: str,
    station_id: str,
) -> List[datetime]:
    sql = f"""
    SELECT obs_time
    FROM {table_name}
    WHERE source = ?
      AND dataset_code = ?
      AND station_id = ?
    ORDER BY obs_time
    """
    times: List[datetime] = []
    for (obs_time,) in conn.execute(sql, (source, dataset_code, station_id)):
        dt = parse_iso_dt(obs_time)
        if dt is not None:
            times.append(dt)
    times.sort()
    return times


def temporal_metrics(
    activity: ActivityWindow,
    obs_times: List[datetime],
    tolerance_hours: float,
    expected_interval_minutes: float,
) -> Dict[str, Any]:
    window_start = activity.start_time - timedelta(hours=tolerance_hours)
    window_end = activity.end_time + timedelta(hours=tolerance_hours)

    station_has_any_records = len(obs_times) > 0

    in_activity = [t for t in obs_times if activity.start_time <= t <= activity.end_time]
    in_tolerance = [t for t in obs_times if window_start <= t <= window_end]

    before_activity = [t for t in obs_times if t < activity.start_time]
    after_activity = [t for t in obs_times if t > activity.end_time]

    latest_before = before_activity[-1] if before_activity else None
    earliest_after = after_activity[0] if after_activity else None

    latest_before_gap = (
        round((activity.start_time - latest_before).total_seconds() / 60.0, 3)
        if latest_before is not None
        else ""
    )
    earliest_after_gap = (
        round((earliest_after - activity.end_time).total_seconds() / 60.0, 3)
        if earliest_after is not None
        else ""
    )

    if in_activity:
        nearest_obs_time = min(in_activity, key=lambda t: abs((t - activity.start_time).total_seconds()))
        nearest_relation = "overlaps_activity"
        signed_gap = 0.0
        abs_gap = 0.0
    elif latest_before is not None and earliest_after is not None:
        before_gap = (activity.start_time - latest_before).total_seconds() / 60.0
        after_gap = (earliest_after - activity.end_time).total_seconds() / 60.0
        if abs(before_gap) <= abs(after_gap):
            nearest_obs_time = latest_before
            nearest_relation = "before_activity"
            signed_gap = round(before_gap, 3)
            abs_gap = round(abs(before_gap), 3)
        else:
            nearest_obs_time = earliest_after
            nearest_relation = "after_activity"
            signed_gap = round(-after_gap, 3)
            abs_gap = round(abs(after_gap), 3)
    elif latest_before is not None:
        before_gap = (activity.start_time - latest_before).total_seconds() / 60.0
        nearest_obs_time = latest_before
        nearest_relation = "before_activity"
        signed_gap = round(before_gap, 3)
        abs_gap = round(abs(before_gap), 3)
    elif earliest_after is not None:
        after_gap = (earliest_after - activity.end_time).total_seconds() / 60.0
        nearest_obs_time = earliest_after
        nearest_relation = "after_activity"
        signed_gap = round(-after_gap, 3)
        abs_gap = round(abs(after_gap), 3)
    else:
        nearest_obs_time = None
        nearest_relation = "no_station_records"
        signed_gap = ""
        abs_gap = ""

    tolerance_window_minutes = (window_end - window_start).total_seconds() / 60.0
    expected_points = max(1, int(math.floor(tolerance_window_minutes / expected_interval_minutes)) + 1)
    observed_points = len(in_tolerance)
    coverage_ratio_estimated = round(min(1.0, observed_points / expected_points), 6)

    if in_activity:
        temporal_relation_refined = "overlaps_activity"
    elif in_tolerance:
        temporal_relation_refined = "records_in_tolerance_only"
    elif station_has_any_records:
        temporal_relation_refined = "station_records_outside_tolerance"
    else:
        temporal_relation_refined = "no_station_records"

    return {
        "activity_start_time_refined": activity.start_time.isoformat(),
        "activity_end_time_refined": activity.end_time.isoformat(),
        "activity_duration_minutes": round((activity.end_time - activity.start_time).total_seconds() / 60.0, 3),
        "tolerance_window_start": window_start.isoformat(),
        "tolerance_window_end": window_end.isoformat(),
        "tolerance_window_minutes": round(tolerance_window_minutes, 3),
        "expected_interval_minutes": expected_interval_minutes,
        "station_has_any_records": str(station_has_any_records).lower(),
        "station_total_obs_records_recount": len(obs_times),
        "station_first_obs_time": obs_times[0].isoformat() if obs_times else "",
        "station_last_obs_time": obs_times[-1].isoformat() if obs_times else "",
        "records_in_activity_window": len(in_activity),
        "records_in_tolerance_window_recount": len(in_tolerance),
        "station_has_records_in_tolerance_window": str(len(in_tolerance) > 0).lower(),
        "coverage_expected_points": expected_points,
        "coverage_observed_points": observed_points,
        "coverage_ratio_estimated": coverage_ratio_estimated,
        "temporal_relation_refined": temporal_relation_refined,
        "nearest_obs_time": nearest_obs_time.isoformat() if nearest_obs_time else "",
        "nearest_obs_relation": nearest_relation,
        "nearest_obs_gap_minutes": signed_gap,
        "nearest_obs_gap_abs_minutes": abs_gap,
        "latest_obs_before_activity": latest_before.isoformat() if latest_before else "",
        "latest_obs_before_gap_minutes": latest_before_gap,
        "earliest_obs_after_activity": earliest_after.isoformat() if earliest_after else "",
        "earliest_obs_after_gap_minutes": earliest_after_gap,
        "zero_fallback_detected": "false",
    }


def enrich_candidates(
    conn: sqlite3.Connection,
    activity: ActivityWindow,
    candidates: List[Dict[str, str]],
    candidate_type: str,
    tolerance_hours: float,
    expected_interval_minutes: float,
) -> List[Dict[str, Any]]:
    table_name = "weather_observations" if candidate_type == "weather" else "water_level_observations"
    enriched: List[Dict[str, Any]] = []

    for row in candidates:
        source = row.get("source", "")
        dataset_code = row.get("dataset_code", "")
        station_id = row.get("station_id", "")

        obs_times = fetch_station_obs_times(
            conn=conn,
            table_name=table_name,
            source=source,
            dataset_code=dataset_code,
            station_id=station_id,
        )

        metrics = temporal_metrics(
            activity=activity,
            obs_times=obs_times,
            tolerance_hours=tolerance_hours,
            expected_interval_minutes=expected_interval_minutes,
        )

        out = dict(row)
        out.update(metrics)
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
        "candidate_rank",
        "station_id",
        "station_name",
        "route_distance_m",
        "temporal_relation",
        "temporal_relation_refined",
        "coverage_ratio_estimated",
        "records_in_tolerance_window_recount",
        "nearest_obs_relation",
        "nearest_obs_time",
        "nearest_obs_gap_abs_minutes",
        "latest_obs_before_activity",
        "latest_obs_before_gap_minutes",
        "earliest_obs_after_activity",
        "earliest_obs_after_gap_minutes",
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
<title>IB3W Temporal Coverage Audit v1</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 12px; margin-bottom: 32px; }}
th, td {{ border: 1px solid #ccc; padding: 4px 6px; vertical-align: top; }}
th {{ background: #f2f2f2; }}
code {{ background: #f5f5f5; padding: 2px 4px; }}
</style>
</head>
<body>
<h1>IB3W Temporal Coverage Audit v1</h1>
<p>This report enriches existing Top-N station candidates with refined temporal coverage evidence.</p>
<p>No formal joined dataset is created. Missing weather/water remains missing evidence.</p>
<p>Safety rule: <code>zero_fallback_detected=false</code>.</p>
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
    parser.add_argument("--case-config", default="configs/weather_context/ib3w_temporal_coverage_smoke_cases_v1.csv")
    parser.add_argument("--out-dir", default="outputs/ib3w_weather_context_temporal_coverage_v1")
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
                enrich_candidates(
                    conn=conn,
                    activity=activity,
                    candidates=weather_candidates,
                    candidate_type="weather",
                    tolerance_hours=tolerance_hours,
                    expected_interval_minutes=expected_interval_minutes,
                )
            )
            water_all.extend(
                enrich_candidates(
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

    weather_csv = out_dir / "ib3w_station_candidates_weather_temporal_coverage.csv"
    water_csv = out_dir / "ib3w_station_candidates_water_temporal_coverage.csv"
    html_path = out_dir / "ib3w_temporal_coverage_summary.html"

    write_csv(weather_csv, weather_all)
    write_csv(water_csv, water_all)
    write_html(html_path, weather_all, water_all)

    zero_fallback_count = 0
    for row in weather_all + water_all:
        if str(row.get("zero_fallback_detected", "")).lower() == "true":
            zero_fallback_count += 1

    weather_refined = {}
    for row in weather_all:
        key = str(row.get("temporal_relation_refined", ""))
        weather_refined[key] = weather_refined.get(key, 0) + 1

    water_refined = {}
    for row in water_all:
        key = str(row.get("temporal_relation_refined", ""))
        water_refined[key] = water_refined.get(key, 0) + 1

    print("IB3W temporal coverage audit written")
    print(f"Weather CSV: {weather_csv}")
    print(f"Water CSV: {water_csv}")
    print(f"HTML: {html_path}")
    print(f"weather_candidates: {len(weather_all)}")
    print(f"water_candidates: {len(water_all)}")
    print(f"weather_temporal_relation_refined: {weather_refined}")
    print(f"water_temporal_relation_refined: {water_refined}")
    print(f"zero_fallback_detected_count: {zero_fallback_count}")


if __name__ == "__main__":
    main()
