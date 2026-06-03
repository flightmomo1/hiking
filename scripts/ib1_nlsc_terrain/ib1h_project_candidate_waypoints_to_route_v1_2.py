# =========================================================
# ib1h_project_candidate_waypoints_to_route.py
#
# 目的：
# - 讀取 candidate waypoints by distance
# - 支援 risk / scenic / combined 三種 waypoint set
# - 讀取 Prototype A combined risk profile GeoJSON
# - 讀取 Prototype A risk zones
# - 依 target_dist_m 找最近 profile point
# - 補上 lat / lon / projected_dist_m / risk / terrain / hydrology / zone info
# - 輸出 projected waypoint CSV / GeoJSON / summary
#
# v1.1 update:
# - 保留原本 risk waypoint projection 流程
# - 新增 WAYPOINT_SET = "combined" 支援
# - 可投影：
#   1) *_candidate_waypoints_by_distance.csv
#   2) *_scenic_candidate_waypoints_by_distance.csv
#   3) *_candidate_waypoints_combined_by_distance.csv
# =========================================================

from pathlib import Path

import pandas as pd
import geopandas as gpd


# =========================================================
# 0. Case 設定
# =========================================================
CASE_ID = "juansi_waterfall_fitcsv_20260503"
CASE_NAME = "絹絲瀑布 FIT CSV 20260503"
MODEL_VERSION = "prototype_A_terrain_dominant_v1"

# 可選：
# - "risk"     : 原本 risk-zone based candidate waypoints
# - "scenic"   : Ia1 v1.3 scenic / destination candidate waypoints
# - "combined" : risk + scenic 合併後 candidate waypoints
WAYPOINT_SET = "combined"

BASE_DIR = Path("outputs") / "prototype_A_terrain_dominant" / CASE_ID

WAYPOINT_FILES = {
    "risk": {
        "input": BASE_DIR / f"{CASE_ID}_prototype_A_candidate_waypoints_by_distance.csv",
        "out_csv": BASE_DIR / f"{CASE_ID}_prototype_A_candidate_waypoints_projected.csv",
        "out_geojson": BASE_DIR / f"{CASE_ID}_prototype_A_candidate_waypoints_projected.geojson",
        "out_summary": BASE_DIR / f"{CASE_ID}_prototype_A_candidate_waypoints_projected_summary.txt",
        "summary_title": "Prototype A Projected Candidate Waypoints Summary",
    },
    "scenic": {
        "input": BASE_DIR / f"{CASE_ID}_prototype_A_scenic_candidate_waypoints_by_distance.csv",
        "out_csv": BASE_DIR / f"{CASE_ID}_prototype_A_scenic_candidate_waypoints_projected.csv",
        "out_geojson": BASE_DIR / f"{CASE_ID}_prototype_A_scenic_candidate_waypoints_projected.geojson",
        "out_summary": BASE_DIR / f"{CASE_ID}_prototype_A_scenic_candidate_waypoints_projected_summary.txt",
        "summary_title": "Prototype A Projected Scenic Candidate Waypoints Summary",
    },
    "combined": {
        "input": BASE_DIR / f"{CASE_ID}_prototype_A_candidate_waypoints_combined_by_distance.csv",
        "out_csv": BASE_DIR / f"{CASE_ID}_prototype_A_candidate_waypoints_combined_projected.csv",
        "out_geojson": BASE_DIR / f"{CASE_ID}_prototype_A_candidate_waypoints_combined_projected.geojson",
        "out_summary": BASE_DIR / f"{CASE_ID}_prototype_A_candidate_waypoints_combined_projected_summary.txt",
        "summary_title": "Prototype A Projected Combined Candidate Waypoints Summary",
    },
}

if WAYPOINT_SET not in WAYPOINT_FILES:
    raise ValueError(f"未知 WAYPOINT_SET: {WAYPOINT_SET}")

WAYPOINT_DISTANCE_CSV = WAYPOINT_FILES[WAYPOINT_SET]["input"]
OUT_WAYPOINT_CSV = WAYPOINT_FILES[WAYPOINT_SET]["out_csv"]
OUT_WAYPOINT_GEOJSON = WAYPOINT_FILES[WAYPOINT_SET]["out_geojson"]
OUT_SUMMARY_TXT = WAYPOINT_FILES[WAYPOINT_SET]["out_summary"]
SUMMARY_TITLE = WAYPOINT_FILES[WAYPOINT_SET]["summary_title"]

