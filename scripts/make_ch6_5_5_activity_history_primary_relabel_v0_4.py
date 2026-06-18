#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CH6.5.5 v0.4 activity-history-primary relabel.

Consumes v0.3 split full context and relabels the evidence hierarchy:

Primary evidence:
- actual hiking activity history, such as CH6.5.4 route-load match review level
  and behavior degradation flags

Secondary evidence:
- HR zone / HR output context

Tertiary evidence:
- non-standard estimated VO2max
- subjective Qixing difficulty rating

Important boundary:
- Estimated VO2max and subjective difficulty never promote an activity into
  route-load strain candidate by themselves.
- High HR alone is not strain.
- This layer is descriptive evidence only.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd


DEFAULT_INPUT = (
    "outputs/report_figures/ch6_5_5_personal_profile_metadata_split_v0_3/"
    "personal_profile_metadata_split_full_context_v0_3.csv"
)
DEFAULT_OUT = "outputs/report_figures/ch6_5_5_activity_history_primary_relabel_v0_4"

BOUNDARY = (
    "Descriptive CH6.5.5 v0.4 activity-history-primary context evidence only. "
    "Actual hiking activity history is treated as primary evidence. HR zone is secondary "
    "context. Non-standard estimated VO2max and subjective Qixing difficulty are tertiary "
    "supporting context only and never promote an activity into strain candidate by themselves. "
    "High HR alone is not strain. This is not an ability score, ability rank, ability class, "
    "final hiking risk score, route suitability score, go/no-go decision, medical diagnosis, "
    "or causality evidence."
)

PRIMARY_STRAIN_LABELS = {
    "ACTIVITY_HISTORY_MULTI_FACTOR_STRAIN_CANDIDATE",
    "ACTIVITY_HISTORY_MODERATE_STRAIN_CANDIDATE",
}

SINGLE_FACTOR_REVIEW_LABELS = {
    "ACTIVITY_HISTORY_SINGLE_FACTOR_BEHAVIOR_REVIEW_NEEDS_NUMERIC_CHECK",
    "ACTIVITY_HISTORY_SINGLE_FACTOR_HR_BEHAVIOR_REVIEW_NEEDS_NUMERIC_CHECK",
}


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=r"D:\mountain_work\115_osm")
    p.add_argument("--input", default=DEFAULT_INPUT)
    p.add_argument("--output-root", default=DEFAULT_OUT)
    return p.parse_args()


