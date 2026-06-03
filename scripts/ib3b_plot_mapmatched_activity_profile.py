from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


"""
ib3b_plot_mapmatched_activity_profile.py

定位：
- ib3a_mapmatch_highfreq_activity.py 的 QA 視覺化腳本
- 用於檢查 GPX/FIT 活動軌跡貼回 OSM 主線後的品質
- 主要檢查：
  1. route_dist_m vs raw_ele_m
  2. route_dist_m vs forward_speed_route_mps
  3. route_dist_m vs offset_to_mainline_m
  4. match_quality / stationary markers

輸入：
- ib3a_mapmatched_activity_output/qixing_activity_mapmatched.csv

輸出：
- ib3b_mapmatched_activity_profile_output/qixing_mapmatched_activity_profile.png
- ib3b_mapmatched_activity_profile_output/qixing_mapmatched_activity_profile_plot_data.csv
"""


# =========================================================
# 0. 路徑設定
# =========================================================
INPUT_CSV = Path("ib3a_mapmatched_activity_output/qixing_activity_mapmatched.csv")

CONTOUR_PROFILE_CSV = Path(
    "ib1h_v2_contour_window_profile_output/qixing_gpx_vs_contour_elevation_band_merged.csv"
)

OUT_DIR = Path("ib3b_mapmatched_activity_profile_output")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_PNG = OUT_DIR / "qixing_mapmatched_activity_profile_aligned_contour.png"
OUT_PNG_RAW = OUT_DIR / "qixing_mapmatched_activity_profile_raw_contour.png"
OUT_CSV = OUT_DIR / "qixing_mapmatched_activity_profile_plot_data.csv"


# =========================================================
# 1. 讀資料
# =========================================================
if not INPUT_CSV.exists():
    raise FileNotFoundError(f"找不到輸入檔：{INPUT_CSV.resolve()}，請先執行 ib3a")

df = pd.read_csv(INPUT_CSV)

if df.empty:
    raise ValueError("輸入 CSV 為空")

required_cols = [
    "route_dist_m",
    "raw_ele_m",
    "forward_speed_route_mps",
    "offset_to_mainline_m",
    "match_quality",
]

for c in required_cols:
    if c not in df.columns:
        raise ValueError(f"缺少欄位：{c}")

df = df.sort_values("route_dist_m").reset_index(drop=True)

# =========================================================
# 1b. 合併國土測繪 Contour-derived elevation band
# =========================================================
if CONTOUR_PROFILE_CSV.exists():
    contour_df = pd.read_csv(CONTOUR_PROFILE_CSV)

    required_contour_cols = [
        "dist_mid",
        "elev_min",
        "contour_elev_mid",
        "elev_max",
        "contour_elev_min_aligned",
        "contour_elev_mid_aligned",
        "contour_elev_max_aligned",
    ]

    missing = [c for c in required_contour_cols if c not in contour_df.columns]

    if missing:
        print(f"警告：Contour profile 缺少欄位 {missing}，略過國土測繪高程帶")
    else:
        contour_small = contour_df[required_contour_cols].copy()
        contour_small = contour_small.sort_values("dist_mid")

        df = pd.merge_asof(
            df.sort_values("route_dist_m"),
            contour_small,
            left_on="route_dist_m",
            right_on="dist_mid",
            direction="nearest",
        )

        df["contour_dist_diff_m"] = df["route_dist_m"] - df["dist_mid"]

        print("\n=== contour elevation band merged ===")
        print(df["contour_dist_diff_m"].describe())

        # raw NLSC contour vs GPX elevation bias
    if {"raw_ele_m", "contour_elev_mid"}.issubset(df.columns):
        valid_bias = df[["raw_ele_m", "contour_elev_mid"]].dropna()

        if not valid_bias.empty:
            raw_contour_bias_m = (
                valid_bias["raw_ele_m"] - valid_bias["contour_elev_mid"]
            ).median()

            mean_raw_contour_bias_m = (
                valid_bias["raw_ele_m"] - valid_bias["contour_elev_mid"]
            ).mean()

            print("\n=== raw contour elevation bias ===")
            print(f"median(raw_ele_m - contour_elev_mid): {raw_contour_bias_m:.2f} m")
            print(f"mean(raw_ele_m - contour_elev_mid): {mean_raw_contour_bias_m:.2f} m")
        else:
            raw_contour_bias_m = None
            mean_raw_contour_bias_m = None
