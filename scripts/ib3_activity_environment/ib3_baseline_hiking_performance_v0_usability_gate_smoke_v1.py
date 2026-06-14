from __future__ import annotations

import argparse
import csv
import html
import math
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "ib3_baseline_hiking_performance_v0_usability_gate_smoke_v1"

DEFAULT_SMOKE_FEATURES_CSV = Path(
    "outputs/ib3_baseline_hiking_performance_model_smoke_v1/"
    "activity_baseline_performance_smoke_features.csv"
)
DEFAULT_SMOKE_AUDIT_CSV = Path(
    "outputs/ib3_baseline_hiking_performance_model_smoke_v1/"
    "activity_baseline_performance_smoke_audit.csv"
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
    "outputs/ib3_baseline_hiking_performance_v0_usability_gate_smoke_v1"
)

EXPECTED_SMOKE_AUDIT = "PASS_BASELINE_PERFORMANCE_SMOKE_DESCRIPTIVE_ONLY"
USABLE_GATE = "USABLE_FOR_V0_MODEL_SMOKE"
USABLE_GROUP = "qixing_lengshuikeng_full26_baseline_smoke"
PASS_CONCLUSION = "PASS_V0_USABILITY_GATE_SMOKE_ONLY"
FAIL_CONCLUSION = "FAIL_V0_USABILITY_GATE_SMOKE_CONTRACT_OR_INPUT"

OUTPUT_FIELDS = [
    "schema_version",
    "activity_id_short",
    "activity_id_full",
    "join_status",
    "duration_min",
    "route_dist_covered_m",
    "route_dist_covered_km",
    "candidate_duration_min_per_km",
    "candidate_median_speed_kmh",
    "candidate_gain_m_per_km",
    "candidate_duration_min_per_100m_gain",
    "candidate_gain_rate_m_per_hour",
    "heart_rate_available",
    "heart_rate_bpm_median",
    "candidate_hr_median_context",
    "candidate_weather_context_flags",
    "backend_use_analytics_ready_ratio",
    "calibration_review_required_ratio",
    "movement_review_required_ratio",
    "activity_performance_quality_flag",
    "candidate_data_quality_gate",
    "v0_candidate_group_id",
    "v0_usability_gate",
    "v0_usability_reasons",
    "v0_review_required",
    "v0_exclude_from_ability_estimate",
    "v0_gate_note",
    "ability_score_generated",
    "ability_rank_generated",
    "ability_class_generated",
    "thci_scoring_authorized",
    "radar_scoring_authorized",
    "final_hiking_risk_scoring_authorized",
    "authorization_note",
]

