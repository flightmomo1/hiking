#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CH6.5.6 terrain movement efficiency evidence v1.

This layer builds descriptive terrain/surface x movement-response evidence
from existing 50 m activity route-load behavior windows.

Purpose:
- Fill the previously missing "terrain movement efficiency" evidence chain for
  later radar-axis update.
- Keep the result descriptive and group-relative.
- Do NOT generate an ability score, rank, class, THCI score, final hiking risk
  score, route suitability score, go/no-go decision, medical diagnosis, or
  causality claim.
- Do NOT zero-fill missing evidence.

Default input:
  outputs/ib3_personal_hiking_features_route_load_comparison_full25_v1/
    activity_route_load_behavior_response_windows.csv

Outputs:
  outputs/report_figures/ch6_5_6_terrain_movement_efficiency_evidence_v1/
    terrain_movement_efficiency_window_evidence_v1.csv
    terrain_movement_efficiency_activity_summary_v1.csv
    terrain_movement_efficiency_axis_update_v1.csv
    terrain_movement_efficiency_context_group_summary_v1.csv
    terrain_movement_efficiency_attention_summary_v1.csv
    terrain_movement_efficiency_audit_v1.csv
    terrain_movement_efficiency_report_v1.html
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path
import numpy as np
import pandas as pd


DEFAULT_INPUT = (
    "outputs/ib3_personal_hiking_features_route_load_comparison_full25_v1/"
    "activity_route_load_behavior_response_windows.csv"
)
FALLBACK_INPUTS = [
    "outputs/report_figures/ch6_5_route_load_context_index_v1/route_load_context_windows_v1.csv",
    "outputs/ib3_personal_hiking_features_route_load_comparison_smoke_v1/activity_route_load_behavior_response_windows.csv",
]
DEFAULT_OUTPUT_ROOT = "outputs/report_figures/ch6_5_6_terrain_movement_efficiency_evidence_v1"

BOUNDARY = (
    "Descriptive CH6.5.6 terrain/surface x movement-response evidence only. "
    "Indices are group-relative context evidence for visualization and review. "
    "They are not ability scores, ability ranks, ability classes, THCI scores, "
    "final hiking risk scores, route suitability scores, go/no-go decisions, "
    "medical diagnoses, or causality evidence. Missing evidence is not zero-filled."
)

WINDOW_BOUNDARY = (
    "Window-level terrain movement maintenance context only. A low value indicates "
    "relative movement-response review within comparable terrain/surface contexts, "
    "not personal ability, abnormality, or causality."
)

LOW_SPEED_THRESHOLD_MPS = 0.7
MIN_CONTEXT_GROUP_WINDOWS = 20
MIN_ACTIVITY_WINDOWS_FOR_AXIS = 10


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=r"D:\mountain_work\115_osm")
    p.add_argument("--input-csv", default=DEFAULT_INPUT)
    p.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    p.add_argument("--min-context-group-windows", type=int, default=MIN_CONTEXT_GROUP_WINDOWS)
    p.add_argument("--min-activity-windows-for-axis", type=int, default=MIN_ACTIVITY_WINDOWS_FOR_AXIS)
    return p.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def locate_input(root: Path, requested: str) -> tuple[Path, list[dict]]:
    candidates = [requested] + FALLBACK_INPUTS
    inventory = []
    for c in candidates:
        p = resolve(root, c)
        exists = p.exists()
        inventory.append({
            "candidate_input_path": str(p),
            "exists": bool(exists),
            "length_bytes": int(p.stat().st_size) if exists else 0,
        })
        if exists:
            return p, inventory
    raise FileNotFoundError(
        "No terrain movement source input found. Tried:\n" +
        "\n".join(item["candidate_input_path"] for item in inventory)
    )


