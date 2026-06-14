from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ib3m_weather_gate_enforced_radar_consumer_smoke_v1 import (
    evaluate_row,
    read_csv_rows,
    to_bool,
    write_csv_rows,
)


SCHEMA_VERSION = "ib3m_weather_gate_enforced_radar_consumer_fixture_smoke_v1"


def evaluate_fixture(row: dict[str, str]) -> dict[str, Any]:
    result = evaluate_row(row)
    expected_allowed = to_bool(
        row.get("expected_radar_consumer_invocation_allowed")
    )
    actual_allowed = to_bool(result["radar_consumer_invocation_allowed"])
    actual_invoked = to_bool(result["actual_radar_consumer_invoked"])
    expectation_matches = expected_allowed == actual_allowed
    enforcement_violation = (
        to_bool(result["enforcement_violation"])
        or actual_invoked
        or not expectation_matches
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "fixture_case_id": row.get("fixture_case_id", ""),
        **result,
        "expected_radar_consumer_invocation_allowed": str(expected_allowed),
        "fixture_expectation_matches": str(expectation_matches),
        "fixture_enforcement_violation": str(enforcement_violation),
    }


def count_true(rows: list[dict[str, Any]], field: str) -> int:
    return sum(1 for row in rows if to_bool(row.get(field)))


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fixture_case_count = len(rows)
    expected_allowed_count = count_true(
        rows, "expected_radar_consumer_invocation_allowed"
    )
    actual_allowed_count = count_true(rows, "radar_consumer_invocation_allowed")
    dry_run_actual_invocation_count = count_true(
        rows, "actual_radar_consumer_invoked"
    )
    enforcement_violation_count = count_true(
        rows, "fixture_enforcement_violation"
    )
    expected_blocked_count = fixture_case_count - expected_allowed_count
    actual_blocked_count = fixture_case_count - actual_allowed_count

    passed = (
        fixture_case_count == 2
        and expected_allowed_count == 1
        and expected_blocked_count == 1
        and actual_allowed_count == 1
        and actual_blocked_count == 1
        and dry_run_actual_invocation_count == 0
        and enforcement_violation_count == 0
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "fixture_case_count": fixture_case_count,
        "expected_allowed_count": expected_allowed_count,
        "expected_blocked_count": expected_blocked_count,
        "actual_allowed_count": actual_allowed_count,
        "actual_blocked_count": actual_blocked_count,
        "dry_run_actual_invocation_count": dry_run_actual_invocation_count,
        "enforcement_violation_count": enforcement_violation_count,
        "fixture_smoke_conclusion": "PASS" if passed else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Positive and blocked fixtures for the IB3M radar gate wrapper."
    )
    parser.add_argument(
        "--fixture-csv",
        default=(
            "configs/weather_context/"
            "ib3m_weather_gate_enforced_consumer_fixture_cases_v1.csv"
        ),
    )
    parser.add_argument(
        "--out-root",
        default="outputs/ib3m_weather_gate_enforced_consumer_fixture_v1",
    )
    args = parser.parse_args()

    fixture_csv = Path(args.fixture_csv)
    out_root = Path(args.out_root)
    rows = [evaluate_fixture(row) for row in read_csv_rows(fixture_csv)]
    summary = build_summary(rows)

    results_csv = (
        out_root
        / "ib3m_weather_gate_enforced_radar_consumer_fixture_results.csv"
    )
    summary_csv = (
        out_root
        / "ib3m_weather_gate_enforced_radar_consumer_fixture_summary.csv"
    )
    result_fields = [
        "schema_version",
        "fixture_case_id",
        "case_id",
        "activity_id",
        "weather_context_consumption_gate",
        "downstream_score_allowed",
        "thci_authorization_status",
        "radar_authorization_status",
        "final_hiking_risk_authorization_status",
        "radar_consumer",
        "expected_radar_consumer_invocation_allowed",
        "radar_consumer_invocation_allowed",
        "radar_consumer_invocation_blocked",
        "radar_consumer_blocking_reasons",
        "actual_radar_consumer_invoked",
        "fixture_expectation_matches",
        "fixture_enforcement_violation",
        "enforcement_action",
    ]
    summary_fields = [
        "schema_version",
        "fixture_case_count",
        "expected_allowed_count",
        "expected_blocked_count",
        "actual_allowed_count",
        "actual_blocked_count",
        "dry_run_actual_invocation_count",
        "enforcement_violation_count",
        "fixture_smoke_conclusion",
    ]

    write_csv_rows(results_csv, rows, result_fields)
    write_csv_rows(summary_csv, [summary], summary_fields)

    print("IB3M weather gate enforced radar consumer fixture smoke v1")
    print(f"fixture_csv: {fixture_csv}")
    print(f"results_csv: {results_csv}")
    print(f"summary_csv: {summary_csv}")
    print("summary:")
    for field in summary_fields:
        print(f"{field}: {summary[field]}")

    return 0 if summary["fixture_smoke_conclusion"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