AUTHORIZATION_NOTE = (
    "Future model usability gate smoke only. No ability score, rank, class, "
    "THCI score, radar score, or final hiking risk score is generated or "
    "authorized."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify future IB3 model v0 activity usability."
    )
    parser.add_argument(
        "--smoke-features-csv", type=Path, default=DEFAULT_SMOKE_FEATURES_CSV
    )
    parser.add_argument(
        "--smoke-audit-csv", type=Path, default=DEFAULT_SMOKE_AUDIT_CSV
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


def is_ready_gate(value: Any) -> bool:
    return str(value or "").strip().upper().startswith("READY")


def classify_activity(row: dict[str, str]) -> tuple[str, list[str]]:
    join_status = str(row.get("join_status", "")).strip().upper()
    quality_gate = str(row.get("candidate_data_quality_gate", "")).strip()
    analytics_ratio = as_float(row.get("backend_use_analytics_ready_ratio"))
    calibration_ratio = as_float(row.get("calibration_review_required_ratio"))
    movement_ratio = as_float(row.get("movement_review_required_ratio"))
    duration_min = as_float(row.get("duration_min"))
    distance_m = as_float(row.get("route_dist_covered_m"))
    duration_per_km = as_float(row.get("candidate_duration_min_per_km"))

    reasons: list[str] = []
    if join_status != "MATCHED":
        reasons.append("JOIN_STATUS_NOT_MATCHED")
    if not is_ready_gate(quality_gate):
        reasons.append(
            f"DATA_QUALITY_GATE_NOT_READY__{quality_gate or 'MISSING'}"
        )
    if analytics_ratio is None:
        reasons.append("ANALYTICS_READY_RATIO_MISSING")
    elif analytics_ratio < 0.5:
        reasons.append("ANALYTICS_READY_RATIO_BELOW_0_5")
    if calibration_ratio is None:
        reasons.append("CALIBRATION_REVIEW_RATIO_MISSING")
    elif calibration_ratio > 0.5:
        reasons.append("CALIBRATION_REVIEW_RATIO_ABOVE_0_5")
    if movement_ratio is None:
        reasons.append("MOVEMENT_REVIEW_RATIO_MISSING")
    elif movement_ratio > 0.5:
        reasons.append("MOVEMENT_REVIEW_RATIO_ABOVE_0_5")
    if duration_min is None or duration_min <= 0:
        reasons.append("DURATION_MISSING_OR_NON_POSITIVE")
    if distance_m is None or distance_m <= 0:
        reasons.append("ROUTE_DISTANCE_MISSING_OR_NON_POSITIVE")
    if duration_per_km is None:
        reasons.append("ROUTE_NORMALIZED_DURATION_MISSING")

    # The primary outcome follows the requested gate priority. All applicable
    # reasons remain visible for review and audit.
    if join_status != "MATCHED":
        return "REVIEW_ONLY_JOIN_UNMATCHED", reasons
    if not is_ready_gate(quality_gate):
        return "REVIEW_ONLY_DATA_QUALITY", reasons
    if analytics_ratio is None or analytics_ratio < 0.5:
        return "REVIEW_ONLY_DATA_QUALITY", reasons
    if calibration_ratio is None or calibration_ratio > 0.5:
        return "REVIEW_ONLY_DATA_QUALITY", reasons
    if movement_ratio is None or movement_ratio > 0.5:
        return "REVIEW_ONLY_DATA_QUALITY", reasons
    if duration_min is None or duration_min <= 0:
        return "REVIEW_ONLY_MISSING_DURATION", reasons
    if distance_m is None or distance_m <= 0:
        return "REVIEW_ONLY_MISSING_ROUTE_DISTANCE", reasons
    if duration_per_km is None:
        return "REVIEW_ONLY_MISSING_ROUTE_NORMALIZED_DURATION", reasons
    return USABLE_GATE, ["ALL_V0_SMOKE_USABILITY_GATES_PASSED"]


def build_output_row(row: dict[str, str]) -> dict[str, Any]:
    gate, reasons = classify_activity(row)
    usable = gate == USABLE_GATE
    output = {field: row.get(field, "") for field in OUTPUT_FIELDS}
    output.update(
        {
            "schema_version": SCHEMA_VERSION,
            "v0_candidate_group_id": USABLE_GROUP if usable else "",
            "v0_usability_gate": gate,
            "v0_usability_reasons": "|".join(reasons),
            "v0_review_required": str(not usable),
            "v0_exclude_from_ability_estimate": str(not usable),
            "v0_gate_note": (
                "Passed future model v0 smoke usability checks and assigned to "
                "a candidate comparison group. USABLE does not indicate strong "
                "ability."
                if usable
                else "Retained as review-only evidence and excluded from any "
                "future ability estimate. REVIEW_ONLY does not indicate weak "
                "ability."
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
    return output


def serialize_distribution(counter: Counter[str]) -> str:
    return "|".join(f"{key}:{counter[key]}" for key in sorted(counter))


def build_audit(
    args: argparse.Namespace,
    input_rows: list[dict[str, str]],
    smoke_audit_rows: list[dict[str, str]],
    rule_rows: list[dict[str, str]],
    output_contract_rows: list[dict[str, str]],
    output_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    smoke_audit_status = (
        smoke_audit_rows[0].get("audit_conclusion", "")
        if len(smoke_audit_rows) == 1
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

    gate_distribution = Counter(
        str(row["v0_usability_gate"]) for row in output_rows
    )
    reason_distribution: Counter[str] = Counter()
    for row in output_rows:
        for reason in str(row["v0_usability_reasons"]).split("|"):
            if reason and reason != "ALL_V0_SMOKE_USABILITY_GATES_PASSED":
                reason_distribution[reason] += 1
    group_distribution = Counter(
        str(row["v0_candidate_group_id"])
        for row in output_rows
        if row["v0_candidate_group_id"]
    )

    usable_count = gate_distribution[USABLE_GATE]
    review_count = len(output_rows) - usable_count
    excluded_count = sum(
        str(row["v0_exclude_from_ability_estimate"]).lower() == "true"
        for row in output_rows
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
        for row in output_rows
        for field in auth_fields
    )
    gate_assignments_consistent = all(
        (
            row["v0_usability_gate"] == USABLE_GATE
            and row["v0_candidate_group_id"] == USABLE_GROUP
            and str(row["v0_review_required"]).lower() == "false"
            and str(row["v0_exclude_from_ability_estimate"]).lower() == "false"
        )
        or (
            row["v0_usability_gate"] != USABLE_GATE
            and not row["v0_candidate_group_id"]
            and str(row["v0_review_required"]).lower() == "true"
            and str(row["v0_exclude_from_ability_estimate"]).lower() == "true"
        )
        for row in output_rows
    )
    passed = (
        len(input_rows) == 26
        and len(output_rows) == 26
        and len(smoke_audit_rows) == 1
        and smoke_audit_status == EXPECTED_SMOKE_AUDIT
        and len(rule_rows) == 23
        and len(output_contract_rows) == 16
        and rule_all_disallowed
        and output_all_generated_false
        and output_all_scoring_disallowed
        and all_auth_false
        and usable_count + review_count == len(output_rows)
        and excluded_count == review_count
        and sum(group_distribution.values()) == usable_count
        and gate_assignments_consistent
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "input_smoke_features_csv": str(args.smoke_features_csv),
        "input_smoke_audit_csv": str(args.smoke_audit_csv),
        "input_rule_contract_csv": str(args.rule_contract_csv),
        "input_output_contract_csv": str(args.output_contract_csv),
        "input_row_count": len(input_rows),
        "output_row_count": len(output_rows),
        "rule_contract_row_count": len(rule_rows),
        "output_contract_row_count": len(output_contract_rows),
        "rule_contract_all_scoring_disallowed": str(rule_all_disallowed),
        "output_contract_all_generated_false": str(output_all_generated_false),
        "output_contract_all_scoring_disallowed": str(
            output_all_scoring_disallowed
        ),
        "usable_for_v0_model_smoke_count": usable_count,
        "review_only_count": review_count,
        "excluded_from_ability_estimate_count": excluded_count,
        "gate_distribution": serialize_distribution(gate_distribution),
        "review_reason_distribution": serialize_distribution(reason_distribution),
        "candidate_group_distribution": serialize_distribution(group_distribution),
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
        "duration_min",
        "route_dist_covered_km",
        "candidate_duration_min_per_km",
        "candidate_median_speed_kmh",
        "candidate_gain_rate_m_per_hour",
        "backend_use_analytics_ready_ratio",
        "calibration_review_required_ratio",
        "movement_review_required_ratio",
        "candidate_data_quality_gate",
        "v0_usability_gate",
        "v0_usability_reasons",
        "v0_candidate_group_id",
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
    output_rows: list[dict[str, Any]], audit: dict[str, Any]
) -> str:
    cards = [
        ("input activities", audit["input_row_count"]),
        ("usable for v0 smoke", audit["usable_for_v0_model_smoke_count"]),
        ("review-only", audit["review_only_count"]),
        (
            "excluded from ability estimate",
            audit["excluded_from_ability_estimate_count"],
        ),
        ("rule contract rows", audit["rule_contract_row_count"]),
        ("output contract rows", audit["output_contract_row_count"]),
    ]
    card_html = "".join(
        f'<div class="card"><strong>{html.escape(str(value))}</strong>'
        f"<span>{html.escape(label)}</span></div>"
        for label, value in cards
    )
    gates = Counter(str(row["v0_usability_gate"]) for row in output_rows)
    reasons: Counter[str] = Counter()
    for row in output_rows:
        for reason in str(row["v0_usability_reasons"]).split("|"):
            if reason and reason != "ALL_V0_SMOKE_USABILITY_GATES_PASSED":
                reasons[reason] += 1
    gate_items = "".join(
        f"<li><code>{html.escape(key)}</code>: {value}</li>"
        for key, value in sorted(gates.items())
    )
    reason_items = "".join(
        f"<li><code>{html.escape(key)}</code>: {value}</li>"
        for key, value in sorted(reasons.items())
    ) or "<li>None</li>"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>IB3 Baseline Hiking Performance v0 Usability Gate Smoke</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2933; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; }}
.card {{ border: 1px solid #d8dee4; border-radius: 8px; padding: 12px; background: #f8fafc; }}
.card strong {{ display: block; font-size: 24px; }}
.card span {{ color: #52606d; font-size: 12px; }}
.note {{ background: #fff8dc; border-left: 4px solid #d4a72c; padding: 12px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 12px; margin-top: 12px; }}
th, td {{ border: 1px solid #d8dee4; padding: 6px; text-align: right; }}
th:first-child, td:first-child, th:nth-last-child(-n+3), td:nth-last-child(-n+3) {{ text-align: left; }}
th {{ background: #eef2f6; position: sticky; top: 0; }}
code {{ font-size: 12px; }}
</style>
</head>
<body>
<h1>IB3 Baseline Hiking Performance v0 Usability Gate Smoke</h1>
<p class="note"><strong>This smoke report only classifies future model usability.</strong><br>
It does not compute ability scores, ability rankings, THCI scores, radar scores, or final hiking risk scores.<br>
READY / USABLE does not mean strong ability.<br>
REVIEW_ONLY does not mean weak ability.</p>
<div class="cards">{card_html}</div>
<h2>Gate distribution</h2>
<ul>{gate_items}</ul>
<h2>Review reason distribution</h2>
<ul>{reason_items}</ul>
<h2>Activity table</h2>
{render_activity_table(output_rows)}
</body>
</html>
"""


def main() -> int:
    args = parse_args()
    input_rows = read_csv(args.smoke_features_csv)
    smoke_audit_rows = read_csv(args.smoke_audit_csv)
    rule_rows = read_csv(args.rule_contract_csv)
    output_contract_rows = read_csv(args.output_contract_csv)

    output_rows = [build_output_row(row) for row in input_rows]
    audit = build_audit(
        args,
        input_rows,
        smoke_audit_rows,
        rule_rows,
        output_contract_rows,
        output_rows,
    )

    output_csv = args.out_root / "activity_v0_usability_gate_smoke.csv"
    audit_csv = args.out_root / "activity_v0_usability_gate_smoke_audit.csv"
    report_html = args.out_root / "activity_v0_usability_gate_smoke_report.html"
    write_csv(output_csv, output_rows, OUTPUT_FIELDS)
    write_csv(audit_csv, [audit], list(audit))
    report_html.write_text(build_report(output_rows, audit), encoding="utf-8")

    print("IB3 baseline hiking performance v0 usability gate smoke")
    for field in [
        "input_row_count",
        "output_row_count",
        "rule_contract_row_count",
        "output_contract_row_count",
        "rule_contract_all_scoring_disallowed",
        "output_contract_all_generated_false",
        "output_contract_all_scoring_disallowed",
        "usable_for_v0_model_smoke_count",
        "review_only_count",
        "excluded_from_ability_estimate_count",
        "gate_distribution",
        "review_reason_distribution",
        "candidate_group_distribution",
        "audit_conclusion",
    ]:
        print(f"{field}: {audit[field]}")
    print("output_csv:", output_csv)
    print("audit_csv:", audit_csv)
    print("report_html:", report_html)
    return 0 if audit["audit_conclusion"] == PASS_CONCLUSION else 1


if __name__ == "__main__":
    raise SystemExit(main())
