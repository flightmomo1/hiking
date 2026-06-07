#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IB3A-RC v1g off-target route detector.

Review-only post-processor:
- Reads v1e point-level summit anchor stabilized CSV
- Reads v1f2 transition-labeled segment CSV
- Labels point-level target route status
- Builds episode-level off/on-target route intervals
- Does NOT modify candidate_context, training_use_policy, usable_on_route, or upstream outputs.
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


def segment_for_elapsed(segments: list[dict[str, str]], elapsed_sec: float) -> dict[str, str] | None:
    for s in segments:
        start = to_float(s.get("start_elapsed_sec"))
        end = to_float(s.get("end_elapsed_sec"))
        if start is None or end is None:
            continue
        if start <= elapsed_sec <= end:
            return s
    return None


def classify_point(row: dict[str, str], seg: dict[str, str] | None, off_candidate_dist_m: float) -> dict[str, Any]:
    context = row.get("candidate_context", "")
    policy = row.get("training_use_policy", "")
    nearest_distance = to_float(row.get("nearest_distance_m"), 999999.0) or 999999.0

    anchor_stabilized = parse_bool(row.get("anchor_stabilized_flag", ""))
    anchor_reason = row.get("anchor_refit_reason", "")

    transition_type = seg.get("transition_type", "") if seg else ""
    transition_review_level = seg.get("transition_review_level", "") if seg else ""

    target_route_status = ""
    target_route_label = ""
    off_target_flag = False
    retain_for_training_flag = False
    retain_for_review_flag = True
    reason = ""

    if anchor_stabilized and anchor_reason == "summit_stay_drift":
        target_route_status = "ON_TARGET_SUMMIT_STAY"
        target_route_label = "SUMMIT_STAY_DRIFT"
        off_target_flag = False
        retain_for_training_flag = True
        retain_for_review_flag = True
        reason = "summit_anchor_stabilized"

    elif policy == "TRAINING_OK_MAINLINE":
        target_route_status = "ON_TARGET_ROUTE"
        target_route_label = "MAINLINE"
        off_target_flag = False
        retain_for_training_flag = True
        retain_for_review_flag = False
        reason = "training_ok_mainline"

    elif policy == "TRAINING_OK_ROUTE_CONNECTOR" or transition_type == "NORMAL_CONNECTOR_MAINLINE_TRANSITION":
        target_route_status = "ON_TARGET_CONNECTOR"
        target_route_label = "CONNECTOR"
        off_target_flag = False
        retain_for_training_flag = True
        retain_for_review_flag = False
        reason = "normal_connector_mainline_transition"

    elif nearest_distance >= off_candidate_dist_m:
        target_route_status = "OFF_CANDIDATE_EXCURSION"
        target_route_label = "OFF_CANDIDATE"
        off_target_flag = True
        retain_for_training_flag = False
        retain_for_review_flag = True
        reason = f"nearest_distance_ge_{off_candidate_dist_m:g}m"

    elif context == "BRANCH_OR_SIDE_TRAIL_LIKELY":
        target_route_status = "OFF_TARGET_BRANCH"
        target_route_label = "BRANCH"
        off_target_flag = True
        retain_for_training_flag = False
        retain_for_review_flag = True
        reason = "branch_or_side_trail_context"

    elif context == "LOW_CONFIDENCE_CANDIDATE" or transition_type == "APPROACH_LOWCONF_OSCILLATION":
        target_route_status = "OFF_TARGET_LOW_CONFIDENCE"
        target_route_label = "LOW_CONFIDENCE"
        off_target_flag = True
        retain_for_training_flag = False
        retain_for_review_flag = True
        reason = "low_confidence_or_approach_lowconf_oscillation"

    elif context == "APPROACH_OR_ROAD" or transition_type == "MAINLINE_EXIT_TO_APPROACH_LOOP":
        target_route_status = "OFF_TARGET_APPROACH_OR_SERVICE"
        target_route_label = "APPROACH_OR_SERVICE"
        off_target_flag = True
        retain_for_training_flag = False
        retain_for_review_flag = True
        reason = "approach_or_service_context"

    else:
        target_route_status = "UNKNOWN_REVIEW"
        target_route_label = "UNKNOWN"
        off_target_flag = True
        retain_for_training_flag = False
        retain_for_review_flag = True
        reason = "unclassified_review_required"

    return {
        "target_route_status": target_route_status,
        "target_route_label": target_route_label,
        "off_target_flag": str(off_target_flag),
        "off_target_reason": reason,
        "retain_for_training_flag": str(retain_for_training_flag),
        "retain_for_review_flag": str(retain_for_review_flag),
        "transition_type": transition_type,
        "transition_review_level": transition_review_level,
    }


