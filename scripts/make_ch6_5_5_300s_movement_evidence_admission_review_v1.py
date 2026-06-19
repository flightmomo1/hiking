#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build CH6.5.5 300s movement evidence admission review v1.

This script reviews whether 300-second movement evidence from the corrected-data
study is suitable for radar-axis admission. It does not compute radar scores,
ability scores, ability ranks, ability classes, go/no-go decisions, medical
diagnoses, or causality claims.
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_INPUT_ROOT = "outputs/report_figures/ch6_5_5_movement_300s_corrected_data_study_v1_1"
DEFAULT_OUTPUT_ROOT = "outputs/report_figures/ch6_5_5_300s_movement_evidence_admission_review_v1"

BOUNDARY = (
    "CH6.5.5 300s movement evidence admission review v1 is admission-review evidence only. "
    "It reviews corrected 300-second horizontal, vertical, HR, route-continuity, and artifact-guard "
    "evidence. It does not compute or authorize radar scores, ability scores, ability ranks, "
    "ability classes, THCI scores, final hiking risk scores, route suitability scores, go/no-go "
    "decisions, medical diagnoses, or causality claims."
)

PASS = "PASS_CH6_5_5_300S_MOVEMENT_EVIDENCE_ADMISSION_REVIEW_V1_DESCRIPTIVE_ONLY"
REVIEW = "REVIEW_REQUIRED_CH6_5_5_300S_MOVEMENT_EVIDENCE_ADMISSION_REVIEW_V1"

