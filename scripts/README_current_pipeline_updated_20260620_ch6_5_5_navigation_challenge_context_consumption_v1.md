
# README — Current Pipeline Update: CH6.5.5 Navigation Challenge Context Consumption v1.1

Updated: 20260620  
Generated at: 2026-06-20 22:43:29

## Purpose

This update documents the CH6.5.5 navigation-challenge exposure context consumption layer.

It consumes upstream governed topology evidence from IB1 route topology node-degree generator v1.1 and attaches route-level navigation-challenge context to CH6.5.5 route-following interpretation tables.

## Files

Script:

- `scripts/make_ch6_5_5_navigation_challenge_context_consumption_v1_1.py`

Output root:

- `outputs/report_figures/ch6_5_5_navigation_challenge_context_consumption_v1_1`

Output files:

- `activity_navigation_challenge_context_v1_1.csv`
- `route_navigation_challenge_context_v1_1.csv`
- `route_following_with_navigation_context_v1_1.csv`
- `navigation_challenge_context_source_inventory_v1_1.csv`
- `navigation_challenge_context_consumption_admission_v1_1.csv`
- `navigation_challenge_context_consumption_audit_v1_1.csv`
- `navigation_challenge_context_consumption_report_v1_1.html`

## Upstream Input

- `outputs/report_figures/ib1_route_topology_generator_node_degree_v1_1`
- `route_topology_decision_points_v1_1.csv`
- `route_topology_generator_audit_v1_1.csv`
- `route_topology_generator_admission_v1_1.csv`

## Audit Summary

| Field | Value |
|---|---:|
| topology_audit_conclusion | `PASS_IB1_ROUTE_TOPOLOGY_GENERATOR_NODE_DEGREE_V1_1_GOVERNED_SOURCE_CANDIDATE` |
| topology_admission_decision | `ADMIT_AS_GOVERNED_FORK_DECISION_POINT_SOURCE_CANDIDATE` |
| route_context_count | 5 |
| activity_context_count | 25 |
| joined_route_following_context_count | 25 |
| missing_route_context_count | 0 |
| default_activity_route_binding_count | 25 |
| excluded_activity_ids | 6_1 |
| extra_source_6_1_excluded | True |
| governed_decision_point_candidate_count_consumed | 1357 |
| governed_fork_candidate_count_consumed | 1357 |
| admission_decision | `ADMIT_AS_NAVIGATION_CHALLENGE_CONTEXT_SOURCE` |
| audit_conclusion | `PASS_CH6_5_5_NAVIGATION_CHALLENGE_CONTEXT_CONSUMPTION_V1_1_GOVERNED_CONTEXT_AVAILABLE` |

## Governance Rules

- Do not add `navigation_challenge_exposure` as a personal ability radar axis in this branch.
- Do not produce navigation ability scores.
- Do not produce rankings or classes.
- Do not produce go/no-go decisions.
- Do not modify CH6.5 axis contract, radar plot, or existing radar data table.
- Keep `6_1` excluded from formal activity context consumption.

## Status

`navigation_challenge_exposure` is now a governed context source for route-following interpretation.
