from __future__ import annotations

import sqlite3
from datetime import timedelta
from pathlib import Path

import pandas as pd


SCHEMA_VERSION = "ib3w_antecedent_precipitation_context_v1"

VECTOR_CSV = Path(
    "outputs/ib3w_weather_sensitive_feature_vector_v1/"
    "activity_weather_sensitive_feature_vector.csv"
)

WEATHER_DB = Path("weather/tw_weather_2026-05-01.sqlite3")
OUT_DIR = Path("outputs/ib3w_antecedent_precipitation_context_v1")

LOOKBACK_WINDOWS = {
    "6h": 6,
    "24h": 24,
    "72h": 72,
    "7d": 168,
}

PRECIPITATION_AMOUNT_SEMANTICS = (
    "RAW_OBSERVED_PRECIPITATION_MM_NOT_SUMMED_AS_LOOKBACK_ACCUMULATION"
)


def as_bool(value: object) -> bool:
    return str(value).strip().lower() == "true"


def safe_int(value: object) -> int:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return 0 if pd.isna(parsed) else int(parsed)


def split_stations(value: object) -> list[str]:
    if pd.isna(value):
        return []
    return [x.strip() for x in str(value).split("|") if x.strip()]


def fetch_precipitation(
    conn: sqlite3.Connection,
    station_ids: list[str],
    start_utc: pd.Timestamp,
    end_utc: pd.Timestamp,
) -> pd.DataFrame:
    if not station_ids:
        return pd.DataFrame(columns=["station_id", "station_name", "obs_time_utc", "precipitation_mm"])

    placeholders = ",".join(["?"] * len(station_ids))
    sql = f"""
    SELECT
      station_id,
      station_name,
      obs_time,
      precipitation_mm
    FROM weather_observations
    WHERE station_id IN ({placeholders})
      AND obs_time >= ?
      AND obs_time <= ?
    ORDER BY obs_time, station_id
    """

    params = station_ids + [start_utc.isoformat(), end_utc.isoformat()]
    df = pd.read_sql_query(sql, conn, params=params)

    if df.empty:
        return pd.DataFrame(columns=["station_id", "station_name", "obs_time_utc", "precipitation_mm"])

    df["station_id"] = df["station_id"].astype(str).str.strip()
    df["station_name"] = df["station_name"].astype(str).str.strip()
    df["obs_time_utc"] = pd.to_datetime(df["obs_time"], errors="coerce", utc=True)
    df["precipitation_mm"] = pd.to_numeric(df["precipitation_mm"], errors="coerce")
    df = df.dropna(subset=["obs_time_utc"])

    # Defensive: DB diagnosis found no duplicates, but keep this safeguard.
    df = df.drop_duplicates(subset=["station_id", "obs_time_utc"])

    return df[["station_id", "station_name", "obs_time_utc", "precipitation_mm"]]


