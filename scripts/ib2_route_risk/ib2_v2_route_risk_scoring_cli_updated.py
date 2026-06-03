# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RISK_MODEL_VERSION = "terrain_dominant_from_ib1e_v0.4_cli"
PIPELINE_STAGE = "ib2_v2_route_risk_scoring_cli_updated"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compute ib2 v2 route risk scores from ib1e contour-window terrain outputs."
        )
    )
    parser.add_argument("--case-id", required=True, help="Route case id.")
    parser.add_argument(
        "--case-name",
        default=None,
        help="Human-readable route name. Defaults to --case-id.",
    )
    parser.add_argument(
        "--input-csv",
        default=None,
        help=(
            "Input ib1e enriched CSV. Defaults to "
            "outputs/ib1e_route_profile_contour_window_terrain/<case-id>/"
            "<case-id>_route_profile_contour_window_terrain_enriched.csv"
        ),
    )
    parser.add_argument(
        "--input-geojson",
        default=None,
        help=(
            "Input ib1e enriched GeoJSON. Defaults to "
            "outputs/ib1e_route_profile_contour_window_terrain/<case-id>/"
            "<case-id>_route_profile_contour_window_terrain_enriched.geojson"
        ),
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Output directory. Defaults to outputs/ib2_v2_route_risk/<case-id>.",
    )
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def default_input_csv(case_id: str) -> Path:
    return (
        PROJECT_ROOT
        / "outputs"
        / "ib1e_route_profile_contour_window_terrain"
        / case_id
        / f"{case_id}_route_profile_contour_window_terrain_enriched.csv"
    )


def default_input_geojson(case_id: str) -> Path:
    return (
        PROJECT_ROOT
        / "outputs"
        / "ib1e_route_profile_contour_window_terrain"
        / case_id
        / f"{case_id}_route_profile_contour_window_terrain_enriched.geojson"
    )


def default_out_dir(case_id: str) -> Path:
    return PROJECT_ROOT / "outputs" / "ib2_v2_route_risk" / case_id


def norm_text(v) -> str:
    if pd.isna(v):
        return ""
    text = str(v).strip().lower()
    return "" if text in {"", "nan", "none", "<na>", "null"} else text


def split_flags(value) -> list[str]:
    text = norm_text(value)
    if not text or text == "normal":
        return []
    return [x.strip() for x in text.split("|") if x.strip()]


def band_from_01(score) -> str:
    if pd.isna(score):
        return "unknown"
    score = float(score)
    if score < 0.20:
        return "low"
    if score < 0.40:
        return "moderate"
    if score < 0.65:
        return "high"
    return "very_high"


def numeric_series(df: pd.DataFrame, col: str, default=0.0) -> pd.Series:
    if col in df.columns:
        source = df[col]
    else:
        source = pd.Series(default, index=df.index)
    return pd.to_numeric(source, errors="coerce").fillna(default)


def choose_slope_col(df: pd.DataFrame) -> str | None:
    for col in [
        "slope_band_window",
        "slope_band_window_nlsc",
        "terrain_slope_band_window",
        "slope_band",
    ]:
        if col in df.columns:
            return col
    return None


def build_reason(row: pd.Series) -> str:
    reasons: list[str] = []
    for col in [
        "technical_flags",
        "hazard_flags",
        "hydrology_flags",
        "weather_sensitive_flags",
        "conditional_factor_flags",
    ]:
        reasons.extend(split_flags(row.get(col, "")))

    for score_col, label in [
        ("terrain_window_risk_score", "terrain_window"),
        ("hydro_terrain_amplifier_score", "hydro_terrain"),
        ("osm_semantic_risk_score", "osm_semantic"),
    ]:
        if float(row.get(score_col, 0) or 0) >= 0.40:
            reasons.append(label)

    if not bool(row.get("route_data_ok", True)):
        reasons.append("route_data_quality")

    seen: list[str] = []
    for item in reasons:
        if item and item not in seen:
            seen.append(item)
    return "|".join(seen) if seen else "normal"


