#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IB3A-RC v1k2a motion artifact classification.

Companion layer for v1k2:
- Reads v1k2 calibrated motion CSV.
- Adds artifact classification fields.
- Does NOT modify v1k / v1j / v1i / original v1k2 outputs.
- Does NOT add elevation / NLSC / facility / radar / THCI fields.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ARTIFACT_COLUMNS = [
    "source_transition_flag",
    "route_class_transition_flag",
    "summit_anchor_transition_flag",
    "raw_fallback_transition_flag",
    "motion_artifact_flag",
    "motion_artifact_type",
    "motion_artifact_reason",
]


FORBIDDEN_SUBSTRINGS = [
    "elevation",
    "nlsc",
    "facility",
    "radar",
    "thci",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    return rows, fields


def write_csv(path: Path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def to_float(v):
    try:
        if v is None:
            return None
        s = str(v).strip()
        if s == "":
            return None
        return float(s)
    except Exception:
        return None


def truth(v) -> bool:
    return str(v).strip().lower() in {"true", "1", "yes", "y", "t"}


def classify_row(row, prev):
    speed = to_float(row.get("calibrated_speed_mps"))
    step = to_float(row.get("calibrated_step_distance_m"))

    speed_outlier = speed is not None and speed > 5.0
    distance_jump = step is not None and step > 20.0

    source_transition = False
    route_transition = False
    summit_transition = False
    raw_fallback_transition = False

    if prev is not None:
        source_transition = row.get("horizontal_calibration_source", "") != prev.get("horizontal_calibration_source", "")
        route_transition = row.get("route_class", "") != prev.get("route_class", "")

        row_source = row.get("horizontal_calibration_source", "")
        prev_source = prev.get("horizontal_calibration_source", "")
        row_route = row.get("route_class", "")
        prev_route = prev.get("route_class", "")

        summit_transition = (
            row_source == "REVIEWED_SUMMIT_ANCHOR"
            or prev_source == "REVIEWED_SUMMIT_ANCHOR"
            or row_route == "MAINLINE_SUMMIT_STAY"
            or prev_route == "MAINLINE_SUMMIT_STAY"
        ) and (source_transition or route_transition)

        raw_fallback_transition = (
            row_source == "RAW_GPS_FALLBACK"
            or prev_source == "RAW_GPS_FALLBACK"
        ) and (source_transition or route_transition)

    artifact_type = "NONE"
    reasons = []

    if speed_outlier:
        reasons.append("calibrated_speed_over_5_mps")
    if distance_jump:
        reasons.append("calibrated_step_distance_over_20m")
    if source_transition:
        reasons.append("source_transition")
    if route_transition:
        reasons.append("route_class_transition")
    if summit_transition:
        reasons.append("summit_anchor_transition")
    if raw_fallback_transition:
        reasons.append("raw_fallback_transition")

    if speed_outlier or distance_jump:
        if summit_transition:
            artifact_type = "SUMMIT_ANCHOR_TRANSITION_JUMP"
        elif raw_fallback_transition:
            artifact_type = "RAW_FALLBACK_TRANSITION_JUMP"
        elif source_transition or route_transition:
            artifact_type = "SOURCE_TRANSITION_JUMP"
        elif distance_jump:
            artifact_type = "DISTANCE_JUMP"
        elif speed_outlier:
            artifact_type = "CALIBRATED_SPEED_OUTLIER"

    row["source_transition_flag"] = str(bool(source_transition))
    row["route_class_transition_flag"] = str(bool(route_transition))
    row["summit_anchor_transition_flag"] = str(bool(summit_transition))
    row["raw_fallback_transition_flag"] = str(bool(raw_fallback_transition))
    row["motion_artifact_flag"] = str(artifact_type != "NONE")
    row["motion_artifact_type"] = artifact_type
    row["motion_artifact_reason"] = "|".join(reasons) if reasons else ""

    return row


def process_activity(route_folder: str, activity_id: str, input_root: Path, out_root: Path):
    src = input_root / route_folder / activity_id / f"{route_folder}_{activity_id}_calibrated_motion_v1k2.csv"
    if not src.exists():
        return {
            "activity_id": activity_id,
            "status": "FAIL",
            "notes": f"missing input: {src}",
        }

    before_hash = sha256_file(src)
    rows, fields = read_csv(src)

    original_rows = [dict(r) for r in rows]

    out_rows = []
    prev = None
    for row in rows:
        classified = classify_row(dict(row), prev)
        out_rows.append(classified)
        prev = row

    out_fields = list(fields)
    for c in ARTIFACT_COLUMNS:
        if c not in out_fields:
            out_fields.append(c)

    out_csv = out_root / route_folder / activity_id / f"{route_folder}_{activity_id}_calibrated_motion_artifacts_v1k2a.csv"
    write_csv(out_csv, out_rows, out_fields)

    after_hash = sha256_file(src)

    protected_changed = 0
    for old, new in zip(original_rows, out_rows):
        for f in fields:
            if old.get(f, "") != new.get(f, ""):
                protected_changed += 1
                break

    artifact_counts = Counter(r.get("motion_artifact_type", "") for r in out_rows)
    route_transition_artifacts = sum(
        r.get("motion_artifact_flag") == "True" and r.get("route_class_transition_flag") == "True"
        for r in out_rows
    )
    source_transition_artifacts = sum(
        r.get("motion_artifact_flag") == "True" and r.get("source_transition_flag") == "True"
        for r in out_rows
    )
    summit_transition_artifacts = sum(
        r.get("motion_artifact_flag") == "True" and r.get("summit_anchor_transition_flag") == "True"
        for r in out_rows
    )
    raw_fallback_transition_artifacts = sum(
        r.get("motion_artifact_flag") == "True" and r.get("raw_fallback_transition_flag") == "True"
        for r in out_rows
    )

    speed_outliers = sum((to_float(r.get("calibrated_speed_mps")) or 0.0) > 5.0 for r in out_rows)
    distance_jumps = sum((to_float(r.get("calibrated_step_distance_m")) or 0.0) > 20.0 for r in out_rows)

    forbidden = [
        c for c in out_fields
        if any(s in c.lower() for s in FORBIDDEN_SUBSTRINGS)
        and c not in fields
    ]

    summary = {
        "activity_id": activity_id,
        "status": "PASS" if before_hash == after_hash and protected_changed == 0 and not forbidden else "FAIL",
        "rows": len(out_rows),
        "input_sha256_unchanged": before_hash == after_hash,
        "protected_fields_changed": protected_changed,
        "forbidden_new_columns": ",".join(forbidden),
        "speed_outliers_gt5": speed_outliers,
        "distance_jumps_gt20": distance_jumps,
        "motion_artifact_rows": sum(r.get("motion_artifact_flag") == "True" for r in out_rows),
        "source_transition_artifact_rows": source_transition_artifacts,
        "route_transition_artifact_rows": route_transition_artifacts,
        "summit_transition_artifact_rows": summit_transition_artifacts,
        "raw_fallback_transition_artifact_rows": raw_fallback_transition_artifacts,
        "artifact_type_counts": json.dumps(dict(artifact_counts), ensure_ascii=False, sort_keys=True),
        "output_csv": str(out_csv),
        "notes": "none",
    }

    out_summary = out_root / route_folder / activity_id / f"{route_folder}_{activity_id}_calibrated_motion_artifacts_summary_v1k2a.json"
    out_summary.parent.mkdir(parents=True, exist_ok=True)
    out_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--route-folder", required=True)
    ap.add_argument("--activity-ids", required=True)
    ap.add_argument("--input-root", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    ids = [x.strip() for x in args.activity_ids.split(",") if x.strip()]
    input_root = Path(args.input_root)
    out_root = Path(args.out_dir)

    summaries = []
    for aid in ids:
        s = process_activity(args.route_folder, aid, input_root, out_root)
        summaries.append(s)
        print(f"[{s['status']}] {aid}: artifacts={s.get('motion_artifact_rows')} summit_artifacts={s.get('summit_transition_artifact_rows')}")

    batch_dir = out_root / "_batch_summary"
    batch_dir.mkdir(parents=True, exist_ok=True)

    csv_path = batch_dir / f"{args.route_folder}_v1k2a_motion_artifact_summary.csv"
    fields = list(summaries[0].keys()) if summaries else []
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summaries)

    json_path = batch_dir / f"{args.route_folder}_v1k2a_motion_artifact_summary.json"
    json_path.write_text(
        json.dumps(
            {
                "route_folder": args.route_folder,
                "activities": summaries,
                "status": "PASS" if all(s["status"] == "PASS" for s in summaries) else "FAIL",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"summary_csv={csv_path}")
    print(f"summary_json={json_path}")
    print("status=" + ("PASS" if all(s["status"] == "PASS" for s in summaries) else "FAIL"))


if __name__ == "__main__":
    main()
