# Current Index — CH6.8 Personal Route-Load Readiness Review v1.1

## Working Directory

`D:\mountain_work\115_osm`

## Current Recommended Layers

### CH6.7 HR recovery from IB3C events

Current recommended version: `v1.1`

Script:

`D:\mountain_work\115_osm\scripts\make_ch6_7_hr_recovery_from_ib3c_events_v1_1.py`

Output root:

`outputs\report_figures\ch6_7_hr_recovery_from_ib3c_events_v1_1`

Effective outputs:

- `activity_hr_recovery_events_from_ib3c_v1_1.csv`
- `activity_hr_recovery_activity_summary_from_ib3c_v1_1.csv`
- `activity_hr_recovery_phase_summary_from_ib3c_v1_1.csv`
- `activity_hr_recovery_group_summary_from_ib3c_v1_1.csv`
- `activity_hr_recovery_from_ib3c_audit_v1_1.csv`
- `activity_hr_recovery_from_ib3c_report_v1_1.html`

Audit summary:

- event CSVs: 26
- raw event rows: 346
- standardized event rows: 346
- activities: 26
- route-core events: 316
- route-core facility-rest events: 42
- activities with route-core facility-rest events: 15
- confirmed HR recovery events: 88
- high-HR pause-without-recovery events: 56
- forbidden columns absent: True
- conclusion: `PASS_CH6_7_HR_RECOVERY_FROM_IB3C_EVENTS_V1_1_DESCRIPTIVE_ONLY`

Status:

- v1 is conservative baseline.
- v1.1 is current recommended.

### CH6.8 personal route-load readiness review

Current recommended version: `v1.1`

Script:

`D:\mountain_work\115_osm\scripts\make_ch6_8_personal_route_load_readiness_review_v1_1.py`

Output root:

`outputs\report_figures\ch6_8_personal_route_load_readiness_review_v1_1`

Effective outputs:

- `personal_route_load_readiness_review_v1_1.csv`
- `personal_route_load_readiness_group_summary_v1_1.csv`
- `personal_route_load_readiness_input_contract_v1_1.csv`
- `personal_route_load_readiness_audit_v1_1.csv`
- `personal_route_load_readiness_report_v1_1.html`

Audit summary:

- activities: 26
- group summary rows: 3
- `EARLY_CHECKPOINT_REVIEW_REQUIRED`: 15
- `CONSERVATIVE_PACING_RECOMMENDED`: 10
- `INSUFFICIENT_PERSONAL_HISTORY`: 1
- `STANDARD_PREP_REASONABLE`: 0
- `WEATHER_SENSITIVE_REVIEW_REQUIRED`: 0 as primary gate count
- missing inputs: none
- forbidden columns absent: True
- conclusion: `PASS_CH6_8_PERSONAL_ROUTE_LOAD_READINESS_REVIEW_V1_1_DESCRIPTIVE_ONLY`

Status:

- v1 is high-sensitivity smoke version.
- v1.1 is current recommended.

## CH6.8 Input Evidence

CH6.8 v1.1 uses these descriptive evidence sources:

- CH6.7 HR recovery from IB3C events v1.1
- CH6.7 HR lifecycle recovery profile v2
- CH6.7 completion feasibility review v1.1
- CH6.7 planning context fusion v1.1
- CH6.5 route-load context index v1

## Gate Interpretation

The primary gate is a descriptive review label. It is not a route suitability result.

Recommended wording:

- `EARLY_CHECKPOINT_REVIEW_REQUIRED`: existing evidence suggests emphasizing early status checkpoint and conservative pacing.
- `CONSERVATIVE_PACING_RECOMMENDED`: existing evidence supports completion feasibility but suggests conservative pace/rest planning.
- `INSUFFICIENT_PERSONAL_HISTORY`: available personal evidence is insufficient for readiness review.
- `STANDARD_PREP_REASONABLE`: available evidence does not trigger extra conservative or early-checkpoint review; currently no rows in this run.

## Boundary

This current index does not authorize:

- cardiopulmonary diagnosis
- ability score
- ability rank
- ability class
- route suitability score
- THCI score
- radar score
- final hiking risk score
- automatic suitable/unsuitable decision
- weather causality inference
- OSM proximity as actual facility use

Weather-sensitive review flags remain available inside `readiness_review_flags`; the audit count is primary-gate-only.

## Recommended Next Action

Commit scripts and documentation if the repository convention allows evidence outputs to be tracked. If outputs are not tracked, commit at least:

- `scripts\make_ch6_7_hr_recovery_from_ib3c_events_v1_1.py`
- `scripts\make_ch6_8_personal_route_load_readiness_review_v1_1.py`
- updated current index / changelog / handoff / README documents

Suggested commit message:

`Add CH6.8 personal route-load readiness review`
