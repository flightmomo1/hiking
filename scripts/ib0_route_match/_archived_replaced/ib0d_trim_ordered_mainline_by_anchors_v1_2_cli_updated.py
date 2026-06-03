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
import argparse

import pandas as pd
import geopandas as gpd
import folium
from shapely.geometry import LineString, Point


# =========================================================
# 0. 路徑設定
# =========================================================
PROJECT_ROOT = Path(r"C:\mountain_work\115_osm")


def resolve_path(value, project_root=PROJECT_ROOT):
    if value is None:
        return None
    p = Path(value)
    if p.is_absolute():
        return p
    return project_root / p


def parse_args():
    parser = argparse.ArgumentParser(
        description="ib0d: trim ib0b ordered mainline by ib0c start/end anchors"
    )
    parser.add_argument("--case-id", default="qixing_xiaoyoukeng_roundtrip_joyhike")
    parser.add_argument(
        "--ordered-path-fp",
        default=None,
        help="ib0b ordered path GeoJSON. Default: outputs/ib0b_mainline/<case-id>/<case-id>_mainline_ordered_path.geojson",
    )
    parser.add_argument(
        "--anchor-fp",
        default=None,
        help="ib0c route anchors GeoJSON. Default: outputs/ib0c_anchor/<case-id>/<case-id>_route_anchors.geojson",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Output folder. Default: outputs/ib0d_trimmed_mainline/<case-id>",
    )
    parser.add_argument("--trim-buffer-m", type=float, default=0.0)
    parser.add_argument("--anchor-to-line-warn-m", type=float, default=50.0)
    parser.add_argument("--min-trim-length-m", type=float, default=30.0)
    parser.add_argument(
        "--same-entry-policy",
        default="keep_full",
        choices=["keep_full", "trim_leading", "trim_between_first_last_anchor"],
        help=(
            "same-entry-exit / out-and-back route trimming policy. "
            "keep_full keeps the full ordered path; "
            "trim_leading removes leading spur before the entry anchor if it exceeds threshold; "
            "trim_between_first_last_anchor keeps the portion between first and last near-anchor projections."
        ),
    )
    parser.add_argument(
        "--same-entry-leading-threshold-m",
        type=float,
        default=50.0,
        help="For same-entry routes, if entry anchor projection is beyond this distance, trim leading spur.",
    )
    parser.add_argument(
        "--same-entry-anchor-match-radius-m",
        type=float,
        default=30.0,
        help="Radius for detecting first/last projections near the same entry anchor.",
    )
    return parser.parse_args()


args = parse_args()
CASE_ID = args.case_id

if args.ordered_path_fp is None:
    ORDERED_PATH_FP = (
        PROJECT_ROOT
        / "outputs"
        / "ib0b_mainline"
        / CASE_ID
        / f"{CASE_ID}_mainline_ordered_path.geojson"
    )
else:
    ORDERED_PATH_FP = resolve_path(args.ordered_path_fp)

if args.anchor_fp is None:
    ANCHOR_FP = (
        PROJECT_ROOT
        / "outputs"
        / "ib0c_anchor"
        / CASE_ID
        / f"{CASE_ID}_route_anchors.geojson"
    )
else:
    ANCHOR_FP = resolve_path(args.anchor_fp)

if args.out_dir is None:
    OUT_DIR = PROJECT_ROOT / "outputs" / "ib0d_trimmed_mainline" / CASE_ID
else:
    OUT_DIR = resolve_path(args.out_dir)

OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_TRIMMED_GEOJSON = OUT_DIR / f"{CASE_ID}_mainline_ordered_path_trimmed.geojson"
OUT_SUMMARY_CSV = OUT_DIR / f"{CASE_ID}_mainline_trim_summary.csv"
OUT_HTML = OUT_DIR / f"{CASE_ID}_mainline_ordered_path_trimmed_map.html"

OUT_ROUTE_POINTS_CSV = OUT_DIR / f"{CASE_ID}_mainline_ordered_path_trimmed_route_points.csv"
OUT_SELF_NEAR_CSV = OUT_DIR / f"{CASE_ID}_mainline_self_near_pairs.csv"
OUT_SELF_NEAR_ZONES_CSV = OUT_DIR / f"{CASE_ID}_mainline_self_near_zones.csv"
OUT_QA_SUMMARY_TXT = OUT_DIR / f"{CASE_ID}_mainline_ordered_path_trimmed_qa_summary.txt"

