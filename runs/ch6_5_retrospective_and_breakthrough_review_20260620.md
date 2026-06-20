# CH6.5 / CH6.5.5 Retrospective and Breakthrough Review - 2026-06-20

## 1. Executive assessment

Short answer: CH6.5 / CH6.5.5 is not simply stuck in a loop, but it is close to a governance plateau.

The work is not pure "ghost circling" because several outputs now form traceable, auditable chains from evidence source to admission decision to governed plot output. The clearest example is `route_following_stability`: proxy admission v1_1, axis contract v1_1, data table v1_1, radar plot v1_1, and documentation handoff all exist and agree on the same boundary. The plot audit reports 25 baseline plots, 0 extra-source plots, 3 limited proxy axes, and no score/rank/class/go-no-go fields.

The looping is real in another sense: many CH6.5.x branches now produce review, audit, report, and handoff layers without adding new admitted axes. That is partly correct governance, but it increases directory/version load and can feel like movement without capability expansion. The evidence is that the v1_1 contract still has 0 numeric axes, only 3 limited proxy axes, and several axes retained as descriptive or missing evidence.

What is improving is the quality of boundaries. Earlier work moved from story/report outputs toward explicit governed evidence layers. Missing evidence is no longer silently zero-filled. Extra source `6_1` is consistently blocked. `deviation_correction_ability` was not wrongly upgraded from route issue keywords. `navigation_challenge_exposure` was retained as source gap rather than faking fork exposure counts from route semantics.

Current judgement: the project has moved from exploratory plotting into evidence governance. That is progress. The next breakthrough will not come from another radar/report wrapper; it will come from building one upstream source layer that unlocks a currently blocked axis or context.

## 2. Evidence of progress

### Governed evidence layers replaced loose plotting

Earlier CH6.5 / CH6.5.5 work included radar previews and story-style reports. Current outputs now separate:

- source evidence
- admission review
- axis contract
- governed data table
- plot preview
- documentation handoff

This matters because the radar is no longer allowed to turn "interesting data" into a hidden score. The axis contract and data table encode `axis_output_mode`, `radar_output_permission`, `axis_value_allowed`, `required_gate_status`, `fallback_status`, and `interpretation_boundary`.

### Route-following stability formed a closed loop

`route_following_stability` now has a complete traceable mini-pipeline:

- proxy admission v1_1:
  `outputs/report_figures/ch6_5_5_route_following_stability_proxy_admission_v1_1`
- axis contract patch:
  `outputs/report_figures/ch6_5_5_route_following_axis_contract_patch_v1`
- data table patch:
  `outputs/report_figures/ch6_5_5_route_following_data_table_patch_v1`
- radar plot v1_1:
  `outputs/report_figures/ch6_5_5_personal_ability_radar_plot_v1_1`
- docs handoff:
  `runs/CURRENT_INDEX_updated_20260620_ch6_5_5_route_following_radar_v1_1.md`
  and related handoff / README files

Key evidence:

- route-following admission audit:
  `PASS_CH6_5_5_ROUTE_FOLLOWING_STABILITY_PROXY_ADMISSION_V1_1_GOVERNED_LIMITED_PROXY_CANDIDATE`
- axis contract patch changed `route_following_stability` from `MISSING_EVIDENCE_ANNOTATION` to `LIMITED_PROXY_AXIS`.
- data table patch audit reports:
  - `row_count = 286`
  - `activity_count = 26`
  - `axis_count = 11`
  - `route_following_baseline_value_count = 25`
  - `route_following_extra_source_value_count = 0`
  - `zero_fill_used = False`
- radar plot v1_1 audit reports:
  - `plotted_baseline_activity_count = 25`
  - `plotted_extra_source_activity_count = 0`
  - `limited_proxy_axis_count = 3`
  - `generated_plot_count = 25`

### Radar preview improved from 2 to 3 limited proxy axes

The current governed limited proxy radar preview uses:

- `terrain_movement_efficiency`
- `pacing_movement_stability`
- `route_following_stability`

