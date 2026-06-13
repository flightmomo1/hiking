from __future__ import annotations

from pathlib import Path
import pandas as pd


SCHEMA_VERSION = "ib3w_surface_wetness_proxy_v1"

ANTECEDENT_CSV = Path(
    "outputs/ib3w_antecedent_precipitation_context_v1/"
    "activity_antecedent_precipitation_context.csv"
)

VECTOR_CSV = Path(
    "outputs/ib3w_weather_sensitive_feature_vector_v1/"
    "activity_weather_sensitive_feature_vector.csv"
)

OUT_DIR = Path("outputs/ib3w_surface_wetness_proxy_v1")


def as_bool(value: object) -> bool:
    return str(value).strip().lower() == "true"


def as_num(value: object):
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return pd.NA
    return float(parsed)


def first_value(row: pd.Series, candidates: list[str], default: str = ""):
    for col in candidates:
        if col in row.index:
            value = row.get(col)
            if not pd.isna(value) and str(value).strip() != "":
                return value
    return default


def first_num(row: pd.Series, candidates: list[str]):
    return as_num(first_value(row, candidates, pd.NA))


def get_bool(row: pd.Series, col: str) -> bool:
    return as_bool(row.get(col, False))


def wetness_pressure(row: pd.Series) -> tuple[float, list[str]]:
    score = 0.0
    evidence = []

    max_6h = as_num(row.get("rain_lookback_6h_max_observed_precipitation_mm"))
    max_24h = as_num(row.get("rain_lookback_24h_max_observed_precipitation_mm"))
    max_72h = as_num(row.get("rain_lookback_72h_max_observed_precipitation_mm"))
    max_7d = as_num(row.get("max_observed_precipitation_lookback_7d_mm"))

    if get_bool(row, "rain_lookback_6h_positive_observed_flag"):
        if not pd.isna(max_6h) and max_6h <= 1.0:
            score += 1.0
            evidence.append("light rain observed within 6h, max <= 1.0 mm")
        else:
            score += 3.0
            evidence.append("rain observed within 6h")
    elif get_bool(row, "rain_lookback_24h_positive_observed_flag"):
        if not pd.isna(max_24h) and max_24h <= 1.0:
            score += 0.75
            evidence.append("light rain observed within 24h, max <= 1.0 mm")
        else:
            score += 2.0
            evidence.append("rain observed within 24h")
    elif get_bool(row, "rain_lookback_72h_positive_observed_flag"):
        if not pd.isna(max_72h) and max_72h <= 5.0:
            score += 0.75
            evidence.append("minor antecedent rain observed within 72h")
        else:
            score += 1.0
            evidence.append("rain observed within 72h")
    elif get_bool(row, "rain_lookback_7d_positive_observed_flag"):
        score += 0.5
        evidence.append("rain observed within 7d")

    hours_since = as_num(row.get("hours_since_last_observed_rain"))
    last_rain_max = as_num(row.get("last_observed_rain_precipitation_mm_max"))

    if not pd.isna(hours_since):
        if hours_since <= 6:
            if not pd.isna(last_rain_max) and last_rain_max <= 1.0:
                score += 0.5
                evidence.append("last observed rain within 6h but light, max <= 1.0 mm")
            else:
                score += 2.0
                evidence.append("last observed rain within 6h before start")
        elif hours_since <= 24:
            score += 1.0
            evidence.append("last observed rain within 24h before start")
        elif hours_since <= 72:
            score += 0.5
            evidence.append("last observed rain within 72h before start")

    if not pd.isna(max_7d):
        if max_7d >= 20:
            score += 0.5
            evidence.append("large raw observed precipitation value within 7d, used as background only")
        elif max_7d >= 5:
            score += 0.25
            evidence.append("moderate raw observed precipitation value within 7d, used as background only")

    positive_dates = as_num(row.get("positive_rain_local_dates_count_lookback_7d"))
    if not pd.isna(positive_dates):
        if positive_dates >= 3:
            score += 0.5
            evidence.append("multiple local dates with positive rain observations")
        elif positive_dates >= 1:
            score += 0.25
            evidence.append("at least one local date with positive rain observations")

    return score, evidence


