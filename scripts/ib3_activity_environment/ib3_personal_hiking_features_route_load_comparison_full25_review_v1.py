from __future__ import annotations

import csv
import html
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = (
    "ib3_personal_hiking_features_route_load_comparison_full25_review_v1"
)

WINDOWS_CSV = Path(
    "outputs/ib3_personal_hiking_features_route_load_comparison_full25_v1/"
    "activity_route_load_behavior_response_windows.csv"
)
SUMMARY_CSV = Path(
    "outputs/ib3_personal_hiking_features_route_load_comparison_full25_v1/"
    "activity_route_load_behavior_response_summary.csv"
)
AUDIT_CSV = Path(
    "outputs/ib3_personal_hiking_features_route_load_comparison_full25_v1/"
    "activity_route_load_behavior_response_full25_audit.csv"
)
SCHEMA_CSV = Path(
    "configs/personal_hiking_features/"
    "ib3_route_load_behavior_response_schema_v1.csv"
)
SCHEMA_MD = Path("docs/ib3_route_load_behavior_response_schema_v1.md")

OUT_ROOT = Path(
    "outputs/"
    "ib3_personal_hiking_features_route_load_comparison_full25_review_v1"
)
OUT_REVIEW_CSV = (
    OUT_ROOT
    / "activity_route_load_behavior_response_full25_descriptive_review.csv"
)
OUT_REPORT_HTML = (
    OUT_ROOT
    / "activity_route_load_behavior_response_full25_descriptive_review_report.html"
)
OUT_ADDENDUM_MD = Path(
    "docs/ib3_route_load_behavior_response_full25_review_addendum_v1.md"
)

REVIEW_FIELDS = [
    "schema_version",
    "review_item",
    "review_status",
    "affected_field",
    "finding",
    "interpretation_boundary",
    "recommended_action",
    "safe_for_6_5_1_text",
]

PROHIBITED_OUTPUT_FIELDS = {
    "ability_score",
    "ability_rank",
    "ability_class",
    "thci_score",
    "radar_score",
    "final_hiking_risk_score",
}

