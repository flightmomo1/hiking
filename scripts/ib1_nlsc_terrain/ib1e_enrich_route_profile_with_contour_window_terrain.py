# =========================================================
# ib1e_enrich_route_profile_with_contour_window_terrain.py
#
# 目的：
# - 讀取 ib1c_apply_osm_semantic_risk_mapping.py 產出的 1m route profile
# - 讀取 ib1g_v2_compute_contour_window_features.py 產出的 20m contour window features
# - 以 route distance axis 對齊：
#     profile.dist_m  對應  contour.dist_mid
# - 輸出含 OSM semantic risk + NLSC contour window terrain 的 route profile
# =========================================================

from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import geopandas as gpd


# =========================================================
# 0. Case 設定
# =========================================================
CASE_ID = "juansi_waterfall_fitcsv_20260503"
CASE_NAME = "絹絲瀑布 FIT CSV 20260503"

PROJECT_ROOT = Path("C:/mountain_work/115_osm")

PROFILE_CSV = (
    PROJECT_ROOT
    / "outputs"
    / "ib1c_osm_semantic_risk"
    / CASE_ID
    / f"{CASE_ID}_osm_semantic_risk_profile.csv"
)

PROFILE_GEOJSON = (
    PROJECT_ROOT
    / "outputs"
    / "ib1c_osm_semantic_risk"
    / CASE_ID
    / f"{CASE_ID}_osm_semantic_risk_profile.geojson"
)

CONTOUR_CSV = (
    PROJECT_ROOT
    / "outputs"
    / "ib1g_contour_window_features"
    / CASE_ID
    / f"{CASE_ID}_contour_window_features.csv"
)

CONTOUR_GEOJSON = (
    PROJECT_ROOT
    / "outputs"
    / "ib1g_contour_window_features"
    / CASE_ID
    / f"{CASE_ID}_contour_window_features.geojson"
)

OUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "ib1e_route_profile_contour_window_terrain"
    / CASE_ID
)
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_CSV = OUT_DIR / f"{CASE_ID}_route_profile_contour_window_terrain_enriched.csv"
OUT_GEOJSON = OUT_DIR / f"{CASE_ID}_route_profile_contour_window_terrain_enriched.geojson"
OUT_SUMMARY_CSV = OUT_DIR / f"{CASE_ID}_route_profile_contour_window_terrain_summary.csv"


# =========================================================
# 1. 參數
# =========================================================
NOW_UTC = datetime.now(timezone.utc).isoformat()

PROFILE_DIST_COL = "dist_m"
CONTOUR_DIST_COL_CANDIDATES = ["dist_mid", "dist_mid_m"]

MAX_DIST_ALIGN_DIFF_M = 15.0

TERRAIN_KEEP_COLS = [
    "seg_id",
    "dist_mid",
    "dist_mid_m",
    "seg_len",
    "segment_len_m",
    "elev_min",
    "elev_max",
    "elev_range",
    "slope_window",
    "slope_band_window",
    "contour_density_20m",
    "pipeline_stage",
    "case_id",
    "case_name",
    "derived_at",
    "window_radius_m",
    "density_buffer_m",
    "elevation_source",
]


# =========================================================
# 2. 工具函式
# =========================================================
def choose_contour_dist_col(df: pd.DataFrame) -> str:
    for col in CONTOUR_DIST_COL_CANDIDATES:
        if col in df.columns:
            return col
    raise ValueError(f"找不到 contour distance 欄位，候選：{CONTOUR_DIST_COL_CANDIDATES}")


def classify_terrain_risk_from_window(row):
    """
    第一版 terrain risk hint：
    僅根據 contour window 的 slope_band_window 與 elev_range 給初步地形風險。
    後續可再與 OSM hydrology / weather 互動。
    """
    band = str(row.get("slope_band_window_nlsc", "")).strip().lower()
    elev_range = row.get("elev_range_nlsc_window", np.nan)

    if band == "very_steep":
        return 0.70
    if band == "steep":
        return 0.50
    if band == "moderate":
        return 0.30
    if band == "gentle":
        return 0.15
    if band == "flat":
        return 0.05

    if pd.notna(elev_range):
        if elev_range >= 60:
            return 0.65
        if elev_range >= 40:
            return 0.45
        if elev_range >= 20:
            return 0.25
        return 0.05

    return 0.0


def classify_hydro_terrain_amplifier(row):
    """
    OSM hydrology + NLSC terrain 的交互提示。
    這不是最終天氣風險，只是 terrain-aware hydrology potential。
    """
    needs_nlsc = str(row.get("needs_nlsc_flags", ""))
    weather_flags = str(row.get("weather_sensitive_flags", ""))
    band = str(row.get("slope_band_window_nlsc", "")).strip().lower()

    has_hydro = (
        "waterway" in needs_nlsc
        or "wetland" in needs_nlsc
        or "waterway" in weather_flags
        or "wetland" in weather_flags
    )

    if not has_hydro:
        return 0.0

    if band == "very_steep":
        return 0.45
    if band == "steep":
        return 0.35
    if band == "moderate":
        return 0.25
    if band in {"gentle", "flat"}:
        return 0.15

    return 0.20


