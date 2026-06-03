from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


# =========================================================
# ib2b_v2_plot_route_segment_risk_profile.py
#
# 目的：
# - 讀取 ib2_v3 的 100m 區段風險結果
# - 輸出正式報告用風險剖面圖
# - 上圖：風險 / effort / exposure
# - 下圖：資料品質 mismatch / distance misaligned
# =========================================================


# =========================================================
# 0. 路徑設定
# =========================================================
INPUT_CSV = Path("ib2_v3_route_segment_risk_output/qixing_route_segment_risk_100m.csv")

OUT_DIR = Path("ib2b_v2_segment_risk_profile_output")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_PNG = OUT_DIR / "qixing_route_segment_risk_profile_report.png"
OUT_CSV = OUT_DIR / "qixing_route_segment_risk_profile_report_data.csv"


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

if "segment_valid" not in df.columns:
    df["segment_valid"] = True

if "valid_route_end_m" not in df.columns:
    df["valid_route_end_m"] = df["segment_end_m"].max()

if "risk_confidence_dominant" not in df.columns:
    df["risk_confidence_dominant"] = "unknown"

if "data_quality_reason_merged" not in df.columns:
    df["data_quality_reason_merged"] = "normal"

if "low_confidence_ratio" not in df.columns:
    df["low_confidence_ratio"] = 0.0

if "route_data_bad_ratio" not in df.columns:
    df["route_data_bad_ratio"] = 0.0

# 只畫有效 segment，避免無效尾段進入正式報告圖
df_all = df.copy()
df = df[df["segment_valid"].astype(bool)].copy()

if df.empty:
    raise ValueError("segment_valid 過濾後沒有可繪製資料，請檢查 ib2_v3 輸出")

# 有效路線終點，用於圖上標示與摘要輸出
valid_route_end_m = float(df["valid_route_end_m"].dropna().iloc[0])


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
# 4. 連續區段偵測
# =========================================================
def find_band_runs(dataframe, band_value):
    runs = []
    start_idx = None

    for i, value in enumerate(dataframe["segment_risk_band"].astype(str)):
        if value == band_value and start_idx is None:
            start_idx = i

        if value != band_value and start_idx is not None:
            runs.append((start_idx, i - 1))
            start_idx = None

    if start_idx is not None:
        runs.append((start_idx, len(dataframe) - 1))

    return runs


very_high_runs = find_band_runs(df, "very_high")


# =========================================================
# 5. 畫圖
# =========================================================
fig, (ax1, ax2) = plt.subplots(
    nrows=2,
    ncols=1,
    figsize=(15, 8),
    sharex=True,
    gridspec_kw={"height_ratios": [3, 1.15]},
)

bar_width = (
    df["segment_end_m"] - df["segment_start_m"]
).median() * 0.86


# ---------------------------------------------------------
# 5a. 上圖：區段風險
# ---------------------------------------------------------
ax1.bar(
    df["segment_mid_m"],
    df["segment_risk_score"],
    width=bar_width,
    color=bar_colors,
    alpha=0.55,
    label="segment_risk_score (max)",
)

ax1.plot(
    df["segment_mid_m"],
    df["segment_risk_score_mean"],
    linewidth=2.2,
    color="black",
    label="segment_risk_score_mean",
)

ax1.plot(
    df["segment_mid_m"],
    df["effort_score_mean"],
    linewidth=1.7,
    linestyle="--",
    label="effort_score_mean",
)

ax1.plot(
    df["segment_mid_m"],
    df["exposure_score_mean"],
    linewidth=1.7,
    linestyle=":",
    label="exposure_score_mean",
)

ax1.set_ylabel("Risk / Component Score")
ax1.grid(True, alpha=0.25)


# ---------------------------------------------------------
# 5b. very_high 連續區段標註
# ---------------------------------------------------------
y_max = max(
    df["segment_risk_score"].max(),
    df["segment_risk_score_mean"].max(),
)

for start_i, end_i in very_high_runs:
    start_m = df.iloc[start_i]["segment_start_m"]
    end_m = df.iloc[end_i]["segment_end_m"]
    mid_m = (start_m + end_m) / 2

    ax1.axvspan(
        start_m,
        end_m,
        color="#d7301f",
        alpha=0.08,
    )

    ax1.text(
        mid_m,
        y_max + 0.35,
        f"{int(start_m)}–{int(end_m)} m\nvery_high zone",
        ha="center",
        va="bottom",
        fontsize=8,
        color="#7f0000",
    )

