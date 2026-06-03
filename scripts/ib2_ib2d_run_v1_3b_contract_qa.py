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

IB1E_ROOT = PROJECT_ROOT / "outputs" / "ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa"
IB1G_ROOT = PROJECT_ROOT / "outputs" / "ib1g_contour_window_features_v1_3b_contract_qa"
IB2_ROOT = PROJECT_ROOT / "outputs" / "ib2_v2_route_risk_v1_3b_contract_qa"
IB2D_ROOT = PROJECT_ROOT / "outputs" / "ib2d_route_risk_offline_map_v1_3b_contract_qa"
BATCH_ROOT = IB2D_ROOT / "_batch_summary"

IB2_SCRIPT = PROJECT_ROOT / "scripts" / "ib2_route_risk" / "ib2_v2_route_risk_scoring_cli_updated.py"
IB2D_SCRIPT = PROJECT_ROOT / "scripts" / "ib2_route_risk" / "ib2d_plot_route_risk_offline_map_cli_updated.py"

WEATHER_MODE = "not_integrated_at_ib2d"
WEATHER_SCOPE = "future_ib3_activity_layer"

REQUIRED_IB2_COLUMNS = [
    "dist_m",
    "lat",
    "lon",
    "risk_score",
    "risk_score_raw",
    "risk_score_smooth",
    "risk_band",
    "effort_score",
    "exposure_score",
    "terrain_score",
    "effort_slope_band",
    "route_data_ok",
    "risk_reason",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def path_str(path: Path) -> str:
    return str(path)


def ib1e_csv(case_id: str) -> Path:
    return IB1E_ROOT / case_id / f"{case_id}_route_profile_contour_window_terrain_enriched.csv"


def ib1e_geojson(case_id: str) -> Path:
    return IB1E_ROOT / case_id / f"{case_id}_route_profile_contour_window_terrain_enriched.geojson"


def ib1e_summary(case_id: str) -> Path:
    return IB1E_ROOT / case_id / f"{case_id}_route_profile_contour_window_terrain_summary.csv"


def ib1g_csv(case_id: str) -> Path:
    return IB1G_ROOT / case_id / f"{case_id}_contour_window_features.csv"


def ib2_csv(case_id: str) -> Path:
    return IB2_ROOT / case_id / f"{case_id}_route_risk_v2.csv"


def ib2_geojson(case_id: str) -> Path:
    return IB2_ROOT / case_id / f"{case_id}_route_risk_v2.geojson"


def ib2_summary(case_id: str) -> Path:
    return IB2_ROOT / case_id / f"{case_id}_route_risk_v2_summary.csv"


def contour_tiles() -> dict[str, Path]:
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


def prior_ib1g_tile(case_id: str) -> tuple[str, str]:
    fp = ib1g_csv(case_id)
    if not fp.exists():
        return "", ""
    try:
        row = pd.read_csv(fp, nrows=1, encoding="utf-8-sig").iloc[0]
        return str(row.get("nlsc_tile", "")), str(row.get("contour_fp", ""))
    except Exception:
        return "", ""


def route_buffer(case_id: str):
    gdf = gpd.read_file(ib1e_geojson(case_id))
    metric = gdf.to_crs(gdf.estimate_utm_crs() or "EPSG:3826")
    return metric, metric.union_all().convex_hull.buffer(350)


def assign_tiles() -> list[dict[str, object]]:
    tiles = contour_tiles()
    rows: list[dict[str, object]] = []
    for case_id in CASES:
        metric, buffer_geom = route_buffer(case_id)
        hits: dict[str, int] = {}
        valid_elev: dict[str, int] = {}
        for tile, contour_fp in tiles.items():
            contour = gpd.read_file(contour_fp).to_crs(metric.crs)
            hit = contour[contour.intersects(buffer_geom)].copy()
            hits[tile] = int(len(hit))
            valid_elev[tile] = valid_elevation_count(hit)
        best_tile = max(hits, key=lambda tile: (hits[tile], valid_elev.get(tile, 0))) if hits else ""
        best_hits = hits.get(best_tile, 0)
        best_valid_elev = valid_elev.get(best_tile, 0)
        prior_tile, prior_fp = prior_ib1g_tile(case_id)
        if best_hits <= 0 or best_valid_elev <= 0:
            contour_fp = Path(prior_fp) if prior_fp else Path("")
            reason = f"WARN: no contour tile intersects 350 m route buffer with valid elevation data; prior_ib1g_tile={prior_tile}; hits={hits}; valid_elevation={valid_elev}"
            used = False
        else:
            contour_fp = tiles[best_tile]
            reason = f"selected by route-buffer contour intersections + valid elevation count; hits={hits}; valid_elevation={valid_elev}; prior_ib1g_tile={prior_tile or 'unknown'}"
            if prior_tile and prior_tile != best_tile:
                reason += "; prior IB1G tile differs and should be reviewed upstream"
            used = True
        rows.append(
            {
                "case_id": case_id,
                "contour_tile": best_tile,
                "contour_fp": str(contour_fp),
                "tile_reason": reason,
                "contour_fp_exists": bool(contour_fp and contour_fp.exists()),
                "used_by_ib2d": used,
                "prior_ib1g_tile": prior_tile,
                "prior_ib1g_contour_fp": prior_fp,
                "nw_hits": hits.get("97233NW", 0),
                "sw_hits": hits.get("97233SW", 0),
                "nw_valid_elevation_count": valid_elev.get("97233NW", 0),
                "sw_valid_elevation_count": valid_elev.get("97233SW", 0),
            }
        )
    return rows


def run_command(cmd: list[str]) -> tuple[int, str]:
    completed = subprocess.run(cmd, cwd=PROJECT_ROOT, text=True, capture_output=True)
    text = "\n".join(
        [
            "$ " + " ".join(f'"{part}"' if " " in part else part for part in cmd),
            f"exit_code={completed.returncode}",
            "--- stdout ---",
            completed.stdout,
            "--- stderr ---",
            completed.stderr,
        ]
    )
    return completed.returncode, text


def run_ib2(case_id: str) -> tuple[str, str]:
    out_dir = IB2_ROOT / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(IB2_SCRIPT),
        "--case-id",
        case_id,
        "--case-name",
        case_id,
        "--input-csv",
        str(ib1e_csv(case_id)),
        "--input-geojson",
        str(ib1e_geojson(case_id)),
        "--out-dir",
        str(out_dir),
    ]
    code, log = run_command(cmd)
    return ("PASS" if code == 0 else "FAIL"), log


