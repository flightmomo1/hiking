from __future__ import annotations

import csv
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median


SCHEMA_VERSION = "ib3w_codis_merged_context_weather_distribution_v1"

INPUT_CSV = Path(
    "outputs/ib3w_codis_multistation_fallback_merge_v1/"
    "activity_weather_codis_multistation_merged_context.csv"
)

OUT_ROOT = Path("outputs/ib3w_codis_merged_context_weather_distribution_v1")
PROFILE_WIDE_CSV = OUT_ROOT / "activity_weather_profile_wide.csv"
VARIABLE_SUMMARY_CSV = OUT_ROOT / "weather_variable_distribution_summary.csv"
ACTIVITY_SUMMARY_CSV = OUT_ROOT / "activity_weather_distribution_summary.csv"

OBSERVED_SOURCE_TYPES = {
    "SAME_DAY_DIRECT_OBSERVATION",
    "OBSERVED_HISTORICAL_CODIS",
}

PROFILE_VARIABLES = [
    "precipitation_mm",
    "temperature_c",
    "relative_humidity_pct",
    "pressure_hpa",
    "wind_speed_ms",
    "wind_direction_deg",
    "wind_gust_ms",
    "sunshine_duration_min",
    "uv_index",
]

# Descriptive labels only. These are not risk scores and must not authorize downstream scoring.
HIGH_HUMIDITY_THRESHOLD_PCT = 90.0
RAIN_OBSERVED_THRESHOLD_MM = 0.0
WIND_GUST_OBSERVED_THRESHOLD_MS = 0.0


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def as_float(value: object) -> float | None:
    text = str(value).strip()
    if not text:
        return None
    try:
        val = float(text)
    except ValueError:
        return None
    if math.isnan(val):
        return None
    return val


def fmt_number(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.6f}".rstrip("0").rstrip(".")


def truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def choose_source_type(rows: list[dict[str, str]]) -> str:
    counts = Counter(str(r.get("source_type", "")).strip() for r in rows)
    if counts.get("SAME_DAY_DIRECT_OBSERVATION", 0) and counts.get("OBSERVED_HISTORICAL_CODIS", 0):
        return "MIXED_DIRECT_AND_CODIS"
    if counts.get("SAME_DAY_DIRECT_OBSERVATION", 0):
        return "SAME_DAY_DIRECT_OBSERVATION"
    if counts.get("OBSERVED_HISTORICAL_CODIS", 0):
        return "OBSERVED_HISTORICAL_CODIS"
    return "NO_OBSERVED_WEATHER_CONTEXT"


