# -*- coding: utf-8 -*-
"""Compute THCI v1.0a axis scores with feature-coverage proxy calibration.

This version does not overwrite v1.0 outputs. It keeps the v1.0 deterministic
contract: fixed configs, fixed thresholds, no batch min-max normalization, and
no runtime LLM calls.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import thci_compute_axis_scores_v1_0 as v10  # noqa: E402


PROJECT_ROOT = Path(r"C:\mountain_work\115_osm")
OUT_ROOT = PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_0a"
DIAG_ROOT = PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_0a_diagnostics"

INPUT_ROOTS = {
    **v10.INPUT_ROOTS,
    "ib0d": PROJECT_ROOT
    / "outputs"
    / "ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa",
    "diagnostics": DIAG_ROOT,
}


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _load_diagnostic(case_id: str) -> dict[str, Any]:
    fp = DIAG_ROOT / case_id / f"{case_id}_thci_feature_coverage_diagnostic_v1_0a.csv"
    if not fp.exists():
        raise FileNotFoundError(fp)
    df = pd.read_csv(fp, low_memory=False)
    if df.empty:
        raise ValueError(f"Diagnostic CSV is empty: {fp}")
    return df.iloc[0].to_dict()


def _remove_missing(detail: dict[str, Any], feature_name: str) -> None:
    missing = detail.get("missing_features", [])
    detail["missing_features"] = [x for x in missing if x != feature_name]


def _collect_missing(details: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    return {
        axis: sorted(set(detail.get("missing_features", [])))
        for axis, detail in details.items()
    }


def _count_nested_features(features_by_axis: dict[str, list[Any]]) -> int:
    return sum(len(values or []) for values in features_by_axis.values())


def _sustained_climb_or_stairs_proxy(diag: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    steep20 = _num(diag.get("slope_pct_ge_20_ratio"))
    steps = _num(diag.get("highway_steps_ratio"))
    score = v10.clip01(0.60 * steep20 + 0.40 * steps) or 0.0
    return score, {
        "feature_name": "sustained_climb_or_stairs_score",
        "proxy_method": "0.60*slope_pct_ge_20_ratio + 0.40*highway_steps_ratio",
        "slope_pct_ge_20_ratio": steep20,
        "highway_steps_ratio": steps,
        "proxy_score": score,
    }


def _terrain_hazard_proxy(diag: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    high_band = _num(diag.get("ib1e_high_or_very_high_risk_band_ratio"))
    slope_high = _num(diag.get("slope_band_high_or_very_steep_ratio"))
    terrain_high = _num(diag.get("terrain_window_risk_high_ratio"))
    combined_high = _num(diag.get("osm_terrain_combined_risk_high_ratio"))
    score = v10.clip01(
        0.45 * high_band
        + 0.25 * slope_high
        + 0.15 * terrain_high
        + 0.15 * combined_high
    ) or 0.0
    return score, {
        "feature_name": "terrain_hazard_proxy",
        "proxy_method": "0.45*ib1e_high_or_very_high_risk_band_ratio + 0.25*slope_band_high_or_very_steep_ratio + 0.15*terrain_window_risk_high_ratio + 0.15*osm_terrain_combined_risk_high_ratio",
        "ib1e_high_or_very_high_risk_band_ratio": high_band,
        "slope_band_high_or_very_steep_ratio": slope_high,
        "terrain_window_risk_high_ratio": terrain_high,
        "osm_terrain_combined_risk_high_ratio": combined_high,
        "proxy_score": score,
        "note": "dip_slope remains missing unless a geology layer is available.",
    }


def _weather_impact_proxy(diag: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    surface = _num(diag.get("surface_mud_ground_dirt_earth_unpaved_ratio"))
    steep = _num(diag.get("slope_pct_ge_20_ratio"))
    steps = _num(diag.get("highway_steps_ratio"))
    hydrology = max(
        _num(diag.get("hydrology_flags_ratio")),
        _num(diag.get("near_waterway_ratio")),
        _num(diag.get("hydro_terrain_amplifier_high_ratio")),
    )
    score = v10.clip01(0.35 * surface + 0.25 * steep + 0.20 * steps + 0.20 * hydrology) or 0.0
    return score, {
        "feature_name": "weather_impact_proxy",
        "proxy_method": "0.35*weather_sensitive_surface_ratio + 0.25*steep_slope_ratio + 0.20*steps_ratio + 0.20*hydrology_proxy",
        "surface_mud_ground_dirt_earth_unpaved_ratio": surface,
        "steep_slope_ratio": steep,
        "steps_ratio": steps,
        "hydrology_proxy": hydrology,
        "proxy_score": score,
    }


def _return_difficulty_proxy(diag: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    same_entry = _bool(diag.get("same_entry_keep_full"))
    self_near_exists = _bool(diag.get("self_near_zones_exists"))
    summit_self_near = _bool(diag.get("summit_self_near_zone_exists"))
    route_gap = _num(diag.get("route_gap_max_m"), default=0.0)

    if not (same_entry or self_near_exists or summit_self_near or route_gap > 0):
        score = 0.0
        reliable = False
    else:
        route_gap_score = v10.clip01(route_gap / 5000.0) or 0.0
        score = v10.clip01(
            0.50 * route_gap_score
            + 0.25 * (1.0 if same_entry else 0.0)
            + 0.15 * (1.0 if self_near_exists else 0.0)
            + 0.10 * (1.0 if summit_self_near else 0.0)
        ) or 0.0
        reliable = True

    return score, {
        "feature_name": "return_difficulty_proxy",
        "proxy_method": "0.50*route_gap_norm_5km + 0.25*same_entry_keep_full + 0.15*self_near_zones_exists + 0.10*summit_self_near_zone_exists",
        "same_entry_keep_full": same_entry,
        "self_near_zones_exists": self_near_exists,
        "summit_self_near_zone_exists": summit_self_near,
        "route_gap_max_m": route_gap,
        "proxy_score": score,
        "reliable_proxy_used": reliable,
    }


def _compute_physical_v10a(frames: dict[str, pd.DataFrame], config: dict[str, Any], diag: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    base_score, detail = v10.compute_physical_score(frames["ib1a"], config)
    proxy_score, proxy_detail = _sustained_climb_or_stairs_proxy(diag)

    components = detail["component_scores"]
    old_sustained = _num(components.get("sustained_climb_or_stairs_score"))
    components["sustained_climb_or_stairs_score"] = proxy_score
    calibrated_score = v10.clip01(base_score + 0.10 * (proxy_score - old_sustained)) or 0.0

    _remove_missing(detail, "sustained_climb_or_stairs_score")
    detail["score_before_calibration"] = base_score
    detail["score_after_calibration"] = calibrated_score
    detail["direct_features"] = [
        "dist_m",
        "cum_gain_m",
        "cum_loss_m",
        "slope_pct",
    ]
    detail["proxy_features"] = [proxy_detail]
    detail["calibration_note"] = "v1.0a fills sustained_climb_or_stairs_score from diagnostics proxy."
    return calibrated_score, detail


def _compute_axis_v10a(
    axis_id: str,
    frames: dict[str, pd.DataFrame],
    config: dict[str, Any],
    diag: dict[str, Any],
) -> tuple[float, dict[str, Any]]:
    base_score, detail = v10.compute_mapping_axis_score(axis_id, frames, config)
    detail.setdefault("direct_features", [
        item.get("matched_column")
        for item in detail.get("feature_details", [])
        if item.get("status") == "used"
    ])
    detail.setdefault("proxy_features", [])
    detail["score_before_calibration"] = base_score

    if axis_id == "baseline_hazard_score":
        proxy_score, proxy_detail = _terrain_hazard_proxy(diag)
        score = max(base_score, proxy_score)
        detail["proxy_features"].append(proxy_detail)
    elif axis_id == "weather_impact_score":
        proxy_score, proxy_detail = _weather_impact_proxy(diag)
        score = max(base_score, proxy_score)
        detail["proxy_features"].append(proxy_detail)
    elif axis_id == "navigation_risk_score":
        proxy_score, proxy_detail = _return_difficulty_proxy(diag)
        if proxy_detail["reliable_proxy_used"]:
            score = max(base_score, proxy_score)
            detail["proxy_features"].append(proxy_detail)
            _remove_missing(detail, "return_difficulty")
        else:
            score = base_score
            detail["proxy_features"].append(proxy_detail)
    else:
        score = base_score

    detail["score_after_calibration"] = v10.clip01(score) or 0.0
    return detail["score_after_calibration"], detail


def compute_case_scores_v1_0a(case_id: str, config: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    frames = v10._read_case_inputs(case_id)
    diag = _load_diagnostic(case_id)

    scores: dict[str, float] = {}
    details: dict[str, dict[str, Any]] = {}

    physical_score, physical_detail = _compute_physical_v10a(frames, config, diag)
    scores["physical_difficulty_score"] = physical_score
    details["physical_difficulty_score"] = physical_detail

    for axis_id in v10.AXES:
        if axis_id == "physical_difficulty_score":
            continue
        score, detail = _compute_axis_v10a(axis_id, frames, config, diag)
        scores[axis_id] = score
        details[axis_id] = detail

    missing_features = _collect_missing(details)
    proxy_features = {
        axis: detail.get("proxy_features", [])
        for axis, detail in details.items()
    }
    direct_features = {
        axis: detail.get("direct_features", [])
        for axis, detail in details.items()
    }

    row = {
        "case_id": case_id,
        "scoring_version": "v1.0a",
        **{axis: scores.get(axis, 0.0) for axis in v10.AXES},
        "proxy_features_n": _count_nested_features(proxy_features),
        "missing_features_n": _count_nested_features(missing_features),
        "calibrated_from_v1_0": True,
    }
    out_df = pd.DataFrame([row])

    summary = {
        "case_id": case_id,
        "thci_version": "v1.0a",
        "scoring_version": "v1.0a",
        "scoring_mode": "deterministic_config_only_no_runtime_llm",
        "calibrated_from_v1_0": True,
        "config_paths": config["config_paths"],
        "input_roots": {name: str(path) for name, path in INPUT_ROOTS.items()},
        "output_root": str(OUT_ROOT),
        "axis_scores": {axis: scores.get(axis, 0.0) for axis in v10.AXES},
        "direct_features": direct_features,
        "proxy_features": proxy_features,
        "missing_features": missing_features,
        "proxy_features_n": row["proxy_features_n"],
        "missing_features_n": row["missing_features_n"],
        "axis_details": details,
    }
    return out_df, summary


def write_case_outputs(case_id: str, case_scores: pd.DataFrame, summary: dict[str, Any]) -> None:
    out_dir = OUT_ROOT / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    case_scores.to_csv(out_dir / f"{case_id}_thci_axis_scores_v1_0a.csv", index=False, encoding="utf-8-sig")
    (out_dir / f"{case_id}_thci_axis_score_summary_v1_0a.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_batch_summary(case_rows: list[pd.DataFrame]) -> None:
    batch_dir = OUT_ROOT / "_batch_summary"
    batch_dir.mkdir(parents=True, exist_ok=True)
    pd.concat(case_rows, ignore_index=True).to_csv(
        batch_dir / "thci_axis_scores_v1_0a_case_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )


def main() -> int:
    config = v10.load_config_bundle()
    case_rows: list[pd.DataFrame] = []
    for case_id in v10.CASES:
        case_scores, summary = compute_case_scores_v1_0a(case_id, config)
        write_case_outputs(case_id, case_scores, summary)
        case_rows.append(case_scores)
        print(case_scores.to_string(index=False))
    write_batch_summary(case_rows)
    print("batch summary:", OUT_ROOT / "_batch_summary" / "thci_axis_scores_v1_0a_case_summary.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