def build_episodes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    episodes: list[dict[str, Any]] = []

    current: list[dict[str, Any]] = []
    current_key = None

    def flush() -> None:
        if not current:
            return

        first = current[0]
        last = current[-1]
        status = first.get("target_route_status", "")
        label = first.get("target_route_label", "")

        elapsed_vals = [to_float(r.get("elapsed_sec")) for r in current]
        elapsed_vals = [v for v in elapsed_vals if v is not None]

        dist_vals = [to_float(r.get("nearest_distance_m")) for r in current]
        dist_vals = [v for v in dist_vals if v is not None]

        contexts: dict[str, int] = {}
        transitions: dict[str, int] = {}

        for r in current:
            c = str(r.get("candidate_context", ""))
            t = str(r.get("transition_type", ""))
            contexts[c] = contexts.get(c, 0) + 1
            transitions[t] = transitions.get(t, 0) + 1

        dominant_context = max(contexts.items(), key=lambda kv: kv[1])[0] if contexts else ""
        dominant_transition = max(transitions.items(), key=lambda kv: kv[1])[0] if transitions else ""

        episode_id = f"ep_{len(episodes) + 1:04d}"

        for r in current:
            r["target_route_episode_id"] = episode_id

        episodes.append({
            "episode_id": episode_id,
            "target_route_status": status,
            "target_route_label": label,
            "off_target_flag": first.get("off_target_flag", ""),
            "retain_for_training_flag": first.get("retain_for_training_flag", ""),
            "retain_for_review_flag": first.get("retain_for_review_flag", ""),
            "off_target_reason": first.get("off_target_reason", ""),
            "start_elapsed_sec": min(elapsed_vals) if elapsed_vals else "",
            "end_elapsed_sec": max(elapsed_vals) if elapsed_vals else "",
            "duration_sec": (max(elapsed_vals) - min(elapsed_vals)) if len(elapsed_vals) >= 2 else 0,
            "points_n": len(current),
            "dominant_candidate_context": dominant_context,
            "dominant_transition_type": dominant_transition,
            "nearest_distance_min_m": min(dist_vals) if dist_vals else "",
            "nearest_distance_median_m": sorted(dist_vals)[len(dist_vals) // 2] if dist_vals else "",
            "nearest_distance_max_m": max(dist_vals) if dist_vals else "",
        })

    for r in rows:
        key = (r.get("target_route_status", ""), r.get("target_route_label", ""))
        if current_key is None:
            current_key = key
            current = [r]
        elif key == current_key:
            current.append(r)
        else:
            flush()
            current_key = key
            current = [r]

    flush()
    return episodes


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect IB3A-RC v1g off-target route episodes.")
    parser.add_argument("--route-folder", required=True)
    parser.add_argument("--activity-id", required=True)
    parser.add_argument("--point-csv", required=True, help="v1e point-level summit anchor stabilized CSV")
    parser.add_argument("--segments-csv", required=True, help="v1f2 transition-labeled segments CSV")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--off-candidate-dist-m", type=float, default=30.0)
    args = parser.parse_args()

    route_folder = args.route_folder
    activity_id = args.activity_id

    point_fp = Path(args.point_csv)
    seg_fp = Path(args.segments_csv)
    out_root = Path(args.out_dir)

    point_rows, point_fields = read_csv_rows(point_fp)
    seg_rows, _ = read_csv_rows(seg_fp)
    seg_rows = sorted(seg_rows, key=lambda r: to_float(r.get("start_elapsed_sec"), 0.0) or 0.0)

    out_rows: list[dict[str, Any]] = []

    for row in point_rows:
        elapsed = to_float(row.get("elapsed_sec"))
        seg = segment_for_elapsed(seg_rows, elapsed) if elapsed is not None else None

        labels = classify_point(row, seg, off_candidate_dist_m=args.off_candidate_dist_m)

        new_row = dict(row)
        new_row.update(labels)
        new_row["target_route_episode_id"] = ""
        out_rows.append(new_row)

    episodes = build_episodes(out_rows)

    out_dir = out_root / route_folder / activity_id
    out_point_csv = out_dir / f"{route_folder}_{activity_id}_off_target_route_point_labels_v1g.csv"
    out_episode_csv = out_dir / f"{route_folder}_{activity_id}_off_target_route_episodes_v1g.csv"
    out_summary_json = out_dir / f"{route_folder}_{activity_id}_off_target_route_summary_v1g.json"

    new_point_cols = [
        "target_route_status",
        "target_route_label",
        "target_route_episode_id",
        "off_target_flag",
        "off_target_reason",
        "retain_for_training_flag",
        "retain_for_review_flag",
        "transition_type",
        "transition_review_level",
    ]

    final_point_fields = list(point_fields)
    for c in new_point_cols:
        if c not in final_point_fields:
            final_point_fields.append(c)

    episode_fields = [
        "episode_id",
        "target_route_status",
        "target_route_label",
        "off_target_flag",
        "retain_for_training_flag",
        "retain_for_review_flag",
        "off_target_reason",
        "start_elapsed_sec",
        "end_elapsed_sec",
        "duration_sec",
        "points_n",
        "dominant_candidate_context",
        "dominant_transition_type",
        "nearest_distance_min_m",
        "nearest_distance_median_m",
        "nearest_distance_max_m",
    ]

    write_csv_rows(out_point_csv, out_rows, final_point_fields)
    write_csv_rows(out_episode_csv, episodes, episode_fields)

    status_counts: dict[str, int] = {}
    episode_status_counts: dict[str, int] = {}
    for r in out_rows:
        s = str(r.get("target_route_status", ""))
        status_counts[s] = status_counts.get(s, 0) + 1
    for ep in episodes:
        s = str(ep.get("target_route_status", ""))
        episode_status_counts[s] = episode_status_counts.get(s, 0) + 1

    summary = {
        "route_folder": route_folder,
        "activity_id": activity_id,
        "input_point_csv": str(point_fp),
        "input_segments_csv": str(seg_fp),
        "output_point_csv": str(out_point_csv),
        "output_episode_csv": str(out_episode_csv),
        "rows": len(out_rows),
        "episodes": len(episodes),
        "off_candidate_dist_m": args.off_candidate_dist_m,
        "point_status_counts": status_counts,
        "episode_status_counts": episode_status_counts,
        "training_retained_rows": sum(1 for r in out_rows if r.get("retain_for_training_flag") == "True"),
        "review_retained_rows": sum(1 for r in out_rows if r.get("retain_for_review_flag") == "True"),
        "off_target_rows": sum(1 for r in out_rows if r.get("off_target_flag") == "True"),
    }

    out_summary_json.parent.mkdir(parents=True, exist_ok=True)
    out_summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("IB3A-RC v1g off-target route detection written")
    print(f"POINT CSV: {out_point_csv}")
    print(f"EPISODE CSV: {out_episode_csv}")
    print(f"SUMMARY JSON: {out_summary_json}")
    print(f"rows: {len(out_rows)}")
    print(f"episodes: {len(episodes)}")
    print(f"point_status_counts: {status_counts}")
    print(f"episode_status_counts: {episode_status_counts}")
    print(f"off_target_rows: {summary['off_target_rows']}")
    print(f"training_retained_rows: {summary['training_retained_rows']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
