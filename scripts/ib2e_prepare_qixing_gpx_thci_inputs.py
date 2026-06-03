# -*- coding: utf-8 -*-
from pathlib import Path
from datetime import datetime, timezone
import os
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.append(str(PROJECT_ROOT / "scripts"))

from common.activity_loader import load_activity_points  # noqa: E402


MODEL_VERSION = "prototype_A_terrain_dominant_v1_gpx_direct"
CONTOUR_FP = PROJECT_ROOT / "nlsc_raw" / "97233NW" / "向量25K" / "ContourL.shp"
METRIC_CRS = "EPSG:32651"
SAMPLE_INTERVAL_M = 1.0
CONTOUR_SEGMENT_LEN_M = 20.0
CONTOUR_WINDOW_RADIUS_M = 50.0
CONTOUR_DENSITY_BUFFER_M = 20.0

CASES = [
    {
        "case_id": "qixing_xiaoyoukeng_main_peak_20260315",
        "case_name": "小油坑七星山主峰 20260315",
        "gpx_path": "qixing_xiaoyoukeng_main_peak_20260315/小油坑七星山主峰.gpx",
    },
    {
        "case_id": "qixing_lengshuikeng_main_peak_20260523",
        "case_name": "冷水坑到七星山主峰 20260523",
        "gpx_path": "qixing_lengshuikeng_main_peak_20260523/冷水坑到七星山主峰.gpx",
    },
]

NEAR_RULES = {
    "safety_rope": ("osm_safety_rope_raw.geojson", 40.0),
    "handrail": ("osm_handrail_raw.geojson", 40.0),
    "rungs": ("osm_rungs_raw.geojson", 40.0),
    "ladder": ("osm_ladder_raw.geojson", 40.0),
    "via_ferrata": ("osm_via_ferrata_raw.geojson", 40.0),
    "cliff": ("osm_cliff_raw.geojson", 60.0),
    "scree": ("osm_scree_raw.geojson", 60.0),
    "bare_rock": ("osm_bare_rock_raw.geojson", 60.0),
    "landslide": ("osm_landslide_raw.geojson", 60.0),
    "waterway": ("osm_waterway_raw.geojson", 35.0),
    "water_area": ("osm_water_area_raw.geojson", 35.0),
    "wetland": ("osm_wetland_raw.geojson", 35.0),
    "trailhead": ("osm_trailhead_raw.geojson", 25.0),
    "peak": ("osm_peak_raw.geojson", 25.0),
    "guidepost": ("osm_guidepost_raw.geojson", 25.0),
    "shelter": ("osm_shelter_raw.geojson", 25.0),
    "alpine_hut": ("osm_alpine_hut_raw.geojson", 25.0),
    "wilderness_hut": ("osm_wilderness_hut_raw.geojson", 25.0),
    "bench": ("osm_bench_raw.geojson", 25.0),
    "picnic_table": ("osm_picnic_table_raw.geojson", 25.0),
    "picnic_site": ("osm_picnic_site_raw.geojson", 25.0),
    "drinking_water": ("osm_drinking_water_raw.geojson", 25.0),
    "toilets": ("osm_toilets_raw.geojson", 25.0),
    "visitor_centre": ("osm_visitor_centre_raw.geojson", 25.0),
    "information_office": ("osm_information_office_raw.geojson", 25.0),
}

SLOPE_BAND_WINDOW_SCORE = {
    "flat": 0.05,
    "gentle": 0.15,
    "moderate": 0.35,
    "steep": 0.55,
    "very_steep": 0.70,
    "unknown": 0.20,
}


def clamp(v, lo=0.0, hi=1.0):
    if pd.isna(v):
        return np.nan
    return max(lo, min(hi, float(v)))


def haversine_m(lat1, lon1, lat2, lon2):
    radius = 6371000.0
    lat1 = np.radians(lat1)
    lon1 = np.radians(lon1)
    lat2 = np.radians(lat2)
    lon2 = np.radians(lon2)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return radius * 2 * np.arcsin(np.sqrt(a))


def ensure_inputs():
    if not CONTOUR_FP.exists():
        raise FileNotFoundError(CONTOUR_FP)


