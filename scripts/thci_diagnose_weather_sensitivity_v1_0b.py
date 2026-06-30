# -*- coding: utf-8 -*-
"""Diagnose THCI v1.0b weather sensitivity without changing scores."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(r"D:\mountain_work\115_osm")

try:
    import pandas as pd
except ModuleNotFoundError:
    venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
        os.execv(str(venv_python), [str(venv_python), __file__, *sys.argv[1:]])
    raise


DIAGNOSTIC_VERSION = "v1.0b"

STEEP_SLOPE_PCT = 20
VERY_STEEP_SLOPE_PCT = 30
HIGH_STEPS_RATIO = 0.30
HIGH_HYDROLOGY_RATIO = 0.05
HIGH_SLIPPERY_SURFACE_RATIO = 0.10
HIGH_EXPOSURE_RATIO = 0.05
LOW_WEATHER_SCORE_THRESHOLD = 0.25

CASES = [
    "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b",
    "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b",
    "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b",
    "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b",
    "qixing_lengshuikeng_xiaoyoukeng_gpx_osmrefresh_v1_3b",
]

INPUT_ROOTS = {
    "ib1e": PROJECT_ROOT / "outputs" / "ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa",
    "ib1c": PROJECT_ROOT / "outputs" / "ib1c_route_profile_semantics_v1_3b_contract_qa",
    "thci_axis_scores_v1_0b": PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_0b",
    "thci_route_metric_summary_v1": PROJECT_ROOT / "outputs" / "thci_route_metric_summary_v1",
}

OUT_ROOT = PROJECT_ROOT / "outputs" / "thci_weather_sensitivity_diagnostics_v1_0b"

AXES = [
    "physical_difficulty_score",
    "technical_difficulty_score",
    "baseline_hazard_score",
    "navigation_risk_score",
    "support_difficulty_score",
    "weather_impact_score",
]

HYDROLOGY_TOKENS = {
    "waterway",
    "stream",
    "river",
    "ditch",
    "drainage",
    "crossing",
    "bridge",
    "waterfall",
    "wetland",
    "ford",
}

SLIPPERY_SURFACE_TOKENS = {
    "mud",
    "dirt",
    "ground",
    "earth",
    "unpaved",
    "gravel",
    "rock",
    "stone",
    "grass",
    "wet",
    "slippery",
}

EXPOSURE_TOKENS = {
    "ridge",
    "peak",
    "cliff",
    "bare_rock",
    "scree",
    "exposed",
    "summit",
    "saddle",
}


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
    return pd.read_csv(path, low_memory=False, encoding="utf-8-sig")


def case_paths(case_id: str) -> dict[str, Path]:
    return {
        "ib1e_csv": INPUT_ROOTS["ib1e"] / case_id / f"{case_id}_route_profile_contour_window_terrain_enriched.csv",
        "ib1c_csv": INPUT_ROOTS["ib1c"] / case_id / f"{case_id}_route_profile_semantic_enriched.csv",
        "axis_score_csv": INPUT_ROOTS["thci_axis_scores_v1_0b"] / case_id / f"{case_id}_thci_axis_scores_v1_0b.csv",
        "route_metric_summary_csv": INPUT_ROOTS["thci_route_metric_summary_v1"] / "five_route_distance_gain_stairs_summary.csv",
    }


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def weights(df: pd.DataFrame) -> pd.Series:
    if "delta_dist_m" in df.columns:
        out = numeric(df["delta_dist_m"]).fillna(0.0).clip(lower=0.0)
        if float(out.sum()) > 0:
            return out
    if "dist_m" in df.columns:
        dist = numeric(df["dist_m"]).fillna(method="ffill").fillna(0.0)
        out = dist.diff().fillna(0.0).clip(lower=0.0)
        if float(out.sum()) > 0:
            return out
    return pd.Series([1.0] * len(df), index=df.index)


def weighted_length(df: pd.DataFrame, mask: pd.Series) -> float:
    if df is None or df.empty:
        return 0.0
    w = weights(df)
    return float(w[mask.fillna(False)].sum())


def total_distance(df: pd.DataFrame | None, route_metric_row: dict[str, Any] | None) -> float:
    if route_metric_row:
        value = route_metric_row.get("total_route_distance_m")
        if pd.notna(value):
            return float(value)
    if df is not None and not df.empty and "dist_m" in df.columns:
        vals = numeric(df["dist_m"]).dropna()
        if not vals.empty:
            return float(vals.max())
    return 0.0


def ratio(length_m: float, total_m: float) -> float:
    return float(length_m / total_m) if total_m > 0 else 0.0


def text_mask(df: pd.DataFrame | None, tokens: set[str], cols_hint: list[str] | None = None) -> tuple[pd.Series, list[str]]:
    if df is None or df.empty:
        return pd.Series(dtype=bool), []
    cols = cols_hint or []
    cols = [col for col in cols if col in df.columns]
    if not cols:
        cols = [
            col
            for col in df.columns
            if any(token in col.lower() for token in tokens)
            or any(key in col.lower() for key in ["osm_", "hydrology", "surface", "terrain", "exposure", "near_", "dist_"])
        ]
    mask = pd.Series(False, index=df.index)
    used_cols: list[str] = []
    token_pattern = "|".join(tokens)
    for col in cols:
        name_hit = any(token in col.lower() for token in tokens)
        series = df[col]
        col_mask = pd.Series(False, index=df.index)
        if name_hit:
            if col.lower().startswith("near_"):
                col_mask = series.astype(str).str.lower().isin({"true", "1", "yes", "y"})
            elif col.lower().startswith("dist_"):
                vals = numeric(series)
                col_mask = vals.notna() & (vals <= 20.0)
            else:
                text = series.fillna("").astype(str).str.lower()
                col_mask = text.ne("") & text.ne("nan") & text.ne("<na>")
        text = series.fillna("").astype(str).str.lower()
        col_mask = col_mask | text.str.contains(token_pattern, regex=True, na=False)
        if bool(col_mask.any()):
            used_cols.append(col)
            mask = mask | col_mask
    return mask, used_cols


def load_route_metric_row(case_id: str) -> tuple[dict[str, Any] | None, Path]:
    fp = INPUT_ROOTS["thci_route_metric_summary_v1"] / "five_route_distance_gain_stairs_summary.csv"
    df = read_csv(fp)
    if df is None or df.empty or "case_id" not in df.columns:
        return None, fp
    hit = df[df["case_id"].astype(str) == case_id]
    if hit.empty:
        return None, fp
    return hit.iloc[0].to_dict(), fp


def load_axis_scores(case_id: str, fp: Path) -> dict[str, float | None]:
    df = read_csv(fp)
    out = {axis: None for axis in AXES}
    if df is None or df.empty:
        return out
    row = df.iloc[0]
    for axis in AXES:
        if axis in df.columns:
            value = pd.to_numeric(pd.Series([row[axis]]), errors="coerce").iloc[0]
            out[axis] = None if pd.isna(value) else float(value)
    return out


def compute_steps_metrics(
    ib1e: pd.DataFrame | None,
    ib1c: pd.DataFrame | None,
    route_metric_row: dict[str, Any] | None,
    total_m: float,
) -> dict[str, float]:
    if route_metric_row:
        ascent = float(route_metric_row.get("ascent_steps_length_m") or 0.0)
        descent = float(route_metric_row.get("descent_steps_length_m") or 0.0)
        total_steps = float(route_metric_row.get("total_steps_length_m") or 0.0)
    else:
        source = ib1e if ib1e is not None else ib1c
        if source is None or source.empty or "osm_highway" not in source.columns:
            ascent = descent = total_steps = 0.0
        else:
            step_mask = source["osm_highway"].fillna("").astype(str).str.lower().eq("steps")
            delta_ele = numeric(source["delta_ele_m"]) if "delta_ele_m" in source.columns else pd.Series(0.0, index=source.index)
            ascent = weighted_length(source, step_mask & (delta_ele > 0))
            descent = weighted_length(source, step_mask & (delta_ele < 0))
            total_steps = weighted_length(source, step_mask)
    return {
        "ascent_steps_length_m": ascent,
        "descent_steps_length_m": descent,
        "total_steps_length_m": total_steps,
        "steps_length_ratio": ratio(total_steps, total_m),
        "ascent_steps_ratio": ratio(ascent, total_m),
        "descent_steps_ratio": ratio(descent, total_m),
    }


def compute_slope_metrics(df: pd.DataFrame | None, total_m: float) -> dict[str, float]:
    if df is None or df.empty or "slope_pct" not in df.columns:
        return {
            "steep_slope_ratio": 0.0,
            "very_steep_slope_ratio": 0.0,
            "downhill_steep_ratio": 0.0,
            "uphill_steep_ratio": 0.0,
        }
    slope = numeric(df["slope_pct"]).abs()
    delta_ele = numeric(df["delta_ele_m"]) if "delta_ele_m" in df.columns else pd.Series(0.0, index=df.index)
    steep = slope >= STEEP_SLOPE_PCT
    very_steep = slope >= VERY_STEEP_SLOPE_PCT
    return {
        "steep_slope_ratio": ratio(weighted_length(df, steep), total_m),
        "very_steep_slope_ratio": ratio(weighted_length(df, very_steep), total_m),
        "downhill_steep_ratio": ratio(weighted_length(df, steep & (delta_ele < 0)), total_m),
        "uphill_steep_ratio": ratio(weighted_length(df, steep & (delta_ele > 0)), total_m),
    }


def token_metrics(
    primary: pd.DataFrame | None,
    secondary: pd.DataFrame | None,
    tokens: set[str],
    total_m: float,
    cols_hint: list[str],
    prefix: str,
) -> dict[str, Any]:
    source = primary if primary is not None else secondary
    if source is None:
        return {
            f"{prefix}_rows_n": 0,
            f"{prefix}_length_m": 0.0,
            f"{prefix}_length_ratio": 0.0,
            f"{prefix}_source_columns": [],
        }
    mask, used_cols = text_mask(source, tokens, cols_hint)
    length_m = weighted_length(source, mask)
    return {
        f"{prefix}_rows_n": int(mask.sum()) if not mask.empty else 0,
        f"{prefix}_length_m": length_m,
        f"{prefix}_length_ratio": ratio(length_m, total_m),
        f"{prefix}_source_columns": used_cols,
    }


def diagnose_case(case_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    paths = case_paths(case_id)
    ib1e = read_csv(paths["ib1e_csv"])
    ib1c = read_csv(paths["ib1c_csv"])
    route_metric_row, route_metric_fp = load_route_metric_row(case_id)
    axis_scores = load_axis_scores(case_id, paths["axis_score_csv"])
    profile_source = ib1e if ib1e is not None else ib1c
    total_m = total_distance(profile_source, route_metric_row)

    missing_inputs = [
        str(path)
        for key, path in paths.items()
        if key != "route_metric_summary_csv" and not path.exists()
    ]
    status = "FAIL" if missing_inputs else "PASS"
    note = "diagnostic only; THCI v1.0b scores and IB2D outputs were not modified."
    if missing_inputs:
        note += " Missing inputs: " + "; ".join(missing_inputs)

    steps = compute_steps_metrics(ib1e, ib1c, route_metric_row, total_m)
    slope = compute_slope_metrics(ib1e, total_m)
    hydrology = token_metrics(
        ib1e,
        ib1c,
        HYDROLOGY_TOKENS,
        total_m,
        ["hydrology_flags", "near_waterway", "dist_waterway_m", "near_water_area", "dist_water_area_m", "dist_wetland_m", "osm_bridge", "osm_ford"],
        "hydrology_related",
    )
    slippery = token_metrics(
        ib1e,
        ib1c,
        SLIPPERY_SURFACE_TOKENS,
        total_m,
        ["osm_surface", "surface_class", "surface_slip_risk_score", "conditional_risk_domains"],
        "slippery_surface",
    )
    exposure = token_metrics(
        ib1e,
        ib1c,
        EXPOSURE_TOKENS,
        total_m,
        ["near_cliff", "dist_cliff_m", "dist_scree_m", "dist_bare_rock_m", "near_peak", "dist_peak_m", "exposure_risk_score", "terrain_risk_score", "conditional_risk_domains"],
        "exposure_related",
    )

    weather_score = axis_scores.get("weather_impact_score") or 0.0
    weather_driver_steps = steps["steps_length_ratio"] >= HIGH_STEPS_RATIO and weather_score >= LOW_WEATHER_SCORE_THRESHOLD
    weather_driver_slope = slope["steep_slope_ratio"] >= HIGH_STEPS_RATIO and weather_score >= LOW_WEATHER_SCORE_THRESHOLD
    weather_driver_hydrology = hydrology["hydrology_related_length_ratio"] >= HIGH_HYDROLOGY_RATIO
    weather_driver_slippery = slippery["slippery_surface_length_ratio"] >= HIGH_SLIPPERY_SURFACE_RATIO
    weather_driver_exposure = exposure["exposure_related_length_ratio"] >= HIGH_EXPOSURE_RATIO and weather_score >= LOW_WEATHER_SCORE_THRESHOLD
    underestimate = (
        (hydrology["hydrology_related_length_ratio"] >= HIGH_HYDROLOGY_RATIO or slippery["slippery_surface_length_ratio"] >= HIGH_SLIPPERY_SURFACE_RATIO)
        and weather_score < LOW_WEATHER_SCORE_THRESHOLD
    )
    overestimate = (
        weather_score >= LOW_WEATHER_SCORE_THRESHOLD
        and not any([weather_driver_steps, weather_driver_slope, weather_driver_hydrology, weather_driver_slippery, weather_driver_exposure])
    )

    flags = {
        "weather_driver_steps": bool(weather_driver_steps),
        "weather_driver_slope": bool(weather_driver_slope),
        "weather_driver_hydrology": bool(weather_driver_hydrology),
        "weather_driver_slippery_surface": bool(weather_driver_slippery),
        "weather_driver_exposure": bool(weather_driver_exposure),
        "weather_score_possible_underestimate": bool(underestimate),
        "weather_score_possible_overestimate": bool(overestimate),
    }

    row = {
        "case_id": case_id,
        "status": status,
        **axis_scores,
        "total_route_distance_m": total_m,
        **steps,
        **slope,
        "hydrology_related_rows_n": hydrology["hydrology_related_rows_n"],
        "hydrology_related_length_m": hydrology["hydrology_related_length_m"],
        "hydrology_related_length_ratio": hydrology["hydrology_related_length_ratio"],
        "slippery_surface_rows_n": slippery["slippery_surface_rows_n"],
        "slippery_surface_length_m": slippery["slippery_surface_length_m"],
        "slippery_surface_length_ratio": slippery["slippery_surface_length_ratio"],
        "exposure_related_rows_n": exposure["exposure_related_rows_n"],
        "exposure_related_length_m": exposure["exposure_related_length_m"],
        "exposure_related_length_ratio": exposure["exposure_related_length_ratio"],
        **flags,
        "note": note,
    }

    summary = {
        "case_id": case_id,
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "weather_impact_score": weather_score,
        "input_roots": {key: str(path) for key, path in INPUT_ROOTS.items()},
        "source_files": {
            **{key: str(path) for key, path in paths.items()},
            "route_metric_summary_csv": str(route_metric_fp),
        },
        "steps_metrics": steps,
        "slope_metrics": slope,
        "hydrology_metrics": hydrology,
        "slippery_surface_metrics": slippery,
        "exposure_metrics": exposure,
        "diagnostic_flags": flags,
        "thresholds": {
            "STEEP_SLOPE_PCT": STEEP_SLOPE_PCT,
            "VERY_STEEP_SLOPE_PCT": VERY_STEEP_SLOPE_PCT,
            "HIGH_STEPS_RATIO": HIGH_STEPS_RATIO,
            "HIGH_HYDROLOGY_RATIO": HIGH_HYDROLOGY_RATIO,
            "HIGH_SLIPPERY_SURFACE_RATIO": HIGH_SLIPPERY_SURFACE_RATIO,
            "HIGH_EXPOSURE_RATIO": HIGH_EXPOSURE_RATIO,
            "LOW_WEATHER_SCORE_THRESHOLD": LOW_WEATHER_SCORE_THRESHOLD,
        },
        "note": note,
        "runtime_llm_allowed": False,
    }
    return row, summary


def write_case_outputs(case_id: str, row: dict[str, Any], summary: dict[str, Any]) -> None:
    out_dir = OUT_ROOT / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([row]).to_csv(
        out_dir / f"{case_id}_weather_sensitivity_diagnostic_v1_0b.csv",
        index=False,
        encoding="utf-8-sig",
    )
    (out_dir / f"{case_id}_weather_sensitivity_summary_v1_0b.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_batch_summary(rows: list[dict[str, Any]]) -> None:
    batch_dir = OUT_ROOT / "_batch_summary"
    batch_dir.mkdir(parents=True, exist_ok=True)
    cols = [
        "case_id",
        "status",
        "weather_impact_score",
        "total_route_distance_m",
        "total_steps_length_m",
        "steps_length_ratio",
        "steep_slope_ratio",
        "very_steep_slope_ratio",
        "hydrology_related_length_ratio",
        "slippery_surface_length_ratio",
        "exposure_related_length_ratio",
        "weather_driver_steps",
        "weather_driver_slope",
        "weather_driver_hydrology",
        "weather_driver_slippery_surface",
        "weather_driver_exposure",
        "weather_score_possible_underestimate",
        "weather_score_possible_overestimate",
        "note",
    ]
    pd.DataFrame(rows)[cols].to_csv(
        batch_dir / "thci_weather_sensitivity_diagnostic_v1_0b_case_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )



# THCI_WEATHER_DIAG_NONE_SAFE_PRINT_PATCH_V1
def _fmt_weather_diag_value_v1b(v, digits: int = 4) -> str:
    try:
        if v is None or pd.isna(v):
            return "NA"
    except Exception:
        if v is None:
            return "NA"
    try:
        return f"{float(v):.{digits}f}"
    except Exception:
        return str(v)


def main() -> int:
    args = parse_args()
    rows: list[dict[str, Any]] = []
    for case_id in resolve_cases(args):
        row, summary = diagnose_case(case_id)
        write_case_outputs(case_id, row, summary)
        rows.append(row)
        print(
            f"{case_id}: {row['status']} "
            f"weather={_fmt_weather_diag_value_v1b(row.get('weather_impact_score'))} "
            f"steps={row['steps_length_ratio']:.4f} "
            f"steep={row['steep_slope_ratio']:.4f} "
            f"hydro={row['hydrology_related_length_ratio']:.4f} "
            f"slippery={row['slippery_surface_length_ratio']:.4f} "
            f"exposure={row['exposure_related_length_ratio']:.4f} "
            f"underestimate={row['weather_score_possible_underestimate']}"
        )
    write_batch_summary(rows)
    print("batch summary:", OUT_ROOT / "_batch_summary" / "thci_weather_sensitivity_diagnostic_v1_0b_case_summary.csv")
    return 1 if any(row["status"] != "PASS" for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
