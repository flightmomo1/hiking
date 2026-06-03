# -*- coding: utf-8 -*-
"""
Build an integrated 1D/2D activity profile board.

Example:
    python scripts/ib3b2_plot_activity_profile_1d_2d.py ^
        --route-folder qixing_lengshuikeng ^
        --case-id qixing_lengshuikeng_main_peak_20260523 ^
        --activity-id 37_1
"""

from __future__ import annotations

import argparse
import html
import json
import warnings
from pathlib import Path

import folium
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pandas.errors import DtypeWarning, PerformanceWarning
from pyproj import Geod, Transformer

warnings.filterwarnings("ignore", category=DtypeWarning)
warnings.filterwarnings("ignore", category=PerformanceWarning)

GEOD = Geod(ellps="WGS84")
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MAPMATCHED_ROOT = Path("outputs/ib3a_mapmatched_standardized_activity")
DEFAULT_IB3A2_ROOT = Path("outputs/ib3a2_on_route_activity_filter")


QUALITY_COLOR = {
    "good": "#2f855a",
    "acceptable": "#38a169",
    "fair": "#d69e2e",
    "weak": "#dd6b20",
    "poor": "#c53030",
    "off_route": "#6b46c1",
    "nan": "#718096",
}

SEGMENT_COLORS = [
    "#2563eb",
    "#059669",
    "#d97706",
    "#7c3aed",
    "#dc2626",
    "#0891b2",
    "#65a30d",
    "#be185d",
]

LABEL_COLOR = {
    "route_variant": "#f59e0b",
    "wrong_route": "#dc2626",
    "post_route": "#64748b",
    "gps_artifact": "#7c3aed",
    "start_offset": "#0ea5e9",
    "intentional_rest": "#16a34a",
    "ambiguous": "#78716c",
}

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

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--route-folder", default="qixing_lengshuikeng")
    parser.add_argument("--case-id", default="qixing_lengshuikeng_main_peak_20260523")
    parser.add_argument("--activity-id", default="37_1")
    parser.add_argument(
        "--mapmatched-root",
        type=Path,
        default=DEFAULT_MAPMATCHED_ROOT,
        help=(
            "Root containing raw mapmatched CSVs. Default preserves the legacy ib3a/ib3a2 flow. "
            "Use outputs/ib3a_sequence_mapmatched_activity for sequence-mapmatched visualization."
        ),
    )
    parser.add_argument(
        "--ib3a2-root",
        type=Path,
        default=DEFAULT_IB3A2_ROOT,
        help=(
            "Root containing ib3a2 labeled/on-route CSVs. "
            "Use outputs/ib3a2_on_route_activity_filter_v3 when visualizing sequence v3 outputs."
        ),
    )
    parser.add_argument("--segment-m", type=float, default=250.0)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("outputs/ib3b2_activity_profile_1d_2d"),
    )
    parser.add_argument(
        "--ib3c-root",
        type=Path,
        default=Path("outputs/ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route"),
        help="Root containing IB3C behavior event CSVs.",
    )
    parser.add_argument(
        "--events-csv",
        type=Path,
        default=None,
        help="Optional explicit IB3C behavior events CSV.",
    )
    parser.add_argument(
        "--show-events",
        action="store_true",
        help="Overlay IB3C observed behavior events on the activity profile.",
    )
    return parser.parse_args()


def require_file(path: Path, label: str) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path.resolve()}")
    return path


def resolve_path(value, project_root: Path = PROJECT_ROOT) -> Path:
    p = Path(value)
    if p.is_absolute():
        return p
    return project_root / p


def to_bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin(["true", "1", "yes", "y"])


