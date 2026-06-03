# -*- coding: utf-8 -*-
from pathlib import Path
import os
import numpy as np
import pandas as pd


# =========================================================
# A. Input / Output
# =========================================================
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent

SCENARIO_NAME = os.environ.get("SCENARIO_NAME", "actual_gpx_9stations")

ENV_BASE_DIR = BASE_DIR / "ib3_environment_output"
ENV_DIR = ENV_BASE_DIR / SCENARIO_NAME

WEATHER_TREND_CSV = ENV_DIR / "qixing_weather_trend_features.csv"
WEATHER_QUALITY_CSV = ENV_DIR / "qixing_weather_data_quality_summary.csv"
TERRAIN_FEATURES_CSV = ENV_DIR / "qixing_route_microclimate_terrain_features.csv"

OUT_INTERACTION_CSV = ENV_DIR / "qixing_weather_terrain_microclimate_interaction.csv"
OUT_SUMMARY_CSV = ENV_DIR / "qixing_weather_terrain_microclimate_interaction_summary.csv"

# =========================================================
# B. Station weighting
# =========================================================
WEATHER_STATION_WEIGHTS = {
    "466930": 0.40,  # 陽明山
    "466910": 0.30,  # 鞍部
    "C0AC40": 0.15,  # 大屯山
    "A0A460": 0.10,  # 文化大學
    "C0AH40": 0.05,  # 平等
}


# =========================================================
# C. Thresholds
# =========================================================
TEMP_HOT_C = 28.0
TEMP_COLD_C = 12.0
TEMP_COOL_C = 18.0

HUMIDITY_HIGH_PCT = 90.0
HUMIDITY_VERY_HIGH_PCT = 95.0
HUMIDITY_LOW_PCT = 60.0

RAIN_LIGHT_MM = 0.1
RAIN_MODERATE_MM = 10.0
RAIN_HEAVY_MM = 50.0
RAIN_EXTREME_MM = 100.0

WIND_BREEZY_MS = 3.0
WIND_WINDY_MS = 6.0
WIND_STRONG_MS = 10.0

VIS_CLEAR_M = 10000
VIS_REDUCED_M = 5000
VIS_POOR_M = 1000

PRESSURE_DROP_RATE_WARN = 0.8

SCORE_MIN = 0.0
SCORE_MAX = 1.0


# =========================================================
# D. Utility
# =========================================================
def ensure_exists(fp: Path):
    if not fp.exists():
        raise FileNotFoundError(f"找不到檔案：{fp.resolve()}")


def normalize_columns(df: pd.DataFrame):
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    return out


def read_csv(fp: Path):
    ensure_exists(fp)
    return normalize_columns(pd.read_csv(fp))


def read_csv_optional(fp: Path):
    if not fp.exists():
        return pd.DataFrame()
    return normalize_columns(pd.read_csv(fp))


def to_numeric_safe(df: pd.DataFrame, cols):
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def clamp(v, lo=SCORE_MIN, hi=SCORE_MAX):
    if pd.isna(v):
        return np.nan
    return max(lo, min(hi, float(v)))


def clamp_series(s, lo=SCORE_MIN, hi=SCORE_MAX):
    return pd.to_numeric(s, errors="coerce").fillna(0.0).clip(lo, hi)


def safe_float(v, default=0.0):
    try:
        if pd.isna(v):
            return default
        return float(v)
    except Exception:
        return default


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


def weighted_mode_by_station(df, value_col, weight_map):
    if df.empty or value_col not in df.columns:
        return ""

    score = {}

    for _, row in df.iterrows():
        station_id = str(row.get("station_id", ""))
        val = row.get(value_col, "")

        if pd.isna(val) or str(val).strip() == "":
            continue

        w = weight_map.get(station_id, 0.0)
        if w <= 0:
            continue

        key = str(val)
        score[key] = score.get(key, 0.0) + w

    if not score:
        return ""

    return max(score.items(), key=lambda kv: kv[1])[0]


