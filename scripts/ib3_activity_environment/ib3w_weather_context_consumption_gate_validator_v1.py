from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "ib3w_weather_context_consumption_gate_validator_v1"

REQUIRED_POLICY_GATES = {
    "ALLOW_CONTEXT_ONLY",
    "ALLOW_PROXY_REVIEW_ONLY",
    "BLOCK_SCORE_WEATHER_UNAVAILABLE",
    "BLOCK_SCORE_ZERO_FALLBACK",
    "BLOCK_SCORE_UNSUPPORTED_DIRECT_CLAIM",
}

WEATHER_VARIABLES = [
    "precipitation_mm",
    "precipitation_10min_mm",
    "precipitation_1hr_mm",
    "temperature_c",
    "relative_humidity_pct",
    "wind_speed_ms",
    "wind_direction_deg",
    "pressure_hpa",
    "visibility_m",
    "weather",
]

UNSUPPORTED_DIRECT_VARIABLES_REQUIRING_REVIEW = {
    "precipitation_10min_mm",
    "precipitation_1hr_mm",
    "visibility_m",
    "weather",
}


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


def to_bool(value: Any) -> bool:
    if value is None:
        return False

    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y", "t"}


def pipe_join(values: list[str]) -> str:
    clean = [v for v in values if v]
    return "|".join(clean)


def load_policy_gate_values(policy_rows: list[dict[str, str]]) -> set[str]:
    return {row.get("consumption_gate", "").strip() for row in policy_rows if row.get("consumption_gate")}


def get_policy_row(policy_rows: list[dict[str, str]], gate_case: str) -> dict[str, str]:
    for row in policy_rows:
        if row.get("gate_case", "").strip() == gate_case:
            return row
    return {}


def observed_variables(feature_row: dict[str, str]) -> list[str]:
    observed: list[str] = []

    for variable in WEATHER_VARIABLES:
        observed_any_col = f"{variable}_primary_observed_any"
        observed_station_count_col = f"{variable}_primary_observed_station_count"
        nonnull_count_col = f"{variable}_obs_count_nonnull_sum"

        if to_bool(feature_row.get(observed_any_col)):
            observed.append(variable)
            continue

        if to_int(feature_row.get(observed_station_count_col)) > 0:
            observed.append(variable)
            continue

        if to_int(feature_row.get(nonnull_count_col)) > 0:
            observed.append(variable)
            continue

    return observed


def missing_variables(feature_row: dict[str, str], observed: list[str]) -> list[str]:
    observed_set = set(observed)
    missing: list[str] = []

    for variable in WEATHER_VARIABLES:
        if variable in observed_set:
            continue

        row_count_col = f"{variable}_primary_row_count"
        missing_station_count_col = f"{variable}_primary_missing_station_count"
        null_count_col = f"{variable}_obs_count_null_sum"

        if (
            to_int(feature_row.get(row_count_col)) > 0
            or to_int(feature_row.get(missing_station_count_col)) > 0
            or to_int(feature_row.get(null_count_col)) > 0
            or variable in WEATHER_VARIABLES
        ):
            missing.append(variable)

    return missing


