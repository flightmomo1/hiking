#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build Chapter 6.7 HR lifecycle and recovery profile v2 evidence outputs.

This script analyzes full activity time-series heart-rate behavior when the
source CSVs contain elapsed time, heart rate, speed, and route-distance fields.
It produces descriptive evidence only: HR lifecycle, recovery events after
pause/low-speed segments, route-load HR response, and phase-level recovery
changes. It does NOT create ability scores, ability ranks/classes, route
suitability scores, THCI/radar scores, or final hiking-risk scores.
"""

from __future__ import annotations

import argparse
import html
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib
import matplotlib.font_manager
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DEFAULT_ROOT = r"D:\mountain_work\115_osm"
DEFAULT_OUTPUT_ROOT = "outputs/report_figures/ch6_7_hr_lifecycle_recovery_profile_v2"
DEFAULT_ROUTE_LOAD_WINDOWS = (
    "outputs/report_figures/ch6_5_route_load_context_index_v1/"
    "route_load_context_windows_v1.csv"
)
DEFAULT_PLANNING_WINDOWS = (
    "outputs/report_figures/ch6_7_planning_context_fusion_v1_1/"
    "planning_context_route_windows_v1_1.csv"
)
DEFAULT_GLOBS = [
    "outputs/ib3a2_on_route_activity_filter_v4b_after_forced_route/qixing_lengshuikeng/*_mapmatched_activity_labeled.csv",
    "outputs/**/qixing_lengshuikeng_*_mapmatched_activity_labeled.csv",
    "outputs/**/qixing_lengshuikeng_*activity*.csv",
]

FORBIDDEN_OUTPUT_COLUMNS = {
    "ability_score",
    "ability_rank",
    "ability_class",
    "thci_score",
    "radar_score",
    "final_hiking_risk_score",
    "route_suitability_score",
    "personal_fitness_score",
    "cardiopulmonary_fitness_score",
}

BOUNDARY = (
    "Descriptive HR lifecycle and recovery profile only. Heart-rate level, "
    "route-load response, recovery slope, fatigue drift, weather/event context, "
    "and movement behavior are descriptive evidence. This output is not a "
    "cardiopulmonary diagnosis, not ability scoring, not route suitability scoring, "
    "not THCI/radar scoring, and not a final hiking risk assessment."
)

HR_ALIASES = [
    "heart_rate_bpm", "heart_rate", "hr_bpm", "hr", "heartrate", "heartRate",
]
TIME_ALIASES = [
    "elapsed_sec", "timestamp_s", "time_s", "seconds", "sec", "elapsed_time_sec",
]
SPEED_ALIASES = [
    "speed_mps", "speed", "speed_ms", "speed_m_s", "activity_speed_mps",
]
ROUTE_DISTANCE_ALIASES = [
    "route_distance_m", "route_dist_m", "distance_on_route_m", "dist_on_route_m",
    "matched_route_distance_m", "reliable_route_distance_m", "route_m", "dist_m",
]
ELEVATION_ALIASES = ["elevation_m", "altitude_m", "ele", "alt", "enhanced_altitude"]
LAT_ALIASES = ["lat", "latitude", "position_lat"]
LON_ALIASES = ["lon", "lng", "longitude", "position_long"]

LEVEL_ORDER = [
    "ROUTINE_PLANNING_CONTEXT",
    "REVIEW_FOR_CONSERVATIVE_PLANNING",
    "CONSERVATIVE_PLANNING_RECOMMENDED",
    "TURNAROUND_CONDITION_REVIEW_RECOMMENDED",
]
HIGH_LOAD_BANDS = {"HIGH_ROUTE_LOAD_CONTEXT", "VERY_HIGH_ROUTE_LOAD_CONTEXT"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=DEFAULT_ROOT)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--activity-glob", action="append", default=[])
    parser.add_argument("--route-load-windows", default=DEFAULT_ROUTE_LOAD_WINDOWS)
    parser.add_argument("--planning-windows", default=DEFAULT_PLANNING_WINDOWS)
    parser.add_argument("--pause-speed-threshold-mps", type=float, default=0.30)
    parser.add_argument("--pause-min-duration-sec", type=float, default=30.0)
    parser.add_argument("--pre-pause-peak-window-sec", type=float, default=60.0)
    parser.add_argument("--recovery-horizons-sec", default="30,60,120")
    parser.add_argument("--representative-activities", default="37_1,48_1,33_1")
    return parser.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    p = Path(value)
    return p if p.is_absolute() else root / p


def setup_matplotlib_font() -> None:
    preferred = ["Microsoft JhengHei", "Noto Sans CJK TC", "Noto Sans TC", "SimHei", "Arial Unicode MS"]
    available = {font.name for font in matplotlib.font_manager.fontManager.ttflist}
    for font in preferred:
        if font in available:
            plt.rcParams["font.family"] = font
            break
    plt.rcParams["axes.unicode_minus"] = False


def read_csv(path: Path, **kwargs) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)

    if path.stat().st_size == 0:
        raise pd.errors.EmptyDataError(f"Empty CSV file: {path}")

    try:
        df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False, **kwargs)
    except pd.errors.EmptyDataError as exc:
        raise pd.errors.EmptyDataError(f"No columns to parse from file: {path}") from exc

    df.columns = [str(c).strip() for c in df.columns]
    return df


def numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def first_existing(columns: Iterable[str], aliases: list[str]) -> str | None:
    cols = list(columns)
    lower_map = {c.lower(): c for c in cols}
    for a in aliases:
        if a in cols:
            return a
        if a.lower() in lower_map:
            return lower_map[a.lower()]
    return None


def split_flags(value: object) -> list[str]:
    if pd.isna(value):
        return []
    text = str(value).strip()
    if not text or text.upper() == "NONE":
        return []
    return [part.strip() for part in text.split("|") if part.strip()]


def pipe_flags(values: Iterable[object]) -> str:
    out: list[str] = []
    for value in values:
        for flag in split_flags(value):
            if flag not in out:
                out.append(flag)
    return "|".join(out) if out else "NONE"


def mode_text(series: pd.Series) -> str:
    clean = series.dropna().astype(str)
    clean = clean[clean.str.strip().ne("")]
    if clean.empty:
        return ""
    return str(clean.mode().iloc[0])


def parse_activity_id(path: Path, df: pd.DataFrame | None = None) -> str:
    if df is not None and "activity_id_short" in df.columns and df["activity_id_short"].notna().any():
        return str(df["activity_id_short"].dropna().astype(str).iloc[0])
    text = path.stem
    patterns = [r"qixing_lengshuikeng_(\d+_\d+)", r"activity_(\d+_\d+)", r"(\d+_\d+)"]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1)
    return text


def discover_activity_files(root: Path, globs: list[str]) -> list[Path]:
    patterns = globs if globs else DEFAULT_GLOBS
    files: list[Path] = []
    for pat in patterns:
        for p in root.glob(pat):
            if p.is_file() and p.suffix.lower() == ".csv" and p not in files:
                files.append(p)
    return sorted(files)


def standardize_activity_df(path: Path) -> tuple[str, pd.DataFrame, dict[str, str], list[str]]:
    raw = read_csv(path)
    warnings: list[str] = []
    activity_id = parse_activity_id(path, raw)
    cols = raw.columns
    time_col = first_existing(cols, TIME_ALIASES)
    hr_col = first_existing(cols, HR_ALIASES)
    speed_col = first_existing(cols, SPEED_ALIASES)
    route_col = first_existing(cols, ROUTE_DISTANCE_ALIASES)
    elev_col = first_existing(cols, ELEVATION_ALIASES)
    lat_col = first_existing(cols, LAT_ALIASES)
    lon_col = first_existing(cols, LON_ALIASES)

    if time_col is None:
        warnings.append("TIME_COLUMN_MISSING")
    if hr_col is None:
        warnings.append("HEART_RATE_COLUMN_MISSING")
    if speed_col is None:
        warnings.append("SPEED_COLUMN_MISSING")
    if route_col is None:
        warnings.append("ROUTE_DISTANCE_COLUMN_MISSING")

    df = pd.DataFrame(index=raw.index)
    df["activity_id_short"] = activity_id
    df["source_file"] = str(path)
    df["elapsed_sec"] = numeric(raw[time_col]) if time_col else np.arange(len(raw), dtype=float)
    df["heart_rate_bpm"] = numeric(raw[hr_col]) if hr_col else np.nan
    df["speed_mps"] = numeric(raw[speed_col]) if speed_col else np.nan
    df["route_distance_m"] = numeric(raw[route_col]) if route_col else np.nan
    df["elevation_m"] = numeric(raw[elev_col]) if elev_col else np.nan
    df["lat"] = numeric(raw[lat_col]) if lat_col else np.nan
    df["lon"] = numeric(raw[lon_col]) if lon_col else np.nan

    df = df.sort_values("elapsed_sec").drop_duplicates("elapsed_sec", keep="first").reset_index(drop=True)
    # Basic HR plausibility filter; do not impute missing values.
    df.loc[~df["heart_rate_bpm"].between(35, 230), "heart_rate_bpm"] = np.nan
    if df["elapsed_sec"].isna().all():
        df["elapsed_sec"] = np.arange(len(df), dtype=float)
    mapping = {
        "time_col": time_col or "",
        "hr_col": hr_col or "",
        "speed_col": speed_col or "",
        "route_distance_col": route_col or "",
        "elevation_col": elev_col or "",
    }
    return activity_id, df, mapping, warnings


def load_route_context(route_load_path: Path, planning_path: Path) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    if route_load_path.exists():
        rl = read_csv(route_load_path)
        keep = [
            "activity_id_short", "route_distance_window_start_m", "route_distance_window_end_m",
            "route_load_context_index_0_100", "route_load_context_band",
        ]
        parts.append(rl[[c for c in keep if c in rl.columns]].copy())
    if planning_path.exists():
        pl = read_csv(planning_path)
        keep = [
            "activity_id_short", "route_distance_window_start_m", "route_distance_window_end_m",
            "planning_caution_level",
        ]
        parts.append(pl[[c for c in keep if c in pl.columns]].copy())
    if not parts:
        return pd.DataFrame()
    base = parts[0]
    for extra in parts[1:]:
        keys = [c for c in ["activity_id_short", "route_distance_window_start_m", "route_distance_window_end_m"] if c in base.columns and c in extra.columns]
        if len(keys) == 3:
            base = base.merge(extra, on=keys, how="left")
    return base


def attach_context(df: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if context.empty or out["route_distance_m"].isna().all():
        out["route_distance_window_start_m"] = np.nan
        out["route_distance_window_end_m"] = np.nan
        out["route_load_context_band"] = pd.NA
        out["route_load_context_index_0_100"] = np.nan
        out["planning_caution_level"] = pd.NA
        return out
    out["route_distance_window_start_m"] = np.floor(out["route_distance_m"] / 50.0) * 50.0
    out["route_distance_window_end_m"] = out["route_distance_window_start_m"] + 50.0
    ctx = context.copy()
    for c in ["route_distance_window_start_m", "route_distance_window_end_m"]:
        ctx[c] = numeric(ctx[c]).astype(float)
    keys = ["activity_id_short", "route_distance_window_start_m", "route_distance_window_end_m"]
    return out.merge(ctx, on=keys, how="left")


def activity_phase(elapsed: pd.Series) -> pd.Series:
    valid = numeric(elapsed)
    start = valid.min()
    end = valid.max()
    if pd.isna(start) or pd.isna(end) or end <= start:
        return pd.Series(["unknown"] * len(elapsed), index=elapsed.index)
    frac = (valid - start) / (end - start)
    return pd.cut(frac, bins=[-0.01, 1/3, 2/3, 1.01], labels=["early", "middle", "late"]).astype(str)


def nearest_value_at(df: pd.DataFrame, target_sec: float, col: str) -> float:
    sub = df[["elapsed_sec", col]].dropna()
    if sub.empty:
        return np.nan
    idx = (sub["elapsed_sec"] - target_sec).abs().idxmin()
    return float(sub.loc[idx, col])


def time_to_drop(df: pd.DataFrame, start_sec: float, baseline_hr: float, drop_bpm: float, max_sec: float) -> float:
    if pd.isna(baseline_hr):
        return np.nan
    sub = df[(df["elapsed_sec"] >= start_sec) & (df["elapsed_sec"] <= start_sec + max_sec)].copy()
    sub = sub[sub["heart_rate_bpm"].notna()]
    if sub.empty:
        return np.nan
    hit = sub[sub["heart_rate_bpm"] <= baseline_hr - drop_bpm]
    if hit.empty:
        return np.nan
    return float(hit["elapsed_sec"].iloc[0] - start_sec)


def detect_pause_segments(df: pd.DataFrame, speed_threshold: float, min_duration: float) -> pd.DataFrame:
    if df["speed_mps"].isna().all():
        return pd.DataFrame()
    tmp = df[["elapsed_sec", "speed_mps", "route_distance_m", "heart_rate_bpm"]].copy()
    tmp["is_pause"] = tmp["speed_mps"].le(speed_threshold)
    tmp["group"] = (tmp["is_pause"] != tmp["is_pause"].shift()).cumsum()
    rows = []
    for _, g in tmp[tmp["is_pause"]].groupby("group"):
        start = float(g["elapsed_sec"].min())
        end = float(g["elapsed_sec"].max())
        duration = end - start
        if duration >= min_duration:
            rows.append({
                "pause_start_sec": start,
                "pause_end_sec": end,
                "pause_duration_sec": duration,
                "pause_start_route_distance_m": numeric(g["route_distance_m"]).dropna().iloc[0] if g["route_distance_m"].notna().any() else np.nan,
                "pause_end_route_distance_m": numeric(g["route_distance_m"]).dropna().iloc[-1] if g["route_distance_m"].notna().any() else np.nan,
                "lowest_hr_during_pause": numeric(g["heart_rate_bpm"]).min(),
                "hr_median_during_pause": numeric(g["heart_rate_bpm"]).median(),
            })
    return pd.DataFrame(rows)


def compute_extremes(activity_id: str, df: pd.DataFrame) -> pd.DataFrame:
    rows = []

    if "heart_rate_bpm" not in df.columns:
        return pd.DataFrame()

    hr = numeric(df["heart_rate_bpm"])

    # Important: do not call idxmin/idxmax on an all-NA HR series.
    # HR missing is not interpreted as low effort; this activity simply has no HR extremes.
    if hr.notna().sum() == 0:
        return pd.DataFrame()

    for kind, idx in [("min", hr.idxmin()), ("max", hr.idxmax())]:
        if pd.isna(idx):
            continue
        row = df.loc[idx]
        rows.append({
            "activity_id_short": activity_id,
            "extreme_type": f"hr_{kind}",
            "heart_rate_bpm": row.get("heart_rate_bpm"),
            "elapsed_sec": row.get("elapsed_sec"),
            "route_distance_m": row.get("route_distance_m"),
            "speed_mps": row.get("speed_mps"),
            "elevation_m": row.get("elevation_m"),
            "route_load_context_band": row.get("route_load_context_band", ""),
            "planning_caution_level": row.get("planning_caution_level", ""),
            "boundary": BOUNDARY,
        })

    return pd.DataFrame(rows)


def compute_lifecycle_summary(activity_id: str, df: pd.DataFrame, mappings: dict[str, str], warnings: list[str]) -> dict[str, object]:
    hr = df["heart_rate_bpm"]
    duration = numeric(df["elapsed_sec"]).max() - numeric(df["elapsed_sec"]).min()
    high_load = df.get("route_load_context_band", pd.Series(dtype=object)).isin(HIGH_LOAD_BANDS)
    phases = activity_phase(df["elapsed_sec"])
    df_phase = df.copy()
    df_phase["activity_phase"] = phases
    early_hr = numeric(df_phase.loc[df_phase["activity_phase"].eq("early"), "heart_rate_bpm"]).median()
    late_hr = numeric(df_phase.loc[df_phase["activity_phase"].eq("late"), "heart_rate_bpm"]).median()
    early_speed = numeric(df_phase.loc[df_phase["activity_phase"].eq("early"), "speed_mps"]).median()
    late_speed = numeric(df_phase.loc[df_phase["activity_phase"].eq("late"), "speed_mps"]).median()
    return {
        "activity_id_short": activity_id,
        "duration_sec": duration,
        "point_count": len(df),
        "hr_available_count": int(hr.notna().sum()),
        "hr_coverage_ratio": float(hr.notna().mean()) if len(df) else np.nan,
        "hr_min_bpm": numeric(hr).min(),
        "hr_max_bpm": numeric(hr).max(),
        "hr_median_bpm": numeric(hr).median(),
        "hr_p75_bpm": numeric(hr).quantile(0.75),
        "hr_p90_bpm": numeric(hr).quantile(0.90),
        "hr_range_bpm": numeric(hr).max() - numeric(hr).min(),
        "speed_mps_median": numeric(df["speed_mps"]).median(),
        "high_load_hr_median": numeric(df.loc[high_load, "heart_rate_bpm"]).median() if high_load.any() else np.nan,
        "high_load_speed_mps_median": numeric(df.loc[high_load, "speed_mps"]).median() if high_load.any() else np.nan,
        "early_hr_median": early_hr,
        "middle_hr_median": numeric(df_phase.loc[df_phase["activity_phase"].eq("middle"), "heart_rate_bpm"]).median(),
        "late_hr_median": late_hr,
        "early_speed_median": early_speed,
        "late_speed_median": late_speed,
        "hr_drift_late_minus_early_bpm": late_hr - early_hr if pd.notna(late_hr) and pd.notna(early_hr) else np.nan,
        "speed_drift_late_minus_early_mps": late_speed - early_speed if pd.notna(late_speed) and pd.notna(early_speed) else np.nan,
        "input_time_col": mappings.get("time_col", ""),
        "input_hr_col": mappings.get("hr_col", ""),
        "input_speed_col": mappings.get("speed_col", ""),
        "input_route_distance_col": mappings.get("route_distance_col", ""),
        "data_quality_flags": pipe_flags(warnings) if warnings else "INPUT_COLUMNS_AVAILABLE",
        "boundary": BOUNDARY,
    }


def compute_recovery_events(
    activity_id: str,
    df: pd.DataFrame,
    pause_df: pd.DataFrame,
    pre_window_sec: float,
    horizons: list[int],
) -> pd.DataFrame:
    if pause_df.empty:
        return pd.DataFrame()
    rows = []
    df = df.copy()
    df["activity_phase"] = activity_phase(df["elapsed_sec"])
    for i, pause in pause_df.reset_index(drop=True).iterrows():
        start = float(pause["pause_start_sec"])
        pre = df[(df["elapsed_sec"] >= start - pre_window_sec) & (df["elapsed_sec"] <= start)]
        hr_start = nearest_value_at(df, start, "heart_rate_bpm")
        peak_pre = numeric(pre["heart_rate_bpm"]).max() if not pre.empty else np.nan
        row = {
            "activity_id_short": activity_id,
            "recovery_event_id": f"{activity_id}_recovery_{i+1:03d}",
            "pause_start_sec": start,
            "pause_end_sec": pause["pause_end_sec"],
            "pause_duration_sec": pause["pause_duration_sec"],
            "pause_start_route_distance_m": pause["pause_start_route_distance_m"],
            "pause_end_route_distance_m": pause["pause_end_route_distance_m"],
            "activity_phase": mode_text(df.loc[(df["elapsed_sec"] - start).abs().nsmallest(1).index, "activity_phase"]),
            "hr_at_pause_start": hr_start,
            "hr_peak_pre_pause_60s": peak_pre,
            "lowest_hr_during_pause": pause["lowest_hr_during_pause"],
            "time_to_drop_10bpm_sec": time_to_drop(df, start, hr_start, 10, max(horizons) if horizons else 120),
            "time_to_drop_20bpm_sec": time_to_drop(df, start, hr_start, 20, max(horizons) if horizons else 120),
            "boundary": BOUNDARY,
        }
        for h in horizons:
            hr_after = nearest_value_at(df, start + h, "heart_rate_bpm")
            row[f"hr_after_{h}s"] = hr_after
            row[f"hr_drop_from_start_{h}s"] = hr_start - hr_after if pd.notna(hr_start) and pd.notna(hr_after) else np.nan
            row[f"hr_drop_from_pre_peak_{h}s"] = peak_pre - hr_after if pd.notna(peak_pre) and pd.notna(hr_after) else np.nan
            row[f"hr_recovery_slope_bpm_per_min_{h}s"] = ((hr_start - hr_after) / h * 60.0) if pd.notna(hr_start) and pd.notna(hr_after) and h else np.nan
        rows.append(row)
    return pd.DataFrame(rows).round(6)


def compute_recovery_phase_summary(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    rows = []
    for activity_id, g in events.groupby("activity_id_short"):
        out = {"activity_id_short": activity_id, "recovery_event_count": len(g), "boundary": BOUNDARY}
        for phase in ["early", "middle", "late"]:
            sub = g[g["activity_phase"].eq(phase)]
            out[f"{phase}_event_count"] = len(sub)
            out[f"{phase}_drop_60s_median"] = numeric(sub.get("hr_drop_from_start_60s", pd.Series(dtype=float))).median()
            out[f"{phase}_slope_60s_bpm_per_min_median"] = numeric(sub.get("hr_recovery_slope_bpm_per_min_60s", pd.Series(dtype=float))).median()
        early = out.get("early_drop_60s_median")
        late = out.get("late_drop_60s_median")
        out["late_vs_early_drop_60s_ratio"] = late / early if pd.notna(late) and pd.notna(early) and early else np.nan
        if pd.notna(late) and pd.notna(early) and late < early * 0.7:
            out["recovery_phase_flags"] = "LATE_ACTIVITY_HR_RECOVERY_SLOWDOWN"
        elif pd.isna(late) or pd.isna(early):
            out["recovery_phase_flags"] = "INSUFFICIENT_PHASE_RECOVERY_EVENTS"
        else:
            out["recovery_phase_flags"] = "NO_CLEAR_LATE_RECOVERY_SLOWDOWN"
        rows.append(out)
    return pd.DataFrame(rows).round(6)


def compute_route_load_efficiency(activity_id: str, df: pd.DataFrame) -> pd.DataFrame:
    if "route_load_context_band" not in df.columns:
        return pd.DataFrame()
    rows = []
    for band, g in df.groupby("route_load_context_band", dropna=True):
        if not str(band) or str(band) == "nan":
            continue
        hr_med = numeric(g["heart_rate_bpm"]).median()
        speed_med = numeric(g["speed_mps"]).median()
        rows.append({
            "activity_id_short": activity_id,
            "route_load_context_band": band,
            "window_point_count": len(g),
            "hr_median_bpm": hr_med,
            "hr_p75_bpm": numeric(g["heart_rate_bpm"]).quantile(0.75),
            "speed_mps_median": speed_med,
            "speed_per_hr_mps_per_bpm": speed_med / hr_med if pd.notna(speed_med) and pd.notna(hr_med) and hr_med else np.nan,
            "boundary": BOUNDARY,
        })
    return pd.DataFrame(rows).round(6)


def save_activity_route_window_hr_plot(activity_id: str, df: pd.DataFrame, out_path: Path) -> None:
    """Plot route-distance window median HR.

    This avoids connecting raw time-series points on route distance, because
    route_distance_m may be non-monotonic, repeated, or map-matched to the same
    route position multiple times.
    """
    required = {
        "route_distance_window_start_m",
        "route_distance_window_end_m",
        "heart_rate_bpm",
    }
    if df.empty or not required.issubset(df.columns):
        return

    plot = df.copy()
    plot["heart_rate_bpm"] = numeric(plot["heart_rate_bpm"])
    plot["route_distance_window_start_m"] = numeric(plot["route_distance_window_start_m"])
    plot["route_distance_window_end_m"] = numeric(plot["route_distance_window_end_m"])

    plot = plot.dropna(
        subset=[
            "heart_rate_bpm",
            "route_distance_window_start_m",
            "route_distance_window_end_m",
        ]
    )
    if plot.empty:
        return

    grouped = (
        plot.groupby(
            ["route_distance_window_start_m", "route_distance_window_end_m"],
            as_index=False,
        )
        .agg(
            hr_median_bpm=("heart_rate_bpm", "median"),
            hr_p75_bpm=("heart_rate_bpm", lambda s: numeric(s).quantile(0.75)),
            point_count=("heart_rate_bpm", "size"),
            route_load_context_band=("route_load_context_band", mode_text)
            if "route_load_context_band" in plot.columns
            else ("heart_rate_bpm", lambda s: ""),
        )
        .sort_values("route_distance_window_start_m")
    )

    grouped["route_mid_km"] = (
        grouped["route_distance_window_start_m"]
        + grouped["route_distance_window_end_m"]
    ) / 2000.0

    fig, ax = plt.subplots(figsize=(14, 5), constrained_layout=True)

    # Route-load background bands, drawn by window instead of raw time-series points.
    if "route_load_context_band" in grouped.columns:
        for band, alpha in [
            ("VERY_HIGH_ROUTE_LOAD_CONTEXT", 0.10),
            ("HIGH_ROUTE_LOAD_CONTEXT", 0.06),
        ]:
            sub = grouped[grouped["route_load_context_band"].eq(band)]
            for _, row in sub.iterrows():
                ax.axvspan(
                    float(row["route_distance_window_start_m"]) / 1000.0,
                    float(row["route_distance_window_end_m"]) / 1000.0,
                    color="#7C2D12",
                    alpha=alpha,
                    linewidth=0,
                )


    # Break line across missing / non-contiguous route windows.
    # A 50m window should advance by about 0.05 km. Larger gaps are left unconnected.
    grouped = grouped.sort_values("route_mid_km").reset_index(drop=True)
    route_gap_km = grouped["route_mid_km"].diff()
    gap_break_threshold_km = 0.075

    median_y = grouped["hr_median_bpm"].copy()
    p75_y = grouped["hr_p75_bpm"].copy()

    median_y.loc[route_gap_km > gap_break_threshold_km] = np.nan
    p75_y.loc[route_gap_km > gap_break_threshold_km] = np.nan

    ax.plot(
        grouped["route_mid_km"],
        median_y,
        marker="o",
        markersize=3,
        linewidth=1.2,
        color="#DC2626",
        label="window median HR",
    )
    ax.plot(
        grouped["route_mid_km"],
        p75_y,
        linewidth=0.9,
        color="#991B1B",
        alpha=0.55,
        label="window p75 HR",
    )

    # Keep visible points even when line is broken by gaps.
    ax.scatter(
        grouped["route_mid_km"],
        grouped["hr_median_bpm"],
        s=12,
        color="#DC2626",
        alpha=0.85,
    )

    ax.set_title(f"Activity {activity_id} route-window HR response")
    ax.set_xlabel("route distance window (km)")
    ax.set_ylabel("HR bpm")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)

    fig.text(
        0.01,
        0.01,
        "Route-distance view uses 50m window median/p75 HR; non-contiguous windows are not connected.",
        fontsize=9,
        color="#475569",
    )
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def save_activity_plot(activity_id: str, df: pd.DataFrame, events: pd.DataFrame, out_path: Path) -> None:
    """Plot HR lifecycle against elapsed time.

    Do not use route_distance_m as the raw line-plot x-axis here. Route distance
    can repeat, reverse, or jump after map matching, which creates misleading
    zig-zag and horizontal lines.
    """
    if df.empty or df["heart_rate_bpm"].isna().all():
        return

    plot = df.copy()
    plot["elapsed_min"] = numeric(plot["elapsed_sec"]) / 60.0
    plot["heart_rate_bpm"] = numeric(plot["heart_rate_bpm"])
    plot = plot.dropna(subset=["elapsed_min", "heart_rate_bpm"]).sort_values("elapsed_min")

    if plot.empty:
        return

    # Break visually across large sampling gaps.
    dt = plot["elapsed_min"].diff()
    median_dt = dt[dt > 0].median()
    gap_threshold_min = max(2.0, float(median_dt) * 5.0) if pd.notna(median_dt) else 2.0
    y = plot["heart_rate_bpm"].copy()
    y.loc[dt > gap_threshold_min] = np.nan

    fig, ax = plt.subplots(figsize=(14, 5), constrained_layout=True)

    # Mark high route-load periods on the time axis.
    if "route_load_context_band" in plot.columns:
        for band, alpha in [
            ("VERY_HIGH_ROUTE_LOAD_CONTEXT", 0.10),
            ("HIGH_ROUTE_LOAD_CONTEXT", 0.06),
        ]:
            tmp = plot[["elapsed_min", "route_load_context_band"]].copy()
            tmp["is_band"] = tmp["route_load_context_band"].eq(band)
            tmp["group"] = (tmp["is_band"] != tmp["is_band"].shift()).cumsum()

            for _, g in tmp[tmp["is_band"]].groupby("group"):
                start_min = float(g["elapsed_min"].min())
                end_min = float(g["elapsed_min"].max())
                if end_min > start_min:
                    ax.axvspan(
                        start_min,
                        end_min,
                        color="#7C2D12",
                        alpha=alpha,
                        linewidth=0,
                    )

    ax.plot(
        plot["elapsed_min"],
        y,
        color="#DC2626",
        linewidth=1.0,
        label="heart rate bpm",
    )

    # Early / middle / late phase guide lines.
    start_min = float(plot["elapsed_min"].min())
    end_min = float(plot["elapsed_min"].max())
    if end_min > start_min:
        for frac, label in [(1 / 3, "early/middle"), (2 / 3, "middle/late")]:
            x = start_min + (end_min - start_min) * frac
            ax.axvline(x, color="#64748B", alpha=0.35, linewidth=0.8)
            ax.text(
                x,
                ax.get_ylim()[1],
                label,
                rotation=90,
                va="top",
                ha="right",
                fontsize=8,
                color="#64748B",
            )

    # Recovery events, if any become available later.
    if events is not None and not events.empty:
        ev = events[events["activity_id_short"].eq(activity_id)]
        for _, row in ev.iterrows():
            ev_x = float(row.get("pause_start_sec", np.nan)) / 60.0
            if pd.notna(ev_x):
                ax.axvline(ev_x, color="#111827", alpha=0.30, linewidth=0.8)

    ax.set_title(f"Activity {activity_id} HR lifecycle profile")
    ax.set_xlabel("elapsed time (min)")
    ax.set_ylabel("HR bpm")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)

    fig.text(
        0.01,
        0.01,
        "Descriptive HR lifecycle evidence only; elapsed-time plot, not ability scoring.",
        fontsize=9,
        color="#475569",
    )
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def html_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    view = df if max_rows is None else df.head(max_rows)
    return view.to_html(index=False, escape=True, border=0, classes="data-table")


def write_html_report(path: Path, summary: pd.DataFrame, extremes: pd.DataFrame, events: pd.DataFrame,
                      phase_summary: pd.DataFrame, efficiency: pd.DataFrame, audit: pd.DataFrame,
                      pngs: list[Path]) -> None:
    img_tags = "\n".join(f'<figure><img src="{html.escape(p.name)}" alt="{html.escape(p.stem)}"></figure>' for p in pngs if p.exists())
    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CH6.7 HR Lifecycle Recovery Profile v2</title>
<style>
body {{ font-family: "Microsoft JhengHei", Arial, sans-serif; margin: 32px; color: #111827; }}
h1, h2 {{ margin-bottom: 0.35rem; }}
.boundary {{ padding: 12px 14px; border-left: 4px solid #DC2626; background: #FEF2F2; }}
.data-table {{ border-collapse: collapse; width: 100%; font-size: 12px; margin: 10px 0 24px; }}
.data-table th, .data-table td {{ border: 1px solid #CBD5E1; padding: 6px 8px; text-align: left; vertical-align: top; }}
.data-table th {{ background: #F1F5F9; }}
img {{ max-width: 100%; border: 1px solid #E5E7EB; }}
figure {{ margin: 20px 0; }}
</style>
</head>
<body>
<h1>CH6.7 HR Lifecycle Recovery Profile v2</h1>
<p class="boundary">{html.escape(BOUNDARY)}</p>
{img_tags}
<h2>Activity HR Lifecycle Summary</h2>
{html_table(summary)}
<h2>HR Extreme Points</h2>
{html_table(extremes)}
<h2>HR Recovery Events</h2>
{html_table(events, max_rows=100)}
<h2>HR Recovery Phase Summary</h2>
{html_table(phase_summary)}
<h2>HR Route-Load Efficiency</h2>
{html_table(efficiency)}
<h2>Audit</h2>
{html_table(audit)}
</body>
</html>
"""
    path.write_text(doc, encoding="utf-8")


