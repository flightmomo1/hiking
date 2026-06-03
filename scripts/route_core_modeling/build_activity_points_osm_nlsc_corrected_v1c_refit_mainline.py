from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


def read_csv_required(fp: Path, name: str) -> pd.DataFrame:
    if not fp.exists():
        raise FileNotFoundError(f"{name} not found: {fp}")
    return pd.read_csv(fp, low_memory=False)


def find_first_existing(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def assign_segments(mask: pd.Series) -> pd.Series:
    """
    Assign segment ids to consecutive True runs.
    False rows get empty string.
    """
    seg_ids = []
    current_id = 0
    in_seg = False

    for v in mask.fillna(False).astype(bool).tolist():
        if v:
            if not in_seg:
                current_id += 1
                in_seg = True
            seg_ids.append(str(current_id))
        else:
            in_seg = False
            seg_ids.append("")

    return pd.Series(seg_ids, index=mask.index)


def interpolate_route_dist_by_distance(
    row_distance: float,
    prev_distance: float,
    next_distance: float,
    prev_route_dist: float,
    next_route_dist: float,
) -> float:
    if pd.isna(row_distance) or pd.isna(prev_distance) or pd.isna(next_distance):
        return float("nan")

    denom = next_distance - prev_distance

    if denom == 0:
        return float("nan")

    ratio = (row_distance - prev_distance) / denom
    ratio = max(0.0, min(1.0, ratio))

    return prev_route_dist + ratio * (next_route_dist - prev_route_dist)


def interpolate_route_dist_by_time(
    row_elapsed: float,
    prev_elapsed: float,
    next_elapsed: float,
    prev_route_dist: float,
    next_route_dist: float,
) -> float:
    if pd.isna(row_elapsed) or pd.isna(prev_elapsed) or pd.isna(next_elapsed):
        return float("nan")

    denom = next_elapsed - prev_elapsed

    if denom == 0:
        return float("nan")

    ratio = (row_elapsed - prev_elapsed) / denom
    ratio = max(0.0, min(1.0, ratio))

    return prev_route_dist + ratio * (next_route_dist - prev_route_dist)


def refit_mainline(
    df: pd.DataFrame,
    max_anchor_gap_sec: float,
    max_anchor_gap_route_m: float,
) -> pd.DataFrame:
    out = df.copy()

    elapsed_col = find_first_existing(out, ["elapsed_sec", "time_sec"])
    distance_col = find_first_existing(out, ["distance_m", "gps_distance_m"])
    route_dist_col = find_first_existing(out, ["reliable_route_dist_m", "projected_route_dist_m", "route_dist_m"])

    if route_dist_col is None:
        raise ValueError("No route distance column found for refit.")

    if elapsed_col is not None:
        out[elapsed_col] = pd.to_numeric(out[elapsed_col], errors="coerce")

    if distance_col is not None:
        out[distance_col] = pd.to_numeric(out[distance_col], errors="coerce")

    out[route_dist_col] = pd.to_numeric(out[route_dist_col], errors="coerce")

    if "route_context_model_status" not in out.columns:
        raise ValueError("Input missing route_context_model_status. Use v1b_offset5 output as input.")

    # Keep original route-context/model fields.
    status = out["route_context_model_status"].astype(str)
    excluded_reason = out["excluded_reason"].astype(str) if "excluded_reason" in out.columns else pd.Series([""] * len(out), index=out.index)

    # Initial v1c fields.
    out["route_context_model_status_v1c"] = ""
    out["route_context_model_usable_v1c"] = False
    out["route_context_model_reason_v1c"] = ""
    out["route_dist_refit_m"] = pd.NA
    out["route_dist_refit_method"] = ""
    out["route_dist_refit_prev_anchor_elapsed_sec"] = pd.NA
    out["route_dist_refit_next_anchor_elapsed_sec"] = pd.NA
    out["route_dist_refit_prev_anchor_route_dist_m"] = pd.NA
    out["route_dist_refit_next_anchor_route_dist_m"] = pd.NA
    out["route_dist_refit_anchor_gap_sec"] = pd.NA
    out["route_dist_refit_anchor_gap_route_m"] = pd.NA

    # Clean core points keep original reliable route distance.
    clean_mask = status.eq("matched_core")
    out.loc[clean_mask, "route_context_model_status_v1c"] = "matched_core_clean"
    out.loc[clean_mask, "route_context_model_usable_v1c"] = True
    out.loc[clean_mask, "route_context_model_reason_v1c"] = "v1b_matched_core"
    out.loc[clean_mask, "route_dist_refit_m"] = out.loc[clean_mask, route_dist_col]
    out.loc[clean_mask, "route_dist_refit_method"] = "original_route_dist"

    # Never refit no_activity_route_dist / unmatched.
    no_dist_mask = status.eq("no_activity_route_dist")
    out.loc[no_dist_mask, "route_context_model_status_v1c"] = "no_activity_route_dist"
    out.loc[no_dist_mask, "route_context_model_usable_v1c"] = False
    out.loc[no_dist_mask, "route_context_model_reason_v1c"] = "no_activity_route_dist"

    unmatched_mask = status.eq("unmatched")
    out.loc[unmatched_mask, "route_context_model_status_v1c"] = "unmatched"
    out.loc[unmatched_mask, "route_context_model_usable_v1c"] = False
    out.loc[unmatched_mask, "route_context_model_reason_v1c"] = "unmatched"

    # Candidate points are high-offset matched points from v1b.
    candidate_mask = status.eq("matched_low_confidence_offset")

    # Conservative guard: if upstream already labels off-route in excluded_reason, do not refit.
    offroute_reason_mask = excluded_reason.str.contains("off_route|branch_ambiguous", case=False, na=False)

    candidate_refit_mask = candidate_mask & (~offroute_reason_mask)
    candidate_blocked_mask = candidate_mask & offroute_reason_mask

    out.loc[candidate_blocked_mask, "route_context_model_status_v1c"] = "off_branch_or_excluded"
    out.loc[candidate_blocked_mask, "route_context_model_usable_v1c"] = False
    out.loc[candidate_blocked_mask, "route_context_model_reason_v1c"] = "blocked_by_excluded_reason"

    # Segment candidates for refit.
    out["route_dist_refit_candidate_segment_id"] = assign_segments(candidate_refit_mask)

    # Prepare anchor indexes: clean points only.
    clean_indexes = list(out.index[clean_mask])

    for seg_id in sorted([s for s in out["route_dist_refit_candidate_segment_id"].unique() if str(s).strip() != ""]):
        seg_idx = list(out.index[out["route_dist_refit_candidate_segment_id"].astype(str).eq(str(seg_id))])
        if not seg_idx:
            continue

        first_idx = seg_idx[0]
        last_idx = seg_idx[-1]

        prev_candidates = [i for i in clean_indexes if i < first_idx]
        next_candidates = [i for i in clean_indexes if i > last_idx]

        if not prev_candidates or not next_candidates:
            out.loc[seg_idx, "route_context_model_status_v1c"] = "matched_low_confidence_offset"
            out.loc[seg_idx, "route_context_model_usable_v1c"] = False
            out.loc[seg_idx, "route_context_model_reason_v1c"] = "missing_clean_anchor"
            continue

        prev_idx = prev_candidates[-1]
        next_idx = next_candidates[0]

        prev_route = out.loc[prev_idx, route_dist_col]
        next_route = out.loc[next_idx, route_dist_col]

        if pd.isna(prev_route) or pd.isna(next_route):
            out.loc[seg_idx, "route_context_model_status_v1c"] = "matched_low_confidence_offset"
            out.loc[seg_idx, "route_context_model_usable_v1c"] = False
            out.loc[seg_idx, "route_context_model_reason_v1c"] = "anchor_route_dist_missing"
            continue

        anchor_gap_route = abs(float(next_route) - float(prev_route))

        prev_elapsed = out.loc[prev_idx, elapsed_col] if elapsed_col else pd.NA
        next_elapsed = out.loc[next_idx, elapsed_col] if elapsed_col else pd.NA
        anchor_gap_sec = abs(float(next_elapsed) - float(prev_elapsed)) if elapsed_col and not pd.isna(prev_elapsed) and not pd.isna(next_elapsed) else pd.NA

        if not pd.isna(anchor_gap_sec) and float(anchor_gap_sec) > max_anchor_gap_sec:
            out.loc[seg_idx, "route_context_model_status_v1c"] = "matched_low_confidence_offset"
            out.loc[seg_idx, "route_context_model_usable_v1c"] = False
            out.loc[seg_idx, "route_context_model_reason_v1c"] = f"anchor_gap_sec_gt_{max_anchor_gap_sec:g}"
            continue

        if anchor_gap_route > max_anchor_gap_route_m:
            out.loc[seg_idx, "route_context_model_status_v1c"] = "matched_low_confidence_offset"
            out.loc[seg_idx, "route_context_model_usable_v1c"] = False
            out.loc[seg_idx, "route_context_model_reason_v1c"] = f"anchor_gap_route_gt_{max_anchor_gap_route_m:g}m"
            continue

        prev_distance = out.loc[prev_idx, distance_col] if distance_col else pd.NA
        next_distance = out.loc[next_idx, distance_col] if distance_col else pd.NA

        for idx in seg_idx:
            method = ""
            refit = float("nan")

            if distance_col and not pd.isna(prev_distance) and not pd.isna(next_distance) and float(next_distance) != float(prev_distance):
                refit = interpolate_route_dist_by_distance(
                    row_distance=out.loc[idx, distance_col],
                    prev_distance=prev_distance,
                    next_distance=next_distance,
                    prev_route_dist=float(prev_route),
                    next_route_dist=float(next_route),
                )
                method = "distance_ratio_between_clean_anchors"

            elif elapsed_col and not pd.isna(prev_elapsed) and not pd.isna(next_elapsed) and float(next_elapsed) != float(prev_elapsed):
                refit = interpolate_route_dist_by_time(
                    row_elapsed=out.loc[idx, elapsed_col],
                    prev_elapsed=prev_elapsed,
                    next_elapsed=next_elapsed,
                    prev_route_dist=float(prev_route),
                    next_route_dist=float(next_route),
                )
                method = "time_ratio_between_clean_anchors"

            if pd.isna(refit):
                out.loc[idx, "route_context_model_status_v1c"] = "matched_low_confidence_offset"
                out.loc[idx, "route_context_model_usable_v1c"] = False
                out.loc[idx, "route_context_model_reason_v1c"] = "refit_interpolation_failed"
                continue

            out.loc[idx, "route_context_model_status_v1c"] = "matched_core_refit_from_anchors"
            out.loc[idx, "route_context_model_usable_v1c"] = True
            out.loc[idx, "route_context_model_reason_v1c"] = "refit_between_clean_anchors"
            out.loc[idx, "route_dist_refit_m"] = refit
            out.loc[idx, "route_dist_refit_method"] = method
            out.loc[idx, "route_dist_refit_prev_anchor_elapsed_sec"] = prev_elapsed
            out.loc[idx, "route_dist_refit_next_anchor_elapsed_sec"] = next_elapsed
            out.loc[idx, "route_dist_refit_prev_anchor_route_dist_m"] = prev_route
            out.loc[idx, "route_dist_refit_next_anchor_route_dist_m"] = next_route
            out.loc[idx, "route_dist_refit_anchor_gap_sec"] = anchor_gap_sec
            out.loc[idx, "route_dist_refit_anchor_gap_route_m"] = anchor_gap_route

    # Any remaining unassigned rows get a safe default.
    empty_mask = out["route_context_model_status_v1c"].astype(str).str.strip().eq("")
    out.loc[empty_mask, "route_context_model_status_v1c"] = "unclassified"
    out.loc[empty_mask, "route_context_model_usable_v1c"] = False
    out.loc[empty_mask, "route_context_model_reason_v1c"] = "unclassified"

    return out


def run_refit(
    input_fp: Path,
    route_folder: str,
    activity_id: str,
    out_dir: Path,
    max_anchor_gap_sec: float,
    max_anchor_gap_route_m: float,
) -> Path:
    df = read_csv_required(input_fp, "v1b corrected activity points")

    out = refit_mainline(
        df,
        max_anchor_gap_sec=max_anchor_gap_sec,
        max_anchor_gap_route_m=max_anchor_gap_route_m,
    )

    out_root = out_dir / route_folder / activity_id
    out_root.mkdir(parents=True, exist_ok=True)

    out_fp = out_root / f"{route_folder}_{activity_id}_activity_points_osm_nlsc_corrected_v1c.csv"
    out.to_csv(out_fp, index=False, encoding="utf-8-sig")

    summary_fp = out_root / f"{route_folder}_{activity_id}_activity_points_osm_nlsc_corrected_v1c_summary.txt"

    summary_lines = []
    summary_lines.append(f"route_folder: {route_folder}")
    summary_lines.append(f"activity_id: {activity_id}")
    summary_lines.append(f"input_fp: {input_fp}")
    summary_lines.append(f"rows_total: {len(out)}")
    summary_lines.append(f"max_anchor_gap_sec: {max_anchor_gap_sec}")
    summary_lines.append(f"max_anchor_gap_route_m: {max_anchor_gap_route_m}")

    for col in [
        "route_context_model_status",
        "route_context_model_usable",
        "route_context_model_status_v1c",
        "route_context_model_usable_v1c",
        "route_context_model_reason_v1c",
        "route_dist_refit_method",
    ]:
        if col in out.columns:
            summary_lines.append("")
            summary_lines.append(f"{col}:")
            summary_lines.append(str(out[col].value_counts(dropna=False).head(30)))

    summary_fp.write_text("\n".join(summary_lines), encoding="utf-8")

    return out_fp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refit mainline GPS drift points between clean route-distance anchors."
    )

    parser.add_argument("--route-folder", default="qixing_lengshuikeng")
    parser.add_argument("--activity-id", required=True)
    parser.add_argument("--input-fp", required=True)
    parser.add_argument(
        "--out-dir",
        default=r"outputs\activity_points_osm_nlsc_corrected_v1c_refit_mainline",
    )
    parser.add_argument("--max-anchor-gap-sec", type=float, default=120.0)
    parser.add_argument("--max-anchor-gap-route-m", type=float, default=120.0)

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    out_fp = run_refit(
        input_fp=Path(args.input_fp),
        route_folder=args.route_folder,
        activity_id=args.activity_id,
        out_dir=Path(args.out_dir),
        max_anchor_gap_sec=args.max_anchor_gap_sec,
        max_anchor_gap_route_m=args.max_anchor_gap_route_m,
    )

    print("v1c refit mainline output written:")
    print(out_fp)


if __name__ == "__main__":
    main()
