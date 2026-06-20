#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CH6.5.5 v0.5 activity-history numeric attribution.

Consumes:
- CH6.5.5 v0.4 full context
- CH6.5.4 reference thresholds

Produces numeric attribution for:
- primary activity-history strain candidates
- single-factor behavior review rows

The goal is to explain which actual hiking activity-history metrics triggered
the review, not to create an ability score or route suitability score.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd


DEFAULT_CONTEXT = (
    "outputs/report_figures/ch6_5_5_activity_history_primary_relabel_v0_4/"
    "personal_activity_history_primary_full_context_v0_4.csv"
)
DEFAULT_THRESHOLDS = (
    "outputs/report_figures/ch6_5_4_personal_route_load_match_review_v1/"
    "personal_route_load_match_reference_thresholds_v1.csv"
)
DEFAULT_OUT = "outputs/report_figures/ch6_5_5_activity_history_numeric_attribution_v0_5"

BOUNDARY = (
    "Descriptive CH6.5.5 v0.5 activity-history numeric attribution evidence only. "
    "It explains which observed activity-history metrics triggered candidate or review labels. "
    "It does not produce ability scores, ability ranks, ability classes, final hiking risk scores, "
    "route suitability scores, go/no-go decisions, medical diagnoses, or causality evidence."
)

PRIMARY_LABELS = {
    "ACTIVITY_HISTORY_MULTI_FACTOR_STRAIN_CANDIDATE",
    "ACTIVITY_HISTORY_MODERATE_STRAIN_CANDIDATE",
}
REVIEW_LABELS = {
    "ACTIVITY_HISTORY_SINGLE_FACTOR_BEHAVIOR_REVIEW_NEEDS_NUMERIC_CHECK",
    "ACTIVITY_HISTORY_SINGLE_FACTOR_HR_BEHAVIOR_REVIEW_NEEDS_NUMERIC_CHECK",
}
ATTRIBUTION_LABELS = PRIMARY_LABELS | REVIEW_LABELS

METRIC_RULES = [
    {
        "metric": "speed_mps_median_median",
        "threshold_col": "p25",
        "direction": "lower_is_attention",
        "flag": "NUMERIC_SLOWER_SPEED_LE_P25",
        "domain": "movement_degradation",
        "note": "Median speed at or below group p25.",
    },
    {
        "metric": "low_speed_ratio_avg",
        "threshold_col": "p75",
        "direction": "higher_is_attention",
        "flag": "NUMERIC_HIGH_LOW_SPEED_RATIO_GE_P75",
        "domain": "movement_degradation",
        "note": "Low-speed ratio at or above group p75.",
    },
    {
        "metric": "stopped_ratio_avg",
        "threshold_col": "p75",
        "direction": "higher_is_attention",
        "flag": "NUMERIC_HIGH_STOPPED_RATIO_GE_P75",
        "domain": "movement_degradation",
        "note": "Stopped ratio at or above group p75.",
    },
    {
        "metric": "route_load_behavior_candidate_window_ratio",
        "threshold_col": "p75",
        "direction": "higher_is_attention",
        "flag": "NUMERIC_HIGH_ROUTE_LOAD_BEHAVIOR_RESPONSE_GE_P75",
        "domain": "route_load_behavior",
        "note": "Route-load behavior candidate ratio at or above group p75.",
    },
    {
        "metric": "behavior_weather_context_review_required_ratio",
        "threshold_col": "p75",
        "direction": "higher_is_attention",
        "flag": "NUMERIC_HIGH_BEHAVIOR_WEATHER_OVERLAP_GE_P75",
        "domain": "weather_behavior_overlap",
        "note": "Behavior-weather context overlap at or above group p75.",
    },
    {
        "metric": "uphill_high_route_load_ratio",
        "threshold_col": "p75",
        "direction": "higher_is_attention",
        "flag": "NUMERIC_HIGH_UPHILL_LOAD_EXPOSURE_GE_P75_CONTEXT_ONLY",
        "domain": "route_load_exposure_context",
        "note": "High uphill-load exposure at or above group p75. Context only, not strain by itself.",
    },
]


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=r"D:\mountain_work\115_osm")
    p.add_argument("--context", default=DEFAULT_CONTEXT)
    p.add_argument("--thresholds", default=DEFAULT_THRESHOLDS)
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


def to_num(s):
    return pd.to_numeric(s, errors="coerce")


def pipe(values) -> str:
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


def threshold_map(th: pd.DataFrame) -> dict:
    out = {}
    if "metric" not in th.columns:
        raise KeyError("threshold table missing metric column")
    for _, r in th.iterrows():
        metric = str(r["metric"]).strip()
        out[metric] = {}
        for col in ["min", "p25", "median", "p75", "max"]:
            if col in th.columns:
                out[metric][col] = pd.to_numeric(pd.Series([r[col]]), errors="coerce").iloc[0]
    return out


