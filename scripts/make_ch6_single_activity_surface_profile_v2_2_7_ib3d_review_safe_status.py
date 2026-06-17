#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Build Chapter 6.5 single-activity route-surface / behavior profile v2.2.7 + speed threshold pause focus.

This script combines:
1. Codex v1.4 style 1 m standard-route surface ribbon, event markers, and route slope.
2. Single activity behavior profile filtered by --activity-id.

Intended use:
    cd D:\mountain_work\115_osm
    python scripts\make_ch6_single_activity_surface_profile_v2_2_7_ib3d_review_safe_status.py --root D:\mountain_work\115_osm --activity-id 8_1

Batch all activities in the behavior CSV:
    python scripts\make_ch6_single_activity_surface_profile_v2_2_7_ib3d_review_safe_status.py --root D:\mountain_work\115_osm --all

Boundaries:
- Descriptive profile only.
- No ability score, ability rank, ability class, THCI score, radar score, or final hiking risk score.
- Route surface and slope are route-axis evidence.
- Behavior metrics are window summaries for a selected activity, not 1 m instantaneous observations.
- Shelter is displayed as a context zone merged from OSM proximity runs; markers are nearest-node references, not physical facility counts or proof of facility use.
- Event markers are OSM proximity / behavior candidates, not proof of facility use.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.font_manager import FontProperties, findfont
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


DEFAULT_ROUTE_CSV = (
    "outputs/ib2_v2_route_risk_v1_3b_contract_qa/"
    "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b/"
    "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b_route_risk_v2.csv"
)

# Prefer the smoke CSV discussed in the review thread. The script also auto-falls back to full25.
DEFAULT_BEHAVIOR_CSV = (
    "outputs/ib3_personal_hiking_features_route_load_comparison_smoke_v1/"
    "activity_route_load_behavior_response_windows.csv"
)
FALLBACK_BEHAVIOR_CSV = (
    "outputs/ib3_personal_hiking_features_route_load_comparison_full25_v1/"
    "activity_route_load_behavior_response_windows.csv"
)

DEFAULT_OUTDIR = (
    "outputs/report_figures/"
    "ch6_single_activity_surface_profiles_v2_2_7_ib3d_review_safe_status"
)

DEFAULT_IB3D_EVENT_OVERLAY_ROOT = (
    "outputs/report_figures/"
    "ch6_5_ib3d_event_route_window_bridge_v1"
)

LOW_SPEED_THRESHOLD_MPS = 0.7

IB3D_EVENT_OVERLAY_SPECS = [
    {
        "event_type": "high_hr_recovery_stop",
        "label": "IB3D high-HR recovery",
        "count_col": "high_hr_recovery_stop_count",
        "ratio_col": "high_hr_recovery_stop_ratio",
        "color": "#DC2626",
        "marker": "v",
        "y": 1.26,
        "size": 72,
        "band_color": "#DC2626",
        "band_alpha": 0.105,
    },
    {
        "event_type": "short_pause",
        "label": "IB3D short pause",
        "count_col": "short_pause_count",
        "ratio_col": "",
        "color": "#64748B",
        "marker": "o",
        "y": 1.08,
        "size": 54,
        "band_color": "#64748B",
        "band_alpha": 0.18,
    },
    {
        "event_type": "off_route_rest",
        "label": "IB3D off-route rest",
        "count_col": "",
        "ratio_col": "off_route_rest_ratio",
        "color": "#7C3AED",
        "marker": "X",
        "y": 0.90,
        "size": 64,
        "band_color": "#7C3AED",
        "band_alpha": 0.115,
    },
]

IB3D_EVENT_OVERLAY_BOUNDARY = (
    "IB3D event overlay is derived from elapsed-time intervals bridged to "
    "IB3A2 reliable route-distance points and aggregated to 50 m route windows. "
    "It is descriptive event evidence only, not a score, rank, class, THCI, "
    "radar, final-risk result, causal claim, or proof of facility use."
)

SURFACE_ORDER = ["step", "footway", "path_trail", "road", "unknown_other"]
SURFACE_LABELS = {
    "step": "階梯 step",
    "footway": "步道 footway",
    "path_trail": "山徑 path / trail",
    "road": "道路 road",
    "unknown_other": "未知／其他",
}
SURFACE_COLORS = {
    "step": "#D55E00",
    "footway": "#E69F00",
    "path_trail": "#009E73",
    "road": "#4C78A8",
    "unknown_other": "#B8B8B8",
}

EVENT_SPECS = [
    ("shelter", "遮蔽／庇護", "near_shelter", "dist_shelter_m", "s"),
    ("guidepost", "指標", "near_guidepost", "dist_guidepost_m", "^"),
    ("peak", "山峰", "near_peak", "dist_peak_m", "*"),
    ("trailhead", "登山口", "near_trailhead", "dist_trailhead_m", "D"),
    ("waterway", "水系", "near_waterway", "dist_waterway_m", "v"),
]
EVENT_COLORS = {
    "shelter": "#8C564B",
    "guidepost": "#9467BD",
    "peak": "#D62728",
    "trailhead": "#1F77B4",
    "waterway": "#17BECF",
    "rest_candidate": "#2CA02C",
}

PROHIBITED_OUTPUT_TOKENS = (
    "ability_score",
    "ability_rank",
    "ability_class",
    "thci_score",
    "radar_score",
    "final_hiking_risk_score",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Chapter 6.5 single-activity route surface / behavior profile."
    )
    parser.add_argument("--root", default=r"D:\mountain_work\115_osm")
    parser.add_argument("--route-csv", default=DEFAULT_ROUTE_CSV)
    parser.add_argument("--behavior-csv", default=DEFAULT_BEHAVIOR_CSV)
    parser.add_argument("--outdir", default=DEFAULT_OUTDIR)
    parser.add_argument("--activity-id", default="8_1", help="activity_id_short to plot")
    parser.add_argument("--all", action="store_true", help="Generate one figure per activity_id_short in behavior CSV")
    parser.add_argument(
        "--behavior-bin-m",
        type=int,
        choices=(10, 25, 50, 100, 500),
        default=50,
        help="Distance grain for behavior summaries. Use 50 m by default.",
    )
    parser.add_argument(
        "--rest-stopped-threshold",
        type=float,
        default=0.10,
        help="Single-activity rest candidate threshold for stopped_ratio.",
    )
    parser.add_argument(
        "--rest-low-speed-threshold",
        type=float,
        default=0.60,
        help="Single-activity rest candidate threshold for low_speed_ratio.",
    )
    parser.add_argument(
        "--speed-plot-cap-mps",
        type=float,
        default=2.5,
        help=(
            "Cap speed panel display at this m/s value to avoid one GPS/projection spike "
            "compressing ordinary hiking-speed variation. The CSV export remains uncapped."
        ),
    )
    parser.add_argument(
        "--shelter-zone-merge-gap-m",
        type=float,
        default=120.0,
        help=(
            "Merge adjacent near_shelter proximity runs into one report-level shelter context "
            "zone when the route-axis gap between runs is no more than this many meters."
        ),
    )
    return parser.parse_args()


def resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def resolve_behavior_csv(root: Path, behavior_csv_arg: str) -> Path:
    path = resolve_path(root, behavior_csv_arg)
    if path.exists():
        return path

    fallback = resolve_path(root, FALLBACK_BEHAVIOR_CSV)
    if fallback.exists():
        print(f"[WARN] behavior CSV not found: {path}")
        print(f"[WARN] fallback behavior CSV used: {fallback}")
        return fallback

    raise FileNotFoundError(f"Behavior CSV not found: {path}; fallback not found: {fallback}")