# =========================================================
# 1. 參數
# =========================================================
# 是否在 start/end anchor 外再保留一點 buffer
# 先設 0，代表精準依 anchor 投影位置裁切
TRIM_BUFFER_M = args.trim_buffer_m

# 如果 start/end anchor 離 ordered path 太遠，印出警告
ANCHOR_TO_LINE_WARN_M = args.anchor_to_line_warn_m


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


def projection_distances_near_point(line: LineString, pt: Point, radius_m: float) -> list[float]:
    """
    Find all along-line distances where each line segment comes within radius_m of pt.

    Shapely LineString.project(pt) returns only the first nearest projection. For
    same-entry / out-and-back routes, the same physical anchor may appear twice
    on the ordered path. This helper scans each segment and returns all local
    closest-point projections whose distance to the anchor is within radius_m.
    """
    coords = list(line.coords)
    if len(coords) < 2:
        return []

    hits = []
    acc = 0.0

    for i in range(len(coords) - 1):
        seg = LineString([coords[i], coords[i + 1]])
        seg_len = seg.length

        if seg_len <= 0:
            continue

        local_d = seg.project(pt)
        local_pt = seg.interpolate(local_d)
        offset = local_pt.distance(pt)

        if offset <= radius_m:
            hits.append(acc + local_d)

        acc += seg_len

    if not hits:
        return []

    # Deduplicate nearly identical segment-boundary projections.
    hits = sorted(hits)
    dedup = []
    for d in hits:
        if not dedup or abs(d - dedup[-1]) > 1.0:
            dedup.append(d)

    return dedup

def build_route_points_table(
    line_m: LineString,
    metric_crs,
    sample_interval_m: float = 1.0,
) -> gpd.GeoDataFrame:
    """
    Build a densified route point table along the trimmed mainline.

    Important:
    - Do not use only LineString vertices, because OSM geometry vertices are sparse.
    - Sampling every 1 m makes route_point_index approximately comparable to
      downstream 1 m route profile indices.
    """
    rows = []
    length_m = float(line_m.length)

    d = 0.0
    i = 0
    while d < length_m:
        pt = line_m.interpolate(d)
        rows.append(
            {
                "route_point_index": i,
                "route_dist_m": d,
                "x": pt.x,
                "y": pt.y,
                "geometry": pt,
            }
        )
        i += 1
        d += sample_interval_m

    # Always include exact endpoint.
    if not rows or abs(rows[-1]["route_dist_m"] - length_m) > 1e-6:
        pt = line_m.interpolate(length_m)
        rows.append(
            {
                "route_point_index": i,
                "route_dist_m": length_m,
                "x": pt.x,
                "y": pt.y,
                "geometry": pt,
            }
        )

    return gpd.GeoDataFrame(rows, geometry="geometry", crs=metric_crs)


def find_self_near_pairs(
    route_points_m: gpd.GeoDataFrame,
    spatial_threshold_m: float = 10.0,
    route_gap_threshold_m: float = 80.0,
    min_index_gap: int = 20,
) -> pd.DataFrame:
    """
    Find self-near route point pairs.

    Rule:
    - spatial_distance_m <= spatial_threshold_m
    - route_distance_gap_m >= route_gap_threshold_m
    - route_point_index gap >= min_index_gap

    This version uses GeoPandas spatial index instead of O(n^2) full scan.
    """
    output_cols = [
        "idx_a",
        "dist_a_m",
        "idx_b",
        "dist_b_m",
        "spatial_distance_m",
        "route_distance_gap_m",
        "possible_issue_type",
    ]

    if route_points_m.empty:
        return pd.DataFrame(columns=output_cols)

    pts = route_points_m.reset_index(drop=True).copy()

    # Ensure spatial index exists.
    sindex = pts.sindex

    rows = []

    for i, row_i in pts.iterrows():
        pi = row_i.geometry
        di = float(row_i.route_dist_m)
        idx_i = int(row_i.route_point_index)

        # Query only nearby candidates by spatial bounding box.
        search_geom = pi.buffer(spatial_threshold_m)
        candidate_idx = list(sindex.intersection(search_geom.bounds))

        for j in candidate_idx:
            if j <= i:
                continue

            row_j = pts.iloc[j]
            idx_j = int(row_j.route_point_index)

            if abs(idx_j - idx_i) < min_index_gap:
                continue

            dj = float(row_j.route_dist_m)
            route_gap = abs(dj - di)

            if route_gap < route_gap_threshold_m:
                continue

            pj = row_j.geometry
            spatial_dist = float(pi.distance(pj))

            if spatial_dist <= spatial_threshold_m:
                rows.append(
                    {
                        "idx_a": idx_i,
                        "dist_a_m": di,
                        "idx_b": idx_j,
                        "dist_b_m": dj,
                        "spatial_distance_m": spatial_dist,
                        "route_distance_gap_m": route_gap,
                        "possible_issue_type": "self_near_ordered_path",
                    }
                )

    return pd.DataFrame(rows, columns=output_cols)


