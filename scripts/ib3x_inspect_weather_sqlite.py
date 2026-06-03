# -*- coding: utf-8 -*-
from pathlib import Path
import sqlite3
import pandas as pd


DB_PATH = Path(
    "/Users/iddmini/Documents/115_Motion改造/FY115_登山/weather/"
    "tw_weather_2026-05-01.sqlite3"
)


def print_section(title):
    print("\n" + "=" * 90)
    print(title)
    print("=" * 90)


def get_tables(conn):
    sql = """
    SELECT name
    FROM sqlite_master
    WHERE type='table'
    ORDER BY name;
    """
    return pd.read_sql_query(sql, conn)


def get_table_info(conn, table_name):
    return pd.read_sql_query(f'PRAGMA table_info("{table_name}")', conn)


def get_table_count(conn, table_name):
    try:
        cur = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        return cur.fetchone()[0]
    except Exception as e:
        return f"COUNT failed: {e}"


def preview_table(conn, table_name, limit=5):
    try:
        return pd.read_sql_query(f'SELECT * FROM "{table_name}" LIMIT {limit}', conn)
    except Exception as e:
        return f"PREVIEW failed: {e}"


def detect_candidate_columns(columns):
    cols = [str(c) for c in columns]
    lower_map = {c: c.lower() for c in cols}

    candidates = {
        "time": [],
        "station": [],
        "lat_lon": [],
        "rain": [],
        "temperature": [],
        "wind": [],
        "humidity": [],
        "visibility": [],
        "pressure": [],
    }

    for c, lc in lower_map.items():
        if any(k in lc for k in ["time", "date", "datetime", "obs_time", "timestamp", "資料時間", "觀測時間"]):
            candidates["time"].append(c)

        if any(k in lc for k in ["station", "station_id", "stno", "stn", "測站", "站號", "站名"]):
            candidates["station"].append(c)

        if any(k in lc for k in ["lat", "latitude", "緯度", "lon", "lng", "longitude", "經度"]):
            candidates["lat_lon"].append(c)

        if any(k in lc for k in ["rain", "precip", "rainfall", "降雨", "雨量", "precipitation"]):
            candidates["rain"].append(c)

        if any(k in lc for k in ["temp", "temperature", "氣溫", "溫度"]):
            candidates["temperature"].append(c)

        if any(k in lc for k in ["wind", "windspeed", "wind_speed", "風速", "風向"]):
            candidates["wind"].append(c)

        if any(k in lc for k in ["humid", "humidity", "相對濕度", "濕度"]):
            candidates["humidity"].append(c)

        if any(k in lc for k in ["vis", "visibility", "能見度"]):
            candidates["visibility"].append(c)

        if any(k in lc for k in ["press", "pressure", "氣壓"]):
            candidates["pressure"].append(c)

    return candidates


def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"找不到資料庫：{DB_PATH.resolve()}")

    print_section("SQLite weather DB inspection")
    print("DB:", DB_PATH.resolve())
    print("Size GB:", round(DB_PATH.stat().st_size / 1024 / 1024 / 1024, 3))

    conn = sqlite3.connect(DB_PATH)

    try:
        tables = get_tables(conn)

        print_section("Tables")
        print(tables.to_string(index=False))

        for table_name in tables["name"].tolist():
            print_section(f"Table: {table_name}")

            count = get_table_count(conn, table_name)
            print("rows:", count)

            info = get_table_info(conn, table_name)
            print("\n--- columns ---")
            print(info.to_string(index=False))

            cols = info["name"].tolist()
            candidates = detect_candidate_columns(cols)

            print("\n--- candidate columns ---")
            any_found = False
            for k, v in candidates.items():
                if v:
                    any_found = True
                    print(f"{k}: {v}")

            if not any_found:
                print("(no obvious weather-related columns detected by keyword)")

            print("\n--- preview ---")
            preview = preview_table(conn, table_name, limit=5)
            if isinstance(preview, pd.DataFrame):
                print(preview.to_string(index=False))
            else:
                print(preview)

    finally:
        conn.close()


if __name__ == "__main__":
    main()