This is a genuine improvement over the earlier two-axis preview. It is still not a formal ability score, but it is a stronger governed preview surface.

### Extra source handling is consistent

Extra source `6_1` is repeatedly blocked:

- data table v1 had extra-source proxy rows blocked by baseline gate
- route-following data table patch reports `route_following_extra_source_value_count = 0`
- radar plot v1_1 reports `plotted_extra_source_activity_count = 0`
- navigation challenge context keeps `6_1` blocked

This is good evidence hygiene.

### Conservative non-upgrades are working

`deviation_correction_ability` was not upgraded from route issue keywords. The event-chain review reports:

- `baseline_activity_count = 25`
- `baseline_with_complete_chain_candidate_count = 0`
- recommended mode: `MISSING_EVIDENCE_ANNOTATION`
- admission decision:
  `RETAIN_AS_MISSING_EVIDENCE_ANNOTATION_REQUIRES_EVENT_CHAIN_VALIDATION`

`navigation_challenge_exposure` was also not converted into a fake axis or value. Its review reports:

- `usable_fork_source_count = 0`
- `context_source_count = 824`
- decision:
  `RETAIN_AS_SOURCE_GAP_FOR_FORK_DECISION_POINT_INVENTORY`
- audit:
  `PASS_CH6_5_5_NAVIGATION_CHALLENGE_EXPOSURE_REVIEW_V1_SOURCE_GAP_ONLY`

### Governance checks are now persistent

Across the checked audits, recurring guardrails are present:

- `zero_fill_used = False`
- forbidden score/rank/class fields absent
- no final hiking risk score
- no route suitability score
- no go/no-go decision
- no medical diagnosis
- no causality claim

That is not cosmetic. It prevents the radar from becoming a persuasive but unsupported scoring product.

## 3. Evidence of looping / friction

### Many layers, few admitted axes

The scripts inventory shows many CH6.5.5 review/audit/report generators:

- 300s movement study / admission / QA gate / consumption integration
- pacing movement stability axis and admission audit
- terrain movement efficiency evidence and admission audit
- personal ability radar axis contract
- personal ability radar data table
- route-following proxy admission / contract patch / data table patch / plot
- deviation correction event-chain review
- navigation challenge exposure review

That is a lot of machinery for a radar that currently has:

- 0 numeric axes
- 3 limited proxy axes
- several descriptive annotation axes
- several missing evidence axes

The friction is not that the work is wrong. The friction is that governance work can keep expanding while admitted evidence grows slowly.

### Output/version sprawl is becoming expensive

There are many adjacent roots under `outputs/report_figures/ch6_5*` and `outputs/report_figures/ch6_5_5*`. Versioning is traceable, but expensive to hold in working memory. The project now depends on remembering which of several similarly named roots is authoritative:

- original radar data table v1
- route-following data table patch v1 / v1_1
- original axis contract v1
- route-following axis contract patch v1 / v1_1
- radar plot v1
- radar plot v1_1

Without a registry, each patch increases the chance of using the wrong input.

### Several axes remain descriptive or missing

The current axis contract v1_1 still keeps:

- `endurance_sustained_movement` as `DESCRIPTIVE_ANNOTATION`
- `uphill_load_tolerance` as `DESCRIPTIVE_ANNOTATION`
- `hr_load_management_recovery` as `DESCRIPTIVE_ANNOTATION`
- `weather_performance_maintenance` as `DESCRIPTIVE_ANNOTATION`
- `autonomous_completion_readiness` as `DESCRIPTIVE_ANNOTATION`
- `deviation_correction_ability` as `MISSING_EVIDENCE_ANNOTATION`
- `risk_response_experience` as `MISSING_EVIDENCE_ANNOTATION`
- `supply_equipment_support` as `MISSING_EVIDENCE_ANNOTATION`

This is correct, but it means many radar ambitions are still not evidence-admitted.

### 300s movement evidence has value but remains blocked

The 300s movement admission audit reports:

- baseline activity count: 25
- extra source activity count: 1
- horizontal evidence activity count: 6
- vertical evidence activity count: 6
- both horizontal/vertical evidence activity count: 2
- standalone axis admitted count: 0
- QA gate or guard admitted count: 2

So 300s movement evidence is useful as descriptive support and QA gating, but not yet as standalone radar axis evidence.

### HR, weather, completion, supply, and risk response are high-risk for overclaiming

The current governance repeatedly blocks these from becoming scores because they need better source contracts:

- HR needs device validity and HRmax handling before it can be more than context.
- Weather needs paired same-person baseline under varying conditions.
- Completion/readiness evidence does not prove autonomy, supply, or support independence.
- Supply/equipment requires questionnaire or explicit logs.
- Risk response requires observed risk recognition / avoidance / fallback behavior, not route risk alone.

These are the right blocks, but they create the feeling of repeated review without breakthrough.

### Navigation challenge exposure found context, not fork inventory

The navigation challenge review found 824 context sources, but 0 usable fork exposure sources. It correctly classified:

- activity map-match / wrong-branch diagnostics as not fork inventory
- mainline graph summary as not decision point inventory
- route geometry self-near context as not fork inventory
- route semantic context as not fork inventory

This is a useful negative result, but not yet a capability gain.

## 4. Current axis maturity table

| axis_id | zh label | current status | admitted as radar proxy? | current evidence source | blocker | next best action |
|---|---|---:|---:|---|---|---|
| `terrain_movement_efficiency` | 地形移動效率 | `LIMITED_PROXY_AXIS` | Yes | CH6.5.6 terrain movement efficiency admission + route load context index | Still proxy, not formal ability score | Keep as governed proxy; do not expand until source registry exists |
| `pacing_movement_stability` | 穩定移動能力 | `LIMITED_PROXY_AXIS` | Yes | pacing movement stability axis v1 + admission audit | Still proxy and activity-history bounded | Keep as governed proxy; consider later stability decomposition only after registry |
| `route_following_stability` | 路線跟隨穩定性 | `LIMITED_PROXY_AXIS` | Yes | route-following proxy admission v1_1 + contract/data/plot v1_1 | Navigation challenge context still source gap | Build fork / decision-point inventory to improve confidence interpretation |
| `endurance_sustained_movement` | 持續耐力 | `DESCRIPTIVE_ANNOTATION` | No | 300s horizontal movement admission review | Coverage limited; no standalone axis admitted | Either improve multi-activity coverage or keep descriptive |
| `uphill_load_tolerance` | 上坡負荷承受力 | `DESCRIPTIVE_ANNOTATION` | No | 300s vertical movement + HR context | Limited coverage; positive-delta artifact guard; HR validity | Do not promote until vertical/VAM source contract is stronger |
| `hr_load_management_recovery` | HR負荷管理與恢復能力 | `DESCRIPTIVE_ANNOTATION` | No | CH6.7 HR lifecycle/recovery context | Device validity and HRmax uncertainty; medical overclaim risk | Build HR quality / HRmax governance before axis work |
| `weather_performance_maintenance` | 天候條件下表現維持 | `DESCRIPTIVE_ANNOTATION` | No | weather context summary + route-load readiness review | Needs paired same-person weather baseline | Build weather paired-baseline source governance |
| `autonomous_completion_readiness` | 自主完成能力 | `DESCRIPTIVE_ANNOTATION` | No | CH6.8 personal route-load readiness review | Completion does not prove autonomy, supply, equipment, team support | Add explicit support/supply/team metadata before scoring |
| `deviation_correction_ability` | 偏離修正能力 | `MISSING_EVIDENCE_ANNOTATION` | No | deviation correction event-chain review v1 | 0 complete baseline chain candidates; no deviation-start -> correction/rejoin model | Build deviation event-chain model upstream |
| `risk_response_experience` | 風險應對經驗 | `MISSING_EVIDENCE_ANNOTATION` | No | route risk / route-load context only | No observed risk response outcome field | Define risk-response event taxonomy after deviation/fork layers |
| `supply_equipment_support` | 補給／裝備支援 | `MISSING_EVIDENCE_ANNOTATION` | No | none in personal evidence | No supply/equipment/hydration/support data | Add questionnaire/log source governance |
| `navigation_challenge_exposure` | 導航挑戰暴露 | `CONTEXT_ONLY / SOURCE_GAP` | No | navigation challenge exposure review v1 | 0 governed fork/decision-point inventory sources | Build fork / decision-point inventory; use only as route-following confidence context |

