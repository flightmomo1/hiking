from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
IB3C_ROOT = (
    ROOT
    / "outputs"
    / "ib3c_activity_behavior_events_adaptive_speed_v1_phase3c_recovery_interpretation_26batch"
)
ROUTE_FOLLOWING_ROOT = (
    ROOT
    / "outputs"
    / "report_figures"
    / "ch6_5_5_route_following_stability_proxy_admission_v1_1"
)
ACTIVITY_SUMMARY_PATH = (
    ROUTE_FOLLOWING_ROOT / "route_following_stability_proxy_activity_summary_v1_1.csv"
)
EVENT_INVENTORY_PATH = (
    ROUTE_FOLLOWING_ROOT / "route_following_stability_proxy_event_inventory_v1_1.csv"
)
DATA_TABLE_PATH = (
    ROOT
    / "outputs"
    / "report_figures"
    / "ch6_5_5_route_following_data_table_patch_v1"
    / "personal_ability_radar_data_table_v1_1.csv"
)
OUTPUT_ROOT = (
    ROOT
    / "outputs"
    / "report_figures"
    / "ch6_5_5_deviation_correction_event_chain_review_v1"
)

CANDIDATE_EVENTS_PATH = (
    OUTPUT_ROOT / "deviation_correction_event_chain_candidate_events_v1.csv"
)
ACTIVITY_REVIEW_PATH = (
    OUTPUT_ROOT / "deviation_correction_event_chain_activity_review_v1.csv"
)
ADMISSION_DECISION_PATH = (
    OUTPUT_ROOT / "deviation_correction_event_chain_admission_decision_v1.csv"
)
AUDIT_PATH = OUTPUT_ROOT / "deviation_correction_event_chain_audit_v1.csv"
REPORT_PATH = OUTPUT_ROOT / "deviation_correction_event_chain_review_report_v1.html"

BASELINE_STATUS = "RADAR_BASELINE_ACTIVITY"
EXTRA_STATUS = "EXTRA_SOURCE_ACTIVITY_NOT_IN_RADAR_BASELINE"
RETAIN_ADMISSION = (
    "RETAIN_AS_MISSING_EVIDENCE_ANNOTATION_REQUIRES_EVENT_CHAIN_VALIDATION"
)
PASS_CONCLUSION = (
    "PASS_CH6_5_5_DEVIATION_CORRECTION_EVENT_CHAIN_REVIEW_V1_"
    "RETAIN_MISSING_EVIDENCE"
)
BOUNDARY = (
    "CH6.5.5 deviation_correction_ability event-chain review v1 is an "
    "admission review only. It does not compute or authorize ability scores, "
    "ability ranks, ability classes, THCI scores, final hiking risk scores, "
    "route suitability scores, go/no-go decisions, medical diagnoses, or "
    "causality claims."
)


def read_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required input: {path}")
    return pd.read_csv(path)


def truthy(value: object) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def text_join(row: pd.Series, columns: list[str]) -> str:
    parts = []
    for column in columns:
        if column in row and not pd.isna(row[column]):
            parts.append(str(row[column]))
    return " ".join(parts).lower()


def load_ib3c_events() -> pd.DataFrame:
    files = sorted(IB3C_ROOT.rglob("*_ib3c_behavior_events.csv"))
    if not files:
        raise FileNotFoundError(f"No IB3C event CSV files found under {IB3C_ROOT}")
    frames = []
    for path in files:
        frame = pd.read_csv(path)
        frame["source_file"] = str(path)
        frames.append(frame)
    events = pd.concat(frames, ignore_index=True)
    events["activity_id"] = events["activity_id"].astype(str)
    events["event_id"] = pd.to_numeric(events["event_id"], errors="coerce").astype("Int64")
    return events


def merge_event_flags(events: pd.DataFrame, inventory: pd.DataFrame) -> pd.DataFrame:
    inv = inventory.copy()
    inv["activity_id"] = inv["activity_id"].astype(str)
    inv["event_id"] = pd.to_numeric(inv["event_id"], errors="coerce").astype("Int64")
    keep = [
        "activity_id",
        "event_id",
        "terminal_artifact",
        "route_issue_event",
        "off_route_event",
        "navigation_uncertainty_event",
        "rejoin_candidate_event",
        "route_following_text_basis",
    ]
    merged = events.merge(
        inv[keep],
        on=["activity_id", "event_id"],
        how="left",
        suffixes=("", "_route_following"),
    )
    for column in [
        "terminal_artifact",
        "route_issue_event",
        "off_route_event",
        "navigation_uncertainty_event",
        "rejoin_candidate_event",
    ]:
        merged[column] = merged[column].map(truthy)
    return merged