def read_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def require_columns(df: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise KeyError(f"{label} missing required columns: {missing}; available={list(df.columns)}")


def num(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series([np.nan] * len(df), index=df.index, dtype=float)
    return pd.to_numeric(df[col], errors="coerce")


def text_col(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series([""] * len(df), index=df.index, dtype=str)
    return df[col].fillna("").astype(str).str.strip()


def bool_from_text(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def pipe_join(values) -> str:
    out = []
    for v in values:
        if v is None or pd.isna(v):
            continue
        for part in str(v).split("|"):
            p = part.strip()
            if p and p.upper() != "NONE" and p.lower() != "nan":
                out.append(p)
    return "|".join(sorted(set(out))) if out else "NONE"


def contains_token(series: pd.Series, token: str) -> pd.Series:
    return series.fillna("").astype(str).str.lower().str.contains(token.lower(), regex=False)


def percentile_index(values: pd.Series, higher_is_better: bool = True) -> pd.Series:
    v = pd.to_numeric(values, errors="coerce")
    valid = v.dropna()
    if valid.nunique() <= 1:
        return pd.Series([np.nan] * len(v), index=v.index, dtype=float)
    ranks = v.rank(pct=True, method="average") * 100.0
    if not higher_is_better:
        ranks = 100.0 - ranks
    return ranks.round(3)


def context_group_percentile(
    df: pd.DataFrame,
    values: pd.Series,
    group_col: str,
    higher_is_better: bool,
    min_group_n: int,
) -> tuple[pd.Series, pd.Series]:
    """Return percentile index and source label using context group when possible.

    If a context group has fewer than min_group_n valid windows, fallback to global
    percentile. This avoids unstable tiny-bucket interpretation.
    """
    out = pd.Series([np.nan] * len(df), index=df.index, dtype=float)
    source = pd.Series(["MISSING"] * len(df), index=df.index, dtype=object)

    global_idx = percentile_index(values, higher_is_better=higher_is_better)

    for group_value, group_idx in df.groupby(group_col, dropna=False).groups.items():
        idx = list(group_idx)
        valid_n = pd.to_numeric(values.loc[idx], errors="coerce").notna().sum()
        if valid_n >= min_group_n:
            out.loc[idx] = percentile_index(values.loc[idx], higher_is_better=higher_is_better)
            source.loc[idx] = f"WITHIN_CONTEXT_GROUP:{group_value}"
        else:
            out.loc[idx] = global_idx.loc[idx]
            source.loc[idx] = f"GLOBAL_FALLBACK_SMALL_CONTEXT_GROUP:{group_value}"

    return out.round(3), source


def classify_context(row: pd.Series) -> str:
    flags = str(row.get("terrain_surface_context_flags", ""))
    band = str(row.get("route_load_context_band", ""))
    terrain_high = bool(row.get("terrain_evidence_high_context_bool", False))
    slope_high = bool(row.get("slope_or_vertical_high_context_bool", False))

    if "STEPS_CONTEXT" in flags:
        return "STEPS_CONTEXT"
    if terrain_high:
        return "HIGH_TERRAIN_EVIDENCE_CONTEXT"
    if band in {"HIGH_ROUTE_LOAD_CONTEXT", "VERY_HIGH_ROUTE_LOAD_CONTEXT"} or slope_high:
        return "HIGH_ROUTE_LOAD_OR_SLOPE_CONTEXT"
    if "ROAD_CONTEXT" in flags:
        return "ROAD_OR_WIDE_PATH_CONTEXT"
    if "TRAIL_OR_MIXED_OSM_CONTEXT" in flags:
        return "TRAIL_OR_MIXED_CONTEXT"
    return "LOW_INFORMATION_MIXED_CONTEXT"


def build_window_evidence(df: pd.DataFrame, min_group_n: int) -> pd.DataFrame:
    required = [
        "activity_id_short",
        "route_distance_window_start_m",
        "route_distance_window_end_m",
        "speed_mps_median",
        "low_speed_ratio",
        "stopped_ratio",
    ]
    require_columns(df, required, "activity route-load behavior windows")

    w = df.copy()

    # Normalize core fields.
    w["activity_id_short"] = text_col(w, "activity_id_short")
    w["route_distance_window_start_m"] = num(w, "route_distance_window_start_m")
    w["route_distance_window_end_m"] = num(w, "route_distance_window_end_m")
    w["point_count"] = num(w, "point_count")
    w["speed_mps_median"] = num(w, "speed_mps_median")
    w["low_speed_ratio"] = num(w, "low_speed_ratio")
    w["stopped_ratio"] = num(w, "stopped_ratio")

    # Terrain / surface evidence. Missing values remain NaN; boolean flags only
    # become true when evidence exists.
    w["route_profile_elevation_range_m"] = num(w, "route_profile_elevation_range_m")
    w["calibrated_slope_pct_p75_abs"] = num(w, "calibrated_slope_pct_p75_abs")
    w["ib2_terrain_evidence_median"] = num(w, "ib2_terrain_evidence_median")
    w["ib2_effort_evidence_median"] = num(w, "ib2_effort_evidence_median")
    w["near_steps_ratio"] = num(w, "near_steps_ratio")
    w["near_road_ratio"] = num(w, "near_road_ratio")
    w["near_cliff_ratio"] = num(w, "near_cliff_ratio")
    w["near_waterway_ratio"] = num(w, "near_waterway_ratio")
    w["route_load_context_band"] = text_col(w, "route_load_context_band").replace("", "ROUTE_LOAD_CONTEXT_MISSING")
    w["osm_exposure_types"] = text_col(w, "osm_exposure_types")

    if "route_load_context_index_0_100" in w.columns:
        w["route_load_context_index_0_100"] = num(w, "route_load_context_index_0_100")
    else:
        w["route_load_context_index_0_100"] = np.nan

    # Thresholds are descriptive within current full25 window distribution.
    terrain_p75 = w["ib2_terrain_evidence_median"].dropna().quantile(0.75) if w["ib2_terrain_evidence_median"].notna().any() else np.nan
    slope_p75 = w["calibrated_slope_pct_p75_abs"].dropna().quantile(0.75) if w["calibrated_slope_pct_p75_abs"].notna().any() else np.nan
    elev_p75 = w["route_profile_elevation_range_m"].dropna().quantile(0.75) if w["route_profile_elevation_range_m"].notna().any() else np.nan

    has_steps = (w["near_steps_ratio"].fillna(0) >= 0.30) | contains_token(w["osm_exposure_types"], "steps")
    has_road = (w["near_road_ratio"].fillna(0) >= 0.50) | contains_token(w["osm_exposure_types"], "road")
    has_trail = contains_token(w["osm_exposure_types"], "trail") | contains_token(w["osm_exposure_types"], "guidepost")
    has_cliff = (w["near_cliff_ratio"].fillna(0) > 0) | contains_token(w["osm_exposure_types"], "cliff")
    has_waterway = (w["near_waterway_ratio"].fillna(0) >= 0.30) | contains_token(w["osm_exposure_types"], "waterway")

    w["terrain_evidence_high_context_bool"] = False if pd.isna(terrain_p75) else (w["ib2_terrain_evidence_median"] >= float(terrain_p75))
    slope_high = False if pd.isna(slope_p75) else (w["calibrated_slope_pct_p75_abs"] >= float(slope_p75))
    elev_high = False if pd.isna(elev_p75) else (w["route_profile_elevation_range_m"] >= float(elev_p75))
    w["slope_or_vertical_high_context_bool"] = slope_high | elev_high

    flags = []
    for i in w.index:
        fs = []
        if bool(has_steps.loc[i]):
            fs.append("STEPS_CONTEXT")
        if bool(has_road.loc[i]):
            fs.append("ROAD_CONTEXT")
        if bool(has_trail.loc[i]):
            fs.append("TRAIL_OR_MIXED_OSM_CONTEXT")
        if bool(has_cliff.loc[i]):
            fs.append("CLIFF_PROXIMITY_CONTEXT")
        if bool(has_waterway.loc[i]):
            fs.append("WATERWAY_PROXIMITY_CONTEXT")
        if bool(w.loc[i, "terrain_evidence_high_context_bool"]):
            fs.append("IB2_TERRAIN_HIGH_CONTEXT")
        if bool(w.loc[i, "slope_or_vertical_high_context_bool"]):
            fs.append("SLOPE_OR_VERTICAL_HIGH_CONTEXT")
        flags.append(pipe_join(fs))
    w["terrain_surface_context_flags"] = flags
    w["terrain_surface_context_group"] = w.apply(classify_context, axis=1)

    # Context-adjusted movement maintenance components.
    speed_idx, speed_src = context_group_percentile(
        w, w["speed_mps_median"], "terrain_surface_context_group", True, min_group_n
    )
    low_speed_idx, low_speed_src = context_group_percentile(
        w, w["low_speed_ratio"], "terrain_surface_context_group", False, min_group_n
    )
    stopped_idx, stopped_src = context_group_percentile(
        w, w["stopped_ratio"], "terrain_surface_context_group", False, min_group_n
    )

    w["speed_context_adjusted_index_0_100"] = speed_idx
    w["low_speed_context_adjusted_index_0_100"] = low_speed_idx
    w["stopped_context_adjusted_index_0_100"] = stopped_idx
    w["speed_context_percentile_source"] = speed_src
    w["low_speed_context_percentile_source"] = low_speed_src
    w["stopped_context_percentile_source"] = stopped_src

    component_available = (
        w["speed_context_adjusted_index_0_100"].notna()
        & w["low_speed_context_adjusted_index_0_100"].notna()
        & w["stopped_context_adjusted_index_0_100"].notna()
    )
    w["terrain_movement_component_available_bool"] = component_available

    w["terrain_movement_maintenance_index_0_100"] = np.where(
        component_available,
        (
            0.50 * w["speed_context_adjusted_index_0_100"]
            + 0.30 * w["low_speed_context_adjusted_index_0_100"]
            + 0.20 * w["stopped_context_adjusted_index_0_100"]
        ),
        np.nan,
    )
    w["terrain_movement_maintenance_index_0_100"] = pd.to_numeric(
        w["terrain_movement_maintenance_index_0_100"], errors="coerce"
    ).round(3)

    w["high_terrain_or_surface_context_bool"] = (
        has_steps
        | w["terrain_evidence_high_context_bool"]
        | w["slope_or_vertical_high_context_bool"]
        | w["route_load_context_band"].isin(["HIGH_ROUTE_LOAD_CONTEXT", "VERY_HIGH_ROUTE_LOAD_CONTEXT"])
    )

    attention_flags = []
    for _, row in w.iterrows():
        fs = []
        if pd.notna(row.get("speed_mps_median")) and float(row["speed_mps_median"]) < LOW_SPEED_THRESHOLD_MPS:
            fs.append("LOW_SPEED_WINDOW_CONTEXT")
        if pd.notna(row.get("low_speed_ratio")) and float(row["low_speed_ratio"]) >= 0.30:
            fs.append("HIGH_LOW_SPEED_RATIO_CONTEXT")
        if pd.notna(row.get("stopped_ratio")) and float(row["stopped_ratio"]) > 0.05:
            fs.append("STOPPED_WINDOW_CONTEXT")
        if pd.notna(row.get("terrain_movement_maintenance_index_0_100")) and float(row["terrain_movement_maintenance_index_0_100"]) <= 25:
            fs.append("LOW_TERRAIN_MOVEMENT_MAINTENANCE_INDEX_CONTEXT")
        if bool(row.get("high_terrain_or_surface_context_bool", False)):
            fs.append("HIGH_TERRAIN_OR_SURFACE_CONTEXT")
        attention_flags.append(pipe_join(fs))
    w["terrain_movement_attention_flags"] = attention_flags

    keep = [
        "activity_id_short",
        "activity_id_full",
        "route_distance_window_start_m",
        "route_distance_window_end_m",
        "route_phase",
        "point_count",
        "route_load_context_band",
        "route_load_context_index_0_100",
        "route_profile_elevation_range_m",
        "calibrated_slope_pct_p75_abs",
        "ib2_terrain_evidence_median",
        "ib2_effort_evidence_median",
        "osm_exposure_types",
        "near_steps_ratio",
        "near_road_ratio",
        "near_cliff_ratio",
        "near_waterway_ratio",
        "terrain_surface_context_flags",
        "terrain_surface_context_group",
        "terrain_evidence_high_context_bool",
        "slope_or_vertical_high_context_bool",
        "high_terrain_or_surface_context_bool",
        "speed_mps_median",
        "low_speed_ratio",
        "stopped_ratio",
        "speed_context_adjusted_index_0_100",
        "low_speed_context_adjusted_index_0_100",
        "stopped_context_adjusted_index_0_100",
        "speed_context_percentile_source",
        "low_speed_context_percentile_source",
        "stopped_context_percentile_source",
        "terrain_movement_component_available_bool",
        "terrain_movement_maintenance_index_0_100",
        "terrain_movement_attention_flags",
        "window_qa_flags",
    ]
    keep = [c for c in keep if c in w.columns]
    out = w[keep].copy()
    out["interpretation_boundary"] = WINDOW_BOUNDARY
    return out


def weighted_mean(values: pd.Series, weights: pd.Series | None = None) -> float:
    v = pd.to_numeric(values, errors="coerce")
    if weights is None:
        return float(v.dropna().mean()) if v.notna().any() else np.nan
    w = pd.to_numeric(weights, errors="coerce").fillna(0)
    mask = v.notna() & (w > 0)
    if mask.any():
        return float(np.average(v[mask], weights=w[mask]))
    return float(v.dropna().mean()) if v.notna().any() else np.nan


def build_activity_summary(w: pd.DataFrame, min_activity_windows: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    for activity_id, g in w.groupby("activity_id_short", dropna=False):
        total_n = int(len(g))
        available_n = int(g["terrain_movement_component_available_bool"].fillna(False).sum())
        high_context = g["high_terrain_or_surface_context_bool"].fillna(False)
        high_n = int(high_context.sum())
        high_available = g.loc[high_context & g["terrain_movement_component_available_bool"].fillna(False)]

        weights = pd.to_numeric(g.get("point_count", pd.Series([1] * len(g), index=g.index)), errors="coerce").fillna(1)
        idx_mean = weighted_mean(g["terrain_movement_maintenance_index_0_100"], weights)
        high_idx_mean = weighted_mean(
            high_available["terrain_movement_maintenance_index_0_100"],
            pd.to_numeric(high_available.get("point_count", pd.Series([1] * len(high_available), index=high_available.index)), errors="coerce").fillna(1),
        ) if len(high_available) else np.nan

        # A compact top flag summary.
        all_flags = []
        for item in g["terrain_movement_attention_flags"]:
            if item and str(item).upper() != "NONE":
                all_flags.extend(str(item).split("|"))
        flag_summary = "|".join(
            f"{flag}:{all_flags.count(flag)}"
            for flag in sorted(set(all_flags))
        ) if all_flags else "NONE"

        if available_n < min_activity_windows:
            support = "INSUFFICIENT_EVIDENCE"
        elif high_n < 3:
            support = "LIMITED_LOW_TERRAIN_SURFACE_EXPOSURE"
        else:
            support = "SUPPORTED_TERRAIN_MOVEMENT_EVIDENCE"

        rows.append({
            "activity_id_short": activity_id,
            "window_count": total_n,
            "available_window_count": available_n,
            "high_terrain_or_surface_window_count": high_n,
            "high_terrain_or_surface_window_ratio": round(high_n / total_n, 6) if total_n else np.nan,
            "terrain_movement_maintenance_index_mean_0_100": round(idx_mean, 3) if pd.notna(idx_mean) else np.nan,
            "high_terrain_movement_maintenance_index_mean_0_100": round(high_idx_mean, 3) if pd.notna(high_idx_mean) else np.nan,
            "terrain_surface_context_group_summary": pipe_join(g["terrain_surface_context_group"].dropna().astype(str).unique()),
            "terrain_movement_attention_flag_summary": flag_summary,
            "axis_support_status": support,
            "interpretation_boundary": BOUNDARY,
        })

    summary = pd.DataFrame(rows)

    # Activity-level group-relative axis index based on the terrain-adjusted maintenance mean.
    vals = pd.to_numeric(summary["terrain_movement_maintenance_index_mean_0_100"], errors="coerce")
    if vals.dropna().nunique() > 1:
        summary["terrain_movement_efficiency_axis_index_0_100"] = vals.rank(pct=True, method="average") * 100
        summary["terrain_movement_efficiency_axis_index_0_100"] = summary["terrain_movement_efficiency_axis_index_0_100"].round(3)
    else:
        summary["terrain_movement_efficiency_axis_index_0_100"] = np.nan

    q25 = vals.dropna().quantile(0.25) if vals.notna().any() else np.nan
    q75 = vals.dropna().quantile(0.75) if vals.notna().any() else np.nan
    labels = []
    for _, row in summary.iterrows():
        value = row["terrain_movement_maintenance_index_mean_0_100"]
        support = row["axis_support_status"]
        if support == "INSUFFICIENT_EVIDENCE":
            labels.append("INSUFFICIENT_TERRAIN_MOVEMENT_EVIDENCE")
        elif support == "LIMITED_LOW_TERRAIN_SURFACE_EXPOSURE":
            labels.append("LIMITED_TERRAIN_SURFACE_EXPOSURE_CONTEXT")
        elif pd.notna(q25) and pd.notna(value) and float(value) <= float(q25):
            labels.append("LOWER_TERRAIN_MOVEMENT_MAINTENANCE_CONTEXT_REVIEW")
        elif pd.notna(q75) and pd.notna(value) and float(value) >= float(q75):
            labels.append("HIGHER_TERRAIN_MOVEMENT_MAINTENANCE_CONTEXT")
        else:
            labels.append("REFERENCE_TERRAIN_MOVEMENT_MAINTENANCE_CONTEXT")
    summary["terrain_movement_context_label"] = labels

    axis_update = summary[[
        "activity_id_short",
        "terrain_movement_efficiency_axis_index_0_100",
        "terrain_movement_maintenance_index_mean_0_100",
        "high_terrain_movement_maintenance_index_mean_0_100",
        "axis_support_status",
        "terrain_movement_context_label",
        "available_window_count",
        "high_terrain_or_surface_window_count",
        "high_terrain_or_surface_window_ratio",
    ]].copy()
    axis_update["axis_id"] = "terrain_movement_efficiency"
    axis_update["axis_label_zh"] = "地形移動效率"
    axis_update["axis_support_status_for_radar"] = np.where(
        axis_update["axis_support_status"].eq("SUPPORTED_TERRAIN_MOVEMENT_EVIDENCE"),
        "SUPPORTED_TERRAIN_MOVEMENT_EVIDENCE",
        axis_update["axis_support_status"],
    )
    axis_update["axis_description"] = (
        "Descriptive terrain/surface-adjusted movement maintenance context. "
        "Use as radar evidence only after preserving interpretation boundary."
    )
    axis_update["interpretation_boundary"] = BOUNDARY

    attention = summary.groupby(["terrain_movement_context_label", "axis_support_status"], dropna=False).agg(
        activity_count=("activity_id_short", "count"),
        activity_id_short_list=("activity_id_short", lambda s: "|".join(map(str, sorted(s)))),
        mean_axis_index_0_100=("terrain_movement_efficiency_axis_index_0_100", lambda s: round(float(pd.to_numeric(s, errors="coerce").mean()), 3) if pd.to_numeric(s, errors="coerce").notna().any() else np.nan),
    ).reset_index()
    attention["interpretation_boundary"] = BOUNDARY

    return summary.sort_values("activity_id_short").reset_index(drop=True), axis_update.sort_values("activity_id_short").reset_index(drop=True), attention


def build_context_group_summary(w: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for group_name, g in w.groupby("terrain_surface_context_group", dropna=False):
        idx = pd.to_numeric(g["terrain_movement_maintenance_index_0_100"], errors="coerce")
        rows.append({
            "terrain_surface_context_group": group_name,
            "window_count": int(len(g)),
            "activity_count": int(g["activity_id_short"].nunique()),
            "available_window_count": int(idx.notna().sum()),
            "speed_mps_median": round(float(pd.to_numeric(g["speed_mps_median"], errors="coerce").median()), 6) if g["speed_mps_median"].notna().any() else np.nan,
            "low_speed_ratio_median": round(float(pd.to_numeric(g["low_speed_ratio"], errors="coerce").median()), 6) if g["low_speed_ratio"].notna().any() else np.nan,
            "stopped_ratio_median": round(float(pd.to_numeric(g["stopped_ratio"], errors="coerce").median()), 6) if g["stopped_ratio"].notna().any() else np.nan,
            "terrain_movement_maintenance_index_median_0_100": round(float(idx.median()), 3) if idx.notna().any() else np.nan,
            "terrain_movement_maintenance_index_mean_0_100": round(float(idx.mean()), 3) if idx.notna().any() else np.nan,
            "interpretation_boundary": BOUNDARY,
        })
    return pd.DataFrame(rows).sort_values("terrain_surface_context_group").reset_index(drop=True)


def html_escape(v) -> str:
    return html.escape("" if pd.isna(v) else str(v))


def write_html_report(path: Path, input_path: Path, summary: pd.DataFrame, context_summary: pd.DataFrame, attention: pd.DataFrame, audit: pd.DataFrame) -> None:
    top_low = summary.sort_values("terrain_movement_efficiency_axis_index_0_100", na_position="last").head(12)
    top_high = summary.sort_values("terrain_movement_efficiency_axis_index_0_100", ascending=False, na_position="last").head(12)

    def table(df: pd.DataFrame, columns: list[str]) -> str:
        rows = []
        rows.append("<table><thead><tr>" + "".join(f"<th>{html_escape(c)}</th>" for c in columns) + "</tr></thead><tbody>")
        for _, r in df[columns].iterrows():
            rows.append("<tr>" + "".join(f"<td>{html_escape(r[c])}</td>" for c in columns) + "</tr>")
        rows.append("</tbody></table>")
        return "\n".join(rows)

    summary_cols = [
        "activity_id_short",
        "axis_support_status",
        "terrain_movement_context_label",
        "terrain_movement_efficiency_axis_index_0_100",
        "terrain_movement_maintenance_index_mean_0_100",
        "high_terrain_or_surface_window_ratio",
        "terrain_movement_attention_flag_summary",
    ]
    context_cols = [
        "terrain_surface_context_group",
        "window_count",
        "activity_count",
        "terrain_movement_maintenance_index_mean_0_100",
        "speed_mps_median",
        "low_speed_ratio_median",
        "stopped_ratio_median",
    ]
    attention_cols = [
        "terrain_movement_context_label",
        "axis_support_status",
        "activity_count",
        "activity_id_short_list",
        "mean_axis_index_0_100",
    ]

    html_text = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>CH6.5.6 Terrain Movement Efficiency Evidence v1</title>
<style>
body {{ font-family: "Microsoft JhengHei", "Noto Sans TC", Arial, sans-serif; margin: 24px; line-height: 1.55; }}
.boundary {{ background: #fff7e6; border-left: 5px solid #d99000; padding: 12px 16px; margin-bottom: 20px; }}
table {{ border-collapse: collapse; width: 100%; margin: 12px 0 24px 0; font-size: 13px; }}
th, td {{ border: 1px solid #ccc; padding: 6px 8px; vertical-align: top; }}
th {{ background: #f2f2f2; }}
code {{ background: #f4f4f4; padding: 2px 4px; border-radius: 4px; }}
</style>
</head>
<body>
<h1>CH6.5.6 地形移動效率 evidence v1</h1>
<div class="boundary"><b>Interpretation boundary:</b> {html_escape(BOUNDARY)}</div>
<p><b>Input:</b> <code>{html_escape(str(input_path))}</code></p>
<p><b>Audit:</b> <code>{html_escape(audit.iloc[0].get("audit_conclusion", ""))}</code></p>

<h2>Context group summary</h2>
{table(context_summary, context_cols)}

<h2>Lower terrain movement maintenance context review</h2>
{table(top_low, summary_cols)}

<h2>Higher terrain movement maintenance context</h2>
{table(top_high, summary_cols)}

<h2>Attention label summary</h2>
{table(attention, attention_cols)}
</body>
</html>
"""
    path.write_text(html_text, encoding="utf-8")


def build_audit(
    input_path: Path,
    output_root: Path,
    source_inventory: list[dict],
    windows: pd.DataFrame,
    summary: pd.DataFrame,
    context_summary: pd.DataFrame,
    axis_update: pd.DataFrame,
    min_group_n: int,
    min_activity_windows: int,
) -> pd.DataFrame:
    issues = []
    if windows.empty:
        issues.append("NO_WINDOW_ROWS")
    if summary.empty:
        issues.append("NO_ACTIVITY_SUMMARY_ROWS")
    if windows["terrain_movement_maintenance_index_0_100"].isna().all():
        issues.append("ALL_WINDOW_TERRAIN_MOVEMENT_INDEX_MISSING")
    if axis_update["terrain_movement_efficiency_axis_index_0_100"].isna().all():
        issues.append("ALL_AXIS_UPDATE_INDEX_MISSING")
    forbidden = [
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
    generated_cols = set(windows.columns) | set(summary.columns) | set(axis_update.columns)
    bad_cols = [c for c in generated_cols if c in forbidden]
    if bad_cols:
        issues.append("FORBIDDEN_COLUMNS_PRESENT:" + "|".join(sorted(bad_cols)))

    conclusion = "PASS_CH6_5_6_TERRAIN_MOVEMENT_EFFICIENCY_EVIDENCE_V1_DESCRIPTIVE_ONLY"
    if issues:
        conclusion = "REVIEW_REQUIRED_CH6_5_6_TERRAIN_MOVEMENT_EFFICIENCY_EVIDENCE_V1"

    return pd.DataFrame([{
        "input_path": str(input_path),
        "output_root": str(output_root),
        "source_inventory": "|".join(f"{i['candidate_input_path']}:{i['exists']}" for i in source_inventory),
        "window_rows": int(len(windows)),
        "activity_rows": int(len(summary)),
        "context_group_rows": int(len(context_summary)),
        "axis_update_rows": int(len(axis_update)),
        "min_context_group_windows": int(min_group_n),
        "min_activity_windows_for_axis": int(min_activity_windows),
        "supported_axis_rows": int(axis_update["axis_support_status"].eq("SUPPORTED_TERRAIN_MOVEMENT_EVIDENCE").sum()),
        "limited_axis_rows": int(axis_update["axis_support_status"].astype(str).str.startswith("LIMITED").sum()),
        "insufficient_axis_rows": int(axis_update["axis_support_status"].eq("INSUFFICIENT_EVIDENCE").sum()),
        "zero_fill_used": False,
        "weather_zero_fill_used": False,
        "ability_score_generated": False,
        "ability_rank_generated": False,
        "ability_class_generated": False,
        "route_suitability_score_generated": False,
        "go_no_go_generated": False,
        "audit_issues": pipe_join(issues),
        "audit_conclusion": conclusion,
        "interpretation_boundary": BOUNDARY,
    }])


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    input_path, source_inventory = locate_input(root, args.input_csv)
    output_root = resolve(root, args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    source = read_csv(input_path, "activity route-load behavior windows")

    windows = build_window_evidence(source, args.min_context_group_windows)
    summary, axis_update, attention = build_activity_summary(windows, args.min_activity_windows_for_axis)
    context_summary = build_context_group_summary(windows)
    audit = build_audit(
        input_path,
        output_root,
        source_inventory,
        windows,
        summary,
        context_summary,
        axis_update,
        args.min_context_group_windows,
        args.min_activity_windows_for_axis,
    )

    outputs = {
        "windows": output_root / "terrain_movement_efficiency_window_evidence_v1.csv",
        "activity_summary": output_root / "terrain_movement_efficiency_activity_summary_v1.csv",
        "axis_update": output_root / "terrain_movement_efficiency_axis_update_v1.csv",
        "context_group_summary": output_root / "terrain_movement_efficiency_context_group_summary_v1.csv",
        "attention_summary": output_root / "terrain_movement_efficiency_attention_summary_v1.csv",
        "audit": output_root / "terrain_movement_efficiency_audit_v1.csv",
        "html_report": output_root / "terrain_movement_efficiency_report_v1.html",
    }

    windows.to_csv(outputs["windows"], index=False, encoding="utf-8-sig")
    summary.to_csv(outputs["activity_summary"], index=False, encoding="utf-8-sig")
    axis_update.to_csv(outputs["axis_update"], index=False, encoding="utf-8-sig")
    context_summary.to_csv(outputs["context_group_summary"], index=False, encoding="utf-8-sig")
    attention.to_csv(outputs["attention_summary"], index=False, encoding="utf-8-sig")
    audit.to_csv(outputs["audit"], index=False, encoding="utf-8-sig")
    write_html_report(outputs["html_report"], input_path, summary, context_summary, attention, audit)

    print({
        "output_root": str(output_root),
        "input_path": str(input_path),
        "window_rows": int(len(windows)),
        "activity_rows": int(len(summary)),
        "axis_update_rows": int(len(axis_update)),
        "supported_axis_rows": int(audit.iloc[0]["supported_axis_rows"]),
        "limited_axis_rows": int(audit.iloc[0]["limited_axis_rows"]),
        "insufficient_axis_rows": int(audit.iloc[0]["insufficient_axis_rows"]),
        "zero_fill_used": False,
        "audit_conclusion": str(audit.iloc[0]["audit_conclusion"]),
        "outputs": {k: str(v) for k, v in outputs.items()},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
