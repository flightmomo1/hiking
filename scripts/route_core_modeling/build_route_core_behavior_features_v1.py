from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


INTERPRETATION_LABELS = [
    "confirmed_hr_recovery",
    "possible_recovery",
    "high_hr_pause_without_recovery",
    "pause_without_hr_drop",
    "facility_rest_with_hr_drop",
    "facility_rest_without_hr_drop",
    "off_route_event",
    "other",
]


def read_events(fp: Path) -> pd.DataFrame:
    if not fp.exists():
        raise FileNotFoundError(f"events CSV not found: {fp}")

    df = pd.read_csv(fp)

    required = [
        "activity_id",
        "event_type",
        "duration_sec",
        "semantic_recovery_interpretation",
    ]

    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"missing required columns in {fp}: {missing}")

    df["duration_sec"] = pd.to_numeric(df["duration_sec"], errors="coerce").fillna(0.0)
    return df


def summarize_activity(events: pd.DataFrame, route_folder: str, activity_id: str) -> dict:
    out = {
        "route_folder": route_folder,
        "activity_id": activity_id,
        "events_total": int(len(events)),
        "terminal_artifact_count": int((events["event_type"] == "terminal_artifact").sum()),
    }

    nonterminal = events[events["event_type"] != "terminal_artifact"].copy()

    out["nonterminal_events"] = int(len(nonterminal))
    out["terminal_artifact_duration_sec"] = float(
        events.loc[events["event_type"] == "terminal_artifact", "duration_sec"].sum()
    )

    nonterminal_event_duration_sec = float(nonterminal["duration_sec"].sum())
    out["nonterminal_event_duration_sec"] = nonterminal_event_duration_sec

    interpreted_duration = 0.0

    for label in INTERPRETATION_LABELS:
        mask = nonterminal["semantic_recovery_interpretation"] == label
        count_col = f"{label}_count"
        dur_col = f"{label}_duration_sec"

        count = int(mask.sum())
        dur = float(nonterminal.loc[mask, "duration_sec"].sum())

        out[count_col] = count
        out[dur_col] = dur

        if label != "other":
            interpreted_duration += dur

    out["total_interpreted_behavior_duration_sec"] = float(interpreted_duration)

    if nonterminal_event_duration_sec > 0:
        out["behavior_duration_ratio_to_nonterminal_event_duration"] = (
            interpreted_duration / nonterminal_event_duration_sec
        )
    else:
        out["behavior_duration_ratio_to_nonterminal_event_duration"] = 0.0

    # Compact QA fields
    out["has_terminal_artifact"] = out["terminal_artifact_count"] > 0
    out["has_off_route_event"] = out["off_route_event_count"] > 0
    out["has_confirmed_hr_recovery"] = out["confirmed_hr_recovery_count"] > 0
    out["has_possible_recovery"] = out["possible_recovery_count"] > 0

    return out


def build_features(
    checkpoint_root: Path,
    route_folder: str,
    activity_ids: list[str],
    out_dir: Path,
) -> Path:
    p3c_root = checkpoint_root / "p3c_26batch" / route_folder

    rows = []

    for activity_id in activity_ids:
        fp = (
            p3c_root
            / activity_id
            / f"{route_folder}_{activity_id}_ib3c_behavior_events.csv"
        )

        events = read_events(fp)
        rows.append(summarize_activity(events, route_folder, activity_id))

    out = pd.DataFrame(rows)

    # Stable ordering
    front_cols = [
        "route_folder",
        "activity_id",
        "events_total",
        "nonterminal_events",
        "terminal_artifact_count",
        "terminal_artifact_duration_sec",
        "nonterminal_event_duration_sec",
    ]

    remaining_cols = [c for c in out.columns if c not in front_cols]
    out = out[front_cols + remaining_cols]

    out_dir.mkdir(parents=True, exist_ok=True)

    out_csv = out_dir / f"{route_folder}_route_core_behavior_features_v1.csv"
    out.to_csv(out_csv, index=False, encoding="utf-8-sig")

    return out_csv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build route-core behavior features from verified IB3C Phase 3-C events."
    )

    parser.add_argument(
        "--checkpoint-root",
        default=r"outputs\_checkpoints\cp_20260530_ib3c_p3c_recovery_interpretation_verified",
        help="Verified Phase 3-C checkpoint root.",
    )

    parser.add_argument(
        "--route-folder",
        default="qixing_lengshuikeng",
        help="Route folder name.",
    )

    parser.add_argument(
        "--activity-ids",
        nargs="+",
        required=True,
        help="Activity IDs to process.",
    )

    parser.add_argument(
        "--out-dir",
        default=r"outputs\route_core_behavior_features_v1",
        help="Output directory.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    out_csv = build_features(
        checkpoint_root=Path(args.checkpoint_root),
        route_folder=args.route_folder,
        activity_ids=args.activity_ids,
        out_dir=Path(args.out_dir),
    )

    print("route-core behavior features written:")
    print(out_csv)


if __name__ == "__main__":
    main()
