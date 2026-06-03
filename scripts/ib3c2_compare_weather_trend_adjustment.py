# -*- coding: utf-8 -*-
from pathlib import Path

import numpy as np
import pandas as pd


# =========================================================
# A. Input / Output
# =========================================================
RISK_CSV = Path("ib2_v2_route_risk_output/qixing_route_risk_v2.csv")

SEMANTIC_CSV = Path(
    "ib1c_route_profile_semantic_output/qixing_route_profile_semantic_enriched.csv"
)

WEATHER_SUMMARY_CSV = Path(
    "ib3_environment_output/qixing_weather_summary_by_station.csv"
)

WATER_SUMMARY_CSV = Path(
    "ib3_environment_output/qixing_water_summary_by_station.csv"
)

# ib3b2 output
WEATHER_TREND_FEATURES_CSV = Path(
    "ib3_environment_output/qixing_weather_trend_features.csv"
)

WEATHER_DATA_QUALITY_CSV = Path(
    "ib3_environment_output/qixing_weather_data_quality_summary.csv"
)

OUT_DIR = Path("ib3_environment_output")

OUT_COMPARE_CSV = OUT_DIR / "qixing_environment_adjusted_risk_compare_weather_trend.csv"
OUT_SUMMARY_CSV = OUT_DIR / "qixing_environment_adjusted_risk_compare_weather_trend_summary.csv"


# =========================================================
# B. Config
# =========================================================
WEATHER_STATION_WEIGHTS = {
    "466930": 0.40,  # 陽明山
    "466910": 0.30,  # 鞍部
    "C0AC40": 0.15,  # 大屯山
    "A0A460": 0.10,  # 文化大學
    "C0AH40": 0.05,  # 平等
}

WATER_STATION_WEIGHTS = {
    "1140H179": 0.25,  # 磺溪橋_北
    "1140H180": 0.20,  # 中和橋_北
    "1140H175": 0.20,  # 薇閣_北
    "1140H162": 0.20,  # 三和橋
    "1010H006": 0.15,  # 新磺溪橋(即時)
}

RAIN_SUM_CAP_MM = 200.0
WIND_MAX_CAP_MS = 15.0
HUMIDITY_CAP_PCT = 100.0
WATER_CHANGE_CAP_M = 0.5
WATER_RANGE_CAP_M = 1.0

# 趨勢補償用
PRE_WETNESS_CAP_MM = 20.0
POST_LAG_RAIN_CAP_MM = 20.0

WEATHER_MODIFIER_MAX = 2.0
HYDRO_MODIFIER_MAX = 1.2
TOTAL_ENV_MODIFIER_MAX = 2.8

RISK_BAND_THRESHOLDS = {
    "low": 2.0,
    "moderate": 4.0,
    "high": 6.0,
}


# =========================================================
# C. Utility
# =========================================================
def ensure_exists(fp: Path):
    if not fp.exists():
        raise FileNotFoundError(f"找不到檔案：{fp.resolve()}")


def normalize_columns(df: pd.DataFrame):
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    return out


def read_optional_csv(fp: Path):
    if not fp.exists():
        return pd.DataFrame()
    return normalize_columns(pd.read_csv(fp))


def to_numeric_safe(df: pd.DataFrame, cols):
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def find_distance_col(df: pd.DataFrame):
    candidates = ["dist_m", "cumdist_m", "distance_m", "cum_dist_m", "distance"]
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(f"找不到距離欄位，現有欄位：{list(df.columns)}")


def find_base_risk_col(df: pd.DataFrame):
    for c in ["risk_score_smooth", "risk_score", "segment_risk_score"]:
        if c in df.columns:
            return c
    raise KeyError(f"找不到風險分數欄位，現有欄位：{list(df.columns)}")


def risk_band_from_score(score):
    if pd.isna(score):
        return "unknown"
    if score < RISK_BAND_THRESHOLDS["low"]:
        return "low"
    if score < RISK_BAND_THRESHOLDS["moderate"]:
        return "moderate"
    if score < RISK_BAND_THRESHOLDS["high"]:
        return "high"
    return "very_high"


