from __future__ import annotations

import argparse
import html
from pathlib import Path

import pandas as pd


SCHEMA_VERSION = "ib3w_weather_sensitive_feature_vector_v1"

DEFAULT_FEATURES_CSV = Path(
    "outputs/ib3w_representative_environment_features_v1/"
    "activity_representative_environment_features.csv"
)

DEFAULT_GATE_CSV = Path(
    "outputs/ib3w_weather_sensitive_feature_gate_v1/"
    "activity_weather_sensitive_feature_gate.csv"
)

DEFAULT_OUT_DIR = Path("outputs/ib3w_weather_sensitive_feature_vector_v1")

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build IB3W weather-sensitive feature vector v1."
    )
    parser.add_argument("--features-csv", type=Path, default=DEFAULT_FEATURES_CSV)
    parser.add_argument("--gate-csv", type=Path, default=DEFAULT_GATE_CSV)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def read_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    return pd.read_csv(path, dtype=str)


def str_value(row: pd.Series, col: str, default: str = "") -> str:
    value = row.get(col, default)
    if pd.isna(value):
        return default
    return str(value).strip()


def num_value(row: pd.Series, col: str):
    value = row.get(col, "")
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return pd.NA
    return float(parsed)


def int_value(row: pd.Series, col: str) -> int:
    value = num_value(row, col)
    if pd.isna(value):
        return 0
    return int(value)


def bool_value(row: pd.Series, col: str) -> bool:
    return str_value(row, col).lower() == "true"


def safe_ratio(numerator: float | int, denominator: float | int):
    if denominator is None or denominator == 0:
        return pd.NA
    return round(float(numerator) / float(denominator), 6)


def observed_station_count(row: pd.Series, variable: str) -> int:
    return int_value(row, f"{variable}_primary_observed_station_count")


def variable_available(row: pd.Series, variable: str) -> bool:
    return observed_station_count(row, variable) > 0


def numeric_if_available(row: pd.Series, variable: str, suffix: str):
    if not variable_available(row, variable):
        return pd.NA
    return num_value(row, f"{variable}_{suffix}")


def classify_vector_status(row: pd.Series) -> str:
    gate = str_value(row, "weather_sensitive_feature_gate")

    if gate == "BLOCK_ZERO_FALLBACK_QA_FAILED":
        return "WEATHER_FEATURE_VECTOR_BLOCKED_ZERO_FALLBACK"

    if gate == "WEATHER_FEATURE_UNAVAILABLE_DO_NOT_SCORE":
        return "WEATHER_FEATURE_VECTOR_UNAVAILABLE"

    if gate == "WEATHER_FEATURE_AVAILABLE_PARTIAL_SCORE_ALLOWED_FOR_OBSERVED_VARIABLES_ONLY":
        return "WEATHER_FEATURE_VECTOR_AVAILABLE_PARTIAL"

    if gate == "WEATHER_FEATURE_AVAILABLE_FULL_SCORE_ALLOWED":
        return "WEATHER_FEATURE_VECTOR_AVAILABLE_FULL"

    return "WEATHER_FEATURE_VECTOR_REVIEW_REQUIRED"


def classify_rain_observation_status(row: pd.Series, score_allowed: bool) -> str:
    if not score_allowed:
        return "BLOCKED_BY_GATE"

    precip_available = variable_available(row, "precipitation_mm")
    if not precip_available:
        return "RAIN_OBSERVATION_MISSING"

    positive_count = int_value(row, "precipitation_mm_obs_count_positive_sum")
    zero_count = int_value(row, "precipitation_mm_obs_count_zero_sum")
    precip_max = num_value(row, "precipitation_mm_primary_value_max")

    if positive_count > 0:
        return "OBSERVED_RAIN"

    if zero_count > 0 and not pd.isna(precip_max) and float(precip_max) == 0:
        return "OBSERVED_NO_RAIN"

    return "RAIN_OBSERVATION_PARTIAL_REVIEW"