def score_route_risk(df: pd.DataFrame, case_id: str, case_name: str, input_csv: Path) -> pd.DataFrame:
    if df.empty:
        raise ValueError(f"Empty input: {input_csv}")
    if "dist_m" not in df.columns:
        raise KeyError("input CSV must contain dist_m")

    df = df.sort_values("dist_m").reset_index(drop=True).copy()

    required_scores = [
        "osm_semantic_risk_score",
        "terrain_window_risk_score",
        "hydro_terrain_amplifier_score",
        "osm_terrain_combined_risk_score",
    ]
    for col in required_scores:
        if col not in df.columns:
            raise KeyError(f"input CSV missing score column: {col}")
        df[col] = numeric_series(df, col).clip(0, 1)

    if "osm_terrain_combined_risk_band" in df.columns:
        df["risk_band"] = df["osm_terrain_combined_risk_band"].map(norm_text)
    else:
        df["risk_band"] = df["osm_terrain_combined_risk_score"].apply(band_from_01)
    df["risk_band"] = df["risk_band"].where(df["risk_band"].ne(""), "unknown")

    df["risk_score_raw"] = numeric_series(
        df,
        "osm_terrain_combined_risk_score_raw",
        default=np.nan,
    )
    df["risk_score_raw"] = df["risk_score_raw"].fillna(df["osm_terrain_combined_risk_score"])
    df["risk_score"] = df["osm_terrain_combined_risk_score"]
    df["risk_score_smooth"] = df["risk_score"].rolling(9, center=True, min_periods=2).mean()

    df["terrain_score"] = numeric_series(df, "terrain_window_risk_score").clip(0, 1)
    if "route_effort_risk_score" in df.columns:
        df["effort_score"] = numeric_series(df, "route_effort_risk_score").clip(0, 1)
    else:
        df["effort_score"] = df["terrain_score"]

    if "exposure_risk_score" in df.columns:
        df["exposure_score"] = numeric_series(df, "exposure_risk_score").clip(0, 1)
    else:
        df["exposure_score"] = (
            0.65 * numeric_series(df, "hydro_terrain_amplifier_score")
            + 0.35 * numeric_series(df, "terrain_window_risk_score")
        ).clip(0, 1)

    slope_col = choose_slope_col(df)
    df["effort_slope_band"] = df[slope_col].map(norm_text) if slope_col else "unknown"
    df["terrain_exposure_band"] = df["effort_slope_band"]
    df["slope_final_band"] = df["effort_slope_band"]

    if "dist_to_contour_window_mid_m" in df.columns:
        align_diff = numeric_series(df, "dist_to_contour_window_mid_m", default=np.nan).abs()
        df["dist_alignment_diff_m"] = align_diff
        df["alignment_ok"] = align_diff <= 10.0
    else:
        df["dist_alignment_diff_m"] = 0.0
        df["alignment_ok"] = True

    if "contour_window_match_status" in df.columns:
        df["within_validation_range"] = df["contour_window_match_status"].astype(str).eq("matched")
    else:
        df["within_validation_range"] = True

    df["route_data_ok"] = df["alignment_ok"].astype(bool) & df["within_validation_range"].astype(bool)
    df["gpx_quality_flag"] = np.where(df["route_data_ok"], "ok", "mismatch")
    df["risk_confidence"] = np.where(df["route_data_ok"], "normal", "low_data_quality")
    df["data_quality_reason"] = np.where(df["route_data_ok"], "normal", "contour_window_alignment")
    df["risk_reason"] = df.apply(build_reason, axis=1)

    df["case_id"] = case_id
    df["case_name"] = case_name
    df["risk_model_version"] = RISK_MODEL_VERSION
    df["risk_scored_at"] = datetime.now(timezone.utc).isoformat()
    df["pipeline_stage"] = PIPELINE_STAGE
    df["ib2_input_csv"] = str(input_csv)

    required_output_cols = [
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
    ]
    missing_output = [col for col in required_output_cols if col not in df.columns]
    if missing_output:
        raise KeyError(f"scored output missing required columns: {missing_output}")

    return df