def weighted_circular_mean_deg_by_station(df, value_col, valid_count_col, weight_map):
    """
    風向向量加權平均。
    注意：風向通常代表「風從哪裡來」。
    """
    if df.empty or value_col not in df.columns:
        return np.nan

    sin_sum = 0.0
    cos_sum = 0.0
    w_sum = 0.0

    for _, row in df.iterrows():
        station_id = str(row.get("station_id", ""))
        deg = row.get(value_col, np.nan)

        if pd.isna(deg):
            continue

        if valid_count_col in df.columns:
            valid_count = safe_float(row.get(valid_count_col), default=0.0)
            if valid_count <= 0:
                continue

        w = weight_map.get(station_id, 0.0)
        if w <= 0:
            continue

        rad = np.deg2rad(float(deg) % 360.0)
        sin_sum += np.sin(rad) * w
        cos_sum += np.cos(rad) * w
        w_sum += w

    if w_sum <= 0:
        return np.nan

    sin_mean = sin_sum / w_sum
    cos_mean = cos_sum / w_sum

    if np.isclose(sin_mean, 0.0) and np.isclose(cos_mean, 0.0):
        return np.nan

    mean_deg = np.rad2deg(np.arctan2(sin_mean, cos_mean)) % 360.0
    return float(mean_deg)


# =========================================================
# E. Weather context classification
# =========================================================
def classify_thermal_humidity_regime(temp_c, humidity_pct):
    if pd.isna(temp_c) or pd.isna(humidity_pct):
        return "unknown_thermal_humidity"

    temp_c = float(temp_c)
    humidity_pct = float(humidity_pct)

    high_humidity = humidity_pct >= HUMIDITY_HIGH_PCT
    low_humidity = humidity_pct <= HUMIDITY_LOW_PCT

    if temp_c >= TEMP_HOT_C and high_humidity:
        return "hot_humid"
    if temp_c <= TEMP_COLD_C and high_humidity:
        return "cold_humid"
    if temp_c >= TEMP_HOT_C and low_humidity:
        return "hot_dry"
    if temp_c <= TEMP_COLD_C and low_humidity:
        return "cold_dry"

    if temp_c <= TEMP_COOL_C and high_humidity:
        return "cool_humid"
    if high_humidity:
        return "mild_humid"
    if low_humidity:
        return "mild_dry"

    return "mild_normal"


def classify_rainfall_level(rain_mm):
    if pd.isna(rain_mm):
        return "rain_data_unknown"

    rain_mm = float(rain_mm)

    if rain_mm < RAIN_LIGHT_MM:
        return "no_measured_rain"
    if rain_mm < RAIN_MODERATE_MM:
        return "light_rain"
    if rain_mm < RAIN_HEAVY_MM:
        return "moderate_rain"
    if rain_mm < RAIN_EXTREME_MM:
        return "heavy_rain"
    return "extreme_rain"


def classify_wind_level(wind_ms, gust_ms=np.nan):
    vals = []
    if pd.notna(wind_ms):
        vals.append(float(wind_ms))
    if pd.notna(gust_ms):
        vals.append(float(gust_ms))

    if not vals:
        return "wind_data_unknown"

    v = max(vals)

    if v < WIND_BREEZY_MS:
        return "calm_or_light_wind"
    if v < WIND_WINDY_MS:
        return "breezy"
    if v < WIND_STRONG_MS:
        return "windy"
    return "strong_wind"


def classify_visibility_level(visibility_min_m):
    if pd.isna(visibility_min_m):
        return "visibility_unknown"

    v = float(visibility_min_m)

    if v >= VIS_CLEAR_M:
        return "clear_visibility"
    if v >= VIS_REDUCED_M:
        return "reduced_visibility"
    if v >= VIS_POOR_M:
        return "poor_visibility"
    return "very_poor_visibility"


def classify_pressure_trend(pressure_drop_rate):
    if pd.isna(pressure_drop_rate):
        return "pressure_trend_unknown"

    r = float(pressure_drop_rate)

    if r >= PRESSURE_DROP_RATE_WARN:
        return "pressure_falling_fast"

    if r > 0:
        return "pressure_slightly_falling"

    return "pressure_stable_or_rising"


def factor_thermal_stress(temp_c, humidity_pct, thermal_regime):
    temp_c = safe_float(temp_c, default=np.nan)
    humidity_pct = safe_float(humidity_pct, default=np.nan)

    if pd.isna(temp_c) or pd.isna(humidity_pct):
        return 0.0

    if thermal_regime == "hot_humid":
        return 1.0

    if thermal_regime == "hot_dry":
        return 0.75

    if thermal_regime == "cold_humid":
        return 0.70

    if thermal_regime == "cold_dry":
        return 0.45

    if thermal_regime == "cool_humid":
        return 0.45

    if thermal_regime == "mild_humid":
        return 0.30

    return 0.10