PROFILE_GEOJSON = (
    Path("outputs")
    / "ib1e_osm_nlsc_terrain_risk"
    / CASE_ID
    / f"{CASE_ID}_osm_nlsc_terrain_risk_profile.geojson"
)

ZONE_CSV = (
    Path("outputs")
    / "prototype_A_terrain_dominant"
    / CASE_ID
    / f"{CASE_ID}_prototype_A_risk_zones.csv"
)

OUT_DIR = BASE_DIR
OUT_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# 1. 參數
# =========================================================
MAX_DIST_MATCH_M = 5.0


# =========================================================
# 2. 工具函式
# =========================================================
def norm_text(v):
    if pd.isna(v):
        return ""
    text = str(v).strip().lower()
    if text in {"", "nan", "none", "<na>", "na", "null"}:
        return ""
    return text


def find_nearest_profile_point(profile_gdf, target_dist_m):
    d = float(target_dist_m)
    diff = (profile_gdf["dist_m"].astype(float) - d).abs()
    idx = diff.idxmin()
    row = profile_gdf.loc[idx].copy()
    return row, float(diff.loc[idx])


def find_zone_for_dist(zone_df, dist_m):
    d = float(dist_m)

    matched = zone_df[
        (zone_df["start_dist_m"].astype(float) <= d)
        & (zone_df["end_dist_m"].astype(float) >= d)
    ]

    if matched.empty:
        return None

    return matched.iloc[0]


def safe_get(row, key, default=""):
    if row is None:
        return default
    if key not in row:
        return default
    v = row.get(key, default)
    if pd.isna(v):
        return default
    return v


def ensure_col(df, col, default=""):
    if col not in df.columns:
        df[col] = default
    return df


def make_projected_note(row):
    wp_type = norm_text(row.get("waypoint_type", ""))
    zone_group = norm_text(row.get("projected_zone_risk_group", ""))
    terrain = norm_text(row.get("projected_slope_band", ""))
    hydro = float(row.get("projected_hydrology_present_ratio", 0) or 0)

    notes = []

    # risk-zone waypoint notes
    if "recovery" in wp_type:
        notes.append("通過高負荷或高風險區後，適合恢復心率、補水與重新評估。")

    if "decision" in wp_type or "final_push" in wp_type:
        notes.append("適合確認體力、時間、天候與是否繼續推進。")

    if "conditional_check" in wp_type:
        notes.append("適合檢查橋梁、水文、濕滑或其他條件式風險。")

    if "rest_candidate" in wp_type:
        notes.append("位於相對低風險區，可作為短暫休息或節奏調整候選點。")

    if "pacing" in wp_type:
        notes.append("適合調整配速、確認呼吸節奏與步行負荷。")

    # scenic / destination waypoint notes
    if "destination_stop" in wp_type:
        notes.append("此點具目的地或主要景點語意，適合安排停留、拍照或行程確認。")

    if "viewpoint_stop" in wp_type:
        notes.append("此點具展望點語意，可作為觀景與短暫停留候選點。")

    if "guide_map_stop" in wp_type:
        notes.append("此點具導覽圖、資訊牌或景點解說語意，適合停下確認路線與景點資訊。")

    if "scenic_stop" in wp_type:
        notes.append("此點具景點或旅遊語意，可作為非風險導向的停留候選點。")

    # projected environment context
    if zone_group == "high":
        notes.append("所在或鄰近區段屬高風險，停留與推進需更保守。")

    if terrain in {"steep", "very_steep"}:
        notes.append("周邊地形坡度較高，需注意體力消耗與下坡安全。")

    if hydro >= 0.5:
        notes.append("該區段水文鄰近比例高，雨後或潮濕時需注意濕滑。")

    if not notes:
        notes.append("可作為路線節奏調整與狀態確認點。")

    return "".join(notes)


# =========================================================
# 3. 讀資料
# =========================================================
for fp in [WAYPOINT_DISTANCE_CSV, PROFILE_GEOJSON, ZONE_CSV]:
    if not fp.exists():
        raise FileNotFoundError(f"找不到輸入檔：{fp.resolve()}")

wp_df = pd.read_csv(WAYPOINT_DISTANCE_CSV, low_memory=False)
profile_gdf = gpd.read_file(PROFILE_GEOJSON).to_crs("EPSG:4326")
zone_df = pd.read_csv(ZONE_CSV, low_memory=False)


