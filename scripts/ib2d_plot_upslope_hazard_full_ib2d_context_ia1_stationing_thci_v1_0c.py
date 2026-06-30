# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import re
import shutil
import textwrap
from pathlib import Path

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.lines import Line2D
from PIL import Image, ImageOps
from shapely.geometry import LineString, Point
from shapely.ops import nearest_points, linemerge

DPI = 150
MAP_BUFFER_M = 1000.0

DEFAULT_ROUTE_CONTEXT_NOTE = (
    "本 GPX 路線由松鶴登山口起登，經唐麻丹山步道區段後接入蝴蝶谷瀑布步道，"
    "並於接近蝴蝶谷瀑布處折返，最後沿原路返回。"
)
DEFAULT_PROXY_NOTE = (
    "圖中顏色表示各路段局部 upslope hazard proxy 分數，非沿路累積值；"
    "紅色區段為高分複核區，屬 review evidence，非正式落石、土石流或崩塌潛勢判定。"
)


POINT_LAYERS = {
    "trailhead": ("osm_trailhead_raw.geojson", "^", "#1B5E20", "登山口 trailhead"),
    "peak": ("osm_peak_raw.geojson", "*", "#6A1B9A", "山峰 peak"),
    "guidepost": ("osm_guidepost_raw.geojson", "P", "#1565C0", "指標 guidepost"),
    "shelter": ("osm_shelter_raw.geojson", "s", "#795548", "避難/休憩 shelter"),
    "bench": ("osm_bench_raw.geojson", "v", "#8D6E63", "座椅 bench"),
    "drinking_water": ("osm_drinking_water_raw.geojson", "o", "#0097A7", "飲水 drinking water"),
    "toilets": ("osm_toilets_raw.geojson", "D", "#455A64", "廁所 toilets"),
    "information": ("osm_information_office_raw.geojson", "X", "#EF6C00", "資訊 information"),
}

LINE_LAYERS = {
    "nearby_path": ("osm_highway_raw.geojson", "--", "#8F8F8F", "鄰近路徑 nearby paths"),
    "cliff": ("osm_cliff_raw.geojson", "--", "#8B0000", "崖線 cliff"),
    "waterway": ("osm_waterway_raw.geojson", "-", "#1976D2", "OSM 水系 waterway"),
    "handrail": ("osm_handrail_raw.geojson", ":", "#6D4C41", "扶手 handrail"),
    "safety_rope": ("osm_safety_rope_raw.geojson", "-.", "#5D4037", "安全繩 safety rope"),
}

AREA_LAYERS = {
    "scree": ("osm_scree_raw.geojson", "#D7CCC8", "#8D6E63", "碎石坡 scree"),
    "wetland": ("osm_wetland_raw.geojson", "#B2DFDB", "#00897B", "濕地 wetland"),
    "water_area": ("osm_water_area_raw.geojson", "#BBDEFB", "#1976D2", "水域 water area"),
    "bare_rock": ("osm_bare_rock_raw.geojson", "#BDBDBD", "#757575", "裸岩 bare rock"),
}

ROUTE_RISK_RADAR_AXES = [
    ("體力難度", ["effort_score", "route_effort_risk_score"]),
    ("技術難度", ["technical_risk_score"]),
    ("基礎危害", ["exposure_score"]),
    ("地形壓力", ["terrain_score", "terrain_window_risk_score"]),
    ("濕滑敏感", ["surface_slip_risk_score"]),
    ("水文敏感", ["hydrology_risk_score", "hydro_terrain_amplifier_score"]),
]


def find_project_root() -> Path:
    """Resolve project root when this script is placed in scripts/ or a subfolder.

    Fallback to cwd so it still works when called from D:\\mountain_work\\115_osm.
    """
    here = Path(__file__).resolve()
    markers = ("outputs", "activity_input", "nlsc_raw", "scripts")
    for parent in [here.parent, *here.parents]:
        if any((parent / marker).exists() for marker in markers):
            if parent.name.lower() == "scripts" and parent.parent.exists():
                return parent.parent
            return parent
    return Path.cwd().resolve()


PROJECT_ROOT = find_project_root()

mpl.rcParams["font.sans-serif"] = [
    "Microsoft JhengHei",
    "Microsoft YaHei",
    "Noto Sans CJK TC",
    "Arial Unicode MS",
    "DejaVu Sans",
]
mpl.rcParams["axes.unicode_minus"] = False


ELEVATION_COL_CANDIDATES = [
    "ele_smooth",
    "ele_gpx_m",
    "route_ele_m",
    "route_elevation_m",
    "elevation_m",
    "elev_m",
    "ele_m",
    "elevation",
    "elev",
    "ele",
    "height",
    "z",
]

CONTOUR_ELEV_COL_CANDIDATES = ["zv2", "z", "elev", "elevation", "height", "contour", "altitude"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Plot upslope contributing-area hazard proxy map with NLSC/OSM context, "
            "IA1 named-trail stationing, elevation profile, and THCI v1.0c radar."
        )
    )
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--case-name", default=None)
    parser.add_argument("--hazard-csv", default=None)
    parser.add_argument("--hazard-geojson", default=None)
    parser.add_argument("--profile-geojson", default=None)
    parser.add_argument("--risk-csv", default=None, help="Deprecated compatibility argument; THCI v1.0c radar no longer falls back to route-risk CSV.")
    parser.add_argument("--osm-raw-dir", default=None, help="Defaults to osm_raw_output/<case-id>.")
    parser.add_argument("--ia1-output-dir", default=None, help="IA1/OSM raw output directory used to locate named trail highway features. Defaults to --osm-raw-dir.")
    parser.add_argument("--route-radar-png", default=None, help="Deprecated alias for --thci-radar-png. Prefer THCI v1.0c radar PNG.")
    parser.add_argument("--thci-radar-png", default=None, help="Existing THCI v1.0c radar PNG. Defaults to outputs/thci_radar_v1_0c/<case-id>/<case-id>_thci_radar_v1_0c.png.")
    parser.add_argument("--thci-plot-data-csv", default=None, help="Optional THCI v1.0c radar plot-data CSV with columns: axis_order, axis_id, axis_label_zh, score.")
    parser.add_argument("--thci-summary-json", default=None, help="Optional THCI v1.0c radar summary JSON containing axis_order and axis_scores.")
    parser.add_argument("--trail-name", default=None, help="Named trail label shown on the map. Defaults to case-name.")
    parser.add_argument("--trail-keywords", default=None, help="Keywords used to find the named trail in IA1/osm_highway_raw.geojson. Separate by comma, pipe, or semicolon. Defaults to trail-name/case-name derived terms.")
    parser.add_argument("--trail-km-step", type=float, default=0.2, help="Named-trail station label interval in km, measured from the named trail start found in IA1. Use 0 to disable.")
    parser.add_argument("--trail-display-length-km", type=float, default=None, help="Optional official/expected named-trail display length in km. Labels are placed along IA1/OSM geometry, while displayed station values are scaled to this length.")
    parser.add_argument("--trail2-name", default=None, help="Optional second named trail shown on the two profile panels only.")
    parser.add_argument("--trail2-keywords", default=None, help="Keywords used to find the second named trail in IA1/osm_highway_raw.geojson. Separate by comma, pipe, or semicolon.")
    parser.add_argument("--trail2-display-length-km", type=float, default=None, help="Optional official/expected display length for the second named trail in km.")
    parser.add_argument("--trail2-km-step", type=float, default=None, help="Second-trail station label interval in km. Defaults to --trail-km-step.")
    parser.add_argument("--profile-trail-label-all", action="store_true", help="Label every 0.2k/step marker on profile panels. Default labels endpoints and every 0.4k to reduce clutter.")
    parser.add_argument("--figure-number", default="圖 X", help="Figure number prefix used in the generated formal caption.")
    parser.add_argument("--route-context-note", default=DEFAULT_ROUTE_CONTEXT_NOTE, help="Route narrative used in the formal caption and map footnote. Use empty string to suppress route narrative.")
    parser.add_argument("--proxy-note", default=DEFAULT_PROXY_NOTE, help="Proxy/disclaimer note used in the formal caption and map footnote. Use empty string to suppress proxy note.")
    parser.add_argument("--no-map-footnote", action="store_true", help="Do not draw the short route/proxy footnote at the bottom of the map panel.")
    parser.add_argument("--trail-match-buffer-m", type=float, default=60.0, help="Maximum distance between IA1 named trail geometry and the route for stationing, in meters.")
    parser.add_argument("--km-step", type=float, default=0.0, help="Whole-GPX distance label interval in km. Default 0 disables whole-route labels; named trail labels use --trail-km-step.")
    parser.add_argument("--contour-fp", default=None)
    parser.add_argument("--collapse-mask-fp", default=None)
    parser.add_argument("--watercourse-fp", default=None)
    parser.add_argument("--out-dir", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path | None) -> Path | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    value_str = str(value).strip()
    if not value_str or value_str.lower() in {"nan", "none", "null"}:
        return None
    path = Path(value_str)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def default_hazard_dir(case_id: str) -> Path:
    return PROJECT_ROOT / "outputs" / "ib1g3_upslope_contributing_area_hazard_proxy" / case_id


def default_hazard_csv(case_id: str) -> Path:
    return default_hazard_dir(case_id) / f"{case_id}_upslope_contributing_area_hazard_proxy.csv"


def default_hazard_geojson(case_id: str) -> Path:
    return default_hazard_dir(case_id) / f"{case_id}_upslope_contributing_area_hazard_proxy.geojson"


def default_osm_raw_dir(case_id: str) -> Path:
    return PROJECT_ROOT / "osm_raw_output" / case_id


def default_risk_csv(case_id: str) -> Path:
    return PROJECT_ROOT / "outputs" / "ib2_v2_route_risk" / case_id / f"{case_id}_route_risk_v2.csv"


def default_thci_radar_png(case_id: str) -> Path:
    return PROJECT_ROOT / "outputs" / "thci_radar_v1_0c" / case_id / f"{case_id}_thci_radar_v1_0c.png"


def default_thci_plot_data_csv(case_id: str) -> Path:
    return PROJECT_ROOT / "outputs" / "thci_radar_v1_0c" / case_id / f"{case_id}_thci_radar_plot_data_v1_0c.csv"


def default_thci_summary_json(case_id: str) -> Path:
    return PROJECT_ROOT / "outputs" / "thci_radar_v1_0c" / case_id / f"{case_id}_thci_radar_summary_v1_0c.json"


def default_thci_axis_score_csv(case_id: str) -> Path:
    return PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_0c" / case_id / f"{case_id}_thci_axis_scores_v1_0c.csv"


def default_thci_axis_score_summary_json(case_id: str) -> Path:
    return PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_0c" / case_id / f"{case_id}_thci_axis_score_summary_v1_0c.json"


def default_profile_geojson(case_id: str) -> Path:
    return (
        PROJECT_ROOT
        / "outputs"
        / "ib1e_route_profile_contour_window_terrain"
        / case_id
        / f"{case_id}_route_profile_contour_window_terrain_enriched.geojson"
    )


def default_out_dir(case_id: str) -> Path:
    return PROJECT_ROOT / "outputs" / "ib2d_upslope_contributing_hazard_map" / case_id


def first_present_path(df: pd.DataFrame, col: str) -> Path | None:
    if col not in df.columns:
        return None
    values = df[col].dropna().astype(str).str.strip()
    values = values[~values.str.lower().isin({"", "nan", "none", "null"})]
    if values.empty:
        return None
    return resolve_path(values.iloc[0])


def read_optional_layer(path: Path | None, crs) -> gpd.GeoDataFrame:
    if path is None or not path.exists():
        return gpd.GeoDataFrame(geometry=[], crs=crs)
    try:
        gdf = gpd.read_file(path)
    except Exception as exc:
        print(f"WARNING: could not read {path}: {exc}")
        return gpd.GeoDataFrame(geometry=[], crs=crs)
    if gdf.empty:
        return gpd.GeoDataFrame(geometry=[], crs=crs)
    if gdf.crs is None:
        # NLSC 25K SHP commonly uses TWD97 / TM2 zone 121.
        gdf = gdf.set_crs("EPSG:3826")
    return gdf.to_crs(crs)




def read_osm_layer(path: Path | None, crs) -> gpd.GeoDataFrame:
    """Read OSM GeoJSON context layers. OSM raw outputs are normally EPSG:4326."""
    if path is None or not path.exists():
        return gpd.GeoDataFrame(geometry=[], crs=crs)
    try:
        gdf = gpd.read_file(path)
    except Exception as exc:
        print(f"WARNING: could not read OSM layer {path}: {exc}")
        return gpd.GeoDataFrame(geometry=[], crs=crs)
    if gdf.empty:
        return gpd.GeoDataFrame(geometry=[], crs=crs)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    return gdf.to_crs(crs)


def subset_geometry(gdf: gpd.GeoDataFrame, area) -> gpd.GeoDataFrame:
    if gdf.empty:
        return gdf
    try:
        return gdf[gdf.intersects(area)].copy()
    except Exception:
        return gdf.iloc[0:0].copy()


