#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IB3A-RC v1e summit/target anchor stabilization.

Review-only post-processor:
- Reads IB3A-RC v1d3 candidate_point_stability.csv
- Reads IB0A control point projected_to_osm_topk.csv
- Adds summit anchor stabilization evidence columns
- Does NOT modify candidate_context, training_use_policy, movement flags, or upstream outputs.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any


TRUE_SET = {"true", "1", "yes", "y", "t"}


def parse_bool(value: Any) -> bool:
    return str(value).strip().lower() in TRUE_SET


def to_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2.0) ** 2
    )
    return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def load_summit_anchor_projection(anchor_projection_csv: Path) -> dict[str, Any]:
    if not anchor_projection_csv.exists():
        raise FileNotFoundError(f"anchor projection CSV not found: {anchor_projection_csv}")

    candidates: list[tuple[int, float, dict[str, str]]] = []

    with anchor_projection_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            control_id = str(row.get("control_id", "")).strip().lower()
            name = str(row.get("name", "")).strip()
            projection_ok = parse_bool(row.get("projection_ok", ""))

            if not projection_ok:
                continue

            is_summit = (
                control_id in {"turnaround", "summit", "peak"}
                or name in {"七星山", "七星山主峰"}
            )
            if not is_summit:
                continue

            rank = int(to_float(row.get("candidate_rank"), 999999) or 999999)
            offset = to_float(row.get("offset_to_osm_m"), float("inf"))
            candidates.append((rank, offset if offset is not None else float("inf"), row))

    if not candidates:
        raise ValueError("No summit/turnaround projection_ok anchor found in anchor projection CSV.")

    candidates.sort(key=lambda x: (x[0], x[1]))
    row = candidates[0][2]

    matched_id_text = str(row.get("matched_id_text", ""))
    osm_way_id = ""
    for part in matched_id_text.split(";"):
        if part.startswith("osm_way_id="):
            osm_way_id = part.split("=", 1)[1].strip()

    return {
        "anchor_type": "summit",
        "anchor_name": row.get("name", ""),
        "anchor_lat": to_float(row.get("lat")),
        "anchor_lon": to_float(row.get("lon")),
        "anchor_projected_lat": to_float(row.get("projected_lat")),
        "anchor_projected_lon": to_float(row.get("projected_lon")),
        "anchor_refit_osm_way_id": osm_way_id,
        "anchor_projected_dist_on_feature_m": to_float(row.get("projected_dist_on_feature_m")),
        "anchor_offset_to_osm_m": to_float(row.get("offset_to_osm_m")),
        "anchor_match_score": to_float(row.get("match_score")),
        "anchor_projection_source": str(anchor_projection_csv),
        "anchor_matched_id_text": matched_id_text,
        "anchor_highway": row.get("highway", ""),
        "anchor_route_role": row.get("route_role", ""),
        "anchor_selected": row.get("selected", ""),
    }


