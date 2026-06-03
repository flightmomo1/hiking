# =========================================================
# ib1h_generate_scenic_candidate_waypoints_from_osm.py
#
# 目的：
# - 讀取 Ia1 v1.3 OSM scenic / destination raw layers
# - 將 waterfall / viewpoint / guide_map_attraction / selected tourism POI
#   投影到 Prototype A route profile common route axis
# - 產生 scenic / destination candidate waypoints by distance
#
# 注意：
# - 本腳本補足 risk-zone based waypoint generation 的不足。
# - 既有 ib1h_generate_candidate_waypoints_from_risk_zones.py 仍負責：
#   recovery / pacing / conditional_check / rest_candidate / final_push。
# - 本腳本負責：
#   destination_stop / viewpoint_stop / scenic_stop / guide_map_stop。
# =========================================================

from pathlib import Path
import json

import pandas as pd
import geopandas as gpd


# =========================================================
# 0. Case 設定
# =========================================================
CASE_ID = "juansi_waterfall_fitcsv_20260503"
CASE_NAME = "絹絲瀑布 FIT CSV 20260503"
MODEL_VERSION = "prototype_A_terrain_dominant_v1"
OSM_DATASET_ID = CASE_ID

PROJECT_ROOT = Path(".")

PROFILE_GEOJSON = (
    PROJECT_ROOT
    / "outputs"
    / "ib1e_osm_nlsc_terrain_risk"
    / CASE_ID
    / f"{CASE_ID}_osm_nlsc_terrain_risk_profile.geojson"
)

OSM_RAW_DIR = PROJECT_ROOT / "osm_raw_output" / OSM_DATASET_ID

WATERFALL_GEOJSON = OSM_RAW_DIR / "osm_waterfall_raw.geojson"
VIEWPOINT_GEOJSON = OSM_RAW_DIR / "osm_viewpoint_raw.geojson"
GUIDE_MAP_GEOJSON = OSM_RAW_DIR / "osm_guide_map_attraction_raw.geojson"
TOURISM_GEOJSON = OSM_RAW_DIR / "osm_tourism_raw.geojson"
BENCH_FP = OSM_RAW_DIR / "osm_bench_raw.geojson"
SHELTER_FP = OSM_RAW_DIR / "osm_shelter_raw.geojson"
PICNIC_TABLE_FP = OSM_RAW_DIR / "osm_picnic_table_raw.geojson"
PICNIC_SITE_FP = OSM_RAW_DIR / "osm_picnic_site_raw.geojson"
TOILETS_FP = OSM_RAW_DIR / "osm_toilets_raw.geojson"
DRINKING_WATER_FP = OSM_RAW_DIR / "osm_drinking_water_raw.geojson"

OUT_DIR = PROJECT_ROOT / "outputs" / "prototype_A_terrain_dominant" / CASE_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_WAYPOINT_CSV = (
    OUT_DIR
    / f"{CASE_ID}_prototype_A_scenic_candidate_waypoints_by_distance.csv"
)
OUT_WAYPOINT_GEOJSON = (
    OUT_DIR
    / f"{CASE_ID}_prototype_A_scenic_candidate_waypoints.geojson"
)
OUT_SUMMARY_TXT = (
    OUT_DIR
    / f"{CASE_ID}_prototype_A_scenic_candidate_waypoints_summary.txt"
)


# =========================================================
# 1. 參數
# =========================================================
METRIC_CRS = "EPSG:32651"

# scenic POI 不一定壓在 route 線上，因此 offset 不能設太嚴。
MAX_OFFSET_BY_SOURCE = {
    "osm_waterfall_raw": 180.0,
    "osm_viewpoint_raw": 150.0,
    "osm_guide_map_attraction_raw": 80.0,
    "osm_tourism_raw": 100.0,

    # rest / support facility
    "osm_shelter_raw": 50.0,
    "osm_bench_raw": 30.0,
    "osm_picnic_table_raw": 40.0,
    "osm_picnic_site_raw": 60.0,
    "osm_toilets_raw": 60.0,
    "osm_drinking_water_raw": 60.0,
}

