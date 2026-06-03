from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point


PROJECT_ROOT = Path(r"C:\mountain_work\115_osm")
DEFAULT_INPUT_ROOT = (
    PROJECT_ROOT / "outputs" / "ib0b_mainline_route_definition_v1_3b_control_points_only"
)
DEFAULT_OUTPUT_ROOT = (
    PROJECT_ROOT
    / "outputs"
    / "ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa"
)
ORDERED_SUFFIX = "_mainline_ordered_path_ib0_candidates.geojson"
CONTROL_CSV_SUFFIX = "_route_definition_control_points_used_ib0_candidates.csv"
CONTROL_GEOJSON_SUFFIX = "_route_definition_control_points_used_ib0_candidates.geojson"


@dataclass
class CaseResult:
    case_id: str
    status: str
    hard_fail_reasons: list[str]
    warnings: list[str]
    out_dir: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "IB0D v1.3b control-points-only contract / QA gate. "
            "Canonical authority is IB0B ordered_path plus "
            "route_definition_control_points_used, never IB0C anchors."
        )
    )
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--input-root", default=str(DEFAULT_INPUT_ROOT))
    parser.add_argument("--out-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--max-control-offset-m", type=float, default=50.0)
    parser.add_argument("--sample-interval-m", type=float, default=1.0)
    parser.add_argument("--self-near-spatial-threshold-m", type=float, default=10.0)
    parser.add_argument("--self-near-route-gap-threshold-m", type=float, default=80.0)
    parser.add_argument(
        "--allow-existing-case-dir",
        action="store_true",
        help="Allow writing into an existing per-case output directory.",
    )
    return parser.parse_args()


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def get_single_linestring(gdf: gpd.GeoDataFrame) -> LineString:
    if gdf.empty:
        raise ValueError("ordered path GeoDataFrame is empty")
    geom = gdf.geometry.iloc[0]
    if geom is None or geom.is_empty:
        raise ValueError("ordered path geometry is empty")
    if geom.geom_type == "LineString":
        return geom
    if geom.geom_type == "MultiLineString":
        coords = []
        for part in geom.geoms:
            part_coords = list(part.coords)
            if not coords:
                coords.extend(part_coords)
            elif coords[-1] == part_coords[0]:
                coords.extend(part_coords[1:])
            else:
                coords.extend(part_coords)
        return LineString(coords)
    raise ValueError(f"unsupported ordered path geometry type: {geom.geom_type}")


def cut_line_between(line: LineString, start_d: float, end_d: float) -> LineString:
    if end_d <= start_d:
        raise ValueError(f"invalid trim range: start={start_d}, end={end_d}")

    coords = list(line.coords)
    new_pts = [(line.interpolate(start_d).x, line.interpolate(start_d).y)]
    acc = 0.0
    for i in range(len(coords) - 1):
        seg = LineString([coords[i], coords[i + 1]])
        seg_len = seg.length
        seg_start = acc
        seg_end = acc + seg_len
        if seg_start > start_d and seg_start < end_d:
            new_pts.append(coords[i])
        if seg_end > start_d and seg_end < end_d:
            new_pts.append(coords[i + 1])
        acc = seg_end
    new_pts.append((line.interpolate(end_d).x, line.interpolate(end_d).y))

    dedup = []
    for pt in new_pts:
        if not dedup or pt != dedup[-1]:
            dedup.append(pt)
    if len(dedup) < 2:
        raise ValueError("trimmed geometry has fewer than two distinct points")
    return LineString(dedup)


def build_route_points_table(
    line_m: LineString,
    metric_crs,
    sample_interval_m: float,
) -> gpd.GeoDataFrame:
    rows = []
    length_m = float(line_m.length)
    d = 0.0
    idx = 0
    while d < length_m:
        pt = line_m.interpolate(d)
        rows.append(
            {
                "route_point_index": idx,
                "route_dist_m": d,
                "x": pt.x,
                "y": pt.y,
                "geometry": pt,
            }
        )
        idx += 1
        d += sample_interval_m
    pt = line_m.interpolate(length_m)
    rows.append(
        {
            "route_point_index": idx,
            "route_dist_m": length_m,
            "x": pt.x,
            "y": pt.y,
            "geometry": pt,
        }
    )
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=metric_crs)


