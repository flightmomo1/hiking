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

ACTIVITY_BASE_DIR = BASE_DIR / "ib4_activity_output"

# ib4a 的活動摘要、停留段、微休息段是同一筆 GPX 的固定活動特徵，仍讀共用檔
ACTIVITY_SUMMARY_CSV = ACTIVITY_BASE_DIR / "qixing_activity_summary.csv"
STATIONARY_SEGMENTS_CSV = ACTIVITY_BASE_DIR / "qixing_activity_stationary_segments.csv"
MICRO_REST_SEGMENTS_CSV = ACTIVITY_BASE_DIR / "qixing_activity_micro_rest_segments.csv"

# ib4b 的 overlay 是情境版，必須讀各情境資料夾
SCENARIO_ACTIVITY_DIR = ACTIVITY_BASE_DIR / SCENARIO_NAME
OVERLAY_POINTS_CSV = SCENARIO_ACTIVITY_DIR / "qixing_activity_risk_overlay_points.csv"

OUT_DIR = SCENARIO_ACTIVITY_DIR
OUT_CAPABILITY_CSV = OUT_DIR / "qixing_personal_capability_score.csv"


# =========================================================
# B. Scoring reference values
# =========================================================
"""
第一版先用可解釋的 rule-based normalization。
分數範圍原則：
- 0：明顯偏弱或資料不足
- 50：普通 / 基準
- 100：表現佳

後續有更多受試者資料後，可以把這些 reference value
改成分位數、年齡校正、性別校正或模型學習值。
"""

# 垂直能力參考
REF_VERTICAL_SPEED_LOW_M_H = 250.0
REF_VERTICAL_SPEED_HIGH_M_H = 700.0

REF_300S_GAIN_LOW_M = 20.0
REF_300S_GAIN_HIGH_M = 60.0

# 水平能力參考
REF_HORIZONTAL_SPEED_LOW_KM_H = 1.5
REF_HORIZONTAL_SPEED_HIGH_KM_H = 4.0

REF_300S_HORIZONTAL_DIST_LOW_M = 120.0
REF_300S_HORIZONTAL_DIST_HIGH_M = 350.0

# 節奏穩定參考
REF_SPEED_CV_GOOD = 0.35
REF_SPEED_CV_POOR = 0.90

# 休息反應參考
REF_STATIONARY_RATIO_LOW = 0.05
REF_STATIONARY_RATIO_HIGH = 0.25

REF_MICRO_REST_PER_HOUR_LOW = 5.0
REF_MICRO_REST_PER_HOUR_HIGH = 25.0

# 風險通過能力參考
REF_HIGH_RISK_MOVING_SPEED_LOW_KM_H = 1.0
REF_HIGH_RISK_MOVING_SPEED_HIGH_KM_H = 3.0

REF_VERY_HIGH_RISK_MOVING_SPEED_LOW_KM_H = 0.8
REF_VERY_HIGH_RISK_MOVING_SPEED_HIGH_KM_H = 2.5

REF_HIGH_RISK_REST_RATIO_LOW = 0.03
REF_HIGH_RISK_REST_RATIO_HIGH = 0.25

# 環境挑戰程度參考
# 這些不是「能力分數」，而是用來描述該情境有多困難。
REF_ENV_MODIFIER_LOW = 0.30
REF_ENV_MODIFIER_HIGH = 2.00

REF_HIGH_RISK_DURATION_RATIO_LOW = 0.20
REF_HIGH_RISK_DURATION_RATIO_HIGH = 0.70

REF_VERY_HIGH_RISK_DURATION_RATIO_LOW = 0.05
REF_VERY_HIGH_RISK_DURATION_RATIO_HIGH = 0.35


# =========================================================
# C. Utility
# =========================================================
def ensure_exists(fp: Path):
    if not fp.exists():
        raise FileNotFoundError(f"找不到檔案：{fp.resolve()}")


def read_optional_csv(fp: Path) -> pd.DataFrame:
    if not fp.exists():
        return pd.DataFrame()
    return pd.read_csv(fp)


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