def risk_band(score):
    if score < 0.20:
        return "low"
    if score < 0.40:
        return "moderate"
    if score < 0.65:
        return "high"
    return "very_high"


# =========================================================
# 3. 檢查輸入
# =========================================================
for fp in [PROFILE_CSV, PROFILE_GEOJSON, CONTOUR_CSV, CONTOUR_GEOJSON]:
    if not fp.exists():
        raise FileNotFoundError(f"找不到輸入檔：{fp.resolve()}")


# =========================================================
# 4. 讀資料
# =========================================================
profile_df = pd.read_csv(PROFILE_CSV, low_memory=False)
profile_gdf = gpd.read_file(PROFILE_GEOJSON)

contour_df = pd.read_csv(CONTOUR_CSV, low_memory=False)
contour_gdf = gpd.read_file(CONTOUR_GEOJSON)

if len(profile_df) != len(profile_gdf):
    raise ValueError(f"profile CSV / GeoJSON 筆數不一致：csv={len(profile_df)}, geojson={len(profile_gdf)}")

if PROFILE_DIST_COL not in profile_df.columns:
    raise ValueError(f"profile 找不到距離欄位：{PROFILE_DIST_COL}")

contour_dist_col = choose_contour_dist_col(contour_df)

print("case:", CASE_ID)
print("profile rows:", len(profile_df))
print("contour rows:", len(contour_df))
print("profile dist col:", PROFILE_DIST_COL)
print("contour dist col:", contour_dist_col)


# =========================================================
# 5. 整理 contour window 欄位
# =========================================================
keep_cols = [c for c in TERRAIN_KEEP_COLS if c in contour_df.columns]

if contour_dist_col not in keep_cols:
    keep_cols.append(contour_dist_col)

terrain_df = contour_df[keep_cols].copy()

# 統一距離欄位名稱
terrain_df = terrain_df.rename(columns={contour_dist_col: "terrain_dist_mid_m"})

# 避免重名，NLSC contour window 欄位加後綴
rename_map = {
    "seg_id": "terrain_segment_id",
    "dist_mid": "terrain_dist_mid_original",
    "dist_mid_m": "terrain_dist_mid_original",
    "seg_len": "terrain_segment_len_m",
    "segment_len_m": "terrain_segment_len_m",
    "elev_min": "elev_min_nlsc_window",
    "elev_max": "elev_max_nlsc_window",
    "elev_range": "elev_range_nlsc_window",
    "slope_window": "slope_window_nlsc",
    "slope_band_window": "slope_band_window_nlsc",
    "contour_density_20m": "contour_density_20m_nlsc_window",
    "pipeline_stage": "terrain_pipeline_stage",
    "case_id": "terrain_case_id",
    "case_name": "terrain_case_name",
    "derived_at": "terrain_derived_at",
    "window_radius_m": "terrain_window_radius_m",
    "density_buffer_m": "terrain_density_buffer_m",
    "elevation_source": "terrain_elevation_source",
}

terrain_df = terrain_df.rename(columns=rename_map)

# 如果 rename 後產生重複欄，保留第一個
terrain_df = terrain_df.loc[:, ~terrain_df.columns.duplicated()].copy()

terrain_df = terrain_df.sort_values("terrain_dist_mid_m").reset_index(drop=True)


# =========================================================
# 6. 以 distance axis 對齊 profile 與 contour window
# =========================================================
profile_work = profile_df.copy().reset_index(drop=True)
profile_work["profile_row_id"] = profile_work.index
profile_work["profile_dist_m"] = pd.to_numeric(profile_work[PROFILE_DIST_COL], errors="coerce")

profile_work = profile_work.sort_values("profile_dist_m").reset_index(drop=True)

aligned = pd.merge_asof(
    profile_work,
    terrain_df,
    left_on="profile_dist_m",
    right_on="terrain_dist_mid_m",
    direction="nearest",
)

aligned["dist_to_contour_window_mid_m"] = (
    aligned["profile_dist_m"] - aligned["terrain_dist_mid_m"]
).abs()

aligned["contour_window_match_status"] = np.where(
    aligned["dist_to_contour_window_mid_m"] <= MAX_DIST_ALIGN_DIFF_M,
    "matched",
    "unmatched",
)

# 對於距離超過門檻者，保留 match_status，但 terrain 欄位可仍留著供 QA；
# 正式模型可用 match_status 決定是否採用。


# =========================================================
# 7. 產生 terrain risk hint
# =========================================================
aligned["terrain_window_risk_score"] = aligned.apply(
    classify_terrain_risk_from_window,
    axis=1,
)

aligned["hydro_terrain_amplifier_score"] = aligned.apply(
    classify_hydro_terrain_amplifier,
    axis=1,
)

