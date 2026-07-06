# -*- coding: utf-8 -*-
"""Plot deterministic THCI v1.0a six-axis radar charts.

The script reads precomputed THCI v1.0a axis scores only. It does not
recalculate scores and does not call any runtime LLM.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(r"C:\mountain_work\115_osm")

AXIS_DEFINITION_CSV = (
    PROJECT_ROOT / "configs" / "risk_semantics" / "thci_axis_definition_v1_2_support_updated.csv"
)
AXIS_SCORE_ROOT = PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_0a"
OUT_ROOT = PROJECT_ROOT / "outputs" / "thci_radar_v1_0a"

SCORING_VERSION = "v1.0a"

CASES = [
    "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b",
    "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b",
    "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b",
    "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b",
]

AXIS_ORDER = [
    "physical_difficulty_score",
    "technical_difficulty_score",
    "baseline_hazard_score",
    "navigation_risk_score",
    "support_difficulty_score",
    "weather_impact_score",
]

DEFAULT_AXIS_LABELS_ZH = {
    "physical_difficulty_score": "體力難度",
    "technical_difficulty_score": "技術難度",
    "baseline_hazard_score": "基礎危害",
    "navigation_risk_score": "迷航風險",
    "support_difficulty_score": "支援不易",
    "weather_impact_score": "天候影響",
}


def load_axis_definition() -> dict[str, dict[str, str]]:
    """Load THCI axis definitions keyed by axis_id."""
    if not AXIS_DEFINITION_CSV.exists():
        raise FileNotFoundError(AXIS_DEFINITION_CSV)
    df = pd.read_csv(AXIS_DEFINITION_CSV, low_memory=False)
    required = {"axis_id", "display_name_zh"}
    missing = required.difference(df.columns)
    if missing:
        raise KeyError(f"Axis definition missing columns: {sorted(missing)}")
    return {
        str(row["axis_id"]): {
            "display_name_zh": str(row.get("display_name_zh", "")),
            "display_name_en": str(row.get("display_name_en", "")),
        }
        for _, row in df.iterrows()
    }


def load_axis_scores(case_id: str) -> tuple[pd.DataFrame, Path]:
    """Load one case's precomputed THCI v1.0a axis score CSV."""
    case_dir = AXIS_SCORE_ROOT / case_id
    score_csv = case_dir / f"{case_id}_thci_axis_scores_v1_0a.csv"
    if not score_csv.exists():
        raise FileNotFoundError(score_csv)
    df = pd.read_csv(score_csv, low_memory=False)
    if df.empty:
        raise ValueError(f"Axis score CSV is empty: {score_csv}")
    return df, score_csv


def load_axis_score_summary(case_id: str) -> tuple[dict[str, Any], Path]:
    """Load one case's THCI v1.0a axis score summary JSON."""
    case_dir = AXIS_SCORE_ROOT / case_id
    score_summary_json = case_dir / f"{case_id}_thci_axis_score_summary_v1_0a.json"
    if not score_summary_json.exists():
        raise FileNotFoundError(score_summary_json)
    with score_summary_json.open("r", encoding="utf-8") as handle:
        summary = json.load(handle)
    return summary, score_summary_json


def validate_axis_scores(score_df: pd.DataFrame) -> dict[str, Any]:
    """Validate required axis score columns and numeric 0..1 values."""
    row = score_df.iloc[0]
    missing_axes = [axis for axis in AXIS_ORDER if axis not in score_df.columns]
    non_numeric_axes: list[str] = []
    out_of_range_axes: list[str] = []
    axis_scores: dict[str, float | None] = {}

    for axis in AXIS_ORDER:
        if axis in missing_axes:
            axis_scores[axis] = None
            continue
        raw = row[axis]
        try:
            value = float(raw)
        except (TypeError, ValueError):
            non_numeric_axes.append(axis)
            axis_scores[axis] = None
            continue
        if math.isnan(value):
            non_numeric_axes.append(axis)
            axis_scores[axis] = None
            continue
        axis_scores[axis] = value
        if value < 0.0 or value > 1.0:
            out_of_range_axes.append(axis)

    numeric_values = [value for value in axis_scores.values() if value is not None]
    return {
        "axis_scores": axis_scores,
        "missing_axes": missing_axes,
        "non_numeric_axes": non_numeric_axes,
        "out_of_range_axes": out_of_range_axes,
        "score_min": min(numeric_values) if numeric_values else None,
        "score_max": max(numeric_values) if numeric_values else None,
        "ok": not missing_axes and not non_numeric_axes and not out_of_range_axes,
    }