def contains_any(series_value, keywords):
    if pd.isna(series_value):
        return False
    s = str(series_value).lower()
    return any(k.lower() in s for k in keywords)


def weighted_mean_by_station(df, value_col, weight_map):
    if df.empty or value_col not in df.columns:
        return np.nan

    rows = []

    for _, row in df.iterrows():
        station_id = str(row.get("station_id", ""))
        val = row.get(value_col, np.nan)

        if pd.isna(val):
            continue

        w = weight_map.get(station_id, 0.0)

        if w <= 0:
            continue

        rows.append((float(val), float(w)))

    if not rows:
        return np.nan

    total_w = sum(w for _, w in rows)

    if total_w <= 0:
        return np.nan

    return sum(v * w for v, w in rows) / total_w


def weighted_max_by_station(df, value_col, weight_map):
    if df.empty or value_col not in df.columns:
        return np.nan

    vals = []

    for _, row in df.iterrows():
        station_id = str(row.get("station_id", ""))
        val = row.get(value_col, np.nan)

        if pd.isna(val):
            continue

        if station_id in weight_map:
            vals.append(float(val))

    if not vals:
        return np.nan

    return max(vals)


def safe_float(v, default=0.0):
    try:
        if pd.isna(v):
            return default
        return float(v)
    except Exception:
        return default


# =========================================================
# D. Weather / Hydro Index
# =========================================================
def factor_from_rain_mm(mm, cap_mm):
    mm = safe_float(mm, default=0.0)

    if mm <= 0:
        return 0.0

    return min(max(mm / cap_mm, 0.0), 1.0)


def factor_from_humidity_pct(humidity):
    if pd.isna(humidity):
        return 0.0

    humidity_capped = min(max(float(humidity), 0.0), HUMIDITY_CAP_PCT)
    return max(0.0, (humidity_capped - 80.0) / 20.0)


def factor_from_wind_ms(wind_max):
    wind_max = safe_float(wind_max, default=0.0)
    wind_max_capped = min(max(wind_max, 0.0), WIND_MAX_CAP_MS)
    return wind_max_capped / WIND_MAX_CAP_MS


def factor_from_temperature_c(temp_mean):
    if pd.isna(temp_mean):
        return 0.0

    temp_mean = float(temp_mean)

    if temp_mean < 15.0:
        return min((15.0 - temp_mean) / 10.0, 1.0)

    if temp_mean > 30.0:
        return min((temp_mean - 30.0) / 10.0, 1.0)

    return 0.0


def wetness_factor_from_status(status, hint):
    """
    將 ib3b2 的 rain_data_status / weather_trend_hint 轉成濕滑代理分數。
    """
    status = "" if pd.isna(status) else str(status)
    hint = "" if pd.isna(hint) else str(hint)

    s = status + "|" + hint

    if "observed_rain" in s or "rain_observed" in s:
        return 1.00
    if "rain_lag_suspected" in s:
        return 0.75
    if "prior_rain_wet_trail" in s or "wet_trail_from_prior_rain" in s:
        return 0.55
    if "suspected_wet_high_humidity" in s or "possible_mist_or_drizzle" in s:
        return 0.50
    if "humid_no_measured_rain" in s:
        return 0.30
    if "rain_data_uncertain_coarse_update" in s or "coarse_update_frequency" in s:
        return 0.20

    return 0.0


