from __future__ import annotations

import argparse
import html
from pathlib import Path
from typing import Any

import pandas as pd


SCHEMA_VERSION = "ib3w_station_representativeness_policy_v1"

DEFAULT_STATION_REVIEW_CSV = Path(
    "outputs/ib3w_environment_window_review_report_v1/"
    "environment_window_station_review.csv"
)

DEFAULT_OUT_DIR = Path("outputs/ib3w_station_representativeness_policy_v1")

PRIMARY_MOUNTAIN_STATION_IDS = {"466930", "466910", "C0AC40", "A0A460"}
KNOWN_COUNTEREXAMPLE_STATION_IDS = {"CAA020"}

STATUS_ORDER = [
    "PRIMARY_MOUNTAIN_REPRESENTATIVE_CANDIDATE",
    "NEARBY_SECONDARY_REVIEW_CANDIDATE",
    "LOWLAND_OR_URBAN_LOW_PRIORITY",
    "LOW_PRIORITY_REGIONAL_OBSERVATION_ONLY",
    "MISSING_STATION_ELEVATION_EVIDENCE",
    "COUNTEREXAMPLE_NOT_MOUNTAIN_REPRESENTATIVE",
    "ROAD_OR_HIGHWAY_STATION_EXCLUDED",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build IB3W station representativeness policy review v1."
    )
    parser.add_argument(
        "--station-review-csv",
        type=Path,
        default=DEFAULT_STATION_REVIEW_CSV,
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def read_station_review(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"station review CSV not found: {path}")

    df = pd.read_csv(path, dtype={"station_id": str})

    required = [
        "source_output_case",
        "station_id",
        "station_name",
        "county_name",
        "town_name",
        "nearest_activity_dist_m",
        "station_rank_by_distance",
        "weather_db_station_elevation_m",
        "nlsc_station_elevation_m",
        "station_elevation_status",
        "station_elevation_confidence",
        "station_elevation_nlsc_tile",
        "station_elevation_context_status",
        "station_elevation_policy_action",
        "station_elevation_context_class",
        "station_elevation_join_status",
        "observed_variable_count",
        "missing_variable_count",
        "observed_precipitation_zero_rows",
        "representativeness_review",
        "representativeness_reason",
        "zero_fallback_true_count",
    ]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"station review CSV missing columns: {missing}")

    return df


def to_float(value: Any) -> float | None:
    value = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return float(value) if pd.notna(value) else None


def to_int(value: Any) -> int | None:
    value = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return int(value) if pd.notna(value) else None


def is_blank(value: Any) -> bool:
    return pd.isna(value) or str(value).strip() == ""


def distance_band(distance_m: float | None) -> str:
    if distance_m is None:
        return "UNKNOWN_DISTANCE"
    if distance_m <= 2000:
        return "WITHIN_2KM"
    if distance_m <= 5000:
        return "WITHIN_5KM"
    if distance_m <= 10000:
        return "WITHIN_10KM"
    return "OVER_10KM"


def elevation_band(elevation_m: float | None) -> str:
    if elevation_m is None:
        return "UNKNOWN_ELEVATION"
    if elevation_m >= 800:
        return "MOUNTAIN_HIGH_ELEVATION"
    if elevation_m >= 300:
        return "MOUNTAIN_OR_HILLSIDE_ELEVATION"
    if elevation_m >= 100:
        return "LOW_HILLS_OR_URBAN_EDGE"
    return "LOWLAND_URBAN_ELEVATION"


