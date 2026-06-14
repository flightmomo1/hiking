from __future__ import annotations

import argparse
import csv
import html
import math
from pathlib import Path
from statistics import median
from typing import Any


SCHEMA_VERSION = (
    "ib3_baseline_hiking_performance_route_normalized_comparison_smoke_v1"
)

DEFAULT_GATE_CSV = Path(
    "outputs/ib3_baseline_hiking_performance_v0_usability_gate_smoke_v1/"
    "activity_v0_usability_gate_smoke.csv"
)
DEFAULT_GATE_AUDIT_CSV = Path(
    "outputs/ib3_baseline_hiking_performance_v0_usability_gate_smoke_v1/"
    "activity_v0_usability_gate_smoke_audit.csv"
)
DEFAULT_RULE_CONTRACT_CSV = Path(
    "configs/hiking_performance/"
    "ib3_baseline_hiking_performance_model_v0_rule_contract_v1.csv"
)
DEFAULT_OUTPUT_CONTRACT_CSV = Path(
    "configs/hiking_performance/"
    "ib3_baseline_hiking_performance_model_v0_output_contract_v1.csv"
)
DEFAULT_OUT_ROOT = Path(
    "outputs/"
    "ib3_baseline_hiking_performance_route_normalized_comparison_smoke_v1"
)

EXPECTED_GATE_AUDIT = "PASS_V0_USABILITY_GATE_SMOKE_ONLY"
PASS_CONCLUSION = "PASS_ROUTE_NORMALIZED_COMPARISON_SMOKE_DESCRIPTIVE_ONLY"
FAIL_CONCLUSION = "FAIL_ROUTE_NORMALIZED_COMPARISON_SMOKE_CONTRACT_OR_INPUT"
SUPPORTED_USABLE_GATES = {"USABLE", "USABLE_FOR_V0_MODEL_SMOKE"}
NEAR_MEDIAN_RELATIVE_TOLERANCE = 0.05

METRICS = {
    "duration_min_per_km": "candidate_duration_min_per_km",
    "median_speed_kmh": "candidate_median_speed_kmh",
    "gain_m_per_km": "candidate_gain_m_per_km",
    "gain_rate_m_per_hour": "candidate_gain_rate_m_per_hour",
}

COMPARISON_FIELDS = [
    "schema_version",
    "activity_id_short",
    "activity_id_full",
    "v0_candidate_group_id",
    "v0_usability_gate",
    "included_in_baseline_reference",
    "duration_min",
    "route_dist_covered_km",
    "candidate_duration_min_per_km",
    "candidate_median_speed_kmh",
    "candidate_gain_m_per_km",
    "candidate_duration_min_per_100m_gain",
    "candidate_gain_rate_m_per_hour",
    "heart_rate_bpm_median",
    "temperature_c",
    "relative_humidity_pct",
    "precipitation_mm",
    "wind_gust_ms",
    "sunshine_duration_min",
    "uv_index",
    "candidate_weather_context_flags",
    "baseline_duration_min_per_km_median",
    "baseline_median_speed_kmh_median",
    "baseline_gain_m_per_km_median",
    "baseline_gain_rate_m_per_hour_median",
    "duration_min_per_km_delta_from_median",
    "median_speed_kmh_delta_from_median",
    "gain_m_per_km_delta_from_median",
    "gain_rate_m_per_hour_delta_from_median",
    "descriptive_performance_context",
    "descriptive_weather_context",
    "comparison_note",
    "ability_score_generated",
    "ability_rank_generated",
    "ability_class_generated",
    "thci_scoring_authorized",
    "radar_scoring_authorized",
    "final_hiking_risk_scoring_authorized",
    "authorization_note",
]

SUMMARY_FIELDS = [
    "schema_version",
    "candidate_group_id",
    "input_row_count",
    "usable_row_count",
    "review_only_row_count",
    "baseline_reference_row_count",
]
for prefix in METRICS:
    SUMMARY_FIELDS.extend(
        [
            f"{prefix}_min",
            f"{prefix}_p25",
            f"{prefix}_median",
            f"{prefix}_p75",
            f"{prefix}_max",
        ]
    )
SUMMARY_FIELDS.extend(
    [
        "hr_median_observed_count",
        "high_humidity_observed_count",
        "rain_observed_count",
        "high_uv_observed_count",
        "wind_gust_observed_count",
        "ability_score_generated",
        "ability_rank_generated",
        "ability_class_generated",
        "thci_scoring_authorized",
        "radar_scoring_authorized",
        "final_hiking_risk_scoring_authorized",
        "authorization_note",
    ]
)

