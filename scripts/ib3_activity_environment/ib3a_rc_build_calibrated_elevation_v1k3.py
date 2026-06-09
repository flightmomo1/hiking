#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
IB3A-RC v1k3 calibrated elevation / slope / cumulative gain-loss layer.

Input:
- v1k2a calibrated motion artifact CSV
- IB1E route_profile_contour_window_terrain_enriched.csv

Design:
- Preserve all upstream fields and row order.
- Do not overwrite raw_elevation_m.
- MAINLINE_CORE / MAINLINE_SUMMIT_STAY / CONNECTOR:
  use calibrated_lat/lon spatial nearest join to IB1E route profile.
- WRONG_ROUTE / OFF_TARGET:
  do not force to canonical mainline profile; use raw elevation fallback.
- Compute calibrated delta elevation, slope, cumulative gain/loss conservatively.
- Detect route-profile spatial ambiguity near self-near/overlapping route sections.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


EXTRA_COLUMNS = [
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
    "elevation_profile_candidate_count_10m",
    "elevation_profile_candidate_dist_range_m",
    "elevation_profile_dist_jump_flag",
    "calibrated_delta_elevation_m",
    "calibrated_slope_pct",
    "slope_review_required",
    "elevation_step_valid",
    "calibrated_cumulative_gain_m",
    "calibrated_cumulative_loss_m",
    "elevation_artifact_flag",
    "elevation_artifact_reason",
    "gain_loss_excluded_reason",
]


FORBIDDEN_KEYWORDS = [
    "facility_interaction",
    "nearest_osm_feature",
    "radar_evidence",
    "thci",
    "weather_sensitivity",
]


MAINLINE_CLASSES = {"MAINLINE_CORE", "MAINLINE_SUMMIT_STAY"}
SPATIAL_JOIN_CLASSES = {"MAINLINE_CORE", "MAINLINE_SUMMIT_STAY", "CONNECTOR"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build IB3A-RC v1k3 calibrated elevation / slope / cumulative gain-loss dataset."
    )
    parser.add_argument("--route-folder", required=True)
    parser.add_argument("--activity-id", default="")
    parser.add_argument("--activity-ids", default="")
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--ib1e-profile-csv", required=True)
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def sha256_file(fp: Path) -> str:
    h = hashlib.sha256()
    with fp.open("rb") as f:
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
        return float(s)
    except Exception:
        return None


def to_bool(v: Any) -> bool:
    if v is None:
        return False
    return str(v).strip().lower() in {"true", "1", "yes", "y"}