def find_self_near_pairs(
    route_points_m: gpd.GeoDataFrame,
    spatial_threshold_m: float,
    route_gap_threshold_m: float,
    min_index_gap: int = 20,
) -> pd.DataFrame:
    cols = [
        "idx_a",
        "dist_a_m",
        "idx_b",
        "dist_b_m",
        "spatial_distance_m",
        "route_distance_gap_m",
        "classification",
    ]
    if route_points_m.empty:
        return pd.DataFrame(columns=cols)

    pts = route_points_m.reset_index(drop=True).copy()
    sindex = pts.sindex
    rows = []
    for i, row_i in pts.iterrows():
        pi = row_i.geometry
        di = float(row_i.route_dist_m)
        idx_i = int(row_i.route_point_index)
        for j in sindex.intersection(pi.buffer(spatial_threshold_m).bounds):
            if j <= i:
                continue
            row_j = pts.iloc[j]
            idx_j = int(row_j.route_point_index)
            if abs(idx_j - idx_i) < min_index_gap:
                continue
            dj = float(row_j.route_dist_m)
            route_gap = abs(dj - di)
            if route_gap < route_gap_threshold_m:
                continue
            spatial_dist = float(pi.distance(row_j.geometry))
            if spatial_dist <= spatial_threshold_m:
                rows.append(
                    {
                        "idx_a": idx_i,
                        "dist_a_m": di,
                        "idx_b": idx_j,
                        "dist_b_m": dj,
                        "spatial_distance_m": spatial_dist,
                        "route_distance_gap_m": route_gap,
                        "classification": "unclassified",
                    }
                )
    return pd.DataFrame(rows, columns=cols)


def classify_self_near_pairs(
    pairs: pd.DataFrame,
    route_length_m: float,
    same_entry_keep_full: bool,
) -> pd.DataFrame:
    if pairs.empty:
        return pairs
    out = pairs.copy()
    if same_entry_keep_full:
        out["classification"] = "expected_same_entry_exit"
        return out
    same_entry = (
        ((out["dist_a_m"] <= 100.0) & (out["dist_b_m"] >= route_length_m - 100.0))
        | ((out["dist_b_m"] <= 100.0) & (out["dist_a_m"] >= route_length_m - 100.0))
    )
    summit = (
        (
            ((out["dist_a_m"] >= 1800.0) & (out["dist_a_m"] <= 2050.0))
            | ((out["dist_b_m"] >= 1800.0) & (out["dist_b_m"] <= 2050.0))
        )
        & (
            ((out["dist_a_m"] >= 2150.0) & (out["dist_a_m"] <= 2350.0))
            | ((out["dist_b_m"] >= 2150.0) & (out["dist_b_m"] <= 2350.0))
        )
    )
    out.loc[same_entry, "classification"] = "expected_same_entry_exit"
    out.loc[~same_entry & summit, "classification"] = "expected_summit_self_near"
    out.loc[out["classification"].eq("unclassified"), "classification"] = "unexpected_self_near"
    return out


def summarize_self_near_zones(pairs: pd.DataFrame) -> pd.DataFrame:
    if pairs.empty:
        return pd.DataFrame()
    rows = []
    for cls, group in pairs.groupby("classification"):
        rows.append(
            {
                "classification": cls,
                "pair_count": int(len(group)),
                "dist_a_min_m": float(group["dist_a_m"].min()),
                "dist_a_max_m": float(group["dist_a_m"].max()),
                "dist_b_min_m": float(group["dist_b_m"].min()),
                "dist_b_max_m": float(group["dist_b_m"].max()),
                "spatial_distance_min_m": float(group["spatial_distance_m"].min()),
                "route_gap_max_m": float(group["route_distance_gap_m"].max()),
            }
        )
    return pd.DataFrame(rows)


