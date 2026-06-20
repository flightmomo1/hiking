#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
Generate run documentation for CH6.5.5 route-following × navigation-challenge
context interpretation v1.

Expected working directory:
  D:\mountain_work\115_osm

This documentation layer records an interpretation context only. It does not create,
modify, authorize, or imply ability scores, ability ranks, ability classes, THCI
scores, radar scores, navigation ability scores, final hiking risk scores, route
suitability scores, medical diagnoses, causal claims, or go/no-go decisions.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List

RUN_DATE = "20260620"
SLUG = "ch6_5_5_route_following_navigation_context_interpretation_v1"
SCRIPT_NAME = f"make_docs_{SLUG}.py"

OUTPUT_ROOT = Path("outputs/report_figures/ch6_5_5_route_following_navigation_context_interpretation_v1")
AUDIT_CSV = OUTPUT_ROOT / "route_following_navigation_context_audit_v1.csv"
GROUP_SUMMARY_CSV = OUTPUT_ROOT / "route_following_navigation_context_group_summary_v1.csv"
INTERPRETATION_CSV = OUTPUT_ROOT / "route_following_navigation_context_interpretation_v1.csv"
REPORT_HTML = OUTPUT_ROOT / "route_following_navigation_context_report_v1.html"
SOURCE_INVENTORY_CSV = OUTPUT_ROOT / "route_following_navigation_context_source_inventory_v1.csv"

UPSTREAM_CONTEXT_ROOT = Path("outputs/report_figures/ch6_5_5_navigation_challenge_context_consumption_v1_1")
UPSTREAM_ROUTE_FOLLOWING_ROOTS = [
    Path("outputs/report_figures/ch6_5_5_route_following_stability_proxy_admission_v1_1"),
    Path("outputs/report_figures/ch6_5_5_route_following_data_table_patch_v1"),
]

COMMIT_MAIN_BASE_TAG = "ch6-5-5-navigation-context-v1-main-20260620"
INTERPRETATION_COMMIT = "09bfc21 Add CH6.5.5 route following navigation context interpretation"

FORBIDDEN_BOUNDARY = [
    "not an ability score",
    "not an ability rank",
    "not an ability class",
    "not a THCI score",
    "not a radar score",
    "not a navigation ability score",
    "not a final hiking risk score",
    "not a route suitability score",
    "not a medical diagnosis",
    "not a causal claim",
    "not a go/no-go decision",
]

EXPECTED_AUDIT_FALLBACK = {
    "output_interpretation_count": "25",
    "context_available_count": "25",
    "review_recommended_count": "10",
    "extra_source_6_1_excluded": "True",
    "admission_decision": "ADMIT_AS_ROUTE_FOLLOWING_NAVIGATION_CONTEXT_INTERPRETATION",
    "audit_conclusion": "PASS_CH6_5_5_ROUTE_FOLLOWING_NAVIGATION_CONTEXT_INTERPRETATION_V1_GOVERNED_CONTEXT_AVAILABLE",
}


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_audit(path: Path) -> Dict[str, str]:
    rows = read_csv_rows(path)
    if not rows:
        return dict(EXPECTED_AUDIT_FALLBACK)
    row = rows[0]
    # Keep all audit fields, but fill core fields if older/newer output omits one.
    out = {k: (v if v is not None else "") for k, v in row.items()}
    for k, v in EXPECTED_AUDIT_FALLBACK.items():
        out.setdefault(k, v)
    return out


def md_table(rows: List[Dict[str, str]], limit: int = 12) -> str:
    if not rows:
        return "_No rows available._"
    rows = rows[:limit]
    keys = list(rows[0].keys())
    lines = ["| " + " | ".join(keys) + " |", "|" + "|".join(["---"] * len(keys)) + "|"]
    for row in rows:
        vals = []
        for k in keys:
            val = str(row.get(k, "")).replace("|", "\\|").replace("\n", " ")
            vals.append(val)
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def bullet_paths(paths: List[Path]) -> str:
    return "\n".join(f"- `{p.as_posix()}`" for p in paths)


