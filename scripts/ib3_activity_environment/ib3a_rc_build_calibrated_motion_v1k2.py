#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Build the IB3A-RC v1k2 calibrated motion layer.

This layer derives horizontal step distance, speed, and conservative movement
states from immutable v1k calibrated positions. It does not modify upstream
coordinates, labels, route classes, policies, heart rate, or raw activity data.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


VERSION = "v1k2_calibrated_motion_v1"
MAX_VALID_SPEED_MPS = 5.0
DISTANCE_JUMP_M = 20.0
STOP_SPEED_MPS = 0.10
SLOW_SPEED_MPS = 0.35
STOP_MIN_DURATION_SEC = 15.0
LONG_INTERVAL_SEC = 30.0

NEW_FIELDS = [
    "timestamp_group_id",
    "timestamp_group_size",
    "motion_representative_flag",
    "duplicate_timestamp_policy",
    "duplicate_group_route_mixed_flag",
    "duplicate_group_source_mixed_flag",
    "duplicate_group_membership_mixed_flag",
    "duplicate_group_wrong_route_mixed_flag",
    "duplicate_group_review_required",
    "duplicate_group_motion_role",
    "calibrated_step_distance_m",
    "calibrated_horizontal_distance_m",
    "calibrated_speed_mps",
    "calibrated_speed_source",
    "calibrated_motion_source",
    "movement_state",
    "movement_confidence",
    "movement_review_required_v1k2",
    "gps_drift_suspected",
    "gps_drift_reason",
    "low_speed_uncertain",
    "time_interval_valid",
    "speed_review_required",
    "distance_review_required",
]

REQUIRED_FIELDS = [
    "raw_point_index",
    "activity_id",
    "timestamp_s",
    "elapsed_sec",
    "dt_sec",
    "duplicate_timestamp_flag",
    "heart_rate_bpm",
    "raw_distance_m",
    "raw_gps_speed_estimated_mps",
    "raw_step_m",
    "calibrated_lat",
    "calibrated_lon",
    "horizontal_calibration_source",
    "horizontal_calibration_confidence",
    "horizontal_review_required",
    "route_class",
    "backend_use_policy",
    "pause_or_stall_flag",
    "route_dist_reversal_flag",
    "route_dist_jump_flag",
    "candidate_way_switch_flag",
    "movement_review_required",
    "nearest_candidate_way_id",
    "wrong_route_flag",
    "off_target_flag",
    "mainline_membership",
    "candidate_context",
    "training_use_policy",
]

