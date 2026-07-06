# -*- coding: utf-8 -*-
"""Compute THCI v1.2 support-updated axis scores without overwriting v1.0c.

This is a lightweight THCI radar version bump. It reads the existing v1.0c
axis scores, keeps physical / technical / baseline hazard / navigation /
weather axes unchanged, and recalibrates only support_difficulty_score using
the v1.2 support semantics available from existing route profile and OSM
semantic fields. It does not rerun IB1G2/IB1G3, weather-terrain fusion, or
join NLSC collapse masks back to the route profile.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(r"D:\mountain_work\115_osm")

try:
    import pandas as pd
except ModuleNotFoundError:
    venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
        os.execv(str(venv_python), [str(venv_python), __file__, *sys.argv[1:]])
    raise


CASE_DEFAULT = "taichung_guguan_butterfly_valley_waterfall_20260630"
SCORING_VERSION = "v1.2_support_updated"
PREVIOUS_VERSION = "v1.0c"

CONFIGS = {
    "thci_axis_definition_config": PROJECT_ROOT
    / "configs"
    / "risk_semantics"
    / "thci_axis_definition_v1_2_support_updated.csv",
    "thci_axis_scoring_rule_config": PROJECT_ROOT
    / "configs"
    / "risk_semantics"
    / "thci_axis_scoring_rule_v1_2_support_updated.csv",
    "thci_feature_mapping_config": PROJECT_ROOT
    / "configs"
    / "risk_semantics"
    / "thci_feature_mapping_v1_3_support_updated.csv",
    "thci_normalization_threshold_config": PROJECT_ROOT
    / "configs"
    / "risk_semantics"
    / "thci_normalization_threshold_v1_2_support_updated.csv",
    "osm_semantic_risk_mapping_config": PROJECT_ROOT
    / "configs"
    / "risk_semantics"
    / "osm_semantic_risk_mapping_v1_5_support_updated.csv",
}

AXES = [
    "physical_difficulty_score",
    "technical_difficulty_score",
    "baseline_hazard_score",
    "navigation_risk_score",
    "support_difficulty_score",
    "weather_impact_score",
]

OLD_AXIS_ROOT = PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_0c"
OUT_ROOT = PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_2_support_updated"
IB1C_ROOT = PROJECT_ROOT / "outputs" / "ib1c_route_profile_semantics_v1_3b_contract_qa"
IB1E_ROOT = PROJECT_ROOT / "outputs" / "ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa"
IB0D_ROOT = PROJECT_ROOT / "outputs" / "ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", action="append", default=[])
    return parser.parse_args()


def resolve_cases(args: argparse.Namespace) -> list[str]:
    return list(dict.fromkeys(args.case_id or [CASE_DEFAULT]))


def generated_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def clip01(value: float) -> float:
    if not math.isfinite(float(value)):
        return 0.0
    return max(0.0, min(1.0, float(value)))


def num(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def piecewise(value: float, thresholds: tuple[float, float, float, float, float]) -> float:
    x0, x25, x50, x75, x1 = thresholds
    if value <= x0:
        return 0.0
    if value >= x1:
        return 1.0
    points = [(x0, 0.0), (x25, 0.25), (x50, 0.50), (x75, 0.75), (x1, 1.0)]
    for (a_x, a_y), (b_x, b_y) in zip(points, points[1:]):
        if a_x <= value <= b_x:
            if b_x == a_x:
                return b_y
            return a_y + (value - a_x) / (b_x - a_x) * (b_y - a_y)
    return 0.0


def inverse_piecewise(value: float, thresholds: tuple[float, float, float, float, float]) -> float:
    # Threshold tuple is ordered as value at score 0, .25, .50, .75, 1.
    return piecewise(value, tuple(reversed(thresholds)))


def read_first_csv_row(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    if df.empty:
        raise ValueError(f"CSV is empty: {path}")
    return df.iloc[0].to_dict()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def find_case_csv(root: Path, case_id: str, suffix: str) -> Path:
    case_dir = root / case_id
    exact = case_dir / f"{case_id}{suffix}"
    if exact.exists():
        return exact
    matches = sorted(case_dir.glob(f"*{suffix}"))
    if not matches:
        raise FileNotFoundError(f"No *{suffix} under {case_dir}")
    return matches[0]


def load_case_frames(case_id: str) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Path]]:
    ib1c = find_case_csv(IB1C_ROOT, case_id, "_route_profile_semantic_enriched.csv")
    ib1e = find_case_csv(IB1E_ROOT, case_id, "_route_profile_contour_window_terrain_enriched.csv")
    return (
        pd.read_csv(ib1c, encoding="utf-8-sig", low_memory=False),
        pd.read_csv(ib1e, encoding="utf-8-sig", low_memory=False),
        {"ib1c_csv": ib1c, "ib1e_csv": ib1e},
    )


def route_length_m(df: pd.DataFrame) -> float:
    if "dist_m" in df.columns:
        return float(pd.to_numeric(df["dist_m"], errors="coerce").max())
    return 0.0


def nearest_distance_km(df: pd.DataFrame, columns: list[str], default_km: float = 5.0) -> tuple[float, str]:
    best = math.inf
    best_col = ""
    for col in columns:
        if col not in df.columns:
            continue
        values = pd.to_numeric(df[col], errors="coerce")
        if values.notna().any():
            val = float(values.min())
            if val < best:
                best = val
                best_col = col
    if not math.isfinite(best):
        return default_km, ""
    return max(0.0, best / 1000.0), best_col


def near_ratio(df: pd.DataFrame, columns: list[str]) -> tuple[float, list[str]]:
    used: list[str] = []
    masks = []
    for col in columns:
        if col in df.columns:
            used.append(col)
            masks.append(pd.to_numeric(df[col], errors="coerce").fillna(0).astype(float) > 0)
    if not masks:
        return 0.0, used
    mask = masks[0]
    for item in masks[1:]:
        mask = mask | item
    return float(mask.mean()), used


def count_geojson_features(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    features = data.get("features")
    return len(features) if isinstance(features, list) else 0


def support_bottleneck_score(case_id: str, route_km: float) -> tuple[float, dict[str, Any]]:
    ib0d_dir = IB0D_ROOT / case_id
    self_near = ib0d_dir / "self_near_zones.csv"
    trim = ib0d_dir / "trim_summary.csv"
    self_near_count = 0
    if self_near.exists():
        try:
            self_near_count = len(pd.read_csv(self_near, encoding="utf-8-sig"))
        except Exception:
            self_near_count = 0
    roundtrip_single_access_score = 0.45 if self_near_count > 0 and route_km >= 4.0 else 0.20
    return clip01(roundtrip_single_access_score), {
        "self_near_zones_csv": str(self_near),
        "self_near_zone_count": self_near_count,
        "trim_summary_csv": str(trim),
        "proxy_score": clip01(roundtrip_single_access_score),
        "note": "Lightweight bottleneck proxy from existing IB0D out-and-back/self-near evidence; no graph rerun.",
    }


def compute_support_v1_2(case_id: str, ib1c: pd.DataFrame, ib1e: pd.DataFrame) -> tuple[float, dict[str, Any]]:
    route_km = route_length_m(ib1e) / 1000.0

    vehicle_branch_ratio, vehicle_branch_cols = near_ratio(
        ib1c,
        ["near_highway", "near_trailhead"],
    )
    vehicle_branch_density = vehicle_branch_ratio * max(len(ib1c), 1) / max(route_km, 0.001)
    vehicle_access_deficit = inverse_piecewise(
        vehicle_branch_density,
        (2.0, 1.0, 0.5, 0.2, 0.0),
    )

    # No formal exit-point graph is produced in the current lightweight input set.
    # Use total route length as a conservative long-route-without-exit proxy.
    long_route_without_exit = piecewise(route_km, (0.0, 2.0, 5.0, 8.0, 12.0))
    road_access_km, road_access_col = nearest_distance_km(
        ib1c,
        ["dist_highway_m", "dist_trailhead_m"],
        default_km=5.0,
    )
    road_access_distance = piecewise(road_access_km, (0.0, 0.5, 1.5, 3.0, 5.0))
    evacuation_access_difficulty = clip01(
        0.45 * road_access_distance
        + 0.35 * vehicle_access_deficit
        + 0.20 * long_route_without_exit
    )

    support_facility_km, support_facility_col = nearest_distance_km(
        ib1c,
        [
            "dist_shelter_m",
            "dist_alpine_hut_m",
            "dist_wilderness_hut_m",
            "dist_bench_m",
            "dist_picnic_table_m",
            "dist_picnic_site_m",
            "dist_drinking_water_m",
            "dist_toilets_m",
            "dist_visitor_centre_m",
            "dist_information_office_m",
        ],
        default_km=5.0,
    )
    support_facility_deficit = piecewise(support_facility_km, (0.0, 0.5, 1.5, 3.0, 5.0))

    emergency_near_ratio, emergency_cols = near_ratio(
        ib1c,
        ["near_shelter", "near_alpine_hut", "near_wilderness_hut", "near_trailhead"],
    )
    rescue_operation_difficulty = clip01(1.0 - emergency_near_ratio)

    critical_link_bottleneck, bottleneck_detail = support_bottleneck_score(case_id, route_km)

    score = clip01(
        0.40 * evacuation_access_difficulty
        + 0.25 * support_facility_deficit
        + 0.20 * rescue_operation_difficulty
        + 0.15 * critical_link_bottleneck
    )

    detail = {
        "scoring_rule": "0.40*evacuation_access_difficulty + 0.25*support_facility_deficit + 0.20*rescue_operation_difficulty + 0.15*critical_link_bottleneck",
        "route_km": route_km,
        "road_access_distance_km": road_access_km,
        "road_access_source_col": road_access_col,
        "road_access_distance_score": road_access_distance,
        "vehicle_accessible_branch_density_proxy": vehicle_branch_density,
        "vehicle_accessible_branch_cols": vehicle_branch_cols,
        "vehicle_access_deficit_score": vehicle_access_deficit,
        "long_route_without_exit_score": long_route_without_exit,
        "evacuation_access_difficulty_score": evacuation_access_difficulty,
        "nearest_support_facility_km": support_facility_km,
        "nearest_support_facility_source_col": support_facility_col,
        "support_facility_deficit_score": support_facility_deficit,
        "emergency_near_ratio_proxy": emergency_near_ratio,
        "emergency_near_cols": emergency_cols,
        "rescue_operation_difficulty_score": rescue_operation_difficulty,
        "critical_link_bottleneck_score": critical_link_bottleneck,
        "critical_link_bottleneck_detail": bottleneck_detail,
        "proxy_method_note": (
            "Uses existing IB1C/IB1E/IB0D outputs only. No OSM graph rerun, no "
            "IB1G2/IB1G3 rerun, no weather-terrain fusion rerun, and no NLSC "
            "collapse-mask join to route profile."
        ),
    }
    return score, detail


def old_paths(case_id: str) -> dict[str, Path]:
    return {
        "v1_0c_axis_score_csv": OLD_AXIS_ROOT / case_id / f"{case_id}_thci_axis_scores_v1_0c.csv",
        "v1_0c_axis_score_summary_json": OLD_AXIS_ROOT / case_id / f"{case_id}_thci_axis_score_summary_v1_0c.json",
    }


def compute_case(case_id: str) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame]:
    paths = old_paths(case_id)
    old_row = read_first_csv_row(paths["v1_0c_axis_score_csv"])
    old_summary = read_json(paths["v1_0c_axis_score_summary_json"])
    ib1c, ib1e, input_files = load_case_frames(case_id)

    support_score, support_detail = compute_support_v1_2(case_id, ib1c, ib1e)
    new_scores = {axis: clip01(num(old_row.get(axis))) for axis in AXES}
    new_scores["support_difficulty_score"] = support_score

    now = generated_at()
    config_metadata = {key: str(path) for key, path in CONFIGS.items()}
    row = {
        "case_id": case_id,
        "status": "PASS",
        "scoring_version": SCORING_VERSION,
        "previous_scoring_version": PREVIOUS_VERSION,
        "lightweight_support_update": True,
        "generated_at": now,
        **new_scores,
        "previous_v1_0c_support_difficulty_score": clip01(num(old_row.get("support_difficulty_score"))),
        "v1_2_support_difficulty_score": support_score,
        "support_delta_v1_2_minus_v1_0c": support_score - clip01(num(old_row.get("support_difficulty_score"))),
        **config_metadata,
        "runtime_llm_allowed": False,
        "reran_ib1g2_ib1g3": False,
        "reran_weather_terrain_fusion": False,
        "joined_nlsc_collapse_mask_to_route_profile": False,
    }

    comparison_rows = []
    for axis in AXES:
        old_score = clip01(num(old_row.get(axis)))
        new_score = new_scores[axis]
        comparison_rows.append(
            {
                "case_id": case_id,
                "axis_id": axis,
                "v1_0c_score": old_score,
                "v1_2_support_updated_score": new_score,
                "delta_v1_2_minus_v1_0c": new_score - old_score,
                "changed": abs(new_score - old_score) > 1e-12,
            }
        )

    previous_proxy = old_summary.get("proxy_features", {})
    previous_missing = old_summary.get("missing_features", {})
    summary = {
        "case_id": case_id,
        "scoring_version": SCORING_VERSION,
        "previous_scoring_version": PREVIOUS_VERSION,
        "generated_at": now,
        **config_metadata,
        "source_files": {
            **{key: str(path) for key, path in paths.items()},
            **{key: str(path) for key, path in input_files.items()},
        },
        "axis_scores": new_scores,
        "previous_v1_0c_axis_scores": {axis: clip01(num(old_row.get(axis))) for axis in AXES},
        "comparison_csv": str(
            OUT_ROOT
            / case_id
            / f"{case_id}_thci_axis_scores_v1_0c_vs_v1_2_support_updated_comparison.csv"
        ),
        "support_v1_2_detail": support_detail,
        "carried_forward_axes": [
            axis for axis in AXES if axis != "support_difficulty_score"
        ],
        "changed_axes": [
            item["axis_id"] for item in comparison_rows if item["changed"]
        ],
        "runtime_llm_allowed": False,
        "lightweight_update_scope": {
            "reran_ib1g2_ib1g3": False,
            "reran_weather_terrain_fusion": False,
            "joined_nlsc_collapse_mask_to_route_profile": False,
            "modified_thci_scoring_config": False,
            "overwrote_v1_0c_outputs": False,
        },
        "proxy_features": {
            **(previous_proxy if isinstance(previous_proxy, dict) else {}),
            "support_difficulty_score": [
                {
                    "feature_name": "support_v1_2_lightweight_recalibration",
                    "proxy_method": support_detail["scoring_rule"],
                    **support_detail,
                    "proxy_score": support_score,
                }
            ],
        },
        "missing_features": {
            **(previous_missing if isinstance(previous_missing, dict) else {}),
            "support_difficulty_score": [
                "formal_exit_point_graph",
                "formal_vehicle_accessible_branch_graph",
                "formal_rescue_landing_site_inventory",
                "mobile_signal",
                "gps_blockage_or_drift",
            ],
        },
    }
    return pd.DataFrame([row]), summary, pd.DataFrame(comparison_rows)


def write_case(case_id: str, scores: pd.DataFrame, summary: dict[str, Any], comparison: pd.DataFrame) -> None:
    out_dir = OUT_ROOT / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    scores.to_csv(
        out_dir / f"{case_id}_thci_axis_scores_v1_2_support_updated.csv",
        index=False,
        encoding="utf-8-sig",
    )
    (out_dir / f"{case_id}_thci_axis_score_summary_v1_2_support_updated.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    comparison.to_csv(
        out_dir / f"{case_id}_thci_axis_scores_v1_0c_vs_v1_2_support_updated_comparison.csv",
        index=False,
        encoding="utf-8-sig",
    )


def main() -> int:
    args = parse_args()
    failures = 0
    for case_id in resolve_cases(args):
        try:
            scores, summary, comparison = compute_case(case_id)
            write_case(case_id, scores, summary, comparison)
            row = scores.iloc[0]
            print(
                f"{case_id}: PASS support "
                f"{row['previous_v1_0c_support_difficulty_score']:.4f} -> "
                f"{row['v1_2_support_difficulty_score']:.4f} "
                f"delta={row['support_delta_v1_2_minus_v1_0c']:.4f}"
            )
        except Exception as exc:
            failures += 1
            print(f"{case_id}: FAIL {exc}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
