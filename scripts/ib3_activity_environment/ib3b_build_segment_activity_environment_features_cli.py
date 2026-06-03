from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

np = None
pd = None


ROUTE_CASE_MAP = {
    "juansi_waterfall": "juansi_waterfall_fitcsv_20260503",
    "qixing_lengshuikeng": "qixing_lengshuikeng_main_peak_20260523",
}

OFFSET_BINS = {
    "on_route": (None, 30.0),
    "near_route": (30.0, 80.0),
    "far_route": (80.0, 150.0),
    "off_route": (150.0, None),
}

RISK_BAND_SEVERITY = {
    "low": 1,
    "moderate": 2,
    "high": 3,
    "very_high": 4,
}

ENV_MEAN_MAX_COLS = [
    "risk_score",
    "risk_score_smooth",
    "osm_terrain_combined_risk_score",
    "osm_semantic_risk_score",
    "terrain_window_risk_score",
    "hydro_terrain_amplifier_score",
    "technical_risk_score",
    "exposure_risk_score",
    "hydrology_risk_score",
    "surface_slip_risk_score",
    "route_effort_risk_score",
    "route_type_risk_score",
    "elev_range",
]

ENV_MEAN_ONLY_COLS = [
    "support_score",
    "navigation_support_score",
    "night_navigation_support_score",
    "rest_support_score",
]

ENV_MODE_COLS = [
    "slope_band_window",
    "risk_band",
    "contour_window_match_status",
]

ENV_OUTPUT_COLUMNS = [
    "risk_score_mean",
    "risk_score_max",
    "risk_score_smooth_mean",
    "risk_score_smooth_max",
    "osm_terrain_combined_risk_score_mean",
    "osm_terrain_combined_risk_score_max",
    "osm_semantic_risk_score_mean",
    "osm_semantic_risk_score_max",
    "terrain_window_risk_score_mean",
    "terrain_window_risk_score_max",
    "hydro_terrain_amplifier_score_mean",
    "hydro_terrain_amplifier_score_max",
    "technical_risk_score_mean",
    "technical_risk_score_max",
    "exposure_risk_score_mean",
    "exposure_risk_score_max",
    "hydrology_risk_score_mean",
    "hydrology_risk_score_max",
    "surface_slip_risk_score_mean",
    "surface_slip_risk_score_max",
    "route_effort_risk_score_mean",
    "route_effort_risk_score_max",
    "route_type_risk_score_mean",
    "route_type_risk_score_max",
    "support_score_mean",
    "navigation_support_score_mean",
    "night_navigation_support_score_mean",
    "rest_support_score_mean",
    "slope_band_window_mode",
    "risk_band_mode",
    "risk_band_max_severity",
    "elev_range_mean",
    "elev_range_max",
    "contour_window_match_status_mode",
]

FEATURE_COLUMNS = [
    "route_folder",
    "case_id",
    "subject_id",
    "trial_id",
    "activity_id",
    "segment_id",
    "dist_start_m",
    "dist_end_m",
    "direction_hint",
    "segment_elapsed_sec",
    "segment_point_n",
    "segment_speed_mps",
    "elapsed_sec_min",
    "elapsed_sec_max",
    "distance_m_min",
    "distance_m_max",
    "distance_delta_m",
    "ele_m_mean",
    "ele_m_min",
    "ele_m_max",
    "ele_delta_m",
    "heart_rate_mean",
    "heart_rate_median",
    "heart_rate_min",
    "heart_rate_max",
    "heart_rate_valid_ratio",
    "dt_sec_median",
    "dt_sec_mean",
    "dt_sec_max",
    "duplicate_timestamp_ratio",
    "irregular_interval_ratio",
    "sampling_profile",
    "time_quality",
    "offset_m_mean",
    "offset_m_median",
    "offset_m_p90",
    "offset_m_p95",
    "offset_m_max",
    "on_route_ratio",
    "near_route_ratio",
    "far_route_ratio",
    "off_route_ratio",
    "segment_match_quality",
] + ENV_OUTPUT_COLUMNS

