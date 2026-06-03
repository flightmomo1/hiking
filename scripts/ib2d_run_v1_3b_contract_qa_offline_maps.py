# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASES = [
    "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b",
    "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b",
    "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b",
    "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b",
]

INPUT_ROOT = PROJECT_ROOT / "outputs" / "ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa"
OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "ib2d_route_risk_offline_map_v1_3b_contract_qa"
BATCH_ROOT = OUTPUT_ROOT / "_batch_summary"
IB2D_CLI = PROJECT_ROOT / "scripts" / "ib2_route_risk" / "ib2d_plot_route_risk_offline_map_cli_updated.py"
CONTOUR_FP = PROJECT_ROOT / "nlsc_raw" / "97233NW" / "向量25K" / "ContourL.shp"
SEMANTIC_RISK_CONFIG = PROJECT_ROOT / "configs" / "risk_semantics" / "osm_semantic_risk_mapping_v1.csv"
WEATHER_ROOT = PROJECT_ROOT / "weather"
WEATHER_MODE = "not_integrated_at_ib2d"
WEATHER_SCOPE = "future_ib3_activity_layer"

REQUIRED_CASE_OUTPUTS = [
    "{case_id}_route_risk_offline_map.png",
    "{case_id}_route_risk_offline_segments.geojson",
    "{case_id}_route_challenge_radar.png",
    "{case_id}_route_risk_offline_map_with_radar.png",
    "{case_id}_ib2d_summary.txt",
]

BAND_COLUMNS = [
    "risk_band_low_count",
    "risk_band_moderate_count",
    "risk_band_high_count",
    "risk_band_very_high_count",
    "risk_band_unknown_count",
]

