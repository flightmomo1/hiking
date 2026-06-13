from __future__ import annotations

import argparse
import html
from pathlib import Path

import pandas as pd


SCHEMA_VERSION = "ib3w_weather_sensitive_feature_gate_v1"

DEFAULT_FEATURES_CSV = Path(
    "outputs/ib3w_representative_environment_features_v1/"
    "activity_representative_environment_features.csv"
)

DEFAULT_OUT_DIR = Path("outputs/ib3w_weather_sensitive_feature_gate_v1")

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
        description="Build IB3W weather-sensitive activity feature gate v1."
    )
    parser.add_argument("--features-csv", type=Path, default=DEFAULT_FEATURES_CSV)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def read_features(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"representative features CSV not found: {path}")
    df = pd.read_csv(path, dtype=str)

    required = [
        "output_case",
        "activity_id",
        "representative_feature_status",
        "zero_fallback_true_count",
        "primary_candidate_station_ids",
        "primary_station_count_present_in_activity_window",
        "primary_observed_row_count",
        "primary_missing_row_count",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"features CSV missing columns: {missing}")

    return df


def to_int(value: object) -> int:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return int(parsed) if pd.notna(parsed) else 0


def observed_station_count(row: pd.Series, variable: str) -> int:
    return to_int(row.get(f"{variable}_primary_observed_station_count", 0))


def status_set(row: pd.Series, variable: str) -> str:
    value = row.get(f"{variable}_primary_context_status_set", "")
    return "" if pd.isna(value) else str(value).strip()


def build_available_missing_sets(row: pd.Series) -> tuple[str, str, str]:
    available = []
    missing = []
    partial_or_missing_status = []

    for variable in WEATHER_VARIABLES:
        obs_count = observed_station_count(row, variable)
        status = status_set(row, variable)

        if obs_count > 0:
            available.append(variable)
        else:
            missing.append(variable)

        if "MISSING" in status or obs_count == 0:
            partial_or_missing_status.append(variable)

    return "|".join(available), "|".join(missing), "|".join(partial_or_missing_status)


def classify_gate(row: pd.Series) -> tuple[str, str, bool]:
    status = str(row.get("representative_feature_status", "")).strip()
    zero_fallback_count = to_int(row.get("zero_fallback_true_count", 0))

    if zero_fallback_count > 0:
        return (
            "BLOCK_ZERO_FALLBACK_QA_FAILED",
            "zero_fallback_true_count is greater than 0; missing weather values may have been converted to zero.",
            False,
        )

    if status == "NO_PRIMARY_REPRESENTATIVE_ROWS":
        return (
            "WEATHER_FEATURE_UNAVAILABLE_DO_NOT_SCORE",
            "No primary representative station rows are available for this activity; do not compute weather-sensitive features.",
            False,
        )

    if status == "PRIMARY_REPRESENTATIVE_FEATURES_AVAILABLE_PARTIAL":
        return (
            "WEATHER_FEATURE_AVAILABLE_PARTIAL_SCORE_ALLOWED_FOR_OBSERVED_VARIABLES_ONLY",
            "Primary representative station rows exist, but feature coverage is partial; consume only observed variables.",
            True,
        )

    if status == "PRIMARY_REPRESENTATIVE_FEATURES_AVAILABLE_FULL":
        return (
            "WEATHER_FEATURE_AVAILABLE_FULL_SCORE_ALLOWED",
            "Primary representative station rows have full feature coverage.",
            True,
        )

    if status == "PRIMARY_REPRESENTATIVE_ROWS_ALL_MISSING":
        return (
            "WEATHER_FEATURE_UNAVAILABLE_ALL_MISSING_REVIEW_REQUIRED",
            "Primary representative station rows exist but all values are missing; block weather-sensitive scoring.",
            False,
        )

    return (
        "WEATHER_FEATURE_GATE_UNKNOWN_REVIEW_REQUIRED",
        f"Unrecognized representative_feature_status: {status}",
        False,
    )