# ---------------------------------------------------------
# waypoint schema normalization
# ---------------------------------------------------------
if "waypoint_id" not in wp_df.columns:
    id_candidates = [
        "combined_waypoint_id",
        "primary_waypoint_id",
        "combined_id",
        "cwp_id",
        "scenic_waypoint_id",
        "source_waypoint_id",
    ]

    found_id_col = None
    for col in id_candidates:
        if col in wp_df.columns:
            found_id_col = col
            break

    if found_id_col is not None:
        wp_df["waypoint_id"] = wp_df[found_id_col].astype(str)
        print(f"補 waypoint_id from {found_id_col}")
    else:
        prefix = {
            "risk": "WP",
            "scenic": "SWP",
            "combined": "CWP",
        }.get(WAYPOINT_SET, "WP")

        wp_df["waypoint_id"] = [
            f"{prefix}{i + 1:02d}"
            for i in range(len(wp_df))
        ]
        print(f"補 waypoint_id by generated sequence prefix={prefix}")

REQUIRED_WP_COLS = [
    "waypoint_id",
    "target_dist_m",
    "waypoint_type",
]

missing_wp = [
    c for c in REQUIRED_WP_COLS
    if c not in wp_df.columns
]

if missing_wp:
    raise ValueError(f"waypoint CSV 缺少必要欄位：{missing_wp}")
# optional fields used by original risk waypoint output
optional_defaults = {
    "generated_order": "",
    "name": "",
    "primary_role": "",
    "secondary_roles": "",
    "recommendation_reason": "",
}

for col, default in optional_defaults.items():
    wp_df = ensure_col(wp_df, col, default)

if "dist_m" not in profile_gdf.columns:
    raise ValueError("profile GeoJSON 缺少 dist_m 欄位")

required_zone = [
    "zone_id",
    "zone_risk_group",
    "start_dist_m",
    "end_dist_m",
    "mean_combined_risk",
    "max_combined_risk",
    "dominant_slope_band",
    "hydrology_present_ratio",
    "zone_main_reason",
    "suggested_warning_text",
]

missing_zone = [c for c in required_zone if c not in zone_df.columns]
if missing_zone:
    raise ValueError(f"risk zone CSV 缺少必要欄位：{missing_zone}")

print("case:", CASE_ID)
print("waypoint_set:", WAYPOINT_SET)
print("input waypoint CSV:", WAYPOINT_DISTANCE_CSV)
print("waypoints:", len(wp_df))
print("profile points:", len(profile_gdf))
print("zones:", len(zone_df))


# =========================================================
# 4. 依 target_dist_m 投影到最近 route profile point
# =========================================================
projected_rows = []

for idx, wp in wp_df.iterrows():
    target_dist = float(wp["target_dist_m"])

    profile_row, dist_error = find_nearest_profile_point(profile_gdf, target_dist)
    nearest_dist = float(profile_row["dist_m"])

    zone_row = find_zone_for_dist(zone_df, nearest_dist)

    geom = profile_row.geometry

    out = wp.to_dict()

    if not out.get("generated_order"):
        out["generated_order"] = int(idx) + 1

    out.update({
        "projected_dist_m": round(nearest_dist, 3),
        "target_to_projected_dist_error_m": round(dist_error, 3),
        "projection_match_ok": bool(dist_error <= MAX_DIST_MATCH_M),

        "lat": float(geom.y),
        "lon": float(geom.x),

        "projected_osm_semantic_risk_score": safe_get(profile_row, "osm_semantic_risk_score", ""),
        "projected_terrain_window_risk_score": safe_get(profile_row, "terrain_window_risk_score", ""),
        "projected_hydro_terrain_amplifier_score": safe_get(profile_row, "hydro_terrain_amplifier_score", ""),
        "projected_combined_risk_score": safe_get(profile_row, "osm_terrain_combined_risk_score", ""),
        "projected_combined_risk_band": safe_get(profile_row, "osm_terrain_combined_risk_band", ""),

        "projected_slope_band": safe_get(profile_row, "terrain_slope_band_window", ""),
        "projected_elev_range": safe_get(profile_row, "terrain_elev_range", ""),
        "projected_hydrology_flags": safe_get(profile_row, "hydrology_flags", ""),
        "projected_osm_surface": safe_get(profile_row, "osm_surface", ""),
        "projected_osm_highway": safe_get(profile_row, "osm_highway", ""),
        "projected_conditional_factor_flags": safe_get(profile_row, "conditional_factor_flags", ""),
    })

    if zone_row is not None:
        out.update({
            "projected_zone_id": int(zone_row["zone_id"]),
            "projected_zone_risk_group": zone_row["zone_risk_group"],
            "projected_zone_start_m": float(zone_row["start_dist_m"]),
            "projected_zone_end_m": float(zone_row["end_dist_m"]),
            "projected_zone_mean_combined_risk": float(zone_row["mean_combined_risk"]),
            "projected_zone_max_combined_risk": float(zone_row["max_combined_risk"]),
            "projected_zone_dominant_slope_band": zone_row["dominant_slope_band"],
            "projected_hydrology_present_ratio": float(zone_row["hydrology_present_ratio"]),
            "projected_zone_main_reason": zone_row["zone_main_reason"],
            "projected_zone_warning_text": zone_row["suggested_warning_text"],
        })
    else:
        out.update({
            "projected_zone_id": -1,
            "projected_zone_risk_group": "",
            "projected_zone_start_m": "",
            "projected_zone_end_m": "",
            "projected_zone_mean_combined_risk": "",
            "projected_zone_max_combined_risk": "",
            "projected_zone_dominant_slope_band": "",
            "projected_hydrology_present_ratio": 0.0,
            "projected_zone_main_reason": "",
            "projected_zone_warning_text": "",
        })

    out["projected_note"] = make_projected_note(out)
    out["geometry"] = geom

    projected_rows.append(out)


