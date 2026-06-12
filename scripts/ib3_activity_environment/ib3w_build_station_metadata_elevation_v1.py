#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
IB3W Station Metadata Elevation v1

Purpose:
- Extract unique weather / water stations from the weather SQLite DB.
- Preserve existing DB elevation when available.
- Mark stations that need future DEM/NLSC terrain elevation lookup.
- Do NOT perform DEM/NLSC lookup in this version.
- Do NOT modify station ranking / temporal coverage / variable coverage outputs.
"""

from __future__ import annotations

import argparse
import html
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


COLUMN_CANDIDATES = {
    "source": [
        "source",
        "source_code",
        "data_source",
        "provider",
        "agency",
    ],
    "dataset_code": [
        "dataset_code",
        "dataset",
        "dataid",
        "data_id",
        "api_name",
        "resource_id",
        "dataset_name",
    ],
    "station_id": [
        "station_id",
        "stationID",
        "StationID",
        "station_no",
        "stationNo",
        "station_code",
        "StationCode",
        "stationId",
        "id",
    ],
    "station_name": [
        "station_name",
        "stationName",
        "StationName",
        "name",
        "Name",
        "station_name_zh",
        "station_zh_name",
    ],
    "latitude": [
        "latitude",
        "lat",
        "Latitude",
        "station_latitude",
        "station_lat",
        "y",
    ],
    "longitude": [
        "longitude",
        "lon",
        "lng",
        "Longitude",
        "station_longitude",
        "station_lon",
        "x",
    ],
    "elevation_m": [
        "elevation_m",
        "elevation",
        "elev",
        "altitude_m",
        "altitude",
        "station_elevation_m",
        "station_elevation",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--weather-db",
        default="weather/tw_weather_2026-05-01.sqlite3",
        help="SQLite DB path containing weather/water observations.",
    )
    parser.add_argument(
        "--out-dir",
        default="outputs/ib3w_station_metadata_elevation_v1",
        help="Output directory.",
    )
    return parser.parse_args()


def list_tables(conn: sqlite3.Connection) -> List[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows]


def table_columns(conn: sqlite3.Connection, table_name: str) -> List[str]:
    rows = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    return [r[1] for r in rows]


def pick_column(columns: List[str], logical_name: str) -> Optional[str]:
    candidates = COLUMN_CANDIDATES[logical_name]
    lower_map = {c.lower(): c for c in columns}
    for c in candidates:
        if c in columns:
            return c
        if c.lower() in lower_map:
            return lower_map[c.lower()]
    return None


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def extract_station_table(
    conn: sqlite3.Connection,
    table_name: str,
    station_type: str,
    fallback_source: str,
    fallback_dataset_code: str,
) -> pd.DataFrame:
    columns = table_columns(conn, table_name)

    colmap: Dict[str, Optional[str]] = {
        logical: pick_column(columns, logical)
        for logical in COLUMN_CANDIDATES.keys()
    }

    required = ["station_id", "latitude", "longitude"]
    missing_required = [k for k in required if colmap.get(k) is None]
    if missing_required:
        return pd.DataFrame(
            [
                {
                    "source": fallback_source,
                    "station_type": station_type,
                    "dataset_code": fallback_dataset_code,
                    "station_id": "",
                    "station_name": "",
                    "latitude": "",
                    "longitude": "",
                    "db_elevation_m": "",
                    "terrain_lookup_elevation_m": "",
                    "elevation_source": "unknown",
                    "elevation_lookup_status": "MISSING_COORDINATE",
                    "needs_terrain_lookup": "false",
                    "metadata_source_table": table_name,
                    "metadata_status": "SKIPPED_MISSING_REQUIRED_COLUMNS",
                    "notes": "missing required columns: " + ",".join(missing_required),
                }
            ]
        )

    select_exprs = []
    aliases = [
        "source",
        "dataset_code",
        "station_id",
        "station_name",
        "latitude",
        "longitude",
        "db_elevation_m",
    ]

    source_col = colmap.get("source")
    dataset_col = colmap.get("dataset_code")
    station_name_col = colmap.get("station_name")
    elevation_col = colmap.get("elevation_m")

    select_exprs.append(
        f"{quote_ident(source_col)} AS source" if source_col else f"'{fallback_source}' AS source"
    )
    select_exprs.append(
        f"{quote_ident(dataset_col)} AS dataset_code" if dataset_col else f"'{fallback_dataset_code}' AS dataset_code"
    )
    select_exprs.append(f"{quote_ident(colmap['station_id'])} AS station_id")
    select_exprs.append(
        f"{quote_ident(station_name_col)} AS station_name" if station_name_col else "'' AS station_name"
    )
    select_exprs.append(f"{quote_ident(colmap['latitude'])} AS latitude")
    select_exprs.append(f"{quote_ident(colmap['longitude'])} AS longitude")
    select_exprs.append(
        f"{quote_ident(elevation_col)} AS db_elevation_m" if elevation_col else "NULL AS db_elevation_m"
    )

    sql = f"""
        SELECT DISTINCT
            {", ".join(select_exprs)}
        FROM {quote_ident(table_name)}
        WHERE {quote_ident(colmap['station_id'])} IS NOT NULL
          AND {quote_ident(colmap['latitude'])} IS NOT NULL
          AND {quote_ident(colmap['longitude'])} IS NOT NULL
    """

    df = pd.read_sql_query(sql, conn)

    if df.empty:
        return pd.DataFrame(columns=[
            "source",
            "station_type",
            "dataset_code",
            "station_id",
            "station_name",
            "latitude",
            "longitude",
            "db_elevation_m",
            "terrain_lookup_elevation_m",
            "elevation_source",
            "elevation_lookup_status",
            "needs_terrain_lookup",
            "metadata_source_table",
            "metadata_status",
            "notes",
        ])

    for col in aliases:
        if col not in df.columns:
            df[col] = ""

    df["station_type"] = station_type
    df["metadata_source_table"] = table_name
    df["metadata_status"] = "EXTRACTED"

    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["db_elevation_m"] = pd.to_numeric(df["db_elevation_m"], errors="coerce")

    df = df.dropna(subset=["latitude", "longitude"]).copy()

    df["terrain_lookup_elevation_m"] = ""

    has_db_elevation = df["db_elevation_m"].notna()
    df["elevation_source"] = has_db_elevation.map(
        {True: "db_elevation", False: "terrain_lookup_pending"}
    )
    df["elevation_lookup_status"] = has_db_elevation.map(
        {True: "DB_ELEVATION_AVAILABLE", False: "NEED_TERRAIN_LOOKUP"}
    )
    df["needs_terrain_lookup"] = (~has_db_elevation).astype(str).str.lower()

    df["notes"] = ""
    df.loc[~has_db_elevation, "notes"] = "No db_elevation_m; future DEM/NLSC lookup required."

    output_cols = [
        "source",
        "station_type",
        "dataset_code",
        "station_id",
        "station_name",
        "latitude",
        "longitude",
        "db_elevation_m",
        "terrain_lookup_elevation_m",
        "elevation_source",
        "elevation_lookup_status",
        "needs_terrain_lookup",
        "metadata_source_table",
        "metadata_status",
        "notes",
    ]
    return df[output_cols]


def build_html_report(metadata_df: pd.DataFrame, summary_df: pd.DataFrame, out_html: Path) -> None:
    def df_to_html(df: pd.DataFrame, max_rows: int = 100) -> str:
        if df.empty:
            return "<p>No rows.</p>"
        return df.head(max_rows).to_html(index=False, escape=True)

    total = len(metadata_df)
    need_lookup = int((metadata_df["needs_terrain_lookup"] == "true").sum()) if total else 0
    db_available = int((metadata_df["elevation_lookup_status"] == "DB_ELEVATION_AVAILABLE").sum()) if total else 0

    body = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>IB3W Station Metadata Elevation v1</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; }}
table {{ border-collapse: collapse; margin: 12px 0; font-size: 13px; }}
th, td {{ border: 1px solid #ccc; padding: 4px 8px; }}
th {{ background: #f2f2f2; }}
code {{ background: #f7f7f7; padding: 2px 4px; }}
</style>
</head>
<body>
<h1>IB3W Station Metadata Elevation v1</h1>
<p>This report extracts station metadata and flags stations needing terrain elevation lookup. It does not perform DEM/NLSC lookup.</p>

<h2>Summary</h2>
<ul>
<li>Total station metadata rows: <code>{total}</code></li>
<li>DB elevation available: <code>{db_available}</code></li>
<li>Need terrain lookup: <code>{need_lookup}</code></li>
</ul>

<h2>Status Summary</h2>
{df_to_html(summary_df)}

<h2>Metadata Preview</h2>
{df_to_html(metadata_df)}
</body>
</html>
"""
    out_html.write_text(body, encoding="utf-8")


