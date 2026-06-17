#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build CH6.5.1 personal/activity-group behavior profile v1.1.

v1.1 adds route-phase recovery for profile comparison using signed route-window
slope from the full25 activity behavior windows.

The route phase used here is a conservative descriptive route-context phase:
- calibrated_slope_pct_median >= +3%  => UPHILL_ROUTE_CONTEXT
- calibrated_slope_pct_median <= -3%  => DOWNHILL_ROUTE_CONTEXT
- otherwise                           => LOW_SLOPE_OR_MIXED_ROUTE_CONTEXT
- missing / unparsable slope          => SLOPE_MISSING_REVIEW_REQUIRED

Boundaries:
- descriptive personal/activity-group behavior profile only
- no ability score, rank, or class
- no THCI score, radar score, final hiking risk score, route suitability score
- no go/no-go decision
- no medical diagnosis
- no causality inference
- no weather zero-fill
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


DEFAULT_ROUTE_FOLDER = "qixing_lengshuikeng"
DEFAULT_PROFILE_ID = "qixing_lengshuikeng_activity_group_full25"

DEFAULT_BEHAVIOR_WINDOWS = (
    "outputs/ib3_personal_hiking_features_route_load_comparison_full25_v1/"
    "activity_route_load_behavior_response_windows.csv"
)
DEFAULT_ROUTE_LOAD_ROOT = "outputs/report_figures/ch6_5_route_load_context_index_v1"
DEFAULT_HR_RECOVERY_ROOT = "outputs/report_figures/ch6_7_hr_recovery_from_ib3c_events_v1_1"
DEFAULT_COMPLETION_ROOT = "outputs/report_figures/ch6_7_completion_feasibility_review_v1_1"
DEFAULT_READINESS_ROOT = "outputs/report_figures/ch6_8_personal_route_load_readiness_review_v1_1"

DEFAULT_OUTPUT_ROOT = "outputs/report_figures/ch6_5_1_personal_activity_behavior_profile_v1_1"

ROUTE_LOAD_BAND_ORDER = [
    "LOWER_ROUTE_LOAD_CONTEXT",
    "MODERATE_ROUTE_LOAD_CONTEXT",
    "HIGH_ROUTE_LOAD_CONTEXT",
    "VERY_HIGH_ROUTE_LOAD_CONTEXT",
    "ROUTE_LOAD_CONTEXT_MISSING",
]

ROUTE_PHASE_ORDER = [
    "UPHILL_ROUTE_CONTEXT",
    "DOWNHILL_ROUTE_CONTEXT",
    "LOW_SLOPE_OR_MIXED_ROUTE_CONTEXT",
    "SLOPE_MISSING_REVIEW_REQUIRED",
]

FORBIDDEN_OUTPUT_TOKENS = [
    "ability_score",
    "ability_rank",
    "ability_class",
    "thci_score",
    "radar_score",
    "final_hiking_risk_score",
    "route_suitability_score",
    "go_no_go",
    "medical_diagnosis",
]

BOUNDARY_TEXT = (
    "Descriptive CH6.5.1 personal/activity-group behavior profile only. "
    "This evidence summarizes historical route-window behavior under route-load "
    "context bands and recovered route-context phases. It is not an ability "
    "score, ability rank, ability class, THCI score, radar score, final hiking "
    "risk score, route suitability score, go/no-go decision, medical diagnosis, "
    "or causality result. Weather context is descriptive only and missing weather "
    "is not zero-filled."
)

