#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
IB3K-RC v1k5 aggregated low-speed elevation step supplement policy.

Purpose:
- Start from v1k3 calibrated elevation outputs.
- Preserve all v1k3 fields and row order.
- Do not overwrite v1k3 calibrated_cumulative_gain_m / calibrated_cumulative_loss_m.
- Add supplement-only aggregated elevation step fields.

Policy:
- v1k3 remains the baseline.
- v1k5 only supplements rows that v1k3 excluded because of STEP_DISTANCE_LT_3M.
- v1k5 does not re-compute the whole activity gain/loss from zero.
- v1k5 does not include wrong-route, off-target, unknown, stopped, profile-jump, artifact, or hard-excluded rows.
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


ALLOWED_ROUTE_CLASSES = {"MAINLINE_CORE", "MAINLINE_SUMMIT_STAY", "CONNECTOR"}
ALLOWED_MOVEMENT_STATES = {"MOVING", "SLOW_MOVING"}

HARD_EXCLUSION_TOKENS = [
    "ELEVATION_JOIN_DIST_GT_10M_HARD_EXCLUDED",
    "PROFILE_DISTANCE_JUMP_HARD_EXCLUDED",
    "ELEVATION_ARTIFACT_DELTA_GT_10M",
]

SUPPLEMENT_FIELDS = [
    "agg_supplement_step_valid",
    "agg_supplement_step_review_only",
    "agg_supplement_step_id",
    "agg_supplement_step_reason",
    "agg_supplement_start_raw_point_index",
    "agg_supplement_end_raw_point_index",
    "agg_supplement_start_elapsed_sec",
    "agg_supplement_end_elapsed_sec",
    "agg_supplement_duration_sec",
    "agg_supplement_horizontal_distance_m",
    "agg_supplement_start_elevation_m",
    "agg_supplement_end_elevation_m",
    "agg_supplement_delta_elevation_m",
    "agg_supplement_slope_pct",
    "agg_supplemental_gain_m",
    "agg_supplemental_loss_m",
    "agg_total_gain_m",
    "agg_total_loss_m",
    "agg_supplement_excluded_reason",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build IB3K-RC v1k5 supplement-only aggregated low-speed elevation step dataset."
    )
    parser.add_argument("--route-folder", required=True)
    parser.add_argument("--activity-id", default="")
    parser.add_argument("--activity-ids", default="")
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--out-dir", required=True)

    parser.add_argument("--min-agg-horizontal-m", type=float, default=15.0)
    parser.add_argument("--min-agg-duration-sec", type=float, default=10.0)
    parser.add_argument("--min-agg-delta-ele-m", type=float, default=2.0)
    parser.add_argument("--gain-loss-delta-threshold-m", type=float, default=1.0)
    parser.add_argument("--max-abs-slope-pct-for-gain-loss", type=float, default=45.0)

    return parser.parse_args()


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
    if v is None:
        return False
    return str(v).strip().lower() in {"true", "1", "yes", "y"}


def fmt_float(v: Optional[float], ndigits: int = 6) -> str:
    if v is None or not math.isfinite(v):
        return ""
    return f"{v:.{ndigits}f}".rstrip("0").rstrip(".")


