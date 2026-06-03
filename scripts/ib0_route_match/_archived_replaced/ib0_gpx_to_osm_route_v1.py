from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import geopandas as gpd
import folium
from shapely.geometry import LineString


"""
ib0_gpx_to_osm_route_v1.py

定位：
- GPX-guided OSM candidate route matching
- 讀取指定 GPX 路線與 Ia1 產生之 OSM highway raw layer
- 從固定版 OSM highway 圖層中，篩選出最可能對應 GPX 路線的候選路段集合
- 輸出 candidate / matched OSM route，作為後續 ib0a 修剪、ib0c 錨點建立與 ib0b 主幹路線抽取的基礎

主要功能：
1. 讀取 GPX 並建立 route geometry
2. 讀取 Ia1 產生之 OSM highway raw layer
3. 以距離、重疊比例、highway 語意進行初步 matching
4. 輸出 candidate / matched GeoJSON、summary CSV 與 QA 地圖

注意：
- 本腳本不重新下載 OSM，底層 OSM 圖資由 ia1_osm_fetch_raw.py 管理
- 本版為 rule-based candidate matching，不是完整 graph-based map matching
- 後續由 ib0a / ib0c / ib0b 進行修剪、錨點約束與主幹路線抽取
"""


# =========================================================
# 0. 路徑設定
# =========================================================

PROJECT_ROOT = Path(r"C:\mountain_work\115_osm")

# =========================================================
# 0-1. Activity / Route 設定：這次要分析的活動軌跡
# =========================================================

ACTIVITY_ROOT = PROJECT_ROOT / "activity_input"

# A. GPX：七星山小油坑進出 Joyhike
# ROUTE_ID = "qixing_xiaoyoukeng_roundtrip_joyhike"
# ACTIVITY_TYPE = "gpx"
# ROUTE_GROUP = "qixing_xiaoyoukeng_roundtrip"
# ACTIVITY_NAME = "七星山 (小油坑進出)_Joyhike.gpx"
# ACTIVITY_DIR = ACTIVITY_ROOT / "gpx" / ROUTE_GROUP

# B. FIT CSV：絹絲瀑布 Garmin/FIT 轉 CSV
ROUTE_ID = "juansi_waterfall_fitcsv_20260503"
ACTIVITY_TYPE = "fit_csv"
ROUTE_GROUP = "juansi_waterfall"
ACTIVITY_NAME = "3.csv"
ACTIVITY_DIR = ACTIVITY_ROOT / "csv" / ROUTE_GROUP

ACTIVITY_FP = ACTIVITY_DIR / ACTIVITY_NAME

# =========================================================
# 0-2. Ia1 dataset 設定：底層 OSM 場域圖資
# =========================================================
IA1_VERSION = "v1.2"
IA1_DATASET_ID = "qixing_lengshuikeng_xiaoyoukeng_v1_2_success_20260511"
IA1_SNAPSHOT_TAG = "success_20260511"

IA1_DIR = PROJECT_ROOT / "osm_raw_output" / IA1_DATASET_ID
OSM_HIGHWAY_FP = IA1_DIR / "osm_highway_raw.geojson"

# =========================================================
# 0-3. Ib0 輸出設定
# =========================================================
OUT_DIR = PROJECT_ROOT / "outputs" / "ib0_route_match" / ROUTE_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)

CANDIDATE_GEOJSON_FP = OUT_DIR / f"{ROUTE_ID}_activity_osm_candidates.geojson"
MATCHED_GEOJSON_FP = OUT_DIR / f"{ROUTE_ID}_activity_osm_matched.geojson"
QA_HTML_FP = OUT_DIR / f"{ROUTE_ID}_activity_osm_matched_map.html"
SUMMARY_CSV_FP = OUT_DIR / f"{ROUTE_ID}_activity_osm_match_summary.csv"


# =========================================================
# 1. 參數設定
# =========================================================
GPX_BUFFER_FETCH_M = 60
GPX_BUFFER_MATCH_M = 30
MAX_DISTANCE_M = 20
MIN_OVERLAP_RATIO = 0.30
MATCH_SCORE_THRESHOLD = 0.55