def factor_rainfall(rain_level):
    mapping = {
        "no_measured_rain": 0.00,
        "light_rain": 0.25,
        "moderate_rain": 0.55,
        "heavy_rain": 0.80,
        "extreme_rain": 1.00,
        "rain_data_unknown": 0.10,
    }
    return mapping.get(str(rain_level), 0.10)


def factor_wetness_condition(rain_data_status, weather_trend_hint):
    s = f"{rain_data_status}|{weather_trend_hint}"

    if "observed_rain" in s or "rain_observed" in s:
        return 1.00
    if "rain_lag_suspected" in s:
        return 0.75
    if "prior_rain_wet_trail" in s or "wet_trail_from_prior_rain" in s:
        return 0.60
    if "suspected_wet_high_humidity" in s or "possible_mist_or_drizzle" in s:
        return 0.55
    if "humid_no_measured_rain" in s:
        return 0.35
    if "rain_data_uncertain_coarse_update" in s or "coarse_update_frequency" in s:
        return 0.20

    return 0.0


def factor_wind(wind_level):
    mapping = {
        "calm_or_light_wind": 0.05,
        "breezy": 0.25,
        "windy": 0.60,
        "strong_wind": 1.00,
        "wind_data_unknown": 0.10,
    }
    return mapping.get(str(wind_level), 0.10)


def factor_visibility(visibility_level):
    mapping = {
        "clear_visibility": 0.00,
        "reduced_visibility": 0.30,
        "poor_visibility": 0.65,
        "very_poor_visibility": 1.00,
        "visibility_unknown": 0.10,
    }
    return mapping.get(str(visibility_level), 0.10)


def factor_weather_deterioration(pressure_trend_condition, weather_trend_hint):
    if weather_trend_hint == "weather_deterioration_suspected":
        return 0.80

    if pressure_trend_condition == "pressure_falling_fast":
        return 0.60

    if pressure_trend_condition == "pressure_slightly_falling":
        return 0.20

    return 0.0


