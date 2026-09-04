from pathlib import Path
import argparse
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import geopandas as gpd
import folium
import networkx as nx
from shapely.geometry import LineString, Point


IB0_VERSION = "v1.1-identity-contract"
IB0_IDENTITY_CONTRACT = "canonical_osm_type_id_v1"


"""
ib0_gpx_to_osm_route_v1.1_identity_contract.py

定位：
- Activity-guided OSM candidate route matching
- 支援 GPX / FIT CSV / 一般 CSV 三位一體活動軌跡來源
- 讀取指定活動軌跡與 Ia1 / per-CASE_ID 產生之 OSM highway raw layer
- 從固定版 OSM highway 圖層中，篩選出最可能對應活動軌跡的候選路段集合
- 輸出 candidate / matched OSM route，作為後續 ib0a 修剪、ib0c 錨點建立與 ib0b 主幹路線抽取的基礎

主要功能：
1. 讀取 GPX / FIT CSV / 一般 CSV 並建立 activity route geometry
2. 讀取 Ia1 產生之 OSM highway raw layer
3. 以距離、重疊比例、highway 語意進行初步 matching
4. 輸出 candidate / matched GeoJSON、summary CSV 與 QA 地圖

注意：
- 本腳本不重新下載 OSM，底層 OSM 圖資由 ia1_osm_fetch_raw.py 或 case-level OSM layer copy/clip 管理
- 本版為 rule-based candidate matching，不是完整 graph-based map matching
- 後續由 ib0a / ib0c / ib0b 進行修剪、錨點約束與主幹路線抽取
"""


# =========================================================
# 0. 預設路徑與參數
# =========================================================
# scripts/ib0_route_match/<this_file.py> -> project root
# Avoid a machine-specific C:/D: hard-coded path.  Absolute CLI paths still
# work, while relative paths resolve against the repository containing this
# script rather than the terminal's current drive.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CASE_ID = "juansi_waterfall_fitcsv_20260503"
DEFAULT_ACTIVITY_FP = PROJECT_ROOT / "activity_input" / "csv" / "juansi_waterfall" / "3.csv"
DEFAULT_ACTIVITY_TYPE = "auto"

DEFAULT_GPX_BUFFER_FETCH_M = 60
DEFAULT_GPX_BUFFER_MATCH_M = 30
DEFAULT_MAX_DISTANCE_M = 20
DEFAULT_MIN_OVERLAP_RATIO = 0.30
DEFAULT_MATCH_SCORE_THRESHOLD = 0.55
DEFAULT_FALLBACK_MAX_ENDPOINT_OFFSET_M = 30
DEFAULT_FALLBACK_MAX_LENGTH_M = 1000

# 放寬候選集：先保留較多可能路型，再交給活動軌跡距離與重疊判斷
ALLOWED_HIGHWAY = [
    # trail core
    "path",
    "footway",
    "steps",
    "track",
    "pedestrian",
    # approach / road
    "service",
    "unclassified",
    "residential",
    "living_street",
    "road",
    "tertiary",
    "tertiary_link",
]

SEMANTIC_SCORE_MAP = {
    # trail core
    "path": 1.00,
    "steps": 0.95,
    "footway": 0.85,
    "track": 0.75,
    "pedestrian": 0.60,
    # approach / road
    "service": 0.45,
    "unclassified": 0.40,
    "residential": 0.35,
    "living_street": 0.35,
    "road": 0.30,
    "tertiary": 0.25,
    "tertiary_link": 0.20,
}


# =========================================================
# 1. CLI 參數
# =========================================================
def resolve_path(p: str | Path, project_root: Path = PROJECT_ROOT) -> Path:
    """將相對路徑轉成 project root 下的絕對路徑。"""
    p = Path(p)
    if p.is_absolute():
        return p
    return project_root / p


def parse_args():
    parser = argparse.ArgumentParser(
        description="ib0 activity-to-OSM route matching; supports GPX / FIT CSV / generic CSV."
    )

    parser.add_argument(
        "--case-id",
        default=DEFAULT_CASE_ID,
        help="CASE_ID / route_id, e.g. qixing_xiaoyoukeng_main_peak_20260315",
    )
    parser.add_argument(
        "--activity-fp",
        default=str(DEFAULT_ACTIVITY_FP),
        help="Activity file path. Supports GPX, FIT-converted CSV, or generic lat/lon CSV.",
    )
    parser.add_argument(
        "--activity-type",
        default=DEFAULT_ACTIVITY_TYPE,
        choices=["auto", "gpx", "fit_csv", "csv"],
        help="Activity source type. Use auto unless you need to force a parser.",
    )
    parser.add_argument(
        "--osm-raw-dir",
        default=None,
        help="Folder containing osm_highway_raw.geojson. Default: osm_raw_output/<case-id>",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Output folder. Default: outputs/ib0_route_match/<case-id>",
    )

    parser.add_argument("--ia1-version", default="case_level", help="Ia1 / OSM raw version label.")
    parser.add_argument("--ia1-snapshot-tag", default="case_osm_raw", help="Ia1 / OSM snapshot label.")

    parser.add_argument("--gpx-buffer-fetch-m", type=float, default=DEFAULT_GPX_BUFFER_FETCH_M)
    parser.add_argument("--gpx-buffer-match-m", type=float, default=DEFAULT_GPX_BUFFER_MATCH_M)
    parser.add_argument("--max-distance-m", type=float, default=DEFAULT_MAX_DISTANCE_M)
    parser.add_argument("--min-overlap-ratio", type=float, default=DEFAULT_MIN_OVERLAP_RATIO)
    parser.add_argument("--match-score-threshold", type=float, default=DEFAULT_MATCH_SCORE_THRESHOLD)
    parser.add_argument(
        "--enable-gpx-fallback",
        action="store_true",
        help=(
            "Explicitly allow activity-evidence connectors between disconnected "
            "selected OSM components. Disabled by default."
        ),
    )
    parser.add_argument(
        "--fallback-max-endpoint-offset-m",
        type=float,
        default=DEFAULT_FALLBACK_MAX_ENDPOINT_OFFSET_M,
        help="Maximum activity-point to selected-OSM-node offset for an approved fallback endpoint.",
    )
    parser.add_argument(
        "--fallback-max-length-m",
        type=float,
        default=DEFAULT_FALLBACK_MAX_LENGTH_M,
        help="Maximum activity subline length for one approved GPX fallback connector.",
    )

    return parser.parse_args()