def drying_potential(row: pd.Series) -> tuple[float, list[str], list[str]]:
    drying = 0.0
    wetness_evidence = []
    drying_evidence = []

    temp = first_num(row, [
        "temperature_c_mean_primary",
        "temperature_c_primary_value_mean_of_station_means",
    ])

    rh = first_num(row, [
        "relative_humidity_pct_mean_primary",
        "relative_humidity_pct_primary_value_mean_of_station_means",
    ])

    wind = first_num(row, [
        "wind_speed_ms_mean_primary",
        "wind_speed_ms_primary_value_mean_of_station_means",
    ])

    wind_max = first_num(row, [
        "wind_speed_ms_max_primary",
        "wind_speed_ms_primary_value_max",
    ])

    if not pd.isna(rh):
        if rh >= 90:
            wetness_evidence.append("relative humidity >= 90%, drying likely limited")
        elif rh >= 80:
            wetness_evidence.append("relative humidity >= 80%, drying may be limited")
        elif rh < 70:
            drying += 0.5
            drying_evidence.append("relative humidity < 70%, drying more favorable")

    if not pd.isna(temp):
        if temp >= 25:
            drying += 1.0
            drying_evidence.append("temperature >= 25C")
        elif temp >= 18:
            drying += 0.5
            drying_evidence.append("temperature >= 18C")
        else:
            wetness_evidence.append("temperature < 18C, evaporation likely weaker")

    if not pd.isna(wind):
        if wind >= 5:
            drying += 1.0
            drying_evidence.append("mean wind speed >= 5 m/s")
        elif wind >= 2:
            drying += 0.5
            drying_evidence.append("mean wind speed >= 2 m/s")
        else:
            wetness_evidence.append("mean wind speed < 2 m/s, drying likely weaker")

    if not pd.isna(wind_max) and wind_max >= 5:
        drying += 0.5
        drying_evidence.append("max wind speed >= 5 m/s")

    return drying, wetness_evidence, drying_evidence


def classify_proxy(
    score: float,
    drying: float,
    antecedent_status: str,
    score_allowed: bool,
) -> tuple[str, str, str]:
    if not score_allowed:
        return (
            "BLOCKED_BY_GATE",
            "NOT_EVALUATED",
            "Weather-sensitive feature gate did not allow evaluation.",
        )

    if antecedent_status == "ANTECEDENT_PRECIPITATION_MISSING":
        return (
            "SURFACE_WETNESS_PROXY_UNAVAILABLE_NO_ANTECEDENT_PRECIPITATION",
            "LOW",
            "Antecedent precipitation context is missing.",
        )

    if antecedent_status == "ANTECEDENT_PRECIPITATION_OBSERVED_NO_RAIN":
        if drying >= 1.0:
            return (
                "SURFACE_WETNESS_PROXY_DRYING_LIKELY",
                "PARTIAL",
                "No antecedent rain observed and drying context is favorable.",
            )
        return (
            "SURFACE_WETNESS_PROXY_NO_RAIN_OBSERVED",
            "PARTIAL",
            "No antecedent rain observed, but drying context is incomplete.",
        )

    net = score - drying

    if antecedent_status == "ANTECEDENT_PRECIPITATION_OBSERVED_RAIN":
        if net >= 6:
            return (
                "SURFACE_WETNESS_PROXY_PERSISTENT_WETNESS_POSSIBLE",
                "PARTIAL",
                "Repeated or stronger antecedent rain plus limited drying context.",
            )
        if net >= 3:
            return (
                "SURFACE_WETNESS_PROXY_RECENT_RAIN_WETNESS_POSSIBLE",
                "PARTIAL",
                "Antecedent rain exists; drying may not fully offset it.",
            )
        if net >= 1:
            return (
                "SURFACE_WETNESS_PROXY_WETNESS_POSSIBLE_LOW_TO_MODERATE",
                "PARTIAL",
                "Recent rain was light, but humid antecedent background keeps some surface wetness possibility.",
            )
        return (
            "SURFACE_WETNESS_PROXY_ANTECEDENT_WETNESS_PRESENT",
            "PARTIAL",
            "Antecedent rain exists, but available drying context partly offsets it.",
        )

    return (
        "SURFACE_WETNESS_PROXY_REVIEW_REQUIRED",
        "LOW",
        "Proxy inputs did not match expected patterns.",
    )


