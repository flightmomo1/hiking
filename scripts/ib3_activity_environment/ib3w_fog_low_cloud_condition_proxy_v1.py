from __future__ import annotations

import math
import sqlite3
from pathlib import Path

import pandas as pd


SCHEMA_VERSION = "ib3w_fog_low_cloud_condition_proxy_v1"

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
WEATHER_DB = Path("weather/tw_weather_2026-05-01.sqlite3")
OUT_DIR = Path("outputs/ib3w_fog_low_cloud_condition_proxy_v1")


def as_bool(value) -> bool:
    return str(value).strip().lower() == "true"


def as_num(value):
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return pd.NA if pd.isna(parsed) else float(parsed)


def split_stations(value) -> list[str]:
    if pd.isna(value):
        return []
    return [x.strip() for x in str(value).split("|") if x.strip()]


def dew_point_c(temp_c, rh_pct):
    if pd.isna(temp_c) or pd.isna(rh_pct):
        return pd.NA
    temp_c = float(temp_c)
    rh_pct = float(rh_pct)
    if rh_pct <= 0 or rh_pct > 100:
        return pd.NA
    a = 17.625
    b = 243.04
    gamma = math.log(rh_pct / 100.0) + (a * temp_c) / (b + temp_c)
    return (b * gamma) / (a - gamma)


def local_hour(ts: pd.Timestamp):
    if pd.isna(ts):
        return pd.NA
    return int((ts + pd.Timedelta(hours=8)).hour)


def is_night_or_early(ts: pd.Timestamp) -> bool:
    h = local_hour(ts)
    if pd.isna(h):
        return False
    return h >= 18 or h <= 8


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


def fetch_rows(conn, station_ids, start_utc, end_utc) -> pd.DataFrame:
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
      visibility_m,
      weather
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
        "visibility_m",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["weather"] = df["weather"].fillna("").astype(str).str.strip()
    df = df.dropna(subset=["obs_time_utc"])
    df = df.drop_duplicates(subset=["station_id", "obs_time_utc"])

    dew = []
    ttd = []
    for _, r in df.iterrows():
        td = dew_point_c(r.get("temperature_c"), r.get("relative_humidity_pct"))
        dew.append(td)
        if pd.isna(td) or pd.isna(r.get("temperature_c")):
            ttd.append(pd.NA)
        else:
            ttd.append(round(float(r.get("temperature_c")) - float(td), 4))

    df["estimated_dew_point_c"] = dew
    df["temperature_minus_dew_point_c"] = pd.to_numeric(pd.Series(ttd), errors="coerce")

    return df


def summarize_station_saturation(df: pd.DataFrame, station_ids: list[str]) -> tuple[int, int, float, str]:
    summaries = []
    weak_count = 0
    observed_count = 0

    for sid in station_ids:
        s = df[df["station_id"].astype(str) == str(sid)].copy()
        if s.empty:
            summaries.append(f"{sid}:rows=0:NO_DATA")
            continue

        observed_count += 1
        name = s["station_name"].dropna().astype(str).iloc[0] if s["station_name"].notna().any() else ""
        rh = pd.to_numeric(s["relative_humidity_pct"], errors="coerce").dropna()
        ttd = pd.to_numeric(s["temperature_minus_dew_point_c"], errors="coerce").dropna()

        rh_max = round(float(rh.max()), 4) if len(rh) else pd.NA
        ttd_min = round(float(ttd.min()), 4) if len(ttd) else pd.NA

        if not pd.isna(rh_max) and not pd.isna(ttd_min):
            if rh_max >= 98 and ttd_min <= 1.0:
                level = "SATURATION_STRONG"
                weak_count += 1
            elif rh_max >= 97 and ttd_min <= 1.5:
                level = "SATURATION_MODERATE"
                weak_count += 1
            elif rh_max >= 95 and ttd_min <= 3.0:
                level = "SATURATION_WEAK"
                weak_count += 1
            else:
                level = "SATURATION_NOT_SUPPORTED"
        else:
            level = "INSUFFICIENT"

        summaries.append(f"{sid}:{name}:rows={len(s)}:rh_max={rh_max}:ttd_min={ttd_min}:{level}")

    ratio = round(weak_count / observed_count, 4) if observed_count else pd.NA
    return weak_count, observed_count, ratio, " | ".join(summaries)