# =========================================================
# 2. 活動軌跡讀取工具函式
# =========================================================
def parse_gpx_track(gpx_fp: Path) -> LineString:
    """
    解析 GPX，將所有 trkpt 串成一條 LineString。
    假設此 GPX 主要只有一條主路線。
    """
    if not gpx_fp.exists():
        raise FileNotFoundError(f"找不到 GPX：{gpx_fp}")

    tree = ET.parse(gpx_fp)
    root = tree.getroot()

    ns = {}
    if root.tag.startswith("{"):
        uri = root.tag.split("}")[0].strip("{")
        ns = {"gpx": uri}
        trkpt_xpath = ".//gpx:trkpt"
    else:
        trkpt_xpath = ".//trkpt"

    pts = []
    for trkpt in root.findall(trkpt_xpath, ns):
        lat = float(trkpt.attrib["lat"])
        lon = float(trkpt.attrib["lon"])
        pts.append((lon, lat))

    if len(pts) < 2:
        raise ValueError("GPX 軌跡點不足，無法建立路線")

    return LineString(dedup_points(pts))


def parse_fit_csv_track(csv_fp: Path) -> LineString:
    """
    解析 FIT 轉出的 CSV，支援 Garmin FIT semicircles 座標格式。
    將 record.position_lat[semicircles] / record.position_long[semicircles]
    轉成 WGS84 lat/lon，再串成 LineString。
    """
    if not csv_fp.exists():
        raise FileNotFoundError(f"找不到 CSV：{csv_fp}")

    df = pd.read_csv(csv_fp, low_memory=False)

    lat_col = "record.position_lat[semicircles]"
    lon_col = "record.position_long[semicircles]"

    if lat_col not in df.columns or lon_col not in df.columns:
        raise ValueError(
            f"CSV 找不到 FIT semicircles 經緯度欄位，目前欄位為：{list(df.columns)}"
        )

    df = df[[lat_col, lon_col]].copy()
    df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
    df[lon_col] = pd.to_numeric(df[lon_col], errors="coerce")
    df = df.dropna(subset=[lat_col, lon_col])

    # FIT semicircles → degrees
    semicircle_to_deg = 180 / (2 ** 31)
    df["lat"] = df[lat_col] * semicircle_to_deg
    df["lon"] = df[lon_col] * semicircle_to_deg

    # 合理經緯度範圍過濾
    df = df[
        (df["lat"].between(-90, 90)) &
        (df["lon"].between(-180, 180))
    ].copy()

    if len(df) < 2:
        raise ValueError("CSV 有效經緯度點不足，無法建立路線")

    print(f"FIT CSV 有效 GPS 點數：{len(df)}")
    return LineString(dedup_points(list(zip(df["lon"], df["lat"]))))


def parse_generic_csv_track(csv_fp: Path) -> LineString:
    """
    解析一般 CSV 經緯度欄位。
    支援常見欄位名稱：lat/lon、latitude/longitude、緯度/經度、經度/緯度。
    """
    if not csv_fp.exists():
        raise FileNotFoundError(f"找不到 CSV：{csv_fp}")

    df = pd.read_csv(csv_fp, low_memory=False)
    col_map = {str(c).strip().lower(): c for c in df.columns}

    lat_candidates = ["lat", "latitude", "y", "緯度"]
    lon_candidates = ["lon", "lng", "longitude", "x", "經度"]

    lat_col = next((col_map[c] for c in lat_candidates if c in col_map), None)
    lon_col = next((col_map[c] for c in lon_candidates if c in col_map), None)

    if lat_col is None or lon_col is None:
        raise ValueError(
            "CSV 找不到一般經緯度欄位；支援 lat/lon, latitude/longitude, 緯度/經度。"
            f"目前欄位為：{list(df.columns)}"
        )

    df = df[[lat_col, lon_col]].copy()
    df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
    df[lon_col] = pd.to_numeric(df[lon_col], errors="coerce")
    df = df.dropna(subset=[lat_col, lon_col])

    df = df[
        (df[lat_col].between(-90, 90)) &
        (df[lon_col].between(-180, 180))
    ].copy()

    if len(df) < 2:
        raise ValueError("CSV 有效經緯度點不足，無法建立路線")

    print(f"Generic CSV 有效 GPS 點數：{len(df)}")
    return LineString(dedup_points(list(zip(df[lon_col], df[lat_col]))))


def dedup_points(pts):
    """去除連續重複點，避免 LineString 含大量相同座標。"""
    dedup_pts = []
    for pt in pts:
        if not dedup_pts or pt != dedup_pts[-1]:
            dedup_pts.append(pt)

    if len(dedup_pts) < 2:
        raise ValueError("去除重複點後有效點不足，無法建立路線")

    return dedup_pts


def infer_activity_type(activity_fp: Path, activity_type: str) -> str:
    """依副檔名與欄位自動判斷活動資料類型。"""
    activity_type = activity_type.lower().strip()
    if activity_type != "auto":
        return activity_type

    suffix = activity_fp.suffix.lower()
    if suffix == ".gpx":
        return "gpx"

    if suffix == ".csv":
        sample = pd.read_csv(activity_fp, nrows=5, low_memory=False)
        cols = set(sample.columns)
        if {
            "record.position_lat[semicircles]",
            "record.position_long[semicircles]",
        }.issubset(cols):
            return "fit_csv"
        return "csv"

    raise ValueError(f"無法自動判斷活動資料類型：{activity_fp}")


