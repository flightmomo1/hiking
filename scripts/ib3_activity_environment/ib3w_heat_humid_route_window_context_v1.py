from __future__ import annotations

import math
import sqlite3
from pathlib import Path

import pandas as pd


SCHEMA_VERSION = "ib3w_heat_humid_route_window_context_v1"

WEATHER_DB = Path("weather/tw_weather_2026-05-01.sqlite3")
OUT_DIR = Path("outputs/ib3w_heat_humid_route_window_context_v1")

PRIMARY_STATION_IDS = ["466910", "466930", "A0A460", "C0AC40"]
PRIMARY_STATION_LABEL = "466910|466930|A0A460|C0AC40"
ROUTE_BIN_WIDTH_M = 250.0
WEATHER_PAD_MIN = 30


SOURCE_GLOBS = [
    # Formal v1 scope:
    # one 2026 GPX/IB4 point-level source that overlaps the current weather DB.
    # Older IB3D 2024/2004 timelines are valid route-window candidates, but are excluded here
    # because they do not overlap weather/tw_weather_2026-05-01.sqlite3.
    "outputs/ib4_activity_output/actual_gpx_9stations/qixing_activity_risk_overlay_points.csv",
]


def safe(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def as_num(value):
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return pd.NA if pd.isna(parsed) else float(parsed)


def parse_bool(value) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def parse_time_series(series: pd.Series) -> pd.Series:
    """
    Handles common IB3/IB4 time cases:
    - Unix seconds in timestamp_s
    - Unix milliseconds
    - ISO/local-ish text time
    """
    raw = series.copy()

    numeric = pd.to_numeric(raw, errors="coerce")
    if numeric.notna().sum() > 0:
        med = float(numeric.dropna().median())
        if 1_000_000_000 <= med <= 2_000_000_000:
            return pd.to_datetime(numeric, unit="s", errors="coerce", utc=True)
        if 1_000_000_000_000 <= med <= 2_000_000_000_000:
            return pd.to_datetime(numeric, unit="ms", errors="coerce", utc=True)

    return pd.to_datetime(raw, errors="coerce", utc=True)


def first_existing_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def mode_str(series: pd.Series) -> str:
    s = series.dropna().astype(str).str.strip()
    s = s[s != ""]
    if s.empty:
        return ""
    return s.mode().iloc[0]


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
    """
    Rothfusz heat index approximation.
    Only computed when T >= 26.7C / 80F and RH >= 40%.
    Still proxy only; not WBGT.
    """
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
    return "HEAT_INDEX_COMPUTED_STANDARD_PROXY_NOT_WBGT", round(float((hi_f - 32.0) * 5.0 / 9.0), 4)


def fetch_weather(conn, start_utc, end_utc) -> pd.DataFrame:
    start_pad = start_utc - pd.Timedelta(minutes=WEATHER_PAD_MIN)
    end_pad = end_utc + pd.Timedelta(minutes=WEATHER_PAD_MIN)

    placeholders = ",".join(["?"] * len(PRIMARY_STATION_IDS))
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

    params = PRIMARY_STATION_IDS + [start_pad.isoformat(), end_pad.isoformat()]
    df = pd.read_sql_query(sql, conn, params=params)

    if df.empty:
        return pd.DataFrame(columns=[
            "station_id",
            "station_name",
            "obs_time",
            "temperature_c",
            "relative_humidity_pct",
            "wind_speed_ms",
            "wind_direction_deg",
            "precipitation_mm",
            "sunshine_duration_min",
            "uv_index",
            "obs_time_utc",
        ])

    df["obs_time_utc"] = pd.to_datetime(df["obs_time"], errors="coerce", utc=True)
    df["station_id"] = df["station_id"].astype(str).str.strip()
    df["station_name"] = df["station_name"].astype(str).str.strip()

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
            "weather_row_count": 0,
            "weather_station_count": 0,
            "weather_station_ids": "",
            "temperature_mean_c": pd.NA,
            "temperature_max_c": pd.NA,
            "relative_humidity_mean_pct": pd.NA,
            "relative_humidity_max_pct": pd.NA,
            "wind_speed_mean_ms": pd.NA,
            "wind_speed_max_ms": pd.NA,
            "wind_class": "WIND_UNKNOWN",
            "precipitation_positive_row_count": 0,
            "precipitation_max_observed_mm": pd.NA,
            "sunshine_available_row_count": 0,
            "uv_available_row_count": 0,
        }

    temp = pd.to_numeric(df["temperature_c"], errors="coerce").dropna()
    rh = pd.to_numeric(df["relative_humidity_pct"], errors="coerce").dropna()
    wind = pd.to_numeric(df["wind_speed_ms"], errors="coerce").dropna()
    rain = pd.to_numeric(df["precipitation_mm"], errors="coerce").dropna()
    sun = pd.to_numeric(df["sunshine_duration_min"], errors="coerce").dropna()
    uv = pd.to_numeric(df["uv_index"], errors="coerce").dropna()

    wind_mean = round(float(wind.mean()), 4) if len(wind) else pd.NA

    return {
        "weather_row_count": int(len(df)),
        "weather_station_count": int(df["station_id"].nunique()),
        "weather_station_ids": "|".join(sorted(df["station_id"].dropna().astype(str).unique().tolist())),
        "temperature_mean_c": round(float(temp.mean()), 4) if len(temp) else pd.NA,
        "temperature_max_c": round(float(temp.max()), 4) if len(temp) else pd.NA,
        "relative_humidity_mean_pct": round(float(rh.mean()), 4) if len(rh) else pd.NA,
        "relative_humidity_max_pct": round(float(rh.max()), 4) if len(rh) else pd.NA,
        "wind_speed_mean_ms": wind_mean,
        "wind_speed_max_ms": round(float(wind.max()), 4) if len(wind) else pd.NA,
        "wind_class": wind_class(wind_mean),
        "precipitation_positive_row_count": int((rain > 0).sum()) if len(rain) else 0,
        "precipitation_max_observed_mm": round(float(rain.max()), 4) if len(rain) else pd.NA,
        "sunshine_available_row_count": int(len(sun)),
        "uv_available_row_count": int(len(uv)),
    }