else:
    print(f"警告：找不到 {CONTOUR_PROFILE_CSV}，上圖只顯示 GPX 高程")


# =========================================================
# 2. 欄位容錯
# =========================================================
if "time" in df.columns:
    df["time"] = pd.to_datetime(df["time"], errors="coerce")
else:
    df["time"] = pd.NaT

if "is_stationary" not in df.columns:
    df["is_stationary"] = False

if "speed_capped" not in df.columns:
    df["speed_capped"] = False

if "backtrack_constrained" not in df.columns:
    df["backtrack_constrained"] = False

if "is_off_route" not in df.columns:
    df["is_off_route"] = False


# =========================================================
# 3. 平滑速度
# =========================================================
df["forward_speed_smooth_mps"] = (
    df["forward_speed_route_mps"]
    .rolling(window=15, center=True, min_periods=3)
    .median()
)


# =========================================================
# 4. 顏色設定
# =========================================================
QUALITY_COLOR = {
    "good": "#2ca25f",
    "fair": "#fec44f",
    "weak": "#fc8d59",
    "poor": "#d7301f",
    "off_route": "#756bb1",
}


# =========================================================
# 5. 畫圖
# =========================================================
fig, axes = plt.subplots(
    nrows=3,
    ncols=1,
    figsize=(15, 9),
    sharex=True,
    gridspec_kw={"height_ratios": [2.2, 1.5, 1.2]},
)

ax_ele, ax_speed, ax_offset = axes


# ---------------------------------------------------------
# 5a. 高程
# ---------------------------------------------------------
ax_ele.plot(
    df["route_dist_m"],
    df["raw_ele_m"],
    linewidth=1.4,
    label="raw_ele_m",
)

# Contour-derived elevation band
contour_cols = {
    "contour_elev_min_aligned",
    "contour_elev_mid_aligned",
    "contour_elev_max_aligned",
}

if contour_cols.issubset(df.columns):
    ax_ele.fill_between(
        df["route_dist_m"],
        df["contour_elev_min_aligned"],
        df["contour_elev_max_aligned"],
        alpha=0.18,
        label="NLSC contour elevation band (bias-aligned)",
    )

    ax_ele.plot(
        df["route_dist_m"],
        df["contour_elev_mid_aligned"],
        linewidth=1.2,
        linestyle="--",
        label="NLSC contour midpoint (bias-aligned)",
    )

# stationary markers
stationary_df = df[df["is_stationary"].astype(bool)]
if not stationary_df.empty:
    ax_ele.scatter(
        stationary_df["route_dist_m"],
        stationary_df["raw_ele_m"],
        s=8,
        marker="o",
        alpha=0.35,
        label="stationary",
    )

ax_ele.set_ylabel("Elevation (m)")
ax_ele.grid(True, alpha=0.25)
ax_ele.legend(loc="upper right", fontsize=8)


# ---------------------------------------------------------
# 5b. 沿主線前進速度
# ---------------------------------------------------------
ax_speed.plot(
    df["route_dist_m"],
    df["forward_speed_route_mps"],
    linewidth=0.7,
    alpha=0.35,
    label="forward_speed_route_mps raw",
)

ax_speed.plot(
    df["route_dist_m"],
    df["forward_speed_smooth_mps"],
    linewidth=1.8,
    label="forward_speed_route_mps smooth",
)

# speed capped markers
speed_capped_df = df[df["speed_capped"].astype(bool)]
if not speed_capped_df.empty:
    ax_speed.scatter(
        speed_capped_df["route_dist_m"],
        speed_capped_df["forward_speed_route_mps"],
        s=20,
        marker="x",
        label="speed_capped",
    )

ax_speed.axhline(0.2, linestyle="--", linewidth=1.0, alpha=0.5, label="stationary threshold")
ax_speed.set_ylabel("Speed (m/s)")
ax_speed.grid(True, alpha=0.25)
ax_speed.legend(loc="upper right", fontsize=8)


# ---------------------------------------------------------
# 5c. offset / match quality
# ---------------------------------------------------------
ax_offset.plot(
    df["route_dist_m"],
    df["offset_to_mainline_m"],
    linewidth=1.0,
    label="offset_to_mainline_m",
)

