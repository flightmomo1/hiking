from __future__ import annotations

import argparse
import html
import importlib
import re
from pathlib import Path
from typing import Any


OFFSET_FALLBACK_COLUMNS = [
    "offset_m",
    "offset_to_route_m",
    "nearest_offset_m",
    "nearest_route_offset_m",
    "distance_to_route_m",
]

TIMESTAMP_FALLBACK_COLUMNS = [
    "timestamp_s",
    "timestamp",
    "time",
    "datetime",
    "recorded_at",
]

SUPPORTED_MANUAL_LABELS = [
    "pre_route_start_offset",
    "gps_start_drift",
    "gps_drift_near_trailhead",
    "route_choice_variant_rejoin",
    "true_mid_route_excursion_return",
    "facility_detour",
    "rest_detour_to_pavilion",
    "terminal_off_route",
    "on_route_backtrack_unexplained",
]

SUPPORTED_MANUAL_INTERPRETATIONS = [
    "route_variant",
    "post_route",
    "start_offset",
    "gps_artifact",
    "wrong_route",
    "unexplained_backtrack",
    "intentional_rest",
    "ambiguous",
]

MANUAL_LABEL_ALIASES = {
    "true_mid_route_excursion": "true_mid_route_excursion_return",
}

MANUAL_SEGMENT_ROLE_MAP = {
    "pre_route_start_offset": "manual_pre_route_start_offset",
    "gps_start_drift": "manual_gps_drift",
    "gps_drift_near_trailhead": "manual_gps_drift",
    "route_choice_variant_rejoin": "manual_route_choice_variant",
    "true_mid_route_excursion_return": "manual_off_route_excursion",
    "facility_detour": "manual_rest_detour",
    "rest_detour_to_pavilion": "manual_rest_detour",
    "terminal_off_route": "manual_terminal_off_route",
    "on_route_backtrack_unexplained": "manual_on_route_backtrack_unexplained",
}

MANUAL_REASON_COLOR_MAP = {
    "manual_pre_route_start_offset": "#0F766E",
    "manual_gps_start_drift": "#64748B",
    "manual_gps_drift_near_trailhead": "#94A3B8",
    "manual_route_choice_variant_rejoin": "#A16207",
    "manual_true_mid_route_excursion_return": "#B91C1C",
    "manual_facility_detour": "#BE185D",
    "manual_rest_detour_to_pavilion": "#BE185D",
    "manual_terminal_off_route": "#C2410C",
    "manual_on_route_backtrack_unexplained": "#475569",
}

ROUTE_PROGRESS_REASON_COLOR_MAP = {
    "route_progress_off_route_projection_only": "#9333EA",
    "route_progress_near_route_low_confidence": "#D97706",
    "route_progress_branch_ambiguous_projection": "#BE123C",
    "route_progress_unmatched": "#6B7280",
}

ROUTE_PROGRESS_REASON_MAP = {
    "off_route_projection_only": "route_progress_off_route_projection_only",
    "near_route_low_confidence": "route_progress_near_route_low_confidence",
    "branch_ambiguous_projection": "route_progress_branch_ambiguous_projection",
    "unmatched": "route_progress_unmatched",
}

ROUTE_PROGRESS_SEGMENT_ROLE_MAP = {
    "off_route_projection_only": "low_confidence_projection_off_route",
    "near_route_low_confidence": "low_confidence_projection_near_route",
    "branch_ambiguous_projection": "low_confidence_projection_branch_ambiguous",
    "unmatched": "low_confidence_projection_unmatched",
}

OUTPUT_COLUMNS = [
    "usable_on_route",
    "excluded_reason",
    "excursion_id",
    "segment_id",
    "segment_role",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Label ib3a mapmatched activity rows that are usable on the route axis, "
            "and split long off-route excursions into separate outputs."
        )
    )
    parser.add_argument("--route-folder", required=True, help="Route folder key.")
    parser.add_argument("--subject-id", default=None, help="Activity subject id.")
    parser.add_argument("--trial-id", default=None, help="Activity trial id.")
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Process every *_mapmatched.csv under the selected route folder.",
    )
    parser.add_argument(
        "--mapmatched-csv",
        default=None,
        help="Explicit ib3a mapmatched CSV path. If omitted, inferred from --mapmatched-root.",
    )
    parser.add_argument(
        "--mapmatched-root",
        default="outputs/ib3a_mapmatched_standardized_activity",
        help="Root folder containing ib3a mapmatched CSV files.",
    )
    parser.add_argument(
        "--out-dir",
        default="outputs/ib3a2_on_route_activity_filter",
        help="Output root for labeled, on-route, excursion, and summary files.",
    )
    parser.add_argument(
        "--offset-column",
        default="offset_m",
        help="Preferred offset column. Falls back to common route offset column names.",
    )
    parser.add_argument(
        "--offset-threshold-m",
        type=float,
        default=50.0,
        help="Minimum offset for off-route block candidates.",
    )
    parser.add_argument(
        "--min-duration-sec",
        type=float,
        default=60.0,
        help="Minimum contiguous candidate block duration.",
    )
    parser.add_argument(
        "--buffer-sec",
        type=float,
        default=10.0,
        help=(
            "Context buffer recorded in excursion summaries. The first version keeps "
            "labeling on the detected core block so mainline rows remain usable."
        ),
    )
    parser.add_argument(
        "--terminal-fraction",
        type=float,
        default=0.75,
        help=(
            "Deprecated alias for terminal elapsed classification. "
            "Use --terminal-elapsed-ratio."
        ),
    )
    parser.add_argument(
        "--endpoint-margin-m",
        type=float,
        default=80.0,
        help="Route distance margin from route start/end used to detect endpoint artifacts.",
    )
    parser.add_argument(
        "--terminal-elapsed-ratio",
        type=float,
        default=0.65,
        help="Blocks ending after this elapsed-time ratio are terminal/event-tail candidates.",
    )
    parser.add_argument(
        "--endpoint-ratio-threshold",
        type=float,
        default=0.7,
        help="Minimum share of block points near route endpoints for route_endpoint_artifact.",
    )
    parser.add_argument(
        "--debug-html-map",
        action="store_true",
        help="Also write an optional HTML map showing usable and excluded points.",
    )
    parser.add_argument(
        "--debug-point-step",
        type=int,
        default=5,
        help="Draw one clickable raw GPS point every N rows in debug maps. Use 1 to draw every point.",
    )
    parser.add_argument(
        "--manual-override-csv",
        default=None,
        help=(
            "Optional manual event override CSV. If omitted, uses the route-level "
            "manual_event_override_template.csv when present."
        ),
    )
    parser.add_argument(
        "--no-manual-overrides",
        action="store_true",
        help="Ignore any manual override CSV even when it exists.",
    )
    return parser.parse_args()


