# -*- coding: utf-8 -*-
"""Compute THCI v1.0b axis scores with navigation semantics calibration.

This version does not overwrite v1.0 or v1.0a outputs. It reads v1.0a axis
scores, keeps the five non-navigation axes unchanged, and recalculates only
navigation_risk_score using deterministic components.
"""

from __future__ import annotations

import json
import os
import sys
import argparse
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(r"C:\mountain_work\115_osm")

try:
    import pandas as pd
except ModuleNotFoundError:
    venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
        os.execv(str(venv_python), [str(venv_python), __file__, *sys.argv[1:]])
    raise


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import thci_compute_axis_scores_v1_0 as v10  # noqa: E402
import thci_compute_axis_scores_v1_0a as v10a  # noqa: E402
import thci_diagnose_feature_coverage_v1_0a as diag_v10a  # noqa: E402


V10A_ROOT = PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_0a"
DIAG_ROOT = PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_0a_diagnostics"
OUT_ROOT = PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_0b"

SCORING_VERSION = "v1.0b"
NAVIGATION_AXIS = "navigation_risk_score"
NON_NAVIGATION_AXES = [axis for axis in v10.AXES if axis != NAVIGATION_AXIS]

INPUT_ROOTS = {
    "thci_axis_scores_v1_0a": V10A_ROOT,
    "diagnostics": DIAG_ROOT,
    "ib1a": PROJECT_ROOT / "outputs" / "ib1_route_profile_v1_3b_contract_qa",
    "ib1c": PROJECT_ROOT / "outputs" / "ib1c_route_profile_semantics_v1_3b_contract_qa",
    "ib1e": PROJECT_ROOT / "outputs" / "ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa",
    "ib0d": PROJECT_ROOT
    / "outputs"
    / "ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Run only the specified case_id. Can be repeated. Defaults to the four formal cases.",
    )
    parser.add_argument(
        "--case-list",
        default=None,
        help="Optional text file containing one case_id per line. Blank lines and # comments are ignored.",
    )
    return parser.parse_args()


def resolve_cases(args: argparse.Namespace) -> tuple[list[str], bool]:
    cases = list(args.case_id or [])
    if args.case_list:
        case_list_fp = Path(args.case_list)
        if not case_list_fp.is_absolute():
            case_list_fp = PROJECT_ROOT / case_list_fp
        with case_list_fp.open("r", encoding="utf-8") as handle:
            for line in handle:
                item = line.strip()
                if item and not item.startswith("#"):
                    cases.append(item)
    if not cases:
        return list(v10.CASES), False
    deduped = list(dict.fromkeys(cases))
    return deduped, True


def ensure_v10a_prerequisites(case_id: str, config: dict[str, Any]) -> None:
    """Create per-case diagnostics and v1.0a sidecars when a CLI-added case needs them."""
    diag_fp = DIAG_ROOT / case_id / f"{case_id}_thci_feature_coverage_diagnostic_v1_0a.csv"
    if not diag_fp.exists():
        row = diag_v10a.diagnose_case(case_id)
        diag_v10a.write_case_output(case_id, row)
        merge_batch_summary(
            DIAG_ROOT / "_batch_summary" / "thci_feature_coverage_diagnostic_v1_0a_case_summary.csv",
            [pd.DataFrame([row])],
            key="case_id",
        )

    v10a_score_fp = V10A_ROOT / case_id / f"{case_id}_thci_axis_scores_v1_0a.csv"
    v10a_summary_fp = V10A_ROOT / case_id / f"{case_id}_thci_axis_score_summary_v1_0a.json"
    if not v10a_score_fp.exists() or not v10a_summary_fp.exists():
        case_scores, summary = v10a.compute_case_scores_v1_0a(case_id, config)
        v10a.write_case_outputs(case_id, case_scores, summary)
        merge_batch_summary(
            V10A_ROOT / "_batch_summary" / "thci_axis_scores_v1_0a_case_summary.csv",
            [case_scores],
            key="case_id",
        )


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _load_csv_first_row(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path, low_memory=False)
    if df.empty:
        raise ValueError(f"CSV is empty: {path}")
    return df.iloc[0].to_dict()


