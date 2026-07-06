# THCI Route Risk Six-Axis Handoff Report v1

Generated: 2026-07-06  
Project root: `D:\mountain_work\115_osm`  
Primary case: `taichung_guguan_butterfly_valley_waterfall_20260630`

This handoff separates the current official THCI scoring line from the v1.3 weather-terrain candidate simulation line.

## Version Status

| Track | Version | Status | Main outputs | Notes |
|---|---|---|---|---|
| Official scoring | THCI v1.2 support updated | Official current THCI scoring | `outputs/thci_axis_scores_v1_2_support_updated/`; `outputs/thci_radar_v1_2_support_updated/` | Support difficulty has been upgraded with v1.2 support semantics. |
| Candidate simulation | THCI v1.3 weather-terrain candidate | Simulation only, not official scoring | `outputs/thci_weather_terrain_scoring_v1_3_candidate/`; `outputs/thci_radar_v1_3_weather_terrain_candidate/` | Tests weather-terrain effects on `weather_impact_score` without changing official scoring. |

## Evidence Layers

| Layer | Current role | Butterfly Valley status | Scoring status |
|---|---|---|---|
| ib1g2 upslope/collapse proxy | Nearby upslope relief, contour density, watercourse channel, and collapse-mask proxy | Available under `outputs/ib1g2_upslope_collapse_hazard_proxy/taichung_guguan_butterfly_valley_waterfall_20260630/` | Static terrain evidence; not directly used by v1.3 candidate except through adapter lineage/review. |
| ib1g3 upslope contributing area proxy | Broader upslope source contribution, source count, fall gradient, source relief | Available under `outputs/ib1g3_upslope_contributing_area_hazard_proxy/taichung_guguan_butterfly_valley_waterfall_20260630/` | Strong upslope evidence; raw `upslope_contributing_hazard_score` is not reused directly as weather amplification. |
| NLSC collapse mask / distant collapse review | Standalone collapse-mask evidence and distance review | Nearest NLSC collapse mask distance is about `1339.87 m`; ib2d buffer hit count is `0` | Review-only. Not near-route scoring evidence for Butterfly Valley. |
| ib2d upslope map and hotspots | Map-level upslope hotspot review and radar context | Hotspot length `560.0 m`; route-level hotspot overlap candidate about `0.102210` | Used through candidate adapter as `fusion_hotspot_overlap_ratio`. |
| Weather-terrain fusion | Scenario-specific rainwash and hotspot interaction summary | `rainwash_axis_score = 0.913204674854`; `rain_factor = 1.25`; scenario `antecedent_rain_high_sensitivity` | Candidate simulation source. Rain factor remains review-only context. |

## Six-Axis Maturity

| Axis | Chinese label | Current maturity | Official status | Candidate status |
|---|---|---|---|---|
| `physical_difficulty_score` | 體力難度 | Mature | v1.2 official score available | Unchanged in v1.3 candidate |
| `technical_difficulty_score` | 技術難度 | Mature enough for current route comparison | v1.2 official score available | Unchanged in v1.3 candidate |
| `baseline_hazard_score` | 基礎危害 | Mature for OSM/terrain baseline hazards, but still needs guards against weather duplication | v1.2 official score available | Unchanged in v1.3 candidate |
| `navigation_risk_score` | 迷航風險 | Mature after navigation/support semantics updates | v1.2 official score available | Unchanged in v1.3 candidate |
| `support_difficulty_score` | 支援不易 | Recently upgraded and official in v1.2 support updated | v1.2 official score available | Unchanged in v1.3 candidate |
| `weather_impact_score` | 天候影響 | Developing | v1.2 official score available but conservative | v1.3 candidate simulation increases this axis using traceable weather-terrain fields only |

## Butterfly Valley Six-Axis Difference

| Axis | v1.2 support updated | v1.3 weather-terrain candidate | Delta | Interpretation |
|---|---:|---:|---:|---|
| `physical_difficulty_score` | `0.459762675058` | `0.459762675058` | `0` | No candidate change |
| `technical_difficulty_score` | `0.26` | `0.26` | `0` | No candidate change |
| `baseline_hazard_score` | `0.4` | `0.4` | `0` | No candidate change; avoids double-counting static terrain hazard |
| `navigation_risk_score` | `0.4875` | `0.4875` | `0` | No candidate change |
| `support_difficulty_score` | `0.445788676787` | `0.445788676787` | `0` | No candidate change |
| `weather_impact_score` | `0.194779578` | `0.672134200562` | `+0.477354622562` | Candidate-only weather-terrain simulation effect |

The v1.3 candidate formula used in the simulation is:

`weather_terrain_candidate_component = 0.40 * rainwash_or_convergence_sensitivity + 0.45 * weather_terrain_fusion_rainwash_axis_score + 0.15 * fusion_hotspot_overlap_ratio_normalized`

`fusion_hotspot_overlap_ratio_normalized = clip(fusion_hotspot_overlap_ratio / 0.30, 0, 1)`

`weather_impact_score_v1_3_candidate = max(existing_weather_impact_score_v1_2, weather_terrain_candidate_component)`

The `0.30` hotspot-overlap threshold is a simulation threshold only, not an official THCI threshold.

