from pathlib import Path
import pandas as pd
import numpy as np


# =========================================================
# ib2_v3_route_segment_risk.py
#
# 目的：
# - 將 ib2_v2 產出的點級風險 profile 聚合成 100m 區段級風險
# - 讓後續圖表、HTML map、簡報比較容易解讀
#
# 輸入：
# - ib2_v2_route_risk_output/qixing_route_risk_v2.csv
#
# 輸出：
# - ib2_v3_route_segment_risk_output/qixing_route_segment_risk_100m.csv
# =========================================================


# =========================================================
# 0. 路徑設定
# =========================================================
INPUT_CSV = Path("ib2_v2_route_risk_output/qixing_route_risk_v2.csv")

OUT_DIR = Path("ib2_v3_route_segment_risk_output")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_CSV = OUT_DIR / "qixing_route_segment_risk_100m.csv"


# =========================================================
# 1. 參數
# =========================================================
SEGMENT_SIZE_M = 100.0

# 是否排除超出有效路線資料範圍的尾段點
# True：正式報告建議使用，會避免 3400m 之後無效尾段被聚合進結果
# False：保留所有點，但仍會標示 segment_valid / risk_confidence
DROP_LOW_CONFIDENCE_TAIL = True


# =========================================================
# 2. 工具函式
# =========================================================
def dominant_value(series):
    """回傳眾數；若空值則回傳 unknown。"""
    s = series.dropna().astype(str)
    if s.empty:
        return "unknown"
    return s.value_counts().idxmax()


def join_unique_flags(series):
    """把 risk_reason / flags 合併成去重後的 | 字串。"""
    items = []

    for v in series.dropna().astype(str):
        if v in ["", "none", "normal", "nan"]:
            continue
        for part in v.split("|"):
            part = part.strip()
            if part and part not in items:
                items.append(part)

    return "|".join(items) if items else "normal"


def risk_band_from_score(score):
    if pd.isna(score):
        return "unknown"
    if score < 1.5:
        return "low"
    elif score < 3.5:
        return "moderate"
    elif score < 6.0:
        return "high"
    else:
        return "very_high"


# =========================================================
# 3. 讀取資料
# =========================================================
if not INPUT_CSV.exists():
    raise FileNotFoundError(f"找不到輸入檔：{INPUT_CSV.resolve()}，請先執行 ib2_v2")

df = pd.read_csv(INPUT_CSV)

if df.empty:
    raise ValueError("輸入 CSV 為空")

if "dist_m" not in df.columns:
    raise ValueError("缺少 dist_m 欄位")

if "risk_score" not in df.columns:
    raise ValueError("缺少 risk_score 欄位")

df = df.sort_values("dist_m").reset_index(drop=True)

# =========================================================
# 3a. 有效路線距離範圍判斷
# =========================================================
# 優先使用 ib2_v2 v0.3 輸出的 route_data_ok 判斷有效距離。
# route_data_ok = within_validation_range & alignment_ok
#
# 若沒有 route_data_ok，則退回使用 alignment_ok。
# 若兩者都沒有，則保留全部資料。

if "route_data_ok" in df.columns:
    valid_mask = df["route_data_ok"].astype(bool)
elif "alignment_ok" in df.columns:
    valid_mask = df["alignment_ok"].astype(bool)
else:
    valid_mask = pd.Series(True, index=df.index)

if valid_mask.any():
    VALID_ROUTE_START_M = df.loc[valid_mask, "dist_m"].min()
    VALID_ROUTE_END_M = df.loc[valid_mask, "dist_m"].max()
else:
    VALID_ROUTE_START_M = df["dist_m"].min()
    VALID_ROUTE_END_M = df["dist_m"].max()

df["within_valid_route"] = (
    (df["dist_m"] >= VALID_ROUTE_START_M) &
    (df["dist_m"] <= VALID_ROUTE_END_M)
)

