from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches


# =========================================================
# 路徑設定
# =========================================================
INPUT_CSV = Path("ib2_v2_route_risk_output/qixing_route_risk_v2.csv")

OUT_DIR = Path("ib2a_risk_profile_output")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_PNG = OUT_DIR / "qixing_route_risk_profile.png"
OUT_CSV = OUT_DIR / "qixing_route_risk_profile_plot_data.csv"


# =========================================================
# 讀資料
# =========================================================
if not INPUT_CSV.exists():
    raise FileNotFoundError(INPUT_CSV)

df = pd.read_csv(INPUT_CSV)

if df.empty:
    raise ValueError("輸入 CSV 為空")

required_cols = ["dist_m", "risk_score", "risk_band"]
for c in required_cols:
    if c not in df.columns:
        raise ValueError(f"缺少欄位: {c}")

df = df.sort_values("dist_m").reset_index(drop=True)

# =========================================================
# 欄位容錯：新版 ib2_v2 才會有 effort / exposure
# =========================================================
if "effort_score" not in df.columns:
    print("警告：缺少 effort_score，將以 0 顯示")
    df["effort_score"] = 0.0

if "exposure_score" not in df.columns:
    print("警告：缺少 exposure_score，將以 0 顯示")
    df["exposure_score"] = 0.0

if "terrain_score" not in df.columns:
    df["terrain_score"] = df["effort_score"] + df["exposure_score"]

if "gpx_quality_flag" not in df.columns:
    df["gpx_quality_flag"] = "unknown"

if "alignment_ok" not in df.columns:
    df["alignment_ok"] = True


# =========================================================
# 欄位容錯：新版 ib2_v2 已帶入 ib1c 的 OSM route semantics
# =========================================================
if "route_semantic_class" not in df.columns:
    df["route_semantic_class"] = "unknown_route_type"

if "surface_class" not in df.columns:
    df["surface_class"] = "unknown_surface"

if "risk_confidence" not in df.columns:
    df["risk_confidence"] = "unknown"

if "data_quality_reason" not in df.columns:
    df["data_quality_reason"] = "normal"