def get_scalar(df: pd.DataFrame, col: str, default=np.nan):
    if df.empty or col not in df.columns:
        return default
    if len(df) == 0:
        return default
    return df[col].iloc[0]


def clamp(v, lo=0.0, hi=100.0):
    if pd.isna(v):
        return np.nan
    return max(lo, min(hi, float(v)))


def score_linear_high_is_good(value, low_ref, high_ref):
    """
    value <= low_ref -> 0
    value >= high_ref -> 100
    中間線性內插
    """
    if pd.isna(value):
        return np.nan
    if high_ref == low_ref:
        return np.nan
    score = (value - low_ref) / (high_ref - low_ref) * 100.0
    return clamp(score)


def score_linear_low_is_good(value, good_ref, poor_ref):
    """
    value <= good_ref -> 100
    value >= poor_ref -> 0
    中間線性內插
    """
    if pd.isna(value):
        return np.nan
    if poor_ref == good_ref:
        return np.nan
    score = (poor_ref - value) / (poor_ref - good_ref) * 100.0
    return clamp(score)


def safe_divide(a, b):
    if pd.isna(a) or pd.isna(b) or b == 0:
        return np.nan
    return a / b


def weighted_mean(values, weights=None):
    vals = np.array(values, dtype=float)

    if weights is None:
        weights = np.ones_like(vals)
    else:
        weights = np.array(weights, dtype=float)

    mask = np.isfinite(vals) & np.isfinite(weights) & (weights > 0)

    if mask.sum() == 0:
        return np.nan

    return float(np.sum(vals[mask] * weights[mask]) / np.sum(weights[mask]))


def normalize_bool_series(s):
    return (
        s.astype(str)
        .str.lower()
        .isin(["true", "1", "yes"])
    )


# =========================================================
# D. Feature extraction
# =========================================================
def compute_speed_variability(overlay_df: pd.DataFrame):
    """
    用 moving points 的平滑速度計算速度變異。
    speed_cv = std / mean
    """
    if overlay_df.empty:
        return {
            "moving_speed_mean_km_h": np.nan,
            "moving_speed_std_km_h": np.nan,
            "moving_speed_cv": np.nan,
        }

    df = overlay_df.copy()

    if "moving_flag" in df.columns:
        moving_mask = normalize_bool_series(df["moving_flag"])
    else:
        moving_mask = pd.Series([True] * len(df))

    speed_col = None
    for c in ["speed_km_h_smooth", "speed_km_h"]:
        if c in df.columns:
            speed_col = c
            break

    if speed_col is None:
        return {
            "moving_speed_mean_km_h": np.nan,
            "moving_speed_std_km_h": np.nan,
            "moving_speed_cv": np.nan,
        }

    speed = pd.to_numeric(df.loc[moving_mask, speed_col], errors="coerce")
    speed = speed.replace([np.inf, -np.inf], np.nan).dropna()

    # 排除過低速度，避免停頓點把變異拉太大
    speed = speed[speed > 0.2]

    if len(speed) < 3:
        return {
            "moving_speed_mean_km_h": np.nan,
            "moving_speed_std_km_h": np.nan,
            "moving_speed_cv": np.nan,
        }

    mean_v = speed.mean()
    std_v = speed.std()

    return {
        "moving_speed_mean_km_h": mean_v,
        "moving_speed_std_km_h": std_v,
        "moving_speed_cv": safe_divide(std_v, mean_v),
    }