def sha256_file(fp: Path) -> str:
    h = hashlib.sha256()
    with fp.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(fp: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    with fp.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    return rows, fieldnames


def write_csv(fp: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    fp.parent.mkdir(parents=True, exist_ok=True)
    with fp.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def find_input_csv(input_root: Path, route_folder: str, activity_id: str) -> Path:
    folder = input_root / route_folder / activity_id
    expected = folder / f"{route_folder}_{activity_id}_calibrated_elevation_v1k3.csv"
    if expected.exists():
        return expected

    matches = list(folder.glob("*_calibrated_elevation_v1k3.csv"))
    if len(matches) == 1:
        return matches[0]

    raise FileNotFoundError(f"Cannot find v1k3 CSV for {route_folder}/{activity_id}: {folder}")


def has_hard_exclusion(row: Dict[str, str]) -> bool:
    reason = row.get("gain_loss_excluded_reason", "") or ""
    return any(tok in reason for tok in HARD_EXCLUSION_TOKENS)


def row_exclusion_reason(row: Dict[str, str]) -> str:
    reasons: List[str] = []

    route_class = row.get("route_class", "")
    movement_state = row.get("movement_state", "")
    gain_loss_reason = row.get("gain_loss_excluded_reason", "") or ""

    if route_class not in ALLOWED_ROUTE_CLASSES:
        reasons.append(f"ROUTE_CLASS_EXCLUDED:{route_class}")

    if movement_state not in ALLOWED_MOVEMENT_STATES:
        reasons.append(f"MOVEMENT_STATE_EXCLUDED:{movement_state}")

    if to_bool(row.get("elevation_step_valid")):
        reasons.append("V1K3_ALREADY_VALID_STEP")

    if "STEP_DISTANCE_LT_3M" not in gain_loss_reason:
        reasons.append("NOT_STEP_DISTANCE_LT_3M_EXCLUDED")

    if to_bool(row.get("elevation_profile_dist_jump_flag")):
        reasons.append("PROFILE_DISTANCE_JUMP_SOFT_EXCLUDED_FOR_SUPPLEMENT")

    if not to_bool(row.get("motion_representative_flag")):
        reasons.append("MOTION_REPRESENTATIVE_FALSE")

    if not to_bool(row.get("time_interval_valid")):
        reasons.append("TIME_INTERVAL_INVALID")

    if to_bool(row.get("motion_artifact_flag")):
        reasons.append("MOTION_ARTIFACT_FLAG_TRUE")

    if to_bool(row.get("elevation_artifact_flag")):
        reasons.append("ELEVATION_ARTIFACT_FLAG_TRUE")

    if has_hard_exclusion(row):
        reasons.append("V1K3_HARD_EXCLUSION")

    if to_float(row.get("calibrated_elevation_m")) is None:
        reasons.append("MISSING_CALIBRATED_ELEVATION")

    if to_float(row.get("elapsed_sec")) is None:
        reasons.append("MISSING_ELAPSED_SEC")

    return ";".join(reasons)


def is_eligible(row: Dict[str, str]) -> bool:
    return row_exclusion_reason(row) == ""


def init_supplement_fields(row: Dict[str, Any], baseline_gain: float, baseline_loss: float) -> None:
    for f in SUPPLEMENT_FIELDS:
        row[f] = ""
    row["agg_supplement_step_valid"] = "False"
    row["agg_supplement_step_review_only"] = "False"
    row["agg_supplemental_gain_m"] = "0"
    row["agg_supplemental_loss_m"] = "0"
    row["agg_total_gain_m"] = fmt_float(baseline_gain, 6)
    row["agg_total_loss_m"] = fmt_float(baseline_loss, 6)


def get_original_final_gain_loss(rows: List[Dict[str, str]]) -> Tuple[float, float]:
    gain = 0.0
    loss = 0.0
    for r in reversed(rows):
        g = to_float(r.get("calibrated_cumulative_gain_m"))
        l = to_float(r.get("calibrated_cumulative_loss_m"))
        if g is not None or l is not None:
            gain = g or 0.0
            loss = l or 0.0
            break
    return gain, loss


def reset_buffer(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "start_row": row,
        "end_row": row,
        "start_elapsed": to_float(row.get("elapsed_sec")),
        "end_elapsed": to_float(row.get("elapsed_sec")),
        "start_ele": to_float(row.get("calibrated_elevation_m")),
        "end_ele": to_float(row.get("calibrated_elevation_m")),
        "horizontal_m": 0.0,
        "rows_n": 1,
    }


def buffer_ready(
    buf: Dict[str, Any],
    min_horizontal_m: float,
    min_duration_sec: float,
    min_delta_ele_m: float,
) -> Tuple[bool, str]:
    start_elapsed = buf.get("start_elapsed")
    end_elapsed = buf.get("end_elapsed")
    start_ele = buf.get("start_ele")
    end_ele = buf.get("end_ele")
    horizontal_m = float(buf.get("horizontal_m") or 0.0)

    if start_elapsed is None or end_elapsed is None or start_ele is None or end_ele is None:
        return False, ""

    duration = max(0.0, end_elapsed - start_elapsed)
    delta_ele = end_ele - start_ele

    if (
        horizontal_m >= min_horizontal_m
        and duration >= min_duration_sec
        and abs(delta_ele) >= min_delta_ele_m
    ):
        return True, "SUPPLEMENT_LOW_SPEED_AGGREGATED_STEP"

    return False, ""


def finalize_buffer_step(
    buf: Dict[str, Any],
    step_id: int,
    reason: str,
    supplemental_gain: float,
    supplemental_loss: float,
    baseline_gain: float,
    baseline_loss: float,
    gain_loss_delta_threshold_m: float,
    max_abs_slope_pct_for_gain_loss: float,
) -> Tuple[int, float, float, bool]:
    start_row = buf["start_row"]
    end_row = buf["end_row"]

    start_elapsed = buf.get("start_elapsed")
    end_elapsed = buf.get("end_elapsed")
    start_ele = buf.get("start_ele")
    end_ele = buf.get("end_ele")
    horizontal_m = float(buf.get("horizontal_m") or 0.0)

    if start_elapsed is None or end_elapsed is None or start_ele is None or end_ele is None:
        return step_id, supplemental_gain, supplemental_loss, False

    duration = max(0.0, end_elapsed - start_elapsed)
    delta_ele = end_ele - start_ele

    slope_pct = None
    if horizontal_m > 0:
        slope_pct = (delta_ele / horizontal_m) * 100.0

    step_id += 1

    review_only = False
    counted = False
    step_reason = reason

    if slope_pct is not None and abs(slope_pct) > max_abs_slope_pct_for_gain_loss:
        review_only = True
        step_reason += ";SUPPLEMENT_SLOPE_GT_MAX_REVIEW_ONLY"
    else:
        if delta_ele >= gain_loss_delta_threshold_m:
            supplemental_gain += delta_ele
            counted = True
        elif delta_ele <= -gain_loss_delta_threshold_m:
            supplemental_loss += abs(delta_ele)
            counted = True

    end_row["agg_supplement_step_valid"] = "True" if counted else "False"
    end_row["agg_supplement_step_review_only"] = "True" if review_only else "False"
    end_row["agg_supplement_step_id"] = str(step_id)
    end_row["agg_supplement_step_reason"] = step_reason
    end_row["agg_supplement_start_raw_point_index"] = start_row.get("raw_point_index", "")
    end_row["agg_supplement_end_raw_point_index"] = end_row.get("raw_point_index", "")
    end_row["agg_supplement_start_elapsed_sec"] = fmt_float(start_elapsed, 3)
    end_row["agg_supplement_end_elapsed_sec"] = fmt_float(end_elapsed, 3)
    end_row["agg_supplement_duration_sec"] = fmt_float(duration, 3)
    end_row["agg_supplement_horizontal_distance_m"] = fmt_float(horizontal_m, 6)
    end_row["agg_supplement_start_elevation_m"] = fmt_float(start_ele, 6)
    end_row["agg_supplement_end_elevation_m"] = fmt_float(end_ele, 6)
    end_row["agg_supplement_delta_elevation_m"] = fmt_float(delta_ele, 6)
    end_row["agg_supplement_slope_pct"] = fmt_float(slope_pct, 6)
    end_row["agg_supplemental_gain_m"] = fmt_float(supplemental_gain, 6)
    end_row["agg_supplemental_loss_m"] = fmt_float(supplemental_loss, 6)
    end_row["agg_total_gain_m"] = fmt_float(baseline_gain + supplemental_gain, 6)
    end_row["agg_total_loss_m"] = fmt_float(baseline_loss + supplemental_loss, 6)

    return step_id, supplemental_gain, supplemental_loss, counted


def process_activity(
    route_folder: str,
    activity_id: str,
    input_root: Path,
    out_dir: Path,
    min_horizontal_m: float,
    min_duration_sec: float,
    min_delta_ele_m: float,
    gain_loss_delta_threshold_m: float,
    max_abs_slope_pct_for_gain_loss: float,
) -> Dict[str, Any]:
    in_fp = find_input_csv(input_root, route_folder, activity_id)
    input_sha = sha256_file(in_fp)

    rows, fields = read_csv(in_fp)
    rows_out: List[Dict[str, Any]] = [dict(r) for r in rows]

    baseline_gain, baseline_loss = get_original_final_gain_loss(rows)

    for row in rows_out:
        init_supplement_fields(row, baseline_gain, baseline_loss)

    step_id = 0
    supplemental_gain = 0.0
    supplemental_loss = 0.0

    buf: Optional[Dict[str, Any]] = None

    eligible_rows = 0
    excluded_counter: Counter[str] = Counter()
    counted_steps = 0
    review_only_steps = 0

    for row in rows_out:
        eligible = is_eligible(row)

        if not eligible:
            reason = row_exclusion_reason(row)
            row["agg_supplement_excluded_reason"] = reason
            excluded_counter[reason] += 1
            buf = None
            row["agg_supplemental_gain_m"] = fmt_float(supplemental_gain, 6)
            row["agg_supplemental_loss_m"] = fmt_float(supplemental_loss, 6)
            row["agg_total_gain_m"] = fmt_float(baseline_gain + supplemental_gain, 6)
            row["agg_total_loss_m"] = fmt_float(baseline_loss + supplemental_loss, 6)
            continue

        eligible_rows += 1

        elapsed = to_float(row.get("elapsed_sec"))
        ele = to_float(row.get("calibrated_elevation_m"))
        step_dist = to_float(row.get("calibrated_step_distance_m")) or 0.0

        if buf is None:
            buf = reset_buffer(row)
            row["agg_supplemental_gain_m"] = fmt_float(supplemental_gain, 6)
            row["agg_supplemental_loss_m"] = fmt_float(supplemental_loss, 6)
            row["agg_total_gain_m"] = fmt_float(baseline_gain + supplemental_gain, 6)
            row["agg_total_loss_m"] = fmt_float(baseline_loss + supplemental_loss, 6)
            continue

        buf["end_row"] = row
        buf["end_elapsed"] = elapsed
        buf["end_ele"] = ele
        buf["horizontal_m"] = float(buf.get("horizontal_m") or 0.0) + max(0.0, step_dist)
        buf["rows_n"] = int(buf.get("rows_n") or 0) + 1

        ready, reason = buffer_ready(
            buf,
            min_horizontal_m=min_horizontal_m,
            min_duration_sec=min_duration_sec,
            min_delta_ele_m=min_delta_ele_m,
        )

        if ready:
            before_gain = supplemental_gain
            before_loss = supplemental_loss

            step_id, supplemental_gain, supplemental_loss, counted = finalize_buffer_step(
                buf=buf,
                step_id=step_id,
                reason=reason,
                supplemental_gain=supplemental_gain,
                supplemental_loss=supplemental_loss,
                baseline_gain=baseline_gain,
                baseline_loss=baseline_loss,
                gain_loss_delta_threshold_m=gain_loss_delta_threshold_m,
                max_abs_slope_pct_for_gain_loss=max_abs_slope_pct_for_gain_loss,
            )

            if counted:
                counted_steps += 1
            else:
                review_only_steps += 1

            buf = reset_buffer(row)

        row["agg_supplemental_gain_m"] = fmt_float(supplemental_gain, 6)
        row["agg_supplemental_loss_m"] = fmt_float(supplemental_loss, 6)
        row["agg_total_gain_m"] = fmt_float(baseline_gain + supplemental_gain, 6)
        row["agg_total_loss_m"] = fmt_float(baseline_loss + supplemental_loss, 6)

    out_activity_dir = out_dir / route_folder / activity_id
    out_activity_dir.mkdir(parents=True, exist_ok=True)

    out_csv = out_activity_dir / f"{route_folder}_{activity_id}_calibrated_elevation_v1k5.csv"
    out_summary = out_activity_dir / f"{route_folder}_{activity_id}_calibrated_elevation_v1k5_summary.json"
    out_provenance = out_activity_dir / f"{route_folder}_{activity_id}_calibrated_elevation_v1k5_provenance.json"

    out_fields = list(fields)
    for f in SUPPLEMENT_FIELDS:
        if f not in out_fields:
            out_fields.append(f)

    write_csv(out_csv, rows_out, out_fields)

    supplement_steps = [
        r for r in rows_out
        if r.get("agg_supplement_step_id", "").strip() != ""
    ]
    supplement_valid_steps = [
        r for r in rows_out
        if r.get("agg_supplement_step_valid") == "True"
    ]
    supplement_review_steps = [
        r for r in rows_out
        if r.get("agg_supplement_step_review_only") == "True"
    ]

    summary = {
        "activity_id": activity_id,
        "status": "PASS",
        "rows": len(rows_out),
        "input_csv": str(in_fp),
        "output_csv": str(out_csv),
        "input_sha256": input_sha,
        "row_count_preserved": len(rows) == len(rows_out),
        "field_count_in": len(fields),
        "field_count_out": len(out_fields),
        "eligible_rows": eligible_rows,
        "supplement_candidate_steps": len(supplement_steps),
        "supplement_valid_steps": len(supplement_valid_steps),
        "supplement_review_only_steps": len(supplement_review_steps),
        "baseline_v1k3_cumulative_gain_m": baseline_gain,
        "baseline_v1k3_cumulative_loss_m": baseline_loss,
        "supplemental_gain_m": supplemental_gain,
        "supplemental_loss_m": supplemental_loss,
        "agg_total_gain_m": baseline_gain + supplemental_gain,
        "agg_total_loss_m": baseline_loss + supplemental_loss,
        "gain_delta_vs_v1k3_m": supplemental_gain,
        "loss_delta_vs_v1k3_m": supplemental_loss,
        "excluded_reason_counts": dict(excluded_counter),
        "policy": {
            "mode": "supplement_only",
            "allowed_route_classes": sorted(ALLOWED_ROUTE_CLASSES),
            "allowed_movement_states": sorted(ALLOWED_MOVEMENT_STATES),
            "requires_v1k3_step_distance_lt_3m_exclusion": True,
            "excludes_v1k3_elevation_step_valid_true": True,
            "excludes_profile_dist_jump_flag": True,
            "min_agg_horizontal_m": min_horizontal_m,
            "min_agg_duration_sec": min_duration_sec,
            "min_agg_delta_ele_m": min_delta_ele_m,
            "gain_loss_delta_threshold_m": gain_loss_delta_threshold_m,
            "max_abs_slope_pct_for_gain_loss": max_abs_slope_pct_for_gain_loss,
            "hard_exclusion_tokens": HARD_EXCLUSION_TOKENS,
        },
    }

    out_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    provenance = {
        "script": "scripts/ib3_activity_environment/ib3a_rc_build_calibrated_elevation_v1k5.py",
        "purpose": "supplement-only aggregated low-speed elevation step policy on top of v1k3",
        "input_csv": str(in_fp),
        "output_csv": str(out_csv),
        "input_sha256": input_sha,
        "immutability": [
            "v1k3 input CSV is read-only",
            "v1k3 calibrated_cumulative_gain_m/loss_m are not overwritten",
            "all original rows and fields are preserved",
            "new fields are appended with agg_supplement_* and agg_total_* prefixes",
            "v1k5 totals are v1k3 baseline plus supplement-only gain/loss",
        ],
    }
    out_provenance.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")

    return summary


def write_batch_summary(route_folder: str, out_dir: Path, summaries: List[Dict[str, Any]]) -> Tuple[Path, Path]:
    batch_dir = out_dir / "_batch_summary"
    batch_dir.mkdir(parents=True, exist_ok=True)

    out_csv = batch_dir / f"{route_folder}_v1k5_aggregated_elevation_step_summary.csv"
    out_json = batch_dir / f"{route_folder}_v1k5_aggregated_elevation_step_summary.json"

    csv_rows: List[Dict[str, Any]] = []
    for s in summaries:
        row = dict(s)
        row["excluded_reason_counts"] = json.dumps(row.get("excluded_reason_counts", {}), ensure_ascii=False)
        row["policy"] = json.dumps(row.get("policy", {}), ensure_ascii=False)
        csv_rows.append(row)

    fieldnames = list(csv_rows[0].keys()) if csv_rows else []
    write_csv(out_csv, csv_rows, fieldnames)
    out_json.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")

    return out_csv, out_json


def main() -> int:
    args = parse_args()

    route_folder = args.route_folder
    input_root = Path(args.input_root)
    out_dir = Path(args.out_dir)

    if args.activity_ids.strip():
        activity_ids = [x.strip() for x in args.activity_ids.split(",") if x.strip()]
    elif args.activity_id.strip():
        activity_ids = [args.activity_id.strip()]
    else:
        raise ValueError("Provide --activity-id or --activity-ids")

    summaries: List[Dict[str, Any]] = []
    fail_n = 0

    for activity_id in activity_ids:
        try:
            summary = process_activity(
                route_folder=route_folder,
                activity_id=activity_id,
                input_root=input_root,
                out_dir=out_dir,
                min_horizontal_m=args.min_agg_horizontal_m,
                min_duration_sec=args.min_agg_duration_sec,
                min_delta_ele_m=args.min_agg_delta_ele_m,
                gain_loss_delta_threshold_m=args.gain_loss_delta_threshold_m,
                max_abs_slope_pct_for_gain_loss=args.max_abs_slope_pct_for_gain_loss,
            )
            summaries.append(summary)
            print(
                f"[PASS] {activity_id}: "
                f"rows={summary['rows']} "
                f"supp_steps={summary['supplement_valid_steps']} "
                f"review_steps={summary['supplement_review_only_steps']} "
                f"base={summary['baseline_v1k3_cumulative_gain_m']:.3f}/{summary['baseline_v1k3_cumulative_loss_m']:.3f} "
                f"supp={summary['supplemental_gain_m']:.3f}/{summary['supplemental_loss_m']:.3f} "
                f"total={summary['agg_total_gain_m']:.3f}/{summary['agg_total_loss_m']:.3f}"
            )
        except Exception as exc:
            fail_n += 1
            summary = {
                "activity_id": activity_id,
                "status": "FAIL",
                "rows": 0,
                "input_csv": "",
                "output_csv": "",
                "input_sha256": "",
                "row_count_preserved": False,
                "field_count_in": "",
                "field_count_out": "",
                "eligible_rows": "",
                "supplement_candidate_steps": "",
                "supplement_valid_steps": "",
                "supplement_review_only_steps": "",
                "baseline_v1k3_cumulative_gain_m": "",
                "baseline_v1k3_cumulative_loss_m": "",
                "supplemental_gain_m": "",
                "supplemental_loss_m": "",
                "agg_total_gain_m": "",
                "agg_total_loss_m": "",
                "gain_delta_vs_v1k3_m": "",
                "loss_delta_vs_v1k3_m": "",
                "excluded_reason_counts": {"ERROR": str(exc)},
                "policy": {},
            }
            summaries.append(summary)
            print(f"[FAIL] {activity_id}: {exc}")

    batch_csv, batch_json = write_batch_summary(route_folder, out_dir, summaries)

    print(f"summary_csv={batch_csv}")
    print(f"summary_json={batch_json}")
    print("status=PASS" if fail_n == 0 else f"status=FAIL fail_n={fail_n}")

    return 0 if fail_n == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
