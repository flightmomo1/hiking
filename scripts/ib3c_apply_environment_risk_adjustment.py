# -*- coding: utf-8 -*-
from pathlib import Path
import os
import numpy as np
import pandas as pd


# =========================================================
# A. Input / Output
# =========================================================
RISK_CSV = Path("ib2_v2_route_risk_output/qixing_route_risk_v2.csv")

SEMANTIC_CSV = Path(
    "ib1c_route_profile_semantic_output/qixing_route_profile_semantic_enriched.csv"
)

SCENARIO_NAME = os.environ.get("SCENARIO_NAME", "actual_gpx_9stations")

ENV_BASE_DIR = Path("ib3_environment_output")
ENV_DIR = ENV_BASE_DIR / SCENARIO_NAME

WEATHER_SUMMARY_CSV = ENV_DIR / "qixing_weather_summary_by_station.csv"

FUSED_WEATHER_SUMMARY_CSV = ENV_DIR / "qixing_route_weather_fused_summary.csv"

WATER_SUMMARY_CSV = ENV_DIR / "qixing_water_summary_by_station.csv"

OUT_DIR = ENV_DIR
OUT_ADJUSTED_CSV = OUT_DIR / "qixing_environment_adjusted_risk.csv"
OUT_SUMMARY_CSV = OUT_DIR / "qixing_environment_adjusted_risk_summary.csv"


# =========================================================
# B. Config
# =========================================================
# 主測站權重：第一版先用距離最近且山區代表性高的測站
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

# 避免雨量欄位定義造成風險爆表，第一版先做截斷
RAIN_SUM_CAP_MM = 200.0
WIND_MAX_CAP_MS = 15.0
HUMIDITY_CAP_PCT = 100.0
WATER_CHANGE_CAP_M = 0.5
WATER_RANGE_CAP_M = 1.0

# 動態修正上限，避免蓋過原始路線風險
WEATHER_MODIFIER_MAX = 2.0
HYDRO_MODIFIER_MAX = 1.2
TOTAL_ENV_MODIFIER_MAX = 2.8

# 風險分級門檻，可依 ib2 原本規則再調整
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


# =========================================================
# D. Environment summary
# =========================================================