## Fields Included in v1.3 Candidate Scoring

| Field | Value | Status | Contribution | Double-count guard |
|---|---:|---|---:|---:|
| `rainwash_or_convergence_sensitivity` | `0.525217653179` | `scoring_ready_candidate` | `0.210087061272` | true |
| `weather_terrain_fusion_rainwash_axis_score` | `0.913204674854` | `scoring_ready_candidate` | `0.410942103684` | true |
| `fusion_hotspot_overlap_ratio` | `0.102210071212` | `scoring_ready_candidate` | `0.051105035606` | true |

## Fields Kept as Review-Only or Planned

| Field | Value | Status | Reason |
|---|---:|---|---|
| `upslope_weather_amplification_score` | empty | `planned` | Weather amplification residual formula is not defined; raw upslope score must not be reused directly. |
| `nlsc_collapse_mask_overlap_ratio` | `0` | `review_only` | Current ib2d buffer hit count is `0`; no accepted route-level NLSC overlap scoring field exists. |
| `nlsc_collapse_mask_nearby` | `false` | `review_only` | Distant collapse mask review flag exists, but nearest distance is about `1339.87 m`; not near-route scoring evidence. |
| `dist_nlsc_collapse_mask_m` | `1339.86597092` | `review_only` | Distance evidence only; do not mix with OSM `dist_landslide_m` or feed scoring without accepted lineage. |
| `weather_terrain_fusion_rain_factor` | `1.25` | `review_only` | Context only. Rain factor must not independently raise THCI. |

## Why v1.3 Candidate Is Not Official Scoring

- It uses a clearly labeled simulation formula, not the official THCI scoring script.
- It does not update or validate the official THCI scoring rule implementation.
- It does not modify `risk_semantics` configs.
- `fusion_hotspot_overlap_ratio_normalized` uses a temporary `0.30` simulation threshold.
- `upslope_weather_amplification_score` remains `planned`.
- NLSC collapse-mask evidence remains `review_only` for Butterfly Valley.
- Weather-terrain fields still need batch QA, route-level lineage checks, and double-count guard validation before official adoption.

## Batch Data Quality and Review Flags

| Tier | Required evidence | Suggested route flag | Use in candidate scoring |
|---|---|---|---|
| A | v1.2 official THCI scores, route profile, ib1g2/ib1g3, ib2d upslope hotspot summary, weather-terrain fusion summary with `case_id`, `scenario`, `as_of`, `rain_flags`, and source files | `WT_READY_CANDIDATE_QA_PASS` | Candidate scoring allowed for approved fields |
| B | v1.2 official THCI scores plus partial weather-terrain fusion or partial upslope evidence | `WT_PARTIAL_LINEAGE_REVIEW` | Review only or limited simulation |
| C | Route profile and v1.2 THCI scores exist, but no weather-terrain fusion or no reliable upslope/hotspot rollup | `WT_PENDING_SOURCE` | Do not run weather-terrain scoring |
| D | Missing route profile, unstable route geometry, missing case ID, or source-file lineage unavailable | `WT_BLOCKED_INPUT_QA` | Block candidate scoring |

Recommended review flags:

- `ROUTE_PROFILE_LINEAGE_MISSING`
- `WEATHER_SCENARIO_AS_OF_MISSING`
- `RAIN_FLAGS_MISSING`
- `UPSLOPE_PROXY_MISSING`
- `HOTSPOT_ROLLUP_MISSING`
- `NLSC_COLLAPSE_REVIEW_ONLY`
- `DOUBLE_COUNT_GUARD_REQUIRED`
- `RAIN_FACTOR_CONTEXT_ONLY`
- `SIMULATION_THRESHOLD_USED`
- `OFFICIAL_SCORING_NOT_UPDATED`

## Next Steps for Four Existing Routes

Target routes:

- `qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b`
- `qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b`
- `juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b`
- `zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b`

Recommended sequence:

1. Confirm each route has official v1.2 support updated THCI axis scores.
2. Confirm route profile, OSM semantic profile, NLSC terrain window, ib1g2, ib1g3, ib2d upslope hotspot summary, and weather-terrain fusion outputs exist.
3. Run a route-level weather-terrain adapter equivalent to `thci_weather_terrain_adapter_v1_3.py` for each route.
4. Verify each adapter output has `case_id`, route fingerprint or route ID, `scenario`, `as_of`, `rain_flags`, `source_file`, `source_field`, and field status.
5. Keep `review_only` and `planned` fields out of scoring.
6. Run candidate scoring simulation only for routes with Tier A or approved Tier B evidence.
7. Produce candidate radar comparison only after the simulation report shows that only intended axes changed.
8. Prepare a batch QA matrix comparing all five routes, including Butterfly Valley as the pilot reference.

## Handoff Summary

THCI v1.2 support updated remains the official route-risk six-axis scoring line. THCI v1.3 weather-terrain candidate is useful as a controlled simulation for the weather axis, especially where weather-terrain fusion and hotspot rollups have strong lineage. It should stay separate from official scoring until the scoring rule, normalization thresholds, adapter lineage, and double-count guards are reviewed across a larger route batch.