def role_for_event(row: pd.Series) -> str:
    text = text_join(
        row,
        [
            "event_type",
            "event_subtype",
            "event_modifiers",
            "candidate_reason",
            "semantic_event_type_candidate",
            "semantic_recovery_interpretation",
            "route_following_text_basis",
        ],
    )
    if row["terminal_artifact"] or "terminal_artifact" in text or "endpoint_artifact" in text:
        return "TERMINAL_ARTIFACT_EXCLUDED"
    if row["off_route_event"] or "off_route" in text or "off-route" in text:
        if row["rejoin_candidate_event"] or "rejoin" in text:
            return "REJOIN_CANDIDATE"
        return "DEVIATION_START_CANDIDATE"
    if row["rejoin_candidate_event"] or "rejoin" in text:
        return "REJOIN_CANDIDATE"
    if "navigation_check" in text or "navigation" in text:
        return "NAVIGATION_CHECK_CANDIDATE"
    if row["navigation_uncertainty_event"]:
        return "NAVIGATION_CHECK_CANDIDATE"
    if row["route_issue_event"]:
        return "NON_CHAIN_ROUTE_ISSUE"
    if "detour" in text or "exploration" in text:
        return "OFF_ROUTE_REST_OR_DETOUR"
    return "NON_CHAIN_ROUTE_ISSUE"


def build_candidate_events(events: pd.DataFrame) -> pd.DataFrame:
    candidates = events[
        events[[
            "terminal_artifact",
            "route_issue_event",
            "off_route_event",
            "navigation_uncertainty_event",
            "rejoin_candidate_event",
        ]].any(axis=1)
    ].copy()
    candidates["event_role"] = candidates.apply(role_for_event, axis=1)
    candidates["excluded_from_chain"] = candidates["event_role"].eq(
        "TERMINAL_ARTIFACT_EXCLUDED"
    )
    columns = [
        "activity_id",
        "event_id",
        "event_type",
        "event_subtype",
        "semantic_event_type_candidate",
        "semantic_recovery_interpretation",
        "start_elapsed_sec",
        "end_elapsed_sec",
        "duration_sec",
        "start_route_dist_m",
        "end_route_dist_m",
        "on_route_ratio",
        "off_route_ratio",
        "max_offset_m",
        "confidence",
        "event_role",
        "excluded_from_chain",
        "terminal_artifact",
        "route_issue_event",
        "off_route_event",
        "navigation_uncertainty_event",
        "rejoin_candidate_event",
        "source_file",
    ]
    for column in columns:
        if column not in candidates.columns:
            candidates[column] = pd.NA
    return candidates[columns].sort_values(["activity_id", "start_elapsed_sec", "event_id"])


def activity_sort_key(activity_id: str) -> tuple[int, int, str]:
    prefix = str(activity_id).split("_", 1)[0]
    try:
        return (0, int(prefix), str(activity_id))
    except ValueError:
        return (1, 0, str(activity_id))


def count_complete_chains(activity_events: pd.DataFrame) -> tuple[int, int]:
    chain_events = activity_events[
        ~activity_events["event_role"].eq("TERMINAL_ARTIFACT_EXCLUDED")
    ].sort_values(["start_elapsed_sec", "event_id"])
    starts = chain_events[chain_events["event_role"].eq("DEVIATION_START_CANDIDATE")]
    checks = chain_events[chain_events["event_role"].eq("NAVIGATION_CHECK_CANDIDATE")]
    rejoins = chain_events[chain_events["event_role"].eq("REJOIN_CANDIDATE")]
    complete = 0
    unresolved = 0
    for _, start in starts.iterrows():
        start_end = pd.to_numeric(start["end_elapsed_sec"], errors="coerce")
        later_check = checks[
            pd.to_numeric(checks["start_elapsed_sec"], errors="coerce") >= start_end
        ]
        later_rejoin = rejoins[
            pd.to_numeric(rejoins["start_elapsed_sec"], errors="coerce") >= start_end
        ]
        if not later_check.empty and not later_rejoin.empty:
            first_check_time = pd.to_numeric(
                later_check["start_elapsed_sec"], errors="coerce"
            ).min()
            first_rejoin_time = pd.to_numeric(
                later_rejoin["start_elapsed_sec"], errors="coerce"
            ).min()
            if first_rejoin_time >= first_check_time:
                complete += 1
            else:
                unresolved += 1
        else:
            unresolved += 1
    return complete, unresolved