def build_weather_index_from_fused_route_weather(fused_weather: pd.DataFrame):
    """
    使用 ib3b4 融合後的 GPX 路線位置天候估計。
    這是新版優先邏輯：
    - 溫度、濕度、氣壓、風速、雨量來自 route-level fused weather
    - 不再直接對測站做固定權重平均
    """
    if fused_weather.empty:
        return None

    row = fused_weather.iloc[0]

    temp_mean = pd.to_numeric(
        row.get("route_temperature_est_c", np.nan),
        errors="coerce",
    )

    humidity = pd.to_numeric(
        row.get("route_humidity_est_pct", np.nan),
        errors="coerce",
    )

    pressure = pd.to_numeric(
        row.get("route_pressure_est_hpa", np.nan),
        errors="coerce",
    )

    wind_mean = pd.to_numeric(
        row.get("route_wind_speed_mean_est_ms", np.nan),
        errors="coerce",
    )

    wind_max = pd.to_numeric(
        row.get("route_wind_speed_max_station_ms", np.nan),
        errors="coerce",
    )

    rain_sum = pd.to_numeric(
        row.get("route_precipitation_weighted_sum_mm", np.nan),
        errors="coerce",
    )

    rain_max_station = pd.to_numeric(
        row.get("route_precipitation_max_station_mm", np.nan),
        errors="coerce",
    )

    visibility_min = pd.to_numeric(
        row.get("route_visibility_min_station_m", np.nan),
        errors="coerce",
    )

    station_count = pd.to_numeric(
        row.get("station_count", np.nan),
        errors="coerce",
    )

    max_station_weight = pd.to_numeric(
        row.get("max_station_weight", np.nan),
        errors="coerce",
    )

    if pd.isna(rain_sum):
        rain_sum = 0.0
    if pd.isna(rain_max_station):
        rain_max_station = rain_sum
    if pd.isna(wind_max):
        wind_max = 0.0
    if pd.isna(wind_mean):
        wind_mean = 0.0

    rain_sum_capped = min(max(float(rain_sum), 0.0), RAIN_SUM_CAP_MM)
    wind_max_capped = min(max(float(wind_max), 0.0), WIND_MAX_CAP_MS)

    # 雨量：weighted sum 為主，但保留 max station 作為局部強降雨證據
    rain_factor = rain_sum_capped / RAIN_SUM_CAP_MM

    if pd.isna(humidity):
        humidity_factor = 0.0
    else:
        humidity_capped = min(max(float(humidity), 0.0), HUMIDITY_CAP_PCT)
        humidity_factor = max(0.0, (humidity_capped - 80.0) / 20.0)

    wind_factor = wind_max_capped / WIND_MAX_CAP_MS

    if pd.isna(temp_mean):
        temp_factor = 0.0
    elif temp_mean < 15.0:
        temp_factor = min((15.0 - float(temp_mean)) / 10.0, 1.0)
    elif temp_mean > 30.0:
        temp_factor = min((float(temp_mean) - 30.0) / 10.0, 1.0)
    else:
        temp_factor = 0.0

    weather_modifier_base = (
        1.20 * rain_factor
        + 0.35 * humidity_factor
        + 0.35 * wind_factor
        + 0.25 * temp_factor
    )
    weather_modifier_base = min(weather_modifier_base, WEATHER_MODIFIER_MAX)

    return {
        "weather_available": 1,
        "weather_fusion_used": 1,
        "weather_fusion_method": row.get("fusion_method", ""),
        "weather_station_count": station_count,
        "weather_max_station_weight": max_station_weight,

        "weather_rain_sum_mm": rain_sum,
        "weather_rain_max_station_mm": rain_max_station,
        "weather_rain_factor": rain_factor,

        "weather_humidity_pct": humidity,
        "weather_humidity_factor": humidity_factor,

        "weather_wind_mean_ms": wind_mean,
        "weather_wind_max_ms": wind_max,
        "weather_wind_factor": wind_factor,

        "weather_temp_mean_c": temp_mean,
        "weather_temp_factor": temp_factor,

        "weather_pressure_hpa": pressure,
        "weather_visibility_min_m": visibility_min,

        "weather_modifier_base": weather_modifier_base,
    }



