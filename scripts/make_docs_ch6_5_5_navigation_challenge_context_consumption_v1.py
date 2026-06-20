#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create documentation handoff files for CH6.5.5 navigation challenge context consumption v1.1.

This script only writes documentation files:
- runs/CURRENT_INDEX_updated_20260620_ch6_5_5_navigation_challenge_context_consumption_v1.md
- runs/changelog_updated_20260620_ch6_5_5_navigation_challenge_context_consumption_v1.md
- runs/latest_handoff_prompt_updated_20260620_ch6_5_5_navigation_challenge_context_consumption_v1.md
- scripts/README_current_pipeline_updated_20260620_ch6_5_5_navigation_challenge_context_consumption_v1.md

It does not modify CH6.5 axis contracts, data tables, radar plots, or generated evidence outputs.
"""
from __future__ import annotations

import csv
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
SCRIPTS = ROOT / "scripts"

DATE_TAG = "20260620"
DOC_STEM = "ch6_5_5_navigation_challenge_context_consumption_v1"

EVIDENCE_ROOT = ROOT / "outputs" / "report_figures" / "ch6_5_5_navigation_challenge_context_consumption_v1_1"
TOPOLOGY_ROOT = ROOT / "outputs" / "report_figures" / "ib1_route_topology_generator_node_degree_v1_1"

AUDIT_CSV = EVIDENCE_ROOT / "navigation_challenge_context_consumption_audit_v1_1.csv"
ADMISSION_CSV = EVIDENCE_ROOT / "navigation_challenge_context_consumption_admission_v1_1.csv"
ROUTE_CONTEXT_CSV = EVIDENCE_ROOT / "route_navigation_challenge_context_v1_1.csv"
ACTIVITY_CONTEXT_CSV = EVIDENCE_ROOT / "activity_navigation_challenge_context_v1_1.csv"
ROUTE_FOLLOWING_CONTEXT_CSV = EVIDENCE_ROOT / "route_following_with_navigation_context_v1_1.csv"
REPORT_HTML = EVIDENCE_ROOT / "navigation_challenge_context_consumption_report_v1_1.html"
SCRIPT_PATH = SCRIPTS / "make_ch6_5_5_navigation_challenge_context_consumption_v1_1.py"
UPSTREAM_SCRIPT_PATH = SCRIPTS / "make_ib1_route_topology_generator_node_degree_v1_1.py"

CURRENT_INDEX = RUNS / f"CURRENT_INDEX_updated_{DATE_TAG}_{DOC_STEM}.md"
CHANGELOG = RUNS / f"changelog_updated_{DATE_TAG}_{DOC_STEM}.md"
HANDOFF = RUNS / f"latest_handoff_prompt_updated_{DATE_TAG}_{DOC_STEM}.md"
README = SCRIPTS / f"README_current_pipeline_updated_{DATE_TAG}_{DOC_STEM}.md"


def read_single_row_csv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return rows[0] if rows else {}


def count_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return max(sum(1 for _ in f) - 1, 0)


def safe(row: dict[str, str], key: str, default: str = "UNKNOWN") -> str:
    v = row.get(key, "")
    return v if v not in (None, "") else default


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    print(f"wrote: {path}")


def main() -> None:
    audit = read_single_row_csv(AUDIT_CSV)
    admission = read_single_row_csv(ADMISSION_CSV)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    activity_context_count = safe(audit, "activity_context_count", str(count_rows(ACTIVITY_CONTEXT_CSV)))
    joined_context_count = safe(audit, "joined_route_following_context_count", str(count_rows(ROUTE_FOLLOWING_CONTEXT_CSV)))
    route_context_count = safe(audit, "route_context_count", str(count_rows(ROUTE_CONTEXT_CSV)))
    missing_route_context_count = safe(audit, "missing_route_context_count", "UNKNOWN")
    default_binding_count = safe(audit, "default_activity_route_binding_count", "UNKNOWN")
    excluded_activity_ids = safe(audit, "excluded_activity_ids", "6_1")
    extra_excluded = safe(audit, "extra_source_6_1_excluded", "UNKNOWN")
    decision_points = safe(audit, "governed_decision_point_candidate_count_consumed", safe(admission, "governed_decision_point_candidate_count", "UNKNOWN"))
    fork_points = safe(audit, "governed_fork_candidate_count_consumed", safe(admission, "governed_fork_candidate_count", "UNKNOWN"))
    audit_conclusion = safe(audit, "audit_conclusion")
    admission_decision = safe(audit, "admission_decision", safe(admission, "decision"))
    topology_audit = safe(audit, "topology_audit_conclusion")
    topology_admission = safe(audit, "topology_admission_decision")

    governance_boundary = (
        "Navigation-challenge exposure context consumption only. Not a personal ability axis, "
        "ability score, rank, class, radar score, final hiking risk score, route suitability score, "
        "go/no-go decision, medical diagnosis, or causal claim."
    )

    current_index = f"""