def plot_osm_context(ax, osm_raw_dir: Path | None, metric_crs, route_area) -> tuple[list[Line2D], dict[str, int]]:
    """Plot OSM context layers and return legend handles plus plotted feature counts."""
    handles: list[Line2D] = []
    counts: dict[str, int] = {}
    if osm_raw_dir is None or not osm_raw_dir.exists():
        return handles, counts

    for key, (filename, face, edge, label) in AREA_LAYERS.items():
        layer = subset_geometry(read_osm_layer(osm_raw_dir / filename, metric_crs), route_area)
        counts[key] = int(len(layer))
        if not layer.empty:
            layer.plot(ax=ax, facecolor=face, edgecolor=edge, alpha=0.30, linewidth=0.8, zorder=1.4)
            handles.append(Line2D([0], [0], marker="s", color=edge, label=label, markerfacecolor=face, markersize=7, linestyle="None"))

    for key, (filename, linestyle, color, label) in LINE_LAYERS.items():
        layer = subset_geometry(read_osm_layer(osm_raw_dir / filename, metric_crs), route_area)
        counts[key] = int(len(layer))
        if not layer.empty:
            layer.plot(ax=ax, color=color, linestyle=linestyle, linewidth=1.25, alpha=0.78, zorder=2.6)
            handles.append(Line2D([0], [0], color=color, linestyle=linestyle, lw=2.0, label=label))

    for key, (filename, marker, color, label) in POINT_LAYERS.items():
        layer = subset_geometry(read_osm_layer(osm_raw_dir / filename, metric_crs), route_area)
        counts[key] = int(len(layer))
        if not layer.empty:
            geom = layer.geometry
            if not all(geom.geom_type == "Point"):
                geom = geom.representative_point()
            ax.scatter(geom.x, geom.y, c=color, marker=marker, s=52, edgecolors="white", linewidths=0.7, zorder=8)
            handles.append(Line2D([0], [0], marker=marker, color="w", label=label, markerfacecolor=color, markeredgecolor="white", markersize=8, linestyle="None"))
    return handles, counts


def route_center_point(route_gdf: gpd.GeoDataFrame):
    try:
        return geometry_union(route_gdf.geometry).representative_point()
    except Exception:
        bounds = route_gdf.total_bounds
        return gpd.points_from_xy([(bounds[0] + bounds[2]) / 2.0], [(bounds[1] + bounds[3]) / 2.0])[0]


def add_trail_name_label(ax, trail_name: str | None, route_gdf: gpd.GeoDataFrame) -> None:
    if not trail_name or route_gdf.empty:
        return
    pt = route_center_point(route_gdf)
    ax.text(
        pt.x,
        pt.y + 65,
        trail_name,
        fontsize=11,
        weight="bold",
        color="#222222",
        ha="center",
        va="bottom",
        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#666666", alpha=0.88),
        zorder=14,
    )


def build_route_line_from_segments(route_gdf: gpd.GeoDataFrame) -> LineString | None:
    if route_gdf.empty:
        return None
    gdf = route_gdf.copy()
    sort_col = "dist_start" if "dist_start" in gdf.columns else ("dist_mid" if "dist_mid" in gdf.columns else None)
    if sort_col:
        gdf = gdf.sort_values(sort_col)
    coords: list[tuple[float, float]] = []
    for geom in gdf.geometry:
        parts = list(iter_line_parts(geom))
        if not parts:
            continue
        line = parts[0]
        line_coords = [(float(x), float(y)) for x, y, *_ in line.coords]
        if not coords:
            coords.extend(line_coords)
        else:
            if coords[-1] == line_coords[0]:
                coords.extend(line_coords[1:])
            else:
                coords.extend(line_coords)
    if len(coords) < 2:
        return None
    return LineString(coords)


def add_km_labels(ax, route_gdf: gpd.GeoDataFrame, step_km: float = 0.5) -> None:
    if step_km is None or step_km <= 0 or route_gdf.empty:
        return
    route_line = build_route_line_from_segments(route_gdf)
    if route_line is None or route_line.is_empty:
        return
    if "dist_end" in route_gdf.columns:
        total_m = float(pd.to_numeric(route_gdf["dist_end"], errors="coerce").max())
    elif "dist_mid" in route_gdf.columns:
        total_m = float(pd.to_numeric(route_gdf["dist_mid"], errors="coerce").max())
    else:
        total_m = float(route_line.length)
    if not np.isfinite(total_m) or total_m <= 0:
        total_m = float(route_line.length)

    for dist_m in np.arange(0.0, total_m + 1.0, step_km * 1000.0):
        # Use true line length ratio, but label with route distance from CSV.
        ratio = min(max(dist_m / total_m, 0.0), 1.0)
        pt = route_line.interpolate(ratio * route_line.length)
        ax.scatter(pt.x, pt.y, s=20, c="white", edgecolors="#444444", linewidths=0.7, zorder=15)
        ax.text(
            pt.x + 15,
            pt.y + 10,
            f"{dist_m / 1000.0:.1f}k",
            fontsize=8.2,
            color="#222222",
            ha="left",
            va="bottom",
            bbox=dict(boxstyle="round,pad=0.14", fc="white", ec="#999999", alpha=0.86),
            zorder=15,
        )



def split_trail_keywords(raw_keywords: str | None, trail_name: str | None, case_name: str | None) -> list[str]:
    candidates: list[str] = []
    if raw_keywords:
        candidates.extend([x.strip() for x in re.split(r"[,;|，、；]+", raw_keywords) if x.strip()])
    else:
        for text_value in [trail_name, case_name]:
            if not text_value:
                continue
            candidates.append(text_value.strip())
            for token in re.split(r"\s+", text_value.strip()):
                token = token.strip()
                if len(token) >= 2:
                    candidates.append(token)
            if "蝴蝶谷" in text_value:
                candidates.extend(["蝴蝶谷", "蝴蝶谷瀑布", "蝴蝶谷瀑布步道", "蝴蝶谷步道"])
    seen = set()
    out: list[str] = []
    for kw in candidates:
        kw = kw.strip()
        if not kw or kw in seen:
            continue
        seen.add(kw)
        out.append(kw)
    return out


def find_ia1_highway_geojson(ia1_output_dir: Path | None) -> Path | None:
    if ia1_output_dir is None or not ia1_output_dir.exists():
        return None
    preferred = [
        ia1_output_dir / "osm_highway_raw.geojson",
        ia1_output_dir / "highway_raw.geojson",
        ia1_output_dir / "ia1_osm_highway_raw.geojson",
    ]
    for fp in preferred:
        if fp.exists():
            return fp
    matches = sorted(ia1_output_dir.glob("*highway*.geojson"))
    if matches:
        return matches[0]
    matches = sorted(ia1_output_dir.rglob("*highway*.geojson"))
    return matches[0] if matches else None


def text_columns_for_match(gdf: gpd.GeoDataFrame) -> list[str]:
    preferred = [
        "name", "name:zh", "name:zh-TW", "name:en", "alt_name", "official_name",
        "description", "ref", "operator", "note", "osm_name",
    ]
    cols = [c for c in preferred if c in gdf.columns]
    for col in gdf.columns:
        if col == "geometry" or col in cols:
            continue
        if pd.api.types.is_object_dtype(gdf[col]):
            cols.append(col)
    return cols


def filter_named_trail_features(highway_gdf: gpd.GeoDataFrame, keywords: list[str]) -> gpd.GeoDataFrame:
    if highway_gdf.empty or not keywords:
        return highway_gdf.iloc[0:0].copy()
    cols = text_columns_for_match(highway_gdf)
    if not cols:
        return highway_gdf.iloc[0:0].copy()
    text_blob = highway_gdf[cols].fillna("").astype(str).agg(" ".join, axis=1)
    pattern = "|".join(re.escape(kw) for kw in keywords if kw)
    if not pattern:
        return highway_gdf.iloc[0:0].copy()
    mask = text_blob.str.contains(pattern, case=False, regex=True, na=False)
    return highway_gdf[mask].copy()


def sample_points_on_geometry(geom, max_points_per_part: int = 80) -> list[Point]:
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "Point":
        return [geom]
    points: list[Point] = []
    for line in iter_line_parts(geom):
        coords = list(line.coords)
        if not coords:
            continue
        if len(coords) <= max_points_per_part:
            chosen = coords
        else:
            idx = np.linspace(0, len(coords) - 1, max_points_per_part).round().astype(int)
            chosen = [coords[i] for i in idx]
        for x, y, *_ in chosen:
            points.append(Point(float(x), float(y)))
        # Include regularly interpolated samples so long straight segments are still covered.
        if line.length > 0:
            n = max(2, min(max_points_per_part, int(np.ceil(line.length / 25.0))))
            for d in np.linspace(0.0, line.length, n):
                points.append(line.interpolate(float(d)))
    return points


def route_total_csv_distance_m(route_gdf: gpd.GeoDataFrame, route_line: LineString) -> float:
    for col in ["dist_end", "dist_mid", "dist_start"]:
        if col in route_gdf.columns:
            value = float(pd.to_numeric(route_gdf[col], errors="coerce").max())
            if np.isfinite(value) and value > 0:
                return value
    return float(route_line.length)




def find_first_contiguous_route_match_interval(
    route_gdf: gpd.GeoDataFrame,
    named_gdf: gpd.GeoDataFrame,
    match_buffer_m: float,
    gap_tolerance_m: float = 35.0,
    min_interval_m: float = 80.0,
) -> tuple[float, float, dict] | None:
    """Find the first contiguous route pass matching the named IA1 highway.

    This avoids the out-and-back problem where a named trail is traversed twice:
    using the min/max projection across all matches can span both the outbound
    and return passes, causing labels such as 2.2k to appear physically close to
    the 0.0k/0.2k area.  We instead locate continuous route-distance runs whose
    route segments are close to the named highway and choose the first valid run.
    """
    if route_gdf.empty or named_gdf.empty:
        return None
    if "dist_start" not in route_gdf.columns or "dist_end" not in route_gdf.columns:
        return None
    try:
        named_union = geometry_union(named_gdf.geometry)
    except Exception:
        return None
    if named_union is None or named_union.is_empty:
        return None

    work = route_gdf.copy()
    work["_dist_start_num"] = pd.to_numeric(work["dist_start"], errors="coerce")
    work["_dist_end_num"] = pd.to_numeric(work["dist_end"], errors="coerce")
    work = work.dropna(subset=["_dist_start_num", "_dist_end_num"])
    if work.empty:
        return None
    try:
        work["_named_dist_m"] = work.geometry.distance(named_union)
    except Exception:
        return None
    matched = work[work["_named_dist_m"] <= float(match_buffer_m)].sort_values("_dist_start_num").copy()
    if matched.empty:
        return None

    groups: list[list[dict]] = []
    current: list[dict] = []
    last_end: float | None = None
    for _, row in matched.iterrows():
        start = float(row["_dist_start_num"])
        end = float(row["_dist_end_num"])
        if end < start:
            start, end = end, start
        item = {"start": start, "end": end, "dist_to_named_m": float(row["_named_dist_m"])}
        if last_end is None or start <= last_end + float(gap_tolerance_m):
            current.append(item)
            last_end = max(end, last_end if last_end is not None else end)
        else:
            groups.append(current)
            current = [item]
            last_end = end
    if current:
        groups.append(current)

    run_rows = []
    for idx, group in enumerate(groups, start=1):
        start = min(x["start"] for x in group)
        end = max(x["end"] for x in group)
        length = end - start
        run_rows.append(
            {
                "run_index": idx,
                "start_m": start,
                "end_m": end,
                "length_m": length,
                "segment_count": len(group),
                "mean_dist_to_named_m": float(np.mean([x["dist_to_named_m"] for x in group])),
            }
        )
    if not run_rows:
        return None

    valid = [r for r in run_rows if r["length_m"] >= float(min_interval_m)]
    chosen = valid[0] if valid else max(run_rows, key=lambda r: r["length_m"])
    diagnostics = {
        "trail_stationing_method": "first_contiguous_route_pass_from_ia1_highway",
        "trail_match_run_count": len(run_rows),
        "trail_match_run_index": int(chosen["run_index"]),
        "trail_match_run_segment_count": int(chosen["segment_count"]),
        "trail_match_run_mean_dist_to_named_m": float(chosen["mean_dist_to_named_m"]),
    }
    return float(chosen["start_m"]), float(chosen["end_m"]), diagnostics

