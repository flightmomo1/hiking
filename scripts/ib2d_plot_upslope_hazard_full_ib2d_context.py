# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import shutil
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
from shapely.geometry import LineString

DPI = 150
MAP_BUFFER_M = 1000.0


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
        description="Plot upslope contributing-area hazard proxy map with NLSC contours, hazard profile, elevation profile, and radar."
    )
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--case-name", default=None)
    parser.add_argument("--hazard-csv", default=None)
    parser.add_argument("--hazard-geojson", default=None)
    parser.add_argument("--profile-geojson", default=None)
    parser.add_argument("--risk-csv", default=None, help="Route risk CSV for the original route-risk radar fallback.")
    parser.add_argument("--osm-raw-dir", default=None, help="Defaults to osm_raw_output/<case-id>.")
    parser.add_argument("--route-radar-png", default=None, help="Existing route challenge radar PNG. Defaults to outputs/ib2e_route_challenge_index/<case-id>/<case-id>_route_challenge_radar.png when present.")
    parser.add_argument("--trail-name", default=None, help="Trail label shown on the map. Defaults to case-name.")
    parser.add_argument("--km-step", type=float, default=0.5, help="Distance label interval in km. Use 0 to disable.")
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


def default_route_radar_source(case_id: str) -> Path:
    return PROJECT_ROOT / "outputs" / "ib2e_route_challenge_index" / case_id / f"{case_id}_route_challenge_radar.png"


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


def numeric_col(df: pd.DataFrame, col: str, default=0.0) -> pd.Series:
    if col in df.columns:
        source = df[col]
    else:
        source = pd.Series(default, index=df.index)
    return pd.to_numeric(source, errors="coerce").fillna(default)


def radar_mean_score(df: pd.DataFrame, candidates: list[str]) -> float:
    for col in candidates:
        if col in df.columns:
            return float(numeric_col(df, col, 0.0).clip(0, 1).mean() * 100.0)
    return 0.0


def write_fallback_route_risk_radar(risk_df: pd.DataFrame, case_name: str, out_radar_png: Path) -> None:
    values = [radar_mean_score(risk_df, cols) for _, cols in ROUTE_RISK_RADAR_AXES]
    labels = [f"{label}\n{value:.0f}" for (label, _), value in zip(ROUTE_RISK_RADAR_AXES, values)]
    angles = np.linspace(0, 2 * np.pi, len(values), endpoint=False).tolist()
    plot_values = values + values[:1]
    plot_angles = angles + angles[:1]

    fig = plt.figure(figsize=(6.2, 6.2), dpi=DPI)
    ax = fig.add_subplot(111, polar=True)
    ax.plot(plot_angles, plot_values, color="#1565C0", linewidth=2.2)
    ax.fill(plot_angles, plot_values, color="#64B5F6", alpha=0.28)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=8)
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=10)
    ax.grid(color="#B0BEC5", linewidth=0.8)
    ax.set_title(f"{case_name}\n六軸路線風險雷達圖", fontsize=13, pad=24)
    fig.tight_layout()
    fig.savefig(out_radar_png, facecolor="white")
    plt.close(fig)


def make_route_risk_radar(case_id: str, case_name: str, risk_csv: Path | None, route_radar_arg: str | None, out_radar_png: Path) -> tuple[bool, str]:
    source = resolve_path(route_radar_arg) if route_radar_arg else default_route_radar_source(case_id)
    if source is not None and source.exists():
        shutil.copy2(source, out_radar_png)
        return True, str(source)

    risk_csv = risk_csv if risk_csv is not None else default_risk_csv(case_id)
    if risk_csv.exists():
        risk_df = pd.read_csv(risk_csv, low_memory=False, encoding="utf-8-sig")
        write_fallback_route_risk_radar(risk_df, case_name, out_radar_png)
        return True, str(risk_csv)

    fig = plt.figure(figsize=(6.2, 6.2), dpi=DPI)
    ax = fig.add_subplot(111)
    ax.axis("off")
    ax.text(0.5, 0.5, "Route risk radar unavailable\n(no ib2e radar PNG or risk CSV)", ha="center", va="center", fontsize=12)
    fig.savefig(out_radar_png, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return False, ""

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
        f"# {case_name} upslope contributing hazard hotspots",
        "",
        (
            "This is a relative hotspot list from the broad upslope contributing-area proxy. "
            "It uses higher NLSC contour sources up to 1000 m from the trail and does not model "
            "true rockfall physics, DEM aspect, or debris-flow runout."
        ),
        "",
        f"Hotspot threshold: score >= {threshold:.3f}",
        "",
    ]
    if table.empty:
        lines.append("No hotspot sections found.")
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


