#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CH6.5.5 pacing / movement stability axis admission audit v1.

Reviews whether pacing_movement_stability_axis_v1 can replace the previous
limited-proxy radar axis. This is descriptive admission evidence only.
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_AXIS_ROOT = "outputs/report_figures/ch6_5_5_pacing_movement_stability_axis_v1"
DEFAULT_OUTPUT_ROOT = "outputs/report_figures/ch6_5_5_pacing_movement_stability_axis_admission_audit_v1"

BOUNDARY = (
    "CH6.5.5 pacing / movement stability axis admission audit v1 is descriptive evidence only. "
    "It reviews whether the pacing_movement_stability v1 evidence layer can replace the previous "
    "limited proxy radar axis. It does not compute or authorize ability scores, ability ranks, "
    "ability classes, THCI scores, radar scores, final hiking risk scores, route suitability scores, "
    "go/no-go decisions, medical diagnoses, or causality claims."
)

AXIS_ID = "pacing_movement_stability"
AXIS_LABEL_ZH = "配速／移動穩定性"
PASS_DECISION = "ADMIT_TO_RADAR_V1_DESCRIPTIVE_SUPPORTED_AXIS_WITH_BOUNDARY"
REVIEW_DECISION = "REVIEW_REQUIRED_BEFORE_RADAR_REPLACEMENT"

REQUIRED_AXIS_FILES = [
    "pacing_movement_stability_axis_v1.csv",
    "pacing_movement_stability_component_v1.csv",
    "pacing_movement_stability_activity_summary_v1.csv",
    "pacing_movement_stability_audit_v1.csv",
    "pacing_movement_stability_window_evidence_v1.csv",
]

EXPECTED_COMPONENT_IDS = {
    "speed_variability_inverse_index",
    "low_speed_clustering_inverse_index",
    "stopped_clustering_inverse_index",
    "late_stage_degradation_inverse_index",
    "high_route_load_speed_maintenance_index",
}

GATES = [
    ("G01_AXIS_AUDIT_PASS", "Axis evidence audit conclusion passes"),
    ("G02_ROUTE_WINDOW_SOURCE", "Primary source is route-distance-window normalized evidence"),
    ("G03_REQUIRED_ROWS_PRESENT", "Window, activity, component, and axis rows are present"),
    ("G04_ACTIVITY_COVERAGE", "All expected activity rows are represented"),
    ("G05_COMPONENT_COVERAGE", "All activities have sufficient component evidence"),
    ("G06_HIGHER_IS_BETTER", "Axis and components are higher-is-better indices"),
    ("G07_NO_ZERO_FILL", "Missing component evidence is not zero-filled"),
    ("G08_BOUNDARY_FLAGS_CLEAN", "No prohibited score/rank/decision/causality outputs are generated"),
    ("G09_NON_DUPLICATIVE_EVIDENCE_DESIGN", "Axis uses variability/clustering/degradation/maintenance evidence"),
    ("G10_REVIEW_CASES_DIRECTIONAL_SANITY", "Low/high example activities align with component directions"),
    ("G11_SPARSE_COMPONENT_REVIEWED", "Sparse stopped-clustering component is explicitly reviewed and bounded"),
    ("G12_RADAR_REPLACEMENT_SCOPE", "Admission only replaces pacing_movement_stability, not route_following_stability"),
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=r"D:\mountain_work\115_osm")
    p.add_argument("--axis-root", default=DEFAULT_AXIS_ROOT)
    p.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    p.add_argument("--expected-activity-rows", type=int, default=25)
    p.add_argument("--min-supported-axis-rows", type=int, default=25)
    p.add_argument("--min-component-available-count", type=int, default=5)
    return p.parse_args()


