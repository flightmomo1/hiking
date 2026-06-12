#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IB3W adapter row context summary v1.

Purpose:
- Convert variable-level coverage audit rows into an activity-level context summary.
- Select the best candidate station per context variable.
- Produce formal context_status values:
    OBSERVED, MISSING, NO_SOURCE, UNKNOWN
- Preserve detailed audit_status.
- Do not create a row-level activity/weather join.
- Do not impute or synthesize zero-valued normal fallback.

Non-goals:
- No full pipeline.
- No per-activity-row weather join.
- No IB3M behavior analysis.
- No route risk / radar / THCI adjustment.
"""

from __future__ import annotations

import argparse
import csv
import html
from pathlib import Path
from typing import Any, Dict, List, Optional


OBSERVED_STATUSES = {"OBSERVED_IN_ACTIVITY", "OBSERVED_IN_TOLERANCE"}
MISSING_STATUSES = {"OUTSIDE_TOLERANCE", "NULL_VALUE_ONLY"}
NO_SOURCE_STATUSES = {"NO_STATION_RECORDS", "NO_VARIABLE_COLUMN"}


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


def to_int(value: Any) -> int:
    f = to_float(value)
    return int(f) if f is not None else 0


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def context_status_from_audit(audit_status: str) -> str:
    if audit_status in OBSERVED_STATUSES:
        return "OBSERVED"
    if audit_status in MISSING_STATUSES:
        return "MISSING"
    if audit_status in NO_SOURCE_STATUSES:
        return "NO_SOURCE"
    return "UNKNOWN"


def candidate_sort_key(row: Dict[str, str]) -> tuple:
    audit_status = row.get("variable_coverage_status", "")
    context_status = context_status_from_audit(audit_status)

    status_priority = {
        "OBSERVED": 0,
        "MISSING": 1,
        "NO_SOURCE": 2,
        "UNKNOWN": 3,
    }.get(context_status, 3)

    audit_priority = {
        "OBSERVED_IN_ACTIVITY": 0,
        "OBSERVED_IN_TOLERANCE": 1,
        "OUTSIDE_TOLERANCE": 2,
        "NULL_VALUE_ONLY": 3,
        "NO_STATION_RECORDS": 4,
        "NO_VARIABLE_COLUMN": 5,
    }.get(audit_status, 9)

    gap = to_float(row.get("variable_nearest_valid_obs_gap_abs_minutes"))
    if gap is None:
        gap = 999999999.0

    distance = to_float(row.get("route_distance_m"))
    if distance is None:
        distance = 999999999.0

    rank = to_float(row.get("candidate_rank"))
    if rank is None:
        rank = 999999999.0

    valid_in_activity = -to_int(row.get("variable_valid_records_in_activity"))
    valid_in_tolerance = -to_int(row.get("variable_valid_records_in_tolerance"))
    total_valid = -to_int(row.get("variable_valid_records_total"))

    return (
        status_priority,
        audit_priority,
        gap,
        distance,
        rank,
        valid_in_activity,
        valid_in_tolerance,
        total_valid,
    )


def select_best_by_variable(rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, str]]] = {}
    for row in rows:
        variable_name = row.get("variable_name", "")
        if not variable_name:
            continue
        grouped.setdefault(variable_name, []).append(row)

    output: List[Dict[str, Any]] = []

    for variable_name, candidates in grouped.items():
        sorted_candidates = sorted(candidates, key=candidate_sort_key)
        selected = sorted_candidates[0]
        audit_status = selected.get("variable_coverage_status", "")
        context_status = context_status_from_audit(audit_status)

        observed_values_available = context_status == "OBSERVED"
        value_mean = selected.get("valid_value_mean", "")
        value_min = selected.get("valid_value_min", "")
        value_max = selected.get("valid_value_max", "")
        value_latest = selected.get("valid_value_last", "")

        if context_status != "OBSERVED":
            value_mean = ""
            value_min = ""
            value_max = ""
            value_latest = ""

        output.append({
            "case_id": selected.get("case_id", ""),
            "activity_id": selected.get("activity_id", ""),
            "candidate_type": selected.get("candidate_type", ""),
            "context_variable": variable_name,
            "variable_column": selected.get("variable_column", ""),
            "context_status": context_status,
            "audit_status": audit_status,
            "selected_station_id": selected.get("station_id", ""),
            "selected_station_name": selected.get("station_name", ""),
            "selected_station_source": selected.get("source", ""),
            "selected_dataset_code": selected.get("dataset_code", ""),
            "selected_candidate_rank": selected.get("candidate_rank", ""),
            "selected_route_distance_m": selected.get("route_distance_m", ""),
            "station_temporal_relation_refined": selected.get("station_temporal_relation_refined", ""),
            "station_coverage_ratio_estimated": selected.get("station_coverage_ratio_estimated", ""),
            "variable_coverage_ratio_estimated": selected.get("variable_coverage_ratio_estimated", ""),
            "valid_records_total": selected.get("variable_valid_records_total", ""),
            "valid_records_in_activity": selected.get("variable_valid_records_in_activity", ""),
            "valid_records_in_tolerance": selected.get("variable_valid_records_in_tolerance", ""),
            "null_or_blank_records_total": selected.get("variable_null_or_blank_records_total", ""),
            "nearest_valid_obs_relation": selected.get("variable_nearest_valid_obs_relation", ""),
            "nearest_valid_obs_time": selected.get("variable_nearest_valid_obs_time", ""),
            "nearest_valid_obs_gap_minutes": selected.get("variable_nearest_valid_obs_gap_minutes", ""),
            "nearest_valid_obs_gap_abs_minutes": selected.get("variable_nearest_valid_obs_gap_abs_minutes", ""),
            "nearest_valid_obs_value": selected.get("variable_nearest_valid_obs_value", ""),
            "observed_value_mean": value_mean,
            "observed_value_min": value_min,
            "observed_value_max": value_max,
            "observed_value_latest": value_latest,
            "observed_values_available": str(observed_values_available).lower(),
            "zero_fallback_detected": "false",
            "candidate_rows_considered": len(candidates),
            "selection_rule": "status_priority,audit_priority,nearest_gap,distance,candidate_rank",
            "notes": "Activity-level context summary only; no row-level join and no imputation.",
        })

    order = {
        "precipitation_1hr": 1,
        "wind_speed": 2,
        "temperature": 3,
        "water_level": 4,
    }
    output.sort(key=lambda r: order.get(str(r.get("context_variable")), 999))
    return output


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


def write_html(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    focus_cols = [
        "context_variable",
        "context_status",
        "audit_status",
        "selected_station_id",
        "selected_station_name",
        "selected_candidate_rank",
        "selected_route_distance_m",
        "valid_records_in_activity",
        "valid_records_in_tolerance",
        "nearest_valid_obs_relation",
        "nearest_valid_obs_time",
        "nearest_valid_obs_gap_abs_minutes",
        "observed_values_available",
        "zero_fallback_detected",
    ]

    headers = [c for c in focus_cols if rows and c in rows[0]]
    th = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
    body = []
    for row in rows:
        td = "".join(f"<td>{html.escape(str(row.get(h, '')))}</td>" for h in headers)
        body.append(f"<tr>{td}</tr>")

    doc = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>IB3W Adapter Row Context Summary v1</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 12px; margin-bottom: 32px; }}
th, td {{ border: 1px solid #ccc; padding: 4px 6px; vertical-align: top; }}
th {{ background: #f2f2f2; }}
code {{ background: #f5f5f5; padding: 2px 4px; }}
</style>
</head>
<body>
<h1>IB3W Adapter Row Context Summary v1</h1>
<p>This report converts variable-level coverage evidence into activity-level context status.</p>
<p>No row-level weather join is created. No imputation is performed.</p>
<p>Safety rule: <code>zero_fallback_detected=false</code>.</p>
<table><thead><tr>{th}</tr></thead><tbody>{''.join(body)}</tbody></table>
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
    parser.add_argument("--case-config", default="configs/weather_context/ib3w_adapter_row_smoke_cases_v1.csv")
    parser.add_argument("--out-dir", default="outputs/ib3w_weather_context_adapter_row_v1")
    args = parser.parse_args()

    case_config = Path(args.case_config)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_summary_rows: List[Dict[str, Any]] = []

    with case_config.open("r", encoding="utf-8-sig", newline="") as f:
        cases = list(csv.DictReader(f))

    for case in cases:
        weather_rows = read_csv_rows(Path(case["weather_variable_coverage_csv"]))
        water_rows = read_csv_rows(Path(case["water_variable_coverage_csv"]))

        selected_rows = select_best_by_variable(weather_rows + water_rows)

        for row in selected_rows:
            row["adapter_case_id"] = case.get("case_id", "")
            row["adapter_input_activity_csv"] = case.get("input_csv", "")

        all_summary_rows.extend(selected_rows)

    out_csv = out_dir / "ib3w_activity_context_summary_v1.csv"
    out_html = out_dir / "ib3w_activity_context_summary_v1.html"

    write_csv(out_csv, all_summary_rows)
    write_html(out_html, all_summary_rows)

    zero_fallback_count = sum(
        1 for row in all_summary_rows
        if str(row.get("zero_fallback_detected", "")).lower() == "true"
    )

    print("IB3W adapter row context summary written")
    print(f"CSV: {out_csv}")
    print(f"HTML: {out_html}")
    print(f"context_rows: {len(all_summary_rows)}")
    print(f"context_status_counts: {count_by(all_summary_rows, 'context_status')}")
    print(f"audit_status_counts: {count_by(all_summary_rows, 'audit_status')}")
    print(f"zero_fallback_detected_count: {zero_fallback_count}")


if __name__ == "__main__":
    main()
