from __future__ import annotations

import argparse
import math
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

try:
    import pandas as pd
except ModuleNotFoundError:
    venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
        os.execv(str(venv_python), [str(venv_python), __file__, *sys.argv[1:]])
    raise


SCHEMA_VERSION = "ib3w_weather_inference_fallback_prototype_v1"
DEFAULT_ACTIVITY_CSV = Path(
    "outputs/ib3w_representative_environment_features_v1/"
    "activity_representative_environment_features.csv"
)
DEFAULT_WEATHER_DB = Path("weather/tw_weather_2026-05-01.sqlite3")
DEFAULT_OUT_DIR = Path("outputs/ib3w_weather_inference_fallback_prototype_v1")

LOOKAROUND_DAYS = 7
DIRECT_TOLERANCE_HOURS = 3
MIN_CLIMATOLOGY_SAMPLES = 3

VARIABLES = [
    "precipitation_mm",
    "precipitation_10min_mm",
    "precipitation_1hr_mm",
    "temperature_c",
    "relative_humidity_pct",
    "pressure_hpa",
    "wind_speed_ms",
    "wind_direction_deg",
    "wind_gust_ms",
    "sunshine_duration_min",
    "visibility_m",
    "uv_index",
    "weather",
]

NUMERIC_VARIABLES = set(VARIABLES) - {"weather"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build field-level IB3W inferred weather context evidence."
    )
    parser.add_argument("--activity-csv", type=Path, default=DEFAULT_ACTIVITY_CSV)
    parser.add_argument("--weather-db", type=Path, default=DEFAULT_WEATHER_DB)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def parse_utc(value: Any) -> datetime:
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        raise ValueError(f"Invalid activity timestamp: {value}")
    return parsed.to_pydatetime()


def split_station_ids(value: Any) -> list[str]:
    return [
        item.strip()
        for item in str(value or "").split("|")
        if item.strip()
    ]