def infer_mapmatched_csv(args: argparse.Namespace) -> Path:
    if args.mapmatched_csv:
        return Path(args.mapmatched_csv)
    return (
        Path(args.mapmatched_root)
        / str(args.route_folder)
        / f"{args.subject_id}_{args.trial_id}_mapmatched.csv"
    )


def parse_subject_trial_from_path(path: Path) -> tuple[str, str]:
    match = re.match(r"^(.+?)_(\d+)_mapmatched\.csv$", path.name)
    if not match:
        raise ValueError(f"could not parse subject_id/trial_id from filename: {path.name}")
    return match.group(1), match.group(2)


def resolve_offset_column(df: Any, preferred: str) -> str:
    candidates = [preferred] + [col for col in OFFSET_FALLBACK_COLUMNS if col != preferred]
    for col in candidates:
        if col in df.columns:
            return col
    raise ValueError(f"missing offset column; tried: {', '.join(candidates)}")


def add_elapsed_sec(df: Any) -> Any:
    if "elapsed_sec" in df.columns:
        df["elapsed_sec"] = pd.to_numeric(df["elapsed_sec"], errors="coerce")
        if df["elapsed_sec"].notna().any():
            return df

    timestamp_col = next((col for col in TIMESTAMP_FALLBACK_COLUMNS if col in df.columns), None)
    if timestamp_col is None:
        raise ValueError("missing elapsed_sec and no timestamp fallback column is available")

    numeric_ts = pd.to_numeric(df[timestamp_col], errors="coerce")
    if numeric_ts.notna().any():
        df["elapsed_sec"] = numeric_ts - numeric_ts.dropna().iloc[0]
        return df

    parsed = pd.to_datetime(df[timestamp_col], errors="coerce", utc=True)
    if not parsed.notna().any():
        raise ValueError(f"could not parse timestamp fallback column: {timestamp_col}")
    df["elapsed_sec"] = (parsed - parsed.dropna().iloc[0]).dt.total_seconds()
    return df


def add_stable_point_indices(df: Any) -> Any:
    out = df.copy()
    source_candidates = ["source_csv_row_index", "row_index", "point_index", "index", "Unnamed: 0"]
    source_col = next((col for col in source_candidates if col in out.columns), None)
    if source_col is not None:
        out["source_csv_row_index"] = out[source_col]
    elif "source_csv_row_index" not in out.columns:
        out["source_csv_row_index"] = pd.NA
    out["row_index"] = range(len(out))
    out["point_index"] = out["row_index"]
    return out

def to_bool_series(series: Any) -> Any:
    return series.astype(str).str.strip().str.lower().isin(
        ["true", "1", "yes", "y"]
    )


def find_candidate_blocks(df: Any, offset_col: str, offset_threshold_m: float) -> list[tuple[int, int]]:
    match_quality = df["match_quality"].astype(str).str.strip().str.lower() if "match_quality" in df.columns else ""
    offsets = pd.to_numeric(df[offset_col], errors="coerce")
    mask = (match_quality == "off_route") & (offsets >= offset_threshold_m)

    blocks: list[tuple[int, int]] = []
    start: int | None = None
    for idx, is_candidate in enumerate(mask.tolist()):
        if is_candidate and start is None:
            start = idx
        if (not is_candidate or idx == len(mask) - 1) and start is not None:
            end = idx - 1 if not is_candidate else idx
            blocks.append((start, end))
            start = None
    return blocks


