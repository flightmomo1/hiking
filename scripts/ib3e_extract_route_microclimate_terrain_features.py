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
OUT_DIR = ENV_BASE_DIR / SCENARIO_NAME
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_FEATURES_CSV = OUT_DIR / "qixing_route_microclimate_terrain_features.csv"
OUT_SUMMARY_CSV = OUT_DIR / "qixing_route_microclimate_terrain_features_summary.csv"

# =========================================================
# B. Input candidates
# =========================================================
# 優先讀已整合 OSM / 地形 / 風險的資料。
# 若檔案不存在，會往下找其他候選。
ROUTE_INPUT_CANDIDATES = [
    OUT_DIR / "qixing_environment_adjusted_risk.csv",
    BASE_DIR / "ib2_route_risk_profile_output" / "qixing_route_risk_profile_plot_data.csv",
    BASE_DIR / "ib2_route_risk_profile_output" / "qixing_route_risk_points.csv",
    BASE_DIR / "ib2_route_risk_profile_output" / "qixing_route_risk_scored.csv",
    BASE_DIR / "ib2_v2_route_risk_output" / "qixing_route_risk_v2.csv",
    BASE_DIR / "ib1c_route_profile_semantic_output" / "qixing_route_profile_semantic_enriched.csv",
]


# =========================================================
# C. Parameters
# =========================================================
# altitude regime thresholds, Taiwan hiking-oriented
ALT_LOW_MAX_M = 800
ALT_MID_MAX_M = 1500
ALT_UPPER_MID_MAX_M = 2500
ALT_HIGH_MAX_M = 3000

# slope thresholds, percent
SLOPE_GENTLE_MAX = 5
SLOPE_MODERATE_MAX = 15
SLOPE_STEEP_MAX = 30
SLOPE_VERY_STEEP_MAX = 45

# score caps
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


def to_numeric_safe(df: pd.DataFrame, cols):
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def clamp_series(s, lo=SCORE_MIN, hi=SCORE_MAX):
    return pd.to_numeric(s, errors="coerce").fillna(0.0).clip(lo, hi)


def contains_any(value, keywords):
    if pd.isna(value):
        return False
    text = str(value).lower()
    return any(str(k).lower() in text for k in keywords)


def bool_col(df, col):
    if col not in df.columns:
        return pd.Series(False, index=df.index)

    s = df[col]

    if s.dtype == bool:
        return s.fillna(False)

    return s.astype(str).str.lower().isin(
        ["true", "1", "yes", "y", "t", "near", "present"]
    )


def numeric_col(df, col, default=np.nan):
    if col not in df.columns:
        return pd.Series(default, index=df.index)
    return pd.to_numeric(df[col], errors="coerce")


def find_route_input():
    for fp in ROUTE_INPUT_CANDIDATES:
        if fp.exists():
            try:
                df = pd.read_csv(fp, nrows=5)
                cols = set(df.columns)
                if "dist_m" in cols or "dist_mid" in cols:
                    return fp
            except Exception:
                pass

    # fallback：在 BASE_DIR 內找含 dist 與 ele/slope 的 CSV
    candidates = []
    for fp in BASE_DIR.rglob("*.csv"):
        if "ib_scenario_output" in fp.parts:
            continue

        try:
            df = pd.read_csv(fp, nrows=5)
            cols = set(df.columns)
            has_dist = any(c in cols for c in ["dist_m", "dist_mid", "distance_m", "cumdist_m"])
            has_geo = any(c in cols for c in ["ele_smooth", "ele_gpx_m", "slope_pct", "slope_final"])
            if has_dist and has_geo:
                candidates.append(fp)
        except Exception:
            continue

    if not candidates:
        raise FileNotFoundError(
            "找不到可用路線 CSV。請確認 ib1c / ib2 / ib3c 已產生路線資料。"
        )

    candidates = sorted(candidates, key=lambda p: (0 if "risk" in p.name.lower() else 1, len(str(p))))
    return candidates[0]


def choose_first_existing_col(df, candidates, default_name=None):
    for c in candidates:
        if c in df.columns:
            return c
    return default_name


# =========================================================
# E. Classification
# =========================================================
def classify_altitude_regime(ele_m):
    if pd.isna(ele_m):
        return "unknown"

    ele_m = float(ele_m)

    if ele_m < ALT_LOW_MAX_M:
        return "low_altitude"
    if ele_m < ALT_MID_MAX_M:
        return "mid_altitude"
    if ele_m < ALT_UPPER_MID_MAX_M:
        return "upper_mid_altitude"
    if ele_m < ALT_HIGH_MAX_M:
        return "high_altitude"
    return "very_high_altitude"