def display_offset_control_points(
    control_m: gpd.GeoDataFrame,
    cluster_threshold_m: float = 20.0,
    display_radius_m: float = 14.0,
) -> gpd.GeoDataFrame:
    display = control_m.copy()
    display["true_geometry"] = display.geometry
    display["display_offset_m"] = 0.0
    display["display_cluster_size"] = 1

    remaining = set(display.index.tolist())
    clusters = []
    while remaining:
        seed = min(remaining)
        seed_geom = display.loc[seed].geometry
        cluster = [
            idx
            for idx in sorted(remaining)
            if seed_geom.distance(display.loc[idx].geometry) <= cluster_threshold_m
        ]
        for idx in cluster:
            remaining.remove(idx)
        clusters.append(cluster)

    for cluster in clusters:
        n = len(cluster)
        if n <= 1:
            continue
        for pos, idx in enumerate(cluster):
            angle = (2.0 * math.pi * pos / n) - (math.pi / 2.0)
            radius = display_radius_m + max(0, n - 3) * 1.5
            true_pt = display.loc[idx].geometry
            display.at[idx, "geometry"] = Point(
                true_pt.x + math.cos(angle) * radius,
                true_pt.y + math.sin(angle) * radius,
            )
            display.at[idx, "display_offset_m"] = radius
            display.at[idx, "display_cluster_size"] = n

    return display


def status_from(failures: list[str], warnings: list[str]) -> str:
    if failures:
        return "FAIL"
    if warnings:
        return "WARN"
    return "PASS"


def discover_cases(input_root: Path, requested_case_ids: list[str]) -> list[str]:
    if requested_case_ids:
        return requested_case_ids
    return sorted(p.name[: -len(ORDERED_SUFFIX)] for p in input_root.glob(f"*{ORDERED_SUFFIX}"))


def control_points_have_fallback(control_df: pd.DataFrame) -> bool:
    for value in control_df.to_numpy().ravel():
        if "fallback_gpx_point" in str(value).lower():
            return True
    return False


def projection_order_violations(control_df: pd.DataFrame) -> list[str]:
    ordered = control_df.sort_values("order").copy()
    projected = pd.to_numeric(ordered["projected_route_dist_m"], errors="coerce")
    violations = []
    prev = None
    prev_id = None
    for idx, dist in zip(ordered["control_id"], projected):
        if pd.isna(dist):
            continue
        if prev is not None and float(dist) + 1e-6 < prev:
            violations.append(f"{prev_id}->{idx} projected distance decreases {prev:.2f}->{float(dist):.2f}")
        prev = float(dist)
        prev_id = idx
    return violations


def choose_trim_range(
    control_df: pd.DataFrame,
    ordered_len_m: float,
    same_entry_control_points: bool,
) -> tuple[float, float, str, list[str]]:
    warnings = []
    trim_controls = control_df[control_df["route_action"].astype(str).eq("trim_anchor")].copy()
    if trim_controls.empty:
        return 0.0, ordered_len_m, "keep_full_no_trim_anchor", warnings

    dists = pd.to_numeric(trim_controls["projected_route_dist_m"], errors="coerce").dropna()
    if len(dists) < len(trim_controls):
        raise ValueError("one or more trim_anchor control points has no projected_route_dist_m")

    start_d = max(0.0, float(dists.min()))
    end_d = min(ordered_len_m, float(dists.max()))
    if same_entry_control_points or end_d - start_d < 30.0:
        warnings.append("same-entry route uses keep_full policy")
        return 0.0, ordered_len_m, "same_entry_keep_full_by_control_points", warnings
    return start_d, end_d, "trim_by_route_definition_control_points", warnings