def load_trimmed_gpx(gpx_fp):
    gdf = load_activity_points(gpx_fp, "gpx")
    ele = pd.to_numeric(gdf["ele_m"], errors="coerce")
    summit_idx = int(ele.idxmax())
    trimmed = gdf.iloc[: summit_idx + 1].copy().reset_index(drop=True)
    trimmed["trim_rule"] = "start_to_max_elevation"
    return trimmed, summit_idx, len(gdf)


def cumulative_distance_metric(gdf_metric):
    coords = [(geom.x, geom.y) for geom in gdf_metric.geometry]
    dists = [0.0]
    for i in range(1, len(coords)):
        x0, y0 = coords[i - 1]
        x1, y1 = coords[i]
        dists.append(float(np.hypot(x1 - x0, y1 - y0)))
    return np.cumsum(dists)


def slope_band_from_pct(v):
    if pd.isna(v):
        return "unknown"
    a = abs(float(v))
    if a < 3:
        return "flat"
    if a < 8:
        return "gentle"
    if a < 15:
        return "moderate"
    if a < 25:
        return "steep"
    return "very_steep"


def build_route_profile(case, trimmed_gdf):
    metric = trimmed_gdf.to_crs(METRIC_CRS)
    raw_dist = cumulative_distance_metric(metric)
    keep = np.r_[True, np.diff(raw_dist) > 0.05]
    metric = metric.loc[keep].reset_index(drop=True)
    geo = trimmed_gdf.loc[keep].reset_index(drop=True)
    raw_dist = cumulative_distance_metric(metric)

    line = LineString([p for p in metric.geometry])
    total_len = float(line.length)
    sample_dists = np.arange(0.0, total_len + SAMPLE_INTERVAL_M, SAMPLE_INTERVAL_M)
    if sample_dists[-1] > total_len:
        sample_dists[-1] = total_len

    raw_ele = pd.to_numeric(geo["ele_m"], errors="coerce").interpolate().bfill().ffill().to_numpy(dtype=float)
    sample_ele = np.interp(sample_dists, raw_dist, raw_ele)
    sample_pts_metric = [line.interpolate(float(d)) for d in sample_dists]
    sample_gdf_metric = gpd.GeoDataFrame(
        {"dist_m": sample_dists, "ele_gpx_m": sample_ele},
        geometry=sample_pts_metric,
        crs=METRIC_CRS,
    )
    sample_gdf = sample_gdf_metric.to_crs("EPSG:4326")

    df = pd.DataFrame(
        {
            "sample_idx": np.arange(len(sample_gdf)),
            "dist_m": sample_dists,
            "lat": sample_gdf.geometry.y,
            "lon": sample_gdf.geometry.x,
            "ele_gpx_m": sample_ele,
        }
    )
    df["delta_dist_m"] = df["dist_m"].diff()
    df["delta_ele_m"] = df["ele_gpx_m"].diff()
    df["ele_smooth"] = df["ele_gpx_m"].rolling(41, center=True, min_periods=1).median()
    df["slope_pct"] = (df["ele_smooth"].diff() / df["delta_dist_m"]) * 100.0
    df["slope_band"] = df["slope_pct"].apply(slope_band_from_pct)
    df["gain_m"] = df["delta_ele_m"].clip(lower=0).fillna(0.0)
    df["loss_m"] = (-df["delta_ele_m"].clip(upper=0)).fillna(0.0)
    df["cum_gain_m"] = df["gain_m"].cumsum()
    df["cum_loss_m"] = df["loss_m"].cumsum()
    df["nearest_gpx_idx"] = np.searchsorted(raw_dist, sample_dists, side="left").clip(0, len(raw_dist) - 1)
    df["nearest_gpx_dist_m"] = np.abs(raw_dist[df["nearest_gpx_idx"]] - sample_dists)
    df["time_raw"] = pd.NA

    out_gdf = gpd.GeoDataFrame(df.copy(), geometry=sample_gdf.geometry, crs="EPSG:4326")

    profile_dir = PROJECT_ROOT / "outputs" / "ib1_route_profile" / case["case_id"]
    profile_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(profile_dir / f"{case['case_id']}_route_profile.csv", index=False, encoding="utf-8-sig")
    out_gdf.to_file(profile_dir / f"{case['case_id']}_route_profile_points.geojson", driver="GeoJSON")

    mainline_dir = PROJECT_ROOT / "outputs" / "ib0d_trimmed_mainline" / case["case_id"]
    mainline_dir.mkdir(parents=True, exist_ok=True)
    line_gdf = gpd.GeoDataFrame(
        [{"case_id": case["case_id"], "case_name": case["case_name"], "route_len_m": total_len}],
        geometry=[LineString(list(sample_gdf.geometry))],
        crs="EPSG:4326",
    )
    line_gdf.to_file(mainline_dir / f"{case['case_id']}_mainline_ordered_path_trimmed.geojson", driver="GeoJSON")

    return out_gdf, line_gdf