FORBIDDEN_COLUMNS = {
    "calibrated_elevation_m",
    "nlsc_elevation_m",
    "calibrated_slope_pct",
    "calibrated_cumulative_gain_m",
    "calibrated_cumulative_loss_m",
    "facility_interaction_type",
    "facility_proximity_m",
    "radar_evidence",
    "thci_score",
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
    a = (
        math.sin(dp / 2.0) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    )
    return radius_m * 2.0 * math.atan2(
        math.sqrt(a), math.sqrt(max(0.0, 1.0 - a))
    )


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


def resolve_input(root: Path, route_folder: str, activity_id: str) -> Path:
    activity_dir = root / route_folder / activity_id
    expected = activity_dir / f"{route_folder}_{activity_id}_calibrated_activity_v1k.csv"
    if expected.exists():
        return expected
    matches = sorted(activity_dir.glob("*_calibrated_activity_v1k.csv"))
    if len(matches) == 1:
        return matches[0]
    raise FileNotFoundError(f"Unable to resolve one v1k CSV in {activity_dir}")


def compare_source_rows(
    source_rows: list[dict[str, Any]],
    output_rows: list[dict[str, Any]],
    protected_fields: list[str],
) -> int:
    if len(source_rows) != len(output_rows):
        return abs(len(source_rows) - len(output_rows)) + 1
    return sum(
        any(str(source.get(field, "")) != str(output.get(field, "")) for field in protected_fields)
        for source, output in zip(source_rows, output_rows)
    )


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = fraction * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def as_output_number(value: float | None) -> str | float:
    return "" if value is None else value


def sort_key_raw_point(row: dict[str, str]) -> tuple[float, str]:
    value = to_float(row.get("raw_point_index"))
    return (value if value is not None else float("inf"), str(row.get("raw_point_index", "")))


def build_timestamp_group_metadata(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    groups: dict[str, list[int]] = defaultdict(list)
    key_order: list[str] = []
    for index, row in enumerate(rows):
        timestamp = str(row.get("timestamp_s", "")).strip()
        key = timestamp if timestamp else f"__missing_timestamp_{index}"
        if key not in groups:
            key_order.append(key)
        groups[key].append(index)

    metadata: list[dict[str, Any]] = [{} for _ in rows]
    for group_number, key in enumerate(key_order, start=1):
        indices = groups[key]
        group_rows = [rows[index] for index in indices]
        group_id = f"tsg_{group_number:06d}"
        representative_index = min(indices, key=lambda index: sort_key_raw_point(rows[index]))
        route_mixed = len({str(row.get("route_class", "")) for row in group_rows}) > 1
        source_mixed = (
            len({str(row.get("horizontal_calibration_source", "")) for row in group_rows}) > 1
        )
        membership_mixed = (
            len({str(row.get("mainline_membership", "")) for row in group_rows}) > 1
        )
        wrong_route_mixed = len({is_true(row.get("wrong_route_flag")) for row in group_rows}) > 1
        any_mixed = route_mixed or source_mixed or membership_mixed or wrong_route_mixed
        policy = (
            "single_timestamp_row"
            if len(indices) == 1
            else "representative_per_timestamp_group_raw_point_index_min"
        )
        for index in indices:
            if len(indices) == 1:
                role = "single_timestamp_row"
                representative = True
            elif wrong_route_mixed:
                role = "mixed_group_review"
                representative = False
            elif index == representative_index:
                role = "representative"
                representative = True
            else:
                role = "non_representative"
                representative = False
            metadata[index] = {
                "timestamp_group_id": group_id,
                "timestamp_group_size": len(indices),
                "motion_representative_flag": representative,
                "duplicate_timestamp_policy": policy,
                "duplicate_group_route_mixed_flag": route_mixed,
                "duplicate_group_source_mixed_flag": source_mixed,
                "duplicate_group_membership_mixed_flag": membership_mixed,
                "duplicate_group_wrong_route_mixed_flag": wrong_route_mixed,
                "duplicate_group_review_required": any_mixed,
                "duplicate_group_motion_role": role,
            }
    return metadata


def legitimate_source_transition(previous: dict[str, str], current: dict[str, str]) -> bool:
    previous_source = str(previous.get("horizontal_calibration_source", ""))
    current_source = str(current.get("horizontal_calibration_source", ""))
    previous_class = str(previous.get("route_class", ""))
    current_class = str(current.get("route_class", ""))
    if "REVIEWED_SUMMIT_ANCHOR" in {previous_source, current_source}:
        return True
    protected_classes = {"CONNECTOR", "WRONG_ROUTE"}
    return previous_class in protected_classes or current_class in protected_classes


def mark_stopped_runs(metrics: list[dict[str, Any]]) -> set[int]:
    stopped: set[int] = set()
    run: list[int] = []
    duration = 0.0

    def flush() -> None:
        nonlocal run, duration
        if run and duration >= STOP_MIN_DURATION_SEC:
            stopped.update(run)
        run = []
        duration = 0.0

    for index, metric in enumerate(metrics):
        qualifies = (
            metric["motion_representative"]
            and metric["time_interval_valid"]
            and metric["speed"] is not None
            and metric["speed"] <= STOP_SPEED_MPS
            and metric["pause_or_stall"]
            and not metric["gps_drift_suspected"]
        )
        if qualifies:
            run.append(index)
            duration += metric["dt"] or 0.0
        else:
            flush()
    flush()
    return stopped


def classify_movement(
    metric: dict[str, Any],
    stopped: bool,
) -> tuple[str, str, bool, bool]:
    if metric["duplicate_group_motion_role"] == "mixed_group_review":
        return "MIXED_DUPLICATE_GROUP_REVIEW", "review", True, False
    if not metric["motion_representative"]:
        return "DUPLICATE_TIMESTAMP_NON_REPRESENTATIVE", "review", True, False
    if not metric["time_interval_valid"]:
        return "TIME_INVALID", "review", True, False
    if metric["gps_drift_suspected"]:
        return "GPS_DRIFT_SUSPECTED", "review", True, False
    if stopped:
        confidence = "medium" if metric["horizontal_review"] else "high"
        return "STOPPED", confidence, metric["horizontal_review"], False
    if metric["horizontal_review"] or metric["source"] == "RAW_GPS_FALLBACK":
        speed = metric["speed"]
        low_speed_uncertain = speed is not None and speed <= SLOW_SPEED_MPS
        return "LOW_CONFIDENCE_REVIEW", "low", True, low_speed_uncertain

    speed = metric["speed"]
    route_class = metric["route_class"]
    if speed is not None and speed > STOP_SPEED_MPS and route_class == "WRONG_ROUTE":
        return "WRONG_ROUTE_MOVING", "high", metric["review_evidence"], False
    if speed is not None and speed > STOP_SPEED_MPS and route_class == "OFF_TARGET":
        return "OFF_TARGET_MOVING", "medium", True, False
    if speed is not None and STOP_SPEED_MPS < speed <= SLOW_SPEED_MPS:
        return "SLOW_MOVING", "medium", metric["review_evidence"], True
    if speed is not None and speed > SLOW_SPEED_MPS:
        confidence = "high" if not metric["review_evidence"] else "medium"
        return "MOVING", confidence, metric["review_evidence"], False
    return "UNKNOWN_REVIEW", "review", True, True


def derive_metrics(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    cumulative_distance = 0.0
    group_metadata = build_timestamp_group_metadata(rows)
    previous_representative_index: int | None = None

    for index, row in enumerate(rows):
        duplicate_meta = group_metadata[index]
        motion_representative = bool(duplicate_meta["motion_representative_flag"])
        previous = (
            rows[previous_representative_index]
            if previous_representative_index is not None and motion_representative
            else None
        )
        current_lat = to_float(row.get("calibrated_lat"))
        current_lon = to_float(row.get("calibrated_lon"))
        previous_lat = to_float(previous.get("calibrated_lat")) if previous else None
        previous_lon = to_float(previous.get("calibrated_lon")) if previous else None
        coordinate_valid = valid_latlon(current_lat, current_lon) and valid_latlon(
            previous_lat, previous_lon
        )
        step = (
            haversine_m(previous_lat, previous_lon, current_lat, current_lon)
            if coordinate_valid and motion_representative
            else None
        )

        current_elapsed = to_float(row.get("elapsed_sec"))
        current_timestamp = to_float(row.get("timestamp_s"))
        previous_elapsed = to_float(previous.get("elapsed_sec")) if previous else None
        previous_timestamp = to_float(previous.get("timestamp_s")) if previous else None
        dt = None
        if motion_representative and previous is not None:
            if current_elapsed is not None and previous_elapsed is not None:
                dt = current_elapsed - previous_elapsed
            elif current_timestamp is not None and previous_timestamp is not None:
                dt = current_timestamp - previous_timestamp
        timestamp = to_float(row.get("timestamp_s"))
        duplicate_timestamp = is_true(row.get("duplicate_timestamp_flag"))
        time_valid = (
            motion_representative
            and previous is not None
            and dt is not None
            and dt > 0.0
            and timestamp is not None
            and not duplicate_meta["duplicate_group_wrong_route_mixed_flag"]
        )
        speed = step / dt if time_valid and step is not None else None
        if time_valid and step is not None:
            cumulative_distance += step

        source = str(row.get("horizontal_calibration_source", ""))
        source_transition = bool(
            previous
            and source != str(previous.get("horizontal_calibration_source", ""))
        )
        way_switch = is_true(row.get("candidate_way_switch_flag"))
        source_or_way_switch = source_transition or way_switch
        transition_exempt = bool(
            previous and source_or_way_switch and legitimate_source_transition(previous, row)
        )
        jump = step is not None and step > DISTANCE_JUMP_M
        speed_outlier = speed is not None and speed > MAX_VALID_SPEED_MPS
        pause_jump = is_true(row.get("pause_or_stall_flag")) and jump
        transition_jump = jump and source_or_way_switch

        drift_reasons: list[str] = []
        if pause_jump:
            drift_reasons.append("pause_or_stall_with_distance_jump")
        if speed_outlier:
            drift_reasons.append("calibrated_speed_over_5_mps")
        if transition_jump and not transition_exempt:
            drift_reasons.append("non_exempt_source_or_way_transition_jump")
        gps_drift = bool(drift_reasons)

        horizontal_review = is_true(row.get("horizontal_review_required"))
        distance_review = (
            step is None
            or not time_valid
            or source == "RAW_GPS_FALLBACK"
            or horizontal_review
            or jump
            or duplicate_meta["duplicate_group_review_required"]
            or not motion_representative
        )
        speed_review = (
            not time_valid
            or speed is None
            or (dt is not None and dt > LONG_INTERVAL_SEC)
            or speed_outlier
            or horizontal_review
            or source == "RAW_GPS_FALLBACK"
            or duplicate_meta["duplicate_group_review_required"]
            or not motion_representative
        )
        review_evidence = is_true(row.get("movement_review_required"))

        metrics.append(
            {
                **duplicate_meta,
                "step": step,
                "cumulative_distance": cumulative_distance,
                "dt": dt,
                "speed": speed,
                "time_interval_valid": time_valid,
                "duplicate_timestamp": duplicate_timestamp,
                "pause_or_stall": is_true(row.get("pause_or_stall_flag")),
                "gps_drift_suspected": gps_drift,
                "gps_drift_reason": "|".join(drift_reasons),
                "distance_review_required": distance_review,
                "speed_review_required": speed_review,
                "speed_outlier": speed_outlier,
                "distance_jump": jump,
                "source_transition_jump": transition_jump,
                "source_transition_exempt": transition_exempt,
                "source": source,
                "route_class": str(row.get("route_class", "")),
                "horizontal_review": horizontal_review,
                "review_evidence": review_evidence,
                "motion_representative": motion_representative,
            }
        )
        if motion_representative:
            previous_representative_index = index
    return metrics


def raw_distance_total(rows: list[dict[str, str]]) -> float | None:
    values = [to_float(row.get("raw_distance_m")) for row in rows]
    valid = [value for value in values if value is not None]
    if not valid:
        return None
    return max(valid) - min(valid)


def process_activity(
    route_folder: str,
    activity_id: str,
    v1k_root: Path,
    out_root: Path,
) -> dict[str, Any]:
    input_csv = resolve_input(v1k_root, route_folder, activity_id)
    hash_before = sha256_file(input_csv)
    source_rows, source_fields = read_csv(input_csv)
    missing = [field for field in REQUIRED_FIELDS if field not in source_fields]
    if missing:
        raise ValueError(f"Missing required v1k fields: {', '.join(missing)}")
    overlap = [field for field in NEW_FIELDS if field in source_fields]
    if overlap:
        raise ValueError(f"v1k input already contains v1k2 fields: {', '.join(overlap)}")

    metrics = derive_metrics(source_rows)
    stopped_rows = mark_stopped_runs(metrics)
    output_rows: list[dict[str, Any]] = []
    state_counts: Counter[str] = Counter()
    state_duration: defaultdict[str, float] = defaultdict(float)
    route_class_distance: defaultdict[str, float] = defaultdict(float)

    for index, (row, metric) in enumerate(zip(source_rows, metrics)):
        state, confidence, review_required, low_speed_uncertain = classify_movement(
            metric, index in stopped_rows
        )
        motion_source = (
            f"{metric['source']}_POSITION_DELTA"
            if metric["source"]
            else "UNRESOLVED_POSITION_DELTA"
        )
        additions = {
            "timestamp_group_id": metric["timestamp_group_id"],
            "timestamp_group_size": metric["timestamp_group_size"],
            "motion_representative_flag": metric["motion_representative_flag"],
            "duplicate_timestamp_policy": metric["duplicate_timestamp_policy"],
            "duplicate_group_route_mixed_flag": metric["duplicate_group_route_mixed_flag"],
            "duplicate_group_source_mixed_flag": metric["duplicate_group_source_mixed_flag"],
            "duplicate_group_membership_mixed_flag": metric["duplicate_group_membership_mixed_flag"],
            "duplicate_group_wrong_route_mixed_flag": metric["duplicate_group_wrong_route_mixed_flag"],
            "duplicate_group_review_required": metric["duplicate_group_review_required"],
            "duplicate_group_motion_role": metric["duplicate_group_motion_role"],
            "calibrated_step_distance_m": as_output_number(metric["step"]),
            "calibrated_horizontal_distance_m": metric["cumulative_distance"],
            "calibrated_speed_mps": as_output_number(metric["speed"]),
            "calibrated_speed_source": (
                "CALIBRATED_POSITION_DELTA_OVER_DT"
                if metric["speed"] is not None
                else "UNAVAILABLE_INVALID_TIME_OR_POSITION"
            ),
            "calibrated_motion_source": motion_source,
            "movement_state": state,
            "movement_confidence": confidence,
            "movement_review_required_v1k2": review_required,
            "gps_drift_suspected": metric["gps_drift_suspected"],
            "gps_drift_reason": metric["gps_drift_reason"],
            "low_speed_uncertain": low_speed_uncertain,
            "time_interval_valid": metric["time_interval_valid"],
            "speed_review_required": metric["speed_review_required"],
            "distance_review_required": metric["distance_review_required"],
        }
        output = dict(row)
        output.update(additions)
        output_rows.append(output)
        state_counts[state] += 1
        if metric["time_interval_valid"] and metric["dt"] is not None:
            state_duration[state] += metric["dt"]
        if metric["time_interval_valid"] and metric["step"] is not None:
            route_class_distance[metric["route_class"] or "UNKNOWN"] += metric["step"]

    protected_fields_changed = compare_source_rows(
        source_rows, output_rows, source_fields
    )
    row_order_preserved = [
        row.get("raw_point_index", "") for row in source_rows
    ] == [row.get("raw_point_index", "") for row in output_rows]
    forbidden = sorted(
        field for field in (source_fields + NEW_FIELDS) if field in FORBIDDEN_COLUMNS
    )

    activity_dir = out_root / route_folder / activity_id
    output_csv = activity_dir / f"{route_folder}_{activity_id}_calibrated_motion_v1k2.csv"
    summary_json = activity_dir / f"{route_folder}_{activity_id}_calibrated_motion_summary_v1k2.json"
    provenance_json = activity_dir / f"{route_folder}_{activity_id}_calibrated_motion_provenance_v1k2.json"
    write_csv(output_csv, output_rows, source_fields + NEW_FIELDS)

    hash_after = sha256_file(input_csv)
    valid_speeds = [
        metric["speed"] for metric in metrics if metric["speed"] is not None
    ]
    calibrated_total = metrics[-1]["cumulative_distance"] if metrics else 0.0
    raw_total = raw_distance_total(source_rows)
    raw_vs_calibrated_ratio = (
        raw_total / calibrated_total
        if raw_total is not None and calibrated_total > 0
        else None
    )
    raw_fallback_distance = sum(
        metric["step"] or 0.0
        for metric in metrics
        if metric["time_interval_valid"]
        and metric["source"] == "RAW_GPS_FALLBACK"
    )

    summary = {
        "route_folder": route_folder,
        "activity_id": activity_id,
        "motion_version": VERSION,
        "input_v1k_csv": str(input_csv.resolve()),
        "output_csv": str(output_csv.resolve()),
        "rows": len(output_rows),
        "row_preserved": len(output_rows) == len(source_rows),
        "row_order_preserved": row_order_preserved,
        "protected_fields_changed": protected_fields_changed,
        "v1k_sha256_unchanged": hash_before == hash_after,
        "time_valid_rows": sum(metric["time_interval_valid"] for metric in metrics),
        "time_invalid_rows": sum(not metric["time_interval_valid"] for metric in metrics),
        "duplicate_timestamp_rows": sum(metric["duplicate_timestamp"] for metric in metrics),
        "timestamp_group_count": len({metric["timestamp_group_id"] for metric in metrics}),
        "duplicate_group_count": len(
            {
                metric["timestamp_group_id"]
                for metric in metrics
                if metric["timestamp_group_size"] > 1
            }
        ),
        "representative_rows": sum(metric["motion_representative"] for metric in metrics),
        "non_representative_rows": sum(
            metric["duplicate_group_motion_role"] == "non_representative"
            for metric in metrics
        ),
        "mixed_group_review_rows": sum(
            metric["duplicate_group_motion_role"] == "mixed_group_review"
            for metric in metrics
        ),
        "mixed_route_group_count": len(
            {
                metric["timestamp_group_id"]
                for metric in metrics
                if metric["duplicate_group_route_mixed_flag"]
            }
        ),
        "mixed_source_group_count": len(
            {
                metric["timestamp_group_id"]
                for metric in metrics
                if metric["duplicate_group_source_mixed_flag"]
            }
        ),
        "mixed_membership_group_count": len(
            {
                metric["timestamp_group_id"]
                for metric in metrics
                if metric["duplicate_group_membership_mixed_flag"]
            }
        ),
        "mixed_wrong_route_group_count": len(
            {
                metric["timestamp_group_id"]
                for metric in metrics
                if metric["duplicate_group_wrong_route_mixed_flag"]
            }
        ),
        "distance_excluded_rows": sum(
            not metric["time_interval_valid"] or metric["step"] is None
            for metric in metrics
        ),
        "calibrated_horizontal_distance_m_total": calibrated_total,
        "raw_distance_m_total": raw_total,
        "raw_vs_calibrated_distance_ratio": raw_vs_calibrated_ratio,
        "calibrated_speed_p50": percentile(valid_speeds, 0.50),
        "calibrated_speed_p95": percentile(valid_speeds, 0.95),
        "calibrated_speed_p99": percentile(valid_speeds, 0.99),
        "calibrated_speed_max": max(valid_speeds) if valid_speeds else None,
        "movement_state_counts": dict(state_counts),
        "movement_state_duration_sec": dict(state_duration),
        "gps_drift_suspected_rows": sum(
            metric["gps_drift_suspected"] for metric in metrics
        ),
        "stopped_rows": state_counts["STOPPED"],
        "wrong_route_moving_rows": state_counts["WRONG_ROUTE_MOVING"],
        "off_target_moving_rows": state_counts["OFF_TARGET_MOVING"],
        "low_confidence_review_rows": state_counts["LOW_CONFIDENCE_REVIEW"],
        "speed_outlier_rows": sum(metric["speed_outlier"] for metric in metrics),
        "distance_jump_rows": sum(metric["distance_jump"] for metric in metrics),
        "source_transition_jump_rows": sum(
            metric["source_transition_jump"] for metric in metrics
        ),
        "source_transition_exempt_rows": sum(
            metric["source_transition_exempt"] for metric in metrics
        ),
        "route_class_distance_distribution": dict(route_class_distance),
        "raw_fallback_distance_ratio": (
            raw_fallback_distance / calibrated_total if calibrated_total > 0 else None
        ),
        "forbidden_columns_created": forbidden,
        "runtime_llm_allowed": False,
        "notes": (
            "Horizontal motion derivation only. Heart rate and all v1k fields are "
            "preserved. No elevation, NLSC, facility/radar, or THCI fields are created."
        ),
    }
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    summary_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    provenance = {
        "motion_version": VERSION,
        "route_folder": route_folder,
        "activity_id": activity_id,
        "input_v1k_csv": str(input_csv.resolve()),
        "input_v1k_sha256_before": hash_before,
        "input_v1k_sha256_after": hash_after,
        "input_rows": len(source_rows),
        "output_rows": len(output_rows),
        "protected_fields_changed": protected_fields_changed,
        "row_order_preserved": row_order_preserved,
        "distance_method": "haversine(previous calibrated_lat/lon, current calibrated_lat/lon)",
        "speed_method": "calibrated_step_distance_m / dt_sec",
        "cumulative_distance_rule": (
            "Accumulate only when time_interval_valid=True and step distance is valid."
        ),
        "heart_rate_policy": "Preserved raw heart_rate_bpm; not required for movement state.",
        "route_semantics_policy": (
            "Preserve wrong-route, connector, off-target, route_class, and backend policy."
        ),
        "output_csv": str(output_csv.resolve()),
        "runtime_llm_allowed": False,
    }
    provenance_json.write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary["summary_json"] = str(summary_json.resolve())
    summary["provenance_json"] = str(provenance_json.resolve())
    return summary


def write_batch_summary(out_root: Path, summaries: list[dict[str, Any]]) -> None:
    batch_dir = out_root / "_batch_summary"
    batch_csv = batch_dir / "ib3a_rc_calibrated_motion_v1k2_case_summary.csv"
    batch_json = batch_dir / "ib3a_rc_calibrated_motion_v1k2_case_summary.json"
    contract_json = batch_dir / "ib3a_rc_calibrated_motion_v1k2_contract.json"
    fields = [
        "activity_id",
        "status",
        "rows",
        "row_preserved",
        "row_order_preserved",
        "protected_fields_changed",
        "v1k_sha256_unchanged",
        "time_valid_rows",
        "time_invalid_rows",
        "duplicate_timestamp_rows",
        "timestamp_group_count",
        "duplicate_group_count",
        "representative_rows",
        "non_representative_rows",
        "mixed_group_review_rows",
        "mixed_route_group_count",
        "mixed_source_group_count",
        "mixed_membership_group_count",
        "mixed_wrong_route_group_count",
        "distance_excluded_rows",
        "calibrated_horizontal_distance_m_total",
        "raw_distance_m_total",
        "raw_vs_calibrated_distance_ratio",
        "calibrated_speed_p50",
        "calibrated_speed_p95",
        "calibrated_speed_p99",
        "calibrated_speed_max",
        "movement_state_counts",
        "movement_state_duration_sec",
        "gps_drift_suspected_rows",
        "stopped_rows",
        "wrong_route_moving_rows",
        "off_target_moving_rows",
        "low_confidence_review_rows",
        "speed_outlier_rows",
        "distance_jump_rows",
        "source_transition_jump_rows",
        "route_class_distance_distribution",
        "raw_fallback_distance_ratio",
        "forbidden_columns_created",
        "output_csv",
        "summary_json",
        "provenance_json",
        "notes",
    ]
    csv_rows: list[dict[str, Any]] = []
    for summary in summaries:
        row = dict(summary)
        for field in [
            "movement_state_counts",
            "movement_state_duration_sec",
            "route_class_distance_distribution",
            "forbidden_columns_created",
        ]:
            row[field] = json.dumps(
                row.get(field, {}), ensure_ascii=False, sort_keys=True
            )
        row["notes"] = summary.get("blocking_issue") or summary.get("notes", "")
        csv_rows.append(row)
    write_csv(batch_csv, csv_rows, fields)

    batch = {
        "motion_version": VERSION,
        "activities_n": len(summaries),
        "pass_n": sum(summary.get("status") == "PASS" for summary in summaries),
        "fail_n": sum(summary.get("status") == "FAIL" for summary in summaries),
        "total_rows": sum(summary.get("rows", 0) for summary in summaries),
        "summaries": summaries,
        "output_root": str(out_root.resolve()),
        "runtime_llm_allowed": False,
    }
    batch_json.parent.mkdir(parents=True, exist_ok=True)
    batch_json.write_text(
        json.dumps(batch, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    contract = {
        "motion_version": VERSION,
        "new_fields": NEW_FIELDS,
        "movement_state_enum": [
            "TIME_INVALID",
            "DUPLICATE_TIMESTAMP_NON_REPRESENTATIVE",
            "MIXED_DUPLICATE_GROUP_REVIEW",
            "GPS_DRIFT_SUSPECTED",
            "STOPPED",
            "LOW_CONFIDENCE_REVIEW",
            "WRONG_ROUTE_MOVING",
            "OFF_TARGET_MOVING",
            "SLOW_MOVING",
            "MOVING",
            "UNKNOWN_REVIEW",
        ],
        "thresholds": {
            "max_valid_speed_mps": MAX_VALID_SPEED_MPS,
            "distance_jump_m": DISTANCE_JUMP_M,
            "stop_speed_mps": STOP_SPEED_MPS,
            "slow_speed_mps": SLOW_SPEED_MPS,
            "stop_min_duration_sec": STOP_MIN_DURATION_SEC,
            "long_interval_sec": LONG_INTERVAL_SEC,
        },
        "duplicate_timestamp_policy": (
            "Rows are preserved. Each timestamp group gets one representative row "
            "by minimum raw_point_index unless wrong_route membership is mixed; "
            "only representative rows produce motion distance/speed."
        ),
        "forbidden_columns": sorted(FORBIDDEN_COLUMNS),
        "upstream_fields_immutable": True,
        "heart_rate_preserved_raw": True,
        "runtime_llm_allowed": False,
    }
    contract_json.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8"
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
        description="Build the IB3A-RC v1k2 calibrated horizontal motion layer."
    )
    parser.add_argument("--route-folder", required=True)
    parser.add_argument("--activity-id", default="")
    parser.add_argument("--activity-ids", default="")
    parser.add_argument("--v1k-root", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    summaries: list[dict[str, Any]] = []
    for activity_id in parse_activity_ids(args):
        try:
            summary = process_activity(
                args.route_folder,
                activity_id,
                Path(args.v1k_root),
                Path(args.out_dir),
            )
            passed = (
                summary["row_preserved"]
                and summary["row_order_preserved"]
                and summary["protected_fields_changed"] == 0
                and summary["v1k_sha256_unchanged"]
                and not summary["forbidden_columns_created"]
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
            f"distance_m={summary.get('calibrated_horizontal_distance_m_total', '')} "
            f"states={summary.get('movement_state_counts', {})} "
            f"blocking_issue={summary.get('blocking_issue', '')}"
        )

    write_batch_summary(Path(args.out_dir), summaries)
    fail_n = sum(summary.get("status") != "PASS" for summary in summaries)
    print(
        f"v1k2 activities={len(summaries)} "
        f"pass={len(summaries) - fail_n} fail={fail_n}"
    )
    print(f"output_root={Path(args.out_dir).resolve()}")
    return 1 if fail_n else 0


if __name__ == "__main__":
    raise SystemExit(main())
