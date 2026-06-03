# =========================================================
# ib0b_route_mainline_extract_abtest_v1.py
# A/B 測試版：從 ib0 matched 或 ib0a pruned OSM segments 抽取主幹路徑
# 使用 ib0c anchors + activity interval anchors
#
# A: ib0 → ib0a → ib0b
# B: ib0 → ib0b
#
# 本版用途：
# - 支援 GPX / FIT CSV / 一般 CSV 三種活動輸入
# - 將不同活動格式統一轉為 activity_line
# - 支援 case-specific input / output
# - 輸出可追溯 route_id / case_id / activity_type / input_stage / ab_mode
# =========================================================

from pathlib import Path
import argparse
import xml.etree.ElementTree as ET

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point
import networkx as nx
import folium


# =========================================================
# 0. 路徑設定
# =========================================================

# =========================================================
# 0a. Project / Route / Case / Activity / A-B Test 設定
# =========================================================
PROJECT_ROOT = Path(r"C:\mountain_work\115_osm")


def resolve_path(value, project_root=PROJECT_ROOT):
    """
    將 CLI 傳入路徑轉成 Path。
    - 絕對路徑：原樣使用
    - 相對路徑：以 PROJECT_ROOT 為基準
    """
    if value is None:
        return None

    p = Path(value)
    if p.is_absolute():
        return p
    return project_root / p


def infer_activity_type(activity_fp: Path) -> str:
    """
    自動判斷活動資料型態：
    - .gpx -> gpx
    - .csv 且含 Garmin FIT semicircles 欄位 -> fit_csv
    - .csv 且含一般 lat/lon 欄位 -> csv
    """
    suffix = activity_fp.suffix.lower()

    if suffix == ".gpx":
        return "gpx"

    if suffix == ".csv":
        sample = pd.read_csv(activity_fp, nrows=5, low_memory=False)
        cols = {str(c).strip().lower() for c in sample.columns}

        fit_lat = "record.position_lat[semicircles]".lower()
        fit_lon = "record.position_long[semicircles]".lower()
        if fit_lat in cols and fit_lon in cols:
            return "fit_csv"

        lat_candidates = {"lat", "latitude", "position_lat", "raw_lat", "緯度"}
        lon_candidates = {"lon", "lng", "longitude", "position_long", "position_lon", "raw_lon", "經度"}
        if cols.intersection(lat_candidates) and cols.intersection(lon_candidates):
            return "csv"

        raise ValueError(
            "無法自動判斷 CSV 活動資料型態：找不到 FIT semicircles 或一般 lat/lon 欄位。"
        )

    raise ValueError(f"無法自動判斷活動資料型態：不支援副檔名 {suffix}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="ib0b: 從 ib0 matched 或 ib0a pruned OSM segments 抽取 ordered mainline"
    )

    parser.add_argument(
        "--case-id",
        default="juansi_waterfall_fitcsv_20260503",
        help="CASE_ID，例如 qixing_xiaoyoukeng_main_peak_20260315",
    )
    parser.add_argument(
        "--route-id",
        default=None,
        help="route_id；未指定時等於 case-id",
    )
    parser.add_argument(
        "--case-name",
        default=None,
        help="人類可讀案例名稱；未指定時等於 case-id",
    )
    parser.add_argument(
        "--route-group",
        default=None,
        help="route_group；未指定時等於 case-id",
    )
    parser.add_argument(
        "--activity-fp",
        default=None,
        help="活動軌跡檔，可為 GPX / FIT CSV / 一般 CSV。相對路徑以 PROJECT_ROOT 為基準。",
    )
    parser.add_argument(
        "--activity-type",
        default="auto",
        choices=["auto", "gpx", "fit_csv", "csv"],
        help="活動資料型態，預設 auto。",
    )
    parser.add_argument(
        "--ab-mode",
        default="B",
        choices=["A", "B"],
        help="A=讀 ib0a pruned；B=直接讀 ib0 matched。七星山補 provenance 建議先用 B。",
    )
    parser.add_argument(
        "--input-stage",
        default=None,
        choices=["ib0_matched", "ib0a_pruned"],
        help="輸入階段。未指定時依 ab-mode 推定。",
    )
    parser.add_argument(
        "--in-fp",
        default=None,
        help="輸入 matched/pruned GeoJSON。未指定時依 case-id 與 input-stage 推定。",
    )
    parser.add_argument(
        "--anchor-fp",
        default=None,
        help="ib0c anchor GeoJSON。若未指定且檔案不存在，會改用 activity start/mid/end fallback anchors。",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="輸出資料夾。未指定時使用 outputs/ib0b_mainline/<CASE_ID>。",
    )
    parser.add_argument(
        "--ia1-dataset-id",
        default=None,
        help="OSM dataset id / provenance；未指定時預設為 case-id。",
    )
    parser.add_argument(
        "--ia1-version",
        default="case_level",
        help="IA1 version / provenance label。",
    )
    parser.add_argument(
        "--ia1-snapshot-tag",
        default="case_osm_raw",
        help="IA1 snapshot / provenance label。",
    )
    parser.add_argument(
        "--strict-anchor",
        action="store_true",
        help="若指定，找不到 anchor-fp 時直接停止；預設允許 fallback activity anchors。",
    )

    return parser.parse_args()


