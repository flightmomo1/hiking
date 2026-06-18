#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split CH6.5.5 v0.2 outputs into clearer v0.3 context tables.

Consumes:
  outputs/report_figures/ch6_5_5_personal_profile_metadata_join_v0_2/
    personal_profile_metadata_join_v0_2.csv

Produces:
  - full context table with v0.3 split labels
  - true route-load strain candidate table
  - HR output context table
  - HRmax estimate/sensor review table
  - split summaries and audit

Boundary:
This is descriptive context evidence only. It does not produce ability scores,
ability ranks, ability classes, final hiking risk scores, route suitability
scores, go/no-go decisions, medical diagnoses, or causality evidence.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd


DEFAULT_INPUT = (
    "outputs/report_figures/ch6_5_5_personal_profile_metadata_join_v0_2/"
    "personal_profile_metadata_join_v0_2.csv"
)
DEFAULT_OUT = "outputs/report_figures/ch6_5_5_personal_profile_metadata_split_v0_3"

BOUNDARY = (
    "Descriptive CH6.5.5 v0.3 personal profile split context evidence only. "
    "High HR can be controlled output and is not strain by itself. Route-load strain "
    "candidate tables are separated from HR output context tables. Sex-age HRmax is "
    "estimated, not measured. This is not an ability score, ability rank, ability class, "
    "final hiking risk score, route suitability score, go/no-go decision, medical diagnosis, "
    "or causality evidence."
)

STRAIN_LABELS = {
    "HIGH_CONFIDENCE_ROUTE_LOAD_STRAIN_CANDIDATE_WITH_PROFILE_SUPPORT",
    "BEHAVIOR_ROUTE_LOAD_STRAIN_CANDIDATE",
    "MODERATE_ROUTE_LOAD_STRAIN_CANDIDATE_WITH_PROFILE_SUPPORT",
    "HR_BEHAVIOR_MISMATCH_REVIEW_CANDIDATE",
}

CONTROLLED_HR_LABEL = "HIGH_HR_OUTPUT_CONTROLLED_CONTEXT_NOT_STRAIN_BY_ITSELF"
HRMAX_REVIEW_CONTEXT = "HRMAX_ESTIMATE_OR_SENSOR_REVIEW_CONTEXT"


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


def split_category(row) -> str:
    route_label = str(row.get("route_load_strain_context_label", "")).strip()
    hr_eff = str(row.get("hr_output_efficiency_context", "")).strip()
    zone = str(row.get("hr_median_zone_sex_age_est", "")).strip()

    if route_label in STRAIN_LABELS:
        return "ROUTE_LOAD_STRAIN_CANDIDATE"
    if hr_eff == "HRMAX_ESTIMATE_OR_SENSOR_REVIEW_REQUIRED" or zone == "HR_ESTIMATE_EXCEEDS_100_REVIEW":
        return "HRMAX_ESTIMATE_OR_SENSOR_REVIEW_CONTEXT"
    if route_label == CONTROLLED_HR_LABEL or hr_eff == "HIGH_HR_ZONE_EFFICIENT_OR_CONTROLLED_OUTPUT_CONTEXT":
        return "HIGH_HR_CONTROLLED_OUTPUT_CONTEXT"
    if "HIGH_HR_ZONE_WITH_BEHAVIOR_DEGRADATION" in hr_eff:
        return "HR_BEHAVIOR_REVIEW_CONTEXT"
    return "REFERENCE_OR_LIMITED_ATTENTION_CONTEXT"


def strain_priority(row) -> int:
    label = str(row.get("route_load_strain_context_label", "")).strip()
    if label == "HIGH_CONFIDENCE_ROUTE_LOAD_STRAIN_CANDIDATE_WITH_PROFILE_SUPPORT":
        return 1
    if label == "BEHAVIOR_ROUTE_LOAD_STRAIN_CANDIDATE":
        return 2
    if label == "MODERATE_ROUTE_LOAD_STRAIN_CANDIDATE_WITH_PROFILE_SUPPORT":
        return 3
    if label == "HR_BEHAVIOR_MISMATCH_REVIEW_CANDIDATE":
        return 4
    return 99


