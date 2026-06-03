from pathlib import Path
import argparse
import xml.etree.ElementTree as ET

import pandas as pd
import geopandas as gpd
import folium
from shapely.geometry import Point, LineString


"""
ib0c_anchor_from_landmarks.py

目的：
- 從 GPX + OSM landmarks 自動產生 route anchors
- 產生 START / VIA / END 三個 anchor
- 後續供 ib0b_route_mainline_extract.py 使用

Anchor 規則：
1. START：
   GPX 起點附近優先找 trailhead，其次 guidepost，最後 fallback 到 GPX 起點

2. VIA：
   GPX 最高點附近優先找 peak，其次 guidepost，最後 fallback 到 GPX 最高點

3. END：
   GPX 終點附近優先找 trailhead，其次 guidepost，最後 fallback 到 GPX 終點

注意：
- 使用者輸入 GPX 為 lat/lon
- shapely Point 內部仍維持 Point(lon, lat)
"""


# =========================================================
# 0. Project / Case / Activity / Ia1 設定
# =========================================================
PROJECT_ROOT = Path(r"C:\mountain_work\115_osm")
SCRIPT_VERSION = "v1.2_cli_updated"


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
        description="ib0c: 從 activity route + per-CASE_ID OSM landmarks 自動產生 start/via/end anchors"
    )

    parser.add_argument("--case-id", default="juansi_waterfall_fitcsv_20260503")
    parser.add_argument("--case-name", default=None)
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
        "--osm-raw-dir",
        default=None,
        help="per-CASE_ID OSM raw folder。未指定時使用 osm_raw_output/<case-id>。",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="輸出資料夾。未指定時使用 outputs/ib0c_anchor/<case-id>。",
    )
    parser.add_argument("--ia1-version", default="case_level")
    parser.add_argument("--ia1-dataset-id", default=None)
    parser.add_argument("--ia1-snapshot-tag", default="case_osm_raw")

    parser.add_argument("--start-trailhead-radius-m", type=float, default=200)
    parser.add_argument("--start-guidepost-radius-m", type=float, default=120)
    parser.add_argument("--end-trailhead-radius-m", type=float, default=200)
    parser.add_argument("--end-guidepost-radius-m", type=float, default=120)
    parser.add_argument("--via-peak-radius-m", type=float, default=300)
    parser.add_argument("--via-guidepost-radius-m", type=float, default=150)

    return parser.parse_args()


args = parse_args()

CASE_ID = args.case_id
CASE_NAME = args.case_name or args.case_id

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

if args.osm_raw_dir is None:
    IA1_DIR = PROJECT_ROOT / "osm_raw_output" / CASE_ID
else:
    IA1_DIR = resolve_path(args.osm_raw_dir)

if args.out_dir is None:
    OUT_DIR = PROJECT_ROOT / "outputs" / "ib0c_anchor" / CASE_ID
else:
    OUT_DIR = resolve_path(args.out_dir)

OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_GEOJSON_FP = OUT_DIR / f"{CASE_ID}_route_anchors.geojson"
OUT_CSV_FP = OUT_DIR / f"{CASE_ID}_route_anchors.csv"
OUT_HTML_FP = OUT_DIR / f"{CASE_ID}_route_anchors_map.html"
OUT_MANIFEST_FP = OUT_DIR / f"{CASE_ID}_anchor_manifest.csv"


# =========================================================
# 1. landmark 檔案名稱
# =========================================================
TRAILHEAD_NAME = "osm_trailhead_raw.geojson"
PEAK_NAME = "osm_peak_raw.geojson"
GUIDEPOST_NAME = "osm_guidepost_raw.geojson"


# =========================================================
# 2. anchor 搜尋半徑設定
# =========================================================
START_TRAILHEAD_RADIUS_M = args.start_trailhead_radius_m
START_GUIDEPOST_RADIUS_M = args.start_guidepost_radius_m

END_TRAILHEAD_RADIUS_M = args.end_trailhead_radius_m
END_GUIDEPOST_RADIUS_M = args.end_guidepost_radius_m

VIA_PEAK_RADIUS_M = args.via_peak_radius_m
VIA_GUIDEPOST_RADIUS_M = args.via_guidepost_radius_m


