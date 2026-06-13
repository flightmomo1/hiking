from __future__ import annotations

import sqlite3
from pathlib import Path
import pandas as pd


SCHEMA_VERSION = "ib3w_heat_humid_stress_context_v1"

ANTECEDENT_CSV = Path("outputs/ib3w_antecedent_precipitation_context_v1/activity_antecedent_precipitation_context.csv")
VECTOR_CSV = Path("outputs/ib3w_weather_sensitive_feature_vector_v1/activity_weather_sensitive_feature_vector.csv")
FOG_PROXY_CSV = Path("outputs/ib3w_fog_low_cloud_condition_proxy_v1/activity_fog_low_cloud_condition_proxy.csv")
WET_COLD_CSV = Path("outputs/ib3w_wet_cold_exposure_context_v1/activity_wet_cold_exposure_context.csv")
WEATHER_DB = Path("weather/tw_weather_2026-05-01.sqlite3")
OUT_DIR = Path("outputs/ib3w_heat_humid_stress_context_v1")


def as_bool(value) -> bool:
    return str(value).strip().lower() == "true"


def split_stations(value) -> list[str]:
    if pd.isna(value):
        return []
    return [x.strip() for x in str(value).split("|") if x.strip()]


def num(value):
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return pd.NA if pd.isna(parsed) else float(parsed)


def safe(value) -> str:
    return "" if pd.isna(value) else str(value).strip()


def wind_class(wind_ms):
    if pd.isna(wind_ms):
        return "WIND_UNKNOWN"
    wind_ms = float(wind_ms)
    if wind_ms < 0.5:
        return "CALM_LT_0P5_MS"
    if wind_ms < 2:
        return "LIGHT_0P5_TO_2_MS"
    if wind_ms <= 5:
        return "GENTLE_2_TO_5_MS"
    return "STRONG_GT_5_MS"


def heat_index_proxy_c(temp_c, rh_pct):
    if pd.isna(temp_c) or pd.isna(rh_pct):
        return "HEAT_INDEX_NOT_COMPUTED_INPUT_MISSING", pd.NA

    temp_c = float(temp_c)
    rh_pct = float(rh_pct)

    if temp_c < 26.7:
        return "HEAT_INDEX_NOT_COMPUTED_TEMPERATURE_BELOW_STANDARD_THRESHOLD", pd.NA
    if rh_pct < 40:
        return "HEAT_INDEX_NOT_COMPUTED_RH_BELOW_STANDARD_THRESHOLD", pd.NA

    t = temp_c * 9.0 / 5.0 + 32.0
    rh = rh_pct

    hi_f = (
        -42.379
        + 2.04901523 * t
        + 10.14333127 * rh
        - 0.22475541 * t * rh
        - 0.00683783 * t * t
        - 0.05481717 * rh * rh
        + 0.00122874 * t * t * rh
        + 0.00085282 * t * rh * rh
        - 0.00000199 * t * t * rh * rh
    )
    hi_c = (hi_f - 32.0) * 5.0 / 9.0
    return "HEAT_INDEX_COMPUTED_STANDARD_PROXY_NOT_WBGT", round(float(hi_c), 4)