def build_context() -> pd.DataFrame:
    antecedent = pd.read_csv(ANTECEDENT_CSV, dtype=str)
    vector = pd.read_csv(VECTOR_CSV, dtype=str)

    merged = antecedent.merge(
        vector[["output_case", "activity_id", "zero_fallback_true_count"]],
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
        merged = merged.merge(
            surface[surface_cols],
            on=["output_case", "activity_id"],
            how="left",
        )
    else:
        merged["surface_wetness_proxy_status"] = ""
        merged["surface_wetness_proxy_confidence"] = ""
        merged["surface_wetness_proxy_net_index"] = ""

    rows = []

    with sqlite3.connect(WEATHER_DB) as conn:
        for _, src in merged.iterrows():
            allowed = as_bool(src.get("weather_sensitive_score_allowed"))
            start = pd.to_datetime(src.get("activity_start_time_utc"), errors="coerce", utc=True)
            end = pd.to_datetime(src.get("activity_end_time_utc"), errors="coerce", utc=True)
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
                "direct_visibility_observation_status": "VISIBILITY_M_UNAVAILABLE_IN_CURRENT_DB",
                "weather_text_observation_status": "WEATHER_TEXT_UNAVAILABLE_IN_CURRENT_DB",
                "dew_point_estimation_status": "ESTIMATED_FROM_TEMPERATURE_AND_RH_WHEN_AVAILABLE",
                "actual_fog_claim_status": "NOT_CLAIMED_NO_DIRECT_VISIBILITY_OR_WEATHER_TEXT",
                "actual_low_cloud_claim_status": "NOT_CLAIMED_CONDITION_PROXY_ONLY",
                "actual_navigation_failure_claim_status": "NOT_CLAIMED_REQUIRES_ACTIVITY_BEHAVIOR_LAYER",
                "thci_or_final_risk_status": "NOT_COMPUTED_CONTEXT_ONLY",
                "surface_wetness_proxy_status": src.get("surface_wetness_proxy_status", ""),
                "surface_wetness_proxy_confidence": src.get("surface_wetness_proxy_confidence", ""),
                "surface_wetness_proxy_net_index": src.get("surface_wetness_proxy_net_index", ""),
                "scope_note": "Fog/low-cloud condition proxy only. No direct fog observation, no direct visibility observation, no actual迷航 claim, no THCI, no final hiking risk score, no missing-to-zero imputation.",
            }

            if not allowed:
                out.update({
                    "activity_start_local_hour": "",
                    "activity_start_night_or_early_morning_flag": "",
                    "analysis_weather_row_count": 0,
                    "analysis_observed_station_count": 0,
                    "analysis_rh_mean_pct": "",
                    "analysis_rh_max_pct": "",
                    "analysis_t_minus_td_min_c": "",
                    "analysis_t_minus_td_mean_c": "",
                    "analysis_wind_mean_ms": "",
                    "analysis_wind_class": "WIND_UNKNOWN",
                    "analysis_station_agreement_ratio": "",
                    "analysis_station_saturation_summary": "",
                    "prestart_3h_temperature_change_c": "",
                    "fog_low_cloud_condition_proxy_status": "BLOCKED_BY_GATE",
                    "fog_low_cloud_condition_proxy_confidence": "NOT_EVALUATED",
                    "fog_low_cloud_condition_proxy_index_v1": "",
                    "fog_type_hint": "NO_FOG_TYPE_HINT",
                    "fog_low_cloud_condition_proxy_reason": "Weather-sensitive feature gate did not allow fog/low-cloud proxy evaluation.",
                    "fog_low_cloud_condition_proxy_evidence": "",
                    "zero_fallback_true_count": src.get("zero_fallback_true_count", src.get("zero_fallback_true_count_vector", 0)),
                })
                rows.append(out)
                continue

            if pd.isna(start) or pd.isna(end):
                raise ValueError(f"bad activity time: {src.get('activity_id')}")

            analysis_start = start - pd.Timedelta(hours=3)
            df = fetch_rows(conn, station_ids, analysis_start, end)

            pre3 = df[(df["obs_time_utc"] >= analysis_start) & (df["obs_time_utc"] <= start)].copy()

            rh = pd.to_numeric(df["relative_humidity_pct"], errors="coerce").dropna() if not df.empty else pd.Series(dtype=float)
            ttd = pd.to_numeric(df["temperature_minus_dew_point_c"], errors="coerce").dropna() if not df.empty else pd.Series(dtype=float)
            wind = pd.to_numeric(df["wind_speed_ms"], errors="coerce").dropna() if not df.empty else pd.Series(dtype=float)

            rh_mean = round(float(rh.mean()), 4) if len(rh) else pd.NA
            rh_max = round(float(rh.max()), 4) if len(rh) else pd.NA
            ttd_min = round(float(ttd.min()), 4) if len(ttd) else pd.NA
            ttd_mean = round(float(ttd.mean()), 4) if len(ttd) else pd.NA
            wind_mean = round(float(wind.mean()), 4) if len(wind) else pd.NA

            weak_count, observed_count, agreement, station_text = summarize_station_saturation(df, station_ids)

            temp_change = pd.NA
            if not pre3.empty:
                temp_rows = pre3.dropna(subset=["temperature_c"]).sort_values("obs_time_utc")
                if len(temp_rows) >= 2:
                    temp_change = round(float(temp_rows.iloc[-1]["temperature_c"]) - float(temp_rows.iloc[0]["temperature_c"]), 4)

            score = 0.0
            evidence = [
                "VISIBILITY_M_UNAVAILABLE_IN_CURRENT_DB",
                "WEATHER_TEXT_UNAVAILABLE_IN_CURRENT_DB",
            ]

            if not pd.isna(ttd_min):
                if ttd_min <= 1.0:
                    score += 2.0
                    evidence.append("T-Td min <= 1.0C, very near saturation")
                elif ttd_min <= 1.5:
                    score += 1.5
                    evidence.append("T-Td min <= 1.5C, near saturation")
                elif ttd_min <= 3.0:
                    score += 0.75
                    evidence.append("T-Td min <= 3.0C, weak saturation support")

            if not pd.isna(rh_max):
                if rh_max >= 98:
                    score += 1.5
                    evidence.append("RH max >= 98%")
                elif rh_max >= 97:
                    score += 1.0
                    evidence.append("RH max >= 97%")
                elif rh_max >= 95:
                    score += 0.5
                    evidence.append("RH max >= 95%")

            if not pd.isna(rh_mean):
                if rh_mean >= 95:
                    score += 1.0
                    evidence.append("RH mean >= 95%")
                elif rh_mean >= 90:
                    score += 0.5
                    evidence.append("RH mean >= 90%")

            if not pd.isna(agreement):
                if agreement >= 0.5:
                    score += 1.0
                    evidence.append("multi-station saturation support >= 0.5")
                elif agreement > 0:
                    score += 0.5
                    evidence.append("some station saturation support")

            if is_night_or_early(start):
                score += 0.75
                evidence.append("activity start is night or early morning")

            wet = str(src.get("surface_wetness_proxy_status", ""))
            if wet in [
                "SURFACE_WETNESS_PROXY_PERSISTENT_WETNESS_POSSIBLE",
                "SURFACE_WETNESS_PROXY_RECENT_RAIN_WETNESS_POSSIBLE",
            ]:
                score += 1.0
                evidence.append(f"surface wetness context supports moisture background: {wet}")
            elif wet in [
                "SURFACE_WETNESS_PROXY_WETNESS_POSSIBLE_LOW_TO_MODERATE",
                "SURFACE_WETNESS_PROXY_ANTECEDENT_WETNESS_PRESENT",
            ]:
                score += 0.5
                evidence.append(f"surface wetness context weakly supports moisture background: {wet}")

            if not pd.isna(temp_change):
                if temp_change <= -1.0:
                    score += 0.75
                    evidence.append("prestart 3h temperature dropped by >= 1C")
                elif temp_change <= -0.5:
                    score += 0.5
                    evidence.append("prestart 3h temperature dropped by >= 0.5C")

            wc = wind_class(wind_mean)
            if wc in ["CALM_LT_0P5_MS", "LIGHT_0P5_TO_2_MS"]:
                score += 0.5
                evidence.append(f"wind class may support radiation-fog-like conditions: {wc}")
            elif wc == "GENTLE_2_TO_5_MS":
                score += 0.5
                evidence.append(f"wind class may support hill/upslope low-cloud transport: {wc}")

            hints = []
            if is_night_or_early(start) and wc in ["CALM_LT_0P5_MS", "LIGHT_0P5_TO_2_MS"]:
                hints.append("RADIATION_FOG_LIKE")
            if wc in ["LIGHT_0P5_TO_2_MS", "GENTLE_2_TO_5_MS"] and not pd.isna(ttd_min) and ttd_min <= 2:
                hints.append("HILL_OR_UPSLOPE_LOW_CLOUD_LIKE")
            if "WETNESS" in wet:
                hints.append("RAIN_WET_SURFACE_FOG_LIKE")
            if not hints:
                hints.append("UNSPECIFIED_HUMIDITY_SATURATION_PROXY")

            score = round(float(score), 4)

            if score >= 6:
                status = "FOG_LOW_CLOUD_CONDITION_PROXY_HIGH_REVIEW_ONLY"
            elif score >= 4:
                status = "FOG_LOW_CLOUD_CONDITION_PROXY_MODERATE_REVIEW_ONLY"
            elif score >= 2:
                status = "FOG_LOW_CLOUD_CONDITION_PROXY_LOW_REVIEW_ONLY"
            else:
                status = "FOG_LOW_CLOUD_CONDITION_PROXY_NOT_SUPPORTED_BY_AVAILABLE_WEATHER"

            if score >= 4 and not pd.isna(agreement) and agreement >= 0.5:
                confidence = "MEDIUM_PROXY_ONLY"
            elif score >= 2:
                confidence = "LOW_TO_MEDIUM_PROXY_ONLY"
            else:
                confidence = "LOW_PROXY_ONLY"

            out.update({
                "activity_start_local_hour": local_hour(start),
                "activity_start_night_or_early_morning_flag": is_night_or_early(start),
                "analysis_weather_row_count": int(len(df)),
                "analysis_observed_station_count": observed_count,
                "analysis_rh_mean_pct": rh_mean,
                "analysis_rh_max_pct": rh_max,
                "analysis_t_minus_td_min_c": ttd_min,
                "analysis_t_minus_td_mean_c": ttd_mean,
                "analysis_wind_mean_ms": wind_mean,
                "analysis_wind_class": wc,
                "analysis_station_agreement_ratio": agreement,
                "analysis_station_saturation_summary": station_text,
                "prestart_3h_temperature_change_c": temp_change,
                "fog_low_cloud_condition_proxy_status": status,
                "fog_low_cloud_condition_proxy_confidence": confidence,
                "fog_low_cloud_condition_proxy_index_v1": score,
                "fog_type_hint": "|".join(sorted(set(hints))),
                "fog_low_cloud_condition_proxy_reason": "Fog/low-cloud favorable conditions are inferred from saturation, wind, timing, and moisture-background proxy evidence only.",
                "fog_low_cloud_condition_proxy_evidence": " | ".join(evidence),
                "zero_fallback_true_count": src.get("zero_fallback_true_count", src.get("zero_fallback_true_count_vector", 0)),
            })

            rows.append(out)

    return pd.DataFrame(rows)


