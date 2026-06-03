from pathlib import Path
import argparse

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


"""
ib3b_plot_mapmatched_activity_profile.py

定位：
- ib3a_mapmatch_highfreq_activity.py 的 QA 視覺化腳本
- 用於檢查 FIT/GPX 活動軌跡貼回 route distance axis 後的品質
- 目前正式 case：
  juansi_waterfall_fitcsv_20260503

輸入：
1. ib3a core mapmatched activity:
   outputs/ib3a_mapmatched_activity/<CASE_ID>/<CASE_ID>_activity_mapmatched_core.csv

2. optional ib1i GPX vs NLSC contour validation:
   outputs/ib1i_gpx_vs_contour_validation/<CASE_ID>/<CASE_ID>_gpx_vs_contour_validation.csv

輸出：
1. outputs/ib3b_mapmatched_activity_profile/<CASE_ID>/<CASE_ID>_mapmatched_activity_profile.png
2. outputs/ib3b_mapmatched_activity_profile/<CASE_ID>/<CASE_ID>_mapmatched_activity_profile_plot_data.csv
3. outputs/ib3b_mapmatched_activity_profile/<CASE_ID>/<CASE_ID>_mapmatched_activity_profile_summary.txt

說明：
- 預設讀取 *_activity_mapmatched_core.csv，避免 terminal_off_route 污染主路線活動剖面。
- 若 ib1i validation CSV 存在，會依 route_dist_m / dist_m 做 nearest merge，
  加入 route profile elevation / NLSC terrain window / gpx_quality_flag 作為 QA 背景參考。
"""


# =========================================================
# 0a. CLI arguments
# =========================================================
def parse_cli_args():
    """
    保留原本直接執行單一 case 的用法。
    若由 batch runner 呼叫，則可用 CLI 覆蓋 activity / output 設定。
    """
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--case-id", default=None)
    parser.add_argument("--activity-id", default=None)
    parser.add_argument("--user-id", default=None)
    parser.add_argument("--activity-core-csv", default=None)
    parser.add_argument("--out-dir", default=None)
    return parser.parse_args()


CLI_ARGS = parse_cli_args()


# =========================================================
# 0. Case / path settings
# =========================================================
CASE_ID = CLI_ARGS.case_id or "juansi_waterfall_fitcsv_20260503"
CASE_NAME = "絹絲瀑布 FIT CSV 20260503"
MODEL_VERSION = "prototype_A_terrain_dominant_v1"
ACTIVITY_ID = CLI_ARGS.activity_id or CASE_ID
USER_ID = CLI_ARGS.user_id or ""
OUTPUT_PREFIX = ACTIVITY_ID if CLI_ARGS.activity_id else CASE_ID

PROJECT_ROOT = Path(r"C:\mountain_work\115_osm")

INPUT_CSV = (
    Path(CLI_ARGS.activity_core_csv)
    if CLI_ARGS.activity_core_csv
    else (
        PROJECT_ROOT
        / "outputs"
        / "ib3a_mapmatched_activity"
        / CASE_ID
        / f"{CASE_ID}_activity_mapmatched_core.csv"
    )
)

IB1I_VALIDATION_CSV = (
    PROJECT_ROOT
    / "outputs"
    / "ib1i_gpx_vs_contour_validation"
    / CASE_ID
    / f"{CASE_ID}_gpx_vs_contour_validation.csv"
)

OUT_DIR = (
    Path(CLI_ARGS.out_dir)
    if CLI_ARGS.out_dir
    else PROJECT_ROOT / "outputs" / "ib3b_mapmatched_activity_profile" / CASE_ID
)
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_PNG = OUT_DIR / f"{OUTPUT_PREFIX}_mapmatched_activity_profile.png"
OUT_CSV = OUT_DIR / f"{OUTPUT_PREFIX}_mapmatched_activity_profile_plot_data.csv"
OUT_SUMMARY_TXT = OUT_DIR / f"{OUTPUT_PREFIX}_mapmatched_activity_profile_summary.txt"


# =========================================================
# 1. Utility
# =========================================================
def first_existing_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def read_csv_required(fp: Path, label: str) -> pd.DataFrame:
    if not fp.exists():
        raise FileNotFoundError(f"找不到 {label}: {fp.resolve()}")
    df = pd.read_csv(fp, low_memory=False)
    if df.empty:
        raise ValueError(f"{label} 為空: {fp.resolve()}")
    return df


