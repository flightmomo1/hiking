# =========================================================
# ib0d_trim_ordered_mainline_by_anchors_v1.1.py
#
# 目的：
# - 讀取 ib0b ordered mainline
# - 讀取 ib0c start / end anchors
# - 將 start / end anchor 投影到 ordered path 上
# - 自動判斷 point-to-point 或 same-entry-exit 路線
# - point-to-point：依 start/end 投影距離裁切 ordered path
# - same-entry-exit / out-and-back：保留完整 ordered path
# - 輸出 trimmed ordered mainline，供 ib1a 使用
# =========================================================
 
from pathlib import Path

import pandas as pd
import geopandas as gpd
import folium
from shapely.geometry import LineString, Point


# =========================================================
# 0. 路徑設定
# =========================================================
PROJECT_ROOT = Path(r"C:\mountain_work\115_osm")

# ROUTE_ID = "qixing_xiaoyoukeng_roundtrip_joyhike"
# ROUTE_GROUP = "qixing_xiaoyoukeng_roundtrip"
# CASE_NAME = "七星山小油坑進出 Joyhike"

ROUTE_ID = "juansi_waterfall_fitcsv_20260503"
ROUTE_GROUP = "juansi_waterfall"
CASE_NAME = "絹絲瀑布 FIT CSV 20260503"

IB0B_STAGE = "ib0b_mainline"
IB0C_STAGE = "ib0c_anchor"
IB0D_STAGE = "ib0d_trimmed_mainline"

IB0B_DIR = PROJECT_ROOT / "outputs" / IB0B_STAGE / ROUTE_ID
IB0C_DIR = PROJECT_ROOT / "outputs" / IB0C_STAGE / ROUTE_ID
OUT_DIR = PROJECT_ROOT / "outputs" / IB0D_STAGE / ROUTE_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)

ORDERED_PATH_FP = IB0B_DIR / f"{ROUTE_ID}_mainline_ordered_path.geojson"
ANCHOR_FP = IB0C_DIR / f"{ROUTE_ID}_route_anchors.geojson"

OUT_TRIMMED_GEOJSON = OUT_DIR / f"{ROUTE_ID}_mainline_ordered_path_trimmed.geojson"
OUT_SUMMARY_CSV = OUT_DIR / f"{ROUTE_ID}_mainline_trim_summary.csv"
OUT_HTML = OUT_DIR / f"{ROUTE_ID}_mainline_ordered_path_trimmed_map.html"


# =========================================================
# 1. 參數
# =========================================================
# 是否在 start/end anchor 外再保留一點 buffer
# 先設 0，代表精準依 anchor 投影位置裁切
TRIM_BUFFER_M = 0.0

# 如果 start/end anchor 離 ordered path 太遠，印出警告
ANCHOR_TO_LINE_WARN_M = 50.0


# =========================================================
# 2. 工具函式
# =========================================================
def get_single_linestring(gdf: gpd.GeoDataFrame) -> LineString:
    """
    取得單一 ordered path LineString。
    ib0b ordered path 正常應該只有一筆 LineString。
    """
    if gdf.empty:
        raise ValueError("ordered path GeoDataFrame 為空")

    geom = gdf.geometry.iloc[0]

    if geom is None or geom.is_empty:
        raise ValueError("ordered path geometry 為空")

    if geom.geom_type == "LineString":
        return geom

    if geom.geom_type == "MultiLineString":
        # 若意外是 MultiLineString，先取所有座標串接
        coords = []
        for part in geom.geoms:
            part_coords = list(part.coords)
            if not coords:
                coords.extend(part_coords)
            else:
                # 避免重複端點
                if coords[-1] == part_coords[0]:
                    coords.extend(part_coords[1:])
                else:
                    coords.extend(part_coords)
        return LineString(coords)

    raise ValueError(f"不支援的 ordered path geometry type：{geom.geom_type}")


def cut_line_between(line: LineString, start_d: float, end_d: float) -> LineString:
    """
    依線上距離裁切 LineString。
    不依賴 shapely.ops.substring，避免版本差異。
    """
    if end_d <= start_d:
        raise ValueError(f"end_d 必須大於 start_d，目前 start={start_d}, end={end_d}")

    coords = list(line.coords)
    new_pts = []

    # 加入 start 插值點
    start_pt = line.interpolate(start_d)
    end_pt = line.interpolate(end_d)
    new_pts.append((start_pt.x, start_pt.y))

    acc = 0.0

    for i in range(len(coords) - 1):
        p0 = Point(coords[i])
        p1 = Point(coords[i + 1])
        seg = LineString([p0, p1])
        seg_len = seg.length

        seg_start = acc
        seg_end = acc + seg_len

        # 若原始節點落在 start/end 之間，保留
        if seg_start > start_d and seg_start < end_d:
            new_pts.append((p0.x, p0.y))

        if seg_end > start_d and seg_end < end_d:
            new_pts.append((p1.x, p1.y))

        acc = seg_end

    # 加入 end 插值點
    new_pts.append((end_pt.x, end_pt.y))

    # 去除連續重複點
    dedup = []
    for pt in new_pts:
        if not dedup or pt != dedup[-1]:
            dedup.append(pt)

    if len(dedup) < 2:
        raise ValueError("裁切後點數不足，無法建立 LineString")

    return LineString(dedup)


