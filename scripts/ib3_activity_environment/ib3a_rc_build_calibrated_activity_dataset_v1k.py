#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IB3A-RC v1k minimal calibrated activity dataset.

This first version adds only a horizontal calibration contract. It preserves
every v1j and v1i source field and does not calculate calibrated speed,
distance, elevation, movement state, or facility/radar evidence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any


VERSION = "v1k_horizontal_v1"

NEW_FIELDS = [
    "raw_lat",
    "raw_lon",
    "raw_elevation_m",
    "raw_distance_m",
    "raw_gps_speed_estimated_mps",
    "raw_speed_source",
    "calibrated_lat",
    "calibrated_lon",
    "horizontal_calibration_source",
    "horizontal_calibration_method",
    "horizontal_calibration_confidence",
    "horizontal_calibration_distance_m",
    "horizontal_review_required",
    "route_class",
    "connector_flag",
    "backend_use_policy",
    "calibration_status",
    "calibration_review_required",
]

REQUIRED_V1J_FIELDS = [
    "raw_point_index",
    "activity_id",
    "timestamp_s",
    "elapsed_sec",
    "lat",
    "lon",
    "ele_m",
    "distance_m",
    "heart_rate_bpm",
    "projected_lat",
    "projected_lon",
    "candidate_confidence",
    "candidate_context",
    "training_use_policy",
    "anchor_stabilized_flag",
    "anchor_refit_lat",
    "anchor_refit_lon",
    "target_route_status",
    "off_target_flag",
    "mainline_membership",
    "wrong_route_flag",
    "display_lat",
    "display_lon",
    "display_coordinate_source",
]

FORBIDDEN_COLUMNS = {
    "calibrated_speed_mps",
    "calibrated_step_distance_m",
    "calibrated_horizontal_distance_m",
    "calibrated_elevation_m",
    "movement_state",
    "gps_drift_suspected",
    "nlsc_elevation_m",
    "calibrated_slope_pct",
    "calibrated_cumulative_gain_m",
    "calibrated_cumulative_loss_m",
}


def to_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return default
        number = float(value)
        return number if math.isfinite(number) else default
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def resolve_input(
    root: Path,
    route_folder: str,
    activity_id: str,
    expected_suffix: str,
) -> Path:
    activity_dir = root / route_folder / activity_id
    expected = activity_dir / f"{route_folder}_{activity_id}_{expected_suffix}"
    if expected.exists():
        return expected
    matches = sorted(activity_dir.glob(f"*{expected_suffix}"))
    if len(matches) == 1:
        return matches[0]
    raise FileNotFoundError(f"Unable to resolve one *{expected_suffix} in {activity_dir}")


def determine_route_class(row: dict[str, str]) -> str:
    membership = str(row.get("mainline_membership", "")).strip()
    context = str(row.get("candidate_context", "")).strip()
    target_status = str(row.get("target_route_status", "")).strip()
    non_mainline_type = str(row.get("non_mainline_type_after_v1i", "")).strip()

    if is_true(row.get("wrong_route_flag")):
        return "WRONG_ROUTE"
    if membership == "MAINLINE_SUMMIT_STAY":
        return "MAINLINE_SUMMIT_STAY"
    if membership == "CONNECTOR":
        return "CONNECTOR"
    if membership == "MAINLINE_CORE":
        return "MAINLINE_CORE"
    if is_true(row.get("off_target_flag")) or target_status.startswith("OFF_TARGET"):
        return "OFF_TARGET"
    if "BRANCH" in non_mainline_type or context == "BRANCH_OR_SIDE_TRAIL_LIKELY":
        return "NON_MAINLINE_BRANCH"
    if context == "APPROACH_OR_ROAD" or "APPROACH" in non_mainline_type:
        return "APPROACH_OR_SERVICE"
    if context == "LOW_CONFIDENCE_CANDIDATE":
        return "LOW_CONFIDENCE"
    return "UNKNOWN_REVIEW"


