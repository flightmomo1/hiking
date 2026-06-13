from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd


SCHEMA_VERSION = "ib3w_representative_environment_features_v1"

DEFAULT_ADAPTER_ROOT = Path("outputs/ib3w_activity_environment_window_adapter_v1")
DEFAULT_POLICY_CSV = Path(
    "outputs/ib3w_station_representativeness_policy_v1/"
    "station_representativeness_policy_review.csv"
)
DEFAULT_OUT_DIR = Path("outputs/ib3w_representative_environment_features_v1")

CONTEXT_VARIABLES = [
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

VALUE_COLUMNS = ["value_min", "value_max", "value_mean", "value_sum"]
COUNT_COLUMNS = [
    "obs_count_total_window",
    "obs_count_nonnull",
    "obs_count_null",
    "obs_count_zero",
    "obs_count_positive",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build IB3W representative environment features v1."
    )
    parser.add_argument("--adapter-root", type=Path, default=DEFAULT_ADAPTER_ROOT)
    parser.add_argument("--policy-csv", type=Path, default=DEFAULT_POLICY_CSV)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def bool_true_count(series: pd.Series) -> int:
    return int(series.astype(str).str.strip().str.lower().eq("true").sum())


def bool_true_mask(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().eq("true")


def to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def first_nonblank(df: pd.DataFrame, column: str) -> str:
    if column not in df.columns:
        return ""
    values = df[column].dropna().astype(str).str.strip()
    values = values[values.ne("")]
    return values.iloc[0] if len(values) else ""


def join_nonblank(values: pd.Series) -> str:
    clean = values.dropna().astype(str).str.strip()
    clean = clean[clean.ne("")]
    return "|".join(sorted(clean.unique()))


def read_policy(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"policy CSV not found: {path}")

    df = pd.read_csv(path, dtype={"station_id": str})

    required = [
        "station_id",
        "station_name",
        "station_policy_class",
        "selection_action",
        "eligible_for_mountain_representative_selection",
        "station_rank_by_distance",
        "nearest_activity_dist_m",
        "nlsc_station_elevation_m",
        "station_elevation_confidence",
    ]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"policy CSV missing columns: {missing}")

    return df


def find_adapter_outputs(root: Path) -> list[Path]:
    if not root.exists():
        raise FileNotFoundError(f"adapter root not found: {root}")

    paths = sorted(root.rglob("activity_environment_window_adapter_output.csv"))
    if not paths:
        raise FileNotFoundError(
            f"No activity_environment_window_adapter_output.csv found under: {root}"
        )
    return paths


def read_adapter_outputs(root: Path) -> pd.DataFrame:
    paths = find_adapter_outputs(root)
    frames = []

    for path in paths:
        df = pd.read_csv(path, dtype={"station_id": str})
        required = [
            "output_case",
            "activity_id",
            "context_variable",
            "context_status",
            "audit_status",
            "station_id",
            "station_name",
            "observed_values_available",
            "zero_fallback_used",
        ]
        missing = [column for column in required if column not in df.columns]
        if missing:
            raise ValueError(f"adapter output missing columns {missing}: {path}")

        for column in VALUE_COLUMNS + COUNT_COLUMNS:
            if column not in df.columns:
                df[column] = pd.NA

        for column in [
            "case_id",
            "activity_source_type",
            "activity_source_path",
            "activity_start_time_utc",
            "activity_end_time_utc",
            "activity_duration_min",
            "timestamp_epoch_used",
            "missingness_reason",
        ]:
            if column not in df.columns:
                df[column] = ""

        df["source_adapter_output_csv"] = str(path)
        frames.append(df)

    return pd.concat(frames, ignore_index=True)


def attach_policy(adapter: pd.DataFrame, policy: pd.DataFrame) -> pd.DataFrame:
    policy_cols = [
        "station_id",
        "station_policy_class",
        "selection_action",
        "eligible_for_mountain_representative_selection",
        "station_rank_by_distance",
        "nearest_activity_dist_m",
        "nlsc_station_elevation_m",
        "station_elevation_confidence",
    ]

    merged = adapter.merge(
        policy[policy_cols],
        on="station_id",
        how="left",
        suffixes=("", "_policy"),
    )

    return merged


def observed_rows(df: pd.DataFrame) -> pd.DataFrame:
    observed_available = bool_true_mask(df["observed_values_available"])
    return df[df["context_status"].eq("OBSERVED") & observed_available].copy()


def aggregate_variable(primary_rows: pd.DataFrame, variable: str) -> dict[str, Any]:
    rows = primary_rows[primary_rows["context_variable"].eq(variable)].copy()
    obs = observed_rows(rows)

    result: dict[str, Any] = {
        f"{variable}_primary_row_count": int(len(rows)),
        f"{variable}_primary_station_count": int(
            rows["station_id"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().nunique()
        ),
        f"{variable}_primary_observed_station_count": int(
            obs["station_id"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().nunique()
        ),
        f"{variable}_primary_missing_station_count": int(
            rows[rows["context_status"].eq("MISSING")]["station_id"]
            .dropna()
            .astype(str)
            .str.strip()
            .replace("", pd.NA)
            .dropna()
            .nunique()
        ),
        f"{variable}_primary_observed_any": bool(len(obs) > 0),
        f"{variable}_primary_context_status_set": join_nonblank(rows["context_status"]),
        f"{variable}_primary_audit_status_set": join_nonblank(rows["audit_status"]),
        f"{variable}_primary_missingness_reason_set": join_nonblank(
            rows["missingness_reason"] if "missingness_reason" in rows.columns else pd.Series(dtype=str)
        ),
        f"{variable}_obs_count_total_window_sum": int(
            to_numeric(rows["obs_count_total_window"]).fillna(0).sum()
        ),
        f"{variable}_obs_count_nonnull_sum": int(
            to_numeric(rows["obs_count_nonnull"]).fillna(0).sum()
        ),
        f"{variable}_obs_count_null_sum": int(
            to_numeric(rows["obs_count_null"]).fillna(0).sum()
        ),
        f"{variable}_obs_count_zero_sum": int(
            to_numeric(rows["obs_count_zero"]).fillna(0).sum()
        ),
        f"{variable}_obs_count_positive_sum": int(
            to_numeric(rows["obs_count_positive"]).fillna(0).sum()
        ),
    }

    if len(obs) == 0:
        result.update(
            {
                f"{variable}_primary_value_min": "",
                f"{variable}_primary_value_max": "",
                f"{variable}_primary_value_mean_of_station_means": "",
                f"{variable}_primary_value_sum_of_station_sums": "",
            }
        )
        return result

    value_min = to_numeric(obs["value_min"])
    value_max = to_numeric(obs["value_max"])
    value_mean = to_numeric(obs["value_mean"])
    value_sum = to_numeric(obs["value_sum"])

    result.update(
        {
            f"{variable}_primary_value_min": (
                round(float(value_min.min()), 4) if value_min.notna().any() else ""
            ),
            f"{variable}_primary_value_max": (
                round(float(value_max.max()), 4) if value_max.notna().any() else ""
            ),
            f"{variable}_primary_value_mean_of_station_means": (
                round(float(value_mean.mean()), 4) if value_mean.notna().any() else ""
            ),
            f"{variable}_primary_value_sum_of_station_sums": (
                round(float(value_sum.sum()), 4) if value_sum.notna().any() else ""
            ),
        }
    )

    return result


def feature_status(primary_rows: pd.DataFrame) -> str:
    if len(primary_rows) == 0:
        return "NO_PRIMARY_REPRESENTATIVE_ROWS"

    observed = observed_rows(primary_rows)
    if len(observed) == 0:
        return "PRIMARY_REPRESENTATIVE_ROWS_ALL_MISSING"

    missing_count = int(primary_rows["context_status"].eq("MISSING").sum())
    if missing_count > 0:
        return "PRIMARY_REPRESENTATIVE_FEATURES_AVAILABLE_PARTIAL"

    return "PRIMARY_REPRESENTATIVE_FEATURES_AVAILABLE_FULL"


def build_activity_features(merged: pd.DataFrame, policy: pd.DataFrame) -> pd.DataFrame:
    primary_policy = policy[
        policy["station_policy_class"].eq("PRIMARY_MOUNTAIN_REPRESENTATIVE_CANDIDATE")
        & bool_true_mask(policy["eligible_for_mountain_representative_selection"])
    ].copy()

    primary_station_ids = sorted(primary_policy["station_id"].astype(str).tolist())
    primary_station_names = sorted(primary_policy["station_name"].astype(str).tolist())

    rows = []
    group_cols = ["output_case", "activity_id"]

    for (output_case, activity_id), group in merged.groupby(group_cols, dropna=False, sort=True):
        primary_rows = group[group["station_id"].astype(str).isin(primary_station_ids)].copy()

        primary_observed = observed_rows(primary_rows)
        primary_missing = primary_rows[primary_rows["context_status"].eq("MISSING")]

        out: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "output_case": output_case,
            "case_id": first_nonblank(group, "case_id"),
            "activity_id": activity_id,
            "activity_source_type": first_nonblank(group, "activity_source_type"),
            "activity_source_path": first_nonblank(group, "activity_source_path"),
            "activity_start_time_utc": first_nonblank(group, "activity_start_time_utc"),
            "activity_end_time_utc": first_nonblank(group, "activity_end_time_utc"),
            "activity_duration_min": first_nonblank(group, "activity_duration_min"),
            "timestamp_epoch_used": first_nonblank(group, "timestamp_epoch_used"),
            "source_adapter_output_csv": first_nonblank(group, "source_adapter_output_csv"),
            "primary_candidate_station_ids": "|".join(primary_station_ids),
            "primary_candidate_station_names": "|".join(primary_station_names),
            "primary_candidate_station_count_policy": int(len(primary_station_ids)),
            "primary_station_count_present_in_activity_window": int(
                primary_rows["station_id"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().nunique()
            ),
            "primary_row_count": int(len(primary_rows)),
            "primary_observed_row_count": int(len(primary_observed)),
            "primary_missing_row_count": int(len(primary_missing)),
            "primary_context_status_set": join_nonblank(primary_rows["context_status"]),
            "primary_audit_status_set": join_nonblank(primary_rows["audit_status"]),
            "representative_feature_status": feature_status(primary_rows),
            "zero_fallback_true_count": bool_true_count(group["zero_fallback_used"]),
            "zero_fallback_used": False,
            "feature_notes": (
                "Primary representative features aggregate only stations selected by "
                "IB3W station representativeness policy. Missing values remain missing; "
                "observed zero remains raw observed zero."
            ),
        }

        for variable in CONTEXT_VARIABLES:
            out.update(aggregate_variable(primary_rows, variable))

        rows.append(out)

    return pd.DataFrame(rows)


def build_summary(features: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for status, group in features.groupby(
        "representative_feature_status", dropna=False, sort=True
    ):
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "summary_type": "representative_feature_status",
                "summary_key": status,
                "activity_count": int(len(group)),
                "zero_fallback_true_count": int(
                    to_numeric(group["zero_fallback_true_count"]).fillna(0).sum()
                ),
            }
        )

    for output_case, group in features.groupby("output_case", dropna=False, sort=True):
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "summary_type": "output_case",
                "summary_key": output_case,
                "activity_count": int(len(group)),
                "zero_fallback_true_count": int(
                    to_numeric(group["zero_fallback_true_count"]).fillna(0).sum()
                ),
            }
        )

    rows.append(
        {
            "schema_version": SCHEMA_VERSION,
            "summary_type": "overall",
            "summary_key": "ALL_ACTIVITIES",
            "activity_count": int(len(features)),
            "zero_fallback_true_count": int(
                to_numeric(features["zero_fallback_true_count"]).fillna(0).sum()
            ),
        }
    )

    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()

    policy = read_policy(args.policy_csv)
    adapter = read_adapter_outputs(args.adapter_root)
    merged = attach_policy(adapter, policy)

    features = build_activity_features(merged, policy)
    summary = build_summary(features)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    features_csv = args.out_dir / "activity_representative_environment_features.csv"
    summary_csv = args.out_dir / "activity_representative_environment_features_summary.csv"

    features.to_csv(features_csv, index=False, encoding="utf-8-sig")
    summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")

    print("IB3W representative environment features v1 written")
    print("features_csv:", features_csv)
    print("summary_csv:", summary_csv)
    print()
    print("summary:")
    print(summary.to_string(index=False))
    print()
    print("feature_status_distribution:")
    print(
        features.groupby("representative_feature_status")
        .size()
        .reset_index(name="activity_count")
        .sort_values("activity_count", ascending=False)
        .to_string(index=False)
    )
    print()
    print("selected feature columns:")
    selected_cols = [
        "output_case",
        "activity_id",
        "primary_candidate_station_ids",
        "primary_station_count_present_in_activity_window",
        "primary_observed_row_count",
        "primary_missing_row_count",
        "representative_feature_status",
        "precipitation_mm_primary_observed_station_count",
        "precipitation_mm_primary_value_mean_of_station_means",
        "temperature_c_primary_observed_station_count",
        "temperature_c_primary_value_mean_of_station_means",
        "relative_humidity_pct_primary_observed_station_count",
        "relative_humidity_pct_primary_value_mean_of_station_means",
        "wind_speed_ms_primary_observed_station_count",
        "wind_speed_ms_primary_value_max",
        "zero_fallback_true_count",
    ]
    print(features[selected_cols].to_string(index=False))


if __name__ == "__main__":
    main()
