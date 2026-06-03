# =========================================================
# ib1c_enrich_route_profile_semantics.py
# 讀取 ib1a route profile，接上 ia1 OSM raw semantic layers
# 輸出 technical / hazard / hydrology / facility / rest 等語意欄位
# =========================================================

from pathlib import Path
import argparse

import pandas as pd
import geopandas as gpd


# =========================================================
# 0. 路徑設定
# =========================================================
PROJECT_ROOT = Path("C:/mountain_work/115_osm")


def resolve_path(value, project_root=PROJECT_ROOT):
    if value is None:
        return None
    p = Path(value)
    if p.is_absolute():
        return p
    return project_root / p


def parse_args():
    parser = argparse.ArgumentParser(
        description="ib1c: enrich ib1a route profile with OSM semantic layers"
    )
    parser.add_argument("--case-id", default="juansi_waterfall_fitcsv_20260503")
    parser.add_argument("--case-name", default=None)
    parser.add_argument(
        "--profile-csv",
        default=None,
        help="ib1a route profile CSV. Default: outputs/ib1_route_profile/<case-id>/<case-id>_route_profile.csv",
    )
    parser.add_argument(
        "--profile-geojson",
        default=None,
        help="ib1a route profile points GeoJSON. Default: outputs/ib1_route_profile/<case-id>/<case-id>_route_profile_points.geojson",
    )
    parser.add_argument(
        "--osm-raw-dir",
        default=None,
        help="ia1 / per-CASE_ID OSM raw folder. Default: osm_raw_output/<case-id>",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Output folder. Default: outputs/ib1c_route_profile_semantics/<case-id>",
    )
    parser.add_argument("--near-technical-m", type=float, default=40.0)
    parser.add_argument("--near-hazard-m", type=float, default=60.0)
    parser.add_argument("--near-waterway-m", type=float, default=35.0)
    parser.add_argument("--near-poi-m", type=float, default=25.0)
    parser.add_argument("--near-highway-m", type=float, default=30.0)
    return parser.parse_args()


args = parse_args()

CASE_ID = args.case_id
CASE_NAME = args.case_name or args.case_id

if args.profile_csv is None:
    PROFILE_CSV = (
        PROJECT_ROOT
        / "outputs"
        / "ib1_route_profile"
        / CASE_ID
        / f"{CASE_ID}_route_profile.csv"
    )
else:
    PROFILE_CSV = resolve_path(args.profile_csv)

if args.profile_geojson is None:
    PROFILE_GEOJSON = (
        PROJECT_ROOT
        / "outputs"
        / "ib1_route_profile"
        / CASE_ID
        / f"{CASE_ID}_route_profile_points.geojson"
    )
else:
    PROFILE_GEOJSON = resolve_path(args.profile_geojson)

if args.osm_raw_dir is None:
    IA1_DIR = PROJECT_ROOT / "osm_raw_output" / CASE_ID
else:
    IA1_DIR = resolve_path(args.osm_raw_dir)

IA1_DATASET_ID = IA1_DIR.name

OSM_HIGHWAY_FP = IA1_DIR / "osm_highway_raw.geojson"

if args.out_dir is None:
    OUT_DIR = PROJECT_ROOT / "outputs" / "ib1c_route_profile_semantics" / CASE_ID
else:
    OUT_DIR = resolve_path(args.out_dir)

OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_CSV = OUT_DIR / f"{CASE_ID}_route_profile_semantic_enriched.csv"
OUT_GEOJSON = OUT_DIR / f"{CASE_ID}_route_profile_semantic_enriched.geojson"




# =========================================================
# 1. 參數
# =========================================================
# 線狀/面狀圖層距離門檻
# technical
NEAR_TECHNICAL_M = args.near_technical_m

# hazard
NEAR_HAZARD_M = args.near_hazard_m

# hydrology
NEAR_WATERWAY_M = args.near_waterway_m

# 點狀設施距離門檻
# POI / facility
NEAR_POI_M = args.near_poi_m

