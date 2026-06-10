#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
IB3A-RC v1l-2 route semantic / facility / radar evidence join.

Purpose
-------
Read v1l-1 backend enriched activity CSVs and join route-side evidence
from IB2 route_risk_v2.csv by profile distance.

Primary join policy
-------------------
- MAINLINE_CORE / MAINLINE_SUMMIT_STAY / CONNECTOR:
    v1l1.elevation_profile_dist_m -> nearest ib2.dist_m
- WRONG_ROUTE / OFF_TARGET:
    preserve as behavior evidence, do not force canonical mainline OSM/risk semantics.

This script does NOT:
- modify v1l-1 outputs in place
- overwrite raw/calibrated/display coordinates
- recompute speed, elevation, movement_state, gain/loss, or backend_use_policy
- compute final radar score
- recompute THCI
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


PIPELINE_VERSION = "IB3A-RC-v1l2-osm-radar-evidence-join-v1"

ELIGIBLE_ROUTE_CLASSES = {
    "MAINLINE_CORE",
    "MAINLINE_SUMMIT_STAY",
    "CONNECTOR",
}

OFF_ROUTE_CLASSES = {
    "WRONG_ROUTE",
    "OFF_TARGET",
}

PROTECTED_FIELDS = {
    # identity / order
    "route_folder",
    "case_id",
    "activity_id",
    "raw_point_index",
    "row_id",
    "timestamp",
    "elapsed_sec",
    "source_file",
    "source_sha256",
    # raw activity
    "raw_lat",
    "raw_lon",
    "raw_elevation_m",
    "raw_distance_m",
    "raw_speed_mps",
    "raw_heart_rate",
    "raw_cadence",
    "raw_power",
    "raw_temperature",
    # calibrated/display coordinates
    "calibrated_lat",
    "calibrated_lon",
    "display_lat",
    "display_lon",
    # horizontal calibration
    "horizontal_calibration_source",
    "horizontal_calibration_method",
    "horizontal_calibration_confidence",
    "horizontal_calibration_review_required",
    "horizontal_join_dist_m",
    "horizontal_projection_dist_m",
    "horizontal_phase_ambiguous_flag",
    "horizontal_calibration_reason",
    # elevation calibration
    "calibrated_elevation_m",
    "calibrated_elevation_source",
    "calibrated_elevation_confidence",
    "calibrated_elevation_review_required",
    "elevation_lookup_method",
    "elevation_reference_id",
    "elevation_join_dist_m",
    "elevation_profile_dist_m",
    "elevation_profile_ele_smooth_m",
    "elevation_profile_ambiguous_flag",
    "elevation_profile_ambiguity_reason",
    "elevation_profile_dist_jump_flag",
    "calibrated_delta_elevation_m",
    "calibrated_slope_pct",
    "elevation_step_valid",
    "calibrated_cumulative_gain_m",
    "calibrated_cumulative_loss_m",
    "agg_supplemental_gain_m",
    "agg_supplemental_loss_m",
    "agg_total_gain_m",
    "agg_total_loss_m",
    "agg_supplement_step_valid",
    "agg_supplement_step_review_only",
    "agg_supplement_step_reason",
    # movement / route
    "route_class",
    "movement_state",
    "backend_use_policy",
    "motion_representative_flag",
    "time_interval_valid",
    "motion_artifact_flag",
    "motion_artifact_type",
    "motion_artifact_reason",
    "elevation_artifact_flag",
    "elevation_artifact_reason",
    "gain_loss_excluded_reason",
    "calibration_review_required",
    "model_exclusion_reason",
}

