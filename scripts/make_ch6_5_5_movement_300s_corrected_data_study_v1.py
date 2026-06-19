#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build CH6.5.5 movement 300s corrected-data study v1.

This script creates descriptive 300-second movement evidence from corrected
activity files. It does not create radar scores, ability scores, ranks,
classes, go/no-go decisions, medical diagnoses, or causality claims.
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_SOURCE_ROOT = "outputs/report_figures/ch6_single_activity_mainline_profile_v2_3_2"
DEFAULT_RADAR_AXIS = (
    "outputs/script_inputs/ch6_5_5_radar_v1_axis_refinement_input_pack_v1/"
    "radar_baseline/personal_activity_performance_radar_report_safe_axis_table_v1_terrain_axis.csv"
)
DEFAULT_PROFILE_JOIN = (
    "outputs/report_figures/ch6_5_5_personal_profile_metadata_join_v0_2/"
    "personal_profile_metadata_join_v0_2.csv"
)
DEFAULT_OUTPUT_ROOT = "outputs/report_figures/ch6_5_5_movement_300s_corrected_data_study_v1"

BOUNDARY = (
    "CH6.5.5 movement 300s corrected-data study v1 is descriptive study evidence only. "
    "It uses corrected route-distance and calibrated elevation fields where available. "
    "No zero-fill is used for missing evidence. It does not compute or authorize radar scores, "
    "ability scores, ability ranks, ability classes, THCI scores, final hiking risk scores, "
    "route suitability scores, go/no-go decisions, medical diagnoses, or causality claims."
)

PASS = "PASS_CH6_5_5_MOVEMENT_300S_CORRECTED_DATA_STUDY_V1_DESCRIPTIVE_ONLY"
REVIEW = "REVIEW_REQUIRED_CH6_5_5_MOVEMENT_300S_CORRECTED_DATA_STUDY_V1"

