from __future__ import annotations

import argparse
import html
import importlib
import json
from pathlib import Path
from typing import Any


ROUTE_CASE_MAP = {
    "juansi_waterfall": "juansi_waterfall_fitcsv_20260503",
    "qixing_lengshuikeng": "qixing_lengshuikeng_main_peak_20260523",
}

POPUP_COLUMNS = [
    "subject_id",
    "trial_id",
    "elapsed_sec",
    "route_dist_m",
    "segment_id",
    "offset_m",
    "match_quality",
    "heart_rate_bpm",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Plot one ib3a standardized activity mapmatch debug HTML map "
            "showing raw points, matched route-axis points, and offset lines."
        )
    )
    parser.add_argument("--route-folder", required=True, help="Route folder key.")
    parser.add_argument("--subject-id", required=True, help="Activity subject id.")
    parser.add_argument("--trial-id", required=True, help="Activity trial id.")
    parser.add_argument(
        "--mapmatched-root",
        default="outputs/ib3a_mapmatched_standardized_activity",
        help="Root folder containing ib3a mapmatched CSV files.",
    )
    parser.add_argument(
        "--route-profile-root",
        default="outputs/ib1_route_profile",
        help="Root folder containing ib1 route profile outputs.",
    )
    parser.add_argument(
        "--out-dir",
        default="outputs/ib3a_mapmatched_standardized_activity_debug_maps",
        help="Output directory for debug HTML maps.",
    )
    parser.add_argument(
        "--offset-line-step",
        type=int,
        default=200,
        help="Draw one raw-to-matched offset line every N source rows.",
    )
    parser.add_argument(
        "--max-points",
        type=int,
        default=5000,
        help="Maximum activity rows to draw as point markers.",
    )
    return parser.parse_args()


def read_route_profile_points(route_profile_root: Path, case_id: str) -> pd.DataFrame:
    path = route_profile_root / case_id / f"{case_id}_route_profile_points.geojson"
    if not path.exists():
        raise FileNotFoundError(f"missing route profile points GeoJSON: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    rows: list[dict[str, Any]] = []
    for feature in data.get("features", []):
        props = dict(feature.get("properties") or {})
        geom = feature.get("geometry") or {}
        coords = geom.get("coordinates") or []
        if geom.get("type") != "Point" or len(coords) < 2:
            continue
        props["lon"] = coords[0]
        props["lat"] = coords[1]
        rows.append(props)

    route = pd.DataFrame(rows)
    if route.empty:
        raise ValueError(f"route profile points are empty: {path}")

    for col in ["dist_m", "sample_idx", "lat", "lon"]:
        if col in route.columns:
            route[col] = pd.to_numeric(route[col], errors="coerce")

    sort_cols = [col for col in ["dist_m", "sample_idx"] if col in route.columns]
    if sort_cols:
        route = route.sort_values(sort_cols).reset_index(drop=True)
    route = route.dropna(subset=["lat", "lon"]).copy()
    if len(route) < 2:
        raise ValueError(f"route profile needs at least 2 valid points: {path}")
    if "dist_m" not in route.columns or route["dist_m"].isna().all():
        route["dist_m"] = np.arange(len(route), dtype=float)
    return route


def add_matched_points(activity: pd.DataFrame, route: pd.DataFrame) -> pd.DataFrame:
    out = activity.copy()
    if {"matched_lat", "matched_lon"}.issubset(out.columns):
        out["matched_lat"] = pd.to_numeric(out["matched_lat"], errors="coerce")
        out["matched_lon"] = pd.to_numeric(out["matched_lon"], errors="coerce")
        if out["matched_lat"].notna().any() and out["matched_lon"].notna().any():
            return out

    dist_col = "nearest_route_dist_m" if "nearest_route_dist_m" in out.columns else "route_dist_m"
    if dist_col not in out.columns:
        raise ValueError("mapmatched CSV needs nearest_route_dist_m or route_dist_m")

    left = out.reset_index(names="_source_index").copy()
    left["_match_dist_m"] = pd.to_numeric(left[dist_col], errors="coerce")
    route_lookup = route[["dist_m", "lat", "lon"]].dropna().sort_values("dist_m")

    matched = pd.merge_asof(
        left.sort_values("_match_dist_m"),
        route_lookup.rename(columns={"lat": "matched_lat", "lon": "matched_lon"}),
        left_on="_match_dist_m",
        right_on="dist_m",
        direction="nearest",
    ).sort_values("_source_index")

    matched = matched.drop(columns=["_source_index", "_match_dist_m", "dist_m"], errors="ignore")
    return matched.reset_index(drop=True)


def load_activity(csv_path: Path, route: pd.DataFrame) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"missing mapmatched CSV: {csv_path}")
    activity = pd.read_csv(csv_path, low_memory=False)
    for col in ["lat", "lon", "elapsed_sec", "route_dist_m", "offset_m", "heart_rate_bpm"]:
        if col in activity.columns:
            activity[col] = pd.to_numeric(activity[col], errors="coerce")
    activity = activity.dropna(subset=["lat", "lon"]).reset_index(drop=True)
    if activity.empty:
        raise ValueError(f"mapmatched CSV has no valid lat/lon rows: {csv_path}")
    return add_matched_points(activity, route)


def sample_activity_rows(activity: pd.DataFrame, max_points: int, offset_line_step: int) -> pd.DataFrame:
    activity = activity.reset_index(names="_row_index")
    if max_points <= 0 or len(activity) <= max_points:
        return activity

    line_step = max(1, offset_line_step)
    line_indices = set(range(0, len(activity), line_step))
    remaining = max(0, max_points - len(line_indices))
    even_indices = set(np.linspace(0, len(activity) - 1, remaining, dtype=int)) if remaining else set()
    indices = sorted(line_indices | even_indices)
    return activity.iloc[indices].copy()