def classify_slope_regime(slope_pct):
    if pd.isna(slope_pct):
        return "unknown"

    s = abs(float(slope_pct))

    if s < SLOPE_GENTLE_MAX:
        return "flat_or_gentle"
    if s < SLOPE_MODERATE_MAX:
        return "moderate_slope"
    if s < SLOPE_STEEP_MAX:
        return "steep_slope"
    if s < SLOPE_VERY_STEEP_MAX:
        return "very_steep_slope"
    return "extreme_slope"


def classify_route_exposure(row):
    """
    路線暴露程度：先用 OSM/地貌語意粗估。
    """
    flags = []

    for c in [
        "hazard_flags",
        "technical_flags",
        "route_semantic_class",
        "osm_vertical_context",
        "nearby_named_features",
        "surface_class",
    ]:
        if c in row.index and pd.notna(row[c]):
            flags.append(str(row[c]).lower())

    text = " | ".join(flags)

    near_cliff = bool(row.get("near_cliff", False))
    near_bare_rock = bool(row.get("near_bare_rock", False))
    near_scree = bool(row.get("near_scree", False))
    near_landslide = bool(row.get("near_landslide", False))

    if near_cliff or "cliff" in text:
        return "cliff_exposed"

    if near_bare_rock or "bare_rock" in text or "bare rock" in text:
        return "bare_rock_exposed"

    if near_scree or "scree" in text:
        return "scree_exposed"

    if near_landslide or "landslide" in text:
        return "unstable_exposed"

    if contains_any(text, ["ridge", "summit", "peak", "open", "exposed"]):
        return "ridge_or_open_exposed"

    if contains_any(text, ["forest", "wood", "shaded", "covered"]):
        return "sheltered_or_shaded"

    return "general_trail"


def classify_moisture_retention(row):
    """
    濕氣滯留或路面不易乾燥的可能性。
    """
    near_waterway = bool(row.get("near_waterway", False))
    near_water_area = bool(row.get("near_water_area", False))
    near_wetland = bool(row.get("near_wetland", False))

    text_parts = []
    for c in [
        "hydrology_flags",
        "surface_class",
        "route_semantic_class",
        "osm_surface",
        "osm_highway",
        "nearby_named_features",
    ]:
        if c in row.index and pd.notna(row[c]):
            text_parts.append(str(row[c]).lower())

    text = " | ".join(text_parts)

    if near_wetland or "wetland" in text:
        return "wetland_or_saturated"

    if near_waterway or near_water_area or contains_any(text, ["waterway", "stream", "river", "creek", "ditch"]):
        return "near_water_or_drainage"

    if contains_any(text, ["mud", "soil", "earth", "dirt", "grass"]):
        return "moisture_retaining_surface"

    if contains_any(text, ["forest", "wood", "shaded", "covered"]):
        return "shaded_retains_moisture"

    return "normal_drying"


def classify_surface_slip(row):
    text_parts = []
    for c in [
        "surface_class",
        "route_semantic_class",
        "osm_surface",
        "osm_highway",
        "hazard_flags",
        "technical_flags",
    ]:
        if c in row.index and pd.notna(row[c]):
            text_parts.append(str(row[c]).lower())

    text = " | ".join(text_parts)

    near_bare_rock = bool(row.get("near_bare_rock", False))
    near_scree = bool(row.get("near_scree", False))

    if contains_any(text, ["steps", "stair", "stone_steps"]):
        return "steps_slip_sensitive"

    if near_bare_rock or contains_any(text, ["bare_rock", "rock", "stone", "paved_stone"]):
        return "rock_slip_sensitive"

    if near_scree or contains_any(text, ["scree", "gravel", "loose"]):
        return "loose_surface_slip_sensitive"

    if contains_any(text, ["mud", "soil", "earth", "dirt", "grass", "ground"]):
        return "natural_surface_slip_sensitive"

    if contains_any(text, ["asphalt", "concrete", "paved"]):
        return "paved_low_to_moderate_slip"

    return "general_slip_sensitivity"


# =========================================================
# F. Factor computation
# =========================================================
def altitude_thermal_amplifier(ele_m):
    """
    海拔對低溫、風寒、濕冷的放大效果。
    七星山約屬 mid_altitude，不是高山症模型，但可作為濕冷/風霧放大。
    """
    if pd.isna(ele_m):
        return 0.0

    ele_m = float(ele_m)

    if ele_m < 800:
        return 0.10
    if ele_m < 1500:
        return 0.35
    if ele_m < 2500:
        return 0.60
    if ele_m < 3000:
        return 0.80
    return 1.00


