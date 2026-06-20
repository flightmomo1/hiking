# Latest handoff prompt — 20260618_ch6_5_5_activity_history_numeric_attribution

Continue from:

`D:\mountain_work\115_osm`

The CH6.5.5 personal profile / activity-history review layer has reached v0.5.

## Completed

- v0.2: participant profile metadata join with sex-age estimated HRmax and HR zones.
- v0.3: split route-load strain candidates from high-HR controlled output context.
- v0.4: relabel evidence hierarchy to make actual hiking activity history primary.
- v0.5: numeric attribution explaining which observed activity-history metrics triggered candidates or review rows.

## Key outputs

v0.4 output root:

`outputs/report_figures/ch6_5_5_activity_history_primary_relabel_v0_4`

v0.5 output root:

`outputs/report_figures/ch6_5_5_activity_history_numeric_attribution_v0_5`

v0.5 audit conclusion:

`PASS_CH6_5_5_ACTIVITY_HISTORY_NUMERIC_ATTRIBUTION_V0_5_DESCRIPTIVE_ONLY`

## Key counts

- v0.4 primary activity-history candidates: 7
- v0.4 single-factor behavior review rows: 5
- v0.5 attribution scope rows: 12
- v0.5 triggered metric rows: 38

## Current report interpretation

Use actual hiking activity history as the primary evidence.

Primary cases:
- `42_1`
- `43_1`
- `46_1`
- `48_1`

Secondary cases:
- `23_1`
- `38_1`
- `9_1`

Numeric-detail review, not primary report cases yet:
- `16_1`
- `28_1`
- `37_1`
- `44_1`
- `8_1`

## Boundary

Descriptive CH6.5.5 personal activity-history evidence only. Actual hiking activity history is primary evidence; HR zone is secondary context; non-standard estimated VO2max and subjective Qixing difficulty are tertiary supporting context only and do not promote an activity into strain candidate by themselves. This is not an ability score, ability rank, ability class, final hiking risk score, route suitability score, go/no-go decision, medical diagnosis, or causality evidence.

## Recommended next step

Build CH6.5.5 personal activity performance radar v0 using only available evidence and explicit `INSUFFICIENT_EVIDENCE` for missing axes.

High-priority missing features:
- 300s vertical gain
- 300s horizontal movement distance
- 300s VAM
- late-vs-early 300s movement degradation
- terrain/surface x movement-efficiency join
