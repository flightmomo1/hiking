# -*- coding: utf-8 -*-
from pathlib import Path
import os

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.patches import Patch


# =========================================================
# 0. Matplotlib font
# =========================================================
mpl.rcParams["font.sans-serif"] = [
    "PingFang TC",
    "Heiti TC",
    "Arial Unicode MS",
    "Noto Sans CJK TC",
    "DejaVu Sans",
]
mpl.rcParams["axes.unicode_minus"] = False


# =========================================================
# A. Input / Output
# =========================================================
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent

SCENARIO_NAME = os.environ.get("SCENARIO_NAME", "actual_gpx_9stations")

ACTIVITY_POINTS_CSV = BASE_DIR / "ib4_activity_output" / "qixing_activity_track_points.csv"

ENV_BASE_DIR = BASE_DIR / "ib3_environment_output"
ENV_DIR = ENV_BASE_DIR / SCENARIO_NAME

RISK_ROUTE_CSV = ENV_DIR / "qixing_environment_adjusted_risk.csv"

OUT_BASE_DIR = BASE_DIR / "ib4_activity_output"
OUT_DIR = OUT_BASE_DIR / SCENARIO_NAME

OUT_OVERLAY_POINTS_CSV = OUT_DIR / "qixing_activity_risk_overlay_points.csv"
OUT_OVERLAY_SUMMARY_CSV = OUT_DIR / "qixing_activity_risk_overlay_summary.csv"
OUT_OVERLAY_PNG = OUT_DIR / "qixing_activity_risk_overlay_profile.png"


# =========================================================
# B. Config
# =========================================================
DPI = 220

MAX_MATCH_DIST_M = 80.0
SPEED_ROLLING_WINDOW = 9

RISK_COLORS = {
    "low": "#4CAF50",
    "moderate": "#F2C037",
    "high": "#F57C00",
    "very_high": "#D93A3A",
    "unknown": "#BDBDBD",
}

RISK_ORDER = ["low", "moderate", "high", "very_high", "unknown"]


# =========================================================
# C. Utility
# =========================================================
def ensure_exists(fp: Path):
    if not fp.exists():
        raise FileNotFoundError(f"找不到檔案：{fp.resolve()}")


def normalize_columns(df: pd.DataFrame):
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    return out


