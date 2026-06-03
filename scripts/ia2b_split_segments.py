from pathlib import Path
import math
import geopandas as gpd
from shapely.geometry import LineString, MultiLineString


"""
ia2b_split_segments.py

定位：
- ia 系列第二階段的中繼腳本
- 將原始 RoadL 尺度的線資料切成固定長度 segment
- 只處理 geometry split，不重新計算 terrain / hydrology 特徵

主要功能：
1. 讀取 ia2_enrich_segments_contour.py 輸出的 GeoJSON
2. 將 LineString / MultiLineString 切成固定長度的小段（預設 20m）
3. 保留 parent_id 與原始屬性，供後續 ia2c 重新 enrich 使用

注意：
- 本腳本不重新計算 contour_cross_n / slope_est_mean / near_lake_m 等欄位
- 本腳本輸出的 enrich 欄位仍繼承自 parent road，不能直接當最終分析輸入
- 真正用於模型前的 segment-level 特徵，應由 ia2c 重新計算
"""


# =========================================================
# 0. 基本設定
# =========================================================
INPUT_FP = Path("contour_enriched_output/97233NW_road_contour_enriched.geojson")

OUT_DIR = Path("segment_output")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_FP = OUT_DIR / "97233NW_segments_20m.geojson"

SEGMENT_LENGTH_M = 20.0


# =========================================================
# 1. 工具函式
# =========================================================
def split_linestring_by_length(line: LineString, segment_length: float) -> list[LineString]:
    """
    將單一 LineString 依固定長度切段。
    若原線長度小於 segment_length，則原樣保留。
    """
    if line.is_empty:
        return []

    total_len = line.length
    if total_len == 0:
        return []

    if total_len <= segment_length:
        return [line]

    segments = []
    start_d = 0.0

    while start_d < total_len:
        end_d = min(start_d + segment_length, total_len)

        p0 = line.interpolate(start_d)
        p1 = line.interpolate(end_d)

        seg = LineString([p0, p1])

        if not seg.is_empty and seg.length > 1.0:
            segments.append(seg)

        if math.isclose(end_d, total_len):
            break

        start_d = end_d

    return segments


def explode_to_lines(geom):
    """
    將 geometry 拆成單一 LineString 清單。
    支援 LineString / MultiLineString。
    """
    if geom is None or geom.is_empty:
        return []

    if geom.geom_type == "LineString":
        return [geom]

    if geom.geom_type == "MultiLineString":
        return [g for g in geom.geoms if g is not None and not g.is_empty]

    return []


# =========================================================
# 2. 讀檔
# =========================================================

if not INPUT_FP.exists():
    raise FileNotFoundError(f"找不到輸入檔：{INPUT_FP.resolve()}，請先執行 ia2")

gdf = gpd.read_file(INPUT_FP)

if gdf.empty:
    raise ValueError(f"輸入檔為空：{INPUT_FP}")





if gdf.crs is None:
    raise ValueError("輸入資料缺少 CRS，無法進行嚴謹的長度切段。")


# =========================================================
# 3. 轉投影座標系（公尺）以進行嚴謹切段
# =========================================================
metric_crs = gdf.estimate_utm_crs()
gdf_metric = gdf.to_crs(metric_crs)


# =========================================================
# 4. 切段
# =========================================================
segment_rows = []
segment_global_id = 0

for parent_idx, row in gdf_metric.iterrows():
    geom = row.geometry
    lines = explode_to_lines(geom)

    if not lines:
        continue

    parent_seg_seq = 0

    for line_idx, line in enumerate(lines):
        split_segments = split_linestring_by_length(line, SEGMENT_LENGTH_M)

        for seg in split_segments:
            new_row = row.copy()

            # 幾何與追蹤資訊
            new_row.geometry = seg
            new_row["parent_id"] = parent_idx
            new_row["parent_part_id"] = line_idx
            new_row["segment_id"] = segment_global_id
            new_row["segment_seq"] = parent_seg_seq

            # segment 幾何層級欄位
            new_row["seg_len_m"] = seg.length
            new_row["analysis_unit"] = "segment_20m_geometry_only"
            new_row["feature_status"] = "inherited_from_parent_not_recomputed"

            segment_rows.append(new_row)

            segment_global_id += 1
            parent_seg_seq += 1


# =========================================================
# 5. 建立輸出 GeoDataFrame
# =========================================================
if not segment_rows:
    raise ValueError("切段後沒有產生任何 segment，請檢查輸入幾何。")

gdf_seg_metric = gpd.GeoDataFrame(segment_rows, geometry="geometry", crs=metric_crs)

# 回到 WGS84 供 folium / GeoJSON 顯示
gdf_seg = gdf_seg_metric.to_crs("EPSG:4326")



# =========================================================
# 6. 輸出
# =========================================================

gdf_seg["source_parent_file"] = str(INPUT_FP)
gdf_seg["pipeline_stage"] = "ia2b_split_nlsc_segments"
gdf_seg["segment_length_target_m"] = SEGMENT_LENGTH_M

if "tile_id" in gdf.columns:
    gdf_seg["tile_id"] = gdf["tile_id"].iloc[0]

gdf_seg.to_file(OUT_FP, driver="GeoJSON")

print("完成！")
print("輸入：", INPUT_FP.resolve())
print("輸出：", OUT_FP.resolve())
print("原始筆數：", len(gdf))
print("切段後筆數：", len(gdf_seg))
print("分析座標系：", metric_crs)
print("顯示座標系： EPSG:4326")
print("segment 長度設定（m）：", SEGMENT_LENGTH_M)
print("analysis_unit：segment_20m_geometry_only")
print("feature_status：inherited_from_parent_not_recomputed")