FORBIDDEN_OUTPUT_PATTERNS = [
    "radar_score",
    "ability_score",
    "ability_rank",
    "ability_class",
    "go_no_go",
    "go/no-go",
    "medical_diagnosis",
    "causality_claim",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=r"D:\mountain_work\115_osm")
    parser.add_argument("--source-root", default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--radar-axis-table", default=DEFAULT_RADAR_AXIS)
    parser.add_argument("--profile-join", default=DEFAULT_PROFILE_JOIN)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--window-sec", type=float, default=300.0)
    parser.add_argument("--min-duration-sec", type=float, default=270.0)
    parser.add_argument("--step-sec", type=float, default=30.0)
    return parser.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    p = Path(value)
    return p if p.is_absolute() else root / p


def read_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def nser(df: pd.DataFrame, col: str, default: float = np.nan) -> pd.Series:
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce")
    return pd.Series(default, index=df.index, dtype=float)


def boolser(df: pd.DataFrame, col: str, default: bool = False) -> pd.Series:
    if col not in df.columns:
        return pd.Series(default, index=df.index, dtype=bool)
    s = df[col]
    if s.dtype == bool:
        return s.fillna(default)
    return s.astype(str).str.strip().str.lower().isin(["true", "1", "yes", "y"])


def first_present(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    out = pd.Series(np.nan, index=df.index, dtype=float)
    for col in cols:
        if col in df.columns:
            out = out.combine_first(pd.to_numeric(df[col], errors="coerce"))
    return out


def q(values: pd.Series, quantile: float) -> float:
    v = pd.to_numeric(values, errors="coerce").dropna()
    return float(v.quantile(quantile)) if len(v) else np.nan


def pctl(values: pd.Series, quantiles: list[float]) -> dict[str, float]:
    v = pd.to_numeric(values, errors="coerce").dropna()
    if len(v) == 0:
        return {f"p{int(x * 100)}": np.nan for x in quantiles}
    return {f"p{int(x * 100)}": float(v.quantile(x)) for x in quantiles}


def activity_short_from_path(path: Path) -> str:
    name = path.name
    prefix = "activity_"
    suffix = "_projected_joined_v2_3_2.csv"
    if name.startswith(prefix) and name.endswith(suffix):
        return name[len(prefix) : -len(suffix)]
    return path.parent.name


def activity_short_from_frame(df: pd.DataFrame, path: Path) -> str:
    if "activity_id" in df.columns:
        vals = df["activity_id"].dropna().astype(str)
        if len(vals):
            m = vals.iloc[0].strip().split("_")
            if len(m) >= 2 and m[-1].isdigit() and m[-2].isdigit():
                return f"{m[-2]}_{m[-1]}"
    if {"subject_id", "trial_id"}.issubset(df.columns):
        sid = pd.to_numeric(df["subject_id"], errors="coerce").dropna()
        tid = pd.to_numeric(df["trial_id"], errors="coerce").dropna()
        if len(sid) and len(tid):
            return f"{int(sid.iloc[0])}_{int(tid.iloc[0])}"
    return activity_short_from_path(path)


def hr_zone(pct: float) -> str:
    if pd.isna(pct):
        return ""
    if pct > 100:
        return "HR_ESTIMATE_EXCEEDS_100_REVIEW"
    if pct >= 90:
        return "ZONE5_90_100_PCT_HRMAX"
    if pct >= 80:
        return "ZONE4_80_90_PCT_HRMAX"
    if pct >= 70:
        return "ZONE3_70_80_PCT_HRMAX"
    if pct >= 60:
        return "ZONE2_60_70_PCT_HRMAX"
    if pct >= 50:
        return "ZONE1_50_60_PCT_HRMAX"
    return "BELOW_ZONE1_LT_50_PCT_HRMAX"


def load_profile(profile_path: Path) -> pd.DataFrame:
    if not profile_path.exists():
        return pd.DataFrame(columns=[
            "activity_id_short",
            "hrmax_bpm",
            "hrmax_source",
            "profile_join_status",
            "profile_join_reason",
        ])
    profile = read_csv(profile_path, "profile join")
    profile["activity_id_short"] = profile["activity_id_short"].astype(str).str.strip()
    profile["hrmax_bpm"] = pd.to_numeric(profile.get("sex_age_est_hrmax_bpm"), errors="coerce")
    profile["hrmax_source"] = profile.get("sex_age_est_hrmax_formula", "SEX_AGE_EST_HRMAX")
    profile["profile_join_status"] = np.where(
        profile.get("metadata_join_status", "").astype(str).eq("PARTICIPANT_PROFILE_JOINED"),
        "PROFILE_JOINED",
        "MISSING_PROFILE",
    )
    profile["profile_join_reason"] = profile.get("metadata_join_status", "PROFILE_JOIN_SOURCE_UNAVAILABLE")
    cols = ["activity_id_short", "hrmax_bpm", "hrmax_source", "profile_join_status", "profile_join_reason"]
    return profile[cols].drop_duplicates("activity_id_short")


def prepare_activity(df: pd.DataFrame, path: Path) -> pd.DataFrame:
    work = df.copy()
    work["activity_id_short"] = activity_short_from_frame(work, path)
    work["participant_id"] = pd.to_numeric(work.get("subject_id"), errors="coerce")
    work["elapsed_sec"] = nser(work, "elapsed_sec")
    work["route_dist_m"] = first_present(work, ["route_dist_m", "v2_3_projected_route_distance_m", "nearest_route_dist_m"])
    work["calibrated_elevation_m"] = nser(work, "calibrated_elevation_m")
    work["calibrated_delta_elevation_m"] = nser(work, "calibrated_delta_elevation_m")
    work["calibrated_cumulative_gain_m"] = nser(work, "calibrated_cumulative_gain_m")
    work["calibrated_slope_pct"] = nser(work, "calibrated_slope_pct")
    work["standard_slope_pct"] = nser(work, "standard_slope_pct")
    work["heart_rate_bpm"] = first_present(work, ["heart_rate_bpm", "raw_heart_rate"])
    work["elevation_step_valid_bool"] = boolser(work, "elevation_step_valid")
    work["elevation_artifact_bool"] = boolser(work, "elevation_artifact_flag")
    work["pause_or_stall_bool"] = boolser(work, "pause_or_stall_flag")
    work["osm_steps_bool"] = boolser(work, "osm_steps")
    work["near_steps_bool"] = boolser(work, "near_steps_flag")
    if "route_context_osm_highway" in work.columns:
        highway = work["route_context_osm_highway"].astype(str)
    elif "standard_osm_highway" in work.columns:
        highway = work["standard_osm_highway"].astype(str)
    elif "osm_highway" in work.columns:
        highway = work["osm_highway"].astype(str)
    else:
        highway = pd.Series("", index=work.index)
    work["steps_context_bool"] = work["osm_steps_bool"] | work["near_steps_bool"] | highway.str.lower().eq("steps")
    work = work.dropna(subset=["elapsed_sec"]).sort_values("elapsed_sec", kind="mergesort").reset_index(drop=True)
    work = work.drop_duplicates("elapsed_sec", keep="first").reset_index(drop=True)
    work["positive_delta_elevation_m"] = work["calibrated_delta_elevation_m"].clip(lower=0)
    return work


def window_row(g: pd.DataFrame, start_pos: int, end_pos: int, profile: dict[str, Any], source_path: str) -> dict[str, Any]:
    seg = g.iloc[start_pos : end_pos + 1]
    first = seg.iloc[0]
    last = seg.iloc[-1]
    duration = float(last["elapsed_sec"] - first["elapsed_sec"])
    dist_delta = float(last["route_dist_m"] - first["route_dist_m"]) if pd.notna(last["route_dist_m"]) and pd.notna(first["route_dist_m"]) else np.nan
    gain_delta = (
        float(last["calibrated_cumulative_gain_m"] - first["calibrated_cumulative_gain_m"])
        if pd.notna(last["calibrated_cumulative_gain_m"]) and pd.notna(first["calibrated_cumulative_gain_m"])
        else np.nan
    )
    valid_elev = seg["elevation_step_valid_bool"]
    artifact = seg["elevation_artifact_bool"]
    hr = pd.to_numeric(seg["heart_rate_bpm"], errors="coerce")
    hr_valid = hr[(hr >= 40) & (hr <= 220)]
    hrmax = profile.get("hrmax_bpm", np.nan)
    hr_pct = hr_valid / hrmax * 100 if pd.notna(hrmax) and hrmax > 0 else pd.Series(dtype=float)
    slope_ok = (
        seg["calibrated_slope_pct"].abs().le(5).fillna(False)
        | seg["standard_slope_pct"].abs().le(5).fillna(False)
    )
    horizontal_sample_ratio = float(slope_ok.mean()) if len(seg) else np.nan
    ascent_sample_ratio = float(seg["calibrated_slope_pct"].gt(5).fillna(False).mean()) if len(seg) else np.nan
    elevation_valid_ratio = float(valid_elev.mean()) if len(seg) else np.nan
    hr_valid_ratio = float(len(hr_valid) / len(seg)) if len(seg) else np.nan
    hr_ok = bool(hr_valid_ratio >= 0.7 and len(hr_valid) >= 60)
    horizontal_valid = bool(
        duration >= 270
        and pd.notna(dist_delta)
        and dist_delta > 0
        and horizontal_sample_ratio >= 0.7
    )
    vertical_valid = bool(
        duration >= 270
        and ascent_sample_ratio >= 0.6
        and pd.notna(gain_delta)
        and gain_delta >= 10
        and pd.notna(dist_delta)
        and dist_delta > 0
        and elevation_valid_ratio >= 0.7
        and not bool(artifact.any())
    )
    row = {
        "activity_id_short": first["activity_id_short"],
        "participant_id": first["participant_id"],
        "source_path": source_path,
        "window_start_elapsed_sec": float(first["elapsed_sec"]),
        "window_end_elapsed_sec": float(last["elapsed_sec"]),
        "duration_sec": duration,
        "sample_count": int(len(seg)),
        "route_dist_start_m": float(first["route_dist_m"]) if pd.notna(first["route_dist_m"]) else np.nan,
        "route_dist_end_m": float(last["route_dist_m"]) if pd.notna(last["route_dist_m"]) else np.nan,
        "route_dist_delta_m": dist_delta,
        "calibrated_elevation_start_m": float(first["calibrated_elevation_m"]) if pd.notna(first["calibrated_elevation_m"]) else np.nan,
        "calibrated_elevation_end_m": float(last["calibrated_elevation_m"]) if pd.notna(last["calibrated_elevation_m"]) else np.nan,
        "vertical_gain_300s_calibrated_m": gain_delta,
        "vertical_gain_300s_sum_positive_delta_m": float(seg["positive_delta_elevation_m"].sum(skipna=True)),
        "calibrated_slope_pct_median": float(seg["calibrated_slope_pct"].median(skipna=True)),
        "standard_slope_pct_median": float(seg["standard_slope_pct"].median(skipna=True)),
        "horizontal_sample_ratio": horizontal_sample_ratio,
        "ascent_sample_ratio": ascent_sample_ratio,
        "elevation_step_valid_ratio": elevation_valid_ratio,
        "elevation_artifact_flag": bool(artifact.any()),
        "horizontal_300s_window_status": "VALID_HORIZONTAL_WINDOW" if horizontal_valid else "INSUFFICIENT_HORIZONTAL_EVIDENCE",
        "vertical_300s_window_status": "VALID_VERTICAL_WINDOW" if vertical_valid else "INSUFFICIENT_VERTICAL_EVIDENCE",
        "horizontal_300s_route_speed_mps": dist_delta / duration if horizontal_valid else np.nan,
        "vertical_300s_vam_mph": gain_delta / duration * 3600 if vertical_valid else np.nan,
        "hr_sample_count": int(len(hr_valid)),
        "hr_valid_ratio": hr_valid_ratio,
        "hr_min_bpm": float(hr_valid.min()) if len(hr_valid) else np.nan,
        "hr_max_bpm": float(hr_valid.max()) if len(hr_valid) else np.nan,
        "hr_range_bpm": float(hr_valid.max() - hr_valid.min()) if len(hr_valid) else np.nan,
        "hr_mean_bpm": float(hr_valid.mean()) if len(hr_valid) else np.nan,
        "hr_median_bpm": float(hr_valid.median()) if len(hr_valid) else np.nan,
        "hr_p75_bpm": q(hr_valid, 0.75),
        "hr_p90_bpm": q(hr_valid, 0.90),
        "hr_window_status": "VALID_HR_WINDOW" if hr_ok else "INSUFFICIENT_HR_EVIDENCE",
        "hrmax_bpm": hrmax,
        "hrmax_source": profile.get("hrmax_source", ""),
        "hr_pct_sex_age_est_hrmax_median": float(hr_pct.median()) if len(hr_pct) else np.nan,
        "hr_pct_sex_age_est_hrmax_p90": q(hr_pct, 0.90),
        "hr_zone_sex_age_est": hr_zone(float(hr_pct.median())) if len(hr_pct) else "",
        "profile_join_status": profile.get("profile_join_status", "MISSING_PROFILE"),
        "profile_join_reason": profile.get("profile_join_reason", "NO_PROFILE_JOIN_ROW"),
        "interpretation_boundary": BOUNDARY,
    }
    return row


def build_windows(g: pd.DataFrame, profile: dict[str, Any], source_path: str, window_sec: float, min_duration: float, step_sec: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if len(g) < 2:
        return rows
    elapsed = g["elapsed_sec"].to_numpy(dtype=float)
    next_emit = elapsed[0]
    for start_pos, start in enumerate(elapsed):
        if start + 1e-9 < next_emit:
            continue
        target = start + window_sec
        end_pos = int(np.searchsorted(elapsed, target, side="right") - 1)
        if end_pos <= start_pos:
            continue
        duration = elapsed[end_pos] - start
        if duration >= min_duration:
            rows.append(window_row(g, start_pos, end_pos, profile, source_path))
        next_emit = start + step_sec
    return rows


def best_window_context(windows: pd.DataFrame, value_col: str, prefix: str) -> dict[str, Any]:
    valid = windows[pd.to_numeric(windows[value_col], errors="coerce").notna()].copy() if value_col in windows.columns else pd.DataFrame()
    if valid.empty:
        return {
            f"{prefix}_hr_min_bpm_at_window": np.nan,
            f"{prefix}_hr_max_bpm_at_window": np.nan,
            f"{prefix}_hr_range_bpm_at_window": np.nan,
            f"{prefix}_hr_p90_bpm_at_window": np.nan,
            f"{prefix}_hr_min_pct_hrmax_at_window": np.nan,
            f"{prefix}_hr_max_pct_hrmax_at_window": np.nan,
            f"{prefix}_hr_range_pct_hrmax_at_window": np.nan,
            f"{prefix}_hr_p90_pct_hrmax_at_window": np.nan,
        }
    idx = pd.to_numeric(valid[value_col], errors="coerce").idxmax()
    row = valid.loc[idx]
    hrmax = row.get("hrmax_bpm", np.nan)
    min_pct = row["hr_min_bpm"] / hrmax * 100 if pd.notna(hrmax) and hrmax > 0 and pd.notna(row["hr_min_bpm"]) else np.nan
    max_pct = row["hr_max_bpm"] / hrmax * 100 if pd.notna(hrmax) and hrmax > 0 and pd.notna(row["hr_max_bpm"]) else np.nan
    p90_pct = row["hr_p90_bpm"] / hrmax * 100 if pd.notna(hrmax) and hrmax > 0 and pd.notna(row["hr_p90_bpm"]) else np.nan
    return {
        f"{prefix}_hr_min_bpm_at_window": row["hr_min_bpm"],
        f"{prefix}_hr_max_bpm_at_window": row["hr_max_bpm"],
        f"{prefix}_hr_range_bpm_at_window": row["hr_range_bpm"],
        f"{prefix}_hr_p90_bpm_at_window": row["hr_p90_bpm"],
        f"{prefix}_hr_min_pct_hrmax_at_window": min_pct,
        f"{prefix}_hr_max_pct_hrmax_at_window": max_pct,
        f"{prefix}_hr_range_pct_hrmax_at_window": max_pct - min_pct if pd.notna(max_pct) and pd.notna(min_pct) else np.nan,
        f"{prefix}_hr_p90_pct_hrmax_at_window": p90_pct,
    }


def summarize_windows(windows: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for activity_id, g in windows.groupby("activity_id_short", sort=True):
        h = g[pd.to_numeric(g["horizontal_300s_route_speed_mps"], errors="coerce").notna()]
        v = g[pd.to_numeric(g["vertical_300s_vam_mph"], errors="coerce").notna()]
        hp = pctl(h["horizontal_300s_route_speed_mps"], [0.5, 0.75, 0.9])
        gp = pctl(v["vertical_gain_300s_calibrated_m"], [0.5, 0.75, 0.9])
        vp = pctl(v["vertical_300s_vam_mph"], [0.5, 0.75, 0.9])
        first = g.iloc[0]
        row = {
            "activity_id_short": activity_id,
            "participant_id": first.get("participant_id"),
            "rolling_window_count": int(len(g)),
            "horizontal_300s_valid_window_count": int(len(h)),
            "horizontal_300s_route_speed_p50_mps": hp["p50"],
            "horizontal_300s_route_speed_p75_mps": hp["p75"],
            "horizontal_300s_route_speed_p90_mps": hp["p90"],
            "horizontal_300s_route_speed_max_mps": float(h["horizontal_300s_route_speed_mps"].max()) if len(h) else np.nan,
            "vertical_300s_valid_window_count": int(len(v)),
            "vertical_300s_gain_p50_m": gp["p50"],
            "vertical_300s_gain_p75_m": gp["p75"],
            "vertical_300s_gain_p90_m": gp["p90"],
            "vertical_300s_gain_max_m": float(v["vertical_gain_300s_calibrated_m"].max()) if len(v) else np.nan,
            "vertical_300s_vam_p50_mph": vp["p50"],
            "vertical_300s_vam_p75_mph": vp["p75"],
            "vertical_300s_vam_p90_mph": vp["p90"],
            "vertical_300s_vam_max_mph": float(v["vertical_300s_vam_mph"].max()) if len(v) else np.nan,
            "hr_valid_window_count": int(g["hr_window_status"].eq("VALID_HR_WINDOW").sum()),
            "profile_join_status": first.get("profile_join_status"),
            "profile_join_reason": first.get("profile_join_reason"),
            "hrmax_bpm": first.get("hrmax_bpm"),
            "hrmax_source": first.get("hrmax_source"),
            "interpretation_boundary": BOUNDARY,
        }
        row.update(best_window_context(h, "horizontal_300s_route_speed_mps", "horizontal_300s_hr_at_speed_p90_window"))
        row.update(best_window_context(v, "vertical_300s_vam_mph", "vertical_300s_hr_at_vam_p90_window"))
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_hr_response(windows: pd.DataFrame, bouts: pd.DataFrame, recovery: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for activity_id, g in windows.groupby("activity_id_short", sort=True):
        b = bouts[bouts["activity_id_short"].eq(activity_id)] if not bouts.empty else pd.DataFrame()
        r = recovery[recovery["activity_id_short"].eq(activity_id)] if not recovery.empty else pd.DataFrame()
        rows.append({
            "activity_id_short": activity_id,
            "hr_valid_window_count": int(g["hr_window_status"].eq("VALID_HR_WINDOW").sum()),
            "hr_window_count": int(len(g)),
            "hr_valid_window_ratio": float(g["hr_window_status"].eq("VALID_HR_WINDOW").mean()) if len(g) else np.nan,
            "hr_median_bpm_window_median": float(g["hr_median_bpm"].median(skipna=True)),
            "hr_p90_bpm_window_median": float(g["hr_p90_bpm"].median(skipna=True)),
            "ascent_bout_count": int(b["bout_type"].eq("continuous_ascent_bout").sum()) if not b.empty else 0,
            "steps_bout_count": int(b["bout_type"].eq("continuous_steps_bout").sum()) if not b.empty else 0,
            "pause_recovery_event_count": int(len(r)),
            "best_hr_drop_60s_bpm": float(r["hr_drop_60s_bpm"].max()) if not r.empty else np.nan,
            "best_hr_drop_120s_bpm": float(r["hr_drop_120s_bpm"].max()) if not r.empty else np.nan,
            "best_hr_drop_180s_bpm": float(r["hr_drop_180s_bpm"].max()) if not r.empty else np.nan,
            "interpretation_boundary": BOUNDARY,
        })
    return pd.DataFrame(rows)


def segment_runs(g: pd.DataFrame, flag: pd.Series, min_duration: float) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for i, ok in enumerate(flag.fillna(False).tolist()):
        if ok and start is None:
            start = i
        if (not ok or i == len(flag) - 1) and start is not None:
            end = i if ok and i == len(flag) - 1 else i - 1
            if end > start and g.iloc[end]["elapsed_sec"] - g.iloc[start]["elapsed_sec"] >= min_duration:
                runs.append((start, end))
            start = None
    return runs


def bout_row(g: pd.DataFrame, start: int, end: int, bout_type: str, profile: dict[str, Any]) -> dict[str, Any]:
    seg = g.iloc[start : end + 1]
    first = seg.iloc[0]
    last = seg.iloc[-1]
    duration = float(last["elapsed_sec"] - first["elapsed_sec"])
    dist = float(last["route_dist_m"] - first["route_dist_m"]) if pd.notna(last["route_dist_m"]) and pd.notna(first["route_dist_m"]) else np.nan
    gain = float(seg["positive_delta_elevation_m"].sum(skipna=True))
    hr = pd.to_numeric(seg["heart_rate_bpm"], errors="coerce")
    hr = hr[(hr >= 40) & (hr <= 220)]
    hrmax = profile.get("hrmax_bpm", np.nan)
    pct = hr / hrmax * 100 if pd.notna(hrmax) and hrmax > 0 else pd.Series(dtype=float)
    return {
        "activity_id_short": first["activity_id_short"],
        "participant_id": first["participant_id"],
        "bout_type": bout_type,
        "bout_start_elapsed_sec": float(first["elapsed_sec"]),
        "bout_end_elapsed_sec": float(last["elapsed_sec"]),
        "bout_duration_sec": duration,
        "bout_route_dist_delta_m": dist,
        "bout_gain_m": gain,
        "bout_vam_mph": gain / duration * 3600 if duration > 0 else np.nan,
        "bout_median_slope_pct": float(seg["calibrated_slope_pct"].median(skipna=True)),
        "bout_steps_context_ratio": float(seg["steps_context_bool"].mean()) if len(seg) else np.nan,
        "pause_or_stall_ratio": float(seg["pause_or_stall_bool"].mean()) if len(seg) else np.nan,
        "elevation_step_valid_ratio": float(seg["elevation_step_valid_bool"].mean()) if len(seg) else np.nan,
        "hr_start_bpm": float(hr.iloc[0]) if len(hr) else np.nan,
        "hr_end_bpm": float(hr.iloc[-1]) if len(hr) else np.nan,
        "hr_peak_bpm": float(hr.max()) if len(hr) else np.nan,
        "hr_delta_bpm": float(hr.iloc[-1] - hr.iloc[0]) if len(hr) else np.nan,
        "hr_rise_rate_bpm_per_min": float((hr.iloc[-1] - hr.iloc[0]) / duration * 60) if len(hr) and duration > 0 else np.nan,
        "hr_p90_bpm": q(hr, 0.90),
        "hr_range_bpm": float(hr.max() - hr.min()) if len(hr) else np.nan,
        "hr_start_pct_hrmax": float(pct.iloc[0]) if len(pct) else np.nan,
        "hr_end_pct_hrmax": float(pct.iloc[-1]) if len(pct) else np.nan,
        "hr_peak_pct_hrmax": float(pct.max()) if len(pct) else np.nan,
        "hr_delta_pct_hrmax": float(pct.iloc[-1] - pct.iloc[0]) if len(pct) else np.nan,
        "hr_rise_rate_pct_hrmax_per_min": float((pct.iloc[-1] - pct.iloc[0]) / duration * 60) if len(pct) and duration > 0 else np.nan,
        "hr_p90_pct_hrmax": q(pct, 0.90),
        "hrmax_bpm": hrmax,
        "hrmax_source": profile.get("hrmax_source", ""),
        "profile_join_status": profile.get("profile_join_status", "MISSING_PROFILE"),
        "interpretation_boundary": BOUNDARY,
    }


def build_bouts(g: pd.DataFrame, profile: dict[str, Any]) -> pd.DataFrame:
    rows = []
    ascent_flag = (
        g["calibrated_slope_pct"].gt(5).fillna(False)
        & g["route_dist_m"].diff().fillna(0).ge(0)
        & g["elevation_step_valid_bool"]
    )
    steps_flag = g["steps_context_bool"]
    for start, end in segment_runs(g, ascent_flag, 120):
        row = bout_row(g, start, end, "continuous_ascent_bout", profile)
        if row["bout_route_dist_delta_m"] > 0 and row["bout_gain_m"] >= 10 and row["pause_or_stall_ratio"] <= 0.5:
            rows.append(row)
    for start, end in segment_runs(g, steps_flag, 60):
        row = bout_row(g, start, end, "continuous_steps_bout", profile)
        if row["bout_route_dist_delta_m"] > 0:
            rows.append(row)
    return pd.DataFrame(rows)


def build_recovery_events(g: pd.DataFrame, bouts: pd.DataFrame, profile: dict[str, Any]) -> pd.DataFrame:
    rows = []
    if bouts.empty:
        return pd.DataFrame(rows)
    hrmax = profile.get("hrmax_bpm", np.nan)
    for _, bout in bouts.iterrows():
        start_time = float(bout["bout_end_elapsed_sec"])
        after = g[g["elapsed_sec"].ge(start_time)].copy()
        if after.empty:
            continue
        low_speed = after["pause_or_stall_bool"] | after["route_dist_m"].diff().fillna(0).le(0.3)
        runs = segment_runs(after.reset_index(drop=True), low_speed.reset_index(drop=True), 30)
        if not runs:
            continue
        rs, re = runs[0]
        pause = after.reset_index(drop=True).iloc[rs : re + 1]
        recovery_start = float(pause.iloc[0]["elapsed_sec"])
        recovery_end = float(pause.iloc[-1]["elapsed_sec"])
        hr_at_start = pd.to_numeric(pause.iloc[:5]["heart_rate_bpm"], errors="coerce").dropna()
        start_hr = float(hr_at_start.iloc[0]) if len(hr_at_start) else np.nan
        rec = after[(after["elapsed_sec"] >= recovery_start) & (after["elapsed_sec"] <= recovery_start + 180)].copy()
        hr = pd.to_numeric(rec["heart_rate_bpm"], errors="coerce")
        hr = hr[(hr >= 40) & (hr <= 220)]

        def min_in(sec: float) -> float:
            part = rec[rec["elapsed_sec"].le(recovery_start + sec)]
            vals = pd.to_numeric(part["heart_rate_bpm"], errors="coerce")
            vals = vals[(vals >= 40) & (vals <= 220)]
            return float(vals.min()) if len(vals) else np.nan

        mins = {60: min_in(60), 120: min_in(120), 180: min_in(180)}

        def time_to_drop(drop: float) -> float:
            if pd.isna(start_hr):
                return np.nan
            target = start_hr - drop
            rec2 = rec.copy()
            vals = pd.to_numeric(rec2["heart_rate_bpm"], errors="coerce")
            hit = rec2[vals.le(target)]
            return float(hit.iloc[0]["elapsed_sec"] - recovery_start) if len(hit) else np.nan

        row = {
            "activity_id_short": bout["activity_id_short"],
            "participant_id": bout["participant_id"],
            "recovery_start_elapsed_sec": recovery_start,
            "recovery_end_elapsed_sec": recovery_end,
            "recovery_duration_sec": recovery_end - recovery_start,
            "preceding_bout_type": bout["bout_type"],
            "preceding_bout_gain_m": bout["bout_gain_m"],
            "preceding_bout_vam_mph": bout["bout_vam_mph"],
            "preceding_bout_hr_peak_bpm": bout["hr_peak_bpm"],
            "hr_at_pause_start_bpm": start_hr,
            "hr_min_60s_bpm": mins[60],
            "hr_min_120s_bpm": mins[120],
            "hr_min_180s_bpm": mins[180],
            "hr_drop_60s_bpm": start_hr - mins[60] if pd.notna(start_hr) and pd.notna(mins[60]) else np.nan,
            "hr_drop_120s_bpm": start_hr - mins[120] if pd.notna(start_hr) and pd.notna(mins[120]) else np.nan,
            "hr_drop_180s_bpm": start_hr - mins[180] if pd.notna(start_hr) and pd.notna(mins[180]) else np.nan,
            "time_to_drop_10bpm_sec": time_to_drop(10),
            "time_to_drop_20bpm_sec": time_to_drop(20),
            "hrmax_bpm": hrmax,
            "hrmax_source": profile.get("hrmax_source", ""),
            "profile_join_status": profile.get("profile_join_status", "MISSING_PROFILE"),
            "interpretation_boundary": BOUNDARY,
        }
        for sec in [60, 120, 180]:
            drop = row[f"hr_drop_{sec}s_bpm"]
            row[f"hr_drop_{sec}s_pct_hrmax"] = drop / hrmax * 100 if pd.notna(drop) and pd.notna(hrmax) and hrmax > 0 else np.nan
            row[f"hr_recovery_rate_{sec}s_bpm_per_min"] = drop / sec * 60 if pd.notna(drop) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def source_inventory(source_paths: list[Path], radar_activities: set[str]) -> pd.DataFrame:
    rows = []
    for path in source_paths:
        aid = activity_short_from_path(path)
        rows.append({
            "activity_id_short": aid,
            "source_path": str(path),
            "source_file_size_bytes": path.stat().st_size,
            "in_radar_baseline": aid in radar_activities,
            "source_layer": "ch6_single_activity_mainline_profile_v2_3_2",
            "inventory_status": "RADAR_BASELINE_ACTIVITY" if aid in radar_activities else "EXTRA_SOURCE_ACTIVITY_NOT_IN_RADAR_BASELINE",
            "interpretation_boundary": BOUNDARY,
        })
    return pd.DataFrame(rows).sort_values("activity_id_short")


def audit_frame(
    inventory: pd.DataFrame,
    radar_activities: set[str],
    missing_columns: dict[str, list[str]],
    windows: pd.DataFrame,
    profiles: pd.DataFrame,
    output_columns: list[str],
) -> pd.DataFrame:
    joined = int((profiles["profile_join_status"] == "PROFILE_JOINED").sum()) if not profiles.empty else 0
    missing_profile = int((profiles["profile_join_status"] != "PROFILE_JOINED").sum()) if not profiles.empty else 0
    forbidden = [c for c in output_columns if any(p in c.lower() for p in FORBIDDEN_OUTPUT_PATTERNS)]
    review_reasons = []
    if missing_columns:
        review_reasons.append("MISSING_CORE_COLUMNS")
    if forbidden:
        review_reasons.append("FORBIDDEN_FIELD_PRESENT")
    conclusion = REVIEW if review_reasons else PASS
    row = {
        "source_files_count": int(len(inventory)),
        "radar_baseline_activity_count": int(len(radar_activities)),
        "extra_source_activities": "|".join(inventory.loc[~inventory["in_radar_baseline"], "activity_id_short"].astype(str)),
        "missing_core_columns": ";".join(f"{k}:{'|'.join(v)}" for k, v in missing_columns.items()) if missing_columns else "NONE",
        "rolling_window_count": int(len(windows)),
        "horizontal_valid_window_count": int(windows["horizontal_300s_window_status"].eq("VALID_HORIZONTAL_WINDOW").sum()) if not windows.empty else 0,
        "vertical_valid_window_count": int(windows["vertical_300s_window_status"].eq("VALID_VERTICAL_WINDOW").sum()) if not windows.empty else 0,
        "hr_valid_window_count": int(windows["hr_window_status"].eq("VALID_HR_WINDOW").sum()) if not windows.empty else 0,
        "profile_join_count": joined,
        "missing_profile_count": missing_profile,
        "elevation_validity": float(windows["elevation_step_valid_ratio"].mean()) if not windows.empty else np.nan,
        "zero_fill_used": False,
        "forbidden_score_rank_class_fields_present": bool(forbidden),
        "forbidden_fields": "|".join(forbidden) if forbidden else "NONE",
        "radar_scoring_absent": True,
        "ability_scoring_absent": True,
        "ranking_absent": True,
        "class_label_absent": True,
        "decision_label_absent": True,
        "diagnosis_absent": True,
        "causal_claim_absent": True,
        "audit_conclusion": conclusion,
        "review_reasons": "|".join(review_reasons) if review_reasons else "NONE",
        "interpretation_boundary": BOUNDARY,
    }
    return pd.DataFrame([row])


def write_html(out_path: Path, audit: pd.DataFrame, inventory: pd.DataFrame, summary: pd.DataFrame, bouts: pd.DataFrame, recovery: pd.DataFrame) -> None:
    def table(df: pd.DataFrame, cols: list[str], n: int = 20) -> str:
        if df.empty:
            return "<p>No rows.</p>"
        use = [c for c in cols if c in df.columns]
        return df[use].head(n).to_html(index=False, escape=True, classes="data")

    conclusion = audit.iloc[0]["audit_conclusion"] if not audit.empty else REVIEW
    body = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CH6.5.5 Movement 300s Corrected-Data Study v1</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2933; }}
h1, h2 {{ margin-bottom: 8px; }}
.boundary {{ border-left: 4px solid #687078; padding: 8px 12px; background: #f5f7f8; }}
.status {{ font-weight: 700; }}
table.data {{ border-collapse: collapse; font-size: 12px; margin: 12px 0 24px; }}
table.data th, table.data td {{ border: 1px solid #d6dde3; padding: 5px 7px; }}
table.data th {{ background: #eef2f5; }}
</style>
</head>
<body>
<h1>CH6.5.5 Movement 300s Corrected-Data Study v1</h1>
<p class="status">{html.escape(str(conclusion))}</p>
<p class="boundary">{html.escape(BOUNDARY)}</p>
<h2>Audit</h2>
{table(audit, list(audit.columns), 5)}
<h2>Source Inventory</h2>
{table(inventory, ["activity_id_short", "in_radar_baseline", "inventory_status", "source_path"], 50)}
<h2>Activity Summary</h2>
{table(summary, ["activity_id_short", "rolling_window_count", "horizontal_300s_valid_window_count", "horizontal_300s_route_speed_p90_mps", "vertical_300s_valid_window_count", "vertical_300s_vam_p90_mph", "hr_valid_window_count", "profile_join_status"], 50)}
<h2>Ascent and Steps Bouts</h2>
{table(bouts, ["activity_id_short", "bout_type", "bout_duration_sec", "bout_gain_m", "bout_vam_mph", "hr_peak_bpm", "hr_delta_bpm"], 50)}
<h2>Pause Recovery Events</h2>
{table(recovery, ["activity_id_short", "preceding_bout_type", "recovery_duration_sec", "hr_at_pause_start_bpm", "hr_drop_60s_bpm", "hr_drop_120s_bpm", "hr_drop_180s_bpm"], 50)}
</body>
</html>
"""
    out_path.write_text(body, encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    source_root = resolve(root, args.source_root)
    radar_path = resolve(root, args.radar_axis_table)
    profile_path = resolve(root, args.profile_join)
    out_root = resolve(root, args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)

    radar = read_csv(radar_path, "radar baseline axis table")
    radar_activities = set(radar["activity_id_short"].dropna().astype(str).str.strip())
    profiles = load_profile(profile_path)
    profile_map = profiles.set_index("activity_id_short").to_dict("index") if not profiles.empty else {}

    source_paths = sorted(source_root.glob("*/activity_*_projected_joined_v2_3_2.csv"))
    inventory = source_inventory(source_paths, radar_activities)

    all_windows: list[dict[str, Any]] = []
    all_bouts: list[pd.DataFrame] = []
    all_recovery: list[pd.DataFrame] = []
    missing_columns: dict[str, list[str]] = {}
    required = ["elapsed_sec", "calibrated_elevation_m", "calibrated_delta_elevation_m", "calibrated_cumulative_gain_m"]

    for path in source_paths:
        raw = read_csv(path, f"source activity {path.name}")
        aid = activity_short_from_frame(raw, path)
        missing = [c for c in required if c not in raw.columns]
        if not ({"route_dist_m", "v2_3_projected_route_distance_m", "nearest_route_dist_m"} & set(raw.columns)):
            missing.append("route_dist_m_or_v2_3_projected_route_distance_m")
        if missing:
            missing_columns[aid] = missing
        g = prepare_activity(raw, path)
        profile = profile_map.get(aid, {
            "hrmax_bpm": np.nan,
            "hrmax_source": "",
            "profile_join_status": "MISSING_PROFILE",
            "profile_join_reason": "NO_PROFILE_JOIN_ROW",
        })
        all_windows.extend(build_windows(g, profile, str(path), args.window_sec, args.min_duration_sec, args.step_sec))
        bouts = build_bouts(g, profile)
        if not bouts.empty:
            all_bouts.append(bouts)
            recovery = build_recovery_events(g, bouts, profile)
            if not recovery.empty:
                all_recovery.append(recovery)

    windows = pd.DataFrame(all_windows)
    summary = summarize_windows(windows) if not windows.empty else pd.DataFrame()
    bouts = pd.concat(all_bouts, ignore_index=True) if all_bouts else pd.DataFrame()
    recovery = pd.concat(all_recovery, ignore_index=True) if all_recovery else pd.DataFrame()
    hr_summary = summarize_hr_response(windows, bouts, recovery) if not windows.empty else pd.DataFrame()

    output_columns = list(inventory.columns) + list(windows.columns) + list(summary.columns) + list(bouts.columns) + list(recovery.columns) + list(hr_summary.columns)
    audit = audit_frame(inventory, radar_activities, missing_columns, windows, profiles, output_columns)

    outputs = {
        "inventory": out_root / "movement_300s_source_inventory_v1.csv",
        "windows": out_root / "movement_300s_window_candidates_v1.csv",
        "summary": out_root / "movement_300s_activity_summary_v1.csv",
        "bouts": out_root / "movement_hr_ascent_bouts_v1.csv",
        "recovery": out_root / "movement_hr_pause_recovery_events_v1.csv",
        "hr_summary": out_root / "movement_hr_response_activity_summary_v1.csv",
        "audit": out_root / "movement_300s_audit_v1.csv",
        "html": out_root / "movement_300s_report_v1.html",
    }

    inventory.to_csv(outputs["inventory"], index=False, encoding="utf-8-sig")
    windows.to_csv(outputs["windows"], index=False, encoding="utf-8-sig")
    summary.to_csv(outputs["summary"], index=False, encoding="utf-8-sig")
    bouts.to_csv(outputs["bouts"], index=False, encoding="utf-8-sig")
    recovery.to_csv(outputs["recovery"], index=False, encoding="utf-8-sig")
    hr_summary.to_csv(outputs["hr_summary"], index=False, encoding="utf-8-sig")
    audit.to_csv(outputs["audit"], index=False, encoding="utf-8-sig")
    write_html(outputs["html"], audit, inventory, summary, bouts, recovery)

    print({
        "output_root": str(out_root),
        "source_files_count": int(len(inventory)),
        "rolling_window_count": int(len(windows)),
        "horizontal_valid_window_count": int(audit.iloc[0]["horizontal_valid_window_count"]),
        "vertical_valid_window_count": int(audit.iloc[0]["vertical_valid_window_count"]),
        "hr_valid_window_count": int(audit.iloc[0]["hr_valid_window_count"]),
        "audit_conclusion": str(audit.iloc[0]["audit_conclusion"]),
        "outputs": {k: str(v) for k, v in outputs.items()},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
