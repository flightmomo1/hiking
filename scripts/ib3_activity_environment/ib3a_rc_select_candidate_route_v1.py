"""IB3A-RC v1d3 prototype: add segment review-density classification.

This review-only prototype exports candidate-way proximity, raw-point refit
evidence, and conservative training-use policy labels. It does not assemble a
complete route, classify route choice, modify IB3A2/IB3F, or produce a final
training-ready dataset.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


CONTRACT_VERSION = "ib3a_rc_candidate_selection_v1d3_segment_review_density_prototype"

STABILITY_WINDOW_SEC = 30.0
SWITCH_WINDOW_SEC = 60.0
RAW_PAUSE_SPEED_MPS = 0.10
STALL_ROUTE_RANGE_M = 5.0
REVERSAL_DELTA_M = -10.0
JUMP_DELTA_M = 50.0
HIGH_SWITCH_COUNT = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--route-folder", required=True)
    parser.add_argument("--activity-id", required=True)
    parser.add_argument("--standardized-csv", required=True)
    parser.add_argument("--candidate-route-points-csv", required=True)
    parser.add_argument("--candidate-way-pool-csv", required=True)
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def require_file(path: Path, label: str) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    return path


def bool_series(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.lower().isin(["true", "1", "yes", "y"])


def quantile_or_null(values: np.ndarray, q: float) -> float | None:
    clean = values[np.isfinite(values)]
    return float(np.quantile(clean, q)) if clean.size else None


def label_candidate_context(row: pd.Series) -> tuple[str, str, bool, str, str]:
    distance = pd.to_numeric(pd.Series([row.get("nearest_distance_m")]), errors="coerce").iloc[0]
    selected = bool(row.get("nearest_selected_from_ib0", False))
    route_role = str(row.get("nearest_route_role", "")).strip().lower()
    highway = str(row.get("nearest_highway_norm", "")).strip().lower()

    if pd.isna(distance) or distance > 30.0:
        return (
            "LOW_CONFIDENCE_CANDIDATE",
            "low",
            True,
            "nearest_distance_gt_30m_or_missing",
            "EXCLUDE_LOW_CONFIDENCE",
        )
    if distance <= 10.0 and selected and route_role == "trail_core":
        return (
            "MAINLINE_LIKELY",
            "high",
            False,
            "",
            "TRAINING_OK_MAINLINE",
        )
    if distance <= 10.0 and route_role == "trail_core" and not selected:
        return (
            "BRANCH_OR_SIDE_TRAIL_LIKELY",
            "medium",
            True,
            "near_unselected_trail_core_candidate",
            "EXCLUDE_FROM_MAINLINE_TRAINING_KEEP_FOR_REVIEW",
        )
    if (
        distance <= 10.0
        and selected
        and (highway in {"service", "tertiary"} or route_role == "approach_or_road")
        and not bool(row.get("rc_terminal_segment", False))
    ):
        return (
            "MAINLINE_CONNECTOR_LIKELY",
            "medium_high",
            False,
            "",
            "TRAINING_OK_ROUTE_CONNECTOR",
        )
    if highway in {"service", "tertiary"} or route_role == "approach_or_road":
        return (
            "APPROACH_OR_ROAD",
            "medium",
            True,
            "nearest_candidate_is_terminal_or_unresolved_approach_or_road",
            "EXCLUDE_APPROACH_TERMINAL_KEEP_FOR_REVIEW",
        )
    if 10.0 < distance <= 30.0:
        return (
            "LOW_CONFIDENCE_CANDIDATE",
            "medium_low",
            True,
            "nearest_distance_between_10m_and_30m",
            "EXCLUDE_LOW_CONFIDENCE",
        )
    return (
        "AMBIGUOUS_MULTI_CANDIDATE",
        "low",
        True,
        "candidate_context_not_resolved_by_v1b_rules",
        "EXCLUDE_AMBIGUOUS",
    )


def local_xy(lat: np.ndarray, lon: np.ndarray, lat0: float, lon0: float) -> tuple[np.ndarray, np.ndarray]:
    cos_lat = math.cos(math.radians(lat0))
    x = (lon - lon0) * 111_320.0 * cos_lat
    y = (lat - lat0) * 110_540.0
    return x, y


def inverse_local_xy(x: np.ndarray, y: np.ndarray, lat0: float, lon0: float) -> tuple[np.ndarray, np.ndarray]:
    cos_lat = math.cos(math.radians(lat0))
    lat = lat0 + y / 110_540.0
    lon = lon0 + x / (111_320.0 * cos_lat)
    return lat, lon


def add_stability_evidence(refit: pd.DataFrame) -> pd.DataFrame:
    out = refit.copy()
    elapsed = pd.to_numeric(out.get("elapsed_sec"), errors="coerce")
    lat = pd.to_numeric(out["lat"], errors="coerce").to_numpy(float)
    lon = pd.to_numeric(out["lon"], errors="coerce").to_numpy(float)
    route_dist = pd.to_numeric(out["nearest_route_dist_m"], errors="coerce").to_numpy(float)
    selected = out["nearest_selected_from_ib0"].fillna(False).astype(bool).to_numpy()
    way = out["nearest_candidate_way_id"].fillna("").astype(str).to_numpy()

    terminal = np.full(len(out), "none", dtype=object)
    fraction = pd.to_numeric(out["rc_elapsed_fraction"], errors="coerce").to_numpy(float)
    terminal[fraction <= 0.05] = "start_terminal"
    terminal[fraction >= 0.95] = "end_terminal"
    out["terminal_zone"] = terminal

    raw_step_m = np.full(len(out), np.nan)
    delta_sec = np.full(len(out), np.nan)
    if len(out) > 1:
        lat_mid = np.radians((lat[1:] + lat[:-1]) / 2.0)
        dx = np.radians(lon[1:] - lon[:-1]) * 6_371_000.0 * np.cos(lat_mid)
        dy = np.radians(lat[1:] - lat[:-1]) * 6_371_000.0
        raw_step_m[1:] = np.sqrt(dx * dx + dy * dy)
        elapsed_np = elapsed.to_numpy(float)
        delta_sec[1:] = elapsed_np[1:] - elapsed_np[:-1]
    raw_speed = np.divide(
        raw_step_m,
        delta_sec,
        out=np.full(len(out), np.nan),
        where=np.isfinite(delta_sec) & (delta_sec > 0),
    )
    route_delta = np.full(len(out), np.nan)
    route_delta[1:] = route_dist[1:] - route_dist[:-1]
    way_switch = np.zeros(len(out), dtype=bool)
    way_switch[1:] = way[1:] != way[:-1]
    continuous_selected = np.zeros(len(out), dtype=bool)
    continuous_selected[1:] = selected[1:] & selected[:-1]

    route_range = np.full(len(out), np.nan)
    switch_count = np.zeros(len(out), dtype=int)
    left_stability = 0
    left_switch = 0
    elapsed_np = elapsed.to_numpy(float)
    for index in range(len(out)):
        if not np.isfinite(elapsed_np[index]):
            continue
        while (
            left_stability < index
            and elapsed_np[index] - elapsed_np[left_stability] > STABILITY_WINDOW_SEC
        ):
            left_stability += 1
        window_route = route_dist[left_stability : index + 1]
        finite_route = window_route[np.isfinite(window_route)]
        if finite_route.size:
            route_range[index] = float(finite_route.max() - finite_route.min())
        while left_switch < index and elapsed_np[index] - elapsed_np[left_switch] > SWITCH_WINDOW_SEC:
            left_switch += 1
        switch_count[index] = int(way_switch[left_switch : index + 1].sum())

    raw_pause = np.isfinite(raw_speed) & (raw_speed <= RAW_PAUSE_SPEED_MPS)
    reversal = (
        np.isfinite(route_delta)
        & (route_delta < REVERSAL_DELTA_M)
        & (~way_switch)
        & continuous_selected
    )
    jump = (
        np.isfinite(route_delta)
        & (np.abs(route_delta) > JUMP_DELTA_M)
        & (~way_switch)
    )
    route_stall = (
        (terminal == "none")
        & (~raw_pause)
        & np.isfinite(route_range)
        & (route_range < STALL_ROUTE_RANGE_M)
    )
    pause = raw_pause | route_stall
    excessive_switch = (terminal == "none") & (switch_count >= HIGH_SWITCH_COUNT)
    movement_review = ((reversal | jump) & (~pause)) | excessive_switch

    reasons: list[str] = []
    for index in range(len(out)):
        row_reasons = []
        if reversal[index] and not pause[index]:
            row_reasons.append("route_dist_reversal")
        if jump[index] and not pause[index]:
            row_reasons.append("route_dist_jump")
        if excessive_switch[index]:
            row_reasons.append("high_candidate_way_switch_count_60s")
        reasons.append(";".join(row_reasons))

    out["raw_step_m"] = raw_step_m
    out["raw_speed_estimated_mps"] = raw_speed
    out["route_dist_delta_m_v1d"] = route_delta
    out["route_dist_range_30s_m"] = route_range
    out["candidate_way_switch_count_60s"] = switch_count
    out["pause_or_stall_flag"] = pause
    out["route_dist_reversal_flag"] = reversal
    out["route_dist_jump_flag"] = jump
    out["route_dist_stall_flag"] = route_stall
    out["candidate_way_switch_flag"] = way_switch
    out["movement_review_required"] = movement_review
    out["movement_review_reason"] = reasons
    return out


def dominant_value(segment: pd.DataFrame, column: str) -> str:
    mode = segment[column].fillna("").astype(str).mode()
    return str(mode.iloc[0]) if len(mode) else ""


def policy_family(policy: str) -> str:
    return "exclude" if str(policy).startswith("EXCLUDE_") else "training"


def max_continuous_review_duration_sec(segment: pd.DataFrame) -> float:
    elapsed = pd.to_numeric(segment.get("elapsed_sec"), errors="coerce")
    review = segment["movement_review_required"].astype(bool).to_numpy()
    maximum = 0.0
    start: int | None = None
    for index, flagged in enumerate(review):
        if flagged and start is None:
            start = index
        if start is not None and (not flagged or index == len(review) - 1):
            end = index if flagged and index == len(review) - 1 else index - 1
            start_elapsed = elapsed.iloc[start]
            end_elapsed = elapsed.iloc[end]
            if pd.notna(start_elapsed) and pd.notna(end_elapsed):
                maximum = max(maximum, float(end_elapsed - start_elapsed))
            start = None
    return maximum


def summarize_context_segment(segment: pd.DataFrame, segment_id: int) -> dict[str, Any]:
    elapsed = pd.to_numeric(segment.get("elapsed_sec"), errors="coerce")
    distance = pd.to_numeric(segment["nearest_distance_m"], errors="coerce")
    route_dist = pd.to_numeric(segment["nearest_route_dist_m"], errors="coerce")
    reasons = sorted(
        {
            reason
            for value in segment["movement_review_reason"].fillna("").astype(str)
            for reason in value.split(";")
            if reason
        }
    )
    context = dominant_value(segment, "candidate_context")
    policy = dominant_value(segment, "training_use_policy")
    duration = float(elapsed.max() - elapsed.min()) if elapsed.notna().any() else 0.0
    reversal_count = int(segment["route_dist_reversal_flag"].astype(bool).sum())
    jump_count = int(segment["route_dist_jump_flag"].astype(bool).sum())
    median_distance = float(distance.median()) if distance.notna().any() else None
    review_points_n = int(segment["movement_review_required"].astype(bool).sum())
    review_point_ratio = float(review_points_n / len(segment)) if len(segment) else 0.0
    continuous_review_duration = max_continuous_review_duration_sec(segment)
    review_event_types = list(reasons)
    review_required = False
    segment_review_level = "none"
    exclusion_policy = policy_family(policy) == "exclude"
    strong_movement_evidence = bool(
        review_points_n > 0
        and (
            review_point_ratio >= 0.10
            or continuous_review_duration >= 10.0
            or jump_count > 0
        )
    )
    sparse_mainline_evidence = bool(
        review_points_n > 0
        and context in {"MAINLINE_LIKELY", "MAINLINE_CONNECTOR_LIKELY"}
        and policy.startswith("TRAINING_OK_")
        and review_points_n <= 3
        and review_point_ratio < 0.05
        and jump_count == 0
        and median_distance is not None
        and median_distance < 10.0
    )

    if strong_movement_evidence:
        segment_review_level = "review_segment"
        review_required = True
        if exclusion_policy:
            reasons = sorted(set(reasons + [f"exclusion_policy_review:{policy}"]))
    elif sparse_mainline_evidence:
        segment_review_level = "evidence_only"
        review_required = False
        isolated_reasons = review_event_types or reasons
        reasons = [f"isolated_{reason}_evidence" for reason in isolated_reasons]
    elif exclusion_policy:
        segment_review_level = "evidence_only"
        review_required = False
        reasons = sorted(set(reasons + [f"exclusion_policy_evidence:{policy}"]))
    elif review_points_n > 0:
        segment_review_level = "evidence_only"
        review_required = False

    return {
        "segment_id": segment_id,
        "start_elapsed_sec": float(elapsed.min()) if elapsed.notna().any() else None,
        "end_elapsed_sec": float(elapsed.max()) if elapsed.notna().any() else None,
        "duration_sec": duration,
        "points_n": int(len(segment)),
        "dominant_candidate_context": context,
        "dominant_training_policy": policy,
        "dominant_candidate_way_id": dominant_value(segment, "nearest_candidate_way_id"),
        "candidate_way_switch_count": int(segment["candidate_way_switch_flag"].astype(bool).sum()),
        "median_nearest_distance_m": median_distance,
        "p90_nearest_distance_m": float(distance.quantile(0.90)) if distance.notna().any() else None,
        "route_dist_min_m": float(route_dist.min()) if route_dist.notna().any() else None,
        "route_dist_max_m": float(route_dist.max()) if route_dist.notna().any() else None,
        "route_dist_reversal_count": reversal_count,
        "route_dist_jump_count": jump_count,
        "route_dist_stall_ratio": float(segment["route_dist_stall_flag"].astype(bool).mean()),
        "pause_or_stall_ratio": float(segment["pause_or_stall_flag"].astype(bool).mean()),
        "terminal_zone": dominant_value(segment, "terminal_zone"),
        "review_points_n": review_points_n,
        "review_point_ratio": review_point_ratio,
        "review_event_types": ";".join(review_event_types),
        "continuous_review_evidence_duration_sec": continuous_review_duration,
        "segment_review_level": segment_review_level,
        "review_required": review_required,
        "review_reasons": ";".join(reasons),
        "short_segment_evidence": bool(duration < 10.0 or len(segment) < 5),
    }


def consolidate_context_segments(refit: pd.DataFrame) -> pd.DataFrame:
    if refit.empty:
        return pd.DataFrame()
    movement_review = refit["movement_review_required"].astype(bool)
    jump_flag = refit["route_dist_jump_flag"].astype(bool)
    split = (
        refit["candidate_context"].ne(refit["candidate_context"].shift())
        | refit["training_use_policy"].ne(refit["training_use_policy"].shift())
        | refit["terminal_zone"].ne(refit["terminal_zone"].shift())
        | movement_review.ne(movement_review.shift())
        | jump_flag.ne(jump_flag.shift())
    )
    segment_ids = split.cumsum().astype(int)
    chunks = [segment.copy() for _, segment in refit.groupby(segment_ids, sort=True)]

    changed = True
    while changed and len(chunks) > 1:
        changed = False
        for index, chunk in enumerate(chunks):
            summary = summarize_context_segment(chunk, index + 1)
            single_reversal_noise = (
                summary["points_n"] == 1
                and summary["route_dist_reversal_count"] == 1
                and summary["route_dist_jump_count"] == 0
                and summary["median_nearest_distance_m"] is not None
                and summary["median_nearest_distance_m"] < 10.0
                and summary["dominant_candidate_context"]
                in {"MAINLINE_LIKELY", "MAINLINE_CONNECTOR_LIKELY"}
            )
            short = summary["duration_sec"] < 10.0 or summary["points_n"] < 5
            if not (short or single_reversal_noise):
                continue

            neighbors = [candidate for candidate in (index - 1, index + 1) if 0 <= candidate < len(chunks)]
            if not neighbors:
                continue
            policy = summary["dominant_training_policy"]
            context = summary["dominant_candidate_context"]
            family = policy_family(policy)
            terminal_zone = summary["terminal_zone"]

            exact_policy = [
                candidate
                for candidate in neighbors
                if dominant_value(chunks[candidate], "training_use_policy") == policy
                and dominant_value(chunks[candidate], "terminal_zone") == terminal_zone
            ]
            same_context = [
                candidate
                for candidate in neighbors
                if dominant_value(chunks[candidate], "candidate_context") == context
                and policy_family(dominant_value(chunks[candidate], "training_use_policy")) == family
                and dominant_value(chunks[candidate], "terminal_zone") == terminal_zone
            ]
            compatible = exact_policy or same_context
            if not compatible:
                continue

            target = max(compatible, key=lambda candidate: len(chunks[candidate]))
            if target < index:
                chunks[target] = pd.concat([chunks[target], chunk]).sort_index()
                del chunks[index]
            else:
                chunks[target] = pd.concat([chunk, chunks[target]]).sort_index()
                del chunks[index]
            changed = True
            break

    return pd.DataFrame(
        [summarize_context_segment(chunk, index + 1) for index, chunk in enumerate(chunks)]
    )


def distance_to_polyline(
    point_x: np.ndarray,
    point_y: np.ndarray,
    route_x: np.ndarray,
    route_y: np.ndarray,
    route_dist: np.ndarray,
) -> dict[str, np.ndarray]:
    n = len(point_x)
    if len(route_x) == 0:
        return {
            "distance_m": np.full(n, np.nan),
            "route_dist_m": np.full(n, np.nan),
            "projected_x": np.full(n, np.nan),
            "projected_y": np.full(n, np.nan),
            "segment_index": np.full(n, -1, dtype=int),
        }
    if len(route_x) == 1:
        dx = point_x - route_x[0]
        dy = point_y - route_y[0]
        return {
            "distance_m": np.sqrt(dx * dx + dy * dy),
            "route_dist_m": np.full(n, route_dist[0]),
            "projected_x": np.full(n, route_x[0]),
            "projected_y": np.full(n, route_y[0]),
            "segment_index": np.zeros(n, dtype=int),
        }

    ax = route_x[:-1]
    ay = route_y[:-1]
    bx = route_x[1:]
    by = route_y[1:]
    vx = bx - ax
    vy = by - ay
    length_sq = vx * vx + vy * vy
    length_sq = np.where(length_sq > 0, length_sq, 1.0)
    best_dist_sq = np.full(n, np.inf)
    best_t = np.zeros(n)
    best_segment = np.full(n, -1, dtype=int)

    for segment_index in range(len(ax)):
        wx = point_x - ax[segment_index]
        wy = point_y - ay[segment_index]
        t = np.clip(
            (wx * vx[segment_index] + wy * vy[segment_index]) / length_sq[segment_index],
            0.0,
            1.0,
        )
        projected_x = ax[segment_index] + t * vx[segment_index]
        projected_y = ay[segment_index] + t * vy[segment_index]
        dist_sq = (point_x - projected_x) ** 2 + (point_y - projected_y) ** 2
        improve = dist_sq < best_dist_sq
        best_dist_sq[improve] = dist_sq[improve]
        best_t[improve] = t[improve]
        best_segment[improve] = segment_index

    segment = np.maximum(best_segment, 0)
    projected_x = ax[segment] + best_t * vx[segment]
    projected_y = ay[segment] + best_t * vy[segment]
    projected_route_dist = route_dist[segment] + best_t * (route_dist[segment + 1] - route_dist[segment])
    return {
        "distance_m": np.sqrt(best_dist_sq),
        "route_dist_m": projected_route_dist,
        "projected_x": projected_x,
        "projected_y": projected_y,
        "segment_index": best_segment,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_qa_html(
    *,
    case_id: str,
    route_folder: str,
    activity_id: str,
    activity: pd.DataFrame,
    refit: pd.DataFrame,
    route_points: pd.DataFrame,
    scores: pd.DataFrame,
    segments: pd.DataFrame,
) -> str:
    display_scores = scores.copy()
    majority_context = (
        refit.groupby("nearest_candidate_way_id")["candidate_context"]
        .agg(lambda values: values.value_counts().index[0] if len(values) else "")
        .to_dict()
    )
    majority_policy = (
        refit.groupby("nearest_candidate_way_id")["training_use_policy"]
        .agg(lambda values: values.value_counts().index[0] if len(values) else "")
        .to_dict()
    )
    display_scores["majority_context"] = (
        display_scores["candidate_way_id"].astype(str).map(majority_context).fillna("")
    )
    display_scores["majority_training_policy"] = (
        display_scores["candidate_way_id"].astype(str).map(majority_policy).fillna("")
    )
    top_ids = display_scores.head(20)["candidate_way_id"].astype(str).tolist()
    color_list = [
        "#2563eb", "#dc2626", "#059669", "#9333ea", "#ea580c",
        "#0891b2", "#be123c", "#4f46e5", "#65a30d", "#c026d3",
    ]
    candidates = []
    for index, way_id in enumerate(top_ids):
        rows = route_points[route_points["candidate_way_id"].astype(str) == way_id].sort_values("route_point_index")
        candidates.append(
            {
                "candidate_way_id": way_id,
                "color": color_list[index % len(color_list)],
                "points": rows[["lat", "lon"]].astype(float).to_dict("records"),
            }
        )
    sample_step = max(1, len(activity) // 2500)
    raw_rows = activity.iloc[::sample_step]
    refit_rows = refit.iloc[::sample_step]
    payload = {
        "case_id": case_id,
        "route_folder": route_folder,
        "activity_id": activity_id,
        "raw": raw_rows[["lat", "lon", "elapsed_sec"]].replace({np.nan: None}).to_dict("records"),
        "refit": refit_rows[
            [
                "lat",
                "lon",
                "projected_lat",
                "projected_lon",
                "nearest_candidate_way_id",
                "nearest_distance_m",
                "candidate_context",
                "training_use_policy",
                "movement_review_required",
                "movement_review_reason",
            ]
        ].replace({np.nan: None}).to_dict("records"),
        "candidates": candidates,
        "top_scores": display_scores.head(20).replace({np.nan: None}).to_dict("records"),
        "segments": segments.replace({np.nan: None}).to_dict("records"),
    }
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>IB3A-RC v1d3 review-density QA - {html.escape(activity_id)}</title>
  <style>
    body {{ margin:0; font-family:Arial,sans-serif; color:#172033; background:#f8fafc; }}
    header {{ padding:16px 20px; background:#0f172a; color:white; }}
    header h1 {{ margin:0 0 6px; font-size:21px; }}
    header p {{ margin:3px 0; color:#cbd5e1; }}
    main {{ padding:14px; }}
    .section {{ margin-bottom:20px; padding:14px; border:1px solid #cbd5e1; background:white; }}
    .section h2 {{ margin:0 0 5px; font-size:18px; }}
    .section p {{ margin:4px 0 10px; color:#475569; }}
    svg {{ width:100%; height:560px; border:1px solid #cbd5e1; background:#fff; }}
    .legend {{ display:flex; flex-wrap:wrap; gap:12px; margin:8px 0; font-size:12px; }}
    .legend span::before {{ content:''; display:inline-block; width:11px; height:11px; margin-right:5px; background:var(--c); vertical-align:-1px; }}
    .table-wrap {{ overflow:auto; }}
    table {{ border-collapse:collapse; width:100%; font-size:12px; }}
    th,td {{ border-bottom:1px solid #e2e8f0; padding:6px; text-align:left; white-space:nowrap; }}
    th {{ position:sticky; top:0; background:#f8fafc; }}
    .note {{ font-size:13px; color:#475569; line-height:1.45; }}
  </style>
</head>
<body>
<header>
  <h1>IB3A-RC v1d3 review-density QA - {html.escape(activity_id)}</h1>
  <p>Review-only candidate context labels. No full route assembly or route-choice classification.</p>
</header>
<main>
  <section class="section">
    <h2>1. Raw GPS vs nearest candidate projection</h2>
    <p>檢查 raw GPS 是否完整保留，以及 nearest candidate refit 是否貼近 raw trajectory。</p>
    <div class="legend">
      <span style="--c:#334155">Raw GPS</span>
      <span style="--c:#06b6d4">Nearest candidate projection</span>
      <span style="--c:#7c3aed">Top candidate ways</span>
    </div>
    <svg id="raw-board"></svg>
  </section>
  <section class="section">
    <h2>2. Candidate context view</h2>
    <p>檢查 mainline、road、low-confidence、branch 與 ambiguous 標記在空間上的位置是否合理。</p>
    <div id="context-legend" class="legend"></div>
    <svg id="context-board"></svg>
  </section>
  <section class="section">
    <h2>3. Training policy view</h2>
    <p>檢查哪些點會進入主線訓練，哪些點被排除或保留供人工 review。</p>
    <div id="policy-legend" class="legend"></div>
    <svg id="policy-board"></svg>
  </section>
  <section class="section">
    <h2>Top candidate ways</h2>
    <div id="scores" class="table-wrap"></div>
    <p class="note">Point context and training-use policies are conservative prototype labels, not final training labels.</p>
    <p class="note">This prototype does not modify IB3A2 usable_on_route or IB3F features.</p>
  </section>
  <section class="section">
    <h2>4. Movement review evidence</h2>
    <p>紅點僅表示 stabilization review evidence，不代表 confirmed wrong branch，也不會修改 training policy。</p>
    <div class="legend"><span style="--c:#dc2626">movement_review_required</span></div>
    <svg id="movement-board"></svg>
  </section>
  <section class="section">
    <h2>Candidate context segments</h2>
    <div id="segments" class="table-wrap"></div>
  </section>
</main>
<script>
const D={data}, NS='http://www.w3.org/2000/svg';
const all=[...D.raw,...D.refit.map(p=>({{lat:p.projected_lat,lon:p.projected_lon}})),...D.candidates.flatMap(c=>c.points)];
const valid=all.filter(p=>Number.isFinite(Number(p.lat))&&Number.isFinite(Number(p.lon)));
const lat0=valid.reduce((s,p)=>s+Number(p.lat),0)/valid.length;
const lon0=valid.reduce((s,p)=>s+Number(p.lon),0)/valid.length;
const cos=Math.cos(lat0*Math.PI/180);
function xy(p){{return {{x:(Number(p.lon)-lon0)*111320*cos,y:-(Number(p.lat)-lat0)*110540}}}}
function make(tag,a={{}}){{const e=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(a))e.setAttribute(k,v);return e}}
function attr(ps){{return ps.filter(p=>p.lat!=null&&p.lon!=null).map(p=>{{const q=xy(p);return `${{q.x}},${{q.y}}`}}).join(' ')}}
const q=valid.map(xy), xs=q.map(p=>p.x), ys=q.map(p=>p.y), pad=35;
const viewBox=`${{Math.min(...xs)-pad}} ${{Math.min(...ys)-pad}} ${{Math.max(...xs)-Math.min(...xs)+2*pad}} ${{Math.max(...ys)-Math.min(...ys)+2*pad}}`;
function setupBoard(id){{const svg=document.getElementById(id);svg.setAttribute('viewBox',viewBox);return svg}}
function addCandidateWays(svg, opacity=.28){{
  for(const c of D.candidates){{
    const p=make('polyline',{{points:attr(c.points),fill:'none',stroke:c.color,'stroke-width':2.4,opacity}});
    const t=make('title');t.textContent=c.candidate_way_id;p.appendChild(t);svg.appendChild(p);
  }}
}}
function addRaw(svg, opacity=.65){{svg.appendChild(make('polyline',{{points:attr(D.raw),fill:'none',stroke:'#334155','stroke-width':1.3,opacity}}))}}
function addColoredPoints(svg, field, colors){{
  for(const row of D.refit){{
    if(row.projected_lat==null||row.projected_lon==null) continue;
    const q=xy({{lat:row.projected_lat,lon:row.projected_lon}});
    const circle=make('circle',{{cx:q.x,cy:q.y,r:2.2,fill:colors[row[field]]||'#64748b',opacity:.82}});
    const title=make('title');
    title.textContent=`${{field}}=${{row[field]}}\\nway=${{row.nearest_candidate_way_id}}\\ndistance_m=${{Number(row.nearest_distance_m).toFixed(2)}}`;
    circle.appendChild(title);svg.appendChild(circle);
  }}
}}
function legend(id, colors){{
  document.getElementById(id).innerHTML=Object.entries(colors).map(([k,c])=>`<span style="--c:${{c}}">${{k}}</span>`).join('');
}}
const contextColors={{
  MAINLINE_LIKELY:'#16a34a',
  MAINLINE_CONNECTOR_LIKELY:'#0284c7',
  APPROACH_OR_ROAD:'#f59e0b',
  LOW_CONFIDENCE_CANDIDATE:'#dc2626',
  BRANCH_OR_SIDE_TRAIL_LIKELY:'#7c3aed',
  AMBIGUOUS_MULTI_CANDIDATE:'#64748b'
}};
const policyColors={{
  TRAINING_OK_MAINLINE:'#16a34a',
  TRAINING_OK_ROUTE_CONNECTOR:'#0284c7',
  EXCLUDE_LOW_CONFIDENCE:'#dc2626',
  EXCLUDE_FROM_MAINLINE_TRAINING_KEEP_FOR_REVIEW:'#f59e0b',
  EXCLUDE_AMBIGUOUS:'#64748b'
}};
const rawBoard=setupBoard('raw-board');addCandidateWays(rawBoard,.72);addRaw(rawBoard,.85);
rawBoard.appendChild(make('polyline',{{points:attr(D.refit.map(p=>({{lat:p.projected_lat,lon:p.projected_lon}}))),fill:'none',stroke:'#06b6d4','stroke-width':1.5,'stroke-dasharray':'5 4',opacity:.85}}));
const contextBoard=setupBoard('context-board');addCandidateWays(contextBoard,.18);addRaw(contextBoard,.28);addColoredPoints(contextBoard,'candidate_context',contextColors);
const policyBoard=setupBoard('policy-board');addCandidateWays(policyBoard,.18);addRaw(policyBoard,.28);addColoredPoints(policyBoard,'training_use_policy',policyColors);
const movementBoard=setupBoard('movement-board');addCandidateWays(movementBoard,.18);addRaw(movementBoard,.35);
for(const row of D.refit){{
  if(!row.movement_review_required||row.projected_lat==null||row.projected_lon==null) continue;
  const q=xy({{lat:row.projected_lat,lon:row.projected_lon}});
  const circle=make('circle',{{cx:q.x,cy:q.y,r:2.8,fill:'#dc2626',opacity:.9}});
  const title=make('title');title.textContent=`review=${{row.movement_review_reason}}\\nway=${{row.nearest_candidate_way_id}}\\ndistance_m=${{Number(row.nearest_distance_m).toFixed(2)}}`;
  circle.appendChild(title);movementBoard.appendChild(circle);
}}
legend('context-legend',contextColors);legend('policy-legend',policyColors);
document.getElementById('scores').innerHTML='<table><tr><th>way</th><th>name</th><th>highway_norm</th><th>route_role</th><th>IB0 selected</th><th>within_10m_rows</th><th>median_nearest_distance_m</th><th>p90_nearest_distance_m</th><th>raw_elapsed_min</th><th>raw_elapsed_max</th><th>majority_context</th><th>majority_training_policy</th></tr>'+D.top_scores.map(r=>`<tr><td>${{r.candidate_way_id}}</td><td>${{r.name||''}}</td><td>${{r.highway_norm||''}}</td><td>${{r.route_role||''}}</td><td>${{r.selected_from_ib0}}</td><td>${{r.raw_points_within_10m}}</td><td>${{Number(r.median_distance_m).toFixed(2)}}</td><td>${{Number(r.p90_distance_m).toFixed(2)}}</td><td>${{r.raw_elapsed_min==null?'':Number(r.raw_elapsed_min).toFixed(1)}}</td><td>${{r.raw_elapsed_max==null?'':Number(r.raw_elapsed_max).toFixed(1)}}</td><td>${{r.majority_context||''}}</td><td>${{r.majority_training_policy||''}}</td></tr>`).join('')+'</table>';
document.getElementById('segments').innerHTML='<table><tr><th>segment</th><th>elapsed</th><th>duration</th><th>points</th><th>context</th><th>policy</th><th>way</th><th>switches</th><th>median/p90 offset</th><th>route range</th><th>reversal</th><th>jump</th><th>review points</th><th>review ratio</th><th>continuous review sec</th><th>event types</th><th>review level</th><th>review required</th><th>reasons</th></tr>'+D.segments.map(r=>`<tr><td>${{r.segment_id}}</td><td>${{Number(r.start_elapsed_sec).toFixed(1)}}–${{Number(r.end_elapsed_sec).toFixed(1)}}</td><td>${{Number(r.duration_sec).toFixed(1)}}</td><td>${{r.points_n}}</td><td>${{r.dominant_candidate_context}}</td><td>${{r.dominant_training_policy}}</td><td>${{r.dominant_candidate_way_id}}</td><td>${{r.candidate_way_switch_count}}</td><td>${{Number(r.median_nearest_distance_m).toFixed(2)}} / ${{Number(r.p90_nearest_distance_m).toFixed(2)}}</td><td>${{Number(r.route_dist_min_m).toFixed(1)}}–${{Number(r.route_dist_max_m).toFixed(1)}}</td><td>${{r.route_dist_reversal_count}}</td><td>${{r.route_dist_jump_count}}</td><td>${{r.review_points_n}}</td><td>${{Number(r.review_point_ratio).toFixed(4)}}</td><td>${{Number(r.continuous_review_evidence_duration_sec).toFixed(1)}}</td><td>${{r.review_event_types||''}}</td><td>${{r.segment_review_level}}</td><td>${{r.review_required}}</td><td>${{r.review_reasons||''}}</td></tr>`).join('')+'</table>';
</script>
</body>
</html>"""