def write_geojson(scored: pd.DataFrame, input_geojson: Path, out_geojson: Path) -> None:
    if not input_geojson.exists():
        raise FileNotFoundError(f"Missing input GeoJSON: {input_geojson}")

    gdf = gpd.read_file(input_geojson)
    if len(gdf) != len(scored):
        gdf = gdf.sort_values("dist_m").reset_index(drop=True) if "dist_m" in gdf.columns else gdf.reset_index(drop=True)
        if len(gdf) != len(scored):
            raise ValueError(
                f"CSV/GeoJSON row count mismatch: CSV={len(scored)} GeoJSON={len(gdf)}"
            )

    geometry = gdf.geometry
    crs = gdf.crs
    out_gdf = gpd.GeoDataFrame(scored.copy(), geometry=geometry, crs=crs)
    out_gdf.to_file(out_geojson, driver="GeoJSON")


def make_summary(scored: pd.DataFrame, case_id: str, case_name: str, input_csv: Path, input_geojson: Path) -> pd.DataFrame:
    band_counts = scored["risk_band"].value_counts(dropna=False).to_dict()
    summary = {
        "case_id": case_id,
        "case_name": case_name,
        "rows": len(scored),
        "dist_min_m": float(scored["dist_m"].min()),
        "dist_max_m": float(scored["dist_m"].max()),
        "risk_score_min": float(scored["risk_score"].min()),
        "risk_score_mean": float(scored["risk_score"].mean()),
        "risk_score_max": float(scored["risk_score"].max()),
        "risk_score_smooth_min": float(scored["risk_score_smooth"].min()),
        "risk_score_smooth_mean": float(scored["risk_score_smooth"].mean()),
        "risk_score_smooth_max": float(scored["risk_score_smooth"].max()),
        "route_data_ok_count": int(scored["route_data_ok"].sum()),
        "route_data_mismatch_count": int((~scored["route_data_ok"]).sum()),
        "risk_model_version": RISK_MODEL_VERSION,
        "pipeline_stage": PIPELINE_STAGE,
        "input_csv": str(input_csv),
        "input_geojson": str(input_geojson),
        "scored_at": scored["risk_scored_at"].iloc[0],
    }
    for band in ["low", "moderate", "high", "very_high", "unknown"]:
        summary[f"risk_band_{band}_count"] = int(band_counts.get(band, 0))
    return pd.DataFrame([summary])


def main() -> None:
    args = parse_args()
    case_id = args.case_id
    case_name = args.case_name or case_id
    input_csv = resolve_path(args.input_csv) if args.input_csv else default_input_csv(case_id)
    input_geojson = (
        resolve_path(args.input_geojson) if args.input_geojson else default_input_geojson(case_id)
    )
    out_dir = resolve_path(args.out_dir) if args.out_dir else default_out_dir(case_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    out_csv = out_dir / f"{case_id}_route_risk_v2.csv"
    out_geojson = out_dir / f"{case_id}_route_risk_v2.geojson"
    out_summary = out_dir / f"{case_id}_route_risk_v2_summary.csv"

    df = pd.read_csv(input_csv, low_memory=False, encoding="utf-8-sig")
    scored = score_route_risk(df, case_id, case_name, input_csv)
    scored.to_csv(out_csv, index=False, encoding="utf-8-sig")
    write_geojson(scored, input_geojson, out_geojson)
    summary = make_summary(scored, case_id, case_name, input_csv, input_geojson)
    summary.to_csv(out_summary, index=False, encoding="utf-8-sig")

    print("case:", case_id)
    print("case_name:", case_name)
    print("rows:", len(scored))
    print("CSV:", out_csv)
    print("GeoJSON:", out_geojson)
    print("Summary:", out_summary)
    print("\n=== risk_band ===")
    print(scored["risk_band"].value_counts(dropna=False))
    print("\n=== score min/mean/max ===")
    print(scored["risk_score"].min(), scored["risk_score"].mean(), scored["risk_score"].max())
    print("\n=== route_data_ok ===")
    print(scored["route_data_ok"].value_counts(dropna=False))


if __name__ == "__main__":
    main()