# OSM highway/path 線段距離門檻
# 用於將 route profile point 對應到最近 OSM 路線線段
NEAR_HIGHWAY_M = args.near_highway_m


# =========================================================
# 2. ia1 圖層設定
# =========================================================
SEMANTIC_LAYERS = {
    # technical / safety
    "safety_rope": {
        "fp": IA1_DIR / "osm_safety_rope_raw.geojson",
        "category": "technical",
        "threshold_m": NEAR_TECHNICAL_M,
    },
    "assisted_trail": {
        "fp": IA1_DIR / "osm_assisted_trail_raw.geojson",
        "category": "technical",
        "threshold_m": NEAR_TECHNICAL_M,
    },
    "handrail": {
        "fp": IA1_DIR / "osm_handrail_raw.geojson",
        "category": "technical",
        "threshold_m": NEAR_TECHNICAL_M,
    },
    "rungs": {
        "fp": IA1_DIR / "osm_rungs_raw.geojson",
        "category": "technical",
        "threshold_m": NEAR_TECHNICAL_M,
    },
    "ladder": {
        "fp": IA1_DIR / "osm_ladder_raw.geojson",
        "category": "technical",
        "threshold_m": NEAR_TECHNICAL_M,
    },
    "via_ferrata": {
        "fp": IA1_DIR / "osm_via_ferrata_raw.geojson",
        "category": "technical",
        "threshold_m": NEAR_TECHNICAL_M,
    },
    "street_lamp": {
        "fp": IA1_DIR / "osm_street_lamp_raw.geojson",
        "category": "safety",
        "threshold_m": NEAR_POI_M,
    },

    # hazard / terrain
    "cliff": {
        "fp": IA1_DIR / "osm_cliff_raw.geojson",
        "category": "hazard",
        "threshold_m": NEAR_HAZARD_M,
    },
    "scree": {
        "fp": IA1_DIR / "osm_scree_raw.geojson",
        "category": "hazard",
        "threshold_m": NEAR_HAZARD_M,
    },
    "bare_rock": {
        "fp": IA1_DIR / "osm_bare_rock_raw.geojson",
        "category": "hazard",
        "threshold_m": NEAR_HAZARD_M,
    },
    "landslide": {
        "fp": IA1_DIR / "osm_landslide_raw.geojson",
        "category": "hazard",
        "threshold_m": NEAR_HAZARD_M,
    },

    # hydrology
    "waterway": {
        "fp": IA1_DIR / "osm_waterway_raw.geojson",
        "category": "hydrology",
        "threshold_m": NEAR_WATERWAY_M,
    },
    "water_area": {
        "fp": IA1_DIR / "osm_water_area_raw.geojson",
        "category": "hydrology",
        "threshold_m": NEAR_WATERWAY_M,
    },
    "wetland": {
        "fp": IA1_DIR / "osm_wetland_raw.geojson",
        "category": "hydrology",
        "threshold_m": NEAR_WATERWAY_M,
    },

    # landmark
    "trailhead": {
        "fp": IA1_DIR / "osm_trailhead_raw.geojson",
        "category": "landmark",
        "threshold_m": NEAR_POI_M,
    },
    "peak": {
        "fp": IA1_DIR / "osm_peak_raw.geojson",
        "category": "landmark",
        "threshold_m": NEAR_POI_M,
    },
    "guidepost": {
        "fp": IA1_DIR / "osm_guidepost_raw.geojson",
        "category": "landmark",
        "threshold_m": NEAR_POI_M,
    },

    # refuge / rest / support
    "shelter": {
        "fp": IA1_DIR / "osm_shelter_raw.geojson",
        "category": "facility",
        "threshold_m": NEAR_POI_M,
    },
    "alpine_hut": {
        "fp": IA1_DIR / "osm_alpine_hut_raw.geojson",
        "category": "facility",
        "threshold_m": NEAR_POI_M,
    },
    "wilderness_hut": {
        "fp": IA1_DIR / "osm_wilderness_hut_raw.geojson",
        "category": "facility",
        "threshold_m": NEAR_POI_M,
    },
    "bench": {
        "fp": IA1_DIR / "osm_bench_raw.geojson",
        "category": "rest",
        "threshold_m": NEAR_POI_M,
    },
    "picnic_table": {
        "fp": IA1_DIR / "osm_picnic_table_raw.geojson",
        "category": "rest",
        "threshold_m": NEAR_POI_M,
    },
    "picnic_site": {
        "fp": IA1_DIR / "osm_picnic_site_raw.geojson",
        "category": "rest",
        "threshold_m": NEAR_POI_M,
    },
    "drinking_water": {
        "fp": IA1_DIR / "osm_drinking_water_raw.geojson",
        "category": "support",
        "threshold_m": NEAR_POI_M,
    },
    "toilets": {
        "fp": IA1_DIR / "osm_toilets_raw.geojson",
        "category": "support",
        "threshold_m": NEAR_POI_M,
    },
    "visitor_centre": {
        "fp": IA1_DIR / "osm_visitor_centre_raw.geojson",
        "category": "support",
        "threshold_m": NEAR_POI_M,
    },
    "information_office": {
        "fp": IA1_DIR / "osm_information_office_raw.geojson",
        "category": "support",
        "threshold_m": NEAR_POI_M,
    },
}