# CURRENT INDEX — CH6.5.5 Navigation Challenge Context Consumption v1.1

Updated: {DATE_TAG}  
Generated at: {now}

## Current Recommended Evidence

Use **CH6.5.5 navigation challenge context consumption v1.1** as the current evidence layer for consuming upstream governed topology into route-following interpretation context.

- Branch: `codex/ch6-5-5-navigation-challenge-context-consumption-v1`
- Evidence commit: `0b596e4 Add CH6.5.5 navigation challenge context consumption`
- Upstream topology generator commit: `c4bebf9 Add IB1 route topology node degree generator`
- Output root: `{rel(EVIDENCE_ROOT)}`
- Script: `{rel(SCRIPT_PATH)}`
- HTML report: `{rel(REPORT_HTML)}`

## Current Result

| Field | Value |
|---|---:|
| route_context_count | {route_context_count} |
| activity_context_count | {activity_context_count} |
| joined_route_following_context_count | {joined_context_count} |
| missing_route_context_count | {missing_route_context_count} |
| default_activity_route_binding_count | {default_binding_count} |
| excluded_activity_ids | {excluded_activity_ids} |
| extra_source_6_1_excluded | {extra_excluded} |
| governed_decision_point_candidate_count_consumed | {decision_points} |
| governed_fork_candidate_count_consumed | {fork_points} |
| admission_decision | `{admission_decision}` |
| audit_conclusion | `{audit_conclusion}` |

## Interpretation

`navigation_challenge_exposure` has advanced from source gap to governed context source consumption.

The context is available for **route-following interpretation only**. It is not admitted as a personal ability axis, navigation ability score, radar score, ranking, class, route suitability score, or go/no-go decision.

## Governance Boundary

{governance_boundary}

## Do Not Supersede

This document does not supersede:

- CH6.5.5 personal ability radar v1.1 as governed limited proxy preview.
- CH6.5.5 route-following stability proxy admission / axis contract / data table patches.
- IB1 route topology node degree generator v1.1 as upstream topology source candidate.
"""

    changelog = f"""
# Changelog — CH6.5.5 Navigation Challenge Context Consumption v1.1

Updated: {DATE_TAG}  
Generated at: {now}

## Added

Added documentation for the CH6.5.5 navigation challenge context consumption layer.

Evidence branch:

- `codex/ch6-5-5-navigation-challenge-context-consumption-v1`

Evidence commit:

- `0b596e4 Add CH6.5.5 navigation challenge context consumption`

Script and output:

- `{rel(SCRIPT_PATH)}`
- `{rel(EVIDENCE_ROOT)}`

## Upstream Dependency

This layer consumes the upstream governed topology source candidate generated by:

- `{rel(UPSTREAM_SCRIPT_PATH)}`
- `{rel(TOPOLOGY_ROOT)}`
- audit: `{topology_audit}`
- admission: `{topology_admission}`

## Evidence Summary

| Field | Value |
|---|---:|
| route_context_count | {route_context_count} |
| activity_context_count | {activity_context_count} |
| joined_route_following_context_count | {joined_context_count} |
| missing_route_context_count | {missing_route_context_count} |
| excluded_activity_ids | {excluded_activity_ids} |
| extra_source_6_1_excluded | {extra_excluded} |
| governed_decision_point_candidate_count_consumed | {decision_points} |
| governed_fork_candidate_count_consumed | {fork_points} |
| admission_decision | `{admission_decision}` |
| audit_conclusion | `{audit_conclusion}` |

## Important Correction Preserved

The earlier v1 draft consumed 26 activities and included `6_1`, which is an extra/source-only activity and must not enter formal context consumption.

v1.1 fixes this by excluding `6_1`:

- `excluded_activity_ids = 6_1`
- `extra_source_6_1_excluded = True`
- activity context rows reduced to 25
- route-following context rows reduced to 25

## Boundary

{governance_boundary}

## Next Step

If continuing this line, consume `navigation_challenge_exposure` only as route-following interpretation context. Do not add it as a radar axis unless a separate governance decision explicitly admits such an axis.
"""

    handoff = f"""
# Latest Handoff Prompt — CH6.5.5 Navigation Challenge Context Consumption v1.1

Updated: {DATE_TAG}  
Generated at: {now}

Continue from `D:\\mountain_work\\115_osm`.

Current relevant branch:

- `codex/ch6-5-5-navigation-challenge-context-consumption-v1`

Current evidence commit:

- `0b596e4 Add CH6.5.5 navigation challenge context consumption`

Latest docs branch:

- `codex/docs-ch6-5-5-navigation-challenge-context-consumption-v1`

