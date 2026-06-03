from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import linemerge, unary_union


ROUTE_CASE_MAP = {
    "juansi_waterfall": "juansi_waterfall_fitcsv_20260503",
    "qixing_lengshuikeng": "qixing_lengshuikeng_main_peak_20260523",
}

OUTPUT_COLUMNS = [
    "route_folder",
    "case_id",
    "subject_id",
    "trial_id",
    "activity_id",
    "timestamp_s",
    "elapsed_sec",
    "dt_sec",
    "lat",
    "lon",
    "ele_m",
    "distance_m",
    "heart_rate_bpm",
    "route_dist_m",
    "nearest_route_dist_m",
    "offset_m",
    "segment_id",
    "direction_hint",
    "match_quality",
    "source_file",
]

SUMMARY_COLUMNS = [
    "route_folder",
    "case_id",
    "subject_id",
    "trial_id",
    "rows_input",
    "rows_matched",
    "match_ratio",
    "offset_m_mean",
    "offset_m_p95",
    "route_dist_min",
    "route_dist_max",
    "duration_sec",
    "distance_max",
    "sampling_profile",
    "time_quality",
    "status",
    "error",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Batch map-match standardized activity CSV files to route profile "
            "distance axes for ib3a downstream processing."
        )
    )
    parser.add_argument(
        "--manifest-csv",
        default="outputs/activity_standardized/activity_standardized_manifest.csv",
        help="Standardized activity manifest CSV.",
    )
    parser.add_argument(
        "--standardized-root",
        default="outputs/activity_standardized",
        help="Root folder containing standardized activity CSV files.",
    )
    parser.add_argument(
        "--route-profile-root",
        default="outputs/ib1_route_profile",
        help="Root folder containing ib1 route profile outputs.",
    )
    parser.add_argument(
        "--out-dir",
        default="outputs/ib3a_mapmatched_standardized_activity",
        help="Output directory for mapmatched activity files and batch summary.",
    )
    parser.add_argument(
        "--segment-m",
        type=float,
        default=20.0,
        help="Segment length in meters for provisional segment_id.",
    )
    parser.add_argument(
        "--off-route-m",
        type=float,
        default=50.0,
        help="Offset threshold above which points are marked off_route.",
    )
    return parser.parse_args()


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def is_standardized_status(value: Any) -> bool:
    if pd.isna(value):
        return False
    status = str(value).strip().lower()
    return status == "standardized" or status.startswith("standardized_")


def resolve_path(path_like: Any, fallback_root: Path | None = None) -> Path:
    path = Path(str(path_like))
    if path.exists() or path.is_absolute() or fallback_root is None:
        return path
    return fallback_root / path.name


def extract_single_route_line(gdf_m: gpd.GeoDataFrame) -> LineString:
    geom_types = set(gdf_m.geometry.geom_type.dropna().unique())

    if geom_types.issubset({"Point"}):
        sort_col = None
        for candidate in ["dist_m", "profile_dist_m", "cum_dist_m", "distance_m", "sample_idx"]:
            if candidate in gdf_m.columns:
                sort_col = candidate
                break
        ordered = gdf_m.sort_values(sort_col).copy() if sort_col else gdf_m.copy()
        points = [geom for geom in ordered.geometry if geom is not None and not geom.is_empty]
        if len(points) < 2:
            raise ValueError("route profile points must contain at least 2 valid points")
        return LineString(points)

    geoms = []
    for geom in gdf_m.geometry:
        if geom is None or geom.is_empty:
            continue
        if geom.geom_type == "LineString":
            geoms.append(geom)
        elif geom.geom_type == "MultiLineString":
            geoms.extend(list(geom.geoms))

    if not geoms:
        raise ValueError("route geometry must contain Point, LineString, or MultiLineString features")

    merged = linemerge(unary_union(geoms))
    if isinstance(merged, LineString):
        return merged
    if isinstance(merged, MultiLineString):
        return max(list(merged.geoms), key=lambda line: line.length)
    raise ValueError(f"unsupported route geometry type: {merged.geom_type}")


