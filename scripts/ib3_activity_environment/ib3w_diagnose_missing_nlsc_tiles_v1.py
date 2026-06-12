from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


PRIMARY_RECOMMENDED_TILES = ["97233NE", "97233SE"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="IB3W v1: diagnose likely missing NLSC tiles behind low-confidence station elevation rows."
    )
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--station-plot-csv", required=True)
    parser.add_argument("--nlsc-root", default="nlsc_raw")
    parser.add_argument(
        "--out-dir",
        default="outputs/ib3w_missing_nlsc_tile_diagnosis_v1",
    )
    return parser.parse_args()


def ensure_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def list_available_tiles(nlsc_root: Path) -> list[str]:
    if not nlsc_root.exists():
        return []
    return sorted([p.name for p in nlsc_root.iterdir() if p.is_dir()])


def numeric_series(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce")


def lon_region(lon: float) -> str:
    if pd.isna(lon):
        return "LON_UNKNOWN"
    if lon < 121.50:
        return "WEST_SIDE_OR_BASIN_WEST"
    if lon < 121.62:
        return "CENTRAL_97233_CORRIDOR"
    if lon < 121.70:
        return "EAST_SIDE_CANDIDATE_97233E"
    return "FAR_EAST_KEELUNG_REVIEW"


def lat_region(lat: float) -> str:
    if pd.isna(lat):
        return "LAT_UNKNOWN"
    if lat < 25.05:
        return "SOUTH_BASIN"
    if lat < 25.15:
        return "CENTRAL_BASIN_YANGMINGSHAN_EDGE"
    if lat < 25.23:
        return "NORTH_COAST_EDGE"
    return "FAR_NORTH_COAST_REVIEW"


def suspected_tile_need(row: pd.Series, available_tiles: set[str]) -> tuple[str, str, str]:
    lon = row.get("station_longitude_num")
    lat = row.get("station_latitude_num")
    final_tile = str(row.get("elevation_final_nlsc_tile", ""))

    reasons = []
    primary_candidates = []

    if "97233NE" not in available_tiles and pd.notna(lon) and lon >= 121.62:
        primary_candidates.append("97233NE")
        reasons.append("station longitude is east-side while 97233NE is not available")

    if "97233SE" not in available_tiles and pd.notna(lon) and lon >= 121.50 and pd.notna(lat) and lat < 25.10:
        primary_candidates.append("97233SE")
        reasons.append("station is south/east or basin-side while 97233SE is not available")

    if pd.notna(lat) and lat >= 25.23:
        reasons.append("station is near far-north coast; north-neighbor tile review may be needed after 97233NE/NW coverage is complete")

    if pd.notna(lon) and lon >= 121.70:
        reasons.append("station is far east / Keelung-side; east-neighbor tile review may be needed after 97233NE/SE coverage is complete")

    if not primary_candidates:
        if final_tile in {"97233NW", "97233SW"}:
            reasons.append("low confidence despite current west-side tile lookup; may be due to distance from available contours or station being far from route")
        else:
            reasons.append("low confidence with unknown or non-current final tile")

    primary_candidates = sorted(set(primary_candidates))
    if primary_candidates:
        flag = "SUSPECT_MISSING_97233_EAST_TILE"
        candidate_text = "|".join(primary_candidates)
    elif pd.notna(lat) and lat >= 25.23:
        flag = "SUSPECT_NORTH_NEIGHBOR_REVIEW_AFTER_PRIMARY_TILES"
        candidate_text = "NORTH_NEIGHBOR_REVIEW"
    elif pd.notna(lon) and lon >= 121.70:
        flag = "SUSPECT_EAST_NEIGHBOR_REVIEW_AFTER_PRIMARY_TILES"
        candidate_text = "EAST_NEIGHBOR_REVIEW"
    else:
        flag = "LOW_CONFIDENCE_NOT_EXPLAINED_BY_PRIMARY_TILE_GAP"
        candidate_text = ""

    return flag, candidate_text, "; ".join(reasons)


def add_extent_summary(summary_rows: list[dict], prefix: str, df: pd.DataFrame) -> None:
    if df.empty:
        summary_rows.append({"metric": f"{prefix}_rows", "value": 0})
        return

    summary_rows.extend([
        {"metric": f"{prefix}_rows", "value": int(len(df))},
        {"metric": f"{prefix}_lat_min", "value": float(df["station_latitude_num"].min())},
        {"metric": f"{prefix}_lat_max", "value": float(df["station_latitude_num"].max())},
        {"metric": f"{prefix}_lon_min", "value": float(df["station_longitude_num"].min())},
        {"metric": f"{prefix}_lon_max", "value": float(df["station_longitude_num"].max())},
        {"metric": f"{prefix}_distance_to_route_m_min", "value": float(df["distance_to_route_m_num"].min())},
        {"metric": f"{prefix}_distance_to_route_m_max", "value": float(df["distance_to_route_m_num"].max())},
    ])


def main() -> None:
    args = parse_args()
    case_id = args.case_id

    station_csv = Path(args.station_plot_csv)
    nlsc_root = Path(args.nlsc_root)
    out_dir = Path(args.out_dir) / case_id
    out_dir.mkdir(parents=True, exist_ok=True)

    ensure_exists(station_csv, "station plot CSV")

    stations = pd.read_csv(station_csv)
    required = [
        "station_group",
        "station_id",
        "station_name",
        "station_latitude",
        "station_longitude",
        "distance_to_route_m",
        "station_elevation_m_final",
        "elevation_final_status",
        "elevation_final_confidence",
        "elevation_final_nlsc_tile",
    ]
    missing = [c for c in required if c not in stations.columns]
    if missing:
        raise ValueError(f"station plot CSV missing required columns: {missing}")

    available_tiles = list_available_tiles(nlsc_root)
    available_tile_set = set(available_tiles)

    stations["station_latitude_num"] = numeric_series(stations, "station_latitude")
    stations["station_longitude_num"] = numeric_series(stations, "station_longitude")
    stations["distance_to_route_m_num"] = numeric_series(stations, "distance_to_route_m")

    low = stations[stations["elevation_final_status"] == "FINAL_LOW_CONFIDENCE_REVIEW_REQUIRED"].copy()
    low["lat_region"] = low["station_latitude_num"].apply(lat_region)
    low["lon_region"] = low["station_longitude_num"].apply(lon_region)

    tile_results = low.apply(
        lambda r: suspected_tile_need(r, available_tile_set),
        axis=1,
        result_type="expand",
    )
    tile_results.columns = [
        "suspected_missing_tile_need",
        "recommended_missing_tile_candidate",
        "missing_tile_diagnosis_reason",
    ]
    diagnosis = pd.concat([low.reset_index(drop=True), tile_results.reset_index(drop=True)], axis=1)

    diagnosis["available_nlsc_tiles"] = "|".join(available_tiles)
    diagnosis["primary_recommended_missing_tiles"] = "|".join(
        [t for t in PRIMARY_RECOMMENDED_TILES if t not in available_tile_set]
    )
    diagnosis["diagnosis_scope"] = "MISSING_NLSC_TILE_DIAGNOSIS_ONLY_NO_LOOKUP_NO_FUSION"
    diagnosis["zero_fallback_used"] = False

    out_csv = out_dir / "missing_nlsc_tile_diagnosis.csv"
    summary_csv = out_dir / "missing_nlsc_tile_diagnosis_summary.csv"

    diagnosis.to_csv(out_csv, index=False, encoding="utf-8-sig")

    summary_rows: list[dict] = []
    summary_rows.append({"metric": "case_id", "value": case_id})
    summary_rows.append({"metric": "available_nlsc_tiles", "value": "|".join(available_tiles)})
    summary_rows.append({"metric": "available_nlsc_tile_count", "value": len(available_tiles)})
    summary_rows.append({
        "metric": "primary_recommended_missing_tiles",
        "value": "|".join([t for t in PRIMARY_RECOMMENDED_TILES if t not in available_tile_set]),
    })
    summary_rows.append({"metric": "station_rows", "value": int(len(stations))})
    add_extent_summary(summary_rows, "low_confidence", diagnosis)

    for group, n in diagnosis["station_group"].value_counts(dropna=False).sort_index().items():
        summary_rows.append({"metric": f"low_station_group_{group}", "value": int(n)})

    for tile, n in diagnosis["elevation_final_nlsc_tile"].value_counts(dropna=False).sort_index().items():
        summary_rows.append({"metric": f"low_current_final_tile_{tile}", "value": int(n)})

    for region, n in diagnosis["lon_region"].value_counts(dropna=False).sort_index().items():
        summary_rows.append({"metric": f"low_lon_region_{region}", "value": int(n)})

    for region, n in diagnosis["lat_region"].value_counts(dropna=False).sort_index().items():
        summary_rows.append({"metric": f"low_lat_region_{region}", "value": int(n)})

    for flag, n in diagnosis["suspected_missing_tile_need"].value_counts(dropna=False).sort_index().items():
        summary_rows.append({"metric": f"suspected_{flag}", "value": int(n)})

    summary_rows.append({"metric": "zero_fallback_used", "value": False})
    summary_rows.append({"metric": "branch_scope", "value": "diagnosis_only_no_new_elevation_lookup_no_weather_fusion_no_risk_adjustment"})

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")

    print("IB3W missing NLSC tile diagnosis written")
    print("case_id:", case_id)
    print("station_csv:", station_csv)
    print("nlsc_root:", nlsc_root)
    print("available_tiles:", "|".join(available_tiles))
    print("out_csv:", out_csv)
    print("summary_csv:", summary_csv)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