Note: `navigation_challenge_exposure` is not one of the original 11 personal ability axes. It is included here because it is now an explicit context evidence item for interpreting `route_following_stability`.

## 5. Breakthrough recommendations

### A. Build fork / decision-point inventory

This is the best near-term breakthrough.

Purpose: fill the `navigation_challenge_exposure` source gap and make `route_following_stability` more interpretable.

Key questions to answer:

- Which OSM / route graph features are true fork or decision-point candidates?
- Which are merely road/trail/path semantics, guideposts, facilities, or POIs?
- Which intersections are irrelevant because they are not plausible wrong-branch exposure?
- How close must a side path / branch be to the mainline to count?
- How should confidence differ between actual graph node degree, nearby OSM ways, road crossings, guideposts, and facility context?

Needed design:

- route-level or route-window-level inventory
- fields such as `route_dist_m`, `node_degree`, `connected_way_count`, `connected_highway_types`, `side_branch_angle`, `branch_length_m`, `same_route_name`, `guidepost_nearby`, `facility_nearby`, `decision_point_confidence`
- clear exclusions for POI-only, guidepost-only, facility-only, and road crossing without plausible trail choice

Breakthrough value:

This does not create a new ability score. It improves confidence interpretation for `route_following_stability`: stable route following under high decision-point exposure means more than stable route following on a simple corridor.

### B. Build deviation event-chain model

Purpose: give `deviation_correction_ability` a real path out of missing evidence.

The current IB3C event keyword layer is not enough. It can identify route issue / uncertainty / rejoin-like events, but the event-chain review found 0 complete baseline deviation correction chains.

Needed upstream layer:

- map-matched trajectory sequence model
- branch id or candidate way id over time
- route distance monotonicity / reversal
- offset distance over time
- wrong-branch depth
- time-to-rejoin
- correction/backtrack signature
- rejoin point
- evidence confidence

Potential chain:

`deviation_start -> wrong_branch_depth_accumulation -> correction/backtrack/navigation_check -> rejoin_mainline`

Breakthrough value:

This could eventually promote `deviation_correction_ability` from `MISSING_EVIDENCE_ANNOTATION` to candidate proxy. But it is harder than fork inventory because it requires trajectory-event modeling, not just route graph inventory.

### C. Build axis lifecycle registry

Purpose: stop relying on memory across patches.

The registry should contain:

- `axis_id`
- `version`
- `output_mode`
- `evidence_source`
- `admission_status`
- `blocker`
- `last_commit`
- `next_action`
- `forbidden_use_boundary`

Breakthrough value:

This reduces operational friction and prevents wrong input usage. It does not by itself unlock new evidence, but it will become necessary soon because the project now has several v1 / v1_1 contract and table layers.

### D. Pause radar axis expansion and strengthen source governance

This should be the default policy. Do not add more ability axes until source governance improves.

Priority source governance:

- fork / decision-point inventory
- deviation chain model
- HR quality / HRmax handling
- weather paired baseline
- supply/equipment questionnaire

This would prevent the radar from becoming visually richer but evidentially weaker.

## 6. Recommended next branch

Recommended next branch:

`codex/ch6-5-5-fork-decision-point-inventory-v1`

Reason:

This is the highest-leverage next step because it addresses a concrete source gap found by the latest review and improves an already admitted axis (`route_following_stability`) without prematurely inventing a new ability score. It is also more tractable than deviation correction because it can start from route graph / OSM / mainline data before touching activity behavior modeling.

