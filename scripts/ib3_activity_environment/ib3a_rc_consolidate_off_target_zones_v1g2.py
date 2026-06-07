#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IB3A-RC v1g2 off-target zone consolidation.

Review-only episode-level post-processor:
- Reads v1g off_target_route_episodes_v1g.csv
- Merges fragmented off-target episodes into broader off-target zones
- Does NOT modify point-level labels, training flags, usable_on_route, or upstream outputs.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


OFF_TARGET_STATUSES = {
    "OFF_TARGET_APPROACH_OR_SERVICE",
    "OFF_TARGET_BRANCH",
    "OFF_TARGET_LOW_CONFIDENCE",
    "OFF_CANDIDATE_EXCURSION",
    "UNKNOWN_REVIEW",
}


def to_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def read_csv_rows(fp: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not fp.exists():
        raise FileNotFoundError(fp)
    with fp.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader), list(reader.fieldnames or [])


def write_csv_rows(fp: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    fp.parent.mkdir(parents=True, exist_ok=True)
    with fp.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def is_off_target_episode(row: dict[str, str]) -> bool:
    return row.get("target_route_status", "") in OFF_TARGET_STATUSES or row.get("off_target_flag", "") == "True"


def choose_zone_type(status_counts: dict[str, int]) -> str:
    if not status_counts:
        return "UNKNOWN_ZONE"

    if status_counts.get("OFF_CANDIDATE_EXCURSION", 0) > 0 and (
        status_counts.get("OFF_TARGET_LOW_CONFIDENCE", 0) > 0
        or status_counts.get("OFF_TARGET_APPROACH_OR_SERVICE", 0) > 0
    ):
        return "OFF_TARGET_APPROACH_LOWCONF_ZONE"

    if status_counts.get("OFF_TARGET_APPROACH_OR_SERVICE", 0) > 0:
        return "OFF_TARGET_APPROACH_OR_SERVICE_ZONE"

    if status_counts.get("OFF_TARGET_LOW_CONFIDENCE", 0) > 0:
        return "OFF_TARGET_LOW_CONFIDENCE_ZONE"

    if status_counts.get("OFF_TARGET_BRANCH", 0) > 0:
        return "OFF_TARGET_BRANCH_ZONE"

    if status_counts.get("OFF_CANDIDATE_EXCURSION", 0) > 0:
        return "OFF_CANDIDATE_EXCURSION_ZONE"

    return "OFF_TARGET_REVIEW_ZONE"


def summarize_zone(zone_eps: list[dict[str, str]], zone_index: int) -> dict[str, Any]:
    elapsed_start = []
    elapsed_end = []
    points_total = 0

    status_counts: dict[str, int] = {}
    label_counts: dict[str, int] = {}
    context_counts: dict[str, int] = {}
    transition_counts: dict[str, int] = {}
    reason_counts: dict[str, int] = {}

    dist_medians = []
    dist_maxes = []

    for ep in zone_eps:
        s = to_float(ep.get("start_elapsed_sec"))
        e = to_float(ep.get("end_elapsed_sec"))
        if s is not None:
            elapsed_start.append(s)
        if e is not None:
            elapsed_end.append(e)

        points_total += int(to_float(ep.get("points_n"), 0) or 0)

        for key, counts in [
            (ep.get("target_route_status", ""), status_counts),
            (ep.get("target_route_label", ""), label_counts),
            (ep.get("dominant_candidate_context", ""), context_counts),
            (ep.get("dominant_transition_type", ""), transition_counts),
            (ep.get("off_target_reason", ""), reason_counts),
        ]:
            if key:
                counts[key] = counts.get(key, 0) + 1

        med = to_float(ep.get("nearest_distance_median_m"))
        mx = to_float(ep.get("nearest_distance_max_m"))
        if med is not None:
            dist_medians.append(med)
        if mx is not None:
            dist_maxes.append(mx)

    start = min(elapsed_start) if elapsed_start else ""
    end = max(elapsed_end) if elapsed_end else ""
    duration = (end - start) if isinstance(start, float) and isinstance(end, float) else ""

    def compact_counts(counts: dict[str, int]) -> str:
        return "; ".join(f"{k}:{v}" for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))

    zone_type = choose_zone_type(status_counts)

    return {
        "zone_id": f"zone_{zone_index:04d}",
        "zone_type": zone_type,
        "start_elapsed_sec": start,
        "end_elapsed_sec": end,
        "duration_sec": duration,
        "episodes_n": len(zone_eps),
        "points_n": points_total,
        "component_episode_ids": ";".join(ep.get("episode_id", "") for ep in zone_eps),
        "component_status_counts": compact_counts(status_counts),
        "component_label_counts": compact_counts(label_counts),
        "component_context_counts": compact_counts(context_counts),
        "component_transition_counts": compact_counts(transition_counts),
        "component_reason_counts": compact_counts(reason_counts),
        "nearest_distance_median_of_medians_m": sorted(dist_medians)[len(dist_medians) // 2] if dist_medians else "",
        "nearest_distance_max_m": max(dist_maxes) if dist_maxes else "",
        "retain_for_training_flag": "False",
        "retain_for_review_flag": "True",
        "zone_reason": "consolidated_adjacent_off_target_episodes",
    }


def consolidate_zones(
    episodes: list[dict[str, str]],
    max_gap_sec: float,
    min_zone_duration_sec: float,
    min_zone_points: int,
) -> list[dict[str, Any]]:
    episodes = sorted(episodes, key=lambda r: to_float(r.get("start_elapsed_sec"), 0.0) or 0.0)

    zones: list[list[dict[str, str]]] = []
    current: list[dict[str, str]] = []

    for ep in episodes:
        if not is_off_target_episode(ep):
            if current:
                zones.append(current)
                current = []
            continue

        if not current:
            current = [ep]
            continue

        prev = current[-1]
        prev_end = to_float(prev.get("end_elapsed_sec"), 0.0) or 0.0
        this_start = to_float(ep.get("start_elapsed_sec"), 0.0) or 0.0
        gap = this_start - prev_end

        if gap <= max_gap_sec:
            current.append(ep)
        else:
            zones.append(current)
            current = [ep]

    if current:
        zones.append(current)

    zone_rows = []
    for idx, zone_eps in enumerate(zones, start=1):
        z = summarize_zone(zone_eps, idx)

        duration = to_float(z.get("duration_sec"), 0.0) or 0.0
        points_n = int(to_float(z.get("points_n"), 0) or 0)

        z["zone_quality_flag"] = (
            "KEEP"
            if duration >= min_zone_duration_sec or points_n >= min_zone_points
            else "SHORT_REVIEW"
        )
        zone_rows.append(z)

    return zone_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Consolidate IB3A-RC v1g off-target episodes into v1g2 zones.")
    parser.add_argument("--route-folder", required=True)
    parser.add_argument("--activity-id", required=True)
    parser.add_argument("--episodes-csv", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--max-gap-sec", type=float, default=5.0)
    parser.add_argument("--min-zone-duration-sec", type=float, default=10.0)
    parser.add_argument("--min-zone-points", type=int, default=10)
    args = parser.parse_args()

    route_folder = args.route_folder
    activity_id = args.activity_id
    in_fp = Path(args.episodes_csv)
    out_root = Path(args.out_dir)

    episodes, _ = read_csv_rows(in_fp)
    zone_rows = consolidate_zones(
        episodes,
        max_gap_sec=args.max_gap_sec,
        min_zone_duration_sec=args.min_zone_duration_sec,
        min_zone_points=args.min_zone_points,
    )

    out_dir = out_root / route_folder / activity_id
    out_csv = out_dir / f"{route_folder}_{activity_id}_off_target_route_zones_v1g2.csv"
    out_json = out_dir / f"{route_folder}_{activity_id}_off_target_route_zone_summary_v1g2.json"

    zone_fields = [
        "zone_id",
        "zone_type",
        "start_elapsed_sec",
        "end_elapsed_sec",
        "duration_sec",
        "episodes_n",
        "points_n",
        "component_episode_ids",
        "component_status_counts",
        "component_label_counts",
        "component_context_counts",
        "component_transition_counts",
        "component_reason_counts",
        "nearest_distance_median_of_medians_m",
        "nearest_distance_max_m",
        "retain_for_training_flag",
        "retain_for_review_flag",
        "zone_quality_flag",
        "zone_reason",
    ]

    write_csv_rows(out_csv, zone_rows, zone_fields)

    zone_type_counts: dict[str, int] = {}
    quality_counts: dict[str, int] = {}
    for z in zone_rows:
        zone_type_counts[z["zone_type"]] = zone_type_counts.get(z["zone_type"], 0) + 1
        quality_counts[z["zone_quality_flag"]] = quality_counts.get(z["zone_quality_flag"], 0) + 1

    summary = {
        "route_folder": route_folder,
        "activity_id": activity_id,
        "input_episodes_csv": str(in_fp),
        "output_zones_csv": str(out_csv),
        "episodes_input_n": len(episodes),
        "off_target_episodes_input_n": sum(1 for ep in episodes if is_off_target_episode(ep)),
        "zones_n": len(zone_rows),
        "max_gap_sec": args.max_gap_sec,
        "min_zone_duration_sec": args.min_zone_duration_sec,
        "min_zone_points": args.min_zone_points,
        "zone_type_counts": zone_type_counts,
        "zone_quality_counts": quality_counts,
        "zone_points_total": sum(int(to_float(z.get("points_n"), 0) or 0) for z in zone_rows),
    }

    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("IB3A-RC v1g2 off-target zone consolidation written")
    print(f"CSV: {out_csv}")
    print(f"JSON: {out_json}")
    print(f"episodes input: {len(episodes)}")
    print(f"zones: {len(zone_rows)}")
    print(f"zone_type_counts: {zone_type_counts}")
    print(f"zone_quality_counts: {quality_counts}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
