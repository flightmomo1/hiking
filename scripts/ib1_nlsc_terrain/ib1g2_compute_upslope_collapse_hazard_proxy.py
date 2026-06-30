# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString
from shapely.ops import substring


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compute an upslope collapse / rockfall-debris hazard proxy from "
            "NLSC contours, collapse masks, and watercourses."
        )
    )
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--case-name", default=None)
    parser.add_argument("--route-line-fp", required=True)
    parser.add_argument("--profile-csv", required=True)
    parser.add_argument("--contour-fp", required=True)
    parser.add_argument("--collapse-mask-fp", default=None)
    parser.add_argument("--watercourse-fp", default=None)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--tile", default="")
    parser.add_argument("--segment-len-m", type=float, default=20.0)
    parser.add_argument("--radii-m", default="50,100,200,300")
    parser.add_argument("--collapse-search-m", type=float, default=300.0)
    parser.add_argument("--watercourse-search-m", type=float, default=100.0)
    return parser.parse_args()


def resolve_path(value: str | Path | None) -> Path | None:
    if value is None or str(value).strip() == "":
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def parse_radii(value: str) -> list[float]:
    radii = [float(v.strip()) for v in str(value).split(",") if v.strip()]
    if not radii:
        raise ValueError("--radii-m must contain at least one radius")
    return sorted(set(radii))


def guess_elev_col(gdf: gpd.GeoDataFrame) -> str:
    preferred = ["zv2", "elev", "elevation", "height", "altitude"]
    lower_to_col = {c.lower(): c for c in gdf.columns}
    for key in preferred:
        if key in lower_to_col:
            return lower_to_col[key]
    for col in gdf.columns:
        text = col.lower()
        if "elev" in text or text.startswith("z"):
            return col
    raise ValueError("No elevation-like column found in contour layer")


def split_line_with_axis(line, step: float) -> list[dict[str, object]]:
    total = float(line.length)
    stops = list(np.arange(0, total, step))
    if not stops or stops[0] != 0:
        stops.insert(0, 0.0)
    if stops[-1] < total:
        stops.append(total)

    rows: list[dict[str, object]] = []
    for i in range(len(stops) - 1):
        start = float(stops[i])
        end = float(stops[i + 1])
        if end <= start:
            continue
        geom = substring(line, start, end)
        if geom is None or geom.is_empty:
            continue
        rows.append(
            {
                "geometry": geom,
                "dist_start": start,
                "dist_end": end,
                "dist_mid": (start + end) / 2.0,
                "seg_len_m": end - start,
            }
        )
    return rows


def route_segments(route_gdf: gpd.GeoDataFrame, segment_len_m: float) -> gpd.GeoDataFrame:
    rows: list[dict[str, object]] = []
    offset = 0.0
    seg_id = 0
    for geom in route_gdf.geometry:
        if geom is None or geom.is_empty:
            continue
        parts = list(geom.geoms) if geom.geom_type == "MultiLineString" else [geom]
        for part in parts:
            for item in split_line_with_axis(part, segment_len_m):
                row = dict(item)
                row["seg_id"] = seg_id
                row["dist_start"] = float(row["dist_start"]) + offset
                row["dist_end"] = float(row["dist_end"]) + offset
                row["dist_mid"] = float(row["dist_mid"]) + offset
                rows.append(row)
                seg_id += 1
            offset += float(part.length)
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=route_gdf.crs)


def nearest_profile_elevation(profile: pd.DataFrame, dist_m: float) -> float:
    idx = (profile["dist_m_num"] - dist_m).abs().idxmin()
    return float(profile.loc[idx, "route_ele_m"])


def load_optional_layer(path: Path | None, metric_crs) -> gpd.GeoDataFrame | None:
    if path is None or not path.exists():
        return None
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    return gdf.to_crs(metric_crs)


def min_distance_to_layer(layer: gpd.GeoDataFrame | None, point, search_m: float) -> float:
    if layer is None or layer.empty:
        return float("nan")
    idxs = list(layer.sindex.intersection(point.buffer(search_m).bounds))
    if not idxs:
        return float("nan")
    subset = layer.iloc[idxs]
    if subset.empty:
        return float("nan")
    distances = subset.distance(point)
    distances = distances[distances <= search_m]
    if distances.empty:
        return float("nan")
    return float(distances.min())


def score_relief(relief_50: float, relief_100: float, relief_200: float, relief_300: float) -> float:
    vals = [
        np.clip((relief_50 or 0.0) / 40.0, 0.0, 1.0),
        np.clip((relief_100 or 0.0) / 70.0, 0.0, 1.0),
        np.clip((relief_200 or 0.0) / 120.0, 0.0, 1.0),
        np.clip((relief_300 or 0.0) / 180.0, 0.0, 1.0),
    ]
    return float(np.nanmax(vals))


