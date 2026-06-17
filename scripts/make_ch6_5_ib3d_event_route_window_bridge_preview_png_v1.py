from __future__ import annotations

import re
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path("outputs/report_figures/ch6_5_ib3d_event_route_window_bridge_v1")
OUT_ALL = ROOT / "ib3d_event_route_window_bridge_preview_all.png"

KNOWN_EVENT_TYPES = [
    "high_hr_recovery_stop",
    "short_pause",
    "off_route_rest",
    "terminal_artifact",
]

EVENT_COLORS = {
    "high_hr_recovery_stop": "#d62728",
    "short_pause": "#ff7f0e",
    "off_route_rest": "#1f77b4",
    "terminal_artifact": "#7f7f7f",
    "any_event": "#9467bd",
}

STATUS_COLORS = {
    "ROUTE_WINDOW_OVERLAY_READY": "#2ca02c",
    "NO_ACTIVITY_POINTS_IN_ROUTE_WINDOW": "#c7c7c7",
    "REVIEW_REQUIRED": "#d62728",
}


def activity_id_from_path(path: Path) -> str:
    m = re.match(r"activity_(.+?)_ib3d_event_route_window_overlay\.csv$", path.name)
    return m.group(1) if m else path.stem


def find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lower_map = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    return None


def find_window_cols(df: pd.DataFrame) -> tuple[str, str]:
    start_col = find_col(df, [
        "route_distance_window_start_m",
        "route_window_start_m",
        "window_start_m",
        "start_route_dist_m",
    ])
    end_col = find_col(df, [
        "route_distance_window_end_m",
        "route_window_end_m",
        "window_end_m",
        "end_route_dist_m",
    ])
    if not start_col or not end_col:
        raise ValueError(f"Cannot find route window start/end columns. columns={list(df.columns)}")
    return start_col, end_col


def find_status_col(df: pd.DataFrame) -> str | None:
    return find_col(df, [
        "route_window_overlay_status",
        "overlay_status",
        "bridge_status",
        "status",
    ])


def build_event_counts(df: pd.DataFrame, start_col: str, end_col: str) -> pd.DataFrame:
    base = df[[start_col, end_col]].drop_duplicates().copy()
    base = base.sort_values([start_col, end_col]).reset_index(drop=True)

    for ev in KNOWN_EVENT_TYPES:
        base[ev] = 0

    # Case 1: one row per event-window with event_type column.
    event_type_col = find_col(df, ["event_type"])
    if event_type_col:
        grp = (
            df.groupby([start_col, end_col, event_type_col], dropna=False)
              .size()
              .reset_index(name="n")
        )
        for _, row in grp.iterrows():
            ev = str(row[event_type_col])
            if ev not in KNOWN_EVENT_TYPES:
                continue
            mask = (base[start_col] == row[start_col]) & (base[end_col] == row[end_col])
            base.loc[mask, ev] += int(row["n"])

    # Case 2: one row per window with event_types pipe-separated.
    event_types_col = find_col(df, ["event_types", "mapped_event_types", "overlay_event_types"])
    if event_types_col:
        for _, row in df.iterrows():
            evs = str(row.get(event_types_col, "") or "").split("|")
            for ev in evs:
                ev = ev.strip()
                if ev not in KNOWN_EVENT_TYPES:
                    continue
                mask = (base[start_col] == row[start_col]) & (base[end_col] == row[end_col])
                base.loc[mask, ev] += 1

    # Case 3: count columns already exist.
    for ev in KNOWN_EVENT_TYPES:
        candidates = [
            ev,
            f"{ev}_count",
            f"event_{ev}_count",
            f"{ev}_event_count",
            f"{ev}_window_count",
        ]
        col = find_col(df, candidates)
        if col and pd.api.types.is_numeric_dtype(df[col]):
            summed = df.groupby([start_col, end_col])[col].sum().reset_index()
            for _, row in summed.iterrows():
                mask = (base[start_col] == row[start_col]) & (base[end_col] == row[end_col])
                base.loc[mask, ev] += int(row[col])

    known_sum = base[KNOWN_EVENT_TYPES].sum(axis=1)

    # Fallback: generic event_count, if no known event type was found.
    if known_sum.sum() == 0:
        event_count_col = find_col(df, ["event_count", "mapped_event_count", "overlay_event_count"])
        if event_count_col and pd.api.types.is_numeric_dtype(df[event_count_col]):
            summed = df.groupby([start_col, end_col])[event_count_col].sum().reset_index()
            base["any_event"] = 0
            for _, row in summed.iterrows():
                mask = (base[start_col] == row[start_col]) & (base[end_col] == row[end_col])
                base.loc[mask, "any_event"] = int(row[event_count_col])
        else:
            base["any_event"] = 0

    return base