def resolve(root: Path, path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else root / p


def read_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def as_float(value: Any, default: float = np.nan) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def scalar(df: pd.DataFrame, col: str, default: Any = "") -> Any:
    if df.empty or col not in df.columns:
        return default
    return df.iloc[0].get(col, default)


def pipe_join(values: list[str] | pd.Series) -> str:
    out: list[str] = []
    for value in values:
        if value is None or pd.isna(value):
            continue
        s = str(value).strip()
        if not s or s.upper() == "NONE":
            continue
        for part in s.split("|"):
            part = part.strip()
            if part and part.upper() != "NONE":
                out.append(part)
    return "|".join(sorted(set(out))) if out else "NONE"


def gate(gate_id: str, passed: bool, evidence: str) -> dict[str, Any]:
    label = dict(GATES)[gate_id]
    return {
        "gate_id": gate_id,
        "gate_label": label,
        "required": True,
        "gate_status": "PASS" if passed else "FAIL",
        "evidence": evidence,
        "interpretation_boundary": BOUNDARY,
    }


def directional_sanity(axis: pd.DataFrame, activity: pd.DataFrame) -> tuple[bool, str, pd.DataFrame]:
    a = axis.copy()
    a["_score"] = pd.to_numeric(a["axis_group_relative_index_0_100"], errors="coerce")
    low_ids = a.sort_values("_score").head(5)["activity_id_short"].astype(str).tolist()
    high_ids = a.sort_values("_score").tail(5)["activity_id_short"].astype(str).tolist()

    r = activity.copy()
    metric_cols = [
        "speed_cv_iqr_over_median",
        "low_speed_high_cluster_max_run_fraction",
        "stopped_cluster_max_run_fraction",
        "late_stage_speed_degradation_ratio",
        "high_route_load_speed_maintenance_ratio",
    ]
    for c in metric_cols:
        r[c] = pd.to_numeric(r[c], errors="coerce")

    low = r[r["activity_id_short"].astype(str).isin(low_ids)]
    high = r[r["activity_id_short"].astype(str).isin(high_ids)]

    rows = []
    lower_is_better = [
        "speed_cv_iqr_over_median",
        "low_speed_high_cluster_max_run_fraction",
        "stopped_cluster_max_run_fraction",
        "late_stage_speed_degradation_ratio",
    ]
    for c in lower_is_better:
        low_med = low[c].median()
        high_med = high[c].median()
        rows.append({
            "metric": c,
            "expected": "low_score_group_median >= high_score_group_median",
            "low_score_group_median": low_med,
            "high_score_group_median": high_med,
            "passes": bool(pd.notna(low_med) and pd.notna(high_med) and low_med >= high_med),
        })

    c = "high_route_load_speed_maintenance_ratio"
    low_med = low[c].median()
    high_med = high[c].median()
    rows.append({
        "metric": c,
        "expected": "high_score_group_median >= low_score_group_median",
        "low_score_group_median": low_med,
        "high_score_group_median": high_med,
        "passes": bool(pd.notna(low_med) and pd.notna(high_med) and high_med >= low_med),
    })

    review = pd.DataFrame(rows)
    pass_count = int(review["passes"].astype(bool).sum())
    passed = pass_count >= 4
    evidence = f"directional_sanity_passed={pass_count}/5; low_ids={pipe_join(low_ids)}; high_ids={pipe_join(high_ids)}"
    return passed, evidence, review


def sparse_stopped_review(component: pd.DataFrame) -> tuple[bool, str, pd.DataFrame]:
    s = component[component["component_id"].astype(str).eq("stopped_clustering_inverse_index")].copy()
    s["raw"] = pd.to_numeric(s["component_raw_value"], errors="coerce")
    n = len(s)
    zero_count = int(s["raw"].fillna(0).eq(0).sum())
    nonzero_count = int(s["raw"].fillna(0).gt(0).sum())
    zero_ratio = zero_count / n if n else np.nan
    review = pd.DataFrame([{
        "component_id": "stopped_clustering_inverse_index",
        "raw_metric": "stopped_cluster_max_run_fraction",
        "activity_rows": n,
        "zero_raw_value_count": zero_count,
        "nonzero_raw_value_count": nonzero_count,
        "zero_raw_value_ratio": zero_ratio,
        "review_note": (
            "Stopped clustering is sparse. It is acceptable as one bounded component in the composite, "
            "but must not be interpreted as a standalone stop/stall ability or safety score."
        ),
    }])
    return n > 0, f"stopped_component_rows={n}; zero_raw_value_ratio={zero_ratio:.3f}" if n else "stopped_component_missing", review


def write_html(path: Path, admission: pd.DataFrame, gates: pd.DataFrame, notes: pd.DataFrame,
               directional: pd.DataFrame, sparse: pd.DataFrame) -> None:
    def t(df: pd.DataFrame) -> str:
        cols = list(df.columns)
        parts = ["<table><thead><tr>"]
        parts.append("".join(f"<th>{html.escape(c)}</th>" for c in cols))
        parts.append("</tr></thead><tbody>")
        for _, row in df.iterrows():
            parts.append("<tr>" + "".join(f"<td>{html.escape('' if pd.isna(row[c]) else str(row[c]))}</td>" for c in cols) + "</tr>")
        parts.append("</tbody></table>")
        return "\n".join(parts)

    decision = str(admission.iloc[0]["axis_admission_decision"])
    body = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>CH6.5.5 Pacing Movement Stability Axis Admission Audit v1</title>
<style>
body {{ font-family: "Microsoft JhengHei", "Noto Sans TC", Arial, sans-serif; margin: 24px; line-height: 1.55; }}
.boundary {{ background: #fff7e6; border-left: 5px solid #d99000; padding: 12px 16px; }}
table {{ border-collapse: collapse; width: 100%; margin: 12px 0 24px 0; font-size: 13px; }}
th, td {{ border: 1px solid #ccc; padding: 6px 8px; vertical-align: top; }}
th {{ background: #f2f2f2; }}
code {{ background: #f4f4f4; padding: 2px 4px; }}
</style>
</head>
<body>
<h1>CH6.5.5 配速／移動穩定性軸 Admission Audit v1</h1>
<div class="boundary"><b>Boundary:</b> {html.escape(BOUNDARY)}</div>
<p><b>Decision:</b> <code>{html.escape(decision)}</code></p>
<h2>Admission Summary</h2>
{t(admission)}
<h2>Gate Detail</h2>
{t(gates)}
<h2>Context Notes</h2>
{t(notes)}
<h2>Directional Sanity Review</h2>
{t(directional)}
<h2>Sparse Component Review</h2>
{t(sparse)}
</body>
</html>
"""
    path.write_text(body, encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    axis_root = resolve(root, args.axis_root)
    output_root = resolve(root, args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    missing_files = [name for name in REQUIRED_AXIS_FILES if not (axis_root / name).exists()]
    if missing_files:
        raise FileNotFoundError(f"Missing required axis evidence files: {missing_files}")

    axis = read_csv(axis_root / "pacing_movement_stability_axis_v1.csv", "axis")
    component = read_csv(axis_root / "pacing_movement_stability_component_v1.csv", "component")
    activity = read_csv(axis_root / "pacing_movement_stability_activity_summary_v1.csv", "activity summary")
    audit = read_csv(axis_root / "pacing_movement_stability_audit_v1.csv", "axis audit")
    _window = read_csv(axis_root / "pacing_movement_stability_window_evidence_v1.csv", "window evidence")

    gate_rows = []

    axis_audit_pass = str(scalar(audit, "audit_conclusion")).strip() == "PASS_CH6_5_5_PACING_MOVEMENT_STABILITY_AXIS_V1_DESCRIPTIVE_ONLY"
    gate_rows.append(gate("G01_AXIS_AUDIT_PASS", axis_audit_pass, f"audit_conclusion={scalar(audit, 'audit_conclusion')}"))

    primary_input = str(scalar(audit, "primary_input_path"))
    route_window_source = "route_load_context_windows_v1.csv" in primary_input and "script_inputs" in primary_input
    gate_rows.append(gate("G02_ROUTE_WINDOW_SOURCE", route_window_source, f"primary_input_path={primary_input}"))

    required_rows = (
        int(as_float(scalar(audit, "window_rows"), 0)) > 0
        and int(as_float(scalar(audit, "activity_rows"), 0)) > 0
        and int(as_float(scalar(audit, "component_rows"), 0)) > 0
        and int(as_float(scalar(audit, "axis_rows"), 0)) > 0
    )
    gate_rows.append(gate(
        "G03_REQUIRED_ROWS_PRESENT",
        required_rows,
        f"window_rows={scalar(audit, 'window_rows')}; activity_rows={scalar(audit, 'activity_rows')}; component_rows={scalar(audit, 'component_rows')}; axis_rows={scalar(audit, 'axis_rows')}",
    ))

    activity_rows = int(axis["activity_id_short"].nunique())
    activity_coverage = activity_rows >= args.expected_activity_rows
    gate_rows.append(gate("G04_ACTIVITY_COVERAGE", activity_coverage, f"axis_activity_rows={activity_rows}; expected={args.expected_activity_rows}"))

    comp_count = pd.to_numeric(axis["component_available_count"], errors="coerce")
    supported_rows = int(axis["axis_support_status"].astype(str).eq("SUPPORTED_PACING_MOVEMENT_STABILITY_EVIDENCE").sum())
    component_coverage = supported_rows >= args.min_supported_axis_rows and comp_count.min() >= args.min_component_available_count
    gate_rows.append(gate(
        "G05_COMPONENT_COVERAGE",
        bool(component_coverage),
        f"supported_axis_rows={supported_rows}; min_component_available_count_observed={comp_count.min()}",
    ))

    axis_direction = axis["axis_direction"].astype(str).eq("higher_is_better").all()
    c_avail = component["component_available"].map(as_bool)
    c_index = pd.to_numeric(component["component_group_relative_index_0_100"], errors="coerce")
    comp_indices_valid = c_index[c_avail].notna().all()
    higher_is_better = bool(axis_direction and comp_indices_valid)
    gate_rows.append(gate("G06_HIGHER_IS_BETTER", higher_is_better, f"axis_direction_all_higher={axis_direction}; component_indices_valid={comp_indices_valid}"))

    no_zero_fill = not as_bool(scalar(audit, "zero_fill_used")) and not as_bool(scalar(audit, "weather_zero_fill_used"))
    gate_rows.append(gate("G07_NO_ZERO_FILL", no_zero_fill, f"zero_fill_used={scalar(audit, 'zero_fill_used')}; weather_zero_fill_used={scalar(audit, 'weather_zero_fill_used')}"))

    prohibited = [
        "ability_score_generated",
        "ability_rank_generated",
        "ability_class_generated",
        "radar_score_generated",
        "route_suitability_score_generated",
        "go_no_go_generated",
        "medical_diagnosis_generated",
        "causality_claim_generated",
    ]
    boundary_clean = all(not as_bool(scalar(audit, col)) for col in prohibited)
    gate_rows.append(gate("G08_BOUNDARY_FLAGS_CLEAN", boundary_clean, "; ".join(f"{col}={scalar(audit, col)}" for col in prohibited)))

    comp_ids = set(component["component_id"].astype(str))
    nondup = EXPECTED_COMPONENT_IDS.issubset(comp_ids)
    gate_rows.append(gate("G09_NON_DUPLICATIVE_EVIDENCE_DESIGN", nondup, f"components_present={pipe_join(sorted(EXPECTED_COMPONENT_IDS.intersection(comp_ids)))}"))

    directional_pass, directional_evidence, directional_review = directional_sanity(axis, activity)
    gate_rows.append(gate("G10_REVIEW_CASES_DIRECTIONAL_SANITY", directional_pass, directional_evidence))

    sparse_pass, sparse_evidence, sparse_review = sparse_stopped_review(component)
    gate_rows.append(gate("G11_SPARSE_COMPONENT_REVIEWED", sparse_pass, sparse_evidence))

    scope = axis["axis_id"].astype(str).eq(AXIS_ID).all() and not axis["axis_id"].astype(str).str.contains("route_following", case=False, na=False).any()
    gate_rows.append(gate("G12_RADAR_REPLACEMENT_SCOPE", bool(scope), "scope=replace pacing_movement_stability only; keep route_following_stability missing"))

    gates = pd.DataFrame(gate_rows)
    failed = gates.loc[gates["gate_status"].ne("PASS"), "gate_id"].astype(str).tolist()
    decision = PASS_DECISION if not failed else REVIEW_DECISION

    notes = pd.DataFrame([
        {
            "note_id": "DATA_SOURCE",
            "note": "Primary source is route-distance-window normalized evidence from the input pack.",
            "boundary": BOUNDARY,
        },
        {
            "note_id": "RADAR_REPLACEMENT",
            "note": "This admission applies only to replacing the pacing/movement stability proxy axis. It does not create route-following stability evidence.",
            "boundary": BOUNDARY,
        },
        {
            "note_id": "SPARSE_STOP_COMPONENT",
            "note": "Stopped clustering is sparse and should remain one bounded component in the composite, not a standalone interpretation.",
            "boundary": BOUNDARY,
        },
        {
            "note_id": "DIRECTION",
            "note": "All admitted component and axis values are higher-is-better group-relative descriptive indices.",
            "boundary": BOUNDARY,
        },
    ])

    admission = pd.DataFrame([{
        "axis_id": AXIS_ID,
        "axis_label_zh": AXIS_LABEL_ZH,
        "axis_admission_decision": decision,
        "recommended_replacement_axis_id": AXIS_ID,
        "recommended_replacement_axis_label_zh": AXIS_LABEL_ZH,
        "radar_update_recommendation": (
            "Use pacing_movement_stability_axis_v1.csv to replace the previous limited proxy pacing/movement stability radar axis. "
            "Do not use this evidence to fill route-following stability."
            if decision == PASS_DECISION else
            "Do not replace the radar axis until failed gates are resolved."
        ),
        "gate_pass_count": int(gates["gate_status"].eq("PASS").sum()),
        "gate_count": int(len(gates)),
        "failed_gate_ids": pipe_join(failed),
        "axis_root": str(axis_root),
        "output_root": str(output_root),
        "observed_activity_rows": activity_rows,
        "supported_axis_rows": supported_rows,
        "boundary": BOUNDARY,
    }])

    outputs = {
        "admission": output_root / "pacing_movement_stability_axis_admission_audit_v1.csv",
        "gate_detail": output_root / "pacing_movement_stability_axis_admission_gate_detail_v1.csv",
        "context_notes": output_root / "pacing_movement_stability_axis_admission_context_notes_v1.csv",
        "directional_review": output_root / "pacing_movement_stability_axis_directional_sanity_review_v1.csv",
        "sparse_component_review": output_root / "pacing_movement_stability_sparse_component_review_v1.csv",
        "report_md": output_root / "pacing_movement_stability_axis_admission_report_v1.md",
        "report_html": output_root / "pacing_movement_stability_axis_admission_report_v1.html",
    }

    admission.to_csv(outputs["admission"], index=False, encoding="utf-8-sig")
    gates.to_csv(outputs["gate_detail"], index=False, encoding="utf-8-sig")
    notes.to_csv(outputs["context_notes"], index=False, encoding="utf-8-sig")
    directional_review.to_csv(outputs["directional_review"], index=False, encoding="utf-8-sig")
    sparse_review.to_csv(outputs["sparse_component_review"], index=False, encoding="utf-8-sig")

    md = [
        "# CH6.5.5 Pacing Movement Stability Axis Admission Audit v1",
        "",
        f"- axis_id: `{AXIS_ID}`",
        f"- axis_label_zh: `{AXIS_LABEL_ZH}`",
        f"- decision: `{decision}`",
        f"- gate_pass_count: {int(gates['gate_status'].eq('PASS').sum())}",
        f"- gate_count: {len(gates)}",
        f"- failed_gate_ids: `{pipe_join(failed)}`",
        "",
        "## Boundary",
        "",
        BOUNDARY,
        "",
        "## Recommendation",
        "",
        str(admission.iloc[0]["radar_update_recommendation"]),
        "",
        "## Notes",
        "",
        "- This admission replaces only the pacing/movement stability proxy axis.",
        "- It does not fill the route-following stability missing-evidence axis.",
        "- Stopped clustering is sparse and must remain a bounded component.",
    ]
    outputs["report_md"].write_text("\n".join(md) + "\n", encoding="utf-8")
    write_html(outputs["report_html"], admission, gates, notes, directional_review, sparse_review)

    print({
        "output_root": str(output_root),
        "axis_admission_decision": decision,
        "gate_pass_count": int(gates["gate_status"].eq("PASS").sum()),
        "gate_count": int(len(gates)),
        "failed_gate_ids": pipe_join(failed),
        "supported_axis_rows": supported_rows,
        "observed_activity_rows": activity_rows,
        "outputs": {k: str(v) for k, v in outputs.items()},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
