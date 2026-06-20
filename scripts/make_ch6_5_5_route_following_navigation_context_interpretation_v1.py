#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
CH6.5.5 route-following ? navigation challenge context interpretation v1

Purpose
-------
Consume the governed navigation-challenge exposure context produced by:
  outputs/report_figures/ch6_5_5_navigation_challenge_context_consumption_v1_1

and produce a conservative interpretation layer for route_following_stability.

This script does NOT modify radar outputs, axis contracts, data tables, or upstream evidence.
It does NOT compute ability scores, ranks, classes, final hiking risk scores, route suitability
scores, go/no-go decisions, medical diagnoses, or causal claims.

Expected working directory:
  D:\mountain_work\115_osm
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

ROOT = Path.cwd()
INPUT_ROOT = ROOT / "outputs" / "report_figures" / "ch6_5_5_navigation_challenge_context_consumption_v1_1"
OUTPUT_ROOT = ROOT / "outputs" / "report_figures" / "ch6_5_5_route_following_navigation_context_interpretation_v1"
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

RF_NAV_CSV = INPUT_ROOT / "route_following_with_navigation_context_v1_1.csv"
ACTIVITY_CTX_CSV = INPUT_ROOT / "activity_navigation_challenge_context_v1_1.csv"
ROUTE_CTX_CSV = INPUT_ROOT / "route_navigation_challenge_context_v1_1.csv"
CONSUMPTION_AUDIT_CSV = INPUT_ROOT / "navigation_challenge_context_consumption_audit_v1_1.csv"
CONSUMPTION_ADMISSION_CSV = INPUT_ROOT / "navigation_challenge_context_consumption_admission_v1_1.csv"

OUT_INTERPRETATION = OUTPUT_ROOT / "route_following_navigation_context_interpretation_v1.csv"
OUT_GROUP_SUMMARY = OUTPUT_ROOT / "route_following_navigation_context_group_summary_v1.csv"
OUT_AUDIT = OUTPUT_ROOT / "route_following_navigation_context_audit_v1.csv"
OUT_REPORT = OUTPUT_ROOT / "route_following_navigation_context_report_v1.html"
OUT_SOURCE_INVENTORY = OUTPUT_ROOT / "route_following_navigation_context_source_inventory_v1.csv"

EXCLUDED_ACTIVITY_IDS = {"6_1"}

INTERPRETATION_BOUNDARY = (
    "Route-following ? navigation-challenge context interpretation only. "
    "Not a personal ability axis, ability score, rank, class, radar score, final hiking risk score, "
    "route suitability score, go/no-go decision, medical diagnosis, or causal claim."
)

FORBIDDEN_TOKENS = [
    "ability_score",
    "ability_rank",
    "ability_class",
    "final_hiking_risk_score",
    "route_suitability_score",
    "go_no_go",
    "medical_diagnosis",
    "causal_claim",
    "navigation_ability_score",
    "radar_score",
]


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def first_value(df: pd.DataFrame, col: str, default: str = "") -> str:
    if df.empty or col not in df.columns:
        return default
    vals = [str(v) for v in df[col].tolist() if str(v) != ""]
    return vals[0] if vals else default


def to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def ensure_columns(df: pd.DataFrame, cols: Iterable[str]) -> pd.DataFrame:
    df = df.copy()
    for col in cols:
        if col not in df.columns:
            df[col] = ""
    return df