def summarize_self_near_zones(
    self_near_pairs: pd.DataFrame,
    route_length_m: float,
) -> pd.DataFrame:
    if self_near_pairs.empty:
        return pd.DataFrame()

    pairs = self_near_pairs.copy()
    for col in [
        "idx_a",
        "dist_a_m",
        "idx_b",
        "dist_b_m",
        "spatial_distance_m",
        "route_distance_gap_m",
    ]:
    
        pairs[col] = pd.to_numeric(pairs[col], errors="coerce")
    
    pairs = pairs.dropna(
        subset=[
            "idx_a",
            "dist_a_m",
            "idx_b",
            "dist_b_m",
            "spatial_distance_m",
            "route_distance_gap_m",
        ]
    ).copy()



    zones = []

    def add_zone(zone_type: str, z: pd.DataFrame) -> None:
        if z.empty:
            return

        rep_min_spatial = z.sort_values(
            ["spatial_distance_m", "route_distance_gap_m"],
            ascending=[True, False],
        ).iloc[0]

        rep_max_gap = z.sort_values(
            ["route_distance_gap_m", "spatial_distance_m"],
            ascending=[False, True],
        ).iloc[0]

        zones.append(
            {
                "zone_type": zone_type,
                "pair_count": int(len(z)),
                "dist_a_min_m": float(z["dist_a_m"].min()),
                "dist_a_max_m": float(z["dist_a_m"].max()),
                "dist_b_min_m": float(z["dist_b_m"].min()),
                "dist_b_max_m": float(z["dist_b_m"].max()),
                "spatial_distance_min_m": float(z["spatial_distance_m"].min()),
                "spatial_distance_avg_m": float(z["spatial_distance_m"].mean()),
                "spatial_distance_max_m": float(z["spatial_distance_m"].max()),
                "route_gap_min_m": float(z["route_distance_gap_m"].min()),
                "route_gap_avg_m": float(z["route_distance_gap_m"].mean()),
                "route_gap_max_m": float(z["route_distance_gap_m"].max()),

                "min_spatial_idx_a": int(rep_min_spatial["idx_a"]),
                "min_spatial_dist_a_m": float(rep_min_spatial["dist_a_m"]),
                "min_spatial_idx_b": int(rep_min_spatial["idx_b"]),
                "min_spatial_dist_b_m": float(rep_min_spatial["dist_b_m"]),
                "min_spatial_distance_m": float(rep_min_spatial["spatial_distance_m"]),
                "min_spatial_route_gap_m": float(rep_min_spatial["route_distance_gap_m"]),

                "max_gap_idx_a": int(rep_max_gap["idx_a"]),
                "max_gap_dist_a_m": float(rep_max_gap["dist_a_m"]),
                "max_gap_idx_b": int(rep_max_gap["idx_b"]),
                "max_gap_dist_b_m": float(rep_max_gap["dist_b_m"]),
                "max_gap_spatial_distance_m": float(rep_max_gap["spatial_distance_m"]),
                "max_gap_route_gap_m": float(rep_max_gap["route_distance_gap_m"]),
            }
        )

    same_entry = pairs[
        (
            (pairs["dist_a_m"] <= 100.0)
            & (pairs["dist_b_m"] >= route_length_m - 100.0)
        )
        | (
            (pairs["dist_b_m"] <= 100.0)
            & (pairs["dist_a_m"] >= route_length_m - 100.0)
        )
    ]
    add_zone("same_entry_exit_zone", same_entry)

    summit = pairs[
        (
            (
                (pairs["dist_a_m"] >= 1800.0)
                & (pairs["dist_a_m"] <= 2050.0)
            )
            | (
                (pairs["dist_b_m"] >= 1800.0)
                & (pairs["dist_b_m"] <= 2050.0)
            )
        )
        & (
            (
                (pairs["dist_a_m"] >= 2150.0)
                & (pairs["dist_a_m"] <= 2350.0)
            )
            | (
                (pairs["dist_b_m"] >= 2150.0)
                & (pairs["dist_b_m"] <= 2350.0)
            )
        )
    ]
    add_zone("summit_self_near_zone", summit)

    used_idx = set(same_entry.index).union(set(summit.index))
    other = pairs.loc[~pairs.index.isin(used_idx)]
    add_zone("other_self_near_zone", other)

    return pd.DataFrame(zones)

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
MIN_TRIM_LENGTH_M = args.min_trim_length_m
same_entry_exit = (trim_end_m - trim_start_m) < MIN_TRIM_LENGTH_M

