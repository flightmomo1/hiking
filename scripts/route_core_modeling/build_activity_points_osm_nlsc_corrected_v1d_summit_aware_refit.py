from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


def read_csv_required(fp: Path, name: str) -> pd.DataFrame:
    if not fp.exists():
        raise FileNotFoundError(f"{name} not found: {fp}")
    return pd.read_csv(fp, low_memory=False)


def summit_aware_refit(
    df: pd.DataFrame,
    summit_route_dist_m: float,
    summit_window_m: float,
) -> pd.DataFrame:
    out = df.copy()

    required = [
        "route_context_model_status_v1c",
        "reliable_route_dist_m",
    ]
    missing = [c for c in required if c not in out.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")

    out["reliable_route_dist_m"] = pd.to_numeric(out["reliable_route_dist_m"], errors="coerce")

    excluded_reason = (
        out["excluded_reason"].astype(str)
        if "excluded_reason" in out.columns
        else pd.Series([""] * len(out), index=out.index)
    )

    v1c_status = out["route_context_model_status_v1c"].astype(str)

    near_summit = (
        out["reliable_route_dist_m"].notna()
        & ((out["reliable_route_dist_m"] - summit_route_dist_m).abs() <= summit_window_m)
    )

    blocked_reason = excluded_reason.str.contains(
        "off_route|branch_ambiguous",
        case=False,
        na=False,
    )

    summit_candidate = (
        v1c_status.eq("matched_low_confidence_offset")
        & near_summit
        & (~blocked_reason)
    )

    # Default: inherit v1c.
    out["route_context_model_status_v1d"] = out["route_context_model_status_v1c"]
    out["route_context_model_usable_v1d"] = out["route_context_model_usable_v1c"] if "route_context_model_usable_v1c" in out.columns else False
    out["route_context_model_reason_v1d"] = out["route_context_model_reason_v1c"] if "route_context_model_reason_v1c" in out.columns else ""

    # Default refit distance inherits v1c route_dist_refit_m when available.
    if "route_dist_refit_m" in out.columns:
        out["route_dist_refit_m_v1d"] = out["route_dist_refit_m"]
    else:
        out["route_dist_refit_m_v1d"] = pd.NA

    if "route_dist_refit_method" in out.columns:
        out["route_dist_refit_method_v1d"] = out["route_dist_refit_method"]
    else:
        out["route_dist_refit_method_v1d"] = ""

    out["summit_aware_refit_candidate"] = summit_candidate
    out["summit_aware_refit_applied"] = False
    out["summit_route_dist_m_v1d"] = summit_route_dist_m
    out["summit_window_m_v1d"] = summit_window_m
    out["summit_route_dist_delta_m_v1d"] = (out["reliable_route_dist_m"] - summit_route_dist_m).abs()

    # Apply summit-aware refit.
    out.loc[summit_candidate, "route_context_model_status_v1d"] = "matched_core_refit_to_summit"
    out.loc[summit_candidate, "route_context_model_usable_v1d"] = True
    out.loc[summit_candidate, "route_context_model_reason_v1d"] = "summit_aware_refit"
    out.loc[summit_candidate, "route_dist_refit_m_v1d"] = summit_route_dist_m
    out.loc[summit_candidate, "route_dist_refit_method_v1d"] = "summit_anchor"
    out.loc[summit_candidate, "summit_aware_refit_applied"] = True

    return out


def run(
    input_fp: Path,
    route_folder: str,
    activity_id: str,
    out_dir: Path,
    summit_route_dist_m: float,
    summit_window_m: float,
) -> Path:
    df = read_csv_required(input_fp, "v1c corrected activity points")

    out = summit_aware_refit(
        df,
        summit_route_dist_m=summit_route_dist_m,
        summit_window_m=summit_window_m,
    )

    out_root = out_dir / route_folder / activity_id
    out_root.mkdir(parents=True, exist_ok=True)

    out_fp = out_root / f"{route_folder}_{activity_id}_activity_points_osm_nlsc_corrected_v1d.csv"
    out.to_csv(out_fp, index=False, encoding="utf-8-sig")

    summary_fp = out_root / f"{route_folder}_{activity_id}_activity_points_osm_nlsc_corrected_v1d_summary.txt"

    summary_lines = []
    summary_lines.append(f"route_folder: {route_folder}")
    summary_lines.append(f"activity_id: {activity_id}")
    summary_lines.append(f"input_fp: {input_fp}")
    summary_lines.append(f"rows_total: {len(out)}")
    summary_lines.append(f"summit_route_dist_m: {summit_route_dist_m}")
    summary_lines.append(f"summit_window_m: {summit_window_m}")

    for col in [
        "route_context_model_status_v1c",
        "route_context_model_status_v1d",
        "route_context_model_usable_v1d",
        "route_context_model_reason_v1d",
        "route_dist_refit_method_v1d",
        "summit_aware_refit_candidate",
        "summit_aware_refit_applied",
    ]:
        if col in out.columns:
            summary_lines.append("")
            summary_lines.append(f"{col}:")
            summary_lines.append(str(out[col].value_counts(dropna=False).head(40)))

    summary_fp.write_text("\n".join(summary_lines), encoding="utf-8")

    return out_fp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply summit-aware refit on top of v1c refit-mainline output."
    )
    parser.add_argument("--route-folder", default="qixing_lengshuikeng")
    parser.add_argument("--activity-id", required=True)
    parser.add_argument("--input-fp", required=True)
    parser.add_argument(
        "--out-dir",
        default=r"outputs\activity_points_osm_nlsc_corrected_v1d_summit_aware_refit_offset3",
    )
    parser.add_argument("--summit-route-dist-m", type=float, default=2096.0)
    parser.add_argument("--summit-window-m", type=float, default=30.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    out_fp = run(
        input_fp=Path(args.input_fp),
        route_folder=args.route_folder,
        activity_id=args.activity_id,
        out_dir=Path(args.out_dir),
        summit_route_dist_m=args.summit_route_dist_m,
        summit_window_m=args.summit_window_m,
    )

    print("v1d summit-aware refit output written:")
    print(out_fp)


if __name__ == "__main__":
    main()