def evaluate_gate(
    feature_row: dict[str, str],
    policy_rows: list[dict[str, str]],
) -> dict[str, Any]:
    representative_status = feature_row.get("representative_feature_status", "").strip()
    zero_fallback_true_count = to_int(feature_row.get("zero_fallback_true_count"))
    zero_fallback_used = to_bool(feature_row.get("zero_fallback_used"))

    primary_observed_row_count = to_int(feature_row.get("primary_observed_row_count"))
    primary_missing_row_count = to_int(feature_row.get("primary_missing_row_count"))
    primary_row_count = to_int(feature_row.get("primary_row_count"))
    primary_station_count = to_int(feature_row.get("primary_station_count_present_in_activity_window"))

    available_vars = observed_variables(feature_row)
    missing_vars = missing_variables(feature_row, available_vars)

    unsupported_observed = [
        v for v in available_vars
        if v in UNSUPPORTED_DIRECT_VARIABLES_REQUIRING_REVIEW
    ]

    if zero_fallback_true_count > 0 or zero_fallback_used:
        gate_case = "zero_fallback_detected"
        gate = "BLOCK_SCORE_ZERO_FALLBACK"
        reason = "zero_fallback_true_count greater than 0 or zero_fallback_used is true; downstream consumption is blocked."
    elif representative_status == "NO_PRIMARY_REPRESENTATIVE_ROWS":
        gate_case = "no_primary_representative_rows"
        gate = "BLOCK_SCORE_WEATHER_UNAVAILABLE"
        reason = "No primary representative station rows; weather evidence is unavailable and must not be treated as benign weather."
    elif representative_status == "PRIMARY_REPRESENTATIVE_ROWS_ALL_MISSING":
        gate_case = "all_primary_rows_missing"
        gate = "BLOCK_SCORE_WEATHER_UNAVAILABLE"
        reason = "Primary representative rows exist but all relevant values are missing; downstream score consumption is blocked."
    elif primary_row_count > 0 and primary_observed_row_count == 0:
        gate_case = "all_primary_rows_missing"
        gate = "BLOCK_SCORE_WEATHER_UNAVAILABLE"
        reason = "Primary representative row count is positive but observed row count is zero; downstream score consumption is blocked."
    elif unsupported_observed:
        gate_case = "unsupported_direct_observation_claim"
        gate = "BLOCK_SCORE_UNSUPPORTED_DIRECT_CLAIM"
        reason = "Unsupported direct weather variables appear observed under the current contract; policy review is required before downstream consumption."
    elif available_vars and missing_vars:
        gate_case = "partial_observed_variables"
        gate = "ALLOW_CONTEXT_ONLY"
        reason = "Some observed variables are available and zero fallback is absent; downstream may consume observed variables as context-only evidence."
    elif available_vars:
        gate_case = "observed_direct_context_available"
        gate = "ALLOW_CONTEXT_ONLY"
        reason = "Observed representative weather variables are available and zero fallback is absent; downstream may consume context-only evidence."
    else:
        gate_case = "all_primary_rows_missing"
        gate = "BLOCK_SCORE_WEATHER_UNAVAILABLE"
        reason = "No observed weather variables were derived; downstream score consumption is blocked."

    policy_row = get_policy_row(policy_rows, gate_case)

    context_allowed = gate == "ALLOW_CONTEXT_ONLY"
    proxy_review_only = gate == "ALLOW_PROXY_REVIEW_ONLY"
    score_allowed = False

    return {
        "schema_version": SCHEMA_VERSION,
        "source_schema_version": feature_row.get("schema_version", ""),
        "output_case": feature_row.get("output_case", ""),
        "case_id": feature_row.get("case_id", ""),
        "activity_id": feature_row.get("activity_id", ""),
        "activity_source_type": feature_row.get("activity_source_type", ""),
        "activity_start_time_utc": feature_row.get("activity_start_time_utc", ""),
        "activity_end_time_utc": feature_row.get("activity_end_time_utc", ""),
        "representative_feature_status": representative_status,
        "primary_candidate_station_ids": feature_row.get("primary_candidate_station_ids", ""),
        "primary_station_count_present_in_activity_window": primary_station_count,
        "primary_row_count": primary_row_count,
        "primary_observed_row_count": primary_observed_row_count,
        "primary_missing_row_count": primary_missing_row_count,
        "zero_fallback_true_count": zero_fallback_true_count,
        "zero_fallback_used": str(zero_fallback_used),
        "available_weather_variable_set": pipe_join(available_vars),
        "missing_weather_variable_set": pipe_join(missing_vars),
        "unsupported_direct_variable_observed_set": pipe_join(unsupported_observed),
        "consumption_gate_case": gate_case,
        "weather_context_consumption_gate": gate,
        "weather_context_consumption_gate_reason": reason,
        "policy_allowed_downstream_use": policy_row.get("allowed_downstream_use", ""),
        "policy_blocked_downstream_use": policy_row.get("blocked_downstream_use", ""),
        "context_consumption_allowed": str(context_allowed),
        "proxy_review_only": str(proxy_review_only),
        "downstream_score_allowed": str(score_allowed),
        "thci_authorization_status": "NOT_AUTHORIZED_BY_IB3W_GATE",
        "radar_authorization_status": "NOT_AUTHORIZED_BY_IB3W_GATE",
        "final_hiking_risk_authorization_status": "NOT_AUTHORIZED_BY_IB3W_GATE",
        "medical_diagnosis_authorization_status": "NOT_AUTHORIZED_BY_IB3W_GATE",
        "validator_notes": "Validator emits gate evidence only; it does not compute THCI, radar, final hiking risk, medical diagnosis, or behavior interpretation.",
    }


