from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import sqlite3
import pandas as pd


CASE_ID = "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b"

ACTIVITY_ROOT = Path(
    "outputs/ib3a_rc_backend_activity_enriched_v1l2_osm_radar_evidence_qixing_lengshuikeng_full26"
)

WEATHER_DB = Path("weather/tw_weather_2026-05-01.sqlite3")

OUT_DIR = Path("outputs/ib3w_activity_weather_observation_availability_audit_v1") / CASE_ID
OUT_AUDIT_CSV = OUT_DIR / "activity_weather_observation_availability_audit.csv"
OUT_SUMMARY_CSV = OUT_DIR / "activity_weather_observation_availability_summary.csv"

GARMIN_TO_UNIX_OFFSET = 631065600


def utc_iso_from_garmin_seconds(value: int) -> str:
    unix_ts = int(value) + GARMIN_TO_UNIX_OFFSET
    return datetime.fromtimestamp(unix_ts, timezone.utc).isoformat()


def parse_iso_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def get_weather_db_range(conn: sqlite3.Connection) -> dict:
    if not table_exists(conn, "weather_observations"):
        return {
            "weather_observation_table_found": False,
            "weather_db_obs_start_utc": "",
            "weather_db_obs_end_utc": "",
            "weather_db_obs_count": 0,
        }

    row = conn.execute(
        """
        SELECT
          MIN(obs_time) AS min_time,
          MAX(obs_time) AS max_time,
          COUNT(*) AS n
        FROM weather_observations
        WHERE obs_time IS NOT NULL
        """
    ).fetchone()

    return {
        "weather_observation_table_found": True,
        "weather_db_obs_start_utc": row[0] or "",
        "weather_db_obs_end_utc": row[1] or "",
        "weather_db_obs_count": int(row[2] or 0),
    }


