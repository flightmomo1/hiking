# =========================================================
# ib1f_summarize_prototype_A_risk_segments.py
#
# 目的：
# - 讀取 Prototype A combined risk profile
# - 將 1m profile 彙整成固定距離風險路段摘要
# - 輸出可讀的 high/moderate/low risk segment table
# =========================================================

from pathlib import Path
import pandas as pd


# =========================================================
# 0. Case 設定
# =========================================================
CASE_ID = "juansi_waterfall_fitcsv_20260503"
CASE_NAME = "絹絲瀑布 FIT CSV 20260503"
MODEL_VERSION = "prototype_A_terrain_dominant_v1"

IN_CSV = (
    Path("outputs")
    / "ib1e_osm_nlsc_terrain_risk"
    / CASE_ID
    / f"{CASE_ID}_osm_nlsc_terrain_risk_profile.csv"
)

OUT_DIR = Path("outputs") / "prototype_A_terrain_dominant" / CASE_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_SEGMENT_CSV = OUT_DIR / f"{CASE_ID}_prototype_A_risk_segments_100m.csv"
OUT_HIGH_SEGMENT_CSV = OUT_DIR / f"{CASE_ID}_prototype_A_high_risk_segments.csv"
OUT_SUMMARY_TXT = OUT_DIR / f"{CASE_ID}_prototype_A_segment_summary.txt"


# =========================================================
# 1. 參數
# =========================================================
SEGMENT_SIZE_M = 100.0

HIGH_RISK_THRESHOLD = 0.40
VERY_HIGH_RISK_THRESHOLD = 0.65

REQUIRED_COLS = [
    "dist_m",
    "osm_semantic_risk_score",
    "terrain_window_risk_score",
    "hydro_terrain_amplifier_score",
    "osm_terrain_combined_risk_score",
    "osm_terrain_combined_risk_band",
]


# =========================================================
# 2. 工具函式
# =========================================================
def norm_text(v):
    if pd.isna(v):
        return ""
    text = str(v).strip()
    if text.lower() in {"", "nan", "none", "<na>", "na", "null"}:
        return ""
    return text


def dominant_value(series):
    s = series.dropna().astype(str)
    s = s[s.str.strip() != ""]
    if s.empty:
        return ""
    return s.value_counts().idxmax()


def value_ratio(series, keyword):
    s = series.fillna("").astype(str)
    return s.str.contains(keyword, case=False, regex=False).mean()


def risk_band_from_score(score):
    if score < 0.20:
        return "low"
    if score < 0.40:
        return "moderate"
    if score < 0.65:
        return "high"
    return "very_high"


def make_main_reason(row):
    reasons = []

    if row["mean_terrain_risk"] >= 0.60:
        reasons.append("terrain_high")
    elif row["mean_terrain_risk"] >= 0.40:
        reasons.append("terrain_moderate")

    if row["hydrology_present_ratio"] >= 0.50:
        reasons.append("hydrology_present")

    if row["mean_hydro_amplifier"] >= 0.30:
        reasons.append("hydro_terrain_amplified")

    if row["steps_ratio"] >= 0.20:
        reasons.append("steps_present")

    if row["sett_surface_ratio"] >= 0.50:
        reasons.append("sett_surface")

    if row["bridge_ratio"] > 0:
        reasons.append("bridge_conditional")

    if row["dominant_slope_band"] in {"steep", "very_steep"}:
        reasons.append(f"slope_{row['dominant_slope_band']}")

    if not reasons:
        reasons.append("low_or_mixed_risk")

    return "|".join(reasons)


# =========================================================
# 3. 讀資料與檢查
# =========================================================
if not IN_CSV.exists():
    raise FileNotFoundError(f"找不到輸入檔：{IN_CSV.resolve()}")

df = pd.read_csv(IN_CSV, low_memory=False)

missing = [c for c in REQUIRED_COLS if c not in df.columns]
if missing:
    raise ValueError(f"缺少必要欄位：{missing}")