def compute_risk_exposure_features(overlay_df: pd.DataFrame):
    if overlay_df.empty:
        return {}

    df = overlay_df.copy()

    numeric_cols = [
        "delta_time_s",
        "delta_dist_m_clean",
        "delta_dist_m",
        "speed_km_h",
        "speed_km_h_smooth",
        "gain_m",
        "loss_m",
        "route_environment_adjusted_risk_score",
        "route_dynamic_environment_modifier",
        "route_weather_modifier",
        "route_hydro_modifier",
    ]
    df = to_numeric_safe(df, numeric_cols)

    if "moving_flag" in df.columns:
        df["moving_flag"] = normalize_bool_series(df["moving_flag"])
    else:
        df["moving_flag"] = True

    if "stationary_flag" in df.columns:
        df["stationary_flag"] = normalize_bool_series(df["stationary_flag"])
    else:
        df["stationary_flag"] = False

    if "micro_rest_flag" in df.columns:
        df["micro_rest_flag"] = normalize_bool_series(df["micro_rest_flag"])
    else:
        df["micro_rest_flag"] = False

    if "route_adjusted_risk_band_norm" not in df.columns:
        df["route_adjusted_risk_band_norm"] = "unknown"

    total_duration_s = df["delta_time_s"].sum()

    high_mask = df["route_adjusted_risk_band_norm"].isin(["high", "very_high"])
    very_high_mask = df["route_adjusted_risk_band_norm"].eq("very_high")

    moving_high = df[high_mask & df["moving_flag"]].copy()
    moving_very_high = df[very_high_mask & df["moving_flag"]].copy()

    high_duration_s = df.loc[high_mask, "delta_time_s"].sum()
    very_high_duration_s = df.loc[very_high_mask, "delta_time_s"].sum()

    high_moving_duration_s = moving_high["delta_time_s"].sum()
    very_high_moving_duration_s = moving_very_high["delta_time_s"].sum()

    high_dist_m = (
        moving_high["delta_dist_m_clean"].sum()
        if "delta_dist_m_clean" in moving_high.columns
        else moving_high["delta_dist_m"].sum()
    )

    very_high_dist_m = (
        moving_very_high["delta_dist_m_clean"].sum()
        if "delta_dist_m_clean" in moving_very_high.columns
        else moving_very_high["delta_dist_m"].sum()
    )

    high_moving_speed_km_h = (
        high_dist_m / high_moving_duration_s * 3.6
        if high_moving_duration_s > 0
        else np.nan
    )

    very_high_moving_speed_km_h = (
        very_high_dist_m / very_high_moving_duration_s * 3.6
        if very_high_moving_duration_s > 0
        else np.nan
    )

    high_stationary_duration_s = df.loc[high_mask & df["stationary_flag"], "delta_time_s"].sum()
    high_micro_rest_duration_s = df.loc[high_mask & df["micro_rest_flag"], "delta_time_s"].sum()

    very_high_stationary_duration_s = df.loc[
        very_high_mask & df["stationary_flag"],
        "delta_time_s",
    ].sum()

    very_high_micro_rest_duration_s = df.loc[
        very_high_mask & df["micro_rest_flag"],
        "delta_time_s",
    ].sum()

    high_rest_duration_s = high_stationary_duration_s + high_micro_rest_duration_s
    very_high_rest_duration_s = (
        very_high_stationary_duration_s + very_high_micro_rest_duration_s
    )

    high_rest_ratio = safe_divide(high_rest_duration_s, high_duration_s)
    very_high_rest_ratio = safe_divide(very_high_rest_duration_s, very_high_duration_s)

    return {
        "duration_min_in_adjusted_high_or_above": high_duration_s / 60.0,
        "duration_min_in_adjusted_very_high": very_high_duration_s / 60.0,

        "duration_ratio_in_adjusted_high_or_above": safe_divide(high_duration_s, total_duration_s),
        "duration_ratio_in_adjusted_very_high": safe_divide(very_high_duration_s, total_duration_s),

        "moving_speed_km_h_in_adjusted_high_or_above": high_moving_speed_km_h,
        "moving_speed_km_h_in_adjusted_very_high": very_high_moving_speed_km_h,

        "stationary_duration_min_in_adjusted_high_or_above": high_stationary_duration_s / 60.0,
        "micro_rest_duration_min_in_adjusted_high_or_above": high_micro_rest_duration_s / 60.0,

        "stationary_duration_min_in_adjusted_very_high": very_high_stationary_duration_s / 60.0,
        "micro_rest_duration_min_in_adjusted_very_high": very_high_micro_rest_duration_s / 60.0,

        "rest_ratio_in_adjusted_high_or_above": high_rest_ratio,
        "rest_ratio_in_adjusted_very_high": very_high_rest_ratio,

        "micro_rest_count_in_adjusted_high_or_above": int(
            (high_mask & df["micro_rest_flag"]).sum()
        ),
        "micro_rest_count_in_adjusted_very_high": int(
            (very_high_mask & df["micro_rest_flag"]).sum()
        ),

        "environment_modifier_mean": (
            df["route_dynamic_environment_modifier"].mean()
            if "route_dynamic_environment_modifier" in df.columns
            else np.nan
        ),
        "environment_modifier_max": (
            df["route_dynamic_environment_modifier"].max()
            if "route_dynamic_environment_modifier" in df.columns
            else np.nan
        ),
        "weather_modifier_mean": (
            df["route_weather_modifier"].mean()
            if "route_weather_modifier" in df.columns
            else np.nan
        ),
        "hydro_modifier_mean": (
            df["route_hydro_modifier"].mean()
            if "route_hydro_modifier" in df.columns
            else np.nan
        ),
    }