args = parse_args()

ROUTE_ID = args.route_id or args.case_id
ROUTE_GROUP = args.route_group or args.case_id
CASE_ID = args.case_id
CASE_NAME = args.case_name or args.case_id

# 三位一體活動輸入：
# ACTIVITY_TYPE 可選 "auto" / "gpx" / "fit_csv" / "csv"
if args.activity_fp is None:
    # 保留舊版預設，避免未帶 CLI 時完全不能執行。
    ACTIVITY_FP = PROJECT_ROOT / "activity_input" / "csv" / "juansi_waterfall" / "3.csv"
else:
    ACTIVITY_FP = resolve_path(args.activity_fp)

ACTIVITY_NAME = ACTIVITY_FP.name
ACTIVITY_TYPE = args.activity_type
if ACTIVITY_TYPE == "auto":
    ACTIVITY_TYPE = infer_activity_type(ACTIVITY_FP)

IA1_VERSION = args.ia1_version
IA1_DATASET_ID = args.ia1_dataset_id or CASE_ID
IA1_SNAPSHOT_TAG = args.ia1_snapshot_tag

# A：正式穩定版，使用 ib0a pruning 後的 matched route
# B：診斷比較版，直接使用 ib0 matched route，不經 ib0a
AB_MODE = args.ab_mode

IB0_DIR = PROJECT_ROOT / "outputs" / "ib0_route_match" / CASE_ID
IB0A_DIR = PROJECT_ROOT / "outputs" / "ib0a_prune" / CASE_ID
IB0C_DIR = PROJECT_ROOT / "outputs" / "ib0c_anchor" / CASE_ID

if args.input_stage is not None:
    INPUT_STAGE = args.input_stage
elif AB_MODE == "A":
    INPUT_STAGE = "ib0a_pruned"
elif AB_MODE == "B":
    INPUT_STAGE = "ib0_matched"
else:
    raise ValueError("AB_MODE 只能是 'A' 或 'B'")

if args.in_fp is not None:
    IN_FP = resolve_path(args.in_fp)
elif INPUT_STAGE == "ib0a_pruned":
    IN_FP = IB0A_DIR / f"{CASE_ID}_activity_osm_matched_pruned.geojson"
elif INPUT_STAGE == "ib0_matched":
    IN_FP = IB0_DIR / f"{CASE_ID}_activity_osm_matched.geojson"
else:
    raise ValueError(f"不支援的 INPUT_STAGE：{INPUT_STAGE}")

if args.anchor_fp is not None:
    ANCHOR_FP = resolve_path(args.anchor_fp)
else:
    ANCHOR_FP = IB0C_DIR / f"{CASE_ID}_route_anchors.geojson"

STRICT_ANCHOR = bool(args.strict_anchor)

if args.out_dir is not None:
    OUT_DIR = resolve_path(args.out_dir)
else:
    OUT_DIR = PROJECT_ROOT / "outputs" / "ib0b_mainline" / CASE_ID

OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_FP = OUT_DIR / f"{CASE_ID}_mainline_{INPUT_STAGE}.geojson"
OUT_HTML_FP = OUT_DIR / f"{CASE_ID}_mainline_map_{INPUT_STAGE}.html"
OUT_ORDERED_PATH_FP = OUT_DIR / f"{CASE_ID}_mainline_ordered_path_{INPUT_STAGE}.geojson"

OUT_DEBUG_CSV = OUT_DIR / f"{CASE_ID}_mainline_debug_segments_{INPUT_STAGE}.csv"
OUT_SUMMARY_CSV = OUT_DIR / f"{CASE_ID}_mainline_summary_{INPUT_STAGE}.csv"

OUT_STANDARD_ORDERED_PATH_FP = OUT_DIR / f"{CASE_ID}_mainline_ordered_path.geojson"
OUT_STANDARD_MAINLINE_FP = OUT_DIR / f"{CASE_ID}_mainline.geojson"
OUT_STANDARD_HTML_FP = OUT_DIR / f"{CASE_ID}_mainline_map.html"