FORBIDDEN_OUTPUT_PATTERNS = [
    "radar_score",
    "ability_score",
    "ability_rank",
    "ability_class",
    "go_no_go",
    "go/no-go",
    "medical_diagnosis",
    "causality_claim",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=r"D:\mountain_work\115_osm")
    parser.add_argument("--input-root", default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--min-standalone-coverage-ratio", type=float, default=0.50)
    parser.add_argument("--min-standalone-valid-window-count", type=int, default=50)
    return parser.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    p = Path(value)
    return p if p.is_absolute() else root / p


def read_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def pct(n: int, d: int) -> float:
    return float(n / d) if d else np.nan


def bool_count(df: pd.DataFrame, col: str) -> int:
    if df.empty or col not in df.columns:
        return 0
    return int(df[col].astype(str).str.lower().isin(["true", "1", "yes"]).sum())


def count_status(df: pd.DataFrame, col: str, value: str) -> int:
    if df.empty or col not in df.columns:
        return 0
    return int(df[col].astype(str).eq(value).sum())


def safe_max(df: pd.DataFrame, col: str) -> float:
    if df.empty or col not in df.columns:
        return np.nan
    v = to_num(df[col]).dropna()
    return float(v.max()) if len(v) else np.nan


def safe_median(df: pd.DataFrame, col: str) -> float:
    if df.empty or col not in df.columns:
        return np.nan
    v = to_num(df[col]).dropna()
    return float(v.median()) if len(v) else np.nan


def build_activity_coverage(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, r in summary.iterrows():
        is_baseline = str(r.get("study_population_status", "")) == "RADAR_BASELINE_ACTIVITY"
        h_count = int(float(r.get("horizontal_300s_valid_window_count", 0) or 0))
        v_count = int(float(r.get("vertical_300s_valid_window_count", 0) or 0))
        rows.append({
            "activity_id_short": r.get("activity_id_short", ""),
            "study_population_status": r.get("study_population_status", ""),
            "in_radar_baseline": is_baseline,
            "has_horizontal_300s_evidence": h_count > 0,
            "has_vertical_300s_evidence": v_count > 0,
            "has_both_horizontal_and_vertical_300s_evidence": h_count > 0 and v_count > 0,
            "horizontal_300s_valid_window_count": h_count,
            "horizontal_300s_route_speed_p90_mps": r.get("horizontal_300s_route_speed_p90_mps", np.nan),
            "vertical_300s_valid_window_count": v_count,
            "vertical_300s_gain_p90_m": r.get("vertical_300s_gain_p90_m", np.nan),
            "vertical_300s_vam_p90_mph": r.get("vertical_300s_vam_p90_mph", np.nan),
            "horizontal_hr_p90_pct_hrmax_at_speed_p90_window": r.get("horizontal_300s_hr_at_speed_p90_window_hr_p90_pct_hrmax_at_window", np.nan),
            "vertical_hr_p90_pct_hrmax_at_vam_p90_window": r.get("vertical_300s_hr_at_vam_p90_window_hr_p90_pct_hrmax_at_window", np.nan),
            "profile_join_status": r.get("profile_join_status", ""),
            "interpretation_boundary": BOUNDARY,
        })
    return pd.DataFrame(rows).sort_values(["study_population_status", "activity_id_short"])


def axis_decision_rows(
    summary: pd.DataFrame,
    windows: pd.DataFrame,
    audit: pd.DataFrame,
    min_cov: float,
    min_windows: int,
) -> pd.DataFrame:
    baseline = summary[summary["study_population_status"].astype(str).eq("RADAR_BASELINE_ACTIVITY")].copy()
    baseline_n = int(len(baseline))

    h_activity_n = int((to_num(baseline["horizontal_300s_valid_window_count"]) > 0).sum()) if baseline_n else 0
    v_activity_n = int((to_num(baseline["vertical_300s_valid_window_count"]) > 0).sum()) if baseline_n else 0
    both_activity_n = int(((to_num(baseline["horizontal_300s_valid_window_count"]) > 0) & (to_num(baseline["vertical_300s_valid_window_count"]) > 0)).sum()) if baseline_n else 0

    h_window_n = int(audit.iloc[0].get("horizontal_valid_window_count", 0)) if not audit.empty else 0
    v_window_n = int(audit.iloc[0].get("vertical_valid_window_count", 0)) if not audit.empty else 0
    route_ok_n = int(audit.iloc[0].get("route_ok_window_count", 0)) if not audit.empty else 0
    positive_artifact_reject_n = int(audit.iloc[0].get("vertical_rejected_by_positive_delta_artifact_suspect_count", 0)) if not audit.empty else 0

    h_cov = pct(h_activity_n, baseline_n)
    v_cov = pct(v_activity_n, baseline_n)
    both_cov = pct(both_activity_n, baseline_n)

    h_admit = h_cov >= min_cov and h_window_n >= min_windows
    v_admit = v_cov >= min_cov and v_window_n >= min_windows

    rows = [
        {
            "review_item": "horizontal_300s_route_speed_p90_mps",
            "review_type": "candidate_performance_axis",
            "baseline_activity_count": baseline_n,
            "covered_baseline_activity_count": h_activity_n,
            "coverage_ratio": h_cov,
            "valid_window_count": h_window_n,
            "admission_status": "DO_NOT_ADMIT_STANDALONE_RETAIN_DESCRIPTIVE_LIMITED_COVERAGE" if not h_admit else "ADMIT_CANDIDATE_AXIS_FOR_DOWNSTREAM_REVIEW",
            "primary_reason": "baseline activity coverage below standalone threshold or window count below threshold" if not h_admit else "coverage and window count pass configured review thresholds",
            "allowed_use": "descriptive_supporting_evidence_only",
            "disallowed_use": "standalone_radar_axis_or_ability_ranking",
            "interpretation_boundary": BOUNDARY,
        },
        {
            "review_item": "vertical_300s_vam_p90_mph",
            "review_type": "candidate_performance_axis",
            "baseline_activity_count": baseline_n,
            "covered_baseline_activity_count": v_activity_n,
            "coverage_ratio": v_cov,
            "valid_window_count": v_window_n,
            "admission_status": "DO_NOT_ADMIT_STANDALONE_RETAIN_DESCRIPTIVE_LIMITED_COVERAGE" if not v_admit else "ADMIT_CANDIDATE_AXIS_FOR_DOWNSTREAM_REVIEW",
            "primary_reason": "baseline activity coverage below standalone threshold or window count below threshold" if not v_admit else "coverage and window count pass configured review thresholds",
            "allowed_use": "descriptive_supporting_evidence_only",
            "disallowed_use": "standalone_radar_axis_or_ability_ranking",
            "interpretation_boundary": BOUNDARY,
        },
        {
            "review_item": "vertical_300s_gain_p90_m",
            "review_type": "candidate_performance_axis_support",
            "baseline_activity_count": baseline_n,
            "covered_baseline_activity_count": v_activity_n,
            "coverage_ratio": v_cov,
            "valid_window_count": v_window_n,
            "admission_status": "DO_NOT_ADMIT_STANDALONE_RETAIN_AS_VERTICAL_CONTEXT",
            "primary_reason": "gain magnitude is useful as context but should not be separated from VAM, route continuity, and artifact guard",
            "allowed_use": "vertical_context_for_interpretation",
            "disallowed_use": "standalone_score_or_rank",
            "interpretation_boundary": BOUNDARY,
        },
        {
            "review_item": "hr_at_representative_300s_windows",
            "review_type": "supporting_context",
            "baseline_activity_count": baseline_n,
            "covered_baseline_activity_count": int(((baseline.get("horizontal_300s_hr_at_speed_p90_window_hr_p90_pct_hrmax_at_window").notna()) | (baseline.get("vertical_300s_hr_at_vam_p90_window_hr_p90_pct_hrmax_at_window").notna())).sum()),
            "coverage_ratio": np.nan,
            "valid_window_count": int(audit.iloc[0].get("hr_valid_window_count", 0)) if not audit.empty else 0,
            "admission_status": "RETAIN_AS_SUPPORTING_CONTEXT_ONLY",
            "primary_reason": "HR context depends on estimated HRmax and should support interpretation rather than define ability",
            "allowed_use": "load_context_for_horizontal_or_vertical_windows",
            "disallowed_use": "medical_diagnosis_or_standalone_ability_axis",
            "interpretation_boundary": BOUNDARY,
        },
        {
            "review_item": "route_continuity_300s_gate",
            "review_type": "qa_gate",
            "baseline_activity_count": baseline_n,
            "covered_baseline_activity_count": baseline_n,
            "coverage_ratio": 1.0 if baseline_n else np.nan,
            "valid_window_count": route_ok_n,
            "admission_status": "ADMIT_AS_REQUIRED_QA_GATE",
            "primary_reason": "required to prevent route-axis reversal or jump windows from entering movement evidence",
            "allowed_use": "quality_gate",
            "disallowed_use": "performance_axis",
            "interpretation_boundary": BOUNDARY,
        },
        {
            "review_item": "positive_delta_artifact_guard",
            "review_type": "qa_guard",
            "baseline_activity_count": baseline_n,
            "covered_baseline_activity_count": baseline_n,
            "coverage_ratio": 1.0 if baseline_n else np.nan,
            "valid_window_count": positive_artifact_reject_n,
            "admission_status": "ADMIT_AS_REQUIRED_VERTICAL_QA_GUARD",
            "primary_reason": "positive-delta elevation can over-accumulate artifact; guard is required before vertical evidence is interpreted",
            "allowed_use": "vertical_quality_guard",
            "disallowed_use": "performance_axis",
            "interpretation_boundary": BOUNDARY,
        },
        {
            "review_item": "combined_horizontal_vertical_300s_evidence",
            "review_type": "combined_evidence_coverage_review",
            "baseline_activity_count": baseline_n,
            "covered_baseline_activity_count": both_activity_n,
            "coverage_ratio": both_cov,
            "valid_window_count": h_window_n + v_window_n,
            "admission_status": "DO_NOT_ADMIT_COMBINED_STANDALONE_LIMITED_OVERLAP",
            "primary_reason": "only activities with both horizontal and vertical evidence can support combined movement interpretation",
            "allowed_use": "case-level_review_context",
            "disallowed_use": "combined_score_or_rank",
            "interpretation_boundary": BOUNDARY,
        },
    ]

    return pd.DataFrame(rows)


def build_audit(
    input_audit: pd.DataFrame,
    axis_decision: pd.DataFrame,
    coverage: pd.DataFrame,
    output_columns: list[str],
) -> pd.DataFrame:
    forbidden = [c for c in output_columns if any(p in c.lower() for p in FORBIDDEN_OUTPUT_PATTERNS)]
    baseline = coverage[coverage["study_population_status"].astype(str).eq("RADAR_BASELINE_ACTIVITY")]
    extra = coverage[coverage["study_population_status"].astype(str).ne("RADAR_BASELINE_ACTIVITY")]

    review_reasons = []
    if input_audit.empty:
        review_reasons.append("MISSING_INPUT_AUDIT")
    if forbidden:
        review_reasons.append("FORBIDDEN_FIELD_PRESENT")
    if not input_audit.empty and not str(input_audit.iloc[0].get("audit_conclusion", "")).startswith("PASS_"):
        review_reasons.append("INPUT_AUDIT_NOT_PASS")

    row = {
        "input_audit_conclusion": input_audit.iloc[0].get("audit_conclusion", "") if not input_audit.empty else "",
        "baseline_activity_count": int(len(baseline)),
        "extra_source_activity_count": int(len(extra)),
        "extra_source_activities": "|".join(extra["activity_id_short"].astype(str)) if len(extra) else "NONE",
        "horizontal_evidence_activity_count": int(baseline["has_horizontal_300s_evidence"].sum()) if len(baseline) else 0,
        "vertical_evidence_activity_count": int(baseline["has_vertical_300s_evidence"].sum()) if len(baseline) else 0,
        "both_horizontal_vertical_evidence_activity_count": int(baseline["has_both_horizontal_and_vertical_300s_evidence"].sum()) if len(baseline) else 0,
        "standalone_axis_admitted_count": int(axis_decision["admission_status"].astype(str).str.startswith("ADMIT_CANDIDATE_AXIS").sum()) if not axis_decision.empty else 0,
        "qa_gate_or_guard_admitted_count": int(axis_decision["admission_status"].astype(str).isin(["ADMIT_AS_REQUIRED_QA_GATE", "ADMIT_AS_REQUIRED_VERTICAL_QA_GUARD"]).sum()) if not axis_decision.empty else 0,
        "zero_fill_used": False,
        "forbidden_score_rank_class_fields_present": bool(forbidden),
        "forbidden_fields": "|".join(forbidden) if forbidden else "NONE",
        "radar_scoring_absent": True,
        "ability_scoring_absent": True,
        "ranking_absent": True,
        "class_label_absent": True,
        "decision_label_absent": True,
        "diagnosis_absent": True,
        "causal_claim_absent": True,
        "audit_conclusion": REVIEW if review_reasons else PASS,
        "review_reasons": "|".join(review_reasons) if review_reasons else "NONE",
        "interpretation_boundary": BOUNDARY,
    }
    return pd.DataFrame([row])


def write_html(out_path: Path, audit: pd.DataFrame, axis_decision: pd.DataFrame, coverage: pd.DataFrame) -> None:
    def table(df: pd.DataFrame, cols: list[str], n: int = 50) -> str:
        if df.empty:
            return "<p>No rows.</p>"
        use = [c for c in cols if c in df.columns]
        return df[use].head(n).to_html(index=False, escape=True, classes="data")

    conclusion = audit.iloc[0]["audit_conclusion"] if not audit.empty else REVIEW
    body = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CH6.5.5 300s Movement Evidence Admission Review v1</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2933; }}
