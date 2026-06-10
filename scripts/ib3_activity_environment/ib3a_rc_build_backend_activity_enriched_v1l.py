#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
IB3A-RC v1l backend activity enriched dataset builder.

Purpose:
- Build row-level backend-facing enriched activity dataset from v1k5.
- Preserve raw rows and all upstream columns.
- Add backend contract columns for:
  raw/calibrated aliases,
  horizontal calibration audit,
  elevation calibration audit,
  OSM route attributes,
  terrain/profile placeholders,
  facility/hazard placeholders,
  route complexity placeholders,
  radar-ready evidence hints.

This v1l-1 version is schema-preserving and conservative:
- Does not overwrite upstream fields.
- Does not perform spatial OSM proximity join yet.
- Does not compute formal radar scores.
- Does not create high-level behavior events.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


PIPELINE_VERSION = "IB3A-RC-v1l-backend-enriched-schema-v1"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build IB3A-RC v1l backend activity enriched row-level dataset."
    )
    p.add_argument("--route-folder", required=True)
    p.add_argument("--activity-id", default="")
    p.add_argument("--activity-ids", default="")
    p.add_argument("--input-root", required=True)
    p.add_argument("--catalog", required=True)
    p.add_argument("--out-dir", required=True)
    return p.parse_args()


def read_csv(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    return rows, fields


def write_csv(path: Path, rows: List[Dict[str, Any]], fields: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip()
    if s == "" or s.lower() in {"nan", "none", "null"}:
        return None
    try:
        f = float(s)
    except Exception:
        return None
    if not math.isfinite(f):
        return None
    return f


def to_bool(v: Any) -> bool:
    return str(v).strip().lower() in {"true", "1", "yes", "y"}


def first_nonempty(row: Dict[str, Any], candidates: Iterable[str], default: str = "") -> str:
    for c in candidates:
        v = row.get(c)
        if v is not None and str(v).strip() != "":
            return str(v)
    return default


def add_if_missing(fields: List[str], name: str) -> None:
    if name not in fields:
        fields.append(name)


def find_input_csv(input_root: Path, route_folder: str, activity_id: str) -> Path:
    folder = input_root / route_folder / activity_id
    expected = folder / f"{route_folder}_{activity_id}_calibrated_elevation_v1k5.csv"
    if expected.exists():
        return expected

    matches = sorted(folder.glob("*_calibrated_elevation_v1k5.csv"))
    if len(matches) == 1:
        return matches[0]

    raise FileNotFoundError(f"Cannot find v1k5 CSV for {route_folder}/{activity_id}: {folder}")


def load_catalog(catalog_path: Path) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
    rows, fields = read_csv(catalog_path)
    formal = [r for r in rows if str(r.get("include_in_formal_v1l_candidate", "")).lower() == "true"]

    axis_counts: Dict[str, int] = {}
    for r in rows:
        axis = r.get("radar_axis_primary", "")
        axis_counts[axis] = axis_counts.get(axis, 0) + 1

    meta = {
        "catalog_path": str(catalog_path),
        "catalog_rows": len(rows),
        "catalog_fields": fields,
        "formal_candidate_n": len(formal),
        "radar_axis_primary_counts": axis_counts,
    }
    return rows, meta


def infer_horizontal_source(row: Dict[str, str]) -> str:
    explicit = first_nonempty(
        row,
        [
            "horizontal_calibration_source",
            "calibrated_coordinate_source",
            "calibrated_location_source",
            "coordinate_source",
            "display_coordinate_source",
        ],
    )
    if explicit:
        return explicit

    route_class = first_nonempty(row, ["route_class"])
    if route_class in {"WRONG_ROUTE"}:
        return "WRONG_ROUTE_PRESERVED"
    if route_class in {"OFF_TARGET"}:
        return "OFF_TARGET_RAW_FALLBACK"
    if route_class in {"CONNECTOR"}:
        return "CONNECTOR_PROJECTION"
    if route_class in {"MAINLINE_SUMMIT_STAY"}:
        return "REVIEWED_SUMMIT_ANCHOR"
    if route_class in {"MAINLINE_CORE"}:
        return "OSM_CANDIDATE_PROJECTION"
    return "UNKNOWN"


def infer_horizontal_method(row: Dict[str, str], source: str) -> str:
    explicit = first_nonempty(
        row,
        [
            "horizontal_calibration_method",
            "calibrated_coordinate_method",
            "projection_method",
            "display_coordinate_method",
        ],
    )
    if explicit:
        return explicit

    if source in {"OSM_CANDIDATE_PROJECTION", "CONNECTOR_PROJECTION"}:
        return "candidate_route_projection"
    if source == "REVIEWED_SUMMIT_ANCHOR":
        return "summit_anchor_reviewed"
    if source in {"OFF_TARGET_RAW_FALLBACK", "WRONG_ROUTE_PRESERVED"}:
        return "raw_preserved"
    return "unknown"


def infer_horizontal_confidence(row: Dict[str, str], source: str) -> str:
    explicit = first_nonempty(
        row,
        [
            "horizontal_calibration_confidence",
            "calibrated_coordinate_confidence",
            "display_coordinate_confidence",
        ],
    )
    if explicit:
        return explicit

    review = to_bool(first_nonempty(row, ["calibration_review_required", "horizontal_calibration_review_required"]))
    route_class = first_nonempty(row, ["route_class"])
    if review or route_class in {"UNKNOWN_REVIEW", "OFF_TARGET"}:
        return "REVIEW"
    if source in {"OSM_CANDIDATE_PROJECTION", "REVIEWED_SUMMIT_ANCHOR", "CONNECTOR_PROJECTION"}:
        return "HIGH"
    if source in {"WRONG_ROUTE_PRESERVED", "OFF_TARGET_RAW_FALLBACK"}:
        return "LOW"
    return "UNKNOWN"


def infer_backend_use(row: Dict[str, str]) -> str:
    explicit = first_nonempty(row, ["backend_use_policy"])
    if explicit:
        return explicit

    route_class = first_nonempty(row, ["route_class"])
    if route_class in {"OFF_TARGET", "WRONG_ROUTE", "UNKNOWN_REVIEW"}:
        return "QA_ONLY"

    if to_bool(row.get("motion_artifact_flag")) or to_bool(row.get("elevation_artifact_flag")):
        return "REVIEW_REQUIRED"

    return "ANALYTICS_READY"


def infer_model_exclusion_reason(row: Dict[str, str]) -> str:
    reasons: List[str] = []

    route_class = first_nonempty(row, ["route_class"])
    if route_class in {"OFF_TARGET", "WRONG_ROUTE", "UNKNOWN_REVIEW"}:
        reasons.append(f"ROUTE_CLASS_{route_class}")

    if to_bool(row.get("motion_artifact_flag")):
        reasons.append("MOTION_ARTIFACT")

    if to_bool(row.get("elevation_artifact_flag")):
        reasons.append("ELEVATION_ARTIFACT")

    if not to_bool(first_nonempty(row, ["time_interval_valid"], "true")):
        reasons.append("INVALID_TIME_INTERVAL")

    if not to_bool(first_nonempty(row, ["motion_representative_flag"], "true")):
        reasons.append("NON_REPRESENTATIVE_MOTION")

    return ";".join(reasons)


def infer_radar_hints(row: Dict[str, str]) -> Dict[str, str]:
    """
    v1l-1 conservative placeholders.
    True OSM/facility/hazard evidence will be added in v1l-2.
    Here we only expose minimal hints from already-known row-level state.
    """
    route_class = first_nonempty(row, ["route_class"])
    movement_state = first_nonempty(row, ["movement_state"])
    slope = to_float(first_nonempty(row, ["calibrated_slope_pct"]))

    hints = {
        "radar_physical_fitness_hint": "0",
        "radar_technical_difficulty_hint": "0",
        "radar_base_hazard_hint": "0",
        "radar_navigation_hint": "0",
        "radar_support_insufficiency_hint": "0",
        "radar_weather_sensitivity_hint": "0",
        "radar_evidence_layers": "",
        "radar_evidence_types": "",
        "radar_evidence_directions": "",
        "radar_evidence_notes": "",
    }

    layers: List[str] = []
    types: List[str] = []
    directions: List[str] = []
    notes: List[str] = []

    if slope is not None and abs(slope) >= 15:
        hints["radar_physical_fitness_hint"] = "1"
        layers.append("calibrated_slope")
        types.append("steep_slope_hint")
        directions.append("increase")
        notes.append("row_slope_abs_ge_15_pct")

    if route_class in {"WRONG_ROUTE", "OFF_TARGET", "UNKNOWN_REVIEW"}:
        hints["radar_navigation_hint"] = "2"
        layers.append("route_class")
        types.append("route_uncertainty")
        directions.append("increase")
        notes.append(f"route_class={route_class}")

    if movement_state in {"STOPPED"}:
        layers.append("movement_state")
        types.append("stopped_context")
        directions.append("contextual")
        notes.append("stopped_row_context_only")

    hints["radar_evidence_layers"] = ";".join(layers)
    hints["radar_evidence_types"] = ";".join(types)
    hints["radar_evidence_directions"] = ";".join(directions)
    hints["radar_evidence_notes"] = ";".join(notes)

    return hints


BACKEND_CONTRACT_FIELDS = [
    "route_folder",
    "case_id",
    "row_id",
    "source_file",
    "source_sha256",
    "pipeline_version",

    "raw_lat",
    "raw_lon",
    "raw_elevation_m",
    "raw_distance_m",
    "raw_speed_mps",
    "raw_heart_rate",
    "raw_cadence",
    "raw_power",
    "raw_temperature",

    "calibrated_lat",
    "calibrated_lon",
    "display_lat",
    "display_lon",

    "horizontal_calibration_source",
    "horizontal_calibration_method",
    "horizontal_calibration_confidence",
    "horizontal_calibration_review_required",
    "horizontal_join_dist_m",
    "horizontal_projection_dist_m",
    "horizontal_phase_ambiguous_flag",
    "horizontal_calibration_reason",

    "model_exclusion_reason",
    "calibration_review_required",

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
    "osm_width",
    "osm_access",
    "osm_foot",
    "osm_bicycle",
    "osm_semantic_join_method",
    "osm_semantic_join_dist_m",
    "osm_semantic_confidence",
    "osm_semantic_review_required",

    "route_dist_m",
    "route_progress_ratio",
    "route_phase",
    "terrain_elevation_m",
    "terrain_slope_pct",
    "terrain_aspect_deg",
    "contour_density",
    "terrain_risk_band",
    "dist_to_start_m",
    "dist_to_peak_m",
    "dist_to_end_m",
    "nearest_anchor_name",
    "nearest_anchor_type",

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

    "candidate_route_count_30m",
    "candidate_route_count_50m",
    "path_intersection_count_30m",
    "path_intersection_count_50m",
    "parallel_route_flag",
    "self_near_route_flag",
    "route_phase_ambiguous_flag",
    "horizontal_phase_ambiguous_flag",
    "elevation_profile_ambiguous_flag",
    "route_choice_complexity_score_hint",

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


def enrich_row(
    row: Dict[str, str],
    route_folder: str,
    activity_id: str,
    source_file: str,
    source_sha: str,
) -> Dict[str, str]:
    out = dict(row)

    raw_index = first_nonempty(out, ["raw_point_index", "point_index", "index"])
    out["route_folder"] = first_nonempty(out, ["route_folder"], route_folder)
    out["case_id"] = first_nonempty(out, ["case_id"], route_folder)
    out["activity_id"] = first_nonempty(out, ["activity_id"], activity_id)
    out["row_id"] = first_nonempty(out, ["row_id"], f"{activity_id}_{raw_index}")
    out["source_file"] = first_nonempty(out, ["source_file"], source_file)
    out["source_sha256"] = first_nonempty(out, ["source_sha256"], source_sha)
    out["pipeline_version"] = PIPELINE_VERSION

    out["raw_lat"] = first_nonempty(out, ["raw_lat", "lat", "latitude", "gps_lat", "original_lat"])
    out["raw_lon"] = first_nonempty(out, ["raw_lon", "lon", "lng", "longitude", "gps_lon", "original_lon"])
    out["raw_elevation_m"] = first_nonempty(out, ["raw_elevation_m", "elevation_m", "altitude", "altitude_m", "ele"])
    out["raw_distance_m"] = first_nonempty(out, ["raw_distance_m", "distance_m", "distance"])
    out["raw_speed_mps"] = first_nonempty(out, ["raw_speed_mps", "speed_mps", "speed"])
    out["raw_heart_rate"] = first_nonempty(out, ["raw_heart_rate", "heart_rate", "hr"])
    out["raw_cadence"] = first_nonempty(out, ["raw_cadence", "cadence"])
    out["raw_power"] = first_nonempty(out, ["raw_power", "power"])
    out["raw_temperature"] = first_nonempty(out, ["raw_temperature", "temperature", "temp"])

    out["calibrated_lat"] = first_nonempty(out, ["calibrated_lat", "display_lat", "candidate_lat", "projected_lat", "raw_lat"])
    out["calibrated_lon"] = first_nonempty(out, ["calibrated_lon", "display_lon", "candidate_lon", "projected_lon", "raw_lon"])
    out["display_lat"] = first_nonempty(out, ["display_lat", "calibrated_lat", "raw_lat"])
    out["display_lon"] = first_nonempty(out, ["display_lon", "calibrated_lon", "raw_lon"])

    source = infer_horizontal_source(out)
    method = infer_horizontal_method(out, source)
    confidence = infer_horizontal_confidence(out, source)

    out["horizontal_calibration_source"] = first_nonempty(out, ["horizontal_calibration_source"], source)
    out["horizontal_calibration_method"] = first_nonempty(out, ["horizontal_calibration_method"], method)
    out["horizontal_calibration_confidence"] = first_nonempty(out, ["horizontal_calibration_confidence"], confidence)
    out["horizontal_calibration_review_required"] = first_nonempty(
        out,
        ["horizontal_calibration_review_required"],
        "True" if confidence in {"LOW", "REVIEW", "UNKNOWN"} else "False",
    )
    out["horizontal_join_dist_m"] = first_nonempty(
        out,
        ["horizontal_join_dist_m", "candidate_dist_m", "projection_dist_m", "match_dist_m"],
    )
    out["horizontal_projection_dist_m"] = first_nonempty(
        out,
        ["horizontal_projection_dist_m", "projection_dist_m", "candidate_projection_dist_m"],
    )
    out["horizontal_phase_ambiguous_flag"] = first_nonempty(
        out,
        ["horizontal_phase_ambiguous_flag", "route_phase_ambiguous_flag", "candidate_ambiguous_flag"],
        "False",
    )
    out["horizontal_calibration_reason"] = first_nonempty(
        out,
        ["horizontal_calibration_reason", "display_coordinate_reason", "calibrated_coordinate_reason"],
        f"source={source};method={method}",
    )

    out["backend_use_policy"] = infer_backend_use(out)
    out["model_exclusion_reason"] = first_nonempty(
        out,
        ["model_exclusion_reason"],
        infer_model_exclusion_reason(out),
    )
    out["calibration_review_required"] = first_nonempty(
        out,
        ["calibration_review_required"],
        "True" if (
            to_bool(out.get("horizontal_calibration_review_required"))
            or to_bool(out.get("calibrated_elevation_review_required"))
            or out["model_exclusion_reason"] != ""
        ) else "False",
    )

    # OSM route attributes: v1l-1 keeps schema, v1l-2 will populate by OSM/profile joins.
    for c in [
        "osm_way_id", "osm_relation_id", "osm_name", "osm_ref",
        "osm_highway", "osm_surface", "osm_smoothness", "osm_tracktype",
        "osm_bridge", "osm_tunnel", "osm_steps", "osm_incline",
        "osm_sac_scale", "osm_trail_visibility", "osm_width",
        "osm_access", "osm_foot", "osm_bicycle",
    ]:
        out[c] = first_nonempty(out, [c, c.replace("osm_", "")])

    out["osm_semantic_join_method"] = first_nonempty(out, ["osm_semantic_join_method"], "NOT_JOINED_V1L1_SCHEMA_ONLY")
    out["osm_semantic_join_dist_m"] = first_nonempty(out, ["osm_semantic_join_dist_m"])
    out["osm_semantic_confidence"] = first_nonempty(out, ["osm_semantic_confidence"], "NOT_AVAILABLE")
    out["osm_semantic_review_required"] = first_nonempty(out, ["osm_semantic_review_required"], "True")

    # Terrain/profile aliases if upstream already has compatible fields.
    out["route_dist_m"] = first_nonempty(out, ["route_dist_m", "elevation_profile_dist_m", "profile_dist_m"])
    out["terrain_elevation_m"] = first_nonempty(out, ["terrain_elevation_m", "elevation_profile_ele_smooth_m", "calibrated_elevation_m"])
    out["terrain_slope_pct"] = first_nonempty(out, ["terrain_slope_pct", "calibrated_slope_pct"])
    out["route_phase"] = first_nonempty(out, ["route_phase"], "UNKNOWN")
    out["elevation_profile_ambiguous_flag"] = first_nonempty(
        out,
        ["elevation_profile_ambiguous_flag"],
        "False",
    )
    out["route_phase_ambiguous_flag"] = first_nonempty(
        out,
        ["route_phase_ambiguous_flag"],
        first_nonempty(out, ["elevation_profile_ambiguous_flag"], "False"),
    )

    # Fill remaining placeholder columns.
    for c in BACKEND_CONTRACT_FIELDS:
        if c not in out:
            if c.endswith("_flag") or c.endswith("_review_required"):
                out[c] = "False"
            elif c.endswith("_hint") or c.endswith("_count_30m") or c.endswith("_count_50m"):
                out[c] = "0"
            else:
                out[c] = ""

    out.update(infer_radar_hints(out))

    return out


def summarize(rows: List[Dict[str, str]], activity_id: str, in_csv: Path, out_csv: Path) -> Dict[str, Any]:
    n = len(rows)

    def count_nonempty(col: str) -> int:
        return sum(1 for r in rows if str(r.get(col, "")).strip() != "")

    def count_true(col: str) -> int:
        return sum(1 for r in rows if to_bool(r.get(col)))

    def count_nonzero(col: str) -> int:
        return sum(1 for r in rows if (to_float(r.get(col)) or 0.0) != 0.0)

    return {
        "activity_id": activity_id,
        "status": "PASS",
        "rows": n,
        "input_csv": str(in_csv),
        "output_csv": str(out_csv),
        "raw_lat_nonempty": count_nonempty("raw_lat"),
        "raw_lon_nonempty": count_nonempty("raw_lon"),
        "calibrated_lat_nonempty": count_nonempty("calibrated_lat"),
        "calibrated_lon_nonempty": count_nonempty("calibrated_lon"),
        "calibrated_elevation_nonempty": count_nonempty("calibrated_elevation_m"),
        "backend_use_analytics_ready_n": sum(1 for r in rows if r.get("backend_use_policy") == "ANALYTICS_READY"),
        "calibration_review_required_n": count_true("calibration_review_required"),
        "osm_semantic_joined_n": sum(1 for r in rows if r.get("osm_semantic_join_method") != "NOT_JOINED_V1L1_SCHEMA_ONLY"),
        "osm_semantic_review_required_n": count_true("osm_semantic_review_required"),
        "radar_physical_fitness_nonzero_n": count_nonzero("radar_physical_fitness_hint"),
        "radar_technical_difficulty_nonzero_n": count_nonzero("radar_technical_difficulty_hint"),
        "radar_base_hazard_nonzero_n": count_nonzero("radar_base_hazard_hint"),
        "radar_navigation_nonzero_n": count_nonzero("radar_navigation_hint"),
        "radar_support_insufficiency_nonzero_n": count_nonzero("radar_support_insufficiency_hint"),
        "radar_weather_sensitivity_nonzero_n": count_nonzero("radar_weather_sensitivity_hint"),
    }


def process_activity(
    route_folder: str,
    activity_id: str,
    input_root: Path,
    out_dir: Path,
) -> Dict[str, Any]:
    in_csv = find_input_csv(input_root, route_folder, activity_id)
    source_sha = sha256_file(in_csv)
    rows, upstream_fields = read_csv(in_csv)

    out_rows = [
        enrich_row(
            row=r,
            route_folder=route_folder,
            activity_id=activity_id,
            source_file=str(in_csv),
            source_sha=source_sha,
        )
        for r in rows
    ]

    out_fields = list(upstream_fields)
    for f in BACKEND_CONTRACT_FIELDS:
        add_if_missing(out_fields, f)

    out_activity_dir = out_dir / route_folder / activity_id
    out_csv = out_activity_dir / f"{route_folder}_{activity_id}_backend_activity_enriched_v1l.csv"
    write_csv(out_csv, out_rows, out_fields)

    s = summarize(out_rows, activity_id, in_csv, out_csv)

    if s["rows"] != len(rows):
        s["status"] = "FAIL_ROW_COUNT_CHANGED"

    return s


def main() -> int:
    args = parse_args()

    route_folder = args.route_folder
    input_root = Path(args.input_root)
    catalog_path = Path(args.catalog)
    out_dir = Path(args.out_dir)

    _, catalog_meta = load_catalog(catalog_path)

    if args.activity_ids.strip():
        activity_ids = [x.strip() for x in args.activity_ids.split(",") if x.strip()]
    elif args.activity_id.strip():
        activity_ids = [args.activity_id.strip()]
    else:
        raise ValueError("Provide --activity-id or --activity-ids")

    summaries: List[Dict[str, Any]] = []
    fail_n = 0

    for aid in activity_ids:
        try:
            s = process_activity(route_folder, aid, input_root, out_dir)
            summaries.append(s)
            if s["status"] != "PASS":
                fail_n += 1
            print(
                f"[{s['status']}] {aid}: rows={s['rows']} "
                f"raw={s['raw_lat_nonempty']}/{s['raw_lon_nonempty']} "
                f"cal={s['calibrated_lat_nonempty']}/{s['calibrated_lon_nonempty']} "
                f"ele={s['calibrated_elevation_nonempty']} "
                f"analytics_ready={s['backend_use_analytics_ready_n']} "
                f"osm_joined={s['osm_semantic_joined_n']} "
                f"out={s['output_csv']}"
            )
        except Exception as exc:
            fail_n += 1
            s = {
                "activity_id": aid,
                "status": "FAIL",
                "rows": 0,
                "error": str(exc),
            }
            summaries.append(s)
            print(f"[FAIL] {aid}: {exc}")

    batch_dir = out_dir / "_batch_summary"
    batch_dir.mkdir(parents=True, exist_ok=True)

    summary_csv = batch_dir / f"{route_folder}_v1l_backend_activity_enriched_summary.csv"
    summary_json = batch_dir / f"{route_folder}_v1l_backend_activity_enriched_summary.json"

    all_keys: List[str] = []
    for s in summaries:
        for k in s.keys():
            if k not in all_keys:
                all_keys.append(k)

    write_csv(summary_csv, summaries, all_keys)

    summary_payload = {
        "pipeline_version": PIPELINE_VERSION,
        "route_folder": route_folder,
        "catalog_meta": catalog_meta,
        "summaries": summaries,
    }
    summary_json.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"summary_csv={summary_csv}")
    print(f"summary_json={summary_json}")
    print("status=PASS" if fail_n == 0 else f"status=FAIL fail_n={fail_n}")

    return 0 if fail_n == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