def horizontal_calibration(row: dict[str, str]) -> dict[str, Any]:
    raw_lat = to_float(row.get("lat"))
    raw_lon = to_float(row.get("lon"))
    projected_lat = to_float(row.get("projected_lat"))
    projected_lon = to_float(row.get("projected_lon"))
    anchor_lat = to_float(row.get("anchor_refit_lat"))
    anchor_lon = to_float(row.get("anchor_refit_lon"))

    membership = str(row.get("mainline_membership", "")).strip()
    confidence = str(row.get("candidate_confidence", "")).strip().lower()
    wrong_route = is_true(row.get("wrong_route_flag"))
    off_target = is_true(row.get("off_target_flag"))
    anchor_stabilized = is_true(row.get("anchor_stabilized_flag"))
    route_class = determine_route_class(row)

    calibrated_lat: float | None = None
    calibrated_lon: float | None = None
    source = "UNRESOLVED"
    method = "NO_VALID_COORDINATE"
    output_confidence = "unresolved"
    review_required = True
    backend_policy = "EXCLUDE_UNRESOLVED_CALIBRATION"
    calibration_status = "UNRESOLVED"

    if wrong_route and valid_latlon(projected_lat, projected_lon):
        calibrated_lat, calibrated_lon = projected_lat, projected_lon
        source = "OSM_WRONG_ROUTE_CANDIDATE_PROJECTION"
        method = "REVIEWED_ROUTE_LEVEL_WAY_RULE"
        output_confidence = "high"
        review_required = False
        backend_policy = "BEHAVIOR_ANALYTICS_ONLY_WRONG_ROUTE"
        calibration_status = "CALIBRATED_HIGH_CONFIDENCE"
    elif (
        membership == "MAINLINE_SUMMIT_STAY"
        and anchor_stabilized
        and valid_latlon(anchor_lat, anchor_lon)
    ):
        calibrated_lat, calibrated_lon = anchor_lat, anchor_lon
        source = "REVIEWED_SUMMIT_ANCHOR"
        method = "SUMMIT_ANCHOR_STABILIZATION_V1E"
        output_confidence = "high"
        review_required = False
        backend_policy = "ANALYTICS_READY"
        calibration_status = "CALIBRATED_HIGH_CONFIDENCE"
    elif (
        membership == "CONNECTOR"
        and confidence in {"high", "medium_high"}
        and valid_latlon(projected_lat, projected_lon)
    ):
        calibrated_lat, calibrated_lon = projected_lat, projected_lon
        source = "OSM_CONNECTOR_PROJECTION"
        method = "NEAREST_SELECTED_CANDIDATE_WAY"
        output_confidence = confidence
        review_required = False
        backend_policy = "ANALYTICS_READY"
        calibration_status = "CALIBRATED_HIGH_CONFIDENCE"
    elif (
        membership == "MAINLINE_CORE"
        and confidence in {"high", "medium_high"}
        and valid_latlon(projected_lat, projected_lon)
    ):
        calibrated_lat, calibrated_lon = projected_lat, projected_lon
        source = "OSM_MAINLINE_CANDIDATE_PROJECTION"
        method = "NEAREST_SELECTED_CANDIDATE_WAY"
        output_confidence = confidence
        review_required = False
        backend_policy = "ANALYTICS_READY"
        calibration_status = "CALIBRATED_HIGH_CONFIDENCE"
    elif (
        not off_target
        and membership in {"MAINLINE_CORE", "CONNECTOR"}
        and confidence == "medium"
        and valid_latlon(projected_lat, projected_lon)
    ):
        calibrated_lat, calibrated_lon = projected_lat, projected_lon
        source = "OSM_CANDIDATE_PROJECTION_REVIEW_REQUIRED"
        method = "NEAREST_CANDIDATE_WAY_MEDIUM_CONFIDENCE"
        output_confidence = "medium"
        review_required = True
        backend_policy = "ANALYTICS_READY_WITH_REVIEW_FLAGS"
        calibration_status = "CALIBRATED_WITH_REVIEW"
    elif valid_latlon(raw_lat, raw_lon):
        calibrated_lat, calibrated_lon = raw_lat, raw_lon
        source = "RAW_GPS_FALLBACK"
        method = "RAW_COORDINATE_PRESERVED"
        output_confidence = "low"
        review_required = True
        backend_policy = (
            "BEHAVIOR_ANALYTICS_ONLY_OFF_TARGET"
            if off_target
            else "EXCLUDE_LOW_CONFIDENCE_POSITION"
        )
        calibration_status = "RAW_FALLBACK_REVIEW_REQUIRED"

    distance: float | str = ""
    if valid_latlon(raw_lat, raw_lon) and valid_latlon(calibrated_lat, calibrated_lon):
        distance = round(
            haversine_m(raw_lat, raw_lon, calibrated_lat, calibrated_lon),
            3,
        )

    return {
        "calibrated_lat": "" if calibrated_lat is None else calibrated_lat,
        "calibrated_lon": "" if calibrated_lon is None else calibrated_lon,
        "horizontal_calibration_source": source,
        "horizontal_calibration_method": method,
        "horizontal_calibration_confidence": output_confidence,
        "horizontal_calibration_distance_m": distance,
        "horizontal_review_required": review_required,
        "route_class": route_class,
        "connector_flag": membership == "CONNECTOR",
        "backend_use_policy": backend_policy,
        "calibration_status": calibration_status,
        "calibration_review_required": review_required,
    }