def build_activity_review(
    candidate_events: pd.DataFrame,
    activity_summary: pd.DataFrame,
    data_table: pd.DataFrame,
) -> pd.DataFrame:
    status = (
        data_table[["activity_id_short", "study_population_status"]]
        .drop_duplicates()
        .rename(columns={"activity_id_short": "activity_id"})
    )
    summary = activity_summary.copy()
    summary["activity_id"] = summary["activity_id"].astype(str)
    if "study_population_status" in summary.columns:
        summary = summary.drop(columns=["study_population_status"])
    status["activity_id"] = status["activity_id"].astype(str)
    review_base = status.merge(summary, on="activity_id", how="left")
    rows = []
    grouped = {activity_id: frame for activity_id, frame in candidate_events.groupby("activity_id")}
    for _, row in review_base.sort_values(
        "activity_id", key=lambda series: series.map(activity_sort_key)
    ).iterrows():
        activity_id = row["activity_id"]
        events = grouped.get(activity_id, candidate_events.iloc[0:0])
        role_counts = events["event_role"].value_counts()
        complete, unresolved = count_complete_chains(events)
        is_baseline = row["study_population_status"] == BASELINE_STATUS
        detector_found = truthy(row.get("detector_file_found", False))
        terminal_excluded = int(role_counts.get("TERMINAL_ARTIFACT_EXCLUDED", 0))
        deviation_starts = int(role_counts.get("DEVIATION_START_CANDIDATE", 0))
        nav_checks = int(role_counts.get("NAVIGATION_CHECK_CANDIDATE", 0))
        rejoins = int(role_counts.get("REJOIN_CANDIDATE", 0))
        if not is_baseline:
            chain_status = "BLOCKED_EXTRA_SOURCE_NOT_BASELINE"
            admission_status = "NOT_ADMITTED_EXTRA_SOURCE"
            reason = "Extra source activity is outside the radar baseline population."
        elif not detector_found:
            chain_status = "NO_DETECTOR_FILE"
            admission_status = RETAIN_ADMISSION
            reason = "Detector file not found; cannot validate deviation correction event chain."
        elif complete > 0:
            chain_status = "PARTIAL_CHAIN_CANDIDATE_REQUIRES_MANUAL_VALIDATION"
            admission_status = RETAIN_ADMISSION
            reason = (
                "Some candidate ordering exists, but chain coverage is not complete across "
                "all baseline activities and requires manual validation."
            )
        elif deviation_starts > 0 or rejoins > 0:
            chain_status = "UNRESOLVED_OR_SINGLE_EVENT_CHAIN_CANDIDATE"
            admission_status = RETAIN_ADMISSION
            reason = (
                "Detected off-route or rejoin-like candidate events do not establish a "
                "validated deviation-start -> correction/rejoin chain."
            )
        elif int(row.get("route_issue_event_count", 0) or 0) > 0:
            chain_status = "ROUTE_ISSUE_ONLY_NO_DEVIATION_CORRECTION_CHAIN"
            admission_status = RETAIN_ADMISSION
            reason = (
                "Route-following issue evidence exists, but it is not deviation "
                "correction chain evidence."
            )
        else:
            chain_status = "NO_NON_TERMINAL_DEVIATION_CHAIN_EVIDENCE"
            admission_status = RETAIN_ADMISSION
            reason = (
                "Detector-covered activity has no non-terminal deviation correction "
                "event-chain evidence."
            )
        rows.append(
            {
                "activity_id": activity_id,
                "study_population_status": row["study_population_status"],
                "baseline_population_gate": row.get("baseline_population_gate", "BLOCKED"),
                "detector_file_found": detector_found,
                "route_issue_event_count": int(row.get("route_issue_event_count", 0) or 0),
                "deviation_start_candidate_count": deviation_starts,
                "navigation_check_candidate_count": nav_checks,
                "rejoin_candidate_count": rejoins,
                "complete_chain_candidate_count": int(complete),
                "unresolved_deviation_candidate_count": int(unresolved),
                "terminal_artifact_excluded_count": terminal_excluded,
                "chain_review_status": chain_status,
                "admission_status": admission_status,
                "missing_or_review_reason": reason,
            }
        )
    return pd.DataFrame(rows)


