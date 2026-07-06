#!/usr/bin/env python3
"""Plot THCI v1.3 weather-terrain candidate simulation radars.

This script reads official-current v1.2 support-updated scores and v1.3
candidate simulation scores. It does not compute official THCI scores, modify
scoring scripts, modify risk-semantics configs, overwrite v1.2 radar outputs,
or produce an official radar.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT_DEFAULT = Path(r"D:\mountain_work\115_osm")
CASE_ID = "taichung_guguan_butterfly_valley_waterfall_20260630"
SCORING_LABEL = "THCI v1.3 weather-terrain candidate simulation"
NOT_OFFICIAL_LABEL = "Candidate simulation only; not official THCI scoring."

try:
    import matplotlib.font_manager as fm
    import matplotlib.pyplot as plt
except ModuleNotFoundError:
    venv_python = PROJECT_ROOT_DEFAULT / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
        os.execv(str(venv_python), [str(venv_python), __file__, *sys.argv[1:]])
    raise


AXIS_ORDER = [
    ("physical_difficulty_score", "Physical"),
    ("technical_difficulty_score", "Technical"),
    ("baseline_hazard_score", "Baseline\nhazard"),
    ("navigation_risk_score", "Navigation"),
    ("support_difficulty_score", "Support"),
    ("weather_impact_score", "Weather\nimpact"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        default=str(PROJECT_ROOT_DEFAULT),
        help="Project root. Defaults to D:\\mountain_work\\115_osm.",
    )
    return parser.parse_args()


def read_one_row(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 1:
        raise ValueError(f"Expected exactly one row in {path}, found {len(rows)}")
    return rows[0]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Expected numeric score, got {value!r}") from None
    if math.isnan(number) or math.isinf(number):
        raise ValueError(f"Invalid numeric score: {value!r}")
    return number


def fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.12g}"
    return str(value)


def generated_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def setup_font() -> None:
    preferred = [
        "Microsoft JhengHei",
        "Microsoft YaHei",
        "Noto Sans CJK TC",
        "Noto Sans CJK JP",
        "SimHei",
        "Arial Unicode MS",
    ]
    available = {font.name for font in fm.fontManager.ttflist}
    for name in preferred:
        if name in available:
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False


def load_inputs(project_root: Path) -> tuple[dict[str, str], dict[str, str], list[dict[str, str]], dict[str, Path]]:
    outputs = project_root / "outputs"
    paths = {
        "v12_scores": outputs
        / "thci_axis_scores_v1_2_support_updated"
        / CASE_ID
        / f"{CASE_ID}_thci_axis_scores_v1_2_support_updated.csv",
        "candidate_scores": outputs
        / "thci_weather_terrain_scoring_v1_3_candidate"
        / CASE_ID
        / f"{CASE_ID}_thci_axis_scores_v1_3_weather_terrain_candidate.csv",
        "candidate_breakdown": outputs
        / "thci_weather_terrain_scoring_v1_3_candidate"
        / CASE_ID
        / f"{CASE_ID}_weather_terrain_candidate_breakdown_v1_3.csv",
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing required inputs:\n" + "\n".join(missing))
    return (
        read_one_row(paths["v12_scores"]),
        read_one_row(paths["candidate_scores"]),
        read_csv_rows(paths["candidate_breakdown"]),
        paths,
    )


def axis_scores(row: dict[str, str]) -> dict[str, float]:
    return {axis: parse_float(row.get(axis)) for axis, _ in AXIS_ORDER}


def validate_scores(scores: dict[str, float], label: str) -> None:
    bad = [axis for axis, value in scores.items() if not 0.0 <= value <= 1.0]
    if bad:
        raise ValueError(f"{label} scores out of range 0..1: {', '.join(bad)}")


def closed(values: list[float]) -> list[float]:
    return values + values[:1]


def radar_geometry() -> tuple[list[str], list[float], list[float]]:
    labels = [label for _, label in AXIS_ORDER]
    angles = [idx / float(len(labels)) * 2.0 * math.pi for idx in range(len(labels))]
    return labels, angles, angles + angles[:1]


def annotate_values(ax: Any, angles: list[float], values: list[float], color: str, radius_offset: float = 0.08) -> None:
    for angle, value in zip(angles, values):
        ax.text(
            angle,
            min(1.08, value + radius_offset),
            f"{value:.2f}",
            ha="center",
            va="center",
            fontsize=9,
            color=color,
        )


def plot_candidate(case_id: str, candidate_scores: dict[str, float], output_png: Path) -> None:
    labels, angles, angles_closed = radar_geometry()
    values = [candidate_scores[axis] for axis, _ in AXIS_ORDER]
    setup_font()
    fig = plt.figure(figsize=(8.4, 8.4))
    ax = fig.add_subplot(111, polar=True)
    ax.plot(angles_closed, closed(values), color="#B24C2E", linewidth=2.6)
    ax.fill(angles_closed, closed(values), color="#B24C2E", alpha=0.18)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], fontsize=9)
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=12)
    ax.grid(color="#b8c2ce", linewidth=0.8)
    ax.set_title(f"{SCORING_LABEL}\n{case_id}", va="bottom", fontsize=14, pad=24)
    fig.text(0.5, 0.045, NOT_OFFICIAL_LABEL, ha="center", fontsize=11, color="#8A2F20")
    annotate_values(ax, angles, values, "#8A2F20")
    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_comparison(
    case_id: str,
    v12_scores: dict[str, float],
    candidate_scores: dict[str, float],
    output_png: Path,
) -> None:
    labels, angles, angles_closed = radar_geometry()
    v12_values = [v12_scores[axis] for axis, _ in AXIS_ORDER]
    candidate_values = [candidate_scores[axis] for axis, _ in AXIS_ORDER]
    setup_font()
    fig = plt.figure(figsize=(8.8, 8.8))
    ax = fig.add_subplot(111, polar=True)
    ax.plot(angles_closed, closed(v12_values), color="#2F5D50", linewidth=2.2, label="v1.2 support updated (current official)")
    ax.fill(angles_closed, closed(v12_values), color="#2F5D50", alpha=0.10)
    ax.plot(angles_closed, closed(candidate_values), color="#B24C2E", linewidth=2.6, linestyle="--", label="v1.3 weather-terrain candidate")
    ax.fill(angles_closed, closed(candidate_values), color="#B24C2E", alpha=0.12)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], fontsize=9)
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=12)
    ax.grid(color="#b8c2ce", linewidth=0.8)
    ax.set_title(f"THCI v1.2 vs v1.3 weather-terrain candidate\n{case_id}", va="bottom", fontsize=14, pad=24)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), frameon=False, fontsize=10)
    fig.text(0.5, 0.045, NOT_OFFICIAL_LABEL, ha="center", fontsize=11, color="#8A2F20")
    annotate_values(ax, angles, candidate_values, "#8A2F20")
    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=180, bbox_inches="tight")
    plt.close(fig)


def output_paths(project_root: Path) -> dict[str, Path]:
    out_dir = project_root / "outputs" / "thci_radar_v1_3_weather_terrain_candidate" / CASE_ID
    return {
        "candidate_png": out_dir / f"{CASE_ID}_thci_radar_v1_3_weather_terrain_candidate.png",
        "comparison_png": out_dir / f"{CASE_ID}_thci_radar_v1_2_vs_v1_3_weather_terrain_candidate.png",
        "plot_data_csv": out_dir / f"{CASE_ID}_thci_radar_plot_data_v1_3_weather_terrain_candidate.csv",
        "report_md": out_dir / f"{CASE_ID}_thci_radar_v1_3_weather_terrain_candidate_report.md",
    }


def write_outputs(
    project_root: Path,
    v12_row: dict[str, str],
    candidate_row: dict[str, str],
    breakdown_rows: list[dict[str, str]],
    input_paths: dict[str, Path],
) -> dict[str, Path]:
    paths = output_paths(project_root)
    existing = [str(path) for path in paths.values() if path.exists()]
    if existing:
        raise FileExistsError("Refusing to overwrite existing candidate radar outputs:\n" + "\n".join(existing))
    paths["candidate_png"].parent.mkdir(parents=True, exist_ok=True)

    v12 = axis_scores(v12_row)
    candidate = axis_scores(candidate_row)
    validate_scores(v12, "v1.2")
    validate_scores(candidate, "v1.3 candidate")

    plot_candidate(CASE_ID, candidate, paths["candidate_png"])
    plot_comparison(CASE_ID, v12, candidate, paths["comparison_png"])

    plot_rows: list[dict[str, Any]] = []
    for idx, (axis, label) in enumerate(AXIS_ORDER, start=1):
        old = v12[axis]
        new = candidate[axis]
        plot_rows.append(
            {
                "axis_order": idx,
                "axis_id": axis,
                "axis_label": label.replace("\n", " "),
                "v1_2_support_updated_score": fmt(old),
                "v1_3_weather_terrain_candidate_score": fmt(new),
                "delta_candidate_minus_v1_2": fmt(new - old),
                "changed": str(abs(new - old) > 1e-12),
                "candidate_simulation_only": "True",
                "not_official_scoring": "True",
            }
        )
    write_csv(
        paths["plot_data_csv"],
        plot_rows,
        [
            "axis_order",
            "axis_id",
            "axis_label",
            "v1_2_support_updated_score",
            "v1_3_weather_terrain_candidate_score",
            "delta_candidate_minus_v1_2",
            "changed",
            "candidate_simulation_only",
            "not_official_scoring",
        ],
    )

    included = [row for row in breakdown_rows if row.get("used_in_candidate_scoring") == "True"]
    excluded = [row for row in breakdown_rows if row.get("used_in_candidate_scoring") != "True"]
    existing_weather = candidate_row.get("weather_impact_score_v1_2", "")
    component = candidate_row.get("weather_terrain_candidate_component", "")
    final_weather = candidate_row.get("weather_impact_score", "")
    delta = candidate_row.get("weather_terrain_candidate_delta", "")

    lines = [
        "# THCI v1.3 Weather-Terrain Candidate Radar Report",
        "",
        f"Case ID: `{CASE_ID}`",
        f"Generated at: `{generated_at()}`",
        "",
        f"**{SCORING_LABEL}**",
        "",
        f"**{NOT_OFFICIAL_LABEL}**",
        "",
        "## Scope",
        "",
        "This report and the PNGs are candidate simulation artifacts only. They do not replace v1.2 support-updated radar outputs and do not represent official THCI scoring.",
        "",
        "## Weather Impact Values",
        "",
        f"- `existing_weather_impact_score_v1_2`: `{existing_weather}`",
        f"- `weather_terrain_candidate_component`: `{component}`",
        f"- `weather_impact_score_v1_3_candidate`: `{final_weather}`",
        f"- `delta`: `{delta}`",
        "",
        "## Six-Axis Difference",
        "",
        "| axis | v1.2 support updated | v1.3 candidate | delta |",
        "|---|---:|---:|---:|",
    ]
    for row in plot_rows:
        lines.append(
            f"| `{row['axis_id']}` | `{row['v1_2_support_updated_score']}` | `{row['v1_3_weather_terrain_candidate_score']}` | `{row['delta_candidate_minus_v1_2']}` |"
        )

    lines.extend(["", "## Included Fields", ""])
    for row in included:
        lines.append(
            f"- `{row.get('thci_field')}`: value `{row.get('value')}`, contribution `{row.get('candidate_contribution')}`, source `{row.get('source_field')}`"
        )

    lines.extend(["", "## Excluded Fields", ""])
    for row in excluded:
        lines.append(
            f"- `{row.get('thci_field')}`: `{row.get('field_status')}`; {row.get('exclusion_reason')}"
        )

    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- candidate radar PNG: `{paths['candidate_png']}`",
            f"- comparison radar PNG: `{paths['comparison_png']}`",
            f"- plot data CSV: `{paths['plot_data_csv']}`",
            "",
            "## Inputs",
            "",
            f"- v1.2 support updated scores: `{input_paths['v12_scores']}`",
            f"- v1.3 weather-terrain candidate scores: `{input_paths['candidate_scores']}`",
            f"- candidate breakdown: `{input_paths['candidate_breakdown']}`",
        ]
    )
    paths["report_md"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    return paths


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    v12_row, candidate_row, breakdown_rows, input_paths = load_inputs(project_root)
    paths = write_outputs(project_root, v12_row, candidate_row, breakdown_rows, input_paths)
    print(json.dumps({key: str(value) for key, value in paths.items()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
