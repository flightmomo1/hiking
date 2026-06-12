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

ACCEPTABLE_CONFIDENCE = {"good", "moderate"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "IB3W v1: water candidate station elevation primary lookup, "
            "neighbor tile review, and finalization."
        )
    )
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--water-candidates-csv", required=True)
    parser.add_argument("--tile-mapping-csv", required=True)
    parser.add_argument("--nlsc-root", default="nlsc_raw")
    parser.add_argument(
        "--out-dir",
        default="outputs/ib3w_water_candidate_elevation_v1",
    )
    return parser.parse_args()


def ensure_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def confidence_rank(value: object) -> int:
    return CONFIDENCE_RANK.get(str(value), 0)


def classify_primary_review(row: pd.Series) -> str:
    status = str(row.get("elevation_lookup_status", ""))
    confidence = str(row.get("elevation_confidence", ""))
    nearest = pd.to_numeric(row.get("nearest_contour_distance_m", np.nan), errors="coerce")

    if status != "ELEVATION_LOOKUP_OK":
        return "LOOKUP_FAILED"
    if confidence in ACCEPTABLE_CONFIDENCE:
        return "ACCEPTABLE"
    if pd.notna(nearest) and nearest > base_lookup.ELEVATION_CONFIDENCE_OK_DISTANCE_M:
        return "NEED_NEIGHBOR_TILE_REVIEW"
    return "REVIEW_REQUIRED"


def classify_final_status(confidence: object, elevation: object, lookup_status: object) -> str:
    conf = str(confidence)
    status = str(lookup_status)
    elev = pd.to_numeric(elevation, errors="coerce")

    if status and status != "ELEVATION_LOOKUP_OK":
        return "FINAL_LOOKUP_FAILED"
    if pd.isna(elev):
        return "FINAL_ELEVATION_MISSING"
    if conf in ACCEPTABLE_CONFIDENCE:
        return "FINAL_ACCEPTABLE"
    if conf == "low":
        return "FINAL_LOW_CONFIDENCE_REVIEW_REQUIRED"
    return "FINAL_REVIEW_REQUIRED"


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


def build_station_gdf(df: pd.DataFrame) -> gpd.GeoDataFrame:
    if "station_latitude" not in df.columns or "station_longitude" not in df.columns:
        raise ValueError("water candidates CSV must contain station_latitude and station_longitude")

    x = df.copy()
    x["_lat"] = pd.to_numeric(x["station_latitude"], errors="coerce")
    x["_lon"] = pd.to_numeric(x["station_longitude"], errors="coerce")
    x = x.dropna(subset=["_lat", "_lon"]).copy()

    return gpd.GeoDataFrame(
        x,
        geometry=[Point(lon, lat) for lon, lat in zip(x["_lon"], x["_lat"])],
        crs="EPSG:4326",
    ).to_crs(base_lookup.TARGET_METRIC_CRS)


def make_key(df: pd.DataFrame) -> pd.Series:
    if "candidate_rank" in df.columns and "station_id" in df.columns:
        return df["candidate_rank"].astype(str) + "||" + df["station_id"].astype(str)
    if "station_id" in df.columns:
        return df["station_id"].astype(str)
    raise ValueError("Cannot build merge key")


