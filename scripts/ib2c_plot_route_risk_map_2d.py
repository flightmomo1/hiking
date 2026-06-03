# -*- coding: utf-8 -*-
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt

from matplotlib.lines import Line2D
from shapely.geometry import LineString


# =========================================================
# A. 路徑設定
# =========================================================
RISK_CSV = Path("ib2_v2_route_risk_output/qixing_route_risk_v2.csv")
PROFILE_GEOJSON = Path("ib1c_route_profile_semantic_output/qixing_route_profile_semantic_enriched.geojson")

OUT_DIR = Path("ib2c_route_risk_map_output")
OUT_PNG = OUT_DIR / "qixing_route_risk_map_2d.png"
OUT_GEOJSON = OUT_DIR / "qixing_route_risk_map_2d_segments.geojson"


# =========================================================
# B. 視覺設定
# =========================================================
RISK_COLOR_MAP = {
    "low": "#4CAF50",        # 綠
    "moderate": "#FBC02D",   # 黃
    "high": "#FB8C00",       # 橘
    "very_high": "#D32F2F",  # 紅
    "unknown": "#9E9E9E",    # 灰
}

RISK_LEVEL_MAP = {
    "unknown": 0,
    "low": 1,
    "moderate": 2,
    "high": 3,
    "very_high": 4,
}

FIG_W = 10
FIG_H = 10
DPI = 200

LINE_WIDTH = 5.5
BASELINE_WIDTH = 1.2
ANNOTATION_FONTSIZE = 9
TITLE_FONTSIZE = 18
SUBTITLE_FONTSIZE = 12
LABEL_FONTSIZE = 12
TICK_FONTSIZE = 10


# =========================================================
# C. 工具函式
# =========================================================
def require_file(fp: Path) -> None:
    if not fp.exists():
        raise FileNotFoundError(f"找不到檔案：{fp.resolve()}")


def normalize_risk_band(v):
    if pd.isna(v):
        return "unknown"
    s = str(v).strip().lower()
    return s if s in RISK_COLOR_MAP else "unknown"


def risk_to_level(v):
    return RISK_LEVEL_MAP.get(normalize_risk_band(v), 0)


def pick_segment_risk_band(b1, b2):
    """
    線段風險用兩端點中較高者，較符合保守判讀。
    """
    b1 = normalize_risk_band(b1)
    b2 = normalize_risk_band(b2)
    return b1 if risk_to_level(b1) >= risk_to_level(b2) else b2


def safe_text(v, fallback=""):
    if pd.isna(v):
        return fallback
    return str(v)


def compute_very_high_runs(seg_gdf: gpd.GeoDataFrame):
    """
    找出連續 very_high 區段，回傳 [(start_dist, end_dist), ...]
    """
    if seg_gdf.empty:
        return []

    df = seg_gdf.sort_values("seg_start_dist").reset_index(drop=True).copy()
    mask = df["risk_band"] == "very_high"

    runs = []
    run_start = None
    run_end = None

    for i, is_vh in enumerate(mask):
        if is_vh:
            if run_start is None:
                run_start = float(df.loc[i, "seg_start_dist"])
            run_end = float(df.loc[i, "seg_end_dist"])
        else:
            if run_start is not None:
                runs.append((run_start, run_end))
                run_start = None
                run_end = None

    if run_start is not None:
        runs.append((run_start, run_end))

    return runs