def compare_source_rows(
    expected: list[dict[str, str]],
    actual: list[dict[str, Any]],
    fields: list[str],
) -> int:
    if len(expected) != len(actual):
        return abs(len(expected) - len(actual)) + 1
    changed = 0
    for source, derived in zip(expected, actual):
        if any(str(source.get(field, "")) != str(derived.get(field, "")) for field in fields):
            changed += 1
    return changed


def process_activity(
    route_folder: str,
    activity_id: str,
    v1j_root: Path,
    v1i_root: Path,
    out_root: Path,
) -> dict[str, Any]:
    v1j_csv = resolve_input(
        v1j_root,
        route_folder,
        activity_id,
        "display_trajectory_v1j.csv",
    )
    v1i_csv = resolve_input(
        v1i_root,
        route_folder,
        activity_id,
        "wrong_route_manual_seed_labels_v1i.csv",
    )
    v1i_hash_before = sha256_file(v1i_csv)
    v1j_hash_before = sha256_file(v1j_csv)

    v1j_rows, v1j_fields = read_csv(v1j_csv)
    v1i_rows, v1i_fields = read_csv(v1i_csv)
    missing = [field for field in REQUIRED_V1J_FIELDS if field not in v1j_fields]
    if missing:
        raise ValueError(f"Missing required v1j fields: {', '.join(missing)}")
    overlap = [field for field in NEW_FIELDS if field in v1j_fields]
    if overlap:
        raise ValueError(f"v1j input already contains v1k fields: {', '.join(overlap)}")
    if len(v1j_rows) != len(v1i_rows):
        raise ValueError(f"v1j/v1i row mismatch: {len(v1j_rows)} != {len(v1i_rows)}")

    v1i_vs_v1j_changed = compare_source_rows(v1i_rows, v1j_rows, v1i_fields)
    if v1i_vs_v1j_changed:
        raise ValueError(f"v1j differs from protected v1i fields in {v1i_vs_v1j_changed} rows")

    output_rows: list[dict[str, Any]] = []
    source_counts: Counter[str] = Counter()
    route_class_counts: Counter[str] = Counter()
    backend_policy_counts: Counter[str] = Counter()

    for row in v1j_rows:
        calibrated = horizontal_calibration(row)
        raw_speed = row.get("raw_speed_estimated_mps", "")
        additions: dict[str, Any] = {
            "raw_lat": row.get("lat", ""),
            "raw_lon": row.get("lon", ""),
            "raw_elevation_m": row.get("ele_m", ""),
            "raw_distance_m": row.get("distance_m", ""),
            "raw_gps_speed_estimated_mps": raw_speed,
            "raw_speed_source": (
                "ESTIMATED_FROM_RAW_GPS" if str(raw_speed).strip() else "UNAVAILABLE"
            ),
            **calibrated,
        }
        output = dict(row)
        output.update(additions)
        output_rows.append(output)
        source_counts[calibrated["horizontal_calibration_source"]] += 1
        route_class_counts[calibrated["route_class"]] += 1
        backend_policy_counts[calibrated["backend_use_policy"]] += 1

    protected_fields_changed = compare_source_rows(v1j_rows, output_rows, v1j_fields)
    v1i_protected_changed = compare_source_rows(v1i_rows, output_rows, v1i_fields)
    forbidden = sorted(
        field for field in (v1j_fields + NEW_FIELDS) if field in FORBIDDEN_COLUMNS
    )

    activity_dir = out_root / route_folder / activity_id
    output_csv = activity_dir / f"{route_folder}_{activity_id}_calibrated_activity_v1k.csv"
    summary_json = activity_dir / f"{route_folder}_{activity_id}_calibrated_activity_summary_v1k.json"
    provenance_json = activity_dir / f"{route_folder}_{activity_id}_calibrated_activity_provenance_v1k.json"
    write_csv(output_csv, output_rows, v1j_fields + NEW_FIELDS)

    v1i_hash_after = sha256_file(v1i_csv)
    v1j_hash_after = sha256_file(v1j_csv)
    review_required_rows = sum(
        is_true(row.get("calibration_review_required")) for row in output_rows
    )
    wrong_route_rows = sum(is_true(row.get("wrong_route_flag")) for row in output_rows)
    connector_rows = sum(row.get("route_class") == "CONNECTOR" for row in output_rows)
    raw_fallback_rows = source_counts["RAW_GPS_FALLBACK"]
    unresolved_rows = source_counts["UNRESOLVED"]
    calibrated_rows = len(output_rows) - unresolved_rows

    summary = {
        "route_folder": route_folder,
        "activity_id": activity_id,
        "calibration_version": VERSION,
        "input_v1j_csv": str(v1j_csv.resolve()),
        "input_v1i_csv": str(v1i_csv.resolve()),
        "output_csv": str(output_csv.resolve()),
        "rows": len(output_rows),
        "row_preserved": len(output_rows) == len(v1j_rows) == len(v1i_rows),
        "protected_fields_changed": protected_fields_changed + v1i_protected_changed,
        "v1i_sha256_unchanged": v1i_hash_before == v1i_hash_after,
        "v1j_sha256_unchanged": v1j_hash_before == v1j_hash_after,
        "calibrated_rows": calibrated_rows,
        "source_counts": dict(source_counts),
        "route_class_counts": dict(route_class_counts),
        "backend_use_policy_counts": dict(backend_policy_counts),
        "review_required_rows": review_required_rows,
        "wrong_route_rows": wrong_route_rows,
        "connector_rows": connector_rows,
        "raw_fallback_rows": raw_fallback_rows,
        "unresolved_rows": unresolved_rows,
        "forbidden_columns_created": forbidden,
        "runtime_llm_allowed": False,
        "note": (
            "Minimal horizontal calibration only. No calibrated speed, distance, "
            "elevation, movement-state, NLSC, facility, or radar fields are created."
        ),
    }
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    summary_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    provenance = {
        "calibration_version": VERSION,
        "route_folder": route_folder,
        "activity_id": activity_id,
        "source_files": {
            "v1j_csv": str(v1j_csv.resolve()),
            "v1i_csv": str(v1i_csv.resolve()),
        },
        "source_sha256": {
            "v1j_before": v1j_hash_before,
            "v1j_after": v1j_hash_after,
            "v1i_before": v1i_hash_before,
            "v1i_after": v1i_hash_after,
        },
        "source_rows": {
            "v1j": len(v1j_rows),
            "v1i": len(v1i_rows),
            "output": len(output_rows),
        },
        "protected_columns": {
            "v1j_columns_n": len(v1j_fields),
            "v1i_columns_n": len(v1i_fields),
            "changed_rows": protected_fields_changed + v1i_protected_changed,
        },
        "raw_alias_mapping": {
            "raw_lat": "lat",
            "raw_lon": "lon",
            "raw_elevation_m": "ele_m",
            "raw_distance_m": "distance_m",
            "raw_gps_speed_estimated_mps": "raw_speed_estimated_mps",
            "heart_rate_bpm": "heart_rate_bpm (preserved source field)",
            "timestamp_s": "timestamp_s (preserved source field)",
            "elapsed_sec": "elapsed_sec (preserved source field)",
            "raw_point_index": "raw_point_index (preserved source field)",
        },
        "output_csv": str(output_csv.resolve()),
        "runtime_llm_allowed": False,
    }
    provenance_json.write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary["summary_json"] = str(summary_json.resolve())
    summary["provenance_json"] = str(provenance_json.resolve())
    return summary


