from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "ib3w_codis_historical_weather_multistation_ingest_v1"
SOURCE_TYPE = "OBSERVED_HISTORICAL_CODIS"
DEFAULT_INPUT_DIR = Path("weather/codis")
DEFAULT_OUT_DIR = Path(
    "outputs/ib3w_codis_historical_weather_multistation_ingest_v1"
)

STATIONS = {
    "466910": {
        "station_name": "鞍部",
        "station_role": "PRIMARY_MOUNTAIN_RIDGE",
    },
    "C0AC40": {
        "station_name": "大屯山",
        "station_role": "PRIMARY_MOUNTAIN_RIDGE_BACKUP",
    },
    "466930": {
        "station_name": "竹子湖",
        "station_role": "MOUNTAIN_AREA_BACKGROUND",
    },
    "C0AH40": {
        "station_name": "平等",
        "station_role": "LOW_TO_MID_ELEVATION_BACKUP",
    },
}

FIELD_MAP = {
    "Temperature": "temperature_c",
    "RH": "relative_humidity_pct",
    "WS": "wind_speed_mps",
    "WD": "wind_direction_deg",
    "WSGust": "wind_gust_mps",
    "Precp": "precipitation_mm",
    "SunShine": "sunshine_hour",
    "GloblRad": "global_radiation_mj_m2",
    "UVI": "uvi",
    "Cloud Amount Sat": "cloud_amount_0_10",
}