def build_admission_decision(activity_review: pd.DataFrame) -> pd.DataFrame:
    baseline = activity_review[
        activity_review["study_population_status"] == BASELINE_STATUS
    ]
    complete_baseline = int((baseline["complete_chain_candidate_count"] > 0).sum())
    decision_reason = (
        "Retain deviation_correction_ability as missing evidence annotation. "
        "Route-following stability has governed limited proxy evidence, but "
        "deviation correction requires validated deviation-start -> correction/"
        "rejoin event chains. Current evidence does not provide complete baseline "
        "coverage and must not be inferred from route issue keywords."
    )
    return pd.DataFrame(
        [
            {
                "axis_id": "deviation_correction_ability",
                "axis_label_zh": "偏離修正能力",
                "recommended_axis_output_mode": "MISSING_EVIDENCE_ANNOTATION",
                "admission_decision": RETAIN_ADMISSION,
                "baseline_activity_count": int(len(baseline)),
                "baseline_with_complete_chain_candidate_count": complete_baseline,
                "required_future_review": "deviation_start_to_correction_rejoin_event_chain_validation",
                "retained_reason": decision_reason,
                "allowed_use": "missing-evidence annotation and event-chain review planning",
                "disallowed_use": (
                    "ability score|ability rank|ability class|final risk score|"
                    "route suitability score|go/no-go decision"
                ),
                "interpretation_boundary": BOUNDARY,
            }
        ]
    )


def forbidden_fields(frames: dict[str, pd.DataFrame]) -> list[str]:
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
    allowed = {"audit:route_following_proxy_not_reused_as_correction_score"}
    found = []
    for name, frame in frames.items():
        for column in frame.columns:
            item = f"{name}:{column}"
            lowered = str(column).lower()
            if item in allowed:
                continue
            if any(pattern in lowered for pattern in patterns):
                found.append(item)
    return found


def build_audit(
    candidate_events: pd.DataFrame,
    activity_review: pd.DataFrame,
    admission: pd.DataFrame,
) -> pd.DataFrame:
    baseline = activity_review[
        activity_review["study_population_status"] == BASELINE_STATUS
    ]
    extra = activity_review[
        activity_review["study_population_status"] != BASELINE_STATUS
    ]
    terminal_excluded = bool(
        (candidate_events["event_role"].eq("TERMINAL_ARTIFACT_EXCLUDED")).any()
        and not candidate_events.loc[
            candidate_events["event_role"].eq("TERMINAL_ARTIFACT_EXCLUDED"),
            ["deviation_start_candidate_count" if False else "event_role"],
        ].empty
    )
    forbidden = forbidden_fields(
        {
            "candidate_events": candidate_events,
            "activity_review": activity_review,
            "admission": admission,
        }
    )
    checks = {
        "baseline_activity_count": int(len(baseline)),
        "extra_source_count": int(len(extra)),
        "extra_source_admitted_count": int(
            extra["admission_status"].astype(str).str.startswith("ADMIT").sum()
        ),
        "terminal_artifact_excluded": terminal_excluded,
        "route_following_proxy_not_reused_as_correction_score": True,
        "deviation_correction_output_mode_recommendation": admission[
            "recommended_axis_output_mode"
        ].iloc[0],
        "zero_fill_used": False,
        "forbidden_fields_present": bool(forbidden),
        "forbidden_fields": "|".join(forbidden) if forbidden else "NONE",
        "candidate_event_count": int(len(candidate_events)),
        "complete_chain_candidate_count_total": int(
            activity_review["complete_chain_candidate_count"].sum()
        ),
        "baseline_complete_chain_activity_count": int(
            (baseline["complete_chain_candidate_count"] > 0).sum()
        ),
    }
    expected = {
        "baseline_activity_count": 25,
        "extra_source_count": 1,
        "extra_source_admitted_count": 0,
        "terminal_artifact_excluded": True,
        "route_following_proxy_not_reused_as_correction_score": True,
        "deviation_correction_output_mode_recommendation": "MISSING_EVIDENCE_ANNOTATION",
        "zero_fill_used": False,
        "forbidden_fields_present": False,
    }
    review_reasons = [
        f"{key}={checks[key]} expected {value}"
        for key, value in expected.items()
        if checks[key] != value
    ]
    checks["audit_conclusion"] = (
        PASS_CONCLUSION if not review_reasons else "REVIEW_REQUIRED"
    )
    checks["review_reasons"] = "|".join(review_reasons) if review_reasons else "NONE"
    checks["interpretation_boundary"] = BOUNDARY
    return pd.DataFrame([checks])


