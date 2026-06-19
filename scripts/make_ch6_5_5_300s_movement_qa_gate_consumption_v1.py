#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build CH6.5.5 300s movement QA gate consumption v1.

This script consumes the CH6.5.5 300s movement evidence admission review and
materializes downstream consumption rules for 300-second movement evidence.

It does not compute radar scores, ability scores, ability ranks, ability classes,
THCI scores, final hiking risk scores, route suitability scores, go/no-go
decisions, medical diagnoses, or causality claims.
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_STUDY_ROOT = "outputs/report_figures/ch6_5_5_movement_300s_corrected_data_study_v1_1"
DEFAULT_ADMISSION_ROOT = "outputs/report_figures/ch6_5_5_300s_movement_evidence_admission_review_v1"
DEFAULT_OUTPUT_ROOT = "outputs/report_figures/ch6_5_5_300s_movement_qa_gate_consumption_v1"

BOUNDARY = (
    "CH6.5.5 300s movement QA gate consumption v1 is a downstream consumption "
    "gate layer only. It consumes admission-review results and marks which 300s "
    "movement evidence rows may be referenced as descriptive supporting evidence. "
    "It does not compute or authorize radar scores, ability scores, ability ranks, "
    "ability classes, THCI scores, final hiking risk scores, route suitability scores, "
    "go/no-go decisions, medical diagnoses, or causality claims."
)

PASS = "PASS_CH6_5_5_300S_MOVEMENT_QA_GATE_CONSUMPTION_V1_DESCRIPTIVE_ONLY"
REVIEW = "REVIEW_REQUIRED_CH6_5_5_300S_MOVEMENT_QA_GATE_CONSUMPTION_V1"

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
    parser.add_argument("--study-root", default=DEFAULT_STUDY_ROOT)
    parser.add_argument("--admission-root", default=DEFAULT_ADMISSION_ROOT)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
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


