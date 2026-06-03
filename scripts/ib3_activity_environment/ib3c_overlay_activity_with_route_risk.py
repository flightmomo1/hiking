from pathlib import Path

import pandas as pd
import numpy as np


"""
ib3c_overlay_activity_with_route_risk.py

定位：
- 將 ib3a mapmatched activity 與 ib2_v3 100m route segment risk 疊合
- 把每個活動時間點標註為所在風險區段
- 用於後續：
  1. 高風險區通過時間
  2. 高風險區停留
  3. ETA / risk timeline
  4. 活動歷程風險摘要

輸入：
- ib3a_mapmatched_activity_output/qixing_activity_mapmatched.csv
- ib2_v3_route_segment_risk_output/qixing_route_segment_risk_100m.csv

輸出：
- ib3c_activity_risk_overlay_output/qixing_activity_risk_overlay.csv
"""


# =========================================================
# 0. 路徑設定
# =========================================================
ACTIVITY_CSV = Path("ib3a_mapmatched_activity_output/qixing_activity_mapmatched.csv")
SEGMENT_RISK_CSV = Path("ib2_v3_route_segment_risk_output/qixing_route_segment_risk_100m.csv")

OUT_DIR = Path("ib3c_activity_risk_overlay_output")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_CSV = OUT_DIR / "qixing_activity_risk_overlay.csv"
OUT_SUMMARY_CSV = OUT_DIR / "qixing_activity_risk_overlay_summary.csv"


# =========================================================
# 1. 讀資料
# =========================================================
if not ACTIVITY_CSV.exists():
    raise FileNotFoundError(f"找不到活動檔：{ACTIVITY_CSV.resolve()}，請先執行 ib3a")

if not SEGMENT_RISK_CSV.exists():
    raise FileNotFoundError(f"找不到風險區段檔：{SEGMENT_RISK_CSV.resolve()}，請先執行 ib2_v3")

activity = pd.read_csv(ACTIVITY_CSV)
risk_seg = pd.read_csv(SEGMENT_RISK_CSV)

if activity.empty:
    raise ValueError("activity CSV 為空")

if risk_seg.empty:
    raise ValueError("segment risk CSV 為空")


# =========================================================
# 2. 欄位檢查
# =========================================================
required_activity_cols = [
    "route_dist_m",
    "forward_speed_route_mps",
    "is_stationary",
]

for c in required_activity_cols:
    if c not in activity.columns:
        raise ValueError(f"activity 缺少欄位：{c}")

required_risk_cols = [
    "segment_start_m",
    "segment_end_m",
    "segment_risk_score",
    "segment_risk_band",
]

for c in required_risk_cols:
    if c not in risk_seg.columns:
        raise ValueError(f"risk segment 缺少欄位：{c}")


# =========================================================
# 3. 欄位容錯
# =========================================================
if "time" in activity.columns:
    activity["time"] = pd.to_datetime(activity["time"], errors="coerce", utc=True)
else:
    activity["time"] = pd.NaT

if "activity_idx" not in activity.columns:
    activity["activity_idx"] = range(len(activity))

if "match_quality" not in activity.columns:
    activity["match_quality"] = "unknown"

if "offset_to_mainline_m" not in activity.columns:
    activity["offset_to_mainline_m"] = np.nan

if "raw_ele_m" not in activity.columns:
    activity["raw_ele_m"] = np.nan

if "effort_score_mean" not in risk_seg.columns:
    risk_seg["effort_score_mean"] = np.nan

if "exposure_score_mean" not in risk_seg.columns:
    risk_seg["exposure_score_mean"] = np.nan

if "gpx_mismatch_ratio" not in risk_seg.columns:
    risk_seg["gpx_mismatch_ratio"] = np.nan

if "dist_misaligned_ratio" not in risk_seg.columns:
    risk_seg["dist_misaligned_ratio"] = np.nan

if "risk_reason_merged" not in risk_seg.columns:
    risk_seg["risk_reason_merged"] = "normal"


# =========================================================
# 4. 建立活動點所屬 100m segment
# =========================================================
# 依 risk_seg 實際 segment size 推估，通常是 100m
segment_size_m = (
    risk_seg["segment_end_m"].iloc[0] - risk_seg["segment_start_m"].iloc[0]
)

activity["risk_segment_id"] = (
    activity["route_dist_m"] // segment_size_m
).astype(int)

if "risk_segment_id" not in risk_seg.columns:
    risk_seg["risk_segment_id"] = (
        risk_seg["segment_start_m"] // segment_size_m
    ).astype(int)


