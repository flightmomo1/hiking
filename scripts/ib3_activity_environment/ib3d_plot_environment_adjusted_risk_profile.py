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
# 腳本通常放在：115_osm/七星山上山/
# 輸出資料夾通常在：115_osm/ib3_environment_output/
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent

SCENARIO_NAME = os.environ.get("SCENARIO_NAME", "actual_gpx_9stations")

ENV_BASE_DIR = BASE_DIR / "ib3_environment_output"
ENV_DIR = ENV_BASE_DIR / SCENARIO_NAME

INPUT_CSV = ENV_DIR / "qixing_environment_adjusted_risk.csv"

# 若 INPUT_CSV 裡沒有 elevation 欄位，會從這裡補
ELEVATION_GEOJSON = BASE_DIR / "ib1a_route_elevation_profile_output" / "qixing_route_profile_points.geojson"

OUT_DIR = ENV_DIR
OUT_PNG = OUT_DIR / "qixing_environment_adjusted_risk_profile.png"
OUT_PLOT_CSV = OUT_DIR / "qixing_environment_adjusted_risk_plot_data.csv"


# =========================================================
# B. Style
# =========================================================
DPI = 220

RISK_COLORS = {
    "low": "#4CAF50",
    "moderate": "#F2C037",
    "high": "#F57C00",
    "very_high": "#D93A3A",
    "unknown": "#BDBDBD",
}

RISK_ORDER = ["low", "moderate", "high", "very_high"]

COLOR_ORIGINAL_RISK = "#222222"
COLOR_ADJUSTED_RISK = "#E53935"
COLOR_DYNAMIC_MOD = "#1E88E5"
COLOR_ELEVATION = "#6C63FF"

COLOR_WEATHER_MOD = "#FB8C00"
COLOR_HYDRO_MOD = "#1976D2"
COLOR_TOTAL_MOD = "#8E24AA"

MIN_SHADE_RUN_LENGTH_M = 80  # 只用背景陰影標示長度 >= 80m 的 very_high 區段


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


def find_original_risk_col(df: pd.DataFrame):
    col = find_first_existing(
        df,
        [
            "risk_score_smooth",
            "risk_score",
            "segment_risk_score",
        ],
    )
    if col is None:
        raise KeyError(f"找不到原始風險分數欄位，現有欄位：{list(df.columns)}")
    return col


def find_elevation_col(df: pd.DataFrame):
    """
    優先使用平滑後高程，圖面比較穩。
    """
    return find_first_existing(
        df,
        [
            "ele_smooth",
            "ele_med",
            "ele_gpx_m",
            "gpx_elevation_m",
            "raw_ele_m",
            "elevation_m",
            "gpx_ele_m",
            "ele_m",
            "altitude_m",
            "elevation",
            "nslc_elevation_m",
            "contour_elevation_m",
            "dem_elevation_m",
            "ele",
            "height_m",
            "z_m",
        ],
    )


def attach_elevation_if_missing(df: pd.DataFrame, elevation_col):
    """
    若 adjusted risk CSV 沒有海拔欄位，則從 ib1a profile points GeoJSON 補入。
    第一版以列數順序對齊；若列數不同，截到最小長度。
    """
    if elevation_col is not None:
        return df, elevation_col

    if not ELEVATION_GEOJSON.exists():
        print(f"警告：找不到海拔來源檔：{ELEVATION_GEOJSON.resolve()}")
        return df, None

    elev_gdf = gpd.read_file(ELEVATION_GEOJSON)
    elev_gdf = normalize_columns(elev_gdf)

    src_ele_col = find_elevation_col(elev_gdf)

    if src_ele_col is None:
        print("\n警告：profile points 裡也找不到海拔欄位")
        print("profile columns:", list(elev_gdf.columns))
        return df, None

    out = df.copy()

    n = min(len(out), len(elev_gdf))

    if len(out) != len(elev_gdf):
        print(f"警告：風險資料與海拔資料列數不同，將以 n={n} 對齊")
        out = out.iloc[:n].copy()
        elev_gdf = elev_gdf.iloc[:n].copy()

    elev_values = pd.to_numeric(elev_gdf[src_ele_col], errors="coerce").values
    out["elevation_m_for_plot"] = elev_values

    print(
        f"已從 {ELEVATION_GEOJSON.name} 補入海拔欄位："
        f"{src_ele_col} -> elevation_m_for_plot"
    )

    return out, "elevation_m_for_plot"