def run_ib2d(case_id: str, contour_fp: Path) -> tuple[str, str]:
    out_dir = IB2D_ROOT / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(IB2D_SCRIPT),
        "--case-id",
        case_id,
        "--case-name",
        case_id,
        "--risk-csv",
        str(ib2_csv(case_id)),
        "--risk-geojson",
        str(ib2_geojson(case_id)),
        "--profile-geojson",
        str(ib1e_geojson(case_id)),
        "--osm-raw-dir",
        str(PROJECT_ROOT / "osm_raw_output" / case_id),
        "--contour-fp",
        str(contour_fp),
        "--out-dir",
        str(out_dir),
    ]
    code, log = run_command(cmd)
    return ("PASS" if code == 0 else "FAIL"), log


def read_summary_row(case_id: str) -> dict[str, object]:
    summary_fp = ib2_summary(case_id)
    if not summary_fp.exists():
        return {}
    return pd.read_csv(summary_fp, encoding="utf-8-sig").iloc[0].to_dict()


def validate_case(case_id: str, ib2_status: str, ib2d_status: str, tile_row: dict[str, object]) -> dict[str, object]:
    row: dict[str, object] = {
        "case_id": case_id,
        "ib2_scoring_status": ib2_status,
        "ib2d_map_status": ib2d_status,
        "overall_status": "FAIL",
        "risk_rows": 0,
        "risk_geojson_rows": 0,
        "segments_n": 0,
        "risk_band_low_count": 0,
        "risk_band_moderate_count": 0,
        "risk_band_high_count": 0,
        "risk_band_very_high_count": 0,
        "risk_band_unknown_count": 0,
        "route_data_ok_count": 0,
        "route_data_mismatch_count": 0,
        "map_png_exists": False,
        "segments_geojson_exists": False,
        "radar_png_exists": False,
        "combined_map_radar_png_exists": False,
        "osm_raw_dir_exists": (PROJECT_ROOT / "osm_raw_output" / case_id).exists(),
        "contour_tile": tile_row.get("contour_tile", ""),
        "contour_fp": tile_row.get("contour_fp", ""),
        "weather_mode": WEATHER_MODE,
        "weather_scope": WEATHER_SCOPE,
        "blocking_issue": "",
        "warning_note": "",
    }

    required_outputs = [ib2_csv(case_id), ib2_geojson(case_id), ib2_summary(case_id)]
    missing_ib2 = [str(fp) for fp in required_outputs if not fp.exists()]
    missing_cols: list[str] = []
    if ib2_csv(case_id).exists():
        risk_df = pd.read_csv(ib2_csv(case_id), low_memory=False, encoding="utf-8-sig")
        row["risk_rows"] = int(len(risk_df))
        missing_cols = [col for col in REQUIRED_IB2_COLUMNS if col not in risk_df.columns]
        if "risk_band" in risk_df.columns:
            counts = risk_df["risk_band"].fillna("unknown").astype(str).value_counts().to_dict()
            for band in ["low", "moderate", "high", "very_high", "unknown"]:
                row[f"risk_band_{band}_count"] = int(counts.get(band, 0))
        if "route_data_ok" in risk_df.columns:
            ok = risk_df["route_data_ok"].astype(str).str.lower().isin(["true", "1", "yes"])
            row["route_data_ok_count"] = int(ok.sum())
            row["route_data_mismatch_count"] = int((~ok).sum())
    if ib2_geojson(case_id).exists():
        row["risk_geojson_rows"] = int(len(gpd.read_file(ib2_geojson(case_id))))

    case_out = IB2D_ROOT / case_id
    map_png = case_out / f"{case_id}_route_risk_offline_map.png"
    seg_geojson = case_out / f"{case_id}_route_risk_offline_segments.geojson"
    radar_png = case_out / f"{case_id}_route_challenge_radar.png"
    combined_png = case_out / f"{case_id}_route_risk_offline_map_with_radar.png"
    row["map_png_exists"] = map_png.exists()
    row["segments_geojson_exists"] = seg_geojson.exists()
    row["radar_png_exists"] = radar_png.exists()
    row["combined_map_radar_png_exists"] = combined_png.exists()
    if seg_geojson.exists():
        seg = gpd.read_file(seg_geojson)
        row["segments_n"] = int(len(seg))
        if "risk_band" in seg.columns:
            counts = seg["risk_band"].fillna("unknown").astype(str).value_counts().to_dict()
            for band in ["low", "moderate", "high", "very_high", "unknown"]:
                row[f"risk_band_{band}_count"] = int(counts.get(band, row[f"risk_band_{band}_count"]))

    summary = read_summary_row(case_id)
    if summary:
        row["route_data_ok_count"] = int(summary.get("route_data_ok_count", row["route_data_ok_count"]))
        row["route_data_mismatch_count"] = int(summary.get("route_data_mismatch_count", row["route_data_mismatch_count"]))

    failures: list[str] = []
    warnings: list[str] = []
    if ib2_status != "PASS":
        failures.append("IB2_v2 scoring CLI failed")
    if ib2d_status != "PASS":
        failures.append("IB2D offline map CLI failed")
    if missing_ib2:
        failures.append("missing IB2 outputs: " + "; ".join(missing_ib2))
    if missing_cols:
        failures.append("missing IB2 required columns: " + "; ".join(missing_cols))
    for key in ["map_png_exists", "segments_geojson_exists", "radar_png_exists", "combined_map_radar_png_exists"]:
        if not row[key]:
            failures.append(f"{key}=False")
    if not row["osm_raw_dir_exists"]:
        failures.append("OSM raw dir missing")
    if not tile_row.get("contour_fp_exists", False):
        failures.append("NLSC contour fp missing")
    if int(row["risk_band_unknown_count"]) >= int(row["segments_n"] or 0) and int(row["segments_n"] or 0) > 0:
        failures.append("segment risk_band all unknown")
    if int(row["route_data_mismatch_count"]) > 0:
        warnings.append(f"route_data_mismatch_count={row['route_data_mismatch_count']}")
    if tile_row.get("prior_ib1g_tile") and tile_row.get("prior_ib1g_tile") != tile_row.get("contour_tile"):
        warnings.append("IB2D contour tile differs from prior IB1G record; upstream IB1G/IB1E tile should be reviewed")

    if failures:
        row["overall_status"] = "FAIL"
        row["blocking_issue"] = "; ".join(failures)
    elif warnings:
        row["overall_status"] = "WARN"
        row["warning_note"] = "; ".join(warnings)
    else:
        row["overall_status"] = "PASS"
    return row


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_stage_summary(rows: list[dict[str, object]], tile_rows: list[dict[str, object]]) -> None:
    counts = pd.Series([row["overall_status"] for row in rows]).value_counts().to_dict()
    stage_status = "PASS" if all(row["overall_status"] == "PASS" for row in rows) else "WARN" if all(row["overall_status"] in {"PASS", "WARN"} for row in rows) else "FAIL"
    lines = [
        "# IB2 / IB2D v1.3b contract QA stage summary",
        "",
        f"- generated_at_utc: {utc_now()}",
        f"- stage_status: {stage_status}",
        f"- ib2_script: `{IB2_SCRIPT}`",
        f"- ib2d_script: `{IB2D_SCRIPT}`",
        f"- ib2_input_root: `{IB1E_ROOT}`",
        f"- ib2_output_root: `{IB2_ROOT}`",
        f"- ib2d_output_root: `{IB2D_ROOT}`",
        "- formal_mainline: IB1E v1.3b contract QA output -> IB2_v2 route risk scoring CLI updated -> IB2D offline map CLI updated",
        "- pyc_policy: __pycache__ files are execution cache only, not formal source",
        "- stage_role: route-level baseline risk visualization",
        "- risk_sources: IB1C OSM semantic risk + IB1G NLSC contour/terrain window features + IB1E terrain/hydro baseline enrichment + IB2_v2 scoring + IB2D map/radar",
        f"- weather_mode: `{WEATHER_MODE}`",
        f"- weather_scope: `{WEATHER_SCOPE}`",
        "- observed_weather_integrated: False",
        f"- status_counts: {counts}",
        "",
        "## NLSC Tile Selection Specification",
        "",
        "Specification basis:",
        "",
        "```text",
        "113 年度「臺灣地區經建版地形圖」製圖作業工作總報告書",
        "```",
        "",
        "Applied assumptions:",
        "",
        "```text",
        "經建版地形圖包含 1/25,000、1/50,000、1/100,000。",
        r"nlsc_raw\<tile>\向量25K\ContourL.shp 對應 1/25,000 圖資。",
        "1/25,000 圖幅經緯度範圍為 7'30\" x 7'30\"。",
        "投影為橫麥卡脫 TM 投影，經差二度分帶；臺灣地區中央子午線 121°E。",
        "大地基準採 TWD97，高程基準採 TWVD2001。",
        "1/25,000 等高線規格：計曲線 50m、首曲線 10m、間曲線 5m。",
        "```",
        "",
        "Selector definition:",
        "",
        "```text",
        "route geometry / GPS bbox",
        "-> candidate 1/25,000 tile",
        r"-> nlsc_raw\<tile>\向量25K\ContourL.shp",
        "-> route buffer intersection + valid elevation count validation",
        "```",
        "",
        "## Tile Assignment",
        "",
        "| case_id | contour_tile | contour_fp_exists | used_by_ib2d | NW hits / valid elev | SW hits / valid elev | tile_reason |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for row in tile_rows:
        lines.append(
            f"| {row['case_id']} | {row['contour_tile']} | {row['contour_fp_exists']} | {row['used_by_ib2d']} | {row.get('nw_hits', 0)} / {row.get('nw_valid_elevation_count', 0)} | {row.get('sw_hits', 0)} / {row.get('sw_valid_elevation_count', 0)} | {str(row['tile_reason']).replace('|', '/')} |"
        )

    lines.extend(
        [
            "",
            "## Case Summary",
            "",
            "| case_id | status | ib2 | ib2d | rows | segments | route_data_mismatch | low | moderate | high | very_high | unknown | note |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in rows:
        note = row.get("blocking_issue") or row.get("warning_note") or ""
        lines.append(
            "| {case_id} | {overall_status} | {ib2} | {ib2d} | {risk_rows} | {segments_n} | {mismatch} | {low} | {moderate} | {high} | {very_high} | {unknown} | {note} |".format(
                case_id=row["case_id"],
                overall_status=row["overall_status"],
                ib2=row["ib2_scoring_status"],
                ib2d=row["ib2d_map_status"],
                risk_rows=row["risk_rows"],
                segments_n=row["segments_n"],
                mismatch=row["route_data_mismatch_count"],
                low=row["risk_band_low_count"],
                moderate=row["risk_band_moderate_count"],
                high=row["risk_band_high_count"],
                very_high=row["risk_band_very_high_count"],
                unknown=row["risk_band_unknown_count"],
                note=str(note).replace("|", "/"),
            )
        )

    lines.extend(
        [
            "",
            "## Decision",
            "",
            "The v1.3b route-level baseline risk visualization checkpoint is established when every case is PASS or acceptable WARN.",
        ]
    )
    (BATCH_ROOT / "ib2d_v1_3b_contract_qa_stage_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    BATCH_ROOT.mkdir(parents=True, exist_ok=True)
    logs = [
        f"IB2 / IB2D v1.3b contract QA run started at {utc_now()}",
        f"ib2_script_exists={IB2_SCRIPT.exists()}",
        f"ib2d_script_exists={IB2D_SCRIPT.exists()}",
        f"weather_mode={WEATHER_MODE}",
        f"weather_scope={WEATHER_SCOPE}",
    ]
    for script in [IB2_SCRIPT, IB2D_SCRIPT]:
        code, log = run_command([sys.executable, "-m", "py_compile", str(script)])
        logs.append(log)
        if code != 0:
            raise RuntimeError(f"py_compile failed: {script}")

    tile_rows = assign_tiles()
    write_csv(
        BATCH_ROOT / "ib2d_v1_3b_contract_qa_tile_assignment.csv",
        tile_rows,
        [
            "case_id",
            "contour_tile",
            "contour_fp",
            "tile_reason",
            "contour_fp_exists",
            "used_by_ib2d",
            "prior_ib1g_tile",
            "prior_ib1g_contour_fp",
            "nw_hits",
            "sw_hits",
            "nw_valid_elevation_count",
            "sw_valid_elevation_count",
        ],
    )

    rows: list[dict[str, object]] = []
    tile_by_case = {row["case_id"]: row for row in tile_rows}
    for case_id in CASES:
        ib2_status, log = run_ib2(case_id)
        logs.append(log)
        contour_fp = Path(str(tile_by_case[case_id]["contour_fp"]))
        ib2d_status, log = run_ib2d(case_id, contour_fp)
        logs.append(log)
        row = validate_case(case_id, ib2_status, ib2d_status, tile_by_case[case_id])
        rows.append(row)
        print(f"{case_id}: {row['overall_status']}")

    fields = [
        "case_id",
        "ib2_scoring_status",
        "ib2d_map_status",
        "overall_status",
        "risk_rows",
        "risk_geojson_rows",
        "segments_n",
        "risk_band_low_count",
        "risk_band_moderate_count",
        "risk_band_high_count",
        "risk_band_very_high_count",
        "risk_band_unknown_count",
        "route_data_ok_count",
        "route_data_mismatch_count",
        "map_png_exists",
        "segments_geojson_exists",
        "radar_png_exists",
        "combined_map_radar_png_exists",
        "osm_raw_dir_exists",
        "contour_tile",
        "contour_fp",
        "weather_mode",
        "weather_scope",
        "blocking_issue",
        "warning_note",
    ]
    write_csv(BATCH_ROOT / "ib2_v1_3b_contract_qa_case_summary.csv", rows, fields)
    write_stage_summary(rows, tile_rows)
    logs.append(f"IB2 / IB2D v1.3b contract QA run finished at {utc_now()}")
    (BATCH_ROOT / "ib2_ib2d_v1_3b_contract_qa_run_log.txt").write_text("\n\n".join(logs) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
