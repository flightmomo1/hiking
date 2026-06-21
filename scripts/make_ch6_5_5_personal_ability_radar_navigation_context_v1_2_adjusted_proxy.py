#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Build CH6.5.5 personal ability radar navigation-context v1.2 using adjusted route-following proxy.

This script updates the existing governed personal-ability radar preview with the
CH6.5.5 route-following adjusted proxy v1.2.

It does not add a navigation ability axis. Navigation challenge exposure remains
route/environment context and is shown only as caption, annotation, and review
context. It does not compute or authorize ability scores, ability ranks, ability
classes, THCI scores, radar scores, navigation ability scores, final hiking risk
scores, route suitability scores, go/no-go decisions, medical diagnoses, or causal
claims.
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DEFAULT_RADAR_PLOT_ROOT = "outputs/report_figures/ch6_5_5_personal_ability_radar_plot_v1_1"
DEFAULT_ADJUSTED_PROXY_ROOT = "outputs/report_figures/ch6_5_5_route_following_adjusted_proxy_v1_2"
DEFAULT_NAV_CONTEXT_ROOT = "outputs/report_figures/ch6_5_5_route_following_navigation_context_interpretation_v1"
DEFAULT_OUTPUT_ROOT = "outputs/report_figures/ch6_5_5_personal_ability_radar_navigation_context_v1_2_adjusted_proxy"

BOUNDARY = (
    "CH6.5.5 personal ability radar navigation-context v1.2 adjusted-proxy preview reuses the "
    "governed radar preview axes and replaces the route_following_stability proxy value with "
    "CH6.5.5 route-following adjusted proxy v1.2. Navigation challenge exposure is shown only "
    "as caption/annotation/review context. It is not a personal ability axis and does not create "
    "a navigation ability score. This output does not compute or authorize radar scores, ability "
    "scores, ability ranks, ability classes, THCI scores, final hiking risk scores, route "
    "suitability scores, go/no-go decisions, medical diagnoses, or causal claims."
)

PASS = "PASS_CH6_5_5_PERSONAL_ABILITY_RADAR_NAVIGATION_CONTEXT_V1_2_ADJUSTED_PROXY_PREVIEW"
REVIEW = "REVIEW_REQUIRED_CH6_5_5_PERSONAL_ABILITY_RADAR_NAVIGATION_CONTEXT_V1_2_ADJUSTED_PROXY"

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

PREFERRED_AXIS_ORDER = [
    "terrain_movement_efficiency",
    "pacing_movement_stability",
    "route_following_stability",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=r"D:\mountain_work\115_osm")
    parser.add_argument("--radar-plot-root", default=DEFAULT_RADAR_PLOT_ROOT)
    parser.add_argument("--adjusted-proxy-root", default=DEFAULT_ADJUSTED_PROXY_ROOT)
    parser.add_argument("--navigation-context-root", default=DEFAULT_NAV_CONTEXT_ROOT)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--max-plots", type=int, default=200)
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


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def safe_filename(value: Any) -> str:
    keep = []
    for ch in str(value):
        if ch.isalnum() or ch in {"_", "-", "."}:
            keep.append(ch)
        else:
            keep.append("_")
    return "".join(keep).strip("_") or "unknown"


def first_existing(root: Path, candidates: list[tuple[str, str]]) -> tuple[Path, str]:
    for rel, label in candidates:
        path = root / rel
        if path.exists():
            return path, label
    detail = "\n".join(str(root / rel) for rel, _ in candidates)
    raise FileNotFoundError(f"None of the candidate inputs exists:\n{detail}")


def select_activity_col(df: pd.DataFrame) -> str:
    for c in ["activity_id", "activity_id_short", "activity"]:
        if c in df.columns:
            return c
    raise KeyError("No activity id column found.")


def normalize_activity_key(value: Any) -> str:
    return str(value).strip()


def find_radar_inputs(radar_root: Path) -> dict[str, tuple[Path, str]]:
    ready_path, ready_label = first_existing(
        radar_root,
        [
            ("personal_ability_radar_plot_ready_table_v1_1.csv", "radar plot ready table v1_1"),
            ("personal_ability_radar_plot_ready_table_v1.csv", "radar plot ready table v1"),
        ],
    )
    plot_index_path, plot_index_label = first_existing(
        radar_root,
        [
            ("personal_ability_radar_plot_index_v1_1.csv", "radar plot index v1_1"),
            ("personal_ability_radar_plot_index_v1.csv", "radar plot index v1"),
        ],
    )
    audit_path, audit_label = first_existing(
        radar_root,
        [
            ("personal_ability_radar_plot_audit_v1_1.csv", "radar plot audit v1_1"),
            ("personal_ability_radar_plot_audit_v1.csv", "radar plot audit v1"),
        ],
    )
    out = {
        "plot_ready": (ready_path, ready_label),
        "plot_index": (plot_index_path, plot_index_label),
        "plot_audit": (audit_path, audit_label),
    }
    for rel, label in [
        ("personal_ability_radar_annotation_summary_v1_1.csv", "radar annotation summary v1_1"),
        ("personal_ability_radar_annotation_summary_v1.csv", "radar annotation summary v1"),
    ]:
        p = radar_root / rel
        if p.exists():
            out["annotation_summary"] = (p, label)
            break
    return out


