from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


"""
ib3d_v2_plot_activity_risk_timeline_report.py

定位：
- ib3d_plot_activity_risk_timeline.py 的正式報告版
- 僅突出 high / very_high 風險背景
- 淡化一般 stationary，只強調 high / very_high 區段中的低速/停留
- 用於展示：
  1. 使用者何時進入高風險區段
  2. 高風險區段通過時間
  3. very_high 區段位置與活動行為
  4. 高風險區低速/停留點
"""


# =========================================================
# 0. 路徑設定
# =========================================================
INPUT_CSV = Path("ib3c_activity_risk_overlay_output/qixing_activity_risk_overlay.csv")

OUT_DIR = Path("ib3d_v2_activity_risk_timeline_report_output")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_PNG = OUT_DIR / "qixing_activity_risk_timeline_report.png"
OUT_CSV = OUT_DIR / "qixing_activity_risk_timeline_report_plot_data.csv"


# =========================================================
# 1. 讀資料
# =========================================================
if not INPUT_CSV.exists():
    raise FileNotFoundError(f"找不到輸入檔：{INPUT_CSV.resolve()}，請先執行 ib3c")

df = pd.read_csv(INPUT_CSV)

if df.empty:
    raise ValueError("輸入 CSV 為空")

required_cols = [
    "activity_idx",
    "route_dist_m",
    "forward_speed_route_mps",
    "segment_risk_band",
    "segment_risk_score",
]

for c in required_cols:
    if c not in df.columns:
        raise ValueError(f"缺少欄位：{c}")

df = df.sort_values("activity_idx").reset_index(drop=True)


# =========================================================
# 2. 時間欄位
# =========================================================
if "time" in df.columns:
    df["time"] = pd.to_datetime(df["time"], errors="coerce", utc=True)
else:
    df["time"] = pd.NaT

if df["time"].notna().any():
    t0 = df["time"].dropna().iloc[0]
    df["elapsed_s"] = (df["time"] - t0).dt.total_seconds()
else:
    df["elapsed_s"] = df["activity_idx"].astype(float)

df["elapsed_min"] = df["elapsed_s"] / 60.0


# =========================================================
# 3. 欄位容錯
# =========================================================
if "raw_ele_m" not in df.columns:
    df["raw_ele_m"] = pd.NA

if "is_stationary_bool" not in df.columns:
    if "is_stationary" in df.columns:
        df["is_stationary_bool"] = (
            df["is_stationary"].astype(str).str.lower().isin(["true", "1", "yes"])
        )
    else:
        df["is_stationary_bool"] = False

if "is_in_high_risk_segment" not in df.columns:
    df["is_in_high_risk_segment"] = df["segment_risk_band"].isin(["high", "very_high"])

if "is_in_very_high_risk_segment" not in df.columns:
    df["is_in_very_high_risk_segment"] = df["segment_risk_band"].eq("very_high")

if "is_stationary_in_high_risk" not in df.columns:
    df["is_stationary_in_high_risk"] = (
        df["is_stationary_bool"] & df["is_in_high_risk_segment"]
    )

if "is_stationary_in_very_high_risk" not in df.columns:
    df["is_stationary_in_very_high_risk"] = (
        df["is_stationary_bool"] & df["is_in_very_high_risk_segment"]
    )

if "duration_s_capped" not in df.columns:
    if "delta_time_s" in df.columns:
        df["duration_s_capped"] = df["delta_time_s"].fillna(0).clip(lower=0, upper=10)
    else:
        df["duration_s_capped"] = df["elapsed_s"].diff().fillna(0).clip(lower=0, upper=10)


# =========================================================
# 4. 平滑速度
# =========================================================
df["forward_speed_smooth_mps"] = (
    df["forward_speed_route_mps"]
    .rolling(window=15, center=True, min_periods=3)
    .median()
)


# =========================================================
# 5. 工具函式：只畫 high / very_high 背景
# =========================================================
RISK_COLOR_REPORT = {
    "high": "#fc8d59",
    "very_high": "#d7301f",
}


def build_runs(dataframe, col):
    runs = []
    if dataframe.empty:
        return runs

    values = dataframe[col].fillna("unknown").astype(str).tolist()
    start = 0

    for i in range(1, len(values)):
        if values[i] != values[start]:
            runs.append((start, i - 1, values[start]))
            start = i

    runs.append((start, len(values) - 1, values[start]))
    return runs


def add_high_risk_background(ax, x_col):
    for s, e, band in build_runs(df, "segment_risk_band"):
        if band not in ["high", "very_high"]:
            continue

        x0 = df.iloc[s][x_col]
        x1 = df.iloc[e][x_col]

        if e + 1 < len(df):
            x1 = df.iloc[e + 1][x_col]

        alpha = 0.12 if band == "high" else 0.22

        ax.axvspan(
            x0,
            x1,
            color=RISK_COLOR_REPORT.get(band, "#bdbdbd"),
            alpha=alpha,
        )