AUTHORIZATION_NOTE = (
    "Descriptive route-normalized comparison smoke only. No ability score, "
    "rank, class, THCI score, radar score, or final hiking risk score is "
    "generated or authorized."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a descriptive route-normalized comparison smoke."
    )
    parser.add_argument("--gate-csv", type=Path, default=DEFAULT_GATE_CSV)
    parser.add_argument(
        "--gate-audit-csv", type=Path, default=DEFAULT_GATE_AUDIT_CSV
    )
    parser.add_argument(
        "--rule-contract-csv", type=Path, default=DEFAULT_RULE_CONTRACT_CSV
    )
    parser.add_argument(
        "--output-contract-csv", type=Path, default=DEFAULT_OUTPUT_CONTRACT_CSV
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


def format_number(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.6f}".rstrip("0").rstrip(".")


def percentile_inc(values: list[float], probability: float) -> float:
    """Excel PERCENTILE.INC equivalent using linear interpolation."""
    if not values:
        raise ValueError("Cannot calculate a percentile from an empty list")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def metric_values(rows: list[dict[str, str]], field: str) -> list[float]:
    values = [as_float(row.get(field)) for row in rows]
    return [value for value in values if value is not None]


def metric_summary(rows: list[dict[str, str]], field: str) -> dict[str, float]:
    values = metric_values(rows, field)
    if not values:
        raise ValueError(f"No usable values for required metric: {field}")
    return {
        "min": min(values),
        "p25": percentile_inc(values, 0.25),
        "median": median(values),
        "p75": percentile_inc(values, 0.75),
        "max": max(values),
    }


def flag_set(row: dict[str, str]) -> set[str]:
    return {
        flag
        for flag in str(row.get("candidate_weather_context_flags", "")).split("|")
        if flag
    }


def count_flag(rows: list[dict[str, str]], flag: str) -> int:
    return sum(flag in flag_set(row) for row in rows)


def build_summary(
    input_rows: list[dict[str, str]],
    usable_rows: list[dict[str, str]],
    candidate_group_id: str,
    summaries: dict[str, dict[str, float]],
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "candidate_group_id": candidate_group_id,
        "input_row_count": len(input_rows),
        "usable_row_count": len(usable_rows),
        "review_only_row_count": len(input_rows) - len(usable_rows),
        "baseline_reference_row_count": len(usable_rows),
    }
    for prefix, stats in summaries.items():
        for statistic, value in stats.items():
            row[f"{prefix}_{statistic}"] = format_number(value)
    row.update(
        {
            "hr_median_observed_count": sum(
                as_float(item.get("heart_rate_bpm_median")) is not None
                for item in usable_rows
            ),
            "high_humidity_observed_count": count_flag(
                usable_rows, "HIGH_HUMIDITY_OBSERVED"
            ),
            "rain_observed_count": count_flag(usable_rows, "RAIN_OBSERVED"),
            "high_uv_observed_count": count_flag(
                usable_rows, "HIGH_UV_OBSERVED"
            ),
            "wind_gust_observed_count": count_flag(
                usable_rows, "WIND_GUST_OBSERVED"
            ),
            "ability_score_generated": "False",
            "ability_rank_generated": "False",
            "ability_class_generated": "False",
            "thci_scoring_authorized": "False",
            "radar_scoring_authorized": "False",
            "final_hiking_risk_scoring_authorized": "False",
            "authorization_note": AUTHORIZATION_NOTE,
        }
    )
    return row


def performance_context(value: float, baseline_median: float) -> str:
    tolerance = abs(baseline_median) * NEAR_MEDIAN_RELATIVE_TOLERANCE
    delta = value - baseline_median
    if abs(delta) <= tolerance:
        return "OBSERVED_NEAR_MEDIAN_DURATION_PER_KM"
    if delta < 0:
        return "OBSERVED_BELOW_MEDIAN_DURATION_PER_KM"
    return "OBSERVED_ABOVE_MEDIAN_DURATION_PER_KM"


def weather_context(row: dict[str, str]) -> str:
    flags = flag_set(row)
    descriptions: list[str] = []
    if "HIGH_HUMIDITY_OBSERVED" in flags:
        descriptions.append("HIGH_HUMIDITY_CONTEXT")
    if "RAIN_OBSERVED" in flags:
        descriptions.append("RAIN_OBSERVED_CONTEXT")
    if "HIGH_UV_OBSERVED" in flags:
        descriptions.append("HIGH_UV_CONTEXT")
    if "WIND_GUST_OBSERVED" in flags:
        descriptions.append("WIND_GUST_OBSERVED_CONTEXT")
    if not descriptions:
        descriptions.append("NO_LISTED_WEATHER_CONTEXT_FLAG")
    return "|".join(descriptions)


def build_comparison_rows(
    usable_rows: list[dict[str, str]],
    summaries: dict[str, dict[str, float]],
) -> list[dict[str, Any]]:
    baseline_medians = {
        name: stats["median"] for name, stats in summaries.items()
    }
    output_rows: list[dict[str, Any]] = []
    for source in usable_rows:
        duration_per_km = as_float(source.get("candidate_duration_min_per_km"))
        speed_kmh = as_float(source.get("candidate_median_speed_kmh"))
        gain_per_km = as_float(source.get("candidate_gain_m_per_km"))
        gain_rate = as_float(source.get("candidate_gain_rate_m_per_hour"))
        if None in {duration_per_km, speed_kmh, gain_per_km, gain_rate}:
            raise ValueError(
                f"Usable row has missing comparison metric: "
                f"{source.get('activity_id_short', '')}"
            )

        row = {field: source.get(field, "") for field in COMPARISON_FIELDS}
        row.update(
            {
                "schema_version": SCHEMA_VERSION,
                "included_in_baseline_reference": "True",
                "baseline_duration_min_per_km_median": format_number(
                    baseline_medians["duration_min_per_km"]
                ),
                "baseline_median_speed_kmh_median": format_number(
                    baseline_medians["median_speed_kmh"]
                ),
                "baseline_gain_m_per_km_median": format_number(
                    baseline_medians["gain_m_per_km"]
                ),
                "baseline_gain_rate_m_per_hour_median": format_number(
                    baseline_medians["gain_rate_m_per_hour"]
                ),
                "duration_min_per_km_delta_from_median": format_number(
                    duration_per_km
                    - baseline_medians["duration_min_per_km"]
                ),
                "median_speed_kmh_delta_from_median": format_number(
                    speed_kmh - baseline_medians["median_speed_kmh"]
                ),
                "gain_m_per_km_delta_from_median": format_number(
                    gain_per_km - baseline_medians["gain_m_per_km"]
                ),
                "gain_rate_m_per_hour_delta_from_median": format_number(
                    gain_rate - baseline_medians["gain_rate_m_per_hour"]
                ),
                "descriptive_performance_context": performance_context(
                    duration_per_km,
                    baseline_medians["duration_min_per_km"],
                ),
                "descriptive_weather_context": weather_context(source),
                "comparison_note": (
                    "DESCRIPTIVE_ONLY; below/above/near median describes this "
                    "usable sample only and is not an ability judgment. Raw "
                    "weather numeric fields are blank when absent from the "
                    "gate input; weather flags are not penalties."
                ),
                "ability_score_generated": "False",
                "ability_rank_generated": "False",
                "ability_class_generated": "False",
                "thci_scoring_authorized": "False",
                "radar_scoring_authorized": "False",
                "final_hiking_risk_scoring_authorized": "False",
                "authorization_note": AUTHORIZATION_NOTE,
            }
        )
        output_rows.append(row)
    return output_rows


def build_audit(
    args: argparse.Namespace,
    input_rows: list[dict[str, str]],
    usable_rows: list[dict[str, str]],
    comparison_rows: list[dict[str, Any]],
    gate_audit_rows: list[dict[str, str]],
    rule_rows: list[dict[str, str]],
    output_contract_rows: list[dict[str, str]],
    candidate_group_id: str,
) -> dict[str, Any]:
    gate_audit_status = (
        gate_audit_rows[0].get("audit_conclusion", "")
        if len(gate_audit_rows) == 1
        else ""
    )
    rule_all_disallowed = bool(rule_rows) and all(
        row.get("scoring_allowed_in_this_branch", "").strip().lower() == "false"
        for row in rule_rows
    )
    output_all_generated_false = bool(output_contract_rows) and all(
        row.get("generated_in_this_branch", "").strip().lower() == "false"
        for row in output_contract_rows
    )
    output_all_scoring_disallowed = bool(output_contract_rows) and all(
        row.get("scoring_allowed_in_this_branch", "").strip().lower() == "false"
        for row in output_contract_rows
    )
    auth_fields = [
        "ability_score_generated",
        "ability_rank_generated",
        "ability_class_generated",
        "thci_scoring_authorized",
        "radar_scoring_authorized",
        "final_hiking_risk_scoring_authorized",
    ]
    all_auth_false = all(
        str(row.get(field, "")).lower() == "false"
        for row in comparison_rows
        for field in auth_fields
    )
    all_included = all(
        str(row.get("included_in_baseline_reference", "")).lower() == "true"
        for row in comparison_rows
    )
    group_ids = {
        row.get("v0_candidate_group_id", "")
        for row in usable_rows
        if row.get("v0_candidate_group_id", "")
    }
    passed = (
        len(input_rows) == 26
        and len(usable_rows) == 25
        and len(input_rows) - len(usable_rows) == 1
        and len(comparison_rows) == 25
        and len(gate_audit_rows) == 1
        and gate_audit_status == EXPECTED_GATE_AUDIT
        and len(rule_rows) == 23
        and len(output_contract_rows) == 16
        and rule_all_disallowed
        and output_all_generated_false
        and output_all_scoring_disallowed
        and all_auth_false
        and all_included
        and group_ids == {candidate_group_id}
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "input_gate_csv": str(args.gate_csv),
        "input_gate_audit_csv": str(args.gate_audit_csv),
        "input_row_count": len(input_rows),
        "usable_input_row_count": len(usable_rows),
        "review_only_input_row_count": len(input_rows) - len(usable_rows),
        "output_comparison_row_count": len(comparison_rows),
        "baseline_reference_row_count": len(usable_rows),
        "rule_contract_row_count": len(rule_rows),
        "output_contract_row_count": len(output_contract_rows),
        "rule_contract_all_scoring_disallowed": str(rule_all_disallowed),
        "output_contract_all_generated_false": str(output_all_generated_false),
        "output_contract_all_scoring_disallowed": str(
            output_all_scoring_disallowed
        ),
        "candidate_group_id": candidate_group_id,
        "ability_score_generated": "False",
        "ability_rank_generated": "False",
        "ability_class_generated": "False",
        "thci_scoring_authorized": "False",
        "radar_scoring_authorized": "False",
        "final_hiking_risk_scoring_authorized": "False",
        "zero_fallback_used": "False",
        "audit_conclusion": PASS_CONCLUSION if passed else FAIL_CONCLUSION,
    }


def render_activity_table(rows: list[dict[str, Any]]) -> str:
    fields = [
        "activity_id_short",
        "candidate_duration_min_per_km",
        "duration_min_per_km_delta_from_median",
        "candidate_median_speed_kmh",
        "median_speed_kmh_delta_from_median",
        "candidate_gain_rate_m_per_hour",
        "gain_rate_m_per_hour_delta_from_median",
        "heart_rate_bpm_median",
        "relative_humidity_pct",
        "precipitation_mm",
        "wind_gust_ms",
        "uv_index",
        "descriptive_performance_context",
        "descriptive_weather_context",
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
    input_rows: list[dict[str, str]],
    usable_rows: list[dict[str, str]],
    summary: dict[str, Any],
    comparison_rows: list[dict[str, Any]],
) -> str:
    cards = [
        ("input activities", len(input_rows)),
        ("usable activities", len(usable_rows)),
        ("review-only", len(input_rows) - len(usable_rows)),
        ("baseline reference rows", len(usable_rows)),
        (
            "median duration min/km",
            summary["duration_min_per_km_median"],
        ),
        ("median speed km/h", summary["median_speed_kmh_median"]),
        (
            "median gain rate m/h",
            summary["gain_rate_m_per_hour_median"],
        ),
    ]
    card_html = "".join(
        f'<div class="card"><strong>{html.escape(str(value))}</strong>'
        f"<span>{html.escape(label)}</span></div>"
        for label, value in cards
    )
    summary_rows = "".join(
        "<tr>"
        f"<td>{html.escape(prefix)}</td>"
        + "".join(
            f"<td>{html.escape(str(summary[f'{prefix}_{stat}']))}</td>"
            for stat in ("min", "p25", "median", "p75", "max")
        )
        + "</tr>"
        for prefix in METRICS
    )
    weather_rows = "".join(
        f"<li>{html.escape(label)}: {summary[field]}</li>"
        for label, field in [
            ("high humidity", "high_humidity_observed_count"),
            ("rain observed", "rain_observed_count"),
            ("high UV", "high_uv_observed_count"),
            ("wind gust observed", "wind_gust_observed_count"),
        ]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>IB3 Route-Normalized Performance Comparison Smoke</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2933; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }}
