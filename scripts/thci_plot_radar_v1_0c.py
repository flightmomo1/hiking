# -*- coding: utf-8 -*-
"""Plot THCI v1.0c radar charts from precomputed axis score CSV files.

THCI v1.0c is the current recommended display/scoring version. It keeps the
five non-weather axes from v1.0b and applies the weather semantics calibration
candidate promoted by the hydrology-topography review evidence.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(r"D:\mountain_work\115_osm")

try:
    import matplotlib.font_manager as fm
    import matplotlib.pyplot as plt
except ModuleNotFoundError:
    venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
        os.execv(str(venv_python), [str(venv_python), __file__, *sys.argv[1:]])
    raise


SCORING_VERSION = "v1.0c"
PREVIOUS_RECOMMENDED_VERSION = "v1.0b"
HYDRO_TOPO_REVIEW_STATUS = "WEATHER_CALIBRATION_ESTABLISHED_WITH_HYDROLOGY_TOPOGRAPHY_REVIEW"

AXIS_DEFINITION_CSV = PROJECT_ROOT / "configs" / "risk_semantics" / "thci_axis_definition_v1_0.csv"
AXIS_SCORE_ROOT = PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_0c"
OUT_ROOT = PROJECT_ROOT / "outputs" / "thci_radar_v1_0c"

CASES = [
    "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b",
    "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b",
    "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b",
    "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b",
    "qixing_lengshuikeng_xiaoyoukeng_gpx_osmrefresh_v1_3b",
]

AXIS_ORDER = [
    ("physical_difficulty_score", "體力難度"),
    ("technical_difficulty_score", "技術難度"),
    ("baseline_hazard_score", "基礎危害"),
    ("navigation_risk_score", "迷航風險"),
    ("support_difficulty_score", "支援不易"),
    ("weather_impact_score", "天候影響"),
]


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


def _float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def load_axis_definition() -> dict[str, dict[str, str]]:
    """Load the official axis definition table for provenance."""
    definitions: dict[str, dict[str, str]] = {}
    if not AXIS_DEFINITION_CSV.exists():
        return definitions
    with AXIS_DEFINITION_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            axis_id = str(row.get("axis_id") or row.get("axis") or "").strip()
            if axis_id:
                definitions[axis_id] = dict(row)
    return definitions


def load_axis_scores(case_id: str) -> tuple[dict[str, Any], Path]:
    """Load one THCI v1.0c axis score CSV without recalculating scores."""
    path = AXIS_SCORE_ROOT / case_id / f"{case_id}_thci_axis_scores_v1_0c.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            axis_scores = {axis: _float_or_none(row.get(axis)) for axis, _label in AXIS_ORDER}
            row["axis_scores"] = axis_scores
            return row, path
    raise ValueError(f"CSV is empty: {path}")


def load_axis_score_summary(case_id: str) -> tuple[dict[str, Any], Path]:
    """Load one THCI v1.0c axis score summary JSON."""
    path = AXIS_SCORE_ROOT / case_id / f"{case_id}_thci_axis_score_summary_v1_0c.json"
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle), path


def validate_axis_scores(axis_scores: dict[str, float | None]) -> tuple[list[str], list[str]]:
    missing_axes = [axis for axis, _label in AXIS_ORDER if axis_scores.get(axis) is None]
    out_of_range_axes = [
        axis
        for axis, _label in AXIS_ORDER
        if axis_scores.get(axis) is not None and not (0.0 <= float(axis_scores[axis]) <= 1.0)
    ]
    return missing_axes, out_of_range_axes


def setup_chinese_font() -> None:
    """Prefer Microsoft JhengHei on Windows, then fall back to common CJK fonts."""
    preferred = [
        "Microsoft JhengHei",
        "Microsoft YaHei",
        "Noto Sans CJK TC",
        "Noto Sans CJK JP",
        "SimHei",
        "Arial Unicode MS",
    ]
    available = {font.name for font in fm.fontManager.ttflist}
    for font_name in preferred:
        if font_name in available:
            plt.rcParams["font.family"] = font_name
            break
    plt.rcParams["axes.unicode_minus"] = False


def plot_radar(case_id: str, axis_scores: dict[str, float], output_png: Path) -> None:
    """Write one 0-1 radar PNG."""
    labels = [label for _axis, label in AXIS_ORDER]
    values = [float(axis_scores[axis]) for axis, _label in AXIS_ORDER]
    angles = [idx / float(len(labels)) * 2.0 * math.pi for idx in range(len(labels))]
    angles_closed = angles + angles[:1]
    values_closed = values + values[:1]

    setup_chinese_font()
    fig = plt.figure(figsize=(7.2, 7.2))
    ax = fig.add_subplot(111, polar=True)
    ax.plot(angles_closed, values_closed, color="#355f8c", linewidth=2.4)
    ax.fill(angles_closed, values_closed, color="#355f8c", alpha=0.18)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], fontsize=9)
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=13)
    ax.grid(color="#b8c2ce", linewidth=0.8)
    ax.set_title(
        f"THCI v1.0c weather semantics calibrated\n{case_id}",
        va="bottom",
        fontsize=15,
        pad=22,
    )
    for angle, value in zip(angles, values):
        ax.text(angle, min(1.06, value + 0.08), f"{value:.2f}", ha="center", va="center", fontsize=10)
    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=180, bbox_inches="tight")
    plt.close(fig)


def write_case_outputs(
    case_id: str,
    axis_definitions: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Write radar PNG, plot data CSV, and summary JSON for one case."""
    out_dir = OUT_ROOT / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    output_png = out_dir / f"{case_id}_thci_radar_v1_0c.png"
    output_plot_data_csv = out_dir / f"{case_id}_thci_radar_plot_data_v1_0c.csv"
    output_summary_json = out_dir / f"{case_id}_thci_radar_summary_v1_0c.json"

    radar_status = "PASS"
    missing_axes: list[str] = []
    out_of_range_axes: list[str] = []
    axis_scores: dict[str, float | None] = {axis: None for axis, _label in AXIS_ORDER}
    score_row: dict[str, Any] = {}
    score_summary: dict[str, Any] = {}
    axis_score_csv = AXIS_SCORE_ROOT / case_id / f"{case_id}_thci_axis_scores_v1_0c.csv"
    axis_score_summary_json = AXIS_SCORE_ROOT / case_id / f"{case_id}_thci_axis_score_summary_v1_0c.json"
    blocking_issues: list[str] = []

    try:
        score_row, axis_score_csv = load_axis_scores(case_id)
        axis_scores = score_row["axis_scores"]
    except Exception as exc:
        blocking_issues.append(f"FAIL_load_axis_scores:{exc}")

    try:
        score_summary, axis_score_summary_json = load_axis_score_summary(case_id)
    except Exception as exc:
        blocking_issues.append(f"FAIL_load_axis_summary:{exc}")

    missing_axes, out_of_range_axes = validate_axis_scores(axis_scores)
    if missing_axes:
        blocking_issues.append("FAIL_missing_axes")
    if out_of_range_axes:
        blocking_issues.append("FAIL_out_of_range_axes")
    if score_row and score_row.get("scoring_version") != SCORING_VERSION:
        blocking_issues.append("FAIL_scoring_version")
    if score_summary and score_summary.get("runtime_llm_allowed") is not False:
        blocking_issues.append("FAIL_runtime_llm_allowed_not_false")

    numeric_axis_scores = {
        axis: float(axis_scores[axis])
        for axis, _label in AXIS_ORDER
        if axis_scores.get(axis) is not None
    }
    if not blocking_issues and len(numeric_axis_scores) == len(AXIS_ORDER):
        plot_radar(case_id, numeric_axis_scores, output_png)
    else:
        radar_status = blocking_issues[0] if blocking_issues else "FAIL"

    with output_plot_data_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        fieldnames = ["axis_order", "axis_id", "axis_label_zh", "score"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for idx, (axis, label) in enumerate(AXIS_ORDER, start=1):
            writer.writerow(
                {
                    "axis_order": idx,
                    "axis_id": axis,
                    "axis_label_zh": label,
                    "score": "" if axis_scores.get(axis) is None else f"{float(axis_scores[axis]):.12g}",
                }
            )

    score_values = [float(value) for value in axis_scores.values() if value is not None]
    previous_weather = _float_or_none(score_row.get("previous_v1_0b_weather_impact_score"))
    v10c_weather = _float_or_none(score_row.get("v1_0c_weather_impact_score"))
    weather_delta = None
    if previous_weather is not None and v10c_weather is not None:
        weather_delta = v10c_weather - previous_weather

    summary = {
        "case_id": case_id,
        "radar_status": radar_status,
        "scoring_version": SCORING_VERSION,
        "calibrated_from_v1_0b": True,
        "weather_semantics_calibrated": True,
        "current_recommended_display_version": True,
        "previous_recommended_version": PREVIOUS_RECOMMENDED_VERSION,
        "input_axis_score_csv": str(axis_score_csv),
        "input_axis_score_summary_json": str(axis_score_summary_json),
        "axis_definition_csv": str(AXIS_DEFINITION_CSV),
        "axis_definitions_loaded_n": len(axis_definitions),
        "output_png": str(output_png),
        "output_plot_data_csv": str(output_plot_data_csv),
        "axis_order": [{"axis_id": axis, "axis_label_zh": label} for axis, label in AXIS_ORDER],
        "axis_scores": axis_scores,
        "weather_impact_score": axis_scores.get("weather_impact_score"),
        "previous_v1_0b_weather_impact_score": previous_weather,
        "v1_0c_weather_impact_score": v10c_weather,
        "weather_delta_v1_0c_minus_v1_0b": weather_delta,
        "hydrology_topography_review_status": HYDRO_TOPO_REVIEW_STATUS,
        "score_range_min": min(score_values) if score_values else None,
        "score_range_max": max(score_values) if score_values else None,
        "missing_axes": missing_axes,
        "out_of_range_axes": out_of_range_axes,
        "runtime_llm_allowed": False,
        "blocking_issues": blocking_issues,
    }
    output_summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "case_id": case_id,
        "radar_status": radar_status,
        "scoring_version": SCORING_VERSION,
        "calibrated_from_v1_0b": True,
        "weather_semantics_calibrated": True,
        "current_recommended_display_version": True,
        "previous_recommended_version": PREVIOUS_RECOMMENDED_VERSION,
        "png_exists": output_png.exists(),
        "plot_data_exists": output_plot_data_csv.exists(),
        "summary_json_exists": output_summary_json.exists(),
        "axis_count": len([value for value in axis_scores.values() if value is not None]),
        "score_min": min(score_values) if score_values else "",
        "score_max": max(score_values) if score_values else "",
        "weather_impact_score": axis_scores.get("weather_impact_score"),
        "previous_v1_0b_weather_impact_score": previous_weather,
        "v1_0c_weather_impact_score": v10c_weather,
        "weather_delta_v1_0c_minus_v1_0b": weather_delta,
        "hydrology_topography_review_status": HYDRO_TOPO_REVIEW_STATUS,
        "missing_axes": "|".join(missing_axes),
        "out_of_range_axes": "|".join(out_of_range_axes),
        "output_png": str(output_png),
    }


