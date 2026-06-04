from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd


ROUTE_CASE_MAP = {
    "juansi_waterfall": "juansi_waterfall_fitcsv_20260503",
    "qixing_lengshuikeng": "qixing_lengshuikeng_main_peak_20260523",
}


OUTPUT_COLUMNS = [
    "route_folder",
    "case_id",
    "subject_id",
    "trial_id",
    "row_index",
    "point_index",
    "activity_id",
    "timestamp_s",
    "elapsed_sec",
    "dt_sec",
    "lat",
    "lon",
    "ele_m",
    "distance_m",
    "heart_rate_bpm",

    # Projection distance: always available when mapmatched.
    "route_dist_m",
    "projected_route_dist_m",
    "nearest_route_dist_m",

    # Reliable progress distance: only valid for trusted on-route progress.
    "reliable_route_dist_m",
    "route_progress_reliable",
    "route_progress_state",
    "route_projection_confidence",
    "route_projection_note",

    "offset_m",
    "segment_id",
    "direction_hint",
    "match_quality",
    "source_file",

    "sequence_match_score",
    "candidate_rank",
    "route_dist_delta_m",
    "reliable_route_dist_delta_m",
    "implied_route_speed_mps",
    "sequence_jump_guard_flag",
    "sequence_branch_ambiguity_flag",
    "summit_dist_m",
    "summit_reached_flag",
    "candidate_phase",
    "summit_transition_lock_applied",
    "summit_transition_release_flag",
]

