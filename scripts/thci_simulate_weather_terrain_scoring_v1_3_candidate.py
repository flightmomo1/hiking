#!/usr/bin/env python3
"""Simulate THCI v1.3 weather-terrain candidate scoring.

This script is intentionally separate from the official THCI scoring pipeline.
It reads the v1.2 support-updated axis scores and the v1.3 weather-terrain
adapter output, then writes candidate-only comparison artifacts. It does not
modify scoring scripts, risk-semantics configs, v1.2 outputs, or radar outputs.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CASE_ID = "taichung_guguan_butterfly_valley_waterfall_20260630"
SCRIPT_VERSION = "thci_weather_terrain_scoring_v1_3_candidate"

AXES = [
    "physical_difficulty_score",
    "technical_difficulty_score",
    "baseline_hazard_score",
    "navigation_risk_score",
    "support_difficulty_score",
    "weather_impact_score",
]

ALLOWED_FIELDS = {
    "rainwash_or_convergence_sensitivity",
    "weather_terrain_fusion_rainwash_axis_score",
    "fusion_hotspot_overlap_ratio",
}

WEIGHTS = {
    "rainwash_or_convergence_sensitivity": 0.40,
    "weather_terrain_fusion_rainwash_axis_score": 0.45,
    "fusion_hotspot_overlap_ratio_normalized": 0.15,
}

SIMULATION_HOTSPOT_RATIO_THRESHOLD = 0.30


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.12g}"
    return str(value)


def clip(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def require_one_row(path: Path) -> dict[str, str]:
    rows = read_csv_rows(path)
    if len(rows) != 1:
        raise ValueError(f"Expected exactly one row in {path}, found {len(rows)}")
    return rows[0]


def field_map(adapter_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    by_field: dict[str, dict[str, str]] = {}
    for row in adapter_rows:
        field = row.get("thci_field", "")
        if field:
            by_field[field] = row
    return by_field


def ensure_required(paths: list[Path]) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing required inputs:\n" + "\n".join(missing))


def build_simulation(project_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    out = project_root / "outputs"
    v12_csv = (
        out
        / "thci_axis_scores_v1_2_support_updated"
        / CASE_ID
        / f"{CASE_ID}_thci_axis_scores_v1_2_support_updated.csv"
    )
    adapter_csv = (
        out
        / "thci_weather_terrain_adapter_v1_3"
        / CASE_ID
        / f"{CASE_ID}_thci_weather_terrain_route_level_v1_3.csv"
    )
    ensure_required([v12_csv, adapter_csv])

    v12 = require_one_row(v12_csv)
    adapter_rows = read_csv_rows(adapter_csv)
    fields = field_map(adapter_rows)

    missing_allowed = sorted(field for field in ALLOWED_FIELDS if field not in fields)
    if missing_allowed:
        raise ValueError("Adapter is missing allowed candidate fields: " + ", ".join(missing_allowed))

    existing_weather = parse_float(v12.get("weather_impact_score"))
    if existing_weather is None:
        raise ValueError("v1.2 score file is missing numeric weather_impact_score")

    rainwash = parse_float(fields["rainwash_or_convergence_sensitivity"].get("value"))
    fusion_rainwash = parse_float(fields["weather_terrain_fusion_rainwash_axis_score"].get("value"))
    hotspot_ratio = parse_float(fields["fusion_hotspot_overlap_ratio"].get("value"))
    if rainwash is None or fusion_rainwash is None or hotspot_ratio is None:
        raise ValueError("Allowed candidate fields must have numeric values")

    hotspot_normalized = clip(hotspot_ratio / SIMULATION_HOTSPOT_RATIO_THRESHOLD)
    rainwash_component = WEIGHTS["rainwash_or_convergence_sensitivity"] * rainwash
    fusion_component = WEIGHTS["weather_terrain_fusion_rainwash_axis_score"] * fusion_rainwash
    hotspot_component = WEIGHTS["fusion_hotspot_overlap_ratio_normalized"] * hotspot_normalized
    weather_terrain_component = clip(rainwash_component + fusion_component + hotspot_component)
    final_weather = max(existing_weather, weather_terrain_component)
    delta_weather = final_weather - existing_weather
    generated_at = datetime.now(timezone.utc).isoformat()

    candidate = dict(v12)
    candidate.update(
        {
            "status": "SIMULATION_ONLY",
            "scoring_version": "v1.3_weather_terrain_candidate",
            "previous_scoring_version": v12.get("scoring_version", "v1.2_support_updated"),
            "generated_at": generated_at,
            "weather_impact_score": fmt(final_weather),
            "weather_impact_score_v1_2": fmt(existing_weather),
            "weather_terrain_candidate_component": fmt(weather_terrain_component),
            "weather_terrain_candidate_delta": fmt(delta_weather),
            "candidate_formula": (
                "max(existing_weather_impact_score_v1_2, "
                "0.40*rainwash_or_convergence_sensitivity + "
                "0.45*weather_terrain_fusion_rainwash_axis_score + "
                "0.15*clip(fusion_hotspot_overlap_ratio/0.30,0,1))"
            ),
            "simulation_only": "True",
            "produced_official_thci_radar": "False",
            "modified_scoring_script": "False",
            "modified_risk_semantics_config": "False",
            "input_v1_2_scores_csv": str(v12_csv),
            "input_weather_terrain_adapter_csv": str(adapter_csv),
        }
    )

    comparison_rows: list[dict[str, Any]] = []
    for axis in AXES:
        old = parse_float(v12.get(axis), 0.0) or 0.0
        new = final_weather if axis == "weather_impact_score" else old
        comparison_rows.append(
            {
                "case_id": CASE_ID,
                "axis": axis,
                "v1_2_support_updated_score": fmt(old),
                "v1_3_weather_terrain_candidate_score": fmt(new),
                "delta_candidate_minus_v1_2": fmt(new - old),
                "changed": str(abs(new - old) > 1e-12),
                "simulation_only": "True",
                "notes": "Candidate weather-terrain simulation updates only weather_impact_score." if axis == "weather_impact_score" else "Unchanged from v1.2 support updated.",
            }
        )

    breakdown_rows: list[dict[str, Any]] = []
    contribution_by_field = {
        "rainwash_or_convergence_sensitivity": rainwash_component,
        "weather_terrain_fusion_rainwash_axis_score": fusion_component,
        "fusion_hotspot_overlap_ratio": hotspot_component,
    }
    normalized_by_field = {
        "rainwash_or_convergence_sensitivity": rainwash,
        "weather_terrain_fusion_rainwash_axis_score": fusion_rainwash,
        "fusion_hotspot_overlap_ratio": hotspot_normalized,
    }
    weight_by_field = {
        "rainwash_or_convergence_sensitivity": WEIGHTS["rainwash_or_convergence_sensitivity"],
        "weather_terrain_fusion_rainwash_axis_score": WEIGHTS["weather_terrain_fusion_rainwash_axis_score"],
        "fusion_hotspot_overlap_ratio": WEIGHTS["fusion_hotspot_overlap_ratio_normalized"],
    }

    for row in adapter_rows:
        field = row.get("thci_field", "")
        status = row.get("field_status", "")
        used = field in ALLOWED_FIELDS and status == "scoring_ready_candidate"
        if used:
            exclusion_reason = ""
        elif status == "review_only":
            exclusion_reason = "review_only field excluded from candidate scoring"
        elif status == "planned":
            exclusion_reason = "planned field excluded from candidate scoring"
        elif status != "scoring_ready_candidate":
            exclusion_reason = f"{status or 'unknown'} field excluded from candidate scoring"
        else:
            exclusion_reason = "not in allowlist for candidate formula"

        breakdown_rows.append(
            {
                "case_id": CASE_ID,
                "thci_field": field,
                "value": row.get("value", ""),
                "field_status": status,
                "used_in_candidate_scoring": str(used),
                "candidate_weight": fmt(weight_by_field.get(field)),
                "normalized_value_used": fmt(normalized_by_field.get(field)),
                "candidate_contribution": fmt(contribution_by_field.get(field)),
                "existing_weather_impact_score_v1_2": fmt(existing_weather),
                "weather_terrain_candidate_component": fmt(weather_terrain_component),
                "final_candidate_weather_impact_score": fmt(final_weather),
                "delta": fmt(delta_weather),
                "source_file": row.get("source_file", ""),
                "source_field": row.get("source_field", ""),
                "double_count_guard_required": row.get("double_count_guard_required", ""),
                "exclusion_reason": exclusion_reason,
                "notes": row.get("notes", ""),
            }
        )

    diagnostics = {
        "case_id": CASE_ID,
        "generated_at": generated_at,
        "script_version": SCRIPT_VERSION,
        "existing_weather_impact_score_v1_2": existing_weather,
        "weather_terrain_candidate_component": weather_terrain_component,
        "final_candidate_weather_impact_score": final_weather,
        "delta": delta_weather,
        "allowed_fields_used": sorted(
            row["thci_field"] for row in breakdown_rows if row["used_in_candidate_scoring"] == "True"
        ),
        "excluded_fields": [
            {
                "thci_field": row["thci_field"],
                "field_status": row["field_status"],
                "reason": row["exclusion_reason"],
            }
            for row in breakdown_rows
            if row["used_in_candidate_scoring"] != "True"
        ],
        "formula": {
            "label": "simulation_only_candidate_formula",
            "rainwash_weight": WEIGHTS["rainwash_or_convergence_sensitivity"],
            "fusion_rainwash_weight": WEIGHTS["weather_terrain_fusion_rainwash_axis_score"],
            "hotspot_overlap_weight": WEIGHTS["fusion_hotspot_overlap_ratio_normalized"],
            "hotspot_overlap_normalization": "clip(fusion_hotspot_overlap_ratio / 0.30, 0, 1)",
            "hotspot_threshold_note": "0.30 is a simulation threshold, not an official THCI threshold.",
            "final_weather_impact_score": "max(existing_weather_impact_score_v1_2, weather_terrain_candidate_component)",
        },
        "inputs": {
            "v1_2_scores_csv": str(v12_csv),
            "adapter_csv": str(adapter_csv),
        },
    }
    return [candidate], comparison_rows, breakdown_rows, diagnostics


def write_outputs(
    project_root: Path,
    candidate_rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    breakdown_rows: list[dict[str, Any]],
    diagnostics: dict[str, Any],
) -> dict[str, Path]:
    out_dir = project_root / "outputs" / "thci_weather_terrain_scoring_v1_3_candidate" / CASE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "candidate_csv": out_dir / f"{CASE_ID}_thci_axis_scores_v1_3_weather_terrain_candidate.csv",
        "comparison_csv": out_dir / f"{CASE_ID}_thci_v1_2_vs_v1_3_weather_terrain_candidate_comparison.csv",
        "breakdown_csv": out_dir / f"{CASE_ID}_weather_terrain_candidate_breakdown_v1_3.csv",
        "report_md": out_dir / f"{CASE_ID}_thci_weather_terrain_candidate_report_v1_3.md",
    }
    existing = [str(path) for path in outputs.values() if path.exists()]
    if existing:
        raise FileExistsError("Refusing to overwrite existing candidate outputs:\n" + "\n".join(existing))

    candidate_fields = list(candidate_rows[0].keys())
    write_csv(outputs["candidate_csv"], candidate_rows, candidate_fields)

    write_csv(
        outputs["comparison_csv"],
        comparison_rows,
        [
            "case_id",
            "axis",
            "v1_2_support_updated_score",
            "v1_3_weather_terrain_candidate_score",
            "delta_candidate_minus_v1_2",
            "changed",
            "simulation_only",
            "notes",
        ],
    )

    write_csv(
        outputs["breakdown_csv"],
        breakdown_rows,
        [
            "case_id",
            "thci_field",
            "value",
            "field_status",
            "used_in_candidate_scoring",
            "candidate_weight",
            "normalized_value_used",
            "candidate_contribution",
            "existing_weather_impact_score_v1_2",
            "weather_terrain_candidate_component",
            "final_candidate_weather_impact_score",
            "delta",
            "source_file",
            "source_field",
            "double_count_guard_required",
            "exclusion_reason",
            "notes",
        ],
    )

    lines = [
        "# THCI v1.3 Weather-Terrain Candidate Scoring Simulation",
        "",
        f"Case ID: `{CASE_ID}`",
        f"Generated at: `{diagnostics['generated_at']}`",
        "",
        "## Scope",
        "",
        "This is a simulation-only candidate scoring run. It does not modify the official THCI scoring scripts, does not modify risk-semantics configs, does not overwrite v1.2 outputs, and does not produce an official THCI radar.",
        "",
        "## Candidate Formula",
        "",
        "`weather_terrain_candidate_component = 0.40 * rainwash_or_convergence_sensitivity + 0.45 * weather_terrain_fusion_rainwash_axis_score + 0.15 * fusion_hotspot_overlap_ratio_normalized`",
        "",
        "`fusion_hotspot_overlap_ratio_normalized = clip(fusion_hotspot_overlap_ratio / 0.30, 0, 1)`",
        "",
        "`weather_impact_score_v1_3_candidate = max(existing_weather_impact_score_v1_2, weather_terrain_candidate_component)`",
        "",
        "`0.30` is a simulation threshold, not an official THCI threshold.",
        "",
        "## Weather Impact Result",
        "",
        f"- existing v1.2 `weather_impact_score`: `{fmt(diagnostics['existing_weather_impact_score_v1_2'])}`",
        f"- candidate weather-terrain component: `{fmt(diagnostics['weather_terrain_candidate_component'])}`",
        f"- final v1.3 candidate `weather_impact_score`: `{fmt(diagnostics['final_candidate_weather_impact_score'])}`",
        f"- delta: `{fmt(diagnostics['delta'])}`",
        "",
        "## Fields Used",
        "",
    ]
    for field in diagnostics["allowed_fields_used"]:
        lines.append(f"- `{field}`")

    lines.extend(["", "## Fields Excluded", ""])
    for item in diagnostics["excluded_fields"]:
        lines.append(f"- `{item['thci_field']}`: `{item['field_status']}`; {item['reason']}")

    lines.extend(
        [
            "",
            "## Breakdown",
            "",
            "| field | value | status | used | contribution | guard |",
            "|---|---:|---|---:|---:|---:|",
        ]
    )
    for row in breakdown_rows:
        lines.append(
            f"| `{row['thci_field']}` | `{row['value']}` | `{row['field_status']}` | `{row['used_in_candidate_scoring']}` | `{row['candidate_contribution']}` | `{row['double_count_guard_required']}` |"
        )

    lines.extend(
        [
            "",
            "## Input Files",
            "",
            f"- v1.2 support updated scores: `{diagnostics['inputs']['v1_2_scores_csv']}`",
            f"- v1.3 weather-terrain adapter: `{diagnostics['inputs']['adapter_csv']}`",
        ]
    )
    outputs["report_md"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Project root. Defaults to the parent of scripts/.",
    )
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    candidate_rows, comparison_rows, breakdown_rows, diagnostics = build_simulation(project_root)
    outputs = write_outputs(project_root, candidate_rows, comparison_rows, breakdown_rows, diagnostics)
    print(json.dumps({key: str(value) for key, value in outputs.items()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