def anchor_point_by_role(anchors_gdf: gpd.GeoDataFrame, role: str):
    rows = anchors_gdf[anchors_gdf["anchor_role"].astype(str).str.lower() == role]
    if rows.empty:
        raise ValueError(f"找不到 anchor_role={role}")
    return rows.geometry.iloc[0], rows.iloc[0]


# =========================================================
# 3. 輸入檢查
# =========================================================
if not ORDERED_PATH_FP.exists():
    raise FileNotFoundError(f"找不到 ordered path：{ORDERED_PATH_FP.resolve()}，請先執行 ib0b")

if not ANCHOR_FP.exists():
    raise FileNotFoundError(f"找不到 anchors：{ANCHOR_FP.resolve()}，請先執行 ib0c")


# =========================================================
# 4. 讀資料
# =========================================================
ordered_gdf = gpd.read_file(ORDERED_PATH_FP)

if ordered_gdf.crs is None:
    ordered_gdf = ordered_gdf.set_crs("EPSG:4326")

anchors = gpd.read_file(ANCHOR_FP)

if anchors.crs is None:
    anchors = anchors.set_crs("EPSG:4326")

# 使用 ordered path 的 UTM 作為公尺座標
metric_crs = ordered_gdf.estimate_utm_crs()

ordered_m = ordered_gdf.to_crs(metric_crs)
anchors_m = anchors.to_crs(metric_crs)

ordered_line_m = get_single_linestring(ordered_m)
original_len_m = ordered_line_m.length

print("ordered path input:", ORDERED_PATH_FP.resolve())
print("anchors input:", ANCHOR_FP.resolve())
print("metric CRS:", metric_crs)
print(f"original ordered path length m: {original_len_m:.2f}")


# =========================================================
# 5. 取得 start / end anchors 並投影到 ordered path
# =========================================================
start_pt_m, start_row = anchor_point_by_role(anchors_m, "start")
end_pt_m, end_row = anchor_point_by_role(anchors_m, "end")

start_proj_m = ordered_line_m.project(start_pt_m)
end_proj_m = ordered_line_m.project(end_pt_m)

start_snap_pt_m = ordered_line_m.interpolate(start_proj_m)
end_snap_pt_m = ordered_line_m.interpolate(end_proj_m)

start_offset_m = start_pt_m.distance(start_snap_pt_m)
end_offset_m = end_pt_m.distance(end_snap_pt_m)

# 確保距離順序正確
trim_start_m = min(start_proj_m, end_proj_m)
trim_end_m = max(start_proj_m, end_proj_m)

trim_start_m = max(0.0, trim_start_m - TRIM_BUFFER_M)
trim_end_m = min(original_len_m, trim_end_m + TRIM_BUFFER_M)

# =========================================================
# 5b. 自動判斷裁切模式
# =========================================================
MIN_TRIM_LENGTH_M = 30.0
same_entry_exit = (trim_end_m - trim_start_m) < MIN_TRIM_LENGTH_M

if same_entry_exit:
    TRIM_MODE = "same_entry_exit_keep_full_ordered_path"
    trim_start_m = 0.0
    trim_end_m = original_len_m
    trim_reason = (
        "start/end anchors project to nearly same position; "
        "treated as same-entry-exit or out-and-back route, "
        "keep full ordered path."
    )
else:
    TRIM_MODE = "point_to_point_anchor_trim"
    trim_reason = "start/end anchors are different; trim between projected anchor distances."

print("\n=== anchor projection ===")
print(f"start anchor source: {start_row.get('anchor_source', '')}")
print(f"start anchor name: {start_row.get('anchor_name', '')}")
print(f"start projected dist m: {start_proj_m:.2f}")
print(f"start offset to ordered path m: {start_offset_m:.2f}")

print(f"end anchor source: {end_row.get('anchor_source', '')}")
print(f"end anchor name: {end_row.get('anchor_name', '')}")
print(f"end projected dist m: {end_proj_m:.2f}")
print(f"end offset to ordered path m: {end_offset_m:.2f}")

if start_offset_m > ANCHOR_TO_LINE_WARN_M:
    print(f"警告：start anchor 離 ordered path 較遠：{start_offset_m:.2f} m")

if end_offset_m > ANCHOR_TO_LINE_WARN_M:
    print(f"警告：end anchor 離 ordered path 較遠：{end_offset_m:.2f} m")

print("\n=== trim range ===")
print(f"trim_start_m: {trim_start_m:.2f}")
print(f"trim_end_m: {trim_end_m:.2f}")
print(f"trim removed head m: {trim_start_m:.2f}")
print(f"trim removed tail m: {original_len_m - trim_end_m:.2f}")

print("\n=== trim mode ===")
print(f"trim mode: {TRIM_MODE}")
print(f"same_entry_exit: {same_entry_exit}")
print(f"trim reason: {trim_reason}")


