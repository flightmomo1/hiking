from __future__ import annotations

import csv
import html
import json
import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
OUTPUT_ROOT = (
    OUTPUTS
    / "report_figures"
    / "ch6_5_5_navigation_challenge_exposure_review_v1"
)

DATA_TABLE_PATH = (
    OUTPUTS
    / "report_figures"
    / "ch6_5_5_route_following_data_table_patch_v1"
    / "personal_ability_radar_data_table_v1_1.csv"
)
ROUTE_FOLLOWING_SUMMARY_PATH = (
    OUTPUTS
    / "report_figures"
    / "ch6_5_5_route_following_stability_proxy_admission_v1_1"
    / "route_following_stability_proxy_activity_summary_v1_1.csv"
)

SOURCE_INVENTORY_PATH = OUTPUT_ROOT / "navigation_challenge_source_inventory_v1.csv"
ROUTE_EXPOSURE_PATH = (
    OUTPUT_ROOT / "navigation_challenge_route_exposure_candidates_v1.csv"
)
ACTIVITY_CONTEXT_PATH = OUTPUT_ROOT / "navigation_challenge_activity_context_v1.csv"
ADMISSION_DECISION_PATH = (
    OUTPUT_ROOT / "navigation_challenge_exposure_admission_decision_v1.csv"
)
AUDIT_PATH = OUTPUT_ROOT / "navigation_challenge_exposure_audit_v1.csv"
REPORT_PATH = OUTPUT_ROOT / "navigation_challenge_exposure_review_report_v1.html"

BASELINE_STATUS = "RADAR_BASELINE_ACTIVITY"
PASS_CONTEXT = "PASS_CH6_5_5_NAVIGATION_CHALLENGE_EXPOSURE_REVIEW_V1_CONTEXT_ONLY"
PASS_SOURCE_GAP = "PASS_CH6_5_5_NAVIGATION_CHALLENGE_EXPOSURE_REVIEW_V1_SOURCE_GAP_ONLY"
SOURCE_GAP_DECISION = "RETAIN_AS_SOURCE_GAP_FOR_FORK_DECISION_POINT_INVENTORY"
CONTEXT_DECISION = "ADMIT_AS_ROUTE_FOLLOWING_CONFIDENCE_CONTEXT_NOT_AXIS"
BOUNDARY = (
    "CH6.5.5 navigation_challenge_exposure review v1 is contextual evidence "
    "for interpreting route_following_stability confidence only. It is not a "
    "personal ability axis and does not compute or authorize ability scores, "
    "ability ranks, ability classes, THCI scores, final hiking risk scores, "
    "route suitability scores, go/no-go decisions, medical diagnoses, or "
    "causality claims."
)