def build_gate(features: pd.DataFrame, features_csv: Path) -> pd.DataFrame:
    rows = []

    passthrough = [
        "output_case",
        "case_id",
        "activity_id",
        "activity_source_type",
        "activity_source_path",
        "activity_start_time_utc",
        "activity_end_time_utc",
        "activity_duration_min",
        "timestamp_epoch_used",
        "primary_candidate_station_ids",
        "primary_candidate_station_names",
        "primary_candidate_station_count_policy",
        "primary_station_count_present_in_activity_window",
        "primary_observed_row_count",
        "primary_missing_row_count",
        "representative_feature_status",
        "zero_fallback_true_count",
    ]

    for _, row in features.iterrows():
        gate, reason, score_allowed = classify_gate(row)
        available_set, missing_set, partial_or_missing_set = build_available_missing_sets(row)

        out = {
            "schema_version": SCHEMA_VERSION,
            "source_features_csv": str(features_csv),
            "weather_sensitive_feature_gate": gate,
            "weather_sensitive_feature_gate_reason": reason,
            "weather_sensitive_score_allowed": score_allowed,
            "available_weather_variable_set": available_set,
            "missing_weather_variable_set": missing_set,
            "partial_or_missing_weather_variable_set": partial_or_missing_set,
            "available_weather_variable_count": len([v for v in available_set.split("|") if v]),
            "missing_weather_variable_count": len([v for v in missing_set.split("|") if v]),
        }

        for col in passthrough:
            out[col] = row.get(col, "")

        rows.append(out)

    cols_front = [
        "schema_version",
        "output_case",
        "case_id",
        "activity_id",
        "representative_feature_status",
        "weather_sensitive_feature_gate",
        "weather_sensitive_score_allowed",
        "weather_sensitive_feature_gate_reason",
        "zero_fallback_true_count",
        "primary_candidate_station_ids",
        "primary_station_count_present_in_activity_window",
        "primary_observed_row_count",
        "primary_missing_row_count",
        "available_weather_variable_count",
        "missing_weather_variable_count",
        "available_weather_variable_set",
        "missing_weather_variable_set",
        "partial_or_missing_weather_variable_set",
        "source_features_csv",
    ]

    df = pd.DataFrame(rows)
    remaining = [c for c in df.columns if c not in cols_front]
    return df[cols_front + remaining]


def build_summary(gate: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for gate_name, group in gate.groupby("weather_sensitive_feature_gate", dropna=False, sort=True):
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "summary_type": "weather_sensitive_feature_gate",
                "summary_key": gate_name,
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

    for status, group in gate.groupby("representative_feature_status", dropna=False, sort=True):
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "summary_type": "representative_feature_status",
                "summary_key": status,
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
            "activity_count": int(len(gate)),
            "score_allowed_count": int(
                gate["weather_sensitive_score_allowed"]
                .astype(str)
                .str.lower()
                .eq("true")
                .sum()
            ),
            "zero_fallback_true_count": int(
                pd.to_numeric(gate["zero_fallback_true_count"], errors="coerce")
                .fillna(0)
                .sum()
            ),
        }
    )

    return pd.DataFrame(rows)


def html_table(
    df: pd.DataFrame,
    columns: list[str] | None = None,
    max_rows: int | None = None,
) -> str:
    view = df.copy()
    if columns is not None:
        view = view[[c for c in columns if c in view.columns]]
    if max_rows is not None:
        view = view.head(max_rows)
    view = view.fillna("")
    return view.to_html(index=False, escape=True, border=0, classes="data-table")


