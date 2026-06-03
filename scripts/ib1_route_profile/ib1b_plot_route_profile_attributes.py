# =========================================================
# ib1b_plot_route_profile_attributes.py
# 讀取 ib1a route profile，疊加 ib0b mainline 的 OSM 路段屬性
# 輸出海拔剖面圖 + highway / mainline_role / technical 色帶
# =========================================================

from pathlib import Path

import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch


# =========================================================
# 0. 路徑設定
# =========================================================
CASE_ID = "qixing_xiaoyoukeng_roundtrip_joyhike"

PROFILE_CSV = (
    Path("ib1a_route_elevation_profile_output")
    / CASE_ID
    / "qixing_route_profile.csv"
)

PROFILE_GEOJSON = (
    Path("ib1a_route_elevation_profile_output")
    / CASE_ID
    / "qixing_route_profile_points.geojson"
)

MAINLINE_FP = (
    Path("ib0b_output")
    / CASE_ID
    / f"{CASE_ID}_mainline.geojson"
)

OUT_DIR = Path("ib1b_route_profile_attribute_output") / CASE_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_PNG = OUT_DIR / "qixing_route_profile_with_osm_attributes.png"
OUT_ATTR_CSV = OUT_DIR / "qixing_route_profile_with_osm_attributes.csv"

# =========================================================
# 1. 參數
# =========================================================
ELEVATION_COL = "ele_gpx_m"   # 可改成 "ele_smooth"

HIGHWAY_COLOR = {
    "steps": "#e74c3c",
    "footway": "#2ecc71",
    "path": "#f39c12",
    "service": "#95a5a6",
    "tertiary": "#7f8c8d",
    "residential": "#bdc3c7",
    "track": "#8e44ad",
    "ladder": "#9b59b6",
    "unknown": "#d0d0d0",
}

ROLE_COLOR = {
    "trail_core": "#d62728",
    "approach": "#ff9800",
    "unknown": "#aaaaaa",
}

TECH_COLOR = {
    "steps": "#e74c3c",
    "ladder": "#8e44ad",
    "rope": "#f1c40f",
    "normal": "#ecf0f1",
}


# =========================================================
# 2. 檢查輸入
# =========================================================
for fp in [PROFILE_CSV, PROFILE_GEOJSON, MAINLINE_FP]:
    if not fp.exists():
        raise FileNotFoundError(f"找不到檔案：{fp.resolve()}")


# =========================================================
# 3. 工具函式
# =========================================================
def build_runs(df, col):
    runs = []
    start_idx = 0
    values = df[col].tolist()

    for i in range(1, len(values)):
        if values[i] != values[start_idx]:
            runs.append((start_idx, i - 1, values[start_idx]))
            start_idx = i

    runs.append((start_idx, len(values) - 1, values[start_idx]))
    return runs


def classify_technical(seg):
    hw = str(seg.get("highway_norm", "")).lower()

    if hw == "steps":
        return "steps"

    ladder = str(seg.get("ladder", "")).lower()
    safety_rope = str(seg.get("safety_rope", "")).lower()

    if ladder in ["yes", "true", "1"]:
        return "ladder"

    if safety_rope in ["yes", "true", "1"]:
        return "rope"

    # fallback：避免欄位不存在時完全漏掉
    seg_text = str(seg).lower()

    if "ladder" in seg_text:
        return "ladder"

    if "rope" in seg_text or "safety_rope" in seg_text:
        return "rope"

    return "normal"


# =========================================================
# 4. 讀資料
# =========================================================
profile_df = pd.read_csv(PROFILE_CSV)
profile_pts = gpd.read_file(PROFILE_GEOJSON).to_crs("EPSG:4326")
mainline = gpd.read_file(MAINLINE_FP).to_crs("EPSG:4326")

metric_crs = mainline.estimate_utm_crs()
profile_pts_m = profile_pts.to_crs(metric_crs)
mainline_m = mainline.to_crs(metric_crs)

if ELEVATION_COL not in profile_df.columns:
    raise ValueError(f"profile CSV 沒有欄位：{ELEVATION_COL}")


has_elevation = profile_df[ELEVATION_COL].notna().any()

print("has_elevation:", has_elevation)
if not has_elevation:
    print("警告：profile 沒有可用 GPX 高程，ib1b 將只輸出 OSM attribute 色帶與距離軸 QA。")

# =========================================================
# 5. 將每個 profile point 對應最近的 OSM mainline segment
# =========================================================
matched_rows = []

for i, pt in profile_pts_m.iterrows():
    dists = mainline_m.geometry.distance(pt.geometry)
    nearest_idx = dists.idxmin()
    seg = mainline.loc[nearest_idx]

    highway = str(seg.get("highway_norm", "unknown")).lower()
    role = str(seg.get("mainline_role", "unknown")).lower()

    matched_rows.append({
        "sample_idx": i,
        "nearest_mainline_idx": nearest_idx,
        "nearest_segment_dist_m": float(dists.loc[nearest_idx]),
        "highway_norm": highway if highway else "unknown",
        "mainline_role": role if role else "unknown",
        "technical": classify_technical(seg),
        "osm_way_id": seg.get("osm_way_id", ""),
        "name": seg.get("name", ""),
    })

attr_df = pd.DataFrame(matched_rows)

plot_df = profile_df.copy()
plot_df["highway_norm"] = attr_df["highway_norm"].values
plot_df["mainline_role"] = attr_df["mainline_role"].values
plot_df["technical"] = attr_df["technical"].values
plot_df["nearest_segment_dist_m"] = attr_df["nearest_segment_dist_m"].values
plot_df["osm_way_id"] = attr_df["osm_way_id"].values
plot_df["name"] = attr_df["name"].values


