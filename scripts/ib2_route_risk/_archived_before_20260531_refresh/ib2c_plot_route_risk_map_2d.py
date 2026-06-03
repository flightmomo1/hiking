# -*- coding: utf-8 -*-
from pathlib import Path
import os

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from shapely.geometry import LineString


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

RISK_CSV = (
    PROJECT_ROOT / "outputs" / "ib2_v2_route_risk" / CASE_ID / f"{CASE_ID}_route_risk_v2.csv"
)
PROFILE_GEOJSON_CANDIDATES = [
    PROJECT_ROOT
    / "outputs"
    / "ib1e_route_profile_contour_window_terrain"
    / CASE_ID
    / f"{CASE_ID}_route_profile_contour_window_terrain_enriched.geojson",
    PROJECT_ROOT
    / "outputs"
    / "ib1_route_profile"
    / CASE_ID
    / f"{CASE_ID}_route_profile_points.geojson",
]

OUT_DIR = PROJECT_ROOT / "outputs" / "ib2c_route_risk_map_2d" / CASE_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PNG = OUT_DIR / f"{CASE_ID}_route_risk_map_2d.png"
OUT_GEOJSON = OUT_DIR / f"{CASE_ID}_route_risk_map_2d_segments.geojson"

RISK_COLOR = {
    "low": "#4CAF50",
    "moderate": "#F2C037",
    "high": "#F57C00",
    "very_high": "#D93A3A",
    "unknown": "#9E9E9E",
}
RISK_LEVEL = {"unknown": 0, "low": 1, "moderate": 2, "high": 3, "very_high": 4}


def first_existing(candidates, label):
    for fp in candidates:
        if fp.exists():
            print(f"{label}: {fp}")
            return fp
    raise FileNotFoundError(
        f"Missing {label}. Tried:\n" + "\n".join(str(fp) for fp in candidates)
    )


def norm_band(v):
    if pd.isna(v):
        return "unknown"
    s = str(v).strip().lower()
    return s if s in RISK_COLOR else "unknown"


def pick_band(a, b):
    a = norm_band(a)
    b = norm_band(b)
    return a if RISK_LEVEL[a] >= RISK_LEVEL[b] else b


def build_segments(points):
    rows = []
    points = points.sort_values("dist_m").reset_index(drop=True)
    for i in range(len(points) - 1):
        r1 = points.iloc[i]
        r2 = points.iloc[i + 1]
        if r1.geometry is None or r2.geometry is None:
            continue
        if r1.geometry.is_empty or r2.geometry.is_empty:
            continue
        rows.append(
            {
                "seg_id": i,
                "seg_start_dist": float(r1["dist_m"]),
                "seg_end_dist": float(r2["dist_m"]),
                "seg_mid_dist": float((r1["dist_m"] + r2["dist_m"]) / 2),
                "risk_band": pick_band(r1["risk_band"], r2["risk_band"]),
                "risk_score_smooth": np.nanmean(
                    [r1.get("risk_score_smooth", np.nan), r2.get("risk_score_smooth", np.nan)]
                ),
                "risk_reason": str(r1.get("risk_reason", "")),
                "geometry": LineString([r1.geometry, r2.geometry]),
            }
        )
    if not rows:
        raise ValueError("No line segments could be built from profile points")
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=points.crs)


def very_high_runs(seg_gdf):
    runs = []
    run_start = None
    run_end = None
    for _, row in seg_gdf.sort_values("seg_start_dist").iterrows():
        if row["risk_band"] == "very_high":
            if run_start is None:
                run_start = float(row["seg_start_dist"])
            run_end = float(row["seg_end_dist"])
        elif run_start is not None:
            runs.append((run_start, run_end))
            run_start = None
    if run_start is not None:
        runs.append((run_start, run_end))
    return runs


