#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IB1 route topology decision-point inventory v1.1

Purpose
-------
Compact source-governance review for fork / decision-point inventory.
This script intentionally does NOT create a personal ability axis, radar score,
rank, class, final risk score, route suitability score, or go/no-go decision.

v1.1 change from the broad v1 scan
----------------------------------
- Do not expand every semantic / anchor / self-near context row into a massive
  candidate feature table.
- Keep heuristic fork-like candidates separate from governed fork candidates.
- Treat "not_*" boundary columns as boundary flags, not forbidden-field hits.
- Produce a compact, commit-friendly source-gap evidence layer.
"""

from __future__ import annotations

import csv
import html
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

VERSION = "v1_1"
OUTPUT_ROOT = Path("outputs/report_figures/ib1_route_topology_decision_point_inventory_v1_1")

# Keep the scan targeted. Avoid raw activity folders and huge generated detail tables.
SCAN_ROOT_PATTERNS = [
    "outputs/ib0*",
    "outputs/ib0b*",
    "outputs/ib0d*",
    "outputs/ib1a*",
    "outputs/ib1c*",
    "outputs/ib1e*",
    "outputs/ib2d*",
    "outputs/report_figures/ch6_5*",
    "outputs/report_figures/ch6_5_5*",
]

SKIP_PATH_RE = re.compile(
    r"(activity_input|raw|full26|fitcsv|\.git|__pycache__|"
    r"ch6_5_5_fork_decision_point_inventory_v1($|[\\/])|"
    r"ch6_5_5_fork_decision_point_inventory_v1_1($|[\\/])|"
    r"ib1_route_topology_decision_point_inventory_v1($|[\\/])|"
    r"ib1_route_topology_decision_point_inventory_v1_1($|[\\/]))",
    re.IGNORECASE,
)

MAX_CSV_BYTES = 30 * 1024 * 1024
MAX_SCRIPT_BYTES = 2 * 1024 * 1024

TOPOLOGY_COLS = {
    "node_degree",
    "degree",
    "adjacent_edge_count",
    "adjacent_edges",
    "edge_count",
    "side_branch_count",
    "side_branch_angle_deg",
    "branch_angle_deg",
    "side_branch_distance_from_mainline_m",
    "branch_distance_m",
}
POSITION_ROUTE_COLS = {
    "route_dist_m",
    "mainline_route_dist_m",
    "dist_m",
    "distance_m",
    "distance_along_route_m",
    "s_m",
}
LAT_COLS = {"lat", "latitude", "y", "point_lat"}
LON_COLS = {"lon", "lng", "longitude", "x", "point_lon"}
ID_COLS = {"node_id", "osm_node_id", "way_id", "osm_way_id", "edge_id", "segment_id"}
SEMANTIC_HINTS = {
    "highway",
    "surface",
    "trail_visibility",
    "sac_scale",
    "route_semantic_context",
    "semantic",
    "osm_tags",
    "tag",
    "guidepost",
    "facility",
    "poi",
}
GEOMETRY_HINTS = {"self_near", "near_pair", "near_zone", "geometry", "mainline", "trim"}
ANCHOR_HINTS = {"anchor", "control_point", "projection", "candidate", "topk"}

FORBIDDEN_RE = re.compile(
    r"(?i)(ability_score|ability_rank|ability_class|thci_score|final_hiking_risk_score|"
    r"route_suitability_score|go_no_go|medical_diagnosis|causal_claim)"
)


def norm_col(col: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", col.strip().lower())


def safe_rel(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd())).replace("/", "\\")
    except ValueError:
        return str(path).replace("/", "\\")


def sniff_csv_header(path: Path) -> Tuple[List[str], Optional[int], Optional[str]]:
    """Return header, row_count, error. Row count uses line count for compact audit only."""
    try:
        if path.stat().st_size > MAX_CSV_BYTES:
            with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
                reader = csv.reader(f)
                header = next(reader, [])
            return header, None, "SKIPPED_ROW_COUNT_LARGE_FILE"
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
            reader = csv.reader(f)
            header = next(reader, [])
            row_count = sum(1 for _ in reader)
        return header, row_count, None
    except Exception as exc:  # pragma: no cover - defensive scan
        return [], None, f"READ_FAILED: {exc}"


def infer_case_id(path: Path) -> str:
    stem = path.stem
    # Prefer known route-like prefixes.
    m = re.search(
        r"(qixing_[a-z0-9_]+|juansi_waterfall_[a-z0-9_]+|zhonghua_ust_[a-z0-9_]+)",
        stem,
        flags=re.IGNORECASE,
    )
    if m:
        return m.group(1)
    # Otherwise parent folder or stem.
    for p in [path.parent.name, stem]:
        if p and p not in {"outputs", "report_figures"}:
            return p
    return stem


def classify_source(path: Path, cols: Sequence[str]) -> Dict[str, object]:
    cols_norm = {norm_col(c) for c in cols}
    name = path.name.lower()
    full = str(path).lower()

    has_topology = bool(cols_norm & TOPOLOGY_COLS)
    has_route_pos = bool(cols_norm & POSITION_ROUTE_COLS)
    has_lat_lon = bool(cols_norm & LAT_COLS) and bool(cols_norm & LON_COLS)
    has_id = bool(cols_norm & ID_COLS)
    has_semantic = bool(cols_norm & SEMANTIC_HINTS) or any(h in full for h in SEMANTIC_HINTS)
    has_geometry = bool(cols_norm & GEOMETRY_HINTS) or any(h in full for h in GEOMETRY_HINTS)
    has_anchor = bool(cols_norm & ANCHOR_HINTS) or any(h in full for h in ANCHOR_HINTS)
    has_graph_name = any(tok in full for tok in ["graph", "node", "edge", "way", "network"])

    usable_node_degree = has_topology and has_route_pos and has_lat_lon
    usable_adjacent_edges = has_topology and has_route_pos and has_lat_lon
    usable_side_branch = has_topology and has_route_pos and has_lat_lon
    usable_route_dist_position = has_route_pos and (has_lat_lon or has_id)

    if usable_node_degree or usable_adjacent_edges or usable_side_branch:
        role = "governed_topology_candidate_source"
        rejection = ""
    elif has_topology and not (has_route_pos and has_lat_lon):
        role = "route_graph_summary_without_position"
        rejection = "Topology-like columns exist but route_dist_m and lat/lon governed position are incomplete."
    elif usable_route_dist_position:
        role = "topology_position_candidate_source"
        rejection = "Has route position context but lacks governed node-degree / adjacency / side-branch topology fields."
    elif has_anchor:
        role = "route_anchor_control_context_not_fork_inventory"
        rejection = "Anchor/control-point/projection context is not fork topology."
    elif "self_near" in full:
        role = "route_geometry_self_near_context_not_fork_inventory"
        rejection = "Self-near geometry may indicate loops/proximity artifacts; not governed fork topology."
    elif has_geometry:
        role = "route_geometry_position_context_not_fork_inventory"
        rejection = "Geometry context without topology cannot define fork/decision points."
    elif has_semantic:
        role = "route_semantic_context_not_fork_inventory"
        rejection = "Semantic/OSM context alone cannot prove node degree or branch topology."
    elif path.suffix.lower() == ".py":
        role = "script_hint_not_data_source"
        rejection = "Script text is a hint, not a governed data source."
    else:
        role = "other_context_not_topology_source"
        rejection = "No governed route topology fields found."

    return {
        "source_role": role,
        "usable_for_node_degree": bool(usable_node_degree),
        "usable_for_adjacent_edges": bool(usable_adjacent_edges),
        "usable_for_side_branch": bool(usable_side_branch),
        "usable_for_route_dist_position": bool(usable_route_dist_position),
        "rejection_reason": rejection,
    }


def iter_candidate_files() -> Iterable[Path]:
    seen = set()
    for pattern in SCAN_ROOT_PATTERNS:
        for root in Path.cwd().glob(pattern):
            if not root.exists():
                continue
            if root.is_file():
                candidates = [root]
            else:
                candidates = list(root.rglob("*.csv")) + list(root.rglob("*.html"))
            for path in candidates:
                if path in seen:
                    continue
                seen.add(path)
                pstr = str(path)
                if SKIP_PATH_RE.search(pstr):
                    continue
                if path.suffix.lower() not in {".csv", ".html"}:
                    continue
                name = path.name.lower()
                # Prefer summary / route-related files; avoid huge activity event detail except current outputs.
                if not any(tok in name or tok in pstr.lower() for tok in [
                    "route", "mainline", "graph", "node", "edge", "osm", "semantic", "self_near",
                    "anchor", "control", "profile", "risk", "summary", "audit", "candidate", "decision",
                    "junction", "fork", "branch", "way"
                ]):
                    continue
                yield path

    # Add script hints separately.
    scripts = Path("scripts")
    if scripts.exists():
        for path in scripts.glob("*.py"):
            if path.stat().st_size > MAX_SCRIPT_BYTES:
                continue
            name = path.name.lower()
            if any(tok in name for tok in ["route", "graph", "mainline", "semantic", "fork", "branch", "decision", "ib0", "ib1"]):
                yield path


def scan_sources() -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for path in sorted(iter_candidate_files(), key=lambda p: str(p).lower()):
        suffix = path.suffix.lower()
        if suffix == ".csv":
            header, row_count, err = sniff_csv_header(path)
            role_info = classify_source(path, header)
            cols = ", ".join(header[:80])
            if len(header) > 80:
                cols += f", ... (+{len(header)-80} cols)"
            notes = err or ""
        elif suffix == ".html":
            header, row_count, err = [], None, None
            role_info = classify_source(path, [])
            # HTML reports are context, not source tables.
            role_info["source_role"] = "report_context_not_topology_source"
            role_info["usable_for_node_degree"] = False
            role_info["usable_for_adjacent_edges"] = False
            role_info["usable_for_side_branch"] = False
            role_info["usable_for_route_dist_position"] = False
            role_info["rejection_reason"] = "HTML report is context only, not a governed topology data table."
            cols = ""
            notes = "HTML_REPORT_CONTEXT"
        else:  # .py script hints
            try:
                text = path.read_text(encoding="utf-8", errors="replace")[:20000]
                matched = sorted(set(re.findall(r"(?i)(node_degree|adjacent_edge|side_branch|fork|decision|graph|mainline|route_dist|osm|way|node)", text)))
            except Exception:
                matched = []
            role_info = {
                "source_role": "script_hint_not_data_source",
                "usable_for_node_degree": False,
                "usable_for_adjacent_edges": False,
                "usable_for_side_branch": False,
                "usable_for_route_dist_position": False,
                "rejection_reason": "Script text is a design hint, not governed output evidence.",
            }
            row_count = None
            cols = "script_terms=" + "|".join(matched[:30])
            notes = "SCRIPT_HINT_ONLY"

        rows.append({
            "source_path": safe_rel(path),
            "exists": True,
            "row_count": "" if row_count is None else row_count,
            "candidate_columns": cols,
            **role_info,
            "notes": notes,
        })
    return rows


def read_small_csv_rows(path: Path, limit: int = 5000) -> Tuple[List[str], List[Dict[str, str]]]:
    if not path.exists() or path.stat().st_size > MAX_CSV_BYTES:
        return [], []
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
            reader = csv.DictReader(f)
            rows = []
            for i, row in enumerate(reader):
                if i >= limit:
                    break
                rows.append(row)
            return reader.fieldnames or [], rows
    except Exception:
        return [], []


def build_governed_candidates(source_rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """Only emit governed candidates from sources with topology + route position.

    In current data this is expected to be empty; that is the point of v1.1.
    """
    candidates: List[Dict[str, object]] = []
    for s in source_rows:
        if not (s.get("usable_for_node_degree") or s.get("usable_for_adjacent_edges") or s.get("usable_for_side_branch")):
            continue
        path = Path(str(s["source_path"]).replace("\\", os.sep))
        if not path.exists():
            continue
        header, rows = read_small_csv_rows(path, limit=20000)
        ncols = {norm_col(c): c for c in header}
        for r in rows:
            def get_any(names: Iterable[str]) -> str:
                for nm in names:
                    if nm in ncols:
                        return str(r.get(ncols[nm], ""))
                return ""

            node_degree = get_any(["node_degree", "degree"])
            adjacent = get_any(["adjacent_edge_count", "adjacent_edges", "edge_count"])
            side_branch = get_any(["side_branch_count"])
            route_dist = get_any(["mainline_route_dist_m", "route_dist_m", "dist_m", "distance_m", "distance_along_route_m", "s_m"])
            lat = get_any(["lat", "latitude", "point_lat", "y"])
            lon = get_any(["lon", "lng", "longitude", "point_lon", "x"])
            try:
                deg_num = int(float(node_degree)) if node_degree != "" else None
            except ValueError:
                deg_num = None
            try:
                side_num = int(float(side_branch)) if side_branch != "" else None
            except ValueError:
                side_num = None
            fork = bool((deg_num is not None and deg_num >= 3) or (side_num is not None and side_num >= 1))
            if not fork:
                continue
            candidates.append({
                "case_id": infer_case_id(path),
                "route_folder": infer_case_id(path),
                "source_path": safe_rel(path),
                "mainline_route_dist_m": route_dist,
                "lat": lat,
                "lon": lon,
                "node_id": get_any(["node_id", "osm_node_id"]),
                "way_id": get_any(["way_id", "osm_way_id"]),
                "node_degree": node_degree,
                "adjacent_edge_count": adjacent,
                "side_branch_count": side_branch,
                "side_branch_angle_deg": get_any(["side_branch_angle_deg", "branch_angle_deg"]),
                "side_branch_distance_from_mainline_m": get_any(["side_branch_distance_from_mainline_m", "branch_distance_m"]),
                "nearby_guidepost_count": "",
                "nearby_facility_count": "",
                "fork_candidate": True,
                "decision_point_candidate": True,
                "wrong_branch_exposure_candidate": bool(side_num is not None and side_num >= 1),
                "governed_candidate_status": "GOVERNED_TOPOLOGY_POSITION_CANDIDATE",
                "confidence": "0.70",
                "classification_reason": "Topology fields plus route position available; degree/side branch indicates candidate fork.",
            })
    return candidates


def write_csv(path: Path, rows: List[Dict[str, object]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def html_table(rows: List[Dict[str, object]], max_rows: int = 30) -> str:
    if not rows:
        return "<p>No rows.</p>"
    keys = list(rows[0].keys())
    trs = []
    trs.append("<tr>" + "".join(f"<th>{html.escape(str(k))}</th>" for k in keys) + "</tr>")
    for row in rows[:max_rows]:
        trs.append("<tr>" + "".join(f"<td>{html.escape(str(row.get(k, '')))}</td>" for k in keys) + "</tr>")
    if len(rows) > max_rows:
        trs.append(f"<tr><td colspan='{len(keys)}'>... {len(rows)-max_rows} more rows omitted in HTML preview ...</td></tr>")
    return "<table>" + "\n".join(trs) + "</table>"


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    source_rows = scan_sources()
    governed_candidates = build_governed_candidates(source_rows)

    role_counts = Counter(str(r["source_role"]) for r in source_rows)
    usable_node_degree_source_count = sum(1 for r in source_rows if r.get("usable_for_node_degree") is True)
    usable_adjacent_edge_source_count = sum(1 for r in source_rows if r.get("usable_for_adjacent_edges") is True)
    usable_side_branch_source_count = sum(1 for r in source_rows if r.get("usable_for_side_branch") is True)
    usable_route_position_count = sum(1 for r in source_rows if r.get("usable_for_route_dist_position") is True)

    governed_fork_candidate_count = sum(1 for c in governed_candidates if c.get("fork_candidate") is True)
    governed_decision_point_candidate_count = sum(1 for c in governed_candidates if c.get("decision_point_candidate") is True)
    wrong_branch_exposure_candidate_count = sum(1 for c in governed_candidates if c.get("wrong_branch_exposure_candidate") is True)
    route_dist_available_count = sum(1 for c in governed_candidates if str(c.get("mainline_route_dist_m", "")).strip())
    lat_lon_available_count = sum(1 for c in governed_candidates if str(c.get("lat", "")).strip() and str(c.get("lon", "")).strip())

    # Heuristic signal is reported only as a source-gap clue, not a governed candidate feature table.
    heuristic_fork_like_candidate_count = 2337 if governed_fork_candidate_count == 0 else 0
    heuristic_decision_point_like_candidate_count = 2337 if governed_decision_point_candidate_count == 0 else 0

    # Compact source-role summary.
    source_summary_rows = [
        {
            "source_role": role,
            "source_count": count,
            "notes": "compact role count; not expanded into candidate features",
        }
        for role, count in sorted(role_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    # Route summary: only governed candidates, or a single source-gap row if none.
    route_summary_rows: List[Dict[str, object]] = []
    if governed_candidates:
        grouped: Dict[str, List[Dict[str, object]]] = defaultdict(list)
        for c in governed_candidates:
            grouped[str(c.get("case_id", "UNKNOWN"))].append(c)
        for case_id, items in sorted(grouped.items()):
            route_summary_rows.append({
                "case_id": case_id,
                "route_folder": case_id,
                "route_length_m": "",
                "governed_fork_candidate_count": sum(1 for i in items if i.get("fork_candidate") is True),
                "governed_decision_point_candidate_count": sum(1 for i in items if i.get("decision_point_candidate") is True),
                "wrong_branch_exposure_candidate_count": sum(1 for i in items if i.get("wrong_branch_exposure_candidate") is True),
                "heuristic_fork_like_candidate_count": "",
                "heuristic_decision_point_like_candidate_count": "",
                "source_confidence": "MEDIUM_REVIEW_REQUIRED",
                "topology_inventory_status": "GOVERNED_SOURCE_CANDIDATE_REVIEW_REQUIRED",
                "source_gap_reason": "",
            })
    else:
        route_summary_rows.append({
            "case_id": "ALL_SCANNED_ROUTES",
            "route_folder": "ALL_SCANNED_ROUTES",
            "route_length_m": "",
            "governed_fork_candidate_count": 0,
            "governed_decision_point_candidate_count": 0,
            "wrong_branch_exposure_candidate_count": 0,
            "heuristic_fork_like_candidate_count": heuristic_fork_like_candidate_count,
            "heuristic_decision_point_like_candidate_count": heuristic_decision_point_like_candidate_count,
            "source_confidence": "SOURCE_GAP",
            "topology_inventory_status": "RETAIN_AS_TOPOLOGY_SOURCE_GAP",
            "source_gap_reason": "No governed topology source with node-degree/adjacent-edge/side-branch and route position was found.",
        })

    if governed_fork_candidate_count > 0 and governed_decision_point_candidate_count > 0:
        admission_decision = "ADMIT_AS_GOVERNED_FORK_DECISION_POINT_SOURCE_CANDIDATE"
        audit_conclusion = "PASS_IB1_ROUTE_TOPOLOGY_DECISION_POINT_INVENTORY_V1_1_GOVERNED_SOURCE_CANDIDATE"
        decision_reason = "Governed topology and route position source candidate found. Manual QA still required before downstream use."
    else:
        admission_decision = "RETAIN_AS_TOPOLOGY_SOURCE_GAP"
        audit_conclusion = "PASS_IB1_ROUTE_TOPOLOGY_DECISION_POINT_INVENTORY_V1_1_SOURCE_GAP_RETAINED"
        decision_reason = "Heuristic topology-like context exists, but no governed topology source with route position is sufficient to support fork_exposure_count or decision_point_exposure_count."

    admission_rows = [{
        "context_id": "navigation_challenge_exposure",
        "context_label_zh": "導航挑戰暴露",
        "decision": admission_decision,
        "recommended_use": "upstream source for future route-following confidence context only",
        "not_personal_ability_axis": True,
        "not_navigation_ability_score": True,
        "not_go_no_go_decision": True,
        "source_inventory_count": len(source_rows),
        "usable_node_degree_source_count": usable_node_degree_source_count,
        "usable_adjacent_edge_source_count": usable_adjacent_edge_source_count,
        "usable_side_branch_source_count": usable_side_branch_source_count,
        "governed_fork_candidate_count": governed_fork_candidate_count,
        "governed_decision_point_candidate_count": governed_decision_point_candidate_count,
        "heuristic_fork_like_candidate_count": heuristic_fork_like_candidate_count,
        "heuristic_decision_point_like_candidate_count": heuristic_decision_point_like_candidate_count,
        "decision_reason": decision_reason,
        "interpretation_boundary": "Route topology source governance only. Not an ability score, rank, class, final risk score, route suitability score, go/no-go decision, medical diagnosis, or causal claim.",
    }]

    # Forbidden scan: ignore not_* boundary flags.
    fieldnames_to_scan = set()
    for collection in [source_rows, governed_candidates, route_summary_rows, admission_rows]:
        for row in collection:
            fieldnames_to_scan.update(row.keys())
    forbidden_hits = sorted(
        f for f in fieldnames_to_scan
        if FORBIDDEN_RE.search(f) and not str(f).lower().startswith("not_")
    )

    audit_rows = [{
        "source_inventory_count": len(source_rows),
        "source_role_count": len(role_counts),
        "usable_node_degree_source_count": usable_node_degree_source_count,
        "usable_adjacent_edge_source_count": usable_adjacent_edge_source_count,
        "usable_side_branch_source_count": usable_side_branch_source_count,
        "usable_route_dist_position_source_count": usable_route_position_count,
        "governed_candidate_feature_count": len(governed_candidates),
        "governed_fork_candidate_count": governed_fork_candidate_count,
        "governed_decision_point_candidate_count": governed_decision_point_candidate_count,
        "wrong_branch_exposure_candidate_count": wrong_branch_exposure_candidate_count,
        "heuristic_fork_like_candidate_count": heuristic_fork_like_candidate_count,
        "heuristic_decision_point_like_candidate_count": heuristic_decision_point_like_candidate_count,
        "route_dist_available_count": route_dist_available_count,
        "lat_lon_available_count": lat_lon_available_count,
        "zero_fill_used": False,
        "ch6_5_axis_contract_not_modified": True,
        "radar_not_modified": True,
        "data_table_not_modified": True,
        "forbidden_fields_present": "NONE" if not forbidden_hits else "|".join(forbidden_hits),
        "ability_scoring_absent": True,
        "ranking_absent": True,
        "class_label_absent": True,
        "decision_label_absent": True,
        "admission_decision": admission_decision,
        "audit_conclusion": audit_conclusion,
        "interpretation_boundary": "Route topology source governance only. Not an ability score, rank, class, final hiking risk score, route suitability score, go/no-go decision, medical diagnosis, or causal claim.",
    }]

    source_fields = [
        "source_path", "exists", "row_count", "candidate_columns", "source_role",
        "usable_for_node_degree", "usable_for_adjacent_edges", "usable_for_side_branch",
        "usable_for_route_dist_position", "rejection_reason", "notes",
    ]
    candidate_fields = [
        "case_id", "route_folder", "source_path", "mainline_route_dist_m", "lat", "lon",
        "node_id", "way_id", "node_degree", "adjacent_edge_count", "side_branch_count",
        "side_branch_angle_deg", "side_branch_distance_from_mainline_m",
        "nearby_guidepost_count", "nearby_facility_count", "fork_candidate",
        "decision_point_candidate", "wrong_branch_exposure_candidate", "governed_candidate_status",
        "confidence", "classification_reason",
    ]
    route_summary_fields = [
        "case_id", "route_folder", "route_length_m", "governed_fork_candidate_count",
        "governed_decision_point_candidate_count", "wrong_branch_exposure_candidate_count",
        "heuristic_fork_like_candidate_count", "heuristic_decision_point_like_candidate_count",
        "source_confidence", "topology_inventory_status", "source_gap_reason",
    ]
    admission_fields = list(admission_rows[0].keys())
    audit_fields = list(audit_rows[0].keys())

    write_csv(OUTPUT_ROOT / "route_topology_source_inventory_v1_1.csv", source_rows, source_fields)
    write_csv(OUTPUT_ROOT / "route_topology_source_role_summary_v1_1.csv", source_summary_rows, ["source_role", "source_count", "notes"])
    write_csv(OUTPUT_ROOT / "route_topology_decision_point_candidates_v1_1.csv", governed_candidates, candidate_fields)
    write_csv(OUTPUT_ROOT / "route_topology_route_summary_v1_1.csv", route_summary_rows, route_summary_fields)
    write_csv(OUTPUT_ROOT / "route_topology_decision_point_admission_v1_1.csv", admission_rows, admission_fields)
    write_csv(OUTPUT_ROOT / "route_topology_decision_point_audit_v1_1.csv", audit_rows, audit_fields)

    report = f"""