def classify_blocks(
    df: Any,
    blocks: list[tuple[int, int]],
    min_duration_sec: float,
    buffer_sec: float,
    terminal_elapsed_ratio: float,
    endpoint_margin_m: float,
    endpoint_ratio_threshold: float,
) -> list[dict[str, Any]]:
    elapsed = pd.to_numeric(df["elapsed_sec"], errors="coerce")
    activity_start = float(elapsed.min())
    activity_end = float(elapsed.max())
    activity_duration = max(0.0, activity_end - activity_start)

    route_dist_col = "nearest_route_dist_m" if "nearest_route_dist_m" in df.columns else "route_dist_m"
    if route_dist_col not in df.columns:
        raise ValueError("endpoint artifact detection requires nearest_route_dist_m or route_dist_m")
    route_dist = pd.to_numeric(df[route_dist_col], errors="coerce")
    if route_dist_col == "nearest_route_dist_m" and "route_dist_m" in df.columns:
        route_dist = route_dist.combine_first(pd.to_numeric(df["route_dist_m"], errors="coerce"))
    route_length_m = float(route_dist.max()) if route_dist.notna().any() else 0.0

    excursions: list[dict[str, Any]] = []
    excursion_id = 1
    for start_idx, end_idx in blocks:
        block = df.iloc[start_idx : end_idx + 1]
        start_sec = float(block["elapsed_sec"].min())
        end_sec = float(block["elapsed_sec"].max())
        duration_sec = end_sec - start_sec
        if duration_sec < min_duration_sec:
            continue

        block_route_dist = pd.to_numeric(block[route_dist_col], errors="coerce")
        if route_dist_col == "nearest_route_dist_m" and "route_dist_m" in block.columns:
            block_route_dist = block_route_dist.combine_first(pd.to_numeric(block["route_dist_m"], errors="coerce"))
        near_start = block_route_dist <= endpoint_margin_m
        near_end = block_route_dist >= route_length_m - endpoint_margin_m
        near_endpoint = near_start | near_end
        block_point_count = int(len(block))
        near_start_count = int(near_start.sum())
        near_end_count = int(near_end.sum())
        endpoint_ratio = float(near_endpoint.sum() / block_point_count) if block_point_count else 0.0
        if activity_duration > 0:
            block_start_ratio = float((start_sec - activity_start) / activity_duration)
            block_end_ratio = float((end_sec - activity_start) / activity_duration)
        else:
            block_start_ratio = 0.0
            block_end_ratio = 0.0

        if block_end_ratio >= terminal_elapsed_ratio:
            if endpoint_ratio >= endpoint_ratio_threshold:
                role = "route_endpoint_artifact"
            else:
                role = "terminal_off_route"
        else:
            role = "off_route_excursion"

        excursions.append(
            {
                "excursion_id": excursion_id,
                "event_source": "auto_detected",
                "manual_event_id": "",
                "manual_label": "",
                "excluded_reason": role,
                "segment_role": role,
                "start_index": start_idx,
                "end_index": end_idx,
                "start_elapsed_sec": start_sec,
                "end_elapsed_sec": end_sec,
                "block_start_elapsed_sec": start_sec,
                "block_end_elapsed_sec": end_sec,
                "block_start_ratio": block_start_ratio,
                "block_end_ratio": block_end_ratio,
                "duration_sec": duration_sec,
                "buffer_start_elapsed_sec": max(activity_start, start_sec - buffer_sec),
                "buffer_end_elapsed_sec": min(activity_end, end_sec + buffer_sec),
                "endpoint_ratio": endpoint_ratio,
                "near_start_count": near_start_count,
                "near_end_count": near_end_count,
                "endpoint_near_start_count": near_start_count,
                "endpoint_near_end_count": near_end_count,
                "route_length_m": route_length_m,
                "route_dist_col_used": route_dist_col,
                "rows": block_point_count,
            }
        )
        excursion_id += 1
    return excursions


def label_activity(df: Any, excursions: list[dict[str, Any]]) -> Any:
    labeled = df.copy()
    if "row_index" not in labeled.columns:
        labeled["row_index"] = range(len(labeled))
    if "point_index" not in labeled.columns:
        labeled["point_index"] = labeled["row_index"]
    if "source_csv_row_index" not in labeled.columns:
        labeled["source_csv_row_index"] = pd.NA
    labeled["usable_on_route"] = True
    labeled["excluded_reason"] = ""
    labeled["excursion_id"] = pd.NA
    labeled["manual_override_applied"] = False
    labeled["manual_event_id"] = ""
    labeled["manual_label"] = ""
    labeled["manual_interpretation"] = ""
    if "segment_id" not in labeled.columns:
        labeled["segment_id"] = pd.NA
    labeled["segment_role"] = "mainline"

    for excursion in excursions:
        start_idx = int(excursion["start_index"])
        end_idx = int(excursion["end_index"])
        row_index = labeled.index[start_idx : end_idx + 1]
        reason = excursion["excluded_reason"]
        labeled.loc[row_index, "usable_on_route"] = False
        labeled.loc[row_index, "excluded_reason"] = reason
        labeled.loc[row_index, "excursion_id"] = int(excursion["excursion_id"])
        labeled.loc[row_index, "segment_role"] = reason

    return labeled


def apply_route_progress_filter(labeled: Any) -> Any:
    """
    Use ib3a_sequence v3 route-progress semantics.

    Projection columns such as route_dist_m / projected_route_dist_m are kept
    for debugging, but rows with route_progress_reliable=False should not enter
    on-route analysis outputs.
    """
    out = labeled.copy()

    if "route_progress_reliable" not in out.columns:
        return out

    reliable = to_bool_series(out["route_progress_reliable"])
    state = (
        out["route_progress_state"].fillna("").astype(str).str.strip()
        if "route_progress_state" in out.columns
        else ""
    )

    # Only add route-progress exclusion to rows that are still usable.
    # Existing off_route_excursion / terminal_off_route / manual labels are preserved.
    mask = (~reliable) & out["usable_on_route"].fillna(True)

    if not mask.any():
        return out

    reason = state.map(ROUTE_PROGRESS_REASON_MAP).fillna("route_progress_low_confidence")
    role = state.map(ROUTE_PROGRESS_SEGMENT_ROLE_MAP).fillna("low_confidence_projection")

    out.loc[mask, "usable_on_route"] = False
    out.loc[mask, "excluded_reason"] = reason.loc[mask]
    out.loc[mask, "segment_role"] = role.loc[mask]

    if "route_progress_excluded" not in out.columns:
        out["route_progress_excluded"] = False
    out.loc[mask, "route_progress_excluded"] = True

    return out



def resolve_manual_override_csv(args: argparse.Namespace, route_folder: str) -> Path | None:
    if args.no_manual_overrides:
        return None
    if args.manual_override_csv:
        return Path(args.manual_override_csv)
    candidate = (
        Path(args.out_dir)
        / route_folder
        / f"{route_folder}_ib3a2_manual_event_override_template.csv"
    )
    return candidate if candidate.exists() else None