def main():
    if not RISK_CSV.exists():
        raise FileNotFoundError(RISK_CSV)
    profile_geojson = first_existing(PROFILE_GEOJSON_CANDIDATES, "profile GeoJSON")

    risk_df = pd.read_csv(RISK_CSV, low_memory=False, encoding="utf-8-sig")
    profile_gdf = gpd.read_file(profile_geojson)
    if profile_gdf.crs is None:
        profile_gdf = profile_gdf.set_crs("EPSG:4326")
    profile_gdf = profile_gdf.to_crs("EPSG:4326")

    for col in ["dist_m", "risk_band"]:
        if col not in risk_df.columns:
            raise KeyError(f"risk CSV missing column: {col}")
    if "dist_m" not in profile_gdf.columns:
        raise KeyError("profile GeoJSON missing dist_m")

    risk_df = risk_df.copy()
    profile_gdf = profile_gdf.copy()
    risk_df["dist_key"] = risk_df["dist_m"].round(3)
    profile_gdf["dist_key"] = profile_gdf["dist_m"].round(3)

    keep = [
        "dist_key",
        "dist_m",
        "risk_score",
        "risk_score_smooth",
        "risk_band",
        "risk_reason",
        "data_quality_reason",
        "route_semantic_class",
        "surface_class",
    ]
    keep = [c for c in keep if c in risk_df.columns]
    merged = profile_gdf.merge(risk_df[keep], on="dist_key", how="left", suffixes=("_geo", "_risk"))
    if "dist_m_risk" in merged.columns:
        merged["dist_m"] = merged["dist_m_risk"]
    elif "dist_m_geo" in merged.columns:
        merged["dist_m"] = merged["dist_m_geo"]
    merged["risk_band"] = merged["risk_band"].map(norm_band)
    if "risk_score_smooth" not in merged.columns and "risk_score" in merged.columns:
        merged["risk_score_smooth"] = merged["risk_score"].rolling(9, center=True, min_periods=2).mean()

    merged = gpd.GeoDataFrame(merged, geometry="geometry", crs=profile_gdf.crs)
    merged = merged[merged["risk_band"].notna()].sort_values("dist_m").reset_index(drop=True)
    seg_gdf = build_segments(merged)
    seg_gdf.to_file(OUT_GEOJSON, driver="GeoJSON")

    seg_plot = seg_gdf.to_crs(epsg=3857)
    points_plot = merged.to_crs(epsg=3857)

    fig, ax = plt.subplots(figsize=(10, 10), dpi=200)
    seg_plot.plot(ax=ax, color="#D0D0D0", linewidth=1.2, zorder=1)
    for band in ["low", "moderate", "high", "very_high", "unknown"]:
        sub = seg_plot[seg_plot["risk_band"] == band]
        if not sub.empty:
            sub.plot(ax=ax, color=RISK_COLOR[band], linewidth=5.5, alpha=0.95, zorder=3)

    start_pt = points_plot.geometry.iloc[0]
    end_pt = points_plot.geometry.iloc[-1]
    ax.scatter(start_pt.x, start_pt.y, s=90, c="#2E7D32", marker="o", edgecolors="white", zorder=5)
    ax.scatter(end_pt.x, end_pt.y, s=90, c="#C62828", marker="s", edgecolors="white", zorder=5)
    ax.annotate("Start", xy=(start_pt.x, start_pt.y), xytext=(8, 8), textcoords="offset points", color="#1B5E20", weight="bold")
    ax.annotate("End", xy=(end_pt.x, end_pt.y), xytext=(8, 8), textcoords="offset points", color="#B71C1C", weight="bold")

    for start_m, end_m in very_high_runs(seg_gdf):
        target = seg_plot[
            (seg_plot["seg_start_dist"] <= end_m)
            & (seg_plot["seg_end_dist"] >= start_m)
            & (seg_plot["risk_band"] == "very_high")
        ]
        if target.empty:
            continue
        centroid = target.geometry.union_all().centroid if hasattr(target.geometry, "union_all") else target.unary_union.centroid
        ax.annotate(
            f"very_high\n{int(start_m)}-{int(end_m)} m",
            xy=(centroid.x, centroid.y),
            xytext=(0, 12),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            color="#8B0000",
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#D93A3A", alpha=0.9),
        )

    ax.set_title(f"{CASE_NAME}\nib2c route risk map", fontsize=16)
    ax.set_axis_off()
    ax.set_aspect("equal")
    minx, miny, maxx, maxy = seg_plot.total_bounds
    pad_x = (maxx - minx) * 0.08
    pad_y = (maxy - miny) * 0.08
    ax.set_xlim(minx - pad_x, maxx + pad_x)
    ax.set_ylim(miny - pad_y, maxy + pad_y)
    ax.legend(
        handles=[Line2D([0], [0], color=RISK_COLOR[b], lw=4, label=b) for b in ["low", "moderate", "high", "very_high"]],
        title="Risk band",
        loc="lower left",
    )
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=200, bbox_inches="tight")
    plt.close(fig)

    print("case:", CASE_ID)
    print("PNG:", OUT_PNG)
    print("GeoJSON:", OUT_GEOJSON)
    print(seg_gdf["risk_band"].value_counts(dropna=False))


if __name__ == "__main__":
    main()
