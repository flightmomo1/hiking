from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "ib3m_weather_gate_enforced_radar_consumer_smoke_v1"
NOT_AUTHORIZED = "NOT_AUTHORIZED_BY_IB3W_GATE"
RADAR_CONSUMER = "scripts/thci_plot_radar_v1_0c.py"
BLOCKING_GATE_PREFIX = "BLOCK_SCORE_"


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing input CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def to_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "t"}


def is_not_authorized(value: Any) -> bool:
    return str(value or "").strip() == NOT_AUTHORIZED


def evaluate_row(row: dict[str, str]) -> dict[str, Any]:
    gate = str(row.get("weather_context_consumption_gate") or "").strip()
    downstream_score_allowed = to_bool(row.get("downstream_score_allowed"))
    thci_not_authorized = is_not_authorized(row.get("thci_authorization_status"))
    radar_not_authorized = is_not_authorized(row.get("radar_authorization_status"))
    final_risk_not_authorized = is_not_authorized(
        row.get("final_hiking_risk_authorization_status")
    )

    blocking_reasons: list[str] = []
    if gate.startswith(BLOCKING_GATE_PREFIX):
        blocking_reasons.append(f"blocking_weather_context_gate:{gate}")
    if not downstream_score_allowed:
        blocking_reasons.append("downstream_score_allowed_not_true")
    if thci_not_authorized:
        blocking_reasons.append("thci_not_authorized_by_ib3w_gate")
    if radar_not_authorized:
        blocking_reasons.append("radar_not_authorized_by_ib3w_gate")

    invocation_allowed = not blocking_reasons

    # This smoke verifies enforcement only. It never invokes the production radar consumer.
    actual_invoked = False
    enforcement_violation = actual_invoked and not invocation_allowed

    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": row.get("case_id", ""),
        "activity_id": row.get("activity_id", ""),
        "weather_context_consumption_gate": gate,
        "downstream_score_allowed": str(downstream_score_allowed),
        "thci_authorization_status": row.get("thci_authorization_status", ""),
        "radar_authorization_status": row.get("radar_authorization_status", ""),
        "final_hiking_risk_authorization_status": row.get(
            "final_hiking_risk_authorization_status", ""
        ),
        "final_hiking_risk_authorized_for_separate_consumer": str(
            not final_risk_not_authorized
        ),
        "radar_consumer": RADAR_CONSUMER,
        "radar_consumer_invocation_allowed": str(invocation_allowed),
        "radar_consumer_invocation_blocked": str(not invocation_allowed),
        "radar_consumer_blocking_reasons": "|".join(blocking_reasons),
        "actual_radar_consumer_invoked": str(actual_invoked),
        "enforcement_violation": str(enforcement_violation),
        "enforcement_action": (
            "BLOCK_RADAR_CONSUMER_INVOCATION"
            if not invocation_allowed
            else "ALLOW_RECORDED_NO_INVOCATION_IN_SMOKE"
        ),
    }


def count_true(rows: list[dict[str, Any]], field: str) -> int:
    return sum(1 for row in rows if to_bool(row.get(field)))


def count_authorized(rows: list[dict[str, Any]], field: str) -> int:
    return sum(1 for row in rows if not is_not_authorized(row.get(field)))


def build_summary(result_rows: list[dict[str, Any]]) -> dict[str, Any]:
    activity_count = len(result_rows)
    allowed_count = count_true(result_rows, "radar_consumer_invocation_allowed")
    blocked_count = count_true(result_rows, "radar_consumer_invocation_blocked")
    actual_invocation_count = count_true(
        result_rows, "actual_radar_consumer_invoked"
    )
    violation_count = count_true(result_rows, "enforcement_violation")

    thci_authorized_count = count_authorized(
        result_rows, "thci_authorization_status"
    )
    radar_authorized_count = count_authorized(
        result_rows, "radar_authorization_status"
    )
    final_risk_authorized_count = count_authorized(
        result_rows, "final_hiking_risk_authorization_status"
    )
    downstream_allowed_count = count_true(result_rows, "downstream_score_allowed")

    expected_current_result = (
        activity_count == 27
        and allowed_count == 0
        and blocked_count == activity_count
        and actual_invocation_count == 0
        and thci_authorized_count == 0
        and radar_authorized_count == 0
        and final_risk_authorized_count == 0
        and downstream_allowed_count == 0
        and violation_count == 0
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "activity_count": activity_count,
        "radar_consumer_invocation_allowed_count": allowed_count,
        "radar_consumer_invocation_blocked_count": blocked_count,
        "actual_radar_consumer_invocation_count": actual_invocation_count,
        "thci_authorized_count": thci_authorized_count,
        "radar_authorized_count": radar_authorized_count,
        "final_hiking_risk_authorized_count": final_risk_authorized_count,
        "downstream_score_allowed_count": downstream_allowed_count,
        "enforcement_violation_count": violation_count,
        "smoke_conclusion": "PASS" if expected_current_result else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enforce IB3W gate decisions before a hypothetical THCI radar consumer."
    )
    parser.add_argument(
        "--gate-csv",
        default=(
            "outputs/ib3w_weather_context_consumption_gate_validator_v1/"
            "activity_weather_context_consumption_gate.csv"
        ),
    )
    parser.add_argument(
        "--out-root",
        default="outputs/ib3m_weather_gate_enforced_consumer_v1",
    )
    args = parser.parse_args()

    gate_csv = Path(args.gate_csv)
    out_root = Path(args.out_root)
    gate_rows = read_csv_rows(gate_csv)
    result_rows = [evaluate_row(row) for row in gate_rows]
    summary = build_summary(result_rows)

    results_csv = (
        out_root / "ib3m_weather_gate_enforced_radar_consumer_smoke_results.csv"
    )
    summary_csv = (
        out_root / "ib3m_weather_gate_enforced_radar_consumer_smoke_summary.csv"
    )

    result_fields = [
        "schema_version",
        "case_id",
        "activity_id",
        "weather_context_consumption_gate",
        "downstream_score_allowed",
        "thci_authorization_status",
        "radar_authorization_status",
        "final_hiking_risk_authorization_status",
        "radar_consumer",
        "radar_consumer_invocation_allowed",
        "radar_consumer_invocation_blocked",
        "radar_consumer_blocking_reasons",
        "actual_radar_consumer_invoked",
        "enforcement_violation",
        "enforcement_action",
    ]
    summary_fields = [
        "schema_version",
        "activity_count",
        "radar_consumer_invocation_allowed_count",
        "radar_consumer_invocation_blocked_count",
        "actual_radar_consumer_invocation_count",
        "thci_authorized_count",
        "radar_authorized_count",
        "final_hiking_risk_authorized_count",
        "downstream_score_allowed_count",
        "enforcement_violation_count",
        "smoke_conclusion",
    ]

    write_csv_rows(results_csv, result_rows, result_fields)
    write_csv_rows(summary_csv, [summary], summary_fields)

    print("IB3M weather gate enforced radar consumer smoke v1")
    print(f"gate_csv: {gate_csv}")
    print(f"results_csv: {results_csv}")
    print(f"summary_csv: {summary_csv}")
    print("summary:")
    for field in summary_fields:
        print(f"{field}: {summary[field]}")

    return 0 if summary["smoke_conclusion"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