# 放寬候選集：先保留較多可能路型，再交給 GPX 距離與重疊判斷
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
# 2. 工具函式
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

    return LineString(pts)


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

    pts = list(zip(df["lon"], df["lat"]))

    # 去除連續重複點，避免 LineString 含大量相同座標
    dedup_pts = []
    for pt in pts:
        if not dedup_pts or pt != dedup_pts[-1]:
            dedup_pts.append(pt)

    if len(dedup_pts) < 2:
        raise ValueError("CSV 去除重複點後有效點不足，無法建立路線")

    return LineString(dedup_pts)

def load_activity_track(activity_fp: Path, activity_type: str) -> LineString:
    """
    依活動資料格式載入軌跡，統一輸出 WGS84 LineString。
    支援：
    - gpx
    - fit_csv
    """
    activity_type = activity_type.lower().strip()

    if activity_type == "gpx":
        return parse_gpx_track(activity_fp)

    if activity_type == "fit_csv":
        return parse_fit_csv_track(activity_fp)

    raise ValueError(f"不支援的 ACTIVITY_TYPE：{activity_type}")



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


def classify_selected(row):
    cond1 = row["distance_to_gpx_m"] <= MAX_DISTANCE_M
    cond2 = row["overlap_ratio"] >= MIN_OVERLAP_RATIO
    cond3 = row["match_score"] >= MATCH_SCORE_THRESHOLD
    return int((cond1 and cond2) or cond3)


# =========================================================
# 3. 讀取活動軌跡 GPX / FIT CSV
# =========================================================
activity_line = load_activity_track(ACTIVITY_FP, ACTIVITY_TYPE)

activity_gdf = gpd.GeoDataFrame(
    [{"route_name": ACTIVITY_NAME, "geometry": activity_line}],
    geometry="geometry",
    crs="EPSG:4326",
)

print("活動軌跡載入成功：", ACTIVITY_FP)
print("活動資料類型：", ACTIVITY_TYPE)
print("軌跡點數（近似）：", len(list(activity_line.coords)))

center_lat, center_lon = get_center_latlon(activity_line)

metric_crs = activity_gdf.estimate_utm_crs()
activity_gdf_m = activity_gdf.to_crs(metric_crs)
activity_line_m = activity_gdf_m.geometry.iloc[0]

gpx_buffer_fetch = activity_line_m.buffer(GPX_BUFFER_FETCH_M)
gpx_buffer_match = activity_line_m.buffer(GPX_BUFFER_MATCH_M)

# =========================================================
# 4. 讀取 Ia1 產生的 OSM highway raw layer
# =========================================================
if not OSM_HIGHWAY_FP.exists():
    raise FileNotFoundError(
        f"找不到 Ia1 highway raw layer：{OSM_HIGHWAY_FP.resolve()}，請先執行 ia1_osm_fetch_raw.py"
    )

print("讀取 Ia1 OSM highway raw layer:", OSM_HIGHWAY_FP.resolve())
gdf_osm = gpd.read_file(OSM_HIGHWAY_FP)

if gdf_osm.empty:
    raise ValueError("Ia1 OSM highway raw layer 為空")


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
gdf_osm_m = gdf_osm_m[gdf_osm_m.intersects(gpx_buffer_fetch)].copy()

if gdf_osm_m.empty:
    raise ValueError("GPX 附近無候選 OSM 路段")


# =========================================================
# 5. 計算 matching 特徵
# =========================================================
print("計算 matching 特徵中...")

gdf_osm_m["segment_len_m"] = gdf_osm_m.geometry.length
gdf_osm_m["distance_to_gpx_m"] = gdf_osm_m.geometry.distance(activity_line_m)

intersections = gdf_osm_m.geometry.intersection(gpx_buffer_match)
gdf_osm_m["overlap_len_m"] = intersections.length
gdf_osm_m["overlap_ratio"] = (
    gdf_osm_m["overlap_len_m"] / gdf_osm_m["segment_len_m"]
).replace([np.inf, -np.inf], np.nan).fillna(0)

gdf_osm_m["semantic_score"] = gdf_osm_m.apply(get_semantic_score, axis=1)

