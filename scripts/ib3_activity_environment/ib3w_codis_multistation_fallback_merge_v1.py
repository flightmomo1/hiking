from __future__ import annotations

import csv
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


SCHEMA_VERSION = "ib3w_codis_multistation_fallback_merge_v1"

FALLBACK_CSV = Path("outputs/ib3w_weather_inference_fallback_prototype_v1/activity_weather_inference_fallback_evidence.csv")
CODIS_CSV = Path("outputs/ib3w_codis_historical_weather_multistation_ingest_v1/codis_hourly_observations_normalized_multistation.csv")
RAW_CODIS_DIR = Path("weather/codis")

OUT_ROOT = Path("outputs/ib3w_codis_multistation_fallback_merge_v1")
MERGED_CSV = OUT_ROOT / "activity_weather_codis_multistation_merged_context.csv"
SUMMARY_CSV = OUT_ROOT / "activity_weather_codis_multistation_merged_summary.csv"
STATION_SUMMARY_CSV = OUT_ROOT / "activity_weather_codis_multistation_merge_station_summary.csv"

WINDOW_PAD_HOURS = 3

STATION_PRIORITY = [
    {
        "station_id": "466910",
        "station_name": "鞍部",
        "station_role": "PRIMARY_MOUNTAIN_RIDGE",
        "priority": 1,
        "confidence": 0.90,
    },
    {
        "station_id": "C0AC40",
        "station_name": "大屯山",
        "station_role": "PRIMARY_MOUNTAIN_RIDGE_BACKUP",
        "priority": 2,
        "confidence": 0.87,
    },
    {
        "station_id": "466930",
        "station_name": "竹子湖",
        "station_role": "MOUNTAIN_AREA_BACKGROUND",
        "priority": 3,
        "confidence": 0.82,
    },
    {
        "station_id": "C0AH40",
        "station_name": "平等",
        "station_role": "LOW_TO_MID_ELEVATION_BACKUP",
        "priority": 4,
        "confidence": 0.70,
    },
]

VARIABLE_MAPPING = {
    "precipitation_mm": {
        "columns": ["precipitation_mm"],
        "aggregation": "sum",
        "unit": "mm",
    },
    "temperature_c": {
        "columns": ["temperature_c"],
        "aggregation": "mean",
        "unit": "degC",
    },
    "relative_humidity_pct": {
        "columns": ["relative_humidity_pct"],
        "aggregation": "mean",
        "unit": "pct",
    },
    "pressure_hpa": {
        "columns": ["station_pressure_hpa", "pressure_hpa", "stnpres_hpa"],
        "aggregation": "mean",
        "unit": "hPa",
    },
    "wind_speed_ms": {
        "columns": ["wind_speed_mps"],
        "aggregation": "mean",
        "unit": "mps",
    },
    "wind_direction_deg": {
        "columns": ["wind_direction_deg"],
        "aggregation": "circular_mean_deg",
        "unit": "deg",
    },
    "wind_gust_ms": {
        "columns": ["wind_gust_mps"],
        "aggregation": "max",
        "unit": "mps",
    },
    "sunshine_duration_min": {
        "columns": ["sunshine_hour"],
        "aggregation": "sum_x60",
        "unit": "min",
    },
    "uv_index": {
        "columns": ["uvi"],
        "aggregation": "max",
        "unit": "index",
    },
    "global_radiation_mj_m2": {
        "columns": ["global_radiation_mj_m2"],
        "aggregation": "sum",
        "unit": "MJ/m2",
    },
    "cloud_amount_0_10": {
        "columns": ["cloud_amount_0_10"],
        "aggregation": "mean",
        "unit": "0-10",
    },
}

UNSUPPORTED_TARGETS = {
    "precipitation_10min_mm",
    "precipitation_1hr_mm",
    "visibility_m",
    "weather",
}

EXTRA_FIELDS = [
    "codis_merge_applied",
    "codis_selected_station_id",
    "codis_selected_station_name",
    "codis_selected_station_role",
    "codis_selected_station_priority",
    "codis_aggregation",
    "codis_window_pad_hours",
    "codis_value_column",
]


def parse_datetime(value: str) -> datetime:
    text = str(value).strip()
    if not text:
        raise ValueError("empty datetime")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError(f"datetime has no timezone: {value}")
    return dt.astimezone(timezone.utc)


