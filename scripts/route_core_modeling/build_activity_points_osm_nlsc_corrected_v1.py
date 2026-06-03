from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


ROUTE_CONTEXT_KEEP_COLS = [
    "dist_m",
    "route_dist_m",
    "ele_smooth",
    "ele_gpx_m",
    "contour_mid",
    "slope_band_window_nlsc",
    "terrain_window_risk_score",
    "hydro_terrain_amplifier_score",
    "osm_terrain_combined_risk_score",
    "osm_terrain_combined_risk_band",
    "osm_highway",
    "osm_surface",
    "surface_class",
    "route_semantic_class",
    "facility_flags",
    "rest_flags",
    "support_flags",
    "hydrology_flags",
    "visibility_class",
    "osm_difficulty_class",
]


def read_csv_required(fp: Path, name: str) -> pd.DataFrame:
    if not fp.exists():
        raise FileNotFoundError(f"{name} not found: {fp}")
    return pd.read_csv(fp)


def find_distance_col(df: pd.DataFrame, candidates: list[str], name: str) -> str:
    for c in candidates:
        if c in df.columns:
            return c
    raise ValueError(f"{name} has no usable distance column. Tried: {candidates}")


def prepare_route_context(route_df: pd.DataFrame) -> pd.DataFrame:
    route_df = route_df.copy()

    route_dist_col = find_distance_col(
        route_df,
        ["dist_m", "route_dist_m"],
        "route_context",
    )

    route_df["__route_context_dist_m"] = pd.to_numeric(
        route_df[route_dist_col], errors="coerce"
    )

    route_df = route_df.dropna(subset=["__route_context_dist_m"])
    route_df = route_df.sort_values("__route_context_dist_m")

    keep_cols = [c for c in ROUTE_CONTEXT_KEEP_COLS if c in route_df.columns]

    out = route_df[["__route_context_dist_m"] + keep_cols].copy()

    # Avoid duplicate route context column names after merge_asof.
    rename = {}
    for c in keep_cols:
        if c in {"dist_m", "route_dist_m"}:
            rename[c] = f"route_context_{c}"
        else:
            rename[c] = f"route_context_{c}"

    out = out.rename(columns=rename)

    return out


