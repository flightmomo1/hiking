from pathlib import Path
import argparse
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.ops import substring


# ---------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_STAGE = "ib1g_route_axis_terrain_evidence_v2_0"


def resolve_path(value):
    p = Path(value)
    if p.is_absolute():
        return p
    return PROJECT_ROOT / p


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Compute direction-neutral NLSC contour terrain evidence "
            "along an authoritative Route Axis."
        )
    )

    parser.add_argument("--case-id", required=True)
    parser.add_argument("--case-name", default=None)

    parser.add_argument(
        "--route-line-fp",
        required=True,
        help="Authoritative IB0D Route Axis GeoJSON.",
    )

    parser.add_argument(
        "--contour-fp",
        required=True,
        help="Validated NLSC ContourL shapefile.",
    )

    parser.add_argument(
        "--tile",
        required=True,
        help="NLSC tile identifier, for provenance.",
    )

    parser.add_argument(
        "--out-dir",
        default=None,
        help=(
            "Output directory. Default: "
            "outputs/ib1g_route_axis_terrain_evidence/<case-id>"
        ),
    )

    parser.add_argument(
        "--segment-len-m",
        type=float,
        default=20.0,
    )

    parser.add_argument(
        "--window-radius-m",
        type=float,
        default=50.0,
    )

    parser.add_argument(
        "--contour-count-buffer-m",
        "--density-buffer-m",
        dest="contour_count_buffer_m",
        type=float,
        default=20.0,
        help=(
            "Buffer around each Route Axis segment used only to count "
            "intersecting contour features. This is not a true density."
        ),
    )

    parser.add_argument(
        "--elevation-field",
        default="zv2",
        help="Validated contour elevation field. Default: zv2",
    )

    parser.add_argument(
        "--analysis-crs",
        default="auto_utm",
        help=(
            "Metric CRS for Route Axis distance. "
            "Default auto_utm preserves the current IB0D metric convention."
        ),
    )

    return parser.parse_args()


def split_line_with_axis(line, step):
    """
    Split a LineString by true curvilinear along-line distance.

    The final remainder is preserved.
    """
    total = float(line.length)

    pts = list(np.arange(0.0, total, step))

    if len(pts) == 0 or pts[0] != 0.0:
        pts.insert(0, 0.0)

    if pts[-1] < total:
        pts.append(total)

    segments = []

    for i in range(len(pts) - 1):
        p0 = float(pts[i])
        p1 = float(pts[i + 1])

        if p1 <= p0:
            continue

        geom = substring(line, p0, p1)

        if geom is None or geom.is_empty:
            continue

        segments.append(
            {
                "geometry": geom,
                "seg_id": i,
                "dist_start": p0,
                "dist_end": p1,
                "dist_mid": (p0 + p1) / 2.0,
                "seg_len_axis_m": p1 - p0,
                "seg_len_geom_m": float(geom.length),
            }
        )

    return segments


