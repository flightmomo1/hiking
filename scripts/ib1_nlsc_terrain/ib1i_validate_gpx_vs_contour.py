from pathlib import Path
import numpy as np
import pandas as pd


# =========================================================
# 設定
# =========================================================
# MERGED_FP = Path("ib1h_contour_window_profile_output/qixing_contour_window_profile_merged.csv")

# OUT_DIR = Path("ib1i_validation_output")
# OUT_DIR.mkdir(parents=True, exist_ok=True)

# OUT_CSV = OUT_DIR / "qixing_gpx_vs_contour_validation.csv"

CASE_ID = "juansi_waterfall_fitcsv_20260503"
CASE_NAME = "絹絲瀑布 FIT CSV 20260503"

MERGED_FP = (
    Path("outputs")
    / "ib1e_route_profile_contour_window_terrain"
    / CASE_ID
    / f"{CASE_ID}_route_profile_contour_window_terrain_enriched.csv"
)

OUT_DIR = Path("outputs") / "ib1i_gpx_vs_contour_validation" / CASE_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_CSV = OUT_DIR / f"{CASE_ID}_gpx_vs_contour_validation.csv"
OUT_SUMMARY_TXT = OUT_DIR / f"{CASE_ID}_gpx_vs_contour_validation_summary.txt"

# =========================================================
# 讀資料
# =========================================================
if not MERGED_FP.exists():
    raise FileNotFoundError(MERGED_FP)

df = pd.read_csv(MERGED_FP)

def first_existing_col(df, candidates):
    for col in candidates:
        if col in df.columns:
            return col
    return None


DIST_COL = first_existing_col(
    df,
    ["dist_m", "route_dist_m", "dist_mid", "distance_m"],
)

GPX_ELE_COL = first_existing_col(
    df,
    ["ele_smooth", "ele", "ele_gpx_m", "elevation", "altitude"],
)

CONTOUR_ELEV_RANGE_COL = first_existing_col(
    df,
    [
        "terrain_elev_range",
        "elev_range_nlsc_window",
        "elev_range",
        "elev_range_m",
    ],
)

CONTOUR_SLOPE_BAND_COL = first_existing_col(
    df,
    [
        "terrain_slope_band_window",
        "slope_band_window_nlsc",
        "slope_band_window",
        "dominant_slope_band",
    ],
)

CONTOUR_SLOPE_COL = first_existing_col(
    df,
    [
        "slope_window_nlsc",
        "terrain_slope_window",
        "slope_contour_window",
    ],
)

missing = {
    "distance": DIST_COL,
    "contour_elev_range": CONTOUR_ELEV_RANGE_COL,
    "contour_slope_band": CONTOUR_SLOPE_BAND_COL,
}

missing_keys = [k for k, v in missing.items() if v is None]

if missing_keys:
    raise ValueError(
        f"缺少必要欄位類型: {missing_keys}\n"
        f"目前欄位: {list(df.columns)}"
    )

HAS_GPX_ELEVATION = GPX_ELE_COL is not None


# =========================================================
# 1. 計算 GPX / NLSC contour window slope
# =========================================================
df = df.sort_values(DIST_COL).reset_index(drop=True)
df = df.copy()

# =========================================================
# Window setting
# =========================================================
# route profile 目前通常是 1m sample interval。
# 不要硬寫 WINDOW_N = 5，否則 1m profile 只會取約 5m 高程差，
# 再除以 100m，會把 GPX slope 壓得過小。
WINDOW_LEN = 100.0

dist_series = pd.to_numeric(df[DIST_COL], errors="coerce")
sample_interval_m = dist_series.diff().median()

if pd.isna(sample_interval_m) or sample_interval_m <= 0:
    sample_interval_m = 1.0

WINDOW_N = int(round(WINDOW_LEN / sample_interval_m)) + 1

# rolling center window 建議用奇數，中心點才穩定
if WINDOW_N % 2 == 0:
    WINDOW_N += 1

MIN_PERIODS = max(5, int(WINDOW_N * 0.5))

print("sample_interval_m:", sample_interval_m)
print("WINDOW_LEN:", WINDOW_LEN)
print("WINDOW_N:", WINDOW_N)
print("MIN_PERIODS:", MIN_PERIODS)

# ---------------------------------------------------------
# 1a. GPX / FIT elevation window slope
# ---------------------------------------------------------
if HAS_GPX_ELEVATION:
    df[GPX_ELE_COL] = pd.to_numeric(df[GPX_ELE_COL], errors="coerce")

    df["elev_min_gpx_window"] = df[GPX_ELE_COL].rolling(
        WINDOW_N, center=True, min_periods=3
    ).min()

    df["elev_max_gpx_window"] = df[GPX_ELE_COL].rolling(
        WINDOW_N, center=True, min_periods=3
    ).max()

    df["elev_range_gpx_window"] = (
        df["elev_max_gpx_window"] - df["elev_min_gpx_window"]
    )

    df["slope_gpx_window"] = df["elev_range_gpx_window"] / WINDOW_LEN
else:
    df["elev_min_gpx_window"] = np.nan
    df["elev_max_gpx_window"] = np.nan
    df["elev_range_gpx_window"] = np.nan
    df["slope_gpx_window"] = np.nan


# ---------------------------------------------------------
# 1b. NLSC contour window slope
# ---------------------------------------------------------
if CONTOUR_SLOPE_COL is not None:
    df["slope_contour_window"] = pd.to_numeric(
        df[CONTOUR_SLOPE_COL],
        errors="coerce",
    )