def summarize_window(
    obs: pd.DataFrame,
    station_ids: list[str],
    activity_start_utc: pd.Timestamp,
    label: str,
    hours: int,
) -> dict:
    start_utc = activity_start_utc - timedelta(hours=hours)
    end_utc = activity_start_utc

    rows = obs[
        (obs["obs_time_utc"] >= start_utc)
        & (obs["obs_time_utc"] <= end_utc)
    ].copy()

    nonnull = rows[rows["precipitation_mm"].notna()].copy()
    positive = nonnull[nonnull["precipitation_mm"] > 0].copy()
    zero = nonnull[nonnull["precipitation_mm"] == 0].copy()

    observed_station_ids = sorted(nonnull["station_id"].dropna().astype(str).unique().tolist())
    positive_station_ids = sorted(positive["station_id"].dropna().astype(str).unique().tolist())

    if len(nonnull) == 0:
        status = "PRECIPITATION_LOOKBACK_MISSING"
        max_observed = pd.NA
        mean_observed = pd.NA
    elif len(positive) > 0:
        status = "PRECIPITATION_LOOKBACK_OBSERVED_RAIN"
        max_observed = round(float(nonnull["precipitation_mm"].max()), 4)
        mean_observed = round(float(nonnull["precipitation_mm"].mean()), 4)
    elif len(zero) > 0:
        status = "PRECIPITATION_LOOKBACK_OBSERVED_NO_RAIN"
        max_observed = round(float(nonnull["precipitation_mm"].max()), 4)
        mean_observed = round(float(nonnull["precipitation_mm"].mean()), 4)
    else:
        status = "PRECIPITATION_LOOKBACK_REVIEW_REQUIRED"
        max_observed = pd.NA
        mean_observed = pd.NA

    return {
        f"rain_lookback_{label}_start_utc": start_utc.isoformat(),
        f"rain_lookback_{label}_end_utc": end_utc.isoformat(),
        f"rain_lookback_{label}_status": status,
        f"rain_lookback_{label}_row_count": int(len(rows)),
        f"rain_lookback_{label}_nonnull_row_count": int(len(nonnull)),
        f"rain_lookback_{label}_null_row_count": int(len(rows) - len(nonnull)),
        f"rain_lookback_{label}_observed_station_count": int(len(observed_station_ids)),
        f"rain_lookback_{label}_positive_station_count": int(len(positive_station_ids)),
        f"rain_lookback_{label}_missing_station_count": max(len(station_ids) - len(observed_station_ids), 0),
        f"rain_lookback_{label}_observed_station_ids": "|".join(observed_station_ids),
        f"rain_lookback_{label}_positive_station_ids": "|".join(positive_station_ids),
        f"rain_lookback_{label}_zero_observation_count": int(len(zero)),
        f"rain_lookback_{label}_positive_observation_count": int(len(positive)),
        f"rain_lookback_{label}_max_observed_precipitation_mm": max_observed,
        f"rain_lookback_{label}_mean_observed_precipitation_mm": mean_observed,
        f"rain_lookback_{label}_observed_any": bool(len(nonnull) > 0),
        f"rain_lookback_{label}_positive_observed_flag": bool(len(positive) > 0),
        f"rain_lookback_{label}_observed_zero_flag": bool(len(nonnull) > 0 and len(positive) == 0 and len(zero) > 0),
    }


def summarize_last_rain_and_dates(
    obs: pd.DataFrame,
    activity_start_utc: pd.Timestamp,
) -> dict:
    start_utc = activity_start_utc - timedelta(hours=168)

    rows = obs[
        (obs["obs_time_utc"] >= start_utc)
        & (obs["obs_time_utc"] <= activity_start_utc)
        & (obs["precipitation_mm"].notna())
    ].copy()

    positive = rows[rows["precipitation_mm"] > 0].copy()

    if positive.empty:
        return {
            "positive_rain_local_dates_count_lookback_7d": 0,
            "positive_rain_local_dates_lookback_7d": "",
            "max_observed_precipitation_lookback_7d_mm": pd.NA,
            "hours_since_last_observed_rain": pd.NA,
            "last_observed_rain_time_utc": "",
            "last_observed_rain_station_ids": "",
            "last_observed_rain_station_names": "",
            "last_observed_rain_precipitation_mm_max": pd.NA,
        }

    positive["local_date_taipei"] = positive["obs_time_utc"].dt.tz_convert("Asia/Taipei").dt.date.astype(str)

    local_dates = sorted(positive["local_date_taipei"].dropna().astype(str).unique().tolist())
    last_time = positive["obs_time_utc"].max()
    last_rows = positive[positive["obs_time_utc"] == last_time].copy()

    return {
        "positive_rain_local_dates_count_lookback_7d": int(len(local_dates)),
        "positive_rain_local_dates_lookback_7d": "|".join(local_dates),
        "max_observed_precipitation_lookback_7d_mm": round(float(positive["precipitation_mm"].max()), 4),
        "hours_since_last_observed_rain": round((activity_start_utc - last_time).total_seconds() / 3600.0, 3),
        "last_observed_rain_time_utc": last_time.isoformat(),
        "last_observed_rain_station_ids": "|".join(sorted(last_rows["station_id"].astype(str).unique().tolist())),
        "last_observed_rain_station_names": "|".join(sorted(last_rows["station_name"].astype(str).unique().tolist())),
        "last_observed_rain_precipitation_mm_max": round(float(last_rows["precipitation_mm"].max()), 4),
    }


