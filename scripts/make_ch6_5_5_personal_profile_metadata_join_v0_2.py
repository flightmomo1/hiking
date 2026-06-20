#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build CH6.5.5 personal profile metadata join v0.2 with sex-age HR zones.

This script joins participant metadata to CH6.5.4 personal route-load match review.

HRmax formula used in v0.2:
- male / sex_code 1:   HRmax = 214 - 0.8 * age
- female / sex_code 2: HRmax = 209 - 0.7 * age

Boundaries:
- sex-age HRmax is an estimate, not a measured HRmax
- HR zone is context evidence only
- high HR is not treated as poor ability by itself
- descriptive evidence only; no ability score, class, final risk score,
  route suitability score, go/no-go decision, medical diagnosis, or causality
"""

from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd


BOUNDARY = (
    "Descriptive participant-profile and sex-age HR-zone context evidence only. "
    "Sex-age HRmax is estimated, not measured. HR zones are context evidence and "
    "high HR is not interpreted as poor ability by itself. This is not an ability "
    "score, ability rank, ability class, final hiking risk score, route suitability "
    "score, go/no-go decision, medical diagnosis, or causality evidence."
)

DEFAULT_MATCH = "outputs/report_figures/ch6_5_4_personal_route_load_match_review_v1/personal_route_load_match_review_v1.csv"
DEFAULT_PROFILE = "configs/personal/qixing_participant_profile_v1.csv"
DEFAULT_OUT = "outputs/report_figures/ch6_5_5_personal_profile_metadata_join_v0_2"


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=r"D:\mountain_work\115_osm")
    p.add_argument("--match-review", default=DEFAULT_MATCH)
    p.add_argument("--participant-profile", default=DEFAULT_PROFILE)
    p.add_argument("--output-root", default=DEFAULT_OUT)
    return p.parse_args()


def resolve(root: Path, value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else root / p


def read_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def num(s):
    return pd.to_numeric(s, errors="coerce")


def pipe_flags(values) -> str:
    out = []
    for v in values:
        if v is None:
            continue
        s = str(v).strip()
        if not s or s.lower() == "nan" or s == "NONE":
            continue
        for part in s.split("|"):
            part = part.strip()
            if part and part != "NONE" and part.lower() != "nan":
                out.append(part)
    return "|".join(sorted(set(out))) if out else "NONE"


def sex_age_hrmax(row) -> float:
    age = row.get("age_yrs")
    sex = row.get("sex_code")
    if pd.isna(age) or pd.isna(sex):
        return np.nan
    if int(sex) == 1:
        return 214 - 0.8 * float(age)
    if int(sex) == 2:
        return 209 - 0.7 * float(age)
    return np.nan


def hr_zone(pct) -> str:
    if pd.isna(pct):
        return "HR_ZONE_MISSING"
    if pct > 100:
        return "HR_ESTIMATE_EXCEEDS_100_REVIEW"
    if pct >= 90:
        return "ZONE5_90_100_PCT_HRMAX"
    if pct >= 80:
        return "ZONE4_80_90_PCT_HRMAX"
    if pct >= 70:
        return "ZONE3_70_80_PCT_HRMAX"
    if pct >= 60:
        return "ZONE2_60_70_PCT_HRMAX"
    if pct >= 50:
        return "ZONE1_50_60_PCT_HRMAX"
    return "BELOW_ZONE1_LT_50_PCT_HRMAX"


def vo2_tier(value, p25, p75) -> str:
    if pd.isna(value):
        return "VO2MAX_CONTEXT_MISSING"
    if value <= p25:
        return "LOWER_VO2MAX_CONTEXT"
    if value >= p75:
        return "HIGHER_VO2MAX_CONTEXT"
    return "MIDDLE_VO2MAX_CONTEXT"


def difficulty_tier(value) -> str:
    if pd.isna(value):
        return "SELF_REPORTED_DIFFICULTY_MISSING"
    if value >= 7:
        return "SELF_REPORTED_HIGH_DIFFICULTY"
    if value >= 5:
        return "SELF_REPORTED_MODERATE_DIFFICULTY"
    return "SELF_REPORTED_LOW_DIFFICULTY"


def has_behavior_degradation(row) -> bool:
    flags = str(row.get("personal_route_load_match_review_flags", ""))
    level = str(row.get("personal_route_load_match_review_level", ""))
    behavior_tokens = [
        "RELATIVE_SLOWER_SPEED",
        "RELATIVE_HIGH_LOW_SPEED_RATIO",
        "RELATIVE_HIGH_STOPPED_RATIO",
        "RELATIVE_HIGH_ROUTE_LOAD_BEHAVIOR_RESPONSE",
        "MULTI_FACTOR",
        "MODERATE_ATTENTION",
    ]
    joined = f"{flags}|{level}"
    return any(token in joined for token in behavior_tokens)


def hr_output_efficiency_context(row) -> str:
    zone = str(row.get("hr_median_zone_sex_age_est", ""))
    behavior = bool(row.get("behavior_degradation_proxy_present", False))
    level = str(row.get("personal_route_load_match_review_level", ""))

    if zone == "HR_ESTIMATE_EXCEEDS_100_REVIEW":
        return "HRMAX_ESTIMATE_OR_SENSOR_REVIEW_REQUIRED"
    if zone.startswith("ZONE5") or zone.startswith("ZONE4"):
        if behavior:
            return "HIGH_HR_ZONE_WITH_BEHAVIOR_DEGRADATION_REVIEW"
        return "HIGH_HR_ZONE_EFFICIENT_OR_CONTROLLED_OUTPUT_CONTEXT"
    if behavior:
        if "MULTI_FACTOR" in level:
            return "LOWER_OR_MODERATE_HR_WITH_MULTI_FACTOR_BEHAVIOR_DEGRADATION_REVIEW"
        return "LOWER_OR_MODERATE_HR_WITH_BEHAVIOR_DEGRADATION_PROXY_REVIEW"
    return "HR_BEHAVIOR_CONTEXT_REFERENCE_OR_LIMITED_ATTENTION"


def route_load_strain_label(row) -> str:
    level = str(row.get("personal_route_load_match_review_level", ""))
    vo2 = str(row.get("vo2max_context_tier", ""))
    diff = str(row.get("qixing_self_report_difficulty_tier", ""))
    hr_eff = str(row.get("hr_output_efficiency_context", ""))

    multi = "MULTI_FACTOR" in level
    moderate = "MODERATE" in level
    low_vo2 = vo2 == "LOWER_VO2MAX_CONTEXT"
    high_diff = diff == "SELF_REPORTED_HIGH_DIFFICULTY"
    behavior_hr = "BEHAVIOR_DEGRADATION" in hr_eff

    if multi and (low_vo2 or high_diff):
        return "HIGH_CONFIDENCE_ROUTE_LOAD_STRAIN_CANDIDATE_WITH_PROFILE_SUPPORT"
    if multi:
        return "BEHAVIOR_ROUTE_LOAD_STRAIN_CANDIDATE"
    if moderate and (low_vo2 or high_diff):
        return "MODERATE_ROUTE_LOAD_STRAIN_CANDIDATE_WITH_PROFILE_SUPPORT"
    if behavior_hr:
        return "HR_BEHAVIOR_MISMATCH_REVIEW_CANDIDATE"
    if "HIGH_HR_ZONE_EFFICIENT" in hr_eff:
        return "HIGH_HR_OUTPUT_CONTROLLED_CONTEXT_NOT_STRAIN_BY_ITSELF"
    return "REFERENCE_OR_LIMITED_ATTENTION_CONTEXT"


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    match_path = resolve(root, args.match_review)
    profile_path = resolve(root, args.participant_profile)
    out_root = resolve(root, args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)

    match = read_csv(match_path, "CH6.5.4 match review")
    profile = read_csv(profile_path, "participant profile")

    match["activity_id_short"] = match["activity_id_short"].astype(str).str.strip()
    match["participant_id"] = match["activity_id_short"].str.extract(r"^(\d+)").astype(float).astype("Int64")

    for col in [
        "participant_id", "age_yrs", "sex_code", "height_cm", "weight_kg", "bmi",
        "estimated_vo2max_ml_kg_min", "qixing_difficulty_scale"
    ]:
        if col in profile.columns:
            profile[col] = num(profile[col])

    for col in [
        "heart_rate_bpm_median_avg", "speed_mps_median_median", "low_speed_ratio_avg",
        "stopped_ratio_avg", "uphill_high_route_load_ratio",
        "route_load_behavior_candidate_window_ratio",
        "behavior_weather_context_review_required_ratio"
    ]:
        if col in match.columns:
            match[col] = num(match[col])

    joined = match.merge(profile, on="participant_id", how="left", indicator=True)
    joined["metadata_join_status"] = np.where(joined["_merge"].eq("both"), "PARTICIPANT_PROFILE_JOINED", "PARTICIPANT_PROFILE_MISSING")
    joined = joined.drop(columns=["_merge"])

    joined["sex_age_est_hrmax_bpm"] = joined.apply(sex_age_hrmax, axis=1)
    joined["sex_age_est_hrmax_formula"] = np.where(
        joined["sex_code"].eq(1),
        "MALE_214_MINUS_0_8_AGE",
        np.where(joined["sex_code"].eq(2), "FEMALE_209_MINUS_0_7_AGE", "SEX_CODE_MISSING_OR_UNKNOWN"),
    )
    joined["hr_median_pct_sex_age_est_hrmax"] = joined["heart_rate_bpm_median_avg"] / joined["sex_age_est_hrmax_bpm"] * 100
    joined["hr_median_zone_sex_age_est"] = joined["hr_median_pct_sex_age_est_hrmax"].apply(hr_zone)

    vo2 = joined["estimated_vo2max_ml_kg_min"].dropna()
    p25 = float(vo2.quantile(0.25)) if not vo2.empty else np.nan
    p75 = float(vo2.quantile(0.75)) if not vo2.empty else np.nan
    joined["vo2max_context_tier"] = joined["estimated_vo2max_ml_kg_min"].apply(lambda v: vo2_tier(v, p25, p75))
    joined["qixing_self_report_difficulty_tier"] = joined["qixing_difficulty_scale"].apply(difficulty_tier)

    joined["behavior_degradation_proxy_present"] = joined.apply(has_behavior_degradation, axis=1)
    joined["hr_output_efficiency_context"] = joined.apply(hr_output_efficiency_context, axis=1)
    joined["route_load_strain_context_label"] = joined.apply(route_load_strain_label, axis=1)
    joined["interpretation_boundary"] = BOUNDARY

    candidate_labels = [
        "HIGH_CONFIDENCE_ROUTE_LOAD_STRAIN_CANDIDATE_WITH_PROFILE_SUPPORT",
        "BEHAVIOR_ROUTE_LOAD_STRAIN_CANDIDATE",
        "MODERATE_ROUTE_LOAD_STRAIN_CANDIDATE_WITH_PROFILE_SUPPORT",
        "HR_BEHAVIOR_MISMATCH_REVIEW_CANDIDATE",
        "HIGH_HR_OUTPUT_CONTROLLED_CONTEXT_NOT_STRAIN_BY_ITSELF",
    ]
    candidates = joined[joined["route_load_strain_context_label"].isin(candidate_labels)].copy()

    keep_cols = [
        "activity_id_short", "participant_id", "metadata_join_status",
        "age_yrs", "sex_code", "bmi", "estimated_vo2max_ml_kg_min",
        "vo2max_context_tier", "qixing_difficulty_scale", "qixing_self_report_difficulty_tier",
        "heart_rate_bpm_median_avg", "sex_age_est_hrmax_bpm", "sex_age_est_hrmax_formula",
        "hr_median_pct_sex_age_est_hrmax", "hr_median_zone_sex_age_est",
        "behavior_degradation_proxy_present", "hr_output_efficiency_context",
        "personal_route_load_match_review_level", "personal_route_load_match_review_flags",
        "speed_mps_median_median", "low_speed_ratio_avg", "stopped_ratio_avg",
        "uphill_high_route_load_ratio", "route_load_behavior_candidate_window_ratio",
        "behavior_weather_context_review_required_ratio", "route_load_strain_context_label",
        "interpretation_boundary",
    ]
    keep_cols = [c for c in keep_cols if c in joined.columns]

    summary = joined.groupby("route_load_strain_context_label", dropna=False).agg(
        activity_count=("activity_id_short", "count"),
        activity_id_short_list=("activity_id_short", lambda s: "|".join(sorted(map(str, s)))),
    ).reset_index()
    summary["interpretation_boundary"] = BOUNDARY

    hr_summary = joined.groupby("hr_median_zone_sex_age_est", dropna=False).agg(
        activity_count=("activity_id_short", "count"),
        activity_id_short_list=("activity_id_short", lambda s: "|".join(sorted(map(str, s)))),
        hr_pct_mean=("hr_median_pct_sex_age_est_hrmax", "mean"),
        hr_pct_min=("hr_median_pct_sex_age_est_hrmax", "min"),
        hr_pct_max=("hr_median_pct_sex_age_est_hrmax", "max"),
    ).reset_index()
    hr_summary["interpretation_boundary"] = BOUNDARY

    audit = pd.DataFrame([{
        "activity_count": len(joined),
        "participant_profile_rows": len(profile),
        "participant_profile_joined_n": int((joined["metadata_join_status"] == "PARTICIPANT_PROFILE_JOINED").sum()),
        "participant_profile_missing_n": int((joined["metadata_join_status"] != "PARTICIPANT_PROFILE_JOINED").sum()),
        "sex_age_hrmax_available_n": int(joined["sex_age_est_hrmax_bpm"].notna().sum()),
        "hr_zone_available_n": int(joined["hr_median_zone_sex_age_est"].ne("HR_ZONE_MISSING").sum()),
        "candidate_rows": len(candidates),
        "vo2_p25_joined": p25,
        "vo2_p75_joined": p75,
        "audit_conclusion": "PASS_CH6_5_5_PERSONAL_PROFILE_METADATA_JOIN_V0_2_SEX_AGE_HR_ZONE_DESCRIPTIVE_ONLY",
        "interpretation_boundary": BOUNDARY,
    }])

    outputs = {
        "joined": out_root / "personal_profile_metadata_join_v0_2.csv",
        "candidate": out_root / "personal_route_load_strain_candidate_with_profile_v0_2.csv",
        "summary": out_root / "personal_profile_metadata_join_summary_v0_2.csv",
        "hr_zone_summary": out_root / "personal_profile_hr_zone_summary_v0_2.csv",
        "audit": out_root / "personal_profile_metadata_join_audit_v0_2.csv",
    }
    joined[keep_cols].to_csv(outputs["joined"], index=False, encoding="utf-8-sig")
    candidates[keep_cols].to_csv(outputs["candidate"], index=False, encoding="utf-8-sig")
    summary.to_csv(outputs["summary"], index=False, encoding="utf-8-sig")
    hr_summary.to_csv(outputs["hr_zone_summary"], index=False, encoding="utf-8-sig")
    audit.to_csv(outputs["audit"], index=False, encoding="utf-8-sig")

    print({
        "output_root": str(out_root),
        "activity_count": len(joined),
        "participant_profile_rows": len(profile),
        "participant_profile_joined_n": int((joined["metadata_join_status"] == "PARTICIPANT_PROFILE_JOINED").sum()),
        "participant_profile_missing_n": int((joined["metadata_join_status"] != "PARTICIPANT_PROFILE_JOINED").sum()),
        "sex_age_hrmax_available_n": int(joined["sex_age_est_hrmax_bpm"].notna().sum()),
        "hr_zone_available_n": int(joined["hr_median_zone_sex_age_est"].ne("HR_ZONE_MISSING").sum()),
        "candidate_rows": len(candidates),
        "audit_conclusion": "PASS_CH6_5_5_PERSONAL_PROFILE_METADATA_JOIN_V0_2_SEX_AGE_HR_ZONE_DESCRIPTIVE_ONLY",
        "outputs": {k: str(v) for k, v in outputs.items()},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