def main() -> None:
    args = parse_args()

    db_path = Path(args.weather_db)
    if not db_path.exists():
        raise FileNotFoundError(f"Missing SQLite DB: {db_path}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    tables = set(list_tables(conn))

    frames: List[pd.DataFrame] = []

    if "weather_observations" in tables:
        frames.append(
            extract_station_table(
                conn,
                table_name="weather_observations",
                station_type="weather",
                fallback_source="cwa",
                fallback_dataset_code="weather_observations",
            )
        )

    if "water_level_observations" in tables:
        frames.append(
            extract_station_table(
                conn,
                table_name="water_level_observations",
                station_type="water",
                fallback_source="wra",
                fallback_dataset_code="water_level_observations",
            )
        )

    if "wra_station_metadata" in tables:
        frames.append(
            extract_station_table(
                conn,
                table_name="wra_station_metadata",
                station_type="water",
                fallback_source="wra",
                fallback_dataset_code="wra_station_metadata",
            )
        )

    conn.close()

    if not frames:
        raise RuntimeError("No supported station metadata tables found.")

    metadata_df = pd.concat(frames, ignore_index=True)

    # Remove diagnostic skipped rows from de-dup preference only if real rows exist.
    real_df = metadata_df[metadata_df["metadata_status"] == "EXTRACTED"].copy()
    diag_df = metadata_df[metadata_df["metadata_status"] != "EXTRACTED"].copy()

    if not real_df.empty:
        # Prefer rows with db elevation, then weather over water metadata duplicates, then stable source table order.
        real_df["_has_db_elevation"] = real_df["db_elevation_m"].notna().astype(int)
        real_df["_source_table_priority"] = real_df["metadata_source_table"].map(
            {
                "weather_observations": 1,
                "water_level_observations": 2,
                "wra_station_metadata": 3,
            }
        ).fillna(99)
        real_df = real_df.sort_values(
            by=[
                "station_type",
                "station_id",
                "_has_db_elevation",
                "_source_table_priority",
            ],
            ascending=[True, True, False, True],
        )
        real_df = real_df.drop_duplicates(
            subset=["source", "station_type", "station_id", "latitude", "longitude"],
            keep="first",
        )
        real_df = real_df.drop(columns=["_has_db_elevation", "_source_table_priority"])

    metadata_df = pd.concat([real_df, diag_df], ignore_index=True)

    summary_df = (
        metadata_df
        .groupby(
            [
                "source",
                "station_type",
                "metadata_source_table",
                "elevation_lookup_status",
                "needs_terrain_lookup",
            ],
            dropna=False,
        )
        .size()
        .reset_index(name="station_rows")
        .sort_values(
            by=[
                "source",
                "station_type",
                "metadata_source_table",
                "elevation_lookup_status",
            ]
        )
    )

    out_metadata = out_dir / "ib3w_station_metadata_elevation_v1.csv"
    out_summary = out_dir / "ib3w_station_metadata_elevation_summary_v1.csv"
    out_html = out_dir / "ib3w_station_metadata_elevation_v1.html"

    metadata_df.to_csv(out_metadata, index=False, encoding="utf-8-sig")
    summary_df.to_csv(out_summary, index=False, encoding="utf-8-sig")
    build_html_report(metadata_df, summary_df, out_html)

    total = len(metadata_df)
    db_available = int((metadata_df["elevation_lookup_status"] == "DB_ELEVATION_AVAILABLE").sum()) if total else 0
    need_lookup = int((metadata_df["needs_terrain_lookup"] == "true").sum()) if total else 0

    print("IB3W station metadata elevation cache written")
    print(f"Metadata CSV: {out_metadata}")
    print(f"Summary CSV: {out_summary}")
    print(f"HTML: {out_html}")
    print(f"station_rows: {total}")
    print(f"db_elevation_available_rows: {db_available}")
    print(f"need_terrain_lookup_rows: {need_lookup}")


if __name__ == "__main__":
    main()