def compare_metric(value, threshold, direction) -> bool:
    if pd.isna(value) or pd.isna(threshold):
        return False
    if direction == "lower_is_attention":
        return float(value) <= float(threshold)
    if direction == "higher_is_attention":
        return float(value) >= float(threshold)
    return False


def flag_distance(value, threshold, direction) -> float:
    """Return signed ratio distance from threshold; positive means beyond attention threshold."""
    if pd.isna(value) or pd.isna(threshold) or float(threshold) == 0:
        return np.nan
    if direction == "lower_is_attention":
        return round((float(threshold) - float(value)) / abs(float(threshold)), 6)
    if direction == "higher_is_attention":
        return round((float(value) - float(threshold)) / abs(float(threshold)), 6)
    return np.nan


def metric_long_rows(row, refs):
    rows = []
    for rule in METRIC_RULES:
        metric = rule["metric"]
        val = row.get(metric, np.nan)
        ref = refs.get(metric, {})
        threshold = ref.get(rule["threshold_col"], np.nan)
        triggered = compare_metric(val, threshold, rule["direction"])
        rows.append({
            "activity_id_short": row.get("activity_id_short"),
            "participant_id": row.get("participant_id"),
            "activity_history_primary_label": row.get("activity_history_primary_label"),
            "metric": metric,
            "metric_value": val,
            "threshold_reference": rule["threshold_col"],
            "threshold_value": threshold,
            "attention_direction": rule["direction"],
            "numeric_attention_triggered": bool(triggered),
            "numeric_attention_flag": rule["flag"] if triggered else "NOT_TRIGGERED",
            "numeric_attention_domain": rule["domain"],
            "threshold_distance_ratio": flag_distance(val, threshold, rule["direction"]) if triggered else np.nan,
            "metric_note": rule["note"],
            "interpretation_boundary": BOUNDARY,
        })
    return rows


def classify(row, triggered_flags, movement_count, route_load_count, weather_count, exposure_count):
    label = str(row.get("activity_history_primary_label", ""))
    hr_zone = str(row.get("hr_median_zone_sex_age_est", ""))
    tertiary = str(row.get("tertiary_profile_context_signal", ""))

    primary_count = movement_count + route_load_count + weather_count

    if label == "ACTIVITY_HISTORY_MULTI_FACTOR_STRAIN_CANDIDATE":
        if primary_count >= 4:
            return "MULTI_FACTOR_NUMERIC_ATTRIBUTION_STRONG"
        if primary_count >= 3:
            return "MULTI_FACTOR_NUMERIC_ATTRIBUTION_SUPPORTED"
        return "MULTI_FACTOR_LABEL_REVIEW_NUMERIC_SUPPORT_WEAK"

    if label == "ACTIVITY_HISTORY_MODERATE_STRAIN_CANDIDATE":
        if primary_count >= 3:
            return "MODERATE_NUMERIC_ATTRIBUTION_SUPPORTED"
        if primary_count >= 2:
            return "MODERATE_NUMERIC_ATTRIBUTION_LIMITED"
        return "MODERATE_LABEL_REVIEW_NUMERIC_SUPPORT_WEAK"

    if label == "ACTIVITY_HISTORY_SINGLE_FACTOR_BEHAVIOR_REVIEW_NEEDS_NUMERIC_CHECK":
        if movement_count >= 1:
            return "SINGLE_FACTOR_BEHAVIOR_NUMERIC_TRIGGER_CONFIRMED"
        return "SINGLE_FACTOR_BEHAVIOR_REVIEW_NUMERIC_TRIGGER_NOT_CONFIRMED"

    if label == "ACTIVITY_HISTORY_SINGLE_FACTOR_HR_BEHAVIOR_REVIEW_NEEDS_NUMERIC_CHECK":
        if movement_count >= 1 and hr_zone.startswith(("ZONE4", "ZONE5")):
            return "SINGLE_FACTOR_HR_PLUS_MOVEMENT_NUMERIC_REVIEW"
        if movement_count >= 1:
            return "SINGLE_FACTOR_MOVEMENT_NUMERIC_REVIEW_WITH_HR_CONTEXT"
        return "SINGLE_FACTOR_HR_CONTEXT_REVIEW_MOVEMENT_NUMERIC_TRIGGER_WEAK"

    return "NOT_IN_NUMERIC_ATTRIBUTION_SCOPE"