SUMMARY_COLUMNS = [
    "route_folder",
    "case_id",
    "subject_id",
    "trial_id",
    "activity_id",
    "segments_n",
    "valid_segments_n",
    "clean_segments_n",
    "strict_clean_segments_n",
    "invalid_segments_n",
    "duration_sec",
    "segment_elapsed_sec_sum",
    "route_dist_min",
    "route_dist_max",
    "offset_m_p95_overall",
    "off_route_ratio_overall",
    "heart_rate_valid_ratio_overall",
    "sampling_profile",
    "time_quality",
    "activity_input_source",
    "rows_total_before_filter",
    "rows_used_after_filter",
    "rows_excluded_by_ib3a2",
    "manual_override_event_count",
    "excluded_label_counts",
    "status",
    "error",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build ib3b segment-level activity + environment feature tables "
            "from ib3a mapmatched standardized activities and v1_1 route features."
        )
    )
    parser.add_argument(
        "--mapmatched-root",
        default="outputs/ib3a_mapmatched_standardized_activity",
        help="Root folder containing ib3a mapmatched standardized activity CSVs.",
    )
    parser.add_argument(
        "--ib3a2-root",
        default="outputs/ib3a2_on_route_activity_filter",
        help="Root folder containing ib3a2 on-route filtered activity CSVs.",
    )
    parser.add_argument(
        "--risk-root",
        default="outputs/ib2_v2_route_risk_v1_1",
        help="Root folder containing v1_1 route risk outputs.",
    )
    parser.add_argument(
        "--ib1e-root",
        default="outputs/ib1e_route_profile_contour_window_terrain_v1_1",
        help="Root folder containing v1_1 ib1e OSM + NLSC terrain outputs.",
    )
    parser.add_argument(
        "--out-dir",
        default="outputs/ib3b_activity_environment_segments",
        help="Output directory for segment feature tables and summary.",
    )
    parser.add_argument(
        "--segment-len-m",
        type=float,
        default=20.0,
        help="Segment length in meters.",
    )
    parser.add_argument(
        "--clean-offset-p95-m",
        type=float,
        default=100.0,
        help="Clean segment offset p95 threshold in meters.",
    )
    parser.add_argument(
        "--strict-clean-offset-p95-m",
        type=float,
        default=60.0,
        help="Strict clean segment offset p95 threshold in meters.",
    )
    parser.add_argument(
        "--max-off-route-ratio",
        type=float,
        default=0.2,
        help="Maximum off-route point ratio allowed in clean outputs.",
    )
    return parser.parse_args()


def safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def first_non_null(series: pd.Series) -> Any:
    values = series.dropna()
    return values.iloc[0] if not values.empty else pd.NA


def mode_value(series: pd.Series) -> Any:
    values = series.dropna().astype(str)
    values = values[values.str.strip() != ""]
    if values.empty:
        return pd.NA
    counts = values.value_counts()
    return counts.index[0]


def max_risk_band(series: pd.Series) -> Any:
    values = series.dropna().astype(str).str.strip().str.lower()
    if values.empty:
        return pd.NA
    known = values[values.isin(RISK_BAND_SEVERITY)]
    if known.empty:
        return pd.NA
    return max(known, key=lambda value: RISK_BAND_SEVERITY[value])


def classify_sampling_profile(dt_sec: pd.Series, duplicate_ratio: float, irregular_ratio: float) -> tuple[str, str]:
    valid_dt = safe_numeric(dt_sec).dropna()
    if valid_dt.empty:
        return "invalid_time", "invalid_time"

    median_dt = float(valid_dt.median())
    dup = 0.0 if pd.isna(duplicate_ratio) else float(duplicate_ratio)
    irr = 0.0 if pd.isna(irregular_ratio) else float(irregular_ratio)

    if median_dt < 0.5 or dup > 0.10:
        return "high_frequency", "irregular" if dup > 0 or irr > 0.05 else "ok"
    if median_dt > 1.5:
        return "low_frequency", "irregular" if irr > 0.05 else "ok"
    if dup > 0 or irr > 0.05:
        return "irregular", "irregular"
    return "regular_1hz", "ok"


def classify_segment_match_quality(offset_p95: float) -> str:
    if pd.isna(offset_p95):
        return "unknown"
    if offset_p95 <= 50.0:
        return "good"
    if offset_p95 <= 100.0:
        return "fair"
    if offset_p95 <= 150.0:
        return "poor"
    return "very_poor"


def offset_ratio(offset: pd.Series, label: str) -> float:
    values = safe_numeric(offset).dropna()
    if values.empty:
        return np.nan
    lower, upper = OFFSET_BINS[label]
    mask = pd.Series(True, index=values.index)
    if lower is not None:
        mask &= values > lower
    if upper is not None:
        mask &= values <= upper
    return float(mask.mean())


def resolve_subject_trial_from_path(path: Path) -> tuple[str, Any]:
    stem = path.stem.replace("_mapmatched", "")
    parts = stem.split("_")
    if len(parts) >= 2:
        return parts[0], parts[1]
    return stem, pd.NA


