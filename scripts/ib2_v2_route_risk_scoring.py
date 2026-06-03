from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd


# =========================================================
# ib2_v2_route_risk_scoring.py
# Terrain-aware route risk scoring
#
# Inputs:
# - ib1c: OSM semantic enriched profile
# - ib1i: GPX vs Contour validation / fused terrain basis
# =========================================================


# =========================================================
# 0. 路徑設定
# =========================================================
SEMANTIC_CSV = Path("ib1c_route_profile_semantic_output/qixing_route_profile_semantic_enriched.csv")
VALIDATION_CSV = Path("ib1i_validation_output/qixing_gpx_vs_contour_validation.csv")

OUT_DIR = Path("ib2_v2_route_risk_output")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_CSV = OUT_DIR / "qixing_route_risk_v2.csv"


# =========================================================
# 1. 參數
# =========================================================
NOW_UTC = datetime.now(timezone.utc).isoformat()
RISK_MODEL_VERSION = "terrain_aware_rule_v0.3"


TERRAIN_SLOPE_WEIGHTS = {
    "flat": 0.0,
    "gentle": 0.5,
    "moderate": 1.2,
    "steep": 2.5,
    "very_steep": 4.0,
    "unknown": 0.5,
}

HAZARD_WEIGHTS = {
    "cliff": 4.0,
    "scree": 2.5,
    "bare_rock": 2.0,
    "landslide": 5.0,
}

HYDROLOGY_WEIGHTS = {
    "waterway": 1.5,
    "water_area": 1.5,
    "wetland": 2.0,
}

TECHNICAL_WEIGHTS = {
    "safety_rope": 2.0,
    "handrail": 1.0,
    "ladder": 4.0,
    "rungs": 3.0,
    "via_ferrata": 5.0,
    "assisted_trail": 3.0,
    "steps": 1.5,
}

SUPPORT_WEIGHTS = {
    "shelter": -1.0,
    "bench": -0.3,
    "picnic_table": -0.2,
    "picnic_site": -0.2,
    "drinking_water": -0.5,
    "toilets": -0.3,
    "information_office": -0.5,
    "visitor_centre": -0.8,
    "trailhead": -0.5,
    "guidepost": -0.3,
    "peak": 0.0,
}


# =========================================================
# 2. 工具函式
# =========================================================
def split_flags(value):
    if pd.isna(value):
        return []
    text = str(value).strip()
    if text in ["", "normal", "none", "nan"]:
        return []
    return [x for x in text.split("|") if x]


def score_sum(value, weight_map):
    return sum(weight_map.get(f, 0.0) for f in split_flags(value))


def score_max(value, weight_map):
    flags = split_flags(value)
    if not flags:
        return 0.0
    return max(weight_map.get(f, 0.0) for f in flags)


def slope_to_band(s):
    if pd.isna(s):
        return "unknown"
    if s < 0.05:
        return "flat"
    elif s < 0.10:
        return "gentle"
    elif s < 0.20:
        return "moderate"
    elif s < 0.35:
        return "steep"
    else:
        return "very_steep"


def risk_band(score):
    if score < 1.5:
        return "low"
    elif score < 3.5:
        return "moderate"
    elif score < 6.0:
        return "high"
    else:
        return "very_high"


def build_reason(row):
    """
    風險來源：
    只放「路線本身」或「地形/水文/技術特徵」造成的風險。
    不把 distance alignment 問題當成風險來源。
    """
    reasons = []

    for col in ["technical_flags", "hazard_flags", "hydrology_flags"]:
        for f in split_flags(row.get(col, "")):
            reasons.append(f)

    effort_band = row.get("effort_slope_band", "unknown")
    exposure_band = row.get("terrain_exposure_band", "unknown")

    if effort_band in ["steep", "very_steep"]:
        reasons.append(f"effort_{effort_band}")

    if exposure_band in ["steep", "very_steep"]:
        reasons.append(f"exposure_{exposure_band}")

    # GPX / contour mismatch 仍保留為風險判讀提醒，
    # 但 distance misaligned 不放在 risk_reason，改放 data_quality_reason。
    if row.get("gpx_quality_flag", "") == "mismatch":
        reasons.append("gpx_contour_mismatch")

    return "|".join(reasons) if reasons else "normal"