def compute_rest_features(activity_summary_df, stationary_df, micro_rest_df):
    total_duration_min = get_scalar(activity_summary_df, "total_duration_min")
    stationary_duration_min = get_scalar(activity_summary_df, "stationary_duration_min", 0.0)
    stationary_count = get_scalar(activity_summary_df, "stationary_count", 0)

    micro_rest_duration_min = get_scalar(activity_summary_df, "micro_rest_duration_min", 0.0)
    micro_rest_count = get_scalar(activity_summary_df, "micro_rest_count", 0)

    stationary_ratio = safe_divide(stationary_duration_min, total_duration_min)
    micro_rest_ratio = safe_divide(micro_rest_duration_min, total_duration_min)

    micro_rest_per_hour = (
        micro_rest_count / (total_duration_min / 60.0)
        if pd.notna(total_duration_min) and total_duration_min > 0
        else np.nan
    )

    stationary_per_hour = (
        stationary_count / (total_duration_min / 60.0)
        if pd.notna(total_duration_min) and total_duration_min > 0
        else np.nan
    )

    return {
        "stationary_count": stationary_count,
        "stationary_duration_min": stationary_duration_min,
        "stationary_ratio": stationary_ratio,
        "stationary_per_hour": stationary_per_hour,

        "micro_rest_count": micro_rest_count,
        "micro_rest_duration_min": micro_rest_duration_min,
        "micro_rest_ratio": micro_rest_ratio,
        "micro_rest_per_hour": micro_rest_per_hour,
    }