def find_mapmatched_files(mapmatched_root: Path) -> list[Path]:
    files = [
        path
        for path in mapmatched_root.glob("*/*_mapmatched.csv")
        if path.is_file() and path.parent.name in ROUTE_CASE_MAP
    ]
    return sorted(files, key=lambda p: (p.parent.name, p.name))


def ib3a2_paths(ib3a2_root: Path, route_folder: str, subject_id: Any, trial_id: Any) -> dict[str, Path]:
    subject = str(subject_id)
    trial = str(trial_id)
    stem = f"{route_folder}_{subject}_{trial}_mapmatched_activity"
    route_dir = ib3a2_root / route_folder
    return {
        "on_route": route_dir / f"{stem}_on_route.csv",
        "labeled": route_dir / f"{stem}_labeled.csv",
        "excursions": route_dir / f"{stem}_excursions.csv",
    }


def activity_input_metadata(
    activity_csv: Path,
    raw_activity_csv: Path,
    source: str,
    ib3a2_files: dict[str, Path] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "activity_input_source": source,
        "rows_total_before_filter": pd.NA,
        "rows_used_after_filter": pd.NA,
        "rows_excluded_by_ib3a2": pd.NA,
        "manual_override_event_count": 0,
        "excluded_label_counts": "{}",
    }

    if source == "ib3a_raw_mapmatched":
        raw = pd.read_csv(raw_activity_csv, low_memory=False)
        metadata["rows_total_before_filter"] = int(len(raw))
        metadata["rows_used_after_filter"] = int(len(raw))
        metadata["rows_excluded_by_ib3a2"] = 0
        return metadata

    used = pd.read_csv(activity_csv, low_memory=False)
    metadata["rows_used_after_filter"] = int(len(used))

    if ib3a2_files and ib3a2_files["labeled"].exists():
        labeled = pd.read_csv(ib3a2_files["labeled"], low_memory=False)
        metadata["rows_total_before_filter"] = int(len(labeled))
        metadata["rows_excluded_by_ib3a2"] = int(len(labeled) - len(used))
        if "usable_on_route" in labeled.columns:
            usable = labeled["usable_on_route"].astype(str).str.lower().isin(["true", "1", "yes"])
            excluded = labeled.loc[~usable].copy()
        else:
            excluded = labeled.iloc[0:0].copy()
        if "excluded_reason" in excluded.columns and not excluded.empty:
            counts = excluded["excluded_reason"].fillna("").astype(str).replace("", "unknown").value_counts().to_dict()
            metadata["excluded_label_counts"] = json.dumps(counts, ensure_ascii=False, sort_keys=True)
        else:
            metadata["excluded_label_counts"] = "{}"
    else:
        metadata["rows_total_before_filter"] = int(len(used))
        metadata["rows_excluded_by_ib3a2"] = 0

    if ib3a2_files and ib3a2_files["excursions"].exists():
        excursions = pd.read_csv(ib3a2_files["excursions"], low_memory=False)
        if "event_source" in excursions.columns:
            metadata["manual_override_event_count"] = int(
                excursions["event_source"].astype(str).eq("manual_override").sum()
            )
    return metadata


def select_activity_input(
    raw_activity_csv: Path,
    ib3a2_root: Path,
    route_folder: str,
    subject_id: Any,
    trial_id: Any,
) -> tuple[Path, str, dict[str, Path] | None]:
    paths = ib3a2_paths(ib3a2_root, route_folder, subject_id, trial_id)
    if paths["on_route"].exists():
        return paths["on_route"], "ib3a2_on_route", paths
    return raw_activity_csv, "ib3a_raw_mapmatched", None


def env_input_paths(risk_root: Path, ib1e_root: Path, case_id: str) -> tuple[Path, Path]:
    risk_csv = risk_root / case_id / f"{case_id}_route_risk_v2.csv"
    ib1e_csv = ib1e_root / case_id / f"{case_id}_route_profile_contour_window_terrain_enriched.csv"
    return risk_csv, ib1e_csv


def pick_existing_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def normalize_env_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    aliases = {
        "elev_range": ["elev_range", "elev_range_nlsc_window"],
        "slope_band_window": ["slope_band_window", "slope_band_window_nlsc", "slope_final_band"],
    }
    for target, candidates in aliases.items():
        if target in out.columns:
            continue
        source = pick_existing_column(out, candidates)
        out[target] = out[source] if source else pd.NA
    return out