def build_data_quality_reason(row):
    """
    資料品質原因：
    用來標示此點的風險分數可信度，而不是直接提高風險分數。
    """
    reasons = []

    if row.get("gpx_quality_flag", "") == "mismatch":
        reasons.append("gpx_contour_mismatch")

    if not row.get("alignment_ok", True):
        reasons.append("dist_misaligned")

    if not row.get("within_validation_range", True):
        reasons.append("out_of_validation_range")

    return "|".join(reasons) if reasons else "normal"


# =========================================================
# 3. 讀資料
# =========================================================
for fp in [SEMANTIC_CSV, VALIDATION_CSV]:
    if not fp.exists():
        raise FileNotFoundError(f"找不到輸入檔：{fp.resolve()}")

semantic = pd.read_csv(SEMANTIC_CSV)
validation = pd.read_csv(VALIDATION_CSV)

print("semantic rows:", len(semantic))
print("validation rows:", len(validation))


# =========================================================
# 4. 欄位確認與距離對齊
# =========================================================
if "dist_m" not in semantic.columns:
    raise ValueError("semantic CSV 缺少 dist_m")

if "dist_mid" not in validation.columns:
    raise ValueError("validation CSV 缺少 dist_mid")

semantic = semantic.sort_values("dist_m").copy()
validation = validation.sort_values("dist_mid").copy()

df = pd.merge_asof(
    semantic,
    validation,
    left_on="dist_m",
    right_on="dist_mid",
    direction="nearest",
    suffixes=("", "_terrain"),
)

df["dist_alignment_diff_m"] = df["dist_m"] - df["dist_mid"]

# 距離對齊防呆：避免尾端或缺資料時對到太遠的 terrain segment
MAX_DIST_ALIGNMENT_M = 50.0

df["alignment_ok"] = (
    df["dist_alignment_diff_m"].abs() <= MAX_DIST_ALIGNMENT_M
)

# validation / contour 資料的有效距離範圍
# 若 semantic dist_m 超出 validation dist_mid 範圍，就標示為低可信度區段。
VALIDATION_DIST_MIN_M = validation["dist_mid"].min()
VALIDATION_DIST_MAX_M = validation["dist_mid"].max()

df["within_validation_range"] = (
    (df["dist_m"] >= VALIDATION_DIST_MIN_M) &
    (df["dist_m"] <= VALIDATION_DIST_MAX_M)
)

# route_data_ok 代表此點的地形資料可正常用於坡度與風險判讀
df["route_data_ok"] = (
    df["within_validation_range"] &
    df["alignment_ok"]
)


if "gpx_quality_flag" not in df.columns:
    df["gpx_quality_flag"] = "unknown"


df["risk_confidence"] = np.select(
    [
        ~df["within_validation_range"],
        ~df["alignment_ok"],
        df["gpx_quality_flag"].eq("mismatch"),
    ],
    [
        "low_out_of_validation_range",
        "low_distance_misaligned",
        "medium_gpx_contour_mismatch",
    ],
    default="normal",
)


# =========================================================
# 5. 建立 effort_slope / terrain_exposure
# =========================================================
# effort_slope：代表使用者實際走在步道路面上的體力坡度
# 原則上以 GPX 為主；若 GPX 與 contour 差異大，仍保留 GPX，但標記為 mismatch
df["effort_slope"] = df["slope_gpx_window"]

df["effort_slope"] = df["effort_slope"].replace([np.inf, -np.inf], np.nan)
df["effort_slope"] = df["effort_slope"].clip(lower=0, upper=1.0)

df["effort_slope_band"] = df["effort_slope"].apply(slope_to_band)