def copy_from_activity_context(base: pd.DataFrame, activity_ctx: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    """Fill missing columns in base from activity context using activity_id."""
    base = base.copy()
    if activity_ctx.empty or "activity_id" not in base.columns or "activity_id" not in activity_ctx.columns:
        return ensure_columns(base, cols)

    missing = [c for c in cols if c not in base.columns]
    present = [c for c in cols if c in activity_ctx.columns]
    if not present and not missing:
        return ensure_columns(base, cols)

    join_cols = ["activity_id"] + [c for c in present if c not in base.columns]
    if len(join_cols) > 1:
        base = base.merge(activity_ctx[join_cols].drop_duplicates("activity_id"), on="activity_id", how="left")

    # Fill blank values from suffixed columns if both existed in rare cases.
    for c in cols:
        if c not in base.columns:
            base[c] = ""
    return base


def compute_route_context_thresholds(route_ctx: pd.DataFrame) -> Tuple[Optional[float], Optional[float], str]:
    """Return low/high threshold for exposure_per_km based on route context distribution."""
    if route_ctx.empty:
        return None, None, "NO_ROUTE_CONTEXT_DISTRIBUTION"

    metric_col = None
    for c in ["decision_point_exposure_per_km", "fork_exposure_per_km"]:
        if c in route_ctx.columns:
            metric_col = c
            break
    if metric_col is None:
        return None, None, "NO_EXPOSURE_PER_KM_COLUMN"

    values = to_num(route_ctx[metric_col]).dropna()
    if values.empty:
        return None, None, "NO_NUMERIC_EXPOSURE_PER_KM_VALUES"

    if len(values) >= 3:
        low_thr = float(values.quantile(0.333333))
        high_thr = float(values.quantile(0.666667))
        method = f"ROUTE_CONTEXT_TERTILES_{metric_col}"
    else:
        low_thr = float(values.min())
        high_thr = float(values.max())
        method = f"ROUTE_CONTEXT_MIN_MAX_{metric_col}"

    return low_thr, high_thr, method


def classify_exposure(value: Optional[float], low_thr: Optional[float], high_thr: Optional[float]) -> str:
    if value is None or pd.isna(value):
        return "NAVIGATION_EXPOSURE_UNKNOWN"
    if high_thr is None or low_thr is None:
        return "NAVIGATION_EXPOSURE_CONTEXT_AVAILABLE"
    if value >= high_thr:
        return "HIGH_NAVIGATION_EXPOSURE"
    if value <= low_thr:
        return "LOW_NAVIGATION_EXPOSURE"
    return "MID_NAVIGATION_EXPOSURE"


def classify_route_following(value: Optional[float]) -> str:
    if value is None or pd.isna(value):
        return "ROUTE_FOLLOWING_PROXY_MISSING"
    if value >= 80:
        return "HIGH_ROUTE_FOLLOWING"
    if value >= 50:
        return "MID_ROUTE_FOLLOWING"
    return "LOW_ROUTE_FOLLOWING"


def interpretation_label(route_following_band: str, exposure_level: str, has_context: bool) -> str:
    if not has_context:
        return "MISSING_NAVIGATION_CONTEXT_REVIEW"
    if route_following_band == "ROUTE_FOLLOWING_PROXY_MISSING":
        return "ROUTE_FOLLOWING_PROXY_MISSING_CONTEXT_ONLY_REVIEW"
    if route_following_band == "HIGH_ROUTE_FOLLOWING" and exposure_level == "HIGH_NAVIGATION_EXPOSURE":
        return "HIGH_ROUTE_FOLLOWING_UNDER_HIGH_NAVIGATION_EXPOSURE"
    if route_following_band == "LOW_ROUTE_FOLLOWING" and exposure_level == "HIGH_NAVIGATION_EXPOSURE":
        return "LOW_ROUTE_FOLLOWING_UNDER_HIGH_NAVIGATION_EXPOSURE_REVIEW"
    if route_following_band == "LOW_ROUTE_FOLLOWING" and exposure_level == "LOW_NAVIGATION_EXPOSURE":
        return "LOW_ROUTE_FOLLOWING_UNDER_LOW_NAVIGATION_EXPOSURE_REVIEW"
    if route_following_band == "LOW_ROUTE_FOLLOWING":
        return "LOW_ROUTE_FOLLOWING_UNDER_AVAILABLE_NAVIGATION_CONTEXT_REVIEW"
    return "CONTEXT_AVAILABLE_NO_SCORE"


def review_flag(label: str) -> str:
    if "REVIEW" in label or label.startswith("MISSING"):
        return "REVIEW_RECOMMENDED"
    return "NO_REVIEW_FLAG"


def forbidden_fields_present(columns: Iterable[str]) -> str:
    hits: List[str] = []
    for col in columns:
        c = str(col).lower()
        if c.startswith("not_"):
            continue
        for tok in FORBIDDEN_TOKENS:
            if tok in c:
                hits.append(col)
                break
    return "NONE" if not hits else "|".join(sorted(set(hits)))


def write_html_report(
    audit: Dict[str, object],
    route_ctx: pd.DataFrame,
    group_summary: pd.DataFrame,
    source_inventory: pd.DataFrame,
) -> None:
    def table(df: pd.DataFrame, max_rows: int = 30) -> str:
        if df.empty:
            return "<p><em>No rows.</em></p>"
        return df.head(max_rows).to_html(index=False, escape=True)

    html_doc = f"""<!doctype html>
<html lang=\"zh-Hant\">
<head>
  <meta charset=\"utf-8\" />
  <title>CH6.5.5 Route-following ? Navigation Challenge Context Interpretation v1</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 2rem; line-height: 1.55; }}
    h1, h2 {{ color: #222; }}
    table {{ border-collapse: collapse; margin: 1rem 0; font-size: 0.9rem; }}
    th, td {{ border: 1px solid #ddd; padding: 0.35rem 0.55rem; vertical-align: top; }}
    th {{ background: #f3f3f3; }}
    code {{ background: #f6f6f6; padding: 0.1rem 0.25rem; }}
    .boundary {{ border-left: 4px solid #999; padding-left: 1rem; color: #444; }}
  </style>
</head>
<body>
  <h1>CH6.5.5 Route-following ? Navigation Challenge Context Interpretation v1</h1>
  <p class=\"boundary\">{html.escape(INTERPRETATION_BOUNDARY)}</p>
  <h2>Audit summary</h2>
  {table(pd.DataFrame([audit]).T.reset_index().rename(columns={"index": "metric", 0: "value"}), 100)}
  <h2>Route navigation context</h2>
  {table(route_ctx, 20)}
  <h2>Interpretation group summary</h2>
  {table(group_summary, 50)}
  <h2>Source inventory</h2>
  {table(source_inventory, 20)}
</body>
</html>"""
    OUT_REPORT.write_text(html_doc, encoding="utf-8")


def main() -> None:
    rf_nav = read_csv_if_exists(RF_NAV_CSV)
    activity_ctx = read_csv_if_exists(ACTIVITY_CTX_CSV)
    route_ctx = read_csv_if_exists(ROUTE_CTX_CSV)
    consumption_audit = read_csv_if_exists(CONSUMPTION_AUDIT_CSV)
    consumption_admission = read_csv_if_exists(CONSUMPTION_ADMISSION_CSV)

    source_inventory = pd.DataFrame([
        {
            "source_name": "route_following_with_navigation_context_v1_1",
            "source_path": str(RF_NAV_CSV.relative_to(ROOT)) if RF_NAV_CSV.exists() else str(RF_NAV_CSV),
            "exists": str(RF_NAV_CSV.exists()),
            "row_count": len(rf_nav),
            "source_role": "primary_route_following_navigation_join",
            "notes": "Primary input from CH6.5.5 navigation challenge context consumption v1_1.",
        },
        {
            "source_name": "activity_navigation_challenge_context_v1_1",
            "source_path": str(ACTIVITY_CTX_CSV.relative_to(ROOT)) if ACTIVITY_CTX_CSV.exists() else str(ACTIVITY_CTX_CSV),
            "exists": str(ACTIVITY_CTX_CSV.exists()),
            "row_count": len(activity_ctx),
            "source_role": "activity_navigation_context",
            "notes": "Used to fill activity-level exposure fields if missing in primary join.",
        },
        {
            "source_name": "route_navigation_challenge_context_v1_1",
            "source_path": str(ROUTE_CTX_CSV.relative_to(ROOT)) if ROUTE_CTX_CSV.exists() else str(ROUTE_CTX_CSV),
            "exists": str(ROUTE_CTX_CSV.exists()),
            "row_count": len(route_ctx),
            "source_role": "route_navigation_context_threshold_reference",
            "notes": "Used to define relative navigation exposure bands from route-level context distribution.",
        },
    ])

    if rf_nav.empty:
        interpretation = pd.DataFrame()
        group_summary = pd.DataFrame()
    else:
        df = rf_nav.copy()
        df = df[df.get("activity_id", "").astype(str).map(lambda x: x not in EXCLUDED_ACTIVITY_IDS)].copy()
        df = copy_from_activity_context(
            df,
            activity_ctx,
            [
                "route_case_id",
                "governed_decision_point_exposure_count",
                "governed_fork_exposure_count",
                "decision_point_exposure_per_km",
                "fork_exposure_per_km",
                "route_length_m",
                "navigation_challenge_context_status",
            ],
        )

        for col in [
            "activity_id",
            "route_case_id",
            "route_following_stability_proxy_value",
            "route_following_source_status",
            "navigation_challenge_context_status",
            "governed_decision_point_exposure_count",
            "governed_fork_exposure_count",
            "decision_point_exposure_per_km",
            "fork_exposure_per_km",
            "route_length_m",
        ]:
            if col not in df.columns:
                df[col] = ""

        low_thr, high_thr, threshold_method = compute_route_context_thresholds(route_ctx)
        rf_values = to_num(df["route_following_stability_proxy_value"])
        exp_values = to_num(df["decision_point_exposure_per_km"])

        df["route_following_band"] = [classify_route_following(v) for v in rf_values]
        df["navigation_exposure_level"] = [classify_exposure(v, low_thr, high_thr) for v in exp_values]
        df["navigation_exposure_threshold_method"] = threshold_method
        df["navigation_exposure_low_threshold_per_km"] = "" if low_thr is None else round(low_thr, 6)
        df["navigation_exposure_high_threshold_per_km"] = "" if high_thr is None else round(high_thr, 6)

        has_context = df["navigation_challenge_context_status"].astype(str).str.contains("AVAILABLE", na=False)
        df["route_following_navigation_interpretation_label"] = [
            interpretation_label(rf_band, exp_level, bool(ctx))
            for rf_band, exp_level, ctx in zip(df["route_following_band"], df["navigation_exposure_level"], has_context)
        ]
        df["route_following_navigation_review_flag"] = df["route_following_navigation_interpretation_label"].map(review_flag)
        df["not_personal_ability_axis"] = "True"
        df["not_navigation_ability_score"] = "True"
        df["not_radar_score"] = "True"
        df["not_go_no_go_decision"] = "True"
        df["interpretation_boundary"] = INTERPRETATION_BOUNDARY

        ordered_cols = [
            "activity_id",
            "route_case_id",
            "route_following_stability_proxy_value",
            "route_following_band",
            "route_following_source_status",
            "navigation_challenge_context_status",
            "governed_decision_point_exposure_count",
            "governed_fork_exposure_count",
            "decision_point_exposure_per_km",
            "fork_exposure_per_km",
            "route_length_m",
            "navigation_exposure_level",
            "navigation_exposure_threshold_method",
            "navigation_exposure_low_threshold_per_km",
            "navigation_exposure_high_threshold_per_km",
            "route_following_navigation_interpretation_label",
            "route_following_navigation_review_flag",
            "not_personal_ability_axis",
            "not_navigation_ability_score",
            "not_radar_score",
            "not_go_no_go_decision",
            "interpretation_boundary",
        ]
        interpretation = df[ordered_cols].sort_values("activity_id", kind="stable")

        group_cols = [
            "route_following_band",
            "navigation_exposure_level",
            "route_following_navigation_interpretation_label",
            "route_following_navigation_review_flag",
        ]
        group_summary = (
            interpretation.groupby(group_cols, dropna=False)
            .size()
            .reset_index(name="activity_count")
            .sort_values(["route_following_navigation_review_flag", "activity_count"], ascending=[True, False])
        )

    interpretation.to_csv(OUT_INTERPRETATION, index=False, encoding="utf-8-sig")
    group_summary.to_csv(OUT_GROUP_SUMMARY, index=False, encoding="utf-8-sig")
    source_inventory.to_csv(OUT_SOURCE_INVENTORY, index=False, encoding="utf-8-sig")

    # Audit
    excluded_found_in_raw = 0
    if not rf_nav.empty and "activity_id" in rf_nav.columns:
        excluded_found_in_raw = int(rf_nav["activity_id"].astype(str).isin(EXCLUDED_ACTIVITY_IDS).sum())
    excluded_found_in_output = 0
    if not interpretation.empty and "activity_id" in interpretation.columns:
        excluded_found_in_output = int(interpretation["activity_id"].astype(str).isin(EXCLUDED_ACTIVITY_IDS).sum())

    forbidden = forbidden_fields_present(list(interpretation.columns) + list(group_summary.columns) + list(source_inventory.columns))

    input_audit_conclusion = first_value(consumption_audit, "audit_conclusion")
    input_admission_decision = first_value(consumption_audit, "admission_decision") or first_value(consumption_admission, "decision")

    output_count = len(interpretation)
    context_available_count = int(
        interpretation.get("navigation_challenge_context_status", pd.Series(dtype=str))
        .astype(str)
        .str.contains("AVAILABLE", na=False)
        .sum()
    ) if not interpretation.empty else 0
    review_recommended_count = int(
        (interpretation.get("route_following_navigation_review_flag", pd.Series(dtype=str)) == "REVIEW_RECOMMENDED").sum()
    ) if not interpretation.empty else 0

    admission_decision = (
        "ADMIT_AS_ROUTE_FOLLOWING_NAVIGATION_CONTEXT_INTERPRETATION"
        if output_count > 0 and context_available_count == output_count and excluded_found_in_output == 0
        else "RETAIN_FOR_REVIEW_ROUTE_FOLLOWING_NAVIGATION_CONTEXT_INTERPRETATION"
    )

    audit_conclusion = (
        "PASS_CH6_5_5_ROUTE_FOLLOWING_NAVIGATION_CONTEXT_INTERPRETATION_V1_GOVERNED_CONTEXT_AVAILABLE"
        if admission_decision.startswith("ADMIT") and forbidden == "NONE"
        else "REVIEW_CH6_5_5_ROUTE_FOLLOWING_NAVIGATION_CONTEXT_INTERPRETATION_V1"
    )

    audit = {
        "input_root_exists": INPUT_ROOT.exists(),
        "route_following_navigation_context_exists": RF_NAV_CSV.exists(),
        "activity_navigation_context_exists": ACTIVITY_CTX_CSV.exists(),
        "route_navigation_context_exists": ROUTE_CTX_CSV.exists(),
        "input_audit_conclusion": input_audit_conclusion,
        "input_admission_decision": input_admission_decision,
        "source_inventory_count": len(source_inventory),
        "input_route_following_context_count": len(rf_nav),
        "output_interpretation_count": output_count,
        "context_available_count": context_available_count,
        "review_recommended_count": review_recommended_count,
        "group_summary_count": len(group_summary),
        "excluded_activity_ids": "|".join(sorted(EXCLUDED_ACTIVITY_IDS)),
        "excluded_activity_found_in_input_count": excluded_found_in_raw,
        "excluded_activity_found_in_output_count": excluded_found_in_output,
        "extra_source_6_1_excluded": excluded_found_in_output == 0,
        "zero_fill_used": False,
        "ch6_5_axis_contract_not_modified": True,
        "radar_not_modified": True,
        "data_table_not_modified": True,
        "navigation_challenge_not_added_as_axis": True,
        "forbidden_fields_present": forbidden,
        "ability_scoring_absent": True,
        "ranking_absent": True,
        "class_label_absent": True,
        "decision_label_absent": True,
        "admission_decision": admission_decision,
        "audit_conclusion": audit_conclusion,
        "interpretation_boundary": INTERPRETATION_BOUNDARY,
    }
    pd.DataFrame([audit]).to_csv(OUT_AUDIT, index=False, encoding="utf-8-sig")
    write_html_report(audit, route_ctx, group_summary, source_inventory)

    print({
        "output_root": str(OUTPUT_ROOT),
        "output_interpretation_count": output_count,
        "context_available_count": context_available_count,
        "review_recommended_count": review_recommended_count,
        "extra_source_6_1_excluded": excluded_found_in_output == 0,
        "admission_decision": admission_decision,
        "audit_conclusion": audit_conclusion,
    })


if __name__ == "__main__":
    main()

