# -*- coding: utf-8 -*-
"""
diagnose_activity_points_osm_nlsc_corrected_v1g_route_phase_ambiguity.py

V1G diagnosis only.

Purpose:
- Diagnose remaining low-confidence / non-usable points after v1f.
- Detect route phase ambiguity caused by overlapping uphill/downhill route corridor.
- Do NOT generate corrected v1g CSV.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd
import numpy as np


USABLE_STATUS_KEYWORDS = [
    "matched_core_clean",
    "matched_core_recovered_from_mainline_refit",
    "matched_core_recovered_from_summit_anchor",
    "matched_core_recovered_from_isolated_orange",
    "matched_core_recovered_from_safe_corridor",
]


EXCLUDED_STATUS_KEYWORDS = [
    "off_route_excursion",
    "route_endpoint_artifact",
]


def pick_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def to_num(s):
    return pd.to_numeric(s, errors="coerce")


def is_usable_status(status: str) -> bool:
    s = str(status)
    return any(k in s for k in USABLE_STATUS_KEYWORDS)


def is_excluded_status(status: str) -> bool:
    s = str(status)
    return any(k in s for k in EXCLUDED_STATUS_KEYWORDS)


def summarize_window(win: pd.DataFrame, route_col: str, elapsed_col: str, center_elapsed: float) -> dict:
    vals = to_num(win[route_col]).dropna()

    if len(vals) == 0:
        return {
            "count": 0,
            "min_route_dist_m": np.nan,
            "p25_route_dist_m": np.nan,
            "median_route_dist_m": np.nan,
            "p75_route_dist_m": np.nan,
            "max_route_dist_m": np.nan,
            "nearest_time_gap_sec": np.nan,
            "nearest_route_dist_m": np.nan,
        }

    elapsed_vals = to_num(win[elapsed_col])
    gaps = (elapsed_vals - center_elapsed).abs()
    nearest_idx = gaps.idxmin()

    return {
        "count": int(len(vals)),
        "min_route_dist_m": float(vals.min()),
        "p25_route_dist_m": float(vals.quantile(0.25)),
        "median_route_dist_m": float(vals.median()),
        "p75_route_dist_m": float(vals.quantile(0.75)),
        "max_route_dist_m": float(vals.max()),
        "nearest_time_gap_sec": float(gaps.loc[nearest_idx]),
        "nearest_route_dist_m": float(pd.to_numeric(win.loc[nearest_idx, route_col], errors="coerce")),
    }


def phase_hint(prev_med: float, next_med: float, prev_count: int, next_count: int) -> str:
    if prev_count < 2 or next_count < 2:
        return "insufficient_context"

    if pd.isna(prev_med) or pd.isna(next_med):
        return "insufficient_context"

    jump = abs(prev_med - next_med)

    if jump < 1500:
        return "no_large_phase_jump"

    # For qixing_lengshuikeng 37_1 known overlap:
    # uphill-like phase around 500-800, downhill-like phase around 3400-3600.
    if 400 <= prev_med <= 900 and 3200 <= next_med <= 3800:
        return "ambiguous_between_uphill_downhill"

    if 3200 <= prev_med <= 3800 and 400 <= next_med <= 900:
        return "ambiguous_between_downhill_uphill"

    return "large_route_dist_jump_other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-csv", required=True)
    ap.add_argument("--route-folder", required=True)
    ap.add_argument("--activity-id", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--max-offset-m", type=float, default=5.0)
    ap.add_argument("--phase-jump-threshold-m", type=float, default=1500.0)
    args = ap.parse_args()

    input_csv = Path(args.input_csv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_csv, encoding="utf-8-sig", low_memory=False)

    elapsed_col = pick_col(df, [
        "elapsed_sec",
        "elapsed_s",
        "timestamp_s",
        "time_sec",
    ])

    status_col = pick_col(df, [
        "route_context_model_status_v1f",
        "route_context_model_status_v1e",
        "route_context_model_status_v1d",
        "route_context_model_status_v1c",
        "route_context_match_status",
        "status",
        "match_status",
        "corrected_status",
    ])

    usable_col = pick_col(df, [
        "route_context_model_usable_v1f",
        "route_context_model_usable_v1e",
        "route_context_model_usable_v1d",
        "route_context_model_usable_v1c",
        "usable_on_route",
    ])

    offset_col = pick_col(df, [
        "offset_m",
        "route_context_model_offset_m",
        "offset_to_route_m",
    ])

    route_col = pick_col(df, [
        "route_dist_refit_m_v1f",
        "route_dist_refit_m_v1e",
        "route_dist_refit_m_v1d",
        "route_dist_refit_m",
        "reliable_route_dist_m",
        "projected_route_dist_m",
        "route_dist_m",
    ])

    activity_route_col = pick_col(df, [
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
        "status_col": status_col,
        "offset_col": offset_col,
        "route_col": route_col,
    }

    missing = [k for k, v in required.items() if v is None]
    if missing:
        print("ERROR: missing required columns:", missing)
        print("Available columns:")
        for c in df.columns:
            print(" -", c)
        raise SystemExit(1)


    df["_elapsed"] = to_num(df[elapsed_col])
    df["_offset"] = to_num(df[offset_col])
    df["_status"] = df[status_col].astype(str)

    if usable_col is not None:
        usable_raw = df[usable_col].astype(str).str.lower().str.strip()
        df["_usable"] = usable_raw.isin(["true", "1", "yes", "y"]) & to_num(df[route_col]).notna()
    else:
        df["_usable"] = df["_status"].apply(is_usable_status) & to_num(df[route_col]).notna()


    # Candidate low-confidence / non-usable points
    cand_mask = (
        df["_elapsed"].notna()
        & df["_offset"].notna()
        & (df["_offset"] <= args.max_offset_m)
        & (~df["_usable"])
    )

    candidates = df.loc[cand_mask].copy()

    rows = []

    for _, r in candidates.iterrows():
        elapsed = float(r["_elapsed"])
        status = str(r["_status"])
        offset = float(r["_offset"])

        excluded_time_range = (
            (4209 <= elapsed <= 4219)
            or (5138 <= elapsed <= 5148)
            or (elapsed >= 7382)
        )

        excluded_status = is_excluded_status(status)

        in_mainline_corridor = offset <= args.max_offset_m

        for window_sec in [10, 20, 30]:
            base = {
                "route_folder": args.route_folder,
                "activity_id": args.activity_id,
                "elapsed_sec": elapsed,
                "original_status": status,
                "offset_m": offset,
                "window_sec": window_sec,
                "route_dist_refit_m_v1f": pd.to_numeric(r.get("route_dist_refit_m_v1f", np.nan), errors="coerce"),
                "activity_route_dist_m": pd.to_numeric(r.get(activity_route_col, np.nan), errors="coerce") if activity_route_col else np.nan,
                "nearest_route_dist_m": pd.to_numeric(r.get(nearest_route_col, np.nan), errors="coerce") if nearest_route_col else np.nan,
                "in_mainline_corridor": bool(in_mainline_corridor),
                "excluded_time_range": bool(excluded_time_range),
                "excluded_status": bool(excluded_status),
            }

            if excluded_time_range:
                base.update({
                    "prev_count": 0,
                    "prev_median_route_dist_m": np.nan,
                    "prev_min_route_dist_m": np.nan,
                    "prev_max_route_dist_m": np.nan,
                    "next_count": 0,
                    "next_median_route_dist_m": np.nan,
                    "next_min_route_dist_m": np.nan,
                    "next_max_route_dist_m": np.nan,
                    "phase_jump_m": np.nan,
                    "phase_jump_detected": False,
                    "candidate_phase_hint": "excluded_time_range",
                    "dist_to_prev_phase_m": np.nan,
                    "dist_to_next_phase_m": np.nan,
                    "closer_phase": "unknown",
                    "recommended_action": "skip_excluded_time_range",
                })
                rows.append(base)
                continue

            if excluded_status:
                base.update({
                    "prev_count": 0,
                    "prev_median_route_dist_m": np.nan,
                    "prev_min_route_dist_m": np.nan,
                    "prev_max_route_dist_m": np.nan,
                    "next_count": 0,
                    "next_median_route_dist_m": np.nan,
                    "next_min_route_dist_m": np.nan,
                    "next_max_route_dist_m": np.nan,
                    "phase_jump_m": np.nan,
                    "phase_jump_detected": False,
                    "candidate_phase_hint": "excluded_status",
                    "dist_to_prev_phase_m": np.nan,
                    "dist_to_next_phase_m": np.nan,
                    "closer_phase": "unknown",
                    "recommended_action": "skip_excluded_status",
                })
                rows.append(base)
                continue

            if not in_mainline_corridor:
                base.update({
                    "prev_count": 0,
                    "prev_median_route_dist_m": np.nan,
                    "prev_min_route_dist_m": np.nan,
                    "prev_max_route_dist_m": np.nan,
                    "next_count": 0,
                    "next_median_route_dist_m": np.nan,
                    "next_min_route_dist_m": np.nan,
                    "next_max_route_dist_m": np.nan,
                    "phase_jump_m": np.nan,
                    "phase_jump_detected": False,
                    "candidate_phase_hint": "not_in_mainline_corridor",
                    "dist_to_prev_phase_m": np.nan,
                    "dist_to_next_phase_m": np.nan,
                    "closer_phase": "unknown",
                    "recommended_action": "skip_not_in_corridor",
                })
                rows.append(base)
                continue

            usable = df[df["_usable"]].copy()

            prev_win = usable[
                (usable["_elapsed"] >= elapsed - window_sec)
                & (usable["_elapsed"] < elapsed)
            ]

            next_win = usable[
                (usable["_elapsed"] > elapsed)
                & (usable["_elapsed"] <= elapsed + window_sec)
            ]

            prev = summarize_window(prev_win, route_col, "_elapsed", elapsed)
            nxt = summarize_window(next_win, route_col, "_elapsed", elapsed)

            prev_med = prev["median_route_dist_m"]
            next_med = nxt["median_route_dist_m"]
            prev_count = prev["count"]
            next_count = nxt["count"]

            if pd.isna(prev_med) or pd.isna(next_med):
                phase_jump = np.nan
                phase_jump_detected = False
            else:
                phase_jump = abs(prev_med - next_med)
                phase_jump_detected = (
                    prev_count >= 2
                    and next_count >= 2
                    and phase_jump >= args.phase_jump_threshold_m
                )

            hint = phase_hint(prev_med, next_med, prev_count, next_count)

            cand_route_candidates = []
            for c in ["route_dist_refit_m_v1f", activity_route_col, nearest_route_col]:
                if c and c in df.columns:
                    val = pd.to_numeric(r.get(c, np.nan), errors="coerce")
                    if pd.notna(val):
                        cand_route_candidates.append(float(val))

            cand_route = cand_route_candidates[0] if cand_route_candidates else np.nan

            if pd.notna(cand_route) and pd.notna(prev_med):
                dist_to_prev = abs(cand_route - prev_med)
            else:
                dist_to_prev = np.nan

            if pd.notna(cand_route) and pd.notna(next_med):
                dist_to_next = abs(cand_route - next_med)
            else:
                dist_to_next = np.nan

            if pd.isna(dist_to_prev) or pd.isna(dist_to_next):
                closer_phase = "unknown"
            elif abs(dist_to_prev - dist_to_next) <= 20:
                closer_phase = "tie"
            elif dist_to_prev < dist_to_next:
                closer_phase = "prev_phase"
            else:
                closer_phase = "next_phase"

            if prev_count < 2 or next_count < 2:
                recommended_action = "skip_insufficient_context"
            elif phase_jump_detected and in_mainline_corridor:
                recommended_action = "diagnose_only_route_phase_ambiguity_candidate"
            else:
                recommended_action = "diagnose_only_low_confidence_corridor_candidate"

            base.update({
                "prev_count": prev_count,
                "prev_median_route_dist_m": prev_med,
                "prev_min_route_dist_m": prev["min_route_dist_m"],
                "prev_max_route_dist_m": prev["max_route_dist_m"],
                "prev_nearest_time_gap_sec": prev["nearest_time_gap_sec"],
                "prev_nearest_route_dist_m": prev["nearest_route_dist_m"],

                "next_count": next_count,
                "next_median_route_dist_m": next_med,
                "next_min_route_dist_m": nxt["min_route_dist_m"],
                "next_max_route_dist_m": nxt["max_route_dist_m"],
                "next_nearest_time_gap_sec": nxt["nearest_time_gap_sec"],
                "next_nearest_route_dist_m": nxt["nearest_route_dist_m"],

                "phase_jump_m": phase_jump,
                "phase_jump_detected": bool(phase_jump_detected),
                "candidate_phase_hint": hint,
                "dist_to_prev_phase_m": dist_to_prev,
                "dist_to_next_phase_m": dist_to_next,
                "closer_phase": closer_phase,
                "recommended_action": recommended_action,
            })

            rows.append(base)

    out_df = pd.DataFrame(rows)

    out_fp = out_dir / f"{args.route_folder}_{args.activity_id}_route_phase_ambiguity_candidates.csv"
    out_df.to_csv(out_fp, index=False, encoding="utf-8-sig")

    print("V1G route phase ambiguity diagnosis written")
    print("input:", input_csv)
    print("output:", out_fp)
    print("rows:", len(out_df))

    if len(out_df) > 0:
        print()
        print("--- recommended_action summary ---")
        print(out_df["recommended_action"].value_counts(dropna=False).to_string())

        print()
        print("--- key elapsed 978 / 980 if present ---")
        key = out_df[out_df["elapsed_sec"].isin([978.0, 980.0])]
        if len(key) == 0:
            print("elapsed 978 / 980 not found in candidates")
        else:
            cols = [
                "elapsed_sec",
                "original_status",
                "offset_m",
                "window_sec",
                "prev_count",
                "prev_median_route_dist_m",
                "next_count",
                "next_median_route_dist_m",
                "phase_jump_m",
                "phase_jump_detected",
                "candidate_phase_hint",
                "closer_phase",
                "recommended_action",
            ]
            print(key[cols].to_string(index=False))


if __name__ == "__main__":
    main()