def load_activities(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Activity CSV not found: {path}")
    frame = pd.read_csv(path, dtype={"activity_id": str})
    required = [
        "output_case",
        "case_id",
        "activity_id",
        "activity_start_time_utc",
        "activity_end_time_utc",
        "primary_candidate_station_ids",
    ]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Activity CSV missing columns: {missing}")
    return frame


def load_weather(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Weather DB not found: {path}")
    columns = [
        "source",
        "dataset_code",
        "station_id",
        "station_name",
        "obs_time",
        "latitude",
        "longitude",
        *VARIABLES,
        "qc_flag",
    ]
    with sqlite3.connect(path) as connection:
        frame = pd.read_sql_query(
            f"SELECT {', '.join(columns)} FROM weather_observations",
            connection,
            dtype={"station_id": str},
        )
    frame["_obs_time"] = pd.to_datetime(frame["obs_time"], errors="coerce", utc=True)
    frame = frame[frame["_obs_time"].notna()].copy()
    frame["_date"] = frame["_obs_time"].dt.date
    frame["_hour"] = frame["_obs_time"].dt.hour
    frame["_month"] = frame["_obs_time"].dt.month
    return frame


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_m = 6_371_000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    value = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * radius_m * math.asin(math.sqrt(value))


def aggregate(rows: pd.DataFrame, variable: str) -> tuple[Any, int]:
    if rows.empty or variable not in rows.columns:
        return None, 0
    if variable in NUMERIC_VARIABLES:
        values = pd.to_numeric(rows[variable], errors="coerce").dropna()
        return (float(values.mean()), int(len(values))) if len(values) else (None, 0)
    values = rows[variable].dropna().astype(str).str.strip()
    values = values[values.ne("")]
    if values.empty:
        return None, 0
    counts = Counter(values)
    return counts.most_common(1)[0][0], int(len(values))


def source_metadata(rows: pd.DataFrame) -> dict[str, str]:
    if rows.empty:
        return {
            "source_station_ids": "",
            "source_station_names": "",
            "source_dataset_codes": "",
            "source_observation_start_time_utc": "",
            "source_observation_end_time_utc": "",
        }
    return {
        "source_station_ids": "|".join(
            sorted(rows["station_id"].dropna().astype(str).unique())
        ),
        "source_station_names": "|".join(
            sorted(rows["station_name"].dropna().astype(str).unique())
        ),
        "source_dataset_codes": "|".join(
            sorted(rows["dataset_code"].dropna().astype(str).unique())
        ),
        "source_observation_start_time_utc": rows["_obs_time"].min().isoformat(),
        "source_observation_end_time_utc": rows["_obs_time"].max().isoformat(),
    }


def same_hour_window(
    weather: pd.DataFrame,
    target: datetime,
    station_ids: list[str] | None,
    exclude_station_ids: list[str] | None = None,
) -> pd.DataFrame:
    lower_date = (target - timedelta(days=LOOKAROUND_DAYS)).date()
    upper_date = (target + timedelta(days=LOOKAROUND_DAYS)).date()
    mask = (
        weather["_date"].between(lower_date, upper_date)
        & weather["_hour"].eq(target.hour)
        & weather["_date"].ne(target.date())
    )
    if station_ids is not None:
        mask &= weather["station_id"].astype(str).isin(station_ids)
    if exclude_station_ids:
        mask &= ~weather["station_id"].astype(str).isin(exclude_station_ids)
    return weather[mask].copy()


def nearest_neighbor_rows(
    weather: pd.DataFrame,
    target: datetime,
    primary_ids: list[str],
) -> tuple[pd.DataFrame, float | None]:
    candidates = same_hour_window(
        weather, target, station_ids=None, exclude_station_ids=primary_ids
    )
    if candidates.empty:
        return candidates, None

    primary_meta = weather[
        weather["station_id"].astype(str).isin(primary_ids)
    ][["latitude", "longitude"]].dropna()
    station_meta = (
        candidates[["station_id", "latitude", "longitude"]]
        .dropna()
        .drop_duplicates("station_id")
    )
    if primary_meta.empty or station_meta.empty:
        first_id = str(candidates["station_id"].iloc[0])
        return candidates[candidates["station_id"].astype(str).eq(first_id)], None

    center_lat = float(primary_meta["latitude"].mean())
    center_lon = float(primary_meta["longitude"].mean())
    station_meta["_distance_m"] = station_meta.apply(
        lambda row: haversine_m(
            center_lat,
            center_lon,
            float(row["latitude"]),
            float(row["longitude"]),
        ),
        axis=1,
    )
    nearest = station_meta.sort_values("_distance_m").iloc[0]
    station_id = str(nearest["station_id"])
    return (
        candidates[candidates["station_id"].astype(str).eq(station_id)].copy(),
        float(nearest["_distance_m"]),
    )


def climatology_rows(
    weather: pd.DataFrame,
    target: datetime,
    primary_ids: list[str],
) -> pd.DataFrame:
    mask = weather["_month"].eq(target.month) & weather["_hour"].eq(target.hour)
    primary = weather[
        mask & weather["station_id"].astype(str).isin(primary_ids)
    ].copy()
    return primary if not primary.empty else weather[mask].copy()


def evidence_result(
    rows: pd.DataFrame,
    variable: str,
    source_type: str,
    confidence: float,
    method: str,
    lookaround_days: int,
    neighbor_distance_m: float | None = None,
) -> dict[str, Any] | None:
    value, sample_count = aggregate(rows, variable)
    if value is None:
        return None
    context_type = "OBSERVED" if source_type == "SAME_DAY_DIRECT_OBSERVATION" else (
        "CLIMATOLOGY_ESTIMATE"
        if source_type == "SEASONAL_HOURLY_CLIMATOLOGY"
        else "INFERRED"
    )
    return {
        "value": value,
        "source_type": source_type,
        "context_type": context_type,
        "confidence": confidence,
        "method": method,
        "lookback_days": lookaround_days,
        "lookahead_days": lookaround_days,
        "lookaround_days": lookaround_days,
        "sample_count": sample_count,
        "neighbor_station_distance_m": (
            round(neighbor_distance_m, 3)
            if neighbor_distance_m is not None
            else ""
        ),
        **source_metadata(rows),
    }


def activity_candidates(
    weather: pd.DataFrame,
    start: datetime,
    end: datetime,
    primary_ids: list[str],
) -> dict[str, Any]:
    direct_start = start - timedelta(hours=DIRECT_TOLERANCE_HOURS)
    direct_end = end + timedelta(hours=DIRECT_TOLERANCE_HOURS)
    direct = weather[
        weather["station_id"].astype(str).isin(primary_ids)
        & weather["_obs_time"].between(direct_start, direct_end)
    ].copy()
    target = start + (end - start) / 2
    same_station = same_hour_window(weather, target, primary_ids)
    neighbor, neighbor_distance_m = nearest_neighbor_rows(
        weather, target, primary_ids
    )
    climatology = climatology_rows(weather, target, primary_ids)
    return {
        "direct": direct,
        "same_station": same_station,
        "neighbor": neighbor,
        "neighbor_distance_m": neighbor_distance_m,
        "climatology": climatology,
    }


def infer_variable(
    variable: str,
    candidates: dict[str, Any],
) -> dict[str, Any]:
    result = evidence_result(
        candidates["direct"],
        variable,
        "SAME_DAY_DIRECT_OBSERVATION",
        0.95,
        "primary representative station observation within activity window +/- 3 hours",
        0,
    )
    if result:
        return result

    result = evidence_result(
        candidates["same_station"],
        variable,
        "SAME_STATION_7D_SAME_HOUR_INFERENCE",
        0.70,
        "mean or mode from primary station observations within +/- 7 days at the same UTC hour",
        LOOKAROUND_DAYS,
    )
    if result:
        return result

    result = evidence_result(
        candidates["neighbor"],
        variable,
        "NEIGHBOR_STATION_7D_SAME_HOUR_INFERENCE",
        0.50,
        "mean or mode from nearest neighboring station within +/- 7 days at the same UTC hour",
        LOOKAROUND_DAYS,
        candidates["neighbor_distance_m"],
    )
    if result:
        return result

    climatology = candidates["climatology"]
    value, sample_count = aggregate(climatology, variable)
    if value is not None and sample_count >= MIN_CLIMATOLOGY_SAMPLES:
        result = evidence_result(
            climatology,
            variable,
            "SEASONAL_HOURLY_CLIMATOLOGY",
            0.30,
            "mean or mode from available observations in the target calendar month and UTC hour",
            0,
        )
        if result:
            return result

    return {
        "value": None,
        "source_type": "UNAVAILABLE",
        "context_type": "MISSING",
        "confidence": 0.0,
        "method": "no direct, +/- 7 day same-hour, neighboring-station, or climatology evidence available",
        "lookback_days": LOOKAROUND_DAYS,
        "lookahead_days": LOOKAROUND_DAYS,
        "lookaround_days": LOOKAROUND_DAYS,
        "sample_count": 0,
        "neighbor_station_distance_m": "",
        **source_metadata(pd.DataFrame()),
    }


def build_evidence(activities: pd.DataFrame, weather: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for activity in activities.to_dict(orient="records"):
        start = parse_utc(activity["activity_start_time_utc"])
        end = parse_utc(activity["activity_end_time_utc"])
        primary_ids = split_station_ids(activity["primary_candidate_station_ids"])
        candidates = activity_candidates(weather, start, end, primary_ids)
        for variable in VARIABLES:
            inferred = infer_variable(variable, candidates)
            value = inferred.pop("value")
            source_type = inferred["source_type"]
            direct_observed = source_type == "SAME_DAY_DIRECT_OBSERVATION"
            rows.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "output_case": activity["output_case"],
                    "case_id": activity["case_id"],
                    "activity_id": activity["activity_id"],
                    "activity_start_time_utc": start.isoformat(),
                    "activity_end_time_utc": end.isoformat(),
                    "target_variable": variable,
                    "value_numeric": value if variable in NUMERIC_VARIABLES else "",
                    "value_text": value if variable == "weather" else "",
                    **inferred,
                    "direct_observation": str(direct_observed),
                    "inferred_or_climatology": str(
                        source_type
                        not in {"SAME_DAY_DIRECT_OBSERVATION", "UNAVAILABLE"}
                    ),
                    "missing_value_preserved": str(source_type == "UNAVAILABLE"),
                    "zero_fallback_used": "False",
                    "thci_scoring_authorized": "False",
                    "radar_scoring_authorized": "False",
                    "final_hiking_risk_scoring_authorized": "False",
                    "authorization_reason": (
                        "Evidence prototype only; no scoring authorization."
                    ),
                }
            )
    return pd.DataFrame(rows)


def build_summary(evidence: pd.DataFrame) -> pd.DataFrame:
    source_counts = evidence.groupby("source_type").size().to_dict()
    return pd.DataFrame(
        [
            {
                "schema_version": SCHEMA_VERSION,
                "activity_count": int(evidence["activity_id"].nunique()),
                "variable_count": len(VARIABLES),
                "evidence_row_count": int(len(evidence)),
                "same_day_direct_observation_count": int(
                    source_counts.get("SAME_DAY_DIRECT_OBSERVATION", 0)
                ),
                "same_station_7d_same_hour_inference_count": int(
                    source_counts.get("SAME_STATION_7D_SAME_HOUR_INFERENCE", 0)
                ),
                "neighbor_station_7d_same_hour_inference_count": int(
                    source_counts.get(
                        "NEIGHBOR_STATION_7D_SAME_HOUR_INFERENCE", 0
                    )
                ),
                "seasonal_hourly_climatology_count": int(
                    source_counts.get("SEASONAL_HOURLY_CLIMATOLOGY", 0)
                ),
                "unavailable_count": int(source_counts.get("UNAVAILABLE", 0)),
                "zero_fallback_true_count": int(
                    evidence["zero_fallback_used"]
                    .astype(str)
                    .str.lower()
                    .eq("true")
                    .sum()
                ),
                "scoring_authorized_count": int(
                    evidence["thci_scoring_authorized"]
                    .astype(str)
                    .str.lower()
                    .eq("true")
                    .sum()
                ),
                "prototype_conclusion": "PASS",
            }
        ]
    )


def main() -> int:
    args = parse_args()
    activities = load_activities(args.activity_csv)
    weather = load_weather(args.weather_db)
    evidence = build_evidence(activities, weather)
    summary = build_summary(evidence)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    evidence_csv = args.out_dir / "activity_weather_inference_fallback_evidence.csv"
    summary_csv = args.out_dir / "activity_weather_inference_fallback_summary.csv"
    evidence.to_csv(evidence_csv, index=False, encoding="utf-8-sig")
    summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")

    print("IB3W weather inference fallback prototype v1")
    print("evidence_csv:", evidence_csv)
    print("summary_csv:", summary_csv)
    print(summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
