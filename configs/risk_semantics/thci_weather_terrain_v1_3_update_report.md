# THCI v1.3 Weather-Terrain Updated Report

Generated: 2026-07-06T13:06:28.876Z

## Base

Requested Excel base `thci_risk_semantics_support_update_v1_2_review.xlsx` was not found in the project workspace, so this workbook was generated from the current v1.2 support-updated CSV source-of-truth files under `configs/risk_semantics`.

## Difference From v1.2 Support Updated

v1.2 focused on `support_difficulty_score`: evacuation access, support facilities, rescue operation difficulty, and critical bottlenecks.

v1.3 weather-terrain updated keeps those support definitions and adds a planned weather-terrain integration design for `weather_impact_score`:

- `rainwash_or_convergence_sensitivity`
- `upslope_weather_amplification_score`
- `nlsc_collapse_mask_overlap_ratio`
- `nlsc_collapse_mask_nearby`
- `dist_nlsc_collapse_mask_m`
- `weather_terrain_fusion_rainwash_axis_score`
- `fusion_hotspot_overlap_ratio`
- `weather_terrain_fusion_rain_factor` as review-only context

## Guardrails

- Do not hard-raise `weather_impact_score`.
- Do not use standalone NLSC collapse mask geometry directly in THCI.
- Do not mix OSM `dist_landslide_m` with NLSC `dist_nlsc_collapse_mask_m`.
- Do not double-count baseline hazards; weather axis receives only weather amplification residuals.
- Fields without route-profile or fusion-summary lineage are marked `planned`, `pending_source`, or `planned_review_only`.

## Outputs

- `D:\mountain_work\115_osm\configs\risk_semantics\osm_semantic_risk_mapping_v1_6_weather_terrain_updated.csv`
- `D:\mountain_work\115_osm\configs\risk_semantics\thci_axis_definition_v1_3_weather_terrain_updated.csv`
- `D:\mountain_work\115_osm\configs\risk_semantics\thci_axis_scoring_rule_v1_3_weather_terrain_updated.csv`
- `D:\mountain_work\115_osm\configs\risk_semantics\thci_feature_mapping_v1_4_weather_terrain_updated.csv`
- `D:\mountain_work\115_osm\configs\risk_semantics\thci_normalization_threshold_v1_3_weather_terrain_updated.csv`
- `D:\mountain_work\115_osm\configs\risk_semantics\thci_weather_terrain_v1_3_update_changelog.md`
- `D:\mountain_work\115_osm\configs\risk_semantics\thci_risk_semantics_weather_terrain_v1_3_review.xlsx`
