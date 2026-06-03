import geopandas as gpd
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from tqdm import tqdm
import time
import random

# === 1. 讀取主路線 GeoJSON ===
gdf = gpd.read_file("Ic_combined_main_route_segments.geojson")

# === 2. 正規化 way_id，提取純數字 ===
def extract_way_id(val):
    try:
        if isinstance(val, (tuple, list)) and len(val) == 2:
            return str(val[1])
        elif isinstance(val, str) and val.startswith("('way',"):
            return val.split(",")[1].strip().replace(")", "").strip()
        elif isinstance(val, (int, float)):
            return str(int(val))
        elif isinstance(val, str):
            return val.strip()
    except:
        return None

way_ids_raw = gdf["way_id"].dropna().unique().tolist()
way_ids = list({extract_way_id(wid) for wid in way_ids_raw if extract_way_id(wid)})

# === 3. 擷取 XML 並解析 tag + node_ids ===
def fetch_osm_way_tags_via_api(way_id):
    url = f"https://api.openstreetmap.org/api/0.6/way/{way_id}"
    result = {
        "way_id": way_id,
        "version": None,
        "changeset": None,
        "timestamp": None,
        "user": None,
        "uid": None,
        "highway": None,
        "name": None,
        "surface": None,
        "trail_visibility": None,
        "bridge": None,
        "node_ids": [],   # list 格式
        "error": None
    }

    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        tree = ET.fromstring(response.content)

        way_elem = tree.find("way")
        if way_elem is not None:
            result["version"] = way_elem.attrib.get("version")
            result["changeset"] = way_elem.attrib.get("changeset")
            result["timestamp"] = way_elem.attrib.get("timestamp")
            result["user"] = way_elem.attrib.get("user")
            result["uid"] = way_elem.attrib.get("uid")

            for tag in way_elem.findall("tag"):
                k = tag.attrib.get("k")
                v = tag.attrib.get("v")
                if k == "bridge:structure":
                    result["bridge"] = v
                elif k in result:
                    result[k] = v

            result["node_ids"] = [
                nd.attrib.get("ref") for nd in way_elem.findall("nd") if nd.attrib.get("ref")
            ]

    except Exception as e:
        result["error"] = str(e)

    return result

# === 4. 擷取資料 ===
results = []
for wid in tqdm(way_ids, desc="擷取中..."):
    results.append(fetch_osm_way_tags_via_api(wid))
    time.sleep(random.uniform(1.5, 3.0))  # 防封鎖

# === 5. 建立 DataFrame 與處理 node_ids 字串化 ===
df = pd.DataFrame(results)
df["node_ids_str"] = df["node_ids"].apply(lambda x: ";".join(x) if isinstance(x, list) else "")

# === 6. 欄位順序與儲存 ===
columns = [
    "way_id", "version", "changeset", "timestamp", "user", "uid",
    "highway", "name", "surface", "trail_visibility", "bridge", "node_ids_str", "error"
]
df.to_csv("Ic2_osm_way_tag_results.csv", index=False, columns=columns)
print(f"\n✅ 擷取完成，共匯出 {len(df)} 筆資料")