df = df.copy()
df["segment_id_100m"] = (df["dist_m"] // SEGMENT_SIZE_M).astype(int)
df["segment_start_m"] = df["segment_id_100m"] * SEGMENT_SIZE_M
df["segment_end_m"] = df["segment_start_m"] + SEGMENT_SIZE_M

print("case:", CASE_ID)
print("rows:", len(df))
print("route length approx:", df["dist_m"].max())
print("segment size m:", SEGMENT_SIZE_M)


# =========================================================
# 4. 彙整 100m segments
# =========================================================
rows = []

for seg_id, g in df.groupby("segment_id_100m"):
    g = g.sort_values("dist_m")

    start_m = float(g["segment_start_m"].iloc[0])
    end_m = float(min(g["segment_end_m"].iloc[0], df["dist_m"].max()))

    mean_combined = float(g["osm_terrain_combined_risk_score"].mean())
    max_combined = float(g["osm_terrain_combined_risk_score"].max())
    p75_combined = float(g["osm_terrain_combined_risk_score"].quantile(0.75))

    mean_osm = float(g["osm_semantic_risk_score"].mean())
    mean_terrain = float(g["terrain_window_risk_score"].mean())
    mean_hydro = float(g["hydro_terrain_amplifier_score"].mean())

    high_ratio = float((g["osm_terrain_combined_risk_score"] >= HIGH_RISK_THRESHOLD).mean())
    very_high_ratio = float((g["osm_terrain_combined_risk_score"] >= VERY_HIGH_RISK_THRESHOLD).mean())

    hydrology_ratio = 0.0
    if "hydrology_flags" in g.columns:
        hydrology_ratio = float(
            g["hydrology_flags"]
            .fillna("")
            .astype(str)
            .str.contains("waterway|wetland", case=False, regex=True)
            .mean()
        )

    steps_ratio = 0.0
    if "osm_highway" in g.columns:
        steps_ratio = float(
            g["osm_highway"]
            .fillna("")
            .astype(str)
            .str.lower()
            .eq("steps")
            .mean()
        )

    sett_ratio = 0.0
    if "osm_surface" in g.columns:
        sett_ratio = float(
            g["osm_surface"]
            .fillna("")
            .astype(str)
            .str.lower()
            .eq("sett")
            .mean()
        )

    bridge_ratio = 0.0
    if "conditional_factor_flags" in g.columns:
        bridge_ratio = float(
            g["conditional_factor_flags"]
            .fillna("")
            .astype(str)
            .str.contains("bridge", case=False, regex=False)
            .mean()
        )

    dominant_slope = ""
    if "terrain_slope_band_window" in g.columns:
        dominant_slope = dominant_value(g["terrain_slope_band_window"])

    dominant_risk_band = risk_band_from_score(mean_combined)

    row = {
        "case_id": CASE_ID,
        "case_name": CASE_NAME,
        "model_version": MODEL_VERSION,
        "segment_id": int(seg_id),
        "start_dist_m": round(start_m, 2),
        "end_dist_m": round(end_m, 2),
        "point_n": int(len(g)),

        "mean_combined_risk": round(mean_combined, 6),
        "p75_combined_risk": round(p75_combined, 6),
        "max_combined_risk": round(max_combined, 6),
        "dominant_risk_band": dominant_risk_band,

        "mean_osm_semantic_risk": round(mean_osm, 6),
        "mean_terrain_risk": round(mean_terrain, 6),
        "mean_hydro_amplifier": round(mean_hydro, 6),

        "high_risk_point_ratio": round(high_ratio, 6),
        "very_high_risk_point_ratio": round(very_high_ratio, 6),

        "dominant_slope_band": dominant_slope,
        "hydrology_present_ratio": round(hydrology_ratio, 6),
        "steps_ratio": round(steps_ratio, 6),
        "sett_surface_ratio": round(sett_ratio, 6),
        "bridge_ratio": round(bridge_ratio, 6),
    }

    row["main_reason"] = make_main_reason(row)

    rows.append(row)

seg_df = pd.DataFrame(rows)


# =========================================================
# 5. 輸出 high risk subset
# =========================================================
high_df = seg_df[
    (seg_df["dominant_risk_band"].isin(["high", "very_high"]))
    | (seg_df["high_risk_point_ratio"] >= 0.50)
].copy()

seg_df.to_csv(OUT_SEGMENT_CSV, index=False, encoding="utf-8-sig")
high_df.to_csv(OUT_HIGH_SEGMENT_CSV, index=False, encoding="utf-8-sig")


# =========================================================
# 6. Summary
# =========================================================
summary_lines = [
    f"Prototype A Risk Segment Summary",
    f"case_id: {CASE_ID}",
    f"case_name: {CASE_NAME}",
    f"model_version: {MODEL_VERSION}",
    "",
    f"input: {IN_CSV}",
    f"segment_size_m: {SEGMENT_SIZE_M}",
    f"profile_points: {len(df)}",
    f"segments: {len(seg_df)}",
    f"high_segments: {len(high_df)}",
    "",
    "dominant_risk_band counts:",
    str(seg_df["dominant_risk_band"].value_counts()),
    "",
    "dominant_slope_band counts:",
    str(seg_df["dominant_slope_band"].value_counts()),
    "",
    f"segment CSV: {OUT_SEGMENT_CSV}",
    f"high risk CSV: {OUT_HIGH_SEGMENT_CSV}",
]

OUT_SUMMARY_TXT.write_text("\n".join(summary_lines), encoding="utf-8")

print("\n完成！")
print("segment CSV:", OUT_SEGMENT_CSV.resolve())
print("high risk CSV:", OUT_HIGH_SEGMENT_CSV.resolve())
print("summary TXT:", OUT_SUMMARY_TXT.resolve())

print("\n--- dominant risk band ---")
print(seg_df["dominant_risk_band"].value_counts())

print("\n--- dominant slope band ---")
print(seg_df["dominant_slope_band"].value_counts())

print("\n--- high risk segments preview ---")
print(
    high_df[
        [
            "segment_id",
            "start_dist_m",
            "end_dist_m",
            "mean_combined_risk",
            "max_combined_risk",
            "dominant_risk_band",
            "dominant_slope_band",
            "hydrology_present_ratio",
            "main_reason",
        ]
    ].head(30)
)