def truthy_series(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(False, index=df.index)
    return df[col].astype(str).str.lower().isin(["true", "1", "yes"])


def status_eq(df: pd.DataFrame, col: str | None, value: str) -> pd.Series:
    if col is None or col not in df.columns:
        return pd.Series(False, index=df.index)
    return df[col].astype(str).eq(value)


def first_existing(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def build_policy(axis_decision: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    def decision(item: str) -> dict[str, Any]:
        if axis_decision.empty or "review_item" not in axis_decision.columns:
            return {}
        hit = axis_decision[axis_decision["review_item"].astype(str).eq(item)]
        if hit.empty:
            return {}
        return hit.iloc[0].to_dict()

    policy_items = [
        {
            "policy_item": "route_continuity_300s_gate",
            "policy_type": "required_consumption_gate",
            "source_review_item": "route_continuity_300s_gate",
            "consumption_rule": "required before any horizontal or vertical 300s movement evidence is referenced downstream",
            "allowed_downstream_use": "quality_gate",
            "disallowed_downstream_use": "performance_axis_or_score",
        },
        {
            "policy_item": "positive_delta_artifact_guard",
            "policy_type": "required_vertical_consumption_guard",
            "source_review_item": "positive_delta_artifact_guard",
            "consumption_rule": "required before any vertical 300s movement evidence is referenced downstream",
            "allowed_downstream_use": "vertical_quality_guard",
            "disallowed_downstream_use": "performance_axis_or_score",
        },
        {
            "policy_item": "baseline_population_gate",
            "policy_type": "required_population_gate",
            "source_review_item": "activity_coverage",
            "consumption_rule": "formal downstream tables may consume only RADAR_BASELINE_ACTIVITY rows; extra source activities remain review-only",
            "allowed_downstream_use": "population_filter",
            "disallowed_downstream_use": "adding_extra_activity_to_baseline_without_review",
        },
        {
            "policy_item": "horizontal_300s_route_speed_p90_mps",
            "policy_type": "descriptive_supporting_evidence",
            "source_review_item": "horizontal_300s_route_speed_p90_mps",
            "consumption_rule": "may be referenced only as descriptive supporting evidence after route continuity and population gates pass",
            "allowed_downstream_use": "descriptive_supporting_evidence_only",
            "disallowed_downstream_use": "standalone_radar_axis_or_ability_ranking",
        },
        {
            "policy_item": "vertical_300s_vam_p90_mph",
            "policy_type": "descriptive_supporting_evidence",
            "source_review_item": "vertical_300s_vam_p90_mph",
            "consumption_rule": "may be referenced only as descriptive supporting evidence after route continuity, positive-delta artifact, and population gates pass",
            "allowed_downstream_use": "descriptive_supporting_evidence_only",
            "disallowed_downstream_use": "standalone_radar_axis_or_ability_ranking",
        },
        {
            "policy_item": "hr_at_representative_300s_windows",
            "policy_type": "supporting_context_only",
            "source_review_item": "hr_at_representative_300s_windows",
            "consumption_rule": "may be referenced only as load context for already-gated horizontal or vertical evidence",
            "allowed_downstream_use": "load_context_only",
            "disallowed_downstream_use": "medical_diagnosis_or_standalone_ability_axis",
        },
    ]

    for p in policy_items:
        source = decision(p["source_review_item"])
        rows.append({
            **p,
            "source_admission_status": source.get("admission_status", ""),
            "source_allowed_use": source.get("allowed_use", ""),
            "source_disallowed_use": source.get("disallowed_use", ""),
            "policy_status": "ACTIVE",
            "interpretation_boundary": BOUNDARY,
        })

    return pd.DataFrame(rows)


def build_window_review(windows: pd.DataFrame, coverage: pd.DataFrame) -> pd.DataFrame:
    population = coverage[["activity_id_short", "study_population_status"]].copy()
    w = windows.merge(population, on="activity_id_short", how="left")

    is_baseline = w["study_population_status"].astype(str).eq("RADAR_BASELINE_ACTIVITY")

    route_ok = truthy_series(w, "route_continuity_valid")
    h_status_col = first_existing(w, ["horizontal_window_status", "horizontal_300s_window_status"])
    v_status_col = first_existing(w, ["vertical_window_status", "vertical_300s_window_status"])

    if not route_ok.any() and h_status_col is not None:
        route_ok = ~w[h_status_col].astype(str).str.contains("ROUTE_CONTINUITY", na=False)
    if not route_ok.any() and "route_dist_delta_m" in w.columns:
        route_ok = pd.to_numeric(w["route_dist_delta_m"], errors="coerce").gt(0)

    positive_artifact = truthy_series(w, "positive_delta_artifact_suspect")
    if not positive_artifact.any():
        positive_artifact = truthy_series(w, "elevation_artifact_flag")

    h_consumable = is_baseline & route_ok & status_eq(w, h_status_col, "VALID_HORIZONTAL_WINDOW")
    v_consumable = is_baseline & route_ok & status_eq(w, v_status_col, "VALID_VERTICAL_WINDOW") & (~positive_artifact)

    hr_status_col = first_existing(w, ["hr_window_status", "hr_status"])
    hr_valid = status_eq(w, hr_status_col, "VALID_HR_WINDOW")
    hr_context = is_baseline & hr_valid & (h_consumable | v_consumable)

    status = np.select(
        [
            ~is_baseline,
            h_consumable & v_consumable,
            h_consumable,
            v_consumable,
            is_baseline & route_ok & positive_artifact,
            is_baseline & route_ok,
            is_baseline & (~route_ok),
        ],
        [
            "BLOCKED_EXTRA_SOURCE_ACTIVITY_REVIEW_ONLY",
            "CONSUMABLE_DESCRIPTIVE_HORIZONTAL_AND_VERTICAL_EVIDENCE",
            "CONSUMABLE_DESCRIPTIVE_HORIZONTAL_EVIDENCE_ONLY",
            "CONSUMABLE_DESCRIPTIVE_VERTICAL_EVIDENCE_ONLY",
            "BLOCKED_VERTICAL_ARTIFACT_GUARD_REVIEW_ONLY",
            "RETAIN_NONCONSUMABLE_DESCRIPTIVE_CONTEXT",
            "BLOCKED_ROUTE_CONTINUITY_GATE",
        ],
        default="REVIEW_REQUIRED_UNCLASSIFIED",
    )

    rename_map: dict[str, str] = {}
    if h_status_col == "horizontal_300s_window_status":
        rename_map[h_status_col] = "horizontal_window_status"
    if v_status_col == "vertical_300s_window_status":
        rename_map[v_status_col] = "vertical_window_status"
    if "vertical_gain_300s_calibrated_m" in w.columns:
        rename_map["vertical_gain_300s_calibrated_m"] = "vertical_300s_gain_calibrated_m"
    w = w.rename(columns=rename_map)

    keep_candidates = [
        "activity_id_short",
        "study_population_status",
        "window_start_elapsed_sec",
        "window_end_elapsed_sec",
        "duration_sec",
        "route_dist_delta_m",
        "route_continuity_valid",
        "positive_delta_artifact_suspect",
        "horizontal_window_status",
        "horizontal_300s_route_speed_mps",
        "vertical_window_status",
        "vertical_300s_gain_calibrated_m",
        "vertical_300s_vam_mph",
        "hr_window_status",
        "hr_valid_ratio",
        "hr_p90_bpm",
        "hr_p90_pct_sex_age_est_hrmax",
    ]
    keep = [c for c in keep_candidates if c in w.columns]

    out = w[keep].copy()
    out.insert(2, "population_gate_pass", is_baseline.values)
    out.insert(3, "route_continuity_gate_pass", route_ok.values)
    out.insert(4, "positive_delta_artifact_guard_pass", (~positive_artifact).values)
    out.insert(5, "horizontal_descriptive_consumption_allowed", h_consumable.values)
    out.insert(6, "vertical_descriptive_consumption_allowed", v_consumable.values)
    out.insert(7, "hr_context_consumption_allowed", hr_context.values)
    out.insert(8, "consumption_status", status)
    out["interpretation_boundary"] = BOUNDARY
    return out


def build_activity_summary(window_review: pd.DataFrame, coverage: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for _, c in coverage.iterrows():
        aid = str(c.get("activity_id_short", ""))
        w = window_review[window_review["activity_id_short"].astype(str).eq(aid)]

        h_n = int(w["horizontal_descriptive_consumption_allowed"].sum()) if not w.empty else 0
        v_n = int(w["vertical_descriptive_consumption_allowed"].sum()) if not w.empty else 0
        hr_n = int(w["hr_context_consumption_allowed"].sum()) if not w.empty else 0
        route_block_n = int(w["consumption_status"].astype(str).eq("BLOCKED_ROUTE_CONTINUITY_GATE").sum()) if not w.empty else 0
        artifact_block_n = int(w["consumption_status"].astype(str).eq("BLOCKED_VERTICAL_ARTIFACT_GUARD_REVIEW_ONLY").sum()) if not w.empty else 0

        if str(c.get("study_population_status", "")) != "RADAR_BASELINE_ACTIVITY":
            activity_status = "EXTRA_SOURCE_ACTIVITY_REVIEW_ONLY_NOT_CONSUMABLE"
        elif h_n > 0 or v_n > 0:
            activity_status = "CONSUMABLE_DESCRIPTIVE_300S_EVIDENCE_AVAILABLE"
        else:
            activity_status = "NO_CONSUMABLE_300S_MOVEMENT_EVIDENCE"

        rows.append({
            "activity_id_short": aid,
            "study_population_status": c.get("study_population_status", ""),
            "activity_consumption_status": activity_status,
            "horizontal_consumable_window_count": h_n,
            "vertical_consumable_window_count": v_n,
            "hr_context_consumable_window_count": hr_n,
            "route_continuity_blocked_window_count": route_block_n,
            "positive_delta_artifact_blocked_window_count": artifact_block_n,
            "source_horizontal_300s_valid_window_count": c.get("horizontal_300s_valid_window_count", np.nan),
            "source_vertical_300s_valid_window_count": c.get("vertical_300s_valid_window_count", np.nan),
            "source_horizontal_300s_route_speed_p90_mps": c.get("horizontal_300s_route_speed_p90_mps", np.nan),
            "source_vertical_300s_gain_p90_m": c.get("vertical_300s_gain_p90_m", np.nan),
            "source_vertical_300s_vam_p90_mph": c.get("vertical_300s_vam_p90_mph", np.nan),
            "allowed_downstream_use": "descriptive_supporting_evidence_only" if h_n > 0 or v_n > 0 else "not_consumed",
            "disallowed_downstream_use": "standalone_radar_axis_score_rank_or_class",
            "interpretation_boundary": BOUNDARY,
        })

    return pd.DataFrame(rows)


def build_audit(
    admission_audit: pd.DataFrame,
    policy: pd.DataFrame,
    activity_summary: pd.DataFrame,
    window_review: pd.DataFrame,
) -> pd.DataFrame:
    # Policy prose intentionally names disallowed uses; only structural field names are scanned.
    output_columns = list(activity_summary.columns) + list(window_review.columns)
    forbidden = [c for c in output_columns if any(p in c.lower() for p in FORBIDDEN_OUTPUT_PATTERNS)]

    baseline = activity_summary[
        activity_summary["study_population_status"].astype(str).eq("RADAR_BASELINE_ACTIVITY")
    ]
    extra = activity_summary[
        activity_summary["study_population_status"].astype(str).ne("RADAR_BASELINE_ACTIVITY")
    ]

    admitted_qa = set(policy.loc[policy["policy_type"].astype(str).str.contains("gate|guard", case=False, na=False), "policy_item"].astype(str))

    review_reasons: list[str] = []
    if admission_audit.empty:
        review_reasons.append("MISSING_ADMISSION_AUDIT")
    if not admission_audit.empty and not str(admission_audit.iloc[0].get("audit_conclusion", "")).startswith("PASS_"):
        review_reasons.append("ADMISSION_AUDIT_NOT_PASS")
    if "route_continuity_300s_gate" not in admitted_qa:
        review_reasons.append("MISSING_ROUTE_CONTINUITY_POLICY")
    if "positive_delta_artifact_guard" not in admitted_qa:
        review_reasons.append("MISSING_POSITIVE_DELTA_ARTIFACT_POLICY")
    if forbidden:
        review_reasons.append("FORBIDDEN_FIELD_PRESENT")

    row = {
        "admission_audit_conclusion": admission_audit.iloc[0].get("audit_conclusion", "") if not admission_audit.empty else "",
        "baseline_activity_count": int(len(baseline)),
        "extra_source_activity_count": int(len(extra)),
        "extra_source_activities": "|".join(extra["activity_id_short"].astype(str)) if len(extra) else "NONE",
        "policy_row_count": int(len(policy)),
        "window_review_row_count": int(len(window_review)),
        "horizontal_consumable_window_count": int(window_review["horizontal_descriptive_consumption_allowed"].sum()) if not window_review.empty else 0,
        "vertical_consumable_window_count": int(window_review["vertical_descriptive_consumption_allowed"].sum()) if not window_review.empty else 0,
        "hr_context_consumable_window_count": int(window_review["hr_context_consumption_allowed"].sum()) if not window_review.empty else 0,
        "activities_with_consumable_horizontal_count": int((baseline["horizontal_consumable_window_count"] > 0).sum()) if not baseline.empty else 0,
        "activities_with_consumable_vertical_count": int((baseline["vertical_consumable_window_count"] > 0).sum()) if not baseline.empty else 0,
        "route_continuity_gate_policy_active": "route_continuity_300s_gate" in admitted_qa,
        "positive_delta_artifact_guard_policy_active": "positive_delta_artifact_guard" in admitted_qa,
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


def write_html(out_path: Path, audit: pd.DataFrame, policy: pd.DataFrame, activity: pd.DataFrame) -> None:
    def table(df: pd.DataFrame, cols: list[str], n: int = 60) -> str:
        if df.empty:
            return "<p>No rows.</p>"
        use = [c for c in cols if c in df.columns]
        return df[use].head(n).to_html(index=False, escape=True, classes="data")

    conclusion = audit.iloc[0]["audit_conclusion"] if not audit.empty else REVIEW
    body = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CH6.5.5 300s Movement QA Gate Consumption v1</title>
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
<h1>CH6.5.5 300s Movement QA Gate Consumption v1</h1>
<p class="status">{html.escape(str(conclusion))}</p>
<p class="boundary">{html.escape(BOUNDARY)}</p>

<h2>Audit</h2>
{table(audit, list(audit.columns), 5)}

<h2>Consumption Policy</h2>
{table(policy, ["policy_item", "policy_type", "source_admission_status", "consumption_rule", "allowed_downstream_use", "disallowed_downstream_use", "policy_status"], 20)}

<h2>Activity Consumption Summary</h2>
{table(activity, ["activity_id_short", "study_population_status", "activity_consumption_status", "horizontal_consumable_window_count", "vertical_consumable_window_count", "hr_context_consumable_window_count", "route_continuity_blocked_window_count", "positive_delta_artifact_blocked_window_count", "allowed_downstream_use", "disallowed_downstream_use"], 60)}
</body>
</html>
"""
    out_path.write_text(body, encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    study_root = resolve(root, args.study_root)
    admission_root = resolve(root, args.admission_root)
    out_root = resolve(root, args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)

    windows = read_csv(study_root / "movement_300s_window_candidates_v1_1.csv", "movement 300s window candidates v1.1")
    admission_axis = read_csv(admission_root / "movement_300s_admission_axis_decision_v1.csv", "admission axis decision v1")
    admission_coverage = read_csv(admission_root / "movement_300s_admission_activity_coverage_v1.csv", "admission activity coverage v1")
    admission_audit = read_csv(admission_root / "movement_300s_admission_audit_v1.csv", "admission audit v1")

    policy = build_policy(admission_axis)
    window_review = build_window_review(windows, admission_coverage)
    activity_summary = build_activity_summary(window_review, admission_coverage)
    audit = build_audit(admission_audit, policy, activity_summary, window_review)

    outputs = {
        "policy": out_root / "movement_300s_consumption_gate_policy_v1.csv",
        "activity_summary": out_root / "movement_300s_consumption_activity_summary_v1.csv",
        "window_review": out_root / "movement_300s_consumption_window_review_v1.csv",
        "audit": out_root / "movement_300s_consumption_audit_v1.csv",
        "html": out_root / "movement_300s_consumption_report_v1.html",
    }

    policy.to_csv(outputs["policy"], index=False, encoding="utf-8-sig")
    activity_summary.to_csv(outputs["activity_summary"], index=False, encoding="utf-8-sig")
    window_review.to_csv(outputs["window_review"], index=False, encoding="utf-8-sig")
    audit.to_csv(outputs["audit"], index=False, encoding="utf-8-sig")
    write_html(outputs["html"], audit, policy, activity_summary)

    print({
        "output_root": str(out_root),
        "baseline_activity_count": int(audit.iloc[0]["baseline_activity_count"]),
        "extra_source_activities": str(audit.iloc[0]["extra_source_activities"]),
        "horizontal_consumable_window_count": int(audit.iloc[0]["horizontal_consumable_window_count"]),
        "vertical_consumable_window_count": int(audit.iloc[0]["vertical_consumable_window_count"]),
        "hr_context_consumable_window_count": int(audit.iloc[0]["hr_context_consumable_window_count"]),
        "route_continuity_gate_policy_active": bool(audit.iloc[0]["route_continuity_gate_policy_active"]),
        "positive_delta_artifact_guard_policy_active": bool(audit.iloc[0]["positive_delta_artifact_guard_policy_active"]),
        "audit_conclusion": str(audit.iloc[0]["audit_conclusion"]),
        "outputs": {k: str(v) for k, v in outputs.items()},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