def axis_display_label(axis_id: str, axis_label_zh: str = "") -> str:
    mapping = {
        "terrain_movement_efficiency": "Terrain movement",
        "pacing_movement_stability": "Pacing stability",
        "route_following_stability": "Route following",
    }
    return mapping.get(str(axis_id), str(axis_id).replace("_", " ").title())


def order_axis_rows(rows: pd.DataFrame) -> pd.DataFrame:
    rows = rows.copy()
    order_map = {axis: i for i, axis in enumerate(PREFERRED_AXIS_ORDER)}
    rows["_axis_order"] = rows.get("axis_id", "").astype(str).map(order_map).fillna(999)
    rows["_axis_label_sort"] = rows.get("axis_id", "").astype(str)
    return rows.sort_values(["_axis_order", "_axis_label_sort"]).drop(columns=["_axis_order", "_axis_label_sort"])


def build_adjusted_annotation(adjusted: pd.DataFrame) -> pd.DataFrame:
    df = adjusted.copy()
    c = select_activity_col(df)
    df["activity_key"] = df[c].map(normalize_activity_key)
    df = df[~df["activity_key"].isin(EXCLUDED_ACTIVITY_IDS)].copy()

    for col, default in {
        "route_case_id": "",
        "prior_route_following_proxy_value": np.nan,
        "prior_route_following_band": "",
        "route_following_adjusted_proxy_value": np.nan,
        "route_following_adjusted_band": "",
        "navigation_exposure_level": "",
        "decision_point_exposure_per_km": np.nan,
        "fork_exposure_per_km": np.nan,
        "wrong_branch_evidence_count": 0,
        "off_route_evidence_count": 0,
        "post_finish_evidence_count": 0,
        "adjustment_reason": "",
        "route_following_adjusted_review_flag": "",
        "route_following_adjusted_interpretation_label": "",
    }.items():
        if col not in df.columns:
            df[col] = default

    df["route_following_adjusted_proxy_value_numeric"] = pd.to_numeric(
        df["route_following_adjusted_proxy_value"],
        errors="coerce",
    )
    df["prior_route_following_proxy_value_numeric"] = pd.to_numeric(
        df["prior_route_following_proxy_value"],
        errors="coerce",
    )
    df["off_route_evidence_count_numeric"] = pd.to_numeric(df["off_route_evidence_count"], errors="coerce").fillna(0)
    df["wrong_branch_evidence_count_numeric"] = pd.to_numeric(df["wrong_branch_evidence_count"], errors="coerce").fillna(0)
    df["post_finish_evidence_count_numeric"] = pd.to_numeric(df["post_finish_evidence_count"], errors="coerce").fillna(0)

    def badge(row: pd.Series) -> str:
        interpretation = str(row.get("route_following_adjusted_interpretation_label", ""))
        reason = str(row.get("adjustment_reason", ""))
        band = str(row.get("route_following_adjusted_band", ""))
        nav_level = str(row.get("navigation_exposure_level", ""))
        if interpretation == "STABLE_MAINLINE_FOLLOWING_UNDER_HIGH_NAVIGATION_EXPOSURE_DESCRIPTIVE_EVIDENCE":
            return "STABLE_MAINLINE_FOLLOWING_UNDER_HIGH_NAVIGATION_EXPOSURE"
        if reason == "ACTIVE_OFF_ROUTE_EVIDENCE_PENALIZED":
            return "CONFIRMED_ACTIVE_OFF_ROUTE_REJOIN_REVIEW"
        if reason == "WRONG_BRANCH_EVIDENCE_PENALIZED":
            return "CONFIRMED_WRONG_BRANCH_REVIEW"
        if band == "HIGH_ROUTE_FOLLOWING_ADJUSTED" and nav_level == "HIGH_NAVIGATION_EXPOSURE":
            return "STABLE_MAINLINE_FOLLOWING_UNDER_HIGH_NAVIGATION_EXPOSURE"
        return "ADJUSTED_ROUTE_FOLLOWING_CONTEXT_AVAILABLE"

    def caption(row: pd.Series) -> str:
        badge_text = badge(row)
        prior = row.get("prior_route_following_proxy_value_numeric", np.nan)
        adjusted_value = row.get("route_following_adjusted_proxy_value_numeric", np.nan)
        band = str(row.get("route_following_adjusted_band", "") or "UNKNOWN_ADJUSTED_BAND")
        nav_level = str(row.get("navigation_exposure_level", "") or "UNKNOWN_NAVIGATION_EXPOSURE")
        off_count = float(row.get("off_route_evidence_count_numeric", 0) or 0)
        wrong_count = float(row.get("wrong_branch_evidence_count_numeric", 0) or 0)
        post_finish_count = float(row.get("post_finish_evidence_count_numeric", 0) or 0)

        prior_txt = f"{float(prior):.1f}" if pd.notna(prior) else "NA"
        adjusted_txt = f"{float(adjusted_value):.1f}" if pd.notna(adjusted_value) else "NA"

        if badge_text == "STABLE_MAINLINE_FOLLOWING_UNDER_HIGH_NAVIGATION_EXPOSURE":
            lead = (
                "Adjusted route-following remains high under high navigation-challenge exposure; "
                "this is descriptive evidence of stable mainline following under a more complex route context."
            )
        elif badge_text in {"CONFIRMED_ACTIVE_OFF_ROUTE_REJOIN_REVIEW", "CONFIRMED_WRONG_BRANCH_REVIEW"}:
            lead = (
                "Adjusted route-following is lowered by confirmed active-route issue evidence; "
                "interpret as route-following review context, not as a navigation ability score."
            )
        else:
            lead = (
                "Adjusted route-following context is available; interpretation remains descriptive and score-free."
            )

        return (
            f"{lead} Prior proxy={prior_txt}; adjusted proxy={adjusted_txt}; "
            f"adjusted band={band}; navigation exposure={nav_level}; "
            f"confirmed off-route={off_count:.0f}; confirmed wrong-branch={wrong_count:.0f}; "
            f"post-finish artifacts excluded={post_finish_count:.0f}."
        )

    df["navigation_context_badge"] = df.apply(badge, axis=1)
    df["navigation_context_caption"] = df.apply(caption, axis=1)
    df["navigation_context_boundary"] = BOUNDARY
    df["navigation_context_available"] = True

    cols = [
        "activity_key",
        "route_case_id",
        "prior_route_following_proxy_value",
        "prior_route_following_band",
        "route_following_adjusted_proxy_value",
        "route_following_adjusted_band",
        "navigation_exposure_level",
        "decision_point_exposure_per_km",
        "fork_exposure_per_km",
        "wrong_branch_evidence_count",
        "off_route_evidence_count",
        "post_finish_evidence_count",
        "adjustment_reason",
        "route_following_adjusted_review_flag",
        "route_following_adjusted_interpretation_label",
        "navigation_context_badge",
        "navigation_context_caption",
        "navigation_context_boundary",
        "navigation_context_available",
    ]
    return df[[c for c in cols if c in df.columns]].copy()


