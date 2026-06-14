from __future__ import annotations

import argparse
import csv
import html
import math
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any


SCHEMA_VERSION = "ib3_baseline_hiking_performance_model_smoke_v1"

DEFAULT_JOIN_CSV = Path(
    "outputs/ib3w_activity_weather_performance_join_v1/"
    "activity_weather_performance_join.csv"
)
DEFAULT_JOIN_AUDIT_CSV = Path(
    "outputs/ib3w_activity_weather_performance_join_v1/"
    "activity_weather_performance_join_audit.csv"
)
DEFAULT_FEATURE_CONTRACT_CSV = Path(
    "configs/hiking_performance/"
    "ib3_baseline_hiking_performance_feature_contract_v1.csv"
)
DEFAULT_OUT_ROOT = Path("outputs/ib3_baseline_hiking_performance_model_smoke_v1")

EXPECTED_JOIN_AUDIT = "PASS_DESCRIPTIVE_ACTIVITY_WEATHER_PERFORMANCE_JOIN_ONLY"
PASS_CONCLUSION = "PASS_BASELINE_PERFORMANCE_SMOKE_DESCRIPTIVE_ONLY"
FAIL_CONCLUSION = "FAIL_BASELINE_PERFORMANCE_SMOKE_CONTRACT_OR_INPUT"

CANDIDATE_FIELDS = [
    "candidate_duration_min_per_km",
    "candidate_median_speed_kmh",
    "candidate_gain_m_per_km",
    "candidate_duration_min_per_100m_gain",
    "candidate_gain_rate_m_per_hour",
    "candidate_hr_median_context",
    "candidate_weather_context_flags",
    "candidate_data_quality_gate",
    "candidate_model_readiness_note",
]

OUTPUT_FIELDS = [
    "schema_version",
    "activity_id_short",
    "activity_id_full",
    "join_status",
    "duration_min",
    "route_dist_covered_m",
    "route_dist_covered_km",
    "calibrated_speed_mps_median",
    "moving_sec",
    "stopped_sec",
    "heart_rate_available",
    "heart_rate_bpm_median",
    "heart_rate_bpm_p75",
    "heart_rate_bpm_p90",
    "calibrated_cumulative_gain_m",
    "calibrated_cumulative_loss_m",
    "terrain_slope_pct_median",
    "terrain_slope_pct_p75",
    "terrain_slope_pct_p90",
    "backend_use_analytics_ready_ratio",
    "calibration_review_required_ratio",
    "movement_review_required_ratio",
    "activity_performance_quality_flag",
    "temperature_c",
    "relative_humidity_pct",
    "pressure_hpa",
    "wind_speed_ms",
    "wind_gust_ms",
    "precipitation_mm",
    "sunshine_duration_min",
    "uv_index",
    "rain_observed",
    "high_humidity_observed",
    "wind_gust_observed",
    "descriptive_tags",
    *CANDIDATE_FIELDS,
    "ability_score_generated",
    "ability_rank_generated",
    "thci_scoring_authorized",
    "radar_scoring_authorized",
    "final_hiking_risk_scoring_authorized",
    "authorization_note",
]