NAME_PATTERN = re.compile(
    r"(ib1c|ib1e|ib2d|route_profile|route_context|semantic|surface|"
    r"branch|fork|junction|intersection|crossing|guidepost|facility|"
    r"trail|path|road|way|mainline|self_near)",
    re.I,
)
FORK_COLUMN_PATTERN = re.compile(
    r"(^|_)(fork|junction|intersection|crossing|decision_point)(_count|_id|_type|_candidate|_exposure|$)|"
    r"(fork_count|junction_count|intersection_count|decision_point_count)",
    re.I,
)
CONTEXT_COLUMN_PATTERN = re.compile(
    r"(guidepost|facility|trail|path|road|way|surface|semantic|highway|"
    r"graph_nodes|graph_edges|self_near|mainline|route_role)",
    re.I,
)


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required input: {path}")
    return pd.read_csv(path)


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def count_csv_rows(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            return max(sum(1 for _ in f) - 1, 0)
    except Exception:
        return 0


def csv_columns(path: Path) -> list[str]:
    try:
        with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            return next(csv.reader(f), [])
    except Exception:
        return []


def geojson_properties(path: Path) -> tuple[int, list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig", errors="ignore"))
        features = data.get("features", []) if isinstance(data, dict) else []
        columns: set[str] = set()
        for feature in features[:50]:
            props = feature.get("properties", {}) if isinstance(feature, dict) else {}
            columns.update(str(key) for key in props.keys())
        return len(features), sorted(columns)
    except Exception:
        return 0, []


def classify_source(path: Path, columns: list[str], row_count: int) -> tuple[str, bool, str]:
    path_text = str(path).lower()
    column_text = " ".join(columns).lower()
    activity_diagnostic = any(
        token in path_text
        for token in [
            "activity_points",
            "ib3c_",
            "ib3f_",
            "single_activity",
            "wrong_branch",
        ]
    )
    if FORK_COLUMN_PATTERN.search(column_text):
        if activity_diagnostic:
            return (
                "activity_mapmatch_or_wrong_branch_diagnostic_not_fork_inventory",
                False,
                "Activity-level branch ambiguity, candidate-way switching, or wrong-branch diagnostics are behavior/map-match evidence, not route-level fork exposure inventory.",
            )
        return (
            "candidate_fork_decision_point_inventory",
            True,
            "",
        )
    if "sequence_branch_ambiguity" in column_text or "candidate_way_switch" in column_text or "wrong_branch" in path_text:
        return (
            "activity_mapmatch_or_wrong_branch_diagnostic_not_fork_inventory",
            False,
            "Branch ambiguity and wrong-branch diagnostics are useful navigation behavior context, but they do not enumerate route fork or decision point exposure.",
        )
    if "self_near" in path_text:
        return (
            "route_geometry_self_near_context_not_fork_inventory",
            False,
            "Self-near geometry can indicate route geometry complexity, but it does not identify fork or decision point exposure.",
        )
    if "mainline_summary" in path_text and (
        "graph_nodes_n" in column_text or "graph_edges_n" in column_text
    ):
        return (
            "mainline_graph_summary_not_decision_point_inventory",
            False,
            "Graph node/edge counts summarize route construction and cannot be treated as exposed fork or decision point counts.",
        )
    if "semantic" in path_text or CONTEXT_COLUMN_PATTERN.search(column_text):
        return (
            "route_semantic_context_not_fork_inventory",
            False,
            "Route semantic, surface, guidepost, facility, trail, path, road, or way context exists, but it is not a governed fork/decision point inventory.",
        )
    return (
        "candidate_route_context_unusable_for_fork_exposure",
        False,
        "No explicit fork, junction, intersection, crossing, branch, or decision point fields found.",
    )


def discover_sources() -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for path in sorted(OUTPUTS.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".csv", ".geojson", ".json"}:
            continue
        if not NAME_PATTERN.search(str(path)):
            continue
        # Keep the inventory focused and avoid old checkpoint / backup noise unless
        # the source name contains explicit fork-like terms.
        path_text = str(path).lower()
        if ("_backup" in path_text or "_checkpoints" in path_text) and not FORK_COLUMN_PATTERN.search(path_text):
            continue
        try:
            if path.stat().st_size > 25_000_000:
                continue
        except OSError:
            continue
        if path.suffix.lower() == ".csv":
            columns = csv_columns(path)
            row_count = count_csv_rows(path)
        else:
            row_count, columns = geojson_properties(path)
        if not columns:
            continue
        columns_text = " ".join(columns)
        if not (NAME_PATTERN.search(str(path)) or CONTEXT_COLUMN_PATTERN.search(columns_text)):
            continue
        source_role, usable, gap_reason = classify_source(path, columns, row_count)
        # Include all explicit fork-like candidates, plus representative route
        # semantics / graph / self-near sources that explain why the review stays
        # a source gap.
        include = usable or source_role in {
            "activity_mapmatch_or_wrong_branch_diagnostic_not_fork_inventory",
            "route_geometry_self_near_context_not_fork_inventory",
            "mainline_graph_summary_not_decision_point_inventory",
            "route_semantic_context_not_fork_inventory",
        }
        if include:
            records.append(
                {
                    "source_path": relative(path),
                    "exists": True,
                    "row_count": int(row_count),
                    "candidate_columns": "|".join(columns[:80]),
                    "source_role": source_role,
                    "usable_for_fork_exposure": bool(usable),
                    "source_gap_reason": gap_reason,
                }
            )
    if not records:
        records.append(
            {
                "source_path": "",
                "exists": False,
                "row_count": 0,
                "candidate_columns": "",
                "source_role": "no_candidate_source_found",
                "usable_for_fork_exposure": False,
                "source_gap_reason": "No route semantics, route profile, or fork/decision point candidate sources found.",
            }
        )
    frame = pd.DataFrame(records).drop_duplicates(subset=["source_path"])
    frame = frame.sort_values(
        ["usable_for_fork_exposure", "source_role", "source_path"],
        ascending=[False, True, True],
    )
    return frame


def build_route_exposure_candidates(source_inventory: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "route_folder",
        "case_id",
        "route_dist_m",
        "feature_type",
        "feature_name",
        "osm_tags",
        "is_fork_candidate",
        "is_decision_point_candidate",
        "is_wrong_branch_exposure_candidate",
        "confidence",
        "source_path",
        "source_status",
        "source_gap_reason",
    ]
    usable = source_inventory[source_inventory["usable_for_fork_exposure"] == True]
    if usable.empty:
        return pd.DataFrame(
            [
                {
                    "route_folder": "",
                    "case_id": "",
                    "route_dist_m": pd.NA,
                    "feature_type": "SOURCE_GAP",
                    "feature_name": "",
                    "osm_tags": "",
                    "is_fork_candidate": pd.NA,
                    "is_decision_point_candidate": pd.NA,
                    "is_wrong_branch_exposure_candidate": pd.NA,
                    "confidence": pd.NA,
                    "source_path": "",
                    "source_status": "INSUFFICIENT_FORK_SOURCE",
                    "source_gap_reason": "No governed fork / junction / branch / decision point inventory source was found. Guidepost, facility, trail, path, road, way, and graph-summary sources are contextual only.",
                }
            ],
            columns=columns,
        )
    # This path is intentionally conservative. A future source with explicit fork
    # columns will be inventoried, but route-level candidate extraction should be
    # reviewed before admission as confidence context.
    return pd.DataFrame(columns=columns)


def build_activity_context(
    data_table: pd.DataFrame,
    route_following_summary: pd.DataFrame,
    source_inventory: pd.DataFrame,
) -> pd.DataFrame:
    activity_status = (
        data_table[["activity_id_short", "study_population_status"]]
        .drop_duplicates()
        .rename(columns={"activity_id_short": "activity_id"})
    )
    summary = route_following_summary.copy()
    summary["activity_id"] = summary["activity_id"].astype(str)
    if "study_population_status" in summary.columns:
        summary = summary.drop(columns=["study_population_status"])
    context = activity_status.merge(summary, on="activity_id", how="left")
    usable_source = bool(source_inventory["usable_for_fork_exposure"].any())
    source_status = (
        "FORK_SOURCE_AVAILABLE_REQUIRES_CONTEXT_ADMISSION"
        if usable_source
        else "INSUFFICIENT_FORK_SOURCE"
    )
    rows = []
    for _, row in context.iterrows():
        is_baseline = row["study_population_status"] == BASELINE_STATUS
        baseline_gate = row.get("baseline_population_gate", "")
        if not is_baseline:
            baseline_gate = "BLOCKED_EXTRA_SOURCE"
        if usable_source:
            interpretation_note = (
                "Navigation challenge source exists but remains contextual only; "
                "it may support route-following confidence interpretation after "
                "fork exposure extraction review."
            )
            exposure_confidence = "SOURCE_AVAILABLE_REVIEW_REQUIRED"
            fork_count = decision_count = wrong_branch_count = pd.NA
        else:
            interpretation_note = (
                "Fork / decision point source is insufficient. Do not zero-fill "
                "navigation challenge exposure; retain as source gap."
            )
            exposure_confidence = "INSUFFICIENT_FORK_SOURCE"
            fork_count = decision_count = wrong_branch_count = pd.NA
        if not is_baseline:
            interpretation_note += " Extra source activity 6_1 is blocked from baseline admission."
        rows.append(
            {
                "activity_id": row["activity_id"],
                "study_population_status": row["study_population_status"],
                "baseline_population_gate": baseline_gate,
                "route_following_evidence_state": row.get("evidence_state", ""),
                "route_issue_event_count": row.get("route_issue_event_count", pd.NA),
                "candidate_proxy_route_following_stability_0_100": row.get(
                    "candidate_proxy_route_following_stability_0_100", pd.NA
                ),
                "navigation_challenge_source_status": source_status,
                "fork_exposure_count": fork_count,
                "decision_point_exposure_count": decision_count,
                "wrong_branch_exposure_count": wrong_branch_count,
                "exposure_confidence": exposure_confidence,
                "interpretation_note": interpretation_note,
            }
        )
    return pd.DataFrame(rows).sort_values(
        "activity_id",
        key=lambda s: s.map(activity_sort_key),
    )


def activity_sort_key(activity_id: object) -> tuple[int, int, str]:
    text = str(activity_id)
    head = text.split("_", 1)[0]
    try:
        return (0, int(head), text)
    except ValueError:
        return (1, 0, text)


def build_admission(source_inventory: pd.DataFrame) -> pd.DataFrame:
    usable = bool(source_inventory["usable_for_fork_exposure"].any())
    decision = CONTEXT_DECISION if usable else SOURCE_GAP_DECISION
    source_status = (
        "USABLE_FORK_DECISION_POINT_SOURCE_FOUND"
        if usable
        else "INSUFFICIENT_FORK_DECISION_POINT_SOURCE"
    )
    reason = (
        "A governed fork / decision point source exists; navigation challenge "
        "exposure may be admitted only as route-following confidence context, "
        "not as a personal ability axis."
        if usable
        else "No governed fork / decision point inventory source was found. "
        "Route semantics, guidepost, facility, trail, path, road, way, graph, "
        "and self-near sources remain contextual but cannot produce exposure counts."
    )
    return pd.DataFrame(
        [
            {
                "evidence_id": "navigation_challenge_exposure",
                "evidence_label_zh": "導航挑戰暴露",
                "admission_decision": decision,
                "evidence_use": "ROUTE_FOLLOWING_CONFIDENCE_CONTEXT" if usable else "SOURCE_GAP",
                "source_status": source_status,
                "not_personal_ability_axis": True,
                "axis_contract_patch_required": False,
                "retained_or_admitted_reason": reason,
                "allowed_use": "contextual interpretation of route_following_stability confidence",
                "disallowed_use": "ability score|ability rank|ability class|final risk score|route suitability score|go/no-go decision|deviation correction inference",
                "interpretation_boundary": BOUNDARY,
            }
        ]
    )


def forbidden_columns(frames: dict[str, pd.DataFrame]) -> list[str]:
    patterns = [
        "ability_score",
        "ability_rank",
        "ability_class",
        "thci_score",
        "final_hiking_risk_score",
        "route_suitability_score",
        "go_no_go",
        "medical_diagnosis",
        "causality_claim",
    ]
    found = []
    for name, frame in frames.items():
        for column in frame.columns:
            lowered = str(column).lower()
            if any(pattern in lowered for pattern in patterns):
                found.append(f"{name}:{column}")
    return found


def build_audit(
    data_table: pd.DataFrame,
    activity_context: pd.DataFrame,
    source_inventory: pd.DataFrame,
    admission: pd.DataFrame,
) -> pd.DataFrame:
    baseline = activity_context[
        activity_context["study_population_status"] == BASELINE_STATUS
    ]
    extra = activity_context[
        activity_context["study_population_status"] != BASELINE_STATUS
    ]
    route_following_rows = data_table[
        data_table["axis_id"] == "route_following_stability"
    ]
    deviation_rows = data_table[
        data_table["axis_id"] == "deviation_correction_ability"
    ]
    navigation_axis_rows = data_table[
        data_table["axis_id"] == "navigation_challenge_exposure"
    ]
    usable_source = bool(source_inventory["usable_for_fork_exposure"].any())
    forbidden = forbidden_columns(
        {
            "source_inventory": source_inventory,
            "route_exposure": pd.DataFrame(),
            "activity_context": activity_context,
            "admission": admission,
        }
    )
    exposure_count_columns = [
        "fork_exposure_count",
        "decision_point_exposure_count",
        "wrong_branch_exposure_count",
    ]
    zero_fill_used = False
    for column in exposure_count_columns:
        values = activity_context[column]
        zero_fill_used = zero_fill_used or bool(
            (values.fillna("").astype(str).str.strip() == "0").any()
            and not usable_source
        )
    checks = {
        "baseline_activity_count": int(len(baseline)),
        "extra_source_count": int(len(extra)),
        "extra_source_admitted_count": 0,
        "route_following_axis_not_modified": bool(
            not route_following_rows.empty
            and route_following_rows["axis_output_mode"].eq("LIMITED_PROXY_AXIS").all()
        ),
        "deviation_correction_axis_not_modified": bool(
            not deviation_rows.empty
            and deviation_rows["axis_output_mode"].eq("MISSING_EVIDENCE_ANNOTATION").all()
        ),
        "navigation_challenge_not_added_as_axis": bool(navigation_axis_rows.empty),
        "zero_fill_used": bool(zero_fill_used),
        "forbidden_fields_present": bool(forbidden),
        "forbidden_fields": "|".join(forbidden) if forbidden else "NONE",
        "usable_fork_source_count": int(source_inventory["usable_for_fork_exposure"].sum()),
        "context_source_count": int(len(source_inventory)),
        "admission_decision": admission["admission_decision"].iloc[0],
    }
    expected = {
        "baseline_activity_count": 25,
        "extra_source_count": 1,
        "extra_source_admitted_count": 0,
        "route_following_axis_not_modified": True,
        "deviation_correction_axis_not_modified": True,
        "navigation_challenge_not_added_as_axis": True,
        "zero_fill_used": False,
        "forbidden_fields_present": False,
    }
    review_reasons = [
        f"{key}={checks[key]} expected {value}"
        for key, value in expected.items()
        if checks[key] != value
    ]
    checks["audit_conclusion"] = (
        (PASS_CONTEXT if usable_source else PASS_SOURCE_GAP)
        if not review_reasons
        else "REVIEW_REQUIRED"
    )
    checks["review_reasons"] = "|".join(review_reasons) if review_reasons else "NONE"
    checks["interpretation_boundary"] = BOUNDARY
    return pd.DataFrame([checks])


def table_html(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    data = frame if max_rows is None else frame.head(max_rows)
    return data.to_html(index=False, escape=True, border=0)


def write_report(
    source_inventory: pd.DataFrame,
    route_exposure: pd.DataFrame,
    activity_context: pd.DataFrame,
    admission: pd.DataFrame,
    audit: pd.DataFrame,
) -> None:
    audit_row = audit.iloc[0]
    decision = admission.iloc[0]
    source_summary = (
        source_inventory.groupby(["source_role", "usable_for_fork_exposure"])
        .size()
        .reset_index(name="source_count")
        .sort_values(["usable_for_fork_exposure", "source_role"], ascending=[False, True])
    )
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>CH6.5.5 navigation challenge exposure review v1</title>
  <style>
    body {{ font-family: Arial, "Microsoft JhengHei", sans-serif; margin: 32px; color: #172326; background: #f7f8f4; }}
    h1, h2 {{ margin-bottom: 0.35rem; }}
    .note {{ max-width: 980px; line-height: 1.5; }}
    .badge {{ display: inline-block; padding: 4px 8px; border-radius: 4px; background: #e3ece8; color: #153d37; font-weight: 700; }}
    table {{ border-collapse: collapse; width: 100%; margin: 14px 0 28px; background: white; font-size: 13px; }}
    th, td {{ border: 1px solid #d8dfda; padding: 7px 8px; vertical-align: top; }}
    th {{ background: #e8efeb; text-align: left; }}
    code {{ background: #eef2ef; padding: 2px 4px; border-radius: 3px; }}
  </style>
</head>
<body>
  <h1>CH6.5.5 Navigation Challenge Exposure Review v1</h1>
  <p><span class="badge">Contextual evidence, not an axis</span></p>
  <p class="note">Navigation challenge exposure is contextual evidence for interpreting route-following stability proxy confidence. Many forks with no route issue can support interpretation confidence, but it is not a formal ability score.</p>
  <p class="note">This review must not be used to infer deviation correction ability. No deviation does not prove correction ability; that requires deviation-start -&gt; correction/rejoin event-chain evidence.</p>
  <p class="note"><strong>Decision:</strong> <code>{html.escape(str(decision["admission_decision"]))}</code></p>
  <p class="note">{html.escape(str(decision["retained_or_admitted_reason"]))}</p>
  <p class="note">{html.escape(BOUNDARY)}</p>

  <h2>Audit</h2>
  <p><code>{html.escape(str(audit_row["audit_conclusion"]))}</code></p>
  {table_html(audit)}

  <h2>Source Inventory Summary</h2>
  {table_html(source_summary)}

  <h2>Route Exposure Candidates</h2>
  {table_html(route_exposure)}

  <h2>Activity Context</h2>
  {table_html(activity_context)}

  <h2>Source Inventory Sample</h2>
  {table_html(source_inventory, max_rows=60)}
</body>
</html>
"""
    REPORT_PATH.write_text(html_text, encoding="utf-8")


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    data_table = read_csv(DATA_TABLE_PATH)
    route_following_summary = read_csv(ROUTE_FOLLOWING_SUMMARY_PATH)
    source_inventory = discover_sources()
    route_exposure = build_route_exposure_candidates(source_inventory)
    activity_context = build_activity_context(
        data_table, route_following_summary, source_inventory
    )
    admission = build_admission(source_inventory)
    audit = build_audit(data_table, activity_context, source_inventory, admission)

    source_inventory.to_csv(SOURCE_INVENTORY_PATH, index=False, encoding="utf-8-sig")
    route_exposure.to_csv(ROUTE_EXPOSURE_PATH, index=False, encoding="utf-8-sig")
    activity_context.to_csv(ACTIVITY_CONTEXT_PATH, index=False, encoding="utf-8-sig")
    admission.to_csv(ADMISSION_DECISION_PATH, index=False, encoding="utf-8-sig")
    audit.to_csv(AUDIT_PATH, index=False, encoding="utf-8-sig")
    write_report(source_inventory, route_exposure, activity_context, admission, audit)

    source_summary = (
        source_inventory.groupby(["source_role", "usable_for_fork_exposure"])
        .size()
        .reset_index(name="source_count")
        .to_dict(orient="records")
    )
    result = {
        "script": str(Path(__file__).resolve()),
        "output_root": str(OUTPUT_ROOT),
        "audit_csv": str(AUDIT_PATH),
        "audit_conclusion": audit["audit_conclusion"].iloc[0],
        "source_inventory_summary": source_summary,
        "admission_decision": admission["admission_decision"].iloc[0],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