# =========================================================
# E. Capability score
# =========================================================
def compute_capability_scores(features: dict):
    # -----------------------------
    # A. 垂直能力
    # -----------------------------
    score_vertical_speed = score_linear_high_is_good(
        features.get("max_300s_vertical_speed_m_h"),
        REF_VERTICAL_SPEED_LOW_M_H,
        REF_VERTICAL_SPEED_HIGH_M_H,
    )

    score_300s_gain = score_linear_high_is_good(
        features.get("max_300s_gain_m"),
        REF_300S_GAIN_LOW_M,
        REF_300S_GAIN_HIGH_M,
    )

    vertical_capability_score = weighted_mean(
        [score_vertical_speed, score_300s_gain],
        [0.6, 0.4],
    )

    # -----------------------------
    # B. 水平能力
    # -----------------------------
    score_horizontal_speed = score_linear_high_is_good(
        features.get("max_300s_horizontal_speed_km_h"),
        REF_HORIZONTAL_SPEED_LOW_KM_H,
        REF_HORIZONTAL_SPEED_HIGH_KM_H,
    )

    score_300s_horizontal_dist = score_linear_high_is_good(
        features.get("max_300s_horizontal_distance_m"),
        REF_300S_HORIZONTAL_DIST_LOW_M,
        REF_300S_HORIZONTAL_DIST_HIGH_M,
    )

    score_moving_avg_speed = score_linear_high_is_good(
        features.get("moving_avg_speed_km_h"),
        REF_HORIZONTAL_SPEED_LOW_KM_H,
        REF_HORIZONTAL_SPEED_HIGH_KM_H,
    )

    horizontal_capability_score = weighted_mean(
        [score_horizontal_speed, score_300s_horizontal_dist, score_moving_avg_speed],
        [0.4, 0.35, 0.25],
    )

    # -----------------------------
    # C. 節奏穩定性
    # -----------------------------
    score_speed_stability = score_linear_low_is_good(
        features.get("moving_speed_cv"),
        REF_SPEED_CV_GOOD,
        REF_SPEED_CV_POOR,
    )

    # 若速度平均太低，穩定但慢不應給太高；乘上一個移動速度修正
    speed_level_score = score_linear_high_is_good(
        features.get("moving_avg_speed_km_h"),
        REF_HORIZONTAL_SPEED_LOW_KM_H,
        REF_HORIZONTAL_SPEED_HIGH_KM_H,
    )

    pacing_stability_score = weighted_mean(
        [score_speed_stability, speed_level_score],
        [0.65, 0.35],
    )

    # -----------------------------
    # D. 休息反應
    # -----------------------------
    score_stationary_ratio = score_linear_low_is_good(
        features.get("stationary_ratio"),
        REF_STATIONARY_RATIO_LOW,
        REF_STATIONARY_RATIO_HIGH,
    )

    score_micro_rest_frequency = score_linear_low_is_good(
        features.get("micro_rest_per_hour"),
        REF_MICRO_REST_PER_HOUR_LOW,
        REF_MICRO_REST_PER_HOUR_HIGH,
    )

    rest_response_score = weighted_mean(
        [score_stationary_ratio, score_micro_rest_frequency],
        [0.55, 0.45],
    )

    # -----------------------------
    # E1. 情境通過表現
    # -----------------------------
    # 這是「在目前被定義為 high / very_high 的路段中，
    # 使用者通過得是否順暢」。
    # 天氣較好時，這個分數可能較高；但它不等於環境適應能力。
    score_high_risk_speed = score_linear_high_is_good(
        features.get("moving_speed_km_h_in_adjusted_high_or_above"),
        REF_HIGH_RISK_MOVING_SPEED_LOW_KM_H,
        REF_HIGH_RISK_MOVING_SPEED_HIGH_KM_H,
    )

    score_very_high_risk_speed = score_linear_high_is_good(
        features.get("moving_speed_km_h_in_adjusted_very_high"),
        REF_VERY_HIGH_RISK_MOVING_SPEED_LOW_KM_H,
        REF_VERY_HIGH_RISK_MOVING_SPEED_HIGH_KM_H,
    )

    score_high_risk_rest_ratio = score_linear_low_is_good(
        features.get("rest_ratio_in_adjusted_high_or_above"),
        REF_HIGH_RISK_REST_RATIO_LOW,
        REF_HIGH_RISK_REST_RATIO_HIGH,
    )

    scenario_passing_score = weighted_mean(
        [
            score_high_risk_speed,
            score_very_high_risk_speed,
            score_high_risk_rest_ratio,
        ],
        [0.35, 0.35, 0.30],
    )

    # 保留舊欄位名稱，避免後續腳本或舊 CSV 對不上。
    # 但語意上 risk_handling_score = scenario_passing_score。
    risk_handling_score = scenario_passing_score

    # -----------------------------
    # E2. 環境挑戰程度
    # -----------------------------
    # 這是「該環境條件本身有多困難」。
    # 天氣越差、動態修正量越高、high / very_high 暴露時間越長，分數越高。
    score_environment_modifier = score_linear_high_is_good(
        features.get("environment_modifier_mean"),
        REF_ENV_MODIFIER_LOW,
        REF_ENV_MODIFIER_HIGH,
    )

    score_high_risk_duration_ratio = score_linear_high_is_good(
        features.get("duration_ratio_in_adjusted_high_or_above"),
        REF_HIGH_RISK_DURATION_RATIO_LOW,
        REF_HIGH_RISK_DURATION_RATIO_HIGH,
    )

    score_very_high_risk_duration_ratio = score_linear_high_is_good(
        features.get("duration_ratio_in_adjusted_very_high"),
        REF_VERY_HIGH_RISK_DURATION_RATIO_LOW,
        REF_VERY_HIGH_RISK_DURATION_RATIO_HIGH,
    )

    environment_challenge_score = weighted_mean(
        [
            score_environment_modifier,
            score_high_risk_duration_ratio,
            score_very_high_risk_duration_ratio,
        ],
        [0.45, 0.30, 0.25],
    )

    # -----------------------------
    # E3. 環境適應能力證明強度
    # -----------------------------
    # 同樣表現若發生於較差環境，才更能證明環境適應能力。
    # 因此以「情境通過表現 × 環境挑戰程度」計算。
    if pd.notna(scenario_passing_score) and pd.notna(environment_challenge_score):
        environment_adaptation_score = (
            scenario_passing_score * environment_challenge_score / 100.0
        )
    else:
        environment_adaptation_score = np.nan


    # -----------------------------
    # Composite indices
    # -----------------------------
    # base_capability_index：
    #   只描述「人的基礎活動能力」，不納入情境風險分級。
    #   因此同一份 GPX 在不同天候情境下應維持一致。
    base_capability_index = weighted_mean(
        [
            vertical_capability_score,
            horizontal_capability_score,
            pacing_stability_score,
            rest_response_score,
        ],
        [0.30, 0.25, 0.25, 0.20],
    )

    # scenario_adjusted_performance_index：
    #   描述「基礎能力 + 當前情境下高風險路段通過表現」。
    #   會隨 high / very_high 區段重新分配而改變。
    scenario_adjusted_performance_index = weighted_mean(
        [
            vertical_capability_score,
            horizontal_capability_score,
            pacing_stability_score,
            rest_response_score,
            scenario_passing_score,
        ],
        [0.25, 0.20, 0.20, 0.15, 0.20],
    )

    # 保留舊欄位名稱，但語意改為「基礎能力指數」。
    # 如果後續腳本仍讀 personal_capability_index，會得到不受情境影響的能力值。
    personal_capability_index = base_capability_index

    return {
        "score_vertical_speed": score_vertical_speed,
        "score_300s_gain": score_300s_gain,
        "vertical_capability_score": vertical_capability_score,

        "score_horizontal_speed": score_horizontal_speed,
        "score_300s_horizontal_dist": score_300s_horizontal_dist,
        "score_moving_avg_speed": score_moving_avg_speed,
        "horizontal_capability_score": horizontal_capability_score,

        "score_speed_stability": score_speed_stability,
        "score_speed_level": speed_level_score,
        "pacing_stability_score": pacing_stability_score,

        "score_stationary_ratio": score_stationary_ratio,
        "score_micro_rest_frequency": score_micro_rest_frequency,
        "rest_response_score": rest_response_score,

        "score_high_risk_speed": score_high_risk_speed,
        "score_very_high_risk_speed": score_very_high_risk_speed,
        "score_high_risk_rest_ratio": score_high_risk_rest_ratio,
        "scenario_passing_score": scenario_passing_score,
        "risk_handling_score": risk_handling_score,

        "score_environment_modifier": score_environment_modifier,
        "score_high_risk_duration_ratio": score_high_risk_duration_ratio,
        "score_very_high_risk_duration_ratio": score_very_high_risk_duration_ratio,
        "environment_challenge_score": environment_challenge_score,

        "environment_adaptation_score": environment_adaptation_score,

        "base_capability_index": base_capability_index,
        "scenario_adjusted_performance_index": scenario_adjusted_performance_index,
        "personal_capability_index": personal_capability_index,
    }