# v1l-2 fields populated or appended by this script.
V1L2_FIELDS = [
    "v1l2_pipeline_version",
    "v1l2_join_status",
    "v1l2_join_reason",
    "v1l2_route_evidence_source",
    "v1l2_ib2_dist_m",
    "v1l2_ib2_join_dist_m",
    "v1l2_ib2_sample_idx",

    # OSM semantic fields
    "osm_way_id",
    "osm_relation_id",
    "osm_name",
    "osm_ref",
    "osm_highway",
    "osm_surface",
    "osm_smoothness",
    "osm_tracktype",
    "osm_bridge",
    "osm_tunnel",
    "osm_steps",
    "osm_incline",
    "osm_sac_scale",
    "osm_trail_visibility",
    "osm_access",
    "osm_foot",
    "osm_bicycle",
    "osm_width",
    "osm_semantic_join_method",
    "osm_semantic_join_dist_m",
    "osm_semantic_confidence",
    "osm_semantic_review_required",

    # Useful semantic/risk classes
    "surface_class",
    "route_semantic_class",
    "assist_class",
    "visibility_class",
    "osm_difficulty_class",

    # Proximity fields expected by backend v1l schema
    "nearest_cliff_dist_m",
    "near_cliff_flag",
    "nearest_waterway_dist_m",
    "near_waterway_flag",
    "nearest_wetland_dist_m",
    "near_wetland_flag",
    "nearest_scree_dist_m",
    "near_scree_flag",
    "nearest_landslide_dist_m",
    "near_landslide_flag",
    "nearest_handrail_dist_m",
    "near_handrail_flag",
    "nearest_steps_dist_m",
    "near_steps_flag",
    "nearest_bridge_dist_m",
    "near_bridge_flag",
    "nearest_guidepost_dist_m",
    "near_guidepost_flag",
    "nearest_trailhead_dist_m",
    "near_trailhead_flag",
    "nearest_shelter_dist_m",
    "near_shelter_flag",
    "nearest_toilet_dist_m",
    "near_toilet_flag",
    "nearest_water_source_dist_m",
    "near_water_source_flag",
    "nearest_peak_dist_m",
    "near_peak_flag",
    "nearest_parking_dist_m",
    "near_parking_flag",
    "nearest_road_dist_m",
    "near_road_flag",

    # Route risk / evidence fields
    "ib2_risk_score",
    "ib2_risk_band",
    "ib2_risk_score_smooth",
    "ib2_terrain_score",
    "ib2_effort_score",
    "ib2_exposure_score",
    "ib2_risk_reason",
    "ib2_data_quality_reason",
    "ib2_risk_confidence",

    # Risk subdomain evidence copied from IB2 source when available
    "exposure_risk_score",
    "hydrology_risk_score",
    "navigation_risk_score",
    "navigation_support_score",
    "night_navigation_risk_score",
    "night_navigation_support_score",
    "rest_support_score",
    "route_continuity_context_score",
    "route_effort_risk_score",
    "route_type_risk_score",
    "support_score",
    "surface_slip_risk_score",
    "technical_risk_score",
    "terrain_risk_score",
    "terrain_window_risk_score",
    "hydro_terrain_amplifier_score",
    "osm_terrain_combined_risk_score",
    "osm_terrain_combined_risk_band",
    "osm_semantic_risk_score",
    "osm_semantic_risk_band",

    # Flags / notes
    "technical_flags",
    "hazard_flags",
    "hydrology_flags",
    "facility_flags",
    "support_flags",
    "weather_sensitive_flags",
    "nearby_named_features",
    "conditional_factor_flags",
    "conditional_risk_domains",
    "conditional_notes",

    # Radar hints
    "radar_physical_fitness_hint",
    "radar_technical_difficulty_hint",
    "radar_base_hazard_hint",
    "radar_navigation_hint",
    "radar_support_insufficiency_hint",
    "radar_weather_sensitivity_hint",
    "radar_evidence_layers",
    "radar_evidence_types",
    "radar_evidence_directions",
    "radar_evidence_notes",
]


OSM_FIELD_MAP = {
    "osm_way_id": "osm_way_id",
    "osm_name": "osm_way_name",
    "osm_highway": "osm_highway",
    "osm_surface": "osm_surface",
    "osm_smoothness": "osm_smoothness",
    "osm_tracktype": "osm_tracktype",
    "osm_bridge": "osm_bridge",
    "osm_tunnel": "osm_tunnel",
    "osm_incline": "osm_incline",
    "osm_sac_scale": "osm_sac_scale",
    "osm_trail_visibility": "osm_trail_visibility",
    "osm_width": "osm_width",
    "surface_class": "surface_class",
    "route_semantic_class": "route_semantic_class",
    "assist_class": "assist_class",
    "visibility_class": "visibility_class",
    "osm_difficulty_class": "osm_difficulty_class",
}

