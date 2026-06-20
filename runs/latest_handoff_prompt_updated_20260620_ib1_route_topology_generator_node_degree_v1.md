# Latest handoff prompt — IB1 route topology generator node degree v1

Continue from:

`D:\mountain_work\115_osm`

Current documented implementation commit:

`c4bebf9 Add IB1 route topology node degree generator`

## Current status

The upstream route topology source gap has been partially resolved as a governed source candidate.

The current recommended topology generator is:

`D:\mountain_work\115_osm\scripts\make_ib1_route_topology_generator_node_degree_v1_1.py`

Output root:

`D:\mountain_work\115_osm\outputs\report_figures\ib1_route_topology_generator_node_degree_v1_1`

## Important audit result

Audit CSV:

`outputs\report_figures\ib1_route_topology_generator_node_degree_v1_1\route_topology_generator_audit_v1_1.csv`

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
