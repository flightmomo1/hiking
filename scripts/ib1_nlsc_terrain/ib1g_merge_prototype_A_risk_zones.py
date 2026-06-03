# =========================================================
# ib1g_merge_prototype_A_risk_zones.py
#
# 目的：
# - 讀取 Prototype A 100m risk segment summary
# - 將連續 high / moderate / low risk segments 合併成 risk zones
# - 輸出可讀的風險區間表
# =========================================================

from pathlib import Path
import pandas as pd


# =========================================================
# 0. Case 設定
# =========================================================
CASE_ID = "juansi_waterfall_fitcsv_20260503"
CASE_NAME = "絹絲瀑布 FIT CSV 20260503"
MODEL_VERSION = "prototype_A_terrain_dominant_v1"

IN_SEGMENT_CSV = (
    Path("outputs")
    / "prototype_A_terrain_dominant"
    / CASE_ID
    / f"{CASE_ID}_prototype_A_risk_segments_100m.csv"
)

OUT_DIR = Path("outputs") / "prototype_A_terrain_dominant" / CASE_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_ZONE_CSV = OUT_DIR / f"{CASE_ID}_prototype_A_risk_zones.csv"
OUT_HIGH_ZONE_CSV = OUT_DIR / f"{CASE_ID}_prototype_A_high_risk_zones.csv"
OUT_SUMMARY_TXT = OUT_DIR / f"{CASE_ID}_prototype_A_risk_zone_summary.txt"


# =========================================================
# 1. 參數
# =========================================================
# 合併策略：
# - 連續相同 dominant_risk_band 的 100m segment 合併
# - high / very_high 視為 high_group
# - moderate 維持 moderate_group
# - low 維持 low_group
MERGE_HIGH_AND_VERY_HIGH = True

# 允許中間插入短 low/moderate 噪音段的距離，Prototype A 先保守設 0
# 之後可改成 100m，讓 high 區間更連續。
ALLOW_GAP_SEGMENTS = 0

HIGH_ZONE_BANDS = {"high", "very_high"}


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


def risk_group(band):
    band = norm_text(band)

    if MERGE_HIGH_AND_VERY_HIGH and band in {"high", "very_high"}:
        return "high"

    if band in {"low", "moderate", "high", "very_high"}:
        return band

    return "unknown"


def dominant_value(series):
    s = series.dropna().astype(str)
    s = s[s.str.strip() != ""]
    if s.empty:
        return ""
    return s.value_counts().idxmax()


def weighted_mean(values, weights):
    values = pd.to_numeric(values, errors="coerce")
    weights = pd.to_numeric(weights, errors="coerce")

    mask = values.notna() & weights.notna() & (weights > 0)

    if not mask.any():
        return float(values.mean()) if values.notna().any() else 0.0

    return float((values[mask] * weights[mask]).sum() / weights[mask].sum())


def merge_reason_text(reason_series):
    """
    合併 main_reason，依出現頻率排序。
    """
    counts = {}

    for text in reason_series.dropna().astype(str):
        for item in text.split("|"):
            item = item.strip()
            if not item:
                continue
            counts[item] = counts.get(item, 0) + 1

    if not counts:
        return ""

    ordered = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    return "|".join([k for k, _ in ordered])


def make_warning_text(row):
    band = row["zone_risk_group"]
    start = row["start_dist_m"]
    end = row["end_dist_m"]
    reason = row["zone_main_reason"]

    if band == "high":
        prefix = "高風險區間"
    elif band == "moderate":
        prefix = "中風險區間"
    elif band == "low":
        prefix = "低風險區間"
    else:
        prefix = "未分類風險區間"

    reason_map = {
        "terrain_high": "局部地形起伏大",
        "terrain_moderate": "局部地形起伏中等",
        "hydrology_present": "鄰近水系或潮濕環境",
        "hydro_terrain_amplified": "水文與陡地形共同放大風險",
        "steps_present": "含階梯路段",
        "sett_surface": "鋪石路面可能於潮濕時較滑",
        "bridge_conditional": "含橋梁條件式通行因子",
        "slope_very_steep": "等高線窗判定非常陡",
        "slope_steep": "等高線窗判定陡峭",
    }

    reason_items = []
    for key in str(reason).split("|"):
        key = key.strip()
        if key in reason_map:
            reason_items.append(reason_map[key])

    if reason_items:
        reason_text = "、".join(reason_items[:4])
    else:
        reason_text = "綜合風險較低或風險來源混合"

    return f"{prefix} {start:.0f}–{end:.0f} m：{reason_text}。"


# =========================================================
# 3. 讀資料
# =========================================================
if not IN_SEGMENT_CSV.exists():
    raise FileNotFoundError(f"找不到輸入檔：{IN_SEGMENT_CSV.resolve()}")

seg_df = pd.read_csv(IN_SEGMENT_CSV, low_memory=False)

required = [
    "segment_id",
    "start_dist_m",
    "end_dist_m",
    "point_n",
    "mean_combined_risk",
    "p75_combined_risk",
    "max_combined_risk",
    "dominant_risk_band",
    "mean_osm_semantic_risk",
    "mean_terrain_risk",
    "mean_hydro_amplifier",
    "dominant_slope_band",
    "hydrology_present_ratio",
    "steps_ratio",
    "sett_surface_ratio",
    "bridge_ratio",
    "main_reason",
]

missing = [c for c in required if c not in seg_df.columns]
if missing:
    raise ValueError(f"缺少必要欄位：{missing}")

seg_df = seg_df.sort_values("segment_id").reset_index(drop=True)
seg_df["risk_group"] = seg_df["dominant_risk_band"].apply(risk_group)