# =========================================================
# 3. 工具函式
# =========================================================
def find_file(filename: str) -> Path | None:
    """
    固定讀取目前 IA1_DATASET_ID 對應的 Ia1 輸出資料夾。
    不使用 rglob，也不 fallback 到其他資料夾，避免跨路線污染。
    """
    fp = IA1_DIR / filename

    if fp.exists():
        print(f"使用目前路線 landmark：{fp}")
        return fp

    print(f"找不到目前路線 landmark：{fp}")
    return None


def read_optional_geojson(filename: str) -> gpd.GeoDataFrame:
    fp = find_file(filename)

    if fp is None:
        print(f"找不到 landmark 檔案，略過：{filename}")
        return gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs="EPSG:4326")

    gdf = gpd.read_file(fp)

    if gdf.empty:
        print(f"landmark 空圖層：{fp}")
        return gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs="EPSG:4326")

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")

    gdf = gdf.to_crs("EPSG:4326")
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()

    print(f"讀取 landmark：{fp}，筆數：{len(gdf)}")
    return gdf


def parse_gpx_points(gpx_fp: Path) -> gpd.GeoDataFrame:
    if not gpx_fp.exists():
        raise FileNotFoundError(f"找不到 GPX：{gpx_fp}")

    tree = ET.parse(gpx_fp)
    root = tree.getroot()

    if root.tag.startswith("{"):
        uri = root.tag.split("}")[0].strip("{")
        ns = {"gpx": uri}
        trkpt_xpath = ".//gpx:trkpt"
        ele_tag = "gpx:ele"
        time_tag = "gpx:time"
    else:
        ns = {}
        trkpt_xpath = ".//trkpt"
        ele_tag = "ele"
        time_tag = "time"

    rows = []

    for i, trkpt in enumerate(root.findall(trkpt_xpath, ns)):
        lat = float(trkpt.attrib["lat"])
        lon = float(trkpt.attrib["lon"])

        ele_elem = trkpt.find(ele_tag, ns)
        time_elem = trkpt.find(time_tag, ns)

        ele = float(ele_elem.text) if ele_elem is not None and ele_elem.text else None
        t = time_elem.text if time_elem is not None else None

        rows.append({
            "gpx_idx": i,
            "lat": lat,
            "lon": lon,
            "ele_gpx_m": ele,
            "time_raw": t,
            "geometry": Point(lon, lat),
        })

    if len(rows) < 2:
        raise ValueError("GPX 點數不足")

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    return gdf

def semicircles_to_degrees(value):
    """
    Garmin FIT semicircles 轉十進位經緯度。
    degrees = semicircles * 180 / 2^31
    """
    if pd.isna(value):
        return pd.NA
    return float(value) * 180.0 / (2 ** 31)