def main():
    args = parse_args()

    case_id = args.case_id
    case_name = args.case_name or case_id

    route_fp = resolve_path(args.route_line_fp)
    contour_fp = resolve_path(args.contour_fp)

    if args.out_dir is None:
        out_dir = (
            PROJECT_ROOT
            / "outputs"
            / "ib1g_route_axis_terrain_evidence"
            / case_id
        )
    else:
        out_dir = resolve_path(args.out_dir)

    out_dir.mkdir(parents=True, exist_ok=True)

    out_csv = out_dir / f"{case_id}_terrain_evidence.csv"
    out_geojson = out_dir / f"{case_id}_terrain_evidence.geojson"

    segment_len = float(args.segment_len_m)
    window_radius = float(args.window_radius_m)
    contour_count_buffer = float(args.contour_count_buffer_m)
    elevation_field = args.elevation_field

    if segment_len <= 0:
        raise ValueError("--segment-len-m must be > 0")

    if window_radius <= 0:
        raise ValueError("--window-radius-m must be > 0")

    if contour_count_buffer < 0:
        raise ValueError("--contour-count-buffer-m must be >= 0")

    if not route_fp.exists():
        raise FileNotFoundError(f"Route Axis not found: {route_fp}")

    if not contour_fp.exists():
        raise FileNotFoundError(f"Contour source not found: {contour_fp}")

    route = gpd.read_file(route_fp)
    contours = gpd.read_file(contour_fp)

    if route.crs is None:
        raise ValueError("Route Axis CRS is missing; refusing to assume EPSG:4326")

    if contours.crs is None:
        raise ValueError("Contour CRS is missing; refusing metric analysis")

    if len(route) != 1:
        raise ValueError(
            "v2.0 requires exactly one authoritative ordered Route Axis feature; "
            f"got {len(route)}"
        )

    route_geom = route.geometry.iloc[0]

    if route_geom is None or route_geom.is_empty:
        raise ValueError("Route Axis geometry is empty")

    if route_geom.geom_type != "LineString":
        raise ValueError(
            "v2.0 requires one ordered LineString Route Axis; "
            f"got {route_geom.geom_type}"
        )

    if elevation_field not in contours.columns:
        raise ValueError(
            f"Required elevation field '{elevation_field}' not found. "
            f"Available fields: {list(contours.columns)}"
        )

    route_source_crs = str(route.crs)
    contour_source_crs = str(contours.crs)

    if args.analysis_crs == "auto_utm":
        metric_crs = route.estimate_utm_crs()

        if metric_crs is None:
            raise ValueError("Could not determine metric UTM CRS from Route Axis")
    else:
        metric_crs = args.analysis_crs

    route_m = route.to_crs(metric_crs)
    contours_m = contours.to_crs(metric_crs)

    analysis_crs = str(route_m.crs)

    # Preserve raw source field and create a validated numeric working copy.
    contours_m = contours_m.copy()
    contours_m["_elev_numeric"] = pd.to_numeric(
        contours_m[elevation_field],
        errors="coerce",
    )

    route_line = route_m.geometry.iloc[0]
    route_axis_length_m = float(route_line.length)

    segment_records = split_line_with_axis(
        route_line,
        segment_len,
    )

    if not segment_records:
        raise ValueError("No Route Axis segments were generated")

    seg_gdf = gpd.GeoDataFrame(
        segment_records,
        geometry="geometry",
        crs=route_m.crs,
    )

    # -----------------------------------------------------------------
    # Route Axis hard QA
    # -----------------------------------------------------------------

    segment_axis_sum_m = float(seg_gdf["seg_len_axis_m"].sum())
    segment_geom_sum_m = float(seg_gdf["seg_len_geom_m"].sum())
    final_dist_end_m = float(seg_gdf["dist_end"].iloc[-1])

    axis_sum_delta_m = segment_axis_sum_m - route_axis_length_m
    geom_sum_delta_m = segment_geom_sum_m - route_axis_length_m
    tail_delta_m = final_dist_end_m - route_axis_length_m

    tolerance_m = 1e-6

    if abs(axis_sum_delta_m) > tolerance_m:
        raise ValueError(
            "Route Axis conservation failed: "
            f"segment axis sum delta={axis_sum_delta_m}"
        )

    if abs(geom_sum_delta_m) > tolerance_m:
        raise ValueError(
            "Route geometry conservation failed: "
            f"segment geometry sum delta={geom_sum_delta_m}"
        )

    if abs(tail_delta_m) > tolerance_m:
        raise ValueError(
            "Route tail alignment failed: "
            f"final dist_end delta={tail_delta_m}"
        )

    if not seg_gdf["dist_start"].is_monotonic_increasing:
        raise ValueError("Route Axis dist_start is not monotonic")

    contours_sindex = contours_m.sindex

    local_min = []
    local_max = []
    local_relief = []
    relief_ratio = []

    contour_window_count = []
    contour_near_count = []

    contour_elevation_level_count = []
    relief_evidence_status = []

    evidence_present = []
    evidence_status = []

    for _, row in seg_gdf.iterrows():
        geom = row.geometry

        # True on-axis midpoint, unlike geometric centroid.
        mid = geom.interpolate(0.5, normalized=True)

        terrain_window = mid.buffer(window_radius)

        candidate_idx = list(
            contours_sindex.intersection(terrain_window.bounds)
        )

        subset = contours_m.iloc[candidate_idx]
        subset = subset[subset.intersects(terrain_window)]

        window_count = int(len(subset))
        contour_window_count.append(window_count)

        if window_count == 0:
            local_min.append(np.nan)
            local_max.append(np.nan)
            local_relief.append(np.nan)
            relief_ratio.append(np.nan)

            contour_elevation_level_count.append(0)
            relief_evidence_status.append("NO_CONTOUR_EVIDENCE")

            evidence_present.append(False)
            evidence_status.append("EMPTY")

        else:
            vals = subset["_elev_numeric"].dropna()

            if len(vals) == 0:
                local_min.append(np.nan)
                local_max.append(np.nan)
                local_relief.append(np.nan)
                relief_ratio.append(np.nan)

                contour_elevation_level_count.append(0)
                relief_evidence_status.append("UNKNOWN_ATTRIBUTE")

                evidence_present.append(False)
                evidence_status.append("UNKNOWN_ATTRIBUTE")

            else:
                z_levels = sorted(
                    vals.astype(float).unique().tolist()
                )

                level_count = len(z_levels)
                z_min = float(min(z_levels))
                z_max = float(max(z_levels))

                local_min.append(z_min)
                local_max.append(z_max)

                contour_elevation_level_count.append(level_count)

                evidence_present.append(True)

                if len(vals) < window_count:
                    evidence_status.append("PARTIAL")
                else:
                    evidence_status.append("AVAILABLE")

                if level_count < 2:
                    # One contour elevation level cannot establish
                    # local vertical relief.
                    local_relief.append(np.nan)
                    relief_ratio.append(np.nan)
                    relief_evidence_status.append("SINGLE_LEVEL_ONLY")

                else:
                    relief = z_max - z_min
                    ratio = relief / (window_radius * 2.0)

                    local_relief.append(relief)
                    relief_ratio.append(ratio)
                    relief_evidence_status.append("RELIEF_OBSERVABLE")

        near_buffer = geom.buffer(contour_count_buffer)

        candidate_idx_2 = list(
            contours_sindex.intersection(near_buffer.bounds)
        )

        subset_2 = contours_m.iloc[candidate_idx_2]
        subset_2 = subset_2[subset_2.intersects(near_buffer)]

        contour_near_count.append(int(len(subset_2)))

    seg_gdf["local_contour_min_m"] = local_min
    seg_gdf["local_contour_max_m"] = local_max
    seg_gdf["local_relief_m"] = local_relief
    seg_gdf["contour_elevation_level_count"] = (
        contour_elevation_level_count
    )
    seg_gdf["relief_evidence_status"] = relief_evidence_status

    # Terrain context proxy only.
    # This is NOT Route Axis grade and NOT a risk score.
    seg_gdf["terrain_relief_ratio"] = relief_ratio

    seg_gdf["contour_feature_count_window"] = contour_window_count
    seg_gdf["contour_feature_count_near"] = contour_near_count

    seg_gdf["contour_evidence_present"] = evidence_present
    seg_gdf["map_evidence_status"] = evidence_status

    # -----------------------------------------------------------------
    # Provenance
    # -----------------------------------------------------------------

    now = datetime.now(timezone.utc).isoformat()

    seg_gdf["pipeline_stage"] = PIPELINE_STAGE
    seg_gdf["case_id"] = case_id
    seg_gdf["case_name"] = case_name
    seg_gdf["derived_at"] = now

    seg_gdf["segment_len_m"] = segment_len
    seg_gdf["window_radius_m"] = window_radius
    seg_gdf["contour_count_buffer_m"] = contour_count_buffer

    seg_gdf["route_axis_source"] = str(route_fp)
    seg_gdf["contour_source"] = str(contour_fp)
    seg_gdf["nlsc_tile"] = args.tile

    seg_gdf["route_source_crs"] = route_source_crs
    seg_gdf["contour_source_crs"] = contour_source_crs
    seg_gdf["analysis_crs"] = analysis_crs

    seg_gdf["elevation_field"] = elevation_field

    seg_gdf["route_axis_length_m"] = route_axis_length_m
    seg_gdf["distance_axis_method"] = (
        "projected_route_axis_shapely_substring_v2_0"
    )
    seg_gdf["window_center_method"] = (
        "route_segment_midpoint_interpolate"
    )

    seg_gdf["terrain_evidence_scope"] = (
        "direction_neutral_not_route_grade_not_risk"
    )

    # -----------------------------------------------------------------
    # Output
    # -----------------------------------------------------------------

    out = seg_gdf.to_crs("EPSG:4326")

    out.to_file(
        out_geojson,
        driver="GeoJSON",
    )

    out.drop(columns="geometry").to_csv(
        out_csv,
        index=False,
        encoding="utf-8-sig",
    )

    print("=" * 72)
    print("IB1G ROUTE AXIS TERRAIN EVIDENCE v2.0")
    print("=" * 72)

    print("case_id:", case_id)
    print("route:", route_fp)
    print("contour:", contour_fp)
    print("tile:", args.tile)

    print()
    print("route_source_crs:", route_source_crs)
    print("contour_source_crs:", contour_source_crs)
    print("analysis_crs:", analysis_crs)
    print("elevation_field:", elevation_field)

    print()
    print("route_axis_length_m:", route_axis_length_m)
    print("segments:", len(seg_gdf))
    print("segment_axis_sum_m:", segment_axis_sum_m)
    print("segment_geom_sum_m:", segment_geom_sum_m)
    print("final_dist_end_m:", final_dist_end_m)

    print()
    print("axis_sum_delta_m:", axis_sum_delta_m)
    print("geom_sum_delta_m:", geom_sum_delta_m)
    print("tail_delta_m:", tail_delta_m)

    print()
    print("=== MAP EVIDENCE STATUS ===")
    print(
        seg_gdf["map_evidence_status"]
        .value_counts(dropna=False)
        .to_string()
    )

    print()
    print("=== RELIEF EVIDENCE STATUS ===")
    print(
        seg_gdf["relief_evidence_status"]
        .value_counts(dropna=False)
        .to_string()
    )

    print()
    print("=== LOCAL RELIEF M ===")
    print(
        seg_gdf["local_relief_m"]
        .describe()
        .to_string()
    )

    print()
    print("=== TERRAIN RELIEF RATIO ===")
    print(
        seg_gdf["terrain_relief_ratio"]
        .describe()
        .to_string()
    )

    print()
    print("CSV:", out_csv)
    print("GEOJSON:", out_geojson)
    print("N6_GENERATION: PASS")


if __name__ == "__main__":
    main()
