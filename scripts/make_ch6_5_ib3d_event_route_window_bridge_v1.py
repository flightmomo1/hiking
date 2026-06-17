# -*- coding: utf-8 -*-
"""
Build CH6.5 IB3D event to route-window overlay evidence.

This bridge keeps the IB3D elapsed-time behavior events separate from the
CH6.5 route-distance profile. It maps events to 50 m route windows only through
IB3A2 activity points that have both elapsed time and reliable route distance.

It does not modify the v2.2.2 main figure, does not generate scores, and does
not authorize THCI, radar, final-risk, or ability scoring.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ROUTE_FOLDER = "qixing_lengshuikeng"
DEFAULT_CASE_ID = "qixing_lengshuikeng_main_peak_20260523"
DEFAULT_ACTIVITY_IDS = ["37_1", "20_1", "9_1"]
DEFAULT_IB3A2_ROOT = Path("outputs/ib3a2_on_route_activity_filter_v4b_after_forced_route")
DEFAULT_IB3C_ROOT = Path("outputs/ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route")
DEFAULT_OUTPUT_ROOT = Path("outputs/report_figures/ch6_5_ib3d_event_route_window_bridge_v1")

WINDOW_M = 50.0
EVENT_TYPES = [
    "high_hr_recovery_stop",
    "short_pause",
    "off_route_rest",
    "terminal_artifact",
]

BOUNDARY_TEXT = (
    "IB3D events are elapsed-time intervals. This overlay is derived only via "
    "IB3A2 activity points with elapsed_sec and reliable route distance; it is "
    "route-window event evidence, not a behavior curve replacement, score, rank, "
    "THCI score, radar score, or final hiking risk score."
)


@dataclass(frozen=True)
class ActivityPaths:
    activity_id_short: str
    ib3a2_csv: Path
    ib3c_csv: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--route-folder", default=DEFAULT_ROUTE_FOLDER)
    parser.add_argument("--case-id", default=DEFAULT_CASE_ID)
    parser.add_argument("--activity-ids", nargs="+", default=DEFAULT_ACTIVITY_IDS)
    parser.add_argument("--ib3a2-root", type=Path, default=DEFAULT_IB3A2_ROOT)
    parser.add_argument("--ib3c-root", type=Path, default=DEFAULT_IB3C_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--window-m", type=float, default=WINDOW_M)
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def activity_paths(args: argparse.Namespace, activity_id_short: str) -> ActivityPaths:
    ib3a2_csv = (
        resolve_path(args.ib3a2_root)
        / args.route_folder
        / f"{args.route_folder}_{activity_id_short}_mapmatched_activity_labeled.csv"
    )
    ib3c_csv = (
        resolve_path(args.ib3c_root)
        / args.route_folder
        / activity_id_short
        / f"{args.route_folder}_{activity_id_short}_ib3c_behavior_events.csv"
    )
    return ActivityPaths(activity_id_short, ib3a2_csv, ib3c_csv)


def read_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def to_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(["true", "1", "yes", "y"])


def normalize_activity(activity: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    df = activity.copy()
    required = ["elapsed_sec", "usable_on_route"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"IB3A2 activity CSV missing required columns: {missing}")

    for col in ["elapsed_sec", "reliable_route_dist_m", "route_dist_m", "projected_route_dist_m"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "reliable_route_dist_m" in df.columns and df["reliable_route_dist_m"].notna().any():
        route_dist_col = "reliable_route_dist_m"
    elif "route_dist_m" in df.columns and df["route_dist_m"].notna().any():
        route_dist_col = "route_dist_m"
    elif "projected_route_dist_m" in df.columns and df["projected_route_dist_m"].notna().any():
        route_dist_col = "projected_route_dist_m"
    else:
        raise KeyError("IB3A2 activity CSV has no usable route distance column.")

    df["ib3d_bridge_route_dist_m"] = pd.to_numeric(df[route_dist_col], errors="coerce")
    df["elapsed_sec"] = pd.to_numeric(df["elapsed_sec"], errors="coerce")
    df["usable_on_route"] = to_bool(df["usable_on_route"])

    if "excluded_reason" not in df.columns:
        df["excluded_reason"] = ""
    df["excluded_reason"] = df["excluded_reason"].fillna("").astype(str)
    df["off_excluded"] = ~df["usable_on_route"]

    df = df[df["elapsed_sec"].notna()].copy()
    df = df.sort_values("elapsed_sec").reset_index(drop=True)
    return df, route_dist_col


def normalize_events(events: pd.DataFrame) -> pd.DataFrame:
    df = events.copy()
    required = ["event_id", "event_type", "start_elapsed_sec", "end_elapsed_sec"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"IB3C events CSV missing required columns: {missing}")

    for col in ["event_id", "start_elapsed_sec", "end_elapsed_sec", "duration_sec"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["event_type"] = df["event_type"].fillna("").astype(str)
    df = df[
        df["event_type"].isin(EVENT_TYPES)
        & df["start_elapsed_sec"].notna()
        & df["end_elapsed_sec"].notna()
        & (df["end_elapsed_sec"] >= df["start_elapsed_sec"])
    ].copy()
    return df.reset_index(drop=True)


def add_event_flags(activity: pd.DataFrame, events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = activity.copy()
    for event_type in EVENT_TYPES:
        df[f"in_event_{event_type}"] = False

    event_records = []
    elapsed = df["elapsed_sec"]
    for _, event in events.iterrows():
        event_type = str(event["event_type"])
        start = float(event["start_elapsed_sec"])
        end = float(event["end_elapsed_sec"])
        mask = elapsed.between(start, end, inclusive="both")
        route_m = df.loc[mask, "ib3d_bridge_route_dist_m"]
        safe_mask = mask & df["ib3d_bridge_route_dist_m"].notna()
        df.loc[safe_mask, f"in_event_{event_type}"] = True

        safe_route_m = df.loc[safe_mask, "ib3d_bridge_route_dist_m"]
        if safe_route_m.notna().any():
            status = "ROUTE_WINDOW_OVERLAY_READY"
            reason = "event interval has IB3A2 elapsed-time points with reliable route distance"
        elif route_m.empty:
            status = "REVIEW_REQUIRED"
            reason = "event interval has no matching IB3A2 elapsed-time points"
        else:
            status = "REVIEW_REQUIRED"
            reason = "event interval has IB3A2 elapsed-time points but no safe route distance"

        event_records.append(
            {
                "event_id": event.get("event_id", ""),
                "event_type": event_type,
                "start_elapsed_sec": start,
                "end_elapsed_sec": end,
                "activity_point_count_in_interval": int(mask.sum()),
                "safe_route_point_count_in_interval": int(safe_mask.sum()),
                "route_dist_min_m": safe_route_m.min() if safe_route_m.notna().any() else np.nan,
                "route_dist_max_m": safe_route_m.max() if safe_route_m.notna().any() else np.nan,
                "event_mapping_status": status,
                "event_mapping_reason": reason,
            }
        )

    return df, pd.DataFrame(event_records)


def distinct_event_count(events: pd.DataFrame, event_type: str, start_m: float, end_m: float) -> int:
    if events.empty:
        return 0
    sub = events[
        (events["event_type"] == event_type)
        & events["route_dist_min_m"].notna()
        & events["route_dist_max_m"].notna()
        & (events["route_dist_max_m"] >= start_m)
        & (events["route_dist_min_m"] < end_m)
    ]
    return int(sub["event_id"].nunique()) if "event_id" in sub.columns else int(len(sub))


def ratio(series: pd.Series, denominator: int) -> float:
    if denominator <= 0:
        return np.nan
    return float(series.sum()) / float(denominator)


def build_overlay(
    activity_id_short: str,
    activity: pd.DataFrame,
    mapped_events: pd.DataFrame,
    window_m: float,
    route_dist_col: str,
) -> pd.DataFrame:
    route = activity["ib3d_bridge_route_dist_m"].dropna()
    if route.empty:
        raise ValueError(f"{activity_id_short}: no route-distance activity points available.")

    max_route = float(np.ceil(route.max() / window_m) * window_m)
    rows = []
    for start_m in np.arange(0.0, max_route, window_m):
        end_m = start_m + window_m
        in_window = activity["ib3d_bridge_route_dist_m"].ge(start_m) & activity["ib3d_bridge_route_dist_m"].lt(end_m)
        w = activity.loc[in_window].copy()
        point_count = int(len(w))

        if point_count == 0:
            status = "NO_ACTIVITY_POINTS_IN_ROUTE_WINDOW"
        elif mapped_events["event_mapping_status"].eq("REVIEW_REQUIRED").any():
            status = "ROUTE_WINDOW_OVERLAY_READY_WITH_EVENT_REVIEW"
        else:
            status = "ROUTE_WINDOW_OVERLAY_READY"

        rows.append(
            {
                "activity_id_short": activity_id_short,
                "route_window_start_m": round(float(start_m), 3),
                "route_window_end_m": round(float(end_m), 3),
                "activity_point_count": point_count,
                "route_distance_source_column": route_dist_col,
                "high_hr_recovery_stop_ratio": ratio(w["in_event_high_hr_recovery_stop"], point_count),
                "high_hr_recovery_stop_count": distinct_event_count(
                    mapped_events, "high_hr_recovery_stop", start_m, end_m
                ),
                "short_pause_count": distinct_event_count(mapped_events, "short_pause", start_m, end_m),
                "off_route_rest_ratio": ratio(w["in_event_off_route_rest"], point_count),
                "terminal_artifact_ratio": ratio(w["in_event_terminal_artifact"], point_count),
                "usable_on_route_ratio": ratio(w["usable_on_route"], point_count),
                "off_excluded_ratio": ratio(w["off_excluded"], point_count),
                "event_overlay_status": status,
                "event_overlay_boundary": BOUNDARY_TEXT,
            }
        )

    return pd.DataFrame(rows)


def process_activity(args: argparse.Namespace, activity_id_short: str) -> dict[str, object]:
    paths = activity_paths(args, activity_id_short)
    activity_raw = read_csv(paths.ib3a2_csv, "IB3A2 activity")
    events_raw = read_csv(paths.ib3c_csv, "IB3C events")

    activity, route_dist_col = normalize_activity(activity_raw)
    events = normalize_events(events_raw)
    activity_with_events, mapped_events = add_event_flags(activity, events)
    overlay = build_overlay(activity_id_short, activity_with_events, mapped_events, args.window_m, route_dist_col)

    out_root = resolve_path(args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)
    overlay_csv = out_root / f"activity_{activity_id_short}_ib3d_event_route_window_overlay.csv"
    event_map_csv = out_root / f"activity_{activity_id_short}_ib3d_event_mapping_review.csv"
    overlay.to_csv(overlay_csv, index=False, encoding="utf-8-sig")
    mapped_events.to_csv(event_map_csv, index=False, encoding="utf-8-sig")

    return {
        "activity_id_short": activity_id_short,
        "ib3a2_csv": str(paths.ib3a2_csv),
        "ib3c_csv": str(paths.ib3c_csv),
        "ib3a2_columns": "|".join(activity_raw.columns.astype(str)),
        "ib3c_columns": "|".join(events_raw.columns.astype(str)),
        "route_distance_source_column": route_dist_col,
        "activity_rows": len(activity_raw),
        "event_rows": len(events_raw),
        "mapped_event_rows": len(mapped_events),
        "event_review_required_count": int(mapped_events["event_mapping_status"].eq("REVIEW_REQUIRED").sum())
        if not mapped_events.empty
        else 0,
        "overlay_window_rows": len(overlay),
        "overlay_csv": str(overlay_csv),
        "event_mapping_review_csv": str(event_map_csv),
        "event_overlay_status_distribution": " | ".join(
            f"{k}:{v}" for k, v in overlay["event_overlay_status"].value_counts(dropna=False).sort_index().items()
        ),
    }


def main() -> None:
    args = parse_args()
    summaries = []
    for activity_id in args.activity_ids:
        summaries.append(process_activity(args, activity_id))

    out_root = resolve_path(args.output_root)
    summary = pd.DataFrame(summaries)
    summary_csv = out_root / "ib3d_event_route_window_bridge_summary.csv"
    summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")

    report = out_root / "ib3d_event_route_window_bridge_run_report.md"
    lines = [
        "# CH6.5 IB3D Event Route Window Bridge v1",
        "",
        f"Route folder: `{args.route_folder}`",
        f"Window size: `{args.window_m:g} m`",
        "",
        "## Method",
        "",
        "- IB3D events remain elapsed-time intervals.",
        "- Each event is mapped to route windows only through IB3A2 activity rows where `elapsed_sec` falls within the event interval.",
        "- Route distance uses `reliable_route_dist_m` when available, then falls back to `route_dist_m` or `projected_route_dist_m` only if needed.",
        "- Events without safe point-level route distance are marked `REVIEW_REQUIRED` and are not force-filled into a route window.",
        "- This bridge does not modify v2.2.2 behavior curves and does not generate ability, THCI, radar, or final-risk scores.",
        "",
        "## Outputs",
        "",
    ]
    for row in summaries:
        lines.extend(
            [
                f"### {row['activity_id_short']}",
                "",
                f"- IB3A2 input: `{row['ib3a2_csv']}`",
                f"- IB3C input: `{row['ib3c_csv']}`",
                f"- Route distance source: `{row['route_distance_source_column']}`",
                f"- Activity rows: `{row['activity_rows']}`",
                f"- IB3C event rows: `{row['event_rows']}`",
                f"- Bridge event rows: `{row['mapped_event_rows']}`",
                f"- Event review required count: `{row['event_review_required_count']}`",
                f"- Overlay window rows: `{row['overlay_window_rows']}`",
                f"- Overlay status distribution: `{row['event_overlay_status_distribution']}`",
                f"- Overlay CSV: `{row['overlay_csv']}`",
                "",
            ]
        )
    report.write_text("\n".join(lines), encoding="utf-8")

    print(summary.to_string(index=False))
    print(f"\nWrote summary: {summary_csv}")
    print(f"Wrote report: {report}")


if __name__ == "__main__":
    main()