# =========================================================
# 顏色設定
# =========================================================
RISK_COLOR = {
    "low": "#2ca25f",
    "moderate": "#fec44f",
    "high": "#fc8d59",
    "very_high": "#d7301f",
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

def build_runs(df, col):
    runs = []
    start = 0
    values = df[col].tolist()

    for i in range(1, len(values)):
        if values[i] != values[start]:
            runs.append((start, i - 1, values[start]))
            start = i

    runs.append((start, len(values) - 1, values[start]))
    return runs

def draw_category_strip(ax, df, col, color_map, label):
    """
    依 dist_m 將類別欄位畫成底部色帶。
    """
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    ax.set_ylabel(label, rotation=0, ha="right", va="center", labelpad=55)
    ax.grid(False)

    for s, e, value in build_runs(df, col):
        x0 = df.iloc[s]["dist_m"]
        x1 = df.iloc[e]["dist_m"]

        if e + 1 < len(df):
            x1 = df.iloc[e + 1]["dist_m"]

        color = color_map.get(str(value), "#dddddd")
        ax.axvspan(x0, x1, ymin=0, ymax=1, color=color, alpha=0.95)

    ax.set_xlim(df["dist_m"].min(), df["dist_m"].max())

    used_values = [v for v in df[col].dropna().unique().tolist()]
    handles = [
        mpatches.Patch(
            color=color_map.get(str(v), "#dddddd"),
            label=str(v),
        )
        for v in used_values
    ]

    return handles

# =========================================================
# 畫圖
# =========================================================

df["risk_score_smooth"] = (
    df["risk_score"].rolling(5, center=True, min_periods=2).mean()
)

df["effort_score_smooth"] = (
    df["effort_score"].rolling(5, center=True, min_periods=2).mean()
)

df["exposure_score_smooth"] = (
    df["exposure_score"].rolling(5, center=True, min_periods=2).mean()
)

fig, (ax1, ax_route, ax_surface) = plt.subplots(
    nrows=3,
    ncols=1,
    figsize=(14, 7.2),
    sharex=True,
    gridspec_kw={"height_ratios": [5.0, 0.35, 0.35]},
)

# --- risk_band 背景 ---
for s, e, band in build_runs(df, "risk_band"):
    x0 = df.iloc[s]["dist_m"]
    x1 = df.iloc[e]["dist_m"]

    if e + 1 < len(df):
        x1 = df.iloc[e + 1]["dist_m"]

    ax1.axvspan(
        x0,
        x1,
        color=RISK_COLOR.get(band, "#cccccc"),
        alpha=0.2,
    )

# --- risk_score 曲線 ---
ax1.plot(
    df["dist_m"],
    df["risk_score_smooth"],
    linewidth=2,
    color="black",
    label="risk_score_smooth",
)

# --- effort / exposure score 曲線 ---
ax1.plot(
    df["dist_m"],
    df["effort_score_smooth"],
    linewidth=1.6,
    linestyle="--",
    label="effort_score_smooth",
)

ax1.plot(
    df["dist_m"],
    df["exposure_score_smooth"],
    linewidth=1.6,
    linestyle=":",
    label="exposure_score_smooth",
)

ax1.set_ylabel("Risk Score")
ax1.grid(True, alpha=0.3)


# --- GPX/Contour mismatch 標記 ---
mismatch_df = df[df["gpx_quality_flag"] == "mismatch"]
if not mismatch_df.empty:
    ax1.scatter(
        mismatch_df["dist_m"],
        mismatch_df["risk_score"],
        s=18,
        marker="x",
        label="gpx-contour mismatch",
    )

# --- distance alignment issue 標記 ---
bad_align_df = df[df["alignment_ok"] == False]
if not bad_align_df.empty:
    ax1.scatter(
        bad_align_df["dist_m"],
        bad_align_df["risk_score"],
        s=28,
        marker="o",
        facecolors="none",
        label="distance misaligned",
    )


# --- elevation 疊加 ---
if "ele_gpx_m" in df.columns:
    ax2 = ax1.twinx()
    ax2.plot(
        df["dist_m"],
        df["ele_gpx_m"],
        color="blue",
        linewidth=1.5,
        label="elevation",
        alpha=0.6,
    )
    ax2.set_ylabel("Elevation (m)")


# --- legend ---
lines1, labels1 = ax1.get_legend_handles_labels()

if "ele_gpx_m" in df.columns:
    lines2, labels2 = ax2.get_legend_handles_labels()
    main_lines = lines1 + lines2
    main_labels = labels1 + labels2
else:
    main_lines = lines1
    main_labels = labels1

#ax1.legend(
#    main_lines,
#    main_labels,
#    loc="upper left",
#    bbox_to_anchor=(1.01, 1.0),
#    ncol=1,
#    fontsize=8,
#    frameon=True,
#)

# --- OSM route semantic strip ---
route_handles = draw_category_strip(
    ax_route,
    df,
    "route_semantic_class",
    ROUTE_CLASS_COLOR,
    "Route type",
)

# --- OSM surface class strip ---
surface_handles = draw_category_strip(
    ax_surface,
    df,
    "surface_class",
    SURFACE_CLASS_COLOR,
    "Surface",
)

ax_surface.set_xlabel("Distance (m)")

# ===== Figure-level legends =====

# 主圖圖例：放在下方靠左
fig.legend(
    handles=main_lines,
    labels=main_labels,
    loc="lower left",
    bbox_to_anchor=(0.06, 0.02),
    ncol=3,
    fontsize=8,
    frameon=True,
)

# OSM 圖例：放在下方靠右
fig.legend(
    handles=route_handles + surface_handles,
    loc="lower right",
    bbox_to_anchor=(0.94, 0.02),
    ncol=5,
    fontsize=8,
    frameon=True,
)

# 標題（置中）
fig.suptitle(
    "Route Risk Profile\n"
    "Risk, Elevation, and OSM Route Semantics",
    y=0.98,
    fontsize=14,
)

# 版面配置：上方留標題、下方留兩組圖例
plt.tight_layout(rect=[0.03, 0.12, 0.97, 0.86])

plt.savefig(OUT_PNG, dpi=200, bbox_inches="tight")
plt.close()


# =========================================================
# 輸出
# =========================================================
print("完成！")

plot_cols = [
    "dist_m",
    "ele_gpx_m",
    "risk_score",
    "risk_score_smooth",
    "risk_band",
    "effort_score",
    "effort_score_smooth",
    "exposure_score",
    "exposure_score_smooth",
    "terrain_score",
    "gpx_quality_flag",
    "alignment_ok",
    "risk_confidence",
    "data_quality_reason",
    "risk_reason",

    # OSM route semantics
    "osm_way_name",
    "osm_highway",
    "osm_surface",
    "route_semantic_class",
    "surface_class",
    "assist_class",
    "visibility_class",
    "osm_difficulty_class",
]

plot_cols = [c for c in plot_cols if c in df.columns]
df[plot_cols].to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

print("PNG:", OUT_PNG.resolve())
print("plot CSV:", OUT_CSV.resolve())

print("\n=== gpx_quality_flag ===")
print(df["gpx_quality_flag"].value_counts(dropna=False))

print("\n=== alignment_ok ===")
print(df["alignment_ok"].value_counts(dropna=False))

print("\n=== score summary ===")
summary_cols = [
    "risk_score",
    "risk_score_smooth",
    "effort_score",
    "exposure_score",
    "terrain_score",
]
summary_cols = [c for c in summary_cols if c in df.columns]
print(df[summary_cols].describe())

print("\n=== risk_band ===")
print(df["risk_band"].value_counts())

print("\n=== route_semantic_class ===")
print(df["route_semantic_class"].value_counts(dropna=False))

print("\n=== surface_class ===")
print(df["surface_class"].value_counts(dropna=False))