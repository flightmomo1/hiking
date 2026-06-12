from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point

import ib3w_lookup_route_candidate_station_elevation_v1b as base_lookup


CONFIDENCE_RANK = {
    "none": 0,
    "low": 1,
    "moderate": 2,
    "good": 3,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "IB3W v1: review NEED_NEIGHBOR_TILE_REVIEW station elevations "
            "against all available NLSC ContourL.shp tiles."
        )
    )
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--nlsc-root", default="nlsc_raw")
    parser.add_argument(
        "--out-dir",
        default="outputs/ib3w_route_candidate_neighbor_tile_review_v1",
    )
    parser.add_argument(
        "--review-status",
        default="NEED_NEIGHBOR_TILE_REVIEW",
        help="Only rows with this elevation_review_status are reviewed.",
    )
    return parser.parse_args()


def ensure_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def discover_contour_files(nlsc_root: Path) -> list[dict]:
    ensure_exists(nlsc_root, "NLSC root")

    rows = []
    for fp in sorted(nlsc_root.rglob("ContourL.shp")):
        try:
            tile = fp.parents[1].name
        except Exception:
            tile = fp.parent.name

        rows.append({
            "nlsc_tile_candidate": tile,
            "contour_fp_candidate": fp.resolve(),
        })

    if not rows:
        raise FileNotFoundError(f"No ContourL.shp found under: {nlsc_root}")

    return rows


def find_station_coordinate_columns(df: pd.DataFrame) -> tuple[str, str]:
    lat_candidates = [
        "station_latitude_lookup",
        "station_latitude",
        "station_lat",
        "lat",
        "latitude",
        "緯度",
    ]
    lon_candidates = [
        "station_longitude_lookup",
        "station_longitude",
        "station_lon",
        "station_lng",
        "lon",
        "lng",
        "longitude",
        "經度",
    ]

    lat_col = next((c for c in lat_candidates if c in df.columns), None)
    lon_col = next((c for c in lon_candidates if c in df.columns), None)

    if lat_col is None or lon_col is None:
        raise ValueError(f"Cannot find station lat/lon columns. columns={list(df.columns)}")

    return lat_col, lon_col


def confidence_rank(value: object) -> int:
    return CONFIDENCE_RANK.get(str(value), 0)


def build_station_gdf(df: pd.DataFrame) -> gpd.GeoDataFrame:
    lat_col, lon_col = find_station_coordinate_columns(df)

    df = df.copy()
    df["_review_lat"] = pd.to_numeric(df[lat_col], errors="coerce")
    df["_review_lon"] = pd.to_numeric(df[lon_col], errors="coerce")
    df = df.dropna(subset=["_review_lat", "_review_lon"]).copy()

    return gpd.GeoDataFrame(
        df,
        geometry=[
            Point(lon, lat)
            for lon, lat in zip(df["_review_lon"], df["_review_lat"])
        ],
        crs="EPSG:4326",
    ).to_crs(base_lookup.TARGET_METRIC_CRS)


def select_best_tile(trials: pd.DataFrame) -> pd.DataFrame:
    if trials.empty:
        return trials.copy()

    df = trials.copy()
    df["_confidence_rank"] = df["candidate_elevation_confidence"].map(confidence_rank)
    df["_distance_sort"] = pd.to_numeric(
        df["candidate_nearest_contour_distance_m"],
        errors="coerce",
    ).fillna(np.inf)
    df["_ok_rank"] = (
        df["candidate_elevation_lookup_status"] == "ELEVATION_LOOKUP_OK"
    ).astype(int)

    sort_cols = [
        "station_row_key",
        "_ok_rank",
        "_confidence_rank",
        "_distance_sort",
    ]
    ascending = [True, False, False, True]

    df = df.sort_values(sort_cols, ascending=ascending).copy()
    best = df.groupby("station_row_key", as_index=False).head(1).copy()

    best["recommended_nlsc_tile"] = best["nlsc_tile_candidate"]
    best["recommended_station_elevation_m"] = best["candidate_station_elevation_m"]
    best["recommended_elevation_confidence"] = best["candidate_elevation_confidence"]
    best["recommended_nearest_contour_distance_m"] = best["candidate_nearest_contour_distance_m"]
    best["recommended_elevation_lookup_status"] = best["candidate_elevation_lookup_status"]

    primary_dist = pd.to_numeric(
        best.get("primary_nearest_contour_distance_m", np.nan),
        errors="coerce",
    )
    best_dist = pd.to_numeric(
        best["recommended_nearest_contour_distance_m"],
        errors="coerce",
    )

    best["neighbor_tile_improved_distance"] = (
        best_dist.notna() & primary_dist.notna() & (best_dist < primary_dist)
    )

    primary_conf_rank = best["primary_elevation_confidence"].map(confidence_rank)
    best_conf_rank = best["recommended_elevation_confidence"].map(confidence_rank)

    best["neighbor_tile_improved_confidence"] = best_conf_rank > primary_conf_rank

    best["neighbor_tile_review_result"] = np.where(
        best["neighbor_tile_improved_distance"] | best["neighbor_tile_improved_confidence"],
        "NEIGHBOR_TILE_IMPROVED",
        "PRIMARY_TILE_REMAINS_BEST_OR_TIED",
    )

    drop_cols = [c for c in best.columns if c.startswith("_")]
    best = best.drop(columns=drop_cols)

    return best


