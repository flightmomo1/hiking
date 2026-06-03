# -*- coding: utf-8 -*-
"""
recover_activity_points_osm_nlsc_corrected_v1g_route_phase_aware.py

V1G reviewed route phase aware recovery.

Purpose:
- Apply only human-reviewed route phase ambiguity recovery.
- Read review list CSV.
- Preserve temporal order: elapsed_sec, timestamp_s, activity order, HR, GPS are NOT changed.
- Refit only route-distance representation to reviewed spatial route segment target.

Important:
- This script does NOT blindly recover all V1G diagnosis candidates.
- Recovery is controlled by:
    qixing_lengshuikeng_v1g_recovery_review_list_reviewed.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd
import numpy as np


RECOVERY_STATUS = "matched_core_recovered_from_route_phase_ambiguity"
RECOVERY_METHOD = "v1g_route_phase_aware_spatial_segment_refit_reviewed_list"


def pick_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def to_num(s):
    return pd.to_numeric(s, errors="coerce")


def bool_like_true(v) -> bool:
    return str(v).strip().lower() in ["true", "1", "yes", "y"]


def estimate_from_next_phase_local_anchors(
    df: pd.DataFrame,
    elapsed: float,
    route_col: str,
    elapsed_col: str,
    usable_col: str,
    lookahead_sec: float = 10.0,
) -> float:
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
    ap.add_argument("--route-folder", default="qixing_lengshuikeng")
    ap.add_argument("--input-root", required=True)
    ap.add_argument("--review-list-csv", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--lookahead-sec", type=float, default=10.0)
    ap.add_argument("--max-offset-m", type=float, default=5.0)
    args = ap.parse_args()

    input_root = Path(args.input_root)
    review_csv = Path(args.review_list_csv)
    out_root = Path(args.out_dir)

    reviews = pd.read_csv(review_csv, encoding="utf-8-sig", low_memory=False)

    required_review_cols = [
        "activity_id",
        "elapsed_start_sec",
        "elapsed_end_sec",
        "spatial_route_phase_target",
        "recovery_allowed",
        "target_route_dist_source",
        "review_reason",
    ]
    missing_review = [c for c in required_review_cols if c not in reviews.columns]
    if missing_review:
        raise SystemExit(f"Missing review columns: {missing_review}")

    reviews = reviews[
        reviews["recovery_allowed"].astype(str).str.lower().str.strip().isin(["true", "1", "yes", "y"])
    ].copy()

    if len(reviews) == 0:
        raise SystemExit("No recovery_allowed rows in review list.")

    all_applied_rows = []

    for activity_id, activity_reviews in reviews.groupby("activity_id"):
        input_fp = (
            input_root
            / args.route_folder
            / activity_id
            / f"{args.route_folder}_{activity_id}_activity_points_osm_nlsc_corrected_v1f.csv"
        )

        if not input_fp.exists():
            print(f"SKIP {activity_id}: input not found: {input_fp}")
            continue

        print()
        print("=" * 100)
        print("V1G reviewed recovery:", activity_id)
        print("=" * 100)

        df = pd.read_csv(input_fp, encoding="utf-8-sig", low_memory=False)

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

        projected_col = pick_col(df, [
            "projected_route_dist_m",
            "route_dist_m",
            "nearest_route_dist_m",
        ])

        required = {
            "elapsed_col": elapsed_col,
            "offset_col": offset_col,
            "status_v1f_col": status_v1f_col,
            "usable_v1f_col": usable_v1f_col,
            "route_v1f_col": route_v1f_col,
            "projected_col": projected_col,
        }
        missing = [k for k, v in required.items() if v is None]
        if missing:
            print(f"SKIP {activity_id}: missing columns {missing}")
            continue

        # Baseline copy from v1f
        df["route_context_model_status_v1g"] = df[status_v1f_col]
        df["route_context_model_usable_v1g"] = df[usable_v1f_col]
        df["route_context_model_reason_v1g"] = df.get("route_context_model_reason_v1f", "")

        df["route_dist_refit_m_v1g"] = df[route_v1f_col]
        df["route_dist_refit_method_v1g"] = df.get("route_dist_refit_method_v1f", "")

        df["route_phase_ambiguity_detected_v1g"] = False
        df["spatial_route_phase_target_v1g"] = ""
        df["temporal_phase_preserved_v1g"] = True
        df["route_phase_recovery_reason_v1g"] = ""
        df["route_phase_recovery_source_v1g"] = ""
        df["route_phase_recovery_applied_v1g"] = False
        df["route_phase_recovery_block_reason_v1g"] = ""

        df["_elapsed"] = to_num(df[elapsed_col])
        df["_offset"] = to_num(df[offset_col])

        applied_rows = []

        for _, rv in activity_reviews.iterrows():
            start = float(rv["elapsed_start_sec"])
            end = float(rv["elapsed_end_sec"])
            target = str(rv["spatial_route_phase_target"])
            source = str(rv["target_route_dist_source"])
            reason = str(rv["review_reason"])

            # Optional column:
            # - old reviewed CSV may not have this column
            # - default false keeps old behavior
            apply_only_unusable = False
            if "apply_only_unusable_v1f" in activity_reviews.columns:
                apply_only_unusable = bool_like_true(rv.get("apply_only_unusable_v1f", "false"))

            mask = (
                df["_elapsed"].notna()
                & (df["_elapsed"] >= start)
                & (df["_elapsed"] <= end)
            )

            idxs = df.index[mask].tolist()

            for idx in idxs:
                elapsed = float(df.at[idx, "_elapsed"])
                offset = df.at[idx, "_offset"]

                if apply_only_unusable and bool_like_true(df.at[idx, usable_v1f_col]):
                    df.at[idx, "route_phase_recovery_block_reason_v1g"] = "skip_clean_row_apply_only_unusable_v1f"
                    continue

                if pd.isna(offset) or float(offset) > args.max_offset_m:
                    df.at[idx, "route_phase_recovery_block_reason_v1g"] = "offset_exceeds_v1g_limit"
                    continue

                if source == "candidate_projected_route_dist":
                    estimated_route = pd.to_numeric(df.at[idx, projected_col], errors="coerce")

                elif source == "next_phase_local_anchors":
                    estimated_route = estimate_from_next_phase_local_anchors(
                        df=df,
                        elapsed=elapsed,
                        route_col=route_v1f_col,
                        elapsed_col=elapsed_col,
                        usable_col=usable_v1f_col,
                        lookahead_sec=args.lookahead_sec,
                    )

                else:
                    df.at[idx, "route_phase_recovery_block_reason_v1g"] = f"unsupported_target_route_dist_source:{source}"
                    continue

                if pd.isna(estimated_route):
                    df.at[idx, "route_phase_recovery_block_reason_v1g"] = "no_target_route_dist_available"
                    continue

                df.at[idx, "route_context_model_status_v1g"] = RECOVERY_STATUS
                df.at[idx, "route_context_model_usable_v1g"] = True
                df.at[idx, "route_context_model_reason_v1g"] = reason

                df.at[idx, "route_dist_refit_m_v1g"] = float(estimated_route)
                df.at[idx, "route_dist_refit_method_v1g"] = RECOVERY_METHOD

                df.at[idx, "route_phase_ambiguity_detected_v1g"] = True
                df.at[idx, "spatial_route_phase_target_v1g"] = target
                df.at[idx, "temporal_phase_preserved_v1g"] = True
                df.at[idx, "route_phase_recovery_reason_v1g"] = reason
                df.at[idx, "route_phase_recovery_source_v1g"] = source
                df.at[idx, "route_phase_recovery_applied_v1g"] = True
                df.at[idx, "route_phase_recovery_block_reason_v1g"] = ""

                applied_rows.append({
                    "activity_id": activity_id,
                    "elapsed_sec": elapsed,
                    "offset_m": float(offset),
                    "original_status_v1f": str(df.at[idx, status_v1f_col]),
                    "original_route_dist_refit_m_v1f": pd.to_numeric(df.at[idx, route_v1f_col], errors="coerce"),
                    "projected_route_dist_m": pd.to_numeric(df.at[idx, projected_col], errors="coerce"),
                    "route_dist_refit_m_v1g": float(estimated_route),
                    "spatial_route_phase_target_v1g": target,
                    "temporal_phase_preserved_v1g": True,
                    "target_route_dist_source": source,
                    "apply_only_unusable_v1f": apply_only_unusable,
                    "route_context_model_status_v1g": RECOVERY_STATUS,
                    "route_context_model_reason_v1g": reason,
                })

        df = df.drop(columns=["_elapsed", "_offset"], errors="ignore")

        out_dir = out_root / args.route_folder / activity_id
        out_dir.mkdir(parents=True, exist_ok=True)

        out_fp = out_dir / f"{args.route_folder}_{activity_id}_activity_points_osm_nlsc_corrected_v1g.csv"
        df.to_csv(out_fp, index=False, encoding="utf-8-sig")

        applied_df = pd.DataFrame(applied_rows)
        applied_fp = out_dir / f"{args.route_folder}_{activity_id}_activity_points_osm_nlsc_corrected_v1g_recovery_applied_rows.csv"
        applied_df.to_csv(applied_fp, index=False, encoding="utf-8-sig")

        print("output:", out_fp)
        print("applied rows:", len(applied_df))

        all_applied_rows.extend(applied_rows)

    all_applied_df = pd.DataFrame(all_applied_rows)
    summary_fp = out_root / args.route_folder / f"{args.route_folder}_v1g_reviewed_recovery_applied_rows_all.csv"
    summary_fp.parent.mkdir(parents=True, exist_ok=True)
    all_applied_df.to_csv(summary_fp, index=False, encoding="utf-8-sig")

    print()
    print("=" * 100)
    print("V1G reviewed recovery completed")
    print("review rows:", len(reviews))
    print("applied rows total:", len(all_applied_df))
    print("summary:", summary_fp)
    print("=" * 100)


if __name__ == "__main__":
    main()