def build_weather_index_original(weather_summary: pd.DataFrame):
    """
    舊方法：只使用 weather summary 中的雨量、濕度、風速、溫度。
    """
    if weather_summary.empty:
        return {
            "original_weather_available": 0,
            "original_weather_rain_sum_mm": 0.0,
            "original_weather_rain_factor": 0.0,
            "original_weather_humidity_pct": np.nan,
            "original_weather_humidity_factor": 0.0,
            "original_weather_wind_max_ms": 0.0,
            "original_weather_wind_factor": 0.0,
            "original_weather_temp_mean_c": np.nan,
            "original_weather_temp_factor": 0.0,
            "original_weather_modifier_base": 0.0,
        }

    w = weather_summary.copy()
    w["station_id"] = w["station_id"].astype(str)

    numeric_cols = [
        "temperature_mean_c",
        "humidity_mean_pct",
        "wind_speed_max_ms",
        "wind_gust_max_ms",
        "precipitation_sum_mm",
        "precipitation_1hr_max_mm",
        "visibility_min_m",
    ]
    w = to_numeric_safe(w, numeric_cols)

    rain_sum = weighted_mean_by_station(w, "precipitation_sum_mm", WEATHER_STATION_WEIGHTS)
    humidity = weighted_mean_by_station(w, "humidity_mean_pct", WEATHER_STATION_WEIGHTS)
    temp_mean = weighted_mean_by_station(w, "temperature_mean_c", WEATHER_STATION_WEIGHTS)
    wind_max = weighted_max_by_station(w, "wind_speed_max_ms", WEATHER_STATION_WEIGHTS)

    if pd.isna(rain_sum):
        rain_sum = 0.0

    if pd.isna(wind_max):
        wind_max = 0.0

    rain_factor = factor_from_rain_mm(rain_sum, RAIN_SUM_CAP_MM)
    humidity_factor = factor_from_humidity_pct(humidity)
    wind_factor = factor_from_wind_ms(wind_max)
    temp_factor = factor_from_temperature_c(temp_mean)

    weather_modifier_base = (
        1.20 * rain_factor
        + 0.35 * humidity_factor
        + 0.35 * wind_factor
        + 0.25 * temp_factor
    )
    weather_modifier_base = min(weather_modifier_base, WEATHER_MODIFIER_MAX)

    return {
        "original_weather_available": 1,
        "original_weather_rain_sum_mm": rain_sum,
        "original_weather_rain_factor": rain_factor,
        "original_weather_humidity_pct": humidity,
        "original_weather_humidity_factor": humidity_factor,
        "original_weather_wind_max_ms": wind_max,
        "original_weather_wind_factor": wind_factor,
        "original_weather_temp_mean_c": temp_mean,
        "original_weather_temp_factor": temp_factor,
        "original_weather_modifier_base": weather_modifier_base,
    }