def build_weather_index(weather_summary: pd.DataFrame):
    """
    把多測站摘要轉成一組路線級天氣指標。
    第一版先以整條路線同一組天氣條件修正。
    """
    if weather_summary.empty:
        return {
            "weather_available": 0,
            "weather_fusion_used": 0,
            "weather_fusion_method": "none",
            "weather_station_count": 0,
            "weather_max_station_weight": np.nan,

            "weather_rain_sum_mm": 0.0,
            "weather_rain_max_station_mm": 0.0,
            "weather_rain_factor": 0.0,

            "weather_humidity_pct": np.nan,
            "weather_humidity_factor": 0.0,

            "weather_wind_mean_ms": 0.0,
            "weather_wind_max_ms": 0.0,
            "weather_wind_factor": 0.0,

            "weather_temp_mean_c": np.nan,
            "weather_temp_factor": 0.0,

            "weather_pressure_hpa": np.nan,
            "weather_visibility_min_m": np.nan,

            "weather_modifier_base": 0.0,
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

    rain_sum = weighted_mean_by_station(
        w,
        "precipitation_sum_mm",
        WEATHER_STATION_WEIGHTS,
    )
    humidity = weighted_mean_by_station(
        w,
        "humidity_mean_pct",
        WEATHER_STATION_WEIGHTS,
    )
    temp_mean = weighted_mean_by_station(
        w,
        "temperature_mean_c",
        WEATHER_STATION_WEIGHTS,
    )
    wind_max = weighted_max_by_station(
        w,
        "wind_speed_max_ms",
        WEATHER_STATION_WEIGHTS,
    )

    if pd.isna(rain_sum):
        rain_sum = 0.0
    if pd.isna(wind_max):
        wind_max = 0.0

    rain_sum_capped = min(max(rain_sum, 0.0), RAIN_SUM_CAP_MM)
    wind_max_capped = min(max(wind_max, 0.0), WIND_MAX_CAP_MS)

    # 雨量：0–200 mm 映射到 0–1
    rain_factor = rain_sum_capped / RAIN_SUM_CAP_MM

    # 濕度：80% 以上開始加權，100% 到 1
    if pd.isna(humidity):
        humidity_factor = 0.0
    else:
        humidity_capped = min(max(humidity, 0.0), HUMIDITY_CAP_PCT)
        humidity_factor = max(0.0, (humidity_capped - 80.0) / 20.0)

    # 風速：0–15 m/s 映射到 0–1
    wind_factor = wind_max_capped / WIND_MAX_CAP_MS

    # 溫度：低於 15°C 或高於 30°C 提高負荷
    if pd.isna(temp_mean):
        temp_factor = 0.0
    elif temp_mean < 15.0:
        temp_factor = min((15.0 - temp_mean) / 10.0, 1.0)
    elif temp_mean > 30.0:
        temp_factor = min((temp_mean - 30.0) / 10.0, 1.0)
    else:
        temp_factor = 0.0

    # 基礎天氣修正值，最多 2 分
    weather_modifier_base = (
        1.20 * rain_factor
        + 0.35 * humidity_factor
        + 0.35 * wind_factor
        + 0.25 * temp_factor
    )
    weather_modifier_base = min(weather_modifier_base, WEATHER_MODIFIER_MAX)

    return {
        "weather_available": 1,
        "weather_fusion_used": 0,
        "weather_fusion_method": "station_weighted_fallback",
        "weather_station_count": len(w),
        "weather_max_station_weight": np.nan,
        "weather_rain_sum_mm": rain_sum,
        "weather_rain_factor": rain_factor,
        "weather_humidity_pct": humidity,
        "weather_humidity_factor": humidity_factor,
        "weather_wind_max_ms": wind_max,
        "weather_wind_factor": wind_factor,
        "weather_temp_mean_c": temp_mean,
        "weather_temp_factor": temp_factor,
        "weather_modifier_base": weather_modifier_base,
        "weather_pressure_hpa": np.nan,
        "weather_visibility_min_m": weighted_max_by_station(
            w,
            "visibility_min_m",
            WEATHER_STATION_WEIGHTS,
        ),
    }


def build_hydro_index(water_summary: pd.DataFrame):
    """
    把多水位站摘要轉成一組區域水文指標。
    第一版只當作水系附近路段的修正參考。
    """
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

    water_change = weighted_mean_by_station(
        h,
        "water_level_change_m",
        WATER_STATION_WEIGHTS,
    )
    water_range = weighted_mean_by_station(
        h,
        "water_level_range_m",
        WATER_STATION_WEIGHTS,
    )

    if pd.isna(water_change):
        water_change = 0.0
    if pd.isna(water_range):
        water_range = 0.0

    # 只把上升水位視為增加風險，下降不增加
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
def contains_any(series_value, keywords):
    if pd.isna(series_value):
        return False
    s = str(series_value).lower()
    return any(k.lower() in s for k in keywords)


def compute_segment_sensitivity(df: pd.DataFrame):
    """
    根據 ib1c 的語意欄位，決定天氣/水文對各路段的敏感度。
    """
    out = df.copy()

    # 預設敏感度
    out["rain_sensitivity"] = 1.00
    out["wind_sensitivity"] = 1.00
    out["hydro_sensitivity"] = 0.15
    out["slip_sensitivity"] = 1.00

    # 若有鋪石、階梯、石面，雨天濕滑加權
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

    # cliff / scree / bare rock：風雨暴露加權
    if "hazard_flags" in out.columns:
        hazard_mask = out["hazard_flags"].apply(
            lambda v: contains_any(v, ["cliff", "scree", "bare_rock", "landslide"])
        )
        out.loc[hazard_mask, "rain_sensitivity"] += 0.25
        out.loc[hazard_mask, "wind_sensitivity"] += 0.35

    # waterway / wetland / water_area：水文加權
    if "hydrology_flags" in out.columns:
        hydro_mask = out["hydrology_flags"].apply(
            lambda v: contains_any(v, ["waterway", "wetland", "water_area"])
        )
        out.loc[hydro_mask, "hydro_sensitivity"] += 0.85
        out.loc[hydro_mask, "rain_sensitivity"] += 0.15

    # 欄位值合理截斷
    out["rain_sensitivity"] = out["rain_sensitivity"].clip(0.5, 1.8)
    out["wind_sensitivity"] = out["wind_sensitivity"].clip(0.5, 1.8)
    out["hydro_sensitivity"] = out["hydro_sensitivity"].clip(0.0, 1.5)
    out["slip_sensitivity"] = out["slip_sensitivity"].clip(0.5, 1.8)

    return out


def apply_environment_adjustment(df, weather_idx, hydro_idx, base_risk_col):
    out = df.copy()

    # weather components
    weather_rain_component = (
        1.20
        * weather_idx["weather_rain_factor"]
        * out["rain_sensitivity"]
        * out["slip_sensitivity"]
    )

    weather_wind_component = (
        0.35
        * weather_idx["weather_wind_factor"]
        * out["wind_sensitivity"]
    )

    weather_humidity_component = (
        0.35
        * weather_idx["weather_humidity_factor"]
    )

    weather_temp_component = (
        0.25
        * weather_idx["weather_temp_factor"]
    )

    out["weather_rain_component"] = weather_rain_component
    out["weather_wind_component"] = weather_wind_component
    out["weather_humidity_component"] = weather_humidity_component
    out["weather_temp_component"] = weather_temp_component

    out["weather_modifier"] = (
        out["weather_rain_component"]
        + out["weather_wind_component"]
        + out["weather_humidity_component"]
        + out["weather_temp_component"]
    ).clip(0, WEATHER_MODIFIER_MAX)

    # hydro only activated mainly on hydrology-related segments
    out["hydro_modifier"] = (
        hydro_idx["hydro_modifier_base"]
        * out["hydro_sensitivity"]
    ).clip(0, HYDRO_MODIFIER_MAX)

    out["dynamic_environment_modifier"] = (
        out["weather_modifier"]
        + out["hydro_modifier"]
    ).clip(0, TOTAL_ENV_MODIFIER_MAX)

    out["environment_adjusted_risk_score"] = (
        out[base_risk_col]
        + out["dynamic_environment_modifier"]
    )

    out["environment_adjusted_risk_score"] = out[
        "environment_adjusted_risk_score"
    ].clip(lower=0)

    out["environment_delta_score"] = (
        out["environment_adjusted_risk_score"]
        - out[base_risk_col]
    )

    # 用同一套分級門檻重新計算原始風險 band，避免舊 risk_band 與 adjusted band 門檻不一致
    out["risk_band_recomputed"] = out[base_risk_col].apply(risk_band_from_score)

    out["environment_adjusted_risk_band"] = out[
        "environment_adjusted_risk_score"
    ].apply(risk_band_from_score)

    for k, v in weather_idx.items():
        out[k] = v

    for k, v in hydro_idx.items():
        out[k] = v

    return out


# =========================================================
# F. Main
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

    if FUSED_WEATHER_SUMMARY_CSV.exists():
        fused_weather_summary = normalize_columns(
            pd.read_csv(FUSED_WEATHER_SUMMARY_CSV)
        )
    else:
        fused_weather_summary = pd.DataFrame()

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

    # semantic 欄位對齊
    if len(risk_df) != len(semantic_df):
        n = min(len(risk_df), len(semantic_df))
        print(f"警告：risk_df 與 semantic_df 列數不同，將截到 n={n}")
        risk_df = risk_df.iloc[:n].copy()
        semantic_df = semantic_df.iloc[:n].copy()

    merged = risk_df.copy()

    # 補上語意欄位，避免覆蓋既有風險欄位
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

    weather_idx = build_weather_index_from_fused_route_weather(
        fused_weather_summary
    )

    if weather_idx is None:
        print("警告：找不到 fused route weather，改用 weather_summary_by_station fallback。")
        weather_idx = build_weather_index(weather_summary)

    hydro_idx = build_hydro_index(water_summary)

    enriched = compute_segment_sensitivity(merged)
    adjusted = apply_environment_adjustment(
        enriched,
        weather_idx,
        hydro_idx,
        base_risk_col=base_risk_col,
    )

    adjusted.to_csv(OUT_ADJUSTED_CSV, index=False, encoding="utf-8-sig")

    # summary
    summary_rows = []

    summary_rows.append(
        {
            "metric": "base_risk_col",
            "value": base_risk_col,
        }
    )

    for key, value in weather_idx.items():
        summary_rows.append({"metric": key, "value": value})

    for key, value in hydro_idx.items():
        summary_rows.append({"metric": key, "value": value})

    summary_rows.extend(
        [
            {
                "metric": "base_risk_mean",
                "value": adjusted[base_risk_col].mean(),
            },
            {
                "metric": "base_risk_max",
                "value": adjusted[base_risk_col].max(),
            },
            {
                "metric": "weather_modifier_mean",
                "value": adjusted["weather_modifier"].mean(),
            },
            {
                "metric": "weather_modifier_max",
                "value": adjusted["weather_modifier"].max(),
            },
            {
                "metric": "hydro_modifier_mean",
                "value": adjusted["hydro_modifier"].mean(),
            },
            {
                "metric": "hydro_modifier_max",
                "value": adjusted["hydro_modifier"].max(),
            },
            {
                "metric": "dynamic_environment_modifier_mean",
                "value": adjusted["dynamic_environment_modifier"].mean(),
            },
            {
                "metric": "dynamic_environment_modifier_max",
                "value": adjusted["dynamic_environment_modifier"].max(),
            },
            {
                "metric": "environment_delta_score_mean",
                "value": adjusted["environment_delta_score"].mean(),
            },
            {
                "metric": "environment_delta_score_max",
                "value": adjusted["environment_delta_score"].max(),
            },
            {
                "metric": "environment_adjusted_risk_mean",
                "value": adjusted["environment_adjusted_risk_score"].mean(),
            },
            {
                "metric": "environment_adjusted_risk_max",
                "value": adjusted["environment_adjusted_risk_score"].max(),
            },
        ]
    )

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(OUT_SUMMARY_CSV, index=False, encoding="utf-8-sig")

    print("完成！")
    print("scenario:", SCENARIO_NAME)
    print("adjusted CSV:", OUT_ADJUSTED_CSV.resolve())
    print("summary CSV:", OUT_SUMMARY_CSV.resolve())

    print("\n=== environment indices ===")
    for key, value in weather_idx.items():
        print(f"{key}: {value}")
    for key, value in hydro_idx.items():
        print(f"{key}: {value}")

    print("\n=== modifier summary ===")
    cols = [
        base_risk_col,
        "weather_modifier",
        "hydro_modifier",
        "dynamic_environment_modifier",
        "environment_delta_score",
        "environment_adjusted_risk_score",
    ]
    print(adjusted[cols].describe().to_string())

    print("\n=== environment_adjusted_risk_band ===")
    print(adjusted["environment_adjusted_risk_band"].value_counts(dropna=False))

    if "risk_band" in adjusted.columns:
        print("\n=== original risk_band legacy ===")
        print(adjusted["risk_band"].value_counts(dropna=False))

    print("\n=== original risk_band recomputed ===")
    print(adjusted["risk_band_recomputed"].value_counts(dropna=False))

    print("\n=== risk band transition: recomputed -> adjusted ===")
    print(pd.crosstab(
        adjusted["risk_band_recomputed"],
        adjusted["environment_adjusted_risk_band"],
    ))


if __name__ == "__main__":
    main()