AUTHORIZATION_NOTE = (
    "Descriptive baseline performance smoke metrics only. No ability score, "
    "ranking, THCI score, radar score, or final hiking risk score is generated "
    "or authorized."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate descriptive candidate hiking performance smoke metrics."
    )
    parser.add_argument("--join-csv", type=Path, default=DEFAULT_JOIN_CSV)
    parser.add_argument(
        "--join-audit-csv", type=Path, default=DEFAULT_JOIN_AUDIT_CSV
    )
    parser.add_argument(
        "--feature-contract-csv",
        type=Path,
        default=DEFAULT_FEATURE_CONTRACT_CSV,
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


def format_number(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.6f}".rstrip("0").rstrip(".")


def safe_divide(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def weather_flags(row: dict[str, str]) -> list[str]:
    flags: list[str] = []
    if is_true(row.get("high_humidity_observed")):
        flags.append("HIGH_HUMIDITY_OBSERVED")
    if is_true(row.get("rain_observed")):
        flags.append("RAIN_OBSERVED")
    else:
        flags.append("NO_RAIN_OBSERVED")
    if is_true(row.get("wind_gust_observed")):
        flags.append("WIND_GUST_OBSERVED")
    uv_index = as_float(row.get("uv_index"))
    if uv_index is not None and uv_index >= 6:
        flags.append("HIGH_UV_OBSERVED")
    return flags


def quality_gate(row: dict[str, str]) -> tuple[str, str]:
    join_status = str(row.get("join_status", "")).strip().upper()
    analytics_ratio = as_float(row.get("backend_use_analytics_ready_ratio"))
    calibration_ratio = as_float(row.get("calibration_review_required_ratio"))
    movement_ratio = as_float(row.get("movement_review_required_ratio"))

    if join_status != "MATCHED":
        return (
            "NOT_READY_JOIN_UNMATCHED",
            "Weather and performance evidence are not matched; exclude from "
            "future descriptive model use.",
        )
    if analytics_ratio is None:
        return (
            "REVIEW_MISSING_ANALYTICS_READY_RATIO",
            "Analytics-ready ratio is missing; review data usability before "
            "future model use.",
        )
    if analytics_ratio < 0.5:
        return (
            "REVIEW_LOW_ANALYTICS_READY_RATIO",
            f"Analytics-ready ratio {analytics_ratio:.6f} is below the 0.5 "
            "smoke usability threshold.",
        )
    if calibration_ratio is None:
        return (
            "REVIEW_MISSING_CALIBRATION_REVIEW_RATIO",
            "Calibration-review ratio is missing; review data usability before "
            "future model use.",
        )
    if calibration_ratio > 0.5:
        return (
            "REVIEW_HIGH_CALIBRATION_REVIEW_RATIO",
            f"Calibration-review ratio {calibration_ratio:.6f} is above the "
            "0.5 smoke review threshold.",
        )
    if movement_ratio is None:
        return (
            "REVIEW_MISSING_MOVEMENT_REVIEW_RATIO",
            "Movement-review ratio is missing; review data usability before "
            "future model use.",
        )
    if movement_ratio > 0.5:
        return (
            "REVIEW_HIGH_MOVEMENT_REVIEW_RATIO",
            f"Movement-review ratio {movement_ratio:.6f} is above the 0.5 "
            "smoke review threshold.",
        )
    return (
        "READY_FOR_DESCRIPTIVE_MODEL_SMOKE",
        "Join and smoke usability checks passed for descriptive comparison; "
        "this does not authorize an ability or risk score.",
    )


def build_feature_row(row: dict[str, str]) -> dict[str, Any]:
    duration_min = as_float(row.get("duration_min"))
    distance_m = as_float(row.get("route_dist_covered_m"))
    distance_km = None if distance_m is None else distance_m / 1000
    speed_mps = as_float(row.get("calibrated_speed_mps_median"))
    gain_m = as_float(row.get("calibrated_cumulative_gain_m"))

    duration_per_km = safe_divide(duration_min, distance_km)
    speed_kmh = None if speed_mps is None else speed_mps * 3.6
    gain_per_km = safe_divide(gain_m, distance_km)
    duration_per_100m_gain = safe_divide(
        duration_min, None if gain_m is None else gain_m / 100
    )
    gain_rate = safe_divide(
        gain_m, None if duration_min is None else duration_min / 60
    )

    hr_context = (
        "HR_OBSERVED"
        if is_true(row.get("heart_rate_available"))
        and as_float(row.get("heart_rate_bpm_median")) is not None
        else "HR_UNAVAILABLE"
    )
    flags = weather_flags(row)
    gate, readiness_note = quality_gate(row)

    output = {field: row.get(field, "") for field in OUTPUT_FIELDS}
    output.update(
        {
            "schema_version": SCHEMA_VERSION,
            "route_dist_covered_km": format_number(distance_km),
            "candidate_duration_min_per_km": format_number(duration_per_km),
            "candidate_median_speed_kmh": format_number(speed_kmh),
            "candidate_gain_m_per_km": format_number(gain_per_km),
            "candidate_duration_min_per_100m_gain": format_number(
                duration_per_100m_gain
            ),
            "candidate_gain_rate_m_per_hour": format_number(gain_rate),
            "candidate_hr_median_context": hr_context,
            "candidate_weather_context_flags": "|".join(flags),
            "candidate_data_quality_gate": gate,
            "candidate_model_readiness_note": readiness_note,
            "ability_score_generated": "False",
            "ability_rank_generated": "False",
            "thci_scoring_authorized": "False",
            "radar_scoring_authorized": "False",
            "final_hiking_risk_scoring_authorized": "False",
            "authorization_note": AUTHORIZATION_NOTE,
        }
    )
    return output


def serialize_distribution(counter: Counter[str]) -> str:
    return "|".join(f"{key}:{counter[key]}" for key in sorted(counter))


def build_audit(
    args: argparse.Namespace,
    join_rows: list[dict[str, str]],
    join_audit_rows: list[dict[str, str]],
    contract_rows: list[dict[str, str]],
    feature_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    join_audit_status = (
        join_audit_rows[0].get("audit_conclusion", "")
        if len(join_audit_rows) == 1
        else ""
    )
    contract_all_disallowed = bool(contract_rows) and all(
        row.get("scoring_allowed_in_this_branch", "").strip().lower() == "false"
        for row in contract_rows
    )
    gate_distribution = Counter(
        str(row["candidate_data_quality_gate"]) for row in feature_rows
    )
    weather_distribution: Counter[str] = Counter()
    for row in feature_rows:
        for flag in str(row["candidate_weather_context_flags"]).split("|"):
            if flag:
                weather_distribution[flag] += 1

    authorization_fields = [
        "ability_score_generated",
        "ability_rank_generated",
        "thci_scoring_authorized",
        "radar_scoring_authorized",
        "final_hiking_risk_scoring_authorized",
    ]
    all_authorization_false = all(
        str(row.get(field, "")).lower() == "false"
        for row in feature_rows
        for field in authorization_fields
    )
    passed = (
        len(join_rows) == 26
        and len(join_audit_rows) == 1
        and join_audit_status == EXPECTED_JOIN_AUDIT
        and len(contract_rows) == 35
        and contract_all_disallowed
        and len(feature_rows) == 26
        and all_authorization_false
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "input_join_csv": str(args.join_csv),
        "input_join_audit_csv": str(args.join_audit_csv),
        "input_feature_contract_csv": str(args.feature_contract_csv),
        "input_join_row_count": len(join_rows),
        "feature_contract_row_count": len(contract_rows),
        "feature_contract_all_scoring_disallowed": str(
            contract_all_disallowed
        ),
        "output_feature_row_count": len(feature_rows),
        "ability_score_generated": "False",
        "ability_rank_generated": "False",
        "thci_scoring_authorized": "False",
        "radar_scoring_authorized": "False",
        "final_hiking_risk_scoring_authorized": "False",
        "zero_fallback_used": "False",
        "candidate_metric_count": len(CANDIDATE_FIELDS),
        "data_quality_gate_distribution": serialize_distribution(
            gate_distribution
        ),
        "weather_context_flag_distribution": serialize_distribution(
            weather_distribution
        ),
        "audit_conclusion": PASS_CONCLUSION if passed else FAIL_CONCLUSION,
    }


def metric_summary(
    rows: list[dict[str, Any]], field: str
) -> tuple[str, str, str]:
    values = [
        value
        for value in (as_float(row.get(field)) for row in rows)
        if value is not None
    ]
    if not values:
        return "", "", ""
    return (
        format_number(min(values)),
        format_number(median(values)),
        format_number(max(values)),
    )


def render_activity_table(rows: list[dict[str, Any]]) -> str:
    fields = [
        "activity_id_short",
        "duration_min",
        "route_dist_covered_km",
        "candidate_duration_min_per_km",
        "candidate_median_speed_kmh",
        "candidate_gain_m_per_km",
        "candidate_gain_rate_m_per_hour",
        "heart_rate_bpm_median",
        "relative_humidity_pct",
        "precipitation_mm",
        "wind_gust_ms",
        "uv_index",
        "candidate_weather_context_flags",
        "candidate_data_quality_gate",
    ]
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = []
    for row in rows:
        cells = "".join(
            f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields
        )
        body.append(f"<tr>{cells}</tr>")
    return (
        f"<table><thead><tr>{header}</tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table>"
    )


def build_report(
    feature_rows: list[dict[str, Any]], audit: dict[str, Any]
) -> str:
    gates = Counter(
        str(row["candidate_data_quality_gate"]) for row in feature_rows
    )
    ready_count = gates["READY_FOR_DESCRIPTIVE_MODEL_SMOKE"]
    review_count = len(feature_rows) - ready_count
    hr_observed_count = sum(
        row["candidate_hr_median_context"] == "HR_OBSERVED"
        for row in feature_rows
    )
    high_humidity_count = sum(
        "HIGH_HUMIDITY_OBSERVED"
        in str(row["candidate_weather_context_flags"]).split("|")
        for row in feature_rows
    )
    rain_count = sum(
        "RAIN_OBSERVED"
        in str(row["candidate_weather_context_flags"]).split("|")
        for row in feature_rows
    )
    high_uv_count = sum(
        "HIGH_UV_OBSERVED"
        in str(row["candidate_weather_context_flags"]).split("|")
        for row in feature_rows
    )
    cards = [
        ("activities", len(feature_rows)),
        ("candidate metrics", audit["candidate_metric_count"]),
        ("ready", ready_count),
        ("review", review_count),
        ("HR observed", hr_observed_count),
        ("high humidity", high_humidity_count),
        ("rain observed", rain_count),
        ("high UV", high_uv_count),
    ]
    card_html = "".join(
        f'<div class="card"><strong>{html.escape(str(value))}</strong>'
        f"<span>{html.escape(label)}</span></div>"
        for label, value in cards
    )

    summaries = [
        (
            "duration_min_per_km",
            metric_summary(feature_rows, "candidate_duration_min_per_km"),
        ),
        (
            "median_speed_kmh",
            metric_summary(feature_rows, "candidate_median_speed_kmh"),
        ),
        (
            "gain_m_per_km",
            metric_summary(feature_rows, "candidate_gain_m_per_km"),
        ),
        (
            "gain_rate_m_per_hour",
            metric_summary(feature_rows, "candidate_gain_rate_m_per_hour"),
        ),
    ]
    summary_rows = "".join(
        "<tr>"
        f"<td>{html.escape(name)}</td>"
        f"<td>{html.escape(values[0])}</td>"
        f"<td>{html.escape(values[1])}</td>"
        f"<td>{html.escape(values[2])}</td>"
        "</tr>"
        for name, values in summaries
    )

    gate_rows = "".join(
        f"<li><code>{html.escape(gate)}</code>: {count}</li>"
        for gate, count in sorted(gates.items())
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>IB3 Baseline Hiking Performance Model Smoke v1</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2933; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; }}
.card {{ border: 1px solid #d8dee4; border-radius: 8px; padding: 12px; background: #f8fafc; }}
.card strong {{ display: block; font-size: 24px; }}
.card span {{ color: #52606d; font-size: 12px; }}
.note {{ background: #fff8dc; border-left: 4px solid #d4a72c; padding: 12px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 12px; margin-top: 12px; }}
th, td {{ border: 1px solid #d8dee4; padding: 6px; text-align: right; }}
th:first-child, td:first-child, th:nth-last-child(-n+2), td:nth-last-child(-n+2) {{ text-align: left; }}
th {{ background: #eef2f6; position: sticky; top: 0; }}
code {{ font-size: 12px; }}
</style>
</head>
<body>
<h1>IB3 Baseline Hiking Performance Model Smoke v1</h1>
<p class="note"><strong>This smoke report generates descriptive candidate metrics only.</strong><br>
It does not compute ability scores, rankings, THCI scores, radar scores, or final hiking risk scores.
Weather context flags are descriptive and are not penalties. Missing values are not hard-filled as zero.</p>
<div class="cards">{card_html}</div>
<h2>Data quality gate distribution</h2>
<ul>{gate_rows}</ul>
<h2>Candidate metric summary</h2>
<table>
<thead><tr><th>metric</th><th>min</th><th>median</th><th>max</th></tr></thead>
<tbody>{summary_rows}</tbody>
</table>
<h2>Activity table</h2>
{render_activity_table(feature_rows)}
</body>
</html>
"""


def main() -> int:
    args = parse_args()
    join_rows = read_csv(args.join_csv)
    join_audit_rows = read_csv(args.join_audit_csv)
    contract_rows = read_csv(args.feature_contract_csv)

    feature_rows = [build_feature_row(row) for row in join_rows]
    audit = build_audit(
        args, join_rows, join_audit_rows, contract_rows, feature_rows
    )

    feature_csv = args.out_root / "activity_baseline_performance_smoke_features.csv"
    audit_csv = args.out_root / "activity_baseline_performance_smoke_audit.csv"
    report_html = args.out_root / "activity_baseline_performance_smoke_report.html"

    write_csv(feature_csv, feature_rows, OUTPUT_FIELDS)
    write_csv(audit_csv, [audit], list(audit))
    report_html.write_text(build_report(feature_rows, audit), encoding="utf-8")

    print("IB3 baseline hiking performance model smoke v1")
    for field in [
        "input_join_row_count",
        "feature_contract_row_count",
        "feature_contract_all_scoring_disallowed",
        "output_feature_row_count",
        "candidate_metric_count",
        "data_quality_gate_distribution",
        "weather_context_flag_distribution",
        "audit_conclusion",
    ]:
        print(f"{field}: {audit[field]}")
    print("feature_csv:", feature_csv)
    print("audit_csv:", audit_csv)
    print("report_html:", report_html)
    return 0 if audit["audit_conclusion"] == PASS_CONCLUSION else 1


if __name__ == "__main__":
    raise SystemExit(main())
