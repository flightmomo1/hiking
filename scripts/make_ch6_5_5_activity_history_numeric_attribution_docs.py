#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate CH6.5.5 v0.5 documentation/update notes.

This script writes four markdown files under runs/ documenting the CH6.5.5
activity-history numeric attribution layer.

Inputs expected:
- outputs/report_figures/ch6_5_5_activity_history_primary_relabel_v0_4/
- outputs/report_figures/ch6_5_5_activity_history_numeric_attribution_v0_5/

Outputs:
- runs/README_current_pipeline_updated_20260618_ch6_5_5_activity_history_numeric_attribution.md
- runs/changelog_updated_20260618_ch6_5_5_activity_history_numeric_attribution.md
- runs/CURRENT_INDEX_updated_20260618_ch6_5_5_activity_history_numeric_attribution.md
- runs/latest_handoff_prompt_updated_20260618_ch6_5_5_activity_history_numeric_attribution.md
"""

from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


TAG = "20260618_ch6_5_5_activity_history_numeric_attribution"

V04_ROOT = "outputs/report_figures/ch6_5_5_activity_history_primary_relabel_v0_4"
V05_ROOT = "outputs/report_figures/ch6_5_5_activity_history_numeric_attribution_v0_5"

BOUNDARY = (
    "Descriptive CH6.5.5 personal activity-history evidence only. Actual hiking "
    "activity history is primary evidence; HR zone is secondary context; non-standard "
    "estimated VO2max and subjective Qixing difficulty are tertiary supporting context "
    "only and do not promote an activity into strain candidate by themselves. This is "
    "not an ability score, ability rank, ability class, final hiking risk score, route "
    "suitability score, go/no-go decision, medical diagnosis, or causality evidence."
)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=r"D:\mountain_work\115_osm")
    return p.parse_args()


def read_csv(path: Path, required=True) -> pd.DataFrame:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return pd.DataFrame()
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def md_table(df: pd.DataFrame, cols: list[str], max_rows: int | None = None) -> str:
    if df.empty:
        return "_No rows._"
    rows = df[cols].copy()
    if max_rows is not None:
        rows = rows.head(max_rows)
    return rows.to_markdown(index=False)


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    runs = root / "runs"
    runs.mkdir(parents=True, exist_ok=True)

    v04 = root / V04_ROOT
    v05 = root / V05_ROOT

    audit_v04 = read_csv(v04 / "personal_activity_history_primary_audit_v0_4.csv")
    summary_v04 = read_csv(v04 / "personal_activity_history_primary_summary_v0_4.csv")
    audit_v05 = read_csv(v05 / "personal_activity_history_numeric_attribution_audit_v0_5.csv")
    summary_v05 = read_csv(v05 / "personal_activity_history_numeric_attribution_summary_v0_5.csv")
    flag_v05 = read_csv(v05 / "personal_activity_history_numeric_attribution_flag_summary_v0_5.csv")
    attrib_v05 = read_csv(v05 / "personal_activity_history_numeric_attribution_v0_5.csv")

    audit4 = audit_v04.iloc[0].to_dict()
    audit5 = audit_v05.iloc[0].to_dict()

    primary_cases = attrib_v05[
        attrib_v05["suggested_report_case_role"].astype(str).eq("REPORT_PRIMARY_CASE_CANDIDATE")
    ].copy()
    secondary_cases = attrib_v05[
        attrib_v05["suggested_report_case_role"].astype(str).eq("REPORT_SECONDARY_CASE_CANDIDATE")
    ].copy()
    review_cases = attrib_v05[
        attrib_v05["suggested_report_case_role"].astype(str).eq("NUMERIC_DETAIL_REVIEW_NOT_PRIMARY_CASE_YET")
    ].copy()

    readme = f"""# README current pipeline update — CH6.5.5 activity-history numeric attribution

## Scope

This update documents the CH6.5.5 personal route-load / activity-history review layer.

The layer was built to support a personal activity performance radar and route-demand match workflow while preserving the core interpretation boundary:

> {BOUNDARY}

## Evidence hierarchy

| Evidence tier | Role | Notes |
|---|---|---|
| Primary | Actual hiking activity history | speed, low-speed ratio, stopped ratio, route-load behavior response, behavior-weather overlap, uphill-load exposure context |
| Secondary | HR zone / HR output context | sex-age estimated HRmax; high HR is not strain by itself |
| Tertiary | estimated VO2max / subjective Qixing difficulty | non-standard and/or subjective context only; not used to promote candidates |

## v0.4 activity-history-primary relabel

Output root:

`{V04_ROOT}`

Audit summary:

| metric | value |
|---|---:|
| activity_count | {audit4.get("activity_count")} |
| primary_activity_history_candidate_rows | {audit4.get("primary_activity_history_candidate_rows")} |
| single_factor_behavior_review_rows | {audit4.get("single_factor_behavior_review_rows")} |
| hr_context_rows | {audit4.get("hr_context_rows")} |
| profile_context_only_rows | {audit4.get("profile_context_only_rows")} |
| profile_promotion_used | {audit4.get("profile_promotion_used")} |

Audit conclusion:

`{audit4.get("audit_conclusion")}`

## v0.5 numeric attribution

Output root:

`{V05_ROOT}`

Audit summary:

| metric | value |
|---|---:|
| attribution_scope_rows | {audit5.get("attribution_scope_rows")} |
| primary_candidate_rows_in_scope | {audit5.get("primary_candidate_rows_in_scope")} |
| single_factor_review_rows_in_scope | {audit5.get("single_factor_review_rows_in_scope")} |
| metric_attribution_long_rows | {audit5.get("metric_attribution_long_rows")} |
| triggered_metric_rows | {audit5.get("triggered_metric_rows")} |
| threshold_metric_rules_n | {audit5.get("threshold_metric_rules_n")} |
| profile_promotion_used | {audit5.get("profile_promotion_used")} |

Audit conclusion:

`{audit5.get("audit_conclusion")}`

## v0.5 attribution groups

{md_table(summary_v05, ["numeric_attribution_label_v0_5", "suggested_report_case_role", "activity_count", "activity_id_short_list"])}

## Numeric trigger summary

{md_table(flag_v05, ["numeric_attention_flag", "numeric_attention_domain", "activity_count", "activity_id_short_list"])}

## Report case candidates

### Primary case candidates

{md_table(primary_cases, ["activity_id_short", "participant_id", "numeric_attribution_label_v0_5", "numeric_attention_flag_count", "movement_degradation_flag_count", "numeric_attention_flags", "hr_median_zone_sex_age_est", "tertiary_profile_context_signal"])}

### Secondary case candidates

{md_table(secondary_cases, ["activity_id_short", "participant_id", "numeric_attribution_label_v0_5", "numeric_attention_flag_count", "movement_degradation_flag_count", "numeric_attention_flags", "hr_median_zone_sex_age_est", "tertiary_profile_context_signal"])}

### Numeric-detail review, not primary cases yet

{md_table(review_cases, ["activity_id_short", "participant_id", "numeric_attribution_label_v0_5", "numeric_attention_flag_count", "movement_degradation_flag_count", "numeric_attention_flags", "hr_median_zone_sex_age_est", "tertiary_profile_context_signal"])}

## Output files

### v0.4

- `personal_activity_history_primary_full_context_v0_4.csv`
- `personal_activity_history_primary_strain_candidate_v0_4.csv`
- `personal_activity_history_single_factor_behavior_review_v0_4.csv`
- `personal_activity_history_hr_output_context_v0_4.csv`
- `personal_profile_context_only_v0_4.csv`
- `personal_activity_history_primary_summary_v0_4.csv`
- `personal_activity_history_profile_context_summary_v0_4.csv`
- `personal_activity_history_primary_audit_v0_4.csv`

### v0.5

- `personal_activity_history_numeric_attribution_v0_5.csv`
- `personal_activity_history_numeric_attribution_metric_long_v0_5.csv`
- `personal_activity_history_numeric_attribution_summary_v0_5.csv`
- `personal_activity_history_numeric_attribution_flag_summary_v0_5.csv`
- `personal_activity_history_numeric_attribution_thresholds_v0_5.csv`
- `personal_activity_history_numeric_attribution_audit_v0_5.csv`

## Next recommended work

1. Add 300s rolling movement output:
   - vertical_gain_300s_m
   - horizontal_dist_300s_m
   - VAM_300s
   - late-vs-early 300s degradation
2. Build personal activity performance radar v0 from available evidence only.
3. Keep missing axes as `INSUFFICIENT_EVIDENCE`; do not zero-fill.
"""

    changelog = f"""# Changelog update — {TAG}

## Added

- CH6.5.5 v0.4 activity-history-primary relabel evidence.
- CH6.5.5 v0.5 activity-history numeric attribution evidence.
- Evidence hierarchy:
  - primary: actual hiking activity history
  - secondary: sex-age HR zone context
  - tertiary: estimated VO2max and subjective difficulty
- Numeric attribution of candidate/review labels using CH6.5.4 reference thresholds.

## Results

### v0.4

- activity_count: {audit4.get("activity_count")}
- primary_activity_history_candidate_rows: {audit4.get("primary_activity_history_candidate_rows")}
- single_factor_behavior_review_rows: {audit4.get("single_factor_behavior_review_rows")}
- hr_context_rows: {audit4.get("hr_context_rows")}
- profile_context_only_rows: {audit4.get("profile_context_only_rows")}
- profile_promotion_used: {audit4.get("profile_promotion_used")}
- audit_conclusion: `{audit4.get("audit_conclusion")}`

### v0.5