def altitude_load_factor(ele_m, cum_gain_m=None):
    """
    海拔 + 累積爬升造成的負荷提示。
    注意：這不是個人生理高度適應模型，只是環境負荷因子。
    """
    base = altitude_thermal_amplifier(ele_m)

    gain_factor = 0.0
    if cum_gain_m is not None and pd.notna(cum_gain_m):
        gain_factor = min(float(cum_gain_m) / 1000.0, 1.0) * 0.35

    return min(base * 0.65 + gain_factor, 1.0)


def slope_load_factor(slope_pct):
    if pd.isna(slope_pct):
        return 0.0

    s = abs(float(slope_pct))

    if s < 5:
        return 0.05
    if s < 15:
        return 0.25
    if s < 30:
        return 0.55
    if s < 45:
        return 0.80
    return 1.00


def exposure_factor_from_class(exposure_class):
    mapping = {
        "general_trail": 0.20,
        "sheltered_or_shaded": 0.10,
        "ridge_or_open_exposed": 0.65,
        "bare_rock_exposed": 0.75,
        "scree_exposed": 0.70,
        "unstable_exposed": 0.85,
        "cliff_exposed": 1.00,
    }
    return mapping.get(str(exposure_class), 0.20)


def moisture_retention_factor_from_class(cls):
    mapping = {
        "normal_drying": 0.10,
        "shaded_retains_moisture": 0.35,
        "moisture_retaining_surface": 0.45,
        "near_water_or_drainage": 0.65,
        "wetland_or_saturated": 0.90,
    }
    return mapping.get(str(cls), 0.10)


def slip_factor_from_class(cls):
    mapping = {
        "general_slip_sensitivity": 0.25,
        "paved_low_to_moderate_slip": 0.25,
        "natural_surface_slip_sensitive": 0.50,
        "loose_surface_slip_sensitive": 0.65,
        "rock_slip_sensitive": 0.75,
        "steps_slip_sensitive": 0.80,
    }
    return mapping.get(str(cls), 0.25)


def support_reduction_factor(row):
    """
    欄杆、安全繩、輔助設施可降低部分跌倒/暴露風險。
    不是降低天氣本身，而是降低路段通過風險。
    """
    has_handrail = bool(row.get("near_handrail", False)) or str(row.get("osm_handrail", "")).lower() in ["yes", "true", "1"]
    has_rope = bool(row.get("near_safety_rope", False)) or str(row.get("osm_safety_rope", "")).lower() in ["yes", "true", "1"]

    if has_handrail and has_rope:
        return 0.25
    if has_handrail or has_rope:
        return 0.15
    return 0.0


def build_microclimate_interaction_hint(row):
    altitude = row.get("altitude_regime", "unknown")
    exposure = row.get("route_exposure_class", "general_trail")
    moisture = row.get("terrain_moisture_retention_class", "normal_drying")
    slip = row.get("surface_wet_slip_class", "general_slip_sensitivity")

    hints = []

    if altitude in ["mid_altitude", "upper_mid_altitude", "high_altitude", "very_high_altitude"]:
        hints.append("altitude_amplified_weather")

    if exposure in ["ridge_or_open_exposed", "bare_rock_exposed", "scree_exposed", "unstable_exposed", "cliff_exposed"]:
        hints.append("wind_exposed_terrain")

    if moisture in ["near_water_or_drainage", "wetland_or_saturated", "shaded_retains_moisture"]:
        hints.append("moisture_retaining_terrain")

    if slip in ["steps_slip_sensitive", "rock_slip_sensitive", "loose_surface_slip_sensitive"]:
        hints.append("wet_slip_sensitive_surface")

    if not hints:
        return "general_microclimate"

    return "|".join(hints)


