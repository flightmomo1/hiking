# =========================================================
# ib1e_combine_osm_semantic_and_nlsc_terrain_risk.py
#
# 目的：
# - 讀取 ib1c_apply_osm_semantic_risk_mapping.py 產出的 OSM semantic risk profile
# - 讀取 ib1g_v2_compute_contour_window_features.py 產出的 contour window terrain features
# - 以 dist_m 對 dist_mid 最近鄰合併
# - 計算 terrain_window_risk_score
# - 計算 hydro_terrain_amplifier_score

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
MODEL_NOTE = "OSM semantic + NLSC terrain window + hydro terrain amplifier; terrain-dominant prototype"

OSM_RISK_CSV = (
    Path("outputs")
    / "ib1c_osm_semantic_risk"
    / CASE_ID
    / f"{CASE_ID}_osm_semantic_risk_profile.csv"
)

OSM_RISK_GEOJSON = (
    Path("outputs")
    / "ib1c_osm_semantic_risk"
    / CASE_ID
    / f"{CASE_ID}_osm_semantic_risk_profile.geojson"
)

CONTOUR_FEATURE_CSV = (
    Path("outputs")
    / "ib1g_contour_window_features"
    / CASE_ID
    / f"{CASE_ID}_contour_window_features.csv"
)

OUT_DIR = Path("outputs") / "ib1e_osm_nlsc_terrain_risk" / CASE_ID
OUT_DIR = Path("outputs") / "prototype_A_terrain_dominant" / CASE_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_CSV = OUT_DIR / f"{CASE_ID}_osm_nlsc_terrain_risk_profile.csv"
OUT_GEOJSON = OUT_DIR / f"{CASE_ID}_osm_nlsc_terrain_risk_profile.geojson"
OUT_SUMMARY_CSV = OUT_DIR / f"{CASE_ID}_osm_nlsc_terrain_risk_summary.csv"


# =========================================================
# 1. 參數
# =========================================================
MAX_DIST_MATCH_M = 20.0

# terrain window risk 分數表
SLOPE_BAND_WINDOW_SCORE = {
    "flat": 0.05,
    "gentle": 0.15,
    "moderate": 0.35,
    "steep": 0.55,
    "very_steep": 0.70,
    "unknown": 0.20,
    "": 0.20,
}

# combined risk 權重
W_OSM_SEMANTIC = 0.35
W_TERRAIN_WINDOW = 0.45
W_HYDRO_TERRAIN = 0.20


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


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, float(v)))


def nearest_by_distance_axis(profile_df, terrain_df):
    """
    對每個 profile point 的 dist_m，找最近 contour window 的 dist_mid。
    """
    if "dist_m" not in profile_df.columns:
        raise ValueError("OSM risk profile 缺少 dist_m 欄位")

    if "dist_mid" not in terrain_df.columns:
        raise ValueError("contour window features 缺少 dist_mid 欄位")

    terrain_sorted = terrain_df.sort_values("dist_mid").reset_index(drop=True)

    matched_rows = []

    terrain_dist = terrain_sorted["dist_mid"].astype(float).values

    for _, row in profile_df.iterrows():
        d = float(row["dist_m"])

        # 用 pandas / numpy 都可，這裡用簡單寫法，3973 x 199 筆規模可接受
        idx = abs(terrain_dist - d).argmin()
        terrain_row = terrain_sorted.iloc[idx].copy()

        terrain_row["terrain_match_dist_m"] = abs(float(terrain_row["dist_mid"]) - d)

        matched_rows.append(terrain_row)

    return pd.DataFrame(matched_rows).reset_index(drop=True)


def terrain_window_risk_score(row):
    """
    第一版地形窗風險：
    - 主要依 terrain_slope_band_window
    - terrain_elev_range / terrain_contour_density_20m 作為微調
    """
    band = norm_text(row.get("terrain_slope_band_window", "unknown"))
    base = SLOPE_BAND_WINDOW_SCORE.get(band, 0.20)

    elev_range = pd.to_numeric(row.get("terrain_elev_range", 0.0), errors="coerce")
    density = pd.to_numeric(row.get("terrain_contour_density_20m", 0.0), errors="coerce")

    if pd.isna(elev_range):
        elev_range = 0.0
    if pd.isna(density):
        density = 0.0

    elev_bonus = min(float(elev_range) / 70.0, 1.0) * 0.15
    density_bonus = min(float(density) / 5.0, 1.0) * 0.05

    return clamp(base + elev_bonus + density_bonus, 0.0, 1.0)


