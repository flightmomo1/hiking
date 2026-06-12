from __future__ import annotations

import argparse
import sqlite3
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path
from typing import Any

import pandas as pd


SCHEMA_VERSION = "ib3w_activity_environment_window_adapter_v1"
WEATHER_TABLE = "weather_observations"
GARMIN_TO_UNIX_OFFSET_SEC = 631065600

CONTEXT_VARIABLES = [
    "precipitation_mm",
    "precipitation_10min_mm",
    "precipitation_1hr_mm",
    "temperature_c",
    "relative_humidity_pct",
    "wind_speed_ms",
    "wind_direction_deg",
    "pressure_hpa",
    "visibility_m",
    "weather",
]

NUMERIC_VARIABLES = set(CONTEXT_VARIABLES) - {"weather"}

OUTPUT_COLUMNS = [
    "schema_version",
    "output_case",
    "case_id",
    "activity_id",
    "activity_source_type",
    "activity_source_path",
    "activity_start_time_utc",
    "activity_end_time_utc",
    "activity_duration_min",
    "timestamp_epoch_used",
    "context_variable",
    "context_status",
    "audit_status",
    "weather_db_path",
    "weather_table",
    "station_id",
    "station_name",
    "county_name",
    "town_name",
    "station_latitude",
    "station_longitude",
    "station_elevation_m",
    "nearest_activity_dist_m",
    "station_rank_by_distance",
    "obs_count_total_window",
    "obs_count_nonnull",
    "obs_count_null",
    "obs_count_zero",
    "obs_count_positive",
    "nearest_obs_time_utc",
    "nearest_obs_gap_min",
    "value_min",
    "value_max",
    "value_mean",
    "value_sum",
    "observed_values_available",
    "selection_rule",
    "missingness_reason",
    "zero_fallback_used",
    "context_notes",
]


@dataclass
class ActivityWindow:
    case_id: str
    activity_id: str
    source_type: str
    source_path: Path
    start_time: datetime | None
    end_time: datetime | None
    timestamp_epoch_used: str
    points: list[tuple[float, float]]
    time_status: str

    @property
    def duration_min(self) -> float | str:
        if self.start_time is None or self.end_time is None:
            return ""
        return round((self.end_time - self.start_time).total_seconds() / 60.0, 3)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="IB3W formal activity environment window adapter v1."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--backend-activity-root", type=Path)
    source.add_argument("--gpx", type=Path)
    parser.add_argument("--output-case", required=True)
    parser.add_argument("--case-id", default="")
    parser.add_argument("--activity-id", default="")
    parser.add_argument(
        "--weather-db",
        type=Path,
        default=Path("weather/tw_weather_2026-05-01.sqlite3"),
    )
    parser.add_argument(
        "--out-root",
        type=Path,
        default=Path("outputs/ib3w_activity_environment_window_adapter_v1"),
    )
    parser.add_argument("--bbox-pad-deg", type=float, default=0.20)
    return parser.parse_args()