def classify_moisture_context_status(row: pd.Series, score_allowed: bool) -> str:
    if not score_allowed:
        return "BLOCKED_BY_GATE"

    humidity_available = variable_available(row, "relative_humidity_pct")
    temperature_available = variable_available(row, "temperature_c")

    if humidity_available and temperature_available:
        return "MOISTURE_CONTEXT_AVAILABLE"

    if humidity_available:
        return "MOISTURE_CONTEXT_HUMIDITY_ONLY_AVAILABLE"

    return "MOISTURE_CONTEXT_MISSING"


def classify_wind_context_status(row: pd.Series, score_allowed: bool) -> str:
    if not score_allowed:
        return "BLOCKED_BY_GATE"

    wind_speed_available = variable_available(row, "wind_speed_ms")
    wind_direction_available = variable_available(row, "wind_direction_deg")

    if wind_speed_available and wind_direction_available:
        return "WIND_CONTEXT_AVAILABLE"

    if wind_speed_available:
        return "WIND_SPEED_ONLY_AVAILABLE"

    if wind_direction_available:
        return "WIND_DIRECTION_ONLY_AVAILABLE"

    return "WIND_CONTEXT_MISSING"


def classify_pressure_context_status(row: pd.Series, score_allowed: bool, primary_station_count: int) -> str:
    if not score_allowed:
        return "BLOCKED_BY_GATE"

    pressure_count = observed_station_count(row, "pressure_hpa")

    if pressure_count <= 0:
        return "PRESSURE_CONTEXT_MISSING"

    if primary_station_count > 0 and pressure_count < primary_station_count:
        return "PRESSURE_CONTEXT_AVAILABLE_PARTIAL"

    return "PRESSURE_CONTEXT_AVAILABLE_FULL"


