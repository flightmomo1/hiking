# CH6.5.5 route-following navigation context interpretation v1

## Status

This module adds a descriptive interpretation layer that combines route-following stability evidence with governed navigation-challenge context.

- branch: `codex/ch6-5-5-route-following-navigation-context-interpretation-v1`
- commit: `09bfc21 Add CH6.5.5 route following navigation context interpretation`
- upstream main tag: `ch6-5-5-navigation-context-v1-main-20260620`
- output root: `outputs/report_figures/ch6_5_5_route_following_navigation_context_interpretation_v1`
- audit conclusion: `PASS_CH6_5_5_ROUTE_FOLLOWING_NAVIGATION_CONTEXT_INTERPRETATION_V1_GOVERNED_CONTEXT_AVAILABLE`
- admission decision: `ADMIT_AS_ROUTE_FOLLOWING_NAVIGATION_CONTEXT_INTERPRETATION`

## Governance boundary

This layer is interpretation context only. It is:

- not an ability score
- not an ability rank
- not an ability class
- not a THCI score
- not a radar score
- not a navigation ability score
- not a final hiking risk score
- not a route suitability score
- not a medical diagnosis
- not a causal claim
- not a go/no-go decision

It does not modify radar output, personal ability axis contract, THCI logic, route-risk logic, or any go/no-go gate.

## Inputs

Primary upstream context:

- `outputs/report_figures/ch6_5_5_navigation_challenge_context_consumption_v1_1`

Route-following context roots considered:

- `outputs/report_figures/ch6_5_5_route_following_stability_proxy_admission_v1_1`
- `outputs/report_figures/ch6_5_5_route_following_data_table_patch_v1`

## Outputs

- `outputs/report_figures/ch6_5_5_route_following_navigation_context_interpretation_v1/route_following_navigation_context_audit_v1.csv`
- `outputs/report_figures/ch6_5_5_route_following_navigation_context_interpretation_v1/route_following_navigation_context_group_summary_v1.csv`
- `outputs/report_figures/ch6_5_5_route_following_navigation_context_interpretation_v1/route_following_navigation_context_interpretation_v1.csv`
- `outputs/report_figures/ch6_5_5_route_following_navigation_context_interpretation_v1/route_following_navigation_context_report_v1.html`
- `outputs/report_figures/ch6_5_5_route_following_navigation_context_interpretation_v1/route_following_navigation_context_source_inventory_v1.csv`

## Audit highlights

| metric | value |
|---|---:|
| output_interpretation_count | 25 |
| context_available_count | 25 |
| review_recommended_count | 10 |
| extra_source_6_1_excluded | True |
| admission_decision | ADMIT_AS_ROUTE_FOLLOWING_NAVIGATION_CONTEXT_INTERPRETATION |
| audit_conclusion | PASS_CH6_5_5_ROUTE_FOLLOWING_NAVIGATION_CONTEXT_INTERPRETATION_V1_GOVERNED_CONTEXT_AVAILABLE |

## Interpretation labels

The interpretation labels are review helpers. They do not represent ability classes or ranks.

| route_following_band | navigation_exposure_level | route_following_navigation_interpretation_label | route_following_navigation_review_flag | activity_count |
|---|---|---|---|---|
| HIGH_ROUTE_FOLLOWING | HIGH_NAVIGATION_EXPOSURE | HIGH_ROUTE_FOLLOWING_UNDER_HIGH_NAVIGATION_EXPOSURE | NO_REVIEW_FLAG | 11 |
| MID_ROUTE_FOLLOWING | HIGH_NAVIGATION_EXPOSURE | CONTEXT_AVAILABLE_NO_SCORE | NO_REVIEW_FLAG | 4 |
| LOW_ROUTE_FOLLOWING | HIGH_NAVIGATION_EXPOSURE | LOW_ROUTE_FOLLOWING_UNDER_HIGH_NAVIGATION_EXPOSURE_REVIEW | REVIEW_RECOMMENDED | 10 |

## Operational notes

- `6_1` is excluded as an extra source and does not enter the interpretation output.
- `review_recommended_count` indicates cases where route-following evidence should be read together with navigation exposure.
- High navigation-challenge exposure provides context for interpretation; it does not prove causality.