def prepare_activity_points(points_df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    points_df = points_df.copy()

    # Preferred order:
    # reliable_route_dist_m = best route-core usable distance when available.
    # route_dist_m / projected_route_dist_m = fallback for observed behavior context.
    dist_col = find_distance_col(
        points_df,
        [
            "reliable_route_dist_m",
            "route_dist_m",
            "projected_route_dist_m",
        ],
        "activity_points",
    )

    points_df["__activity_join_dist_m"] = pd.to_numeric(
        points_df[dist_col], errors="coerce"
    )

    return points_df, dist_col


def enrich_activity_points(
    points_fp: Path,
    route_context_fp: Path,
    route_folder: str,
    activity_id: str,
    out_dir: Path,
    max_match_dist_m: float,
) -> Path:
    points_df = read_csv_required(points_fp, "activity_points")
    route_df = read_csv_required(route_context_fp, "route_context")

    points_df, activity_dist_col = prepare_activity_points(points_df)
    route_context = prepare_route_context(route_df)

    # Preserve original row order.
    points_df["__original_row_order"] = range(len(points_df))

    valid = points_df.dropna(subset=["__activity_join_dist_m"]).copy()
    invalid = points_df[points_df["__activity_join_dist_m"].isna()].copy()

    valid = valid.sort_values("__activity_join_dist_m")

    enriched_valid = pd.merge_asof(
        valid,
        route_context,
        left_on="__activity_join_dist_m",
        right_on="__route_context_dist_m",
        direction="nearest",
        tolerance=max_match_dist_m,
    )

    enriched_valid["route_context_join_dist_diff_m"] = (
        enriched_valid["__activity_join_dist_m"]
        - enriched_valid["__route_context_dist_m"]
    ).abs()

    enriched_valid["route_context_match_status"] = enriched_valid[
        "__route_context_dist_m"
    ].notna().map({True: "matched", False: "unmatched"})

    if len(invalid) > 0:
        for c in route_context.columns:
            if c not in invalid.columns:
                invalid[c] = pd.NA
        invalid["route_context_join_dist_diff_m"] = pd.NA
        invalid["route_context_match_status"] = "no_activity_route_dist"
        enriched = pd.concat([enriched_valid, invalid], ignore_index=True, sort=False)
    else:
        enriched = enriched_valid

    enriched = enriched.sort_values("__original_row_order").drop(
        columns=[
            "__original_row_order",
            "__activity_join_dist_m",
            "__route_context_dist_m",
        ],
        errors="ignore",
    )

    enriched["route_folder"] = route_folder
    enriched["activity_id"] = activity_id
    enriched["activity_route_context_join_dist_col"] = activity_dist_col
    enriched["route_context_source_fp"] = str(route_context_fp)
    enriched["activity_points_source_fp"] = str(points_fp)

    out_root = out_dir / route_folder / activity_id
    out_root.mkdir(parents=True, exist_ok=True)

    out_fp = out_root / f"{route_folder}_{activity_id}_activity_points_osm_nlsc_corrected_v1.csv"
    enriched.to_csv(out_fp, index=False, encoding="utf-8-sig")

    summary_fp = out_root / f"{route_folder}_{activity_id}_activity_points_osm_nlsc_corrected_v1_summary.txt"

    summary_lines = []
    summary_lines.append(f"route_folder: {route_folder}")
    summary_lines.append(f"activity_id: {activity_id}")
    summary_lines.append(f"points_fp: {points_fp}")
    summary_lines.append(f"route_context_fp: {route_context_fp}")
    summary_lines.append(f"activity_route_context_join_dist_col: {activity_dist_col}")
    summary_lines.append(f"max_match_dist_m: {max_match_dist_m}")
    summary_lines.append(f"rows_total: {len(enriched)}")
    summary_lines.append("")
    summary_lines.append("route_context_match_status:")
    summary_lines.append(str(enriched["route_context_match_status"].value_counts(dropna=False)))

    if "usable_on_route" in enriched.columns:
        summary_lines.append("")
        summary_lines.append("usable_on_route:")
        summary_lines.append(str(enriched["usable_on_route"].value_counts(dropna=False)))

    if "excluded_reason" in enriched.columns:
        summary_lines.append("")
        summary_lines.append("excluded_reason top:")
        summary_lines.append(str(enriched["excluded_reason"].value_counts(dropna=False).head(20)))

    if "route_context_join_dist_diff_m" in enriched.columns:
        diff = pd.to_numeric(enriched["route_context_join_dist_diff_m"], errors="coerce")
        summary_lines.append("")
        summary_lines.append("route_context_join_dist_diff_m:")
        summary_lines.append(str(diff.describe()))

    summary_fp.write_text("\n".join(summary_lines), encoding="utf-8")

    return out_fp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Join IB3A2 activity labeled points with IB1E OSM/NLSC route context."
    )

    parser.add_argument("--route-folder", default="qixing_lengshuikeng")
    parser.add_argument("--activity-id", required=True)

    parser.add_argument(
        "--points-fp",
        required=True,
        help="IB3A2 labeled activity points CSV.",
    )

    parser.add_argument(
        "--route-context-fp",
        default=(
            r"outputs\ib1e_route_profile_contour_window_terrain"
            r"\qixing_lengshuikeng_main_peak_20260523"
            r"\qixing_lengshuikeng_main_peak_20260523_route_profile_contour_window_terrain_enriched.csv"
        ),
        help="IB1E route profile contour-window terrain enriched CSV.",
    )

    parser.add_argument(
        "--out-dir",
        default=r"outputs\activity_points_osm_nlsc_corrected_v1",
    )

    parser.add_argument(
        "--max-match-dist-m",
        type=float,
        default=10.0,
        help="Maximum nearest route-context distance match tolerance.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    out_fp = enrich_activity_points(
        points_fp=Path(args.points_fp),
        route_context_fp=Path(args.route_context_fp),
        route_folder=args.route_folder,
        activity_id=args.activity_id,
        out_dir=Path(args.out_dir),
        max_match_dist_m=args.max_match_dist_m,
    )

    print("activity points OSM/NLSC corrected output written:")
    print(out_fp)


if __name__ == "__main__":
    main()
