# -*- coding: utf-8 -*-
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib as mpl

from matplotlib.lines import Line2D
from matplotlib.gridspec import GridSpec
from shapely.geometry import LineString


# =========================================================
# 0. Matplotlib font
# =========================================================
mpl.rcParams["font.sans-serif"] = [
    "PingFang TC",
    "Heiti TC",
    "Arial Unicode MS",
    "Noto Sans CJK TC",
    "DejaVu Sans",
]
mpl.rcParams["axes.unicode_minus"] = False


# =========================================================
# A. Input / Output
# =========================================================
# RISK_CSV = Path("ib2_v2_route_risk_output/qixing_route_risk_v2.csv")
# SEMANTIC_GEOJSON = Path("ib1c_route_profile_semantic_output/qixing_route_profile_semantic_enriched.geojson")
# PROFILE_POINTS_GEOJSON = Path("ib1a_route_elevation_profile_output/qixing_route_profile_points.geojson")

# # NSLC 25K 等高線 Shapefile
# CONTOUR_FILE = Path(
#     "/Users/iddmini/Documents/osm路況研究/"
#     "112年經建版地形圖數值資料檔(比例尺二萬五千分之一)(SHP檔)/"
#     "112年經建版地形圖數值資料檔(比例尺二萬五千分之一)(SHP檔)_/"
#     "圖檔/97233NW/向量25K/ContourL.shp"
# )

# # OSM raw layers
# OSM_RAW_DIR = Path("osm_raw_output")

# OSM_POINT_LAYERS = {
#     "trailhead": OSM_RAW_DIR / "osm_trailhead_raw.geojson",
#     "peak": OSM_RAW_DIR / "osm_peak_raw.geojson",
#     "guidepost": OSM_RAW_DIR / "osm_guidepost_raw.geojson",
#     "shelter": OSM_RAW_DIR / "osm_shelter_raw.geojson",
#     "bench": OSM_RAW_DIR / "osm_bench_raw.geojson",
#     "picnic_table": OSM_RAW_DIR / "osm_picnic_table_raw.geojson",
#     "drinking_water": OSM_RAW_DIR / "osm_drinking_water_raw.geojson",
#     "toilets": OSM_RAW_DIR / "osm_toilets_raw.geojson",
#     "information_office": OSM_RAW_DIR / "osm_information_office_raw.geojson",
# }

# OSM_AREA_LAYERS = {
#     "picnic_site": OSM_RAW_DIR / "osm_picnic_site_raw.geojson",
#     "bare_rock": OSM_RAW_DIR / "osm_bare_rock_raw.geojson",
#     "scree": OSM_RAW_DIR / "osm_scree_raw.geojson",
#     "wetland": OSM_RAW_DIR / "osm_wetland_raw.geojson",
#     "water_area": OSM_RAW_DIR / "osm_water_area_raw.geojson",
# }

# OSM_LINE_LAYERS = {
#     "cliff": OSM_RAW_DIR / "osm_cliff_raw.geojson",
#     "waterway": OSM_RAW_DIR / "osm_waterway_raw.geojson",
#     "handrail": OSM_RAW_DIR / "osm_handrail_raw.geojson",
#     "safety_rope": OSM_RAW_DIR / "osm_safety_rope_raw.geojson",
#     "ladder": OSM_RAW_DIR / "osm_ladder_raw.geojson",
# }

# OUT_DIR = Path("ib2d_route_risk_offline_map_output")
# OUT_PNG = OUT_DIR / "qixing_route_context_offline_map.png"
# OUT_SEG_GEOJSON = OUT_DIR / "qixing_route_risk_offline_segments.geojson"


# =========================================================
# A. Input / Output
# =========================================================
CASE_ID = "juansi_waterfall_fitcsv_20260503"
CASE_NAME = "絹絲瀑布 FIT CSV 20260503"

# 建議從專案根目錄 C:\mountain_work\115_osm 執行
PROJECT_ROOT = Path.cwd()

# ---------------------------------------------------------
# Route / risk inputs
# ---------------------------------------------------------
PROFILE_POINTS_GEOJSON = (
    PROJECT_ROOT
    / "outputs"
    / "ib1_route_profile"
    / CASE_ID
    / f"{CASE_ID}_route_profile_points.geojson"
)

SEMANTIC_GEOJSON_CANDIDATES = [
    PROJECT_ROOT
    / "outputs"
    / "ib1c_route_profile_semantics"
    / CASE_ID
    / f"{CASE_ID}_route_profile_semantic_enriched.geojson",

    PROJECT_ROOT
    / "outputs"
    / "ib1c_osm_semantic_risk"
    / CASE_ID
    / f"{CASE_ID}_osm_semantic_risk_profile.geojson",
]