# =========================================================
# 1. 參數設定
# =========================================================
GPX_ANCHOR_INTERVAL_M = 30.0

# 是否啟用 snap link
# 先設 False，避免上下緣被錯誤接起來
ENABLE_SNAP_LINK = False
SNAP_TOLERANCE_M = 15.0
SNAP_LINK_WEIGHT = 0.30

MIN_ANCHOR_SPACING_M = 15.0


# =========================================================
# 2. 輸入檢查
# =========================================================
if not IN_FP.exists():
    if AB_MODE == "A":
        raise FileNotFoundError(
            f"找不到 A 模式輸入檔：{IN_FP.resolve()}，請先執行 ib0a"
        )
    else:
        raise FileNotFoundError(
            f"找不到 B 模式輸入檔：{IN_FP.resolve()}，請先執行 ib0"
        )

if not ANCHOR_FP.exists() and STRICT_ANCHOR:
    raise FileNotFoundError(f"找不到 anchors：{ANCHOR_FP.resolve()}，請先執行 ib0c 或移除 --strict-anchor 使用 fallback anchors")

if not ACTIVITY_FP.exists():
    raise FileNotFoundError(f"找不到活動軌跡檔：{ACTIVITY_FP.resolve()}")


# =========================================================
# 3. 工具函式
# =========================================================
def parse_gpx_line(gpx_fp: Path) -> LineString:
    tree = ET.parse(gpx_fp)
    root = tree.getroot()

    if root.tag.startswith("{"):
        uri = root.tag.split("}")[0].strip("{")
        ns = {"gpx": uri}
        trkpt_xpath = ".//gpx:trkpt"
    else:
        ns = {}
        trkpt_xpath = ".//trkpt"

    pts = []

    for trkpt in root.findall(trkpt_xpath, ns):
        lat = float(trkpt.attrib["lat"])
        lon = float(trkpt.attrib["lon"])
        pts.append((lon, lat))

    if len(pts) < 2:
        raise ValueError("GPX 點數不足，無法建立 LineString")

    return LineString(pts)


def semicircles_to_degrees(value):
    """
    Garmin FIT semicircles 轉十進位經緯度。
    degrees = semicircles * 180 / 2^31
    """
    if pd.isna(value):
        return pd.NA
    return float(value) * 180.0 / (2 ** 31)


