# IB0D v1.3b control-points-only contract

Status as of 2026-06-01:

- IA1 / IB0C / IB0A / IB0A-2 / IB0B v1.3b are converged.
- IB0D v1.3b initial run exposed a contract gap: legacy IB0D still used `outputs\ib0c_anchor` as trim authority.
- IB1 is paused until IB0D v1.3b contract / QA gate returns PASS or reviewed WARN.

## Canonical inputs

IB0D v1.3b control-points-only must use only:

- `outputs\ib0b_mainline_route_definition_v1_3b_control_points_only\<case_id>_mainline_ordered_path_ib0_candidates.geojson`
- `outputs\ib0b_mainline_route_definition_v1_3b_control_points_only\<case_id>_route_definition_control_points_used_ib0_candidates.csv`
- `outputs\ib0b_mainline_route_definition_v1_3b_control_points_only\<case_id>_route_definition_control_points_used_ib0_candidates.geojson`

The canonical route axis is the IB0B ordered path.

The route-axis control point authority is `route_definition_control_points_used`.

`outputs\ib0c_anchor` is legacy / QA reference only. It must not be used as formal IB0D trim authority for v1.3b control-points-only.

## Runner

Use:

```powershell
.\.venv\Scripts\python.exe scripts\ib0_route_match\ib0d_v1_3b_control_points_only_contract_qa.py
```

Default output root:

```text
outputs\ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa\
```

The runner does not write into the previous IB0D roots. By default it refuses an existing per-case output directory; pass `--allow-existing-case-dir` only for an intentional rerun of this same contract QA root.

## Hard FAIL

- Any input/control point text contains `fallback_gpx_point`.
- Start/end/control point offset to IB0B ordered path exceeds 50 m.
- Route definition control points cannot be projected onto ordered path.
- Route definition projected distances violate intended `order`.
- Trimmed length is unexpectedly shorter than the IB0B ordered path.
- Downstream route_points cannot be generated.
- Unexpected self-near pairs remain after classification.

## WARN

- High self-near pair count is explainable as same-entry-exit or summit self-near.
- Mainline segment set has spur warning but ordered path remains valid.
- Same-entry route uses `keep_full` policy.

## PASS

- IB0B ordered path is preserved or trimmed by route-definition control points correctly.
- Route-definition control points project onto ordered path in correct sequence.
- `route_points.csv`, `qa_summary.txt`, `qa_map.html`, and `trim_summary.csv` exist.
- Output is safe for IB1A / IB1C / IB1G / IB1E.

IB1A / IB1C / IB1G / IB1E may run only after IB0D v1.3b PASS or reviewed WARN.

## QA map control point display

`qa_map.html` renders `route_definition_control_points_used` with display-only offsets for overlapping or near-overlapping control points. This is for visual QA only and does not change route geometry, trim distances, route_points, or true control point coordinates.

- Default layer: `route_definition_control_points_used (display-offset)` shows every control point with `order:control_id` labels.
- Hidden layer: `true control point locations` shows the original point locations.
- Offset points are connected back to their true locations with short colored lines.