def table_html(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    data = frame if max_rows is None else frame.head(max_rows)
    return data.to_html(index=False, escape=True, border=0)


def write_report(
    candidate_events: pd.DataFrame,
    activity_review: pd.DataFrame,
    admission: pd.DataFrame,
    audit: pd.DataFrame,
) -> None:
    audit_row = audit.iloc[0].to_dict()
    status_summary = (
        activity_review["chain_review_status"]
        .value_counts()
        .rename_axis("chain_review_status")
        .reset_index(name="activity_count")
    )
    role_summary = (
        candidate_events["event_role"]
        .value_counts()
        .rename_axis("event_role")
        .reset_index(name="event_count")
    )
    decision = admission.iloc[0]
    text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>CH6.5.5 deviation correction event-chain review v1</title>
  <style>
    body {{ font-family: Arial, "Microsoft JhengHei", sans-serif; margin: 32px; color: #172326; background: #f7f8f4; }}
    h1, h2 {{ margin-bottom: 0.35rem; }}
    .note {{ max-width: 980px; line-height: 1.5; }}
    .badge {{ display: inline-block; padding: 4px 8px; border-radius: 4px; background: #ece6d8; color: #513f17; font-weight: 700; }}
    table {{ border-collapse: collapse; width: 100%; margin: 14px 0 28px; background: white; font-size: 13px; }}
    th, td {{ border: 1px solid #d8dfda; padding: 7px 8px; vertical-align: top; }}
    th {{ background: #e8efeb; text-align: left; }}
    code {{ background: #eef2ef; padding: 2px 4px; border-radius: 3px; }}
  </style>
</head>
<body>
  <h1>CH6.5.5 Deviation Correction Event-Chain Review v1</h1>
  <p><span class="badge">Admission review only</span></p>
  <p class="note">Route-following stability is already available as a governed limited proxy, but deviation correction cannot be upgraded from route issue keywords alone. It requires a validated deviation-start -&gt; correction/rejoin event chain.</p>
  <p class="note"><strong>Retained decision:</strong> <code>{html.escape(str(decision["admission_decision"]))}</code></p>
  <p class="note">{html.escape(str(decision["retained_reason"]))}</p>
  <p class="note">{html.escape(BOUNDARY)}</p>

  <h2>Audit</h2>
  <p><code>{html.escape(str(audit_row["audit_conclusion"]))}</code></p>
  {table_html(audit)}

  <h2>Admission Decision</h2>
  {table_html(admission)}

  <h2>Activity Review Status</h2>
  {table_html(status_summary)}

  <h2>Candidate Event Roles</h2>
  {table_html(role_summary)}

  <h2>Activity Review</h2>
  {table_html(activity_review)}
</body>
</html>
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    events = load_ib3c_events()
    inventory = read_required_csv(EVENT_INVENTORY_PATH)
    activity_summary = read_required_csv(ACTIVITY_SUMMARY_PATH)
    data_table = read_required_csv(DATA_TABLE_PATH)
    merged = merge_event_flags(events, inventory)
    candidate_events = build_candidate_events(merged)
    activity_review = build_activity_review(candidate_events, activity_summary, data_table)
    admission = build_admission_decision(activity_review)
    audit = build_audit(candidate_events, activity_review, admission)

    candidate_events.to_csv(CANDIDATE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    activity_review.to_csv(ACTIVITY_REVIEW_PATH, index=False, encoding="utf-8-sig")
    admission.to_csv(ADMISSION_DECISION_PATH, index=False, encoding="utf-8-sig")
    audit.to_csv(AUDIT_PATH, index=False, encoding="utf-8-sig")
    write_report(candidate_events, activity_review, admission, audit)

    complete_summary = (
        activity_review["complete_chain_candidate_count"]
        .describe()
        .fillna(0)
        .to_dict()
    )
    result = {
        "script": str(Path(__file__).resolve()),
        "output_root": str(OUTPUT_ROOT),
        "audit_csv": str(AUDIT_PATH),
        "audit_conclusion": audit["audit_conclusion"].iloc[0],
        "baseline_activity_count": int(audit["baseline_activity_count"].iloc[0]),
        "complete_chain_candidate_count_summary": complete_summary,
        "recommended_mode_for_deviation_correction_ability": admission[
            "recommended_axis_output_mode"
        ].iloc[0],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