else:
    df[CONTOUR_ELEV_RANGE_COL] = pd.to_numeric(
        df[CONTOUR_ELEV_RANGE_COL],
        errors="coerce",
    )

    df["slope_contour_window"] = df[CONTOUR_ELEV_RANGE_COL] / WINDOW_LEN


# ---------------------------------------------------------
# 1c. Smooth
# ---------------------------------------------------------
df["slope_gpx_window_smooth"] = (
    df["slope_gpx_window"]
    .rolling(3, center=True, min_periods=2)
    .mean()
)

df["slope_contour_window_smooth"] = (
    df["slope_contour_window"]
    .rolling(3, center=True, min_periods=2)
    .mean()
)


# =========================================================
# 2. GPX / NLSC consistency metrics
# =========================================================
if HAS_GPX_ELEVATION:
    valid = df[
        [
            "slope_gpx_window_smooth",
            "slope_contour_window_smooth",
        ]
    ].dropna()

    if len(valid) > 10:
        corr = np.corrcoef(
            valid["slope_gpx_window_smooth"].abs(),
            valid["slope_contour_window_smooth"].abs(),
        )[0, 1]
    else:
        corr = np.nan

    df["slope_diff_window"] = (
        df["slope_gpx_window_smooth"]
        - df["slope_contour_window_smooth"]
    )

    THRESH_DIFF = 0.25

    df["gpx_quality_flag"] = np.where(
        df["slope_diff_window"].abs() > THRESH_DIFF,
        "mismatch",
        "ok",
    )

else:
    corr = np.nan
    df["slope_diff_window"] = np.nan
    df["gpx_quality_flag"] = "no_gpx_elevation"


# contour 不是絕對高程，不能估 elevation bias
bias_est = np.nan



# =========================================================
# 7. 統計指標（取代 correlation 為主判讀）
# =========================================================
total_n = len(df)

ok_n = (df["gpx_quality_flag"] == "ok").sum()
mismatch_n = (df["gpx_quality_flag"] == "mismatch").sum()

if HAS_GPX_ELEVATION:
    ok_ratio = ok_n / total_n if total_n > 0 else np.nan
    mismatch_ratio = mismatch_n / total_n if total_n > 0 else np.nan
    mean_abs_diff = df["slope_diff_window"].abs().mean()
    median_abs_diff = df["slope_diff_window"].abs().median()
else:
    ok_ratio = np.nan
    mismatch_ratio = np.nan
    mean_abs_diff = np.nan
    median_abs_diff = np.nan


summary_lines = [
    "ib1i GPX vs NLSC contour validation",
    f"case_id: {CASE_ID}",
    f"case_name: {CASE_NAME}",
    "",
    f"input: {MERGED_FP}",
    f"output_csv: {OUT_CSV}",
    "",
    f"distance_col: {DIST_COL}",
    f"gpx_elevation_col: {GPX_ELE_COL}",
    f"contour_elev_range_col: {CONTOUR_ELEV_RANGE_COL}",
    f"contour_slope_col: {CONTOUR_SLOPE_COL}",
    f"contour_slope_band_col: {CONTOUR_SLOPE_BAND_COL}",
    f"has_gpx_elevation: {HAS_GPX_ELEVATION}",
    "",
    f"rows: {len(df)}",
    f"ok_ratio: {ok_ratio:.3f}" if HAS_GPX_ELEVATION else "ok_ratio: NA",
    f"mismatch_ratio: {mismatch_ratio:.3f}" if HAS_GPX_ELEVATION else "mismatch_ratio: NA",
    f"mean_abs_slope_diff: {mean_abs_diff:.3f}" if HAS_GPX_ELEVATION else "mean_abs_slope_diff: NA",
    f"median_abs_slope_diff: {median_abs_diff:.3f}" if HAS_GPX_ELEVATION else "median_abs_slope_diff: NA",
    f"corr_abs_slope: {corr:.3f}" if HAS_GPX_ELEVATION and not np.isnan(corr) else "corr_abs_slope: NA",
    "",
    "gpx_quality_flag counts:",
    str(df["gpx_quality_flag"].value_counts(dropna=False)),
]

# =========================================================
# 8. 輸出
# =========================================================
df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

OUT_SUMMARY_TXT.write_text("\n".join(summary_lines), encoding="utf-8")

print("完成")
print("CSV:", OUT_CSV)
print("SUMMARY:", OUT_SUMMARY_TXT)

print("\n=== 欄位偵測 ===")
print("distance_col:", DIST_COL)
print("gpx_elevation_col:", GPX_ELE_COL)
print("contour_elev_range_col:", CONTOUR_ELEV_RANGE_COL)
print("contour_slope_band_col:", CONTOUR_SLOPE_BAND_COL)
print("has_gpx_elevation:", HAS_GPX_ELEVATION)

print("\n=== 核心評估指標 ===")
if HAS_GPX_ELEVATION:
    print(f"ok_ratio: {ok_ratio:.3f}")
    print(f"mismatch_ratio: {mismatch_ratio:.3f}")
    print(f"mean_abs_slope_diff: {mean_abs_diff:.3f}")
    print(f"median_abs_slope_diff: {median_abs_diff:.3f}")
    print(f"corr_abs_slope: {corr:.3f}" if not np.isnan(corr) else "corr_abs_slope: NA")
else:
    print("無 GPX/FIT elevation 欄位，已降級為 NLSC contour profile QA。")

print("\n=== gpx_quality_flag ===")
print(df["gpx_quality_flag"].value_counts(dropna=False))