def build_vector(features: pd.DataFrame, gate: pd.DataFrame, features_csv: Path, gate_csv: Path) -> pd.DataFrame:
    key_cols = ["output_case", "activity_id"]

    missing_features_keys = [c for c in key_cols if c not in features.columns]
    missing_gate_keys = [c for c in key_cols if c not in gate.columns]
    if missing_features_keys:
        raise ValueError(f"features CSV missing key columns: {missing_features_keys}")
    if missing_gate_keys:
        raise ValueError(f"gate CSV missing key columns: {missing_gate_keys}")

    merged = features.merge(
        gate,
        on=key_cols,
        how="left",
        suffixes=("_features", "_gate"),
    )

    rows = []

    for _, row in merged.iterrows():
        primary_ids = str_value(row, "primary_candidate_station_ids_features") or str_value(row, "primary_candidate_station_ids_gate")
        primary_station_count_policy = len([x for x in primary_ids.split("|") if x.strip()])

        primary_station_count_present = int_value(row, "primary_station_count_present_in_activity_window_features")
        if primary_station_count_present == 0:
            primary_station_count_present = int_value(row, "primary_station_count_present_in_activity_window_gate")

        primary_observed_row_count = int_value(row, "primary_observed_row_count_features")
        if primary_observed_row_count == 0:
            primary_observed_row_count = int_value(row, "primary_observed_row_count_gate")

        primary_missing_row_count = int_value(row, "primary_missing_row_count_features")
        if primary_missing_row_count == 0:
            primary_missing_row_count = int_value(row, "primary_missing_row_count_gate")

        primary_total_rows = primary_observed_row_count + primary_missing_row_count

        score_allowed = bool_value(row, "weather_sensitive_score_allowed")
        vector_status = classify_vector_status(row)

        available_weather_variable_set = str_value(row, "available_weather_variable_set")
        missing_weather_variable_set = str_value(row, "missing_weather_variable_set")

        available_count = int_value(row, "available_weather_variable_count")
        missing_count = int_value(row, "missing_weather_variable_count")
        if available_count == 0 and available_weather_variable_set:
            available_count = len([x for x in available_weather_variable_set.split("|") if x])
        if missing_count == 0 and missing_weather_variable_set:
            missing_count = len([x for x in missing_weather_variable_set.split("|") if x])

        variable_total_count = available_count + missing_count

        precip_available = variable_available(row, "precipitation_mm")
        precip_positive_count = int_value(row, "precipitation_mm_obs_count_positive_sum")
        precip_zero_count = int_value(row, "precipitation_mm_obs_count_zero_sum")

        out = {
            "schema_version": SCHEMA_VERSION,
            "output_case": str_value(row, "output_case"),
            "case_id": str_value(row, "case_id_gate") or str_value(row, "case_id_features"),
            "activity_id": str_value(row, "activity_id"),
            "activity_source_type": str_value(row, "activity_source_type_gate") or str_value(row, "activity_source_type_features"),
            "activity_source_path": str_value(row, "activity_source_path_gate") or str_value(row, "activity_source_path_features"),
            "activity_start_time_utc": str_value(row, "activity_start_time_utc_gate") or str_value(row, "activity_start_time_utc_features"),
            "activity_end_time_utc": str_value(row, "activity_end_time_utc_gate") or str_value(row, "activity_end_time_utc_features"),
            "activity_duration_min": str_value(row, "activity_duration_min_gate") or str_value(row, "activity_duration_min_features"),

            "representative_feature_status": str_value(row, "representative_feature_status_gate") or str_value(row, "representative_feature_status_features"),
            "weather_sensitive_feature_gate": str_value(row, "weather_sensitive_feature_gate"),
            "weather_sensitive_score_allowed": score_allowed,
            "weather_feature_vector_status": vector_status,
            "weather_sensitive_feature_gate_reason": str_value(row, "weather_sensitive_feature_gate_reason"),

            "zero_fallback_true_count": int_value(row, "zero_fallback_true_count_gate"),
            "zero_fallback_used": str_value(row, "zero_fallback_used"),

            "primary_candidate_station_ids": primary_ids,
            "primary_candidate_station_names": str_value(row, "primary_candidate_station_names_features") or str_value(row, "primary_candidate_station_names_gate"),
            "primary_station_count_policy": primary_station_count_policy,
            "primary_station_count_present_in_activity_window": primary_station_count_present,
            "primary_station_coverage_ratio": safe_ratio(primary_station_count_present, primary_station_count_policy),
            "primary_observed_row_count": primary_observed_row_count,
            "primary_missing_row_count": primary_missing_row_count,
            "primary_observed_row_ratio": safe_ratio(primary_observed_row_count, primary_total_rows),

            "available_weather_variable_count": available_count,
            "missing_weather_variable_count": missing_count,
            "weather_variable_coverage_ratio": safe_ratio(available_count, variable_total_count),
            "available_weather_variable_set": available_weather_variable_set,
            "missing_weather_variable_set": missing_weather_variable_set,

            "activity_time_rain_observation_status": classify_rain_observation_status(row, score_allowed),
            "activity_time_moisture_context_status": classify_moisture_context_status(row, score_allowed),
            "activity_time_wind_context_status": classify_wind_context_status(row, score_allowed),
            "activity_time_pressure_context_status": classify_pressure_context_status(row, score_allowed, primary_station_count_policy),
            "antecedent_precipitation_context_status": "NOT_EVALUATED_IN_V1",
            "surface_wetness_proxy_status": "NOT_EVALUATED_IN_V1",
            "surface_wetness_proxy_reason": "Antecedent precipitation and route-surface wetness are reserved for a later lookback/context layer.",

            "precipitation_mm_available": precip_available,
            "precipitation_mm_observed_station_count": observed_station_count(row, "precipitation_mm"),
            "precipitation_mm_mean_primary": numeric_if_available(row, "precipitation_mm", "primary_value_mean_of_station_means"),
            "precipitation_mm_max_primary": numeric_if_available(row, "precipitation_mm", "primary_value_max"),
            "precipitation_mm_min_primary": numeric_if_available(row, "precipitation_mm", "primary_value_min"),
            "precipitation_observed_zero_flag": bool(precip_available and precip_zero_count > 0 and precip_positive_count == 0),
            "precipitation_positive_observed_flag": bool(precip_available and precip_positive_count > 0),
            "precipitation_observed_zero_count": precip_zero_count,
            "precipitation_positive_observed_count": precip_positive_count,

            "precipitation_10min_mm_available": variable_available(row, "precipitation_10min_mm"),
            "precipitation_1hr_mm_available": variable_available(row, "precipitation_1hr_mm"),

            "temperature_c_available": variable_available(row, "temperature_c"),
            "temperature_c_observed_station_count": observed_station_count(row, "temperature_c"),
            "temperature_c_mean_primary": numeric_if_available(row, "temperature_c", "primary_value_mean_of_station_means"),

            "relative_humidity_pct_available": variable_available(row, "relative_humidity_pct"),
            "relative_humidity_pct_observed_station_count": observed_station_count(row, "relative_humidity_pct"),
            "relative_humidity_pct_mean_primary": numeric_if_available(row, "relative_humidity_pct", "primary_value_mean_of_station_means"),

            "wind_speed_ms_available": variable_available(row, "wind_speed_ms"),
            "wind_speed_ms_observed_station_count": observed_station_count(row, "wind_speed_ms"),
            "wind_speed_ms_mean_primary": numeric_if_available(row, "wind_speed_ms", "primary_value_mean_of_station_means"),
            "wind_speed_ms_max_primary": numeric_if_available(row, "wind_speed_ms", "primary_value_max"),

            "wind_direction_deg_available": variable_available(row, "wind_direction_deg"),
            "wind_direction_deg_observed_station_count": observed_station_count(row, "wind_direction_deg"),
            "wind_direction_deg_mean_primary_linear_raw_not_circular": numeric_if_available(row, "wind_direction_deg", "primary_value_mean_of_station_means"),
            "wind_direction_deg_note": "Linear mean retained only as raw review evidence; circular mean is not computed in v1.",

            "pressure_hpa_available": variable_available(row, "pressure_hpa"),
            "pressure_hpa_partial_flag": bool(
                observed_station_count(row, "pressure_hpa") > 0
                and primary_station_count_policy > 0
                and observed_station_count(row, "pressure_hpa") < primary_station_count_policy
            ),
            "pressure_hpa_observed_station_count": observed_station_count(row, "pressure_hpa"),
            "pressure_hpa_mean_primary": numeric_if_available(row, "pressure_hpa", "primary_value_mean_of_station_means"),

            "visibility_m_available": variable_available(row, "visibility_m"),
            "visibility_m_observed_station_count": observed_station_count(row, "visibility_m"),

            "weather_text_available": variable_available(row, "weather"),
            "weather_text_observed_station_count": observed_station_count(row, "weather"),

            "source_features_csv": str(features_csv),
            "source_gate_csv": str(gate_csv),
        }

        rows.append(out)

    return pd.DataFrame(rows)