def fmt_value(value: Any) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def popup_for_row(row: pd.Series) -> folium.Popup:
    lines = []
    for col in POPUP_COLUMNS:
        value = row.get(col, "")
        lines.append(f"<b>{html.escape(col)}:</b> {html.escape(fmt_value(value))}")
    return folium.Popup("<br>".join(lines), max_width=320)


def color_for_quality(value: Any) -> str:
    quality = str(value).strip().lower()
    if quality == "good":
        return "#1B9E77"
    if quality == "acceptable":
        return "#D95F02"
    if quality == "weak":
        return "#E7298A"
    if quality == "off_route":
        return "#D73027"
    return "#7570B3"


def build_map(
    route_folder: str,
    subject_id: str,
    trial_id: str,
    route: pd.DataFrame,
    activity: pd.DataFrame,
    offset_line_step: int,
    max_points: int,
) -> folium.Map:
    center = [float(activity["lat"].mean()), float(activity["lon"].mean())]
    m = folium.Map(location=center, zoom_start=15, tiles="CartoDB positron")

    sampled = sample_activity_rows(activity, max_points=max_points, offset_line_step=offset_line_step)
    route_coords = route[["lat", "lon"]].dropna().to_numpy().tolist()
    raw_coords = sampled[["lat", "lon"]].dropna().to_numpy().tolist()
    matched_coords = sampled[["matched_lat", "matched_lon"]].dropna().to_numpy().tolist()

    route_fg = folium.FeatureGroup(name=f"route axis ({len(route_coords)} pts)", show=True)
    folium.PolyLine(route_coords, color="#111827", weight=4, opacity=0.85).add_to(route_fg)
    route_fg.add_to(m)

    raw_fg = folium.FeatureGroup(name=f"activity raw points ({len(raw_coords)} shown)", show=True)
    for _, row in sampled.iterrows():
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=2.2,
            color="#2563EB",
            fill=True,
            fill_color="#2563EB",
            fill_opacity=0.65,
            weight=1,
            popup=popup_for_row(row),
        ).add_to(raw_fg)
    raw_fg.add_to(m)

    matched_fg = folium.FeatureGroup(name=f"matched route points ({len(matched_coords)} shown)", show=True)
    for _, row in sampled.dropna(subset=["matched_lat", "matched_lon"]).iterrows():
        quality_color = color_for_quality(row.get("match_quality", ""))
        folium.CircleMarker(
            location=[row["matched_lat"], row["matched_lon"]],
            radius=2.0,
            color=quality_color,
            fill=True,
            fill_color=quality_color,
            fill_opacity=0.8,
            weight=1,
            popup=popup_for_row(row),
        ).add_to(matched_fg)
    matched_fg.add_to(m)

    line_fg = folium.FeatureGroup(name=f"offset lines every {offset_line_step} rows", show=True)
    line_step = max(1, offset_line_step)
    line_rows = sampled[(sampled["_row_index"] % line_step) == 0].dropna(
        subset=["lat", "lon", "matched_lat", "matched_lon"]
    )
    for _, row in line_rows.iterrows():
        folium.PolyLine(
            [[row["lat"], row["lon"]], [row["matched_lat"], row["matched_lon"]]],
            color="#F59E0B",
            weight=1.4,
            opacity=0.55,
            popup=popup_for_row(row),
        ).add_to(line_fg)
    line_fg.add_to(m)

    title = html.escape(f"{route_folder} subject {subject_id} trial {trial_id}")
    title_html = (
        f'<div style="position: fixed; top: 12px; left: 50px; z-index: 9999; '
        f'background: white; padding: 8px 10px; border: 1px solid #d1d5db; '
        f'font: 13px Arial, sans-serif;"><b>{title}</b><br>'
        f'rows: {len(activity)}; shown: {len(sampled)}; offset lines: {len(line_rows)}</div>'
    )
    m.get_root().html.add_child(folium.Element(title_html))

    all_bounds = route_coords + raw_coords + matched_coords
    if all_bounds:
        m.fit_bounds(all_bounds)
    folium.LayerControl(collapsed=False).add_to(m)
    return m


def run(args: argparse.Namespace) -> int:
    global folium, np, pd
    folium = importlib.import_module("folium")
    np = importlib.import_module("numpy")
    pd = importlib.import_module("pandas")

    route_folder = str(args.route_folder)
    case_id = ROUTE_CASE_MAP.get(route_folder)
    if case_id is None:
        known = ", ".join(sorted(ROUTE_CASE_MAP))
        raise ValueError(f"unknown route_folder {route_folder!r}; known values: {known}")

    mapmatched_root = Path(args.mapmatched_root)
    route_profile_root = Path(args.route_profile_root)
    out_dir = Path(args.out_dir)

    csv_path = mapmatched_root / route_folder / f"{args.subject_id}_{args.trial_id}_mapmatched.csv"
    route = read_route_profile_points(route_profile_root, case_id)
    activity = load_activity(csv_path, route)

    m = build_map(
        route_folder=route_folder,
        subject_id=str(args.subject_id),
        trial_id=str(args.trial_id),
        route=route,
        activity=activity,
        offset_line_step=args.offset_line_step,
        max_points=args.max_points,
    )

    output_dir = out_dir / route_folder
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{args.subject_id}_{args.trial_id}_debug_map.html"
    m.save(output_path)
    print(f"Wrote debug map: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