def find_very_high_time_runs():
    runs = []

    vh = df["segment_risk_band"].astype(str).eq("very_high").tolist()
    start = None

    for i, value in enumerate(vh):
        if value and start is None:
            start = i
        elif not value and start is not None:
            runs.append((start, i - 1))
            start = None

    if start is not None:
        runs.append((start, len(vh) - 1))

    return runs


very_high_runs = find_very_high_time_runs()


# =========================================================
# 6. 摘要統計
# =========================================================
total_duration_s = df["duration_s_capped"].sum()
high_duration_s = df.loc[df["is_in_high_risk_segment"], "duration_s_capped"].sum()
very_high_duration_s = df.loc[df["is_in_very_high_risk_segment"], "duration_s_capped"].sum()
stationary_high_s = df.loc[df["is_stationary_in_high_risk"], "duration_s_capped"].sum()
stationary_vh_s = df.loc[df["is_stationary_in_very_high_risk"], "duration_s_capped"].sum()

total_duration_min = total_duration_s / 60.0
high_duration_min = high_duration_s / 60.0
very_high_duration_min = very_high_duration_s / 60.0
stationary_high_min = stationary_high_s / 60.0
stationary_vh_min = stationary_vh_s / 60.0


# =========================================================
# 7. 畫圖
# =========================================================
fig, axes = plt.subplots(
    nrows=4,
    ncols=1,
    figsize=(15, 11),
    sharex=True,
    gridspec_kw={"height_ratios": [2.1, 1.35, 1.35, 1.45]},
)

ax_route, ax_speed, ax_risk, ax_stationary = axes


# ---------------------------------------------------------
# 7a. 活動進度
# ---------------------------------------------------------
add_high_risk_background(ax_route, "elapsed_min")

ax_route.plot(
    df["elapsed_min"],
    df["route_dist_m"],
    linewidth=2.0,
    label="route_dist_m",
)

vh_df = df[df["is_in_very_high_risk_segment"].astype(bool)]
if not vh_df.empty:
    ax_route.scatter(
        vh_df["elapsed_min"],
        vh_df["route_dist_m"],
        s=10,
        marker="o",
        alpha=0.5,
        label="very_high segment",
    )

# 標註 very_high time zones
y_max_route = df["route_dist_m"].max()

for start_i, end_i in very_high_runs:
    t_start = df.iloc[start_i]["elapsed_min"]
    t_end = df.iloc[end_i]["elapsed_min"]
    mid_t = (t_start + t_end) / 2
    start_dist = df.iloc[start_i]["route_dist_m"]
    end_dist = df.iloc[end_i]["route_dist_m"]

    ax_route.text(
        mid_t,
        y_max_route * 0.98,
        f"{t_start:.0f}–{t_end:.0f} min\n"
        f"{start_dist:.0f}–{end_dist:.0f} m\n"
        "very_high",
        ha="center",
        va="top",
        fontsize=8,
        color="#7f0000",
    )

ax_route.set_ylabel("Route distance (m)")
ax_route.grid(True, alpha=0.25)
ax_route.legend(loc="upper left", fontsize=8)
ax_route.set_title("Activity Progression with High-Risk Background")


# ---------------------------------------------------------
# 7b. 速度
# ---------------------------------------------------------
add_high_risk_background(ax_speed, "elapsed_min")

ax_speed.plot(
    df["elapsed_min"],
    df["forward_speed_route_mps"],
    linewidth=0.7,
    alpha=0.25,
    label="forward_speed_route_mps raw",
)

ax_speed.plot(
    df["elapsed_min"],
    df["forward_speed_smooth_mps"],
    linewidth=1.9,
    label="forward_speed_route_mps smooth",
)

ax_speed.axhline(
    0.2,
    linestyle="--",
    linewidth=1.0,
    alpha=0.5,
    label="stationary threshold",
)

ax_speed.set_ylabel("Speed (m/s)")
ax_speed.grid(True, alpha=0.25)
ax_speed.legend(loc="upper right", fontsize=8)


# ---------------------------------------------------------
# 7c. 風險分數
# ---------------------------------------------------------
add_high_risk_background(ax_risk, "elapsed_min")

ax_risk.plot(
    df["elapsed_min"],
    df["segment_risk_score"],
    linewidth=1.7,
    label="segment_risk_score",
)

if "segment_risk_score_mean" in df.columns:
    ax_risk.plot(
        df["elapsed_min"],
        df["segment_risk_score_mean"],
        linewidth=1.2,
        linestyle="--",
        label="segment_risk_score_mean",
    )

ax_risk.axhline(3.5, linestyle="--", linewidth=1.0, alpha=0.4, label="high threshold")
ax_risk.axhline(6.0, linestyle="--", linewidth=1.0, alpha=0.4, label="very_high threshold")

