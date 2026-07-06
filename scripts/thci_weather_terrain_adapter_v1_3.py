#!/usr/bin/env python3
"""Build route-level THCI v1.3 weather-terrain adapter evidence.

This adapter does not compute THCI scores and does not modify any scoring or
risk-semantics configuration. It only rolls existing Butterfly Valley evidence
into named route-level candidate fields with lineage and QC metadata.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


CASE_ID = "taichung_guguan_butterfly_valley_waterfall_20260630"
ADAPTER_VERSION = "thci_weather_terrain_adapter_v1_3"

FIELDS = [
    "rainwash_or_convergence_sensitivity",
    "upslope_weather_amplification_score",
    "nlsc_collapse_mask_overlap_ratio",
    "nlsc_collapse_mask_nearby",
    "dist_nlsc_collapse_mask_m",
    "weather_terrain_fusion_rainwash_axis_score",
    "fusion_hotspot_overlap_ratio",
    "weather_terrain_fusion_rain_factor",
]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_metric_csv(path: Path) -> dict[str, str]:
    rows = read_csv_rows(path)
    return {row.get("metric", ""): row.get("value", "") for row in rows}


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


def bool_text(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_required(paths: Iterable[Path]) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing required input files:\n" + "\n".join(missing))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def format_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.12g}"
    return str(value)


def length_weighted_mean(rows: list[dict[str, str]], value_field: str, length_field: str) -> float | None:
    numerator = 0.0
    denominator = 0.0
    for row in rows:
        value = parse_float(row.get(value_field))
        length = parse_float(row.get(length_field))
        if value is None or length is None:
            continue
        numerator += value * length
        denominator += length
    if denominator == 0:
        return None
    return numerator / denominator


def sum_length(rows: list[dict[str, str]], predicate) -> float:
    total = 0.0
    for row in rows:
        if predicate(row):
            total += parse_float(row.get("length_m"), 0.0) or 0.0
    return total


def build_rows(project_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    out = project_root / "outputs"
    route_profile = out / "ib1_route_profile_v1_3b_contract_qa" / CASE_ID / f"{CASE_ID}_route_profile.csv"
    contour_summary = out / "ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa" / CASE_ID / f"{CASE_ID}_route_profile_contour_window_terrain_summary.csv"
    ib1g2_csv = out / "ib1g2_upslope_collapse_hazard_proxy" / CASE_ID / f"{CASE_ID}_upslope_collapse_hazard_proxy.csv"
    ib1g2_summary = out / "ib1g2_upslope_collapse_hazard_proxy" / CASE_ID / f"{CASE_ID}_upslope_collapse_hazard_proxy_summary.csv"
    ib1g3_csv = out / "ib1g3_upslope_contributing_area_hazard_proxy" / CASE_ID / f"{CASE_ID}_upslope_contributing_area_hazard_proxy.csv"
    ib1g3_summary = out / "ib1g3_upslope_contributing_area_hazard_proxy" / CASE_ID / f"{CASE_ID}_upslope_contributing_area_hazard_proxy_summary.csv"
    distant_summary = out / "ib1g3_distant_collapse_mask_review" / CASE_ID / f"{CASE_ID}_distant_collapse_mask_review_summary.csv"
    ib2d_summary = out / "ib2d_upslope_contributing_hazard_map" / CASE_ID / f"{CASE_ID}_upslope_contributing_hazard_map_summary.csv"
    fusion_summary_json = out / "ib2d_weather_terrain_fusion_scenarios_v1" / CASE_ID / f"{CASE_ID}_weather_terrain_fusion_summary.json"
    fusion_segment_csv = out / "ib2d_weather_terrain_fusion_scenarios_v1" / CASE_ID / f"{CASE_ID}_weather_terrain_fusion_segment_risk.csv"
    audit_report = out / "thci_weather_terrain_v1_3_implementation_audit" / CASE_ID / "thci_weather_terrain_v1_3_implementation_audit_report.md"

    ensure_required(
        [
            route_profile,
            contour_summary,
            ib1g2_csv,
            ib1g2_summary,
            ib1g3_csv,
            ib1g3_summary,
            distant_summary,
            ib2d_summary,
            fusion_summary_json,
            fusion_segment_csv,
            audit_report,
        ]
    )

    contour_metrics = read_metric_csv(contour_summary)
    ib1g2_metrics = read_metric_csv(ib1g2_summary)
    ib1g3_metrics = read_metric_csv(ib1g3_summary)
    distant_rows = read_csv_rows(distant_summary)
    ib2d_rows = read_csv_rows(ib2d_summary)
    fusion_segments = read_csv_rows(fusion_segment_csv)

    with fusion_summary_json.open("r", encoding="utf-8") as f:
        fusion_summary = json.load(f)

    distant = distant_rows[0]
    ib2d = ib2d_rows[0]

    route_fingerprint = "sha256:" + sha256_file(route_profile)
    scenario = fusion_summary.get("scenario", "")
    as_of = fusion_summary.get("as_of", "")
    rain_flags = "|".join(fusion_summary.get("rain_flags", []))
    generated_at = datetime.now(timezone.utc).isoformat()

    route_len_m = parse_float(fusion_summary.get("route_len_m"))
    if route_len_m is None:
        route_len_m = sum(parse_float(row.get("length_m"), 0.0) or 0.0 for row in fusion_segments)

    hotspot_len_m = sum_length(fusion_segments, lambda row: bool_text(row.get("overlap_hotspot")))
    hotspot_ratio = hotspot_len_m / route_len_m if route_len_m else None
    rain_sensitivity_mean = length_weighted_mean(fusion_segments, "rain_sensitivity", "length_m")

    ib1g3_watercourse_max = parse_float(ib1g3_metrics.get("watercourse_channel_score_max"))
    hydro_amp_mean = parse_float(contour_metrics.get("hydro_terrain_amplifier_score_mean"))
    hydro_amp_max = parse_float(contour_metrics.get("hydro_terrain_amplifier_score_max"))
    rainwash_candidates = [x for x in [rain_sensitivity_mean, ib1g3_watercourse_max, hydro_amp_max] if x is not None]
    rainwash_value = max(rainwash_candidates) if rainwash_candidates else None

    collapse_features_in_buffer = parse_float(ib2d.get("collapse_mask_features_within_buffer"), 0.0) or 0.0
    collapse_overlap_ratio = 0.0 if collapse_features_in_buffer == 0 else None
    nearest_collapse_dist = parse_float(distant.get("min_distance_to_route_m"))
    collapse_nearby = bool(collapse_features_in_buffer > 0)

    common = {
        "case_id": CASE_ID,
        "route_fingerprint": route_fingerprint,
        "scenario": scenario,
        "as_of": as_of,
        "rain_flags": rain_flags,
        "adapter_version": ADAPTER_VERSION,
        "generated_at": generated_at,
    }

    rows: list[dict[str, Any]] = []

    def add(
        field: str,
        value: Any,
        status: str,
        source_file: Path,
        source_field: str,
        double_count_guard_required: bool,
        notes: str,
        support: dict[str, Any] | None = None,
    ) -> None:
        row = {
            **common,
            "thci_field": field,
            "value": value,
            "field_status": status,
            "source_file": str(source_file),
            "source_field": source_field,
            "double_count_guard_required": double_count_guard_required,
            "notes": notes,
            "supporting_values_json": json.dumps(support or {}, ensure_ascii=False, sort_keys=True),
        }
        rows.append(row)

    add(
        "rainwash_or_convergence_sensitivity",
        rainwash_value,
        "scoring_ready_candidate" if rainwash_value is not None else "pending_source",
        fusion_segment_csv,
        "rain_sensitivity:length_weighted_mean|ib1g3.watercourse_channel_score_max|contour.hydro_terrain_amplifier_score_max",
        True,
        "Candidate route-level rainwash/convergence sensitivity. Uses the strongest traceable review signal and must remain guarded against baseline terrain double counting.",
        {
            "fusion_rain_sensitivity_length_weighted_mean": rain_sensitivity_mean,
            "ib1g3_watercourse_channel_score_max": ib1g3_watercourse_max,
            "hydro_terrain_amplifier_score_mean": hydro_amp_mean,
            "hydro_terrain_amplifier_score_max": hydro_amp_max,
        },
    )

    add(
        "upslope_weather_amplification_score",
        None,
        "planned",
        ib1g3_csv,
        "upslope_contributing_hazard_score|rain_factor|rain_flags",
        True,
        "Not emitted as a score because the weather amplification residual formula is not defined. Raw upslope_contributing_hazard_score is intentionally not reused directly.",
        {
            "ib1g3_score_mean": parse_float(ib1g3_metrics.get("score_mean")),
            "ib1g3_score_max": parse_float(ib1g3_metrics.get("score_max")),
            "rain_factor": parse_float(fusion_summary.get("rain_factor")),
        },
    )

    add(
        "nlsc_collapse_mask_overlap_ratio",
        collapse_overlap_ratio,
        "review_only",
        ib2d_summary,
        "collapse_mask_features_within_buffer",
        True,
        "Review-only placeholder. ib2d reports zero collapse-mask features within the map buffer; no accepted route-level overlap ratio exists yet.",
        {"collapse_mask_features_within_buffer": collapse_features_in_buffer},
    )

    add(
        "nlsc_collapse_mask_nearby",
        collapse_nearby,
        "review_only",
        distant_summary,
        "nearest_review_flag|min_distance_to_route_m",
        True,
        "Distant collapse mask review flag exists; nearest distance 1339.87 m; not near-route scoring evidence.",
        {
            "nearest_review_flag": distant.get("nearest_review_flag"),
            "min_distance_to_route_m": nearest_collapse_dist,
            "collapse_mask_features_within_buffer": collapse_features_in_buffer,
        },
    )

    add(
        "dist_nlsc_collapse_mask_m",
        nearest_collapse_dist,
        "review_only",
        distant_summary,
        "min_distance_to_route_m",
        True,
        "Review distance only. Do not mix with OSM dist_landslide_m and do not feed scoring without accepted NLSC route-level lineage.",
        {"nearest_distance_band": distant.get("nearest_distance_band")},
    )

    add(
        "weather_terrain_fusion_rainwash_axis_score",
        parse_float(fusion_summary.get("rainwash_axis_score")),
        "scoring_ready_candidate",
        fusion_summary_json,
        "rainwash_axis_score",
        True,
        "Direct route-level rename from fusion summary with scenario/as_of/rain_flags lineage preserved.",
        {"weather_csv": fusion_summary.get("weather_csv")},
    )

    add(
        "fusion_hotspot_overlap_ratio",
        hotspot_ratio,
        "scoring_ready_candidate" if hotspot_ratio is not None else "pending_source",
        fusion_segment_csv,
        "overlap_hotspot:length_m/route_len_m",
        True,
        "Route-level rollup of weather-terrain hotspot segment length divided by route length.",
        {"hotspot_len_m": hotspot_len_m, "route_len_m": route_len_m},
    )

    add(
        "weather_terrain_fusion_rain_factor",
        parse_float(fusion_summary.get("rain_factor")),
        "review_only",
        fusion_summary_json,
        "rain_factor",
        False,
        "Context/review-only field. It must not independently raise THCI without accepted route sensitivity fields.",
        {"effective_rain_factor_segment_values": sorted({row.get("effective_rain_factor", "") for row in fusion_segments})},
    )

    diagnostics = {
        "case_id": CASE_ID,
        "adapter_version": ADAPTER_VERSION,
        "generated_at": generated_at,
        "route_fingerprint": route_fingerprint,
        "field_count": len(rows),
        "expected_fields": FIELDS,
        "missing_fields": [field for field in FIELDS if field not in {row["thci_field"] for row in rows}],
        "route_len_m": route_len_m,
        "fusion_hotspot_len_m": hotspot_len_m,
        "fusion_hotspot_overlap_ratio": hotspot_ratio,
        "rain_sensitivity_length_weighted_mean": rain_sensitivity_mean,
        "collapse_mask_features_within_buffer": collapse_features_in_buffer,
        "nearest_nlsc_collapse_mask_distance_m": nearest_collapse_dist,
        "source_files": {
            "route_profile": str(route_profile),
            "contour_summary": str(contour_summary),
            "ib1g2_csv": str(ib1g2_csv),
            "ib1g2_summary": str(ib1g2_summary),
            "ib1g3_csv": str(ib1g3_csv),
            "ib1g3_summary": str(ib1g3_summary),
            "distant_collapse_summary": str(distant_summary),
            "ib2d_summary": str(ib2d_summary),
            "fusion_summary_json": str(fusion_summary_json),
            "fusion_segment_csv": str(fusion_segment_csv),
            "audit_report": str(audit_report),
        },
    }
    return rows, diagnostics


def write_outputs(project_root: Path, rows: list[dict[str, Any]], diagnostics: dict[str, Any]) -> dict[str, Path]:
    out_dir = project_root / "outputs" / "thci_weather_terrain_adapter_v1_3" / CASE_ID
    out_dir.mkdir(parents=True, exist_ok=True)

    outputs = {
        "route_csv": out_dir / f"{CASE_ID}_thci_weather_terrain_route_level_v1_3.csv",
        "route_json": out_dir / f"{CASE_ID}_thci_weather_terrain_route_level_v1_3.json",
        "lineage_csv": out_dir / f"{CASE_ID}_thci_weather_terrain_field_lineage_v1_3.csv",
        "qc_md": out_dir / f"{CASE_ID}_thci_weather_terrain_adapter_qc_v1_3.md",
    }
    existing = [str(path) for path in outputs.values() if path.exists()]
    if existing:
        raise FileExistsError("Refusing to overwrite existing adapter outputs:\n" + "\n".join(existing))

    csv_fields = [
        "thci_field",
        "value",
        "field_status",
        "case_id",
        "route_fingerprint",
        "scenario",
        "as_of",
        "rain_flags",
        "source_file",
        "source_field",
        "double_count_guard_required",
        "notes",
    ]
    csv_rows = [{**row, "value": format_value(row["value"])} for row in rows]
    write_csv(outputs["route_csv"], csv_rows, csv_fields)

    json_payload = {
        "case_id": CASE_ID,
        "adapter_version": ADAPTER_VERSION,
        "generated_at": diagnostics["generated_at"],
        "route_fingerprint": diagnostics["route_fingerprint"],
        "fields": rows,
        "diagnostics": diagnostics,
        "notes": [
            "Adapter output only; no THCI scoring was run.",
            "NLSC collapse-mask values are review-only for this case.",
            "Rain factor is context-only and must not independently raise THCI.",
        ],
    }
    with outputs["route_json"].open("w", encoding="utf-8") as f:
        json.dump(json_payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    lineage_fields = csv_fields + ["adapter_version", "generated_at", "supporting_values_json"]
    lineage_rows = [{**row, "value": format_value(row["value"])} for row in rows]
    write_csv(outputs["lineage_csv"], lineage_rows, lineage_fields)

    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row["field_status"]] = status_counts.get(row["field_status"], 0) + 1

    lines = [
        "# THCI Weather-Terrain Adapter v1.3 QC",
        "",
        f"Case ID: `{CASE_ID}`",
        f"Generated at: `{diagnostics['generated_at']}`",
        f"Route fingerprint: `{diagnostics['route_fingerprint']}`",
        "",
        "## Scope",
        "",
        "This adapter creates route-level THCI v1.3 weather-terrain candidate fields only. It does not compute THCI scores, modify scoring scripts, or modify risk-semantics configs.",
        "",
        "## Output Field Status Counts",
        "",
    ]
    for status in sorted(status_counts):
        lines.append(f"- `{status}`: {status_counts[status]}")
    lines.extend(
        [
            "",
            "## Field Summary",
            "",
            "| field | value | status | source_field | double_count_guard_required |",
            "|---|---:|---|---|---:|",
        ]
    )
    for row in rows:
        lines.append(
            f"| `{row['thci_field']}` | `{format_value(row['value'])}` | `{row['field_status']}` | `{row['source_field']}` | `{str(row['double_count_guard_required']).lower()}` |"
        )
    lines.extend(
        [
            "",
            "## QC Notes",
            "",
            f"- Expected field count: `{len(FIELDS)}`; emitted field count: `{len(rows)}`.",
            f"- Missing expected fields: `{', '.join(diagnostics['missing_fields']) if diagnostics['missing_fields'] else 'none'}`.",
            f"- Fusion hotspot overlap ratio: `{format_value(diagnostics['fusion_hotspot_overlap_ratio'])}`.",
            f"- Nearest NLSC collapse-mask distance: `{format_value(diagnostics['nearest_nlsc_collapse_mask_distance_m'])}` m.",
            f"- Collapse-mask features within ib2d buffer: `{format_value(diagnostics['collapse_mask_features_within_buffer'])}`.",
            "- `upslope_weather_amplification_score` remains planned because no weather amplification residual formula is defined.",
            "- NLSC collapse-mask fields are review-only and must not enter scoring at this stage.",
            "- `weather_terrain_fusion_rain_factor` is review-only context and must not independently raise THCI.",
            "",
            "## Source Files",
            "",
        ]
    )
    for key, value in diagnostics["source_files"].items():
        lines.append(f"- `{key}`: `{value}`")
    outputs["qc_md"].write_text("\n".join(lines) + "\n", encoding="utf-8")

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
    rows, diagnostics = build_rows(project_root)
    outputs = write_outputs(project_root, rows, diagnostics)
    print(json.dumps({key: str(value) for key, value in outputs.items()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