def dominant_weather_context(weather_df, quality_df):
    """
    將多測站趨勢整理成一組全線 weather context。
    後續 ib3f 先做全線 weather × 分段 terrain。
    第二階段才做空間化 weather interpolation。
    """
    w = weather_df.copy()

    numeric_cols = [
        "rain_sum_mm_activity",
        "rain_sum_mm_pre_wetness",
        "rain_sum_mm_post_lag",
        "humidity_mean_pct_activity",
        "temperature_mean_c_activity",
        "wind_speed_max_ms_activity",
        "wind_gust_max_ms_activity",
        "visibility_min_m_activity",
        "pressure_drop_rate_hpa_per_hr",
        "wind_direction_vector_mean_deg_activity",
        "wind_direction_valid_count_activity",
    ]
    w = to_numeric_safe(w, numeric_cols)

    temp_mean = weighted_mean_by_station(w, "temperature_mean_c_activity", WEATHER_STATION_WEIGHTS)
    humidity_mean = weighted_mean_by_station(w, "humidity_mean_pct_activity", WEATHER_STATION_WEIGHTS)

    rain_sum = weighted_mean_by_station(w, "rain_sum_mm_activity", WEATHER_STATION_WEIGHTS)
    pre_rain_sum = weighted_mean_by_station(w, "rain_sum_mm_pre_wetness", WEATHER_STATION_WEIGHTS)
    post_rain_sum = weighted_mean_by_station(w, "rain_sum_mm_post_lag", WEATHER_STATION_WEIGHTS)

    wind_max = weighted_max_by_station(w, "wind_speed_max_ms_activity", WEATHER_STATION_WEIGHTS)
    gust_max = weighted_max_by_station(w, "wind_gust_max_ms_activity", WEATHER_STATION_WEIGHTS)

    visibility_min = weighted_max_by_station(w, "visibility_min_m_activity", WEATHER_STATION_WEIGHTS)
    pressure_drop_rate = weighted_max_by_station(w, "pressure_drop_rate_hpa_per_hr", WEATHER_STATION_WEIGHTS)

    wind_direction_mean = weighted_circular_mean_deg_by_station(
        w,
        "wind_direction_vector_mean_deg_activity",
        "wind_direction_valid_count_activity",
        WEATHER_STATION_WEIGHTS,
    )

    rain_data_status = weighted_mode_by_station(w, "rain_data_status", WEATHER_STATION_WEIGHTS)
    weather_trend_hint = weighted_mode_by_station(w, "weather_trend_hint", WEATHER_STATION_WEIGHTS)
    wind_direction_data_status = weighted_mode_by_station(w, "wind_direction_data_status", WEATHER_STATION_WEIGHTS)

    if quality_df.empty:
        weather_data_quality = "unknown"
    else:
        weather_data_quality = str(quality_df.iloc[0].get("weather_data_quality", "unknown"))

    thermal_humidity_regime = classify_thermal_humidity_regime(temp_mean, humidity_mean)
    rainfall_level = classify_rainfall_level(rain_sum)
    wind_level = classify_wind_level(wind_max, gust_max)
    visibility_level = classify_visibility_level(visibility_min)
    pressure_trend_condition = classify_pressure_trend(pressure_drop_rate)

    thermal_stress_base = factor_thermal_stress(temp_mean, humidity_mean, thermal_humidity_regime)
    rainfall_base = factor_rainfall(rainfall_level)
    wetness_base = max(
        rainfall_base,
        factor_wetness_condition(rain_data_status, weather_trend_hint),
    )
    wind_base = factor_wind(wind_level)
    visibility_base = factor_visibility(visibility_level)
    weather_deterioration_base = factor_weather_deterioration(
        pressure_trend_condition,
        weather_trend_hint,
    )

    return {
        "weather_data_quality": weather_data_quality,

        "temperature_mean_c_activity_weighted": temp_mean,
        "humidity_mean_pct_activity_weighted": humidity_mean,

        "rain_sum_mm_activity_weighted": rain_sum,
        "rain_sum_mm_pre_wetness_weighted": pre_rain_sum,
        "rain_sum_mm_post_lag_weighted": post_rain_sum,

        "wind_speed_max_ms_activity_weighted": wind_max,
        "wind_gust_max_ms_activity_weighted": gust_max,
        "wind_direction_vector_mean_deg_weighted": wind_direction_mean,
        "wind_direction_data_status_weighted": wind_direction_data_status,

        "visibility_min_m_activity_weighted": visibility_min,
        "pressure_drop_rate_hpa_per_hr_weighted": pressure_drop_rate,

        "rain_data_status_weighted": rain_data_status,
        "weather_trend_hint_weighted": weather_trend_hint,

        "thermal_humidity_regime": thermal_humidity_regime,
        "rainfall_level": rainfall_level,
        "wind_level": wind_level,
        "visibility_level": visibility_level,
        "pressure_trend_condition": pressure_trend_condition,

        "thermal_stress_base": thermal_stress_base,
        "rainfall_base": rainfall_base,
        "wetness_base": wetness_base,
        "wind_base": wind_base,
        "visibility_base": visibility_base,
        "weather_deterioration_base": weather_deterioration_base,
    }


# =========================================================
# F. Terrain-weather interaction
# =========================================================
def classify_interaction(row):
    thermal = row.get("thermal_humidity_regime", "")
    rain = row.get("rainfall_level", "")
    wind = row.get("wind_level", "")
    visibility = row.get("visibility_level", "")
    exposure = row.get("route_exposure_class", "")
    moisture = row.get("terrain_moisture_retention_class", "")
    slip = row.get("surface_wet_slip_class", "")
    altitude = row.get("altitude_regime", "")

    tags = []

    if rain in ["heavy_rain", "extreme_rain"]:
        tags.append("rainy")
    elif rain in ["light_rain", "moderate_rain"]:
        tags.append("wet_weather")

    if thermal in ["cold_humid", "cool_humid"]:
        tags.append("cold_humid")
    elif thermal == "hot_humid":
        tags.append("hot_humid")
    elif thermal == "hot_dry":
        tags.append("hot_dry")

    if wind in ["windy", "strong_wind"]:
        tags.append("windy")

    if visibility in ["poor_visibility", "very_poor_visibility"]:
        tags.append("low_visibility")

    if exposure in [
        "ridge_or_open_exposed",
        "bare_rock_exposed",
        "scree_exposed",
        "unstable_exposed",
        "cliff_exposed",
    ]:
        tags.append("exposed_terrain")

    if moisture in [
        "near_water_or_drainage",
        "wetland_or_saturated",
        "shaded_retains_moisture",
    ]:
        tags.append("moisture_retaining")

    if slip in [
        "steps_slip_sensitive",
        "rock_slip_sensitive",
        "loose_surface_slip_sensitive",
    ]:
        tags.append("slip_sensitive")

    if altitude in [
        "mid_altitude",
        "upper_mid_altitude",
        "high_altitude",
        "very_high_altitude",
    ]:
        tags.append("altitude_amplified")

    if not tags:
        return "general_weather_terrain"

    return "|".join(tags)