# =========================================================
# 3. 工具函式
# =========================================================
def load_layer(fp: Path, target_crs):
    if not fp.exists():
        return None

    try:
        gdf = gpd.read_file(fp)
    except Exception as e:
        print(f"讀取失敗，略過：{fp} error={e}")
        return None

    if gdf.empty or "geometry" not in gdf.columns:
        return None

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")

    return gdf.to_crs(target_crs)


def safe_text(v):
    if isinstance(v, list):
        return str(v[0]) if v else ""
    if pd.isna(v):
        return ""
    return str(v)


def nearest_layer_info(pt_geom, layer_gdf, threshold_m):
    """
    回傳此 profile point 與某 OSM layer 的最近物件資訊。
    """
    if layer_gdf is None or layer_gdf.empty:
        return {
            "hit": 0,
            "dist_m": None,
            "name": "",
            "osm_id": "",
            "osm_type": "",
        }

    dists = layer_gdf.geometry.distance(pt_geom)
    idx = dists.idxmin()
    min_dist = float(dists.loc[idx])

    if min_dist <= threshold_m:
        row = layer_gdf.loc[idx]
        return {
            "hit": 1,
            "dist_m": min_dist,
            "name": safe_text(row.get("name", "")),
            "osm_id": safe_text(row.get("osm_id", "")),
            "osm_type": safe_text(row.get("osm_type", "")),
        }

    return {
        "hit": 0,
        "dist_m": min_dist,
        "name": "",
        "osm_id": "",
        "osm_type": "",
    }

