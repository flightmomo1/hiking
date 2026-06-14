from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "ib3w_codis_historical_weather_ingest_v1"
STATION_ID = "466930"
STATION_NAME = "竹子湖"
OBSERVATION_DATE = date(2026, 4, 11)
SOURCE_TYPE = "OBSERVED_HISTORICAL_CODIS"

DEFAULT_INPUT = Path("inputs/weather/codis/466930-2026-04-11.csv")
LEGACY_INPUT = Path("weather/codis/466930-2026-04-11.csv")
DEFAULT_OUT_DIR = Path("outputs/ib3w_codis_historical_weather_ingest_v1")

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize one CODiS historical hourly weather CSV for IB3W evidence."
    )
    parser.add_argument("--input-csv", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def resolve_input(path: Path) -> tuple[Path, bool]:
    if path.exists():
        return path, False
    if path == DEFAULT_INPUT and LEGACY_INPUT.exists():
        return LEGACY_INPUT, True
    raise FileNotFoundError(f"CODiS input CSV not found: {path}")


def read_codis_rows(path: Path) -> tuple[list[str], list[str], list[list[str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 3:
        raise ValueError(f"CODiS CSV must contain two headers and data rows: {path}")

    chinese_header = rows[0]
    field_header = rows[1]
    if len(chinese_header) != len(field_header):
        raise ValueError("CODiS bilingual header column counts differ")
    if field_header[0] != "ObsTime":
        raise ValueError(f"Expected ObsTime as first CODiS field, got: {field_header[0]}")

    data_rows = rows[2:]
    bad_width = [
        index + 3
        for index, row in enumerate(data_rows)
        if len(row) != len(field_header)
    ]
    if bad_width:
        raise ValueError(f"CODiS data rows have unexpected column counts: {bad_width}")
    return chinese_header, field_header, data_rows


def parse_numeric(raw_value: Any) -> tuple[str, bool, str]:
    text = str(raw_value or "").strip()
    if text.upper() in MISSING_TOKENS:
        return "", True, text
    try:
        return str(float(text)), False, ""
    except ValueError:
        return "", True, text


def observation_timestamp(hour_text: str) -> datetime:
    hour = int(hour_text)
    if hour < 1 or hour > 24:
        raise ValueError(f"CODiS observation hour must be 01-24: {hour_text}")
    tz = timezone(timedelta(hours=8))
    if hour == 24:
        return datetime.combine(OBSERVATION_DATE + timedelta(days=1), time(0), tz)
    return datetime.combine(OBSERVATION_DATE, time(hour), tz)


def normalize_rows(
    source_path: Path,
    field_header: list[str],
    data_rows: list[list[str]],
) -> list[dict[str, Any]]:
    index_by_field = {field: index for index, field in enumerate(field_header)}
    missing_fields = [
        field for field in ["ObsTime", *FIELD_MAP] if field not in index_by_field
    ]
    if missing_fields:
        raise ValueError(f"CODiS CSV missing required fields: {missing_fields}")

    normalized: list[dict[str, Any]] = []
    for source_row_number, source_row in enumerate(data_rows, start=3):
        hour_text = source_row[index_by_field["ObsTime"]].strip()
        timestamp = observation_timestamp(hour_text)
        output: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "source_type": SOURCE_TYPE,
            "source_file": str(source_path),
            "source_row_number": source_row_number,
            "station_id": STATION_ID,
            "station_name": STATION_NAME,
            "observation_date_local": OBSERVATION_DATE.isoformat(),
            "observation_hour_local": hour_text.zfill(2),
            "observation_time_local": timestamp.isoformat(),
            "source_confidence": "HIGH",
            "scoring_authorized": "False",
            "production_scoring_authorized": "False",
            "zero_fallback_used": "False",
        }

        missing_variables: list[str] = []
        for source_field, output_field in FIELD_MAP.items():
            raw_value = source_row[index_by_field[source_field]]
            value, missing, missing_token = parse_numeric(raw_value)
            output[output_field] = value
            output[f"{output_field}_missing"] = str(missing)
            output[f"{output_field}_missing_token"] = missing_token
            if missing:
                missing_variables.append(output_field)

        output["any_required_value_missing"] = str(bool(missing_variables))
        output["missing_variable_count"] = len(missing_variables)
        output["missing_variables"] = "|".join(missing_variables)
        normalized.append(output)
    return normalized


def build_summary(
    source_path: Path,
    requested_path: Path,
    legacy_fallback_used: bool,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    missing_counts = {
        output_field: sum(
            1
            for row in rows
            if row[f"{output_field}_missing"] == "True"
        )
        for output_field in FIELD_MAP.values()
    }
    hour_counts = Counter(row["observation_hour_local"] for row in rows)
    duplicate_hours = sorted(hour for hour, count in hour_counts.items() if count > 1)

    validation_pass = (
        len(rows) == 24
        and not duplicate_hours
        and all(row["zero_fallback_used"] == "False" for row in rows)
        and all(row["scoring_authorized"] == "False" for row in rows)
        and all(row["production_scoring_authorized"] == "False" for row in rows)
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "source_type": SOURCE_TYPE,
        "requested_input_csv": str(requested_path),
        "resolved_input_csv": str(source_path),
        "legacy_input_fallback_used": str(legacy_fallback_used),
        "station_id": STATION_ID,
        "station_name": STATION_NAME,
        "observation_date_local": OBSERVATION_DATE.isoformat(),
        "normalized_row_count": len(rows),
        "unique_observation_hour_count": len(hour_counts),
        "duplicate_observation_hours": "|".join(duplicate_hours),
        "rows_with_any_required_value_missing": sum(
            1 for row in rows if row["any_required_value_missing"] == "True"
        ),
        "total_missing_value_count": sum(missing_counts.values()),
        **{
            f"{field}_missing_count": count
            for field, count in missing_counts.items()
        },
        "zero_fallback_true_count": sum(
            1 for row in rows if row["zero_fallback_used"] == "True"
        ),
        "scoring_authorized_count": sum(
            1 for row in rows if row["scoring_authorized"] == "True"
        ),
        "production_scoring_authorized_count": sum(
            1 for row in rows
            if row["production_scoring_authorized"] == "True"
        ),
        "ingest_conclusion": "PASS" if validation_pass else "FAIL",
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    source_path, legacy_fallback_used = resolve_input(args.input_csv)
    _chinese_header, field_header, data_rows = read_codis_rows(source_path)
    normalized = normalize_rows(source_path, field_header, data_rows)
    summary = build_summary(
        source_path,
        args.input_csv,
        legacy_fallback_used,
        normalized,
    )

    normalized_csv = args.out_dir / "codis_hourly_observations_normalized.csv"
    summary_csv = args.out_dir / "codis_hourly_observations_summary.csv"

    normalized_fields = [
        "schema_version",
        "source_type",
        "source_file",
        "source_row_number",
        "station_id",
        "station_name",
        "observation_date_local",
        "observation_hour_local",
        "observation_time_local",
    ]
    for output_field in FIELD_MAP.values():
        normalized_fields.extend(
            [
                output_field,
                f"{output_field}_missing",
                f"{output_field}_missing_token",
            ]
        )
    normalized_fields.extend(
        [
            "any_required_value_missing",
            "missing_variable_count",
            "missing_variables",
            "source_confidence",
            "scoring_authorized",
            "production_scoring_authorized",
            "zero_fallback_used",
        ]
    )
    summary_fields = list(summary)

    write_csv(normalized_csv, normalized, normalized_fields)
    write_csv(summary_csv, [summary], summary_fields)

    print("IB3W CODiS historical weather ingest v1")
    print(f"normalized_csv: {normalized_csv}")
    print(f"summary_csv: {summary_csv}")
    print("summary:")
    for field in summary_fields:
        print(f"{field}: {summary[field]}")
    return 0 if summary["ingest_conclusion"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
