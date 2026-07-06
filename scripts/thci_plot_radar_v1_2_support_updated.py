# -*- coding: utf-8 -*-
"""Plot THCI v1.2 support-updated radar charts without overwriting v1.0c."""

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


PROJECT_ROOT = Path(r"D:\mountain_work\115_osm")

try:
    import matplotlib.font_manager as fm
    import matplotlib.pyplot as plt
except ModuleNotFoundError:
    venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
        os.execv(str(venv_python), [str(venv_python), __file__, *sys.argv[1:]])
    raise


CASE_DEFAULT = "taichung_guguan_butterfly_valley_waterfall_20260630"
SCORING_VERSION = "v1.2_support_updated"

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

AXIS_SCORE_ROOT = PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_2_support_updated"
OUT_ROOT = PROJECT_ROOT / "outputs" / "thci_radar_v1_2_support_updated"

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
    return parser.parse_args()


def resolve_cases(args: argparse.Namespace) -> list[str]:
    return list(dict.fromkeys(args.case_id or [CASE_DEFAULT]))


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


def float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def load_scores(case_id: str) -> tuple[dict[str, Any], Path]:
    path = AXIS_SCORE_ROOT / case_id / f"{case_id}_thci_axis_scores_v1_2_support_updated.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            return row, path
    raise ValueError(f"CSV is empty: {path}")


def load_score_summary(case_id: str) -> tuple[dict[str, Any], Path]:
    path = AXIS_SCORE_ROOT / case_id / f"{case_id}_thci_axis_score_summary_v1_2_support_updated.json"
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8")), path


def load_axis_definitions() -> dict[str, dict[str, str]]:
    path = CONFIGS["thci_axis_definition_config"]
    out: dict[str, dict[str, str]] = {}
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            axis_id = str(row.get("axis_id", "")).strip()
            if axis_id:
                out[axis_id] = dict(row)
    return out


def validate(axis_scores: dict[str, float | None]) -> tuple[list[str], list[str]]:
    missing = [axis for axis, _ in AXIS_ORDER if axis_scores.get(axis) is None]
    out_of_range = [
        axis
        for axis, _ in AXIS_ORDER
        if axis_scores.get(axis) is not None and not 0.0 <= float(axis_scores[axis]) <= 1.0
    ]
    return missing, out_of_range


def plot_radar(case_id: str, axis_scores: dict[str, float], output_png: Path) -> None:
    labels = [label for _, label in AXIS_ORDER]
    values = [float(axis_scores[axis]) for axis, _ in AXIS_ORDER]
    angles = [idx / float(len(labels)) * 2.0 * math.pi for idx in range(len(labels))]
    angles_closed = angles + angles[:1]
    values_closed = values + values[:1]

    setup_font()
    fig = plt.figure(figsize=(7.2, 7.2))
    ax = fig.add_subplot(111, polar=True)
    ax.plot(angles_closed, values_closed, color="#2F5D50", linewidth=2.5)
    ax.fill(angles_closed, values_closed, color="#2F5D50", alpha=0.18)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], fontsize=9)
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=13)
    ax.grid(color="#b8c2ce", linewidth=0.8)
    ax.set_title(
        f"THCI v1.2 support updated\n{case_id}",
        va="bottom",
        fontsize=15,
        pad=22,
    )
    for angle, value in zip(angles, values):
        ax.text(angle, min(1.06, value + 0.08), f"{value:.2f}", ha="center", va="center", fontsize=10)
    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=180, bbox_inches="tight")
    plt.close(fig)


def write_case(case_id: str, axis_definitions: dict[str, dict[str, str]]) -> dict[str, Any]:
    row, score_csv = load_scores(case_id)
    score_summary, score_summary_json = load_score_summary(case_id)
    axis_scores = {axis: float_or_none(row.get(axis)) for axis, _ in AXIS_ORDER}
    missing, out_of_range = validate(axis_scores)

    out_dir = OUT_ROOT / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    output_png = out_dir / f"{case_id}_thci_radar_v1_2_support_updated.png"
    output_plot_csv = out_dir / f"{case_id}_thci_radar_plot_data_v1_2_support_updated.csv"
    output_summary_json = out_dir / f"{case_id}_thci_radar_summary_v1_2_support_updated.json"

    status = "PASS"
    blocking = []
    if missing:
        blocking.append("missing_axes")
    if out_of_range:
        blocking.append("out_of_range_axes")
    if row.get("scoring_version") != SCORING_VERSION:
        blocking.append("unexpected_scoring_version")
    if blocking:
        status = "FAIL_" + "|".join(blocking)

    numeric_scores = {
        axis: float(axis_scores[axis])
        for axis, _ in AXIS_ORDER
        if axis_scores.get(axis) is not None
    }
    if status == "PASS":
        plot_radar(case_id, numeric_scores, output_png)

    with output_plot_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["axis_order", "axis_id", "axis_label_zh", "score"])
        writer.writeheader()
        for idx, (axis, label) in enumerate(AXIS_ORDER, start=1):
            value = axis_scores.get(axis)
            writer.writerow(
                {
                    "axis_order": idx,
                    "axis_id": axis,
                    "axis_label_zh": label,
                    "score": "" if value is None else f"{float(value):.12g}",
                }
            )

    now = generated_at()
    config_metadata = {key: str(path) for key, path in CONFIGS.items()}
    summary = {
        "case_id": case_id,
        "radar_status": status,
        "scoring_version": SCORING_VERSION,
        "generated_at": now,
        **config_metadata,
        "input_axis_score_csv": str(score_csv),
        "input_axis_score_summary_json": str(score_summary_json),
        "axis_definitions_loaded_n": len(axis_definitions),
        "axis_order": [{"axis_id": axis, "axis_label_zh": label} for axis, label in AXIS_ORDER],
        "axis_scores": axis_scores,
        "score_summary_changed_axes": score_summary.get("changed_axes", []),
        "runtime_llm_allowed": False,
        "missing_axes": missing,
        "out_of_range_axes": out_of_range,
        "blocking_issues": blocking,
        "output_png": str(output_png),
        "output_plot_data_csv": str(output_plot_csv),
    }
    output_summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "case_id": case_id,
        "radar_status": status,
        "scoring_version": SCORING_VERSION,
        "generated_at": now,
        "png_exists": output_png.exists(),
        "output_png": str(output_png),
    }


def main() -> int:
    args = parse_args()
    axis_definitions = load_axis_definitions()
    failures = 0
    for case_id in resolve_cases(args):
        try:
            row = write_case(case_id, axis_definitions)
            if row["radar_status"] != "PASS":
                failures += 1
            print(f"{case_id}: {row['radar_status']} png={row['output_png']}")
        except Exception as exc:
            failures += 1
            print(f"{case_id}: FAIL {exc}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