def read_layer(case_id, layer_name):
    fp = PROJECT_ROOT / "osm_raw_output" / case_id / layer_name
    if not fp.exists():
        return None
    try:
        gdf = gpd.read_file(fp)
    except Exception:
        return None
    if gdf.empty:
        return None
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    return gdf.to_crs(METRIC_CRS)


def nearest_layer(profile_metric, layer_gdf, max_distance=None):
    if layer_gdf is None or layer_gdf.empty:
        return pd.DataFrame(index=profile_metric.index)
    joined = gpd.sjoin_nearest(
        profile_metric,
        layer_gdf,
        how="left",
        max_distance=max_distance,
        distance_col="_dist_m",
    )
    joined = joined[~joined.index.duplicated(keep="first")]
    return joined.reindex(profile_metric.index)


def norm_text(v):
    if pd.isna(v):
        return ""
    s = str(v).strip()
    if s.lower() in {"", "nan", "none", "<na>", "null"}:
        return ""
    return s


def split_flags(flags):
    return [f for f in flags if f]


def classify_surface(surface):
    s = norm_text(surface).lower()
    if s in {"sett", "paving_stones", "paved", "concrete", "asphalt"}:
        return "paved_stone" if s in {"sett", "paving_stones"} else "paved"
    if s in {"ground", "earth", "dirt", "mud", "grass"}:
        return "natural_soil"
    if s in {"rock", "bare_rock", "stone"}:
        return "rock"
    return "unknown"


def score_surface_slip(surface):
    cls = classify_surface(surface)
    return {"paved": 0.05, "paved_stone": 0.25, "natural_soil": 0.45, "rock": 0.50}.get(cls, 0.20)


def score_route_effort(slope_pct):
    if pd.isna(slope_pct):
        return 0.0
    a = abs(float(slope_pct))
    if a >= 25:
        return 0.45
    if a >= 15:
        return 0.30
    if a >= 8:
        return 0.15
    return 0.0


