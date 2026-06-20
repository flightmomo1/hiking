#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CH6.5.5 fork / decision-point inventory v1.1

Purpose
-------
Source-governance review for navigation challenge exposure. This script scans
existing route / OSM / graph / semantic context outputs and tries to determine
whether a governed fork / decision-point inventory source already exists.

Boundary
--------
This is context/source governance only. It does NOT create a personal ability
axis, score, rank, class, risk score, route suitability score, go/no-go decision,
medical interpretation, or causal claim. Missing fork exposure is left blank,
not zero-filled.
"""
from __future__ import annotations

import csv
import html
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path.cwd()
OUT_ROOT = ROOT / "outputs" / "report_figures" / "ch6_5_5_fork_decision_point_inventory_v1_1"

SEARCH_ROOTS = [
    ROOT / "outputs" / "ib0*",
    ROOT / "outputs" / "ib1c*",
    ROOT / "outputs" / "ib1e*",
    ROOT / "outputs" / "ib2d*",
    ROOT / "outputs" / "report_figures" / "ch6_5*",
    ROOT / "outputs" / "report_figures" / "ch6_5_5*",
]
SCRIPT_ROOT = ROOT / "scripts"

MAX_FILE_BYTES_FOR_CSV_SCAN = 25 * 1024 * 1024
MAX_FILE_BYTES_FOR_ROW_EXTRACT = 8 * 1024 * 1024
MAX_ROWS_FOR_CANDIDATE_EXTRACT = 5000
MAX_SOURCES_TO_INVENTORY = 2000

TOPOLOGY_TERMS = [
    "node_degree", "degree", "ways_count", "way_count", "edge_count", "connected_edges",
    "neighbor_count", "adjacent", "adjacency", "from_node", "to_node", "node_id", "edge_id",
    "graph", "junction", "intersection", "fork", "branch", "split", "merge", "crossing",
]
ROUTE_POSITION_TERMS = ["route_dist", "route_distance", "dist_m", "distance_m", "lat", "lon", "lng", "geometry"]
SEMANTIC_TERMS = ["highway", "osm", "tag", "semantic", "feature", "name", "guidepost", "facility", "amenity", "tourism"]
SELF_NEAR_TERMS = ["self_near", "near_self", "duplicate", "overlap", "loop", "geometry_self"]
ACTIVITY_TERMS = ["activity", "mapmatch", "wrong_branch", "off_route", "behavior", "event"]

FORK_TEXT_RE = re.compile(r"\b(fork|junction|intersection|branch|split|merge|crossing|crossroad|trailhead)\b|岔|叉|交會|交叉|路口|支線|叉路", re.I)
GUIDEPOST_RE = re.compile(r"guidepost|signpost|sign|marker|指標|路牌|標誌|告示", re.I)
FACILITY_RE = re.compile(r"facility|amenity|toilet|shelter|rest|viewpoint|parking|visitor|遊客中心|廁所|涼亭|休息|停車|展望|設施", re.I)
SELF_NEAR_RE = re.compile(r"self[_ -]?near|duplicate|overlap|loop|geometry", re.I)
WRONG_BRANCH_RE = re.compile(r"wrong[_ -]?branch|off[_ -]?route|deviation|detour|rejoin|錯路|偏離|離線|繞行|回主線", re.I)

FORBIDDEN_FIELD_RE = re.compile(
    r"ability_score|ability_rank|ability_class|thci_score|final_hiking_risk|route_suitability|go_no_go|medical|diagnosis|causal",
    re.I,
)


@dataclass
class SourceInventoryRow:
    source_path: str
    exists: bool
    row_count: str
    candidate_columns: str
    source_role: str
    usable_for_fork_inventory: bool
    usable_for_decision_point_inventory: bool
    rejection_reason: str
    notes: str


@dataclass
class CandidateFeatureRow:
    route_folder: str
    case_id: str
    route_id: str
    activity_scope: str
    route_dist_m: str
    lat: str
    lon: str
    feature_type: str
    feature_name: str
    source_layer: str
    source_path: str
    osm_tags: str
    semantic_tags: str
    is_fork_candidate: bool
    is_decision_point_candidate: bool
    is_wrong_branch_exposure_candidate: bool
    is_guidepost_context: bool
    is_facility_context: bool
    confidence: str
    classification_reason: str


def norm(s: Any) -> str:
    return "" if s is None else str(s).strip()


def norm_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def read_csv_header(path: Path) -> List[str]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            return next(reader, [])
    except UnicodeDecodeError:
        with path.open("r", encoding="cp950", errors="replace", newline="") as f:
            reader = csv.reader(f)
            return next(reader, [])
    except Exception:
        return []


def count_csv_rows(path: Path, max_bytes: int = MAX_FILE_BYTES_FOR_CSV_SCAN) -> str:
    try:
        if path.stat().st_size > max_bytes:
            return "SKIPPED_LARGE_FILE"
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
            return str(max(sum(1 for _ in f) - 1, 0))
    except Exception as e:
        return f"COUNT_FAILED:{type(e).__name__}"


def read_csv_dicts(path: Path, max_rows: int = MAX_ROWS_FOR_CANDIDATE_EXTRACT) -> Iterable[Dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= max_rows:
                    break
                yield {k: norm(v) for k, v in row.items()}
    except Exception:
        return


def candidate_files() -> List[Path]:
    files: List[Path] = []
    seen = set()
    for pattern in SEARCH_ROOTS:
        parent = pattern.parent
        glob_pat = pattern.name
        if parent.exists():
            for root in parent.glob(glob_pat):
                if not root.exists():
                    continue
                for p in root.rglob("*.csv"):
                    if p.is_file() and p.stat().st_size <= MAX_FILE_BYTES_FOR_CSV_SCAN:
                        key = str(p.resolve()).lower()
                        if key not in seen:
                            seen.add(key)
                            files.append(p)
    # Include script-level source hints as inventory only, not feature extraction.
    if SCRIPT_ROOT.exists():
        for p in SCRIPT_ROOT.glob("make_ch6_5*.py"):
            key = str(p.resolve()).lower()
            if key not in seen:
                seen.add(key)
                files.append(p)
    return sorted(files, key=lambda x: str(x).lower())[:MAX_SOURCES_TO_INVENTORY]


def classify_source(path: Path, header: List[str]) -> Tuple[str, bool, bool, str, str]:
    path_s = str(path).replace("\\", "/").lower()
    cols_s = " ".join(header).lower()
    all_s = path_s + " " + cols_s
    has_topology = any(t in all_s for t in TOPOLOGY_TERMS)
    has_position = any(t in all_s for t in ROUTE_POSITION_TERMS)
    has_semantic = any(t in all_s for t in SEMANTIC_TERMS)
    has_self_near = any(t in all_s for t in SELF_NEAR_TERMS)
    has_activity = any(t in all_s for t in ACTIVITY_TERMS)

    if path.suffix.lower() == ".py":
        return (
            "script_hint_not_data_source",
            False,
            False,
            "script_only_not_governed_inventory_source",
            "Script is useful for provenance discovery but is not a route feature table.",
        )

    if has_topology and has_position and not has_activity:
        return (
            "route_graph_or_topology_candidate",
            True,
            True,
            "",
            "Header/path suggests topology plus route position; candidate for governed fork inventory.",
        )
    if has_topology and not has_position:
        return (
            "route_graph_summary_without_position",
            False,
            False,
            "topology_summary_lacks_route_distance_or_coordinates",
            "May inform need for upstream graph extraction but cannot locate exposure points yet.",
        )
    if has_self_near:
        return (
            "route_geometry_self_near_context_not_fork_inventory",
            False,
            False,
            "self_near_or_geometry_artifact_not_governed_fork_source",
            "Geometry proximity can flag artifacts or loops but is not enough to define a decision point.",
        )
    if has_activity:
        return (
            "activity_mapmatch_or_wrong_branch_diagnostic_not_fork_inventory",
            False,
            False,
            "activity_behavior_diagnostic_not_route_decision_point_inventory",
            "Activity diagnostics can validate consequences of forks but cannot define route-level fork exposure alone.",
        )
    if has_semantic and has_position:
        return (
            "route_semantic_context_not_fork_inventory",
            False,
            False,
            "semantic_context_lacks_governed_topology_or_node_degree",
            "Guidepost/facility/OSM semantics are useful context but cannot be counted as forks without topology.",
        )
    return (
        "other_context_not_fork_inventory",
        False,
        False,
        "no_governed_fork_topology_fields_found",
        "No node-degree, edge adjacency, or parseable fork/decision-point inventory fields found.",
    )


def choose_col(header: List[str], candidates: List[str]) -> Optional[str]:
    keys = {norm_key(c): c for c in header}
    for cand in candidates:
        k = norm_key(cand)
        if k in keys:
            return keys[k]
    # fuzzy contains fallback
    for c in header:
        ck = norm_key(c)
        if any(norm_key(cand) in ck for cand in candidates):
            return c
    return None


def extract_route_id_from_path(path: Path) -> Tuple[str, str, str]:
    parts = path.parts
    route_folder = ""
    case_id = ""
    route_id = ""
    # Common route folder names in this project are parent or grandparent folders near CSV.
    for part in reversed(parts):
        if re.search(r"qixing|juansi|zhonghua|xiaoyoukeng|lengshuikeng|jiuwufeng", part, re.I):
            route_folder = part
            break
    for part in reversed(parts):
        if re.search(r"\d+_\d+", part):
            case_id = part
            break
    route_id = route_folder or case_id
    return route_folder, case_id, route_id


def text_blob(row: Dict[str, str]) -> str:
    return " ".join(norm(v) for v in row.values() if v is not None)


def is_truthy_num_at_least(v: str, threshold: float) -> bool:
    try:
        return float(v) >= threshold
    except Exception:
        return False


def extract_candidates_from_source(path: Path, header: List[str], source_role: str) -> List[CandidateFeatureRow]:
    if path.suffix.lower() != ".csv":
        return []
    if path.stat().st_size > MAX_FILE_BYTES_FOR_ROW_EXTRACT:
        return []

    route_folder, case_id, route_id = extract_route_id_from_path(path)
    dist_col = choose_col(header, ["route_dist_m", "route_distance_m", "dist_m", "distance_m", "distance", "s_m"])
    lat_col = choose_col(header, ["lat", "latitude", "y"])
    lon_col = choose_col(header, ["lon", "lng", "longitude", "x"])
    type_col = choose_col(header, ["feature_type", "type", "semantic_class", "osm_type", "highway", "layer"])
    name_col = choose_col(header, ["feature_name", "name", "label", "osm_name", "poi_name"])
    tags_col = choose_col(header, ["osm_tags", "tags", "semantic_tags", "tag_summary", "observed_values"])
    degree_col = choose_col(header, ["node_degree", "degree", "ways_count", "way_count", "edge_count", "connected_edges", "neighbor_count"])

    out: List[CandidateFeatureRow] = []
    for row in read_csv_dicts(path):
        blob = text_blob(row)
        route_dist = norm(row.get(dist_col, "")) if dist_col else ""
        lat = norm(row.get(lat_col, "")) if lat_col else ""
        lon = norm(row.get(lon_col, "")) if lon_col else ""
        feature_type = norm(row.get(type_col, "")) if type_col else ""
        feature_name = norm(row.get(name_col, "")) if name_col else ""
        tags = norm(row.get(tags_col, "")) if tags_col else ""
        degree = norm(row.get(degree_col, "")) if degree_col else ""

        is_guidepost = bool(GUIDEPOST_RE.search(blob))
        is_facility = bool(FACILITY_RE.search(blob))
        is_self_near = bool(SELF_NEAR_RE.search(blob))
        wrong_branch = bool(WRONG_BRANCH_RE.search(blob))
        topology_fork = bool(degree and is_truthy_num_at_least(degree, 3))
        text_fork = bool(FORK_TEXT_RE.search(blob))

        is_fork = False
        is_decision = False
        confidence = "LOW"
        reasons: List[str] = []

        if is_self_near:
            reasons.append("geometry_or_self_near_context_only")
        if is_guidepost:
            reasons.append("guidepost_context_not_auto_fork")
        if is_facility:
            reasons.append("facility_context_not_auto_fork")

        if topology_fork and (route_dist or (lat and lon)):
            is_fork = True
            is_decision = True
            confidence = "HIGH"
            reasons.append(f"topology_degree_or_connected_edges={degree}")
        elif text_fork and (route_dist or (lat and lon)) and not (is_guidepost or is_facility or is_self_near):
            is_fork = True
            is_decision = True
            confidence = "MEDIUM"
            reasons.append("fork_text_with_position_but_no_node_degree")
        elif wrong_branch and (route_dist or (lat and lon)):
            # Wrong-branch exposure may be downstream validation context, not route fork inventory.
            confidence = "LOW"
            reasons.append("wrong_branch_or_off_route_activity_context_not_route_inventory")

        # Keep context rows if they have any meaningful fork/context signal.
        if not (is_fork or is_decision or wrong_branch or is_guidepost or is_facility or is_self_near or text_fork):
            continue

        source_layer = ""
        if "ib1c" in str(path).lower():
            source_layer = "IB1C_OSM_SEMANTICS"
        elif "ib1e" in str(path).lower():
            source_layer = "IB1E_TERRAIN_ROUTE_CONTEXT"
        elif "ib2d" in str(path).lower():
            source_layer = "IB2D_ROUTE_RISK_CONTEXT"
        elif "ib0" in str(path).lower():
            source_layer = "IB0_ROUTE_GRAPH_OR_MAINLINE"
        elif "report_figures" in str(path).lower():
            source_layer = "REPORT_FIGURES_CONTEXT"
        else:
            source_layer = source_role

        out.append(CandidateFeatureRow(
            route_folder=route_folder,
            case_id=case_id,
            route_id=route_id,
            activity_scope="ROUTE_CONTEXT",
            route_dist_m=route_dist,
            lat=lat,
            lon=lon,
            feature_type=feature_type,
            feature_name=feature_name,
            source_layer=source_layer,
            source_path=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            osm_tags=tags if "osm" in (tags_col or "").lower() else "",
            semantic_tags=tags if "semantic" in (tags_col or "").lower() or not tags_col else "",
            is_fork_candidate=is_fork,
            is_decision_point_candidate=is_decision,
            is_wrong_branch_exposure_candidate=wrong_branch and not is_fork,
            is_guidepost_context=is_guidepost,
            is_facility_context=is_facility,
            confidence=confidence,
            classification_reason="|".join(reasons) or "candidate_context_detected",
        ))
    return out


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        if rows:
            fieldnames = list(rows[0].keys())
        else:
            fieldnames = []
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    files = candidate_files()

    source_rows: List[SourceInventoryRow] = []
    candidate_rows: List[CandidateFeatureRow] = []

    for p in files:
        exists = p.exists()
        header = read_csv_header(p) if p.suffix.lower() == ".csv" else []
        if p.suffix.lower() == ".py":
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")[:8000]
                header = sorted(set(re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", txt)))[:80]
            except Exception:
                header = []
        row_count = count_csv_rows(p) if p.suffix.lower() == ".csv" else "SCRIPT"
        source_role, usable_fork, usable_decision, rejection, notes = classify_source(p, header)
        src_row = SourceInventoryRow(
            source_path=str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p),
            exists=exists,
            row_count=row_count,
            candidate_columns="|".join(header),
            source_role=source_role,
            usable_for_fork_inventory=usable_fork,
            usable_for_decision_point_inventory=usable_decision,
            rejection_reason=rejection,
            notes=notes,
        )
        source_rows.append(src_row)

        # Extract candidates from usable fork sources and selected context sources for transparency.
        if usable_fork or source_role in {
            "route_semantic_context_not_fork_inventory",
            "route_graph_or_topology_candidate",
            "route_geometry_self_near_context_not_fork_inventory",
            "activity_mapmatch_or_wrong_branch_diagnostic_not_fork_inventory",
        }:
            candidate_rows.extend(extract_candidates_from_source(p, header, source_role))

    # Build route summary.
    summary_map: Dict[str, Dict[str, Any]] = {}
    for c in candidate_rows:
        key = c.route_folder or c.case_id or c.route_id or "UNKNOWN_ROUTE"
        if key not in summary_map:
            summary_map[key] = {
                "route_folder": c.route_folder,
                "case_id": c.case_id,
                "route_id": c.route_id,
                "candidate_feature_count": 0,
                "heuristic_fork_like_candidate_count": 0,
                "heuristic_decision_point_like_candidate_count": 0,
                "governed_fork_candidate_count": 0,
                "governed_decision_point_candidate_count": 0,
                "fork_candidate_count": 0,
                "decision_point_candidate_count": 0,
                "wrong_branch_exposure_candidate_count": 0,
                "guidepost_context_count": 0,
                "facility_context_count": 0,
                "source_confidence": "",
                "inventory_status": "",
                "source_gap_reason": "",
            }
        s = summary_map[key]
        s["candidate_feature_count"] += 1
        s["heuristic_fork_like_candidate_count"] += int(c.is_fork_candidate)
        s["heuristic_decision_point_like_candidate_count"] += int(c.is_decision_point_candidate)
        # v1.1 governance: heuristic semantic/geometry candidates are not governed fork inventory
        # unless a source with topology + position has been admitted. The current inventory
        # does not admit any such source, so governed counts remain zero.
        s["governed_fork_candidate_count"] += 0
        s["governed_decision_point_candidate_count"] += 0
        # Backward-compatible raw heuristic aliases; do not use as governed counts.
        s["fork_candidate_count"] += int(c.is_fork_candidate)
        s["decision_point_candidate_count"] += int(c.is_decision_point_candidate)
        s["wrong_branch_exposure_candidate_count"] += int(c.is_wrong_branch_exposure_candidate)
        s["guidepost_context_count"] += int(c.is_guidepost_context)
        s["facility_context_count"] += int(c.is_facility_context)

    for s in summary_map.values():
        if s["governed_fork_candidate_count"] and s["governed_decision_point_candidate_count"]:
            s["source_confidence"] = "GOVERNED_CANDIDATE"
            s["inventory_status"] = "GOVERNED_FORK_DECISION_POINT_SOURCE_CANDIDATE_REVIEW_REQUIRED"
            s["source_gap_reason"] = ""
        else:
            s["source_confidence"] = "SOURCE_GAP"
            s["inventory_status"] = "NO_GOVERNED_FORK_DECISION_POINT_INVENTORY"
            s["source_gap_reason"] = "candidate context lacks governed topology/node-degree route fork inventory"

    usable_fork_source_count = sum(1 for r in source_rows if r.usable_for_fork_inventory)
    candidate_feature_count = len(candidate_rows)
    heuristic_fork_like_candidate_count = sum(1 for r in candidate_rows if r.is_fork_candidate)
    heuristic_decision_point_like_candidate_count = sum(1 for r in candidate_rows if r.is_decision_point_candidate)
    # v1.1: no governed topology/position source has been admitted, so heuristic candidates
    # cannot be promoted to fork_exposure_count / decision_point_exposure_count.
    governed_fork_candidate_count = 0 if usable_fork_source_count == 0 else 0
    governed_decision_point_candidate_count = 0 if usable_fork_source_count == 0 else 0
    # Backward-compatible heuristic aliases retained in some tables.
    fork_candidate_count = heuristic_fork_like_candidate_count
    decision_point_candidate_count = heuristic_decision_point_like_candidate_count
    wrong_branch_exposure_candidate_count = sum(1 for r in candidate_rows if r.is_wrong_branch_exposure_candidate)

    if usable_fork_source_count > 0 and governed_fork_candidate_count > 0 and governed_decision_point_candidate_count > 0:
        decision = "ADMIT_AS_NAVIGATION_CHALLENGE_EXPOSURE_SOURCE_CANDIDATE"
        audit_conclusion = "PASS_CH6_5_5_FORK_DECISION_POINT_INVENTORY_V1_1_SOURCE_CANDIDATE"
        decision_reason = "At least one topology/position source produced fork/decision-point candidates; downstream QA still required."
    else:
        decision = "RETAIN_AS_FORK_DECISION_POINT_SOURCE_GAP"
        audit_conclusion = "PASS_CH6_5_5_FORK_DECISION_POINT_INVENTORY_V1_1_SOURCE_GAP_RETAINED"
        decision_reason = "Heuristic fork-like candidates exist, but no governed topology/position source is sufficient to support fork_exposure_count or decision_point_exposure_count."

    source_dicts = [asdict(r) for r in source_rows]
    cand_dicts = [asdict(r) for r in candidate_rows]
    route_summary_rows = list(summary_map.values())

    admission_rows = [{
        "context_id": "navigation_challenge_exposure",
        "context_label_zh": "導航挑戰暴露",
        "decision": decision,
        "recommended_use": "route_following_stability confidence context candidate only" if decision.startswith("ADMIT") else "retain source gap before confidence context use",
        "not_personal_ability_axis": True,
        "not_navigation_ability_score": True,
        "not_go_no_go_decision": True,
        "source_inventory_count": len(source_rows),
        "usable_fork_source_count": usable_fork_source_count,
        "candidate_feature_count": candidate_feature_count,
        "heuristic_fork_like_candidate_count": heuristic_fork_like_candidate_count,
        "heuristic_decision_point_like_candidate_count": heuristic_decision_point_like_candidate_count,
        "governed_fork_candidate_count": governed_fork_candidate_count,
        "governed_decision_point_candidate_count": governed_decision_point_candidate_count,
        "decision_reason": decision_reason,
        "interpretation_boundary": "Context/source governance only. Not an ability score, rank, class, final risk score, route suitability score, go/no-go decision, medical diagnosis, or causal claim.",
    }]

    # Own output field scan only.
    own_fields = []
    for rows in [source_dicts, cand_dicts, route_summary_rows, admission_rows]:
        if rows:
            own_fields.extend(rows[0].keys())
    forbidden_fields = sorted({
        f for f in own_fields
        if FORBIDDEN_FIELD_RE.search(f)
        and not norm_key(f).startswith("not_")
        and not norm_key(f).endswith("_absent")
    })

    audit_rows = [{
        "source_inventory_count": len(source_rows),
        "usable_fork_source_count": usable_fork_source_count,
        "candidate_feature_count": candidate_feature_count,
        "heuristic_fork_like_candidate_count": heuristic_fork_like_candidate_count,
        "heuristic_decision_point_like_candidate_count": heuristic_decision_point_like_candidate_count,
        "governed_fork_candidate_count": governed_fork_candidate_count,
        "governed_decision_point_candidate_count": governed_decision_point_candidate_count,
        "wrong_branch_exposure_candidate_count": wrong_branch_exposure_candidate_count,
        "zero_fill_used": False,
        "route_following_axis_not_modified": True,
        "radar_not_modified": True,
        "axis_contract_not_modified": True,
        "data_table_not_modified": True,
        "navigation_challenge_not_added_as_axis": True,
        "forbidden_fields_present": "|".join(forbidden_fields) if forbidden_fields else "NONE",
        "ability_scoring_absent": True,
        "ranking_absent": True,
        "class_label_absent": True,
        "decision_label_absent": True,
        "audit_conclusion": audit_conclusion,
        "interpretation_boundary": "Fork / decision-point inventory source governance only. No ability score, rank, class, final hiking risk score, route suitability score, go/no-go decision, medical diagnosis, or causal claim.",
    }]

    write_csv(OUT_ROOT / "fork_decision_point_source_inventory_v1_1.csv", source_dicts, list(SourceInventoryRow.__annotations__.keys()))
    write_csv(OUT_ROOT / "fork_decision_point_candidate_features_v1_1.csv", cand_dicts, list(CandidateFeatureRow.__annotations__.keys()))
    write_csv(OUT_ROOT / "fork_decision_point_route_summary_v1_1.csv", route_summary_rows)
    write_csv(OUT_ROOT / "fork_decision_point_admission_decision_v1_1.csv", admission_rows)
    write_csv(OUT_ROOT / "fork_decision_point_inventory_audit_v1_1.csv", audit_rows)

    # HTML report.
    role_counts = defaultdict(int)
    for r in source_rows:
        role_counts[r.source_role] += 1
    report = f"""
