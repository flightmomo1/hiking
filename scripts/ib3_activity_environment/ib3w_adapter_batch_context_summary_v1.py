#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IB3W adapter batch context summary v1.

Purpose:
- Read one or more adapter-row activity context summary CSVs.
- Combine them into a batch-level context summary.
- Produce batch QA counts by context_status, audit_status, context_variable, and activity_id.
- Preserve no-imputation / no-zero-fallback rule.

Non-goals:
- No station ranking.
- No temporal coverage recomputation.
- No variable coverage recomputation.
- No row-level weather join.
- No IB3M behavior analysis.
- No route risk / radar / THCI adjustment.
"""

from __future__ import annotations

import argparse
import csv
import html
from pathlib import Path
from typing import Any, Dict, List


REQUIRED_CONTEXT_VARIABLES = [
    "precipitation_1hr",
    "wind_speed",
    "temperature",
    "water_level",
]


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing input CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


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


def count_by(rows: List[Dict[str, Any]], *keys: str) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for row in rows:
        label = " | ".join(str(row.get(k, "")) for k in keys)
        result[label] = result.get(label, 0) + 1
    return result


def counts_to_rows(counts: Dict[str, int], count_name: str = "count") -> List[Dict[str, Any]]:
    return [{"name": name, count_name: count} for name, count in sorted(counts.items())]


def validate_activity_context(activity_id: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    variables_present = {str(row.get("context_variable", "")) for row in rows}
    missing_required = [v for v in REQUIRED_CONTEXT_VARIABLES if v not in variables_present]

    zero_fallback_rows = [
        row for row in rows
        if str(row.get("zero_fallback_detected", "")).lower() == "true"
    ]

    observed_rows = [
        row for row in rows
        if str(row.get("context_status", "")) == "OBSERVED"
    ]

    missing_rows = [
        row for row in rows
        if str(row.get("context_status", "")) == "MISSING"
    ]

    no_source_rows = [
        row for row in rows
        if str(row.get("context_status", "")) == "NO_SOURCE"
    ]

    unknown_rows = [
        row for row in rows
        if str(row.get("context_status", "")) == "UNKNOWN"
    ]

    if zero_fallback_rows:
        batch_activity_status = "FAIL_ZERO_FALLBACK"
    elif missing_required:
        batch_activity_status = "WARN_MISSING_REQUIRED_VARIABLE"
    elif unknown_rows:
        batch_activity_status = "WARN_UNKNOWN_CONTEXT_STATUS"
    else:
        batch_activity_status = "PASS_CONTEXT_SUMMARY_READY"

    return {
        "activity_id": activity_id,
        "context_rows": len(rows),
        "required_variables_present": ",".join(sorted(variables_present)),
        "required_variables_missing": ",".join(missing_required),
        "observed_count": len(observed_rows),
        "missing_count": len(missing_rows),
        "no_source_count": len(no_source_rows),
        "unknown_count": len(unknown_rows),
        "zero_fallback_detected_count": len(zero_fallback_rows),
        "batch_activity_status": batch_activity_status,
    }


def write_html(
    path: Path,
    combined_rows: List[Dict[str, Any]],
    activity_summary_rows: List[Dict[str, Any]],
    status_rows: List[Dict[str, Any]],
    audit_rows: List[Dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    def table_html(rows: List[Dict[str, Any]], preferred_cols: List[str] | None = None) -> str:
        if not rows:
            return "<p>No rows.</p>"

        if preferred_cols:
            headers = [c for c in preferred_cols if c in rows[0]]
        else:
            headers = list(rows[0].keys())

        th = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
        body = []
        for row in rows:
            td = "".join(f"<td>{html.escape(str(row.get(h, '')))}</td>" for h in headers)
            body.append(f"<tr>{td}</tr>")
        return f"<table><thead><tr>{th}</tr></thead><tbody>{''.join(body)}</tbody></table>"

    focus_cols = [
        "batch_case_id",
        "activity_id",
        "context_variable",
        "context_status",
        "audit_status",
        "selected_station_id",
        "selected_station_name",
        "selected_candidate_rank",
        "valid_records_in_activity",
        "valid_records_in_tolerance",
        "nearest_valid_obs_relation",
        "nearest_valid_obs_time",
        "nearest_valid_obs_gap_abs_minutes",
        "observed_values_available",
        "zero_fallback_detected",
    ]

    doc = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>IB3W Adapter Batch Context Summary v1</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 12px; margin-bottom: 32px; }}
th, td {{ border: 1px solid #ccc; padding: 4px 6px; vertical-align: top; }}
th {{ background: #f2f2f2; }}
code {{ background: #f5f5f5; padding: 2px 4px; }}
</style>
</head>
<body>
<h1>IB3W Adapter Batch Context Summary v1</h1>
<p>This report combines activity-level IB3W context summaries into a batch-level QA view.</p>
<p>No row-level weather join is created. No imputation is performed.</p>
<p>Safety rule: <code>zero_fallback_detected=false</code>.</p>

<h2>Activity QA summary</h2>
{table_html(activity_summary_rows)}

<h2>Context status counts</h2>
{table_html(status_rows)}

<h2>Audit status counts</h2>
{table_html(audit_rows)}

<h2>Combined context rows</h2>
{table_html(combined_rows, focus_cols)}
</body>
</html>
"""
    path.write_text(doc, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-config", default="configs/weather_context/ib3w_adapter_batch_smoke_cases_v1.csv")
    parser.add_argument("--out-dir", default="outputs/ib3w_weather_context_adapter_batch_v1")
    args = parser.parse_args()

    case_config = Path(args.case_config)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cases = read_csv_rows(case_config)

    combined_rows: List[Dict[str, Any]] = []
    activity_groups: Dict[str, List[Dict[str, Any]]] = {}

    for case in cases:
        batch_case_id = case.get("batch_case_id", "")
        activity_id_from_case = case.get("activity_id", "")
        route_folder = case.get("route_folder", "")
        input_csv = Path(case["adapter_row_context_summary_csv"])

        context_rows = read_csv_rows(input_csv)

        for row in context_rows:
            activity_id = row.get("activity_id") or activity_id_from_case
            enriched = dict(row)
            enriched["batch_case_id"] = batch_case_id
            enriched["batch_route_folder"] = route_folder
            enriched["adapter_row_context_summary_csv"] = str(input_csv)
            enriched["batch_notes"] = case.get("notes", "")
            combined_rows.append(enriched)
            activity_groups.setdefault(activity_id, []).append(enriched)

    activity_summary_rows = [
        validate_activity_context(activity_id, rows)
        for activity_id, rows in sorted(activity_groups.items())
    ]

    status_rows = counts_to_rows(count_by(combined_rows, "context_status"), "count")
    audit_rows = counts_to_rows(count_by(combined_rows, "audit_status"), "count")
    variable_status_rows = counts_to_rows(count_by(combined_rows, "context_variable", "context_status", "audit_status"), "count")

    zero_fallback_count = sum(
        1 for row in combined_rows
        if str(row.get("zero_fallback_detected", "")).lower() == "true"
    )

    combined_csv = out_dir / "ib3w_batch_activity_context_summary_v1.csv"
    activity_summary_csv = out_dir / "ib3w_batch_activity_context_status_summary_v1.csv"
    status_counts_csv = out_dir / "ib3w_batch_context_status_counts_v1.csv"
    audit_counts_csv = out_dir / "ib3w_batch_audit_status_counts_v1.csv"
    variable_status_counts_csv = out_dir / "ib3w_batch_variable_status_counts_v1.csv"
    html_path = out_dir / "ib3w_adapter_batch_context_summary_v1.html"

    write_csv(combined_csv, combined_rows)
    write_csv(activity_summary_csv, activity_summary_rows)
    write_csv(status_counts_csv, status_rows)
    write_csv(audit_counts_csv, audit_rows)
    write_csv(variable_status_counts_csv, variable_status_rows)
    write_html(html_path, combined_rows, activity_summary_rows, status_rows, audit_rows)

    print("IB3W adapter batch context summary written")
    print(f"Combined CSV: {combined_csv}")
    print(f"Activity status CSV: {activity_summary_csv}")
    print(f"Context status counts CSV: {status_counts_csv}")
    print(f"Audit status counts CSV: {audit_counts_csv}")
    print(f"Variable status counts CSV: {variable_status_counts_csv}")
    print(f"HTML: {html_path}")
    print(f"batch_cases: {len(cases)}")
    print(f"activities: {len(activity_groups)}")
    print(f"context_rows: {len(combined_rows)}")
    print(f"context_status_counts: {count_by(combined_rows, 'context_status')}")
    print(f"audit_status_counts: {count_by(combined_rows, 'audit_status')}")
    print(f"zero_fallback_detected_count: {zero_fallback_count}")


if __name__ == "__main__":
    main()
