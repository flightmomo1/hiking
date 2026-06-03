# -*- coding: utf-8 -*-
from pathlib import Path
import sqlite3
import pandas as pd


# =========================================================
# A. Input / Output
# =========================================================
DB_PATH = Path(
    "/Users/iddmini/Documents/115_Motion改造/FY115_登山/weather/"
    "tw_weather_2026-05-01.sqlite3"
)

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent

OUT_DIR = BASE_DIR / "ib3_environment_output"

OUT_TABLES_CSV = OUT_DIR / "weather_database_tables.csv"
OUT_SCHEMA_CSV = OUT_DIR / "weather_database_schema.csv"
OUT_CANDIDATES_CSV = OUT_DIR / "weather_database_column_candidates.csv"
OUT_SAMPLE_VALUES_CSV = OUT_DIR / "weather_database_candidate_sample_values.csv"


# =========================================================
# B. Candidate keyword rules
# =========================================================
CANDIDATE_RULES = {
    "wind_direction": [
        "wind_direction",
        "wind_dir",
        "winddirection",
        "wind_from",
        "windfrom",
        "wd",
        "wdir",
        "風向",
    ],
    "wind_speed": [
        "wind_speed",
        "windspeed",
        "wind_spd",
        "ws",
        "風速",
    ],
    "wind_gust": [
        "gust",
        "wind_gust",
        "max_wind",
        "陣風",
        "最大風",
    ],
    "visibility": [
        "visibility",
        "vis",
        "能見度",
    ],
    "pressure": [
        "pressure",
        "press",
        "hpa",
        "barometer",
        "氣壓",
    ],
    "weather_text": [
        "weather",
        "weather_desc",
        "phenomena",
        "phenomenon",
        "wx",
        "天氣",
        "天氣現象",
    ],
    "precipitation": [
        "precip",
        "rain",
        "rainfall",
        "precipitation",
        "降雨",
        "雨量",
    ],
    "humidity": [
        "humidity",
        "relative_humidity",
        "rh",
        "濕度",
    ],
    "temperature": [
        "temperature",
        "temp",
        "溫度",
    ],
    "station": [
        "station",
        "station_id",
        "station_name",
        "測站",
    ],
    "time": [
        "time",
        "obs_time",
        "datetime",
        "timestamp",
        "觀測時間",
        "時間",
    ],
    "location": [
        "lat",
        "latitude",
        "lon",
        "longitude",
        "經度",
        "緯度",
    ],
}


# =========================================================
# C. Utility
# =========================================================
def ensure_exists(fp: Path):
    if not fp.exists():
        raise FileNotFoundError(f"找不到檔案：{fp.resolve()}")


def get_sqlite_tables(conn):
    sql = """
    SELECT
        name,
        type
    FROM sqlite_master
    WHERE type IN ('table', 'view')
      AND name NOT LIKE 'sqlite_%'
    ORDER BY type, name
    """
    return pd.read_sql_query(sql, conn)


def get_table_schema(conn, table_name):
    sql = f"PRAGMA table_info('{table_name}')"
    df = pd.read_sql_query(sql, conn)

    if df.empty:
        return pd.DataFrame()

    df["table_name"] = table_name

    # PRAGMA table_info columns:
    # cid, name, type, notnull, dflt_value, pk
    cols = [
        "table_name",
        "cid",
        "name",
        "type",
        "notnull",
        "dflt_value",
        "pk",
    ]
    cols = [c for c in cols if c in df.columns]
    return df[cols]


def classify_column_candidate(column_name):
    name = str(column_name).lower()

    matched_categories = []

    for category, keywords in CANDIDATE_RULES.items():
        for kw in keywords:
            if kw.lower() in name:
                matched_categories.append(category)
                break

    if not matched_categories:
        return ""

    return "|".join(matched_categories)


def quote_identifier(name):
    return '"' + str(name).replace('"', '""') + '"'


def get_table_row_count(conn, table_name):
    try:
        sql = f"SELECT COUNT(*) AS n FROM {quote_identifier(table_name)}"
        df = pd.read_sql_query(sql, conn)
        return int(df["n"].iloc[0])
    except Exception:
        return None


def get_sample_values(conn, table_name, column_name, limit=10):
    try:
        sql = f"""
        SELECT DISTINCT {quote_identifier(column_name)} AS value
        FROM {quote_identifier(table_name)}
        WHERE {quote_identifier(column_name)} IS NOT NULL
        LIMIT {int(limit)}
        """
        df = pd.read_sql_query(sql, conn)

        if df.empty:
            return ""

        values = df["value"].astype(str).tolist()
        return " | ".join(values)

    except Exception as e:
        return f"ERROR: {e}"


def build_schema(conn, tables_df):
    rows = []

    for _, row in tables_df.iterrows():
        table_name = row["name"]
        table_type = row["type"]

        schema_df = get_table_schema(conn, table_name)

        if schema_df.empty:
            continue

        row_count = get_table_row_count(conn, table_name)

        for _, c in schema_df.iterrows():
            column_name = c["name"]
            candidate_category = classify_column_candidate(column_name)

            rows.append(
                {
                    "table_name": table_name,
                    "table_type": table_type,
                    "row_count": row_count,
                    "cid": c.get("cid"),
                    "column_name": column_name,
                    "column_type": c.get("type"),
                    "notnull": c.get("notnull"),
                    "default_value": c.get("dflt_value"),
                    "primary_key": c.get("pk"),
                    "candidate_category": candidate_category,
                }
            )

    return pd.DataFrame(rows)