def update_plot_ready_with_adjusted_proxy(plot_ready: pd.DataFrame, adjusted_annotation: pd.DataFrame) -> pd.DataFrame:
    df = plot_ready.copy()
    c = select_activity_col(df)
    df["activity_key"] = df[c].map(normalize_activity_key)

    adj = adjusted_annotation[
        [
            "activity_key",
            "route_following_adjusted_proxy_value",
            "route_following_adjusted_band",
            "navigation_context_badge",
        ]
    ].copy()
    adj["route_following_adjusted_proxy_value_numeric"] = pd.to_numeric(
        adj["route_following_adjusted_proxy_value"],
        errors="coerce",
    )

    df = df.merge(adj, on="activity_key", how="left")

    is_route_following = df.get("axis_id", "").astype(str).eq("route_following_stability")
    has_adj = df["route_following_adjusted_proxy_value_numeric"].notna()
    replace_mask = is_route_following & has_adj

    for value_col in ["plot_value", "axis_value"]:
        if value_col in df.columns:
            df.loc[replace_mask, value_col] = df.loc[replace_mask, "route_following_adjusted_proxy_value_numeric"]

    if "axis_value_source" in df.columns:
        df.loc[replace_mask, "axis_value_source"] = "CH6_5_5_ROUTE_FOLLOWING_ADJUSTED_PROXY_V1_2"
    else:
        df["axis_value_source"] = ""
        df.loc[replace_mask, "axis_value_source"] = "CH6_5_5_ROUTE_FOLLOWING_ADJUSTED_PROXY_V1_2"

    df["route_following_adjusted_proxy_applied"] = replace_mask
    df["route_following_adjusted_band_for_annotation"] = df["route_following_adjusted_band"].fillna("")
    df["navigation_context_badge_for_annotation"] = df["navigation_context_badge"].fillna("")

    return df


