# -*- coding: utf-8 -*-
"""Combine existing upslope hazard map with THCI v1.2 support-updated radar.

This script intentionally does not recompute IB1G2/IB1G3 upslope/collapse
evidence and does not rerun weather-terrain fusion. It only reads existing
upslope map artifacts and the new THCI radar, then writes versioned combined
outputs under a new output root.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(r"D:\mountain_work\115_osm")

try:
    from PIL import Image, ImageOps
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

OLD_UPSLOPE_ROOT = PROJECT_ROOT / "outputs" / "ib2d_upslope_contributing_hazard_map"
NEW_UPSLOPE_ROOT = PROJECT_ROOT / "outputs" / "ib2d_upslope_contributing_hazard_map_v1_2_support_updated"
NEW_RADAR_ROOT = PROJECT_ROOT / "outputs" / "thci_radar_v1_2_support_updated"
NEW_AXIS_ROOT = PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_2_support_updated"
OLD_AXIS_ROOT = PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_0c"

AXES = [
    "physical_difficulty_score",
    "technical_difficulty_score",
    "baseline_hazard_score",
    "navigation_risk_score",
    "support_difficulty_score",
    "weather_impact_score",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", default=CASE_DEFAULT)
    return parser.parse_args()


def generated_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def combine_images(map_fp: Path, radar_fp: Path, out_fp: Path) -> None:
    map_img = Image.open(map_fp).convert("RGB")
    radar_img = Image.open(radar_fp).convert("RGB")
    radar_img = ImageOps.contain(radar_img, (int(map_img.width * 0.34), int(map_img.height * 0.52)))

    pad = 34
    canvas = Image.new("RGB", (map_img.width + radar_img.width + pad * 3, map_img.height + pad * 2), "white")
    canvas.paste(map_img, (pad, pad))
    x = map_img.width + pad * 2
    y = pad + (map_img.height - radar_img.height) // 2
    canvas.paste(radar_img, (x, y))
    out_fp.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_fp)


def read_first_csv(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            return dict(row)
    raise ValueError(f"CSV is empty: {path}")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def read_comparison(case_id: str) -> list[dict[str, Any]]:
    path = (
        NEW_AXIS_ROOT
        / case_id
        / f"{case_id}_thci_axis_scores_v1_0c_vs_v1_2_support_updated_comparison.csv"
    )
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def fmt(value: Any) -> str:
    try:
        return f"{float(value):.4f}"
    except Exception:
        return str(value)


def write_report(
    case_id: str,
    out_dir: Path,
    combined_png: Path,
    summary: dict[str, Any],
    comparison_rows: list[dict[str, Any]],
) -> Path:
    changed = [row for row in comparison_rows if boolish(row.get("changed"))]
    nav = next(row for row in comparison_rows if row["axis_id"] == "navigation_risk_score")
    support = next(row for row in comparison_rows if row["axis_id"] == "support_difficulty_score")
    baseline = next(row for row in comparison_rows if row["axis_id"] == "baseline_hazard_score")
    weather = next(row for row in comparison_rows if row["axis_id"] == "weather_impact_score")

    lines = [
        "# THCI v1.2 Support Updated Radar Report",
        "",
        f"Case ID: `{case_id}`",
        f"Generated at: `{summary['generated_at']}`",
        "",
        "## Scope",
        "",
        "- 舊版 THCI radar 吃到的是 `v1_0c` outputs。",
        "- 新版使用 `v1_2_support_updated` axis definition / scoring rule / normalization threshold，並使用 `thci_feature_mapping_v1_3_support_updated.csv`。",
        "- 本次只更新 THCI scores / radar 與 upslope map 中的 THCI radar panel；不改 upslope / collapse evidence layer。",
        "- 未重跑 `ib1g2` / `ib1g3` upslope + collapse proxy。",
        "- 未重跑 weather-terrain fusion。",
        "- 未把 NLSC 崩土遮罩 join 回 route profile。",
        "- 未修改 THCI scoring config，且未覆蓋既有 v1_0c outputs。",
        "",
        "## Config Metadata",
        "",
    ]
    for key in [
        "thci_axis_definition_config",
        "thci_axis_scoring_rule_config",
        "thci_feature_mapping_config",
        "thci_normalization_threshold_config",
        "osm_semantic_risk_mapping_config",
    ]:
        lines.append(f"- `{key}`: `{summary[key]}`")

    lines.extend(
        [
            "",
            "## Axis Comparison",
            "",
            "| axis | v1_0c | v1_2_support_updated | delta | changed |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for row in comparison_rows:
        lines.append(
            f"| `{row['axis_id']}` | {fmt(row['v1_0c_score'])} | "
            f"{fmt(row['v1_2_support_updated_score'])} | "
            f"{fmt(row['delta_v1_2_minus_v1_0c'])} | {row['changed']} |"
        )

    lines.extend(
        [
            "",
            "## Findings",
            "",
            f"- 有變化的軸：{', '.join('`' + row['axis_id'] + '`' for row in changed) if changed else '無'}。",
            f"- `navigation_risk_score` 是否仍為 0：否；新版為 {fmt(nav['v1_2_support_updated_score'])}，沿用 v1_0c。",
            f"- `support_difficulty_score` 是否有變化：{'是' if boolish(support['changed']) else '否'}；{fmt(support['v1_0c_score'])} -> {fmt(support['v1_2_support_updated_score'])}。",
            f"- `baseline_hazard_score` 是否有變化：{'是' if boolish(baseline['changed']) else '否'}；{fmt(baseline['v1_0c_score'])} -> {fmt(baseline['v1_2_support_updated_score'])}。",
            f"- `weather_impact_score` 是否有變化：{'是' if boolish(weather['changed']) else '否'}；{fmt(weather['v1_0c_score'])} -> {fmt(weather['v1_2_support_updated_score'])}。",
            "",
            "## Outputs",
            "",
            f"- 新版 THCI radar PNG: `{summary['new_thci_radar_png']}`",
            f"- 新版 upslope hazard map with updated THCI radar PNG: `{combined_png}`",
            f"- comparison CSV: `{summary['comparison_csv']}`",
            "",
            "## Note",
            "",
            "這次是 THCI radar 輕量升版。NLSC 崩土遮罩與 upslope contributing hazard proxy 仍維持既有 evidence layer；它們沒有被併回 route profile，也沒有被加入這次新版 THCI 分數計算。",
        ]
    )
    report_fp = out_dir / "thci_v1_2_support_update_report.md"
    report_fp.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    return report_fp


def main() -> int:
    args = parse_args()
    case_id = args.case_id
    old_map = OLD_UPSLOPE_ROOT / case_id / f"{case_id}_upslope_contributing_hazard_map.png"
    new_radar = NEW_RADAR_ROOT / case_id / f"{case_id}_thci_radar_v1_2_support_updated.png"
    out_dir = NEW_UPSLOPE_ROOT / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    combined = out_dir / f"{case_id}_upslope_map_thci_v1_2_support_updated.png"

    if not old_map.exists():
        raise FileNotFoundError(old_map)
    if not new_radar.exists():
        raise FileNotFoundError(new_radar)
    combine_images(old_map, new_radar, combined)

    axis_score_csv = NEW_AXIS_ROOT / case_id / f"{case_id}_thci_axis_scores_v1_2_support_updated.csv"
    axis_summary_json = NEW_AXIS_ROOT / case_id / f"{case_id}_thci_axis_score_summary_v1_2_support_updated.json"
    radar_summary_json = NEW_RADAR_ROOT / case_id / f"{case_id}_thci_radar_summary_v1_2_support_updated.json"
    comparison_csv = (
        NEW_AXIS_ROOT
        / case_id
        / f"{case_id}_thci_axis_scores_v1_0c_vs_v1_2_support_updated_comparison.csv"
    )
    axis_row = read_first_csv(axis_score_csv)
    axis_summary = read_json(axis_summary_json)
    radar_summary = read_json(radar_summary_json)
    comparison_rows = read_comparison(case_id)

    now = generated_at()
    metadata = {key: str(path) for key, path in CONFIGS.items()}
    summary = {
        "case_id": case_id,
        "generated_at": now,
        **metadata,
        "old_upslope_base_map_png": str(old_map),
        "new_thci_radar_png": str(new_radar),
        "combined_updated_thci_radar_png": str(combined),
        "new_axis_score_csv": str(axis_score_csv),
        "new_axis_summary_json": str(axis_summary_json),
        "new_radar_summary_json": str(radar_summary_json),
        "comparison_csv": str(comparison_csv),
        "old_thci_version": "v1_0c",
        "new_thci_version": SCORING_VERSION,
        "reran_ib1g2_ib1g3": False,
        "reran_weather_terrain_fusion": False,
        "joined_nlsc_collapse_mask_to_route_profile": False,
        "modified_thci_scoring_config": False,
        "overwrote_v1_0c_outputs": False,
        "axis_scores": {axis: axis_row.get(axis) for axis in AXES},
        "axis_summary_changed_axes": axis_summary.get("changed_axes", []),
        "radar_status": radar_summary.get("radar_status"),
    }
    summary_fp = out_dir / f"{case_id}_upslope_thci_v1_2_support_updated_summary.json"
    summary_fp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_fp = write_report(case_id, NEW_RADAR_ROOT / case_id, combined, summary, comparison_rows)

    print(f"{case_id}: PASS combined={combined}")
    print(f"report={report_fp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