# ib2d 需要「點級」風險資料，不建議直接吃 100m segment。
# 優先吃 Prototype A / ib1e 點級 combined risk；找不到再 fallback。
RISK_CSV_CANDIDATES = [
    PROJECT_ROOT
    / "outputs"
    / "ib1e_osm_nlsc_terrain_risk"
    / CASE_ID
    / f"{CASE_ID}_osm_nlsc_terrain_risk_profile.csv",

    PROJECT_ROOT
    / "outputs"
    / "ib1e_osm_terrain_risk"
    / CASE_ID
    / f"{CASE_ID}_osm_terrain_risk_profile.csv",

    PROJECT_ROOT
    / "outputs"
    / "ib1c_osm_semantic_risk"
    / CASE_ID
    / f"{CASE_ID}_osm_semantic_risk_profile.csv",
]

# ---------------------------------------------------------
# NSLC 25K contour
# ---------------------------------------------------------
CONTOUR_FILE = (
    PROJECT_ROOT
    / "nlsc_raw"
    / "97233NW"
    / "向量25K"
    / "ContourL.shp"
)

# ---------------------------------------------------------
# OSM raw layers
# ---------------------------------------------------------
OSM_RAW_DIR = PROJECT_ROOT / "osm_raw_output" / CASE_ID

OSM_POINT_LAYERS = {
    "trailhead": OSM_RAW_DIR / "osm_trailhead_raw.geojson",
    "peak": OSM_RAW_DIR / "osm_peak_raw.geojson",
    "guidepost": OSM_RAW_DIR / "osm_guidepost_raw.geojson",
    "shelter": OSM_RAW_DIR / "osm_shelter_raw.geojson",
    "bench": OSM_RAW_DIR / "osm_bench_raw.geojson",
    "picnic_table": OSM_RAW_DIR / "osm_picnic_table_raw.geojson",
    "drinking_water": OSM_RAW_DIR / "osm_drinking_water_raw.geojson",
    "toilets": OSM_RAW_DIR / "osm_toilets_raw.geojson",
    "information_office": OSM_RAW_DIR / "osm_information_office_raw.geojson",
}

OSM_AREA_LAYERS = {
    "picnic_site": OSM_RAW_DIR / "osm_picnic_site_raw.geojson",
    "bare_rock": OSM_RAW_DIR / "osm_bare_rock_raw.geojson",
    "scree": OSM_RAW_DIR / "osm_scree_raw.geojson",
    "wetland": OSM_RAW_DIR / "osm_wetland_raw.geojson",
    "water_area": OSM_RAW_DIR / "osm_water_area_raw.geojson",
}

OSM_LINE_LAYERS = {
    "cliff": OSM_RAW_DIR / "osm_cliff_raw.geojson",
    "waterway": OSM_RAW_DIR / "osm_waterway_raw.geojson",
    "handrail": OSM_RAW_DIR / "osm_handrail_raw.geojson",
    "safety_rope": OSM_RAW_DIR / "osm_safety_rope_raw.geojson",
    "ladder": OSM_RAW_DIR / "osm_ladder_raw.geojson",
}

# ---------------------------------------------------------
# Outputs
# ---------------------------------------------------------
OUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "ib2d_route_risk_offline_map"
    / CASE_ID
)
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_PNG = OUT_DIR / f"{CASE_ID}_route_context_offline_map.png"
OUT_SEG_GEOJSON = OUT_DIR / f"{CASE_ID}_route_context_offline_segments.geojson"


# =========================================================
# B. Style config
# =========================================================

PRESENTATION_CONTEXT_ONLY = True

ROUTE_BUFFER_M = 500
DPI = 300

RISK_COLORS = {
    "low": "#4CAF50",
    "moderate": "#F2C037",
    "high": "#F57C00",
    "very_high": "#D93A3A",
    "unknown": "#9E9E9E",
}

RISK_LEVEL = {
    "unknown": 0,
    "low": 1,
    "moderate": 2,
    "high": 3,
    "very_high": 4,
}

POINT_STYLE = {
    "trailhead": {"color": "#1b5e20", "marker": "^", "size": 75, "label": "trailhead"},
    "peak": {"color": "#6a1b9a", "marker": "*", "size": 145, "label": "peak"},
    "guidepost": {"color": "#1565c0", "marker": "P", "size": 55, "label": "guidepost"},
    "shelter": {"color": "#795548", "marker": "s", "size": 60, "label": "shelter"},
    "bench": {"color": "#8d6e63", "marker": "v", "size": 55, "label": "bench"},
    "picnic_table": {"color": "#5d4037", "marker": "D", "size": 45, "label": "picnic_table"},
    "drinking_water": {"color": "#0097a7", "marker": "o", "size": 60, "label": "drinking_water"},
    "toilets": {"color": "#455a64", "marker": "D", "size": 50, "label": "toilets"},
    "information_office": {"color": "#ef6c00", "marker": "X", "size": 70, "label": "information_office"},
}