PROXIMITY_FIELD_MAP = {
    "nearest_cliff_dist_m": "dist_cliff_m",
    "near_cliff_flag": "near_cliff",
    "nearest_waterway_dist_m": "dist_waterway_m",
    "near_waterway_flag": "near_waterway",
    "nearest_wetland_dist_m": "dist_wetland_m",
    "near_wetland_flag": "near_wetland",
    "nearest_scree_dist_m": "dist_scree_m",
    "near_scree_flag": "near_scree",
    "nearest_landslide_dist_m": "dist_landslide_m",
    "near_landslide_flag": "near_landslide",
    "nearest_handrail_dist_m": "dist_handrail_m",
    "near_handrail_flag": "near_handrail",
    "nearest_guidepost_dist_m": "dist_guidepost_m",
    "near_guidepost_flag": "near_guidepost",
    "nearest_trailhead_dist_m": "dist_trailhead_m",
    "near_trailhead_flag": "near_trailhead",
    "nearest_shelter_dist_m": "dist_shelter_m",
    "near_shelter_flag": "near_shelter",
    "nearest_toilet_dist_m": "dist_toilets_m",
    "near_toilet_flag": "near_toilets",
    "nearest_water_source_dist_m": "dist_drinking_water_m",
    "near_water_source_flag": "near_drinking_water",
    "nearest_peak_dist_m": "dist_peak_m",
    "near_peak_flag": "near_peak",
    "nearest_road_dist_m": "dist_highway_m",
    "near_road_flag": "near_highway",
}

RISK_FIELD_MAP = {
    "ib2_risk_score": "risk_score",
    "ib2_risk_band": "risk_band",
    "ib2_risk_score_smooth": "risk_score_smooth",
    "ib2_terrain_score": "terrain_score",
    "ib2_effort_score": "effort_score",
    "ib2_exposure_score": "exposure_score",
    "ib2_risk_reason": "risk_reason",
    "ib2_data_quality_reason": "data_quality_reason",
    "ib2_risk_confidence": "risk_confidence",

    "exposure_risk_score": "exposure_risk_score",
    "hydrology_risk_score": "hydrology_risk_score",
    "navigation_risk_score": "navigation_risk_score",
    "navigation_support_score": "navigation_support_score",
    "night_navigation_risk_score": "night_navigation_risk_score",
    "night_navigation_support_score": "night_navigation_support_score",
    "rest_support_score": "rest_support_score",
    "route_continuity_context_score": "route_continuity_context_score",
    "route_effort_risk_score": "route_effort_risk_score",
    "route_type_risk_score": "route_type_risk_score",
    "support_score": "support_score",
    "surface_slip_risk_score": "surface_slip_risk_score",
    "technical_risk_score": "technical_risk_score",
    "terrain_risk_score": "terrain_risk_score",
    "terrain_window_risk_score": "terrain_window_risk_score",
    "hydro_terrain_amplifier_score": "hydro_terrain_amplifier_score",
    "osm_terrain_combined_risk_score": "osm_terrain_combined_risk_score",
    "osm_terrain_combined_risk_band": "osm_terrain_combined_risk_band",
    "osm_semantic_risk_score": "osm_semantic_risk_score",
    "osm_semantic_risk_band": "osm_semantic_risk_band",

    "technical_flags": "technical_flags",
    "hazard_flags": "hazard_flags",
    "hydrology_flags": "hydrology_flags",
    "facility_flags": "facility_flags",
    "support_flags": "support_flags",
    "weather_sensitive_flags": "weather_sensitive_flags",
    "nearby_named_features": "nearby_named_features",
    "conditional_factor_flags": "conditional_factor_flags",
    "conditional_risk_domains": "conditional_risk_domains",
    "conditional_notes": "conditional_notes",
}


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    s = str(value).strip()
    return s == "" or s.lower() in {"nan", "none", "null"}


def to_float(value: Any) -> Optional[float]:
    if is_blank(value):
        return None
    try:
        x = float(str(value).strip())
        if math.isnan(x) or math.isinf(x):
            return None
        return x
    except Exception:
        return None