## Current Evidence Layer

CH6.5.5 navigation challenge context consumption v1.1 consumes the upstream IB1 route topology node-degree generator evidence as route-following interpretation context.

Key files:

- Script: `{rel(SCRIPT_PATH)}`
- Output root: `{rel(EVIDENCE_ROOT)}`
- Audit CSV: `{rel(EVIDENCE_ROOT / 'navigation_challenge_context_consumption_audit_v1_1.csv')}`
- Admission CSV: `{rel(EVIDENCE_ROOT / 'navigation_challenge_context_consumption_admission_v1_1.csv')}`
- Activity context CSV: `{rel(ACTIVITY_CONTEXT_CSV)}`
- Route-following context CSV: `{rel(ROUTE_FOLLOWING_CONTEXT_CSV)}`
- Report: `{rel(REPORT_HTML)}`

## Current Results

- `route_context_count = {route_context_count}`
- `activity_context_count = {activity_context_count}`
- `joined_route_following_context_count = {joined_context_count}`
- `missing_route_context_count = {missing_route_context_count}`
- `excluded_activity_ids = {excluded_activity_ids}`
- `extra_source_6_1_excluded = {extra_excluded}`
- `governed_decision_point_candidate_count_consumed = {decision_points}`
- `governed_fork_candidate_count_consumed = {fork_points}`
- `admission_decision = {admission_decision}`
- `audit_conclusion = {audit_conclusion}`

## Required Interpretation

`navigation_challenge_exposure` is now a governed context source available for route-following interpretation.

It is **not**:

- a personal ability axis
- a navigation ability score
- a radar score
- a final hiking risk score
- a route suitability score
- a go/no-go decision
- a medical diagnosis
- a causal claim

## Critical QA Note

Do not use the earlier v1 output that included 26 activities and consumed `6_1`. Use v1.1 only. Formal activity context count is 25, with `6_1` excluded.

## Recommended Next Work

If proceeding, build a small interpretation/report layer that explains route-following stability under navigation challenge exposure. Keep it as descriptive context and do not modify the radar axis contract or radar plot.
"""

    readme = f"""
# README — Current Pipeline Update: CH6.5.5 Navigation Challenge Context Consumption v1.1

Updated: {DATE_TAG}  
Generated at: {now}

## Purpose

This update documents the CH6.5.5 navigation-challenge exposure context consumption layer.

It consumes upstream governed topology evidence from IB1 route topology node-degree generator v1.1 and attaches route-level navigation-challenge context to CH6.5.5 route-following interpretation tables.

## Files

Script:

- `{rel(SCRIPT_PATH)}`

Output root:

- `{rel(EVIDENCE_ROOT)}`

Output files:

- `activity_navigation_challenge_context_v1_1.csv`
- `route_navigation_challenge_context_v1_1.csv`
- `route_following_with_navigation_context_v1_1.csv`
- `navigation_challenge_context_source_inventory_v1_1.csv`
- `navigation_challenge_context_consumption_admission_v1_1.csv`
- `navigation_challenge_context_consumption_audit_v1_1.csv`
- `navigation_challenge_context_consumption_report_v1_1.html`

## Upstream Input

- `{rel(TOPOLOGY_ROOT)}`
- `route_topology_decision_points_v1_1.csv`
- `route_topology_generator_audit_v1_1.csv`
- `route_topology_generator_admission_v1_1.csv`

## Audit Summary

| Field | Value |
|---|---:|
| topology_audit_conclusion | `{topology_audit}` |
| topology_admission_decision | `{topology_admission}` |
| route_context_count | {route_context_count} |
| activity_context_count | {activity_context_count} |
| joined_route_following_context_count | {joined_context_count} |
| missing_route_context_count | {missing_route_context_count} |
| default_activity_route_binding_count | {default_binding_count} |
| excluded_activity_ids | {excluded_activity_ids} |
| extra_source_6_1_excluded | {extra_excluded} |
| governed_decision_point_candidate_count_consumed | {decision_points} |
| governed_fork_candidate_count_consumed | {fork_points} |
| admission_decision | `{admission_decision}` |
| audit_conclusion | `{audit_conclusion}` |

## Governance Rules

- Do not add `navigation_challenge_exposure` as a personal ability radar axis in this branch.
- Do not produce navigation ability scores.
- Do not produce rankings or classes.
- Do not produce go/no-go decisions.
- Do not modify CH6.5 axis contract, radar plot, or existing radar data table.
- Keep `6_1` excluded from formal activity context consumption.

## Status

`navigation_challenge_exposure` is now a governed context source for route-following interpretation.
"""

    write(CURRENT_INDEX, current_index)
    write(CHANGELOG, changelog)
    write(HANDOFF, handoff)
    write(README, readme)


if __name__ == "__main__":
    main()