AREA_STYLE = {
    "picnic_site": {"facecolor": "#c8e6c9", "edgecolor": "#66bb6a", "alpha": 0.35, "label": "picnic_site"},
    "bare_rock": {"facecolor": "#bdbdbd", "edgecolor": "#757575", "alpha": 0.35, "label": "bare_rock"},
    "scree": {"facecolor": "#d7ccc8", "edgecolor": "#8d6e63", "alpha": 0.40, "label": "scree"},
    "wetland": {"facecolor": "#b2dfdb", "edgecolor": "#00897b", "alpha": 0.35, "label": "wetland"},
    "water_area": {"facecolor": "#bbdefb", "edgecolor": "#1976d2", "alpha": 0.35, "label": "water_area"},
}

LINE_STYLE = {
    "cliff": {"color": "#8b0000", "linewidth": 1.8, "linestyle": "--", "alpha": 0.90, "label": "cliff"},
    "waterway": {"color": "#1976d2", "linewidth": 1.0, "linestyle": "-", "alpha": 0.65, "label": "waterway"},
    "handrail": {"color": "#6d4c41", "linewidth": 1.4, "linestyle": ":", "alpha": 0.90, "label": "handrail"},
    "safety_rope": {"color": "#5d4037", "linewidth": 1.6, "linestyle": "-.", "alpha": 0.90, "label": "safety_rope"},
    "ladder": {"color": "#000000", "linewidth": 1.5, "linestyle": ":", "alpha": 0.90, "label": "ladder"},
}


# =========================================================
# C. Utility
# =========================================================
def ensure_exists(fp: Path, required=True):
    if not fp.exists():
        msg = f"找不到檔案：{fp.resolve()}"
        if required:
            raise FileNotFoundError(msg)
        print("optional layer missing:", fp)
        return False
    return True

def first_existing(candidates, label="file", required=True):
    for fp in candidates:
        if fp.exists():
            print(f"{label}:", fp)
            return fp

    msg = "\n".join(str(fp) for fp in candidates)
    if required:
        raise FileNotFoundError(f"找不到 {label}，候選路徑：\n{msg}")

    print(f"optional {label} missing. candidates:\n{msg}")
    return None


def normalize_columns(df: pd.DataFrame):
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    return out


def maybe_to_numeric(df: pd.DataFrame, cols):
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def find_distance_col(df: pd.DataFrame):
    candidates = ["dist_m", "cumdist_m", "distance_m", "cum_dist_m", "distance"]
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(f"找不到距離欄位，現有欄位：{list(df.columns)}")


def find_risk_band_col(df: pd.DataFrame):
    candidates = [
        "risk_band_recomputed",
        "osm_terrain_combined_risk_band",
        "combined_risk_band",
        "risk_band",
        "segment_risk_band",
    ]
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(f"找不到 risk band 欄位，現有欄位：{list(df.columns)}")


def find_risk_score_col(df: pd.DataFrame):
    candidates = [
        "risk_score_smooth",
        "risk_score",
        "osm_terrain_combined_risk_score",
        "combined_risk_score",
        "osm_semantic_risk_score",
        "segment_risk_score",
    ]
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(f"找不到 risk score 欄位，現有欄位：{list(df.columns)}")


def normalize_risk_band(v):
    if pd.isna(v):
        return "unknown"
    s = str(v).strip().lower()
    return s if s in RISK_COLORS else "unknown"


def risk_to_level(v):
    return RISK_LEVEL.get(normalize_risk_band(v), 0)


def pick_segment_risk_band(b1, b2):
    b1 = normalize_risk_band(b1)
    b2 = normalize_risk_band(b2)
    return b1 if risk_to_level(b1) >= risk_to_level(b2) else b2


def get_metric_crs(gdf: gpd.GeoDataFrame):
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    return gdf.estimate_utm_crs()


def safe_union(geo_series):
    if hasattr(geo_series, "union_all"):
        return geo_series.union_all()
    return geo_series.unary_union


def safe_union_centroid(gdf: gpd.GeoDataFrame):
    return safe_union(gdf.geometry).centroid


def read_optional_layer(fp: Path, target_crs=None) -> gpd.GeoDataFrame:
    if not fp.exists():
        print(f"layer missing: {fp}")
        return gpd.GeoDataFrame(geometry=[], crs=target_crs)

    try:
        gdf = gpd.read_file(fp)
    except Exception as e:
        print(f"layer read failed: {fp} | {e}")
        return gpd.GeoDataFrame(geometry=[], crs=target_crs)

    if gdf.empty:
        print(f"layer empty: {fp}")
        return gpd.GeoDataFrame(geometry=[], crs=target_crs)

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")

    if target_crs is not None:
        gdf = gdf.to_crs(target_crs)

    return gdf


def clip_to_route_buffer(gdf: gpd.GeoDataFrame, route_buffer):
    if gdf is None or gdf.empty:
        return gdf

    try:
        return gdf[gdf.intersects(route_buffer)].copy()
    except Exception as e:
        print("clip failed:", e)
        return gdf.iloc[0:0].copy()


def load_osm_raw_layers(layer_dict, target_crs, route_buffer):
    out = {}
    for name, fp in layer_dict.items():
        gdf = read_optional_layer(fp, target_crs=target_crs)
        gdf = clip_to_route_buffer(gdf, route_buffer)
        out[name] = gdf
        print(f"{name}: {len(gdf)}")
    return out