# =========================================================
# 5. 疊合 activity + risk segment
# =========================================================
risk_keep_cols = [
    "risk_segment_id",
    "segment_start_m",
    "segment_end_m",
    "segment_mid_m",
    "segment_risk_score",
    "segment_risk_score_mean",
    "segment_risk_band",
    "effort_score_mean",
    "exposure_score_mean",
    "gpx_mismatch_ratio",
    "dist_misaligned_ratio",
    "risk_reason_merged",
]

risk_keep_cols = [c for c in risk_keep_cols if c in risk_seg.columns]

df = activity.merge(
    risk_seg[risk_keep_cols],
    on="risk_segment_id",
    how="left",
)


# =========================================================
# 6. 高風險標記
# =========================================================
df["is_in_high_risk_segment"] = df["segment_risk_band"].isin(["high", "very_high"])
df["is_in_very_high_risk_segment"] = df["segment_risk_band"].eq("very_high")

# is_stationary 可能是字串，要轉 bool
if df["is_stationary"].dtype == object:
    df["is_stationary_bool"] = df["is_stationary"].astype(str).str.lower().isin(["true", "1", "yes"])
else:
    df["is_stationary_bool"] = df["is_stationary"].astype(bool)

df["is_stationary_in_high_risk"] = (
    df["is_stationary_bool"] & df["is_in_high_risk_segment"]
)

df["is_stationary_in_very_high_risk"] = (
    df["is_stationary_bool"] & df["is_in_very_high_risk_segment"]
)


# =========================================================
# 7. 時間統計
# =========================================================
df = df.sort_values("activity_idx").reset_index(drop=True)

if "delta_time_s" in df.columns:
    df["duration_s"] = df["delta_time_s"]
else:
    df["duration_s"] = df["time"].diff().dt.total_seconds()

# 第一筆 duration 沒有上一筆，設 0
df["duration_s"] = df["duration_s"].fillna(0)

# 避免異常大 gap 直接灌進統計，暫時 cap 在 10 秒
df["duration_s_capped"] = df["duration_s"].clip(lower=0, upper=10)


# =========================================================
# 8. 摘要統計
# =========================================================
total_duration_s = df["duration_s_capped"].sum()
high_duration_s = df.loc[df["is_in_high_risk_segment"], "duration_s_capped"].sum()
very_high_duration_s = df.loc[df["is_in_very_high_risk_segment"], "duration_s_capped"].sum()
stationary_high_s = df.loc[df["is_stationary_in_high_risk"], "duration_s_capped"].sum()
stationary_very_high_s = df.loc[df["is_stationary_in_very_high_risk"], "duration_s_capped"].sum()

summary = pd.DataFrame([
    {
        "total_duration_s": total_duration_s,
        "high_duration_s": high_duration_s,
        "very_high_duration_s": very_high_duration_s,
        "stationary_high_s": stationary_high_s,
        "stationary_very_high_s": stationary_very_high_s,
        "high_duration_ratio": high_duration_s / total_duration_s if total_duration_s > 0 else np.nan,
        "very_high_duration_ratio": very_high_duration_s / total_duration_s if total_duration_s > 0 else np.nan,
        "stationary_high_ratio": stationary_high_s / total_duration_s if total_duration_s > 0 else np.nan,
        "stationary_very_high_ratio": stationary_very_high_s / total_duration_s if total_duration_s > 0 else np.nan,
        "activity_points_n": len(df),
        "segment_size_m": segment_size_m,
    }
])


# =========================================================
# 9. 輸出
# =========================================================
df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
summary.to_csv(OUT_SUMMARY_CSV, index=False, encoding="utf-8-sig")


# =========================================================
# 10. 摘要
# =========================================================
print("完成！")
print("activity risk overlay CSV:", OUT_CSV.resolve())
print("summary CSV:", OUT_SUMMARY_CSV.resolve())

print("\n=== segment_risk_band on activity points ===")
print(df["segment_risk_band"].value_counts(dropna=False))

print("\n=== duration summary ===")
print(summary.to_string(index=False))

print("\n=== stationary in risk ===")
print("stationary_high_s:", round(stationary_high_s, 1))
print("stationary_very_high_s:", round(stationary_very_high_s, 1))

print("\n=== top activity risk rows ===")
show_cols = [
    "activity_idx",
    "time",
    "route_dist_m",
    "raw_ele_m",
    "forward_speed_route_mps",
    "is_stationary_bool",
    "segment_start_m",
    "segment_end_m",
    "segment_risk_score",
    "segment_risk_band",
    "effort_score_mean",
    "exposure_score_mean",
    "gpx_mismatch_ratio",
    "dist_misaligned_ratio",
    "risk_reason_merged",
]

show_cols = [c for c in show_cols if c in df.columns]

print(
    df.sort_values("segment_risk_score", ascending=False)[show_cols]
    .head(20)
    .to_string(index=False)
)