def hydro_terrain_amplifier_score(row):
    """
    水文 + 地形的條件式放大因子。
    只有當 OSM 顯示 waterway / wetland 且 NLSC terrain 較陡時才拉高。
    """
    hydrology = str(row.get("hydrology_flags", ""))
    needs_nlsc = str(row.get("needs_nlsc_flags", ""))

    has_hydro = (
        "waterway" in hydrology
        or "wetland" in hydrology
        or "waterway" in needs_nlsc
        or "wetland" in needs_nlsc
    )

    if not has_hydro:
        return 0.0

    terrain_score = float(row.get("terrain_window_risk_score", 0.0))

    surface = str(row.get("osm_surface", "")).lower()
    route_type = str(row.get("osm_highway", "")).lower()

    surface_bonus = 0.0
    if surface in {"sett", "wood", "rock", "mud", "earth", "dirt"}:
        surface_bonus += 0.10

    if route_type == "steps":
        surface_bonus += 0.05

    # 水文存在時，地形越陡，放大越明顯
    return clamp(terrain_score * 0.50 + surface_bonus, 0.0, 0.70)


def combined_risk_score(row):
    osm_score = float(row.get("osm_semantic_risk_score", 0.0))
    terrain_score = float(row.get("terrain_window_risk_score", 0.0))
    hydro_score = float(row.get("hydro_terrain_amplifier_score", 0.0))

    score = (
        osm_score * W_OSM_SEMANTIC
        + terrain_score * W_TERRAIN_WINDOW
        + hydro_score * W_HYDRO_TERRAIN
    )

    return clamp(score, 0.0, 1.0)


def risk_band(score):
    score = float(score)

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
for fp in [OSM_RISK_CSV, OSM_RISK_GEOJSON, CONTOUR_FEATURE_CSV]:
    if not fp.exists():
        raise FileNotFoundError(f"找不到輸入檔：{fp.resolve()}")


# =========================================================
# 4. 讀資料
# =========================================================
osm_df = pd.read_csv(OSM_RISK_CSV, low_memory=False)
osm_geo = gpd.read_file(OSM_RISK_GEOJSON)
terrain_df = pd.read_csv(CONTOUR_FEATURE_CSV, low_memory=False)

print("case:", CASE_ID)
print("OSM risk rows:", len(osm_df))
print("OSM risk cols:", len(osm_df.columns))
print("terrain rows:", len(terrain_df))
print("terrain cols:", len(terrain_df.columns))

if len(osm_df) != len(osm_geo):
    raise ValueError(f"OSM CSV 與 GeoJSON 筆數不一致：csv={len(osm_df)}, geojson={len(osm_geo)}")


# =========================================================
# 5. 以 dist_m 對 dist_mid 最近鄰合併
# =========================================================
matched_terrain = nearest_by_distance_axis(osm_df, terrain_df)

# 避免欄位名稱衝突：terrain 欄位加 prefix，但保留幾個常用欄位另存
terrain_keep = matched_terrain.copy()

rename_cols = {}
for col in terrain_keep.columns:
    if col not in {"dist_mid", "terrain_match_dist_m"}:
        rename_cols[col] = f"terrain_{col}"

terrain_keep = terrain_keep.rename(columns=rename_cols)

out_df = pd.concat(
    [
        osm_df.reset_index(drop=True),
        terrain_keep.reset_index(drop=True),
    ],
    axis=1,
)

# 合併距離品質
out_df["terrain_match_ok"] = out_df["terrain_match_dist_m"] <= MAX_DIST_MATCH_M