def build_route_segments(points_gdf: gpd.GeoDataFrame, risk_df: pd.DataFrame):
    dist_col = find_distance_col(risk_df)
    risk_band_col = find_risk_band_col(risk_df)
    risk_score_col = find_risk_score_col(risk_df)

    risk_df = risk_df.sort_values(dist_col).reset_index(drop=True).copy()
    points_gdf = points_gdf.copy()

    if dist_col in points_gdf.columns:
        points_gdf = points_gdf.sort_values(dist_col).reset_index(drop=True)
    elif "dist_m" in points_gdf.columns:
        points_gdf = points_gdf.sort_values("dist_m").reset_index(drop=True)
    else:
        points_gdf = points_gdf.reset_index(drop=True)

    if len(points_gdf) != len(risk_df):
        n = min(len(points_gdf), len(risk_df))
        warnings.warn(f"points 與 risk 列數不同，將截到最小長度 n={n}")
        points_gdf = points_gdf.iloc[:n].copy()
        risk_df = risk_df.iloc[:n].copy()

    rows = []

    for i in range(len(points_gdf) - 1):
        p1 = points_gdf.iloc[i]
        p2 = points_gdf.iloc[i + 1]
        r1 = risk_df.iloc[i]
        r2 = risk_df.iloc[i + 1]

        if p1.geometry is None or p2.geometry is None:
            continue
        if p1.geometry.is_empty or p2.geometry.is_empty:
            continue

        line = LineString([p1.geometry, p2.geometry])

        risk_vals = []
        if risk_score_col in r1.index and pd.notna(r1[risk_score_col]):
            risk_vals.append(float(r1[risk_score_col]))
        if risk_score_col in r2.index and pd.notna(r2[risk_score_col]):
            risk_vals.append(float(r2[risk_score_col]))

        seg_risk_score = float(np.mean(risk_vals)) if risk_vals else np.nan

        effort_vals = []
        if "effort_score" in r1.index and pd.notna(r1["effort_score"]):
            effort_vals.append(float(r1["effort_score"]))
        if "effort_score" in r2.index and pd.notna(r2["effort_score"]):
            effort_vals.append(float(r2["effort_score"]))
        seg_effort_score = float(np.mean(effort_vals)) if effort_vals else np.nan

        exposure_vals = []
        if "exposure_score" in r1.index and pd.notna(r1["exposure_score"]):
            exposure_vals.append(float(r1["exposure_score"]))
        if "exposure_score" in r2.index and pd.notna(r2["exposure_score"]):
            exposure_vals.append(float(r2["exposure_score"]))
        seg_exposure_score = float(np.mean(exposure_vals)) if exposure_vals else np.nan

        seg_risk_band = pick_segment_risk_band(r1[risk_band_col], r2[risk_band_col])

        rows.append(
            {
                "seg_id": i,
                "start_dist_m": float(r1[dist_col]),
                "end_dist_m": float(r2[dist_col]),
                "mid_dist_m": float(np.nanmean([r1[dist_col], r2[dist_col]])),
                "risk_band": seg_risk_band,
                "risk_score_for_map": seg_risk_score,
                "effort_score": seg_effort_score,
                "exposure_score": seg_exposure_score,
                "geometry": line,
            }
        )

    if not rows:
        raise ValueError("無法建立 route segments，請檢查 profile points geometry。")

    return gpd.GeoDataFrame(rows, geometry="geometry", crs=points_gdf.crs)


def contiguous_runs(seg_gdf: gpd.GeoDataFrame, target_band="very_high"):
    runs = []
    current = []

    for _, row in seg_gdf.sort_values("start_dist_m").iterrows():
        if row["risk_band"] == target_band:
            current.append(row)
        else:
            if current:
                runs.append(current)
                current = []

    if current:
        runs.append(current)

    out = []
    for run in runs:
        start_m = run[0]["start_dist_m"]
        end_m = run[-1]["end_dist_m"]
        subset = gpd.GeoDataFrame(run, geometry="geometry", crs=seg_gdf.crs)
        centroid = safe_union_centroid(subset)
        out.append((start_m, end_m, centroid))

    return out


def add_north_arrow(ax, x=0.06, y=0.94, size=14):
    ax.annotate(
        "N",
        xy=(x, y),
        xycoords="axes fraction",
        xytext=(x, y - 0.06),
        textcoords="axes fraction",
        arrowprops=dict(arrowstyle="-|>", lw=1.5, color="black"),
        ha="center",
        va="center",
        fontsize=size,
        fontweight="bold",
    )