# =========================================================
# G. Main feature extraction
# =========================================================
def build_features(df):
    out = df.copy()

    # normalize boolean-like columns used by classifiers
    bool_like_cols = [
        "near_cliff",
        "near_bare_rock",
        "near_scree",
        "near_landslide",
        "near_waterway",
        "near_water_area",
        "near_wetland",
        "near_handrail",
        "near_safety_rope",
    ]

    for c in bool_like_cols:
        if c in out.columns:
            out[c] = bool_col(out, c)

    dist_col = choose_first_existing_col(
        out,
        ["dist_m", "dist_mid", "distance_m", "cumdist_m", "cum_dist_m"],
        default_name=None,
    )
    if dist_col is None:
        raise KeyError("找不到距離欄位 dist_m / dist_mid / distance_m / cumdist_m")

    ele_col = choose_first_existing_col(
        out,
        ["ele_smooth", "ele_gpx_m", "ele_gpx_m_terrain", "elev_max", "elev_min"],
        default_name=None,
    )
    if ele_col is None:
        raise KeyError("找不到海拔欄位 ele_smooth / ele_gpx_m / ele_gpx_m_terrain")

    slope_col = choose_first_existing_col(
        out,
        ["slope_pct", "slope_gpx_window_smooth", "slope_gpx_window", "slope_window", "slope_final"],
        default_name=None,
    )

    gain_col = choose_first_existing_col(
        out,
        ["cum_gain_m", "gain_m"],
        default_name=None,
    )

    out["dist_m_microclimate"] = pd.to_numeric(out[dist_col], errors="coerce")
    out["ele_m_microclimate"] = pd.to_numeric(out[ele_col], errors="coerce")

    if slope_col is not None:
        out["slope_pct_microclimate"] = pd.to_numeric(out[slope_col], errors="coerce")
    else:
        out["slope_pct_microclimate"] = np.nan

    if gain_col is not None:
        out["cum_gain_m_microclimate"] = pd.to_numeric(out[gain_col], errors="coerce")
    else:
        out["cum_gain_m_microclimate"] = np.nan

    # classification
    out["altitude_regime"] = out["ele_m_microclimate"].apply(classify_altitude_regime)
    out["slope_regime"] = out["slope_pct_microclimate"].apply(classify_slope_regime)

    out["route_exposure_class"] = out.apply(classify_route_exposure, axis=1)
    out["terrain_moisture_retention_class"] = out.apply(classify_moisture_retention, axis=1)
    out["surface_wet_slip_class"] = out.apply(classify_surface_slip, axis=1)

    # factors
    out["altitude_thermal_amplifier"] = out["ele_m_microclimate"].apply(altitude_thermal_amplifier)

    out["altitude_load_factor"] = [
        altitude_load_factor(ele, gain)
        for ele, gain in zip(
            out["ele_m_microclimate"],
            out["cum_gain_m_microclimate"],
        )
    ]

    out["slope_load_factor"] = out["slope_pct_microclimate"].apply(slope_load_factor)

    out["ridge_exposure_factor"] = out["route_exposure_class"].apply(exposure_factor_from_class)
    out["wind_exposure_factor_terrain"] = out["ridge_exposure_factor"]

    out["valley_humidity_retention_factor"] = out[
        "terrain_moisture_retention_class"
    ].apply(moisture_retention_factor_from_class)

    out["surface_wet_slip_sensitivity"] = out["surface_wet_slip_class"].apply(slip_factor_from_class)

    out["support_reduction_factor"] = out.apply(support_reduction_factor, axis=1)

    # combined terrain microclimate factor
    raw_factor = (
        0.25 * out["altitude_thermal_amplifier"]
        + 0.20 * out["slope_load_factor"]
        + 0.25 * out["ridge_exposure_factor"]
        + 0.20 * out["valley_humidity_retention_factor"]
        + 0.25 * out["surface_wet_slip_sensitivity"]
        - 0.15 * out["support_reduction_factor"]
    )

    out["terrain_microclimate_factor"] = clamp_series(raw_factor, 0.0, 1.0)

    # route-weather interaction hint
    out["microclimate_interaction_hint"] = out.apply(
        build_microclimate_interaction_hint,
        axis=1,
    )

    # keep output focused but still useful
    preferred_cols = [
        "sample_idx",
        "dist_m",
        "dist_mid",
        "dist_m_microclimate",
        "lat",
        "lon",
        "ele_smooth",
        "ele_gpx_m",
        "ele_m_microclimate",
        "slope_pct",
        "slope_final",
        "slope_pct_microclimate",
        "cum_gain_m",
        "cum_gain_m_microclimate",

        "altitude_regime",
        "slope_regime",
        "route_exposure_class",
        "terrain_moisture_retention_class",
        "surface_wet_slip_class",

        "altitude_thermal_amplifier",
        "altitude_load_factor",
        "slope_load_factor",
        "ridge_exposure_factor",
        "wind_exposure_factor_terrain",
        "valley_humidity_retention_factor",
        "surface_wet_slip_sensitivity",
        "support_reduction_factor",
        "terrain_microclimate_factor",
        "microclimate_interaction_hint",

        "near_cliff",
        "near_bare_rock",
        "near_scree",
        "near_landslide",
        "near_waterway",
        "near_water_area",
        "near_wetland",
        "near_handrail",
        "near_safety_rope",

        "surface_class",
        "route_semantic_class",
        "hazard_flags",
        "hydrology_flags",
        "technical_flags",
        "support_flags",
        "osm_highway",
        "osm_surface",
        "osm_vertical_context",
        "risk_score",
        "risk_band",
        "environment_adjusted_risk_score",
        "environment_adjusted_risk_band",
    ]

    existing_cols = [c for c in preferred_cols if c in out.columns]

    # append other useful columns if not already selected
    extra_cols = [
        c for c in out.columns
        if c not in existing_cols
        and c.startswith(("near_", "osm_", "risk_", "weather_", "hydro_"))
    ]

    return out[existing_cols + extra_cols]