def normalize_activity_columns(df: pd.DataFrame, source_fp: Path) -> pd.DataFrame:
    df = df.copy()
    df["activity_source_fp"] = str(source_fp)

    rename = {
        "ele_m": "raw_ele_m",
        "offset_m": "offset_to_mainline_m",
        "lat": "raw_lat",
        "lon": "raw_lon",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    for col in [
        "route_dist_m",
        "nearest_route_dist_m",
        "timestamp_s",
        "elapsed_sec",
        "raw_ele_m",
        "row_index",
        "point_index",
        "segment_id",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "route_dist_m" not in df.columns:
        raise KeyError("activity CSV must contain route_dist_m")
    if "offset_to_mainline_m" not in df.columns:
        raise KeyError("activity CSV must contain offset_m or offset_to_mainline_m")

    if "row_index" not in df.columns:
        df["row_index"] = np.arange(len(df), dtype=int)
    if "point_index" not in df.columns:
        df["point_index"] = df["row_index"]

    if "usable_on_route" not in df.columns:
        df["usable_on_route"] = True
    else:
        df["usable_on_route"] = to_bool_series(df["usable_on_route"])

    for col in ["manual_override_applied"]:
        if col in df.columns:
            df[col] = to_bool_series(df[col])
        else:
            df[col] = False

    for col in ["manual_label", "manual_interpretation", "excluded_reason", "segment_role"]:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str)

    # Do not sort by route_dist_m here.
    # Activity order should follow original activity row/time order, not mapmatched route distance.
    sort_cols = []
    for col in ["row_index", "elapsed_sec", "timestamp_s", "point_index"]:
        if col in df.columns and df[col].notna().any():
            sort_cols.append(col)

    if sort_cols:
        return df.sort_values(sort_cols, na_position="last").reset_index(drop=True)

    return df.reset_index(drop=True)


def use_legacy_ib3a2_flow(mapmatched_root: Path) -> bool:
    return Path(mapmatched_root) == DEFAULT_MAPMATCHED_ROOT


def ib3a2_activity_paths(ib3a2_root: Path, route_folder: str, activity_id: str) -> dict[str, Path]:
    stem = f"{route_folder}_{activity_id}_mapmatched_activity"
    route_dir = Path(ib3a2_root) / route_folder
    return {
        "labeled": route_dir / f"{stem}_labeled.csv",
        "on_route": route_dir / f"{stem}_on_route.csv",
        "excursions": route_dir / f"{stem}_excursions.csv",
    }


def read_activity_full(
    route_folder: str,
    activity_id: str,
    mapmatched_root: Path,
    ib3a2_root: Path,
) -> pd.DataFrame:
    paths = ib3a2_activity_paths(ib3a2_root, route_folder, activity_id)
    mapmatched_fp = Path(mapmatched_root) / route_folder / f"{activity_id}_mapmatched.csv"

    if paths["labeled"].exists():
        fp = paths["labeled"]
    else:
        fp = require_file(mapmatched_fp, "mapmatched activity")

    return normalize_activity_columns(pd.read_csv(fp), fp)


def read_activity_for_speed(
    route_folder: str,
    activity_id: str,
    full_df: pd.DataFrame,
    mapmatched_root: Path,
    ib3a2_root: Path,
) -> tuple[pd.DataFrame, str]:
    paths = ib3a2_activity_paths(ib3a2_root, route_folder, activity_id)

    if paths["on_route"].exists():
        return (
            normalize_activity_columns(pd.read_csv(paths["on_route"]), paths["on_route"]),
            f"{Path(ib3a2_root).name}_on_route_csv",
        )

    speed_df = full_df[full_df["usable_on_route"]].copy()
    return speed_df.reset_index(drop=True), "full_labeled_filtered_usable_on_route"


SPEED_COLS = [
    "speed_usable_segment_id",
    "forward_delta_route_dist_m",
    "forward_delta_route_point_index",
    "forward_speed_route_mps_raw_uncapped",
    "forward_speed_route_mps_raw",
    "forward_speed_route_mps_smooth",
    "speed_source",
    "speed_input_source",
    "speed_base_dist_col",
    "speed_continuous_segment_id",
    "speed_negative_delta_flag",
    "speed_invalid_dt_flag",
    "speed_gap_break_flag",
    "speed_route_dist_jump_flag",
    "speed_route_point_index_jump_flag",
    "speed_mapmatch_jump_flag",
    "speed_summit_transition_release_break_flag",
    "mapmatch_branch_jump_warning",
    "previous_route_phase",
    "route_phase_jump_flag",
    "mapmatch_branch_ambiguity_flag",
    "stationary_gps_drift_flag",
    "stationary_gps_drift_segment_id",
    "stationary_duration_sec",
    "stationary_route_dist_range_m",
    "stationary_gps_spread_m",
    "stationary_hr_delta_bpm",
    "stationary_hr_recovery_hint",
    "speed_capped_flag",
]

SPEED_GAP_THRESHOLD_SEC = 10.0
SPEED_ROUTE_DIST_JUMP_THRESHOLD_M = 30.0
SPEED_ROUTE_POINT_INDEX_JUMP_THRESHOLD = 30.0
SPEED_CAP_MPS = 3.0
STATIONARY_GPS_DRIFT_WINDOW_SEC = 60.0
STATIONARY_GPS_DRIFT_MIN_SPAN_SEC = 30.0
STATIONARY_GPS_DRIFT_ROUTE_RANGE_M = 15.0
STATIONARY_GPS_DRIFT_SPREAD_M = 25.0
STATIONARY_GPS_DRIFT_SPIKE_MPS = 0.75
SUMMIT_SELF_NEAR_WINDOW_M = 300.0
ONE_D_PROFILE_BIN_M = 5.0
PANEL1_MODE = "full_route_axis"  # "full_route_axis" or "out_and_back_mirror"


def derive_speed(df: pd.DataFrame, speed_input_source: str) -> None:
    if "forward_speed_route_mps_raw" in df.columns:
        raw = pd.to_numeric(df["forward_speed_route_mps_raw"], errors="coerce")
        df["speed_source"] = "provided_forward_speed_route_mps_raw"
        df["speed_base_dist_col"] = ""
        df["speed_gap_break_flag"] = False
        df["speed_route_dist_jump_flag"] = False
        df["speed_route_point_index_jump_flag"] = False
        df["speed_mapmatch_jump_flag"] = False
        df["mapmatch_branch_jump_warning"] = False
    elif "forward_speed_route_mps" in df.columns:
        raw = pd.to_numeric(df["forward_speed_route_mps"], errors="coerce")
        df["speed_source"] = "provided_forward_speed_route_mps"
        df["speed_base_dist_col"] = ""
        df["speed_gap_break_flag"] = False
        df["speed_route_dist_jump_flag"] = False
        df["speed_route_point_index_jump_flag"] = False
        df["speed_mapmatch_jump_flag"] = False
        df["mapmatch_branch_jump_warning"] = False
    else:
        if "route_dist_m" in df.columns and df["route_dist_m"].notna().any():
            dist_col = "route_dist_m"
        elif "nearest_route_dist_m" in df.columns and df["nearest_route_dist_m"].notna().any():
            dist_col = "nearest_route_dist_m"
        else:
            raise KeyError("activity CSV must contain route_dist_m or nearest_route_dist_m for speed reconstruction")

        if "elapsed_sec" in df.columns and df["elapsed_sec"].notna().any():
            time = pd.to_numeric(df["elapsed_sec"], errors="coerce")
            dt = time.diff()
            time_col = "elapsed_sec"
        elif "timestamp_s" in df.columns:
            time = pd.to_numeric(df["timestamp_s"], errors="coerce")
            dt = time.diff()
            time_col = "timestamp_s"
        else:
            time = pd.Series(np.nan, index=df.index)
            dt = pd.Series(np.nan, index=df.index)
            time_col = ""

        gap_break = build_speed_gap_breaks(df, dt)
        df["speed_gap_break_flag"] = gap_break
        df["speed_usable_segment_id"] = gap_break.cumsum().astype(int)

        dist = pd.to_numeric(df[dist_col], errors="coerce")
        dd = dist.groupby(df["speed_usable_segment_id"]).diff()
        dt_in_segment = time.groupby(df["speed_usable_segment_id"]).diff()
        df["forward_delta_route_dist_m"] = dd
        df["speed_negative_delta_flag"] = dd < 0
        df["speed_invalid_dt_flag"] = ~(dt_in_segment > 0)

        raw_uncapped_pre_guard = dd.where(dd >= 0).div(dt_in_segment.where(dt_in_segment > 0))
        if "route_point_index" in df.columns:
            dpi = pd.to_numeric(df["route_point_index"], errors="coerce").groupby(df["speed_usable_segment_id"]).diff()
        else:
            dpi = pd.Series(np.nan, index=df.index)
        df["forward_delta_route_point_index"] = dpi
        add_route_phase_jump_flags(df)

        if "summit_transition_release_flag" in df.columns:
            summit_release_break = to_bool_series(df["summit_transition_release_flag"])
        else:
            summit_release_break = pd.Series(False, index=df.index)

        df["speed_summit_transition_release_break_flag"] = summit_release_break

        df["speed_route_dist_jump_flag"] = dd.abs() > SPEED_ROUTE_DIST_JUMP_THRESHOLD_M
        df["speed_route_point_index_jump_flag"] = dpi.abs() > SPEED_ROUTE_POINT_INDEX_JUMP_THRESHOLD
        df["speed_mapmatch_jump_flag"] = (
            df["speed_route_dist_jump_flag"]
            | df["speed_route_point_index_jump_flag"]
            | (raw_uncapped_pre_guard > SPEED_CAP_MPS)
            | df["route_phase_jump_flag"]
            | df["mapmatch_branch_ambiguity_flag"]
            | df["speed_summit_transition_release_break_flag"]
        )

        df["mapmatch_branch_jump_warning"] = df["speed_mapmatch_jump_flag"]
        add_stationary_gps_drift_flags(df, time, dist, raw_uncapped_pre_guard)
        raw = raw_uncapped_pre_guard.where(
            ~df["speed_mapmatch_jump_flag"] & ~df["stationary_gps_drift_flag"]
        )
        df["speed_continuous_segment_id"] = (
            df["speed_gap_break_flag"].fillna(False)
            | df["speed_mapmatch_jump_flag"].fillna(False)
            | df["stationary_gps_drift_flag"].fillna(False)
        ).cumsum().astype(int)
        df["speed_source"] = f"reconstructed_from_on_route_{dist_col}_{time_col}"
        df["speed_base_dist_col"] = dist_col

    df["speed_input_source"] = speed_input_source
    if "raw_uncapped_pre_guard" in locals():
        df["speed_capped_flag"] = raw_uncapped_pre_guard > SPEED_CAP_MPS
        df["forward_speed_route_mps_raw_uncapped"] = raw_uncapped_pre_guard
    else:
        df["speed_capped_flag"] = raw > SPEED_CAP_MPS
        df["forward_speed_route_mps_raw_uncapped"] = raw
    df["forward_speed_route_mps_raw"] = raw.clip(lower=0, upper=SPEED_CAP_MPS)
    if "forward_speed_route_mps_smooth" not in df.columns:
        if {"speed_gap_break_flag", "speed_mapmatch_jump_flag"}.issubset(df.columns):
            if "speed_continuous_segment_id" in df.columns:
                speed_group = df["speed_continuous_segment_id"]
            else:
                speed_group = (
                df["speed_gap_break_flag"].fillna(False)
                | df["speed_mapmatch_jump_flag"].fillna(False)
                | df.get(
                    "stationary_gps_drift_flag",
                    pd.Series(False, index=df.index),
                ).fillna(False)
            ).cumsum()
            df["forward_speed_route_mps_smooth"] = df.groupby(speed_group, group_keys=False)[
                "forward_speed_route_mps_raw"
            ].apply(lambda s: s.rolling(21, center=True, min_periods=5).median())
            df.loc[
                df["speed_gap_break_flag"].fillna(False)
                | df["speed_mapmatch_jump_flag"].fillna(False)
                | df.get(
                    "stationary_gps_drift_flag",
                    pd.Series(False, index=df.index),
                ).fillna(False),
                "forward_speed_route_mps_smooth",
            ] = np.nan
        else:
            df["forward_speed_route_mps_smooth"] = (
                df["forward_speed_route_mps_raw"].rolling(21, center=True, min_periods=5).median()
            )
    if "speed_negative_delta_flag" not in df.columns:
        df["speed_negative_delta_flag"] = False
    if "speed_invalid_dt_flag" not in df.columns:
        df["speed_invalid_dt_flag"] = False
    if "speed_gap_break_flag" not in df.columns:
        df["speed_gap_break_flag"] = False
    if "speed_usable_segment_id" not in df.columns:
        df["speed_usable_segment_id"] = 0
    if "speed_continuous_segment_id" not in df.columns:
        df["speed_continuous_segment_id"] = df["speed_usable_segment_id"]
    for col in [
        "speed_route_dist_jump_flag",
        "speed_route_point_index_jump_flag",
        "speed_mapmatch_jump_flag",
        "speed_summit_transition_release_break_flag",
        "mapmatch_branch_jump_warning",
        "route_phase_jump_flag",
        "mapmatch_branch_ambiguity_flag",
        "stationary_gps_drift_flag",
        "stationary_hr_recovery_hint",
    ]:
        if col not in df.columns:
            df[col] = False
    for col in [
        "stationary_gps_drift_segment_id",
        "stationary_duration_sec",
        "stationary_route_dist_range_m",
        "stationary_gps_spread_m",
        "stationary_hr_delta_bpm",
    ]:
        if col not in df.columns:
            df[col] = np.nan
    if "previous_route_phase" not in df.columns:
        df["previous_route_phase"] = ""


def build_speed_gap_breaks(df: pd.DataFrame, dt: pd.Series) -> pd.Series:
    gap_break = pd.Series(False, index=df.index)
    if not gap_break.empty:
        gap_break.iloc[0] = True

    if "row_index" in df.columns and df["row_index"].notna().any():
        row_gap = pd.to_numeric(df["row_index"], errors="coerce").diff()
        gap_break = gap_break | (row_gap > 1)

    gap_break = gap_break | (dt > SPEED_GAP_THRESHOLD_SEC)

    if "segment_role" in df.columns:
        role = df["segment_role"].fillna("").astype(str)
        gap_break = gap_break | (role != role.shift())

    return gap_break.fillna(False)


def add_route_phase_jump_flags(df: pd.DataFrame) -> None:
    if "route_phase" not in df.columns:
        df["previous_route_phase"] = ""
        df["route_phase_jump_flag"] = False
        df["mapmatch_branch_ambiguity_flag"] = False
        return

    phase = df["route_phase"].fillna("").astype(str)
    prev_phase = phase.groupby(df["speed_usable_segment_id"]).shift()
    df["previous_route_phase"] = prev_phase.fillna("")

    if "elapsed_sec" in df.columns:
        elapsed_delta = pd.to_numeric(df["elapsed_sec"], errors="coerce").groupby(df["speed_usable_segment_id"]).diff()
    elif "timestamp_s" in df.columns:
        elapsed_delta = pd.to_numeric(df["timestamp_s"], errors="coerce").groupby(df["speed_usable_segment_id"]).diff()
    else:
        elapsed_delta = pd.Series(np.nan, index=df.index)

    dist_delta = pd.to_numeric(df["route_dist_m"], errors="coerce").groupby(df["speed_usable_segment_id"]).diff()
    point_delta = (
        pd.to_numeric(df["route_point_index"], errors="coerce").groupby(df["speed_usable_segment_id"]).diff()
        if "route_point_index" in df.columns
        else pd.Series(np.nan, index=df.index)
    )
    phase_changed = phase.ne(prev_phase) & prev_phase.notna()
    short_time = elapsed_delta.le(SPEED_GAP_THRESHOLD_SEC).fillna(False)
    big_route_delta = dist_delta.abs().gt(SPEED_ROUTE_DIST_JUMP_THRESHOLD_M).fillna(False)
    big_point_delta = point_delta.abs().gt(SPEED_ROUTE_POINT_INDEX_JUMP_THRESHOLD).fillna(False)
    suspicious_pair = (
        (prev_phase.eq("ascent") & phase.eq("descent"))
        | (prev_phase.eq("descent") & phase.eq("ascent"))
        | (prev_phase.eq("summit_self_near") & phase.isin(["ascent", "descent"]) & (big_route_delta | big_point_delta))
        | (phase.eq("summit_self_near") & prev_phase.isin(["ascent", "descent"]) & (big_route_delta | big_point_delta))
    )
    jump = phase_changed & short_time & suspicious_pair
    df["route_phase_jump_flag"] = jump.fillna(False)
    df["mapmatch_branch_ambiguity_flag"] = (jump | (phase_changed & short_time & (big_route_delta | big_point_delta))).fillna(False)


def add_stationary_gps_drift_flags(
    df: pd.DataFrame,
    time: pd.Series,
    dist: pd.Series,
    raw_uncapped: pd.Series,
) -> None:
    n = len(df)
    flag = pd.Series(False, index=df.index)
    route_range_out = pd.Series(np.nan, index=df.index)
    gps_spread_out = pd.Series(np.nan, index=df.index)
    hr_delta_out = pd.Series(np.nan, index=df.index)
    hr_recovery = pd.Series(False, index=df.index)

    if n == 0 or not {"raw_lat", "raw_lon"}.issubset(df.columns):
        df["stationary_gps_drift_flag"] = flag
        df["stationary_gps_drift_segment_id"] = np.nan
        df["stationary_duration_sec"] = np.nan
        df["stationary_route_dist_range_m"] = route_range_out
        df["stationary_gps_spread_m"] = gps_spread_out
        df["stationary_hr_delta_bpm"] = hr_delta_out
        df["stationary_hr_recovery_hint"] = hr_recovery
        return

    lat = pd.to_numeric(df["raw_lat"], errors="coerce")
    lon = pd.to_numeric(df["raw_lon"], errors="coerce")
    lat0 = float(lat.dropna().median()) if lat.notna().any() else 0.0
    meters_per_lat = 111_320.0
    meters_per_lon = 111_320.0 * np.cos(np.deg2rad(lat0))
    x = (lon - float(lon.dropna().median() if lon.notna().any() else 0.0)) * meters_per_lon
    y = (lat - lat0) * meters_per_lat
    hr = pd.to_numeric(df["heart_rate_bpm"], errors="coerce") if "heart_rate_bpm" in df.columns else None

    t = pd.to_numeric(time, errors="coerce")
    start = 0
    for end in range(n):
        if not np.isfinite(t.iloc[end]):
            continue
        while start < end and np.isfinite(t.iloc[start]) and (
            t.iloc[end] - t.iloc[start] > STATIONARY_GPS_DRIFT_WINDOW_SEC
        ):
            start += 1
        idx = df.index[start : end + 1]
        span = t.loc[idx].max() - t.loc[idx].min()
        if not np.isfinite(span) or span < STATIONARY_GPS_DRIFT_MIN_SPAN_SEC:
            continue

        route_range = dist.loc[idx].max() - dist.loc[idx].min()
        gps_dx = x.loc[idx].max() - x.loc[idx].min()
        gps_dy = y.loc[idx].max() - y.loc[idx].min()
        gps_spread = float(np.sqrt(gps_dx * gps_dx + gps_dy * gps_dy))
        speed_spike = raw_uncapped.loc[idx].max()
        if not all(np.isfinite(v) for v in [route_range, gps_spread, speed_spike]):
            continue
        if (
            route_range < STATIONARY_GPS_DRIFT_ROUTE_RANGE_M
            and gps_spread < STATIONARY_GPS_DRIFT_SPREAD_M
            and speed_spike > STATIONARY_GPS_DRIFT_SPIKE_MPS
        ):
            flag.loc[idx] = True
            route_range_out.loc[idx] = route_range
            gps_spread_out.loc[idx] = gps_spread
            if hr is not None and hr.loc[idx].notna().sum() >= 3:
                hr_delta = hr.loc[idx].iloc[-1] - hr.loc[idx].iloc[0]
                hr_delta_out.loc[idx] = hr_delta
                hr_recovery.loc[idx] = hr_delta <= 0

    segment_start = flag & ~flag.shift(fill_value=False)
    segment_id = segment_start.cumsum().where(flag)
    duration = pd.Series(np.nan, index=df.index)
    for _, group in df[flag].groupby(segment_id[flag]):
        span = t.loc[group.index].max() - t.loc[group.index].min()
        duration.loc[group.index] = span if np.isfinite(span) else np.nan

    df["stationary_gps_drift_flag"] = flag.fillna(False)
    df["stationary_gps_drift_segment_id"] = segment_id
    df["stationary_duration_sec"] = duration
    df["stationary_route_dist_range_m"] = route_range_out
    df["stationary_gps_spread_m"] = gps_spread_out
    df["stationary_hr_delta_bpm"] = hr_delta_out
    df["stationary_hr_recovery_hint"] = hr_recovery.fillna(False)


def attach_on_route_speed(full_df: pd.DataFrame, speed_df: pd.DataFrame) -> pd.DataFrame:
    full_df = full_df.copy()
    for col in SPEED_COLS:
        if col in full_df.columns:
            full_df = full_df.drop(columns=[col])

    cols = [c for c in SPEED_COLS if c in speed_df.columns]
    if "row_index" in full_df.columns and "row_index" in speed_df.columns:
        speed_keep = speed_df[["row_index"] + cols].drop_duplicates("row_index", keep="last")
        merged = full_df.merge(speed_keep, on="row_index", how="left")
    else:
        key = "elapsed_sec" if "elapsed_sec" in full_df.columns and "elapsed_sec" in speed_df.columns else "timestamp_s"
        speed_keep = speed_df[[key] + cols].drop_duplicates(key, keep="last")
        merged = full_df.merge(speed_keep, on=key, how="left")

    for col in [
        "speed_negative_delta_flag",
        "speed_invalid_dt_flag",
        "speed_gap_break_flag",
        "speed_route_dist_jump_flag",
        "speed_route_point_index_jump_flag",
        "speed_mapmatch_jump_flag",
        "speed_summit_transition_release_break_flag",
        "mapmatch_branch_jump_warning",
        "stationary_gps_drift_flag",
        "stationary_hr_recovery_hint",
        "speed_capped_flag",
    ]:
        if col not in merged.columns:
            merged[col] = False
        merged[col] = merged[col].fillna(False).astype(bool)
    return merged


def derive_stationary(df: pd.DataFrame) -> None:
    if "is_stationary" in df.columns:
        df["is_stationary"] = to_bool_series(df["is_stationary"])
        return
    direction = df["direction_hint"].astype(str).str.lower() if "direction_hint" in df.columns else ""
    speed = df["forward_speed_route_mps_smooth"].fillna(df["forward_speed_route_mps_raw"])
    drift = df["stationary_gps_drift_flag"] if "stationary_gps_drift_flag" in df.columns else False
    df["is_stationary"] = (direction == "stationary") | (speed < 0.2) | drift


def read_route(case_id: str) -> pd.DataFrame:
    contour_fp = Path(
        f"outputs/ib1e_route_profile_contour_window_terrain/{case_id}/"
        f"{case_id}_route_profile_contour_window_terrain_enriched.csv"
    )
    profile_fp = Path(f"outputs/ib1_route_profile/{case_id}/{case_id}_route_profile.csv")
    fp = contour_fp if contour_fp.exists() else require_file(profile_fp, "route profile")
    route = pd.read_csv(fp)
    if "dist_m" not in route.columns:
        raise KeyError("route profile must contain dist_m")
    route = route.sort_values("dist_m").drop_duplicates("dist_m").reset_index(drop=True)
    route["route_point_index"] = route.index
    route["route_source_fp"] = str(fp)
    add_route_bearing(route)
    add_route_phase(route)

    if {"elev_min_nlsc_window", "elev_max_nlsc_window"}.issubset(route.columns):
        route["contour_elev_min_m"] = pd.to_numeric(route["elev_min_nlsc_window"], errors="coerce")
        route["contour_elev_max_m"] = pd.to_numeric(route["elev_max_nlsc_window"], errors="coerce")
        route["contour_elev_mid_m"] = (
            route["contour_elev_min_m"] + route["contour_elev_max_m"]
        ) / 2.0
    return route


def add_route_phase(route: pd.DataFrame) -> None:
    ele_col = "ele_smooth" if "ele_smooth" in route.columns and route["ele_smooth"].notna().any() else "ele_gpx_m"
    if ele_col in route.columns and route[ele_col].notna().any():
        summit_idx = pd.to_numeric(route[ele_col], errors="coerce").idxmax()
        summit_dist = float(route.loc[summit_idx, "dist_m"])
    else:
        summit_dist = float(route["dist_m"].median())
    dist = pd.to_numeric(route["dist_m"], errors="coerce")
    route["summit_route_dist_m"] = summit_dist
    route["dist_to_summit_m"] = dist - summit_dist
    route["route_phase"] = np.select(
        [
            route["dist_to_summit_m"].abs() <= SUMMIT_SELF_NEAR_WINDOW_M,
            dist < summit_dist,
            dist > summit_dist,
        ],
        ["summit_self_near", "ascent", "descent"],
        default="unknown",
    )


def add_route_bearing(route: pd.DataFrame) -> None:
    bearings = []
    seglens = []
    rows = route[["lat", "lon"]].copy()
    for i, row in rows.iterrows():
        if i == len(rows) - 1:
            bearings.append(np.nan)
            seglens.append(np.nan)
            continue
        nxt = rows.iloc[i + 1]
        az12, _, dist = GEOD.inv(float(row["lon"]), float(row["lat"]), float(nxt["lon"]), float(nxt["lat"]))
        bearings.append((az12 + 360.0) % 360.0)
        seglens.append(dist)
    route["bearing_to_next"] = bearings
    route["segment_length_to_next_m"] = seglens


def merge_route_context(activity: pd.DataFrame, route: pd.DataFrame) -> pd.DataFrame:
    activity_work = activity.copy()
    activity_work["_activity_order"] = np.arange(len(activity_work))
    keep = [
        "dist_m",
        "route_point_index",
        "route_phase",
        "dist_to_summit_m",
        "summit_route_dist_m",
        "lat",
        "lon",
        "ele_gpx_m",
        "ele_smooth",
        "bearing_to_next",
        "segment_length_to_next_m",
        "contour_elev_min_m",
        "contour_elev_mid_m",
        "contour_elev_max_m",
    ]
    keep = [c for c in keep if c in route.columns]
    merged = pd.merge_asof(
        activity_work.sort_values("route_dist_m"),
        route[keep].sort_values("dist_m"),
        left_on="route_dist_m",
        right_on="dist_m",
        direction="nearest",
    )
    merged = (
        merged.sort_values("_activity_order")
        .drop(columns=["_activity_order"])
        .reset_index(drop=True)
    )
    if {"lat", "lon"}.issubset(merged.columns):
        merged = merged.rename(columns={"lat": "matched_lat", "lon": "matched_lon"})
    return merged


def sort_activity_time_order(df: pd.DataFrame) -> pd.DataFrame:
    sort_cols = []
    for col in ["elapsed_sec", "timestamp_s", "row_index"]:
        if col in df.columns and df[col].notna().any():
            sort_cols.append(col)
    if not sort_cols:
        return df.reset_index(drop=True)
    return df.sort_values(sort_cols, na_position="last").reset_index(drop=True)


def add_activity_route_phase_transition_flags(df: pd.DataFrame) -> None:
    if "route_phase" not in df.columns:
        return
    work = sort_activity_time_order(df).copy()
    phase = work["route_phase"].fillna("").astype(str)
    prev = phase.shift()
    work["previous_route_phase_full"] = prev.fillna("")
    work["route_point_index_delta_full"] = pd.to_numeric(work["route_point_index"], errors="coerce").diff()
    work["route_dist_delta_m_full"] = pd.to_numeric(work["route_dist_m"], errors="coerce").diff()
    work["elapsed_delta_sec_full"] = pd.to_numeric(work["elapsed_sec"], errors="coerce").diff()
    phase_changed = phase.ne(prev) & prev.notna()
    short_time = work["elapsed_delta_sec_full"].le(SPEED_GAP_THRESHOLD_SEC).fillna(False)
    big_point = work["route_point_index_delta_full"].abs().gt(SPEED_ROUTE_POINT_INDEX_JUMP_THRESHOLD).fillna(False)
    big_dist = work["route_dist_delta_m_full"].abs().gt(SPEED_ROUTE_DIST_JUMP_THRESHOLD_M).fillna(False)
    suspicious = (
        (prev.eq("ascent") & phase.eq("descent"))
        | (prev.eq("descent") & phase.eq("ascent"))
        | (prev.eq("summit_self_near") & phase.isin(["ascent", "descent"]) & (big_point | big_dist))
        | (phase.eq("summit_self_near") & prev.isin(["ascent", "descent"]) & (big_point | big_dist))
        | (phase_changed & short_time & (big_point | big_dist))
    )
    work["route_phase_jump_flag_full"] = (phase_changed & short_time & suspicious).fillna(False)
    work["mapmatch_branch_ambiguity_flag_full"] = work["route_phase_jump_flag_full"]

    cols = [
        "row_index",
        "previous_route_phase_full",
        "route_point_index_delta_full",
        "route_dist_delta_m_full",
        "elapsed_delta_sec_full",
        "route_phase_jump_flag_full",
        "mapmatch_branch_ambiguity_flag_full",
    ]
    if "row_index" in df.columns:
        updates = work[cols].drop_duplicates("row_index", keep="last")
        merged = df[["row_index"]].merge(updates, on="row_index", how="left")
        target_index = df.index
    else:
        merged = work[cols[1:]].reindex(df.index)
        target_index = df.index

    for col in cols[1:]:
        df[col] = merged[col].values
    for base, full in [
        ("route_phase_jump_flag", "route_phase_jump_flag_full"),
        ("mapmatch_branch_ambiguity_flag", "mapmatch_branch_ambiguity_flag_full"),
    ]:
        if base not in df.columns:
            df[base] = False
        df[base] = df[base].fillna(False) | df[full].fillna(False)
    if "previous_route_phase" not in df.columns:
        df["previous_route_phase"] = df["previous_route_phase_full"].fillna("")
    else:
        df["previous_route_phase"] = df["previous_route_phase"].fillna(df["previous_route_phase_full"]).fillna("")


def read_anchors(case_id: str, route: pd.DataFrame) -> pd.DataFrame:
    fp = Path(f"outputs/ib0c_anchor/{case_id}/{case_id}_route_anchors.csv")
    if not fp.exists():
        return pd.DataFrame()
    anchors = pd.read_csv(fp)
    if anchors.empty or not {"ref_lat", "ref_lon"}.issubset(anchors.columns):
        return pd.DataFrame()

    anchors["anchor_dist_m"] = anchors.apply(
        lambda r: nearest_dist(route, float(r["ref_lat"]), float(r["ref_lon"])), axis=1
    )
    return anchors


def nearest_dist(route: pd.DataFrame, lat: float, lon: float) -> float:
    d2 = (route["lat"].astype(float) - lat) ** 2 + (route["lon"].astype(float) - lon) ** 2
    idx = int(d2.idxmin())
    return float(route.loc[idx, "dist_m"])


def make_segments(route_len_m: float, segment_m: float) -> list[dict]:
    starts = np.arange(0, route_len_m + segment_m, segment_m)
    rows = []
    for i, start in enumerate(starts[:-1]):
        end = min(float(starts[i + 1]), float(route_len_m))
        if end <= start:
            continue
        rows.append(
            {
                "segment_id": i,
                "start_m": float(start),
                "end_m": float(end),
                "color": SEGMENT_COLORS[i % len(SEGMENT_COLORS)],
            }
        )
    return rows


def project_xy(*frames: pd.DataFrame) -> None:
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3826", always_xy=True)
    for frame in frames:
        if frame.empty:
            continue
        lon_col = "lon" if "lon" in frame.columns else "raw_lon"
        lat_col = "lat" if "lat" in frame.columns else "raw_lat"
        if {lon_col, lat_col}.issubset(frame.columns):
            x, y = transformer.transform(frame[lon_col].astype(float).values, frame[lat_col].astype(float).values)
            frame["x_m"] = x
            frame["y_m"] = y
        if {"matched_lon", "matched_lat"}.issubset(frame.columns):
            x, y = transformer.transform(
                frame["matched_lon"].astype(float).values,
                frame["matched_lat"].astype(float).values,
            )
            frame["matched_x_m"] = x
            frame["matched_y_m"] = y


def add_segment_bands(ax, segments: list[dict]) -> None:
    for seg in segments:
        ax.axvspan(seg["start_m"], seg["end_m"], color=seg["color"], alpha=0.075, lw=0)


def build_one_d_profile(df: pd.DataFrame, route: pd.DataFrame, bin_m: float = ONE_D_PROFILE_BIN_M) -> pd.DataFrame:
    route_len = float(max(route["dist_m"].max(), df["route_dist_m"].max(), 1.0))
    bins = pd.DataFrame({"route_bin_m": np.arange(0.0, route_len + bin_m, bin_m)})

    activity = df.copy()
    activity["route_bin_m"] = (pd.to_numeric(activity["route_dist_m"], errors="coerce") / bin_m).round() * bin_m
    usable = activity[activity["usable_on_route"].fillna(False)].copy()

    pieces = [bins]
    if not usable.empty:
        speed_valid = usable.copy()
        for flag_col in [
            "speed_mapmatch_jump_flag",
            "speed_summit_transition_release_break_flag",
            "stationary_gps_drift_flag",
            "speed_gap_break_flag",
            "speed_invalid_dt_flag",
            "speed_negative_delta_flag",
        ]:
            if flag_col in speed_valid.columns:
                speed_valid = speed_valid[~speed_valid[flag_col].fillna(False)]

        speed = speed_valid.groupby("route_bin_m", as_index=False).agg(
            forward_speed_route_mps_raw_median=("forward_speed_route_mps_raw", "median"),
            forward_speed_route_mps_smooth_median=("forward_speed_route_mps_smooth", "median"),
        )
        pieces.append(speed)

        heart_rate = usable.groupby("route_bin_m", as_index=False).agg(
            heart_rate_bpm_median=("heart_rate_bpm", "median"),
        )
        pieces.append(heart_rate)

        offset_onroute = usable.groupby("route_bin_m", as_index=False).agg(
            offset_onroute_median=("offset_to_mainline_m", "median"),
        )
        pieces.append(offset_onroute)

    if not activity.empty:
        offset_all = activity.groupby("route_bin_m", as_index=False).agg(
            offset_all_p90=("offset_to_mainline_m", lambda s: pd.to_numeric(s, errors="coerce").quantile(0.90)),
        )
        pieces.append(offset_all)

    profile = pieces[0]
    for piece in pieces[1:]:
        profile = profile.merge(piece, on="route_bin_m", how="left")
    return profile.sort_values("route_bin_m").reset_index(drop=True)


def get_panel1_summit_dist(route: pd.DataFrame) -> float:
    """Get summit / mirror reference distance from route profile elevation."""
    for col in ["ele_smooth", "ele_gpx_m", "contour_elev_mid_m"]:
        if col in route.columns:
            ele = pd.to_numeric(route[col], errors="coerce")
            if ele.notna().any():
                idx = ele.idxmax()
                return float(route.loc[idx, "dist_m"])
    return float(pd.to_numeric(route["dist_m"], errors="coerce").median())


def add_panel1_mirror_columns(df: pd.DataFrame, route: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Add Panel 1 x-axis columns.

    full_route_axis:
        x = route_dist_m

    out_and_back_mirror:
        ascent:  x = route_dist_m
        descent: x = 2 * summit_dist - route_dist_m
    """
    summit_dist = get_panel1_summit_dist(route)

    df2 = df.copy()
    route2 = route.copy()

    route_dist = pd.to_numeric(route2["dist_m"], errors="coerce")
    act_dist = pd.to_numeric(df2["route_dist_m"], errors="coerce")

    route2["panel1_full_route_dist_m"] = route_dist
    route2["panel1_summit_route_dist_m"] = summit_dist
    route2["panel1_mirror_x_m"] = np.where(
        route_dist <= summit_dist,
        route_dist,
        2.0 * summit_dist - route_dist,
    )
    route2["panel1_mirror_out_of_range_flag"] = route2["panel1_mirror_x_m"] < 0

    df2["panel1_full_route_dist_m"] = act_dist
    df2["panel1_summit_route_dist_m"] = summit_dist
    df2["panel1_mirror_x_m"] = np.where(
        act_dist <= summit_dist,
        act_dist,
        2.0 * summit_dist - act_dist,
    )
    df2["panel1_mirror_out_of_range_flag"] = df2["panel1_mirror_x_m"] < 0

    info = {
        "panel1_mode": PANEL1_MODE,
        "panel1_summit_route_dist_m": summit_dist,
        "panel1_mirror_x_min_m": float(pd.to_numeric(df2["panel1_mirror_x_m"], errors="coerce").min()),
        "panel1_mirror_x_max_m": float(pd.to_numeric(df2["panel1_mirror_x_m"], errors="coerce").max()),
        "panel1_mirror_out_of_range_rows": int(df2["panel1_mirror_out_of_range_flag"].sum()),
    }
    return df2, route2, info


def plot_excluded_spans(ax, df: pd.DataFrame, y_frac: float = 0.03) -> None:
    excluded = df[~df["usable_on_route"]].copy()
    if excluded.empty:
        return
    groups = excluded.groupby(["excursion_id", "manual_interpretation", "excluded_reason"], dropna=False)
    ymin, ymax = ax.get_ylim()
    height = (ymax - ymin) * y_frac
    for (_, interp, reason), g in groups:
        label = interp or reason or "excluded"
        color = LABEL_COLOR.get(str(interp), "#dc2626")
        ax.axvspan(g["route_dist_m"].min(), g["route_dist_m"].max(), color=color, alpha=0.12, lw=0)
        ax.text(
            g["route_dist_m"].median(),
            ymin + height,
            label,
            ha="center",
            va="bottom",
            fontsize=7,
            color=color,
            rotation=0,
        )


def plot_anchors_1d(ax, anchors: pd.DataFrame) -> None:
    if anchors.empty:
        return
    ymin, ymax = ax.get_ylim()
    for _, row in anchors.iterrows():
        x = float(row["anchor_dist_m"])
        label = f"{row.get('anchor_role', '')} waypoint".strip()
        ax.axvline(x, color="#111827", lw=0.8, ls=":", alpha=0.6)
        ax.text(x, ymax, label, ha="center", va="top", fontsize=7, rotation=90, color="#111827")


def build_route_line_segments(route: pd.DataFrame, segments: list[dict]) -> list[tuple]:
    rows = []
    route = route.dropna(subset=["x_m", "y_m", "dist_m"]).sort_values("dist_m")
    for seg in segments:
        part = route[(route["dist_m"] >= seg["start_m"]) & (route["dist_m"] <= seg["end_m"])]
        if len(part) < 2:
            continue
        coords = part[["x_m", "y_m"]].to_numpy()
        rows.append((coords, seg["color"], seg))
    return rows


def write_png(out_png: Path, df: pd.DataFrame, route: pd.DataFrame, anchors: pd.DataFrame, segments: list[dict]) -> None:
    df_time = sort_activity_time_order(df)
    df_1d = build_one_d_profile(df, route)
    df_p1, route_p1, panel1_info = add_panel1_mirror_columns(df, route)

    if PANEL1_MODE == "out_and_back_mirror":
        p1_route_x = route_p1["panel1_mirror_x_m"]
        p1_activity_x = df_p1["panel1_mirror_x_m"]
    else:
        p1_route_x = route_p1["dist_m"]
        p1_activity_x = df_p1["route_dist_m"]
    fig = plt.figure(figsize=(16, 20), constrained_layout=False)
    gs = fig.add_gridspec(5, 1, height_ratios=[1.1, 0.85, 0.85, 0.55, 3.2], hspace=0.20)
    ax_ele = fig.add_subplot(gs[0])
    ax_speed = fig.add_subplot(gs[1])
    ax_hr = fig.add_subplot(gs[2], sharex=ax_speed)
    ax_qa = fig.add_subplot(gs[3], sharex=ax_speed)
    ax_map = fig.add_subplot(gs[4])

    ax_ele.grid(True, alpha=0.22)

    for ax in [ax_speed, ax_hr, ax_qa]:
        add_segment_bands(ax, segments)
        ax.grid(True, alpha=0.22)

    ax_ele.plot(p1_route_x, route_p1["ele_gpx_m"], color="#1f2937", lw=0.9, alpha=0.7, label="GPX raw elevation")
    if {"contour_elev_min_m", "contour_elev_max_m"}.issubset(route.columns):
        ax_ele.fill_between(
            p1_route_x,
            route_p1["contour_elev_min_m"],
            route_p1["contour_elev_max_m"],
            color="#38bdf8",
            alpha=0.22,
            label="NLSC contour elevation band",
        )
        ax_ele.plot(
            p1_route_x,
            route_p1["contour_elev_mid_m"],
            color="#0284c7",
            lw=1.3,
            ls="--",
            label="NLSC contour midpoint",
        )

    if "ele_smooth" in route.columns:
        ax_ele.plot(
            p1_route_x,
            route_p1["ele_smooth"],
            color="#16a34a",
            lw=1.1,
            label="corrected / route smoothed elevation",
        )

    ax_ele.scatter(
        p1_activity_x,
        df_p1["raw_ele_m"],
        color="#64748b",
        s=2,
        alpha=0.12,
        label="activity raw elevation points",
    )

    summit_x = panel1_info["panel1_summit_route_dist_m"]
    ax_ele.axvline(
        summit_x,
        color="#f97316",
        lw=1.2,
        ls="--",
        alpha=0.85,
        label=f"summit / mirror point {summit_x / 1000:.3f} km",
    )

    if PANEL1_MODE == "out_and_back_mirror":
        ax_ele.set_xlim(0, summit_x)
        ax_ele.set_xlabel("Mirrored distance to summit (m)")
    else:
        ax_ele.set_xlabel("Route distance (m)")

    ax_ele.text(
        0.995,
        0.92,
        f"Panel1 mode: {PANEL1_MODE}",
        transform=ax_ele.transAxes,
        ha="right",
        va="top",
        fontsize=8,
        color="#334155",
    )

    ax_ele.set_ylabel("Elevation (m)")
    ax_ele.legend(loc="upper left", fontsize=8, ncol=2)

    ax_speed.scatter(
        df["route_dist_m"],
        df["forward_speed_route_mps_raw"],
        color="#94a3b8",
        s=3,
        alpha=0.14,
        label="forward_speed_route_mps_raw points",
    )
    ax_speed.plot(
        df_1d["route_bin_m"],
        df_1d["forward_speed_route_mps_smooth_median"],
        color="#2563eb",
        lw=1.4,
        label="median forward_speed_route_mps_smooth by route bin",
    )
    stationary = df[df["is_stationary"]]
    if not stationary.empty:
        ax_speed.scatter(
            stationary["route_dist_m"],
            stationary["forward_speed_route_mps_raw"].fillna(0),
            s=5,
            color="#111827",
            alpha=0.18,
            label="stationary",
        )
    capped = df[df["speed_capped_flag"]]
    if not capped.empty:
        ax_speed.scatter(
            capped["route_dist_m"],
            capped["forward_speed_route_mps_raw"],
            s=12,
            marker="x",
            color="#f97316",
            alpha=0.65,
            label="speed_capped_flag",
        )
    ax_speed.set_ylabel("Speed (m/s)")
    ax_speed.set_ylim(0, 3.1)
    ax_speed.legend(loc="upper left", fontsize=8, ncol=3)

    if "heart_rate_bpm" in df.columns:
        ax_hr.plot(df_1d["route_bin_m"], df_1d["heart_rate_bpm_median"], color="#dc2626", lw=1.15, alpha=0.9, label="median heart_rate_bpm by route bin")
        hr = pd.to_numeric(df["heart_rate_bpm"], errors="coerce")
        if hr.notna().any():
            lo = max(40, float(hr.quantile(0.01)) - 5)
            hi = min(220, float(hr.quantile(0.99)) + 5)
            if hi > lo:
                ax_hr.set_ylim(lo, hi)
    ax_hr.set_ylabel("Heart rate (bpm)")
    ax_hr.legend(loc="upper left", fontsize=8)

    offset_plot = df_1d["offset_onroute_median"].clip(upper=30)
    ax_qa.plot(df_1d["route_bin_m"], offset_plot, color="#334155", lw=0.85, label="on-route median offset by route bin")
    if "offset_all_p90" in df_1d.columns:
        ax_qa.plot(df_1d["route_bin_m"], df_1d["offset_all_p90"].clip(upper=30), color="#64748b", lw=0.75, ls="--", alpha=0.75, label="all activity p90 offset by route bin")
    for quality, color in QUALITY_COLOR.items():
        q = df[df["match_quality"].astype(str).str.lower().fillna("nan") == quality]
        if not q.empty:
            ax_qa.scatter(q["route_dist_m"], q["offset_to_mainline_m"].clip(upper=30), s=7, color=color, alpha=0.72, label=f"match_quality={quality}")
    ax_qa.axhline(10, color="#f59e0b", lw=0.9, ls="--", label="10m reference")
    ax_qa.axhline(25, color="#dc2626", lw=0.9, ls="--", label="25m reference")
    ax_qa.set_ylim(0, 30)
    plot_excluded_spans(ax_qa, df)
    ax_qa.set_ylabel("Offset (m)")
    ax_qa.set_xlabel("Route distance (m)")
    ax_qa.legend(loc="upper left", fontsize=7, ncol=3)

    route_segs = build_route_line_segments(route, segments)
    for coords, color, _ in route_segs:
        ax_map.plot(coords[:, 0], coords[:, 1], color=color, lw=5.0, alpha=0.9, solid_capstyle="round")
    ax_map.plot(route["x_m"], route["y_m"], color="#111827", lw=0.7, alpha=0.42, label="route axis")
    ax_map.plot(df_time["x_m"], df_time["y_m"], color="#94a3b8", lw=0.65, alpha=0.55, label="raw activity trajectory")
    if {"matched_x_m", "matched_y_m"}.issubset(df.columns):
        ax_map.plot(df_time["matched_x_m"], df_time["matched_y_m"], color="#111827", lw=1.0, alpha=0.42, label="matched trajectory")
    for interp, g in df_time[~df_time["usable_on_route"]].groupby("manual_interpretation", dropna=False):
        color = LABEL_COLOR.get(str(interp), "#dc2626")
        ax_map.scatter(g["x_m"], g["y_m"], s=6, color=color, alpha=0.65, label=f"excluded: {interp or 'unlabeled'}")
    manual = df_time[df_time["manual_override_applied"]]
    if not manual.empty:
        ax_map.scatter(manual["x_m"], manual["y_m"], s=16, facecolors="none", edgecolors="#f59e0b", lw=0.8, label="manual override")
    if not route.empty:
        start = route.sort_values("dist_m").iloc[0]
        end = route.sort_values("dist_m").iloc[-1]
        ax_map.scatter([start["x_m"]], [start["y_m"]], marker="o", s=82, color="#16a34a", edgecolor="white", linewidth=1.2, zorder=7, label="start")
        ax_map.scatter([end["x_m"]], [end["y_m"]], marker="s", s=82, color="#dc2626", edgecolor="white", linewidth=1.2, zorder=7, label="end")
        ax_map.text(start["x_m"], start["y_m"], " start", fontsize=9, ha="left", va="bottom", color="#14532d")
        ax_map.text(end["x_m"], end["y_m"], " end", fontsize=9, ha="left", va="bottom", color="#7f1d1d")
    plot_anchors_2d(ax_map, anchors)
    ax_map.set_aspect("equal", adjustable="datalim")
    ax_map.set_xlabel("TWD97 TM2 X (m)")
    ax_map.set_ylabel("TWD97 TM2 Y (m)")
    ax_map.grid(True, alpha=0.18)
    ax_map.legend(loc="best", fontsize=8, ncol=2)

    for ax in [ax_speed, ax_hr, ax_qa]:
        plot_anchors_1d(ax, anchors)

    fig.suptitle("Activity Profile 1D + 2D Route Board: qixing_lengshuikeng 37_1", fontsize=15, y=0.985)
    fig.savefig(out_png, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_anchors_2d(ax, anchors: pd.DataFrame) -> None:
    if anchors.empty:
        return
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3826", always_xy=True)
    xs, ys = transformer.transform(anchors["ref_lon"].astype(float).values, anchors["ref_lat"].astype(float).values)
    ax.scatter(xs, ys, marker="*", s=90, color="#111827", edgecolor="white", linewidth=0.8, zorder=6, label="waypoint / event")
    for x, y, (_, row) in zip(xs, ys, anchors.iterrows()):
        label = f"{row.get('anchor_role', 'waypoint')} waypoint"
        ax.text(x, y, label, fontsize=8, ha="left", va="bottom", color="#111827")


def scale(values: pd.Series, out_min: float, out_max: float, pad: float = 0.08) -> tuple[list[float], float, float]:
    vals = pd.to_numeric(values, errors="coerce")
    vmin = float(vals.min())
    vmax = float(vals.max())
    if not np.isfinite(vmin) or not np.isfinite(vmax):
        vmin, vmax = 0.0, 1.0
    if abs(vmax - vmin) < 1e-9:
        vmax = vmin + 1.0
    span = vmax - vmin
    vmin -= span * pad
    vmax += span * pad
    scaled = out_max - (vals - vmin) / (vmax - vmin) * (out_max - out_min)
    return scaled.fillna(out_max).tolist(), vmin, vmax


def scale_with_bounds(values: pd.Series, out_min: float, out_max: float, vmin: float, vmax: float) -> list[float]:
    vals = pd.to_numeric(values, errors="coerce")
    if abs(vmax - vmin) < 1e-9:
        vmax = vmin + 1.0
    return (out_max - (vals - vmin) / (vmax - vmin) * (out_max - out_min)).tolist()


def scale_x(dist: pd.Series, route_len: float, left: float, right: float) -> list[float]:
    return (left + pd.to_numeric(dist, errors="coerce").fillna(0) / route_len * (right - left)).tolist()


def svg_polyline(xs: list[float], ys: list[float], color: str, width: float, opacity: float = 1.0, dash: str = "") -> str:
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys) if np.isfinite(x) and np.isfinite(y))
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}" opacity="{opacity}"{dash_attr}/>'


def svg_polyline_breaks(xs: list[float], ys: list[float], color: str, width: float, opacity: float = 1.0, dash: str = "") -> str:
    parts = []
    current = []
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    for x, y in zip(xs, ys):
        if np.isfinite(x) and np.isfinite(y):
            current.append(f"{x:.1f},{y:.1f}")
        else:
            if len(current) >= 2:
                parts.append(
                    f'<polyline points="{" ".join(current)}" fill="none" stroke="{color}" stroke-width="{width}" opacity="{opacity}"{dash_attr}/>'
                )
            current = []
    if len(current) >= 2:
        parts.append(
            f'<polyline points="{" ".join(current)}" fill="none" stroke="{color}" stroke-width="{width}" opacity="{opacity}"{dash_attr}/>'
        )
    return "".join(parts)


def svg_scatter(xs: list[float], ys: list[float], color: str, radius: float, opacity: float) -> str:
    return "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{color}" opacity="{opacity}"/>'
        for x, y in zip(xs, ys)
        if np.isfinite(x) and np.isfinite(y)
    )


def fmt_value(value, digits: int = 3) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, (bool, np.bool_)):
        return str(bool(value))
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        return f"{float(value):.{digits}f}"
    return str(value)


def html_lines(rows: list[tuple[str, object, int]]) -> str:
    lines = []
    for key, value, digits in rows:
        text = fmt_value(value, digits)
        if text == "":
            continue
        lines.append(f"{html.escape(key)} = {html.escape(text)}")
    return "<br/>".join(lines)


def svg_title(rows: list[tuple[str, object, int]]) -> str:
    text = "\n".join(
        f"{key} = {fmt_value(value, digits)}"
        for key, value, digits in rows
        if fmt_value(value, digits) != ""
    )
    return f"<title>{html.escape(text)}</title>"


def route_point_tooltip_rows(row: pd.Series) -> list[tuple[str, object, int]]:
    return [
        ("route_point_index", row.get("route_point_index", ""), 0),
        ("dist_m", row.get("dist_m", ""), 3),
        ("route_dist_m", row.get("dist_m", ""), 3),
        ("dist_km", float(row.get("dist_m", np.nan)) / 1000.0, 3),
        ("route_phase", row.get("route_phase", ""), 0),
        ("dist_to_summit_m", row.get("dist_to_summit_m", ""), 3),
        ("lat", row.get("lat", ""), 7),
        ("lon", row.get("lon", ""), 7),
        ("ele_gpx_m", row.get("ele_gpx_m", ""), 2),
        ("ele_smooth", row.get("ele_smooth", ""), 2),
        ("bearing_to_next", row.get("bearing_to_next", ""), 1),
    ]


def activity_tooltip_rows(row: pd.Series) -> list[tuple[str, object, int]]:
    return [
        ("activity_row_index", row.get("row_index", ""), 0),
        ("point_index", row.get("point_index", ""), 0),
        ("subject_id", row.get("subject_id", ""), 0),
        ("trial_id", row.get("trial_id", ""), 0),
        ("elapsed_sec", row.get("elapsed_sec", ""), 1),
        ("lat", row.get("raw_lat", row.get("lat", "")), 7),
        ("lon", row.get("raw_lon", row.get("lon", "")), 7),
        ("route_dist_m", row.get("route_dist_m", ""), 3),
        ("route_point_index", row.get("route_point_index", ""), 0),
        ("route_phase", row.get("route_phase", ""), 0),
        ("dist_to_summit_m", row.get("dist_to_summit_m", ""), 3),
        ("nearest_route_dist_m", row.get("nearest_route_dist_m", ""), 3),
        ("offset_m", row.get("offset_to_mainline_m", row.get("offset_m", "")), 3),
        ("match_quality", row.get("match_quality", ""), 0),
        ("usable_on_route", row.get("usable_on_route", ""), 0),
        ("manual_label", row.get("manual_label", ""), 0),
        ("manual_interpretation", row.get("manual_interpretation", ""), 0),
        ("excluded_reason", row.get("excluded_reason", ""), 0),
        ("manual_event_id", row.get("manual_event_id", ""), 0),
        ("mapmatch_branch_jump_warning", row.get("mapmatch_branch_jump_warning", ""), 0),
        ("speed_mapmatch_jump_flag", row.get("speed_mapmatch_jump_flag", ""), 0),
        ("route_phase_jump_flag", row.get("route_phase_jump_flag", ""), 0),
        ("mapmatch_branch_ambiguity_flag", row.get("mapmatch_branch_ambiguity_flag", ""), 0),
        ("manual_override_index_note", "use 2D raw activity point popup activity_row_index for manual override start/end", 0),
        ("stationary_gps_drift_flag", row.get("stationary_gps_drift_flag", ""), 0),
        ("stationary_duration_sec", row.get("stationary_duration_sec", ""), 1),
        ("stationary_hr_recovery_hint", row.get("stationary_hr_recovery_hint", ""), 0),
    ]


def event_tooltip_rows(row: pd.Series) -> list[tuple[str, object, int]]:
    return [
        ("event_id", row.get("event_id", ""), 0),
        ("event_type", row.get("event_type", ""), 0),
        ("event_subtype", row.get("event_subtype", ""), 0),
        ("start_elapsed_sec", row.get("start_elapsed_sec", ""), 1),
        ("end_elapsed_sec", row.get("end_elapsed_sec", ""), 1),
        ("duration_sec", row.get("duration_sec", ""), 1),
        ("start_route_dist_m", row.get("start_route_dist_m", ""), 1),
        ("end_route_dist_m", row.get("end_route_dist_m", ""), 1),
        ("route_dist_span_m", row.get("route_dist_span_m", ""), 1),
        ("max_offset_m", row.get("max_offset_m", ""), 1),
        ("max_hr_bpm", row.get("max_hr_bpm", ""), 1),
        ("rest_duration_tier", row.get("rest_duration_tier", ""), 0),
        ("recovery_level", row.get("recovery_level", ""), 0),
        ("estimated_recovery_score", row.get("estimated_recovery_score", ""), 2),
        ("recovery_interpretation", row.get("recovery_interpretation", ""), 0),
    ]


def svg_ib3c_event_overlays(
    events: pd.DataFrame,
    route_len: float,
    left: float,
    right: float,
    panels: dict,
) -> str:
    if events is None or events.empty:
        return ""

    parts = ['<g id="ib3c-event-overlays">']

    # 先畫在 speed / HR / QA 三個 1D panels 上。
    overlay_panels = ["speed", "hr", "qa"]

    for _, row in events.iterrows():
        event_type = str(row.get("event_type", ""))
        color = EVENT_COLOR.get(event_type, "#334155")

        start_dist = pd.to_numeric(row.get("start_route_dist_m", np.nan), errors="coerce")
        end_dist = pd.to_numeric(row.get("end_route_dist_m", np.nan), errors="coerce")

        # terminal_artifact 或 off-route 事件常可能 route_dist 為 NaN，
        # 先退回 start/end elapsed 無法直接畫在 route axis；第一版只畫有 route distance 的事件。
        if not np.isfinite(start_dist) and not np.isfinite(end_dist):
            continue

        if not np.isfinite(start_dist):
            start_dist = end_dist
        if not np.isfinite(end_dist):
            end_dist = start_dist

        x1 = left + max(0.0, min(float(start_dist), route_len)) / route_len * (right - left)
        x2 = left + max(0.0, min(float(end_dist), route_len)) / route_len * (right - left)

        if x2 < x1:
            x1, x2 = x2, x1

        width = max(x2 - x1, 3.0)

        tooltip = svg_title(event_tooltip_rows(row))

        for panel_key in overlay_panels:
            top, bottom = panels[panel_key]
            parts.append(
                f'<rect x="{x1:.1f}" y="{top:.1f}" width="{width:.1f}" height="{bottom - top:.1f}" '
                f'fill="{color}" opacity="0.10" stroke="{color}" stroke-width="0.6" stroke-dasharray="4 3">'
                f'{tooltip}</rect>'
            )

        label_y = panels["speed"][0] + 10
        label_x = x1 + width / 2.0
        label = event_type.replace("_", " ")
        if width >= 28:
            parts.append(
                f'<text x="{label_x:.1f}" y="{label_y:.1f}" text-anchor="middle" '
                f'class="event-label" fill="{color}">{html.escape(label)}</text>'
            )
        else:
            parts.append(
                f'<circle cx="{label_x:.1f}" cy="{label_y:.1f}" r="3.5" fill="{color}" opacity="0.85">'
                f'{tooltip}</circle>'
            )

    parts.append("</g>")
    return "".join(parts)




def write_html(
    out_html: Path,
    df: pd.DataFrame,
    route: pd.DataFrame,
    anchors: pd.DataFrame,
    segments: list[dict],
    events: pd.DataFrame | None = None,
) -> None: 
    df_time = sort_activity_time_order(df)
    df_1d = build_one_d_profile(df, route)
    route_len = float(max(route["dist_m"].max(), df["route_dist_m"].max(), 1.0))
    w, h = 1280, 1400
    left, right = 78, 1220
    panels = {
        "ele": (42, 205),
        "speed": (242, 365),
        "hr": (402, 525),
        "qa": (562, 640),
        "map": (690, 1350),
    }

    parts = []
    parts.append(f'<svg id="board" viewBox="0 0 {w} {h}" role="img">')
    parts.append(f'<rect x="0" y="0" width="{w}" height="{h}" fill="#f8fafc"/>')

    for key, (top, bottom) in panels.items():
        parts.append(f'<text x="{left}" y="{top - 14}" class="panel-title">{html.escape(panel_title(key))}</text>')
        parts.append(f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" class="axis"/>')
        parts.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" class="axis"/>')
        if key != "map":
            for seg in segments:
                x1 = left + seg["start_m"] / route_len * (right - left)
                x2 = left + seg["end_m"] / route_len * (right - left)
                parts.append(
                    f'<rect x="{x1:.1f}" y="{top}" width="{max(x2 - x1, 0):.1f}" height="{bottom - top}" '
                    f'fill="{seg["color"]}" opacity="0.075"/>'
                )

    route_xs = scale_x(route["dist_m"], route_len, left, right)
    activity_xs = scale_x(df["route_dist_m"], route_len, left, right)
    profile_xs = scale_x(df_1d["route_bin_m"], route_len, left, right)
    ele_values = pd.concat(
        [
            pd.to_numeric(route.get("ele_gpx_m", pd.Series(dtype=float)), errors="coerce"),
            pd.to_numeric(route.get("ele_smooth", pd.Series(dtype=float)), errors="coerce"),
            pd.to_numeric(df.get("raw_ele_m", pd.Series(dtype=float)), errors="coerce"),
        ],
        ignore_index=True,
    ).dropna()
    ele_min = float(ele_values.quantile(0.01)) if not ele_values.empty else 0.0
    ele_max = float(ele_values.quantile(0.99)) if not ele_values.empty else 1.0
    y_raw = scale_with_bounds(route["ele_gpx_m"], panels["ele"][0], panels["ele"][1], ele_min, ele_max)
    parts.append(svg_polyline_breaks(route_xs, y_raw, "#1f2937", 1.4, 0.75))
    activity_ele_y = scale_with_bounds(df["raw_ele_m"], panels["ele"][0], panels["ele"][1], ele_min, ele_max)
    parts.append(svg_scatter(activity_xs, activity_ele_y, "#64748b", 1.15, 0.12))
    if {"contour_elev_mid_m", "contour_elev_min_m", "contour_elev_max_m"}.issubset(route.columns):
        y_mid = scale_with_bounds(route["contour_elev_mid_m"], panels["ele"][0], panels["ele"][1], ele_min, ele_max)
        y_low = scale_with_bounds(route["contour_elev_min_m"], panels["ele"][0], panels["ele"][1], ele_min, ele_max)
        y_high = scale_with_bounds(route["contour_elev_max_m"], panels["ele"][0], panels["ele"][1], ele_min, ele_max)
        band = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(route_xs, y_low))
        band += " " + " ".join(f"{x:.1f},{y:.1f}" for x, y in reversed(list(zip(route_xs, y_high))))
        parts.append(f'<polygon points="{band}" fill="#38bdf8" opacity="0.20"/>')
        parts.append(svg_polyline_breaks(route_xs, y_mid, "#0284c7", 1.5, 1.0, "6 4"))
    if "ele_smooth" in route.columns:
        y_corr = scale_with_bounds(route["ele_smooth"], panels["ele"][0], panels["ele"][1], ele_min, ele_max)
        parts.append(svg_polyline_breaks(route_xs, y_corr, "#16a34a", 1.2, 0.95))

    y_speed_raw = scale_with_bounds(df["forward_speed_route_mps_raw"], panels["speed"][0], panels["speed"][1], 0.0, 3.0)
    y_speed_smooth = scale_with_bounds(df_1d["forward_speed_route_mps_smooth_median"], panels["speed"][0], panels["speed"][1], 0.0, 3.0)
    parts.append(svg_scatter(activity_xs, y_speed_raw, "#94a3b8", 1.1, 0.14))
    parts.append(svg_polyline_breaks(profile_xs, y_speed_smooth, "#2563eb", 1.8, 0.95))
    if "heart_rate_bpm" in df.columns:
        hr_values = pd.to_numeric(df["heart_rate_bpm"], errors="coerce").dropna()
        hr_min = max(40.0, float(hr_values.quantile(0.01)) - 5) if not hr_values.empty else 40.0
        hr_max = min(220.0, float(hr_values.quantile(0.99)) + 5) if not hr_values.empty else 220.0
        y_hr = scale_with_bounds(df_1d["heart_rate_bpm_median"], panels["hr"][0], panels["hr"][1], hr_min, hr_max)
        parts.append(svg_polyline_breaks(profile_xs, y_hr, "#dc2626", 1.5, 0.9))

    offset_clipped = df_1d["offset_onroute_median"].clip(lower=0, upper=30)
    y_offset = (
        panels["qa"][1]
        - offset_clipped / 30 * (panels["qa"][1] - panels["qa"][0])
    ).tolist()
    parts.append(svg_polyline_breaks(profile_xs, y_offset, "#334155", 1.3, 0.9))
    if "offset_all_p90" in df_1d.columns:
        y_offset_p90 = (
            panels["qa"][1]
            - df_1d["offset_all_p90"].clip(lower=0, upper=30) / 30 * (panels["qa"][1] - panels["qa"][0])
        ).tolist()
        parts.append(svg_polyline_breaks(profile_xs, y_offset_p90, "#64748b", 1.0, 0.7, "5 4"))
    for ref, color in [(10, "#f59e0b"), (25, "#dc2626")]:
        y = panels["qa"][1] - (ref / 30) * (panels["qa"][1] - panels["qa"][0])
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" stroke="{color}" stroke-dasharray="6 4" opacity="0.7"/>')

    for _, row in df[df["is_stationary"]].iloc[:: max(len(df) // 450, 1)].iterrows():
        x = left + float(row["route_dist_m"]) / route_len * (right - left)
        parts.append(f'<circle cx="{x:.1f}" cy="{panels["speed"][1] - 8}" r="2" fill="#111827" opacity="0.25"/>')

    for _, row in df[~df["usable_on_route"]].iloc[:: max(len(df) // 700, 1)].iterrows():
        x = left + float(row["route_dist_m"]) / route_len * (right - left)
        color = LABEL_COLOR.get(str(row["manual_interpretation"]), "#dc2626")
        parts.append(f'<circle cx="{x:.1f}" cy="{panels["qa"][0] + 10}" r="2.4" fill="{color}" opacity="0.55"/>')
    
    parts.append(svg_ib3c_event_overlays(events, route_len, left, right, panels))

    route_map = route.dropna(subset=["x_m", "y_m", "dist_m"]).copy()
    map_left, map_right = left, right
    map_top, map_bottom = panels["map"]
    minx, maxx = route_map["x_m"].min(), route_map["x_m"].max()
    miny, maxy = route_map["y_m"].min(), route_map["y_m"].max()
    pad = 60
    sx = (map_right - map_left - pad * 2) / max(maxx - minx, 1)
    sy = (map_bottom - map_top - pad * 2) / max(maxy - miny, 1)
    sm = min(sx, sy)

    def mx(v: float) -> float:
        return map_left + pad + (v - minx) * sm

    def my(v: float) -> float:
        return map_bottom - pad - (v - miny) * sm

    for coords, color, seg in build_route_line_segments(route_map, segments):
        pts = " ".join(f"{mx(x):.1f},{my(y):.1f}" for x, y in coords)
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="6" opacity="0.9" stroke-linecap="round"/>')
    parts.append(svg_map_polyline(df_time, "x_m", "y_m", mx, my, "#94a3b8", 1.0, 0.55))
    if {"matched_x_m", "matched_y_m"}.issubset(df.columns):
        parts.append(svg_map_polyline(df_time, "matched_x_m", "matched_y_m", mx, my, "#111827", 1.2, 0.42))
    for interp, g in df_time[~df_time["usable_on_route"]].groupby("manual_interpretation", dropna=False):
        color = LABEL_COLOR.get(str(interp), "#dc2626")
        parts.append(svg_map_polyline(g, "x_m", "y_m", mx, my, color, 2.2, 0.76))

    if not route_map.empty:
        start = route_map.sort_values("dist_m").iloc[0]
        end = route_map.sort_values("dist_m").iloc[-1]
        parts.append(f'<circle cx="{mx(float(start["x_m"])):.1f}" cy="{my(float(start["y_m"])):.1f}" r="7" fill="#16a34a" stroke="#fff" stroke-width="2"/>')
        parts.append(f'<text x="{mx(float(start["x_m"])) + 10:.1f}" y="{my(float(start["y_m"])) - 8:.1f}" class="small-label">start</text>')
        parts.append(f'<rect x="{mx(float(end["x_m"])) - 6:.1f}" y="{my(float(end["y_m"])) - 6:.1f}" width="12" height="12" fill="#dc2626" stroke="#fff" stroke-width="2"/>')
        parts.append(f'<text x="{mx(float(end["x_m"])) + 10:.1f}" y="{my(float(end["y_m"])) - 8:.1f}" class="small-label">end</text>')

    if not anchors.empty:
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:3826", always_xy=True)
        ax, ay = transformer.transform(anchors["ref_lon"].astype(float).values, anchors["ref_lat"].astype(float).values)
        for x, y, (_, row) in zip(ax, ay, anchors.iterrows()):
            label = f"{row.get('anchor_role', 'waypoint')} waypoint"
            parts.append(f'<circle cx="{mx(x):.1f}" cy="{my(y):.1f}" r="5" fill="#111827" stroke="#fff" stroke-width="1.5"/>')
            parts.append(f'<text x="{mx(x) + 8:.1f}" y="{my(y) - 5:.1f}" class="small-label">{html.escape(label)}</text>')

    parts.append(svg_route_hit_targets(route_map, mx, my))
    parts.append(svg_activity_hit_targets(df_time, mx, my))

    for seg in segments:
        x = left + seg["start_m"] / route_len * (right - left)
        parts.append(f'<text x="{x + 3:.1f}" y="{panels["qa"][1] + 18}" class="tick">{seg["start_m"] / 1000:.2f} km</text>')

    legend = [
        ("GPX raw elevation", "#1f2937"),
        ("NLSC midpoint", "#0284c7"),
        ("speed smooth", "#2563eb"),
        ("heart rate", "#dc2626"),
        ("raw trajectory", "#94a3b8"),
        ("excluded/manual labels", "#dc2626"),
    ]
    lx = left
    for i, (label, color) in enumerate(legend):
        x = lx + i * 175
        parts.append(f'<line x1="{x}" y1="1380" x2="{x + 22}" y2="1380" stroke="{color}" stroke-width="3"/>')
        parts.append(f'<text x="{x + 28}" y="1384" class="legend">{html.escape(label)}</text>')

    hover_rows = make_hover_rows(df, route_map, left, right, route_len)
    route_cursor_rows = make_route_cursor_rows(route_map, mx, my)
    parts.append('<line id="cursor" x1="0" y1="38" x2="0" y2="640" stroke="#0f172a" stroke-width="1.2" opacity="0" pointer-events="none"/>')
    parts.append('<g id="map-cursor" opacity="0" pointer-events="none">')
    parts.append(f'<line id="map-cursor-v" x1="0" y1="{map_top}" x2="0" y2="{map_bottom}" stroke="#0f172a" stroke-width="1" stroke-dasharray="5 4" opacity="0.55"/>')
    parts.append(f'<line id="map-cursor-h" x1="{map_left}" y1="0" x2="{map_right}" y2="0" stroke="#0f172a" stroke-width="1" stroke-dasharray="5 4" opacity="0.55"/>')
    parts.append('<circle id="map-cursor-dot" cx="0" cy="0" r="7" fill="#f97316" stroke="#fff" stroke-width="2.2"/>')
    parts.append('<circle id="map-cursor-ring" cx="0" cy="0" r="13" fill="none" stroke="#f97316" stroke-width="2" opacity="0.65"/>')
    parts.append('<text id="map-cursor-label" x="0" y="0" class="cursor-label"></text>')
    parts.append('</g>')
    parts.append('<rect id="hover-zone" x="70" y="38" width="1160" height="605" fill="transparent"/>')
    parts.append("</svg>")

    html_text = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8"/>
<title>Activity Profile 1D + 2D - qixing_lengshuikeng 37_1</title>
<style>
body {{ margin: 0; background: #e5e7eb; font-family: Arial, 'Microsoft JhengHei', sans-serif; color: #111827; }}
.wrap {{ max-width: 1280px; margin: 0 auto; padding: 16px; }}
#board {{ width: 100%; height: auto; background: #f8fafc; box-shadow: 0 10px 30px rgba(15,23,42,0.14); }}
.axis {{ stroke: #475569; stroke-width: 1; opacity: 0.65; }}
.panel-title {{ font-weight: 700; font-size: 15px; fill: #111827; }}
.small-label {{ font-size: 11px; fill: #111827; paint-order: stroke; stroke: #fff; stroke-width: 3px; }}
.tick {{ font-size: 10px; fill: #475569; }}
.legend {{ font-size: 12px; fill: #334155; }}
.event-label {{ font-size: 9px; font-weight: 700; paint-order: stroke; stroke: #fff; stroke-width: 3px; }}
.cursor-label {{ font-size: 12px; fill: #111827; font-weight: 700; paint-order: stroke; stroke: #fff; stroke-width: 4px; }}
#tip {{ position: fixed; pointer-events: none; opacity: 0; background: rgba(15,23,42,0.94); color: #fff; padding: 8px 10px; border-radius: 6px; font-size: 12px; line-height: 1.35; max-width: 300px; }}
</style>
</head>
<body>
<div class="wrap">
{''.join(parts)}
</div>
<div id="tip"></div>
<script>
const rows = {json.dumps(hover_rows, ensure_ascii=False)};
const routeRows = {json.dumps(route_cursor_rows, ensure_ascii=False)};
const cursor = document.getElementById('cursor');
const mapCursor = document.getElementById('map-cursor');
const mapCursorV = document.getElementById('map-cursor-v');
const mapCursorH = document.getElementById('map-cursor-h');
const mapCursorDot = document.getElementById('map-cursor-dot');
const mapCursorRing = document.getElementById('map-cursor-ring');
const mapCursorLabel = document.getElementById('map-cursor-label');
const zone = document.getElementById('hover-zone');
const tip = document.getElementById('tip');
function nearest(x) {{
  let best = rows[0], d = Math.abs(rows[0].x - x);
  for (const r of rows) {{
    const nd = Math.abs(r.x - x);
    if (nd < d) {{ best = r; d = nd; }}
  }}
  return best;
}}
function nearestRoute(dist) {{
  let best = routeRows[0], d = Math.abs(routeRows[0].dist - dist);
  for (const r of routeRows) {{
    const nd = Math.abs(r.dist - dist);
    if (nd < d) {{ best = r; d = nd; }}
  }}
  return best;
}}
function setMapCursor(r) {{
  const m = nearestRoute(r.dist);
  mapCursor.setAttribute('opacity', '1');
  mapCursorV.setAttribute('x1', m.x);
  mapCursorV.setAttribute('x2', m.x);
  mapCursorH.setAttribute('y1', m.y);
  mapCursorH.setAttribute('y2', m.y);
  mapCursorDot.setAttribute('cx', m.x);
  mapCursorDot.setAttribute('cy', m.y);
  mapCursorRing.setAttribute('cx', m.x);
  mapCursorRing.setAttribute('cy', m.y);
  mapCursorLabel.setAttribute('x', m.x + 14);
  mapCursorLabel.setAttribute('y', m.y - 14);
  mapCursorLabel.textContent = `${{(m.dist / 1000).toFixed(3)}} km / route_idx=${{m.route_point_index}}`;
  const title = mapCursor.querySelector('title') || document.createElementNS('http://www.w3.org/2000/svg', 'title');
  title.textContent = `nearest_route_point_index = ${{m.route_point_index}}\ndist_m = ${{m.dist.toFixed(3)}}\ndist_km = ${{(m.dist / 1000).toFixed(3)}}`;
  if (!title.parentNode) mapCursor.appendChild(title);
}}
zone.addEventListener('mousemove', (ev) => {{
  const svg = document.getElementById('board');
  const pt = svg.createSVGPoint();
  pt.x = ev.clientX; pt.y = ev.clientY;
  const p = pt.matrixTransform(svg.getScreenCTM().inverse());
  const r = nearest(p.x);
  cursor.setAttribute('x1', r.x);
  cursor.setAttribute('x2', r.x);
  cursor.setAttribute('opacity', '0.85');
  setMapCursor(r);
  tip.style.opacity = 1;
  tip.style.left = (ev.clientX + 14) + 'px';
  tip.style.top = (ev.clientY + 14) + 'px';
  tip.innerHTML = r.html;
}});
zone.addEventListener('mouseleave', () => {{
  cursor.setAttribute('opacity', '0');
  mapCursor.setAttribute('opacity', '0');
  tip.style.opacity = 0;
}});
</script>
</body>
</html>
"""
    out_html.write_text(html_text, encoding="utf-8")


def panel_title(key: str) -> str:
    return {
        "ele": "Panel 1: elevation comparison",
        "speed": "Panel 2: speed",
        "hr": "Panel 3: heart rate",
        "qa": "Panel 4: offset / mapmatching quality",
        "map": "Panel 5: 2D route map",
    }[key]


def svg_map_polyline(df: pd.DataFrame, x_col: str, y_col: str, mx, my, color: str, width: float, opacity: float) -> str:
    pts = []
    for _, r in df.dropna(subset=[x_col, y_col]).iterrows():
        pts.append(f"{mx(float(r[x_col])):.1f},{my(float(r[y_col])):.1f}")
    return f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="{width}" opacity="{opacity}"/>'


def svg_route_hit_targets(route_map: pd.DataFrame, mx, my) -> str:
    parts = ['<g id="route-point-hit-targets">']
    for _, r in route_map.dropna(subset=["x_m", "y_m", "dist_m"]).iterrows():
        parts.append(
            f'<circle cx="{mx(float(r["x_m"])):.1f}" cy="{my(float(r["y_m"])):.1f}" '
            'r="4.5" fill="#ffffff" opacity="0.001" stroke="none">'
            f"{svg_title(route_point_tooltip_rows(r))}</circle>"
        )
    parts.append("</g>")
    return "".join(parts)


def svg_activity_hit_targets(df: pd.DataFrame, mx, my) -> str:
    parts = ['<g id="activity-point-hit-targets">']
    for _, r in df.dropna(subset=["x_m", "y_m"]).iterrows():
        parts.append(
            f'<circle cx="{mx(float(r["x_m"])):.1f}" cy="{my(float(r["y_m"])):.1f}" '
            'r="3.8" fill="#ffffff" opacity="0.001" stroke="none">'
            f"{svg_title(activity_tooltip_rows(r))}</circle>"
        )
    parts.append("</g>")
    return "".join(parts)


def resolve_ib3c_events_csv(args: argparse.Namespace) -> Path:
    if args.events_csv is not None:
        return resolve_path(args.events_csv)

    return (
        resolve_path(args.ib3c_root)
        / args.route_folder
        / args.activity_id
        / f"{args.route_folder}_{args.activity_id}_ib3c_behavior_events.csv"
    )


def load_ib3c_events(args: argparse.Namespace) -> pd.DataFrame:
    if not getattr(args, "show_events", False):
        return pd.DataFrame()

    fp = resolve_ib3c_events_csv(args)
    if not fp.exists():
        print(f"warning: IB3C events CSV not found: {fp}")
        return pd.DataFrame()

    events = pd.read_csv(fp, encoding="utf-8-sig")
    events.columns = [str(c).strip() for c in events.columns]

    for c in [
        "event_id",
        "start_elapsed_sec",
        "end_elapsed_sec",
        "duration_sec",
        "start_route_dist_m",
        "end_route_dist_m",
        "max_offset_m",
        "max_hr_bpm",
        "confidence",
    ]:
        if c in events.columns:
            events[c] = pd.to_numeric(events[c], errors="coerce")

    return events


def make_hover_rows(
    df: pd.DataFrame,
    route_map: pd.DataFrame,
    left: float,
    right: float,
    route_len: float,
) -> list[dict]:
    route_axis = route_map.dropna(subset=["dist_m"]).sort_values("dist_m").copy()
    if route_axis.empty:
        route_axis = pd.DataFrame({"dist_m": [0.0], "route_point_index": [0]})
    sample = route_axis.iloc[:: max(len(route_axis) // 900, 1)].copy()
    summit_dist = route_axis.loc[pd.to_numeric(route_axis.get("ele_smooth", pd.Series(index=route_axis.index)), errors="coerce").idxmax(), "dist_m"] if "ele_smooth" in route_axis.columns and route_axis["ele_smooth"].notna().any() else np.nan
    rows = []
    for _, r in sample.iterrows():
        dist = float(r.get("dist_m", 0))
        activity_ref = nearest_activity_by_route_dist(df, dist)
        warning = ""
        if np.isfinite(summit_dist) and abs(dist - float(summit_dist)) <= 700:
            warning = "Route-distance based activity lookup may be ambiguous in summit/self-near sections; use 2D raw activity point popup for manual override index."
        bits = [
            ("route_point_index", r.get("route_point_index", r.name), 0),
            ("route_phase", r.get("route_phase", ""), 0),
            ("dist_to_summit_m", r.get("dist_to_summit_m", ""), 3),
            ("route_dist_m", dist, 3),
            ("route_dist_km", dist / 1000.0, 3),
            ("nearest_activity_row_index_by_route_dist", activity_ref.get("row_index", ""), 0),
            ("activity_row_index_note", "reference only; activity row lookup may jump in out-and-back / self-near sections", 0),
            ("point_index", activity_ref.get("point_index", ""), 0),
            ("subject_id", activity_ref.get("subject_id", ""), 0),
            ("trial_id", activity_ref.get("trial_id", ""), 0),
            ("elapsed_sec", activity_ref.get("elapsed_sec", ""), 1),
            ("usable_on_route", activity_ref.get("usable_on_route", ""), 0),
            ("manual_label", activity_ref.get("manual_label", ""), 0),
            ("excluded_reason", activity_ref.get("excluded_reason", ""), 0),
            ("manual_interpretation", activity_ref.get("manual_interpretation", ""), 0),
            ("mapmatch_branch_jump_warning", activity_ref.get("mapmatch_branch_jump_warning", ""), 0),
            ("speed_mapmatch_jump_flag", activity_ref.get("speed_mapmatch_jump_flag", ""), 0),
            ("route_phase_jump_flag", activity_ref.get("route_phase_jump_flag", ""), 0),
            ("mapmatch_branch_ambiguity_flag", activity_ref.get("mapmatch_branch_ambiguity_flag", ""), 0),
            ("stationary_gps_drift_flag", activity_ref.get("stationary_gps_drift_flag", ""), 0),
            ("stationary_duration_sec", activity_ref.get("stationary_duration_sec", ""), 1),
            ("self_near_warning", warning, 0),
            ("manual_override_index_note", "use 2D raw activity point popup activity_row_index for manual override start/end", 0),
        ]
        rows.append(
            {
                "x": left + dist / route_len * (right - left),
                "dist": dist,
                "html": html_lines(bits),
            }
        )
    return rows


def nearest_activity_by_route_dist(df: pd.DataFrame, dist_m: float) -> pd.Series:
    if df.empty or "route_dist_m" not in df.columns:
        return pd.Series(dtype=object)
    dist = pd.to_numeric(df["route_dist_m"], errors="coerce")
    valid = dist.notna()
    if not valid.any():
        return pd.Series(dtype=object)
    idx = (dist[valid] - dist_m).abs().idxmin()
    return df.loc[idx]


def make_route_cursor_rows(route_map: pd.DataFrame, mx, my) -> list[dict]:
    rows = []
    if route_map.empty:
        return [{"dist": 0.0, "x": 0.0, "y": 0.0}]
    route_small = route_map.dropna(subset=["dist_m", "x_m", "y_m"]).sort_values("dist_m")
    for _, r in route_small.iterrows():
        rows.append(
            {
                "dist": float(r["dist_m"]),
                "x": float(mx(float(r["x_m"]))),
                "y": float(my(float(r["y_m"]))),
                "route_point_index": int(r.get("route_point_index", r.name)),
            }
        )
    return rows


def write_plot_data(out_csv: Path, df: pd.DataFrame) -> None:
    cols = [
        "route_folder",
        "case_id",
        "subject_id",
        "trial_id",
        "activity_id",
        "row_index",
        "point_index",
        "elapsed_sec",
        "raw_lat",
        "raw_lon",
        "matched_lat",
        "matched_lon",
        "route_dist_m",
        "projected_route_dist_m",
        "reliable_route_dist_m",
        "route_progress_reliable",
        "route_progress_state",
        "route_projection_confidence",
        "route_projection_note",
        "candidate_phase",
        "summit_dist_m",
        "summit_reached_flag",
        "summit_transition_lock_applied",
        "summit_transition_release_flag",
        "route_point_index",
        "route_phase",
        "previous_route_phase",
        "dist_to_summit_m",
        "route_point_index_delta_full",
        "route_dist_delta_m_full",
        "elapsed_delta_sec_full",
        "raw_ele_m",
        "ele_smooth",
        "contour_elev_min_m",
        "contour_elev_mid_m",
        "contour_elev_max_m",
        "speed_usable_segment_id",
        "forward_delta_route_dist_m",
        "forward_delta_route_point_index",
        "forward_speed_route_mps_raw",
        "forward_speed_route_mps_raw_uncapped",
        "forward_speed_route_mps_smooth",
        "speed_source",
        "speed_input_source",
        "speed_base_dist_col",
        "speed_continuous_segment_id",
        "speed_negative_delta_flag",
        "speed_invalid_dt_flag",
        "speed_gap_break_flag",
        "speed_route_dist_jump_flag",
        "speed_route_point_index_jump_flag",
        "speed_mapmatch_jump_flag",
        "speed_summit_transition_release_break_flag",
        "mapmatch_branch_jump_warning",
        "route_phase_jump_flag",
        "mapmatch_branch_ambiguity_flag",
        "route_phase_jump_flag_full",
        "mapmatch_branch_ambiguity_flag_full",
        "stationary_gps_drift_flag",
        "stationary_gps_drift_segment_id",
        "stationary_duration_sec",
        "stationary_route_dist_range_m",
        "stationary_gps_spread_m",
        "stationary_hr_delta_bpm",
        "stationary_hr_recovery_hint",
        "speed_capped_flag",
        "heart_rate_bpm",
        "offset_to_mainline_m",
        "match_quality",
        "is_stationary",
        "usable_on_route",
        "excluded_reason",
        "excursion_id",
        "manual_override_applied",
        "manual_label",
        "manual_interpretation",
        "segment_role",
    ]
    cols = [c for c in cols if c in df.columns]
    cols = list(dict.fromkeys(cols))
    df[cols].to_csv(out_csv, index=False, encoding="utf-8-sig")


def write_summary(
    out_summary: Path,
    df: pd.DataFrame,
    segments: list[dict],
    mapmatched_root: Path,
    ib3a2_root: Path,
    events: pd.DataFrame | None = None,
    events_csv: Path | None = None,
) -> None:
    one_d_profile_row_count = int(np.floor(max(pd.to_numeric(df["route_dist_m"], errors="coerce").max(), 0) / ONE_D_PROFILE_BIN_M) + 1)
    speed_source = df["speed_source"].dropna().astype(str).mode()
    speed_source_value = speed_source.iloc[0] if not speed_source.empty else "unknown"
    speed_input_source = df["speed_input_source"].dropna().astype(str).mode()
    speed_input_source_value = speed_input_source.iloc[0] if not speed_input_source.empty else "unknown"
    base_dist = df["speed_base_dist_col"].dropna().astype(str).mode()
    base_dist_value = base_dist.iloc[0] if not base_dist.empty else ""
    self_near_detected = detect_self_near_ambiguous_zone(df)
    self_near_jump_count = int((df["speed_mapmatch_jump_flag"] & df["route_dist_m"].between(1400, 2700)).sum())
    stationary_count = int(df["stationary_gps_drift_flag"].sum())
    summit_transition_release_count = (
        int(to_bool_series(df["summit_transition_release_flag"]).sum())
        if "summit_transition_release_flag" in df.columns
        else 0
    )
    speed_summit_transition_release_break_count = (
        int(df["speed_summit_transition_release_break_flag"].fillna(False).sum())
        if "speed_summit_transition_release_break_flag" in df.columns
        else 0
    )
    stationary_segment_count = int(df["stationary_gps_drift_segment_id"].dropna().nunique())
    stationary_duration = pd.to_numeric(df["stationary_duration_sec"], errors="coerce").dropna()
    stationary_total_duration = (
        df[df["stationary_gps_drift_flag"]]
        .groupby("stationary_gps_drift_segment_id")["stationary_duration_sec"]
        .max()
        .sum()
    )
    phase_jump_count = int(df["route_phase_jump_flag"].sum()) if "route_phase_jump_flag" in df.columns else 0
    branch_ambiguity_count = (
        int(df["mapmatch_branch_ambiguity_flag"].sum()) if "mapmatch_branch_ambiguity_flag" in df.columns else 0
    )
    phase_jump_full_count = (
        int(df["route_phase_jump_flag_full"].sum()) if "route_phase_jump_flag_full" in df.columns else phase_jump_count
    )
    branch_ambiguity_full_count = (
        int(df["mapmatch_branch_ambiguity_flag_full"].sum())
        if "mapmatch_branch_ambiguity_flag_full" in df.columns
        else branch_ambiguity_count
    )
    trajectory_order = sort_activity_time_order(df)
    one_d_speed_valid_mask = df["usable_on_route"].fillna(False)
    for flag_col in [
        "speed_mapmatch_jump_flag",
        "speed_summit_transition_release_break_flag",
        "stationary_gps_drift_flag",
        "speed_gap_break_flag",
        "speed_invalid_dt_flag",
        "speed_negative_delta_flag",
    ]:
        if flag_col in df.columns:
            one_d_speed_valid_mask = one_d_speed_valid_mask & ~df[flag_col].fillna(False)
    row_index_monotonic = (
        bool(pd.to_numeric(trajectory_order["row_index"], errors="coerce").is_monotonic_increasing)
        if "row_index" in trajectory_order.columns
        else False
    )
    elapsed_monotonic = (
        bool(pd.to_numeric(trajectory_order["elapsed_sec"], errors="coerce").is_monotonic_increasing)
        if "elapsed_sec" in trajectory_order.columns
        else False
    )
    merge_preserves_activity_order = (
        bool(pd.to_numeric(df["row_index"], errors="coerce").is_monotonic_increasing)
        if "row_index" in df.columns
        else elapsed_monotonic
    )
    lines = [
        "activity_profile_1d_2d_summary",
        f"rows: {len(df)}",
        f"segments_250m: {len(segments)}",
        f"ib3c_events_csv: {events_csv if events_csv is not None else ''}",
        f"ib3c_events_loaded: {0 if events is None else len(events)}",
        f"mapmatched_root: {Path(mapmatched_root).as_posix()}",
        f"ib3a2_root: {Path(ib3a2_root).as_posix()}",
        f"legacy_ib3a2_labeled_flow: {use_legacy_ib3a2_flow(mapmatched_root)}",
        f"speed_input_source: {speed_input_source_value}",
        f"speed_source: {speed_source_value}",
        f"speed_base_dist_col: {base_dist_value}",
        "speed_semantics: forward speed along common route axis, not device raw GPS speed",
        "df_order_for_2d_trajectory: elapsed_sec / row_index",
        f"one_d_profile_bin_m: {ONE_D_PROFILE_BIN_M:g}",
        f"one_d_profile_row_count: {one_d_profile_row_count}",
        "one_d_profile_source: route_distance_binned_activity",
        f"one_d_speed_valid_input_rows: {int(one_d_speed_valid_mask.sum())}",
        "one_d_speed_filter: usable_on_route and not speed_mapmatch_jump/summit_transition_release/stationary_gps_drift/speed_gap_break/speed_invalid_dt/speed_negative_delta",
        "one_d_offset_source: on-route median plus all-activity p90",
        "two_d_trajectory_order: elapsed_sec / row_index",
        f"merge_route_context_preserves_activity_order: {merge_preserves_activity_order}",
        f"2D trajectory row_index monotonic: {row_index_monotonic}",
        f"2D trajectory elapsed_sec monotonic: {elapsed_monotonic}",
        f"speed_gap_threshold_sec: {SPEED_GAP_THRESHOLD_SEC:g}",
        "speed_gap_break_criteria: first row, row_index discontinuity, elapsed_sec/timestamp_s gap > threshold, or segment_role change",
        f"speed_segment_count: {int(df['speed_usable_segment_id'].dropna().nunique())}",
        f"speed_continuous_segment_count: {int(df['speed_continuous_segment_id'].dropna().nunique())}",
        f"speed_gap_break_count: {int(df['speed_gap_break_flag'].sum())}",
        f"speed_negative_delta_count: {int(df['speed_negative_delta_flag'].sum())}",
        f"speed_capped_count: {int(df['speed_capped_flag'].sum())}",
        f"route_dist_jump_count: {int(df['speed_route_dist_jump_flag'].sum())}",
        f"route_point_index_jump_count: {int(df['speed_route_point_index_jump_flag'].sum())}",
        f"speed_mapmatch_jump_count: {int(df['speed_mapmatch_jump_flag'].sum())}",
        f"summit_transition_release_count: {summit_transition_release_count}",
        f"speed_summit_transition_release_break_count: {speed_summit_transition_release_break_count}",
        f"self_near_mapmatch_jump_count: {self_near_jump_count}",
        f"self_near_ambiguous_zone_detected: {self_near_detected}",
        f"route_phase_window_m: {SUMMIT_SELF_NEAR_WINDOW_M:g}",
        f"route_phase_jump_count: {phase_jump_count}",
        f"mapmatch_branch_ambiguity_count: {branch_ambiguity_count}",
        f"route_phase_jump_full_activity_count: {phase_jump_full_count}",
        f"mapmatch_branch_ambiguity_full_activity_count: {branch_ambiguity_full_count}",
        f"stationary_gps_drift_count: {stationary_count}",
        f"stationary_gps_drift_segment_count: {stationary_segment_count}",
        f"stationary_gps_drift_total_duration_sec: {fmt_value(stationary_total_duration, 1)}",
        f"stationary_gps_drift_max_segment_duration_sec: {fmt_value(stationary_duration.max() if not stationary_duration.empty else np.nan, 1)}",
        f"stationary_gps_drift_window_sec: {STATIONARY_GPS_DRIFT_WINDOW_SEC:g}",
        f"stationary_gps_drift_min_span_sec: {STATIONARY_GPS_DRIFT_MIN_SPAN_SEC:g}",
        f"stationary_gps_drift_route_range_threshold_m: {STATIONARY_GPS_DRIFT_ROUTE_RANGE_M:g}",
        f"stationary_gps_drift_spread_threshold_m: {STATIONARY_GPS_DRIFT_SPREAD_M:g}",
        f"stationary_gps_drift_spike_threshold_mps: {STATIONARY_GPS_DRIFT_SPIKE_MPS:g}",
        f"speed_invalid_dt_rows: {int(df['speed_invalid_dt_flag'].sum())}",
        f"speed_cap_mps: {SPEED_CAP_MPS:g}",
        f"speed_route_dist_jump_threshold_m: {SPEED_ROUTE_DIST_JUMP_THRESHOLD_M:g}",
        f"speed_route_point_index_jump_threshold: {SPEED_ROUTE_POINT_INDEX_JUMP_THRESHOLD:g}",
        "speed_smooth: rolling median, 21 samples, centered, min_periods=5",
        "html_tooltip_activity_index_enabled: True",
        "html_tooltip_route_point_index_enabled: True",
        "nearest_activity_lookup_method: 1D hover uses route axis rows as primary; nearest_activity_row_index_by_route_dist is reference only and may jump in self-near sections",
        "nearest_route_point_lookup_method: 2D cursor uses nearest route axis point by route_dist_m",
        "manual_override_index_method: use 2D raw activity point popup activity_row_index; do not use route cursor nearest activity reference",
        "",
        "match_quality:",
        df["match_quality"].value_counts(dropna=False).to_string(),
        "",
        "usable_on_route:",
        df["usable_on_route"].value_counts(dropna=False).to_string(),
    ]
    
    if events is not None and not events.empty and "event_type" in events.columns:
        lines += [
            "",
            "ib3c_event_type_counts:",
            events["event_type"].value_counts(dropna=False).to_string(),
        ]

    if events is not None and not events.empty:
        keep = [
            "event_id",
            "event_type",
            "event_subtype",
            "start_elapsed_sec",
            "end_elapsed_sec",
            "duration_sec",
            "start_route_dist_m",
            "end_route_dist_m",
            "rest_duration_tier",
            "recovery_level",
            "estimated_recovery_score",
            "recovery_interpretation",
        ]
        keep = [c for c in keep if c in events.columns]
        lines += [
            "",
            "ib3c_events_preview:",
            events[keep].head(20).to_string(index=False),
        ]

    out_summary.write_text("\n".join(lines) + "\n", encoding="utf-8")


def detect_self_near_ambiguous_zone(df: pd.DataFrame) -> bool:
    if "route_point_index" not in df.columns:
        return False
    w = df[df["route_dist_m"].between(1400, 2700)].sort_values("elapsed_sec")
    if w.empty:
        return False
    jumps = pd.to_numeric(w["route_point_index"], errors="coerce").diff().abs() > SPEED_ROUTE_POINT_INDEX_JUMP_THRESHOLD
    return bool(jumps.sum() > 0)


def maybe_write_event_qa(
    args: argparse.Namespace,
    out_dir: Path,
    df: pd.DataFrame,
    route: pd.DataFrame,
) -> tuple[Path | None, Path | None, Path | None]:
    if not (
        args.route_folder == "qixing_lengshuikeng"
        and args.activity_id == "37_1"
    ):
        return None, None, None

    event_start = 4201
    event_end = 5156
    event_dir = out_dir / "event_qa_4201_5156"
    event_dir.mkdir(parents=True, exist_ok=True)
    out_rows = event_dir / "qixing_lengshuikeng_37_1_event_4201_5156_qa_rows.csv"
    out_summary = event_dir / "qixing_lengshuikeng_37_1_event_4201_5156_qa_summary.txt"
    out_map = event_dir / "qixing_lengshuikeng_37_1_event_4201_5156_qa_map.html"

    event = df[df["row_index"].between(event_start, event_end)].sort_values("row_index").copy()
    qa_cols = [
        "row_index",
        "point_index",
        "elapsed_sec",
        "raw_lat",
        "raw_lon",
        "route_dist_m",
        "nearest_route_dist_m",
        "offset_to_mainline_m",
        "match_quality",
        "usable_on_route",
        "manual_label",
        "manual_interpretation",
        "excluded_reason",
        "manual_event_id",
    ]
    qa_cols = [c for c in qa_cols if c in event.columns]
    event[qa_cols].rename(columns={"raw_lat": "lat", "raw_lon": "lon", "offset_to_mainline_m": "offset_m"}).to_csv(
        out_rows,
        index=False,
        encoding="utf-8-sig",
    )

    summit = summit_row(route)
    summary_values = event_summary_values(event, summit)
    classification, note, label_recommendation = classify_event_location(event, summit)
    write_event_summary(out_summary, summary_values, summit, classification, note, label_recommendation)
    write_event_map(out_map, event, route, summit, event_start, event_end, summary_values)
    return out_rows, out_summary, out_map


def write_route_phase_jump_qa(args: argparse.Namespace, out_dir: Path, df: pd.DataFrame) -> Path:
    qa_dir = out_dir / "route_phase_leg_qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    out_csv = qa_dir / f"{args.route_folder}_{args.activity_id}_route_phase_jump_qa.csv"
    work = sort_activity_time_order(df).copy()
    work["previous_route_phase"] = work["route_phase"].fillna("").astype(str).shift()
    work["route_point_index_delta"] = pd.to_numeric(work["route_point_index"], errors="coerce").diff()
    work["route_dist_delta_m"] = pd.to_numeric(work["route_dist_m"], errors="coerce").diff()
    work["elapsed_delta_sec"] = pd.to_numeric(work["elapsed_sec"], errors="coerce").diff()
    phase = work["route_phase"].fillna("").astype(str)
    prev = work["previous_route_phase"].fillna("").astype(str)
    short_time = work["elapsed_delta_sec"].le(SPEED_GAP_THRESHOLD_SEC).fillna(False)
    big_point = work["route_point_index_delta"].abs().gt(SPEED_ROUTE_POINT_INDEX_JUMP_THRESHOLD).fillna(False)
    big_dist = work["route_dist_delta_m"].abs().gt(SPEED_ROUTE_DIST_JUMP_THRESHOLD_M).fillna(False)
    phase_changed = phase.ne(prev) & prev.ne("")
    suspicious = (
        (prev.eq("ascent") & phase.eq("descent"))
        | (prev.eq("descent") & phase.eq("ascent"))
        | (prev.eq("summit_self_near") & phase.isin(["ascent", "descent"]) & (big_point | big_dist))
        | (phase.eq("summit_self_near") & prev.isin(["ascent", "descent"]) & (big_point | big_dist))
        | (phase_changed & short_time & (big_point | big_dist))
    )
    qa = work[phase_changed & short_time & suspicious].copy()
    qa["route_phase_jump_flag"] = True
    qa["mapmatch_branch_ambiguity_flag"] = True
    cols = [
        "row_index",
        "elapsed_sec",
        "route_dist_m",
        "route_point_index",
        "route_phase",
        "previous_route_phase",
        "route_point_index_delta",
        "route_dist_delta_m",
        "elapsed_delta_sec",
        "offset_to_mainline_m",
        "usable_on_route",
        "manual_label",
        "route_phase_jump_flag",
        "mapmatch_branch_ambiguity_flag",
    ]
    cols = [c for c in cols if c in qa.columns]
    qa[cols].rename(columns={"offset_to_mainline_m": "offset_m"}).to_csv(out_csv, index=False, encoding="utf-8-sig")
    return out_csv


def summit_row(route: pd.DataFrame) -> pd.Series:
    if "ele_smooth" in route.columns and route["ele_smooth"].notna().any():
        idx = pd.to_numeric(route["ele_smooth"], errors="coerce").idxmax()
        row = route.loc[idx].copy()
        row["summit_ele_m"] = row["ele_smooth"]
        return row
    idx = pd.to_numeric(route["ele_gpx_m"], errors="coerce").idxmax()
    row = route.loc[idx].copy()
    row["summit_ele_m"] = row["ele_gpx_m"]
    return row


def event_summary_values(event: pd.DataFrame, summit: pd.Series) -> dict:
    if event.empty:
        return {}
    route_dist = pd.to_numeric(event["route_dist_m"], errors="coerce")
    nearest_dist = pd.to_numeric(event.get("nearest_route_dist_m", route_dist), errors="coerce")
    offset = pd.to_numeric(event.get("offset_to_mainline_m", np.nan), errors="coerce")
    start = event.iloc[0]
    end = event.iloc[-1]
    return {
        "start_row_index": start.get("row_index", ""),
        "end_row_index": end.get("row_index", ""),
        "start_elapsed_sec": start.get("elapsed_sec", ""),
        "end_elapsed_sec": end.get("elapsed_sec", ""),
        "start_route_dist_m": start.get("route_dist_m", ""),
        "median_route_dist_m": route_dist.median(),
        "max_route_dist_m": route_dist.max(),
        "end_route_dist_m": end.get("route_dist_m", ""),
        "start_nearest_route_dist_m": start.get("nearest_route_dist_m", ""),
        "median_nearest_route_dist_m": nearest_dist.median(),
        "max_nearest_route_dist_m": nearest_dist.max(),
        "end_nearest_route_dist_m": end.get("nearest_route_dist_m", ""),
        "max_offset_m": offset.max(),
        "mean_offset_m": offset.mean(),
        "route_dist_delta_start_to_end_m": end.get("route_dist_m", np.nan) - start.get("route_dist_m", np.nan),
        "nearest_route_dist_delta_start_to_end_m": end.get("nearest_route_dist_m", np.nan) - start.get("nearest_route_dist_m", np.nan),
        "summit_route_dist_m": summit.get("dist_m", ""),
    }


def classify_event_location(event: pd.DataFrame, summit: pd.Series) -> tuple[str, str, str]:
    if event.empty:
        return "unable_to_determine", "無法判斷；event rows 為空。", "no label change"
    route_dist = pd.to_numeric(event["route_dist_m"], errors="coerce")
    nearest_dist = pd.to_numeric(event.get("nearest_route_dist_m", route_dist), errors="coerce")
    summit_dist = float(summit["dist_m"])
    event_min = float(route_dist.min())
    event_med = float(route_dist.median())
    event_max = float(route_dist.max())
    post_summit_fraction = float((route_dist > summit_dist).mean())
    self_near_window = (event_min <= summit_dist + 500.0) and (event_max >= summit_dist - 150.0)
    route_delta = float(route_dist.iloc[-1] - route_dist.iloc[0])
    nearest_delta = float(nearest_dist.iloc[-1] - nearest_dist.iloc[0])

    if post_summit_fraction > 0.75 and event_med > summit_dist + 120.0 and not self_near_window:
        classification = "post_summit_downhill"
    elif self_near_window:
        classification = "summit_self_near_loop_zone"
    elif event_max < summit_dist - 120.0:
        classification = "pre_summit_uphill"
    elif event_min > summit_dist + 120.0:
        classification = "post_summit_downhill"
    else:
        classification = "unable_to_determine"

    if classification == "post_summit_downhill":
        note = "下山段疑似走入錯誤支線後折返／接回主線；山頂附近 route axis 存在 self-near geometry，2D 判讀需避免誤解成再次往主峰方向行進。"
        label_recommendation = "manual_label can remain; update manual_note/confidence"
    elif classification == "summit_self_near_loop_zone":
        note = "山頂附近疑似偏離／折返事件；因 route axis 存在 self-near geometry，僅依 2D 圖難以判定是否為明確走錯，需結合 route_dist progression、offset 與 bearing 複核。"
        label_recommendation = "do not change manual_label yet; update note/confidence"
    else:
        note = "目前無法單靠 event route_dist、offset 與 summit distance 明確判斷，建議保留 label 並降低 confidence。"
        label_recommendation = "do not change manual_label; update confidence"

    note += f" route_dist_delta={route_delta:.1f}m; nearest_route_dist_delta={nearest_delta:.1f}m."
    return classification, note, label_recommendation


def write_event_summary(
    out_summary: Path,
    values: dict,
    summit: pd.Series,
    classification: str,
    note: str,
    label_recommendation: str,
) -> None:
    rows = ["qixing_lengshuikeng_37_1_event_4201_5156_qa_summary"]
    for key in [
        "start_row_index",
        "end_row_index",
        "start_elapsed_sec",
        "end_elapsed_sec",
        "start_route_dist_m",
        "median_route_dist_m",
        "max_route_dist_m",
        "end_route_dist_m",
        "start_nearest_route_dist_m",
        "median_nearest_route_dist_m",
        "max_nearest_route_dist_m",
        "end_nearest_route_dist_m",
        "max_offset_m",
        "mean_offset_m",
    ]:
        rows.append(f"{key}: {fmt_value(values.get(key, ''), 3)}")
    rows.extend(
        [
            "",
            f"summit_route_dist_m: {fmt_value(summit.get('dist_m', ''), 3)}",
            f"summit_ele_m: {fmt_value(summit.get('summit_ele_m', ''), 3)}",
            f"summit_point_index: {fmt_value(summit.get('route_point_index', ''), 0)}",
            f"summit_lat: {fmt_value(summit.get('lat', ''), 8)}",
            f"summit_lon: {fmt_value(summit.get('lon', ''), 8)}",
            "",
            f"event_location_classification: {classification}",
            f"recommended_manual_note: {note}",
            f"manual_label_recommendation: {label_recommendation}",
        ]
    )
    out_summary.write_text("\n".join(rows) + "\n", encoding="utf-8")


def write_event_map(
    out_map: Path,
    event: pd.DataFrame,
    route: pd.DataFrame,
    summit: pd.Series,
    event_start: int,
    event_end: int,
    values: dict,
) -> None:
    center = [
        float(event["raw_lat"].mean() if not event.empty else summit["lat"]),
        float(event["raw_lon"].mean() if not event.empty else summit["lon"]),
    ]
    m = folium.Map(location=center, zoom_start=17, tiles="OpenStreetMap")
    route_coords = route[["lat", "lon"]].dropna().values.tolist()
    folium.PolyLine(route_coords, color="#2563eb", weight=4, opacity=0.55, tooltip="route axis").add_to(m)

    event_coords = event[["raw_lat", "raw_lon"]].dropna().values.tolist()
    if event_coords:
        folium.PolyLine(
            event_coords,
            color="#dc2626",
            weight=5,
            opacity=0.85,
            tooltip=f"event raw GPS rows {event_start}-{event_end}",
        ).add_to(m)
        add_event_marker(m, event.iloc[0], "event start", "green")
        add_event_marker(m, event.iloc[-1], "event end", "red")

    folium.Marker(
        [float(summit["lat"]), float(summit["lon"])],
        tooltip=f"summit / highest point dist={float(summit['dist_m']):.1f}m",
        popup=folium.Popup(
            html_lines(
                [
                    ("summit_route_dist_m", summit.get("dist_m", ""), 3),
                    ("summit_ele_m", summit.get("summit_ele_m", ""), 2),
                    ("summit_point_index", summit.get("route_point_index", ""), 0),
                    ("lat", summit.get("lat", ""), 7),
                    ("lon", summit.get("lon", ""), 7),
                ]
            ),
            max_width=360,
        ),
        icon=folium.Icon(color="orange", icon="star"),
    ).add_to(m)

    folium.Marker(
        center,
        icon=folium.DivIcon(
            html=(
                '<div style="background:white;border:1px solid #334155;padding:6px;'
                'font-size:12px;white-space:nowrap;">'
                f"summit_dist={fmt_value(summit.get('dist_m', ''), 1)}m<br>"
                f"event_route_dist={fmt_value(values.get('start_route_dist_m', ''), 1)}"
                f"-{fmt_value(values.get('end_route_dist_m', ''), 1)}m</div>"
            )
        ),
    ).add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    m.save(out_map)


def add_event_marker(m: folium.Map, row: pd.Series, label: str, color: str) -> None:
    folium.Marker(
        [float(row["raw_lat"]), float(row["raw_lon"])],
        tooltip=label,
        popup=folium.Popup(
            html_lines(
                [
                    ("activity_row_index", row.get("row_index", ""), 0),
                    ("route_dist_m", row.get("route_dist_m", ""), 3),
                    ("nearest_route_dist_m", row.get("nearest_route_dist_m", ""), 3),
                    ("offset_m", row.get("offset_to_mainline_m", ""), 3),
                ]
            ),
            max_width=320,
        ),
        icon=folium.Icon(color=color, icon="info-sign"),
    ).add_to(m)


def main() -> None:
    args = parse_args()
    out_dir = args.out_dir / args.route_folder / args.activity_id
    out_dir.mkdir(parents=True, exist_ok=True)

    route = read_route(args.case_id)

    activity_full = read_activity_full(
        args.route_folder,
        args.activity_id,
        args.mapmatched_root,
        args.ib3a2_root,
    )

    speed_activity, speed_input_source = read_activity_for_speed(
        args.route_folder,
        args.activity_id,
        activity_full,
        args.mapmatched_root,
        args.ib3a2_root,
    )

    speed_activity = sort_activity_time_order(
        merge_route_context(speed_activity, route)
    )
    derive_speed(speed_activity, speed_input_source)

    activity = attach_on_route_speed(activity_full, speed_activity)
    derive_stationary(activity)

    df = merge_route_context(activity, route)
    add_activity_route_phase_transition_flags(df)
    anchors = read_anchors(args.case_id, route)

    project_xy(route, df)
    segments = make_segments(float(route["dist_m"].max()), args.segment_m)

    out_png = out_dir / f"{args.route_folder}_{args.activity_id}_activity_profile_1d_2d.png"
    out_html = out_dir / f"{args.route_folder}_{args.activity_id}_activity_profile_1d_2d.html"
    out_csv = out_dir / f"{args.route_folder}_{args.activity_id}_activity_profile_1d_2d_plot_data.csv"
    out_summary = out_dir / f"{args.route_folder}_{args.activity_id}_activity_profile_1d_2d_summary.txt"

    events = load_ib3c_events(args)
    events_csv = resolve_ib3c_events_csv(args) if args.show_events else None

    write_png(out_png, df, route, anchors, segments)
    write_html(out_html, df, route, anchors, segments, events=events)
    write_plot_data(out_csv, df)
    write_summary(
        out_summary,
        df,
        segments,
        args.mapmatched_root,
        args.ib3a2_root,
        events=events,
        events_csv=events_csv,
    )

    event_rows, event_summary, event_map = maybe_write_event_qa(args, out_dir, df, route)
    phase_jump_qa = write_route_phase_jump_qa(args, out_dir, df)

    print("activity profile board written")
    print(f"PNG: {out_png.resolve()}")
    print(f"HTML: {out_html.resolve()}")
    print(f"plot data: {out_csv.resolve()}")
    print(f"summary: {out_summary.resolve()}")
    if args.show_events:
        print(f"IB3C events CSV: {events_csv.resolve() if events_csv is not None else ''}")
        print(f"IB3C events loaded: {len(events)}")
    
    if event_summary is not None:
        print(f"event QA rows: {event_rows.resolve()}")
        print(f"event QA summary: {event_summary.resolve()}")
        print(f"event QA map: {event_map.resolve()}")
    print(f"route phase jump QA: {phase_jump_qa.resolve()}")
    print(f"rows: {len(df)}")
    print(f"segments_250m: {len(segments)}")
    print("match_quality:")
    print(df["match_quality"].value_counts(dropna=False).to_string())
    print("usable_on_route:")
    print(df["usable_on_route"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