print("case:", CASE_ID)
print("segments:", len(seg_df))
print("\n--- input risk group ---")
print(seg_df["risk_group"].value_counts(dropna=False))


# =========================================================
# 4. 合併連續 risk zones
# =========================================================
zone_rows = []

zone_id = 0
current_group = None
current_rows = []

for _, row in seg_df.iterrows():
    group = row["risk_group"]

    if current_group is None:
        current_group = group
        current_rows = [row]
        continue

    if group == current_group:
        current_rows.append(row)
    else:
        z = pd.DataFrame(current_rows)
        zone_rows.append((zone_id, current_group, z))
        zone_id += 1

        current_group = group
        current_rows = [row]

if current_rows:
    z = pd.DataFrame(current_rows)
    zone_rows.append((zone_id, current_group, z))


# =========================================================
# 5. zone 統計
# =========================================================
out_rows = []

for zid, group, z in zone_rows:
    point_n = int(z["point_n"].sum())
    length_m = float(z["end_dist_m"].max() - z["start_dist_m"].min())

    row = {
        "case_id": CASE_ID,
        "case_name": CASE_NAME,
        "model_version": MODEL_VERSION,
        "zone_id": int(zid),
        "zone_risk_group": group,

        "start_dist_m": round(float(z["start_dist_m"].min()), 2),
        "end_dist_m": round(float(z["end_dist_m"].max()), 2),
        "length_m": round(length_m, 2),
        "segment_n": int(len(z)),
        "point_n": point_n,

        "mean_combined_risk": round(weighted_mean(z["mean_combined_risk"], z["point_n"]), 6),
        "p75_combined_risk_mean": round(weighted_mean(z["p75_combined_risk"], z["point_n"]), 6),
        "max_combined_risk": round(float(z["max_combined_risk"].max()), 6),

        "mean_osm_semantic_risk": round(weighted_mean(z["mean_osm_semantic_risk"], z["point_n"]), 6),
        "mean_terrain_risk": round(weighted_mean(z["mean_terrain_risk"], z["point_n"]), 6),
        "mean_hydro_amplifier": round(weighted_mean(z["mean_hydro_amplifier"], z["point_n"]), 6),

        "dominant_slope_band": dominant_value(z["dominant_slope_band"]),
        "hydrology_present_ratio": round(weighted_mean(z["hydrology_present_ratio"], z["point_n"]), 6),
        "steps_ratio": round(weighted_mean(z["steps_ratio"], z["point_n"]), 6),
        "sett_surface_ratio": round(weighted_mean(z["sett_surface_ratio"], z["point_n"]), 6),
        "bridge_ratio": round(weighted_mean(z["bridge_ratio"], z["point_n"]), 6),

        "zone_main_reason": merge_reason_text(z["main_reason"]),
        "source_segment_ids": "|".join(z["segment_id"].astype(str).tolist()),
    }

    row["suggested_warning_text"] = make_warning_text(row)
    out_rows.append(row)

zone_df = pd.DataFrame(out_rows)

high_zone_df = zone_df[zone_df["zone_risk_group"].isin(HIGH_ZONE_BANDS)].copy()


# =========================================================
# 6. 輸出
# =========================================================
zone_df.to_csv(OUT_ZONE_CSV, index=False, encoding="utf-8-sig")
high_zone_df.to_csv(OUT_HIGH_ZONE_CSV, index=False, encoding="utf-8-sig")

summary_lines = [
    "Prototype A Risk Zone Summary",
    f"case_id: {CASE_ID}",
    f"case_name: {CASE_NAME}",
    f"model_version: {MODEL_VERSION}",
    "",
    f"input segment CSV: {IN_SEGMENT_CSV}",
    f"segments: {len(seg_df)}",
    f"zones: {len(zone_df)}",
    f"high zones: {len(high_zone_df)}",
    "",
    "zone_risk_group counts:",
    str(zone_df["zone_risk_group"].value_counts()),
    "",
    "high risk zones:",
]

if high_zone_df.empty:
    summary_lines.append("None")
else:
    for _, row in high_zone_df.iterrows():
        summary_lines.append(
            f"- zone {row['zone_id']}: "
            f"{row['start_dist_m']:.0f}-{row['end_dist_m']:.0f} m, "
            f"length={row['length_m']:.0f} m, "
            f"mean={row['mean_combined_risk']:.3f}, "
            f"max={row['max_combined_risk']:.3f}, "
            f"reason={row['zone_main_reason']}"
        )

summary_lines.extend([
    "",
    f"zone CSV: {OUT_ZONE_CSV}",
    f"high zone CSV: {OUT_HIGH_ZONE_CSV}",
])

OUT_SUMMARY_TXT.write_text("\n".join(summary_lines), encoding="utf-8")


print("\n完成！")
print("zone CSV:", OUT_ZONE_CSV.resolve())
print("high zone CSV:", OUT_HIGH_ZONE_CSV.resolve())
print("summary TXT:", OUT_SUMMARY_TXT.resolve())

print("\n--- zone risk group ---")
print(zone_df["zone_risk_group"].value_counts())

print("\n--- zones ---")
print(
    zone_df[
        [
            "zone_id",
            "zone_risk_group",
            "start_dist_m",
            "end_dist_m",
            "length_m",
            "mean_combined_risk",
            "max_combined_risk",
            "dominant_slope_band",
            "hydrology_present_ratio",
            "zone_main_reason",
            "suggested_warning_text",
        ]
    ]
)

print("\n--- high zones ---")
print(
    high_zone_df[
        [
            "zone_id",
            "start_dist_m",
            "end_dist_m",
            "length_m",
            "mean_combined_risk",
            "max_combined_risk",
            "dominant_slope_band",
            "hydrology_present_ratio",
            "suggested_warning_text",
        ]
    ]
)