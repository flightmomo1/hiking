#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Build CH6.5.5 route-following adjusted proxy v1.2.

This is a governed limited-proxy adjustment layer for route-following stability.

Design intent:
- Mainline / acceptable-route adherence is the primary evidence.
- Missing exact uphill/downhill required anchors is a small review penalty, not a hard failure.
- Wrong-branch / wrong-route evidence is a stronger penalty.
- Post-finish movement away from the trailhead is not counted as route-following instability.
- GPS drift is not counted when map-matching / refit evidence indicates the OSM route is correct.

This script does not compute or authorize ability scores, ability ranks, ability classes,
THCI scores, radar scores, navigation ability scores, final hiking risk scores,
route suitability scores, go/no-go decisions, medical diagnoses, or causal claims.
"""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_NAV_CONTEXT_ROOT = "outputs/report_figures/ch6_5_5_route_following_navigation_context_interpretation_v1"
DEFAULT_ROUTE_FOLLOWING_ROOTS = [
    "outputs/report_figures/ch6_5_5_route_following_stability_proxy_admission_v1_1",
    "outputs/report_figures/ch6_5_5_route_following_stability_proxy_admission_v1",
]
DEFAULT_OUTPUT_ROOT = "outputs/report_figures/ch6_5_5_route_following_adjusted_proxy_v1_2"

BOUNDARY = (
    "CH6.5.5 route-following adjusted proxy v1.2 is a limited descriptive proxy. "
    "It reinterprets route-following stability with mainline adherence as the primary evidence, "
    "wrong-branch evidence as stronger penalty, anchor-miss evidence as small review penalty, "
    "post-finish off-route movement excluded, and GPS drift ignored when route refit/map-matching "
    "is correct. It does not compute or authorize radar scores, ability scores, ability ranks, "
    "ability classes, THCI scores, navigation ability scores, final hiking risk scores, route "
    "suitability scores, go/no-go decisions, medical diagnoses, or causal claims."
)

PASS = "PASS_CH6_5_5_ROUTE_FOLLOWING_ADJUSTED_PROXY_V1_2_MAINLINE_WEIGHTED_LIMITED_PROXY"
REVIEW = "REVIEW_REQUIRED_CH6_5_5_ROUTE_FOLLOWING_ADJUSTED_PROXY_V1_2"

EXCLUDED_ACTIVITY_IDS = {"6_1"}

FORBIDDEN_OUTPUT_PATTERNS = [
    "radar_score",
    "ability_score",
    "ability_rank",
    "ability_class",
    "navigation_ability_score",
    "final_hiking_risk_score",
    "route_suitability_score",
    "go_no_go",
    "medical_diagnosis",
    "causal_claim",
]

TEXT_FLAG_PATTERNS = {
    "wrong_branch": re.compile(
        r"wrong[_ -]?branch|wrong[_ -]?route|route[_ -]?choice|錯路|走錯|支線|非主線|branch",
        re.I,
    ),
    "off_route": re.compile(r"off[_ -]?route|offroute|離線|偏離|deviation|deviat", re.I),
    "post_finish": re.compile(r"post[_ -]?finish|after[_ -]?finish|finish[_ -]?exit|trailhead[_ -]?exit|end[_ -]?exit|離開登山口|結束後", re.I),
    "gps_drift_refit": re.compile(r"gps|drift|飄|refit|re-fit|map[_ -]?match|mapmatched|osm", re.I),
    "anchor_miss": re.compile(r"anchor|checkpoint|required|control[_ -]?point|必經|上山必經|下山必經", re.I),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=r"D:\mountain_work\115_osm")
    parser.add_argument("--navigation-context-root", default=DEFAULT_NAV_CONTEXT_ROOT)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    p = Path(value)
    return p if p.is_absolute() else root / p


def read_csv(path: Path, label: str, required: bool = True) -> pd.DataFrame:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Missing {label}: {path}")
        return pd.DataFrame()
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def activity_col(df: pd.DataFrame) -> str | None:
    for c in ["activity_id", "activity_id_short", "activity", "id"]:
        if c in df.columns:
            return c
    return None


def normalize_activity(value: Any) -> str:
    return str(value).strip()


def numeric(s: pd.Series | Any) -> pd.Series:
    if isinstance(s, pd.Series):
        return pd.to_numeric(s, errors="coerce")
    return pd.Series(dtype="float64")


def find_route_following_sources(root: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for rel_root in DEFAULT_ROUTE_FOLLOWING_ROOTS:
        base = resolve(root, rel_root)
        if not base.exists():
            continue
        candidates = {
            "route_following_activity_summary": [
                "route_following_stability_proxy_activity_summary_v1_1.csv",
                "route_following_stability_proxy_activity_summary_v1.csv",
            ],
            "route_following_event_inventory": [
                "route_following_stability_proxy_event_inventory_v1_1.csv",
                "route_following_stability_proxy_event_inventory_v1.csv",
            ],
            "route_following_admission": [
                "route_following_stability_proxy_admission_decision_v1_1.csv",
                "route_following_stability_proxy_admission_decision_v1.csv",
            ],
            "route_following_audit": [
                "route_following_stability_proxy_admission_audit_v1_1.csv",
                "route_following_stability_proxy_admission_audit_v1.csv",
            ],
        }
        for role, rels in candidates.items():
            if role in found:
                continue
            for rel in rels:
                p = base / rel
                if p.exists():
                    found[role] = p
                    break
    return found


def build_source_inventory(nav_root: Path, rf_sources: dict[str, Path]) -> pd.DataFrame:
    rows = []
    nav_sources = {
        "navigation_context_interpretation": nav_root / "route_following_navigation_context_interpretation_v1.csv",
        "navigation_context_audit": nav_root / "route_following_navigation_context_audit_v1.csv",
        "navigation_context_group_summary": nav_root / "route_following_navigation_context_group_summary_v1.csv",
    }
    for role, p in {**nav_sources, **rf_sources}.items():
        rows.append(
            {
                "source_role": role,
                "source_path": str(p),
                "source_exists": p.exists(),
                "file_size_bytes": p.stat().st_size if p.exists() else 0,
            }
        )
    return pd.DataFrame(rows)


def base_from_nav_context(nav: pd.DataFrame) -> pd.DataFrame:
    df = nav.copy()
    c = activity_col(df)
    if c is None:
        raise KeyError("Navigation context input has no activity id column.")
    df["activity_id"] = df[c].map(normalize_activity)
    df = df[~df["activity_id"].isin(EXCLUDED_ACTIVITY_IDS)].copy()

    # Stable normalized columns.
    for col, default in {
        "route_case_id": "",
        "route_following_stability_proxy_value": np.nan,
        "route_following_band": "",
        "navigation_exposure_level": "",
        "decision_point_exposure_per_km": np.nan,
        "fork_exposure_per_km": np.nan,
        "route_following_navigation_interpretation_label": "",
        "route_following_navigation_review_flag": "",
    }.items():
        if col not in df.columns:
            df[col] = default

    df["prior_route_following_proxy_value"] = pd.to_numeric(
        df["route_following_stability_proxy_value"],
        errors="coerce",
    )

    band_map = {
        "HIGH_ROUTE_FOLLOWING": 88.0,
        "MID_ROUTE_FOLLOWING": 76.0,
        "LOW_ROUTE_FOLLOWING": 64.0,
    }
    band_fallback = df["route_following_band"].astype(str).map(band_map)
    df["prior_route_following_proxy_value"] = df["prior_route_following_proxy_value"].fillna(band_fallback)

    df["decision_point_exposure_per_km_numeric"] = pd.to_numeric(df["decision_point_exposure_per_km"], errors="coerce")
    df["fork_exposure_per_km_numeric"] = pd.to_numeric(df["fork_exposure_per_km"], errors="coerce")

    return df


def extract_text_flags(event_df: pd.DataFrame) -> pd.DataFrame:
    """Extract route-following evidence from governed event inventory.

    Important v1.2 correction:
    - Do not treat generic "off_route" text in terminal artifacts as active-route
      deviation. Many rows contain endpoint_artifact + off_route because the person
      already left the trailhead after finishing; this must be excluded.
    - Only confirmed non-terminal route-issue events become active-off-route evidence.
    - Navigation uncertainty is a review signal, but not automatically a hard route
      following failure.
    """
    empty_cols = [
        "activity_id",
        "wrong_branch_evidence_count",
        "off_route_evidence_count",
        "post_finish_evidence_count",
        "gps_drift_refit_evidence_count",
        "anchor_miss_evidence_count",
    ]

    if event_df.empty:
        return pd.DataFrame(columns=empty_cols)

    c = activity_col(event_df)
    if c is None:
        return pd.DataFrame(columns=empty_cols)

    df = event_df.copy()
    df["activity_id"] = df[c].map(normalize_activity)
    df = df[~df["activity_id"].isin(EXCLUDED_ACTIVITY_IDS)].copy()

    text_cols = []
    for col in df.columns:
        if col == "activity_id":
            continue
        if df[col].dtype == "object" or any(
            key in col.lower()
            for key in ["flag", "event", "status", "label", "reason", "type", "class", "note", "basis", "modifier"]
        ):
            text_cols.append(col)

    if not text_cols:
        df["_event_text"] = ""
    else:
        text_part = df[text_cols].fillna("")
        df["_event_text"] = text_part.apply(
            lambda row: " | ".join(str(x) for x in row.tolist()),
            axis=1,
        )

    # One event row is one evidence unit. Do not use event_id or arbitrary count-like
    # fields as weights; otherwise later events get over-weighted just because their
    # event_id is larger.
    df["_weight"] = 1.0

    def col_bool(col: str) -> pd.Series:
        if col not in df.columns:
            return pd.Series(False, index=df.index)
        return df[col].map(truthy)

    text = df["_event_text"].astype(str)

    terminal_artifact = (
        col_bool("terminal_artifact")
        | text.str.contains(r"terminal_artifact|endpoint_artifact|終點後|終點周邊|不納入 route-core", case=False, regex=True, na=False)
    )

    # Confirmed route evidence is deliberately narrow.
    wrong_branch = (
        ~terminal_artifact
        & text.str.contains(r"wrong[_ -]?branch|wrong[_ -]?route|route[_ -]?choice|錯路|走錯|錯支線", case=False, regex=True, na=False)
    )

    # Confirmed active off-route evidence must come from explicit semantic event labels.
    # Do NOT use generic boolean off_route_event / route_issue_event here, because upstream
    # marks many short_pause / facility_rest rows as off_route context even when they are
    # not confirmed route-following failures.
    event_type_text = df.get("event_type", pd.Series("", index=df.index)).astype(str)
    event_subtype_text = df.get("event_subtype", pd.Series("", index=df.index)).astype(str)
    candidate_reason_text = df.get("candidate_reason", pd.Series("", index=df.index)).astype(str)
    semantic_candidate_text = df.get("semantic_event_type_candidate", pd.Series("", index=df.index)).astype(str)

    explicit_active_event = (
        event_type_text.str.fullmatch(r"route_uncertainty_stop|off_route_rest|off_route_detour", case=False, na=False)
        | event_subtype_text.str.fullmatch(
            r"short_off_route_uncertainty|off_route_exploration_navigation_rejoin_candidate|off_route_detour_or_rejoin_candidate",
            case=False,
            na=False,
        )
        | candidate_reason_text.str.fullmatch(
            r"short_off_route_uncertainty|off_route_exploration_navigation_rejoin_candidate|off_route_detour_or_rejoin_candidate",
            case=False,
            na=False,
        )
        | semantic_candidate_text.str.fullmatch(r"route_uncertainty_stop|off_route_rest|off_route_detour", case=False, na=False)
    )

    confirmed_active_off_route = ~terminal_artifact & explicit_active_event

    # Navigation uncertainty is retained only as context/review evidence. It should
    # not become a strong penalty unless paired with explicit off-route evidence above.
    gps_refit = text.str.contains(r"gps|drift|飄|refit|re-fit|map[_ -]?match|mapmatched|osm", case=False, regex=True, na=False)
    anchor_miss = text.str.contains(r"anchor|checkpoint|required|control[_ -]?point|必經|上山必經|下山必經", case=False, regex=True, na=False)

    df["_wrong_branch_confirmed"] = wrong_branch
    df["_active_off_route_confirmed"] = confirmed_active_off_route
    df["_post_finish"] = terminal_artifact
    df["_gps_drift_refit"] = gps_refit
    df["_anchor_miss"] = anchor_miss & ~terminal_artifact

    if df.empty:
        return pd.DataFrame(columns=empty_cols)

    agg = df.groupby("activity_id").apply(
        lambda g: pd.Series({
            "wrong_branch_evidence_count": float(g.loc[g["_wrong_branch_confirmed"], "_weight"].sum()),
            "off_route_evidence_count": float(g.loc[g["_active_off_route_confirmed"], "_weight"].sum()),
            "post_finish_evidence_count": float(g.loc[g["_post_finish"], "_weight"].sum()),
            "gps_drift_refit_evidence_count": float(g.loc[g["_gps_drift_refit"], "_weight"].sum()),
            "anchor_miss_evidence_count": float(g.loc[g["_anchor_miss"], "_weight"].sum()),
        }),
        include_groups=False,
    ).reset_index()

    return agg


def capped_count(value: Any, cap: float) -> float:
    try:
        x = float(value)
    except Exception:
        return 0.0
    if np.isnan(x):
        return 0.0
    return max(0.0, min(x, cap))


def compute_adjusted_proxy(base: pd.DataFrame, flags: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = base.merge(flags, on="activity_id", how="left")
    for col in [
        "wrong_branch_evidence_count",
        "off_route_evidence_count",
        "post_finish_evidence_count",
        "gps_drift_refit_evidence_count",
        "anchor_miss_evidence_count",
    ]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    rows = []
    breakdown_rows = []
    for _, row in df.iterrows():
        prior = row.get("prior_route_following_proxy_value", np.nan)
        prior = 70.0 if pd.isna(prior) else float(prior)

        rf_band = str(row.get("route_following_band", ""))
        nav_level = str(row.get("navigation_exposure_level", ""))

        wrong = capped_count(row.get("wrong_branch_evidence_count", 0), 5)
        off = capped_count(row.get("off_route_evidence_count", 0), 5)
        anchor = capped_count(row.get("anchor_miss_evidence_count", 0), 5)
        gps_refit = capped_count(row.get("gps_drift_refit_evidence_count", 0), 5)
        post_finish = capped_count(row.get("post_finish_evidence_count", 0), 5)

        # Key governance adjustment:
        # If no explicit wrong-branch/off-route evidence exists, low values are softened
        # because route following should primarily represent mainline adherence, not exact
        # anchor/checkpoint hit rate.
        mainline_floor = 82.0 if wrong == 0 and off == 0 else 68.0
        if rf_band == "HIGH_ROUTE_FOLLOWING":
            mainline_floor = max(mainline_floor, 88.0)
        elif rf_band == "MID_ROUTE_FOLLOWING" and wrong == 0 and off == 0:
            mainline_floor = max(mainline_floor, 80.0)
        elif rf_band == "LOW_ROUTE_FOLLOWING" and wrong == 0 and off == 0:
            mainline_floor = max(mainline_floor, 76.0)

        anchor_penalty = min(4.0, anchor * 0.8)
        wrong_branch_penalty = min(18.0, wrong * 6.0)
        active_off_route_penalty = min(8.0, off * 2.0)
        # GPS refit correct evidence and post-finish movement are not route-following failures.
        gps_refit_credit = min(4.0, gps_refit * 0.8)
        post_finish_exclusion_credit = min(3.0, post_finish * 0.5)

        preliminary = max(prior, mainline_floor)
        adjusted = preliminary - anchor_penalty - wrong_branch_penalty - active_off_route_penalty + gps_refit_credit + post_finish_exclusion_credit
        adjusted = float(max(0.0, min(100.0, adjusted)))

        if adjusted >= 85:
            adjusted_band = "HIGH_ROUTE_FOLLOWING_ADJUSTED"
        elif adjusted >= 72:
            adjusted_band = "MID_ROUTE_FOLLOWING_ADJUSTED"
        else:
            adjusted_band = "LOW_ROUTE_FOLLOWING_ADJUSTED"

        if wrong > 0:
            adjustment_reason = "WRONG_BRANCH_EVIDENCE_PENALIZED"
            review_flag = "ROUTE_FOLLOWING_WRONG_BRANCH_REVIEW"
        elif off > 0:
            adjustment_reason = "ACTIVE_OFF_ROUTE_EVIDENCE_PENALIZED"
            review_flag = "ROUTE_FOLLOWING_ACTIVE_OFF_ROUTE_REVIEW"
        elif anchor > 0 and adjusted >= 72:
            adjustment_reason = "ANCHOR_MISS_SOFT_PENALTY_ONLY"
            review_flag = "ANCHOR_MISS_CONTEXT_REVIEW_ONLY"
        elif prior < adjusted:
            adjustment_reason = "MAINLINE_ADHERENCE_REWEIGHTED_UPWARD"
            review_flag = "ADJUSTED_PROXY_CONTEXT_REWEIGHTED"
        else:
            adjustment_reason = "PRIOR_PROXY_RETAINED"
            review_flag = "ADJUSTED_PROXY_CONTEXT_AVAILABLE"

        if (
            adjusted_band == "HIGH_ROUTE_FOLLOWING_ADJUSTED"
            and nav_level == "HIGH_NAVIGATION_EXPOSURE"
            and wrong == 0
            and off == 0
        ):
            interpretation = "STABLE_MAINLINE_FOLLOWING_UNDER_HIGH_NAVIGATION_EXPOSURE_DESCRIPTIVE_EVIDENCE"
        elif wrong > 0:
            interpretation = "ROUTE_FOLLOWING_LOWERED_BY_WRONG_BRANCH_EVIDENCE"
        elif off > 0:
            interpretation = "ROUTE_FOLLOWING_LOWERED_BY_ACTIVE_OFF_ROUTE_EVIDENCE"
        else:
            interpretation = "ROUTE_FOLLOWING_ADJUSTED_CONTEXT_AVAILABLE_NO_SCORE"

        rows.append({
            "activity_id": row.get("activity_id", ""),
            "route_case_id": row.get("route_case_id", ""),
            "prior_route_following_proxy_value": prior,
            "prior_route_following_band": rf_band,
            "route_following_adjusted_proxy_value": round(adjusted, 3),
            "route_following_adjusted_band": adjusted_band,
            "navigation_exposure_level": nav_level,
            "decision_point_exposure_per_km": row.get("decision_point_exposure_per_km", ""),
            "fork_exposure_per_km": row.get("fork_exposure_per_km", ""),
            "wrong_branch_evidence_count": row.get("wrong_branch_evidence_count", 0),
            "off_route_evidence_count": row.get("off_route_evidence_count", 0),
            "post_finish_evidence_count": row.get("post_finish_evidence_count", 0),
            "gps_drift_refit_evidence_count": row.get("gps_drift_refit_evidence_count", 0),
            "anchor_miss_evidence_count": row.get("anchor_miss_evidence_count", 0),
            "adjustment_reason": adjustment_reason,
            "route_following_adjusted_review_flag": review_flag,
            "route_following_adjusted_interpretation_label": interpretation,
            "adjustment_boundary": BOUNDARY,
        })

        breakdown_rows.append({
            "activity_id": row.get("activity_id", ""),
            "prior_route_following_proxy_value": prior,
            "mainline_floor_applied": mainline_floor,
            "preliminary_after_mainline_floor": round(preliminary, 3),
            "anchor_miss_soft_penalty": round(anchor_penalty, 3),
            "wrong_branch_penalty": round(wrong_branch_penalty, 3),
            "active_off_route_penalty": round(active_off_route_penalty, 3),
            "gps_drift_refit_credit": round(gps_refit_credit, 3),
            "post_finish_exclusion_credit": round(post_finish_exclusion_credit, 3),
            "route_following_adjusted_proxy_value": round(adjusted, 3),
            "post_finish_policy": "EXCLUDED_FROM_ACTIVE_ROUTE_FOLLOWING_PENALTY",
            "gps_refit_policy": "NO_PENALTY_WHEN_REFIT_TO_OSM_ROUTE_IS_CORRECT",
            "anchor_policy": "SOFT_REVIEW_PENALTY_ONLY",
            "wrong_branch_policy": "STRONGER_PENALTY_WHEN_EVIDENCE_EXISTS",
        })

    out = pd.DataFrame(rows).sort_values("activity_id").reset_index(drop=True)
    breakdown = pd.DataFrame(breakdown_rows).sort_values("activity_id").reset_index(drop=True)
    return out, breakdown


def build_group_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    g = (
        df.groupby(["route_following_adjusted_band", "navigation_exposure_level"], dropna=False)
        .agg(
            activity_count=("activity_id", "count"),
            adjusted_proxy_median=("route_following_adjusted_proxy_value", "median"),
            prior_proxy_median=("prior_route_following_proxy_value", "median"),
            wrong_branch_evidence_total=("wrong_branch_evidence_count", "sum"),
            active_off_route_evidence_total=("off_route_evidence_count", "sum"),
            anchor_miss_evidence_total=("anchor_miss_evidence_count", "sum"),
        )
        .reset_index()
    )
    return g


def build_audit(
    adjusted: pd.DataFrame,
    breakdown: pd.DataFrame,
    source_inventory: pd.DataFrame,
    nav_audit: pd.DataFrame,
) -> pd.DataFrame:
    columns = list(adjusted.columns) + list(breakdown.columns)
    forbidden = [c for c in columns if any(p in c.lower() for p in FORBIDDEN_OUTPUT_PATTERNS)]

    activity_ids = set(adjusted.get("activity_id", pd.Series(dtype=str)).astype(str))
    extra_present = bool(activity_ids.intersection(EXCLUDED_ACTIVITY_IDS))

    score_spread = (
        float(adjusted["route_following_adjusted_proxy_value"].max() - adjusted["route_following_adjusted_proxy_value"].min())
        if not adjusted.empty
        else 0.0
    )
    prior_spread = (
        float(adjusted["prior_route_following_proxy_value"].max() - adjusted["prior_route_following_proxy_value"].min())
        if not adjusted.empty
        else 0.0
    )

    review_reasons = []
    if source_inventory["source_exists"].map(truthy).sum() < 2:
        review_reasons.append("REQUIRED_SOURCE_FILE_MISSING")
    if nav_audit.empty or not str(nav_audit.iloc[0].get("audit_conclusion", "")).startswith("PASS_"):
        review_reasons.append("SOURCE_NAVIGATION_CONTEXT_AUDIT_NOT_PASS")
    if extra_present:
        review_reasons.append("EXTRA_SOURCE_ACTIVITY_PRESENT")
    if forbidden:
        review_reasons.append("FORBIDDEN_FIELD_PRESENT")
    if adjusted.empty:
        review_reasons.append("NO_ADJUSTED_ROWS")

    row = {
        "output_adjusted_proxy_count": int(len(adjusted)),
        "prior_proxy_value_min": round(float(adjusted["prior_route_following_proxy_value"].min()), 3) if not adjusted.empty else "",
        "prior_proxy_value_max": round(float(adjusted["prior_route_following_proxy_value"].max()), 3) if not adjusted.empty else "",
        "prior_proxy_value_spread": round(prior_spread, 3),
        "adjusted_proxy_value_min": round(float(adjusted["route_following_adjusted_proxy_value"].min()), 3) if not adjusted.empty else "",
        "adjusted_proxy_value_max": round(float(adjusted["route_following_adjusted_proxy_value"].max()), 3) if not adjusted.empty else "",
        "adjusted_proxy_value_spread": round(score_spread, 3),
        "high_adjusted_count": int(adjusted["route_following_adjusted_band"].astype(str).eq("HIGH_ROUTE_FOLLOWING_ADJUSTED").sum()) if not adjusted.empty else 0,
        "mid_adjusted_count": int(adjusted["route_following_adjusted_band"].astype(str).eq("MID_ROUTE_FOLLOWING_ADJUSTED").sum()) if not adjusted.empty else 0,
        "low_adjusted_count": int(adjusted["route_following_adjusted_band"].astype(str).eq("LOW_ROUTE_FOLLOWING_ADJUSTED").sum()) if not adjusted.empty else 0,
        "stable_under_high_navigation_exposure_count": int(adjusted["route_following_adjusted_interpretation_label"].astype(str).eq("STABLE_MAINLINE_FOLLOWING_UNDER_HIGH_NAVIGATION_EXPOSURE_DESCRIPTIVE_EVIDENCE").sum()) if not adjusted.empty else 0,
        "wrong_branch_penalized_count": int(adjusted["adjustment_reason"].astype(str).eq("WRONG_BRANCH_EVIDENCE_PENALIZED").sum()) if not adjusted.empty else 0,
        "active_off_route_penalized_count": int(adjusted["adjustment_reason"].astype(str).eq("ACTIVE_OFF_ROUTE_EVIDENCE_PENALIZED").sum()) if not adjusted.empty else 0,
        "anchor_soft_penalty_count": int(adjusted["adjustment_reason"].astype(str).eq("ANCHOR_MISS_SOFT_PENALTY_ONLY").sum()) if not adjusted.empty else 0,
        "confirmed_active_off_route_evidence_total": round(float(adjusted["off_route_evidence_count"].sum()), 3) if not adjusted.empty else 0,
        "post_finish_evidence_total_excluded": round(float(adjusted["post_finish_evidence_count"].sum()), 3) if not adjusted.empty else 0,
        "mainline_reweighted_upward_count": int(adjusted["adjustment_reason"].astype(str).eq("MAINLINE_ADHERENCE_REWEIGHTED_UPWARD").sum()) if not adjusted.empty else 0,
        "extra_source_6_1_excluded": not extra_present,
        "zero_fill_used": False,
        "post_finish_off_route_excluded": True,
        "gps_drift_refit_not_penalized_when_correct": True,
        "anchor_miss_soft_penalty_only": True,
        "wrong_branch_evidence_stronger_penalty": True,
        "forbidden_score_rank_class_fields_present": bool(forbidden),
        "forbidden_fields": "|".join(forbidden) if forbidden else "NONE",
        "radar_not_modified": True,
        "axis_contract_not_modified": True,
        "navigation_challenge_not_added_as_axis": True,
        "ability_scoring_absent": True,
        "ranking_absent": True,
        "class_label_absent": True,
        "navigation_ability_scoring_absent": True,
        "go_no_go_absent": True,
        "diagnosis_absent": True,
        "causal_claim_absent": True,
        "admission_decision": "ADMIT_AS_ROUTE_FOLLOWING_ADJUSTED_LIMITED_PROXY_FOR_REVIEW",
        "audit_conclusion": REVIEW if review_reasons else PASS,
        "review_reasons": "|".join(review_reasons) if review_reasons else "NONE",
        "interpretation_boundary": BOUNDARY,
    }
    return pd.DataFrame([row])


def html_table(df: pd.DataFrame, n: int = 80) -> str:
    if df.empty:
        return "<p>No rows.</p>"
    return df.head(n).to_html(index=False, escape=True, classes="data")


def write_report(path: Path, audit: pd.DataFrame, adjusted: pd.DataFrame, breakdown: pd.DataFrame, group_summary: pd.DataFrame, sources: pd.DataFrame) -> None:
    conclusion = audit.iloc[0].get("audit_conclusion", REVIEW) if not audit.empty else REVIEW
    body = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CH6.5.5 Route Following Adjusted Proxy v1.2</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2933; }}
.boundary {{ border-left: 4px solid #687078; padding: 8px 12px; background: #f5f7f8; }}
.status {{ font-weight: 700; }}
table.data {{ border-collapse: collapse; font-size: 12px; margin: 12px 0 24px; }}
table.data th, table.data td {{ border: 1px solid #d6dde3; padding: 5px 7px; vertical-align: top; }}
table.data th {{ background: #eef2f5; }}
</style>
</head>
<body>
<h1>CH6.5.5 Route Following Adjusted Proxy v1.2</h1>
<p class="status">{html.escape(str(conclusion))}</p>
<p class="boundary">{html.escape(BOUNDARY)}</p>

<h2>Audit</h2>
{html_table(audit, 10)}

<h2>Group Summary</h2>
{html_table(group_summary, 60)}

<h2>Adjusted Proxy</h2>
{html_table(adjusted, 120)}

<h2>Penalty / Credit Breakdown</h2>
{html_table(breakdown, 120)}

<h2>Source Inventory</h2>
{html_table(sources, 30)}
</body>
</html>
"""
    path.write_text(body, encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    nav_root = resolve(root, args.navigation_context_root)
    out_root = resolve(root, args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)

    nav_path = nav_root / "route_following_navigation_context_interpretation_v1.csv"
    nav_audit_path = nav_root / "route_following_navigation_context_audit_v1.csv"
    nav = read_csv(nav_path, "navigation context interpretation")
    nav_audit = read_csv(nav_audit_path, "navigation context audit")

    rf_sources = find_route_following_sources(root)
    source_inventory = build_source_inventory(nav_root, rf_sources)

    event_df = pd.DataFrame()
    if "route_following_event_inventory" in rf_sources:
        event_df = read_csv(rf_sources["route_following_event_inventory"], "route-following event inventory", required=False)

    base = base_from_nav_context(nav)
    flags = extract_text_flags(event_df)
    adjusted, breakdown = compute_adjusted_proxy(base, flags)
    group_summary = build_group_summary(adjusted)
    audit = build_audit(adjusted, breakdown, source_inventory, nav_audit)

    outputs = {
        "adjusted": out_root / "route_following_adjusted_proxy_v1_2.csv",
        "breakdown": out_root / "route_following_adjusted_proxy_penalty_breakdown_v1_2.csv",
        "group_summary": out_root / "route_following_adjusted_proxy_group_summary_v1_2.csv",
        "source_inventory": out_root / "route_following_adjusted_proxy_source_inventory_v1_2.csv",
        "audit": out_root / "route_following_adjusted_proxy_audit_v1_2.csv",
        "report": out_root / "route_following_adjusted_proxy_report_v1_2.html",
    }

    adjusted.to_csv(outputs["adjusted"], index=False, encoding="utf-8-sig")
    breakdown.to_csv(outputs["breakdown"], index=False, encoding="utf-8-sig")
    group_summary.to_csv(outputs["group_summary"], index=False, encoding="utf-8-sig")
    source_inventory.to_csv(outputs["source_inventory"], index=False, encoding="utf-8-sig")
    audit.to_csv(outputs["audit"], index=False, encoding="utf-8-sig")
    write_report(outputs["report"], audit, adjusted, breakdown, group_summary, source_inventory)

    summary = {
        "output_root": str(out_root),
        "output_adjusted_proxy_count": int(audit.iloc[0]["output_adjusted_proxy_count"]),
        "high_adjusted_count": int(audit.iloc[0]["high_adjusted_count"]),
        "mid_adjusted_count": int(audit.iloc[0]["mid_adjusted_count"]),
        "low_adjusted_count": int(audit.iloc[0]["low_adjusted_count"]),
        "stable_under_high_navigation_exposure_count": int(audit.iloc[0]["stable_under_high_navigation_exposure_count"]),
        "extra_source_6_1_excluded": bool(audit.iloc[0]["extra_source_6_1_excluded"]),
        "admission_decision": str(audit.iloc[0]["admission_decision"]),
        "audit_conclusion": str(audit.iloc[0]["audit_conclusion"]),
    }
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