def find_named_trail_station_range(
    route_gdf: gpd.GeoDataFrame,
    ia1_output_dir: Path | None,
    trail_name: str | None,
    trail_keywords: str | None,
    case_name: str | None,
    match_buffer_m: float = 60.0,
) -> tuple[dict, gpd.GeoDataFrame]:
    info = {
        "trail_stationing_found": False,
        "trail_name": trail_name or "",
        "trail_keywords": "",
        "ia1_highway_geojson": "",
        "trail_highway_match_count": 0,
        "trail_highway_close_match_count": 0,
        "trail_start_route_m": np.nan,
        "trail_end_route_m": np.nan,
        "trail_length_m": np.nan,
        "trail_match_buffer_m": float(match_buffer_m),
        "trail_stationing_note": "",
    }
    empty = gpd.GeoDataFrame(geometry=[], crs=route_gdf.crs)
    route_line = build_route_line_from_segments(route_gdf)
    if route_line is None or route_line.is_empty:
        info["trail_stationing_note"] = "route_line_unavailable"
        return info, empty

    keywords = split_trail_keywords(trail_keywords, trail_name, case_name)
    info["trail_keywords"] = ";".join(keywords)
    highway_fp = find_ia1_highway_geojson(ia1_output_dir)
    if highway_fp is None:
        info["trail_stationing_note"] = "ia1_highway_geojson_not_found"
        return info, empty
    info["ia1_highway_geojson"] = str(highway_fp)

    highway = read_osm_layer(highway_fp, route_gdf.crs)
    named = filter_named_trail_features(highway, keywords)
    info["trail_highway_match_count"] = int(len(named))
    if named.empty:
        info["trail_stationing_note"] = "no_highway_name_keyword_match"
        return info, empty

    named = named.copy()
    named["route_dist_m"] = named.geometry.distance(route_line)
    close = named[named["route_dist_m"] <= float(match_buffer_m)].copy()
    info["trail_highway_close_match_count"] = int(len(close))
    if close.empty:
        info["trail_stationing_note"] = "named_highway_found_but_not_close_to_route"
        return info, named

    interval = find_first_contiguous_route_match_interval(
        route_gdf=route_gdf,
        named_gdf=close,
        match_buffer_m=match_buffer_m,
    )
    if interval is not None:
        start_route_m, end_route_m, diagnostics = interval
        info.update(
            {
                "trail_stationing_found": True,
                "trail_start_route_m": float(start_route_m),
                "trail_end_route_m": float(end_route_m),
                "trail_length_m": float(end_route_m - start_route_m),
                "trail_stationing_note": "ok_named_ia1_highway_first_contiguous_route_pass",
                **diagnostics,
            }
        )
        close["trail_station_start_route_m"] = float(start_route_m)
        close["trail_station_end_route_m"] = float(end_route_m)
        return info, close

    # Fallback: projection across the complete route. This is kept only for
    # unusual cases where route segment distances are unavailable. For ordinary
    # out-and-back GPX, the contiguous-route-pass method above is preferred.
    line_projections: list[float] = []
    for geom in close.geometry:
        if geom is None or geom.is_empty:
            continue
        try:
            route_pt, _ = nearest_points(route_line, geom)
            if route_pt.distance(geom) <= match_buffer_m:
                line_projections.append(float(route_line.project(route_pt)))
        except Exception:
            pass
        for pt in sample_points_on_geometry(geom):
            if pt.distance(route_line) <= match_buffer_m:
                line_projections.append(float(route_line.project(pt)))

    if not line_projections:
        info["trail_stationing_note"] = "close_highway_found_but_no_projected_samples"
        return info, close

    line_start_m = max(0.0, min(line_projections))
    line_end_m = min(float(route_line.length), max(line_projections))
    if line_end_m <= line_start_m:
        info["trail_stationing_note"] = "invalid_projected_trail_range"
        return info, close

    total_route_m = route_total_csv_distance_m(route_gdf, route_line)
    start_route_m = line_start_m / float(route_line.length) * total_route_m
    end_route_m = line_end_m / float(route_line.length) * total_route_m
    info.update(
        {
            "trail_stationing_found": True,
            "trail_start_route_m": float(start_route_m),
            "trail_end_route_m": float(end_route_m),
            "trail_length_m": float(end_route_m - start_route_m),
            "trail_stationing_note": "fallback_projected_named_ia1_highway_to_full_route",
            "trail_stationing_method": "fallback_full_route_projection",
        }
    )
    close["trail_station_start_route_m"] = float(start_route_m)
    close["trail_station_end_route_m"] = float(end_route_m)
    return info, close



def build_named_trail_reference_line(
    close_named: gpd.GeoDataFrame,
    route_gdf: gpd.GeoDataFrame,
    start_route_m: float | None = None,
) -> LineString | None:
    """Build a linear-reference line from IA1/OSM named trail geometry.

    GPX tracks may include approach trails, duplicated out-and-back passes, or
    overlapping route segments.  Therefore named-trail kilometre labels should
    be measured along the IA1/OSM named highway geometry, not along the complete
    GPX route line.  The line is oriented so 0.0k is closest to the detected
    first contiguous route pass start.
    """
    if close_named is None or close_named.empty:
        return None

    line_parts: list[LineString] = []
    for geom in close_named.geometry:
        for part in iter_line_parts(geom):
            if part is not None and (not part.is_empty) and part.length > 0:
                line_parts.append(part)
    if not line_parts:
        return None

    ref_geom = None
    try:
        ref_geom = linemerge(geometry_union(gpd.GeoSeries(line_parts, crs=close_named.crs)))
    except Exception:
        try:
            ref_geom = linemerge(line_parts)
        except Exception:
            ref_geom = None

    candidate_lines: list[LineString] = []
    if ref_geom is not None and not ref_geom.is_empty:
        if ref_geom.geom_type == "LineString":
            candidate_lines = [ref_geom]
        elif ref_geom.geom_type == "MultiLineString":
            candidate_lines = [g for g in ref_geom.geoms if g.geom_type == "LineString" and g.length > 0]
    if not candidate_lines:
        candidate_lines = line_parts

    # Prefer the longest named feature; short named spurs are usually side fragments.
    line = max(candidate_lines, key=lambda g: float(g.length))

    try:
        route_line = build_route_line_from_segments(route_gdf)
        if route_line is not None and not route_line.is_empty and start_route_m is not None and np.isfinite(start_route_m):
            total_route_m = route_total_csv_distance_m(route_gdf, route_line)
            if total_route_m > 0 and route_line.length > 0:
                start_line_m = max(0.0, min(float(route_line.length), float(start_route_m) / total_route_m * float(route_line.length)))
                detected_start_pt = route_line.interpolate(start_line_m)
                coords = list(line.coords)
                if len(coords) >= 2:
                    d0 = Point(coords[0]).distance(detected_start_pt)
                    d1 = Point(coords[-1]).distance(detected_start_pt)
                    if d1 < d0:
                        line = LineString(list(reversed(coords)))
    except Exception:
        pass

    return line

def add_named_trail_station_labels(
    ax,
    route_gdf: gpd.GeoDataFrame,
    ia1_output_dir: Path | None,
    trail_name: str | None,
    trail_keywords: str | None,
    case_name: str | None,
    step_km: float = 0.2,
    match_buffer_m: float = 60.0,
    trail_display_length_km: float | None = None,
) -> tuple[dict, gpd.GeoDataFrame]:
    info, close_named = find_named_trail_station_range(
        route_gdf=route_gdf,
        ia1_output_dir=ia1_output_dir,
        trail_name=trail_name,
        trail_keywords=trail_keywords,
        case_name=case_name,
        match_buffer_m=match_buffer_m,
    )
    if not info.get("trail_stationing_found") or step_km is None or step_km <= 0:
        return info, close_named

    named_line = build_named_trail_reference_line(
        close_named=close_named,
        route_gdf=route_gdf,
        start_route_m=float(info.get("trail_start_route_m", np.nan)),
    )
    if named_line is None or named_line.is_empty or named_line.length <= 0:
        info["trail_stationing_note"] = str(info.get("trail_stationing_note", "")) + "|named_osm_line_unavailable"
        return info, close_named

    info["trail_stationing_method"] = "ia1_named_highway_geometry_linear_reference"
    osm_length_m = float(named_line.length)
    display_length_m = osm_length_m
    display_length_source = "osm_named_highway_geometry"
    if trail_display_length_km is not None and np.isfinite(trail_display_length_km) and float(trail_display_length_km) > 0:
        display_length_m = float(trail_display_length_km) * 1000.0
        display_length_source = "field_sign_or_argument"

    info["trail_osm_length_m"] = osm_length_m
    info["trail_display_length_m"] = display_length_m
    info["trail_display_length_source"] = display_length_source
    # trail_length_m is the displayed named-trail stationing length.  Keep
    # trail_osm_length_m separately so the summary exposes the geometry source.
    info["trail_length_m"] = display_length_m

    # Mark the IA1/OSM named-trail 0.0k point.
    start_pt = named_line.interpolate(0.0)
    ax.scatter(start_pt.x, start_pt.y, s=80, c="#FFFFFF", edgecolors="#0B3D2E", marker="D", linewidths=1.1, zorder=18)
    ax.text(
        start_pt.x + 18,
        start_pt.y + 18,
        f"{trail_name or 'named trail'} 0.0k 起點",
        fontsize=8.6,
        weight="bold",
        color="#0B3D2E",
        ha="left",
        va="bottom",
        bbox=dict(boxstyle="round,pad=0.17", fc="white", ec="#0B3D2E", alpha=0.88),
        zorder=18,
    )

    # Draw kilometre labels along IA1/OSM named-trail geometry, not along the
    # full GPX.  Displayed station values may optionally be scaled to an
    # official/expected trail length, while label positions still follow the
    # available IA1/OSM geometry.
    step_m = float(step_km) * 1000.0
    if step_m <= 0 or display_length_m <= 0 or osm_length_m <= 0:
        return info, close_named
    n_steps = int(np.floor((display_length_m + 1e-6) / step_m))
    label_m_values = [float(i) * step_m for i in range(n_steps + 1)]
    if display_length_m - label_m_values[-1] > min(50.0, step_m * 0.25):
        label_m_values.append(display_length_m)
    elif abs(display_length_m - label_m_values[-1]) <= min(25.0, step_m * 0.125):
        label_m_values[-1] = display_length_m

    for display_rel_m in label_m_values:
        position_rel_m = (display_rel_m / display_length_m) * osm_length_m
        position_rel_m = max(0.0, min(osm_length_m, float(position_rel_m)))
        pt = named_line.interpolate(position_rel_m)
        label = f"{display_rel_m / 1000.0:.1f}k"
        ax.scatter(pt.x, pt.y, s=22, c="white", edgecolors="#123B69", linewidths=0.75, zorder=17)
        ax.text(
            pt.x + 13,
            pt.y + 9,
            label,
            fontsize=7.8,
            color="#123B69",
            ha="left",
            va="bottom",
            bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="#6B8FB8", alpha=0.86),
            zorder=17,
        )
    return info, close_named


PROFILE_TRAIL_COLORS = ["#123B69", "#7B1FA2", "#0B6E4F", "#9A4D00"]


def station_label_values_m(display_length_m: float, step_km: float) -> list[float]:
    """Return displayed station values in meters, including the terminal point."""
    if display_length_m is None or not np.isfinite(display_length_m) or display_length_m <= 0:
        return []
    step_m = float(step_km) * 1000.0
    if step_m <= 0:
        return []
    n_steps = int(np.floor((display_length_m + 1e-6) / step_m))
    values = [float(i) * step_m for i in range(n_steps + 1)]
    if not values:
        values = [0.0]
    # Always include the terminal station when it is materially different from
    # the last regular 0.2k tick.  If it is very close, snap the last label to
    # the terminal value so official lengths such as 1.4k are shown exactly.
    if display_length_m - values[-1] > min(50.0, step_m * 0.25):
        values.append(float(display_length_m))
    elif abs(display_length_m - values[-1]) <= min(25.0, step_m * 0.125):
        values[-1] = float(display_length_m)
    return values


def build_profile_markers_for_named_trail(
    route_gdf: gpd.GeoDataFrame,
    close_named: gpd.GeoDataFrame,
    trail_info: dict,
    trail_name: str | None,
    step_km: float,
    trail_display_length_km: float | None = None,
    trail_order: int = 1,
) -> pd.DataFrame:
    """Build GPX-distance profile markers for a named IA1/OSM trail.

    Map labels are placed on the IA1/OSM geometry.  Profile labels need an
    x-coordinate in GPX distance, so each station point on the named geometry is
    projected back onto the complete GPX route line.  This keeps profile panels
    interpretable when the GPX includes approach trails or out-and-back travel.
    """
    if close_named is None or close_named.empty or not trail_info.get("trail_stationing_found"):
        return pd.DataFrame()
    if step_km is None or step_km <= 0:
        return pd.DataFrame()
    route_line = build_route_line_from_segments(route_gdf)
    if route_line is None or route_line.is_empty or route_line.length <= 0:
        return pd.DataFrame()
    named_line = build_named_trail_reference_line(
        close_named=close_named,
        route_gdf=route_gdf,
        start_route_m=float(trail_info.get("trail_start_route_m", np.nan)),
    )
    if named_line is None or named_line.is_empty or named_line.length <= 0:
        return pd.DataFrame()

    osm_length_m = float(named_line.length)
    display_length_m = float(trail_info.get("trail_display_length_m", np.nan))
    display_source = str(trail_info.get("trail_display_length_source", ""))
    if trail_display_length_km is not None and np.isfinite(trail_display_length_km) and float(trail_display_length_km) > 0:
        display_length_m = float(trail_display_length_km) * 1000.0
        display_source = "field_sign_or_argument"
    if not np.isfinite(display_length_m) or display_length_m <= 0:
        display_length_m = osm_length_m
        display_source = "osm_named_highway_geometry"

    total_route_m = route_total_csv_distance_m(route_gdf, route_line)
    if not np.isfinite(total_route_m) or total_route_m <= 0:
        total_route_m = float(route_line.length)

    rows = []
    values = station_label_values_m(display_length_m, step_km)
    for idx, display_rel_m in enumerate(values):
        position_rel_m = (float(display_rel_m) / display_length_m) * osm_length_m
        position_rel_m = max(0.0, min(osm_length_m, float(position_rel_m)))
        pt = named_line.interpolate(position_rel_m)
        route_line_m = float(route_line.project(pt))
        route_m = route_line_m / float(route_line.length) * float(total_route_m)
        is_start = idx == 0
        is_end = idx == len(values) - 1
        rows.append(
            {
                "trail_order": int(trail_order),
                "trail_name": trail_name or str(trail_info.get("trail_name", "named trail") or "named trail"),
                "route_m": route_m,
                "route_km": route_m / 1000.0,
                "display_m": float(display_rel_m),
                "display_km": float(display_rel_m) / 1000.0,
                "station_label": f"{float(display_rel_m) / 1000.0:.1f}k",
                "is_start": bool(is_start),
                "is_end": bool(is_end),
                "is_endpoint": bool(is_start or is_end),
                "display_length_m": float(display_length_m),
                "osm_length_m": float(osm_length_m),
                "display_length_source": display_source,
            }
        )
    return pd.DataFrame(rows)