def build_candidates(schema_df):
    if schema_df.empty:
        return pd.DataFrame()

    candidates = schema_df[
        schema_df["candidate_category"].astype(str).str.len() > 0
    ].copy()

    priority_order = {
        "wind_direction": 1,
        "wind_speed": 2,
        "wind_gust": 3,
        "visibility": 4,
        "pressure": 5,
        "weather_text": 6,
        "precipitation": 7,
        "humidity": 8,
        "temperature": 9,
        "station": 10,
        "time": 11,
        "location": 12,
    }

    def sort_priority(categories):
        cats = str(categories).split("|")
        vals = [priority_order.get(c, 99) for c in cats]
        return min(vals) if vals else 99

    candidates["sort_priority"] = candidates["candidate_category"].apply(sort_priority)

    candidates = candidates.sort_values(
        ["sort_priority", "table_name", "column_name"]
    ).reset_index(drop=True)

    return candidates


def build_candidate_sample_values(conn, candidates_df):
    rows = []

    if candidates_df.empty:
        return pd.DataFrame()

    for _, row in candidates_df.iterrows():
        table_name = row["table_name"]
        column_name = row["column_name"]

        sample_values = get_sample_values(
            conn=conn,
            table_name=table_name,
            column_name=column_name,
            limit=10,
        )

        rows.append(
            {
                "table_name": table_name,
                "column_name": column_name,
                "candidate_category": row["candidate_category"],
                "column_type": row["column_type"],
                "sample_values": sample_values,
            }
        )

    return pd.DataFrame(rows)


def print_key_findings(candidates_df):
    print("\n=== key candidate columns ===")

    if candidates_df.empty:
        print("(no candidate columns found)")
        return

    key_categories = [
        "wind_direction",
        "wind_speed",
        "wind_gust",
        "visibility",
        "pressure",
        "weather_text",
        "precipitation",
        "humidity",
        "temperature",
    ]

    for category in key_categories:
        matched = candidates_df[
            candidates_df["candidate_category"]
            .astype(str)
            .str.contains(category, regex=False)
        ]

        print(f"\n[{category}]")

        if matched.empty:
            print("  (not found)")
            continue

        show_cols = [
            "table_name",
            "column_name",
            "column_type",
            "row_count",
            "candidate_category",
        ]
        show_cols = [c for c in show_cols if c in matched.columns]
        print(matched[show_cols].to_string(index=False))


def print_recommendation(candidates_df):
    print("\n=== recommendation ===")

    has_wind_direction = (
        not candidates_df[
            candidates_df["candidate_category"]
            .astype(str)
            .str.contains("wind_direction", regex=False)
        ].empty
    )

    has_visibility = (
        not candidates_df[
            candidates_df["candidate_category"]
            .astype(str)
            .str.contains("visibility", regex=False)
        ].empty
    )

    has_pressure = (
        not candidates_df[
            candidates_df["candidate_category"]
            .astype(str)
            .str.contains("pressure", regex=False)
        ].empty
    )

    has_gust = (
        not candidates_df[
            candidates_df["candidate_category"]
            .astype(str)
            .str.contains("wind_gust", regex=False)
        ].empty
    )

    if has_wind_direction:
        print("1. 找到疑似風向欄位：可進一步做 windward / leeward 迎風坡與背風坡分析。")
    else:
        print("1. 未找到明顯風向欄位：短期先做『風速 × 地形暴露』，迎風坡/背風坡留待補資料。")

    if has_visibility:
        print("2. 找到疑似能見度欄位：可納入 visibility_navigation_factor。")
    else:
        print("2. 未找到明顯能見度欄位，或欄位可能存在但命名未被規則捕捉。")

    if has_pressure:
        print("3. 找到疑似氣壓欄位：可保留 pressure trend 作為天候轉壞輔助證據。")
    else:
        print("3. 未找到明顯氣壓欄位。")

    if has_gust:
        print("4. 找到疑似陣風欄位：可用於 ridge / exposed segment 風暴露風險。")
    else:
        print("4. 未找到明顯陣風欄位。")


# =========================================================
# D. Main
# =========================================================
def main():
    ensure_exists(DB_PATH)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("DB:", DB_PATH.resolve())

    conn = sqlite3.connect(DB_PATH)

    try:
        tables_df = get_sqlite_tables(conn)

        if tables_df.empty:
            raise ValueError("SQLite 中找不到 table 或 view。")

        # add row count
        row_counts = []
        for _, row in tables_df.iterrows():
            table_name = row["name"]
            row_counts.append(get_table_row_count(conn, table_name))

        tables_df["row_count"] = row_counts

        schema_df = build_schema(conn, tables_df)
        candidates_df = build_candidates(schema_df)
        sample_values_df = build_candidate_sample_values(conn, candidates_df)

    finally:
        conn.close()

    tables_df.to_csv(OUT_TABLES_CSV, index=False, encoding="utf-8-sig")
    schema_df.to_csv(OUT_SCHEMA_CSV, index=False, encoding="utf-8-sig")
    candidates_df.to_csv(OUT_CANDIDATES_CSV, index=False, encoding="utf-8-sig")
    sample_values_df.to_csv(OUT_SAMPLE_VALUES_CSV, index=False, encoding="utf-8-sig")

    print("\n完成！")
    print("tables CSV:", OUT_TABLES_CSV.resolve())
    print("schema CSV:", OUT_SCHEMA_CSV.resolve())
    print("candidate columns CSV:", OUT_CANDIDATES_CSV.resolve())
    print("sample values CSV:", OUT_SAMPLE_VALUES_CSV.resolve())

    print("\n=== tables ===")
    print(tables_df.to_string(index=False))

    print_key_findings(candidates_df)
    print_recommendation(candidates_df)


if __name__ == "__main__":
    main()