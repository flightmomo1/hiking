# Current pipeline status updated 20260604 THCI version comparison v1.0 / v1.0a / v1.0b / v1.0c

Run date: 2026-06-04

## Current status

```text
THCI config bundle v1.0 = CONVERGED_WITH_NEEDS_REVIEW
THCI axis scores v1.0 = CONVERGED_WITH_MISSING_FEATURES_RECORDED
THCI radar v1.0 = CONVERGED
THCI axis scores v1.0a = CONVERGED_WITH_PROXY_FEATURES_RECORDED
THCI axis scores v1.0b = CONVERGED_WITH_NAVIGATION_SEMANTICS_CALIBRATED
THCI radar v1.0b = CONVERGED_WITH_NAVIGATION_SEMANTICS_CALIBRATED
THCI version comparison v1.0 / v1.0a / v1.0b = COMPLETED
```

This README keeps the IB2 / IB2D v1.3b route-level baseline risk visualization checkpoint and updates THCI to the current v1.0c weather-semantics-calibrated display state. THCI v1.0b is preserved as the previous recommended baseline.

## Current recommended THCI branch

```text
Current recommended THCI display / scoring version = v1.0c
Recommended scoring root: outputs\thci_axis_scores_v1_0c\
Recommended radar root:   outputs\thci_radar_v1_0c\
Recommended integrated root, auto left map:     outputs\ib2d_thci_radar_v1_0c\
Recommended integrated root, IB2D PNG left map: outputs\ib2d_thci_radar_v1_0c_ib2d_png\
```

THCI v1.0c changes only `weather_impact_score`. The five non-weather axes are copied from v1.0b, and v1.0b remains available as the previous recommended baseline under:

```text
outputs\thci_axis_scores_v1_0b\
outputs\thci_radar_v1_0b\
```

v1.0c promotion is backed by:

```text
scripts\thci_diagnose_weather_sensitivity_v1_0b.py
scripts\thci_diagnose_weather_hydrology_topography_v1_0c_review.py
scripts\audit_thci_v1_0c_weather_review_convergence.ps1
scripts\audit_thci_v1_0c_official_display_convergence.ps1
```

The weather review decision is:

```text
THCI_V1_0C_WEATHER_REVIEW_STATUS = WEATHER_CALIBRATION_ESTABLISHED_WITH_HYDROLOGY_TOPOGRAPHY_REVIEW
THCI_V1_0C_OFFICIAL_DISPLAY_STATUS = CURRENT_RECOMMENDED_VERSION
```

The Juansi waterfall route has hydrology-topography evidence for prior weather underestimation: high hydrology proximity, low-elevation hydrology overlap, water crossing presence, and elevated drainage accumulation proxy.

## Previous recommended THCI branch

```text
Previous recommended scoring root: outputs\thci_axis_scores_v1_0b\
Previous recommended radar root:   outputs\thci_radar_v1_0b\
```

## THCI version hierarchy

```text
v1.0  = deterministic baseline; complete scoring runtime but missing feature coverage caused low scores in some axes.
v1.0a = proxy feature coverage calibration; brought physical, baseline hazard, weather, and initial navigation proxies into scoring.
v1.0b = navigation semantics calibration; only navigation_risk_score was recalibrated from v1.0a.
```

## THCI comparison outputs

```text
outputs\thci_version_comparison\thci_axis_scores_v1_0_v1_0a_v1_0b_comparison_wide.csv
outputs\thci_version_comparison\thci_axis_scores_v1_0_v1_0a_v1_0b_comparison_long.csv
```

## THCI v1.0 / v1.0a / v1.0b comparison findings

The comparison table confirms the intended interpretation of the three scoring branches:

```text
v1.0  = deterministic baseline; missing features caused several axes to be under-scored.
v1.0a = proxy feature calibration; physical, baseline hazard, weather impact, and initial navigation proxies were added.
v1.0b = navigation semantics calibration; only navigation_risk_score was recalibrated while the other five axes remain aligned with v1.0a.
```

### Navigation risk comparison

| case_id | v1.0 | v1.0a | v1.0b | v1.0a - v1.0 | v1.0b - v1.0a |
|---|---:|---:|---:|---:|---:|
| juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b | 0.000 | 0.150 | 0.060 | +0.150 | -0.090 |
| qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b | 0.000 | 0.819 | 0.454 | +0.819 | -0.364 |
| qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b | 0.000 | 0.725 | 0.405 | +0.725 | -0.319 |
| zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b | 0.000 | 0.900 | 0.485 | +0.900 | -0.415 |

### Interpretation

- v1.0a successfully added proxy coverage, but navigation risk became too sensitive to junction / route-complexity proxy.
- v1.0b corrected this by treating junction density as contextual instead of a direct迷航 score.
- v1.0b navigation risk now reflects route confusion, poor visibility, return difficulty, safe-exit connectivity, and cap guard.
- The five non-navigation axes remain effectively unchanged from v1.0a to v1.0b, aside from floating-point noise.

### Current recommended version