def parse_fit_csv_points(csv_fp: Path) -> gpd.GeoDataFrame:
    if not csv_fp.exists():
        raise FileNotFoundError(f"找不到 FIT CSV：{csv_fp}")

    # low_memory=False 可避免混合欄位型別警告
    df = pd.read_csv(csv_fp, low_memory=False)

    # -----------------------------------------------------
    # 1. 優先支援 Garmin FIT CSV 原始欄位
    # -----------------------------------------------------
    fit_lat_col = "record.position_lat[semicircles]"
    fit_lon_col = "record.position_long[semicircles]"

    if fit_lat_col in df.columns and fit_lon_col in df.columns:
        out = pd.DataFrame()
        out["lat"] = pd.to_numeric(df[fit_lat_col], errors="coerce").apply(semicircles_to_degrees)
        out["lon"] = pd.to_numeric(df[fit_lon_col], errors="coerce").apply(semicircles_to_degrees)

        if "record.enhanced_altitude[m]" in df.columns:
            out["ele_gpx_m"] = pd.to_numeric(df["record.enhanced_altitude[m]"], errors="coerce")
        elif "record.altitude[m]" in df.columns:
            out["ele_gpx_m"] = pd.to_numeric(df["record.altitude[m]"], errors="coerce")
        else:
            out["ele_gpx_m"] = pd.NA

        if "record.timestamp[s]" in df.columns:
            out["time_raw"] = df["record.timestamp[s]"]
        else:
            out["time_raw"] = pd.NA

    else:
        # -------------------------------------------------
        # 2. fallback：支援已轉好的十進位 lat/lon CSV
        # -------------------------------------------------
        rename_map = {}

        for c in df.columns:
            lc = str(c).strip().lower()

            if lc in ["lat", "latitude", "position_lat", "raw_lat"]:
                rename_map[c] = "lat"
            elif lc in ["lon", "lng", "longitude", "position_long", "position_lon", "raw_lon"]:
                rename_map[c] = "lon"
            elif lc in ["ele", "elev", "elevation", "alt", "altitude", "enhanced_altitude", "raw_ele_m"]:
                rename_map[c] = "ele_gpx_m"
            elif lc in ["time", "timestamp", "datetime", "record_time"]:
                rename_map[c] = "time_raw"

        df = df.rename(columns=rename_map)

        required_cols = ["lat", "lon"]
        for c in required_cols:
            if c not in df.columns:
                raise ValueError(
                    f"FIT CSV 缺少必要欄位：{c}。目前欄位：{list(df.columns)}"
                )

        out = pd.DataFrame()
        out["lat"] = pd.to_numeric(df["lat"], errors="coerce")
        out["lon"] = pd.to_numeric(df["lon"], errors="coerce")
        out["ele_gpx_m"] = pd.to_numeric(df["ele_gpx_m"], errors="coerce") if "ele_gpx_m" in df.columns else pd.NA
        out["time_raw"] = df["time_raw"] if "time_raw" in df.columns else pd.NA

    # -----------------------------------------------------
    # 3. 清理有效 GPS 點
    # -----------------------------------------------------
    out = out.dropna(subset=["lat", "lon"]).copy()

    # 排除不合理經緯度
    out = out[
        (out["lat"].between(-90, 90)) &
        (out["lon"].between(-180, 180))
    ].copy()

    if len(out) < 2:
        raise ValueError(f"FIT CSV 有效 GPS 點數不足：{csv_fp}")

    out = out.reset_index(drop=True)
    out["gpx_idx"] = out.index

    out["geometry"] = out.apply(
        lambda r: Point(float(r["lon"]), float(r["lat"])),
        axis=1,
    )

    gdf = gpd.GeoDataFrame(out, geometry="geometry", crs="EPSG:4326")

    print("FIT CSV 有效 GPS 點數：", len(gdf))
    print("FIT CSV lat range:", float(gdf["lat"].min()), "→", float(gdf["lat"].max()))
    print("FIT CSV lon range:", float(gdf["lon"].min()), "→", float(gdf["lon"].max()))

    return gdf


def get_name(row):
    for c in ["name", "name_display", "ref", "description", "board:title"]:
        if c in row and pd.notna(row[c]):
            return str(row[c])

    information = row.get("information", "")
    osm_type = row.get("osm_type", "")
    osm_id = row.get("osm_id", "")

    if pd.notna(information) and str(information).strip():
        return f"{information} ({osm_type}/{osm_id})"

    if pd.notna(osm_id) and str(osm_id).strip():
        return f"unnamed_landmark ({osm_type}/{osm_id})"

    return "unnamed_landmark"


def nearest_landmark(pt_m, landmark_m, max_dist_m: float):
    if landmark_m.empty:
        return None

    dists = landmark_m.geometry.distance(pt_m)
    min_idx = dists.idxmin()
    min_dist = float(dists.loc[min_idx])

    if min_dist <= max_dist_m:
        row = landmark_m.loc[min_idx]
        return {
            "geometry": row.geometry,
            "anchor_name": get_name(row),
            "distance_to_gpx_m": min_dist,
        }

    return None


def make_anchor_row(anchor_role, anchor_source, anchor_name, distance_to_gpx_m, geom_m, ref_geom_m):
    return {
        "anchor_role": anchor_role,
        "anchor_source": anchor_source,
        "anchor_name": anchor_name,
        "distance_to_gpx_m": distance_to_gpx_m,
        "ref_lon": ref_geom_m.x,
        "ref_lat": ref_geom_m.y,
        "geometry": geom_m,
    }