MISSING_TOKENS = {"", "/", "X", "T", "...", "NA", "N/A", "NULL", "-"}
FILENAME_RE = re.compile(
    r"^(?P<station_id>466910|C0AC40|466930|C0AH40)-"
    r"(?P<date>\d{4}-\d{2}-\d{2})\.csv$",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize multiple CODiS historical hourly station CSV files."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def discover_files(input_dir: Path) -> list[Path]:
    if not input_dir.exists():
        raise FileNotFoundError(f"CODiS input directory not found: {input_dir}")
    files: list[Path] = []
    for station_id in STATIONS:
        files.extend(input_dir.glob(f"{station_id}-*.csv"))
    return sorted(set(files), key=lambda path: path.name)


def parse_filename(path: Path) -> tuple[str, date]:
    match = FILENAME_RE.match(path.name)
    if not match:
        raise ValueError(f"Malformed CODiS filename: {path.name}")
    station_id = match.group("station_id").upper()
    observation_date = date.fromisoformat(match.group("date"))
    return station_id, observation_date


def read_codis_file(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 3:
        raise ValueError("file does not contain bilingual headers and data rows")
    chinese_header, field_header = rows[0], rows[1]
    if len(chinese_header) != len(field_header):
        raise ValueError("bilingual header column counts differ")
    if not field_header or field_header[0] != "ObsTime":
        raise ValueError("first normalized header is not ObsTime")
    data_rows = rows[2:]
    if any(len(row) != len(field_header) for row in data_rows):
        raise ValueError("data row column count differs from header")
    return field_header, data_rows


def parse_numeric(raw_value: Any) -> tuple[str, bool, str]:
    text = str(raw_value or "").strip()
    if text.upper() in MISSING_TOKENS:
        return "", True, text
    try:
        return str(float(text)), False, ""
    except ValueError:
        return "", True, text


def observation_timestamp(observation_date: date, hour_text: str) -> datetime:
    hour = int(hour_text)
    if hour < 1 or hour > 24:
        raise ValueError(f"observation hour must be 01-24: {hour_text}")
    local_tz = timezone(timedelta(hours=8))
    if hour == 24:
        return datetime.combine(
            observation_date + timedelta(days=1), time(0), local_tz
        )
    return datetime.combine(observation_date, time(hour), local_tz)


def normalized_fieldnames() -> list[str]:
    fields = [
        "schema_version",
        "source_type",
        "source_file",
        "source_row_number",
        "station_id",
        "station_name",
        "station_role",
        "observation_date_local",
        "observation_hour_local",
        "observation_time_local",
    ]
    for output_field in FIELD_MAP.values():
        fields.extend(
            [
                output_field,
                f"{output_field}_missing",
                f"{output_field}_missing_token",
                f"{output_field}_source_column_present",
            ]
        )
    fields.extend(
        [
            "any_required_value_missing",
            "missing_variable_count",
            "missing_variables",
            "source_confidence",
            "zero_fallback_used",
            "scoring_authorized",
            "production_scoring_authorized",
        ]
    )
    return fields


def normalize_file(
    path: Path,
    station_id: str,
    observation_date: date,
    field_header: list[str],
    data_rows: list[list[str]],
) -> list[dict[str, Any]]:
    field_indexes = {field: index for index, field in enumerate(field_header)}
    if "ObsTime" not in field_indexes:
        raise ValueError("required ObsTime field is missing")

    station = STATIONS[station_id]
    normalized: list[dict[str, Any]] = []
    for source_row_number, source_row in enumerate(data_rows, start=3):
        hour_text = source_row[field_indexes["ObsTime"]].strip()
        timestamp = observation_timestamp(observation_date, hour_text)
        output: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "source_type": SOURCE_TYPE,
            "source_file": str(path),
            "source_row_number": source_row_number,
            "station_id": station_id,
            "station_name": station["station_name"],
            "station_role": station["station_role"],
            "observation_date_local": observation_date.isoformat(),
            "observation_hour_local": hour_text.zfill(2),
            "observation_time_local": timestamp.isoformat(),
            "source_confidence": "HIGH",
            "zero_fallback_used": "False",
            "scoring_authorized": "False",
            "production_scoring_authorized": "False",
        }

        missing_variables: list[str] = []
        for source_field, output_field in FIELD_MAP.items():
            source_present = source_field in field_indexes
            if source_present:
                raw_value = source_row[field_indexes[source_field]]
                value, missing, missing_token = parse_numeric(raw_value)
            else:
                value, missing, missing_token = "", True, "SOURCE_COLUMN_MISSING"
            output[output_field] = value
            output[f"{output_field}_missing"] = str(missing)
            output[f"{output_field}_missing_token"] = missing_token
            output[f"{output_field}_source_column_present"] = str(source_present)
            if missing:
                missing_variables.append(output_field)

        output["any_required_value_missing"] = str(bool(missing_variables))
        output["missing_variable_count"] = len(missing_variables)
        output["missing_variables"] = "|".join(missing_variables)
        normalized.append(output)
    return normalized


def station_date_row(
    station_id: str,
    observation_date: date,
    source_file: Path | None,
    normalized_rows: list[dict[str, Any]],
    file_status: str,
    issue: str = "",
) -> dict[str, Any]:
    station = STATIONS[station_id]
    hour_counts = Counter(
        str(row["observation_hour_local"]) for row in normalized_rows
    )
    missing_counts = {
        field: sum(
            1
            for row in normalized_rows
            if row[f"{field}_missing"] == "True"
        )
        for field in FIELD_MAP.values()
    }
    complete = (
        file_status == "PRESENT"
        and len(normalized_rows) == 24
        and len(hour_counts) == 24
        and not any(count > 1 for count in hour_counts.values())
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "station_id": station_id,
        "station_name": station["station_name"],
        "station_role": station["station_role"],
        "observation_date_local": observation_date.isoformat(),
        "source_file": str(source_file) if source_file else "",
        "file_status": file_status,
        "normalized_row_count": len(normalized_rows),
        "unique_observation_hour_count": len(hour_counts),
        "duplicate_observation_hours": "|".join(
            sorted(hour for hour, count in hour_counts.items() if count > 1)
        ),
        "station_date_complete": str(complete),
        "total_missing_value_count": sum(missing_counts.values()),
        **{f"{field}_missing_count": count for field, count in missing_counts.items()},
        "issue": issue,
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    discovered = discover_files(args.input_dir)

    parsed_files: dict[tuple[str, date], Path] = {}
    malformed_files: list[tuple[Path, str]] = []
    for path in discovered:
        try:
            station_id, observation_date = parse_filename(path)
            parsed_files[(station_id, observation_date)] = path
        except Exception as exc:
            malformed_files.append((path, str(exc)))

    observed_dates = sorted({key[1] for key in parsed_files})
    expected_keys = [
        (station_id, observation_date)
        for station_id in STATIONS
        for observation_date in observed_dates
    ]

    normalized_rows: list[dict[str, Any]] = []
    station_date_rows: list[dict[str, Any]] = []
    malformed_count = len(malformed_files)

    for station_id, observation_date in expected_keys:
        path = parsed_files.get((station_id, observation_date))
        if path is None:
            station_date_rows.append(
                station_date_row(
                    station_id,
                    observation_date,
                    None,
                    [],
                    "MISSING_FILE",
                    "Expected station-date CSV is missing.",
                )
            )
            continue
        try:
            field_header, data_rows = read_codis_file(path)
            rows = normalize_file(
                path, station_id, observation_date, field_header, data_rows
            )
            normalized_rows.extend(rows)
            station_date_rows.append(
                station_date_row(
                    station_id,
                    observation_date,
                    path,
                    rows,
                    "PRESENT",
                )
            )
        except Exception as exc:
            malformed_count += 1
            station_date_rows.append(
                station_date_row(
                    station_id,
                    observation_date,
                    path,
                    [],
                    "MALFORMED_FILE",
                    str(exc),
                )
            )

    missing_file_count = sum(
        1 for row in station_date_rows if row["file_status"] == "MISSING_FILE"
    )
    incomplete_count = sum(
        1
        for row in station_date_rows
        if row["file_status"] == "PRESENT"
        and row["station_date_complete"] != "True"
    )
    expected_row_count = len(expected_keys) * 24
    total_missing_value_count = sum(
        int(row["missing_variable_count"]) for row in normalized_rows
    )
    zero_fallback_true_count = sum(
        1 for row in normalized_rows if row["zero_fallback_used"] == "True"
    )
    scoring_authorized_count = sum(
        1 for row in normalized_rows if row["scoring_authorized"] == "True"
    )
    production_authorized_count = sum(
        1
        for row in normalized_rows
        if row["production_scoring_authorized"] == "True"
    )

    passed = (
        len(discovered) == len(expected_keys)
        and missing_file_count == 0
        and malformed_count == 0
        and incomplete_count == 0
        and len(normalized_rows) == expected_row_count
        and zero_fallback_true_count == 0
        and scoring_authorized_count == 0
        and production_authorized_count == 0
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "input_directory": str(args.input_dir),
        "input_file_count": len(discovered),
        "station_count": len(STATIONS),
        "unique_observation_date_count": len(observed_dates),
        "station_date_count": len(expected_keys),
        "observed_station_date_count": len(parsed_files),
        "expected_row_count": expected_row_count,
        "normalized_row_count": len(normalized_rows),
        "missing_file_count": missing_file_count,
        "malformed_file_count": malformed_count,
        "incomplete_station_date_count": incomplete_count,
        "total_missing_value_count": total_missing_value_count,
        "zero_fallback_true_count": zero_fallback_true_count,
        "scoring_authorized_count": scoring_authorized_count,
        "production_scoring_authorized_count": production_authorized_count,
        "ingest_conclusion": "PASS" if passed else "FAIL",
    }

    normalized_csv = (
        args.out_dir / "codis_hourly_observations_normalized_multistation.csv"
    )
    summary_csv = (
        args.out_dir / "codis_hourly_observations_multistation_summary.csv"
    )
    station_date_csv = (
        args.out_dir / "codis_hourly_observations_station_date_summary.csv"
    )
    station_date_fields = list(station_date_rows[0]) if station_date_rows else []

    write_csv(normalized_csv, normalized_rows, normalized_fieldnames())
    write_csv(summary_csv, [summary], list(summary))
    write_csv(station_date_csv, station_date_rows, station_date_fields)

    print("IB3W CODiS historical weather multistation ingest v1")
    print(f"normalized_csv: {normalized_csv}")
    print(f"summary_csv: {summary_csv}")
    print(f"station_date_csv: {station_date_csv}")
    print("summary:")
    for field, value in summary.items():
        print(f"{field}: {value}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