def normalize_band(v):
    if pd.isna(v):
        return "unknown"
    s = str(v).strip().lower()
    return s if s in RISK_COLORS else "unknown"


def get_band_runs(df, dist_col, band_col, target_band="very_high"):
    if band_col not in df.columns:
        return []

    x = df[dist_col].to_numpy()
    band = df[band_col].apply(normalize_band).to_numpy()

    runs = []
    current_start = None
    current_end = None

    for i, b in enumerate(band):
        if b == target_band:
            if current_start is None:
                current_start = x[i]
            current_end = x[i]
        else:
            if current_start is not None:
                runs.append((current_start, current_end))
                current_start = None
                current_end = None

    if current_start is not None:
        runs.append((current_start, current_end))

    return runs


def add_vertical_regions(ax, runs, color="#D93A3A", alpha=0.10):
    for start, end in runs:
        ax.axvspan(start, end, color=color, alpha=alpha, zorder=1)


def add_band_strip(ax, df, dist_col, band_col, y0, y1, label):
    """
    在 ax 的 y0~y1 範圍畫 risk band 色帶。
    y0/y1 使用 axis fraction。
    """
    if band_col not in df.columns:
        return

    x = df[dist_col].to_numpy()
    bands = df[band_col].apply(normalize_band).to_numpy()

    if len(x) < 2:
        return

    dx = np.nanmedian(np.diff(x))
    if not np.isfinite(dx) or dx <= 0:
        dx = 20.0

    for i in range(len(df)):
        if i == 0:
            x0 = x[i]
        else:
            x0 = (x[i - 1] + x[i]) / 2

        if i == len(df) - 1:
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


def build_environment_context_text(df):
    weather_rain_factor = (
        df["weather_rain_factor"].iloc[0]
        if "weather_rain_factor" in df.columns
        else np.nan
    )
    weather_rain_sum = (
        df["weather_rain_sum_mm"].iloc[0]
        if "weather_rain_sum_mm" in df.columns
        else np.nan
    )
    weather_humidity = (
        df["weather_humidity_pct"].iloc[0]
        if "weather_humidity_pct" in df.columns
        else np.nan
    )
    weather_wind = (
        df["weather_wind_max_ms"].iloc[0]
        if "weather_wind_max_ms" in df.columns
        else np.nan
    )
    weather_temp = (
        df["weather_temp_mean_c"].iloc[0]
        if "weather_temp_mean_c" in df.columns
        else np.nan
    )
    hydro_change = (
        df["hydro_water_change_m"].iloc[0]
        if "hydro_water_change_m" in df.columns
        else np.nan
    )
    hydro_range = (
        df["hydro_water_range_m"].iloc[0]
        if "hydro_water_range_m" in df.columns
        else np.nan
    )

    if pd.notna(weather_rain_factor) and weather_rain_factor >= 0.99:
        rain_line = "Rain factor: high (capped)"
    elif pd.notna(weather_rain_sum):
        rain_line = f"Rain index: {weather_rain_sum:.1f} mm"
    else:
        rain_line = "Rain factor: n/a"

    lines = [
        "Environment context",
        rain_line,
    ]

    if pd.notna(weather_humidity):
        lines.append(f"Humidity: {weather_humidity:.1f}%")
    if pd.notna(weather_wind):
        lines.append(f"Wind max: {weather_wind:.1f} m/s")
    if pd.notna(weather_temp):
        lines.append(f"Mean temp.: {weather_temp:.1f}°C")
    if pd.notna(hydro_change):
        lines.append(f"Water Δ: {hydro_change:.3f} m")
    if pd.notna(hydro_range):
        lines.append(f"Water range: {hydro_range:.3f} m")

    return "\n".join(lines)