def collect_profile_trail_markers(
    route_gdf: gpd.GeoDataFrame,
    ia1_output_dir: Path | None,
    case_name: str | None,
    primary_info: dict,
    primary_close_named: gpd.GeoDataFrame,
    primary_name: str | None,
    primary_step_km: float,
    primary_display_length_km: float | None,
    trail2_name: str | None,
    trail2_keywords: str | None,
    trail2_step_km: float | None,
    trail2_display_length_km: float | None,
    match_buffer_m: float,
) -> tuple[pd.DataFrame, dict]:
    frames = []
    trail2_info: dict = {"trail2_stationing_found": False, "trail2_stationing_note": "trail2_not_requested"}

    primary_markers = build_profile_markers_for_named_trail(
        route_gdf=route_gdf,
        close_named=primary_close_named,
        trail_info=primary_info,
        trail_name=primary_name,
        step_km=primary_step_km,
        trail_display_length_km=primary_display_length_km,
        trail_order=1,
    )
    if not primary_markers.empty:
        frames.append(primary_markers)

    if trail2_name or trail2_keywords:
        step2 = float(trail2_step_km) if trail2_step_km is not None else float(primary_step_km)
        info2, close2 = find_named_trail_station_range(
            route_gdf=route_gdf,
            ia1_output_dir=ia1_output_dir,
            trail_name=trail2_name,
            trail_keywords=trail2_keywords,
            case_name=case_name,
            match_buffer_m=match_buffer_m,
        )
        trail2_info = {f"trail2_{k}": v for k, v in info2.items()}
        markers2 = build_profile_markers_for_named_trail(
            route_gdf=route_gdf,
            close_named=close2,
            trail_info=info2,
            trail_name=trail2_name,
            step_km=step2,
            trail_display_length_km=trail2_display_length_km,
            trail_order=2,
        )
        if not markers2.empty:
            frames.append(markers2)
            trail2_info["trail2_profile_marker_count"] = int(len(markers2))
            trail2_info["trail2_display_length_km"] = float(markers2["display_length_m"].iloc[0]) / 1000.0
            trail2_info["trail2_osm_length_km"] = float(markers2["osm_length_m"].iloc[0]) / 1000.0
            trail2_info["trail2_display_length_source"] = str(markers2["display_length_source"].iloc[0])
        else:
            trail2_info["trail2_profile_marker_count"] = 0
    if frames:
        markers = pd.concat(frames, ignore_index=True)
        markers = markers.sort_values(["trail_order", "display_m"]).reset_index(drop=True)
        return markers, trail2_info
    return pd.DataFrame(), trail2_info


def annotate_trail_profile_markers(
    ax,
    markers: pd.DataFrame | None,
    label_all: bool = False,
) -> None:
    """Annotate hazard/elevation profile panels with named-trail station ticks.

    The x-axis stays in GPX distance.  Tick labels show each named trail's own
    stationing so the user can read where high-score sections fall within each
    trail, even when the GPX is out-and-back.
    """
    if markers is None or markers.empty:
        return
    ymin, ymax = ax.get_ylim()
    yrange = ymax - ymin
    if yrange <= 0:
        return
    top = ymax - 0.05 * yrange
    unique_orders = list(dict.fromkeys(markers["trail_order"].astype(int).tolist()))
    for lane_idx, order in enumerate(unique_orders):
        sub = markers[markers["trail_order"].astype(int) == int(order)].copy()
        if sub.empty:
            continue
        color = PROFILE_TRAIL_COLORS[(int(order) - 1) % len(PROFILE_TRAIL_COLORS)]
        x_min = float(sub["route_km"].min())
        x_max = float(sub["route_km"].max())
        ax.axvspan(x_min, x_max, color=color, alpha=0.045, zorder=0)
        lane_y = top - lane_idx * 0.16 * yrange
        name = str(sub["trail_name"].iloc[0])
        if np.isfinite(x_min) and np.isfinite(x_max) and x_max > x_min:
            ax.text(
                (x_min + x_max) / 2.0,
                lane_y + 0.055 * yrange,
                name,
                ha="center",
                va="bottom",
                fontsize=7.0,
                color=color,
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec=color, alpha=0.70),
                zorder=9,
            )
        for _, row in sub.iterrows():
            x = float(row["route_km"])
            if not np.isfinite(x):
                continue
            endpoint = bool(row.get("is_endpoint", False))
            ax.axvline(
                x,
                color=color,
                linestyle="-" if endpoint else ":",
                linewidth=1.05 if endpoint else 0.62,
                alpha=0.82 if endpoint else 0.55,
                zorder=5,
            )
            display_km = float(row["display_km"])
            # Default: draw all vertical ticks but reduce text clutter by labeling
            # endpoints and every 0.4k.  --profile-trail-label-all labels all.
            should_label = bool(label_all or endpoint or np.isclose((display_km * 10) % 4, 0, atol=1e-4))
            if should_label:
                suffix = " 起" if bool(row.get("is_start", False)) else (" 終" if bool(row.get("is_end", False)) else "")
                ax.text(
                    x,
                    lane_y,
                    f"{row['station_label']}{suffix}",
                    rotation=90,
                    ha="center",
                    va="top",
                    fontsize=6.4,
                    color=color,
                    bbox=dict(boxstyle="round,pad=0.07", fc="white", ec=color, alpha=0.72),
                    zorder=10,
                )

def numeric_col(df: pd.DataFrame, col: str, default=0.0) -> pd.Series:
    if col in df.columns:
        source = df[col]
    else:
        source = pd.Series(default, index=df.index)
    return pd.to_numeric(source, errors="coerce").fillna(default)


THCI_AXIS_ORDER_V1_0C = [
    ("physical_difficulty_score", "體力難度"),
    ("technical_difficulty_score", "技術難度"),
    ("baseline_hazard_score", "基礎危害"),
    ("navigation_risk_score", "迷航風險"),
    ("support_difficulty_score", "支援不易"),
    ("weather_impact_score", "天候影響"),
]


def normalize_thci_axis_df(axis_df: pd.DataFrame) -> pd.DataFrame:
    """Normalize THCI axis data to axis_order/axis_id/axis_label_zh/score.

    This intentionally follows THCI v1.0c semantics and does not use the old
    IB2E route-risk fallback axes, so Butterfly Valley can remain comparable
    with the current recommended THCI display version.
    """
    df = axis_df.copy()
    if "axis_id" not in df.columns:
        # Some upstream exports may store axis IDs as a first unnamed column.
        unnamed_cols = [c for c in df.columns if str(c).lower().startswith("unnamed")]
        if unnamed_cols:
            df = df.rename(columns={unnamed_cols[0]: "axis_id"})
    if "score" not in df.columns:
        score_candidates = [
            "axis_score",
            "calibrated_score",
            "score_v1_0c",
            "value",
            "normalized_score",
        ]
        score_col = next((c for c in score_candidates if c in df.columns), None)
        if score_col:
            df = df.rename(columns={score_col: "score"})
    if "axis_label_zh" not in df.columns:
        label_candidates = ["axis_label", "label_zh", "label", "zh_label", "name_zh"]
        label_col = next((c for c in label_candidates if c in df.columns), None)
        if label_col:
            df = df.rename(columns={label_col: "axis_label_zh"})

    if "axis_id" not in df.columns or "score" not in df.columns:
        raise ValueError("THCI axis data must contain axis_id and score columns after normalization.")

    axis_order_map = {axis_id: idx + 1 for idx, (axis_id, _label) in enumerate(THCI_AXIS_ORDER_V1_0C)}
    axis_label_map = dict(THCI_AXIS_ORDER_V1_0C)
    df["axis_id"] = df["axis_id"].astype(str).str.strip()
    df = df[df["axis_id"].isin(axis_order_map)].copy()
    df["axis_order"] = df["axis_id"].map(axis_order_map)
    if "axis_label_zh" not in df.columns:
        df["axis_label_zh"] = df["axis_id"].map(axis_label_map)
    else:
        df["axis_label_zh"] = df["axis_label_zh"].fillna(df["axis_id"].map(axis_label_map))
        df.loc[df["axis_label_zh"].astype(str).str.strip() == "", "axis_label_zh"] = df["axis_id"].map(axis_label_map)
    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    df = df.dropna(subset=["score"])
    df["score"] = df["score"].clip(0, 1)
    df = df.sort_values("axis_order").drop_duplicates("axis_id", keep="first")

    missing = [axis_id for axis_id, _ in THCI_AXIS_ORDER_V1_0C if axis_id not in set(df["axis_id"])]
    if missing:
        raise ValueError(f"THCI v1.0c missing axes: {missing}")
    return df[["axis_order", "axis_id", "axis_label_zh", "score"]].reset_index(drop=True)


def load_thci_axis_from_summary_json(summary_fp: Path) -> pd.DataFrame:
    payload = json.loads(summary_fp.read_text(encoding="utf-8-sig"))
    axis_order = payload.get("axis_order") or []
    axis_scores = payload.get("axis_scores") or {}
    rows = []
    if axis_order:
        for idx, item in enumerate(axis_order, start=1):
            axis_id = str(item.get("axis_id", "")).strip()
            if not axis_id:
                continue
            rows.append(
                {
                    "axis_order": idx,
                    "axis_id": axis_id,
                    "axis_label_zh": item.get("axis_label_zh", axis_id),
                    "score": axis_scores.get(axis_id),
                }
            )
    else:
        for idx, (axis_id, label) in enumerate(THCI_AXIS_ORDER_V1_0C, start=1):
            rows.append(
                {"axis_order": idx, "axis_id": axis_id, "axis_label_zh": label, "score": axis_scores.get(axis_id)}
            )
    return normalize_thci_axis_df(pd.DataFrame(rows))


def load_thci_axis_data(case_id: str, plot_data_arg: str | None, summary_arg: str | None) -> tuple[pd.DataFrame | None, str]:
    candidates_csv = []
    if plot_data_arg:
        resolved = resolve_path(plot_data_arg)
        if resolved is not None:
            candidates_csv.append(resolved)
    candidates_csv.extend([default_thci_plot_data_csv(case_id), default_thci_axis_score_csv(case_id)])
    for fp in candidates_csv:
        if fp.exists():
            try:
                return normalize_thci_axis_df(pd.read_csv(fp, encoding="utf-8-sig")), str(fp)
            except Exception as exc:
                print(f"WARNING: could not use THCI CSV {fp}: {exc}")

    candidates_json = []
    if summary_arg:
        resolved = resolve_path(summary_arg)
        if resolved is not None:
            candidates_json.append(resolved)
    candidates_json.extend([default_thci_summary_json(case_id), default_thci_axis_score_summary_json(case_id)])
    for fp in candidates_json:
        if fp.exists():
            try:
                return load_thci_axis_from_summary_json(fp), str(fp)
            except Exception as exc:
                print(f"WARNING: could not use THCI JSON {fp}: {exc}")
    return None, ""