def suggested_case_role(row, attribution_label):
    label = str(row.get("activity_history_primary_label", ""))
    profile = str(row.get("profile_context_consistency_with_activity_history", ""))
    activity = str(row.get("activity_id_short", ""))

    if attribution_label.startswith("MULTI_FACTOR_NUMERIC_ATTRIBUTION"):
        return "REPORT_PRIMARY_CASE_CANDIDATE"
    if attribution_label.startswith("MODERATE_NUMERIC_ATTRIBUTION_SUPPORTED"):
        return "REPORT_SECONDARY_CASE_CANDIDATE"
    if "SINGLE_FACTOR" in attribution_label:
        return "NUMERIC_DETAIL_REVIEW_NOT_PRIMARY_CASE_YET"
    if "WEAK" in attribution_label:
        return "MANUAL_REVIEW_BEFORE_REPORT_USE"
    return "CONTEXT_ONLY"


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    context_path = resolve(root, args.context)
    threshold_path = resolve(root, args.thresholds)
    out_root = resolve(root, args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)

    df = read_csv(context_path, "v0.4 activity-history primary full context")
    th = read_csv(threshold_path, "CH6.5.4 reference thresholds")

    for col in [
        "speed_mps_median_median",
        "low_speed_ratio_avg",
        "stopped_ratio_avg",
        "uphill_high_route_load_ratio",
        "route_load_behavior_candidate_window_ratio",
        "behavior_weather_context_review_required_ratio",
        "heart_rate_bpm_median_avg",
        "hr_median_pct_sex_age_est_hrmax",
        "estimated_vo2max_ml_kg_min",
        "qixing_difficulty_scale",
    ]:
        if col in df.columns:
            df[col] = to_num(df[col])

    if "activity_history_primary_label" not in df.columns:
        raise KeyError("v0.4 context missing activity_history_primary_label")

    scope = df[df["activity_history_primary_label"].isin(ATTRIBUTION_LABELS)].copy()

    refs = threshold_map(th)
    long_rows = []
    wide_rows = []

    for _, row in scope.iterrows():
        activity = str(row.get("activity_id_short"))
        metric_rows = metric_long_rows(row, refs)
        long_rows.extend(metric_rows)

        triggered = [r for r in metric_rows if r["numeric_attention_triggered"]]
        flags = [r["numeric_attention_flag"] for r in triggered]
        domains = [r["numeric_attention_domain"] for r in triggered]

        movement_count = sum(1 for d in domains if d == "movement_degradation")
        route_load_count = sum(1 for d in domains if d == "route_load_behavior")
        weather_count = sum(1 for d in domains if d == "weather_behavior_overlap")
        exposure_count = sum(1 for d in domains if d == "route_load_exposure_context")
        attribution = classify(row, flags, movement_count, route_load_count, weather_count, exposure_count)

        wide_rows.append({
            "activity_id_short": activity,
            "participant_id": row.get("participant_id"),
            "activity_history_primary_label": row.get("activity_history_primary_label"),
            "activity_history_evidence_tier": row.get("activity_history_evidence_tier"),
            "personal_route_load_match_review_level": row.get("personal_route_load_match_review_level"),
            "personal_route_load_match_review_flags": row.get("personal_route_load_match_review_flags"),
            "numeric_attribution_label_v0_5": attribution,
            "suggested_report_case_role": suggested_case_role(row, attribution),
            "numeric_attention_flag_count": len(flags),
            "movement_degradation_flag_count": movement_count,
            "route_load_behavior_flag_count": route_load_count,
            "weather_behavior_overlap_flag_count": weather_count,
            "route_load_exposure_context_flag_count": exposure_count,
            "numeric_attention_flags": pipe(flags),
            "numeric_attention_domains": pipe(domains),
            "speed_mps_median_median": row.get("speed_mps_median_median"),
            "low_speed_ratio_avg": row.get("low_speed_ratio_avg"),
            "stopped_ratio_avg": row.get("stopped_ratio_avg"),
            "uphill_high_route_load_ratio": row.get("uphill_high_route_load_ratio"),
            "route_load_behavior_candidate_window_ratio": row.get("route_load_behavior_candidate_window_ratio"),
            "behavior_weather_context_review_required_ratio": row.get("behavior_weather_context_review_required_ratio"),
            "hr_median_zone_sex_age_est": row.get("hr_median_zone_sex_age_est"),
            "hr_output_efficiency_context": row.get("hr_output_efficiency_context"),
            "hr_median_pct_sex_age_est_hrmax": row.get("hr_median_pct_sex_age_est_hrmax"),
            "estimated_vo2max_ml_kg_min": row.get("estimated_vo2max_ml_kg_min"),
            "qixing_difficulty_scale": row.get("qixing_difficulty_scale"),
            "tertiary_profile_context_signal": row.get("tertiary_profile_context_signal"),
            "profile_context_consistency_with_activity_history": row.get("profile_context_consistency_with_activity_history"),
            "interpretation_boundary": BOUNDARY,
        })

    wide = pd.DataFrame(wide_rows)
    long = pd.DataFrame(long_rows)

    if not wide.empty:
        wide = wide.sort_values(
            by=[
                "suggested_report_case_role",
                "numeric_attention_flag_count",
                "movement_degradation_flag_count",
                "activity_id_short",
            ],
            ascending=[True, False, False, True],
            kind="mergesort",
        )

    summary = wide.groupby(["numeric_attribution_label_v0_5", "suggested_report_case_role"], dropna=False).agg(
        activity_count=("activity_id_short", "count"),
        activity_id_short_list=("activity_id_short", lambda s: "|".join(sorted(map(str, s)))),
        mean_numeric_attention_flag_count=("numeric_attention_flag_count", "mean"),
        mean_movement_degradation_flag_count=("movement_degradation_flag_count", "mean"),
    ).reset_index() if not wide.empty else pd.DataFrame()

    flag_summary = long[long["numeric_attention_triggered"]].groupby(
        ["numeric_attention_flag", "numeric_attention_domain"], dropna=False
    ).agg(
        activity_count=("activity_id_short", "nunique"),
        activity_id_short_list=("activity_id_short", lambda s: "|".join(sorted(set(map(str, s))))),
    ).reset_index() if not long.empty else pd.DataFrame()

    # Threshold evidence table used by this run.
    threshold_rows = []
    for rule in METRIC_RULES:
        ref = refs.get(rule["metric"], {})
        threshold_rows.append({
            "metric": rule["metric"],
            "attention_direction": rule["direction"],
            "threshold_reference": rule["threshold_col"],
            "threshold_value": ref.get(rule["threshold_col"], np.nan),
            "p25": ref.get("p25", np.nan),
            "median": ref.get("median", np.nan),
            "p75": ref.get("p75", np.nan),
            "numeric_attention_flag": rule["flag"],
            "numeric_attention_domain": rule["domain"],
            "metric_note": rule["note"],
            "interpretation_boundary": BOUNDARY,
        })
    threshold_evidence = pd.DataFrame(threshold_rows)

    audit = pd.DataFrame([{
        "context_source_path": str(context_path),
        "threshold_source_path": str(threshold_path),
        "activity_count_total_context": int(len(df)),
        "attribution_scope_rows": int(len(wide)),
        "primary_candidate_rows_in_scope": int(df["activity_history_primary_label"].isin(PRIMARY_LABELS).sum()),
        "single_factor_review_rows_in_scope": int(df["activity_history_primary_label"].isin(REVIEW_LABELS).sum()),
        "metric_attribution_long_rows": int(len(long)),
        "triggered_metric_rows": int(long["numeric_attention_triggered"].sum()) if not long.empty else 0,
        "threshold_metric_rules_n": int(len(METRIC_RULES)),
        "profile_promotion_used": False,
        "audit_conclusion": "PASS_CH6_5_5_ACTIVITY_HISTORY_NUMERIC_ATTRIBUTION_V0_5_DESCRIPTIVE_ONLY",
        "interpretation_boundary": BOUNDARY,
    }])

    outputs = {
        "attribution": out_root / "personal_activity_history_numeric_attribution_v0_5.csv",
        "metric_long": out_root / "personal_activity_history_numeric_attribution_metric_long_v0_5.csv",
        "summary": out_root / "personal_activity_history_numeric_attribution_summary_v0_5.csv",
        "flag_summary": out_root / "personal_activity_history_numeric_attribution_flag_summary_v0_5.csv",
        "thresholds": out_root / "personal_activity_history_numeric_attribution_thresholds_v0_5.csv",
        "audit": out_root / "personal_activity_history_numeric_attribution_audit_v0_5.csv",
    }

    wide.to_csv(outputs["attribution"], index=False, encoding="utf-8-sig")
    long.to_csv(outputs["metric_long"], index=False, encoding="utf-8-sig")
    summary.to_csv(outputs["summary"], index=False, encoding="utf-8-sig")
    flag_summary.to_csv(outputs["flag_summary"], index=False, encoding="utf-8-sig")
    threshold_evidence.to_csv(outputs["thresholds"], index=False, encoding="utf-8-sig")
    audit.to_csv(outputs["audit"], index=False, encoding="utf-8-sig")

    print({
        "output_root": str(out_root),
        "attribution_scope_rows": int(len(wide)),
        "metric_attribution_long_rows": int(len(long)),
        "triggered_metric_rows": int(long["numeric_attention_triggered"].sum()) if not long.empty else 0,
        "summary_rows": int(len(summary)),
        "flag_summary_rows": int(len(flag_summary)),
        "audit_conclusion": "PASS_CH6_5_5_ACTIVITY_HISTORY_NUMERIC_ATTRIBUTION_V0_5_DESCRIPTIVE_ONLY",
        "outputs": {k: str(v) for k, v in outputs.items()},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