def build_proxy(antecedent: pd.DataFrame, vector: pd.DataFrame) -> pd.DataFrame:
    df = antecedent.merge(
        vector,
        on=["output_case", "activity_id"],
        how="left",
        suffixes=("", "_vector"),
    )

    rows = []

    for _, row in df.iterrows():
        score_allowed = as_bool(row.get("weather_sensitive_score_allowed"))
        antecedent_status = str(row.get("antecedent_precipitation_context_status", "")).strip()

        wet_score, rain_evidence = wetness_pressure(row)
        dry_score, weather_wet_evidence, drying_evidence = drying_potential(row)

        rh = first_num(row, [
            "relative_humidity_pct_mean_primary",
            "relative_humidity_pct_primary_value_mean_of_station_means",
        ])

        if not pd.isna(rh):
            if rh >= 90:
                wet_score += 1.0
            elif rh >= 80:
                wet_score += 0.5

        proxy_status, proxy_confidence, proxy_reason = classify_proxy(
            score=wet_score,
            drying=dry_score,
            antecedent_status=antecedent_status,
            score_allowed=score_allowed,
        )

        temp = first_value(row, [
            "temperature_c_mean_primary",
            "temperature_c_primary_value_mean_of_station_means",
        ])

        humidity = first_value(row, [
            "relative_humidity_pct_mean_primary",
            "relative_humidity_pct_primary_value_mean_of_station_means",
        ])

        wind = first_value(row, [
            "wind_speed_ms_mean_primary",
            "wind_speed_ms_primary_value_mean_of_station_means",
        ])

        wind_max = first_value(row, [
            "wind_speed_ms_max_primary",
            "wind_speed_ms_primary_value_max",
        ])

        input_quality = "WEATHER_CONTEXT_PARTIAL"
        if str(temp).strip() and str(humidity).strip() and str(wind).strip():
            input_quality = "WEATHER_CONTEXT_TEMP_RH_WIND_AVAILABLE"

        evidence = rain_evidence + weather_wet_evidence + drying_evidence

        zero_fallback = row.get("zero_fallback_true_count")
        if pd.isna(zero_fallback) or str(zero_fallback).strip() == "":
            zero_fallback = row.get("zero_fallback_true_count_vector", 0)

        out = {
            "schema_version": SCHEMA_VERSION,
            "output_case": row.get("output_case", ""),
            "case_id": row.get("case_id", ""),
            "activity_id": row.get("activity_id", ""),
            "activity_start_time_utc": row.get("activity_start_time_utc", ""),
            "activity_end_time_utc": row.get("activity_end_time_utc", ""),
            "weather_sensitive_score_allowed": score_allowed,
            "antecedent_precipitation_context_status": antecedent_status,
            "antecedent_precipitation_data_quality": row.get("antecedent_precipitation_data_quality", ""),
            "precipitation_amount_semantics": row.get("precipitation_amount_semantics", ""),
            "surface_wetness_proxy_status": proxy_status,
            "surface_wetness_proxy_confidence": proxy_confidence,
            "surface_wetness_proxy_reason": proxy_reason,
            "surface_wetness_proxy_input_quality": input_quality,
            "surface_wetness_proxy_net_index": round(float(wet_score - dry_score), 4),
            "wetness_pressure_index": round(float(wet_score), 4),
            "drying_potential_index": round(float(dry_score), 4),
            "surface_wetness_proxy_evidence": " | ".join(evidence),
            "rain_lookback_6h_status": row.get("rain_lookback_6h_status", ""),
            "rain_lookback_6h_max_observed_precipitation_mm": row.get("rain_lookback_6h_max_observed_precipitation_mm", ""),
            "rain_lookback_24h_status": row.get("rain_lookback_24h_status", ""),
            "rain_lookback_24h_max_observed_precipitation_mm": row.get("rain_lookback_24h_max_observed_precipitation_mm", ""),
            "rain_lookback_72h_status": row.get("rain_lookback_72h_status", ""),
            "rain_lookback_72h_max_observed_precipitation_mm": row.get("rain_lookback_72h_max_observed_precipitation_mm", ""),
            "rain_lookback_7d_status": row.get("rain_lookback_7d_status", ""),
            "rain_lookback_7d_max_observed_precipitation_mm": row.get("rain_lookback_7d_max_observed_precipitation_mm", ""),
            "positive_rain_local_dates_count_lookback_7d": row.get("positive_rain_local_dates_count_lookback_7d", ""),
            "positive_rain_local_dates_lookback_7d": row.get("positive_rain_local_dates_lookback_7d", ""),
            "hours_since_last_observed_rain": row.get("hours_since_last_observed_rain", ""),
            "last_observed_rain_time_utc": row.get("last_observed_rain_time_utc", ""),
            "last_observed_rain_station_ids": row.get("last_observed_rain_station_ids", ""),
            "last_observed_rain_station_names": row.get("last_observed_rain_station_names", ""),
            "last_observed_rain_precipitation_mm_max": row.get("last_observed_rain_precipitation_mm_max", ""),
            "temperature_c_mean_primary": temp,
            "relative_humidity_pct_mean_primary": humidity,
            "wind_speed_ms_mean_primary": wind,
            "wind_speed_ms_max_primary": wind_max,
            "sunshine_context_status": "SUNSHINE_NOT_AVAILABLE_IN_CURRENT_FEATURE_VECTOR_V1",
            "terrain_surface_context_status": "NOT_JOINED_IN_V1",
            "soil_moisture_claim_status": "NOT_CLAIMED_PROXY_ONLY",
            "zero_fallback_true_count": zero_fallback,
            "source_antecedent_csv": str(ANTECEDENT_CSV),
            "source_vector_csv": str(VECTOR_CSV),
            "scope_note": "Surface wetness proxy only. No true soil moisture claim, no hiking risk score, no THCI, no terrain/surface join, no missing-to-zero imputation.",
        }

        rows.append(out)

    return pd.DataFrame(rows)


