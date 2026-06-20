#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CH6.5.5 route_following_stability proxy admission review v1.1.

This script evaluates whether existing IB3C phase3c event evidence is mature
enough to promote route_following_stability from MISSING_EVIDENCE_ANNOTATION to
a LIMITED_PROXY_AXIS candidate.

It does not modify existing contracts, radar data tables, reports, Word/docx
files, or upstream evidence.
"""

from __future__ import annotations

import csv
import html
import math
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional


ROOT = Path("D:/mountain_work/115_osm")
EVENT_ROOT = ROOT / "outputs/ib3c_activity_behavior_events_adaptive_speed_v1_phase3c_recovery_interpretation_26batch"
RADAR_DATA_TABLE = ROOT / "outputs/report_figures/ch6_5_5_personal_ability_radar_data_table_v1/personal_ability_radar_data_table_v1.csv"
OUT_ROOT = ROOT / "outputs/report_figures/ch6_5_5_route_following_stability_proxy_admission_v1_1"

ROUTE_TEXT_COLS = [
    "event_type",
    "event_subtype",
    "event_modifiers",
    "candidate_reason",
    "recovery_interpretation",
    "semantic_event_type_candidate",
    "semantic_recovery_interpretation",
]

ROUTE_ISSUE_RE = re.compile(
    r"off[_ -]?route|detour|route_uncertainty|navigation_check|uncertainty|wrong[_ -]?branch|wrong|branch|deviation|rejoin|return|correction|backtrack|偏離|錯路|支線|導航|回主線|修正|折返",
    re.I,
)
OFF_ROUTE_RE = re.compile(r"off[_ -]?route|detour|deviation|wrong[_ -]?branch|wrong|branch|偏離|錯路|支線", re.I)
NAV_RE = re.compile(r"route_uncertainty|navigation_check|uncertainty|navigation|導航", re.I)
REJOIN_RE = re.compile(r"rejoin|return|correction|backtrack|回主線|修正|折返", re.I)
TERMINAL_RE = re.compile(r"terminal_artifact|endpoint_artifact|post_route|終點後", re.I)

FORBIDDEN = [
    "ability_score",
    "ability_rank",
    "ability_class",
    "radar_score",
    "thci_score",
    "final_hiking_risk_score",
    "route_suitability_score",
    "go_no_go",
    "diagnosis",
    "medical",
]


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: List[Dict[str, object]], fields: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def s(row: Dict[str, str], key: str) -> str:
    return str(row.get(key, "") or "")


def joined(row: Dict[str, str], keys: Iterable[str]) -> str:
    return " ".join(s(row, k) for k in keys)


def fnum(v: object) -> Optional[float]:
    if v is None:
        return None
    t = str(v).strip()
    if not t or t.lower() in {"nan", "none", "null"}:
        return None
    try:
        x = float(t)
        if math.isfinite(x):
            return x
    except Exception:
        pass
    return None


def mean(xs: List[Optional[float]]) -> Optional[float]:
    ys = [x for x in xs if x is not None]
    if not ys:
        return None
    return sum(ys) / len(ys)


def maxv(xs: List[Optional[float]]) -> Optional[float]:
    ys = [x for x in xs if x is not None]
    if not ys:
        return None
    return max(ys)


def minv(xs: List[Optional[float]]) -> Optional[float]:
    ys = [x for x in xs if x is not None]
    if not ys:
        return None
    return min(ys)


def sumv(xs: List[Optional[float]]) -> Optional[float]:
    ys = [x for x in xs if x is not None]
    if not ys:
        return None
    return sum(ys)


def bool_text(x: bool) -> str:
    return "True" if x else "False"


def group_by(rows: Iterable[Dict[str, str]], key: str) -> Dict[str, List[Dict[str, str]]]:
    out: Dict[str, List[Dict[str, str]]] = {}
    for row in rows:
        out.setdefault(s(row, key), []).append(row)
    return out


def load_baseline_status() -> Dict[str, str]:
    if not RADAR_DATA_TABLE.exists():
        return {}
    out: Dict[str, str] = {}
    for row in read_csv(RADAR_DATA_TABLE):
        act = s(row, "activity_id_short")
        pop = s(row, "study_population_status")
        if act and act not in out:
            out[act] = pop
    return out


def flags(row: Dict[str, str]) -> Dict[str, bool]:
    text = joined(row, ROUTE_TEXT_COLS)
    terminal = bool(TERMINAL_RE.search(text))
    return {
        "terminal_artifact": terminal,
        "route_issue_event": bool(ROUTE_ISSUE_RE.search(text)) and not terminal,
        "off_route_event": bool(OFF_ROUTE_RE.search(text)) and not terminal,
        "navigation_uncertainty_event": bool(NAV_RE.search(text)) and not terminal,
        "rejoin_candidate_event": bool(REJOIN_RE.search(text)) and not terminal,
    }


def candidate_value(
    route_issue_count: int,
    off_route_count: int,
    nav_count: int,
    rejoin_count: int,
    issue_duration_sec: Optional[float],
    max_offset_m: Optional[float],
    high_conf_issue_count: int,
) -> float:
    """Higher means more stable. This is a limited-proxy candidate only."""
    penalty = 0.0
    penalty += min(route_issue_count * 4.0, 32.0)
    penalty += min(off_route_count * 7.0, 35.0)
    penalty += min(nav_count * 4.0, 20.0)
    penalty += min(high_conf_issue_count * 3.0, 18.0)
    penalty += min((issue_duration_sec or 0.0) / 60.0 * 1.5, 25.0)

    off = max_offset_m or 0.0
    if off > 100:
        penalty += 10.0
    elif off > 60:
        penalty += 6.0
    elif off > 30:
        penalty += 3.0

    penalty -= min(rejoin_count * 2.0, 10.0)
    return round(max(0.0, min(100.0, 100.0 - penalty)), 2)


def html_table(rows: List[Dict[str, object]], cols: List[str]) -> str:
    parts = ["<table><thead><tr>"]
    for col in cols:
        parts.append(f"<th>{html.escape(col)}</th>")
    parts.append("</tr></thead><tbody>")
    for row in rows:
        parts.append("<tr>")
        for col in cols:
            parts.append(f"<td>{html.escape(str(row.get(col, '')))}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "\n".join(parts)


def write_report(audit: Dict[str, object], decisions: List[Dict[str, object]], activity_rows: List[Dict[str, object]]) -> None:
    css = """
    body { font-family: Arial, 'Microsoft JhengHei', sans-serif; margin: 24px; line-height: 1.45; }
    table { border-collapse: collapse; width: 100%; font-size: 13px; margin: 12px 0; }
    th, td { border: 1px solid #ddd; padding: 6px 8px; vertical-align: top; }
    th { background: #f2f2f2; }
    .card { border: 1px solid #ddd; border-radius: 8px; background: #fafafa; padding: 12px; margin: 12px 0; }
    """
    audit_cols = list(audit.keys())
    decision_cols = [
        "axis_id", "axis_label_zh", "current_axis_output_mode", "recommended_axis_output_mode",
        "admission_decision", "baseline_activity_count", "baseline_with_events_count",
        "baseline_with_route_issue_count", "extra_source_count", "extra_source_admitted_count",
        "proxy_basis", "review_reasons"
    ]
    activity_cols = [
        "activity_id", "study_population_status", "baseline_population_gate", "event_rows",
        "non_terminal_event_rows", "route_issue_event_count", "off_route_event_count",
        "navigation_uncertainty_event_count", "rejoin_candidate_event_count",
        "high_confidence_route_issue_count", "route_issue_duration_sec", "max_offset_m",
        "candidate_proxy_route_following_stability_0_100", "admission_status",
    ]
    text = f"""<!doctype html>
<html lang="zh-Hant">
<head><meta charset="utf-8"><title>Route Following Stability Proxy Admission v1</title><style>{css}</style></head>
<body>
<h1>CH6.5.5 Route Following Stability Proxy Admission v1</h1>
<div class="card">
<p><strong>Audit:</strong> {html.escape(str(audit.get("audit_conclusion", "")))}</p>
<p><strong>Boundary:</strong> {html.escape(str(audit.get("interpretation_boundary", "")))}</p>
</div>
<h2>Audit summary</h2>
{html_table([audit], audit_cols)}
<h2>Admission decisions</h2>
{html_table(decisions, decision_cols)}
<h2>Activity summary</h2>
{html_table(activity_rows, activity_cols)}
</body></html>"""
    (OUT_ROOT / "route_following_stability_proxy_admission_report_v1_1.html").write_text(text, encoding="utf-8")


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    baseline_status = load_baseline_status()

    events: List[Dict[str, str]] = []
    for path in sorted(EVENT_ROOT.rglob("*_ib3c_behavior_events.csv")):
        for row in read_csv(path):
            row["source_file"] = str(path)
            events.append(row)

    if not events:
        raise SystemExit(f"No event rows found under {EVENT_ROOT}")

    inventory: List[Dict[str, object]] = []
    for row in events:
        fl = flags(row)
        inventory.append({
            "activity_id": s(row, "activity_id"),
            "event_id": s(row, "event_id"),
            "event_type": s(row, "event_type"),
            "event_subtype": s(row, "event_subtype"),
            "event_modifiers": s(row, "event_modifiers"),
            "candidate_reason": s(row, "candidate_reason"),
            "semantic_event_type_candidate": s(row, "semantic_event_type_candidate"),
            "semantic_recovery_interpretation": s(row, "semantic_recovery_interpretation"),
            "duration_sec": s(row, "duration_sec"),
            "on_route_ratio": s(row, "on_route_ratio"),
            "off_route_ratio": s(row, "off_route_ratio"),
            "median_offset_m": s(row, "median_offset_m"),
            "max_offset_m": s(row, "max_offset_m"),
            "confidence": s(row, "confidence"),
            "terminal_artifact": bool_text(fl["terminal_artifact"]),
            "route_issue_event": bool_text(fl["route_issue_event"]),
            "off_route_event": bool_text(fl["off_route_event"]),
            "navigation_uncertainty_event": bool_text(fl["navigation_uncertainty_event"]),
            "rejoin_candidate_event": bool_text(fl["rejoin_candidate_event"]),
            "source_file": s(row, "source_file"),
            "route_following_text_basis": joined(row, ROUTE_TEXT_COLS),
        })

    activity_rows: List[Dict[str, object]] = []
    event_groups = group_by(events, "activity_id")
    all_activity_ids = sorted(set(baseline_status.keys()) | set(event_groups.keys()))

    for act in all_activity_ids:
        rows = event_groups.get(act, [])
        pop = baseline_status.get(act, "UNKNOWN_POPULATION_STATUS")
        baseline_ok = pop == "RADAR_BASELINE_ACTIVITY"
        detector_file_found = len(rows) > 0

        row_flags = [flags(r) for r in rows]
        terminal = [r for r, fl in zip(rows, row_flags) if fl["terminal_artifact"]]
        non_terminal = [r for r, fl in zip(rows, row_flags) if not fl["terminal_artifact"]]
        route_issue = [r for r, fl in zip(rows, row_flags) if fl["route_issue_event"]]
        off_route = [r for r, fl in zip(rows, row_flags) if fl["off_route_event"]]
        nav = [r for r, fl in zip(rows, row_flags) if fl["navigation_uncertainty_event"]]
        rejoin = [r for r, fl in zip(rows, row_flags) if fl["rejoin_candidate_event"]]

        issue_duration = sumv([fnum(r.get("duration_sec")) for r in route_issue])
        total_duration = sumv([fnum(r.get("duration_sec")) for r in rows])
        max_offset = maxv([fnum(r.get("max_offset_m")) for r in non_terminal])
        mean_off = mean([fnum(r.get("off_route_ratio")) for r in non_terminal])
        min_on = minv([fnum(r.get("on_route_ratio")) for r in non_terminal])

        high_conf = 0
        low_conf = 0
        for r in route_issue:
            c = fnum(r.get("confidence"))
            if c is not None and c >= 0.7:
                high_conf += 1
            if c is None or c < 0.6:
                low_conf += 1

        value = candidate_value(len(route_issue), len(off_route), len(nav), len(rejoin), issue_duration, max_offset, high_conf)

        if not baseline_ok:
            admission = "BLOCKED_EXTRA_SOURCE_NOT_BASELINE"
            value_out: object = ""
            evidence_state = "EXTRA_SOURCE_BLOCKED"
            note = "Extra source activity is excluded from formal baseline proxy admission."
        elif not detector_file_found:
            admission = "MISSING_DETECTOR_FILE_REVIEW_REQUIRED"
            value_out = ""
            evidence_state = "MISSING_DETECTOR_FILE"
            note = "No IB3C detector output file found for this baseline activity."
        elif len(route_issue) == 0:
            admission = "LIMITED_PROXY_CANDIDATE_NO_NON_TERMINAL_ROUTE_ISSUE_DETECTED"
            value_out = 100.0
            evidence_state = "DETECTOR_COVERED_NO_ROUTE_ISSUE"
            note = "Detector file exists; no non-terminal route-following issue detected. Terminal artifacts are excluded."
        else:
            admission = "LIMITED_PROXY_CANDIDATE_FOR_ROUTE_FOLLOWING_STABILITY"
            value_out = value
            evidence_state = "DETECTOR_COVERED_ROUTE_ISSUE_BURDEN"
            note = "LIMITED_PROXY_CANDIDATE_EVENT_BURDEN_MODEL_NOT_FORMAL_SCORE"

        activity_rows.append({
            "activity_id": act,
            "study_population_status": pop,
            "baseline_population_gate": "PASS" if baseline_ok else "BLOCKED_EXTRA_SOURCE",
            "detector_file_found": bool_text(detector_file_found),
            "evidence_state": evidence_state,
            "event_rows": len(rows),
            "terminal_event_rows": len(terminal),
            "non_terminal_event_rows": len(non_terminal),
            "route_issue_event_count": len(route_issue),
            "off_route_event_count": len(off_route),
            "navigation_uncertainty_event_count": len(nav),
            "rejoin_candidate_event_count": len(rejoin),
            "high_confidence_route_issue_count": high_conf,
            "low_confidence_route_issue_count": low_conf,
            "route_issue_duration_sec": round(issue_duration, 3) if issue_duration is not None else "",
            "total_event_duration_sec": round(total_duration, 3) if total_duration is not None else "",
            "max_offset_m": round(max_offset, 3) if max_offset is not None else "",
            "mean_off_route_ratio": round(mean_off, 4) if mean_off is not None else "",
            "min_on_route_ratio": round(min_on, 4) if min_on is not None else "",
            "candidate_proxy_route_following_stability_0_100": value_out,
            "candidate_proxy_note": note,
            "admission_status": admission,
            "allowed_use": "Descriptive governed limited proxy admission review for route_following_stability only.",
            "disallowed_use": "Do not use as ability score, rank, class, THCI score, final hiking risk score, route suitability score, or go/no-go decision.",
        })

    baseline = [r for r in activity_rows if r["study_population_status"] == "RADAR_BASELINE_ACTIVITY"]
    extra = [r for r in activity_rows if r["study_population_status"] != "RADAR_BASELINE_ACTIVITY"]
    baseline_activity_count = len(baseline)
    baseline_detector_file_found_count = sum(1 for r in baseline if r["detector_file_found"] == "True")
    baseline_no_non_terminal_issue_count = sum(1 for r in baseline if r["evidence_state"] == "DETECTOR_COVERED_NO_ROUTE_ISSUE")
    baseline_with_events = sum(1 for r in baseline if int(r["non_terminal_event_rows"]) > 0)
    baseline_with_route_issue = sum(1 for r in baseline if int(r["route_issue_event_count"]) > 0)
    extra_admitted = sum(1 for r in extra if str(r["admission_status"]).startswith("LIMITED_PROXY_CANDIDATE"))

    reasons: List[str] = []
    if baseline_activity_count < 25:
        reasons.append("Baseline activity coverage is below expected 25.")
    if baseline_detector_file_found_count < baseline_activity_count:
        reasons.append("Not all baseline activities have IB3C detector output files.")
    if extra_admitted > 0:
        reasons.append("Extra source activity was incorrectly admitted.")

    if reasons:
        route_decision = "RETAIN_AS_MISSING_EVIDENCE_OR_REVIEW_REQUIRED"
        route_recommendation = "MISSING_EVIDENCE_ANNOTATION"
    else:
        route_decision = "ADMIT_AS_LIMITED_PROXY_AXIS_CANDIDATE_REQUIRES_CONTRACT_PATCH"
        route_recommendation = "LIMITED_PROXY_AXIS"

    deviation_decision = "RETAIN_AS_CANDIDATE_REQUIRES_EVENT_CHAIN_REVIEW"

    decisions = [
        {
            "axis_id": "route_following_stability",
            "axis_label_zh": "路線跟隨穩定性",
            "current_axis_output_mode": "MISSING_EVIDENCE_ANNOTATION",
            "recommended_axis_output_mode": route_recommendation,
            "admission_decision": route_decision,
            "baseline_activity_count": baseline_activity_count,
            "baseline_detector_file_found_count": baseline_detector_file_found_count,
            "baseline_no_non_terminal_issue_count": baseline_no_non_terminal_issue_count,
            "baseline_with_events_count": baseline_with_events,
            "baseline_with_route_issue_count": baseline_with_route_issue,
            "extra_source_count": len(extra),
            "extra_source_admitted_count": extra_admitted,
            "evidence_source": str(EVENT_ROOT.relative_to(ROOT)),
            "evidence_fields": "event_type|event_subtype|event_modifiers|candidate_reason|semantic_event_type_candidate|semantic_recovery_interpretation|on_route_ratio|off_route_ratio|max_offset_m|confidence|duration_sec",
            "proxy_basis": "route issue event burden: off_route / route_uncertainty / navigation_check / rejoin candidate evidence",
            "review_reasons": "|".join(reasons) if reasons else "NONE",
            "interpretation_boundary": "Governed limited proxy admission only; not an ability score, rank, class, final risk score, or go/no-go decision.",
        },
        {
            "axis_id": "deviation_correction_ability",
            "axis_label_zh": "偏離修正能力",
            "current_axis_output_mode": "MISSING_EVIDENCE_ANNOTATION",
            "recommended_axis_output_mode": "MISSING_EVIDENCE_ANNOTATION",
            "admission_decision": deviation_decision,
            "baseline_activity_count": baseline_activity_count,
            "baseline_detector_file_found_count": baseline_detector_file_found_count,
            "baseline_no_non_terminal_issue_count": baseline_no_non_terminal_issue_count,
            "baseline_with_events_count": baseline_with_events,
            "baseline_with_route_issue_count": baseline_with_route_issue,
            "extra_source_count": len(extra),
            "extra_source_admitted_count": 0,
            "evidence_source": str(EVENT_ROOT.relative_to(ROOT)),
            "evidence_fields": "semantic_recovery_interpretation|event_subtype|candidate_reason|rejoin_candidate_event",
            "proxy_basis": "Candidate only; rejoin/correction chain not yet validated.",
            "review_reasons": "Needs formal deviation-start to correction/rejoin event-chain review.",
            "interpretation_boundary": "Do not admit deviation correction ability from route issue keywords alone.",
        },
    ]

    forbidden_fields = sorted({k for row in activity_rows + decisions for k in row.keys() if any(p in k.lower() for p in FORBIDDEN)})
    if forbidden_fields:
        audit = "FAIL_FORBIDDEN_FIELDS_PRESENT"
        audit_reasons = "Forbidden fields present: " + "|".join(forbidden_fields)
    elif extra_admitted > 0:
        audit = "FAIL_EXTRA_SOURCE_ADMITTED"
        audit_reasons = "Extra source activity admitted."
    elif route_decision.startswith("ADMIT"):
        audit = "PASS_CH6_5_5_ROUTE_FOLLOWING_STABILITY_PROXY_ADMISSION_V1_1_GOVERNED_LIMITED_PROXY_CANDIDATE"
        audit_reasons = "NONE"
    else:
        audit = "REVIEW_REQUIRED_ROUTE_FOLLOWING_STABILITY_PROXY_ADMISSION_V1_1"
        audit_reasons = "|".join(reasons) if reasons else "REVIEW_REQUIRED"

    audit_row = {
        "source_event_root": str(EVENT_ROOT.relative_to(ROOT)),
        "event_rows": len(events),
        "activity_rows": len(activity_rows),
        "baseline_activity_count": baseline_activity_count,
        "baseline_detector_file_found_count": baseline_detector_file_found_count,
        "baseline_no_non_terminal_issue_count": baseline_no_non_terminal_issue_count,
        "baseline_with_events_count": baseline_with_events,
        "baseline_with_route_issue_count": baseline_with_route_issue,
        "extra_source_count": len(extra),
        "extra_source_admitted_count": extra_admitted,
        "route_following_admission_decision": route_decision,
        "deviation_correction_decision": deviation_decision,
        "zero_fill_used": False,
        "forbidden_fields_present": "|".join(forbidden_fields),
        "ability_scoring_absent": True,
        "ranking_absent": True,
        "class_label_absent": True,
        "decision_label_absent": True,
        "audit_conclusion": audit,
        "review_reasons": audit_reasons,
        "interpretation_boundary": "Governed limited proxy admission review only. No score, rank, class, final hiking risk score, route suitability score, go/no-go decision, medical diagnosis, or causal claim.",
    }

    write_csv(
        OUT_ROOT / "route_following_stability_proxy_event_inventory_v1_1.csv",
        inventory,
        [
            "activity_id", "event_id", "event_type", "event_subtype", "event_modifiers",
            "candidate_reason", "semantic_event_type_candidate", "semantic_recovery_interpretation",
            "duration_sec", "on_route_ratio", "off_route_ratio", "median_offset_m", "max_offset_m",
            "confidence", "terminal_artifact", "route_issue_event", "off_route_event",
            "navigation_uncertainty_event", "rejoin_candidate_event", "source_file", "route_following_text_basis",
        ],
    )
    write_csv(
        OUT_ROOT / "route_following_stability_proxy_activity_summary_v1_1.csv",
        activity_rows,
        [
            "activity_id", "study_population_status", "baseline_population_gate", "detector_file_found",
            "evidence_state", "event_rows", "terminal_event_rows", "non_terminal_event_rows",
            "route_issue_event_count", "off_route_event_count",
            "navigation_uncertainty_event_count", "rejoin_candidate_event_count",
            "high_confidence_route_issue_count", "low_confidence_route_issue_count",
            "route_issue_duration_sec", "total_event_duration_sec", "max_offset_m",
            "mean_off_route_ratio", "min_on_route_ratio", "candidate_proxy_route_following_stability_0_100",
            "candidate_proxy_note", "admission_status", "allowed_use", "disallowed_use",
        ],
    )
    write_csv(
        OUT_ROOT / "route_following_stability_proxy_admission_decision_v1_1.csv",
        decisions,
        [
            "axis_id", "axis_label_zh", "current_axis_output_mode", "recommended_axis_output_mode",
            "admission_decision", "baseline_activity_count", "baseline_detector_file_found_count",
            "baseline_no_non_terminal_issue_count", "baseline_with_events_count",
            "baseline_with_route_issue_count", "extra_source_count", "extra_source_admitted_count",
            "evidence_source", "evidence_fields", "proxy_basis", "review_reasons", "interpretation_boundary",
        ],
    )
    write_csv(
        OUT_ROOT / "route_following_stability_proxy_admission_audit_v1_1.csv",
        [audit_row],
        [
            "source_event_root", "event_rows", "activity_rows", "baseline_activity_count",
            "baseline_detector_file_found_count", "baseline_no_non_terminal_issue_count", "baseline_with_events_count", "baseline_with_route_issue_count", "extra_source_count",
            "extra_source_admitted_count", "route_following_admission_decision",
            "deviation_correction_decision", "zero_fill_used", "forbidden_fields_present",
            "ability_scoring_absent", "ranking_absent", "class_label_absent", "decision_label_absent",
            "audit_conclusion", "review_reasons", "interpretation_boundary",
        ],
    )
    write_report(audit_row, decisions, activity_rows)

    print({
        "output_root": str(OUT_ROOT),
        "event_rows": len(events),
        "activity_rows": len(activity_rows),
        "baseline_activity_count": baseline_activity_count,
        "baseline_with_route_issue_count": baseline_with_route_issue,
        "extra_source_admitted_count": extra_admitted,
        "route_following_admission_decision": route_decision,
        "audit_conclusion": audit,
    })


if __name__ == "__main__":
    main()