def setup_font() -> None:
    candidates = [
        "Microsoft JhengHei",
        "Microsoft YaHei",
        "Noto Sans CJK TC",
        "Noto Sans TC",
        "Source Han Sans TW",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    for family in candidates:
        try:
            located = findfont(FontProperties(family=family), fallback_to_default=False)
        except ValueError:
            continue
        if located:
            plt.rcParams["font.family"] = family
            break
    plt.rcParams["axes.unicode_minus"] = False


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    for enc in ("utf-8-sig", "utf-8", "cp950"):
        try:
            return pd.read_csv(path, encoding=enc, low_memory=False)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, low_memory=False)


def require_columns(df: pd.DataFrame, columns: Iterable[str], source: Path | str) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"{source} missing required columns: {missing}")


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def truthy(series: pd.Series) -> pd.Series:
    return (
        series.fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        .isin({"1", "true", "yes", "y"})
    )


def mode_text(series: pd.Series) -> str:
    values = series.dropna().astype(str)
    values = values[values.str.strip() != ""]
    if values.empty:
        return ""
    modes = values.mode()
    return str(modes.iloc[0]) if not modes.empty else str(values.iloc[0])


def sanitize(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_\-]+", "_", str(value))


def classify_surface(row: pd.Series) -> str:
    """Classify route surface/path type from canonical route semantics.

    Priority:
    step > footway > path/trail > road > unknown/other
    """
    highway = str(row.get("osm_highway", "") or "").strip().lower()
    semantic = str(row.get("route_semantic_class", "") or "").strip().lower()
    source_surface = str(row.get("surface_class", "") or "").strip().lower()
    osm_surface = str(row.get("osm_surface", "") or "").strip().lower()
    steps = str(row.get("osm_is_steps", "") or "").strip().lower()

    text = " ".join([highway, semantic, source_surface, osm_surface])

    if steps in {"1", "true", "yes", "y"} or highway == "steps" or "step" in text:
        return "step"
    if highway == "footway" or "footway" in text:
        return "footway"
    if highway in {"path", "track", "trail", "bridleway"} or any(
        token in text for token in ("path", "trail", "track")
    ):
        return "path_trail"
    if highway in {
        "service",
        "residential",
        "living_street",
        "unclassified",
        "tertiary",
        "secondary",
        "primary",
        "road",
        "pedestrian",
    } or any(token in text for token in ("road", "street")):
        return "road"
    return "unknown_other"


def build_route_1m(route: pd.DataFrame, source_name: Path | str) -> pd.DataFrame:
    """Normalize route evidence to an integer 1 m route-distance axis."""
    # Route CSV variants may not all have exactly the same columns. Keep hard requirements minimal.
    require_columns(route, ["dist_m"], source_name)

    source = route.copy()
    source["dist_m"] = numeric(source["dist_m"])
    source = source.dropna(subset=["dist_m"]).sort_values("dist_m")
    source = source.drop_duplicates(subset=["dist_m"], keep="first")

    if source.empty:
        raise ValueError("route source is empty after dist_m cleaning")

    max_integer_m = int(np.floor(source["dist_m"].max()))
    grid = pd.DataFrame({"route_distance_m": np.arange(max_integer_m + 1, dtype=float)})

    wanted = [
        "dist_m",
        "lat",
        "lon",
        "osm_highway",
        "osm_surface",
        "surface_class",
        "route_semantic_class",
        "osm_is_steps",
        "slope_pct",
        "slope_window_nlsc",
        "calibrated_slope_pct_median",
    ]
    for _, _, near_col, distance_col, _ in EVENT_SPECS:
        wanted.extend([near_col, distance_col])
    wanted.extend([
        "near_bench",
        "dist_bench_m",
        "near_picnic_table",
        "dist_picnic_table_m",
    ])
    wanted = [column for column in dict.fromkeys(wanted) if column in source.columns]

    merged = pd.merge_asof(
        grid.sort_values("route_distance_m"),
        source[wanted].sort_values("dist_m"),
        left_on="route_distance_m",
        right_on="dist_m",
        direction="nearest",
        tolerance=0.51,
    )

    merged["source_route_distance_m"] = merged["dist_m"]
    merged["route_distance_m"] = merged["route_distance_m"].astype(int)

    # Missing semantic columns are allowed, but surface will be unknown/other.
    for col in ["osm_highway", "osm_surface", "surface_class", "route_semantic_class", "osm_is_steps"]:
        if col not in merged.columns:
            merged[col] = ""

    merged["surface_type"] = merged.apply(classify_surface, axis=1)
    merged["surface_label"] = merged["surface_type"].map(SURFACE_LABELS)

    # Prefer signed route slope.
    if "slope_pct" in merged.columns:
        slope_series = numeric(merged["slope_pct"])
        slope_source = "slope_pct"
    elif "slope_window_nlsc" in merged.columns:
        slope_series = numeric(merged["slope_window_nlsc"])
        slope_source = "slope_window_nlsc"
    elif "calibrated_slope_pct_median" in merged.columns:
        slope_series = numeric(merged["calibrated_slope_pct_median"])
        slope_source = "calibrated_slope_pct_median"
    else:
        slope_series = pd.Series(np.nan, index=merged.index)
        slope_source = "missing"

    merged["slope_pct_raw"] = slope_series
    merged["slope_pct_plot"] = slope_series.rolling(window=11, center=True, min_periods=1).median()
    merged["slope_source"] = slope_source
    merged["slope_method"] = (
        "11m centered rolling median of signed route slope for display readability"
        if slope_source != "missing"
        else "slope source missing"
    )
    merged["surface_method"] = (
        "nearest canonical route row within 0.51m; priority=step>footway>path/trail>road>unknown/other"
    )
    return merged


def contiguous_true_runs(mask: pd.Series) -> list[tuple[int, int]]:
    indexes = np.flatnonzero(mask.fillna(False).to_numpy(dtype=bool))
    if len(indexes) == 0:
        return []
    split_at = np.where(np.diff(indexes) > 1)[0] + 1
    groups = np.split(indexes, split_at)
    return [(int(group[0]), int(group[-1])) for group in groups if len(group)]