def load_manual_overrides(args: argparse.Namespace, route_folder: str, subject_id: str, trial_id: str) -> Any:
    override_csv = resolve_manual_override_csv(args, route_folder)
    if override_csv is None:
        return pd.DataFrame()
    if not override_csv.exists():
        raise FileNotFoundError(f"manual override CSV does not exist: {override_csv}")

    overrides = pd.read_csv(override_csv, dtype=str).fillna("")
    required = ["route_folder", "subject_id", "trial_id", "manual_label", "manual_start_index", "manual_end_index"]
    missing = [col for col in required if col not in overrides.columns]
    if missing:
        raise ValueError(f"manual override CSV missing required columns: {missing}")

    overrides["manual_label"] = overrides["manual_label"].map(canonical_manual_label)
    unsupported = sorted(
        set(overrides.loc[overrides["manual_label"].astype(str).str.strip() != "", "manual_label"])
        - set(SUPPORTED_MANUAL_LABELS)
    )
    if unsupported:
        supported = ", ".join(SUPPORTED_MANUAL_LABELS)
        raise ValueError(f"unsupported manual_label values: {unsupported}; supported: {supported}")
    if "manual_interpretation" in overrides.columns:
        unknown_interpretations = sorted(
            set(
                overrides.loc[
                    overrides["manual_interpretation"].astype(str).str.strip() != "",
                    "manual_interpretation",
                ]
            )
            - set(SUPPORTED_MANUAL_INTERPRETATIONS)
        )
        if unknown_interpretations:
            supported = ", ".join(SUPPORTED_MANUAL_INTERPRETATIONS)
            raise ValueError(
                f"unsupported manual_interpretation values: {unknown_interpretations}; supported: {supported}"
            )

    selected = overrides[
        (overrides["route_folder"].astype(str) == str(route_folder))
        & (overrides["subject_id"].astype(str) == str(subject_id))
        & (overrides["trial_id"].astype(str) == str(trial_id))
        & (overrides["manual_label"].astype(str).str.strip() != "")
    ].copy()
    return selected.reset_index(drop=True)


def canonical_manual_label(label: str) -> str:
    clean = str(label).strip()
    return MANUAL_LABEL_ALIASES.get(clean, clean)


def manual_label_to_reason(label: str) -> str:
    clean = canonical_manual_label(label)
    if clean.startswith("manual_"):
        return clean
    return f"manual_{clean}" if clean else ""


def manual_label_to_segment_role(label: str) -> str:
    clean = canonical_manual_label(label)
    return MANUAL_SEGMENT_ROLE_MAP.get(clean, manual_label_to_reason(clean))


def apply_manual_overrides(labeled: Any, overrides: Any) -> Any:
    if overrides is None or overrides.empty:
        return labeled

    out = labeled.copy()
    max_row_index = int(pd.to_numeric(out["row_index"], errors="coerce").max())
    for override_idx, override in overrides.iterrows():
        try:
            start_index = int(float(override["manual_start_index"]))
            end_raw = str(override.get("manual_end_index", "")).strip()
            end_index = max_row_index if end_raw.lower() in {"", "last", "end"} else int(float(end_raw))
        except ValueError as exc:
            raise ValueError(f"invalid manual override index at row {override_idx}: {exc}") from exc

        start_index = max(0, start_index)
        end_index = min(max_row_index, end_index)
        if end_index < start_index:
            raise ValueError(f"manual override end before start at row {override_idx}: {start_index}>{end_index}")

        manual_label = canonical_manual_label(override["manual_label"])
        excluded_reason = manual_label_to_reason(manual_label)
        segment_role = manual_label_to_segment_role(manual_label)
        manual_event_id = str(override.get("manual_event_id", "")).strip()
        manual_interpretation = str(override.get("manual_interpretation", "")).strip()
        mask = (out["row_index"].astype(int) >= start_index) & (out["row_index"].astype(int) <= end_index)

        out.loc[mask, "usable_on_route"] = False
        out.loc[mask, "excluded_reason"] = excluded_reason
        out.loc[mask, "segment_role"] = segment_role
        out.loc[mask, "manual_override_applied"] = True
        out.loc[mask, "manual_event_id"] = manual_event_id
        out.loc[mask, "manual_label"] = manual_label
        out.loc[mask, "manual_interpretation"] = manual_interpretation

    return out