def run(args: argparse.Namespace) -> dict[str, Any]:
    standardized_path = require_file(Path(args.standardized_csv), "standardized activity CSV")
    route_points_path = require_file(Path(args.candidate_route_points_csv), "candidate route points CSV")
    way_pool_path = require_file(Path(args.candidate_way_pool_csv), "candidate way pool CSV")

    activity = pd.read_csv(standardized_path)
    route_points = pd.read_csv(route_points_path)
    way_pool = pd.read_csv(way_pool_path)
    required_activity = {"lat", "lon"}
    required_points = {"candidate_way_id", "route_point_index", "route_dist_m", "lat", "lon"}
    if not required_activity.issubset(activity.columns):
        raise KeyError(f"Activity missing columns: {sorted(required_activity - set(activity.columns))}")
    if not required_points.issubset(route_points.columns):
        raise KeyError(f"Candidate points missing columns: {sorted(required_points - set(route_points.columns))}")

    activity["lat"] = pd.to_numeric(activity["lat"], errors="coerce")
    activity["lon"] = pd.to_numeric(activity["lon"], errors="coerce")
    valid_activity = activity["lat"].notna() & activity["lon"].notna()
    activity_valid = activity.loc[valid_activity].copy().reset_index().rename(columns={"index": "raw_point_index"})
    route_points["lat"] = pd.to_numeric(route_points["lat"], errors="coerce")
    route_points["lon"] = pd.to_numeric(route_points["lon"], errors="coerce")
    route_points["route_dist_m"] = pd.to_numeric(route_points["route_dist_m"], errors="coerce")
    route_points["route_point_index"] = pd.to_numeric(route_points["route_point_index"], errors="coerce")

    combined_lat = pd.concat([activity_valid["lat"], route_points["lat"]]).dropna()
    combined_lon = pd.concat([activity_valid["lon"], route_points["lon"]]).dropna()
    lat0 = float(combined_lat.mean())
    lon0 = float(combined_lon.mean())
    point_x, point_y = local_xy(
        activity_valid["lat"].to_numpy(float),
        activity_valid["lon"].to_numpy(float),
        lat0,
        lon0,
    )

    way_meta = way_pool.copy()
    way_meta["selected_from_ib0"] = bool_series(way_meta["selected"])
    way_meta = way_meta.set_index(way_meta["candidate_way_id"].astype(str), drop=False)

    global_distance = np.full(len(activity_valid), np.inf)
    global_way = np.full(len(activity_valid), "", dtype=object)
    global_route_dist = np.full(len(activity_valid), np.nan)
    global_projected_x = np.full(len(activity_valid), np.nan)
    global_projected_y = np.full(len(activity_valid), np.nan)
    score_rows: list[dict[str, Any]] = []

    grouped = route_points.groupby(route_points["candidate_way_id"].astype(str), sort=False)
    for candidate_way_id, rows in grouped:
        rows = rows.sort_values("route_point_index")
        route_x, route_y = local_xy(
            rows["lat"].to_numpy(float),
            rows["lon"].to_numpy(float),
            lat0,
            lon0,
        )
        result = distance_to_polyline(
            point_x,
            point_y,
            route_x,
            route_y,
            rows["route_dist_m"].to_numpy(float),
        )
        distances = result["distance_m"]
        improve = distances < global_distance
        global_distance[improve] = distances[improve]
        global_way[improve] = candidate_way_id
        global_route_dist[improve] = result["route_dist_m"][improve]
        global_projected_x[improve] = result["projected_x"][improve]
        global_projected_y[improve] = result["projected_y"][improve]
        meta = way_meta.loc[candidate_way_id] if candidate_way_id in way_meta.index else {}
        elapsed = pd.to_numeric(activity_valid.get("elapsed_sec"), errors="coerce")
        score_rows.append(
            {
                "case_id": args.case_id,
                "route_folder": args.route_folder,
                "activity_id": args.activity_id,
                "candidate_way_id": candidate_way_id,
                "osm_way_id": rows.iloc[0].get("osm_way_id", ""),
                "raw_points_nearest_count": 0,
                "raw_points_within_5m": int(np.sum(distances <= 5.0)),
                "raw_points_within_10m": int(np.sum(distances <= 10.0)),
                "raw_points_within_20m": int(np.sum(distances <= 20.0)),
                "median_distance_m": quantile_or_null(distances, 0.50),
                "p90_distance_m": quantile_or_null(distances, 0.90),
                "raw_elapsed_min": float(elapsed.min()) if elapsed.notna().any() else None,
                "raw_elapsed_max": float(elapsed.max()) if elapsed.notna().any() else None,
                "candidate_route_dist_min_m": float(rows["route_dist_m"].min()),
                "candidate_route_dist_max_m": float(rows["route_dist_m"].max()),
                "match_score_from_ib0": meta.get("match_score", "") if isinstance(meta, pd.Series) else "",
                "selected_from_ib0": bool(meta.get("selected_from_ib0", False)) if isinstance(meta, pd.Series) else False,
                "highway_norm": meta.get("highway_norm", "") if isinstance(meta, pd.Series) else "",
                "route_role": meta.get("route_role", "") if isinstance(meta, pd.Series) else "",
                "name": meta.get("name", "") if isinstance(meta, pd.Series) else "",
            }
        )

    nearest_counts = pd.Series(global_way).value_counts()
    for row in score_rows:
        row["raw_points_nearest_count"] = int(nearest_counts.get(row["candidate_way_id"], 0))
    scores = pd.DataFrame(score_rows).sort_values(
        ["raw_points_within_10m", "median_distance_m", "match_score_from_ib0"],
        ascending=[False, True, False],
    ).reset_index(drop=True)

    projected_lat, projected_lon = inverse_local_xy(
        global_projected_x,
        global_projected_y,
        lat0,
        lon0,
    )
    refit = activity_valid.copy()
    refit["case_id"] = args.case_id
    refit["candidate_route_selection_version"] = CONTRACT_VERSION
    refit["nearest_candidate_way_id"] = global_way
    refit["nearest_distance_m"] = np.where(np.isfinite(global_distance), global_distance, np.nan)
    refit["nearest_route_dist_m"] = global_route_dist
    refit["projected_lat"] = projected_lat
    refit["projected_lon"] = projected_lon
    refit = refit.merge(
        scores[
            [
                "candidate_way_id",
                "osm_way_id",
                "match_score_from_ib0",
                "selected_from_ib0",
                "highway_norm",
                "route_role",
                "name",
            ]
        ],
        left_on="nearest_candidate_way_id",
        right_on="candidate_way_id",
        how="left",
    )
    refit = refit.rename(
        columns={
            "osm_way_id": "nearest_osm_way_id",
            "match_score_from_ib0": "nearest_match_score",
            "selected_from_ib0": "nearest_selected_from_ib0",
            "highway_norm": "nearest_highway_norm",
            "route_role": "nearest_route_role",
            "name": "nearest_way_name",
        }
    )
    elapsed = pd.to_numeric(refit.get("elapsed_sec"), errors="coerce")
    if elapsed.notna().any() and float(elapsed.max()) > float(elapsed.min()):
        elapsed_fraction = (elapsed - float(elapsed.min())) / (float(elapsed.max()) - float(elapsed.min()))
    else:
        elapsed_fraction = pd.Series(
            np.arange(len(refit), dtype=float) / max(len(refit) - 1, 1),
            index=refit.index,
        )
    refit["rc_elapsed_fraction"] = elapsed_fraction
    refit["rc_terminal_segment"] = (elapsed_fraction <= 0.05) | (elapsed_fraction >= 0.95)
    context_labels = refit.apply(label_candidate_context, axis=1, result_type="expand")
    context_labels.columns = [
        "candidate_context",
        "candidate_confidence",
        "rc_review_required",
        "rc_review_reason",
        "training_use_policy",
    ]
    refit = pd.concat([refit, context_labels], axis=1)
    refit = add_stability_evidence(refit)
    segments = consolidate_context_segments(refit)

    out_dir = Path(args.out_dir) / args.route_folder / args.activity_id
    scores_csv = out_dir / f"{args.route_folder}_{args.activity_id}_candidate_way_scores.csv"
    refit_csv = out_dir / f"{args.route_folder}_{args.activity_id}_candidate_point_stability.csv"
    segments_csv = out_dir / f"{args.route_folder}_{args.activity_id}_candidate_context_segments.csv"
    summary_json = out_dir / f"{args.route_folder}_{args.activity_id}_candidate_selection_summary.json"
    qa_html = out_dir / f"{args.route_folder}_{args.activity_id}_raw_vs_candidate_context_qa.html"
    out_dir.mkdir(parents=True, exist_ok=True)
    scores.to_csv(scores_csv, index=False, encoding="utf-8-sig")
    refit.to_csv(refit_csv, index=False, encoding="utf-8-sig")
    segments.to_csv(segments_csv, index=False, encoding="utf-8-sig")

    finite_distance = global_distance[np.isfinite(global_distance)]
    selected_hit_ratio = (
        float(refit["nearest_selected_from_ib0"].fillna(False).astype(bool).mean()) if len(refit) else 0.0
    )
    context_counts = refit["candidate_context"].value_counts(dropna=False).to_dict()
    policy_counts = refit["training_use_policy"].value_counts(dropna=False).to_dict()
    review_ratio = float(refit["rc_review_required"].astype(bool).mean()) if len(refit) else 0.0
    training_ok_rows = int((refit["training_use_policy"] == "TRAINING_OK_MAINLINE").sum())
    training_ok_connector_rows = int(
        (refit["training_use_policy"] == "TRAINING_OK_ROUTE_CONNECTOR").sum()
    )
    excluded_rows = int(refit["training_use_policy"].astype(str).str.startswith("EXCLUDE_").sum())
    pause_rows = int(refit["pause_or_stall_flag"].astype(bool).sum())
    reversal_rows = int(refit["route_dist_reversal_flag"].astype(bool).sum())
    jump_rows = int(refit["route_dist_jump_flag"].astype(bool).sum())
    switch_rows = int(refit["candidate_way_switch_flag"].astype(bool).sum())
    movement_review_rows = int(refit["movement_review_required"].astype(bool).sum())
    movement_review_ratio = float(
        refit["movement_review_required"].astype(bool).mean()
    ) if len(refit) else 0.0
    review_segments = int(segments["review_required"].astype(bool).sum()) if len(segments) else 0
    evidence_only_segments = (
        int((segments["segment_review_level"] == "evidence_only").sum()) if len(segments) else 0
    )
    review_level_segments = (
        int((segments["segment_review_level"] == "review_segment").sum()) if len(segments) else 0
    )
    terminal_segments = int((segments["terminal_zone"] != "none").sum()) if len(segments) else 0
    top20 = scores.head(20)[
        [
            "candidate_way_id",
            "osm_way_id",
            "raw_points_within_10m",
            "median_distance_m",
            "p90_distance_m",
            "match_score_from_ib0",
            "selected_from_ib0",
            "highway_norm",
            "route_role",
        ]
    ].replace({np.nan: None}).to_dict("records")
    summary = {
        "contract_version": CONTRACT_VERSION,
        "case_id": args.case_id,
        "route_folder": args.route_folder,
        "activity_id": args.activity_id,
        "raw_activity_rows": int(len(activity)),
        "raw_activity_valid_coordinate_rows": int(len(activity_valid)),
        "candidate_ways_total": int(route_points["candidate_way_id"].nunique()),
        "candidate_ways_used": int(pd.Series(global_way[global_way != ""]).nunique()),
        "total_candidate_route_points": int(len(route_points)),
        "nearest_distance_median": quantile_or_null(finite_distance, 0.50),
        "nearest_distance_p90": quantile_or_null(finite_distance, 0.90),
        "selected_from_ib0_nearest_hit_ratio": selected_hit_ratio,
        "raw_points_without_candidate": int(np.sum(global_way == "")) + int((~valid_activity).sum()),
        "candidate_context_distribution": {str(key): int(value) for key, value in context_counts.items()},
        "training_use_policy_distribution": {str(key): int(value) for key, value in policy_counts.items()},
        "rc_review_required_ratio": review_ratio,
        "training_ok_mainline_rows": training_ok_rows,
        "training_ok_route_connector_rows": training_ok_connector_rows,
        "exclude_policy_rows": excluded_rows,
        "stability_evidence": {
            "window_sec": STABILITY_WINDOW_SEC,
            "switch_window_sec": SWITCH_WINDOW_SEC,
            "pause_or_stall_rows": pause_rows,
            "route_dist_reversal_rows": reversal_rows,
            "route_dist_jump_rows": jump_rows,
            "candidate_way_switch_rows": switch_rows,
            "movement_review_required_rows": movement_review_rows,
            "movement_review_required_ratio": movement_review_ratio,
            "segments_n": int(len(segments)),
            "review_segments_n": review_segments,
            "evidence_only_segments_n": evidence_only_segments,
            "review_level_segments_n": review_level_segments,
            "terminal_segments_n": terminal_segments,
        },
        "top_20_candidate_ways": top20,
        "inputs": {
            "standardized_csv": str(standardized_path),
            "candidate_route_points_csv": str(route_points_path),
            "candidate_way_pool_csv": str(way_pool_path),
        },
        "outputs": {
            "candidate_way_scores_csv": str(scores_csv),
            "candidate_point_stability_csv": str(refit_csv),
            "candidate_context_segments_csv": str(segments_csv),
            "candidate_selection_summary_json": str(summary_json),
            "raw_vs_candidate_context_qa_html": str(qa_html),
        },
        "boundaries": [
            "Prototype candidate-way proximity evidence only.",
            "Does not assemble a complete route.",
            "Does not classify route choice.",
            "Does not modify IB3A2 usable_on_route.",
            "Does not modify IB3F.",
            "Does not delete raw activity points.",
            "Context labels are review-only and not confirmed route-choice labels.",
            "Not a final AI training-ready dataset.",
        ],
        "runtime_llm_allowed": False,
    }
    write_json(summary_json, summary)
    qa_html.write_text(
        build_qa_html(
            case_id=args.case_id,
            route_folder=args.route_folder,
            activity_id=args.activity_id,
            activity=activity_valid,
            refit=refit,
            route_points=route_points,
            scores=scores,
            segments=segments,
        ),
        encoding="utf-8",
    )
    return summary


