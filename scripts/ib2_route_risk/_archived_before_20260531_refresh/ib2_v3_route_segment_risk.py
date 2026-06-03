# -*- coding: utf-8 -*-
from pathlib import Path
import os

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CASE_ID = os.environ.get("CASE_ID", "qixing_xiaoyoukeng_main_peak_20260315")
SEGMENT_SIZE_M = float(os.environ.get("SEGMENT_SIZE_M", "100"))

INPUT_CSV = (
    PROJECT_ROOT
    / "outputs"
    / "ib2_v2_route_risk"
    / CASE_ID
    / f"{CASE_ID}_route_risk_v2.csv"
)
OUT_DIR = PROJECT_ROOT / "outputs" / "ib2_v3_route_segment_risk" / CASE_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_CSV = OUT_DIR / f"{CASE_ID}_route_segment_risk_{int(SEGMENT_SIZE_M)}m.csv"

RISK_LEVEL = {"unknown": 0, "low": 1, "moderate": 2, "high": 3, "very_high": 4}


def norm_band(v):
    if pd.isna(v):
        return "unknown"
    s = str(v).strip().lower()
    return s if s in RISK_LEVEL else "unknown"


def dominant_value(series):
    s = series.dropna().astype(str)
    if s.empty:
        return "unknown"
    return s.value_counts().idxmax()


def highest_band(series):
    bands = [norm_band(v) for v in series]
    return max(bands, key=lambda b: RISK_LEVEL.get(b, 0)) if bands else "unknown"


def join_unique_flags(series):
    items = []
    for v in series.dropna().astype(str):
        if v in {"", "none", "normal", "nan"}:
            continue
        for part in v.split("|"):
            part = part.strip()
            if part and part not in items:
                items.append(part)
    return "|".join(items) if items else "normal"


def main():
    if not INPUT_CSV.exists():
        raise FileNotFoundError(INPUT_CSV)
    df = pd.read_csv(INPUT_CSV, low_memory=False, encoding="utf-8-sig")
    if df.empty:
        raise ValueError(f"Empty input: {INPUT_CSV}")
    for col in ["dist_m", "risk_score", "risk_band"]:
        if col not in df.columns:
            raise KeyError(f"missing required column: {col}")

    df = df.sort_values("dist_m").reset_index(drop=True)
    df["risk_band"] = df["risk_band"].map(norm_band)
    df["risk_segment_id"] = np.floor(df["dist_m"] / SEGMENT_SIZE_M).astype(int)

    route_start = float(df["dist_m"].min())
    route_end = float(df["dist_m"].max())

    agg = {
        "dist_m": ["min", "max", "count"],
        "risk_score": ["mean", "max", "median"],
    }
    for col in [
        "risk_score_smooth",
        "effort_score",
        "exposure_score",
        "terrain_score",
        "osm_semantic_risk_score",
        "terrain_window_risk_score",
        "hydro_terrain_amplifier_score",
    ]:
        if col in df.columns:
            agg[col] = ["mean", "max"]

    grouped = df.groupby("risk_segment_id").agg(agg)
    grouped.columns = [
        "_".join([x for x in col if x]).strip("_")
        for col in grouped.columns.to_flat_index()
    ]
    grouped = grouped.reset_index()

    grouped["segment_start_m"] = grouped["risk_segment_id"] * SEGMENT_SIZE_M
    grouped["segment_end_m"] = np.minimum(grouped["segment_start_m"] + SEGMENT_SIZE_M, route_end)
    grouped["segment_mid_m"] = (grouped["segment_start_m"] + grouped["segment_end_m"]) / 2
    grouped["points_n"] = grouped["dist_m_count"]
    grouped["segment_valid"] = grouped["segment_start_m"] <= route_end
    grouped["valid_route_start_m"] = route_start
    grouped["valid_route_end_m"] = route_end

    grouped["segment_risk_score"] = grouped["risk_score_max"]
    grouped["segment_risk_score_mean"] = grouped["risk_score_mean"]

    band_df = (
        df.groupby("risk_segment_id")["risk_band"]
        .apply(highest_band)
        .reset_index()
        .rename(columns={"risk_band": "segment_risk_band"})
    )
    grouped = grouped.merge(band_df, on="risk_segment_id", how="left")

    for col in [
        "risk_band",
        "effort_slope_band",
        "terrain_exposure_band",
        "slope_final_band",
        "gpx_quality_flag",
        "risk_confidence",
        "route_semantic_class",
        "surface_class",
    ]:
        if col in df.columns:
            tmp = df.groupby("risk_segment_id")[col].apply(dominant_value).reset_index()
            grouped = grouped.merge(
                tmp.rename(columns={col: f"{col}_dominant"}),
                on="risk_segment_id",
                how="left",
            )

    for col in [
        "risk_reason",
        "data_quality_reason",
        "technical_flags",
        "hazard_flags",
        "hydrology_flags",
        "facility_flags",
        "support_flags",
        "weather_sensitive_flags",
    ]:
        if col in df.columns:
            tmp = df.groupby("risk_segment_id")[col].apply(join_unique_flags).reset_index()
            grouped = grouped.merge(
                tmp.rename(columns={col: f"{col}_merged"}),
                on="risk_segment_id",
                how="left",
            )

    if "route_data_ok" in df.columns:
        bad = (
            df.assign(route_data_bad=(~df["route_data_ok"].astype(bool)).astype(float))
            .groupby("risk_segment_id")["route_data_bad"]
            .mean()
            .reset_index()
            .rename(columns={"route_data_bad": "route_data_bad_ratio"})
        )
        grouped = grouped.merge(bad, on="risk_segment_id", how="left")
    else:
        grouped["route_data_bad_ratio"] = 0.0

    grouped["case_id"] = CASE_ID
    grouped["segment_size_m"] = SEGMENT_SIZE_M
    grouped["ib2_input_csv"] = str(INPUT_CSV)
    grouped = grouped.sort_values("segment_start_m").reset_index(drop=True)
    grouped.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    print("case:", CASE_ID)
    print("CSV:", OUT_CSV)
    print("segments:", len(grouped))
    print(grouped["segment_risk_band"].value_counts(dropna=False))


if __name__ == "__main__":
    main()
