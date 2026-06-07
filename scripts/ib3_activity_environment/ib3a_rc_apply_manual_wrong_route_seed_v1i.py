#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IB3A-RC v1i manual wrong-route seed labeling.

Review-only patch layer:
- Reads v1h mainline membership labels
- Reads manual wrong-route review CSV
- Adds wrong-route fields
- Builds wrong-route episode table
- Does NOT overwrite v1h or upstream outputs.
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


def read_csv_rows(fp: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not fp.exists():
        raise FileNotFoundError(fp)
    with fp.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    return rows, fields


def write_csv_rows(fp: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    fp.parent.mkdir(parents=True, exist_ok=True)
    with fp.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def seed_matches(row: dict[str, str], seed: dict[str, str]) -> bool:
    field = seed.get("match_field", "").strip()
    value = seed.get("match_value", "").strip()

    if not field or not value:
        return False

    if str(row.get(field, "")).strip() != value:
        return False

    elapsed = to_float(row.get("elapsed_sec"))
    if elapsed is None:
        return False

    start = to_float(seed.get("elapsed_start_sec"))
    end = to_float(seed.get("elapsed_end_sec"))

    if start is not None and elapsed < start:
        return False
    if end is not None and elapsed > end:
        return False

    return True


def seed_applies_to_activity(seed: dict[str, str], activity_id: str) -> bool:
    seed_activity_id = seed.get("activity_id", "").strip()
    return (
        seed_activity_id == activity_id
        or seed_activity_id == "*"
        or seed_activity_id.upper() == "ALL"
        or seed_activity_id == ""
    )


def build_episodes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wrong_rows = [
        r for r in rows
        if str(r.get("wrong_route_flag", "")).lower() == "true"
    ]

    wrong_rows.sort(key=lambda r: (
        str(r.get("wrong_route_label", "")),
        str(r.get("candidate_way_id", "")),
        to_float(r.get("elapsed_sec"), 0.0) or 0.0,
    ))

    episodes: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    current_key: tuple[str, str] | None = None
    last_elapsed: float | None = None

    def flush() -> None:
        nonlocal current
        if not current:
            return

        elapsed_values = [to_float(r.get("elapsed_sec"), 0.0) or 0.0 for r in current]
        nearest_dist_values = [
            to_float(r.get("nearest_distance_m"))
            for r in current
            if to_float(r.get("nearest_distance_m")) is not None
        ]

        first = current[0]
        label = str(first.get("wrong_route_label", ""))
        way_id = str(first.get("candidate_way_id", ""))

        episodes.append({
            "wrong_route_episode_id": f"wrong_route_{len(episodes)+1:04d}",
            "wrong_route_label": label,
            "candidate_way_id": way_id,
            "nearest_osm_way_id": first.get("nearest_osm_way_id", ""),
            "nearest_way_name": first.get("nearest_way_name", ""),
            "start_elapsed_sec": min(elapsed_values),
            "end_elapsed_sec": max(elapsed_values),
            "duration_sec": round(max(elapsed_values) - min(elapsed_values), 3),
            "points_n": len(current),
            "mainline_membership_counts": "; ".join(
                f"{k}:{v}" for k, v in count_values(current, "mainline_membership").items()
            ),
            "wrong_route_type_counts": "; ".join(
                f"{k}:{v}" for k, v in count_values(current, "wrong_route_type").items()
            ),
            "nearest_distance_m_min": round(min(nearest_dist_values), 3) if nearest_dist_values else "",
            "nearest_distance_m_max": round(max(nearest_dist_values), 3) if nearest_dist_values else "",
            "manual_review_reason": first.get("manual_wrong_route_review_reason", ""),
        })

        current = []

    for row in wrong_rows:
        label = str(row.get("wrong_route_label", ""))
        way_id = str(row.get("candidate_way_id", ""))
        elapsed = to_float(row.get("elapsed_sec"), 0.0) or 0.0
        key = (label, way_id)

        if current and (key != current_key or (last_elapsed is not None and elapsed - last_elapsed > 2.0)):
            flush()

        current.append(row)
        current_key = key
        last_elapsed = elapsed

    flush()
    return episodes


def count_values(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in rows:
        v = str(r.get(field, ""))
        counts[v] = counts.get(v, 0) + 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route-folder", required=True)
    parser.add_argument("--activity-id", required=True)
    parser.add_argument("--membership-csv", required=True)
    parser.add_argument("--review-csv", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    route_folder = args.route_folder
    activity_id = args.activity_id

    membership_fp = Path(args.membership_csv)
    review_fp = Path(args.review_csv)
    out_root = Path(args.out_dir)

    rows, fields = read_csv_rows(membership_fp)
    seeds, _ = read_csv_rows(review_fp)

    active_seeds = [
        s for s in seeds
        if s.get("route_folder", "") == route_folder
        and seed_applies_to_activity(s, activity_id)
    ]
    route_level_seeds = [
        s for s in active_seeds
        if s.get("activity_id", "").strip() in {"", "*"}
        or s.get("activity_id", "").strip().upper() == "ALL"
    ]
    blank_activity_id_seeds = [
        s for s in route_level_seeds
        if s.get("activity_id", "").strip() == ""
    ]

    out_rows: list[dict[str, Any]] = []

    for row in rows:
        new_row: dict[str, Any] = dict(row)

        matched_seed = None
        for seed in active_seeds:
            if seed_matches(row, seed):
                matched_seed = seed
                break

        if matched_seed:
            label = matched_seed.get("wrong_route_label", "")
            decision = matched_seed.get("review_decision", "")
            reason = matched_seed.get("review_reason", "")

            new_row["wrong_route_flag"] = "True"
            new_row["wrong_route_type"] = "MANUAL_WRONG_ROUTE_WAY"
            new_row["wrong_route_label"] = label
            new_row["wrong_route_review_decision"] = decision
            new_row["manual_wrong_route_review_reason"] = reason
            new_row["manual_wrong_route_match_field"] = matched_seed.get("match_field", "")
            new_row["manual_wrong_route_match_value"] = matched_seed.get("match_value", "")
            new_row["manual_wrong_route_official_osm_id"] = matched_seed.get("official_osm_id", "")
            new_row["manual_wrong_route_official_way_name"] = matched_seed.get("official_way_name", "")

            if decision == "exclude_from_mainline_training":
                new_row["mainline_training_flag_after_v1i"] = "False"
                new_row["non_mainline_flag_after_v1i"] = "True"
                new_row["non_mainline_type_after_v1i"] = "WRONG_ROUTE_CANDIDATE_EPISODE"
            else:
                new_row["mainline_training_flag_after_v1i"] = row.get("mainline_training_flag", "")
                new_row["non_mainline_flag_after_v1i"] = row.get("non_mainline_flag", "")
                new_row["non_mainline_type_after_v1i"] = row.get("non_mainline_type", "")

        else:
            new_row["wrong_route_flag"] = "False"
            new_row["wrong_route_type"] = ""
            new_row["wrong_route_label"] = ""
            new_row["wrong_route_review_decision"] = ""
            new_row["manual_wrong_route_review_reason"] = ""
            new_row["manual_wrong_route_match_field"] = ""
            new_row["manual_wrong_route_match_value"] = ""
            new_row["manual_wrong_route_official_osm_id"] = ""
            new_row["manual_wrong_route_official_way_name"] = ""
            new_row["mainline_training_flag_after_v1i"] = row.get("mainline_training_flag", "")
            new_row["non_mainline_flag_after_v1i"] = row.get("non_mainline_flag", "")
            new_row["non_mainline_type_after_v1i"] = row.get("non_mainline_type", "")

        out_rows.append(new_row)

    new_cols = [
        "wrong_route_flag",
        "wrong_route_type",
        "wrong_route_label",
        "wrong_route_review_decision",
        "manual_wrong_route_review_reason",
        "manual_wrong_route_match_field",
        "manual_wrong_route_match_value",
        "manual_wrong_route_official_osm_id",
        "manual_wrong_route_official_way_name",
        "mainline_training_flag_after_v1i",
        "non_mainline_flag_after_v1i",
        "non_mainline_type_after_v1i",
    ]

    out_fields = list(fields)
    for c in new_cols:
        if c not in out_fields:
            out_fields.append(c)

    episodes = build_episodes(out_rows)
    episode_fields = [
        "wrong_route_episode_id",
        "wrong_route_label",
        "candidate_way_id",
        "nearest_osm_way_id",
        "nearest_way_name",
        "start_elapsed_sec",
        "end_elapsed_sec",
        "duration_sec",
        "points_n",
        "mainline_membership_counts",
        "wrong_route_type_counts",
        "nearest_distance_m_min",
        "nearest_distance_m_max",
        "manual_review_reason",
    ]

    out_dir = out_root / route_folder / activity_id
    out_csv = out_dir / f"{route_folder}_{activity_id}_wrong_route_manual_seed_labels_v1i.csv"
    out_episode_csv = out_dir / f"{route_folder}_{activity_id}_wrong_route_manual_seed_episodes_v1i.csv"
    out_json = out_dir / f"{route_folder}_{activity_id}_wrong_route_manual_seed_summary_v1i.json"

    write_csv_rows(out_csv, out_rows, out_fields)
    write_csv_rows(out_episode_csv, episodes, episode_fields)

    summary = {
        "route_folder": route_folder,
        "activity_id": activity_id,
        "input_membership_csv": str(membership_fp),
        "input_review_csv": str(review_fp),
        "output_csv": str(out_csv),
        "output_episode_csv": str(out_episode_csv),
        "rows": len(out_rows),
        "active_seeds": len(active_seeds),
        "route_level_seeds": len(route_level_seeds),
        "blank_activity_id_route_level_seeds": len(blank_activity_id_seeds),
        "seed_scope_notes": [
            "activity_id=* and activity_id=ALL are treated as route-level seeds.",
            "A blank seed activity_id is treated as route-level and recorded explicitly.",
        ],
        "wrong_route_rows": sum(1 for r in out_rows if r.get("wrong_route_flag") == "True"),
        "wrong_route_label_counts": count_values(
            [r for r in out_rows if r.get("wrong_route_flag") == "True"],
            "wrong_route_label"
        ),
        "wrong_route_episode_count": len(episodes),
        "mainline_training_rows_before": sum(1 for r in out_rows if r.get("mainline_training_flag") == "True"),
        "mainline_training_rows_after_v1i": sum(1 for r in out_rows if r.get("mainline_training_flag_after_v1i") == "True"),
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("IB3A-RC v1i manual wrong-route seed labels written")
    print(f"CSV: {out_csv}")
    print(f"EPISODES: {out_episode_csv}")
    print(f"JSON: {out_json}")
    print(f"rows: {len(out_rows)}")
    print(f"active_seeds: {len(active_seeds)}")
    print(f"wrong_route_rows: {summary['wrong_route_rows']}")
    print(f"wrong_route_label_counts: {summary['wrong_route_label_counts']}")
    print(f"wrong_route_episode_count: {len(episodes)}")
    print(f"mainline_training_before: {summary['mainline_training_rows_before']}")
    print(f"mainline_training_after_v1i: {summary['mainline_training_rows_after_v1i']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
