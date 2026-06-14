from __future__ import annotations

import argparse
import html
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

try:
    import pandas as pd
except ModuleNotFoundError:
    venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
        os.execv(str(venv_python), [str(venv_python), __file__, *sys.argv[1:]])
    raise


SCHEMA_VERSION = "ib3a_rc_full26_performance_summary_v1"
ROUTE_FOLDER = "qixing_lengshuikeng"
EXPECTED_ACTIVITY_COUNT = 26

PRIMARY_ROOT = Path(
    "outputs/ib3a_rc_backend_activity_enriched_v1l_qixing_lengshuikeng_full26"
)
LOCAL_COPY_ROOT = Path(
    "outputs/ib3a_rc_backend_activity_enriched_v1l_qixing_lengshuikeng_full26 - 複製"
)
SUMMARY_RELATIVE_PATH = Path(
    "_batch_summary/qixing_lengshuikeng_v1l_backend_activity_enriched_summary.csv"
)
DEFAULT_OUT_ROOT = Path("outputs/ib3a_rc_full26_performance_summary_v1")

SUMMARY_FIELDS = [
    "schema_version",
    "route_folder",
    "activity_id_short",
    "activity_id_full",
    "input_csv",
    "status",
    "rows",
    "elapsed_min_sec",
    "elapsed_max_sec",
    "duration_sec",
    "duration_min",
    "dt_valid_count",
    "backend_use_analytics_ready_n",
    "backend_use_analytics_ready_ratio",
    "calibration_review_required_n",
    "calibration_review_required_ratio",
    "movement_review_required_n",
    "movement_review_required_ratio",
    "speed_available",
    "calibrated_speed_mps_median",
    "calibrated_speed_mps_p25",
    "calibrated_speed_mps_p75",
    "calibrated_speed_mps_max",
    "moving_sec",
    "stopped_sec",
    "movement_state_distribution",
    "heart_rate_available",
    "heart_rate_bpm_median",
    "heart_rate_bpm_p75",
    "heart_rate_bpm_p90",
    "heart_rate_bpm_max",
    "route_dist_min_m",
    "route_dist_max_m",
    "route_dist_covered_m",
    "route_progress_min",
    "route_progress_max",
    "calibrated_elevation_min_m",
    "calibrated_elevation_max_m",
    "calibrated_cumulative_gain_m",
    "calibrated_cumulative_loss_m",
    "terrain_slope_pct_median",
    "terrain_slope_pct_p75",
    "terrain_slope_pct_p90",
    "terrain_risk_band_distribution",
    "route_phase_distribution",
    "radar_physical_fitness_hint_nonzero_n",
    "radar_technical_difficulty_hint_nonzero_n",
    "radar_base_hazard_hint_nonzero_n",
    "radar_navigation_hint_nonzero_n",
    "radar_support_insufficiency_hint_nonzero_n",
    "radar_weather_sensitivity_hint_nonzero_n",
    "activity_performance_quality_flag",
    "authorization_note",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build activity-level performance summaries from IB3A-RC full26 point data."
    )
    parser.add_argument("--primary-root", type=Path, default=PRIMARY_ROOT)
    parser.add_argument("--local-copy-root", type=Path, default=LOCAL_COPY_ROOT)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    return parser.parse_args()


def activity_csv_path(root: Path, activity_id: str) -> Path:
    return (
        root
        / ROUTE_FOLDER
        / activity_id
        / f"{ROUTE_FOLDER}_{activity_id}_backend_activity_enriched_v1l.csv"
    )


def inspect_root(root: Path) -> tuple[bool, pd.DataFrame | None, list[str]]:
    summary_path = root / SUMMARY_RELATIVE_PATH
    if not summary_path.exists():
        return False, None, []
    summary = pd.read_csv(summary_path, dtype={"activity_id": str})
    missing = [
        activity_id
        for activity_id in summary["activity_id"].astype(str)
        if not activity_csv_path(root, activity_id).exists()
    ]
    complete = len(summary) == EXPECTED_ACTIVITY_COUNT and not missing
    return complete, summary, missing


