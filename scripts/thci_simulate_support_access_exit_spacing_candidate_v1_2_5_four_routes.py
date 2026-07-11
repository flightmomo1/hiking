# -*- coding: utf-8 -*-
"""THCI support access-exit spacing candidate simulation v1.2.5.

Candidate simulation only. This script reads v1.2 official support summaries
and v1.2.4 access-exit spacing audit outputs, then writes separate v1.2.5
simulation artifacts. It does not modify official scoring scripts,
risk_semantics config, or existing v1.2 outputs.
"""

from __future__ import annotations

import csv
import json
import math
import os
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

V124_SUMMARY_CSV = (
    PROJECT_ROOT
    / "outputs"
    / "thci_support_access_exit_destination_spacing_v1_2_4_audit"
    / "four_route_access_exit_spacing_summary_v1_2_4.csv"
)
V12_ROOT = PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_2_support_updated"
OUT_DIR = PROJECT_ROOT / "outputs" / "thci_support_access_exit_spacing_candidate_v1_2_5_simulation"

OUT_CSV = OUT_DIR / "four_route_support_access_exit_spacing_candidate_v1_2_5.csv"
OUT_MD = OUT_DIR / "four_route_support_access_exit_spacing_candidate_v1_2_5_summary.md"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(out):
        return default
    return out


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def linear_score(value: float, low_value: float, high_value: float) -> float:
    """Return 0 at low_value-or-better and 1 at high_value-or-worse."""
    if value <= low_value:
        return 0.0
    if value >= high_value:
        return 1.0
    return clamp01((value - low_value) / (high_value - low_value))


def inverse_linear_score(value: float, good_high: float, bad_low: float) -> float:
    """Return 0 at good_high-or-better and 1 at bad_low-or-worse."""
    if value >= good_high:
        return 0.0
    if value <= bad_low:
        return 1.0
    return clamp01((good_high - value) / (good_high - bad_low))


def load_v124_spacing_rows() -> dict[str, dict[str, str]]:
    with V124_SUMMARY_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        return {row["case_id"]: row for row in csv.DictReader(handle)}


def v12_summary_path(case_id: str) -> Path:
    return V12_ROOT / case_id / f"{case_id}_thci_axis_score_summary_v1_2_support_updated.json"


def component(detail: dict[str, Any], name: str) -> float:
    return safe_float(detail.get(name), 0.0)


