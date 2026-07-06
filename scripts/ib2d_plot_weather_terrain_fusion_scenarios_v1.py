from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.cm import ScalarMappable


PROJECT_ROOT = Path(r"D:\mountain_work\115_osm")
DEFAULT_CASE_ID = "taichung_guguan_butterfly_valley_waterfall_20260630"

# Figure 1 compatible hazard color scale.
# Low -> high: yellow -> orange -> red.
FIG1_HAZARD_CMAP = LinearSegmentedColormap.from_list(
    "fig1_upslope_hazard",
    ["#F5D76E", "#F28E2B", "#C9252D"],
)
FIG1_HAZARD_NORM = Normalize(vmin=0.70, vmax=0.85)

FUSION_ROOT = PROJECT_ROOT / "outputs" / "ib2d_weather_terrain_fusion_scenarios_v1"

ROUTE_PROFILE_CANDIDATES = [
    PROJECT_ROOT / "outputs" / "ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa",
    PROJECT_ROOT / "outputs" / "ib1e_route_profile_contour_window_terrain",
    PROJECT_ROOT / "outputs" / "ib1c_route_profile_semantics_v1_3b_contract_qa",
    PROJECT_ROOT / "outputs" / "ib1_route_profile_v1_3b_contract_qa",
]


def configure_cjk_font() -> None:
    candidates = [
        "Microsoft JhengHei",
        "Microsoft YaHei",
        "Noto Sans CJK TC",
        "Noto Sans TC",
        "SimHei",
        "Arial Unicode MS",
    ]
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in available:
            plt.rcParams["font.sans-serif"] = [name]
            break
    plt.rcParams["axes.unicode_minus"] = False


def boolish(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"true", "1", "yes", "y"}


def first_col(df: pd.DataFrame, names: list[str]) -> str | None:
    lower = {c.lower(): c for c in df.columns}
    for name in names:
        if name.lower() in lower:
            return lower[name.lower()]
    return None


def route_dist_col(df: pd.DataFrame) -> str | None:
    return first_col(
        df,
        [
            "route_dist_m",
            "route_distance_m",
            "distance_m",
            "dist_m",
            "gpx_dist_m",
            "cumdist_m",
            "station_m",
            "s_m",
            "m",
        ],
    )


def coordinate_cols(df: pd.DataFrame) -> tuple[str | None, str | None]:
    pairs = [
        ("metric_x", "metric_y"),
        ("map_x", "map_y"),
        ("route_x", "route_y"),
        ("x", "y"),
        ("easting", "northing"),
        ("utm_x", "utm_y"),
        ("lon", "lat"),
        ("longitude", "latitude"),
    ]
    lower = {c.lower(): c for c in df.columns}
    for x, y in pairs:
        if x.lower() in lower and y.lower() in lower:
            return lower[x.lower()], lower[y.lower()]
    return None, None


