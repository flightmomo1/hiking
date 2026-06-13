from __future__ import annotations

import argparse
import html
from pathlib import Path

import pandas as pd


SCHEMA_VERSION = "ib3w_representative_environment_features_report_v1"

DEFAULT_FEATURES_CSV = Path(
    "outputs/ib3w_representative_environment_features_v1/"
    "activity_representative_environment_features.csv"
)
DEFAULT_SUMMARY_CSV = Path(
    "outputs/ib3w_representative_environment_features_v1/"
    "activity_representative_environment_features_summary.csv"
)
DEFAULT_HTML_REPORT = Path(
    "outputs/ib3w_representative_environment_features_v1/"
    "activity_representative_environment_features_report.html"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build IB3W representative environment features HTML report."
    )
    parser.add_argument("--features-csv", type=Path, default=DEFAULT_FEATURES_CSV)
    parser.add_argument("--summary-csv", type=Path, default=DEFAULT_SUMMARY_CSV)
    parser.add_argument("--html-report", type=Path, default=DEFAULT_HTML_REPORT)
    return parser.parse_args()


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")
    return pd.read_csv(path, dtype=str)


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


def first_nonblank(df: pd.DataFrame, column: str) -> str:
    if column not in df.columns:
        return ""
    values = df[column].dropna().astype(str).str.strip()
    values = values[values.ne("")]
    return values.iloc[0] if len(values) else ""


def numeric_sum(df: pd.DataFrame, column: str) -> int:
    if column not in df.columns:
        return 0
    return int(pd.to_numeric(df[column], errors="coerce").fillna(0).sum())


def build_report(features: pd.DataFrame, summary: pd.DataFrame, features_csv: Path, summary_csv: Path) -> str:
    status_counts = (
        features.groupby("representative_feature_status", dropna=False)
        .size()
        .reset_index(name="activity_count")
        .sort_values("activity_count", ascending=False)
    )

    output_case_counts = (
        features.groupby("output_case", dropna=False)
        .size()
        .reset_index(name="activity_count")
        .sort_values("activity_count", ascending=False)
    )

    backend_rows = features[
        features["representative_feature_status"].eq("NO_PRIMARY_REPRESENTATIVE_ROWS")
    ].copy()

    partial_rows = features[
        features["representative_feature_status"].eq(
            "PRIMARY_REPRESENTATIVE_FEATURES_AVAILABLE_PARTIAL"
        )
    ].copy()

    total_activities = int(len(features))
    zero_fallback_true_count = numeric_sum(features, "zero_fallback_true_count")

    primary_station_ids = first_nonblank(features, "primary_candidate_station_ids")
    primary_station_names = first_nonblank(features, "primary_candidate_station_names")

    key_cols = [
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

    variable_cols = [
        "output_case",
        "activity_id",
        "precipitation_mm_primary_observed_station_count",
        "precipitation_mm_primary_value_min",
        "precipitation_mm_primary_value_max",
        "precipitation_mm_primary_value_mean_of_station_means",
        "precipitation_mm_primary_value_sum_of_station_sums",
        "precipitation_mm_obs_count_zero_sum",
        "precipitation_mm_obs_count_positive_sum",
        "precipitation_10min_mm_primary_observed_station_count",
        "precipitation_1hr_mm_primary_observed_station_count",
        "temperature_c_primary_observed_station_count",
        "temperature_c_primary_value_mean_of_station_means",
        "relative_humidity_pct_primary_observed_station_count",
        "relative_humidity_pct_primary_value_mean_of_station_means",
        "wind_speed_ms_primary_observed_station_count",
        "wind_speed_ms_primary_value_max",
        "wind_direction_deg_primary_observed_station_count",
        "pressure_hpa_primary_observed_station_count",
        "visibility_m_primary_observed_station_count",
        "weather_primary_observed_station_count",
    ]

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>IB3W Representative Environment Features v1</title>
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
.warn {{
  border-left: 5px solid #b7791f;
  background: #fff8e6;
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
  <h1>IB3W Representative Environment Features v1</h1>
  <p>Activity-level representative weather features from primary mountain station candidates.</p>
</header>
<main>
<section>
  <h2>1. Scope and guardrails</h2>
  <div class="callout">
    This report reads the representative features CSV and summary CSV only.
    It does not query the weather DB, does not change adapter output, does not compute
    risk score, and does not fill missing values with zero.
  </div>
  <div class="cards">
    <div class="card"><strong>{total_activities}</strong><span>activities reviewed</span></div>
    <div class="card"><strong>{len(backend_rows)}</strong><span>activities with no primary representative rows</span></div>
    <div class="card"><strong>{len(partial_rows)}</strong><span>activities with partial primary representative features</span></div>
    <div class="card"><strong>{zero_fallback_true_count}</strong><span>zero fallback violations</span></div>
  </div>
</section>

<section>
  <h2>2. Primary representative station set</h2>
  <p><strong>Station IDs:</strong> <code>{html.escape(primary_station_ids)}</code></p>
  <p><strong>Station names:</strong> <code>{html.escape(primary_station_names)}</code></p>
  <div class="warn">
    Observed zero precipitation is preserved as an observed value. It is not equivalent to
    missing-to-zero fallback. The zero fallback count must remain zero.
  </div>
</section>

<section>
  <h2>3. Representative feature status distribution</h2>
  <div class="table-wrap">{html_table(status_counts)}</div>
</section>

<section>
  <h2>4. Output case distribution</h2>
  <div class="table-wrap">{html_table(output_case_counts)}</div>
</section>

<section>
  <h2>5. GPX positive case representative features</h2>
  <div class="table-wrap">{html_table(partial_rows, key_cols)}</div>
</section>

<section>
  <h2>6. GPX variable-level details</h2>
  <div class="table-wrap">{html_table(partial_rows, variable_cols)}</div>
</section>

<section>
  <h2>7. Backend 2024 activities without primary representative rows</h2>
  <p>
    These activities retain the previous audit conclusion: the 2024 backend activities do
    not overlap the weather DB observation window, so no representative feature values are
    synthesized.
  </p>
  <div class="table-wrap">{html_table(backend_rows, key_cols, max_rows=30)}</div>
</section>

<section>
  <h2>8. Full activity feature review</h2>
  <div class="table-wrap">{html_table(features, key_cols)}</div>
</section>

<section>
  <h2>9. Summary table</h2>
  <div class="table-wrap">{html_table(summary)}</div>
</section>

<section>
  <h2>10. Source files and limitations</h2>
  <ul>
    <li>Features CSV: <code>{html.escape(str(features_csv))}</code></li>
    <li>Summary CSV: <code>{html.escape(str(summary_csv))}</code></li>
    <li>No risk score is computed in this report layer.</li>
    <li>No THCI integration is performed in this report layer.</li>
    <li>No station fusion weighting is performed in this report layer.</li>
    <li>Missing remains missing; only observed zero precipitation remains zero.</li>
  </ul>
</section>
</main>
</body>
</html>
"""


def main() -> None:
    args = parse_args()

    features = read_csv(args.features_csv)
    summary = read_csv(args.summary_csv)

    args.html_report.parent.mkdir(parents=True, exist_ok=True)
    args.html_report.write_text(
        build_report(features, summary, args.features_csv, args.summary_csv),
        encoding="utf-8",
    )

    print("IB3W representative environment features report written")
    print("features_csv:", args.features_csv)
    print("summary_csv:", args.summary_csv)
    print("html_report:", args.html_report)

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
    print("zero_fallback_true_total:", numeric_sum(features, "zero_fallback_true_count"))


if __name__ == "__main__":
    main()
