# =========================================================
# ib1c_apply_osm_semantic_risk_mapping.py
#
# 目的：
# - 讀取 ib1c OSM semantic enriched route profile
# - 讀取 configs/risk_semantics/osm_semantic_risk_mapping_v1.csv
# - 將 OSM 原始語意與 flags 轉換成 risk_domain score
# - 將 conditional 語意例如 bridge 先保留為條件因子，不直接加風險
# - 輸出可供 ib2 使用的 OSM semantic risk profile
# =========================================================

from pathlib import Path
import argparse
import pandas as pd
import geopandas as gpd


# =========================================================
# 0. Case 設定
# =========================================================
PROJECT_ROOT = Path("C:/mountain_work/115_osm")


def resolve_path(value, project_root=PROJECT_ROOT):
    if value is None:
        return None
    p = Path(value)
    if p.is_absolute():
        return p
    return project_root / p


def parse_args():
    parser = argparse.ArgumentParser(
        description="ib1c apply: convert OSM semantic enriched profile to OSM semantic risk profile"
    )
    parser.add_argument("--case-id", default="juansi_waterfall_fitcsv_20260503")
    parser.add_argument("--case-name", default=None)
    parser.add_argument(
        "--semantic-csv",
        default=None,
        help="ib1c semantic enriched CSV. Default: outputs/ib1c_route_profile_semantics/<case-id>/<case-id>_route_profile_semantic_enriched.csv",
    )
    parser.add_argument(
        "--semantic-geojson",
        default=None,
        help="ib1c semantic enriched GeoJSON. Default: outputs/ib1c_route_profile_semantics/<case-id>/<case-id>_route_profile_semantic_enriched.geojson",
    )
    parser.add_argument(
        "--mapping-csv",
        default=None,
        help="OSM semantic risk mapping CSV. Default: configs/risk_semantics/osm_semantic_risk_mapping_v1.csv",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Output folder. Default: outputs/ib1c_osm_semantic_risk/<case-id>",
    )
    return parser.parse_args()


args = parse_args()

CASE_ID = args.case_id
CASE_NAME = args.case_name or args.case_id

if args.semantic_csv is None:
    SEMANTIC_CSV = (
        PROJECT_ROOT
        / "outputs"
        / "ib1c_route_profile_semantics"
        / CASE_ID
        / f"{CASE_ID}_route_profile_semantic_enriched.csv"
    )
else:
    SEMANTIC_CSV = resolve_path(args.semantic_csv)

if args.semantic_geojson is None:
    SEMANTIC_GEOJSON = (
        PROJECT_ROOT
        / "outputs"
        / "ib1c_route_profile_semantics"
        / CASE_ID
        / f"{CASE_ID}_route_profile_semantic_enriched.geojson"
    )
else:
    SEMANTIC_GEOJSON = resolve_path(args.semantic_geojson)

if args.mapping_csv is None:
    MAPPING_CSV = (
        PROJECT_ROOT
        / "configs"
        / "risk_semantics"
        / "osm_semantic_risk_mapping_v1.csv"
    )
else:
    MAPPING_CSV = resolve_path(args.mapping_csv)

if args.out_dir is None:
    OUT_DIR = PROJECT_ROOT / "outputs" / "ib1c_osm_semantic_risk" / CASE_ID
else:
    OUT_DIR = resolve_path(args.out_dir)

OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_CSV = OUT_DIR / f"{CASE_ID}_osm_semantic_risk_profile.csv"
OUT_GEOJSON = OUT_DIR / f"{CASE_ID}_osm_semantic_risk_profile.geojson"
OUT_SUMMARY_CSV = OUT_DIR / f"{CASE_ID}_osm_semantic_risk_summary.csv"


# =========================================================
# 1. 原始 OSM 欄位對應 mapping source_field
# =========================================================
FIELD_TO_SOURCE_FIELD = {
    "osm_trail_visibility": "trail_visibility",
    "osm_surface": "surface",
    "osm_highway": "highway",
    "osm_bridge": "bridge",
    "osm_ford": "ford",
    "osm_tunnel": "tunnel",
    "osm_handrail": "handrail",
    "osm_safety_rope": "safety_rope",
    "osm_sac_scale": "sac_scale",
    "osm_lit": "lit",
    "osm_lit_status": "lit",
}