Why not the other options:

- `codex/ch6-5-5-deviation-event-chain-model-v1`: important, but heavier. It needs trajectory sequence logic, branch identity, offset/time dynamics, and rejoin validation. It should come after fork/decision-point inventory because branch exposure and branch identity help define deviation in the first place.
- `codex/ch6-5-5-axis-lifecycle-registry-v1`: valuable for reducing version sprawl, but it is an operations breakthrough, not an evidence breakthrough. It should follow soon, but not before the next source gap is attacked.
- `codex/ch6-5-5-radar-v1-1-consolidated-docs-only`: useful if preparing a handoff or publication snapshot, but it will not unlock any blocked axis or context. Doing this next would increase the sense of looping.

## 7. Files inspected

### Scripts inspected / inventoried

- `scripts/make_ch6_5_route_load_context_index_v1.py`
- `scripts/make_ch6_5_5_300s_movement_consumption_integration_review_v1.py`
- `scripts/make_ch6_5_5_300s_movement_evidence_admission_review_v1.py`
- `scripts/make_ch6_5_5_300s_movement_qa_gate_consumption_v1.py`
- `scripts/make_ch6_5_5_activity_history_numeric_attribution_v0_5.py`
- `scripts/make_ch6_5_5_deviation_correction_event_chain_review_v1.py`
- `scripts/make_ch6_5_5_navigation_challenge_exposure_review_v1.py`
- `scripts/make_ch6_5_5_pacing_movement_stability_axis_admission_audit_v1.py`
- `scripts/make_ch6_5_5_pacing_movement_stability_axis_v1.py`
- `scripts/make_ch6_5_5_personal_ability_radar_axis_contract_v1.py`
- `scripts/make_ch6_5_5_personal_ability_radar_data_table_v1.py`
- `scripts/make_ch6_5_5_personal_ability_radar_plot_v1_1.py`
- `scripts/make_ch6_5_5_route_following_axis_contract_patch_v1.py`
- `scripts/make_ch6_5_5_route_following_data_table_patch_v1.py`
- `scripts/make_ch6_5_5_route_following_stability_proxy_admission_v1.py`
- `scripts/make_ch6_5_5_route_following_stability_proxy_admission_v1_1.py`
- `scripts/make_ch6_5_6_terrain_movement_efficiency_axis_admission_audit_v1_2.py`
- `scripts/make_ch6_5_6_terrain_movement_efficiency_evidence_v1.py`

### Outputs / audit / decision files inspected