def add_scale_bar(ax, length_m=500, location=(0.06, 0.06), linewidth=3):
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()

    x0 = xlim[0] + (xlim[1] - xlim[0]) * location[0]
    y0 = ylim[0] + (ylim[1] - ylim[0]) * location[1]

    ax.plot([x0, x0 + length_m], [y0, y0], color="black", lw=linewidth, solid_capstyle="butt")
    ax.plot([x0, x0], [y0 - 20, y0 + 20], color="black", lw=linewidth / 2)
    ax.plot([x0 + length_m, x0 + length_m], [y0 - 20, y0 + 20], color="black", lw=linewidth / 2)

    ax.text(
        x0 + length_m / 2,
        y0 + 45,
        f"{length_m:.0f} m",
        ha="center",
        va="bottom",
        fontsize=10,
        clip_on=True,
    )


def make_osm_legend_handles(osm_point_layers, osm_area_layers, osm_line_layers):
    handles = []

    for name, gdf_sub in osm_point_layers.items():
        if gdf_sub.empty:
            continue

        s = POINT_STYLE.get(
            name,
            {"color": "#333333", "marker": "o", "size": 50, "label": name},
        )

        handles.append(
            Line2D(
                [0],
                [0],
                marker=s["marker"],
                color="w",
                markerfacecolor=s["color"],
                markeredgecolor="white",
                markersize=8,
                linewidth=0,
                label=s.get("label", name),
            )
        )

    for name, gdf_sub in osm_line_layers.items():
        if gdf_sub.empty:
            continue

        s = LINE_STYLE.get(
            name,
            {"color": "#999999", "linestyle": "-", "linewidth": 1.2, "label": name},
        )

        handles.append(
            Line2D(
                [0],
                [0],
                color=s["color"],
                linestyle=s.get("linestyle", "-"),
                linewidth=2,
                label=s.get("label", name),
            )
        )

    for name, gdf_sub in osm_area_layers.items():
        if gdf_sub.empty:
            continue

        s = AREA_STYLE.get(
            name,
            {"facecolor": "#eeeeee", "edgecolor": "#999999", "label": name},
        )

        handles.append(
            Line2D(
                [0],
                [0],
                marker="s",
                color=s["edgecolor"],
                markerfacecolor=s["facecolor"],
                markersize=8,
                linewidth=0,
                label=s.get("label", name),
            )
        )

    return handles


def add_contour_labels_near_route(
    ax,
    contour_gdf,
    route_buffer_geom,
    elev_col="_contour_val",
    major_step=50,
    label_every_n=2,
    max_labels=18,
    text_color="#666666",
):
    if contour_gdf is None or contour_gdf.empty:
        return
    if elev_col not in contour_gdf.columns:
        return

    cg = contour_gdf.copy()
    cg = cg[cg[elev_col].notna()].copy()
    if cg.empty:
        return

    cg[elev_col] = pd.to_numeric(cg[elev_col], errors="coerce")
    cg = cg[cg[elev_col].notna()].copy()
    cg = cg[(cg[elev_col] % major_step) == 0].copy()

    if cg.empty:
        return

    if route_buffer_geom is not None:
        near_zone = route_buffer_geom.buffer(120)
        cg = cg[cg.intersects(near_zone)].copy()

    if cg.empty:
        return

    cg["_label_x"] = cg.geometry.representative_point().x
    cg["_label_y"] = cg.geometry.representative_point().y
    cg = cg.sort_values([elev_col, "_label_x", "_label_y"]).iloc[::label_every_n].copy()

    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()

    label_count = 0

    for _, row in cg.iterrows():
        if label_count >= max_labels:
            break

        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        try:
            candidate = geom

            if route_buffer_geom is not None:
                inter = geom.intersection(route_buffer_geom.buffer(80))
                if not inter.is_empty:
                    candidate = inter

            pt = candidate.representative_point()
            x, y = pt.x, pt.y

            if not (x0 <= x <= x1 and y0 <= y <= y1):
                continue

            ax.text(
                x,
                y,
                f"{int(round(row[elev_col]))}",
                fontsize=7,
                color=text_color,
                ha="center",
                va="center",
                bbox=dict(
                    boxstyle="round,pad=0.12",
                    facecolor="white",
                    edgecolor="none",
                    alpha=0.65,
                ),
                clip_on=True,
                zorder=5,
            )
            label_count += 1

        except Exception:
            continue