def build_summary(vector: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for col in [
        "weather_feature_vector_status",
        "activity_time_rain_observation_status",
        "activity_time_moisture_context_status",
        "activity_time_wind_context_status",
        "activity_time_pressure_context_status",
        "antecedent_precipitation_context_status",
        "surface_wetness_proxy_status",
    ]:
        for key, group in vector.groupby(col, dropna=False, sort=True):
            rows.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "summary_type": col,
                    "summary_key": key,
                    "activity_count": int(len(group)),
                    "score_allowed_count": int(
                        group["weather_sensitive_score_allowed"]
                        .astype(str)
                        .str.lower()
                        .eq("true")
                        .sum()
                    ),
                    "zero_fallback_true_count": int(
                        pd.to_numeric(group["zero_fallback_true_count"], errors="coerce")
                        .fillna(0)
                        .sum()
                    ),
                }
            )

    rows.append(
        {
            "schema_version": SCHEMA_VERSION,
            "summary_type": "overall",
            "summary_key": "ALL_ACTIVITIES",
            "activity_count": int(len(vector)),
            "score_allowed_count": int(
                vector["weather_sensitive_score_allowed"]
                .astype(str)
                .str.lower()
                .eq("true")
                .sum()
            ),
            "zero_fallback_true_count": int(
                pd.to_numeric(vector["zero_fallback_true_count"], errors="coerce")
                .fillna(0)
                .sum()
            ),
        }
    )

    return pd.DataFrame(rows)