def load_route_axis(route_profile_root: Path, case_id: str) -> dict[str, Any]:
    case_dir = route_profile_root / case_id
    profile_csv = case_dir / f"{case_id}_route_profile.csv"
    profile_points = case_dir / f"{case_id}_route_profile_points.geojson"

    if not profile_csv.exists():
        raise FileNotFoundError(f"missing route profile CSV: {profile_csv}")
    if not profile_points.exists():
        raise FileNotFoundError(f"missing route profile points GeoJSON: {profile_points}")

    profile = pd.read_csv(profile_csv, low_memory=False)
    if "dist_m" not in profile.columns:
        raise ValueError(f"route profile missing dist_m column: {profile_csv}")

    route_gdf = gpd.read_file(profile_points)
    if route_gdf.empty:
        raise ValueError(f"route profile points are empty: {profile_points}")
    if route_gdf.crs is None:
        route_gdf = route_gdf.set_crs("EPSG:4326")

    metric_crs = route_gdf.estimate_utm_crs()
    route_gdf_m = route_gdf.to_crs(metric_crs)
    route_line_m = extract_single_route_line(route_gdf_m)

    dist_values = np.array(
        pd.to_numeric(profile["dist_m"], errors="coerce").dropna().to_numpy(dtype=float),
        copy=True,
    )
    if len(dist_values) == 0:
        raise ValueError(f"route profile has no numeric dist_m values: {profile_csv}")
    dist_values.sort()

    return {
        "case_id": case_id,
        "profile_csv": profile_csv,
        "profile_points": profile_points,
        "metric_crs": metric_crs,
        "route_line_m": route_line_m,
        "route_len_m": float(route_line_m.length),
        "profile_dist_values": dist_values,
    }


def nearest_profile_dist(projected_dist_m: float, profile_dist_values: np.ndarray) -> float:
    idx = int(np.searchsorted(profile_dist_values, projected_dist_m))
    if idx <= 0:
        return float(profile_dist_values[0])
    if idx >= len(profile_dist_values):
        return float(profile_dist_values[-1])
    before = profile_dist_values[idx - 1]
    after = profile_dist_values[idx]
    return float(before if abs(projected_dist_m - before) <= abs(after - projected_dist_m) else after)


def classify_match_quality(offset_m: float, off_route_m: float) -> str:
    if pd.isna(offset_m):
        return "unmatched"
    if offset_m > off_route_m:
        return "off_route"
    if offset_m <= 10.0:
        return "good"
    if offset_m <= 25.0:
        return "acceptable"
    return "weak"


def add_direction_hint(route_dist: pd.Series) -> pd.Series:
    delta = pd.to_numeric(route_dist, errors="coerce").diff()
    hints = np.where(delta > 1.0, "forward", np.where(delta < -1.0, "backtrack", "stationary"))
    if len(hints):
        hints[0] = "start"
    return pd.Series(hints, index=route_dist.index)


def mapmatch_activity(
    activity_csv: Path,
    route_folder: str,
    case_id: str,
    route_axis: dict[str, Any],
    segment_m: float,
    off_route_m: float,
) -> pd.DataFrame:
    activity = pd.read_csv(activity_csv, low_memory=False)
    required = ["lat", "lon"]
    missing = [col for col in required if col not in activity.columns]
    if missing:
        raise ValueError(f"activity CSV missing required columns: {missing}")

    activity["lat"] = pd.to_numeric(activity["lat"], errors="coerce")
    activity["lon"] = pd.to_numeric(activity["lon"], errors="coerce")
    activity = activity.dropna(subset=["lat", "lon"]).copy()
    if activity.empty:
        raise ValueError("activity has no valid lat/lon rows")

    gdf = gpd.GeoDataFrame(
        activity,
        geometry=gpd.points_from_xy(activity["lon"], activity["lat"]),
        crs="EPSG:4326",
    )
    gdf_m = gdf.to_crs(route_axis["metric_crs"])
    route_line_m: LineString = route_axis["route_line_m"]
    profile_dist_values: np.ndarray = route_axis["profile_dist_values"]

    route_dist = []
    nearest_dist = []
    offsets = []
    for geom in gdf_m.geometry:
        projected = float(route_line_m.project(geom))
        matched_point = route_line_m.interpolate(projected)
        route_dist.append(projected)
        nearest_dist.append(nearest_profile_dist(projected, profile_dist_values))
        offsets.append(float(geom.distance(matched_point)))

    out = activity.copy()
    out["route_folder"] = route_folder
    out["case_id"] = case_id
    out["route_dist_m"] = route_dist
    out["nearest_route_dist_m"] = nearest_dist
    out["offset_m"] = offsets
    out["segment_id"] = np.floor(pd.to_numeric(out["route_dist_m"], errors="coerce") / segment_m).astype("Int64")
    out["direction_hint"] = add_direction_hint(out["route_dist_m"])
    out["match_quality"] = [classify_match_quality(offset, off_route_m) for offset in out["offset_m"]]

    for col in OUTPUT_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA
    return out[OUTPUT_COLUMNS]