def setup_chinese_font() -> str:
    """Configure matplotlib for Traditional Chinese labels on Windows."""
    preferred = [
        "Microsoft JhengHei",
        "Microsoft YaHei",
        "Noto Sans CJK TC",
        "Noto Sans CJK SC",
        "SimHei",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    installed = {font.name for font in fm.fontManager.ttflist}
    chosen = next((name for name in preferred if name in installed), "DejaVu Sans")
    plt.rcParams["font.family"] = chosen
    plt.rcParams["axes.unicode_minus"] = False
    return chosen


def plot_radar(
    case_id: str,
    axis_scores: dict[str, float | None],
    axis_definitions: dict[str, dict[str, str]],
    output_png: Path,
    dpi: int = 180,
) -> None:
    """Plot and save one THCI v1.0a six-axis radar chart."""
    labels = [
        axis_definitions.get(axis, {}).get("display_name_zh")
        or DEFAULT_AXIS_LABELS_ZH.get(axis, axis)
        for axis in AXIS_ORDER
    ]
    values = [axis_scores[axis] for axis in AXIS_ORDER]
    if any(value is None for value in values):
        raise ValueError(f"Cannot plot radar with missing values for {case_id}")
    numeric_values = [float(value) for value in values]

    angles = np.linspace(0, 2 * np.pi, len(AXIS_ORDER), endpoint=False).tolist()
    closed_angles = angles + angles[:1]
    closed_values = numeric_values + numeric_values[:1]

    fig = plt.figure(figsize=(7.2, 7.2))
    ax = fig.add_subplot(111, polar=True)
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)

    ax.plot(closed_angles, closed_values, color="#28666e", linewidth=2.2)
    ax.fill(closed_angles, closed_values, color="#4aa3a2", alpha=0.24)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], fontsize=9)
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=12)
    ax.grid(color="#b8c0c8", linewidth=0.8)

    for angle, value in zip(angles, numeric_values):
        ax.text(
            angle,
            min(1.08, value + 0.08),
            f"{value:.2f}",
            ha="center",
            va="center",
            fontsize=10,
        )

    ax.set_title(
        f"THCI v1.0a calibrated with proxy features\n{case_id}",
        va="bottom",
        fontsize=13,
        pad=26,
    )
    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_png, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def _summary_count(summary: dict[str, Any], key: str) -> int:
    value = summary.get(key, 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def write_case_outputs(
    case_id: str,
    axis_definitions: dict[str, dict[str, str]],
    font_name: str,
) -> dict[str, Any]:
    """Validate, plot, and write all per-case radar outputs."""
    score_df, score_csv = load_axis_scores(case_id)
    axis_score_summary, score_summary_json = load_axis_score_summary(case_id)
    validation = validate_axis_scores(score_df)

    out_dir = OUT_ROOT / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    output_png = out_dir / f"{case_id}_thci_radar_v1_0a.png"
    output_plot_data_csv = out_dir / f"{case_id}_thci_radar_plot_data_v1_0a.csv"
    output_summary_json = out_dir / f"{case_id}_thci_radar_summary_v1_0a.json"

    scoring_version_ok = axis_score_summary.get("scoring_version") == SCORING_VERSION
    calibrated_ok = axis_score_summary.get("calibrated_from_v1_0") is True
    radar_status = "PASS" if validation["ok"] and scoring_version_ok and calibrated_ok else "FAIL"

    proxy_features_n = _summary_count(axis_score_summary, "proxy_features_n")
    missing_features_n = _summary_count(axis_score_summary, "missing_features_n")

    plot_rows = []
    for idx, axis in enumerate(AXIS_ORDER, start=1):
        plot_rows.append(
            {
                "axis_order": idx,
                "axis_id": axis,
                "display_name_zh": axis_definitions.get(axis, {}).get("display_name_zh")
                or DEFAULT_AXIS_LABELS_ZH.get(axis, axis),
                "score": validation["axis_scores"].get(axis),
            }
        )
    pd.DataFrame(plot_rows).to_csv(output_plot_data_csv, index=False, encoding="utf-8-sig")

    if radar_status == "PASS":
        plot_radar(case_id, validation["axis_scores"], axis_definitions, output_png)
    elif output_png.exists():
        output_png.unlink()

    summary = {
        "case_id": case_id,
        "radar_status": radar_status,
        "scoring_version": SCORING_VERSION,
        "calibrated_from_v1_0": True,
        "uses_proxy_features": True,
        "input_axis_score_csv": str(score_csv),
        "input_axis_score_summary_json": str(score_summary_json),
        "axis_definition_csv": str(AXIS_DEFINITION_CSV),
        "output_png": str(output_png),
        "output_plot_data_csv": str(output_plot_data_csv),
        "output_summary_json": str(output_summary_json),
        "axis_order": AXIS_ORDER,
        "axis_scores": validation["axis_scores"],
        "score_range_min": validation["score_min"],
        "score_range_max": validation["score_max"],
        "missing_axes": validation["missing_axes"],
        "non_numeric_axes": validation["non_numeric_axes"],
        "out_of_range_axes": validation["out_of_range_axes"],
        "proxy_features_n": proxy_features_n,
        "missing_features_n": missing_features_n,
        "runtime_llm_allowed": False,
        "matplotlib_font": font_name,
        "source_scoring_version": axis_score_summary.get("scoring_version"),
        "source_calibrated_from_v1_0": axis_score_summary.get("calibrated_from_v1_0"),
    }
    output_summary_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "case_id": case_id,
        "radar_status": radar_status,
        "scoring_version": SCORING_VERSION,
        "calibrated_from_v1_0": True,
        "uses_proxy_features": True,
        "png_exists": output_png.exists(),
        "plot_data_exists": output_plot_data_csv.exists(),
        "summary_json_exists": output_summary_json.exists(),
        "axis_count": len(AXIS_ORDER) - len(validation["missing_axes"]),
        "score_min": validation["score_min"],
        "score_max": validation["score_max"],
        "proxy_features_n": proxy_features_n,
        "missing_features_n": missing_features_n,
        "missing_axes": "|".join(validation["missing_axes"]),
        "out_of_range_axes": "|".join(validation["out_of_range_axes"]),
        "output_png": str(output_png),
    }


def write_batch_summary(case_rows: list[dict[str, Any]]) -> None:
    """Write THCI v1.0a radar batch summary CSV."""
    batch_dir = OUT_ROOT / "_batch_summary"
    batch_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(case_rows).to_csv(
        batch_dir / "thci_radar_v1_0a_case_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )


def main() -> int:
    axis_definitions = load_axis_definition()
    font_name = setup_chinese_font()
    case_rows = []
    for case_id in CASES:
        row = write_case_outputs(case_id, axis_definitions, font_name)
        case_rows.append(row)
        print(
            f"{case_id}: {row['radar_status']} "
            f"png={row['png_exists']} score_min={row['score_min']} "
            f"score_max={row['score_max']} proxy_features_n={row['proxy_features_n']} "
            f"missing_features_n={row['missing_features_n']}"
        )
    write_batch_summary(case_rows)
    print("batch summary:", OUT_ROOT / "_batch_summary" / "thci_radar_v1_0a_case_summary.csv")
    return 1 if any(row["radar_status"] == "FAIL" for row in case_rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