def apply_interaction(terrain_df, weather_ctx):
    out = terrain_df.copy()

    # attach weather context
    for k, v in weather_ctx.items():
        out[k] = v

    # terrain columns with safe defaults
    terrain_micro = pd.to_numeric(
        out.get("terrain_microclimate_factor", 0.0),
        errors="coerce",
    ).fillna(0.0).clip(0, 1)

    altitude_amp = pd.to_numeric(
        out.get("altitude_thermal_amplifier", 0.0),
        errors="coerce",
    ).fillna(0.0).clip(0, 1)

    slope_load = pd.to_numeric(
        out.get("slope_load_factor", 0.0),
        errors="coerce",
    ).fillna(0.0).clip(0, 1)

    wet_slip = pd.to_numeric(
        out.get("surface_wet_slip_sensitivity", 0.0),
        errors="coerce",
    ).fillna(0.0).clip(0, 1)

    wind_exposure = pd.to_numeric(
        out.get("wind_exposure_factor_terrain", 0.0),
        errors="coerce",
    ).fillna(0.0).clip(0, 1)

    moisture_retention = pd.to_numeric(
        out.get("valley_humidity_retention_factor", 0.0),
        errors="coerce",
    ).fillna(0.0).clip(0, 1)

    support_reduction = pd.to_numeric(
        out.get("support_reduction_factor", 0.0),
        errors="coerce",
    ).fillna(0.0).clip(0, 1)

    # weather bases
    thermal_base = safe_float(weather_ctx.get("thermal_stress_base"), 0.0)
    wetness_base = safe_float(weather_ctx.get("wetness_base"), 0.0)
    wind_base = safe_float(weather_ctx.get("wind_base"), 0.0)
    visibility_base = safe_float(weather_ctx.get("visibility_base"), 0.0)
    deterioration_base = safe_float(weather_ctx.get("weather_deterioration_base"), 0.0)

    # interaction factors
    out["thermal_stress_factor"] = clamp_series(
        thermal_base * (0.45 + 0.55 * altitude_amp + 0.25 * slope_load),
        0,
        1,
    )

    out["wetness_slip_factor"] = clamp_series(
        wetness_base * (0.35 + 0.65 * wet_slip + 0.25 * moisture_retention),
        0,
        1,
    )

    out["wind_exposure_factor"] = clamp_series(
        wind_base * (0.30 + 0.70 * wind_exposure + 0.25 * altitude_amp),
        0,
        1,
    )

    out["visibility_navigation_factor"] = clamp_series(
        visibility_base * (0.50 + 0.30 * terrain_micro + 0.20 * wind_exposure),
        0,
        1,
    )

    out["weather_deterioration_factor"] = clamp_series(
        deterioration_base * (0.50 + 0.25 * altitude_amp + 0.25 * wind_exposure),
        0,
        1,
    )

    # combined microclimate-weather factor
    combined_raw = (
        0.22 * out["thermal_stress_factor"]
        + 0.30 * out["wetness_slip_factor"]
        + 0.22 * out["wind_exposure_factor"]
        + 0.14 * out["visibility_navigation_factor"]
        + 0.12 * out["weather_deterioration_factor"]
        + 0.20 * terrain_micro
        - 0.10 * support_reduction
    )

    out["combined_microclimate_weather_factor"] = clamp_series(combined_raw, 0, 1)

    out["weather_terrain_interaction_class"] = out.apply(
        classify_interaction,
        axis=1,
    )

    return out


