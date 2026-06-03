# -*- coding: utf-8 -*-
"""
batch_run_activity_points_osm_nlsc_corrected_v1b_to_v1f_qixing_lengshuikeng.py

Batch runner for qixing_lengshuikeng activity_points_osm_nlsc_corrected flow.

Flow:
  v1b offset3
  → v1c refit mainline
  → v1d summit-aware refit
  → v1e isolated orange recovery
  → v1f safe corridor recovery

This batch runner does NOT run v1g recovery.
V1G should remain diagnosis-first and reviewed-recovery-only.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path
from datetime import datetime


def run_cmd(cmd: list[str]) -> tuple[bool, str]:
    print()
    print(">>>", " ".join(str(x) for x in cmd))
    try:
        p = subprocess.run(
            cmd,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        print(p.stdout)
        return True, p.stdout
    except subprocess.CalledProcessError as e:
        print(e.stdout)
        return False, e.stdout or str(e)


def find_points_csv(activity_dir: Path, activity_id: str) -> Path | None:
    """
    Find IB3A2 labeled activity points CSV.

    Supports two layouts:

    1. Nested layout:
       <ib3a2_root>/<route_folder>/<activity_id>/*.csv

    2. Flat route-folder layout:
       <ib3a2_root>/<route_folder>/<route_folder>_<activity_id>_mapmatched_activity_labeled.csv
    """

    search_dirs = []

    if activity_dir.exists() and activity_dir.is_dir():
        search_dirs.append(activity_dir)

    # Flat-layout fallback:
    # if activity_dir = <root>/<route_folder>/<activity_id>,
    # then parent = <root>/<route_folder> may directly contain CSVs.
    parent_dir = activity_dir.parent
    if parent_dir.exists() and parent_dir.is_dir():
        search_dirs.append(parent_dir)

    all_csvs = []
    for d in search_dirs:
        all_csvs.extend(list(d.glob("*.csv")))

    if not all_csvs:
        return None

    preferred = []
    for p in all_csvs:
        name = p.name.lower()
        if activity_id.lower() not in name:
            continue
        if "summary" in name:
            continue
        if "event" in name:
            continue
        if "excursion" in name:
            continue
        if "on_route" in name and "labeled" not in name:
            continue
        if "labeled" in name:
            preferred.append(p)

    if preferred:
        return sorted(preferred, key=lambda x: len(x.name))[0]

    candidates = []
    for p in all_csvs:
        name = p.name.lower()
        if activity_id.lower() not in name:
            continue
        if "summary" in name or "event" in name or "excursion" in name:
            continue
        candidates.append(p)

    if not candidates:
        return None

    return sorted(candidates, key=lambda x: x.stat().st_size, reverse=True)[0]

def collect_activity_dirs(ib3a2_root: Path, route_folder: str) -> list[Path]:
    """
    Collect activity pseudo-directories.

    Supports:
    1. Nested layout:
       <ib3a2_root>/<route_folder>/<activity_id>/

    2. Flat layout:
       <ib3a2_root>/<route_folder>/<route_folder>_<activity_id>_mapmatched_activity_labeled.csv

    For flat layout, return pseudo paths:
       <ib3a2_root>/<route_folder>/<activity_id>
    so downstream activity_id = p.name still works.
    """

    route_root = ib3a2_root / route_folder
    if not route_root.exists():
        raise FileNotFoundError(f"IB3A2 route root not found: {route_root}")

    nested_dirs = [p for p in route_root.iterdir() if p.is_dir()]
    if nested_dirs:
        return sorted(nested_dirs, key=lambda p: p.name)

    labeled_csvs = sorted(route_root.glob(f"{route_folder}_*_mapmatched_activity_labeled.csv"))

    activity_ids = []
    prefix = f"{route_folder}_"
    suffix = "_mapmatched_activity_labeled.csv"

    for fp in labeled_csvs:
        name = fp.name
        if not name.startswith(prefix) or not name.endswith(suffix):
            continue
        activity_id = name[len(prefix):-len(suffix)]
        activity_ids.append(activity_id)

    return [route_root / aid for aid in sorted(activity_ids)]



def write_summary(summary_fp: Path, rows: list[dict]) -> None:
    summary_fp.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "route_folder",
        "activity_id",
        "points_fp",
        "v1b_status",
        "v1c_status",
        "v1d_status",
        "v1e_status",
        "v1f_status",
        "final_status",
        "v1b_fp",
        "v1c_fp",
        "v1d_fp",
        "v1e_fp",
        "v1f_fp",
        "error_stage",
        "error_message",
    ]

    with summary_fp.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--route-folder", default="qixing_lengshuikeng")
    ap.add_argument("--case-id", default="qixing_lengshuikeng_main_peak_20260523")

    ap.add_argument(
        "--ib3a2-root",
        default="outputs/ib3a2_on_route_activity_filter_v4b_after_forced_route",
        help="Root containing qixing_lengshuikeng/<activity_id> IB3A2 labeled CSVs.",
    )

    ap.add_argument(
        "--route-context-fp",
        default=(
            "outputs/ib1e_route_profile_contour_window_terrain/"
            "qixing_lengshuikeng_main_peak_20260523/"
            "qixing_lengshuikeng_main_peak_20260523_route_profile_contour_window_terrain_enriched.csv"
        ),
        help="Official IB1E OSM/NLSC route context CSV.",
    )

    ap.add_argument("--activity-id", default="", help="Optional single activity id, e.g. 37_1.")
    ap.add_argument("--limit", type=int, default=0, help="Optional max number of activities for smoke test.")

    ap.add_argument("--python-exe", default=".venv/Scripts/python.exe")

    ap.add_argument("--max-model-offset-m", type=float, default=3.0)
    ap.add_argument("--summit-route-dist-m", type=float, default=2096.0)

    # v1e parameters
    ap.add_argument("--v1e-max-segment-rows", type=int, default=5)
    ap.add_argument("--v1e-max-segment-duration-sec", type=float, default=10.0)
    ap.add_argument("--v1e-max-offset-m", type=float, default=5.0)
    ap.add_argument("--v1e-offroute-buffer-sec", type=float, default=60.0)

    # v1f parameters: verified strict safe-corridor settings
    ap.add_argument("--v1f-max-segment-rows", type=int, default=5)
    ap.add_argument("--v1f-max-segment-duration-sec", type=float, default=10.0)
    ap.add_argument("--v1f-max-offset-m", type=float, default=8.0)
    ap.add_argument("--v1f-max-prev-next-route-gap-m", type=float, default=30.0)
    ap.add_argument("--v1f-offroute-buffer-sec", type=float, default=60.0)
    ap.add_argument("--v1f-endpoint-route-tail-buffer-m", type=float, default=50.0)

    ap.add_argument(
        "--out-summary-dir",
        default="outputs/activity_points_osm_nlsc_corrected_batch_summary",
    )

    args = ap.parse_args()

    project_root = Path.cwd()
    python_exe = project_root / args.python_exe

    scripts_dir = project_root / "scripts" / "route_core_modeling"

    s_v1b = scripts_dir / "build_activity_points_osm_nlsc_corrected_v1b.py"
    s_v1c = scripts_dir / "build_activity_points_osm_nlsc_corrected_v1c_refit_mainline.py"
    s_v1d = scripts_dir / "build_activity_points_osm_nlsc_corrected_v1d_summit_aware_refit.py"
    s_v1e = scripts_dir / "build_activity_points_osm_nlsc_corrected_v1e_recover_isolated_orange.py"
    s_v1f = scripts_dir / "build_activity_points_osm_nlsc_corrected_v1f_safe_corridor_recovery.py"

    for s in [s_v1b, s_v1c, s_v1d, s_v1e, s_v1f]:
        if not s.exists():
            raise FileNotFoundError(f"Script not found: {s}")

    ib3a2_root = project_root / args.ib3a2_root
    route_context_fp = project_root / args.route_context_fp

    if not route_context_fp.exists():
        raise FileNotFoundError(f"Route context CSV not found: {route_context_fp}")

    if args.activity_id:
        activity_dirs = [ib3a2_root / args.route_folder / args.activity_id]
    else:
        activity_dirs = collect_activity_dirs(ib3a2_root, args.route_folder)

    if args.limit and args.limit > 0:
        activity_dirs = activity_dirs[: args.limit]

    # Official output roots
    out_v1b = project_root / "outputs" / "activity_points_osm_nlsc_corrected_v1b_offset3"
    out_v1c = project_root / "outputs" / "activity_points_osm_nlsc_corrected_v1c_refit_mainline_offset3"
    out_v1d = project_root / "outputs" / "activity_points_osm_nlsc_corrected_v1d_summit_aware_refit_offset3"
    out_v1e = project_root / "outputs" / "activity_points_osm_nlsc_corrected_v1e_recover_isolated_orange_offset3"
    out_v1f = project_root / "outputs" / "activity_points_osm_nlsc_corrected_v1f_safe_corridor_recovery_offset3"

    rows = []

    for activity_dir in activity_dirs:
        activity_id = activity_dir.name
        print()
        print("=" * 100)
        print(f"Activity: {activity_id}")
        print("=" * 100)

        row = {
            "route_folder": args.route_folder,
            "activity_id": activity_id,
            "v1b_status": "not_run",
            "v1c_status": "not_run",
            "v1d_status": "not_run",
            "v1e_status": "not_run",
            "v1f_status": "not_run",
            "final_status": "not_run",
            "error_stage": "",
            "error_message": "",
        }

        points_fp = find_points_csv(activity_dir, activity_id)
        if points_fp is None or not points_fp.exists():
            row["final_status"] = "failed"
            row["error_stage"] = "find_points_csv"
            row["error_message"] = f"No points CSV found in {activity_dir}"
            rows.append(row)
            continue

        row["points_fp"] = str(points_fp)

        v1b_fp = out_v1b / args.route_folder / activity_id / f"{args.route_folder}_{activity_id}_activity_points_osm_nlsc_corrected_v1.csv"
        v1c_fp = out_v1c / args.route_folder / activity_id / f"{args.route_folder}_{activity_id}_activity_points_osm_nlsc_corrected_v1c.csv"
        v1d_fp = out_v1d / args.route_folder / activity_id / f"{args.route_folder}_{activity_id}_activity_points_osm_nlsc_corrected_v1d.csv"
        v1e_fp = out_v1e / args.route_folder / activity_id / f"{args.route_folder}_{activity_id}_activity_points_osm_nlsc_corrected_v1e.csv"
        v1f_fp = out_v1f / args.route_folder / activity_id / f"{args.route_folder}_{activity_id}_activity_points_osm_nlsc_corrected_v1f.csv"

        row["v1b_fp"] = str(v1b_fp)
        row["v1c_fp"] = str(v1c_fp)
        row["v1d_fp"] = str(v1d_fp)
        row["v1e_fp"] = str(v1e_fp)
        row["v1f_fp"] = str(v1f_fp)

        stages = [
            (
                "v1b",
                [
                    str(python_exe),
                    str(s_v1b),
                    "--route-folder", args.route_folder,
                    "--activity-id", activity_id,
                    "--points-fp", str(points_fp),
                    "--route-context-fp", str(route_context_fp),
                    "--out-dir", str(out_v1b),
                    "--max-model-offset-m", str(args.max_model_offset_m),
                ],
                v1b_fp,
            ),
            (
                "v1c",
                [
                    str(python_exe),
                    str(s_v1c),
                    "--route-folder", args.route_folder,
                    "--activity-id", activity_id,
                    "--input-fp", str(v1b_fp),
                    "--out-dir", str(out_v1c),
                ],
                v1c_fp,
            ),
            (
                "v1d",
                [
                    str(python_exe),
                    str(s_v1d),
                    "--route-folder", args.route_folder,
                    "--activity-id", activity_id,
                    "--input-fp", str(v1c_fp),
                    "--out-dir", str(out_v1d),
                    "--summit-route-dist-m", str(args.summit_route_dist_m),
                ],
                v1d_fp,
            ),
            (
                "v1e",
                [
                    str(python_exe),
                    str(s_v1e),
                    "--route-folder", args.route_folder,
                    "--activity-id", activity_id,
                    "--input-fp", str(v1d_fp),
                    "--out-dir", str(out_v1e),
                    "--max-segment-rows", str(args.v1e_max_segment_rows),
                    "--max-segment-duration-sec", str(args.v1e_max_segment_duration_sec),
                    "--max-offset-m", str(args.v1e_max_offset_m),
                    "--offroute-buffer-sec", str(args.v1e_offroute_buffer_sec),
                ],
                v1e_fp,
            ),
            (
                "v1f",
                [
                    str(python_exe),
                    str(s_v1f),
                    "--route-folder", args.route_folder,
                    "--activity-id", activity_id,
                    "--input-fp", str(v1e_fp),
                    "--out-dir", str(out_v1f),
                    "--max-segment-rows", str(args.v1f_max_segment_rows),
                    "--max-segment-duration-sec", str(args.v1f_max_segment_duration_sec),
                    "--max-offset-m", str(args.v1f_max_offset_m),
                    "--max-prev-next-route-gap-m", str(args.v1f_max_prev_next_route_gap_m),
                    "--offroute-buffer-sec", str(args.v1f_offroute_buffer_sec),
                    "--endpoint-route-tail-buffer-m", str(args.v1f_endpoint_route_tail_buffer_m),
                ],
                v1f_fp,
            ),
        ]

        ok_all = True

        for stage_name, cmd, expected_fp in stages:
            ok, output = run_cmd(cmd)
            row[f"{stage_name}_status"] = "ok" if ok and expected_fp.exists() else "failed"

            if not ok or not expected_fp.exists():
                ok_all = False
                row["final_status"] = "failed"
                row["error_stage"] = stage_name
                if not expected_fp.exists():
                    row["error_message"] = f"Expected output missing: {expected_fp}"
                else:
                    row["error_message"] = output[-1000:]
                break

        if ok_all:
            row["final_status"] = "ok"

        rows.append(row)

        summary_fp_live = (
            project_root
            / args.out_summary_dir
            / f"{args.route_folder}_v1b_to_v1f_batch_summary_live.csv"
        )
        write_summary(summary_fp_live, rows)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_fp = (
        project_root
        / args.out_summary_dir
        / f"{args.route_folder}_v1b_to_v1f_batch_summary_{ts}.csv"
    )
    write_summary(summary_fp, rows)

    ok_count = sum(1 for r in rows if r.get("final_status") == "ok")
    failed_count = sum(1 for r in rows if r.get("final_status") != "ok")

    print()
    print("=" * 100)
    print("Batch completed")
    print("route_folder:", args.route_folder)
    print("activities:", len(rows))
    print("ok:", ok_count)
    print("failed:", failed_count)
    print("summary:", summary_fp)
    print("=" * 100)

    if failed_count:
        print()
        print("--- failed rows ---")
        for r in rows:
            if r.get("final_status") != "ok":
                print(r["activity_id"], r["error_stage"], r["error_message"])


if __name__ == "__main__":
    main()