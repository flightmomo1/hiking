#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IB3A-RC v1j display trajectory selection.

This is a display-only derivative layer. It reads existing v1i labels and
selects display coordinates without modifying raw coordinates, reliability,
membership, wrong-route labels, or training policy.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any


VERSION = "v1j"
DISPLAY_FIELDS = [
    "display_lat",
    "display_lon",
    "display_coordinate_source",
    "display_refit_applied",
    "display_refit_reason",
    "display_refit_distance_m",
    "display_route_class",
    "display_review_required",
]


def to_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return default
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def is_true(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y", "t"}


def valid_latlon(lat: float | None, lon: float | None) -> bool:
    return (
        lat is not None
        and lon is not None
        and -90.0 <= lat <= 90.0
        and -180.0 <= lon <= 180.0
    )


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_m = 6_371_008.8
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return radius_m * 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


def read_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        return rows, list(reader.fieldnames or [])


def write_csv_rows(
    path: Path,
    rows: list[dict[str, Any]],
    fields: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def select_display_coordinate(row: dict[str, str]) -> dict[str, Any]:
    raw_lat = to_float(row.get("lat"))
    raw_lon = to_float(row.get("lon"))
    projected_lat = to_float(row.get("projected_lat"))
    projected_lon = to_float(row.get("projected_lon"))
    anchor_lat = to_float(row.get("anchor_refit_lat"))
    anchor_lon = to_float(row.get("anchor_refit_lon"))

    membership = str(row.get("mainline_membership", "")).strip()
    confidence = str(row.get("candidate_confidence", "")).strip().lower()
    wrong_route = is_true(row.get("wrong_route_flag"))
    anchor_stabilized = is_true(row.get("anchor_stabilized_flag"))

    display_lat = raw_lat
    display_lon = raw_lon
    source = "raw_fallback_low_confidence"
    reason = "raw fallback: projected coordinate is not eligible under the v1j display contract"
    review_required = True

    if (
        membership == "MAINLINE_SUMMIT_STAY"
        and anchor_stabilized
        and valid_latlon(anchor_lat, anchor_lon)
    ):
        display_lat = anchor_lat
        display_lon = anchor_lon
        source = "summit_anchor_refit"
        reason = "reviewed summit-stay anchor stabilization"
        review_required = False
    elif wrong_route and valid_latlon(projected_lat, projected_lon):
        display_lat = projected_lat
        display_lon = projected_lon
        source = "wrong_route_candidate_projection"
        reason = "reviewed wrong-route point retained on its candidate way; not canonical mainline"
        review_required = False
    elif (
        membership in {"MAINLINE_CORE", "CONNECTOR"}
        and confidence != "low"
        and valid_latlon(projected_lat, projected_lon)
    ):
        display_lat = projected_lat
        display_lon = projected_lon
        source = "candidate_way_projection"
        reason = f"eligible {membership.lower()} candidate projection with confidence={confidence or 'unknown'}"
        review_required = False
    elif not valid_latlon(raw_lat, raw_lon):
        display_lat = None
        display_lon = None
        source = "raw_fallback_missing_coordinate"
        reason = "no valid raw coordinate and no eligible display refit coordinate"
        review_required = True

    refit_applied = (
        source not in {"raw_fallback_low_confidence", "raw_fallback_missing_coordinate"}
        and valid_latlon(display_lat, display_lon)
    )
    distance_m: float | str = ""
    if valid_latlon(raw_lat, raw_lon) and valid_latlon(display_lat, display_lon):
        distance_m = round(haversine_m(raw_lat, raw_lon, display_lat, display_lon), 3)

    route_class = (
        "WRONG_ROUTE"
        if wrong_route
        else membership or str(row.get("candidate_context", "")).strip() or "UNCLASSIFIED"
    )

    return {
        "display_lat": "" if display_lat is None else display_lat,
        "display_lon": "" if display_lon is None else display_lon,
        "display_coordinate_source": source,
        "display_refit_applied": refit_applied,
        "display_refit_reason": reason,
        "display_refit_distance_m": distance_m,
        "display_route_class": route_class,
        "display_review_required": review_required,
    }


def make_projector(
    points: list[tuple[float, float]],
    width: int = 1200,
    height: int = 860,
    pad: int = 55,
):
    if not points:
        raise ValueError("No valid coordinates available for QA HTML.")
    min_lat = min(p[0] for p in points)
    max_lat = max(p[0] for p in points)
    min_lon = min(p[1] for p in points)
    max_lon = max(p[1] for p in points)
    if min_lat == max_lat:
        min_lat -= 0.00001
        max_lat += 0.00001
    if min_lon == max_lon:
        min_lon -= 0.00001
        max_lon += 0.00001

    def xy(lat: float, lon: float) -> tuple[float, float]:
        x = pad + (lon - min_lon) / (max_lon - min_lon) * (width - 2 * pad)
        y = height - pad - (lat - min_lat) / (max_lat - min_lat) * (height - 2 * pad)
        return x, y

    return xy, width, height


def svg_polyline(points: list[tuple[float, float]], color: str, width: float, opacity: float) -> str:
    if len(points) < 2:
        return ""
    value = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return (
        f'<polyline points="{value}" fill="none" stroke="{color}" '
        f'stroke-width="{width}" opacity="{opacity}"/>'
    )


def render_qa_html(
    path: Path,
    route_folder: str,
    activity_id: str,
    source_csv: Path,
    output_csv: Path,
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    raw_points: list[tuple[float, float]] = []
    display_points: list[tuple[float, float]] = []
    for row in rows:
        raw_lat = to_float(row.get("lat"))
        raw_lon = to_float(row.get("lon"))
        display_lat = to_float(row.get("display_lat"))
        display_lon = to_float(row.get("display_lon"))
        if valid_latlon(raw_lat, raw_lon):
            raw_points.append((raw_lat, raw_lon))
        if valid_latlon(display_lat, display_lon):
            display_points.append((display_lat, display_lon))

    projector, width, height = make_projector(raw_points + display_points)
    raw_xy = [projector(lat, lon) for lat, lon in raw_points]
    display_xy = [projector(lat, lon) for lat, lon in display_points]

    source_colors = {
        "summit_anchor_refit": "#eab308",
        "wrong_route_candidate_projection": "#dc2626",
        "candidate_way_projection": "#2563eb",
        "raw_fallback_low_confidence": "#6b7280",
        "raw_fallback_missing_coordinate": "#111827",
    }
    circles: list[str] = []
    sample_every = max(1, len(rows) // 1800)
    for index, row in enumerate(rows):
        if index % sample_every != 0 and index not in {0, len(rows) - 1}:
            continue
        lat = to_float(row.get("display_lat"))
        lon = to_float(row.get("display_lon"))
        if not valid_latlon(lat, lon):
            continue
        x, y = projector(lat, lon)
        source = str(row.get("display_coordinate_source", ""))
        color = source_colors.get(source, "#111827")
        tooltip = (
            f"activity_id={activity_id}\n"
            f"raw_point_index={row.get('raw_point_index','')}\n"
            f"elapsed_sec={row.get('elapsed_sec','')}\n"
            f"raw_latlon={row.get('lat','')}, {row.get('lon','')}\n"
            f"display_latlon={row.get('display_lat','')}, {row.get('display_lon','')}\n"
            f"display_source={source}\n"
            f"display_refit_distance_m={row.get('display_refit_distance_m','')}\n"
            f"display_route_class={row.get('display_route_class','')}\n"
            f"membership={row.get('mainline_membership','')}\n"
            f"wrong_route_flag={row.get('wrong_route_flag','')}\n"
            f"candidate_confidence={row.get('candidate_confidence','')}\n"
            f"review_required={row.get('display_review_required','')}"
        )
        circles.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.4" fill="{color}" opacity="0.72">'
            f"<title>{html.escape(tooltip)}</title></circle>"
        )

    count_rows = "".join(
        f"<tr><td>{html.escape(str(key))}</td><td>{value}</td></tr>"
        for key, value in sorted(summary["display_source_counts"].items())
    )
    content = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8"/>
<title>IB3A-RC v1j raw vs display QA - {html.escape(activity_id)}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 24px; color: #111827; }}
.box {{ border: 1px solid #d1d5db; border-radius: 8px; padding: 14px; margin: 16px 0; }}
svg {{ background: #f9fafb; border: 1px solid #d1d5db; max-width: 100%; height: auto; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
th, td {{ border: 1px solid #d1d5db; padding: 6px 8px; text-align: left; }}
th {{ background: #f3f4f6; }}
code {{ background: #f3f4f6; padding: 2px 4px; }}
.swatch {{ display:inline-block; width:22px; height:4px; margin-right:6px; vertical-align:middle; }}
</style>
</head>
<body>
<h1>IB3A-RC v1j raw vs display QA</h1>
<p><strong>{html.escape(route_folder)} / {html.escape(activity_id)}</strong></p>
<div class="box">
<h2>Contract boundary</h2>
<p>This is display trajectory selection only. It does not create the v1k calibrated dataset.</p>
<p>Raw GPS and selected display trajectory are both rendered so display refit cannot silently hide real off-target or wrong-route movement.</p>
<p>No usable, training, membership, or wrong-route field is changed.</p>
</div>
<div class="box">
<h2>Trajectory comparison</h2>
<p>
<span class="swatch" style="background:#111827"></span>raw GPS trace
&nbsp;&nbsp;
<span class="swatch" style="background:#06b6d4"></span>selected display trajectory
</p>
<p>Point colors: blue candidate projection, yellow summit anchor, red wrong-route candidate, gray raw fallback.</p>
<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">
{svg_polyline(raw_xy, "#111827", 2.0, 0.55)}
{svg_polyline(display_xy, "#06b6d4", 2.2, 0.82)}
{''.join(circles)}
</svg>
</div>
<div class="box">
<h2>Display source counts</h2>
<table><tr><th>Source</th><th>Rows</th></tr>{count_rows}</table>
</div>
<div class="box">
<h2>Summary</h2>
<table>
<tr><th>Rows</th><td>{summary['rows']}</td></tr>
<tr><th>Refit rows</th><td>{summary['display_refit_rows']}</td></tr>
<tr><th>Raw fallback rows</th><td>{summary['raw_fallback_rows']}</td></tr>
<tr><th>Review-required rows</th><td>{summary['display_review_required_rows']}</td></tr>
<tr><th>Median raw-to-display distance</th><td>{summary['display_refit_distance_median']} m</td></tr>
<tr><th>P90 raw-to-display distance</th><td>{summary['display_refit_distance_p90']} m</td></tr>
</table>
<p>Input: <code>{html.escape(str(source_csv))}</code></p>
<p>Output: <code>{html.escape(str(output_csv))}</code></p>
</div>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def percentile(values: list[float], fraction: float) -> float | str:
    if not values:
        return ""
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 3)
    weight = position - lower
    return round(ordered[lower] * (1.0 - weight) + ordered[upper] * weight, 3)


def resolve_input_csv(v1i_root: Path, route_folder: str, activity_id: str) -> Path:
    activity_dir = v1i_root / route_folder / activity_id
    expected = activity_dir / f"{route_folder}_{activity_id}_wrong_route_manual_seed_labels_v1i.csv"
    if expected.exists():
        return expected
    matches = sorted(activity_dir.glob("*wrong_route_manual_seed_labels_v1i.csv"))
    if len(matches) == 1:
        return matches[0]
    raise FileNotFoundError(f"Unable to resolve one v1i labels CSV in {activity_dir}")


def process_activity(
    v1i_root: Path,
    out_root: Path,
    route_folder: str,
    activity_id: str,
) -> dict[str, Any]:
    source_csv = resolve_input_csv(v1i_root, route_folder, activity_id)
    rows, fields = read_csv_rows(source_csv)
    missing = [
        field
        for field in [
            "lat",
            "lon",
            "projected_lat",
            "projected_lon",
            "candidate_confidence",
            "mainline_membership",
            "wrong_route_flag",
            "anchor_stabilized_flag",
            "anchor_refit_lat",
            "anchor_refit_lon",
        ]
        if field not in fields
    ]
    if missing:
        raise ValueError(f"Missing required v1i columns: {', '.join(missing)}")
    overlap = [field for field in DISPLAY_FIELDS if field in fields]
    if overlap:
        raise ValueError(f"Input already contains v1j fields: {', '.join(overlap)}")

    output_rows: list[dict[str, Any]] = []
    source_counts: Counter[str] = Counter()
    distances: list[float] = []
    for row in rows:
        display = select_display_coordinate(row)
        new_row: dict[str, Any] = dict(row)
        new_row.update(display)
        output_rows.append(new_row)
        source_counts[str(display["display_coordinate_source"])] += 1
        distance = to_float(display["display_refit_distance_m"])
        if distance is not None:
            distances.append(distance)

    activity_dir = out_root / route_folder / activity_id
    output_csv = activity_dir / f"{route_folder}_{activity_id}_display_trajectory_v1j.csv"
    summary_json = activity_dir / f"{route_folder}_{activity_id}_display_trajectory_summary_v1j.json"
    qa_html = activity_dir / f"{route_folder}_{activity_id}_raw_vs_display_trajectory_qa_v1j.html"
    write_csv_rows(output_csv, output_rows, fields + DISPLAY_FIELDS)

    refit_rows = sum(
        1 for row in output_rows if is_true(row.get("display_refit_applied"))
    )
    review_rows = sum(
        1 for row in output_rows if is_true(row.get("display_review_required"))
    )
    raw_fallback_rows = sum(
        count for source, count in source_counts.items() if source.startswith("raw_fallback")
    )
    summary: dict[str, Any] = {
        "route_folder": route_folder,
        "activity_id": activity_id,
        "display_trajectory_version": VERSION,
        "input_v1i_csv": str(source_csv.resolve()),
        "output_csv": str(output_csv.resolve()),
        "output_qa_html": str(qa_html.resolve()),
        "rows": len(rows),
        "row_order_preserved": True,
        "source_columns_preserved": True,
        "upstream_labels_modified": False,
        "v1k_calibrated_dataset_created": False,
        "display_source_counts": dict(source_counts),
        "display_refit_rows": refit_rows,
        "raw_fallback_rows": raw_fallback_rows,
        "display_review_required_rows": review_rows,
        "display_refit_distance_median": percentile(distances, 0.5),
        "display_refit_distance_p90": percentile(distances, 0.9),
        "runtime_llm_allowed": False,
        "note": (
            "Display-only derivative. Raw GPS, usable_on_route, candidate/training policy, "
            "mainline membership, wrong-route labels, and all v1d3-v1i inputs remain unchanged."
        ),
    }
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    summary_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    render_qa_html(
        qa_html,
        route_folder,
        activity_id,
        source_csv,
        output_csv,
        output_rows,
        summary,
    )
    summary["summary_json"] = str(summary_json.resolve())
    return summary


def write_batch_outputs(out_root: Path, summaries: list[dict[str, Any]]) -> None:
    batch_dir = out_root / "_batch_summary"
    batch_csv = batch_dir / "ib3a_rc_display_trajectory_v1j_case_summary.csv"
    batch_json = batch_dir / "ib3a_rc_display_trajectory_v1j_contract_summary.json"
    fields = [
        "route_folder",
        "activity_id",
        "status",
        "rows",
        "display_refit_rows",
        "raw_fallback_rows",
        "display_review_required_rows",
        "display_refit_distance_median",
        "display_refit_distance_p90",
        "display_source_counts",
        "output_csv",
        "output_qa_html",
        "summary_json",
        "blocking_issue",
    ]
    csv_rows: list[dict[str, Any]] = []
    for summary in summaries:
        csv_rows.append({
            **summary,
            "display_source_counts": json.dumps(
                summary.get("display_source_counts", {}),
                ensure_ascii=False,
                sort_keys=True,
            ),
        })
    write_csv_rows(batch_csv, csv_rows, fields)
    contract = {
        "display_trajectory_version": VERSION,
        "activities_n": len(summaries),
        "pass_n": sum(1 for s in summaries if s.get("status") == "PASS"),
        "fail_n": sum(1 for s in summaries if s.get("status") != "PASS"),
        "v1j_display_only": True,
        "v1k_calibrated_dataset_created": False,
        "raw_trace_required_in_qa": True,
        "display_trace_required_in_qa": True,
        "upstream_outputs_modified": False,
        "output_root": str(out_root.resolve()),
        "batch_summary_csv": str(batch_csv.resolve()),
        "runtime_llm_allowed": False,
    }
    batch_json.parent.mkdir(parents=True, exist_ok=True)
    batch_json.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_activity_ids(args: argparse.Namespace) -> list[str]:
    values: list[str] = []
    if args.activity_id:
        values.append(args.activity_id.strip())
    if args.activity_ids:
        values.extend(part.strip() for part in args.activity_ids.split(","))
    deduplicated: list[str] = []
    for value in values:
        if value and value not in deduplicated:
            deduplicated.append(value)
    if not deduplicated:
        raise ValueError("Provide --activity-id or --activity-ids.")
    return deduplicated


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build an isolated IB3A-RC v1j display trajectory from existing v1i labels."
    )
    parser.add_argument("--route-folder", required=True)
    parser.add_argument("--activity-id", default="")
    parser.add_argument("--activity-ids", default="")
    parser.add_argument("--v1i-root", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    activity_ids = parse_activity_ids(args)
    v1i_root = Path(args.v1i_root)
    out_root = Path(args.out_dir)
    summaries: list[dict[str, Any]] = []

    for activity_id in activity_ids:
        try:
            summary = process_activity(
                v1i_root,
                out_root,
                args.route_folder,
                activity_id,
            )
            summary["status"] = "PASS"
            summary["blocking_issue"] = ""
        except Exception as exc:
            summary = {
                "route_folder": args.route_folder,
                "activity_id": activity_id,
                "status": "FAIL",
                "blocking_issue": f"{type(exc).__name__}: {exc}",
            }
        summaries.append(summary)
        print(
            f"{activity_id}: {summary['status']} "
            f"rows={summary.get('rows', '')} "
            f"sources={summary.get('display_source_counts', {})} "
            f"blocking_issue={summary.get('blocking_issue', '')}"
        )

    write_batch_outputs(out_root, summaries)
    fail_n = sum(1 for summary in summaries if summary["status"] != "PASS")
    print(f"v1j activities={len(summaries)} pass={len(summaries)-fail_n} fail={fail_n}")
    print(f"output_root={out_root.resolve()}")
    return 1 if fail_n else 0


if __name__ == "__main__":
    raise SystemExit(main())
