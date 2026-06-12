from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point


DEFAULT_CONTOUR_CRS_IF_MISSING = "EPSG:3826"
TARGET_METRIC_CRS = "EPSG:3826"

SEARCH_RADII_M = [500, 1000, 2000, 5000]
MAX_CONTOURS_USED = 12
MIN_CONTOURS_REQUIRED = 2
IDW_POWER = 2.0
MIN_DISTANCE_M = 1.0

ELEVATION_CONFIDENCE_GOOD_DISTANCE_M = 300
ELEVATION_CONFIDENCE_OK_DISTANCE_M = 1000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "IB3W v1: lookup route-scoped weather candidate station elevation "
            "from case-level NLSC tile mapping and ContourL.shp"
        )
    )
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--tile-mapping-csv", required=True)
    parser.add_argument("--weather-candidates-csv", required=True)
    parser.add_argument("--nlsc-root", default="nlsc_raw")
    parser.add_argument(
        "--out-dir",
        default="outputs/ib3w_route_candidate_terrain_elevation_lookup_v1",
    )
    return parser.parse_args()


def ensure_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def resolve_case_tile(case_id: str, mapping_csv: Path, nlsc_root: Path) -> dict:
    ensure_exists(mapping_csv, "tile mapping CSV")

    df = pd.read_csv(mapping_csv)
    if "case_id" not in df.columns or "nlsc_tile" not in df.columns:
        raise ValueError("tile mapping CSV must contain case_id and nlsc_tile columns")

    hit = df[df["case_id"].astype(str) == str(case_id)].copy()
    if hit.empty:
        raise ValueError(f"case_id not found in tile mapping: {case_id}")

    if len(hit) > 1:
        raise ValueError(f"case_id maps to multiple rows: {case_id}")

    row = hit.iloc[0].to_dict()
    tile = str(row["nlsc_tile"])

    contour_rel = row.get("contour_relative_path", "")
    if isinstance(contour_rel, str) and contour_rel.strip():
        contour_fp = Path(contour_rel)
    else:
        contour_fp = nlsc_root / tile / "向量25K" / "ContourL.shp"

    if not contour_fp.is_absolute():
        contour_fp = Path.cwd() / contour_fp

    return {
        "nlsc_tile": tile,
        "contour_fp": contour_fp,
        "tile_source": row.get("tile_source", ""),
        "tile_status": row.get("tile_status", ""),
        "tile_notes": row.get("notes", ""),
    }


def detect_elevation_field(gdf: gpd.GeoDataFrame) -> str:
    candidates = [
        "ELEV", "Elev", "elev",
        "ELEVATION", "Elevation", "elevation",
        "HEIGHT", "Height", "height",
        "Z", "z",
        "Contour", "CONTOUR", "contour",
        "contour_m", "CONTOUR_M",
        "高程", "等高線", "標高",
        "zv2", "ZV2",
    ]

    cols_lower = {str(c).lower(): c for c in gdf.columns}

    for c in candidates:
        if c in gdf.columns:
            return c
        if c.lower() in cols_lower:
            return cols_lower[c.lower()]

    numeric_cols = [
        c for c in gdf.columns
        if c != "geometry" and pd.api.types.is_numeric_dtype(gdf[c])
    ]

    for c in numeric_cols:
        cl = str(c).lower()
        if any(k in cl for k in ["elev", "height", "contour", "zv", "z"]):
            return c

    numeric_candidates = []
    for c in numeric_cols:
        s = pd.to_numeric(gdf[c], errors="coerce").dropna()
        if s.empty:
            continue
        valid_ratio = ((s >= -100) & (s <= 4000)).mean()
        if valid_ratio >= 0.8:
            numeric_candidates.append((c, valid_ratio, float(s.median())))

    if numeric_candidates:
        numeric_candidates = sorted(
            numeric_candidates,
            key=lambda x: (-x[1], abs(x[2] - 500)),
        )
        return numeric_candidates[0][0]

    raise ValueError(
        "Could not detect contour elevation field. "
        f"Available columns: {list(gdf.columns)}"
    )


def load_contours(contour_fp: Path) -> tuple[gpd.GeoDataFrame, str]:
    ensure_exists(contour_fp, "ContourL.shp")

    gdf = gpd.read_file(contour_fp)
    if gdf.empty:
        raise ValueError(f"Contour shapefile is empty: {contour_fp}")

    if gdf.crs is None:
        gdf = gdf.set_crs(DEFAULT_CONTOUR_CRS_IF_MISSING)

    elevation_field = detect_elevation_field(gdf)

    gdf["contour_elevation_m"] = pd.to_numeric(
        gdf[elevation_field],
        errors="coerce",
    )
    gdf = gdf.dropna(subset=["contour_elevation_m", "geometry"]).copy()
    gdf = gdf[gdf.geometry.type.isin(["LineString", "MultiLineString"])].copy()

    if gdf.empty:
        raise ValueError(f"No valid contour lines after filtering: {contour_fp}")

    gdf = gdf.to_crs(TARGET_METRIC_CRS)
    return gdf, elevation_field