FLAG_FIELDS = {
    "technical_flags": "technical",
    "safety_flags": "safety",
    "hazard_flags": "hazard",
    "hydrology_flags": "hydrology",
    "landmark_flags": "landmark",
    "facility_flags": "facility",
    "rest_flags": "rest",
    "support_flags": "support",
}

FLAG_VALUE_TO_SOURCE_FIELD = {
    "handrail": "handrail",
    "safety_rope": "safety_rope",
    "rungs": "rungs",
    "ladder": "ladder",
    "via_ferrata": "via_ferrata",
    "assisted_trail": "assisted_trail",

    "cliff": "cliff",
    "scree": "scree",
    "bare_rock": "bare_rock",
    "landslide": "landslide",

    "waterway": "waterway",
    "wetland": "wetland",
    "water_area": "water_area",

    "guidepost": "guidepost",
    "trailhead": "trailhead",
    "peak": "peak",

    "shelter": "shelter",
    "alpine_hut": "alpine_hut",
    "wilderness_hut": "wilderness_hut",
    "bench": "bench",
    "picnic_table": "picnic_table",
    "picnic_site": "picnic_site",
    "drinking_water": "drinking_water",
    "toilets": "toilets",
    "visitor_centre": "visitor_centre",
    "information_office": "information_office",

    "street_lamp": "street_lamp",
}


# =========================================================
# 2. risk domain 欄位設定
# =========================================================
RISK_DOMAIN_SCORE_COLS = {
    "navigation_risk": "navigation_risk_score",
    "slip_risk": "surface_slip_risk_score",
    "route_difficulty": "route_type_risk_score",
    "effort_risk": "route_effort_risk_score",
    "exposure_risk": "exposure_risk_score",
    "hydrology_risk": "hydrology_risk_score",
    "technical_risk_hint": "technical_risk_score",
    "terrain_risk": "terrain_risk_score",
    "support_availability": "support_score",
    "rest_availability": "rest_support_score",
    "navigation_support": "navigation_support_score",
    "landmark_context": "landmark_context_score",
    "night_navigation_risk": "night_navigation_risk_score",
    "night_navigation_support": "night_navigation_support_score",
    "route_continuity": "route_continuity_context_score",
}

# 最終 OSM semantic risk v1 的初步權重
# 注意：support / rest / navigation_support 是負分或 lower 類，已經在 mapping base_score 反映
FINAL_WEIGHTS = {
    "navigation_risk_score": 0.25,
    "surface_slip_risk_score": 0.15,
    "route_type_risk_score": 0.12,
    "route_effort_risk_score": 0.10,
    "technical_risk_score": 0.12,
    "terrain_risk_score": 0.12,
    "exposure_risk_score": 0.12,
    "hydrology_risk_score": 0.10,
    "night_navigation_risk_score": 0.05,

    # 支援類以 mapping 中的負分進入，因此權重保留正值
    "support_score": 0.08,
    "rest_support_score": 0.05,
    "navigation_support_score": 0.08,
    "night_navigation_support_score": 0.05,

    # route_continuity 目前 base_score 0，作為 context，不直接影響總分
    "route_continuity_context_score": 0.00,
}


# =========================================================
# 3. 工具函式
# =========================================================
def norm_value(v):
    if pd.isna(v):
        return ""

    text = str(v).strip().strip('"').strip().lower()

    if text in {"", "nan", "none", "<na>", "na", "null", "nat"}:
        return ""

    return text


def split_flag_value(v):
    text = norm_value(v)

    if text in {"", "normal", "none"}:
        return []

    return [p.strip() for p in text.split("|") if p.strip()]


def make_key(source_field, source_value):
    return f"{source_field}::{source_value}"


def build_mapping_lookup(mapping_df):
    lookup = {}

    for _, row in mapping_df.iterrows():
        source_field = norm_value(row.get("source_field", ""))
        source_value = norm_value(row.get("source_value", ""))

        if not source_field or not source_value:
            continue

        key = make_key(source_field, source_value)

        lookup[key] = {
            "semantic_group": row.get("semantic_group", ""),
            "source_field": row.get("source_field", ""),
            "source_value": row.get("source_value", ""),
            "derived_class": row.get("derived_class", ""),
            "risk_domain": row.get("risk_domain", ""),
            "risk_meaning": row.get("risk_meaning", ""),
            "risk_direction": norm_value(row.get("risk_direction", "")),
            "base_score": float(row.get("base_score", 0.0)),
            "weather_sensitive": norm_value(row.get("weather_sensitive", "")),
            "needs_nlsc": norm_value(row.get("needs_nlsc", "")),
            "needs_activity": norm_value(row.get("needs_activity", "")),
            "notes": row.get("notes", ""),
        }

    return lookup


