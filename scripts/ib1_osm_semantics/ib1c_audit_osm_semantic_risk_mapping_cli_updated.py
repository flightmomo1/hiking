# =========================================================
# ib1c_audit_osm_semantic_risk_mapping.py
#
# 目的：
# - 讀取 ib1c OSM semantic enriched route profile
# - 讀取 OSM semantic risk mapping table
# - 盤點哪些 OSM 語意已經有風險對照
# - 找出 ib1c 產生但 mapping 尚未定義的語意值
# - 找出 mapping 已定義但本次路線未出現的語意
# - 找出 implemented_in_ib1c=yes 但 used_in_ib2=no 的待導入風險特徵
# =========================================================

from pathlib import Path
import argparse
import pandas as pd


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
        description="ib1c audit: check OSM semantic risk mapping coverage for semantic enriched route profile"
    )
    parser.add_argument("--case-id", default="juansi_waterfall_fitcsv_20260503")
    parser.add_argument("--case-name", default=None)
    parser.add_argument(
        "--semantic-csv",
        default=None,
        help="ib1c semantic enriched CSV. Default: outputs/ib1c_route_profile_semantics/<case-id>/<case-id>_route_profile_semantic_enriched.csv",
    )
    parser.add_argument(
        "--mapping-csv",
        default=None,
        help="OSM semantic risk mapping CSV. Default: configs/risk_semantics/osm_semantic_risk_mapping_v1_5_support_updated.csv",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Output folder. Default: outputs/ib1c_osm_semantic_audit/<case-id>",
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

if args.mapping_csv is None:
    MAPPING_CSV = (
        PROJECT_ROOT
        / "configs"
        / "risk_semantics"
        / "osm_semantic_risk_mapping_v1_5_support_updated.csv"
    )
else:
    MAPPING_CSV = resolve_path(args.mapping_csv)

if args.out_dir is None:
    OUT_DIR = (
        PROJECT_ROOT
        / "outputs"
        / "ib1c_osm_semantic_audit"
        / CASE_ID
    )
else:
    OUT_DIR = resolve_path(args.out_dir)

OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_FIELD_SUMMARY = OUT_DIR / f"{CASE_ID}_semantic_field_summary.csv"
OUT_VALUE_COVERAGE = OUT_DIR / f"{CASE_ID}_semantic_value_mapping_coverage.csv"
OUT_UNMAPPED_VALUES = OUT_DIR / f"{CASE_ID}_semantic_unmapped_values.csv"
OUT_MAPPING_UNUSED = OUT_DIR / f"{CASE_ID}_mapping_defined_but_not_seen.csv"
OUT_IB2_PENDING = OUT_DIR / f"{CASE_ID}_implemented_but_not_used_in_ib2.csv"
OUT_SUMMARY_TXT = OUT_DIR / f"{CASE_ID}_semantic_audit_summary.txt"


# =========================================================
# 1. 欲盤點的 ib1c 語意欄位
# =========================================================
# key = ib1c enriched CSV 欄位
# value = 對應 mapping CSV 的 source_field
FIELD_TO_SOURCE_FIELD = {
    # navigation：原始 OSM tag
    "osm_trail_visibility": "trail_visibility",

    # surface：原始 OSM tag
    "osm_surface": "surface",

    # route type / route structure：原始 OSM tag
    "osm_highway": "highway",
    "osm_bridge": "bridge",
    "osm_ford": "ford",
    "osm_tunnel": "tunnel",

    # technical / assist：原始 OSM tag
    "osm_handrail": "handrail",
    "osm_safety_rope": "safety_rope",

    # OSM difficulty：原始 OSM tag
    "osm_sac_scale": "sac_scale",

    # lighting：原始 OSM tag
    "osm_lit": "lit",
    "osm_lit_status": "lit",
}

# flags 欄位的值是多值組合，例如 waterway|wetland，需要拆開
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

# flag 值對應 mapping CSV 的 source_field
FLAG_VALUE_TO_SOURCE_FIELD = {
    # technical
    "handrail": "handrail",
    "safety_rope": "safety_rope",
    "rungs": "rungs",
    "ladder": "ladder",
    "via_ferrata": "via_ferrata",
    "assisted_trail": "assisted_trail",

    # hazard
    "cliff": "cliff",
    "scree": "scree",
    "bare_rock": "bare_rock",
    "landslide": "landslide",

    # hydrology
    "waterway": "waterway",
    "wetland": "wetland",
    "water_area": "water_area",

    # navigation support / landmark
    "guidepost": "guidepost",
    "trailhead": "trailhead",
    "peak": "peak",

    # facility / rest / support
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

    # lighting
    "street_lamp": "street_lamp",
}


# =========================================================
# 2. 工具函式
# =========================================================
def norm_value(v):
    if pd.isna(v):
        return ""

    text = str(v).strip().strip('"').strip().lower()

    if text in {"", "nan", "none", "<na>", "na", "null", "nat"}:
        return ""

    return text


def split_flag_value(v):
    """
    將 flags 欄位拆成單一語意值。
    normal / none 視為無語意命中，不列入風險 mapping 覆蓋率。
    """
    text = norm_value(v)

    if text in {"", "normal", "none"}:
        return []

    parts = [p.strip() for p in text.split("|") if p.strip()]
    return parts


def make_mapping_key(source_field, source_value):
    return f"{source_field}::{source_value}"


def mapping_keys_from_table(mapping_df):
    keys = set()

    for _, row in mapping_df.iterrows():
        source_field = norm_value(row.get("source_field", ""))
        source_value = norm_value(row.get("source_value", ""))

        if not source_field or not source_value:
            continue

        keys.add(make_mapping_key(source_field, source_value))

    return keys


def check_mapping(source_field, source_value, mapping_key_set):
    """
    一般欄位採 exact matching。
    flag 類通常使用 near，因此外部會另外處理。
    """
    key = make_mapping_key(source_field, source_value)
    return key in mapping_key_set


# =========================================================
# 3. 讀資料
# =========================================================
if not SEMANTIC_CSV.exists():
    raise FileNotFoundError(f"找不到 ib1c semantic CSV：{SEMANTIC_CSV.resolve()}")

if not MAPPING_CSV.exists():
    raise FileNotFoundError(f"找不到 mapping CSV：{MAPPING_CSV.resolve()}")

semantic_df = pd.read_csv(SEMANTIC_CSV, low_memory=False)
mapping_df = pd.read_csv(MAPPING_CSV, low_memory=False)

mapping_key_set = mapping_keys_from_table(mapping_df)

print("case:", CASE_ID)
print("case_name:", CASE_NAME)
print("semantic_csv:", SEMANTIC_CSV.resolve())
print("mapping_csv:", MAPPING_CSV.resolve())
print("out_dir:", OUT_DIR.resolve())
print("semantic rows:", len(semantic_df))
print("semantic cols:", len(semantic_df.columns))
print("mapping rows:", len(mapping_df))
print("mapping keys:", len(mapping_key_set))


# =========================================================
# 4. 欄位層級盤點
# =========================================================
field_rows = []

for col in sorted(set(list(FIELD_TO_SOURCE_FIELD.keys()) + list(FLAG_FIELDS.keys()))):
    exists = col in semantic_df.columns

    if exists:
        non_empty_n = semantic_df[col].map(norm_value).ne("").sum()
        unique_n = semantic_df[col].map(norm_value).replace("", pd.NA).dropna().nunique()
    else:
        non_empty_n = 0
        unique_n = 0

    field_rows.append({
        "field": col,
        "exists_in_ib1c_output": int(exists),
        "non_empty_n": int(non_empty_n),
        "unique_n": int(unique_n),
        "source_field_for_mapping": FIELD_TO_SOURCE_FIELD.get(col, ""),
        "is_flag_field": int(col in FLAG_FIELDS),
    })

field_summary = pd.DataFrame(field_rows)
field_summary.to_csv(OUT_FIELD_SUMMARY, index=False, encoding="utf-8-sig")


# =========================================================
# 5. 語意值 mapping 覆蓋率盤點
# =========================================================
coverage_rows = []

# 5a. 一般欄位
for col, source_field in FIELD_TO_SOURCE_FIELD.items():
    if col not in semantic_df.columns:
        coverage_rows.append({
            "ib1c_field": col,
            "source_field": source_field,
            "observed_value": "",
            "observed_n": 0,
            "mapping_key": "",
            "has_mapping": 0,
            "note": "field_missing_in_ib1c_output",
        })
        continue

    vc = (
        semantic_df[col]
        .map(norm_value)
        .replace("", pd.NA)
        .dropna()
        .value_counts()
    )

    for value, n in vc.items():
        key = make_mapping_key(source_field, value)
        has_mapping = key in mapping_key_set

        coverage_rows.append({
            "ib1c_field": col,
            "source_field": source_field,
            "observed_value": value,
            "observed_n": int(n),
            "mapping_key": key,
            "has_mapping": int(has_mapping),
            "note": "",
        })


# 5b. flags 欄位
for flag_col, semantic_group in FLAG_FIELDS.items():
    if flag_col not in semantic_df.columns:
        coverage_rows.append({
            "ib1c_field": flag_col,
            "source_field": "",
            "observed_value": "",
            "observed_n": 0,
            "mapping_key": "",
            "has_mapping": 0,
            "note": "flag_field_missing_in_ib1c_output",
        })
        continue

    exploded = []

    for v in semantic_df[flag_col]:
        exploded.extend(split_flag_value(v))

    if not exploded:
        continue

    vc = pd.Series(exploded).value_counts()

    for value, n in vc.items():
        source_field = FLAG_VALUE_TO_SOURCE_FIELD.get(value, value)

        # flags 類 mapping 表多用 source_value=near
        key_near = make_mapping_key(source_field, "near")
        key_yes = make_mapping_key(source_field, "yes")
        key_exact = make_mapping_key(source_field, value)

        has_mapping = (
            key_near in mapping_key_set
            or key_yes in mapping_key_set
            or key_exact in mapping_key_set
        )

        if key_near in mapping_key_set:
            mapping_key = key_near
        elif key_yes in mapping_key_set:
            mapping_key = key_yes
        else:
            mapping_key = key_exact

        coverage_rows.append({
            "ib1c_field": flag_col,
            "source_field": source_field,
            "observed_value": value,
            "observed_n": int(n),
            "mapping_key": mapping_key,
            "has_mapping": int(has_mapping),
            "note": f"flag_group={semantic_group}",
        })


coverage_df = pd.DataFrame(coverage_rows)
coverage_df.to_csv(OUT_VALUE_COVERAGE, index=False, encoding="utf-8-sig")

unmapped_df = coverage_df[
    (coverage_df["observed_n"] > 0)
    & (coverage_df["has_mapping"] == 0)
].copy()

unmapped_df.to_csv(OUT_UNMAPPED_VALUES, index=False, encoding="utf-8-sig")


# =========================================================
# 6. mapping 已定義但本次路線未出現
# =========================================================
observed_mapping_keys = set(
    coverage_df.loc[
        coverage_df["has_mapping"] == 1,
        "mapping_key"
    ].dropna().astype(str)
)

mapping_unused_rows = []

for _, row in mapping_df.iterrows():
    source_field = norm_value(row.get("source_field", ""))
    source_value = norm_value(row.get("source_value", ""))
    key = make_mapping_key(source_field, source_value)

    if key not in observed_mapping_keys:
        mapping_unused_rows.append({
            "mapping_key": key,
            "semantic_group": row.get("semantic_group", ""),
            "source_field": row.get("source_field", ""),
            "source_value": row.get("source_value", ""),
            "derived_class": row.get("derived_class", ""),
            "risk_domain": row.get("risk_domain", ""),
            "base_score": row.get("base_score", ""),
            "implemented_in_ib1c": row.get("implemented_in_ib1c", ""),
            "used_in_ib2": row.get("used_in_ib2", ""),
            "notes": row.get("notes", ""),
        })

mapping_unused_df = pd.DataFrame(mapping_unused_rows)
mapping_unused_df.to_csv(OUT_MAPPING_UNUSED, index=False, encoding="utf-8-sig")


# =========================================================
# 7. implemented_in_ib1c=yes 但 used_in_ib2=no
# =========================================================
ib2_pending = mapping_df[
    (mapping_df["implemented_in_ib1c"].astype(str).str.lower() == "yes")
    & (mapping_df["used_in_ib2"].astype(str).str.lower() == "no")
].copy()

ib2_pending.to_csv(OUT_IB2_PENDING, index=False, encoding="utf-8-sig")


# =========================================================
# 8. Summary
# =========================================================
total_observed_values = len(coverage_df[coverage_df["observed_n"] > 0])
mapped_values = len(coverage_df[(coverage_df["observed_n"] > 0) & (coverage_df["has_mapping"] == 1)])
unmapped_values = len(unmapped_df)

coverage_rate = mapped_values / total_observed_values if total_observed_values else 0

summary_lines = [
    f"CASE_ID: {CASE_ID}",
    f"CASE_NAME: {CASE_NAME}",
    "",
    f"semantic rows: {len(semantic_df)}",
    f"semantic columns: {len(semantic_df.columns)}",
    f"mapping rows: {len(mapping_df)}",
    "",
    f"observed semantic values: {total_observed_values}",
    f"mapped observed values: {mapped_values}",
    f"unmapped observed values: {unmapped_values}",
    f"mapping coverage rate: {coverage_rate:.3f}",
    "",
    f"field summary: {OUT_FIELD_SUMMARY}",
    f"value coverage: {OUT_VALUE_COVERAGE}",
    f"unmapped values: {OUT_UNMAPPED_VALUES}",
    f"mapping defined but not seen: {OUT_MAPPING_UNUSED}",
    f"implemented but not used in ib2: {OUT_IB2_PENDING}",
]

OUT_SUMMARY_TXT.write_text("\n".join(summary_lines), encoding="utf-8")

print("\n完成！")
print("\n".join(summary_lines))

if unmapped_values > 0:
    print("\n--- unmapped observed values preview ---")
    print(unmapped_df.head(30))
else:
    print("\n所有 observed semantic values 都已有 mapping。")