def build_summary(context: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col in [
        "fog_low_cloud_condition_proxy_status",
        "fog_low_cloud_condition_proxy_confidence",
        "fog_type_hint",
        "direct_visibility_observation_status",
        "weather_text_observation_status",
        "actual_fog_claim_status",
        "actual_navigation_failure_claim_status",
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
        "fog_low_cloud_condition_proxy_status",
        "fog_low_cloud_condition_proxy_confidence",
        "fog_low_cloud_condition_proxy_index_v1",
        "fog_type_hint",
        "fog_low_cloud_condition_proxy_evidence",
        "activity_start_local_hour",
        "activity_start_night_or_early_morning_flag",
        "analysis_rh_mean_pct",
        "analysis_rh_max_pct",
        "analysis_t_minus_td_min_c",
        "analysis_t_minus_td_mean_c",
        "analysis_wind_mean_ms",
        "analysis_wind_class",
        "analysis_station_agreement_ratio",
        "analysis_station_saturation_summary",
        "prestart_3h_temperature_change_c",
        "surface_wetness_proxy_status",
        "direct_visibility_observation_status",
        "weather_text_observation_status",
        "actual_fog_claim_status",
        "actual_low_cloud_claim_status",
        "actual_navigation_failure_claim_status",
        "thci_or_final_risk_status",
    ]

    allowed = context[context["weather_sensitive_score_allowed"].astype(str).str.lower().eq("true")].copy()
    zero_fallback = int(pd.to_numeric(context["zero_fallback_true_count"], errors="coerce").fillna(0).sum())

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>IB3W Fog Low-cloud Condition Proxy v1</title>
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
<h1>IB3W Fog / Low-cloud Condition Proxy v1</h1>
<section>
<p>Fog/low-cloud condition proxy based on temperature, relative humidity, estimated dew point depression, wind, timing, and surface wetness context.</p>
<p>No direct fog observation, no direct visibility observation, no actual迷航 claim, no route-deviation claim, no THCI, no final hiking risk score, no missing-to-zero imputation.</p>
<p>Current DB direct fields are unavailable: visibility_m and weather text are kept as explicit unavailable statuses.</p>
<p>Total activities: {len(context)}; evaluated activities: {len(allowed)}; zero fallback violations: {zero_fallback}</p>
</section>
<section><h2>Evaluated rows</h2><div class="wrap">{html_table(allowed[key_cols])}</div></section>
<section><h2>Full fog/low-cloud proxy review</h2><div class="wrap">{html_table(context[key_cols])}</div></section>
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

    context_csv = OUT_DIR / "activity_fog_low_cloud_condition_proxy.csv"
    summary_csv = OUT_DIR / "activity_fog_low_cloud_condition_proxy_summary.csv"
    html_report = OUT_DIR / "activity_fog_low_cloud_condition_proxy_report.html"

    context.to_csv(context_csv, index=False, encoding="utf-8-sig")
    summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")
    html_report.write_text(build_html(context, summary), encoding="utf-8")

    print("IB3W fog low-cloud condition proxy v1 written")
    print("context_csv:", context_csv)
    print("summary_csv:", summary_csv)
    print("html_report:", html_report)
    print()
    print("fog_low_cloud_condition_proxy_status_distribution:")
    print(
        context.groupby("fog_low_cloud_condition_proxy_status")
        .size()
        .reset_index(name="activity_count")
        .sort_values("activity_count", ascending=False)
        .to_string(index=False)
    )
    print()
    print("zero_fallback_true_total:", int(pd.to_numeric(context["zero_fallback_true_count"], errors="coerce").fillna(0).sum()))


if __name__ == "__main__":
    main()