def utc_iso(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(timezone.utc).isoformat()


def parse_iso_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def garmin_seconds_to_utc(value: float) -> datetime:
    unix_seconds = float(value) + GARMIN_TO_UNIX_OFFSET_SEC
    return datetime.fromtimestamp(unix_seconds, timezone.utc)


def numeric_points(df: pd.DataFrame, lat_col: str, lon_col: str) -> list[tuple[float, float]]:
    lat = pd.to_numeric(df[lat_col], errors="coerce")
    lon = pd.to_numeric(df[lon_col], errors="coerce")
    valid = pd.DataFrame({"lat": lat, "lon": lon}).dropna()
    return list(valid.itertuples(index=False, name=None))


def load_backend_activities(root: Path) -> list[ActivityWindow]:
    if not root.exists():
        raise FileNotFoundError(f"Backend activity root not found: {root}")

    paths = sorted(root.glob("*.csv"))
    if not paths:
        raise FileNotFoundError(f"No backend activity CSV found under: {root}")

    activities = []
    for path in paths:
        df = pd.read_csv(
            path,
            usecols=["activity_id", "case_id", "timestamp_s", "lat", "lon"],
        )
        activity_id = str(df["activity_id"].iloc[0]) if len(df) else path.stem
        case_id = str(df["case_id"].iloc[0]) if len(df) else ""
        timestamps = pd.to_numeric(df["timestamp_s"], errors="coerce")
        timestamps = timestamps[timestamps > 0]

        if timestamps.empty:
            start_time = None
            end_time = None
            time_status = "MISSING_TIMESTAMP"
        else:
            start_time = garmin_seconds_to_utc(float(timestamps.min()))
            end_time = garmin_seconds_to_utc(float(timestamps.max()))
            time_status = "OK"

        activities.append(
            ActivityWindow(
                case_id=case_id,
                activity_id=activity_id,
                source_type="backend_activity_csv",
                source_path=path,
                start_time=start_time,
                end_time=end_time,
                timestamp_epoch_used="garmin_seconds",
                points=numeric_points(df, "lat", "lon"),
                time_status=time_status,
            )
        )

    return activities


def load_gpx_activity(
    path: Path,
    case_id: str,
    activity_id: str,
) -> list[ActivityWindow]:
    if not path.exists():
        raise FileNotFoundError(f"GPX not found: {path}")

    root = ET.parse(path).getroot()
    points = []
    times = []

    for trkpt in root.iter():
        if trkpt.tag.split("}")[-1] != "trkpt":
            continue

        time_node = next(
            (child for child in trkpt if child.tag.split("}")[-1] == "time"),
            None,
        )
        if time_node is None or not time_node.text:
            continue

        dt = parse_iso_datetime(time_node.text)
        if dt is None:
            continue

        try:
            point = (float(trkpt.attrib["lat"]), float(trkpt.attrib["lon"]))
        except (KeyError, ValueError):
            continue

        points.append(point)
        times.append(dt)

    if not times:
        raise RuntimeError(f"No valid GPX trackpoint time found: {path}")

    return [
        ActivityWindow(
            case_id=case_id,
            activity_id=activity_id,
            source_type="gpx",
            source_path=path,
            start_time=min(times),
            end_time=max(times),
            timestamp_epoch_used="explicit_gpx_utc",
            points=points,
            time_status="OK",
        )
    ]


def readonly_connect(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise FileNotFoundError(f"Weather DB not found: {path}")
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    conn.execute("PRAGMA query_only = ON")
    return conn


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table_name}")')}


def weather_db_range(conn: sqlite3.Connection) -> tuple[str, str, int]:
    row = conn.execute(
        f"""
        SELECT MIN(obs_time), MAX(obs_time), COUNT(*)
        FROM "{WEATHER_TABLE}"
        WHERE obs_time IS NOT NULL
        """
    ).fetchone()
    return str(row[0] or ""), str(row[1] or ""), int(row[2] or 0)


def windows_overlap(
    activity: ActivityWindow,
    db_start: str,
    db_end: str,
) -> bool:
    start = parse_iso_datetime(db_start)
    end = parse_iso_datetime(db_end)
    if activity.start_time is None or activity.end_time is None or start is None or end is None:
        return False
    return activity.start_time <= end and activity.end_time >= start


def build_bbox(points: list[tuple[float, float]], pad_deg: float) -> dict[str, float] | None:
    if not points:
        return None
    latitudes = [point[0] for point in points]
    longitudes = [point[1] for point in points]
    return {
        "lat_min": min(latitudes) - pad_deg,
        "lat_max": max(latitudes) + pad_deg,
        "lon_min": min(longitudes) - pad_deg,
        "lon_max": max(longitudes) + pad_deg,
    }


def query_activity_observations(
    conn: sqlite3.Connection,
    activity: ActivityWindow,
    bbox: dict[str, float] | None,
    available_variables: list[str],
) -> pd.DataFrame:
    select_columns = [
        "station_id",
        "station_name",
        "county_name",
        "town_name",
        "latitude",
        "longitude",
        "elevation_m",
        "obs_time",
        *available_variables,
    ]
    sql = f"""
    SELECT {", ".join(f'"{column}"' for column in select_columns)}
    FROM "{WEATHER_TABLE}"
    WHERE obs_time >= ?
      AND obs_time <= ?
    """
    params: list[Any] = [utc_iso(activity.start_time), utc_iso(activity.end_time)]

    if bbox is not None:
        sql += """
          AND latitude BETWEEN ? AND ?
          AND longitude BETWEEN ? AND ?
        """
        params.extend(
            [
                bbox["lat_min"],
                bbox["lat_max"],
                bbox["lon_min"],
                bbox["lon_max"],
            ]
        )

    sql += " ORDER BY station_id, obs_time"
    return pd.read_sql_query(sql, conn, params=params)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_m = 6371000.0
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)
    a = (
        sin(delta_phi / 2) ** 2
        + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
    )
    return radius_m * 2 * atan2(sqrt(a), sqrt(1 - a))


