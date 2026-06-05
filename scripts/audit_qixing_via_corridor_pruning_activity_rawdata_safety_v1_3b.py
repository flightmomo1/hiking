from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


ROUTE_FOLDER = "qixing_lengshuikeng"
ACTIVITY_IDS = ["37_1", "33_1", "15_1"]
CORRIDOR_START_M = 305.0
CORRIDOR_END_M = 3721.0
REVERSAL_DELTA_THRESHOLD_M = 1.0

STANDARDIZED_ROOT = Path("outputs/activity_standardized")
MANIFEST_CSV = STANDARDIZED_ROOT / "activity_standardized_manifest.csv"

BEFORE_SEQUENCE_ROOT = Path("outputs/ib3a_sequence_mapmatched_activity_v1_3b_thci_v1_0c")
BEFORE_ON_ROUTE_ROOT = Path("outputs/ib3a2_on_route_activity_filter_v1_3b_thci_v1_0c")
BEFORE_VISUAL_QA_ROOT = Path("outputs/ib3_activity_profile_visual_qa_v1_3b_thci_v1_0c")

AFTER_SEQUENCE_ROOT = Path("outputs/ib3a_sequence_mapmatched_activity_v1_3b_qixing_via_corridor_repair_candidate")
AFTER_ON_ROUTE_ROOT = Path("outputs/ib3a2_on_route_activity_filter_v1_3b_qixing_via_corridor_repair_candidate")
AFTER_VISUAL_QA_ROOT = Path("outputs/ib3_activity_profile_visual_qa_v1_3b_qixing_via_corridor_repair_candidate")

OUT_ROOT = Path("outputs/qixing_via_corridor_pruning_activity_rawdata_safety_audit_v1_3b")


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False)