PRIMARY_ROUTE_LOAD_FIELDS = [
    "route_profile_elevation_min_m",
    "route_profile_elevation_max_m",
    "route_profile_elevation_range_m",
    "ib2_terrain_evidence_median",
    "ib2_effort_evidence_median",
    "ib2_exposure_evidence_median",
    "ib2_risk_band_evidence",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def as_float(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def pct(count: int, total: int) -> str:
    if total == 0:
        return ""
    return f"{100 * count / total:.2f}%"


def nonblank_count(rows: list[dict[str, str]], field: str) -> int:
    return sum(bool(str(row.get(field, "")).strip()) for row in rows)


def positive_count(rows: list[dict[str, str]], field: str) -> int:
    return sum((as_float(row.get(field)) or 0.0) > 0 for row in rows)


def review_row(
    item: str,
    status: str,
    affected_field: str,
    finding: str,
    boundary: str,
    action: str,
    safe: bool,
) -> dict[str, str]:
    return {
        "schema_version": SCHEMA_VERSION,
        "review_item": item,
        "review_status": status,
        "affected_field": affected_field,
        "finding": finding,
        "interpretation_boundary": boundary,
        "recommended_action": action,
        "safe_for_6_5_1_text": str(safe),
    }


def build_review_rows(
    windows: list[dict[str, str]],
    summaries: list[dict[str, str]],
    audit: dict[str, str],
    schema_rows: list[dict[str, str]],
    schema_text: str,
) -> list[dict[str, str]]:
    window_count = len(windows)
    activity_count = len(summaries)
    route_phase_unknown = sum(
        row.get("route_phase", "") == "UNKNOWN" for row in windows
    )
    slope_coverage = nonblank_count(windows, "calibrated_slope_pct_p75_abs")
    slope_review = sum(
        "SLOPE_REVIEW_PRESENT" in row.get("window_qa_flags", "")
        for row in windows
    )
    movement_review = sum(
        "MOVEMENT_REVIEW_PRESENT" in row.get("window_qa_flags", "")
        for row in windows
    )
    nearest_zero = sum(
        as_float(row.get("nearest_environment_feature_distance_m_min")) == 0
        for row in windows
    )
    road_positive = positive_count(windows, "near_road_ratio")
    cliff_positive = positive_count(windows, "near_cliff_ratio")
    weather_available = sum(
        row.get("weather_context_available", "") == "True"
        for row in summaries
    )
    fixture_contract = (
        any(row.get("field_name") == "fixture_activity" for row in schema_rows)
        and "Fixture scope" in schema_text
    )

    primary_coverage = {
        field: nonblank_count(windows, field)
        for field in PRIMARY_ROUTE_LOAD_FIELDS
    }
    all_primary_complete = all(
        count == window_count for count in primary_coverage.values()
    )

    rows = [
        review_row(
            "FULL25_DESCRIPTIVE_ANALYSIS_SCOPE",
            "USABLE_WITH_BOUNDARIES",
            "full25 evidence layer",
            (
                f"{activity_count} usable activities and {window_count} 50m "
                "route-window rows support descriptive route-load, behavior, "
                "OSM exposure, and activity-level weather context analysis."
            ),
            (
                "Supports descriptive association and coverage summaries only; "
                "does not support ability ranking or causal inference."
            ),
            "Use as the evidence basis for 6.5.1 with all review boundaries retained.",
            True,
        ),
        review_row(
            "ROUTE_PHASE_LIMITATION",
            "BLOCK_DIRECTIONAL_INTERPRETATION",
            "route_phase",
            (
                f"{route_phase_unknown}/{window_count} windows "
                f"({pct(route_phase_unknown, window_count)}) are UNKNOWN."
            ),
            (
                "Full25 evidence cannot distinguish ascent, descent, or a "
                "single directional pass through a route window."
            ),
            "Do not write ascent-versus-descent or pass-specific comparisons.",
            False,
        ),
        review_row(
            "ELAPSED_SPAN_LIMITATION",
            "DO_NOT_INTERPRET_AS_PASS_TIME",
            "elapsed_time_span_sec",
            (
                "The field is max(elapsed_sec)-min(elapsed_sec) inside a route "
                "bin; the same route bin may aggregate observations from "
                "multiple separated periods."
            ),
            "It is an aggregation span, not route-window traversal time.",
            "Exclude from completion-time or single-pass duration statements.",
            False,
        ),
        review_row(
            "POINT_RATIO_NAMING",
            "RENAME_RECOMMENDED",
            "stopped_ratio|low_speed_ratio",
            (
                "Both ratios use point counts as denominators rather than "
                "time-weighted duration."
            ),
            "They describe sampled point proportions, not percentages of time.",
            (
                "Use stopped_point_ratio and low_speed_point_ratio in future "
                "contracts; define the denominator explicitly in 6.5.1."
            ),
            True,
        ),
        review_row(
            "SLOPE_EVIDENCE_LIMITATION",
            "SECONDARY_REVIEW_ONLY",
            "calibrated_slope_pct_median|calibrated_slope_pct_p75_abs",
            (
                f"Slope coverage is {slope_coverage}/{window_count} "
                f"({pct(slope_coverage, window_count)}); "
                f"SLOPE_REVIEW_PRESENT appears in {slope_review}/{window_count} "
                f"windows ({pct(slope_review, window_count)})."
            ),
            "Calibrated slope must not be the primary 6.5.1 route-load source.",
            "Retain only as secondary reviewed context.",
            False,
        ),
        review_row(
            "PRIMARY_ROUTE_LOAD_EVIDENCE",
            "SAFE_DESCRIPTIVE",
            "|".join(PRIMARY_ROUTE_LOAD_FIELDS),
            (
                "All seven preferred route-profile and IB2 evidence fields "
                f"cover {window_count}/{window_count} windows."
                if all_primary_complete
                else f"Primary coverage: {primary_coverage}"
            ),
            (
                "IB2 terrain, effort, exposure, and risk-band fields describe "
                "route evidence and are not personal ability labels."
            ),
            "Use these fields as the primary route-load evidence in 6.5.1.",
            True,
        ),
        review_row(
            "ROUTE_LOAD_RULE_LABEL",
            "RENAME_RECOMMENDED",
            "route_load_context_band",
            (
                "The field is a rule-derived context label combining slope, "
                "IB2 effort evidence, and IB2 risk-band evidence."
            ),
            "It is neither an ability class nor a formal risk score.",
            "Rename to route_load_evidence_rule_label in a future contract.",
            True,
        ),
        review_row(
            "NEAREST_ENVIRONMENT_DISTANCE_LIMITATION",
            "NO_ANALYTIC_DISCRIMINATION",
            "nearest_environment_feature_distance_m_min",
            (
                f"{nearest_zero}/{window_count} values "
                f"({pct(nearest_zero, window_count)}) are zero."
            ),
            "The generic minimum distance cannot distinguish environment exposure.",
            "Do not use; prefer feature-specific near_*_ratio fields.",
            False,
        ),
        review_row(
            "ROAD_CLIFF_EXPOSURE_LIMITATION",
            "NO_COMPARATIVE_VARIATION",
            "near_road_ratio|near_cliff_ratio",
            (
                f"near_road_ratio is positive in {road_positive}/{window_count} "
                f"windows; near_cliff_ratio is positive in "
                f"{cliff_positive}/{window_count} windows."
            ),
            "All-positive or all-zero exposure has no within-dataset contrast.",
            "Exclude road and cliff proximity from comparative claims.",
            False,
        ),
        review_row(
            "OSM_FACILITY_EXPOSURE_BOUNDARY",
            "SAFE_AS_EXPOSURE_ONLY",
            "osm_exposure_types|near_*_ratio",
            (
                "Feature-specific proximity ratios retain mapped environmental "
                "and facility exposure evidence."
            ),
            "Mapped proximity does not prove facility use or behavioral response.",
            "Write exposure, proximity, or mapped context; never write facility use.",
            True,
        ),
        review_row(
            "WEATHER_CONTEXT_LEVEL",
            "ACTIVITY_LEVEL_CONTEXT_ONLY",
            (
                "temperature_c|relative_humidity_pct|precipitation_mm|"
                "wind_speed_ms|wind_gust_ms|uv_index"
            ),
            (
                f"Numeric weather context is available for "
                f"{weather_available}/{activity_count} activities and is "
                "repeated across each activity's route windows."
            ),
            (
                "These fields are activity-level background context, not "
                "window-level instantaneous weather."
            ),
            (
                "Use for descriptive stratification only; do not attribute "
                "single-window speed changes to weather."
            ),
            True,
        ),
        review_row(
            "SCHEMA_FULL25_ALIGNMENT",
            "CONTRACT_ADDENDUM_REQUIRED",
            "fixture_activity|usable_activity|fixture scope",
            (
                "The existing schema and Markdown still describe a three-case "
                "fixture while the full25 output uses usable_activity."
                if fixture_contract
                else "No fixture/full25 contract mismatch detected."
            ),
            "The full25 artifact must not be represented as fully covered by the fixture contract.",
            "Use this addendum until a dedicated full25 schema contract is approved.",
            False,
        ),
        review_row(
            "QA_FLAG_PREVALENCE",
            "REPORT_WITH_CONTEXT",
            "window_qa_flags",
            (
                f"MOVEMENT_REVIEW_PRESENT occurs in {movement_review}/"
                f"{window_count} windows ({pct(movement_review, window_count)})."
            ),
            "A review flag indicates evidence quality review, not weak ability.",
            "Report QA prevalence alongside descriptive findings.",
            True,
        ),
        review_row(
            "NONCANONICAL_ROUTE_BOUNDARY",
            "REVIEW_EVIDENCE_ONLY",
            "wrong_route|off_target",
            (
                f"Audit records {audit.get('wrong_route_review_evidence_row_count')} "
                "wrong-route and "
                f"{audit.get('off_target_review_evidence_row_count')} off-target "
                "rows outside canonical route-load comparison."
            ),
            "Noncanonical rows must not inherit canonical route-load evidence.",
            "Retain counts as review evidence only.",
            True,
        ),
        review_row(
            "LEGACY_AND_SCORING_BOUNDARY",
            "BOUNDARY_PASS",
            (
                "legacy gain|ability score|ability rank|ability class|"
                "THCI|radar|final hiking risk"
            ),
            (
                "Full25 audit reports zero legacy gain use, zero weather "
                "zero-fill, and zero prohibited score/rank/class generation."
            ),
            "The review does not authorize any scoring or personal classification.",
            "Carry the explicit zero-generation boundary into 6.5.1.",
            True,
        ),
        review_row(
            "CAUSAL_AND_PERSONAL_INFERENCE_BOUNDARY",
            "PROHIBITED_CONCLUSION",
            "all descriptive evidence",
            (
                "The evidence is observational, route-window aggregated, and "
                "contains activity-level weather and mapped proximity context."
            ),
            (
                "Do not infer causality, personal ability, personal risk, or "
                "actual facility use."
            ),
            "Limit conclusions to descriptive patterns and evidence coverage.",
            False,
        ),
    ]
    return rows


def html_table(rows: list[dict[str, Any]], fields: list[str]) -> str:
    head = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "".join(
        "<tr>"
        + "".join(
            f"<td>{html.escape(str(row.get(field, '')))}</td>"
            for field in fields
        )
        + "</tr>"
        for row in rows
    )
    return (
        '<div class="table-wrap"><table><thead><tr>'
        + head
        + "</tr></thead><tbody>"
        + body
        + "</tbody></table></div>"
    )


def render_html(
    path: Path,
    review_rows: list[dict[str, str]],
    windows: list[dict[str, str]],
    summaries: list[dict[str, str]],
    audit: dict[str, str],
) -> None:
    route_phase_counts = Counter(row.get("route_phase", "") for row in windows)
    load_fields = PRIMARY_ROUTE_LOAD_FIELDS + [
        "calibrated_slope_pct_p75_abs"
    ]
    behavior_fields = [
        "speed_mps_median",
        "stopped_ratio",
        "low_speed_ratio",
        "heart_rate_bpm_median",
    ]
    exposure_fields = [
        "near_steps_ratio",
        "near_guidepost_ratio",
        "near_shelter_ratio",
        "near_waterway_ratio",
        "near_road_ratio",
        "near_cliff_ratio",
    ]
    coverage_rows = []
    for field in load_fields + behavior_fields:
        count = nonblank_count(windows, field)
        coverage_rows.append(
            {
                "field": field,
                "level": "window",
                "available_count": count,
                "total_count": len(windows),
                "coverage": pct(count, len(windows)),
                "use_note": (
                    "secondary reviewed context"
                    if field == "calibrated_slope_pct_p75_abs"
                    else "descriptive evidence"
                ),
            }
        )
    for field in exposure_fields:
        positive = positive_count(windows, field)
        coverage_rows.append(
            {
                "field": field,
                "level": "window exposure",
                "available_count": positive,
                "total_count": len(windows),
                "coverage": pct(positive, len(windows)),
                "use_note": "positive mapped proximity; not facility use",
            }
        )

    phase_rows = [
        {
            "route_phase": key or "BLANK",
            "window_count": value,
            "window_ratio": pct(value, len(windows)),
        }
        for key, value in sorted(route_phase_counts.items())
    ]

    method_rows = [
        {
            "method_point": "Usable activity gate",
            "text": (
                "Use only the 25 activities accepted by the data-quality "
                "usability gate; retain the review-only case as excluded evidence."
            ),
        },
        {
            "method_point": "Canonical 50m route windows",
            "text": (
                "Aggregate joined canonical route evidence by 50m route-distance "
                "bins; wrong-route and off-target rows remain review evidence."
            ),
        },
        {
            "method_point": "Primary route-load evidence",
            "text": (
                "Prioritize route-profile elevation context and existing IB2 "
                "terrain, effort, exposure, and risk-band evidence."
            ),
        },
        {
            "method_point": "Behavior response",
            "text": (
                "Describe calibrated speed, sampled-point stop/low-speed ratios, "
                "and heart-rate percentiles without deriving ability."
            ),
        },
        {
            "method_point": "Context boundary",
            "text": (
                "Treat OSM proximity and activity-level weather as contextual "
                "evidence, not causal or scoring inputs."
            ),
        },
    ]
    prohibited_rows = [
        {"prohibited_conclusion": text}
        for text in [
            "Do not distinguish ascent from descent while route_phase is UNKNOWN.",
            "Do not interpret elapsed_time_span_sec as route-window traversal time.",
            "Do not infer that route load caused speed, stop, or heart-rate change.",
            "Do not rank or classify personal hiking ability.",
            "Do not interpret IB2 risk evidence as a personal ability or outcome label.",
            "Do not interpret mapped proximity as actual facility use.",
            "Do not treat activity-level weather as window-level instantaneous weather.",
            "Do not use legacy gain fields or generate THCI, radar, or final-risk scores.",
        ]
    ]

    audit_rows = [
        {
            "metric": key,
            "value": audit.get(key, ""),
        }
        for key in [
            "input_usable_activity_count",
            "review_only_excluded_count",
            "output_window_row_count",
            "output_activity_summary_row_count",
            "missing_route_load_evidence_count",
            "missing_behavior_response_evidence_count",
            "missing_weather_context_count",
            "weather_zero_fill_count",
            "legacy_gain_fields_used_count",
            "prohibited_score_rank_class_generated_count",
            "thci_score_generated_count",
            "radar_score_generated_count",
            "final_hiking_risk_score_generated_count",
            "audit_conclusion",
        ]
    ]

    section_groups = {
        "Route phase limitation": {"ROUTE_PHASE_LIMITATION", "ELAPSED_SPAN_LIMITATION"},
        "Slope limitation": {"SLOPE_EVIDENCE_LIMITATION"},
        "Ratio naming limitation": {"POINT_RATIO_NAMING"},
        "OSM / facility exposure limitation": {
            "NEAREST_ENVIRONMENT_DISTANCE_LIMITATION",
            "ROAD_CLIFF_EXPOSURE_LIMITATION",
            "OSM_FACILITY_EXPOSURE_BOUNDARY",
        },
        "Weather context limitation": {"WEATHER_CONTEXT_LEVEL"},
    }
    review_fields = [
        "review_item",
        "review_status",
        "affected_field",
        "finding",
        "interpretation_boundary",
        "recommended_action",
        "safe_for_6_5_1_text",
    ]
    focused_sections = "".join(
        f"<h2>{html.escape(title)}</h2>"
        + html_table(
            [
                row
                for row in review_rows
                if row["review_item"] in item_names
            ],
            review_fields,
        )
        for title, item_names in section_groups.items()
    )

    report = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>IB3 Route Load Behavior Response Full25 Descriptive Review</title>
<style>
body{{font-family:Arial,"Noto Sans TC",sans-serif;margin:24px;color:#1f2933;line-height:1.5}}
.note{{background:#fff8dc;border-left:4px solid #b7791f;padding:12px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin:16px 0}}
.card{{border:1px solid #d8dee4;border-radius:8px;padding:12px;background:#f8fafc}}
.card strong{{display:block;font-size:20px}}.card span{{color:#52606d;font-size:12px}}
.table-wrap{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:12px;margin:12px 0 24px}}
th,td{{border:1px solid #d8dee4;padding:6px;text-align:left;vertical-align:top}}
th{{background:#eef2f6}}
</style>
</head>
<body>
<h1>IB3 Route Load Behavior Response Full25 Descriptive Review</h1>
<p class="note"><strong>Boundary:</strong> This report reviews existing
descriptive evidence only. It does not recalculate the full25 evidence, rank
activities or people, generate an ability score/class, or generate THCI,
radar, or final hiking risk scores.</p>
<div class="cards">
<div class="card"><strong>{len(summaries)}</strong><span>usable activity summaries</span></div>
<div class="card"><strong>{len(windows)}</strong><span>existing 50m window rows reviewed</span></div>
<div class="card"><strong>{len(review_rows)}</strong><span>review items</span></div>
<div class="card"><strong>{html.escape(audit.get("audit_conclusion", ""))}</strong><span>source audit</span></div>
</div>
<h2>Full25 audit summary</h2>
{html_table(audit_rows, ["metric", "value"])}
<h2>Field coverage and usability</h2>
{html_table(coverage_rows, ["field", "level", "available_count", "total_count", "coverage", "use_note"])}
<h2>Route phase coverage</h2>
{html_table(phase_rows, ["route_phase", "window_count", "window_ratio"])}
{focused_sections}
<h2>6.5.1 methodology points that are safe to write</h2>
{html_table(method_rows, ["method_point", "text"])}
<h2>Conclusions that must not be written</h2>
{html_table(prohibited_rows, ["prohibited_conclusion"])}
<h2>Complete review register</h2>
{html_table(review_rows, review_fields)}
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")


def render_addendum(
    path: Path,
    review_rows: list[dict[str, str]],
    windows: list[dict[str, str]],
    summaries: list[dict[str, str]],
    audit: dict[str, str],
) -> None:
    safe_rows = [
        row for row in review_rows if row["safe_for_6_5_1_text"] == "True"
    ]
    blocked_rows = [
        row for row in review_rows if row["safe_for_6_5_1_text"] == "False"
    ]
    text = f"""# IB3 Route Load Behavior Response Full25 Review Addendum v1

## Purpose

This addendum records the descriptive-use boundaries for the existing full25
route-load and behavior-response evidence. It does not modify or recalculate
the source evidence.

Source scope:

- `{WINDOWS_CSV.as_posix()}`
- `{SUMMARY_CSV.as_posix()}`
- `{AUDIT_CSV.as_posix()}`
- `{SCHEMA_CSV.as_posix()}`
- `{SCHEMA_MD.as_posix()}`

Reviewed scope:

- usable activity summaries: {len(summaries)}
- 50m route-window rows: {len(windows)}
- source audit: `{audit.get("audit_conclusion", "")}`

## Primary decision

The full25 evidence can support descriptive analysis of behavior response,
route-load evidence, mapped environment/facility exposure, and activity-level
weather context.

It cannot support personal ability ranking, ability classification, causal
inference, facility-use claims, or weather-attributed route-window effects.

## Route phase and elapsed-span limits

- All route windows have `route_phase=UNKNOWN`.
- The evidence cannot distinguish ascent, descent, or a single directional pass.
- `elapsed_time_span_sec` is an aggregation span and must not be interpreted as
  route-window traversal time.

## Route-load evidence

Use these fields as the primary descriptive route-load evidence:

{chr(10).join(f"- `{field}`" for field in PRIMARY_ROUTE_LOAD_FIELDS)}

`calibrated_slope_pct_median` and `calibrated_slope_pct_p75_abs` are secondary
review-only context because coverage is incomplete and slope review flags are
prevalent.

`route_load_context_band` is a rule-derived evidence label. It is not an
ability class or formal risk score. The recommended future name is
`route_load_evidence_rule_label`.

## Behavior-response naming

- `stopped_ratio` is a sampled-point ratio, not a time ratio.
- `low_speed_ratio` is a sampled-point ratio, not a time ratio.
- Recommended future names are `stopped_point_ratio` and
  `low_speed_point_ratio`.

Speed percentiles and heart-rate percentiles remain descriptive context only.

## OSM and facility exposure

- Feature-specific `near_*_ratio` fields represent mapped proximity exposure.
- Proximity does not prove actual facility use.
- `nearest_environment_feature_distance_m_min` has no useful discrimination
  because all reviewed values are zero.
- `near_road_ratio` has no comparative variation because road exposure is
  positive for all windows.
- `near_cliff_ratio` has no comparative variation because cliff exposure is
  zero for all windows.

## Weather context

Weather fields are attached at activity level and repeated across route
windows. They may be used for descriptive activity-level stratification, but
not as window-level instantaneous weather and not to explain a single-window
speed or heart-rate change.

Missing weather must remain missing and must never be hard-filled as zero.

## Safe 6.5.1 methodology statements

{chr(10).join(f"- **{row['review_item']}**: {row['recommended_action']}" for row in safe_rows)}

## Conclusions that are not supported

{chr(10).join(f"- **{row['review_item']}**: {row['interpretation_boundary']}" for row in blocked_rows)}

## Explicit engineering boundary

This addendum does not generate or authorize:

- ability score
- ability rank
- ability class
- THCI score
- radar score
- final hiking risk score

IB2 risk evidence remains route evidence and must not become a personal ability
label. Legacy gain fields remain blocked as route-load sources.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    windows = read_csv(WINDOWS_CSV)
    summaries = read_csv(SUMMARY_CSV)
    audit_rows = read_csv(AUDIT_CSV)
    schema_rows = read_csv(SCHEMA_CSV)
    schema_text = SCHEMA_MD.read_text(encoding="utf-8")
    if len(audit_rows) != 1:
        raise ValueError("Expected exactly one full25 audit row")
    audit = audit_rows[0]

    review_rows = build_review_rows(
        windows, summaries, audit, schema_rows, schema_text
    )
    generated_fields = set(REVIEW_FIELDS)
    prohibited_generated = sorted(
        generated_fields & PROHIBITED_OUTPUT_FIELDS
    )
    if prohibited_generated:
        raise ValueError(
            "Prohibited generated fields: " + "|".join(prohibited_generated)
        )
    if audit.get("audit_conclusion") != (
        "PASS_ROUTE_LOAD_BEHAVIOR_RESPONSE_FULL25_DESCRIPTIVE_ONLY"
    ):
        raise ValueError("Full25 source audit is not PASS")

    write_csv(OUT_REVIEW_CSV, review_rows)
    render_html(OUT_REPORT_HTML, review_rows, windows, summaries, audit)
    render_addendum(OUT_ADDENDUM_MD, review_rows, windows, summaries, audit)

    print(f"review_item_count={len(review_rows)}")
    print("ability_score_rank_class_generated_count=0")
    print("thci_radar_final_risk_score_generated_count=0")
    print("review_conclusion=PASS_FULL25_DESCRIPTIVE_REVIEW_BOUNDARIES_DOCUMENTED")


if __name__ == "__main__":
    main()