def nearest_activity_distance_m(
    station_latitude: float | None,
    station_longitude: float | None,
    points: list[tuple[float, float]],
) -> float | str:
    if station_latitude is None or station_longitude is None or not points:
        return ""
    distance = min(
        haversine_m(station_latitude, station_longitude, lat, lon)
        for lat, lon in points
    )
    return round(distance, 1)


def first_nonblank(series: pd.Series) -> Any:
    for value in series:
        if pd.notna(value) and str(value).strip():
            return value
    return ""


def as_float_or_none(value: Any) -> float | None:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def nearest_gap_min(activity: ActivityWindow, obs_time: datetime) -> float:
    if activity.start_time is None or activity.end_time is None:
        return float("nan")
    if activity.start_time <= obs_time <= activity.end_time:
        return 0.0
    return round(
        min(
            abs((obs_time - activity.start_time).total_seconds()),
            abs((obs_time - activity.end_time).total_seconds()),
        )
        / 60.0,
        3,
    )


def base_output_row(
    output_case: str,
    activity: ActivityWindow,
    weather_db: Path,
    variable: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "output_case": output_case,
        "case_id": activity.case_id,
        "activity_id": activity.activity_id,
        "activity_source_type": activity.source_type,
        "activity_source_path": str(activity.source_path),
        "activity_start_time_utc": utc_iso(activity.start_time),
        "activity_end_time_utc": utc_iso(activity.end_time),
        "activity_duration_min": activity.duration_min,
        "timestamp_epoch_used": activity.timestamp_epoch_used,
        "context_variable": variable,
        "weather_db_path": str(weather_db),
        "weather_table": WEATHER_TABLE,
        "zero_fallback_used": False,
    }


def unavailable_row(
    output_case: str,
    activity: ActivityWindow,
    weather_db: Path,
    variable: str,
    context_status: str,
    audit_status: str,
    missingness_reason: str,
) -> dict[str, Any]:
    row = base_output_row(output_case, activity, weather_db, variable)
    row.update(
        {
            "context_status": context_status,
            "audit_status": audit_status,
            "station_id": "",
            "station_name": "",
            "county_name": "",
            "town_name": "",
            "station_latitude": "",
            "station_longitude": "",
            "station_elevation_m": "",
            "nearest_activity_dist_m": "",
            "station_rank_by_distance": "",
            "obs_count_total_window": 0,
            "obs_count_nonnull": 0,
            "obs_count_null": 0,
            "obs_count_zero": 0,
            "obs_count_positive": 0,
            "nearest_obs_time_utc": "",
            "nearest_obs_gap_min": "",
            "value_min": "",
            "value_max": "",
            "value_mean": "",
            "value_sum": "",
            "observed_values_available": False,
            "selection_rule": "exact_activity_window; no station synthesized when evidence is unavailable",
            "missingness_reason": missingness_reason,
            "context_notes": "Missing weather remains missing; no zero or calm fallback is created.",
        }
    )
    return row