def read_csv_rows(fp: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not fp.exists():
        raise FileNotFoundError(f"input CSV not found: {fp}")

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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply review-only IB3A-RC v1e summit anchor stabilization."
    )
    parser.add_argument("--route-folder", required=True)
    parser.add_argument("--activity-id", required=True)
    parser.add_argument("--point-stability-csv", required=True)
    parser.add_argument("--anchor-projection-csv", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--anchor-radius-m", type=float, default=50.0)
    parser.add_argument("--require-pause-or-stall", action="store_true")
    args = parser.parse_args()

    route_folder = args.route_folder
    activity_id = args.activity_id
    point_fp = Path(args.point_stability_csv)
    anchor_fp = Path(args.anchor_projection_csv)
    out_root = Path(args.out_dir)

    anchor = load_summit_anchor_projection(anchor_fp)
    rows, fieldnames = read_csv_rows(point_fp)

    anchor_lat = anchor.get("anchor_lat")
    anchor_lon = anchor.get("anchor_lon")
    refit_lat = anchor.get("anchor_projected_lat") or anchor.get("anchor_lat")
    refit_lon = anchor.get("anchor_projected_lon") or anchor.get("anchor_lon")

    if anchor_lat is None or anchor_lon is None:
        raise ValueError("summit anchor missing anchor_lat or anchor_lon")

    new_cols = [
        "anchor_stabilized_flag",
        "anchor_type",
        "anchor_name",
        "anchor_distance_m",
        "anchor_refit_lat",
        "anchor_refit_lon",
        "anchor_refit_osm_way_id",
        "anchor_refit_reason",
    ]

    out_rows: list[dict[str, Any]] = []
    stabilized_rows = 0
    near_anchor_rows = 0
    pause_near_anchor_rows = 0
    distances: list[float] = []

    for row in rows:
        raw_lat = to_float(row.get("lat"))
        raw_lon = to_float(row.get("lon"))
        pause_flag = parse_bool(row.get("pause_or_stall_flag", ""))

        anchor_distance_m: float | None = None
        is_near_anchor = False
        anchor_stabilized = False
        reason = ""

        if raw_lat is not None and raw_lon is not None:
            anchor_distance_m = haversine_m(raw_lat, raw_lon, float(anchor_lat), float(anchor_lon))
            distances.append(anchor_distance_m)
            is_near_anchor = anchor_distance_m <= args.anchor_radius_m

        if is_near_anchor:
            near_anchor_rows += 1

        if is_near_anchor and pause_flag:
            pause_near_anchor_rows += 1

        if is_near_anchor and (pause_flag or not args.require_pause_or_stall):
            anchor_stabilized = True
            stabilized_rows += 1
            reason = "summit_stay_drift" if pause_flag else "near_summit_anchor"

        new_row = dict(row)
        new_row["anchor_stabilized_flag"] = str(anchor_stabilized)
        new_row["anchor_type"] = anchor.get("anchor_type", "") if anchor_stabilized else ""
        new_row["anchor_name"] = anchor.get("anchor_name", "") if anchor_stabilized else ""
        new_row["anchor_distance_m"] = "" if anchor_distance_m is None else f"{anchor_distance_m:.3f}"
        new_row["anchor_refit_lat"] = "" if not anchor_stabilized else refit_lat
        new_row["anchor_refit_lon"] = "" if not anchor_stabilized else refit_lon
        new_row["anchor_refit_osm_way_id"] = "" if not anchor_stabilized else anchor.get("anchor_refit_osm_way_id", "")
        new_row["anchor_refit_reason"] = reason
        out_rows.append(new_row)

    out_dir = out_root / route_folder / activity_id
    out_csv = out_dir / f"{route_folder}_{activity_id}_candidate_point_summit_anchor_stabilized.csv"
    out_summary = out_dir / f"{route_folder}_{activity_id}_summit_anchor_stabilization_summary.json"

    final_fields = list(fieldnames)
    for col in new_cols:
        if col not in final_fields:
            final_fields.append(col)

    write_csv_rows(out_csv, out_rows, final_fields)

    distances_sorted = sorted(distances)
    def percentile(p: float) -> float | None:
        if not distances_sorted:
            return None
        idx = min(len(distances_sorted) - 1, max(0, int(round((len(distances_sorted) - 1) * p))))
        return distances_sorted[idx]

    summary = {
        "route_folder": route_folder,
        "activity_id": activity_id,
        "rows": len(rows),
        "anchor_radius_m": args.anchor_radius_m,
        "require_pause_or_stall": args.require_pause_or_stall,
        "near_anchor_rows": near_anchor_rows,
        "pause_near_anchor_rows": pause_near_anchor_rows,
        "anchor_stabilized_rows": stabilized_rows,
        "anchor_stabilized_ratio": (stabilized_rows / len(rows)) if rows else 0,
        "anchor_distance_m_median": percentile(0.5),
        "anchor_distance_m_p90": percentile(0.9),
        "anchor": anchor,
        "input_point_stability_csv": str(point_fp),
        "output_csv": str(out_csv),
    }

    out_summary.parent.mkdir(parents=True, exist_ok=True)
    out_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("IB3A-RC v1e summit anchor stabilization written")
    print(f"CSV: {out_csv}")
    print(f"JSON: {out_summary}")
    print(f"rows: {len(rows)}")
    print(f"near_anchor_rows: {near_anchor_rows}")
    print(f"pause_near_anchor_rows: {pause_near_anchor_rows}")
    print(f"anchor_stabilized_rows: {stabilized_rows}")
    print(f"anchor_refit_osm_way_id: {anchor.get('anchor_refit_osm_way_id', '')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