def find_mapping_for_raw(source_field, value, lookup):
    value = norm_value(value)

    if not value:
        return None

    key = make_key(source_field, value)
    return lookup.get(key)


def find_mapping_for_flag(flag_value, lookup):
    flag_value = norm_value(flag_value)

    if not flag_value:
        return None

    source_field = FLAG_VALUE_TO_SOURCE_FIELD.get(flag_value, flag_value)

    # flags 通常 mapping source_value 是 near，也可能是 yes
    for candidate_value in ["near", "yes", flag_value]:
        key = make_key(source_field, candidate_value)
        if key in lookup:
            return lookup[key]

    return None


def add_mapping_to_row(row_scores, mapping, hit_label):
    """
    將 mapping 加到該 route point 的 score accumulator。
    conditional 不直接加風險分數，只記錄 condition flag。
    """
    if mapping is None:
        return

    risk_domain = norm_value(mapping["risk_domain"])
    risk_direction = norm_value(mapping["risk_direction"])
    base_score = float(mapping["base_score"])

    if risk_domain not in RISK_DOMAIN_SCORE_COLS:
        row_scores["unhandled_risk_domains"].append(risk_domain)
        return

    score_col = RISK_DOMAIN_SCORE_COLS[risk_domain]

    if risk_direction == "conditional":
        row_scores["conditional_factor_flags"].append(hit_label)
        row_scores["conditional_risk_domains"].append(risk_domain)
        row_scores["conditional_notes"].append(str(mapping.get("notes", "")))
        return

    # higher / lower / neutral 都直接採 base_score
    # lower 通常在 mapping 表中已用負分表示
    row_scores[score_col] += base_score

    if base_score != 0:
        row_scores["applied_mapping_hits"].append(hit_label)

    if norm_value(mapping.get("weather_sensitive", "")) == "yes":
        row_scores["weather_sensitive_flags"].append(hit_label)

    if norm_value(mapping.get("needs_nlsc", "")) == "yes":
        row_scores["needs_nlsc_flags"].append(hit_label)

    if norm_value(mapping.get("needs_activity", "")) == "yes":
        row_scores["needs_activity_flags"].append(hit_label)


def unique_join(items):
    out = []
    for x in items:
        x = str(x)
        if x and x not in out:
            out.append(x)
    return "|".join(out) if out else ""


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, float(v)))


# =========================================================
# 4. 讀資料
# =========================================================
if not SEMANTIC_CSV.exists():
    raise FileNotFoundError(f"找不到 semantic CSV：{SEMANTIC_CSV.resolve()}")

if not SEMANTIC_GEOJSON.exists():
    raise FileNotFoundError(f"找不到 semantic GeoJSON：{SEMANTIC_GEOJSON.resolve()}")

if not MAPPING_CSV.exists():
    raise FileNotFoundError(f"找不到 mapping CSV：{MAPPING_CSV.resolve()}")

semantic_df = pd.read_csv(SEMANTIC_CSV, low_memory=False)
semantic_geo = gpd.read_file(SEMANTIC_GEOJSON)
mapping_df = pd.read_csv(MAPPING_CSV, low_memory=False)

lookup = build_mapping_lookup(mapping_df)

print("case:", CASE_ID)
print("case_name:", CASE_NAME)
print("semantic_csv:", SEMANTIC_CSV.resolve())
print("semantic_geojson:", SEMANTIC_GEOJSON.resolve())
print("mapping_csv:", MAPPING_CSV.resolve())
print("out_dir:", OUT_DIR.resolve())
print("semantic rows:", len(semantic_df))
print("semantic cols:", len(semantic_df.columns))
print("mapping rows:", len(mapping_df))
print("mapping keys:", len(lookup))


# =========================================================
# 5. 套用 mapping
# =========================================================
risk_rows = []

score_cols = sorted(set(RISK_DOMAIN_SCORE_COLS.values()))

