from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


ACCEPTABLE_CONFIDENCE = {"good", "moderate"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="IB3W v1: finalize route candidate station elevation from primary lookup and neighbor tile review."
    )
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--primary-csv", required=True)
    parser.add_argument("--neighbor-best-csv", required=True)
    parser.add_argument(
        "--out-dir",
        default="outputs/ib3w_route_candidate_elevation_finalize_v1",
    )
    return parser.parse_args()


def ensure_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def make_key(df: pd.DataFrame) -> pd.Series:
    if "candidate_rank" in df.columns and "station_id" in df.columns:
        return df["candidate_rank"].astype(str) + "||" + df["station_id"].astype(str)
    if "station_id" in df.columns:
        return df["station_id"].astype(str)
    raise ValueError("Cannot build merge key: missing candidate_rank/station_id columns")


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


def main() -> None:
    args = parse_args()

    case_id = args.case_id
    primary_csv = Path(args.primary_csv)
    neighbor_best_csv = Path(args.neighbor_best_csv)
    out_dir = Path(args.out_dir) / case_id
    out_dir.mkdir(parents=True, exist_ok=True)

    ensure_exists(primary_csv, "primary lookup CSV")
    ensure_exists(neighbor_best_csv, "neighbor best CSV")

    primary = pd.read_csv(primary_csv)
    neighbor = pd.read_csv(neighbor_best_csv)

    if "elevation_review_status" not in primary.columns:
        raise ValueError("primary CSV must contain elevation_review_status")

    primary = primary.copy()
    primary["_merge_key"] = make_key(primary)

    neighbor = neighbor.copy()
    neighbor["_merge_key"] = make_key(neighbor)

    neighbor_keep_cols = [
        "_merge_key",
        "recommended_nlsc_tile",
        "recommended_station_elevation_m",
        "recommended_elevation_confidence",
        "recommended_nearest_contour_distance_m",
        "recommended_elevation_lookup_status",
        "neighbor_tile_review_result",
        "neighbor_tile_improved_distance",
        "neighbor_tile_improved_confidence",
    ]
    neighbor_keep_cols = [c for c in neighbor_keep_cols if c in neighbor.columns]

    merged = primary.merge(
        neighbor[neighbor_keep_cols],
        on="_merge_key",
        how="left",
        validate="one_to_one",
    )

    final_rows = []

    for _, row in merged.iterrows():
        review_status = str(row.get("elevation_review_status", ""))

        if review_status == "ACCEPTABLE":
            final_source = "primary_tile_lookup"
            final_tile = row.get("nlsc_tile", "")
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
            final_tile = row.get("nlsc_tile", "")
            final_elev = row.get("station_elevation_m", np.nan)
            final_conf = row.get("elevation_confidence", "")
            final_nearest = row.get("nearest_contour_distance_m", np.nan)
            final_lookup_status = row.get("elevation_lookup_status", "")
            final_neighbor_result = ""

        final_status = classify_final_status(final_conf, final_elev, final_lookup_status)

        out_row = row.drop(labels=["_merge_key"]).to_dict()
        out_row.update({
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
        final_rows.append(out_row)

    final = pd.DataFrame(final_rows)

    sort_cols = [c for c in ["candidate_rank", "distance_to_route_m", "station_id"] if c in final.columns]
    if sort_cols:
        final = final.sort_values(sort_cols).reset_index(drop=True)

    out_csv = out_dir / "weather_station_candidates_elevation_final.csv"
    summary_csv = out_dir / "weather_station_candidates_elevation_final_summary.csv"

    final.to_csv(out_csv, index=False, encoding="utf-8-sig")

    summary = pd.DataFrame([{
        "case_id": case_id,
        "primary_rows": int(len(primary)),
        "neighbor_best_rows": int(len(neighbor)),
        "final_rows": int(len(final)),
        "primary_acceptable_rows": int((primary["elevation_review_status"] == "ACCEPTABLE").sum()),
        "primary_need_neighbor_tile_review_rows": int((primary["elevation_review_status"] == "NEED_NEIGHBOR_TILE_REVIEW").sum()),
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

    print("IB3W route candidate station elevation final table written")
    print("case_id:", case_id)
    print("primary_csv:", primary_csv)
    print("neighbor_best_csv:", neighbor_best_csv)
    print("out_csv:", out_csv)
    print("summary_csv:", summary_csv)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
