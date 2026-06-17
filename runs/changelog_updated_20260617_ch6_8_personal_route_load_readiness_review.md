# Changelog — CH6.8 Personal Route-Load Readiness Review v1.1

## Added

- Added `make_ch6_7_hr_recovery_from_ib3c_events_v1_1.py`.
- Added `make_ch6_8_personal_route_load_readiness_review_v1_1.py`.
- Added CH6.7 IB3C event-based HR recovery evidence output v1.1.
- Added CH6.8 personal route-load readiness evidence gate output v1.1.

## CH6.7 HR Recovery v1.1

The HR recovery event layer now includes on-route facility/rest-point events as route-core review evidence when the event is a facility-like rest event and `on_route_ratio >= 0.8`.

Important output root:

`outputs\report_figures\ch6_7_hr_recovery_from_ib3c_events_v1_1`

Audit result:

- 26 event CSVs
- 346 raw event rows
- 346 standardized event rows
- 26 activities
- 316 route-core review events
- 42 route-core facility-rest review events
- 15 activities with route-core facility-rest events
- 88 confirmed HR recovery events
- 56 high-HR pause-without-recovery events
- `PASS_CH6_7_HR_RECOVERY_FROM_IB3C_EVENTS_V1_1_DESCRIPTIVE_ONLY`

Version decision:

- v1 remains a conservative baseline.
- v1.1 is current recommended for CH6.8 readiness review input.

## CH6.8 Readiness Review v1.1

The readiness layer integrates:

- CH6.7 HR recovery from IB3C events v1.1
- CH6.7 HR lifecycle recovery profile v2
- CH6.7 completion feasibility review v1.1
- CH6.7 planning context fusion v1.1
- CH6.5 route-load context index v1

Important output root:

`outputs\report_figures\ch6_8_personal_route_load_readiness_review_v1_1`

Audit result:

- 26 activities
- 3 readiness gate summary rows
- 15 `EARLY_CHECKPOINT_REVIEW_REQUIRED`
- 10 `CONSERVATIVE_PACING_RECOMMENDED`
- 1 `INSUFFICIENT_PERSONAL_HISTORY`
- 0 `STANDARD_PREP_REASONABLE`
- 0 `WEATHER_SENSITIVE_REVIEW_REQUIRED` as a primary gate count
- `forbidden_columns_absent=True`
- `PASS_CH6_8_PERSONAL_ROUTE_LOAD_READINESS_REVIEW_V1_1_DESCRIPTIVE_ONLY`

## v1 to v1.1 Readiness Gate Change

The v1 readiness review was intentionally high sensitivity and produced:

- 24 `EARLY_CHECKPOINT_REVIEW_REQUIRED`
- 1 `CONSERVATIVE_PACING_RECOMMENDED`
- 1 `INSUFFICIENT_PERSONAL_HISTORY`

The v1.1 readiness review reduces early-checkpoint over-triggering by requiring stronger early checkpoint evidence or compound evidence before elevating the primary gate to `EARLY_CHECKPOINT_REVIEW_REQUIRED`.

The v1.1 distribution is now:

- 15 `EARLY_CHECKPOINT_REVIEW_REQUIRED`
- 10 `CONSERVATIVE_PACING_RECOMMENDED`
- 1 `INSUFFICIENT_PERSONAL_HISTORY`

Manual sanity review confirmed that v1.1 early gates are supported by strong early checkpoint HR ratio, high-load HR evidence, slow-group context, route-core HR recovery limitation, or high-HR no-recovery burden.

## Boundary

This changelog records descriptive evidence-layer additions only.

No cardiopulmonary diagnosis, ability scoring, ability ranking, ability class generation, route suitability scoring, THCI scoring, radar scoring, final hiking risk scoring, or automatic go/no-go decision was added.

Weather-sensitive flags may appear inside `readiness_review_flags`; the audit field `weather_sensitive_review_required_count` is primary-gate-only and being zero does not mean weather evidence is absent.
