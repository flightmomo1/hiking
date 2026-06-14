from __future__ import annotations

import argparse
import csv
import html
import math
from pathlib import Path
from statistics import median
from typing import Any


SCHEMA_VERSION = "ib3w_activity_weather_performance_join_v1"

DEFAULT_PERFORMANCE_CSV = Path(
    "outputs/ib3a_rc_full26_performance_summary_v1/activity_performance_summary.csv"
)
DEFAULT_PERFORMANCE_AUDIT_CSV = Path(
    "outputs/ib3a_rc_full26_performance_summary_v1/activity_performance_summary_audit.csv"
)
DEFAULT_WEATHER_CSV = Path(
    "outputs/ib3w_codis_weather_profile_report_v1/activity_weather_profile_report_table.csv"
)
DEFAULT_WEATHER_SUMMARY_CSV = Path(
    "outputs/ib3w_codis_weather_profile_report_v1/weather_profile_report_summary.csv"
)
DEFAULT_OUT_ROOT = Path("outputs/ib3w_activity_weather_performance_join_v1")

JOIN_FIELDS = [
    "schema_version",
    "activity_id_short",
    "activity_id_full",
    "performance_activity_id_full",
    "weather_activity_id",
    "join_status",
    "duration_sec",
    "duration_min",
    "route_dist_covered_m",
    "backend_use_analytics_ready_ratio",
    "calibration_review_required_ratio",
    "movement_review_required_ratio",
    "calibrated_speed_mps_median",
    "calibrated_speed_mps_p25",
    "calibrated_speed_mps_p75",
    "moving_sec",
    "stopped_sec",
    "movement_state_distribution",
    "heart_rate_available",
    "heart_rate_bpm_median",
    "heart_rate_bpm_p75",
    "heart_rate_bpm_p90",
    "calibrated_cumulative_gain_m",
    "calibrated_cumulative_loss_m",
    "terrain_slope_pct_median",
    "terrain_slope_pct_p75",
    "terrain_slope_pct_p90",
    "terrain_risk_band_distribution",
    "route_phase_distribution",
    "activity_performance_quality_flag",
    "activity_date_taiwan",
    "activity_start_taiwan",
    "activity_end_taiwan",
    "observed_context_source_type",
    "observed_variable_count",
    "unavailable_variable_count",
    "temperature_c",
    "relative_humidity_pct",
    "pressure_hpa",
    "wind_speed_ms",
    "wind_gust_ms",
    "wind_direction_deg",
    "precipitation_mm",
    "sunshine_duration_min",
    "uv_index",
    "rain_observed",
    "high_humidity_observed",
    "wind_gust_observed",
    "descriptive_tags",
    "codis_selected_station_names",
    "descriptive_context_note",
    "weather_join_performed",
    "thci_scoring_authorized",
    "radar_scoring_authorized",
    "final_hiking_risk_scoring_authorized",
    "authorization_note",
]

PERFORMANCE_FIELDS = JOIN_FIELDS[6:30]
WEATHER_FIELDS = JOIN_FIELDS[30:51]