def manual_overrides_to_excursions(
    labeled: Any,
    overrides: Any,
    start_excursion_id: int,
    endpoint_margin_m: float,
) -> list[dict[str, Any]]:
    if overrides is None or overrides.empty:
        return []

    manual_excursions: list[dict[str, Any]] = []
    max_row_index = int(pd.to_numeric(labeled["row_index"], errors="coerce").max())
    route_dist_col = "nearest_route_dist_m" if "nearest_route_dist_m" in labeled.columns else "route_dist_m"
    route_dist = pd.to_numeric(labeled[route_dist_col], errors="coerce") if route_dist_col in labeled.columns else None
    route_length_m = float(route_dist.max()) if route_dist is not None and route_dist.notna().any() else 0.0

    excursion_id = start_excursion_id
    for override_idx, override in overrides.iterrows():
        try:
            start_index = int(float(override["manual_start_index"]))
            end_raw = str(override.get("manual_end_index", "")).strip()
            end_index = max_row_index if end_raw.lower() in {"", "last", "end"} else int(float(end_raw))
        except ValueError as exc:
            raise ValueError(f"invalid manual override index at row {override_idx}: {exc}") from exc

        start_index = max(0, start_index)
        end_index = min(max_row_index, end_index)
        block = labeled[(labeled["row_index"].astype(int) >= start_index) & (labeled["row_index"].astype(int) <= end_index)]
        if block.empty:
            continue

        start_sec = float(pd.to_numeric(block["elapsed_sec"], errors="coerce").min())
        end_sec = float(pd.to_numeric(block["elapsed_sec"], errors="coerce").max())
        activity_start = float(pd.to_numeric(labeled["elapsed_sec"], errors="coerce").min())
        activity_end = float(pd.to_numeric(labeled["elapsed_sec"], errors="coerce").max())
        activity_duration = max(0.0, activity_end - activity_start)
        if activity_duration > 0:
            block_start_ratio = float((start_sec - activity_start) / activity_duration)
            block_end_ratio = float((end_sec - activity_start) / activity_duration)
        else:
            block_start_ratio = 0.0
            block_end_ratio = 0.0

        if route_dist_col in block.columns:
            block_route_dist = pd.to_numeric(block[route_dist_col], errors="coerce")
            near_start_count = int((block_route_dist <= endpoint_margin_m).sum())
            near_end_count = int((block_route_dist >= route_length_m - endpoint_margin_m).sum())
            endpoint_ratio = float(
                ((block_route_dist <= endpoint_margin_m) | (block_route_dist >= route_length_m - endpoint_margin_m)).sum()
                / len(block)
            )
        else:
            near_start_count = 0
            near_end_count = 0
            endpoint_ratio = 0.0

        manual_label = canonical_manual_label(override["manual_label"])
        excluded_reason = manual_label_to_reason(manual_label)
        segment_role = manual_label_to_segment_role(manual_label)
        manual_interpretation = str(override.get("manual_interpretation", "")).strip()
        manual_excursions.append(
            {
                "excursion_id": excursion_id,
                "event_source": "manual_override",
                "manual_event_id": str(override.get("manual_event_id", "")).strip(),
                "manual_label": manual_label,
                "manual_interpretation": manual_interpretation,
                "excluded_reason": excluded_reason,
                "segment_role": segment_role,
                "start_index": start_index,
                "end_index": end_index,
                "start_elapsed_sec": start_sec,
                "end_elapsed_sec": end_sec,
                "block_start_elapsed_sec": start_sec,
                "block_end_elapsed_sec": end_sec,
                "block_start_ratio": block_start_ratio,
                "block_end_ratio": block_end_ratio,
                "duration_sec": end_sec - start_sec,
                "buffer_start_elapsed_sec": start_sec,
                "buffer_end_elapsed_sec": end_sec,
                "endpoint_ratio": endpoint_ratio,
                "near_start_count": near_start_count,
                "near_end_count": near_end_count,
                "endpoint_near_start_count": near_start_count,
                "endpoint_near_end_count": near_end_count,
                "route_length_m": route_length_m,
                "route_dist_col_used": route_dist_col,
                "rows": int(len(block)),
            }
        )
        excursion_id += 1

    return manual_excursions


def manual_summary_counts(labeled: Any | None, manual_excursions: list[dict[str, Any]] | None) -> dict[str, int]:
    counts: dict[str, int] = {}
    manual_excursions = manual_excursions or []
    for label in SUPPORTED_MANUAL_LABELS:
        if labeled is not None and "manual_label" in labeled.columns:
            rows = int((labeled["manual_label"].astype(str) == label).sum())
        else:
            rows = 0
        events = sum(
            1
            for excursion in manual_excursions
            if excursion.get("event_source") == "manual_override"
            and excursion.get("manual_label") == label
        )
        counts[f"manual_{label}_rows"] = rows
        counts[f"manual_{label}_event_count"] = events
    for interpretation in SUPPORTED_MANUAL_INTERPRETATIONS:
        if labeled is not None and "manual_interpretation" in labeled.columns:
            rows = int((labeled["manual_interpretation"].astype(str) == interpretation).sum())
        else:
            rows = 0
        events = sum(
            1
            for excursion in manual_excursions
            if excursion.get("event_source") == "manual_override"
            and excursion.get("manual_interpretation") == interpretation
        )
        counts[f"manual_interpretation_{interpretation}_rows"] = rows
        counts[f"manual_interpretation_{interpretation}_event_count"] = events
    return counts


def summarize_labeled(
    labeled: Any,
    excursions: list[dict[str, Any]],
    manual_excursions: list[dict[str, Any]],
    route_folder: str,
    subject_id: str,
    trial_id: str,
    offset_col: str,
    args: argparse.Namespace,
) -> str:
    total_rows = len(labeled)
    usable_rows = int(labeled["usable_on_route"].sum())
    excluded_rows = total_rows - usable_rows
    manual_counts = manual_summary_counts(labeled, manual_excursions)
    lines = [
        f"route_folder: {route_folder}",
        f"subject_id: {subject_id}",
        f"trial_id: {trial_id}",
        f"offset_column: {offset_col}",
        f"offset_threshold_m: {args.offset_threshold_m}",
        f"min_duration_sec: {args.min_duration_sec}",
        f"buffer_sec: {args.buffer_sec}",
        f"endpoint_margin_m: {args.endpoint_margin_m}",
        f"terminal_elapsed_ratio: {args.terminal_elapsed_ratio}",
        f"endpoint_ratio_threshold: {args.endpoint_ratio_threshold}",
        f"rows_total: {total_rows}",
        f"rows_usable_on_route: {usable_rows}",
        f"rows_excluded: {excluded_rows}",
        f"excursion_count: {len(excursions)}",
        "",
    ]
    for label in SUPPORTED_MANUAL_LABELS:
        lines.append(f"manual_{label}_rows: {manual_counts[f'manual_{label}_rows']}")
        lines.append(f"manual_{label}_event_count: {manual_counts[f'manual_{label}_event_count']}")
    for interpretation in SUPPORTED_MANUAL_INTERPRETATIONS:
        lines.append(
            f"manual_interpretation_{interpretation}_rows: "
            f"{manual_counts[f'manual_interpretation_{interpretation}_rows']}"
        )
        lines.append(
            f"manual_interpretation_{interpretation}_event_count: "
            f"{manual_counts[f'manual_interpretation_{interpretation}_event_count']}"
        )
    lines.append("")
    for excursion in excursions:
        lines.extend(
            [
                f"excursion_id: {excursion['excursion_id']}",
                f"excluded_reason: {excursion['excluded_reason']}",
                f"start_elapsed_sec: {excursion['start_elapsed_sec']:.3f}",
                f"end_elapsed_sec: {excursion['end_elapsed_sec']:.3f}",
                f"block_start_ratio: {excursion['block_start_ratio']:.6f}",
                f"block_end_ratio: {excursion['block_end_ratio']:.6f}",
                f"duration_sec: {excursion['duration_sec']:.3f}",
                f"buffer_start_elapsed_sec: {excursion['buffer_start_elapsed_sec']:.3f}",
                f"buffer_end_elapsed_sec: {excursion['buffer_end_elapsed_sec']:.3f}",
                f"endpoint_ratio: {excursion['endpoint_ratio']:.6f}",
                f"near_start_count: {excursion['near_start_count']}",
                f"near_end_count: {excursion['near_end_count']}",
                f"route_length_m: {excursion['route_length_m']:.3f}",
                f"rows: {excursion['rows']}",
                "",
            ]
        )
    return "\n".join(lines)