def html_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int | None = None) -> str:
    view = df.copy()
    if columns is not None:
        view = view[[c for c in columns if c in view.columns]]
    if max_rows is not None:
        view = view.head(max_rows)
    view = view.fillna("")
    return view.to_html(index=False, escape=True, border=0, classes="data-table")


def build_html_report(vector: pd.DataFrame, summary: pd.DataFrame, features_csv: Path, gate_csv: Path) -> str:
    total = int(len(vector))
    allowed = int(vector["weather_sensitive_score_allowed"].astype(str).str.lower().eq("true").sum())
    zero_fallback_total = int(
        pd.to_numeric(vector["zero_fallback_true_count"], errors="coerce").fillna(0).sum()
    )

    status_counts = (
        vector.groupby("weather_feature_vector_status", dropna=False)
        .size()
        .reset_index(name="activity_count")
        .sort_values("activity_count", ascending=False)
    )

    key_cols = [
        "output_case",
        "activity_id",
        "weather_feature_vector_status",
        "weather_sensitive_score_allowed",
        "activity_time_rain_observation_status",
        "activity_time_moisture_context_status",
        "activity_time_wind_context_status",
        "activity_time_pressure_context_status",
        "antecedent_precipitation_context_status",
        "surface_wetness_proxy_status",
        "primary_station_coverage_ratio",
        "primary_observed_row_ratio",
        "weather_variable_coverage_ratio",
        "precipitation_mm_available",
        "precipitation_mm_mean_primary",
        "precipitation_mm_max_primary",
        "precipitation_observed_zero_flag",
        "temperature_c_mean_primary",
        "relative_humidity_pct_mean_primary",
        "wind_speed_ms_mean_primary",
        "wind_speed_ms_max_primary",
        "pressure_hpa_partial_flag",
        "pressure_hpa_mean_primary",
        "available_weather_variable_set",
        "missing_weather_variable_set",
    ]

    allowed_rows = vector[
        vector["weather_sensitive_score_allowed"].astype(str).str.lower().eq("true")
    ].copy()

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>IB3W Weather-Sensitive Feature Vector v1</title>
<style>
body {{
  margin: 0;
  background: #f4f7f9;
  color: #1f2937;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.5;
}}
header {{
  background: #25465f;
  color: white;
  padding: 26px 32px;
}}
main {{
  max-width: 1500px;
  margin: 0 auto;
  padding: 24px;
}}
section {{
  background: white;
  border: 1px solid #d9e1e7;
  border-radius: 10px;
  padding: 20px;
  margin-bottom: 18px;
}}
.cards {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 12px;
}}
.card {{
  border: 1px solid #d9e1e7;
  border-radius: 8px;
  padding: 14px;
  background: #fbfcfd;
}}
.card strong {{
  display: block;
  font-size: 24px;
}}
.callout {{
  border-left: 5px solid #2b6f96;
  background: #eef7fc;
  padding: 12px 14px;
  margin: 12px 0;
}}
.table-wrap {{
  overflow-x: auto;
}}
table.data-table {{
  border-collapse: collapse;
  width: 100%;
  font-size: 12px;
}}
.data-table th, .data-table td {{
  border: 1px solid #d9e1e7;
  padding: 6px 8px;
  text-align: left;
  vertical-align: top;
}}
.data-table th {{
  background: #edf2f5;
}}
code {{
  color: #18344a;
}}
</style>
</head>
<body>
<header>
  <h1>IB3W Weather-Sensitive Feature Vector v1</h1>
  <p>Activity-time weather observation vector. No risk score, no THCI, no missing-to-zero imputation.</p>