ROUTE_PHASE_NOTE = (
    "route_phase_for_profile is recovered from signed calibrated_slope_pct_median "
    "and is descriptive route context only. It must not be interpreted as strict "
    "uphill/downhill ability or causality."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=r"D:\mountain_work\115_osm")
    parser.add_argument("--route-folder", default=DEFAULT_ROUTE_FOLDER)
    parser.add_argument("--profile-id", default=DEFAULT_PROFILE_ID)
    parser.add_argument("--behavior-windows", default=DEFAULT_BEHAVIOR_WINDOWS)
    parser.add_argument("--route-load-root", default=DEFAULT_ROUTE_LOAD_ROOT)
    parser.add_argument("--hr-recovery-root", default=DEFAULT_HR_RECOVERY_ROOT)
    parser.add_argument("--completion-root", default=DEFAULT_COMPLETION_ROOT)
    parser.add_argument("--readiness-root", default=DEFAULT_READINESS_ROOT)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--uphill-threshold-pct", type=float, default=3.0)
    parser.add_argument("--downhill-threshold-pct", type=float, default=-3.0)
    return parser.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def read_csv(path: Path | None, label: str, required: bool = True) -> pd.DataFrame:
    if path is None or not path.exists():
        if required:
            raise FileNotFoundError(f"Missing {label}: {path}")
        return pd.DataFrame()
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def clean_str(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip()


def pipe_flags(values: Iterable[str]) -> str:
    out: list[str] = []
    for value in values:
        if value is None:
            continue
        s = str(value).strip()
        if not s or s.lower() == "nan" or s == "NONE":
            continue
        for part in s.split("|"):
            p = part.strip()
            if p and p.lower() != "nan" and p != "NONE":
                out.append(p)
    return "|".join(sorted(set(out))) if out else "NONE"


def q(series: pd.Series, quantile: float) -> float:
    s = numeric(series).dropna()
    return float(s.quantile(quantile)) if not s.empty else np.nan


def ratio_true(series: pd.Series) -> float:
    if len(series) == 0:
        return np.nan
    return float(series.fillna(False).astype(bool).sum()) / float(len(series))


def require_columns(df: pd.DataFrame, cols: list[str], label: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(f"{label} missing required columns: {missing}; available={list(df.columns)}")


def find_file(root: Path, names: list[str]) -> Path | None:
    for name in names:
        path = root / name
        if path.exists():
            return path
    return None


def build_source_inventory(paths: dict[str, Path | None]) -> pd.DataFrame:
    rows = []
    for label, path in paths.items():
        exists = bool(path is not None and path.exists())
        rows.append({
            "source_label": label,
            "source_path": str(path) if path is not None else "",
            "exists": exists,
            "length_bytes": int(path.stat().st_size) if exists else 0,
        })
    return pd.DataFrame(rows)


def recover_route_phase(
    slope_value: object,
    uphill_threshold: float,
    downhill_threshold: float,
) -> tuple[str, str, str]:
    slope = pd.to_numeric(pd.Series([slope_value]), errors="coerce").iloc[0]
    if pd.isna(slope):
        return (
            "SLOPE_MISSING_REVIEW_REQUIRED",
            "CALIBRATED_SLOPE_PCT_MEDIAN_MISSING",
            "ROUTE_PHASE_RECOVERY_REVIEW_REQUIRED",
        )
    if float(slope) >= uphill_threshold:
        return (
            "UPHILL_ROUTE_CONTEXT",
            "CALIBRATED_SLOPE_PCT_MEDIAN",
            "RECOVERED_UPHILL_FROM_SIGNED_SLOPE",
        )
    if float(slope) <= downhill_threshold:
        return (
            "DOWNHILL_ROUTE_CONTEXT",
            "CALIBRATED_SLOPE_PCT_MEDIAN",
            "RECOVERED_DOWNHILL_FROM_SIGNED_SLOPE",
        )
    return (
        "LOW_SLOPE_OR_MIXED_ROUTE_CONTEXT",
        "CALIBRATED_SLOPE_PCT_MEDIAN",
        "RECOVERED_LOW_SLOPE_OR_MIXED_FROM_SIGNED_SLOPE",
    )


def add_candidate_marker(w: pd.DataFrame, candidate_windows: pd.DataFrame) -> pd.Series:
    key_cols = ["activity_id_short", "route_distance_window_start_m", "route_distance_window_end_m"]
    if candidate_windows.empty or not all(c in candidate_windows.columns for c in key_cols):
        return pd.Series(False, index=w.index)

    cw = candidate_windows.copy()
    for c in ["route_distance_window_start_m", "route_distance_window_end_m"]:
        cw[c] = numeric(cw[c])

    keys = set(tuple(row) for row in cw[key_cols].dropna(subset=key_cols).itertuples(index=False, name=None))
    return pd.Series(
        [(a, s, e) in keys for a, s, e in w[key_cols].itertuples(index=False, name=None)],
        index=w.index,
    )


def build_windows(
    behavior_windows: pd.DataFrame,
    candidate_windows: pd.DataFrame,
    profile_id: str,
    route_folder: str,
    uphill_threshold: float,
    downhill_threshold: float,
) -> pd.DataFrame:
    required = [
        "activity_id_short",
        "route_distance_window_start_m",
        "route_distance_window_end_m",
        "route_phase",
        "calibrated_slope_pct_median",
        "route_load_context_band",
        "speed_mps_median",
        "low_speed_ratio",
        "stopped_ratio",
        "heart_rate_bpm_median",
    ]
    require_columns(behavior_windows, required, "activity_route_load_behavior_response_windows")

    w = behavior_windows.copy()
    w["profile_id"] = profile_id
    w["profile_scope"] = "ACTIVITY_GROUP"
    w["route_folder"] = route_folder

    numeric_cols = [
        "route_distance_window_start_m",
        "route_distance_window_end_m",
        "point_count",
        "calibrated_slope_pct_median",
        "calibrated_slope_pct_p75_abs",
        "speed_mps_median",
        "speed_mps_p25",
        "speed_mps_p75",
        "low_speed_ratio",
        "stopped_ratio",
        "heart_rate_bpm_median",
        "heart_rate_bpm_p75",
        "heart_rate_bpm_p90",
        "temperature_c",
        "relative_humidity_pct",
        "precipitation_mm",
        "wind_speed_ms",
        "wind_gust_ms",
        "uv_index",
    ]
    for c in numeric_cols:
        if c in w.columns:
            w[c] = numeric(w[c])

    w["route_phase_original"] = clean_str(w["route_phase"]).replace("", "UNKNOWN")
    recovered = w["calibrated_slope_pct_median"].apply(
        lambda x: recover_route_phase(x, uphill_threshold, downhill_threshold)
    )
    w["route_phase_for_profile"] = [x[0] for x in recovered]
    w["route_phase_recovery_source"] = [x[1] for x in recovered]
    w["route_phase_recovery_flags"] = [x[2] for x in recovered]

    w["route_load_context_band_original"] = clean_str(w["route_load_context_band"]).replace("", "ROUTE_LOAD_CONTEXT_MISSING")
    route_load_band_map = {
        "LOWER_ROUTE_LOAD_EVIDENCE": "LOWER_ROUTE_LOAD_CONTEXT",
        "MODERATE_ROUTE_LOAD_EVIDENCE": "MODERATE_ROUTE_LOAD_CONTEXT",
        "HIGH_ROUTE_LOAD_EVIDENCE": "HIGH_ROUTE_LOAD_CONTEXT",
        "VERY_HIGH_ROUTE_LOAD_EVIDENCE": "VERY_HIGH_ROUTE_LOAD_CONTEXT",
        "LOWER_ROUTE_LOAD_CONTEXT": "LOWER_ROUTE_LOAD_CONTEXT",
        "MODERATE_ROUTE_LOAD_CONTEXT": "MODERATE_ROUTE_LOAD_CONTEXT",
        "HIGH_ROUTE_LOAD_CONTEXT": "HIGH_ROUTE_LOAD_CONTEXT",
        "VERY_HIGH_ROUTE_LOAD_CONTEXT": "VERY_HIGH_ROUTE_LOAD_CONTEXT",
    }
    w["route_load_context_band"] = w["route_load_context_band_original"].map(route_load_band_map).fillna("ROUTE_LOAD_CONTEXT_MISSING")

    if "window_qa_flags" not in w.columns:
        w["window_qa_flags"] = "NONE"
    w["window_qa_flags"] = clean_str(w["window_qa_flags"]).replace("", "NONE")

    if "weather_context_available" in w.columns:
        w["weather_context_available_bool"] = clean_str(w["weather_context_available"]).str.lower().isin(["true", "1", "yes", "y"])
    else:
        w["weather_context_available_bool"] = False

    if "behavior_response_flags" not in w.columns:
        # Original full25 windows do not always have behavior_response_flags;
        # reconstruct from observable signals for descriptive output.
        flags = []
        for _, row in w.iterrows():
            fs: list[str] = []
            if pd.notna(row.get("speed_mps_median")) and float(row["speed_mps_median"]) < 0.7:
                fs.append("SPEED_BELOW_LOW_SPEED_THRESHOLD")
            if pd.notna(row.get("low_speed_ratio")) and float(row["low_speed_ratio"]) >= 0.30:
                fs.append("LOW_SPEED_RATIO_HIGH")
            if pd.notna(row.get("stopped_ratio")) and float(row["stopped_ratio"]) > 0.05:
                fs.append("STOP_RATIO_OBSERVED")
            flags.append(pipe_flags(fs))
        w["behavior_response_flags"] = flags
    else:
        w["behavior_response_flags"] = clean_str(w["behavior_response_flags"]).replace("", "NONE")

    # Activity-relative high HR window.
    hr = w["heart_rate_bpm_median"]
    activity_hr_p75 = hr.groupby(w["activity_id_short"]).transform(
        lambda s: s.quantile(0.75) if s.notna().any() else np.nan
    )
    w["activity_heart_rate_bpm_median_p75"] = activity_hr_p75
    w["high_hr_window_bool"] = hr.notna() & activity_hr_p75.notna() & (hr >= activity_hr_p75)

    w["low_speed_window_bool"] = numeric(w["low_speed_ratio"]).fillna(0) >= 0.30
    w["stopped_window_bool"] = numeric(w["stopped_ratio"]).fillna(0) > 0.05
    w["route_load_behavior_candidate_window_bool"] = add_candidate_marker(w, candidate_windows)

    w["route_phase_for_profile_note"] = ROUTE_PHASE_NOTE
    w["interpretation_boundary"] = BOUNDARY_TEXT
    return w


def aggregate_response(group: pd.DataFrame, profile_id: str, route_folder: str) -> dict[str, object]:
    activity_ids = sorted(group["activity_id_short"].dropna().astype(str).unique().tolist())
    return {
        "profile_id": profile_id,
        "profile_scope": "ACTIVITY_GROUP",
        "route_folder": route_folder,
        "activity_count": int(len(activity_ids)),
        "activity_id_short_list": "|".join(activity_ids),
        "windows_n": int(len(group)),
        "speed_mps_median_p25": round(q(group.get("speed_mps_median", pd.Series(dtype=float)), 0.25), 6),
        "speed_mps_median_median": round(q(group.get("speed_mps_median", pd.Series(dtype=float)), 0.50), 6),
        "speed_mps_median_p75": round(q(group.get("speed_mps_median", pd.Series(dtype=float)), 0.75), 6),
        "low_speed_ratio_avg": round(float(numeric(group.get("low_speed_ratio", pd.Series(dtype=float))).mean()), 6),
        "low_speed_ratio_median": round(q(group.get("low_speed_ratio", pd.Series(dtype=float)), 0.50), 6),
        "stopped_ratio_avg": round(float(numeric(group.get("stopped_ratio", pd.Series(dtype=float))).mean()), 6),
        "stopped_ratio_median": round(q(group.get("stopped_ratio", pd.Series(dtype=float)), 0.50), 6),
        "heart_rate_bpm_median_avg": round(float(numeric(group.get("heart_rate_bpm_median", pd.Series(dtype=float))).mean()), 6),
        "heart_rate_bpm_median_median": round(q(group.get("heart_rate_bpm_median", pd.Series(dtype=float)), 0.50), 6),
        "heart_rate_bpm_p75_median": round(q(group.get("heart_rate_bpm_p75", pd.Series(dtype=float)), 0.50), 6)
        if "heart_rate_bpm_p75" in group.columns else np.nan,
        "high_hr_window_ratio": round(ratio_true(group.get("high_hr_window_bool", pd.Series(dtype=bool))), 6),
        "low_speed_window_ratio": round(ratio_true(group.get("low_speed_window_bool", pd.Series(dtype=bool))), 6),
        "stopped_window_ratio": round(ratio_true(group.get("stopped_window_bool", pd.Series(dtype=bool))), 6),
        "route_load_behavior_candidate_window_ratio": round(
            ratio_true(group.get("route_load_behavior_candidate_window_bool", pd.Series(dtype=bool))), 6
        ),
        "weather_context_available_ratio": round(ratio_true(group.get("weather_context_available_bool", pd.Series(dtype=bool))), 6),
        "data_quality_flags": pipe_flags(group.get("window_qa_flags", pd.Series(dtype=str)).astype(str).tolist()),
        "behavior_response_flags_observed": pipe_flags(group.get("behavior_response_flags", pd.Series(dtype=str)).astype(str).tolist()),
        "route_phase_recovery_flags_observed": pipe_flags(group.get("route_phase_recovery_flags", pd.Series(dtype=str)).astype(str).tolist()),
        "interpretation_boundary": BOUNDARY_TEXT,
    }


def sort_band_phase(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    if "route_load_context_band" in df.columns:
        df["route_load_context_band"] = pd.Categorical(
            df["route_load_context_band"],
            categories=ROUTE_LOAD_BAND_ORDER,
            ordered=True,
        )
    if "route_phase_for_profile" in df.columns:
        df["route_phase_for_profile"] = pd.Categorical(
            df["route_phase_for_profile"],
            categories=ROUTE_PHASE_ORDER,
            ordered=True,
        )
    sort_cols = [c for c in ["route_load_context_band", "route_phase_for_profile"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols).reset_index(drop=True)
    for c in ["route_load_context_band", "route_phase_for_profile"]:
        if c in df.columns:
            df[c] = df[c].astype(str)
    return df


def build_route_load_phase_profile(w: pd.DataFrame, profile_id: str, route_folder: str) -> pd.DataFrame:
    rows = []
    for (band, phase), group in w.groupby(["route_load_context_band", "route_phase_for_profile"], dropna=False):
        row = aggregate_response(group, profile_id, route_folder)
        row["route_load_context_band"] = band
        row["route_phase_for_profile"] = phase
        row["route_phase_original_values"] = pipe_flags(group["route_phase_original"].astype(str).tolist())
        row["route_phase_recovery_source_values"] = pipe_flags(group["route_phase_recovery_source"].astype(str).tolist())
        row["route_phase_for_profile_note"] = ROUTE_PHASE_NOTE
        rows.append(row)
    return sort_band_phase(pd.DataFrame(rows))


def build_phase_summary(w: pd.DataFrame, profile_id: str, route_folder: str) -> pd.DataFrame:
    rows = []
    for phase, group in w.groupby("route_phase_for_profile", dropna=False):
        row = aggregate_response(group, profile_id, route_folder)
        row["route_phase_for_profile"] = phase
        row["route_phase_original_values"] = pipe_flags(group["route_phase_original"].astype(str).tolist())
        row["route_phase_recovery_source_values"] = pipe_flags(group["route_phase_recovery_source"].astype(str).tolist())
        row["route_phase_for_profile_note"] = ROUTE_PHASE_NOTE
        rows.append(row)
    out = pd.DataFrame(rows)
    if not out.empty:
        out["route_phase_for_profile"] = pd.Categorical(out["route_phase_for_profile"], categories=ROUTE_PHASE_ORDER, ordered=True)
        out = out.sort_values("route_phase_for_profile").reset_index(drop=True)
        out["route_phase_for_profile"] = out["route_phase_for_profile"].astype(str)
    return out


def build_band_summary(w: pd.DataFrame, profile_id: str, route_folder: str) -> pd.DataFrame:
    rows = []
    for band, group in w.groupby("route_load_context_band", dropna=False):
        row = aggregate_response(group, profile_id, route_folder)
        row["route_load_context_band"] = band
        rows.append(row)
    out = pd.DataFrame(rows)
    if not out.empty:
        out["route_load_context_band"] = pd.Categorical(out["route_load_context_band"], categories=ROUTE_LOAD_BAND_ORDER, ordered=True)
        out = out.sort_values("route_load_context_band").reset_index(drop=True)
        out["route_load_context_band"] = out["route_load_context_band"].astype(str)
    return out


def any_flag_contains(df: pd.DataFrame, patterns: list[str]) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=bool)
    flag_cols = [c for c in df.columns if any(token in c.lower() for token in ["flag", "reason", "gate", "review", "status"])]
    if not flag_cols:
        return pd.Series(False, index=df.index)
    text = df[flag_cols].astype(str).agg(lambda row: "|".join([str(x) for x in row]), axis=1).str.lower()
    mask = pd.Series(False, index=df.index)
    for pat in patterns:
        mask = mask | text.str.contains(pat.lower(), regex=False, na=False)
    return mask


def build_activity_summary(
    w: pd.DataFrame,
    route_load_activity_summary: pd.DataFrame,
    hr_activity_summary: pd.DataFrame,
    completion_conclusion: pd.DataFrame,
    readiness_review: pd.DataFrame,
    profile_id: str,
    route_folder: str,
) -> pd.DataFrame:
    rows = []
    for activity_id, group in w.groupby("activity_id_short", dropna=False):
        row = aggregate_response(group, profile_id, route_folder)
        row["activity_id_short"] = activity_id
        row["activity_windows_n"] = int(len(group))
        row["uphill_windows_n"] = int((group["route_phase_for_profile"] == "UPHILL_ROUTE_CONTEXT").sum())
        row["downhill_windows_n"] = int((group["route_phase_for_profile"] == "DOWNHILL_ROUTE_CONTEXT").sum())
        row["low_slope_or_mixed_windows_n"] = int((group["route_phase_for_profile"] == "LOW_SLOPE_OR_MIXED_ROUTE_CONTEXT").sum())
        row["slope_missing_windows_n"] = int((group["route_phase_for_profile"] == "SLOPE_MISSING_REVIEW_REQUIRED").sum())
        row["slope_available_ratio"] = round(
            float(row["uphill_windows_n"] + row["downhill_windows_n"] + row["low_slope_or_mixed_windows_n"]) / float(len(group)),
            6,
        ) if len(group) else np.nan
        rows.append(row)
    out = pd.DataFrame(rows).sort_values("activity_id_short").reset_index(drop=True)

    if not route_load_activity_summary.empty and "activity_id_short" in route_load_activity_summary.columns:
        keep = [
            c for c in [
                "activity_id_short",
                "candidate_windows_n",
                "max_route_load_context_index_0_100",
                "median_route_load_context_index_0_100",
                "high_or_very_high_load_ratio",
                "candidate_window_ratio",
            ]
            if c in route_load_activity_summary.columns
        ]
        out = out.merge(route_load_activity_summary[keep], on="activity_id_short", how="left")

    out["hr_recovery_evidence_present"] = False
    if not hr_activity_summary.empty and "activity_id_short" in hr_activity_summary.columns:
        hs = hr_activity_summary.copy()
        count_cols = [c for c in hs.columns if "recovery" in c.lower() and ("count" in c.lower() or c.lower().endswith("_n"))]
        if count_cols:
            hs["hr_recovery_evidence_present_source"] = hs[count_cols].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1) > 0
        else:
            hs["hr_recovery_evidence_present_source"] = any_flag_contains(hs, ["recovery"])
        out = out.merge(
            hs[["activity_id_short", "hr_recovery_evidence_present_source"]].drop_duplicates("activity_id_short"),
            on="activity_id_short",
            how="left",
        )
        out["hr_recovery_evidence_present"] = out["hr_recovery_evidence_present_source"].fillna(False).astype(bool)
        out = out.drop(columns=["hr_recovery_evidence_present_source"])

    out["completion_time_context_available"] = False
    if not completion_conclusion.empty:
        if "activity_id_short" in completion_conclusion.columns:
            cc = completion_conclusion[["activity_id_short"]].drop_duplicates().copy()
            cc["completion_time_context_available_source"] = True
            out = out.merge(cc, on="activity_id_short", how="left")
            out["completion_time_context_available"] = out["completion_time_context_available_source"].fillna(False).astype(bool)
            out = out.drop(columns=["completion_time_context_available_source"])
        else:
            out["completion_time_context_available"] = True

    out["readiness_review_available"] = False
    out["readiness_review_flags"] = "NONE"
    if not readiness_review.empty and "activity_id_short" in readiness_review.columns:
        rr = readiness_review.copy()
        rr["readiness_review_available_source"] = True
        flag_cols = [c for c in rr.columns if "flag" in c.lower() or "gate" in c.lower() or "reason" in c.lower()]
        if flag_cols:
            rr["readiness_review_flags_source"] = rr[flag_cols].apply(
                lambda row: pipe_flags([str(x) for x in row.tolist()]),
                axis=1,
            )
        else:
            rr["readiness_review_flags_source"] = "READINESS_REVIEW_AVAILABLE"
        out = out.merge(
            rr[["activity_id_short", "readiness_review_available_source", "readiness_review_flags_source"]].drop_duplicates("activity_id_short"),
            on="activity_id_short",
            how="left",
        )
        out["readiness_review_available"] = out["readiness_review_available_source"].fillna(False).astype(bool)
        out["readiness_review_flags"] = out["readiness_review_flags_source"].fillna("NONE")
        out = out.drop(columns=["readiness_review_available_source", "readiness_review_flags_source"])

    out["early_high_hr_evidence_present"] = out["readiness_review_flags"].astype(str).str.contains(
        "EARLY|HIGH_HR|early|high_hr", regex=True, na=False
    )
    out["interpretation_boundary"] = BOUNDARY_TEXT
    return out


def build_profile_overall(
    w: pd.DataFrame,
    activity_summary: pd.DataFrame,
    route_load_phase_profile: pd.DataFrame,
    phase_summary: pd.DataFrame,
    source_inventory: pd.DataFrame,
    profile_id: str,
    route_folder: str,
) -> pd.DataFrame:
    row = aggregate_response(w, profile_id, route_folder)
    row["route_load_context_band"] = "ALL"
    row["route_phase_for_profile"] = "ALL"
    row["route_phase_original_values"] = pipe_flags(w["route_phase_original"].astype(str).tolist())
    row["source_files_available_n"] = int(source_inventory["exists"].sum()) if not source_inventory.empty else 0
    row["source_files_expected_n"] = int(len(source_inventory)) if not source_inventory.empty else 0
    row["uphill_windows_n"] = int((w["route_phase_for_profile"] == "UPHILL_ROUTE_CONTEXT").sum())
    row["downhill_windows_n"] = int((w["route_phase_for_profile"] == "DOWNHILL_ROUTE_CONTEXT").sum())
    row["low_slope_or_mixed_windows_n"] = int((w["route_phase_for_profile"] == "LOW_SLOPE_OR_MIXED_ROUTE_CONTEXT").sum())
    row["slope_missing_windows_n"] = int((w["route_phase_for_profile"] == "SLOPE_MISSING_REVIEW_REQUIRED").sum())
    row["slope_available_ratio"] = round(
        float(row["uphill_windows_n"] + row["downhill_windows_n"] + row["low_slope_or_mixed_windows_n"]) / float(len(w)),
        6,
    ) if len(w) else np.nan
    row["early_high_hr_evidence_present"] = bool(
        activity_summary.get("early_high_hr_evidence_present", pd.Series(dtype=bool)).fillna(False).astype(bool).any()
    )
    row["hr_recovery_evidence_present"] = bool(
        activity_summary.get("hr_recovery_evidence_present", pd.Series(dtype=bool)).fillna(False).astype(bool).any()
    )
    row["completion_time_context_available"] = bool(
        activity_summary.get("completion_time_context_available", pd.Series(dtype=bool)).fillna(False).astype(bool).any()
    )
    row["readiness_review_available"] = bool(
        activity_summary.get("readiness_review_available", pd.Series(dtype=bool)).fillna(False).astype(bool).any()
    )
    row["route_load_phase_profile_rows"] = int(len(route_load_phase_profile))
    row["phase_summary_rows"] = int(len(phase_summary))
    row["route_phase_for_profile_note"] = ROUTE_PHASE_NOTE
    row["interpretation_boundary"] = BOUNDARY_TEXT
    return pd.DataFrame([row])


def build_data_quality(
    w: pd.DataFrame,
    source_inventory: pd.DataFrame,
    output_fields: dict[str, list[str]],
    profile_id: str,
    route_folder: str,
) -> pd.DataFrame:
    activity_ids = sorted(w["activity_id_short"].dropna().astype(str).unique().tolist())
    observed_bands = set(w["route_load_context_band"].dropna().astype(str).unique().tolist())
    unexpected_bands = sorted(observed_bands - set(ROUTE_LOAD_BAND_ORDER))

    observed_phases = set(w["route_phase_for_profile"].dropna().astype(str).unique().tolist())
    unexpected_phases = sorted(observed_phases - set(ROUTE_PHASE_ORDER))

    slope_missing_ratio = round(float((w["route_phase_for_profile"] == "SLOPE_MISSING_REVIEW_REQUIRED").sum()) / float(len(w)), 6) if len(w) else np.nan
    uphill_n = int((w["route_phase_for_profile"] == "UPHILL_ROUTE_CONTEXT").sum())
    downhill_n = int((w["route_phase_for_profile"] == "DOWNHILL_ROUTE_CONTEXT").sum())

    rows = [
        {
            "profile_id": profile_id,
            "route_folder": route_folder,
            "check_name": "activity_coverage_count",
            "check_status": "PASS" if len(activity_ids) > 0 else "REVIEW_REQUIRED",
            "check_value": len(activity_ids),
            "details": "|".join(activity_ids),
        },
        {
            "profile_id": profile_id,
            "route_folder": route_folder,
            "check_name": "route_load_context_band_domain",
            "check_status": "PASS" if not unexpected_bands else "REVIEW_REQUIRED",
            "check_value": len(unexpected_bands),
            "details": pipe_flags(unexpected_bands),
        },
        {
            "profile_id": profile_id,
            "route_folder": route_folder,
            "check_name": "route_phase_for_profile_domain",
            "check_status": "PASS" if not unexpected_phases else "REVIEW_REQUIRED",
            "check_value": len(unexpected_phases),
            "details": pipe_flags(unexpected_phases),
        },
        {
            "profile_id": profile_id,
            "route_folder": route_folder,
            "check_name": "uphill_downhill_windows_present",
            "check_status": "PASS" if uphill_n > 0 and downhill_n > 0 else "REVIEW_REQUIRED",
            "check_value": uphill_n + downhill_n,
            "details": f"uphill={uphill_n};downhill={downhill_n}",
        },
        {
            "profile_id": profile_id,
            "route_folder": route_folder,
            "check_name": "slope_missing_ratio_review",
            "check_status": "PASS_WITH_SLOPE_MISSING_REVIEW" if slope_missing_ratio <= 0.60 else "REVIEW_REQUIRED_HIGH_SLOPE_MISSING_RATIO",
            "check_value": slope_missing_ratio,
            "details": "SLOPE_MISSING is retained as separate review phase and is not imputed.",
        },
        {
            "profile_id": profile_id,
            "route_folder": route_folder,
            "check_name": "weather_zero_fill_absent",
            "check_status": "PASS",
            "check_value": 1,
            "details": "script does not fill missing weather with zero/no-rain/safe values",
        },
        {
            "profile_id": profile_id,
            "route_folder": route_folder,
            "check_name": "source_files_available",
            "check_status": "PASS" if source_inventory["exists"].all() else "REVIEW_REQUIRED_OPTIONAL_SOURCE_MISSING",
            "check_value": int(source_inventory["exists"].sum()),
            "details": f"{int(source_inventory['exists'].sum())}/{len(source_inventory)}",
        },
    ]

    generated_cols = []
    for cols in output_fields.values():
        generated_cols.extend(cols)
    generated_lower = [str(c).lower() for c in generated_cols]
    forbidden_present = sorted(
        token for token in FORBIDDEN_OUTPUT_TOKENS
        if any(token in col for col in generated_lower)
    )
    rows.append({
        "profile_id": profile_id,
        "route_folder": route_folder,
        "check_name": "forbidden_columns_absent",
        "check_status": "PASS" if not forbidden_present else "FAIL_FORBIDDEN_COLUMNS_PRESENT",
        "check_value": 0 if not forbidden_present else len(forbidden_present),
        "details": pipe_flags(forbidden_present),
    })

    rows.append({
        "profile_id": profile_id,
        "route_folder": route_folder,
        "check_name": "interpretation_boundary_present",
        "check_status": "PASS",
        "check_value": 1,
        "details": "interpretation_boundary field generated in profile outputs",
    })

    return pd.DataFrame(rows)


def audit_conclusion(data_quality: pd.DataFrame) -> str:
    statuses = data_quality["check_status"].astype(str).tolist()
    if any(s.startswith("FAIL") for s in statuses):
        return "REVIEW_REQUIRED_CH6_5_1_PERSONAL_ACTIVITY_BEHAVIOR_PROFILE_V1_1"
    if any(s.startswith("REVIEW_REQUIRED") for s in statuses):
        return "REVIEW_REQUIRED_CH6_5_1_PERSONAL_ACTIVITY_BEHAVIOR_PROFILE_V1_1"
    return "PASS_CH6_5_1_PERSONAL_ACTIVITY_BEHAVIOR_PROFILE_V1_1_DESCRIPTIVE_ONLY"


def write_run_report(
    path: Path,
    source_inventory: pd.DataFrame,
    profile_overall: pd.DataFrame,
    route_load_phase_profile: pd.DataFrame,
    phase_summary: pd.DataFrame,
    activity_summary: pd.DataFrame,
    band_summary: pd.DataFrame,
    data_quality: pd.DataFrame,
    conclusion: str,
) -> None:
    profile_id = profile_overall.iloc[0]["profile_id"] if not profile_overall.empty else ""
    route_folder = profile_overall.iloc[0]["route_folder"] if not profile_overall.empty else ""
    activity_count = profile_overall.iloc[0]["activity_count"] if not profile_overall.empty else 0
    lines = [
        "# CH6.5.1 Personal Activity Behavior Profile v1.1",
        "",
        f"- profile_id: `{profile_id}`",
        f"- route_folder: `{route_folder}`",
        f"- activity_count: `{activity_count}`",
        f"- route_load_phase_profile_rows: `{len(route_load_phase_profile)}`",
        f"- phase_summary_rows: `{len(phase_summary)}`",
        f"- activity_summary_rows: `{len(activity_summary)}`",
        f"- band_summary_rows: `{len(band_summary)}`",
        f"- audit_conclusion: `{conclusion}`",
        "",
        "## Route Phase Recovery",
        "",
        "- `route_phase_original` is retained from input and may be UNKNOWN.",
        "- `route_phase_for_profile` is recovered from `calibrated_slope_pct_median`.",
        "- Uphill threshold: `>= +3%`.",
        "- Downhill threshold: `<= -3%`.",
        "- Missing signed slope remains `SLOPE_MISSING_REVIEW_REQUIRED` and is not imputed.",
        "- The recovered phase is descriptive route context only and must not be interpreted as strict uphill/downhill ability or causality.",
        "",
        "## Sources",
        "",
    ]
    for _, row in source_inventory.iterrows():
        lines.append(f"- {row['source_label']}: `{row['source_path']}` exists={row['exists']} bytes={row['length_bytes']}")
    lines.extend([
        "",
        "## Method",
        "",
        "- Uses existing 50 m route-window activity behavior evidence.",
        "- Aggregates historical speed, low-speed, stopped, and HR response by route-load context band and recovered route-context phase.",
        "- HR recovery evidence is used only as descriptive recovery evidence, not as medical diagnosis.",
        "- Weather context is descriptive only; missing weather is not zero-filled.",
        "",
        "## Boundaries",
        "",
        "- no ability score",
        "- no ability rank",
        "- no ability class",
        "- no THCI score",
        "- no radar score",
        "- no final hiking risk score",
        "- no route suitability score",
        "- no go/no-go decision",
        "- no medical diagnosis",
        "- no causality inference",
        "",
        "## Data Quality Checks",
        "",
    ])
    for _, row in data_quality.iterrows():
        lines.append(f"- {row['check_name']}: {row['check_status']} ({row['details']})")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    out_root = resolve(root, args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)

    behavior_windows_path = resolve(root, args.behavior_windows)
    route_load_root = resolve(root, args.route_load_root)
    hr_recovery_root = resolve(root, args.hr_recovery_root)
    completion_root = resolve(root, args.completion_root)
    readiness_root = resolve(root, args.readiness_root)

    route_load_activity_summary_path = route_load_root / "route_load_context_activity_summary_v1.csv"
    candidate_windows_path = route_load_root / "route_load_behavior_response_candidate_windows_v1.csv"

    hr_activity_summary_path = find_file(hr_recovery_root, [
        "activity_hr_recovery_activity_summary_from_ib3c_v1_1.csv",
        "activity_hr_recovery_activity_summary_from_ib3c_v1.csv",
    ])
    completion_conclusion_path = find_file(completion_root, [
        "completion_feasibility_conclusion_v1_1.csv",
        "completion_feasibility_conclusion_v1.csv",
    ])
    completion_hr_effort_path = find_file(completion_root, [
        "completion_hr_effort_context_v1_1.csv",
        "completion_hr_effort_context_v1.csv",
    ])
    readiness_review_path = find_file(readiness_root, [
        "personal_route_load_readiness_review_v1_1.csv",
        "personal_route_load_readiness_review_v1.csv",
    ])

    paths = {
        "behavior_windows": behavior_windows_path,
        "route_load_context_activity_summary": route_load_activity_summary_path,
        "route_load_behavior_candidate_windows": candidate_windows_path,
        "hr_recovery_activity_summary": hr_activity_summary_path,
        "completion_feasibility_conclusion": completion_conclusion_path,
        "completion_hr_effort_context": completion_hr_effort_path,
        "personal_route_load_readiness_review": readiness_review_path,
    }
    source_inventory = build_source_inventory(paths)

    behavior_windows = read_csv(behavior_windows_path, "behavior windows", required=True)
    route_load_activity_summary = read_csv(route_load_activity_summary_path, "route-load activity summary", required=True)
    candidate_windows = read_csv(candidate_windows_path, "candidate windows", required=True)
    hr_activity_summary = read_csv(hr_activity_summary_path, "HR recovery activity summary", required=False)
    completion_conclusion = read_csv(completion_conclusion_path, "completion conclusion", required=False)
    readiness_review = read_csv(readiness_review_path, "readiness review", required=False)

    w = build_windows(
        behavior_windows,
        candidate_windows,
        args.profile_id,
        args.route_folder,
        args.uphill_threshold_pct,
        args.downhill_threshold_pct,
    )

    route_load_phase_profile = build_route_load_phase_profile(w, args.profile_id, args.route_folder)
    phase_summary = build_phase_summary(w, args.profile_id, args.route_folder)
    band_summary = build_band_summary(w, args.profile_id, args.route_folder)
    activity_summary = build_activity_summary(
        w,
        route_load_activity_summary,
        hr_activity_summary,
        completion_conclusion,
        readiness_review,
        args.profile_id,
        args.route_folder,
    )
    profile_overall = build_profile_overall(
        w,
        activity_summary,
        route_load_phase_profile,
        phase_summary,
        source_inventory,
        args.profile_id,
        args.route_folder,
    )

    output_paths = {
        "personal_activity_behavior_profile": out_root / "personal_activity_behavior_profile_v1_1.csv",
        "personal_route_load_phase_response_profile": out_root / "personal_route_load_phase_response_profile_v1_1.csv",
        "personal_behavior_profile_phase_summary": out_root / "personal_behavior_profile_phase_summary_v1_1.csv",
        "personal_behavior_profile_activity_summary": out_root / "personal_behavior_profile_activity_summary_v1_1.csv",
        "personal_behavior_profile_route_load_band_summary": out_root / "personal_behavior_profile_route_load_band_summary_v1_1.csv",
        "personal_behavior_profile_window_features": out_root / "personal_behavior_profile_window_features_v1_1.csv",
        "personal_behavior_profile_data_quality": out_root / "personal_behavior_profile_data_quality_v1_1.csv",
        "personal_activity_behavior_profile_audit": out_root / "personal_activity_behavior_profile_audit_v1_1.csv",
        "personal_activity_behavior_profile_run_report": out_root / "personal_activity_behavior_profile_run_report_v1_1.md",
    }

    output_fields = {
        "personal_activity_behavior_profile": list(profile_overall.columns),
        "personal_route_load_phase_response_profile": list(route_load_phase_profile.columns),
        "personal_behavior_profile_phase_summary": list(phase_summary.columns),
        "personal_behavior_profile_activity_summary": list(activity_summary.columns),
        "personal_behavior_profile_route_load_band_summary": list(band_summary.columns),
        "personal_behavior_profile_window_features": list(w.columns),
    }

    data_quality = build_data_quality(w, source_inventory, output_fields, args.profile_id, args.route_folder)
    conclusion = audit_conclusion(data_quality)

    audit = pd.DataFrame([{
        "profile_id": args.profile_id,
        "route_folder": args.route_folder,
        "activity_count": int(w["activity_id_short"].nunique()),
        "window_row_count": int(len(w)),
        "uphill_windows_n": int((w["route_phase_for_profile"] == "UPHILL_ROUTE_CONTEXT").sum()),
        "downhill_windows_n": int((w["route_phase_for_profile"] == "DOWNHILL_ROUTE_CONTEXT").sum()),
        "low_slope_or_mixed_windows_n": int((w["route_phase_for_profile"] == "LOW_SLOPE_OR_MIXED_ROUTE_CONTEXT").sum()),
        "slope_missing_windows_n": int((w["route_phase_for_profile"] == "SLOPE_MISSING_REVIEW_REQUIRED").sum()),
        "route_load_phase_profile_rows": int(len(route_load_phase_profile)),
        "phase_summary_rows": int(len(phase_summary)),
        "activity_summary_rows": int(len(activity_summary)),
        "band_summary_rows": int(len(band_summary)),
        "source_files_available_n": int(source_inventory["exists"].sum()),
        "source_files_expected_n": int(len(source_inventory)),
        "audit_conclusion": conclusion,
        "interpretation_boundary": BOUNDARY_TEXT,
    }])

    # Keep full window features because v1.1's key value is route-phase recovery at window level.
    profile_overall.to_csv(output_paths["personal_activity_behavior_profile"], index=False, encoding="utf-8-sig")
    route_load_phase_profile.to_csv(output_paths["personal_route_load_phase_response_profile"], index=False, encoding="utf-8-sig")
    phase_summary.to_csv(output_paths["personal_behavior_profile_phase_summary"], index=False, encoding="utf-8-sig")
    activity_summary.to_csv(output_paths["personal_behavior_profile_activity_summary"], index=False, encoding="utf-8-sig")
    band_summary.to_csv(output_paths["personal_behavior_profile_route_load_band_summary"], index=False, encoding="utf-8-sig")
    w.to_csv(output_paths["personal_behavior_profile_window_features"], index=False, encoding="utf-8-sig")
    data_quality.to_csv(output_paths["personal_behavior_profile_data_quality"], index=False, encoding="utf-8-sig")
    audit.to_csv(output_paths["personal_activity_behavior_profile_audit"], index=False, encoding="utf-8-sig")

    write_run_report(
        output_paths["personal_activity_behavior_profile_run_report"],
        source_inventory,
        profile_overall,
        route_load_phase_profile,
        phase_summary,
        activity_summary,
        band_summary,
        data_quality,
        conclusion,
    )

    print({
        "output_root": str(out_root),
        "profile_id": args.profile_id,
        "activity_count": int(w["activity_id_short"].nunique()),
        "window_row_count": int(len(w)),
        "uphill_windows_n": int((w["route_phase_for_profile"] == "UPHILL_ROUTE_CONTEXT").sum()),
        "downhill_windows_n": int((w["route_phase_for_profile"] == "DOWNHILL_ROUTE_CONTEXT").sum()),
        "low_slope_or_mixed_windows_n": int((w["route_phase_for_profile"] == "LOW_SLOPE_OR_MIXED_ROUTE_CONTEXT").sum()),
        "slope_missing_windows_n": int((w["route_phase_for_profile"] == "SLOPE_MISSING_REVIEW_REQUIRED").sum()),
        "route_load_phase_profile_rows": int(len(route_load_phase_profile)),
        "phase_summary_rows": int(len(phase_summary)),
        "activity_summary_rows": int(len(activity_summary)),
        "band_summary_rows": int(len(band_summary)),
        "source_files_available_n": int(source_inventory["exists"].sum()),
        "source_files_expected_n": int(len(source_inventory)),
        "audit_conclusion": conclusion,
        "outputs": {k: str(v) for k, v in output_paths.items()},
    })

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