def write_batch_summary(case_rows: list[dict[str, Any]]) -> None:
    batch_dir = OUT_ROOT / "_batch_summary"
    batch_dir.mkdir(parents=True, exist_ok=True)
    out_fp = batch_dir / "thci_radar_v1_0c_case_summary.csv"
    fieldnames = [
        "case_id",
        "radar_status",
        "scoring_version",
        "calibrated_from_v1_0b",
        "weather_semantics_calibrated",
        "current_recommended_display_version",
        "previous_recommended_version",
        "png_exists",
        "plot_data_exists",
        "summary_json_exists",
        "axis_count",
        "score_min",
        "score_max",
        "weather_impact_score",
        "previous_v1_0b_weather_impact_score",
        "v1_0c_weather_impact_score",
        "weather_delta_v1_0c_minus_v1_0b",
        "hydrology_topography_review_status",
        "missing_axes",
        "out_of_range_axes",
        "output_png",
    ]
    with out_fp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(case_rows)


def main() -> int:
    args = parse_args()
    cases = resolve_cases(args)
    axis_definitions = load_axis_definition()
    rows = []
    for case_id in cases:
        row = write_case_outputs(case_id, axis_definitions)
        rows.append(row)
        print(
            f"{case_id}: {row['radar_status']} "
            f"weather={row['weather_impact_score']} "
            f"prev_v1_0b_weather={row['previous_v1_0b_weather_impact_score']} "
            f"delta={row['weather_delta_v1_0c_minus_v1_0b']} "
            f"png={row['output_png']}"
        )
    write_batch_summary(rows)
    print("batch summary:", OUT_ROOT / "_batch_summary" / "thci_radar_v1_0c_case_summary.csv")
    return 1 if any(row["radar_status"] != "PASS" for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