def classify_station(row: pd.Series) -> dict[str, Any]:
    station_id = str(row["station_id"]).strip()
    station_name = str(row.get("station_name", "")).strip()
    town_name = str(row.get("town_name", "")).strip()

    distance_m = to_float(row.get("nearest_activity_dist_m"))
    rank = to_int(row.get("station_rank_by_distance"))
    elevation_m = to_float(row.get("nlsc_station_elevation_m"))
    elevation_confidence = str(row.get("station_elevation_confidence", "")).strip()
    elevation_context_status = str(
        row.get("station_elevation_context_status", "")
    ).strip()
    elevation_policy_action = str(
        row.get("station_elevation_policy_action", "")
    ).strip()
    elevation_context_class = str(
        row.get("station_elevation_context_class", "")
    ).strip()
    elevation_join_status = str(
        row.get("station_elevation_join_status", "")
    ).strip()

    observed_variable_count = to_int(row.get("observed_variable_count")) or 0
    zero_fallback_true_count = to_int(row.get("zero_fallback_true_count")) or 0

    dist_band = distance_band(distance_m)
    elev_band = elevation_band(elevation_m)

    has_elevation_evidence = (
        elevation_m is not None
        and not is_blank(elevation_confidence)
        and elevation_join_status == "JOINED_STATION_ELEVATION_REVIEW"
    )

    is_road_or_highway_context = (
        "ROAD" in elevation_context_class.upper()
        or "HIGHWAY" in elevation_context_class.upper()
        or "國一" in station_name
        or station_id in KNOWN_COUNTEREXAMPLE_STATION_IDS
    )

    if zero_fallback_true_count > 0:
        return {
            "station_policy_class": "POLICY_QA_FAILED_ZERO_FALLBACK",
            "selection_action": "BLOCK_UNTIL_QA_FIXED",
            "selection_priority": 999,
            "distance_band": dist_band,
            "elevation_band": elev_band,
            "eligible_for_mountain_representative_selection": False,
            "policy_reason": (
                "zero_fallback_true_count is non-zero; station selection must not proceed."
            ),
        }

    if station_id in KNOWN_COUNTEREXAMPLE_STATION_IDS:
        return {
            "station_policy_class": "COUNTEREXAMPLE_NOT_MOUNTAIN_REPRESENTATIVE",
            "selection_action": "EXCLUDE_FROM_MOUNTAIN_REPRESENTATIVE_SELECTION",
            "selection_priority": 900,
            "distance_band": dist_band,
            "elevation_band": elev_band,
            "eligible_for_mountain_representative_selection": False,
            "policy_reason": (
                "Station is the documented CAA020 counterexample from the station-elevation "
                "and environment-window review. It has observations but is a road/highway "
                "station and must not be treated as representative of mountain-route weather."
            ),
        }

    if is_road_or_highway_context:
        return {
            "station_policy_class": "ROAD_OR_HIGHWAY_STATION_EXCLUDED",
            "selection_action": "EXCLUDE_FROM_MOUNTAIN_REPRESENTATIVE_SELECTION",
            "selection_priority": 910 + (rank or 0),
            "distance_band": dist_band,
            "elevation_band": elev_band,
            "eligible_for_mountain_representative_selection": False,
            "policy_reason": (
                "Station appears to be a road/highway station. Observation availability "
                "is retained as evidence, but the station is excluded from mountain-route "
                "representative selection."
            ),
        }

    if not has_elevation_evidence:
        return {
            "station_policy_class": "MISSING_STATION_ELEVATION_EVIDENCE",
            "selection_action": "REVIEW_REQUIRED_NOT_SELECTED",
            "selection_priority": 800,
            "distance_band": dist_band,
            "elevation_band": elev_band,
            "eligible_for_mountain_representative_selection": False,
            "policy_reason": (
                "Station has incomplete NLSC/context-adjusted elevation evidence; "
                "retain as observation candidate but do not select as mountain representative."
            ),
        }

    if station_id in PRIMARY_MOUNTAIN_STATION_IDS:
        return {
            "station_policy_class": "PRIMARY_MOUNTAIN_REPRESENTATIVE_CANDIDATE",
            "selection_action": "RETAIN_FOR_REPRESENTATIVE_SELECTION",
            "selection_priority": 10 + (rank or 0),
            "distance_band": dist_band,
            "elevation_band": elev_band,
            "eligible_for_mountain_representative_selection": True,
            "policy_reason": (
                "Station is in the predefined nearest mountain review set, has joined "
                "NLSC elevation evidence, and remains a candidate rather than a fusion decision."
            ),
        }

    if (
        distance_m is not None
        and distance_m <= 7000
        and elevation_m is not None
        and elevation_m >= 300
        and elevation_confidence in {"good", "moderate"}
        and observed_variable_count >= 1
    ):
        return {
            "station_policy_class": "NEARBY_SECONDARY_REVIEW_CANDIDATE",
            "selection_action": "RETAIN_FOR_SECONDARY_REVIEW",
            "selection_priority": 100 + (rank or 0),
            "distance_band": dist_band,
            "elevation_band": elev_band,
            "eligible_for_mountain_representative_selection": False,
            "policy_reason": (
                "Station is near the activity and has hillside/mountain elevation evidence, "
                "but is not in the primary representative set."
            ),
        }

    if elevation_m is not None and elevation_m < 300:
        return {
            "station_policy_class": "LOWLAND_OR_URBAN_LOW_PRIORITY",
            "selection_action": "OBSERVATION_ONLY_LOW_PRIORITY",
            "selection_priority": 500 + (rank or 0),
            "distance_band": dist_band,
            "elevation_band": elev_band,
            "eligible_for_mountain_representative_selection": False,
            "policy_reason": (
                "Station has observations but NLSC elevation suggests lowland or urban-edge context; "
                "do not treat as mountain-route representative."
            ),
        }

    if distance_m is not None and distance_m > 10000:
        return {
            "station_policy_class": "LOW_PRIORITY_REGIONAL_OBSERVATION_ONLY",
            "selection_action": "OBSERVATION_ONLY_LOW_PRIORITY",
            "selection_priority": 600 + (rank or 0),
            "distance_band": dist_band,
            "elevation_band": elev_band,
            "eligible_for_mountain_representative_selection": False,
            "policy_reason": (
                "Station is beyond 10 km from the activity track; observation presence is retained "
                "only as regional context."
            ),
        }

    return {
        "station_policy_class": "LOW_PRIORITY_REGIONAL_OBSERVATION_ONLY",
        "selection_action": "OBSERVATION_ONLY_LOW_PRIORITY",
        "selection_priority": 700 + (rank or 0),
        "distance_band": dist_band,
        "elevation_band": elev_band,
        "eligible_for_mountain_representative_selection": False,
        "policy_reason": (
            "Station does not meet primary or secondary representative criteria."
        ),
    }