def build_batch_summary_row(
    route_folder: str,
    subject_id: str,
    trial_id: str,
    labeled: Any | None,
    excursions: list[dict[str, Any]] | None,
    manual_excursions: list[dict[str, Any]] | None,
    offset_col: str | None,
    labeled_path: Path | None,
    on_route_path: Path | None,
    excursions_path: Path | None,
    status: str,
    error_message: str = "",
) -> dict[str, Any]:
    if labeled is None:
        row = {
            "route_folder": route_folder,
            "subject_id": subject_id,
            "trial_id": trial_id,
            "rows_total": 0,
            "rows_usable_on_route": 0,
            "rows_excluded": 0,
            "usable_ratio": 0.0,
            "excursion_count": 0,
            "off_route_excursion_count": 0,
            "terminal_off_route_count": 0,
            "route_endpoint_artifact_count": 0,
            "mixed_event_trial": False,
            "max_offset_m": pd.NA,
            "max_off_route_duration_sec": pd.NA,
            "output_labeled_csv": str(labeled_path or ""),
            "output_on_route_csv": str(on_route_path or ""),
            "output_excursions_csv": str(excursions_path or ""),
            "status": status,
            "error_message": error_message,
        }
        row.update(manual_summary_counts(None, None))
        return row

    excursions = excursions or []
    manual_excursions = manual_excursions or []
    rows_total = int(len(labeled))
    rows_usable = int(labeled["usable_on_route"].sum())
    rows_excluded = rows_total - rows_usable
    max_offset = pd.NA
    if offset_col and offset_col in labeled.columns:
        offsets = pd.to_numeric(labeled[offset_col], errors="coerce")
        if offsets.notna().any():
            max_offset = float(offsets.max())
    durations = [float(excursion["duration_sec"]) for excursion in excursions]
    event_types = {excursion["excluded_reason"] for excursion in excursions}
    row = {
        "route_folder": route_folder,
        "subject_id": subject_id,
        "trial_id": trial_id,
        "rows_total": rows_total,
        "rows_usable_on_route": rows_usable,
        "rows_excluded": rows_excluded,
        "usable_ratio": float(rows_usable / rows_total) if rows_total else 0.0,
        "excursion_count": len(excursions),
        "off_route_excursion_count": sum(
            1 for excursion in excursions if excursion["excluded_reason"] == "off_route_excursion"
        ),
        "terminal_off_route_count": sum(
            1 for excursion in excursions if excursion["excluded_reason"] == "terminal_off_route"
        ),
        "route_endpoint_artifact_count": sum(
            1 for excursion in excursions if excursion["excluded_reason"] == "route_endpoint_artifact"
        ),
        "mixed_event_trial": len(event_types) > 1,
        "max_offset_m": max_offset,
        "max_off_route_duration_sec": max(durations) if durations else 0.0,
        "output_labeled_csv": str(labeled_path or ""),
        "output_on_route_csv": str(on_route_path or ""),
        "output_excursions_csv": str(excursions_path or ""),
        "status": status,
        "error_message": error_message,
    }
    row.update(manual_summary_counts(labeled, manual_excursions))
    return row


DEBUG_POPUP_COLUMNS = [
    "row_index",
    "point_index",
    "subject_id",
    "trial_id",
    "elapsed_sec",
    "timestamp",
    "timestamp_s",
    "lat",
    "lon",
    "route_dist_m",
    "projected_route_dist_m",
    "reliable_route_dist_m",
    "route_progress_reliable",
    "route_progress_state",
    "route_projection_confidence",
    "route_projection_note",
    "route_progress_excluded",
    "nearest_route_dist_m",
    "offset_m",
    "match_quality",
    "usable_on_route",
    "excluded_reason",
    "manual_override_applied",
    "manual_event_id",
    "manual_label",
    "manual_interpretation",
    "segment_id",
    "segment_role",
]


def fmt_popup_value(value: Any) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return str(value)


def debug_color_for_row(row: Any) -> str:
    if bool(row.get("usable_on_route", False)):
        return "#2563EB"
    reason = str(row.get("excluded_reason", "")).strip()
    if reason == "off_route_excursion":
        return "#DC2626"
    if reason == "terminal_off_route":
        return "#F97316"
    if reason == "route_endpoint_artifact":
        return "#7C3AED"
    if reason in MANUAL_REASON_COLOR_MAP:
        return MANUAL_REASON_COLOR_MAP[reason]
    if reason in ROUTE_PROGRESS_REASON_COLOR_MAP:
        return ROUTE_PROGRESS_REASON_COLOR_MAP[reason]
    return "#6B7280"


