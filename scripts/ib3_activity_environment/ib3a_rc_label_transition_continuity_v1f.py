#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IB3A-RC v1f transition continuity labeling.

Review-only segment-level post-processor:
- Reads IB3A-RC v1d3 candidate_context_segments.csv
- Adds transition_type / transition_review_level / transition reason
- Does NOT modify candidate_context, training_use_policy, point-level flags, or upstream outputs.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


MAINLINE_CONTEXTS = {"MAINLINE_LIKELY"}
CONNECTOR_CONTEXTS = {"MAINLINE_CONNECTOR_LIKELY"}
APPROACH_CONTEXTS = {"APPROACH_OR_ROAD"}
BRANCH_CONTEXTS = {"BRANCH_OR_SIDE_TRAIL_LIKELY"}
LOWCONF_CONTEXTS = {"LOW_CONFIDENCE_CANDIDATE"}

TRAINING_OK_POLICIES = {"TRAINING_OK_MAINLINE", "TRAINING_OK_ROUTE_CONNECTOR"}
EXCLUDE_POLICIES = {
    "EXCLUDE_APPROACH_TERMINAL_KEEP_FOR_REVIEW",
    "EXCLUDE_FROM_MAINLINE_TRAINING_KEEP_FOR_REVIEW",
    "EXCLUDE_LOW_CONFIDENCE",
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
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    return rows, fieldnames


def write_csv_rows(fp: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    fp.parent.mkdir(parents=True, exist_ok=True)
    with fp.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def is_mainline(ctx: str) -> bool:
    return ctx in MAINLINE_CONTEXTS


def is_connector(ctx: str) -> bool:
    return ctx in CONNECTOR_CONTEXTS


def is_approach(ctx: str) -> bool:
    return ctx in APPROACH_CONTEXTS


def is_branch(ctx: str) -> bool:
    return ctx in BRANCH_CONTEXTS


def is_lowconf(ctx: str) -> bool:
    return ctx in LOWCONF_CONTEXTS


def is_training_ok(policy: str) -> bool:
    return policy in TRAINING_OK_POLICIES


def classify_transition(
    prev_row: dict[str, str] | None,
    row: dict[str, str],
    next_row: dict[str, str] | None,
    max_normal_dist_m: float,
) -> dict[str, str]:
    """Classify transition around the current segment using previous and next segments.

    The label is stored on the current segment. This is segment-level evidence only.
    """
    ctx = row.get("dominant_candidate_context", "")
    policy = row.get("dominant_training_policy", "")
    way = row.get("dominant_candidate_way_id", "")

    prev_ctx = prev_row.get("dominant_candidate_context", "") if prev_row else ""
    next_ctx = next_row.get("dominant_candidate_context", "") if next_row else ""
    prev_policy = prev_row.get("dominant_training_policy", "") if prev_row else ""
    next_policy = next_row.get("dominant_training_policy", "") if next_row else ""
    prev_way = prev_row.get("dominant_candidate_way_id", "") if prev_row else ""
    next_way = next_row.get("dominant_candidate_way_id", "") if next_row else ""

    dist = to_float(row.get("median_nearest_distance_m"), 999999.0)
    p90 = to_float(row.get("p90_nearest_distance_m"), 999999.0)
    jump_count = int(to_float(row.get("route_dist_jump_count"), 0) or 0)

    transition_type = ""
    stabilized = "False"
    review_level = "none"
    reason = ""

    # A. Normal connector/mainline continuity.
    # Mark connector segments surrounded by mainline or adjacent to mainline,
    # and also mark short mainline transition segments adjacent to connector.
    duration_sec = to_float(row.get("duration_sec"), 0.0) or 0.0
    points_n = int(to_float(row.get("points_n"), 0) or 0)

    # v1f2: avoid labeling long MAINLINE segments as transition only because
    # they are adjacent to a connector segment. Keep the transition label on
    # connector segments, and only allow short mainline bridge segments to be
    # labeled as transition.
    is_short_mainline_bridge = (
        is_mainline(ctx)
        and (is_connector(prev_ctx) or is_connector(next_ctx))
        and (duration_sec <= 30.0 or points_n <= 30)
    )

    connector_mainline_pair = (
        (is_connector(ctx) and (is_mainline(prev_ctx) or is_mainline(next_ctx)))
        or is_short_mainline_bridge
    )
    policy_pair_ok = (
        is_training_ok(policy)
        and ((prev_row is not None and is_training_ok(prev_policy)) or (next_row is not None and is_training_ok(next_policy)))
    )

    if connector_mainline_pair and policy_pair_ok and (dist is not None and dist <= max_normal_dist_m) and jump_count == 0:
        transition_type = "NORMAL_CONNECTOR_MAINLINE_TRANSITION"
        stabilized = "True"
        review_level = "none"
        reason = "training_ok_connector_mainline_continuity"

    # B. Mainline or connector exit into approach / branch / low confidence.
    elif (is_approach(ctx) or is_branch(ctx) or is_lowconf(ctx)) and (
        is_mainline(prev_ctx) or is_connector(prev_ctx)
    ):
        transition_type = "MAINLINE_EXIT_TO_APPROACH_LOOP"
        stabilized = "False"
        review_level = "review_only"
        reason = "mainline_or_connector_exits_to_excluded_context"

    # C. Approach/branch/lowconf zone oscillation.
    elif (
        (is_approach(ctx) or is_branch(ctx) or is_lowconf(ctx))
        and (
            is_approach(prev_ctx) or is_branch(prev_ctx) or is_lowconf(prev_ctx)
            or is_approach(next_ctx) or is_branch(next_ctx) or is_lowconf(next_ctx)
        )
    ):
        transition_type = "APPROACH_LOWCONF_OSCILLATION"
        stabilized = "False"
        review_level = "review_only"
        reason = "excluded_context_oscillation_preserve_review"

    # D. Isolated branch blip inside mainline area.
    elif is_branch(ctx) and (is_mainline(prev_ctx) or is_mainline(next_ctx)) and (dist is not None and dist <= max_normal_dist_m):
        transition_type = "ISOLATED_BRANCH_BLIP_NEAR_MAINLINE"
        stabilized = "False"
        review_level = "evidence_only"
        reason = "short_branch_evidence_near_mainline"

    # E. No special transition.
    else:
        transition_type = "NO_SPECIAL_TRANSITION"
        stabilized = "False"
        review_level = row.get("segment_review_level", "") or "none"
        reason = ""

    return {
        "transition_type": transition_type,
        "transition_stabilized_flag": stabilized,
        "transition_review_level": review_level,
        "transition_from_context": prev_ctx,
        "transition_to_context": next_ctx,
        "transition_from_way_id": prev_way,
        "transition_to_way_id": next_way,
        "transition_reason": reason,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Label IB3A-RC v1f connector/mainline and approach transition continuity."
    )
    parser.add_argument("--route-folder", required=True)
    parser.add_argument("--activity-id", required=True)
    parser.add_argument("--segments-csv", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--max-normal-dist-m", type=float, default=10.0)
    args = parser.parse_args()

    route_folder = args.route_folder
    activity_id = args.activity_id
    in_fp = Path(args.segments_csv)
    out_root = Path(args.out_dir)

    rows, fieldnames = read_csv_rows(in_fp)
    rows = sorted(rows, key=lambda r: to_float(r.get("start_elapsed_sec"), 0.0) or 0.0)

    out_rows: list[dict[str, Any]] = []
    transition_counts: dict[str, int] = {}

    for idx, row in enumerate(rows):
        prev_row = rows[idx - 1] if idx > 0 else None
        next_row = rows[idx + 1] if idx < len(rows) - 1 else None

        transition = classify_transition(
            prev_row=prev_row,
            row=row,
            next_row=next_row,
            max_normal_dist_m=args.max_normal_dist_m,
        )

        new_row = dict(row)
        new_row.update(transition)
        out_rows.append(new_row)

        t = transition["transition_type"]
        transition_counts[t] = transition_counts.get(t, 0) + 1

    new_cols = [
        "transition_type",
        "transition_stabilized_flag",
        "transition_review_level",
        "transition_from_context",
        "transition_to_context",
        "transition_from_way_id",
        "transition_to_way_id",
        "transition_reason",
    ]

    final_fields = list(fieldnames)
    for c in new_cols:
        if c not in final_fields:
            final_fields.append(c)

    out_dir = out_root / route_folder / activity_id
    out_csv = out_dir / f"{route_folder}_{activity_id}_candidate_context_segments_v1f_transition_labeled.csv"
    out_json = out_dir / f"{route_folder}_{activity_id}_transition_continuity_summary.json"

    write_csv_rows(out_csv, out_rows, final_fields)

    summary = {
        "route_folder": route_folder,
        "activity_id": activity_id,
        "input_segments_csv": str(in_fp),
        "output_segments_csv": str(out_csv),
        "segments_n": len(rows),
        "max_normal_dist_m": args.max_normal_dist_m,
        "transition_counts": transition_counts,
        "review_only_segments_n": sum(1 for r in out_rows if r.get("transition_review_level") == "review_only"),
        "stabilized_segments_n": sum(1 for r in out_rows if r.get("transition_stabilized_flag") == "True"),
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("IB3A-RC v1f transition continuity labels written")
    print(f"CSV: {out_csv}")
    print(f"JSON: {out_json}")
    print(f"segments: {len(rows)}")
    print(f"transition_counts: {transition_counts}")
    print(f"stabilized_segments: {summary['stabilized_segments_n']}")
    print(f"review_only_segments: {summary['review_only_segments_n']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