def write_run_report(path: Path, audit: pd.DataFrame, summary: pd.DataFrame) -> None:
    lines = [
        "# CH6.7 HR Lifecycle Recovery Profile v2 Run Report",
        "",
        "## Summary",
        "",
        f"- activity_count: `{len(summary)}`",
        f"- hr_available_activity_count: `{int(summary['hr_available_count'].gt(0).sum()) if 'hr_available_count' in summary else 0}`",
        "",
        "## Audit",
        "",
    ]
    for key, value in audit.iloc[0].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend([
        "",
        "## Boundaries",
        "",
        f"- {BOUNDARY}",
        "- HR high/low is not interpreted as cardiopulmonary ability good/bad.",
        "- HR missing is not interpreted as low effort.",
        "- No Word/docx output is generated.",
        "- No commit is created by this script.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_audit(activity_files: list[Path], summaries: pd.DataFrame, events: pd.DataFrame,
                output_files: list[Path], warnings: dict[str, list[str]]) -> pd.DataFrame:
    generated_cols = set()
    for path in output_files:
        if path.suffix.lower() == ".csv" and path.exists():
            try:
                generated_cols.update(pd.read_csv(path, nrows=0, encoding="utf-8-sig").columns)
            except Exception:
                pass
    forbidden = sorted(FORBIDDEN_OUTPUT_COLUMNS & generated_cols)
    warning_text = []
    for aid, ws in warnings.items():
        for w in ws:
            warning_text.append(f"{aid}:{w}")
    conclusion = "PASS_CH6_7_HR_LIFECYCLE_RECOVERY_PROFILE_V2_DESCRIPTIVE_ONLY"
    if forbidden:
        conclusion = "REVIEW_REQUIRED_FORBIDDEN_COLUMNS_PRESENT"
    elif summaries.empty:
        conclusion = "REVIEW_REQUIRED_NO_ACTIVITY_TIMESERIES_FOUND"
    return pd.DataFrame([{
        "activity_timeseries_file_count": len(activity_files),
        "activity_summary_count": len(summaries),
        "hr_available_activity_count": int(summaries["hr_available_count"].gt(0).sum()) if not summaries.empty else 0,
        "recovery_event_count": len(events),
        "activities_with_recovery_events": int(events["activity_id_short"].nunique()) if not events.empty else 0,
        "input_warnings": "|".join(warning_text) if warning_text else "NONE",
        "forbidden_output_columns_absent": len(forbidden) == 0,
        "forbidden_output_columns": "|".join(forbidden) if forbidden else "NONE",
        "hr_missing_not_interpreted_as_low_effort": True,
        "ability_scoring_performed": False,
        "cardiopulmonary_diagnosis_performed": False,
        "output_files_generated": "|".join(str(p) for p in output_files if p.exists()),
        "audit_conclusion": conclusion,
    }])


def main() -> None:
    args = parse_args()
    setup_matplotlib_font()
    root = Path(args.root)
    output_root = resolve(root, args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    horizons = [int(x.strip()) for x in args.recovery_horizons_sec.split(",") if x.strip()]
    reps = [x.strip() for x in args.representative_activities.split(",") if x.strip()]

    context = load_route_context(resolve(root, args.route_load_windows), resolve(root, args.planning_windows))
    activity_files = discover_activity_files(root, args.activity_glob)

    summaries: list[dict[str, object]] = []
    extremes_list: list[pd.DataFrame] = []
    events_list: list[pd.DataFrame] = []
    efficiency_list: list[pd.DataFrame] = []
    plot_cache: dict[str, pd.DataFrame] = {}
    warnings: dict[str, list[str]] = {}

    for path in activity_files:
        try:
            activity_id, df, mapping, ws = standardize_activity_df(path)
        except pd.errors.EmptyDataError:
            activity_id = parse_activity_id(path, None)
            warnings[activity_id] = [f"SKIPPED_EMPTY_CSV:{path}"]
            continue
        except UnicodeDecodeError:
            activity_id = parse_activity_id(path, None)
            warnings[activity_id] = [f"SKIPPED_DECODE_ERROR:{path}"]
            continue

        # Skip files that do not contain usable HR values.
        # This script is an HR lifecycle profile; HR missing is not interpreted as low effort.
        if "heart_rate_bpm" not in df.columns or df["heart_rate_bpm"].notna().sum() == 0:
            warnings[activity_id] = ws + [f"SKIPPED_NO_USABLE_HR_VALUES:{path}"]
            continue

        # Keep each activity once; prefer first discovered file.
        if activity_id in plot_cache:
            continue

        df = attach_context(df, context)
        plot_cache[activity_id] = df
        warnings[activity_id] = ws
        summaries.append(compute_lifecycle_summary(activity_id, df, mapping, ws))
        ex = compute_extremes(activity_id, df)
        if not ex.empty:
            extremes_list.append(ex)
        pauses = detect_pause_segments(df, args.pause_speed_threshold_mps, args.pause_min_duration_sec)
        ev = compute_recovery_events(activity_id, df, pauses, args.pre_pause_peak_window_sec, horizons)
        if not ev.empty:
            events_list.append(ev)
        eff = compute_route_load_efficiency(activity_id, df)
        if not eff.empty:
            efficiency_list.append(eff)

    summary_df = pd.DataFrame(summaries).sort_values("activity_id_short") if summaries else pd.DataFrame()
    extremes_df = pd.concat(extremes_list, ignore_index=True) if extremes_list else pd.DataFrame()
    events_df = pd.concat(events_list, ignore_index=True) if events_list else pd.DataFrame()
    phase_summary_df = compute_recovery_phase_summary(events_df)
    efficiency_df = pd.concat(efficiency_list, ignore_index=True) if efficiency_list else pd.DataFrame()

    summary_csv = output_root / "activity_hr_lifecycle_summary_v2.csv"
    extremes_csv = output_root / "activity_hr_extreme_points_v2.csv"
    events_csv = output_root / "activity_hr_recovery_events_v2.csv"
    phase_csv = output_root / "activity_hr_recovery_phase_summary_v2.csv"
    efficiency_csv = output_root / "activity_hr_route_load_efficiency_v2.csv"
    audit_csv = output_root / "activity_hr_lifecycle_audit_v2.csv"
    report_md = output_root / "activity_hr_lifecycle_run_report_v2.md"
    html_report = output_root / "activity_hr_lifecycle_report_v2.html"

    summary_df.to_csv(summary_csv, index=False, encoding="utf-8-sig")
    extremes_df.to_csv(extremes_csv, index=False, encoding="utf-8-sig")
    events_df.to_csv(events_csv, index=False, encoding="utf-8-sig")
    phase_summary_df.to_csv(phase_csv, index=False, encoding="utf-8-sig")
    efficiency_df.to_csv(efficiency_csv, index=False, encoding="utf-8-sig")

    pngs: list[Path] = []
    for aid in reps:
        if aid in plot_cache:
            time_png = output_root / f"activity_{aid}_hr_lifecycle_time_profile_v2.png"
            save_activity_plot(aid, plot_cache[aid], events_df, time_png)
            if time_png.exists():
                pngs.append(time_png)

            route_png = output_root / f"activity_{aid}_hr_route_window_median_profile_v2.png"
            save_activity_route_window_hr_plot(aid, plot_cache[aid], route_png)
            if route_png.exists():
                pngs.append(route_png)

    output_files = [summary_csv, extremes_csv, events_csv, phase_csv, efficiency_csv, audit_csv, report_md, html_report] + pngs
    audit_df = build_audit(activity_files, summary_df, events_df, output_files, warnings)
    audit_df.to_csv(audit_csv, index=False, encoding="utf-8-sig")
    write_html_report(html_report, summary_df, extremes_df, events_df, phase_summary_df, efficiency_df, audit_df, pngs)
    write_run_report(report_md, audit_df, summary_df)

    payload = {
        "script_path": str(Path(__file__)),
        "output_root": str(output_root),
        "activity_timeseries_file_count": len(activity_files),
        "activity_summary_count": len(summary_df),
        "hr_available_activity_count": int(summary_df["hr_available_count"].gt(0).sum()) if not summary_df.empty else 0,
        "recovery_event_count": len(events_df),
        "activities_with_recovery_events": int(events_df["activity_id_short"].nunique()) if not events_df.empty else 0,
        "html_report": str(html_report),
        "png_paths": [str(p) for p in pngs],
        "audit_conclusion": str(audit_df.iloc[0]["audit_conclusion"]),
        "forbidden_columns_absent": bool(audit_df.iloc[0]["forbidden_output_columns_absent"]),
        "boundary": BOUNDARY,
    }
    print(payload)


if __name__ == "__main__":
    main()
