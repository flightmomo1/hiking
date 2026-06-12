from __future__ import annotations

import argparse
import html
from pathlib import Path
from typing import Any

import pandas as pd


REVIEW_CASE = "ib3w_environment_window_review_report_v1"
STATUS_ORDER = ["OBSERVED", "MISSING", "NO_SOURCE", "NO_VARIABLE"]
STATUS_CLASS = {
    "OBSERVED": "status-observed",
    "MISSING": "status-missing",
    "NO_SOURCE": "status-no-source",
    "NO_VARIABLE": "status-no-variable",
}

DEFAULT_BACKEND_CANDIDATES = [
    Path(
        "outputs/ib3w_activity_environment_window_adapter_v1/"
        "backend_full26_2024/activity_environment_window_adapter_output.csv"
    ),
    Path(
        "outputs/ib3w_activity_environment_window_adapter_v1/"
        "qixing_lengshuikeng_full26_backend_2024_v1/"
        "activity_environment_window_adapter_output.csv"
    ),
]
DEFAULT_GPX_CANDIDATES = [
    Path(
        "outputs/ib3w_activity_environment_window_adapter_v1/"
        "gpx_qixing_lengshuikeng_xiaoyoukeng_20260410_biji/"
        "activity_environment_window_adapter_output.csv"
    ),
    Path(
        "outputs/ib3w_activity_environment_window_adapter_v1/"
        "qixing_lengshuikeng_xiaoyoukeng_20260410_gpx_v1/"
        "activity_environment_window_adapter_output.csv"
    ),
]
DEFAULT_AVAILABILITY_ROOT = Path(
    "outputs/ib3w_activity_weather_observation_availability_audit_v1"
)
DEFAULT_GPX_SMOKE_ROOT = Path(
    "outputs/ib3w_gpx_weather_observation_smoke_test_v1"
)
DEFAULT_OUT_DIR = Path("outputs/ib3w_environment_window_review_report_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build IB3W environment window review report v1 from existing outputs."
    )
    parser.add_argument("--backend-output-csv", type=Path)
    parser.add_argument("--gpx-output-csv", type=Path)
    parser.add_argument(
        "--availability-root",
        type=Path,
        default=DEFAULT_AVAILABILITY_ROOT,
    )
    parser.add_argument(
        "--gpx-smoke-root",
        type=Path,
        default=DEFAULT_GPX_SMOKE_ROOT,
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def resolve_existing(explicit: Path | None, candidates: list[Path], label: str) -> Path:
    if explicit is not None:
        if not explicit.exists():
            raise FileNotFoundError(f"{label} not found: {explicit}")
        return explicit

    for candidate in candidates:
        if candidate.exists():
            return candidate

    joined = "\n".join(f"  - {candidate}" for candidate in candidates)
    raise FileNotFoundError(f"{label} not found. Checked:\n{joined}")


def find_single(root: Path, filename: str) -> Path:
    matches = sorted(root.rglob(filename))
    if not matches:
        raise FileNotFoundError(f"{filename} not found under: {root}")
    if len(matches) > 1:
        raise RuntimeError(
            f"Expected one {filename} under {root}, found {len(matches)}"
        )
    return matches[0]


def read_adapter_output(path: Path, evidence_role: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = [
        "output_case",
        "activity_id",
        "context_variable",
        "context_status",
        "audit_status",
        "station_id",
        "station_name",
        "obs_count_total_window",
        "obs_count_nonnull",
        "obs_count_null",
        "obs_count_zero",
        "obs_count_positive",
        "observed_values_available",
        "missingness_reason",
        "zero_fallback_used",
    ]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Adapter output missing columns {missing}: {path}")

    out = df.copy()
    out["source_output_case"] = out["output_case"].astype(str)
    out["evidence_role"] = evidence_role
    out["source_adapter_output_csv"] = str(path)
    return out


def bool_true_count(series: pd.Series) -> int:
    return int(series.astype(str).str.strip().str.lower().eq("true").sum())


def numeric_sum(df: pd.DataFrame, column: str) -> int:
    return int(pd.to_numeric(df[column], errors="coerce").fillna(0).sum())


def observed_zero_precipitation_mask(df: pd.DataFrame) -> pd.Series:
    return (
        df["context_variable"].eq("precipitation_mm")
        & df["context_status"].eq("OBSERVED")
        & (pd.to_numeric(df["obs_count_nonnull"], errors="coerce").fillna(0) > 0)
        & (pd.to_numeric(df["obs_count_zero"], errors="coerce").fillna(0) > 0)
    )


def missing_variable_mask(df: pd.DataFrame, variable: str) -> pd.Series:
    return df["context_variable"].eq(variable) & df["context_status"].eq("MISSING")


def summary_row(
    df: pd.DataFrame,
    source_output_case: str,
    conclusion: str,
) -> dict[str, Any]:
    status_counts = df["context_status"].value_counts().to_dict()
    station_ids = df["station_id"].dropna().astype(str).str.strip()
    station_ids = station_ids[station_ids.ne("")]
    return {
        "review_case": REVIEW_CASE,
        "source_output_case": source_output_case,
        "activity_count": int(df["activity_id"].nunique()),
        "station_count": int(station_ids.nunique()),
        "row_count": int(len(df)),
        "observed_count": int(status_counts.get("OBSERVED", 0)),
        "missing_count": int(status_counts.get("MISSING", 0)),
        "no_source_count": int(status_counts.get("NO_SOURCE", 0)),
        "no_variable_count": int(status_counts.get("NO_VARIABLE", 0)),
        "observed_zero_precipitation_rows": int(
            observed_zero_precipitation_mask(df).sum()
        ),
        "missing_precipitation_10min_rows": int(
            missing_variable_mask(df, "precipitation_10min_mm").sum()
        ),
        "missing_precipitation_1hr_rows": int(
            missing_variable_mask(df, "precipitation_1hr_mm").sum()
        ),
        "zero_fallback_true_count": bool_true_count(df["zero_fallback_used"]),
        "review_conclusion": conclusion,
    }


def build_review_summary(
    backend: pd.DataFrame,
    gpx: pd.DataFrame,
) -> pd.DataFrame:
    combined = pd.concat([backend, gpx], ignore_index=True)
    backend_case = str(backend["source_output_case"].iloc[0])
    gpx_case = str(gpx["source_output_case"].iloc[0])
    return pd.DataFrame(
        [
            summary_row(
                backend,
                backend_case,
                (
                    "Negative evidence: all activity-variable rows are missing because "
                    "the 2024 activity windows are outside the weather DB observation range."
                ),
            ),
            summary_row(
                gpx,
                gpx_case,
                (
                    "Positive evidence: observations exist in the 2026 GPX activity window; "
                    "raw zero precipitation remains observed zero while null variables remain missing."
                ),
            ),
            summary_row(
                combined,
                "ALL_REVIEW_CASES",
                (
                    "Combined QA preserves OBSERVED, MISSING, NO_SOURCE, and NO_VARIABLE "
                    "as explicit states and detects no zero fallback."
                ),
            ),
        ]
    )


def build_variable_status(combined: pd.DataFrame) -> pd.DataFrame:
    rows = []
    group_columns = [
        "source_output_case",
        "context_variable",
        "context_status",
        "audit_status",
    ]
    for keys, group in combined.groupby(group_columns, dropna=False, sort=True):
        rows.append(
            {
                "source_output_case": keys[0],
                "context_variable": keys[1],
                "context_status": keys[2],
                "audit_status": keys[3],
                "row_count": int(len(group)),
                "obs_count_total_window_sum": numeric_sum(
                    group, "obs_count_total_window"
                ),
                "obs_count_nonnull_sum": numeric_sum(group, "obs_count_nonnull"),
                "obs_count_null_sum": numeric_sum(group, "obs_count_null"),
                "obs_count_zero_sum": numeric_sum(group, "obs_count_zero"),
                "obs_count_positive_sum": numeric_sum(group, "obs_count_positive"),
                "observed_values_available_count": bool_true_count(
                    group["observed_values_available"]
                ),
                "zero_fallback_true_count": bool_true_count(
                    group["zero_fallback_used"]
                ),
            }
        )
    return pd.DataFrame(rows)


def representative_review(
    station_id: str,
    station_name: str,
    distance_m: float | None,
    rank: int | None,
    smoke_hint: str,
) -> tuple[str, str]:
    if station_id == "CAA020":
        return (
            "COUNTEREXAMPLE_NOT_MOUNTAIN_REPRESENTATIVE",
            (
                "CAA020 is the National Freeway 1 S026K station in Sanchong, "
                "11.6 km from the activity and rank 15. Observation availability "
                "does not make it representative of mountain-route weather."
            ),
        )

    primary_ids = {"466930", "466910", "C0AC40", "A0A460"}
    if station_id in primary_ids:
        return (
            "PRIMARY_NEARBY_MOUNTAIN_REVIEW_SET",
            (
                f"{station_name} is in the nearest four stations by activity-track "
                "distance and is suitable for focused representativeness review; "
                "distance rank alone is not final weather representativeness."
            ),
        )

    if smoke_hint == "LIKELY_REPRESENTATIVE_MOUNTAIN_OR_NEARBY_STATION":
        return (
            "NEARBY_REVIEW_CANDIDATE",
            (
                "The GPX smoke test marks this as a nearby candidate, but formal "
                "representativeness still requires terrain, elevation, and source-quality review."
            ),
        )

    if distance_m is not None and distance_m <= 5000:
        return (
            "NEARBY_REVIEW_CANDIDATE",
            "Within 5 km of the activity track; retain for review without treating distance as proof.",
        )

    rank_text = str(rank) if rank is not None else "unknown"
    return (
        "LOWER_PRIORITY_DISTANCE_OR_CONTEXT",
        (
            f"Distance/rank evidence is lower priority (rank {rank_text}); "
            "observation presence alone is insufficient for mountain representativeness."
        ),
    )


def build_station_review(
    combined: pd.DataFrame,
    smoke_stations: pd.DataFrame,
) -> pd.DataFrame:
    station_rows = combined[
        combined["station_id"].notna()
        & combined["station_id"].astype(str).str.strip().ne("")
    ].copy()
    smoke_by_id = {}
    if not smoke_stations.empty and "station_id" in smoke_stations.columns:
        for _, row in smoke_stations.iterrows():
            smoke_by_id[str(row["station_id"])] = row.to_dict()

    rows = []
    for (source_output_case, station_id), group in station_rows.groupby(
        ["source_output_case", "station_id"],
        sort=True,
    ):
        first = group.sort_values("station_rank_by_distance").iloc[0]
        station_id = str(station_id)
        smoke = smoke_by_id.get(station_id, {})
        distance = pd.to_numeric(
            pd.Series([first.get("nearest_activity_dist_m")]), errors="coerce"
        ).iloc[0]
        rank = pd.to_numeric(
            pd.Series([first.get("station_rank_by_distance")]), errors="coerce"
        ).iloc[0]
        distance_value = float(distance) if pd.notna(distance) else None
        rank_value = int(rank) if pd.notna(rank) else None
        review, reason = representative_review(
            station_id,
            str(first.get("station_name", "")),
            distance_value,
            rank_value,
            str(smoke.get("representative_candidate_hint", "")),
        )
        rows.append(
            {
                "source_output_case": source_output_case,
                "station_id": station_id,
                "station_name": first.get("station_name", ""),
                "county_name": first.get("county_name", ""),
                "town_name": first.get("town_name", ""),
                "nearest_activity_dist_m": (
                    distance_value if distance_value is not None else ""
                ),
                "station_rank_by_distance": (
                    rank_value if rank_value is not None else ""
                ),
                "station_elevation_m": first.get("station_elevation_m", ""),
                "observed_variable_count": int(
                    (group["context_status"] == "OBSERVED").sum()
                ),
                "missing_variable_count": int(
                    (group["context_status"] == "MISSING").sum()
                ),
                "observed_precipitation_zero_rows": int(
                    observed_zero_precipitation_mask(group).sum()
                ),
                "representativeness_review": review,
                "representativeness_reason": reason,
                "zero_fallback_true_count": bool_true_count(
                    group["zero_fallback_used"]
                ),
            }
        )

    return pd.DataFrame(rows).sort_values(
        ["source_output_case", "station_rank_by_distance", "station_id"],
        na_position="last",
    )


def collect_zero_fallback_audit(
    backend_path: Path,
    gpx_path: Path,
    availability_root: Path,
    gpx_smoke_root: Path,
) -> pd.DataFrame:
    input_files = [
        backend_path,
        backend_path.with_name("activity_environment_window_adapter_summary.csv"),
        gpx_path,
        gpx_path.with_name("activity_environment_window_adapter_summary.csv"),
        find_single(
            availability_root,
            "activity_weather_observation_availability_audit.csv",
        ),
        find_single(
            availability_root,
            "activity_weather_observation_availability_summary.csv",
        ),
        find_single(
            gpx_smoke_root,
            "gpx_weather_observation_nearby_stations.csv",
        ),
        find_single(
            gpx_smoke_root,
            "gpx_weather_observation_smoke_summary.csv",
        ),
    ]

    rows = []
    for path in input_files:
        df = pd.read_csv(path)
        fallback_columns = [
            column
            for column in ["zero_fallback_used", "zero_fallback_detected"]
            if column in df.columns
        ]
        true_count = sum(bool_true_count(df[column]) for column in fallback_columns)
        rows.append(
            {
                "source_file": str(path),
                "row_count": int(len(df)),
                "fallback_columns": "|".join(fallback_columns),
                "zero_fallback_true_count": int(true_count),
            }
        )
    return pd.DataFrame(rows)


def status_distribution_table(summary: pd.DataFrame) -> pd.DataFrame:
    combined = summary[summary["source_output_case"] == "ALL_REVIEW_CASES"].iloc[0]
    return pd.DataFrame(
        [
            {"context_status": "OBSERVED", "row_count": combined["observed_count"]},
            {"context_status": "MISSING", "row_count": combined["missing_count"]},
            {"context_status": "NO_SOURCE", "row_count": combined["no_source_count"]},
            {"context_status": "NO_VARIABLE", "row_count": combined["no_variable_count"]},
        ]
    )


def add_status_classes(table_html: str) -> str:
    for status, css_class in STATUS_CLASS.items():
        table_html = table_html.replace(
            f"<td>{status}</td>",
            f'<td><span class="status {css_class}">{status}</span></td>',
        )
    return table_html


def dataframe_html(
    df: pd.DataFrame,
    columns: list[str] | None = None,
    max_rows: int | None = None,
) -> str:
    view = df.copy()
    if columns is not None:
        view = view[[column for column in columns if column in view.columns]]
    if max_rows is not None:
        view = view.head(max_rows)
    return add_status_classes(
        view.to_html(index=False, escape=True, border=0, classes="data-table")
    )


def build_html(
    summary: pd.DataFrame,
    variable_status: pd.DataFrame,
    station_review: pd.DataFrame,
    zero_audit: pd.DataFrame,
    backend: pd.DataFrame,
    gpx: pd.DataFrame,
    source_files: list[Path],
) -> str:
    combined_status = status_distribution_table(summary)
    backend_summary = summary.iloc[0]
    gpx_summary = summary.iloc[1]
    combined_summary = summary.iloc[2]

    variable_matrix = (
        gpx.groupby(["context_variable", "context_status"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=STATUS_ORDER, fill_value=0)
        .reset_index()
    )

    precipitation_rows = variable_status[
        variable_status["context_variable"].isin(
            [
                "precipitation_mm",
                "precipitation_10min_mm",
                "precipitation_1hr_mm",
            ]
        )
    ].copy()

    nearest_stations = station_review.sort_values(
        ["station_rank_by_distance", "station_id"]
    ).head(15)
    focused_stations = station_review[
        station_review["station_id"].isin(
            ["466930", "466910", "C0AC40", "A0A460", "CAA020"]
        )
    ].sort_values("station_rank_by_distance")
    caa020 = focused_stations[focused_stations["station_id"] == "CAA020"]

    zero_total_rows = int(zero_audit["row_count"].sum())
    zero_true = int(zero_audit["zero_fallback_true_count"].sum())
    source_list = "".join(
        f"<li><code>{html.escape(str(path))}</code></li>" for path in source_files
    )

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>IB3W Environment Window Review Report v1</title>
<style>
:root {{
  --bg: #f4f7f9;
  --panel: #ffffff;
  --ink: #1f2937;
  --muted: #5f6b76;
  --border: #d9e1e7;
  --observed: #177245;
  --observed-bg: #e8f6ee;
  --missing: #9a6700;
  --missing-bg: #fff4ce;
  --no-source: #6b4fa1;
  --no-source-bg: #f0eafd;
  --violation: #b42318;
  --violation-bg: #feeceb;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.5;
}}
header {{
  background: #18344a;
  color: white;
  padding: 28px max(24px, calc((100vw - 1440px) / 2));
}}
header h1 {{ margin: 0 0 6px; font-size: 28px; }}
header p {{ margin: 0; color: #dce8f0; }}
main {{ max-width: 1440px; margin: 0 auto; padding: 24px; }}
section {{
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 20px;
  margin-bottom: 18px;
}}
h2 {{ margin-top: 0; font-size: 20px; }}
h3 {{ margin-bottom: 8px; }}
.cards {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}}
.card {{
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px;
  background: #fbfcfd;
}}
.card strong {{ display: block; font-size: 24px; }}
.card span {{ color: var(--muted); font-size: 13px; }}
.callout {{
  border-left: 5px solid #2b6f96;
  background: #eef7fc;
  padding: 12px 14px;
  margin: 12px 0;
}}
.qa-pass {{
  border-left-color: var(--observed);
  background: var(--observed-bg);
}}
.qa-fail {{
  border-left-color: var(--violation);
  background: var(--violation-bg);
}}
.table-wrap {{ overflow-x: auto; }}
table.data-table {{
  border-collapse: collapse;
  width: 100%;
  font-size: 12px;
}}
.data-table th, .data-table td {{
  border: 1px solid var(--border);
  padding: 6px 8px;
  text-align: left;
  vertical-align: top;
}}
.data-table th {{
  background: #edf2f5;
  position: sticky;
  top: 0;
}}
.status {{
  display: inline-block;
  border-radius: 999px;
  padding: 2px 8px;
  font-weight: 700;
}}
.status-observed {{ color: var(--observed); background: var(--observed-bg); }}
.status-missing {{ color: var(--missing); background: var(--missing-bg); }}
.status-no-source, .status-no-variable {{
  color: var(--no-source);
  background: var(--no-source-bg);
}}
code {{ color: #18344a; overflow-wrap: anywhere; }}
.muted {{ color: var(--muted); }}
ul {{ padding-left: 22px; }}
</style>
</head>
<body>
<header>
  <h1>IB3W Environment Window Review Report v1</h1>
  <p>Review and QA only. No adapter rewrite, weather fusion, risk adjustment, or fallback imputation.</p>
</header>
<main>
<section>
  <h2>1. Scope and guardrails</h2>
  <div class="callout">
    Missing weather is not zero. Observed zero precipitation is raw observed zero.
    Distance rank is not weather representativeness. Station elevation confidence is
    not weather representativeness.
  </div>
  <div class="cards">
    <div class="card"><strong>{int(combined_summary["row_count"])}</strong><span>adapter evidence rows</span></div>
    <div class="card"><strong>{int(combined_summary["observed_count"])}</strong><span>OBSERVED rows</span></div>
    <div class="card"><strong>{int(combined_summary["missing_count"])}</strong><span>MISSING rows</span></div>
    <div class="card"><strong>{zero_true}</strong><span>zero fallback violations</span></div>
  </div>
</section>

<section>
  <h2>2. Backend 2024 negative evidence</h2>
  <p>
    {int(backend_summary["activity_count"])} activities × 10 variables =
    {int(backend_summary["row_count"])} rows. All rows are MISSING because the
    activity windows are outside the weather observation range.
  </p>
  <div class="table-wrap">{dataframe_html(summary.iloc[[0]])}</div>
</section>

<section>
  <h2>3. GPX 2026 positive evidence</h2>
  <p>
    {int(gpx_summary["activity_count"])} activity, {int(gpx_summary["station_count"])}
    stations, {int(gpx_summary["row_count"])} rows:
    {int(gpx_summary["observed_count"])} OBSERVED and
    {int(gpx_summary["missing_count"])} MISSING.
  </p>
  <div class="table-wrap">{dataframe_html(summary.iloc[[1]])}</div>
</section>

<section>
  <h2>4. Context-status distribution</h2>
  <p>NO_SOURCE and NO_VARIABLE are valid adapter states and remain visible even when their count is zero.</p>
  <div class="table-wrap">{dataframe_html(combined_status)}</div>
</section>

<section>
  <h2>5. Variable coverage matrix</h2>
  <div class="table-wrap">{dataframe_html(variable_matrix)}</div>
</section>

<section>
  <h2>6. Observed zero vs missing precipitation</h2>
  <div class="callout">
    <code>precipitation_mm</code> has raw non-null zero observations and is OBSERVED.
    <code>precipitation_10min_mm</code> and <code>precipitation_1hr_mm</code> are null
    and remain MISSING. A displayed zero is never inferred from missingness.
  </div>
  <div class="table-wrap">{dataframe_html(precipitation_rows)}</div>
</section>

<section>
  <h2>7. Nearest station table</h2>
  <div class="table-wrap">{dataframe_html(nearest_stations, [
      "station_rank_by_distance", "station_id", "station_name", "county_name",
      "town_name", "nearest_activity_dist_m", "station_elevation_m",
      "observed_variable_count", "missing_variable_count",
      "observed_precipitation_zero_rows"
  ])}</div>
</section>

<section>
  <h2>8. Station representativeness review</h2>
  <p>
    The focused review set contains Yangmingshan, Anbu, Datunshan, and Chinese Culture
    University as the nearest four stations. This is a review shortlist, not a formal
    fusion decision.
  </p>
  <div class="table-wrap">{dataframe_html(focused_stations)}</div>
</section>

<section>
  <h2>9. CAA020 counterexample</h2>
  <div class="callout">
    CAA020 (National Freeway 1 S026K, Sanchong) demonstrates that observation
    availability does not establish mountain-route representativeness.
  </div>
  <div class="table-wrap">{dataframe_html(caa020)}</div>
</section>

<section>
  <h2>10. Zero-fallback audit</h2>
  <div class="callout {"qa-pass" if zero_true == 0 else "qa-fail"}">
    Reviewed {zero_total_rows} rows across adapter, availability-audit, and GPX-smoke
    outputs. zero_fallback_used=True count: <strong>{zero_true}</strong>.
  </div>
  <div class="table-wrap">{dataframe_html(zero_audit)}</div>
</section>

<section>
  <h2>11. Source files and methodology limitations</h2>
  <ul>{source_list}</ul>
  <ul>
    <li>This report consumes existing CSV outputs and does not query or modify the weather DB.</li>
    <li>Distance rank is geometric proximity only.</li>
    <li>No weather fusion, risk score, radar, THCI, or time-model adjustment is performed.</li>
    <li>Missing values remain missing; observed zero requires raw non-null observations.</li>
  </ul>
</section>
</main>
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    backend_path = resolve_existing(
        args.backend_output_csv,
        DEFAULT_BACKEND_CANDIDATES,
        "backend adapter output",
    )
    gpx_path = resolve_existing(
        args.gpx_output_csv,
        DEFAULT_GPX_CANDIDATES,
        "GPX adapter output",
    )

    availability_audit = find_single(
        args.availability_root,
        "activity_weather_observation_availability_audit.csv",
    )
    availability_summary = find_single(
        args.availability_root,
        "activity_weather_observation_availability_summary.csv",
    )
    gpx_smoke_stations_path = find_single(
        args.gpx_smoke_root,
        "gpx_weather_observation_nearby_stations.csv",
    )
    gpx_smoke_summary = find_single(
        args.gpx_smoke_root,
        "gpx_weather_observation_smoke_summary.csv",
    )

    backend = read_adapter_output(backend_path, "BACKEND_2024_NEGATIVE")
    gpx = read_adapter_output(gpx_path, "GPX_2026_POSITIVE")
    combined = pd.concat([backend, gpx], ignore_index=True)
    smoke_stations = pd.read_csv(gpx_smoke_stations_path)

    summary = build_review_summary(backend, gpx)
    variable_status = build_variable_status(combined)
    station_review = build_station_review(combined, smoke_stations)
    zero_audit = collect_zero_fallback_audit(
        backend_path,
        gpx_path,
        args.availability_root,
        args.gpx_smoke_root,
    )

    source_files = [
        backend_path,
        backend_path.with_name("activity_environment_window_adapter_summary.csv"),
        gpx_path,
        gpx_path.with_name("activity_environment_window_adapter_summary.csv"),
        availability_audit,
        availability_summary,
        gpx_smoke_stations_path,
        gpx_smoke_summary,
    ]
    report_html = build_html(
        summary,
        variable_status,
        station_review,
        zero_audit,
        backend,
        gpx,
        source_files,
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    summary_csv = args.out_dir / "environment_window_review_summary.csv"
    variable_csv = args.out_dir / "environment_window_variable_status.csv"
    station_csv = args.out_dir / "environment_window_station_review.csv"
    html_path = args.out_dir / "environment_window_review_report.html"

    summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")
    variable_status.to_csv(variable_csv, index=False, encoding="utf-8-sig")
    station_review.to_csv(station_csv, index=False, encoding="utf-8-sig")
    html_path.write_text(report_html, encoding="utf-8")

    print("IB3W environment window review report v1 written")
    print("output_dir:", args.out_dir)
    print("summary_csv:", summary_csv)
    print("variable_status_csv:", variable_csv)
    print("station_review_csv:", station_csv)
    print("html_report:", html_path)
    print()
    print("summary:")
    print(summary.to_string(index=False))
    print()
    print("status_distribution:")
    print(status_distribution_table(summary).to_string(index=False))
    print()
    print("station_review_top10:")
    print(
        station_review[
            [
                "station_rank_by_distance",
                "station_id",
                "station_name",
                "nearest_activity_dist_m",
                "representativeness_review",
            ]
        ]
        .head(10)
        .to_string(index=False)
    )
    print()
    print("zero_fallback_QA:")
    print(zero_audit.to_string(index=False))
    print(
        "zero_fallback_true_total:",
        int(zero_audit["zero_fallback_true_count"].sum()),
    )


if __name__ == "__main__":
    main()