def build_summary(
    output_rows: list[dict[str, Any]],
    missing_required_policy_gates: list[str],
) -> dict[str, Any]:
    gate_counts = Counter(row["weather_context_consumption_gate"] for row in output_rows)
    status_counts = Counter(row["representative_feature_status"] for row in output_rows)

    zero_fallback_total = sum(to_int(row.get("zero_fallback_true_count")) for row in output_rows)

    return {
        "schema_version": SCHEMA_VERSION,
        "activity_count": len(output_rows),
        "allow_context_only_count": gate_counts.get("ALLOW_CONTEXT_ONLY", 0),
        "allow_proxy_review_only_count": gate_counts.get("ALLOW_PROXY_REVIEW_ONLY", 0),
        "block_weather_unavailable_count": gate_counts.get("BLOCK_SCORE_WEATHER_UNAVAILABLE", 0),
        "block_zero_fallback_count": gate_counts.get("BLOCK_SCORE_ZERO_FALLBACK", 0),
        "block_unsupported_direct_claim_count": gate_counts.get("BLOCK_SCORE_UNSUPPORTED_DIRECT_CLAIM", 0),
        "no_primary_representative_rows_count": status_counts.get("NO_PRIMARY_REPRESENTATIVE_ROWS", 0),
        "primary_representative_features_available_partial_count": status_counts.get("PRIMARY_REPRESENTATIVE_FEATURES_AVAILABLE_PARTIAL", 0),
        "primary_representative_features_available_full_count": status_counts.get("PRIMARY_REPRESENTATIVE_FEATURES_AVAILABLE_FULL", 0),
        "primary_representative_rows_all_missing_count": status_counts.get("PRIMARY_REPRESENTATIVE_ROWS_ALL_MISSING", 0),
        "zero_fallback_true_count_total": zero_fallback_total,
        "context_consumption_allowed_count": sum(1 for row in output_rows if row.get("context_consumption_allowed") == "True"),
        "downstream_score_allowed_count": sum(1 for row in output_rows if row.get("downstream_score_allowed") == "True"),
        "thci_authorized_count": 0,
        "radar_authorized_count": 0,
        "final_hiking_risk_authorized_count": 0,
        "medical_diagnosis_authorized_count": 0,
        "missing_required_policy_gates": pipe_join(missing_required_policy_gates),
        "validator_conclusion": "PASS_POLICY_PRESENT" if not missing_required_policy_gates else "FAIL_POLICY_MISSING_REQUIRED_GATES",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build IB3W weather context consumption gate validator evidence."
    )
    parser.add_argument(
        "--features-csv",
        default="outputs/ib3w_representative_environment_features_v1/activity_representative_environment_features.csv",
    )
    parser.add_argument(
        "--policy-csv",
        default="configs/weather_context/ib3w_weather_context_consumption_gate_policy_v1.csv",
    )
    parser.add_argument(
        "--out-root",
        default="outputs/ib3w_weather_context_consumption_gate_validator_v1",
    )
    args = parser.parse_args()

    features_csv = Path(args.features_csv)
    policy_csv = Path(args.policy_csv)
    out_root = Path(args.out_root)

    policy_rows = read_csv_rows(policy_csv)
    feature_rows = read_csv_rows(features_csv)

    policy_gate_values = load_policy_gate_values(policy_rows)
    missing_required_policy_gates = sorted(REQUIRED_POLICY_GATES - policy_gate_values)

    output_rows = [evaluate_gate(row, policy_rows) for row in feature_rows]
    summary_row = build_summary(output_rows, missing_required_policy_gates)

    gate_csv = out_root / "activity_weather_context_consumption_gate.csv"
    summary_csv = out_root / "activity_weather_context_consumption_gate_summary.csv"

    output_fields = [
        "schema_version",
        "source_schema_version",
        "output_case",
        "case_id",
        "activity_id",
        "activity_source_type",
        "activity_start_time_utc",
        "activity_end_time_utc",
        "representative_feature_status",
        "primary_candidate_station_ids",
        "primary_station_count_present_in_activity_window",
        "primary_row_count",
        "primary_observed_row_count",
        "primary_missing_row_count",
        "zero_fallback_true_count",
        "zero_fallback_used",
        "available_weather_variable_set",
        "missing_weather_variable_set",
        "unsupported_direct_variable_observed_set",
        "consumption_gate_case",
        "weather_context_consumption_gate",
        "weather_context_consumption_gate_reason",
        "policy_allowed_downstream_use",
        "policy_blocked_downstream_use",
        "context_consumption_allowed",
        "proxy_review_only",
        "downstream_score_allowed",
        "thci_authorization_status",
        "radar_authorization_status",
        "final_hiking_risk_authorization_status",
        "medical_diagnosis_authorization_status",
        "validator_notes",
    ]

    summary_fields = [
        "schema_version",
        "activity_count",
        "allow_context_only_count",
        "allow_proxy_review_only_count",
        "block_weather_unavailable_count",
        "block_zero_fallback_count",
        "block_unsupported_direct_claim_count",
        "no_primary_representative_rows_count",
        "primary_representative_features_available_partial_count",
        "primary_representative_features_available_full_count",
        "primary_representative_rows_all_missing_count",
        "zero_fallback_true_count_total",
        "context_consumption_allowed_count",
        "downstream_score_allowed_count",
        "thci_authorized_count",
        "radar_authorized_count",
        "final_hiking_risk_authorized_count",
        "medical_diagnosis_authorized_count",
        "missing_required_policy_gates",
        "validator_conclusion",
    ]

    write_csv_rows(gate_csv, output_rows, output_fields)
    write_csv_rows(summary_csv, [summary_row], summary_fields)

    print("IB3W weather context consumption gate validator v1 written")
    print(f"features_csv: {features_csv}")
    print(f"policy_csv: {policy_csv}")
    print(f"gate_csv: {gate_csv}")
    print(f"summary_csv: {summary_csv}")
    print("")
    print("summary:")
    for key in summary_fields:
        print(f"{key}: {summary_row.get(key, '')}")

    if missing_required_policy_gates:
        raise SystemExit("Required policy gates missing: " + ", ".join(missing_required_policy_gates))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