# =========================================================
# D. Main
# =========================================================
def main():
    ensure_exists(INPUT_CSV)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    df = normalize_columns(pd.read_csv(INPUT_CSV))

    print("\n=== input columns ===")
    print(list(df.columns))

    if df.empty:
        raise ValueError(f"輸入 CSV 為空：{INPUT_CSV}")

    dist_col = find_distance_col(df)
    original_risk_col = find_original_risk_col(df)
    elevation_col = find_elevation_col(df)

    # 若 adjusted risk CSV 沒有海拔，從 profile points 補
    df, elevation_col = attach_elevation_if_missing(df, elevation_col)

    required_cols = [
        "environment_adjusted_risk_score",
        "weather_modifier",
        "hydro_modifier",
        "dynamic_environment_modifier",
        "risk_band",
        "environment_adjusted_risk_band",
    ]

    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise KeyError(f"缺少必要欄位：{missing}")
    
    original_band_col = (
        "risk_band_recomputed"
        if "risk_band_recomputed" in df.columns
        else "risk_band"
    )

    numeric_cols = [
        dist_col,
        original_risk_col,
        "environment_adjusted_risk_score",
        "weather_modifier",
        "hydro_modifier",
        "dynamic_environment_modifier",
        "weather_rain_factor",
        "weather_rain_sum_mm",
        "weather_humidity_pct",
        "weather_wind_max_ms",
        "weather_temp_mean_c",
        "hydro_water_change_m",
        "hydro_water_range_m",
    ]

    if elevation_col is not None:
        numeric_cols.append(elevation_col)

    df = to_numeric_safe(df, numeric_cols)
    df = df.sort_values(dist_col).reset_index(drop=True)

    # 若主要線條有空值，做線性補值，避免斷線
    line_cols = [
        original_risk_col,
        "environment_adjusted_risk_score",
        "weather_modifier",
        "hydro_modifier",
        "dynamic_environment_modifier",
    ]

    if elevation_col is not None:
        line_cols.append(elevation_col)

    for c in line_cols:
        if c in df.columns:
            df[c] = df[c].interpolate(limit_direction="both")

    x = df[dist_col].to_numpy()

    # -----------------------------------------------------
    # Very high runs：只保留背景陰影，不畫文字標籤
    # -----------------------------------------------------
    all_very_high_runs = get_band_runs(
        df,
        dist_col,
        "environment_adjusted_risk_band",
        target_band="very_high",
    )

    shaded_very_high_runs = [
        (start, end)
        for start, end in all_very_high_runs
        if (end - start) >= MIN_SHADE_RUN_LENGTH_M
    ]

    # -----------------------------------------------------
    # Output plot data
    # -----------------------------------------------------
    plot_cols = [
        dist_col,
        original_risk_col,
        "environment_adjusted_risk_score",
        "weather_modifier",
        "hydro_modifier",
        "dynamic_environment_modifier",
        "risk_band",
        "environment_adjusted_risk_band",
    ]

    if elevation_col is not None:
        plot_cols.append(elevation_col)

    for c in [
        "weather_rain_factor",
        "weather_rain_sum_mm",
        "weather_humidity_pct",
        "weather_wind_max_ms",
        "weather_temp_mean_c",
        "hydro_water_change_m",
        "hydro_water_range_m",
    ]:
        if c in df.columns and c not in plot_cols:
            plot_cols.append(c)

    df[plot_cols].to_csv(OUT_PLOT_CSV, index=False, encoding="utf-8-sig")

    # -----------------------------------------------------
    # Plot layout
    # -----------------------------------------------------
    fig = plt.figure(figsize=(16, 10.2), dpi=DPI)

    gs = fig.add_gridspec(
        nrows=3,
        ncols=1,
        height_ratios=[4.1, 1.75, 1.0],
        hspace=0.24,  # 0.18; 因為圖例拉到外面，所以間隔拉大
    )

    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[1, 0], sharex=ax1)
    ax3 = fig.add_subplot(gs[2, 0], sharex=ax1)

    # -----------------------------------------------------
    # Figure title
    # -----------------------------------------------------
    fig.suptitle(
        "Qixing Route Dynamic Environment Risk Adjustment\n"
        "Original Risk vs Weather/Hydrology Adjusted Risk with Elevation",
        fontsize=17,
        y=0.985,
    )

    # -----------------------------------------------------
    # 1) Main panel: risk + dynamic modifier + elevation
    # -----------------------------------------------------
    add_vertical_regions(
        ax1,
        shaded_very_high_runs,
        color=RISK_COLORS["very_high"],
        alpha=0.10,
    )

    l1, = ax1.plot(
        x,
        df[original_risk_col],
        color=COLOR_ORIGINAL_RISK,
        linewidth=1.9,
        label="Original route risk",
        zorder=4,
    )

    l2, = ax1.plot(
        x,
        df["environment_adjusted_risk_score"],
        color=COLOR_ADJUSTED_RISK,
        linewidth=2.2,
        label="Weather + hydro adjusted risk",
        zorder=5,
    )

    l3, = ax1.plot(
        x,
        df["dynamic_environment_modifier"],
        color=COLOR_DYNAMIC_MOD,
        linewidth=1.7,
        linestyle="--",
        label="Dynamic environment modifier",
        zorder=4,
    )

    ax1.set_ylabel("Risk score", fontsize=12)
    ax1.grid(True, alpha=0.25)
    ax1.set_axisbelow(True)

    # 右軸：海拔
    l4 = None
    ax1r = None

    if elevation_col is not None:
        ax1r = ax1.twinx()

        l4, = ax1r.plot(
            x,
            df[elevation_col],
            color=COLOR_ELEVATION,
            linewidth=1.5,
            alpha=0.48,
            label="Elevation",
            zorder=2,
        )

        ax1r.set_ylabel("Elevation (m)", fontsize=12)
        ax1r.grid(False)

        elev_min = df[elevation_col].min()
        elev_max = df[elevation_col].max()

        if pd.notna(elev_min) and pd.notna(elev_max):
            pad = max((elev_max - elev_min) * 0.08, 20)
            ax1r.set_ylim(elev_min - pad, elev_max + pad)

    # -----------------------------------------------------
    # Figure-level legend：放在圖外上方，不壓 ax1
    # -----------------------------------------------------
    handles = [l1, l2, l3]
    if l4 is not None:
        handles.append(l4)

    labels = [h.get_label() for h in handles]

    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.44, 0.925),
        frameon=True,
        fontsize=9.5,
        ncol=len(handles),
        columnspacing=1.5,
        handletextpad=0.7,
    )

    # -----------------------------------------------------
    # Environment context：圖外上方右側
    # Environment context：簡報後製，不在圖中顯示
    # -----------------------------------------------------
    #info_text = build_environment_context_text(df)
    #
    #fig.text(
    #    0.795,
    #    0.925,
    #    info_text,
    #    ha="left",
    #    va="top",
    #    fontsize=8.5,
    #    linespacing=1.12,
    #    bbox=dict(
    #        facecolor="white",
    #        edgecolor="#999999",
    #        alpha=0.95,
    #        boxstyle="round,pad=0.35",
    #    ),
    #)

    # -----------------------------------------------------
    # 2) Modifier panel
    # -----------------------------------------------------
    ax2.plot(
        x,
        df["weather_modifier"],
        color=COLOR_WEATHER_MOD,
        linewidth=1.8,
        label="Weather modifier",
    )

    ax2.plot(
        x,
        df["hydro_modifier"],
        color=COLOR_HYDRO_MOD,
        linewidth=1.8,
        label="Hydrology modifier",
    )

    ax2.plot(
        x,
        df["dynamic_environment_modifier"],
        color=COLOR_TOTAL_MOD,
        linewidth=1.7,
        linestyle="--",
        label="Total environment modifier",
    )

    ax2.set_ylabel("Modifier", fontsize=12)
    ax2.grid(True, alpha=0.25)
    ax2.set_axisbelow(True)


    #ax2.legend(
    #    loc="upper left",
    #    frameon=True,
    #    fontsize=9,
    #    ncol=3,
    #)

    # 拉到圖例外面
    ax2.legend(
        loc="lower left",
        bbox_to_anchor=(0.0, 1.02),
        frameon=True,
        fontsize=9,
        ncol=3,
        borderaxespad=0.2,
    )

    # -----------------------------------------------------
    # 3) Risk band strips
    # -----------------------------------------------------
    ax3.set_ylim(0, 1)
    ax3.set_yticks([])
    ax3.set_ylabel("Bands", fontsize=12)

    add_band_strip(
        ax3,
        df,
        dist_col=dist_col,
        band_col=original_band_col,
        y0=0.55,
        y1=0.86,
        label="Original",
    )

    add_band_strip(
        ax3,
        df,
        dist_col=dist_col,
        band_col="environment_adjusted_risk_band",
        y0=0.10,
        y1=0.41,
        label="Adjusted",
    )

    ax3.set_xlabel("Distance along route (m)", fontsize=12)
    ax3.grid(False)

    band_handles = [
        Patch(facecolor=RISK_COLORS[b], label=b)
        for b in RISK_ORDER
    ]

    ax3.legend(
        handles=band_handles,
        title="Risk band",
        loc="upper center",
        bbox_to_anchor=(0.5, -0.48),
        ncol=4,
        frameon=True,
        fontsize=9.5,
        title_fontsize=10.5,
    )

    # -----------------------------------------------------
    # Cosmetics / layout
    # -----------------------------------------------------
    plt.setp(ax1.get_xticklabels(), visible=False)
    plt.setp(ax2.get_xticklabels(), visible=False)

    fig.subplots_adjust(
        left=0.07,
        right=0.985,
        top=0.865,
        bottom=0.145,
    )

    fig.savefig(
        OUT_PNG,
        dpi=DPI,
        facecolor="white",
        bbox_inches="tight",
        pad_inches=0.25,
    )

    plt.close(fig)

    # -----------------------------------------------------
    # Console summary
    # -----------------------------------------------------
    print("完成！")
    print("scenario:", SCENARIO_NAME)
    print("PNG:", OUT_PNG.resolve())
    print("plot CSV:", OUT_PLOT_CSV.resolve())

    print("\n=== plotted columns ===")
    print("distance:", dist_col)
    print("original risk:", original_risk_col)
    print("adjusted risk: environment_adjusted_risk_score")
    print("weather modifier: weather_modifier")
    print("hydrology modifier: hydro_modifier")
    print("dynamic modifier: dynamic_environment_modifier")
    print("elevation:", elevation_col if elevation_col is not None else "(missing)")

    print("\n=== original risk_band for plot ===")
    print(df[original_band_col].value_counts(dropna=False))

    print("\n=== environment_adjusted_risk_band ===")
    print(df["environment_adjusted_risk_band"].value_counts(dropna=False))

    print("\n=== all very_high adjusted runs ===")
    if all_very_high_runs:
        for start, end in all_very_high_runs:
            print(f"{int(round(start))}–{int(round(end))} m")
    else:
        print("none")

    print("\n=== shaded very_high runs ===")
    if shaded_very_high_runs:
        for start, end in shaded_very_high_runs:
            print(f"{int(round(start))}–{int(round(end))} m")
    else:
        print("none")


if __name__ == "__main__":
    main()