def add_env_segment_id(df: pd.DataFrame, segment_len_m: float) -> pd.DataFrame:
    out = normalize_env_columns(df)
    dist_col = pick_existing_column(out, ["dist_m", "profile_dist_m", "terrain_dist_mid_m"])
    if dist_col is None:
        raise ValueError("environment CSV missing dist_m/profile_dist_m/terrain_dist_mid_m")
    out["_env_dist_m"] = safe_numeric(out[dist_col])
    out = out.dropna(subset=["_env_dist_m"]).copy()
    out["segment_id"] = np.floor(out["_env_dist_m"] / segment_len_m).astype("Int64")
    return out.dropna(subset=["segment_id"]).copy()


def aggregate_env_source(df: pd.DataFrame, segment_len_m: float) -> tuple[pd.DataFrame, list[str]]:
    out = add_env_segment_id(df, segment_len_m)
    missing: list[str] = []
    rows: list[dict[str, Any]] = []

    needed = ENV_MEAN_MAX_COLS + ENV_MEAN_ONLY_COLS + ENV_MODE_COLS + ["risk_band"]
    for col in needed:
        if col not in out.columns:
            out[col] = pd.NA
            if col not in missing:
                missing.append(col)

    for seg_id, group in out.groupby("segment_id", dropna=True):
        row: dict[str, Any] = {"segment_id": int(seg_id)}
        for col in ENV_MEAN_MAX_COLS:
            values = safe_numeric(group[col])
            row[f"{col}_mean"] = float(values.mean()) if values.notna().any() else np.nan
            row[f"{col}_max"] = float(values.max()) if values.notna().any() else np.nan
        for col in ENV_MEAN_ONLY_COLS:
            values = safe_numeric(group[col])
            row[f"{col}_mean"] = float(values.mean()) if values.notna().any() else np.nan
        for col in ENV_MODE_COLS:
            row[f"{col}_mode"] = mode_value(group[col])
        row["risk_band_max_severity"] = max_risk_band(group["risk_band"])
        rows.append(row)

    env = pd.DataFrame(rows)
    for col in ["segment_id"] + ENV_OUTPUT_COLUMNS:
        if col not in env.columns:
            env[col] = pd.NA
    return env[["segment_id"] + ENV_OUTPUT_COLUMNS], missing


def combine_env_features(
    risk_csv: Path,
    ib1e_csv: Path,
    segment_len_m: float,
) -> tuple[pd.DataFrame, list[str]]:
    risk_df = pd.read_csv(risk_csv, low_memory=False)
    ib1e_df = pd.read_csv(ib1e_csv, low_memory=False)
    risk_env, risk_missing = aggregate_env_source(risk_df, segment_len_m)
    ib1e_env, ib1e_missing = aggregate_env_source(ib1e_df, segment_len_m)

    combined = risk_env.set_index("segment_id").combine_first(ib1e_env.set_index("segment_id")).reset_index()
    for col in ["segment_id"] + ENV_OUTPUT_COLUMNS:
        if col not in combined.columns:
            combined[col] = pd.NA

    still_missing = [
        col
        for col in ENV_OUTPUT_COLUMNS
        if col in combined.columns and combined[col].isna().all()
    ]
    raw_missing = sorted(set(risk_missing + ib1e_missing))
    missing = sorted(set(raw_missing + still_missing))
    return combined[["segment_id"] + ENV_OUTPUT_COLUMNS], missing


