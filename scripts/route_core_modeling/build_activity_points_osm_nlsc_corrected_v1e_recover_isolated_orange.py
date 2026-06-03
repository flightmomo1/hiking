from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


USABLE_STATUSES = {
    "matched_core_clean",
    "matched_core_refit_from_anchors",
    "matched_core_refit_to_summit",
}


def read_csv_required(fp: Path, name: str) -> pd.DataFrame:
    if not fp.exists():
        raise FileNotFoundError(f"{name} not found: {fp}")
    return pd.read_csv(fp, low_memory=False)


def to_num(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def assign_segments(mask: pd.Series) -> pd.Series:
    seg_ids = []
    current = 0
    in_seg = False

    for v in mask.fillna(False).astype(bool).tolist():
        if v:
            if not in_seg:
                current += 1
                in_seg = True
            seg_ids.append(current)
        else:
            in_seg = False
            seg_ids.append(None)

    return pd.Series(seg_ids, index=mask.index)


def near_any_window(elapsed_min: float, elapsed_max: float, windows: list[tuple[float, float]], buffer_sec: float) -> bool:
    if pd.isna(elapsed_min) or pd.isna(elapsed_max):
        return False

    for start, end in windows:
        if elapsed_max >= start - buffer_sec and elapsed_min <= end + buffer_sec:
            return True

    return False


def get_current_route_dist(row: pd.Series) -> float:
    for c in [
        "route_dist_refit_m_v1d",
        "route_dist_refit_m",
        "reliable_route_dist_m",
        "projected_route_dist_m",
        "route_dist_m",
    ]:
        if c in row.index:
            v = pd.to_numeric(pd.Series([row[c]]), errors="coerce").iloc[0]
            if pd.notna(v):
                return float(v)
    return float("nan")


def interpolate_between_anchors(
    row: pd.Series,
    prev_row: pd.Series,
    next_row: pd.Series,
) -> tuple[float, str]:
    prev_route = get_current_route_dist(prev_row)
    next_route = get_current_route_dist(next_row)

    if pd.isna(prev_route) or pd.isna(next_route):
        return float("nan"), "anchor_route_dist_missing"

    # Prefer distance_m ratio.
    if all(c in row.index for c in ["distance_m"]):
        row_d = pd.to_numeric(pd.Series([row.get("distance_m")]), errors="coerce").iloc[0]
        prev_d = pd.to_numeric(pd.Series([prev_row.get("distance_m")]), errors="coerce").iloc[0]
        next_d = pd.to_numeric(pd.Series([next_row.get("distance_m")]), errors="coerce").iloc[0]

        if pd.notna(row_d) and pd.notna(prev_d) and pd.notna(next_d) and float(next_d) != float(prev_d):
            ratio = (float(row_d) - float(prev_d)) / (float(next_d) - float(prev_d))
            ratio = max(0.0, min(1.0, ratio))
            return prev_route + ratio * (next_route - prev_route), "distance_ratio_between_v1d_usable_anchors"

    # Fallback elapsed_sec ratio.
    row_t = pd.to_numeric(pd.Series([row.get("elapsed_sec")]), errors="coerce").iloc[0]
    prev_t = pd.to_numeric(pd.Series([prev_row.get("elapsed_sec")]), errors="coerce").iloc[0]
    next_t = pd.to_numeric(pd.Series([next_row.get("elapsed_sec")]), errors="coerce").iloc[0]

    if pd.notna(row_t) and pd.notna(prev_t) and pd.notna(next_t) and float(next_t) != float(prev_t):
        ratio = (float(row_t) - float(prev_t)) / (float(next_t) - float(prev_t))
        ratio = max(0.0, min(1.0, ratio))
        return prev_route + ratio * (next_route - prev_route), "time_ratio_between_v1d_usable_anchors"

    return float("nan"), "interpolation_failed"


def recover_isolated_orange(
    df: pd.DataFrame,
    max_segment_rows: int,
    max_segment_duration_sec: float,
    max_offset_m: float,
    offroute_buffer_sec: float,
) -> pd.DataFrame:
    out = df.copy()

    out = to_num(
        out,
        [
            "elapsed_sec",
            "distance_m",
            "offset_m",
            "nearest_route_dist_m",
            "reliable_route_dist_m",
            "projected_route_dist_m",
            "route_dist_m",
            "route_dist_refit_m",
            "route_dist_refit_m_v1d",
        ],
    )

    if "route_context_model_status_v1d" not in out.columns:
        raise ValueError("Input must include route_context_model_status_v1d. Use v1d output as input.")

    status_v1d = out["route_context_model_status_v1d"].astype(str)
    orange = status_v1d.eq("no_activity_route_dist")
    out["orange_segment_id_v1e"] = assign_segments(orange)

    # Detect off-route windows from current v1d output.
    excluded = out["excluded_reason"].astype(str) if "excluded_reason" in out.columns else pd.Series([""] * len(out), index=out.index)
    offroute_mask = excluded.str.contains("off_route_excursion", case=False, na=False)

    offroute_windows = []
    if offroute_mask.any():
        offroute_seg = assign_segments(offroute_mask)
        for _, g in out[offroute_mask].groupby(offroute_seg[offroute_mask]):
            offroute_windows.append((float(g["elapsed_sec"].min()), float(g["elapsed_sec"].max())))

    # Defaults: inherit v1d.
    out["route_context_model_status_v1e"] = out["route_context_model_status_v1d"]
    out["route_context_model_usable_v1e"] = out["route_context_model_usable_v1d"] if "route_context_model_usable_v1d" in out.columns else False
    out["route_context_model_reason_v1e"] = out["route_context_model_reason_v1d"] if "route_context_model_reason_v1d" in out.columns else ""

    out["route_dist_refit_m_v1e"] = out["route_dist_refit_m_v1d"] if "route_dist_refit_m_v1d" in out.columns else pd.NA
    out["route_dist_refit_method_v1e"] = out["route_dist_refit_method_v1d"] if "route_dist_refit_method_v1d" in out.columns else ""

    out["isolated_orange_recovery_candidate_v1e"] = False
    out["isolated_orange_recovery_applied_v1e"] = False
    out["isolated_orange_recovery_block_reason_v1e"] = ""

    for seg_id in sorted([s for s in out["orange_segment_id_v1e"].dropna().unique()]):
        g = out[out["orange_segment_id_v1e"].eq(seg_id)].copy()
        if g.empty:
            continue

        idxs = list(g.index)
        first_idx = idxs[0]
        last_idx = idxs[-1]

        prev_idx = first_idx - 1
        next_idx = last_idx + 1

        prev_status = out.loc[prev_idx, "route_context_model_status_v1d"] if prev_idx in out.index else ""
        next_status = out.loc[next_idx, "route_context_model_status_v1d"] if next_idx in out.index else ""

        elapsed_min = g["elapsed_sec"].min()
        elapsed_max = g["elapsed_sec"].max()
        duration_sec = elapsed_max - elapsed_min if pd.notna(elapsed_min) and pd.notna(elapsed_max) else float("inf")

        reason_counts = g["excluded_reason"].astype(str).value_counts(dropna=False).to_dict() if "excluded_reason" in g.columns else {}
        main_reason = next(iter(reason_counts.keys())) if reason_counts else ""

        offset_max = g["offset_m"].max() if "offset_m" in g.columns else float("inf")

        is_short = len(g) <= max_segment_rows or duration_sec <= max_segment_duration_sec
        small_offset = pd.notna(offset_max) and float(offset_max) <= max_offset_m
        mainline_bracketed = prev_status in USABLE_STATUSES and next_status in USABLE_STATUSES
        safe_reason = main_reason == "route_progress_branch_ambiguous_projection"
        near_offroute = near_any_window(elapsed_min, elapsed_max, offroute_windows, offroute_buffer_sec)

        candidate = safe_reason and is_short and small_offset and mainline_bracketed and not near_offroute

        out.loc[idxs, "isolated_orange_recovery_candidate_v1e"] = candidate

        if not candidate:
            reasons = []
            if not safe_reason:
                reasons.append(f"unsafe_reason:{main_reason}")
            if not is_short:
                reasons.append("segment_not_short")
            if not small_offset:
                reasons.append(f"offset_gt_{max_offset_m:g}m")
            if not mainline_bracketed:
                reasons.append("not_bracketed_by_v1d_usable")
            if near_offroute:
                reasons.append("near_offroute_window")
            out.loc[idxs, "isolated_orange_recovery_block_reason_v1e"] = ";".join(reasons)
            continue

        prev_row = out.loc[prev_idx]
        next_row = out.loc[next_idx]

        for idx in idxs:
            refit_m, method = interpolate_between_anchors(out.loc[idx], prev_row, next_row)

            if pd.isna(refit_m):
                out.loc[idx, "isolated_orange_recovery_block_reason_v1e"] = method
                continue

            out.loc[idx, "route_context_model_status_v1e"] = "matched_core_recovered_from_isolated_branch_ambiguous"
            out.loc[idx, "route_context_model_usable_v1e"] = True
            out.loc[idx, "route_context_model_reason_v1e"] = "isolated_orange_branch_ambiguous_recovered"
            out.loc[idx, "route_dist_refit_m_v1e"] = refit_m
            out.loc[idx, "route_dist_refit_method_v1e"] = method
            out.loc[idx, "isolated_orange_recovery_applied_v1e"] = True
            out.loc[idx, "isolated_orange_recovery_block_reason_v1e"] = ""

    out["v1e_max_segment_rows"] = max_segment_rows
    out["v1e_max_segment_duration_sec"] = max_segment_duration_sec
    out["v1e_max_offset_m"] = max_offset_m
    out["v1e_offroute_buffer_sec"] = offroute_buffer_sec

    return out


def run(
    input_fp: Path,
    route_folder: str,
    activity_id: str,
    out_dir: Path,
    max_segment_rows: int,
    max_segment_duration_sec: float,
    max_offset_m: float,
    offroute_buffer_sec: float,
) -> Path:
    df = read_csv_required(input_fp, "v1d corrected activity points")

    out = recover_isolated_orange(
        df,
        max_segment_rows=max_segment_rows,
        max_segment_duration_sec=max_segment_duration_sec,
        max_offset_m=max_offset_m,
        offroute_buffer_sec=offroute_buffer_sec,
    )

    out_root = out_dir / route_folder / activity_id
    out_root.mkdir(parents=True, exist_ok=True)

    out_fp = out_root / f"{route_folder}_{activity_id}_activity_points_osm_nlsc_corrected_v1e.csv"
    out.to_csv(out_fp, index=False, encoding="utf-8-sig")

    summary_fp = out_root / f"{route_folder}_{activity_id}_activity_points_osm_nlsc_corrected_v1e_summary.txt"

    lines = []
    lines.append(f"route_folder: {route_folder}")
    lines.append(f"activity_id: {activity_id}")
    lines.append(f"input_fp: {input_fp}")
    lines.append(f"rows_total: {len(out)}")
    lines.append(f"max_segment_rows: {max_segment_rows}")
    lines.append(f"max_segment_duration_sec: {max_segment_duration_sec}")
    lines.append(f"max_offset_m: {max_offset_m}")
    lines.append(f"offroute_buffer_sec: {offroute_buffer_sec}")

    for col in [
        "route_context_model_status_v1d",
        "route_context_model_status_v1e",
        "route_context_model_usable_v1e",
        "route_context_model_reason_v1e",
        "route_dist_refit_method_v1e",
        "isolated_orange_recovery_candidate_v1e",
        "isolated_orange_recovery_applied_v1e",
        "isolated_orange_recovery_block_reason_v1e",
    ]:
        if col in out.columns:
            lines.append("")
            lines.append(f"{col}:")
            lines.append(str(out[col].value_counts(dropna=False).head(50)))

    summary_fp.write_text("\n".join(lines), encoding="utf-8")

    return out_fp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recover isolated orange no_activity_route_dist points when safely bracketed by v1d usable mainline anchors."
    )
    parser.add_argument("--route-folder", default="qixing_lengshuikeng")
    parser.add_argument("--activity-id", required=True)
    parser.add_argument("--input-fp", required=True)
    parser.add_argument(
        "--out-dir",
        default=r"outputs\activity_points_osm_nlsc_corrected_v1e_recover_isolated_orange_offset3",
    )
    parser.add_argument("--max-segment-rows", type=int, default=2)
    parser.add_argument("--max-segment-duration-sec", type=float, default=2.0)
    parser.add_argument("--max-offset-m", type=float, default=5.0)
    parser.add_argument("--offroute-buffer-sec", type=float, default=60.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    out_fp = run(
        input_fp=Path(args.input_fp),
        route_folder=args.route_folder,
        activity_id=args.activity_id,
        out_dir=Path(args.out_dir),
        max_segment_rows=args.max_segment_rows,
        max_segment_duration_sec=args.max_segment_duration_sec,
        max_offset_m=args.max_offset_m,
        offroute_buffer_sec=args.offroute_buffer_sec,
    )

    print("v1e isolated orange recovery output written:")
    print(out_fp)


if __name__ == "__main__":
    main()
