# CURRENT INDEX — CH6.5.5 300s Movement Evidence Admission Review

## Status

Current branch:

`codex/ch6-5-5-300s-movement-evidence-admission-review`

Latest committed result:

`c8c5248 Add CH6.5.5 300s movement evidence admission review`

Base evidence branch:

`codex/ch6-5-5-horizontal-movement-300s-corrected-data-study`

Base evidence commit:

`208058f Add CH6.5.5 movement 300s corrected-data study`

## Current Effective Evidence

Input evidence root:

`outputs/report_figures/ch6_5_5_movement_300s_corrected_data_study_v1_1`

Admission review output root:

`outputs/report_figures/ch6_5_5_300s_movement_evidence_admission_review_v1`

Main script:

`scripts/make_ch6_5_5_300s_movement_evidence_admission_review_v1.py`

## Admission Review Conclusion

The 300-second movement evidence is retained as descriptive / supporting evidence only.

Horizontal 300s evidence:

- Covered baseline activities: 6 / 25
- Valid windows: 14
- Admission result: do not admit as standalone radar axis

Vertical 300s evidence:

- Covered baseline activities: 6 / 25
- Valid windows: 45
- Admission result: do not admit as standalone radar axis

Combined horizontal + vertical evidence:

- Covered baseline activities: 2 / 25
- Admission result: do not admit as combined standalone axis

Admitted QA items:

- `route_continuity_300s_gate`
- `positive_delta_artifact_guard`

HR representative windows:

- Retained as supporting context only

## Boundary

This review does not compute or authorize radar scores, ability scores, ability ranks, ability classes, THCI scores, final hiking risk scores, route suitability scores, go/no-go decisions, medical diagnoses, or causality claims.

## Recommended Next Step

Next work should consume the admitted QA gate / guard in downstream review logic, not promote 300s movement metrics into radar axes.