def nearest_highway_info(pt_geom, highway_gdf, threshold_m=30.0):
    """
    找距離 profile point 最近的 OSM highway/path 線段，
    回傳 highway / surface / tracktype 等路線語意。
    """
    empty_result = {
        "hit": 0,
        "dist_m": None,
        "name": "",
        "name_zh": "",
        "osm_id": "",
        "osm_type": "",
        "highway": "",
        "surface": "",
        "tracktype": "",
        "smoothness": "",
        "trail_visibility": "",
        "sac_scale": "",
        "incline": "",
        "lit": "",
        "lit_status": "",
        "handrail": "",
        "safety_rope": "",
        "step_count": "",
        "width": "",
        "bridge": "",
        "bridge_material": "",
        "ford": "",
        "tunnel": "",
        "covered": "",
        "highway_family": "",
        "walk_relevance": "",
        "trail_difficulty_hint": "",
        "vertical_context": "",
        "is_steps": "",
    }

    if highway_gdf is None or highway_gdf.empty:
        return empty_result

    dists = highway_gdf.geometry.distance(pt_geom)
    idx = dists.idxmin()
    min_dist = float(dists.loc[idx])

    if min_dist > threshold_m:
        result = empty_result.copy()
        result["dist_m"] = min_dist
        return result

    row = highway_gdf.loc[idx]

    return {
        "hit": 1,
        "dist_m": min_dist,
        "name": safe_text(row.get("name", "")),
        "name_zh": safe_text(row.get("name:zh", "")),
        "osm_id": safe_text(row.get("osm_id", "")),
        "osm_type": safe_text(row.get("osm_type", "")),
        "highway": safe_text(row.get("highway", "")),
        "surface": safe_text(row.get("surface", "")),
        "tracktype": safe_text(row.get("tracktype", "")),
        "smoothness": safe_text(row.get("smoothness", "")),
        "trail_visibility": safe_text(row.get("trail_visibility", "")),
        "sac_scale": safe_text(row.get("sac_scale", "")),
        "incline": safe_text(row.get("incline", "")),
        "lit": safe_text(row.get("lit", "")),
        "lit_status": safe_text(row.get("lit_status", "")),
        "handrail": safe_text(row.get("handrail", "")),
        "safety_rope": safe_text(row.get("safety_rope", "")),
        "step_count": safe_text(row.get("step_count", "")),
        "width": safe_text(row.get("width", "")),
        "bridge": safe_text(row.get("bridge", "")),
        "bridge_material": safe_text(row.get("bridge_material", "")),
        "ford": safe_text(row.get("ford", "")),
        "tunnel": safe_text(row.get("tunnel", "")),
        "covered": safe_text(row.get("covered", "")),
        "highway_family": safe_text(row.get("highway_family", "")),
        "walk_relevance": safe_text(row.get("walk_relevance", "")),
        "trail_difficulty_hint": safe_text(row.get("trail_difficulty_hint", "")),
        "vertical_context": safe_text(row.get("vertical_context", "")),
        "is_steps": safe_text(row.get("is_steps", "")),
    }


def append_unique(items, value):
    if value and value not in items:
        items.append(value)

def norm_tag(v):
    """
    將 OSM tag 轉成乾淨小寫字串。
    並將 nan / none / <NA> / null 等缺值字串視為空值。
    """
    if isinstance(v, list):
        v = v[0] if v else ""

    if pd.isna(v):
        return ""

    text = str(v).strip().strip('"').strip().lower()

    if text in {"", "nan", "none", "<na>", "na", "null", "nat"}:
        return ""

    return text


def has_osm_value(v):
    """
    判斷 OSM tag 是否真的有有效值。
    """
    text = norm_tag(v)
    return text not in {"", "no", "false", "0"}


def is_yes(v):
    text = norm_tag(v)
    return text in {"yes", "true", "1", "designated"}


def classify_surface(row):
    """
    將 OSM surface / tracktype / highway 轉成簡報用地表材質分類。
    """
    highway = norm_tag(row.get("osm_highway", ""))
    surface = norm_tag(row.get("osm_surface", ""))
    tracktype = norm_tag(row.get("osm_tracktype", ""))

    if surface in {"asphalt"}:
        return "paved_asphalt"

    if surface in {"concrete"}:
        return "paved_concrete"

    if surface in {"paving_stones", "sett", "paved", "stone"}:
        return "paved_stone"

    if surface in {"gravel", "fine_gravel", "pebblestone", "compacted"}:
        return "gravel_compacted"

    if surface in {"dirt", "earth", "ground", "mud", "sand", "grass"}:
        return "natural_ground"

    if surface in {"rock", "bare_rock"}:
        return "rock"

    if surface in {"wood", "boardwalk"}:
        return "wood_boardwalk"

    if tracktype in {"grade1"}:
        return "paved_or_compacted"

    if tracktype in {"grade2", "grade3"}:
        return "gravel_or_ground"

    if tracktype in {"grade4", "grade5"}:
        return "rough_ground"

    if highway in {"path", "footway", "track", "steps"}:
        return "trail_unknown_surface"

    return "unknown_surface"