def build_weather_index_trend(weather_summary, trend_features, quality_summary):
    """
    新方法：原始 weather summary + ib3b2 趨勢特徵。
    目的：補償「雨量 0，但高濕、霧雨、前期雨、更新頻率粗」造成的濕滑低估。
    """
    original = build_weather_index_original(weather_summary)

    observed_rain_factor = original["original_weather_rain_factor"]
    humidity_factor = original["original_weather_humidity_factor"]
    wind_factor = original["original_weather_wind_factor"]
    temp_factor = original["original_weather_temp_factor"]

    if trend_features.empty:
        pre_wetness_rain_mm = np.nan
        post_lag_rain_mm = np.nan
        wetness_status_factor = 0.0
        rain_data_status = "trend_data_missing"
        weather_trend_hint = "trend_data_missing"
    else:
        tf = trend_features.copy()
        tf["station_id"] = tf["station_id"].astype(str)

        numeric_cols = [
            "rain_sum_mm_pre_wetness",
            "rain_sum_mm_post_lag",
            "rain_sum_mm_activity",
            "humidity_mean_pct_activity",
            "humidity_above_95_ratio_activity",
            "wind_speed_max_ms_activity",
            "dist_to_route_center_km",
        ]
        tf = to_numeric_safe(tf, numeric_cols)

        pre_wetness_rain_mm = weighted_mean_by_station(
            tf,
            "rain_sum_mm_pre_wetness",
            WEATHER_STATION_WEIGHTS,
        )

        post_lag_rain_mm = weighted_mean_by_station(
            tf,
            "rain_sum_mm_post_lag",
            WEATHER_STATION_WEIGHTS,
        )

        tf["wetness_status_factor"] = [
            wetness_factor_from_status(s, h)
            for s, h in zip(
                tf.get("rain_data_status", pd.Series([""] * len(tf))),
                tf.get("weather_trend_hint", pd.Series([""] * len(tf))),
            )
        ]

        wetness_status_factor = weighted_mean_by_station(
            tf,
            "wetness_status_factor",
            WEATHER_STATION_WEIGHTS,
        )

        if pd.isna(wetness_status_factor):
            wetness_status_factor = 0.0

        # 最近測站狀態，供摘要解讀
        if "dist_to_route_center_km" in tf.columns:
            nearest = tf.sort_values("dist_to_route_center_km").head(1)
        else:
            nearest = tf.head(1)

        if nearest.empty:
            rain_data_status = "unknown"
            weather_trend_hint = "unknown"
        else:
            rain_data_status = str(nearest["rain_data_status"].iloc[0]) if "rain_data_status" in nearest.columns else "unknown"
            weather_trend_hint = str(nearest["weather_trend_hint"].iloc[0]) if "weather_trend_hint" in nearest.columns else "unknown"

    pre_wetness_factor = factor_from_rain_mm(pre_wetness_rain_mm, PRE_WETNESS_CAP_MM) * 0.65
    post_lag_rain_factor = factor_from_rain_mm(post_lag_rain_mm, POST_LAG_RAIN_CAP_MM) * 0.50

    effective_wetness_factor = np.nanmax(
        [
            observed_rain_factor,
            pre_wetness_factor,
            post_lag_rain_factor,
            wetness_status_factor,
        ]
    )

    if pd.isna(effective_wetness_factor):
        effective_wetness_factor = 0.0

    # 資料品質摘要
    if quality_summary.empty:
        weather_data_quality = "not_available"
        dominant_rain_data_status = rain_data_status
        dominant_weather_trend_hint = weather_trend_hint
        suspected_wet_station_count = np.nan
        rain_lag_suspected_station_count = np.nan
    else:
        q = quality_summary.iloc[0]
        weather_data_quality = q.get("weather_data_quality", "unknown")
        dominant_rain_data_status = q.get("dominant_rain_data_status", rain_data_status)
        dominant_weather_trend_hint = q.get("dominant_weather_trend_hint", weather_trend_hint)
        suspected_wet_station_count = q.get("suspected_wet_station_count", np.nan)
        rain_lag_suspected_station_count = q.get("rain_lag_suspected_station_count", np.nan)

    trend_weather_modifier_base = (
        1.20 * observed_rain_factor
        + 0.70 * effective_wetness_factor
        + 0.35 * humidity_factor
        + 0.35 * wind_factor
        + 0.25 * temp_factor
    )
    trend_weather_modifier_base = min(trend_weather_modifier_base, WEATHER_MODIFIER_MAX)

    return {
        "trend_weather_available": original["original_weather_available"],

        "trend_weather_rain_sum_mm": original["original_weather_rain_sum_mm"],
        "trend_weather_observed_rain_factor": observed_rain_factor,

        "trend_weather_pre_wetness_rain_mm": pre_wetness_rain_mm,
        "trend_weather_pre_wetness_factor": pre_wetness_factor,

        "trend_weather_post_lag_rain_mm": post_lag_rain_mm,
        "trend_weather_post_lag_rain_factor": post_lag_rain_factor,

        "trend_weather_wetness_status_factor": wetness_status_factor,
        "trend_weather_effective_wetness_factor": effective_wetness_factor,

        "trend_weather_humidity_pct": original["original_weather_humidity_pct"],
        "trend_weather_humidity_factor": humidity_factor,

        "trend_weather_wind_max_ms": original["original_weather_wind_max_ms"],
        "trend_weather_wind_factor": wind_factor,

        "trend_weather_temp_mean_c": original["original_weather_temp_mean_c"],
        "trend_weather_temp_factor": temp_factor,

        "trend_weather_modifier_base": trend_weather_modifier_base,

        "rain_data_status": rain_data_status,
        "weather_trend_hint": weather_trend_hint,
        "weather_data_quality": weather_data_quality,
        "dominant_rain_data_status": dominant_rain_data_status,
        "dominant_weather_trend_hint": dominant_weather_trend_hint,
        "suspected_wet_station_count": suspected_wet_station_count,
        "rain_lag_suspected_station_count": rain_lag_suspected_station_count,
    }