def build_shelter_context_zones(
    route_1m: pd.DataFrame,
    merge_gap_m: float = 120.0,
) -> pd.DataFrame:
    """Merge near_shelter runs into report-level shelter context zones.

    This is a presentation-layer interpretation for Chapter 6.5. It keeps the
    raw OSM proximity evidence but avoids implying that adjacent near_shelter
    runs are separate physical shelters. A zone means the standard route is in
    the context of the same shelter reference over that route-axis interval.
    """
    if "near_shelter" not in route_1m.columns:
        return pd.DataFrame(
            columns=[
                "shelter_context_zone_id",
                "context_zone_start_m",
                "context_zone_end_m",
                "context_zone_marker_m",
                "route_occurrence_role",
                "raw_proximity_run_count",
                "raw_proximity_runs_m",
                "nearest_feature_distance_m",
                "marker_method",
                "interpretation_boundary",
            ]
        )

    distance_col = "dist_shelter_m"
    raw_runs: list[dict[str, object]] = []
    mask = truthy(route_1m["near_shelter"])
    for run_index, (start_idx, end_idx) in enumerate(contiguous_true_runs(mask), start=1):
        segment = route_1m.iloc[start_idx : end_idx + 1]
        if distance_col in segment.columns:
            nearest_distance = numeric(segment[distance_col])
        else:
            nearest_distance = pd.Series(np.nan, index=segment.index)
        if nearest_distance.notna().any():
            marker_index = nearest_distance.idxmin()
            minimum_distance = float(nearest_distance.loc[marker_index])
        else:
            marker_index = segment.index[len(segment) // 2]
            minimum_distance = np.nan
        raw_runs.append(
            {
                "raw_run_index": run_index,
                "raw_start_m": int(segment["route_distance_m"].min()),
                "raw_end_m": int(segment["route_distance_m"].max()),
                "raw_marker_m": int(route_1m.loc[marker_index, "route_distance_m"]),
                "nearest_feature_distance_m": minimum_distance,
            }
        )

    zones: list[dict[str, object]] = []
    for raw in raw_runs:
        if zones and raw["raw_start_m"] - zones[-1]["context_zone_end_m"] <= merge_gap_m:
            zone = zones[-1]
            zone["context_zone_end_m"] = raw["raw_end_m"]
            zone["raw_proximity_run_count"] += 1
            zone["raw_proximity_runs"].append(
                f"{raw['raw_start_m']}-{raw['raw_end_m']}"
            )
            if (
                pd.notna(raw["nearest_feature_distance_m"])
                and (
                    pd.isna(zone["nearest_feature_distance_m"])
                    or raw["nearest_feature_distance_m"] < zone["nearest_feature_distance_m"]
                )
            ):
                zone["context_zone_marker_m"] = raw["raw_marker_m"]
                zone["nearest_feature_distance_m"] = raw["nearest_feature_distance_m"]
        else:
            zones.append(
                {
                    "context_zone_start_m": raw["raw_start_m"],
                    "context_zone_end_m": raw["raw_end_m"],
                    "context_zone_marker_m": raw["raw_marker_m"],
                    "raw_proximity_run_count": 1,
                    "raw_proximity_runs": [f"{raw['raw_start_m']}-{raw['raw_end_m']}"],
                    "nearest_feature_distance_m": raw["nearest_feature_distance_m"],
                }
            )

    route_mid = float(route_1m["route_distance_m"].max()) / 2.0 if len(route_1m) else 0.0
    records: list[dict[str, object]] = []
    for zone_index, zone in enumerate(zones, start=1):
        marker_m = int(zone["context_zone_marker_m"])
        occurrence_role = (
            "OUTBOUND_SHELTER_CONTEXT_ZONE"
            if marker_m < route_mid
            else "RETURN_SHELTER_CONTEXT_ZONE"
        )
        records.append(
            {
                "shelter_context_zone_id": f"SHELTER_CONTEXT_ZONE_{zone_index}",
                "event_type": "shelter",
                "event_label": "遮蔽設施情境區",
                "route_distance_m": marker_m,
                "exposure_run_start_m": int(zone["context_zone_start_m"]),
                "exposure_run_end_m": int(zone["context_zone_end_m"]),
                "context_zone_start_m": int(zone["context_zone_start_m"]),
                "context_zone_end_m": int(zone["context_zone_end_m"]),
                "context_zone_marker_m": marker_m,
                "route_occurrence_role": occurrence_role,
                "raw_proximity_run_count": int(zone["raw_proximity_run_count"]),
                "raw_proximity_runs_m": "|".join(zone["raw_proximity_runs"]),
                "nearest_feature_distance_m": zone["nearest_feature_distance_m"],
                "marker_method": (
                    "minimum nearest-feature distance within merged shelter context zone; "
                    "zone merged from adjacent near_shelter proximity runs"
                ),
                "interpretation_boundary": (
                    "Report-level shelter context zone derived from OSM proximity. "
                    "It is not a physical facility count, not the first visible point, "
                    "and not proof of facility use."
                ),
            }
        )
    return pd.DataFrame.from_records(records)


def build_route_events(
    route_1m: pd.DataFrame,
    shelter_context_zones: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Collapse route-proximity event runs to markers; shelter uses context zones."""
    records: list[dict[str, object]] = []
    if shelter_context_zones is None:
        shelter_context_zones = build_shelter_context_zones(route_1m)

    for event_type, label, near_col, distance_col, _ in EVENT_SPECS:
        if event_type == "shelter":
            if not shelter_context_zones.empty:
                records.extend(shelter_context_zones.to_dict("records"))
            continue
        if near_col not in route_1m.columns:
            continue
        mask = truthy(route_1m[near_col])
        for start_idx, end_idx in contiguous_true_runs(mask):
            segment = route_1m.iloc[start_idx : end_idx + 1]
            if distance_col in segment.columns:
                nearest_distance = numeric(segment[distance_col])
            else:
                nearest_distance = pd.Series(np.nan, index=segment.index)

            if nearest_distance.notna().any():
                marker_index = nearest_distance.idxmin()
                minimum_distance = float(nearest_distance.loc[marker_index])
            else:
                marker_index = segment.index[len(segment) // 2]
                minimum_distance = np.nan

            records.append(
                {
                    "event_type": event_type,
                    "event_label": label,
                    "route_distance_m": int(route_1m.loc[marker_index, "route_distance_m"]),
                    "exposure_run_start_m": int(segment["route_distance_m"].min()),
                    "exposure_run_end_m": int(segment["route_distance_m"].max()),
                    "nearest_feature_distance_m": minimum_distance,
                    "marker_method": "minimum nearest-feature distance within contiguous near_* exposure run",
                    "interpretation_boundary": "OSM proximity exposure marker; not proof of facility use.",
                }
            )
    return pd.DataFrame.from_records(records)

def filter_behavior_activity(behavior: pd.DataFrame, activity_id: str, source_name: Path | str) -> pd.DataFrame:
    require_columns(behavior, ["activity_id_short"], source_name)
    filtered = behavior[behavior["activity_id_short"].astype(str) == str(activity_id)].copy()
    if filtered.empty:
        available = sorted(behavior["activity_id_short"].dropna().astype(str).unique())
        raise ValueError(f"activity_id_short={activity_id!r} not found. Available: {available}")
    return filtered


def aggregate_single_activity_behavior(behavior_one: pd.DataFrame, bin_m: int, source_name: Path | str) -> pd.DataFrame:
    """Aggregate selected activity windows to requested distance grain.

    This remains a single-activity summary. It does not compute cross-activity IQR.
    """
    required = [
        "activity_id_short",
        "route_distance_window_start_m",
        "route_distance_window_end_m",
        "route_phase",
        "point_count",
        "speed_mps_median",
        "low_speed_ratio",
        "stopped_ratio",
        "heart_rate_bpm_median",
    ]
    require_columns(behavior_one, required, source_name)

    data = behavior_one.copy()
    numeric_columns = [
        "route_distance_window_start_m",
        "route_distance_window_end_m",
        "point_count",
        "speed_mps_median",
        "speed_mps_p25",
        "speed_mps_p75",
        "low_speed_ratio",
        "stopped_ratio",
        "heart_rate_bpm_median",
        "heart_rate_bpm_p75",
        "heart_rate_bpm_p90",
        "calibrated_slope_pct_median",
        "ib2_terrain_evidence_median",
        "ib2_effort_evidence_median",
        "ib2_exposure_evidence_median",
        "near_steps_ratio",
        "near_guidepost_ratio",
        "near_shelter_ratio",
        "near_waterway_ratio",
        "near_cliff_ratio",
        "near_road_ratio",
    ]
    for column in numeric_columns:
        if column in data.columns:
            data[column] = numeric(data[column])

    data = data.dropna(subset=["route_distance_window_start_m"]).copy()
    if data.empty:
        raise ValueError("selected activity has no valid route_distance_window_start_m")

    data["behavior_window_start_m"] = (
        np.floor(data["route_distance_window_start_m"] / bin_m) * bin_m
    ).astype(int)

    def q(q_value: float):
        return lambda values: values.quantile(q_value)

    agg_spec = {
        "activity_id_short": ("activity_id_short", mode_text),
        "behavior_window_end_m": ("behavior_window_start_m", lambda values: int(values.iloc[0] + bin_m)),
        "source_window_row_count": ("activity_id_short", "size"),
        "point_count": ("point_count", "sum"),
        "route_phase": ("route_phase", mode_text),
        "speed_mps_median": ("speed_mps_median", "median"),
        "speed_mps_p25": ("speed_mps_median", q(0.25)),
        "speed_mps_p75": ("speed_mps_median", q(0.75)),
        "low_speed_ratio_mean": ("low_speed_ratio", "mean"),
        "low_speed_ratio_median": ("low_speed_ratio", "median"),
        "stopped_ratio_mean": ("stopped_ratio", "mean"),
        "stopped_ratio_median": ("stopped_ratio", "median"),
        "heart_rate_bpm_median": ("heart_rate_bpm_median", "median"),
        "heart_rate_bpm_p25": ("heart_rate_bpm_median", q(0.25)),
        "heart_rate_bpm_p75": ("heart_rate_bpm_median", q(0.75)),
    }

    optional_specs = {
        "route_load_context_band": ("route_load_context_band", mode_text),
        "calibrated_slope_pct_median_behavior": ("calibrated_slope_pct_median", "median"),
        "ib2_terrain_evidence_median": ("ib2_terrain_evidence_median", "median"),
        "ib2_effort_evidence_median": ("ib2_effort_evidence_median", "median"),
        "ib2_exposure_evidence_median": ("ib2_exposure_evidence_median", "median"),
        "near_steps_ratio": ("near_steps_ratio", "mean"),
        "near_guidepost_ratio": ("near_guidepost_ratio", "mean"),
        "near_shelter_ratio": ("near_shelter_ratio", "mean"),
        "near_waterway_ratio": ("near_waterway_ratio", "mean"),
        "near_cliff_ratio": ("near_cliff_ratio", "mean"),
        "near_road_ratio": ("near_road_ratio", "mean"),
        "osm_exposure_types": ("osm_exposure_types", mode_text),
        "window_qa_flags": ("window_qa_flags", mode_text),
        "interpretation_boundary": ("interpretation_boundary", mode_text),
    }
    for out_col, (src_col, func) in optional_specs.items():
        if src_col in data.columns:
            agg_spec[out_col] = (src_col, func)

    grouped = data.groupby("behavior_window_start_m", as_index=False).agg(**agg_spec)
    grouped["behavior_grain_note"] = (
        f"{bin_m}m single-activity behavior window summary; not a 1m instantaneous value"
    )
    grouped["activity_count"] = 1
    return grouped.sort_values("behavior_window_start_m")


def build_rest_candidates_from_single_activity(
    behavior_summary: pd.DataFrame,
    stopped_threshold: float,
    low_speed_threshold: float,
) -> pd.DataFrame:
    records: list[dict[str, object]] = []

    for _, row in behavior_summary.iterrows():
        stopped = row.get("stopped_ratio_mean", np.nan)
        low = row.get("low_speed_ratio_mean", np.nan)
        try:
            stopped = float(stopped)
        except Exception:
            stopped = np.nan
        try:
            low = float(low)
        except Exception:
            low = np.nan

        if (pd.notna(stopped) and stopped >= stopped_threshold) or (
            pd.notna(low) and low >= low_speed_threshold
        ):
            start_m = int(row["behavior_window_start_m"])
            end_m = int(row["behavior_window_end_m"])
            records.append(
                {
                    "event_type": "rest_candidate",
                    "event_label": "停留候選",
                    "route_distance_m": int((start_m + end_m) / 2),
                    "exposure_run_start_m": start_m,
                    "exposure_run_end_m": end_m,
                    "nearest_feature_distance_m": np.nan,
                    "marker_method": (
                        f"single activity stopped_ratio_mean >= {stopped_threshold:.2f} "
                        f"or low_speed_ratio_mean >= {low_speed_threshold:.2f}"
                    ),
                    "interpretation_boundary": "Single-activity stop/slow candidate only; not a confirmed rest point.",
                }
            )

    return pd.DataFrame.from_records(records)


def combine_events(route_events: pd.DataFrame, rest_events: pd.DataFrame) -> pd.DataFrame:
    if route_events.empty and rest_events.empty:
        return pd.DataFrame(
            columns=[
                "event_type",
                "event_label",
                "route_distance_m",
                "exposure_run_start_m",
                "exposure_run_end_m",
                "nearest_feature_distance_m",
                "marker_method",
                "interpretation_boundary",
            ]
        )
    if route_events.empty:
        return rest_events.copy()
    if rest_events.empty:
        return route_events.copy()
    return pd.concat([route_events, rest_events], ignore_index=True)


def draw_load_background(axis, behavior: pd.DataFrame) -> None:
    """Suppress route_load_context_band background for the publication-style figure.

    v2.1/v2.2 used light load-band backgrounds in the behavior panels.  For the
    Chapter 6.5 presentation figure, those vertical bands visually compete with
    the shelter context zone, so v2.2.7 + IB3D event bands leaves behavior panels clean and keeps
    context shading in the spatial panel only.
    """
    return


def resolve_ib3d_event_overlay_csv(root: Path, activity_id: str) -> Path:
    return resolve_path(
        root,
        str(
            Path(DEFAULT_IB3D_EVENT_OVERLAY_ROOT)
            / f"activity_{sanitize(activity_id)}_ib3d_event_route_window_overlay.csv"
        ),
    )


def build_ib3d_event_markers(root: Path, activity_id: str) -> pd.DataFrame:
    """Build report-level IB3D event markers for the v2.2.3 spatial panel.

    The bridge CSV is already 50 m route-window evidence. This function only
    converts positive event windows into marker points at the route-window
    midpoint. Terminal artifacts are intentionally not plotted on the main
    figure.
    """
    overlay_csv = resolve_ib3d_event_overlay_csv(root, activity_id)
    if not overlay_csv.exists():
        return pd.DataFrame(
            columns=[
                "event_type",
                "event_label",
                "route_distance_m",
                "route_window_start_m",
                "route_window_end_m",
                "marker",
                "color",
                "y_position",
                "marker_size",
                "source_csv",
                "interpretation_boundary",
            ]
        )

    overlay = read_csv(overlay_csv)
    overlay.columns = [str(c).strip() for c in overlay.columns]

    required = [
        "activity_id_short",
        "route_window_start_m",
        "route_window_end_m",
        "event_overlay_status",
    ]
    missing = [c for c in required if c not in overlay.columns]
    if missing:
        raise ValueError(f"IB3D event overlay CSV missing columns: {missing}")

    for col in [
        "route_window_start_m",
        "route_window_end_m",
        "high_hr_recovery_stop_count",
        "high_hr_recovery_stop_ratio",
        "short_pause_count",
        "off_route_rest_ratio",
        "terminal_artifact_ratio",
    ]:
        if col in overlay.columns:
            overlay[col] = numeric(overlay[col])

    ready_statuses = {
        "ROUTE_WINDOW_OVERLAY_READY",
        "ROUTE_WINDOW_OVERLAY_READY_WITH_EVENT_REVIEW",
    }

    overlay = overlay[
        overlay["activity_id_short"].astype(str).eq(str(activity_id))
        & overlay["event_overlay_status"].astype(str).isin(ready_statuses)
    ].copy()

    if overlay.empty:
        return pd.DataFrame()

    records: list[dict[str, object]] = []
    for spec in IB3D_EVENT_OVERLAY_SPECS:
        count_col = spec.get("count_col", "")
        ratio_col = spec.get("ratio_col", "")

        if count_col and count_col in overlay.columns:
            sub = overlay[overlay[count_col].fillna(0) > 0].copy()
        elif ratio_col and ratio_col in overlay.columns:
            sub = overlay[overlay[ratio_col].fillna(0) > 0].copy()
        else:
            continue

        for _, row in sub.iterrows():
            start_m = float(row["route_window_start_m"])
            end_m = float(row["route_window_end_m"])
            records.append(
                {
                    "event_type": spec["event_type"],
                    "event_label": spec["label"],
                    "route_distance_m": int(round((start_m + end_m) / 2.0)),
                    "route_window_start_m": start_m,
                    "route_window_end_m": end_m,
                    "marker": spec["marker"],
                    "color": spec["color"],
                    "y_position": spec["y"],
                    "marker_size": spec["size"],
                    "band_color": spec["band_color"],
                    "band_alpha": spec["band_alpha"],
                    "source_csv": str(overlay_csv),
                    "interpretation_boundary": IB3D_EVENT_OVERLAY_BOUNDARY,
                }
            )

    return pd.DataFrame.from_records(records)



def draw_ib3d_event_backgrounds(
    axes: list,
    ib3d_event_markers: pd.DataFrame | None,
) -> None:
    """Draw IB3D route-window event background bands on behavior panels.

    Red = high-HR recovery stop.
    Gray = short pause.
    Purple = off-route rest.
    Terminal artifacts are intentionally not shown on the main figure.
    """
    if ib3d_event_markers is None or ib3d_event_markers.empty:
        return

    for _, row in ib3d_event_markers.iterrows():
        start_m = row.get("route_window_start_m", np.nan)
        end_m = row.get("route_window_end_m", np.nan)
        if pd.isna(start_m) or pd.isna(end_m):
            continue

        x0 = float(start_m) / 1000.0
        x1 = float(end_m) / 1000.0
        color = str(row.get("band_color", "#64748B"))
        alpha = float(row.get("band_alpha", 0.10))
        event_type = str(row.get("event_type", ""))
        if event_type == "short_pause":
            alpha = max(alpha, 0.18)

        # Keep the surface ribbon readable. Apply bands to slope / HR / speed / ratio panels.
        for axis in axes[1:]:
            axis.axvspan(
                x0,
                x1,
                color=color,
                alpha=alpha,
                linewidth=0,
                zorder=0,
            )


def plot_activity_figure(
    route_1m: pd.DataFrame,
    events: pd.DataFrame,
    behavior: pd.DataFrame,
    shelter_context_zones: pd.DataFrame,
    activity_id: str,
    output_png: Path,
    bin_m: int,
    speed_plot_cap_mps: float,
    ib3d_event_markers: pd.DataFrame | None = None,
) -> None:
    route_x = route_1m["route_distance_m"].to_numpy(dtype=float) / 1000.0
    behavior_x = (
        (behavior["behavior_window_start_m"] + behavior["behavior_window_end_m"])
        / 2.0
        / 1000.0
    ).to_numpy(dtype=float)

    surface_codes = route_1m["surface_type"].map(
        {name: index for index, name in enumerate(SURFACE_ORDER)}
    ).fillna(len(SURFACE_ORDER) - 1).to_numpy(dtype=float)

    cmap = ListedColormap([SURFACE_COLORS[name] for name in SURFACE_ORDER])
    norm = BoundaryNorm(np.arange(-0.5, len(SURFACE_ORDER) + 0.5), cmap.N)

    fig = plt.figure(figsize=(13.2, 9.8))
    grid = fig.add_gridspec(
        5,
        1,
        height_ratios=[1.0, 1.2, 1.2, 1.2, 1.1],
        hspace=0.13,
    )
    axes = [fig.add_subplot(grid[index, 0]) for index in range(5)]
    for axis in axes[1:]:
        axis.sharex(axes[0])

    draw_ib3d_event_backgrounds(axes, ib3d_event_markers)

    # Panel 1: surface + event markers.
    spatial_ax = axes[0]
    spatial_ax.imshow(
        surface_codes.reshape(1, -1),
        aspect="auto",
        cmap=cmap,
        norm=norm,
        extent=[route_x.min(), route_x.max(), 0.02, 0.30],
        interpolation="nearest",
    )
    if shelter_context_zones is not None and not shelter_context_zones.empty:
        for _, zone in shelter_context_zones.iterrows():
            x0 = float(zone["context_zone_start_m"]) / 1000.0
            x1 = float(zone["context_zone_end_m"]) / 1000.0
            spatial_ax.axvspan(
                x0,
                x1,
                ymin=0.30,
                ymax=0.56,
                color=EVENT_COLORS["shelter"],
                alpha=0.18,
                linewidth=0,
                zorder=1,
            )
            spatial_ax.hlines(
                0.43,
                x0,
                x1,
                colors=EVENT_COLORS["shelter"],
                linewidth=3.2,
                alpha=0.55,
                zorder=2,
            )
    spatial_ax.set_ylim(0, 1.42)
    spatial_ax.set_yticks([0.16])
    spatial_ax.set_yticklabels(["路面／路徑"], fontsize=8)

    surface_legend = spatial_ax.legend(
        handles=[
            Patch(facecolor=SURFACE_COLORS[name], label=SURFACE_LABELS[name])
            for name in SURFACE_ORDER
        ],
        loc="upper center",
        bbox_to_anchor=(0.42, 1.64),
        ncol=5,
        frameon=False,
        fontsize=8,
        title="路面／路徑型態（1 m route axis）",
        title_fontsize=8,
    )
    spatial_ax.add_artist(surface_legend)

    # Keep the publication-style panel focused.  Guidepost and rest-candidate
    # markers remain in the CSV/report but are not plotted by default because
    # they visually compete with shelter context zones.
    event_types = ["shelter", "peak", "trailhead", "waterway"]
    event_labels = {spec[0]: spec[1] for spec in EVENT_SPECS}
    event_labels["shelter"] = "遮蔽設施參考點"
    markers = {spec[0]: spec[4] for spec in EVENT_SPECS}
    y_positions = {
        "shelter": 0.60,
        "peak": 0.78,
        "trailhead": 0.96,
        "waterway": 1.14,
    }

    event_handles = []
    for event_type in event_types:
        event_handles.append(
            Line2D(
                [],
                [],
                marker=markers[event_type],
                color=EVENT_COLORS[event_type],
                linestyle="None",
                markersize=7 if event_type != "peak" else 9,
                label=event_labels[event_type],
            )
        )
        subset = events[events["event_type"] == event_type] if not events.empty else pd.DataFrame()
        if subset.empty:
            continue
        spatial_ax.scatter(
            subset["route_distance_m"] / 1000.0,
            [y_positions[event_type]] * len(subset),
            marker=markers[event_type],
            color=EVENT_COLORS[event_type],
            s=26 if event_type == "shelter" else (75 if event_type == "peak" else 42),
            zorder=3,
        )

    # Optional IB3D event overlay markers from elapsed-time events bridged to route windows.
    if ib3d_event_markers is not None and not ib3d_event_markers.empty:
        plotted_ib3d_types: set[str] = set()
        for _, marker_row in ib3d_event_markers.iterrows():
            event_type = str(marker_row.get("event_type", ""))
            plotted_ib3d_types.add(event_type)
            spatial_ax.scatter(
                float(marker_row["route_distance_m"]) / 1000.0,
                float(marker_row["y_position"]),
                marker=str(marker_row["marker"]),
                color=str(marker_row["color"]),
                s=float(marker_row["marker_size"]),
                edgecolors="white",
                linewidths=0.7,
                zorder=5,
            )

        for _, marker_row in ib3d_event_markers.drop_duplicates("event_type").iterrows():
            event_handles.append(
                Patch(
                    facecolor=str(marker_row.get("band_color", marker_row["color"])),
                    alpha=0.28,
                    label=str(marker_row["event_label"]),
                )
            )

    if shelter_context_zones is not None and not shelter_context_zones.empty:
        event_handles.insert(
            0,
            Patch(
                facecolor=EVENT_COLORS["shelter"],
                alpha=0.20,
                label="遮蔽設施情境區帶（整段）",
            ),
        )
    spatial_ax.legend(
        handles=event_handles,
        loc="upper right",
        bbox_to_anchor=(1.0, 1.64),
        ncol=3,
        frameon=False,
        fontsize=7.5,
        title="主要設施／情境區帶",
        title_fontsize=8,
    )
    spatial_ax.grid(True, axis="x", alpha=0.18)

    # Panel 2: route slope.
    slope_ax = axes[1]
    slope = numeric(route_1m["slope_pct_plot"]).to_numpy(dtype=float)
    slope_ax.plot(route_x, slope, color="#7A5195", linewidth=1.0)
    slope_ax.axhline(0, color="#555555", linewidth=0.7)
    slope_ax.fill_between(route_x, 0, slope, where=slope >= 0, color="#EF8354", alpha=0.18)
    slope_ax.fill_between(route_x, 0, slope, where=slope < 0, color="#4C78A8", alpha=0.16)
    slope_ax.set_ylabel("路線坡度\n(%)")
    slope_ax.grid(True, alpha=0.22)

    # Panel 3: heart rate.
    hr_ax = axes[2]
    draw_load_background(hr_ax, behavior)
    hr_ax.plot(
        behavior_x,
        behavior["heart_rate_bpm_median"],
        color="#A4133C",
        linewidth=1.8,
        marker="o",
        markersize=3.5,
        label="心率中位數",
    )
    # For a selected activity, p25/p75 are within bins, not cross-activity IQR.
    if "heart_rate_bpm_p25" in behavior.columns and "heart_rate_bpm_p75" in behavior.columns:
        hr_ax.fill_between(
            behavior_x,
            behavior["heart_rate_bpm_p25"].to_numpy(dtype=float),
            behavior["heart_rate_bpm_p75"].to_numpy(dtype=float),
            color="#D62728",
            alpha=0.10,
            label="視窗內分位範圍",
        )
    hr_ax.set_ylabel("心率\n(bpm)")
    hr_ax.legend(loc="upper right", frameon=False, fontsize=8)
    hr_ax.grid(True, alpha=0.22)

    # Panel 4: speed.
    speed_ax = axes[3]
    draw_load_background(speed_ax, behavior)

    speed_raw = numeric(behavior["speed_mps_median"]).to_numpy(dtype=float)
    speed_clipped = np.minimum(speed_raw, speed_plot_cap_mps)
    clipped_count = int(np.isfinite(speed_raw).sum() - np.isfinite(speed_clipped).sum() + np.sum(speed_raw > speed_plot_cap_mps))

    speed_ax.plot(
        behavior_x,
        speed_clipped,
        color="#1F4E79",
        linewidth=1.8,
        marker="o",
        markersize=3.5,
        label="速度中位數（圖面截頂）" if clipped_count > 0 else "速度中位數",
    )
    if "speed_mps_p25" in behavior.columns and "speed_mps_p75" in behavior.columns:
        speed_p25 = np.minimum(behavior["speed_mps_p25"].to_numpy(dtype=float), speed_plot_cap_mps)
        speed_p75 = np.minimum(behavior["speed_mps_p75"].to_numpy(dtype=float), speed_plot_cap_mps)
        speed_ax.fill_between(
            behavior_x,
            speed_p25,
            speed_p75,
            color="#4C78A8",
            alpha=0.14,
            label="視窗內分位範圍",
        )
    speed_ax.axhline(
        LOW_SPEED_THRESHOLD_MPS,
        color="#B45309",
        linestyle="--",
        linewidth=1.15,
        alpha=0.9,
        label=f"低速閾值 {LOW_SPEED_THRESHOLD_MPS:.1f} m/s",
        zorder=2,
    )
    speed_ax.set_ylim(bottom=0, top=max(speed_plot_cap_mps * 1.08, 0.5))
    speed_ax.set_ylabel("速度\n(m/s)")
    speed_ax.legend(loc="upper right", frameon=False, fontsize=8)
    speed_ax.grid(True, alpha=0.22)

    # Panel 5: low / stop ratios.
    ratio_ax = axes[4]
    draw_load_background(ratio_ax, behavior)
    ratio_ax.plot(
        behavior_x,
        behavior["low_speed_ratio_mean"],
        color="#E69F00",
        linewidth=1.5,
        marker="o",
        markersize=3.5,
        label="低速點比例",
    )
    ratio_ax.plot(
        behavior_x,
        behavior["stopped_ratio_mean"],
        color="#D62728",
        linewidth=1.4,
        linestyle="--",
        marker="s",
        markersize=3.2,
        label="停止點比例",
    )
    ratio_ax.set_ylim(bottom=0)
    ratio_ax.set_ylabel("低速／停止\n點比例")
    ratio_ax.set_xlabel("標準路線距離（km）")
    ratio_ax.legend(loc="upper right", frameon=False, fontsize=8)
    ratio_ax.grid(True, alpha=0.22)

    for axis in axes[:-1]:
        axis.tick_params(labelbottom=False)
    for axis in axes:
        axis.set_xlim(route_x.min(), route_x.max())

    fig.suptitle(
        "6.5 單筆活動：路線型態與活動行為描述性剖面\n"
        f"activity_id_short={activity_id}；路面 1 m route axis；行為 {bin_m} m 視窗",
        fontsize=14,
        fontweight="bold",
        y=0.987,
    )

    phase_values = sorted(set(behavior["route_phase"].dropna().astype(str))) if "route_phase" in behavior.columns else []
    phase_note = ""
    if len(phase_values) == 1 and phase_values[0].upper() == "UNKNOWN":
        phase_note = "若 route_phase=UNKNOWN，不可解讀為上行／下行差異。"

    note = (
        "註：本圖為單筆活動描述性剖面；心率、速度、低速／停止比例為 50 m 視窗摘要，非每 1 m 即時值。"
        f"速度圖面 cap={speed_plot_cap_mps:g} m/s，原值保留於 CSV。"
        f"速度圖之 {LOW_SPEED_THRESHOLD_MPS:.1f} m/s 虛線為低速判讀參考線；此閾值僅供視覺對照，不重新計算行為特徵。"
        f"{phase_note}"
        "遮蔽設施情境區表示標準路線接近同一 OSM shelter reference 的區段；"
        "marker 僅為區帶內最接近 OSM node 的參考點，不代表多個實體設施或實際使用。"
        "本圖不產生能力分數、THCI 分數或最終風險分數。"
    )
    fig.text(0.075, 0.012, note, fontsize=8.2, va="bottom")
    fig.subplots_adjust(left=0.095, right=0.985, top=0.855, bottom=0.09)
    fig.savefig(output_png, dpi=260)
    plt.close(fig)


def build_profile_export(
    route_1m: pd.DataFrame,
    events: pd.DataFrame,
    behavior: pd.DataFrame,
    shelter_context_zones: pd.DataFrame,
    bin_m: int,
    activity_id: str,
) -> pd.DataFrame:
    profile = route_1m.copy()
    profile["activity_id_short"] = activity_id
    profile["behavior_window_start_m"] = (
        np.floor(profile["route_distance_m"] / bin_m) * bin_m
    ).astype(int)
    profile = profile.merge(
        behavior,
        on="behavior_window_start_m",
        how="left",
        validate="many_to_one",
    )

    if events.empty:
        profile["event_types_at_marker_m"] = ""
        profile["event_labels_at_marker_m"] = ""
    else:
        event_summary = events.groupby("route_distance_m", as_index=False).agg(
            event_types_at_marker_m=("event_type", lambda values: "|".join(sorted(set(values)))),
            event_labels_at_marker_m=("event_label", lambda values: "|".join(sorted(set(values)))),
        )
        profile = profile.merge(event_summary, on="route_distance_m", how="left")
        profile["event_types_at_marker_m"] = profile["event_types_at_marker_m"].fillna("")
        profile["event_labels_at_marker_m"] = profile["event_labels_at_marker_m"].fillna("")

    profile["shelter_context_zone_id"] = ""
    if shelter_context_zones is not None and not shelter_context_zones.empty:
        for _, zone in shelter_context_zones.iterrows():
            mask = (
                profile["route_distance_m"].ge(int(zone["context_zone_start_m"]))
                & profile["route_distance_m"].le(int(zone["context_zone_end_m"]))
            )
            profile.loc[mask, "shelter_context_zone_id"] = str(zone["shelter_context_zone_id"])

    profile["profile_interpretation_boundary"] = (
        "Surface and slope are route-axis evidence; behavior is a selected-activity window summary; "
        "event markers and shelter context zones are proximity/candidate evidence only."
    )
    return profile


def build_audit(
    route_csv: Path,
    behavior_csv: Path,
    activity_id: str,
    route_1m: pd.DataFrame,
    behavior_raw: pd.DataFrame,
    behavior_one: pd.DataFrame,
    behavior_summary: pd.DataFrame,
    events: pd.DataFrame,
    shelter_context_zones: pd.DataFrame,
    bin_m: int,
) -> pd.DataFrame:
    generated_columns = set(route_1m.columns) | set(behavior_summary.columns) | set(events.columns)
    prohibited_generated = sorted(token for token in PROHIBITED_OUTPUT_TOKENS if token in generated_columns)

    phase_unknown_count = (
        int(behavior_one["route_phase"].fillna("").astype(str).str.upper().eq("UNKNOWN").sum())
        if "route_phase" in behavior_one.columns
        else 0
    )

    source_offset = (route_1m["route_distance_m"] - route_1m["source_route_distance_m"]).abs()
    audit = {
        "route_input_csv": str(route_csv),
        "behavior_input_csv": str(behavior_csv),
        "activity_id_short": activity_id,
        "available_activity_count_in_behavior_csv": int(behavior_raw["activity_id_short"].nunique()),
        "selected_activity_input_row_count": len(behavior_one),
        "selected_activity_behavior_summary_row_count": len(behavior_summary),
        "behavior_bin_m": bin_m,
        "low_speed_threshold_mps": LOW_SPEED_THRESHOLD_MPS,
        "low_speed_threshold_visual_only": True,
        "ib3d_short_pause_band_alpha": 0.18,
        "route_1m_row_count": len(route_1m),
        "route_distance_max_m": int(route_1m["route_distance_m"].max()),
        "surface_unknown_other_count": int(route_1m["surface_type"].eq("unknown_other").sum()),
        "route_1m_source_match_missing_count": int(route_1m["source_route_distance_m"].isna().sum()),
        "route_1m_source_match_max_offset_m": float(source_offset.max()) if source_offset.notna().any() else np.nan,
        "slope_source": mode_text(route_1m["slope_source"]) if "slope_source" in route_1m.columns else "",
        "slope_missing_count": int(route_1m["slope_pct_plot"].isna().sum()),
        "route_phase_unknown_row_count_for_selected_activity": phase_unknown_count,
        "event_marker_count": len(events),
        "shelter_context_zone_count": len(shelter_context_zones) if shelter_context_zones is not None else 0,
        "shelter_raw_proximity_run_count": int(shelter_context_zones["raw_proximity_run_count"].sum()) if shelter_context_zones is not None and not shelter_context_zones.empty else 0,
        "rest_candidate_count": int(events["event_type"].eq("rest_candidate").sum()) if not events.empty else 0,
        "weather_zero_fill_performed_count": 0,
        "legacy_gain_field_used_count": 0,
        "score_rank_class_generated_count": len(prohibited_generated),
        "prohibited_generated_columns": "|".join(prohibited_generated),
        "audit_conclusion": (
            "PASS_CH6_5_SINGLE_ACTIVITY_SURFACE_PROFILE_V2_2_5_SPEED_THRESHOLD_PAUSE_FOCUS"
            if not prohibited_generated
            and len(behavior_summary) > 0
            and route_1m["slope_pct_plot"].notna().any()
            else "REVIEW_REQUIRED"
        ),
    }
    return pd.DataFrame([audit])


def write_report(
    path: Path,
    route_csv: Path,
    behavior_csv: Path,
    activity_id: str,
    route_1m: pd.DataFrame,
    events: pd.DataFrame,
    behavior: pd.DataFrame,
    shelter_context_zones: pd.DataFrame,
    audit: pd.DataFrame,
) -> None:
    surface_counts = route_1m["surface_type"].value_counts().reindex(SURFACE_ORDER, fill_value=0)
    event_counts = events["event_type"].value_counts() if not events.empty else pd.Series(dtype=int)

    lines = [
        f"# Chapter 6.5 single-activity route surface and behavior profile v2.2.7 speed threshold pause focus: {activity_id}",
        "",
        "## Inputs",
        "",
        f"- canonical route evidence: `{route_csv}`",
        f"- behavior windows: `{behavior_csv}`",
        f"- selected activity_id_short: `{activity_id}`",
        "",
        "## What this version fixes",
        "",
        "- Uses true route-axis 1 m surface / path ribbon from the canonical route evidence, where available.",
        "- Filters behavior data to one `activity_id_short` before aggregation.",
        "- Keeps slope next to heart rate, then speed, then low/stop ratios.",
        "- Marks route events and single-activity stop/slow candidates in the same spatial background panel.",
        "- Does not compute cross-activity IQR for the selected-activity figure.",
        "",
        "## Surface distribution",
        "",
    ]
    lines.extend(f"- {name}: {int(surface_counts[name])} m" for name in SURFACE_ORDER)

    lines.extend(["", "## Event markers", ""])
    if event_counts.empty:
        lines.append("- none")
    else:
        lines.extend(f"- {name}: {int(count)}" for name, count in event_counts.items())

    lines.extend(["", "## Shelter context zones", ""])
    if shelter_context_zones is None or shelter_context_zones.empty:
        lines.append("- none")
    else:
        lines.append(f"- shelter_context_zone_count: {len(shelter_context_zones)}")
        lines.append(f"- raw_near_shelter_run_count: {int(shelter_context_zones['raw_proximity_run_count'].sum())}")
        lines.append("- interpretation: shelter context zones merge adjacent OSM near_shelter proximity runs for presentation; they do not represent physical facility counts, first-visible points, or confirmed use.")
        lines.append("")
        lines.append("| zone_id | role | zone_m | marker_m | raw_runs_m |")
        lines.append("|---|---|---:|---:|---|")
        for _, zone in shelter_context_zones.iterrows():
            lines.append(
                f"| {zone['shelter_context_zone_id']} | {zone['route_occurrence_role']} "
                f"| {int(zone['context_zone_start_m'])}-{int(zone['context_zone_end_m'])} "
                f"| {int(zone['context_zone_marker_m'])} | {zone['raw_proximity_runs_m']} |"
            )

    lines.extend(
        [
            "",
            "## Behavior summary",
            "",
            f"- rows: {len(behavior)}",
            f"- route phase values: {', '.join(sorted(set(behavior['route_phase'].astype(str)))) if 'route_phase' in behavior.columns else ''}",
            "",
            "## Boundaries",
            "",
            "- This figure is descriptive only.",
            "- Surface type is a route-axis spatial distribution.",
            "- Behavior indicators are selected-activity window summaries, not instantaneous 1 m observations.",
            f"- The {LOW_SPEED_THRESHOLD_MPS:.1f} m/s dashed line in the speed panel is visual reference only and does not recalculate behavior features.",
            "- `route_phase=UNKNOWN` cannot support ascent/descent comparison.",
            "- Weather remains activity-level background context, not pointwise weather.",
            "- OSM proximity is exposure evidence, not proof of facility use.",
            "- Shelter context zones are merged report-level proximity zones; they are not physical shelter counts or first-visible points.",
            "- Rest candidate is a stop/slow candidate, not a confirmed rest point.",
            "- No ability score, rank, class, THCI, radar, or final hiking risk score is generated.",
            "",
            "## Audit",
            "",
            f"- conclusion: `{audit.iloc[0]['audit_conclusion']}`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_one_activity(
    root: Path,
    route_csv: Path,
    behavior_csv: Path,
    route_raw: pd.DataFrame,
    behavior_raw: pd.DataFrame,
    activity_id: str,
    outdir: Path,
    bin_m: int,
    rest_stopped_threshold: float,
    rest_low_speed_threshold: float,
    speed_plot_cap_mps: float,
    shelter_zone_merge_gap_m: float,
) -> dict:
    activity_dir = outdir / f"activity_{sanitize(activity_id)}"
    activity_dir.mkdir(parents=True, exist_ok=True)

    route_1m = build_route_1m(route_raw, route_csv)
    shelter_context_zones = build_shelter_context_zones(
        route_1m, merge_gap_m=shelter_zone_merge_gap_m
    )
    route_events = build_route_events(route_1m, shelter_context_zones)
    behavior_one = filter_behavior_activity(behavior_raw, activity_id, behavior_csv)
    behavior_summary = aggregate_single_activity_behavior(behavior_one, bin_m, behavior_csv)
    rest_events = build_rest_candidates_from_single_activity(
        behavior_summary,
        stopped_threshold=rest_stopped_threshold,
        low_speed_threshold=rest_low_speed_threshold,
    )
    events = combine_events(route_events, rest_events)
    ib3d_event_markers = build_ib3d_event_markers(root, activity_id)

    base = f"ch6_5_single_activity_surface_profile_{sanitize(activity_id)}_v2_2_7_ib3d_review_safe_status"
    profile_output = activity_dir / f"{base}.csv"
    shelter_context_output = activity_dir / f"{base}_shelter_context_zones.csv"
    figure_output = activity_dir / f"{base}.png"
    report_output = activity_dir / f"{base}.md"
    run_report_output = activity_dir / f"{base}_run_report.md"

    profile = build_profile_export(
        route_1m, events, behavior_summary, shelter_context_zones, bin_m, activity_id
    )
    profile.to_csv(profile_output, index=False, encoding="utf-8-sig")
    shelter_context_zones.to_csv(shelter_context_output, index=False, encoding="utf-8-sig")

    audit = build_audit(
        route_csv,
        behavior_csv,
        activity_id,
        route_1m,
        behavior_raw,
        behavior_one,
        behavior_summary,
        events,
        shelter_context_zones,
        bin_m,
    )

    plot_activity_figure(
        route_1m,
        events,
        behavior_summary,
        shelter_context_zones,
        activity_id,
        figure_output,
        bin_m,
        speed_plot_cap_mps=speed_plot_cap_mps,
        ib3d_event_markers=ib3d_event_markers,
    )
    write_report(
        report_output,
        route_csv,
        behavior_csv,
        activity_id,
        route_1m,
        events,
        behavior_summary,
        shelter_context_zones,
        audit,
    )

    run_report_lines = [
        f"# Chapter 6.5 single-activity profile v2.2.7 speed threshold pause focus run report: {activity_id}",
        "",
        f"- route_input_csv: `{route_csv}`",
        f"- behavior_input_csv: `{behavior_csv}`",
        f"- output_directory: `{activity_dir}`",
        f"- profile_row_count: {len(profile)}",
        f"- selected_activity_behavior_summary_row_count: {len(behavior_summary)}",
        f"- event_marker_count: {len(events)}",
        f"- ib3d_event_marker_count: {len(ib3d_event_markers)}",
        f"- shelter_context_zone_count: {len(shelter_context_zones)}",
        f"- shelter_raw_proximity_run_count: {int(shelter_context_zones['raw_proximity_run_count'].sum()) if not shelter_context_zones.empty else 0}",
        f"- shelter_zone_merge_gap_m: {shelter_zone_merge_gap_m}",
        f"- speed_plot_cap_mps: {speed_plot_cap_mps}",
        f"- low_speed_threshold_mps: {LOW_SPEED_THRESHOLD_MPS}",
        "- low_speed_threshold_visual_only: True",
        "- ib3d_short_pause_band_alpha: 0.18",
        f"- audit_conclusion: `{audit.iloc[0]['audit_conclusion']}`",
        "",
        "## Audit fields",
        "",
    ]
    for field, value in audit.iloc[0].items():
        run_report_lines.append(f"- {field}: `{value}`")
    run_report_lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- `{figure_output}`",
            f"- `{profile_output}`",
            f"- `{shelter_context_output}`",
            f"- `{report_output}`",
            f"- `{run_report_output}`",
            "",
            "## Main-figure decision",
            "",
            "- Main panel order: spatial background, slope, heart rate, speed, low/stopped point ratios.",
            "- Behavior panels intentionally omit route_load_context_band shading so shelter context zones remain visually unambiguous.",
            "- This is a selected-activity figure, not a cross-activity summary.",
            "",
        ]
    )
    run_report_output.write_text("\n".join(run_report_lines), encoding="utf-8")

    return {
        "activity_id": activity_id,
        "audit_conclusion": str(audit.iloc[0]["audit_conclusion"]),
        "profile_rows": len(profile),
        "behavior_summary_rows": len(behavior_summary),
        "event_marker_rows": len(events),
        "ib3d_event_marker_rows": len(ib3d_event_markers),
        "shelter_context_zone_count": len(shelter_context_zones),
        "shelter_raw_proximity_run_count": int(shelter_context_zones["raw_proximity_run_count"].sum()) if not shelter_context_zones.empty else 0,
        "outputs": [
            str(figure_output),
            str(profile_output),
            str(shelter_context_output),
            str(report_output),
            str(run_report_output),
        ],
    }


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    route_csv = resolve_path(root, args.route_csv)
    behavior_csv = resolve_behavior_csv(root, args.behavior_csv)
    outdir = resolve_path(root, args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    setup_font()
    route_raw = read_csv(route_csv)
    behavior_raw = read_csv(behavior_csv)

    require_columns(behavior_raw, ["activity_id_short"], behavior_csv)

    if args.all:
        activity_ids = sorted(behavior_raw["activity_id_short"].dropna().astype(str).unique())
    else:
        activity_ids = [str(args.activity_id)]

    results = []
    exit_code = 0
    for activity_id in activity_ids:
        try:
            result = make_one_activity(
                root=root,
                route_csv=route_csv,
                behavior_csv=behavior_csv,
                route_raw=route_raw,
                behavior_raw=behavior_raw,
                activity_id=activity_id,
                outdir=outdir,
                bin_m=args.behavior_bin_m,
                rest_stopped_threshold=args.rest_stopped_threshold,
                rest_low_speed_threshold=args.rest_low_speed_threshold,
                speed_plot_cap_mps=args.speed_plot_cap_mps,
                shelter_zone_merge_gap_m=args.shelter_zone_merge_gap_m,
            )
            results.append(result)
            if not result["audit_conclusion"].startswith("PASS_"):
                exit_code = 1
        except Exception as exc:
            exit_code = 1
            results.append(
                {
                    "activity_id": activity_id,
                    "audit_conclusion": "ERROR",
                    "error": repr(exc),
                    "outputs": [],
                }
            )

    master_report = outdir / "ch6_5_single_activity_surface_profiles_v2_2_7_ib3d_review_safe_status_master_run_report.md"
    lines = [
        "# Chapter 6.5 single-activity surface profiles v2.2.7 speed threshold pause focus master run report",
        "",
        f"- root: `{root}`",
        f"- route_input_csv: `{route_csv}`",
        f"- behavior_input_csv: `{behavior_csv}`",
        f"- output_directory: `{outdir}`",
        f"- activity_ids: {', '.join(activity_ids)}",
        "",
        "## Results",
        "",
    ]
    for result in results:
        lines.append(f"### {result.get('activity_id')}")
        lines.append(f"- audit_conclusion: `{result.get('audit_conclusion')}`")
        if result.get("error"):
            lines.append(f"- error: `{result.get('error')}`")
        if result.get("outputs"):
            lines.append("- outputs:")
            for output in result["outputs"]:
                lines.append(f"  - `{output}`")
        lines.append("")
    master_report.write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps(
        {
            "master_report": str(master_report),
            "results": results,
        },
        ensure_ascii=False,
        indent=2,
    ))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