```text
Current recommended THCI display / discussion version = v1.0b
Use outputs\thci_axis_scores_v1_0b and outputs\thci_radar_v1_0b for review and presentation.
```


## THCI v1.0b formal scripts

```text
scripts\thci_compute_axis_scores_v1_0b.py
scripts\audit_thci_axis_scores_v1_0b_convergence.ps1
scripts\thci_plot_radar_v1_0b.py
scripts\audit_thci_radar_v1_0b_convergence.ps1
```

## THCI v1.0b formal outputs

Axis scores:

```text
outputs\thci_axis_scores_v1_0b\<case_id>\<case_id>_thci_axis_scores_v1_0b.csv
outputs\thci_axis_scores_v1_0b\<case_id>\<case_id>_thci_axis_score_summary_v1_0b.json
outputs\thci_axis_scores_v1_0b\_batch_summary\thci_axis_scores_v1_0b_case_summary.csv
outputs\thci_axis_scores_v1_0b\_batch_summary\thci_axis_scores_v1_0b_convergence_audit.csv
outputs\thci_axis_scores_v1_0b\_batch_summary\thci_axis_scores_v1_0b_convergence_decision.csv
```

Radar:

```text
outputs\thci_radar_v1_0b\<case_id>\<case_id>_thci_radar_v1_0b.png
outputs\thci_radar_v1_0b\<case_id>\<case_id>_thci_radar_plot_data_v1_0b.csv
outputs\thci_radar_v1_0b\<case_id>\<case_id>_thci_radar_summary_v1_0b.json
outputs\thci_radar_v1_0b\_batch_summary\thci_radar_v1_0b_case_summary.csv
outputs\thci_radar_v1_0b\_batch_summary\thci_radar_v1_0b_convergence_audit.csv
outputs\thci_radar_v1_0b\_batch_summary\thci_radar_v1_0b_convergence_decision.csv
```

## Navigation semantics boundary

```text
分岔多不必然代表迷航高。
若分岔支線能接到其他登山口、道路或安全出口，迷航後果應降低。
真正高迷航風險是路徑不可視、標示不足、走錯後無法安全接回或下山。
```

## Production scoring boundary

```text
runtime_llm_allowed = false
```

LLM is not part of the THCI production scoring runtime. The THCI scoring branch uses fixed CSV configuration, deterministic scripts, fixed thresholds, proxy feature provenance, and convergence audits.

## THCI v1.0c Weather Review Branch

```text
Recommended display branch remains: THCI v1.0b
Weather calibration candidate branch: THCI v1.0c
```

v1.0c was added as a review branch for weather semantics calibration. It does
not replace v1.0b as the recommended presentation version. The integrated
display / radar recommendation remains:

```text
outputs\thci_axis_scores_v1_0b\
outputs\thci_radar_v1_0b\
outputs\ib2d_thci_radar_v1_0b_ib2d_png\
```

### v1.0c Scripts

```text
scripts\thci_diagnose_weather_sensitivity_v1_0b.py
scripts\thci_compute_axis_scores_v1_0c.py
scripts\thci_diagnose_weather_hydrology_topography_v1_0c_review.py
scripts\audit_thci_v1_0c_weather_review_convergence.ps1
```

### v1.0c Output Roots

```text
outputs\thci_weather_sensitivity_diagnostics_v1_0b\
outputs\thci_axis_scores_v1_0c\
outputs\thci_weather_hydrology_topography_diagnostics_v1_0c_review\
outputs\thci_v1_0c_weather_review_audit\
```

### v1.0c Scoring Boundary

```text
v1.0c recalibrates only weather_impact_score.
physical_difficulty_score is copied from v1.0b.
technical_difficulty_score is copied from v1.0b.
baseline_hazard_score is copied from v1.0b.
navigation_risk_score is copied from v1.0b.
support_difficulty_score is copied from v1.0b.
runtime_llm_allowed = false
batch min-max normalization = false
IB2D rerun = false
v1.0b overwrite = false
```

### Hydrology-Topography Review Evidence

The weather review branch adds a diagnostic distinction that hydrology risk
should not be interpreted from water density alone. Rainwater tends to collect
in route-relative low terrain, valley / drainage terrain, and stream crossing
locations. The hydrology-topography diagnostic therefore records:

```text
hydrology_proximity_ratio
low_elevation_hydrology_overlap_ratio
water_crossing_presence
water_crossing_rows_n
water_crossing_length_m
valley_or_low_terrain_proxy_ratio
drainage_accumulation_proxy_score
crossing_surge_score
hydrology_topography_weather_note
```

### Juansi Weather Underestimation Evidence

`juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b` is now the clearest weather
underestimation review case:

```text
hydrology_proximity_ratio = 0.7724
low_elevation_hydrology_overlap_ratio = 0.3374
water_crossing_presence = true
water_crossing_rows_n = 36
drainage_accumulation_proxy_score = 0.8994
crossing_surge_score = 0.3292
```

Audit decision:

```text
THCI_V1_0C_WEATHER_REVIEW_STATUS =
WEATHER_CALIBRATION_ESTABLISHED_WITH_HYDROLOGY_TOPOGRAPHY_REVIEW
```