- `outputs/report_figures/ch6_5_5_personal_ability_radar_axis_contract_v1/personal_ability_radar_axis_contract_v1.csv`
- `outputs/report_figures/ch6_5_5_personal_ability_radar_axis_contract_v1/personal_ability_radar_axis_contract_audit_v1.csv`
- `outputs/report_figures/ch6_5_5_personal_ability_radar_data_table_v1/personal_ability_radar_data_table_audit_v1.csv`
- `outputs/report_figures/ch6_5_5_route_following_stability_proxy_admission_v1_1/route_following_stability_proxy_admission_audit_v1_1.csv`
- `outputs/report_figures/ch6_5_5_route_following_stability_proxy_admission_v1_1/route_following_stability_proxy_admission_decision_v1_1.csv`
- `outputs/report_figures/ch6_5_5_route_following_axis_contract_patch_v1/personal_ability_radar_axis_contract_patch_audit_v1.csv`
- `outputs/report_figures/ch6_5_5_route_following_axis_contract_patch_v1/personal_ability_radar_axis_contract_v1_1.csv`
- `outputs/report_figures/ch6_5_5_route_following_data_table_patch_v1/personal_ability_radar_data_table_patch_audit_v1.csv`
- `outputs/report_figures/ch6_5_5_personal_ability_radar_plot_v1_1/personal_ability_radar_plot_audit_v1_1.csv`
- `outputs/report_figures/ch6_5_5_deviation_correction_event_chain_review_v1/deviation_correction_event_chain_audit_v1.csv`
- `outputs/report_figures/ch6_5_5_deviation_correction_event_chain_review_v1/deviation_correction_event_chain_admission_decision_v1.csv`
- `outputs/report_figures/ch6_5_5_navigation_challenge_exposure_review_v1/navigation_challenge_exposure_audit_v1.csv`
- `outputs/report_figures/ch6_5_5_navigation_challenge_exposure_review_v1/navigation_challenge_exposure_admission_decision_v1.csv`
- `outputs/report_figures/ch6_5_5_300s_movement_evidence_admission_review_v1/movement_300s_admission_audit_v1.csv`
- `outputs/report_figures/ch6_5_5_300s_movement_qa_gate_consumption_v1/movement_300s_consumption_audit_v1.csv`
- `outputs/report_figures/ch6_5_5_300s_movement_consumption_integration_review_v1/movement_300s_integration_audit_v1.csv`
- `outputs/report_figures/ch6_8_personal_route_load_readiness_review_v1_1/personal_route_load_readiness_audit_v1_1.csv`
- `outputs/report_figures/ch6_5_5_pacing_movement_stability_axis_admission_audit_v1/pacing_movement_stability_axis_admission_audit_v1.csv`
- `outputs/report_figures/ch6_5_6_terrain_movement_efficiency_axis_admission_audit_v1_2/terrain_movement_efficiency_axis_admission_audit_v1_2.csv`

### Output folders inventoried

- `outputs/report_figures/ch6_5_5_300s_movement_consumption_integration_review_v1`
- `outputs/report_figures/ch6_5_5_300s_movement_evidence_admission_review_v1`
- `outputs/report_figures/ch6_5_5_300s_movement_qa_gate_consumption_v1`
- `outputs/report_figures/ch6_5_5_deviation_correction_event_chain_review_v1`
- `outputs/report_figures/ch6_5_5_navigation_challenge_exposure_review_v1`
- `outputs/report_figures/ch6_5_5_personal_ability_radar_axis_contract_v1`
- `outputs/report_figures/ch6_5_5_personal_ability_radar_data_table_v1`
- `outputs/report_figures/ch6_5_5_personal_ability_radar_plot_v1_1`
- `outputs/report_figures/ch6_5_5_route_following_axis_contract_patch_v1`
- `outputs/report_figures/ch6_5_5_route_following_data_table_patch_v1`
- `outputs/report_figures/ch6_5_5_route_following_stability_proxy_admission_v1_1`
- `outputs/report_figures/ch6_5_6_terrain_movement_efficiency_axis_admission_audit_v1_2`
- `outputs/report_figures/ch6_8_personal_route_load_readiness_review_v1_1`

### Runs / README files inspected

- `runs/CURRENT_INDEX_updated_20260620_ch6_5_5_route_following_radar_v1_1.md`
- `runs/latest_handoff_prompt_updated_20260620_ch6_5_5_route_following_radar_v1_1.md`
- `runs/changelog_updated_20260620_ch6_5_5_route_following_radar_v1_1.md`
- `runs/CURRENT_INDEX_updated_20260620_ch6_5_5_personal_ability_radar_axis_contract_v1.md`
- `runs/CURRENT_INDEX_updated_20260620_ch6_5_5_personal_ability_radar_data_table_v1.md`
- `runs/latest_handoff_prompt_updated_20260620_ch6_5_5_personal_ability_radar_data_table_v1.md`
- `scripts/README_current_pipeline_updated_20260620_ch6_5_5_route_following_radar_v1_1.md`
- `scripts/README_current_pipeline_updated_20260620_ch6_5_5_personal_ability_radar_axis_contract_v1.md`
- `scripts/README_current_pipeline_updated_20260620_ch6_5_5_personal_ability_radar_data_table_v1.md`
- `scripts/README_current_pipeline_updated_20260617_ch6_5_route_load_context_index_v1.md`

