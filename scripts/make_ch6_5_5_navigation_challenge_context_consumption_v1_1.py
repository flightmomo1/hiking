#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CH6.5.5 navigation challenge context consumption v1_1

Consumes the upstream IB1 route topology node-degree generator output and creates
route/activity-level navigation-challenge exposure context for route-following
interpretation only.

Boundary:
- This is context/source consumption only.
- It does not create a personal ability axis.
- It does not create ability scores, ranks, classes, radar scores, final hiking
  risk scores, route suitability scores, go/no-go decisions, medical diagnoses,
  or causal claims.
- It does not modify existing CH6.5 axis contract, data table, or radar outputs.
"""
from __future__ import annotations

import csv
import html
import json
import math
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

VERSION = "v1_1"
PROJECT_ROOT = Path.cwd()
TOPO_ROOT = PROJECT_ROOT / "outputs" / "report_figures" / "ib1_route_topology_generator_node_degree_v1_1"
OUT_ROOT = PROJECT_ROOT / "outputs" / "report_figures" / "ch6_5_5_navigation_challenge_context_consumption_v1_1"

BOUNDARY = (
    "Navigation-challenge exposure context consumption only. Not a personal ability axis, "
    "ability score, rank, class, radar score, final hiking risk score, route suitability "
    "score, go/no-go decision, medical diagnosis, or causal claim."
)

KNOWN_CASE_ALIASES = {
    "juansi_waterfall": ["juansi_waterfall", "juansi"],
    "qixing_lengshuikeng": ["qixing_lengshuikeng", "lengshuikeng_main_peak", "冷水坑"],
    "qixing_lengshuikeng_xiaoyoukeng": ["qixing_lengshuikeng_xiaoyoukeng", "lengshuikeng_xiaoyoukeng"],
    "qixing_xiaoyoukeng": ["qixing_xiaoyoukeng", "xiaoyoukeng_main_peak", "小油坑"],
    "zhonghua_ust_jiuwufeng": ["zhonghua_ust_jiuwufeng", "jiuwufeng", "中華", "九五峰"],
}

PREFERRED_ACTIVITY_TABLES = [
    PROJECT_ROOT / "outputs" / "report_figures" / "ch6_5_5_route_following_data_table_patch_v1" / "personal_ability_radar_data_table_v1_1.csv",
    PROJECT_ROOT / "outputs" / "report_figures" / "ch6_5_5_personal_ability_radar_plot_v1_1" / "personal_ability_radar_plot_ready_table_v1_1.csv",
    PROJECT_ROOT / "outputs" / "report_figures" / "ch6_5_5_route_following_data_table_patch_v1" / "personal_ability_radar_data_table_patch_v1.csv",
]

FORBIDDEN_TERMS = [
    "ability_score",
    "ability_rank",
    "ability_class",
    "radar_score",
    "final_hiking_risk_score",
    "route_suitability_score",
    "go_no_go_decision",
    "medical_diagnosis",
    "causal_claim",
]

# Activities that are known extra/source-only records and must not be consumed
# into CH6.5.5 route-following navigation context. Keep them out rather than
# assigning default route context.
EXCLUDED_ACTIVITY_IDS = {"6_1"}



def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_csv_if_exists(path: Path, **kwargs) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str, keep_default_na=False, low_memory=False, **kwargs)


def to_float(value, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None:
            return default
        text = str(value).strip()
        if text == "" or text.lower() in {"nan", "none", "null"}:
            return default
        return float(text)
    except Exception:
        return default


def to_int(value, default: int = 0) -> int:
    f = to_float(value, None)
    if f is None or not math.isfinite(f):
        return default
    return int(round(f))


def is_true(value) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y", "t"}


def normalize_case_id(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    low = text.lower().replace("\\", "/")
    # Order matters: qixing_lengshuikeng_xiaoyoukeng must be checked before qixing_lengshuikeng.
    order = [
        "qixing_lengshuikeng_xiaoyoukeng",
        "qixing_lengshuikeng",
        "qixing_xiaoyoukeng",
        "zhonghua_ust_jiuwufeng",
        "juansi_waterfall",
    ]
    for case in order:
        for alias in KNOWN_CASE_ALIASES[case]:
            if alias.lower() in low:
                return case
    return text


def compact_num(value: Optional[float], digits: int = 6) -> str:
    if value is None or not math.isfinite(value):
        return ""
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.{digits}f}".rstrip("0").rstrip(".")


def write_csv(path: Path, rows: List[Dict], fieldnames: Optional[List[str]] = None) -> None:
    ensure_dir(path.parent)
    if fieldnames is None:
        keys: List[str] = []
        seen = set()
        for row in rows:
            for key in row.keys():
                if key not in seen:
                    seen.add(key)
                    keys.append(key)
        fieldnames = keys
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def scan_forbidden_field_names(paths: Sequence[Path]) -> str:
    hits = set()
    for path in paths:
        if not path.exists() or path.suffix.lower() != ".csv":
            continue
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.reader(f)
                header = next(reader, [])
        except Exception:
            continue
        for col in header:
            c = str(col).strip().lower()
            if c.startswith("not_") or c in {"interpretation_boundary", "boundary"}:
                continue
            for term in FORBIDDEN_TERMS:
                if term in c:
                    hits.add(c)
    return "NONE" if not hits else "|".join(sorted(hits))


def build_route_context() -> Tuple[pd.DataFrame, List[Dict]]:
    dp_path = TOPO_ROOT / "route_topology_decision_points_v1_1.csv"
    route_summary_path = TOPO_ROOT / "route_topology_route_summary_v1_1.csv"
    route_sources_path = TOPO_ROOT / "route_topology_route_sources_v1_1.csv"

    dp = read_csv_if_exists(dp_path)
    if dp.empty:
        return pd.DataFrame(), []

    if "case_id" not in dp.columns:
        raise RuntimeError(f"Missing case_id in {dp_path}")
    if "mainline_route_dist_m" not in dp.columns:
        raise RuntimeError(f"Missing mainline_route_dist_m in {dp_path}")

    dp = dp.copy()
    dp["case_id_norm"] = dp["case_id"].map(normalize_case_id)
    dp["route_dist_float"] = dp["mainline_route_dist_m"].map(lambda x: to_float(x, None))

    # Optional route source table for route_source_path.
    sources = read_csv_if_exists(route_sources_path)
    source_map: Dict[str, str] = {}
    if not sources.empty and {"case_id", "route_source_path"}.issubset(sources.columns):
        for _, row in sources.iterrows():
            source_map[normalize_case_id(row.get("case_id", ""))] = row.get("route_source_path", "")

    summary = read_csv_if_exists(route_summary_path)
    length_map: Dict[str, Optional[float]] = {}
    if not summary.empty and "case_id" in summary.columns:
        len_col = next((c for c in ["route_length_m", "route_dist_max_m", "route_max_m"] if c in summary.columns), "")
        if len_col:
            for _, row in summary.iterrows():
                length_map[normalize_case_id(row.get("case_id", ""))] = to_float(row.get(len_col, ""), None)

    rows: List[Dict] = []
    for case_id, g in dp.groupby("case_id_norm", dropna=False):
        if not case_id:
            continue
        route_len = length_map.get(case_id)
        max_dist = max([x for x in g["route_dist_float"].tolist() if x is not None and math.isfinite(x)] or [None])
        if route_len is None or not math.isfinite(route_len):
            route_len = max_dist
        route_len_km = (route_len / 1000.0) if route_len and route_len > 0 else None

        fork_count = int(g["fork_candidate"].map(is_true).sum()) if "fork_candidate" in g.columns else len(g)
        decision_count = int(g["decision_point_candidate"].map(is_true).sum()) if "decision_point_candidate" in g.columns else len(g)
        node_count = len(g)
        side_branch_sum = int(sum(to_int(v, 0) for v in g.get("side_branch_count", pd.Series(dtype=str)).tolist())) if "side_branch_count" in g.columns else ""

        rows.append({
            "case_id": case_id,
            "route_source_path": source_map.get(case_id, ""),
            "route_length_m": compact_num(route_len, 3),
            "route_length_km": compact_num(route_len_km, 6),
            "governed_topology_context_status": "GOVERNED_TOPOLOGY_CONTEXT_AVAILABLE",
            "governed_decision_point_exposure_count": decision_count,
            "governed_fork_exposure_count": fork_count,
            "governed_topology_node_count_at_decision_points": node_count,
            "governed_side_branch_reference_count": side_branch_sum,
            "decision_point_exposure_per_km": compact_num((decision_count / route_len_km) if route_len_km else None, 6),
            "fork_exposure_per_km": compact_num((fork_count / route_len_km) if route_len_km else None, 6),
            "route_dist_min_m": compact_num(min([x for x in g["route_dist_float"].tolist() if x is not None and math.isfinite(x)] or [None]), 3),
            "route_dist_max_m": compact_num(max_dist, 3),
            "context_source": "ib1_route_topology_generator_node_degree_v1_1",
            "interpretation_boundary": BOUNDARY,
        })
    return pd.DataFrame(rows), rows


def find_activity_table() -> Optional[Path]:
    for p in PREFERRED_ACTIVITY_TABLES:
        if p.exists():
            return p
    # Constrained fallback search in report figures only.
    candidates = []
    rf = PROJECT_ROOT / "outputs" / "report_figures"
    if rf.exists():
        patterns = [
            "**/personal_ability_radar_data_table_v1_1.csv",
            "**/personal_ability_radar_plot_ready_table_v1_1.csv",
            "**/*route_following*data*table*.csv",
        ]
        for pat in patterns:
            candidates.extend(rf.glob(pat))
    candidates = sorted(set(candidates), key=lambda p: ("v1_1" not in p.name, str(p)))
    return candidates[0] if candidates else None


def extract_route_following_rows(route_context_cases: List[str]) -> Tuple[pd.DataFrame, Dict]:
    source = find_activity_table()
    meta = {
        "activity_source_path": str(source.relative_to(PROJECT_ROOT)).replace("\\", "/") if source else "",
        "activity_source_found": bool(source),
        "activity_source_mode": "NONE",
    }
    if source is None:
        return pd.DataFrame(), meta

    df = read_csv_if_exists(source)
    if df.empty:
        return pd.DataFrame(), meta

    cols = list(df.columns)
    low_cols = {c.lower(): c for c in cols}
    activity_col = next((low_cols[c] for c in ["activity_id", "activity", "source_activity_id", "activity_key"] if c in low_cols), "")
    if not activity_col:
        # Try any column containing activity.
        activity_col = next((c for c in cols if "activity" in c.lower()), "")
    if not activity_col:
        meta["activity_source_mode"] = "NO_ACTIVITY_ID_COLUMN"
        return pd.DataFrame(), meta

    axis_col = next((low_cols[c] for c in ["axis_id", "axis_key", "axis", "metric_id", "metric_key"] if c in low_cols), "")
    value_col = next((low_cols[c] for c in ["axis_value", "value", "proxy_value", "display_value"] if c in low_cols), "")
    status_col = next((low_cols[c] for c in ["axis_status", "status", "output_mode", "mode"] if c in low_cols), "")

    route_cols = [c for c in cols if c.lower() in {"route_case_id", "case_id", "route_id", "route_folder", "formal_case_id", "source_case_id"}]

    rows: List[Dict] = []
    if axis_col:
        mask = df[axis_col].astype(str).str.lower().str.contains("route_following_stability", na=False)
        sub = df[mask].copy()
        meta["activity_source_mode"] = "LONG_AXIS_TABLE_ROUTE_FOLLOWING_FILTER"
    elif "route_following_stability" in low_cols:
        sub = df.copy()
        axis_col = low_cols["route_following_stability"]
        value_col = axis_col
        meta["activity_source_mode"] = "WIDE_ROUTE_FOLLOWING_COLUMN"
    else:
        sub = df.copy()
        meta["activity_source_mode"] = "ACTIVITY_TABLE_NO_ROUTE_FOLLOWING_AXIS_FILTER"

    # Exclude known extra/source-only activities before route binding. This prevents
    # context-only or extra sources such as 6_1 from inheriting the default
    # qixing_lengshuikeng route context.
    if activity_col in sub.columns:
        sub = sub[~sub[activity_col].astype(str).str.strip().isin(EXCLUDED_ACTIVITY_IDS)].copy()

    default_case = "qixing_lengshuikeng" if "qixing_lengshuikeng" in route_context_cases else (route_context_cases[0] if route_context_cases else "")

    for _, row in sub.iterrows():
        activity_id = str(row.get(activity_col, "")).strip()
        if not activity_id:
            continue
        route_case = ""
        route_method = ""
        for rc in route_cols:
            cand = normalize_case_id(str(row.get(rc, "")))
            if cand in route_context_cases:
                route_case = cand
                route_method = f"COLUMN_{rc}"
                break
        if not route_case:
            route_case = default_case
            route_method = "DEFAULT_QIXING_LENGSHUIKENG_ACTIVITY_SET" if route_case == "qixing_lengshuikeng" else "DEFAULT_FIRST_AVAILABLE_ROUTE_CONTEXT"

        axis_value = row.get(value_col, "") if value_col else ""
        status = row.get(status_col, "") if status_col else ""
        rows.append({
            "activity_id": activity_id,
            "route_case_id": route_case,
            "activity_route_binding_method": route_method,
            "route_following_stability_proxy_value": axis_value,
            "route_following_source_status": status,
            "activity_source_path": meta["activity_source_path"],
        })

    # Deduplicate activity rows while preserving first occurrence.
    dedup = []
    seen = set()
    for r in rows:
        key = (r["activity_id"], r["route_case_id"])
        if key in seen:
            continue
        seen.add(key)
        dedup.append(r)
    return pd.DataFrame(dedup), meta


def build_activity_context(route_df: pd.DataFrame, route_rows: List[Dict]) -> Tuple[List[Dict], List[Dict], Dict]:
    route_cases = route_df["case_id"].tolist() if not route_df.empty else []
    act_df, meta = extract_route_following_rows(route_cases)
    if act_df.empty:
        return [], [], meta

    route_map = {r["case_id"]: r for r in route_rows}
    activity_rows: List[Dict] = []
    joined_rows: List[Dict] = []
    for _, row in act_df.iterrows():
        case_id = row.get("route_case_id", "")
        rc = route_map.get(case_id, {})
        missing = not bool(rc)
        context_status = "MISSING_ROUTE_TOPOLOGY_CONTEXT" if missing else "GOVERNED_NAVIGATION_CHALLENGE_CONTEXT_AVAILABLE"

        activity_context = {
            "activity_id": row.get("activity_id", ""),
            "route_case_id": case_id,
            "activity_route_binding_method": row.get("activity_route_binding_method", ""),
            "navigation_challenge_context_status": context_status,
            "governed_decision_point_exposure_count": rc.get("governed_decision_point_exposure_count", "") if rc else "",
            "governed_fork_exposure_count": rc.get("governed_fork_exposure_count", "") if rc else "",
            "decision_point_exposure_per_km": rc.get("decision_point_exposure_per_km", "") if rc else "",
            "fork_exposure_per_km": rc.get("fork_exposure_per_km", "") if rc else "",
            "route_length_m": rc.get("route_length_m", "") if rc else "",
            "not_personal_ability_axis": True,
            "not_navigation_ability_score": True,
            "not_radar_score": True,
            "not_go_no_go_decision": True,
            "interpretation_boundary": BOUNDARY,
        }
        activity_rows.append(activity_context)

        joined_rows.append({
            "activity_id": row.get("activity_id", ""),
            "route_case_id": case_id,
            "route_following_stability_proxy_value": row.get("route_following_stability_proxy_value", ""),
            "route_following_source_status": row.get("route_following_source_status", ""),
            "navigation_challenge_context_status": context_status,
            "governed_decision_point_exposure_count": activity_context["governed_decision_point_exposure_count"],
            "governed_fork_exposure_count": activity_context["governed_fork_exposure_count"],
            "decision_point_exposure_per_km": activity_context["decision_point_exposure_per_km"],
            "fork_exposure_per_km": activity_context["fork_exposure_per_km"],
            "route_following_interpretation_context": (
                "ROUTE_FOLLOWING_PROXY_HAS_GOVERNED_NAVIGATION_CHALLENGE_CONTEXT"
                if not missing else "ROUTE_FOLLOWING_PROXY_MISSING_NAVIGATION_CHALLENGE_CONTEXT"
            ),
            "not_personal_ability_axis": True,
            "not_navigation_ability_score": True,
            "not_radar_score": True,
            "not_go_no_go_decision": True,
            "interpretation_boundary": BOUNDARY,
        })
    return activity_rows, joined_rows, meta


def build_report(paths: Dict[str, Path], audit: Dict, admission: Dict, route_rows: List[Dict], activity_count: int) -> None:
    def esc(x) -> str:
        return html.escape(str(x))

    top_routes = "".join(
        f"<tr><td>{esc(r.get('case_id',''))}</td><td>{esc(r.get('governed_decision_point_exposure_count',''))}</td>"
        f"<td>{esc(r.get('governed_fork_exposure_count',''))}</td><td>{esc(r.get('decision_point_exposure_per_km',''))}</td></tr>"
        for r in route_rows
    )
    body = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>CH6.5.5 Navigation Challenge Context Consumption v1.1</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 32px; line-height: 1.55; }}
code, pre {{ background: #f6f8fa; padding: 2px 4px; border-radius: 4px; }}
table {{ border-collapse: collapse; width: 100%; margin: 12px 0 24px; }}
th, td {{ border: 1px solid #ddd; padding: 6px 8px; text-align: left; }}
th {{ background: #f2f2f2; }}
.badge {{ display: inline-block; padding: 4px 8px; border: 1px solid #bbb; border-radius: 6px; background: #fafafa; }}
</style>
</head>
<body>
<h1>CH6.5.5 Navigation Challenge Context Consumption v1.1</h1>
<p><span class="badge">{esc(audit.get('audit_conclusion',''))}</span></p>
<p>This report consumes the upstream IB1 route topology node-degree generator v1.1 output as navigation-challenge exposure context. It does not modify the radar, axis contract, or data table.</p>

<h2>Boundary</h2>
<p>{esc(BOUNDARY)}</p>

<h2>Admission</h2>
<ul>
<li>Decision: <code>{esc(admission.get('decision',''))}</code></li>
<li>Recommended use: {esc(admission.get('recommended_use',''))}</li>
<li>Reason: {esc(admission.get('decision_reason',''))}</li>
</ul>

<h2>Audit summary</h2>
<table>
<tr><th>Metric</th><th>Value</th></tr>
{''.join(f'<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>' for k, v in audit.items())}
</table>

<h2>Route context summary</h2>
<table>
<tr><th>case_id</th><th>decision points</th><th>forks</th><th>decision points per km</th></tr>
{top_routes}
</table>

<h2>Outputs</h2>
<ul>
{''.join(f'<li><code>{esc(p.name)}</code></li>' for p in paths.values())}
</ul>
</body>
</html>
"""
    paths["report"].write_text(body, encoding="utf-8")