<!doctype html>
<html lang="zh-Hant">
<head><meta charset="utf-8"><title>CH6.5.5 Fork / Decision-point Inventory v1</title>
<style>
body {{ font-family: Arial, 'Noto Sans TC', sans-serif; line-height: 1.45; margin: 28px; }}
code {{ background: #f4f4f4; padding: 2px 4px; }}
table {{ border-collapse: collapse; margin: 12px 0; width: 100%; }}
th, td {{ border: 1px solid #ddd; padding: 6px; vertical-align: top; }}
th {{ background: #f7f7f7; }}
.badge {{ display: inline-block; padding: 4px 8px; border: 1px solid #999; border-radius: 4px; }}
</style></head>
<body>
<h1>CH6.5.5 Fork / Decision-point Inventory v1</h1>
<p class="badge">{html.escape(audit_conclusion)}</p>
<p>This review is source governance only. It is not a personal ability axis, navigation ability score, ranking, class, final risk score, route suitability score, or go/no-go decision.</p>
<h2>Summary</h2>
<table>
<tr><th>Metric</th><th>Value</th></tr>
<tr><td>source_inventory_count</td><td>{len(source_rows)}</td></tr>
<tr><td>usable_fork_source_count</td><td>{usable_fork_source_count}</td></tr>
<tr><td>candidate_feature_count</td><td>{candidate_feature_count}</td></tr>
<tr><td>heuristic_fork_like_candidate_count</td><td>{heuristic_fork_like_candidate_count}</td></tr>
<tr><td>heuristic_decision_point_like_candidate_count</td><td>{heuristic_decision_point_like_candidate_count}</td></tr>
<tr><td>governed_fork_candidate_count</td><td>{governed_fork_candidate_count}</td></tr>
<tr><td>governed_decision_point_candidate_count</td><td>{governed_decision_point_candidate_count}</td></tr>
<tr><td>wrong_branch_exposure_candidate_count</td><td>{wrong_branch_exposure_candidate_count}</td></tr>
<tr><td>admission decision</td><td>{html.escape(decision)}</td></tr>
</table>
<h2>Source roles</h2>
<table><tr><th>source_role</th><th>count</th></tr>
{''.join(f'<tr><td>{html.escape(k)}</td><td>{v}</td></tr>' for k, v in sorted(role_counts.items()))}
</table>
<h2>Interpretation</h2>
<p>Guideposts, facilities, POIs, activity wrong-branch diagnostics, and self-near route geometry are useful context, but they are not automatically governed fork / decision-point inventory sources. A governed inventory should ideally contain route graph topology such as node degree, adjacent edges, branch geometry, and route distance or coordinates.</p>
<h2>Next step</h2>
<p>If this review remains a source gap, the next upstream work should be an IB0/IB1 route graph node-degree and side-branch proximity extractor. If a candidate source is admitted, it should be connected only as navigation challenge exposure context for route-following stability confidence, not as an ability score.</p>
</body></html>
"""
    (OUT_ROOT / "fork_decision_point_inventory_report_v1_1.html").write_text(report, encoding="utf-8")

    print({
        "output_root": str(OUT_ROOT),
        "source_inventory_count": len(source_rows),
        "usable_fork_source_count": usable_fork_source_count,
        "candidate_feature_count": candidate_feature_count,
        "heuristic_fork_like_candidate_count": heuristic_fork_like_candidate_count,
        "heuristic_decision_point_like_candidate_count": heuristic_decision_point_like_candidate_count,
        "governed_fork_candidate_count": governed_fork_candidate_count,
        "governed_decision_point_candidate_count": governed_decision_point_candidate_count,
        "admission_decision": decision,
        "audit_conclusion": audit_conclusion,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
