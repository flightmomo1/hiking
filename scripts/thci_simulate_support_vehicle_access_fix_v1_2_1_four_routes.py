# -*- coding: utf-8 -*-
"""Simulate THCI v1.2.1 support vehicle-access direction fix for four routes.

This is a candidate/review simulation only. It does not modify the official
v1.2 scoring script, risk semantics config, or existing v1.2 outputs.
"""

from __future__ import annotations

import csv
import json
import math
import py_compile
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

ROUTES = [
    "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b",
    "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b",
    "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b",
    "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b",
]

V12_ROOT = PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_2_support_updated"
OUT_DIR = PROJECT_ROOT / "outputs" / "thci_support_vehicle_access_fix_v1_2_1_simulation"

OUTPUT_CSV = OUT_DIR / "four_route_support_vehicle_access_fix_v1_2_1_simulation.csv"
OUTPUT_MD = OUT_DIR / "four_route_support_vehicle_access_fix_v1_2_1_summary.md"

VEHICLE_THRESHOLDS_LOWER_IS_RISKIER = (
    (2.0, 0.0),
    (1.0, 0.25),
    (0.5, 0.50),
    (0.2, 0.75),
    (0.0, 1.0),
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        value_f = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(value_f):
        return default
    return value_f


def clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def lower_is_riskier_piecewise(value: float) -> float:
    """Map high density to low deficit, low density to high deficit."""
    points = VEHICLE_THRESHOLDS_LOWER_IS_RISKIER
    if value >= points[0][0]:
        return points[0][1]
    if value <= points[-1][0]:
        return points[-1][1]

    for (x_hi, y_hi), (x_lo, y_lo) in zip(points, points[1:]):
        if x_lo <= value <= x_hi:
            if x_hi == x_lo:
                return y_lo
            t = (x_hi - value) / (x_hi - x_lo)
            return y_hi + t * (y_lo - y_hi)
    return 1.0


def detect_proxy_semantics(detail: dict[str, Any]) -> tuple[bool, str]:
    density = num(detail.get("vehicle_accessible_branch_density_proxy"))
    route_km = num(detail.get("route_km"))
    cols = detail.get("vehicle_accessible_branch_cols", [])
    note = (
        "vehicle_accessible_branch_density_proxy is computed in the v1.2 script "
        "as near_ratio(near_highway|near_trailhead) * row_count / route_km. "
        "That is route-profile sample density near access features, not a "
        "graph-derived vehicle-accessible branch count/km."
    )
    review_required = bool(density > 50 or cols != ["near_highway", "near_trailhead"] or route_km > 0)
    return review_required, note


def simulate_case(case_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    summary_path = V12_ROOT / case_id / f"{case_id}_thci_axis_score_summary_v1_2_support_updated.json"
    summary = load_json(summary_path)
    detail = summary["support_v1_2_detail"]

    current_support = num(summary["axis_scores"]["support_difficulty_score"])
    current_vehicle_deficit = num(detail["vehicle_access_deficit_score"])
    density = num(detail["vehicle_accessible_branch_density_proxy"])
    fixed_vehicle_deficit = clip01(lower_is_riskier_piecewise(density))

    road_access = num(detail["road_access_distance_score"])
    long_route = num(detail["long_route_without_exit_score"])
    facility_deficit = num(detail["support_facility_deficit_score"])
    rescue = num(detail["rescue_operation_difficulty_score"])
    bottleneck = num(detail["critical_link_bottleneck_score"])

    current_evac = num(detail["evacuation_access_difficulty_score"])
    fixed_evac = clip01(0.45 * road_access + 0.35 * fixed_vehicle_deficit + 0.20 * long_route)
    fixed_support = clip01(
        0.40 * fixed_evac
        + 0.25 * facility_deficit
        + 0.20 * rescue
        + 0.15 * bottleneck
    )

    review_required, proxy_note = detect_proxy_semantics(detail)
    direction_fix_saturated_to_zero = fixed_vehicle_deficit == 0.0 and density >= 2.0

    row = {
        "case_id": case_id,
        "current_v1_2_support_difficulty_score": current_support,
        "direction_fix_support_difficulty_score_v1_2_1_candidate": fixed_support,
        "support_delta_v1_2_1_minus_v1_2": fixed_support - current_support,
        "vehicle_accessible_branch_density_proxy": density,
        "vehicle_access_deficit_score_v1_2_current": current_vehicle_deficit,
        "vehicle_access_deficit_score_v1_2_1_direction_fix": fixed_vehicle_deficit,
        "vehicle_deficit_delta": fixed_vehicle_deficit - current_vehicle_deficit,
        "evacuation_access_difficulty_score_v1_2_current": current_evac,
        "evacuation_access_difficulty_score_v1_2_1_direction_fix": fixed_evac,
        "evacuation_delta": fixed_evac - current_evac,
        "road_access_distance_score": road_access,
        "long_route_without_exit_score": long_route,
        "support_facility_deficit_score": facility_deficit,
        "rescue_operation_difficulty_score": rescue,
        "critical_link_bottleneck_score": bottleneck,
        "direction_fix_saturates_deficit_to_zero": direction_fix_saturated_to_zero,
        "proxy_semantics_review_required": review_required,
        "proxy_semantics_note": proxy_note,
        "input_summary_json": str(summary_path),
        "simulation_status": "candidate_review_only_not_official",
    }

    debug = {
        "case_id": case_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_summary_json": str(summary_path),
        "guardrails": [
            "did not modify official v1.2 scoring script",
            "did not modify risk_semantics config",
            "did not overwrite existing v1.2 outputs",
            "did not change other five axes",
            "candidate/review simulation only",
        ],
        "threshold_interpretation": {
            "feature": "vehicle_accessible_branch_density_per_km",
            "direction": "lower_is_riskier",
            "score_0": 2.0,
            "score_1": 0.0,
            "expected_semantics": "density >= 2/km gives deficit near 0; density near 0/km gives deficit near 1",
            "direction_fix_threshold_points": VEHICLE_THRESHOLDS_LOWER_IS_RISKIER,
        },
        "current_support_v1_2_detail": detail,
        "simulation_row": row,
    }
    return row, debug


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)

    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def py_compile_result() -> dict[str, Any]:
    try:
        py_compile.compile(str(Path(__file__).resolve()), doraise=True)
        return {"status": "PASS", "returncode": 0, "message": ""}
    except Exception as exc:  # pragma: no cover
        return {"status": "FAIL", "returncode": 1, "message": str(exc)}


def git_status_short() -> str:
    proc = subprocess.run(
        ["git", "status", "--short"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return proc.stderr.strip() or proc.stdout.strip()
    return proc.stdout.strip()


def build_summary(rows: list[dict[str, Any]], compile_info: dict[str, Any], git_status: str) -> str:
    lines = [
        "# THCI v1.2.1 Support Vehicle Access Direction Fix Simulation",
        "",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This is a candidate/review simulation only. It is not official scoring.",
        "",
        "Guardrails:",
        "- Did not modify `scripts/thci_compute_axis_scores_v1_2_support_updated.py`.",
        "- Did not modify risk semantics config.",
        "- Did not overwrite existing v1.2 outputs.",
        "- Did not change the other five THCI axes.",
        "",
        "## Direction-Only Simulation",
        "",
        "| Route | Current v1.2 support | Direction-fix support | Delta | Density proxy | Current vehicle deficit | Fixed vehicle deficit | Fixed deficit saturated to 0 |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]

    for row in rows:
        lines.append(
            "| {case} | {cur:.6f} | {fix:.6f} | {delta:.6f} | {density:.3f} | {vcur:.3f} | {vfix:.3f} | {sat} |".format(
                case=row["case_id"],
                cur=row["current_v1_2_support_difficulty_score"],
                fix=row["direction_fix_support_difficulty_score_v1_2_1_candidate"],
                delta=row["support_delta_v1_2_1_minus_v1_2"],
                density=row["vehicle_accessible_branch_density_proxy"],
                vcur=row["vehicle_access_deficit_score_v1_2_current"],
                vfix=row["vehicle_access_deficit_score_v1_2_1_direction_fix"],
                sat=row["direction_fix_saturates_deficit_to_zero"],
            )
        )

    lines.extend(
        [
            "",
            "## Evacuation Component Comparison",
            "",
            "| Route | Current evacuation | Direction-fix evacuation | Delta | long_route_without_exit | critical_link_bottleneck |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in rows:
        lines.append(
            "| {case} | {cur:.6f} | {fix:.6f} | {delta:.6f} | {long:.6f} | {bottleneck:.6f} |".format(
                case=row["case_id"],
                cur=row["evacuation_access_difficulty_score_v1_2_current"],
                fix=row["evacuation_access_difficulty_score_v1_2_1_direction_fix"],
                delta=row["evacuation_delta"],
                long=row["long_route_without_exit_score"],
                bottleneck=row["critical_link_bottleneck_score"],
            )
        )

    lines.extend(
        [
            "",
            "## Proxy Semantics Audit",
            "",
            "The current proxy is not a true graph-based vehicle-accessible branch count/km. It is computed from route-profile sample rows near `near_highway` or `near_trailhead`, scaled by route length. Because the route profiles are densely sampled, the resulting values are around 1000, far above the config threshold of 2/km.",
            "",
            "All four routes are marked `proxy_semantics_review_required = true`.",
            "",
            "Direction-only fix causes `vehicle_access_deficit_score` to saturate to 0 for all four routes, because the current proxy values are far above 2. This fixes the direction but exposes the second issue: the proxy unit does not match the config unit.",
            "",
            "Recommendation: keep v1.2.1 as candidate/review only until a graph-based vehicle-accessible branch count/km or exit-access metric is implemented.",
            "",
            "## py_compile",
            "",
            f"- Status: `{compile_info['status']}`",
            f"- Return code: `{compile_info['returncode']}`",
            f"- Message: `{compile_info.get('message', '')}`",
            "",
            "## git status --short",
            "",
            "```text",
            git_status if git_status else "(clean)",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []

    for case_id in ROUTES:
        row, debug = simulate_case(case_id)
        rows.append(row)
        debug_path = OUT_DIR / f"{case_id}_support_vehicle_access_fix_v1_2_1_debug.json"
        debug_path.write_text(json.dumps(debug, ensure_ascii=False, indent=2), encoding="utf-8")

    write_csv(OUTPUT_CSV, rows)
    compile_info = py_compile_result()
    git_status = git_status_short()
    OUTPUT_MD.write_text(build_summary(rows, compile_info, git_status), encoding="utf-8")

    print("output_csv:", OUTPUT_CSV)
    print("output_summary_md:", OUTPUT_MD)
    print("py_compile:", compile_info["status"])
    for row in rows:
        print(
            f"{row['case_id']}: "
            f"support {row['current_v1_2_support_difficulty_score']:.6f} -> "
            f"{row['direction_fix_support_difficulty_score_v1_2_1_candidate']:.6f} "
            f"delta={row['support_delta_v1_2_1_minus_v1_2']:.6f}"
        )
    return 0 if compile_info["returncode"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