def find_coord_columns(df: pd.DataFrame) -> tuple[str, str]:
    lat_candidates = [
        "station_latitude", "station_lat", "lat", "latitude", "緯度",
    ]
    lon_candidates = [
        "station_longitude", "station_lon", "station_lng", "lon", "lng", "longitude", "經度",
    ]

    lat_col = next((c for c in lat_candidates if c in df.columns), None)
    lon_col = next((c for c in lon_candidates if c in df.columns), None)

    if lat_col is None or lon_col is None:
        raise ValueError(
            f"Cannot find station coordinate columns. columns={list(df.columns)}"
        )

    return lat_col, lon_col


def read_station_candidates(csv_fp: Path) -> gpd.GeoDataFrame:
    ensure_exists(csv_fp, "weather candidates CSV")

    df = pd.read_csv(csv_fp)
    if df.empty:
        raise ValueError(f"weather candidates CSV is empty: {csv_fp}")

    lat_col, lon_col = find_coord_columns(df)

    df["station_latitude_lookup"] = pd.to_numeric(df[lat_col], errors="coerce")
    df["station_longitude_lookup"] = pd.to_numeric(df[lon_col], errors="coerce")
    df = df.dropna(subset=["station_latitude_lookup", "station_longitude_lookup"]).copy()

    gdf = gpd.GeoDataFrame(
        df,
        geometry=[
            Point(lon, lat)
            for lon, lat in zip(
                df["station_longitude_lookup"],
                df["station_latitude_lookup"],
            )
        ],
        crs="EPSG:4326",
    ).to_crs(TARGET_METRIC_CRS)

    return gdf


def idw_elevation_from_contours(
    station_geom,
    contours_gdf: gpd.GeoDataFrame,
) -> dict:
    sindex = contours_gdf.sindex

    selected = None
    selected_radius = np.nan

    for radius_m in SEARCH_RADII_M:
        buffer_geom = station_geom.buffer(radius_m)
        idx = list(sindex.query(buffer_geom, predicate="intersects"))

        if not idx:
            continue

        cand = contours_gdf.iloc[idx].copy()
        cand["distance_m"] = cand.geometry.distance(station_geom)
        cand = cand[cand["distance_m"] <= radius_m].copy()

        if cand.empty:
            continue

        cand = cand.sort_values("distance_m").head(MAX_CONTOURS_USED)

        if len(cand) >= MIN_CONTOURS_REQUIRED:
            selected = cand
            selected_radius = radius_m
            break

    if selected is None:
        cand = contours_gdf.copy()
        cand["distance_m"] = cand.geometry.distance(station_geom)
        cand = cand.sort_values("distance_m").head(MAX_CONTOURS_USED)
        selected = cand

    if selected.empty:
        return {
            "station_elevation_m": np.nan,
            "elevation_lookup_status": "NO_VALID_CONTOURS",
            "elevation_source": "nlsc_contour_failed",
            "elevation_confidence": "none",
            "elevation_search_radius_m": selected_radius,
            "n_contours_used": 0,
            "nearest_contour_distance_m": np.nan,
            "nearest_contour_elevation_m": np.nan,
            "contour_elevation_min_m": np.nan,
            "contour_elevation_max_m": np.nan,
            "contour_elevation_std_m": np.nan,
        }

    selected = selected.copy()

    dist = selected["distance_m"].clip(lower=MIN_DISTANCE_M)
    weights = 1.0 / (dist ** IDW_POWER)

    elev = pd.to_numeric(selected["contour_elevation_m"], errors="coerce")
    valid = elev.notna() & weights.notna() & (weights > 0)

    if not valid.any():
        return {
            "station_elevation_m": np.nan,
            "elevation_lookup_status": "NO_VALID_CONTOURS",
            "elevation_source": "nlsc_contour_failed",
            "elevation_confidence": "none",
            "elevation_search_radius_m": selected_radius,
            "n_contours_used": int(len(selected)),
            "nearest_contour_distance_m": np.nan,
            "nearest_contour_elevation_m": np.nan,
            "contour_elevation_min_m": np.nan,
            "contour_elevation_max_m": np.nan,
            "contour_elevation_std_m": np.nan,
        }

    station_elev = float(np.average(elev[valid], weights=weights[valid]))

    nearest = selected.sort_values("distance_m").iloc[0]
    nearest_dist = float(nearest["distance_m"])
    nearest_elev = float(nearest["contour_elevation_m"])

    if nearest_dist <= ELEVATION_CONFIDENCE_GOOD_DISTANCE_M:
        confidence = "good"
    elif nearest_dist <= ELEVATION_CONFIDENCE_OK_DISTANCE_M:
        confidence = "moderate"
    else:
        confidence = "low"

    return {
        "station_elevation_m": station_elev,
        "elevation_lookup_status": "ELEVATION_LOOKUP_OK",
        "elevation_source": "nlsc_contour_idw",
        "elevation_confidence": confidence,
        "elevation_search_radius_m": selected_radius,
        "n_contours_used": int(len(selected)),
        "nearest_contour_distance_m": nearest_dist,
        "nearest_contour_elevation_m": nearest_elev,
        "contour_elevation_min_m": float(elev.min()),
        "contour_elevation_max_m": float(elev.max()),
        "contour_elevation_std_m": float(elev.std()) if len(elev.dropna()) > 1 else 0.0,
    }


