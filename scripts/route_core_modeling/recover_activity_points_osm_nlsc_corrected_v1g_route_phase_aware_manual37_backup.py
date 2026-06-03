# -*- coding: utf-8 -*-
"""
recover_activity_points_osm_nlsc_corrected_v1g_route_phase_aware.py

V1G route phase aware recovery.

Purpose:
- Recover route phase ambiguity points confirmed by V1G diagnosis.
- Preserve temporal order: elapsed_sec, timestamp_s, activity order, HR, GPS are NOT changed.
- Refit only the route-distance representation to the spatial route segment where the point actually lies.

Current conservative scope:
- qixing_lengshuikeng / activity 37_1
- elapsed_sec 978–981
- manually confirmed spatial target:
    downhill_required_segment
- This means the activity happened during the uphill-time period,
  but the spatial route segment belongs to the mapped/NLSC downhill-required corridor.

Input:
- v1f corrected activity points CSV
- v1g diagnosis candidates CSV

Output:
- v1g corrected activity points CSV
"""

from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd
import numpy as np


RECOVERY_STATUS = "matched_core_recovered_from_route_phase_ambiguity"
RECOVERY_REASON = "spatial_corridor_supports_downhill_required_segment_temporal_order_preserved"
RECOVERY_METHOD = "v1g_route_phase_aware_spatial_segment_refit_manual_override"


def pick_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def to_num(s):
    return pd.to_numeric(s, errors="coerce")


def bool_like_true(v) -> bool:
    return str(v).strip().lower() in ["true", "1", "yes", "y"]