proj_gdf = gpd.GeoDataFrame(projected_rows, geometry="geometry", crs="EPSG:4326")
proj_df = pd.DataFrame(projected_rows).drop(columns=["geometry"])


# =========================================================
# 5. 輸出
# =========================================================
proj_df.to_csv(OUT_WAYPOINT_CSV, index=False, encoding="utf-8-sig")
proj_gdf.to_file(OUT_WAYPOINT_GEOJSON, driver="GeoJSON")

summary_lines = [
    SUMMARY_TITLE,
    f"case_id: {CASE_ID}",
    f"case_name: {CASE_NAME}",
    f"model_version: {MODEL_VERSION}",
    f"waypoint_set: {WAYPOINT_SET}",
    "",
    f"input waypoint distance CSV: {WAYPOINT_DISTANCE_CSV}",
    f"profile GeoJSON: {PROFILE_GEOJSON}",
    f"zone CSV: {ZONE_CSV}",
    "",
    f"waypoints: {len(proj_df)}",
    f"projection_match_ok_n: {int(proj_df['projection_match_ok'].sum())}",
    f"projection_match_not_ok_n: {int((~proj_df['projection_match_ok']).sum())}",
    "",
    "waypoint_type counts:",
    str(proj_df["waypoint_type"].value_counts()),
    "",
    "projected_zone_risk_group counts:",
    str(proj_df["projected_zone_risk_group"].value_counts()),
    "",
    f"projected waypoint CSV: {OUT_WAYPOINT_CSV}",
    f"projected waypoint GeoJSON: {OUT_WAYPOINT_GEOJSON}",
]

OUT_SUMMARY_TXT.write_text("\n".join(summary_lines), encoding="utf-8")


print("\n完成！")
print("waypoint_set:", WAYPOINT_SET)
print("projected waypoint CSV:", OUT_WAYPOINT_CSV.resolve())
print("projected waypoint GeoJSON:", OUT_WAYPOINT_GEOJSON.resolve())
print("summary TXT:", OUT_SUMMARY_TXT.resolve())

print("\n--- projection match ---")
print(proj_df["projection_match_ok"].value_counts(dropna=False))

print("\n--- waypoint type ---")
print(proj_df["waypoint_type"].value_counts(dropna=False))

print("\n--- projected zone risk group ---")
print(proj_df["projected_zone_risk_group"].value_counts(dropna=False))

print("\n--- projected waypoint preview ---")
preview_cols = [
    "generated_order",
    "waypoint_id",
    "target_dist_m",
    "projected_dist_m",
    "target_to_projected_dist_error_m",
    "lat",
    "lon",
    "waypoint_type",
    "projected_zone_id",
    "projected_zone_risk_group",
    "projected_combined_risk_score",
    "projected_slope_band",
    "projected_hydrology_flags",
    "projected_note",
]

preview_cols = [c for c in preview_cols if c in proj_df.columns]
print(proj_df[preview_cols])