# =========================================================
# 6. 計算 NLSC terrain / hydro terrain / combined risk
# =========================================================
out_df["terrain_window_risk_score"] = out_df.apply(terrain_window_risk_score, axis=1)
out_df["hydro_terrain_amplifier_score"] = out_df.apply(hydro_terrain_amplifier_score, axis=1)
out_df["osm_terrain_combined_risk_score"] = out_df.apply(combined_risk_score, axis=1)
out_df["osm_terrain_combined_risk_band"] = out_df["osm_terrain_combined_risk_score"].apply(risk_band)

# 方便 QA 的文字欄位
out_df["terrain_risk_reason"] = (
    "slope_band_window="
    + out_df.get("terrain_slope_band_window", "").astype(str)
    + "|elev_range="
    + out_df.get("terrain_elev_range", "").astype(str)
    + "|hydro="
    + out_df.get("hydrology_flags", "").astype(str)
)


# =========================================================
# 7. GeoJSON 輸出
# =========================================================
out_geo = osm_geo.copy()

for col in [
    "dist_mid",
    "terrain_match_dist_m",
    "terrain_match_ok",
    "terrain_elev_min",
    "terrain_elev_max",
    "terrain_elev_range",
    "terrain_slope_window",
    "terrain_slope_band_window",
    "terrain_contour_density_20m",
    "terrain_window_risk_score",
    "hydro_terrain_amplifier_score",
    "osm_terrain_combined_risk_score",
    "osm_terrain_combined_risk_band",
    "terrain_risk_reason",
]:
    if col in out_df.columns:
        out_geo[col] = out_df[col].values


# =========================================================
# 8. 輸出
# =========================================================
out_df["risk_model_version"] = MODEL_VERSION
out_df["risk_model_note"] = MODEL_NOTE

out_geo["risk_model_version"] = MODEL_VERSION
out_geo["risk_model_note"] = MODEL_NOTE

out_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
out_geo.to_file(OUT_GEOJSON, driver="GeoJSON")


# =========================================================
# 9. Summary
# =========================================================
summary_rows = []

def add_summary(metric, value):
    summary_rows.append({"metric": metric, "value": value})


add_summary("case_id", CASE_ID)
add_summary("rows", len(out_df))
add_summary("model_version", MODEL_VERSION)
add_summary("model_note", MODEL_NOTE)
add_summary("terrain_match_ok_n", int(out_df["terrain_match_ok"].sum()))
add_summary("terrain_match_not_ok_n", int((~out_df["terrain_match_ok"]).sum()))

for col in [
    "osm_semantic_risk_score",
    "terrain_window_risk_score",
    "hydro_terrain_amplifier_score",
    "osm_terrain_combined_risk_score",
]:
    add_summary(f"{col}_min", float(out_df[col].min()))
    add_summary(f"{col}_mean", float(out_df[col].mean()))
    add_summary(f"{col}_max", float(out_df[col].max()))

for band, n in out_df["osm_terrain_combined_risk_band"].value_counts().items():
    add_summary(f"combined_band_{band}_n", int(n))

if "terrain_slope_band_window" in out_df.columns:
    for band, n in out_df["terrain_slope_band_window"].value_counts().items():
        add_summary(f"terrain_slope_band_{band}_n", int(n))

summary_df = pd.DataFrame(summary_rows)
summary_df.to_csv(OUT_SUMMARY_CSV, index=False, encoding="utf-8-sig")


print("\n完成！")
print("combined CSV:", OUT_CSV.resolve())
print("combined GeoJSON:", OUT_GEOJSON.resolve())
print("summary CSV:", OUT_SUMMARY_CSV.resolve())

print("\n--- match quality ---")
print(out_df["terrain_match_ok"].value_counts(dropna=False))

print("\n--- score summary ---")
for col in [
    "osm_semantic_risk_score",
    "terrain_window_risk_score",
    "hydro_terrain_amplifier_score",
    "osm_terrain_combined_risk_score",
]:
    print(f"\n{col}")
    print(out_df[col].describe())

print("\n--- combined risk band ---")
print(out_df["osm_terrain_combined_risk_band"].value_counts(dropna=False))

if "terrain_slope_band_window" in out_df.columns:
    print("\n--- terrain slope band window ---")
    print(out_df["terrain_slope_band_window"].value_counts(dropna=False))