def classify_route_semantic(row):
    """
    將 OSM highway / bridge / tunnel / ford 轉成通行型態分類。
    handrail / safety_rope 不放在這裡，改由 assist_class 表示。
    """
    highway = norm_tag(row.get("osm_highway", ""))

    if highway == "ladder":
        return "ladder"

    if highway == "via_ferrata":
        return "via_ferrata"

    if highway == "steps":
        return "steps"

    if has_osm_value(row.get("osm_bridge", "")):
        return "bridge"

    if has_osm_value(row.get("osm_tunnel", "")):
        return "tunnel"

    if has_osm_value(row.get("osm_ford", "")):
        return "ford"

    if highway == "footway":
        return "footway"

    if highway == "path":
        return "path"

    if highway == "track":
        return "track"

    if highway == "service":
        return "service_road"

    if highway in {
        "residential",
        "unclassified",
        "tertiary",
        "secondary",
        "primary",
        "road",
        "living_street",
    }:
        return "road"

    return "unknown_route_type"


def classify_assist(row):
    """
    將 handrail / safety_rope 統整成輔助設施分類。
    """
    has_handrail = has_osm_value(row.get("osm_handrail", ""))
    has_rope = has_osm_value(row.get("osm_safety_rope", ""))

    if has_handrail and has_rope:
        return "handrail_and_safety_rope"

    if has_rope:
        return "safety_rope"

    if has_handrail:
        return "handrail"

    return "none"


def classify_visibility(row):
    """
    將 trail_visibility 收斂成簡報用分類。
    """
    v = norm_tag(row.get("osm_trail_visibility", ""))

    if v in {"excellent", "good"}:
        return "clear_visibility"

    if v in {"intermediate"}:
        return "intermediate_visibility"

    if v in {"bad", "horrible", "no"}:
        return "poor_visibility"

    return "unknown_visibility"


def classify_osm_difficulty(row):
    """
    根據 sac_scale 轉成簡報用難度分類。
    """
    sac = norm_tag(row.get("osm_sac_scale", ""))

    if sac == "hiking":
        return "easy_hiking"

    if sac == "mountain_hiking":
        return "mountain_hiking"

    if sac == "demanding_mountain_hiking":
        return "demanding"

    if sac in {"alpine_hiking", "demanding_alpine_hiking", "difficult_alpine_hiking"}:
        return "alpine_or_technical"

    return "unknown_difficulty"


# =========================================================
# 4. 檢查輸入
# =========================================================
for fp in [PROFILE_CSV, PROFILE_GEOJSON]:
    if not fp.exists():
        raise FileNotFoundError(f"找不到檔案：{fp.resolve()}")


# =========================================================
# 5. 讀 profile
# =========================================================
profile_df = pd.read_csv(PROFILE_CSV)
profile_pts = gpd.read_file(PROFILE_GEOJSON).to_crs("EPSG:4326")

metric_crs = profile_pts.estimate_utm_crs()
profile_pts_m = profile_pts.to_crs(metric_crs)

print("case:", CASE_ID)
print("case_name:", CASE_NAME)
print("profile_csv:", PROFILE_CSV.resolve())
print("profile_geojson:", PROFILE_GEOJSON.resolve())
print("osm_raw_dir:", IA1_DIR.resolve())
print("ia1_dataset_id:", IA1_DATASET_ID)
print("out_dir:", OUT_DIR.resolve())
print("profile points:", len(profile_pts))
print("metric CRS:", metric_crs)

# =========================================================
# 5a. 載入 OSM highway raw layer
# =========================================================
highway_gdf = load_layer(OSM_HIGHWAY_FP, metric_crs)

if highway_gdf is None or highway_gdf.empty:
    print("highway layer missing/empty")
    highway_gdf = None
else:
    highway_gdf = highway_gdf[
        highway_gdf.geometry.type.isin(["LineString", "MultiLineString"])
    ].copy()
    print(f"highway layer loaded: n={len(highway_gdf)}")