def station_metadata(
    group: pd.DataFrame,
    activity: ActivityWindow,
) -> dict[str, Any]:
    latitude = as_float_or_none(first_nonblank(group["latitude"]))
    longitude = as_float_or_none(first_nonblank(group["longitude"]))
    elevation = as_float_or_none(first_nonblank(group["elevation_m"]))
    return {
        "station_id": str(first_nonblank(group["station_id"])),
        "station_name": str(first_nonblank(group["station_name"])),
        "county_name": str(first_nonblank(group["county_name"])),
        "town_name": str(first_nonblank(group["town_name"])),
        "station_latitude": latitude if latitude is not None else "",
        "station_longitude": longitude if longitude is not None else "",
        "station_elevation_m": elevation if elevation is not None else "",
        "nearest_activity_dist_m": nearest_activity_distance_m(
            latitude,
            longitude,
            activity.points,
        ),
    }


def variable_row(
    output_case: str,
    activity: ActivityWindow,
    weather_db: Path,
    station_group: pd.DataFrame,
    metadata: dict[str, Any],
    station_rank: int,
    variable: str,
) -> dict[str, Any]:
    row = base_output_row(output_case, activity, weather_db, variable)
    raw_values = station_group[variable]

    if variable in NUMERIC_VARIABLES:
        values = pd.to_numeric(raw_values, errors="coerce")
        valid_mask = values.notna()
        valid_values = values[valid_mask]
        zero_count = int((valid_values == 0).sum())
        positive_count = int((valid_values > 0).sum())
    else:
        text = raw_values.astype("string").str.strip()
        valid_mask = text.notna() & text.ne("")
        valid_values = text[valid_mask]
        zero_count = 0
        positive_count = 0

    nonnull_count = int(valid_mask.sum())
    null_count = int(len(station_group) - nonnull_count)
    observed = nonnull_count > 0

    if observed:
        valid_obs_times = pd.to_datetime(
            station_group.loc[valid_mask, "obs_time"],
            errors="coerce",
            utc=True,
        ).dropna()
        nearest_time = min(
            (value.to_pydatetime() for value in valid_obs_times),
            key=lambda value: nearest_gap_min(activity, value),
        )
        context_status = "OBSERVED"
        audit_status = "OBSERVED_IN_ACTIVITY_WINDOW"
        missingness_reason = ""
    else:
        nearest_time = None
        context_status = "MISSING"
        audit_status = "NULL_VALUE_ONLY"
        missingness_reason = "VARIABLE_VALUES_NULL_OR_BLANK_IN_ACTIVITY_WINDOW"

    if observed and variable in NUMERIC_VARIABLES:
        value_min: Any = float(valid_values.min())
        value_max: Any = float(valid_values.max())
        value_mean: Any = float(valid_values.mean())
        value_sum: Any = float(valid_values.sum())
    else:
        value_min = ""
        value_max = ""
        value_mean = ""
        value_sum = ""

    notes = (
        "Raw zero values are retained as observed evidence; zero is never synthesized."
        if observed and zero_count > 0
        else "Exact activity-window station-variable evidence; no imputation or weather fusion."
    )
    if variable == "weather" and observed:
        notes = "Nonblank raw weather text is observed evidence; numeric value statistics are not applicable."

    row.update(metadata)
    row.update(
        {
            "station_rank_by_distance": station_rank,
            "context_status": context_status,
            "audit_status": audit_status,
            "obs_count_total_window": int(len(station_group)),
            "obs_count_nonnull": nonnull_count,
            "obs_count_null": null_count,
            "obs_count_zero": zero_count,
            "obs_count_positive": positive_count,
            "nearest_obs_time_utc": utc_iso(nearest_time),
            "nearest_obs_gap_min": (
                nearest_gap_min(activity, nearest_time)
                if nearest_time is not None
                else ""
            ),
            "value_min": value_min,
            "value_max": value_max,
            "value_mean": value_mean,
            "value_sum": value_sum,
            "observed_values_available": observed,
            "selection_rule": (
                "stations_with_observations_in_exact_activity_window_and_activity_bbox;"
                " rank_by_nearest_activity_trackpoint_distance"
            ),
            "missingness_reason": missingness_reason,
            "context_notes": notes,
        }
    )
    return row