def classify_capability(score):
    if pd.isna(score):
        return "unknown"
    if score >= 80:
        return "excellent"
    if score >= 65:
        return "good"
    if score >= 50:
        return "moderate"
    if score >= 35:
        return "limited"
    return "low"


def build_interpretation(features):
    pci = features.get("personal_capability_index")
    base = features.get("base_capability_index")
    sapi = features.get("scenario_adjusted_performance_index")
    v = features.get("vertical_capability_score")
    h = features.get("horizontal_capability_score")
    p = features.get("pacing_stability_score")
    r = features.get("rest_response_score")
    sp = features.get("scenario_passing_score")
    ec = features.get("environment_challenge_score")
    ea = features.get("environment_adaptation_score")

    lines = []

    lines.append(
        f"Base capability class: {classify_capability(base)}; "
        f"Scenario-adjusted performance: {classify_capability(sapi)}."
    )

    lines.append(
        f"Vertical capability: {classify_capability(v)}; "
        f"Horizontal capability: {classify_capability(h)}."
    )

    lines.append(
        f"Pacing stability: {classify_capability(p)}; "
        f"Rest response: {classify_capability(r)}; "
        f"Scenario passing: {classify_capability(sp)}."
    )

    lines.append(
        f"Environment challenge: {classify_capability(ec)}; "
        f"Environment adaptation evidence: {classify_capability(ea)}."
    )

    if pd.notna(features.get("micro_rest_per_hour")):
        lines.append(
            f"Micro-rest frequency: {features.get('micro_rest_per_hour'):.2f} events/hour."
        )

    if pd.notna(features.get("duration_min_in_adjusted_very_high")):
        lines.append(
            f"Very-high adjusted risk exposure: "
            f"{features.get('duration_min_in_adjusted_very_high'):.1f} min."
        )

    return " ".join(lines)