# =========================================================
# 6. 裁切 ordered path
# =========================================================
trimmed_line_m = cut_line_between(ordered_line_m, trim_start_m, trim_end_m)
trimmed_len_m = trimmed_line_m.length

trimmed_gdf_m = gpd.GeoDataFrame(
    [
        {
            "source": "ib0d_trim_ordered_mainline_by_anchors",
            "input_ordered_path": str(ORDERED_PATH_FP),
            "input_anchor": str(ANCHOR_FP),
            "original_len_m": original_len_m,
            "trim_start_m": trim_start_m,
            "trim_end_m": trim_end_m,
            "trimmed_len_m": trimmed_len_m,
            "removed_head_m": trim_start_m,
            "removed_tail_m": original_len_m - trim_end_m,
            "start_anchor_source": start_row.get("anchor_source", ""),
            "start_anchor_name": start_row.get("anchor_name", ""),
            "start_anchor_offset_m": start_offset_m,
            "end_anchor_source": end_row.get("anchor_source", ""),
            "end_anchor_name": end_row.get("anchor_name", ""),
            "end_anchor_offset_m": end_offset_m,
            "geometry": trimmed_line_m,
            "trim_mode": TRIM_MODE,
            "trim_reason": trim_reason,
            "is_same_entry_exit": same_entry_exit,
        }
    ],
    geometry="geometry",
    crs=metric_crs,
)

trimmed_gdf = trimmed_gdf_m.to_crs("EPSG:4326")
trimmed_gdf.to_file(OUT_TRIMMED_GEOJSON, driver="GeoJSON")

print(f"\ntrimmed ordered path 輸出：{OUT_TRIMMED_GEOJSON.resolve()}")
print(f"trimmed length m: {trimmed_len_m:.2f}")


# =========================================================
# 7. Summary CSV
# =========================================================
summary = {
    "input_ordered_path": str(ORDERED_PATH_FP),
    "input_anchor": str(ANCHOR_FP),
    "trim_mode": TRIM_MODE,
    "trim_reason": trim_reason,
    "is_same_entry_exit": same_entry_exit,
    "original_len_m": original_len_m,
    "start_proj_m": start_proj_m,
    "end_proj_m": end_proj_m,
    "start_end_proj_diff_m": abs(start_proj_m - end_proj_m),
    "trim_start_m": trim_start_m,
    "trim_end_m": trim_end_m,
    "trimmed_len_m": trimmed_len_m,
    "removed_head_m": trim_start_m,
    "removed_tail_m": original_len_m - trim_end_m,
    "start_anchor_source": start_row.get("anchor_source", ""),
    "start_anchor_name": start_row.get("anchor_name", ""),
    "start_anchor_offset_m": start_offset_m,
    "end_anchor_source": end_row.get("anchor_source", ""),
    "end_anchor_name": end_row.get("anchor_name", ""),
    "end_anchor_offset_m": end_offset_m,
}

pd.DataFrame([summary]).to_csv(
    OUT_SUMMARY_CSV,
    index=False,
    encoding="utf-8-sig",
)

print(f"summary 輸出：{OUT_SUMMARY_CSV.resolve()}")


# =========================================================
# 8. QA HTML
# =========================================================
ordered_wgs84 = ordered_m.to_crs("EPSG:4326")
trimmed_wgs84 = trimmed_gdf
anchors_wgs84 = anchors.to_crs("EPSG:4326")

center_geom = trimmed_wgs84.geometry.iloc[0].centroid
center = [center_geom.y, center_geom.x]

m = folium.Map(
    location=center,
    zoom_start=15,
    tiles="CartoDB positron",
    width="100%",
    height="800px",
)

# 原 ordered path：灰色
folium.GeoJson(
    ordered_wgs84,
    name="original ordered path",
    style_function=lambda feat: {
        "color": "gray",
        "weight": 4,
        "opacity": 0.45,
    },
).add_to(m)

# trimmed path：紅色
folium.GeoJson(
    trimmed_wgs84,
    name="trimmed ordered path",
    style_function=lambda feat: {
        "color": "red",
        "weight": 6,
        "opacity": 0.9,
    },
).add_to(m)

# anchors
for _, row in anchors_wgs84.iterrows():
    role = str(row.get("anchor_role", ""))
    color = {
        "start": "green",
        "via": "blue",
        "end": "red",
    }.get(role, "purple")

    popup = (
        f"<pre>"
        f"role: {row.get('anchor_role', '')}\n"
        f"source: {row.get('anchor_source', '')}\n"
        f"name: {row.get('anchor_name', '')}\n"
        f"distance_to_gpx_m: {row.get('distance_to_gpx_m', '')}"
        f"</pre>"
    )

    folium.Marker(
        location=[row.geometry.y, row.geometry.x],
        popup=folium.Popup(popup, max_width=300),
        icon=folium.Icon(color=color),
    ).add_to(m)

folium.LayerControl(collapsed=False).add_to(m)
m.save(OUT_HTML)

print(f"QA map 輸出：{OUT_HTML.resolve()}")