# 正式報告用：排除超出有效 route / validation 範圍的尾段點
if DROP_LOW_CONFIDENCE_TAIL:
    before_n = len(df)
    df = df[df["within_valid_route"]].copy()
    after_n = len(df)
    print(f"valid-route filter: {before_n} -> {after_n} points")

    if df.empty:
        raise ValueError(
            "valid-route filter 後資料為空，請檢查 route_data_ok / alignment_ok / validation range"
        )

print(f"VALID_ROUTE_START_M: {VALID_ROUTE_START_M:.2f}")
print(f"VALID_ROUTE_END_M: {VALID_ROUTE_END_M:.2f}")


# =========================================================
# 4. 建立 100m 區段 ID
# =========================================================
df["risk_segment_id"] = (df["dist_m"] // SEGMENT_SIZE_M).astype(int)
df["segment_start_m"] = df["risk_segment_id"] * SEGMENT_SIZE_M

# 尾段不可超過有效路線終點
df["segment_end_m"] = np.minimum(
    df["segment_start_m"] + SEGMENT_SIZE_M,
    VALID_ROUTE_END_M,
)

df["segment_valid"] = df["segment_start_m"] < VALID_ROUTE_END_M


# =========================================================
# 5. 聚合欄位
# =========================================================
agg_dict = {
    "dist_m": ["min", "max", "count"],
    "risk_score": ["mean", "max", "median"],
}

optional_mean_cols = [
    "risk_score_smooth",
    "terrain_score",
    "effort_score",
    "exposure_score",
    "terrain_density_score",
    "terrain_quality_penalty",
    "effort_slope",
    "terrain_exposure_slope",
    "slope_final",
    "ele_gpx_m",
]

for c in optional_mean_cols:
    if c in df.columns:
        agg_dict[c] = ["mean", "max"]

grouped = df.groupby("risk_segment_id").agg(agg_dict)

# flatten columns
grouped.columns = [
    "_".join([x for x in col if x]).strip("_")
    for col in grouped.columns.to_flat_index()
]

grouped = grouped.reset_index()


# =========================================================
# 6. 補區段基本欄位
# =========================================================
grouped["segment_start_m"] = grouped["risk_segment_id"] * SEGMENT_SIZE_M

# 聚合後再次截斷，避免最後一段超出有效 route end
grouped["segment_end_m"] = np.minimum(
    grouped["segment_start_m"] + SEGMENT_SIZE_M,
    VALID_ROUTE_END_M,
)

grouped["segment_mid_m"] = (
    grouped["segment_start_m"] + grouped["segment_end_m"]
) / 2

grouped["points_n"] = grouped["dist_m_count"]

grouped["segment_valid"] = grouped["segment_start_m"] < VALID_ROUTE_END_M
grouped["valid_route_start_m"] = VALID_ROUTE_START_M
grouped["valid_route_end_m"] = VALID_ROUTE_END_M


# =========================================================
# 7. 區段風險等級
# =========================================================
# 以 max 作為區段風險，避免危險點被平均稀釋
grouped["segment_risk_score"] = grouped["risk_score_max"]
grouped["segment_risk_band"] = grouped["segment_risk_score"].apply(risk_band_from_score)

# 也保留平均風險，方便比較
grouped["segment_risk_score_mean"] = grouped["risk_score_mean"]


# =========================================================
# 8. 類別欄位聚合
# =========================================================
category_cols = [
    "risk_band",
    "effort_slope_band",
    "terrain_exposure_band",
    "slope_final_band",
    "gpx_quality_flag",
    "risk_confidence",
]

for c in category_cols:
    if c in df.columns:
        tmp = df.groupby("risk_segment_id")[c].apply(dominant_value).reset_index()
        tmp = tmp.rename(columns={c: f"{c}_dominant"})
        grouped = grouped.merge(tmp, on="risk_segment_id", how="left")


flag_cols = [
    "risk_reason",
    "data_quality_reason",
    "technical_flags",
    "hazard_flags",
    "hydrology_flags",
    "facility_flags",
    "rest_flags",
    "support_flags",
    "landmark_flags",
]

for c in flag_cols:
    if c in df.columns:
        tmp = df.groupby("risk_segment_id")[c].apply(join_unique_flags).reset_index()
        tmp = tmp.rename(columns={c: f"{c}_merged"})
        grouped = grouped.merge(tmp, on="risk_segment_id", how="left")


# =========================================================
# 9. mismatch / alignment 統計
# =========================================================
if "gpx_quality_flag" in df.columns:
    mismatch_ratio = (
        df.assign(is_mismatch=df["gpx_quality_flag"].eq("mismatch").astype(float))
        .groupby("risk_segment_id")["is_mismatch"]
        .mean()
        .reset_index()
        .rename(columns={"is_mismatch": "gpx_mismatch_ratio"})
    )
    grouped = grouped.merge(mismatch_ratio, on="risk_segment_id", how="left")

if "alignment_ok" in df.columns:
    bad_align_ratio = (
        df.assign(is_bad_align=(~df["alignment_ok"].astype(bool)).astype(float))
        .groupby("risk_segment_id")["is_bad_align"]
        .mean()
        .reset_index()
        .rename(columns={"is_bad_align": "dist_misaligned_ratio"})
    )
    grouped = grouped.merge(bad_align_ratio, on="risk_segment_id", how="left")


if "risk_confidence" in df.columns:
    low_confidence_ratio = (
        df.assign(
            is_low_confidence=df["risk_confidence"]
            .astype(str)
            .str.startswith("low")
            .astype(float)
        )
        .groupby("risk_segment_id")["is_low_confidence"]
        .mean()
        .reset_index()
        .rename(columns={"is_low_confidence": "low_confidence_ratio"})
    )
    grouped = grouped.merge(low_confidence_ratio, on="risk_segment_id", how="left")

if "route_data_ok" in df.columns:
    route_data_bad_ratio = (
        df.assign(is_route_data_bad=(~df["route_data_ok"].astype(bool)).astype(float))
        .groupby("risk_segment_id")["is_route_data_bad"]
        .mean()
        .reset_index()
        .rename(columns={"is_route_data_bad": "route_data_bad_ratio"})
    )
    grouped = grouped.merge(route_data_bad_ratio, on="risk_segment_id", how="left")

# =========================================================
# 10. 排序與輸出
# =========================================================
grouped = grouped.sort_values("segment_start_m").reset_index(drop=True)

# 欄位容錯，避免後續 plot script 讀到 NaN
for c in [
    "gpx_mismatch_ratio",
    "dist_misaligned_ratio",
    "low_confidence_ratio",
    "route_data_bad_ratio",
]:
    if c in grouped.columns:
        grouped[c] = grouped[c].fillna(0.0)

if "risk_confidence_dominant" not in grouped.columns:
    grouped["risk_confidence_dominant"] = "unknown"

if "data_quality_reason_merged" not in grouped.columns:
    grouped["data_quality_reason_merged"] = "normal"

grouped.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")


# =========================================================
# 11. 摘要
# =========================================================
print("完成！")
print("CSV:", OUT_CSV.resolve())

print("\n=== segment_risk_band ===")
print(grouped["segment_risk_band"].value_counts(dropna=False))

print("\n=== top risky segments ===")
show_cols = [
    "risk_segment_id",
    "segment_start_m",
    "segment_end_m",
    "segment_valid",
    "segment_risk_score",
    "segment_risk_band",
    "segment_risk_score_mean",
    "effort_score_mean",
    "exposure_score_mean",
    "gpx_mismatch_ratio",
    "dist_misaligned_ratio",
    "low_confidence_ratio",
    "route_data_bad_ratio",
    "risk_confidence_dominant",
    "risk_reason_merged",
    "data_quality_reason_merged",
]
show_cols = [c for c in show_cols if c in grouped.columns]

print(
    grouped.sort_values("segment_risk_score", ascending=False)[show_cols]
    .head(15)
    .to_string(index=False)
)