def build_hydro_index(water_summary: pd.DataFrame):
    if water_summary.empty:
        return {
            "hydro_available": 0,
            "hydro_water_change_m": 0.0,
            "hydro_water_range_m": 0.0,
            "hydro_change_factor": 0.0,
            "hydro_range_factor": 0.0,
            "hydro_modifier_base": 0.0,
        }

    h = water_summary.copy()
    h["station_id"] = h["station_id"].astype(str)

    numeric_cols = [
        "water_level_change_m",
        "water_level_range_m",
        "water_level_mean_m",
        "water_level_max_m",
        "valid_check_result_ratio",
    ]
    h = to_numeric_safe(h, numeric_cols)

    water_change = weighted_mean_by_station(h, "water_level_change_m", WATER_STATION_WEIGHTS)
    water_range = weighted_mean_by_station(h, "water_level_range_m", WATER_STATION_WEIGHTS)

    if pd.isna(water_change):
        water_change = 0.0

    if pd.isna(water_range):
        water_range = 0.0

    water_change_pos = max(water_change, 0.0)

    change_factor = min(water_change_pos / WATER_CHANGE_CAP_M, 1.0)
    range_factor = min(max(water_range, 0.0) / WATER_RANGE_CAP_M, 1.0)

    hydro_modifier_base = (
        0.75 * change_factor
        + 0.45 * range_factor
    )
    hydro_modifier_base = min(hydro_modifier_base, HYDRO_MODIFIER_MAX)

    return {
        "hydro_available": 1,
        "hydro_water_change_m": water_change,
        "hydro_water_range_m": water_range,
        "hydro_change_factor": change_factor,
        "hydro_range_factor": range_factor,
        "hydro_modifier_base": hydro_modifier_base,
    }


# =========================================================
# E. Segment sensitivity
# =========================================================
def compute_segment_sensitivity(df: pd.DataFrame):
    out = df.copy()

    out["rain_sensitivity"] = 1.00
    out["wind_sensitivity"] = 1.00
    out["hydro_sensitivity"] = 0.15
    out["slip_sensitivity"] = 1.00

    if "surface_class" in out.columns:
        stone_mask = out["surface_class"].apply(
            lambda v: contains_any(v, ["stone", "rock", "paved_stone"])
        )
        asphalt_mask = out["surface_class"].apply(
            lambda v: contains_any(v, ["asphalt", "concrete"])
        )

        out.loc[stone_mask, "slip_sensitivity"] += 0.35
        out.loc[asphalt_mask, "slip_sensitivity"] += 0.15

    if "route_semantic_class" in out.columns:
        steps_mask = out["route_semantic_class"].apply(
            lambda v: contains_any(v, ["steps"])
        )
        road_mask = out["route_semantic_class"].apply(
            lambda v: contains_any(v, ["road", "service"])
        )

        out.loc[steps_mask, "slip_sensitivity"] += 0.30
        out.loc[road_mask, "slip_sensitivity"] -= 0.10

    if "hazard_flags" in out.columns:
        hazard_mask = out["hazard_flags"].apply(
            lambda v: contains_any(v, ["cliff", "scree", "bare_rock", "landslide"])
        )
        out.loc[hazard_mask, "rain_sensitivity"] += 0.25
        out.loc[hazard_mask, "wind_sensitivity"] += 0.35

    if "hydrology_flags" in out.columns:
        hydro_mask = out["hydrology_flags"].apply(
            lambda v: contains_any(v, ["waterway", "wetland", "water_area"])
        )
        out.loc[hydro_mask, "hydro_sensitivity"] += 0.85
        out.loc[hydro_mask, "rain_sensitivity"] += 0.15

    out["rain_sensitivity"] = out["rain_sensitivity"].clip(0.5, 1.8)
    out["wind_sensitivity"] = out["wind_sensitivity"].clip(0.5, 1.8)
    out["hydro_sensitivity"] = out["hydro_sensitivity"].clip(0.0, 1.5)
    out["slip_sensitivity"] = out["slip_sensitivity"].clip(0.5, 1.8)

    return out