def build_plot_manifest(
    plot_ready: pd.DataFrame,
    plot_index: pd.DataFrame,
    adjusted_annotation: pd.DataFrame,
    root: Path,
    out_root: Path,
    max_plots: int,
) -> pd.DataFrame:
    activity_col = select_activity_col(plot_ready)
    plot_ready = plot_ready.copy()
    plot_ready["activity_key"] = plot_ready[activity_col].map(normalize_activity_key)

    index_activity_col = select_activity_col(plot_index)
    plot_index = plot_index.copy()
    plot_index["activity_key"] = plot_index[index_activity_col].map(normalize_activity_key)

    plot_dir = out_root / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for i, (activity_key, g) in enumerate(plot_ready.groupby("activity_key", dropna=False)):
        if i >= max_plots:
            break

        g = g.copy()
        idx = plot_index[plot_index["activity_key"] == activity_key].head(1)
        adj_row = adjusted_annotation[adjusted_annotation["activity_key"] == activity_key].head(1)

        study_status = str(g.iloc[0].get("study_population_status", ""))
        participant_id = str(g.iloc[0].get("participant_id", ""))
        base_plot_created = bool(idx.iloc[0].get("plot_created", False)) if not idx.empty else False

        if activity_key in EXCLUDED_ACTIVITY_IDS or study_status != "RADAR_BASELINE_ACTIVITY":
            continue

        if "plot_allowed" in g.columns:
            allowed = g["plot_allowed"].map(truthy)
        elif "axis_value_allowed" in g.columns:
            allowed = g["axis_value_allowed"].map(truthy)
        else:
            allowed = pd.Series([False] * len(g), index=g.index)

        if "plot_value" in g.columns:
            value_col = "plot_value"
        elif "axis_value" in g.columns:
            value_col = "axis_value"
        else:
            value_col = ""

        if value_col:
            g["_plot_value_numeric"] = pd.to_numeric(g[value_col], errors="coerce")
        else:
            g["_plot_value_numeric"] = np.nan

        plot_rows = g[allowed & g["_plot_value_numeric"].notna()].copy()
        plot_rows = order_axis_rows(plot_rows)

        adjusted_context_available = not adj_row.empty
        navigation_context_badge = (
            str(adj_row.iloc[0].get("navigation_context_badge", ""))
            if adjusted_context_available
            else "ADJUSTED_ROUTE_FOLLOWING_CONTEXT_MISSING"
        )
        navigation_context_caption = (
            str(adj_row.iloc[0].get("navigation_context_caption", ""))
            if adjusted_context_available
            else "Adjusted route-following context missing; no navigation-context annotation applied."
        )
        navigation_exposure_level = (
            str(adj_row.iloc[0].get("navigation_exposure_level", ""))
            if adjusted_context_available
            else ""
        )
        adjusted_route_following_band = (
            str(adj_row.iloc[0].get("route_following_adjusted_band", ""))
            if adjusted_context_available
            else ""
        )
        adjusted_route_following_value = (
            adj_row.iloc[0].get("route_following_adjusted_proxy_value", "")
            if adjusted_context_available
            else ""
        )
        prior_route_following_value = (
            adj_row.iloc[0].get("prior_route_following_proxy_value", "")
            if adjusted_context_available
            else ""
        )

        plot_created = False
        plot_reason = "NOT_PLOTTED"
        out_path = plot_dir / f"personal_ability_radar_navigation_context_adjusted_proxy_{safe_filename(activity_key)}_v1_2.png"

        route_axis_applied = bool(plot_rows.get("route_following_adjusted_proxy_applied", pd.Series(False, index=plot_rows.index)).map(truthy).any())

        if plot_rows.empty:
            plot_reason = "NO_ALLOWED_PROXY_AXIS_VALUE"
        elif not adjusted_context_available:
            plot_reason = "MISSING_ADJUSTED_ROUTE_FOLLOWING_CONTEXT"
        elif not route_axis_applied:
            plot_reason = "ROUTE_FOLLOWING_ADJUSTED_PROXY_NOT_APPLIED"
        else:
            plot_activity(
                plot_rows=plot_rows,
                activity_key=activity_key,
                participant_id=participant_id,
                out_path=out_path,
                navigation_context_badge=navigation_context_badge,
                navigation_context_caption=navigation_context_caption,
                navigation_exposure_level=navigation_exposure_level,
                adjusted_route_following_band=adjusted_route_following_band,
                adjusted_route_following_value=adjusted_route_following_value,
            )
            plot_created = True
            plot_reason = "PLOTTED_WITH_ROUTE_FOLLOWING_ADJUSTED_PROXY_AND_NAVIGATION_CONTEXT"

        try:
            plot_path_rel = str(out_path.relative_to(root)) if plot_created else ""
        except Exception:
            plot_path_rel = str(out_path) if plot_created else ""

        rows.append(
            {
                "activity_id": activity_key,
                "participant_id": participant_id,
                "study_population_status": study_status,
                "base_radar_plot_created": base_plot_created,
                "plot_created": plot_created,
                "plot_reason": plot_reason,
                "plot_path": plot_path_rel,
                "plotted_axis_count": int(len(plot_rows)) if plot_created else 0,
                "route_following_adjusted_proxy_applied": route_axis_applied,
                "adjusted_route_following_value": adjusted_route_following_value,
                "prior_route_following_value": prior_route_following_value,
                "adjusted_route_following_band": adjusted_route_following_band,
                "navigation_context_available": adjusted_context_available,
                "navigation_context_badge": navigation_context_badge,
                "navigation_exposure_level": navigation_exposure_level,
                "navigation_context_caption": navigation_context_caption,
                "navigation_context_boundary": BOUNDARY,
            }
        )

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["study_population_status", "activity_id"]).reset_index(drop=True)
    return out