def summarize_result(
    manifest_row: pd.Series,
    case_id: str,
    rows_input: int,
    result: pd.DataFrame | None,
    status: str,
    error: str = "",
) -> dict[str, Any]:
    if result is None or result.empty:
        return {
            "route_folder": manifest_row.get("route_folder"),
            "case_id": case_id,
            "subject_id": manifest_row.get("subject_id"),
            "trial_id": manifest_row.get("trial_id"),
            "rows_input": rows_input,
            "rows_matched": 0,
            "match_ratio": 0.0,
            "offset_m_mean": np.nan,
            "offset_m_p95": np.nan,
            "route_dist_min": np.nan,
            "route_dist_max": np.nan,
            "duration_sec": manifest_row.get("duration_sec", np.nan),
            "distance_max": manifest_row.get("distance_max", np.nan),
            "sampling_profile": manifest_row.get("sampling_profile", ""),
            "time_quality": manifest_row.get("time_quality", ""),
            "status": status,
            "error": error,
        }

    matched_mask = result["route_dist_m"].notna()
    return {
        "route_folder": manifest_row.get("route_folder"),
        "case_id": case_id,
        "subject_id": manifest_row.get("subject_id"),
        "trial_id": manifest_row.get("trial_id"),
        "rows_input": rows_input,
        "rows_matched": int(matched_mask.sum()),
        "match_ratio": float(matched_mask.mean()) if len(result) else 0.0,
        "offset_m_mean": float(result["offset_m"].mean()) if result["offset_m"].notna().any() else np.nan,
        "offset_m_p95": float(result["offset_m"].quantile(0.95)) if result["offset_m"].notna().any() else np.nan,
        "route_dist_min": float(result["route_dist_m"].min()) if result["route_dist_m"].notna().any() else np.nan,
        "route_dist_max": float(result["route_dist_m"].max()) if result["route_dist_m"].notna().any() else np.nan,
        "duration_sec": manifest_row.get("duration_sec", np.nan),
        "distance_max": manifest_row.get("distance_max", np.nan),
        "sampling_profile": manifest_row.get("sampling_profile", ""),
        "time_quality": manifest_row.get("time_quality", ""),
        "status": status,
        "error": error,
    }


def run(args: argparse.Namespace) -> int:
    manifest_csv = Path(args.manifest_csv)
    standardized_root = Path(args.standardized_root)
    route_profile_root = Path(args.route_profile_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = pd.read_csv(manifest_csv, low_memory=False)
    selected = manifest[
        manifest["status"].map(is_standardized_status)
        & manifest["usable_for_time_model"].map(as_bool)
    ].copy()

    route_axes: dict[str, dict[str, Any]] = {}
    summary_rows: list[dict[str, Any]] = []

    for _, row in selected.iterrows():
        route_folder = str(row["route_folder"])
        case_id = ROUTE_CASE_MAP.get(route_folder)
        subject_id = str(int(row["subject_id"])) if pd.notna(row["subject_id"]) else ""
        trial_id = int(row["trial_id"]) if pd.notna(row["trial_id"]) else 1

        if case_id is None:
            summary_rows.append(summarize_result(row, "", 0, None, "error", f"no case_id mapping for {route_folder}"))
            continue

        try:
            if case_id not in route_axes:
                route_axes[case_id] = load_route_axis(route_profile_root, case_id)

            activity_csv = resolve_path(row["output_file"], standardized_root / route_folder)
            if not activity_csv.exists():
                raise FileNotFoundError(f"missing standardized activity CSV: {activity_csv}")

            result = mapmatch_activity(
                activity_csv=activity_csv,
                route_folder=route_folder,
                case_id=case_id,
                route_axis=route_axes[case_id],
                segment_m=args.segment_m,
                off_route_m=args.off_route_m,
            )

            route_out_dir = out_dir / route_folder
            route_out_dir.mkdir(parents=True, exist_ok=True)
            output_csv = route_out_dir / f"{subject_id}_{trial_id}_mapmatched.csv"
            result.to_csv(output_csv, index=False, encoding="utf-8-sig")

            summary_rows.append(
                summarize_result(
                    manifest_row=row,
                    case_id=case_id,
                    rows_input=len(result),
                    result=result,
                    status="mapmatched",
                )
            )
        except Exception as exc:
            rows_input = int(row["rows_valid"]) if pd.notna(row.get("rows_valid", np.nan)) else 0
            summary_rows.append(summarize_result(row, case_id or "", rows_input, None, "error", str(exc)))

    summary = pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS)
    summary_path = out_dir / "ib3a_batch_mapmatch_summary.csv"
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")

    status_counts = summary["status"].value_counts(dropna=False).to_dict() if not summary.empty else {}
    print(f"Selected standardized activities: {len(selected)}")
    print(f"Wrote summary: {summary_path}")
    print(f"Status counts: {status_counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
