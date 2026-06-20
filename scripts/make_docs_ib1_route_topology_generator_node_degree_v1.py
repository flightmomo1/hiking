from pathlib import Path
from datetime import datetime

ROOT = Path(r"D:\mountain_work\115_osm")
DATE = "20260620"
TAG = "ib1_route_topology_generator_node_degree_v1"

RUNS = ROOT / "runs"
SCRIPTS = ROOT / "scripts"

RUNS.mkdir(parents=True, exist_ok=True)
SCRIPTS.mkdir(parents=True, exist_ok=True)

FILES = {
    RUNS / f"CURRENT_INDEX_updated_{DATE}_{TAG}.md": """# CURRENT_INDEX update — IB1 route topology generator node degree v1

Date: 2026-06-20  
Branch: `codex/docs-ib1-route-topology-generator-node-degree-v1`  
Upstream implementation commit: `c4bebf9 Add IB1 route topology node degree generator`

## Current recommended topology source

The current recommended upstream route topology evidence is:

- Script: `scripts/make_ib1_route_topology_generator_node_degree_v1_1.py`
- Output root: `outputs/report_figures/ib1_route_topology_generator_node_degree_v1_1`
- Audit CSV: `outputs/report_figures/ib1_route_topology_generator_node_degree_v1_1/route_topology_generator_audit_v1_1.csv`
- Admission CSV: `outputs/report_figures/ib1_route_topology_generator_node_degree_v1_1/route_topology_generator_admission_v1_1.csv`
- Report HTML: `outputs/report_figures/ib1_route_topology_generator_node_degree_v1_1/route_topology_generator_report_v1_1.html`

## Current status

`navigation_challenge_exposure` has moved from source gap review to upstream governed source candidate.

Key audit values:

| Field | Value |
|---|---:|
| usable_route_position_source_count | 5 |
| usable_osm_graph_topology_source_count | 149 |
| generated_node_count | 33,918 |
| generated_edge_count | 98,821 |
| generated_side_branch_count | 5,434 |
| governed_fork_candidate_count | 1,357 |
| governed_decision_point_candidate_count | 1,357 |

Audit conclusion:

`PASS_IB1_ROUTE_TOPOLOGY_GENERATOR_NODE_DEGREE_V1_1_GOVERNED_SOURCE_CANDIDATE`

Admission decision:

`ADMIT_AS_GOVERNED_FORK_DECISION_POINT_SOURCE_CANDIDATE`

## Accepted route-position sources

The QA-patched v1_1 run admits five route-position sources only:

- `juansi_waterfall`
- `qixing_lengshuikeng`
- `qixing_lengshuikeng_xiaoyoukeng`
- `qixing_xiaoyoukeng`
- `zhonghua_ust_jiuwufeng`

The following config/control sources were excluded from route-position source admission:

- `configs/route_definitions/route_control_points_v1_3b.csv`
- `configs/route_definitions/route_expected_time_segments_v1_3b.csv`

## Boundary

This is route topology source governance only.

It is not:

- a personal ability axis
- a navigation ability score
- a radar score
- a final hiking risk score
- a route suitability score
- a go/no-go decision
- a medical diagnosis
- a causal claim

Do not connect this directly to radar or ability scoring. The correct next use is as upstream context for CH6.5.5 navigation-challenge exposure consumption and route-following interpretation.
""",

    RUNS / f"changelog_updated_{DATE}_{TAG}.md": """# Changelog update — IB1 route topology generator node degree v1

Date: 2026-06-20  
Branch: `codex/docs-ib1-route-topology-generator-node-degree-v1`  
Implementation commit documented: `c4bebf9 Add IB1 route topology node degree generator`

## Summary

Added and validated the first governed upstream route topology generator for fork / decision-point evidence.

This closes the previous source-gap finding from the compact source-gap review:

- Earlier source-gap review: `5817ffd Add IB1 route topology decision point source gap review`
- New governed source candidate: `c4bebf9 Add IB1 route topology node degree generator`

## What changed

The project previously had only heuristic fork-like / decision-point-like context:

- semantic context
- anchor/control context
- self-near geometry context
- route profile context
- wrong-branch activity context

Those sources were not sufficient to produce governed `fork_exposure_count` or `decision_point_exposure_count`.

The new generator parses OSM/graph topology and route-position sources and produces governed upstream topology tables:

- `route_topology_nodes_v1_1.csv`
- `route_topology_edges_v1_1.csv`
- `route_topology_side_branches_v1_1.csv`
- `route_topology_decision_points_v1_1.csv`
- `route_topology_route_sources_v1_1.csv`
- `route_topology_route_summary_v1_1.csv`
- `route_topology_source_inventory_v1_1.csv`
- `route_topology_source_role_summary_v1_1.csv`
- `route_topology_generator_audit_v1_1.csv`
- `route_topology_generator_admission_v1_1.csv`
- `route_topology_generator_report_v1_1.html`

## QA correction

The initial generator attempt admitted two suspicious config/control sources as route-position sources:

- `configs/route_definitions/route_control_points_v1_3b.csv`
- `configs/route_definitions/route_expected_time_segments_v1_3b.csv`

The v1_1 patch excludes those sources and retains only five route-position sources:

- `juansi_waterfall`
- `qixing_lengshuikeng`
- `qixing_lengshuikeng_xiaoyoukeng`
- `qixing_xiaoyoukeng`
- `zhonghua_ust_jiuwufeng`

## Audit result

`PASS_IB1_ROUTE_TOPOLOGY_GENERATOR_NODE_DEGREE_V1_1_GOVERNED_SOURCE_CANDIDATE`

Key values:

| Field | Value |
|---|---:|
| source_inventory_count | 2055 |
| usable_osm_graph_topology_source_count | 149 |
| usable_route_position_source_count | 5 |
| usable_node_degree_source_count | 149 |
| usable_adjacent_edge_source_count | 149 |
| usable_side_branch_source_count | 149 |
| generated_node_count | 33918 |
| generated_edge_count | 98821 |
| generated_side_branch_count | 5434 |
| governed_fork_candidate_count | 1357 |
| governed_decision_point_candidate_count | 1357 |
| route_dist_available_count | 33918 |
| lat_lon_available_count | 33918 |
| zero_fill_used | False |

## Governance boundary

No CH6.5 axis contract, radar, or data table was modified.

This is not a personal ability score, rank, class, final risk score, route suitability score, go/no-go decision, medical diagnosis, or causal claim.

## Next recommended branch

`codex/ch6-5-5-navigation-challenge-context-consumption-v1`

Purpose: consume the governed topology source as CH6.5.5 navigation-challenge context, without adding a radar axis or ability score.
""",

    RUNS / f"latest_handoff_prompt_updated_{DATE}_{TAG}.md": """# Latest handoff prompt — IB1 route topology generator node degree v1

Continue from:

`D:\\mountain_work\\115_osm`

Current documented implementation commit:

`c4bebf9 Add IB1 route topology node degree generator`

## Current status

The upstream route topology source gap has been partially resolved as a governed source candidate.

The current recommended topology generator is:

`D:\\mountain_work\\115_osm\\scripts\\make_ib1_route_topology_generator_node_degree_v1_1.py`

Output root:

`D:\\mountain_work\\115_osm\\outputs\\report_figures\\ib1_route_topology_generator_node_degree_v1_1`

## Important audit result

Audit CSV:

`outputs\\report_figures\\ib1_route_topology_generator_node_degree_v1_1\\route_topology_generator_audit_v1_1.csv`

Audit conclusion:

`PASS_IB1_ROUTE_TOPOLOGY_GENERATOR_NODE_DEGREE_V1_1_GOVERNED_SOURCE_CANDIDATE`

Admission decision:

`ADMIT_AS_GOVERNED_FORK_DECISION_POINT_SOURCE_CANDIDATE`

Key counts:

- source_inventory_count = 2055
- usable_osm_graph_topology_source_count = 149
- usable_route_position_source_count = 5
- generated_node_count = 33918
- generated_edge_count = 98821
- generated_side_branch_count = 5434
- governed_fork_candidate_count = 1357
- governed_decision_point_candidate_count = 1357
- zero_fill_used = False

## QA note

The first attempt admitted two config/control sources incorrectly:

- `configs/route_definitions/route_control_points_v1_3b.csv`
- `configs/route_definitions/route_expected_time_segments_v1_3b.csv`

v1_1 excludes those sources.

Accepted route-position sources are:

- `juansi_waterfall`
- `qixing_lengshuikeng`
- `qixing_lengshuikeng_xiaoyoukeng`
- `qixing_xiaoyoukeng`
- `zhonghua_ust_jiuwufeng`

## Next task

Create a new branch:

`codex/ch6-5-5-navigation-challenge-context-consumption-v1`

Goal:

Consume the governed topology decision-point source as CH6.5.5 navigation-challenge context.

Do not make it a personal ability axis.  
Do not modify radar plots.  
Do not modify CH6.5.5 axis contract or data table.  
Do not compute a navigation score, ability score, rank, class, final risk score, route suitability score, go/no-go decision, medical diagnosis, or causal claim.

Expected outputs may include:

- `route_navigation_challenge_context_v1.csv`
- `activity_navigation_challenge_context_v1.csv`
- `route_following_with_navigation_context_v1.csv`
- `navigation_challenge_context_consumption_audit_v1.csv`
- `navigation_challenge_context_consumption_report_v1.html`

Core logic:

- Map activity route/case id to route topology source.
- Count governed decision-point / fork exposure at route level.
- Attach exposure context to route-following interpretation.
- Keep the result descriptive/contextual only.
""",

    SCRIPTS / f"README_current_pipeline_updated_{DATE}_{TAG}.md": """# README current pipeline update — IB1 route topology generator node degree v1

Date: 2026-06-20  
Documented implementation commit: `c4bebf9 Add IB1 route topology node degree generator`

## Purpose

This update documents the first governed upstream topology generator used to support future navigation-challenge exposure context.

The generator is not a CH6.5 personal ability model. It is a source-governance layer that produces topology evidence.

## Script

`scripts/make_ib1_route_topology_generator_node_degree_v1_1.py`

## Output root

`outputs/report_figures/ib1_route_topology_generator_node_degree_v1_1`

## Main outputs

| File | Role |
|---|---|
| `route_topology_nodes_v1_1.csv` | Node table with route position and degree context |
| `route_topology_edges_v1_1.csv` | Edge adjacency table |
| `route_topology_side_branches_v1_1.csv` | Side branch evidence |
| `route_topology_decision_points_v1_1.csv` | Governed fork / decision-point candidates |
| `route_topology_route_sources_v1_1.csv` | Accepted route-position sources |
| `route_topology_route_summary_v1_1.csv` | Route-level topology summary |
| `route_topology_source_inventory_v1_1.csv` | Source inventory |
| `route_topology_source_role_summary_v1_1.csv` | Source role summary |
| `route_topology_generator_audit_v1_1.csv` | Audit |
| `route_topology_generator_admission_v1_1.csv` | Admission decision |
| `route_topology_generator_report_v1_1.html` | Human-readable report |

## Result

The v1_1 generator produced a governed source candidate:

- usable route-position sources: 5
- generated nodes: 33,918
- generated edges: 98,821
- generated side branches: 5,434
- governed fork candidates: 1,357
- governed decision-point candidates: 1,357

Audit conclusion:

`PASS_IB1_ROUTE_TOPOLOGY_GENERATOR_NODE_DEGREE_V1_1_GOVERNED_SOURCE_CANDIDATE`

Admission decision:

`ADMIT_AS_GOVERNED_FORK_DECISION_POINT_SOURCE_CANDIDATE`

## QA boundary

The v1_1 patch excludes config/control/time-segment route definition sources from route-position source admission.

Excluded examples:

- `configs/route_definitions/route_control_points_v1_3b.csv`
- `configs/route_definitions/route_expected_time_segments_v1_3b.csv`

## Correct downstream usage

This source may be consumed by CH6.5.5 navigation-challenge context.

It should be used to explain route-following context, for example:

- high route-following stability on routes with high decision-point exposure
- route-level fork / decision-point exposure as descriptive context

## Forbidden downstream usage

Do not use this as:

- personal ability axis
- navigation ability score
- radar score
- final hiking risk score
- route suitability score
- go/no-go decision
- medical diagnosis
- causal claim
"""
}

for path, text in FILES.items():
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote: {path}")