def hr_context_priority(row) -> int:
    zone = str(row.get("hr_median_zone_sex_age_est", ""))
    hr_eff = str(row.get("hr_output_efficiency_context", ""))
    if zone == "HR_ESTIMATE_EXCEEDS_100_REVIEW" or hr_eff == "HRMAX_ESTIMATE_OR_SENSOR_REVIEW_REQUIRED":
        return 1
    if "HIGH_HR_ZONE_WITH_BEHAVIOR_DEGRADATION" in hr_eff:
        return 2
    if "HIGH_HR_ZONE_EFFICIENT" in hr_eff or "HIGH_HR_OUTPUT_CONTROLLED" in str(row.get("route_load_strain_context_label", "")):
        return 3
    if zone.startswith("ZONE5"):
        return 4
    if zone.startswith("ZONE4"):
        return 5
    return 9


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    src_path = resolve(root, args.input)
    out_root = resolve(root, args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)

    df = read_csv(src_path)
    required = ["activity_id_short", "route_load_strain_context_label", "hr_output_efficiency_context", "hr_median_zone_sex_age_est"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns from v0.2 joined file: {missing}")

    df["ch6_5_5_v0_3_split_category"] = df.apply(split_category, axis=1)
    df["ch6_5_5_v0_3_boundary"] = BOUNDARY

    # Full v0.3 context.
    full = df.copy()

    # True route-load strain candidates only.
    strain = df[df["route_load_strain_context_label"].isin(STRAIN_LABELS)].copy()
    if not strain.empty:
        strain["strain_priority"] = strain.apply(strain_priority, axis=1)
        strain = strain.sort_values(
            by=["strain_priority", "activity_id_short"],
            ascending=[True, True],
            kind="mergesort",
        )

    # HR output context is separate and includes controlled-output cases and HR-behavior review.
    hr_context_mask = (
        df["ch6_5_5_v0_3_split_category"].isin([
            "HIGH_HR_CONTROLLED_OUTPUT_CONTEXT",
            "HR_BEHAVIOR_REVIEW_CONTEXT",
            "HRMAX_ESTIMATE_OR_SENSOR_REVIEW_CONTEXT",
        ])
        | df["hr_median_zone_sex_age_est"].astype(str).str.startswith("ZONE4", na=False)
        | df["hr_median_zone_sex_age_est"].astype(str).str.startswith("ZONE5", na=False)
        | df["hr_median_zone_sex_age_est"].astype(str).eq("HR_ESTIMATE_EXCEEDS_100_REVIEW")
    )
    hr_context = df[hr_context_mask].copy()
    if not hr_context.empty:
        hr_context["hr_context_priority"] = hr_context.apply(hr_context_priority, axis=1)
        hr_context = hr_context.sort_values(
            by=["hr_context_priority", "activity_id_short"],
            ascending=[True, True],
            kind="mergesort",
        )

    hrmax_review = df[
        (df["hr_median_zone_sex_age_est"].astype(str) == "HR_ESTIMATE_EXCEEDS_100_REVIEW")
        | (df["hr_output_efficiency_context"].astype(str) == "HRMAX_ESTIMATE_OR_SENSOR_REVIEW_REQUIRED")
    ].copy()

    summary = full.groupby("ch6_5_5_v0_3_split_category", dropna=False).agg(
        activity_count=("activity_id_short", "count"),
        activity_id_short_list=("activity_id_short", lambda s: "|".join(sorted(map(str, s)))),
    ).reset_index()
    summary["interpretation_boundary"] = BOUNDARY

    strain_summary = strain.groupby("route_load_strain_context_label", dropna=False).agg(
        activity_count=("activity_id_short", "count"),
        activity_id_short_list=("activity_id_short", lambda s: "|".join(sorted(map(str, s)))),
    ).reset_index() if not strain.empty else pd.DataFrame(columns=["route_load_strain_context_label", "activity_count", "activity_id_short_list"])
    strain_summary["interpretation_boundary"] = BOUNDARY

    hr_summary = hr_context.groupby(["hr_median_zone_sex_age_est", "hr_output_efficiency_context"], dropna=False).agg(
        activity_count=("activity_id_short", "count"),
        activity_id_short_list=("activity_id_short", lambda s: "|".join(sorted(map(str, s)))),
    ).reset_index() if not hr_context.empty else pd.DataFrame(columns=["hr_median_zone_sex_age_est", "hr_output_efficiency_context", "activity_count", "activity_id_short_list"])
    hr_summary["interpretation_boundary"] = BOUNDARY

    controlled_count = int((full["route_load_strain_context_label"].astype(str) == CONTROLLED_HR_LABEL).sum())
    candidate_count_v02 = int(full["route_load_strain_context_label"].astype(str).isin(
        list(STRAIN_LABELS) + [CONTROLLED_HR_LABEL]
    ).sum())
    audit = pd.DataFrame([{
        "source_path": str(src_path),
        "activity_count": int(len(full)),
        "v0_2_candidate_like_rows_including_controlled_hr": candidate_count_v02,
        "v0_3_true_strain_candidate_rows": int(len(strain)),
        "v0_3_hr_output_context_rows": int(len(hr_context)),
        "v0_3_hrmax_review_rows": int(len(hrmax_review)),
        "high_hr_controlled_context_rows_removed_from_strain_candidate": controlled_count,
        "split_category_count": int(full["ch6_5_5_v0_3_split_category"].nunique()),
        "audit_conclusion": "PASS_CH6_5_5_PROFILE_METADATA_SPLIT_V0_3_DESCRIPTIVE_ONLY",
        "interpretation_boundary": BOUNDARY,
    }])

    outputs = {
        "full_context": out_root / "personal_profile_metadata_split_full_context_v0_3.csv",
        "strain_candidate": out_root / "personal_route_load_strain_candidate_v0_3.csv",
        "hr_output_context": out_root / "personal_hr_output_context_v0_3.csv",
        "hrmax_review": out_root / "personal_hrmax_estimate_sensor_review_v0_3.csv",
        "split_summary": out_root / "personal_profile_metadata_split_summary_v0_3.csv",
        "strain_summary": out_root / "personal_route_load_strain_candidate_summary_v0_3.csv",
        "hr_output_summary": out_root / "personal_hr_output_context_summary_v0_3.csv",
        "audit": out_root / "personal_profile_metadata_split_audit_v0_3.csv",
    }

    full.to_csv(outputs["full_context"], index=False, encoding="utf-8-sig")
    strain.to_csv(outputs["strain_candidate"], index=False, encoding="utf-8-sig")
    hr_context.to_csv(outputs["hr_output_context"], index=False, encoding="utf-8-sig")
    hrmax_review.to_csv(outputs["hrmax_review"], index=False, encoding="utf-8-sig")
    summary.to_csv(outputs["split_summary"], index=False, encoding="utf-8-sig")
    strain_summary.to_csv(outputs["strain_summary"], index=False, encoding="utf-8-sig")
    hr_summary.to_csv(outputs["hr_output_summary"], index=False, encoding="utf-8-sig")
    audit.to_csv(outputs["audit"], index=False, encoding="utf-8-sig")

    print({
        "output_root": str(out_root),
        "activity_count": int(len(full)),
        "v0_3_true_strain_candidate_rows": int(len(strain)),
        "v0_3_hr_output_context_rows": int(len(hr_context)),
        "v0_3_hrmax_review_rows": int(len(hrmax_review)),
        "high_hr_controlled_context_rows_removed_from_strain_candidate": controlled_count,
        "audit_conclusion": "PASS_CH6_5_5_PROFILE_METADATA_SPLIT_V0_3_DESCRIPTIVE_ONLY",
        "outputs": {k: str(v) for k, v in outputs.items()},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