def debug_popup_for_row(row: Any) -> Any:
    lines = []
    for col in DEBUG_POPUP_COLUMNS:
        if col not in row.index:
            continue
        lines.append(
            f"<b>{html.escape(col)}:</b> {html.escape(fmt_popup_value(row.get(col)))}"
        )
    return folium.Popup("<br>".join(lines), max_width=360)


def write_debug_map(labeled: Any, output_path: Path, debug_point_step: int) -> None:
    global folium
    folium = importlib.import_module("folium")
    if "lat" not in labeled.columns or "lon" not in labeled.columns:
        raise ValueError("debug map requires lat and lon columns")

    points = labeled.dropna(subset=["lat", "lon"]).copy()
    if points.empty:
        raise ValueError("debug map has no valid lat/lon rows")
    point_step = max(1, int(debug_point_step))
    points_to_draw = points[points["row_index"].astype(int) % point_step == 0].copy()

    m = folium.Map(
        location=[float(points["lat"].mean()), float(points["lon"].mean())],
        zoom_start=15,
        tiles="CartoDB positron",
    )
    layers = {
        "usable_on_route": folium.FeatureGroup(name="usable_on_route", show=True),
        "off_route_excursion": folium.FeatureGroup(name="off_route_excursion", show=True),
        "terminal_off_route": folium.FeatureGroup(name="terminal_off_route", show=True),
        "route_endpoint_artifact": folium.FeatureGroup(name="route_endpoint_artifact", show=True),
        "excluded_other": folium.FeatureGroup(name="excluded_other", show=True),
    }
    for reason in MANUAL_REASON_COLOR_MAP:
        layers[reason] = folium.FeatureGroup(name=reason, show=True)

    for _, row in points_to_draw.iterrows():
        color = debug_color_for_row(row)
        if bool(row.get("usable_on_route", False)):
            layer_name = "usable_on_route"
        else:
            reason = str(row.get("excluded_reason", "")).strip()
            layer_name = reason if reason in layers else "excluded_other"
        marker = folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=2,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            weight=1,
            popup=debug_popup_for_row(row),
        )
        marker.add_to(layers[layer_name])

    for layer in layers.values():
        layer.add_to(m)
    title_html = (
        f'<div style="position: fixed; top: 12px; left: 50px; z-index: 9999; '
        f'background: white; padding: 8px 10px; border: 1px solid #d1d5db; '
        f'font: 13px Arial, sans-serif;">'
        f'<b>ib3a2 QA debug map</b><br>'
        f'clickable raw GPS points shown: {len(points_to_draw)} / {len(points)} '
        f'(debug_point_step={point_step})</div>'
    )
    m.get_root().html.add_child(folium.Element(title_html))
    folium.LayerControl(collapsed=False).add_to(m)
    m.fit_bounds(points[["lat", "lon"]].to_numpy().tolist())
    m.save(output_path)


def output_paths(out_dir: Path, route_folder: str, subject_id: str, trial_id: str) -> dict[str, Path]:
    output_dir = out_dir / route_folder
    stem = f"{route_folder}_{subject_id}_{trial_id}_mapmatched_activity"
    return {
        "dir": output_dir,
        "labeled": output_dir / f"{stem}_labeled.csv",
        "on_route": output_dir / f"{stem}_on_route.csv",
        "excursions": output_dir / f"{stem}_excursions.csv",
        "summary": output_dir / f"{route_folder}_{subject_id}_{trial_id}_on_route_filter_summary.txt",
        "debug_map": output_dir / f"{stem}_on_route_filter_debug_map.html",
    }


def write_manual_override_template(
    output_dir: Path,
    route_folder: str,
    trial_rows: list[dict[str, Any]],
) -> Path:
    template_path = output_dir / f"{route_folder}_ib3a2_manual_event_override_template.csv"
    columns = [
        "route_folder",
        "subject_id",
        "trial_id",
        "manual_event_id",
        "manual_label",
        "manual_start_index",
        "manual_end_index",
        "manual_start_elapsed_sec",
        "manual_end_elapsed_sec",
        "manual_note",
    ]
    existing = pd.DataFrame(columns=columns)
    if template_path.exists():
        existing = pd.read_csv(template_path, dtype=str).fillna("")
        for col in columns:
            if col not in existing.columns:
                existing[col] = ""
        existing = existing[columns]

    rows = []
    seen: set[tuple[str, str]] = set(
        zip(existing["subject_id"].astype(str), existing["trial_id"].astype(str))
    )
    for row in trial_rows:
        subject_id = str(row.get("subject_id", ""))
        trial_id = str(row.get("trial_id", ""))
        key = (subject_id, trial_id)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "route_folder": route_folder,
                "subject_id": subject_id,
                "trial_id": trial_id,
                "manual_event_id": "",
                "manual_label": "",
                "manual_start_index": "",
                "manual_end_index": "",
                "manual_start_elapsed_sec": "",
                "manual_end_elapsed_sec": "",
                "manual_note": "",
            }
        )
    appended = pd.DataFrame(rows, columns=columns)
    out = pd.concat([existing, appended], ignore_index=True)
    out.to_csv(template_path, index=False, encoding="utf-8-sig")
    return template_path


