from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


SCHEMA_VERSION = "ib3w_wet_cold_exposure_context_v1"

ANTECEDENT_CSV = Path(
    "outputs/ib3w_antecedent_precipitation_context_v1/"
    "activity_antecedent_precipitation_context.csv"
)
VECTOR_CSV = Path(
    "outputs/ib3w_weather_sensitive_feature_vector_v1/"
    "activity_weather_sensitive_feature_vector.csv"
)
SURFACE_WETNESS_CSV = Path(
    "outputs/ib3w_surface_wetness_proxy_v1/"
    "activity_surface_wetness_proxy.csv"
)
FOG_PROXY_CSV = Path(
    "outputs/ib3w_fog_low_cloud_condition_proxy_v1/"
    "activity_fog_low_cloud_condition_proxy.csv"
)
WEATHER_DB = Path("weather/tw_weather_2026-05-01.sqlite3")
OUT_DIR = Path("outputs/ib3w_wet_cold_exposure_context_v1")


def as_bool(value) -> bool:
    return str(value).strip().lower() == "true"


def as_num(value):
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return pd.NA if pd.isna(parsed) else float(parsed)


def split_stations(value) -> list[str]:
    if pd.isna(value):
        return []
    return [x.strip() for x in str(value).split("|") if x.strip()]