</header>
<main>
<section>
  <h2>1. Scope</h2>
  <div class="callout">
    This layer converts gate-approved representative weather features into a cleaner
    activity-level feature vector. It does not decide mountain weather risk. Antecedent
    precipitation and surface wetness are reserved for a later context layer.
  </div>
  <div class="cards">
    <div class="card"><strong>{total}</strong><span>activities reviewed</span></div>
    <div class="card"><strong>{allowed}</strong><span>activities with score-allowed weather vector</span></div>
    <div class="card"><strong>{total - allowed}</strong><span>activities unavailable or blocked</span></div>
    <div class="card"><strong>{zero_fallback_total}</strong><span>zero fallback violations</span></div>
  </div>
</section>

<section>
  <h2>2. Vector status distribution</h2>
  <div class="table-wrap">{html_table(status_counts)}</div>
</section>

<section>
  <h2>3. Score-allowed weather vectors</h2>
  <div class="table-wrap">{html_table(allowed_rows, key_cols)}</div>
</section>

<section>
  <h2>4. Full vector review</h2>
  <div class="table-wrap">{html_table(vector, key_cols)}</div>
</section>

<section>
  <h2>5. Summary</h2>
  <div class="table-wrap">{html_table(summary)}</div>
</section>

<section>
  <h2>6. Sources and boundaries</h2>
  <ul>
    <li>Representative features CSV: <code>{html.escape(str(features_csv))}</code></li>
    <li>Gate CSV: <code>{html.escape(str(gate_csv))}</code></li>
    <li>No weather DB query is performed.</li>
    <li>No antecedent precipitation lookback is performed in v1.</li>
    <li>No route-surface wetness proxy is computed in v1.</li>
    <li>No risk score or THCI integration is performed.</li>
  </ul>
</section>
</main>
</body>
</html>
"""


def main() -> None:
    args = parse_args()

    features = read_csv(args.features_csv, "representative features CSV")
    gate = read_csv(args.gate_csv, "weather-sensitive feature gate CSV")

    vector = build_vector(features, gate, args.features_csv, args.gate_csv)
    summary = build_summary(vector)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    vector_csv = args.out_dir / "activity_weather_sensitive_feature_vector.csv"
    summary_csv = args.out_dir / "activity_weather_sensitive_feature_vector_summary.csv"
    html_report = args.out_dir / "activity_weather_sensitive_feature_vector_report.html"

    vector.to_csv(vector_csv, index=False, encoding="utf-8-sig")
    summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")
    html_report.write_text(
        build_html_report(vector, summary, args.features_csv, args.gate_csv),
        encoding="utf-8",
    )

    print("IB3W weather-sensitive feature vector v1 written")
    print("vector_csv:", vector_csv)
    print("summary_csv:", summary_csv)
    print("html_report:", html_report)
    print()
    print("vector_status_distribution:")
    print(
        vector.groupby("weather_feature_vector_status")
        .size()
        .reset_index(name="activity_count")
        .sort_values("activity_count", ascending=False)
        .to_string(index=False)
    )
    print()
    print("rain_observation_distribution:")
    print(
        vector.groupby("activity_time_rain_observation_status")
        .size()
        .reset_index(name="activity_count")
        .sort_values("activity_count", ascending=False)
        .to_string(index=False)
    )
    print()
    print(
        "zero_fallback_true_total:",
        int(pd.to_numeric(vector["zero_fallback_true_count"], errors="coerce").fillna(0).sum()),
    )


if __name__ == "__main__":
    main()
