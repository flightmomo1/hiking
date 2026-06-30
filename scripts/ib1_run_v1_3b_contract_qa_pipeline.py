from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd


PROJECT_ROOT = Path(r"D:\mountain_work\115_osm")

CASES = [
    "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b",
    "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b",
    "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b",
    "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b",
]

IB0D_ROOT = (
    PROJECT_ROOT
    / "outputs"
    / "ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa"
)
IB0B_ROOT = (
    PROJECT_ROOT
    / "outputs"
    / "ib0b_mainline_route_definition_v1_3b_control_points_only"
)
SEMANTIC_RISK_MAPPING_CSV = (
    PROJECT_ROOT
    / "configs"
    / "risk_semantics"
    / "osm_semantic_risk_mapping_v1_2_updated.csv"
)

OUT_ROOTS = {
    "ib1a": PROJECT_ROOT / "outputs" / "ib1_route_profile_v1_3b_contract_qa",
    "ib1c_semantics": PROJECT_ROOT
    / "outputs"
    / "ib1c_route_profile_semantics_v1_3b_contract_qa",
    "ib1c_audit": PROJECT_ROOT
    / "outputs"
    / "ib1c_osm_semantic_audit_v1_3b_contract_qa",
    "ib1c_risk": PROJECT_ROOT
    / "outputs"
    / "ib1c_osm_semantic_risk_v1_3b_contract_qa",
    "ib1g": PROJECT_ROOT
    / "outputs"
    / "ib1g_contour_window_features_v1_3b_contract_qa",
    "ib1e": PROJECT_ROOT
    / "outputs"
    / "ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa",
    "plot": PROJECT_ROOT
    / "outputs"
    / "ib1e_osm_nlsc_terrain_risk_plot_v1_3b_contract_qa",
    "summary": PROJECT_ROOT
    / "outputs"
    / "ib1_v1_3b_contract_qa_pipeline_summary",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run IB1A/IB1C/IB1G/IB1E using the IB0D v1.3b contract QA root."
    )
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--skip-plot", action="store_true")
    parser.add_argument("--qa-marker-interval-m", type=float, default=50.0)
    return parser.parse_args()


def available_contour_tiles() -> dict[str, Path]:
    return {path.parts[-3]: path for path in (PROJECT_ROOT / "nlsc_raw").glob("*/**/ContourL.shp")}


def valid_elevation_count(gdf: gpd.GeoDataFrame) -> int:
    elev_cols = [
        col
        for col in gdf.columns
        if col.lower() in {"zv2", "elev", "elevation", "height", "altitude"}
        or "elev" in col.lower()
    ]
    if not elev_cols:
        return 0
    valid = pd.Series(False, index=gdf.index)
    for col in elev_cols:
        valid = valid | pd.to_numeric(gdf[col], errors="coerce").notna()
    return int(valid.sum())


def select_contour_tile(route_line_fp: Path) -> dict[str, object]:
    tiles = available_contour_tiles()
    if not tiles:
        raise FileNotFoundError("Missing NLSC contour shapefiles under nlsc_raw/*/*/ContourL.shp")

    route = gpd.read_file(route_line_fp)
    route_m = route.to_crs(route.estimate_utm_crs() or "EPSG:3826")
    route_buffer = route_m.union_all().convex_hull.buffer(350)

    candidates: list[dict[str, object]] = []
    for tile_id, contour_fp in sorted(tiles.items()):
        contour = gpd.read_file(contour_fp).to_crs(route_m.crs)
        hit = contour[contour.intersects(route_buffer)].copy()
        candidates.append(
            {
                "tile_id": tile_id,
                "contour_fp": contour_fp,
                "intersection_count": int(len(hit)),
                "valid_elevation_count": valid_elevation_count(hit),
            }
        )

    candidates = sorted(
        candidates,
        key=lambda row: (int(row["intersection_count"]), int(row["valid_elevation_count"])),
        reverse=True,
    )
    best = candidates[0]
    if int(best["intersection_count"]) <= 0 or int(best["valid_elevation_count"]) <= 0:
        raise RuntimeError(
            f"No valid NLSC 25K ContourL tile intersects route buffer with elevation data: {route_line_fp}"
        )
    best["tile_reason"] = (
        "route geometry / GPS bbox -> candidate 1/25,000 tile -> "
        "nlsc_raw/<tile>/向量25K/ContourL.shp -> route buffer intersection + valid elevation count"
    )
    best["all_candidates"] = "; ".join(
        f"{row['tile_id']}:intersections={row['intersection_count']},valid_elevation={row['valid_elevation_count']}"
        for row in candidates
    )
    return best