def make_activity_png(path: Path) -> tuple[str, Path]:
    activity_id = activity_id_from_path(path)
    df = pd.read_csv(path)
    start_col, end_col = find_window_cols(df)
    status_col = find_status_col(df)

    counts = build_event_counts(df, start_col, end_col)
    counts["mid_km"] = (counts[start_col].astype(float) + counts[end_col].astype(float)) / 2000.0
    width_km = max((counts[end_col].astype(float) - counts[start_col].astype(float)).median() / 1000.0 * 0.85, 0.02)

    event_cols = [c for c in KNOWN_EVENT_TYPES if c in counts.columns and counts[c].sum() > 0]
    if "any_event" in counts.columns and counts["any_event"].sum() > 0:
        event_cols.append("any_event")

    fig, axes = plt.subplots(
        2 if status_col else 1,
        1,
        figsize=(15, 5.5 if status_col else 4),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1]} if status_col else None,
    )
    if not isinstance(axes, (list, tuple)):
        axes = [axes]
    elif hasattr(axes, "ravel"):
        axes = list(axes.ravel())

    ax = axes[0]
    bottom = pd.Series([0] * len(counts), dtype=float)
    for ev in event_cols:
        ax.bar(
            counts["mid_km"],
            counts[ev],
            width=width_km,
            bottom=bottom,
            label=ev,
            color=EVENT_COLORS.get(ev),
            alpha=0.9,
        )
        bottom = bottom + counts[ev]

    ax.set_title(f"IB3D event route-window overlay preview — {activity_id}")
    ax.set_ylabel("event count")
    ax.grid(True, axis="y", alpha=0.3)
    if event_cols:
        ax.legend(loc="upper right", fontsize=9)
    else:
        ax.text(0.5, 0.5, "No event columns detected", transform=ax.transAxes, ha="center", va="center")

    if status_col:
        sdf = df[[start_col, end_col, status_col]].drop_duplicates().copy()
        sdf["mid_km"] = (sdf[start_col].astype(float) + sdf[end_col].astype(float)) / 2000.0
        ax2 = axes[1]
        for status, g in sdf.groupby(status_col):
            ax2.scatter(
                g["mid_km"],
                [0] * len(g),
                s=42,
                label=str(status),
                color=STATUS_COLORS.get(str(status), "#9467bd"),
            )
        ax2.set_yticks([])
        ax2.set_ylabel("status")
        ax2.grid(True, axis="x", alpha=0.3)
        ax2.legend(loc="upper right", fontsize=8)

    axes[-1].set_xlabel("standard route distance (km)")

    note = (
        "Preview only. Event intervals are bridged to route windows via reliable route-distance points. "
        "No ability score, rank, class, THCI, radar, final risk, or causal inference."
    )
    fig.text(0.01, 0.01, note, fontsize=9)

    out = ROOT / f"activity_{activity_id}_ib3d_event_route_window_overlay_preview.png"
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(out, dpi=180)
    plt.close(fig)
    return activity_id, out


def make_all_png(activity_outputs: list[tuple[str, Path]]) -> None:
    n = len(activity_outputs)
    if n == 0:
        return

    fig, axes = plt.subplots(n, 1, figsize=(15, max(3.2 * n, 4)), sharex=True)
    if n == 1:
        axes = [axes]

    for ax, (activity_id, path) in zip(axes, activity_outputs):
        df = pd.read_csv(ROOT / f"activity_{activity_id}_ib3d_event_route_window_overlay.csv")
        start_col, end_col = find_window_cols(df)
        counts = build_event_counts(df, start_col, end_col)
        counts["mid_km"] = (counts[start_col].astype(float) + counts[end_col].astype(float)) / 2000.0
        width_km = max((counts[end_col].astype(float) - counts[start_col].astype(float)).median() / 1000.0 * 0.85, 0.02)

        event_cols = [c for c in KNOWN_EVENT_TYPES if c in counts.columns and counts[c].sum() > 0]
        if "any_event" in counts.columns and counts["any_event"].sum() > 0:
            event_cols.append("any_event")

        bottom = pd.Series([0] * len(counts), dtype=float)
        for ev in event_cols:
            ax.bar(
                counts["mid_km"],
                counts[ev],
                width=width_km,
                bottom=bottom,
                label=ev,
                color=EVENT_COLORS.get(ev),
                alpha=0.9,
            )
            bottom = bottom + counts[ev]

        ax.set_title(activity_id, loc="left")
        ax.set_ylabel("events")
        ax.grid(True, axis="y", alpha=0.3)

    axes[0].legend(loc="upper right", fontsize=8)
    axes[-1].set_xlabel("standard route distance (km)")
    fig.suptitle("IB3D event route-window bridge preview — all rendered activities", y=0.995)

    fig.text(
        0.01,
        0.01,
        "Preview only. This figure checks event-to-route-window placement; it is not a score, rank, class, THCI, radar, final risk, or causal result.",
        fontsize=9,
    )
    fig.tight_layout(rect=[0, 0.04, 1, 0.97])
    fig.savefig(OUT_ALL, dpi=180)
    plt.close(fig)


def main() -> int:
    overlay_files = sorted(ROOT.glob("activity_*_ib3d_event_route_window_overlay.csv"))
    if not overlay_files:
        raise FileNotFoundError(f"No overlay CSV found in {ROOT}")

    outputs = []
    for path in overlay_files:
        activity_id, out = make_activity_png(path)
        outputs.append((activity_id, out))
        print(f"wrote: {out}")

    make_all_png(outputs)
    print(f"wrote: {OUT_ALL}")
    print("audit: PASS_IB3D_EVENT_ROUTE_WINDOW_BRIDGE_PREVIEW_PNG")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