def simulate_case(case_id: str, spacing: dict[str, str]) -> tuple[dict[str, Any], dict[str, Any]]:
    source_json_path = v12_summary_path(case_id)
    source = read_json(source_json_path)
    support = source.get("support_v1_2_detail") or {}
    axis_scores = source.get("axis_scores") or {}

    route_len_m = safe_float(spacing.get("route_len_m"))
    route_km_spacing = route_len_m / 1000.0 if route_len_m > 0 else component(support, "route_km")
    connected_exit_count = safe_float(spacing.get("connected_exit_count"))
    exits_per_km = connected_exit_count / route_km_spacing if route_km_spacing > 0 else 0.0
    longest_no_exit_m = safe_float(spacing.get("longest_no_exit_segment_length_m"))

    connected_exit_density_score = inverse_linear_score(exits_per_km, good_high=2.0, bad_low=0.3)
    max_no_exit_segment_score = linear_score(longest_no_exit_m, low_value=500.0, high_value=3000.0)

    far_review_flag = ""
    if "route_fraction_farther_than_1000m_from_exit" in spacing and spacing.get("route_fraction_farther_than_1000m_from_exit", "") != "":
        far_from_exit_fraction = clamp01(safe_float(spacing.get("route_fraction_farther_than_1000m_from_exit")))
        far_from_exit_fraction_source = "route_fraction_farther_than_1000m_from_exit"
    else:
        far_from_exit_fraction = clamp01(safe_float(spacing.get("route_fraction_farther_than_500m_from_exit")))
        far_from_exit_fraction_source = "route_fraction_farther_than_500m_from_exit"
        far_review_flag = "fallback_500m_fraction_used_review"
    far_from_exit_fraction_score = far_from_exit_fraction

    access_exit_deficit_candidate = (
        0.35 * connected_exit_density_score
        + 0.35 * max_no_exit_segment_score
        + 0.30 * far_from_exit_fraction_score
    )

    road_access_distance_score = component(support, "road_access_distance_score")
    old_vehicle_access_deficit_score = component(support, "vehicle_access_deficit_score")
    long_route_without_exit_score = component(support, "long_route_without_exit_score")
    old_evacuation_access_difficulty_score = component(support, "evacuation_access_difficulty_score")
    support_facility_deficit_score = component(support, "support_facility_deficit_score")
    rescue_operation_difficulty_score = component(support, "rescue_operation_difficulty_score")
    critical_link_bottleneck_score = component(support, "critical_link_bottleneck_score")

    evacuation_access_difficulty_score_candidate = (
        0.45 * road_access_distance_score
        + 0.35 * access_exit_deficit_candidate
        + 0.20 * long_route_without_exit_score
    )
    support_difficulty_score_candidate = (
        0.40 * evacuation_access_difficulty_score_candidate
        + 0.25 * support_facility_deficit_score
        + 0.20 * rescue_operation_difficulty_score
        + 0.15 * critical_link_bottleneck_score
    )

    current_support_score = safe_float(axis_scores.get("support_difficulty_score"))
    row = {
        "case_id": case_id,
        "simulation_version": "v1.2.5",
        "simulation_status": "candidate_simulation_not_official_score",
        "v1_2_current_support_difficulty_score": round(current_support_score, 6),
        "v1_2_5_candidate_support_difficulty_score": round(support_difficulty_score_candidate, 6),
        "support_score_delta_candidate_minus_v1_2": round(support_difficulty_score_candidate - current_support_score, 6),
        "old_vehicle_access_deficit_score": round(old_vehicle_access_deficit_score, 6),
        "access_exit_deficit_candidate": round(access_exit_deficit_candidate, 6),
        "access_exit_deficit_delta_candidate_minus_old": round(
            access_exit_deficit_candidate - old_vehicle_access_deficit_score, 6
        ),
        "connected_exit_count": int(connected_exit_count),
        "route_km_from_v1_2_4_spacing": round(route_km_spacing, 6),
        "exits_per_km": round(exits_per_km, 6),
        "connected_exit_density_score": round(connected_exit_density_score, 6),
        "longest_no_exit_segment_length_m": round(longest_no_exit_m, 3),
        "max_no_exit_segment_score": round(max_no_exit_segment_score, 6),
        "far_from_exit_fraction": round(far_from_exit_fraction, 6),
        "far_from_exit_fraction_source": far_from_exit_fraction_source,
        "far_from_exit_fraction_score": round(far_from_exit_fraction_score, 6),
        "far_from_exit_fraction_review_flag": far_review_flag,
        "old_evacuation_access_difficulty_score": round(old_evacuation_access_difficulty_score, 6),
        "evacuation_access_difficulty_score_candidate": round(
            evacuation_access_difficulty_score_candidate, 6
        ),
        "road_access_distance_score": round(road_access_distance_score, 6),
        "long_route_without_exit_score": round(long_route_without_exit_score, 6),
        "support_facility_deficit_score": round(support_facility_deficit_score, 6),
        "rescue_operation_difficulty_score": round(rescue_operation_difficulty_score, 6),
        "critical_link_bottleneck_score": round(critical_link_bottleneck_score, 6),
        "v1_2_summary_json": str(source_json_path),
        "v1_2_4_spacing_summary_csv": str(V124_SUMMARY_CSV),
    }

    debug = {
        "case_id": case_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "simulation_version": "v1.2.5",
        "simulation_status": "candidate_simulation_not_official_score",
        "guardrails": [
            "did not modify official scoring scripts",
            "did not modify risk_semantics config",
            "did not overwrite existing v1.2 outputs",
            "candidate support-axis simulation only",
            "other five THCI axes are not changed",
        ],
        "inputs": {
            "v1_2_4_spacing_summary_csv": str(V124_SUMMARY_CSV),
            "v1_2_support_summary_json": str(source_json_path),
        },
        "formulas": {
            "connected_exit_density_score": "0 if exits/km >= 2.0; 1 if exits/km <= 0.3; linear between",
            "max_no_exit_segment_score": "0 if longest_no_exit_segment_length_m <= 500; 1 if >= 3000; linear between",
            "far_from_exit_fraction_score": "route_fraction_farther_than_1000m_from_exit, fallback to >500m fraction with review flag",
            "access_exit_deficit_candidate": "0.35*density + 0.35*max_no_exit_segment + 0.30*far_fraction",
            "evacuation_access_difficulty_score_candidate": "0.45*road_access_distance + 0.35*access_exit_deficit_candidate + 0.20*long_route_without_exit",
            "support_difficulty_score_candidate": "0.40*evacuation_access_candidate + 0.25*support_facility_deficit + 0.20*rescue_operation_difficulty + 0.15*critical_link_bottleneck",
        },
        "v1_2_spacing_row": spacing,
        "v1_2_support_detail_used": support,
        "simulation_row": row,
    }
    return row, debug


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
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