def build_segments(merged_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    將相鄰點轉成 line segment
    """
    rows = []

    merged_gdf = merged_gdf.sort_values("dist_m").reset_index(drop=True)

    for i in range(len(merged_gdf) - 1):
        r1 = merged_gdf.iloc[i]
        r2 = merged_gdf.iloc[i + 1]

        g1 = r1.geometry
        g2 = r2.geometry

        if g1 is None or g2 is None:
            continue
        if g1.is_empty or g2.is_empty:
            continue

        line = LineString([g1, g2])

        seg_risk_band = pick_segment_risk_band(r1["risk_band"], r2["risk_band"])
        seg_risk_score = np.nanmean([r1.get("risk_score_smooth", np.nan), r2.get("risk_score_smooth", np.nan)])

        rows.append(
            {
                "seg_id": i,
                "seg_start_dist": float(r1["dist_m"]),
                "seg_end_dist": float(r2["dist_m"]),
                "seg_mid_dist": float((r1["dist_m"] + r2["dist_m"]) / 2.0),
                "risk_band": seg_risk_band,
                "risk_score_smooth": seg_risk_score,
                "risk_reason": safe_text(r1.get("risk_reason", "")),
                "data_quality_reason": safe_text(r1.get("data_quality_reason", "")),
                "route_semantic_class": safe_text(r1.get("route_semantic_class", "")),
                "surface_class": safe_text(r1.get("surface_class", "")),
                "alignment_ok": bool(r1.get("alignment_ok", True)),
                "gpx_quality_flag": safe_text(r1.get("gpx_quality_flag", "")),
                "geometry": line,
            }
        )

    if not rows:
        raise ValueError("無法建立 segment，請檢查輸入資料的 geometry 是否為有效 Point。")

    seg_gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=merged_gdf.crs)
    return seg_gdf


# =========================================================
# D. 主流程
# =========================================================
def main():
    require_file(RISK_CSV)
    require_file(PROFILE_GEOJSON)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1) 讀檔
    risk_df = pd.read_csv(RISK_CSV)
    profile_gdf = gpd.read_file(PROFILE_GEOJSON)

   # 若風險 CSV 尚未包含平滑分數，於本腳本內自行建立
    if "risk_score_smooth" not in risk_df.columns and "risk_score" in risk_df.columns:
        risk_df = risk_df.sort_values("dist_m").reset_index(drop=True)
        risk_df["risk_score_smooth"] = (
            risk_df["risk_score"].rolling(5, center=True, min_periods=2).mean()
        )


    if risk_df.empty:
        raise ValueError(f"風險 CSV 為空：{RISK_CSV}")
    if profile_gdf.empty:
        raise ValueError(f"語意 GeoJSON 為空：{PROFILE_GEOJSON}")

    if profile_gdf.crs is None:
        profile_gdf = profile_gdf.set_crs("EPSG:4326")
    else:
        profile_gdf = profile_gdf.to_crs("EPSG:4326")

    # 2) 欄位檢查
    for col in ["dist_m", "risk_band"]:
        if col not in risk_df.columns:
            raise KeyError(f"RISK CSV 缺少必要欄位：{col}")

    if "dist_m" not in profile_gdf.columns:
        raise KeyError("PROFILE_GEOJSON 缺少必要欄位：dist_m")

    # 3) 避免浮點數 merge 問題，使用四捨五入後的 key
    risk_df = risk_df.copy()
    profile_gdf = profile_gdf.copy()

    risk_df["dist_key"] = risk_df["dist_m"].round(3)
    profile_gdf["dist_key"] = profile_gdf["dist_m"].round(3)

    # 保留 risk CSV 的主要欄位
    risk_keep_cols = [
        "dist_key",
        "dist_m",
        "risk_score",
        "risk_score_smooth",
        "effort_score",
        "effort_score_smooth",
        "exposure_score",
        "exposure_score_smooth",
        "risk_band",
        "risk_reason",
        "data_quality_reason",
        "alignment_ok",
        "gpx_quality_flag",
    ]
    risk_keep_cols = [c for c in risk_keep_cols if c in risk_df.columns]

    risk_sub = risk_df[risk_keep_cols].copy()

    # merge 後保留 geometry 與 semantic 欄位
    merged = profile_gdf.merge(
        risk_sub,
        on="dist_key",
        how="left",
        suffixes=("_geo", "_risk"),
    )

    if merged.empty:
        raise ValueError("合併後資料為空，請檢查 dist_m / dist_key 是否一致。")

    # 4) 整理 dist_m
    if "dist_m_risk" in merged.columns:
        merged["dist_m"] = merged["dist_m_risk"]
    elif "dist_m_geo" in merged.columns:
        merged["dist_m"] = merged["dist_m_geo"]
    elif "dist_m" not in merged.columns:
        raise KeyError("合併後找不到 dist_m 欄位。")

    # 5) 補齊 risk_band
    merged["risk_band"] = merged["risk_band"].apply(normalize_risk_band)

    # 若 route_semantic_class / surface_class 不存在，補空字串
    for col in ["route_semantic_class", "surface_class"]:
        if col not in merged.columns:
            merged[col] = ""

    merged_gdf = gpd.GeoDataFrame(merged, geometry="geometry", crs=profile_gdf.crs)
    merged_gdf = merged_gdf.sort_values("dist_m").reset_index(drop=True)

    # 6) 建立 line segments
    seg_gdf = build_segments(merged_gdf)

    # 7) 計算 very_high 連續區段
    very_high_runs = compute_very_high_runs(seg_gdf)

    # 8) 轉 Web Mercator 方便繪圖
    merged_plot = merged_gdf.to_crs(epsg=3857)
    seg_plot = seg_gdf.to_crs(epsg=3857)

    # 9) 繪圖
    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H), dpi=DPI)

    # 先畫底線
    seg_plot.plot(
        ax=ax,
        color="#D0D0D0",
        linewidth=BASELINE_WIDTH,
        alpha=0.9,
        zorder=1,
    )

    # 再依 risk_band 著色
    for band in ["low", "moderate", "high", "very_high", "unknown"]:
        sub = seg_plot[seg_plot["risk_band"] == band]
        if len(sub) == 0:
            continue
        sub.plot(
            ax=ax,
            color=RISK_COLOR_MAP[band],
            linewidth=LINE_WIDTH,
            alpha=0.95,
            zorder=3,
        )

    # 起點與終點
    start_pt = merged_plot.geometry.iloc[0]
    end_pt = merged_plot.geometry.iloc[-1]

    ax.scatter(
        start_pt.x, start_pt.y,
        s=90, c="#2E7D32", marker="o",
        edgecolors="white", linewidths=1.0, zorder=5
    )
    ax.scatter(
        end_pt.x, end_pt.y,
        s=90, c="#C62828", marker="s",
        edgecolors="white", linewidths=1.0, zorder=5
    )

    ax.annotate(
        "Start",
        xy=(start_pt.x, start_pt.y),
        xytext=(8, 8),
        textcoords="offset points",
        fontsize=ANNOTATION_FONTSIZE,
        color="#1B5E20",
        weight="bold",
        zorder=6,
    )
    ax.annotate(
        "End",
        xy=(end_pt.x, end_pt.y),
        xytext=(8, 8),
        textcoords="offset points",
        fontsize=ANNOTATION_FONTSIZE,
        color="#B71C1C",
        weight="bold",
        zorder=6,
    )

    # 標註 very_high 區段
    for start_dist, end_dist in very_high_runs:
        target = seg_plot[
            (seg_plot["seg_start_dist"] <= end_dist) &
            (seg_plot["seg_end_dist"] >= start_dist) &
            (seg_plot["risk_band"] == "very_high")
        ]
        if len(target) == 0:
            continue

        if hasattr(target.geometry, "union_all"):
            centroid = target.geometry.union_all().centroid
        else:
            centroid = target.unary_union.centroid
        label = f"very_high\n{int(round(start_dist))}–{int(round(end_dist))} m"

        ax.annotate(
            label,
            xy=(centroid.x, centroid.y),
            xytext=(0, 12),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=ANNOTATION_FONTSIZE,
            color="#8E0000",
            weight="bold",
            bbox=dict(
                boxstyle="round,pad=0.25",
                fc="white",
                ec="#D32F2F",
                alpha=0.85,
            ),
            zorder=7,
        )

    # 10) 視覺設定
    ax.set_title(
        "Qixing Route Risk Map (2D)\nRisk-band Segmented Route",
        fontsize=TITLE_FONTSIZE,
        pad=14,
        loc="center",
    )

    ax.set_axis_off()
    ax.set_aspect("equal")

    # 範圍加 padding
    minx, miny, maxx, maxy = seg_plot.total_bounds
    dx = maxx - minx
    dy = maxy - miny
    pad_x = dx * 0.08 if dx > 0 else 50
    pad_y = dy * 0.08 if dy > 0 else 50
    ax.set_xlim(minx - pad_x, maxx + pad_x)
    ax.set_ylim(miny - pad_y, maxy + pad_y)

    # 11) 圖例
    risk_legend_handles = [
        Line2D([0], [0], color=RISK_COLOR_MAP["low"], lw=4, label="low"),
        Line2D([0], [0], color=RISK_COLOR_MAP["moderate"], lw=4, label="moderate"),
        Line2D([0], [0], color=RISK_COLOR_MAP["high"], lw=4, label="high"),
        Line2D([0], [0], color=RISK_COLOR_MAP["very_high"], lw=4, label="very_high"),
    ]

    marker_legend_handles = [
        Line2D([0], [0], marker="o", color="w", label="start",
               markerfacecolor="#2E7D32", markeredgecolor="white", markersize=9),
        Line2D([0], [0], marker="s", color="w", label="end",
               markerfacecolor="#C62828", markeredgecolor="white", markersize=9),
    ]

    leg1 = ax.legend(
        handles=risk_legend_handles,
        title="Risk band",
        loc="lower left",
        frameon=True,
        framealpha=0.95,
    )
    ax.add_artist(leg1)

    ax.legend(
        handles=marker_legend_handles,
        title="Markers",
        loc="lower right",
        frameon=True,
        framealpha=0.95,
    )

    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=DPI, bbox_inches="tight")
    plt.close(fig)

    # 12) 輸出 segment geojson
    seg_gdf.to_file(OUT_GEOJSON, driver="GeoJSON")

    # 13) Console summary
    print("完成！")
    print("PNG:", OUT_PNG.resolve())
    print("segment GeoJSON:", OUT_GEOJSON.resolve())
    print()
    print("=== merged point summary ===")
    print("points:", len(merged_gdf))
    print("segments:", len(seg_gdf))
    print("risk_band:")
    print(merged_gdf["risk_band"].value_counts(dropna=False))
    print()
    
    print("(note: 2D map runs are based on 20 m profile-point segments, not 100 m aggregated segments)")
    print("=== very_high runs ===")
    if very_high_runs:
        for s, e in very_high_runs:
            print(f"{int(round(s))}–{int(round(e))} m")
    else:
        print("無")


if __name__ == "__main__":
    main()