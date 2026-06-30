# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import math
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.ops import nearest_points, substring


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compute a broad upslope contributing-area hazard proxy. This stage "
            "looks beyond a local buffer and searches higher contour sources that "
            "could plausibly descend toward the route."
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
    parser.add_argument("--max-source-distance-m", type=float, default=1000.0)
    parser.add_argument("--min-source-relief-m", type=float, default=30.0)
    parser.add_argument("--min-fall-gradient", type=float, default=0.15)
    parser.add_argument("--sector-deg", type=float, default=45.0)
    parser.add_argument("--sample-every-n", type=int, default=1)
    return parser.parse_args()


def resolve_path(value: str | Path | None) -> Path | None:
    if value is None or str(value).strip() == "":
        return None
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def guess_elev_col(gdf: gpd.GeoDataFrame) -> str:
    lower_to_col = {c.lower(): c for c in gdf.columns}
    for key in ["zv2", "elev", "elevation", "height", "altitude"]:
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
    distances = subset.distance(point)
    distances = distances[distances <= search_m]
    if distances.empty:
        return float("nan")
    return float(distances.min())


def bearing_deg(dx: float, dy: float) -> float:
    # 0=N, 90=E, 180=S, 270=W
    return (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0


def sector_id(bearing: float, sector_deg: float) -> int:
    return int(math.floor(bearing / sector_deg))


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

    route_fp = resolve_path(args.route_line_fp)
    profile_fp = resolve_path(args.profile_csv)
    contour_fp = resolve_path(args.contour_fp)
    collapse_fp = resolve_path(args.collapse_mask_fp)
    watercourse_fp = resolve_path(args.watercourse_fp)
    out_dir = (
        resolve_path(args.out_dir)
        if args.out_dir
        else PROJECT_ROOT / "outputs" / "ib1g3_upslope_contributing_area_hazard_proxy" / case_id
    )
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
    profile["dist_m_num"] = pd.to_numeric(profile["dist_m"], errors="coerce")
    if "ele_smooth" in profile.columns:
        profile["route_ele_m"] = pd.to_numeric(profile["ele_smooth"], errors="coerce")
    elif "ele_gpx_m" in profile.columns:
        profile["route_ele_m"] = pd.to_numeric(profile["ele_gpx_m"], errors="coerce")
    else:
        raise ValueError("profile CSV missing ele_smooth/ele_gpx_m")
    profile = profile.dropna(subset=["dist_m_num", "route_ele_m"]).copy()

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

    segments = route_segments(route_m, args.segment_len_m)
    if args.sample_every_n > 1:
        segments = segments[segments["seg_id"] % args.sample_every_n == 0].copy()

    rows: list[dict[str, object]] = []
    source_rows: list[dict[str, object]] = []
    search_m = args.max_source_distance_m

    for _, seg in segments.iterrows():
        mid_pt = seg.geometry.interpolate(0.5, normalized=True)
        route_ele = nearest_profile_elevation(profile, float(seg["dist_mid"]))
        idxs = list(contour_sindex.intersection(mid_pt.buffer(search_m).bounds))
        subset = contours.iloc[idxs].copy()
        if not subset.empty:
            subset = subset[subset.intersects(mid_pt.buffer(search_m))]
            subset = subset[subset[z_col] > route_ele + args.min_source_relief_m]

        candidate_sources = []
        sector_best: dict[int, dict[str, float]] = {}
        for src_idx, src in subset.iterrows():
            p_route, p_src = nearest_points(mid_pt, src.geometry)
            distance = float(p_route.distance(p_src))
            if distance <= 0 or distance > search_m:
                continue
            relief = float(src[z_col] - route_ele)
            fall_gradient = relief / distance
            if fall_gradient < args.min_fall_gradient:
                continue
            dx = float(p_src.x - mid_pt.x)
            dy = float(p_src.y - mid_pt.y)
            bearing = bearing_deg(dx, dy)
            sid = sector_id(bearing, args.sector_deg)
            source_score = float(
                np.clip(0.55 * (relief / 250.0) + 0.45 * (fall_gradient / 0.8), 0.0, 1.0)
            )
            source = {
                "source_index": int(src_idx),
                "source_ele_m": float(src[z_col]),
                "source_dist_m": distance,
                "source_relief_m": relief,
                "source_fall_gradient": fall_gradient,
                "source_bearing_deg": bearing,
                "source_sector_id": sid,
                "source_score": source_score,
            }
            candidate_sources.append(source)
            current = sector_best.get(sid)
            if current is None or source_score > current["source_score"]:
                sector_best[sid] = source

        if candidate_sources:
            best = max(candidate_sources, key=lambda s: s["source_score"])
            max_relief = max(s["source_relief_m"] for s in candidate_sources)
            max_gradient = max(s["source_fall_gradient"] for s in candidate_sources)
            min_source_dist = min(s["source_dist_m"] for s in candidate_sources)
        else:
            best = {}
            max_relief = 0.0
            max_gradient = 0.0
            min_source_dist = float("nan")

        active_sector_count = len(sector_best)
        directional_concentration_score = float(np.clip(active_sector_count / max(1, 360.0 / args.sector_deg), 0.0, 1.0))
        source_presence_score = float(np.clip(len(candidate_sources) / 20.0, 0.0, 1.0))
        best_source_score = float(best.get("source_score", 0.0))

        collapse_dist = min_distance_to_layer(collapse, mid_pt, min(search_m, 500.0))
        water_dist = min_distance_to_layer(watercourse, mid_pt, min(search_m, 300.0))
        collapse_score = 0.0 if pd.isna(collapse_dist) else float(np.clip(1.0 - collapse_dist / min(search_m, 500.0), 0.0, 1.0))
        channel_score = 0.0 if pd.isna(water_dist) else float(np.clip(1.0 - water_dist / min(search_m, 300.0), 0.0, 1.0))

        contributing_score = float(
            np.clip(
                0.50 * best_source_score
                + 0.20 * source_presence_score
                + 0.10 * directional_concentration_score
                + 0.12 * collapse_score
                + 0.08 * channel_score,
                0.0,
                1.0,
            )
        )

        row = {
            "seg_id": int(seg["seg_id"]),
            "dist_start": float(seg["dist_start"]),
            "dist_end": float(seg["dist_end"]),
            "dist_mid": float(seg["dist_mid"]),
            "seg_len_m": float(seg["seg_len_m"]),
            "route_ele_m": route_ele,
            "contributing_source_count": len(candidate_sources),
            "contributing_sector_count": active_sector_count,
            "max_source_relief_m": max_relief,
            "max_source_fall_gradient": max_gradient,
            "nearest_source_dist_m": min_source_dist,
            "best_source_ele_m": best.get("source_ele_m", np.nan),
            "best_source_dist_m": best.get("source_dist_m", np.nan),
            "best_source_relief_m": best.get("source_relief_m", np.nan),
            "best_source_fall_gradient": best.get("source_fall_gradient", np.nan),
            "best_source_bearing_deg": best.get("source_bearing_deg", np.nan),
            "best_source_score": best_source_score,
            "source_presence_score": source_presence_score,
            "directional_concentration_score": directional_concentration_score,
            "collapse_mask_dist_m": collapse_dist,
            "collapse_mask_score": collapse_score,
            "watercourse_dist_m": water_dist,
            "watercourse_channel_score": channel_score,
            "upslope_contributing_hazard_score": contributing_score,
            "upslope_contributing_hazard_band": risk_band(contributing_score),
            "geometry": seg.geometry,
        }
        rows.append(row)

        for source in sorted(candidate_sources, key=lambda s: s["source_score"], reverse=True)[:5]:
            source_rows.append(
                {
                    "seg_id": int(seg["seg_id"]),
                    "dist_mid": float(seg["dist_mid"]),
                    **source,
                }
            )

    out = gpd.GeoDataFrame(rows, geometry="geometry", crs=metric_crs)
    out["case_id"] = case_id
    out["case_name"] = case_name
    out["pipeline_stage"] = "ib1g3_upslope_contributing_area_hazard_proxy"
    out["derived_at"] = datetime.now(timezone.utc).isoformat()
    out["route_line_fp"] = str(route_fp)
    out["profile_csv"] = str(profile_fp)
    out["contour_fp"] = str(contour_fp)
    out["collapse_mask_fp"] = str(collapse_fp or "")
    out["watercourse_fp"] = str(watercourse_fp or "")
    out["nlsc_tile"] = args.tile
    out["max_source_distance_m"] = args.max_source_distance_m
    out["min_source_relief_m"] = args.min_source_relief_m
    out["min_fall_gradient"] = args.min_fall_gradient
    out["model_note"] = (
        "Proxy only: broad higher-terrain source search using contours. "
        "It approximates possible upslope contributing sources but does not model true rockfall physics, slope aspect from DEM, or debris-flow runout."
    )

    out_wgs84 = out.to_crs("EPSG:4326")
    out_csv = out_dir / f"{case_id}_upslope_contributing_area_hazard_proxy.csv"
    out_geojson = out_dir / f"{case_id}_upslope_contributing_area_hazard_proxy.geojson"
    out_sources_csv = out_dir / f"{case_id}_upslope_contributing_area_top_sources.csv"
    out_summary = out_dir / f"{case_id}_upslope_contributing_area_hazard_proxy_summary.csv"

    out_wgs84.to_file(out_geojson, driver="GeoJSON")
    out_wgs84.drop(columns="geometry").to_csv(out_csv, index=False, encoding="utf-8-sig")
    pd.DataFrame(source_rows).to_csv(out_sources_csv, index=False, encoding="utf-8-sig")

    summary_rows = [
        {"metric": "segments", "value": len(out_wgs84)},
        {"metric": "route_len_m", "value": float(out_wgs84["dist_end"].max())},
        {"metric": "max_source_distance_m", "value": args.max_source_distance_m},
        {"metric": "score_min", "value": float(out_wgs84["upslope_contributing_hazard_score"].min())},
        {"metric": "score_mean", "value": float(out_wgs84["upslope_contributing_hazard_score"].mean())},
        {"metric": "score_max", "value": float(out_wgs84["upslope_contributing_hazard_score"].max())},
        {"metric": "max_source_relief_m", "value": float(out_wgs84["max_source_relief_m"].max())},
        {"metric": "max_source_fall_gradient", "value": float(out_wgs84["max_source_fall_gradient"].max())},
    ]
    for band, count in out_wgs84["upslope_contributing_hazard_band"].value_counts().items():
        summary_rows.append({"metric": f"band_{band}", "value": int(count)})
    pd.DataFrame(summary_rows).to_csv(out_summary, index=False, encoding="utf-8-sig")

    print("case:", case_id)
    print("segments:", len(out_wgs84))
    print("CSV:", out_csv.resolve())
    print("GeoJSON:", out_geojson.resolve())
    print("top sources CSV:", out_sources_csv.resolve())
    print("summary CSV:", out_summary.resolve())
    print("\n=== upslope_contributing_hazard_band ===")
    print(out_wgs84["upslope_contributing_hazard_band"].value_counts())
    print("\n=== upslope_contributing_hazard_score ===")
    print(out_wgs84["upslope_contributing_hazard_score"].describe())


if __name__ == "__main__":
    main()
