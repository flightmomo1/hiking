#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
Generate main-level rollup documents for CH6.5.5 navigation context milestones.

Expected working directory:
  D:\mountain_work\115_osm

Scope:
  Documentation only.
  Does not modify evidence outputs, radar tables, axis contracts, or scoring logic.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from textwrap import dedent


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
SCRIPTS = ROOT / "scripts"

DATE_TAG = "20260620"
SLUG = "ch6_5_5_navigation_context_main_rollup"

CURRENT_INDEX = RUNS / f"CURRENT_INDEX_updated_{DATE_TAG}_{SLUG}.md"
CHANGELOG = RUNS / f"changelog_updated_{DATE_TAG}_{SLUG}.md"
HANDOFF = RUNS / f"latest_handoff_prompt_updated_{DATE_TAG}_{SLUG}.md"
README = SCRIPTS / f"README_current_pipeline_updated_{DATE_TAG}_{SLUG}.md"


MILESTONE_TAGS = [
    "ch6-5-5-navigation-context-v1-main-20260620",
    "ch6-5-5-route-following-navigation-interpretation-v1-main-20260620",
]

BOUNDARY_TEXT = """\
This rollup is documentation only.

It does not create, modify, or authorize:
- ability scores
- ability ranks
- ability classes
- THCI scores
- radar scores
- navigation ability scores
- final hiking risk scores
- route suitability scores
- go/no-go decisions
- medical diagnoses or causal claims
"""