# =========================================================
# F. Adjustment methods
# =========================================================
def apply_original_adjustment(df, original_weather_idx, hydro_idx, base_risk_col):
    out = df.copy()

    original_weather_rain_component = (
        1.20
        * original_weather_idx["original_weather_rain_factor"]
        * out["rain_sensitivity"]
        * out["slip_sensitivity"]
    )

    original_weather_wind_component = (
        0.35
        * original_weather_idx["original_weather_wind_factor"]
        * out["wind_sensitivity"]
    )

    original_weather_humidity_component = (
        0.35
        * original_weather_idx["original_weather_humidity_factor"]
    )

    original_weather_temp_component = (
        0.25
        * original_weather_idx["original_weather_temp_factor"]
    )

    out["original_weather_rain_component"] = original_weather_rain_component
    out["original_weather_wind_component"] = original_weather_wind_component
    out["original_weather_humidity_component"] = original_weather_humidity_component
    out["original_weather_temp_component"] = original_weather_temp_component

    out["original_weather_modifier"] = (
        out["original_weather_rain_component"]
        + out["original_weather_wind_component"]
        + out["original_weather_humidity_component"]
        + out["original_weather_temp_component"]
    ).clip(0, WEATHER_MODIFIER_MAX)

    out["hydro_modifier"] = (
        hydro_idx["hydro_modifier_base"] * out["hydro_sensitivity"]
    ).clip(0, HYDRO_MODIFIER_MAX)

    out["original_dynamic_environment_modifier"] = (
        out["original_weather_modifier"] + out["hydro_modifier"]
    ).clip(0, TOTAL_ENV_MODIFIER_MAX)

    out["original_environment_adjusted_risk_score"] = (
        out[base_risk_col] + out["original_dynamic_environment_modifier"]
    ).clip(lower=0)

    out["original_environment_adjusted_risk_band"] = out[
        "original_environment_adjusted_risk_score"
    ].apply(risk_band_from_score)

    return out


def apply_trend_adjustment(df, trend_weather_idx, hydro_idx, base_risk_col):
    out = df.copy()

    trend_weather_rain_component = (
        1.20
        * trend_weather_idx["trend_weather_observed_rain_factor"]
        * out["rain_sensitivity"]
        * out["slip_sensitivity"]
    )

    trend_weather_wetness_component = (
        0.70
        * trend_weather_idx["trend_weather_effective_wetness_factor"]
        * out["slip_sensitivity"]
    )

    trend_weather_wind_component = (
        0.35
        * trend_weather_idx["trend_weather_wind_factor"]
        * out["wind_sensitivity"]
    )

    trend_weather_humidity_component = (
        0.35
        * trend_weather_idx["trend_weather_humidity_factor"]
    )

    trend_weather_temp_component = (
        0.25
        * trend_weather_idx["trend_weather_temp_factor"]
    )

    out["trend_weather_rain_component"] = trend_weather_rain_component
    out["trend_weather_wetness_component"] = trend_weather_wetness_component
    out["trend_weather_wind_component"] = trend_weather_wind_component
    out["trend_weather_humidity_component"] = trend_weather_humidity_component
    out["trend_weather_temp_component"] = trend_weather_temp_component

    out["trend_weather_modifier"] = (
        out["trend_weather_rain_component"]
        + out["trend_weather_wetness_component"]
        + out["trend_weather_wind_component"]
        + out["trend_weather_humidity_component"]
        + out["trend_weather_temp_component"]
    ).clip(0, WEATHER_MODIFIER_MAX)

    out["trend_dynamic_environment_modifier"] = (
        out["trend_weather_modifier"] + out["hydro_modifier"]
    ).clip(0, TOTAL_ENV_MODIFIER_MAX)

    out["trend_environment_adjusted_risk_score"] = (
        out[base_risk_col] + out["trend_dynamic_environment_modifier"]
    ).clip(lower=0)

    out["trend_environment_adjusted_risk_band"] = out[
        "trend_environment_adjusted_risk_score"
    ].apply(risk_band_from_score)

    return out