.card {{ border: 1px solid #d8dee4; border-radius: 8px; padding: 12px; background: #f8fafc; }}
.card strong {{ display: block; font-size: 24px; }}
.card span {{ color: #52606d; font-size: 12px; }}
.note {{ background: #fff8dc; border-left: 4px solid #d4a72c; padding: 12px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 12px; margin-top: 12px; }}
th, td {{ border: 1px solid #d8dee4; padding: 6px; text-align: right; }}
th:first-child, td:first-child, th:nth-last-child(-n+2), td:nth-last-child(-n+2) {{ text-align: left; }}
th {{ background: #eef2f6; position: sticky; top: 0; }}
</style>
</head>
<body>
<h1>IB3 Route-Normalized Performance Comparison Smoke</h1>
<p class="note"><strong>This report is a descriptive route-normalized comparison smoke only.</strong><br>
It does not compute ability scores, ability rankings, ability classes, THCI scores, radar scores, or final hiking risk scores.<br>
Below/above median describes observed sample performance only; it is not a personal ability judgment.<br>
Weather context is explanatory context only, not a penalty.<br>
Raw weather numeric fields are unavailable in the gate input and remain blank; weather flags are used only for descriptive counts.</p>
<div class="cards">{card_html}</div>
<h2>Baseline reference table</h2>
<table>
<thead><tr><th>metric</th><th>min</th><th>p25</th><th>median</th><th>p75</th><th>max</th></tr></thead>
<tbody>{summary_rows}</tbody>
</table>
<h2>Weather context counts</h2>
<ul>{weather_rows}</ul>
<h2>Activity comparison table</h2>
{render_activity_table(comparison_rows)}
</body>
</html>
"""


def main() -> int:
    args = parse_args()
    input_rows = read_csv(args.gate_csv)
    gate_audit_rows = read_csv(args.gate_audit_csv)
    rule_rows = read_csv(args.rule_contract_csv)
    output_contract_rows = read_csv(args.output_contract_csv)

    usable_rows = [
        row
        for row in input_rows
        if str(row.get("v0_usability_gate", "")).strip().upper()
        in SUPPORTED_USABLE_GATES
    ]
    candidate_groups = {
        row.get("v0_candidate_group_id", "")
        for row in usable_rows
        if row.get("v0_candidate_group_id", "")
    }
    if len(candidate_groups) != 1:
        raise ValueError(
            f"Expected one usable candidate group, found: {sorted(candidate_groups)}"
        )
    candidate_group_id = next(iter(candidate_groups))

    summaries = {
        name: metric_summary(usable_rows, field)
        for name, field in METRICS.items()
    }
    summary = build_summary(
        input_rows, usable_rows, candidate_group_id, summaries
    )
    comparison_rows = build_comparison_rows(usable_rows, summaries)
    audit = build_audit(
        args,
        input_rows,
        usable_rows,
        comparison_rows,
        gate_audit_rows,
        rule_rows,
        output_contract_rows,
        candidate_group_id,
    )

    comparison_csv = (
        args.out_root / "activity_route_normalized_comparison_smoke.csv"
    )
    summary_csv = (
        args.out_root / "route_normalized_baseline_reference_summary.csv"
    )
    audit_csv = args.out_root / "route_normalized_comparison_smoke_audit.csv"
    report_html = args.out_root / "route_normalized_comparison_smoke_report.html"
    write_csv(comparison_csv, comparison_rows, COMPARISON_FIELDS)
    write_csv(summary_csv, [summary], SUMMARY_FIELDS)
    write_csv(audit_csv, [audit], list(audit))
    report_html.write_text(
        build_report(input_rows, usable_rows, summary, comparison_rows),
        encoding="utf-8",
    )

    print("IB3 route-normalized performance comparison smoke")
    for field in [
        "input_row_count",
        "usable_input_row_count",
        "review_only_input_row_count",
        "baseline_reference_row_count",
        "output_comparison_row_count",
        "candidate_group_id",
        "audit_conclusion",
    ]:
        print(f"{field}: {audit[field]}")
    print(
        "median_duration_min_per_km:",
        summary["duration_min_per_km_median"],
    )
    print("median_speed_kmh:", summary["median_speed_kmh_median"])
    print(
        "median_gain_rate_m_per_hour:",
        summary["gain_rate_m_per_hour_median"],
    )
    print("comparison_csv:", comparison_csv)
    print("summary_csv:", summary_csv)
    print("audit_csv:", audit_csv)
    print("report_html:", report_html)
    return 0 if audit["audit_conclusion"] == PASS_CONCLUSION else 1


if __name__ == "__main__":
    raise SystemExit(main())