def load_activity_track(activity_fp: Path, activity_type: str) -> tuple[LineString, str]:
    """
    依活動資料格式載入軌跡，統一輸出 WGS84 LineString 與 resolved activity_type。
    支援：
    - gpx
    - fit_csv
    - csv
    """
    resolved_type = infer_activity_type(activity_fp, activity_type)

    if resolved_type == "gpx":
        return parse_gpx_track(activity_fp), resolved_type

    if resolved_type == "fit_csv":
        return parse_fit_csv_track(activity_fp), resolved_type

    if resolved_type == "csv":
        return parse_generic_csv_track(activity_fp), resolved_type

    raise ValueError(f"不支援的 activity_type：{resolved_type}")


# =========================================================
# 3. OSM / matching 工具函式
# =========================================================
def normalize_highway_value(v):
    if isinstance(v, list):
        return v[0] if len(v) > 0 else None
    return v


def clean_text_value(v):
    if isinstance(v, list):
        v = v[0] if v else ""
    if pd.isna(v):
        return ""
    text = str(v).strip().strip('"').lower()
    if text in {"", "nan", "none", "<na>", "null"}:
        return ""
    return text


def get_semantic_score(row):
    """
    優先使用 Ia1 若已輸出的 matching_semantic_score。
    若沒有，才退回使用 ib0 內建 SEMANTIC_SCORE_MAP。
    """
    for col in ["matching_semantic_score", "semantic_score", "walk_relevance_score"]:
        if col in row.index:
            try:
                v = float(row.get(col))
                if not np.isnan(v):
                    return v
            except Exception:
                pass

    hw = normalize_highway_value(row.get("highway_norm", row.get("highway", None)))
    return SEMANTIC_SCORE_MAP.get(hw, 0.10)


def classify_route_role(hw):
    hw = normalize_highway_value(hw)

    if hw in {"path", "footway", "steps", "track", "pedestrian"}:
        return "trail_core"
    elif hw in {"service", "unclassified", "residential", "living_street", "road", "tertiary", "tertiary_link"}:
        return "approach_or_road"
    else:
        return "other"


def get_center_latlon(line_wgs84: LineString):
    centroid = line_wgs84.centroid
    return centroid.y, centroid.x


def classify_selected(row, max_distance_m, min_overlap_ratio, match_score_threshold):
    cond1 = row["distance_to_activity_m"] <= max_distance_m
    cond2 = row["overlap_ratio"] >= min_overlap_ratio
    cond3 = row["match_score"] >= match_score_threshold
    return int((cond1 and cond2) or cond3)


def iter_lines(geom):
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "LineString":
        return [geom]
    if geom.geom_type == "MultiLineString":
        return list(geom.geoms)
    return []


def build_geometry_graph(gdf_m):
    """Build the same coordinate-node topology contract consumed by IB0B."""
    graph = nx.Graph()
    for idx, row in gdf_m.iterrows():
        for line in iter_lines(row.geometry):
            coords = list(line.coords)
            for a, b in zip(coords[:-1], coords[1:]):
                a = tuple(a)
                b = tuple(b)
                if a == b:
                    continue
                graph.add_edge(a, b, source_idx=idx)
    return graph


def nearest_graph_node(nodes, point):
    best_node = None
    best_dist = float("inf")
    for node in nodes:
        dist = point.distance(Point(node))
        if dist < best_dist:
            best_node = node
            best_dist = dist
    return best_node, best_dist


def dedup_coordinate_sequence(coords):
    out = []
    for coord in coords:
        coord = tuple(coord)
        if not out or coord != out[-1]:
            out.append(coord)
    return out


def detect_activity_component_gaps(
    candidate_m,
    activity_line_m,
    max_endpoint_offset_m,
    max_fallback_length_m,
):
    """
    Detect component transitions evidenced by the ordered activity coordinates.

    This function never draws a straight connector.  An approved connector is
    the original ordered activity coordinate subsequence, with its first/last
    coordinate locked to existing selected-OSM graph nodes so IB0B can validate
    every downstream graph edge.
    """
    graph = build_geometry_graph(candidate_m)
    if graph.number_of_nodes() == 0:
        return [], [], graph

    components = list(nx.connected_components(graph))
    component_by_node = {
        node: component_id
        for component_id, component in enumerate(components)
        for node in component
    }
    graph_nodes = list(graph.nodes)
    activity_coords = list(activity_line_m.coords)

    observations = []
    for activity_idx, coord in enumerate(activity_coords):
        activity_point = Point(coord)
        node, offset_m = nearest_graph_node(graph_nodes, activity_point)
        if node is None or offset_m > max_endpoint_offset_m:
            continue
        observations.append({
            "activity_idx": activity_idx,
            "node": node,
            "offset_m": float(offset_m),
            "component_id": component_by_node[node],
        })

    gaps = []
    fallbacks = []
    seen_component_pairs = set()

    for left, right in zip(observations[:-1], observations[1:]):
        if left["component_id"] == right["component_id"]:
            continue

        component_pair = tuple(sorted((left["component_id"], right["component_id"])))
        if component_pair in seen_component_pairs:
            continue
        seen_component_pairs.add(component_pair)

        start_idx = left["activity_idx"]
        end_idx = right["activity_idx"]
        if end_idx <= start_idx:
            continue

        fallback_coords = dedup_coordinate_sequence(
            [left["node"]]
            + activity_coords[start_idx:end_idx + 1]
            + [right["node"]]
        )
        fallback_line = LineString(fallback_coords)
        direct_gap_m = Point(left["node"]).distance(Point(right["node"]))
        approved = (
            len(fallback_coords) >= 2
            and fallback_line.length <= max_fallback_length_m
        )
        status = "APPROVED" if approved else "REJECTED_LENGTH"

        gap_id = f"gpx_fallback_{len(gaps) + 1:03d}"
        gaps.append({
            "gap_id": gap_id,
            "from_component_id": left["component_id"],
            "to_component_id": right["component_id"],
            "from_activity_idx": start_idx,
            "to_activity_idx": end_idx,
            "from_endpoint_offset_m": left["offset_m"],
            "to_endpoint_offset_m": right["offset_m"],
            "direct_gap_m": float(direct_gap_m),
            "activity_fallback_length_m": float(fallback_line.length),
            "status": status,
        })

        if approved:
            fallbacks.append((gap_id, fallback_line, gaps[-1]))

    return gaps, fallbacks, graph