def build_html_report(gate: pd.DataFrame, summary: pd.DataFrame, features_csv: Path) -> str:
    total_activities = int(len(gate))
    score_allowed_count = int(
        gate["weather_sensitive_score_allowed"].astype(str).str.lower().eq("true").sum()
    )
    zero_fallback_total = int(
        pd.to_numeric(gate["zero_fallback_true_count"], errors="coerce").fillna(0).sum()
    )

    gate_counts = (
        gate.groupby("weather_sensitive_feature_gate", dropna=False)
        .size()
        .reset_index(name="activity_count")
        .sort_values("activity_count", ascending=False)
    )

    allowed_rows = gate[
        gate["weather_sensitive_score_allowed"].astype(str).str.lower().eq("true")
    ].copy()

    blocked_rows = gate[
        ~gate["weather_sensitive_score_allowed"].astype(str).str.lower().eq("true")
    ].copy()

    key_cols = [
        "output_case",
        "activity_id",
        "representative_feature_status",
        "weather_sensitive_feature_gate",
        "weather_sensitive_score_allowed",
        "zero_fallback_true_count",
        "available_weather_variable_set",
        "missing_weather_variable_set",
        "weather_sensitive_feature_gate_reason",
    ]

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>IB3W Weather-Sensitive Feature Gate v1</title>
<style>
body {{
  margin: 0;
  background: #f4f7f9;
  color: #1f2937;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.5;
}}
header {{
  background: #20374c;
  color: white;
  padding: 26px 32px;
}}
main {{
  max-width: 1440px;
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
  <h1>IB3W Weather-Sensitive Feature Gate v1</h1>
  <p>Read-only gate before weather-sensitive IB3 risk or THCI experiments.</p>
</header>
<main>
<section>
  <h2>1. Scope</h2>
  <div class="callout">
    This layer does not compute risk score. It only decides whether weather-sensitive
    downstream features are unavailable, partially available, or blocked by QA.
    Missing weather values remain missing.
  </div>
  <div class="cards">
    <div class="card"><strong>{total_activities}</strong><span>activities reviewed</span></div>
    <div class="card"><strong>{score_allowed_count}</strong><span>activities allowed for observed-variable scoring</span></div>
    <div class="card"><strong>{len(blocked_rows)}</strong><span>activities blocked or unavailable</span></div>
    <div class="card"><strong>{zero_fallback_total}</strong><span>zero fallback violations</span></div>
  </div>
</section>

<section>
  <h2>2. Gate distribution</h2>
  <div class="table-wrap">{html_table(gate_counts)}</div>
</section>

<section>
  <h2>3. Score-allowed activities</h2>
  <div class="table-wrap">{html_table(allowed_rows, key_cols)}</div>
</section>

<section>
  <h2>4. Blocked or unavailable activities</h2>
  <div class="table-wrap">{html_table(blocked_rows, key_cols, max_rows=30)}</div>
</section>

<section>
  <h2>5. Full gate review</h2>
  <div class="table-wrap">{html_table(gate, key_cols)}</div>
</section>

<section>
  <h2>6. Summary</h2>
  <div class="table-wrap">{html_table(summary)}</div>
</section>

<section>
  <h2>7. Source and non-goals</h2>
  <ul>
    <li>Source features CSV: <code>{html.escape(str(features_csv))}</code></li>
    <li>No weather DB query is performed.</li>
    <li>No risk score is computed.</li>
    <li>No THCI integration is performed.</li>
    <li>No missing-to-zero imputation is allowed.</li>
  </ul>
</section>
</main>
</body>
</html>
"""


def main() -> None:
    args = parse_args()

    features = read_features(args.features_csv)
    gate = build_gate(features, args.features_csv)
    summary = build_summary(gate)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    gate_csv = args.out_dir / "activity_weather_sensitive_feature_gate.csv"
    summary_csv = args.out_dir / "activity_weather_sensitive_feature_gate_summary.csv"
    html_report = args.out_dir / "activity_weather_sensitive_feature_gate_report.html"

    gate.to_csv(gate_csv, index=False, encoding="utf-8-sig")
    summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")
    html_report.write_text(
        build_html_report(gate, summary, args.features_csv),
        encoding="utf-8",
    )

    print("IB3W weather-sensitive feature gate v1 written")
    print("gate_csv:", gate_csv)
    print("summary_csv:", summary_csv)
    print("html_report:", html_report)
    print()
    print("gate_distribution:")
    print(
        gate.groupby("weather_sensitive_feature_gate")
        .size()
        .reset_index(name="activity_count")
        .sort_values("activity_count", ascending=False)
        .to_string(index=False)
    )
    print()
    print("zero_fallback_true_total:", int(
        pd.to_numeric(gate["zero_fallback_true_count"], errors="coerce")
        .fillna(0)
        .sum()
    ))


if __name__ == "__main__":
    main()