def fetch_weather(conn, station_ids, start_utc, end_utc) -> pd.DataFrame:
    if not station_ids:
        return pd.DataFrame()

    placeholders = ",".join(["?"] * len(station_ids))
    sql = f"""
    SELECT
      station_id,
      station_name,
      obs_time,
      temperature_c,
      relative_humidity_pct,
      wind_speed_ms,
      wind_direction_deg,
      precipitation_mm,
      sunshine_duration_min,
      uv_index
    FROM weather_observations
    WHERE station_id IN ({placeholders})
      AND obs_time >= ?
      AND obs_time <= ?
    ORDER BY obs_time, station_id
    """

    params = station_ids + [start_utc.isoformat(), end_utc.isoformat()]
    df = pd.read_sql_query(sql, conn, params=params)

    if df.empty:
        return df

    df["station_id"] = df["station_id"].astype(str).str.strip()
    df["station_name"] = df["station_name"].astype(str).str.strip()
    df["obs_time_utc"] = pd.to_datetime(df["obs_time"], errors="coerce", utc=True)
    df["obs_time_local"] = df["obs_time_utc"] + pd.Timedelta(hours=8)
    df["obs_local_hour"] = df["obs_time_local"].dt.hour

    for col in [
        "temperature_c",
        "relative_humidity_pct",
        "wind_speed_ms",
        "wind_direction_deg",
        "precipitation_mm",
        "sunshine_duration_min",
        "uv_index",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.dropna(subset=["obs_time_utc"]).drop_duplicates(subset=["station_id", "obs_time_utc"])


def summarize_weather(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "activity_weather_row_count": 0,
            "activity_observed_station_count": 0,
            "activity_observed_station_ids": "",
            "temperature_nonnull_count": 0,
            "temperature_mean_c": pd.NA,
            "temperature_max_c": pd.NA,
            "relative_humidity_nonnull_count": 0,
            "relative_humidity_mean_pct": pd.NA,
            "relative_humidity_max_pct": pd.NA,
            "wind_speed_nonnull_count": 0,
            "wind_speed_mean_ms": pd.NA,
            "wind_speed_max_ms": pd.NA,
            "wind_class": "WIND_UNKNOWN",
            "precipitation_nonnull_count": 0,
            "precipitation_positive_row_count": 0,
            "precipitation_max_observed_mm": pd.NA,
            "daytime_heat_window_row_count": 0,
            "daytime_heat_window_ratio": pd.NA,
            "sunshine_duration_available_row_count": 0,
            "uv_index_available_row_count": 0,
        }

    temp = pd.to_numeric(df["temperature_c"], errors="coerce").dropna()
    rh = pd.to_numeric(df["relative_humidity_pct"], errors="coerce").dropna()
    wind = pd.to_numeric(df["wind_speed_ms"], errors="coerce").dropna()
    rain = pd.to_numeric(df["precipitation_mm"], errors="coerce").dropna()
    sun = pd.to_numeric(df["sunshine_duration_min"], errors="coerce").dropna()
    uv = pd.to_numeric(df["uv_index"], errors="coerce").dropna()
    daytime = df[df["obs_local_hour"].between(9, 15, inclusive="both")]

    wind_mean = round(float(wind.mean()), 4) if len(wind) else pd.NA

    return {
        "activity_weather_row_count": int(len(df)),
        "activity_observed_station_count": int(df["station_id"].nunique()),
        "activity_observed_station_ids": "|".join(sorted(df["station_id"].dropna().astype(str).unique().tolist())),
        "temperature_nonnull_count": int(len(temp)),
        "temperature_mean_c": round(float(temp.mean()), 4) if len(temp) else pd.NA,
        "temperature_max_c": round(float(temp.max()), 4) if len(temp) else pd.NA,
        "relative_humidity_nonnull_count": int(len(rh)),
        "relative_humidity_mean_pct": round(float(rh.mean()), 4) if len(rh) else pd.NA,
        "relative_humidity_max_pct": round(float(rh.max()), 4) if len(rh) else pd.NA,
        "wind_speed_nonnull_count": int(len(wind)),
        "wind_speed_mean_ms": wind_mean,
        "wind_speed_max_ms": round(float(wind.max()), 4) if len(wind) else pd.NA,
        "wind_class": wind_class(wind_mean),
        "precipitation_nonnull_count": int(len(rain)),
        "precipitation_positive_row_count": int((rain > 0).sum()) if len(rain) else 0,
        "precipitation_max_observed_mm": round(float(rain.max()), 4) if len(rain) else pd.NA,
        "daytime_heat_window_row_count": int(len(daytime)),
        "daytime_heat_window_ratio": round(float(len(daytime) / len(df)), 4) if len(df) else pd.NA,
        "sunshine_duration_available_row_count": int(len(sun)),
        "uv_index_available_row_count": int(len(uv)),
    }


def score_heat(row: dict):
    score = 0.0
    evidence = [
        "SUNSHINE_DURATION_UNAVAILABLE_IN_CURRENT_DB",
        "UV_INDEX_UNAVAILABLE_IN_CURRENT_DB",
        "WBGT_NOT_COMPUTED_NO_SOLAR_RADIATION_GLOBE_TEMPERATURE_OR_HUMAN_HEAT_BALANCE_INPUTS",
    ]

    temp_mean = num(row.get("temperature_mean_c"))
    temp_max = num(row.get("temperature_max_c"))
    rh_mean = num(row.get("relative_humidity_mean_pct"))
    rh_max = num(row.get("relative_humidity_max_pct"))
    wind_mean = num(row.get("wind_speed_mean_ms"))
    daytime_ratio = num(row.get("daytime_heat_window_ratio"))
    heat_index = num(row.get("heat_index_c"))

    if not pd.isna(temp_mean):
        if temp_mean >= 32:
            score += 4.0
            evidence.append("temperature mean >= 32C")
        elif temp_mean >= 30:
            score += 3.0
            evidence.append("temperature mean >= 30C")
        elif temp_mean >= 28:
            score += 2.0
            evidence.append("temperature mean >= 28C")
        elif temp_mean >= 26:
            score += 1.0
            evidence.append("temperature mean >= 26C")
        elif temp_mean >= 24:
            score += 0.5
            evidence.append("temperature mean >= 24C")

    if not pd.isna(temp_max):
        if temp_max >= 35:
            score += 2.0
            evidence.append("temperature max >= 35C")
        elif temp_max >= 32:
            score += 1.5
            evidence.append("temperature max >= 32C")
        elif temp_max >= 30:
            score += 1.0
            evidence.append("temperature max >= 30C")
        elif temp_max >= 28:
            score += 0.5
            evidence.append("temperature max >= 28C")

    if not pd.isna(heat_index):
        if heat_index >= 40:
            score += 3.0
            evidence.append("computed heat index >= 40C")
        elif heat_index >= 35:
            score += 2.0
            evidence.append("computed heat index >= 35C")
        elif heat_index >= 32:
            score += 1.0
            evidence.append("computed heat index >= 32C")

    if not pd.isna(rh_mean):
        if rh_mean >= 85:
            score += 1.0
            evidence.append("relative humidity mean >= 85%")
        elif rh_mean >= 75:
            score += 0.5
            evidence.append("relative humidity mean >= 75%")

    if not pd.isna(rh_max) and rh_max >= 90:
        score += 0.25
        evidence.append("relative humidity max >= 90%")

    if not pd.isna(wind_mean):
        if wind_mean < 0.5:
            score += 0.75
            evidence.append("mean wind speed < 0.5 m/s, limited convective cooling")
        elif wind_mean < 2:
            score += 0.25
            evidence.append("mean wind speed < 2 m/s, weak convective cooling")
        elif wind_mean >= 5:
            evidence.append("mean wind speed >= 5 m/s, ventilation may reduce perceived heat")

    if not pd.isna(daytime_ratio) and daytime_ratio > 0:
        score += 0.5
        evidence.append("activity weather window overlaps 09-15 local daytime heat window")

    temp_support = (
        (not pd.isna(temp_mean) and temp_mean >= 26)
        or (not pd.isna(temp_max) and temp_max >= 28)
        or (not pd.isna(heat_index) and heat_index >= 32)
    )

    score = round(float(score), 4)

    if score >= 6 and temp_support:
        status = "HEAT_HUMID_STRESS_CONTEXT_ELEVATED_REVIEW_ONLY"
    elif score >= 4 and temp_support:
        status = "HEAT_HUMID_STRESS_CONTEXT_MODERATE_REVIEW_ONLY"
    elif score >= 2:
        status = "HEAT_HUMID_STRESS_CONTEXT_HUMID_MILD_BACKGROUND_REVIEW_ONLY"
    else:
        status = "HEAT_HUMID_STRESS_CONTEXT_NOT_SUPPORTED_BY_AVAILABLE_WEATHER"

    if score >= 4 and temp_support:
        confidence = "MEDIUM_PROXY_ONLY"
    elif score >= 2:
        confidence = "LOW_TO_MEDIUM_PROXY_ONLY"
    else:
        confidence = "LOW_PROXY_ONLY"

    reason = "Heat/humid stress context is inferred from temperature, humidity, wind, activity timing, and available weather observations only."
    return status, confidence, score, reason, " | ".join(evidence)


def build_context() -> pd.DataFrame:
    for p in [ANTECEDENT_CSV, VECTOR_CSV, WEATHER_DB]:
        if not p.exists():
            raise FileNotFoundError(p)

    antecedent = pd.read_csv(ANTECEDENT_CSV, dtype=str)
    vector = pd.read_csv(VECTOR_CSV, dtype=str)

    df = antecedent.merge(
        vector[["output_case", "activity_id", "zero_fallback_true_count"]],
        on=["output_case", "activity_id"],
        how="left",
        suffixes=("", "_vector"),
    )

    if FOG_PROXY_CSV.exists():
        fog = pd.read_csv(FOG_PROXY_CSV, dtype=str)
        df = df.merge(
            fog[[
                "output_case",
                "activity_id",
                "fog_low_cloud_condition_proxy_status",
                "fog_low_cloud_condition_proxy_confidence",
                "fog_low_cloud_condition_proxy_index_v1",
            ]],
            on=["output_case", "activity_id"],
            how="left",
        )
    else:
        df["fog_low_cloud_condition_proxy_status"] = ""
        df["fog_low_cloud_condition_proxy_confidence"] = ""
        df["fog_low_cloud_condition_proxy_index_v1"] = ""

    if WET_COLD_CSV.exists():
        wc = pd.read_csv(WET_COLD_CSV, dtype=str)
        df = df.merge(
            wc[[
                "output_case",
                "activity_id",
                "wet_cold_exposure_context_status",
                "wet_cold_exposure_index_v1",
            ]],
            on=["output_case", "activity_id"],
            how="left",
        )
    else:
        df["wet_cold_exposure_context_status"] = ""
        df["wet_cold_exposure_index_v1"] = ""

    rows = []

    with sqlite3.connect(WEATHER_DB) as conn:
        for _, src in df.iterrows():
            allowed = as_bool(src.get("weather_sensitive_score_allowed"))

            out = {
                "schema_version": SCHEMA_VERSION,
                "output_case": src.get("output_case", ""),
                "case_id": src.get("case_id", ""),
                "activity_id": src.get("activity_id", ""),
                "activity_start_time_utc": src.get("activity_start_time_utc", ""),
                "activity_end_time_utc": src.get("activity_end_time_utc", ""),
                "weather_sensitive_score_allowed": allowed,
                "primary_candidate_station_ids": src.get("primary_candidate_station_ids", ""),
                "primary_candidate_station_names": src.get("primary_candidate_station_names", ""),
                "fog_low_cloud_condition_proxy_status": src.get("fog_low_cloud_condition_proxy_status", ""),
                "fog_low_cloud_condition_proxy_confidence": src.get("fog_low_cloud_condition_proxy_confidence", ""),
                "fog_low_cloud_condition_proxy_index_v1": src.get("fog_low_cloud_condition_proxy_index_v1", ""),
                "wet_cold_exposure_context_status": src.get("wet_cold_exposure_context_status", ""),
                "wet_cold_exposure_index_v1": src.get("wet_cold_exposure_index_v1", ""),
                "sunshine_direct_observation_status": "SUNSHINE_DURATION_UNAVAILABLE_IN_CURRENT_DB",
                "uv_direct_observation_status": "UV_INDEX_UNAVAILABLE_IN_CURRENT_DB",
                "wbgt_status": "NOT_COMPUTED_NO_WBGT_SOLAR_RADIATION_OR_GLOBE_TEMPERATURE",
                "heat_illness_medical_claim_status": "NOT_CLAIMED_NOT_MEDICAL_DIAGNOSIS",
                "thci_or_final_risk_status": "NOT_COMPUTED_CONTEXT_ONLY",
                "scope_note": "Heat/humid stress context only. No WBGT, no UV, no direct sunshine, no heat illness diagnosis, no medical judgment, no THCI, no final hiking risk score, no missing-to-zero imputation.",
            }

            if not allowed:
                out.update(summarize_weather(pd.DataFrame()))
                out["heat_index_status"] = "NOT_EVALUATED"
                out["heat_index_c"] = pd.NA
                out["heat_humid_stress_context_status"] = "BLOCKED_BY_GATE"
                out["heat_humid_stress_context_confidence"] = "NOT_EVALUATED"
                out["heat_humid_stress_index_v1"] = pd.NA
                out["heat_humid_stress_context_reason"] = "Weather-sensitive feature gate did not allow heat/humid stress evaluation."
                out["heat_humid_stress_context_evidence"] = ""
                out["zero_fallback_true_count"] = src.get("zero_fallback_true_count", src.get("zero_fallback_true_count_vector", 0))
                rows.append(out)
                continue

            start = pd.to_datetime(src.get("activity_start_time_utc"), errors="coerce", utc=True)
            end = pd.to_datetime(src.get("activity_end_time_utc"), errors="coerce", utc=True)
            station_ids = split_stations(src.get("primary_candidate_station_ids"))

            weather = fetch_weather(conn, station_ids, start, end)
            out.update(summarize_weather(weather))

            hi_status, hi_c = heat_index_proxy_c(
                num(out.get("temperature_mean_c")),
                num(out.get("relative_humidity_mean_pct")),
            )
            out["heat_index_status"] = hi_status
            out["heat_index_c"] = hi_c

            status, confidence, score, reason, evidence = score_heat(out)
            out["heat_humid_stress_context_status"] = status
            out["heat_humid_stress_context_confidence"] = confidence
            out["heat_humid_stress_index_v1"] = score
            out["heat_humid_stress_context_reason"] = reason
            out["heat_humid_stress_context_evidence"] = evidence
            out["zero_fallback_true_count"] = src.get("zero_fallback_true_count", src.get("zero_fallback_true_count_vector", 0))
            rows.append(out)

    return pd.DataFrame(rows)


def build_summary(context: pd.DataFrame) -> pd.DataFrame:
    rows = []
    cols = [
        "heat_humid_stress_context_status",
        "heat_humid_stress_context_confidence",
        "heat_index_status",
        "sunshine_direct_observation_status",
        "uv_direct_observation_status",
        "wbgt_status",
        "heat_illness_medical_claim_status",
        "thci_or_final_risk_status",
    ]

    for col in cols:
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
        "heat_humid_stress_context_status",
        "heat_humid_stress_context_confidence",
        "heat_humid_stress_index_v1",
        "heat_humid_stress_context_reason",
        "heat_humid_stress_context_evidence",
        "temperature_mean_c",
        "temperature_max_c",
        "relative_humidity_mean_pct",
        "relative_humidity_max_pct",
        "wind_speed_mean_ms",
        "wind_speed_max_ms",
        "wind_class",
        "daytime_heat_window_row_count",
        "daytime_heat_window_ratio",
        "precipitation_positive_row_count",
        "precipitation_max_observed_mm",
        "heat_index_status",
        "heat_index_c",
        "sunshine_direct_observation_status",
        "uv_direct_observation_status",
        "wbgt_status",
        "heat_illness_medical_claim_status",
        "thci_or_final_risk_status",
        "fog_low_cloud_condition_proxy_status",
        "wet_cold_exposure_context_status",
    ]

    allowed = context[context["weather_sensitive_score_allowed"].astype(str).str.lower().eq("true")].copy()
    zero = int(pd.to_numeric(context["zero_fallback_true_count"], errors="coerce").fillna(0).sum())

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>IB3W Heat / Humid Stress Context v1</title>
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
<h1>IB3W Heat / Humid Stress Context v1</h1>
<section>
<p>Heat/humid stress context based on temperature, relative humidity, wind, activity timing, and available weather observations.</p>
<p>No WBGT, no UV, no direct sunshine, no heat illness diagnosis, no medical judgment, no THCI, no final hiking risk score, no missing-to-zero imputation.</p>
<p>Total activities: {len(context)}; evaluated activities: {len(allowed)}; zero fallback violations: {zero}</p>
</section>
<section><h2>Evaluated rows</h2><div class="wrap">{html_table(allowed[key_cols])}</div></section>
<section><h2>Full heat/humid stress review</h2><div class="wrap">{html_table(context[key_cols])}</div></section>
<section><h2>Summary</h2><div class="wrap">{html_table(summary)}</div></section>
</body>
</html>
"""


def main() -> None:
    context = build_context()
    summary = build_summary(context)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    context_csv = OUT_DIR / "activity_heat_humid_stress_context.csv"
    summary_csv = OUT_DIR / "activity_heat_humid_stress_context_summary.csv"
    html_report = OUT_DIR / "activity_heat_humid_stress_context_report.html"

    context.to_csv(context_csv, index=False, encoding="utf-8-sig")
    summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")
    html_report.write_text(build_html(context, summary), encoding="utf-8")

    print("IB3W heat/humid stress context v1 written")
    print("context_csv:", context_csv)
    print("summary_csv:", summary_csv)
    print("html_report:", html_report)
    print()
    print("heat_humid_stress_context_status_distribution:")
    print(
        context.groupby("heat_humid_stress_context_status")
        .size()
        .reset_index(name="activity_count")
        .sort_values("activity_count", ascending=False)
        .to_string(index=False)
    )
    print()
    print("zero_fallback_true_total:", int(pd.to_numeric(context["zero_fallback_true_count"], errors="coerce").fillna(0).sum()))


if __name__ == "__main__":
    main()
