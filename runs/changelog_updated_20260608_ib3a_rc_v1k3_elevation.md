# Changelog - 2026-06-08 IB3A-RC v1k3 Elevation and Gain-Loss

## Completed Engineering Nodes

### v1d3-v1i Evidence and Classification

Commit:

- `581f511 Add IB3A-RC full-batch candidate labeling and wrong-route QA`

This node includes candidate projection and context, summit stabilization, transition evidence, off-target detection, zone consolidation, mainline membership, and route-level wrong-route rules.

### v1j Display Trajectory

Commit:

- `0b04c81 Add IB3A-RC display trajectory refit layer`

The qixing_lengshuikeng full26 run passed with 345,979 rows. v1j adds display coordinates and raw-vs-display QA only. It does not create calibrated fields.

### v1k Minimal Horizontal Dataset

Commit:

- `70e8ffe Add IB3A-RC calibrated activity dataset horizontal layer`

The qixing_lengshuikeng full26 run passed with 26/26 activities, 345,979 rows, row order preserved, protected fields changed = 0, and no semantic mismatch checks.

### v1k2 Calibrated Motion Dataset

Commit:

- `5076517 Add IB3A-RC calibrated motion and artifact QA layers`

v1k2 adds calibrated horizontal motion fields on top of v1k without modifying v1k/v1j/v1i outputs.

Script:

- `scripts/ib3_activity_environment/ib3a_rc_build_calibrated_motion_v1k2.py`

Output root:

- `outputs/ib3a_rc_calibrated_motion_v1k2_qixing_lengshuikeng_duplicate_policy_full26_qa`

Full26 result:

- PASS / FAIL = 26 / 0
- total rows = 345,979
- row count and order preserved
- protected fields changed = 0
- v1k SHA-256 unchanged
- non-representative speed rows = 0
- forbidden elevation / NLSC / facility / radar / THCI fields = 0

### v1k2a Motion Artifact Classification

Commit:

- `5076517 Add IB3A-RC calibrated motion and artifact QA layers`

v1k2a classifies speed and distance artifacts detected in v1k2. It is a QA/review layer and does not modify the v1k2 source outputs.

Scripts:

- `scripts/ib3_activity_environment/ib3a_rc_classify_motion_artifacts_v1k2a.py`
- `scripts/ib3_activity_environment/ib3a_rc_plot_motion_artifacts_v1k2a.py`
- `scripts/ib3_activity_environment/ib3a_rc_plot_calibrated_motion_v1k2.py`

Output root:

- `outputs/ib3a_rc_calibrated_motion_artifacts_v1k2a_qixing_lengshuikeng_full26_qa`

Full26 result:

- PASS / FAIL = 26 / 0
- protected fields changed = 0
- input SHA-256 unchanged
- forbidden new columns = none

Top artifact cases:

- `44_1` = 196 artifacts, 156 summit artifacts
- `45_1` = 147 artifacts, 124 summit artifacts
- `23_1` = 125 artifacts, 52 summit artifacts
- `36_1` = 83 artifacts, 37 summit artifacts
- `28_1` = 82 artifacts, 55 summit artifacts
- `42_1` = 81 artifacts, 29 summit artifacts
- `48_1` = 75 artifacts, 29 summit artifacts
- `46_1` = 74 artifacts, 22 summit artifacts

### v1k3 Calibrated Elevation / Slope / Cumulative Gain-Loss

Commit:

- `855f5a3 Add IB3A-RC calibrated elevation and gain-loss layer`

Script:

- `scripts/ib3_activity_environment/ib3a_rc_build_calibrated_elevation_v1k3.py`

Input roots:

- v1k2a: `outputs/ib3a_rc_calibrated_motion_artifacts_v1k2a_qixing_lengshuikeng_full26_qa`
- IB1E route profile: `outputs/ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa/qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b/qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b_route_profile_contour_window_terrain_enriched.csv`

Output root:

- `outputs/ib3a_rc_calibrated_elevation_v1k3_join_hard_gate_full26_qa`

Full26 result:

- PASS / FAIL = 26 / 0
- total rows = 345,979
- row count and order preserved
- protected fields changed = 0
- v1k2a source SHA-256 unchanged
- forbidden facility / radar / THCI fields = 0
- no v1k3 HTML/PNG visual QA artifacts produced

v1k3 added:

- `calibrated_elevation_m`
- `calibrated_elevation_source`
- `calibrated_elevation_confidence`
- `calibrated_elevation_review_required`
- `elevation_lookup_method`
- `elevation_reference_id`
- `elevation_join_dist_m`
- `elevation_profile_dist_m`
- `elevation_profile_ele_smooth_m`
- `elevation_profile_ambiguous_flag`
- `elevation_profile_ambiguity_reason`
- `elevation_profile_candidate_count_10m`
- `elevation_profile_candidate_dist_range_m`
- `elevation_profile_dist_jump_flag`
- `calibrated_delta_elevation_m`
- `calibrated_slope_pct`
- `slope_review_required`
- `elevation_step_valid`
- `calibrated_cumulative_gain_m`
- `calibrated_cumulative_loss_m`
- `elevation_artifact_flag`
- `elevation_artifact_reason`
- `gain_loss_excluded_reason`

## v1k3 Design Decisions

