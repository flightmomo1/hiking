# -*- coding: utf-8 -*-
from pathlib import Path
from datetime import datetime, timezone
import os

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CASE_ID = os.environ.get("CASE_ID", "qixing_xiaoyoukeng_main_peak_20260315")
CASE_NAME = os.environ.get("CASE_NAME", CASE_ID)
RISK_MODEL_VERSION = "terrain_dominant_from_ib1e_v0.4"


def first_existing(candidates, label):
    for fp in candidates:
        if fp.exists():
            print(f"{label}: {fp}")
            return fp
    raise FileNotFoundError(
        f"Missing {label}. Tried:\n" + "\n".join(str(fp) for fp in candidates)
    )


INPUT_CSV = first_existing(
    [
        PROJECT_ROOT
        / "outputs"
        / "ib1e_route_profile_contour_window_terrain"
        / CASE_ID
        / f"{CASE_ID}_route_profile_contour_window_terrain_enriched.csv",
        PROJECT_ROOT
        / "outputs"
        / "ib1e_osm_nlsc_terrain_risk"
        / CASE_ID
        / f"{CASE_ID}_osm_nlsc_terrain_risk_profile.csv",
    ],
    "input CSV",
)

OUT_DIR = PROJECT_ROOT / "outputs" / "ib2_v2_route_risk" / CASE_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_CSV = OUT_DIR / f"{CASE_ID}_route_risk_v2.csv"


def norm_text(v):
    if pd.isna(v):
        return ""
    text = str(v).strip().lower()
    return "" if text in {"", "nan", "none", "<na>", "null"} else text


def split_flags(value):
    text = norm_text(value)
    if not text or text == "normal":
        return []
    return [x.strip() for x in text.split("|") if x.strip()]


def band_from_01(score):
    if pd.isna(score):
        return "unknown"
    score = float(score)
    if score < 0.20:
        return "low"
    if score < 0.40:
        return "moderate"
    if score < 0.65:
        return "high"
    return "very_high"


def build_reason(row):
    reasons = []
    for col in [
        "technical_flags",
        "hazard_flags",
        "hydrology_flags",
        "weather_sensitive_flags",
        "conditional_factor_flags",
    ]:
        reasons.extend(split_flags(row.get(col, "")))

    for score_col, label in [
        ("terrain_window_risk_score", "terrain_window"),
        ("hydro_terrain_amplifier_score", "hydro_terrain"),
        ("osm_semantic_risk_score", "osm_semantic"),
    ]:
        if float(row.get(score_col, 0) or 0) >= 0.40:
            reasons.append(label)

    if not bool(row.get("route_data_ok", True)):
        reasons.append("route_data_quality")

    seen = []
    for item in reasons:
        if item and item not in seen:
            seen.append(item)
    return "|".join(seen) if seen else "normal"


def main():
    df = pd.read_csv(INPUT_CSV, low_memory=False, encoding="utf-8-sig")
    if df.empty:
        raise ValueError(f"Empty input: {INPUT_CSV}")
    if "dist_m" not in df.columns:
        raise KeyError("input CSV must contain dist_m")

    df = df.sort_values("dist_m").reset_index(drop=True)

    required_scores = [
        "osm_semantic_risk_score",
        "terrain_window_risk_score",
        "hydro_terrain_amplifier_score",
        "osm_terrain_combined_risk_score",
    ]
    for col in required_scores:
        if col not in df.columns:
            raise KeyError(f"input CSV missing score column: {col}")
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).clip(0, 1)

    if "osm_terrain_combined_risk_band" in df.columns:
        df["risk_band"] = df["osm_terrain_combined_risk_band"].map(norm_text)
    else:
        df["risk_band"] = df["osm_terrain_combined_risk_score"].apply(band_from_01)
    df["risk_band"] = df["risk_band"].where(df["risk_band"].ne(""), "unknown")

    df["risk_score"] = df["osm_terrain_combined_risk_score"]
    df["risk_score_raw"] = pd.to_numeric(
        df.get("osm_terrain_combined_risk_score_raw", df["risk_score"]),
        errors="coerce",
    ).fillna(df["risk_score"])
    df["risk_score_smooth"] = (
        df["risk_score"].rolling(9, center=True, min_periods=2).mean()
    )

    df["effort_score"] = pd.to_numeric(
        df.get("terrain_window_risk_score", 0), errors="coerce"
    ).fillna(0)
    df["exposure_score"] = (
        0.65
        * pd.to_numeric(df.get("hydro_terrain_amplifier_score", 0), errors="coerce").fillna(0)
        + 0.35
        * pd.to_numeric(df.get("terrain_window_risk_score", 0), errors="coerce").fillna(0)
    ).clip(0, 1)
    df["terrain_score"] = df["effort_score"]

    slope_col = next(
        (c for c in ["slope_band_window_nlsc", "terrain_slope_band_window", "slope_band"] if c in df.columns),
        None,
    )
    df["effort_slope_band"] = df[slope_col].map(norm_text) if slope_col else "unknown"
    df["terrain_exposure_band"] = df["effort_slope_band"]
    df["slope_final_band"] = df["effort_slope_band"]

    if "dist_to_contour_window_mid_m" in df.columns:
        align_diff = pd.to_numeric(df["dist_to_contour_window_mid_m"], errors="coerce").abs()
        df["dist_alignment_diff_m"] = align_diff
        df["alignment_ok"] = align_diff <= 10.0
    else:
        df["dist_alignment_diff_m"] = 0.0
        df["alignment_ok"] = True

    if "contour_window_match_status" in df.columns:
        df["within_validation_range"] = df["contour_window_match_status"].astype(str).eq("matched")
    else:
        df["within_validation_range"] = True

    df["route_data_ok"] = df["alignment_ok"].astype(bool) & df["within_validation_range"].astype(bool)
    df["gpx_quality_flag"] = np.where(df["route_data_ok"], "ok", "mismatch")
    df["risk_confidence"] = np.where(df["route_data_ok"], "normal", "low_data_quality")
    df["data_quality_reason"] = np.where(df["route_data_ok"], "normal", "contour_window_alignment")
    df["risk_reason"] = df.apply(build_reason, axis=1)

    df["case_id"] = CASE_ID
    df["case_name"] = CASE_NAME
    df["risk_model_version"] = RISK_MODEL_VERSION
    df["risk_scored_at"] = datetime.now(timezone.utc).isoformat()
    df["pipeline_stage"] = "ib2_v2_route_risk_scoring"
    df["ib2_input_csv"] = str(INPUT_CSV)

    df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    print("case:", CASE_ID)
    print("rows:", len(df))
    print("CSV:", OUT_CSV)
    print("\n=== risk_band ===")
    print(df["risk_band"].value_counts(dropna=False))
    print("\n=== score min/mean/max ===")
    print(df["risk_score"].min(), df["risk_score"].mean(), df["risk_score"].max())
    print("\n=== route_data_ok ===")
    print(df["route_data_ok"].value_counts(dropna=False))


if __name__ == "__main__":
    main()