- attribution_scope_rows: {audit5.get("attribution_scope_rows")}
- primary_candidate_rows_in_scope: {audit5.get("primary_candidate_rows_in_scope")}
- single_factor_review_rows_in_scope: {audit5.get("single_factor_review_rows_in_scope")}
- metric_attribution_long_rows: {audit5.get("metric_attribution_long_rows")}
- triggered_metric_rows: {audit5.get("triggered_metric_rows")}
- threshold_metric_rules_n: {audit5.get("threshold_metric_rules_n")}
- profile_promotion_used: {audit5.get("profile_promotion_used")}
- audit_conclusion: `{audit5.get("audit_conclusion")}`

## Interpretation boundary

{BOUNDARY}

## Notes

- High HR controlled output remains separated from route-load strain candidates.
- Non-standard estimated VO2max and subjective Qixing difficulty are retained only as tertiary supporting context.
- v0.5 identifies:
  - 4 primary report case candidates: `42_1`, `43_1`, `46_1`, `48_1`
  - 3 secondary report case candidates: `23_1`, `38_1`, `9_1`
  - 5 numeric-detail review rows: `16_1`, `28_1`, `37_1`, `44_1`, `8_1`
"""

    current_index = f"""# CURRENT INDEX update — {TAG}

## Current effective entry points

### CH6.5.5 v0.4 activity-history-primary relabel

Script:

`scripts/make_ch6_5_5_activity_history_primary_relabel_v0_4.py`

Output root:

`{V04_ROOT}`

Primary output:

`personal_activity_history_primary_full_context_v0_4.csv`

Audit:

`personal_activity_history_primary_audit_v0_4.csv`

### CH6.5.5 v0.5 activity-history numeric attribution

Script:

`scripts/make_ch6_5_5_activity_history_numeric_attribution_v0_5.py`

Output root:

`{V05_ROOT}`

Primary outputs:

- `personal_activity_history_numeric_attribution_v0_5.csv`
- `personal_activity_history_numeric_attribution_metric_long_v0_5.csv`
- `personal_activity_history_numeric_attribution_summary_v0_5.csv`
- `personal_activity_history_numeric_attribution_flag_summary_v0_5.csv`
- `personal_activity_history_numeric_attribution_thresholds_v0_5.csv`
- `personal_activity_history_numeric_attribution_audit_v0_5.csv`

## Current interpretation

Use v0.5 as the current explanation layer for CH6.5.5 candidate/review reasons.

Do not use estimated VO2max or subjective difficulty as primary evidence.

Do not interpret high HR alone as strain.

## Current candidate groups

{md_table(summary_v05, ["numeric_attribution_label_v0_5", "suggested_report_case_role", "activity_count", "activity_id_short_list"])}

## Boundary

{BOUNDARY}
"""

    handoff = f"""# Latest handoff prompt — {TAG}

Continue from:

`D:\\mountain_work\\115_osm`

The CH6.5.5 personal profile / activity-history review layer has reached v0.5.

## Completed

- v0.2: participant profile metadata join with sex-age estimated HRmax and HR zones.
- v0.3: split route-load strain candidates from high-HR controlled output context.
- v0.4: relabel evidence hierarchy to make actual hiking activity history primary.
- v0.5: numeric attribution explaining which observed activity-history metrics triggered candidates or review rows.

## Key outputs

v0.4 output root:

`{V04_ROOT}`

v0.5 output root:

`{V05_ROOT}`

v0.5 audit conclusion:

`{audit5.get("audit_conclusion")}`

## Key counts

- v0.4 primary activity-history candidates: {audit4.get("primary_activity_history_candidate_rows")}
- v0.4 single-factor behavior review rows: {audit4.get("single_factor_behavior_review_rows")}
- v0.5 attribution scope rows: {audit5.get("attribution_scope_rows")}
- v0.5 triggered metric rows: {audit5.get("triggered_metric_rows")}

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

{BOUNDARY}

## Recommended next step

Build CH6.5.5 personal activity performance radar v0 using only available evidence and explicit `INSUFFICIENT_EVIDENCE` for missing axes.

High-priority missing features:
- 300s vertical gain
- 300s horizontal movement distance
- 300s VAM
- late-vs-early 300s movement degradation
- terrain/surface x movement-efficiency join
"""

    files = {
        runs / f"README_current_pipeline_updated_{TAG}.md": readme,
        runs / f"changelog_updated_{TAG}.md": changelog,
        runs / f"CURRENT_INDEX_updated_{TAG}.md": current_index,
        runs / f"latest_handoff_prompt_updated_{TAG}.md": handoff,
    }

    for path, text in files.items():
        path.write_text(text, encoding="utf-8")

    print({
        "written_files": {path.name: str(path) for path in files},
        "audit_v04": audit4.get("audit_conclusion"),
        "audit_v05": audit5.get("audit_conclusion"),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