def _load_v10a_scores(case_id: str) -> tuple[dict[str, Any], Path]:
    fp = V10A_ROOT / case_id / f"{case_id}_thci_axis_scores_v1_0a.csv"
    return _load_csv_first_row(fp), fp


def _load_v10a_summary(case_id: str) -> tuple[dict[str, Any], Path]:
    fp = V10A_ROOT / case_id / f"{case_id}_thci_axis_score_summary_v1_0a.json"
    if not fp.exists():
        raise FileNotFoundError(fp)
    with fp.open("r", encoding="utf-8") as handle:
        return json.load(handle), fp


def _load_diagnostic(case_id: str) -> tuple[dict[str, Any], Path]:
    fp = DIAG_ROOT / case_id / f"{case_id}_thci_feature_coverage_diagnostic_v1_0a.csv"
    return _load_csv_first_row(fp), fp


def _find_case_csv(root_name: str, case_id: str, suffix: str) -> Path:
    case_dir = INPUT_ROOTS[root_name] / case_id
    candidates = sorted(case_dir.glob(f"*{suffix}"))
    if not candidates:
        raise FileNotFoundError(f"No {suffix} under {case_dir}")
    return candidates[0]


def _load_case_frames(case_id: str) -> dict[str, pd.DataFrame]:
    ib1a = _find_case_csv("ib1a", case_id, "_route_profile.csv")
    ib1c = _find_case_csv("ib1c", case_id, "_route_profile_semantic_enriched.csv")
    ib1e = _find_case_csv("ib1e", case_id, "_route_profile_contour_window_terrain_enriched.csv")
    return {
        "ib1a": pd.read_csv(ib1a, low_memory=False),
        "ib1c": pd.read_csv(ib1c, low_memory=False),
        "ib1e": pd.read_csv(ib1e, low_memory=False),
    }


def _weighted_ratio(df: pd.DataFrame, mask: pd.Series) -> float:
    if df.empty:
        return 0.0
    if "delta_dist_m" in df.columns:
        weights = pd.to_numeric(df["delta_dist_m"], errors="coerce").fillna(0.0).clip(lower=0.0)
        total = float(weights.sum())
        if total > 0:
            return v10.clip01(float(weights[mask.fillna(False)].sum()) / total) or 0.0
    return v10.clip01(float(mask.fillna(False).mean())) or 0.0


def _poor_visibility_score(frames: dict[str, pd.DataFrame]) -> tuple[float, list[str], list[dict[str, Any]], list[str]]:
    direct_features: list[str] = []
    proxy_features: list[dict[str, Any]] = []
    missing_features: list[str] = []

    source_df = None
    source_name = ""
    for name in ("ib1c", "ib1e"):
        df = frames.get(name, pd.DataFrame())
        if "osm_trail_visibility" in df.columns:
            source_df = df
            source_name = name
            direct_features.append(f"{name}.osm_trail_visibility")
            break

    if source_df is None:
        missing_features.append("trail_visibility")
        return 0.0, direct_features, proxy_features, missing_features

    visibility = source_df["osm_trail_visibility"].astype(str).str.strip().str.lower()
    excellent_good = visibility.isin(["excellent", "good"])
    intermediate = visibility.eq("intermediate")
    bad = visibility.eq("bad")
    horrible_no = visibility.isin(["horrible", "no"])
    unknown = visibility.isin(["", "<na>", "nan", "none", "unknown"])

    intermediate_ratio = _weighted_ratio(source_df, intermediate)
    bad_ratio = _weighted_ratio(source_df, bad)
    horrible_no_ratio = _weighted_ratio(source_df, horrible_no)
    unknown_ratio = _weighted_ratio(source_df, unknown)
    clear_ratio = _weighted_ratio(source_df, excellent_good)

    score = v10.clip01(
        0.30 * intermediate_ratio
        + 0.60 * bad_ratio
        + 0.85 * horrible_no_ratio
        + 0.15 * unknown_ratio
    ) or 0.0
    proxy_features.append(
        {
            "feature_name": "poor_visibility_score",
            "source": source_name,
            "proxy_method": "length-weighted trail_visibility severity: intermediate=0.30, bad=0.60, horrible/no=0.85, unknown=0.15",
            "excellent_or_good_ratio": clear_ratio,
            "intermediate_ratio": intermediate_ratio,
            "bad_ratio": bad_ratio,
            "horrible_or_no_ratio": horrible_no_ratio,
            "unknown_ratio": unknown_ratio,
            "proxy_score": score,
        }
    )
    return score, direct_features, proxy_features, missing_features