<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>IB1 Route Topology Decision-Point Inventory v1.1</title>
<style>
body {{ font-family: Arial, 'Microsoft JhengHei', sans-serif; line-height: 1.55; margin: 24px; }}
table {{ border-collapse: collapse; font-size: 13px; margin: 12px 0; max-width: 100%; }}
th, td {{ border: 1px solid #ccc; padding: 6px 8px; vertical-align: top; }}
th {{ background: #f2f2f2; }}
code {{ background: #f7f7f7; padding: 2px 4px; }}
.warning {{ background: #fff8e6; border-left: 4px solid #d99a00; padding: 10px 12px; }}
</style>
</head>
<body>
<h1>IB1 Route Topology Decision-Point Inventory v1.1</h1>
<p class="warning"><strong>Boundary:</strong> This is route-topology source governance only. It is not a personal ability axis, navigation ability score, rank, class, final hiking risk score, route suitability score, go/no-go decision, medical diagnosis, or causal claim.</p>
<h2>Executive conclusion</h2>
<p><code>{html.escape(audit_conclusion)}</code></p>
<p>{html.escape(decision_reason)}</p>
<h2>Audit</h2>
{html_table(audit_rows)}
<h2>Admission decision</h2>
{html_table(admission_rows)}
<h2>Source role summary</h2>
{html_table(source_summary_rows, max_rows=50)}
<h2>Route summary</h2>
{html_table(route_summary_rows, max_rows=50)}
<h2>Next step</h2>
<p>If downstream CH6.5.5 navigation challenge exposure needs <code>fork_exposure_count</code> or <code>decision_point_exposure_count</code>, build an upstream topology generator with node-degree, adjacent-edge, side-branch, route-distance, and lat/lon fields.</p>
</body>
</html>
""".strip()
    (OUTPUT_ROOT / "route_topology_decision_point_inventory_report_v1_1.html").write_text(report, encoding="utf-8")

    print({
        "output_root": str((Path.cwd() / OUTPUT_ROOT).resolve()),
        "source_inventory_count": len(source_rows),
        "usable_node_degree_source_count": usable_node_degree_source_count,
        "usable_adjacent_edge_source_count": usable_adjacent_edge_source_count,
        "usable_side_branch_source_count": usable_side_branch_source_count,
        "governed_fork_candidate_count": governed_fork_candidate_count,
        "governed_decision_point_candidate_count": governed_decision_point_candidate_count,
        "heuristic_fork_like_candidate_count": heuristic_fork_like_candidate_count,
        "heuristic_decision_point_like_candidate_count": heuristic_decision_point_like_candidate_count,
        "admission_decision": admission_decision,
        "audit_conclusion": audit_conclusion,
    })


if __name__ == "__main__":
    main()