def main() -> None:
    fieldnames, rows = read_csv(INPUT_CSV)
    required_cols = {"activity_id", "target_variable", "source_type", "value_numeric"}
    missing_cols = required_cols - set(fieldnames)
    if missing_cols:
        raise RuntimeError(f"input missing required columns: {sorted(missing_cols)}")

    all_activity_ids = sorted({str(r.get("activity_id", "")).strip() for r in rows if str(r.get("activity_id", "")).strip()})
    observed_rows = [
        r
        for r in rows
        if str(r.get("source_type", "")).strip() in OBSERVED_SOURCE_TYPES
        and str(r.get("activity_id", "")).strip()
        and str(r.get("target_variable", "")).strip()
    ]

    by_activity: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_activity_var: dict[tuple[str, str], dict[str, str]] = {}

    for row in observed_rows:
        activity_id = str(row.get("activity_id", "")).strip()
        target_variable = str(row.get("target_variable", "")).strip()
        by_activity[activity_id].append(row)

        # Keep first observed row for a variable. Merged evidence should already be one row per activity/target.
        key = (activity_id, target_variable)
        if key not in by_activity_var:
            by_activity_var[key] = row

    profile_rows: list[dict[str, object]] = []
    activity_summary_rows: list[dict[str, object]] = []

    for activity_id in all_activity_ids:
        activity_rows = [r for r in rows if str(r.get("activity_id", "")).strip() == activity_id]
        observed_for_activity = by_activity.get(activity_id, [])

        first = activity_rows[0] if activity_rows else {}
        observed_count = len(observed_for_activity)
        unavailable_count = sum(1 for r in activity_rows if str(r.get("source_type", "")).strip() == "UNAVAILABLE")

        station_ids = sorted(
            {
                str(r.get("codis_selected_station_id", "")).strip()
                for r in observed_for_activity
                if str(r.get("codis_selected_station_id", "")).strip()
            }
        )
        station_names = sorted(
            {
                str(r.get("codis_selected_station_name", "")).strip()
                for r in observed_for_activity
                if str(r.get("codis_selected_station_name", "")).strip()
            }
        )

        profile: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "case_id": first.get("case_id", ""),
            "activity_id": activity_id,
            "activity_start_time_utc": first.get("activity_start_time_utc", ""),
            "activity_end_time_utc": first.get("activity_end_time_utc", ""),
            "observed_context_source_type": choose_source_type(observed_for_activity),
            "observed_variable_count": observed_count,
            "unavailable_variable_count": unavailable_count,
            "codis_selected_station_ids": "|".join(station_ids),
            "codis_selected_station_names": "|".join(station_names),
            "thci_scoring_authorized": "False",
            "radar_scoring_authorized": "False",
            "final_hiking_risk_scoring_authorized": "False",
            "authorization_reason": "Descriptive IB3W weather evidence profiling only; no scoring authorization.",
        }

        for variable in PROFILE_VARIABLES:
            source_row = by_activity_var.get((activity_id, variable))
            numeric = as_float(source_row.get("value_numeric", "")) if source_row else None
            source_type = str(source_row.get("source_type", "")).strip() if source_row else ""
            station_id = str(source_row.get("codis_selected_station_id", "")).strip() if source_row else ""
            station_name = str(source_row.get("codis_selected_station_name", "")).strip() if source_row else ""
            sample_count = str(source_row.get("sample_count", "")).strip() if source_row else ""
            confidence = str(source_row.get("confidence", "")).strip() if source_row else ""

            profile[variable] = fmt_number(numeric)
            profile[f"{variable}_source_type"] = source_type
            profile[f"{variable}_selected_station_id"] = station_id
            profile[f"{variable}_selected_station_name"] = station_name
            profile[f"{variable}_sample_count"] = sample_count
            profile[f"{variable}_confidence"] = confidence

        precipitation = as_float(profile.get("precipitation_mm", ""))
        rh = as_float(profile.get("relative_humidity_pct", ""))
        wind_gust = as_float(profile.get("wind_gust_ms", ""))

        rain_observed = (
            "" if precipitation is None else str(precipitation > RAIN_OBSERVED_THRESHOLD_MM)
        )
        no_rain_observed = (
            "" if precipitation is None else str(precipitation <= RAIN_OBSERVED_THRESHOLD_MM)
        )
        high_humidity_observed = (
            "" if rh is None else str(rh >= HIGH_HUMIDITY_THRESHOLD_PCT)
        )
        wind_gust_observed = (
            "" if wind_gust is None else str(wind_gust > WIND_GUST_OBSERVED_THRESHOLD_MS)
        )

        profile["rain_observed"] = rain_observed
        profile["no_rain_observed"] = no_rain_observed
        profile["high_humidity_observed"] = high_humidity_observed
        profile["wind_gust_observed"] = wind_gust_observed

        profile_rows.append(profile)

        activity_summary_rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "activity_id": activity_id,
                "observed_context_source_type": profile["observed_context_source_type"],
                "observed_variable_count": observed_count,
                "unavailable_variable_count": unavailable_count,
                "rain_observed": rain_observed,
                "no_rain_observed": no_rain_observed,
                "high_humidity_observed": high_humidity_observed,
                "wind_gust_observed": wind_gust_observed,
                "temperature_c": profile.get("temperature_c", ""),
                "relative_humidity_pct": profile.get("relative_humidity_pct", ""),
                "pressure_hpa": profile.get("pressure_hpa", ""),
                "wind_speed_ms": profile.get("wind_speed_ms", ""),
                "wind_gust_ms": profile.get("wind_gust_ms", ""),
                "precipitation_mm": profile.get("precipitation_mm", ""),
                "sunshine_duration_min": profile.get("sunshine_duration_min", ""),
                "uv_index": profile.get("uv_index", ""),
                "codis_selected_station_ids": profile["codis_selected_station_ids"],
                "codis_selected_station_names": profile["codis_selected_station_names"],
                "thci_scoring_authorized": "False",
                "radar_scoring_authorized": "False",
                "final_hiking_risk_scoring_authorized": "False",
                "authorization_reason": "Descriptive IB3W weather evidence profiling only; no scoring authorization.",
            }
        )

    variable_summary_rows: list[dict[str, object]] = []
    all_target_variables = sorted({str(r.get("target_variable", "")).strip() for r in rows if str(r.get("target_variable", "")).strip()})

    for variable in all_target_variables:
        all_var_rows = [r for r in rows if str(r.get("target_variable", "")).strip() == variable]
        obs_var_rows = [
            r for r in all_var_rows
            if str(r.get("source_type", "")).strip() in OBSERVED_SOURCE_TYPES
        ]
        values = [as_float(r.get("value_numeric", "")) for r in obs_var_rows]
        numeric_values = [v for v in values if v is not None]

        source_counts = Counter(str(r.get("source_type", "")).strip() for r in all_var_rows)
        station_counts = Counter(
            str(r.get("codis_selected_station_id", "")).strip()
            for r in obs_var_rows
            if str(r.get("codis_selected_station_id", "")).strip()
        )

        count = len(numeric_values)
        variable_summary_rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "target_variable": variable,
                "total_row_count": len(all_var_rows),
                "observed_row_count": len(obs_var_rows),
                "numeric_observed_count": count,
                "missing_count": len(all_var_rows) - len(obs_var_rows),
                "min": fmt_number(min(numeric_values) if numeric_values else None),
                "median": fmt_number(median(numeric_values) if numeric_values else None),
                "mean": fmt_number(sum(numeric_values) / count if count else None),
                "max": fmt_number(max(numeric_values) if numeric_values else None),
                "source_type_distribution": "|".join(f"{k}={v}" for k, v in sorted(source_counts.items())),
                "selected_station_distribution": "|".join(f"{k}={v}" for k, v in sorted(station_counts.items())),
                "thci_scoring_authorized": "False",
                "radar_scoring_authorized": "False",
                "final_hiking_risk_scoring_authorized": "False",
                "authorization_reason": "Descriptive IB3W weather evidence profiling only; no scoring authorization.",
            }
        )

    profile_fields = [
        "schema_version",
        "case_id",
        "activity_id",
        "activity_start_time_utc",
        "activity_end_time_utc",
        "observed_context_source_type",
        "observed_variable_count",
        "unavailable_variable_count",
        "codis_selected_station_ids",
        "codis_selected_station_names",
    ]
    for variable in PROFILE_VARIABLES:
        profile_fields.extend(
            [
                variable,
                f"{variable}_source_type",
                f"{variable}_selected_station_id",
                f"{variable}_selected_station_name",
                f"{variable}_sample_count",
                f"{variable}_confidence",
            ]
        )
    profile_fields.extend(
        [
            "rain_observed",
            "no_rain_observed",
            "high_humidity_observed",
            "wind_gust_observed",
            "thci_scoring_authorized",
            "radar_scoring_authorized",
            "final_hiking_risk_scoring_authorized",
            "authorization_reason",
        ]
    )

    activity_summary_fields = [
        "schema_version",
        "activity_id",
        "observed_context_source_type",
        "observed_variable_count",
        "unavailable_variable_count",
        "rain_observed",
        "no_rain_observed",
        "high_humidity_observed",
        "wind_gust_observed",
        "temperature_c",
        "relative_humidity_pct",
        "pressure_hpa",
        "wind_speed_ms",
        "wind_gust_ms",
        "precipitation_mm",
        "sunshine_duration_min",
        "uv_index",
        "codis_selected_station_ids",
        "codis_selected_station_names",
        "thci_scoring_authorized",
        "radar_scoring_authorized",
        "final_hiking_risk_scoring_authorized",
        "authorization_reason",
    ]

    variable_summary_fields = [
        "schema_version",
        "target_variable",
        "total_row_count",
        "observed_row_count",
        "numeric_observed_count",
        "missing_count",
        "min",
        "median",
        "mean",
        "max",
        "source_type_distribution",
        "selected_station_distribution",
        "thci_scoring_authorized",
        "radar_scoring_authorized",
        "final_hiking_risk_scoring_authorized",
        "authorization_reason",
    ]

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    write_csv(PROFILE_WIDE_CSV, profile_fields, profile_rows)
    write_csv(VARIABLE_SUMMARY_CSV, variable_summary_fields, variable_summary_rows)
    write_csv(ACTIVITY_SUMMARY_CSV, activity_summary_fields, activity_summary_rows)

    observed_source_counts = Counter(str(r.get("source_type", "")).strip() for r in observed_rows)

    print("IB3W CODiS merged context weather distribution v1")
    print(f"profile_wide_csv: {PROFILE_WIDE_CSV}")
    print(f"variable_summary_csv: {VARIABLE_SUMMARY_CSV}")
    print(f"activity_summary_csv: {ACTIVITY_SUMMARY_CSV}")
    print(f"activity_count: {len(all_activity_ids)}")
    print(f"observed_row_count: {len(observed_rows)}")
    print(f"source_type_distribution: {'|'.join(f'{k}={v}' for k, v in sorted(observed_source_counts.items()))}")
    print("scoring_authorized: False")


if __name__ == "__main__":
    main()