def run_case(
    case_id: str,
    input_root: Path,
    out_root: Path,
    max_control_offset_m: float,
    sample_interval_m: float,
    self_near_spatial_threshold_m: float,
    self_near_route_gap_threshold_m: float,
    allow_existing_case_dir: bool,
) -> CaseResult:
    failures = []
    warnings = []
    out_dir = out_root / case_id
    if out_dir.exists() and not allow_existing_case_dir:
        return CaseResult(case_id, "FAIL", ["output case directory already exists"], [], out_dir)

    ordered_fp = input_root / f"{case_id}{ORDERED_SUFFIX}"
    control_csv_fp = input_root / f"{case_id}{CONTROL_CSV_SUFFIX}"
    control_geojson_fp = input_root / f"{case_id}{CONTROL_GEOJSON_SUFFIX}"
    for fp in [ordered_fp, control_csv_fp, control_geojson_fp]:
        if not fp.exists():
            failures.append(f"missing input: {fp}")
    if failures:
        return CaseResult(case_id, "FAIL", failures, warnings, out_dir)

    out_dir.mkdir(parents=True, exist_ok=True)

    ordered_gdf = gpd.read_file(ordered_fp)
    if ordered_gdf.crs is None:
        ordered_gdf = ordered_gdf.set_crs("EPSG:4326")
    control_gdf = gpd.read_file(control_geojson_fp)
    if control_gdf.crs is None:
        control_gdf = control_gdf.set_crs("EPSG:4326")
    control_df = pd.read_csv(control_csv_fp)

    metric_crs = ordered_gdf.estimate_utm_crs()
    ordered_m = ordered_gdf.to_crs(metric_crs)
    control_m = control_gdf.to_crs(metric_crs)
    ordered_line_m = get_single_linestring(ordered_m)
    ordered_len_m = float(ordered_line_m.length)

    if control_points_have_fallback(control_df):
        failures.append("anchor_source/control point text contains fallback_gpx_point")

    if "projection_ok" in control_df.columns:
        bad = control_df[~control_df["projection_ok"].astype(str).str.lower().isin(["true", "1"])]
        if not bad.empty:
            failures.append(
                "route definition control points cannot be projected: "
                + ",".join(bad["control_id"].astype(str).tolist())
            )

    csv_offsets = pd.to_numeric(control_df.get("nearest_ordered_path_offset_m"), errors="coerce")
    geo_offsets = []
    projected_dists = []
    for _, row in control_m.iterrows():
        pt = row.geometry
        if pt is None or pt.is_empty:
            geo_offsets.append(float("nan"))
            projected_dists.append(float("nan"))
            continue
        proj = ordered_line_m.project(pt)
        snap = ordered_line_m.interpolate(proj)
        geo_offsets.append(float(pt.distance(snap)))
        projected_dists.append(float(proj))

    control_df["contract_projected_route_dist_m"] = projected_dists
    control_df["contract_nearest_ordered_path_offset_m"] = geo_offsets
    max_offset = max(
        [x for x in csv_offsets.dropna().tolist() + geo_offsets if pd.notna(x)] or [float("nan")]
    )
    if pd.isna(max_offset):
        failures.append("route definition control points cannot be projected onto ordered_path")
    elif max_offset > max_control_offset_m:
        failures.append(f"control point offset to ordered_path exceeds {max_control_offset_m} m: {max_offset:.2f} m")

    violations = projection_order_violations(control_df)
    if violations:
        failures.append("route definition projected order violates intended route_axis order: " + "; ".join(violations))

    trim_control_m = control_m[control_m["route_action"].astype(str).eq("trim_anchor")].copy()
    same_entry_control_points = False
    if len(trim_control_m) >= 2:
        first_geom = trim_control_m.sort_values("order").geometry.iloc[0]
        last_geom = trim_control_m.sort_values("order").geometry.iloc[-1]
        same_entry_control_points = bool(first_geom.distance(last_geom) <= max_control_offset_m)

    try:
        trim_start_m, trim_end_m, trim_mode, trim_warnings = choose_trim_range(
            control_df,
            ordered_len_m,
            same_entry_control_points=same_entry_control_points,
        )
        warnings.extend(trim_warnings)
        trimmed_line_m = cut_line_between(ordered_line_m, trim_start_m, trim_end_m)
    except Exception as exc:
        failures.append(f"trim by route-definition control points failed: {exc}")
        trim_start_m, trim_end_m, trim_mode = 0.0, ordered_len_m, "failed"
        trimmed_line_m = ordered_line_m

    trimmed_len_m = float(trimmed_line_m.length)
    if trim_mode != "same_entry_keep_full_by_control_points" and trimmed_len_m < ordered_len_m - 50.0:
        failures.append(
            f"trimmed length is unexpectedly shorter than IB0B ordered_path: {trimmed_len_m:.2f} < {ordered_len_m:.2f}"
        )

    try:
        route_points_m = build_route_points_table(trimmed_line_m, metric_crs, sample_interval_m)
        if route_points_m.empty:
            failures.append("downstream route_points cannot be generated")
    except Exception as exc:
        failures.append(f"downstream route_points cannot be generated: {exc}")
        route_points_m = gpd.GeoDataFrame(geometry=[], crs=metric_crs)

    self_near_pairs = classify_self_near_pairs(
        find_self_near_pairs(
            route_points_m,
            spatial_threshold_m=self_near_spatial_threshold_m,
            route_gap_threshold_m=self_near_route_gap_threshold_m,
        ),
        trimmed_len_m,
        same_entry_keep_full=trim_mode == "same_entry_keep_full_by_control_points",
    )
    self_near_zones = summarize_self_near_zones(self_near_pairs)
    unexpected_self_near_n = int(
        self_near_pairs["classification"].eq("unexpected_self_near").sum()
        if not self_near_pairs.empty
        else 0
    )
    expected_self_near_n = len(self_near_pairs) - unexpected_self_near_n
    if expected_self_near_n:
        warnings.append(
            f"self_near_pair_count high but explainable as expected same-entry/summit self-near: {expected_self_near_n}"
        )
    if unexpected_self_near_n:
        failures.append(f"unexpected self-near pairs present: {unexpected_self_near_n}")

    if "route_point_warning" in control_df.columns:
        spur_rows = control_df[
            control_df["route_point_warning"].fillna("").astype(str).str.contains("spur", case=False, regex=False)
        ]
        if not spur_rows.empty:
            warnings.append("mainline segment set has spur warning but ordered_path is valid")

    trimmed_gdf = gpd.GeoDataFrame(
        [
            {
                "source": "ib0d_v1_3b_control_points_only_contract_qa",
                "case_id": case_id,
                "contract": "IB0D v1.3b control-points-only",
                "input_ordered_path": str(ordered_fp),
                "input_control_points_csv": str(control_csv_fp),
                "input_control_points_geojson": str(control_geojson_fp),
                "trim_mode": trim_mode,
                "original_len_m": ordered_len_m,
                "trim_start_m": trim_start_m,
                "trim_end_m": trim_end_m,
                "trimmed_len_m": trimmed_len_m,
                "geometry": trimmed_line_m,
            }
        ],
        geometry="geometry",
        crs=metric_crs,
    ).to_crs("EPSG:4326")
    # Keep per-case filenames short enough for Windows path limits.
    trimmed_geojson_fp = out_dir / "mainline_ordered_path_trimmed.geojson"
    route_points_csv_fp = out_dir / "route_points.csv"
    self_near_csv_fp = out_dir / "self_near_pairs.csv"
    self_near_zones_fp = out_dir / "self_near_zones.csv"
    trim_summary_fp = out_dir / "trim_summary.csv"
    qa_summary_fp = out_dir / "qa_summary.txt"
    qa_map_fp = out_dir / "qa_map.html"
    control_projection_fp = out_dir / "control_point_projection.csv"

    trimmed_gdf.to_file(trimmed_geojson_fp, driver="GeoJSON")
    control_df.to_csv(control_projection_fp, index=False, encoding="utf-8-sig")
    route_points_wgs84 = route_points_m.to_crs("EPSG:4326").copy()
    route_points_wgs84["lat"] = route_points_wgs84.geometry.y
    route_points_wgs84["lon"] = route_points_wgs84.geometry.x
    route_points_wgs84[["route_point_index", "route_dist_m", "lat", "lon"]].to_csv(
        route_points_csv_fp,
        index=False,
        encoding="utf-8-sig",
    )
    self_near_pairs.to_csv(self_near_csv_fp, index=False, encoding="utf-8-sig")
    self_near_zones.to_csv(self_near_zones_fp, index=False, encoding="utf-8-sig")

    status = status_from(failures, warnings)
    output_files_exist = all(
        fp.exists()
        for fp in [
            trimmed_geojson_fp,
            route_points_csv_fp,
            self_near_csv_fp,
            self_near_zones_fp,
            control_projection_fp,
        ]
    )
    if not output_files_exist:
        failures.append("required output files are missing")
        status = "FAIL"

    summary = {
        "case_id": case_id,
        "status": status,
        "contract": "IB0D v1.3b control-points-only",
        "canonical_input_ordered_path": str(ordered_fp),
        "route_axis_control_point_authority": str(control_csv_fp),
        "legacy_ib0c_anchor_authority": "disallowed",
        "trim_mode": trim_mode,
        "original_len_m": ordered_len_m,
        "trim_start_m": trim_start_m,
        "trim_end_m": trim_end_m,
        "trimmed_len_m": trimmed_len_m,
        "control_point_count": len(control_df),
        "max_control_offset_m": max_offset,
        "route_point_count": len(route_points_m),
        "self_near_pair_count": len(self_near_pairs),
        "expected_self_near_pair_count": expected_self_near_n,
        "unexpected_self_near_pair_count": unexpected_self_near_n,
        "hard_fail_reasons": " | ".join(failures),
        "warnings": " | ".join(warnings),
        "safe_for_ib1a_ib1c_ib1g_ib1e": status in {"PASS", "WARN"},
    }
    pd.DataFrame([summary]).to_csv(trim_summary_fp, index=False, encoding="utf-8-sig")

    qa_lines = [
        "IB0D v1.3b control-points-only contract QA",
        f"case_id: {case_id}",
        f"status: {status}",
        "canonical_input: IB0B ordered_path",
        "route_axis_control_point_authority: IB0B route_definition_control_points_used",
        "legacy_ib0c_anchor_authority: disallowed; legacy / QA reference only",
        f"trim_mode: {trim_mode}",
        f"original_len_m: {ordered_len_m:.2f}",
        f"trimmed_len_m: {trimmed_len_m:.2f}",
        f"route_point_count: {len(route_points_m)}",
        f"self_near_pair_count: {len(self_near_pairs)}",
        f"expected_self_near_pair_count: {expected_self_near_n}",
        f"unexpected_self_near_pair_count: {unexpected_self_near_n}",
        "",
        "Hard FAIL:",
        *(f"- {item}" for item in failures),
        "",
        "WARN:",
        *(f"- {item}" for item in warnings),
        "",
        f"safe_for_ib1a_ib1c_ib1g_ib1e: {status in {'PASS', 'WARN'}}",
    ]
    qa_summary_fp.write_text("\n".join(qa_lines), encoding="utf-8")

    ordered_wgs84 = ordered_m.to_crs("EPSG:4326")
    control_display_m = display_offset_control_points(control_m)
    control_wgs84 = control_display_m.to_crs("EPSG:4326")
    true_control_wgs84 = gpd.GeoSeries(
        control_display_m["true_geometry"],
        crs=metric_crs,
    ).to_crs("EPSG:4326")
    center_geom = trimmed_gdf.geometry.iloc[0].centroid
    m = folium.Map(
        location=[center_geom.y, center_geom.x],
        zoom_start=15,
        tiles="CartoDB positron",
        width="100%",
        height="800px",
    )
    folium.GeoJson(
        ordered_wgs84,
        name="IB0B ordered_path canonical input",
        style_function=lambda feat: {"color": "gray", "weight": 4, "opacity": 0.45},
    ).add_to(m)
    folium.GeoJson(
        trimmed_gdf,
        name="IB0D contract output",
        style_function=lambda feat: {"color": "red", "weight": 6, "opacity": 0.9},
    ).add_to(m)
    control_fg = folium.FeatureGroup(
        name="route_definition_control_points_used (display-offset)",
        show=True,
    )
    true_fg = folium.FeatureGroup(
        name="true control point locations",
        show=False,
    )
    for idx, row in control_wgs84.iterrows():
        role = str(row.get("control_role", ""))
        color = {
            "start": "#1a9850",
            "ascent_via": "#2c7fb8",
            "turnaround": "#7b3294",
            "descent_via": "#fdae61",
            "end": "#d73027",
        }.get(role, "#636363")
        true_pt = true_control_wgs84.loc[idx]
        label = f"{row.get('order', '')}:{row.get('control_id', '')}"
        popup = (
            "<pre>"
            f"control_id: {row.get('control_id', '')}\n"
            f"role: {row.get('control_role', '')}\n"
            f"order: {row.get('order', '')}\n"
            f"name: {row.get('name', '')}\n"
            f"route_action: {row.get('route_action', '')}\n"
            f"projected_route_dist_m: {row.get('projected_route_dist_m', '')}\n"
            f"nearest_ordered_path_offset_m: {row.get('nearest_ordered_path_offset_m', '')}\n"
            f"display_cluster_size: {row.get('display_cluster_size', '')}\n"
            f"display_offset_m: {row.get('display_offset_m', '')}\n"
            f"true_lat: {true_pt.y}\n"
            f"true_lon: {true_pt.x}"
            "</pre>"
        )
        if float(row.get("display_offset_m", 0.0) or 0.0) > 0.0:
            folium.PolyLine(
                locations=[[true_pt.y, true_pt.x], [row.geometry.y, row.geometry.x]],
                color=color,
                weight=2,
                opacity=0.65,
            ).add_to(control_fg)
        folium.CircleMarker(
            location=[true_pt.y, true_pt.x],
            radius=3,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.45,
            weight=1,
            popup=folium.Popup(popup, max_width=360),
        ).add_to(true_fg)
        folium.Marker(
            location=[row.geometry.y, row.geometry.x],
            popup=folium.Popup(popup, max_width=360),
            tooltip=label,
            icon=folium.DivIcon(
                html=(
                    "<div style=\""
                    f"background:{color};"
                    "color:white;"
                    "border:2px solid white;"
                    "border-radius:12px;"
                    "box-shadow:0 1px 4px rgba(0,0,0,.35);"
                    "font-size:11px;"
                    "font-weight:700;"
                    "line-height:18px;"
                    "padding:0 5px;"
                    "white-space:nowrap;"
                    "transform:translate(-50%,-50%);"
                    "\">"
                    f"{label}"
                    "</div>"
                )
            ),
        ).add_to(control_fg)
    true_fg.add_to(m)
    control_fg.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    m.save(qa_map_fp)

    return CaseResult(case_id, status, failures, warnings, out_dir)


