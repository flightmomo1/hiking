# -*- coding: utf-8 -*-
"""Batch rebuild THCI v1.3 terrain evidence for four existing routes.

This wrapper only rebuilds the terrain evidence chain:

1. ib1g2 upslope collapse hazard proxy
2. ib1g3 upslope contributing area hazard proxy
3. ib1g3 distant collapse mask review
4. ib2d upslope contributing hazard map / hotspots

It deliberately does not run weather-terrain fusion, v1.3 adapter, or
candidate scoring. It also does not modify scoring scripts or risk-semantics
configs.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = PROJECT_ROOT / "outputs" / "thci_four_route_terrain_evidence_rebuild_v1"

ROUTES = [
    "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b",
    "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b",
    "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b",
    "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b",
]

SCRIPT_IB1G2 = PROJECT_ROOT / "scripts" / "ib1_nlsc_terrain" / "ib1g2_compute_upslope_collapse_hazard_proxy.py"
SCRIPT_IB1G3 = PROJECT_ROOT / "scripts" / "ib1_nlsc_terrain" / "ib1g3_compute_upslope_contributing_area_hazard_proxy.py"
SCRIPT_DISTANT = PROJECT_ROOT / "scripts" / "ib1g3_plot_distant_collapse_mask_review.py"
SCRIPT_IB2D = PROJECT_ROOT / "scripts" / "ib2_route_risk" / "ib2d_plot_upslope_contributing_hazard_map.py"
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
RUNNER_PYTHON = VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable)


@dataclass
class RouteManifest:
    case_id: str
    case_name: str = ""
    status: str = "PENDING"
    status_reason: str = ""
    route_line_geojson: Path | None = None
    route_line_source_kind: str = ""
    route_profile_csv: Path | None = None
    contour_features_dir: Path | None = None
    contour_features_csv: Path | None = None
    nlsc_tile: str = ""
    contour_source: Path | None = None
    watercourse_source: Path | None = None
    collapse_mask_source: Path | None = None
    ib1g2_out_dir: Path = field(default_factory=Path)
    ib1g3_out_dir: Path = field(default_factory=Path)
    distant_out_dir: Path = field(default_factory=Path)
    ib2d_out_dir: Path = field(default_factory=Path)


@dataclass
class StepResult:
    case_id: str
    step: str
    status: str
    reason: str
    command: str = ""
    returncode: int | None = None
    outputs: list[Path] = field(default_factory=list)
    stdout_tail: str = ""
    stderr_tail: str = ""


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path)


def tail(text: str, limit: int = 3000) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[-limit:]


def read_csv_first_row(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            return {str(k): str(v) for k, v in row.items()}
    raise ValueError(f"CSV has no rows: {path}")


def resolve_path_from_csv(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def first_existing(paths: list[tuple[str, Path]]) -> tuple[str, Path] | tuple[str, None]:
    for kind, path in paths:
        if path.exists():
            return kind, path
    return "", None


def expected_outputs(case_id: str, step: str) -> list[Path]:
    if step == "ib1g2":
        out_dir = PROJECT_ROOT / "outputs" / "ib1g2_upslope_collapse_hazard_proxy" / case_id
        return [
            out_dir / f"{case_id}_upslope_collapse_hazard_proxy.csv",
            out_dir / f"{case_id}_upslope_collapse_hazard_proxy.geojson",
            out_dir / f"{case_id}_upslope_collapse_hazard_proxy_summary.csv",
        ]
    if step == "ib1g3":
        out_dir = PROJECT_ROOT / "outputs" / "ib1g3_upslope_contributing_area_hazard_proxy" / case_id
        return [
            out_dir / f"{case_id}_upslope_contributing_area_hazard_proxy.csv",
            out_dir / f"{case_id}_upslope_contributing_area_hazard_proxy.geojson",
            out_dir / f"{case_id}_upslope_contributing_area_top_sources.csv",
            out_dir / f"{case_id}_upslope_contributing_area_hazard_proxy_summary.csv",
        ]
    if step == "distant_review":
        out_dir = PROJECT_ROOT / "outputs" / "ib1g3_distant_collapse_mask_review" / case_id
        return [
            out_dir / f"{case_id}_distant_collapse_mask_review.csv",
            out_dir / f"{case_id}_distant_collapse_mask_review_summary.csv",
            out_dir / f"{case_id}_distant_collapse_mask_review.md",
            out_dir / f"{case_id}_distant_collapse_mask_review_map.png",
        ]
    if step == "ib2d_hotspot":
        out_dir = PROJECT_ROOT / "outputs" / "ib2d_upslope_contributing_hazard_map" / case_id
        return [
            out_dir / f"{case_id}_upslope_contributing_hazard_hotspots.csv",
            out_dir / f"{case_id}_upslope_contributing_hazard_hotspots.md",
            out_dir / f"{case_id}_upslope_contributing_hazard_map.png",
            out_dir / f"{case_id}_upslope_contributing_hazard_radar.png",
            out_dir / f"{case_id}_upslope_contributing_hazard_map_with_radar.png",
            out_dir / f"{case_id}_upslope_contributing_hazard_map_summary.csv",
        ]
    raise ValueError(f"Unknown step: {step}")


def any_existing(paths: list[Path]) -> list[Path]:
    return [path for path in paths if path.exists()]


def output_status(paths: list[Path]) -> str:
    existing = any_existing(paths)
    if not existing:
        return "none_existing"
    if len(existing) == len(paths):
        return "all_existing"
    return "partial_existing"


def build_manifest(case_id: str) -> RouteManifest:
    manifest = RouteManifest(case_id=case_id)
    manifest.ib1g2_out_dir = PROJECT_ROOT / "outputs" / "ib1g2_upslope_collapse_hazard_proxy" / case_id
    manifest.ib1g3_out_dir = PROJECT_ROOT / "outputs" / "ib1g3_upslope_contributing_area_hazard_proxy" / case_id
    manifest.distant_out_dir = PROJECT_ROOT / "outputs" / "ib1g3_distant_collapse_mask_review" / case_id
    manifest.ib2d_out_dir = PROJECT_ROOT / "outputs" / "ib2d_upslope_contributing_hazard_map" / case_id

    route_dir = (
        PROJECT_ROOT
        / "outputs"
        / "ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa"
        / case_id
    )
    preferred_route_line = route_dir / f"{case_id}_trimmed_mainline.geojson"
    route_line_kind, route_line = first_existing(
        [
            ("requested_case_trimmed_mainline", preferred_route_line),
            ("canonical_mainline_ordered_path_trimmed", route_dir / "mainline_ordered_path_trimmed.geojson"),
            (
                "case_prefixed_mainline_ordered_path_trimmed",
                route_dir / f"{case_id}_mainline_ordered_path_trimmed.geojson",
            ),
        ]
    )
    manifest.route_line_source_kind = route_line_kind
    manifest.route_line_geojson = route_line

    profile_csv = (
        PROJECT_ROOT
        / "outputs"
        / "ib1_route_profile_v1_3b_contract_qa"
        / case_id
        / f"{case_id}_route_profile.csv"
    )
    manifest.route_profile_csv = profile_csv
    if profile_csv.exists():
        try:
            profile_row = read_csv_first_row(profile_csv)
            manifest.case_name = profile_row.get("case_name", "")
        except Exception:
            manifest.case_name = ""

    contour_dir = PROJECT_ROOT / "outputs" / "ib1g_contour_window_features_v1_3b_contract_qa" / case_id
    contour_csv = contour_dir / f"{case_id}_contour_window_features.csv"
    manifest.contour_features_dir = contour_dir
    manifest.contour_features_csv = contour_csv
    if contour_csv.exists():
        row = read_csv_first_row(contour_csv)
        manifest.nlsc_tile = row.get("nlsc_tile", "").strip()
        contour_fp = row.get("contour_fp", "").strip()
        if contour_fp:
            manifest.contour_source = resolve_path_from_csv(contour_fp)

    if manifest.nlsc_tile:
        tile_root = PROJECT_ROOT / "nlsc_raw" / manifest.nlsc_tile
        if manifest.contour_source is None or not manifest.contour_source.exists():
            manifest.contour_source = tile_root / "向量25K" / "ContourL.shp"
        manifest.watercourse_source = tile_root / "向量25K" / "WatrcrsL.shp"
        manifest.collapse_mask_source = tile_root / "遮罩25K" / "崩土遮罩.shp"

    required = [
        ("route_line_geojson", manifest.route_line_geojson),
        ("route_profile_csv", manifest.route_profile_csv),
        ("contour_features_csv", manifest.contour_features_csv),
        ("contour_source", manifest.contour_source),
        ("watercourse_source", manifest.watercourse_source),
        ("collapse_mask_source", manifest.collapse_mask_source),
    ]
    missing = [name for name, path in required if path is None or not path.exists()]
    if missing:
        manifest.status = "BLOCKED"
        manifest.status_reason = "missing required source(s): " + ", ".join(missing)
    else:
        manifest.status = "READY"
        manifest.status_reason = "all required terrain inputs found"
    return manifest


def run_command(case_id: str, step: str, cmd: list[str], outputs: list[Path], dry_run: bool) -> StepResult:
    existing = any_existing(outputs)
    if existing:
        return StepResult(
            case_id=case_id,
            step=step,
            status="SKIP_EXISTING_OUTPUT",
            reason="no-overwrite guard: existing output(s): " + "; ".join(rel(path) for path in existing),
            command=" ".join(cmd),
            outputs=outputs,
        )
    if dry_run:
        return StepResult(
            case_id=case_id,
            step=step,
            status="DRY_RUN_READY",
            reason="dry-run: command not executed",
            command=" ".join(cmd),
            outputs=outputs,
        )

    completed = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    missing_after = [path for path in outputs if not path.exists()]
    if completed.returncode == 0 and not missing_after:
        status = "SUCCESS"
        reason = "all expected outputs produced"
    elif completed.returncode == 0:
        status = "PARTIAL_SUCCESS"
        reason = "command returned 0 but expected output(s) missing: " + "; ".join(rel(path) for path in missing_after)
    else:
        status = "FAILED"
        reason = f"command failed with return code {completed.returncode}"
    return StepResult(
        case_id=case_id,
        step=step,
        status=status,
        reason=reason,
        command=" ".join(cmd),
        returncode=completed.returncode,
        outputs=outputs,
        stdout_tail=tail(completed.stdout),
        stderr_tail=tail(completed.stderr),
    )


def build_commands(manifest: RouteManifest) -> list[tuple[str, list[str], list[Path]]]:
    case_id = manifest.case_id
    case_name = manifest.case_name or case_id
    assert manifest.route_line_geojson is not None
    assert manifest.route_profile_csv is not None
    assert manifest.contour_source is not None
    assert manifest.watercourse_source is not None
    assert manifest.collapse_mask_source is not None

    base_inputs = [
        "--case-id",
        case_id,
        "--case-name",
        case_name,
        "--route-line-fp",
        str(manifest.route_line_geojson),
        "--profile-csv",
        str(manifest.route_profile_csv),
        "--contour-fp",
        str(manifest.contour_source),
        "--collapse-mask-fp",
        str(manifest.collapse_mask_source),
        "--watercourse-fp",
        str(manifest.watercourse_source),
        "--tile",
        manifest.nlsc_tile,
    ]
    ib1g2_cmd = [
        str(RUNNER_PYTHON),
        str(SCRIPT_IB1G2),
        *base_inputs,
        "--out-dir",
        str(manifest.ib1g2_out_dir),
    ]
    ib1g3_cmd = [
        str(RUNNER_PYTHON),
        str(SCRIPT_IB1G3),
        *base_inputs,
        "--out-dir",
        str(manifest.ib1g3_out_dir),
    ]
    distant_cmd = [
        str(RUNNER_PYTHON),
        str(SCRIPT_DISTANT),
        "--case-id",
        case_id,
        "--case-name",
        case_name,
        "--collapse-mask-fp",
        str(manifest.collapse_mask_source),
        "--contour-fp",
        str(manifest.contour_source),
        "--watercourse-fp",
        str(manifest.watercourse_source),
        "--out-dir",
        str(manifest.distant_out_dir),
    ]
    ib2d_cmd = [
        str(RUNNER_PYTHON),
        str(SCRIPT_IB2D),
        "--case-id",
        case_id,
        "--case-name",
        case_name,
        "--contour-fp",
        str(manifest.contour_source),
        "--collapse-mask-fp",
        str(manifest.collapse_mask_source),
        "--watercourse-fp",
        str(manifest.watercourse_source),
        "--out-dir",
        str(manifest.ib2d_out_dir),
    ]
    return [
        ("ib1g2", ib1g2_cmd, expected_outputs(case_id, "ib1g2")),
        ("ib1g3", ib1g3_cmd, expected_outputs(case_id, "ib1g3")),
        ("distant_review", distant_cmd, expected_outputs(case_id, "distant_review")),
        ("ib2d_hotspot", ib2d_cmd, expected_outputs(case_id, "ib2d_hotspot")),
    ]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_ib2d_summary(case_id: str) -> dict[str, str]:
    path = (
        PROJECT_ROOT
        / "outputs"
        / "ib2d_upslope_contributing_hazard_map"
        / case_id
        / f"{case_id}_upslope_contributing_hazard_map_summary.csv"
    )
    if not path.exists():
        return {}
    return read_csv_first_row(path)


def git_status_short() -> str:
    completed = subprocess.run(
        ["git", "status", "--short"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return completed.stderr.strip()
    return completed.stdout.strip()


def write_report(
    path: Path,
    manifests: list[RouteManifest],
    results: list[StepResult],
    py_compile_result: subprocess.CompletedProcess[str] | None,
    git_status: str,
    dry_run: bool,
) -> None:
    result_by_case_step = {(r.case_id, r.step): r for r in results}
    lines: list[str] = [
        "# THCI Four Route Terrain Evidence Rebuild v1",
        "",
        f"Generated at: `{now_utc()}`",
        f"Dry run: `{dry_run}`",
        "",
        "## Scope",
        "",
        "This wrapper rebuilds terrain evidence only. Weather-terrain fusion remains `pending_evidence`.",
        "",
        "Not executed:",
        "- v1.3 weather-terrain fusion",
        "- v1.3 adapter",
        "- v1.3 candidate simulation",
        "- scoring script edits",
        "- risk_semantics config edits",
        "- manual score filling",
        "",
        "## Route Inputs",
        "",
        "| route | manifest status | route line | route line source | profile CSV | NLSC tile | contour source | watercourse source | collapse mask source |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for m in manifests:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{m.case_id}`",
                    f"`{m.status}`",
                    f"`{rel(m.route_line_geojson)}`",
                    f"`{m.route_line_source_kind}`",
                    f"`{rel(m.route_profile_csv)}`",
                    f"`{m.nlsc_tile}`",
                    f"`{rel(m.contour_source)}`",
                    f"`{rel(m.watercourse_source)}`",
                    f"`{rel(m.collapse_mask_source)}`",
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Step Results",
            "",
            "| route | ib1g2 | ib1g3 | distant review | ib2d hotspot | weather fusion |",
            "|---|---|---|---|---|---|",
        ]
    )
    for m in manifests:
        row = [f"`{m.case_id}`"]
        for step in ["ib1g2", "ib1g3", "distant_review", "ib2d_hotspot"]:
            result = result_by_case_step.get((m.case_id, step))
            row.append(f"`{result.status if result else 'NOT_RUN'}`")
        row.append("`pending_evidence`")
        lines.append("| " + " | ".join(row) + " |")

    lines.extend(["", "## Generated Terrain Outputs", ""])
    for m in manifests:
        lines.append(f"### `{m.case_id}`")
        for step in ["ib1g2", "ib1g3", "distant_review", "ib2d_hotspot"]:
            result = result_by_case_step.get((m.case_id, step))
            if not result:
                lines.append(f"- `{step}`: `NOT_RUN`")
                continue
            lines.append(f"- `{step}`: `{result.status}` - {result.reason}")
            for output in result.outputs:
                marker = "exists" if output.exists() else "missing"
                lines.append(f"  - `{rel(output)}`: `{marker}`")
        lines.append("- weather fusion: `pending_evidence`")
        summary = read_ib2d_summary(m.case_id)
        if summary:
            lines.append(
                "- ib2d hotspot summary: "
                f"rows=`{summary.get('rows', '')}`, "
                f"score_mean=`{summary.get('score_mean', '')}`, "
                f"score_max=`{summary.get('score_max', '')}`, "
                f"hotspot_threshold=`{summary.get('hotspot_threshold', '')}`, "
                f"hotspot_count=`{summary.get('hotspot_count', '')}`"
            )
        lines.append("")

    lines.extend(["## No-Overwrite Policy", ""])
    lines.append(
        "Before each stage, the wrapper checks the fixed expected output filenames. "
        "If any expected output already exists, that stage is skipped with `SKIP_EXISTING_OUTPUT`."
    )
    lines.append("")

    lines.extend(["## py_compile", ""])
    if py_compile_result is None:
        lines.append("`py_compile` was not run before this report write.")
    else:
        lines.append(f"returncode: `{py_compile_result.returncode}`")
        if py_compile_result.stdout.strip():
            lines.append("")
            lines.append("stdout:")
            lines.append("```")
            lines.append(py_compile_result.stdout.strip())
            lines.append("```")
        if py_compile_result.stderr.strip():
            lines.append("")
            lines.append("stderr:")
            lines.append("```")
            lines.append(py_compile_result.stderr.strip())
            lines.append("```")

    lines.extend(["", "## git status --short", "", "```"])
    lines.append(git_status)
    lines.append("```")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Build manifest and commands without running evidence scripts.")
    args = parser.parse_args()

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    manifests = [build_manifest(case_id) for case_id in ROUTES]
    results: list[StepResult] = []

    for manifest in manifests:
        if manifest.status != "READY":
            for step in ["ib1g2", "ib1g3", "distant_review", "ib2d_hotspot"]:
                results.append(
                    StepResult(
                        case_id=manifest.case_id,
                        step=step,
                        status="SKIP_PREFLIGHT_BLOCKED",
                        reason=manifest.status_reason,
                        outputs=expected_outputs(manifest.case_id, step),
                    )
                )
            continue

        for step, cmd, outputs in build_commands(manifest):
            if step == "distant_review":
                needed = expected_outputs(manifest.case_id, "ib1g3")
                missing = [path for path in needed[:2] if not path.exists()]
                if missing:
                    results.append(
                        StepResult(
                            case_id=manifest.case_id,
                            step=step,
                            status="SKIP_MISSING_UPSTREAM",
                            reason="missing ib1g3 upstream output(s): " + "; ".join(rel(path) for path in missing),
                            command=" ".join(cmd),
                            outputs=outputs,
                        )
                    )
                    continue
            if step == "ib2d_hotspot":
                needed = expected_outputs(manifest.case_id, "ib1g3")
                missing = [path for path in needed[:2] if not path.exists()]
                if missing:
                    results.append(
                        StepResult(
                            case_id=manifest.case_id,
                            step=step,
                            status="SKIP_MISSING_UPSTREAM",
                            reason="missing ib1g3 upstream output(s): " + "; ".join(rel(path) for path in missing),
                            command=" ".join(cmd),
                            outputs=outputs,
                        )
                    )
                    continue
            results.append(run_command(manifest.case_id, step, cmd, outputs, args.dry_run))

    manifest_rows = [
        {
            "case_id": m.case_id,
            "case_name": m.case_name,
            "manifest_status": m.status,
            "status_reason": m.status_reason,
            "route_line_geojson": rel(m.route_line_geojson),
            "route_line_source_kind": m.route_line_source_kind,
            "route_profile_csv": rel(m.route_profile_csv),
            "contour_features_dir": rel(m.contour_features_dir),
            "contour_features_csv": rel(m.contour_features_csv),
            "nlsc_tile": m.nlsc_tile,
            "contour_source": rel(m.contour_source),
            "watercourse_source": rel(m.watercourse_source),
            "collapse_mask_source": rel(m.collapse_mask_source),
            "ib1g2_out_dir": rel(m.ib1g2_out_dir),
            "ib1g3_out_dir": rel(m.ib1g3_out_dir),
            "distant_out_dir": rel(m.distant_out_dir),
            "ib2d_out_dir": rel(m.ib2d_out_dir),
        }
        for m in manifests
    ]
    summary_rows: list[dict[str, Any]] = []
    for result in results:
        summary_rows.append(
            {
                "case_id": result.case_id,
                "step": result.step,
                "status": result.status,
                "reason": result.reason,
                "returncode": "" if result.returncode is None else result.returncode,
                "expected_output_status": output_status(result.outputs),
                "outputs": ";".join(rel(path) for path in result.outputs),
                "command": result.command,
                "stdout_tail": result.stdout_tail,
                "stderr_tail": result.stderr_tail,
            }
        )

    write_csv(OUT_ROOT / "thci_four_route_terrain_evidence_rebuild_manifest_v1.csv", manifest_rows)
    write_csv(OUT_ROOT / "thci_four_route_terrain_evidence_rebuild_summary_v1.csv", summary_rows)

    py_compile_result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(Path(__file__).resolve())],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    git_status = git_status_short()
    write_report(
        OUT_ROOT / "thci_four_route_terrain_evidence_rebuild_report_v1.md",
        manifests,
        results,
        py_compile_result,
        git_status,
        args.dry_run,
    )

    print(
        json.dumps(
            {
                "manifest_csv": str(OUT_ROOT / "thci_four_route_terrain_evidence_rebuild_manifest_v1.csv"),
                "summary_csv": str(OUT_ROOT / "thci_four_route_terrain_evidence_rebuild_summary_v1.csv"),
                "report_md": str(OUT_ROOT / "thci_four_route_terrain_evidence_rebuild_report_v1.md"),
                "py_compile_returncode": py_compile_result.returncode,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if py_compile_result.returncode == 0 else py_compile_result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