def run_git(args: list[str]) -> str:
    try:
        out = subprocess.check_output(
            ["git", *args],
            cwd=ROOT,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return out.strip()
    except Exception as exc:  # pragma: no cover
        return f"UNAVAILABLE: {exc}"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def build_current_index() -> str:
    head = run_git(["log", "-1", "--oneline", "--decorate"])
    branch = run_git(["branch", "--show-current"])
    tags = "\n".join(f"- `{tag}`" for tag in MILESTONE_TAGS)

    return dedent(f"""\
    # CURRENT INDEX — CH6.5.5 Navigation Context Main Rollup ({DATE_TAG})

    ## Current branch / HEAD

    - branch at generation time: `{branch}`
    - HEAD at generation time: `{head}`

    ## Purpose

    This document is a main-level milestone rollup for the CH6.5.5 navigation-context work chain.

    It records that the navigation-challenge line has moved from source-gap diagnosis to governed context source, and then to an interpretation layer paired with route-following stability.

    ## Fixed tags

    {tags}

    ## Milestone chain

    1. **IB1 route topology generator**
       - Created governed node-degree / edge / side-branch topology evidence.
       - Produced governed fork and decision-point source candidates.
       - Key status: `ADMIT_AS_GOVERNED_FORK_DECISION_POINT_SOURCE_CANDIDATE`.

    2. **CH6.5.5 navigation challenge context consumption**
       - Consumed the governed topology source as route/activity context.
       - Excluded `6_1` from formal activity context.
       - Key status: `ADMIT_AS_NAVIGATION_CHALLENGE_CONTEXT_SOURCE`.

    3. **CH6.5.5 route-following × navigation context interpretation**
       - Combined route-following stability proxy with navigation-challenge exposure context.
       - Produced interpretation labels and review flags only.
       - Key status: `ADMIT_AS_ROUTE_FOLLOWING_NAVIGATION_CONTEXT_INTERPRETATION`.

    ## Mainline result

    The following closed loop is now represented on `main`:

    ```text
    source gap
    → IB1 governed topology source candidate
    → CH6.5.5 governed navigation challenge context
    → route-following × navigation interpretation layer
    → docs
    → main
    → tags
    ```

    ## Governance boundary

    {BOUNDARY_TEXT}
    """).strip() + "\n"


def build_changelog() -> str:
    return dedent(f"""\
    # Changelog — CH6.5.5 Navigation Context Main Rollup ({DATE_TAG})

    ## Summary

    Added a main-level documentation rollup for the CH6.5.5 navigation-context closure.

    This rollup documents two fixed milestones:

    - `ch6-5-5-navigation-context-v1-main-20260620`
    - `ch6-5-5-route-following-navigation-interpretation-v1-main-20260620`

    ## Milestone 1 — Navigation challenge context source

    Completed chain:

    ```text
    CH6.5.5 navigation challenge exposure source gap
    → IB1 route topology node-degree generator
    → governed fork / decision-point source candidate
    → CH6.5.5 navigation challenge context consumption
    → docs
    → main
    → tag
    ```

    Key governance notes:

    - `6_1` was excluded from formal activity context.
    - Navigation challenge exposure is admitted as governed context source.
    - It is not a personal ability axis.

    ## Milestone 2 — Route-following × navigation interpretation layer

    Completed chain:

    ```text
    route_following_stability
    + navigation_challenge_exposure
    → interpretation context layer
    → docs
    → main
    → tag
    ```

    Key governance notes:

    - `output_interpretation_count = 25`
    - `context_available_count = 25`
    - `review_recommended_count = 10`
    - `6_1 excluded = True`
    - Interpretation labels are contextual review aids only.

    ## No behavioral or scoring authority added

    {BOUNDARY_TEXT}
    """).strip() + "\n"


def build_handoff() -> str:
    return dedent(f"""\
    # Latest Handoff Prompt — CH6.5.5 Navigation Context Main Rollup ({DATE_TAG})

    Continue from `D:\\mountain_work\\115_osm`.

    Current main milestone state:

    - `main` includes the CH6.5.5 navigation challenge context source closure.
    - `main` includes the route-following × navigation challenge interpretation layer.
    - Two milestone tags have been pushed:
      - `ch6-5-5-navigation-context-v1-main-20260620`
      - `ch6-5-5-route-following-navigation-interpretation-v1-main-20260620`

    ## Interpretation

    The project now has a governed context source for navigation challenge exposure and a downstream interpretation layer that relates it to route-following stability.

    Use the interpretation layer to explain route-following evidence in context, not to score navigation ability.

    ## Important boundary

    {BOUNDARY_TEXT}

    ## Recommended next work

    Prefer one of these before adding new scoring logic:

    1. Review whether documentation entry points are clear enough for future handoff.
    2. Build a short report-section paragraph for CH6.5.5 explaining the closed loop.
    3. Audit whether any downstream report text accidentally describes navigation challenge exposure as a score or ability axis.
    """).strip() + "\n"


def build_readme() -> str:
    return dedent(f"""\
    # README Current Pipeline Update — CH6.5.5 Navigation Context Main Rollup ({DATE_TAG})

    ## Scope

    This README update records the current `main` milestone for CH6.5.5 navigation context work.

    It is documentation only and should not be interpreted as a new pipeline execution step.

    ## Current governed status

    - `navigation_challenge_exposure`: governed context source available.
    - `route_following_navigation_context_interpretation`: governed interpretation layer available.
    - `route_following_stability`: remains a limited proxy axis already handled by the existing radar governance.
    - `navigation_challenge_exposure`: remains context, not an axis.

    ## Operational boundary

    Do not consume navigation challenge exposure as a personal ability score.

    Do not use it as a radar axis unless a separate explicit governance review admits it, which this rollup does not do.

    ## Fixed tags

    - `ch6-5-5-navigation-context-v1-main-20260620`
    - `ch6-5-5-route-following-navigation-interpretation-v1-main-20260620`

    ## Non-goals

    {BOUNDARY_TEXT}
    """).strip() + "\n"


def main() -> None:
    write(CURRENT_INDEX, build_current_index())
    write(CHANGELOG, build_changelog())
    write(HANDOFF, build_handoff())
    write(README, build_readme())

    print("Wrote:")
    for path in [CURRENT_INDEX, CHANGELOG, HANDOFF, README]:
        print(f"- {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