# =========================================================
# H. Summary
# =========================================================
def summarize_features(features):
    rows = []

    def add_counts(col):
        if col not in features.columns:
            return
        counts = features[col].value_counts(dropna=False)
        total = len(features)

        for k, v in counts.items():
            rows.append(
                {
                    "metric": f"{col}_count",
                    "class": k,
                    "count": int(v),
                    "ratio": float(v / total) if total > 0 else np.nan,
                }
            )

    for col in [
        "altitude_regime",
        "slope_regime",
        "route_exposure_class",
        "terrain_moisture_retention_class",
        "surface_wet_slip_class",
        "microclimate_interaction_hint",
    ]:
        add_counts(col)

    for col in [
        "altitude_thermal_amplifier",
        "altitude_load_factor",
        "slope_load_factor",
        "ridge_exposure_factor",
        "wind_exposure_factor_terrain",
        "valley_humidity_retention_factor",
        "surface_wet_slip_sensitivity",
        "terrain_microclimate_factor",
    ]:
        if col in features.columns:
            s = pd.to_numeric(features[col], errors="coerce")
            rows.append(
                {
                    "metric": f"{col}_summary",
                    "class": "mean",
                    "count": len(s),
                    "ratio": s.mean(),
                }
            )
            rows.append(
                {
                    "metric": f"{col}_summary",
                    "class": "max",
                    "count": len(s),
                    "ratio": s.max(),
                }
            )

    return pd.DataFrame(rows)


# =========================================================
# I. Main
# =========================================================

def main():
    input_csv = find_route_input()
    print("scenario:", SCENARIO_NAME)
    print("route microclimate input:", input_csv.resolve())

    df = normalize_columns(pd.read_csv(input_csv))

    if df.empty:
        raise ValueError(f"輸入 CSV 為空：{input_csv}")

    print("\n=== slope candidate summary ===")
    for c in ["slope_final", "slope_pct", "slope_gpx_window_smooth", "slope_gpx_window", "slope_window"]:
        if c in df.columns:
            s = pd.to_numeric(df[c], errors="coerce")
            print(
                f"{c}: "
                f"count={s.notna().sum()}, "
                f"mean={s.mean():.3f}, "
                f"min={s.min():.3f}, "
                f"p25={s.quantile(0.25):.3f}, "
                f"p50={s.quantile(0.50):.3f}, "
                f"p75={s.quantile(0.75):.3f}, "
                f"max={s.max():.3f}"
            )


    features = build_features(df)
    summary = summarize_features(features)

    features.to_csv(OUT_FEATURES_CSV, index=False, encoding="utf-8-sig")
    summary.to_csv(OUT_SUMMARY_CSV, index=False, encoding="utf-8-sig")

    print("\n完成！")
    print("features CSV:", OUT_FEATURES_CSV.resolve())
    print("summary CSV:", OUT_SUMMARY_CSV.resolve())

    print("\n=== input ===")
    print(input_csv.resolve())

    print("\n=== feature columns ===")
    print(list(features.columns))

    print("\n=== key class counts ===")
    for col in [
        "altitude_regime",
        "slope_regime",
        "route_exposure_class",
        "terrain_moisture_retention_class",
        "surface_wet_slip_class",
        "microclimate_interaction_hint",
    ]:
        if col in features.columns:
            print(f"\n[{col}]")
            print(features[col].value_counts(dropna=False).to_string())

    print("\n=== key factor summary ===")
    for col in [
        "altitude_thermal_amplifier",
        "altitude_load_factor",
        "slope_load_factor",
        "ridge_exposure_factor",
        "wind_exposure_factor_terrain",
        "valley_humidity_retention_factor",
        "surface_wet_slip_sensitivity",
        "terrain_microclimate_factor",
    ]:
        if col in features.columns:
            s = pd.to_numeric(features[col], errors="coerce")
            print(
                f"{col}: "
                f"mean={s.mean():.3f}, "
                f"min={s.min():.3f}, "
                f"max={s.max():.3f}"
            )


if __name__ == "__main__":
    main()