def safe_str(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


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


def fetch_activity_rows(conn, station_ids, start_utc, end_utc) -> pd.DataFrame:
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
        return df

    df["station_id"] = df["station_id"].astype(str).str.strip()
    df["station_name"] = df["station_name"].astype(str).str.strip()
    df["obs_time_utc"] = pd.to_datetime(df["obs_time"], errors="coerce", utc=True)

    for col in [
        "temperature_c",
        "relative_humidity_pct",
        "wind_speed_ms",
        "wind_direction_deg",
        "precipitation_mm",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["obs_time_utc"])
    df = df.drop_duplicates(subset=["station_id", "obs_time_utc"])
    return df


def summarize_weather(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "activity_weather_row_count": 0,
            "activity_observed_station_count": 0,
            "activity_observed_station_ids": "",
            "temperature_nonnull_count": 0,
            "temperature_mean_c": pd.NA,
            "temperature_min_c": pd.NA,
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
        }

    temp = pd.to_numeric(df["temperature_c"], errors="coerce").dropna()
    rh = pd.to_numeric(df["relative_humidity_pct"], errors="coerce").dropna()
    wind = pd.to_numeric(df["wind_speed_ms"], errors="coerce").dropna()
    rain = pd.to_numeric(df["precipitation_mm"], errors="coerce").dropna()

    wind_mean = round(float(wind.mean()), 4) if len(wind) else pd.NA

    return {
        "activity_weather_row_count": int(len(df)),
        "activity_observed_station_count": int(df["station_id"].nunique()),
        "activity_observed_station_ids": "|".join(sorted(df["station_id"].dropna().astype(str).unique().tolist())),
        "temperature_nonnull_count": int(len(temp)),
        "temperature_mean_c": round(float(temp.mean()), 4) if len(temp) else pd.NA,
        "temperature_min_c": round(float(temp.min()), 4) if len(temp) else pd.NA,
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
    }


def wind_chill_note(temp_c, wind_ms) -> tuple[str, object]:
    """
    Standard wind chill formulas are generally not appropriate for warm conditions.
    This layer keeps wind as exposure modifier and only reports wind-chill status.
    """
    if pd.isna(temp_c) or pd.isna(wind_ms):
        return "WIND_CHILL_NOT_COMPUTED_INPUT_MISSING", pd.NA

    temp_c = float(temp_c)
    wind_ms = float(wind_ms)

    if temp_c > 10:
        return "WIND_CHILL_NOT_COMPUTED_TEMPERATURE_ABOVE_10C", pd.NA

    if wind_ms < 1.34:
        return "WIND_CHILL_NOT_COMPUTED_WIND_BELOW_STANDARD_THRESHOLD", pd.NA

    wind_kmh = wind_ms * 3.6
    wc = 13.12 + 0.6215 * temp_c - 11.37 * (wind_kmh ** 0.16) + 0.3965 * temp_c * (wind_kmh ** 0.16)
    return "WIND_CHILL_COMPUTED_STANDARD_FORMULA", round(float(wc), 4)


def score_wet_cold(row: dict) -> tuple[float, str, str, str]:
    score = 0.0
    evidence = []

    temp_mean = as_num(row.get("temperature_mean_c"))
    temp_min = as_num(row.get("temperature_min_c"))
    rh_mean = as_num(row.get("relative_humidity_mean_pct"))
    rh_max = as_num(row.get("relative_humidity_max_pct"))
    wind_mean = as_num(row.get("wind_speed_mean_ms"))
    wind_max = as_num(row.get("wind_speed_max_ms"))
    rain_positive = int(row.get("precipitation_positive_row_count", 0) or 0)

    surface = safe_str(row.get("surface_wetness_proxy_status"))
    fog = safe_str(row.get("fog_low_cloud_condition_proxy_status"))

    if not pd.isna(temp_min):
        if temp_min <= 5:
            score += 3.0
            evidence.append("temperature min <= 5C")
        elif temp_min <= 10:
            score += 2.0
            evidence.append("temperature min <= 10C")
        elif temp_min <= 15:
            score += 1.0
            evidence.append("temperature min <= 15C")
        elif temp_min <= 20:
            score += 0.5
            evidence.append("temperature min <= 20C, cool but not cold")

    if not pd.isna(temp_mean):
        if temp_mean <= 10:
            score += 1.5
            evidence.append("temperature mean <= 10C")
        elif temp_mean <= 15:
            score += 1.0
            evidence.append("temperature mean <= 15C")
        elif temp_mean <= 20:
            score += 0.5
            evidence.append("temperature mean <= 20C, cool but not cold")

    if not pd.isna(rh_mean):
        if rh_mean >= 95:
            score += 1.0
            evidence.append("relative humidity mean >= 95%")
        elif rh_mean >= 90:
            score += 0.75
            evidence.append("relative humidity mean >= 90%")
        elif rh_mean >= 85:
            score += 0.5
            evidence.append("relative humidity mean >= 85%")

    if not pd.isna(rh_max):
        if rh_max >= 98:
            score += 0.5
            evidence.append("relative humidity max >= 98%")
        elif rh_max >= 95:
            score += 0.25
            evidence.append("relative humidity max >= 95%")

    if not pd.isna(wind_mean):
        if wind_mean >= 5:
            score += 1.5
            evidence.append("mean wind speed >= 5 m/s")
        elif wind_mean >= 2:
            score += 0.75
            evidence.append("mean wind speed >= 2 m/s")
        elif wind_mean >= 0.5:
            score += 0.25
            evidence.append("mean wind speed >= 0.5 m/s")

    if not pd.isna(wind_max) and wind_max >= 5:
        score += 0.5
        evidence.append("max wind speed >= 5 m/s")

    if rain_positive > 0:
        score += 1.5
        evidence.append("positive precipitation rows during activity window")

    if surface in [
        "SURFACE_WETNESS_PROXY_PERSISTENT_WETNESS_POSSIBLE",
        "SURFACE_WETNESS_PROXY_RECENT_RAIN_WETNESS_POSSIBLE",
    ]:
        score += 1.0
        evidence.append(f"surface wetness context supports wet exposure: {surface}")
    elif surface in [
        "SURFACE_WETNESS_PROXY_WETNESS_POSSIBLE_LOW_TO_MODERATE",
        "SURFACE_WETNESS_PROXY_ANTECEDENT_WETNESS_PRESENT",
    ]:
        score += 0.5
        evidence.append(f"surface wetness context weakly supports wet exposure: {surface}")

    if fog in [
        "FOG_LOW_CLOUD_CONDITION_PROXY_HIGH_REVIEW_ONLY",
        "FOG_LOW_CLOUD_CONDITION_PROXY_MODERATE_REVIEW_ONLY",
    ]:
        score += 0.5
        evidence.append(f"fog/low-cloud proxy supports damp exposure background: {fog}")

    score = round(float(score), 4)

    if score >= 6 and ((not pd.isna(temp_min) and temp_min <= 15) or rain_positive > 0):
        status = "WET_COLD_EXPOSURE_CONTEXT_ELEVATED_REVIEW_ONLY"
    elif score >= 4:
        status = "WET_COLD_EXPOSURE_CONTEXT_MODERATE_REVIEW_ONLY"
    elif score >= 2:
        status = "WET_COLD_EXPOSURE_CONTEXT_MOIST_COOL_BACKGROUND_REVIEW_ONLY"
    else:
        status = "WET_COLD_EXPOSURE_CONTEXT_NOT_SUPPORTED_BY_AVAILABLE_WEATHER"

    if score >= 4:
        confidence = "MEDIUM_PROXY_ONLY"
    elif score >= 2:
        confidence = "LOW_TO_MEDIUM_PROXY_ONLY"
    else:
        confidence = "LOW_PROXY_ONLY"

    reason = (
        "Wet-cold exposure context is inferred from temperature, humidity, wind, "
        "precipitation, surface wetness, and fog/low-cloud proxy evidence only."
    )

    return status, confidence, score, reason, " | ".join(evidence)


def build_context() -> pd.DataFrame:
    antecedent = pd.read_csv(ANTECEDENT_CSV, dtype=str)
    vector = pd.read_csv(VECTOR_CSV, dtype=str)

    vector_cols = ["output_case", "activity_id", "zero_fallback_true_count"]
    merged = antecedent.merge(
        vector[vector_cols],
        on=["output_case", "activity_id"],
        how="left",
        suffixes=("", "_vector"),
    )

    if SURFACE_WETNESS_CSV.exists():
        surface = pd.read_csv(SURFACE_WETNESS_CSV, dtype=str)
        surface_cols = [
            "output_case",
            "activity_id",
            "surface_wetness_proxy_status",
            "surface_wetness_proxy_confidence",
            "surface_wetness_proxy_net_index",
        ]
        merged = merged.merge(surface[surface_cols], on=["output_case", "activity_id"], how="left")
    else:
        merged["surface_wetness_proxy_status"] = ""
        merged["surface_wetness_proxy_confidence"] = ""
        merged["surface_wetness_proxy_net_index"] = ""

    if FOG_PROXY_CSV.exists():
        fog = pd.read_csv(FOG_PROXY_CSV, dtype=str)
        fog_cols = [
            "output_case",
            "activity_id",
            "fog_low_cloud_condition_proxy_status",
            "fog_low_cloud_condition_proxy_confidence",
            "fog_low_cloud_condition_proxy_index_v1",
        ]
        merged = merged.merge(fog[fog_cols], on=["output_case", "activity_id"], how="left")
    else:
        merged["fog_low_cloud_condition_proxy_status"] = ""
        merged["fog_low_cloud_condition_proxy_confidence"] = ""
        merged["fog_low_cloud_condition_proxy_index_v1"] = ""

    rows = []

    with sqlite3.connect(WEATHER_DB) as conn:
        for _, src in merged.iterrows():
            allowed = as_bool(src.get("weather_sensitive_score_allowed"))
            station_ids = split_stations(src.get("primary_candidate_station_ids"))

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
                "surface_wetness_proxy_status": src.get("surface_wetness_proxy_status", ""),
                "surface_wetness_proxy_confidence": src.get("surface_wetness_proxy_confidence", ""),
                "surface_wetness_proxy_net_index": src.get("surface_wetness_proxy_net_index", ""),
                "fog_low_cloud_condition_proxy_status": src.get("fog_low_cloud_condition_proxy_status", ""),
                "fog_low_cloud_condition_proxy_confidence": src.get("fog_low_cloud_condition_proxy_confidence", ""),
                "fog_low_cloud_condition_proxy_index_v1": src.get("fog_low_cloud_condition_proxy_index_v1", ""),
                "hypothermia_medical_claim_status": "NOT_CLAIMED_NOT_MEDICAL_DIAGNOSIS",
                "clothing_fatigue_exposure_duration_status": "NOT_AVAILABLE_IN_V1",
                "thci_or_final_risk_status": "NOT_COMPUTED_CONTEXT_ONLY",
                "source_antecedent_csv": str(ANTECEDENT_CSV),
                "source_vector_csv": str(VECTOR_CSV),
                "source_surface_wetness_csv": str(SURFACE_WETNESS_CSV),
                "source_fog_proxy_csv": str(FOG_PROXY_CSV),
                "source_weather_db": str(WEATHER_DB),
                "scope_note": "Wet-cold exposure context only. No hypothermia diagnosis, no medical judgment, no THCI, no final hiking risk score, no missing-to-zero imputation.",
            }

            if not allowed:
                out.update(summarize_weather(pd.DataFrame()))
                out["wind_chill_status"] = "NOT_EVALUATED"
                out["wind_chill_c"] = pd.NA
                out["wet_cold_exposure_context_status"] = "BLOCKED_BY_GATE"
                out["wet_cold_exposure_context_confidence"] = "NOT_EVALUATED"
                out["wet_cold_exposure_index_v1"] = pd.NA
                out["wet_cold_exposure_context_reason"] = "Weather-sensitive feature gate did not allow wet-cold exposure evaluation."
                out["wet_cold_exposure_context_evidence"] = ""
                out["zero_fallback_true_count"] = src.get("zero_fallback_true_count", src.get("zero_fallback_true_count_vector", 0))
                rows.append(out)
                continue

            start = pd.to_datetime(src.get("activity_start_time_utc"), errors="coerce", utc=True)
            end = pd.to_datetime(src.get("activity_end_time_utc"), errors="coerce", utc=True)

            if pd.isna(start) or pd.isna(end):
                raise ValueError(f"bad activity time: {src.get('activity_id')}")

            weather_rows = fetch_activity_rows(conn, station_ids, start, end)
            out.update(summarize_weather(weather_rows))

            wc_status, wc_value = wind_chill_note(
                as_num(out.get("temperature_mean_c")),
                as_num(out.get("wind_speed_mean_ms")),
            )
            out["wind_chill_status"] = wc_status
            out["wind_chill_c"] = wc_value

            status, confidence, score, reason, evidence = score_wet_cold(out)
            out["wet_cold_exposure_context_status"] = status
            out["wet_cold_exposure_context_confidence"] = confidence
            out["wet_cold_exposure_index_v1"] = score
            out["wet_cold_exposure_context_reason"] = reason
            out["wet_cold_exposure_context_evidence"] = evidence
            out["zero_fallback_true_count"] = src.get("zero_fallback_true_count", src.get("zero_fallback_true_count_vector", 0))

            rows.append(out)

    return pd.DataFrame(rows)


