# -*- coding: utf-8 -*-
"""
IB3D V1: Plot observed activity behavior timeline.

Purpose:
    Build a time-axis behavior profile from:
      - IB3A2 labeled activity CSV
      - IB3C behavior_events CSV

This figure is different from IB3B2 route-distance QA board.
IB3D uses elapsed time as x-axis, so off-route, stop, recovery,
and terminal_artifact events can be interpreted naturally.

Example:
    python scripts/ib3_activity_environment/ib3d_plot_observed_behavior_timeline_v1.py ^
        --route-folder qixing_lengshuikeng ^
        --case-id qixing_lengshuikeng_main_peak_20260523 ^
        --activity-id 37_1 ^
        --ib3a2-root outputs/ib3a2_on_route_activity_filter_v4b_after_forced_route ^
        --ib3c-root outputs/ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route ^
        --out-dir outputs/ib3d_observed_behavior_timeline_v1
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_IB3A2_ROOT = Path("outputs/ib3a2_on_route_activity_filter_v4b_after_forced_route")
DEFAULT_IB3C_ROOT = Path("outputs/ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route")
DEFAULT_OUT_DIR = Path("outputs/ib3d_observed_behavior_timeline_v1")

EVENT_COLOR = {
    "high_hr_recovery_stop": "#dc2626",
    "short_pause": "#f59e0b",
    "facility_rest": "#16a34a",
    "navigation_check": "#0ea5e9",
    "off_route_rest": "#7c3aed",
    "off_route_detour": "#9333ea",
    "route_uncertainty_stop": "#64748b",
    "terminal_artifact": "#475569",
}

EVENT_PRIORITY = [
    "terminal_artifact",
    "off_route_rest",
    "off_route_detour",
    "route_uncertainty_stop",
    "facility_rest",
    "navigation_check",
    "high_hr_recovery_stop",
    "short_pause",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--route-folder", default="qixing_lengshuikeng")
    parser.add_argument("--case-id", default="qixing_lengshuikeng_main_peak_20260523")
    parser.add_argument("--activity-id", default="37_1")
    parser.add_argument("--ib3a2-root", type=Path, default=DEFAULT_IB3A2_ROOT)
    parser.add_argument("--ib3c-root", type=Path, default=DEFAULT_IB3C_ROOT)
    parser.add_argument("--activity-csv", type=Path, default=None)
    parser.add_argument("--events-csv", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--speed-cap-mps", type=float, default=3.0)
    parser.add_argument(
        "--show-hr-zones",
        action="store_true",
        help="Show estimated HR zones on the heart-rate panel.",
    )
    parser.add_argument(
        "--age",
        type=float,
        default=None,
        help="Age used to estimate HRmax when --hr-max-bpm is not provided.",
    )
    parser.add_argument(
        "--sex",
        choices=["male", "female", "unknown"],
        default="unknown",
        help="Sex used only for HRmax estimation formula.",
    )
    parser.add_argument(
        "--hr-max-bpm",
        type=float,
        default=None,
        help="Optional known personal maximum heart rate. Overrides age/sex estimate.",
    )
    return parser.parse_args()


def resolve_path(p: Path) -> Path:
    p = Path(p)
    if p.is_absolute():
        return p
    return PROJECT_ROOT / p


def resolve_activity_csv(args: argparse.Namespace) -> Path:
    if args.activity_csv is not None:
        return resolve_path(args.activity_csv)

    route_dir = resolve_path(args.ib3a2_root) / args.route_folder
    return route_dir / f"{args.route_folder}_{args.activity_id}_mapmatched_activity_labeled.csv"


def resolve_events_csv(args: argparse.Namespace) -> Path:
    if args.events_csv is not None:
        return resolve_path(args.events_csv)

    return (
        resolve_path(args.ib3c_root)
        / args.route_folder
        / args.activity_id
        / f"{args.route_folder}_{args.activity_id}_ib3c_behavior_events.csv"
    )


def read_csv_required(fp: Path, label: str) -> pd.DataFrame:
    if not fp.exists():
        raise FileNotFoundError(f"Missing {label}: {fp}")
    df = pd.read_csv(fp, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def to_bool_series(s: pd.Series) -> pd.Series:
    return s.astype(str).str.lower().isin(["true", "1", "yes", "y"])


def normalize_activity(df: pd.DataFrame, speed_cap_mps: float) -> pd.DataFrame:
    df = df.copy()

    rename = {
        "lat": "raw_lat",
        "lon": "raw_lon",
        "offset_m": "offset_to_mainline_m",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    for c in [
        "elapsed_sec",
        "timestamp_s",
        "route_dist_m",
        "nearest_route_dist_m",
        "offset_to_mainline_m",
        "heart_rate_bpm",
        "row_index",
        "point_index",
    ]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    if "elapsed_sec" not in df.columns or not df["elapsed_sec"].notna().any():
        if "timestamp_s" in df.columns and df["timestamp_s"].notna().any():
            t0 = df["timestamp_s"].dropna().iloc[0]
            df["elapsed_sec"] = df["timestamp_s"] - t0
        else:
            df["elapsed_sec"] = np.arange(len(df), dtype=float)

    if "row_index" not in df.columns:
        df["row_index"] = np.arange(len(df), dtype=int)

    if "usable_on_route" in df.columns:
        df["usable_on_route"] = to_bool_series(df["usable_on_route"])
    else:
        df["usable_on_route"] = True

    if "route_dist_m" not in df.columns:
        df["route_dist_m"] = np.nan

    if "offset_to_mainline_m" not in df.columns:
        df["offset_to_mainline_m"] = np.nan

    if "heart_rate_bpm" not in df.columns:
        df["heart_rate_bpm"] = np.nan

    for c in ["match_quality", "excluded_reason", "manual_interpretation"]:
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].fillna("").astype(str)

    df = df.sort_values(["elapsed_sec", "row_index"], na_position="last").reset_index(drop=True)
    add_simple_forward_speed(df, speed_cap_mps)
    add_gps_speed(df, speed_cap_mps)
    return df


def add_simple_forward_speed(df: pd.DataFrame, speed_cap_mps: float) -> None:
    elapsed = pd.to_numeric(df["elapsed_sec"], errors="coerce")
    dist = pd.to_numeric(df["route_dist_m"], errors="coerce")

    dt = elapsed.diff()
    dd = dist.diff()

    raw = dd.where(dd >= 0).div(dt.where(dt > 0))
    raw = raw.clip(lower=0, upper=speed_cap_mps)

    # Break speed at unusable/off-route rows so it does not pretend to be route-core speed.
    usable = df["usable_on_route"].fillna(False)
    raw = raw.where(usable)

    df["ib3d_forward_speed_mps_raw"] = raw
    df["ib3d_forward_speed_mps_smooth"] = (
        raw.rolling(21, center=True, min_periods=5).median()
    )


def add_gps_speed(df: pd.DataFrame, speed_cap_mps: float) -> None:
    if not {"raw_lat", "raw_lon", "elapsed_sec"}.issubset(df.columns):
        df["ib3d_gps_speed_mps_raw"] = np.nan
        df["ib3d_gps_speed_mps_smooth"] = np.nan
        return

    lat = pd.to_numeric(df["raw_lat"], errors="coerce")
    lon = pd.to_numeric(df["raw_lon"], errors="coerce")
    elapsed = pd.to_numeric(df["elapsed_sec"], errors="coerce")

    lat0 = float(lat.dropna().median()) if lat.notna().any() else 0.0
    meters_per_lat = 111_320.0
    meters_per_lon = 111_320.0 * np.cos(np.deg2rad(lat0))

    x = lon * meters_per_lon
    y = lat * meters_per_lat

    dx = x.diff()
    dy = y.diff()
    dt = elapsed.diff()

    dist = np.sqrt(dx * dx + dy * dy)
    gps_speed = dist.div(dt.where(dt > 0))
    gps_speed = gps_speed.clip(lower=0, upper=speed_cap_mps)

    df["ib3d_gps_speed_mps_raw"] = gps_speed
    df["ib3d_gps_speed_mps_smooth"] = (
        gps_speed.rolling(21, center=True, min_periods=5).median()
    )



def normalize_events(events: pd.DataFrame) -> pd.DataFrame:
    events = events.copy()
    for c in [
        "event_id",
        "start_elapsed_sec",
        "end_elapsed_sec",
        "duration_sec",
        "start_route_dist_m",
        "end_route_dist_m",
        "route_dist_span_m",
        "max_offset_m",
        "max_hr_bpm",
        "estimated_recovery_score",
        "confidence",
    ]:
        if c in events.columns:
            events[c] = pd.to_numeric(events[c], errors="coerce")

    for c in [
        "event_type",
        "event_subtype",
        "rest_duration_tier",
        "recovery_level",
        "recovery_interpretation",
    ]:
        if c not in events.columns:
            events[c] = ""
        events[c] = events[c].fillna("").astype(str)

    return events.sort_values(["start_elapsed_sec", "event_id"], na_position="last").reset_index(drop=True)


def event_types_in_order(events: pd.DataFrame) -> list[str]:
    found = list(events["event_type"].dropna().astype(str).unique())
    ordered = [t for t in EVENT_PRIORITY if t in found]
    ordered += [t for t in found if t not in ordered]
    return ordered


def add_event_spans_to_axis(ax, events: pd.DataFrame, alpha: float = 0.08) -> None:
    if events.empty:
        return

    for _, row in events.iterrows():
        etype = str(row.get("event_type", ""))

        if etype == "terminal_artifact":
            continue

        color = EVENT_COLOR.get(etype, "#334155")
        start = row.get("start_elapsed_sec", np.nan)
        end = row.get("end_elapsed_sec", np.nan)
        if not np.isfinite(start) or not np.isfinite(end):
            continue

        ax.axvspan(start / 60.0, end / 60.0, color=color, alpha=alpha, lw=0)


def estimate_hr_max_bpm(
    age: float | None = None,
    sex: str = "unknown",
    hr_max_bpm: float | None = None,
) -> float:
    if hr_max_bpm is not None and np.isfinite(hr_max_bpm) and hr_max_bpm > 0:
        return float(hr_max_bpm)

    if age is None or not np.isfinite(age) or age <= 0:
        return np.nan

    # Visualization heuristic only.
    # female: Gulati-style estimate
    # male/unknown: Tanaka-style estimate
    if sex == "female":
        return float(206.0 - 0.88 * age)

    return float(208.0 - 0.7 * age)


def add_hr_zone_bands(
    ax,
    hr_max_bpm: float,
) -> None:
    if not np.isfinite(hr_max_bpm) or hr_max_bpm <= 0:
        return

    zones = [
        (0.50, 0.60, "Z1"),
        (0.60, 0.70, "Z2"),
        (0.70, 0.80, "Z3"),
        (0.80, 0.90, "Z4"),
        (0.90, 1.00, "Z5"),
    ]

    for lo, hi, label in zones:
        y0 = lo * hr_max_bpm
        y1 = hi * hr_max_bpm

        ax.axhspan(
            y0,
            y1,
            alpha=0.045,
            lw=0,
            zorder=0,
        )

    for pct in [0.50, 0.60, 0.70, 0.80, 0.90]:
        y = pct * hr_max_bpm
        ax.axhline(
            y,
            linestyle="--",
            linewidth=0.6,
            alpha=0.35,
            zorder=0,
        )
        ax.text(
            0.995,
            y,
            f"{int(pct * 100)}%",
            transform=ax.get_yaxis_transform(),
            ha="right",
            va="bottom",
            fontsize=7,
            alpha=0.75,
        )



def add_low_speed_spans_to_axis(
    ax,
    activity: pd.DataFrame,
    speed_col: str = "ib3d_gps_speed_mps_smooth",
    threshold_mps: float = 0.7,
    min_duration_sec: float = 20.0,
) -> None:
    if speed_col not in activity.columns:
        return

    work = activity[["elapsed_sec", speed_col]].copy()
    work["elapsed_sec"] = pd.to_numeric(work["elapsed_sec"], errors="coerce")
    work[speed_col] = pd.to_numeric(work[speed_col], errors="coerce")
    work = work.dropna(subset=["elapsed_sec", speed_col]).sort_values("elapsed_sec")

    if work.empty:
        return

    low = work[speed_col] < threshold_mps
    block_id = low.ne(low.shift()).cumsum()
    work["low_speed"] = low
    work["block_id"] = block_id

    for _, g in work[work["low_speed"]].groupby("block_id"):
        start = float(g["elapsed_sec"].min())
        end = float(g["elapsed_sec"].max())
        duration = end - start

        if duration < min_duration_sec:
            continue

        ax.axvspan(
            start / 60.0,
            end / 60.0,
            color="#e5e7eb",
            alpha=0.35,
            lw=0,
            zorder=0,
        )


def plot_timeline(
    out_png: Path,
    activity: pd.DataFrame,
    events: pd.DataFrame,
    route_folder: str,
    activity_id: str,
    show_hr_zones: bool = False,
    hr_max_bpm: float = np.nan,
) -> None:
    t_min = activity["elapsed_sec"] / 60.0

    fig = plt.figure(figsize=(16, 11), constrained_layout=False)
    gs = fig.add_gridspec(
        5,
        1,
        height_ratios=[1.0, 1.0, 0.8, 0.45, 1.25],
        hspace=0.18,
    )
    
    ax_speed = fig.add_subplot(gs[0])
    ax_hr = fig.add_subplot(gs[1], sharex=ax_speed)
    ax_offset = fig.add_subplot(gs[2], sharex=ax_speed)
    ax_onroute = fig.add_subplot(gs[3], sharex=ax_speed)
    ax_events = fig.add_subplot(gs[4], sharex=ax_speed)

    for ax in [ax_speed, ax_hr, ax_offset, ax_onroute]:
        add_low_speed_spans_to_axis(
            ax,
            activity,
            speed_col="ib3d_gps_speed_mps_smooth",
            threshold_mps=0.7,
            min_duration_sec=20.0,
        )
        add_event_spans_to_axis(ax, events, alpha=0.07)
        ax.grid(True, alpha=0.22)

    # Panel 1: speed
    # ax_speed.scatter(
    #     t_min,
    #     activity["ib3d_forward_speed_mps_raw"],
    #     s=4,
    #     alpha=0.10,
    #     label="route-axis speed raw",
    # )

    ax_speed.plot(
        t_min,
        activity["ib3d_gps_speed_mps_smooth"],
        lw=1.3,
        alpha=0.9,
        label="GPS movement speed smooth",
    )

    ax_speed.set_ylabel("Speed (m/s)")
    ax_speed.set_ylim(0, 3.1)

    speed_thresholds = [
        (0.3, "0.3"),
        (0.7, "0.7 IB3C low-speed"),
        (1.0, "1.0"),
        (1.5, "1.5"),
        (2.0, "2.0"),
    ]

    for y, label in speed_thresholds:
        is_main = abs(y - 0.7) < 1e-9
        ax_speed.axhline(
            y,
            color="#dc2626" if is_main else "#94a3b8",
            linestyle="--",
            linewidth=0.9 if is_main else 0.7,
            alpha=0.75 if is_main else 0.45,
            zorder=0,
        )
        ax_speed.text(
            0.995,
            y,
            label,
            transform=ax_speed.get_yaxis_transform(),
            ha="right",
            va="bottom",
            fontsize=7,
            color="#dc2626" if is_main else "#64748b",
            alpha=0.9,
        )

    ax_speed.legend(loc="upper right", fontsize=8)

    

    # Panel 2: heart rate
    if show_hr_zones:
        add_hr_zone_bands(ax_hr, hr_max_bpm)

    if activity["heart_rate_bpm"].notna().any():
        ax_hr.plot(
            t_min,
            activity["heart_rate_bpm"],
            lw=0.9,
            alpha=0.85,
            label="heart_rate_bpm",
        )
        hr = activity["heart_rate_bpm"].dropna()
        lo = max(40, float(hr.quantile(0.01)) - 5)
        hi = min(220, float(hr.quantile(0.99)) + 5)
        if hi > lo:
            ax_hr.set_ylim(lo, hi)
    ax_hr.set_ylabel("HR (bpm)")
    ax_hr.legend(loc="upper right", fontsize=8)

    # Panel 3: offset
    offset = activity["offset_to_mainline_m"].clip(lower=0, upper=120)
    ax_offset.scatter(t_min, offset, s=5, alpha=0.28, label="offset_to_mainline_m")
    ax_offset.axhline(25, ls="--", lw=0.9, color="#dc2626", alpha=0.7, label="25m reference")
    ax_offset.axhline(50, ls="--", lw=0.8, color="#9333ea", alpha=0.6, label="50m reference")
    ax_offset.set_ylabel("Offset (m)")
    ax_offset.set_ylim(0, 120)
    ax_offset.legend(loc="upper right", fontsize=8)

    # Panel 4: usable_on_route
    onroute = activity["usable_on_route"].astype(int)
    ax_onroute.fill_between(t_min, 0, onroute, step="pre", alpha=0.35, label="usable_on_route")
    ax_onroute.set_ylim(-0.1, 1.1)
    ax_onroute.set_yticks([0, 1])
    ax_onroute.set_yticklabels(["off / excluded", "on-route"])
    ax_onroute.set_ylabel("IB3A2")
    ax_onroute.legend(loc="upper right", fontsize=8)

    # Panel 5: event lanes
    types = event_types_in_order(events)
    type_to_y = {t: i for i, t in enumerate(types)}
    ax_events.set_ylim(-0.8, max(len(types) - 0.2, 1.0))

    for _, row in events.iterrows():
        etype = str(row.get("event_type", ""))
        y = type_to_y.get(etype, 0)
        color = EVENT_COLOR.get(etype, "#334155")
        start = row.get("start_elapsed_sec", np.nan)
        end = row.get("end_elapsed_sec", np.nan)
        duration = row.get("duration_sec", np.nan)
        if not np.isfinite(start) or not np.isfinite(end):
            continue

        x0 = start / 60.0
        width = max((end - start) / 60.0, 0.12)

        ax_events.broken_barh(
            [(x0, width)],
            (y - 0.34, 0.68),
            facecolors=color,
            alpha=0.78,
        )

        label = ""
        if etype not in {"high_hr_recovery_stop", "short_pause"} or (np.isfinite(duration) and duration >= 90):
            label = f'{int(row.get("event_id", 0))}:{etype.replace("_", " ")}'
        elif width >= 0.55:
            label = str(int(row.get("event_id", 0)))

        if label:
            ax_events.text(
                x0 + width / 2,
                y,
                label,
                ha="center",
                va="center",
                fontsize=7,
                color="white",
                clip_on=True,
            )

    ax_events.set_yticks(list(type_to_y.values()))
    ax_events.set_yticklabels([t.replace("_", " ") for t in types])
    ax_events.grid(True, axis="x", alpha=0.22)
    ax_events.set_xlabel("Elapsed time (min)")
    ax_events.set_ylabel("IB3C events")

    fig.suptitle(
        f"Observed Behavior Timeline: {route_folder} {activity_id}",
        fontsize=15,
        y=0.985,
    )

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=180, bbox_inches="tight")
    plt.close(fig)


def write_summary(
    out_summary: Path,
    activity: pd.DataFrame,
    events: pd.DataFrame,
    activity_csv: Path,
    events_csv: Path,
    show_hr_zones: bool = False,
    estimated_hr_max_bpm: float = np.nan,
    age: float | None = None,
    sex: str = "unknown",
) -> None:
    lines = [
        "ib3d_observed_behavior_timeline_summary",
        f"activity_csv: {activity_csv}",
        f"events_csv: {events_csv}",
        f"activity_rows: {len(activity)}",
        f"event_rows: {len(events)}",

        f"show_hr_zones: {show_hr_zones}",
        f"estimated_hr_max_bpm: {estimated_hr_max_bpm if np.isfinite(estimated_hr_max_bpm) else ''}",
        f"age: {age if age is not None else ''}",
        f"sex: {sex}",

        f"route_axis_speed_raw_available_count: {int(activity['ib3d_forward_speed_mps_raw'].notna().sum())}",
        f"route_axis_speed_smooth_available_count: {int(activity['ib3d_forward_speed_mps_smooth'].notna().sum())}",
        f"gps_speed_raw_available_count: {int(activity['ib3d_gps_speed_mps_raw'].notna().sum())}",
        f"gps_speed_smooth_available_count: {int(activity['ib3d_gps_speed_mps_smooth'].notna().sum())}",

        f"elapsed_min: {activity['elapsed_sec'].min() / 60.0:.3f}",
        f"elapsed_max: {activity['elapsed_sec'].max() / 60.0:.3f}",
        "",
        "event_type_counts:",
        events["event_type"].value_counts(dropna=False).to_string() if not events.empty else "",
        "",
        "usable_on_route:",
        activity["usable_on_route"].value_counts(dropna=False).to_string(),
    ]

    if not events.empty:
        keep = [
            "event_id",
            "event_type",
            "event_subtype",
            "start_elapsed_sec",
            "end_elapsed_sec",
            "duration_sec",
            "start_route_dist_m",
            "end_route_dist_m",
            "max_offset_m",
            "max_hr_bpm",
            "rest_duration_tier",
            "recovery_level",
            "estimated_recovery_score",
            "recovery_interpretation",
        ]
        keep = [c for c in keep if c in events.columns]
        lines += [
            "",
            "events_preview:",
            events[keep].head(30).to_string(index=False),
        ]

    out_summary.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_html(
    out_html: Path,
    out_png: Path,
    activity: pd.DataFrame,
    events: pd.DataFrame,
    route_folder: str,
    activity_id: str,
) -> None:
    png_rel = html.escape(out_png.name)

    if not events.empty:
        keep = [
            "event_id",
            "event_type",
            "event_subtype",
            "start_elapsed_sec",
            "end_elapsed_sec",
            "duration_sec",
            "start_route_dist_m",
            "end_route_dist_m",
            "max_offset_m",
            "max_hr_bpm",
            "recovery_level",
            "recovery_interpretation",
        ]
        keep = [c for c in keep if c in events.columns]
        event_table = events[keep].to_html(index=False, escape=True)
    else:
        event_table = "<p>No events loaded.</p>"

    html_text = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8"/>
<title>Observed Behavior Timeline - {html.escape(route_folder)} {html.escape(activity_id)}</title>
<style>
body {{
  margin: 0;
  background: #e5e7eb;
  font-family: Arial, "Microsoft JhengHei", sans-serif;
  color: #111827;
}}
.wrap {{
  max-width: 1320px;
  margin: 0 auto;
  padding: 18px;
}}
.card {{
  background: white;
  border-radius: 10px;
  padding: 14px 16px;
  box-shadow: 0 8px 24px rgba(15,23,42,0.12);
  margin-bottom: 16px;
}}
img {{
  width: 100%;
  height: auto;
  display: block;
}}
table {{
  border-collapse: collapse;
  width: 100%;
  font-size: 12px;
}}
th, td {{
  border: 1px solid #cbd5e1;
  padding: 4px 6px;
  vertical-align: top;
}}
th {{
  background: #f1f5f9;
}}
code {{
  background: #f1f5f9;
  padding: 1px 4px;
  border-radius: 4px;
}}
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <h2>Observed Behavior Timeline</h2>
    <p><b>route_folder:</b> <code>{html.escape(route_folder)}</code></p>
    <p><b>activity_id:</b> <code>{html.escape(activity_id)}</code></p>
    <p>This figure uses elapsed time as the main axis. It is intended for observed behavior interpretation, not route-distance QA.</p>
  </div>
  <div class="card">
    <img src="{png_rel}" alt="Observed behavior timeline"/>
  </div>
  <div class="card">
    <h3>IB3C behavior events</h3>
    {event_table}
  </div>
</div>
</body>
</html>
"""
    out_html.write_text(html_text, encoding="utf-8")