def build_report(rows: list[dict[str, Any]], compile_info: dict[str, Any], git_status: str) -> str:
    ranked = sorted(rows, key=lambda row: row["v1_2_5_candidate_support_difficulty_score"], reverse=True)
    zhonghua = next(
        row for row in rows if row["case_id"] == "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b"
    )
    z_rank = next(i + 1 for i, row in enumerate(ranked) if row["case_id"] == zhonghua["case_id"])
    z_high_note = (
        "still relatively high"
        if zhonghua["v1_2_5_candidate_support_difficulty_score"] >= 0.4 or z_rank <= 2
        else "not among the highest after this candidate replacement"
    )

    lines = [
        "# THCI Support Axis v1.2.5 Access-Exit Spacing Candidate Simulation",
        "",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Status: candidate simulation only. This is not an official THCI score output.",
        "",
        "Guardrails:",
        "- Did not modify official scoring scripts.",
        "- Did not modify risk_semantics config.",
        "- Did not overwrite existing v1.2 outputs.",
        "- Other five THCI axes are unchanged; only support-axis candidate components are simulated.",
        "",
        "## Score Comparison",
        "",
        "| Route | v1.2 support | v1.2.5 candidate | delta | old vehicle deficit | new access-exit deficit | longest no-exit m | exits/km | far fraction |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {case} | {old:.3f} | {new:.3f} | {delta:+.3f} | {old_def:.3f} | {new_def:.3f} | {longest:.1f} | {density:.3f} | {far:.3f} |".format(
                case=row["case_id"],
                old=row["v1_2_current_support_difficulty_score"],
                new=row["v1_2_5_candidate_support_difficulty_score"],
                delta=row["support_score_delta_candidate_minus_v1_2"],
                old_def=row["old_vehicle_access_deficit_score"],
                new_def=row["access_exit_deficit_candidate"],
                longest=row["longest_no_exit_segment_length_m"],
                density=row["exits_per_km"],
                far=row["far_from_exit_fraction"],
            )
        )

    lines.extend(
        [
            "",
            "## Candidate Ranking",
            "",
            "| Rank | Route | candidate support | access-exit deficit | longest no-exit m | exits/km |",
            "|---:|---|---:|---:|---:|---:|",
        ]
    )
    for i, row in enumerate(ranked, start=1):
        lines.append(
            f"| {i} | {row['case_id']} | {row['v1_2_5_candidate_support_difficulty_score']:.3f} | {row['access_exit_deficit_candidate']:.3f} | {row['longest_no_exit_segment_length_m']:.1f} | {row['exits_per_km']:.3f} |"
        )

    lines.extend(
        [
            "",
            "## Zhonghua UST / Jiuwufeng",
            "",
            f"Zhonghua UST / Jiuwufeng ranks #{z_rank} of {len(rows)} by candidate support difficulty and is {z_high_note}. Its candidate score is {zhonghua['v1_2_5_candidate_support_difficulty_score']:.3f}, with access-exit deficit {zhonghua['access_exit_deficit_candidate']:.3f}, longest no-exit segment {zhonghua['longest_no_exit_segment_length_m']:.1f} m, exits/km {zhonghua['exits_per_km']:.3f}, and far-from-exit fraction {zhonghua['far_from_exit_fraction']:.3f}.",
            "",
            "## Recommendation",
            "",
            "Use v1.2.5 as the next support-axis candidate simulation for review. It is more interpretable than the old vehicle-access density proxy because it uses connected exit count, along-route no-exit length, and route fraction far from exits. It should remain non-official until v1.2.4 spatial candidates are graph-verified and access restrictions are reviewed.",
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
    spacing_rows = load_v124_spacing_rows()
    rows: list[dict[str, Any]] = []
    for case_id in ROUTES:
        if case_id not in spacing_rows:
            raise KeyError(f"Missing v1.2.4 spacing row for {case_id}")
        case_dir = OUT_DIR / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        row, debug = simulate_case(case_id, spacing_rows[case_id])
        rows.append(row)
        write_json(case_dir / "support_access_exit_spacing_candidate_debug_v1_2_5.json", debug)

    write_csv(OUT_CSV, rows)
    compile_info = py_compile_result()
    git_status = git_status_short()
    OUT_MD.write_text(build_report(rows, compile_info, git_status), encoding="utf-8-sig")

    print("csv:", OUT_CSV)
    print("summary_md:", OUT_MD)
    print("py_compile:", compile_info["status"])
    for row in sorted(rows, key=lambda item: item["v1_2_5_candidate_support_difficulty_score"], reverse=True):
        print(
            "{case}: current={old}, candidate={new}, delta={delta}, access_exit_deficit={deficit}".format(
                case=row["case_id"],
                old=row["v1_2_current_support_difficulty_score"],
                new=row["v1_2_5_candidate_support_difficulty_score"],
                delta=row["support_score_delta_candidate_minus_v1_2"],
                deficit=row["access_exit_deficit_candidate"],
            )
        )
    return 0 if compile_info["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