SUMMARY_COLUMNS = [
    "route_folder",
    "case_id",
    "subject_id",
    "trial_id",
    "activity_id",
    "rows_input",
    "rows_matched",
    "match_ratio",
    "old_route_dist_jump_count",
    "new_route_dist_jump_count",
    "old_speed_impossible_jump_count",
    "new_speed_impossible_jump_count",
    "old_offset_m_mean",
    "new_offset_m_mean",
    "old_offset_m_p95",
    "new_offset_m_p95",
    "offset_mean_delta_m",
    "offset_p95_delta_m",
    "sequence_jump_guard_count",
    "sequence_branch_ambiguity_count",
    "route_progress_reliable_count",
    "route_progress_reliable_ratio",
    "route_progress_state_counts",
    "status",
    "error",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sequence-constrained ib3a mapmatching for standardized activity CSVs.")
    parser.add_argument("--manifest-csv", default="outputs/activity_standardized/activity_standardized_manifest.csv")
    parser.add_argument("--standardized-root", default="outputs/activity_standardized")
    parser.add_argument("--route-profile-root", default="outputs/ib1_route_profile")
    parser.add_argument("--old-mapmatched-root", default="outputs/ib3a_mapmatched_standardized_activity")
    parser.add_argument("--out-dir", default="outputs/ib3a_sequence_mapmatched_activity")
    parser.add_argument("--route-folder", default="", help="Optional route folder filter.")
    parser.add_argument(
        "--case-id",
        default="",
        help="Optional case id override. When set, this takes precedence over ROUTE_CASE_MAP.",
    )
    parser.add_argument("--activity-ids", default="", help="Comma-separated activity ids like 37_1,33_1.")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--segment-m", type=float, default=20.0)
    parser.add_argument("--off-route-m", type=float, default=50.0)
    parser.add_argument(
        "--reliable-offset-m",
        type=float,
        default=25.0,
        help="Maximum offset for a route progress point to be considered reliable.",
    )
    parser.add_argument(
        "--low-confidence-offset-m",
        type=float,
        default=50.0,
        help="Offset above this value is treated as projection-only.",
    )
    parser.add_argument("--continuity-weight", type=float, default=0.20)
    parser.add_argument("--short-dt-sec", type=float, default=5.0)
    parser.add_argument("--jump-dist-m", type=float, default=50.0)
    parser.add_argument("--speed-limit-mps", type=float, default=3.0)
    parser.add_argument("--negative-jump-m", type=float, default=30.0)
    parser.add_argument("--impossible-penalty", type=float, default=10_000.0)
    parser.add_argument("--negative-penalty", type=float, default=2_000.0)

    # summit-lock-window-m:
    # 偵測是否已到山頂附近。

    # summit-release-delta-m:
    # 山頂後，距 summit_dist 超過這個距離的 candidate 視為下山側候選。

    # post-summit-wrong-phase-penalty:
    # 攻頂後還貼回上山側就加重罰分。

    # post-summit-descent-bonus:
    # 攻頂後若候選點是下山側，給足夠分數優勢，讓它能克服 route_dist 大跳懲罰。
    
    parser.add_argument(
        "--summit-lock-window-m",
        type=float,
        default=60.0,
        help="Distance window around summit route distance used to detect summit reached.",
    )
    parser.add_argument(
        "--summit-release-delta-m",
        type=float,
        default=120.0,
        help="Candidate distance beyond summit treated as descent-side release candidate.",
    )
    parser.add_argument(
        "--post-summit-wrong-phase-penalty",
        type=float,
        default=5000.0,
        help="Penalty for selecting ascent-side candidates after summit is reached.",
    )
    parser.add_argument(
        "--post-summit-descent-bonus",
        type=float,
        default=1200.0,
        help="Score bonus for selecting descent-side candidates after summit is reached.",
    )
    return parser.parse_args()


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def is_standardized_status(value: Any) -> bool:
    if pd.isna(value):
        return False
    status = str(value).strip().lower()
    return status == "standardized" or status.startswith("standardized_")


def resolve_path(path_like: Any, fallback_root: Path | None = None) -> Path:
    path = Path(str(path_like))
    if path.exists() or path.is_absolute() or fallback_root is None:
        return path
    return fallback_root / path.name


def classify_match_quality(offset_m: float, off_route_m: float) -> str:
    if pd.isna(offset_m):
        return "unmatched"
    if offset_m > off_route_m:
        return "off_route"
    if offset_m <= 10.0:
        return "good"
    if offset_m <= 25.0:
        return "acceptable"
    return "weak"


def classify_route_progress(
    offset_m: float,
    match_quality: str,
    jump_guard: bool,
    branch_ambiguity: bool,
    args: argparse.Namespace,
) -> tuple[bool, str, float, str]:
    """
    Classify whether the projected route distance can be used as reliable route progress.

    route_dist_m / projected_route_dist_m:
        Always keeps the selected mapmatched projection for visualization / debugging.

    reliable_route_dist_m:
        Only available when the projection is close and not branch-ambiguous.
    """
    if pd.isna(offset_m):
        return False, "unmatched", 0.0, "missing_offset"

    mq = str(match_quality).strip().lower()

    # Base confidence from offset.
    confidence = max(0.0, min(1.0, 1.0 - float(offset_m) / max(args.off_route_m, 1e-6)))

    if offset_m > args.off_route_m or mq == "off_route":
        return (
            False,
            "off_route_projection_only",
            confidence,
            "offset_exceeds_off_route_threshold",
        )

    if jump_guard or branch_ambiguity:
        confidence = min(confidence, 0.35)
        return (
            False,
            "branch_ambiguous_projection",
            confidence,
            "sequence_jump_or_branch_ambiguity",
        )

    if offset_m > args.reliable_offset_m or mq == "weak":
        confidence = min(confidence, 0.60)
        return (
            False,
            "near_route_low_confidence",
            confidence,
            "offset_exceeds_reliable_threshold",
        )

    if mq in {"good", "acceptable"}:
        return (
            True,
            "on_route_reliable",
            confidence,
            "reliable_projection",
        )

    return (
        False,
        "near_route_low_confidence",
        confidence,
        f"match_quality_{mq}",
    )


def add_direction_hint(route_dist: pd.Series) -> pd.Series:
    delta = pd.to_numeric(route_dist, errors="coerce").diff()
    hints = np.where(delta > 1.0, "forward", np.where(delta < -1.0, "backtrack", "stationary"))
    if len(hints):
        hints[0] = "start"
    return pd.Series(hints, index=route_dist.index)


def load_route_candidates(route_profile_root: Path, case_id: str) -> dict[str, Any]:
    case_dir = route_profile_root / case_id
    profile_csv = case_dir / f"{case_id}_route_profile.csv"
    profile_points = case_dir / f"{case_id}_route_profile_points.geojson"
    if not profile_csv.exists():
        raise FileNotFoundError(f"missing route profile CSV: {profile_csv}")
    if not profile_points.exists():
        raise FileNotFoundError(f"missing route profile points GeoJSON: {profile_points}")

    profile = pd.read_csv(profile_csv, low_memory=False)
    points = gpd.read_file(profile_points)
    if points.empty:
        raise ValueError(f"route profile points are empty: {profile_points}")
    if points.crs is None:
        points = points.set_crs("EPSG:4326")
    metric_crs = points.estimate_utm_crs()
    points_m = points.to_crs(metric_crs)

    if "dist_m" not in points_m.columns:
        if "dist_m" not in profile.columns:
            raise ValueError("route profile points/profile missing dist_m")
        points_m = points_m.join(profile[["dist_m"]])
    points_m["dist_m"] = pd.to_numeric(points_m["dist_m"], errors="coerce")
    points_m = points_m.dropna(subset=["dist_m"]).sort_values("dist_m").reset_index(drop=True)
    coords = np.array([[geom.x, geom.y] for geom in points_m.geometry], dtype=float)
    dists = points_m["dist_m"].to_numpy(dtype=float)

    summit_dist_m = np.nan
    for ele_col in ["ele_smooth", "ele_gpx_m", "elevation_m", "ele_m"]:
        if ele_col in profile.columns and "dist_m" in profile.columns:
            ele = pd.to_numeric(profile[ele_col], errors="coerce")
            dist = pd.to_numeric(profile["dist_m"], errors="coerce")
            valid = ele.notna() & dist.notna()
            if valid.any():
                summit_dist_m = float(dist.loc[valid].iloc[int(ele.loc[valid].to_numpy().argmax())])
                break

    if not np.isfinite(summit_dist_m):
        summit_dist_m = float(np.nanmedian(dists))

    return {
        "case_id": case_id,
        "metric_crs": metric_crs,
        "coords": coords,
        "dists": dists,
        "summit_dist_m": summit_dist_m,
        "profile_dist_values": np.sort(pd.to_numeric(profile["dist_m"], errors="coerce").dropna().to_numpy(dtype=float)),
    }


def nearest_profile_dist(dist_m: float, profile_dist_values: np.ndarray) -> float:
    idx = int(np.searchsorted(profile_dist_values, dist_m))
    if idx <= 0:
        return float(profile_dist_values[0])
    if idx >= len(profile_dist_values):
        return float(profile_dist_values[-1])
    before = profile_dist_values[idx - 1]
    after = profile_dist_values[idx]
    return float(before if abs(dist_m - before) <= abs(after - dist_m) else after)


def top_k_candidates(point_xy: np.ndarray, route_coords: np.ndarray, route_dists: np.ndarray, top_k: int) -> list[dict[str, float]]:
    delta = route_coords - point_xy
    offset2 = np.einsum("ij,ij->i", delta, delta)
    k = min(top_k, len(offset2))
    idxs = np.argpartition(offset2, k - 1)[:k]
    idxs = idxs[np.argsort(offset2[idxs])]
    return [
        {
            "route_point_index": float(idx),
            "candidate_dist": float(route_dists[idx]),
            "offset_m": float(np.sqrt(offset2[idx])),
            "candidate_rank": float(rank),
        }
        for rank, idx in enumerate(idxs, start=1)
    ]


def candidate_phase(candidate_dist: float, summit_dist_m: float, args: argparse.Namespace) -> str:
    if not np.isfinite(candidate_dist) or not np.isfinite(summit_dist_m):
        return "unknown"
    if candidate_dist < summit_dist_m - args.summit_lock_window_m:
        return "ascent"
    if candidate_dist > summit_dist_m + args.summit_release_delta_m:
        return "descent"
    return "summit_self_near"


def is_descent_release_candidate(candidate_dist: float, summit_dist_m: float, args: argparse.Namespace) -> bool:
    return (
        np.isfinite(candidate_dist)
        and np.isfinite(summit_dist_m)
        and candidate_dist >= summit_dist_m + args.summit_release_delta_m
    )


def is_near_summit_dist(route_dist_m: float, summit_dist_m: float, args: argparse.Namespace) -> bool:
    return (
        np.isfinite(route_dist_m)
        and np.isfinite(summit_dist_m)
        and abs(route_dist_m - summit_dist_m) <= args.summit_lock_window_m
    )


def score_candidate(
    candidate: dict[str, float],
    prev_dist: float | None,
    dt: float,
    args: argparse.Namespace,
    summit_dist_m: float,
    summit_reached: bool,
) -> tuple[float, bool, bool, bool]:
    score = candidate["offset_m"]
    jump_guard = False
    branch_ambiguity = False
    summit_transition_release = False

    if prev_dist is None or not np.isfinite(prev_dist):
        return score, jump_guard, branch_ambiguity, summit_transition_release

    delta = candidate["candidate_dist"] - prev_dist
    abs_delta = abs(delta)
    score += args.continuity_weight * abs_delta

    cand_phase = candidate_phase(candidate["candidate_dist"], summit_dist_m, args)
    summit_transition_release = (
        summit_reached
        and is_near_summit_dist(prev_dist, summit_dist_m, args)
        and is_descent_release_candidate(candidate["candidate_dist"], summit_dist_m, args)
    )

    if summit_reached:
        if cand_phase == "ascent":
            score += args.post_summit_wrong_phase_penalty
        elif cand_phase == "descent":
            score -= args.post_summit_descent_bonus

    if np.isfinite(dt) and dt > 0:
        implied_speed = abs_delta / dt
        if implied_speed > args.speed_limit_mps and not summit_transition_release:
            score += args.impossible_penalty
            jump_guard = True

    if (
        np.isfinite(dt)
        and dt <= args.short_dt_sec
        and abs_delta > args.jump_dist_m
        and not summit_transition_release
    ):
        score += args.impossible_penalty
        jump_guard = True

    if delta < -args.negative_jump_m:
        score += args.negative_penalty
        branch_ambiguity = True

    if summit_transition_release:
        jump_guard = False
        branch_ambiguity = False

    return score, jump_guard, branch_ambiguity, bool(summit_transition_release)


def mapmatch_activity_sequence(
    activity_csv: Path,
    route_folder: str,
    case_id: str,
    route_axis: dict[str, Any],
    args: argparse.Namespace,
) -> pd.DataFrame:
    activity = pd.read_csv(activity_csv, low_memory=False)
    missing = [col for col in ["lat", "lon"] if col not in activity.columns]
    if missing:
        raise ValueError(f"activity CSV missing required columns: {missing}")
    activity["lat"] = pd.to_numeric(activity["lat"], errors="coerce")
    activity["lon"] = pd.to_numeric(activity["lon"], errors="coerce")
    activity = activity.dropna(subset=["lat", "lon"]).copy()
    if activity.empty:
        raise ValueError("activity has no valid lat/lon rows")
    sort_cols = [c for c in ["elapsed_sec", "timestamp_s"] if c in activity.columns]
    if sort_cols:
        activity = activity.sort_values(sort_cols, na_position="last").reset_index(drop=True)

    if "row_index" not in activity.columns:
        activity["row_index"] = range(len(activity))
    if "point_index" not in activity.columns:
        activity["point_index"] = activity["row_index"]

    gdf = gpd.GeoDataFrame(
        activity,
        geometry=gpd.points_from_xy(activity["lon"], activity["lat"]),
        crs="EPSG:4326",
    ).to_crs(route_axis["metric_crs"])

    if "elapsed_sec" in activity.columns:
        elapsed = pd.to_numeric(activity["elapsed_sec"], errors="coerce")
    elif "timestamp_s" in activity.columns:
        elapsed = pd.to_numeric(activity["timestamp_s"], errors="coerce")
    else:
        elapsed = pd.Series(np.nan, index=activity.index)


    chosen = []
    prev_projected_dist: float | None = None
    prev_projected_time: float | None = None
    prev_reliable_dist: float | None = None
    prev_reliable_time: float | None = None
    summit_dist_m = float(route_axis.get("summit_dist_m", np.nan))
    summit_reached = False

    for i, geom in enumerate(gdf.geometry):
        point_xy = np.array([geom.x, geom.y], dtype=float)
        candidates = top_k_candidates(point_xy, route_axis["coords"], route_axis["dists"], args.top_k)
        t = float(elapsed.iloc[i]) if pd.notna(elapsed.iloc[i]) else np.nan

        # Candidate scoring should follow projected trajectory continuity.
        # Reliability is handled later by reliable_route_dist_m / route_progress_state.
        # Do not use prev_reliable_dist here, otherwise off-route gaps may pull
        # self-near / out-and-back sections back to an earlier branch.
        ref_dist = prev_projected_dist
        ref_time = prev_projected_time

        dt_ref = (
            t - ref_time
            if ref_time is not None and np.isfinite(t) and np.isfinite(ref_time)
            else np.nan
        )

        scored = []
        for cand in candidates:
            score, jump_guard, branch_ambiguity, summit_transition_release = score_candidate(
                cand,
                ref_dist,
                dt_ref,
                args,
                summit_dist_m,
                summit_reached,
            )
            scored.append((score, jump_guard, branch_ambiguity, summit_transition_release, cand))
        score, jump_guard, branch_ambiguity, summit_transition_release, cand = min(scored, key=lambda x: x[0])

        projected_route_dist = cand["candidate_dist"]
        nearest_route_dist = nearest_profile_dist(projected_route_dist, route_axis["profile_dist_values"])
        offset_m = cand["offset_m"]
        match_quality = classify_match_quality(offset_m, args.off_route_m)

        route_delta = (
            projected_route_dist - prev_projected_dist
            if prev_projected_dist is not None and np.isfinite(prev_projected_dist)
            else np.nan
        )

        reliable_delta = (
            projected_route_dist - prev_reliable_dist
            if prev_reliable_dist is not None and np.isfinite(prev_reliable_dist)
            else np.nan
        )

        implied_speed = (
            abs(route_delta) / (t - prev_projected_time)
            if (
                np.isfinite(route_delta)
                and prev_projected_time is not None
                and np.isfinite(t)
                and np.isfinite(prev_projected_time)
                and (t - prev_projected_time) > 0
            )
            else np.nan
        )

        (
            route_progress_reliable,
            route_progress_state,
            route_projection_confidence,
            route_projection_note,
        ) = classify_route_progress(
            offset_m=offset_m,
            match_quality=match_quality,
            jump_guard=bool(jump_guard),
            branch_ambiguity=bool(branch_ambiguity),
            args=args,
        )

        reliable_route_dist = projected_route_dist if route_progress_reliable else np.nan
        cand_phase = candidate_phase(projected_route_dist, summit_dist_m, args)
        summit_transition_lock_applied = False

        if (
            not summit_reached
            and route_progress_reliable
            and is_near_summit_dist(projected_route_dist, summit_dist_m, args)
            and offset_m <= args.reliable_offset_m
        ):
            summit_reached = True
            summit_transition_lock_applied = True

        chosen.append(
            {
                # Backward-compatible projection columns.
                "route_dist_m": projected_route_dist,
                "projected_route_dist_m": projected_route_dist,
                "nearest_route_dist_m": nearest_route_dist,

                # New route-progress semantic columns.
                "reliable_route_dist_m": reliable_route_dist,
                "route_progress_reliable": bool(route_progress_reliable),
                "route_progress_state": route_progress_state,
                "route_projection_confidence": route_projection_confidence,
                "route_projection_note": route_projection_note,

                "offset_m": offset_m,
                "match_quality": match_quality,
                "sequence_match_score": score,
                "candidate_rank": int(cand["candidate_rank"]),
                "route_dist_delta_m": route_delta,
                "reliable_route_dist_delta_m": reliable_delta,
                "implied_route_speed_mps": implied_speed,
                "sequence_jump_guard_flag": bool(jump_guard),
                "sequence_branch_ambiguity_flag": bool(branch_ambiguity),
                "summit_dist_m": summit_dist_m,
                "summit_reached_flag": bool(summit_reached),
                "candidate_phase": cand_phase,
                "summit_transition_lock_applied": bool(summit_transition_lock_applied),
                "summit_transition_release_flag": bool(summit_transition_release),
            }
        )

        # Always update projected state for debugging / raw projection continuity.
        prev_projected_dist = projected_route_dist
        prev_projected_time = t if np.isfinite(t) else prev_projected_time

        # Only reliable points update route-progress state.
        if route_progress_reliable:
            prev_reliable_dist = projected_route_dist
            prev_reliable_time = t if np.isfinite(t) else prev_reliable_time

    out = activity.copy()
    for key in chosen[0].keys():
        out[key] = [row[key] for row in chosen]
    out["route_folder"] = route_folder
    out["case_id"] = case_id
    out["segment_id"] = np.floor(pd.to_numeric(out["route_dist_m"], errors="coerce") / args.segment_m).astype("Int64")
    out["direction_hint"] = add_direction_hint(out["route_dist_m"])

    if "match_quality" not in out.columns or out["match_quality"].isna().all():
        out["match_quality"] = [
            classify_match_quality(offset, args.off_route_m)
            for offset in out["offset_m"]
        ]
        
    for col in OUTPUT_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA
    return out[OUTPUT_COLUMNS]


def jump_count(df: pd.DataFrame, dist_col: str = "route_dist_m") -> int:
    delta = pd.to_numeric(df[dist_col], errors="coerce").diff().abs()
    return int((delta > 50.0).sum())


def impossible_speed_count(df: pd.DataFrame, dist_col: str = "route_dist_m") -> int:
    if "elapsed_sec" in df.columns:
        t = pd.to_numeric(df["elapsed_sec"], errors="coerce")
    elif "timestamp_s" in df.columns:
        t = pd.to_numeric(df["timestamp_s"], errors="coerce")
    else:
        return 0
    dt = t.diff()
    speed = pd.to_numeric(df[dist_col], errors="coerce").diff().abs() / dt.where(dt > 0)
    return int((speed > 3.0).sum())


def summarize_result(
    row: pd.Series,
    case_id: str,
    result: pd.DataFrame | None,
    old: pd.DataFrame | None,
    status: str,
    error: str = "",
) -> dict[str, Any]:
    if result is None or result.empty:
        return {
            "route_folder": row.get("route_folder"),
            "case_id": case_id,
            "subject_id": row.get("subject_id"),
            "trial_id": row.get("trial_id"),
            "activity_id": f"{row.get('subject_id')}_{row.get('trial_id')}",
            "rows_input": int(row.get("rows_valid", 0) or 0),
            "rows_matched": 0,
            "match_ratio": 0.0,
            "old_route_dist_jump_count": pd.NA,
            "new_route_dist_jump_count": pd.NA,
            "old_speed_impossible_jump_count": pd.NA,
            "new_speed_impossible_jump_count": pd.NA,
            "old_offset_m_mean": pd.NA,
            "new_offset_m_mean": pd.NA,
            "old_offset_m_p95": pd.NA,
            "new_offset_m_p95": pd.NA,
            "offset_mean_delta_m": pd.NA,
            "offset_p95_delta_m": pd.NA,
            "sequence_jump_guard_count": pd.NA,
            "sequence_branch_ambiguity_count": pd.NA,
            "route_progress_reliable_count": pd.NA,
            "route_progress_reliable_ratio": pd.NA,
            "route_progress_state_counts": "",
            "status": status,
            "error": error,
        }

    old_offset_mean = (
        float(old["offset_m"].mean())
        if old is not None
        and "offset_m" in old
        and old["offset_m"].notna().any()
        else np.nan
    )
    old_offset_p95 = (
        float(old["offset_m"].quantile(0.95))
        if old is not None
        and "offset_m" in old
        and old["offset_m"].notna().any()
        else np.nan
    )
    new_offset_mean = (
        float(result["offset_m"].mean())
        if "offset_m" in result
        and result["offset_m"].notna().any()
        else np.nan
    )
    new_offset_p95 = (
        float(result["offset_m"].quantile(0.95))
        if "offset_m" in result
        and result["offset_m"].notna().any()
        else np.nan
    )

    if "route_progress_reliable" in result.columns:
        reliable_series = result["route_progress_reliable"].astype(bool)
        route_progress_reliable_count = int(reliable_series.sum())
        route_progress_reliable_ratio = float(reliable_series.mean())
    else:
        route_progress_reliable_count = pd.NA
        route_progress_reliable_ratio = pd.NA

    if "route_progress_state" in result.columns:
        route_progress_state_counts = "; ".join(
            f"{k}={v}"
            for k, v in result["route_progress_state"]
            .value_counts(dropna=False)
            .to_dict()
            .items()
        )
    else:
        route_progress_state_counts = ""

    return {
        "route_folder": row.get("route_folder"),
        "case_id": case_id,
        "subject_id": row.get("subject_id"),
        "trial_id": row.get("trial_id"),
        "activity_id": f"{int(row.get('subject_id'))}_{int(row.get('trial_id'))}",
        "rows_input": len(result),
        "rows_matched": int(result["route_dist_m"].notna().sum()),
        "match_ratio": float(result["route_dist_m"].notna().mean()),
        "old_route_dist_jump_count": (
            jump_count(old) if old is not None and not old.empty else np.nan
        ),
        "new_route_dist_jump_count": jump_count(result),
        "old_speed_impossible_jump_count": (
            impossible_speed_count(old) if old is not None and not old.empty else np.nan
        ),
        "new_speed_impossible_jump_count": impossible_speed_count(result),
        "old_offset_m_mean": old_offset_mean,
        "new_offset_m_mean": new_offset_mean,
        "old_offset_m_p95": old_offset_p95,
        "new_offset_m_p95": new_offset_p95,
        "offset_mean_delta_m": (
            new_offset_mean - old_offset_mean
            if np.isfinite(old_offset_mean) and np.isfinite(new_offset_mean)
            else np.nan
        ),
        "offset_p95_delta_m": (
            new_offset_p95 - old_offset_p95
            if np.isfinite(old_offset_p95) and np.isfinite(new_offset_p95)
            else np.nan
        ),
        "sequence_jump_guard_count": int(result["sequence_jump_guard_flag"].sum()),
        "sequence_branch_ambiguity_count": int(result["sequence_branch_ambiguity_flag"].sum()),
        "route_progress_reliable_count": route_progress_reliable_count,
        "route_progress_reliable_ratio": route_progress_reliable_ratio,
        "route_progress_state_counts": route_progress_state_counts,
        "status": status,
        "error": error,
    }


def run(args: argparse.Namespace) -> int:
    manifest = pd.read_csv(args.manifest_csv, low_memory=False)
    selected = manifest[
        manifest["status"].map(is_standardized_status)
        & manifest["usable_for_time_model"].map(as_bool)
    ].copy()
    if args.route_folder:
        selected = selected[selected["route_folder"].astype(str) == args.route_folder]
    if args.activity_ids:
        ids = {item.strip() for item in args.activity_ids.split(",") if item.strip()}
        selected = selected[
            selected.apply(lambda r: f"{int(r['subject_id'])}_{int(r['trial_id'])}" in ids, axis=1)
        ].copy()

    standardized_root = Path(args.standardized_root)
    route_profile_root = Path(args.route_profile_root)
    old_root = Path(args.old_mapmatched_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    route_axes: dict[str, dict[str, Any]] = {}
    summary_rows = []
    for _, row in selected.iterrows():
        route_folder = str(row["route_folder"])
        case_id = str(args.case_id).strip() or ROUTE_CASE_MAP.get(route_folder)
        subject_id = str(int(row["subject_id"])) if pd.notna(row["subject_id"]) else ""
        trial_id = int(row["trial_id"]) if pd.notna(row["trial_id"]) else 1
        activity_id = f"{subject_id}_{trial_id}"
        try:
            if case_id is None:
                raise ValueError(f"no case_id mapping for {route_folder}")
            if case_id not in route_axes:
                route_axes[case_id] = load_route_candidates(route_profile_root, case_id)
            activity_csv = resolve_path(row["output_file"], standardized_root / route_folder)
            if not activity_csv.exists():
                raise FileNotFoundError(f"missing standardized activity CSV: {activity_csv}")
            result = mapmatch_activity_sequence(activity_csv, route_folder, case_id, route_axes[case_id], args)
            route_out_dir = out_dir / route_folder
            route_out_dir.mkdir(parents=True, exist_ok=True)
            out_csv = route_out_dir / f"{activity_id}_mapmatched.csv"
            result.to_csv(out_csv, index=False, encoding="utf-8-sig")

            old_csv = old_root / route_folder / f"{activity_id}_mapmatched.csv"
            old = pd.read_csv(old_csv, low_memory=False) if old_csv.exists() else None
            summary_rows.append(summarize_result(row, case_id, result, old, "sequence_mapmatched"))
            print(f"wrote {out_csv}")
        except Exception as exc:
            summary_rows.append(summarize_result(row, case_id or "", None, None, "error", str(exc)))
            print(f"error {activity_id}: {exc}")

    summary = pd.DataFrame(summary_rows)
    for col in SUMMARY_COLUMNS:
        if col not in summary.columns:
            summary[col] = pd.NA
    summary = summary[SUMMARY_COLUMNS]
    summary_path = out_dir / "ib3a_sequence_batch_mapmatch_summary.csv"
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    print(f"Selected standardized activities: {len(selected)}")
    print(f"Wrote summary: {summary_path}")
    print(summary[["activity_id", "old_route_dist_jump_count", "new_route_dist_jump_count", "old_speed_impossible_jump_count", "new_speed_impossible_jump_count", "old_offset_m_mean", "new_offset_m_mean", "old_offset_m_p95", "new_offset_m_p95", "status"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