def main() -> None:
    args = parse_args()

    case_id = args.case_id
    input_csv = Path(args.input_csv)
    nlsc_root = Path(args.nlsc_root)
    out_dir = Path(args.out_dir) / case_id
    out_dir.mkdir(parents=True, exist_ok=True)

    ensure_exists(input_csv, "input CSV")

    source = pd.read_csv(input_csv)

    if "elevation_review_status" not in source.columns:
        raise ValueError("input CSV must contain elevation_review_status")

    review = source[source["elevation_review_status"].astype(str) == args.review_status].copy()
    review = review.reset_index(drop=True)
    review["station_row_key"] = review.index.astype(str)

    contours_meta = discover_contour_files(nlsc_root)

    loaded_contours: dict[str, tuple[gpd.GeoDataFrame, str, Path]] = {}
    for c in contours_meta:
        tile = c["nlsc_tile_candidate"]
        fp = Path(c["contour_fp_candidate"])
        contours, elevation_field = base_lookup.load_contours(fp)
        loaded_contours[tile] = (contours, elevation_field, fp)

    stations = build_station_gdf(review)

    trial_rows = []

    for _, station in stations.iterrows():
        original = station.drop(labels=["geometry"]).to_dict()

        for tile, (contours, elevation_field, contour_fp) in loaded_contours.items():
            result = base_lookup.idw_elevation_from_contours(station.geometry, contours)

            row = {
                "case_id": case_id,
                "station_row_key": original.get("station_row_key"),
                "station_id": original.get("station_id", ""),
                "station_name": original.get("station_name", ""),
                "candidate_rank": original.get("candidate_rank", ""),
                "distance_to_route_m": original.get("distance_to_route_m", ""),
                "primary_nlsc_tile": original.get("nlsc_tile", ""),
                "primary_station_elevation_m": original.get("station_elevation_m", ""),
                "primary_elevation_confidence": original.get("elevation_confidence", ""),
                "primary_nearest_contour_distance_m": original.get("nearest_contour_distance_m", ""),
                "primary_elevation_review_status": original.get("elevation_review_status", ""),
                "nlsc_tile_candidate": tile,
                "contour_fp_candidate": str(contour_fp),
                "contour_elevation_field_candidate": elevation_field,
                "candidate_station_elevation_m": result.get("station_elevation_m", np.nan),
                "candidate_elevation_lookup_status": result.get("elevation_lookup_status", ""),
                "candidate_elevation_confidence": result.get("elevation_confidence", ""),
                "candidate_elevation_search_radius_m": result.get("elevation_search_radius_m", np.nan),
                "candidate_n_contours_used": result.get("n_contours_used", np.nan),
                "candidate_nearest_contour_distance_m": result.get("nearest_contour_distance_m", np.nan),
                "candidate_nearest_contour_elevation_m": result.get("nearest_contour_elevation_m", np.nan),
                "candidate_contour_elevation_min_m": result.get("contour_elevation_min_m", np.nan),
                "candidate_contour_elevation_max_m": result.get("contour_elevation_max_m", np.nan),
                "candidate_contour_elevation_std_m": result.get("contour_elevation_std_m", np.nan),
                "zero_fallback_used": False,
            }
            trial_rows.append(row)

    trials = pd.DataFrame(trial_rows)

    if not trials.empty:
        sort_cols = [
            c for c in [
                "candidate_rank",
                "station_id",
                "nlsc_tile_candidate",
            ]
            if c in trials.columns
        ]
        trials = trials.sort_values(sort_cols).reset_index(drop=True)

    best = select_best_tile(trials)

    trials_csv = out_dir / "weather_station_candidates_neighbor_tile_review_trials.csv"
    best_csv = out_dir / "weather_station_candidates_neighbor_tile_review_best.csv"
    summary_csv = out_dir / "weather_station_candidates_neighbor_tile_review_summary.csv"

    trials.to_csv(trials_csv, index=False, encoding="utf-8-sig")
    best.to_csv(best_csv, index=False, encoding="utf-8-sig")

    summary = pd.DataFrame([
        {
            "case_id": case_id,
            "input_rows": int(len(source)),
            "review_status_filter": args.review_status,
            "review_rows": int(len(review)),
            "available_tile_count": int(len(loaded_contours)),
            "tile_trials": int(len(trials)),
            "best_rows": int(len(best)),
            "neighbor_tile_improved": int((best["neighbor_tile_review_result"] == "NEIGHBOR_TILE_IMPROVED").sum()) if not best.empty else 0,
            "primary_tile_remains_best_or_tied": int((best["neighbor_tile_review_result"] == "PRIMARY_TILE_REMAINS_BEST_OR_TIED").sum()) if not best.empty else 0,
            "best_good_confidence": int((best["recommended_elevation_confidence"] == "good").sum()) if not best.empty else 0,
            "best_moderate_confidence": int((best["recommended_elevation_confidence"] == "moderate").sum()) if not best.empty else 0,
            "best_low_confidence": int((best["recommended_elevation_confidence"] == "low").sum()) if not best.empty else 0,
            "best_missing_elevation": int(best["recommended_station_elevation_m"].isna().sum()) if not best.empty else 0,
            "zero_fallback_used": False,
            "tiles_scanned": "|".join(sorted(loaded_contours.keys())),
        }
    ])

    summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")

    print("IB3W neighbor tile station elevation review written")
    print("case_id:", case_id)
    print("input_csv:", input_csv)
    print("review_rows:", len(review))
    print("tiles_scanned:", "|".join(sorted(loaded_contours.keys())))
    print("tile_trials:", len(trials))
    print("best_rows:", len(best))
    print("trials_csv:", trials_csv)
    print("best_csv:", best_csv)
    print("summary_csv:", summary_csv)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