def clean_latlon_points(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    """
    清理 lat/lon 點：
    - 移除空值
    - 移除超出經緯度範圍者
    - 確認至少 2 點
    """
    out = df.dropna(subset=["lat", "lon"]).copy()

    out = out[
        out["lat"].between(-90, 90) &
        out["lon"].between(-180, 180)
    ].copy()

    if len(out) < 2:
        raise ValueError(f"{source_name} 有效 GPS 點數不足")

    out = out.reset_index(drop=True)

    print(f"{source_name} 有效 GPS 點數：", len(out))
    print(f"{source_name} lat range:", float(out["lat"].min()), "→", float(out["lat"].max()))
    print(f"{source_name} lon range:", float(out["lon"].min()), "→", float(out["lon"].max()))

    return out


def parse_fit_csv_line(csv_fp: Path) -> LineString:
    """
    讀取 Garmin FIT CSV：
    - record.position_lat[semicircles]
    - record.position_long[semicircles]
    並轉成 LineString。
    """
    if not csv_fp.exists():
        raise FileNotFoundError(f"找不到 FIT CSV：{csv_fp}")

    df = pd.read_csv(csv_fp, low_memory=False)

    lat_col = "record.position_lat[semicircles]"
    lon_col = "record.position_long[semicircles]"

    if lat_col not in df.columns or lon_col not in df.columns:
        raise ValueError(
            f"FIT CSV 缺少必要欄位：{lat_col}, {lon_col}。目前欄位：{list(df.columns)}"
        )

    out = pd.DataFrame()
    out["lat"] = pd.to_numeric(df[lat_col], errors="coerce").apply(semicircles_to_degrees)
    out["lon"] = pd.to_numeric(df[lon_col], errors="coerce").apply(semicircles_to_degrees)

    out = clean_latlon_points(out, source_name="FIT CSV")

    pts = list(zip(out["lon"], out["lat"]))
    return LineString(pts)


def parse_csv_line(csv_fp: Path) -> LineString:
    """
    讀取一般 CSV。
    支援常見欄位：
    lat / latitude / position_lat / raw_lat
    lon / lng / longitude / position_long / position_lon / raw_lon
    """
    if not csv_fp.exists():
        raise FileNotFoundError(f"找不到 CSV：{csv_fp}")

    df = pd.read_csv(csv_fp, low_memory=False)

    rename_map = {}

    for c in df.columns:
        lc = str(c).strip().lower()

        if lc in ["lat", "latitude", "position_lat", "raw_lat"]:
            rename_map[c] = "lat"
        elif lc in ["lon", "lng", "longitude", "position_long", "position_lon", "raw_lon"]:
            rename_map[c] = "lon"

    df = df.rename(columns=rename_map)

    if "lat" not in df.columns or "lon" not in df.columns:
        raise ValueError(
            f"CSV 缺少必要欄位 lat/lon。支援 lat、latitude、lon、lng、longitude 等欄位。目前欄位：{list(df.columns)}"
        )

    out = pd.DataFrame()
    out["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    out["lon"] = pd.to_numeric(df["lon"], errors="coerce")

    out = clean_latlon_points(out, source_name="CSV")

    pts = list(zip(out["lon"], out["lat"]))
    return LineString(pts)


def parse_activity_line(activity_type: str, activity_fp: Path) -> LineString:
    """
    統一活動軌跡入口。
    將 GPX / FIT CSV / 一般 CSV 全部轉成 LineString。
    """
    activity_type = activity_type.lower()

    if activity_type == "gpx":
        return parse_gpx_line(activity_fp)

    if activity_type == "fit_csv":
        return parse_fit_csv_line(activity_fp)

    if activity_type == "csv":
        return parse_csv_line(activity_fp)

    raise ValueError(
        f"不支援的 ACTIVITY_TYPE：{activity_type}。請使用 'gpx', 'fit_csv', 或 'csv'"
    )

def line_to_nodes(line):
    coords = list(line.coords)
    return tuple(coords[0]), tuple(coords[-1])


def nearest_segment_node(gdf_m, pt_m):
    min_dist = float("inf")
    best_idx = None

    for idx, row in gdf_m.iterrows():
        geom = row.geometry
        d = geom.distance(pt_m)

        if d < min_dist:
            min_dist = d
            best_idx = idx

    geom = gdf_m.loc[best_idx].geometry

    if geom.geom_type == "MultiLineString":
        geom = list(geom.geoms)[0]

    coords = list(geom.coords)
    n1 = tuple(coords[0])
    n2 = tuple(coords[-1])

    if Point(n1).distance(pt_m) < Point(n2).distance(pt_m):
        return n1
    else:
        return n2


def make_gpx_interval_points(gpx_line_m: LineString, interval_m: float):
    total_len = gpx_line_m.length

    rows = []
    d = interval_m
    i = 0

    while d < total_len:
        pt = gpx_line_m.interpolate(d)
        rows.append((f"gpx_{i:03d}", pt, d))
        d += interval_m
        i += 1

    return rows


def node_distance(a, b):
    return Point(a).distance(Point(b))


# =========================================================
# 4. 讀資料
# =========================================================
gdf = gpd.read_file(IN_FP).to_crs(epsg=4326)

print("\n=== ib0b A/B mode ===")
print("ROUTE_ID:", ROUTE_ID)
print("ROUTE_GROUP:", ROUTE_GROUP)
print("CASE_ID:", CASE_ID)
print("CASE_NAME:", CASE_NAME)
print("ACTIVITY_TYPE:", ACTIVITY_TYPE)
print("ACTIVITY_NAME:", ACTIVITY_NAME)
print("ACTIVITY_FP:", ACTIVITY_FP.resolve())
print("IA1_DATASET_ID:", IA1_DATASET_ID)
print("IA1_SNAPSHOT_TAG:", IA1_SNAPSHOT_TAG)
print("AB_MODE:", AB_MODE)
print("INPUT_STAGE:", INPUT_STAGE)
print("IN_FP:", IN_FP.resolve())
print("ANCHOR_FP:", ANCHOR_FP.resolve())
print("OUT_DIR:", OUT_DIR.resolve())
print("segments input:", len(gdf))

metric_crs = gdf.estimate_utm_crs()
gdf_m = gdf.to_crs(metric_crs)

activity_line = parse_activity_line(ACTIVITY_TYPE, ACTIVITY_FP)

activity_gdf = gpd.GeoDataFrame(
    [{
        "case_id": CASE_ID,
        "case_name": CASE_NAME,
        "activity_type": ACTIVITY_TYPE,
        "activity_name": ACTIVITY_NAME,
        "geometry": activity_line,
    }],
    geometry="geometry",
    crs="EPSG:4326",
)

activity_line_m = activity_gdf.to_crs(metric_crs).geometry.iloc[0]

if ANCHOR_FP.exists():
    anchors = gpd.read_file(ANCHOR_FP).to_crs(epsg=4326)
    ANCHOR_SOURCE_MODE = "ib0c_anchor"
    print("anchors source: ib0c")
else:
    # ib0c 尚未建立時的安全 fallback：
    # 使用 activity start / mid / end 作為 ordering anchors，先讓 ib0b 能建立 ordered mainline provenance。
    start_pt = Point(activity_line.coords[0])
    via_pt = activity_line.interpolate(0.5, normalized=True)
    end_pt = Point(activity_line.coords[-1])

    anchors = gpd.GeoDataFrame(
        [
            {
                "case_id": CASE_ID,
                "anchor_role": "start",
                "anchor_source": "activity_fallback_start",
                "geometry": start_pt,
            },
            {
                "case_id": CASE_ID,
                "anchor_role": "via",
                "anchor_source": "activity_fallback_mid",
                "geometry": via_pt,
            },
            {
                "case_id": CASE_ID,
                "anchor_role": "end",
                "anchor_source": "activity_fallback_end",
                "geometry": end_pt,
            },
        ],
        geometry="geometry",
        crs="EPSG:4326",
    )
    ANCHOR_SOURCE_MODE = "activity_start_mid_end_fallback"
    print("WARNING: 找不到 ib0c anchors，改用 activity start/mid/end fallback anchors")


# =========================================================
# 5. 讀 ib0c anchors
# =========================================================
start_pt = anchors.loc[anchors["anchor_role"] == "start"].geometry.iloc[0]
via_pt = anchors.loc[anchors["anchor_role"] == "via"].geometry.iloc[0]
end_pt = anchors.loc[anchors["anchor_role"] == "end"].geometry.iloc[0]

start_pt_m = gpd.GeoSeries([start_pt], crs="EPSG:4326").to_crs(metric_crs).iloc[0]
via_pt_m = gpd.GeoSeries([via_pt], crs="EPSG:4326").to_crs(metric_crs).iloc[0]
end_pt_m = gpd.GeoSeries([end_pt], crs="EPSG:4326").to_crs(metric_crs).iloc[0]


# =========================================================
# 6. 建 graph
# =========================================================
G = nx.Graph()

def split_line_to_segments(line):
    coords = list(line.coords)
    segments = []

    for i in range(len(coords) - 1):
        seg = LineString([coords[i], coords[i + 1]])
        segments.append(seg)

    return segments


for idx, row in gdf_m.iterrows():
    geom = row.geometry

    if geom is None or geom.is_empty:
        continue

    lines = list(geom.geoms) if geom.geom_type == "MultiLineString" else [geom]

    for line in lines:
        segments = split_line_to_segments(line)

        for seg in segments:
            coords = list(seg.coords)
            start = tuple(coords[0])
            end = tuple(coords[1])

            score = row.get("match_score", 0.5)
            dist = row.get("distance_to_gpx_m", 999)
            overlap = row.get("overlap_ratio", 0)

            cost = (
                0.05 * (1.0 - score) +
                0.65 * min(dist / 30.0, 1.0) +
                0.30 * (1.0 - overlap)
            )

            # GPX corridor 懲罰保留
            cost += 0.15 * min(dist, 50)

            # 暫時不要 hard continue，避免 graph 被切斷
            # if dist > 25:
            #     continue

            G.add_edge(start, end, weight=cost, idx=idx, snap_link=0)

print(f"輸入 segments: {len(gdf)}")
print(f"Graph nodes: {len(G.nodes)}")
print(f"Graph edges before snapping: {len(G.edges)}")


# =========================================================
# 7. Optional snap link
# =========================================================
if ENABLE_SNAP_LINK:
    nodes = list(G.nodes)

    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            d = node_distance(nodes[i], nodes[j])

            if d <= SNAP_TOLERANCE_M:
                if not G.has_edge(nodes[i], nodes[j]):
                    G.add_edge(
                        nodes[i],
                        nodes[j],
                        weight=SNAP_LINK_WEIGHT,
                        idx=-1,
                        snap_link=1,
                    )

print(f"ENABLE_SNAP_LINK: {ENABLE_SNAP_LINK}")
print(f"Graph edges after snapping: {len(G.edges)}")


# =========================================================
# 8. 建立 ordered anchors
# =========================================================
activity_interval_rows_m = make_gpx_interval_points(
    activity_line_m,
    GPX_ANCHOR_INTERVAL_M,
)

anchor_ranked = []

# ib0c start / via / end 仍需投影到活動軌跡上取得 progress
anchor_ranked.append(("start", start_pt_m, activity_line_m.project(start_pt_m)))
anchor_ranked.append(("via", via_pt_m, activity_line_m.project(via_pt_m)))
anchor_ranked.append(("end", end_pt_m, activity_line_m.project(end_pt_m)))

# activity interval anchors 本身已知 progress，不再用 project 反推
for role, pt, progress_m in activity_interval_rows_m:
    anchor_ranked.append((role, pt, progress_m))

# 依 GPX progress 排序
anchor_ranked = sorted(anchor_ranked, key=lambda x: x[2])

# 去除過近 anchor
filtered = []

for role, pt, prog in anchor_ranked:
    if not filtered:
        filtered.append((role, pt, prog))
    else:
        if abs(prog - filtered[-1][2]) >= MIN_ANCHOR_SPACING_M:
            filtered.append((role, pt, prog))

anchor_ranked = filtered

print(f"ordered anchors: {len(anchor_ranked)}")
print("first anchor:", anchor_ranked[0][0], anchor_ranked[0][2])
print("last anchor:", anchor_ranked[-1][0], anchor_ranked[-1][2])


# =========================================================
# 9. anchors 轉 graph nodes
# =========================================================
anchor_nodes = []

for role, pt, progress_m in anchor_ranked:
    node = nearest_segment_node(gdf_m, pt)
    anchor_nodes.append((role, node, progress_m))

# 去除連續重複 node
dedup_anchor_nodes = []

for role, node, progress_m in anchor_nodes:
    if not dedup_anchor_nodes or node != dedup_anchor_nodes[-1][1]:
        dedup_anchor_nodes.append((role, node, progress_m))

anchor_nodes = dedup_anchor_nodes

print(f"anchor nodes after dedup: {len(anchor_nodes)}")


# =========================================================
# 10. 依序 shortest path
# =========================================================
full_path = []

for i in range(len(anchor_nodes) - 1):
    role_a, node_a, prog_a = anchor_nodes[i]
    role_b, node_b, prog_b = anchor_nodes[i + 1]

    if node_a == node_b:
        continue

    try:
        sub_path = nx.shortest_path(G, node_a, node_b, weight="weight")
    except nx.NetworkXNoPath:
        print(f"WARNING: no path between {role_a} and {role_b}")
        continue

    if not full_path:
        full_path.extend(sub_path)
    else:
        full_path.extend(sub_path[1:])

print(f"path length nodes: {len(full_path)}")

# =========================================================
# 10b. 輸出 ordered path：保留真正路徑順序
# =========================================================
if len(full_path) < 2:
    raise ValueError("full_path 節點數不足，無法建立 ordered path")

ordered_line_m = LineString(full_path)

ordered_path_gdf = gpd.GeoDataFrame(
    [{
        "route_id": ROUTE_ID,
        "case_id": CASE_ID,
        "case_name": CASE_NAME,
        "activity_type": ACTIVITY_TYPE,
        "activity_name": ACTIVITY_NAME,
        "activity_fp": str(ACTIVITY_FP),
        "ia1_version": IA1_VERSION,
        "ia1_dataset_id": IA1_DATASET_ID,
        "ia1_snapshot_tag": IA1_SNAPSHOT_TAG,
        "analysis_unit": "ordered_mainline_path",
        "source": "ib0b_full_path",
        "input_stage": INPUT_STAGE,
        "ab_mode": AB_MODE,
        "anchor_source_mode": ANCHOR_SOURCE_MODE,
        "path_node_n": len(full_path),
        "length_m": ordered_line_m.length,
        "geometry": ordered_line_m,
    }],
    geometry="geometry",
    crs=metric_crs,
)

ordered_path_gdf_wgs84 = ordered_path_gdf.to_crs("EPSG:4326")

ordered_path_gdf_wgs84.to_file(
    OUT_ORDERED_PATH_FP,
    driver="GeoJSON"
)

print(f"ordered path 輸出：{OUT_ORDERED_PATH_FP}")
print(f"ordered path length m: {ordered_line_m.length:.2f}")

# A 模式作為正式 pipeline 結果，額外輸出標準檔名
if AB_MODE == "A":
    ordered_path_gdf_wgs84.to_file(
        OUT_STANDARD_ORDERED_PATH_FP,
        driver="GeoJSON"
    )
    print(f"正式 downstream ordered path 輸出：{OUT_STANDARD_ORDERED_PATH_FP}")


# =========================================================
# 11. 還原 segments
# =========================================================
edge_set = set()

for i in range(len(full_path) - 1):
    u = full_path[i]
    v = full_path[i + 1]

    if G.has_edge(u, v):
        data = G.get_edge_data(u, v)
        idx = data.get("idx", -1)
        edge_set.add(idx)

valid_idx = [idx for idx in edge_set if idx != -1]
mainline = gdf.loc[valid_idx].copy()

mainline["route_id"] = ROUTE_ID
mainline["case_id"] = CASE_ID
mainline["case_name"] = CASE_NAME
mainline["activity_type"] = ACTIVITY_TYPE
mainline["activity_name"] = ACTIVITY_NAME
mainline["activity_fp"] = str(ACTIVITY_FP)
mainline["ia1_version"] = IA1_VERSION
mainline["ia1_dataset_id"] = IA1_DATASET_ID
mainline["ia1_snapshot_tag"] = IA1_SNAPSHOT_TAG
mainline["input_stage"] = INPUT_STAGE
mainline["ab_mode"] = AB_MODE

# # =========================================================
# # 11a. 主幹二次清理：移除離 GPX 過遠的 spur / tail
# #      因為入口 service road 本來就可能不貼 GPX，硬砍會不穩。
# # =========================================================
# mainline = mainline[
#     mainline["distance_to_gpx_m"] < 20
# ].copy()

# print(f"主幹 segments: {len(mainline)}")

# =========================================================
# 11a. 標記 mainline_role：approach / trail_core
# =========================================================
APPROACH_HIGHWAYS = {
    "service",
    "tertiary",
    "secondary",
    "primary",
    "residential",
    "unclassified",
    "road",
}

TRAIL_HIGHWAYS = {
    "footway",
    "steps",
    "path",
    "track",
}

def classify_mainline_role(row):
    hw = str(row.get("highway_norm", "")).lower()
    role = str(row.get("route_role", "")).lower()

    if hw in APPROACH_HIGHWAYS:
        return "approach"

    if hw in TRAIL_HIGHWAYS:
        return "trail_core"

    if role == "approach_or_road":
        return "approach"

    if role == "trail_core":
        return "trail_core"

    return "unknown"

mainline["mainline_role"] = mainline.apply(classify_mainline_role, axis=1)

print(f"主幹 segments: {len(mainline)}")
print("\n--- mainline_role distribution ---")
print(mainline["mainline_role"].value_counts(dropna=False))

# =========================================================
# 11b. Debug CSV：輸出被選入主幹的 segments
# =========================================================
DEBUG_MAINLINE_CSV = OUT_DEBUG_CSV

debug_cols = [
    "route_id",
    "case_id",
    "case_name",
    "activity_type",
    "activity_name",
    "activity_fp",
    "ia1_version",
    "ia1_dataset_id",
    "ia1_snapshot_tag",
    "input_stage",
    "ab_mode",
    "osm_way_id",
    "name",
    "highway_norm",
    "route_role",
    "mainline_role",
    "distance_to_gpx_m",
    "overlap_ratio",
    "match_score",
]

exist_cols = [c for c in debug_cols if c in mainline.columns]
mainline[exist_cols].to_csv(DEBUG_MAINLINE_CSV, index=False, encoding="utf-8-sig")

print(f"主幹 debug CSV：{DEBUG_MAINLINE_CSV}")

mainline.to_file(OUT_FP, driver="GeoJSON")
print(f"mainline segments 輸出：{OUT_FP}")

# A 模式額外輸出正式標準檔名
if AB_MODE == "A":
    mainline.to_file(OUT_STANDARD_MAINLINE_FP, driver="GeoJSON")
    print(f"正式 downstream mainline segments 輸出：{OUT_STANDARD_MAINLINE_FP}")


# =========================================================
# 11c. QA style helper
# =========================================================
def mainline_style(feat):
    role = feat["properties"].get("mainline_role", "")

    if role == "approach":
        return {
            "color": "orange",
            "weight": 5,
            "opacity": 0.9,
        }

    if role == "trail_core":
        return {
            "color": "red",
            "weight": 5,
            "opacity": 0.95,
        }

    return {
        "color": "purple",
        "weight": 4,
        "opacity": 0.8,
    }

# =========================================================
# 12. QA 地圖
# =========================================================
gdf_wgs84 = gdf.to_crs(epsg=4326)
mainline_wgs84 = mainline.to_crs(epsg=4326)

center_geom = mainline_wgs84.geometry.union_all().centroid
center = [center_geom.y, center_geom.x]

m = folium.Map(
    location=center,
    zoom_start=14,
    tiles="CartoDB positron",
    width="100%",
    height="800px",
)

# 背景：ib0 / ib0a 輸入路段
folium.GeoJson(
    gdf_wgs84,
    name=f"input_segments_{INPUT_STAGE}",
    style_function=lambda feat: {
        "color": "gray",
        "weight": 2,
        "opacity": 0.25,
    },
).add_to(m)

# activity route
folium.PolyLine(
    [(lat, lon) for lon, lat in activity_line.coords],
    color="black",
    weight=3,
    opacity=0.7,
    tooltip=f"{ACTIVITY_TYPE}: {ACTIVITY_NAME}",
).add_to(m)


# mainline
# folium.GeoJson(
#     mainline_wgs84,
#     name="mainline",
#     style_function=lambda feat: {
#         "color": "red",
#         "weight": 5,
#         "opacity": 0.95,
#     },
# ).add_to(m)

folium.GeoJson(
    mainline_wgs84,
    name=f"mainline_{INPUT_STAGE}",
    style_function=mainline_style,
).add_to(m)

# ib0c anchors
for _, row in anchors.iterrows():
    role = row["anchor_role"]
    color = {"start": "green", "via": "blue", "end": "red"}.get(role, "gray")
    icon = {"start": "play", "via": "flag", "end": "stop"}.get(role, "info-sign")

    folium.Marker(
        location=[row.geometry.y, row.geometry.x],
        tooltip=f"{role} - {row.get('anchor_source', '')}",
        icon=folium.Icon(color=color, icon=icon),
    ).add_to(m)

# activity interval anchors
anchor_points_wgs = gpd.GeoSeries(
    [pt for _, pt, _ in anchor_ranked],
    crs=metric_crs,
).to_crs("EPSG:4326")

for i, pt in enumerate(anchor_points_wgs):
    folium.CircleMarker(
        location=[pt.y, pt.x],
        radius=2,
        color="purple",
        fill=True,
        fill_opacity=0.5,
        tooltip=f"activity_anchor_{i}",
    ).add_to(m)

folium.LayerControl(collapsed=False).add_to(m)
m.save(OUT_HTML_FP)
print(f"QA 地圖輸出：{OUT_HTML_FP}")

if AB_MODE == "A":
    m.save(OUT_STANDARD_HTML_FP)
    print(f"正式 downstream QA 地圖輸出：{OUT_STANDARD_HTML_FP}")

# =========================================================
# 13. A/B summary
# =========================================================

summary = {
    "route_id": ROUTE_ID,
    "route_group": ROUTE_GROUP,
    "case_id": CASE_ID,
    "case_name": CASE_NAME,
    "activity_type": ACTIVITY_TYPE,
    "activity_name": ACTIVITY_NAME,
    "activity_fp": str(ACTIVITY_FP),
    "ia1_version": IA1_VERSION,
    "ia1_dataset_id": IA1_DATASET_ID,
    "ia1_snapshot_tag": IA1_SNAPSHOT_TAG,
    "ab_mode": AB_MODE,
    "input_stage": INPUT_STAGE,
    "input_fp": str(IN_FP),
    "anchor_fp": str(ANCHOR_FP),
    "anchor_source_mode": ANCHOR_SOURCE_MODE,
    "out_dir": str(OUT_DIR),

    "input_segments_n": len(gdf),
    "graph_nodes_n": len(G.nodes),
    "graph_edges_n": len(G.edges),
    "ordered_anchors_n": len(anchor_ranked),
    "anchor_nodes_n": len(anchor_nodes),
    "path_node_n": len(full_path),
    "mainline_segments_n": len(mainline),
    "ordered_path_length_m": float(ordered_line_m.length),

    "output_ordered_path_fp": str(OUT_ORDERED_PATH_FP),
    "output_mainline_fp": str(OUT_FP),
    "output_html_fp": str(OUT_HTML_FP),
}

# mainline_role 分布
if "mainline_role" in mainline.columns:
    role_counts = mainline["mainline_role"].value_counts(dropna=False).to_dict()
    for role, n in role_counts.items():
        summary[f"mainline_role_{role}_n"] = int(n)

# highway_norm 分布
if "highway_norm" in mainline.columns:
    hw_counts = mainline["highway_norm"].value_counts(dropna=False).to_dict()
    for hw, n in hw_counts.items():
        summary[f"highway_{hw}_n"] = int(n)

pd.DataFrame([summary]).to_csv(
    OUT_SUMMARY_CSV,
    index=False,
    encoding="utf-8-sig",
)

print(f"A/B summary 輸出：{OUT_SUMMARY_CSV}")