# =========================================================
# F. Main
# =========================================================
def main():
    ensure_exists(ACTIVITY_SUMMARY_CSV)
    ensure_exists(OVERLAY_POINTS_CSV)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    activity_summary_df = normalize_columns(pd.read_csv(ACTIVITY_SUMMARY_CSV))
    overlay_df = normalize_columns(pd.read_csv(OVERLAY_POINTS_CSV))
    stationary_df = normalize_columns(read_optional_csv(STATIONARY_SEGMENTS_CSV))
    micro_rest_df = normalize_columns(read_optional_csv(MICRO_REST_SEGMENTS_CSV))

    numeric_cols_summary = [
        "total_duration_min",
        "moving_duration_min",
        "stationary_duration_min",
        "stationary_count",
        "micro_rest_duration_min",
        "micro_rest_count",
        "total_distance_km",
        "total_gain_m",
        "total_loss_m",
        "moving_avg_speed_km_h",
        "max_300s_gain_m",
        "max_300s_vertical_speed_m_h",
        "max_300s_horizontal_distance_m",
        "max_300s_horizontal_speed_km_h",
        "uphill_ratio",
        "downhill_ratio",
        "flat_ratio",
    ]

    activity_summary_df = to_numeric_safe(activity_summary_df, numeric_cols_summary)

    numeric_cols_overlay = [
        "delta_time_s",
        "delta_dist_m",
        "delta_dist_m_clean",
        "speed_km_h",
        "speed_km_h_smooth",
        "gain_m",
        "loss_m",
        "route_environment_adjusted_risk_score",
    ]

    overlay_df = to_numeric_safe(overlay_df, numeric_cols_overlay)

    # -----------------------------
    # Basic features from ib4a
    # -----------------------------
    features = {
        "total_duration_min": get_scalar(activity_summary_df, "total_duration_min"),
        "moving_duration_min": get_scalar(activity_summary_df, "moving_duration_min"),
        "total_distance_km": get_scalar(activity_summary_df, "total_distance_km"),
        "total_gain_m": get_scalar(activity_summary_df, "total_gain_m"),
        "total_loss_m": get_scalar(activity_summary_df, "total_loss_m"),
        "moving_avg_speed_km_h": get_scalar(activity_summary_df, "moving_avg_speed_km_h"),

        "max_300s_gain_m": get_scalar(activity_summary_df, "max_300s_gain_m"),
        "max_300s_vertical_speed_m_h": get_scalar(activity_summary_df, "max_300s_vertical_speed_m_h"),
        "max_300s_horizontal_distance_m": get_scalar(activity_summary_df, "max_300s_horizontal_distance_m"),
        "max_300s_horizontal_speed_km_h": get_scalar(activity_summary_df, "max_300s_horizontal_speed_km_h"),

        "uphill_ratio": get_scalar(activity_summary_df, "uphill_ratio"),
        "downhill_ratio": get_scalar(activity_summary_df, "downhill_ratio"),
        "flat_ratio": get_scalar(activity_summary_df, "flat_ratio"),
    }

    # -----------------------------
    # Rest features
    # -----------------------------
    features.update(
        compute_rest_features(
            activity_summary_df=activity_summary_df,
            stationary_df=stationary_df,
            micro_rest_df=micro_rest_df,
        )
    )

    # -----------------------------
    # Speed variation
    # -----------------------------
    features.update(compute_speed_variability(overlay_df))

    # -----------------------------
    # Risk exposure
    # -----------------------------
    features.update(compute_risk_exposure_features(overlay_df))

    # -----------------------------
    # Scores
    # -----------------------------
    score_dict = compute_capability_scores(features)
    features.update(score_dict)

    features["base_capability_class"] = classify_capability(
        features.get("base_capability_index")
    )

    features["scenario_adjusted_performance_class"] = classify_capability(
        features.get("scenario_adjusted_performance_index")
    )

    # 保留舊欄位名稱，對應 personal_capability_index。
    features["overall_capability_class"] = classify_capability(
        features.get("personal_capability_index")
    )

    features["vertical_capability_class"] = classify_capability(
        features.get("vertical_capability_score")
    )
    features["horizontal_capability_class"] = classify_capability(
        features.get("horizontal_capability_score")
    )
    features["pacing_stability_class"] = classify_capability(
        features.get("pacing_stability_score")
    )
    features["rest_response_class"] = classify_capability(
        features.get("rest_response_score")
    )
    features["risk_handling_class"] = classify_capability(
        features.get("risk_handling_score")
    )

    features["scenario_passing_class"] = classify_capability(
        features.get("scenario_passing_score")
    )
    features["environment_challenge_class"] = classify_capability(
        features.get("environment_challenge_score")
    )
    features["environment_adaptation_class"] = classify_capability(
        features.get("environment_adaptation_score")
    )

    features["interpretation"] = build_interpretation(features)

    out_df = pd.DataFrame([features])
    out_df.to_csv(OUT_CAPABILITY_CSV, index=False, encoding="utf-8-sig")

    # -----------------------------
    # Console output
    # -----------------------------
    print("完成！")
    print("scenario:", SCENARIO_NAME)
    print("capability CSV:", OUT_CAPABILITY_CSV.resolve())

    print("\n=== key activity features ===")
    key_features = [
        "total_duration_min",
        "moving_duration_min",
        "total_distance_km",
        "total_gain_m",
        "moving_avg_speed_km_h",
        "max_300s_gain_m",
        "max_300s_vertical_speed_m_h",
        "max_300s_horizontal_distance_m",
        "max_300s_horizontal_speed_km_h",
        "moving_speed_cv",
        "stationary_count",
        "stationary_duration_min",
        "micro_rest_count",
        "micro_rest_duration_min",
        "micro_rest_per_hour",
        "duration_min_in_adjusted_high_or_above",
        "duration_min_in_adjusted_very_high",
        "moving_speed_km_h_in_adjusted_high_or_above",
        "moving_speed_km_h_in_adjusted_very_high",
        "rest_ratio_in_adjusted_high_or_above",
        "environment_modifier_mean",
        "environment_modifier_max",
        "duration_ratio_in_adjusted_high_or_above",
        "duration_ratio_in_adjusted_very_high",
    ]

    for k in key_features:
        print(f"{k}: {features.get(k)}")

    print("\n=== capability scores ===")
    score_keys = [
        "vertical_capability_score",
        "horizontal_capability_score",
        "pacing_stability_score",
        "rest_response_score",

        "scenario_passing_score",
        "risk_handling_score",

        "environment_challenge_score",
        "environment_adaptation_score",

        "base_capability_index",
        "base_capability_class",

        "scenario_adjusted_performance_index",
        "scenario_adjusted_performance_class",

        "personal_capability_index",
        "overall_capability_class",

        "scenario_passing_class",
        "environment_challenge_class",
        "environment_adaptation_class",
    ]

    for k in score_keys:
        print(f"{k}: {features.get(k)}")

    print("\n=== interpretation ===")
    print(features["interpretation"])


if __name__ == "__main__":
    main()