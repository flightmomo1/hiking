# =========================================================
# ib1h_project_candidate_waypoints_to_route.py
#
# 目的：
# - 讀取 candidate waypoints by distance
# - 讀取 Prototype A combined risk profile GeoJSON
# - 讀取 Prototype A risk zones
# - 依 target_dist_m 找最近 profile point
# - 補上 lat / lon / nearest_dist_m / risk / terrain / hydrology / zone info
# - 輸出 waypoint CSV / GeoJSON
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

WAYPOINT_DISTANCE_CSV = (
    Path("outputs")
    / "prototype_A_terrain_dominant"
    / CASE_ID
    / f"{CASE_ID}_prototype_A_candidate_waypoints_by_distance.csv"
)

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

OUT_DIR = Path("outputs") / "prototype_A_terrain_dominant" / CASE_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_WAYPOINT_CSV = OUT_DIR / f"{CASE_ID}_prototype_A_candidate_waypoints_projected.csv"
OUT_WAYPOINT_GEOJSON = OUT_DIR / f"{CASE_ID}_prototype_A_candidate_waypoints_projected.geojson"
OUT_SUMMARY_TXT = OUT_DIR / f"{CASE_ID}_prototype_A_candidate_waypoints_projected_summary.txt"


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


def risk_band_from_score(score):
    try:
        score = float(score)
    except Exception:
        return "unknown"

    if score < 0.20:
        return "low"
    if score < 0.40:
        return "moderate"
    if score < 0.65:
        return "high"
    return "very_high"


def make_projected_note(row):
    wp_type = norm_text(row.get("waypoint_type", ""))
    zone_group = norm_text(row.get("projected_zone_risk_group", ""))
    terrain = norm_text(row.get("projected_slope_band", ""))
    hydro = float(row.get("projected_hydrology_present_ratio", 0) or 0)

    notes = []

    if "recovery" in wp_type:
        notes.append("通過高負荷或高風險區後，適合恢復心率、補水與重新評估。")

    if "decision" in wp_type or "final_push" in wp_type:
        notes.append("適合確認體力、時間、天候與是否繼續推進。")

    if "conditional_check" in wp_type:
        notes.append("適合檢查橋梁、水文、濕滑或其他條件式風險。")

    if "rest_candidate" in wp_type:
        notes.append("位於相對低風險區，可作為短暫休息或節奏調整候選點。")

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

required_wp = [
    "waypoint_id",
    "name",
    "target_dist_m",
    "waypoint_type",
    "primary_role",
    "secondary_roles",
    "recommendation_reason",
]

missing_wp = [c for c in required_wp if c not in wp_df.columns]
if missing_wp:
    raise ValueError(f"waypoint CSV 缺少必要欄位：{missing_wp}")

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
print("waypoints:", len(wp_df))
print("profile points:", len(profile_gdf))
print("zones:", len(zone_df))


# =========================================================
# 4. 依 target_dist_m 投影到最近 route profile point
# =========================================================
projected_rows = []

for _, wp in wp_df.iterrows():
    target_dist = float(wp["target_dist_m"])

    profile_row, dist_error = find_nearest_profile_point(profile_gdf, target_dist)
    nearest_dist = float(profile_row["dist_m"])

    zone_row = find_zone_for_dist(zone_df, nearest_dist)

    geom = profile_row.geometry

    out = wp.to_dict()

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
    "Prototype A Projected Candidate Waypoints Summary",
    f"case_id: {CASE_ID}",
    f"case_name: {CASE_NAME}",
    f"model_version: {MODEL_VERSION}",
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

print(proj_df[preview_cols])