# =========================================================
# G. Summary
# =========================================================
def band_counts(df, col, prefix):
    counts = df[col].value_counts(dropna=False).to_dict()
    rows = []

    for band in ["low", "moderate", "high", "very_high", "unknown"]:
        rows.append(
            {
                "metric": f"{prefix}_band_count_{band}",
                "value": counts.get(band, 0),
            }
        )

    return rows


def add_metric(rows, metric, value):
    rows.append({"metric": metric, "value": value})


def build_summary(compare_df, base_risk_col, original_weather_idx, trend_weather_idx, hydro_idx):
    rows = []

    add_metric(rows, "base_risk_col", base_risk_col)

    for k, v in original_weather_idx.items():
        add_metric(rows, k, v)

    for k, v in trend_weather_idx.items():
        add_metric(rows, k, v)

    for k, v in hydro_idx.items():
        add_metric(rows, k, v)

    numeric_metrics = [
        base_risk_col,
        "original_weather_modifier",
        "trend_weather_modifier",
        "hydro_modifier",
        "original_dynamic_environment_modifier",
        "trend_dynamic_environment_modifier",
        "original_environment_adjusted_risk_score",
        "trend_environment_adjusted_risk_score",
        "risk_score_delta_trend_minus_original",
        "modifier_delta_trend_minus_original",
    ]

    for col in numeric_metrics:
        if col not in compare_df.columns:
            continue

        s = pd.to_numeric(compare_df[col], errors="coerce")

        add_metric(rows, f"{col}_mean", s.mean())
        add_metric(rows, f"{col}_max", s.max())
        add_metric(rows, f"{col}_min", s.min())

    rows.extend(
        band_counts(
            compare_df,
            "original_environment_adjusted_risk_band",
            "original_adjusted",
        )
    )

    rows.extend(
        band_counts(
            compare_df,
            "trend_environment_adjusted_risk_band",
            "trend_adjusted",
        )
    )

    if "risk_band" in compare_df.columns:
        rows.extend(
            band_counts(
                compare_df,
                "risk_band",
                "raw_original",
            )
        )

    changed = (
        compare_df["original_environment_adjusted_risk_band"]
        != compare_df["trend_environment_adjusted_risk_band"]
    )

    add_metric(rows, "risk_band_changed_count", int(changed.sum()))
    add_metric(rows, "risk_band_changed_ratio", float(changed.mean()))

    return pd.DataFrame(rows)