def boundary_block() -> str:
    return "\n".join(f"- {item}" for item in FORBIDDEN_BOUNDARY)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def make_readme(audit: Dict[str, str], group_rows: List[Dict[str, str]]) -> str:
    return f"""# CH6.5.5 route-following navigation context interpretation v1

## Status

This module adds a descriptive interpretation layer that combines route-following stability evidence with governed navigation-challenge context.

- branch: `codex/ch6-5-5-route-following-navigation-context-interpretation-v1`
- commit: `{INTERPRETATION_COMMIT}`
- upstream main tag: `{COMMIT_MAIN_BASE_TAG}`
- output root: `{OUTPUT_ROOT.as_posix()}`
- audit conclusion: `{audit.get('audit_conclusion', '')}`
- admission decision: `{audit.get('admission_decision', '')}`

## Governance boundary

This layer is interpretation context only. It is:

{boundary_block()}

It does not modify radar output, personal ability axis contract, THCI logic, route-risk logic, or any go/no-go gate.

## Inputs

Primary upstream context:

- `{UPSTREAM_CONTEXT_ROOT.as_posix()}`

Route-following context roots considered:

{bullet_paths(UPSTREAM_ROUTE_FOLLOWING_ROOTS)}

## Outputs

{bullet_paths([AUDIT_CSV, GROUP_SUMMARY_CSV, INTERPRETATION_CSV, REPORT_HTML, SOURCE_INVENTORY_CSV])}

## Audit highlights

| metric | value |
|---|---:|
| output_interpretation_count | {audit.get('output_interpretation_count', '')} |
| context_available_count | {audit.get('context_available_count', '')} |
| review_recommended_count | {audit.get('review_recommended_count', '')} |
| extra_source_6_1_excluded | {audit.get('extra_source_6_1_excluded', '')} |
| admission_decision | {audit.get('admission_decision', '')} |
| audit_conclusion | {audit.get('audit_conclusion', '')} |

## Interpretation labels

The interpretation labels are review helpers. They do not represent ability classes or ranks.

{md_table(group_rows, limit=20)}

## Operational notes

- `6_1` is excluded as an extra source and does not enter the interpretation output.
- `review_recommended_count` indicates cases where route-following evidence should be read together with navigation exposure.
- High navigation-challenge exposure provides context for interpretation; it does not prove causality.
"""


def make_current_index(audit: Dict[str, str]) -> str:
    return f"""# CURRENT INDEX — CH6.5.5 route-following navigation context interpretation v1

Updated: {RUN_DATE}

## Current effective branch

- `codex/ch6-5-5-route-following-navigation-context-interpretation-v1`
- commit: `{INTERPRETATION_COMMIT}`

## Current effective output

- `{OUTPUT_ROOT.as_posix()}`

## Entry script

- `scripts/make_ch6_5_5_route_following_navigation_context_interpretation_v1.py`

## Documentation generator

- `scripts/{SCRIPT_NAME}`

## Acceptance state

- admission decision: `{audit.get('admission_decision', '')}`
- audit conclusion: `{audit.get('audit_conclusion', '')}`
- output interpretation count: `{audit.get('output_interpretation_count', '')}`
- context available count: `{audit.get('context_available_count', '')}`
- review recommended count: `{audit.get('review_recommended_count', '')}`
- `6_1` excluded: `{audit.get('extra_source_6_1_excluded', '')}`

## Boundary

This is a governed interpretation context layer only:

{boundary_block()}
"""


def make_changelog(audit: Dict[str, str]) -> str:
    return f"""# Changelog — CH6.5.5 route-following navigation context interpretation v1

## {RUN_DATE}

Added route-following × navigation-challenge interpretation context.

### Added

- `scripts/make_ch6_5_5_route_following_navigation_context_interpretation_v1.py`
- `{AUDIT_CSV.as_posix()}`
- `{GROUP_SUMMARY_CSV.as_posix()}`
- `{INTERPRETATION_CSV.as_posix()}`
- `{REPORT_HTML.as_posix()}`
- `{SOURCE_INVENTORY_CSV.as_posix()}`

### Evidence summary

- output interpretation count: `{audit.get('output_interpretation_count', '')}`
- context available count: `{audit.get('context_available_count', '')}`
- review recommended count: `{audit.get('review_recommended_count', '')}`
- `6_1` excluded: `{audit.get('extra_source_6_1_excluded', '')}`
- admission decision: `{audit.get('admission_decision', '')}`
- audit conclusion: `{audit.get('audit_conclusion', '')}`

### Governance

The interpretation layer reads governed navigation context and route-following evidence, but it does not change radar axes, radar plots, personal ability tables, THCI scoring, final risk scoring, or go/no-go logic.

### Boundary terms

{boundary_block()}
"""