def main() -> None:
    ensure_dir(OUT_ROOT)

    topology_audit_path = TOPO_ROOT / "route_topology_generator_audit_v1_1.csv"
    topology_admission_path = TOPO_ROOT / "route_topology_generator_admission_v1_1.csv"
    topology_dp_path = TOPO_ROOT / "route_topology_decision_points_v1_1.csv"

    if not topology_dp_path.exists():
        raise FileNotFoundError(f"Missing topology decision point input: {topology_dp_path}")

    route_df, route_rows = build_route_context()
    activity_rows, joined_rows, activity_meta = build_activity_context(route_df, route_rows)

    topology_audit = read_csv_if_exists(topology_audit_path)
    topo_audit_dict = topology_audit.iloc[0].to_dict() if not topology_audit.empty else {}
    topology_admission = read_csv_if_exists(topology_admission_path)
    topo_admission_dict = topology_admission.iloc[0].to_dict() if not topology_admission.empty else {}

    # Output paths.
    paths = {
        "route_context": OUT_ROOT / "route_navigation_challenge_context_v1_1.csv",
        "activity_context": OUT_ROOT / "activity_navigation_challenge_context_v1_1.csv",
        "route_following_context": OUT_ROOT / "route_following_with_navigation_context_v1_1.csv",
        "source_inventory": OUT_ROOT / "navigation_challenge_context_source_inventory_v1_1.csv",
        "admission": OUT_ROOT / "navigation_challenge_context_consumption_admission_v1_1.csv",
        "audit": OUT_ROOT / "navigation_challenge_context_consumption_audit_v1_1.csv",
        "report": OUT_ROOT / "navigation_challenge_context_consumption_report_v1_1.html",
    }

    route_fields = [
        "case_id", "route_source_path", "route_length_m", "route_length_km", "governed_topology_context_status",
        "governed_decision_point_exposure_count", "governed_fork_exposure_count",
        "governed_topology_node_count_at_decision_points", "governed_side_branch_reference_count",
        "decision_point_exposure_per_km", "fork_exposure_per_km", "route_dist_min_m", "route_dist_max_m",
        "context_source", "interpretation_boundary",
    ]
    write_csv(paths["route_context"], route_rows, route_fields)

    activity_fields = [
        "activity_id", "route_case_id", "activity_route_binding_method", "navigation_challenge_context_status",
        "governed_decision_point_exposure_count", "governed_fork_exposure_count", "decision_point_exposure_per_km",
        "fork_exposure_per_km", "route_length_m", "not_personal_ability_axis", "not_navigation_ability_score",
        "not_radar_score", "not_go_no_go_decision", "interpretation_boundary",
    ]
    write_csv(paths["activity_context"], activity_rows, activity_fields)

    joined_fields = [
        "activity_id", "route_case_id", "route_following_stability_proxy_value", "route_following_source_status",
        "navigation_challenge_context_status", "governed_decision_point_exposure_count", "governed_fork_exposure_count",
        "decision_point_exposure_per_km", "fork_exposure_per_km", "route_following_interpretation_context",
        "not_personal_ability_axis", "not_navigation_ability_score", "not_radar_score", "not_go_no_go_decision",
        "interpretation_boundary",
    ]
    write_csv(paths["route_following_context"], joined_rows, joined_fields)

    source_rows = [
        {
            "source_name": "ib1_route_topology_generator_node_degree_v1_1",
            "source_path": str(TOPO_ROOT.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "source_exists": TOPO_ROOT.exists(),
            "decision_points_path_exists": topology_dp_path.exists(),
            "topology_audit_conclusion": topo_audit_dict.get("audit_conclusion", ""),
            "topology_admission_decision": topo_admission_dict.get("decision", ""),
            "usable_osm_graph_topology_source_count": topo_audit_dict.get("usable_osm_graph_topology_source_count", ""),
            "usable_route_position_source_count": topo_audit_dict.get("usable_route_position_source_count", ""),
            "governed_decision_point_candidate_count": topo_audit_dict.get("governed_decision_point_candidate_count", ""),
            "governed_fork_candidate_count": topo_audit_dict.get("governed_fork_candidate_count", ""),
            "source_role": "upstream_governed_topology_source_candidate",
            "notes": "Consumed as route/activity navigation-challenge exposure context only.",
        },
        {
            "source_name": "route_following_activity_table",
            "source_path": activity_meta.get("activity_source_path", ""),
            "source_exists": activity_meta.get("activity_source_found", False),
            "decision_points_path_exists": "",
            "topology_audit_conclusion": "",
            "topology_admission_decision": "",
            "usable_osm_graph_topology_source_count": "",
            "usable_route_position_source_count": "",
            "governed_decision_point_candidate_count": "",
            "governed_fork_candidate_count": "",
            "source_role": "activity_route_following_context_join_source",
            "notes": activity_meta.get("activity_source_mode", ""),
        },
    ]
    write_csv(paths["source_inventory"], source_rows)

    route_context_count = len(route_rows)
    activity_context_count = len(activity_rows)
    joined_count = len(joined_rows)
    missing_route_context_count = sum(1 for r in activity_rows if r.get("navigation_challenge_context_status") == "MISSING_ROUTE_TOPOLOGY_CONTEXT")
    default_binding_count = sum(1 for r in activity_rows if str(r.get("activity_route_binding_method", "")).startswith("DEFAULT_"))
    excluded_activity_count = len(EXCLUDED_ACTIVITY_IDS)

    # This consumption should not create scores or mutate previous artifacts.
    admission_decision = (
        "ADMIT_AS_NAVIGATION_CHALLENGE_CONTEXT_SOURCE"
        if route_context_count > 0 and int(to_int(topo_audit_dict.get("governed_decision_point_candidate_count", 0), 0)) > 0
        else "RETAIN_AS_NAVIGATION_CHALLENGE_CONTEXT_SOURCE_GAP"
    )
    admission = {
        "context_id": "navigation_challenge_exposure",
        "context_label_zh": "導航挑戰暴露",
        "decision": admission_decision,
        "recommended_use": "route-following interpretation context only; do not add as radar axis",
        "not_personal_ability_axis": True,
        "not_navigation_ability_score": True,
        "not_radar_score": True,
        "not_go_no_go_decision": True,
        "route_context_count": route_context_count,
        "activity_context_count": activity_context_count,
        "joined_route_following_context_count": joined_count,
        "governed_decision_point_candidate_count": topo_audit_dict.get("governed_decision_point_candidate_count", ""),
        "governed_fork_candidate_count": topo_audit_dict.get("governed_fork_candidate_count", ""),
        "decision_reason": "Upstream governed topology source candidate is consumed as navigation-challenge exposure context only.",
        "interpretation_boundary": BOUNDARY,
    }
    write_csv(paths["admission"], [admission])

    forbidden = scan_forbidden_field_names([p for k, p in paths.items() if k != "report"])
    audit_conclusion = (
        "PASS_CH6_5_5_NAVIGATION_CHALLENGE_CONTEXT_CONSUMPTION_V1_1_GOVERNED_CONTEXT_AVAILABLE"
        if admission_decision == "ADMIT_AS_NAVIGATION_CHALLENGE_CONTEXT_SOURCE" and forbidden == "NONE"
        else "FAIL_CH6_5_5_NAVIGATION_CHALLENGE_CONTEXT_CONSUMPTION_V1_REVIEW_REQUIRED"
    )
    audit = {
        "topology_input_root_exists": TOPO_ROOT.exists(),
        "topology_decision_points_exists": topology_dp_path.exists(),
        "topology_audit_conclusion": topo_audit_dict.get("audit_conclusion", ""),
        "topology_admission_decision": topo_admission_dict.get("decision", ""),
        "route_context_count": route_context_count,
        "activity_context_count": activity_context_count,
        "joined_route_following_context_count": joined_count,
        "missing_route_context_count": missing_route_context_count,
        "default_activity_route_binding_count": default_binding_count,
        "excluded_activity_ids": "|".join(sorted(EXCLUDED_ACTIVITY_IDS)),
        "excluded_activity_count_configured": excluded_activity_count,
        "extra_source_6_1_excluded": not any(str(r.get("activity_id", "")).strip() == "6_1" for r in activity_rows),
        "governed_decision_point_candidate_count_consumed": topo_audit_dict.get("governed_decision_point_candidate_count", ""),
        "governed_fork_candidate_count_consumed": topo_audit_dict.get("governed_fork_candidate_count", ""),
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
        "interpretation_boundary": BOUNDARY,
    }
    write_csv(paths["audit"], [audit])
    build_report(paths, audit, admission, route_rows, activity_context_count)

    print({
        "output_root": str(OUT_ROOT),
        "route_context_count": route_context_count,
        "activity_context_count": activity_context_count,
        "joined_route_following_context_count": joined_count,
        "governed_decision_point_candidate_count_consumed": topo_audit_dict.get("governed_decision_point_candidate_count", ""),
        "governed_fork_candidate_count_consumed": topo_audit_dict.get("governed_fork_candidate_count", ""),
        "admission_decision": admission_decision,
        "audit_conclusion": audit_conclusion,
    })


if __name__ == "__main__":
    main()
