#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CH6.5.6 terrain movement efficiency axis admission audit v1.2.

This is a governance/admission audit for deciding whether the CH6.5.6
terrain movement efficiency evidence can enter the next personal activity
performance radar revision.

It is descriptive-only and does not compute or authorize:
- ability scores, ranks, or classes
- THCI scores
- radar scores
- final hiking risk scores
- route suitability scores
- go/no-go decisions
- medical diagnoses
- causality claims
"""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_EVIDENCE_ROOT = "outputs/report_figures/ch6_5_6_terrain_movement_efficiency_evidence_v1"
DEFAULT_UPSTREAM_ROOT = "outputs/report_figures/ch6_5_route_load_context_index_v1"
DEFAULT_OUTPUT_ROOT = "outputs/report_figures/ch6_5_6_terrain_movement_efficiency_axis_admission_audit_v1_2"

EXPECTED_ACTIVITY_COUNT = 25
MIN_CONTEXT_GROUP_WINDOWS = 20

BOUNDARY = (
    "CH6.5.6 terrain movement efficiency axis admission audit is governance review only. "
    "It decides whether a descriptive evidence axis may enter the next radar revision. "
    "It does not compute or authorize ability scores, ability ranks, ability classes, "
    "THCI scores, radar scores, final hiking risk scores, route suitability scores, "
    "go/no-go decisions, medical diagnoses, or causality claims."
)

RADAR_BOUNDARY = (
    "If admitted, the axis may replace the previous missing-evidence terrain movement "
    "efficiency axis in the next radar revision as descriptive terrain movement maintenance "
    "context only. Route-following stability remains missing until separate on-route / "
    "wrong-branch / deviation-recovery evidence is available."
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=r"D:\mountain_work\115_osm")
    p.add_argument("--evidence-root", default=DEFAULT_EVIDENCE_ROOT)
    p.add_argument("--upstream-root", default=DEFAULT_UPSTREAM_ROOT)
    p.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    p.add_argument("--expected-activity-count", type=int, default=EXPECTED_ACTIVITY_COUNT)
    p.add_argument("--min-context-group-windows", type=int, default=MIN_CONTEXT_GROUP_WINDOWS)
    return p.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    p = Path(value)
    return p if p.is_absolute() else root / p


def read_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def first(df: pd.DataFrame, col: str, default: Any = "") -> Any:
    if col not in df.columns or len(df) == 0:
        return default
    return df.iloc[0].get(col, default)


def b(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def i(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except Exception:
        return default


def f(value: Any, default: float = np.nan) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def has(text: str, pattern: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE) is not None


def status(cond: bool) -> str:
    return "PASS" if cond else "FAIL"


def pipe_join(values) -> str:
    out = []
    for value in values:
        if value is None or pd.isna(value):
            continue
        for p in str(value).split("|"):
            p = p.strip()
            if p and p.upper() != "NONE":
                out.append(p)
    return "|".join(sorted(set(out))) if out else "NONE"


def make_gate(gate_id: str, gate_name: str, cond: bool, observed: str, required: str, notes: str) -> dict:
    return {
        "gate_id": gate_id,
        "gate_status": status(cond),
        "gate_name": gate_name,
        "observed_value": observed,
        "required_value": required,
        "notes": notes,
    }


def build_gates(
    evidence_audit: pd.DataFrame,
    activity_summary: pd.DataFrame,
    axis_update: pd.DataFrame,
    context_summary: pd.DataFrame,
    upstream_docs: str,
    expected_activity_count: int,
    min_context_group_windows: int,
) -> pd.DataFrame:
    audit_conclusion = str(first(evidence_audit, "audit_conclusion"))
    zero_fill_used = b(first(evidence_audit, "zero_fill_used", False))
    weather_zero_fill_used = b(first(evidence_audit, "weather_zero_fill_used", False))
    audit_issues = str(first(evidence_audit, "audit_issues", "NONE"))

    forbidden_flags = {
        "ability_score_generated": b(first(evidence_audit, "ability_score_generated", False)),
        "ability_rank_generated": b(first(evidence_audit, "ability_rank_generated", False)),
        "ability_class_generated": b(first(evidence_audit, "ability_class_generated", False)),
        "route_suitability_score_generated": b(first(evidence_audit, "route_suitability_score_generated", False)),
        "go_no_go_generated": b(first(evidence_audit, "go_no_go_generated", False)),
    }

    activity_rows = i(first(evidence_audit, "activity_rows", len(activity_summary)), len(activity_summary))
    axis_rows = i(first(evidence_audit, "axis_update_rows", len(axis_update)), len(axis_update))
    supported = i(first(evidence_audit, "supported_axis_rows", 0))
    limited = i(first(evidence_audit, "limited_axis_rows", 0))
    insufficient = i(first(evidence_audit, "insufficient_axis_rows", 0))

    context_counts = pd.to_numeric(context_summary.get("window_count", pd.Series(dtype=float)), errors="coerce")
    min_context_count = f(context_counts.min()) if context_counts.notna().any() else np.nan

    axis_values = pd.to_numeric(
        axis_update.get("terrain_movement_efficiency_axis_index_0_100", pd.Series(dtype=float)),
        errors="coerce",
    )
    axis_unique = int(axis_values.dropna().nunique())
    axis_min = f(axis_values.min()) if axis_values.notna().any() else np.nan
    axis_max = f(axis_values.max()) if axis_values.notna().any() else np.nan

    labels = set(activity_summary.get("terrain_movement_context_label", pd.Series(dtype=str)).dropna().astype(str))
    required_labels = {
        "LOWER_TERRAIN_MOVEMENT_MAINTENANCE_CONTEXT_REVIEW",
        "REFERENCE_TERRAIN_MOVEMENT_MAINTENANCE_CONTEXT",
        "HIGHER_TERRAIN_MOVEMENT_MAINTENANCE_CONTEXT",
    }

    # v1.2 provenance rule:
    # Use combined run_report + CURRENT_INDEX + README text. The run report may not
    # contain the literal string "50 m", but CURRENT_INDEX/README can establish
    # route-window evidence. The source inventory from CH6.5.6 also proves the
    # effective window CSV.
    source_inventory = str(first(evidence_audit, "source_inventory", ""))
    input_path = str(first(evidence_audit, "input_path", ""))
    upstream_input_found = (
        has(upstream_docs, r"activity_route_load_behavior_response_windows\.csv")
        or "activity_route_load_behavior_response_windows.csv" in source_inventory
    )
    route_window_found = (
        has(upstream_docs, r"50\s*m|50m|50 m route-window|per-activity 50 m route-window|route-window|route_load_context_windows_v1\.csv")
        or "route_load_context_windows_v1.csv" in input_path
        or "route_load_context_windows_v1.csv" in source_inventory
    )

    upstream_factors = (
        has(upstream_docs, r"vertical range")
        and has(upstream_docs, r"slope")
        and has(upstream_docs, r"IB2 effort")
        and has(upstream_docs, r"IB2 terrain")
        and has(upstream_docs, r"near-steps|steps")
    )
    weather_boundary = (
        has(upstream_docs, r"Weather context is descriptive only")
        and has(upstream_docs, r"not included in the index|not used to compute")
        and has(upstream_docs, r"No weather zero-fill|not filled as zero")
    )
    non_score_boundary = (
        has(upstream_docs, r"descriptive")
        and has(upstream_docs, r"ability score")
        and has(upstream_docs, r"ability rank")
        and has(upstream_docs, r"final hiking risk score")
    )

    gates = [
        make_gate(
            "G01", "CH6.5.6 audit conclusion is PASS",
            audit_conclusion == "PASS_CH6_5_6_TERRAIN_MOVEMENT_EFFICIENCY_EVIDENCE_V1_DESCRIPTIVE_ONLY",
            audit_conclusion,
            "PASS_CH6_5_6_TERRAIN_MOVEMENT_EFFICIENCY_EVIDENCE_V1_DESCRIPTIVE_ONLY",
            "Evidence layer must pass before radar admission.",
        ),
        make_gate(
            "G02", "No zero-fill used",
            (not zero_fill_used) and (not weather_zero_fill_used),
            f"zero_fill_used={zero_fill_used}; weather_zero_fill_used={weather_zero_fill_used}",
            "Both False",
            "Missing evidence must not become zero, no-rain, normal, calm, or safe evidence.",
        ),
        make_gate(
            "G03", "No forbidden scoring / decision output",
            not any(forbidden_flags.values()),
            "; ".join(f"{k}={v}" for k, v in forbidden_flags.items()),
            "All False",
            "Admission does not authorize scoring, ranking, suitability, or go/no-go output.",
        ),
        make_gate(
            "G04", "Audit issues are none",
            audit_issues in {"", "NONE", "nan"},
            audit_issues,
            "NONE",
            "Any audit issue must be resolved before admission.",
        ),
        make_gate(
            "G05", "Expected activity coverage",
            activity_rows == expected_activity_count and axis_rows == expected_activity_count,
            f"activity_rows={activity_rows}; axis_update_rows={axis_rows}",
            f"{expected_activity_count} activity rows and {expected_activity_count} axis rows",
            "Radar axis should cover the current full25 activity set.",
        ),
        make_gate(
            "G06", "All rows have supported terrain movement evidence",
            supported == expected_activity_count and limited == 0 and insufficient == 0,
            f"supported={supported}; limited={limited}; insufficient={insufficient}",
            f"supported={expected_activity_count}; limited=0; insufficient=0",
            "This admits the axis as supported for the current activity set.",
        ),
        make_gate(
            "G07", "Context groups meet minimum window threshold",
            pd.notna(min_context_count) and min_context_count >= min_context_group_windows,
            f"context_group_count={len(context_summary)}; min_window_count={min_context_count}",
            f"Each context group >= {min_context_group_windows} windows",
            "Small groups remain caution notes, but are acceptable if above threshold.",
        ),
        make_gate(
            "G08", "Axis index has useful variation",
            axis_unique >= 5 and pd.notna(axis_min) and pd.notna(axis_max) and 0 <= axis_min <= axis_max <= 100,
            f"unique_n={axis_unique}; min={axis_min}; max={axis_max}",
            ">=5 unique values within 0-100",
            "Radar axis should not be flat or out of range.",
        ),
        make_gate(
            "G09", "Lower/reference/higher labels all appear",
            required_labels.issubset(labels),
            pipe_join(sorted(labels)),
            "Contains lower, reference, and higher context labels",
            "Labels support interpretation; they are not ability classes.",
        ),
        make_gate(
            "G10", "Upstream provenance is documented",
            upstream_input_found and route_window_found,
            f"input_found={upstream_input_found}; route_window_found={route_window_found}",
            "full25 input and route-window evidence documented",
            "v1.2 checks run report, CURRENT_INDEX, README, and CH6.5.6 source inventory.",
        ),
        make_gate(
            "G11", "Upstream route/terrain/map-derived factors are documented",
            upstream_factors,
            f"route_terrain_factor_docs={upstream_factors}",
            "vertical range, slope, IB2 effort, IB2 terrain, near-steps",
            "Axis must be grounded in terrain/surface context, not only speed.",
        ),
        make_gate(
            "G12", "Weather boundary is documented",
            weather_boundary,
            f"weather_boundary_docs={weather_boundary}",
            "weather descriptive only, not included in index, no zero-fill",
            "Weather context cannot be hidden route-load or ability evidence.",
        ),
        make_gate(
            "G13", "Upstream non-score boundary is documented",
            non_score_boundary,
            f"upstream_boundary_docs={non_score_boundary}",
            "descriptive and not score/rank/final risk",
            "The radar admission inherits the same non-scoring boundary.",
        ),
    ]

    return pd.DataFrame(gates)


def build_notes(context_summary: pd.DataFrame, activity_summary: pd.DataFrame) -> pd.DataFrame:
    notes = []
    for _, r in context_summary.iterrows():
        group = str(r.get("terrain_surface_context_group", ""))
        wc = i(r.get("window_count", 0))
        ac = i(r.get("activity_count", 0))
        if group == "HIGH_ROUTE_LOAD_OR_SLOPE_CONTEXT":
            note_type = "SMALL_CONTEXT_GROUP_CAUTION"
            note = "Smallest context group. It passes the minimum window threshold but should be reported with caution."
        elif group == "STEPS_CONTEXT":
            note_type = "ROUTE_CHARACTERISTIC_NOTE"
            note = "Dominant route context; consistent with step/stair-heavy route sections. Not ability evidence by itself."
        else:
            note_type = "REFERENCE_CONTEXT_NOTE"
            note = "Mixed or lower-information context retained for descriptive comparison."
        notes.append({
            "note_id": f"CONTEXT_{group}",
            "note_type": note_type,
            "subject": group,
            "window_count": wc,
            "activity_count": ac,
            "note": note,
            "interpretation_boundary": BOUNDARY,
        })

    label_summary = activity_summary.groupby("terrain_movement_context_label", dropna=False).agg(
        activity_count=("activity_id_short", "count"),
        activity_id_short_list=("activity_id_short", lambda s: "|".join(map(str, sorted(s)))),
    ).reset_index()

    for _, r in label_summary.iterrows():
        notes.append({
            "note_id": f"LABEL_{r['terrain_movement_context_label']}",
            "note_type": "ACTIVITY_LABEL_DISTRIBUTION",
            "subject": r["terrain_movement_context_label"],
            "window_count": "",
            "activity_count": i(r["activity_count"]),
            "note": f"Activities: {r['activity_id_short_list']}. Label is descriptive group-relative context, not ability class.",
            "interpretation_boundary": BOUNDARY,
        })

    notes.append({
        "note_id": "RADAR_UPDATE_RECOMMENDATION",
        "note_type": "RADAR_GOVERNANCE",
        "subject": "terrain_movement_efficiency",
        "window_count": "",
        "activity_count": "",
        "note": RADAR_BOUNDARY,
        "interpretation_boundary": BOUNDARY,
    })
    return pd.DataFrame(notes)


def build_admission(
    evidence_root: Path,
    upstream_root: Path,
    output_root: Path,
    evidence_audit: pd.DataFrame,
    activity_summary: pd.DataFrame,
    axis_update: pd.DataFrame,
    context_summary: pd.DataFrame,
    gates: pd.DataFrame,
) -> pd.DataFrame:
    failed = gates[gates["gate_status"] != "PASS"]
    decision = (
        "ADMIT_TO_RADAR_V1_DESCRIPTIVE_SUPPORTED_AXIS_WITH_BOUNDARY"
        if failed.empty
        else "REVIEW_REQUIRED_BEFORE_RADAR_ADMISSION"
    )

    lower_ids = activity_summary.loc[
        activity_summary["terrain_movement_context_label"].astype(str)
        .eq("LOWER_TERRAIN_MOVEMENT_MAINTENANCE_CONTEXT_REVIEW"),
        "activity_id_short",
    ].astype(str).sort_values().tolist()
    higher_ids = activity_summary.loc[
        activity_summary["terrain_movement_context_label"].astype(str)
        .eq("HIGHER_TERRAIN_MOVEMENT_MAINTENANCE_CONTEXT"),
        "activity_id_short",
    ].astype(str).sort_values().tolist()

    return pd.DataFrame([{
        "evidence_root": str(evidence_root),
        "upstream_route_load_root": str(upstream_root),
        "output_root": str(output_root),
        "source_input_path": str(first(evidence_audit, "input_path")),
        "source_inventory": str(first(evidence_audit, "source_inventory")),
        "ch6_5_6_audit_conclusion": str(first(evidence_audit, "audit_conclusion")),
        "gate_count": int(len(gates)),
        "gate_pass_count": int((gates["gate_status"] == "PASS").sum()),
        "gate_fail_count": int(len(failed)),
        "failed_gate_ids": pipe_join(failed["gate_id"].tolist()),
        "activity_rows": int(len(activity_summary)),
        "axis_update_rows": int(len(axis_update)),
        "context_group_rows": int(len(context_summary)),
        "lower_context_review_activity_ids": "|".join(lower_ids),
        "higher_context_activity_ids": "|".join(higher_ids),
        "recommended_axis_id": "terrain_movement_efficiency",
        "recommended_axis_label_zh": "地形移動維持（描述性）",
        "axis_admission_decision": decision,
        "radar_update_recommendation": (
            "Use terrain_movement_efficiency_axis_update_v1.csv to replace the previous missing-evidence "
            "terrain movement efficiency axis in the next radar revision. Keep route-following stability missing "
            "until separate route-following evidence exists."
            if failed.empty else
            "Do not update radar until failed gates are reviewed."
        ),
        "zero_fill_used": False,
        "ability_score_generated": False,
        "ability_rank_generated": False,
        "ability_class_generated": False,
        "radar_score_generated": False,
        "route_suitability_score_generated": False,
        "go_no_go_generated": False,
        "medical_diagnosis_generated": False,
        "causality_claim_generated": False,
        "interpretation_boundary": BOUNDARY,
    }])


def write_md(path: Path, admission: pd.DataFrame, gates: pd.DataFrame, notes: pd.DataFrame) -> None:
    a = admission.iloc[0].to_dict()
    lines = [
        "# CH6.5.6 Terrain Movement Efficiency Axis Admission Audit v1.2",
        "",
        f"- axis_admission_decision: `{a['axis_admission_decision']}`",
        f"- recommended_axis_id: `{a['recommended_axis_id']}`",
        f"- recommended_axis_label_zh: `{a['recommended_axis_label_zh']}`",
        f"- gate_pass_count: `{a['gate_pass_count']}` / `{a['gate_count']}`",
        f"- failed_gate_ids: `{a['failed_gate_ids']}`",
        f"- source_input_path: `{a['source_input_path']}`",
        "",
        "## Boundary",
        "",
        BOUNDARY,
        "",
        "## Radar Update Recommendation",
        "",
        str(a["radar_update_recommendation"]),
        "",
        RADAR_BOUNDARY,
        "",
        "## Gate Detail",
        "",
        "| gate_id | gate_status | gate_name | observed_value | required_value | notes |",
        "|---|---|---|---|---|---|",
    ]
    for _, r in gates.iterrows():
        vals = [str(r[c]).replace("|", "\\|") for c in ["gate_id", "gate_status", "gate_name", "observed_value", "required_value", "notes"]]
        lines.append("| " + " | ".join(vals) + " |")
    lines += ["", "## Context Notes", "", "| note_id | note_type | subject | window_count | activity_count | note |", "|---|---|---|---|---|---|"]
    for _, r in notes.iterrows():
        vals = [str(r.get(c, "")).replace("|", "\\|") for c in ["note_id", "note_type", "subject", "window_count", "activity_count", "note"]]
        lines.append("| " + " | ".join(vals) + " |")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_html(path: Path, md_path: Path, admission: pd.DataFrame, gates: pd.DataFrame, notes: pd.DataFrame) -> None:
    a = admission.iloc[0].to_dict()

    def table(df: pd.DataFrame, cols: list[str]) -> str:
        rows = ["<table><thead><tr>" + "".join(f"<th>{html.escape(c)}</th>" for c in cols) + "</tr></thead><tbody>"]
        for _, r in df[cols].iterrows():
            rows.append("<tr>" + "".join(f"<td>{html.escape('' if pd.isna(r[c]) else str(r[c]))}</td>" for c in cols) + "</tr>")
        rows.append("</tbody></table>")
        return "\n".join(rows)

    text = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>CH6.5.6 Axis Admission Audit v1.2</title>
<style>
body {{ font-family: "Microsoft JhengHei", "Noto Sans TC", Arial, sans-serif; margin: 24px; line-height: 1.55; }}
.decision {{ background: #eef8ee; border-left: 5px solid #2f8f2f; padding: 12px 16px; margin-bottom: 20px; }}
.boundary {{ background: #fff7e6; border-left: 5px solid #d99000; padding: 12px 16px; margin-bottom: 20px; }}
table {{ border-collapse: collapse; width: 100%; margin: 12px 0 24px 0; font-size: 13px; }}
th, td {{ border: 1px solid #ccc; padding: 6px 8px; vertical-align: top; }}
th {{ background: #f2f2f2; }}
code {{ background: #f4f4f4; padding: 2px 4px; border-radius: 4px; }}
</style>
</head>
<body>
<h1>CH6.5.6 地形移動效率軸 admission audit v1.2</h1>
<div class="decision">
<b>Decision:</b> <code>{html.escape(str(a['axis_admission_decision']))}</code><br>
<b>Recommended axis:</b> <code>{html.escape(str(a['recommended_axis_label_zh']))}</code><br>
<b>Gate pass:</b> {html.escape(str(a['gate_pass_count']))} / {html.escape(str(a['gate_count']))}
</div>
<div class="boundary"><b>Boundary:</b> {html.escape(BOUNDARY)}</div>
<p><b>Markdown report:</b> <code>{html.escape(str(md_path))}</code></p>
<h2>Radar Update Recommendation</h2>
<p>{html.escape(str(a['radar_update_recommendation']))}</p>
<p>{html.escape(RADAR_BOUNDARY)}</p>
<h2>Gate Detail</h2>
{table(gates, ["gate_id", "gate_status", "gate_name", "observed_value", "required_value", "notes"])}
<h2>Context Notes</h2>
{table(notes, ["note_id", "note_type", "subject", "window_count", "activity_count", "note"])}
</body>
</html>
"""
    path.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    evidence_root = resolve(root, args.evidence_root)
    upstream_root = resolve(root, args.upstream_root)
    output_root = resolve(root, args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    evidence_audit = read_csv(evidence_root / "terrain_movement_efficiency_audit_v1.csv", "CH6.5.6 audit")
    activity_summary = read_csv(evidence_root / "terrain_movement_efficiency_activity_summary_v1.csv", "CH6.5.6 activity summary")
    axis_update = read_csv(evidence_root / "terrain_movement_efficiency_axis_update_v1.csv", "CH6.5.6 axis update")
    context_summary = read_csv(evidence_root / "terrain_movement_efficiency_context_group_summary_v1.csv", "CH6.5.6 context summary")

    upstream_doc_paths = [
        upstream_root / "route_load_context_index_run_report_v1.md",
        root / "runs" / "CURRENT_INDEX_updated_20260617_ch6_5_route_load_context_index_v1.md",
        root / "scripts" / "README_current_pipeline_updated_20260617_ch6_5_route_load_context_index_v1.md",
    ]
    upstream_docs = "\n".join(read_text_if_exists(p) for p in upstream_doc_paths)

    gates = build_gates(
        evidence_audit,
        activity_summary,
        axis_update,
        context_summary,
        upstream_docs,
        expected_activity_count=args.expected_activity_count,
        min_context_group_windows=args.min_context_group_windows,
    )
    notes = build_notes(context_summary, activity_summary)
    admission = build_admission(evidence_root, upstream_root, output_root, evidence_audit, activity_summary, axis_update, context_summary, gates)

    outputs = {
        "admission_audit": output_root / "terrain_movement_efficiency_axis_admission_audit_v1_2.csv",
        "gate_detail": output_root / "terrain_movement_efficiency_axis_admission_gate_detail_v1_2.csv",
        "context_notes": output_root / "terrain_movement_efficiency_axis_admission_context_notes_v1_2.csv",
        "markdown_report": output_root / "terrain_movement_efficiency_axis_admission_report_v1_2.md",
        "html_report": output_root / "terrain_movement_efficiency_axis_admission_report_v1_2.html",
    }

    admission.to_csv(outputs["admission_audit"], index=False, encoding="utf-8-sig")
    gates.to_csv(outputs["gate_detail"], index=False, encoding="utf-8-sig")
    notes.to_csv(outputs["context_notes"], index=False, encoding="utf-8-sig")
    write_md(outputs["markdown_report"], admission, gates, notes)
    write_html(outputs["html_report"], outputs["markdown_report"], admission, gates, notes)

    a = admission.iloc[0]
    print({
        "output_root": str(output_root),
        "axis_admission_decision": str(a["axis_admission_decision"]),
        "recommended_axis_label_zh": str(a["recommended_axis_label_zh"]),
        "gate_pass_count": int(a["gate_pass_count"]),
        "gate_count": int(a["gate_count"]),
        "gate_fail_count": int(a["gate_fail_count"]),
        "failed_gate_ids": str(a["failed_gate_ids"]),
        "outputs": {k: str(v) for k, v in outputs.items()},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
