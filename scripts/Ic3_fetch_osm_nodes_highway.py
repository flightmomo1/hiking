import geopandas as gpd
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from shapely.geometry import Point
import json
from tqdm import tqdm
import time
import random

# === 1. 讀取 Ic2 匯出的主路線段 node_ids_str ===
df_way = pd.read_csv("Ic2_osm_way_tag_results.csv")  # Ic2 產出
all_node_ids = set()
way_node_pairs = []

for _, row in df_way.iterrows():
    way_id = row["way_id"]
    node_ids = row["node_ids_str"].split(";")
    for i, nid in enumerate(node_ids):
        nid = nid.strip()
        if not nid:
            continue
        all_node_ids.add(nid)
        way_node_pairs.append((way_id, nid, i))

print(f"✔ 共計 {len(all_node_ids)} 個 unique node_id，{len(way_node_pairs)} 組 way-node-index")

# === 2. 查詢 node 屬性與座標 ===
def fetch_node_info(node_id):
    url = f"https://api.openstreetmap.org/api/0.6/node/{node_id}"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        tree = ET.fromstring(r.content)
        node = tree.find("node")
        out = {
            "node_id": node_id,
            "lon": float(node.attrib.get("lon", 0)),
            "lat": float(node.attrib.get("lat", 0)),
            "ele": None,
            "name": None,
            "node_type": None,
            "tags_json": None,
        }
        tags = {}
        for tag in node.findall("tag"):
            k = tag.attrib.get("k")
            v = tag.attrib.get("v")
            tags[k] = v
            if k == "ele":
                out["ele"] = v
            elif k == "name":
                out["name"] = v
            elif k in ["natural", "amenity", "highway", "man_made"]:
                out["node_type"] = v
        out["tags_json"] = json.dumps(tags, ensure_ascii=False)
        return out
    except Exception as e:
        return {
            "node_id": node_id,
            "lon": None, "lat": None, "ele": None, "name": None,
            "node_type": None, "tags_json": None,
            "error": str(e)
        }

# === 3. 查詢所有 node_id ===
node_info_list = []
for nid in tqdm(list(all_node_ids), desc="下載節點屬性"):
    node_info_list.append(fetch_node_info(nid))
    time.sleep(random.uniform(1.1, 1.8))  # 防止 API 封鎖

df_nodes = pd.DataFrame(node_info_list)
df_nodes = df_nodes.dropna(subset=["lon", "lat"])

# === 4. 合併 way_id、index ===
df_pairs = pd.DataFrame(way_node_pairs, columns=["way_id", "node_id", "way_index"])
df_merge = pd.merge(df_pairs, df_nodes, how="left", on="node_id")

# === 5. 建立 geometry 欄位 ===
gdf_nodes = gpd.GeoDataFrame(
    df_merge,
    geometry=[Point(float(lon), float(lat)) for lon, lat in zip(df_merge.lon, df_merge.lat)],
    crs="EPSG:4326"
)

# === 6. 儲存 ===
gdf_nodes.to_file("Ic3_osm_nodes.geojson", driver="GeoJSON")
gdf_nodes.to_csv("Ic3_osm_nodes.csv", index=False)

print(f"✅ Ic3 完成，共 {len(gdf_nodes)} 筆，欄位：{gdf_nodes.columns.tolist()}")