def resolve_input_root(
    primary_root: Path, local_copy_root: Path
) -> tuple[Path, str, pd.DataFrame, list[str]]:
    primary_complete, primary_summary, primary_missing = inspect_root(primary_root)
    if primary_complete and primary_summary is not None:
        return primary_root, "PRIMARY_ROOT_USED", primary_summary, primary_missing

    copy_complete, copy_summary, copy_missing = inspect_root(local_copy_root)
    if copy_complete and copy_summary is not None:
        return (
            local_copy_root,
            "LOCAL_COPY_FALLBACK_USED",
            copy_summary,
            primary_missing,
        )

    details = (
        f"Primary complete={primary_complete}, missing={primary_missing}; "
        f"local copy complete={copy_complete}, missing={copy_missing}"
    )
    raise FileNotFoundError(f"No complete full26 input root. {details}")


def numeric(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[column], errors="coerce")


def truthy(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(False, index=df.index)
    return (
        df[column]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        .isin({"true", "1", "yes", "y"})
    )


def round_or_blank(value: Any, digits: int = 4) -> float | str:
    if value is None or pd.isna(value):
        return ""
    return round(float(value), digits)


def quantile_or_blank(series: pd.Series, quantile: float) -> float | str:
    values = series.dropna()
    return round_or_blank(values.quantile(quantile)) if len(values) else ""


def min_or_blank(series: pd.Series) -> float | str:
    values = series.dropna()
    return round_or_blank(values.min()) if len(values) else ""


def max_or_blank(series: pd.Series) -> float | str:
    values = series.dropna()
    return round_or_blank(values.max()) if len(values) else ""


def ratio(numerator: int, denominator: int) -> float | str:
    return round(numerator / denominator, 6) if denominator > 0 else ""


def distribution(df: pd.DataFrame, column: str) -> str:
    if column not in df.columns:
        return ""
    values = df[column].fillna("").astype(str).str.strip()
    values = values[values.ne("")]
    counts = Counter(values)
    return "|".join(f"{key}:{counts[key]}" for key in sorted(counts))


def nonzero_count(df: pd.DataFrame, column: str) -> int:
    values = numeric(df, column)
    return int((values.fillna(0.0).abs() > 0.0).sum())


def movement_seconds(df: pd.DataFrame) -> tuple[float | str, float | str]:
    if "movement_state" not in df.columns or "dt_sec" not in df.columns:
        return "", ""
    dt = numeric(df, "dt_sec")
    valid = dt.notna() & (dt >= 0)
    state = df["movement_state"].fillna("").astype(str).str.strip().str.upper()
    moving = state.isin({"MOVING", "SLOW_MOVING"})
    stopped = state.eq("STOPPED")
    return (
        round_or_blank(dt[valid & moving].sum()),
        round_or_blank(dt[valid & stopped].sum()),
    )


def quality_flag(
    status: str,
    row_count_matches: bool,
    movement_distribution: str,
    route_distance_available: bool,
) -> str:
    flags: list[str] = []
    if status != "PASS":
        flags.append("SOURCE_STATUS_NOT_PASS")
    if not row_count_matches:
        flags.append("ROW_COUNT_MISMATCH")
    if not movement_distribution:
        flags.append("MOVEMENT_STATE_UNAVAILABLE")
    if not route_distance_available:
        flags.append("ROUTE_DISTANCE_UNAVAILABLE")
    return "|".join(flags) if flags else "PASS_ACTIVITY_PERFORMANCE_EVIDENCE"


def summarize_activity(
    input_root: Path,
    summary_row: dict[str, Any],
) -> dict[str, Any]:
    activity_id = str(summary_row["activity_id"])
    input_csv = activity_csv_path(input_root, activity_id)
    df = pd.read_csv(input_csv, low_memory=False)
    rows = len(df)

    elapsed = numeric(df, "elapsed_sec")
    elapsed_valid = elapsed.dropna()
    elapsed_min = elapsed_valid.min() if len(elapsed_valid) else None
    elapsed_max = elapsed_valid.max() if len(elapsed_valid) else None
    duration_sec = (
        float(elapsed_max - elapsed_min)
        if elapsed_min is not None and elapsed_max is not None
        else None
    )

    dt = numeric(df, "dt_sec")
    dt_valid_count = int((dt.notna() & (dt > 0)).sum())
    analytics_ready_n = int(
        df.get("backend_use_policy", pd.Series("", index=df.index))
        .fillna("")
        .astype(str)
        .eq("ANALYTICS_READY")
        .sum()
    )
    calibration_review_n = int(truthy(df, "calibration_review_required").sum())
    movement_review_n = int(truthy(df, "movement_review_required").sum())

    speed = numeric(df, "calibrated_speed_mps")
    speed_valid = speed[speed.notna() & (speed >= 0)]
    heart_rate = numeric(df, "heart_rate_bpm")
    heart_rate_valid = heart_rate[heart_rate.notna() & (heart_rate > 0)]
    route_distance = numeric(df, "route_dist_m").dropna()
    route_progress = numeric(df, "route_progress_ratio").dropna()
    elevation = numeric(df, "calibrated_elevation_m").dropna()
    gain = numeric(df, "calibrated_cumulative_gain_m").dropna()
    loss = numeric(df, "calibrated_cumulative_loss_m").dropna()
    terrain_slope = numeric(df, "terrain_slope_pct").dropna().abs()

    moving_sec, stopped_sec = movement_seconds(df)
    movement_dist = distribution(df, "movement_state")
    route_dist_min = route_distance.min() if len(route_distance) else None
    route_dist_max = route_distance.max() if len(route_distance) else None
    route_dist_covered = (
        float(route_dist_max - route_dist_min)
        if route_dist_min is not None and route_dist_max is not None
        else None
    )

    status = str(summary_row.get("status", ""))
    expected_rows = int(summary_row.get("rows", rows))
    return {
        "schema_version": SCHEMA_VERSION,
        "route_folder": ROUTE_FOLDER,
        "activity_id_short": activity_id,
        "activity_id_full": f"{ROUTE_FOLDER}_{activity_id}",
        "input_csv": str(input_csv),
        "status": status,
        "rows": rows,
        "elapsed_min_sec": round_or_blank(elapsed_min),
        "elapsed_max_sec": round_or_blank(elapsed_max),
        "duration_sec": round_or_blank(duration_sec),
        "duration_min": round_or_blank(duration_sec / 60 if duration_sec is not None else None),
        "dt_valid_count": dt_valid_count,
        "backend_use_analytics_ready_n": analytics_ready_n,
        "backend_use_analytics_ready_ratio": ratio(analytics_ready_n, rows),
        "calibration_review_required_n": calibration_review_n,
        "calibration_review_required_ratio": ratio(calibration_review_n, rows),
        "movement_review_required_n": movement_review_n,
        "movement_review_required_ratio": ratio(movement_review_n, rows),
        "speed_available": str(len(speed_valid) > 0),
        "calibrated_speed_mps_median": quantile_or_blank(speed_valid, 0.50),
        "calibrated_speed_mps_p25": quantile_or_blank(speed_valid, 0.25),
        "calibrated_speed_mps_p75": quantile_or_blank(speed_valid, 0.75),
        "calibrated_speed_mps_max": max_or_blank(speed_valid),
        "moving_sec": moving_sec,
        "stopped_sec": stopped_sec,
        "movement_state_distribution": movement_dist,
        "heart_rate_available": str(len(heart_rate_valid) > 0),
        "heart_rate_bpm_median": quantile_or_blank(heart_rate_valid, 0.50),
        "heart_rate_bpm_p75": quantile_or_blank(heart_rate_valid, 0.75),
        "heart_rate_bpm_p90": quantile_or_blank(heart_rate_valid, 0.90),
        "heart_rate_bpm_max": max_or_blank(heart_rate_valid),
        "route_dist_min_m": round_or_blank(route_dist_min),
        "route_dist_max_m": round_or_blank(route_dist_max),
        "route_dist_covered_m": round_or_blank(route_dist_covered),
        "route_progress_min": min_or_blank(route_progress),
        "route_progress_max": max_or_blank(route_progress),
        "calibrated_elevation_min_m": min_or_blank(elevation),
        "calibrated_elevation_max_m": max_or_blank(elevation),
        "calibrated_cumulative_gain_m": max_or_blank(gain),
        "calibrated_cumulative_loss_m": max_or_blank(loss),
        "terrain_slope_pct_median": quantile_or_blank(terrain_slope, 0.50),
        "terrain_slope_pct_p75": quantile_or_blank(terrain_slope, 0.75),
        "terrain_slope_pct_p90": quantile_or_blank(terrain_slope, 0.90),
        "terrain_risk_band_distribution": distribution(df, "terrain_risk_band"),
        "route_phase_distribution": distribution(df, "route_phase"),
        "radar_physical_fitness_hint_nonzero_n": nonzero_count(df, "radar_physical_fitness_hint"),
        "radar_technical_difficulty_hint_nonzero_n": nonzero_count(df, "radar_technical_difficulty_hint"),
        "radar_base_hazard_hint_nonzero_n": nonzero_count(df, "radar_base_hazard_hint"),
        "radar_navigation_hint_nonzero_n": nonzero_count(df, "radar_navigation_hint"),
        "radar_support_insufficiency_hint_nonzero_n": nonzero_count(df, "radar_support_insufficiency_hint"),
        "radar_weather_sensitivity_hint_nonzero_n": nonzero_count(df, "radar_weather_sensitivity_hint"),
        "activity_performance_quality_flag": quality_flag(
            status,
            rows == expected_rows,
            movement_dist,
            len(route_distance) > 0,
        ),
        "authorization_note": (
            "Activity performance evidence only. No weather join, THCI scoring, "
            "radar scoring, or final hiking risk scoring is authorized."
        ),
    }


def build_audit(
    input_root: Path,
    input_root_status: str,
    source_summary_csv: Path,
    source_summary_rows: int,
    rows: list[dict[str, Any]],
    missing_count: int,
    failed_count: int,
    out_root: Path,
) -> dict[str, Any]:
    passed = (
        source_summary_rows == EXPECTED_ACTIVITY_COUNT
        and len(rows) == EXPECTED_ACTIVITY_COUNT
        and missing_count == 0
        and failed_count == 0
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "input_root": str(input_root),
        "input_root_status": input_root_status,
        "summary_csv": str(source_summary_csv),
        "summary_row_count": source_summary_rows,
        "activity_count_expected": EXPECTED_ACTIVITY_COUNT,
        "activity_count_processed": len(rows),
        "missing_activity_file_count": missing_count,
        "failed_activity_file_count": failed_count,
        "output_summary_csv": str(out_root / "activity_performance_summary.csv"),
        "output_audit_csv": str(out_root / "activity_performance_summary_audit.csv"),
        "output_report_html": str(out_root / "activity_performance_summary_report.html"),
        "weather_join_performed": "False",
        "thci_scoring_authorized": "False",
        "radar_scoring_authorized": "False",
        "final_hiking_risk_scoring_authorized": "False",
        "zero_fallback_used": "False",
        "audit_conclusion": (
            "PASS_ACTIVITY_PERFORMANCE_SUMMARY_ONLY" if passed else "FAIL"
        ),
    }


def table_html(rows: list[dict[str, Any]], fields: list[str]) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = []
    for row in rows:
        cells = "".join(
            f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields
        )
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_report(rows: list[dict[str, Any]], audit: dict[str, Any]) -> str:
    overview_fields = [
        "activity_id_short",
        "duration_min",
        "route_dist_covered_m",
        "calibrated_speed_mps_median",
        "heart_rate_bpm_median",
        "calibrated_cumulative_gain_m",
        "calibrated_cumulative_loss_m",
        "backend_use_analytics_ready_ratio",
        "calibration_review_required_ratio",
        "movement_review_required_ratio",
        "activity_performance_quality_flag",
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>IB3A-RC Full26 Activity Performance Summary</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2933; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
.card {{ border: 1px solid #d8dee4; border-radius: 8px; padding: 14px; background: #f8fafc; }}
table {{ border-collapse: collapse; width: 100%; font-size: 12px; margin-top: 16px; }}
th, td {{ border: 1px solid #d8dee4; padding: 6px; text-align: right; }}
th:first-child, td:first-child, th:last-child, td:last-child {{ text-align: left; }}
th {{ background: #eef2f6; position: sticky; top: 0; }}
.note {{ background: #fff8dc; border-left: 4px solid #d4a72c; padding: 12px; }}
</style>
</head>
<body>
<h1>IB3A-RC Full26 Activity Performance Summary</h1>
<div class="cards">
  <div class="card"><strong>{len(rows)}</strong><br>activities processed</div>
  <div class="card"><strong>{html.escape(str(audit['input_root_status']))}</strong><br>input root status</div>
  <div class="card"><strong>{html.escape(str(audit['audit_conclusion']))}</strong><br>audit conclusion</div>
</div>
<p class="note">Activity performance evidence only. This report performs no weather join and does not compute or authorize weather risk, THCI, radar, or final hiking risk scoring. Missing measurements remain missing.</p>
<h2>26 Activities Overview</h2>
{table_html(rows, overview_fields)}
</body>
</html>
"""


def main() -> int:
    args = parse_args()
    input_root, root_status, source_summary, primary_missing = resolve_input_root(
        args.primary_root, args.local_copy_root
    )
    source_summary_csv = input_root / SUMMARY_RELATIVE_PATH

    rows: list[dict[str, Any]] = []
    failed_count = 0
    for summary_row in source_summary.to_dict(orient="records"):
        try:
            rows.append(summarize_activity(input_root, summary_row))
        except Exception as exc:
            failed_count += 1
            print(f"FAIL activity_id={summary_row.get('activity_id')}: {exc}")

    audit = build_audit(
        input_root=input_root,
        input_root_status=root_status,
        source_summary_csv=source_summary_csv,
        source_summary_rows=len(source_summary),
        rows=rows,
        missing_count=len(primary_missing) if root_status == "PRIMARY_ROOT_USED" else 0,
        failed_count=failed_count,
        out_root=args.out_root,
    )

    args.out_root.mkdir(parents=True, exist_ok=True)
    summary_csv = args.out_root / "activity_performance_summary.csv"
    audit_csv = args.out_root / "activity_performance_summary_audit.csv"
    report_html = args.out_root / "activity_performance_summary_report.html"

    pd.DataFrame(rows, columns=SUMMARY_FIELDS).to_csv(
        summary_csv, index=False, encoding="utf-8-sig"
    )
    pd.DataFrame([audit]).to_csv(audit_csv, index=False, encoding="utf-8-sig")
    report_html.write_text(build_report(rows, audit), encoding="utf-8")

    print("IB3A-RC full26 activity performance summary v1")
    print("input_root:", input_root)
    print("input_root_status:", root_status)
    print("activity_count_processed:", len(rows))
    print("missing_activity_file_count:", audit["missing_activity_file_count"])
    print("failed_activity_file_count:", failed_count)
    print("summary_csv:", summary_csv)
    print("audit_csv:", audit_csv)
    print("report_html:", report_html)
    print("audit_conclusion:", audit["audit_conclusion"])
    return 0 if audit["audit_conclusion"].startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