def resolve(root: Path, value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else root / p


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def pipe_list(values) -> str:
    vals = sorted(set(str(v) for v in values if str(v).strip() and str(v).lower() != "nan"))
    return "|".join(vals) if vals else "NONE"


def strval(row, col: str) -> str:
    v = row.get(col, "")
    if pd.isna(v):
        return ""
    return str(v).strip()


def behavior_flag_count(row) -> int:
    flags = strval(row, "personal_route_load_match_review_flags")
    tokens = [
        "RELATIVE_SLOWER_SPEED_MATCH_REVIEW",
        "RELATIVE_HIGH_LOW_SPEED_RATIO_MATCH_REVIEW",
        "RELATIVE_HIGH_STOPPED_RATIO_MATCH_REVIEW",
        "RELATIVE_HIGH_ROUTE_LOAD_BEHAVIOR_RESPONSE_MATCH_REVIEW",
        "RELATIVE_HIGH_BEHAVIOR_WEATHER_OVERLAP_MATCH_REVIEW",
    ]
    return sum(1 for t in tokens if t in flags)


def hr_flag_present(row) -> bool:
    flags = strval(row, "personal_route_load_match_review_flags")
    hr_eff = strval(row, "hr_output_efficiency_context")
    return ("RELATIVE_HIGH_HR_CONTEXT_MATCH_REVIEW" in flags) or ("HIGH_HR_ZONE" in hr_eff) or ("HRMAX_ESTIMATE" in hr_eff)


def is_multifactor(row) -> bool:
    return "MULTI_FACTOR" in strval(row, "personal_route_load_match_review_level")


def is_moderate(row) -> bool:
    return "MODERATE" in strval(row, "personal_route_load_match_review_level")


def is_single_factor(row) -> bool:
    return "SINGLE_FACTOR" in strval(row, "personal_route_load_match_review_level")


def activity_history_label(row) -> str:
    hr_zone = strval(row, "hr_median_zone_sex_age_est")
    hr_eff = strval(row, "hr_output_efficiency_context")
    bcount = behavior_flag_count(row)

    if hr_zone == "HR_ESTIMATE_EXCEEDS_100_REVIEW" or hr_eff == "HRMAX_ESTIMATE_OR_SENSOR_REVIEW_REQUIRED":
        return "HRMAX_ESTIMATE_OR_SENSOR_REVIEW_CONTEXT"

    if is_multifactor(row):
        return "ACTIVITY_HISTORY_MULTI_FACTOR_STRAIN_CANDIDATE"

    if is_moderate(row):
        return "ACTIVITY_HISTORY_MODERATE_STRAIN_CANDIDATE"

    if is_single_factor(row) and bcount > 0:
        if hr_flag_present(row):
            return "ACTIVITY_HISTORY_SINGLE_FACTOR_HR_BEHAVIOR_REVIEW_NEEDS_NUMERIC_CHECK"
        return "ACTIVITY_HISTORY_SINGLE_FACTOR_BEHAVIOR_REVIEW_NEEDS_NUMERIC_CHECK"

    if "HIGH_HR_ZONE_EFFICIENT_OR_CONTROLLED_OUTPUT_CONTEXT" in hr_eff:
        return "HIGH_HR_CONTROLLED_OUTPUT_CONTEXT_NOT_STRAIN"

    return "REFERENCE_OR_LIMITED_ACTIVITY_HISTORY_CONTEXT"


def evidence_tier(label: str) -> str:
    if label in PRIMARY_STRAIN_LABELS:
        return "PRIMARY_ACTIVITY_HISTORY_CANDIDATE"
    if label in SINGLE_FACTOR_REVIEW_LABELS:
        return "PRIMARY_ACTIVITY_HISTORY_REVIEW_NEEDS_NUMERIC_CHECK"
    if label == "HRMAX_ESTIMATE_OR_SENSOR_REVIEW_CONTEXT":
        return "SECONDARY_HRMAX_ESTIMATE_OR_SENSOR_REVIEW"
    if label == "HIGH_HR_CONTROLLED_OUTPUT_CONTEXT_NOT_STRAIN":
        return "SECONDARY_HR_OUTPUT_CONTEXT_NOT_STRAIN"
    return "REFERENCE_OR_LIMITED_ATTENTION_CONTEXT"


def tertiary_profile_signal(row) -> str:
    vo2 = strval(row, "vo2max_context_tier")
    diff = strval(row, "qixing_self_report_difficulty_tier")
    sig = []
    if vo2 == "LOWER_VO2MAX_CONTEXT":
        sig.append("LOWER_ESTIMATED_VO2MAX_CONTEXT")
    elif vo2 == "HIGHER_VO2MAX_CONTEXT":
        sig.append("HIGHER_ESTIMATED_VO2MAX_CONTEXT")
    if diff == "SELF_REPORTED_HIGH_DIFFICULTY":
        sig.append("SELF_REPORTED_HIGH_DIFFICULTY_CONTEXT")
    elif diff == "SELF_REPORTED_LOW_DIFFICULTY":
        sig.append("SELF_REPORTED_LOW_DIFFICULTY_CONTEXT")
    return "|".join(sig) if sig else "PROFILE_CONTEXT_REFERENCE_OR_MISSING"


def profile_consistency(row) -> str:
    label = strval(row, "activity_history_primary_label")
    sig = strval(row, "tertiary_profile_context_signal")

    strain_like = label in PRIMARY_STRAIN_LABELS or label in SINGLE_FACTOR_REVIEW_LABELS
    supportive = ("LOWER_ESTIMATED_VO2MAX_CONTEXT" in sig) or ("SELF_REPORTED_HIGH_DIFFICULTY_CONTEXT" in sig)
    contrary = ("HIGHER_ESTIMATED_VO2MAX_CONTEXT" in sig) or ("SELF_REPORTED_LOW_DIFFICULTY_CONTEXT" in sig)

    if not strain_like:
        if supportive:
            return "PROFILE_CONTEXT_ONLY_NOT_ACTIVITY_STRAIN"
        return "PROFILE_CONTEXT_NOT_USED_FOR_PROMOTION"
    if supportive and not contrary:
        return "PROFILE_CONTEXT_CONSISTENT_BUT_TERTIARY_ONLY"
    if contrary and not supportive:
        return "PROFILE_CONTEXT_MIXED_OR_NOT_SUPPORTIVE"
    if supportive and contrary:
        return "PROFILE_CONTEXT_MIXED"
    return "PROFILE_CONTEXT_REFERENCE_OR_MISSING"


def review_priority(row) -> int:
    label = strval(row, "activity_history_primary_label")
    if label == "ACTIVITY_HISTORY_MULTI_FACTOR_STRAIN_CANDIDATE":
        return 1
    if label == "ACTIVITY_HISTORY_MODERATE_STRAIN_CANDIDATE":
        return 2
    if label in SINGLE_FACTOR_REVIEW_LABELS:
        return 3
    if label == "HRMAX_ESTIMATE_OR_SENSOR_REVIEW_CONTEXT":
        return 4
    if label == "HIGH_HR_CONTROLLED_OUTPUT_CONTEXT_NOT_STRAIN":
        return 5
    return 9


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    src_path = resolve(root, args.input)
    out_root = resolve(root, args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)

    df = read_csv(src_path)
    required = [
        "activity_id_short",
        "personal_route_load_match_review_level",
        "personal_route_load_match_review_flags",
        "hr_output_efficiency_context",
        "hr_median_zone_sex_age_est",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"Missing required v0.3 columns: {missing}")

    df["activity_history_primary_label"] = df.apply(activity_history_label, axis=1)
    df["activity_history_evidence_tier"] = df["activity_history_primary_label"].apply(evidence_tier)
    df["activity_history_behavior_flag_count"] = df.apply(behavior_flag_count, axis=1)
    df["hr_context_role"] = "SECONDARY_CONTEXT_ONLY"
    df["profile_context_role"] = "TERTIARY_SUPPORTING_CONTEXT_ONLY_NOT_FOR_PROMOTION"
    df["tertiary_profile_context_signal"] = df.apply(tertiary_profile_signal, axis=1)
    df["profile_context_consistency_with_activity_history"] = df.apply(profile_consistency, axis=1)
    df["review_priority"] = df.apply(review_priority, axis=1)
    df["interpretation_boundary_v0_4"] = BOUNDARY

    primary_candidates = df[df["activity_history_primary_label"].isin(PRIMARY_STRAIN_LABELS)].copy()
    single_factor_review = df[df["activity_history_primary_label"].isin(SINGLE_FACTOR_REVIEW_LABELS)].copy()
    hr_context = df[
        df["activity_history_primary_label"].isin([
            "HRMAX_ESTIMATE_OR_SENSOR_REVIEW_CONTEXT",
            "HIGH_HR_CONTROLLED_OUTPUT_CONTEXT_NOT_STRAIN",
        ])
        | df["hr_median_zone_sex_age_est"].astype(str).str.startswith("ZONE4", na=False)
        | df["hr_median_zone_sex_age_est"].astype(str).str.startswith("ZONE5", na=False)
        | df["hr_median_zone_sex_age_est"].astype(str).eq("HR_ESTIMATE_EXCEEDS_100_REVIEW")
    ].copy()

    profile_context_only = df[
        (~df["activity_history_primary_label"].isin(PRIMARY_STRAIN_LABELS | SINGLE_FACTOR_REVIEW_LABELS))
        & (
            df["tertiary_profile_context_signal"].astype(str).str.contains("LOWER_ESTIMATED_VO2MAX_CONTEXT|SELF_REPORTED_HIGH_DIFFICULTY_CONTEXT", na=False)
        )
    ].copy()

    for frame in [primary_candidates, single_factor_review, hr_context, profile_context_only]:
        if not frame.empty:
            frame.sort_values(["review_priority", "activity_id_short"], inplace=True, kind="mergesort")

    summary = df.groupby(["activity_history_primary_label", "activity_history_evidence_tier"], dropna=False).agg(
        activity_count=("activity_id_short", "count"),
        activity_id_short_list=("activity_id_short", lambda s: "|".join(sorted(map(str, s)))),
    ).reset_index()
    summary["interpretation_boundary"] = BOUNDARY

    profile_summary = df.groupby(["profile_context_consistency_with_activity_history", "tertiary_profile_context_signal"], dropna=False).agg(
        activity_count=("activity_id_short", "count"),
        activity_id_short_list=("activity_id_short", lambda s: "|".join(sorted(map(str, s)))),
    ).reset_index()
    profile_summary["interpretation_boundary"] = BOUNDARY

    audit = pd.DataFrame([{
        "source_path": str(src_path),
        "activity_count": int(len(df)),
        "primary_activity_history_candidate_rows": int(len(primary_candidates)),
        "single_factor_behavior_review_rows": int(len(single_factor_review)),
        "hr_context_rows": int(len(hr_context)),
        "profile_context_only_rows": int(len(profile_context_only)),
        "profile_promotion_used": False,
        "vo2max_role": "TERTIARY_SUPPORTING_CONTEXT_ONLY",
        "subjective_difficulty_role": "TERTIARY_SUPPORTING_CONTEXT_ONLY",
        "audit_conclusion": "PASS_CH6_5_5_ACTIVITY_HISTORY_PRIMARY_RELABEL_V0_4_DESCRIPTIVE_ONLY",
        "interpretation_boundary": BOUNDARY,
    }])

    outputs = {
        "full": out_root / "personal_activity_history_primary_full_context_v0_4.csv",
        "primary_candidate": out_root / "personal_activity_history_primary_strain_candidate_v0_4.csv",
        "single_factor_review": out_root / "personal_activity_history_single_factor_behavior_review_v0_4.csv",
        "hr_context": out_root / "personal_activity_history_hr_output_context_v0_4.csv",
        "profile_context_only": out_root / "personal_profile_context_only_v0_4.csv",
        "summary": out_root / "personal_activity_history_primary_summary_v0_4.csv",
        "profile_summary": out_root / "personal_activity_history_profile_context_summary_v0_4.csv",
        "audit": out_root / "personal_activity_history_primary_audit_v0_4.csv",
    }

    df.to_csv(outputs["full"], index=False, encoding="utf-8-sig")
    primary_candidates.to_csv(outputs["primary_candidate"], index=False, encoding="utf-8-sig")
    single_factor_review.to_csv(outputs["single_factor_review"], index=False, encoding="utf-8-sig")
    hr_context.to_csv(outputs["hr_context"], index=False, encoding="utf-8-sig")
    profile_context_only.to_csv(outputs["profile_context_only"], index=False, encoding="utf-8-sig")
    summary.to_csv(outputs["summary"], index=False, encoding="utf-8-sig")
    profile_summary.to_csv(outputs["profile_summary"], index=False, encoding="utf-8-sig")
    audit.to_csv(outputs["audit"], index=False, encoding="utf-8-sig")

    print({
        "output_root": str(out_root),
        "activity_count": int(len(df)),
        "primary_activity_history_candidate_rows": int(len(primary_candidates)),
        "single_factor_behavior_review_rows": int(len(single_factor_review)),
        "hr_context_rows": int(len(hr_context)),
        "profile_context_only_rows": int(len(profile_context_only)),
        "profile_promotion_used": False,
        "audit_conclusion": "PASS_CH6_5_5_ACTIVITY_HISTORY_PRIMARY_RELABEL_V0_4_DESCRIPTIVE_ONLY",
        "outputs": {k: str(v) for k, v in outputs.items()},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
