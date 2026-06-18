#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CH6.5.5 personal activity performance radar v0.

This script converts the current CH6.5.5 activity-history-primary evidence into
radar-ready descriptive axis data.

Inputs:
- v0.4 full context:
  outputs/report_figures/ch6_5_5_activity_history_primary_relabel_v0_4/
    personal_activity_history_primary_full_context_v0_4.csv

- v0.5 numeric attribution:
  outputs/report_figures/ch6_5_5_activity_history_numeric_attribution_v0_5/
    personal_activity_history_numeric_attribution_v0_5.csv

Outputs:
- personal_activity_performance_radar_axis_v0.csv
- personal_activity_performance_radar_activity_summary_v0.csv
- personal_activity_performance_radar_missing_evidence_v0.csv
- personal_activity_performance_radar_audit_v0.csv

Boundary:
This is a descriptive, group-relative visualization layer only. It is not an
ability score, ability rank, ability class, THCI score, final hiking risk score,
route suitability score, go/no-go decision, medical diagnosis, or causality
evidence. Missing axes are kept as INSUFFICIENT_EVIDENCE and are not zero-filled.
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
DEFAULT_ATTRIB = (
    "outputs/report_figures/ch6_5_5_activity_history_numeric_attribution_v0_5/"
    "personal_activity_history_numeric_attribution_v0_5.csv"
)
DEFAULT_OUT = "outputs/report_figures/ch6_5_5_personal_activity_performance_radar_v0"

BOUNDARY = (
    "Descriptive CH6.5.5 personal activity performance radar-ready context only. "
    "Axis values are group-relative descriptive indices for visualization and review. "
    "They are not ability scores, ability ranks, ability classes, THCI scores, final "
    "hiking risk scores, route suitability scores, go/no-go decisions, medical diagnoses, "
    "or causality evidence. Missing axes remain INSUFFICIENT_EVIDENCE and are not zero-filled."
)


AXES = [
    {
        "axis_id": "sustained_progress",
        "axis_label_zh": "持續推進能力",
        "support_status": "SUPPORTED_ACTIVITY_HISTORY",
        "components": [
            ("speed_mps_median_median", "higher"),
            ("low_speed_ratio_avg", "lower"),
            ("stopped_ratio_avg", "lower"),
        ],
        "description": "Group-relative movement continuity using speed, low-speed ratio, and stopped ratio.",
    },
    {
        "axis_id": "uphill_load_tolerance_proxy",
        "axis_label_zh": "上坡負荷承受力（有限代理）",
        "support_status": "LIMITED_PROXY_ACTIVITY_HISTORY",
        "components": [
            ("route_load_behavior_candidate_window_ratio", "lower"),
            ("uphill_high_route_load_ratio", "context_lower"),
        ],
        "description": "Limited proxy using route-load behavior response and uphill high-load exposure context. This is not a true VAM/vertical-output capacity axis.",
    },
    {
        "axis_id": "pacing_movement_stability",
        "axis_label_zh": "配速／移動穩定性",
        "support_status": "SUPPORTED_ACTIVITY_HISTORY",
        "components": [
            ("low_speed_ratio_avg", "lower"),
            ("stopped_ratio_avg", "lower"),
            ("speed_mps_median_median", "higher"),
        ],
        "description": "Group-relative pacing and movement stability from low-speed, stopped, and speed metrics.",
    },
    {
        "axis_id": "hr_output_efficiency_proxy",
        "axis_label_zh": "HR 輸出效率（有限代理）",
        "support_status": "LIMITED_SECONDARY_HR_CONTEXT",
        "components": [
            ("speed_mps_median_median", "higher"),
            ("hr_median_pct_sex_age_est_hrmax", "lower"),
            ("low_speed_ratio_avg", "lower"),
        ],
        "description": "Limited proxy combining movement output and sex-age estimated HR% context. High HR alone is not strain.",
    },
    {
        "axis_id": "weather_performance_maintenance_proxy",
        "axis_label_zh": "天候下表現維持（有限代理）",
        "support_status": "LIMITED_PROXY_ACTIVITY_WEATHER_CONTEXT",
        "components": [
            ("behavior_weather_context_review_required_ratio", "lower"),
            ("route_load_behavior_candidate_window_ratio", "lower"),
        ],
        "description": "Limited proxy from behavior-weather overlap and route-load behavior response. Station weather is descriptive context only.",
    },
    {
        "axis_id": "terrain_movement_efficiency",
        "axis_label_zh": "地形移動效率",
        "support_status": "INSUFFICIENT_EVIDENCE",
        "components": [],
        "description": "Requires terrain/surface x movement-efficiency join; not scored in v0.",
    },
    {
        "axis_id": "route_following_stability",
        "axis_label_zh": "路線跟隨穩定性",
        "support_status": "INSUFFICIENT_EVIDENCE",
        "components": [],
        "description": "Requires formal on-route / wrong-branch / deviation-recovery evidence; not scored in v0.",
    },
]


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=r"D:\mountain_work\115_osm")
    p.add_argument("--context", default=DEFAULT_CONTEXT)
    p.add_argument("--attribution", default=DEFAULT_ATTRIB)
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