def add_osm_semantics(case, profile_gdf):
    profile_metric = profile_gdf.to_crs(METRIC_CRS)
    out = profile_gdf.drop(columns="geometry").copy()

    highway = read_layer(case["case_id"], "osm_highway_raw.geojson")
    hjoin = nearest_layer(profile_metric, highway, max_distance=30.0)
    out["near_highway"] = hjoin.get("_dist_m", pd.Series(np.nan, index=out.index)).notna().astype(int)
    out["dist_highway_m"] = hjoin.get("_dist_m", pd.Series(np.nan, index=out.index))

    def copy_highway(src_col, out_col):
        out[out_col] = hjoin[src_col] if src_col in hjoin.columns else ""

    copy_highway("name", "osm_way_name")
    copy_highway("name:zh", "osm_way_name_zh")
    copy_highway("osmid", "osm_way_id")
    copy_highway("highway", "osm_highway")
    copy_highway("surface", "osm_surface")
    copy_highway("tracktype", "osm_tracktype")
    copy_highway("smoothness", "osm_smoothness")
    copy_highway("trail_visibility", "osm_trail_visibility")
    copy_highway("sac_scale", "osm_sac_scale")
    copy_highway("incline", "osm_incline")
    copy_highway("lit", "osm_lit")
    copy_highway("handrail", "osm_handrail")
    copy_highway("safety_rope", "osm_safety_rope")
    copy_highway("step_count", "osm_step_count")
    copy_highway("width", "osm_width")
    copy_highway("bridge", "osm_bridge")
    copy_highway("ford", "osm_ford")
    copy_highway("tunnel", "osm_tunnel")
    out["osm_lit_status"] = out["osm_lit"].apply(lambda v: "lit" if norm_text(v).lower() in {"yes", "true", "1"} else "unknown")
    out["osm_highway_family"] = out["osm_highway"].fillna("").astype(str)
    out["osm_walk_relevance"] = "footway_priority"
    out["osm_trail_difficulty_hint"] = out["osm_sac_scale"].apply(lambda v: "mountain_hiking" if norm_text(v) else "unknown")
    out["osm_vertical_context"] = "surface"
    out["osm_is_steps"] = out["osm_highway"].fillna("").astype(str).str.lower().eq("steps").astype(int)

    for key, (fn, threshold) in NEAR_RULES.items():
        layer = read_layer(case["case_id"], fn)
        join = nearest_layer(profile_metric, layer, max_distance=threshold)
        dist = join.get("_dist_m", pd.Series(np.nan, index=out.index))
        out[f"near_{key}"] = dist.notna().astype(int)
        out[f"dist_{key}_m"] = dist

    technical_cols = ["safety_rope", "handrail", "rungs", "ladder", "via_ferrata"]
    hazard_cols = ["cliff", "scree", "bare_rock", "landslide"]
    hydro_cols = ["waterway", "water_area", "wetland"]
    landmark_cols = ["trailhead", "peak", "guidepost"]
    facility_cols = ["shelter", "alpine_hut", "wilderness_hut", "drinking_water", "toilets", "visitor_centre", "information_office"]
    rest_cols = ["bench", "picnic_table", "picnic_site"]
    support_cols = facility_cols + rest_cols

    for label, cols in [
        ("technical_flags", technical_cols),
        ("hazard_flags", hazard_cols),
        ("hydrology_flags", hydro_cols),
        ("landmark_flags", landmark_cols),
        ("facility_flags", facility_cols),
        ("rest_flags", rest_cols),
        ("support_flags", support_cols),
    ]:
        out[label] = out.apply(
            lambda r: "|".join(split_flags([c for c in cols if int(r.get(f"near_{c}", 0)) == 1])) or "none",
            axis=1,
        )

    out["safety_flags"] = out["technical_flags"]
    out["nearby_named_features"] = ""
    out["surface_class"] = out["osm_surface"].apply(classify_surface)
    out["route_semantic_class"] = out["osm_highway"].fillna("").replace("", "unknown")
    out["assist_class"] = out["technical_flags"].apply(lambda v: "assisted" if v != "none" else "none")
    out["visibility_class"] = out["osm_trail_visibility"].apply(lambda v: "clear_visibility" if norm_text(v).lower() in {"good", "excellent"} else "unknown")
    out["osm_difficulty_class"] = out["osm_sac_scale"].apply(lambda v: norm_text(v) or "unknown")

    out["exposure_risk_score"] = (
        out["near_cliff"] * 0.70
        + out["near_scree"] * 0.30
        + out["near_bare_rock"] * 0.25
    ).clip(0, 1)
    out["hydrology_risk_score"] = (
        out["near_waterway"] * 0.45
        + out["near_water_area"] * 0.45
        + out["near_wetland"] * 0.60
    ).clip(0, 1)
    out["landmark_context_score"] = out["near_peak"] * 0.10
    out["navigation_risk_score"] = np.where(out["near_guidepost"].eq(1), 0.0, 0.05)
    out["navigation_support_score"] = np.where(out["near_guidepost"].eq(1), -0.20, 0.0)
    out["night_navigation_risk_score"] = 0.25
    out["night_navigation_support_score"] = 0.0
    out["rest_support_score"] = np.where(out["rest_flags"].ne("none"), -0.10, 0.0)
    out["route_continuity_context_score"] = np.where(out["near_highway"].eq(1), 0.0, 0.20)
    out["route_effort_risk_score"] = out["slope_pct"].apply(score_route_effort)
    out["route_type_risk_score"] = np.where(out["osm_highway"].fillna("").astype(str).str.lower().eq("steps"), 0.35, 0.25)
    out["support_score"] = np.where(out["support_flags"].ne("none"), -0.15, 0.0)
    out["surface_slip_risk_score"] = out["osm_surface"].apply(score_surface_slip)
    out["technical_risk_score"] = np.where(out["technical_flags"].ne("none"), 0.45, 0.0)
    out["terrain_risk_score"] = 0.0

    out["applied_mapping_hits"] = ""
    out["conditional_factor_flags"] = ""
    out["conditional_risk_domains"] = ""
    out["conditional_notes"] = ""
    out["weather_sensitive_flags"] = out.apply(
        lambda r: "|".join(
            split_flags(
                [
                    "surface_slip" if r["surface_slip_risk_score"] >= 0.25 else "",
                    "hydrology" if r["hydrology_flags"] != "none" else "",
                ]
            )
        ),
        axis=1,
    )
    out["needs_nlsc_flags"] = out["hydrology_flags"].replace("none", "")
    out["needs_activity_flags"] = ""
    out["unhandled_risk_domains"] = ""
    out["osm_semantic_risk_score_raw"] = (
        out["exposure_risk_score"] * 0.18
        + out["hydrology_risk_score"] * 0.20
        + out["navigation_risk_score"] * 0.10
        + out["route_effort_risk_score"] * 0.15
        + out["route_type_risk_score"] * 0.10
        + out["surface_slip_risk_score"] * 0.17
        + out["technical_risk_score"] * 0.10
    ).clip(0, 1)
    out["osm_semantic_risk_score"] = out["osm_semantic_risk_score_raw"].clip(0, 1)
    out["osm_semantic_risk_band"] = out["osm_semantic_risk_score"].apply(risk_band)

    gdf = gpd.GeoDataFrame(out.copy(), geometry=profile_gdf.geometry, crs="EPSG:4326")

    sem_dir = PROJECT_ROOT / "outputs" / "ib1c_route_profile_semantics" / case["case_id"]
    sem_dir.mkdir(parents=True, exist_ok=True)
    out.to_csv(sem_dir / f"{case['case_id']}_route_profile_semantic_enriched.csv", index=False, encoding="utf-8-sig")
    gdf.to_file(sem_dir / f"{case['case_id']}_route_profile_semantic_enriched.geojson", driver="GeoJSON")

    risk_dir = PROJECT_ROOT / "outputs" / "ib1c_osm_semantic_risk" / case["case_id"]
    risk_dir.mkdir(parents=True, exist_ok=True)
    out.to_csv(risk_dir / f"{case['case_id']}_osm_semantic_risk_profile.csv", index=False, encoding="utf-8-sig")
    gdf.to_file(risk_dir / f"{case['case_id']}_osm_semantic_risk_profile.geojson", driver="GeoJSON")
    pd.DataFrame(
        [
            {"metric": "case_id", "value": case["case_id"]},
            {"metric": "rows", "value": len(out)},
            {"metric": "osm_semantic_risk_score_mean", "value": float(out["osm_semantic_risk_score"].mean())},
        ]
    ).to_csv(risk_dir / f"{case['case_id']}_osm_semantic_risk_summary.csv", index=False, encoding="utf-8-sig")
    return gdf