def run_primary_lookup(
    case_id: str,
    water_candidates_csv: Path,
    tile_mapping_csv: Path,
    nlsc_root: Path,
) -> pd.DataFrame:
    tile_info = base_lookup.resolve_case_tile(case_id, tile_mapping_csv, nlsc_root)
    contours, elevation_field = base_lookup.load_contours(tile_info["contour_fp"])

    stations = build_station_gdf(pd.read_csv(water_candidates_csv))

    rows = []
    for _, r in stations.iterrows():
        result = base_lookup.idw_elevation_from_contours(r.geometry, contours)
        row = r.drop(labels=["geometry"]).to_dict()
        row.update(result)
        row.update({
            "case_id": case_id,
            "primary_nlsc_tile": tile_info["nlsc_tile"],
            "primary_contour_fp": str(tile_info["contour_fp"]),
            "primary_contour_elevation_field": elevation_field,
            "primary_target_metric_crs": base_lookup.TARGET_METRIC_CRS,
            "zero_fallback_used": False,
        })
        rows.append(row)

    out = pd.DataFrame(rows)
    out["elevation_review_status"] = out.apply(classify_primary_review, axis=1)

    sort_cols = [c for c in ["candidate_rank", "distance_to_route_m", "station_id"] if c in out.columns]
    if sort_cols:
        out = out.sort_values(sort_cols).reset_index(drop=True)

    return out


