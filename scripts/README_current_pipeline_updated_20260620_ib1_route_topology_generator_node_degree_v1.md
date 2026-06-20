# README current pipeline update — IB1 route topology generator node degree v1

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