def score_heat_window(row: dict):
    score = 0.0
    evidence = [
        "SUNSHINE_DURATION_UNAVAILABLE_IN_CURRENT_DB",
        "UV_INDEX_UNAVAILABLE_IN_CURRENT_DB",
        "WBGT_NOT_COMPUTED_NO_SOLAR_RADIATION_GLOBE_TEMPERATURE_OR_HUMAN_HEAT_BALANCE_INPUTS",
    ]

    temp_mean = as_num(row.get("temperature_mean_c"))
    temp_max = as_num(row.get("temperature_max_c"))
    rh_mean = as_num(row.get("relative_humidity_mean_pct"))
    rh_max = as_num(row.get("relative_humidity_max_pct"))
    wind_mean = as_num(row.get("wind_speed_mean_ms"))
    heat_index = as_num(row.get("heat_index_c"))
    daytime_ratio = as_num(row.get("point_daytime_heat_window_ratio"))

    if row.get("weather_row_count", 0) == 0:
        return (
            "HEAT_HUMID_ROUTE_WINDOW_CONTEXT_WEATHER_UNAVAILABLE",
            "NOT_EVALUATED",
            pd.NA,
            "No weather observations were available for this route-distance/time window.",
            "WEATHER_OBSERVATION_UNAVAILABLE_FOR_WINDOW",
        )

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
        evidence.append("activity points overlap 09-15 local daytime heat window")

    temp_support = (
        (not pd.isna(temp_mean) and temp_mean >= 26)
        or (not pd.isna(temp_max) and temp_max >= 28)
        or (not pd.isna(heat_index) and heat_index >= 32)
    )

    score = round(float(score), 4)

    if score >= 6 and temp_support:
        status = "HEAT_HUMID_ROUTE_WINDOW_CONTEXT_ELEVATED_REVIEW_ONLY"
    elif score >= 4 and temp_support:
        status = "HEAT_HUMID_ROUTE_WINDOW_CONTEXT_MODERATE_REVIEW_ONLY"
    elif score >= 2:
        status = "HEAT_HUMID_ROUTE_WINDOW_CONTEXT_HUMID_MILD_BACKGROUND_REVIEW_ONLY"
    else:
        status = "HEAT_HUMID_ROUTE_WINDOW_CONTEXT_NOT_SUPPORTED_BY_AVAILABLE_WEATHER"

    if score >= 4 and temp_support:
        confidence = "MEDIUM_PROXY_ONLY"
    elif score >= 2:
        confidence = "LOW_TO_MEDIUM_PROXY_ONLY"
    else:
        confidence = "LOW_PROXY_ONLY"

    reason = (
        "Route-window heat/humid context is inferred from temperature, humidity, wind, "
        "activity route-distance bin, and available weather observations only."
    )
    return status, confidence, score, reason, " | ".join(evidence)