ax_risk.set_ylabel("Risk score")
ax_risk.grid(True, alpha=0.25)
ax_risk.legend(loc="upper right", fontsize=8)


# ---------------------------------------------------------
# 7d. 高風險低速 / 停留
# ---------------------------------------------------------
add_high_risk_background(ax_stationary, "elapsed_min")

# 淡化一般 stationary
stationary_df = df[df["is_stationary_bool"].astype(bool)]
if not stationary_df.empty:
    ax_stationary.scatter(
        stationary_df["elapsed_min"],
        stationary_df["route_dist_m"],
        s=8,
        alpha=0.12,
        label="stationary",
    )

stationary_high_df = df[df["is_stationary_in_high_risk"].astype(bool)]
if not stationary_high_df.empty:
    ax_stationary.scatter(
        stationary_high_df["elapsed_min"],
        stationary_high_df["route_dist_m"],
        s=24,
        marker="x",
        label="stationary in high/very_high",
    )

stationary_vh_df = df[df["is_stationary_in_very_high_risk"].astype(bool)]
if not stationary_vh_df.empty:
    ax_stationary.scatter(
        stationary_vh_df["elapsed_min"],
        stationary_vh_df["route_dist_m"],
        s=38,
        marker="D",
        facecolors="none",
        label="stationary in very_high",
    )

ax_stationary.set_xlabel("Elapsed time (min)")
ax_stationary.set_ylabel("Route distance (m)")
ax_stationary.grid(True, alpha=0.25)
ax_stationary.legend(loc="upper left", fontsize=8)


# ---------------------------------------------------------
# 7e. 全圖標題與摘要文字
# ---------------------------------------------------------
summary_text = (
    f"Total: {total_duration_min:.1f} min | "
    f"High+: {high_duration_min:.1f} min | "
    f"Very high: {very_high_duration_min:.1f} min | "
    f"Stationary in high+: {stationary_high_min:.1f} min | "
    f"Stationary in very high: {stationary_vh_min:.1f} min"
)

fig.text(
    0.5,
    0.935,
    summary_text,
    ha="center",
    va="center",
    fontsize=10,
)

plt.suptitle(
    "Activity Risk Timeline Report\n"
    "High-Risk Exposure and Stationary Behavior",
    fontsize=14,
)

plt.tight_layout(rect=[0, 0, 1, 0.91])
plt.savefig(OUT_PNG, dpi=220)
plt.close()


# =========================================================
# 8. 輸出 plot data
# =========================================================
plot_cols = [
    "activity_idx",
    "time",
    "elapsed_s",
    "elapsed_min",
    "route_dist_m",
    "raw_ele_m",
    "forward_speed_route_mps",
    "forward_speed_smooth_mps",
    "is_stationary_bool",
    "segment_start_m",
    "segment_end_m",
    "segment_risk_score",
    "segment_risk_score_mean",
    "segment_risk_band",
    "effort_score_mean",
    "exposure_score_mean",
    "gpx_mismatch_ratio",
    "dist_misaligned_ratio",
    "is_in_high_risk_segment",
    "is_in_very_high_risk_segment",
    "is_stationary_in_high_risk",
    "is_stationary_in_very_high_risk",
    "risk_reason_merged",
]

plot_cols = [c for c in plot_cols if c in df.columns]
df[plot_cols].to_csv(OUT_CSV, index=False, encoding="utf-8-sig")


# =========================================================
# 9. 終端摘要
# =========================================================
print("完成！")
print("PNG:", OUT_PNG.resolve())
print("plot CSV:", OUT_CSV.resolve())

print("\n=== duration summary ===")
print(f"total_duration_min: {total_duration_min:.2f}")
print(f"high_duration_min: {high_duration_min:.2f}")
print(f"very_high_duration_min: {very_high_duration_min:.2f}")
print(f"stationary_high_min: {stationary_high_min:.2f}")
print(f"stationary_very_high_min: {stationary_vh_min:.2f}")

print("\n=== segment_risk_band by activity points ===")
print(df["segment_risk_band"].value_counts(dropna=False))

print("\n=== very_high time runs ===")
if very_high_runs:
    for start_i, end_i in very_high_runs:
        print(
            f'{df.iloc[start_i]["elapsed_min"]:.1f}–'
            f'{df.iloc[end_i]["elapsed_min"]:.1f} min | '
            f'{df.iloc[start_i]["route_dist_m"]:.0f}–'
            f'{df.iloc[end_i]["route_dist_m"]:.0f} m'
        )
else:
    print("none")

print("\n=== stationary in risk ===")
print("stationary in high:", int(df["is_stationary_in_high_risk"].sum()))
print("stationary in very_high:", int(df["is_stationary_in_very_high_risk"].sum()))