def choose_start_end_anchor(role, ref_pt_m, trailhead_m, guidepost_m):
    if role == "start":
        trail_radius = START_TRAILHEAD_RADIUS_M
        guide_radius = START_GUIDEPOST_RADIUS_M
    else:
        trail_radius = END_TRAILHEAD_RADIUS_M
        guide_radius = END_GUIDEPOST_RADIUS_M

    hit = nearest_landmark(ref_pt_m, trailhead_m, trail_radius)
    if hit is not None:
        return make_anchor_row(
            role,
            "trailhead",
            hit["anchor_name"],
            hit["distance_to_gpx_m"],
            hit["geometry"],
            ref_pt_m,
        )

    hit = nearest_landmark(ref_pt_m, guidepost_m, guide_radius)
    if hit is not None:
        return make_anchor_row(
            role,
            "guidepost",
            hit["anchor_name"],
            hit["distance_to_gpx_m"],
            hit["geometry"],
            ref_pt_m,
        )

    return make_anchor_row(
        role,
        "fallback_gpx_point",
        "",
        0.0,
        ref_pt_m,
        ref_pt_m,
    )


def choose_via_anchor(ref_pt_m, peak_m, guidepost_m):
    hit = nearest_landmark(ref_pt_m, peak_m, VIA_PEAK_RADIUS_M)
    if hit is not None:
        return make_anchor_row(
            "via",
            "peak",
            hit["anchor_name"],
            hit["distance_to_gpx_m"],
            hit["geometry"],
            ref_pt_m,
        )

    hit = nearest_landmark(ref_pt_m, guidepost_m, VIA_GUIDEPOST_RADIUS_M)
    if hit is not None:
        return make_anchor_row(
            "via",
            "guidepost",
            hit["anchor_name"],
            hit["distance_to_gpx_m"],
            hit["geometry"],
            ref_pt_m,
        )

    return make_anchor_row(
        "via",
        "fallback_gpx_peak",
        "",
        0.0,
        ref_pt_m,
        ref_pt_m,
    )


# =========================================================
# 4. 讀活動軌跡
# =========================================================
if ACTIVITY_TYPE == "gpx":
    activity_points = parse_gpx_points(ACTIVITY_FP)
elif ACTIVITY_TYPE in {"fit_csv", "csv"}:
    activity_points = parse_fit_csv_points(ACTIVITY_FP)
else:
    raise ValueError(f"目前 ib0c 尚未支援 ACTIVITY_TYPE={ACTIVITY_TYPE}")

print("活動軌跡載入成功：", ACTIVITY_FP)
print("活動資料類型：", ACTIVITY_TYPE)
print("活動點數：", len(activity_points))

metric_crs = activity_points.estimate_utm_crs()
activity_m = activity_points.to_crs(metric_crs)

activity_start_m = activity_m.geometry.iloc[0]
activity_end_m = activity_m.geometry.iloc[-1]

if activity_m["ele_gpx_m"].notna().any():
    peak_idx = activity_m["ele_gpx_m"].idxmax()
    activity_peak_m = activity_m.loc[peak_idx].geometry
    activity_peak_source = f"{ACTIVITY_TYPE}_max_elevation"
else:
    peak_idx = len(activity_m) // 2
    activity_peak_m = activity_m.geometry.iloc[peak_idx]
    activity_peak_source = f"{ACTIVITY_TYPE}_midpoint_no_elevation"

print("activity peak source:", activity_peak_source)
print("activity peak idx:", peak_idx)

# =========================================================
# 5. 讀 OSM landmarks
# =========================================================
trailheads = read_optional_geojson(TRAILHEAD_NAME)
peaks = read_optional_geojson(PEAK_NAME)
guideposts = read_optional_geojson(GUIDEPOST_NAME)

trailheads_m = trailheads.to_crs(metric_crs) if not trailheads.empty else trailheads
peaks_m = peaks.to_crs(metric_crs) if not peaks.empty else peaks
guideposts_m = guideposts.to_crs(metric_crs) if not guideposts.empty else guideposts


# =========================================================
# 6. 選 anchors
# =========================================================
anchor_rows = []

anchor_rows.append(
    choose_start_end_anchor("start", activity_start_m, trailheads_m, guideposts_m)
)

anchor_rows.append(
    choose_via_anchor(activity_peak_m, peaks_m, guideposts_m)
)

anchor_rows.append(
    choose_start_end_anchor("end", activity_end_m, trailheads_m, guideposts_m)
)

