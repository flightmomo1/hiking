from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


# =========================================================
# ib1h_v2_plot_contour_window_profile.py
#
# 目的：
# - 疊合 GPX elevation 與 Contour-derived elevation band
# - Contour 不是逐點高程，因此用 window elev_min/elev_max 形成高程帶
# - 使用 median bias 將 contour band 對齊 GPX 高度基準，方便視覺比較
# =========================================================


# =========================================================
# 0. 路徑設定
# =========================================================
CASE_ID = "qixing_xiaoyoukeng_roundtrip_joyhike"
CASE_NAME = "七星山小油坑進出 Joyhike"

CONTOUR_CSV = (
    Path("ib1g_v2_output")
    / CASE_ID
    / "qixing_contour_window_features.csv"
)

PROFILE_CSV = (
    Path("ib1a_route_elevation_profile_output")
    / CASE_ID
    / "qixing_route_profile.csv"
)

OUT_DIR = Path("ib1h_v2_contour_window_profile_output") / CASE_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_PNG = OUT_DIR / "qixing_contour_elevation_band_profile.png"
OUT_CSV = OUT_DIR / "qixing_contour_elevation_band_merged.csv"


# =========================================================
# 1. 輸入檢查
# =========================================================
for fp in [CONTOUR_CSV, PROFILE_CSV]:
    if not fp.exists():
        raise FileNotFoundError(f"找不到輸入檔：{fp.resolve()}")


# =========================================================
# 2. 讀資料
# =========================================================
contour = pd.read_csv(CONTOUR_CSV)
profile = pd.read_csv(PROFILE_CSV)

print("contour rows:", len(contour))
print("profile rows:", len(profile))


# =========================================================
# 3. 欄位確認
# =========================================================
required_contour_cols = [
    "dist_mid",
    "elev_min",
    "elev_max",
    "elev_range",
    "slope_band_window",
]

for c in required_contour_cols:
    if c not in contour.columns:
        raise ValueError(f"contour CSV 缺少欄位：{c}")


profile_dist_col = None
for c in ["dist_m", "distance_m", "cum_dist_m"]:
    if c in profile.columns:
        profile_dist_col = c
        break

profile_ele_col = None
for c in ["ele_gpx_m", "elev_gpx_m", "elevation_m", "ele_m"]:
    if c in profile.columns:
        profile_ele_col = c
        break

if profile_dist_col is None:
    raise ValueError("profile CSV 找不到距離欄位，例如 dist_m")

if profile_ele_col is None:
    raise ValueError("profile CSV 找不到 GPX 高程欄位，例如 ele_gpx_m")


# =========================================================
# 4. 依距離對齊 GPX elevation 到 contour segments
# =========================================================
profile_small = profile[[profile_dist_col, profile_ele_col]].copy()
profile_small = profile_small.rename(
    columns={
        profile_dist_col: "dist_m",
        profile_ele_col: "ele_gpx_m",
    }
).sort_values("dist_m")

profile_small["ele_gpx_m"] = pd.to_numeric(
    profile_small["ele_gpx_m"],
    errors="coerce",
)

has_gpx_elevation = profile_small["ele_gpx_m"].notna().any()

print("has_gpx_elevation:", has_gpx_elevation)

contour = contour.sort_values("dist_mid").copy()

merged = pd.merge_asof(
    contour,
    profile_small,
    left_on="dist_mid",
    right_on="dist_m",
    direction="nearest",
)
# =========================================================
# 4b. 距離軸對齊檢查
# =========================================================
merged["dist_diff_m"] = merged["dist_mid"] - merged["dist_m"]

print("\n--- dist alignment ---")
print(merged["dist_diff_m"].describe())

max_abs_dist_diff = merged["dist_diff_m"].abs().max()

if max_abs_dist_diff > 50:
    print(f"警告：GPX 與 contour 視窗距離對齊最大差異較大：{max_abs_dist_diff:.2f} m")
else:
    print(f"距離對齊檢查通過：max abs diff = {max_abs_dist_diff:.2f} m")


# =========================================================
# 5. 建立 Contour-derived elevation band
# =========================================================
merged["contour_elev_mid"] = (
    merged["elev_min"] + merged["elev_max"]
) / 2

valid_bias = merged[["ele_gpx_m", "contour_elev_mid"]].dropna()

if has_gpx_elevation and len(valid_bias) > 0:
    contour_bias = (
        valid_bias["ele_gpx_m"] - valid_bias["contour_elev_mid"]
    ).median()
    bias_mode = "median_bias_to_gpx"
