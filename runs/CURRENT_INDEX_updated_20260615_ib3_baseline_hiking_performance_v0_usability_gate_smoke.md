# CURRENT INDEX - IB3 Baseline Hiking Performance v0 Usability Gate Smoke

Date: 2026-06-15

## Working directory

- `D:\mountain_work\115_osm`

## Current branch

- `codex/ib3-baseline-hiking-performance-model-v0-usability-gate-smoke-closeout-v1`

## Completed commit chain

- `85733798a1c36371225fa7e99b62462bd5f7ce2c Document IB3 baseline hiking performance smoke closeout`
- `09b676acb20ff36252383c87080de6fb4c287f0b Design IB3 baseline hiking performance model v0`
- `50ee06f9b79d25242a1e302bc0e10d148e9264d6 Add IB3 baseline hiking performance v0 usability gate smoke`

## Inputs

- `outputs/ib3_baseline_hiking_performance_model_smoke_v1/activity_baseline_performance_smoke_features.csv`
- `outputs/ib3_baseline_hiking_performance_model_smoke_v1/activity_baseline_performance_smoke_audit.csv`
- `configs/hiking_performance/ib3_baseline_hiking_performance_model_v0_rule_contract_v1.csv`
- `configs/hiking_performance/ib3_baseline_hiking_performance_model_v0_output_contract_v1.csv`

## Outputs

- `outputs/ib3_baseline_hiking_performance_v0_usability_gate_smoke_v1/activity_v0_usability_gate_smoke.csv`
- `outputs/ib3_baseline_hiking_performance_v0_usability_gate_smoke_v1/activity_v0_usability_gate_smoke_audit.csv`
- `outputs/ib3_baseline_hiking_performance_v0_usability_gate_smoke_v1/activity_v0_usability_gate_smoke_report.html`

## Smoke result

- `input_row_count = 26`
- `output_row_count = 26`
- `usable_for_v0_model_smoke_count = 25`
- `review_only_count = 1`
- `excluded_from_ability_estimate_count = 1`
- Gate distribution: `USABLE:25 | REVIEW_ONLY_DATA_QUALITY:1`
- `rule_contract_all_scoring_disallowed = True`
- `output_contract_all_generated_false = True`
- `output_contract_all_scoring_disallowed = True`
- `audit_conclusion = PASS_V0_USABILITY_GATE_SMOKE_ONLY`

## Engineering boundary

- This stage performs a future model usability gate smoke only.
- It does not generate an ability score, ability rank, or ability class.
- It does not perform THCI, radar, or final hiking risk scoring.
- `USABLE` does not mean strong ability.
- `REVIEW_ONLY_DATA_QUALITY` does not mean weak ability.
- A gate indicates whether an activity is suitable for a future model v0 smoke or comparison.
- Review-only activities must not enter a formal ability estimate.
- Weather-context flags must not become direct penalties.
- A data-quality gate must not be interpreted as an ability rating.

## Recommended next step

- `codex/ib3-baseline-hiking-performance-route-normalized-comparison-smoke-v1`

The next branch should use only the 25 `USABLE` activities for a descriptive
route-normalized comparison smoke. It should examine:

- `candidate_duration_min_per_km` distribution
- `candidate_median_speed_kmh` distribution
- `candidate_gain_rate_m_per_hour` distribution
- Descriptive relationships between weather context and performance
- The effect of data-quality gating on the sample set

It must not generate a formal ability score or rank individual ability.