# 距離分數：越近越高
gdf_osm_m["distance_score"] = 1 - np.clip(
    gdf_osm_m["distance_to_gpx_m"] / GPX_BUFFER_MATCH_M, 0, 1
)

# 綜合分數
gdf_osm_m["match_score"] = (
    0.45 * gdf_osm_m["distance_score"] +
    0.35 * gdf_osm_m["overlap_ratio"] +
    0.20 * gdf_osm_m["semantic_score"]
)

gdf_osm_m["selected"] = gdf_osm_m.apply(classify_selected, axis=1)

# =========================================================
# 5a. metadata：保留本次匹配參數，方便專利/實驗追溯
# =========================================================
gdf_osm_m["pipeline_stage"] = "ib0_activity_to_osm_route"
gdf_osm_m["route_id"] = ROUTE_ID
gdf_osm_m["ia1_version"] = IA1_VERSION
gdf_osm_m["ia1_dataset_id"] = IA1_DATASET_ID
gdf_osm_m["ia1_snapshot_tag"] = IA1_SNAPSHOT_TAG
gdf_osm_m["activity_type"] = ACTIVITY_TYPE
gdf_osm_m["activity_source"] = ACTIVITY_NAME

# 為了相容舊版 ib0a，暫時保留 gpx_source 欄位
gdf_osm_m["gpx_source"] = ACTIVITY_NAME

gdf_osm_m["osm_source"] = str(OSM_HIGHWAY_FP)

gdf_osm_m["gpx_buffer_fetch_m"] = GPX_BUFFER_FETCH_M
gdf_osm_m["gpx_buffer_match_m"] = GPX_BUFFER_MATCH_M
gdf_osm_m["max_distance_m"] = MAX_DISTANCE_M
gdf_osm_m["min_overlap_ratio"] = MIN_OVERLAP_RATIO
gdf_osm_m["match_score_threshold"] = MATCH_SCORE_THRESHOLD

# 補欄位
if isinstance(gdf_osm_m.index, pd.MultiIndex):
    gdf_osm_m["osm_element_type"] = gdf_osm_m.index.get_level_values(0).astype(str)
    gdf_osm_m["osm_id"] = gdf_osm_m.index.get_level_values(1)
    gdf_osm_m["osm_way_id"] = (
        gdf_osm_m["osm_element_type"] + ":" + gdf_osm_m["osm_id"].astype(str)
    )
else:
    gdf_osm_m["osm_element_type"] = "unknown"
    gdf_osm_m["osm_id"] = gdf_osm_m.index
    gdf_osm_m["osm_way_id"] = gdf_osm_m["osm_id"].astype(str)

if "name" not in gdf_osm_m.columns:
    gdf_osm_m["name"] = None

gdf_osm_m["name"] = gdf_osm_m["name"].fillna("")