# terrain_exposure_slope：代表周邊原始地貌陡峭程度
# 由 ContourL window 推估，不等於實際步道路面坡度
df["terrain_exposure_slope"] = df["slope_contour_window"]

df["terrain_exposure_slope"] = df["terrain_exposure_slope"].replace([np.inf, -np.inf], np.nan)
df["terrain_exposure_slope"] = df["terrain_exposure_slope"].clip(lower=0, upper=1.0)

df["terrain_exposure_band"] = df["terrain_exposure_slope"].apply(slope_to_band)


# 保留舊欄位名稱，避免下游暫時爆掉
# 但語意上 slope_final 只是 backward-compatible 欄位
df["slope_final"] = np.where(
    (df["gpx_quality_flag"] == "ok") & (df["route_data_ok"]),
    0.7 * df["effort_slope"] + 0.3 * df["terrain_exposure_slope"],
    df["terrain_exposure_slope"],
)

df["slope_final"] = df["slope_final"].replace([np.inf, -np.inf], np.nan)
df["slope_final"] = df["slope_final"].clip(lower=0, upper=1.0)
df["slope_final_band"] = df["slope_final"].apply(slope_to_band)


# =========================================================
# 6. Terrain score
# =========================================================
# effort_score：體力消耗，主要由實際步道路面坡度決定
df["effort_score"] = df["effort_slope_band"].apply(
    lambda x: TERRAIN_SLOPE_WEIGHTS.get(str(x), 0.5)
)

# exposure_score：地貌暴露，主要由周邊等高線地形強度決定
df["exposure_score"] = df["terrain_exposure_band"].apply(
    lambda x: TERRAIN_SLOPE_WEIGHTS.get(str(x), 0.5)
)

if "contour_density_20m" in df.columns:
    df["terrain_density_score"] = df["contour_density_20m"].fillna(0).clip(upper=5) * 0.3
else:
    df["terrain_density_score"] = 0.0

if "gpx_quality_flag" in df.columns:
    # GPX / contour mismatch 可作為輕微不確定性懲罰。
    # 但 distance misaligned 屬於資料品質/可信度問題，
    # 不應直接增加路線風險分數。
    df["terrain_quality_penalty"] = np.where(
        df["gpx_quality_flag"] == "mismatch",
        0.5,
        0.0,
    )
else:
    df["terrain_quality_penalty"] = 0.0

# 目前先用 60% effort + 40% exposure
# 之後若遇到 bridge / tunnel / boardwalk，可降低 exposure 權重
# exposure_score 目前以固定權重納入；未來應由 weather_factor 動態放大/縮小
df["terrain_score"] = (
    0.6 * df["effort_score"]
    + 0.4 * df["exposure_score"]
    + df["terrain_density_score"]
    + df["terrain_quality_penalty"]
)


# =========================================================
# 7. Semantic risk score
# =========================================================
for col in [
    "technical_flags",
    "hazard_flags",
    "hydrology_flags",
    "facility_flags",
    "rest_flags",
    "support_flags",
    "landmark_flags",
]:
    if col not in df.columns:
        df[col] = "none"

df["risk_technical"] = df["technical_flags"].apply(
    lambda x: score_sum(x, TECHNICAL_WEIGHTS)
)

# 同一地貌不要 double count，用 max
df["risk_hazard"] = df["hazard_flags"].apply(
    lambda x: score_max(x, HAZARD_WEIGHTS)
)

df["risk_hydrology"] = df["hydrology_flags"].apply(
    lambda x: score_max(x, HYDROLOGY_WEIGHTS)
)

df["risk_support_adjustment"] = (
    df["facility_flags"].apply(lambda x: score_sum(x, SUPPORT_WEIGHTS))
    + df["rest_flags"].apply(lambda x: score_sum(x, SUPPORT_WEIGHTS))
    + df["support_flags"].apply(lambda x: score_sum(x, SUPPORT_WEIGHTS))
    + df["landmark_flags"].apply(lambda x: score_sum(x, SUPPORT_WEIGHTS))
)