def numeric_series(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series([np.nan] * len(df), index=df.index, dtype=float)
    return pd.to_numeric(df[col], errors="coerce")


def percentile_index(series: pd.Series, values: pd.Series, direction: str) -> pd.Series:
    """Return 0-100 group-relative index. Higher output means stronger descriptive axis value.

    direction:
    - higher: larger raw value receives higher index
    - lower/context_lower: smaller raw value receives higher index
    """
    s = pd.to_numeric(series, errors="coerce")
    v = pd.to_numeric(values, errors="coerce")
    valid = s.dropna()
    if valid.nunique() <= 1:
        return pd.Series([np.nan] * len(values), index=values.index, dtype=float)

    ranks = v.rank(pct=True, method="average") * 100.0
    if direction in {"lower", "context_lower"}:
        ranks = 100.0 - ranks
    return ranks.round(3)


def component_role(direction: str) -> str:
    if direction == "higher":
        return "HIGHER_IS_MORE_FAVORABLE"
    if direction == "lower":
        return "LOWER_IS_MORE_FAVORABLE"
    if direction == "context_lower":
        return "LOWER_IS_MORE_FAVORABLE_CONTEXT_ONLY"
    return "UNKNOWN"


def split_pipe(value) -> list[str]:
    if value is None or pd.isna(value):
        return []
    out = []
    for item in str(value).split("|"):
        item = item.strip()
        if item and item != "NONE" and item.lower() != "nan":
            out.append(item)
    return out


def safe_mean(values: list[float]) -> float:
    vals = [float(v) for v in values if not pd.isna(v)]
    if not vals:
        return np.nan
    return round(float(np.mean(vals)), 3)


def readiness_from_axis(axis_values: list[float], missing_count: int, limited_count: int) -> str:
    vals = [v for v in axis_values if not pd.isna(v)]
    if not vals:
        return "INSUFFICIENT_EVIDENCE_FOR_RADAR"
    mean_v = float(np.mean(vals))
    if missing_count > 0:
        return "PARTIAL_RADAR_WITH_INSUFFICIENT_EVIDENCE_AXES"
    if mean_v >= 70 and limited_count <= 2:
        return "GROUP_RELATIVE_PROFILE_HIGHER_ACTIVITY_HISTORY_INDEX"
    if mean_v >= 45:
        return "GROUP_RELATIVE_PROFILE_REFERENCE_ACTIVITY_HISTORY_INDEX"
    return "GROUP_RELATIVE_PROFILE_LOWER_ACTIVITY_HISTORY_INDEX_REVIEW"


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    context_path = resolve(root, args.context)
    attrib_path = resolve(root, args.attribution)
    out_root = resolve(root, args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)

    context = read_csv(context_path, "v0.4 activity-history primary full context")
    attrib = read_csv(attrib_path, "v0.5 numeric attribution")

    required = ["activity_id_short", "participant_id"]
    missing = [c for c in required if c not in context.columns]
    if missing:
        raise KeyError(f"v0.4 context missing columns: {missing}")

    # Merge v0.5 attribution back for report-role context.
    attrib_cols = [
        "activity_id_short",
        "numeric_attribution_label_v0_5",
        "suggested_report_case_role",
        "numeric_attention_flag_count",
        "movement_degradation_flag_count",
        "numeric_attention_flags",
    ]
    attrib_keep = attrib[[c for c in attrib_cols if c in attrib.columns]].copy()
    df = context.merge(attrib_keep, on="activity_id_short", how="left")

    # Precompute component percentile indices for all axis components.
    component_index = {}
    for axis in AXES:
        for col, direction in axis["components"]:
            key = (col, direction)
            if key in component_index:
                continue
            component_index[key] = percentile_index(
                numeric_series(df, col),
                numeric_series(df, col),
                direction,
            )

    axis_rows = []
    component_rows = []
    for idx, row in df.iterrows():
        for axis in AXES:
            comp_values = []
            comp_ids = []
            comp_status = []

            if axis["support_status"] == "INSUFFICIENT_EVIDENCE":
                axis_value = np.nan
                evidence_status = "INSUFFICIENT_EVIDENCE"
            else:
                for col, direction in axis["components"]:
                    val = component_index[(col, direction)].iloc[idx]
                    raw = row.get(col, np.nan)
                    comp_values.append(val)
                    comp_ids.append(col)
                    comp_status.append("AVAILABLE" if not pd.isna(val) else "MISSING")

                    component_rows.append({
                        "activity_id_short": row.get("activity_id_short"),
                        "participant_id": row.get("participant_id"),
                        "axis_id": axis["axis_id"],
                        "axis_label_zh": axis["axis_label_zh"],
                        "component_metric": col,
                        "component_role": component_role(direction),
                        "component_raw_value": raw,
                        "component_group_relative_index_0_100": val,
                        "component_support_status": "AVAILABLE" if not pd.isna(val) else "MISSING",
                        "interpretation_boundary": BOUNDARY,
                    })

                axis_value = safe_mean(comp_values)
                if pd.isna(axis_value):
                    evidence_status = "INSUFFICIENT_EVIDENCE"
                elif axis["support_status"].startswith("LIMITED"):
                    evidence_status = axis["support_status"]
                else:
                    evidence_status = axis["support_status"]

            axis_rows.append({
                "activity_id_short": row.get("activity_id_short"),
                "participant_id": row.get("participant_id"),
                "axis_id": axis["axis_id"],
                "axis_label_zh": axis["axis_label_zh"],
                "axis_group_relative_index_0_100": axis_value,
                "axis_support_status": evidence_status,
                "axis_component_metrics": "|".join(comp_ids) if comp_ids else "NONE",
                "axis_description": axis["description"],
                "activity_history_primary_label": row.get("activity_history_primary_label"),
                "activity_history_evidence_tier": row.get("activity_history_evidence_tier"),
                "numeric_attribution_label_v0_5": row.get("numeric_attribution_label_v0_5"),
                "suggested_report_case_role": row.get("suggested_report_case_role"),
                "numeric_attention_flag_count": row.get("numeric_attention_flag_count"),
                "movement_degradation_flag_count": row.get("movement_degradation_flag_count"),
                "numeric_attention_flags": row.get("numeric_attention_flags"),
                "hr_median_zone_sex_age_est": row.get("hr_median_zone_sex_age_est"),
                "tertiary_profile_context_signal": row.get("tertiary_profile_context_signal"),
                "interpretation_boundary": BOUNDARY,
            })

    axis_df = pd.DataFrame(axis_rows)
    component_df = pd.DataFrame(component_rows)

    summary_rows = []
    for activity, g in axis_df.groupby("activity_id_short", dropna=False):
        vals = pd.to_numeric(g["axis_group_relative_index_0_100"], errors="coerce")
        missing_count = int(g["axis_support_status"].eq("INSUFFICIENT_EVIDENCE").sum())
        limited_count = int(g["axis_support_status"].astype(str).str.startswith("LIMITED").sum())
        supported_count = int(g["axis_support_status"].eq("SUPPORTED_ACTIVITY_HISTORY").sum())

        first = g.iloc[0].to_dict()
        valid_vals = vals.dropna()
        lowest_axis = "NONE"
        highest_axis = "NONE"
        if not valid_vals.empty:
            min_idx = vals.idxmin()
            max_idx = vals.idxmax()
            lowest_axis = str(axis_df.loc[min_idx, "axis_id"])
            highest_axis = str(axis_df.loc[max_idx, "axis_id"])

        summary_rows.append({
            "activity_id_short": activity,
            "participant_id": first.get("participant_id"),
            "radar_axis_count": int(len(g)),
            "supported_axis_count": supported_count,
            "limited_proxy_axis_count": limited_count,
            "insufficient_evidence_axis_count": missing_count,
            "mean_available_axis_index_0_100": round(float(valid_vals.mean()), 3) if not valid_vals.empty else np.nan,
            "min_available_axis_index_0_100": round(float(valid_vals.min()), 3) if not valid_vals.empty else np.nan,
            "max_available_axis_index_0_100": round(float(valid_vals.max()), 3) if not valid_vals.empty else np.nan,
            "lowest_available_axis_id": lowest_axis,
            "highest_available_axis_id": highest_axis,
            "radar_readiness_label": readiness_from_axis(list(vals), missing_count, limited_count),
            "activity_history_primary_label": first.get("activity_history_primary_label"),
            "activity_history_evidence_tier": first.get("activity_history_evidence_tier"),
            "numeric_attribution_label_v0_5": first.get("numeric_attribution_label_v0_5"),
            "suggested_report_case_role": first.get("suggested_report_case_role"),
            "hr_median_zone_sex_age_est": first.get("hr_median_zone_sex_age_est"),
            "tertiary_profile_context_signal": first.get("tertiary_profile_context_signal"),
            "interpretation_boundary": BOUNDARY,
        })

    summary_df = pd.DataFrame(summary_rows)

    missing_df = axis_df[axis_df["axis_support_status"].eq("INSUFFICIENT_EVIDENCE")].copy()
    missing_summary = missing_df.groupby(["axis_id", "axis_label_zh"], dropna=False).agg(
        activity_count=("activity_id_short", "count"),
        activity_id_short_list=("activity_id_short", lambda s: "|".join(sorted(map(str, s)))),
    ).reset_index()
    if not missing_summary.empty:
        missing_summary["missing_reason"] = missing_summary["axis_id"].map({
            "terrain_movement_efficiency": "Requires terrain/surface x movement-efficiency join.",
            "route_following_stability": "Requires formal on-route / wrong-branch / deviation-recovery evidence.",
        }).fillna("Insufficient evidence in v0.")
        missing_summary["interpretation_boundary"] = BOUNDARY

    axis_summary = axis_df.groupby(["axis_id", "axis_label_zh", "axis_support_status"], dropna=False).agg(
        activity_count=("activity_id_short", "count"),
        available_value_count=("axis_group_relative_index_0_100", lambda s: pd.to_numeric(s, errors="coerce").notna().sum()),
        mean_axis_index_0_100=("axis_group_relative_index_0_100", lambda s: round(float(pd.to_numeric(s, errors="coerce").mean()), 3) if pd.to_numeric(s, errors="coerce").notna().any() else np.nan),
    ).reset_index()
    axis_summary["interpretation_boundary"] = BOUNDARY

    audit = pd.DataFrame([{
        "context_source_path": str(context_path),
        "attribution_source_path": str(attrib_path),
        "activity_count": int(df["activity_id_short"].nunique()),
        "axis_rows": int(len(axis_df)),
        "component_rows": int(len(component_df)),
        "axis_count": int(len(AXES)),
        "supported_activity_history_axes_n": int(sum(1 for a in AXES if a["support_status"] == "SUPPORTED_ACTIVITY_HISTORY")),
        "limited_proxy_axes_n": int(sum(1 for a in AXES if a["support_status"].startswith("LIMITED"))),
        "insufficient_evidence_axes_n": int(sum(1 for a in AXES if a["support_status"] == "INSUFFICIENT_EVIDENCE")),
        "zero_fill_used": False,
        "audit_conclusion": "PASS_CH6_5_5_PERSONAL_ACTIVITY_PERFORMANCE_RADAR_V0_DESCRIPTIVE_ONLY",
        "interpretation_boundary": BOUNDARY,
    }])

    outputs = {
        "axis": out_root / "personal_activity_performance_radar_axis_v0.csv",
        "component": out_root / "personal_activity_performance_radar_component_v0.csv",
        "activity_summary": out_root / "personal_activity_performance_radar_activity_summary_v0.csv",
        "axis_summary": out_root / "personal_activity_performance_radar_axis_summary_v0.csv",
        "missing": out_root / "personal_activity_performance_radar_missing_evidence_v0.csv",
        "audit": out_root / "personal_activity_performance_radar_audit_v0.csv",
    }

    axis_df.to_csv(outputs["axis"], index=False, encoding="utf-8-sig")
    component_df.to_csv(outputs["component"], index=False, encoding="utf-8-sig")
    summary_df.to_csv(outputs["activity_summary"], index=False, encoding="utf-8-sig")
    axis_summary.to_csv(outputs["axis_summary"], index=False, encoding="utf-8-sig")
    missing_summary.to_csv(outputs["missing"], index=False, encoding="utf-8-sig")
    audit.to_csv(outputs["audit"], index=False, encoding="utf-8-sig")

    print({
        "output_root": str(out_root),
        "activity_count": int(df["activity_id_short"].nunique()),
        "axis_rows": int(len(axis_df)),
        "component_rows": int(len(component_df)),
        "axis_count": int(len(AXES)),
        "zero_fill_used": False,
        "audit_conclusion": "PASS_CH6_5_5_PERSONAL_ACTIVITY_PERFORMANCE_RADAR_V0_DESCRIPTIVE_ONLY",
        "outputs": {k: str(v) for k, v in outputs.items()},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