anchors_m = gpd.GeoDataFrame(anchor_rows, geometry="geometry", crs=metric_crs)
anchors = anchors_m.to_crs("EPSG:4326")

# ref_lon/ref_lat 目前是 metric 座標，另轉成 WGS84 ref point
ref_points_m = gpd.GeoSeries(
    [activity_start_m, activity_peak_m, activity_end_m],
    crs=metric_crs,
)
ref_points_wgs = ref_points_m.to_crs("EPSG:4326")

anchors["ref_lon"] = [p.x for p in ref_points_wgs]
anchors["ref_lat"] = [p.y for p in ref_points_wgs]

anchors["anchor_lon"] = anchors.geometry.x
anchors["anchor_lat"] = anchors.geometry.y

# =========================================================
# 6a. metadata：與 ib0 / ib0a 對齊，方便專利 / 實驗追溯
# =========================================================
anchors["pipeline_stage"] = "ib0c_anchor_from_landmarks"
anchors["case_id"] = CASE_ID
anchors["case_name"] = CASE_NAME
anchors["activity_type"] = ACTIVITY_TYPE
anchors["activity_source"] = ACTIVITY_NAME

anchors["ia1_version"] = IA1_VERSION
anchors["ia1_dataset_id"] = IA1_DATASET_ID
anchors["ia1_snapshot_tag"] = IA1_SNAPSHOT_TAG

anchors["activity_peak_source"] = activity_peak_source
anchors["activity_peak_idx"] = int(peak_idx)

anchors["script_version"] = SCRIPT_VERSION
anchors["activity_input_fp"] = str(ACTIVITY_FP)
anchors["ia1_input_dir"] = str(IA1_DIR)

anchors["start_trailhead_radius_m"] = START_TRAILHEAD_RADIUS_M
anchors["start_guidepost_radius_m"] = START_GUIDEPOST_RADIUS_M
anchors["end_trailhead_radius_m"] = END_TRAILHEAD_RADIUS_M
anchors["end_guidepost_radius_m"] = END_GUIDEPOST_RADIUS_M
anchors["via_peak_radius_m"] = VIA_PEAK_RADIUS_M
anchors["via_guidepost_radius_m"] = VIA_GUIDEPOST_RADIUS_M


# =========================================================
# 7. 輸出
# =========================================================
anchors.to_file(OUT_GEOJSON_FP, driver="GeoJSON")
anchors.drop(columns="geometry").to_csv(OUT_CSV_FP, index=False, encoding="utf-8-sig")
manifest = {
    "pipeline_stage": "ib0c_anchor_from_landmarks",
    "case_id": CASE_ID,
    "case_name": CASE_NAME,
    "activity_type": ACTIVITY_TYPE,
    "activity_name": ACTIVITY_NAME,
    "activity_fp": str(ACTIVITY_FP),

    "ia1_version": IA1_VERSION,
    "ia1_dataset_id": IA1_DATASET_ID,
    "ia1_snapshot_tag": IA1_SNAPSHOT_TAG,
    "ia1_dir": str(IA1_DIR),

    "trailhead_fp": str(IA1_DIR / TRAILHEAD_NAME),
    "peak_fp": str(IA1_DIR / PEAK_NAME),
    "guidepost_fp": str(IA1_DIR / GUIDEPOST_NAME),

    "activity_point_n": len(activity_points),
    "activity_peak_source": activity_peak_source,
    "activity_peak_idx": int(peak_idx),

    "start_trailhead_radius_m": START_TRAILHEAD_RADIUS_M,
    "start_guidepost_radius_m": START_GUIDEPOST_RADIUS_M,
    "end_trailhead_radius_m": END_TRAILHEAD_RADIUS_M,
    "end_guidepost_radius_m": END_GUIDEPOST_RADIUS_M,
    "via_peak_radius_m": VIA_PEAK_RADIUS_M,
    "via_guidepost_radius_m": VIA_GUIDEPOST_RADIUS_M,

    "out_geojson": str(OUT_GEOJSON_FP),
    "out_csv": str(OUT_CSV_FP),
    "out_html": str(OUT_HTML_FP),
}

pd.DataFrame([manifest]).to_csv(
    OUT_MANIFEST_FP,
    index=False,
    encoding="utf-8-sig",
)