def guess_contour_elev_col(gdf):
    candidates = ["zv2", "ELEV", "elev", "Elevation", "height", "Z", "z"]
    for c in candidates:
        if c in gdf.columns:
            return c
    for c in gdf.columns:
        vals = pd.to_numeric(gdf[c], errors="coerce")
        if vals.notna().sum() > len(gdf) * 0.5 and vals.between(0, 4000).mean() > 0.8:
            return c
    raise ValueError("cannot find contour elevation column")


def contour_band(slope):
    if pd.isna(slope):
        return "unknown"
    if slope < 0.05:
        return "flat"
    if slope < 0.15:
        return "gentle"
    if slope < 0.30:
        return "moderate"
    if slope < 0.45:
        return "steep"
    return "very_steep"


def build_contour_features(case, line_gdf):
    contours = gpd.read_file(CONTOUR_FP)
    if contours.crs is None:
        contours = contours.set_crs(METRIC_CRS)
    contours = contours.to_crs(METRIC_CRS)
    elev_col = guess_contour_elev_col(contours)
    contours["_elev"] = pd.to_numeric(contours[elev_col], errors="coerce")
    sidx = contours.sindex
    line_metric = line_gdf.to_crs(METRIC_CRS).geometry.iloc[0]
    total = float(line_metric.length)
    rows = []
    for start in np.arange(0.0, total, CONTOUR_SEGMENT_LEN_M):
        end = min(start + CONTOUR_SEGMENT_LEN_M, total)
        mid = (start + end) / 2.0
        midpt = line_metric.interpolate(mid)
        window = midpt.buffer(CONTOUR_WINDOW_RADIUS_M)
        hits = list(sidx.query(window, predicate="intersects"))
        subset = contours.iloc[hits] if hits else contours.iloc[[]]
        elevs = subset["_elev"].dropna()
        elev_min = float(elevs.min()) if len(elevs) else np.nan
        elev_max = float(elevs.max()) if len(elevs) else np.nan
        elev_range = elev_max - elev_min if len(elevs) else np.nan
        slope_window = elev_range / (CONTOUR_WINDOW_RADIUS_M * 2.0) if pd.notna(elev_range) else np.nan
        rows.append(
            {
                "seg_id": len(rows),
                "dist_mid": mid,
                "terrain_seg_len": end - start,
                "terrain_elev_min": elev_min,
                "terrain_elev_max": elev_max,
                "terrain_elev_range": elev_range,
                "terrain_slope_window": slope_window,
                "terrain_slope_band_window": contour_band(slope_window),
                "terrain_contour_density_20m": int(len(subset)),
                "terrain_pipeline_stage": "gpx_direct_contour_window",
                "terrain_case_id": case["case_id"],
                "terrain_case_name": case["case_name"],
                "terrain_derived_at": datetime.now(timezone.utc).isoformat(),
                "terrain_segment_len_m": CONTOUR_SEGMENT_LEN_M,
                "terrain_window_radius_m": CONTOUR_WINDOW_RADIUS_M,
                "terrain_density_buffer_m": CONTOUR_DENSITY_BUFFER_M,
                "terrain_elevation_source": str(CONTOUR_FP),
                "geometry": midpt,
            }
        )
    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=METRIC_CRS).to_crs("EPSG:4326")
    out_dir = PROJECT_ROOT / "outputs" / "ib1g_contour_window_features" / case["case_id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(gdf.drop(columns="geometry")).to_csv(out_dir / f"{case['case_id']}_contour_window_features.csv", index=False, encoding="utf-8-sig")
    gdf.to_file(out_dir / f"{case['case_id']}_contour_window_features.geojson", driver="GeoJSON")
    return pd.DataFrame(gdf.drop(columns="geometry"))


def terrain_window_risk_score(row):
    band = norm_text(row.get("terrain_slope_band_window")).lower() or "unknown"
    base = SLOPE_BAND_WINDOW_SCORE.get(band, 0.20)
    elev_range = pd.to_numeric(row.get("terrain_elev_range", 0.0), errors="coerce")
    density = pd.to_numeric(row.get("terrain_contour_density_20m", 0.0), errors="coerce")
    elev_range = 0.0 if pd.isna(elev_range) else float(elev_range)
    density = 0.0 if pd.isna(density) else float(density)
    return clamp(base + min(elev_range / 70.0, 1.0) * 0.15 + min(density / 5.0, 1.0) * 0.05)


def hydro_terrain_amplifier_score(row):
    hydrology = str(row.get("hydrology_flags", ""))
    needs_nlsc = str(row.get("needs_nlsc_flags", ""))
    has_hydro = any(k in hydrology or k in needs_nlsc for k in ["waterway", "wetland"])
    if not has_hydro:
        return 0.0
    terrain_score = float(row.get("terrain_window_risk_score", 0.0))
    surface = norm_text(row.get("osm_surface")).lower()
    route_type = norm_text(row.get("osm_highway")).lower()
    bonus = 0.0
    if surface in {"sett", "wood", "rock", "mud", "earth", "dirt"}:
        bonus += 0.10
    if route_type == "steps":
        bonus += 0.05
    return clamp(terrain_score * 0.50 + bonus, 0.0, 0.70)


def risk_band(score):
    score = float(score)
    if score < 0.20:
        return "low"
    if score < 0.40:
        return "moderate"
    if score < 0.65:
        return "high"
    return "very_high"


def combine_ib1e(case, osm_risk_gdf, terrain_df):
    terrain_sorted = terrain_df.sort_values("dist_mid").reset_index(drop=True)
    terrain_dist = terrain_sorted["dist_mid"].astype(float).to_numpy()
    rows = []
    for _, row in osm_risk_gdf.drop(columns="geometry").iterrows():
        d = float(row["dist_m"])
        idx = int(np.abs(terrain_dist - d).argmin())
        tr = terrain_sorted.iloc[idx].copy()
        merged = row.to_dict()
        for c, v in tr.items():
            if c != "geometry":
                merged[c] = v
        merged["terrain_match_dist_m"] = abs(float(tr["dist_mid"]) - d)
        merged["terrain_match_ok"] = merged["terrain_match_dist_m"] <= 20.0
        rows.append(merged)
    out = pd.DataFrame(rows)
    out["terrain_window_risk_score"] = out.apply(terrain_window_risk_score, axis=1)
    out["hydro_terrain_amplifier_score"] = out.apply(hydro_terrain_amplifier_score, axis=1)
    out["osm_terrain_combined_risk_score"] = (
        out["osm_semantic_risk_score"] * 0.35
        + out["terrain_window_risk_score"] * 0.45
        + out["hydro_terrain_amplifier_score"] * 0.20
    ).clip(0, 1)
    out["osm_terrain_combined_risk_band"] = out["osm_terrain_combined_risk_score"].apply(risk_band)
    out["terrain_risk_reason"] = out.apply(
        lambda r: f"slope_band_window={r.get('terrain_slope_band_window', 'unknown')}|elev_range={r.get('terrain_elev_range', '')}|hydro={r.get('hydrology_flags', 'none')}",
        axis=1,
    )

    gdf = gpd.GeoDataFrame(out.copy(), geometry=osm_risk_gdf.geometry, crs="EPSG:4326")
    out_dir = PROJECT_ROOT / "outputs" / "ib1e_osm_nlsc_terrain_risk" / case["case_id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_dir / f"{case['case_id']}_osm_nlsc_terrain_risk_profile.csv", index=False, encoding="utf-8-sig")
    gdf.to_file(out_dir / f"{case['case_id']}_osm_nlsc_terrain_risk_profile.geojson", driver="GeoJSON")

    summary = [
        ("case_id", case["case_id"]),
        ("rows", len(out)),
        ("terrain_match_ok_n", int(out["terrain_match_ok"].sum())),
        ("osm_semantic_risk_score_mean", float(out["osm_semantic_risk_score"].mean())),
        ("terrain_window_risk_score_mean", float(out["terrain_window_risk_score"].mean())),
        ("hydro_terrain_amplifier_score_mean", float(out["hydro_terrain_amplifier_score"].mean())),
        ("osm_terrain_combined_risk_score_mean", float(out["osm_terrain_combined_risk_score"].mean())),
    ]
    for band, n in out["osm_terrain_combined_risk_band"].value_counts().items():
        summary.append((f"combined_band_{band}_n", int(n)))
    pd.DataFrame(summary, columns=["metric", "value"]).to_csv(
        out_dir / f"{case['case_id']}_osm_nlsc_terrain_risk_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return out


def process_case(case):
    gpx_fp = PROJECT_ROOT / "activity_input" / "gpx" / case["gpx_path"]
    if not gpx_fp.exists():
        raise FileNotFoundError(gpx_fp)
    trimmed, summit_idx, original_n = load_trimmed_gpx(gpx_fp)
    profile_gdf, line_gdf = build_route_profile(case, trimmed)
    osm_risk_gdf = add_osm_semantics(case, profile_gdf)
    terrain_df = build_contour_features(case, line_gdf)
    combined = combine_ib1e(case, osm_risk_gdf, terrain_df)
    print(
        f"{case['case_id']}: original_points={original_n}, trimmed_to_idx={summit_idx}, "
        f"profile_points={len(combined)}, dist_km={combined['dist_m'].max()/1000:.2f}, "
        f"mean_combined_risk={combined['osm_terrain_combined_risk_score'].mean():.3f}"
    )


def main():
    ensure_inputs()
    only = os.environ.get("CASE_ID", "").strip()
    selected = [c for c in CASES if not only or c["case_id"] == only]
    if not selected:
        raise ValueError(f"unknown CASE_ID: {only}")
    for case in selected:
        process_case(case)


if __name__ == "__main__":
    main()