# =========================================================
# G. Summary
# =========================================================
def summarize_interaction(df, weather_ctx):
    rows = []

    def add_metric(metric, value):
        rows.append(
            {
                "metric": metric,
                "class": "",
                "value": value,
                "count": "",
                "ratio": "",
            }
        )

    for k, v in weather_ctx.items():
        add_metric(k, v)

    def add_counts(col):
        if col not in df.columns:
            return

        counts = df[col].value_counts(dropna=False)
        total = len(df)

        for k, v in counts.items():
            rows.append(
                {
                    "metric": f"{col}_count",
                    "class": k,
                    "value": "",
                    "count": int(v),
                    "ratio": float(v / total) if total > 0 else np.nan,
                }
            )

    for col in [
        "thermal_humidity_regime",
        "rainfall_level",
        "wind_level",
        "visibility_level",
        "pressure_trend_condition",
        "weather_terrain_interaction_class",
    ]:
        add_counts(col)

    for col in [
        "thermal_stress_factor",
        "wetness_slip_factor",
        "wind_exposure_factor",
        "visibility_navigation_factor",
        "weather_deterioration_factor",
        "terrain_microclimate_factor",
        "combined_microclimate_weather_factor",
    ]:
        if col not in df.columns:
            continue

        s = pd.to_numeric(df[col], errors="coerce")
        add_metric(f"{col}_mean", s.mean())
        add_metric(f"{col}_min", s.min())
        add_metric(f"{col}_max", s.max())
        add_metric(f"{col}_p75", s.quantile(0.75))

    return pd.DataFrame(rows)


# =========================================================
# H. Main
# =========================================================
def main():
    ensure_exists(WEATHER_TREND_CSV)
    ensure_exists(TERRAIN_FEATURES_CSV)

    weather_df = read_csv(WEATHER_TREND_CSV)
    quality_df = read_csv_optional(WEATHER_QUALITY_CSV)
    terrain_df = read_csv(TERRAIN_FEATURES_CSV)

    if weather_df.empty:
        raise ValueError(f"weather trend CSV 為空：{WEATHER_TREND_CSV}")

    if terrain_df.empty:
        raise ValueError(f"terrain features CSV 為空：{TERRAIN_FEATURES_CSV}")

    weather_ctx = dominant_weather_context(weather_df, quality_df)

    out = apply_interaction(terrain_df, weather_ctx)
    summary = summarize_interaction(out, weather_ctx)

    out.to_csv(OUT_INTERACTION_CSV, index=False, encoding="utf-8-sig")
    summary.to_csv(OUT_SUMMARY_CSV, index=False, encoding="utf-8-sig")

    print("完成！")
    print("scenario:", SCENARIO_NAME)
    print("interaction CSV:", OUT_INTERACTION_CSV.resolve())
    print("summary CSV:", OUT_SUMMARY_CSV.resolve())

    print("\n=== weather context ===")
    for k, v in weather_ctx.items():
        print(f"{k}: {v}")

    print("\n=== interaction class counts ===")
    if "weather_terrain_interaction_class" in out.columns:
        print(out["weather_terrain_interaction_class"].value_counts(dropna=False).to_string())

    print("\n=== factor summary ===")
    for col in [
        "thermal_stress_factor",
        "wetness_slip_factor",
        "wind_exposure_factor",
        "visibility_navigation_factor",
        "weather_deterioration_factor",
        "terrain_microclimate_factor",
        "combined_microclimate_weather_factor",
    ]:
        if col in out.columns:
            s = pd.to_numeric(out[col], errors="coerce")
            print(
                f"{col}: "
                f"mean={s.mean():.3f}, "
                f"min={s.min():.3f}, "
                f"p75={s.quantile(0.75):.3f}, "
                f"max={s.max():.3f}"
            )

    print("\n=== top high interaction segments ===")
    show_cols = [
        "dist_m_microclimate",
        "ele_m_microclimate",
        "slope_pct_microclimate",
        "altitude_regime",
        "slope_regime",
        "route_exposure_class",
        "terrain_moisture_retention_class",
        "surface_wet_slip_class",
        "weather_terrain_interaction_class",
        "terrain_microclimate_factor",
        "thermal_stress_factor",
        "wetness_slip_factor",
        "wind_exposure_factor",
        "visibility_navigation_factor",
        "combined_microclimate_weather_factor",
    ]
    show_cols = [c for c in show_cols if c in out.columns]

    top = out.sort_values(
        "combined_microclimate_weather_factor",
        ascending=False,
    ).head(12)

    print(top[show_cols].to_string(index=False))


if __name__ == "__main__":
    main()