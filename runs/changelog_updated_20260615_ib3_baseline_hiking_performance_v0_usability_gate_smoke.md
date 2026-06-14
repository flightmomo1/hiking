# Changelog Update - IB3 Baseline Hiking Performance v0 Usability Gate Smoke

Date: 2026-06-15

## Working directory

- `D:\mountain_work\115_osm`

## Completed commits

- `85733798a1c36371225fa7e99b62462bd5f7ce2c Document IB3 baseline hiking performance smoke closeout`
- `09b676acb20ff36252383c87080de6fb4c287f0b Design IB3 baseline hiking performance model v0`
- `50ee06f9b79d25242a1e302bc0e10d148e9264d6 Add IB3 baseline hiking performance v0 usability gate smoke`

## Inputs used

- `outputs/ib3_baseline_hiking_performance_model_smoke_v1/activity_baseline_performance_smoke_features.csv`
- `outputs/ib3_baseline_hiking_performance_model_smoke_v1/activity_baseline_performance_smoke_audit.csv`
- `configs/hiking_performance/ib3_baseline_hiking_performance_model_v0_rule_contract_v1.csv`
- `configs/hiking_performance/ib3_baseline_hiking_performance_model_v0_output_contract_v1.csv`

## Gate smoke artifacts

- `outputs/ib3_baseline_hiking_performance_v0_usability_gate_smoke_v1/activity_v0_usability_gate_smoke.csv`
- `outputs/ib3_baseline_hiking_performance_v0_usability_gate_smoke_v1/activity_v0_usability_gate_smoke_audit.csv`
- `outputs/ib3_baseline_hiking_performance_v0_usability_gate_smoke_v1/activity_v0_usability_gate_smoke_report.html`

Result:

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

## Boundary preserved

- The stage classifies future model usability only.
- No ability score was generated.
- No ability rank was generated.
- No ability class was generated.
- No THCI, radar, or final hiking risk scoring was performed.
- `USABLE` does not mean strong ability.
- `REVIEW_ONLY_DATA_QUALITY` does not mean weak ability.
- Review-only evidence remains outside a formal ability estimate.
- Weather flags are not penalties.
- Data-quality gates are not ability ratings.

## Recommended next work

- `codex/ib3-baseline-hiking-performance-route-normalized-comparison-smoke-v1`

Use the 25 usable activities for descriptive route-normalized distributions,
weather-context comparison, and sample-impact review. Continue to prohibit
formal ability scoring and ranking.