def read_case_meta(case_id: str) -> dict[str, str]:
    summary_fp = IB0B_ROOT / f"{case_id}_mainline_summary_ib0_candidates.csv"
    if not summary_fp.exists():
        raise FileNotFoundError(f"Missing IB0B summary: {summary_fp}")
    row = pd.read_csv(summary_fp).iloc[0]
    return {
        "case_name": str(row.get("case_name", case_id)),
        "activity_fp": str(row.get("activity_fp", "")),
    }


def run_cmd(cmd: list[str], log_lines: list[str]) -> None:
    log_lines.append("")
    log_lines.append("$ " + " ".join(cmd))
    proc = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
    )
    log_lines.append(f"exit_code={proc.returncode}")
    if proc.stdout:
        log_lines.append("--- stdout ---")
        log_lines.append(proc.stdout.rstrip())
    if proc.stderr:
        log_lines.append("--- stderr ---")
        log_lines.append(proc.stderr.rstrip())
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")


def count_risk_bands(df: pd.DataFrame, col: str) -> str:
    if col not in df.columns:
        return ""
    return ";".join(f"{k}={v}" for k, v in df[col].value_counts(dropna=False).sort_index().items())


def status(ok: bool, warn: bool = False) -> str:
    if not ok:
        return "FAIL"
    if warn:
        return "WARN"
    return "PASS"