def process_one(
    args: argparse.Namespace,
    route_folder: str,
    subject_id: str,
    trial_id: str,
    input_csv: Path,
) -> dict[str, Any]:
    if not input_csv.exists():
        raise FileNotFoundError(f"missing mapmatched CSV: {input_csv}")

    df = pd.read_csv(input_csv, low_memory=False)
    df = add_stable_point_indices(df)
    df = add_elapsed_sec(df)
    offset_col = resolve_offset_column(df, args.offset_column)
    df[offset_col] = pd.to_numeric(df[offset_col], errors="coerce")

    candidate_blocks = find_candidate_blocks(df, offset_col, args.offset_threshold_m)
    excursions = classify_blocks(
        df=df,
        blocks=candidate_blocks,
        min_duration_sec=args.min_duration_sec,
        buffer_sec=args.buffer_sec,
        terminal_elapsed_ratio=args.terminal_elapsed_ratio,
        endpoint_margin_m=args.endpoint_margin_m,
        endpoint_ratio_threshold=args.endpoint_ratio_threshold,
    )

    labeled = label_activity(df, excursions)

    # ib3a_sequence v3: remove low-confidence projected rows from on-route analysis.
    labeled = apply_route_progress_filter(labeled)

    manual_overrides = load_manual_overrides(args, route_folder, subject_id, trial_id)
    labeled = apply_manual_overrides(labeled, manual_overrides)
    on_route = labeled[labeled["usable_on_route"]].copy()
    manual_excursions = manual_overrides_to_excursions(
        labeled,
        manual_overrides,
        start_excursion_id=len(excursions) + 1,
        endpoint_margin_m=args.endpoint_margin_m,
    )
    excursion_summary = pd.DataFrame(excursions + manual_excursions)

    paths = output_paths(Path(args.out_dir), route_folder, subject_id, trial_id)
    output_dir = paths["dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    labeled.to_csv(paths["labeled"], index=False, encoding="utf-8-sig")
    on_route.to_csv(paths["on_route"], index=False, encoding="utf-8-sig")
    excursion_summary.to_csv(paths["excursions"], index=False, encoding="utf-8-sig")
    paths["summary"].write_text(
        summarize_labeled(labeled, excursions, manual_excursions, route_folder, subject_id, trial_id, offset_col, args),
        encoding="utf-8",
    )

    debug_path = None
    if args.debug_html_map:
        debug_path = paths["debug_map"]
        write_debug_map(labeled, debug_path, args.debug_point_step)

    return build_batch_summary_row(
        route_folder=route_folder,
        subject_id=subject_id,
        trial_id=trial_id,
        labeled=labeled,
        excursions=excursions,
        manual_excursions=manual_excursions,
        offset_col=offset_col,
        labeled_path=paths["labeled"],
        on_route_path=paths["on_route"],
        excursions_path=paths["excursions"],
        status="success",
    )


def run_single(args: argparse.Namespace) -> int:
    route_folder = str(args.route_folder)
    if args.subject_id is None or args.trial_id is None:
        raise ValueError("single mode requires --subject-id and --trial-id")
    subject_id = str(args.subject_id)
    trial_id = str(args.trial_id)

    summary = process_one(args, route_folder, subject_id, trial_id, infer_mapmatched_csv(args))
    template_path = write_manual_override_template(
        Path(args.out_dir) / route_folder,
        route_folder,
        [summary],
    )
    print(f"Wrote labeled CSV: {summary['output_labeled_csv']}")
    print(f"Wrote on-route CSV: {summary['output_on_route_csv']}")
    print(f"Wrote excursions CSV: {summary['output_excursions_csv']}")
    summary_path = output_paths(Path(args.out_dir), route_folder, subject_id, trial_id)["summary"]
    print(f"Wrote summary: {summary_path}")
    print(f"Wrote manual override template: {template_path}")
    if args.debug_html_map:
        debug_path = output_paths(Path(args.out_dir), route_folder, subject_id, trial_id)["debug_map"]
        print(f"Wrote debug HTML map: {debug_path}")
    return 0


def run_batch(args: argparse.Namespace) -> int:
    route_folder = str(args.route_folder)
    input_dir = Path(args.mapmatched_root) / route_folder
    if not input_dir.exists():
        raise FileNotFoundError(f"missing route mapmatched directory: {input_dir}")

    input_files = sorted(input_dir.glob("*_mapmatched.csv"))
    if not input_files:
        raise FileNotFoundError(f"no *_mapmatched.csv files found under: {input_dir}")

    rows: list[dict[str, Any]] = []
    for input_csv in input_files:
        subject_id = ""
        trial_id = ""
        try:
            subject_id, trial_id = parse_subject_trial_from_path(input_csv)
            row = process_one(args, route_folder, subject_id, trial_id, input_csv)
        except Exception as exc:
            if not subject_id or not trial_id:
                try:
                    subject_id, trial_id = parse_subject_trial_from_path(input_csv)
                except Exception:
                    subject_id, trial_id = "", ""
            paths = output_paths(Path(args.out_dir), route_folder, subject_id, trial_id)
            row = build_batch_summary_row(
                route_folder=route_folder,
                subject_id=subject_id,
                trial_id=trial_id,
                labeled=None,
                excursions=None,
                manual_excursions=None,
                offset_col=None,
                labeled_path=paths["labeled"],
                on_route_path=paths["on_route"],
                excursions_path=paths["excursions"],
                status="error",
                error_message=str(exc),
            )
        rows.append(row)

    output_dir = Path(args.out_dir) / route_folder
    output_dir.mkdir(parents=True, exist_ok=True)
    batch_summary = pd.DataFrame(rows)
    batch_summary_path = output_dir / f"{route_folder}_ib3a2_batch_summary.csv"
    batch_summary.to_csv(batch_summary_path, index=False, encoding="utf-8-sig")
    template_path = write_manual_override_template(output_dir, route_folder, rows)

    status_counts = batch_summary["status"].value_counts(dropna=False).to_dict()
    print(f"Processed trials: {len(batch_summary)}")
    print(f"Status counts: {status_counts}")
    print(f"Wrote batch summary: {batch_summary_path}")
    print(f"Wrote manual override template: {template_path}")
    return 0


def run(args: argparse.Namespace) -> int:
    global pd
    pd = importlib.import_module("pandas")

    if args.batch:
        if args.mapmatched_csv:
            raise ValueError("--mapmatched-csv cannot be used with --batch")
        return run_batch(args)
    return run_single(args)


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
