# -*- coding: utf-8 -*-
"""Diagnose hydrology-topography weather sensitivity for THCI v1.0c review.

This review script does not modify THCI scores, does not rerun IB2D, and writes
only diagnostic evidence files.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(r"C:\mountain_work\115_osm")

try:
    import pandas as pd
except ModuleNotFoundError:
    venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
        os.execv(str(venv_python), [str(venv_python), __file__, *sys.argv[1:]])
    raise


DIAGNOSTIC_VERSION = "v1.0c_review"
OUT_ROOT = PROJECT_ROOT / "outputs" / "thci_weather_hydrology_topography_diagnostics_v1_0c_review"

IB1E_ROOT = PROJECT_ROOT / "outputs" / "ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa"
IB1C_ROOT = PROJECT_ROOT / "outputs" / "ib1c_route_profile_semantics_v1_3b_contract_qa"
WEATHER_DIAG_ROOT = PROJECT_ROOT / "outputs" / "thci_weather_sensitivity_diagnostics_v1_0b"
THCI_V10C_ROOT = PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_0c"

CASES = [
    "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b",
    "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b",
    "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b",
    "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b",
    "qixing_lengshuikeng_xiaoyoukeng_gpx_osmrefresh_v1_3b",
]

HYDROLOGY_PROXIMITY_M = 30.0
LOW_ELEVATION_QUANTILE = 0.35
VALLEY_NEAR_WATERWAY_M = 50.0
STEEP_SIDE_SLOPE_PCT = 15.0

WATER_CROSSING_TOKENS = {"ford", "crossing", "stream_crossing", "bridge", "water_crossing"}


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


def read_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def weights(df: pd.DataFrame) -> pd.Series:
    if "delta_dist_m" in df.columns:
        w = numeric(df["delta_dist_m"]).fillna(0.0).clip(lower=0.0)
        if float(w.sum()) > 0:
            return w
    if "dist_m" in df.columns:
        dist = numeric(df["dist_m"]).ffill().fillna(0.0)
        w = dist.diff().fillna(0.0).clip(lower=0.0)
        if float(w.sum()) > 0:
            return w
    return pd.Series([1.0] * len(df), index=df.index)


def weighted_length(df: pd.DataFrame, mask: pd.Series) -> float:
    if df.empty:
        return 0.0
    w = weights(df)
    return float(w[mask.fillna(False)].sum())


def ratio(length_m: float, total_m: float) -> float:
    return float(length_m / total_m) if total_m > 0 else 0.0


def total_distance(df: pd.DataFrame) -> float:
    if "dist_m" in df.columns:
        vals = numeric(df["dist_m"]).dropna()
        if not vals.empty:
            return float(vals.max())
    return float(weights(df).sum())


def boolish(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.lower().isin({"true", "1", "yes", "y"})


def text_contains(df: pd.DataFrame, cols: list[str], tokens: set[str]) -> tuple[pd.Series, list[str]]:
    mask = pd.Series(False, index=df.index)
    used_cols: list[str] = []
    pattern = "|".join(tokens)
    for col in cols:
        if col not in df.columns:
            continue
        text = df[col].fillna("").astype(str).str.lower()
        col_mask = text.str.contains(pattern, regex=True, na=False)
        if bool(col_mask.any()):
            used_cols.append(col)
            mask = mask | col_mask
    return mask, used_cols


def case_paths(case_id: str) -> dict[str, Path]:
    return {
        "ib1e_csv": IB1E_ROOT / case_id / f"{case_id}_route_profile_contour_window_terrain_enriched.csv",
        "ib1c_csv": IB1C_ROOT / case_id / f"{case_id}_route_profile_semantic_enriched.csv",
        "weather_sensitivity_csv": WEATHER_DIAG_ROOT / case_id / f"{case_id}_weather_sensitivity_diagnostic_v1_0b.csv",
        "thci_v1_0c_csv": THCI_V10C_ROOT / case_id / f"{case_id}_thci_axis_scores_v1_0c.csv",
    }


def hydrology_proximity_mask(df: pd.DataFrame) -> tuple[pd.Series, list[str]]:
    mask = pd.Series(False, index=df.index)
    used: list[str] = []
    if "near_waterway" in df.columns:
        part = boolish(df["near_waterway"])
        if bool(part.any()):
            used.append("near_waterway")
        mask = mask | part
    for col in ["dist_waterway_m", "dist_water_area_m", "dist_wetland_m"]:
        if col in df.columns:
            vals = numeric(df[col])
            part = vals.notna() & (vals <= HYDROLOGY_PROXIMITY_M)
            if bool(part.any()):
                used.append(col)
            mask = mask | part
    if "hydrology_flags" in df.columns:
        text = df["hydrology_flags"].fillna("").astype(str).str.lower()
        part = text.str.contains("waterway|water_area|wetland|stream|river|ditch|drainage|waterfall", regex=True, na=False)
        if bool(part.any()):
            used.append("hydrology_flags")
        mask = mask | part
    return mask, used


def water_crossing_mask(df: pd.DataFrame) -> tuple[pd.Series, list[str]]:
    mask = pd.Series(False, index=df.index)
    used: list[str] = []
    for col in ["osm_ford", "osm_bridge"]:
        if col in df.columns:
            text = df[col].fillna("").astype(str).str.lower()
            part = text.isin({"true", "1", "yes", "y"}) | text.str.contains("ford|bridge", regex=True, na=False)
            if bool(part.any()):
                used.append(col)
            mask = mask | part
    text_mask, text_cols = text_contains(
        df,
        ["hydrology_flags", "conditional_risk_domains", "unhandled_risk_domains", "osm_highway", "osm_surface"],
        WATER_CROSSING_TOKENS,
    )
    return mask | text_mask, used + text_cols


def low_elevation_mask(df: pd.DataFrame) -> tuple[pd.Series, float | None, str]:
    ele_col = "ele_smooth" if "ele_smooth" in df.columns else "ele_gpx_m" if "ele_gpx_m" in df.columns else ""
    if not ele_col:
        return pd.Series(False, index=df.index), None, ""
    ele = numeric(df[ele_col])
    threshold = ele.quantile(LOW_ELEVATION_QUANTILE)
    return ele.notna() & (ele <= threshold), float(threshold), ele_col


def valley_or_low_terrain_mask(df: pd.DataFrame, hydrology_mask: pd.Series, low_mask: pd.Series) -> tuple[pd.Series, list[str]]:
    mask = low_mask.copy()
    used = ["relative_low_elevation_quantile"]
    if "dist_waterway_m" in df.columns:
        near = numeric(df["dist_waterway_m"]).notna() & (numeric(df["dist_waterway_m"]) <= VALLEY_NEAR_WATERWAY_M)
        mask = mask | (near & low_mask)
        used.append("dist_waterway_m")
    if "slope_pct" in df.columns:
        steep_side = numeric(df["slope_pct"]).abs() >= STEEP_SIDE_SLOPE_PCT
        mask = mask | (hydrology_mask & low_mask & steep_side)
        used.append("slope_pct")
    if "slope_band_window_nlsc" in df.columns:
        band = df["slope_band_window_nlsc"].fillna("").astype(str).str.lower()
        steep_band = band.isin({"steep", "very_steep", "very steep", "high"})
        mask = mask | (hydrology_mask & low_mask & steep_band)
        used.append("slope_band_window_nlsc")
    return mask, used


def drainage_score(
    hydrology_ratio: float,
    low_overlap_ratio: float,
    valley_ratio: float,
    crossing_surge_score: float,
) -> float:
    return max(
        0.0,
        min(
            1.0,
            0.30 * min(1.0, hydrology_ratio / 0.30)
            + 0.30 * min(1.0, low_overlap_ratio / 0.20)
            + 0.25 * min(1.0, valley_ratio / 0.20)
            + 0.15 * crossing_surge_score,
        ),
    )


def crossing_score(crossing_presence: bool, crossing_ratio: float) -> float:
    if not crossing_presence:
        return 0.0
    return max(0.30, min(1.0, 0.30 + crossing_ratio * 3.0))


def note_for(row: dict[str, Any]) -> str:
    notes = []
    if row["water_crossing_presence"]:
        notes.append("Water crossing evidence exists; rain surge or temporary impassability should be reviewed.")
    if row["low_elevation_hydrology_overlap_ratio"] >= 0.10:
        notes.append("Hydrology proximity overlaps route-relative low elevation sections, suggesting drainage accumulation sensitivity.")
    if row["valley_or_low_terrain_proxy_ratio"] >= 0.10:
        notes.append("Valley/low-terrain proxy is non-trivial; rainwater concentration may exceed simple hydrology density.")
    if not notes:
        notes.append("No strong hydrology-topography amplification proxy was detected from current IB1E fields.")
    return " ".join(notes)


def diagnose_case(case_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    paths = case_paths(case_id)
    ib1e = read_csv(paths["ib1e_csv"])
    if ib1e is None or ib1e.empty:
        raise FileNotFoundError(paths["ib1e_csv"])
    total_m = total_distance(ib1e)

    hydro_mask, hydro_cols = hydrology_proximity_mask(ib1e)
    low_mask, low_threshold, ele_col = low_elevation_mask(ib1e)
    crossing_mask, crossing_cols = water_crossing_mask(ib1e)
    valley_mask, valley_cols = valley_or_low_terrain_mask(ib1e, hydro_mask, low_mask)

    hydro_len = weighted_length(ib1e, hydro_mask)
    low_hydro_len = weighted_length(ib1e, hydro_mask & low_mask)
    crossing_len = weighted_length(ib1e, crossing_mask)
    valley_len = weighted_length(ib1e, valley_mask)

    hydrology_proximity_ratio = ratio(hydro_len, total_m)
    low_overlap_ratio = ratio(low_hydro_len, total_m)
    crossing_ratio = ratio(crossing_len, total_m)
    valley_ratio = ratio(valley_len, total_m)
    surge = crossing_score(bool(crossing_mask.any()), crossing_ratio)
    drainage = drainage_score(hydrology_proximity_ratio, low_overlap_ratio, valley_ratio, surge)

    weather_diag = read_csv(paths["weather_sensitivity_csv"])
    thci_v10c = read_csv(paths["thci_v1_0c_csv"])
    weather_score = None
    if thci_v10c is not None and not thci_v10c.empty and "weather_impact_score" in thci_v10c.columns:
        weather_score = float(pd.to_numeric(thci_v10c["weather_impact_score"], errors="coerce").iloc[0])

    row: dict[str, Any] = {
        "case_id": case_id,
        "status": "PASS",
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "weather_impact_score_v1_0c": weather_score,
        "total_route_distance_m": total_m,
        "hydrology_proximity_ratio": hydrology_proximity_ratio,
        "hydrology_proximity_length_m": hydro_len,
        "low_elevation_hydrology_overlap_ratio": low_overlap_ratio,
        "low_elevation_hydrology_overlap_length_m": low_hydro_len,
        "water_crossing_presence": bool(crossing_mask.any()),
        "water_crossing_rows_n": int(crossing_mask.sum()),
        "water_crossing_length_m": crossing_len,
        "water_crossing_length_ratio": crossing_ratio,
        "valley_or_low_terrain_proxy_ratio": valley_ratio,
        "valley_or_low_terrain_proxy_length_m": valley_len,
        "drainage_accumulation_proxy_score": drainage,
        "crossing_surge_score": surge,
        "low_elevation_threshold_m": low_threshold,
        "elevation_column": ele_col,
        "hydrology_source_columns": "|".join(hydro_cols),
        "water_crossing_source_columns": "|".join(crossing_cols),
        "valley_proxy_source_columns": "|".join(valley_cols),
    }
    row["hydrology_topography_weather_note"] = note_for(row)

    summary = {
        "case_id": case_id,
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "status": "PASS",
        "input_roots": {
            "ib1e": str(IB1E_ROOT),
            "ib1c": str(IB1C_ROOT),
            "weather_sensitivity_diagnostics_v1_0b": str(WEATHER_DIAG_ROOT),
            "thci_axis_scores_v1_0c": str(THCI_V10C_ROOT),
        },
        "source_files": {key: str(path) for key, path in paths.items()},
        "source_weather_sensitivity_row": (
            weather_diag.iloc[0].to_dict() if weather_diag is not None and not weather_diag.empty else {}
        ),
        "metrics": row,
        "thresholds": {
            "HYDROLOGY_PROXIMITY_M": HYDROLOGY_PROXIMITY_M,
            "LOW_ELEVATION_QUANTILE": LOW_ELEVATION_QUANTILE,
            "VALLEY_NEAR_WATERWAY_M": VALLEY_NEAR_WATERWAY_M,
            "STEEP_SIDE_SLOPE_PCT": STEEP_SIDE_SLOPE_PCT,
        },
        "note": row["hydrology_topography_weather_note"],
        "score_modified": False,
        "ib2d_rerun": False,
        "runtime_llm_allowed": False,
    }
    return row, summary


def write_case_outputs(case_id: str, row: dict[str, Any], summary: dict[str, Any]) -> None:
    out_dir = OUT_ROOT / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([row]).to_csv(
        out_dir / f"{case_id}_hydro_topo_diag_v1_0c_review.csv",
        index=False,
        encoding="utf-8-sig",
    )
    (out_dir / f"{case_id}_hydro_topo_summary_v1_0c_review.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_batch_summary(rows: list[dict[str, Any]]) -> None:
    batch_dir = OUT_ROOT / "_batch_summary"
    batch_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(
        batch_dir / "thci_weather_hydrology_topography_diagnostic_v1_0c_review_case_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )


def main() -> int:
    args = parse_args()
    rows: list[dict[str, Any]] = []
    failures = 0
    for case_id in resolve_cases(args):
        try:
            row, summary = diagnose_case(case_id)
            write_case_outputs(case_id, row, summary)
            rows.append(row)
            print(
                f"{case_id}: PASS "
                f"hydro={row['hydrology_proximity_ratio']:.4f} "
                f"low_hydro={row['low_elevation_hydrology_overlap_ratio']:.4f} "
                f"crossing={row['water_crossing_presence']} "
                f"valley={row['valley_or_low_terrain_proxy_ratio']:.4f} "
                f"drainage={row['drainage_accumulation_proxy_score']:.4f} "
                f"surge={row['crossing_surge_score']:.4f}"
            )
        except Exception as exc:
            failures += 1
            row = {
                "case_id": case_id,
                "status": "FAIL",
                "diagnostic_version": DIAGNOSTIC_VERSION,
                "hydrology_topography_weather_note": str(exc),
            }
            rows.append(row)
            print(f"{case_id}: FAIL {exc}")
    if rows:
        write_batch_summary(rows)
    print(
        "batch summary:",
        OUT_ROOT / "_batch_summary" / "thci_weather_hydrology_topography_diagnostic_v1_0c_review_case_summary.csv",
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