def activity_segment_row(group: pd.DataFrame, segment_len_m: float) -> dict[str, Any]:
    segment_id = int(group["segment_id"].iloc[0])
    elapsed = safe_numeric(group["elapsed_sec"])
    distance = safe_numeric(group["distance_m"]) if "distance_m" in group else pd.Series(dtype=float)
    ele = safe_numeric(group["ele_m"]) if "ele_m" in group else pd.Series(dtype=float)
    hr = safe_numeric(group["heart_rate_bpm"]) if "heart_rate_bpm" in group else pd.Series(dtype=float)
    dt = safe_numeric(group["dt_sec"]) if "dt_sec" in group else pd.Series(dtype=float)
    offset = safe_numeric(group["offset_m"]) if "offset_m" in group else pd.Series(dtype=float)
    timestamp = safe_numeric(group["timestamp_s"]) if "timestamp_s" in group else pd.Series(dtype=float)

    elapsed_min = float(elapsed.min()) if elapsed.notna().any() else np.nan
    elapsed_max = float(elapsed.max()) if elapsed.notna().any() else np.nan
    segment_elapsed = elapsed_max - elapsed_min if pd.notna(elapsed_min) and pd.notna(elapsed_max) else np.nan

    distance_min = float(distance.min()) if distance.notna().any() else np.nan
    distance_max = float(distance.max()) if distance.notna().any() else np.nan
    distance_delta = distance_max - distance_min if pd.notna(distance_min) and pd.notna(distance_max) else np.nan

    ele_min = float(ele.min()) if ele.notna().any() else np.nan
    ele_max = float(ele.max()) if ele.notna().any() else np.nan
    ele_delta = ele_max - ele_min if pd.notna(ele_min) and pd.notna(ele_max) else np.nan

    duplicate_ratio = float(timestamp.duplicated(keep=False).mean()) if timestamp.notna().any() else np.nan
    valid_dt = dt.dropna()
    irregular_ratio = float(((valid_dt < 0.5) | (valid_dt > 1.5)).mean()) if not valid_dt.empty else np.nan
    sampling_profile, time_quality = classify_sampling_profile(dt, duplicate_ratio, irregular_ratio)

    point_n = int(len(group))
    speed = distance_delta / segment_elapsed if pd.notna(distance_delta) and pd.notna(segment_elapsed) and segment_elapsed > 0 else np.nan
    offset_p95 = float(offset.quantile(0.95)) if offset.notna().any() else np.nan

    if pd.isna(segment_elapsed) or segment_elapsed <= 0:
        time_quality = "invalid_segment_time"
    elif point_n < 2:
        time_quality = "too_few_points"

    return {
        "route_folder": first_non_null(group["route_folder"]),
        "case_id": first_non_null(group["case_id"]),
        "subject_id": first_non_null(group["subject_id"]),
        "trial_id": first_non_null(group["trial_id"]),
        "activity_id": first_non_null(group["activity_id"]),
        "segment_id": segment_id,
        "dist_start_m": float(segment_id * segment_len_m),
        "dist_end_m": float((segment_id + 1) * segment_len_m),
        "direction_hint": mode_value(group["direction_hint"]) if "direction_hint" in group else pd.NA,
        "segment_elapsed_sec": segment_elapsed,
        "segment_point_n": point_n,
        "segment_speed_mps": speed,
        "elapsed_sec_min": elapsed_min,
        "elapsed_sec_max": elapsed_max,
        "distance_m_min": distance_min,
        "distance_m_max": distance_max,
        "distance_delta_m": distance_delta,
        "ele_m_mean": float(ele.mean()) if ele.notna().any() else np.nan,
        "ele_m_min": ele_min,
        "ele_m_max": ele_max,
        "ele_delta_m": ele_delta,
        "heart_rate_mean": float(hr.mean()) if hr.notna().any() else np.nan,
        "heart_rate_median": float(hr.median()) if hr.notna().any() else np.nan,
        "heart_rate_min": float(hr.min()) if hr.notna().any() else np.nan,
        "heart_rate_max": float(hr.max()) if hr.notna().any() else np.nan,
        "heart_rate_valid_ratio": float(hr.notna().mean()) if len(hr) else np.nan,
        "dt_sec_median": float(dt.median()) if dt.notna().any() else np.nan,
        "dt_sec_mean": float(dt.mean()) if dt.notna().any() else np.nan,
        "dt_sec_max": float(dt.max()) if dt.notna().any() else np.nan,
        "duplicate_timestamp_ratio": duplicate_ratio,
        "irregular_interval_ratio": irregular_ratio,
        "sampling_profile": sampling_profile,
        "time_quality": time_quality,
        "offset_m_mean": float(offset.mean()) if offset.notna().any() else np.nan,
        "offset_m_median": float(offset.median()) if offset.notna().any() else np.nan,
        "offset_m_p90": float(offset.quantile(0.90)) if offset.notna().any() else np.nan,
        "offset_m_p95": offset_p95,
        "offset_m_max": float(offset.max()) if offset.notna().any() else np.nan,
        "on_route_ratio": offset_ratio(offset, "on_route"),
        "near_route_ratio": offset_ratio(offset, "near_route"),
        "far_route_ratio": offset_ratio(offset, "far_route"),
        "off_route_ratio": offset_ratio(offset, "off_route"),
        "segment_match_quality": classify_segment_match_quality(offset_p95),
    }


def aggregate_activity(activity: pd.DataFrame, segment_len_m: float) -> pd.DataFrame:
    required = ["segment_id", "elapsed_sec", "route_folder", "case_id", "subject_id", "trial_id", "activity_id"]
    missing = [col for col in required if col not in activity.columns]
    if missing:
        raise ValueError(f"mapmatched activity missing required columns: {missing}")

    out = activity.copy()
    out["segment_id"] = pd.to_numeric(out["segment_id"], errors="coerce").astype("Int64")
    out = out.dropna(subset=["segment_id"]).copy()
    if out.empty:
        raise ValueError("activity has no valid segment_id rows")

    rows = [
        activity_segment_row(group.copy(), segment_len_m)
        for _, group in out.groupby("segment_id", dropna=True, sort=True)
    ]
    features = pd.DataFrame(rows)
    for col in FEATURE_COLUMNS:
        if col not in features.columns:
            features[col] = pd.NA
    return features[FEATURE_COLUMNS]


