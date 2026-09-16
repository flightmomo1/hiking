#!/usr/bin/env python3
import argparse
from pathlib import Path
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point


NULL_LITERALS = {
    "<na>",
    "nan",
    "none",
    "null",
    "nat",
}


def clean(v):
    if pd.isna(v):
        return ""

    s = str(v).strip()

    if s.lower() in NULL_LITERALS:
        return ""

    return s


def norm_id(v):
    s = clean(v)
    if s.endswith(".0") and s[:-2].replace("-", "", 1).isdigit():
        s = s[:-2]
    return s


def line_parts(g):
    if g is None or g.is_empty:
        return []
    if g.geom_type == "LineString":
        return [g]
    if g.geom_type == "MultiLineString":
        return list(g.geoms)
    if g.geom_type == "GeometryCollection":
        out = []
        for part in g.geoms:
            out.extend(line_parts(part))
        return out
    return []


def feature_length_m(g):
    if g is None or g.is_empty:
        return 0.0
    if g.geom_type in ("LineString", "MultiLineString"):
        return float(g.length)
    if g.geom_type in ("Polygon", "MultiPolygon"):
        return float(g.boundary.length)
    return 0.0


def main():
    ap = argparse.ArgumentParser(description="Audit nearby OSM feature geometry against a Route Axis")
    ap.add_argument("--route-axis", required=True)
    ap.add_argument("--feature-geojson", required=True)
    ap.add_argument("--threshold-m", required=True, type=float)
    ap.add_argument("--out-csv", required=True)
    ap.add_argument(
        "--route-axis-edges",
        default=None,
        help="Optional canonical identity check; membership is unknown when omitted",
    )
    ap.add_argument("--metric-crs", default="EPSG:32651")
    args = ap.parse_args()

    if args.threshold_m < 0:
        raise SystemExit("--threshold-m must be >= 0")

    axis = gpd.read_file(args.route_axis).to_crs(args.metric_crs)
    feat = gpd.read_file(args.feature_geojson).to_crs(args.metric_crs)
    if len(axis) != 1:
        raise SystemExit(f"Expected exactly one Route Axis geometry, got {len(axis)}")
    route = axis.geometry.iloc[0]
    if route is None or route.is_empty or route.geom_type != "LineString":
        raise SystemExit(f"Route Axis must be a non-empty LineString, got {getattr(route, 'geom_type', None)}")

    axis_ids = None

    if args.route_axis_edges:
        ed = pd.read_csv(
            args.route_axis_edges,
            low_memory=False,
        )

        required_identity_columns = {
            "osm_type",
            "osm_id",
        }

        missing_identity_columns = (
            required_identity_columns
            - set(ed.columns)
        )

        if missing_identity_columns:
            raise SystemExit(
                "Route Axis edges missing canonical identity columns: "
                + ", ".join(sorted(missing_identity_columns))
            )

        axis_ids = {
            (clean(t), norm_id(i))
            for t, i in zip(
                ed["osm_type"],
                ed["osm_id"],
            )
            if clean(t) and norm_id(i)
        }

    available_tag_columns = [
        c
        for c in [
            "natural",
            "hazard",
            "safety_rope",
            "safety_rope_side",
            "handrail",
            "information",
            "highway",
            "landslide",
        ]
        if c in feat.columns
    ]

    output_columns = [
        "source_row_index",
        "osm_type",
        "osm_id",
        "name",
        "geom_type",
        "feature_length_or_perimeter_m",
        "min_distance_to_axis_m",
        "canonical_identity_on_route_axis",
        "interval_id",
        "route_start_m",
        "route_end_m",
        "route_span_m",
        *available_tag_columns,
    ]

    rows = []
    for idx, r in feat.iterrows():
        geom = r.geometry
        if geom is None or geom.is_empty:
            continue
        min_dist = float(route.distance(geom))
        if min_dist > args.threshold_m:
            continue

        osm_type = clean(r.get("osm_type", ""))
        osm_id = norm_id(r.get("osm_id", ""))
        canonical = (
            ""
            if axis_ids is None
            else (osm_type, osm_id) in axis_ids
        )
        buffered = geom.buffer(args.threshold_m)
        hit = route.intersection(buffered)
        parts = line_parts(hit)
        if not parts:
            parts = [None]

        for interval_id, part in enumerate(parts, start=1):
            start = end = None
            span = 0.0
            if part is not None:
                coords = list(part.coords)
                d0 = float(route.project(Point(coords[0])))
                d1 = float(route.project(Point(coords[-1])))
                start, end = min(d0, d1), max(d0, d1)
                span = float(part.length)

            row = {
                "source_row_index": idx,
                "osm_type": osm_type,
                "osm_id": osm_id,
                "name": clean(r.get("name", "")),
                "geom_type": geom.geom_type,
                "feature_length_or_perimeter_m": feature_length_m(geom),
                "min_distance_to_axis_m": min_dist,
                "canonical_identity_on_route_axis": canonical,
                "interval_id": interval_id,
                "route_start_m": start,
                "route_end_m": end,
                "route_span_m": span,
            }
            for c in available_tag_columns:
                row[c] = clean(r.get(c, ""))
            rows.append(row)

    out = pd.DataFrame(
        rows,
        columns=output_columns,
    )
    if not out.empty:
        out = out.sort_values(["route_start_m", "route_end_m", "osm_id"], na_position="last")
    out_fp = Path(args.out_csv)
    out_fp.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_fp, index=False, encoding="utf-8-sig")

    print("NEARBY FEATURE INTERVAL AUDIT")
    print("threshold_m:", args.threshold_m)
    print("route_length_m:", round(float(route.length), 3))
    print("source_feature_n:", len(feat))
    print("nearby_feature_n:", 0 if out.empty else out[["source_row_index"]].drop_duplicates().shape[0])
    print("unique_osm_identity_n:", 0 if out.empty else out[["osm_type", "osm_id"]].drop_duplicates().shape[0])
    print("interval_n:", len(out))
    print(
        "canonical_identity_check_performed:",
        axis_ids is not None,
    )

    if axis_ids is not None:
        canonical_match_n = (
            0
            if out.empty
            else int(
                out.loc[
                    out["canonical_identity_on_route_axis"],
                    ["osm_type", "osm_id"],
                ]
                .drop_duplicates()
                .shape[0]
            )
        )

        print(
            "canonical_identity_match_n:",
            canonical_match_n,
        )
    else:
        print(
            "canonical_identity_match_n:",
            "UNKNOWN",
        )
    print("CSV:", out_fp)
    if not out.empty:
        cols = [c for c in ["osm_type", "osm_id", "name", "geom_type", "feature_length_or_perimeter_m", "min_distance_to_axis_m", "canonical_identity_on_route_axis", "route_start_m", "route_end_m", "route_span_m"] if c in out.columns]
        print(out[cols].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