def _file_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _stable_frame_hash(df: pd.DataFrame, cols: list[str]) -> str:
    present = [c for c in cols if c in df.columns]
    if not present:
        return ""
    work = df[present].copy()
    for col in present:
        if pd.api.types.is_numeric_dtype(work[col]):
            work[col] = pd.to_numeric(work[col], errors="coerce").round(7)
        else:
            work[col] = work[col].astype("string").fillna("<NA>")
    text = work.to_csv(index=False, lineterminator="\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _activity_paths(root: Path, activity_id: str) -> dict[str, Path]:
    folder = root / ROUTE_FOLDER
    return {
        "labeled": folder / f"{ROUTE_FOLDER}_{activity_id}_mapmatched_activity_labeled.csv",
        "on_route": folder / f"{ROUTE_FOLDER}_{activity_id}_mapmatched_activity_on_route.csv",
        "excursions": folder / f"{ROUTE_FOLDER}_{activity_id}_mapmatched_activity_excursions.csv",
    }


def _sequence_path(root: Path, activity_id: str) -> Path:
    return root / ROUTE_FOLDER / f"{activity_id}_mapmatched.csv"


def _standardized_path(activity_id: str, manifest: pd.DataFrame) -> Path | None:
    if "activity_id" not in manifest.columns:
        return None
    full_activity_id = f"{ROUTE_FOLDER}_{activity_id}"
    row = manifest[
        (manifest["route_folder"] == ROUTE_FOLDER)
        & (manifest["activity_id"].astype(str).isin([activity_id, full_activity_id]))
    ]
    if row.empty:
        return None
    out = str(row.iloc[0].get("output_file", "")).strip()
    return Path(out) if out else None


def _first_existing(cols: list[str], candidates: list[str]) -> str | None:
    for c in candidates:
        if c in cols:
            return c
    return None


def _bool_count(series: pd.Series) -> int:
    if series.empty:
        return 0
    if series.dtype == bool:
        return int(series.sum())
    lowered = series.astype(str).str.lower()
    return int(lowered.isin(["true", "1", "yes", "y"]).sum())


def _sign_reversal_count(values: pd.Series) -> int:
    vals = pd.to_numeric(values, errors="coerce").dropna()
    signs: list[int] = []
    for v in vals:
        if abs(v) < REVERSAL_DELTA_THRESHOLD_M:
            continue
        signs.append(1 if v > 0 else -1)
    if len(signs) < 2:
        return 0
    return sum(1 for a, b in zip(signs, signs[1:]) if a != b)


def _transition_count(series: pd.Series) -> int:
    vals = series.astype("string").fillna("<NA>").tolist()
    if len(vals) < 2:
        return 0
    return sum(1 for a, b in zip(vals, vals[1:]) if a != b)


def _value_counts_json(series: pd.Series) -> str:
    if series.empty:
        return "{}"
    counts = series.astype("string").fillna("<NA>").value_counts(dropna=False).sort_index()
    return json.dumps({str(k): int(v) for k, v in counts.items()}, ensure_ascii=False)


def _projection_metrics(seq: pd.DataFrame, labeled: pd.DataFrame | None) -> dict[str, Any]:
    route_dist = pd.to_numeric(seq.get("route_dist_m"), errors="coerce") if "route_dist_m" in seq.columns else pd.Series(dtype=float)
    corridor_mask = route_dist.between(CORRIDOR_START_M, CORRIDOR_END_M, inclusive="both")

    metrics: dict[str, Any] = {
        "sequence_rows": int(len(seq)),
        "route_dist_min_m": float(route_dist.min()) if not route_dist.empty else None,
        "route_dist_max_m": float(route_dist.max()) if not route_dist.empty else None,
        "route_dist_projection_reversal_n": _sign_reversal_count(seq["route_dist_delta_m"]) if "route_dist_delta_m" in seq.columns else None,
        "corridor_route_dist_projection_reversal_n": _sign_reversal_count(seq.loc[corridor_mask, "route_dist_delta_m"]) if "route_dist_delta_m" in seq.columns else None,
        "candidate_phase_counts": _value_counts_json(seq["candidate_phase"]) if "candidate_phase" in seq.columns else "{}",
        "route_progress_state_counts": _value_counts_json(seq["route_progress_state"]) if "route_progress_state" in seq.columns else "{}",
        "candidate_phase_transition_n": _transition_count(seq["candidate_phase"]) if "candidate_phase" in seq.columns else None,
        "corridor_candidate_phase_transition_n": _transition_count(seq.loc[corridor_mask, "candidate_phase"]) if "candidate_phase" in seq.columns else None,
        "route_progress_state_transition_n": _transition_count(seq["route_progress_state"]) if "route_progress_state" in seq.columns else None,
        "corridor_route_progress_state_transition_n": _transition_count(seq.loc[corridor_mask, "route_progress_state"]) if "route_progress_state" in seq.columns else None,
    }

    if "route_progress_state" in seq.columns:
        state = seq["route_progress_state"].astype("string")
        metrics.update(
            {
                "branch_ambiguous_projection_rows": int((state == "branch_ambiguous_projection").sum()),
                "off_route_projection_only_rows": int((state == "off_route_projection_only").sum()),
                "near_route_low_confidence_rows": int((state == "near_route_low_confidence").sum()),
                "on_route_reliable_rows": int((state == "on_route_reliable").sum()),
            }
        )
    else:
        metrics.update(
            {
                "branch_ambiguous_projection_rows": None,
                "off_route_projection_only_rows": None,
                "near_route_low_confidence_rows": None,
                "on_route_reliable_rows": None,
            }
        )

    if labeled is not None and "usable_on_route" in labeled.columns:
        usable = labeled["usable_on_route"]
        metrics["labeled_rows"] = int(len(labeled))
        metrics["on_route_rows_from_labeled"] = _bool_count(usable)
        metrics["non_usable_rows"] = int(len(labeled) - metrics["on_route_rows_from_labeled"])
    else:
        metrics["labeled_rows"] = None
        metrics["on_route_rows_from_labeled"] = None
        metrics["non_usable_rows"] = None

    return metrics


def _basic_numeric_summary(df: pd.DataFrame, col: str | None) -> dict[str, float | int | None]:
    if not col or col not in df.columns:
        return {"available": False, "min": None, "max": None, "mean": None, "non_null_n": 0}
    vals = pd.to_numeric(df[col], errors="coerce")
    return {
        "available": True,
        "min": float(vals.min()) if vals.notna().any() else None,
        "max": float(vals.max()) if vals.notna().any() else None,
        "mean": float(vals.mean()) if vals.notna().any() else None,
        "non_null_n": int(vals.notna().sum()),
    }


def _aligned_crosswalk(before_seq: pd.DataFrame, after_seq: pd.DataFrame, before_labeled: pd.DataFrame, after_labeled: pd.DataFrame) -> pd.DataFrame:
    key_cols = [c for c in ["row_index", "point_index"] if c in before_seq.columns and c in after_seq.columns]
    if "row_index" in key_cols:
        key_cols = ["row_index"]
    elif not key_cols:
        before_seq = before_seq.reset_index(names="_alignment_index")
        after_seq = after_seq.reset_index(names="_alignment_index")
        before_labeled = before_labeled.reset_index(names="_alignment_index")
        after_labeled = after_labeled.reset_index(names="_alignment_index")
        key_cols = ["_alignment_index"]

    b_cols = key_cols + [
        c
        for c in [
            "timestamp_s",
            "lat",
            "lon",
            "speed_mps",
            "heart_rate_bpm",
            "route_dist_m",
            "reliable_route_dist_m",
            "candidate_phase",
            "route_progress_state",
        ]
        if c in before_seq.columns
    ]
    a_cols = key_cols + [
        c
        for c in [
            "route_dist_m",
            "reliable_route_dist_m",
            "candidate_phase",
            "route_progress_state",
        ]
        if c in after_seq.columns
    ]
    work = before_seq[b_cols].merge(after_seq[a_cols], on=key_cols, how="left", suffixes=("_old", "_new"))

    for label_df, suffix in [(before_labeled, "_old"), (after_labeled, "_new")]:
        if "usable_on_route" in label_df.columns:
            cols = key_cols + ["usable_on_route"]
            work = work.merge(label_df[cols], on=key_cols, how="left")
            work = work.rename(columns={"usable_on_route": f"on_route_usable{suffix}"})

    old_route = pd.to_numeric(work.get("route_dist_m_old"), errors="coerce")
    new_route = pd.to_numeric(work.get("route_dist_m_new"), errors="coerce")
    out = pd.DataFrame(
        {
            "timestamp": work.get("timestamp_s"),
            "raw_lat": work.get("lat"),
            "raw_lon": work.get("lon"),
            "raw_speed": work.get("speed_mps") if "speed_mps" in work.columns else pd.NA,
            "raw_heart_rate": work.get("heart_rate_bpm") if "heart_rate_bpm" in work.columns else pd.NA,
            "old_route_dist_m": work.get("route_dist_m_old"),
            "new_route_dist_m": work.get("route_dist_m_new"),
            "delta_route_dist_m": new_route - old_route,
            "old_reliable_route_dist_m": work.get("reliable_route_dist_m_old"),
            "new_reliable_route_dist_m": work.get("reliable_route_dist_m_new"),
            "old_candidate_phase": work.get("candidate_phase_old"),
            "new_candidate_phase": work.get("candidate_phase_new"),
            "old_route_progress_state": work.get("route_progress_state_old"),
            "new_route_progress_state": work.get("route_progress_state_new"),
            "old_on_route_usable": work.get("on_route_usable_old"),
            "new_on_route_usable": work.get("on_route_usable_new"),
        }
    )
    return out


def _read_optional(path: Path) -> pd.DataFrame | None:
    return _read_csv(path) if path.exists() else None


def audit_activity(activity_id: str, manifest: pd.DataFrame) -> tuple[dict[str, Any], dict[str, Any], pd.DataFrame]:
    standardized_csv = _standardized_path(activity_id, manifest)
    before_sequence_csv = _sequence_path(BEFORE_SEQUENCE_ROOT, activity_id)
    after_sequence_csv = _sequence_path(AFTER_SEQUENCE_ROOT, activity_id)
    before_paths = _activity_paths(BEFORE_ON_ROUTE_ROOT, activity_id)
    after_paths = _activity_paths(AFTER_ON_ROUTE_ROOT, activity_id)

    blocking: list[str] = []
    required_files = {
        "standardized_csv": standardized_csv,
        "before_sequence_csv": before_sequence_csv,
        "after_sequence_csv": after_sequence_csv,
        "before_labeled_csv": before_paths["labeled"],
        "after_labeled_csv": after_paths["labeled"],
        "before_on_route_csv": before_paths["on_route"],
        "after_on_route_csv": after_paths["on_route"],
        "before_excursions_csv": before_paths["excursions"],
        "after_excursions_csv": after_paths["excursions"],
    }
    for name, path in required_files.items():
        if path is None or not Path(path).exists():
            blocking.append(f"missing_{name}")

    if blocking:
        audit = {
            "route_folder": ROUTE_FOLDER,
            "activity_id": activity_id,
            "blocking_issue": ";".join(blocking),
            "activity_status": "FAIL",
        }
        return audit, {}, pd.DataFrame()

    standardized = _read_csv(Path(standardized_csv))
    before_seq = _read_csv(before_sequence_csv)
    after_seq = _read_csv(after_sequence_csv)
    before_labeled = _read_csv(before_paths["labeled"])
    after_labeled = _read_csv(after_paths["labeled"])
    before_on_route = _read_csv(before_paths["on_route"])
    after_on_route = _read_csv(after_paths["on_route"])
    before_excursions = _read_optional(before_paths["excursions"])
    if before_excursions is None:
        before_excursions = pd.DataFrame()
    after_excursions = _read_optional(after_paths["excursions"])
    if after_excursions is None:
        after_excursions = pd.DataFrame()

    raw_cols = [
        "row_index",
        "point_index",
        "timestamp_s",
        "elapsed_sec",
        "dt_sec",
        "lat",
        "lon",
        "ele_m",
        "distance_m",
        "heart_rate_bpm",
    ]
    raw_cols_present = [c for c in raw_cols if c in before_seq.columns and c in after_seq.columns]
    before_hash = _stable_frame_hash(before_seq, raw_cols_present)
    after_hash = _stable_frame_hash(after_seq, raw_cols_present)

    sequence_rows_same = len(before_seq) == len(after_seq)
    row_index_same = before_seq.get("row_index", pd.Series(dtype=object)).equals(after_seq.get("row_index", pd.Series(dtype=object)))
    timestamp_order_same = before_seq.get("timestamp_s", pd.Series(dtype=object)).equals(after_seq.get("timestamp_s", pd.Series(dtype=object)))
    timestamp_set_same = sorted(before_seq["timestamp_s"].astype(str).tolist()) == sorted(after_seq["timestamp_s"].astype(str).tolist()) if "timestamp_s" in before_seq.columns and "timestamp_s" in after_seq.columns else False
    raw_signal_hash_same = before_hash == after_hash
    raw_data_modified = not (sequence_rows_same and row_index_same and timestamp_order_same and raw_signal_hash_same)
    sequence_alignment_changed = not (sequence_rows_same and row_index_same and timestamp_order_same and timestamp_set_same)

    before_metrics = _projection_metrics(before_seq, before_labeled)
    after_metrics = _projection_metrics(after_seq, after_labeled)

    before_on_route_rows = int(len(before_on_route))
    after_on_route_rows = int(len(after_on_route))
    on_route_delta_n = after_on_route_rows - before_on_route_rows
    on_route_delta_ratio = (on_route_delta_n / before_on_route_rows) if before_on_route_rows else None
    excursions_delta_n = int(len(after_excursions) - len(before_excursions))
    excursions_strongly_increase = excursions_delta_n > max(3, int(len(before_excursions) * 0.5))

    hr_col = _first_existing(list(before_seq.columns), ["heart_rate_bpm", "hr", "heart_rate"])
    speed_col = _first_existing(list(before_seq.columns), ["speed_mps", "speed", "enhanced_speed"])
    standardized_speed_col = _first_existing(list(standardized.columns), ["speed_mps", "speed", "enhanced_speed"])
    standardized_hr_col = _first_existing(list(standardized.columns), ["heart_rate_bpm", "hr", "heart_rate"])

    hr_before = _basic_numeric_summary(before_seq, hr_col)
    hr_after = _basic_numeric_summary(after_seq, hr_col)
    speed_before = _basic_numeric_summary(before_seq, speed_col)
    speed_after = _basic_numeric_summary(after_seq, speed_col)

    hr_summary_stable = hr_before == hr_after
    speed_summary_stable = speed_before == speed_after

    crosswalk = _aligned_crosswalk(before_seq, after_seq, before_labeled, after_labeled)

    audit = {
        "route_folder": ROUTE_FOLDER,
        "activity_id": activity_id,
        "standardized_csv": str(standardized_csv),
        "standardized_hash": _file_hash(Path(standardized_csv)),
        "before_sequence_csv": str(before_sequence_csv),
        "after_sequence_csv": str(after_sequence_csv),
        "sequence_rows_before": int(len(before_seq)),
        "sequence_rows_after": int(len(after_seq)),
        "sequence_rows_same": sequence_rows_same,
        "row_index_same": row_index_same,
        "timestamp_order_same": timestamp_order_same,
        "timestamp_set_same": timestamp_set_same,
        "raw_signal_hash_before": before_hash,
        "raw_signal_hash_after": after_hash,
        "raw_signal_hash_same": raw_signal_hash_same,
        "raw_data_modified": raw_data_modified,
        "sequence_alignment_changed": sequence_alignment_changed,
        "standardized_rows": int(len(standardized)),
        "standardized_speed_col": standardized_speed_col,
        "standardized_hr_col": standardized_hr_col,
        "sequence_speed_col": speed_col,
        "sequence_hr_col": hr_col,
        "hr_summary_stable": hr_summary_stable,
        "speed_summary_stable": speed_summary_stable,
        "hr_before": json.dumps(hr_before, ensure_ascii=False),
        "hr_after": json.dumps(hr_after, ensure_ascii=False),
        "speed_before": json.dumps(speed_before, ensure_ascii=False),
        "speed_after": json.dumps(speed_after, ensure_ascii=False),
        "before_labeled_rows": int(len(before_labeled)),
        "after_labeled_rows": int(len(after_labeled)),
        "before_on_route_rows": before_on_route_rows,
        "after_on_route_rows": after_on_route_rows,
        "on_route_delta_n": on_route_delta_n,
        "on_route_delta_ratio": on_route_delta_ratio,
        "before_excursions_rows": int(len(before_excursions)),
        "after_excursions_rows": int(len(after_excursions)),
        "excursions_delta_n": excursions_delta_n,
        "excursions_strongly_increase": excursions_strongly_increase,
        "blocking_issue": "",
        "activity_status": "PASS",
    }

    projection = {
        "route_folder": ROUTE_FOLDER,
        "activity_id": activity_id,
        "route_dist_max_before_m": before_metrics["route_dist_max_m"],
        "route_dist_max_after_m": after_metrics["route_dist_max_m"],
        "route_dist_projection_reversal_before_n": before_metrics["route_dist_projection_reversal_n"],
        "route_dist_projection_reversal_after_n": after_metrics["route_dist_projection_reversal_n"],
        "route_dist_projection_reversal_delta_n": after_metrics["route_dist_projection_reversal_n"] - before_metrics["route_dist_projection_reversal_n"],
        "corridor_reversal_before_n": before_metrics["corridor_route_dist_projection_reversal_n"],
        "corridor_reversal_after_n": after_metrics["corridor_route_dist_projection_reversal_n"],
        "corridor_reversal_delta_n": after_metrics["corridor_route_dist_projection_reversal_n"] - before_metrics["corridor_route_dist_projection_reversal_n"],
        "branch_ambiguous_before_rows": before_metrics["branch_ambiguous_projection_rows"],
        "branch_ambiguous_after_rows": after_metrics["branch_ambiguous_projection_rows"],
        "branch_ambiguous_delta_rows": after_metrics["branch_ambiguous_projection_rows"] - before_metrics["branch_ambiguous_projection_rows"],
        "off_route_projection_before_rows": before_metrics["off_route_projection_only_rows"],
        "off_route_projection_after_rows": after_metrics["off_route_projection_only_rows"],
        "off_route_projection_delta_rows": after_metrics["off_route_projection_only_rows"] - before_metrics["off_route_projection_only_rows"],
        "near_route_low_confidence_before_rows": before_metrics["near_route_low_confidence_rows"],
        "near_route_low_confidence_after_rows": after_metrics["near_route_low_confidence_rows"],
        "near_route_low_confidence_delta_rows": after_metrics["near_route_low_confidence_rows"] - before_metrics["near_route_low_confidence_rows"],
        "candidate_phase_transition_before_n": before_metrics["candidate_phase_transition_n"],
        "candidate_phase_transition_after_n": after_metrics["candidate_phase_transition_n"],
        "corridor_candidate_phase_transition_before_n": before_metrics["corridor_candidate_phase_transition_n"],
        "corridor_candidate_phase_transition_after_n": after_metrics["corridor_candidate_phase_transition_n"],
        "route_progress_state_transition_before_n": before_metrics["route_progress_state_transition_n"],
        "route_progress_state_transition_after_n": after_metrics["route_progress_state_transition_n"],
        "corridor_route_progress_state_transition_before_n": before_metrics["corridor_route_progress_state_transition_n"],
        "corridor_route_progress_state_transition_after_n": after_metrics["corridor_route_progress_state_transition_n"],
        "before_candidate_phase_counts": before_metrics["candidate_phase_counts"],
        "after_candidate_phase_counts": after_metrics["candidate_phase_counts"],
        "before_route_progress_state_counts": before_metrics["route_progress_state_counts"],
        "after_route_progress_state_counts": after_metrics["route_progress_state_counts"],
        "on_route_rows_before": before_on_route_rows,
        "on_route_rows_after": after_on_route_rows,
        "on_route_delta_n": on_route_delta_n,
        "on_route_delta_ratio": on_route_delta_ratio,
        "excursions_rows_before": int(len(before_excursions)),
        "excursions_rows_after": int(len(after_excursions)),
        "excursions_delta_n": excursions_delta_n,
    }

    return audit, projection, crosswalk


def decide(raw_audits: list[dict[str, Any]], projection_rows: list[dict[str, Any]]) -> tuple[str, str]:
    if any(str(r.get("activity_status")) != "PASS" for r in raw_audits):
        return "FAIL_REQUIRED_ACTIVITY_OUTPUT_MISSING", "One or more required standardized, sequence, or on-route files are missing."
    if any(bool(r.get("raw_data_modified")) for r in raw_audits):
        return "FAIL_RAWDATA_MODIFIED", "Raw or standardized activity signal changed between before/after sequence outputs."
    if any(bool(r.get("sequence_alignment_changed")) for r in raw_audits):
        return "FAIL_SEQUENCE_ALIGNMENT_CHANGED", "Sequence row/timestamp alignment changed between before/after outputs."

    on_route_degraded = any(
        r.get("on_route_delta_ratio") is not None and float(r["on_route_delta_ratio"]) < -0.10
        for r in projection_rows
    )
    excursions_increase = any(int(r.get("excursions_delta_n") or 0) > max(3, int((r.get("excursions_rows_before") or 0) * 0.5)) for r in projection_rows)
    if on_route_degraded or excursions_increase:
        return "REVIEW_ROUTE_AXIS_REMAP_DEGRADED", "Raw signal is stable, but on-route rows or excursions degraded after remap."

    clearly_improved = True
    any_improved = False
    for r in projection_rows:
        checks = [
            ("corridor_reversal_after_n", "corridor_reversal_before_n"),
            ("branch_ambiguous_after_rows", "branch_ambiguous_before_rows"),
            ("off_route_projection_after_rows", "off_route_projection_before_rows"),
            ("near_route_low_confidence_after_rows", "near_route_low_confidence_before_rows"),
        ]
        for after_key, before_key in checks:
            after = r.get(after_key)
            before = r.get(before_key)
            if after is None or before is None:
                clearly_improved = False
                continue
            if after > before:
                clearly_improved = False
            if after < before:
                any_improved = True
    if clearly_improved and any_improved:
        return "PASS_RAWDATA_SAFE_PROJECTION_IMPROVED", "Raw signal is stable and projection ambiguity/reversal metrics improved."

    return "PASS_RAWDATA_SAFE_REMAP_REVIEW_REQUIRED", "Raw signal is stable, but projection changes are mixed and need formal repair review."


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = _read_csv(MANIFEST_CSV)

    raw_audits: list[dict[str, Any]] = []
    projections: list[dict[str, Any]] = []
    for activity_id in ACTIVITY_IDS:
        audit, projection, crosswalk = audit_activity(activity_id, manifest)
        raw_audits.append(audit)
        if projection:
            projections.append(projection)
        crosswalk_path = OUT_ROOT / f"qixing_activity_projection_before_after_crosswalk_{activity_id}.csv"
        crosswalk.to_csv(crosswalk_path, index=False, encoding="utf-8-sig")

    decision, note = decide(raw_audits, projections)

    invariant_csv = OUT_ROOT / "qixing_activity_rawdata_invariant_audit.csv"
    projection_csv = OUT_ROOT / "qixing_activity_projection_before_after_summary.csv"
    improvement_csv = OUT_ROOT / "qixing_via_corridor_activity_improvement_summary.csv"
    decision_csv = OUT_ROOT / "qixing_pruning_activity_rawdata_safety_decision.csv"
    summary_json = OUT_ROOT / "qixing_pruning_activity_rawdata_safety_summary.json"

    pd.DataFrame(raw_audits).to_csv(invariant_csv, index=False, encoding="utf-8-sig")
    pd.DataFrame(projections).to_csv(projection_csv, index=False, encoding="utf-8-sig")

    improvement_rows = []
    for r in projections:
        improvement_rows.append(
            {
                "route_folder": r["route_folder"],
                "activity_id": r["activity_id"],
                "on_route_delta_n": r["on_route_delta_n"],
                "on_route_delta_ratio": r["on_route_delta_ratio"],
                "route_dist_projection_reversal_delta_n": r["route_dist_projection_reversal_delta_n"],
                "corridor_reversal_delta_n": r["corridor_reversal_delta_n"],
                "branch_ambiguous_delta_rows": r["branch_ambiguous_delta_rows"],
                "off_route_projection_delta_rows": r["off_route_projection_delta_rows"],
                "near_route_low_confidence_delta_rows": r["near_route_low_confidence_delta_rows"],
                "projection_improvement_note": (
                    "mixed"
                    if any((r.get(k) or 0) > 0 for k in ["corridor_reversal_delta_n", "branch_ambiguous_delta_rows", "off_route_projection_delta_rows", "near_route_low_confidence_delta_rows"])
                    else "non_degraded_or_improved"
                ),
            }
        )
    pd.DataFrame(improvement_rows).to_csv(improvement_csv, index=False, encoding="utf-8-sig")

    raw_data_modified = any(bool(r.get("raw_data_modified")) for r in raw_audits)
    sequence_alignment_changed = any(bool(r.get("sequence_alignment_changed")) for r in raw_audits)
    rawdata_interpretation_safe = not raw_data_modified and not sequence_alignment_changed
    formal_repair_review_ready = decision in {
        "PASS_RAWDATA_SAFE_REMAP_REVIEW_REQUIRED",
        "PASS_RAWDATA_SAFE_PROJECTION_IMPROVED",
    }

    decision_row = {
        "route_folder": ROUTE_FOLDER,
        "activities_n": len(ACTIVITY_IDS),
        "raw_data_modified": raw_data_modified,
        "sequence_alignment_changed": sequence_alignment_changed,
        "rawdata_interpretation_safe": rawdata_interpretation_safe,
        "formal_repair_review_ready": formal_repair_review_ready,
        "qixing_via_corridor_pruning_activity_rawdata_safety_status": decision,
        "note": note,
        "invariant_audit_csv": str(invariant_csv),
        "projection_summary_csv": str(projection_csv),
        "improvement_summary_csv": str(improvement_csv),
    }
    pd.DataFrame([decision_row]).to_csv(decision_csv, index=False, encoding="utf-8-sig")

    summary = {
        "route_folder": ROUTE_FOLDER,
        "activity_ids": ACTIVITY_IDS,
        "corridor_range_m": [CORRIDOR_START_M, CORRIDOR_END_M],
        "input_roots": {
            "standardized_root": str(STANDARDIZED_ROOT),
            "before_sequence_root": str(BEFORE_SEQUENCE_ROOT),
            "before_on_route_root": str(BEFORE_ON_ROUTE_ROOT),
            "before_visual_qa_root": str(BEFORE_VISUAL_QA_ROOT),
            "after_sequence_root": str(AFTER_SEQUENCE_ROOT),
            "after_on_route_root": str(AFTER_ON_ROUTE_ROOT),
            "after_visual_qa_root": str(AFTER_VISUAL_QA_ROOT),
        },
        "outputs": {
            "invariant_audit_csv": str(invariant_csv),
            "projection_summary_csv": str(projection_csv),
            "improvement_summary_csv": str(improvement_csv),
            "decision_csv": str(decision_csv),
        },
        "raw_data_modified": raw_data_modified,
        "sequence_alignment_changed": sequence_alignment_changed,
        "rawdata_interpretation_safe": rawdata_interpretation_safe,
        "formal_repair_review_ready": formal_repair_review_ready,
        "final_decision": decision,
        "note": note,
        "raw_audits": raw_audits,
        "projection_summaries": projections,
        "runtime_llm_allowed": False,
    }
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("activity_id, raw_data_modified, sequence_rows_before, sequence_rows_after, on_route_before, on_route_after, reversal_before, reversal_after, corridor_reversal_before, corridor_reversal_after")
    for audit, projection in zip(raw_audits, projections):
        print(
            f"{audit['activity_id']}, {audit['raw_data_modified']}, "
            f"{audit['sequence_rows_before']}, {audit['sequence_rows_after']}, "
            f"{projection['on_route_rows_before']}, {projection['on_route_rows_after']}, "
            f"{projection['route_dist_projection_reversal_before_n']}, {projection['route_dist_projection_reversal_after_n']}, "
            f"{projection['corridor_reversal_before_n']}, {projection['corridor_reversal_after_n']}"
        )
    print(f"final decision: {decision}")
    print(f"wrote: {invariant_csv}")
    print(f"wrote: {projection_csv}")
    print(f"wrote: {decision_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