INPUT_COMPONENT_COLUMNS = {
    "ib1a_route_profile_present": [
        "dist_m",
        "lat",
        "lon",
        "ele_smooth",
        "cum_gain_m",
        "cum_loss_m",
    ],
    "ib1c_osm_semantics_present": [
        "osm_highway",
        "route_semantic_class",
        "surface_class",
        "assist_class",
        "visibility_class",
        "osm_difficulty_class",
    ],
    "ib1c_semantic_risk_present": [
        "osm_semantic_risk_score",
        "osm_semantic_risk_band",
    ],
    "ib1g_contour_window_present": [
        "terrain_segment_id",
        "terrain_dist_mid_m",
        "terrain_segment_len_m",
        "slope_band_window_nlsc",
        "contour_density_20m_nlsc_window",
        "contour_csv",
    ],
    "ib1e_terrain_enrichment_present": [
        "terrain_window_risk_score",
        "osm_terrain_combined_risk_score",
        "osm_terrain_combined_risk_band",
        "contour_window_match_status",
    ],
    "hydrology_hydro_terrain_present": [
        "hydrology_flags",
        "hydrology_risk_score",
        "hydro_terrain_amplifier_score",
        "hydro_terrain_weight",
    ],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_case_name(case_id: str, risk_csv: Path) -> str:
    try:
        row = pd.read_csv(risk_csv, nrows=1, encoding="utf-8-sig").iloc[0]
        name = str(row.get("case_name", "")).strip()
        return name or case_id
    except Exception:
        return case_id


def input_paths(case_id: str) -> tuple[Path, Path]:
    case_root = INPUT_ROOT / case_id
    risk_csv = case_root / f"{case_id}_route_profile_contour_window_terrain_enriched.csv"
    risk_geojson = case_root / f"{case_id}_route_profile_contour_window_terrain_enriched.geojson"
    return risk_csv, risk_geojson


def summary_path(case_id: str) -> Path:
    return (
        INPUT_ROOT
        / case_id
        / f"{case_id}_route_profile_contour_window_terrain_summary.csv"
    )


def output_paths(case_id: str) -> dict[str, Path]:
    case_root = OUTPUT_ROOT / case_id
    return {
        "map_png": case_root / f"{case_id}_route_risk_offline_map.png",
        "segments_geojson": case_root / f"{case_id}_route_risk_offline_segments.geojson",
        "radar_png": case_root / f"{case_id}_route_challenge_radar.png",
        "combined_png": case_root / f"{case_id}_route_risk_offline_map_with_radar.png",
        "summary_txt": case_root / f"{case_id}_ib2d_summary.txt",
    }


def route_length_from_profile(risk_csv: Path) -> float:
    df = pd.read_csv(risk_csv, usecols=["dist_m"], encoding="utf-8-sig")
    return float(df["dist_m"].max())


def validate_input_contract(risk_csv: Path) -> dict[str, object]:
    columns = pd.read_csv(risk_csv, nrows=0, encoding="utf-8-sig").columns
    column_set = set(columns)
    result: dict[str, object] = {}
    missing_all: list[str] = []
    for component, required_cols in INPUT_COMPONENT_COLUMNS.items():
        missing = [col for col in required_cols if col not in column_set]
        result[component] = not missing
        result[component.replace("_present", "_missing_columns")] = ";".join(missing)
        missing_all.extend(missing)

    result["weather_mode"] = WEATHER_MODE
    result["weather_scope"] = WEATHER_SCOPE
    result["observed_weather_adjustment_present"] = False
    result["weather_adjustment_note"] = (
        "Weather is not an IB2D blocker and is reserved for IB3 activity-level observed behavior/weather context."
    )
    result["weather_root_present_for_inventory_only"] = WEATHER_ROOT.exists()
    result["input_contract_components_complete"] = not missing_all
    result["input_contract_missing_columns"] = ";".join(sorted(set(missing_all)))
    return result


def validate_pre_ib2d_dependencies(case_id: str) -> dict[str, object]:
    summary_fp = summary_path(case_id)
    result: dict[str, object] = {
        "configs_root_present": (PROJECT_ROOT / "configs").exists(),
        "semantic_risk_mapping_config_present": SEMANTIC_RISK_CONFIG.exists(),
        "nlsc_raw_root_present": (PROJECT_ROOT / "nlsc_raw").exists(),
        "nlsc_contour_fp_present": CONTOUR_FP.exists(),
        "ib1e_baseline_input_present": input_paths(case_id)[0].exists() and input_paths(case_id)[1].exists(),
        "terrain_baseline_weight_present": False,
        "hydro_terrain_weight_present": False,
        "pre_ib2d_dependency_audit_pass": False,
    }
    if summary_fp.exists():
        try:
            summary = pd.read_csv(summary_fp, encoding="utf-8-sig")
            metrics = set(summary.get("metric", pd.Series(dtype=str)).astype(str))
            result["terrain_baseline_weight_present"] = "terrain_weight" in metrics
            result["hydro_terrain_weight_present"] = "hydro_terrain_weight" in metrics
        except Exception:
            pass
    result["pre_ib2d_dependency_audit_pass"] = all(
        bool(result[key])
        for key in [
            "configs_root_present",
            "semantic_risk_mapping_config_present",
            "nlsc_raw_root_present",
            "nlsc_contour_fp_present",
            "ib1e_baseline_input_present",
            "terrain_baseline_weight_present",
            "hydro_terrain_weight_present",
        ]
    )
    return result


def validate_segments(case_id: str, risk_csv: Path, seg_geojson: Path) -> dict[str, object]:
    route_len_m = route_length_from_profile(risk_csv)
    gdf = gpd.read_file(seg_geojson)
    result: dict[str, object] = {
        "segment_count": int(len(gdf)),
        "route_len_m": route_len_m,
        "risk_geometry_len_m": 0.0,
        "risk_geometry_coverage_ratio": 0.0,
        "missing_risk_band_count": None,
        "missing_geometry_count": None,
        "risk_band_present": False,
        "geometry_present": False,
    }
    for col in BAND_COLUMNS:
        result[col] = 0

    if "risk_band" not in gdf.columns:
        return result

    result["risk_band_present"] = True
    bands = gdf["risk_band"].fillna("").astype(str).str.strip()
    result["missing_risk_band_count"] = int((bands == "").sum())
    counts = bands.replace("", "unknown").value_counts().to_dict()
    result["risk_band_low_count"] = int(counts.get("low", 0))
    result["risk_band_moderate_count"] = int(counts.get("moderate", 0))
    result["risk_band_high_count"] = int(counts.get("high", 0))
    result["risk_band_very_high_count"] = int(counts.get("very_high", 0))
    result["risk_band_unknown_count"] = int(counts.get("unknown", 0))

    if gdf.empty or gdf.geometry is None:
        result["missing_geometry_count"] = int(len(gdf))
        return result

    valid_geom = gdf.geometry.notna() & ~gdf.geometry.is_empty
    result["missing_geometry_count"] = int((~valid_geom).sum())
    result["geometry_present"] = bool(valid_geom.any())
    if valid_geom.any():
        metric = gdf.loc[valid_geom].copy()
        if metric.crs is None:
            metric = metric.set_crs("EPSG:4326")
        metric = metric.to_crs(metric.estimate_utm_crs() or "EPSG:3826")
        geom_len = float(metric.geometry.length.sum())
        result["risk_geometry_len_m"] = geom_len
        result["risk_geometry_coverage_ratio"] = geom_len / route_len_m if route_len_m else 0.0
    return result


def case_status(row: dict[str, object]) -> tuple[str, str]:
    failures: list[str] = []
    warnings: list[str] = []
    required_present = bool(row["required_outputs_present"])
    if not required_present:
        failures.append("required IB2D PNG/GeoJSON/radar outputs missing")
    if not row["risk_band_present"]:
        failures.append("segment risk_band missing")
    if int(row["missing_risk_band_count"] or 0) > 0:
        failures.append("segment risk_band has missing values")
    if int(row["missing_geometry_count"] or 0) > 0:
        failures.append("segment geometry has missing values")
    if int(row["segment_count"] or 0) <= 0:
        failures.append("no risk segments generated")
    coverage = float(row["risk_geometry_coverage_ratio"] or 0.0)
    if coverage < 0.98 or coverage > 1.02:
        warnings.append(f"risk geometry coverage ratio outside 0.98-1.02: {coverage:.4f}")
    if int(row["risk_band_low_count"]) + int(row["risk_band_moderate_count"]) + int(row["risk_band_high_count"]) + int(row["risk_band_very_high_count"]) <= 0:
        failures.append("no low/moderate/high/very_high risk bands counted")
    if failures:
        return "FAIL", "; ".join(failures + warnings)
    if warnings:
        return "WARN", "; ".join(warnings)
    return "PASS", ""


def run_case(case_id: str) -> tuple[dict[str, object], str]:
    risk_csv, risk_geojson = input_paths(case_id)
    out = output_paths(case_id)
    case_root = OUTPUT_ROOT / case_id
    case_root.mkdir(parents=True, exist_ok=True)

    row: dict[str, object] = {
        "case_id": case_id,
        "input_root": str(INPUT_ROOT),
        "output_root": str(case_root),
        "risk_csv": str(risk_csv),
        "risk_geojson": str(risk_geojson),
        "required_outputs_present": False,
        "required_outputs_missing": "",
        "status": "FAIL",
        "blocking_issue": "",
        "warning_note": "",
        "checkpoint_ready": False,
    }
    for col in BAND_COLUMNS:
        row[col] = 0

    missing_inputs = [str(path) for path in [risk_csv, risk_geojson, CONTOUR_FP] if not path.exists()]
    if missing_inputs:
        row["blocking_issue"] = "missing inputs: " + "; ".join(missing_inputs)
        write_case_summary(case_id, row)
        return row, row["blocking_issue"]

    row.update(validate_input_contract(risk_csv))
    row.update(validate_pre_ib2d_dependencies(case_id))

    case_name = read_case_name(case_id, risk_csv)
    cmd = [
        sys.executable,
        str(IB2D_CLI),
        "--case-id",
        case_id,
        "--case-name",
        case_name,
        "--risk-csv",
        str(risk_csv),
        "--risk-geojson",
        str(risk_geojson),
        "--profile-geojson",
        str(risk_geojson),
        "--osm-raw-dir",
        str(PROJECT_ROOT / "osm_raw_output" / case_id),
        "--contour-fp",
        str(CONTOUR_FP),
        "--out-dir",
        str(case_root),
    ]
    completed = subprocess.run(cmd, cwd=PROJECT_ROOT, text=True, capture_output=True)
    log_text = [
        f"case_id={case_id}",
        "command=" + " ".join(f'"{part}"' if " " in part else part for part in cmd),
        f"returncode={completed.returncode}",
        "--- stdout ---",
        completed.stdout,
        "--- stderr ---",
        completed.stderr,
    ]

    if completed.returncode != 0:
        row["blocking_issue"] = f"IB2D CLI failed with returncode {completed.returncode}"
        write_case_summary(case_id, row)
        return row, "\n".join(log_text)

    missing_outputs = [
        str(case_root / template.format(case_id=case_id))
        for template in REQUIRED_CASE_OUTPUTS[:-1]
        if not (case_root / template.format(case_id=case_id)).exists()
    ]
    row["required_outputs_present"] = not missing_outputs
    row["required_outputs_missing"] = "; ".join(missing_outputs)

    validation = validate_segments(case_id, risk_csv, out["segments_geojson"])
    row.update(validation)
    status, note = case_status(row)
    row["status"] = status
    if status == "FAIL":
        row["blocking_issue"] = note
    elif status == "WARN":
        row["warning_note"] = note
    row["checkpoint_ready"] = status in {"PASS", "WARN"}
    write_case_summary(case_id, row)
    return row, "\n".join(log_text)


def write_case_summary(case_id: str, row: dict[str, object]) -> None:
    summary = output_paths(case_id)["summary_txt"]
    summary.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "IB2D v1.3b contract QA case summary",
        f"generated_at_utc: {utc_now()}",
        f"case_id: {case_id}",
        f"status: {row.get('status', 'FAIL')}",
        f"input_root: {INPUT_ROOT}",
        f"output_root: {summary.parent}",
        f"required_outputs_present: {row.get('required_outputs_present', False)}",
        f"required_outputs_missing: {row.get('required_outputs_missing', '')}",
        f"input_contract_components_complete: {row.get('input_contract_components_complete', False)}",
        f"ib1a_route_profile_present: {row.get('ib1a_route_profile_present', False)}",
        f"ib1c_osm_semantics_present: {row.get('ib1c_osm_semantics_present', False)}",
        f"ib1c_semantic_risk_present: {row.get('ib1c_semantic_risk_present', False)}",
        f"ib1g_contour_window_present: {row.get('ib1g_contour_window_present', False)}",
        f"ib1e_terrain_enrichment_present: {row.get('ib1e_terrain_enrichment_present', False)}",
        f"hydrology_hydro_terrain_present: {row.get('hydrology_hydro_terrain_present', False)}",
        f"pre_ib2d_dependency_audit_pass: {row.get('pre_ib2d_dependency_audit_pass', False)}",
        f"configs_root_present: {row.get('configs_root_present', False)}",
        f"semantic_risk_mapping_config_present: {row.get('semantic_risk_mapping_config_present', False)}",
        f"nlsc_raw_root_present: {row.get('nlsc_raw_root_present', False)}",
        f"nlsc_contour_fp_present: {row.get('nlsc_contour_fp_present', False)}",
        f"ib1e_baseline_input_present: {row.get('ib1e_baseline_input_present', False)}",
        f"terrain_baseline_weight_present: {row.get('terrain_baseline_weight_present', False)}",
        f"hydro_terrain_weight_present: {row.get('hydro_terrain_weight_present', False)}",
        f"weather_mode: {row.get('weather_mode', WEATHER_MODE)}",
        f"weather_scope: {row.get('weather_scope', WEATHER_SCOPE)}",
        f"weather_root_present_for_inventory_only: {row.get('weather_root_present_for_inventory_only', False)}",
        f"observed_weather_adjustment_present: {row.get('observed_weather_adjustment_present', False)}",
        f"weather_adjustment_note: {row.get('weather_adjustment_note', '')}",
        f"segment_count: {row.get('segment_count', 0)}",
        f"risk_band_present: {row.get('risk_band_present', False)}",
        f"missing_risk_band_count: {row.get('missing_risk_band_count', '')}",
        f"missing_geometry_count: {row.get('missing_geometry_count', '')}",
        f"risk_geometry_coverage_ratio: {row.get('risk_geometry_coverage_ratio', '')}",
        "risk_band_counts: "
        + "; ".join(f"{col.replace('risk_band_', '').replace('_count', '')}={row.get(col, 0)}" for col in BAND_COLUMNS),
        f"blocking_issue: {row.get('blocking_issue', '')}",
        f"warning_note: {row.get('warning_note', '')}",
        f"checkpoint_ready: {row.get('checkpoint_ready', False)}",
    ]
    summary.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_batch_outputs(rows: list[dict[str, object]], logs: list[str]) -> None:
    BATCH_ROOT.mkdir(parents=True, exist_ok=True)
    csv_fp = BATCH_ROOT / "ib2d_v1_3b_contract_qa_case_summary.csv"
    fields = [
        "case_id",
        "status",
        "input_contract_components_complete",
        "ib1a_route_profile_present",
        "ib1c_osm_semantics_present",
        "ib1c_semantic_risk_present",
        "ib1g_contour_window_present",
        "ib1e_terrain_enrichment_present",
        "hydrology_hydro_terrain_present",
        "pre_ib2d_dependency_audit_pass",
        "configs_root_present",
        "semantic_risk_mapping_config_present",
        "nlsc_raw_root_present",
        "nlsc_contour_fp_present",
        "ib1e_baseline_input_present",
        "terrain_baseline_weight_present",
        "hydro_terrain_weight_present",
        "weather_mode",
        "weather_scope",
        "weather_root_present_for_inventory_only",
        "observed_weather_adjustment_present",
        "weather_adjustment_note",
        "required_outputs_present",
        "segment_count",
        "route_len_m",
        "risk_geometry_len_m",
        "risk_geometry_coverage_ratio",
        "risk_band_low_count",
        "risk_band_moderate_count",
        "risk_band_high_count",
        "risk_band_very_high_count",
        "risk_band_unknown_count",
        "risk_band_present",
        "missing_risk_band_count",
        "missing_geometry_count",
        "checkpoint_ready",
        "blocking_issue",
        "warning_note",
        "input_root",
        "output_root",
    ]
    with csv_fp.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    status_counts = pd.Series([row["status"] for row in rows]).value_counts().to_dict()
    all_ready = all(bool(row.get("checkpoint_ready")) for row in rows)
    stage_status = "PASS" if all(row["status"] == "PASS" for row in rows) else "WARN" if all_ready else "FAIL"
    md_fp = BATCH_ROOT / "ib2d_v1_3b_contract_qa_stage_summary.md"
    lines = [
        "# IB2D v1.3b contract QA stage summary",
        "",
        f"- generated_at_utc: {utc_now()}",
        f"- stage_status: {stage_status}",
        f"- formal_input_root: `{INPUT_ROOT}`",
        "- ib2d_role: route-level baseline risk visualization",
        "- formal_risk_sources: OSM semantics + OSM semantic risk mapping + OSM hydrology/hydro terrain amplifier + NLSC contour/terrain/slope features + terrain baseline risk",
        "- formal_input_contract: consolidated IB1E carrier containing IB1A route profile + IB1C OSM semantics + IB1C semantic risk + IB1G NLSC contour window + IB1E OSM/NLSC terrain enrichment + hydrology/hydro terrain amplifier",
        f"- pre_ib2d_dependency_audit: configs semantic mapping + NLSC contour raw data + IB1E baseline input are checked per case",
        f"- weather_mode: `{WEATHER_MODE}`",
        f"- weather_scope: `{WEATHER_SCOPE}`",
        "- weather_blocker: False",
        "- weather_adjustment_note: weather is not integrated at IB2D and is reserved for IB3 activity-level observed behavior/weather context",
        f"- output_root: `{OUTPUT_ROOT}`",
        f"- cases_expected: {len(CASES)}",
        f"- cases_processed: {len(rows)}",
        f"- status_counts: {status_counts}",
        f"- checkpoint_ready: {all_ready}",
        "",
        "| case_id | status | dependency_audit | weather_mode | weather_scope | low | moderate | high | very_high | coverage_ratio | checkpoint_ready | note |",
        "|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        note = row.get("blocking_issue") or row.get("warning_note") or ""
        lines.append(
            "| {case_id} | {status} | {dependency_audit} | {weather_mode} | {weather_scope} | {low} | {moderate} | {high} | {very_high} | {coverage:.6f} | {ready} | {note} |".format(
                case_id=row["case_id"],
                status=row["status"],
                dependency_audit=row.get("pre_ib2d_dependency_audit_pass", False),
                weather_mode=row.get("weather_mode", WEATHER_MODE),
                weather_scope=row.get("weather_scope", WEATHER_SCOPE),
                low=row.get("risk_band_low_count", 0),
                moderate=row.get("risk_band_moderate_count", 0),
                high=row.get("risk_band_high_count", 0),
                very_high=row.get("risk_band_very_high_count", 0),
                coverage=float(row.get("risk_geometry_coverage_ratio") or 0.0),
                ready=row.get("checkpoint_ready", False),
                note=str(note).replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "IB2D route risk offline map is a v1.3b route-level risk visualization checkpoint when all cases are PASS or acceptable WARN.",
        ]
    )
    md_fp.write_text("\n".join(lines) + "\n", encoding="utf-8")

    log_fp = BATCH_ROOT / "ib2d_v1_3b_contract_qa_run_log.txt"
    log_fp.write_text("\n\n".join(logs) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    logs = [f"IB2D v1.3b contract QA run started at {utc_now()}"]
    logs.append(f"formal_input_root={INPUT_ROOT}")
    logs.append(f"output_root={OUTPUT_ROOT}")
    logs.append(f"ib2d_cli={IB2D_CLI}")
    logs.append(f"contour_fp={CONTOUR_FP}")
    logs.append(f"semantic_risk_config={SEMANTIC_RISK_CONFIG}")
    logs.append(f"weather_mode={WEATHER_MODE}")
    logs.append(f"weather_scope={WEATHER_SCOPE}")
    logs.append("weather_blocker=False")
    for case_id in CASES:
        row, log_text = run_case(case_id)
        rows.append(row)
        logs.append(log_text)
        print(f"{case_id}: {row['status']}")
    logs.append(f"IB2D v1.3b contract QA run finished at {utc_now()}")
    write_batch_outputs(rows, logs)


if __name__ == "__main__":
    main()