def main() -> None:
    args = parse_args()

    activity_csv = resolve_activity_csv(args)
    events_csv = resolve_events_csv(args)

    activity = normalize_activity(
        read_csv_required(activity_csv, "IB3A2 labeled activity CSV"),
        args.speed_cap_mps,
    )
    events = normalize_events(read_csv_required(events_csv, "IB3C behavior events CSV"))

    out_dir = resolve_path(args.out_dir) / args.route_folder / args.activity_id
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = f"{args.route_folder}_{args.activity_id}_observed_behavior_timeline"
    out_png = out_dir / f"{stem}.png"
    out_html = out_dir / f"{stem}.html"
    out_summary = out_dir / f"{stem}_summary.txt"
    out_activity = out_dir / f"{stem}_activity_plot_data.csv"
    out_events = out_dir / f"{stem}_events_plot_data.csv"

    estimated_hr_max_bpm = estimate_hr_max_bpm(
        age=args.age,
        sex=args.sex,
        hr_max_bpm=args.hr_max_bpm,
    )

    plot_timeline(
        out_png,
        activity,
        events,
        args.route_folder,
        args.activity_id,
        show_hr_zones=args.show_hr_zones,
        hr_max_bpm=estimated_hr_max_bpm,
    )
    write_summary(
        out_summary,
        activity,
        events,
        activity_csv,
        events_csv,
        show_hr_zones=args.show_hr_zones,
        estimated_hr_max_bpm=estimated_hr_max_bpm,
        age=args.age,
        sex=args.sex,
    )
    write_html(out_html, out_png, activity, events, args.route_folder, args.activity_id)

    activity.to_csv(out_activity, index=False, encoding="utf-8-sig")
    events.to_csv(out_events, index=False, encoding="utf-8-sig")

    print("IB3D observed behavior timeline written")
    print(f"PNG: {out_png.resolve()}")
    print(f"HTML: {out_html.resolve()}")
    print(f"summary: {out_summary.resolve()}")
    print(f"activity plot data: {out_activity.resolve()}")
    print(f"events plot data: {out_events.resolve()}")
    print(f"activity rows: {len(activity)}")
    print(f"event rows: {len(events)}")
    print("event_type:")
    print(events["event_type"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()