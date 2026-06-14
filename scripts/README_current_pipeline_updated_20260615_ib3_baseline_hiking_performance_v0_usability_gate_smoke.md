# README Update - IB3 Baseline Hiking Performance v0 Usability Gate Smoke

Date: 2026-06-15

## Working directory

- `D:\mountain_work\115_osm`

## Pipeline status

The baseline hiking performance evidence chain is complete through a v0
usability gate smoke. This gate selects a candidate set for future descriptive
comparison; it is not an ability model.

Completed commits:

- `85733798a1c36371225fa7e99b62462bd5f7ce2c Document IB3 baseline hiking performance smoke closeout`
- `09b676acb20ff36252383c87080de6fb4c287f0b Design IB3 baseline hiking performance model v0`
- `50ee06f9b79d25242a1e302bc0e10d148e9264d6 Add IB3 baseline hiking performance v0 usability gate smoke`

## Input contract

- `outputs/ib3_baseline_hiking_performance_model_smoke_v1/activity_baseline_performance_smoke_features.csv`
- `outputs/ib3_baseline_hiking_performance_model_smoke_v1/activity_baseline_performance_smoke_audit.csv`
- `configs/hiking_performance/ib3_baseline_hiking_performance_model_v0_rule_contract_v1.csv`
- `configs/hiking_performance/ib3_baseline_hiking_performance_model_v0_output_contract_v1.csv`

## Gate smoke artifacts

- `outputs/ib3_baseline_hiking_performance_v0_usability_gate_smoke_v1/activity_v0_usability_gate_smoke.csv`
- `outputs/ib3_baseline_hiking_performance_v0_usability_gate_smoke_v1/activity_v0_usability_gate_smoke_audit.csv`
- `outputs/ib3_baseline_hiking_performance_v0_usability_gate_smoke_v1/activity_v0_usability_gate_smoke_report.html`

Validated result:

- `input_row_count = 26`
- `output_row_count = 26`
- `usable_for_v0_model_smoke_count = 25`
- `review_only_count = 1`
- `excluded_from_ability_estimate_count = 1`
- `gate_distribution = USABLE:25 | REVIEW_ONLY_DATA_QUALITY:1`
- `rule_contract_all_scoring_disallowed = True`
- `output_contract_all_generated_false = True`
- `output_contract_all_scoring_disallowed = True`
- `audit_conclusion = PASS_V0_USABILITY_GATE_SMOKE_ONLY`

## Authorization boundary

- Future model usability gate smoke only
- No ability score
- No ability rank
- No ability class
- No THCI scoring
- No radar scoring
- No final hiking risk scoring
- `USABLE` does not mean strong ability
- `REVIEW_ONLY_DATA_QUALITY` does not mean weak ability
- Review-only activities do not enter a formal ability estimate
- Weather flags do not become penalties
- Data-quality gates do not become ability ratings

## Recommended next branch

- `codex/ib3-baseline-hiking-performance-route-normalized-comparison-smoke-v1`

The next smoke should use only the 25 usable activities and examine:

- Duration per kilometer distribution
- Median speed distribution
- Gain rate per hour distribution
- Descriptive weather-context and performance relationships
- Data-quality gate impact on the sample set

It must not generate a formal ability score or rank personal ability.