for quality, color in QUALITY_COLOR.items():
    qdf = df[df["match_quality"].astype(str) == quality]
    if qdf.empty:
        continue

    ax_offset.scatter(
        qdf["route_dist_m"],
        qdf["offset_to_mainline_m"],
        s=9,
        color=color,
        label=f"match_quality={quality}",
    )

# constraint markers
backtrack_df = df[df["backtrack_constrained"].astype(bool)]
if not backtrack_df.empty:
    ax_offset.scatter(
        backtrack_df["route_dist_m"],
        backtrack_df["offset_to_mainline_m"],
        s=30,
        marker="^",
        label="backtrack_constrained",
    )

ax_offset.axhline(10, linestyle="--", linewidth=1.0, alpha=0.4, label="10m offset")
ax_offset.axhline(25, linestyle="--", linewidth=1.0, alpha=0.4, label="25m offset")
ax_offset.set_ylabel("Offset (m)")
ax_offset.set_xlabel("Route distance (m)")
ax_offset.grid(True, alpha=0.25)
ax_offset.legend(loc="upper right", fontsize=7)


plt.suptitle(
    "Mapmatched Activity Profile\n"
    "Elevation / Forward Speed / Mainline Offset",
    fontsize=14,
)

plt.tight_layout(rect=[0, 0, 1, 0.95])
plt.savefig(OUT_PNG, dpi=220)
plt.close()

# =========================================================
# 5d. 另輸出 raw NLSC contour 高程版本
# =========================================================
raw_contour_cols = {
    "elev_min",
    "contour_elev_mid",
    "elev_max",
}

if raw_contour_cols.issubset(df.columns):
    fig_raw, axes_raw = plt.subplots(
        nrows=3,
        ncols=1,
        figsize=(15, 9),
        sharex=True,
        gridspec_kw={"height_ratios": [2.2, 1.5, 1.2]},
    )

    ax_ele_raw, ax_speed_raw, ax_offset_raw = axes_raw

    # -----------------------------------------------------
    # raw contour elevation
    # -----------------------------------------------------
    ax_ele_raw.plot(
        df["route_dist_m"],
        df["raw_ele_m"],
        linewidth=1.4,
        label="GPX raw_ele_m",
    )

    ax_ele_raw.fill_between(
        df["route_dist_m"],
        df["elev_min"],
        df["elev_max"],
        alpha=0.18,
        label="NLSC raw contour elevation band",
    )

    ax_ele_raw.plot(
        df["route_dist_m"],
        df["contour_elev_mid"],
        linewidth=1.2,
        linestyle="--",
        label="NLSC raw contour midpoint",
    )

    stationary_df = df[df["is_stationary"].astype(bool)]
    if not stationary_df.empty:
        ax_ele_raw.scatter(
            stationary_df["route_dist_m"],
            stationary_df["raw_ele_m"],
            s=8,
            marker="o",
            alpha=0.35,
            label="stationary",
        )

    ax_ele_raw.set_ylabel("Elevation (m)")
    ax_ele_raw.grid(True, alpha=0.25)
    ax_ele_raw.legend(loc="upper right", fontsize=8)

    # -----------------------------------------------------
    # speed
    # -----------------------------------------------------
    ax_speed_raw.plot(
        df["route_dist_m"],
        df["forward_speed_route_mps"],
        linewidth=0.7,
        alpha=0.35,
        label="forward_speed_route_mps raw",
    )

    ax_speed_raw.plot(
        df["route_dist_m"],
        df["forward_speed_smooth_mps"],
        linewidth=1.8,
        label="forward_speed_route_mps smooth",
    )

    speed_capped_df = df[df["speed_capped"].astype(bool)]
    if not speed_capped_df.empty:
        ax_speed_raw.scatter(
            speed_capped_df["route_dist_m"],
            speed_capped_df["forward_speed_route_mps"],
            s=20,
            marker="x",
            label="speed_capped",
        )

    ax_speed_raw.axhline(
        0.2,
        linestyle="--",
        linewidth=1.0,
        alpha=0.5,
        label="stationary threshold",
    )

    ax_speed_raw.set_ylabel("Speed (m/s)")
    ax_speed_raw.grid(True, alpha=0.25)
    ax_speed_raw.legend(loc="upper right", fontsize=8)

    # -----------------------------------------------------
    # offset
    # -----------------------------------------------------
    ax_offset_raw.plot(
        df["route_dist_m"],
        df["offset_to_mainline_m"],
        linewidth=1.0,
        label="offset_to_mainline_m",
    )

    for quality, color in QUALITY_COLOR.items():
        qdf = df[df["match_quality"].astype(str) == quality]
        if qdf.empty:
            continue

        ax_offset_raw.scatter(
            qdf["route_dist_m"],
            qdf["offset_to_mainline_m"],
            s=9,
            color=color,
            label=f"match_quality={quality}",
        )

    backtrack_df = df[df["backtrack_constrained"].astype(bool)]
    if not backtrack_df.empty:
        ax_offset_raw.scatter(
            backtrack_df["route_dist_m"],
            backtrack_df["offset_to_mainline_m"],
            s=30,
            marker="^",
            label="backtrack_constrained",
        )

    ax_offset_raw.axhline(10, linestyle="--", linewidth=1.0, alpha=0.4, label="10m offset")
    ax_offset_raw.axhline(25, linestyle="--", linewidth=1.0, alpha=0.4, label="25m offset")
    ax_offset_raw.set_ylabel("Offset (m)")
    ax_offset_raw.set_xlabel("Route distance (m)")
    ax_offset_raw.grid(True, alpha=0.25)
    ax_offset_raw.legend(loc="upper right", fontsize=7)

    plt.suptitle(
        "Mapmatched Activity Profile\n"
        "GPX Elevation vs Raw NLSC Contour Elevation Band",
        fontsize=14,
    )

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(OUT_PNG_RAW, dpi=220)
    plt.close()