def build_summary(context: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col in [
        "wet_cold_exposure_context_status",
        "wet_cold_exposure_context_confidence",
        "wind_chill_status",
        "hypothermia_medical_claim_status",
        "thci_or_final_risk_status",
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
        "wet_cold_exposure_context_status",
        "wet_cold_exposure_context_confidence",
        "wet_cold_exposure_index_v1",
        "wet_cold_exposure_context_reason",
        "wet_cold_exposure_context_evidence",
        "temperature_mean_c",
        "temperature_min_c",
        "relative_humidity_mean_pct",
        "relative_humidity_max_pct",
        "wind_speed_mean_ms",
        "wind_speed_max_ms",
        "wind_class",
        "precipitation_positive_row_count",
        "precipitation_max_observed_mm",
        "surface_wetness_proxy_status",
        "fog_low_cloud_condition_proxy_status",
        "wind_chill_status",
        "wind_chill_c",
        "hypothermia_medical_claim_status",
        "clothing_fatigue_exposure_duration_status",
        "thci_or_final_risk_status",
    ]

    allowed = context[context["weather_sensitive_score_allowed"].astype(str).str.lower().eq("true")].copy()
    zero_fallback = int(pd.to_numeric(context["zero_fallback_true_count"], errors="coerce").fillna(0).sum())

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>IB3W Wet-cold Exposure Context v1</title>
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
<h1>IB3W Wet-cold Exposure Context v1</h1>
<section>
<p>Wet-cold exposure context based on temperature, relative humidity, wind, precipitation, surface wetness proxy, and fog/low-cloud proxy.</p>
<p>No hypothermia diagnosis, no medical judgment, no THCI, no final hiking risk score, no missing-to-zero imputation.</p>
<p>Total activities: {len(context)}; evaluated activities: {len(allowed)}; zero fallback violations: {zero_fallback}</p>
</section>
<section><h2>Evaluated rows</h2><div class="wrap">{html_table(allowed[key_cols])}</div></section>
<section><h2>Full wet-cold exposure review</h2><div class="wrap">{html_table(context[key_cols])}</div></section>
<section><h2>Summary</h2><div class="wrap">{html_table(summary)}</div></section>
</body>
</html>
"""


def main() -> None:
    for path in [ANTECEDENT_CSV, VECTOR_CSV, WEATHER_DB]:
        if not path.exists():
            raise FileNotFoundError(path)

    context = build_context()
    summary = build_summary(context)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    context_csv = OUT_DIR / "activity_wet_cold_exposure_context.csv"
    summary_csv = OUT_DIR / "activity_wet_cold_exposure_context_summary.csv"
    html_report = OUT_DIR / "activity_wet_cold_exposure_context_report.html"

    context.to_csv(context_csv, index=False, encoding="utf-8-sig")
    summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")
    html_report.write_text(build_html(context, summary), encoding="utf-8")

    print("IB3W wet-cold exposure context v1 written")
    print("context_csv:", context_csv)
    print("summary_csv:", summary_csv)
    print("html_report:", html_report)
    print()
    print("wet_cold_exposure_context_status_distribution:")
    print(
        context.groupby("wet_cold_exposure_context_status")
        .size()
        .reset_index(name="activity_count")
        .sort_values("activity_count", ascending=False)
        .to_string(index=False)
    )
    print()
    print("zero_fallback_true_total:", int(pd.to_numeric(context["zero_fallback_true_count"], errors="coerce").fillna(0).sum()))


if __name__ == "__main__":
    main()