def main() -> None:
    args = parse_args()

    case_id = args.case_id
    tile_mapping_csv = Path(args.tile_mapping_csv)
    weather_candidates_csv = Path(args.weather_candidates_csv)
    nlsc_root = Path(args.nlsc_root)
    out_dir = Path(args.out_dir) / case_id
    out_dir.mkdir(parents=True, exist_ok=True)

    tile_info = resolve_case_tile(case_id, tile_mapping_csv, nlsc_root)
    contour_fp = tile_info["contour_fp"]

    contours, elevation_field = load_contours(contour_fp)
    stations = read_station_candidates(weather_candidates_csv)

    rows = []
    for _, r in stations.iterrows():
        result = idw_elevation_from_contours(r.geometry, contours)
        row = r.drop(labels=["geometry"]).to_dict()
        row.update(result)
        row.update({
            "case_id": case_id,
            "nlsc_tile": tile_info["nlsc_tile"],
            "tile_source": tile_info["tile_source"],
            "tile_status": tile_info["tile_status"],
            "contour_fp": str(contour_fp),
            "contour_elevation_field": elevation_field,
            "target_metric_crs": TARGET_METRIC_CRS,
            "search_radii_m": "|".join(str(x) for x in SEARCH_RADII_M),
            "max_contours_used": MAX_CONTOURS_USED,
            "min_contours_required": MIN_CONTOURS_REQUIRED,
            "idw_power": IDW_POWER,
        })
        rows.append(row)

    out = pd.DataFrame(rows)

    sort_cols = [c for c in ["candidate_rank", "distance_to_route_m", "station_id"] if c in out.columns]
    def classify_review(row):
        status = str(row.get("elevation_lookup_status", ""))
        confidence = str(row.get("elevation_confidence", ""))
        nearest = pd.to_numeric(row.get("nearest_contour_distance_m", np.nan), errors="coerce")

        if status != "ELEVATION_LOOKUP_OK":
            return "LOOKUP_FAILED"
        if confidence in ["good", "moderate"]:
            return "ACCEPTABLE"
        if pd.notna(nearest) and nearest > ELEVATION_CONFIDENCE_OK_DISTANCE_M:
            return "NEED_NEIGHBOR_TILE_REVIEW"
        return "REVIEW_REQUIRED"

    out["elevation_review_status"] = out.apply(classify_review, axis=1)

    if sort_cols:
        out = out.sort_values(sort_cols).reset_index(drop=True)

    out_csv = out_dir / "weather_station_candidates_elevation_lookup.csv"
    summary_csv = out_dir / "weather_station_candidates_elevation_lookup_summary.csv"

    out.to_csv(out_csv, index=False, encoding="utf-8-sig")

    summary = pd.DataFrame([
        {
            "case_id": case_id,
            "input_weather_candidates": len(stations),
            "output_rows": len(out),
            "nlsc_tile": tile_info["nlsc_tile"],
            "contour_fp": str(contour_fp),
            "contour_elevation_field": elevation_field,
            "elevation_lookup_ok": int((out["elevation_lookup_status"] == "ELEVATION_LOOKUP_OK").sum()),
            "no_valid_contours": int((out["elevation_lookup_status"] == "NO_VALID_CONTOURS").sum()),
            "good_confidence": int((out["elevation_confidence"] == "good").sum()),
            "moderate_confidence": int((out["elevation_confidence"] == "moderate").sum()),
            "low_confidence": int((out["elevation_confidence"] == "low").sum()),
            "station_elevation_missing": int(out["station_elevation_m"].isna().sum()),
            "acceptable": int((out["elevation_review_status"] == "ACCEPTABLE").sum()),
            "need_neighbor_tile_review": int((out["elevation_review_status"] == "NEED_NEIGHBOR_TILE_REVIEW").sum()),
            "review_required": int((out["elevation_review_status"] == "REVIEW_REQUIRED").sum()),
            "lookup_failed": int((out["elevation_review_status"] == "LOOKUP_FAILED").sum()),
            "zero_fallback_used": False,
        }
    ])
    summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")

    print("IB3W route candidate terrain elevation lookup written")
    print("case_id:", case_id)
    print("nlsc_tile:", tile_info["nlsc_tile"])
    print("contour_fp:", contour_fp)
    print("contour_elevation_field:", elevation_field)
    print("input_weather_candidates:", len(stations))
    print("output_rows:", len(out))
    print("summary_csv:", summary_csv)
    print("out_csv:", out_csv)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()


