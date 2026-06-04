# -*- coding: utf-8 -*-
"""Compute THCI v1.0c weather semantics calibrated axis scores.

v1.0c keeps the five non-weather axes from THCI v1.0b and recalculates only
weather_impact_score from deterministic weather sensitivity diagnostics.
It does not call LLMs, does not use batch min-max normalization, and does not
modify v1.0b outputs or rerun IB2D.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(r"C:\mountain_work\115_osm")

try:
    import pandas as pd
except ModuleNotFoundError:
    venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
        os.execv(str(venv_python), [str(venv_python), __file__, *sys.argv[1:]])
    raise


SCORING_VERSION = "v1.0c"
OUT_ROOT = PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_0c"

INPUT_ROOTS = {
    "thci_axis_scores_v1_0b": PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_0b",
    "weather_sensitivity_diagnostics_v1_0b": PROJECT_ROOT
    / "outputs"
    / "thci_weather_sensitivity_diagnostics_v1_0b",
    "ib1e": PROJECT_ROOT / "outputs" / "ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa",
    "ib1c": PROJECT_ROOT / "outputs" / "ib1c_route_profile_semantics_v1_3b_contract_qa",
    "thci_route_metric_summary_v1": PROJECT_ROOT / "outputs" / "thci_route_metric_summary_v1",
}

CASES = [
    "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b",
    "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b",
    "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b",
    "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b",
    "qixing_lengshuikeng_xiaoyoukeng_gpx_osmrefresh_v1_3b",
]

AXES = [
    "physical_difficulty_score",
    "technical_difficulty_score",
    "baseline_hazard_score",
    "navigation_risk_score",
    "support_difficulty_score",
    "weather_impact_score",
]

NON_WEATHER_AXES = [axis for axis in AXES if axis != "weather_impact_score"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--case-list", default=None)
    return parser.parse_args()


def resolve_cases(args: argparse.Namespace) -> list[str]:
    cases = list(args.case_id or [])
    if args.case_list:
        fp = Path(args.case_list)
        if not fp.is_absolute():
            fp = PROJECT_ROOT / fp
        with fp.open("r", encoding="utf-8") as handle:
            for line in handle:
                item = line.strip()
                if item and not item.startswith("#"):
                    cases.append(item)
    return list(dict.fromkeys(cases)) if cases else list(CASES)


def clip01(value: float) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _count_nested_features(features_by_axis: Any) -> int:
    if not isinstance(features_by_axis, dict):
        return 0
    total = 0
    for values in features_by_axis.values():
        if isinstance(values, list):
            total += len(values)
    return total


def case_source_files(case_id: str) -> dict[str, str]:
    return {
        "v1_0b_axis_score_csv": str(
            INPUT_ROOTS["thci_axis_scores_v1_0b"]
            / case_id
            / f"{case_id}_thci_axis_scores_v1_0b.csv"
        ),
        "v1_0b_axis_score_summary_json": str(
            INPUT_ROOTS["thci_axis_scores_v1_0b"]
            / case_id
            / f"{case_id}_thci_axis_score_summary_v1_0b.json"
        ),
        "weather_diagnostic_csv": str(
            INPUT_ROOTS["weather_sensitivity_diagnostics_v1_0b"]
            / case_id
            / f"{case_id}_weather_sensitivity_diagnostic_v1_0b.csv"
        ),
        "weather_diagnostic_summary_json": str(
            INPUT_ROOTS["weather_sensitivity_diagnostics_v1_0b"]
            / case_id
            / f"{case_id}_weather_sensitivity_summary_v1_0b.json"
        ),
        "ib1e_csv": str(
            INPUT_ROOTS["ib1e"]
            / case_id
            / f"{case_id}_route_profile_contour_window_terrain_enriched.csv"
        ),
        "ib1c_csv": str(
            INPUT_ROOTS["ib1c"]
            / case_id
            / f"{case_id}_route_profile_semantic_enriched.csv"
        ),
        "route_metric_summary_csv": str(
            INPUT_ROOTS["thci_route_metric_summary_v1"]
            / "five_route_distance_gain_stairs_summary.csv"
        ),
    }


def read_first_row_csv(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path, low_memory=False, encoding="utf-8-sig")
    if df.empty:
        raise ValueError(f"CSV is empty: {path}")
    return df.iloc[0].to_dict()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def step_score(steps_ratio: float) -> float:
    if steps_ratio >= 0.60:
        return 0.70
    if steps_ratio >= 0.40:
        return 0.55
    if steps_ratio >= 0.20:
        return 0.35
    return 0.10


def slope_score(steep_ratio: float, very_steep_ratio: float) -> float:
    return max(0.0, min(0.75, max(steep_ratio * 1.2, very_steep_ratio * 1.6)))


def hydrology_score(hydrology_ratio: float) -> float:
    if hydrology_ratio >= 0.50:
        return 0.70
    if hydrology_ratio >= 0.20:
        return 0.50
    if hydrology_ratio >= 0.05:
        return 0.30
    return 0.05


def slippery_surface_score(slippery_ratio: float) -> float:
    if slippery_ratio >= 0.80:
        return 0.65
    if slippery_ratio >= 0.50:
        return 0.45
    if slippery_ratio >= 0.20:
        return 0.25
    return 0.05


def exposure_score(exposure_ratio: float) -> float:
    if exposure_ratio >= 0.60:
        return 0.70
    if exposure_ratio >= 0.30:
        return 0.50
    if exposure_ratio >= 0.10:
        return 0.30
    return 0.05


def calibrate_weather(previous_score: float, diag: dict[str, Any]) -> dict[str, Any]:
    steps_ratio = _num(diag.get("steps_length_ratio"))
    steep_ratio = _num(diag.get("steep_slope_ratio"))
    very_steep_ratio = _num(diag.get("very_steep_slope_ratio"))
    hydrology_ratio = _num(diag.get("hydrology_related_length_ratio"))
    slippery_ratio = _num(diag.get("slippery_surface_length_ratio"))
    exposure_ratio = _num(diag.get("exposure_related_length_ratio"))

    scores = {
        "weather_steps_score": step_score(steps_ratio),
        "weather_slope_score": slope_score(steep_ratio, very_steep_ratio),
        "weather_hydrology_score": hydrology_score(hydrology_ratio),
        "weather_slippery_surface_score": slippery_surface_score(slippery_ratio),
        "weather_exposure_score": exposure_score(exposure_ratio),
    }
    component_values = list(scores.values())
    component_max = max(component_values)
    component_mean = sum(component_values) / len(component_values)

    raw_score = 0.55 * previous_score + 0.30 * component_max + 0.15 * component_mean
    weather_guard_applied: list[str] = []
    guarded_score = raw_score

    if hydrology_ratio >= 0.50 and slippery_ratio >= 0.50 and guarded_score < 0.30:
        guarded_score = 0.30
        weather_guard_applied.append("hydrology>=0.50_and_slippery>=0.50_floor_0.30")
    if exposure_ratio >= 0.50 and slippery_ratio >= 0.80 and guarded_score < 0.32:
        guarded_score = 0.32
        weather_guard_applied.append("exposure>=0.50_and_slippery>=0.80_floor_0.32")
    if steps_ratio >= 0.60 and steep_ratio >= 0.45 and guarded_score < 0.30:
        guarded_score = 0.30
        weather_guard_applied.append("steps>=0.60_and_steep>=0.45_floor_0.30")

    strong_driver = any(
        [
            steps_ratio >= 0.60,
            steep_ratio >= 0.45,
            hydrology_ratio >= 0.50,
            slippery_ratio >= 0.80,
            exposure_ratio >= 0.50,
        ]
    )
    high_weather_combo = (hydrology_ratio >= 0.50 and slippery_ratio >= 0.50) or (
        exposure_ratio >= 0.50 and slippery_ratio >= 0.80
    )
    cap_limit = 0.60 if high_weather_combo else 0.55
    if not strong_driver:
        cap_limit = min(cap_limit, 0.30)

    capped_score = min(guarded_score, cap_limit)
    weather_cap_applied = capped_score < guarded_score
    final_score = clip01(capped_score)

    return {
        **scores,
        "weather_component_max": component_max,
        "weather_component_mean": component_mean,
        "weather_raw_calibrated_score": raw_score,
        "weather_guarded_score": guarded_score,
        "weather_guard_applied": weather_guard_applied,
        "weather_cap_applied": bool(weather_cap_applied),
        "weather_cap_limit": cap_limit,
        "v1_0c_weather_impact_score": final_score,
        "weather_diagnostic_inputs": {
            "steps_length_ratio": steps_ratio,
            "steep_slope_ratio": steep_ratio,
            "very_steep_slope_ratio": very_steep_ratio,
            "hydrology_related_length_ratio": hydrology_ratio,
            "slippery_surface_length_ratio": slippery_ratio,
            "exposure_related_length_ratio": exposure_ratio,
        },
    }


def compute_case_scores(case_id: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    files = case_source_files(case_id)
    v10b_csv = Path(files["v1_0b_axis_score_csv"])
    v10b_summary_json = Path(files["v1_0b_axis_score_summary_json"])
    diag_csv = Path(files["weather_diagnostic_csv"])
    diag_summary_json = Path(files["weather_diagnostic_summary_json"])

    v10b_row = read_first_row_csv(v10b_csv)
    v10b_summary = read_json(v10b_summary_json)
    diag_row = read_first_row_csv(diag_csv)
    diag_summary = read_json(diag_summary_json) if diag_summary_json.exists() else {}

    previous_weather = clip01(_num(v10b_row.get("weather_impact_score")))
    calibration = calibrate_weather(previous_weather, diag_row)
    v10c_weather = calibration["v1_0c_weather_impact_score"]
    delta = v10c_weather - previous_weather

    axis_scores = {
        axis: clip01(_num(v10b_row.get(axis)))
        for axis in NON_WEATHER_AXES
    }
    axis_scores["weather_impact_score"] = v10c_weather
    ordered_axis_scores = {axis: axis_scores[axis] for axis in AXES}

    missing_features = v10b_summary.get("missing_features", {})
    proxy_features = v10b_summary.get("proxy_features", {})
    proxy_features = dict(proxy_features) if isinstance(proxy_features, dict) else {}
    proxy_features["weather_impact_score"] = list(proxy_features.get("weather_impact_score", [])) + [
        {
            "feature_name": "weather_semantics_calibration_v1_0c",
            "proxy_method": "0.55*v1.0b weather + 0.30*weather_component_max + 0.15*weather_component_mean with deterministic guards/caps",
            **calibration["weather_diagnostic_inputs"],
            "weather_component_max": calibration["weather_component_max"],
            "weather_component_mean": calibration["weather_component_mean"],
            "proxy_score": v10c_weather,
        }
    ]

    missing_features_n = _count_nested_features(missing_features)
    proxy_features_n = _count_nested_features(proxy_features)
    guard_text = "|".join(calibration["weather_guard_applied"])
    calibration_note = (
        "v1.0c recalculates only weather_impact_score from v1.0b weather sensitivity diagnostics; "
        "all non-weather axes are copied from v1.0b. No LLM, no batch min-max normalization, no IB2D rerun."
    )

    row = {
        "case_id": case_id,
        "status": "PASS",
        "scoring_version": SCORING_VERSION,
        "calibrated_from_v1_0b": True,
        "weather_semantics_calibrated": True,
        **ordered_axis_scores,
        "previous_v1_0b_weather_impact_score": previous_weather,
        "v1_0c_weather_impact_score": v10c_weather,
        "weather_delta_v1_0c_minus_v1_0b": delta,
        "weather_steps_score": calibration["weather_steps_score"],
        "weather_slope_score": calibration["weather_slope_score"],
        "weather_hydrology_score": calibration["weather_hydrology_score"],
        "weather_slippery_surface_score": calibration["weather_slippery_surface_score"],
        "weather_exposure_score": calibration["weather_exposure_score"],
        "weather_component_max": calibration["weather_component_max"],
        "weather_component_mean": calibration["weather_component_mean"],
        "weather_guard_applied": guard_text,
        "weather_cap_applied": calibration["weather_cap_applied"],
        "calibration_note": calibration_note,
        "runtime_llm_allowed": False,
        "missing_features_n": missing_features_n,
        "proxy_features_n": proxy_features_n,
    }

    summary = {
        "case_id": case_id,
        "scoring_version": SCORING_VERSION,
        "calibrated_from_v1_0b": True,
        "weather_semantics_calibrated": True,
        "input_roots": {key: str(path) for key, path in INPUT_ROOTS.items()},
        "source_files": files,
        "axis_scores": ordered_axis_scores,
        "previous_v1_0b_weather_impact_score": previous_weather,
        "v1_0c_weather_impact_score": v10c_weather,
        "weather_delta_v1_0c_minus_v1_0b": delta,
        "weather_components": {
            "weather_steps_score": calibration["weather_steps_score"],
            "weather_slope_score": calibration["weather_slope_score"],
            "weather_hydrology_score": calibration["weather_hydrology_score"],
            "weather_slippery_surface_score": calibration["weather_slippery_surface_score"],
            "weather_exposure_score": calibration["weather_exposure_score"],
            "weather_component_max": calibration["weather_component_max"],
            "weather_component_mean": calibration["weather_component_mean"],
            "weather_raw_calibrated_score": calibration["weather_raw_calibrated_score"],
            "weather_guarded_score": calibration["weather_guarded_score"],
            "weather_cap_limit": calibration["weather_cap_limit"],
        },
        "weather_diagnostic_inputs": calibration["weather_diagnostic_inputs"],
        "weather_diagnostic_summary": diag_summary.get("diagnostic_flags", {}),
        "weather_guard_applied": calibration["weather_guard_applied"],
        "weather_cap_applied": calibration["weather_cap_applied"],
        "calibration_note": calibration_note,
        "non_weather_axes_copied_from_v1_0b": True,
        "runtime_llm_allowed": False,
        "missing_features": missing_features,
        "proxy_features": proxy_features,
        "missing_features_n": missing_features_n,
        "proxy_features_n": proxy_features_n,
    }
    return pd.DataFrame([row]), summary


def write_case_outputs(case_id: str, case_scores: pd.DataFrame, summary: dict[str, Any]) -> None:
    out_dir = OUT_ROOT / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    case_scores.to_csv(out_dir / f"{case_id}_thci_axis_scores_v1_0c.csv", index=False, encoding="utf-8-sig")
    (out_dir / f"{case_id}_thci_axis_score_summary_v1_0c.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_batch_summary(rows: list[pd.DataFrame]) -> None:
    batch_dir = OUT_ROOT / "_batch_summary"
    batch_dir.mkdir(parents=True, exist_ok=True)
    pd.concat(rows, ignore_index=True).to_csv(
        batch_dir / "thci_axis_scores_v1_0c_case_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )


def main() -> int:
    args = parse_args()
    rows: list[pd.DataFrame] = []
    failures = 0
    for case_id in resolve_cases(args):
        try:
            case_scores, summary = compute_case_scores(case_id)
            write_case_outputs(case_id, case_scores, summary)
            rows.append(case_scores)
            row = case_scores.iloc[0]
            print(
                f"{case_id}: PASS "
                f"v1.0b_weather={row['previous_v1_0b_weather_impact_score']:.4f} "
                f"v1.0c_weather={row['v1_0c_weather_impact_score']:.4f} "
                f"delta={row['weather_delta_v1_0c_minus_v1_0b']:.4f} "
                f"guard={row['weather_guard_applied'] or 'none'} "
                f"cap={row['weather_cap_applied']}"
            )
        except Exception as exc:
            failures += 1
            row = pd.DataFrame(
                [
                    {
                        "case_id": case_id,
                        "status": "FAIL",
                        "scoring_version": SCORING_VERSION,
                        "calibration_note": str(exc),
                    }
                ]
            )
            rows.append(row)
            print(f"{case_id}: FAIL {exc}")
    if rows:
        write_batch_summary(rows)
    print("batch summary:", OUT_ROOT / "_batch_summary" / "thci_axis_scores_v1_0c_case_summary.csv")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