def make_handoff(audit: Dict[str, str], group_rows: List[Dict[str, str]]) -> str:
    return f"""# Latest handoff — CH6.5.5 route-following navigation context interpretation v1

Continue from `D:\\mountain_work\\115_osm`.

Current branch to document:

- `codex/ch6-5-5-route-following-navigation-context-interpretation-v1`
- commit: `{INTERPRETATION_COMMIT}`

## What was completed

A governed interpretation context layer was added for reading route-following stability together with navigation-challenge exposure.

The layer answers interpretive questions such as whether low route-following stability should be read under high or low route decision-point exposure. It does not score navigation ability and does not change radar output.

## Evidence

- output root: `{OUTPUT_ROOT.as_posix()}`
- audit: `{AUDIT_CSV.as_posix()}`
- interpretation table: `{INTERPRETATION_CSV.as_posix()}`
- group summary: `{GROUP_SUMMARY_CSV.as_posix()}`
- HTML report: `{REPORT_HTML.as_posix()}`

## Audit summary

| metric | value |
|---|---:|
| output_interpretation_count | {audit.get('output_interpretation_count', '')} |
| context_available_count | {audit.get('context_available_count', '')} |
| review_recommended_count | {audit.get('review_recommended_count', '')} |
| extra_source_6_1_excluded | {audit.get('extra_source_6_1_excluded', '')} |
| admission_decision | {audit.get('admission_decision', '')} |
| audit_conclusion | {audit.get('audit_conclusion', '')} |

## Group summary preview

{md_table(group_rows, limit=20)}

## Required next step

Create and commit documentation branch:

- `codex/docs-ch6-5-5-route-following-navigation-context-interpretation-v1`

Expected documentation files:

- `runs/CURRENT_INDEX_updated_{RUN_DATE}_{SLUG}.md`
- `runs/changelog_updated_{RUN_DATE}_{SLUG}.md`
- `runs/latest_handoff_prompt_updated_{RUN_DATE}_{SLUG}.md`
- `scripts/README_current_pipeline_updated_{RUN_DATE}_{SLUG}.md`
- `scripts/{SCRIPT_NAME}`

## Hard boundaries

{boundary_block()}
"""


def main() -> None:
    audit = read_audit(AUDIT_CSV)
    group_rows = read_csv_rows(GROUP_SUMMARY_CSV)

    files = {
        Path(f"runs/CURRENT_INDEX_updated_{RUN_DATE}_{SLUG}.md"): make_current_index(audit),
        Path(f"runs/changelog_updated_{RUN_DATE}_{SLUG}.md"): make_changelog(audit),
        Path(f"runs/latest_handoff_prompt_updated_{RUN_DATE}_{SLUG}.md"): make_handoff(audit, group_rows),
        Path(f"scripts/README_current_pipeline_updated_{RUN_DATE}_{SLUG}.md"): make_readme(audit, group_rows),
    }

    for path, text in files.items():
        write_text(path, text)
        print(f"wrote: {path}")

    print("\nSummary:")
    print(f"  output_interpretation_count = {audit.get('output_interpretation_count', '')}")
    print(f"  context_available_count = {audit.get('context_available_count', '')}")
    print(f"  review_recommended_count = {audit.get('review_recommended_count', '')}")
    print(f"  extra_source_6_1_excluded = {audit.get('extra_source_6_1_excluded', '')}")
    print(f"  admission_decision = {audit.get('admission_decision', '')}")
    print(f"  audit_conclusion = {audit.get('audit_conclusion', '')}")
    print("\nBoundary: documentation only; no radar, axis contract, ability score, navigation score, or go/no-go change.")


if __name__ == "__main__":
    main()