def classify_overall(out: dict, score_allowed: bool) -> tuple[str, str]:
    if not score_allowed:
        return (
            "BLOCKED_BY_GATE",
            "Weather-sensitive feature gate did not allow scoring; antecedent precipitation was not evaluated.",
        )

    if out.get("rain_lookback_7d_status") == "PRECIPITATION_LOOKBACK_MISSING":
        return (
            "ANTECEDENT_PRECIPITATION_MISSING",
            "No non-null precipitation observations were available in the 7-day lookback window.",
        )

    if out.get("rain_lookback_7d_positive_observed_flag") is True:
        return (
            "ANTECEDENT_PRECIPITATION_OBSERVED_RAIN",
            "At least one positive precipitation observation was found in the 7-day lookback window.",
        )

    if out.get("rain_lookback_7d_observed_zero_flag") is True:
        return (
            "ANTECEDENT_PRECIPITATION_OBSERVED_NO_RAIN",
            "Precipitation observations exist in the 7-day lookback window, and all observed values were zero.",
        )

    return (
        "ANTECEDENT_PRECIPITATION_REVIEW_REQUIRED",
        "Lookback observations exist but did not match expected rain/no-rain patterns.",
    )


def classify_data_quality(out: dict, station_count_policy: int, score_allowed: bool) -> str:
    if not score_allowed:
        return "BLOCKED_BY_GATE"

    observed_station_count = int(out.get("rain_lookback_7d_observed_station_count", 0))

    if observed_station_count <= 0:
        return "ANTECEDENT_PRECIPITATION_DATA_MISSING"

    if station_count_policy > 0 and observed_station_count < station_count_policy:
        return "ANTECEDENT_PRECIPITATION_DATA_PARTIAL"

    return "ANTECEDENT_PRECIPITATION_DATA_FULL"


def blocked_window_fields(label: str) -> dict:
    return {
        f"rain_lookback_{label}_status": "BLOCKED_BY_GATE",
        f"rain_lookback_{label}_row_count": 0,
        f"rain_lookback_{label}_nonnull_row_count": 0,
        f"rain_lookback_{label}_null_row_count": 0,
        f"rain_lookback_{label}_observed_station_count": 0,
        f"rain_lookback_{label}_positive_station_count": 0,
        f"rain_lookback_{label}_missing_station_count": pd.NA,
        f"rain_lookback_{label}_observed_station_ids": "",
        f"rain_lookback_{label}_positive_station_ids": "",
        f"rain_lookback_{label}_zero_observation_count": 0,
        f"rain_lookback_{label}_positive_observation_count": 0,
        f"rain_lookback_{label}_max_observed_precipitation_mm": pd.NA,
        f"rain_lookback_{label}_mean_observed_precipitation_mm": pd.NA,
        f"rain_lookback_{label}_observed_any": False,
        f"rain_lookback_{label}_positive_observed_flag": False,
        f"rain_lookback_{label}_observed_zero_flag": False,
    }