def write_batch_summary(out_root: Path, summaries: list[dict[str, Any]]) -> None:
    batch_dir = out_root / "_batch_summary"
    batch_csv = batch_dir / "ib3a_rc_calibrated_activity_v1k_case_summary.csv"
    contract_json = batch_dir / "ib3a_rc_calibrated_activity_v1k_contract_summary.json"
    fields = [
        "activity_id",
        "status",
        "rows",
        "row_preserved",
        "v1i_sha256_unchanged",
        "protected_fields_changed",
        "calibrated_rows",
        "source_counts",
        "route_class_counts",
        "backend_use_policy_counts",
        "review_required_rows",
        "wrong_route_rows",
        "connector_rows",
        "raw_fallback_rows",
        "unresolved_rows",
        "forbidden_columns_created",
        "output_csv",
        "summary_json",
        "provenance_json",
        "notes",
    ]
    rows: list[dict[str, Any]] = []
    for summary in summaries:
        row = dict(summary)
        for field in [
            "source_counts",
            "route_class_counts",
            "backend_use_policy_counts",
            "forbidden_columns_created",
        ]:
            row[field] = json.dumps(row.get(field, {}), ensure_ascii=False, sort_keys=True)
        row["notes"] = summary.get("blocking_issue") or summary.get("note", "none")
        rows.append(row)
    write_csv(batch_csv, rows, fields)

    source_totals: Counter[str] = Counter()
    route_totals: Counter[str] = Counter()
    policy_totals: Counter[str] = Counter()
    for summary in summaries:
        source_totals.update(summary.get("source_counts", {}))
        route_totals.update(summary.get("route_class_counts", {}))
        policy_totals.update(summary.get("backend_use_policy_counts", {}))
    contract = {
        "calibration_version": VERSION,
        "activities_n": len(summaries),
        "pass_n": sum(summary.get("status") == "PASS" for summary in summaries),
        "fail_n": sum(summary.get("status") == "FAIL" for summary in summaries),
        "minimal_horizontal_only": True,
        "source_totals": dict(source_totals),
        "route_class_totals": dict(route_totals),
        "backend_use_policy_totals": dict(policy_totals),
        "forbidden_columns_created_total": sum(
            len(summary.get("forbidden_columns_created", [])) for summary in summaries
        ),
        "upstream_outputs_modified": False,
        "batch_summary_csv": str(batch_csv.resolve()),
        "output_root": str(out_root.resolve()),
        "runtime_llm_allowed": False,
    }
    contract_json.parent.mkdir(parents=True, exist_ok=True)
    contract_json.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_activity_ids(args: argparse.Namespace) -> list[str]:
    values: list[str] = []
    if args.activity_id:
        values.append(args.activity_id.strip())
    if args.activity_ids:
        values.extend(value.strip() for value in args.activity_ids.split(","))
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    if not result:
        raise ValueError("Provide --activity-id or --activity-ids.")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the IB3A-RC v1k minimal horizontal calibrated activity dataset."
    )
    parser.add_argument("--route-folder", required=True)
    parser.add_argument("--activity-id", default="")
    parser.add_argument("--activity-ids", default="")
    parser.add_argument("--v1j-root", required=True)
    parser.add_argument("--v1i-root", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    summaries: list[dict[str, Any]] = []
    for activity_id in parse_activity_ids(args):
        try:
            summary = process_activity(
                args.route_folder,
                activity_id,
                Path(args.v1j_root),
                Path(args.v1i_root),
                Path(args.out_dir),
            )
            forbidden = summary.get("forbidden_columns_created", [])
            passed = (
                summary["row_preserved"]
                and summary["v1i_sha256_unchanged"]
                and summary["v1j_sha256_unchanged"]
                and summary["protected_fields_changed"] == 0
                and not forbidden
            )
            summary["status"] = "PASS" if passed else "FAIL"
            summary["blocking_issue"] = "" if passed else "contract validation failed"
        except Exception as exc:
            summary = {
                "activity_id": activity_id,
                "status": "FAIL",
                "blocking_issue": f"{type(exc).__name__}: {exc}",
            }
        summaries.append(summary)
        print(
            f"{activity_id}: {summary['status']} rows={summary.get('rows', '')} "
            f"sources={summary.get('source_counts', {})} "
            f"blocking_issue={summary.get('blocking_issue', '')}"
        )

    write_batch_summary(Path(args.out_dir), summaries)
    fail_n = sum(summary.get("status") != "PASS" for summary in summaries)
    print(
        f"v1k activities={len(summaries)} "
        f"pass={len(summaries) - fail_n} fail={fail_n}"
    )
    print(f"output_root={Path(args.out_dir).resolve()}")
    return 1 if fail_n else 0


if __name__ == "__main__":
    raise SystemExit(main())