print("Anchor manifest：", OUT_MANIFEST_FP.resolve())

print("\n完成！")
print("Anchor GeoJSON：", OUT_GEOJSON_FP.resolve())
print("Anchor CSV：", OUT_CSV_FP.resolve())

print("\n=== anchors ===")
print(anchors[[
    "anchor_role",
    "anchor_source",
    "anchor_name",
    "distance_to_gpx_m",
    "anchor_lat",
    "anchor_lon",
]])


# =========================================================
# 8. QA 地圖
# =========================================================
activity_line = LineString(list(activity_points.geometry.apply(lambda p: (p.x, p.y))))
center = [activity_points.geometry.y.mean(), activity_points.geometry.x.mean()]

m = folium.Map(
    location=center,
    zoom_start=14,
    tiles="CartoDB positron",
    width="100%",
    height="800px",
)

folium.PolyLine(
    [(lat, lon) for lon, lat in activity_line.coords],
    color="black",
    weight=3,
    opacity=0.8,
    tooltip=f"activity route: {ACTIVITY_NAME}",
).add_to(m)

color_map = {
    "start": "green",
    "via": "blue",
    "end": "red",
}

icon_map = {
    "start": "play",
    "via": "flag",
    "end": "stop",
}

# ---------------------------------------------------------
# 若 start / end / via 座標重疊，只在 QA 地圖顯示時做微小偏移
# 注意：不改 anchors.geometry，避免影響 ib0b 的真實 anchor 座標
# ---------------------------------------------------------
DISPLAY_OFFSET = {
    "start": (0.000035, -0.000035),  # lat offset, lon offset
    "via":   (0.000000,  0.000000),
    "end":   (-0.000035, 0.000035),
}

for _, row in anchors.iterrows():
    popup_text = (
        f"role: {row['anchor_role']}\n"
        f"source: {row['anchor_source']}\n"
        f"name: {row['anchor_name']}\n"
        f"distance_to_gpx_m: {row['distance_to_gpx_m']:.2f}\n"
        f"anchor_latlon: {row['anchor_lat']:.6f}, {row['anchor_lon']:.6f}\n"
        f"ref_latlon: {row['ref_lat']:.6f}, {row['ref_lon']:.6f}"
    )

    role = row["anchor_role"]
    lat_offset, lon_offset = DISPLAY_OFFSET.get(role, (0.0, 0.0))

    display_lat = row.geometry.y + lat_offset
    display_lon = row.geometry.x + lon_offset

    folium.Marker(
        location=[display_lat, display_lon],
        tooltip=f"{row['anchor_role']} - {row['anchor_source']}",
        popup=folium.Popup(f"<pre>{popup_text}</pre>", max_width=350),
        icon=folium.Icon(
            color=color_map.get(row["anchor_role"], "gray"),
            icon=icon_map.get(row["anchor_role"], "info-sign"),
        )
    ).add_to(m)

    # 顯示偏移線：讓使用者知道 marker 是從真實 anchor 位置偏移出來的
    if lat_offset != 0.0 or lon_offset != 0.0:
        folium.PolyLine(
            locations=[
                [row.geometry.y, row.geometry.x],
                [display_lat, display_lon],
            ],
            color=color_map.get(role, "gray"),
            weight=1,
            opacity=0.7,
            dash_array="3, 3",
            tooltip=f"{role} display offset only",
        ).add_to(m)

folium.LayerControl(collapsed=False).add_to(m)
m.save(OUT_HTML_FP)

print("Anchor QA 地圖：", OUT_HTML_FP.resolve())
print("\n=== ib0c anchor summary ===")
print("CASE_ID:", CASE_ID)
print("CASE_NAME:", CASE_NAME)
print("ACTIVITY_TYPE:", ACTIVITY_TYPE)
print("ACTIVITY_NAME:", ACTIVITY_NAME)
print("ACTIVITY_FP:", ACTIVITY_FP)
print("IA1_VERSION:", IA1_VERSION)
print("IA1_DATASET_ID:", IA1_DATASET_ID)
print("IA1_SNAPSHOT_TAG:", IA1_SNAPSHOT_TAG)
print("IA1_DIR:", IA1_DIR)
print("Anchor output dir:", OUT_DIR)