### Elevation Source Policy

- `MAINLINE_CORE`: spatial nearest join from calibrated lat/lon to IB1E route profile.
- `MAINLINE_SUMMIT_STAY`: spatial nearest join to IB1E route profile with summit-specific source label.
- `CONNECTOR`: spatial nearest join to IB1E route profile with connector review confidence.
- `WRONG_ROUTE`: raw elevation fallback.
- `OFF_TARGET` / raw GPS fallback: raw elevation fallback.
- Unknown route class: raw elevation fallback with review status.

### Route-Profile Ambiguity Policy

Cold-water-pit route profile has self-near / route-phase ambiguity. A spatially nearby IB1E point can belong to early-route or late-route profile distance. v1k3 therefore uses conservative QA gates:

- profile candidates within 10 m spanning more than 100 m of route distance are marked as soft QA evidence.
- profile distance jumps over 100 m on small-step rows are marked as soft QA evidence.
- profile distance jump becomes hard exclusion only when join distance or elevation delta is suspicious.
- `elevation_join_dist_m > 10m` is hard-excluded from slope/gain-loss.
- elevation delta over 10 m is labeled as an elevation artifact and excluded from slope/gain-loss.

### Gain/Loss Rule

Cumulative gain/loss uses only rows satisfying conservative conditions:

- representative timestamp row
- time interval valid
- not motion artifact
- calibrated elevation exists
- previous valid elevation exists
- calibrated step distance exists and is at least 3 m
- not high join-distance hard exclusion
- not hard profile jump exclusion
- not elevation artifact
- gain/loss increments only when absolute vertical delta exceeds 1 m

## v1k3 Full26 QA Highlights

### Overall

- full26 PASS = 26/26
- rows = 345,979
- protected fields changed = 0
- input SHA-256 unchanged = True for all activities

### Highest Cumulative Gain/Loss Review Focus

| Activity | Gain m | Loss m | Slope-valid rows | Notes |
|---|---:|---:|---:|---|
| `30_1` | 193.34 | 214.29 | 527 | high cumulative gain/loss; keep as QA focus |
| `38_1` | 147.55 | 185.75 | 490 | high cumulative gain/loss; keep as QA focus |
| `23_1` | 45.60 | 40.67 | 107 | acceptable with review flags |
| `35_1` | 48.42 | 37.35 | 60 | acceptable with review flags |

### Highest Join Hard-Excluded Rows

| Activity | Join hard-excluded rows |
|---|---:|
| `44_1` | 191 |
| `30_1` | 127 |
| `6_1` | 98 |
| `45_1` | 88 |
| `35_1` | 76 |
| `15_1` | 73 |

### Highest Elevation Artifact Rows

| Activity | Elevation artifact rows |
|---|---:|
| `15_1` | 45 |
| `30_1` | 42 |
| `36_1` | 24 |
| `42_1` | 18 |
| `38_1` | 13 |

### Lowest Slope-Valid Rows

| Activity | Slope-valid rows |
|---|---:|
| `36_1` | 29 |
| `37_1` | 43 |
| `15_1` | 45 |
| `41_1` | 49 |
| `6_1` | 51 |

Interpretation:

- `30_1` and `38_1` are not immediate failures because their high gain/loss is supported by many slope-valid rows.
- `15_1`, `30_1`, and `36_1` should remain elevation artifact QA focus.
- `44_1` remains a route-phase / transition QA focus due to high join hard-exclusion rows.
- Low slope-valid rows are expected because v1k3 intentionally applies conservative filters.

## v1k3 Boundaries Preserved

- Raw activity elevation was not overwritten.
- v1k2a input rows were not changed.
- Wrong-route rows were not forced to canonical mainline elevation.
- Off-target rows used raw elevation fallback.
- Duplicate timestamp non-representative rows were preserved.
- Motion artifact rows were preserved and excluded from gain/loss where appropriate.
- Elevation artifact rows were preserved and labeled.
- No facility/radar evidence was added.
- No THCI recomputation was performed.
- No route risk or model inclusion gate was implemented.

## Known Issue: Route-Phase Ambiguity

Row-level QA showed repeated alternation between early-route and late-route `elevation_profile_dist_m` values in some activities. Examples include:

- `30_1`: early rows alternate between profile distance around `10` m and `4178` m.
- `44_1`: early rows alternate between profile distance around `0` m and `4187` m.
- `15_1`: early rows alternate between profile distance around `180` m and `4009` m.
- `36_1`: early rows alternate between profile distance around `13` m and `4172` m.

Interpretation:

- This is route-profile phase ambiguity caused by spatial-nearest join near self-near or overlapping route sections.
- v1k3 does not solve route phase.
- v1k3 contains soft and hard QA gates to prevent obvious bad joins from contaminating slope/gain-loss.
- Future improvement should use route-phase-aware IB1E profile candidate selection.

## Next Stage

Recommended next stage:

- `IB3K-RC v1k3d elevation QA plotter` or `IB3K-RC v1k4 elevation visual QA`

Deferred:

- v1l OSM facility interaction / THCI radar evidence
- IB3F-RC activity-level feature aggregation
- IB3H-RC formal model inclusion gate
- v1e2 / v1h2 summit-anchor smoothing / hysteresis
