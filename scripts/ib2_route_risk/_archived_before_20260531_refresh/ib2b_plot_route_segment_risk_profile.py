from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


# =========================================================
# ib2b_plot_route_segment_risk_profile.py
#
# 目的：
# - 將 ib2_v3_route_segment_risk.py 產出的 100m 區段風險
#   畫成乾淨的區段級風險剖面圖
#
# 輸入：
# - ib2_v3_route_segment_risk_output/qixing_route_segment_risk_100m.csv
#
# 輸出：
# - ib2b_segment_risk_profile_output/qixing_route_segment_risk_profile.png
# =========================================================


# =========================================================
# 0. 路徑設定
# =========================================================
INPUT_CSV = Path("ib2_v3_route_segment_risk_output/qixing_route_segment_risk_100m.csv")

OUT_DIR = Path("ib2b_segment_risk_profile_output")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_PNG = OUT_DIR / "qixing_route_segment_risk_profile.png"
OUT_CSV = OUT_DIR / "qixing_route_segment_risk_profile_plot_data.csv"


# =========================================================
# 1. 讀資料
# =========================================================
if not INPUT_CSV.exists():
    raise FileNotFoundError(f"找不到輸入檔：{INPUT_CSV.resolve()}，請先執行 ib2_v3")

df = pd.read_csv(INPUT_CSV)

if df.empty:
    raise ValueError("輸入 CSV 為空")

required_cols = [
    "segment_start_m",
    "segment_end_m",
    "segment_mid_m",
    "segment_risk_score",
    "segment_risk_band",
]

for c in required_cols:
    if c not in df.columns:
        raise ValueError(f"缺少欄位：{c}")

df = df.sort_values("segment_start_m").reset_index(drop=True)


# =========================================================
# 2. 欄位容錯
# =========================================================
if "segment_risk_score_mean" not in df.columns:
    df["segment_risk_score_mean"] = df["segment_risk_score"]

if "effort_score_mean" not in df.columns:
    df["effort_score_mean"] = 0.0

if "exposure_score_mean" not in df.columns:
    df["exposure_score_mean"] = 0.0

if "gpx_mismatch_ratio" not in df.columns:
    df["gpx_mismatch_ratio"] = 0.0

if "dist_misaligned_ratio" not in df.columns:
    df["dist_misaligned_ratio"] = 0.0

if "risk_reason_merged" not in df.columns:
    df["risk_reason_merged"] = "normal"


# =========================================================
# 3. 顏色設定
# =========================================================
RISK_COLOR = {
    "low": "#2ca25f",
    "moderate": "#fec44f",
    "high": "#fc8d59",
    "very_high": "#d7301f",
    "unknown": "#bdbdbd",
}

bar_colors = [
    RISK_COLOR.get(str(v), "#bdbdbd")
    for v in df["segment_risk_band"]
]


# =========================================================
# 4. 畫圖
# =========================================================
fig, ax1 = plt.subplots(figsize=(15, 6))

bar_width = (
    df["segment_end_m"] - df["segment_start_m"]
).median() * 0.86

# ---------------------------------------------------------
# 4a. 區段最大風險柱狀圖
# ---------------------------------------------------------
ax1.bar(
    df["segment_mid_m"],
    df["segment_risk_score"],
    width=bar_width,
    color=bar_colors,
    alpha=0.55,
    label="segment_risk_score (max)",
)

# ---------------------------------------------------------
# 4b. 區段平均風險
# ---------------------------------------------------------
ax1.plot(
    df["segment_mid_m"],
    df["segment_risk_score_mean"],
    linewidth=2.0,
    color="black",
    label="segment_risk_score_mean",
)

# ---------------------------------------------------------
# 4c. effort / exposure mean
# ---------------------------------------------------------
ax1.plot(
    df["segment_mid_m"],
    df["effort_score_mean"],
    linewidth=1.6,
    linestyle="--",
    label="effort_score_mean",
)

ax1.plot(
    df["segment_mid_m"],
    df["exposure_score_mean"],
    linewidth=1.6,
    linestyle=":",
    label="exposure_score_mean",
)

# ---------------------------------------------------------
# 4d. mismatch / misaligned ratio 第二軸
# ---------------------------------------------------------
ax2 = ax1.twinx()

ax2.plot(
    df["segment_mid_m"],
    df["gpx_mismatch_ratio"],
    linewidth=1.2,
    marker="x",
    label="gpx_mismatch_ratio",
)

ax2.plot(
    df["segment_mid_m"],
    df["dist_misaligned_ratio"],
    linewidth=1.2,
    marker="o",
    fillstyle="none",
    label="dist_misaligned_ratio",
)

ax2.set_ylabel("Quality Issue Ratio")
ax2.set_ylim(-0.05, 1.05)


# ---------------------------------------------------------
# 4e. 標註 very_high 區段
# ---------------------------------------------------------
for _, row in df[df["segment_risk_band"] == "very_high"].iterrows():
    ax1.text(
        row["segment_mid_m"],
        row["segment_risk_score"] + 0.15,
        f'{int(row["segment_start_m"])}-{int(row["segment_end_m"])}m',
        ha="center",
        va="bottom",
        fontsize=7,
        rotation=45,
    )


# ---------------------------------------------------------
# 4f. 圖面設定
# ---------------------------------------------------------
ax1.set_xlabel("Distance (m)")
ax1.set_ylabel("Risk / Component Score")
ax1.grid(True, alpha=0.25)

plt.title(
    "Route Segment Risk Profile (100m)\n"
    "Segment Risk vs Effort / Terrain Exposure / Data Quality"
)

# legends
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()

ax1.legend(
    lines1 + lines2,
    labels1 + labels2,
    loc="upper right",
    fontsize=8,
)

plt.tight_layout()
plt.savefig(OUT_PNG, dpi=220)
plt.close()


# =========================================================
# 5. 輸出 plot data
# =========================================================
plot_cols = [
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

plot_cols = [c for c in plot_cols if c in df.columns]

df[plot_cols].to_csv(OUT_CSV, index=False, encoding="utf-8-sig")


# =========================================================
# 6. 摘要
# =========================================================
print("完成！")
print("PNG:", OUT_PNG.resolve())
print("plot CSV:", OUT_CSV.resolve())

print("\n=== segment_risk_band ===")
print(df["segment_risk_band"].value_counts(dropna=False))

print("\n=== top risky segments ===")
show_cols = [
    "segment_start_m",
    "segment_end_m",
    "segment_risk_score",
    "segment_risk_band",
    "segment_risk_score_mean",
    "effort_score_mean",
    "exposure_score_mean",
    "gpx_mismatch_ratio",
    "dist_misaligned_ratio",
    "risk_reason_merged",
]

show_cols = [c for c in show_cols if c in df.columns]

print(
    df.sort_values("segment_risk_score", ascending=False)[show_cols]
    .head(15)
    .to_string(index=False)
)