def fmt_datetime(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = [dict(r) for r in reader]
        fieldnames = list(reader.fieldnames or [])
    return fieldnames, rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def parse_float(value: object) -> float | None:
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


def get_value(row: dict[str, object], col: str) -> float | None:
    if col not in row:
        return None
    missing_col = f"{col}_missing"
    if missing_col in row and truthy(row.get(missing_col, "")):
        return None
    return parse_float(row.get(col, ""))


def select_first_existing_column(row: dict[str, object], columns: list[str]) -> str | None:
    for col in columns:
        if col in row:
            return col
    return None


def circular_mean_deg(values: list[float]) -> float | None:
    if not values:
        return None

    sin_sum = 0.0
    cos_sum = 0.0

    for deg in values:
        rad = math.radians(deg)
        sin_sum += math.sin(rad)
        cos_sum += math.cos(rad)

    if sin_sum == 0 and cos_sum == 0:
        return None

    mean_rad = math.atan2(sin_sum / len(values), cos_sum / len(values))
    mean_deg = math.degrees(mean_rad)
    if mean_deg < 0:
        mean_deg += 360.0

    return mean_deg


def aggregate(values: list[float], aggregation: str) -> float | None:
    if not values:
        return None

    if aggregation == "sum":
        return sum(values)
    if aggregation == "sum_x60":
        return sum(values) * 60.0
    if aggregation == "mean":
        return sum(values) / len(values)
    if aggregation == "max":
        return max(values)
    if aggregation == "circular_mean_deg":
        return circular_mean_deg(values)

    raise ValueError(f"unsupported aggregation: {aggregation}")


def round_value(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.6f}".rstrip("0").rstrip(".")



def build_raw_station_pressure_lookup(raw_dir: Path) -> dict[tuple[str, str, str], tuple[str, bool]]:
    """Return (station_id, observation_date_local, observation_hour_local) -> (StnPres text, source column present)."""
    lookup: dict[tuple[str, str, str], tuple[str, bool]] = {}

    if not raw_dir.exists():
        return lookup

    for path in sorted(raw_dir.glob("*.csv")):
        stem = path.stem
        if "-" not in stem:
            continue

        station_id, observation_date_local = stem.split("-", 1)

        with path.open("r", encoding="utf-8-sig", newline="") as f:
            # CODiS exported CSVs use row 1 as Chinese labels and row 2 as English field names.
            lines = f.readlines()

        if len(lines) < 2:
            continue

        reader = csv.DictReader(lines[1:])
        has_stnpres = bool(reader.fieldnames and "StnPres" in reader.fieldnames)

        for raw_row in reader:
            hour_text = str(raw_row.get("ObsTime", "")).strip()
            if not hour_text:
                continue

            try:
                hour_norm = f"{int(float(hour_text)):02d}"
            except ValueError:
                hour_norm = hour_text.zfill(2)

            raw_value = str(raw_row.get("StnPres", "")).strip() if has_stnpres else ""
            lookup[(station_id, observation_date_local, hour_norm)] = (raw_value, has_stnpres)

    return lookup

def build_codis_index(codis_rows: list[dict[str, str]], pressure_lookup: dict[tuple[str, str, str], tuple[str, bool]]) -> dict[str, list[dict[str, object]]]:
    index: dict[str, list[dict[str, object]]] = defaultdict(list)

    for row in codis_rows:
        station_id = str(row.get("station_id", "")).strip()
        obs_time_text = str(row.get("observation_time_local", "")).strip()

        if not station_id or not obs_time_text:
            continue

        try:
            obs_time_utc = parse_datetime(obs_time_text)
        except ValueError:
            continue

        enriched: dict[str, object] = dict(row)
        enriched["_observation_time_utc"] = obs_time_utc

        observation_date_local = str(row.get("observation_date_local", "")).strip()
        observation_hour_local = str(row.get("observation_hour_local", "")).strip().zfill(2)
        pressure_value, pressure_present = pressure_lookup.get(
            (station_id, observation_date_local, observation_hour_local),
            ("", False),
        )

        enriched["station_pressure_hpa"] = pressure_value
        enriched["station_pressure_hpa_source_column_present"] = "True" if pressure_present else "False"
        if pressure_present and parse_float(pressure_value) is not None:
            enriched["station_pressure_hpa_missing"] = "False"
            enriched["station_pressure_hpa_missing_token"] = ""
        else:
            enriched["station_pressure_hpa_missing"] = "True"
            enriched["station_pressure_hpa_missing_token"] = pressure_value

        index[station_id].append(enriched)

    for station_id in index:
        index[station_id].sort(key=lambda r: r["_observation_time_utc"])  # type: ignore[index]

    return index


def find_station_values(
    codis_index: dict[str, list[dict[str, object]]],
    station: dict[str, object],
    target_variable: str,
    window_start_utc: datetime,
    window_end_utc: datetime,
) -> tuple[str | None, list[float], list[datetime]]:
    spec = VARIABLE_MAPPING[target_variable]
    station_rows = codis_index.get(str(station["station_id"]), [])

    if not station_rows:
        return None, [], []

    selected_col = select_first_existing_column(station_rows[0], spec["columns"])
    if selected_col is None:
        return None, [], []

    values: list[float] = []
    times: list[datetime] = []

    for row in station_rows:
        obs_time = row["_observation_time_utc"]
        if not isinstance(obs_time, datetime):
            continue

        if obs_time < window_start_utc or obs_time > window_end_utc:
            continue

        val = get_value(row, selected_col)
        if val is None:
            continue

        values.append(val)
        times.append(obs_time)

    return selected_col, values, times


def main() -> None:
    fallback_fields, fallback_rows = read_csv(FALLBACK_CSV)
    _, codis_rows = read_csv(CODIS_CSV)

    if "target_variable" not in fallback_fields:
        raise RuntimeError("fallback evidence does not contain target_variable")

    out_fields = list(fallback_fields)
    for field in EXTRA_FIELDS:
        if field not in out_fields:
            out_fields.append(field)

    pressure_lookup = build_raw_station_pressure_lookup(RAW_CODIS_DIR)
    codis_index = build_codis_index(codis_rows, pressure_lookup)

    source_before = Counter(str(r.get("source_type", "")).strip() for r in fallback_rows)

    merged_rows: list[dict[str, object]] = []
    station_target_counter: Counter[tuple[str, str, str, str, str]] = Counter()

    original_unavailable_count = 0
    original_observed_preserved_count = 0
    codis_merged_count = 0
    unsupported_count = 0
    no_candidate_count = 0
    original_observed_modified_count = 0

    for original in fallback_rows:
        row: dict[str, object] = dict(original)

        for field in EXTRA_FIELDS:
            row[field] = ""

        row["codis_merge_applied"] = "False"

        original_source_type = str(original.get("source_type", "")).strip()
        target_variable = str(original.get("target_variable", "")).strip()

        if original_source_type != "UNAVAILABLE":
            original_observed_preserved_count += 1
            merged_rows.append(row)
            continue

        original_unavailable_count += 1

        if target_variable in UNSUPPORTED_TARGETS or target_variable not in VARIABLE_MAPPING:
            unsupported_count += 1
            merged_rows.append(row)
            continue

        try:
            activity_start_utc = parse_datetime(str(original.get("activity_start_time_utc", "")))
            activity_end_utc = parse_datetime(str(original.get("activity_end_time_utc", "")))
        except ValueError:
            no_candidate_count += 1
            merged_rows.append(row)
            continue

        window_start_utc = activity_start_utc - timedelta(hours=WINDOW_PAD_HOURS)
        window_end_utc = activity_end_utc + timedelta(hours=WINDOW_PAD_HOURS)

        merged = False

        for station in STATION_PRIORITY:
            selected_col, values, times = find_station_values(
                codis_index=codis_index,
                station=station,
                target_variable=target_variable,
                window_start_utc=window_start_utc,
                window_end_utc=window_end_utc,
            )

            if not values or not times or selected_col is None:
                continue

            spec = VARIABLE_MAPPING[target_variable]
            aggregated = aggregate(values, str(spec["aggregation"]))

            if aggregated is None:
                continue

            row["value_numeric"] = round_value(aggregated)
            row["value_text"] = ""
            row["source_type"] = "OBSERVED_HISTORICAL_CODIS"
            row["context_type"] = "OBSERVED"
            row["confidence"] = str(station["confidence"])
            row["method"] = (
                "codis_multistation_activity_window_match_v1; "
                f"priority={station['priority']}; "
                f"station_role={station['station_role']}; "
                f"aggregation={spec['aggregation']}; "
                f"window=activity_time_utc +/- {WINDOW_PAD_HOURS}h; "
                "historical observed evidence only; no scoring authorization"
            )
            row["lookback_days"] = "0"
            row["lookahead_days"] = "0"
            row["lookaround_days"] = "0"
            row["sample_count"] = str(len(values))
            row["neighbor_station_distance_m"] = ""
            row["source_station_ids"] = str(station["station_id"])
            row["source_station_names"] = str(station["station_name"])
            row["source_dataset_codes"] = "CODiS.HistoricalHourly"
            row["source_observation_start_time_utc"] = fmt_datetime(min(times))
            row["source_observation_end_time_utc"] = fmt_datetime(max(times))
            row["direct_observation"] = "True"
            row["inferred_or_climatology"] = "False"
            row["missing_value_preserved"] = "False"
            row["zero_fallback_used"] = "False"
            row["thci_scoring_authorized"] = "False"
            row["radar_scoring_authorized"] = "False"
            row["final_hiking_risk_scoring_authorized"] = "False"
            row["authorization_reason"] = (
                "CODiS historical observed evidence only; "
                "IB3W context layer; no THCI, radar, or final hiking risk scoring authorization."
            )

            row["codis_merge_applied"] = "True"
            row["codis_selected_station_id"] = str(station["station_id"])
            row["codis_selected_station_name"] = str(station["station_name"])
            row["codis_selected_station_role"] = str(station["station_role"])
            row["codis_selected_station_priority"] = str(station["priority"])
            row["codis_aggregation"] = str(spec["aggregation"])
            row["codis_window_pad_hours"] = str(WINDOW_PAD_HOURS)
            row["codis_value_column"] = selected_col

            station_target_counter[
                (
                    str(station["station_id"]),
                    str(station["station_name"]),
                    str(station["station_role"]),
                    str(station["priority"]),
                    target_variable,
                )
            ] += 1

            codis_merged_count += 1
            merged = True
            break

        if not merged:
            no_candidate_count += 1

        merged_rows.append(row)

    source_after = Counter(str(r.get("source_type", "")).strip() for r in merged_rows)
    remaining_unavailable_count = source_after.get("UNAVAILABLE", 0)

    zero_fallback_true_count = sum(1 for r in merged_rows if truthy(r.get("zero_fallback_used", "")))
    thci_scoring_authorized_count = sum(1 for r in merged_rows if truthy(r.get("thci_scoring_authorized", "")))
    radar_scoring_authorized_count = sum(1 for r in merged_rows if truthy(r.get("radar_scoring_authorized", "")))
    final_hiking_risk_scoring_authorized_count = sum(
        1 for r in merged_rows if truthy(r.get("final_hiking_risk_scoring_authorized", ""))
    )
    production_scoring_authorized_count = 0

    selected_station_ids = sorted(
        {
            str(r.get("codis_selected_station_id", "")).strip()
            for r in merged_rows
            if truthy(r.get("codis_merge_applied", ""))
        }
    )

    merge_conclusion = "PASS"
    if zero_fallback_true_count != 0:
        merge_conclusion = "FAIL_ZERO_FALLBACK"
    if (
        thci_scoring_authorized_count
        or radar_scoring_authorized_count
        or final_hiking_risk_scoring_authorized_count
        or production_scoring_authorized_count
    ):
        merge_conclusion = "FAIL_SCORING_AUTHORIZED"

    summary = {
        "schema_version": SCHEMA_VERSION,
        "input_evidence_csv": str(FALLBACK_CSV),
        "input_codis_multistation_csv": str(CODIS_CSV),
        "input_raw_codis_directory_for_pressure": str(RAW_CODIS_DIR),
        "raw_station_pressure_lookup_count": str(len(pressure_lookup)),
        "input_evidence_row_count": str(len(fallback_rows)),
        "original_unavailable_count": str(original_unavailable_count),
        "codis_merged_observed_count": str(codis_merged_count),
        "remaining_unavailable_count": str(remaining_unavailable_count),
        "original_observed_preserved_count": str(original_observed_preserved_count),
        "original_observed_modified_count": str(original_observed_modified_count),
        "unsupported_target_count": str(unsupported_count),
        "no_candidate_count": str(no_candidate_count),
        "merge_station_count": str(len(selected_station_ids)),
        "merge_station_priority_order": ">".join(str(s["station_id"]) for s in STATION_PRIORITY),
        "source_type_before_distribution": "|".join(f"{k}={v}" for k, v in sorted(source_before.items())),
        "source_type_after_distribution": "|".join(f"{k}={v}" for k, v in sorted(source_after.items())),
        "zero_fallback_true_count": str(zero_fallback_true_count),
        "thci_scoring_authorized_count": str(thci_scoring_authorized_count),
        "radar_scoring_authorized_count": str(radar_scoring_authorized_count),
        "final_hiking_risk_scoring_authorized_count": str(final_hiking_risk_scoring_authorized_count),
        "production_scoring_authorized_count": str(production_scoring_authorized_count),
        "merge_conclusion": merge_conclusion,
    }

    station_summary_rows = []
    for (station_id, station_name, station_role, priority, target_variable), count in sorted(
        station_target_counter.items(), key=lambda item: (int(item[0][3]), item[0][4])
    ):
        station_summary_rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "station_id": station_id,
                "station_name": station_name,
                "station_role": station_role,
                "station_priority": priority,
                "target_variable": target_variable,
                "merged_count": str(count),
            }
        )

    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    write_csv(MERGED_CSV, out_fields, merged_rows)
    write_csv(SUMMARY_CSV, list(summary.keys()), [summary])
    write_csv(
        STATION_SUMMARY_CSV,
        [
            "schema_version",
            "station_id",
            "station_name",
            "station_role",
            "station_priority",
            "target_variable",
            "merged_count",
        ],
        station_summary_rows,
    )

    print("IB3W CODiS multistation fallback merge v1")
    print(f"merged_csv: {MERGED_CSV}")
    print(f"summary_csv: {SUMMARY_CSV}")
    print(f"station_summary_csv: {STATION_SUMMARY_CSV}")
    print("summary:")
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