def build_policy_review(station_review: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in station_review.iterrows():
        policy = classify_station(row)
        out = row.to_dict()
        out.update(
            {
                "schema_version": SCHEMA_VERSION,
                "station_policy_class": policy["station_policy_class"],
                "selection_action": policy["selection_action"],
                "selection_priority": policy["selection_priority"],
                "distance_band": policy["distance_band"],
                "elevation_band": policy["elevation_band"],
                "eligible_for_mountain_representative_selection": policy[
                    "eligible_for_mountain_representative_selection"
                ],
                "policy_reason": policy["policy_reason"],
            }
        )
        rows.append(out)

    df = pd.DataFrame(rows)
    return df.sort_values(
        ["selection_priority", "station_rank_by_distance", "station_id"],
        na_position="last",
    )


def build_summary(policy_review: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for station_policy_class, group in policy_review.groupby(
        "station_policy_class", dropna=False, sort=False
    ):
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "summary_type": "station_policy_class",
                "summary_key": station_policy_class,
                "station_count": int(len(group)),
                "eligible_count": int(
                    group["eligible_for_mountain_representative_selection"]
                    .astype(str)
                    .str.lower()
                    .eq("true")
                    .sum()
                ),
                "zero_fallback_true_count": int(
                    pd.to_numeric(
                        group["zero_fallback_true_count"], errors="coerce"
                    )
                    .fillna(0)
                    .sum()
                ),
            }
        )

    for action, group in policy_review.groupby(
        "selection_action", dropna=False, sort=False
    ):
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "summary_type": "selection_action",
                "summary_key": action,
                "station_count": int(len(group)),
                "eligible_count": int(
                    group["eligible_for_mountain_representative_selection"]
                    .astype(str)
                    .str.lower()
                    .eq("true")
                    .sum()
                ),
                "zero_fallback_true_count": int(
                    pd.to_numeric(
                        group["zero_fallback_true_count"], errors="coerce"
                    )
                    .fillna(0)
                    .sum()
                ),
            }
        )

    rows.append(
        {
            "schema_version": SCHEMA_VERSION,
            "summary_type": "overall",
            "summary_key": "ALL_STATIONS",
            "station_count": int(len(policy_review)),
            "eligible_count": int(
                policy_review["eligible_for_mountain_representative_selection"]
                .astype(str)
                .str.lower()
                .eq("true")
                .sum()
            ),
            "zero_fallback_true_count": int(
                pd.to_numeric(
                    policy_review["zero_fallback_true_count"], errors="coerce"
                )
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
        view = view[[column for column in columns if column in view.columns]]
    if max_rows is not None:
        view = view.head(max_rows)
    view = view.fillna("")
    return view.to_html(index=False, escape=True, border=0, classes="data-table")


def build_html_report(
    policy_review: pd.DataFrame,
    summary: pd.DataFrame,
    source_csv: Path,
) -> str:
    class_counts = (
        policy_review.groupby("station_policy_class")
        .size()
        .reset_index(name="station_count")
        .sort_values("station_count", ascending=False)
    )

    primary = policy_review[
        policy_review["station_policy_class"]
        == "PRIMARY_MOUNTAIN_REPRESENTATIVE_CANDIDATE"
    ]
    secondary = policy_review[
        policy_review["station_policy_class"]
        == "NEARBY_SECONDARY_REVIEW_CANDIDATE"
    ]
    counterexamples = policy_review[
        policy_review["station_policy_class"]
        == "COUNTEREXAMPLE_NOT_MOUNTAIN_REPRESENTATIVE"
    ]
    road_highway_excluded = policy_review[
        policy_review["station_policy_class"]
        == "ROAD_OR_HIGHWAY_STATION_EXCLUDED"
    ]
    missing_elev = policy_review[
        policy_review["station_policy_class"]
        == "MISSING_STATION_ELEVATION_EVIDENCE"
    ]

    eligible_count = int(
        policy_review["eligible_for_mountain_representative_selection"]
        .astype(str)
        .str.lower()
        .eq("true")
        .sum()
    )
    zero_fallback_true_count = int(
        pd.to_numeric(policy_review["zero_fallback_true_count"], errors="coerce")
        .fillna(0)
        .sum()
    )

    key_cols = [
        "selection_priority",
        "station_rank_by_distance",
        "station_id",
        "station_name",
        "county_name",
        "town_name",
        "nearest_activity_dist_m",
        "nlsc_station_elevation_m",
        "station_elevation_confidence",
        "station_elevation_context_status",
        "station_policy_class",
        "selection_action",
        "eligible_for_mountain_representative_selection",
        "policy_reason",
    ]

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>IB3W Station Representativeness Policy v1</title>
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
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
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
  <h1>IB3W Station Representativeness Policy v1</h1>
  <p>Policy review only. No weather fusion, no risk score, no missing-to-zero imputation.</p>
</header>
<main>
<section>
  <h2>1. Scope and guardrails</h2>
  <div class="callout">
    Distance rank is not weather representativeness. Station elevation evidence is
    separate from station selection. Observation availability alone does not make a
    station representative of mountain-route weather.
  </div>
  <div class="cards">
    <div class="card"><strong>{len(policy_review)}</strong><span>stations reviewed</span></div>
    <div class="card"><strong>{eligible_count}</strong><span>eligible primary representative candidates</span></div>
    <div class="card"><strong>{len(counterexamples)}</strong><span>counterexamples excluded</span></div>
    <div class="card"><strong>{zero_fallback_true_count}</strong><span>zero fallback violations</span></div>
  </div>
</section>

<section>
  <h2>2. Policy class distribution</h2>
  <div class="table-wrap">{html_table(class_counts)}</div>
</section>

<section>
  <h2>3. Primary mountain representative candidates</h2>
  <div class="table-wrap">{html_table(primary, key_cols)}</div>
</section>

<section>
  <h2>4. Nearby secondary review candidates</h2>
  <div class="table-wrap">{html_table(secondary, key_cols)}</div>
</section>

<section>
  <h2>5. Counterexamples excluded from mountain representative selection</h2>
  <div class="table-wrap">{html_table(counterexamples, key_cols)}</div>
</section>

<section>
  <h2>6. Road/highway stations excluded</h2>
  <p>
    These stations may have observations, but their road/highway context excludes them
    from mountain-route representative selection.
  </p>
  <div class="table-wrap">{html_table(road_highway_excluded, key_cols)}</div>
</section>

<section>
  <h2>7. Missing station elevation evidence</h2>
  <p>These rows are retained for observation audit but are not selected for mountain representativeness.</p>
  <div class="table-wrap">{html_table(missing_elev, key_cols, max_rows=30)}</div>
</section>

<section>
  <h2>8. Full station policy review</h2>
  <div class="table-wrap">{html_table(policy_review, key_cols)}</div>
</section>

<section>
  <h2>9. Source and limitations</h2>
  <ul>
    <li>Source CSV: <code>{html.escape(str(source_csv))}</code></li>
    <li>No weather DB query is performed in this policy layer.</li>
    <li>No station fusion decision is made here.</li>
    <li>Missing station elevation remains missing and is never filled with zero.</li>
  </ul>
</section>
</main>
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    station_review = read_station_review(args.station_review_csv)
    policy_review = build_policy_review(station_review)
    summary = build_summary(policy_review)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    policy_csv = args.out_dir / "station_representativeness_policy_review.csv"
    summary_csv = args.out_dir / "station_representativeness_policy_summary.csv"
    html_path = args.out_dir / "station_representativeness_policy_report.html"

    policy_review.to_csv(policy_csv, index=False, encoding="utf-8-sig")
    summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")
    html_path.write_text(
        build_html_report(policy_review, summary, args.station_review_csv),
        encoding="utf-8",
    )

    print("IB3W station representativeness policy v1 written")
    print("policy_csv:", policy_csv)
    print("summary_csv:", summary_csv)
    print("html_report:", html_path)
    print()
    print("policy_class_distribution:")
    print(
        policy_review.groupby("station_policy_class")
        .size()
        .reset_index(name="station_count")
        .sort_values("station_count", ascending=False)
        .to_string(index=False)
    )
    print()
    print("primary_candidates:")
    print(
        policy_review[
            policy_review["station_policy_class"]
            == "PRIMARY_MOUNTAIN_REPRESENTATIVE_CANDIDATE"
        ][
            [
                "station_rank_by_distance",
                "station_id",
                "station_name",
                "nearest_activity_dist_m",
                "nlsc_station_elevation_m",
                "station_elevation_confidence",
                "station_policy_class",
            ]
        ].to_string(index=False)
    )
    print()
    print("counterexamples:")
    print(
        policy_review[
            policy_review["station_policy_class"]
            == "COUNTEREXAMPLE_NOT_MOUNTAIN_REPRESENTATIVE"
        ][
            [
                "station_rank_by_distance",
                "station_id",
                "station_name",
                "nearest_activity_dist_m",
                "nlsc_station_elevation_m",
                "station_elevation_confidence",
                "station_policy_class",
            ]
        ].to_string(index=False)
    )
    print()
    print("zero_fallback_true_total:", int(
        pd.to_numeric(policy_review["zero_fallback_true_count"], errors="coerce")
        .fillna(0)
        .sum()
    ))


if __name__ == "__main__":
    main()
