# README current pipeline updated 20260601 IB0D v1.3b contract QA

## Status

IB0D v1.3b control-points-only contract QA completed.

IA1 / IB0C / IB0A / IB0A-2 / IB0B v1.3b are treated as converged for this branch. IB0D v1.3b is now gated by the control-points-only contract QA described here.

IB1A / IB1C / IB1G / IB1E can proceed using:

```text
outputs\ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa\
```

## Contract

IB0D v1.3b canonical input is the IB0B ordered path:

```text
outputs\ib0b_mainline_route_definition_v1_3b_control_points_only\<case_id>_mainline_ordered_path_ib0_candidates.geojson
```

The route-axis control point authority is:

```text
outputs\ib0b_mainline_route_definition_v1_3b_control_points_only\<case_id>_route_definition_control_points_used_ib0_candidates.csv
outputs\ib0b_mainline_route_definition_v1_3b_control_points_only\<case_id>_route_definition_control_points_used_ib0_candidates.geojson
```

`outputs\ib0c_anchor` is legacy / QA reference only. It is not formal trim authority for the v1.3b control-points-only branch.

## Runner

```powershell
.\.venv\Scripts\python.exe scripts\ib0_route_match\ib0d_v1_3b_control_points_only_contract_qa.py
```

Intentional rerun into the same per-case QA folders:

```powershell
.\.venv\Scripts\python.exe scripts\ib0_route_match\ib0d_v1_3b_control_points_only_contract_qa.py --allow-existing-case-dir
```

## Output

```text
outputs\ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa\
```

Required aggregate summary:

```text
outputs\ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa\ib0d_v1_3b_contract_qa_summary_all.csv
```

Each case output includes:

- `mainline_ordered_path_trimmed.geojson`
- `route_points.csv`
- `trim_summary.csv`
- `qa_summary.txt`
- `qa_map.html`
- `control_point_projection.csv`
- `self_near_pairs.csv`
- `self_near_zones.csv`

## Case status

```text
juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b       PASS
qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b WARN
qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b  WARN
zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b  WARN
```

No case is FAIL.

The WARN cases are accepted because they are same-entry routes using `keep_full` policy, and high self-near pair counts are classified as expected same-entry / summit self-near rather than unexpected route-axis defects.

## Hard fail rules

- Any `fallback_gpx_point` text in route-definition control point inputs.
- Control point offset to ordered path greater than 50 m.
- Route definition control points cannot be projected onto ordered path.
- Route definition projected order violates intended route-axis order.
- Trimmed length is unexpectedly shorter than IB0B ordered path.
- Downstream `route_points.csv` cannot be generated.
- Unexpected self-near pairs remain after expected same-entry / summit classification.

## QA map note

`qa_map.html` uses display-only offsets for overlapping control points. This makes same-location start/end and ascent/descent points visible. True locations remain available in the `true control point locations` layer and are connected to the display-offset labels by short lines.