def main() -> int:
    args = parse_args()
    summary = run(args)
    print(f"raw_activity_rows={summary['raw_activity_rows']}")
    print(f"candidate_ways_used={summary['candidate_ways_used']}")
    print(f"total_candidate_route_points={summary['total_candidate_route_points']}")
    print(f"nearest_distance_median={summary['nearest_distance_median']}")
    print(f"nearest_distance_p90={summary['nearest_distance_p90']}")
    print(f"selected_from_ib0_nearest_hit_ratio={summary['selected_from_ib0_nearest_hit_ratio']}")
    print(f"raw_points_without_candidate={summary['raw_points_without_candidate']}")
    print(f"candidate_context_distribution={json.dumps(summary['candidate_context_distribution'], ensure_ascii=False)}")
    print(f"training_use_policy_distribution={json.dumps(summary['training_use_policy_distribution'], ensure_ascii=False)}")
    print(f"rc_review_required_ratio={summary['rc_review_required_ratio']}")
    print(f"training_ok_mainline_rows={summary['training_ok_mainline_rows']}")
    print(f"training_ok_route_connector_rows={summary['training_ok_route_connector_rows']}")
    print(f"exclude_policy_rows={summary['exclude_policy_rows']}")
    for key, value in summary["stability_evidence"].items():
        print(f"{key}={value}")
    print(f"top_20_candidate_ways={json.dumps(summary['top_20_candidate_ways'], ensure_ascii=False)}")
    for key, value in summary["outputs"].items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