# =========================================================
# 8. Final risk
# =========================================================
df["risk_score_raw"] = (
    df["terrain_score"]
    + df["risk_technical"]
    + df["risk_hazard"]
    + df["risk_hydrology"]
    + df["risk_support_adjustment"]
)

df["risk_score"] = df["risk_score_raw"].clip(lower=0)
df["risk_band"] = df["risk_score"].apply(risk_band)

# 風險來源與資料品質來源分開
df["risk_reason"] = df.apply(build_reason, axis=1)
df["data_quality_reason"] = df.apply(build_data_quality_reason, axis=1)

df["risk_model_version"] = RISK_MODEL_VERSION
df["risk_scored_at"] = NOW_UTC
df["pipeline_stage"] = "ib2_v2_route_risk_scoring"


# =========================================================
# 9. 輸出
# =========================================================
df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

print("\n完成！")
print("CSV:", OUT_CSV.resolve())

print("\n=== risk_band distribution ===")
print(df["risk_band"].value_counts(dropna=False))

print("\n=== slope_final_band ===")
print(df["slope_final_band"].value_counts(dropna=False))

print("\n=== effort_slope_band ===")
print(df["effort_slope_band"].value_counts(dropna=False))

print("\n=== terrain_exposure_band ===")
print(df["terrain_exposure_band"].value_counts(dropna=False))

print("\n=== gpx_quality_flag ===")
print(df["gpx_quality_flag"].value_counts(dropna=False))

print("\n=== alignment_ok ===")
print(df["alignment_ok"].value_counts(dropna=False))

print("\n=== within_validation_range ===")
print(df["within_validation_range"].value_counts(dropna=False))

print("\n=== risk_confidence ===")
print(df["risk_confidence"].value_counts(dropna=False))

print("\n=== data_quality_reason ===")
print(df["data_quality_reason"].value_counts(dropna=False))

print("\n=== OSM route semantics ===")
for c in [
    "osm_highway",
    "osm_surface",
    "route_semantic_class",
    "surface_class",
    "assist_class",
    "visibility_class",
    "osm_difficulty_class",
]:
    if c in df.columns:
        print(f"\n--- {c} ---")
        print(df[c].value_counts(dropna=False))

print("\n=== top risk points ===")
cols = [
    "dist_m",
    "dist_mid",
    "dist_alignment_diff_m",
    "within_validation_range",
    "alignment_ok",
    "route_data_ok",
    "risk_confidence",
    "data_quality_reason",

    # OSM route semantics from ib1c
    "near_highway",
    "dist_highway_m",
    "osm_way_name",
    "osm_highway",
    "osm_surface",
    "osm_tracktype",
    "osm_smoothness",
    "osm_trail_visibility",
    "osm_sac_scale",
    "osm_incline",
    "osm_lit",
    "osm_handrail",
    "osm_safety_rope",
    "osm_step_count",
    "osm_width",
    "osm_bridge",
    "osm_bridge_material",
    "osm_ford",
    "osm_tunnel",
    "route_semantic_class",
    "surface_class",
    "assist_class",
    "visibility_class",
    "osm_difficulty_class",

    "ele_gpx_m",
    "effort_slope",
    "effort_slope_band",
    "terrain_exposure_slope",
    "terrain_exposure_band",
    "slope_final",
    "slope_final_band",
    "gpx_quality_flag",
    "technical_flags",
    "hazard_flags",
    "hydrology_flags",
    "effort_score",
    "exposure_score",
    "terrain_density_score",
    "terrain_quality_penalty",
    "terrain_score",
    "risk_score",
    "risk_band",
    "risk_reason",
]
cols = [c for c in cols if c in df.columns]

print(
    df.sort_values("risk_score", ascending=False)[cols]
    .head(20)
    .to_string(index=False)
)