#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IB3A-RC v1h mainline / non-mainline membership labeling.

Review-only final integration label:
- Reads v1g point-level off-target route labels
- Reads v1g2 consolidated off-target zones
- Adds mainline_membership and non-mainline fields
- Does NOT modify raw GPS, candidate_context, training_use_policy, target_route_status, or upstream outputs.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def to_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y", "t"}


def read_csv_rows(fp: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not fp.exists():
        raise FileNotFoundError(fp)

    with fp.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    return rows, fieldnames


def write_csv_rows(fp: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    fp.parent.mkdir(parents=True, exist_ok=True)
    with fp.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def zone_for_elapsed(zones: list[dict[str, str]], elapsed_sec: float) -> dict[str, str] | None:
    for z in zones:
        start = to_float(z.get("start_elapsed_sec"))
        end = to_float(z.get("end_elapsed_sec"))
        if start is None or end is None:
            continue
        if start <= elapsed_sec <= end:
            return z
    return None


def classify_membership(row: dict[str, str], zone: dict[str, str] | None) -> dict[str, Any]:
    status = row.get("target_route_status", "")
    label = row.get("target_route_label", "")
    context = row.get("candidate_context", "")
    policy = row.get("training_use_policy", "")
    transition_type = row.get("transition_type", "")

    zone_id = zone.get("zone_id", "") if zone else ""
    zone_type = zone.get("zone_type", "") if zone else ""
    zone_quality = zone.get("zone_quality_flag", "") if zone else ""

    mainline_membership = ""
    mainline_training_flag = False
    connector_training_flag = False
    summit_training_flag = False
    non_mainline_flag = False
    non_mainline_type = ""
    non_mainline_reason = ""
    review_flag = False

    if status == "ON_TARGET_SUMMIT_STAY":
        mainline_membership = "MAINLINE_SUMMIT_STAY"
        mainline_training_flag = True
        summit_training_flag = True
        review_flag = True
        non_mainline_flag = False
        non_mainline_reason = "summit_stay_kept_as_target_route"

    elif status == "ON_TARGET_ROUTE":
        mainline_membership = "MAINLINE_CORE"
        mainline_training_flag = True
        non_mainline_flag = False
        review_flag = False
        non_mainline_reason = "training_ok_mainline_core"

    elif status == "ON_TARGET_CONNECTOR":
        mainline_membership = "CONNECTOR"
        mainline_training_flag = False
        connector_training_flag = True
        non_mainline_flag = True
        non_mainline_type = "CONNECTOR_NOT_MAINLINE_CORE"
        review_flag = False
        non_mainline_reason = "connector_kept_separate_from_mainline_core"

    elif zone is not None:
        mainline_membership = "NON_MAINLINE_OFF_TARGET_ZONE"
        mainline_training_flag = False
        connector_training_flag = False
        non_mainline_flag = True
        non_mainline_type = zone_type or "OFF_TARGET_ZONE"
        review_flag = True
        non_mainline_reason = f"inside_v1g2_zone:{zone_type}"

    elif status == "OFF_TARGET_BRANCH":
        mainline_membership = "NON_MAINLINE_BRANCH"
        non_mainline_flag = True
        non_mainline_type = "OFF_TARGET_BRANCH"
        review_flag = True
        non_mainline_reason = "branch_or_side_trail_not_mainline"

    elif status == "OFF_TARGET_APPROACH_OR_SERVICE":
        mainline_membership = "NON_MAINLINE_APPROACH_OR_SERVICE"
        non_mainline_flag = True
        non_mainline_type = "OFF_TARGET_APPROACH_OR_SERVICE"
        review_flag = True
        non_mainline_reason = "approach_or_service_not_mainline"

    elif status == "OFF_TARGET_LOW_CONFIDENCE":
        mainline_membership = "NON_MAINLINE_LOW_CONFIDENCE"
        non_mainline_flag = True
        non_mainline_type = "OFF_TARGET_LOW_CONFIDENCE"
        review_flag = True
        non_mainline_reason = "low_confidence_not_mainline"

    elif status == "OFF_CANDIDATE_EXCURSION":
        mainline_membership = "NON_MAINLINE_OFF_CANDIDATE"
        non_mainline_flag = True
        non_mainline_type = "OFF_CANDIDATE_EXCURSION"
        review_flag = True
        non_mainline_reason = "off_candidate_distance_not_mainline"

    else:
        mainline_membership = "UNKNOWN_REVIEW"
        non_mainline_flag = True
        non_mainline_type = "UNKNOWN_REVIEW"
        review_flag = True
        non_mainline_reason = f"unclassified_status:{status}"

    return {
        "mainline_membership": mainline_membership,
        "mainline_training_flag": str(mainline_training_flag),
        "connector_training_flag": str(connector_training_flag),
        "summit_training_flag": str(summit_training_flag),
        "non_mainline_flag": str(non_mainline_flag),
        "non_mainline_type": non_mainline_type,
        "non_mainline_reason": non_mainline_reason,
        "membership_review_flag": str(review_flag),
        "v1g2_zone_id": zone_id,
        "v1g2_zone_type": zone_type,
        "v1g2_zone_quality_flag": zone_quality,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Label IB3A-RC v1h mainline / non-mainline membership.")
    parser.add_argument("--route-folder", required=True)
    parser.add_argument("--activity-id", required=True)
    parser.add_argument("--point-csv", required=True, help="v1g point-level target route labels CSV")
    parser.add_argument("--zone-csv", required=True, help="v1g2 off-target route zones CSV")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    route_folder = args.route_folder
    activity_id = args.activity_id

    point_fp = Path(args.point_csv)
    zone_fp = Path(args.zone_csv)
    out_root = Path(args.out_dir)

    point_rows, point_fields = read_csv_rows(point_fp)
    zones, _ = read_csv_rows(zone_fp)

    out_rows: list[dict[str, Any]] = []

    for row in point_rows:
        elapsed = to_float(row.get("elapsed_sec"))
        zone = zone_for_elapsed(zones, elapsed) if elapsed is not None else None

        membership = classify_membership(row, zone)
        new_row = dict(row)
        new_row.update(membership)
        out_rows.append(new_row)

    new_cols = [
        "mainline_membership",
        "mainline_training_flag",
        "connector_training_flag",
        "summit_training_flag",
        "non_mainline_flag",
        "non_mainline_type",
        "non_mainline_reason",
        "membership_review_flag",
        "v1g2_zone_id",
        "v1g2_zone_type",
        "v1g2_zone_quality_flag",
    ]

    final_fields = list(point_fields)
    for c in new_cols:
        if c not in final_fields:
            final_fields.append(c)

    out_dir = out_root / route_folder / activity_id
    out_csv = out_dir / f"{route_folder}_{activity_id}_mainline_membership_labels_v1h.csv"
    out_json = out_dir / f"{route_folder}_{activity_id}_mainline_membership_summary_v1h.json"

    write_csv_rows(out_csv, out_rows, final_fields)

    membership_counts: dict[str, int] = {}
    non_mainline_counts: dict[str, int] = {}
    zone_type_counts: dict[str, int] = {}

    for r in out_rows:
        m = str(r.get("mainline_membership", ""))
        membership_counts[m] = membership_counts.get(m, 0) + 1

        if parse_bool(r.get("non_mainline_flag")):
            t = str(r.get("non_mainline_type", ""))
            non_mainline_counts[t] = non_mainline_counts.get(t, 0) + 1

        zt = str(r.get("v1g2_zone_type", ""))
        if zt:
            zone_type_counts[zt] = zone_type_counts.get(zt, 0) + 1

    summary = {
        "route_folder": route_folder,
        "activity_id": activity_id,
        "input_point_csv": str(point_fp),
        "input_zone_csv": str(zone_fp),
        "output_csv": str(out_csv),
        "rows": len(out_rows),
        "membership_counts": membership_counts,
        "non_mainline_counts": non_mainline_counts,
        "zone_type_counts": zone_type_counts,
        "mainline_training_rows": sum(1 for r in out_rows if r.get("mainline_training_flag") == "True"),
        "connector_training_rows": sum(1 for r in out_rows if r.get("connector_training_flag") == "True"),
        "summit_training_rows": sum(1 for r in out_rows if r.get("summit_training_flag") == "True"),
        "non_mainline_rows": sum(1 for r in out_rows if r.get("non_mainline_flag") == "True"),
        "membership_review_rows": sum(1 for r in out_rows if r.get("membership_review_flag") == "True"),
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("IB3A-RC v1h mainline membership labels written")
    print(f"CSV: {out_csv}")
    print(f"JSON: {out_json}")
    print(f"rows: {len(out_rows)}")
    print(f"membership_counts: {membership_counts}")
    print(f"non_mainline_counts: {non_mainline_counts}")
    print(f"mainline_training_rows: {summary['mainline_training_rows']}")
    print(f"connector_training_rows: {summary['connector_training_rows']}")
    print(f"non_mainline_rows: {summary['non_mainline_rows']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
