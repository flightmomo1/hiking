# Latest Handoff Prompt - IB3 Baseline Hiking Performance Model Planning

Date: 2026-06-15

## Workspace

- `D:\mountain_work\115_osm`

## Current planning branch

- `codex/ib3-baseline-hiking-performance-model-planning-v1`

## Upstream evidence

- Activity performance: 26 activities, primary root used, no missing or failed files
- Weather profile: 27 activities, 243 observed values, 9 variables per activity
- Descriptive join: 26 matched rows and one weather-only unmatched activity
- Join audit: `PASS_DESCRIPTIVE_ACTIVITY_WEATHER_PERFORMANCE_JOIN_ONLY`

Weather-only unmatched activity:

- `qixing_lengshuikeng_xiaoyoukeng_20260410_biji_gpx`

## Planning contract

Read:

- `docs/ib3_baseline_hiking_performance_model_planning_v1.md`
- `configs/hiking_performance/ib3_baseline_hiking_performance_feature_contract_v1.csv`

The contract separates route / terrain demand, activity performance, weather
context, data quality / usability, and a future individual ability estimate.
Every feature row has `scoring_allowed_in_this_branch = False`.

## Non-negotiable boundary

- No ability score is computed.
- No THCI score is computed.
- No radar score is computed.
- No final hiking risk score is computed.
- Weather descriptive labels must not become direct penalties.
- Missing values must not be hard-filled as zero.
- Quality gates must run before any future estimate.
- Individual ability requires multiple comparable quality-passed activities.

## Recommended continuation

- `codex/ib3-baseline-hiking-performance-model-smoke-v1`

The smoke branch should first produce descriptive eligibility, exclusion,
normalization, and weather-comparison evidence. It must not directly
productionize a composite ability score.
