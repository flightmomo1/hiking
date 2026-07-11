# -*- coding: utf-8 -*-
"""Batch runner for four-route THCI v1.2 support-updated official outputs.

This wrapper delegates scoring and radar generation to the existing official
v1.2 support-updated scripts when their fixed official outputs are missing.
It does not modify scoring scripts or risk semantics config, and it does not
run any v1.3 weather-terrain, candidate, or fusion pipeline.
"""

from __future__ import annotations

import argparse
import csv
import json
import py_compile
import shutil
import struct
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

ROUTES = [
    "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b",
    "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b",
    "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b",
    "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b",
]

AXES = [
    "physical_difficulty_score",
    "technical_difficulty_score",
    "baseline_hazard_score",
    "navigation_risk_score",
    "support_difficulty_score",
    "weather_impact_score",
]

COMPUTE_SCRIPT = PROJECT_ROOT / "scripts" / "thci_compute_axis_scores_v1_2_support_updated.py"
PLOT_SCRIPT = PROJECT_ROOT / "scripts" / "thci_plot_radar_v1_2_support_updated.py"

V10C_ROOT = PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_0c"
OFFICIAL_SCORE_ROOT = PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_2_support_updated"
OFFICIAL_RADAR_ROOT = PROJECT_ROOT / "outputs" / "thci_radar_v1_2_support_updated"
BATCH_ROOT = PROJECT_ROOT / "outputs" / "thci_v1_2_support_updated_four_route_batch_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true", help="Overwrite batch outputs.")
    return parser.parse_args()


def python_executable() -> str:
    venv = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if venv.exists():
        return str(venv)
    return sys.executable