def main() -> int:
    args = parse_args()
    input_root = resolve_path(args.input_root)
    out_root = resolve_path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    cases = discover_cases(input_root, args.case_id)
    if not cases:
        raise SystemExit(f"No cases found in {input_root}")

    results = [
        run_case(
            case_id,
            input_root,
            out_root,
            args.max_control_offset_m,
            args.sample_interval_m,
            args.self_near_spatial_threshold_m,
            args.self_near_route_gap_threshold_m,
            args.allow_existing_case_dir,
        )
        for case_id in cases
    ]
    status_fp = out_root / "_ib0d_v1_3b_contract_case_status.csv"
    summary_all_fp = out_root / "ib0d_v1_3b_contract_qa_summary_all.csv"
    pd.DataFrame(
        [
            {
                "case_id": r.case_id,
                "status": r.status,
                "hard_fail_reasons": " | ".join(r.hard_fail_reasons),
                "warnings": " | ".join(r.warnings),
                "out_dir": str(r.out_dir),
            }
            for r in results
        ]
    ).to_csv(status_fp, index=False, encoding="utf-8-sig")

    summary_rows = []
    for r in results:
        trim_summary_fp = r.out_dir / "trim_summary.csv"
        if trim_summary_fp.exists():
            summary_rows.append(pd.read_csv(trim_summary_fp))
        else:
            summary_rows.append(
                pd.DataFrame(
                    [
                        {
                            "case_id": r.case_id,
                            "status": r.status,
                            "hard_fail_reasons": " | ".join(r.hard_fail_reasons),
                            "warnings": " | ".join(r.warnings),
                        }
                    ]
                )
            )
    pd.concat(summary_rows, ignore_index=True).to_csv(
        summary_all_fp,
        index=False,
        encoding="utf-8-sig",
    )

    for r in results:
        print(f"{r.case_id}: {r.status}")
        for item in r.hard_fail_reasons:
            print(f"  FAIL: {item}")
        for item in r.warnings:
            print(f"  WARN: {item}")
    print(f"case status CSV: {status_fp}")
    print(f"summary all CSV: {summary_all_fp}")
    return 1 if any(r.status == "FAIL" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