def fmt_float(v: Optional[float], ndigits: int = 6) -> str:
    if v is None:
        return ""
    if not math.isfinite(v):
        return ""
    return f"{v:.{ndigits}f}".rstrip("0").rstrip(".")


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (
        math.sin(dp / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    )
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def read_csv(fp: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    with fp.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    return rows, fieldnames


def write_csv(fp: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    fp.parent.mkdir(parents=True, exist_ok=True)
    with fp.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_profile(fp: Path) -> List[Dict[str, str]]:
    rows, _ = read_csv(fp)
    usable = []
    for r in rows:
        lat = to_float(r.get("lat"))
        lon = to_float(r.get("lon"))
        ele = to_float(r.get("ele_smooth"))
        if lat is None or lon is None or ele is None:
            continue
        usable.append(r)
    return usable


def nearest_profile_point(
    lat: float,
    lon: float,
    profile: List[Dict[str, str]],
) -> Tuple[Optional[Dict[str, str]], Optional[float], int, Optional[float], bool, str]:
    """Return nearest IB1E profile point plus 10m candidate ambiguity diagnostics."""
    best: Optional[Dict[str, str]] = None
    best_d: Optional[float] = None
    candidate_profile_dists: List[float] = []

    for p in profile:
        plat = to_float(p.get("lat"))
        plon = to_float(p.get("lon"))
        if plat is None or plon is None:
            continue

        d = haversine_m(lat, lon, plat, plon)

        if best_d is None or d < best_d:
            best_d = d
            best = p

        if d <= 10:
            pd = to_float(p.get("dist_m") or p.get("profile_dist_m"))
            if pd is not None:
                candidate_profile_dists.append(pd)

    candidate_count_10m = len(candidate_profile_dists)
    candidate_dist_range_m: Optional[float] = None
    ambiguous_flag = False
    ambiguity_reason = ""

    if candidate_profile_dists:
        candidate_dist_range_m = max(candidate_profile_dists) - min(candidate_profile_dists)
        if candidate_dist_range_m > 100:
            ambiguous_flag = True
            ambiguity_reason = "PROFILE_CANDIDATES_WITHIN_10M_SPAN_GT_100M"

    return (
        best,
        best_d,
        candidate_count_10m,
        candidate_dist_range_m,
        ambiguous_flag,
        ambiguity_reason,
    )


def percentile(vals: List[float], q: float) -> Optional[float]:
    if not vals:
        return None
    sorted_vals = sorted(vals)
    idx = int(round((len(sorted_vals) - 1) * q))
    idx = max(0, min(idx, len(sorted_vals) - 1))
    return sorted_vals[idx]


def find_input_csv(input_root: Path, route_folder: str, activity_id: str) -> Path:
    folder = input_root / route_folder / activity_id
    expected = folder / f"{route_folder}_{activity_id}_calibrated_motion_artifacts_v1k2a.csv"
    if expected.exists():
        return expected

    matches = list(folder.glob("*_calibrated_motion_artifacts_v1k2a.csv"))
    if len(matches) == 1:
        return matches[0]

    raise FileNotFoundError(f"Cannot find v1k2a CSV for {route_folder}/{activity_id}: {folder}")


def classify_elevation_source(
    row: Dict[str, str],
    profile: List[Dict[str, str]],
) -> Tuple[Dict[str, str], Optional[float]]:
    route_class = row.get("route_class", "")
    h_source = row.get("horizontal_calibration_source", "")
    raw_ele = to_float(row.get("raw_elevation_m") or row.get("ele_m"))

    result = {
        "calibrated_elevation_m": "",
        "calibrated_elevation_source": "",
        "calibrated_elevation_confidence": "",
        "calibrated_elevation_review_required": "False",
        "elevation_lookup_method": "",
        "elevation_reference_id": "",
        "elevation_join_dist_m": "",
        "elevation_profile_dist_m": "",
        "elevation_profile_ele_smooth_m": "",
        "elevation_profile_ambiguous_flag": "False",
        "elevation_profile_ambiguity_reason": "",
        "elevation_profile_candidate_count_10m": "",
        "elevation_profile_candidate_dist_range_m": "",
        "elevation_profile_dist_jump_flag": "False",
    }

    if route_class in SPATIAL_JOIN_CLASSES:
        lat = to_float(row.get("calibrated_lat"))
        lon = to_float(row.get("calibrated_lon"))

        if lat is not None and lon is not None:
            (
                best,
                best_d,
                cand_count,
                cand_range,
                ambiguous,
                ambiguity_reason,
            ) = nearest_profile_point(lat, lon, profile)

            if best is not None and best_d is not None:
                ele = to_float(best.get("ele_smooth"))
                dist_m = to_float(best.get("dist_m") or best.get("profile_dist_m"))
                ref_id = best.get("sample_idx") or best.get("terrain_segment_id") or ""

                result["calibrated_elevation_m"] = fmt_float(ele, 3)

                if route_class == "MAINLINE_SUMMIT_STAY":
                    result["calibrated_elevation_source"] = (
                        "IB1E_SUMMIT_ROUTE_PROFILE_SPATIAL_NEAREST_ELE_SMOOTH"
                    )
                elif route_class == "CONNECTOR":
                    result["calibrated_elevation_source"] = (
                        "IB1E_CONNECTOR_REVIEW_SPATIAL_NEAREST_ELE_SMOOTH"
                    )
                else:
                    result["calibrated_elevation_source"] = (
                        "IB1E_ROUTE_PROFILE_SPATIAL_NEAREST_ELE_SMOOTH"
                    )

                result["elevation_lookup_method"] = (
                    "CALIBRATED_LATLON_TO_IB1E_PROFILE_SPATIAL_NEAREST"
                )
                result["elevation_reference_id"] = str(ref_id)
                result["elevation_join_dist_m"] = fmt_float(best_d, 3)
                result["elevation_profile_dist_m"] = fmt_float(dist_m, 3)
                result["elevation_profile_ele_smooth_m"] = fmt_float(ele, 3)
                result["elevation_profile_candidate_count_10m"] = str(cand_count)
                result["elevation_profile_candidate_dist_range_m"] = fmt_float(cand_range, 3)

                if route_class in MAINLINE_CLASSES:
                    if best_d <= 5:
                        result["calibrated_elevation_confidence"] = "high"
                    elif best_d <= 10:
                        result["calibrated_elevation_confidence"] = "medium"
                    else:
                        result["calibrated_elevation_confidence"] = "review"
                        result["calibrated_elevation_review_required"] = "True"
                elif route_class == "CONNECTOR":
                    if best_d <= 10:
                        result["calibrated_elevation_confidence"] = "medium_review"
                        result["calibrated_elevation_review_required"] = "True"
                    else:
                        result["calibrated_elevation_confidence"] = "review"
                        result["calibrated_elevation_review_required"] = "True"

                if ambiguous:
                    result["elevation_profile_ambiguous_flag"] = "True"
                    result["elevation_profile_ambiguity_reason"] = ambiguity_reason

                return result, ele

        result["calibrated_elevation_m"] = fmt_float(raw_ele, 3)
        result["calibrated_elevation_source"] = "RAW_ELEVATION_FALLBACK_SPATIAL_JOIN_FAILED"
        result["calibrated_elevation_confidence"] = "review"
        result["calibrated_elevation_review_required"] = "True"
        result["elevation_lookup_method"] = "RAW_ELEVATION_FALLBACK"
        return result, raw_ele

    if route_class == "WRONG_ROUTE":
        result["calibrated_elevation_m"] = fmt_float(raw_ele, 3)
        result["calibrated_elevation_source"] = "RAW_ELEVATION_FALLBACK_WRONG_ROUTE"
        result["calibrated_elevation_confidence"] = "review"
        result["calibrated_elevation_review_required"] = "True"
        result["elevation_lookup_method"] = "RAW_ELEVATION_FALLBACK"
        return result, raw_ele

    if route_class == "OFF_TARGET" or h_source == "RAW_GPS_FALLBACK":
        result["calibrated_elevation_m"] = fmt_float(raw_ele, 3)
        result["calibrated_elevation_source"] = "RAW_ELEVATION_FALLBACK_OFF_TARGET"
        result["calibrated_elevation_confidence"] = "low_review"
        result["calibrated_elevation_review_required"] = "True"
        result["elevation_lookup_method"] = "RAW_ELEVATION_FALLBACK"
        return result, raw_ele

    result["calibrated_elevation_m"] = fmt_float(raw_ele, 3)
    result["calibrated_elevation_source"] = "RAW_ELEVATION_FALLBACK_UNKNOWN_ROUTE_CLASS"
    result["calibrated_elevation_confidence"] = "review"
    result["calibrated_elevation_review_required"] = "True"
    result["elevation_lookup_method"] = "RAW_ELEVATION_FALLBACK"
    return result, raw_ele


def process_activity(
    route_folder: str,
    activity_id: str,
    input_root: Path,
    profile: List[Dict[str, str]],
    profile_fp: Path,
    out_dir: Path,
) -> Dict[str, Any]:
    in_fp = find_input_csv(input_root, route_folder, activity_id)
    input_sha = sha256_file(in_fp)

    rows, input_fields = read_csv(in_fp)
    original_rows = [dict(r) for r in rows]

    out_fields = list(input_fields)
    for col in EXTRA_COLUMNS:
        if col not in out_fields:
            out_fields.append(col)

    cumulative_gain = 0.0
    cumulative_loss = 0.0
    prev_elev: Optional[float] = None
    prev_profile_dist: Optional[float] = None
    prev_join_dist: Optional[float] = None

    join_dists: List[float] = []
    raw_cal_diffs: List[float] = []

    for row in rows:
        elev_info, elev = classify_elevation_source(row, profile)

        for key, value in elev_info.items():
            row[key] = value

        if elev is not None:
            raw_ele = to_float(row.get("raw_elevation_m") or row.get("ele_m"))
            if raw_ele is not None:
                raw_cal_diffs.append(abs(elev - raw_ele))

        jd = to_float(row.get("elevation_join_dist_m"))
        if jd is not None:
            join_dists.append(jd)

        representative = to_bool(row.get("motion_representative_flag"))
        time_valid = to_bool(row.get("time_interval_valid"))
        motion_artifact = to_bool(row.get("motion_artifact_flag"))
        movement_state = row.get("movement_state", "")
        step_m = to_float(row.get("calibrated_step_distance_m"))
        profile_dist = to_float(row.get("elevation_profile_dist_m"))
        profile_ambiguous = to_bool(row.get("elevation_profile_ambiguous_flag"))
        profile_dist_jump = False

        row["calibrated_delta_elevation_m"] = ""
        row["calibrated_slope_pct"] = ""
        row["slope_review_required"] = "False"
        row["elevation_step_valid"] = "False"
        row["elevation_artifact_flag"] = "False"
        row["elevation_artifact_reason"] = ""
        row["gain_loss_excluded_reason"] = ""
        row["elevation_profile_dist_jump_flag"] = row.get("elevation_profile_dist_jump_flag", "False") or "False"

        gain_loss_excluded_reasons: List[str] = []

        if not representative:
            gain_loss_excluded_reasons.append("NON_REPRESENTATIVE_TIMESTAMP_ROW")
        if not time_valid:
            gain_loss_excluded_reasons.append("TIME_INTERVAL_INVALID")
        if movement_state == "DUPLICATE_TIMESTAMP_NON_REPRESENTATIVE":
            gain_loss_excluded_reasons.append("DUPLICATE_TIMESTAMP_NON_REPRESENTATIVE")
        if motion_artifact:
            gain_loss_excluded_reasons.append("MOTION_ARTIFACT_FLAG_TRUE")
            row["slope_review_required"] = "True"
        
        if profile_ambiguous:
            # Soft QA evidence only. Do not exclude gain/loss by itself.
            pass

        if elev is None:
            gain_loss_excluded_reasons.append("MISSING_CALIBRATED_ELEVATION")
        if prev_elev is None:
            gain_loss_excluded_reasons.append("NO_PREVIOUS_VALID_ELEVATION")

        delta = None
        if elev is not None and prev_elev is not None:
            delta = elev - prev_elev
            row["calibrated_delta_elevation_m"] = fmt_float(delta, 3)

        valid_step = (
            representative
            and time_valid
            and not motion_artifact
            and elev is not None
            and prev_elev is not None
            and step_m is not None
            and step_m >= 3
        )

        
        join_dist = to_float(row.get("elevation_join_dist_m"))
        profile_dist_jump_hard_exclude = False
        join_dist_hard_exclude = False


        if (
            profile_dist is not None
            and prev_profile_dist is not None
            and representative
            and step_m is not None
            and step_m < 30
            and abs(profile_dist - prev_profile_dist) > 100
        ):
            profile_dist_jump = True
            row["elevation_profile_dist_jump_flag"] = "True"
            gain_loss_excluded_reasons.append("PROFILE_DISTANCE_JUMP_GT_100M_WITH_SMALL_STEP_SOFT")

            if (
                (join_dist is not None and join_dist > 10)
                or (prev_join_dist is not None and prev_join_dist > 10)
                or (delta is not None and abs(delta) > 5)
            ):
                profile_dist_jump_hard_exclude = True
                row["slope_review_required"] = "True"
                gain_loss_excluded_reasons.append("PROFILE_DISTANCE_JUMP_HARD_EXCLUDED")
                valid_step = False

        if join_dist is not None and join_dist > 10:
            join_dist_hard_exclude = True
            row["slope_review_required"] = "True"
            gain_loss_excluded_reasons.append("ELEVATION_JOIN_DIST_GT_10M_HARD_EXCLUDED")
            valid_step = False


        if step_m is not None and step_m < 3:
            row["slope_review_required"] = "True"
            gain_loss_excluded_reasons.append("STEP_DISTANCE_LT_3M")

        if delta is not None and abs(delta) > 10:
            row["elevation_artifact_flag"] = "True"
            row["elevation_artifact_reason"] = "ABS_DELTA_ELEVATION_GT_10M"
            row["slope_review_required"] = "True"
            gain_loss_excluded_reasons.append("ELEVATION_ARTIFACT_DELTA_GT_10M")
            valid_step = False

        if valid_step and delta is not None and step_m is not None:
            slope_pct = (delta / step_m) * 100.0
            row["calibrated_slope_pct"] = fmt_float(slope_pct, 3)
            row["elevation_step_valid"] = "True"

            if delta > 1.0:
                cumulative_gain += delta
            elif delta < -1.0:
                cumulative_loss += abs(delta)
        else:
            if representative and time_valid and not motion_artifact:
                row["slope_review_required"] = "True"

        row["calibrated_cumulative_gain_m"] = fmt_float(cumulative_gain, 3)
        row["calibrated_cumulative_loss_m"] = fmt_float(cumulative_loss, 3)
        row["gain_loss_excluded_reason"] = ";".join(dict.fromkeys(gain_loss_excluded_reasons))

        if elev is not None and representative and not profile_dist_jump_hard_exclude and not join_dist_hard_exclude:
            prev_elev = elev

        if profile_dist is not None and representative and not profile_dist_jump_hard_exclude and not join_dist_hard_exclude:
            prev_profile_dist = profile_dist

        if join_dist is not None and representative and not profile_dist_jump_hard_exclude and not join_dist_hard_exclude:
            prev_join_dist = join_dist

    protected_changed = 0
    for before, after in zip(original_rows, rows):
        for field in input_fields:
            if before.get(field, "") != after.get(field, ""):
                protected_changed += 1

    forbidden_new_cols = [
        col for col in EXTRA_COLUMNS
        if any(keyword in col.lower() for keyword in FORBIDDEN_KEYWORDS)
    ]

    out_activity_dir = out_dir / route_folder / activity_id
    out_csv = out_activity_dir / f"{route_folder}_{activity_id}_calibrated_elevation_v1k3.csv"
    out_summary_json = out_activity_dir / f"{route_folder}_{activity_id}_calibrated_elevation_v1k3_summary.json"
    out_provenance_json = out_activity_dir / f"{route_folder}_{activity_id}_calibrated_elevation_v1k3_provenance.json"

    write_csv(out_csv, rows, out_fields)

    output_sha = sha256_file(out_csv)

    source_counts = Counter(row.get("calibrated_elevation_source", "") for row in rows)
    conf_counts = Counter(row.get("calibrated_elevation_confidence", "") for row in rows)
    route_source_counts = Counter(
        f"{row.get('route_class','')}|{row.get('calibrated_elevation_source','')}"
        for row in rows
    )

    null_elev_rows = sum(1 for row in rows if str(row.get("calibrated_elevation_m", "")).strip() == "")
    slope_valid_rows = sum(1 for row in rows if to_bool(row.get("elevation_step_valid")))
    slope_review_rows = sum(1 for row in rows if to_bool(row.get("slope_review_required")))
    elevation_artifact_rows = sum(1 for row in rows if to_bool(row.get("elevation_artifact_flag")))
    wrong_route_fallback_rows = sum(
        1 for row in rows
        if row.get("calibrated_elevation_source") == "RAW_ELEVATION_FALLBACK_WRONG_ROUTE"
    )
    off_target_fallback_rows = sum(
        1 for row in rows
        if row.get("calibrated_elevation_source") == "RAW_ELEVATION_FALLBACK_OFF_TARGET"
    )
    motion_artifact_excluded_rows = sum(
        1 for row in rows
        if "MOTION_ARTIFACT_FLAG_TRUE" in row.get("gain_loss_excluded_reason", "")
    )
    profile_ambiguous_rows = sum(1 for row in rows if to_bool(row.get("elevation_profile_ambiguous_flag")))
    profile_dist_jump_rows = sum(1 for row in rows if to_bool(row.get("elevation_profile_dist_jump_flag")))

    elevation_join_hard_excluded_rows = sum(
        1 for row in rows
        if "ELEVATION_JOIN_DIST_GT_10M_HARD_EXCLUDED" in row.get("gain_loss_excluded_reason", "")
    )

    summary = {
        "activity_id": activity_id,
        "status": "PASS" if protected_changed == 0 and not forbidden_new_cols else "FAIL",
        "rows": len(rows),
        "row_preserved": len(rows) == len(original_rows),
        "protected_fields_changed": protected_changed,
        "input_sha256_unchanged": sha256_file(in_fp) == input_sha,
        "forbidden_new_columns": ";".join(forbidden_new_cols),
        "input_csv": str(in_fp),
        "output_csv": str(out_csv),
        "ib1e_profile_csv": str(profile_fp),
        "input_sha256": input_sha,
        "output_sha256": output_sha,
        "elevation_source_counts": dict(source_counts),
        "elevation_confidence_counts": dict(conf_counts),
        "route_class_elevation_source_counts": dict(route_source_counts),
        "elevation_join_p50_m": percentile(join_dists, 0.50),
        "elevation_join_p95_m": percentile(join_dists, 0.95),
        "elevation_join_max_m": max(join_dists) if join_dists else None,
        "raw_vs_calibrated_elevation_diff_p50_m": percentile(raw_cal_diffs, 0.50),
        "raw_vs_calibrated_elevation_diff_p95_m": percentile(raw_cal_diffs, 0.95),
        "raw_vs_calibrated_elevation_diff_max_m": max(raw_cal_diffs) if raw_cal_diffs else None,
        "null_calibrated_elevation_rows": null_elev_rows,
        "slope_valid_rows": slope_valid_rows,
        "slope_review_required_rows": slope_review_rows,
        "elevation_artifact_rows": elevation_artifact_rows,
        "calibrated_cumulative_gain_m": cumulative_gain,
        "calibrated_cumulative_loss_m": cumulative_loss,
        "wrong_route_fallback_rows": wrong_route_fallback_rows,
        "off_target_fallback_rows": off_target_fallback_rows,
        "motion_artifact_gain_loss_excluded_rows": motion_artifact_excluded_rows,
        "profile_ambiguous_rows": profile_ambiguous_rows,
        "profile_dist_jump_rows": profile_dist_jump_rows,
        "elevation_join_hard_excluded_rows": elevation_join_hard_excluded_rows,
    }

    out_summary_json.parent.mkdir(parents=True, exist_ok=True)
    out_summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    provenance = {
        "stage": "ib3a_rc_calibrated_elevation_v1k3",
        "activity_id": activity_id,
        "route_folder": route_folder,
        "input_csv": str(in_fp),
        "input_sha256": input_sha,
        "ib1e_profile_csv": str(profile_fp),
        "ib1e_profile_sha256": sha256_file(profile_fp),
        "output_csv": str(out_csv),
        "output_sha256": output_sha,
        "policy": {
            "mainline_source": "IB1E spatial nearest using calibrated_lat/lon",
            "wrong_route_source": "raw elevation fallback",
            "off_target_source": "raw elevation fallback",
            "profile_ambiguity_rule": "profile candidates within 10m spanning >100m route distance are soft QA evidence only",
            "profile_dist_jump_rule": "representative small-step rows with >100m profile distance jump are soft QA evidence; excluded from gain-loss only when join distance or elevation delta is suspicious",
            "gain_loss_rule": "representative/time-valid/non-motion-artifact rows only; hard profile jump, high join-distance, and elevation artifact rows are excluded; gain/loss threshold 1m",
            "slope_rule": "delta_elevation / calibrated_step_distance, only when step >= 3m",
        },
    }
    out_provenance_json.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")

    return summary


def main() -> int:
    args = parse_args()

    route_folder = args.route_folder
    input_root = Path(args.input_root)
    out_dir = Path(args.out_dir)
    profile_fp = Path(args.ib1e_profile_csv)

    if args.activity_ids.strip():
        activity_ids = [x.strip() for x in args.activity_ids.split(",") if x.strip()]
    elif args.activity_id.strip():
        activity_ids = [args.activity_id.strip()]
    else:
        raise ValueError("Provide --activity-id or --activity-ids")

    profile = load_profile(profile_fp)
    if not profile:
        raise RuntimeError(f"No usable profile rows from {profile_fp}")

    summaries = []

    for activity_id in activity_ids:
        try:
            summary = process_activity(
                route_folder=route_folder,
                activity_id=activity_id,
                input_root=input_root,
                profile=profile,
                profile_fp=profile_fp,
                out_dir=out_dir,
            )
            summaries.append(summary)
            
            print(
                f"[{summary['status']}] {activity_id}: "
                f"rows={summary['rows']} "
                f"gain={summary['calibrated_cumulative_gain_m']:.2f} "
                f"loss={summary['calibrated_cumulative_loss_m']:.2f} "
                f"ambiguous={summary['profile_ambiguous_rows']} "
                f"profile_jumps={summary['profile_dist_jump_rows']} "
                f"join_hard_excluded={summary['elevation_join_hard_excluded_rows']}"
            )
        except Exception as exc:
            summary = {
                "activity_id": activity_id,
                "status": "FAIL",
                "rows": 0,
                "row_preserved": False,
                "protected_fields_changed": "",
                "input_sha256_unchanged": "",
                "forbidden_new_columns": "",
                "input_csv": "",
                "output_csv": "",
                "ib1e_profile_csv": str(profile_fp),
                "input_sha256": "",
                "output_sha256": "",
                "elevation_source_counts": {},
                "elevation_confidence_counts": {},
                "route_class_elevation_source_counts": {},
                "elevation_join_p50_m": "",
                "elevation_join_p95_m": "",
                "elevation_join_max_m": "",
                "raw_vs_calibrated_elevation_diff_p50_m": "",
                "raw_vs_calibrated_elevation_diff_p95_m": "",
                "raw_vs_calibrated_elevation_diff_max_m": "",
                "null_calibrated_elevation_rows": "",
                "slope_valid_rows": "",
                "slope_review_required_rows": "",
                "elevation_artifact_rows": "",
                "calibrated_cumulative_gain_m": "",
                "calibrated_cumulative_loss_m": "",
                "wrong_route_fallback_rows": "",
                "off_target_fallback_rows": "",
                "motion_artifact_gain_loss_excluded_rows": "",
                "profile_ambiguous_rows": "",
                "profile_dist_jump_rows": "",
                "elevation_join_hard_excluded_rows": "",
                "error": str(exc),
            }
            summaries.append(summary)
            print(f"[FAIL] {activity_id}: {exc}")

    batch_dir = out_dir / "_batch_summary"
    batch_dir.mkdir(parents=True, exist_ok=True)

    batch_csv = batch_dir / f"{route_folder}_v1k3_calibrated_elevation_summary.csv"
    batch_json = batch_dir / f"{route_folder}_v1k3_calibrated_elevation_summary.json"

    csv_rows = []
    for summary in summaries:
        row = dict(summary)
        for key in [
            "elevation_source_counts",
            "elevation_confidence_counts",
            "route_class_elevation_source_counts",
        ]:
            row[key] = json.dumps(row.get(key, {}), ensure_ascii=False)
        csv_rows.append(row)

    fieldnames = list(csv_rows[0].keys()) if csv_rows else []
    write_csv(batch_csv, csv_rows, fieldnames)
    batch_json.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")

    fail_n = sum(1 for summary in summaries if summary.get("status") != "PASS")
    print(f"summary_csv={batch_csv}")
    print(f"summary_json={batch_json}")
    print("status=PASS" if fail_n == 0 else f"status=FAIL fail_n={fail_n}")

    return 0 if fail_n == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
