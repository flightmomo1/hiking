# CURRENT_INDEX update — IB1 route topology generator node degree v1

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