ax1.set_ylim(0, y_max + 1.3)

# 有效路線終點標示
ax1.axvline(
    valid_route_end_m,
    color="gray",
    linestyle="--",
    linewidth=1.2,
    alpha=0.8,
    label=f"valid route end = {valid_route_end_m:.0f} m",
)




# ---------------------------------------------------------
# 5c. 下圖：資料品質
# ---------------------------------------------------------
ax2.plot(
    df["segment_mid_m"],
    df["gpx_mismatch_ratio"],
    linewidth=1.6,
    marker="x",
    label="gpx_mismatch_ratio",
)

ax2.plot(
    df["segment_mid_m"],
    df["dist_misaligned_ratio"],
    linewidth=1.6,
    marker="o",
    fillstyle="none",
    label="dist_misaligned_ratio",
)

ax2.plot(
    df["segment_mid_m"],
    df["low_confidence_ratio"],
    linewidth=1.6,
    marker="s",
    fillstyle="none",
    label="low_confidence_ratio",
)

ax2.plot(
    df["segment_mid_m"],
    df["route_data_bad_ratio"],
    linewidth=1.6,
    marker="^",
    fillstyle="none",
    label="route_data_bad_ratio",
)

ax2.fill_between(
    df["segment_mid_m"],
    0,
    df["gpx_mismatch_ratio"],
    alpha=0.12,
)

ax2.fill_between(
    df["segment_mid_m"],
    0,
    df["dist_misaligned_ratio"],
    alpha=0.12,
)

ax2.fill_between(
    df["segment_mid_m"],
    0,
    df["low_confidence_ratio"],
    alpha=0.08,
)

ax2.fill_between(
    df["segment_mid_m"],
    0,
    df["route_data_bad_ratio"],
    alpha=0.08,
)

ax2.set_ylabel("Quality Issue Ratio")
ax2.set_xlabel("Distance (m)")
ax2.set_ylim(-0.05, 1.05)
ax2.grid(True, alpha=0.25)

ax2.axvline(
    valid_route_end_m,
    color="gray",
    linestyle="--",
    linewidth=1.2,
    alpha=0.8,
)

# ---------------------------------------------------------
# 5d. 圖例與標題
# ---------------------------------------------------------
ax1.legend(loc="upper center", fontsize=8)
ax2.legend(loc="upper center", fontsize=8)

plt.suptitle(
    "Route Segment Risk Profile (100m)\n"
    "Risk Components and Data Quality",
    fontsize=14,
)

plt.tight_layout(rect=[0, 0, 1, 0.95])
plt.savefig(OUT_PNG, dpi=220)
plt.close()


# =========================================================
# 6. 輸出 plot data
# =========================================================
plot_cols = [
    "risk_segment_id",
    "segment_start_m",
    "segment_end_m",
    "segment_mid_m",
    "segment_valid",
    "valid_route_end_m",
    "segment_risk_score",
    "segment_risk_score_mean",
    "segment_risk_band",
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

plot_cols = [c for c in plot_cols if c in df.columns]
df[plot_cols].to_csv(OUT_CSV, index=False, encoding="utf-8-sig")


# =========================================================
# 7. 摘要
# =========================================================
print("完成！")
print("PNG:", OUT_PNG.resolve())
print("plot CSV:", OUT_CSV.resolve())

print("\n=== segment_risk_band ===")
print(df["segment_risk_band"].value_counts(dropna=False))

print("\n=== very_high runs ===")
if very_high_runs:
    for start_i, end_i in very_high_runs:
        print(
            f'{int(df.iloc[start_i]["segment_start_m"])}–'
            f'{int(df.iloc[end_i]["segment_end_m"])} m'
        )
else:
    print("none")

print("\n=== top risky segments ===")
show_cols = [
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

print("\n=== risk_confidence_dominant ===")
print(df["risk_confidence_dominant"].value_counts(dropna=False))

print("\n=== route range ===")
print(f'segment_start_min: {df["segment_start_m"].min():.1f}')
print(f'segment_end_max: {df["segment_end_m"].max():.1f}')
print(f'valid_route_end_m: {valid_route_end_m:.1f}')

show_cols = [c for c in show_cols if c in df.columns]

print(
    df.sort_values("segment_risk_score", ascending=False)[show_cols]
    .head(15)
    .to_string(index=False)
)