def risk_band(score: float) -> str:
    if score < 0.25:
        return "low"
    if score < 0.45:
        return "moderate"
    if score < 0.70:
        return "high"
    return "very_high"


def main() -> None:
    args = parse_args()
    case_id = args.case_id
    case_name = args.case_name or case_id
    radii = parse_radii(args.radii_m)

    route_fp = resolve_path(args.route_line_fp)
    profile_fp = resolve_path(args.profile_csv)
    contour_fp = resolve_path(args.contour_fp)
    collapse_fp = resolve_path(args.collapse_mask_fp)
    watercourse_fp = resolve_path(args.watercourse_fp)

    if args.out_dir:
        out_dir = resolve_path(args.out_dir)
    else:
        out_dir = PROJECT_ROOT / "outputs" / "ib1g2_upslope_collapse_hazard_proxy" / case_id
    assert out_dir is not None
    out_dir.mkdir(parents=True, exist_ok=True)

    for label, fp in [("route line", route_fp), ("profile csv", profile_fp), ("contour", contour_fp)]:
        if fp is None or not fp.exists():
            raise FileNotFoundError(f"Missing {label}: {fp}")

    route = gpd.read_file(route_fp)
    if route.crs is None:
        route = route.set_crs("EPSG:4326")
    metric_crs = route.estimate_utm_crs() or "EPSG:32651"
    route_m = route.to_crs(metric_crs)

    profile = pd.read_csv(profile_fp, low_memory=False)
    if "dist_m" not in profile.columns:
        raise ValueError("profile CSV missing dist_m")
    profile["dist_m_num"] = pd.to_numeric(profile["dist_m"], errors="coerce")
    if "ele_smooth" in profile.columns:
        profile["route_ele_m"] = pd.to_numeric(profile["ele_smooth"], errors="coerce")
    elif "ele_gpx_m" in profile.columns:
        profile["route_ele_m"] = pd.to_numeric(profile["ele_gpx_m"], errors="coerce")
    else:
        raise ValueError("profile CSV missing ele_smooth/ele_gpx_m")
    profile = profile.dropna(subset=["dist_m_num", "route_ele_m"]).copy()
    if profile.empty:
        raise ValueError("profile CSV has no usable route elevations")

    contours = gpd.read_file(contour_fp)
    if contours.crs is None:
        contours = contours.set_crs("EPSG:4326")
    contours = contours.to_crs(metric_crs)
    z_col = guess_elev_col(contours)
    contours[z_col] = pd.to_numeric(contours[z_col], errors="coerce")
    contours = contours.dropna(subset=[z_col]).copy()
    contour_sindex = contours.sindex

    collapse = load_optional_layer(collapse_fp, metric_crs)
    watercourse = load_optional_layer(watercourse_fp, metric_crs)

    seg = route_segments(route_m, args.segment_len_m)
    max_radius = max(radii)
    rows: list[dict[str, object]] = []

    for _, item in seg.iterrows():
        mid_pt = item.geometry.interpolate(0.5, normalized=True)
        route_ele = nearest_profile_elevation(profile, float(item["dist_mid"]))
        row: dict[str, object] = {
            "seg_id": int(item["seg_id"]),
            "dist_start": float(item["dist_start"]),
            "dist_end": float(item["dist_end"]),
            "dist_mid": float(item["dist_mid"]),
            "seg_len_m": float(item["seg_len_m"]),
            "route_ele_m": route_ele,
            "geometry": item.geometry,
        }

        relief_by_radius: dict[float, float] = {}
        upper_count_by_radius: dict[float, int] = {}
        for radius in radii:
            window = mid_pt.buffer(radius)
            idxs = list(contour_sindex.intersection(window.bounds))
            subset = contours.iloc[idxs]
            subset = subset[subset.intersects(window)]
            upper = subset[subset[z_col] > route_ele]
            if upper.empty:
                relief = 0.0
                upper_count = 0
            else:
                relief = float(upper[z_col].max() - route_ele)
                upper_count = int(len(upper))
            relief_by_radius[radius] = relief
            upper_count_by_radius[radius] = upper_count
            row[f"upslope_relief_{int(radius)}m"] = relief
            row[f"upslope_contour_count_{int(radius)}m"] = upper_count

        # Canonical columns expected by downstream review.
        relief_50 = relief_by_radius.get(50.0, relief_by_radius.get(radii[0], 0.0))
        relief_100 = relief_by_radius.get(100.0, relief_50)
        relief_200 = relief_by_radius.get(200.0, relief_100)
        relief_300 = relief_by_radius.get(300.0, relief_200)
        row["upslope_relief_max_m"] = max(relief_by_radius.values()) if relief_by_radius else 0.0
        row["upslope_contour_count_max"] = max(upper_count_by_radius.values()) if upper_count_by_radius else 0
        row["upslope_relief_score"] = score_relief(relief_50, relief_100, relief_200, relief_300)
        row["upslope_contour_density_score"] = float(
            np.clip(row["upslope_contour_count_max"] / 12.0, 0.0, 1.0)
        )

        collapse_dist = min_distance_to_layer(collapse, mid_pt, args.collapse_search_m)
        water_dist = min_distance_to_layer(watercourse, mid_pt, args.watercourse_search_m)
        row["collapse_mask_dist_m"] = collapse_dist
        row["collapse_mask_within_search"] = bool(pd.notna(collapse_dist))
        row["watercourse_dist_m"] = water_dist
        row["watercourse_within_search"] = bool(pd.notna(water_dist))

        if pd.isna(collapse_dist):
            collapse_score = 0.0
        else:
            collapse_score = float(np.clip(1.0 - collapse_dist / args.collapse_search_m, 0.0, 1.0))
        if pd.isna(water_dist):
            channel_score = 0.0
        else:
            channel_score = float(np.clip(1.0 - water_dist / args.watercourse_search_m, 0.0, 1.0))
        row["collapse_mask_score"] = collapse_score
        row["watercourse_channel_score"] = channel_score

        row["rockfall_debris_hazard_proxy_score"] = float(
            np.clip(
                0.45 * row["upslope_relief_score"]
                + 0.25 * row["upslope_contour_density_score"]
                + 0.20 * collapse_score
                + 0.10 * channel_score,
                0.0,
                1.0,
            )
        )
        row["rockfall_debris_hazard_proxy_band"] = risk_band(
            row["rockfall_debris_hazard_proxy_score"]
        )

        rows.append(row)

    out = gpd.GeoDataFrame(rows, geometry="geometry", crs=metric_crs)
    out["case_id"] = case_id
    out["case_name"] = case_name
    out["pipeline_stage"] = "ib1g2_upslope_collapse_hazard_proxy"
    out["derived_at"] = datetime.now(timezone.utc).isoformat()
    out["route_line_fp"] = str(route_fp)
    out["profile_csv"] = str(profile_fp)
    out["contour_fp"] = str(contour_fp)
    out["collapse_mask_fp"] = str(collapse_fp or "")
    out["watercourse_fp"] = str(watercourse_fp or "")
    out["nlsc_tile"] = args.tile
    out["search_radii_m"] = ",".join(str(int(r)) for r in radii)
    out["model_note"] = (
        "Proxy only: nearby higher terrain can threaten the route even without direct intersection. "
        "This is not an official rockfall, dip-slope, or debris-flow susceptibility layer."
    )

    out_wgs84 = out.to_crs("EPSG:4326")
    out_csv = out_dir / f"{case_id}_upslope_collapse_hazard_proxy.csv"
    out_geojson = out_dir / f"{case_id}_upslope_collapse_hazard_proxy.geojson"
    out_summary = out_dir / f"{case_id}_upslope_collapse_hazard_proxy_summary.csv"

    out_wgs84.to_file(out_geojson, driver="GeoJSON")
    out_wgs84.drop(columns="geometry").to_csv(out_csv, index=False, encoding="utf-8-sig")

    summary_rows = [
        {"metric": "segments", "value": len(out_wgs84)},
        {"metric": "route_len_m", "value": float(out_wgs84["dist_end"].max())},
        {"metric": "collapse_mask_present", "value": collapse is not None and not collapse.empty},
        {"metric": "watercourse_present", "value": watercourse is not None and not watercourse.empty},
        {"metric": "score_min", "value": float(out_wgs84["rockfall_debris_hazard_proxy_score"].min())},
        {"metric": "score_mean", "value": float(out_wgs84["rockfall_debris_hazard_proxy_score"].mean())},
        {"metric": "score_max", "value": float(out_wgs84["rockfall_debris_hazard_proxy_score"].max())},
        {"metric": "upslope_relief_max_m", "value": float(out_wgs84["upslope_relief_max_m"].max())},
    ]
    for band, count in out_wgs84["rockfall_debris_hazard_proxy_band"].value_counts().items():
        summary_rows.append({"metric": f"band_{band}", "value": int(count)})
    pd.DataFrame(summary_rows).to_csv(out_summary, index=False, encoding="utf-8-sig")

    print("case:", case_id)
    print("segments:", len(out_wgs84))
    print("CSV:", out_csv.resolve())
    print("GeoJSON:", out_geojson.resolve())
    print("summary CSV:", out_summary.resolve())
    print("\n=== rockfall_debris_hazard_proxy_band ===")
    print(out_wgs84["rockfall_debris_hazard_proxy_band"].value_counts())
    print("\n=== rockfall_debris_hazard_proxy_score ===")
    print(out_wgs84["rockfall_debris_hazard_proxy_score"].describe())


if __name__ == "__main__":
    main()
