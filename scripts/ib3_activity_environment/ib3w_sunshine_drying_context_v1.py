from __future__ import annotations

import sqlite3
from datetime import timedelta
from pathlib import Path

import pandas as pd


SCHEMA_VERSION = "ib3w_sunshine_drying_context_v1"

ANTECEDENT_CSV = Path(
    "outputs/ib3w_antecedent_precipitation_context_v1/"
    "activity_antecedent_precipitation_context.csv"
)

VECTOR_CSV = Path(
    "outputs/ib3w_weather_sensitive_feature_vector_v1/"
    "activity_weather_sensitive_feature_vector.csv"
)

WEATHER_DB = Path("weather/tw_weather_2026-05-01.sqlite3")
OUT_DIR = Path("outputs/ib3w_sunshine_drying_context_v1")

WINDOWS = {
    "6h": 6,
    "24h": 24,
}

SUNSHINE_AMOUNT_SEMANTICS = (
    "RAW_OBSERVED_SUNSHINE_DURATION_MIN_USED_AS_DRYING_CONTEXT_NOT_ZERO_IMPUTED"
)


def as_bool(value: object) -> bool:
    return str(value).strip().lower() == "true"


def as_num(value: object):
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return pd.NA
    return float(parsed)


def safe_str(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def split_stations(value: object) -> list[str]:
    if pd.isna(value):
        return []
    return [x.strip() for x in str(value).split("|") if x.strip()]


def fetch_weather_rows(
    conn: sqlite3.Connection,
    station_ids: list[str],
    start_utc: pd.Timestamp,
    end_utc: pd.Timestamp,
) -> pd.DataFrame:
    if not station_ids:
        return pd.DataFrame(
            columns=[
                "station_id",
                "station_name",
                "obs_time_utc",
                "temperature_c",
                "relative_humidity_pct",
                "wind_speed_ms",
                "wind_gust_ms",
                "sunshine_duration_min",
            ]
        )

    placeholders = ",".join(["?"] * len(station_ids))

    sql = f"""
    SELECT
      station_id,
      station_name,
      obs_time,
      temperature_c,
      relative_humidity_pct,
      wind_speed_ms,
      wind_gust_ms,
      sunshine_duration_min
    FROM weather_observations
    WHERE station_id IN ({placeholders})
      AND obs_time >= ?
      AND obs_time <= ?
    ORDER BY obs_time, station_id
    """

    params = station_ids + [start_utc.isoformat(), end_utc.isoformat()]
    df = pd.read_sql_query(sql, conn, params=params)

    if df.empty:
        return pd.DataFrame(
            columns=[
                "station_id",
                "station_name",
                "obs_time_utc",
                "temperature_c",
                "relative_humidity_pct",
                "wind_speed_ms",
                "wind_gust_ms",
                "sunshine_duration_min",
            ]
        )

    df["station_id"] = df["station_id"].astype(str).str.strip()
    df["station_name"] = df["station_name"].astype(str).str.strip()
    df["obs_time_utc"] = pd.to_datetime(df["obs_time"], errors="coerce", utc=True)

    for col in [
        "temperature_c",
        "relative_humidity_pct",
        "wind_speed_ms",
        "wind_gust_ms",
        "sunshine_duration_min",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["obs_time_utc"])
    df = df.drop_duplicates(subset=["station_id", "obs_time_utc"])

    return df[
        [
            "station_id",
            "station_name",
            "obs_time_utc",
            "temperature_c",
            "relative_humidity_pct",
            "wind_speed_ms",
            "wind_gust_ms",
            "sunshine_duration_min",
        ]
    ]


def summarize_window(
    rows: pd.DataFrame,
    station_ids: list[str],
    activity_start_utc: pd.Timestamp,
    label: str,
    hours: int,
) -> dict:
    start_utc = activity_start_utc - timedelta(hours=hours)
    end_utc = activity_start_utc

    win = rows[
        (rows["obs_time_utc"] >= start_utc)
        & (rows["obs_time_utc"] <= end_utc)
    ].copy()

    station_count = len(station_ids)

    def nonnull_count(col: str) -> int:
        if col not in win.columns:
            return 0
        return int(win[col].notna().sum())

    sunshine = win[win["sunshine_duration_min"].notna()].copy()

    if len(win) == 0:
        sunshine_status = "SUNSHINE_CONTEXT_NO_WEATHER_ROWS"
    elif sunshine.empty:
        sunshine_status = "SUNSHINE_CONTEXT_MISSING"
    else:
        sunshine_status = "SUNSHINE_CONTEXT_AVAILABLE"

    if sunshine.empty:
        sunshine_sum = pd.NA
        sunshine_max = pd.NA
        sunshine_mean = pd.NA
        sunshine_station_ids = ""
    else:
        sunshine_sum = round(float(sunshine["sunshine_duration_min"].sum()), 4)
        sunshine_max = round(float(sunshine["sunshine_duration_min"].max()), 4)
        sunshine_mean = round(float(sunshine["sunshine_duration_min"].mean()), 4)
        sunshine_station_ids = "|".join(
            sorted(sunshine["station_id"].dropna().astype(str).unique().tolist())
        )

    observed_station_ids = "|".join(
        sorted(win["station_id"].dropna().astype(str).unique().tolist())
    )

    return {
        f"drying_window_{label}_start_utc": start_utc.isoformat(),
        f"drying_window_{label}_end_utc": end_utc.isoformat(),
        f"drying_window_{label}_weather_row_count": int(len(win)),
        f"drying_window_{label}_observed_station_count": int(win["station_id"].nunique()) if not win.empty else 0,
        f"drying_window_{label}_missing_station_count": max(station_count - int(win["station_id"].nunique()), 0) if not win.empty else station_count,
        f"drying_window_{label}_observed_station_ids": observed_station_ids,
        f"sunshine_context_{label}_status": sunshine_status,
        f"sunshine_context_{label}_nonnull_row_count": nonnull_count("sunshine_duration_min"),
        f"sunshine_context_{label}_observed_station_ids": sunshine_station_ids,
        f"sunshine_duration_{label}_raw_sum_min": sunshine_sum,
        f"sunshine_duration_{label}_raw_max_min": sunshine_max,
        f"sunshine_duration_{label}_raw_mean_min": sunshine_mean,
        f"temperature_{label}_nonnull_row_count": nonnull_count("temperature_c"),
        f"temperature_{label}_mean_c": round(float(win["temperature_c"].mean()), 4) if nonnull_count("temperature_c") else pd.NA,
        f"relative_humidity_{label}_nonnull_row_count": nonnull_count("relative_humidity_pct"),
        f"relative_humidity_{label}_mean_pct": round(float(win["relative_humidity_pct"].mean()), 4) if nonnull_count("relative_humidity_pct") else pd.NA,
        f"wind_speed_{label}_nonnull_row_count": nonnull_count("wind_speed_ms"),
        f"wind_speed_{label}_mean_ms": round(float(win["wind_speed_ms"].mean()), 4) if nonnull_count("wind_speed_ms") else pd.NA,
        f"wind_speed_{label}_max_ms": round(float(win["wind_speed_ms"].max()), 4) if nonnull_count("wind_speed_ms") else pd.NA,
    }


def compute_drying_indices(row: pd.Series) -> tuple[float, float, list[str], list[str]]:
    drying = 0.0
    limiter = 0.0
    drying_evidence: list[str] = []
    limiter_evidence: list[str] = []

    temp = as_num(row.get("temperature_c_mean_primary"))
    rh = as_num(row.get("relative_humidity_pct_mean_primary"))
    wind = as_num(row.get("wind_speed_ms_mean_primary"))
    wind_max = as_num(row.get("wind_speed_ms_max_primary"))

    sunshine_6h = as_num(row.get("sunshine_duration_6h_raw_sum_min"))
    sunshine_24h = as_num(row.get("sunshine_duration_24h_raw_sum_min"))

    if not pd.isna(sunshine_6h):
        if sunshine_6h >= 120:
            drying += 1.0
            drying_evidence.append("6h sunshine raw sum >= 120 min")
        elif sunshine_6h >= 30:
            drying += 0.5
            drying_evidence.append("6h sunshine raw sum >= 30 min")
    elif not pd.isna(sunshine_24h):
        if sunshine_24h >= 240:
            drying += 1.0
            drying_evidence.append("24h sunshine raw sum >= 240 min")
        elif sunshine_24h >= 60:
            drying += 0.5
            drying_evidence.append("24h sunshine raw sum >= 60 min")
    else:
        limiter += 0.5
        limiter_evidence.append("sunshine unavailable, drying evidence incomplete")

    if not pd.isna(temp):
        if temp >= 25:
            drying += 1.0
            drying_evidence.append("temperature >= 25C")
        elif temp >= 18:
            drying += 0.5
            drying_evidence.append("temperature >= 18C")
        else:
            limiter += 0.5
            limiter_evidence.append("temperature < 18C")

    if not pd.isna(rh):
        if rh >= 90:
            limiter += 1.5
            limiter_evidence.append("relative humidity >= 90%, evaporation likely limited")
        elif rh >= 80:
            limiter += 1.0
            limiter_evidence.append("relative humidity >= 80%, evaporation may be limited")
        elif rh < 70:
            drying += 0.5
            drying_evidence.append("relative humidity < 70%")
    else:
        limiter += 0.5
        limiter_evidence.append("relative humidity unavailable")

    if not pd.isna(wind):
        if wind >= 5:
            drying += 1.0
            drying_evidence.append("mean wind speed >= 5 m/s")
        elif wind >= 2:
            drying += 0.5
            drying_evidence.append("mean wind speed >= 2 m/s")
        else:
            limiter += 0.5
            limiter_evidence.append("mean wind speed < 2 m/s")

    if not pd.isna(wind_max) and wind_max >= 5:
        drying += 0.5
        drying_evidence.append("max wind speed >= 5 m/s")

    return (
        round(float(drying), 4),
        round(float(limiter), 4),
        drying_evidence,
        limiter_evidence,
    )


def classify_drying_context(
    score_allowed: bool,
    sunshine_status_6h: str,
    sunshine_status_24h: str,
    drying_index: float,
    limiter_index: float,
) -> tuple[str, str]:
    if not score_allowed:
        return (
            "BLOCKED_BY_GATE",
            "Weather-sensitive feature gate did not allow drying context evaluation.",
        )

    sunshine_available = (
        sunshine_status_6h == "SUNSHINE_CONTEXT_AVAILABLE"
        or sunshine_status_24h == "SUNSHINE_CONTEXT_AVAILABLE"
    )

    if drying_index <= 0 and limiter_index > 0:
        return (
            "DRYING_CONTEXT_LIMITED_OR_MISSING",
            "Drying evidence is weak or missing, and limiting factors are present.",
        )

    if sunshine_available and drying_index > limiter_index:
        return (
            "DRYING_CONTEXT_FAVORABLE_WITH_SUNSHINE",
            "Sunshine and weather context suggest drying may be favorable.",
        )

    if sunshine_available and drying_index <= limiter_index:
        return (
            "DRYING_CONTEXT_PARTIAL_BUT_LIMITED_BY_HUMIDITY",
            "Sunshine exists, but humidity or other limiting factors reduce drying potential.",
        )

    if not sunshine_available and drying_index > limiter_index:
        return (
            "DRYING_CONTEXT_PARTIAL_WITHOUT_SUNSHINE",
            "Temperature and wind provide some drying evidence, but sunshine is unavailable.",
        )

    return (
        "DRYING_CONTEXT_LIMITED_WITHOUT_SUNSHINE",
        "Drying context is limited because sunshine is unavailable and limiting factors remain.",
    )


def build_context(antecedent: pd.DataFrame, vector: pd.DataFrame) -> pd.DataFrame:
    vector_cols = [
        "output_case",
        "activity_id",
        "temperature_c_mean_primary",
        "relative_humidity_pct_mean_primary",
        "wind_speed_ms_mean_primary",
        "wind_speed_ms_max_primary",
        "zero_fallback_true_count",
    ]
    vector_cols = [c for c in vector_cols if c in vector.columns]

    merged = antecedent.merge(
        vector[vector_cols],
        on=["output_case", "activity_id"],
        how="left",
        suffixes=("", "_vector"),
    )

    rows = []

    with sqlite3.connect(WEATHER_DB) as conn:
        for _, row in merged.iterrows():
            score_allowed = as_bool(row.get("weather_sensitive_score_allowed"))
            station_ids = split_stations(row.get("primary_candidate_station_ids"))

            out = {
                "schema_version": SCHEMA_VERSION,
                "output_case": row.get("output_case", ""),
                "case_id": row.get("case_id", ""),
                "activity_id": row.get("activity_id", ""),
                "activity_start_time_utc": row.get("activity_start_time_utc", ""),
                "activity_end_time_utc": row.get("activity_end_time_utc", ""),
                "weather_sensitive_score_allowed": score_allowed,
                "antecedent_precipitation_context_status": row.get("antecedent_precipitation_context_status", ""),
                "hours_since_last_observed_rain": row.get("hours_since_last_observed_rain", ""),
                "last_observed_rain_time_utc": row.get("last_observed_rain_time_utc", ""),
                "last_observed_rain_station_names": row.get("last_observed_rain_station_names", ""),
                "temperature_c_mean_primary": row.get("temperature_c_mean_primary", ""),
                "relative_humidity_pct_mean_primary": row.get("relative_humidity_pct_mean_primary", ""),
                "wind_speed_ms_mean_primary": row.get("wind_speed_ms_mean_primary", ""),
                "wind_speed_ms_max_primary": row.get("wind_speed_ms_max_primary", ""),
                "sunshine_amount_semantics": SUNSHINE_AMOUNT_SEMANTICS,
                "soil_moisture_claim_status": "NOT_CLAIMED_DRYING_CONTEXT_ONLY",
                "terrain_surface_context_status": "NOT_JOINED_IN_V1",
                "source_antecedent_csv": str(ANTECEDENT_CSV),
                "source_vector_csv": str(VECTOR_CSV),
                "source_weather_db": str(WEATHER_DB),
                "scope_note": "Sunshine and drying context only. No true soil moisture claim, no hiking risk score, no THCI, no terrain/surface join, no missing-to-zero imputation.",
            }

            if not score_allowed:
                for label in WINDOWS:
                    out.update({
                        f"drying_window_{label}_start_utc": "",
                        f"drying_window_{label}_end_utc": "",
                        f"drying_window_{label}_weather_row_count": 0,
                        f"sunshine_context_{label}_status": "BLOCKED_BY_GATE",
                        f"sunshine_context_{label}_nonnull_row_count": 0,
                        f"sunshine_duration_{label}_raw_sum_min": pd.NA,
                        f"sunshine_duration_{label}_raw_max_min": pd.NA,
                        f"sunshine_duration_{label}_raw_mean_min": pd.NA,
                    })
                out["drying_potential_index_v1"] = pd.NA
                out["drying_limiter_index_v1"] = pd.NA
                out["drying_context_status"] = "BLOCKED_BY_GATE"
                out["drying_context_reason"] = "Weather-sensitive feature gate did not allow drying context evaluation."
                out["drying_context_evidence"] = ""
                out["drying_limiter_evidence"] = ""
                out["zero_fallback_true_count"] = row.get("zero_fallback_true_count", row.get("zero_fallback_true_count_vector", 0))
                rows.append(out)
                continue

            activity_start = pd.to_datetime(
                row.get("activity_start_time_utc"),
                errors="coerce",
                utc=True,
            )
            if pd.isna(activity_start):
                raise ValueError(f"bad activity_start_time_utc: {row.get('activity_start_time_utc')}")

            weather_rows = fetch_weather_rows(
                conn,
                station_ids,
                activity_start - timedelta(hours=24),
                activity_start,
            )

            for label, hours in WINDOWS.items():
                out.update(
                    summarize_window(
                        weather_rows,
                        station_ids,
                        activity_start,
                        label,
                        hours,
                    )
                )

            drying_index, limiter_index, drying_evidence, limiter_evidence = compute_drying_indices(pd.Series(out))

            drying_status, drying_reason = classify_drying_context(
                score_allowed=score_allowed,
                sunshine_status_6h=safe_str(out.get("sunshine_context_6h_status")),
                sunshine_status_24h=safe_str(out.get("sunshine_context_24h_status")),
                drying_index=drying_index,
                limiter_index=limiter_index,
            )

            out["drying_potential_index_v1"] = drying_index
            out["drying_limiter_index_v1"] = limiter_index
            out["drying_context_status"] = drying_status
            out["drying_context_reason"] = drying_reason
            out["drying_context_evidence"] = " | ".join(drying_evidence)
            out["drying_limiter_evidence"] = " | ".join(limiter_evidence)
            out["zero_fallback_true_count"] = row.get("zero_fallback_true_count", row.get("zero_fallback_true_count_vector", 0))

            rows.append(out)

    return pd.DataFrame(rows)


def build_summary(context: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for col in [
        "drying_context_status",
        "sunshine_context_6h_status",
        "sunshine_context_24h_status",
        "soil_moisture_claim_status",
        "terrain_surface_context_status",
    ]:
        for key, group in context.groupby(col, dropna=False, sort=True):
            rows.append({
                "schema_version": SCHEMA_VERSION,
                "summary_type": col,
                "summary_key": key,
                "activity_count": int(len(group)),
                "score_allowed_count": int(
                    group["weather_sensitive_score_allowed"]
                    .astype(str)
                    .str.lower()
                    .eq("true")
                    .sum()
                ),
                "zero_fallback_true_count": int(
                    pd.to_numeric(group["zero_fallback_true_count"], errors="coerce")
                    .fillna(0)
                    .sum()
                ),
            })

    rows.append({
        "schema_version": SCHEMA_VERSION,
        "summary_type": "overall",
        "summary_key": "ALL_ACTIVITIES",
        "activity_count": int(len(context)),
        "score_allowed_count": int(
            context["weather_sensitive_score_allowed"]
            .astype(str)
            .str.lower()
            .eq("true")
            .sum()
        ),
        "zero_fallback_true_count": int(
            pd.to_numeric(context["zero_fallback_true_count"], errors="coerce")
            .fillna(0)
            .sum()
        ),
    })

    return pd.DataFrame(rows)


def html_table(df: pd.DataFrame) -> str:
    return df.fillna("").to_html(index=False, escape=True, border=0)


def build_html(context: pd.DataFrame, summary: pd.DataFrame) -> str:
    key_cols = [
        "output_case",
        "activity_id",
        "drying_context_status",
        "drying_context_reason",
        "drying_potential_index_v1",
        "drying_limiter_index_v1",
        "drying_context_evidence",
        "drying_limiter_evidence",
        "sunshine_context_6h_status",
        "sunshine_duration_6h_raw_sum_min",
        "sunshine_duration_6h_raw_max_min",
        "sunshine_context_24h_status",
        "sunshine_duration_24h_raw_sum_min",
        "sunshine_duration_24h_raw_max_min",
        "temperature_c_mean_primary",
        "relative_humidity_pct_mean_primary",
        "wind_speed_ms_mean_primary",
        "wind_speed_ms_max_primary",
        "hours_since_last_observed_rain",
        "last_observed_rain_time_utc",
        "soil_moisture_claim_status",
        "terrain_surface_context_status",
    ]

    allowed = context[
        context["weather_sensitive_score_allowed"]
        .astype(str)
        .str.lower()
        .eq("true")
    ].copy()

    zero_fallback = int(
        pd.to_numeric(context["zero_fallback_true_count"], errors="coerce")
        .fillna(0)
        .sum()
    )

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>IB3W Sunshine Drying Context v1</title>
<style>
body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; background: #f6f8fa; color: #1f2937; }}
section {{ background: white; border: 1px solid #d9e1e7; border-radius: 10px; padding: 18px; margin-bottom: 16px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
th, td {{ border: 1px solid #d9e1e7; padding: 6px 8px; text-align: left; vertical-align: top; }}
th {{ background: #edf2f5; }}
.wrap {{ overflow-x: auto; }}
</style>
</head>
<body>
<h1>IB3W Sunshine Drying Context v1</h1>
<section>
<p>Sunshine and drying context based on sunshine_duration_min, temperature, relative humidity, wind, and last observed rain timing.</p>
<p>No true soil moisture claim, no hiking risk score, no THCI, no terrain/surface join, no missing-to-zero imputation.</p>
<p>Sunshine semantics: {SUNSHINE_AMOUNT_SEMANTICS}</p>
<p>Total activities: {len(context)}; evaluated activities: {len(allowed)}; zero fallback violations: {zero_fallback}</p>
</section>
<section>
<h2>Evaluated rows</h2>
<div class="wrap">{html_table(allowed[key_cols])}</div>
</section>
<section>
<h2>Full drying context review</h2>
<div class="wrap">{html_table(context[key_cols])}</div>
</section>
<section>
<h2>Summary</h2>
<div class="wrap">{html_table(summary)}</div>
</section>
</body>
</html>
"""


def main() -> None:
    if not ANTECEDENT_CSV.exists():
        raise FileNotFoundError(f"antecedent CSV not found: {ANTECEDENT_CSV}")
    if not VECTOR_CSV.exists():
        raise FileNotFoundError(f"vector CSV not found: {VECTOR_CSV}")
    if not WEATHER_DB.exists():
        raise FileNotFoundError(f"weather DB not found: {WEATHER_DB}")

    antecedent = pd.read_csv(ANTECEDENT_CSV, dtype=str)
    vector = pd.read_csv(VECTOR_CSV, dtype=str)

    context = build_context(antecedent, vector)
    summary = build_summary(context)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    context_csv = OUT_DIR / "activity_sunshine_drying_context.csv"
    summary_csv = OUT_DIR / "activity_sunshine_drying_context_summary.csv"
    html_report = OUT_DIR / "activity_sunshine_drying_context_report.html"

    context.to_csv(context_csv, index=False, encoding="utf-8-sig")
    summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")
    html_report.write_text(build_html(context, summary), encoding="utf-8")

    print("IB3W sunshine drying context v1 written")
    print("context_csv:", context_csv)
    print("summary_csv:", summary_csv)
    print("html_report:", html_report)
    print()
    print("drying_context_status_distribution:")
    print(
        context.groupby("drying_context_status")
        .size()
        .reset_index(name="activity_count")
        .sort_values("activity_count", ascending=False)
        .to_string(index=False)
    )
    print()
    print("zero_fallback_true_total:", int(
        pd.to_numeric(context["zero_fallback_true_count"], errors="coerce")
        .fillna(0)
        .sum()
    ))


if __name__ == "__main__":
    main()
