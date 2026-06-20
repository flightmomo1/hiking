# Changelog update — IB1 route topology generator node degree v1

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
