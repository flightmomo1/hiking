from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


# =========================================================
# ib1h_plot_contour_window_profile.py
# 畫 GPX elevation + ContourL window terrain proxy
# =========================================================

CONTOUR_CSV = Path("ib1g_v2_output/qixing_contour_window_features.csv")

# 優先讀 ib1c，因為它已經是 route profile + semantic
PROFILE_CSV = Path("ib1c_route_profile_semantic_output/qixing_route_profile_semantic_enriched.csv")

OUT_DIR = Path("ib1h_contour_window_profile_output")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_PNG = OUT_DIR / "qixing_contour_window_profile.png"
OUT_CSV = OUT_DIR / "qixing_contour_window_profile_merged.csv"


# =========================================================
# 1. 檢查輸入
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
if "dist_mid" not in contour.columns:
    raise ValueError("contour CSV 缺少 dist_mid 欄位")

if "slope_band_window" not in contour.columns:
    raise ValueError("contour CSV 缺少 slope_band_window 欄位")

if "elev_range" not in contour.columns:
    raise ValueError("contour CSV 缺少 elev_range 欄位")


# GPX profile 欄位容錯
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
# 4. 合併最近 GPX 高程到 contour segment
# =========================================================
profile_small = profile[[profile_dist_col, profile_ele_col]].copy()
profile_small = profile_small.rename(
    columns={
        profile_dist_col: "dist_m",
        profile_ele_col: "ele_gpx_m",
    }
).sort_values("dist_m")

contour = contour.sort_values("dist_mid").copy()

merged = pd.merge_asof(
    contour,
    profile_small,
    left_on="dist_mid",
    right_on="dist_m",
    direction="nearest",
)

merged.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")


# =========================================================
# 5. 色帶設定
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
# 6. 畫圖
# =========================================================
fig, ax1 = plt.subplots(figsize=(14, 5))

# GPX elevation
ax1.plot(
    merged["dist_mid"],
    merged["ele_gpx_m"],
    linewidth=1.8,
    label="GPX elevation",
)

ax1.set_xlabel("Distance (m)")
ax1.set_ylabel("Elevation (m)")
ax1.grid(True, alpha=0.25)

# slope band 色帶
y_min = merged["ele_gpx_m"].min()
y_max = merged["ele_gpx_m"].max()

for s, e, band in build_runs(merged, "slope_band_window"):
    x0 = merged.iloc[s]["dist_mid"]
    x1 = merged.iloc[e]["dist_mid"]

    if e + 1 < len(merged):
        x1 = merged.iloc[e + 1]["dist_mid"]

    ax1.axvspan(
        x0,
        x1,
        color=BAND_COLOR.get(band, "#9ecae1"),
        alpha=0.18,
    )

# elev_range 第二軸
ax2 = ax1.twinx()
ax2.plot(
    merged["dist_mid"],
    merged["elev_range"],
    linewidth=1.2,
    linestyle="--",
    label="Contour elevation range (100m window)",
)

ax2.set_ylabel("Contour elev range (m / 100m window)")

# legend
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right")

plt.title("Qixing Route: GPX Elevation + Contour Window Terrain Proxy")
plt.tight_layout()
plt.savefig(OUT_PNG, dpi=200)
plt.close()


# =========================================================
# 7. 摘要
# =========================================================
print("完成！")
print("PNG:", OUT_PNG.resolve())
print("merged CSV:", OUT_CSV.resolve())

print("\n--- slope_band_window ---")
print(merged["slope_band_window"].value_counts(dropna=False))

print("\n--- elev_range ---")
print(merged["elev_range"].describe())