def to_numeric_safe(df: pd.DataFrame, cols):
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def find_first_existing(df: pd.DataFrame, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def find_distance_col(df: pd.DataFrame):
    col = find_first_existing(
        df,
        [
            "dist_m",
            "cumdist_m",
            "distance_m",
            "cum_dist_m",
            "distance",
        ],
    )
    if col is None:
        raise KeyError(f"找不到距離欄位，現有欄位：{list(df.columns)}")
    return col


def normalize_band(v):
    if pd.isna(v):
        return "unknown"
    s = str(v).strip().lower()
    return s if s in RISK_COLORS else "unknown"


def make_gdf_from_latlon(df: pd.DataFrame, lat_col="lat", lon_col="lon"):
    if lat_col not in df.columns or lon_col not in df.columns:
        raise KeyError(f"缺少經緯度欄位：{lat_col}, {lon_col}")

    gdf = gpd.GeoDataFrame(
        df.copy(),
        geometry=gpd.points_from_xy(df[lon_col], df[lat_col]),
        crs="EPSG:4326",
    )
    return gdf


def nearest_route_match(activity_gdf_wgs84, route_gdf_wgs84, route_dist_col):
    """
    將每個活動點配對到最近的路線風險點。
    資料量小，直接用矩陣距離即可，避免 sjoin_nearest 版本差異。
    """
    metric_crs = route_gdf_wgs84.estimate_utm_crs()

    act_m = activity_gdf_wgs84.to_crs(metric_crs)
    route_m = route_gdf_wgs84.to_crs(metric_crs)

    act_xy = np.column_stack([act_m.geometry.x.to_numpy(), act_m.geometry.y.to_numpy()])
    route_xy = np.column_stack([route_m.geometry.x.to_numpy(), route_m.geometry.y.to_numpy()])

    nearest_idx = []
    nearest_dist = []

    for p in act_xy:
        d2 = np.sum((route_xy - p) ** 2, axis=1)
        j = int(np.argmin(d2))
        nearest_idx.append(j)
        nearest_dist.append(float(np.sqrt(d2[j])))

    nearest_idx = np.array(nearest_idx, dtype=int)
    nearest_dist = np.array(nearest_dist, dtype=float)

    out = activity_gdf_wgs84.drop(columns="geometry").copy()

    out["nearest_route_idx"] = nearest_idx
    out["nearest_route_dist_m"] = nearest_dist
    out["route_match_ok"] = out["nearest_route_dist_m"] <= MAX_MATCH_DIST_M

    route_plain = route_gdf_wgs84.drop(columns="geometry").reset_index(drop=True)

    route_cols_to_copy = [
        route_dist_col,
        "risk_score",
        "risk_score_smooth",
        "risk_band",
        "environment_adjusted_risk_score",
        "environment_adjusted_risk_band",
        "weather_modifier",
        "hydro_modifier",
        "dynamic_environment_modifier",
        "ele_smooth",
        "ele_gpx_m",
        "slope_pct",
        "slope_band",
        "surface_class",
        "route_semantic_class",
        "hazard_flags",
        "hydrology_flags",
    ]

    route_cols_to_copy = [c for c in route_cols_to_copy if c in route_plain.columns]

    for c in route_cols_to_copy:
        out[f"route_{c}"] = route_plain.iloc[nearest_idx][c].to_numpy()

    out = out.rename(columns={f"route_{route_dist_col}": "route_dist_m"})

    return out, metric_crs


def add_activity_overlay_features(df: pd.DataFrame):
    out = df.copy()

    # 風險 band 正規化
    if "route_risk_band" in out.columns:
        out["route_risk_band_norm"] = out["route_risk_band"].apply(normalize_band)
    else:
        out["route_risk_band_norm"] = "unknown"

    if "route_environment_adjusted_risk_band" in out.columns:
        out["route_adjusted_risk_band_norm"] = out[
            "route_environment_adjusted_risk_band"
        ].apply(normalize_band)
    else:
        out["route_adjusted_risk_band_norm"] = "unknown"

    # 移動速度平滑
    if "speed_km_h" in out.columns:
        out["speed_km_h_smooth"] = (
            out["speed_km_h"]
            .rolling(SPEED_ROLLING_WINDOW, center=True, min_periods=2)
            .mean()
        )
    else:
        out["speed_km_h_smooth"] = np.nan

    # route distance 排序檢查
    if "route_dist_m" in out.columns:
        out["route_dist_diff_m"] = out["route_dist_m"].diff()
    else:
        out["route_dist_diff_m"] = np.nan

    # 高風險活動點
    out["in_adjusted_high_or_above"] = out["route_adjusted_risk_band_norm"].isin(
        ["high", "very_high"]
    )
    out["in_adjusted_very_high"] = out["route_adjusted_risk_band_norm"].eq("very_high")

    return out


def summarize_by_band(df: pd.DataFrame, band_col: str, label_prefix: str):
    rows = []

    for band in RISK_ORDER:
        g = df[df[band_col] == band].copy()

        if g.empty:
            rows.append(
                {
                    "group_type": label_prefix,
                    "risk_band": band,
                    "point_count": 0,
                    "duration_s": 0.0,
                    "duration_min": 0.0,
                    "moving_duration_s": 0.0,
                    "moving_duration_min": 0.0,
                    "stationary_duration_s": 0.0,
                    "stationary_duration_min": 0.0,
                    "distance_m": 0.0,
                    "gain_m": 0.0,
                    "loss_m": 0.0,
                    "avg_speed_km_h": np.nan,
                    "moving_avg_speed_km_h": np.nan,
                    "mean_adjusted_risk_score": np.nan,
                    "mean_original_risk_score": np.nan,
                }
            )
            continue

        duration_s = g["delta_time_s"].sum() if "delta_time_s" in g.columns else np.nan

        moving_duration_s = (
            g.loc[g["moving_flag"], "delta_time_s"].sum()
            if "moving_flag" in g.columns and "delta_time_s" in g.columns
            else np.nan
        )

        stationary_duration_s = (
            g.loc[g["stationary_flag"], "delta_time_s"].sum()
            if "stationary_flag" in g.columns and "delta_time_s" in g.columns
            else np.nan
        )

        distance_m = (
            g["delta_dist_m_clean"].sum()
            if "delta_dist_m_clean" in g.columns
            else g["delta_dist_m"].sum()
            if "delta_dist_m" in g.columns
            else np.nan
        )

        gain_m = g["gain_m"].sum() if "gain_m" in g.columns else np.nan
        loss_m = g["loss_m"].sum() if "loss_m" in g.columns else np.nan

        avg_speed_km_h = (
            distance_m / duration_s * 3.6
            if pd.notna(duration_s) and duration_s > 0
            else np.nan
        )

        moving_dist_m = (
            g.loc[g["moving_flag"], "delta_dist_m_clean"].sum()
            if "moving_flag" in g.columns and "delta_dist_m_clean" in g.columns
            else np.nan
        )

        moving_avg_speed_km_h = (
            moving_dist_m / moving_duration_s * 3.6
            if pd.notna(moving_duration_s) and moving_duration_s > 0
            else np.nan
        )

        rows.append(
            {
                "group_type": label_prefix,
                "risk_band": band,
                "point_count": len(g),
                "duration_s": duration_s,
                "duration_min": duration_s / 60.0 if pd.notna(duration_s) else np.nan,
                "moving_duration_s": moving_duration_s,
                "moving_duration_min": moving_duration_s / 60.0 if pd.notna(moving_duration_s) else np.nan,
                "stationary_duration_s": stationary_duration_s,
                "stationary_duration_min": stationary_duration_s / 60.0 if pd.notna(stationary_duration_s) else np.nan,
                "distance_m": distance_m,
                "gain_m": gain_m,
                "loss_m": loss_m,
                "avg_speed_km_h": avg_speed_km_h,
                "moving_avg_speed_km_h": moving_avg_speed_km_h,
                "mean_adjusted_risk_score": (
                    g["route_environment_adjusted_risk_score"].mean()
                    if "route_environment_adjusted_risk_score" in g.columns
                    else np.nan
                ),
                "mean_original_risk_score": (
                    g["route_risk_score"].mean()
                    if "route_risk_score" in g.columns
                    else np.nan
                ),
            }
        )

    return pd.DataFrame(rows)


def build_overall_summary(df: pd.DataFrame):
    rows = []

    total_duration_s = df["delta_time_s"].sum() if "delta_time_s" in df.columns else np.nan
    total_distance_m = (
        df["delta_dist_m_clean"].sum()
        if "delta_dist_m_clean" in df.columns
        else df["delta_dist_m"].sum()
        if "delta_dist_m" in df.columns
        else np.nan
    )

    moving_duration_s = (
        df.loc[df["moving_flag"], "delta_time_s"].sum()
        if "moving_flag" in df.columns and "delta_time_s" in df.columns
        else np.nan
    )

    stationary_duration_s = (
        df.loc[df["stationary_flag"], "delta_time_s"].sum()
        if "stationary_flag" in df.columns and "delta_time_s" in df.columns
        else np.nan
    )

    match_ok_ratio = df["route_match_ok"].mean() if "route_match_ok" in df.columns else np.nan

    rows.append({"metric": "point_count", "value": len(df)})
    rows.append({"metric": "route_match_ok_ratio", "value": match_ok_ratio})
    rows.append({"metric": "mean_nearest_route_dist_m", "value": df["nearest_route_dist_m"].mean()})
    rows.append({"metric": "max_nearest_route_dist_m", "value": df["nearest_route_dist_m"].max()})

    rows.append({"metric": "total_duration_min", "value": total_duration_s / 60.0})
    rows.append({"metric": "moving_duration_min", "value": moving_duration_s / 60.0})
    rows.append({"metric": "stationary_duration_min", "value": stationary_duration_s / 60.0})

    rows.append({"metric": "total_distance_km", "value": total_distance_m / 1000.0})

    rows.append(
        {
            "metric": "avg_speed_km_h",
            "value": total_distance_m / total_duration_s * 3.6
            if pd.notna(total_duration_s) and total_duration_s > 0
            else np.nan,
        }
    )

    moving_dist_m = (
        df.loc[df["moving_flag"], "delta_dist_m_clean"].sum()
        if "moving_flag" in df.columns and "delta_dist_m_clean" in df.columns
        else np.nan
    )

    rows.append(
        {
            "metric": "moving_avg_speed_km_h",
            "value": moving_dist_m / moving_duration_s * 3.6
            if pd.notna(moving_duration_s) and moving_duration_s > 0
            else np.nan,
        }
    )

    if "in_adjusted_high_or_above" in df.columns:
        rows.append(
            {
                "metric": "duration_min_in_adjusted_high_or_above",
                "value": df.loc[df["in_adjusted_high_or_above"], "delta_time_s"].sum() / 60.0,
            }
        )
        rows.append(
            {
                "metric": "duration_min_in_adjusted_very_high",
                "value": df.loc[df["in_adjusted_very_high"], "delta_time_s"].sum() / 60.0,
            }
        )

    return pd.DataFrame(rows)


def add_band_strip_to_axis(ax, x, band_series, y0, y1, label):
    bands = band_series.apply(normalize_band).to_numpy()

    if len(x) < 2:
        return

    dx = np.nanmedian(np.diff(x))
    if not np.isfinite(dx) or dx <= 0:
        dx = 20.0

    for i in range(len(x)):
        if i == 0:
            x0 = x[i]
        else:
            x0 = (x[i - 1] + x[i]) / 2

        if i == len(x) - 1:
            x1 = x[i] + dx / 2
        else:
            x1 = (x[i] + x[i + 1]) / 2

        color = RISK_COLORS.get(bands[i], RISK_COLORS["unknown"])

        ax.axvspan(
            x0,
            x1,
            ymin=y0,
            ymax=y1,
            facecolor=color,
            alpha=0.90,
            linewidth=0,
        )

    ax.text(
        x[0],
        (y0 + y1) / 2,
        label,
        transform=ax.get_xaxis_transform(),
        ha="left",
        va="center",
        fontsize=9,
        color="#333333",
        bbox=dict(facecolor="white", edgecolor="none", alpha=0.75, pad=0.25),
    )


def plot_overlay_profile(df: pd.DataFrame):
    x = df["route_dist_m"].to_numpy()

    fig = plt.figure(figsize=(16, 9.5), dpi=DPI)

    gs = fig.add_gridspec(
        nrows=3,
        ncols=1,
        height_ratios=[3.2, 2.2, 0.9],
        hspace=0.18,
    )

    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[1, 0], sharex=ax1)
    ax3 = fig.add_subplot(gs[2, 0], sharex=ax1)

    fig.suptitle(
        "Qixing Activity Overlay with Dynamic Route Risk\n"
        "Activity Speed, Elevation, and Weather/Hydrology Adjusted Risk",
        fontsize=17,
        y=0.98,
    )

    # -----------------------------------------------------
    # 1) speed + risk
    # -----------------------------------------------------
    ax1.plot(
        x,
        df["speed_km_h_smooth"],
        color="#1565C0",
        linewidth=1.8,
        label="Activity speed, smoothed",
        zorder=4,
    )

    ax1.scatter(
        x,
        df["speed_km_h"],
        s=8,
        color="#64B5F6",
        alpha=0.35,
        label="Activity speed, raw",
        zorder=3,
    )

    ax1.set_ylabel("Speed (km/h)")
    ax1.grid(True, alpha=0.25)

    ax1r = ax1.twinx()
    ax1r.plot(
        x,
        df["route_environment_adjusted_risk_score"],
        color="#E53935",
        linewidth=1.8,
        label="Adjusted route risk",
        zorder=5,
    )
    ax1r.set_ylabel("Adjusted risk score")

    # 合併 legend
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax1r.get_legend_handles_labels()
    ax1.legend(
        h1 + h2,
        l1 + l2,
        loc="upper left",
        frameon=True,
        fontsize=9,
        ncol=3,
    )

    # -----------------------------------------------------
    # 2) elevation + stationary
    # -----------------------------------------------------
    ele_col = find_first_existing(df, ["ele_m", "ele_smooth", "route_ele_smooth", "route_ele_gpx_m"])

    if ele_col is not None:
        ax2.plot(
            x,
            df[ele_col],
            color="#6C63FF",
            linewidth=1.7,
            alpha=0.80,
            label="Activity elevation",
        )

    if "stationary_flag" in df.columns:
        st = df[df["stationary_flag"]].copy()
        if not st.empty and ele_col is not None:
            ax2.scatter(
                st["route_dist_m"],
                st[ele_col],
                s=16,
                color="#000000",
                alpha=0.55,
                label="Stationary points",
                zorder=5,
            )

    if "micro_rest_flag" in df.columns:
        mr = df[df["micro_rest_flag"]].copy()
        if not mr.empty and ele_col is not None:
            ax2.scatter(
                mr["route_dist_m"],
                mr[ele_col],
                s=22,
                marker="^",
                color="#F57C00",
                edgecolors="white",
                linewidths=0.35,
                alpha=0.82,
                label="Micro-rest points",
                zorder=6,
            )

    ax2.set_ylabel("Elevation (m)")
    ax2.grid(True, alpha=0.25)
    ax2.legend(
        loc="upper left",
        frameon=True,
        fontsize=9,
        ncol=3,
    )

    # -----------------------------------------------------
    # 3) adjusted risk band
    # -----------------------------------------------------
    ax3.set_ylim(0, 1)
    ax3.set_yticks([])
    ax3.set_ylabel("Risk band")

    add_band_strip_to_axis(
        ax3,
        x,
        df["route_adjusted_risk_band_norm"],
        y0=0.20,
        y1=0.80,
        label="Adjusted",
    )

    ax3.set_xlabel("Distance along route (m)")

    band_handles = [
        Patch(facecolor=RISK_COLORS[b], label=b)
        for b in ["low", "moderate", "high", "very_high"]
    ]

    ax3.legend(
        handles=band_handles,
        title="Adjusted risk band",
        loc="upper center",
        bbox_to_anchor=(0.5, -0.48),
        ncol=4,
        frameon=True,
        fontsize=9.5,
        title_fontsize=10.5,
    )

    plt.setp(ax1.get_xticklabels(), visible=False)
    plt.setp(ax2.get_xticklabels(), visible=False)

    fig.subplots_adjust(
        left=0.07,
        right=0.94,
        top=0.90,
        bottom=0.14,
    )

    fig.savefig(
        OUT_OVERLAY_PNG,
        dpi=DPI,
        facecolor="white",
        bbox_inches="tight",
        pad_inches=0.25,
    )

    plt.close(fig)


