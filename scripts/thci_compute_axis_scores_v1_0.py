# -*- coding: utf-8 -*-
"""Compute deterministic THCI v1.0 axis scores.

This script intentionally uses only fixed CSV configs and local pipeline
outputs. It does not call any runtime LLM or perform batch min-max
normalization.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(r"D:\mountain_work\115_osm")

CASES = [
    "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b",
    "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b",
    "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b",
    "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b",
]

AXES = [
    "physical_difficulty_score",
    "technical_difficulty_score",
    "baseline_hazard_score",
    "navigation_risk_score",
    "support_difficulty_score",
    "weather_impact_score",
]

CONFIG_PATHS = {
    "axis_definition": PROJECT_ROOT
    / "configs"
    / "risk_semantics"
    / "thci_axis_definition_v1_2_support_updated.csv",
    "feature_mapping": PROJECT_ROOT
    / "configs"
    / "risk_semantics"
    / "thci_feature_mapping_v1_3_support_updated.csv",
    "axis_scoring_rule": PROJECT_ROOT
    / "configs"
    / "risk_semantics"
    / "thci_axis_scoring_rule_v1_2_support_updated.csv",
    "normalization_threshold": PROJECT_ROOT
    / "configs"
    / "risk_semantics"
    / "thci_normalization_threshold_v1_2_support_updated.csv",
}

INPUT_ROOTS = {
    "ib1a": PROJECT_ROOT / "outputs" / "ib1_route_profile_v1_3b_contract_qa",
    "ib1c": PROJECT_ROOT
    / "outputs"
    / "ib1c_route_profile_semantics_v1_3b_contract_qa",
    "ib1e": PROJECT_ROOT
    / "outputs"
    / "ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa",
}

OUT_ROOT = PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_0"


def clip01(x: Any) -> float | None:
    """Clip numeric value to 0..1, preserving None for unavailable values."""
    if x is None:
        return None
    try:
        if pd.isna(x):
            return None
        return float(min(1.0, max(0.0, float(x))))
    except (TypeError, ValueError):
        return None


def load_config_bundle() -> dict[str, Any]:
    """Read all THCI v1.0 config CSV files."""
    missing = [str(path) for path in CONFIG_PATHS.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing THCI config files: " + "; ".join(missing))

    bundle = {name: pd.read_csv(path, low_memory=False) for name, path in CONFIG_PATHS.items()}
    rules = bundle["axis_scoring_rule"]
    if "runtime_llm_allowed" in rules.columns:
        allowed = rules["runtime_llm_allowed"].astype(str).str.lower().isin(["true", "1", "yes"])
        if bool(allowed.any()):
            raise ValueError("THCI v1.0 scoring forbids runtime LLM rules.")
    bundle["config_paths"] = {name: str(path) for name, path in CONFIG_PATHS.items()}
    return bundle


def _threshold_lookup(threshold_df: pd.DataFrame, feature_name: str, source_key: str = "") -> pd.Series | None:
    if threshold_df.empty:
        return None
    if "feature_name" in threshold_df.columns:
        rows = threshold_df[threshold_df["feature_name"].astype(str).eq(feature_name)]
        if not rows.empty:
            return rows.iloc[0]
    if source_key and "source_key" in threshold_df.columns:
        rows = threshold_df[threshold_df["source_key"].astype(str).eq(source_key)]
        if not rows.empty:
            return rows.iloc[0]
    return None


def piecewise_linear_score(value: float | int | None, thresholds: pd.Series | dict[str, Any] | None) -> float | None:
    """Score a value using fixed score_0..score_1 threshold breakpoints."""
    if value is None or thresholds is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(v):
        return None

    points = [
        (0.0, float(thresholds["score_0"])),
        (0.25, float(thresholds["score_0_25"])),
        (0.50, float(thresholds["score_0_50"])),
        (0.75, float(thresholds["score_0_75"])),
        (1.0, float(thresholds["score_1"])),
    ]
    points = sorted(points, key=lambda item: item[1])

    if v <= points[0][1]:
        raw = points[0][0]
    elif v >= points[-1][1]:
        raw = points[-1][0]
    else:
        raw = 0.0
        for (score_a, value_a), (score_b, value_b) in zip(points[:-1], points[1:]):
            if value_a <= v <= value_b:
                if value_b == value_a:
                    raw = score_b
                else:
                    ratio = (v - value_a) / (value_b - value_a)
                    raw = score_a + ratio * (score_b - score_a)
                break

    direction = str(thresholds.get("direction", "higher_is_riskier")).strip().lower()
    if direction == "lower_is_riskier":
        raw = 1.0 - raw
    return clip01(raw)


def _read_case_inputs(case_id: str) -> dict[str, pd.DataFrame]:
    fps = {
        "ib1a": INPUT_ROOTS["ib1a"] / case_id / f"{case_id}_route_profile.csv",
        "ib1c": INPUT_ROOTS["ib1c"] / case_id / f"{case_id}_route_profile_semantic_enriched.csv",
        "ib1e": INPUT_ROOTS["ib1e"]
        / case_id
        / f"{case_id}_route_profile_contour_window_terrain_enriched.csv",
    }
    missing = [str(path) for path in fps.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing THCI case inputs: " + "; ".join(missing))
    return {name: pd.read_csv(path, low_memory=False) for name, path in fps.items()}


def _last_numeric(df: pd.DataFrame, col: str) -> float | None:
    if col not in df.columns:
        return None
    vals = pd.to_numeric(df[col], errors="coerce").dropna()
    if vals.empty:
        return None
    return float(vals.iloc[-1])


def compute_physical_score(
    route_profile: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[float, dict[str, Any]]:
    """Compute physical_difficulty_score from IB1A fixed-threshold features."""
    threshold_df = config["normalization_threshold"]
    missing_features: list[str] = []

    dist_m = _last_numeric(route_profile, "dist_m")
    cum_gain_m = _last_numeric(route_profile, "cum_gain_m")
    cum_loss_m = _last_numeric(route_profile, "cum_loss_m")

    slope = pd.to_numeric(route_profile.get("slope_pct"), errors="coerce")
    if len(slope.dropna()) == 0:
        steep_slope_ratio = None
        missing_features.append("slope_pct")
    else:
        steep_slope_ratio = float((slope.abs() >= 20.0).mean())

    if dist_m is None:
        missing_features.append("dist_m")
    if cum_gain_m is None:
        missing_features.append("cum_gain_m")
    if cum_loss_m is None:
        missing_features.append("cum_loss_m")

    distance_score = piecewise_linear_score(
        None if dist_m is None else dist_m / 1000.0,
        _threshold_lookup(threshold_df, "route_distance_km", "dist_m"),
    )
    gain_score = piecewise_linear_score(
        cum_gain_m,
        _threshold_lookup(threshold_df, "cumulative_gain_m", "cum_gain_m"),
    )
    loss_score = piecewise_linear_score(
        cum_loss_m,
        _threshold_lookup(threshold_df, "cumulative_loss_m", "cum_loss_m"),
    )
    steep_score = piecewise_linear_score(
        steep_slope_ratio,
        _threshold_lookup(threshold_df, "steep_slope_ratio", "slope_pct"),
    )

    sustained_climb_or_stairs_score = 0.0
    missing_features.append("sustained_climb_or_stairs_score")

    components = {
        "distance_score": distance_score,
        "cum_gain_score": gain_score,
        "cum_loss_score": loss_score,
        "steep_slope_score": steep_score,
        "sustained_climb_or_stairs_score": sustained_climb_or_stairs_score,
    }
    score = (
        0.30 * (distance_score or 0.0)
        + 0.30 * (gain_score or 0.0)
        + 0.15 * (loss_score or 0.0)
        + 0.15 * (steep_score or 0.0)
        + 0.10 * sustained_climb_or_stairs_score
    )

    detail = {
        "source": "ib1a_route_profile",
        "raw_features": {
            "route_distance_m": dist_m,
            "route_distance_km": None if dist_m is None else dist_m / 1000.0,
            "cum_gain_m": cum_gain_m,
            "cum_loss_m": cum_loss_m,
            "steep_slope_ratio": steep_slope_ratio,
        },
        "component_scores": components,
        "formula_used": "0.30 distance + 0.30 cum_gain + 0.15 cum_loss + 0.15 steep_slope_ratio + 0.10 sustained_climb_or_stairs_score",
        "missing_features": sorted(set(missing_features)),
    }
    return clip01(score) or 0.0, detail


def _candidate_columns(source_key: str) -> list[str]:
    aliases = {
        "highway": ["osm_highway", "osm_highway_family", "route_semantic_class"],
        "surface": ["osm_surface", "surface_class"],
        "sac_scale": ["osm_sac_scale", "osm_difficulty_class"],
        "trail_visibility": ["osm_trail_visibility", "visibility_class"],
        "natural": ["near_cliff", "hazard_flags"],
        "landslide_or_debris_flow": ["near_landslide", "hazard_flags"],
        "dip_slope": ["dip_slope", "near_dip_slope"],
        "junction_density": ["junction_density"],
        "return_difficulty": ["return_difficulty"],
        "shelter": ["near_shelter", "facility_flags"],
        "road_access_distance": ["road_access_distance"],
        "gps_blockage_or_drift": ["gps_blockage", "gps_drift", "gps_blockage_or_drift"],
        "water_crossing": ["osm_ford", "near_waterway", "hydrology_flags"],
        "exposed_ridge": ["exposed_ridge", "near_exposed_ridge"],
    }
    cols = aliases.get(source_key, [])
    return [source_key, f"osm_{source_key}", f"near_{source_key}", f"{source_key}_flags", *cols]


def _row_weights(df: pd.DataFrame) -> pd.Series:
    if "delta_dist_m" in df.columns:
        weights = pd.to_numeric(df["delta_dist_m"], errors="coerce").fillna(1.0).abs()
        weights = weights.replace(0, 1.0)
        return weights
    return pd.Series(1.0, index=df.index)


def _normal_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    if text in {"", "nan", "none", "<na>", "na", "null"}:
        return ""
    return text


def _presence_series(df: pd.DataFrame, col: str, source_values: list[str]) -> pd.Series:
    series = df[col]
    if pd.api.types.is_numeric_dtype(series):
        vals = pd.to_numeric(series, errors="coerce").fillna(0)
        if col.startswith("near_") or col.startswith("has_"):
            return (vals > 0).astype(float)
        if source_values and "*" not in source_values:
            numeric_wanted = [pd.to_numeric(v, errors="coerce") for v in source_values]
            numeric_wanted = [v for v in numeric_wanted if not pd.isna(v)]
            if numeric_wanted:
                return vals.isin(numeric_wanted).astype(float)
            return (vals > 0).astype(float)
        return (vals > 0).astype(float)

    wanted = {v.strip().lower() for v in source_values if v.strip()}
    if not wanted or wanted == {"*"}:
        return series.map(lambda v: 1.0 if _normal_text(v) not in {"", "normal", "none", "no", "0", "false"} else 0.0)

    def matches(value: Any) -> float:
        text = _normal_text(value)
        if not text:
            return 0.0
        tokens = {t.strip() for t in text.replace(";", "|").split("|") if t.strip()}
        tokens.add(text)
        if "near" in wanted and any(t not in {"", "normal", "none"} for t in tokens):
            return 1.0
        return 1.0 if tokens.intersection(wanted) else 0.0

    return series.map(matches)


def _weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    valid = values.notna()
    if not bool(valid.any()):
        return 0.0
    v = pd.to_numeric(values[valid], errors="coerce").fillna(0.0)
    w = pd.to_numeric(weights[valid], errors="coerce").fillna(1.0)
    denom = float(w.sum())
    if denom <= 0:
        return float(v.mean())
    return float((v * w).sum() / denom)


def compute_mapping_axis_score(
    axis_id: str,
    frames: dict[str, pd.DataFrame],
    config: dict[str, Any],
) -> tuple[float, dict[str, Any]]:
    """Compute a non-physical axis from THCI feature mapping rows."""
    mapping = config["feature_mapping"]
    axis_mapping = mapping[mapping["primary_axis"].astype(str).eq(axis_id)].copy()
    if axis_mapping.empty:
        return 0.0, {"missing_features": [f"{axis_id}:no_mapping_rows"], "feature_details": []}

    df = frames["ib1e"] if "ib1e" in frames else frames.get("ib1c")
    if df is None or df.empty:
        return 0.0, {"missing_features": [f"{axis_id}:input_dataframe"], "feature_details": []}

    weights = _row_weights(df)
    weighted_sum = 0.0
    total_weight = 0.0
    missing_features: list[str] = []
    feature_details: list[dict[str, Any]] = []

    for _, row in axis_mapping.iterrows():
        source_key = str(row.get("source_key", "")).strip()
        source_value_raw = str(row.get("source_value", "*")).strip()
        source_values = [v.strip().lower() for v in source_value_raw.split("|") if v.strip()]
        effect = str(row.get("effect_direction", "increase")).strip().lower()
        base_weight = float(pd.to_numeric(row.get("base_weight", 0), errors="coerce") or 0.0)
        base_score = float(pd.to_numeric(row.get("base_score", 0), errors="coerce") or 0.0)

        found_col = None
        for col in dict.fromkeys(_candidate_columns(source_key)):
            if col in df.columns:
                found_col = col
                break

        if found_col is None:
            missing_features.append(source_key)
            feature_details.append(
                {
                    "mapping_id": row.get("mapping_id", ""),
                    "source_key": source_key,
                    "source_value": source_value_raw,
                    "status": "missing_column",
                    "candidate_columns": _candidate_columns(source_key),
                }
            )
            continue

        presence = _presence_series(df, found_col, source_values)
        presence_ratio = _weighted_mean(presence, weights)
        max_presence = float(pd.to_numeric(presence, errors="coerce").max())

        if effect == "decrease":
            contribution = (1.0 - presence_ratio) * abs(base_score)
        else:
            # Rare hazards should not be diluted too aggressively.
            hint = str(row.get("aggregation_hint", "")).lower()
            aggregate_presence = max_presence if "max" in hint or "presence" in hint else presence_ratio
            contribution = aggregate_presence * abs(base_score)

        weighted_sum += base_weight * contribution
        total_weight += abs(base_weight)
        feature_details.append(
            {
                "mapping_id": row.get("mapping_id", ""),
                "source_key": source_key,
                "source_value": source_value_raw,
                "matched_column": found_col,
                "effect_direction": effect,
                "base_weight": base_weight,
                "base_score": base_score,
                "presence_ratio": clip01(presence_ratio),
                "max_presence": clip01(max_presence),
                "contribution": clip01(contribution),
                "status": "used",
            }
        )

    score = 0.0 if total_weight <= 0 else weighted_sum / total_weight
    detail = {
        "source": "ib1e_enriched_profile",
        "mapping_rows": int(len(axis_mapping)),
        "used_feature_count": len([x for x in feature_details if x.get("status") == "used"]),
        "missing_features": sorted(set(missing_features)),
        "feature_details": feature_details,
        "aggregation_method": "weighted deterministic draft using presence or length-weighted mean",
    }
    return clip01(score) or 0.0, detail


def compute_case_scores(case_id: str, config: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Compute all six THCI v1.0 axis scores for one case."""
    frames = _read_case_inputs(case_id)

    scores: dict[str, float] = {}
    details: dict[str, Any] = {}
    missing_features: dict[str, list[str]] = {}

    physical_score, physical_detail = compute_physical_score(frames["ib1a"], config)
    scores["physical_difficulty_score"] = physical_score
    details["physical_difficulty_score"] = physical_detail
    missing_features["physical_difficulty_score"] = physical_detail["missing_features"]

    for axis_id in AXES:
        if axis_id == "physical_difficulty_score":
            continue
        score, detail = compute_mapping_axis_score(axis_id, frames, config)
        scores[axis_id] = score
        details[axis_id] = detail
        missing_features[axis_id] = detail["missing_features"]

    row = {"case_id": case_id, **{axis: scores.get(axis, 0.0) for axis in AXES}}
    out_df = pd.DataFrame([row])

    summary = {
        "case_id": case_id,
        "thci_version": "v1.0",
        "scoring_mode": "deterministic_config_only_no_runtime_llm",
        "config_paths": config["config_paths"],
        "input_roots": {name: str(path) for name, path in INPUT_ROOTS.items()},
        "output_root": str(OUT_ROOT),
        "axis_scores": {axis: scores.get(axis, 0.0) for axis in AXES},
        "missing_features": missing_features,
        "axis_details": details,
    }
    return out_df, summary