# =========================================================
# H. Main
# =========================================================
def main():
    ensure_exists(RISK_CSV)
    ensure_exists(SEMANTIC_CSV)
    ensure_exists(WEATHER_SUMMARY_CSV)
    ensure_exists(WATER_SUMMARY_CSV)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    risk_df = normalize_columns(pd.read_csv(RISK_CSV))
    semantic_df = normalize_columns(pd.read_csv(SEMANTIC_CSV))
    weather_summary = normalize_columns(pd.read_csv(WEATHER_SUMMARY_CSV))
    water_summary = normalize_columns(pd.read_csv(WATER_SUMMARY_CSV))

    trend_features = read_optional_csv(WEATHER_TREND_FEATURES_CSV)
    quality_summary = read_optional_csv(WEATHER_DATA_QUALITY_CSV)

    if trend_features.empty:
        print("警告：找不到 ib3b2 trend features，trend 方法會退化為僅使用 weather summary。")

    if quality_summary.empty:
        print("警告：找不到 ib3b2 data quality summary，將無法輸出完整資料品質註記。")

    risk_dist_col = find_distance_col(risk_df)
    base_risk_col = find_base_risk_col(risk_df)

    risk_df = to_numeric_safe(
        risk_df,
        [
            risk_dist_col,
            "risk_score",
            "risk_score_smooth",
            "effort_score",
            "exposure_score",
            "terrain_score",
        ],
    )

    if len(risk_df) != len(semantic_df):
        n = min(len(risk_df), len(semantic_df))
        print(f"警告：risk_df 與 semantic_df 列數不同，將截到 n={n}")
        risk_df = risk_df.iloc[:n].copy()
        semantic_df = semantic_df.iloc[:n].copy()

    merged = risk_df.copy()

    semantic_cols_to_add = [
        "route_semantic_class",
        "surface_class",
        "hazard_flags",
        "hydrology_flags",
        "technical_flags",
        "facility_flags",
        "rest_flags",
        "support_flags",
        "osm_highway",
        "osm_surface",
    ]

    for c in semantic_cols_to_add:
        if c in semantic_df.columns and c not in merged.columns:
            merged[c] = semantic_df[c].values

    if "risk_band" not in merged.columns:
        merged["risk_band"] = merged[base_risk_col].apply(risk_band_from_score)

    original_weather_idx = build_weather_index_original(weather_summary)
    trend_weather_idx = build_weather_index_trend(
        weather_summary=weather_summary,
        trend_features=trend_features,
        quality_summary=quality_summary,
    )
    hydro_idx = build_hydro_index(water_summary)

    enriched = compute_segment_sensitivity(merged)

    compare_df = apply_original_adjustment(
        enriched,
        original_weather_idx=original_weather_idx,
        hydro_idx=hydro_idx,
        base_risk_col=base_risk_col,
    )

    compare_df = apply_trend_adjustment(
        compare_df,
        trend_weather_idx=trend_weather_idx,
        hydro_idx=hydro_idx,
        base_risk_col=base_risk_col,
    )

    compare_df["risk_score_delta_trend_minus_original"] = (
        compare_df["trend_environment_adjusted_risk_score"]
        - compare_df["original_environment_adjusted_risk_score"]
    )

    compare_df["modifier_delta_trend_minus_original"] = (
        compare_df["trend_dynamic_environment_modifier"]
        - compare_df["original_dynamic_environment_modifier"]
    )

    compare_df["risk_band_changed_by_trend"] = (
        compare_df["original_environment_adjusted_risk_band"]
        != compare_df["trend_environment_adjusted_risk_band"]
    )

    for k, v in original_weather_idx.items():
        compare_df[k] = v

    for k, v in trend_weather_idx.items():
        compare_df[k] = v

    for k, v in hydro_idx.items():
        compare_df[k] = v

    summary = build_summary(
        compare_df=compare_df,
        base_risk_col=base_risk_col,
        original_weather_idx=original_weather_idx,
        trend_weather_idx=trend_weather_idx,
        hydro_idx=hydro_idx,
    )

    compare_df.to_csv(OUT_COMPARE_CSV, index=False, encoding="utf-8-sig")
    summary.to_csv(OUT_SUMMARY_CSV, index=False, encoding="utf-8-sig")

    print("完成！")
    print("compare CSV:", OUT_COMPARE_CSV.resolve())
    print("summary CSV:", OUT_SUMMARY_CSV.resolve())

    print("\n=== original weather index ===")
    for k, v in original_weather_idx.items():
        print(f"{k}: {v}")

    print("\n=== trend weather index ===")
    for k, v in trend_weather_idx.items():
        print(f"{k}: {v}")

    print("\n=== hydro index ===")
    for k, v in hydro_idx.items():
        print(f"{k}: {v}")

    print("\n=== comparison summary ===")
    show_metrics = [
        "risk_score_delta_trend_minus_original_mean",
        "risk_score_delta_trend_minus_original_max",
        "modifier_delta_trend_minus_original_mean",
        "modifier_delta_trend_minus_original_max",
        "risk_band_changed_count",
        "risk_band_changed_ratio",
        "original_adjusted_band_count_low",
        "original_adjusted_band_count_moderate",
        "original_adjusted_band_count_high",
        "original_adjusted_band_count_very_high",
        "trend_adjusted_band_count_low",
        "trend_adjusted_band_count_moderate",
        "trend_adjusted_band_count_high",
        "trend_adjusted_band_count_very_high",
    ]

    s2 = summary[summary["metric"].isin(show_metrics)].copy()
    print(s2.to_string(index=False))

    print("\n=== band comparison ===")
    print(
        compare_df[
            [
                "original_environment_adjusted_risk_band",
                "trend_environment_adjusted_risk_band",
                "risk_band_changed_by_trend",
            ]
        ]
        .value_counts(dropna=False)
        .to_string()
    )


if __name__ == "__main__":
    main()