def plot_hazard_score_profile(ax, hazard_df: pd.DataFrame, hotspots: pd.DataFrame) -> None:
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
    ax.set_xlabel("Distance from trailhead (km)")
    ax.set_ylabel("Hazard score")
    ax.set_title("上方坡面貢獻危害 proxy 剖面", fontsize=11, pad=6)
    ax.grid(color="#E6E6E6", linewidth=0.6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def plot_elevation_profile(ax, hazard_df: pd.DataFrame, hotspots: pd.DataFrame) -> bool:
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
    ax.set_xlabel("距離 (km)")
    ax.set_ylabel("高程 (m)")
    ax.set_title("高程剖面圖（線色為 upslope hazard proxy）", fontsize=11, pad=6)
    ax.grid(True, color="#D7DEE2", linewidth=0.7, alpha=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return True


def plot_map(
    case_name: str,
    trail_name: str | None,
    hazard_gdf: gpd.GeoDataFrame,
    hazard_df: pd.DataFrame,
    contours: gpd.GeoDataFrame,
    collapse: gpd.GeoDataFrame,
    watercourse: gpd.GeoDataFrame,
    osm_raw_dir: Path | None,
    hotspots: pd.DataFrame,
    out_fp: Path,
    elevation_fp: Path,
    km_step: float = 0.5,
) -> tuple[bool, dict[str, int]]:
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
    add_trail_name_label(ax, trail_name, hazard_gdf)
    add_km_labels(ax, hazard_gdf, step_km=km_step)

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
    cbar.set_label("Hazard proxy score")
    route_handles = [
        Line2D([0], [0], marker="^", color="w", label="start", markerfacecolor="#15603A", markeredgecolor="white", markersize=9, linestyle="None"),
        Line2D([0], [0], marker="s", color="w", label="end", markerfacecolor="#4A3F35", markeredgecolor="white", markersize=8, linestyle="None"),
        Line2D([0], [0], color="#6E0015", lw=5, alpha=0.60, label="hotspot"),
    ]
    leg1 = ax.legend(handles=route_handles, loc="upper right", frameon=True, fontsize=8)
    if osm_handles:
        ax.add_artist(leg1)
        ax.legend(handles=osm_handles[:12], title="OSM context", loc="lower left", frameon=True, fontsize=6.8, title_fontsize=8)

    plot_hazard_score_profile(hazard_ax, hazard_df, hotspots)
    elevation_ok = plot_elevation_profile(elevation_ax, hazard_df, hotspots)

    fig.savefig(out_fp, bbox_inches="tight")
    plt.close(fig)

    if elevation_ok:
        fig2 = plt.figure(figsize=(11.5, 4.2), dpi=DPI)
        ax2 = fig2.add_subplot(111)
        plot_elevation_profile(ax2, hazard_df, hotspots)
        fig2.savefig(elevation_fp, bbox_inches="tight", facecolor="white")
        plt.close(fig2)
    return elevation_ok, osm_counts


def plot_radar(case_name: str, df: pd.DataFrame, out_fp: Path) -> None:
    require_columns(df, ["max_source_relief_m", "max_source_fall_gradient"], "hazard CSV")
    metrics = [
        ("Higher relief", np.clip(pd.to_numeric(df["max_source_relief_m"], errors="coerce") / 500.0, 0, 1).mean()),
        ("Fall gradient", np.clip(pd.to_numeric(df["max_source_fall_gradient"], errors="coerce") / 1.0, 0, 1).mean()),
        ("Source density", score_series(df, "source_presence_score").mean()),
        ("Direction spread", score_series(df, "directional_concentration_score").mean()),
        ("Collapse mask", score_series(df, "collapse_mask_score").mean()),
        ("Water channel", score_series(df, "watercourse_channel_score").mean()),
    ]
    labels = [m[0] for m in metrics]
    values = [float(m[1]) for m in metrics]
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
    ax.set_title(f"{case_name}\nIB2D-style radar: upslope hazard factors", fontsize=14, weight="bold", pad=24)
    ax.grid(color="#D8D8D8")
    fig.savefig(out_fp, bbox_inches="tight")
    plt.close(fig)


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
    case_name = args.case_name or case_id
    hazard_csv = resolve_path(args.hazard_csv) if args.hazard_csv else default_hazard_csv(case_id)
    hazard_geojson = resolve_path(args.hazard_geojson) if args.hazard_geojson else default_hazard_geojson(case_id)
    out_dir = resolve_path(args.out_dir) if args.out_dir else default_out_dir(case_id)
    osm_raw_dir = resolve_path(args.osm_raw_dir) if args.osm_raw_dir else default_osm_raw_dir(case_id)
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
    route_radar_fp = out_dir / f"{case_id}_route_challenge_radar.png"
    combined_fp = out_dir / f"{case_id}_upslope_contributing_hazard_map_with_radar.png"
    combined_route_radar_fp = out_dir / f"{case_id}_upslope_contributing_hazard_map_with_route_risk_radar.png"
    combined_both_radars_fp = out_dir / f"{case_id}_upslope_contributing_hazard_map_with_both_radars.png"
    elevation_fp = out_dir / f"{case_id}_upslope_contributing_hazard_elevation_profile.png"

    elevation_profile_ok, osm_counts = plot_map(
        case_name,
        trail_name,
        gdf_m,
        df,
        contours,
        collapse,
        watercourse,
        osm_raw_dir,
        hotspots,
        map_fp,
        elevation_fp,
        km_step=args.km_step,
    )
    plot_radar(case_name, df, radar_fp)
    route_radar_ok, route_radar_source = make_route_risk_radar(case_id, case_name, risk_csv, args.route_radar_png, route_radar_fp)
    combine_images(map_fp, radar_fp, combined_fp)
    combine_images(map_fp, route_radar_fp, combined_route_radar_fp)
    combine_images_stacked_radars(map_fp, [route_radar_fp, radar_fp], combined_both_radars_fp)

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
        "osm_features_within_buffer_total": int(sum(osm_counts.values())) if 'osm_counts' in locals() else 0,
        "elevation_profile_ok": bool(elevation_profile_ok),
        "profile_geojson_used": str(default_profile_geojson(case_id)) if args.profile_geojson is None else str(resolve_path(args.profile_geojson)),
        "map_png": str(map_fp),
        "upslope_radar_png": str(radar_fp),
        "route_risk_radar_png": str(route_radar_fp),
        "route_risk_radar_ok": bool(route_radar_ok),
        "route_risk_radar_source": route_radar_source,
        "combined_png": str(combined_fp),
        "combined_route_risk_radar_png": str(combined_route_radar_fp),
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