def plot_activity(
    plot_rows: pd.DataFrame,
    activity_key: str,
    participant_id: str,
    out_path: Path,
    navigation_context_badge: str,
    navigation_context_caption: str,
    navigation_exposure_level: str,
    adjusted_route_following_band: str,
    adjusted_route_following_value: Any,
) -> None:
    labels = []
    for _, r in plot_rows.iterrows():
        labels.append(axis_display_label(str(r.get("axis_id", "")), str(r.get("axis_label_zh", ""))))

    values = plot_rows["_plot_value_numeric"].astype(float).clip(lower=0, upper=100).tolist()
    n = len(values)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    values_closed = values + values[:1]
    angles_closed = angles + angles[:1]

    fig = plt.figure(figsize=(9.4, 8.6))
    ax = plt.subplot(111, polar=True)
    ax.plot(angles_closed, values_closed, linewidth=2)
    ax.fill(angles_closed, values_closed, alpha=0.18)

    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=8)

    badge_title = navigation_context_badge.replace("_", " ")
    ax.set_title(
        (
            "Personal ability radar preview with adjusted route-following proxy\n"
            f"activity={activity_key} | participant={participant_id}\n"
            f"{badge_title}"
        ),
        va="bottom",
        fontsize=10.5,
        pad=26,
    )

    try:
        rf_value_txt = f"{float(adjusted_route_following_value):.1f}"
    except Exception:
        rf_value_txt = str(adjusted_route_following_value)

    caption = (
        f"Adjusted route-following: {rf_value_txt} | {adjusted_route_following_band or 'NA'} | "
        f"Navigation exposure: {navigation_exposure_level or 'NA'}\n"
        f"{navigation_context_caption}\n"
        "Navigation context is caption/annotation only; it is not a navigation ability axis or radar score."
    )

    fig.text(0.5, 0.032, caption, ha="center", fontsize=8.1, wrap=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def build_annotation_table(manifest: pd.DataFrame, adjusted_annotation: pd.DataFrame) -> pd.DataFrame:
    if manifest.empty:
        return pd.DataFrame()
    merged = manifest.merge(
        adjusted_annotation,
        left_on="activity_id",
        right_on="activity_key",
        how="left",
        suffixes=("", "_adjusted"),
    )
    cols = [
        "activity_id",
        "participant_id",
        "study_population_status",
        "plot_created",
        "route_following_adjusted_proxy_applied",
        "prior_route_following_proxy_value",
        "prior_route_following_band",
        "route_following_adjusted_proxy_value",
        "route_following_adjusted_band",
        "navigation_context_badge",
        "navigation_exposure_level",
        "decision_point_exposure_per_km",
        "fork_exposure_per_km",
        "wrong_branch_evidence_count",
        "off_route_evidence_count",
        "post_finish_evidence_count",
        "adjustment_reason",
        "route_following_adjusted_review_flag",
        "route_following_adjusted_interpretation_label",
        "navigation_context_caption",
        "plot_path",
        "navigation_context_boundary",
    ]
    return merged[[c for c in cols if c in merged.columns]].copy()


def build_source_inventory(
    radar_inputs: dict[str, tuple[Path, str]],
    adjusted_root: Path,
    nav_root: Path,
) -> pd.DataFrame:
    rows = []
    for role, (path, label) in radar_inputs.items():
        rows.append(
            {
                "source_role": role,
                "source_label": label,
                "source_path": str(path),
                "source_exists": path.exists(),
                "file_size_bytes": path.stat().st_size if path.exists() else 0,
            }
        )

    extra_sources = {
        "route_following_adjusted_proxy": adjusted_root / "route_following_adjusted_proxy_v1_2.csv",
        "route_following_adjusted_proxy_audit": adjusted_root / "route_following_adjusted_proxy_audit_v1_2.csv",
        "navigation_context_interpretation": nav_root / "route_following_navigation_context_interpretation_v1.csv",
        "navigation_context_audit": nav_root / "route_following_navigation_context_audit_v1.csv",
    }
    for role, path in extra_sources.items():
        rows.append(
            {
                "source_role": role,
                "source_label": role,
                "source_path": str(path),
                "source_exists": path.exists(),
                "file_size_bytes": path.stat().st_size if path.exists() else 0,
            }
        )
    return pd.DataFrame(rows)


def build_audit(
    radar_audit: pd.DataFrame,
    adjusted_audit: pd.DataFrame,
    nav_audit: pd.DataFrame,
    manifest: pd.DataFrame,
    annotation_table: pd.DataFrame,
    source_inventory: pd.DataFrame,
) -> pd.DataFrame:
    columns = list(manifest.columns) + list(annotation_table.columns) + list(source_inventory.columns)
    forbidden = [c for c in columns if any(p in c.lower() for p in FORBIDDEN_OUTPUT_PATTERNS)]

    plot_created_count = int(manifest["plot_created"].map(truthy).sum()) if not manifest.empty else 0
    baseline_plot_created_count = (
        int(
            (
                manifest["study_population_status"].astype(str).eq("RADAR_BASELINE_ACTIVITY")
                & manifest["plot_created"].map(truthy)
            ).sum()
        )
        if not manifest.empty
        else 0
    )
    nonbaseline_plot_created_count = plot_created_count - baseline_plot_created_count

    nav_context_count = int(manifest["navigation_context_available"].map(truthy).sum()) if not manifest.empty else 0
    missing_nav_context_count = int((~manifest["navigation_context_available"].map(truthy)).sum()) if not manifest.empty else 0
    route_following_applied_count = int(manifest["route_following_adjusted_proxy_applied"].map(truthy).sum()) if not manifest.empty else 0

    activity_ids = set(manifest.get("activity_id", pd.Series(dtype=str)).astype(str))
    extra_present = bool(activity_ids.intersection(EXCLUDED_ACTIVITY_IDS))

    stable_high_count = (
        int(
            manifest["navigation_context_badge"]
            .astype(str)
            .eq("STABLE_MAINLINE_FOLLOWING_UNDER_HIGH_NAVIGATION_EXPOSURE")
            .sum()
        )
        if not manifest.empty and "navigation_context_badge" in manifest.columns
        else 0
    )
    confirmed_review_count = (
        int(
            manifest["navigation_context_badge"]
            .astype(str)
            .isin(["CONFIRMED_ACTIVE_OFF_ROUTE_REJOIN_REVIEW", "CONFIRMED_WRONG_BRANCH_REVIEW"])
            .sum()
        )
        if not manifest.empty and "navigation_context_badge" in manifest.columns
        else 0
    )

    navigation_axis_added = False
    if not annotation_table.empty:
        axis_like_cols = [c for c in annotation_table.columns if "axis" in c.lower()]
        for c in axis_like_cols:
            vals = annotation_table[c].astype(str).str.lower()
            if vals.str.contains("navigation_ability|navigation_challenge_exposure_axis|navigation_score", regex=True).any():
                navigation_axis_added = True

    review_reasons = []
    if radar_audit.empty or not str(radar_audit.iloc[0].get("audit_conclusion", "")).startswith("PASS_"):
        review_reasons.append("SOURCE_RADAR_AUDIT_NOT_PASS_OR_MISSING")
    if adjusted_audit.empty or not str(adjusted_audit.iloc[0].get("audit_conclusion", "")).startswith("PASS_"):
        review_reasons.append("SOURCE_ADJUSTED_PROXY_AUDIT_NOT_PASS_OR_MISSING")
    if nav_audit.empty or not str(nav_audit.iloc[0].get("audit_conclusion", "")).startswith("PASS_"):
        review_reasons.append("SOURCE_NAVIGATION_CONTEXT_AUDIT_NOT_PASS_OR_MISSING")
    if source_inventory["source_exists"].map(truthy).sum() != len(source_inventory):
        review_reasons.append("MISSING_SOURCE_FILE")
    if forbidden:
        review_reasons.append("FORBIDDEN_FIELD_PRESENT")
    if nonbaseline_plot_created_count:
        review_reasons.append("NON_BASELINE_ACTIVITY_PLOTTED")
    if extra_present:
        review_reasons.append("EXTRA_SOURCE_ACTIVITY_PRESENT_IN_OUTPUT")
    if navigation_axis_added:
        review_reasons.append("NAVIGATION_CONTEXT_ADDED_AS_AXIS")
    if route_following_applied_count != baseline_plot_created_count:
        review_reasons.append("ROUTE_FOLLOWING_ADJUSTED_PROXY_NOT_APPLIED_TO_ALL_PLOTS")

    row = {
        "source_radar_audit_conclusion": radar_audit.iloc[0].get("audit_conclusion", "") if not radar_audit.empty else "",
        "source_adjusted_proxy_audit_conclusion": adjusted_audit.iloc[0].get("audit_conclusion", "") if not adjusted_audit.empty else "",
        "source_navigation_context_audit_conclusion": nav_audit.iloc[0].get("audit_conclusion", "") if not nav_audit.empty else "",
        "manifest_row_count": int(len(manifest)),
        "plot_created_count": plot_created_count,
        "baseline_plot_created_count": baseline_plot_created_count,
        "nonbaseline_plot_created_count": nonbaseline_plot_created_count,
        "route_following_adjusted_proxy_applied_count": route_following_applied_count,
        "navigation_context_available_count": nav_context_count,
        "missing_navigation_context_count": missing_nav_context_count,
        "stable_under_high_navigation_exposure_count": stable_high_count,
        "confirmed_route_issue_review_count": confirmed_review_count,
        "extra_source_6_1_excluded": not extra_present,
        "zero_fill_used": False,
        "radar_axes_reused_only": True,
        "route_following_axis_uses_adjusted_proxy_v1_2": True,
        "navigation_challenge_not_added_as_axis": not navigation_axis_added,
        "navigation_context_is_annotation_only": True,
        "forbidden_score_rank_class_fields_present": bool(forbidden),
        "forbidden_fields": "|".join(forbidden) if forbidden else "NONE",
        "radar_scoring_absent": True,
        "ability_scoring_absent": True,
        "ranking_absent": True,
        "class_label_absent": True,
        "navigation_ability_scoring_absent": True,
        "decision_label_absent": True,
        "diagnosis_absent": True,
        "causal_claim_absent": True,
        "admission_decision": "ADMIT_AS_RADAR_NAVIGATION_CONTEXT_PREVIEW_WITH_ADJUSTED_ROUTE_FOLLOWING_PROXY",
        "audit_conclusion": REVIEW if review_reasons else PASS,
        "review_reasons": "|".join(review_reasons) if review_reasons else "NONE",
        "interpretation_boundary": BOUNDARY,
    }
    return pd.DataFrame([row])


def render_html_table(df: pd.DataFrame, n: int = 80, cols: list[str] | None = None) -> str:
    if df.empty:
        return "<p>No rows.</p>"
    show = df.copy()
    if cols:
        use = [c for c in show.columns if c in cols]
        show = show[use]
    return show.head(n).to_html(index=False, escape=True, classes="data")


def write_gallery_html(
    out_path: Path,
    audit: pd.DataFrame,
    manifest: pd.DataFrame,
    annotation_table: pd.DataFrame,
    source_inventory: pd.DataFrame,
) -> None:
    conclusion = audit.iloc[0].get("audit_conclusion", REVIEW) if not audit.empty else REVIEW

    cards = []
    for _, r in manifest[manifest["plot_created"].map(truthy)].iterrows():
        plot_path = str(r.get("plot_path", ""))
        img_src = "plots/" + Path(plot_path).name if plot_path else ""
        title = html.escape(f"{r.get('activity_id', '')} | {r.get('participant_id', '')}")
        badge = html.escape(str(r.get("navigation_context_badge", "")))
        caption = html.escape(str(r.get("navigation_context_caption", "")))
        cards.append(
            f"""
<div class="plot-card">
  <h3>{title}</h3>
  <p class="badge">{badge}</p>
  <img src="{html.escape(img_src)}" alt="{title}">
  <p class="caption">{caption}</p>
</div>
"""
        )

    gallery = "\n".join(cards) if cards else "<p>No plots created.</p>"

    html_text = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CH6.5.5 Personal Ability Radar Navigation Context v1.2 Adjusted Proxy</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2933; }}