def clean_mask(features: pd.DataFrame, offset_p95_m: float, max_off_route_ratio: float) -> pd.Series:
    return (
        (pd.to_numeric(features["segment_elapsed_sec"], errors="coerce") > 0)
        & (pd.to_numeric(features["segment_point_n"], errors="coerce") >= 2)
        & (pd.to_numeric(features["offset_m_p95"], errors="coerce") <= offset_p95_m)
        & (pd.to_numeric(features["off_route_ratio"], errors="coerce") <= max_off_route_ratio)
    )


def summarize_activity(
    activity: pd.DataFrame | None,
    features: pd.DataFrame | None,
    clean_offset_p95_m: float,
    strict_clean_offset_p95_m: float,
    max_off_route_ratio: float,
    status: str,
    error: str = "",
    route_folder: str | None = None,
    case_id: str | None = None,
    subject_id: Any = None,
    trial_id: Any = None,
    activity_id: Any = None,
    input_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    input_metadata = input_metadata or {}
    input_summary = {
        "activity_input_source": input_metadata.get("activity_input_source", ""),
        "rows_total_before_filter": input_metadata.get("rows_total_before_filter", pd.NA),
        "rows_used_after_filter": input_metadata.get("rows_used_after_filter", pd.NA),
        "rows_excluded_by_ib3a2": input_metadata.get("rows_excluded_by_ib3a2", pd.NA),
        "manual_override_event_count": input_metadata.get("manual_override_event_count", 0),
        "excluded_label_counts": input_metadata.get("excluded_label_counts", "{}"),
    }

    if activity is not None and not activity.empty:
        route_folder = str(first_non_null(activity["route_folder"])) if "route_folder" in activity else route_folder
        case_id = str(first_non_null(activity["case_id"])) if "case_id" in activity else case_id
        subject_id = first_non_null(activity["subject_id"]) if "subject_id" in activity else subject_id
        trial_id = first_non_null(activity["trial_id"]) if "trial_id" in activity else trial_id
        activity_id = first_non_null(activity["activity_id"]) if "activity_id" in activity else activity_id

    if features is None or features.empty:
        row = {
            "route_folder": route_folder,
            "case_id": case_id,
            "subject_id": subject_id,
            "trial_id": trial_id,
            "activity_id": activity_id,
            "segments_n": 0,
            "valid_segments_n": 0,
            "clean_segments_n": 0,
            "strict_clean_segments_n": 0,
            "invalid_segments_n": 0,
            "duration_sec": np.nan,
            "segment_elapsed_sec_sum": np.nan,
            "route_dist_min": np.nan,
            "route_dist_max": np.nan,
            "offset_m_p95_overall": np.nan,
            "off_route_ratio_overall": np.nan,
            "heart_rate_valid_ratio_overall": np.nan,
            "sampling_profile": "",
            "time_quality": "",
            "status": status,
            "error": error,
        }
        row.update(input_summary)
        return row

    valid_mask = (
        (pd.to_numeric(features["segment_elapsed_sec"], errors="coerce") > 0)
        & (pd.to_numeric(features["segment_point_n"], errors="coerce") >= 2)
    )
    clean = clean_mask(features, clean_offset_p95_m, max_off_route_ratio)
    strict = clean_mask(features, strict_clean_offset_p95_m, max_off_route_ratio)

    elapsed = safe_numeric(activity["elapsed_sec"]) if activity is not None and "elapsed_sec" in activity else pd.Series(dtype=float)
    route_dist = safe_numeric(activity["route_dist_m"]) if activity is not None and "route_dist_m" in activity else pd.Series(dtype=float)
    offset = safe_numeric(activity["offset_m"]) if activity is not None and "offset_m" in activity else pd.Series(dtype=float)
    hr = safe_numeric(activity["heart_rate_bpm"]) if activity is not None and "heart_rate_bpm" in activity else pd.Series(dtype=float)

    duration = float(elapsed.max() - elapsed.min()) if elapsed.notna().any() else np.nan
    off_route = offset_ratio(offset, "off_route")
    row = {
        "route_folder": route_folder,
        "case_id": case_id,
        "subject_id": subject_id,
        "trial_id": trial_id,
        "activity_id": activity_id,
        "segments_n": int(len(features)),
        "valid_segments_n": int(valid_mask.sum()),
        "clean_segments_n": int(clean.sum()),
        "strict_clean_segments_n": int(strict.sum()),
        "invalid_segments_n": int((~valid_mask).sum()),
        "duration_sec": duration,
        "segment_elapsed_sec_sum": float(features["segment_elapsed_sec"].sum(skipna=True)),
        "route_dist_min": float(route_dist.min()) if route_dist.notna().any() else np.nan,
        "route_dist_max": float(route_dist.max()) if route_dist.notna().any() else np.nan,
        "offset_m_p95_overall": float(offset.quantile(0.95)) if offset.notna().any() else np.nan,
        "off_route_ratio_overall": off_route,
        "heart_rate_valid_ratio_overall": float(hr.notna().mean()) if len(hr) else np.nan,
        "sampling_profile": mode_value(features["sampling_profile"]),
        "time_quality": "invalid_segment_time" if (features["time_quality"] == "invalid_segment_time").any() else mode_value(features["time_quality"]),
        "status": status,
        "error": error,
    }
    row.update(input_summary)
    return row


def format_missing_feature_error(missing_cols: list[str]) -> str:
    if not missing_cols:
        return ""
    return "missing_feature_columns=" + "|".join(sorted(set(missing_cols)))


def run(args: argparse.Namespace) -> int:
    global np, pd
    import numpy as np  # type: ignore[no-redef]
    import pandas as pd  # type: ignore[no-redef]

    mapmatched_root = Path(args.mapmatched_root)
    ib3a2_root = Path(args.ib3a2_root)
    risk_root = Path(args.risk_root)
    ib1e_root = Path(args.ib1e_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    env_cache: dict[str, tuple[pd.DataFrame, list[str]]] = {}
    route_env_status: dict[str, tuple[str, str]] = {}
    all_features: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []

    files = find_mapmatched_files(mapmatched_root)

    for raw_activity_csv in files:
        route_folder = raw_activity_csv.parent.name
        case_id = ROUTE_CASE_MAP.get(route_folder, "")
        subject_id, trial_id = resolve_subject_trial_from_path(raw_activity_csv)
        activity: pd.DataFrame | None = None
        features: pd.DataFrame | None = None
        input_metadata: dict[str, Any] = {
            "activity_input_source": "ib3a_raw_mapmatched",
            "rows_total_before_filter": pd.NA,
            "rows_used_after_filter": pd.NA,
            "rows_excluded_by_ib3a2": pd.NA,
            "manual_override_event_count": 0,
            "excluded_label_counts": "{}",
        }

        try:
            activity_csv, input_source, ib3a2_files = select_activity_input(
                raw_activity_csv=raw_activity_csv,
                ib3a2_root=ib3a2_root,
                route_folder=route_folder,
                subject_id=subject_id,
                trial_id=trial_id,
            )
            input_metadata = activity_input_metadata(
                activity_csv=activity_csv,
                raw_activity_csv=raw_activity_csv,
                source=input_source,
                ib3a2_files=ib3a2_files,
            )

            activity = pd.read_csv(activity_csv, low_memory=False)
            if activity.empty:
                raise ValueError("empty mapmatched activity CSV")

            route_folder = str(first_non_null(activity["route_folder"])) if "route_folder" in activity else route_folder
            case_id = str(first_non_null(activity["case_id"])) if "case_id" in activity else case_id
            subject_id = first_non_null(activity["subject_id"]) if "subject_id" in activity else subject_id
            trial_id = first_non_null(activity["trial_id"]) if "trial_id" in activity else trial_id
            activity_id = first_non_null(activity["activity_id"]) if "activity_id" in activity else f"{route_folder}_{subject_id}_{trial_id}"

            if case_id not in route_env_status:
                risk_csv, ib1e_csv = env_input_paths(risk_root, ib1e_root, case_id)
                missing_inputs = [str(path) for path in [risk_csv, ib1e_csv] if not path.exists()]
                if missing_inputs:
                    route_env_status[case_id] = ("missing_input", "missing_input=" + "|".join(missing_inputs))
                else:
                    env_cache[case_id] = combine_env_features(risk_csv, ib1e_csv, args.segment_len_m)
                    missing_msg = format_missing_feature_error(env_cache[case_id][1])
                    route_env_status[case_id] = ("ok", missing_msg)

            env_status, env_error = route_env_status[case_id]
            if env_status != "ok":
                summary_rows.append(
                    summarize_activity(
                        activity,
                        None,
                        args.clean_offset_p95_m,
                        args.strict_clean_offset_p95_m,
                        args.max_off_route_ratio,
                        status=env_status,
                        error=env_error,
                        route_folder=route_folder,
                        case_id=case_id,
                        subject_id=subject_id,
                        trial_id=trial_id,
                        activity_id=activity_id,
                        input_metadata=input_metadata,
                    )
                )
                continue

            features = aggregate_activity(activity, args.segment_len_m)
            env_features, missing_cols = env_cache[case_id]
            features = features.drop(columns=ENV_OUTPUT_COLUMNS, errors="ignore").merge(
                env_features,
                on="segment_id",
                how="left",
            )
            for col in FEATURE_COLUMNS:
                if col not in features.columns:
                    features[col] = pd.NA
            features = features[FEATURE_COLUMNS]
            all_features.append(features)

            summary_rows.append(
                summarize_activity(
                    activity,
                    features,
                    args.clean_offset_p95_m,
                    args.strict_clean_offset_p95_m,
                    args.max_off_route_ratio,
                    status="segments_built",
                    error=format_missing_feature_error(missing_cols),
                    input_metadata=input_metadata,
                )
            )
        except Exception as exc:
            summary_rows.append(
                summarize_activity(
                    activity,
                    features,
                    args.clean_offset_p95_m,
                    args.strict_clean_offset_p95_m,
                    args.max_off_route_ratio,
                    status="error",
                    error=str(exc),
                    route_folder=route_folder,
                    case_id=case_id,
                    subject_id=subject_id,
                    trial_id=trial_id,
                    input_metadata=input_metadata,
                )
            )

    all_df = pd.concat(all_features, ignore_index=True) if all_features else pd.DataFrame(columns=FEATURE_COLUMNS)
    for col in FEATURE_COLUMNS:
        if col not in all_df.columns:
            all_df[col] = pd.NA
    all_df = all_df[FEATURE_COLUMNS]

    clean_df = all_df[clean_mask(all_df, args.clean_offset_p95_m, args.max_off_route_ratio)].copy() if not all_df.empty else all_df.copy()
    strict_df = all_df[clean_mask(all_df, args.strict_clean_offset_p95_m, args.max_off_route_ratio)].copy() if not all_df.empty else all_df.copy()

    summary = pd.DataFrame(summary_rows)
    for col in SUMMARY_COLUMNS:
        if col not in summary.columns:
            summary[col] = pd.NA
    summary = summary[SUMMARY_COLUMNS]

    all_path = out_dir / "activity_environment_segment_features_all.csv"
    clean_path = out_dir / "activity_environment_segment_features_clean.csv"
    strict_path = out_dir / "activity_environment_segment_features_strict_clean.csv"
    summary_path = out_dir / "activity_environment_segment_summary.csv"

    all_df.to_csv(all_path, index=False, encoding="utf-8-sig")
    clean_df.to_csv(clean_path, index=False, encoding="utf-8-sig")
    strict_df.to_csv(strict_path, index=False, encoding="utf-8-sig")
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")

    invalid_reason_counts = (
        all_df.loc[
            (pd.to_numeric(all_df["segment_elapsed_sec"], errors="coerce") <= 0)
            | (pd.to_numeric(all_df["segment_point_n"], errors="coerce") < 2),
            "time_quality",
        ]
        .value_counts(dropna=False)
        .to_dict()
        if not all_df.empty
        else {}
    )
    match_quality_counts = all_df["segment_match_quality"].value_counts(dropna=False).to_dict() if not all_df.empty else {}
    route_counts = all_df.groupby("route_folder").size().to_dict() if not all_df.empty else {}
    risk_missing_rates = {
        col: float(all_df[col].isna().mean())
        for col in ENV_OUTPUT_COLUMNS
        if not all_df.empty and col in all_df.columns and all_df[col].isna().any()
    }

    print(f"total activities processed: {len(summary)}")
    print(f"activities with segments built: {int((summary['status'] == 'segments_built').sum())}")
    print(f"total all segments: {len(all_df)}")
    print(f"total clean segments: {len(clean_df)}")
    print(f"total strict clean segments: {len(strict_df)}")
    print(f"per route_folder segment counts: {route_counts}")
    print(f"invalid segment reason counts: {invalid_reason_counts}")
    print(f"segment_match_quality distribution: {match_quality_counts}")
    print(f"risk feature merge missing rate: {risk_missing_rates}")
    print(f"wrote all segments: {all_path}")
    print(f"wrote clean segments: {clean_path}")
    print(f"wrote strict clean segments: {strict_path}")
    print(f"wrote summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