# =========================================================
# D. Main
# =========================================================
def main():
    RISK_CSV = first_existing(RISK_CSV_CANDIDATES, label="risk CSV", required=True)
    SEMANTIC_GEOJSON = first_existing(
        SEMANTIC_GEOJSON_CANDIDATES,
        label="semantic GeoJSON",
        required=True,
    )

    ensure_exists(PROFILE_POINTS_GEOJSON)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    risk_df = pd.read_csv(RISK_CSV)
    risk_df = normalize_columns(risk_df)

    risk_df = maybe_to_numeric(
        risk_df,
        [
            "dist_m",
            "cumdist_m",
            "distance_m",
            "cum_dist_m",
            "distance",
            "risk_score",
            "risk_score_smooth",
            "osm_terrain_combined_risk_score",
            "combined_risk_score",
            "osm_semantic_risk_score",
            "segment_risk_score",
            "effort_score",
            "exposure_score",
        ],
    )

    dist_col = find_distance_col(risk_df)

    risk_score_col = find_risk_score_col(risk_df)

    if "risk_score_smooth" not in risk_df.columns:
        risk_df = risk_df.sort_values(dist_col).reset_index(drop=True)
        risk_df["risk_score_smooth"] = (
            risk_df[risk_score_col].rolling(5, center=True, min_periods=2).mean()
        )

    if "risk_score_smooth" in risk_df.columns and risk_df["risk_score_smooth"].isna().all():
        risk_df = risk_df.sort_values(dist_col).reset_index(drop=True)
        risk_df["risk_score_smooth"] = (
            risk_df[risk_score_col].rolling(5, center=True, min_periods=2).mean()
        )

    risk_score_col = "risk_score_smooth"
    print("risk score column for map:", risk_score_col)

    semantic_gdf = gpd.read_file(SEMANTIC_GEOJSON)
    points_gdf = gpd.read_file(PROFILE_POINTS_GEOJSON)

    if risk_df.empty:
        raise ValueError(f"風險 CSV 為空：{RISK_CSV}")
    if semantic_gdf.empty:
        raise ValueError(f"語意 GeoJSON 為空：{SEMANTIC_GEOJSON}")
    if points_gdf.empty:
        raise ValueError(f"profile points GeoJSON 為空：{PROFILE_POINTS_GEOJSON}")

    if semantic_gdf.crs is None:
        semantic_gdf = semantic_gdf.set_crs("EPSG:4326")
    if points_gdf.crs is None:
        points_gdf = points_gdf.set_crs("EPSG:4326")

    metric_crs = get_metric_crs(points_gdf)

    semantic_m = semantic_gdf.to_crs(metric_crs)
    points_m = points_gdf.to_crs(metric_crs)

    if dist_col not in points_m.columns:
        if dist_col in semantic_m.columns and len(semantic_m) == len(points_m):
            points_m[dist_col] = semantic_m[dist_col].values
        elif "dist_m" in semantic_m.columns and len(semantic_m) == len(points_m):
            points_m[dist_col] = semantic_m["dist_m"].values

    seg_gdf = build_route_segments(points_m, risk_df)
    seg_gdf.to_file(OUT_SEG_GEOJSON, driver="GeoJSON")

    route_union = safe_union(seg_gdf.geometry)
    route_buffer = route_union.buffer(ROUTE_BUFFER_M)

    very_high_runs = contiguous_runs(seg_gdf, target_band="very_high")

    contour_m = gpd.GeoDataFrame(geometry=[], crs=metric_crs)

    if CONTOUR_FILE.exists():
        try:
            contour_gdf = gpd.read_file(CONTOUR_FILE)
            if not contour_gdf.empty:
                if contour_gdf.crs is None:
                    contour_gdf = contour_gdf.set_crs("EPSG:4326")
                contour_m = contour_gdf.to_crs(metric_crs)
                contour_m = clip_to_route_buffer(contour_m, route_buffer)
        except Exception as e:
            print(f"contour read failed: {CONTOUR_FILE} | {e}")
    else:
        print(f"contour missing: {CONTOUR_FILE}")

    print("\n=== OSM point layers within route buffer ===")
    osm_point_layers = load_osm_raw_layers(OSM_POINT_LAYERS, metric_crs, route_buffer)

    print("\n=== OSM area layers within route buffer ===")
    osm_area_layers = load_osm_raw_layers(OSM_AREA_LAYERS, metric_crs, route_buffer)

    print("\n=== OSM line layers within route buffer ===")
    osm_line_layers = load_osm_raw_layers(OSM_LINE_LAYERS, metric_crs, route_buffer)

    # -----------------------------------------------------
    # Plot layout: map axis + legend axis
    # -----------------------------------------------------
    fig = plt.figure(figsize=(18, 11), dpi=DPI)

    gs = GridSpec(
        nrows=1,
        ncols=2,
        width_ratios=[4.8, 1.2],
        wspace=0.04,
        figure=fig,
    )

    ax = fig.add_subplot(gs[0, 0])
    ax_leg = fig.add_subplot(gs[0, 1])

    ax.set_facecolor("#f8f8f8")
    ax_leg.axis("off")

    fig.subplots_adjust(left=0.04, right=0.98, top=0.88, bottom=0.07)

    # -----------------------------------------------------
    # Contours
    # -----------------------------------------------------
    if not contour_m.empty:
        contour_col = None
        for c in ["zv2", "elev", "elevation", "contour", "z", "value", "height"]:
            if c in contour_m.columns:
                contour_col = c
                break

        if contour_col is not None:
            contour_m["_contour_val"] = pd.to_numeric(contour_m[contour_col], errors="coerce")
            major_mask = contour_m["_contour_val"].fillna(-999999) % 50 == 0

            contour_minor = contour_m.loc[~major_mask].copy()
            contour_major = contour_m.loc[major_mask].copy()

            if not contour_minor.empty:
                contour_minor.plot(
                    ax=ax,
                    color="#a8a8a8",
                    linewidth=0.55,
                    alpha=0.72,
                    zorder=1,
                )

            if not contour_major.empty:
                contour_major.plot(
                    ax=ax,
                    color="#666666",
                    linewidth=1.05,
                    alpha=0.92,
                    zorder=2,
                )
        else:
            contour_m.plot(
                ax=ax,
                color="#8c8c8c",
                linewidth=0.80,
                alpha=0.75,
                zorder=1,
            )

    # -----------------------------------------------------
    # OSM area layers
    # -----------------------------------------------------
    for name, gdf_sub in osm_area_layers.items():
        if gdf_sub.empty:
            continue

        style = AREA_STYLE.get(
            name,
            {"facecolor": "#eeeeee", "edgecolor": "#999999", "alpha": 0.25},
        )

        gdf_sub.plot(
            ax=ax,
            facecolor=style["facecolor"],
            edgecolor=style["edgecolor"],
            linewidth=0.8,
            alpha=style["alpha"],
            zorder=3,
        )

    # -----------------------------------------------------
    # OSM line layers
    # -----------------------------------------------------
    for name, gdf_sub in osm_line_layers.items():
        if gdf_sub.empty:
            continue

        style = LINE_STYLE.get(
            name,
            {"color": "#999999", "linewidth": 1.0, "linestyle": "-", "alpha": 0.5},
        )

        gdf_sub.plot(
            ax=ax,
            color=style["color"],
            linewidth=style["linewidth"],
            linestyle=style["linestyle"],
            alpha=style["alpha"],
            zorder=4,
        )


    # -----------------------------------------------------
    # Route segments
    # -----------------------------------------------------
    if PRESENTATION_CONTEXT_ONLY:
        # 第二頁：圖資整合版，只畫單色主幹路線，不顯示風險分級
        seg_gdf.plot(
            ax=ax,
            color="#F57C00",
            linewidth=4.8,
            alpha=0.97,
            zorder=8,
            label="route mainline",
        )
    else:
        # 後續頁：風險結果版，依 risk band 著色
        for band in ["low", "moderate", "high", "very_high", "unknown"]:
            sub = seg_gdf[seg_gdf["risk_band"] == band]
            if sub.empty:
                continue

            sub.plot(
                ax=ax,
                color=RISK_COLORS.get(band, "#9E9E9E"),
                linewidth=4.8,
                alpha=0.97,
                zorder=8,
                label=band,
            )

    # -----------------------------------------------------
    # OSM point layers
    # -----------------------------------------------------
    for name, gdf_sub in osm_point_layers.items():
        if gdf_sub.empty:
            continue

        style = POINT_STYLE.get(
            name,
            {"color": "#333333", "marker": "o", "size": 45, "label": name},
        )

        plot_geom = gdf_sub.geometry
        if not all(plot_geom.geom_type == "Point"):
            plot_geom = gdf_sub.geometry.representative_point()

        ax.scatter(
            plot_geom.x,
            plot_geom.y,
            c=style["color"],
            marker=style["marker"],
            s=style["size"],
            edgecolors="white",
            linewidths=0.7,
            alpha=0.96,
            zorder=10,
            label=style["label"],
        )

    # -----------------------------------------------------
    # Start / End
    # -----------------------------------------------------
    start_pt = points_m.iloc[0].geometry
    end_pt = points_m.iloc[-1].geometry

    ax.scatter(
        [start_pt.x],
        [start_pt.y],
        s=140,
        c="#2e7d32",
        marker="o",
        edgecolors="white",
        linewidths=1.5,
        zorder=12,
    )
    ax.text(
        start_pt.x + 15,
        start_pt.y + 15,
        "Start",
        color="#1b5e20",
        fontsize=11,
        fontweight="bold",
        zorder=13,
        bbox=dict(facecolor="white", edgecolor="none", alpha=0.60, pad=0.4),
        clip_on=True,
    )

    ax.scatter(
        [end_pt.x],
        [end_pt.y],
        s=140,
        c="#c62828",
        marker="s",
        edgecolors="white",
        linewidths=1.5,
        zorder=12,
    )
    ax.text(
        end_pt.x + 15,
        end_pt.y + 15,
        "End",
        color="#b71c1c",
        fontsize=11,
        fontweight="bold",
        zorder=13,
        bbox=dict(facecolor="white", edgecolor="none", alpha=0.60, pad=0.4),
        clip_on=True,
    )

    # -----------------------------------------------------
    # Very high labels
    # -----------------------------------------------------
    if not PRESENTATION_CONTEXT_ONLY:
        for start_m, end_m, centroid in very_high_runs:
            label = f"very_high\n{int(round(start_m))}–{int(round(end_m))} m"

            if end_m < 1000:
                offset = (55, 42)
                ha = "left"
            elif start_m > 2500:
                offset = (-80, 45)
                ha = "right"
            else:
                offset = (45, 35)
                ha = "left"

            ax.annotate(
                label,
                xy=(centroid.x, centroid.y),
                xytext=offset,
                textcoords="offset points",
                fontsize=9,
                color="#8b0000",
                ha=ha,
                va="center",
                bbox=dict(
                    boxstyle="round,pad=0.25",
                    fc="white",
                    ec="#D93A3A",
                    alpha=0.94,
                ),
                arrowprops=dict(
                    arrowstyle="-",
                    color="#D93A3A",
                    lw=1.0,
                    alpha=0.85,
                ),
                zorder=15,
                clip_on=True,
            )

    # -----------------------------------------------------
    # Extent / decorations
    # -----------------------------------------------------
    minx, miny, maxx, maxy = route_buffer.bounds
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)

    add_contour_labels_near_route(
        ax=ax,
        contour_gdf=contour_m,
        route_buffer_geom=route_buffer,
        elev_col="_contour_val",
        major_step=50,
        label_every_n=2,
        max_labels=18,
    )

    add_north_arrow(ax, x=0.06, y=0.94, size=14)
    add_scale_bar(ax, length_m=250, location=(0.06, 0.06), linewidth=3)

    
    # if PRESENTATION_CONTEXT_ONLY:
    #     fig.suptitle(
    #         "Qixing Route Context Map\n"
    #         "OSM Features and NSLC Contours",
    #         fontsize=18,
    #         y=0.965,
    #     )
    # else:
    #     fig.suptitle(
    #         "Qixing Route Offline Risk Map\n"
    #         "Risk Segments, Contours, and OSM Raw Features",
    #         fontsize=18,
    #         y=0.965,
    #     )
    if PRESENTATION_CONTEXT_ONLY:
        fig.suptitle(
            f"{CASE_NAME} Route Context Map\n"
            "OSM Features and NSLC Contours",
            fontsize=18,
            y=0.965,
        )
    else:
        fig.suptitle(
            f"{CASE_NAME} Offline Risk Map\n"
            "Risk Segments, Contours, and OSM Raw Features",
            fontsize=18,
            y=0.965,
        )

    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel("")
    ax.set_ylabel("")

    # -----------------------------------------------------
    # Legends in right-side legend panel
    # -----------------------------------------------------
    ax_leg.axis("off")

    if not PRESENTATION_CONTEXT_ONLY:
        risk_handles = [
            Line2D([0], [0], color=RISK_COLORS["low"], lw=4, label="low"),
            Line2D([0], [0], color=RISK_COLORS["moderate"], lw=4, label="moderate"),
            Line2D([0], [0], color=RISK_COLORS["high"], lw=4, label="high"),
            Line2D([0], [0], color=RISK_COLORS["very_high"], lw=4, label="very_high"),
        ]

        risk_legend = ax_leg.legend(
            handles=risk_handles,
            title="Risk band",
            loc="lower left",
            bbox_to_anchor=(0.02, 0.06),
            frameon=True,
            fontsize=10,
            title_fontsize=11,
            borderaxespad=0.0,
            ncol=1,
            handlelength=2.2,
            handletextpad=0.8,
            labelspacing=0.65,
        )
        ax_leg.add_artist(risk_legend)

    osm_handles = make_osm_legend_handles(
        osm_point_layers,
        osm_area_layers,
        osm_line_layers,
    )

    if osm_handles:
        osm_legend = ax_leg.legend(
            handles=osm_handles,
            title="OSM / NSLC features",
            loc="upper left",
            bbox_to_anchor=(0.02, 0.98),
            frameon=True,
            fontsize=8,
            title_fontsize=10,
            borderaxespad=0.0,
            ncol=2,
            handlelength=1.8,
            handletextpad=0.6,
            columnspacing=0.9,
            labelspacing=0.5,
        )
        ax_leg.add_artist(osm_legend)

    fig.savefig(
        OUT_PNG,
        dpi=DPI,
        facecolor="white",
        bbox_inches=None,
        pad_inches=0.1,
    )
    plt.close(fig)

    # -----------------------------------------------------
    # Console summary
    # -----------------------------------------------------
    print("完成！")
    print("case:", CASE_ID)
    print("case name:", CASE_NAME)
    print("PNG:", OUT_PNG.resolve())
    print("segment GeoJSON:", OUT_SEG_GEOJSON.resolve())

    print("\n=== core summary ===")
    print("points:", len(points_m))
    print("segments:", len(seg_gdf))
    print("metric CRS:", metric_crs)


    if not PRESENTATION_CONTEXT_ONLY:
        print("\n=== risk_band ===")
        print(seg_gdf["risk_band"].value_counts(dropna=False))

        print("\n=== very_high runs ===")
        if very_high_runs:
            for start_m, end_m, _ in very_high_runs:
                print(f"{int(round(start_m))}–{int(round(end_m))} m")
        else:
            print("none")

    print("\n=== contour ===")
    print("contour features within buffer:", len(contour_m))


if __name__ == "__main__":
    main()