def write_thci_v1_0c_radar(case_id: str, axis_df: pd.DataFrame, out_radar_png: Path) -> None:
    axis_df = normalize_thci_axis_df(axis_df)
    labels = axis_df["axis_label_zh"].astype(str).tolist()
    values = axis_df["score"].astype(float).tolist()
    angles = np.linspace(0, 2 * np.pi, len(values), endpoint=False).tolist()
    closed_values = values + values[:1]
    closed_angles = angles + angles[:1]

    fig = plt.figure(figsize=(8.6, 8.6), dpi=DPI)
    ax = fig.add_subplot(111, polar=True)
    ax.plot(closed_angles, closed_values, color="#345D8A", linewidth=2.8)
    ax.fill(closed_angles, closed_values, color="#8FA6BD", alpha=0.34)
    ax.scatter(angles, values, s=24, color="#345D8A", zorder=3)
    ax.set_ylim(0, 1.0)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], fontsize=10)
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=16)
    ax.grid(color="#AFC0D0", linewidth=1.0, alpha=0.86)
    ax.spines["polar"].set_color("black")
    ax.spines["polar"].set_linewidth(1.1)

    # Value labels near each vertex. Keep the original v1.0c 0-1 semantics.
    for angle, value in zip(angles, values):
        radius = min(1.04, max(0.12, value + 0.085))
        ax.text(angle, radius, f"{value:.2f}", ha="center", va="center", fontsize=12, color="black")

    ax.set_title(f"THCI v1.0c weather semantics calibrated\n{case_id}", fontsize=19, pad=34)
    fig.tight_layout()
    fig.savefig(out_radar_png, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def write_unavailable_thci_radar(out_radar_png: Path, note: str) -> None:
    fig = plt.figure(figsize=(6.2, 6.2), dpi=DPI)
    ax = fig.add_subplot(111)
    ax.axis("off")
    ax.text(0.5, 0.5, f"THCI v1.0c radar unavailable\n{note}", ha="center", va="center", fontsize=12)
    fig.savefig(out_radar_png, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def make_thci_v1_0c_radar(
    case_id: str,
    thci_radar_arg: str | None,
    thci_plot_data_arg: str | None,
    thci_summary_arg: str | None,
    out_radar_png: Path,
) -> tuple[bool, str, str]:
    # Explicit --thci-radar-png wins. Deprecated --route-radar-png is passed in by main as fallback.
    source = resolve_path(thci_radar_arg) if thci_radar_arg else default_thci_radar_png(case_id)
    if source is not None and source.exists():
        shutil.copy2(source, out_radar_png)
        return True, str(source), "copied_existing_thci_v1_0c_png"

    axis_df, axis_source = load_thci_axis_data(case_id, thci_plot_data_arg, thci_summary_arg)
    if axis_df is not None:
        write_thci_v1_0c_radar(case_id, axis_df, out_radar_png)
        return True, axis_source, "rendered_from_thci_v1_0c_axis_data"

    note = "missing outputs/thci_radar_v1_0c and THCI axis data"
    write_unavailable_thci_radar(out_radar_png, note)
    return False, "", note


def estimate_metric_crs(gdf: gpd.GeoDataFrame):
    try:
        crs = gdf.estimate_utm_crs()
        return crs or "EPSG:3826"
    except Exception:
        return "EPSG:3826"


def geometry_union(geoseries: gpd.GeoSeries):
    union_all = getattr(geoseries, "union_all", None)
    if callable(union_all):
        return union_all()
    return geoseries.unary_union


def subset_to_buffer(gdf: gpd.GeoDataFrame, area) -> gpd.GeoDataFrame:
    if gdf.empty:
        return gdf
    try:
        return gdf[gdf.intersects(area)].copy()
    except Exception:
        return gdf.iloc[0:0].copy()


def iter_line_parts(geom):
    if geom is None or geom.is_empty:
        return
    if geom.geom_type == "LineString":
        yield geom
    elif geom.geom_type == "MultiLineString":
        for part in geom.geoms:
            if part.geom_type == "LineString":
                yield part


def line_segments_and_values(gdf: gpd.GeoDataFrame, value_col: str) -> tuple[list[np.ndarray], np.ndarray]:
    segments: list[np.ndarray] = []
    values: list[float] = []
    for _, row in gdf.iterrows():
        value = pd.to_numeric(row.get(value_col, 0.0), errors="coerce")
        if pd.isna(value):
            value = 0.0
        for line in iter_line_parts(row.geometry):
            coords = np.asarray(line.coords)
            if len(coords) >= 2:
                segments.append(coords[:, :2])
                values.append(float(value))
    return segments, np.asarray(values, dtype=float)


def first_last_xy(gdf: gpd.GeoDataFrame) -> tuple[np.ndarray, np.ndarray]:
    for geom in gdf.geometry:
        for line in iter_line_parts(geom):
            start_xy = np.asarray(line.coords[0])[:2]
            break
        else:
            continue
        break
    else:
        raise ValueError("No valid LineString geometry found for start marker.")

    for geom in reversed(gdf.geometry.tolist()):
        parts = list(iter_line_parts(geom))
        for line in reversed(parts):
            end_xy = np.asarray(line.coords[-1])[:2]
            break
        else:
            continue
        break
    else:
        raise ValueError("No valid LineString geometry found for end marker.")

    return start_xy, end_xy


def score_series(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(np.zeros(len(df), dtype=float), index=df.index)
    return pd.to_numeric(df[col], errors="coerce").fillna(0.0).clip(0, 1)


def require_columns(df: pd.DataFrame, cols: list[str], name: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{name} missing required columns: {missing}")


def first_numeric_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            values = pd.to_numeric(df[col], errors="coerce")
            if values.notna().any():
                return col
    return None


def load_profile_for_elevation(case_id: str, profile_geojson_arg: str | None) -> pd.DataFrame | None:
    profile_geojson = resolve_path(profile_geojson_arg) if profile_geojson_arg else default_profile_geojson(case_id)
    if profile_geojson is None or not profile_geojson.exists():
        return None
    try:
        profile = gpd.read_file(profile_geojson)
    except Exception as exc:
        print(f"WARNING: could not read profile GeoJSON for elevation profile: {profile_geojson} | {exc}")
        return None
    if profile.empty or "dist_m" not in profile.columns:
        return None
    elev_col = first_numeric_col(profile, ELEVATION_COL_CANDIDATES)
    if elev_col is None:
        return None
    out = profile[["dist_m", elev_col]].copy()
    out = out.rename(columns={elev_col: "elevation_profile_m"})
    out["dist_m"] = pd.to_numeric(out["dist_m"], errors="coerce")
    out["elevation_profile_m"] = pd.to_numeric(out["elevation_profile_m"], errors="coerce")
    out = out.dropna().sort_values("dist_m").drop_duplicates("dist_m")
    return out if len(out) >= 2 else None


def attach_elevation_profile(hazard_df: pd.DataFrame, profile_df: pd.DataFrame | None) -> pd.DataFrame:
    out = hazard_df.copy()
    if "dist_mid" in out.columns:
        dist = pd.to_numeric(out["dist_mid"], errors="coerce")
    elif "dist_m" in out.columns:
        dist = pd.to_numeric(out["dist_m"], errors="coerce")
    elif "dist_start" in out.columns and "dist_end" in out.columns:
        dist = (pd.to_numeric(out["dist_start"], errors="coerce") + pd.to_numeric(out["dist_end"], errors="coerce")) / 2.0
    else:
        out["plot_dist_m"] = np.arange(len(out), dtype=float)
        dist = out["plot_dist_m"]
    out["plot_dist_m"] = dist

    hazard_elev_col = first_numeric_col(out, ELEVATION_COL_CANDIDATES)
    if hazard_elev_col is not None:
        out["plot_elevation_m"] = pd.to_numeric(out[hazard_elev_col], errors="coerce")
        return out

    if profile_df is not None and not profile_df.empty:
        valid_dist = dist.notna()
        x = profile_df["dist_m"].to_numpy(dtype=float)
        y = profile_df["elevation_profile_m"].to_numpy(dtype=float)
        out["plot_elevation_m"] = np.nan
        if len(x) >= 2 and valid_dist.any():
            out.loc[valid_dist, "plot_elevation_m"] = np.interp(dist.loc[valid_dist], x, y)
    else:
        out["plot_elevation_m"] = np.nan
    return out


def build_hotspot_table(df: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    require_columns(
        df,
        [
            "dist_start",
            "dist_end",
            "upslope_contributing_hazard_score",
            "max_source_relief_m",
            "max_source_fall_gradient",
            "contributing_source_count",
            "contributing_sector_count",
        ],
        "hazard CSV",
    )
    data = df.copy()
    score_col = "upslope_contributing_hazard_score"
    data[score_col] = pd.to_numeric(data[score_col], errors="coerce").fillna(0.0)
    threshold = max(0.78, float(data[score_col].quantile(0.90)))
    hot = data[data[score_col] >= threshold].copy()
    if hot.empty:
        hot = data.nlargest(min(10, len(data)), score_col).copy()
        threshold = float(hot[score_col].min()) if not hot.empty else 0.0

    groups = []
    current = []
    last_end = None
    for _, row in hot.sort_values("dist_start").iterrows():
        start = float(row["dist_start"])
        end = float(row["dist_end"])
        if last_end is None or start <= last_end + 25.0:
            current.append(row)
        else:
            groups.append(pd.DataFrame(current))
            current = [row]
        last_end = end
    if current:
        groups.append(pd.DataFrame(current))

    rows = []
    for idx, group in enumerate(groups, start=1):
        rows.append(
            {
                "rank": idx,
                "dist_start_m": float(group["dist_start"].min()),
                "dist_end_m": float(group["dist_end"].max()),
                "length_m": float(group["dist_end"].max() - group["dist_start"].min()),
                "mean_score": float(group[score_col].mean()),
                "max_score": float(group[score_col].max()),
                "mean_max_source_relief_m": float(group["max_source_relief_m"].mean()),
                "max_source_relief_m": float(group["max_source_relief_m"].max()),
                "mean_fall_gradient": float(group["max_source_fall_gradient"].mean()),
                "max_fall_gradient": float(group["max_source_fall_gradient"].max()),
                "mean_source_count": float(group["contributing_source_count"].mean()),
                "mean_sector_count": float(group["contributing_sector_count"].mean()),
            }
        )
    table = pd.DataFrame(rows)
    if not table.empty:
        table = table.sort_values(["mean_score", "max_score", "length_m"], ascending=False).reset_index(drop=True)
        table["rank"] = np.arange(1, len(table) + 1)
    return table, threshold


def write_hotspot_markdown(case_name: str, table: pd.DataFrame, threshold: float, out_fp: Path) -> None:
    lines = [
        f"# {case_name} upslope contributing hazard high-score review sections",
        "",
        (
            "This is a relative high-score review-section list from the broad upslope contributing-area proxy. "
            "It uses higher NLSC contour sources up to 1000 m from the trail and does not model "
            "true rockfall physics, DEM aspect, or debris-flow runout."
        ),
        "",
        f"High-score review threshold: score >= {threshold:.3f}",
        "",
    ]
    if table.empty:
        lines.append("No high-score review sections found.")
    else:
        lines.append("| rank | distance km | length m | mean score | max score | max relief m | max fall gradient |")
        lines.append("|---:|---:|---:|---:|---:|---:|---:|")
        for _, row in table.iterrows():
            lines.append(
                "| {rank:.0f} | {start:.2f}-{end:.2f} | {length:.0f} | {mean:.3f} | {maxs:.3f} | {relief:.0f} | {grad:.2f} |".format(
                    rank=row["rank"],
                    start=row["dist_start_m"] / 1000.0,
                    end=row["dist_end_m"] / 1000.0,
                    length=row["length_m"],
                    mean=row["mean_score"],
                    maxs=row["max_score"],
                    relief=row["max_source_relief_m"],
                    grad=row["max_fall_gradient"],
                )
            )
    out_fp.write_text("\n".join(lines) + "\n", encoding="utf-8")


def split_major_minor_contours(contours: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, str | None]:
    if contours.empty:
        return contours, contours, None
    elev_col = first_numeric_col(contours, CONTOUR_ELEV_COL_CANDIDATES)
    if elev_col is None:
        return contours, contours.iloc[0:0].copy(), None
    elev = pd.to_numeric(contours[elev_col], errors="coerce")
    major_mask = elev.notna() & (np.isclose(np.mod(elev, 50), 0) | np.isclose(np.mod(elev, 50), 50))
    major = contours[major_mask].copy()
    minor = contours[~major_mask].copy()
    return minor, major, elev_col


def plot_hazard_score_profile(ax, hazard_df: pd.DataFrame, hotspots: pd.DataFrame, profile_markers: pd.DataFrame | None = None, profile_trail_label_all: bool = False) -> None:
    require_columns(hazard_df, ["plot_dist_m", "dist_end", "upslope_contributing_hazard_score"], "hazard CSV")
    d_km = pd.to_numeric(hazard_df["plot_dist_m"], errors="coerce") / 1000.0
    score = pd.to_numeric(hazard_df["upslope_contributing_hazard_score"], errors="coerce").fillna(0.0)
    valid = d_km.notna() & score.notna()
    d_km = d_km[valid]
    score = score[valid]
    if len(d_km) < 2:
        ax.axis("off")
        ax.text(0.5, 0.5, "Hazard score profile unavailable", ha="center", va="center", transform=ax.transAxes)
        return
    ax.plot(d_km, score, color="#8B1E2D", linewidth=1.7)
    ax.fill_between(d_km, 0.70, score, where=score >= 0.70, color="#F28E2B", alpha=0.22)
    for _, row in hotspots.head(8).iterrows():
        ax.axvspan(row["dist_start_m"] / 1000.0, row["dist_end_m"] / 1000.0, color="#C9252D", alpha=0.20)
    ax.set_ylim(0.68, max(0.86, float(score.max()) + 0.01))
    ax.set_xlim(0, float(pd.to_numeric(hazard_df["dist_end"], errors="coerce").max()) / 1000.0)
    ax.set_xlabel("GPX 里程：自原始軌跡起點起算 (km)")
    ax.set_ylabel("Hazard score")
    ax.set_title("上方坡面貢獻危害 proxy 剖面", fontsize=11, pad=6)
    ax.grid(color="#E6E6E6", linewidth=0.6)
    annotate_trail_profile_markers(ax, profile_markers, label_all=profile_trail_label_all)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def plot_elevation_profile(ax, hazard_df: pd.DataFrame, hotspots: pd.DataFrame, profile_markers: pd.DataFrame | None = None, profile_trail_label_all: bool = False) -> bool:
    if "plot_elevation_m" not in hazard_df.columns or hazard_df["plot_elevation_m"].isna().all():
        ax.axis("off")
        ax.text(
            0.5,
            0.5,
            "Elevation profile unavailable\n(no elevation column in hazard CSV and no usable IB1E profile GeoJSON)",
            ha="center",
            va="center",
            transform=ax.transAxes,
            fontsize=10,
            color="#666666",
        )
        return False

    d_km = pd.to_numeric(hazard_df["plot_dist_m"], errors="coerce") / 1000.0
    elev_m = pd.to_numeric(hazard_df["plot_elevation_m"], errors="coerce")
    score = pd.to_numeric(hazard_df["upslope_contributing_hazard_score"], errors="coerce").fillna(0.0)
    valid = d_km.notna() & elev_m.notna()
    d_km = d_km[valid].reset_index(drop=True)
    elev_m = elev_m[valid].reset_index(drop=True)
    score = score[valid].reset_index(drop=True)
    if len(d_km) < 2:
        ax.axis("off")
        return False

    ymin = float(elev_m.min())
    ymax = float(elev_m.max())
    pad = max(8.0, (ymax - ymin) * 0.08)
    ax.fill_between(d_km, elev_m, ymin - pad, color="#ECEFF1", alpha=0.95, zorder=0)
    ax.plot(d_km, elev_m, color="#78909C", linewidth=1.0, alpha=0.8, zorder=1)

    cmap = LinearSegmentedColormap.from_list("upslope_hazard_profile", ["#F5D76E", "#F28E2B", "#C9252D"])
    norm = Normalize(vmin=0.70, vmax=0.85)
    for i in range(len(d_km) - 1):
        color = cmap(norm(float(score.iloc[i])))
        ax.plot(
            [d_km.iloc[i], d_km.iloc[i + 1]],
            [elev_m.iloc[i], elev_m.iloc[i + 1]],
            color=color,
            linewidth=2.5,
            solid_capstyle="round",
            zorder=2,
        )

    for _, row in hotspots.head(8).iterrows():
        ax.axvspan(row["dist_start_m"] / 1000.0, row["dist_end_m"] / 1000.0, color="#C9252D", alpha=0.12, zorder=0)

    ax.scatter(d_km.iloc[0], elev_m.iloc[0], s=34, c="#2E7D32", edgecolors="white", linewidths=0.7, zorder=4)
    ax.scatter(d_km.iloc[-1], elev_m.iloc[-1], s=34, c="#4A3F35", edgecolors="white", linewidths=0.7, zorder=4)
    ax.set_xlim(float(d_km.min()), float(d_km.max()))
    ax.set_ylim(ymin - pad, ymax + pad)
    ax.set_xlabel("GPX 里程：自原始軌跡起點起算 (km)")
    ax.set_ylabel("高程 (m)")
    ax.set_title("高程剖面圖（線色為 upslope hazard proxy）", fontsize=11, pad=6)
    ax.grid(True, color="#D7DEE2", linewidth=0.7, alpha=0.8)
    annotate_trail_profile_markers(ax, profile_markers, label_all=profile_trail_label_all)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return True




def build_formal_figure_caption(
    case_name: str,
    trail_name: str | None,
    figure_number: str = "圖 X",
    route_context_note: str | None = None,
    proxy_note: str | None = None,
) -> tuple[str, str]:
    """Return a formal figure title and caption body for report use."""
    route_context_note = (route_context_note or "").strip()
    proxy_note = (proxy_note or "").strip()
    trail_phrase = ""
    if trail_name:
        trail_phrase = f"圖中 {trail_name} 以 0.0k–1.4k 標示步道內里程；"
    title = f"{figure_number}　{case_name}路線之上方坡面落石／土石崩落來源區 proxy 圖"
    parts = [
        f"本圖以「{case_name}」GPX 路線為分析對象，疊合 NLSC 等高線、OSM 水系與步道圖資，呈現各路段之上方坡面貢獻危害 proxy 分數。",
    ]
    if route_context_note:
        parts.append(route_context_note)
    if trail_phrase:
        parts.append(f"{trail_phrase}下方剖面圖則以原始 GPX 里程為 X 軸，用於對照危害 proxy 分數與高程變化。")
    else:
        parts.append("下方剖面圖以原始 GPX 里程為 X 軸，用於對照危害 proxy 分數與高程變化。")
    parts.append("紅色區段表示高分複核區，代表該路段落下距離、下落路徑、上方可疑坡面密集度等條件較明顯，建議優先進行人工圖資複核。右下角雷達圖為高分複核區之原因摘要，外圈越大表示該原因越明顯；其中「雨水匯流沖刷敏感」係指高分區鄰近溪溝、水系、凹谷或可能集水線，代表大雨時可能受集中逕流、沖刷、濕滑或坡面鬆動影響。此項為地形與圖資 proxy，非正式水文模擬或災害潛勢判定。")
    if proxy_note:
        parts.append(proxy_note)
    body = "".join(parts)
    return title, body


def write_formal_figure_caption(
    case_name: str,
    trail_name: str | None,
    figure_number: str,
    route_context_note: str | None,
    proxy_note: str | None,
    txt_fp: Path,
    md_fp: Path,
) -> tuple[str, str]:
    """Write formal figure caption to TXT and Markdown files."""
    title, body = build_formal_figure_caption(
        case_name=case_name,
        trail_name=trail_name,
        figure_number=figure_number,
        route_context_note=route_context_note,
        proxy_note=proxy_note,
    )
    txt = f"{title}\n\n{body}\n"
    md = f"**{title}**\n\n{body}\n"
    txt_fp.write_text(txt, encoding="utf-8-sig")
    md_fp.write_text(md, encoding="utf-8-sig")
    return title, body


def build_map_footnote(route_context_note: str | None, proxy_note: str | None) -> str:
    """Short map footnote, kept brief so it remains readable on the figure."""
    route_context_note = (route_context_note or "").strip()
    proxy_note = (proxy_note or DEFAULT_PROXY_NOTE).strip()
    if route_context_note:
        return f"{route_context_note} {proxy_note}"
    return proxy_note


def add_map_footnote(fig, footnote: str | None) -> None:
    if not footnote:
        return
    wrapped = "\n".join(textwrap.wrap(footnote, width=92))
    fig.text(
        0.5,
        0.008,
        wrapped,
        ha="center",
        va="bottom",
        fontsize=8.3,
        color="#333333",
        bbox=dict(boxstyle="round,pad=0.28", fc="white", ec="#D0D0D0", alpha=0.86),
    )

def plot_map(
    case_name: str,
    trail_name: str | None,
    hazard_gdf: gpd.GeoDataFrame,
    hazard_df: pd.DataFrame,
    contours: gpd.GeoDataFrame,
    collapse: gpd.GeoDataFrame,
    watercourse: gpd.GeoDataFrame,
    osm_raw_dir: Path | None,
    ia1_output_dir: Path | None,
    trail_keywords: str | None,
    trail_km_step: float,
    trail_match_buffer_m: float,
    trail_display_length_km: float | None,
    trail2_name: str | None,
    trail2_keywords: str | None,
    trail2_display_length_km: float | None,
    trail2_km_step: float | None,
    profile_trail_label_all: bool,
    route_context_note: str | None,
    proxy_note: str | None,
    show_map_footnote: bool,
    hotspots: pd.DataFrame,
    out_fp: Path,
    elevation_fp: Path,
    km_step: float = 0.5,
) -> tuple[bool, dict[str, int], dict, dict, int]:
    if hazard_gdf.empty:
        raise ValueError("hazard GeoJSON is empty; cannot plot route map.")

    fig = plt.figure(figsize=(15, 12.5), dpi=DPI)
    gs = fig.add_gridspec(3, 1, height_ratios=[5.0, 1.05, 1.22], hspace=0.23)
    ax = fig.add_subplot(gs[0])
    hazard_ax = fig.add_subplot(gs[1])
    elevation_ax = fig.add_subplot(gs[2])

    cmap = LinearSegmentedColormap.from_list("upslope_hazard", ["#F5D76E", "#F28E2B", "#C9252D"])
    norm = Normalize(vmin=0.70, vmax=0.85)

    minor_contours, major_contours, contour_elev_col = split_major_minor_contours(contours)
    if not minor_contours.empty:
        minor_contours.plot(ax=ax, color="#C8C8C8", linewidth=0.35, alpha=0.70, zorder=1)
    if not major_contours.empty:
        major_contours.plot(ax=ax, color="#777777", linewidth=0.78, alpha=0.92, zorder=1)
    elif not contours.empty:
        contours.plot(ax=ax, color="#B7B7B7", linewidth=0.45, alpha=0.75, zorder=1)

    if not collapse.empty:
        collapse.plot(ax=ax, facecolor="#8D5A2B", edgecolor="#5D3218", alpha=0.35, linewidth=0.5, zorder=2)
    if not watercourse.empty:
        watercourse.plot(ax=ax, color="#2D8FCB", linewidth=1.4, alpha=0.85, zorder=3)

    osm_handles, osm_counts = plot_osm_context(ax, osm_raw_dir, hazard_gdf.crs, route_area=geometry_union(hazard_gdf.geometry).buffer(MAP_BUFFER_M))

    segments, values = line_segments_and_values(hazard_gdf, "upslope_contributing_hazard_score")
    if not segments:
        raise ValueError("No valid line segments found in hazard GeoJSON.")
    collection = LineCollection(segments, cmap=cmap, norm=norm, linewidths=5.5, zorder=5, capstyle="round")
    collection.set_array(values)
    ax.add_collection(collection)

    start_xy, end_xy = first_last_xy(hazard_gdf)
    ax.scatter([start_xy[0]], [start_xy[1]], marker="^", s=95, color="#15603A", edgecolor="white", zorder=9, label="start")
    ax.scatter([end_xy[0]], [end_xy[1]], marker="s", s=80, color="#4A3F35", edgecolor="white", zorder=9, label="end")
    # Whole-GPX labels are optional. Named-trail labels below are measured from the IA1-detected trail start.
    add_km_labels(ax, hazard_gdf, step_km=km_step)
    trail_station_info, trail_station_close = add_named_trail_station_labels(
        ax,
        hazard_gdf,
        ia1_output_dir=ia1_output_dir,
        trail_name=trail_name,
        trail_keywords=trail_keywords,
        case_name=case_name,
        step_km=trail_km_step,
        match_buffer_m=trail_match_buffer_m,
        trail_display_length_km=trail_display_length_km,
    )
    profile_trail_markers, trail2_station_info = collect_profile_trail_markers(
        route_gdf=hazard_gdf,
        ia1_output_dir=ia1_output_dir,
        case_name=case_name,
        primary_info=trail_station_info,
        primary_close_named=trail_station_close,
        primary_name=trail_name,
        primary_step_km=trail_km_step,
        primary_display_length_km=trail_display_length_km,
        trail2_name=trail2_name,
        trail2_keywords=trail2_keywords,
        trail2_step_km=trail2_km_step,
        trail2_display_length_km=trail2_display_length_km,
        match_buffer_m=trail_match_buffer_m,
    )
    add_trail_name_label(ax, trail_name, hazard_gdf)

    for _, row in hotspots.head(5).iterrows():
        segs = hazard_gdf[
            (hazard_gdf["dist_start"] >= row["dist_start_m"])
            & (hazard_gdf["dist_end"] <= row["dist_end_m"])
        ]
        if not segs.empty:
            segs.plot(ax=ax, color="#6E0015", linewidth=8.5, alpha=0.55, zorder=6)

    minx, miny, maxx, maxy = hazard_gdf.total_bounds
    padx = max((maxx - minx) * 0.08, 80)
    pady = max((maxy - miny) * 0.08, 80)
    ax.set_xlim(minx - padx, maxx + padx)
    ax.set_ylim(miny - pady, maxy + pady)
    ax.set_aspect("equal", adjustable="box")
    title_suffix = "with NLSC contours"
    if contour_elev_col:
        title_suffix += f" ({contour_elev_col}, major 50 m)"
    ax.set_title(f"{case_name} - upslope rockfall/debris source proxy\n{title_suffix}", fontsize=16, weight="bold")
    ax.set_xlabel("Metric coordinate")
    ax.set_ylabel("Metric coordinate")
    ax.grid(color="#EAEAEA", linewidth=0.6)
    cbar = fig.colorbar(collection, ax=ax, fraction=0.032, pad=0.012)
    cbar.set_label("局部危害 proxy 分數\nLocal hazard proxy score")
    route_handles = [
        Line2D([0], [0], marker="^", color="w", label="start", markerfacecolor="#15603A", markeredgecolor="white", markersize=9, linestyle="None"),
        Line2D([0], [0], marker="s", color="w", label="end", markerfacecolor="#4A3F35", markeredgecolor="white", markersize=8, linestyle="None"),
        Line2D([0], [0], color="#6E0015", lw=5, alpha=0.60, label="高分複核區"),
    ]
    leg1 = ax.legend(handles=route_handles, loc="upper right", frameon=True, fontsize=8)
    if osm_handles:
        ax.add_artist(leg1)
        ax.legend(handles=osm_handles[:12], title="OSM context", loc="lower left", frameon=True, fontsize=6.8, title_fontsize=8)

    plot_hazard_score_profile(hazard_ax, hazard_df, hotspots, profile_trail_markers, profile_trail_label_all)
    elevation_ok = plot_elevation_profile(elevation_ax, hazard_df, hotspots, profile_trail_markers, profile_trail_label_all)

    if show_map_footnote:
        add_map_footnote(fig, build_map_footnote(route_context_note, proxy_note))

    fig.savefig(out_fp, bbox_inches="tight")
    plt.close(fig)

    if elevation_ok:
        fig2 = plt.figure(figsize=(11.5, 4.2), dpi=DPI)
        ax2 = fig2.add_subplot(111)
        plot_elevation_profile(ax2, hazard_df, hotspots, profile_trail_markers, profile_trail_label_all)
        fig2.savefig(elevation_fp, bbox_inches="tight", facecolor="white")
        plt.close(fig2)
    return elevation_ok, osm_counts, trail_station_info, trail2_station_info, int(len(profile_trail_markers))


def segment_length_series(df: pd.DataFrame) -> pd.Series:
    """Return route-segment length in meters for weighted profile/radar summaries."""
    if "dist_start" in df.columns and "dist_end" in df.columns:
        start = pd.to_numeric(df["dist_start"], errors="coerce")
        end = pd.to_numeric(df["dist_end"], errors="coerce")
        length = (end - start).abs()
        return length.replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(lower=0.0)
    return pd.Series(1.0, index=df.index, dtype=float)


def weighted_mean_01(values: pd.Series, weights: pd.Series | None = None) -> float:
    values = pd.to_numeric(values, errors="coerce").clip(0, 1)
    if weights is None:
        return float(values.mean()) if values.notna().any() else 0.0
    weights = pd.to_numeric(weights, errors="coerce").fillna(0.0).clip(lower=0.0)
    valid = values.notna() & weights.gt(0)
    if not valid.any():
        return float(values.mean()) if values.notna().any() else 0.0
    return float(np.average(values.loc[valid], weights=weights.loc[valid]))


def hotspot_rows_for_radar(df: pd.DataFrame, hotspots: pd.DataFrame | None) -> pd.DataFrame:
    """Select rows overlapping high-score review segments for the reason radar.

    The right-bottom radar explains why the red high-score review segment is
    highlighted.  Therefore it should summarize hotspot rows when available,
    rather than averaging the entire out-and-back GPX.
    """
    if hotspots is None or hotspots.empty or "dist_start" not in df.columns or "dist_end" not in df.columns:
        return df.copy()
    start = pd.to_numeric(df["dist_start"], errors="coerce")
    end = pd.to_numeric(df["dist_end"], errors="coerce")
    mask = pd.Series(False, index=df.index)
    for _, hot in hotspots.iterrows():
        h_start = pd.to_numeric(pd.Series([hot.get("dist_start_m")]), errors="coerce").iloc[0]
        h_end = pd.to_numeric(pd.Series([hot.get("dist_end_m")]), errors="coerce").iloc[0]
        if pd.isna(h_start) or pd.isna(h_end):
            continue
        mask = mask | ((end >= float(h_start)) & (start <= float(h_end)))
    selected = df[mask].copy()
    return selected if not selected.empty else df.copy()


UPSLOPE_RADAR_AXIS_METHOD = [
    {
        "label": "落下距離長",
        "basis": "max_source_relief_m",
        "formula": "clip(max_source_relief_m / 500, 0, 1)",
        "zero": "上方複核來源與步道幾乎沒有高差。",
        "hundred": "上方複核來源與步道高差達 500 m 或以上。",
        "limit": "以等高線來源點推估高差，不是落石動能或真實落距模擬。",
    },
    {
        "label": "下落路徑陡直",
        "basis": "max_source_fall_gradient",
        "formula": "clip(max_source_fall_gradient / 1.0, 0, 1)",
        "zero": "來源到步道的坡降比接近 0。",
        "hundred": "來源到步道的坡降比達 1.0 或以上。",
        "limit": "以來源點到步道的直線坡降比近似，未納入坡向、阻擋物或實際滾落路徑。",
    },
    {
        "label": "上方可疑坡面密集",
        "basis": "source_presence_score; fallback contributing_source_count",
        "formula": "source_presence_score if present, else clip(contributing_source_count / 10, 0, 1)",
        "zero": "高分複核區上方幾乎沒有符合條件的可疑來源。",
        "hundred": "高分複核區上方可疑來源非常密集，或來源數達 10 個以上。",
        "limit": "來源密集代表需要複核，不等於每個來源都會崩落。",
    },
    {
        "label": "步道受影響範圍廣",
        "basis": "rank 1 hotspot length_m",
        "formula": "clip(hotspot_length_m / 600, 0, 1)",
        "zero": "高分複核區不是連續路段或長度接近 0。",
        "hundred": "高分複核區連續長度達 600 m 或以上。",
        "limit": "此軸描述高分區沿步道延伸長度，不使用 direction spread / directional concentration。",
    },
    {
        "label": "上方有崩塌地",
        "basis": "collapse_mask_score",
        "formula": "collapse_mask_score",
        "zero": "高分複核區上方或附近未命中既有崩塌遮罩 proxy。",
        "hundred": "高分複核區上方或附近與既有崩塌遮罩 proxy 強烈重疊。",
        "limit": "NLSC 崩塌遮罩是靜態圖資 proxy，不是即時崩塌或正式崩塌潛勢判定。",
    },
    {
        "label": "雨水匯流沖刷敏感",
        "basis": "watercourse_channel_score",
        "formula": "watercourse_channel_score",
        "zero": "高分複核區附近未命中水系或溪溝 proxy。",
        "hundred": "高分複核區鄰近水系、溪溝或集水線 proxy，雨天可能較敏感。",
        "limit": "目前為靜態地形與圖資 proxy，不含活動當日雨勢加權，也不是正式水文模擬。",
    },
]


def radar_hotspot_used(hotspots: pd.DataFrame | None) -> tuple[pd.DataFrame | None, str, float]:
    if hotspots is None or hotspots.empty:
        return None, "no_hotspot_found_used_selected_rows_fallback", 0.0
    table = hotspots.sort_values(["rank"]).head(1).copy() if "rank" in hotspots.columns else hotspots.head(1).copy()
    row = table.iloc[0]
    start = float(pd.to_numeric(pd.Series([row.get("dist_start_m")]), errors="coerce").fillna(0.0).iloc[0])
    end = float(pd.to_numeric(pd.Series([row.get("dist_end_m")]), errors="coerce").fillna(start).iloc[0])
    length = float(pd.to_numeric(pd.Series([row.get("length_m")]), errors="coerce").fillna(max(end - start, 0.0)).iloc[0])
    rank = row.get("rank", 1)
    desc = f"rank {rank} hotspot, {start:.1f}-{end:.1f} m, length {length:.1f} m"
    return table, desc, length


def suspect_slope_axis_score(radar_df: pd.DataFrame) -> pd.Series:
    if "source_presence_score" in radar_df.columns:
        return score_series(radar_df, "source_presence_score")
    if "contributing_source_count" in radar_df.columns:
        return np.clip(pd.to_numeric(radar_df["contributing_source_count"], errors="coerce") / 10.0, 0, 1)
    return pd.Series(0.0, index=radar_df.index, dtype=float)


def compute_upslope_radar_metrics(df: pd.DataFrame, hotspots: pd.DataFrame | None) -> dict:
    require_columns(df, ["max_source_relief_m", "max_source_fall_gradient"], "hazard CSV")
    hotspot_for_radar, hotspot_used, hotspot_length_m = radar_hotspot_used(hotspots)
    radar_df = hotspot_rows_for_radar(df, hotspot_for_radar)
    weights = segment_length_series(radar_df)

    relief_score = np.clip(pd.to_numeric(radar_df["max_source_relief_m"], errors="coerce") / 500.0, 0, 1)
    fall_gradient_score = np.clip(pd.to_numeric(radar_df["max_source_fall_gradient"], errors="coerce") / 1.0, 0, 1)
    suspect_slope_score = suspect_slope_axis_score(radar_df)
    collapse_score = score_series(radar_df, "collapse_mask_score")
    watercourse_score = score_series(radar_df, "watercourse_channel_score")
    if hotspot_length_m <= 0:
        hotspot_length_m = float(weights.sum())
    affected_trail_score = float(np.clip(hotspot_length_m / 600.0, 0, 1))

    labels = [item["label"] for item in UPSLOPE_RADAR_AXIS_METHOD]
    scores = [
        weighted_mean_01(relief_score, weights),
        weighted_mean_01(fall_gradient_score, weights),
        weighted_mean_01(suspect_slope_score, weights),
        affected_trail_score,
        weighted_mean_01(collapse_score, weights),
        weighted_mean_01(watercourse_score, weights),
    ]
    return {
        "labels": labels,
        "scores": [float(np.clip(v, 0, 1)) for v in scores],
        "basis": [f"{item['basis']} | {item['formula']}" for item in UPSLOPE_RADAR_AXIS_METHOD],
        "hotspot_used_for_radar": hotspot_used,
        "hotspot_length_m": float(hotspot_length_m),
        "row_count": int(len(radar_df)),
        "rainwash_axis_note": "目前為靜態地形與圖資 proxy，以 watercourse_channel_score 表示；不含活動當日雨勢加權，也不是正式水文模擬。",
    }


def write_upslope_radar_axis_method(out_fp: Path) -> None:
    lines = [
        "# Upslope high-score review radar axis method",
        "",
        "右下角雷達圖聚焦 rank 1 高分複核區，而不是整條 GPX 平均。各軸先在 segment 層級算 0-1，再以 segment 長度加權平均；圖面顯示為 0-100。",
        "",
        "雨水匯流沖刷敏感目前為靜態地形與圖資 proxy，不含活動當日雨勢加權，也不是正式水文模擬。",
        "",
    ]
    for idx, item in enumerate(UPSLOPE_RADAR_AXIS_METHOD, start=1):
        lines.extend(
            [
                f"## {idx}. {item['label']}",
                "",
                f"- 資料欄位：{item['basis']}",
                f"- 公式：{item['formula']}",
                f"- 0 分意義：{item['zero']}",
                f"- 100 分意義：{item['hundred']}",
                f"- 限制：{item['limit']}",
                "",
            ]
        )
    lines.extend(
        [
            "## V2 terrain-derived flowline / flow accumulation proxy proposal",
            "",
            "可行方向：以 NLSC 等高線建立局部 DEM/TIN 或 raster surface，從坡面梯度推估 D8/D-infinity flow direction，再計算 flow accumulation、凹谷線與步道交會或近距離關係；同時用 NLSC watercourse / OSM waterway 作為校正與驗證層。",
            "",
            "所需資料：足夠密度且拓樸合理的等高線、可靠的水系線、研究區邊界外擴 buffer、必要時補入 DEM 或 LiDAR-derived DEM 以避免等高線內插造成假谷線。",
            "",
            "主要風險：等高線內插 DEM 可能產生平坦區與假洼地；沒有降雨資料時只能描述地形集水敏感度；flow accumulation 對解析度、填洼、外擴範圍非常敏感，若直接併入主分數容易過度精確化。",
            "",
        ]
    )
    out_fp.write_text("\n".join(lines), encoding="utf-8")


def plot_radar(case_name: str, df: pd.DataFrame, hotspots: pd.DataFrame | None, out_fp: Path) -> dict:
    radar_info = compute_upslope_radar_metrics(df, hotspots)
    labels = [
        "\u843d\u4e0b\u8ddd\u96e2\u9577",
        "\u4e0b\u843d\u8def\u5f91\n\u9661\u76f4",
        "\u4e0a\u65b9\u53ef\u7591\n\u5761\u9762\u5bc6\u96c6",
        "\u6b65\u9053\u53d7\u5f71\u97ff\n\u7bc4\u570d\u5ee3",
        "\u4e0a\u65b9\u6709\n\u5d29\u584c\u5730",
        "\u96e8\u6c34\u532f\u6d41\n\u6c96\u5237\u654f\u611f",
    ]
    values = radar_info["scores"]
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    values_closed = values + values[:1]
    angles_closed = angles + angles[:1]

    fig = plt.figure(figsize=(7.8, 7.8), dpi=DPI)
    ax = fig.add_subplot(111, polar=True)
    ax.plot(angles_closed, values_closed, color="#9F1D35", linewidth=2.2)
    ax.fill(angles_closed, values_closed, color="#D94854", alpha=0.25)
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["25", "50", "75", "100"], fontsize=9)
    ax.set_ylim(0, 1)
    title = "\u9ad8\u5206\u8907\u6838\u539f\u56e0\n\u5916\u5708\u8d8a\u5927\uff1d\u539f\u56e0\u8d8a\u660e\u986f"
    ax.set_title(f"{case_name}\n{title}", fontsize=14, weight="bold", pad=24)
    ax.grid(color="#D8D8D8")
    fig.savefig(out_fp, bbox_inches="tight")
    plt.close(fig)
    return radar_info

def combine_images(map_fp: Path, radar_fp: Path, out_fp: Path) -> None:
    map_img = Image.open(map_fp).convert("RGB")
    radar_img = Image.open(radar_fp).convert("RGB")
    radar_img = ImageOps.contain(radar_img, (int(map_img.width * 0.34), int(map_img.height * 0.52)))

    pad = 34
    canvas = Image.new("RGB", (map_img.width + radar_img.width + pad * 3, map_img.height + pad * 2), "white")
    canvas.paste(map_img, (pad, pad))
    x = map_img.width + pad * 2
    y = pad + (map_img.height - radar_img.height) // 2
    canvas.paste(radar_img, (x, y))
    canvas.save(out_fp)


def combine_images_stacked_radars(map_fp: Path, radar_fps: list[Path], out_fp: Path) -> None:
    map_img = Image.open(map_fp).convert("RGB")
    radar_imgs = [Image.open(fp).convert("RGB") for fp in radar_fps if fp.exists()]
    if not radar_imgs:
        return
    pad = 34
    target_w = int(map_img.width * 0.31)
    max_each_h = int((map_img.height - pad * (len(radar_imgs) - 1)) / max(len(radar_imgs), 1))
    resized = [ImageOps.contain(img, (target_w, max_each_h)) for img in radar_imgs]
    right_w = max(img.width for img in resized)
    right_h = sum(img.height for img in resized) + pad * (len(resized) - 1)
    canvas = Image.new("RGB", (map_img.width + right_w + pad * 3, max(map_img.height, right_h) + pad * 2), "white")
    canvas.paste(map_img, (pad, (canvas.height - map_img.height) // 2))
    x = map_img.width + pad * 2
    y = (canvas.height - right_h) // 2
    for img in resized:
        box = ImageOps.expand(img, border=1, fill="#D9E1E5")
        canvas.paste(box, (x + (right_w - box.width) // 2, y))
        y += box.height + pad
    canvas.save(out_fp)


def main() -> None:
    args = parse_args()
    case_id = args.case_id
    if (
        case_id == "taichung_guguan_butterfly_valley_waterfall_20260630"
        and args.trail_display_length_km is None
    ):
        args.trail_display_length_km = 1.6
    case_name = args.case_name or case_id
    hazard_csv = resolve_path(args.hazard_csv) if args.hazard_csv else default_hazard_csv(case_id)
    hazard_geojson = resolve_path(args.hazard_geojson) if args.hazard_geojson else default_hazard_geojson(case_id)
    out_dir = resolve_path(args.out_dir) if args.out_dir else default_out_dir(case_id)
    osm_raw_dir = resolve_path(args.osm_raw_dir) if args.osm_raw_dir else default_osm_raw_dir(case_id)
    ia1_output_dir = resolve_path(args.ia1_output_dir) if args.ia1_output_dir else osm_raw_dir
    risk_csv = resolve_path(args.risk_csv) if args.risk_csv else default_risk_csv(case_id)
    trail_name = args.trail_name or case_name
    assert hazard_csv is not None
    assert hazard_geojson is not None
    assert out_dir is not None
    out_dir.mkdir(parents=True, exist_ok=True)

    if not hazard_csv.exists():
        raise FileNotFoundError(f"hazard CSV not found: {hazard_csv}")
    if not hazard_geojson.exists():
        raise FileNotFoundError(f"hazard GeoJSON not found: {hazard_geojson}")

    df = pd.read_csv(hazard_csv)
    profile_df = load_profile_for_elevation(case_id, args.profile_geojson)
    df = attach_elevation_profile(df, profile_df)

    gdf = gpd.read_file(hazard_geojson)
    if gdf.empty:
        raise ValueError(f"hazard GeoJSON is empty: {hazard_geojson}")
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    metric_crs = estimate_metric_crs(gdf)
    gdf_m = gdf.to_crs(metric_crs)
    route_area = geometry_union(gdf_m.geometry).buffer(MAP_BUFFER_M)

    contour_fp = resolve_path(args.contour_fp) if args.contour_fp else first_present_path(df, "contour_fp")
    collapse_fp = resolve_path(args.collapse_mask_fp) if args.collapse_mask_fp else first_present_path(df, "collapse_mask_fp")
    watercourse_fp = resolve_path(args.watercourse_fp) if args.watercourse_fp else first_present_path(df, "watercourse_fp")

    contours = subset_to_buffer(read_optional_layer(contour_fp, metric_crs), route_area)
    collapse = subset_to_buffer(read_optional_layer(collapse_fp, metric_crs), route_area)
    watercourse = subset_to_buffer(read_optional_layer(watercourse_fp, metric_crs), route_area)

    hotspots, threshold = build_hotspot_table(df)
    hotspot_csv = out_dir / f"{case_id}_upslope_contributing_hazard_hotspots.csv"
    hotspot_md = out_dir / f"{case_id}_upslope_contributing_hazard_hotspots.md"
    hotspots.to_csv(hotspot_csv, index=False, encoding="utf-8-sig")
    write_hotspot_markdown(case_name, hotspots, threshold, hotspot_md)

    map_fp = out_dir / f"{case_id}_upslope_contributing_hazard_map.png"
    radar_fp = out_dir / f"{case_id}_upslope_contributing_hazard_radar.png"
    thci_radar_fp = out_dir / f"{case_id}_thci_radar_v1_0c.png"
    combined_fp = out_dir / f"{case_id}_upslope_contributing_hazard_map_with_radar.png"
    combined_thci_radar_fp = out_dir / f"{case_id}_upslope_contributing_hazard_map_with_thci_v1_0c_radar.png"
    combined_both_radars_fp = out_dir / f"{case_id}_upslope_contributing_hazard_map_with_thci_and_upslope_radars.png"
    elevation_fp = out_dir / f"{case_id}_upslope_contributing_hazard_elevation_profile.png"
    caption_txt_fp = out_dir / f"{case_id}_upslope_contributing_hazard_figure_caption.txt"
    caption_md_fp = out_dir / f"{case_id}_upslope_contributing_hazard_figure_caption.md"

    elevation_profile_ok, osm_counts, trail_station_info, trail2_station_info, profile_trail_marker_count = plot_map(
        case_name,
        trail_name,
        gdf_m,
        df,
        contours,
        collapse,
        watercourse,
        osm_raw_dir,
        ia1_output_dir,
        args.trail_keywords,
        args.trail_km_step,
        args.trail_match_buffer_m,
        args.trail_display_length_km,
        args.trail2_name,
        args.trail2_keywords,
        args.trail2_display_length_km,
        args.trail2_km_step,
        bool(args.profile_trail_label_all),
        args.route_context_note,
        args.proxy_note,
        not bool(args.no_map_footnote),
        hotspots,
        map_fp,
        elevation_fp,
        km_step=args.km_step,
    )
    radar_info = plot_radar(case_name, df, hotspots, radar_fp)
    radar_method_md_fp = out_dir / f"{case_id}_upslope_radar_axis_method.md"
    write_upslope_radar_axis_method(radar_method_md_fp)
    thci_radar_arg = args.thci_radar_png or args.route_radar_png
    thci_radar_ok, thci_radar_source, thci_radar_note = make_thci_v1_0c_radar(
        case_id,
        thci_radar_arg,
        args.thci_plot_data_csv,
        args.thci_summary_json,
        thci_radar_fp,
    )
    combine_images(map_fp, radar_fp, combined_fp)
    combine_images(map_fp, thci_radar_fp, combined_thci_radar_fp)
    combine_images_stacked_radars(map_fp, [thci_radar_fp, radar_fp], combined_both_radars_fp)

    figure_caption_title, figure_caption_body = write_formal_figure_caption(
        case_name=case_name,
        trail_name=trail_name,
        figure_number=args.figure_number,
        route_context_note=args.route_context_note,
        proxy_note=args.proxy_note,
        txt_fp=caption_txt_fp,
        md_fp=caption_md_fp,
    )
    if args.trail_display_length_km is not None and np.isfinite(args.trail_display_length_km):
        display_range = f"0.0k–{float(args.trail_display_length_km):.1f}k"
        figure_caption_body = figure_caption_body.replace("0.0k–1.4k", display_range)
        for caption_fp in [caption_txt_fp, caption_md_fp]:
            if caption_fp.exists():
                caption_fp.write_text(
                    caption_fp.read_text(encoding="utf-8").replace("0.0k–1.4k", display_range),
                    encoding="utf-8",
                )

    score = pd.to_numeric(df["upslope_contributing_hazard_score"], errors="coerce")
    summary = {
        "case_id": case_id,
        "case_name": case_name,
        "project_root": str(PROJECT_ROOT),
        "metric_crs": str(metric_crs),
        "rows": int(len(df)),
        "score_min": float(score.min()),
        "score_mean": float(score.mean()),
        "score_max": float(score.max()),
        "hotspot_threshold": threshold,
        "hotspot_count": int(len(hotspots)),
        "contour_fp": str(contour_fp) if contour_fp else "",
        "contour_features_within_buffer": int(len(contours)),
        "collapse_mask_features_within_buffer": int(len(collapse)),
        "watercourse_features_within_buffer": int(len(watercourse)),
        "osm_raw_dir": str(osm_raw_dir) if osm_raw_dir else "",
        "ia1_output_dir": str(ia1_output_dir) if ia1_output_dir else "",
        "osm_features_within_buffer_total": int(sum(osm_counts.values())) if 'osm_counts' in locals() else 0,
        "trail_stationing_found": bool(trail_station_info.get("trail_stationing_found", False)) if 'trail_station_info' in locals() else False,
        "trail_stationing_note": trail_station_info.get("trail_stationing_note", "") if 'trail_station_info' in locals() else "",
        "trail_stationing_method": trail_station_info.get("trail_stationing_method", "") if 'trail_station_info' in locals() else "",
        "trail_match_run_count": int(trail_station_info.get("trail_match_run_count", 0)) if 'trail_station_info' in locals() else 0,
        "trail_match_run_index": int(trail_station_info.get("trail_match_run_index", 0)) if 'trail_station_info' in locals() else 0,
        "trail_match_run_segment_count": int(trail_station_info.get("trail_match_run_segment_count", 0)) if 'trail_station_info' in locals() else 0,
        "trail_match_run_mean_dist_to_named_m": float(trail_station_info.get("trail_match_run_mean_dist_to_named_m", np.nan)) if 'trail_station_info' in locals() else np.nan,
        "trail_keywords": trail_station_info.get("trail_keywords", "") if 'trail_station_info' in locals() else "",
        "trail_highway_match_count": int(trail_station_info.get("trail_highway_match_count", 0)) if 'trail_station_info' in locals() else 0,
        "trail_highway_close_match_count": int(trail_station_info.get("trail_highway_close_match_count", 0)) if 'trail_station_info' in locals() else 0,
        "trail_start_route_km": float(trail_station_info.get("trail_start_route_m", np.nan)) / 1000.0 if 'trail_station_info' in locals() else np.nan,
        "trail_end_route_km": float(trail_station_info.get("trail_end_route_m", np.nan)) / 1000.0 if 'trail_station_info' in locals() else np.nan,
        "trail_length_km": float(trail_station_info.get("trail_length_m", np.nan)) / 1000.0 if 'trail_station_info' in locals() else np.nan,
        "trail_osm_length_km": float(trail_station_info.get("trail_osm_length_m", np.nan)) / 1000.0 if 'trail_station_info' in locals() else np.nan,
        "trail_display_length_km": float(trail_station_info.get("trail_display_length_m", np.nan)) / 1000.0 if 'trail_station_info' in locals() else np.nan,
        "trail_display_length_source": trail_station_info.get("trail_display_length_source", "") if 'trail_station_info' in locals() else "",
        "trail_station_step_km": float(args.trail_km_step),
        "profile_trail_marker_count": int(profile_trail_marker_count) if 'profile_trail_marker_count' in locals() else 0,
        "profile_trail_label_all": bool(args.profile_trail_label_all),
        "trail2_name": str(args.trail2_name or ""),
        "trail2_keywords": str(args.trail2_keywords or ""),
        "trail2_stationing_found": bool(trail2_station_info.get("trail2_trail_stationing_found", False)) if 'trail2_station_info' in locals() else False,
        "trail2_stationing_note": trail2_station_info.get("trail2_trail_stationing_note", "") if 'trail2_station_info' in locals() else "",
        "trail2_stationing_method": trail2_station_info.get("trail2_trail_stationing_method", "") if 'trail2_station_info' in locals() else "",
        "trail2_profile_marker_count": int(trail2_station_info.get("trail2_profile_marker_count", 0)) if 'trail2_station_info' in locals() else 0,
        "trail2_display_length_km": float(trail2_station_info.get("trail2_display_length_km", np.nan)) if 'trail2_station_info' in locals() else np.nan,
        "trail2_osm_length_km": float(trail2_station_info.get("trail2_osm_length_km", np.nan)) if 'trail2_station_info' in locals() else np.nan,
        "trail2_display_length_source": trail2_station_info.get("trail2_display_length_source", "") if 'trail2_station_info' in locals() else "",
        "ia1_highway_geojson": trail_station_info.get("ia1_highway_geojson", "") if 'trail_station_info' in locals() else "",
        "elevation_profile_ok": bool(elevation_profile_ok),
        "profile_geojson_used": str(default_profile_geojson(case_id)) if args.profile_geojson is None else str(resolve_path(args.profile_geojson)),
        "figure_caption_title": figure_caption_title,
        "figure_caption_body": figure_caption_body,
        "figure_caption_txt": str(caption_txt_fp),
        "figure_caption_md": str(caption_md_fp),
        "route_context_note": str(args.route_context_note or ""),
        "proxy_note": str(args.proxy_note or ""),
        "upslope_radar_axis_labels": json.dumps(radar_info["labels"], ensure_ascii=False),
        "upslope_radar_axis_scores": json.dumps(radar_info["scores"], ensure_ascii=False),
        "upslope_radar_axis_score_basis": json.dumps(radar_info["basis"], ensure_ascii=False),
        "hotspot_used_for_radar": radar_info["hotspot_used_for_radar"],
        "hotspot_length_m": radar_info["hotspot_length_m"],
        "rainwash_axis_note": radar_info["rainwash_axis_note"],
        "upslope_radar_axis_method_md": str(radar_method_md_fp),
        "map_footnote_enabled": not bool(args.no_map_footnote),
        "map_png": str(map_fp),
        "upslope_radar_png": str(radar_fp),
        "thci_radar_v1_0c_png": str(thci_radar_fp),
        "thci_radar_v1_0c_ok": bool(thci_radar_ok),
        "thci_radar_v1_0c_source": thci_radar_source,
        "thci_radar_v1_0c_note": thci_radar_note,
        "combined_png": str(combined_fp),
        "combined_thci_v1_0c_radar_png": str(combined_thci_radar_fp),
        "combined_both_radars_png": str(combined_both_radars_fp),
        "elevation_profile_png": str(elevation_fp) if elevation_profile_ok else "",
        "hotspot_csv": str(hotspot_csv),
        "hotspot_md": str(hotspot_md),
    }
    pd.DataFrame([summary]).to_csv(
        out_dir / f"{case_id}_upslope_contributing_hazard_map_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print("DONE")
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