def _route_confusion_score(diag: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    same_entry = _bool(diag.get("same_entry_keep_full"))
    self_near_exists = _bool(diag.get("self_near_zones_exists"))
    summit_self_near = _bool(diag.get("summit_self_near_zone_exists"))
    route_gap = _num(diag.get("route_gap_max_m"), default=0.0)
    self_near_pairs = _num(diag.get("self_near_pair_count"), default=0.0)
    unexpected_pairs = _num(diag.get("unexpected_self_near_pair_count"), default=0.0)

    route_gap_score = v10.clip01(route_gap / 5000.0) or 0.0
    self_near_density_score = v10.clip01(self_near_pairs / 60000.0) or 0.0
    unexpected_score = v10.clip01(unexpected_pairs / 1000.0) or 0.0
    score = v10.clip01(
        0.20 * (1.0 if same_entry else 0.0)
        + 0.20 * (1.0 if self_near_exists else 0.0)
        + 0.15 * (1.0 if summit_self_near else 0.0)
        + 0.25 * route_gap_score
        + 0.10 * self_near_density_score
        + 0.10 * unexpected_score
    ) or 0.0

    proxy = {
        "feature_name": "route_confusion_score",
        "proxy_method": "same_entry/self_near/route_gap/self_near_pair_count ambiguity proxy; not treated as standalone high navigation risk",
        "same_entry_keep_full": same_entry,
        "self_near_zones_exists": self_near_exists,
        "summit_self_near_zone_exists": summit_self_near,
        "route_gap_max_m": route_gap,
        "route_gap_score_norm_5km": route_gap_score,
        "self_near_pair_count": self_near_pairs,
        "self_near_density_score_norm_60000": self_near_density_score,
        "unexpected_self_near_pair_count": unexpected_pairs,
        "unexpected_self_near_score_norm_1000": unexpected_score,
        "proxy_score": score,
    }
    return score, [proxy]


def _return_difficulty_score(diag: dict[str, Any]) -> tuple[float, list[dict[str, Any]], bool]:
    same_entry = _bool(diag.get("same_entry_keep_full"))
    self_near_exists = _bool(diag.get("self_near_zones_exists"))
    summit_self_near = _bool(diag.get("summit_self_near_zone_exists"))
    route_gap = _num(diag.get("route_gap_max_m"), default=0.0)

    has_return_evidence = same_entry or summit_self_near or route_gap > 0
    route_gap_score = v10.clip01(route_gap / 5000.0) or 0.0
    score = v10.clip01(
        0.35 * route_gap_score
        + 0.25 * (1.0 if same_entry else 0.0)
        + 0.25 * (1.0 if summit_self_near else 0.0)
        + 0.15 * (1.0 if self_near_exists and has_return_evidence else 0.0)
    ) or 0.0

    proxy = {
        "feature_name": "return_difficulty_score",
        "proxy_method": "route_gap/same_entry/summit_self_near return difficulty proxy; self_near alone is not treated as reliable return difficulty evidence",
        "same_entry_keep_full": same_entry,
        "self_near_zones_exists": self_near_exists,
        "summit_self_near_zone_exists": summit_self_near,
        "route_gap_max_m": route_gap,
        "route_gap_score_norm_5km": route_gap_score,
        "has_return_difficulty_evidence": has_return_evidence,
        "proxy_score": score,
    }
    return score, [proxy], has_return_evidence


def _safe_exit_connectivity_score() -> tuple[float, list[str], str]:
    return (
        0.0,
        ["safe_exit_connectivity"],
        "No formal safe-exit connectivity extractor is available in v1.0b; score is held at 0 and recorded as missing.",
    )


def compute_navigation_score_v1_0b(
    case_id: str,
    frames: dict[str, pd.DataFrame],
    diag: dict[str, Any],
    previous_v10a_score: float,
) -> tuple[float, dict[str, Any]]:
    route_confusion, route_confusion_proxies = _route_confusion_score(diag)
    poor_visibility, direct_features, poor_visibility_proxies, missing_features = _poor_visibility_score(frames)
    return_difficulty, return_proxies, has_return_evidence = _return_difficulty_score(diag)
    safe_exit, safe_exit_missing, safe_exit_note = _safe_exit_connectivity_score()
    missing_features.extend(safe_exit_missing)

    score_before_cap = v10.clip01(
        0.30 * route_confusion
        + 0.35 * poor_visibility
        + 0.35 * return_difficulty
        - 0.25 * safe_exit
    ) or 0.0

    route_complexity_evidence = route_confusion > 0.0
    has_poor_visibility_evidence = poor_visibility > 0.0
    navigation_cap_applied = (
        route_complexity_evidence
        and not has_poor_visibility_evidence
        and not has_return_evidence
        and score_before_cap > 0.35
    )
    final_score = min(score_before_cap, 0.35) if navigation_cap_applied else score_before_cap
    final_score = v10.clip01(final_score) or 0.0

    proxy_features = route_confusion_proxies + poor_visibility_proxies + return_proxies
    note = (
        "v1.0b recalculates navigation from semantics components. Junction or route complexity "
        "does not directly equal high navigation risk; safe-exit connectivity is missing and "
        "therefore not credited yet. "
        + safe_exit_note
    )

    detail = {
        "previous_v1_0a_navigation_risk_score": previous_v10a_score,
        "route_confusion_score": route_confusion,
        "poor_visibility_score": poor_visibility,
        "return_difficulty_score": return_difficulty,
        "safe_exit_connectivity_score": safe_exit,
        "navigation_cap_applied": navigation_cap_applied,
        "score_before_cap": score_before_cap,
        "final_score": final_score,
        "direct_features": direct_features,
        "proxy_features": proxy_features,
        "missing_features": sorted(set(missing_features)),
        "note": note,
    }
    return final_score, detail


def _count_nested_features(features_by_axis: dict[str, list[Any]]) -> int:
    return sum(len(values or []) for values in features_by_axis.values())


def compute_case_scores(case_id: str, config: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    v10a_row, v10a_score_csv = _load_v10a_scores(case_id)
    v10a_summary, v10a_summary_json = _load_v10a_summary(case_id)
    diag, diagnostic_csv = _load_diagnostic(case_id)
    frames = _load_case_frames(case_id)

    previous_nav = _num(v10a_row.get(NAVIGATION_AXIS))
    nav_score, nav_detail = compute_navigation_score_v1_0b(case_id, frames, diag, previous_nav)

    scores = {
        axis: v10.clip01(_num(v10a_row.get(axis))) or 0.0
        for axis in NON_NAVIGATION_AXES
    }
    scores[NAVIGATION_AXIS] = nav_score

    previous_axis_details = v10a_summary.get("axis_details", {})
    details = {
        axis: previous_axis_details.get(axis, {"carried_forward_from_v1_0a": True})
        for axis in NON_NAVIGATION_AXES
    }
    details[NAVIGATION_AXIS] = nav_detail

    previous_direct = v10a_summary.get("direct_features", {})
    previous_proxy = v10a_summary.get("proxy_features", {})
    previous_missing = v10a_summary.get("missing_features", {})

    direct_features = {
        axis: previous_direct.get(axis, details[axis].get("direct_features", []))
        for axis in NON_NAVIGATION_AXES
    }
    proxy_features = {
        axis: previous_proxy.get(axis, details[axis].get("proxy_features", []))
        for axis in NON_NAVIGATION_AXES
    }
    missing_features = {
        axis: previous_missing.get(axis, details[axis].get("missing_features", []))
        for axis in NON_NAVIGATION_AXES
    }

    direct_features[NAVIGATION_AXIS] = nav_detail["direct_features"]
    proxy_features[NAVIGATION_AXIS] = nav_detail["proxy_features"]
    missing_features[NAVIGATION_AXIS] = nav_detail["missing_features"]

    proxy_features_n = _count_nested_features(proxy_features)
    missing_features_n = _count_nested_features(missing_features)
    ordered_scores = {axis: scores.get(axis, 0.0) for axis in v10.AXES}

    row = {
        "case_id": case_id,
        "scoring_version": SCORING_VERSION,
        **ordered_scores,
        "calibrated_from_v1_0a": True,
        "navigation_semantics_calibrated": True,
        "route_confusion_score": nav_detail["route_confusion_score"],
        "poor_visibility_score": nav_detail["poor_visibility_score"],
        "return_difficulty_score": nav_detail["return_difficulty_score"],
        "safe_exit_connectivity_score": nav_detail["safe_exit_connectivity_score"],
        "navigation_cap_applied": nav_detail["navigation_cap_applied"],
        "navigation_calibration_note": nav_detail["note"],
        "proxy_features_n": proxy_features_n,
        "missing_features_n": missing_features_n,
    }
    out_df = pd.DataFrame([row])

    summary = {
        "case_id": case_id,
        "thci_version": SCORING_VERSION,
        "scoring_version": SCORING_VERSION,
        "scoring_mode": "deterministic_config_only_no_runtime_llm",
        "calibrated_from_v1_0a": True,
        "navigation_semantics_calibrated": True,
        "config_paths": config["config_paths"],
        "input_roots": {name: str(path) for name, path in INPUT_ROOTS.items()},
        "input_files": {
            "v1_0a_axis_score_csv": str(v10a_score_csv),
            "v1_0a_axis_score_summary_json": str(v10a_summary_json),
            "diagnostic_csv": str(diagnostic_csv),
        },
        "output_root": str(OUT_ROOT),
        "axis_scores": ordered_scores,
        "direct_features": direct_features,
        "proxy_features": proxy_features,
        "missing_features": missing_features,
        "proxy_features_n": proxy_features_n,
        "missing_features_n": missing_features_n,
        "axis_details": details,
        "runtime_llm_allowed": False,
    }
    return out_df, summary


def write_case_outputs(case_id: str, case_scores: pd.DataFrame, summary: dict[str, Any]) -> None:
    out_dir = OUT_ROOT / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    case_scores.to_csv(out_dir / f"{case_id}_thci_axis_scores_v1_0b.csv", index=False, encoding="utf-8-sig")
    (out_dir / f"{case_id}_thci_axis_score_summary_v1_0b.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def merge_batch_summary(out_fp: Path, case_rows: list[pd.DataFrame], key: str = "case_id") -> None:
    out_fp.parent.mkdir(parents=True, exist_ok=True)
    new_df = pd.concat(case_rows, ignore_index=True) if case_rows else pd.DataFrame()
    if out_fp.exists():
        old_df = pd.read_csv(out_fp, low_memory=False)
        if key in old_df.columns and key in new_df.columns:
            old_df = old_df[~old_df[key].astype(str).isin(set(new_df[key].astype(str)))]
            new_df = pd.concat([old_df, new_df], ignore_index=True)
    new_df.to_csv(out_fp, index=False, encoding="utf-8-sig")


def write_batch_summary(case_rows: list[pd.DataFrame], merge_existing: bool = False) -> None:
    batch_dir = OUT_ROOT / "_batch_summary"
    batch_dir.mkdir(parents=True, exist_ok=True)
    out_fp = batch_dir / "thci_axis_scores_v1_0b_case_summary.csv"
    if merge_existing:
        merge_batch_summary(out_fp, case_rows)
    else:
        pd.concat(case_rows, ignore_index=True).to_csv(
            out_fp,
            index=False,
            encoding="utf-8-sig",
        )


def main() -> int:
    args = parse_args()
    cases, is_cli_extension = resolve_cases(args)
    config = v10.load_config_bundle()
    case_rows: list[pd.DataFrame] = []
    for case_id in cases:
        if is_cli_extension:
            ensure_v10a_prerequisites(case_id, config)
        case_scores, summary = compute_case_scores(case_id, config)
        write_case_outputs(case_id, case_scores, summary)
        case_rows.append(case_scores)
        print(case_scores.to_string(index=False))
    write_batch_summary(case_rows, merge_existing=is_cli_extension)
    print("batch summary:", OUT_ROOT / "_batch_summary" / "thci_axis_scores_v1_0b_case_summary.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