same_entry_policy = args.same_entry_policy
same_entry_anchor_hits = []
same_entry_anchor_first_m = pd.NA
same_entry_anchor_last_m = pd.NA
same_entry_trim_applied = False

if same_entry_exit:
    entry_proj_m = min(start_proj_m, end_proj_m)

    same_entry_anchor_hits = projection_distances_near_point(
        ordered_line_m,
        start_pt_m,
        args.same_entry_anchor_match_radius_m,
    )

    if same_entry_anchor_hits:
        same_entry_anchor_first_m = float(min(same_entry_anchor_hits))
        same_entry_anchor_last_m = float(max(same_entry_anchor_hits))

    if same_entry_policy == "trim_between_first_last_anchor" and len(same_entry_anchor_hits) >= 2:
        trim_start_m = max(0.0, float(same_entry_anchor_first_m) - TRIM_BUFFER_M)
        trim_end_m = min(original_len_m, float(same_entry_anchor_last_m) + TRIM_BUFFER_M)
        TRIM_MODE = "same_entry_exit_trim_between_first_last_anchor"
        same_entry_trim_applied = True
        trim_reason = (
            "same-entry-exit route; multiple near-entry anchor projections were detected, "
            "trim between first and last near-anchor projections."
        )

        if (trim_end_m - trim_start_m) < MIN_TRIM_LENGTH_M:
            # Degenerate case: near-anchor hits collapsed; fall back to leading trim or keep full.
            if entry_proj_m > args.same_entry_leading_threshold_m:
                trim_start_m = max(0.0, entry_proj_m - TRIM_BUFFER_M)
                trim_end_m = original_len_m
                TRIM_MODE = "same_entry_exit_trim_leading_spur"
                trim_reason = (
                    "same-entry-exit route; first/last near-anchor range was too short, "
                    "so remove leading spur before entry anchor."
                )
            else:
                trim_start_m = 0.0
                trim_end_m = original_len_m
                TRIM_MODE = "same_entry_exit_keep_full_ordered_path"
                trim_reason = (
                    "same-entry-exit route; first/last near-anchor range was too short "
                    "and entry anchor is near route start, so keep full ordered path."
                )

    elif same_entry_policy in {"trim_leading", "trim_between_first_last_anchor"} and entry_proj_m > args.same_entry_leading_threshold_m:
        trim_start_m = max(0.0, entry_proj_m - TRIM_BUFFER_M)
        trim_end_m = original_len_m
        TRIM_MODE = "same_entry_exit_trim_leading_spur"
        same_entry_trim_applied = True
        trim_reason = (
            "same-entry-exit route; entry anchor projects far from ordered path start, "
            "so remove leading spur before entry anchor."
        )

    else:
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
print(f"same_entry_policy: {same_entry_policy}")
print(f"same_entry_anchor_hits_n: {len(same_entry_anchor_hits)}")
if same_entry_anchor_hits:
    print(f"same_entry_anchor_first_m: {float(same_entry_anchor_first_m):.2f}")
    print(f"same_entry_anchor_last_m: {float(same_entry_anchor_last_m):.2f}")
print(f"same_entry_trim_applied: {same_entry_trim_applied}")
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
            "case_id": CASE_ID,
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
            "same_entry_policy": same_entry_policy,
            "same_entry_trim_applied": same_entry_trim_applied,
            "same_entry_anchor_hits_n": len(same_entry_anchor_hits),
            "same_entry_anchor_first_m": same_entry_anchor_first_m,
            "same_entry_anchor_last_m": same_entry_anchor_last_m,
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
# 6b. Route points / self-near QA
# =========================================================
route_points_m = build_route_points_table(
    trimmed_line_m,
    metric_crs,
    sample_interval_m=1.0,
)
route_points_wgs84 = route_points_m.to_crs("EPSG:4326").copy()
route_points_wgs84["lat"] = route_points_wgs84.geometry.y
route_points_wgs84["lon"] = route_points_wgs84.geometry.x

route_points_wgs84[
    ["route_point_index", "route_dist_m", "lat", "lon"]
].to_csv(
    OUT_ROUTE_POINTS_CSV,
    index=False,
    encoding="utf-8-sig",
)