def build_context(vector: pd.DataFrame) -> pd.DataFrame:
    rows = []

    with sqlite3.connect(WEATHER_DB) as conn:
        for _, row in vector.iterrows():
            score_allowed = as_bool(row.get("weather_sensitive_score_allowed"))
            station_ids = split_stations(row.get("primary_candidate_station_ids"))
            station_count_policy = len(station_ids)

            out = {
                "schema_version": SCHEMA_VERSION,
                "output_case": row.get("output_case", ""),
                "case_id": row.get("case_id", ""),
                "activity_id": row.get("activity_id", ""),
                "activity_start_time_utc": row.get("activity_start_time_utc", ""),
                "activity_end_time_utc": row.get("activity_end_time_utc", ""),
                "activity_duration_min": row.get("activity_duration_min", ""),
                "weather_feature_vector_status": row.get("weather_feature_vector_status", ""),
                "weather_sensitive_score_allowed": score_allowed,
                "weather_sensitive_feature_gate": row.get("weather_sensitive_feature_gate", ""),
                "zero_fallback_true_count": safe_int(row.get("zero_fallback_true_count", 0)),
                "primary_candidate_station_ids": "|".join(station_ids),
                "primary_station_count_policy": station_count_policy,
                "precipitation_amount_semantics": PRECIPITATION_AMOUNT_SEMANTICS,
                "source_weather_db": str(WEATHER_DB),
                "source_vector_csv": str(VECTOR_CSV),
                "scope_note": "Lookback precipitation observation context only. No risk score, no THCI, no final surface wetness judgment, no missing-to-zero imputation.",
            }

            if not score_allowed:
                for label in LOOKBACK_WINDOWS:
                    out.update(blocked_window_fields(label))
                out.update({
                    "positive_rain_local_dates_count_lookback_7d": pd.NA,
                    "positive_rain_local_dates_lookback_7d": "",
                    "max_observed_precipitation_lookback_7d_mm": pd.NA,
                    "hours_since_last_observed_rain": pd.NA,
                    "last_observed_rain_time_utc": "",
                    "last_observed_rain_station_ids": "",
                    "last_observed_rain_station_names": "",
                    "last_observed_rain_precipitation_mm_max": pd.NA,
                })
                status, reason = classify_overall(out, score_allowed)
                out["antecedent_precipitation_context_status"] = status
                out["antecedent_precipitation_context_reason"] = reason
                out["antecedent_precipitation_data_quality"] = classify_data_quality(out, station_count_policy, score_allowed)
                rows.append(out)
                continue

            activity_start_utc = pd.to_datetime(row.get("activity_start_time_utc"), errors="coerce", utc=True)
            if pd.isna(activity_start_utc):
                raise ValueError(f"bad activity_start_time_utc: {row.get('activity_start_time_utc')}")

            obs = fetch_precipitation(
                conn,
                station_ids,
                activity_start_utc - timedelta(hours=168),
                activity_start_utc,
            )

            for label, hours in LOOKBACK_WINDOWS.items():
                out.update(summarize_window(obs, station_ids, activity_start_utc, label, hours))

            out.update(summarize_last_rain_and_dates(obs, activity_start_utc))

            status, reason = classify_overall(out, score_allowed)
            out["antecedent_precipitation_context_status"] = status
            out["antecedent_precipitation_context_reason"] = reason
            out["antecedent_precipitation_data_quality"] = classify_data_quality(out, station_count_policy, score_allowed)

            rows.append(out)

    return pd.DataFrame(rows)


