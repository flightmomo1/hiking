from __future__ import annotations

import argparse
import csv
import math
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "ib3w_codis_fallback_merge_prototype_v1"
CODIS_SOURCE_TYPE = "OBSERVED_HISTORICAL_CODIS"
MERGE_METHOD = "codis_hourly_nearest_or_activity_window_match_v1"

DEFAULT_EVIDENCE_CSV = Path(
    "outputs/ib3w_weather_inference_fallback_prototype_v1/"
    "activity_weather_inference_fallback_evidence.csv"
)
DEFAULT_CODIS_CSV = Path(
    "outputs/ib3w_codis_historical_weather_ingest_v1/"
    "codis_hourly_observations_normalized.csv"
)
DEFAULT_CODIS_SUMMARY_CSV = Path(
    "outputs/ib3w_codis_historical_weather_ingest_v1/"
    "codis_hourly_observations_summary.csv"
)
DEFAULT_OUT_DIR = Path("outputs/ib3w_codis_fallback_merge_prototype_v1")

# Fallback canonical variable -> CODiS normalized field.
VARIABLE_MAP = {
    "temperature_c": ("temperature_c", "mean", 1.0),
    "relative_humidity_pct": ("relative_humidity_pct", "mean", 1.0),
    "wind_speed_ms": ("wind_speed_mps", "mean", 1.0),
    "wind_direction_deg": ("wind_direction_deg", "circular_mean", 1.0),
    "wind_gust_ms": ("wind_gust_mps", "max", 1.0),
    "precipitation_mm": ("precipitation_mm", "sum", 1.0),
    "sunshine_duration_min": ("sunshine_hour", "sum", 60.0),
    "uv_index": ("uvi", "max", 1.0),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge normalized CODiS observations into unavailable IB3W fallback evidence."
    )
    parser.add_argument("--evidence-csv", type=Path, default=DEFAULT_EVIDENCE_CSV)
    parser.add_argument("--codis-csv", type=Path, default=DEFAULT_CODIS_CSV)
    parser.add_argument(
        "--codis-summary-csv", type=Path, default=DEFAULT_CODIS_SUMMARY_CSV
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Input CSV not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def parse_datetime(value: Any) -> datetime:
    text = str(value or "").strip().replace("Z", "+00:00")
    if not text:
        raise ValueError("Missing datetime value")
    return datetime.fromisoformat(text)


def is_true(value: Any) -> bool:
    return str(value or "").strip().lower() in {"true", "1", "yes", "y"}


def variable_value(row: dict[str, Any]) -> str:
    return str(row.get("target_variable") or row.get("variable_name") or "").strip()


def numeric_values(rows: list[dict[str, str]], field: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        if is_true(row.get(f"{field}_missing")):
            continue
        text = str(row.get(field) or "").strip()
        if not text:
            continue
        try:
            values.append(float(text))
        except ValueError:
            continue
    return values


def aggregate(values: list[float], operation: str) -> float | None:
    if not values:
        return None
    if operation == "sum":
        return sum(values)
    if operation == "max":
        return max(values)
    if operation == "circular_mean":
        sin_mean = sum(math.sin(math.radians(value)) for value in values) / len(values)
        cos_mean = sum(math.cos(math.radians(value)) for value in values) / len(values)
        return math.degrees(math.atan2(sin_mean, cos_mean)) % 360.0
    return sum(values) / len(values)


def aligned_codis_rows(
    evidence_row: dict[str, str],
    codis_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], str]:
    activity_start = parse_datetime(evidence_row["activity_start_time_utc"])
    activity_end = parse_datetime(evidence_row["activity_end_time_utc"])
    midpoint = activity_start + (activity_end - activity_start) / 2

    parsed_rows = [
        (row, parse_datetime(row["observation_time_local"]))
        for row in codis_rows
    ]
    window_rows = [
        row
        for row, observation_time in parsed_rows
        if activity_start <= observation_time <= activity_end
    ]
    if window_rows:
        return window_rows, "ACTIVITY_WINDOW_MATCH"

    same_date_rows = [
        (row, observation_time)
        for row, observation_time in parsed_rows
        if observation_time.date() == activity_start.date()
    ]
    if not same_date_rows:
        return [], "NO_SAME_LOCAL_DATE"

    nearest_row, _nearest_time = min(
        same_date_rows,
        key=lambda item: abs((item[1] - midpoint).total_seconds()),
    )
    return [nearest_row], "SAME_DATE_NEAREST_HOUR_MATCH"


def merge_row(
    evidence_row: dict[str, str],
    codis_rows: list[dict[str, str]],
) -> dict[str, Any]:
    output: dict[str, Any] = dict(evidence_row)
    target_variable = variable_value(evidence_row)
    output.pop("variable_name", None)
    output["target_variable"] = target_variable
    output.update(
        {
            "merge_schema_version": SCHEMA_VERSION,
            "codis_merge_applied": "False",
            "codis_match_type": "",
            "codis_source_field": "",
            "codis_source_observation_count": 0,
            "station_id": "",
            "station_name": "",
            "scoring_authorized": "False",
            "production_scoring_authorized": "False",
            "experimental_model_allowed": "False",
        }
    )

    if evidence_row.get("source_type") != "UNAVAILABLE":
        return output

    mapping = VARIABLE_MAP.get(target_variable)
    if mapping is None:
        return output

    source_field, operation, scale = mapping
    matched_rows, match_type = aligned_codis_rows(evidence_row, codis_rows)
    values = numeric_values(matched_rows, source_field)
    merged_value = aggregate(values, operation)
    if merged_value is None:
        return output

    merged_value *= scale
    observation_times = [
        parse_datetime(row["observation_time_local"]) for row in matched_rows
    ]
    output.update(
        {
            "schema_version": SCHEMA_VERSION,
            "value_numeric": str(merged_value),
            "value_text": "",
            "source_type": CODIS_SOURCE_TYPE,
            "context_type": "OBSERVED",
            "confidence": "HIGH",
            "method": MERGE_METHOD,
            "lookback_days": "0",
            "lookahead_days": "0",
            "lookaround_days": "0",
            "sample_count": str(len(values)),
            "source_station_ids": "466930",
            "source_station_names": "竹子湖",
            "source_dataset_codes": "CODIS_HISTORICAL_HOURLY_CSV",
            "source_observation_start_time_utc": min(observation_times).isoformat(),
            "source_observation_end_time_utc": max(observation_times).isoformat(),
            "direct_observation": "True",
            "inferred_or_climatology": "False",
            "missing_value_preserved": "False",
            "zero_fallback_used": "False",
            "thci_scoring_authorized": "False",
            "radar_scoring_authorized": "False",
            "final_hiking_risk_scoring_authorized": "False",
            "authorization_reason": (
                "CODiS historical evidence prototype only; production scoring is not authorized."
            ),
            "codis_merge_applied": "True",
            "codis_match_type": match_type,
            "codis_source_field": source_field,
            "codis_source_observation_count": len(values),
            "station_id": "466930",
            "station_name": "竹子湖",
            "scoring_authorized": "False",
            "production_scoring_authorized": "False",
            "experimental_model_allowed": "True",
        }
    )
    return output


def validate_codis_summary(summary_rows: list[dict[str, str]]) -> dict[str, str]:
    if len(summary_rows) != 1:
        raise ValueError("CODiS ingest summary must contain exactly one row")
    summary = summary_rows[0]
    if summary.get("ingest_conclusion") != "PASS":
        raise ValueError("CODiS ingest summary is not PASS")
    if summary.get("zero_fallback_true_count") != "0":
        raise ValueError("CODiS ingest reports zero fallback usage")
    if summary.get("scoring_authorized_count") != "0":
        raise ValueError("CODiS ingest unexpectedly authorizes scoring")
    if summary.get("production_scoring_authorized_count") != "0":
        raise ValueError("CODiS ingest unexpectedly authorizes production scoring")
    return summary


def build_summary(
    input_rows: list[dict[str, str]],
    merged_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    before_counts = Counter(row.get("source_type", "") for row in input_rows)
    after_counts = Counter(str(row.get("source_type", "")) for row in merged_rows)
    original_observed_count = sum(
        1
        for row in input_rows
        if row.get("source_type") == "SAME_DAY_DIRECT_OBSERVATION"
    )
    original_observed_preserved_count = sum(
        1
        for before, after in zip(input_rows, merged_rows)
        if before.get("source_type") == "SAME_DAY_DIRECT_OBSERVATION"
        and after.get("source_type") == "SAME_DAY_DIRECT_OBSERVATION"
        and before.get("value_numeric") == after.get("value_numeric")
        and before.get("value_text") == after.get("value_text")
    )
    zero_fallback_true_count = sum(
        1 for row in merged_rows if is_true(row.get("zero_fallback_used"))
    )
    scoring_authorized_count = sum(
        1 for row in merged_rows if is_true(row.get("scoring_authorized"))
    )
    production_authorized_count = sum(
        1
        for row in merged_rows
        if is_true(row.get("production_scoring_authorized"))
    )
    experimental_allowed_count = sum(
        1 for row in merged_rows if is_true(row.get("experimental_model_allowed"))
    )
    codis_merged_count = sum(
        1 for row in merged_rows if is_true(row.get("codis_merge_applied"))
    )
    merged_variable_counts = Counter(
        variable_value(row)
        for row in merged_rows
        if row.get("source_type") == CODIS_SOURCE_TYPE
    )
    unavailable_variable_counts = Counter(
        variable_value(row)
        for row in merged_rows
        if row.get("source_type") == "UNAVAILABLE"
    )

    passed = (
        len(input_rows) == len(merged_rows)
        and original_observed_count == original_observed_preserved_count
        and zero_fallback_true_count == 0
        and scoring_authorized_count == 0
        and production_authorized_count == 0
        and codis_merged_count > 0
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "input_evidence_row_count": len(input_rows),
        "original_unavailable_count": before_counts.get("UNAVAILABLE", 0),
        "codis_merged_observed_count": codis_merged_count,
        "remaining_unavailable_count": after_counts.get("UNAVAILABLE", 0),
        "original_observed_preserved_count": original_observed_preserved_count,
        "zero_fallback_true_count": zero_fallback_true_count,
        "scoring_authorized_count": scoring_authorized_count,
        "production_scoring_authorized_count": production_authorized_count,
        "experimental_model_allowed_count": experimental_allowed_count,
        "source_type_distribution_before": "|".join(
            f"{key}:{before_counts[key]}" for key in sorted(before_counts)
        ),
        "source_type_distribution_after": "|".join(
            f"{key}:{after_counts[key]}" for key in sorted(after_counts)
        ),
        "codis_merged_target_variable_distribution": "|".join(
            f"{key}:{merged_variable_counts[key]}"
            for key in sorted(merged_variable_counts)
        ),
        "remaining_unavailable_target_variable_distribution": "|".join(
            f"{key}:{unavailable_variable_counts[key]}"
            for key in sorted(unavailable_variable_counts)
        ),
        "merge_conclusion": "PASS" if passed else "FAIL",
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    evidence_rows = read_csv_rows(args.evidence_csv)
    codis_rows = read_csv_rows(args.codis_csv)
    validate_codis_summary(read_csv_rows(args.codis_summary_csv))

    merged_rows = [merge_row(row, codis_rows) for row in evidence_rows]
    summary = build_summary(evidence_rows, merged_rows)

    merged_csv = args.out_dir / "activity_weather_codis_merged_context.csv"
    summary_csv = args.out_dir / "activity_weather_codis_merged_summary.csv"

    original_fields = (
        [field for field in evidence_rows[0] if field != "variable_name"]
        if evidence_rows
        else []
    )
    if "target_variable" not in original_fields:
        original_fields.append("target_variable")
    extra_fields = [
        "merge_schema_version",
        "codis_merge_applied",
        "codis_match_type",
        "codis_source_field",
        "codis_source_observation_count",
        "station_id",
        "station_name",
        "scoring_authorized",
        "production_scoring_authorized",
        "experimental_model_allowed",
    ]
    write_csv(merged_csv, merged_rows, original_fields + extra_fields)
    write_csv(summary_csv, [summary], list(summary))

    print("IB3W CODiS fallback merge prototype v1")
    print(f"merged_csv: {merged_csv}")
    print(f"summary_csv: {summary_csv}")
    print("summary:")
    for field, value in summary.items():
        print(f"{field}: {value}")
    return 0 if summary["merge_conclusion"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