def count_weather_observations_in_window(
    conn: sqlite3.Connection,
    start_utc: str,
    end_utc: str,
) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM weather_observations
        WHERE obs_time IS NOT NULL
          AND obs_time >= ?
          AND obs_time <= ?
        """,
        (start_utc, end_utc),
    ).fetchone()
    return int(row[0] or 0)


def build_activity_windows() -> list[dict]:
    rows: list[dict] = []

    csv_paths = sorted(ACTIVITY_ROOT.glob("*.csv"))
    if not csv_paths:
        raise FileNotFoundError(f"No activity CSV found under: {ACTIVITY_ROOT}")

    for path in csv_paths:
        df = pd.read_csv(
            path,
            usecols=["activity_id", "case_id", "timestamp_s", "elapsed_sec"],
        )

        ts = pd.to_numeric(df["timestamp_s"], errors="coerce")
        ts = ts[ts > 0]

        activity_id = str(df["activity_id"].iloc[0]) if len(df) else ""
        case_id = str(df["case_id"].iloc[0]) if len(df) else ""

        if ts.empty:
            rows.append(
                {
                    "activity_csv": path.name,
                    "activity_id": activity_id,
                    "case_id": case_id,
                    "activity_rows": len(df),
                    "activity_timestamp_epoch": "garmin_seconds",
                    "activity_start_utc": "",
                    "activity_end_utc": "",
                    "activity_duration_min": "",
                    "activity_time_status": "MISSING_TIMESTAMP",
                }
            )
            continue

        min_ts = int(ts.min())
        max_ts = int(ts.max())

        rows.append(
            {
                "activity_csv": path.name,
                "activity_id": activity_id,
                "case_id": case_id,
                "activity_rows": len(df),
                "activity_timestamp_epoch": "garmin_seconds",
                "activity_start_utc": utc_iso_from_garmin_seconds(min_ts),
                "activity_end_utc": utc_iso_from_garmin_seconds(max_ts),
                "activity_duration_min": round((max_ts - min_ts) / 60.0, 2),
                "activity_time_status": "OK",
            }
        )

    return rows


def windows_overlap(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    a0 = parse_iso_datetime(a_start)
    a1 = parse_iso_datetime(a_end)
    b0 = parse_iso_datetime(b_start)
    b1 = parse_iso_datetime(b_end)

    if not all([a0, a1, b0, b1]):
        return False

    return a0 <= b1 and a1 >= b0


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    weather_db_found = WEATHER_DB.exists()
    weather_range = {
        "weather_observation_table_found": False,
        "weather_db_obs_start_utc": "",
        "weather_db_obs_end_utc": "",
        "weather_db_obs_count": 0,
    }

    conn = None
    if weather_db_found:
        conn = sqlite3.connect(WEATHER_DB)
        weather_range = get_weather_db_range(conn)

    activity_rows = build_activity_windows()
    audit_rows: list[dict] = []

    for row in activity_rows:
        activity_start = row["activity_start_utc"]
        activity_end = row["activity_end_utc"]

        overlap = False
        matching_count = 0
        missingness_reason = ""
        weather_data_status = ""

        if row["activity_time_status"] != "OK":
            weather_data_status = "NO_MATCHING_WEATHER_OBSERVATIONS"
            missingness_reason = "ACTIVITY_TIMESTAMP_MISSING"
        elif not weather_db_found:
            weather_data_status = "NO_MATCHING_WEATHER_OBSERVATIONS"
            missingness_reason = "WEATHER_DB_NOT_FOUND"
        elif not weather_range["weather_observation_table_found"]:
            weather_data_status = "NO_MATCHING_WEATHER_OBSERVATIONS"
            missingness_reason = "WEATHER_OBSERVATION_TABLE_NOT_FOUND"
        elif weather_range["weather_db_obs_count"] <= 0:
            weather_data_status = "NO_MATCHING_WEATHER_OBSERVATIONS"
            missingness_reason = "WEATHER_OBSERVATION_TABLE_EMPTY"
        else:
            overlap = windows_overlap(
                activity_start,
                activity_end,
                weather_range["weather_db_obs_start_utc"],
                weather_range["weather_db_obs_end_utc"],
            )

            if overlap and conn is not None:
                matching_count = count_weather_observations_in_window(
                    conn,
                    activity_start,
                    activity_end,
                )

            if matching_count > 0:
                weather_data_status = "MATCHING_WEATHER_OBSERVATIONS_FOUND"
                missingness_reason = ""
            elif not overlap:
                weather_data_status = "NO_MATCHING_WEATHER_OBSERVATIONS"
                missingness_reason = "ACTIVITY_WINDOW_OUTSIDE_WEATHER_OBSERVATION_RANGE"
            else:
                weather_data_status = "NO_MATCHING_WEATHER_OBSERVATIONS"
                missingness_reason = "NO_OBSERVATIONS_WITHIN_ACTIVITY_WINDOW"

        audit_rows.append(
            {
                **row,
                "weather_db_path": str(WEATHER_DB),
                "weather_db_found": bool(weather_db_found),
                "weather_observation_table_found": bool(
                    weather_range["weather_observation_table_found"]
                ),
                "weather_db_obs_start_utc": weather_range["weather_db_obs_start_utc"],
                "weather_db_obs_end_utc": weather_range["weather_db_obs_end_utc"],
                "weather_db_obs_count": weather_range["weather_db_obs_count"],
                "activity_window_overlaps_weather_db": bool(overlap),
                "matching_weather_obs_count": int(matching_count),
                "weather_data_status": weather_data_status,
                "missingness_reason": missingness_reason,
                "zero_fallback_used": False,
                "audit_policy": "missing_remains_missing; observed_zero_only_if_raw_observation_is_zero",
            }
        )

    if conn is not None:
        conn.close()

    audit = pd.DataFrame(audit_rows)
    audit.to_csv(OUT_AUDIT_CSV, index=False, encoding="utf-8-sig")

    summary = pd.DataFrame(
        [
            {
                "case_id": CASE_ID,
                "activity_input_root": str(ACTIVITY_ROOT),
                "activity_count": len(audit),
                "activity_timestamp_epoch": "garmin_seconds",
                "garmin_to_unix_offset_sec": GARMIN_TO_UNIX_OFFSET,
                "activity_start_min_utc": audit["activity_start_utc"].min(),
                "activity_end_max_utc": audit["activity_end_utc"].max(),
                "weather_db_path": str(WEATHER_DB),
                "weather_db_found": bool(weather_db_found),
                "weather_observation_table_found": bool(
                    weather_range["weather_observation_table_found"]
                ),
                "weather_db_obs_start_utc": weather_range["weather_db_obs_start_utc"],
                "weather_db_obs_end_utc": weather_range["weather_db_obs_end_utc"],
                "weather_db_obs_count": weather_range["weather_db_obs_count"],
                "activity_windows_overlapping_weather_db_n": int(
                    audit["activity_window_overlaps_weather_db"].sum()
                ),
                "activities_with_matching_weather_obs_n": int(
                    (audit["matching_weather_obs_count"] > 0).sum()
                ),
                "activities_without_matching_weather_obs_n": int(
                    (audit["matching_weather_obs_count"] == 0).sum()
                ),
                "dominant_weather_data_status": (
                    audit["weather_data_status"].mode().iloc[0]
                    if len(audit)
                    else ""
                ),
                "dominant_missingness_reason": (
                    audit["missingness_reason"].mode().iloc[0]
                    if len(audit)
                    else ""
                ),
                "zero_fallback_used": False,
                "audit_conclusion": (
                    "No activity windows overlap the weather observation range. "
                    "Weather values are not imputed and missing is not converted to zero."
                ),
            }
        ]
    )

    summary.to_csv(OUT_SUMMARY_CSV, index=False, encoding="utf-8-sig")

    print("wrote:", OUT_AUDIT_CSV)
    print("wrote:", OUT_SUMMARY_CSV)
    print()
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
