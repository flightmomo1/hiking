from pathlib import Path
import numpy as np
import pandas as pd


# =========================================================
# 設定
# =========================================================
MERGED_FP = Path("ib1h_contour_window_profile_output/qixing_contour_window_profile_merged.csv")

OUT_DIR = Path("ib1i_validation_output")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_CSV = OUT_DIR / "qixing_gpx_vs_contour_validation.csv"


# =========================================================
# 讀資料
# =========================================================
if not MERGED_FP.exists():
    raise FileNotFoundError(MERGED_FP)

df = pd.read_csv(MERGED_FP)

required_cols = ["dist_mid", "ele_gpx_m", "elev_range", "slope_band_window"]
for c in required_cols:
    if c not in df.columns:
        raise ValueError(f"缺少欄位: {c}")


# =========================================================
# 1. 計算 GPX window slope
# =========================================================
df = df.sort_values("dist_mid").reset_index(drop=True)

# 你的資料約 20m 一點，5 點約 100m window
WINDOW_N = 5
WINDOW_LEN = 100.0

df["elev_min_gpx_window"] = df["ele_gpx_m"].rolling(
    WINDOW_N, center=True, min_periods=3
).min()

df["elev_max_gpx_window"] = df["ele_gpx_m"].rolling(
    WINDOW_N, center=True, min_periods=3
).max()

df["elev_range_gpx_window"] = (
    df["elev_max_gpx_window"] - df["elev_min_gpx_window"]
)

df["slope_gpx_window"] = df["elev_range_gpx_window"] / WINDOW_LEN


# =========================================================
# 2. Contour window slope
# =========================================================
df["slope_contour_window"] = df["elev_range"] / WINDOW_LEN


# =========================================================
# 3. 平滑
# =========================================================
df["slope_gpx_window_smooth"] = (
    df["slope_gpx_window"].rolling(3, center=True, min_periods=2).mean()
)

df["slope_contour_window_smooth"] = (
    df["slope_contour_window"].rolling(3, center=True, min_periods=2).mean()
)


# =========================================================
# 4. 計算相關性
# =========================================================
valid = df[["slope_gpx_window_smooth", "slope_contour_window_smooth"]].dropna()

if len(valid) > 10:
    corr = np.corrcoef(
        valid["slope_gpx_window_smooth"].abs(),
        valid["slope_contour_window_smooth"].abs(),
    )[0, 1]
else:
    corr = np.nan


# =========================================================
# 5. slope 差異
# =========================================================
df["slope_diff_window"] = (
    df["slope_gpx_window_smooth"] - df["slope_contour_window_smooth"]
)


# =========================================================
# 6. 標記異常
# =========================================================
THRESH_DIFF = 0.25

df["gpx_quality_flag"] = np.where(
    abs(df["slope_diff_window"]) > THRESH_DIFF,
    "mismatch",
    "ok",
)

# contour 不是絕對高程，不能估 elevation bias
bias_est = np.nan


# =========================================================
# 7. 統計指標（取代 correlation 為主判讀）
# =========================================================
total_n = len(df)

ok_n = (df["gpx_quality_flag"] == "ok").sum()
mismatch_n = (df["gpx_quality_flag"] == "mismatch").sum()

ok_ratio = ok_n / total_n if total_n > 0 else np.nan
mismatch_ratio = mismatch_n / total_n if total_n > 0 else np.nan

# 平均差異（用 window slope）
mean_abs_diff = df["slope_diff_window"].abs().mean()
median_abs_diff = df["slope_diff_window"].abs().median()


# =========================================================
# 8. 輸出
# =========================================================
df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

print("完成")
print("CSV:", OUT_CSV)

print("\n=== 核心評估指標 ===")
print(f"ok_ratio: {ok_ratio:.3f}")
print(f"mismatch_ratio: {mismatch_ratio:.3f}")
print(f"mean_abs_slope_diff: {mean_abs_diff:.3f}")
print(f"median_abs_slope_diff: {median_abs_diff:.3f}")

print("\n=== gpx_quality_flag ===")
print(df["gpx_quality_flag"].value_counts())