NO_SCORING_NOTE = (
    "Descriptive activity performance and weather context join only. "
    "No THCI scoring, radar scoring, final hiking risk scoring, or ability scoring is authorized."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Join IB3A-RC activity performance evidence with IB3W weather context."
    )
    parser.add_argument("--performance-csv", type=Path, default=DEFAULT_PERFORMANCE_CSV)
    parser.add_argument(
        "--performance-audit-csv",
        type=Path,
        default=DEFAULT_PERFORMANCE_AUDIT_CSV,
    )
    parser.add_argument("--weather-csv", type=Path, default=DEFAULT_WEATHER_CSV)
    parser.add_argument(
        "--weather-summary-csv",
        type=Path,
        default=DEFAULT_WEATHER_SUMMARY_CSV,
    )
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def as_float(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return None if math.isnan(number) else number


def is_true(value: Any) -> bool:
    return str(value or "").strip().lower() in {"true", "1", "yes", "y"}


def descriptive_context_note(weather: dict[str, str]) -> str:
    notes: list[str] = []
    temperature = as_float(weather.get("temperature_c"))
    humidity = as_float(weather.get("relative_humidity_pct"))
    precipitation = as_float(weather.get("precipitation_mm"))
    gust = as_float(weather.get("wind_gust_ms"))
    sunshine = as_float(weather.get("sunshine_duration_min"))
    uv_index = as_float(weather.get("uv_index"))

    if is_true(weather.get("high_humidity_observed")) or (
        humidity is not None and humidity >= 90
    ):
        notes.append("HIGH_HUMIDITY_WITH_PERFORMANCE_CONTEXT")
    if is_true(weather.get("rain_observed")) or (
        precipitation is not None and precipitation > 0
    ):
        notes.append("RAIN_OBSERVED_WITH_PERFORMANCE_CONTEXT")
    if gust is not None and gust >= 10:
        notes.append("STRONG_GUST_WITH_PERFORMANCE_CONTEXT")
    if (
        temperature is not None
        and temperature >= 25
        and sunshine is not None
        and sunshine >= 60
        and uv_index is not None
        and uv_index >= 6
    ):
        notes.append("HOT_SUNNY_WITH_PERFORMANCE_CONTEXT")
    if not notes:
        notes.append("WEATHER_CONTEXT_ATTACHED_DESCRIPTIVE_ONLY")
    return "|".join(notes)


def validate_upstream(
    performance_audit_rows: list[dict[str, str]],
    weather_summary_rows: list[dict[str, str]],
) -> tuple[str, str]:
    if len(performance_audit_rows) != 1:
        raise ValueError("Performance audit must contain exactly one row")
    if len(weather_summary_rows) != 1:
        raise ValueError("Weather profile summary must contain exactly one row")

    performance_status = performance_audit_rows[0].get("audit_conclusion", "")
    weather_status = weather_summary_rows[0].get("report_conclusion", "")
    if performance_status != "PASS_ACTIVITY_PERFORMANCE_SUMMARY_ONLY":
        raise ValueError(f"Performance audit is not PASS: {performance_status}")
    if weather_status != "PASS_DESCRIPTIVE_EVIDENCE_REPORT_ONLY":
        raise ValueError(f"Weather profile summary is not PASS: {weather_status}")
    return performance_status, weather_status


def build_join(
    performance_rows: list[dict[str, str]],
    weather_rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    weather_by_id: dict[str, dict[str, str]] = {}
    for row in weather_rows:
        key = row.get("activity_id_short", "")
        if not key:
            raise ValueError("Weather row has blank activity_id_short")
        if key in weather_by_id:
            raise ValueError(f"Duplicate weather activity_id_short: {key}")
        weather_by_id[key] = row

    joined: list[dict[str, Any]] = []
    matched_weather_keys: set[str] = set()
    performance_unmatched: list[str] = []

    for performance in performance_rows:
        key = performance.get("activity_id_short", "")
        weather = weather_by_id.get(key)
        if weather is None:
            performance_unmatched.append(key)
            continue

        matched_weather_keys.add(key)
        output: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "activity_id_short": key,
            "activity_id_full": performance.get("activity_id_full", ""),
            "performance_activity_id_full": performance.get("activity_id_full", ""),
            "weather_activity_id": weather.get("activity_id", ""),
            "join_status": "MATCHED",
        }
        for field in PERFORMANCE_FIELDS:
            output[field] = performance.get(field, "")
        for field in WEATHER_FIELDS:
            output[field] = weather.get(field, "")
        output.update(
            {
                "descriptive_context_note": descriptive_context_note(weather),
                "weather_join_performed": "True",
                "thci_scoring_authorized": "False",
                "radar_scoring_authorized": "False",
                "final_hiking_risk_scoring_authorized": "False",
                "authorization_note": NO_SCORING_NOTE,
            }
        )
        joined.append(output)

    weather_unmatched = [
        row.get("activity_id", "")
        for row in weather_rows
        if row.get("activity_id_short", "") not in matched_weather_keys
    ]
    return joined, performance_unmatched, weather_unmatched


def build_audit(
    args: argparse.Namespace,
    performance_rows: list[dict[str, str]],
    weather_rows: list[dict[str, str]],
    joined_rows: list[dict[str, Any]],
    performance_unmatched: list[str],
    weather_unmatched: list[str],
    performance_status: str,
    weather_status: str,
) -> dict[str, Any]:
    expected_unmatched = [
        "qixing_lengshuikeng_xiaoyoukeng_20260410_biji_gpx"
    ]
    passed = (
        len(performance_rows) == 26
        and len(weather_rows) == 27
        and len(joined_rows) == 26
        and not performance_unmatched
        and weather_unmatched == expected_unmatched
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "performance_input_csv": str(args.performance_csv),
        "weather_input_csv": str(args.weather_csv),
        "performance_row_count": len(performance_rows),
        "weather_row_count": len(weather_rows),
        "matched_row_count": len(joined_rows),
        "performance_unmatched_count": len(performance_unmatched),
        "weather_unmatched_count": len(weather_unmatched),
        "weather_unmatched_activity_ids": "|".join(weather_unmatched),
        "join_key": "activity_id_short",
        "weather_join_performed": "True",
        "performance_summary_audit_status": performance_status,
        "weather_profile_summary_status": weather_status,
        "thci_scoring_authorized": "False",
        "radar_scoring_authorized": "False",
        "final_hiking_risk_scoring_authorized": "False",
        "ability_scoring_authorized": "False",
        "zero_fallback_used": "False",
        "audit_conclusion": (
            "PASS_DESCRIPTIVE_ACTIVITY_WEATHER_PERFORMANCE_JOIN_ONLY"
            if passed
            else "FAIL"
        ),
    }


def median_value(rows: list[dict[str, Any]], field: str) -> str:
    values = [
        number
        for number in (as_float(row.get(field)) for row in rows)
        if number is not None
    ]
    return f"{median(values):.4f}".rstrip("0").rstrip(".") if values else ""


def max_value(rows: list[dict[str, Any]], field: str) -> str:
    values = [
        number
        for number in (as_float(row.get(field)) for row in rows)
        if number is not None
    ]
    return f"{max(values):.4f}".rstrip("0").rstrip(".") if values else ""


def render_table(rows: list[dict[str, Any]]) -> str:
    fields = [
        "activity_id_short",
        "duration_min",
        "route_dist_covered_m",
        "calibrated_speed_mps_median",
        "heart_rate_bpm_median",
        "backend_use_analytics_ready_ratio",
        "temperature_c",
        "relative_humidity_pct",
        "precipitation_mm",
        "wind_gust_ms",
        "sunshine_duration_min",
        "uv_index",
        "descriptive_context_note",
    ]
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = []
    for row in rows:
        cells = "".join(
            f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields
        )
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_report(
    joined_rows: list[dict[str, Any]],
    audit: dict[str, Any],
) -> str:
    high_humidity_count = sum(
        1 for row in joined_rows if is_true(row.get("high_humidity_observed"))
    )
    rain_count = sum(1 for row in joined_rows if is_true(row.get("rain_observed")))
    cards = [
        ("performance activities", audit["performance_row_count"]),
        ("weather activities", audit["weather_row_count"]),
        ("matched", audit["matched_row_count"]),
        ("weather unmatched", audit["weather_unmatched_count"]),
        ("high humidity", high_humidity_count),
        ("rain observed", rain_count),
        ("max wind gust m/s", max_value(joined_rows, "wind_gust_ms")),
        ("median duration min", median_value(joined_rows, "duration_min")),
        ("median route covered m", median_value(joined_rows, "route_dist_covered_m")),
        ("median speed m/s", median_value(joined_rows, "calibrated_speed_mps_median")),
    ]
    card_html = "".join(
        f'<div class="card"><strong>{html.escape(str(value))}</strong><span>{html.escape(label)}</span></div>'
        for label, value in cards
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>IB3W Activity Weather Performance Join</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2933; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }}
.card {{ border: 1px solid #d8dee4; border-radius: 8px; padding: 12px; background: #f8fafc; }}
.card strong {{ display: block; font-size: 24px; }}
.card span {{ color: #52606d; font-size: 12px; }}
.note {{ background: #fff8dc; border-left: 4px solid #d4a72c; padding: 12px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 12px; margin-top: 18px; }}
th, td {{ border: 1px solid #d8dee4; padding: 6px; text-align: right; }}
th:first-child, td:first-child, th:last-child, td:last-child {{ text-align: left; }}
th {{ background: #eef2f6; position: sticky; top: 0; }}
</style>
</head>
<body>
<h1>IB3W Activity Weather Performance Join</h1>
<p class="note">This report joins activity performance evidence and weather context evidence. It is descriptive only. It does not authorize THCI scoring, radar scoring, final hiking risk scoring, or ability scoring. Missing values remain missing and are not hard-filled as zero.</p>
<div class="cards">{card_html}</div>
<h2>Matched activities</h2>
{render_table(joined_rows)}
</body>
</html>
"""


def main() -> int:
    args = parse_args()
    performance_rows = read_csv(args.performance_csv)
    performance_audit_rows = read_csv(args.performance_audit_csv)
    weather_rows = read_csv(args.weather_csv)
    weather_summary_rows = read_csv(args.weather_summary_csv)

    performance_status, weather_status = validate_upstream(
        performance_audit_rows, weather_summary_rows
    )
    joined_rows, performance_unmatched, weather_unmatched = build_join(
        performance_rows, weather_rows
    )
    audit = build_audit(
        args,
        performance_rows,
        weather_rows,
        joined_rows,
        performance_unmatched,
        weather_unmatched,
        performance_status,
        weather_status,
    )

    join_csv = args.out_root / "activity_weather_performance_join.csv"
    audit_csv = args.out_root / "activity_weather_performance_join_audit.csv"
    report_html = args.out_root / "activity_weather_performance_join_report.html"
    write_csv(join_csv, joined_rows, JOIN_FIELDS)
    write_csv(audit_csv, [audit], list(audit))
    report_html.write_text(build_report(joined_rows, audit), encoding="utf-8")

    print("IB3W activity weather performance join v1")
    print("performance_row_count:", audit["performance_row_count"])
    print("weather_row_count:", audit["weather_row_count"])
    print("matched_row_count:", audit["matched_row_count"])
    print("performance_unmatched_count:", audit["performance_unmatched_count"])
    print("weather_unmatched_count:", audit["weather_unmatched_count"])
    print("weather_unmatched_activity_ids:", audit["weather_unmatched_activity_ids"])
    print("join_csv:", join_csv)
    print("audit_csv:", audit_csv)
    print("report_html:", report_html)
    print("audit_conclusion:", audit["audit_conclusion"])
    return 0 if audit["audit_conclusion"].startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