def build_rows(
    output_case: str,
    activities: list[ActivityWindow],
    weather_db: Path,
    conn: sqlite3.Connection,
    bbox_pad_deg: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    table_found = table_exists(conn, WEATHER_TABLE)
    columns = table_columns(conn, WEATHER_TABLE) if table_found else set()
    db_start = ""
    db_end = ""
    db_count = 0

    if table_found:
        db_start, db_end, db_count = weather_db_range(conn)

    available_variables = [variable for variable in CONTEXT_VARIABLES if variable in columns]
    missing_variables = [variable for variable in CONTEXT_VARIABLES if variable not in columns]

    for activity in activities:
        if activity.time_status != "OK":
            for variable in CONTEXT_VARIABLES:
                rows.append(
                    unavailable_row(
                        output_case,
                        activity,
                        weather_db,
                        variable,
                        "MISSING",
                        "ACTIVITY_TIMESTAMP_MISSING",
                        "ACTIVITY_TIMESTAMP_MISSING",
                    )
                )
            continue

        if not table_found:
            for variable in CONTEXT_VARIABLES:
                rows.append(
                    unavailable_row(
                        output_case,
                        activity,
                        weather_db,
                        variable,
                        "NO_SOURCE",
                        "WEATHER_TABLE_NOT_FOUND",
                        "WEATHER_OBSERVATION_TABLE_NOT_FOUND",
                    )
                )
            continue

        for variable in missing_variables:
            rows.append(
                unavailable_row(
                    output_case,
                    activity,
                    weather_db,
                    variable,
                    "NO_VARIABLE",
                    "VARIABLE_COLUMN_NOT_FOUND",
                    "VARIABLE_COLUMN_NOT_FOUND",
                )
            )

        if not windows_overlap(activity, db_start, db_end):
            for variable in available_variables:
                rows.append(
                    unavailable_row(
                        output_case,
                        activity,
                        weather_db,
                        variable,
                        "MISSING",
                        "ACTIVITY_WINDOW_OUTSIDE_WEATHER_OBSERVATION_RANGE",
                        "ACTIVITY_WINDOW_OUTSIDE_WEATHER_OBSERVATION_RANGE",
                    )
                )
            continue

        bbox = build_bbox(activity.points, bbox_pad_deg)
        observations = query_activity_observations(
            conn,
            activity,
            bbox,
            available_variables,
        )

        if observations.empty:
            for variable in available_variables:
                rows.append(
                    unavailable_row(
                        output_case,
                        activity,
                        weather_db,
                        variable,
                        "MISSING",
                        "NO_OBSERVATIONS_IN_ACTIVITY_WINDOW_AND_BBOX",
                        "NO_OBSERVATIONS_IN_ACTIVITY_WINDOW_AND_BBOX",
                    )
                )
            continue

        station_groups = []
        for _, station_group in observations.groupby("station_id", sort=True, dropna=False):
            metadata = station_metadata(station_group, activity)
            station_groups.append((metadata, station_group))

        station_groups.sort(
            key=lambda item: (
                float(item[0]["nearest_activity_dist_m"])
                if item[0]["nearest_activity_dist_m"] != ""
                else float("inf"),
                item[0]["station_id"],
            )
        )

        for station_rank, (metadata, station_group) in enumerate(station_groups, start=1):
            for variable in available_variables:
                rows.append(
                    variable_row(
                        output_case,
                        activity,
                        weather_db,
                        station_group,
                        metadata,
                        station_rank,
                        variable,
                    )
                )

    metadata = {
        "weather_table_found": table_found,
        "weather_db_obs_start_utc": db_start,
        "weather_db_obs_end_utc": db_end,
        "weather_db_obs_count": db_count,
        "weather_variable_columns_found": "|".join(available_variables),
        "weather_variable_columns_missing": "|".join(missing_variables),
    }
    return rows, metadata


def build_summary(
    output_case: str,
    activities: list[ActivityWindow],
    output: pd.DataFrame,
    weather_db: Path,
    db_metadata: dict[str, Any],
) -> pd.DataFrame:
    statuses = output["context_status"].value_counts().to_dict()
    audits = output["audit_status"].value_counts().to_dict()
    station_rows = output[output["station_id"].astype(str).str.strip().ne("")]
    observed_zero_rows = int(
        (
            (output["context_status"] == "OBSERVED")
            & (pd.to_numeric(output["obs_count_zero"], errors="coerce").fillna(0) > 0)
        ).sum()
    )
    nearest_stations = (
        station_rows.sort_values(["activity_id", "station_rank_by_distance"])
        .drop_duplicates(["activity_id", "station_id"])
        ["station_name"]
        .astype(str)
        .tolist()
    )

    return pd.DataFrame(
        [
            {
                "schema_version": SCHEMA_VERSION,
                "output_case": output_case,
                "activity_source_type": (
                    activities[0].source_type if activities else ""
                ),
                "activity_count": len(activities),
                "activity_start_min_utc": min(
                    (utc_iso(activity.start_time) for activity in activities if activity.start_time),
                    default="",
                ),
                "activity_end_max_utc": max(
                    (utc_iso(activity.end_time) for activity in activities if activity.end_time),
                    default="",
                ),
                "timestamp_epoch_used": "|".join(
                    sorted({activity.timestamp_epoch_used for activity in activities})
                ),
                "weather_db_path": str(weather_db),
                "weather_table": WEATHER_TABLE,
                **db_metadata,
                "adapter_output_rows": len(output),
                "station_count": int(station_rows["station_id"].nunique()),
                "context_status_observed": int(statuses.get("OBSERVED", 0)),
                "context_status_missing": int(statuses.get("MISSING", 0)),
                "context_status_no_source": int(statuses.get("NO_SOURCE", 0)),
                "context_status_no_variable": int(statuses.get("NO_VARIABLE", 0)),
                "audit_activity_window_outside_weather_range": int(
                    audits.get("ACTIVITY_WINDOW_OUTSIDE_WEATHER_OBSERVATION_RANGE", 0)
                ),
                "audit_observed_in_activity_window": int(
                    audits.get("OBSERVED_IN_ACTIVITY_WINDOW", 0)
                ),
                "audit_null_value_only": int(audits.get("NULL_VALUE_ONLY", 0)),
                "observed_zero_rows": observed_zero_rows,
                "nearest_station_names": "|".join(nearest_stations[:20]),
                "zero_fallback_used": False,
                "adapter_policy": (
                    "exact_activity_window; missing_remains_missing; "
                    "observed_zero_only_if_raw_observation_is_zero; no fusion; no risk adjustment"
                ),
            }
        ]
    )


def main() -> None:
    args = parse_args()
    weather_db = args.weather_db
    out_dir = args.out_root / args.output_case
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.backend_activity_root:
        activities = load_backend_activities(args.backend_activity_root)
    else:
        case_id = args.case_id or args.output_case
        activity_id = args.activity_id or args.output_case
        activities = load_gpx_activity(args.gpx, case_id, activity_id)

    conn = readonly_connect(weather_db)
    try:
        rows, db_metadata = build_rows(
            args.output_case,
            activities,
            weather_db,
            conn,
            args.bbox_pad_deg,
        )
    finally:
        conn.close()

    output = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    summary = build_summary(
        args.output_case,
        activities,
        output,
        weather_db,
        db_metadata,
    )

    output_csv = out_dir / "activity_environment_window_adapter_output.csv"
    summary_csv = out_dir / "activity_environment_window_adapter_summary.csv"
    output.to_csv(output_csv, index=False, encoding="utf-8-sig")
    summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")

    print("IB3W activity environment window adapter v1 written")
    print("output_csv:", output_csv)
    print("summary_csv:", summary_csv)
    print("context_status_distribution:")
    print(output["context_status"].value_counts(dropna=False).to_string())
    print("audit_status_distribution:")
    print(output["audit_status"].value_counts(dropna=False).to_string())
    print()
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
