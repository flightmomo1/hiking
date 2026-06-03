# Current pipeline status updated 20260604 THCI version comparison v1.0 / v1.0a / v1.0b

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

This README keeps the IB2 / IB2D v1.3b route-level baseline risk visualization checkpoint and updates THCI to the current v1.0b navigation-semantics-calibrated state with version comparison evidence.

## Current recommended THCI branch

```text
Recommended scoring root: outputs\thci_axis_scores_v1_0b\
Recommended radar root:   outputs\thci_radar_v1_0b\
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