def estimate_target_route_dist_from_next_phase(
    df: pd.DataFrame,
    elapsed: float,
    route_col: str,
    elapsed_col: str,
    usable_col: str,
    lookahead_sec: float = 10.0,
) -> float:
    """
    Estimate route_dist for a candidate point using nearby usable points after the candidate.

    This is intentionally NOT a global interpolation across prev/next phases.
    It only uses the spatially selected next-phase / downhill-required segment anchors.

    Strategy:
    - Find usable anchors within (elapsed, elapsed + lookahead_sec].
    - If at least 2 anchors exist, estimate local route speed using the nearest two anchors.
      Then back-project route_dist to candidate elapsed.
    - If only 1 anchor exists, use that anchor route_dist.
    - If no anchor exists, return NaN.
    """

    usable = df[
        df[usable_col].apply(bool_like_true)
        & to_num(df[route_col]).notna()
        & to_num(df[elapsed_col]).notna()
    ].copy()

    usable["_elapsed_tmp"] = to_num(usable[elapsed_col])
    usable["_route_tmp"] = to_num(usable[route_col])

    next_anchors = usable[
        (usable["_elapsed_tmp"] > elapsed)
        & (usable["_elapsed_tmp"] <= elapsed + lookahead_sec)
    ].sort_values("_elapsed_tmp")

    if len(next_anchors) == 0:
        return np.nan

    if len(next_anchors) == 1:
        return float(next_anchors.iloc[0]["_route_tmp"])

    a = next_anchors.iloc[0]
    b = next_anchors.iloc[1]

    t1 = float(a["_elapsed_tmp"])
    r1 = float(a["_route_tmp"])
    t2 = float(b["_elapsed_tmp"])
    r2 = float(b["_route_tmp"])

    if t2 == t1:
        return r1

    local_speed = (r2 - r1) / (t2 - t1)
    estimated = r1 - local_speed * (t1 - elapsed)

    return float(estimated)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-csv", required=True)
    ap.add_argument("--diagnosis-csv", required=True)
    ap.add_argument("--route-folder", required=True)
    ap.add_argument("--activity-id", required=True)
    ap.add_argument("--out-dir", required=True)

    # Conservative manual override scope.
    ap.add_argument("--recover-start-elapsed", type=float, default=978.0)
    ap.add_argument("--recover-end-elapsed", type=float, default=981.0)
    ap.add_argument("--max-offset-m", type=float, default=5.0)
    ap.add_argument("--diagnosis-window-sec", type=int, default=30)
    ap.add_argument("--lookahead-sec", type=float, default=10.0)

    args = ap.parse_args()

    input_csv = Path(args.input_csv)
    diagnosis_csv = Path(args.diagnosis_csv)
    out_dir = Path(args.out_dir) / args.route_folder / args.activity_id
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_csv, encoding="utf-8-sig", low_memory=False)
    diag = pd.read_csv(diagnosis_csv, encoding="utf-8-sig", low_memory=False)

    elapsed_col = pick_col(df, ["elapsed_sec", "elapsed_s", "timestamp_s", "time_sec"])
    offset_col = pick_col(df, ["offset_m", "route_context_model_offset_m", "offset_to_route_m"])

    status_v1f_col = pick_col(df, [
        "route_context_model_status_v1f",
        "route_context_model_status_v1e",
        "route_context_model_status_v1d",
        "route_context_model_status_v1c",
        "route_context_match_status",
    ])

    usable_v1f_col = pick_col(df, [
        "route_context_model_usable_v1f",
        "route_context_model_usable_v1e",
        "route_context_model_usable_v1d",
        "route_context_model_usable_v1c",
        "usable_on_route",
    ])

    route_v1f_col = pick_col(df, [
        "route_dist_refit_m_v1f",
        "route_dist_refit_m_v1e",
        "route_dist_refit_m_v1d",
        "route_dist_refit_m",
        "reliable_route_dist_m",
        "projected_route_dist_m",
        "route_dist_m",
    ])

    nearest_route_col = pick_col(df, [
        "nearest_route_dist_m",
        "nearest_route_dist",
        "nearest_dist_m",
    ])

    required = {
        "elapsed_col": elapsed_col,
        "offset_col": offset_col,
        "status_v1f_col": status_v1f_col,
        "usable_v1f_col": usable_v1f_col,
        "route_v1f_col": route_v1f_col,
    }

    missing = [k for k, v in required.items() if v is None]
    if missing:
        print("ERROR: missing required columns:", missing)
        print("Available columns:")
        for c in df.columns:
            print(" -", c)
        raise SystemExit(1)

    # Prepare v1g columns by copying v1f as baseline.
    df["route_context_model_status_v1g"] = df[status_v1f_col]
    df["route_context_model_usable_v1g"] = df[usable_v1f_col]
    df["route_context_model_reason_v1g"] = df.get(
        "route_context_model_reason_v1f",
        ""
    )

    df["route_dist_refit_m_v1g"] = df[route_v1f_col]
    df["route_dist_refit_method_v1g"] = df.get(
        "route_dist_refit_method_v1f",
        ""
    )

    df["route_phase_ambiguity_detected_v1g"] = False
    df["spatial_route_phase_target_v1g"] = ""
    df["temporal_phase_preserved_v1g"] = True
    df["route_phase_recovery_reason_v1g"] = ""
    df["route_phase_recovery_source_v1g"] = ""
    df["route_phase_recovery_applied_v1g"] = False
    df["route_phase_recovery_block_reason_v1g"] = ""

    df["_elapsed"] = to_num(df[elapsed_col])
    df["_offset"] = to_num(df[offset_col])

    # Diagnosis filter:
    # Use window_sec = 30 only to avoid triple-applying same candidate.
    diag["_elapsed"] = to_num(diag["elapsed_sec"])
    diag["_offset"] = to_num(diag["offset_m"])
    diag["_window"] = to_num(diag["window_sec"])

    diag_ok = diag[
        (diag["_window"] == args.diagnosis_window_sec)
        & (diag["recommended_action"] == "diagnose_only_route_phase_ambiguity_candidate")
        & (diag["phase_jump_detected"].astype(str).str.lower().isin(["true", "1", "yes", "y"]))
        & (diag["_offset"] <= args.max_offset_m)
        & (diag["_elapsed"] >= args.recover_start_elapsed)
        & (diag["_elapsed"] <= args.recover_end_elapsed)
    ].copy()

    recover_elapsed_set = set(float(x) for x in diag_ok["_elapsed"].dropna().tolist())

    applied_rows = []

    for idx, r in df.iterrows():
        elapsed = r["_elapsed"]

        if pd.isna(elapsed):
            continue

        elapsed_f = float(elapsed)

        if elapsed_f < args.recover_start_elapsed or elapsed_f > args.recover_end_elapsed:
            continue

        if elapsed_f not in recover_elapsed_set:
            df.at[idx, "route_phase_recovery_block_reason_v1g"] = "not_confirmed_by_v1g_diagnosis"
            continue

        offset = r["_offset"]
        if pd.isna(offset) or float(offset) > args.max_offset_m:
            df.at[idx, "route_phase_recovery_block_reason_v1g"] = "offset_exceeds_v1g_limit"
            continue

        # Core idea:
        # We do NOT change temporal order.
        # We spatially assign this candidate to the manually confirmed downhill-required segment.
        # Use local usable anchors after the candidate, which are on the selected mapped segment.
        estimated_route = estimate_target_route_dist_from_next_phase(
            df=df,
            elapsed=elapsed_f,
            route_col=route_v1f_col,
            elapsed_col=elapsed_col,
            usable_col=usable_v1f_col,
            lookahead_sec=args.lookahead_sec,
        )

        if pd.isna(estimated_route):
            # Fallback: use nearest_route_dist_m if available.
            if nearest_route_col is not None:
                nearest_val = pd.to_numeric(r.get(nearest_route_col, np.nan), errors="coerce")
                if pd.notna(nearest_val):
                    estimated_route = float(nearest_val)

        if pd.isna(estimated_route):
            df.at[idx, "route_phase_recovery_block_reason_v1g"] = "no_target_route_dist_available"
            continue

        df.at[idx, "route_context_model_status_v1g"] = RECOVERY_STATUS
        df.at[idx, "route_context_model_usable_v1g"] = True
        df.at[idx, "route_context_model_reason_v1g"] = RECOVERY_REASON
        df.at[idx, "route_dist_refit_m_v1g"] = estimated_route
        df.at[idx, "route_dist_refit_method_v1g"] = RECOVERY_METHOD

        df.at[idx, "route_phase_ambiguity_detected_v1g"] = True
        df.at[idx, "spatial_route_phase_target_v1g"] = "downhill_required_segment"
        df.at[idx, "temporal_phase_preserved_v1g"] = True
        df.at[idx, "route_phase_recovery_reason_v1g"] = RECOVERY_REASON
        df.at[idx, "route_phase_recovery_source_v1g"] = "manual_spatial_route_segment_override_elapsed_978_981"
        df.at[idx, "route_phase_recovery_applied_v1g"] = True
        df.at[idx, "route_phase_recovery_block_reason_v1g"] = ""

        applied_rows.append({
            "elapsed_sec": elapsed_f,
            "offset_m": float(offset),
            "original_status_v1f": str(r.get(status_v1f_col, "")),
            "original_route_dist_refit_m_v1f": pd.to_numeric(r.get(route_v1f_col, np.nan), errors="coerce"),
            "route_dist_refit_m_v1g": estimated_route,
            "spatial_route_phase_target_v1g": "downhill_required_segment",
            "temporal_phase_preserved_v1g": True,
            "route_context_model_status_v1g": RECOVERY_STATUS,
            "route_context_model_reason_v1g": RECOVERY_REASON,
        })

    # Remove internal helper columns.
    df = df.drop(columns=["_elapsed", "_offset"], errors="ignore")

    out_fp = out_dir / f"{args.route_folder}_{args.activity_id}_activity_points_osm_nlsc_corrected_v1g.csv"
    df.to_csv(out_fp, index=False, encoding="utf-8-sig")

    applied_df = pd.DataFrame(applied_rows)
    applied_fp = out_dir / f"{args.route_folder}_{args.activity_id}_activity_points_osm_nlsc_corrected_v1g_recovery_applied_rows.csv"
    applied_df.to_csv(applied_fp, index=False, encoding="utf-8-sig")

    print("V1G route phase aware recovery written")
    print("input:", input_csv)
    print("diagnosis:", diagnosis_csv)
    print("output:", out_fp)
    print("applied rows csv:", applied_fp)
    print("applied rows:", len(applied_df))

    if len(applied_df) > 0:
        print()
        print("--- applied rows ---")
        print(applied_df.to_string(index=False))


if __name__ == "__main__":
    main()