def truthy(value: Any) -> bool:
    if value is None:
        return False
    s = str(value).strip().lower()
    return s in {"1", "true", "yes", "y", "t"}


def safe_get(row: Dict[str, str], key: str, default: str = "") -> str:
    return row.get(key, default)


def score_to_hint(value: Any) -> int:
    """
    Convert heterogeneous score scales into 0/1/2/3 hints.

    Handles scores that appear as:
    - 0..1
    - 0..10
    - other positive numeric ranges
    """
    x = to_float(value)
    if x is None:
        return 0

    if x <= 0:
        return 0

    # Common normalized 0..1 risk scale.
    if x <= 1.0:
        if x >= 0.75:
            return 3
        if x >= 0.45:
            return 2
        if x >= 0.10:
            return 1
        return 0

    # Common 0..10 style score.
    if x <= 10:
        if x >= 6.0:
            return 3
        if x >= 3.0:
            return 2
        if x >= 0.5:
            return 1
        return 0

    # Fallback for larger scales.
    if x >= 60:
        return 3
    if x >= 30:
        return 2
    return 1


def max_hint(*values: Any) -> int:
    return max(score_to_hint(v) for v in values)


def presence_hint(*values: Any) -> int:
    for v in values:
        if not is_blank(v):
            s = str(v).strip().lower()
            if s not in {"0", "false", "none", "nan", "null", "[]"}:
                return 1
    return 0


def bool_hint(*values: Any) -> int:
    return 1 if any(truthy(v) for v in values) else 0


def compute_radar_hints(ib2_row: Dict[str, str]) -> Dict[str, str]:
    technical = max(
        max_hint(
            ib2_row.get("technical_risk_score"),
            ib2_row.get("route_type_risk_score"),
            ib2_row.get("terrain_window_risk_score"),
        ),
        presence_hint(
            ib2_row.get("osm_difficulty_class"),
            ib2_row.get("osm_sac_scale"),
            ib2_row.get("technical_flags"),
        ),
        bool_hint(
            ib2_row.get("osm_is_steps"),
            ib2_row.get("near_ladder"),
            ib2_row.get("near_rungs"),
            ib2_row.get("near_via_ferrata"),
        ),
    )

    base_hazard = max(
        max_hint(
            ib2_row.get("exposure_risk_score"),
            ib2_row.get("terrain_risk_score"),
            ib2_row.get("osm_terrain_combined_risk_score"),
        ),
        presence_hint(ib2_row.get("hazard_flags")),
        bool_hint(
            ib2_row.get("near_cliff"),
            ib2_row.get("near_scree"),
            ib2_row.get("near_landslide"),
            ib2_row.get("near_bare_rock"),
        ),
    )

    navigation = max(
        max_hint(
            ib2_row.get("navigation_risk_score"),
            ib2_row.get("route_continuity_context_score"),
            ib2_row.get("night_navigation_risk_score"),
        ),
        presence_hint(
            ib2_row.get("visibility_class"),
            ib2_row.get("osm_trail_visibility"),
        ),
    )

    # support_score is a support-availability score, not a deficiency score.
    # For v1l2 evidence hints, we use missing/weak support evidence conservatively.
    support_insufficiency = max(
        presence_hint(ib2_row.get("support_flags")),
        bool_hint(
            # If near support facilities exist, insufficiency should not increase.
            # This boolean hint only reflects that support-related evidence exists.
            # Final insufficiency scoring belongs downstream.
        ),
    )
    # Add low/medium insufficiency if there is no immediate support nearby.
    near_support = any(
        truthy(ib2_row.get(k))
        for k in [
            "near_shelter",
            "near_alpine_hut",
            "near_wilderness_hut",
            "near_toilets",
            "near_drinking_water",
            "near_visitor_centre",
            "near_information_office",
            "near_trailhead",
        ]
    )
    if not near_support:
        support_insufficiency = max(support_insufficiency, 1)

    weather = max(
        max_hint(
            ib2_row.get("surface_slip_risk_score"),
            ib2_row.get("hydrology_risk_score"),
            ib2_row.get("hydro_terrain_amplifier_score"),
        ),
        presence_hint(ib2_row.get("weather_sensitive_flags")),
        bool_hint(
            ib2_row.get("near_waterway"),
            ib2_row.get("near_water_area"),
            ib2_row.get("near_wetland"),
        ),
    )

    physical = max_hint(
        ib2_row.get("route_effort_risk_score"),
        ib2_row.get("effort_score"),
        ib2_row.get("terrain_score"),
        ib2_row.get("slope_pct"),
        ib2_row.get("slope_window_nlsc"),
    )

    layers: List[str] = []
    types: List[str] = []
    directions: List[str] = []
    notes: List[str] = []

    def add(axis: str, hint: int, note: str) -> None:
        if hint > 0:
            layers.append(axis)
            types.append("route_profile_evidence")
            directions.append("risk_increase_hint")
            notes.append(note)

    add("physical_fitness", physical, "effort/slope/terrain evidence")
    add("technical_difficulty", technical, "OSM difficulty, steps, technical flags")
    add("base_hazard", base_hazard, "hazard/exposure/terrain evidence")
    add("navigation", navigation, "visibility/navigation/route-continuity evidence")
    add("support_insufficiency", support_insufficiency, "support/facility availability evidence")
    add("weather_sensitivity", weather, "surface-slip/hydrology/weather-sensitive evidence")

    return {
        "radar_physical_fitness_hint": str(physical),
        "radar_technical_difficulty_hint": str(technical),
        "radar_base_hazard_hint": str(base_hazard),
        "radar_navigation_hint": str(navigation),
        "radar_support_insufficiency_hint": str(support_insufficiency),
        "radar_weather_sensitivity_hint": str(weather),
        "radar_evidence_layers": ";".join(layers),
        "radar_evidence_types": ";".join(types),
        "radar_evidence_directions": ";".join(directions),
        "radar_evidence_notes": ";".join(notes),
    }