for idx, row in semantic_df.iterrows():
    row_scores = {col: 0.0 for col in score_cols}

    row_scores.update({
        "applied_mapping_hits": [],
        "conditional_factor_flags": [],
        "conditional_risk_domains": [],
        "conditional_notes": [],
        "weather_sensitive_flags": [],
        "needs_nlsc_flags": [],
        "needs_activity_flags": [],
        "unhandled_risk_domains": [],
    })

    # 5a. 原始 OSM tag 欄位
    for col, source_field in FIELD_TO_SOURCE_FIELD.items():
        if col not in semantic_df.columns:
            continue

        value = row.get(col, "")
        mapping = find_mapping_for_raw(source_field, value, lookup)

        if mapping is not None:
            hit_label = f"{source_field}={norm_value(value)}"
            add_mapping_to_row(row_scores, mapping, hit_label)

    # 5b. flags 欄位
    for flag_col in FLAG_FIELDS:
        if flag_col not in semantic_df.columns:
            continue

        values = split_flag_value(row.get(flag_col, ""))

        for flag_value in values:
            mapping = find_mapping_for_flag(flag_value, lookup)

            if mapping is not None:
                hit_label = f"{flag_col}:{flag_value}"
                add_mapping_to_row(row_scores, mapping, hit_label)

    # 5c. 彙整總分
    raw_total = 0.0

    for col, w in FINAL_WEIGHTS.items():
        raw_total += row_scores.get(col, 0.0) * w

    # 第一版先限制到 0~1
    # 負分代表支援/降低風險，最低不低於 0
    row_scores["osm_semantic_risk_score_raw"] = raw_total
    row_scores["osm_semantic_risk_score"] = clamp(raw_total, 0.0, 1.0)

    # 分級
    score = row_scores["osm_semantic_risk_score"]
    if score < 0.20:
        band = "low"
    elif score < 0.40:
        band = "moderate"
    elif score < 0.65:
        band = "high"
    else:
        band = "very_high"

    row_scores["osm_semantic_risk_band"] = band

    # list → text
    for k in [
        "applied_mapping_hits",
        "conditional_factor_flags",
        "conditional_risk_domains",
        "conditional_notes",
        "weather_sensitive_flags",
        "needs_nlsc_flags",
        "needs_activity_flags",
        "unhandled_risk_domains",
    ]:
        row_scores[k] = unique_join(row_scores[k])

    risk_rows.append(row_scores)


risk_df = pd.DataFrame(risk_rows)

# =========================================================
# 6. 合併輸出
# =========================================================
out_df = pd.concat(
    [semantic_df.reset_index(drop=True), risk_df.reset_index(drop=True)],
    axis=1,
)

out_geo = semantic_geo.copy()

for col in risk_df.columns:
    out_geo[col] = risk_df[col].values

out_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
out_geo.to_file(OUT_GEOJSON, driver="GeoJSON")


# =========================================================
# 7. Summary
# =========================================================
summary_rows = []

summary_rows.append({
    "metric": "rows",
    "value": len(out_df),
})

summary_rows.append({
    "metric": "osm_semantic_risk_score_min",
    "value": out_df["osm_semantic_risk_score"].min(),
})

summary_rows.append({
    "metric": "osm_semantic_risk_score_mean",
    "value": out_df["osm_semantic_risk_score"].mean(),
})

summary_rows.append({
    "metric": "osm_semantic_risk_score_max",
    "value": out_df["osm_semantic_risk_score"].max(),
})

for band, n in out_df["osm_semantic_risk_band"].value_counts().items():
    summary_rows.append({
        "metric": f"risk_band_{band}_n",
        "value": int(n),
    })

for col in score_cols:
    summary_rows.append({
        "metric": f"{col}_mean",
        "value": float(out_df[col].mean()),
    })

summary_df = pd.DataFrame(summary_rows)
summary_df.to_csv(OUT_SUMMARY_CSV, index=False, encoding="utf-8-sig")

print("\n完成！")
print("risk CSV:", OUT_CSV.resolve())
print("risk GeoJSON:", OUT_GEOJSON.resolve())
print("summary CSV:", OUT_SUMMARY_CSV.resolve())

print("\n--- OSM semantic risk score ---")
print(out_df["osm_semantic_risk_score"].describe())

print("\n--- OSM semantic risk band ---")
print(out_df["osm_semantic_risk_band"].value_counts())

print("\n--- conditional factors ---")
print(out_df["conditional_factor_flags"].value_counts().head(20))

print("\n--- weather sensitive flags ---")
print(out_df["weather_sensitive_flags"].value_counts().head(20))

print("\n--- needs NLSC flags ---")
print(out_df["needs_nlsc_flags"].value_counts().head(20))