else:
    print("警告：缺少 raw contour 欄位，未輸出 raw contour 圖")

# =========================================================
# 6. 輸出 plot data
# =========================================================

# GPX 高程與 raw / aligned NLSC contour midpoint 的差值
if "contour_elev_mid" in df.columns:
    df["raw_minus_contour_mid_m"] = (
        df["raw_ele_m"] - df["contour_elev_mid"]
    )

if "contour_elev_mid_aligned" in df.columns:
    df["raw_minus_contour_mid_aligned_m"] = (
        df["raw_ele_m"] - df["contour_elev_mid_aligned"]
    )

plot_cols = [
    "activity_idx",
    "time",
    "route_dist_m",
    "raw_ele_m",

    # raw NLSC contour elevation band
    "elev_min",
    "contour_elev_mid",
    "elev_max",
    "raw_minus_contour_mid_m",

    # bias-aligned NLSC contour elevation band
    "contour_elev_min_aligned",
    "contour_elev_mid_aligned",
    "contour_elev_max_aligned",
    "raw_minus_contour_mid_aligned_m",
    "contour_dist_diff_m",

    # activity dynamics
    "forward_delta_route_dist_m",
    "forward_speed_route_mps",
    "forward_speed_smooth_mps",

    # map matching QA
    "offset_to_mainline_m",
    "match_quality",
    "is_stationary",
    "speed_capped",
    "backtrack_constrained",
    "is_off_route",

    # coordinates
    "raw_lat",
    "raw_lon",
    "matched_lat",
    "matched_lon",
]

plot_cols = [c for c in plot_cols if c in df.columns]
df[plot_cols].to_csv(OUT_CSV, index=False, encoding="utf-8-sig")


# =========================================================
# 7. 摘要
# =========================================================
print("完成！")
print("PNG aligned:", OUT_PNG.resolve())

if "OUT_PNG_RAW" in globals():
    print("PNG raw:", OUT_PNG_RAW.resolve())

print("plot CSV:", OUT_CSV.resolve())

print("\n=== match_quality ===")
print(df["match_quality"].value_counts(dropna=False))

print("\n=== offset_to_mainline_m ===")
print(df["offset_to_mainline_m"].describe())

print("\n=== forward_speed_route_mps ===")
print(df["forward_speed_route_mps"].describe())

print("\n=== is_stationary ===")
print(df["is_stationary"].value_counts(dropna=False))

print("\n=== constraints ===")
for c in ["speed_capped", "backtrack_constrained", "is_off_route"]:
    if c in df.columns:
        print(c)
        print(df[c].value_counts(dropna=False))