# =========================================================
# 6. 載入 ia1 semantic layers
# =========================================================
loaded_layers = {}

for layer_name, cfg in SEMANTIC_LAYERS.items():
    gdf = load_layer(cfg["fp"], metric_crs)
    loaded_layers[layer_name] = gdf

    if gdf is None:
        print(f"layer missing/empty: {layer_name}")
    else:
        print(f"layer loaded: {layer_name}, n={len(gdf)}")

print("\n=== loaded layer summary ===")
for name, gdf in loaded_layers.items():
    if gdf is not None:
        print(name, len(gdf))

# =========================================================
# 7. 對每個 profile point 做語意補強
# =========================================================
enriched_rows = []

for idx, pt_row in profile_pts_m.iterrows():
    pt_geom = pt_row.geometry

    technical_hits = []
    safety_hits = []
    hazard_hits = []
    hydrology_hits = []
    landmark_hits = []
    facility_hits = []
    rest_hits = []
    support_hits = []

    nearest_names = []

    highway_info = nearest_highway_info(
        pt_geom,
        highway_gdf,
        threshold_m=NEAR_HIGHWAY_M,
    )


    result = {
        "sample_idx": idx,

        # 最近 OSM highway/path 線段屬性
        "near_highway": highway_info["hit"],
        "dist_highway_m": highway_info["dist_m"],
        "osm_way_name": highway_info["name"],
        "osm_way_name_zh": highway_info["name_zh"],
        "osm_way_id": highway_info["osm_id"],
        "osm_way_type": highway_info["osm_type"],
        "osm_highway": highway_info["highway"],
        "osm_surface": highway_info["surface"],
        "osm_tracktype": highway_info["tracktype"],
        "osm_smoothness": highway_info["smoothness"],
        "osm_trail_visibility": highway_info["trail_visibility"],
        "osm_sac_scale": highway_info["sac_scale"],
        "osm_incline": highway_info["incline"],
        "osm_lit": highway_info["lit"],
        "osm_lit_status": highway_info["lit_status"],
        "osm_handrail": highway_info["handrail"],
        "osm_safety_rope": highway_info["safety_rope"],
        "osm_step_count": highway_info["step_count"],
        "osm_width": highway_info["width"],
        "osm_bridge": highway_info["bridge"],
        "osm_bridge_material": highway_info["bridge_material"],
        "osm_ford": highway_info["ford"],
        "osm_tunnel": highway_info["tunnel"],
        "osm_covered": highway_info["covered"],
        "osm_highway_family": highway_info["highway_family"],
        "osm_walk_relevance": highway_info["walk_relevance"],
        "osm_trail_difficulty_hint": highway_info["trail_difficulty_hint"],
        "osm_vertical_context": highway_info["vertical_context"],
        "osm_is_steps": highway_info["is_steps"],
    }

    for layer_name, cfg in SEMANTIC_LAYERS.items():
        layer_gdf = loaded_layers[layer_name]
        threshold_m = cfg["threshold_m"]
        category = cfg["category"]

        info = nearest_layer_info(pt_geom, layer_gdf, threshold_m)

        hit_col = f"near_{layer_name}"
        dist_col = f"dist_{layer_name}_m"

        result[hit_col] = info["hit"]
        result[dist_col] = info["dist_m"]

        if info["hit"] == 1:
            if category == "technical":
                append_unique(technical_hits, layer_name)
            elif category == "safety":
                append_unique(safety_hits, layer_name)
            elif category == "hazard":
                append_unique(hazard_hits, layer_name)
            elif category == "hydrology":
                append_unique(hydrology_hits, layer_name)
            elif category == "landmark":
                append_unique(landmark_hits, layer_name)
            elif category == "facility":
                append_unique(facility_hits, layer_name)
            elif category == "rest":
                append_unique(rest_hits, layer_name)
            elif category == "support":
                append_unique(support_hits, layer_name)

            if info["name"]:
                append_unique(nearest_names, f"{layer_name}:{info['name']}")

    result["technical_flags"] = "|".join(technical_hits) if technical_hits else "normal"
    result["safety_flags"] = "|".join(safety_hits) if safety_hits else "normal"
    result["hazard_flags"] = "|".join(hazard_hits) if hazard_hits else "normal"
    result["hydrology_flags"] = "|".join(hydrology_hits) if hydrology_hits else "normal"
    result["landmark_flags"] = "|".join(landmark_hits) if landmark_hits else "none"
    result["facility_flags"] = "|".join(facility_hits) if facility_hits else "none"
    result["rest_flags"] = "|".join(rest_hits) if rest_hits else "none"
    result["support_flags"] = "|".join(support_hits) if support_hits else "none"
    result["nearby_named_features"] = "; ".join(nearest_names)

    enriched_rows.append(result)