def run_neighbor_review(
    case_id: str,
    primary: pd.DataFrame,
    nlsc_root: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    review = primary[primary["elevation_review_status"] == "NEED_NEIGHBOR_TILE_REVIEW"].copy()
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

            trial_rows.append({
                "case_id": case_id,
                "station_row_key": original.get("station_row_key"),
                "station_id": original.get("station_id", ""),
                "station_name": original.get("station_name", ""),
                "candidate_rank": original.get("candidate_rank", ""),
                "distance_to_route_m": original.get("distance_to_route_m", ""),
                "primary_nlsc_tile": original.get("primary_nlsc_tile", ""),
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
                "candidate_nearest_contour_distance_m": result.get("nearest_contour_distance_m", np.nan),
                "candidate_n_contours_used": result.get("n_contours_used", np.nan),
                "zero_fallback_used": False,
            })

    trials = pd.DataFrame(trial_rows)

    if trials.empty:
        return trials, trials.copy()

    trials["_ok_rank"] = (
        trials["candidate_elevation_lookup_status"] == "ELEVATION_LOOKUP_OK"
    ).astype(int)
    trials["_confidence_rank"] = trials["candidate_elevation_confidence"].map(confidence_rank)
    trials["_distance_sort"] = pd.to_numeric(
        trials["candidate_nearest_contour_distance_m"],
        errors="coerce",
    ).fillna(np.inf)

    trials = trials.sort_values(
        ["station_row_key", "_ok_rank", "_confidence_rank", "_distance_sort"],
        ascending=[True, False, False, True],
    ).copy()

    best = trials.groupby("station_row_key", as_index=False).head(1).copy()

    best["recommended_nlsc_tile"] = best["nlsc_tile_candidate"]
    best["recommended_station_elevation_m"] = best["candidate_station_elevation_m"]
    best["recommended_elevation_confidence"] = best["candidate_elevation_confidence"]
    best["recommended_nearest_contour_distance_m"] = best["candidate_nearest_contour_distance_m"]
    best["recommended_elevation_lookup_status"] = best["candidate_elevation_lookup_status"]

    primary_dist = pd.to_numeric(best["primary_nearest_contour_distance_m"], errors="coerce")
    best_dist = pd.to_numeric(best["recommended_nearest_contour_distance_m"], errors="coerce")

    best["neighbor_tile_improved_distance"] = (
        best_dist.notna() & primary_dist.notna() & (best_dist < primary_dist)
    )

    best["neighbor_tile_improved_confidence"] = (
        best["recommended_elevation_confidence"].map(confidence_rank)
        > best["primary_elevation_confidence"].map(confidence_rank)
    )

    best["neighbor_tile_review_result"] = np.where(
        best["neighbor_tile_improved_distance"] | best["neighbor_tile_improved_confidence"],
        "NEIGHBOR_TILE_IMPROVED",
        "PRIMARY_TILE_REMAINS_BEST_OR_TIED",
    )

    drop_cols = [c for c in best.columns if c.startswith("_")]
    trials = trials.drop(columns=[c for c in trials.columns if c.startswith("_")])
    best = best.drop(columns=drop_cols)

    return trials, best


def finalize(primary: pd.DataFrame, neighbor_best: pd.DataFrame, case_id: str) -> pd.DataFrame:
    primary = primary.copy()
    primary["_merge_key"] = make_key(primary)

    if neighbor_best.empty:
        neighbor_best = pd.DataFrame(columns=[
            "_merge_key",
            "recommended_nlsc_tile",
            "recommended_station_elevation_m",
            "recommended_elevation_confidence",
            "recommended_nearest_contour_distance_m",
            "recommended_elevation_lookup_status",
            "neighbor_tile_review_result",
        ])
    else:
        neighbor_best = neighbor_best.copy()
        neighbor_best["_merge_key"] = make_key(neighbor_best)

    keep = [
        "_merge_key",
        "recommended_nlsc_tile",
        "recommended_station_elevation_m",
        "recommended_elevation_confidence",
        "recommended_nearest_contour_distance_m",
        "recommended_elevation_lookup_status",
        "neighbor_tile_review_result",
    ]
    keep = [c for c in keep if c in neighbor_best.columns]

    merged = primary.merge(neighbor_best[keep], on="_merge_key", how="left")

    rows = []
    for _, row in merged.iterrows():
        review_status = str(row.get("elevation_review_status", ""))

        if review_status == "ACCEPTABLE":
            final_source = "primary_tile_lookup"
            final_tile = row.get("primary_nlsc_tile", "")
            final_elev = row.get("station_elevation_m", np.nan)
            final_conf = row.get("elevation_confidence", "")
            final_nearest = row.get("nearest_contour_distance_m", np.nan)
            final_lookup_status = row.get("elevation_lookup_status", "")
            final_neighbor_result = ""
        elif review_status == "NEED_NEIGHBOR_TILE_REVIEW":
            final_source = "neighbor_tile_review_recommended"
            final_tile = row.get("recommended_nlsc_tile", "")
            final_elev = row.get("recommended_station_elevation_m", np.nan)
            final_conf = row.get("recommended_elevation_confidence", "")
            final_nearest = row.get("recommended_nearest_contour_distance_m", np.nan)
            final_lookup_status = row.get("recommended_elevation_lookup_status", "")
            final_neighbor_result = row.get("neighbor_tile_review_result", "")
        else:
            final_source = "primary_tile_lookup_review_required"
            final_tile = row.get("primary_nlsc_tile", "")
            final_elev = row.get("station_elevation_m", np.nan)
            final_conf = row.get("elevation_confidence", "")
            final_nearest = row.get("nearest_contour_distance_m", np.nan)
            final_lookup_status = row.get("elevation_lookup_status", "")
            final_neighbor_result = ""

        final_status = classify_final_status(final_conf, final_elev, final_lookup_status)

        out = row.drop(labels=["_merge_key"]).to_dict()
        out.update({
            "case_id": case_id,
            "elevation_final_source": final_source,
            "elevation_final_nlsc_tile": final_tile,
            "station_elevation_m_final": final_elev,
            "elevation_final_confidence": final_conf,
            "elevation_final_nearest_contour_distance_m": final_nearest,
            "elevation_final_lookup_status": final_lookup_status,
            "elevation_final_status": final_status,
            "elevation_final_review_required": final_status != "FINAL_ACCEPTABLE",
            "elevation_final_neighbor_tile_review_result": final_neighbor_result,
            "zero_fallback_used": False,
        })
        rows.append(out)

    final = pd.DataFrame(rows)

    sort_cols = [c for c in ["candidate_rank", "distance_to_route_m", "station_id"] if c in final.columns]
    if sort_cols:
        final = final.sort_values(sort_cols).reset_index(drop=True)

    return final


def main() -> None:
    args = parse_args()

    case_id = args.case_id
    water_candidates_csv = Path(args.water_candidates_csv)
    tile_mapping_csv = Path(args.tile_mapping_csv)
    nlsc_root = Path(args.nlsc_root)
    out_dir = Path(args.out_dir) / case_id
    out_dir.mkdir(parents=True, exist_ok=True)

    ensure_exists(water_candidates_csv, "water candidates CSV")
    ensure_exists(tile_mapping_csv, "tile mapping CSV")

    primary = run_primary_lookup(case_id, water_candidates_csv, tile_mapping_csv, nlsc_root)
    trials, best = run_neighbor_review(case_id, primary, nlsc_root)
    final = finalize(primary, best, case_id)

    primary_csv = out_dir / "water_station_candidates_elevation_lookup.csv"
    trials_csv = out_dir / "water_station_candidates_neighbor_tile_review_trials.csv"
    best_csv = out_dir / "water_station_candidates_neighbor_tile_review_best.csv"
    final_csv = out_dir / "water_station_candidates_elevation_final.csv"
    summary_csv = out_dir / "water_station_candidates_elevation_summary.csv"

    primary.to_csv(primary_csv, index=False, encoding="utf-8-sig")
    trials.to_csv(trials_csv, index=False, encoding="utf-8-sig")
    best.to_csv(best_csv, index=False, encoding="utf-8-sig")
    final.to_csv(final_csv, index=False, encoding="utf-8-sig")

    summary = pd.DataFrame([{
        "case_id": case_id,
        "water_candidate_rows": int(len(primary)),
        "primary_acceptable": int((primary["elevation_review_status"] == "ACCEPTABLE").sum()),
        "primary_need_neighbor_tile_review": int((primary["elevation_review_status"] == "NEED_NEIGHBOR_TILE_REVIEW").sum()),
        "primary_lookup_failed": int((primary["elevation_review_status"] == "LOOKUP_FAILED").sum()),
        "neighbor_tile_trials": int(len(trials)),
        "neighbor_best_rows": int(len(best)),
        "neighbor_tile_improved": int((best["neighbor_tile_review_result"] == "NEIGHBOR_TILE_IMPROVED").sum()) if not best.empty else 0,
        "final_rows": int(len(final)),
        "final_acceptable": int((final["elevation_final_status"] == "FINAL_ACCEPTABLE").sum()),
        "final_low_confidence_review_required": int((final["elevation_final_status"] == "FINAL_LOW_CONFIDENCE_REVIEW_REQUIRED").sum()),
        "final_review_required": int((final["elevation_final_status"] == "FINAL_REVIEW_REQUIRED").sum()),
        "final_lookup_failed": int((final["elevation_final_status"] == "FINAL_LOOKUP_FAILED").sum()),
        "final_elevation_missing": int((final["elevation_final_status"] == "FINAL_ELEVATION_MISSING").sum()),
        "final_review_required_total": int(final["elevation_final_review_required"].sum()),
        "final_good_confidence": int((final["elevation_final_confidence"] == "good").sum()),
        "final_moderate_confidence": int((final["elevation_final_confidence"] == "moderate").sum()),
        "final_low_confidence": int((final["elevation_final_confidence"] == "low").sum()),
        "final_source_primary_tile_lookup": int((final["elevation_final_source"] == "primary_tile_lookup").sum()),
        "final_source_neighbor_tile_review_recommended": int((final["elevation_final_source"] == "neighbor_tile_review_recommended").sum()),
        "final_tile_97233NW": int((final["elevation_final_nlsc_tile"].astype(str) == "97233NW").sum()),
        "final_tile_97233SW": int((final["elevation_final_nlsc_tile"].astype(str) == "97233SW").sum()),
        "zero_fallback_used": False,
    }])

    summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")

    print("IB3W water candidate elevation finalization written")
    print("case_id:", case_id)
    print("primary_csv:", primary_csv)
    print("trials_csv:", trials_csv)
    print("best_csv:", best_csv)
    print("final_csv:", final_csv)
    print("summary_csv:", summary_csv)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