def read_activity_points(path: Path) -> tuple[pd.DataFrame, dict]:
    df = pd.read_csv(path, dtype=str)

    time_col = first_existing_col(df, ["timestamp_s", "time", "time_raw"])
    route_col = first_existing_col(df, ["reliable_route_dist_m", "route_dist_m", "projected_route_dist_m", "nearest_route_dist_m", "cum_dist_m"])
    lat_col = first_existing_col(df, ["raw_lat", "lat", "latitude"])
    lon_col = first_existing_col(df, ["raw_lon", "lon", "longitude"])

    meta = {
        "source_file": str(path),
        "time_col": time_col or "",
        "route_distance_col": route_col or "",
        "lat_col": lat_col or "",
        "lon_col": lon_col or "",
        "read_status": "OK",
        "skip_reason": "",
    }

    if not time_col:
        meta["read_status"] = "SKIP"
        meta["skip_reason"] = "missing time column"
        return pd.DataFrame(), meta

    if not route_col:
        meta["read_status"] = "SKIP"
        meta["skip_reason"] = "missing route distance column"
        return pd.DataFrame(), meta

    df["_time_utc"] = parse_time_series(df[time_col])
    df["_route_dist_m"] = pd.to_numeric(df[route_col], errors="coerce")

    if lat_col:
        df["_lat"] = pd.to_numeric(df[lat_col], errors="coerce")
    else:
        df["_lat"] = pd.NA

    if lon_col:
        df["_lon"] = pd.to_numeric(df[lon_col], errors="coerce")
    else:
        df["_lon"] = pd.NA

    if "usable_on_route" in df.columns:
        usable = df["usable_on_route"].map(parse_bool)
        usable_count = int(usable.sum())
        if usable_count > 0:
            df = df[usable].copy()

    df = df.dropna(subset=["_time_utc", "_route_dist_m"]).copy()

    if df.empty:
        meta["read_status"] = "SKIP"
        meta["skip_reason"] = "no valid time + route distance rows after parsing"
        return pd.DataFrame(), meta

    df["_route_bin_start_m"] = (df["_route_dist_m"] // ROUTE_BIN_WIDTH_M) * ROUTE_BIN_WIDTH_M
    df["_route_bin_end_m"] = df["_route_bin_start_m"] + ROUTE_BIN_WIDTH_M
    df["_local_hour"] = (df["_time_utc"] + pd.Timedelta(hours=8)).dt.hour
    df["_is_daytime_heat_window"] = df["_local_hour"].between(9, 15, inclusive="both")

    return df, meta


def activity_identity(df: pd.DataFrame, path: Path) -> dict:
    activity_id = mode_str(df["activity_id"]) if "activity_id" in df.columns else ""
    case_id = mode_str(df["case_id"]) if "case_id" in df.columns else ""
    route_folder = mode_str(df["route_folder"]) if "route_folder" in df.columns else ""

    if not activity_id:
        if "actual_gpx_9stations" in str(path).replace("\\", "/"):
            activity_id = "qixing_lengshuikeng_xiaoyoukeng_20260410_biji_gpx"
        else:
            activity_id = path.parent.name

    if not case_id:
        case_id = "qixing_lengshuikeng"

    if not route_folder:
        route_folder = "qixing_lengshuikeng"

    return {
        "activity_id": activity_id,
        "case_id": case_id,
        "route_folder": route_folder,
    }


def build_windows_for_file(path: Path, conn) -> tuple[list[dict], dict]:
    df, meta = read_activity_points(path)
    if df.empty:
        meta["window_count"] = 0
        return [], meta

    ident = activity_identity(df, path)
    weather_all = fetch_weather(conn, df["_time_utc"].min(), df["_time_utc"].max())

    rows = []
    for (bin_start, bin_end), g in df.groupby(["_route_bin_start_m", "_route_bin_end_m"], sort=True):
        t0 = g["_time_utc"].min()
        t1 = g["_time_utc"].max()

        weather = weather_all[
            (weather_all["obs_time_utc"] >= t0 - pd.Timedelta(minutes=WEATHER_PAD_MIN))
            & (weather_all["obs_time_utc"] <= t1 + pd.Timedelta(minutes=WEATHER_PAD_MIN))
        ].copy()

        w = summarize_weather(weather)
        hi_status, hi_c = heat_index_proxy_c(w["temperature_mean_c"], w["relative_humidity_mean_pct"])

        segment_id = mode_str(g["segment_id"]) if "segment_id" in g.columns else ""
        route_progress_state = mode_str(g["route_progress_state"]) if "route_progress_state" in g.columns else ""
        match_quality = mode_str(g["match_quality"]) if "match_quality" in g.columns else ""

        out = {
            "schema_version": SCHEMA_VERSION,
            "source_file": str(path),
            "route_folder": ident["route_folder"],
            "case_id": ident["case_id"],
            "activity_id": ident["activity_id"],
            "route_bin_width_m": ROUTE_BIN_WIDTH_M,
            "route_distance_start_m": round(float(bin_start), 4),
            "route_distance_end_m": round(float(bin_end), 4),
            "route_distance_mid_m": round(float((bin_start + bin_end) / 2.0), 4),
            "route_distance_label": f"{int(bin_start)}-{int(bin_end)}m",
            "window_start_time_utc": t0.isoformat(),
            "window_end_time_utc": t1.isoformat(),
            "window_duration_sec": round(float((t1 - t0).total_seconds()), 4),
            "point_count": int(len(g)),
            "point_time_col": meta["time_col"],
            "point_route_distance_col": meta["route_distance_col"],
            "point_lat_mean": round(float(pd.to_numeric(g["_lat"], errors="coerce").mean()), 7) if pd.to_numeric(g["_lat"], errors="coerce").notna().any() else pd.NA,
            "point_lon_mean": round(float(pd.to_numeric(g["_lon"], errors="coerce").mean()), 7) if pd.to_numeric(g["_lon"], errors="coerce").notna().any() else pd.NA,
            "point_daytime_heat_window_count": int(g["_is_daytime_heat_window"].sum()),
            "point_daytime_heat_window_ratio": round(float(g["_is_daytime_heat_window"].mean()), 4),
            "segment_id_mode": segment_id,
            "route_progress_state_mode": route_progress_state,
            "match_quality_mode": match_quality,
            "primary_station_ids": PRIMARY_STATION_LABEL,
            "sunshine_direct_observation_status": "SUNSHINE_DURATION_UNAVAILABLE_IN_CURRENT_DB",
            "uv_direct_observation_status": "UV_INDEX_UNAVAILABLE_IN_CURRENT_DB",
            "wbgt_status": "NOT_COMPUTED_NO_WBGT_SOLAR_RADIATION_OR_GLOBE_TEMPERATURE",
            "heat_illness_medical_claim_status": "NOT_CLAIMED_NOT_MEDICAL_DIAGNOSIS",
            "thci_or_final_risk_status": "NOT_COMPUTED_CONTEXT_ONLY",
            "scope_note": "Route-window heat/humid context only. No WBGT, no UV, no direct sunshine, no heat illness diagnosis, no medical judgment, no THCI, no final hiking risk score, no missing-to-zero imputation.",
            "zero_fallback_true_count": 0,
        }
        out.update(w)
        out["heat_index_status"] = hi_status
        out["heat_index_c"] = hi_c

        status, confidence, score, reason, evidence = score_heat_window(out)
        out["heat_humid_route_window_context_status"] = status
        out["heat_humid_route_window_context_confidence"] = confidence
        out["heat_humid_route_window_index_v1"] = score
        out["heat_humid_route_window_context_reason"] = reason
        out["heat_humid_route_window_context_evidence"] = evidence

        rows.append(out)

    meta["window_count"] = len(rows)
    meta["activity_id"] = ident["activity_id"]
    meta["case_id"] = ident["case_id"]
    meta["activity_start_time_utc"] = df["_time_utc"].min().isoformat()
    meta["activity_end_time_utc"] = df["_time_utc"].max().isoformat()
    meta["weather_row_count_for_activity"] = int(len(weather_all))
    return rows, meta


def collect_source_files() -> list[Path]:
    files: list[Path] = []
    for pattern in SOURCE_GLOBS:
        files.extend(sorted(Path(".").glob(pattern)))

    unique = []
    seen = set()
    for p in files:
        key = str(p)
        if key not in seen:
            unique.append(p)
            seen.add(key)
    return unique


def build_summary(context: pd.DataFrame, source_summary: pd.DataFrame) -> pd.DataFrame:
    rows = []

    if not context.empty:
        for col in [
            "heat_humid_route_window_context_status",
            "heat_humid_route_window_context_confidence",
            "heat_index_status",
            "sunshine_direct_observation_status",
            "uv_direct_observation_status",
            "wbgt_status",
            "heat_illness_medical_claim_status",
            "thci_or_final_risk_status",
        ]:
            for key, group in context.groupby(col, dropna=False, sort=True):
                rows.append({
                    "schema_version": SCHEMA_VERSION,
                    "summary_type": col,
                    "summary_key": key,
                    "row_count": int(len(group)),
                    "activity_count": int(group["activity_id"].nunique()),
                    "zero_fallback_true_count": int(pd.to_numeric(group["zero_fallback_true_count"], errors="coerce").fillna(0).sum()),
                })

        rows.append({
            "schema_version": SCHEMA_VERSION,
            "summary_type": "overall",
            "summary_key": "ALL_ROUTE_WINDOWS",
            "row_count": int(len(context)),
            "activity_count": int(context["activity_id"].nunique()),
            "zero_fallback_true_count": int(pd.to_numeric(context["zero_fallback_true_count"], errors="coerce").fillna(0).sum()),
        })

    rows.append({
        "schema_version": SCHEMA_VERSION,
        "summary_type": "source_files",
        "summary_key": "ALL_SOURCE_FILES",
        "row_count": int(len(source_summary)),
        "activity_count": int(source_summary["activity_id"].nunique()) if "activity_id" in source_summary.columns and not source_summary.empty else 0,
        "zero_fallback_true_count": 0,
    })

    return pd.DataFrame(rows)


def html_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "<p>No rows.</p>"
    return df.fillna("").to_html(index=False, escape=True, border=0)


def build_html(context: pd.DataFrame, summary: pd.DataFrame, source_summary: pd.DataFrame) -> str:
    key_cols = [
        "activity_id",
        "route_distance_label",
        "window_start_time_utc",
        "window_end_time_utc",
        "point_count",
        "segment_id_mode",
        "route_progress_state_mode",
        "temperature_mean_c",
        "temperature_max_c",
        "relative_humidity_mean_pct",
        "relative_humidity_max_pct",
        "wind_speed_mean_ms",
        "wind_class",
        "point_daytime_heat_window_ratio",
        "heat_index_status",
        "heat_humid_route_window_context_status",
        "heat_humid_route_window_context_confidence",
        "heat_humid_route_window_index_v1",
        "heat_humid_route_window_context_evidence",
        "sunshine_direct_observation_status",
        "uv_direct_observation_status",
        "wbgt_status",
        "heat_illness_medical_claim_status",
        "thci_or_final_risk_status",
    ]

    shown = context.copy()
    if not shown.empty:
        shown = shown.sort_values(["activity_id", "route_distance_start_m", "window_start_time_utc"])

    zero = int(pd.to_numeric(context["zero_fallback_true_count"], errors="coerce").fillna(0).sum()) if not context.empty else 0

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>IB3W Heat / Humid Route-window Context v1</title>
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
<h1>IB3W Heat / Humid Route-window Context v1</h1>
<section>
<p>Route-window heat/humid context based on activity route-distance bins, point timestamps, primary mountain station observations, temperature, relative humidity, and wind.</p>
<p>No WBGT, no UV, no direct sunshine, no heat illness diagnosis, no medical judgment, no THCI, no final hiking risk score, no missing-to-zero imputation.</p>
<p>Route bin width: {ROUTE_BIN_WIDTH_M} m; route-window rows: {len(context)}; source files: {len(source_summary)}; zero fallback violations: {zero}</p>
</section>
<section><h2>Route-window context rows</h2><div class="wrap">{html_table(shown[key_cols] if not shown.empty else shown)}</div></section>
<section><h2>Summary</h2><div class="wrap">{html_table(summary)}</div></section>
<section><h2>Source file summary</h2><div class="wrap">{html_table(source_summary)}</div></section>
</body>
</html>
"""


def main() -> None:
    if not WEATHER_DB.exists():
        raise FileNotFoundError(WEATHER_DB)

    source_files = collect_source_files()
    all_rows: list[dict] = []
    source_meta: list[dict] = []

    with sqlite3.connect(WEATHER_DB) as conn:
        for path in source_files:
            rows, meta = build_windows_for_file(path, conn)
            all_rows.extend(rows)
            source_meta.append(meta)

    context = pd.DataFrame(all_rows)
    source_summary = pd.DataFrame(source_meta)
    summary = build_summary(context, source_summary)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    context_csv = OUT_DIR / "activity_heat_humid_route_window_context.csv"
    source_summary_csv = OUT_DIR / "activity_heat_humid_route_window_source_summary.csv"
    summary_csv = OUT_DIR / "activity_heat_humid_route_window_context_summary.csv"
    html_report = OUT_DIR / "activity_heat_humid_route_window_context_report.html"

    context.to_csv(context_csv, index=False, encoding="utf-8-sig")
    source_summary.to_csv(source_summary_csv, index=False, encoding="utf-8-sig")
    summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")
    html_report.write_text(build_html(context, summary, source_summary), encoding="utf-8")

    print("IB3W heat/humid route-window context v1 written")
    print("context_csv:", context_csv)
    print("source_summary_csv:", source_summary_csv)
    print("summary_csv:", summary_csv)
    print("html_report:", html_report)
    print()
    print("source files:", len(source_files))
    print("route window rows:", len(context))
    print()
    if not context.empty:
        print("heat_humid_route_window_context_status_distribution:")
        print(
            context.groupby("heat_humid_route_window_context_status")
            .size()
            .reset_index(name="row_count")
            .sort_values("row_count", ascending=False)
            .to_string(index=False)
        )
        print()
        print("zero_fallback_true_total:", int(pd.to_numeric(context["zero_fallback_true_count"], errors="coerce").fillna(0).sum()))
    else:
        print("No route-window rows generated.")


if __name__ == "__main__":
    main()