def validate_case(case_id: str) -> dict[str, object]:
    row: dict[str, object] = {"case_id": case_id}
    blocking: list[str] = []
    warnings: list[str] = []

    ib1a_csv = OUT_ROOTS["ib1a"] / case_id / f"{case_id}_route_profile.csv"
    ib1c_csv = (
        OUT_ROOTS["ib1c_semantics"]
        / case_id
        / f"{case_id}_route_profile_semantic_enriched.csv"
    )
    risk_csv = (
        OUT_ROOTS["ib1c_risk"]
        / case_id
        / f"{case_id}_osm_semantic_risk_profile.csv"
    )
    audit_csv = (
        OUT_ROOTS["ib1c_audit"]
        / case_id
        / f"{case_id}_semantic_value_mapping_coverage.csv"
    )
    ib1g_csv = OUT_ROOTS["ib1g"] / case_id / f"{case_id}_contour_window_features.csv"
    ib1e_csv = (
        OUT_ROOTS["ib1e"]
        / case_id
        / f"{case_id}_route_profile_contour_window_terrain_enriched.csv"
    )

    route_len_m = pd.NA
    points_n = 0
    cum_gain_m = pd.NA
    cum_loss_m = pd.NA

    if not ib1a_csv.exists():
        row["ib1a_status"] = "FAIL"
        blocking.append("IB1A route profile CSV missing")
    else:
        df = pd.read_csv(ib1a_csv)
        points_n = len(df)
        route_len_m = float(pd.to_numeric(df["dist_m"], errors="coerce").max())
        cum_gain_m = float(pd.to_numeric(df["cum_gain_m"], errors="coerce").iloc[-1])
        cum_loss_m = float(pd.to_numeric(df["cum_loss_m"], errors="coerce").iloc[-1])
        ok = points_n > 0 and route_len_m > 0 and pd.to_numeric(df["dist_m"], errors="coerce").min() == 0
        row["ib1a_status"] = status(ok)
        if not ok:
            blocking.append("IB1A route profile validation failed")

    if not ib1c_csv.exists():
        row["ib1c_semantics_status"] = "FAIL"
        blocking.append("IB1C semantic CSV missing")
    else:
        df = pd.read_csv(ib1c_csv, low_memory=False)
        required = {"dist_m", "osm_highway", "route_semantic_class", "surface_class"}
        coverage_ok = points_n == 0 or abs(len(df) - points_n) <= 1
        ok = len(df) > 0 and required.issubset(df.columns) and coverage_ok
        row["ib1c_semantics_status"] = status(ok)
        if not ok:
            blocking.append("IB1C semantic validation failed")

    mapping_coverage_rate = pd.NA
    if not risk_csv.exists():
        row["ib1c_risk_status"] = "FAIL"
        blocking.append("IB1C semantic risk CSV missing")
    else:
        df = pd.read_csv(risk_csv, low_memory=False)
        required = {"osm_semantic_risk_score", "osm_semantic_risk_band"}
        ok = len(df) > 0 and required.issubset(df.columns)
        row["ib1c_risk_status"] = status(ok)
        if not ok:
            blocking.append("IB1C semantic risk validation failed")
        row["risk_band_counts"] = count_risk_bands(df, "osm_semantic_risk_band")

    if audit_csv.exists():
        audit = pd.read_csv(audit_csv, low_memory=False)
        if "has_mapping" in audit.columns:
            vals = audit["has_mapping"].astype(str).str.lower().isin(["true", "1", "yes", "mapped"])
            mapping_coverage_rate = float(vals.mean()) if len(vals) else pd.NA
        else:
            bool_cols = [c for c in audit.columns if "mapped" in c.lower() or "covered" in c.lower()]
            if bool_cols:
                col = bool_cols[0]
                vals = audit[col].astype(str).str.lower().isin(["true", "1", "yes", "mapped"])
                mapping_coverage_rate = float(vals.mean()) if len(vals) else pd.NA
        if pd.notna(mapping_coverage_rate) and mapping_coverage_rate < 1.0:
            if row.get("ib1c_risk_status") == "PASS":
                row["ib1c_risk_status"] = "WARN"
            warnings.append(f"IB1C mapping coverage below 1.0: {mapping_coverage_rate:.3f}")

    contour_match_rate = pd.NA
    max_dist_to_contour = pd.NA
    if not ib1g_csv.exists():
        row["ib1g_status"] = "FAIL"
        blocking.append("IB1G contour window CSV missing")
    else:
        df = pd.read_csv(ib1g_csv, low_memory=False)
        required = {"dist_mid", "seg_len_axis_m", "slope_band_window"}
        seg_sum = float(pd.to_numeric(df.get("seg_len_axis_m"), errors="coerce").sum())
        len_close = pd.isna(route_len_m) or abs(seg_sum - float(route_len_m)) <= 25.0
        ok = len(df) > 0 and required.issubset(df.columns) and len_close
        row["ib1g_status"] = status(ok)
        if not ok:
            blocking.append("IB1G contour window validation failed")

    if not ib1e_csv.exists():
        row["ib1e_status"] = "FAIL"
        blocking.append("IB1E terrain enrichment CSV missing")
    else:
        df = pd.read_csv(ib1e_csv, low_memory=False)
        required = {
            "contour_window_match_status",
            "dist_to_contour_window_mid_m",
            "slope_band_window_nlsc",
            "terrain_window_risk_score",
            "osm_terrain_combined_risk_score",
            "osm_terrain_combined_risk_band",
        }
        if "contour_window_match_status" in df.columns and len(df):
            contour_match_rate = float((df["contour_window_match_status"] == "matched").mean())
        if "dist_to_contour_window_mid_m" in df.columns and len(df):
            max_dist_to_contour = float(
                pd.to_numeric(df["dist_to_contour_window_mid_m"], errors="coerce").max()
            )
        ok = (
            len(df) > 0
            and required.issubset(df.columns)
            and contour_match_rate == 1.0
            and max_dist_to_contour <= 15.0
        )
        row["ib1e_status"] = status(ok)
        if not ok:
            blocking.append("IB1E terrain enrichment validation failed")
        row["risk_band_counts"] = count_risk_bands(df, "osm_terrain_combined_risk_band")

    for key in [
        "ib1a_status",
        "ib1c_semantics_status",
        "ib1c_risk_status",
        "ib1g_status",
        "ib1e_status",
    ]:
        row.setdefault(key, "FAIL")

    row["overall_status"] = "FAIL" if blocking else ("WARN" if warnings else "PASS")
    row["route_len_m"] = route_len_m
    row["points_n"] = points_n
    row["cum_gain_m"] = cum_gain_m
    row["cum_loss_m"] = cum_loss_m
    row["mapping_coverage_rate"] = mapping_coverage_rate
    row["contour_match_rate"] = contour_match_rate
    row["max_dist_to_contour_window_mid_m"] = max_dist_to_contour
    row["blocking_issue"] = " | ".join(blocking)
    row["warning_note"] = " | ".join(warnings)
    row["ib2_ready"] = not blocking
    return row