def write_case_outputs(case_id: str, case_scores: pd.DataFrame, summary: dict[str, Any]) -> None:
    """Write per-case THCI CSV and JSON outputs."""
    out_dir = OUT_ROOT / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    case_scores.to_csv(out_dir / f"{case_id}_thci_axis_scores_v1_0.csv", index=False, encoding="utf-8-sig")
    (out_dir / f"{case_id}_thci_axis_score_summary_v1_0.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_batch_summary(case_rows: list[pd.DataFrame]) -> None:
    """Write the batch THCI case summary."""
    batch_dir = OUT_ROOT / "_batch_summary"
    batch_dir.mkdir(parents=True, exist_ok=True)
    batch_df = pd.concat(case_rows, ignore_index=True)
    batch_df.to_csv(
        batch_dir / "thci_axis_scores_v1_0_case_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )


def main() -> int:
    config = load_config_bundle()
    case_rows: list[pd.DataFrame] = []
    for case_id in CASES:
        case_scores, summary = compute_case_scores(case_id, config)
        write_case_outputs(case_id, case_scores, summary)
        case_rows.append(case_scores)
        print(case_scores.to_string(index=False))
    write_batch_summary(case_rows)
    print("batch summary:", OUT_ROOT / "_batch_summary" / "thci_axis_scores_v1_0_case_summary.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
