# THCI Weather-Terrain v1.3 Update Changelog

Generated: 2026-07-06T13:06:28.873Z

## Scope

- Adds a planned weather-terrain integration layer for THCI v1.3.
- Keeps v1.2 support semantics intact.
- Does not modify scoring scripts.
- Does not raise weather_impact_score directly.
- Marks NLSC collapse / landslide mask fields as planned or pending_source until route-profile or fusion-summary lineage exists.

## New / Updated Artifacts

- osm_semantic_risk_mapping_v1_6_weather_terrain_updated.csv
- thci_axis_definition_v1_3_weather_terrain_updated.csv
- thci_axis_scoring_rule_v1_3_weather_terrain_updated.csv
- thci_feature_mapping_v1_4_weather_terrain_updated.csv
- thci_normalization_threshold_v1_3_weather_terrain_updated.csv
- thci_risk_semantics_weather_terrain_v1_3_review.xlsx

## Key Design Decisions

1. weather_impact_score remains a sensitivity axis, not an actual forecast score.
2. baseline_hazard_score keeps inherent hazards; weather_impact_score receives only traceable weather amplification residuals.
3. rainwash_or_convergence_sensitivity and upslope_weather_amplification_score are planned THCI inputs with fixed thresholds.
4. NLSC collapse mask fields require explicit columns:
   - nlsc_collapse_mask_overlap_ratio
   - nlsc_collapse_mask_nearby
   - dist_nlsc_collapse_mask_m
   - upslope_weather_amplification_score
5. weather-terrain fusion summary can feed THCI only through route-level fields with scenario/as_of/rain_flags lineage.

## Pending Sources

- Formal route-profile or route-level rollup for NLSC collapse mask.
- Formal weather-terrain fusion to THCI adapter.
- Double-count guard implementation in future scoring code.