def run_command(args: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        args,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "args": args,
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def official_paths(case_id: str) -> dict[str, Path]:
    return {
        "axis_csv": OFFICIAL_SCORE_ROOT / case_id / f"{case_id}_thci_axis_scores_v1_2_support_updated.csv",
        "summary_json": OFFICIAL_SCORE_ROOT / case_id / f"{case_id}_thci_axis_score_summary_v1_2_support_updated.json",
        "comparison_csv": OFFICIAL_SCORE_ROOT / case_id / f"{case_id}_thci_axis_scores_v1_0c_vs_v1_2_support_updated_comparison.csv",
        "radar_png": OFFICIAL_RADAR_ROOT / case_id / f"{case_id}_thci_radar_v1_2_support_updated.png",
        "radar_summary_json": OFFICIAL_RADAR_ROOT / case_id / f"{case_id}_thci_radar_summary_v1_2_support_updated.json",
        "radar_plot_csv": OFFICIAL_RADAR_ROOT / case_id / f"{case_id}_thci_radar_plot_data_v1_2_support_updated.csv",
    }


def batch_paths(case_id: str) -> dict[str, Path]:
    case_dir = BATCH_ROOT / case_id
    return {
        "axis_csv": case_dir / f"{case_id}_thci_axis_scores_v1_2_support_updated.csv",
        "summary_json": case_dir / f"{case_id}_thci_axis_score_summary_v1_2_support_updated.json",
        "comparison_csv": case_dir / f"{case_id}_thci_axis_scores_v1_0c_vs_v1_2_support_updated_comparison.csv",
        "radar_png": case_dir / f"{case_id}_thci_radar_v1_2_support_updated.png",
        "radar_summary_json": case_dir / f"{case_id}_thci_radar_summary_v1_2_support_updated.json",
        "radar_plot_csv": case_dir / f"{case_id}_thci_radar_plot_data_v1_2_support_updated.csv",
    }


def target_outputs_exist(paths: dict[str, Path]) -> bool:
    return paths["axis_csv"].exists() and paths["summary_json"].exists() and paths["radar_png"].exists()


def official_score_exists(paths: dict[str, Path]) -> bool:
    return paths["axis_csv"].exists() and paths["summary_json"].exists()


def official_radar_exists(paths: dict[str, Path]) -> bool:
    return paths["radar_png"].exists()


def read_first_csv_row(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            return dict(row)
    raise ValueError(f"CSV is empty: {path}")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def float_value(row: dict[str, Any], key: str) -> float:
    try:
        return float(row.get(key, 0.0))
    except (TypeError, ValueError):
        return 0.0


def png_size(path: Path) -> tuple[bool, int | None, int | None, str]:
    if not path.exists():
        return False, None, None, "missing"
    try:
        with path.open("rb") as handle:
            sig = handle.read(24)
        if len(sig) < 24 or sig[:8] != b"\x89PNG\r\n\x1a\n":
            return False, None, None, "not_png"
        width, height = struct.unpack(">II", sig[16:24])
        return True, int(width), int(height), "ok"
    except Exception as exc:
        return False, None, None, str(exc)


def copy_outputs(src: dict[str, Path], dst: dict[str, Path], overwrite: bool) -> list[str]:
    copied = []
    dst["axis_csv"].parent.mkdir(parents=True, exist_ok=True)
    for key, src_path in src.items():
        if not src_path.exists():
            continue
        dst_path = dst[key]
        if dst_path.exists() and not overwrite:
            continue
        shutil.copy2(src_path, dst_path)
        copied.append(key)
    return copied


def py_compile_result() -> dict[str, Any]:
    try:
        py_compile.compile(str(Path(__file__).resolve()), doraise=True)
        return {"status": "PASS", "returncode": 0, "message": ""}
    except Exception as exc:  # pragma: no cover
        return {"status": "FAIL", "returncode": 1, "message": str(exc)}


def git_status_short() -> str:
    result = run_command(["git", "status", "--short"])
    if result["returncode"] != 0:
        return result["stderr"] or result["stdout"]
    return result["stdout"]


def ensure_official_outputs(case_id: str, paths: dict[str, Path]) -> tuple[str, list[dict[str, Any]]]:
    commands = []
    status_parts = []
    py = python_executable()

    if official_score_exists(paths):
        status_parts.append("official_score_exists")
    else:
        result = run_command([py, str(COMPUTE_SCRIPT), "--case-id", case_id])
        commands.append(result)
        status_parts.append("compute_ran" if result["returncode"] == 0 else "compute_failed")
        if result["returncode"] != 0:
            return "|".join(status_parts), commands

    if official_radar_exists(paths):
        status_parts.append("official_radar_exists")
    else:
        result = run_command([py, str(PLOT_SCRIPT), "--case-id", case_id])
        commands.append(result)
        status_parts.append("plot_ran" if result["returncode"] == 0 else "plot_failed")

    return "|".join(status_parts), commands


def summarize_case(case_id: str, status: str, skip_reason: str, copied: list[str], commands: list[dict[str, Any]]) -> dict[str, Any]:
    dst = batch_paths(case_id)
    axis_row = read_first_csv_row(dst["axis_csv"]) if dst["axis_csv"].exists() else {}
    summary = read_json(dst["summary_json"]) if dst["summary_json"].exists() else {}
    old_scores = summary.get("previous_v1_0c_axis_scores", {}) if isinstance(summary, dict) else {}
    png_ok, png_width, png_height, png_status = png_size(dst["radar_png"])

    out: dict[str, Any] = {
        "case_id": case_id,
        "status": status,
        "skip_reason": skip_reason,
        "copied_outputs": "|".join(copied),
        "command_status": "; ".join(
            f"{' '.join(cmd['args'][-3:])} rc={cmd['returncode']}" for cmd in commands
        ),
        "axis_csv": str(dst["axis_csv"]),
        "summary_json": str(dst["summary_json"]),
        "radar_png": str(dst["radar_png"]),
        "png_openable": png_ok,
        "png_width": png_width or "",
        "png_height": png_height or "",
        "png_status": png_status,
        "support_changed": False,
        "other_axes_unchanged": "",
    }

    for axis in AXES:
        new_score = float_value(axis_row, axis)
        old_score = float(old_scores.get(axis, new_score)) if isinstance(old_scores, dict) else new_score
        out[axis] = new_score
        out[f"v1_0c_{axis}"] = old_score
        out[f"delta_{axis}"] = new_score - old_score

    out["support_changed"] = abs(float(out["delta_support_difficulty_score"])) > 1e-12
    other_axes = [axis for axis in AXES if axis != "support_difficulty_score"]
    out["other_axes_unchanged"] = all(abs(float(out[f"delta_{axis}"])) <= 1e-12 for axis in other_axes)
    return out


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def build_report(rows: list[dict[str, Any]], compile_info: dict[str, Any], git_status: str) -> str:
    lines = [
        "# THCI v1.2 Support Updated Four Route Batch v1",
        "",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Guardrails:",
        "- Existing official THCI v1.2 support-updated scripts were used via wrapper.",
        "- Official scoring logic was not modified.",
        "- Risk semantics config was not modified.",
        "- v1.0c outputs were not overwritten.",
        "- v1.3 weather-terrain adapter, candidate simulation, fusion, and candidate radar were not run.",
        "",
        "## Case Summary",
        "",
        "| Case | Status | Support v1.0c | Support v1.2 | Delta | Other axes unchanged | PNG |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {case} | {status} | {old:.6f} | {new:.6f} | {delta:.6f} | {unchanged} | {png} {w}x{h} |".format(
                case=row["case_id"],
                status=row["status"],
                old=float(row["v1_0c_support_difficulty_score"]),
                new=float(row["support_difficulty_score"]),
                delta=float(row["delta_support_difficulty_score"]),
                unchanged=row["other_axes_unchanged"],
                png=row["png_status"],
                w=row["png_width"],
                h=row["png_height"],
            )
        )

    lines.extend(["", "## Six Axis Scores", ""])
    for row in rows:
        lines.extend(
            [
                f"### {row['case_id']}",
                "",
                "| Axis | v1.0c | v1.2 support updated | Delta |",
                "|---|---:|---:|---:|",
            ]
        )
        for axis in AXES:
            lines.append(
                f"| `{axis}` | {float(row[f'v1_0c_{axis}']):.6f} | {float(row[axis]):.6f} | {float(row[f'delta_{axis}']):.6f} |"
            )
        lines.extend(
            [
                "",
                f"- Axis CSV: `{row['axis_csv']}`",
                f"- Summary JSON: `{row['summary_json']}`",
                f"- Radar PNG: `{row['radar_png']}`",
                f"- Skip/no-overwrite status: `{row['skip_reason'] or 'not_skipped'}`",
                "",
            ]
        )

    lines.extend(
        [
            "## py_compile",
            "",
            f"- Status: `{compile_info['status']}`",
            f"- Return code: `{compile_info['returncode']}`",
            f"- Message: `{compile_info.get('message', '')}`",
            "",
            "## git status --short",
            "",
            "```text",
            git_status if git_status else "(clean)",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    BATCH_ROOT.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    failures = 0

    for case_id in ROUTES:
        src = official_paths(case_id)
        dst = batch_paths(case_id)
        commands: list[dict[str, Any]] = []
        copied: list[str] = []
        skip_reason = ""
        status = "PASS"

        if target_outputs_exist(dst) and not args.overwrite:
            skip_reason = "batch_outputs_exist_no_overwrite"
            status = "SKIP"
        else:
            official_status, commands = ensure_official_outputs(case_id, src)
            if "failed" in official_status:
                status = "FAIL"
                failures += 1
            else:
                copied = copy_outputs(src, dst, overwrite=args.overwrite)
                if not target_outputs_exist(dst):
                    status = "FAIL"
                    failures += 1
                    skip_reason = "missing_batch_target_after_copy"

        if status != "FAIL":
            rows.append(summarize_case(case_id, status, skip_reason, copied, commands))
        else:
            rows.append(
                {
                    "case_id": case_id,
                    "status": status,
                    "skip_reason": skip_reason,
                    "copied_outputs": "|".join(copied),
                    "command_status": "; ".join(
                        f"{' '.join(cmd['args'][-3:])} rc={cmd['returncode']}" for cmd in commands
                    ),
                    "axis_csv": str(dst["axis_csv"]),
                    "summary_json": str(dst["summary_json"]),
                    "radar_png": str(dst["radar_png"]),
                    "png_openable": False,
                    "png_width": "",
                    "png_height": "",
                    "png_status": "not_generated",
                }
            )

    compile_info = py_compile_result()
    if compile_info["returncode"] != 0:
        failures += 1
    git_status = git_status_short()

    summary_csv = BATCH_ROOT / "thci_v1_2_support_updated_four_route_batch_summary_v1.csv"
    report_md = BATCH_ROOT / "thci_v1_2_support_updated_four_route_batch_report_v1.md"
    if args.overwrite or not summary_csv.exists():
        write_csv(summary_csv, rows)
    if args.overwrite or not report_md.exists():
        report_md.write_text(build_report(rows, compile_info, git_status), encoding="utf-8")

    print("batch_output_dir:", BATCH_ROOT)
    print("summary_csv:", summary_csv)
    print("report_md:", report_md)
    print("py_compile:", compile_info["status"])
    for row in rows:
        print(
            f"{row['case_id']}: {row['status']} support={row.get('support_difficulty_score', '')} "
            f"delta={row.get('delta_support_difficulty_score', '')} png={row.get('png_status', '')}"
        )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