def read_fusion_table(case_id: str) -> tuple[pd.DataFrame, Path, dict[str, Any]]:
    out_dir = FUSION_ROOT / case_id
    csv_fp = out_dir / f"{case_id}_weather_terrain_fusion_segment_risk.csv"
    summary_fp = out_dir / f"{case_id}_weather_terrain_fusion_summary.json"

    if not csv_fp.exists():
        raise FileNotFoundError(f"Missing fusion segment CSV: {csv_fp}")

    df = pd.read_csv(csv_fp, encoding="utf-8-sig")

    numeric_cols = [
        "start_m",
        "end_m",
        "length_m",
        "static_hazard_score",
        "rain_sensitivity",
        "rain_factor",
        "effective_rain_factor",
        "weather_scale",
        "weather_adjusted_hazard_score",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values("start_m").reset_index(drop=True)

    summary: dict[str, Any] = {}
    if summary_fp.exists():
        summary = json.loads(summary_fp.read_text(encoding="utf-8"))

    return df, out_dir, summary


def find_route_profile_file(case_id: str) -> Path:
    exact_names = [
        f"{case_id}_route_profile_contour_window_terrain_enriched.csv",
        f"{case_id}_route_profile_semantic_enriched.csv",
        f"{case_id}_route_profile.csv",
    ]

    for root in ROUTE_PROFILE_CANDIDATES:
        case_dir = root / case_id
        for name in exact_names:
            fp = case_dir / name
            if fp.exists():
                return fp

    # Limited fallback search in known roots only.
    for root in ROUTE_PROFILE_CANDIDATES:
        if not root.exists():
            continue
        matches = list(root.rglob(f"{case_id}*route_profile*.csv"))
        if matches:
            return matches[0]

    raise FileNotFoundError(
        "Cannot find route profile CSV. Expected one of IB1 / IB1C / IB1E route profile outputs."
    )


def read_route_profile(case_id: str, route_len_m: float) -> tuple[pd.DataFrame, Path]:
    fp = find_route_profile_file(case_id)
    df = pd.read_csv(fp, encoding="utf-8-sig", low_memory=False)

    x_col, y_col = coordinate_cols(df)
    if x_col is None or y_col is None:
        raise ValueError(
            f"Cannot find coordinate columns in {fp}. "
            f"Columns={list(df.columns)[:80]}"
        )

    d_col = route_dist_col(df)

    out = pd.DataFrame(
        {
            "x": pd.to_numeric(df[x_col], errors="coerce"),
            "y": pd.to_numeric(df[y_col], errors="coerce"),
        }
    )

    if d_col:
        out["route_m"] = pd.to_numeric(df[d_col], errors="coerce")
    else:
        out["route_m"] = np.nan

    out = out.dropna(subset=["x", "y"]).reset_index(drop=True)

    if out.empty:
        raise ValueError(f"No valid route coordinate rows in {fp}")

    if out["route_m"].notna().sum() < max(3, len(out) // 2):
        xy = out[["x", "y"]].to_numpy(float)
        dxy = np.sqrt(((xy[1:] - xy[:-1]) ** 2).sum(axis=1))
        cum = np.r_[0.0, np.cumsum(dxy)]
        if cum[-1] > 0:
            cum = cum / cum[-1] * route_len_m
        out["route_m"] = cum

    out = out.dropna(subset=["route_m"]).sort_values("route_m").reset_index(drop=True)

    # Reduce duplicate points if present.
    out = out.drop_duplicates(subset=["route_m", "x", "y"]).reset_index(drop=True)

    return out, fp


def risk_threshold_lines(ax) -> None:
    thresholds = [
        (0.76, "elevated"),
        (0.82, "high"),
        (0.88, "avoid / review"),
    ]
    for x, label in thresholds:
        ax.axvline(x, linestyle="--", linewidth=0.8, alpha=0.8)
        ax.text(x + 0.003, 0.02, label, rotation=90, va="bottom", fontsize=8)


def segment_at_m(seg_df: pd.DataFrame, m: float) -> pd.Series:
    hit = seg_df[(seg_df["start_m"] <= m) & (m <= seg_df["end_m"])]
    if not hit.empty:
        return hit.iloc[0]

    idx = (seg_df["start_m"] - m).abs().idxmin()
    return seg_df.loc[idx]


def build_route_line_collection(
    route_df: pd.DataFrame,
    seg_df: pd.DataFrame,
    score_col: str,
) -> tuple[list[np.ndarray], list[float]]:
    pts = route_df[["x", "y"]].to_numpy(float)
    route_m = route_df["route_m"].to_numpy(float)

    segments: list[np.ndarray] = []
    values: list[float] = []

    for i in range(len(pts) - 1):
        mid_m = float((route_m[i] + route_m[i + 1]) / 2)
        seg = segment_at_m(seg_df, mid_m)
        value = float(seg[score_col])

        segments.append(np.array([pts[i], pts[i + 1]]))
        values.append(value)

    return segments, values


def plot_route_map(
    ax,
    route_df: pd.DataFrame,
    seg_df: pd.DataFrame,
    score_col: str,
    title: str,
    norm: Normalize,
):
    cmap = FIG1_HAZARD_CMAP if "FIG1_HAZARD_CMAP" in globals() else plt.get_cmap("YlOrRd")

    line_segments, values = build_route_line_collection(route_df, seg_df, score_col)

    # Background line for readability.
    bg = LineCollection(line_segments, linewidths=8.5, colors="black", alpha=0.22)
    ax.add_collection(bg)

    lc = LineCollection(
        line_segments,
        cmap=cmap,
        norm=norm,
        linewidths=6.0,
        alpha=0.98,
    )
    lc.set_array(np.array(values))
    ax.add_collection(lc)

    x_range = float(route_df["x"].max() - route_df["x"].min())
    y_range = float(route_df["y"].max() - route_df["y"].min())
    if not np.isfinite(x_range) or x_range <= 0:
        x_range = 1.0
    if not np.isfinite(y_range) or y_range <= 0:
        y_range = 1.0

    # Offset by data-range ratio, so it works for lon/lat and projected coordinates.
    label_offsets_frac = {
        "S01": (-0.040,  0.060),
        "S02": (-0.015,  0.070),
        "S03": ( 0.032,  0.085),
        "S04": ( 0.020, -0.065),
        "S05": (-0.040, -0.050),
    }

    label_xy = []

    def offset_for(seg_id: str) -> tuple[float, float]:
        fx, fy = label_offsets_frac.get(seg_id, (0.0, 0.055))
        return fx * x_range, fy * y_range

    # Hotspot overlay and S03 label.
    hotspot_rows = seg_df[seg_df["overlap_hotspot"].map(boolish)]
    for _, h in hotspot_rows.iterrows():
        hs = float(h["start_m"])
        he = float(h["end_m"])
        sub = route_df[(route_df["route_m"] >= hs) & (route_df["route_m"] <= he)]
        if len(sub) >= 2:
            pts = sub[["x", "y"]].to_numpy(float)
            hs_segments = [np.array([pts[i], pts[i + 1]]) for i in range(len(pts) - 1)]

            # Do not cover the red risk color. This is only a soft review emphasis.
            hot = LineCollection(hs_segments, linewidths=8.5, colors="#6E0015", alpha=0.18)
            ax.add_collection(hot)

            mid_m = (hs + he) / 2
            mid_idx = (route_df["route_m"] - mid_m).abs().idxmin()
            mx = float(route_df.loc[mid_idx, "x"])
            my = float(route_df.loc[mid_idx, "y"])

            dx, dy = offset_for("S03")
            lx = mx + dx
            ly = my + dy
            label_xy.append((lx, ly))

            ax.annotate(
                "S03\n\u96e8\u5f8c\u9ad8\u654f\u611f",
                xy=(mx, my),
                xytext=(lx, ly),
                textcoords="data",
                ha="center",
                va="center",
                fontsize=9,
                bbox=dict(boxstyle="round,pad=0.25", facecolor="white", alpha=0.88, edgecolor="black"),
                arrowprops=dict(
                    arrowstyle="-",
                    color="0.35",
                    lw=0.8,
                    shrinkA=4,
                    shrinkB=4,
                ),
                zorder=12,
            )

    # Segment labels. S01/S05 and S02/S04 are intentionally offset to avoid overlap.
    for _, s in seg_df.iterrows():
        if boolish(s.get("overlap_hotspot", False)):
            continue

        seg_id = str(s["segment_id"])
        mid_m = (float(s["start_m"]) + float(s["end_m"])) / 2
        idx = (route_df["route_m"] - mid_m).abs().idxmin()
        x = float(route_df.loc[idx, "x"])
        y = float(route_df.loc[idx, "y"])

        dx, dy = offset_for(seg_id)
        lx = x + dx
        ly = y + dy
        label_xy.append((lx, ly))

        ax.annotate(
            seg_id,
            xy=(x, y),
            xytext=(lx, ly),
            textcoords="data",
            fontsize=8,
            ha="center",
            va="center",
            bbox=dict(boxstyle="round,pad=0.15", facecolor="white", alpha=0.78, edgecolor="0.45"),
            arrowprops=dict(
                arrowstyle="-",
                color="0.40",
                lw=0.65,
                shrinkA=3,
                shrinkB=3,
            ),
            zorder=11,
        )

    # Start / end markers.
    ax.scatter(route_df["x"].iloc[0], route_df["y"].iloc[0], marker="^", s=60, label="start", zorder=13)
    ax.scatter(route_df["x"].iloc[-1], route_df["y"].iloc[-1], marker="s", s=45, label="end", zorder=13)

    # Include annotation positions in viewport so labels do not get clipped.
    xs = route_df["x"].astype(float).tolist() + [p[0] for p in label_xy]
    ys = route_df["y"].astype(float).tolist() + [p[1] for p in label_xy]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    pad_x = max((maxx - minx) * 0.035, x_range * 0.02)
    pad_y = max((maxy - miny) * 0.050, y_range * 0.03)

    ax.set_xlim(minx - pad_x, maxx + pad_x)
    ax.set_ylim(miny - pad_y, maxy + pad_y)

    ax.set_aspect("equal", adjustable="datalim")
    ax.set_title(title)
    ax.set_xlabel("\u8def\u7dda\u5ea7\u6a19 X\uff08\u7d93\u5ea6\u6216\u6295\u5f71\u5ea7\u6a19\uff09")
    ax.set_ylabel("\u8def\u7dda\u5ea7\u6a19 Y\uff08\u7def\u5ea6\u6216\u6295\u5f71\u5ea7\u6a19\uff09")
    try:
        ax.ticklabel_format(useOffset=False, style="plain", axis="both")
    except Exception:
        pass
    ax.grid(linewidth=0.4, alpha=0.35)
    ax.legend(loc="best", fontsize=8)

    return lc


def plot_route_strip(ax, df: pd.DataFrame, norm: Normalize) -> None:
    # Force the strip to use exactly the same visual language as the map panel.
    cmap = FIG1_HAZARD_CMAP if "FIG1_HAZARD_CMAP" in globals() else plt.get_cmap("YlOrRd")
    norm = FIG1_HAZARD_NORM if "FIG1_HAZARD_NORM" in globals() else norm

    for _, r in df.iterrows():
        start_km = float(r["start_m"]) / 1000.0
        end_km = float(r["end_m"]) / 1000.0
        mid = (start_km + end_km) / 2.0

        static_score = float(r["static_hazard_score"])
        weather_score = float(r["weather_adjusted_hazard_score"])

        static_color = cmap(norm(static_score))
        weather_color = cmap(norm(weather_score))

        # Static risk row.
        ax.plot(
            [start_km, end_km],
            [1.0, 1.0],
            linewidth=16,
            solid_capstyle="butt",
            color=static_color,
            alpha=0.98,
            zorder=2,
        )

        # Weather-adjusted row. If score exceeds the Fig.1 colorbar maximum,
        # add a subtle dark-red underlay to show that it is beyond the saturated red.
        if weather_score >= 0.85:
            ax.plot(
                [start_km, end_km],
                [0.45, 0.45],
                linewidth=20,
                solid_capstyle="butt",
                color="#6E0015",
                alpha=0.20,
                zorder=1,
            )

        ax.plot(
            [start_km, end_km],
            [0.45, 0.45],
            linewidth=16,
            solid_capstyle="butt",
            color=weather_color,
            alpha=0.98,
            zorder=2,
        )

        # Segment ID.
        ax.text(mid, 1.18, r["segment_id"], ha="center", va="bottom", fontsize=9)

        # Add values so saturated-red segments remain distinguishable.
        ax.text(
            mid,
            1.0,
            f"{static_score:.3f}",
            ha="center",
            va="center",
            fontsize=7.2,
            color="black",
            bbox=dict(boxstyle="round,pad=0.08", fc="white", ec="none", alpha=0.62),
            zorder=4,
        )
        ax.text(
            mid,
            0.45,
            f"{weather_score:.3f}",
            ha="center",
            va="center",
            fontsize=7.2,
            color="black",
            bbox=dict(boxstyle="round,pad=0.08", fc="white", ec="none", alpha=0.62),
            zorder=4,
        )

        if boolish(r.get("overlap_hotspot", False)):
            # Review zone only. Keep it pale so it does not change perceived risk color.
            ax.axvspan(
                start_km,
                end_km,
                facecolor="#C9252D",
                edgecolor="#6E0015",
                alpha=0.055,
                hatch="//",
                zorder=0,
            )
            ax.text(
                mid,
                0.02,
                "\u9ad8\u5206\u8907\u6838\u5340\n\u96e8\u6c34\u532f\u6d41\u654f\u611f",
                ha="center",
                va="bottom",
                fontsize=8,
            )

    ax.set_yticks([1.0, 0.45])
    ax.set_yticklabels(["\u5e73\u5e38\u98a8\u96aa", "\u96e8\u5f8c\u4fee\u6b63"])
    ax.set_xlabel("GPX \u8def\u7dda\u91cc\u7a0b km")
    ax.set_title("\u6cbf\u7dda\u98a8\u96aa\u5e36\uff1a\u5e73\u5e38 vs \u96e8\u5f8c\u4fee\u6b63\uff08\u540c\u4e0a\u5716\u8272\u968e\uff09")
    ax.set_ylim(-0.12, 1.45)
    ax.grid(axis="x", linewidth=0.5, alpha=0.4)

def plot_weather_delta(ax, df: pd.DataFrame) -> None:
    labels = [f"{r.segment_id}" for r in df.itertuples()]
    delta = df["weather_adjusted_hazard_score"] - df["static_hazard_score"]

    ax.barh(labels, delta, color="#6A51A3")
    ax.invert_yaxis()
    ax.set_xlabel("雨後增量")
    ax.set_title("天候造成的分段增量")
    ax.grid(axis="x", linewidth=0.5, alpha=0.35)

    for i, v in enumerate(delta):
        ax.text(v + 0.002, i, f"+{v:.3f}", va="center", fontsize=8)


def as_tst_label(value: Any) -> str:
    if not value:
        return "unknown"
    try:
        ts = pd.to_datetime(value)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        ts = ts.tz_convert("Asia/Taipei")
        return ts.strftime("%Y-%m-%d %H:%M TST")
    except Exception:
        return str(value)


def weather_summary_text(summary: dict[str, Any], seg_df: pd.DataFrame) -> str:
    wm = summary.get("weather_metrics", {})
    scenario = summary.get("scenario", "unknown")
    as_of = as_tst_label(summary.get("as_of") or wm.get("as_of"))

    s03 = seg_df[seg_df["overlap_hotspot"].map(boolish)]
    if not s03.empty:
        row = s03.iloc[0]
        s03_text = (
            f"S03 \u9ad8\u5206\u8907\u6838\u5340: {row['start_m']/1000:.2f}-{row['end_m']/1000:.2f} km\n"
            f"\u5e73\u5e38 -> \u96e8\u5f8c: {row['static_hazard_score']:.3f} -> {row['weather_adjusted_hazard_score']:.3f}\n"
            f"\u5224\u5b9a: {row['weather_adjusted_label']}"
        )
    else:
        s03_text = "S03 hotspot: not found"

    return (
        "\u5929\u5019\u60c5\u5883\u6458\u8981\n"
        "----------------\n"
        f"\u5206\u6790\u6642\u9593: {as_of}\n"
        f"Scenario: {scenario}\n\n"
        "\u964d\u96e8\u8207\u6fd5\u5ea6\n"
        f"1h: {float(wm.get('p1h_mm', 0) or 0):.1f} mm\n"
        f"3h: {float(wm.get('p3h_mm', 0) or 0):.1f} mm\n"
        f"24h: {float(wm.get('p24h_mm', 0) or 0):.1f} mm\n"
        f"72h: {float(wm.get('p72h_mm', 0) or 0):.1f} mm\n"
        f"RH>=90% / 24h: {wm.get('rh_ge_90h_24h', 'NA')} h\n"
        f"RH>=90% / 72h: {wm.get('rh_ge_90h_72h', 'NA')} h\n\n"
        f"{s03_text}\n\n"
        "\u91cd\u9ede\u5224\u8b80\n"
        "\u8fd1\u671f\u7d2f\u7a4d\u96e8\u91cf\u504f\u9ad8\uff0c\u96d6\u975e\u5373\u6642\u5927\u96e8\uff0c\n"
        "\u4f46\u6703\u653e\u5927\u6eaa\u8c37\u3001\u532f\u6d41\u8207\u4e0a\u65b9\u5761\u9762\n"
        "\u654f\u611f\u6bb5\u4e4b\u96e8\u5f8c\u98a8\u96aa\u3002"
    )

def plot_segment_compare(df: pd.DataFrame, out_dir: Path, case_id: str) -> Path:
    fig_fp = out_dir / f"{case_id}_weather_terrain_fusion_segment_compare.png"

    labels = []
    for _, r in df.iterrows():
        labels.append(
            f"{r['segment_id']}  {r['start_m'] / 1000:.2f}–{r['end_m'] / 1000:.2f} km\n{r['segment_name']}"
        )

    y = list(range(len(df)))
    bar_h = 0.36

    fig, ax = plt.subplots(figsize=(12, 6.5))

    ax.barh(
        [v + bar_h / 2 for v in y],
        df["static_hazard_score"],
        height=bar_h,
        label="平常風險 static hazard",
    )
    ax.barh(
        [v - bar_h / 2 for v in y],
        df["weather_adjusted_hazard_score"],
        height=bar_h,
        label="雨後修正 weather-adjusted",
    )

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlim(0.65, 1.0)
    ax.set_xlabel("風險分數 risk score")
    ax.set_title("蝴蝶谷瀑布路線：平常風險 vs 雨後修正風險")
    ax.grid(axis="x", linewidth=0.5, alpha=0.4)
    ax.legend(loc="lower right")

    risk_threshold_lines(ax)

    for i, r in df.iterrows():
        ax.text(
            r["weather_adjusted_hazard_score"] + 0.004,
            i - bar_h / 2,
            f"{r['weather_adjusted_hazard_score']:.3f}",
            va="center",
            fontsize=8,
        )

    fig.tight_layout()
    fig.savefig(fig_fp, dpi=220)
    plt.close(fig)
    return fig_fp


def plot_route_strip_standalone(df: pd.DataFrame, out_dir: Path, case_id: str, norm: Normalize) -> Path:
    fig_fp = out_dir / f"{case_id}_weather_terrain_fusion_route_strip.png"

    fig, ax = plt.subplots(figsize=(12, 3.8))
    plot_route_strip(ax, df, norm)

    cmap = FIG1_HAZARD_CMAP
    sm = ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, orientation="horizontal", pad=0.25)
    cbar.set_label("風險分數 risk score")

    fig.tight_layout()
    fig.savefig(fig_fp, dpi=220)
    plt.close(fig)
    return fig_fp


def plot_weather_adjusted_route_panel(
    df: pd.DataFrame,
    route_df: pd.DataFrame,
    summary: dict[str, Any],
    out_dir: Path,
    case_id: str,
) -> Path:
    fig_fp = out_dir / f"{case_id}_weather_adjusted_route_map_panel.png"

    all_scores = pd.concat(
        [
            df["static_hazard_score"],
            df["weather_adjusted_hazard_score"],
        ]
    )
    norm = FIG1_HAZARD_NORM

    fig = plt.figure(figsize=(17, 10))
    gs = fig.add_gridspec(
        2,
        3,
        width_ratios=[1.35, 1.35, 1.0],
        height_ratios=[1.45, 0.95],
        wspace=0.36,
        hspace=0.46,
    )

    ax_map = fig.add_subplot(gs[0, 0:2])
    ax_info = fig.add_subplot(gs[0, 2])
    ax_strip = fig.add_subplot(gs[1, 0:2])
    ax_delta = fig.add_subplot(gs[1, 2])

    lc = plot_route_map(
        ax=ax_map,
        route_df=route_df,
        seg_df=df,
        score_col="weather_adjusted_hazard_score",
        title="蝴蝶谷瀑布路線：雨後修正風險空間分布",
        norm=norm,
    )

    cbar = fig.colorbar(lc, ax=ax_map, orientation="vertical", fraction=0.035, pad=0.02)
    cbar.set_label("雨後修正風險分數")

    ax_info.axis("off")
    ax_info.text(
        0.0,
        1.0,
        weather_summary_text(summary, df),
        ha="left",
        va="top",
        fontsize=9,
        linespacing=1.28,
        bbox=dict(boxstyle="round,pad=0.45", facecolor="white", edgecolor="0.75", alpha=0.95),
    )

    plot_route_strip(ax_strip, df, norm)
    plot_weather_delta(ax_delta, df)

    fig.suptitle(
        "蝴蝶谷瀑布路線：降雨情境下的天氣 × 地形融合風險分析",
        fontsize=17,
        y=0.98,
    )

    fig.savefig(fig_fp, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return fig_fp


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plot IB2D weather-terrain fusion scenario figures."
    )
    parser.add_argument("--case-id", default=DEFAULT_CASE_ID)
    args = parser.parse_args()

    configure_cjk_font()

    df, out_dir, summary = read_fusion_table(args.case_id)
    route_len_m = float(df["end_m"].max())
    route_df, route_fp = read_route_profile(args.case_id, route_len_m=route_len_m)

    all_scores = pd.concat(
        [
            df["static_hazard_score"],
            df["weather_adjusted_hazard_score"],
        ]
    )
    norm = FIG1_HAZARD_NORM

    fig1 = plot_segment_compare(df, out_dir, args.case_id)
    fig2 = plot_route_strip_standalone(df, out_dir, args.case_id, norm)
    fig3 = plot_weather_adjusted_route_panel(df, route_df, summary, out_dir, args.case_id)

    print("DONE")
    print("route_profile_used:", route_fp)
    print("segment_compare_png:", fig1)
    print("route_strip_png:", fig2)
    print("weather_adjusted_route_map_panel_png:", fig3)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
