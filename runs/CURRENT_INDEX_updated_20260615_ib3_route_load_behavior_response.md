# CURRENT INDEX - IB3 route load behavior response evidence

## Branches

- `codex/ib3-personal-hiking-features-route-load-comparison-smoke-v1`
- `codex/ib3-personal-hiking-features-route-load-comparison-full25-v1`
- `codex/ib3-personal-hiking-features-route-load-comparison-full25-review-v1`

## Commits

- `3b4fb65 Add IB3 route load behavior response fixture smoke`
- `8b839cf Add IB3 route load behavior response full25 evidence`
- `070be50 Add IB3 route load behavior full25 descriptive review`

## Purpose

This evidence layer supports section 6.5.1: personal hiking feature construction and route-load comparison.

It creates a descriptive dataset for:

- route-load evidence
- behavior-response evidence
- OSM / facility exposure evidence
- weather context evidence

## Current effective outputs

Fixture smoke:

- `outputs/ib3_personal_hiking_features_route_load_comparison_smoke_v1/activity_route_load_behavior_response_windows.csv`
- `outputs/ib3_personal_hiking_features_route_load_comparison_smoke_v1/activity_route_load_behavior_response_summary.csv`
- `outputs/ib3_personal_hiking_features_route_load_comparison_smoke_v1/activity_route_load_behavior_response_smoke_audit.csv`
- `outputs/ib3_personal_hiking_features_route_load_comparison_smoke_v1/activity_route_load_behavior_response_smoke_report.html`

Full25 evidence:

- `outputs/ib3_personal_hiking_features_route_load_comparison_full25_v1/activity_route_load_behavior_response_windows.csv`
- `outputs/ib3_personal_hiking_features_route_load_comparison_full25_v1/activity_route_load_behavior_response_summary.csv`
- `outputs/ib3_personal_hiking_features_route_load_comparison_full25_v1/activity_route_load_behavior_response_full25_audit.csv`
- `outputs/ib3_personal_hiking_features_route_load_comparison_full25_v1/activity_route_load_behavior_response_full25_report.html`

Full25 descriptive review:

- `outputs/ib3_personal_hiking_features_route_load_comparison_full25_review_v1/activity_route_load_behavior_response_full25_descriptive_review.csv`
- `outputs/ib3_personal_hiking_features_route_load_comparison_full25_review_v1/activity_route_load_behavior_response_full25_descriptive_review_report.html`
- `docs/ib3_route_load_behavior_response_full25_review_addendum_v1.md`

## Current audit summary

- fixture activities: `3_1 | 8_1 | 9_1`
- full25 usable activities: 25
- review-only excluded: `6_1`
- full25 window rows: 2054
- full25 summary rows: 25
- audit: `PASS_ROUTE_LOAD_BEHAVIOR_RESPONSE_FULL25_DESCRIPTIVE_ONLY`
- descriptive review items: 16
- safe for 6.5.1 text: 9
- limitations / not-for-conclusion items: 7

## Interpretation boundary

This layer is descriptive evidence only.

It does not generate or authorize:

- ability scores
- ability ranks
- ability classes
- THCI scores
- radar scores
- final hiking risk scores

It does not infer causality, facility use, or individual ability ranking.