# =========================================================
# 4. 主流程
# =========================================================
def main():
    args = parse_args()

    case_id = args.case_id
    activity_fp = resolve_path(args.activity_fp)
    osm_raw_dir = resolve_path(args.osm_raw_dir) if args.osm_raw_dir else PROJECT_ROOT / "osm_raw_output" / case_id
    out_dir = resolve_path(args.out_dir) if args.out_dir else PROJECT_ROOT / "outputs" / "ib0_route_match" / case_id
    out_dir.mkdir(parents=True, exist_ok=True)

    osm_highway_fp = osm_raw_dir / "osm_highway_raw.geojson"
    ia1_dataset_id = osm_raw_dir.name

    candidate_geojson_fp = out_dir / f"{case_id}_activity_osm_candidates.geojson"
    matched_geojson_fp = out_dir / f"{case_id}_activity_osm_matched.geojson"
    qa_html_fp = out_dir / f"{case_id}_activity_osm_matched_map.html"
    summary_csv_fp = out_dir / f"{case_id}_activity_osm_match_summary.csv"
    run_summary_fp = out_dir / f"{case_id}_activity_osm_match_run_summary.txt"
    component_gap_qa_fp = out_dir / f"{case_id}_activity_osm_component_gaps.csv"

    # =========================================================
    # 4-1. 讀取活動軌跡 GPX / FIT CSV / CSV
    # =========================================================
    activity_line, resolved_activity_type = load_activity_track(activity_fp, args.activity_type)

    activity_gdf = gpd.GeoDataFrame(
        [{"route_name": activity_fp.name, "geometry": activity_line}],
        geometry="geometry",
        crs="EPSG:4326",
    )

    print("活動軌跡載入成功：", activity_fp)
    print("活動資料類型：", resolved_activity_type)
    print("軌跡點數（近似）：", len(list(activity_line.coords)))

    center_lat, center_lon = get_center_latlon(activity_line)

    metric_crs = activity_gdf.estimate_utm_crs()
    activity_gdf_m = activity_gdf.to_crs(metric_crs)
    activity_line_m = activity_gdf_m.geometry.iloc[0]

    activity_buffer_fetch = activity_line_m.buffer(args.gpx_buffer_fetch_m)
    activity_buffer_match = activity_line_m.buffer(args.gpx_buffer_match_m)

    # =========================================================
    # 4-2. 讀取 Ia1 / case-level OSM highway raw layer
    # =========================================================
    if not osm_highway_fp.exists():
        raise FileNotFoundError(
            f"找不到 OSM highway raw layer：{osm_highway_fp.resolve()}，請先執行 ia1 或建立 per-CASE_ID OSM raw folder"
        )

    print("讀取 OSM highway raw layer:", osm_highway_fp.resolve())
    gdf_osm = gpd.read_file(osm_highway_fp)

    if gdf_osm.empty:
        raise ValueError("OSM highway raw layer 為空")

    gdf_osm = gdf_osm[gdf_osm.geometry.type.isin(["LineString", "MultiLineString"])].copy()

    if gdf_osm.crs is None:
        gdf_osm = gdf_osm.set_crs("EPSG:4326")

    # 優先使用 Ia1 已正規化的 highway_norm；若舊檔沒有才 fallback
    if "highway_norm" not in gdf_osm.columns:
        if "highway" not in gdf_osm.columns:
            raise ValueError("OSM highway layer 缺少 highway / highway_norm 欄位")
        gdf_osm["highway_norm"] = gdf_osm["highway"].apply(normalize_highway_value)

    # 清理 highway_norm，避免 list / nan / none / 大小寫造成漏篩
    gdf_osm["highway_norm"] = gdf_osm["highway_norm"].apply(clean_text_value)

    # route_role 若 Ia1 已提供則沿用；否則才由 ib0 fallback 判斷
    if "route_role" not in gdf_osm.columns:
        gdf_osm["route_role"] = gdf_osm["highway_norm"].apply(classify_route_role)
    else:
        gdf_osm["route_role"] = gdf_osm["route_role"].apply(clean_text_value)

    # 最後才依允許路型篩選
    gdf_osm = gdf_osm[gdf_osm["highway_norm"].isin(ALLOWED_HIGHWAY)].copy()

    if gdf_osm.empty:
        raise ValueError("過濾後無符合條件的 OSM 候選路段")

    gdf_osm_m = gdf_osm.to_crs(metric_crs)

    # 只保留與 fetch buffer 相交者
    gdf_osm_m = gdf_osm_m[gdf_osm_m.intersects(activity_buffer_fetch)].copy()

    if gdf_osm_m.empty:
        raise ValueError("活動軌跡附近無候選 OSM 路段")

    # =========================================================
    # 4-3. 計算 matching 特徵
    # =========================================================
    print("計算 matching 特徵中...")

    gdf_osm_m["segment_len_m"] = gdf_osm_m.geometry.length
    gdf_osm_m["distance_to_activity_m"] = gdf_osm_m.geometry.distance(activity_line_m)

    intersections = gdf_osm_m.geometry.intersection(activity_buffer_match)
    gdf_osm_m["overlap_len_m"] = intersections.length
    gdf_osm_m["overlap_ratio"] = (
        gdf_osm_m["overlap_len_m"] / gdf_osm_m["segment_len_m"]
    ).replace([np.inf, -np.inf], np.nan).fillna(0)

    gdf_osm_m["semantic_score"] = gdf_osm_m.apply(get_semantic_score, axis=1)

    # 距離分數：越近越高
    gdf_osm_m["distance_score"] = 1 - np.clip(
        gdf_osm_m["distance_to_activity_m"] / args.gpx_buffer_match_m, 0, 1
    )

    # 綜合分數
    gdf_osm_m["match_score"] = (
        0.45 * gdf_osm_m["distance_score"] +
        0.35 * gdf_osm_m["overlap_ratio"] +
        0.20 * gdf_osm_m["semantic_score"]
    )

    gdf_osm_m["selected"] = gdf_osm_m.apply(
        lambda row: classify_selected(
            row,
            args.max_distance_m,
            args.min_overlap_ratio,
            args.match_score_threshold,
        ),
        axis=1,
    )

    # =========================================================
    # 4-4. metadata：保留本次匹配參數，方便專利/實驗追溯
    # =========================================================
    gdf_osm_m["pipeline_stage"] = "ib0_activity_to_osm_route"
    gdf_osm_m["case_id"] = case_id
    gdf_osm_m["route_id"] = case_id
    gdf_osm_m["ia1_version"] = args.ia1_version
    gdf_osm_m["ia1_dataset_id"] = ia1_dataset_id
    gdf_osm_m["ia1_snapshot_tag"] = args.ia1_snapshot_tag
    gdf_osm_m["activity_type"] = resolved_activity_type
    gdf_osm_m["activity_source"] = activity_fp.name
    gdf_osm_m["activity_fp"] = str(activity_fp)

    # 為了相容舊版 ib0a，暫時保留 gpx_source / distance_to_gpx_m 欄位
    gdf_osm_m["gpx_source"] = activity_fp.name
    gdf_osm_m["distance_to_gpx_m"] = gdf_osm_m["distance_to_activity_m"]

    gdf_osm_m["osm_source"] = str(osm_highway_fp)

    gdf_osm_m["activity_buffer_fetch_m"] = args.gpx_buffer_fetch_m
    gdf_osm_m["activity_buffer_match_m"] = args.gpx_buffer_match_m
    gdf_osm_m["gpx_buffer_fetch_m"] = args.gpx_buffer_fetch_m
    gdf_osm_m["gpx_buffer_match_m"] = args.gpx_buffer_match_m
    gdf_osm_m["max_distance_m"] = args.max_distance_m
    gdf_osm_m["min_overlap_ratio"] = args.min_overlap_ratio
    gdf_osm_m["match_score_threshold"] = args.match_score_threshold

    # =========================================================
    # OSM identity preservation
    # =========================================================
    # IA1 v1.5.6+ GeoJSON 已正式保存 canonical OSM identity：
    #   osm_type = node / way / relation
    #   osm_id   = 真正 OSM element ID
    #
    # IB0 不得以 GeoDataFrame row index 覆蓋上述 identity。
    # MultiIndex / dataframe-index 邏輯僅保留給舊版資料相容。

    if {"osm_type", "osm_id"}.issubset(gdf_osm_m.columns):
        # Preferred path: preserve IA1 canonical identity exactly.
        gdf_osm_m["osm_type"] = (
            gdf_osm_m["osm_type"]
            .astype("string")
            .str.lower()
        )

        # Compatibility alias for existing IB0B prototypes.
        # New consumers must prefer osm_type.
        gdf_osm_m["osm_element_type"] = gdf_osm_m["osm_type"]

        # osm_way_id is graph convenience only and is populated only for ways.
        gdf_osm_m["osm_way_id"] = pd.NA
        is_way = gdf_osm_m["osm_type"].eq("way").fillna(False)
        gdf_osm_m.loc[is_way, "osm_way_id"] = (
            gdf_osm_m.loc[is_way, "osm_id"].astype("string")
        )

    elif isinstance(gdf_osm_m.index, pd.MultiIndex):
        # Legacy compatibility path.  Promote the legacy element type to the
        # new canonical field, but never invent an ID from a RangeIndex.
        gdf_osm_m["osm_type"] = (
            pd.Series(
                gdf_osm_m.index.get_level_values(0),
                index=gdf_osm_m.index,
                dtype="string",
            )
            .str.lower()
        )
        gdf_osm_m["osm_element_type"] = gdf_osm_m["osm_type"]
        gdf_osm_m["osm_id"] = gdf_osm_m.index.get_level_values(1)

        gdf_osm_m["osm_way_id"] = pd.NA
        is_way = gdf_osm_m["osm_type"].eq("way").fillna(False)
        gdf_osm_m.loc[is_way, "osm_way_id"] = (
            gdf_osm_m.loc[is_way, "osm_id"].astype("string")
        )

    else:
        # Very old/unknown input without canonical OSM identity.
        # Do not use dataframe row index as an OSM ID.
        gdf_osm_m["osm_type"] = pd.NA
        gdf_osm_m["osm_element_type"] = "unknown"
        gdf_osm_m["osm_id"] = pd.NA
        gdf_osm_m["osm_way_id"] = pd.NA

    gdf_osm_m["identity_contract"] = IB0_IDENTITY_CONTRACT
    gdf_osm_m["evidence_id"] = pd.NA

    if "name" not in gdf_osm_m.columns:
        gdf_osm_m["name"] = None

    gdf_osm_m["name"] = gdf_osm_m["name"].fillna("")

    # Geometry provenance is explicit.  Ordinary rows remain OSM-sourced;
    # activity evidence may only be appended through the guarded block below.
    gdf_osm_m["geometry_source"] = "osm"
    gdf_osm_m["fallback_reason"] = ""
    gdf_osm_m["fallback_gap_id"] = ""
    gdf_osm_m["fallback_direct_gap_m"] = np.nan
    gdf_osm_m["fallback_activity_length_m"] = np.nan
    gdf_osm_m["fallback_endpoint_offset_max_m"] = np.nan
    gdf_osm_m["topology_contract"] = "osm_graph_edge"

    # =========================================================
    # 4-4A. Selected graph component QA + optional GPX fallback
    # =========================================================
    # Use the complete IB0 candidate graph here, not only selected/matched rows.
    # Approach/service segments can be valid route evidence while intentionally
    # failing the semantic matched threshold.  Checking only matched rows hides
    # the route-head component and may instead approve an unrelated small gap.
    candidate_graph_m = gdf_osm_m.copy()
    component_gaps, fallback_lines, candidate_graph = detect_activity_component_gaps(
        candidate_graph_m,
        activity_line_m,
        args.fallback_max_endpoint_offset_m,
        args.fallback_max_length_m,
    )

    for gap in component_gaps:
        if gap["status"] == "APPROVED" and not args.enable_gpx_fallback:
            gap["status"] = "DETECTED_FALLBACK_DISABLED"

    gap_columns = [
        "gap_id",
        "from_component_id",
        "to_component_id",
        "from_activity_idx",
        "to_activity_idx",
        "from_endpoint_offset_m",
        "to_endpoint_offset_m",
        "direct_gap_m",
        "activity_fallback_length_m",
        "status",
    ]
    pd.DataFrame(component_gaps, columns=gap_columns).to_csv(
        component_gap_qa_fp,
        index=False,
        encoding="utf-8-sig",
    )

    approved_fallback_n = 0
    if args.enable_gpx_fallback and fallback_lines:
        fallback_rows = []
        for gap_id, fallback_line, gap in fallback_lines:
            fallback_rows.append({
                "pipeline_stage": "ib0_activity_to_osm_route",
                "case_id": case_id,
                "route_id": case_id,
                "ia1_version": args.ia1_version,
                "ia1_dataset_id": ia1_dataset_id,
                "ia1_snapshot_tag": args.ia1_snapshot_tag,
                "activity_type": resolved_activity_type,
                "activity_source": activity_fp.name,
                "activity_fp": str(activity_fp),
                "gpx_source": activity_fp.name,
                "osm_source": str(osm_highway_fp),
                "activity_buffer_fetch_m": args.gpx_buffer_fetch_m,
                "activity_buffer_match_m": args.gpx_buffer_match_m,
                "gpx_buffer_fetch_m": args.gpx_buffer_fetch_m,
                "gpx_buffer_match_m": args.gpx_buffer_match_m,
                "max_distance_m": args.max_distance_m,
                "min_overlap_ratio": args.min_overlap_ratio,
                "match_score_threshold": args.match_score_threshold,
                "osm_type": None,
                "osm_element_type": "activity_evidence",
                "osm_id": None,
                "osm_way_id": None,
                "identity_contract": IB0_IDENTITY_CONTRACT,
                "evidence_id": gap_id,
                "name": "GPX evidence connector",
                "highway": "gpx_fallback",
                "highway_norm": "gpx_fallback",
                "route_role": "activity_connector",
                "segment_len_m": fallback_line.length,
                "distance_to_activity_m": 0.0,
                "distance_to_gpx_m": 0.0,
                "overlap_len_m": fallback_line.length,
                "overlap_ratio": 1.0,
                "semantic_score": 1.0,
                "distance_score": 1.0,
                "match_score": 1.0,
                "selected": 1,
                "geometry_source": "gpx_fallback",
                "fallback_reason": "selected_osm_components_disconnected_local_activity_evidence",
                "fallback_gap_id": gap_id,
                "fallback_direct_gap_m": gap["direct_gap_m"],
                "fallback_activity_length_m": gap["activity_fallback_length_m"],
                "fallback_endpoint_offset_max_m": max(
                    gap["from_endpoint_offset_m"],
                    gap["to_endpoint_offset_m"],
                ),
                "topology_contract": "activity_coordinate_sequence_with_osm_node_endpoints",
                "geometry": fallback_line,
            })

        fallback_gdf_m = gpd.GeoDataFrame(
            fallback_rows,
            geometry="geometry",
            crs=metric_crs,
        )
        gdf_osm_m = pd.concat([gdf_osm_m, fallback_gdf_m], ignore_index=True)
        gdf_osm_m = gpd.GeoDataFrame(gdf_osm_m, geometry="geometry", crs=metric_crs)
        approved_fallback_n = len(fallback_gdf_m)

    print("Candidate OSM graph components:", nx.number_connected_components(candidate_graph) if candidate_graph.number_of_nodes() else 0)
    print("Activity-evidenced component gaps:", len(component_gaps))
    print("Approved GPX fallback connectors:", approved_fallback_n)
    print("Component gap QA:", component_gap_qa_fp.resolve())

    # =========================================================
    # 4-5. 輸出 GeoJSON
    # =========================================================
    candidate_cols = [
        "pipeline_stage",
        "case_id",
        "route_id",
        "ia1_version",
        "ia1_dataset_id",
        "ia1_snapshot_tag",
        "activity_type",
        "activity_source",
        "activity_fp",
        "gpx_source",
        "osm_source",

        "activity_buffer_fetch_m",
        "activity_buffer_match_m",
        "gpx_buffer_fetch_m",
        "gpx_buffer_match_m",
        "max_distance_m",
        "min_overlap_ratio",
        "match_score_threshold",

        "geometry_source",
        "fallback_reason",
        "fallback_gap_id",
        "fallback_direct_gap_m",
        "fallback_activity_length_m",
        "fallback_endpoint_offset_max_m",
        "topology_contract",

        "osm_type",
        "osm_element_type",
        "osm_id",
        "osm_way_id",
        "identity_contract",
        "evidence_id",
        "name",
        "highway",
        "highway_norm",
        "route_role",
        "segment_len_m",
        "distance_to_activity_m",
        "distance_to_gpx_m",
        "overlap_len_m",
        "overlap_ratio",
        "semantic_score",
        "distance_score",
        "match_score",
        "selected",
        "geometry",
    ]

    existing_candidate_cols = [c for c in candidate_cols if c in gdf_osm_m.columns]

    gdf_candidates = gdf_osm_m[existing_candidate_cols].copy().to_crs("EPSG:4326")
    gdf_matched = gdf_candidates[gdf_candidates["selected"] == 1].copy()

    # =========================================================
    # 4-5A. Canonical identity contract QA
    # =========================================================
    osm_rows = gdf_candidates[
        gdf_candidates["geometry_source"].eq("osm")
    ].copy()

    canonical_populated = (
        osm_rows["osm_type"].notna() & osm_rows["osm_id"].notna()
    )
    alias_equal = (
        osm_rows["osm_type"].astype("string")
        == osm_rows["osm_element_type"].astype("string")
    ).fillna(False)

    way_rows = osm_rows[osm_rows["osm_type"].astype("string").eq("way")].copy()
    way_id_equal = (
        way_rows["osm_way_id"].astype("string")
        == way_rows["osm_id"].astype("string")
    ).fillna(False)

    canonical_populated_n = int(canonical_populated.sum())
    alias_equal_n = int(alias_equal.sum())
    way_id_equal_n = int(way_id_equal.sum())

    print("IB0_IDENTITY_QA")
    print(f"  contract: {IB0_IDENTITY_CONTRACT}")
    print(f"  osm rows: {len(osm_rows)}")
    print(f"  canonical populated: {canonical_populated_n}/{len(osm_rows)}")
    print(f"  osm_type == osm_element_type: {alias_equal_n}/{len(osm_rows)}")
    print(f"  way osm_way_id == osm_id: {way_id_equal_n}/{len(way_rows)}")

    if canonical_populated_n != len(osm_rows):
        raise RuntimeError("IB0_IDENTITY_CONTRACT_FAIL: missing canonical osm_type/osm_id")
    if alias_equal_n != len(osm_rows):
        raise RuntimeError("IB0_IDENTITY_CONTRACT_FAIL: compatibility alias mismatch")
    if way_id_equal_n != len(way_rows):
        raise RuntimeError("IB0_IDENTITY_CONTRACT_FAIL: osm_way_id mismatch")

    if gdf_matched.empty:
        print("警告：本次沒有任何 OSM 路段通過 selected 條件")
        print("建議檢查 matching 參數：")
        print(f"- MAX_DISTANCE_M = {args.max_distance_m}")
        print(f"- MIN_OVERLAP_RATIO = {args.min_overlap_ratio}")
        print(f"- MATCH_SCORE_THRESHOLD = {args.match_score_threshold}")

    gdf_candidates.to_file(candidate_geojson_fp, driver="GeoJSON")
    gdf_matched.to_file(matched_geojson_fp, driver="GeoJSON")

    print("候選路段輸出：", candidate_geojson_fp.resolve())
    print("匹配路段輸出：", matched_geojson_fp.resolve())

    # =========================================================
    # 4-6. 輸出 summary csv
    # =========================================================
    summary_rows = []

    for (role, hw), sub in gdf_candidates.groupby(["route_role", "highway_norm"]):
        summary_rows.append({
            "pipeline_stage": "ib0_activity_to_osm_route",
            "case_id": case_id,
            "route_id": case_id,
            "ia1_version": args.ia1_version,
            "ia1_dataset_id": ia1_dataset_id,
            "ia1_snapshot_tag": args.ia1_snapshot_tag,
            "activity_type": resolved_activity_type,
            "activity_source": activity_fp.name,
            "activity_fp": str(activity_fp),

            # 為了相容舊版欄位
            "gpx_source": activity_fp.name,

            "osm_source": str(osm_highway_fp),
            "activity_buffer_fetch_m": args.gpx_buffer_fetch_m,
            "activity_buffer_match_m": args.gpx_buffer_match_m,
            "gpx_buffer_fetch_m": args.gpx_buffer_fetch_m,
            "gpx_buffer_match_m": args.gpx_buffer_match_m,
            "max_distance_m": args.max_distance_m,
            "min_overlap_ratio": args.min_overlap_ratio,
            "match_score_threshold": args.match_score_threshold,

            "route_role": role,
            "highway_norm": hw,
            "candidate_n": len(sub),
            "selected_n": int(sub["selected"].sum()),
            "mean_distance_to_activity_m": sub["distance_to_activity_m"].mean(),
            "mean_distance_to_gpx_m": sub["distance_to_gpx_m"].mean(),
            "mean_overlap_ratio": sub["overlap_ratio"].mean(),
            "mean_match_score": sub["match_score"].mean(),
        })

    summary_df = pd.DataFrame(summary_rows).sort_values(
        by=["selected_n", "candidate_n"],
        ascending=[False, False]
    )
    summary_df.to_csv(summary_csv_fp, index=False, encoding="utf-8-sig")

    print("摘要輸出：", summary_csv_fp.resolve())

    # =========================================================
    # 4-7. 建立 QA 地圖
    # =========================================================
    print("建立 QA 地圖中...")

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=14,
        tiles="CartoDB positron",
        width="100%",
        height="800px",
    )

    # Activity route 圖層
    fg_activity = folium.FeatureGroup(name="Activity route", show=True)
    activity_coords = [(lat, lon) for lon, lat in activity_line.coords]
    folium.PolyLine(
        activity_coords,
        color="blue",
        weight=4,
        opacity=0.9,
        tooltip="Activity route"
    ).add_to(fg_activity)
    fg_activity.add_to(m)

    # OSM 候選圖層
    fg_osm = folium.FeatureGroup(name="OSM candidates / matched", show=True)

    for _, row in gdf_candidates.iterrows():
        geom = row.geometry

        popup_text = (
            f"osm_way_id: {row.get('osm_way_id', '')}\n"
            f"name: {row.get('name', '')}\n"
            f"highway: {row.get('highway_norm', '')}\n"
            f"route_role: {row.get('route_role', '')}\n"
            f"distance_to_activity_m: {row.get('distance_to_activity_m', np.nan):.3f}\n"
            f"overlap_ratio: {row.get('overlap_ratio', np.nan):.3f}\n"
            f"semantic_score: {row.get('semantic_score', np.nan):.3f}\n"
            f"match_score: {row.get('match_score', np.nan):.3f}\n"
            f"selected: {row.get('selected', 0)}"
        )
        popup = folium.Popup(f"<pre>{popup_text}</pre>", max_width=350)

        color = "red" if row.get("selected", 0) == 1 else "gray"
        weight = 5 if row.get("selected", 0) == 1 else 2
        opacity = 0.9 if row.get("selected", 0) == 1 else 0.5

        if geom.geom_type == "LineString":
            coords = [(lat, lon) for lon, lat in geom.coords]
            folium.PolyLine(
                coords,
                color=color,
                weight=weight,
                opacity=opacity,
                popup=popup,
            ).add_to(fg_osm)

        elif geom.geom_type == "MultiLineString":
            for line in geom.geoms:
                coords = [(lat, lon) for lon, lat in line.coords]
                folium.PolyLine(
                    coords,
                    color=color,
                    weight=weight,
                    opacity=opacity,
                    popup=popup,
                ).add_to(fg_osm)

    fg_osm.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    m.save(qa_html_fp)

    print("QA 地圖輸出：", qa_html_fp.resolve())

    # =========================================================
    # 4-8. run summary txt + 終端摘要
    # =========================================================
    selected_role_text = (
        gdf_matched["route_role"].value_counts(dropna=False).to_string()
        if not gdf_matched.empty else "無入選路段"
    )
    selected_highway_text = (
        gdf_matched["highway_norm"].value_counts(dropna=False).to_string()
        if not gdf_matched.empty else "無入選路段"
    )

    run_summary = f"""ib0 activity-to-OSM route match summary
case_id: {case_id}
route_id: {case_id}
ia1_version: {args.ia1_version}
ia1_dataset_id: {ia1_dataset_id}
ia1_snapshot_tag: {args.ia1_snapshot_tag}
ib0_version: {IB0_VERSION}
identity_contract: {IB0_IDENTITY_CONTRACT}
osm_source: {osm_highway_fp}
activity_type: {resolved_activity_type}
activity_source: {activity_fp}
metric_crs: {metric_crs}
activity_points_approx: {len(list(activity_line.coords))}

parameters:
activity_buffer_fetch_m: {args.gpx_buffer_fetch_m}
activity_buffer_match_m: {args.gpx_buffer_match_m}
max_distance_m: {args.max_distance_m}
min_overlap_ratio: {args.min_overlap_ratio}
match_score_threshold: {args.match_score_threshold}
enable_gpx_fallback: {args.enable_gpx_fallback}
fallback_max_endpoint_offset_m: {args.fallback_max_endpoint_offset_m}
fallback_max_length_m: {args.fallback_max_length_m}

outputs:
candidates: {candidate_geojson_fp}
matched: {matched_geojson_fp}
summary_csv: {summary_csv_fp}
qa_html: {qa_html_fp}
component_gap_qa_csv: {component_gap_qa_fp}

counts:
candidate_n: {len(gdf_candidates)}
matched_n: {len(gdf_matched)}
candidate_osm_graph_components_before_fallback: {nx.number_connected_components(candidate_graph) if candidate_graph.number_of_nodes() else 0}
activity_evidenced_component_gap_n: {len(component_gaps)}
approved_gpx_fallback_n: {approved_fallback_n}
canonical_osm_identity_populated_n: {canonical_populated_n}
canonical_osm_identity_row_n: {len(osm_rows)}
osm_type_alias_equal_n: {alias_equal_n}
way_osm_way_id_equal_n: {way_id_equal_n}
way_osm_row_n: {len(way_rows)}

selected route_role distribution:
{selected_role_text}

selected highway distribution:
{selected_highway_text}
"""
    run_summary_fp.write_text(run_summary, encoding="utf-8")

    print("run summary 輸出：", run_summary_fp.resolve())

    print("\n=== match summary ===")
    print("Case ID:", case_id)
    print("Ia1 version:", args.ia1_version)
    print("Ia1 dataset:", ia1_dataset_id)
    print("Ia1 snapshot:", args.ia1_snapshot_tag)
    print("IB0 version:", IB0_VERSION)
    print("Identity contract:", IB0_IDENTITY_CONTRACT)
    print("OSM source:", osm_highway_fp)
    print("Activity type:", resolved_activity_type)
    print("Activity source:", activity_fp)

    print("候選路段數：", len(gdf_candidates))
    print("入選路段數：", len(gdf_matched))

    print("\n--- selected route_role distribution ---")
    print(selected_role_text)

    print("\n--- selected highway distribution ---")
    print(selected_highway_text)


if __name__ == "__main__":
    main()