# =========================================================
# D. Main
# =========================================================
def main():
    ensure_exists(ACTIVITY_POINTS_CSV)
    ensure_exists(RISK_ROUTE_CSV)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    activity_df = normalize_columns(pd.read_csv(ACTIVITY_POINTS_CSV))
    route_df = normalize_columns(pd.read_csv(RISK_ROUTE_CSV))

    if activity_df.empty:
        raise ValueError(f"活動點資料為空：{ACTIVITY_POINTS_CSV}")
    if route_df.empty:
        raise ValueError(f"風險路線資料為空：{RISK_ROUTE_CSV}")

    activity_numeric_cols = [
        "lat",
        "lon",
        "ele_m",
        "delta_dist_m",
        "delta_dist_m_clean",
        "delta_ele_m",
        "delta_time_s",
        "speed_m_s",
        "speed_km_h",
        "slope_pct",
        "cum_dist_m",
        "cum_gain_m",
        "cum_loss_m",
        "gain_m",
        "loss_m",
    ]

    route_numeric_cols = [
        "lat",
        "lon",
        "dist_m",
        "risk_score",
        "risk_score_smooth",
        "environment_adjusted_risk_score",
        "weather_modifier",
        "hydro_modifier",
        "dynamic_environment_modifier",
        "ele_smooth",
        "ele_gpx_m",
        "slope_pct",
    ]

    activity_df = to_numeric_safe(activity_df, activity_numeric_cols)
    route_df = to_numeric_safe(route_df, route_numeric_cols)

    # time / bool parsing
    if "time" in activity_df.columns:
        activity_df["time"] = pd.to_datetime(activity_df["time"], errors="coerce", utc=True)

    for c in ["moving_flag", "stationary_flag", "micro_rest_flag"]:
        if c in activity_df.columns:
            activity_df[c] = (
                activity_df[c]
                .astype(str)
                .str.lower()
                .isin(["true", "1", "yes"])
            )

    route_dist_col = find_distance_col(route_df)

    activity_gdf = make_gdf_from_latlon(activity_df, lat_col="lat", lon_col="lon")
    route_gdf = make_gdf_from_latlon(route_df, lat_col="lat", lon_col="lon")

    overlay_df, metric_crs = nearest_route_match(
        activity_gdf,
        route_gdf,
        route_dist_col=route_dist_col,
    )

    overlay_df = add_activity_overlay_features(overlay_df)

    print("\n=== activity behavior flags ===")
    if "stationary_flag" in overlay_df.columns:
        print("stationary points:", int(overlay_df["stationary_flag"].sum()))
    else:
        print("stationary_flag: missing")

    if "micro_rest_flag" in overlay_df.columns:
        print("micro-rest points:", int(overlay_df["micro_rest_flag"].sum()))
    else:
        print("micro_rest_flag: missing")

    overlay_df.to_csv(OUT_OVERLAY_POINTS_CSV, index=False, encoding="utf-8-sig")
    # summary
    overall_summary = build_overall_summary(overlay_df)
    adjusted_band_summary = summarize_by_band(
        overlay_df,
        band_col="route_adjusted_risk_band_norm",
        label_prefix="adjusted_risk_band",
    )
    original_band_summary = summarize_by_band(
        overlay_df,
        band_col="route_risk_band_norm",
        label_prefix="original_risk_band",
    )

    summary_df = pd.concat(
        [
            overall_summary,
            pd.DataFrame([{"metric": "", "value": ""}]),
            adjusted_band_summary,
            pd.DataFrame([{"metric": "", "value": ""}]),
            original_band_summary,
        ],
        ignore_index=True,
        sort=False,
    )

    summary_df.to_csv(OUT_OVERLAY_SUMMARY_CSV, index=False, encoding="utf-8-sig")

    plot_overlay_profile(overlay_df)

    # console
    print("完成！")
    print("scenario:", SCENARIO_NAME)
    print("overlay points CSV:", OUT_OVERLAY_POINTS_CSV.resolve())
    print("overlay summary CSV:", OUT_OVERLAY_SUMMARY_CSV.resolve())
    print("overlay PNG:", OUT_OVERLAY_PNG.resolve())
    print("metric CRS:", metric_crs)

    print("\n=== route match quality ===")
    print("points:", len(overlay_df))
    print("route_match_ok_ratio:", overlay_df["route_match_ok"].mean())
    print("nearest_route_dist_m mean:", overlay_df["nearest_route_dist_m"].mean())
    print("nearest_route_dist_m max:", overlay_df["nearest_route_dist_m"].max())

    print("\n=== adjusted risk band activity summary ===")
    show_cols = [
        "risk_band",
        "point_count",
        "duration_min",
        "moving_duration_min",
        "stationary_duration_min",
        "distance_m",
        "gain_m",
        "loss_m",
        "avg_speed_km_h",
        "moving_avg_speed_km_h",
        "mean_adjusted_risk_score",
    ]
    print(adjusted_band_summary[show_cols].to_string(index=False))

    print("\n=== original risk band activity summary ===")
    print(original_band_summary[show_cols].to_string(index=False))


if __name__ == "__main__":
    main()