from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "ib3m_weather_context_gate_consumer_smoke_v1"

NOT_AUTHORIZED = "NOT_AUTHORIZED_BY_IB3W_GATE"


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing input CSV: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv_rows(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def to_bool(value: Any) -> bool:
    if value is None:
        return False

    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y", "t"}


def to_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default

    text = str(value).strip()
    if text == "":
        return default

    try:
        return int(float(text))
    except ValueError:
        return default


def is_not_authorized(value: Any) -> bool:
    return str(value or "").strip() == NOT_AUTHORIZED


def evaluate_consumer_row(row: dict[str, str]) -> dict[str, Any]:
    gate = row.get("weather_context_consumption_gate", "").strip()
    activity_id = row.get("activity_id", "").strip()

    context_allowed = to_bool(row.get("context_consumption_allowed"))
    downstream_score_allowed = to_bool(row.get("downstream_score_allowed"))

    thci_not_authorized = is_not_authorized(row.get("thci_authorization_status"))
    radar_not_authorized = is_not_authorized(row.get("radar_authorization_status"))
    final_not_authorized = is_not_authorized(row.get("final_hiking_risk_authorization_status"))
    medical_not_authorized = is_not_authorized(row.get("medical_diagnosis_authorization_status"))

    score_authorization_clear = (
        not downstream_score_allowed
        and thci_not_authorized
        and radar_not_authorized
        and final_not_authorized
        and medical_not_authorized
    )

    if gate == "BLOCK_SCORE_WEATHER_UNAVAILABLE":
        expected_consumer_behavior = "REFUSE_SCORE_CONSUMPTION"
        allowed_consumer_use = "May preserve blocked weather-unavailable status for audit/explanation only."
        blocked_consumer_use = "Must not compute weather-sensitive score, THCI, radar, final hiking risk, or medical diagnosis."
        passed = score_authorization_clear
        reason = "Blocked weather-unavailable row must refuse all score consumers."
    elif gate == "BLOCK_SCORE_ZERO_FALLBACK":
        expected_consumer_behavior = "REFUSE_SCORE_CONSUMPTION"
        allowed_consumer_use = "May preserve zero-fallback QA failure for audit/explanation only."
        blocked_consumer_use = "Must not consume weather context because missing-to-zero fallback invalidates evidence."
        passed = score_authorization_clear
        reason = "Zero fallback row must refuse all score consumers."
    elif gate == "BLOCK_SCORE_UNSUPPORTED_DIRECT_CLAIM":
        expected_consumer_behavior = "REFUSE_SCORE_CONSUMPTION"
        allowed_consumer_use = "May preserve unsupported-claim QA failure for audit/explanation only."
        blocked_consumer_use = "Must not propagate unsupported direct weather/risk claim."
        passed = score_authorization_clear
        reason = "Unsupported direct claim must refuse all score consumers."
    elif gate == "ALLOW_CONTEXT_ONLY":
        expected_consumer_behavior = "ALLOW_NON_SCORING_CONTEXT_ONLY"
        allowed_consumer_use = "May pass observed weather variables as non-scoring context evidence."
        blocked_consumer_use = "Must not compute THCI, radar, final hiking risk, medical diagnosis, or weather-sensitive score."
        passed = context_allowed and score_authorization_clear
        reason = "Context-only row may be consumed only as non-scoring context."
    elif gate == "ALLOW_PROXY_REVIEW_ONLY":
        expected_consumer_behavior = "ALLOW_PROXY_REVIEW_ONLY"
        allowed_consumer_use = "May pass proxy evidence only as review-only context."
        blocked_consumer_use = "Must not compute score or claim direct observation."
        passed = score_authorization_clear
        reason = "Proxy review-only row must remain non-scoring."
    else:
        expected_consumer_behavior = "FAIL_UNKNOWN_GATE"
        allowed_consumer_use = "None."
        blocked_consumer_use = "Unknown gate must not be consumed."
        passed = False
        reason = f"Unknown weather_context_consumption_gate: {gate}"

    return {
        "schema_version": SCHEMA_VERSION,
        "activity_id": activity_id,
        "case_id": row.get("case_id", ""),
        "representative_feature_status": row.get("representative_feature_status", ""),
        "weather_context_consumption_gate": gate,
        "expected_consumer_behavior": expected_consumer_behavior,
        "smoke_pass": str(bool(passed)),
        "smoke_fail_reason": "" if passed else reason,
        "allowed_consumer_use": allowed_consumer_use,
        "blocked_consumer_use": blocked_consumer_use,
        "context_consumption_allowed": str(context_allowed),
        "downstream_score_allowed": str(downstream_score_allowed),
        "thci_authorization_status": row.get("thci_authorization_status", ""),
        "radar_authorization_status": row.get("radar_authorization_status", ""),
        "final_hiking_risk_authorization_status": row.get("final_hiking_risk_authorization_status", ""),
        "medical_diagnosis_authorization_status": row.get("medical_diagnosis_authorization_status", ""),
        "available_weather_variable_set": row.get("available_weather_variable_set", ""),
        "missing_weather_variable_set": row.get("missing_weather_variable_set", ""),
        "consumer_smoke_notes": "Smoke verifies downstream consumer behavior only; it does not compute THCI, radar, final hiking risk, medical diagnosis, behavior interpretation, or route risk.",
    }


def build_summary(result_rows: list[dict[str, Any]], validator_summary: dict[str, str]) -> dict[str, Any]:
    gate_counts = Counter(row["weather_context_consumption_gate"] for row in result_rows)
    behavior_counts = Counter(row["expected_consumer_behavior"] for row in result_rows)

    smoke_pass_count = sum(1 for row in result_rows if row["smoke_pass"] == "True")
    smoke_fail_count = sum(1 for row in result_rows if row["smoke_pass"] != "True")

    downstream_score_allowed_violation_count = sum(
        1 for row in result_rows
        if row["downstream_score_allowed"] == "True"
    )
    thci_authorization_violation_count = sum(
        1 for row in result_rows
        if row["thci_authorization_status"] != NOT_AUTHORIZED
    )
    radar_authorization_violation_count = sum(
        1 for row in result_rows
        if row["radar_authorization_status"] != NOT_AUTHORIZED
    )
    final_hiking_risk_authorization_violation_count = sum(
        1 for row in result_rows
        if row["final_hiking_risk_authorization_status"] != NOT_AUTHORIZED
    )
    medical_diagnosis_authorization_violation_count = sum(
        1 for row in result_rows
        if row["medical_diagnosis_authorization_status"] != NOT_AUTHORIZED
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "activity_count": len(result_rows),
        "smoke_pass_count": smoke_pass_count,
        "smoke_fail_count": smoke_fail_count,
        "block_weather_unavailable_count": gate_counts.get("BLOCK_SCORE_WEATHER_UNAVAILABLE", 0),
        "allow_context_only_count": gate_counts.get("ALLOW_CONTEXT_ONLY", 0),
        "allow_proxy_review_only_count": gate_counts.get("ALLOW_PROXY_REVIEW_ONLY", 0),
        "block_zero_fallback_count": gate_counts.get("BLOCK_SCORE_ZERO_FALLBACK", 0),
        "block_unsupported_direct_claim_count": gate_counts.get("BLOCK_SCORE_UNSUPPORTED_DIRECT_CLAIM", 0),
        "refuse_score_consumption_count": behavior_counts.get("REFUSE_SCORE_CONSUMPTION", 0),
        "allow_non_scoring_context_only_count": behavior_counts.get("ALLOW_NON_SCORING_CONTEXT_ONLY", 0),
        "allow_proxy_review_only_consumer_count": behavior_counts.get("ALLOW_PROXY_REVIEW_ONLY", 0),
        "downstream_score_allowed_violation_count": downstream_score_allowed_violation_count,
        "thci_authorization_violation_count": thci_authorization_violation_count,
        "radar_authorization_violation_count": radar_authorization_violation_count,
        "final_hiking_risk_authorization_violation_count": final_hiking_risk_authorization_violation_count,
        "medical_diagnosis_authorization_violation_count": medical_diagnosis_authorization_violation_count,
        "source_validator_activity_count": validator_summary.get("activity_count", ""),
        "source_validator_conclusion": validator_summary.get("validator_conclusion", ""),
        "consumer_smoke_conclusion": "PASS" if smoke_fail_count == 0 else "FAIL",
        "consumer_smoke_boundary": "No THCI, radar, final hiking risk, medical diagnosis, behavior interpretation, or route risk is computed.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="IB3M consumer smoke test for IB3W weather context gate outputs."
    )
    parser.add_argument(
        "--gate-csv",
        default="outputs/ib3w_weather_context_consumption_gate_validator_v1/activity_weather_context_consumption_gate.csv",
    )
    parser.add_argument(
        "--validator-summary-csv",
        default="outputs/ib3w_weather_context_consumption_gate_validator_v1/activity_weather_context_consumption_gate_summary.csv",
    )
    parser.add_argument(
        "--out-root",
        default="outputs/ib3m_weather_context_gate_consumer_smoke_v1",
    )
    args = parser.parse_args()

    gate_csv = Path(args.gate_csv)
    validator_summary_csv = Path(args.validator_summary_csv)
    out_root = Path(args.out_root)

    gate_rows = read_csv_rows(gate_csv)
    validator_summary_rows = read_csv_rows(validator_summary_csv)
    validator_summary = validator_summary_rows[0] if validator_summary_rows else {}

    result_rows = [evaluate_consumer_row(row) for row in gate_rows]
    summary = build_summary(result_rows, validator_summary)

    result_csv = out_root / "ib3m_weather_context_gate_consumer_smoke_results.csv"
    summary_csv = out_root / "ib3m_weather_context_gate_consumer_smoke_summary.csv"

    result_fields = [
        "schema_version",
        "activity_id",
        "case_id",
        "representative_feature_status",
        "weather_context_consumption_gate",
        "expected_consumer_behavior",
        "smoke_pass",
        "smoke_fail_reason",
        "allowed_consumer_use",
        "blocked_consumer_use",
        "context_consumption_allowed",
        "downstream_score_allowed",
        "thci_authorization_status",
        "radar_authorization_status",
        "final_hiking_risk_authorization_status",
        "medical_diagnosis_authorization_status",
        "available_weather_variable_set",
        "missing_weather_variable_set",
        "consumer_smoke_notes",
    ]

    summary_fields = [
        "schema_version",
        "activity_count",
        "smoke_pass_count",
        "smoke_fail_count",
        "block_weather_unavailable_count",
        "allow_context_only_count",
        "allow_proxy_review_only_count",
        "block_zero_fallback_count",
        "block_unsupported_direct_claim_count",
        "refuse_score_consumption_count",
        "allow_non_scoring_context_only_count",
        "allow_proxy_review_only_consumer_count",
        "downstream_score_allowed_violation_count",
        "thci_authorization_violation_count",
        "radar_authorization_violation_count",
        "final_hiking_risk_authorization_violation_count",
        "medical_diagnosis_authorization_violation_count",
        "source_validator_activity_count",
        "source_validator_conclusion",
        "consumer_smoke_conclusion",
        "consumer_smoke_boundary",
    ]

    write_csv_rows(result_csv, result_rows, result_fields)
    write_csv_rows(summary_csv, [summary], summary_fields)

    print("IB3M weather context gate consumer smoke v1 written")
    print(f"gate_csv: {gate_csv}")
    print(f"validator_summary_csv: {validator_summary_csv}")
    print(f"result_csv: {result_csv}")
    print(f"summary_csv: {summary_csv}")
    print("")
    print("summary:")
    for key in summary_fields:
        print(f"{key}: {summary.get(key, '')}")

    if summary["consumer_smoke_conclusion"] != "PASS":
        raise SystemExit("Consumer smoke failed; see output CSV for details.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