def build_summary(proxy: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for col in [
        "surface_wetness_proxy_status",
        "surface_wetness_proxy_confidence",
        "surface_wetness_proxy_input_quality",
        "antecedent_precipitation_context_status",
        "sunshine_context_status",
        "terrain_surface_context_status",
        "soil_moisture_claim_status",
    ]:
        for key, group in proxy.groupby(col, dropna=False, sort=True):
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
        "activity_count": int(len(proxy)),
        "score_allowed_count": int(
            proxy["weather_sensitive_score_allowed"]
            .astype(str)
            .str.lower()
            .eq("true")
            .sum()
        ),
        "zero_fallback_true_count": int(
            pd.to_numeric(proxy["zero_fallback_true_count"], errors="coerce")
            .fillna(0)
            .sum()
        ),
    })

    return pd.DataFrame(rows)


def html_table(df: pd.DataFrame) -> str:
    return df.fillna("").to_html(index=False, escape=True, border=0)


def build_html(proxy: pd.DataFrame, summary: pd.DataFrame) -> str:
    key_cols = [
        "output_case",
        "activity_id",
        "surface_wetness_proxy_status",
        "surface_wetness_proxy_confidence",
        "surface_wetness_proxy_reason",
        "surface_wetness_proxy_net_index",
        "wetness_pressure_index",
        "drying_potential_index",
        "surface_wetness_proxy_evidence",
        "antecedent_precipitation_context_status",
        "rain_lookback_6h_status",
        "rain_lookback_6h_max_observed_precipitation_mm",
        "rain_lookback_24h_status",
        "rain_lookback_24h_max_observed_precipitation_mm",
        "rain_lookback_72h_status",
        "rain_lookback_72h_max_observed_precipitation_mm",
        "rain_lookback_7d_status",
        "rain_lookback_7d_max_observed_precipitation_mm",
        "hours_since_last_observed_rain",
        "last_observed_rain_time_utc",
        "last_observed_rain_station_names",
        "temperature_c_mean_primary",
        "relative_humidity_pct_mean_primary",
        "wind_speed_ms_mean_primary",
        "wind_speed_ms_max_primary",
        "sunshine_context_status",
        "terrain_surface_context_status",
        "soil_moisture_claim_status",
    ]

    allowed = proxy[
        proxy["weather_sensitive_score_allowed"]
        .astype(str)
        .str.lower()
        .eq("true")
    ].copy()

    zero_fallback = int(
        pd.to_numeric(proxy["zero_fallback_true_count"], errors="coerce")
        .fillna(0)
        .sum()
    )

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>IB3W Surface Wetness Proxy v1</title>
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
<h1>IB3W Surface Wetness Proxy v1</h1>
<section>
<p>Surface wetness proxy based on antecedent precipitation, last observed rain timing, temperature, relative humidity, and wind.</p>
<p>No true soil moisture claim, no hiking risk score, no THCI, no terrain/surface join, no missing-to-zero imputation.</p>
<p>Total activities: {len(proxy)}; evaluated activities: {len(allowed)}; zero fallback violations: {zero_fallback}</p>
</section>
<section>
<h2>Evaluated rows</h2>
<div class="wrap">{html_table(allowed[key_cols])}</div>
</section>
<section>
<h2>Full proxy review</h2>
<div class="wrap">{html_table(proxy[key_cols])}</div>
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

    antecedent = pd.read_csv(ANTECEDENT_CSV, dtype=str)
    vector = pd.read_csv(VECTOR_CSV, dtype=str)

    proxy = build_proxy(antecedent, vector)
    summary = build_summary(proxy)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    proxy_csv = OUT_DIR / "activity_surface_wetness_proxy.csv"
    summary_csv = OUT_DIR / "activity_surface_wetness_proxy_summary.csv"
    html_report = OUT_DIR / "activity_surface_wetness_proxy_report.html"

    proxy.to_csv(proxy_csv, index=False, encoding="utf-8-sig")
    summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")
    html_report.write_text(build_html(proxy, summary), encoding="utf-8")

    print("IB3W surface wetness proxy v1 written")
    print("proxy_csv:", proxy_csv)
    print("summary_csv:", summary_csv)
    print("html_report:", html_report)
    print()
    print("surface_wetness_proxy_status_distribution:")
    print(
        proxy.groupby("surface_wetness_proxy_status")
        .size()
        .reset_index(name="activity_count")
        .sort_values("activity_count", ascending=False)
        .to_string(index=False)
    )
    print()
    print("zero_fallback_true_total:", int(
        pd.to_numeric(proxy["zero_fallback_true_count"], errors="coerce")
        .fillna(0)
        .sum()
    ))


if __name__ == "__main__":
    main()