semantic_df = pd.DataFrame(enriched_rows)

# =========================================================
# 7a. OSM highway/path 語意分類
# =========================================================
semantic_df["surface_class"] = semantic_df.apply(classify_surface, axis=1)
semantic_df["route_semantic_class"] = semantic_df.apply(classify_route_semantic, axis=1)
semantic_df["assist_class"] = semantic_df.apply(classify_assist, axis=1)
semantic_df["visibility_class"] = semantic_df.apply(classify_visibility, axis=1)
semantic_df["osm_difficulty_class"] = semantic_df.apply(classify_osm_difficulty, axis=1)


# =========================================================
# 8. 合併回 profile
# =========================================================
profile_enriched = profile_df.copy()
profile_enriched = pd.concat(
    [profile_enriched.reset_index(drop=True), semantic_df.drop(columns=["sample_idx"]).reset_index(drop=True)],
    axis=1,
)

profile_enriched["case_id"] = CASE_ID
profile_enriched["case_name"] = CASE_NAME
profile_enriched["osm_raw_dir"] = str(IA1_DIR)
profile_enriched["ia1_dataset_id"] = IA1_DATASET_ID
profile_enriched["pipeline_stage"] = "ib1c_enrich_route_profile_semantics"

profile_geo = profile_pts.copy()
profile_geo["case_id"] = CASE_ID
profile_geo["case_name"] = CASE_NAME
profile_geo["osm_raw_dir"] = str(IA1_DIR)
profile_geo["ia1_dataset_id"] = IA1_DATASET_ID
profile_geo["pipeline_stage"] = "ib1c_enrich_route_profile_semantics"

for col in semantic_df.columns:
    if col == "sample_idx":
        continue
    profile_geo[col] = semantic_df[col].values

# 同步保留原 profile CSV 欄位
for col in profile_df.columns:
    if col not in profile_geo.columns:
        profile_geo[col] = profile_df[col].values


# =========================================================
# 9. 輸出
# =========================================================
profile_enriched.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
profile_geo.to_file(OUT_GEOJSON, driver="GeoJSON")

print("\n完成！")
print("semantic CSV:", OUT_CSV.resolve())
print("semantic GeoJSON:", OUT_GEOJSON.resolve())

print("\n--- technical_flags ---")
print(profile_enriched["technical_flags"].value_counts(dropna=False))

print("\n--- hazard_flags ---")
print(profile_enriched["hazard_flags"].value_counts(dropna=False))

print("\n--- hydrology_flags ---")
print(profile_enriched["hydrology_flags"].value_counts(dropna=False))

print("\n--- facility/rest/support summary ---")
for col in ["facility_flags", "rest_flags", "support_flags"]:
    print(f"\n{col}")
    print(profile_enriched[col].value_counts(dropna=False))

print("\n--- OSM highway semantic summary ---")
for col in [
    "near_highway",
    "osm_highway",
    "osm_surface",
    "surface_class",
    "route_semantic_class",
    "assist_class",
    "visibility_class",
    "osm_difficulty_class",
]:
    if col in profile_enriched.columns:
        print(f"\n{col}")
        print(profile_enriched[col].value_counts(dropna=False))