print("start self-near pair detection...")
self_near_pairs = find_self_near_pairs(
    route_points_m,
    spatial_threshold_m=10.0,
    route_gap_threshold_m=80.0,
    min_index_gap=20,
)
print("done self-near pair detection.")


self_near_pairs.to_csv(
    OUT_SELF_NEAR_CSV,
    index=False,
    encoding="utf-8-sig",
)

self_near_zones = summarize_self_near_zones(
    self_near_pairs,
    route_length_m=trimmed_len_m,
)
self_near_zones.to_csv(
    OUT_SELF_NEAR_ZONES_CSV,
    index=False,
    encoding="utf-8-sig",
)

print(f"route points CSV 輸出：{OUT_ROUTE_POINTS_CSV.resolve()}")
print(f"self-near pairs CSV 輸出：{OUT_SELF_NEAR_CSV.resolve()}")
print(f"self-near zones CSV 輸出：{OUT_SELF_NEAR_ZONES_CSV.resolve()}")
print(f"self-near pair count: {len(self_near_pairs)}")
print(f"self-near zone count: {len(self_near_zones)}")


# =========================================================
# 7. Summary CSV
# =========================================================
summary = {
    "case_id": CASE_ID,
    "input_ordered_path": str(ORDERED_PATH_FP),
    "input_anchor": str(ANCHOR_FP),
    "trim_mode": TRIM_MODE,
    "trim_reason": trim_reason,
    "is_same_entry_exit": same_entry_exit,
    "same_entry_policy": same_entry_policy,
    "same_entry_trim_applied": same_entry_trim_applied,
    "same_entry_anchor_hits_n": len(same_entry_anchor_hits),
    "same_entry_anchor_first_m": same_entry_anchor_first_m,
    "same_entry_anchor_last_m": same_entry_anchor_last_m,
    "same_entry_leading_threshold_m": args.same_entry_leading_threshold_m,
    "same_entry_anchor_match_radius_m": args.same_entry_anchor_match_radius_m,
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
    "route_point_count": len(route_points_m),
    "self_near_pair_count": len(self_near_pairs),
    "self_near_zone_count": len(self_near_zones),
    "self_near_spatial_threshold_m": 10.0,
    "self_near_route_gap_threshold_m": 80.0,
}

pd.DataFrame([summary]).to_csv(
    OUT_SUMMARY_CSV,
    index=False,
    encoding="utf-8-sig",
)

qa_lines = [
    "IB0D trimmed ordered mainline QA",
    f"case_id: {CASE_ID}",
    f"trimmed_len_m: {trimmed_len_m:.2f}",
    f"route_point_count: {len(route_points_m)}",
    f"self_near_pair_count: {len(self_near_pairs)}",
    f"self_near_zone_count: {len(self_near_zones)}",
    "self_near_rule: spatial_distance_m <= 10m and route_distance_gap_m >= 80m",
]

if not self_near_pairs.empty:
    top_pairs = self_near_pairs.sort_values(
        ["route_distance_gap_m", "spatial_distance_m"],
        ascending=[False, True],
    ).head(20)

    qa_lines.append("")
    qa_lines.append("Top self-near pairs:")
    for _, r in top_pairs.iterrows():
        qa_lines.append(
            f"- idx {int(r.idx_a)} dist {float(r.dist_a_m):.1f}m "
            f"<-> idx {int(r.idx_b)} dist {float(r.dist_b_m):.1f}m; "
            f"spatial {float(r.spatial_distance_m):.2f}m; "
            f"route_gap {float(r.route_distance_gap_m):.1f}m"
        )
if not self_near_zones.empty:
    qa_lines.append("")
    qa_lines.append("Self-near zones:")
    for _, r in self_near_zones.iterrows():
        qa_lines.append(
            f"- {r['zone_type']}: pair_count={int(r['pair_count'])}; "
            f"dist_a={float(r['dist_a_min_m']):.1f}-{float(r['dist_a_max_m']):.1f}m; "
            f"dist_b={float(r['dist_b_min_m']):.1f}-{float(r['dist_b_max_m']):.1f}m; "
            f"spatial_min={float(r['spatial_distance_min_m']):.3f}m; "
            f"route_gap_max={float(r['route_gap_max_m']):.1f}m"
        )

OUT_QA_SUMMARY_TXT.write_text("\n".join(qa_lines), encoding="utf-8")
print(f"QA summary TXT 輸出：{OUT_QA_SUMMARY_TXT.resolve()}")

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