h1, h2 {{ margin-bottom: 8px; }}
.boundary {{ border-left: 4px solid #687078; padding: 8px 12px; background: #f5f7f8; }}
.status {{ font-weight: 700; }}
table.data {{ border-collapse: collapse; font-size: 12px; margin: 12px 0 24px; }}
table.data th, table.data td {{ border: 1px solid #d6dde3; padding: 5px 7px; }}
table.data th {{ background: #eef2f5; }}
</style>
</head>
<body>
<h1>CH6.5.5 300s Movement Evidence Admission Review v1</h1>
<p class="status">{html.escape(str(conclusion))}</p>
<p class="boundary">{html.escape(BOUNDARY)}</p>
<h2>Audit</h2>
{table(audit, list(audit.columns), 5)}
<h2>Axis Admission Review</h2>
{table(axis_decision, ["review_item", "review_type", "covered_baseline_activity_count", "baseline_activity_count", "coverage_ratio", "valid_window_count", "admission_status", "primary_reason", "allowed_use", "disallowed_use"], 20)}
<h2>Activity Coverage</h2>
{table(coverage, ["activity_id_short", "study_population_status", "has_horizontal_300s_evidence", "horizontal_300s_valid_window_count", "horizontal_300s_route_speed_p90_mps", "has_vertical_300s_evidence", "vertical_300s_valid_window_count", "vertical_300s_gain_p90_m", "vertical_300s_vam_p90_mph", "has_both_horizontal_and_vertical_300s_evidence"], 50)}
</body>
</html>
"""
    out_path.write_text(body, encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    input_root = resolve(root, args.input_root)
    out_root = resolve(root, args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)

    input_audit = read_csv(input_root / "movement_300s_audit_v1_1.csv", "movement 300s audit v1.1")
    summary = read_csv(input_root / "movement_300s_activity_summary_v1_1.csv", "movement 300s activity summary v1.1")
    windows = read_csv(input_root / "movement_300s_window_candidates_v1_1.csv", "movement 300s window candidates v1.1")

    coverage = build_activity_coverage(summary)
    axis_decision = axis_decision_rows(
        summary=summary,
        windows=windows,
        audit=input_audit,
        min_cov=args.min_standalone_coverage_ratio,
        min_windows=args.min_standalone_valid_window_count,
    )

    output_columns = list(coverage.columns) + list(axis_decision.columns)
    audit = build_audit(input_audit, axis_decision, coverage, output_columns)

    outputs = {
        "axis_decision": out_root / "movement_300s_admission_axis_decision_v1.csv",
        "activity_coverage": out_root / "movement_300s_admission_activity_coverage_v1.csv",
        "audit": out_root / "movement_300s_admission_audit_v1.csv",
        "html": out_root / "movement_300s_admission_review_report_v1.html",
    }

    axis_decision.to_csv(outputs["axis_decision"], index=False, encoding="utf-8-sig")
    coverage.to_csv(outputs["activity_coverage"], index=False, encoding="utf-8-sig")
    audit.to_csv(outputs["audit"], index=False, encoding="utf-8-sig")
    write_html(outputs["html"], audit, axis_decision, coverage)

    print({
        "output_root": str(out_root),
        "baseline_activity_count": int(audit.iloc[0]["baseline_activity_count"]),
        "horizontal_evidence_activity_count": int(audit.iloc[0]["horizontal_evidence_activity_count"]),
        "vertical_evidence_activity_count": int(audit.iloc[0]["vertical_evidence_activity_count"]),
        "standalone_axis_admitted_count": int(audit.iloc[0]["standalone_axis_admitted_count"]),
        "qa_gate_or_guard_admitted_count": int(audit.iloc[0]["qa_gate_or_guard_admitted_count"]),
        "audit_conclusion": str(audit.iloc[0]["audit_conclusion"]),
        "outputs": {k: str(v) for k, v in outputs.items()},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