def build_summary(context: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for col in [
        "antecedent_precipitation_context_status",
        "antecedent_precipitation_data_quality",
        "rain_lookback_6h_status",
        "rain_lookback_24h_status",
        "rain_lookback_72h_status",
        "rain_lookback_7d_status",
    ]:
        for key, group in context.groupby(col, dropna=False, sort=True):
            rows.append({
                "schema_version": SCHEMA_VERSION,
                "summary_type": col,
                "summary_key": key,
                "activity_count": int(len(group)),
                "score_allowed_count": int(group["weather_sensitive_score_allowed"].astype(str).str.lower().eq("true").sum()),
                "zero_fallback_true_count": int(pd.to_numeric(group["zero_fallback_true_count"], errors="coerce").fillna(0).sum()),
            })

    rows.append({
        "schema_version": SCHEMA_VERSION,
        "summary_type": "overall",
        "summary_key": "ALL_ACTIVITIES",
        "activity_count": int(len(context)),
        "score_allowed_count": int(context["weather_sensitive_score_allowed"].astype(str).str.lower().eq("true").sum()),
        "zero_fallback_true_count": int(pd.to_numeric(context["zero_fallback_true_count"], errors="coerce").fillna(0).sum()),
    })

    return pd.DataFrame(rows)


def html_table(df: pd.DataFrame) -> str:
    return df.fillna("").to_html(index=False, escape=True, border=0)


def build_html(context: pd.DataFrame, summary: pd.DataFrame) -> str:
    key_cols = [
        "output_case",
        "activity_id",
        "weather_sensitive_score_allowed",
        "antecedent_precipitation_context_status",
        "antecedent_precipitation_data_quality",
        "precipitation_amount_semantics",
        "rain_lookback_6h_status",
        "rain_lookback_6h_max_observed_precipitation_mm",
        "rain_lookback_24h_status",
        "rain_lookback_24h_max_observed_precipitation_mm",
        "rain_lookback_72h_status",
        "rain_lookback_72h_max_observed_precipitation_mm",
        "rain_lookback_7d_status",
        "rain_lookback_7d_max_observed_precipitation_mm",
        "positive_rain_local_dates_count_lookback_7d",
        "positive_rain_local_dates_lookback_7d",
        "max_observed_precipitation_lookback_7d_mm",
        "hours_since_last_observed_rain",
        "last_observed_rain_time_utc",
        "last_observed_rain_station_ids",
        "last_observed_rain_station_names",
        "last_observed_rain_precipitation_mm_max",
        "antecedent_precipitation_context_reason",
    ]

    allowed = context[context["weather_sensitive_score_allowed"].astype(str).str.lower().eq("true")].copy()

    total = len(context)
    evaluated = len(allowed)
    zero_fallback = int(pd.to_numeric(context["zero_fallback_true_count"], errors="coerce").fillna(0).sum())

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>IB3W Antecedent Precipitation Context v1</title>
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
<h1>IB3W Antecedent Precipitation Context v1</h1>
<section>
<p>Lookback precipitation observation context before activity_start_time_utc. No risk score, no THCI, no final surface wetness judgment, no missing-to-zero imputation.</p>
<p>Precipitation amount semantics: {PRECIPITATION_AMOUNT_SEMANTICS}</p>
<p>Total activities: {total}; evaluated activities: {evaluated}; zero fallback violations: {zero_fallback}</p>
</section>
<section>
<h2>Evaluated rows</h2>
<div class="wrap">{html_table(allowed[key_cols])}</div>
</section>
<section>
<h2>Full context review</h2>
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
    if not VECTOR_CSV.exists():
        raise FileNotFoundError(f"vector CSV not found: {VECTOR_CSV}")
    if not WEATHER_DB.exists():
        raise FileNotFoundError(f"weather DB not found: {WEATHER_DB}")

    vector = pd.read_csv(VECTOR_CSV, dtype=str)
    context = build_context(vector)
    summary = build_summary(context)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    context_csv = OUT_DIR / "activity_antecedent_precipitation_context.csv"
    summary_csv = OUT_DIR / "activity_antecedent_precipitation_context_summary.csv"
    html_report = OUT_DIR / "activity_antecedent_precipitation_context_report.html"

    context.to_csv(context_csv, index=False, encoding="utf-8-sig")
    summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")
    html_report.write_text(build_html(context, summary), encoding="utf-8")

    print("IB3W antecedent precipitation context v1 written")
    print("weather_db:", WEATHER_DB)
    print("context_csv:", context_csv)
    print("summary_csv:", summary_csv)
    print("html_report:", html_report)
    print()
    print("antecedent_precipitation_context_status_distribution:")
    print(
        context.groupby("antecedent_precipitation_context_status")
        .size()
        .reset_index(name="activity_count")
        .sort_values("activity_count", ascending=False)
        .to_string(index=False)
    )
    print()
    print("zero_fallback_true_total:", int(pd.to_numeric(context["zero_fallback_true_count"], errors="coerce").fillna(0).sum()))


if __name__ == "__main__":
    main()
