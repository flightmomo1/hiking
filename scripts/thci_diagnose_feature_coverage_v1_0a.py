# -*- coding: utf-8 -*-
"""Diagnose THCI v1.0 proxy feature coverage without changing scores."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError


PROJECT_ROOT = Path(r"D:\mountain_work\115_osm")

CASES = [
    "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b",
    "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b",
    "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b",
    "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b",
]

INPUT_ROOTS = {
    "ib1a": PROJECT_ROOT / "outputs" / "ib1_route_profile_v1_3b_contract_qa",
    "ib1c": PROJECT_ROOT
    / "outputs"
    / "ib1c_route_profile_semantics_v1_3b_contract_qa",
    "ib1e": PROJECT_ROOT
    / "outputs"
    / "ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa",
    "ib0d": PROJECT_ROOT
    / "outputs"
    / "ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa",
    "thci": PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_0",
}

OUT_ROOT = PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_0a_diagnostics"


def read_csv_if_exists(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        return pd.read_csv(path, low_memory=False)
    except EmptyDataError:
        return pd.DataFrame()


def numeric_ratio(series: pd.Series, predicate) -> float | None:
    vals = pd.to_numeric(series, errors="coerce").dropna()
    if vals.empty:
        return None
    return float(predicate(vals).mean())


def text_ratio(series: pd.Series, values: set[str]) -> float | None:
    if series is None:
        return None
    text = series.fillna("").astype(str).str.lower()
    if text.empty:
        return None
    return float(text.isin(values).mean())


def flag_ratio(series: pd.Series, tokens: set[str]) -> float | None:
    if series is None:
        return None
    text = series.fillna("").astype(str).str.lower()
    if text.empty:
        return None

    def has_token(value: str) -> bool:
        parts = {p.strip() for p in value.replace(";", "|").split("|") if p.strip()}
        return bool(parts.intersection(tokens))

    return float(text.map(has_token).mean())


def numeric_high_ratio(series: pd.Series, threshold: float = 0.5) -> float | None:
    vals = pd.to_numeric(series, errors="coerce").dropna()
    if vals.empty:
        return None
    return float((vals >= threshold).mean())


def scalar_from_first(df: pd.DataFrame | None, col: str) -> Any:
    if df is None or df.empty or col not in df.columns:
        return None
    value = df[col].iloc[0]
    if pd.isna(value):
        return None
    return value


def max_numeric(df: pd.DataFrame | None, col: str) -> float | None:
    if df is None or col not in df.columns:
        return None
    vals = pd.to_numeric(df[col], errors="coerce").dropna()
    if vals.empty:
        return None
    return float(vals.max())


def exists_and_nonempty(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_file():
        return path.stat().st_size > 0
    return True


def case_paths(case_id: str) -> dict[str, Path]:
    return {
        "ib1a_csv": INPUT_ROOTS["ib1a"] / case_id / f"{case_id}_route_profile.csv",
        "ib1c_csv": INPUT_ROOTS["ib1c"] / case_id / f"{case_id}_route_profile_semantic_enriched.csv",
        "ib1e_csv": INPUT_ROOTS["ib1e"]
        / case_id
        / f"{case_id}_route_profile_contour_window_terrain_enriched.csv",
        "trim_summary_csv": INPUT_ROOTS["ib0d"] / case_id / "trim_summary.csv",
        "self_near_zones_csv": INPUT_ROOTS["ib0d"] / case_id / "self_near_zones.csv",
        "thci_score_csv": INPUT_ROOTS["thci"] / case_id / f"{case_id}_thci_axis_scores_v1_0.csv",
    }


def diagnose_case(case_id: str) -> dict[str, Any]:
    paths = case_paths(case_id)
    ib1a = read_csv_if_exists(paths["ib1a_csv"])
    ib1c = read_csv_if_exists(paths["ib1c_csv"])
    ib1e = read_csv_if_exists(paths["ib1e_csv"])
    trim = read_csv_if_exists(paths["trim_summary_csv"])
    self_near = read_csv_if_exists(paths["self_near_zones_csv"])
    thci = read_csv_if_exists(paths["thci_score_csv"])

    row: dict[str, Any] = {
        "case_id": case_id,
        "ib1a_exists": ib1a is not None,
        "ib1c_exists": ib1c is not None,
        "ib1e_exists": ib1e is not None,
        "ib0d_trim_summary_exists": trim is not None,
        "ib0d_self_near_zones_exists": self_near is not None,
        "thci_axis_score_exists": thci is not None,
    }

    slope_source = ib1a if ib1a is not None and "slope_pct" in ib1a.columns else ib1e
    row["slope_pct_ge_15_ratio"] = (
        numeric_ratio(slope_source["slope_pct"], lambda v: v.abs() >= 15.0)
        if slope_source is not None and "slope_pct" in slope_source.columns
        else None
    )
    row["slope_pct_ge_20_ratio"] = (
        numeric_ratio(slope_source["slope_pct"], lambda v: v.abs() >= 20.0)
        if slope_source is not None and "slope_pct" in slope_source.columns
        else None
    )

    if ib1e is not None and "osm_highway" in ib1e.columns:
        row["highway_steps_ratio"] = text_ratio(ib1e["osm_highway"], {"steps"})
    elif ib1c is not None and "osm_highway" in ib1c.columns:
        row["highway_steps_ratio"] = text_ratio(ib1c["osm_highway"], {"steps"})
    else:
        row["highway_steps_ratio"] = None

    if ib1e is not None and "osm_terrain_combined_risk_band" in ib1e.columns:
        band = ib1e["osm_terrain_combined_risk_band"].fillna("").astype(str).str.lower()
        row["ib1e_high_or_very_high_risk_band_ratio"] = float(band.isin({"high", "very_high"}).mean())
        row["ib1e_high_risk_band_ratio"] = float(band.eq("high").mean())
        row["ib1e_very_high_risk_band_ratio"] = float(band.eq("very_high").mean())
    else:
        row["ib1e_high_or_very_high_risk_band_ratio"] = None
        row["ib1e_high_risk_band_ratio"] = None
        row["ib1e_very_high_risk_band_ratio"] = None

    if ib1e is not None and "slope_band_window_nlsc" in ib1e.columns:
        slope_band = ib1e["slope_band_window_nlsc"].fillna("").astype(str).str.lower()
        row["slope_band_high_or_very_steep_ratio"] = float(
            slope_band.isin({"high", "very_steep", "steep", "very steep"}).mean()
        )
    elif ib1a is not None and "slope_band" in ib1a.columns:
        slope_band = ib1a["slope_band"].fillna("").astype(str).str.lower()
        row["slope_band_high_or_very_steep_ratio"] = float(
            slope_band.isin({"high", "very_steep", "steep", "very steep"}).mean()
        )
    else:
        row["slope_band_high_or_very_steep_ratio"] = None

    row["terrain_window_risk_high_ratio"] = (
        numeric_high_ratio(ib1e["terrain_window_risk_score"], 0.5)
        if ib1e is not None and "terrain_window_risk_score" in ib1e.columns
        else None
    )
    row["hydro_terrain_amplifier_high_ratio"] = (
        numeric_high_ratio(ib1e["hydro_terrain_amplifier_score"], 0.5)
        if ib1e is not None and "hydro_terrain_amplifier_score" in ib1e.columns
        else None
    )
    row["osm_terrain_combined_risk_high_ratio"] = (
        numeric_high_ratio(ib1e["osm_terrain_combined_risk_score"], 0.5)
        if ib1e is not None and "osm_terrain_combined_risk_score" in ib1e.columns
        else None
    )

    trim_mode = scalar_from_first(trim, "trim_mode")
    row["ib0d_trim_mode"] = trim_mode
    row["same_entry_keep_full"] = (
        bool(isinstance(trim_mode, str) and "same_entry_keep_full" in trim_mode)
        if trim_mode is not None
        else None
    )
    row["self_near_zones_exists"] = exists_and_nonempty(paths["self_near_zones_csv"])
    if self_near is not None and "classification" in self_near.columns:
        classes = self_near["classification"].fillna("").astype(str).str.lower()
        row["summit_self_near_zone_exists"] = bool(classes.str.contains("summit", regex=False).any())
    else:
        row["summit_self_near_zone_exists"] = False if self_near is not None else None
    row["route_gap_max_m"] = max_numeric(self_near, "route_gap_max_m")
    row["self_near_pair_count"] = scalar_from_first(trim, "self_near_pair_count")
    row["unexpected_self_near_pair_count"] = scalar_from_first(trim, "unexpected_self_near_pair_count")

    surface_source = ib1e if ib1e is not None and "osm_surface" in ib1e.columns else ib1c
    row["surface_mud_ground_dirt_earth_unpaved_ratio"] = (
        text_ratio(surface_source["osm_surface"], {"mud", "ground", "dirt", "earth", "unpaved"})
        if surface_source is not None and "osm_surface" in surface_source.columns
        else None
    )
    if ib1e is not None and "hydrology_flags" in ib1e.columns:
        row["hydrology_flags_ratio"] = flag_ratio(ib1e["hydrology_flags"], {"waterway", "wetland", "water_area"})
    elif ib1c is not None and "hydrology_flags" in ib1c.columns:
        row["hydrology_flags_ratio"] = flag_ratio(ib1c["hydrology_flags"], {"waterway", "wetland", "water_area"})
    else:
        row["hydrology_flags_ratio"] = None
    row["near_waterway_ratio"] = (
        numeric_ratio(ib1e["near_waterway"], lambda v: v > 0)
        if ib1e is not None and "near_waterway" in ib1e.columns
        else None
    )

    route_gap = row.get("route_gap_max_m")
    terrain_high = row.get("terrain_window_risk_high_ratio") or 0.0
    self_near_pairs = pd.to_numeric(pd.Series([row.get("self_near_pair_count")]), errors="coerce").iloc[0]
    row["gps_blockage_or_drift_candidate_proxy"] = bool(
        (pd.notna(route_gap) and float(route_gap) >= 1000.0)
        or terrain_high >= 0.20
        or (pd.notna(self_near_pairs) and float(self_near_pairs) >= 1000.0)
    )
    row["road_access_distance_missing"] = True

    if thci is not None and not thci.empty:
        for col in [
            "physical_difficulty_score",
            "technical_difficulty_score",
            "baseline_hazard_score",
            "navigation_risk_score",
            "support_difficulty_score",
            "weather_impact_score",
        ]:
            row[f"current_{col}"] = thci[col].iloc[0] if col in thci.columns else None

    return row


def write_case_output(case_id: str, row: dict[str, Any]) -> None:
    out_dir = OUT_ROOT / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_fp = out_dir / f"{case_id}_thci_feature_coverage_diagnostic_v1_0a.csv"
    pd.DataFrame([row]).to_csv(out_fp, index=False, encoding="utf-8-sig")


def write_batch_summary(rows: list[dict[str, Any]]) -> None:
    out_dir = OUT_ROOT / "_batch_summary"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_fp = out_dir / "thci_feature_coverage_diagnostic_v1_0a_case_summary.csv"
    pd.DataFrame(rows).to_csv(out_fp, index=False, encoding="utf-8-sig")


# THCI_DIAG_V10A_CASE_ID_CLI_ROOT_D_PATCH_V1
def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Diagnose THCI v1.0a feature coverage. Default keeps legacy fixed-case batch; --case-id runs one case."
    )
    parser.add_argument(
        "--case-id",
        default=None,
        help="Run only one case_id. If omitted, run legacy CASES batch.",
    )
    args = parser.parse_args()

    if args.case_id:
        case_ids = [args.case_id]
    else:
        case_ids = list(CASES)

    rows = []

    for case_id in case_ids:
        row = diagnose_case(case_id)
        write_case_output(case_id, row)
        rows.append(row)
        print(
            f"{case_id}: "
            f"slope>=20={row.get('slope_pct_ge_20_ratio')}; "
            f"steps={row.get('highway_steps_ratio')}; "
            f"risk_high={row.get('ib1e_high_or_very_high_risk_band_ratio')}; "
            f"self_near_gap={row.get('route_gap_max_m')}"
        )

    if rows:
        write_batch_summary(rows)
        print("batch summary:", OUT_ROOT / "_batch_summary" / "thci_feature_coverage_diagnostic_v1_0a_case_summary.csv")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