h1, h2 {{ margin-bottom: 8px; }}
.boundary {{ border-left: 4px solid #687078; padding: 8px 12px; background: #f5f7f8; }}
.status {{ font-weight: 700; }}
table.data {{ border-collapse: collapse; font-size: 12px; margin: 12px 0 24px; }}
table.data th, table.data td {{ border: 1px solid #d6dde3; padding: 5px 7px; vertical-align: top; }}
table.data th {{ background: #eef2f5; }}
.plot-card {{ display: inline-block; width: 390px; vertical-align: top; margin: 8px 14px 24px 0; }}
.plot-card img {{ max-width: 370px; border: 1px solid #d6dde3; }}
.badge {{ font-size: 12px; font-weight: 700; }}
.caption {{ font-size: 12px; line-height: 1.35; }}
</style>
</head>
<body>
<h1>CH6.5.5 Personal Ability Radar Navigation Context v1.2 Adjusted Proxy</h1>
<p class="status">{html.escape(str(conclusion))}</p>
<p class="boundary">{html.escape(BOUNDARY)}</p>

<h2>Audit</h2>
{render_html_table(audit, 10)}

<h2>Source Inventory</h2>
{render_html_table(source_inventory, 20)}

<h2>Manifest</h2>
{render_html_table(manifest, 80, [
    "activity_id",
    "participant_id",
    "plot_created",
    "route_following_adjusted_proxy_applied",
    "adjusted_route_following_value",
    "adjusted_route_following_band",
    "navigation_context_badge",
    "navigation_exposure_level",
    "plot_path"
])}

<h2>Radar Gallery</h2>
{gallery}

<h2>Annotation Table</h2>
{render_html_table(annotation_table, 120, [
    "activity_id",
    "participant_id",
    "prior_route_following_proxy_value",
    "route_following_adjusted_proxy_value",
    "route_following_adjusted_band",
    "navigation_context_badge",
    "navigation_exposure_level",
    "off_route_evidence_count",
    "wrong_branch_evidence_count",
    "post_finish_evidence_count",
    "adjustment_reason",
    "route_following_adjusted_interpretation_label",
    "navigation_context_caption"
])}
</body>
</html>
"""
    out_path.write_text(html_text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    radar_root = resolve(root, args.radar_plot_root)
    adjusted_root = resolve(root, args.adjusted_proxy_root)
    nav_root = resolve(root, args.navigation_context_root)
    out_root = resolve(root, args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)

    radar_inputs = find_radar_inputs(radar_root)
    plot_ready_original = read_csv(*radar_inputs["plot_ready"])
    plot_index = read_csv(*radar_inputs["plot_index"])
    radar_audit = read_csv(*radar_inputs["plot_audit"])

    adjusted_path = adjusted_root / "route_following_adjusted_proxy_v1_2.csv"
    adjusted_audit_path = adjusted_root / "route_following_adjusted_proxy_audit_v1_2.csv"
    nav_audit_path = nav_root / "route_following_navigation_context_audit_v1.csv"

    adjusted = read_csv(adjusted_path, "route following adjusted proxy v1_2")
    adjusted_audit = read_csv(adjusted_audit_path, "route following adjusted proxy audit v1_2")
    nav_audit = read_csv(nav_audit_path, "route following navigation context audit v1")

    adjusted_annotation = build_adjusted_annotation(adjusted)
    plot_ready = update_plot_ready_with_adjusted_proxy(plot_ready_original, adjusted_annotation)

    manifest = build_plot_manifest(
        plot_ready=plot_ready,
        plot_index=plot_index,
        adjusted_annotation=adjusted_annotation,
        root=root,
        out_root=out_root,
        max_plots=args.max_plots,
    )
    annotation_table = build_annotation_table(manifest, adjusted_annotation)
    source_inventory = build_source_inventory(radar_inputs, adjusted_root, nav_root)
    audit = build_audit(
        radar_audit=radar_audit,
        adjusted_audit=adjusted_audit,
        nav_audit=nav_audit,
        manifest=manifest,
        annotation_table=annotation_table,
        source_inventory=source_inventory,
    )

    outputs = {
        "audit": out_root / "personal_ability_radar_navigation_context_adjusted_proxy_audit_v1_2.csv",
        "manifest": out_root / "personal_ability_radar_navigation_context_adjusted_proxy_manifest_v1_2.csv",
        "annotation": out_root / "personal_ability_radar_navigation_context_adjusted_proxy_annotation_v1_2.csv",
        "plot_ready": out_root / "personal_ability_radar_navigation_context_adjusted_proxy_plot_ready_v1_2.csv",
        "source_inventory": out_root / "personal_ability_radar_navigation_context_adjusted_proxy_source_inventory_v1_2.csv",
        "gallery": out_root / "personal_ability_radar_navigation_context_adjusted_proxy_gallery_v1_2.html",
    }

    audit.to_csv(outputs["audit"], index=False, encoding="utf-8-sig")
    manifest.to_csv(outputs["manifest"], index=False, encoding="utf-8-sig")
    annotation_table.to_csv(outputs["annotation"], index=False, encoding="utf-8-sig")
    plot_ready.to_csv(outputs["plot_ready"], index=False, encoding="utf-8-sig")
    source_inventory.to_csv(outputs["source_inventory"], index=False, encoding="utf-8-sig")
    write_gallery_html(outputs["gallery"], audit, manifest, annotation_table, source_inventory)

    summary = {
        "output_root": str(out_root),
        "manifest_row_count": int(audit.iloc[0]["manifest_row_count"]),
        "plot_created_count": int(audit.iloc[0]["plot_created_count"]),
        "route_following_adjusted_proxy_applied_count": int(audit.iloc[0]["route_following_adjusted_proxy_applied_count"]),
        "stable_under_high_navigation_exposure_count": int(audit.iloc[0]["stable_under_high_navigation_exposure_count"]),
        "confirmed_route_issue_review_count": int(audit.iloc[0]["confirmed_route_issue_review_count"]),
        "extra_source_6_1_excluded": bool(audit.iloc[0]["extra_source_6_1_excluded"]),
        "admission_decision": str(audit.iloc[0]["admission_decision"]),
        "audit_conclusion": str(audit.iloc[0]["audit_conclusion"]),
    }
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