# =========================================================
# 6. 輸出 GeoJSON
# =========================================================
candidate_cols = [
    "pipeline_stage",
    "route_id",
    "ia1_version",
    "ia1_dataset_id",
    "ia1_snapshot_tag",
    "activity_type",
    "activity_source",
    "gpx_source",
    "osm_source",

    "gpx_buffer_fetch_m",
    "gpx_buffer_match_m",
    "max_distance_m",
    "min_overlap_ratio",
    "match_score_threshold",

    "osm_element_type",
    "osm_id",
    "osm_way_id",
    "name",
    "highway",
    "highway_norm",
    "route_role",
    "segment_len_m",
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

if gdf_matched.empty:
    print("警告：本次沒有任何 OSM 路段通過 selected 條件")
    print("建議檢查 matching 參數：")
    print(f"- MAX_DISTANCE_M = {MAX_DISTANCE_M}")
    print(f"- MIN_OVERLAP_RATIO = {MIN_OVERLAP_RATIO}")
    print(f"- MATCH_SCORE_THRESHOLD = {MATCH_SCORE_THRESHOLD}")

gdf_candidates.to_file(CANDIDATE_GEOJSON_FP, driver="GeoJSON")
gdf_matched.to_file(MATCHED_GEOJSON_FP, driver="GeoJSON")

print("候選路段輸出：", CANDIDATE_GEOJSON_FP.resolve())
print("匹配路段輸出：", MATCHED_GEOJSON_FP.resolve())


# =========================================================
# 7. 輸出 summary csv
# =========================================================
summary_rows = []

for (role, hw), sub in gdf_candidates.groupby(["route_role", "highway_norm"]):

    summary_rows.append({
        "pipeline_stage": "ib0_activity_to_osm_route",
        "route_id": ROUTE_ID,
        "ia1_version": IA1_VERSION,
        "ia1_dataset_id": IA1_DATASET_ID,
        "ia1_snapshot_tag": IA1_SNAPSHOT_TAG,
        "activity_type": ACTIVITY_TYPE,
        "activity_source": ACTIVITY_NAME,

        # 為了相容舊版欄位
        "gpx_source": ACTIVITY_NAME,

        "osm_source": str(OSM_HIGHWAY_FP),
        "gpx_buffer_fetch_m": GPX_BUFFER_FETCH_M,
        "gpx_buffer_match_m": GPX_BUFFER_MATCH_M,
        "max_distance_m": MAX_DISTANCE_M,
        "min_overlap_ratio": MIN_OVERLAP_RATIO,
        "match_score_threshold": MATCH_SCORE_THRESHOLD,

        "route_role": role,
        "highway_norm": hw,
        "candidate_n": len(sub),
        "selected_n": int(sub["selected"].sum()),
        "mean_distance_to_gpx_m": sub["distance_to_gpx_m"].mean(),
        "mean_overlap_ratio": sub["overlap_ratio"].mean(),
        "mean_match_score": sub["match_score"].mean(),
    })

summary_df = pd.DataFrame(summary_rows).sort_values(
    by=["selected_n", "candidate_n"],
    ascending=[False, False]
)
summary_df.to_csv(SUMMARY_CSV_FP, index=False, encoding="utf-8-sig")

print("摘要輸出：", SUMMARY_CSV_FP.resolve())


# =========================================================
# 8. 建立 QA 地圖
# =========================================================
print("建立 QA 地圖中...")

m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=14,
    tiles="CartoDB positron",
    width="100%",
    height="800px",
)

# GPX 圖層
fg_gpx = folium.FeatureGroup(name="Activity route", show=True)
gpx_coords = [(lat, lon) for lon, lat in activity_line.coords]
folium.PolyLine(
    gpx_coords,
    color="blue",
    weight=4,
    opacity=0.9,
    tooltip="Activity route"
).add_to(fg_gpx)
fg_gpx.add_to(m)

# OSM 候選圖層
fg_osm = folium.FeatureGroup(name="OSM candidates / matched", show=True)

for _, row in gdf_candidates.iterrows():
    geom = row.geometry

    popup_text = (
        f"osm_way_id: {row.get('osm_way_id', '')}\n"
        f"name: {row.get('name', '')}\n"
        f"highway: {row.get('highway_norm', '')}\n"
        f"route_role: {row.get('route_role', '')}\n"
        f"distance_to_gpx_m: {row.get('distance_to_gpx_m', np.nan):.3f}\n"
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
m.save(QA_HTML_FP)

print("QA 地圖輸出：", QA_HTML_FP.resolve())


# =========================================================
# 9. 終端摘要
# =========================================================
print("\n=== match summary ===")
print("Route ID:", ROUTE_ID)
print("Ia1 version:", IA1_VERSION)
print("Ia1 dataset:", IA1_DATASET_ID)
print("Ia1 snapshot:", IA1_SNAPSHOT_TAG)
print("OSM source:", OSM_HIGHWAY_FP)
print("Activity type:", ACTIVITY_TYPE)
print("Activity source:", ACTIVITY_FP)

print("候選路段數：", len(gdf_candidates))
print("入選路段數：", len(gdf_matched))

print("\n--- selected route_role distribution ---")
if not gdf_matched.empty:
    print(gdf_matched["route_role"].value_counts(dropna=False))
else:
    print("無入選路段")

print("\n--- selected highway distribution ---")
if not gdf_matched.empty:
    print(gdf_matched["highway_norm"].value_counts(dropna=False))
else:
    print("無入選路段")