def to_bool_series(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    return s.astype(str).str.lower().isin(["true", "1", "yes"])


def first_nonempty_value(df: pd.DataFrame, col: str, default="unknown"):
    if col in df.columns and df[col].notna().any():
        return df[col].dropna().iloc[0]
    return default


def first_float_value(df: pd.DataFrame, col: str, default=np.nan):
    if col in df.columns and df[col].notna().any():
        return float(pd.to_numeric(df[col], errors="coerce").dropna().iloc[0])
    return default


def safe_fmt(value, digits=3, default="NA"):
    try:
        if pd.isna(value):
            return default
        return f"{float(value):.{digits}f}"
    except Exception:
        return default


# =========================================================
# 2. Read activity core
# =========================================================
df = read_csv_required(INPUT_CSV, "ib3a core mapmatched activity CSV")

required_cols = [
    "route_dist_m",
    "raw_ele_m",
    "forward_speed_route_mps",
    "offset_to_mainline_m",
    "match_quality",
]

missing = [col for col in required_cols if col not in df.columns]
if missing:
    raise ValueError(
        f"activity CSV 缺少必要欄位：{missing}\n目前欄位：{list(df.columns)}"
    )

df["route_dist_m"] = pd.to_numeric(df["route_dist_m"], errors="coerce")
df["raw_ele_m"] = pd.to_numeric(df["raw_ele_m"], errors="coerce")
df["forward_speed_route_mps"] = pd.to_numeric(
    df["forward_speed_route_mps"], errors="coerce"
)
df["offset_to_mainline_m"] = pd.to_numeric(
    df["offset_to_mainline_m"], errors="coerce"
)

if "raw_hr_bpm" in df.columns:
    df["raw_hr_bpm"] = pd.to_numeric(df["raw_hr_bpm"], errors="coerce")

if "raw_speed_mps" in df.columns:
    df["raw_speed_mps"] = pd.to_numeric(df["raw_speed_mps"], errors="coerce")

if "time" in df.columns:
    df["time"] = pd.to_datetime(df["time"], errors="coerce", utc=True)
else:
    df["time"] = pd.NaT

for bool_col in [
    "is_stationary",
    "speed_capped",
    "backtrack_constrained",
    "is_off_route",
]:
    if bool_col not in df.columns:
        df[bool_col] = False
    else:
        df[bool_col] = to_bool_series(df[bool_col])

if "analysis_scope" not in df.columns:
    df["analysis_scope"] = "route_core"

df = df.dropna(subset=["route_dist_m"]).sort_values("route_dist_m").reset_index(drop=True)
df = df.copy()

# =========================================================
# Activity-level QA from ib3a
# =========================================================
activity_quality_group = str(
    first_nonempty_value(df, "activity_quality_group", "unknown")
)
route_coverage_group = str(
    first_nonempty_value(df, "route_coverage_group", "unknown")
)
speed_quality_group = str(
    first_nonempty_value(df, "speed_quality_group", "unknown")
)
hr_quality_group = str(
    first_nonempty_value(df, "hr_quality_group", "unknown")
)

route_dist_min_m = first_float_value(
    df,
    "route_dist_min_m",
    float(df["route_dist_m"].min()),
)
route_dist_max_m = first_float_value(
    df,
    "route_dist_max_m",
    float(df["route_dist_m"].max()),
)
route_coverage_ratio = first_float_value(
    df,
    "route_coverage_ratio",
    np.nan,
)
speed_capped_ratio = first_float_value(
    df,
    "speed_capped_ratio",
    np.nan,
)
hr_valid_ratio = first_float_value(
    df,
    "hr_valid_ratio",
    np.nan,
)

route_length_m = first_float_value(
    df,
    "route_length_m",
    float(df["route_dist_m"].max()),
)

# =========================================================
# Speed display columns
# =========================================================
# raw_speed_mps:
#   FIT device speed, used as primary walking speed display.
# forward_speed_route_mps:
#   route-axis derived speed, useful for ETA / route progress QA.
# speed_capped:
#   QA flag. When True, route-axis speed was capped by MAX_SPEED_MPS.

if "raw_speed_mps" in df.columns:
    df["walking_speed_mps"] = pd.to_numeric(
        df["raw_speed_mps"],
        errors="coerce",
    )
else:
    df["walking_speed_mps"] = pd.to_numeric(
        df["forward_speed_route_mps"],
        errors="coerce",
    )

df["route_speed_mps"] = pd.to_numeric(
    df["forward_speed_route_mps"],
    errors="coerce",
)

# route speed for plotting: hide capped values so the line does not falsely stick to 3.0
df["route_speed_mps_for_plot"] = df["route_speed_mps"]

if "speed_capped" in df.columns:
    speed_capped_bool = to_bool_series(df["speed_capped"])
    df.loc[speed_capped_bool, "route_speed_mps_for_plot"] = np.nan
else:
    speed_capped_bool = pd.Series(False, index=df.index)

df["walking_speed_mps_smooth"] = (
    df["walking_speed_mps"]
    .rolling(15, center=True, min_periods=3)
    .median()
)

df["route_speed_mps_smooth"] = (
    df["route_speed_mps_for_plot"]
    .rolling(15, center=True, min_periods=3)
    .median()
)


# =========================================================
# 3. Optional merge with ib1i / route terrain QA
# =========================================================
ib1i_merged = False

if IB1I_VALIDATION_CSV.exists():
    val = pd.read_csv(IB1I_VALIDATION_CSV, low_memory=False)

    dist_col = first_existing_col(val, ["dist_m", "route_dist_m", "profile_dist_m"])
    profile_ele_col = first_existing_col(val, ["ele_smooth", "ele_gpx_m", "ele"])
    nlsc_slope_col = first_existing_col(val, ["slope_window_nlsc", "slope_contour_window"])
    nlsc_band_col = first_existing_col(val, ["slope_band_window_nlsc", "terrain_slope_band_window"])
    nlsc_range_col = first_existing_col(val, ["elev_range_nlsc_window", "terrain_elev_range"])
    gpx_quality_col = first_existing_col(val, ["gpx_quality_flag"])

    keep_cols = [dist_col]
    rename_map = {}

    if profile_ele_col:
        keep_cols.append(profile_ele_col)
        rename_map[profile_ele_col] = "route_profile_ele_m"

    if nlsc_slope_col:
        keep_cols.append(nlsc_slope_col)
        rename_map[nlsc_slope_col] = "route_nlsc_slope_window"

    if nlsc_band_col:
        keep_cols.append(nlsc_band_col)
        rename_map[nlsc_band_col] = "route_nlsc_slope_band"

    if nlsc_range_col:
        keep_cols.append(nlsc_range_col)
        rename_map[nlsc_range_col] = "route_nlsc_elev_range_window"

    if gpx_quality_col:
        keep_cols.append(gpx_quality_col)
        rename_map[gpx_quality_col] = "route_gpx_quality_flag"

    keep_cols = [c for c in keep_cols if c is not None]

    if dist_col and len(keep_cols) >= 2:
        terrain_small = val[keep_cols].copy()
        terrain_small[dist_col] = pd.to_numeric(terrain_small[dist_col], errors="coerce")
        terrain_small = (
            terrain_small
            .dropna(subset=[dist_col])
            .sort_values(dist_col)
            .rename(columns=rename_map)
        )

        df = pd.merge_asof(
            df.sort_values("route_dist_m"),
            terrain_small,
            left_on="route_dist_m",
            right_on=dist_col,
            direction="nearest",
        )

        df["route_profile_dist_diff_m"] = df["route_dist_m"] - df[dist_col]
        ib1i_merged = True

        print("\n=== ib1i validation merged ===")
        print("ib1i:", IB1I_VALIDATION_CSV.resolve())
        print("dist_col:", dist_col)
        print(df["route_profile_dist_diff_m"].describe())
    else:
        print("警告：ib1i validation CSV 欄位不足，略過 merge")
else:
    print(f"警告：找不到 ib1i validation CSV，圖中只顯示活動資料：{IB1I_VALIDATION_CSV}")


# =========================================================
# 4. Derived plotting fields
# =========================================================
# df["forward_speed_smooth_mps"] = (
#     df["forward_speed_route_mps"]
#     .rolling(window=31, center=True, min_periods=5)
#     .median()
# )

if "raw_hr_bpm" in df.columns:
    df["raw_hr_smooth_bpm"] = (
        df["raw_hr_bpm"]
        .rolling(window=31, center=True, min_periods=5)
        .median()
    )


# =========================================================
# 5. Plot
# =========================================================
has_hr = "raw_hr_bpm" in df.columns and df["raw_hr_bpm"].notna().any()
nrows = 4 if has_hr else 3

fig, axes = plt.subplots(
    nrows=nrows,
    ncols=1,
    figsize=(16, 11 if has_hr else 9),
    sharex=True,
    gridspec_kw={"height_ratios": [2.2, 1.5, 1.3, 1.2] if has_hr else [2.2, 1.5, 1.2]},
)

if has_hr:
    ax_ele, ax_speed, ax_hr, ax_offset = axes
else:
    ax_ele, ax_speed, ax_offset = axes
    ax_hr = None

# ---------------------------------------------------------
# QA background shading for partial route
# ---------------------------------------------------------
plot_axes = [ax_ele, ax_speed, ax_offset]
if has_hr and ax_hr is not None:
    plot_axes.insert(2, ax_hr)

if route_coverage_group == "partial_route":
    for ax in plot_axes:
        if route_dist_min_m > 0:
            ax.axvspan(
                0,
                route_dist_min_m,
                alpha=0.12,
                hatch="//",
                label="not covered by activity" if ax is ax_ele else None,
            )

        if not pd.isna(route_length_m) and route_dist_max_m < route_length_m:
            ax.axvspan(
                route_dist_max_m,
                route_length_m,
                alpha=0.12,
                hatch="\\\\",
            )

        ax.axvline(
            route_dist_min_m,
            linestyle=":",
            linewidth=1.2,
            alpha=0.8,
        )

        ax.axvline(
            route_dist_max_m,
            linestyle=":",
            linewidth=1.2,
            alpha=0.8,
        )

# ---------------------------------------------------------
# 5a. Elevation
# ---------------------------------------------------------
ax_ele.plot(
    df["route_dist_m"],
    df["raw_ele_m"],
    linewidth=1.2,
    label="activity raw_ele_m",
)

if "route_profile_ele_m" in df.columns:
    ax_ele.plot(
        df["route_dist_m"],
        df["route_profile_ele_m"],
        linewidth=1.2,
        linestyle="--",
        label="route profile ele_smooth / ib1i",
    )

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
# 5b. Walking speed
# ---------------------------------------------------------
# walking_speed_mps:
#   primary display speed, usually from FIT raw_speed_mps.
# route_speed_mps_smooth:
#   route-axis derived speed, with speed_capped values hidden for plotting.
# speed_capped:
#   QA marker only. It should not be interpreted as real walking speed.

ax_speed.plot(
    df["route_dist_m"],
    df["walking_speed_mps"],
    linewidth=0.7,
    alpha=0.35,
    label="walking speed raw_speed_mps",
)

ax_speed.plot(
    df["route_dist_m"],
    df["walking_speed_mps_smooth"],
    linewidth=1.8,
    label="walking speed smooth",
)

ax_speed.plot(
    df["route_dist_m"],
    df["route_speed_mps_smooth"],
    linewidth=1.2,
    linestyle="--",
    alpha=0.8,
    label="route-axis speed smooth, capped removed",
)

speed_capped_df = df[speed_capped_bool].copy()
if not speed_capped_df.empty:
    ax_speed.scatter(
        speed_capped_df["route_dist_m"],
        speed_capped_df["walking_speed_mps"],
        s=18,
        marker="x",
        label="speed_capped QA",
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
# 5c. Heart rate
# ---------------------------------------------------------
if has_hr and ax_hr is not None:
    ax_hr.plot(
        df["route_dist_m"],
        df["raw_hr_bpm"],
        linewidth=0.7,
        alpha=0.35,
        label="raw_hr_bpm",
    )

    ax_hr.plot(
        df["route_dist_m"],
        df["raw_hr_smooth_bpm"],
        linewidth=1.6,
        label="raw_hr_bpm smooth",
    )

    ax_hr.set_ylabel("HR (bpm)")
    ax_hr.grid(True, alpha=0.25)
    ax_hr.legend(loc="upper right", fontsize=8)


# ---------------------------------------------------------
# 5d. Offset / match quality
# ---------------------------------------------------------
ax_offset.plot(
    df["route_dist_m"],
    df["offset_to_mainline_m"],
    linewidth=0.9,
    label="offset_to_mainline_m",
)

# 不指定顏色，避免 matplotlib backend / style 不一致；用 marker 區分。
QUALITY_MARKERS = {
    "good": ".",
    "acceptable": "o",
    "fair": "o",
    "weak": "^",
    "constrained": "x",
    "poor": "s",
    "off_route": "v",
}

for quality, marker in QUALITY_MARKERS.items():
    qdf = df[df["match_quality"].astype(str) == quality]
    if qdf.empty:
        continue

    ax_offset.scatter(
        qdf["route_dist_m"],
        qdf["offset_to_mainline_m"],
        s=12,
        marker=marker,
        label=f"match_quality={quality}",
    )

backtrack_df = df[df["backtrack_constrained"].astype(bool)]
if not backtrack_df.empty:
    ax_offset.scatter(
        backtrack_df["route_dist_m"],
        backtrack_df["offset_to_mainline_m"],
        s=28,
        marker="^",
        label="backtrack_constrained",
    )

ax_offset.axhline(10, linestyle="--", linewidth=1.0, alpha=0.4, label="10m offset")
ax_offset.axhline(25, linestyle="--", linewidth=1.0, alpha=0.4, label="25m offset")
ax_offset.axhline(50, linestyle="--", linewidth=1.0, alpha=0.4, label="50m off-route threshold")

ax_offset.set_ylabel("Offset (m)")
ax_offset.set_xlabel("Route distance (m)")
ax_offset.grid(True, alpha=0.25)
ax_offset.legend(loc="upper right", fontsize=7)

qa_text = "\n".join(
    [
        f"activity: {ACTIVITY_ID}",
        f"user: {USER_ID}",
        f"activity QA: {activity_quality_group}",
        f"coverage: {route_coverage_group}",
        f"coverage ratio: {safe_fmt(route_coverage_ratio, 3)}",
        f"route range: {safe_fmt(route_dist_min_m, 0)}-{safe_fmt(route_dist_max_m, 0)} m",
        f"speed QA: {speed_quality_group}",
        f"speed capped: {safe_fmt(speed_capped_ratio, 3)}",
        f"HR QA: {hr_quality_group}",
        f"HR valid: {safe_fmt(hr_valid_ratio, 3)}",
    ]
)

fig.text(
    0.012,
    0.955,
    qa_text,
    ha="left",
    va="top",
    fontsize=8,
    bbox=dict(boxstyle="round", alpha=0.12),
)

plt.suptitle(
    f"{ACTIVITY_ID} mapmatched activity profile | "
    f"{activity_quality_group} | {route_coverage_group} | "
    f"speed={speed_quality_group} | HR={hr_quality_group}\n"
    "Elevation / Walking Speed / Heart Rate / Mainline Offset",
    fontsize=14,
)

plt.tight_layout(rect=[0, 0, 1, 0.90])
plt.savefig(OUT_PNG, dpi=220)
plt.close()


# =========================================================
# 6. Output plot data
# =========================================================
plot_cols = [
    "activity_idx",
    "time",
    "analysis_scope",
    "activity_id",
    "user_id",
    "activity_quality_group",
    "route_coverage_group",
    "route_coverage_ratio",
    "route_dist_min_m",
    "route_dist_max_m",
    "speed_quality_group",
    "speed_capped_ratio",
    "hr_quality_group",
    "hr_valid_ratio",
    "route_dist_m",
    "raw_ele_m",
    "route_profile_ele_m",
    "route_nlsc_slope_window",
    "route_nlsc_slope_band",
    "route_nlsc_elev_range_window",
    "route_gpx_quality_flag",
    "route_profile_dist_diff_m",
    "raw_hr_bpm",
    "raw_hr_smooth_bpm",
    "raw_speed_mps",
    "walking_speed_mps",
    "walking_speed_mps_smooth",
    "route_speed_mps",
    "route_speed_mps_for_plot",
    "route_speed_mps_smooth",
    "forward_delta_route_dist_m",
    "forward_speed_route_mps",
    # "forward_speed_smooth_mps",
    "offset_to_mainline_m",
    "match_quality",
    "is_stationary",
    "speed_capped",
    "backtrack_constrained",
    "is_off_route",
    "raw_lat",
    "raw_lon",
    "matched_lat",
    "matched_lon",
]

plot_cols = [col for col in plot_cols if col in df.columns]
plot_df = df[plot_cols].copy()

if "time" in plot_df.columns:
    plot_df["time"] = plot_df["time"].astype(str)

plot_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")


# =========================================================
# 7. Summary
# =========================================================
summary_lines = [
    "ib3b mapmatched activity profile",
    f"case_id: {CASE_ID}",
    f"case_name: {CASE_NAME}",
    f"activity_id: {ACTIVITY_ID}",
    f"user_id: {USER_ID}",
    f"model_version: {MODEL_VERSION}",
    "",
    f"input_csv: {INPUT_CSV}",
    f"ib1i_validation_csv: {IB1I_VALIDATION_CSV}",
    f"ib1i_merged: {ib1i_merged}",
    f"output_png: {OUT_PNG}",
    f"output_csv: {OUT_CSV}",
    "",
    f"rows: {len(df)}",
    f"route_dist_min_m: {df['route_dist_m'].min():.2f}",
    f"route_dist_max_m: {df['route_dist_m'].max():.2f}",
    "",
    "activity_level_qa:",
    f"  activity_quality_group: {activity_quality_group}",
    f"  route_coverage_group: {route_coverage_group}",
    f"  route_coverage_ratio: {safe_fmt(route_coverage_ratio, 3)}",
    f"  route_dist_min_m: {safe_fmt(route_dist_min_m, 2)}",
    f"  route_dist_max_m: {safe_fmt(route_dist_max_m, 2)}",
    f"  speed_quality_group: {speed_quality_group}",
    f"  speed_capped_ratio: {safe_fmt(speed_capped_ratio, 3)}",
    f"  hr_quality_group: {hr_quality_group}",
    f"  hr_valid_ratio: {safe_fmt(hr_valid_ratio, 3)}",
    "",
    "analysis_scope:",
    str(df["analysis_scope"].value_counts(dropna=False)),
    "",
    "match_quality:",
    str(df["match_quality"].value_counts(dropna=False)),
    "",
    "offset_to_mainline_m:",
    str(df["offset_to_mainline_m"].describe()),
    "",
    "walking_speed_mps:",
    str(df["walking_speed_mps"].describe()),
    "",
    "route_speed_mps_for_plot:",
    str(df["route_speed_mps_for_plot"].describe()),
    "",
    "forward_speed_route_mps:",
    str(df["forward_speed_route_mps"].describe()),
    "",
    "is_stationary:",
    str(df["is_stationary"].value_counts(dropna=False)),
]

if has_hr:
    summary_lines.extend(
        [
            "",
            "raw_hr_bpm:",
            str(df["raw_hr_bpm"].describe()),
        ]
    )

if "route_gpx_quality_flag" in df.columns:
    summary_lines.extend(
        [
            "",
            "route_gpx_quality_flag:",
            str(df["route_gpx_quality_flag"].value_counts(dropna=False)),
        ]
    )

OUT_SUMMARY_TXT.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")


print("完成！")
print("PNG:", OUT_PNG.resolve())
print("plot CSV:", OUT_CSV.resolve())
print("summary:", OUT_SUMMARY_TXT.resolve())

print("\n=== analysis_scope ===")
print(df["analysis_scope"].value_counts(dropna=False))

print("\n=== activity_level_qa ===")
print("activity_quality_group:", activity_quality_group)
print("route_coverage_group:", route_coverage_group)
print("route_coverage_ratio:", safe_fmt(route_coverage_ratio, 3))
print("route_dist_min_m:", safe_fmt(route_dist_min_m, 2))
print("route_dist_max_m:", safe_fmt(route_dist_max_m, 2))
print("speed_quality_group:", speed_quality_group)
print("speed_capped_ratio:", safe_fmt(speed_capped_ratio, 3))
print("hr_quality_group:", hr_quality_group)
print("hr_valid_ratio:", safe_fmt(hr_valid_ratio, 3))

print("\n=== match_quality ===")
print(df["match_quality"].value_counts(dropna=False))

print("\n=== offset_to_mainline_m ===")
print(df["offset_to_mainline_m"].describe())

print("\n=== walking_speed_mps ===")
print(df["walking_speed_mps"].describe())

print("\n=== route_speed_mps_for_plot ===")
print(df["route_speed_mps_for_plot"].describe())

print("\n=== forward_speed_route_mps ===")
print(df["forward_speed_route_mps"].describe())

if has_hr:
    print("\n=== raw_hr_bpm ===")
    print(df["raw_hr_bpm"].describe())

print("\n=== is_stationary ===")
print(df["is_stationary"].value_counts(dropna=False))

print("\n=== constraints ===")
for col in ["speed_capped", "backtrack_constrained", "is_off_route"]:
    if col in df.columns:
        print(col)
        print(df[col].value_counts(dropna=False))