# =========================================================
# 6. 產生連續區段，用於色帶
# =========================================================
highway_runs = build_runs(plot_df, "highway_norm")
role_runs = build_runs(plot_df, "mainline_role")
tech_runs = build_runs(plot_df, "technical")


# =========================================================
# 7. 繪圖
# =========================================================
fig, (ax1, ax2, ax3, ax4) = plt.subplots(
    4,
    1,
    figsize=(16, 9),
    sharex=True,
    gridspec_kw={"height_ratios": [5, 0.5, 0.5, 0.5]}
)

# ---------------------------------------------------------
# 7a. 海拔剖面
# ---------------------------------------------------------
ax1.plot(
    plot_df["dist_m"],
    plot_df[ELEVATION_COL],
    linewidth=1.8,
    label=ELEVATION_COL,
)

ax1.set_ylabel("Elevation (m)")
ax1.set_title("Qixing Route Elevation Profile with OSM Attributes")
ax1.grid(True, alpha=0.3)

if has_elevation:
    ax1.plot(
        plot_df["dist_m"],
        plot_df[ELEVATION_COL],
        linewidth=1.8,
        label=ELEVATION_COL,
    )
    ax1.set_ylabel("Elevation (m)")
    ax1.set_title("Qixing Route Elevation Profile with OSM Attributes")
else:
    ax1.plot(
        plot_df["dist_m"],
        [0] * len(plot_df),
        linewidth=1.2,
        label="route distance axis only",
    )
    ax1.set_ylabel("Elevation unavailable")
    ax1.set_title("Qixing Route Distance Axis with OSM Attributes")

ax1.grid(True, alpha=0.3)

# ---------------------------------------------------------
# 7b. 道路類型色帶
# ---------------------------------------------------------
for s, e, hw in highway_runs:
    x0 = plot_df.loc[s, "dist_m"]
    x1 = plot_df.loc[e, "dist_m"]

    if e + 1 < len(plot_df):
        x1 = plot_df.loc[e + 1, "dist_m"]

    ax2.broken_barh(
        [(x0, x1 - x0)],
        (0, 1),
        facecolors=HIGHWAY_COLOR.get(hw, HIGHWAY_COLOR["unknown"]),
    )

ax2.set_yticks([0.5])
ax2.set_yticklabels(["highway"])
ax2.set_ylim(0, 1)
ax2.grid(False)


# ---------------------------------------------------------
# 7c. mainline_role 色帶
# ---------------------------------------------------------
for s, e, role in role_runs:
    x0 = plot_df.loc[s, "dist_m"]
    x1 = plot_df.loc[e, "dist_m"]

    if e + 1 < len(plot_df):
        x1 = plot_df.loc[e + 1, "dist_m"]

    ax3.broken_barh(
        [(x0, x1 - x0)],
        (0, 1),
        facecolors=ROLE_COLOR.get(role, ROLE_COLOR["unknown"]),
    )

ax3.set_yticks([0.5])
ax3.set_yticklabels(["role"])
ax3.set_ylim(0, 1)
ax3.grid(False)


# ---------------------------------------------------------
# 7d. 技術難度色帶
# ---------------------------------------------------------
for s, e, tech in tech_runs:
    x0 = plot_df.loc[s, "dist_m"]
    x1 = plot_df.loc[e, "dist_m"]

    if e + 1 < len(plot_df):
        x1 = plot_df.loc[e + 1, "dist_m"]

    ax4.broken_barh(
        [(x0, x1 - x0)],
        (0, 1),
        facecolors=TECH_COLOR.get(tech, TECH_COLOR["normal"]),
    )

ax4.set_yticks([0.5])
ax4.set_yticklabels(["tech"])
ax4.set_ylim(0, 1)
ax4.set_xlabel("Distance (m)")
ax4.grid(False)


# =========================================================
# 8. 圖例
# =========================================================
used_highways = sorted(plot_df["highway_norm"].dropna().unique())
highway_legend = [
    Patch(
        facecolor=HIGHWAY_COLOR.get(hw, HIGHWAY_COLOR["unknown"]),
        label=f"highway: {hw}",
    )
    for hw in used_highways
]

used_roles = sorted(plot_df["mainline_role"].dropna().unique())
role_legend = [
    Patch(
        facecolor=ROLE_COLOR.get(role, ROLE_COLOR["unknown"]),
        label=f"role: {role}",
    )
    for role in used_roles
]

used_tech = sorted(plot_df["technical"].dropna().unique())
tech_legend = [
    Patch(
        facecolor=TECH_COLOR.get(tech, TECH_COLOR["normal"]),
        label=f"tech: {tech}",
    )
    for tech in used_tech
]

ax1.legend(
    handles=[*highway_legend, *role_legend, *tech_legend],
    loc="upper right",
    fontsize=8,
    ncol=3,
)

plt.tight_layout()
plt.savefig(OUT_PNG, dpi=200)
plt.close()


# =========================================================
# 9. 另存帶屬性的 profile CSV
# =========================================================
plot_df.to_csv(OUT_ATTR_CSV, index=False, encoding="utf-8-sig")

print("完成！")
print("profile attribute CSV:", OUT_ATTR_CSV.resolve())
print("profile attribute PNG:", OUT_PNG.resolve())

print("\n--- highway distribution ---")
print(plot_df["highway_norm"].value_counts(dropna=False))

print("\n--- mainline_role distribution ---")
print(plot_df["mainline_role"].value_counts(dropna=False))

print("\n--- technical distribution ---")
print(plot_df["technical"].value_counts(dropna=False))