else:
    contour_bias = 0.0
    bias_mode = "none_no_gpx_elevation"


merged["has_gpx_elevation"] = has_gpx_elevation
merged["contour_bias_mode"] = bias_mode

merged["contour_elev_mid_aligned"] = merged["contour_elev_mid"] + contour_bias
merged["contour_elev_min_aligned"] = merged["elev_min"] + contour_bias
merged["contour_elev_max_aligned"] = merged["elev_max"] + contour_bias

merged["contour_bias_applied_m"] = contour_bias

print("contour elevation bias applied:", round(contour_bias, 2))


# =========================================================
# 6. 色帶設定
# =========================================================
BAND_COLOR = {
    "flat": "#bdbdbd",
    "gentle": "#74c476",
    "moderate": "#fdae6b",
    "steep": "#e6550d",
    "very_steep": "#a50f15",
    "unknown": "#9ecae1",
}


def build_runs(df, col):
    runs = []
    if df.empty:
        return runs

    start = 0
    values = df[col].fillna("unknown").tolist()

    for i in range(1, len(values)):
        if values[i] != values[start]:
            runs.append((start, i - 1, values[start]))
            start = i

    runs.append((start, len(values) - 1, values[start]))
    return runs


# =========================================================
# 7. 輸出合併 CSV
# =========================================================
merged.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

plot_x = profile_small["dist_m"]

# =========================================================
# 8. 畫圖（v3：GPX x-axis aligned）
# =========================================================
fig, ax1 = plt.subplots(figsize=(15, 6))

# -------------------------------
# slope band background
# -------------------------------
for s, e, band in build_runs(merged, "slope_band_window"):

    x0 = merged.iloc[s]["dist_mid"]
    x1 = merged.iloc[e]["dist_mid"]

    if e + 1 < len(merged):
        x1 = merged.iloc[e + 1]["dist_mid"]

    ax1.axvspan(
        x0,
        x1,
        color=BAND_COLOR.get(band, "#9ecae1"),
        alpha=0.12,
    )


# -------------------------------
# contour elevation band
# contour 用自己的 dist_mid
# -------------------------------
ax1.fill_between(
    merged["dist_mid"],
    merged["contour_elev_min_aligned"],
    merged["contour_elev_max_aligned"],
    alpha=0.22,
    label="Contour elevation range (aligned)",
)

# contour midpoint
ax1.plot(
    merged["dist_mid"],
    merged["contour_elev_mid_aligned"],
    linewidth=1.5,
    linestyle="--",
    label="Contour midpoint elevation (aligned)",
)


# -------------------------------
# GPX elevation
# 用完整 GPX distance
# -------------------------------
if has_gpx_elevation:
    ax1.plot(
        profile_small["dist_m"],
        profile_small["ele_gpx_m"],
        linewidth=2.0,
        label="GPX elevation",
    )


# -------------------------------
# ax1 settings
# -------------------------------
ax1.set_xlabel("Distance (m)")
ax1.set_ylabel("Elevation (m)")
ax1.grid(True, alpha=0.25)


# -------------------------------
# second y-axis
# contour range
# -------------------------------
ax2 = ax1.twinx()

ax2.plot(
    merged["dist_mid"],
    merged["elev_range"],
    linewidth=1.0,
    linestyle=":",
    label="Contour elevation range",
)

ax2.set_ylabel(
    "Contour elev range (m / 100m window)"
)


# -------------------------------
# 統一 x 軸
# 以 GPX 完整距離為主
# -------------------------------
route_max = profile_small["dist_m"].max()

route_max_rounded = (
    int(route_max / 500) + 1
) * 500

for ax in [ax1, ax2]:

    ax.set_xlim(
        0,
        route_max_rounded,
    )

    ax.set_xticks(
        range(
            0,
            route_max_rounded + 1,
            500,
        )
    )


# -------------------------------
# legends
# -------------------------------
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()

ax1.legend(
    lines1 + lines2,
    labels1 + labels2,
    loc="upper right",
)


# -------------------------------
# title
# -------------------------------
plt.title(
    "Qixing Route: GPX Elevation vs Contour-derived Elevation Band\n"
    f"Contour band aligned by median bias = {contour_bias:.2f} m"
)

# -------------------------------
# output
# -------------------------------
plt.tight_layout()

plt.savefig(
    OUT_PNG,
    dpi=220,
)

plt.close()

print("\n完成！")
print("PNG:", OUT_PNG.resolve())
print("merged CSV:", OUT_CSV.resolve())