def read_csv(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    return rows, fieldnames


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_ib2_index(path: Path) -> Tuple[List[Dict[str, str]], List[float]]:
    rows, _ = read_csv(path)
    clean: List[Tuple[float, Dict[str, str]]] = []
    for r in rows:
        d = to_float(r.get("dist_m"))
        if d is not None:
            clean.append((d, r))
    clean.sort(key=lambda x: x[0])
    return [r for _, r in clean], [d for d, _ in clean]


def nearest_ib2(
    dist: float,
    ib2_rows: List[Dict[str, str]],
    ib2_dists: List[float],
) -> Tuple[Optional[Dict[str, str]], Optional[float]]:
    if not ib2_rows:
        return None, None

    idx = bisect.bisect_left(ib2_dists, dist)
    candidates = []
    if idx < len(ib2_dists):
        candidates.append(idx)
    if idx > 0:
        candidates.append(idx - 1)

    best_idx = min(candidates, key=lambda i: abs(ib2_dists[i] - dist))
    return ib2_rows[best_idx], abs(ib2_dists[best_idx] - dist)


def copy_mapped_fields(out: Dict[str, str], ib2_row: Dict[str, str]) -> None:
    for dst, src in OSM_FIELD_MAP.items():
        out[dst] = safe_get(ib2_row, src)

    # aliases / schema normalization
    out["osm_relation_id"] = ""
    out["osm_ref"] = ""
    out["osm_access"] = ""
    out["osm_foot"] = ""
    out["osm_bicycle"] = ""

    # steps normalization
    out["osm_steps"] = "true" if truthy(ib2_row.get("osm_is_steps")) or safe_get(ib2_row, "osm_highway") == "steps" else "false"

    for dst, src in PROXIMITY_FIELD_MAP.items():
        out[dst] = safe_get(ib2_row, src)

    # steps and bridge have no explicit nearest distance in the IB2 source.
    # Use conservative route-local evidence.
    if truthy(ib2_row.get("osm_is_steps")) or safe_get(ib2_row, "osm_highway") == "steps":
        out["near_steps_flag"] = "true"
        out["nearest_steps_dist_m"] = "0"
    else:
        out["near_steps_flag"] = safe_get(ib2_row, "near_assisted_trail", "false")
        out["nearest_steps_dist_m"] = safe_get(ib2_row, "dist_assisted_trail_m")

    if truthy(ib2_row.get("osm_bridge")):
        out["near_bridge_flag"] = "true"
        out["nearest_bridge_dist_m"] = "0"
    else:
        out["near_bridge_flag"] = "false"
        out["nearest_bridge_dist_m"] = ""

    # parking is not present in this source.
    out["near_parking_flag"] = ""
    out["nearest_parking_dist_m"] = ""

    for dst, src in RISK_FIELD_MAP.items():
        out[dst] = safe_get(ib2_row, src)

    out.update(compute_radar_hints(ib2_row))


def make_unjoined_fields(reason: str) -> Dict[str, str]:
    d = {k: "" for k in V1L2_FIELDS}
    d["v1l2_pipeline_version"] = PIPELINE_VERSION
    d["v1l2_join_status"] = "NOT_JOINED"
    d["v1l2_join_reason"] = reason
    d["osm_semantic_join_method"] = "NOT_JOINED"
    d["osm_semantic_confidence"] = "0"
    d["osm_semantic_review_required"] = "true"
    d["radar_physical_fitness_hint"] = "0"
    d["radar_technical_difficulty_hint"] = "0"
    d["radar_base_hazard_hint"] = "0"
    d["radar_navigation_hint"] = "0"
    d["radar_support_insufficiency_hint"] = "0"
    d["radar_weather_sensitivity_hint"] = "0"
    return d


def compare_protected(
    before: Dict[str, str],
    after: Dict[str, str],
    protected_fields: Iterable[str],
) -> int:
    changed = 0
    for k in protected_fields:
        if k in before:
            if before.get(k, "") != after.get(k, ""):
                changed += 1
    return changed


def process_activity_file(
    input_csv: Path,
    out_csv: Path,
    ib2_rows: List[Dict[str, str]],
    ib2_dists: List[float],
    max_join_dist_m: float,
) -> Dict[str, Any]:
    rows, input_fields = read_csv(input_csv)

    output_fields = list(input_fields)
    for f in V1L2_FIELDS:
        if f not in output_fields:
            output_fields.append(f)

    out_rows: List[Dict[str, str]] = []

    joined = 0
    eligible = 0
    not_joined_wrong = 0
    not_joined_off_target = 0
    not_joined_missing_dist = 0
    not_joined_far = 0
    protected_changed = 0

    hint_counts = {
        "physical": 0,
        "technical": 0,
        "base_hazard": 0,
        "navigation": 0,
        "support_insufficiency": 0,
        "weather_sensitivity": 0,
    }

    near_counts = {
        "cliff": 0,
        "waterway": 0,
        "wetland": 0,
        "scree": 0,
        "landslide": 0,
        "handrail": 0,
        "steps": 0,
        "bridge": 0,
        "guidepost": 0,
        "trailhead": 0,
        "shelter": 0,
        "toilet": 0,
        "water_source": 0,
        "peak": 0,
        "road": 0,
    }

    for row in rows:
        before = dict(row)
        out = dict(row)
        out["v1l2_pipeline_version"] = PIPELINE_VERSION

        route_class = safe_get(row, "route_class")

        if route_class in ELIGIBLE_ROUTE_CLASSES:
            eligible += 1
            profile_dist = to_float(row.get("elevation_profile_dist_m"))
            if profile_dist is None:
                out.update(make_unjoined_fields("MISSING_ELEVATION_PROFILE_DIST_M"))
                not_joined_missing_dist += 1
            else:
                ib2_row, join_dist = nearest_ib2(profile_dist, ib2_rows, ib2_dists)
                if ib2_row is None or join_dist is None:
                    out.update(make_unjoined_fields("IB2_SOURCE_EMPTY"))
                    not_joined_missing_dist += 1
                elif join_dist > max_join_dist_m:
                    out.update(make_unjoined_fields("IB2_PROFILE_DIST_JOIN_GT_THRESHOLD"))
                    out["v1l2_ib2_join_dist_m"] = f"{join_dist:.6f}"
                    not_joined_far += 1
                else:
                    copy_mapped_fields(out, ib2_row)
                    out["v1l2_join_status"] = "JOINED"
                    out["v1l2_join_reason"] = "JOIN_IB2_BY_PROFILE_DIST"
                    out["v1l2_route_evidence_source"] = "outputs/ib2_v2_route_risk_v1_3b_contract_qa/qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b/qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b_route_risk_v2.csv"
                    out["v1l2_ib2_dist_m"] = safe_get(ib2_row, "dist_m")
                    out["v1l2_ib2_join_dist_m"] = f"{join_dist:.6f}"
                    out["v1l2_ib2_sample_idx"] = safe_get(ib2_row, "sample_idx")
                    out["osm_semantic_join_method"] = "IB2_ROUTE_RISK_PROFILE_DIST_NEAREST"
                    out["osm_semantic_join_dist_m"] = f"{join_dist:.6f}"
                    out["osm_semantic_confidence"] = "1.0" if join_dist <= 1.0 else "0.8"
                    out["osm_semantic_review_required"] = "false" if join_dist <= 2.0 else "true"
                    joined += 1

        elif route_class == "WRONG_ROUTE":
            out.update(make_unjoined_fields("REVIEW_OR_WRONG_ROUTE_NOT_JOINED"))
            not_joined_wrong += 1
        elif route_class == "OFF_TARGET":
            out.update(make_unjoined_fields("REVIEW_OR_OFF_TARGET_NOT_JOINED"))
            not_joined_off_target += 1
        else:
            out.update(make_unjoined_fields("UNKNOWN_ROUTE_CLASS_NOT_JOINED"))

        # Count hints/near flags after join/unjoin.
        if int(out.get("radar_physical_fitness_hint", "0") or "0") > 0:
            hint_counts["physical"] += 1
        if int(out.get("radar_technical_difficulty_hint", "0") or "0") > 0:
            hint_counts["technical"] += 1
        if int(out.get("radar_base_hazard_hint", "0") or "0") > 0:
            hint_counts["base_hazard"] += 1
        if int(out.get("radar_navigation_hint", "0") or "0") > 0:
            hint_counts["navigation"] += 1
        if int(out.get("radar_support_insufficiency_hint", "0") or "0") > 0:
            hint_counts["support_insufficiency"] += 1
        if int(out.get("radar_weather_sensitivity_hint", "0") or "0") > 0:
            hint_counts["weather_sensitivity"] += 1

        for name in near_counts:
            key = f"near_{name}_flag"
            if truthy(out.get(key)):
                near_counts[name] += 1

        protected_changed += compare_protected(before, out, PROTECTED_FIELDS)
        out_rows.append(out)

    write_csv(out_csv, out_rows, output_fields)

    activity_id = ""
    if rows:
        activity_id = safe_get(rows[0], "activity_id")
    if not activity_id:
        activity_id = input_csv.name.replace("_backend_activity_enriched_v1l.csv", "")

    summary = {
        "activity_id": activity_id,
        "input_csv": str(input_csv),
        "output_csv": str(out_csv),
        "status": "PASS" if len(rows) == len(out_rows) and protected_changed == 0 else "FAIL",
        "rows": len(rows),
        "output_rows": len(out_rows),
        "row_count_preserved": len(rows) == len(out_rows),
        "protected_fields_changed": protected_changed,
        "join_eligible_rows": eligible,
        "joined_rows": joined,
        "join_coverage_eligible": round(joined / eligible, 6) if eligible else None,
        "not_joined_wrong_route_rows": not_joined_wrong,
        "not_joined_off_target_rows": not_joined_off_target,
        "not_joined_missing_profile_dist_rows": not_joined_missing_dist,
        "not_joined_join_dist_gt_threshold_rows": not_joined_far,
        "max_join_dist_m_threshold": max_join_dist_m,
    }
    for k, v in hint_counts.items():
        summary[f"radar_hint_nonzero_{k}_rows"] = v
    for k, v in near_counts.items():
        summary[f"near_{k}_rows"] = v

    return summary


def find_input_files(input_root: Path, activity_ids: Optional[List[str]]) -> List[Path]:
    files = sorted(
        p for p in input_root.rglob("*.csv")
        if "_batch_summary" not in str(p)
    )
    if activity_ids:
        keep = set(activity_ids)
        files = [
            p for p in files
            if any(f"_{aid}_backend_activity_enriched_v1l.csv" in p.name or p.name.startswith(f"qixing_lengshuikeng_{aid}_") for aid in keep)
        ]
    return files


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route-folder", required=True)
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--ib2-route-risk-csv", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--activity-ids", default="")
    parser.add_argument("--max-join-dist-m", type=float, default=2.0)
    args = parser.parse_args()

    input_root = Path(args.input_root)
    ib2_csv = Path(args.ib2_route_risk_csv)
    out_dir = Path(args.out_dir)
    summary_dir = out_dir / "_batch_summary"
    summary_dir.mkdir(parents=True, exist_ok=True)

    activity_ids = [s.strip() for s in args.activity_ids.split(",") if s.strip()] or None

    if not input_root.exists():
        raise FileNotFoundError(f"input root not found: {input_root}")
    if not ib2_csv.exists():
        raise FileNotFoundError(f"IB2 route risk CSV not found: {ib2_csv}")

    ib2_rows, ib2_dists = load_ib2_index(ib2_csv)
    if not ib2_rows:
        raise RuntimeError(f"No valid dist_m rows in IB2 CSV: {ib2_csv}")

    input_files = find_input_files(input_root, activity_ids)
    if not input_files:
        raise RuntimeError(f"No v1l input CSV files found under: {input_root}")

    summaries: List[Dict[str, Any]] = []

    for input_csv in input_files:
        out_name = input_csv.name.replace(
            "_backend_activity_enriched_v1l.csv",
            "_backend_activity_enriched_v1l2_osm_radar_evidence.csv",
        )
        if out_name == input_csv.name:
            out_name = input_csv.stem + "_v1l2_osm_radar_evidence.csv"

        out_csv = out_dir / out_name
        print(f"[v1l2] {input_csv.name} -> {out_csv.name}")
        summaries.append(
            process_activity_file(
                input_csv=input_csv,
                out_csv=out_csv,
                ib2_rows=ib2_rows,
                ib2_dists=ib2_dists,
                max_join_dist_m=args.max_join_dist_m,
            )
        )

    summary_csv = summary_dir / f"{args.route_folder}_v1l2_osm_radar_evidence_summary.csv"
    summary_json = summary_dir / f"{args.route_folder}_v1l2_osm_radar_evidence_summary.json"

    summary_fields: List[str] = []
    for s in summaries:
        for k in s.keys():
            if k not in summary_fields:
                summary_fields.append(k)

    write_csv(summary_csv, summaries, summary_fields)
    with summary_json.open("w", encoding="utf-8") as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)

    pass_n = sum(1 for s in summaries if s.get("status") == "PASS")
    fail_n = len(summaries) - pass_n

    aggregate = {
        "pipeline_version": PIPELINE_VERSION,
        "route_folder": args.route_folder,
        "cases_n": len(summaries),
        "pass_n": pass_n,
        "fail_n": fail_n,
        "rows_total": sum(int(s.get("rows", 0)) for s in summaries),
        "join_eligible_total": sum(int(s.get("join_eligible_rows", 0)) for s in summaries),
        "joined_total": sum(int(s.get("joined_rows", 0)) for s in summaries),
        "not_joined_wrong_route_total": sum(int(s.get("not_joined_wrong_route_rows", 0)) for s in summaries),
        "not_joined_off_target_total": sum(int(s.get("not_joined_off_target_rows", 0)) for s in summaries),
        "summary_csv": str(summary_csv),
        "summary_json": str(summary_json),
        "out_dir": str(out_dir),
    }

    aggregate_json = summary_dir / f"{args.route_folder}_v1l2_osm_radar_evidence_aggregate.json"
    with aggregate_json.open("w", encoding="utf-8") as f:
        json.dump(aggregate, f, ensure_ascii=False, indent=2)

    print("\n=== IB3A-RC v1l2 OSM/radar evidence join summary ===")
    for k, v in aggregate.items():
        print(f"{k}: {v}")

    if fail_n:
        raise SystemExit(1)


if __name__ == "__main__":
    main()