def write_summaries(case_rows: list[dict[str, object]], log_lines: list[str]) -> None:
    summary_root = OUT_ROOTS["summary"]
    summary_root.mkdir(parents=True, exist_ok=True)
    case_df = pd.DataFrame(case_rows)
    case_df.to_csv(summary_root / "ib1_v1_3b_case_summary.csv", index=False, encoding="utf-8-sig")

    stage_rows = []
    stage_defs = [
        ("IB1A route profile", "ib1a_status", OUT_ROOTS["ib1a"]),
        ("IB1C OSM semantic enrichment", "ib1c_semantics_status", OUT_ROOTS["ib1c_semantics"]),
        ("IB1C OSM semantic risk audit/apply", "ib1c_risk_status", OUT_ROOTS["ib1c_risk"]),
        ("IB1G NLSC contour window features", "ib1g_status", OUT_ROOTS["ib1g"]),
        ("IB1E OSM + NLSC terrain enrichment", "ib1e_status", OUT_ROOTS["ib1e"]),
    ]
    for stage, col, out_root in stage_defs:
        counts = case_df[col].value_counts().to_dict()
        statuses = set(case_df[col])
        if "FAIL" in statuses:
            official_status = "FAIL"
        elif "WARN" in statuses:
            official_status = "WARN"
        else:
            official_status = "PASS"
        stage_rows.append(
            {
                "stage": stage,
                "official_status": official_status,
                "output_root": str(out_root),
                "case_coverage_n": len(case_df),
                "case_coverage_expected_n": len(CASES),
                "qa_result_summary": ";".join(f"{k}={v}" for k, v in counts.items()),
            }
        )
    pd.DataFrame(stage_rows).to_csv(
        summary_root / "ib1_v1_3b_stage_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    md = [
        "# IB1 v1.3b contract QA pipeline summary",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "Formal IB1 input root:",
        "",
        "```text",
        r"outputs\ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa\\",
        "```",
        "",
        "## Stage Summary",
        "",
        "| stage | status | qa_result_summary |",
        "|---|---:|---|",
    ]
    for row in stage_rows:
        md.append(f"| {row['stage']} | {row['official_status']} | {row['qa_result_summary']} |")
    md.extend(
        [
            "",
            "## Case Summary",
            "",
            "| case_id | overall | IB1A | IB1C semantics | IB1C risk | IB1G | IB1E | IB2 ready |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in case_rows:
        md.append(
            f"| {row['case_id']} | {row['overall_status']} | {row['ib1a_status']} | "
            f"{row['ib1c_semantics_status']} | {row['ib1c_risk_status']} | "
            f"{row['ib1g_status']} | {row['ib1e_status']} | {row['ib2_ready']} |"
        )
    md.extend(
        [
            "",
            "## Decision",
            "",
            "IB1A / IB1C / IB1G / IB1E are complete if every stage status is PASS.",
            "",
            "Next formal input root for IB2D:",
            "",
            "```text",
            r"outputs\ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa\\",
            "```",
        ]
    )
    (summary_root / "ib1_v1_3b_pipeline_summary.md").write_text("\n".join(md), encoding="utf-8")
    (summary_root / "ib1_v1_3b_contract_qa_run_log.txt").write_text(
        "\n".join(log_lines),
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    cases = args.case_id or CASES
    log_lines = [
        "IB1 v1.3b contract QA run log",
        f"started_at={datetime.now().isoformat(timespec='seconds')}",
        f"ib0d_input_root={IB0D_ROOT}",
        "nlsc_tile_selector=route geometry / GPS bbox -> candidate 1/25,000 tile -> nlsc_raw/<tile>/向量25K/ContourL.shp -> route buffer intersection + valid elevation count",
    ]

    for root in OUT_ROOTS.values():
        root.mkdir(parents=True, exist_ok=True)

    for case_id in cases:
        meta = read_case_meta(case_id)
        case_name = meta["case_name"]
        activity_fp = meta["activity_fp"]
        ordered_path = IB0D_ROOT / case_id / "mainline_ordered_path_trimmed.geojson"
        mainline_fp = IB0B_ROOT / f"{case_id}_mainline_ib0_candidates.geojson"
        route_profile_csv = OUT_ROOTS["ib1a"] / case_id / f"{case_id}_route_profile.csv"
        route_profile_geojson = OUT_ROOTS["ib1a"] / case_id / f"{case_id}_route_profile_points.geojson"
        semantic_csv = (
            OUT_ROOTS["ib1c_semantics"]
            / case_id
            / f"{case_id}_route_profile_semantic_enriched.csv"
        )
        semantic_geojson = (
            OUT_ROOTS["ib1c_semantics"]
            / case_id
            / f"{case_id}_route_profile_semantic_enriched.geojson"
        )
        risk_csv = OUT_ROOTS["ib1c_risk"] / case_id / f"{case_id}_osm_semantic_risk_profile.csv"
        risk_geojson = (
            OUT_ROOTS["ib1c_risk"] / case_id / f"{case_id}_osm_semantic_risk_profile.geojson"
        )
        contour_csv = OUT_ROOTS["ib1g"] / case_id / f"{case_id}_contour_window_features.csv"
        contour_geojson = OUT_ROOTS["ib1g"] / case_id / f"{case_id}_contour_window_features.geojson"
        ib1e_csv = (
            OUT_ROOTS["ib1e"]
            / case_id
            / f"{case_id}_route_profile_contour_window_terrain_enriched.csv"
        )
        ib1e_geojson = (
            OUT_ROOTS["ib1e"]
            / case_id
            / f"{case_id}_route_profile_contour_window_terrain_enriched.geojson"
        )
        contour_selection = select_contour_tile(ordered_path)
        contour_fp = Path(contour_selection["contour_fp"])
        contour_tile = str(contour_selection["tile_id"])
        log_lines.extend(
            [
                "",
                f"NLSC tile selection case_id={case_id}",
                f"contour_tile={contour_tile}",
                f"contour_fp={contour_fp}",
                f"tile_reason={contour_selection['tile_reason']}",
                f"tile_candidates={contour_selection['all_candidates']}",
            ]
        )

        run_cmd(
            [
                sys.executable,
                "scripts/ib1_route_profile/ib1a_build_route_elevation_profile_cli_updated.py",
                "--case-id",
                case_id,
                "--case-name",
                case_name,
                "--activity-fp",
                activity_fp,
                "--activity-type",
                "auto",
                "--ordered-path-fp",
                str(ordered_path),
                "--mainline-fp",
                str(mainline_fp),
                "--out-dir",
                str(OUT_ROOTS["ib1a"] / case_id),
                "--qa-marker-interval-m",
                str(args.qa_marker_interval_m),
            ],
            log_lines,
        )
        run_cmd(
            [
                sys.executable,
                "scripts/ib1_route_profile/ib1c_enrich_route_profile_semantics_cli_updated.py",
                "--case-id",
                case_id,
                "--case-name",
                case_name,
                "--profile-csv",
                str(route_profile_csv),
                "--profile-geojson",
                str(route_profile_geojson),
                "--osm-raw-dir",
                str(PROJECT_ROOT / "osm_raw_output" / case_id),
                "--out-dir",
                str(OUT_ROOTS["ib1c_semantics"] / case_id),
            ],
            log_lines,
        )
        run_cmd(
            [
                sys.executable,
                "scripts/ib1_osm_semantics/ib1c_audit_osm_semantic_risk_mapping_cli_updated.py",
                "--case-id",
                case_id,
                "--case-name",
                case_name,
                "--semantic-csv",
                str(semantic_csv),
                "--mapping-csv",
                str(SEMANTIC_RISK_MAPPING_CSV),
                "--out-dir",
                str(OUT_ROOTS["ib1c_audit"] / case_id),
            ],
            log_lines,
        )
        run_cmd(
            [
                sys.executable,
                "scripts/ib1_osm_semantics/ib1c_apply_osm_semantic_risk_mapping_cli_updated.py",
                "--case-id",
                case_id,
                "--case-name",
                case_name,
                "--semantic-csv",
                str(semantic_csv),
                "--semantic-geojson",
                str(semantic_geojson),
                "--mapping-csv",
                str(SEMANTIC_RISK_MAPPING_CSV),
                "--out-dir",
                str(OUT_ROOTS["ib1c_risk"] / case_id),
            ],
            log_lines,
        )
        run_cmd(
            [
                sys.executable,
                "scripts/ib1_nlsc_terrain/ib1g_v2_compute_contour_window_features_cli_updated_v1_1.py",
                "--case-id",
                case_id,
                "--case-name",
                case_name,
                "--route-line-fp",
                str(ordered_path),
                "--contour-fp",
                str(contour_fp),
                "--tile",
                contour_tile,
                "--out-dir",
                str(OUT_ROOTS["ib1g"] / case_id),
            ],
            log_lines,
        )
        run_cmd(
            [
                sys.executable,
                "scripts/ib1_nlsc_terrain/ib1e_enrich_route_profile_with_contour_window_terrain_cli_updated.py",
                "--case-id",
                case_id,
                "--case-name",
                case_name,
                "--profile-csv",
                str(risk_csv),
                "--profile-geojson",
                str(risk_geojson),
                "--contour-csv",
                str(contour_csv),
                "--contour-geojson",
                str(contour_geojson),
                "--out-dir",
                str(OUT_ROOTS["ib1e"] / case_id),
            ],
            log_lines,
        )
        if not args.skip_plot:
            run_cmd(
                [
                    sys.executable,
                    "scripts/ib1_nlsc_terrain/ib1e_plot_osm_nlsc_terrain_risk_profile.py",
                    "--case-id",
                    case_id,
                    "--case-name",
                    case_name,
                    "--input-csv",
                    str(ib1e_csv),
                    "--input-geojson",
                    str(ib1e_geojson),
                    "--out-dir",
                    str(OUT_ROOTS["plot"] / case_id),
                ],
                log_lines,
            )

    case_rows = [validate_case(case_id) for case_id in cases]
    write_summaries(case_rows, log_lines)
    print(pd.DataFrame(case_rows)[["case_id", "overall_status", "ib2_ready"]].to_string(index=False))
    return 1 if any(row["overall_status"] == "FAIL" for row in case_rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
