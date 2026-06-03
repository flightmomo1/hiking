# -*- coding: utf-8 -*-
from pathlib import Path
import os

import matplotlib as mpl
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CASE_ID = os.environ.get("CASE_ID", "qixing_xiaoyoukeng_main_peak_20260315")
CASE_NAME = os.environ.get("CASE_NAME", CASE_ID)

mpl.rcParams["font.sans-serif"] = [
    "Microsoft JhengHei",
    "Microsoft YaHei",
    "Noto Sans CJK TC",
    "Arial Unicode MS",
    "DejaVu Sans",
]
mpl.rcParams["axes.unicode_minus"] = False

INPUT_CSV = (
    PROJECT_ROOT
    / "outputs"
    / "ib2_v2_route_risk"
    / CASE_ID
    / f"{CASE_ID}_route_risk_v2.csv"
)
OUT_DIR = PROJECT_ROOT / "outputs" / "ib2a_route_risk_profile" / CASE_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PNG = OUT_DIR / f"{CASE_ID}_route_risk_profile.png"
OUT_CSV = OUT_DIR / f"{CASE_ID}_route_risk_profile_plot_data.csv"

RISK_COLOR = {
    "low": "#4CAF50",
    "moderate": "#F2C037",
    "high": "#F57C00",
    "very_high": "#D93A3A",
    "unknown": "#9E9E9E",
}

ROUTE_CLASS_COLOR = {
    "steps": "#7b3294",
    "footway": "#1b9e77",
    "path": "#66a61e",
    "track": "#a6761d",
    "service_road": "#7570b3",
    "road": "#666666",
    "bridge": "#1f78b4",
    "tunnel": "#999999",
    "ford": "#00a6d6",
    "ladder": "#d95f02",
    "via_ferrata": "#e7298a",
    "unknown_route_type": "#dddddd",
}

SURFACE_CLASS_COLOR = {
    "paved_stone": "#8c6d31",
    "paved_asphalt": "#4d4d4d",
    "paved_concrete": "#9e9e9e",
    "gravel_compacted": "#bdb76b",
    "natural_ground": "#8b5a2b",
    "rock": "#6b6b6b",
    "wood_boardwalk": "#c49a6c",
    "trail_unknown_surface": "#c7e9b4",
    "unknown_surface": "#eeeeee",
}


def norm_text(v, fallback="unknown"):
    if pd.isna(v):
        return fallback
    s = str(v).strip()
    return s if s else fallback


def build_runs(df, col):
    values = df[col].fillna("unknown").astype(str).tolist()
    if not values:
        return []
    runs = []
    start = 0
    for i in range(1, len(values)):
        if values[i] != values[start]:
            runs.append((start, i - 1, values[start]))
            start = i
    runs.append((start, len(values) - 1, values[start]))
    return runs


def draw_category_strip(ax, df, col, color_map, label):
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    ax.set_ylabel(label, rotation=0, ha="right", va="center", labelpad=58)
    ax.grid(False)
    for start, end, value in build_runs(df, col):
        x0 = df.iloc[start]["dist_m"]
        x1 = df.iloc[end]["dist_m"]
        if end + 1 < len(df):
            x1 = df.iloc[end + 1]["dist_m"]
        ax.axvspan(x0, x1, ymin=0, ymax=1, color=color_map.get(str(value), "#dddddd"))
    used = [v for v in df[col].dropna().astype(str).unique()]
    return [mpatches.Patch(color=color_map.get(v, "#dddddd"), label=v) for v in used]


def main():
    if not INPUT_CSV.exists():
        raise FileNotFoundError(INPUT_CSV)
    df = pd.read_csv(INPUT_CSV, low_memory=False, encoding="utf-8-sig")
    if df.empty:
        raise ValueError(f"Empty input: {INPUT_CSV}")
    for col in ["dist_m", "risk_score", "risk_band"]:
        if col not in df.columns:
            raise KeyError(f"missing required column: {col}")

    df = df.sort_values("dist_m").reset_index(drop=True)
    df["risk_band"] = df["risk_band"].fillna("unknown").astype(str)

    for col, default in [
        ("risk_score_smooth", None),
        ("effort_score", 0.0),
        ("exposure_score", 0.0),
        ("route_semantic_class", "unknown_route_type"),
        ("surface_class", "unknown_surface"),
    ]:
        if col not in df.columns:
            df[col] = (
                df["risk_score"].rolling(9, center=True, min_periods=2).mean()
                if default is None
                else default
            )

    df["effort_score_smooth"] = df["effort_score"].rolling(9, center=True, min_periods=2).mean()
    df["exposure_score_smooth"] = df["exposure_score"].rolling(9, center=True, min_periods=2).mean()

    fig, (ax1, ax_route, ax_surface) = plt.subplots(
        nrows=3,
        ncols=1,
        figsize=(15, 7.5),
        sharex=True,
        gridspec_kw={"height_ratios": [5, 0.35, 0.35]},
    )

    for start, end, band in build_runs(df, "risk_band"):
        x0 = df.iloc[start]["dist_m"]
        x1 = df.iloc[end]["dist_m"]
        if end + 1 < len(df):
            x1 = df.iloc[end + 1]["dist_m"]
        ax1.axvspan(x0, x1, color=RISK_COLOR.get(band, "#cccccc"), alpha=0.18)

    ax1.plot(df["dist_m"], df["risk_score_smooth"], color="black", lw=2.0, label="risk_score_smooth")
    ax1.plot(df["dist_m"], df["effort_score_smooth"], ls="--", lw=1.5, label="effort_score")
    ax1.plot(df["dist_m"], df["exposure_score_smooth"], ls=":", lw=1.5, label="exposure_score")
    ax1.set_ylabel("Risk score (0-1)")
    ax1.set_ylim(0, max(1.0, float(df["risk_score"].max()) * 1.12))
    ax1.grid(True, alpha=0.25)
    ax1.legend(loc="upper right", ncol=3, fontsize=9)

    route_handles = draw_category_strip(
        ax_route, df, "route_semantic_class", ROUTE_CLASS_COLOR, "route class"
    )
    surface_handles = draw_category_strip(
        ax_surface, df, "surface_class", SURFACE_CLASS_COLOR, "surface"
    )
    ax_surface.set_xlabel("Distance (m)")

    risk_handles = [
        mpatches.Patch(color=color, label=band) for band, color in RISK_COLOR.items()
    ]
    ax1.legend(handles=risk_handles, title="Risk band", loc="upper left", fontsize=8)
    ax_route.legend(handles=route_handles, loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=7)
    ax_surface.legend(handles=surface_handles, loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=7)

    fig.suptitle(f"{CASE_NAME}\nib2a route risk profile", fontsize=15)
    fig.tight_layout(rect=[0, 0, 0.86, 0.93])
    fig.savefig(OUT_PNG, dpi=180)
    plt.close(fig)

    df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print("case:", CASE_ID)
    print("PNG:", OUT_PNG)
    print("CSV:", OUT_CSV)
    print(df["risk_band"].value_counts(dropna=False))


if __name__ == "__main__":
    main()