HIGH_CONF_OFFSET_M = 40.0
MED_CONF_OFFSET_M = 80.0
DEDUP_DISTANCE_M = 30.0

# tourism=True 可能很雜，因此只挑選可能具有停留/景點意義者。
TOURISM_KEEP_VALUES = {
    "attraction",
    "viewpoint",
    "picnic_site",
    "information",
}


# =========================================================
# 2. 工具函式
# =========================================================
def norm_text(v):
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except Exception:
        pass
    text = str(v).strip()
    if text.lower() in {"", "nan", "none", "<na>", "na", "null"}:
        return ""
    return text


def safe_get(row, key, default=""):
    if row is None or key not in row:
        return default
    v = row.get(key, default)
    try:
        if pd.isna(v):
            return default
    except Exception:
        pass
    return v


def read_layer(fp: Path) -> gpd.GeoDataFrame:
    if not fp.exists():
        print(f"圖層不存在，略過：{fp}")
        return gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs="EPSG:4326")

    gdf = gpd.read_file(fp)

    if gdf.empty:
        return gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs=gdf.crs or "EPSG:4326")

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")

    return gdf.to_crs("EPSG:4326")


def representative_points(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    對 Point / LineString / Polygon 都取一個代表點。
    Polygon 使用 representative_point()，避免 centroid 落在 polygon 外。
    """
    if gdf.empty:
        return gdf

    out = gdf.copy()
    out["source_geometry_type"] = out.geometry.geom_type
    out["geometry"] = out.geometry.representative_point()
    return out


def source_tags_json(row) -> str:
    keep_cols = [
        "osm_type", "osm_id",
        "name", "natural", "waterway", "tourism", "information",
        "board_type", "map_type", "description", "attraction",
        "operator", "ref", "network", "distance", "ele",
    ]

    data = {}
    for col in keep_cols:
        if col not in row:
            continue
        v = row.get(col)
        if norm_text(v):
            data[col] = str(v)

    return json.dumps(data, ensure_ascii=False)


def classify_confidence(offset_m: float, max_offset_m: float) -> str:
    if offset_m <= HIGH_CONF_OFFSET_M:
        return "high"
    if offset_m <= MED_CONF_OFFSET_M:
        return "medium"
    if offset_m <= max_offset_m:
        return "low"
    return "reject"


def find_nearest_profile_point(profile_metric: gpd.GeoDataFrame, point_metric):
    distances = profile_metric.geometry.distance(point_metric)
    idx = distances.idxmin()
    row = profile_metric.loc[idx].copy()
    return row, float(distances.loc[idx])


def make_waypoint_from_osm(
    row,
    profile_row,
    offset_m: float,
    source_layer: str,
    waypoint_type: str,
    primary_role: str,
    secondary_roles: str,
    priority: int,
    reason: str,
    confidence: str,
):
    name = norm_text(row.get("name", ""))

    if not name:
        if waypoint_type == "destination_stop":
            name = "未命名瀑布景點"
        elif waypoint_type == "viewpoint_stop":
            name = "未命名展望點"
        elif waypoint_type == "guide_map_stop":
            name = "未命名導覽圖停留點"
        elif waypoint_type == "shelter_stop":
            name = "未命名涼亭／遮蔽休息點"
        elif waypoint_type == "bench_stop":
            name = "未命名座椅休息點"
        elif waypoint_type == "picnic_stop":
            name = "未命名野餐休息點"
        elif waypoint_type == "toilets_stop":
            name = "未命名廁所設施點"
        elif waypoint_type == "drinking_water_stop":
            name = "未命名飲水補給點"
        else:
            name = "未命名景點停留點"

    target_dist = float(profile_row["dist_m"])

    return {
        "case_id": CASE_ID,
        "case_name": CASE_NAME,
        "model_version": MODEL_VERSION,
        "waypoint_id": "",  # dedup 後重編
        "name": name,
        "target_dist_m": round(target_dist, 2),
        "waypoint_type": waypoint_type,
        "primary_role": primary_role,
        "secondary_roles": secondary_roles,
        "candidate_source": "ia1_v1_3_osm_scenic_layer",
        "source_layer": source_layer,
        "source_osm_type": safe_get(row, "osm_type", ""),
        "source_osm_id": safe_get(row, "osm_id", ""),
        "source_name": name,
        "source_geometry_type": safe_get(row, "source_geometry_type", ""),
        "source_tags": source_tags_json(row),
        "nearest_route_offset_m": round(float(offset_m), 3),
        "source_confidence": confidence,
        "recommendation_reason": reason,
        "priority": int(priority),

        # 與 risk-zone waypoint CSV 相容，scenic waypoint 沒有來源 zone。
        "source_zone_id": -1,
        "source_zone_risk_group": "",
        "source_zone_start_m": "",
        "source_zone_end_m": "",
        "source_zone_length_m": "",
        "source_zone_mean_risk": "",
        "source_zone_max_risk": "",
        "dominant_slope_band": "",
        "hydrology_present_ratio": "",
        "zone_main_reason": "",
        "related_zone_ids": "",

        # 原始 scenic POI 位置與投影 route point。
        "source_lat": float(row.geometry.y),
        "source_lon": float(row.geometry.x),
        "route_lat": float(profile_row.geometry.y),
        "route_lon": float(profile_row.geometry.x),
    }


def merge_role_text(a, b):
    items = []
    for text in [a, b]:
        if not norm_text(text):
            continue
        for item in str(text).split("|"):
            item = item.strip()
            if item and item not in items:
                items.append(item)
    return "|".join(items)


def merge_waypoint_rows(base, other):
    merged = dict(base)

    t1 = norm_text(base.get("waypoint_type", ""))
    t2 = norm_text(other.get("waypoint_type", ""))
    if t1 and t2 and t1 != t2:
        merged["waypoint_type"] = merge_role_text(t1, t2)

    merged["secondary_roles"] = merge_role_text(
        base.get("secondary_roles", ""),
        str(other.get("primary_role", "")) + "|" + str(other.get("secondary_roles", "")),
    )

    r1 = norm_text(base.get("recommendation_reason", ""))
    r2 = norm_text(other.get("recommendation_reason", ""))
    if r2 and r2 not in r1:
        merged["recommendation_reason"] = r1 + " 同時，" + r2

    merged["source_layer"] = merge_role_text(
        base.get("source_layer", ""),
        other.get("source_layer", ""),
    )

    merged["source_osm_id"] = merge_role_text(
        base.get("source_osm_id", ""),
        other.get("source_osm_id", ""),
    )

    merged["source_confidence"] = base.get("source_confidence", "")
    merged["priority"] = min(
        int(base.get("priority", 99)),
        int(other.get("priority", 99)),
    )

    return merged


def deduplicate_waypoints(wp_df, min_sep_m=30.0):
    if wp_df.empty:
        return wp_df

    df = wp_df.sort_values(["target_dist_m", "priority"]).reset_index(drop=True)

    kept = []
    for _, row in df.iterrows():
        row_dict = row.to_dict()
        d = float(row_dict["target_dist_m"])

        merge_idx = None
        for i, kept_row in enumerate(kept):
            if abs(float(kept_row["target_dist_m"]) - d) < min_sep_m:
                merge_idx = i
                break

        if merge_idx is None:
            kept.append(row_dict)
        else:
            existing = kept[merge_idx]
            if int(row_dict.get("priority", 99)) < int(existing.get("priority", 99)):
                kept[merge_idx] = merge_waypoint_rows(row_dict, existing)
            else:
                kept[merge_idx] = merge_waypoint_rows(existing, row_dict)

    out = pd.DataFrame(kept)
    out = out.sort_values("target_dist_m").reset_index(drop=True)
    return out


def build_candidates_from_layer(
    gdf: gpd.GeoDataFrame,
    profile_metric: gpd.GeoDataFrame,
    source_layer: str,
    waypoint_type: str,
    primary_role: str,
    secondary_roles: str,
    priority: int,
    reason_template: str,
    max_offset_m: float,
) -> list[dict]:

    if gdf.empty:
        return []

    point_gdf = representative_points(gdf)
    point_metric = point_gdf.to_crs(METRIC_CRS)

    rows = []

    for idx, row_metric in point_metric.iterrows():
        source_point = row_metric.geometry
        profile_row_metric, offset_m = find_nearest_profile_point(
            profile_metric,
            source_point,
        )

        confidence = classify_confidence(offset_m, max_offset_m)
        if confidence == "reject":
            continue

        # profile_row_metric 是 metric CRS，需拿 profile 原始 WGS84 geometry。
        profile_row = profile_row_metric.copy()
        profile_row.geometry = gpd.GeoSeries(
            [profile_row_metric.geometry],
            crs=METRIC_CRS,
        ).to_crs("EPSG:4326").iloc[0]

        # row_wgs 用於輸出 source lat/lon。
        row_wgs = point_gdf.loc[idx].copy()

        source_name = norm_text(row_wgs.get("name", ""))
        reason = reason_template
        if source_name:
            reason = reason + f" OSM 名稱：{source_name}。"

        rows.append(
            make_waypoint_from_osm(
                row_wgs,
                profile_row,
                offset_m,
                source_layer,
                waypoint_type,
                primary_role,
                secondary_roles,
                priority,
                reason,
                confidence,
            )
        )

    return rows


# =========================================================
# 3. 讀資料
# =========================================================
if not PROFILE_GEOJSON.exists():
    raise FileNotFoundError(f"找不到 route profile GeoJSON：{PROFILE_GEOJSON.resolve()}")

profile_gdf = gpd.read_file(PROFILE_GEOJSON).to_crs("EPSG:4326")

if "dist_m" not in profile_gdf.columns:
    raise ValueError("profile GeoJSON 缺少 dist_m 欄位")

profile_metric = profile_gdf.to_crs(METRIC_CRS)

waterfalls = read_layer(WATERFALL_GEOJSON)
viewpoints = read_layer(VIEWPOINT_GEOJSON)
guide_maps = read_layer(GUIDE_MAP_GEOJSON)
tourism = read_layer(TOURISM_GEOJSON)
shelters = read_layer(SHELTER_FP)
benches = read_layer(BENCH_FP)
picnic_tables = read_layer(PICNIC_TABLE_FP)
picnic_sites = read_layer(PICNIC_SITE_FP)
toilets = read_layer(TOILETS_FP)
drinking_water = read_layer(DRINKING_WATER_FP)

if not tourism.empty and "tourism" in tourism.columns:
    tourism = tourism[
        tourism["tourism"].astype(str).str.lower().isin(TOURISM_KEEP_VALUES)
    ].copy()

print("case:", CASE_ID)
print("profile points:", len(profile_gdf))
print("waterfalls:", len(waterfalls))
print("viewpoints:", len(viewpoints))
print("guide_maps:", len(guide_maps))
print("tourism_selected:", len(tourism))
print("shelters:", len(shelters))
print("benches:", len(benches))
print("picnic_tables:", len(picnic_tables))
print("picnic_sites:", len(picnic_sites))
print("toilets:", len(toilets))
print("drinking_water:", len(drinking_water))


# =========================================================
# 4. 產生 scenic / destination candidates
# =========================================================
candidate_rows = []

candidate_rows.extend(
    build_candidates_from_layer(
        waterfalls,
        profile_metric,
        "osm_waterfall_raw",
        "destination_stop",
        "destination",
        "scenic|photo|rest|turnaround_decision",
        1,
        "瀑布或水景為此路線主要目的性停留點，適合安排觀景、拍照、補水與回程狀態確認。",
        MAX_OFFSET_BY_SOURCE["osm_waterfall_raw"],
    )
)

candidate_rows.extend(
    build_candidates_from_layer(
        viewpoints,
        profile_metric,
        "osm_viewpoint_raw",
        "viewpoint_stop",
        "scenic",
        "photo|rest|orientation_check",
        2,
        "展望點適合短暫停留、拍照、確認方向與調整節奏。",
        MAX_OFFSET_BY_SOURCE["osm_viewpoint_raw"],
    )
)

candidate_rows.extend(
    build_candidates_from_layer(
        guide_maps,
        profile_metric,
        "osm_guide_map_attraction_raw",
        "guide_map_stop",
        "navigation",
        "orientation_check|route_confirm|scenic_context",
        3,
        "導覽圖或資訊看板適合確認路線、景點位置與後續行程。",
        MAX_OFFSET_BY_SOURCE["osm_guide_map_attraction_raw"],
    )
)

candidate_rows.extend(
    build_candidates_from_layer(
        shelters,
        profile_metric,
        "osm_shelter_raw",
        "shelter_stop",
        "rest_facility",
        "shelter|shade|rest|weather_protection",
        4,
        "OSM shelter 圖層顯示此處具有涼亭、遮蔽或避難休息設施，適合作為登山者可辨識的休息中繼點。",
        MAX_OFFSET_BY_SOURCE["osm_shelter_raw"],
    )
)

candidate_rows.extend(
    build_candidates_from_layer(
        benches,
        profile_metric,
        "osm_bench_raw",
        "bench_stop",
        "rest_facility",
        "short_rest|behavior_observation",
        7,
        "OSM bench 圖層顯示此處具有座椅設施，可作為短暫休息或停留行為觀測點。",
        MAX_OFFSET_BY_SOURCE["osm_bench_raw"],
    )
)

candidate_rows.extend(
    build_candidates_from_layer(
        picnic_tables,
        profile_metric,
        "osm_picnic_table_raw",
        "picnic_stop",
        "rest_facility",
        "rest|picnic|group_stop",
        6,
        "OSM picnic_table 圖層顯示此處具有野餐桌或可停留設施，可作為休息與團體停留候選點。",
        MAX_OFFSET_BY_SOURCE["osm_picnic_table_raw"],
    )
)

candidate_rows.extend(
    build_candidates_from_layer(
        picnic_sites,
        profile_metric,
        "osm_picnic_site_raw",
        "picnic_stop",
        "rest_facility",
        "rest|picnic|group_stop",
        6,
        "OSM picnic_site 圖層顯示此處具有野餐或休憩區語意，可作為休息與團體停留候選點。",
        MAX_OFFSET_BY_SOURCE["osm_picnic_site_raw"],
    )
)

candidate_rows.extend(
    build_candidates_from_layer(
        toilets,
        profile_metric,
        "osm_toilets_raw",
        "toilets_stop",
        "support_facility",
        "toilet|support|trip_planning",
        4,
        "OSM toilets 圖層顯示此處具有廁所設施，對登山者行程規劃與停留決策具有支援價值。",
        MAX_OFFSET_BY_SOURCE["osm_toilets_raw"],
    )
)

candidate_rows.extend(
    build_candidates_from_layer(
        drinking_water,
        profile_metric,
        "osm_drinking_water_raw",
        "drinking_water_stop",
        "support_facility",
        "water|support|hydration",
        4,
        "OSM drinking_water 圖層顯示此處具有飲水或補水設施，對登山者補給與風險管理具有支援價值。",
        MAX_OFFSET_BY_SOURCE["osm_drinking_water_raw"],
    )
)

wp_df = pd.DataFrame(candidate_rows)

before_n = len(wp_df)
wp_df = deduplicate_waypoints(wp_df, min_sep_m=DEDUP_DISTANCE_M)
after_n = len(wp_df)

if not wp_df.empty:
    wp_df = wp_df.reset_index(drop=True)
    wp_df["generated_order"] = range(1, len(wp_df) + 1)
    wp_df["waypoint_id"] = [
        f"SWP{i:02d}" for i in range(1, len(wp_df) + 1)
    ]

    # 讓 generated_order 放前面，與 risk-zone waypoint 輸出風格接近。
    front_cols = [
        "generated_order",
        "waypoint_id",
        "case_id",
        "case_name",
        "model_version",
        "name",
        "target_dist_m",
        "waypoint_type",
        "primary_role",
        "secondary_roles",
        "candidate_source",
        "source_layer",
        "source_confidence",
        "nearest_route_offset_m",
        "recommendation_reason",
        "priority",
    ]
    other_cols = [c for c in wp_df.columns if c not in front_cols]
    wp_df = wp_df[front_cols + other_cols]


# =========================================================
# 5. 輸出
# =========================================================
wp_df.to_csv(OUT_WAYPOINT_CSV, index=False, encoding="utf-8-sig")

if not wp_df.empty:
    geo_df = wp_df.copy()
    geometry = gpd.points_from_xy(
        geo_df["route_lon"].astype(float),
        geo_df["route_lat"].astype(float),
    )
    wp_gdf = gpd.GeoDataFrame(
        geo_df,
        geometry=geometry,
        crs="EPSG:4326",
    )
else:
    wp_gdf = gpd.GeoDataFrame(
        wp_df,
        geometry=[],
        crs="EPSG:4326",
    )

wp_gdf.to_file(OUT_WAYPOINT_GEOJSON, driver="GeoJSON")

summary_lines = [
    "Prototype A Scenic Candidate Waypoints Summary",
    f"case_id: {CASE_ID}",
    f"case_name: {CASE_NAME}",
    f"model_version: {MODEL_VERSION}",
    "",
    f"profile GeoJSON: {PROFILE_GEOJSON}",
    f"OSM raw dir: {OSM_RAW_DIR}",
    "",
    f"waterfalls: {len(waterfalls)}",
    f"viewpoints: {len(viewpoints)}",
    f"guide_maps: {len(guide_maps)}",
    f"tourism_selected: {len(tourism)}",
    f"shelters: {len(shelters)}",
    f"benches: {len(benches)}",
    f"picnic_tables: {len(picnic_tables)}",
    f"picnic_sites: {len(picnic_sites)}",
    f"toilets: {len(toilets)}",
    f"drinking_water: {len(drinking_water)}",
    "",
    f"generated_waypoints_before_dedup: {before_n}",
    f"generated_waypoints_after_dedup: {after_n}",
]

if not wp_df.empty:
    summary_lines.extend([
        "",
        "waypoint_type counts:",
        str(wp_df["waypoint_type"].value_counts()),
        "",
        "source_layer counts:",
        str(wp_df["source_layer"].value_counts()),
        "",
        "source_confidence counts:",
        str(wp_df["source_confidence"].value_counts()),
    ])

summary_lines.extend([
    "",
    f"scenic waypoint CSV: {OUT_WAYPOINT_CSV}",
    f"scenic waypoint GeoJSON: {OUT_WAYPOINT_GEOJSON}",
])

OUT_SUMMARY_TXT.write_text("\n".join(summary_lines), encoding="utf-8")


print("\n完成！")
print("scenic waypoint CSV:", OUT_WAYPOINT_CSV.resolve())
print("scenic waypoint GeoJSON:", OUT_WAYPOINT_GEOJSON.resolve())
print("summary TXT:", OUT_SUMMARY_TXT.resolve())

print("\n--- scenic waypoint type ---")
if not wp_df.empty:
    print(wp_df["waypoint_type"].value_counts(dropna=False))
else:
    print("no scenic waypoint generated")

print("\n--- scenic candidate preview ---")
preview_cols = [
    "generated_order",
    "waypoint_id",
    "target_dist_m",
    "waypoint_type",
    "source_layer",
    "source_confidence",
    "nearest_route_offset_m",
    "name",
    "recommendation_reason",
]
if not wp_df.empty:
    print(wp_df[preview_cols])
else:
    print(wp_df)