# 第一版 terrain-aware semantic risk：
# 保留原 osm_semantic_risk_score，再加上 terrain 與 hydro-terrain amplifier 的輕量權重。
if "osm_semantic_risk_score" in aligned.columns:
    base_osm = pd.to_numeric(aligned["osm_semantic_risk_score"], errors="coerce").fillna(0.0)
else:
    base_osm = 0.0

aligned["osm_terrain_combined_risk_score_raw"] = (
    base_osm
    + aligned["terrain_window_risk_score"] * 0.25
    + aligned["hydro_terrain_amplifier_score"] * 0.20
)

aligned["osm_terrain_combined_risk_score"] = (
    aligned["osm_terrain_combined_risk_score_raw"]
    .clip(lower=0.0, upper=1.0)
)

aligned["osm_terrain_combined_risk_band"] = aligned["osm_terrain_combined_risk_score"].apply(risk_band)


# =========================================================
# 8. 補 metadata
# =========================================================
aligned["contour_window_enriched_at"] = NOW_UTC
aligned["pipeline_stage"] = "ib1e_enrich_route_profile_with_contour_window_terrain"
aligned["contour_window_max_align_diff_m"] = MAX_DIST_ALIGN_DIFF_M


# =========================================================
# 9. 輸出 CSV / GeoJSON
# =========================================================
# 恢復原始順序
aligned = aligned.sort_values("profile_row_id").reset_index(drop=True)

out_df = aligned.drop(columns=["profile_row_id"], errors="ignore").copy()

out_gdf = profile_gdf.copy()

for col in out_df.columns:
    if col in out_gdf.columns:
        continue
    out_gdf[col] = out_df[col].values

# 如果 out_gdf 缺少新增欄位，補上；若原 GeoJSON 已有部分 profile 欄位則不覆蓋 geometry
for col in [
    "terrain_dist_mid_m",
    "dist_to_contour_window_mid_m",
    "contour_window_match_status",
    "elev_min_nlsc_window",
    "elev_max_nlsc_window",
    "elev_range_nlsc_window",
    "slope_window_nlsc",
    "slope_band_window_nlsc",
    "contour_density_20m_nlsc_window",
    "terrain_window_risk_score",
    "hydro_terrain_amplifier_score",
    "osm_terrain_combined_risk_score",
    "osm_terrain_combined_risk_band",
]:
    if col in out_df.columns:
        out_gdf[col] = out_df[col].values

out_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
out_gdf.to_file(OUT_GEOJSON, driver="GeoJSON")


# =========================================================
# 10. Summary
# =========================================================
summary_rows = []

summary_rows.append({"metric": "profile_rows", "value": len(profile_df)})
summary_rows.append({"metric": "contour_rows", "value": len(contour_df)})
summary_rows.append({"metric": "output_rows", "value": len(out_df)})
summary_rows.append({"metric": "max_dist_align_diff_m", "value": MAX_DIST_ALIGN_DIFF_M})

for status, n in out_df["contour_window_match_status"].value_counts(dropna=False).items():
    summary_rows.append({"metric": f"match_status_{status}", "value": int(n)})

for band, n in out_df["slope_band_window_nlsc"].value_counts(dropna=False).items():
    summary_rows.append({"metric": f"slope_band_window_nlsc_{band}", "value": int(n)})

for band, n in out_df["osm_terrain_combined_risk_band"].value_counts(dropna=False).items():
    summary_rows.append({"metric": f"combined_risk_band_{band}", "value": int(n)})

for col in [
    "dist_to_contour_window_mid_m",
    "terrain_window_risk_score",
    "hydro_terrain_amplifier_score",
    "osm_terrain_combined_risk_score",
]:
    summary_rows.append({"metric": f"{col}_min", "value": float(out_df[col].min())})
    summary_rows.append({"metric": f"{col}_mean", "value": float(out_df[col].mean())})
    summary_rows.append({"metric": f"{col}_max", "value": float(out_df[col].max())})

summary_df = pd.DataFrame(summary_rows)
summary_df.to_csv(OUT_SUMMARY_CSV, index=False, encoding="utf-8-sig")

print("\n完成！")
print("CSV:", OUT_CSV.resolve())
print("GeoJSON:", OUT_GEOJSON.resolve())
print("summary CSV:", OUT_SUMMARY_CSV.resolve())

print("\n=== contour window match status ===")
print(out_df["contour_window_match_status"].value_counts(dropna=False))

print("\n=== dist_to_contour_window_mid_m ===")
print(out_df["dist_to_contour_window_mid_m"].describe())

print("\n=== slope_band_window_nlsc ===")
print(out_df["slope_band_window_nlsc"].value_counts(dropna=False))

print("\n=== terrain_window_risk_score ===")
print(out_df["terrain_window_risk_score"].describe())

print("\n=== hydro_terrain_amplifier_score ===")
print(out_df["hydro_terrain_amplifier_score"].describe())

print("\n=== osm_terrain_combined_risk_band ===")
print(out_df["osm_terrain_combined_risk_band"].value_counts(dropna=False))