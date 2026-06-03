# =========================================================
# ib1e_enrich_route_profile_with_nlsc.py
# 將 ib1c route profile 對齊 ia2c NLSC 20m segment elevation features
# =========================================================

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import geopandas as gpd


# =========================================================
# 0. 路徑設定
# =========================================================
CASE_ID = "juansi_waterfall_fitcsv_20260503"
CASE_NAME = "絹絲瀑布 FIT CSV 20260503"

PROFILE_CSV = (
    Path("outputs")
    / "ib1c_osm_semantic_risk"
    / CASE_ID
    / f"{CASE_ID}_osm_semantic_risk_profile.csv"
)

PROFILE_GEOJSON = (
    Path("outputs")
    / "ib1c_osm_semantic_risk"
    / CASE_ID
    / f"{CASE_ID}_osm_semantic_risk_profile.geojson"
)

NLSC_SEGMENT_FP = (
    Path("outputs")
    / "segment_enriched_output"
    / "97233NW_segments_20m_elevation_enriched.geojson"
)

OUT_DIR = Path("outputs") / "ib1e_route_profile_nlsc_terrain" / CASE_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_CSV = OUT_DIR / f"{CASE_ID}_route_profile_nlsc_terrain_enriched.csv"
OUT_GEOJSON = OUT_DIR / f"{CASE_ID}_route_profile_nlsc_terrain_enriched.geojson"


# =========================================================
# 1. 參數
# =========================================================
MAX_MATCH_DISTANCE_M = 100.0
NOW_UTC = datetime.now(timezone.utc).isoformat()


# =========================================================
# 2. 檢查輸入
# =========================================================
for fp in [PROFILE_CSV, PROFILE_GEOJSON, NLSC_SEGMENT_FP]:
    if not fp.exists():
        raise FileNotFoundError(f"找不到輸入檔：{fp.resolve()}")


# =========================================================
# 3. 讀資料
# =========================================================
profile_df = pd.read_csv(PROFILE_CSV)
profile_gdf = gpd.read_file(PROFILE_GEOJSON)

nlsc_seg = gpd.read_file(NLSC_SEGMENT_FP)

if profile_gdf.empty:
    raise ValueError("profile GeoJSON 為空")

if nlsc_seg.empty:
    raise ValueError("NLSC segment GeoJSON 為空")

if profile_gdf.crs is None:
    profile_gdf = profile_gdf.set_crs("EPSG:4326")

if nlsc_seg.crs is None:
    nlsc_seg = nlsc_seg.set_crs("EPSG:4326")


# =========================================================
# 4. 投影到公尺座標
# =========================================================
metric_crs = profile_gdf.estimate_utm_crs()

profile_m = profile_gdf.to_crs(metric_crs)
nlsc_m = nlsc_seg.to_crs(metric_crs)

print("profile points:", len(profile_m))
print("NLSC segments:", len(nlsc_m))
print("metric CRS:", metric_crs)


# =========================================================
# 5. 精簡 NLSC 欄位
# =========================================================
nlsc_keep_cols = [
    "segment_id",
    "parent_id",
    "tile_id",
    "segment_len_m",
    "elev_gain_est_m",
    "slope_est_mean",
    "slope_band",
    "contour_cross_n",
    "contour_unique_elev_n",
    "contour_interval_m",
    "contour_density_20m",
    "elevp_available",
    "elevation_source",
    "source_name",
    "pipeline_stage",
    "geometry",
]

existing_cols = [c for c in nlsc_keep_cols if c in nlsc_m.columns]
nlsc_m = nlsc_m[existing_cols].copy()

rename_map = {
    "segment_id": "nlsc_segment_id",
    "parent_id": "nlsc_parent_id",
    "tile_id": "nlsc_tile_id",
    "segment_len_m": "nlsc_segment_len_m",
    "elev_gain_est_m": "elev_gain_nlsc_m",
    "slope_est_mean": "slope_nlsc",
    "slope_band": "slope_band_nlsc",
    "contour_cross_n": "contour_cross_n_nlsc",
    "contour_unique_elev_n": "contour_unique_elev_n_nlsc",
    "contour_interval_m": "contour_interval_nlsc_m",
    "contour_density_20m": "contour_density_20m_nlsc",
    "elevp_available": "elevp_available_nlsc",
    "elevation_source": "elevation_source_nlsc",
    "source_name": "nlsc_source_name",
    "pipeline_stage": "nlsc_pipeline_stage",
}

nlsc_m = nlsc_m.rename(columns=rename_map)


# =========================================================
# 6. 最近 NLSC segment 對齊
# =========================================================
profile_m = profile_m.reset_index(drop=True).copy()
profile_m["profile_row_id"] = profile_m.index

nlsc_m = nlsc_m.reset_index(drop=True).copy()
nlsc_m["nlsc_join_id"] = nlsc_m.index

joined_raw = gpd.sjoin_nearest(
    profile_m,
    nlsc_m,
    how="left",
    max_distance=MAX_MATCH_DISTANCE_M,
    distance_col="dist_to_nlsc_segment_m",
)

# sjoin_nearest 可能因為等距最近物件產生一對多結果；
# 這裡強制每個 profile point 只保留最近的一筆。
joined = (
    joined_raw
    .sort_values(
        ["profile_row_id", "dist_to_nlsc_segment_m"],
        na_position="last"
    )
    .drop_duplicates(subset=["profile_row_id"], keep="first")
    .sort_values("profile_row_id")
    .reset_index(drop=True)
)

if len(joined) != len(profile_m):
    raise ValueError(
        f"NLSC join 後筆數不一致：profile={len(profile_m)}, joined={len(joined)}"
    )

print("joined rows:", len(joined))

# sjoin_nearest 可能產生 index_right，保留結果但不需要它
if "index_right" in joined.columns:
    joined = joined.drop(columns=["index_right"])

joined["nlsc_match_status"] = joined["dist_to_nlsc_segment_m"].apply(
    lambda x: "matched" if pd.notna(x) else "unmatched"
)


# =========================================================
# 7. 補 metadata
# =========================================================
joined["nlsc_enriched_at"] = NOW_UTC
joined["pipeline_stage"] = "ib1e_enrich_route_profile_with_nlsc_terrain"
joined["nlsc_match_distance_threshold_m"] = MAX_MATCH_DISTANCE_M


# =========================================================
# 8. 輸出 GeoJSON / CSV
# =========================================================
out_gdf = joined.to_crs("EPSG:4326")

# CSV 不需要 geometry
out_df = pd.DataFrame(out_gdf.drop(columns="geometry"))

out_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
out_gdf.to_file(OUT_GEOJSON, driver="GeoJSON")

print("\n完成！")
print("CSV:", OUT_CSV.resolve())
print("GeoJSON:", OUT_GEOJSON.resolve())

print("\n=== NLSC match status ===")
print(out_df["nlsc_match_status"].value_counts(dropna=False))

print("\n=== slope_band_nlsc ===")
if "slope_band_nlsc" in out_df.columns:
    print(out_df["slope_band_nlsc"].value_counts(dropna=False))

print("\n=== dist_to_nlsc_segment_m summary ===")
print(out_df["dist_to_nlsc_segment_m"].describe())