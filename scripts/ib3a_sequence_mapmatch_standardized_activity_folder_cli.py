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
    "activity_id",
    "timestamp_s",
    "elapsed_sec",
    "dt_sec",
    "lat",
    "lon",
    "ele_m",
    "distance_m",
    "heart_rate_bpm",
    "route_dist_m",
    "nearest_route_dist_m",
    "offset_m",
    "segment_id",
    "direction_hint",
    "match_quality",
    "source_file",
    "sequence_match_score",
    "candidate_rank",
    "route_dist_delta_m",
    "implied_route_speed_mps",
    "sequence_jump_guard_flag",
    "sequence_branch_ambiguity_flag",
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
    parser.add_argument("--activity-ids", default="", help="Comma-separated activity ids like 37_1,33_1.")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--segment-m", type=float, default=20.0)
    parser.add_argument("--off-route-m", type=float, default=50.0)
    parser.add_argument("--continuity-weight", type=float, default=0.20)
    parser.add_argument("--short-dt-sec", type=float, default=5.0)
    parser.add_argument("--jump-dist-m", type=float, default=50.0)
    parser.add_argument("--speed-limit-mps", type=float, default=3.0)
    parser.add_argument("--negative-jump-m", type=float, default=30.0)
    parser.add_argument("--impossible-penalty", type=float, default=10_000.0)
    parser.add_argument("--negative-penalty", type=float, default=2_000.0)
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
    return {
        "case_id": case_id,
        "metric_crs": metric_crs,
        "coords": coords,
        "dists": dists,
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


def score_candidate(candidate: dict[str, float], prev_dist: float | None, dt: float, args: argparse.Namespace) -> tuple[float, bool, bool]:
    score = candidate["offset_m"]
    jump_guard = False
    branch_ambiguity = False
    if prev_dist is None or not np.isfinite(prev_dist):
        return score, jump_guard, branch_ambiguity

    delta = candidate["candidate_dist"] - prev_dist
    abs_delta = abs(delta)
    score += args.continuity_weight * abs_delta
    if np.isfinite(dt) and dt > 0:
        implied_speed = abs_delta / dt
        if implied_speed > args.speed_limit_mps:
            score += args.impossible_penalty
            jump_guard = True
    if np.isfinite(dt) and dt <= args.short_dt_sec and abs_delta > args.jump_dist_m:
        score += args.impossible_penalty
        jump_guard = True
    if delta < -args.negative_jump_m:
        score += args.negative_penalty
        branch_ambiguity = True
    return score, jump_guard, branch_ambiguity


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
    prev_dist: float | None = None
    prev_time: float | None = None
    for i, geom in enumerate(gdf.geometry):
        point_xy = np.array([geom.x, geom.y], dtype=float)
        candidates = top_k_candidates(point_xy, route_axis["coords"], route_axis["dists"], args.top_k)
        t = float(elapsed.iloc[i]) if pd.notna(elapsed.iloc[i]) else np.nan
        dt = t - prev_time if prev_time is not None and np.isfinite(t) and np.isfinite(prev_time) else np.nan

        scored = []
        for cand in candidates:
            score, jump_guard, branch_ambiguity = score_candidate(cand, prev_dist, dt, args)
            scored.append((score, jump_guard, branch_ambiguity, cand))
        score, jump_guard, branch_ambiguity, cand = min(scored, key=lambda x: x[0])
        route_dist = cand["candidate_dist"]
        route_delta = route_dist - prev_dist if prev_dist is not None and np.isfinite(prev_dist) else np.nan
        implied_speed = abs(route_delta) / dt if np.isfinite(route_delta) and np.isfinite(dt) and dt > 0 else np.nan
        chosen.append(
            {
                "route_dist_m": route_dist,
                "nearest_route_dist_m": nearest_profile_dist(route_dist, route_axis["profile_dist_values"]),
                "offset_m": cand["offset_m"],
                "sequence_match_score": score,
                "candidate_rank": int(cand["candidate_rank"]),
                "route_dist_delta_m": route_delta,
                "implied_route_speed_mps": implied_speed,
                "sequence_jump_guard_flag": bool(jump_guard),
                "sequence_branch_ambiguity_flag": bool(branch_ambiguity),
            }
        )
        prev_dist = route_dist
        prev_time = t if np.isfinite(t) else prev_time

    out = activity.copy()
    for key in chosen[0].keys():
        out[key] = [row[key] for row in chosen]
    out["route_folder"] = route_folder
    out["case_id"] = case_id
    out["segment_id"] = np.floor(pd.to_numeric(out["route_dist_m"], errors="coerce") / args.segment_m).astype("Int64")
    out["direction_hint"] = add_direction_hint(out["route_dist_m"])
    out["match_quality"] = [classify_match_quality(offset, args.off_route_m) for offset in out["offset_m"]]
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


def summarize_result(row: pd.Series, case_id: str, result: pd.DataFrame | None, old: pd.DataFrame | None, status: str, error: str = "") -> dict[str, Any]:
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
            "status": status,
            "error": error,
        }

    old_offset_mean = float(old["offset_m"].mean()) if old is not None and "offset_m" in old and old["offset_m"].notna().any() else np.nan
    old_offset_p95 = float(old["offset_m"].quantile(0.95)) if old is not None and "offset_m" in old and old["offset_m"].notna().any() else np.nan
    new_offset_mean = float(result["offset_m"].mean()) if result["offset_m"].notna().any() else np.nan
    new_offset_p95 = float(result["offset_m"].quantile(0.95)) if result["offset_m"].notna().any() else np.nan

    return {
        "route_folder": row.get("route_folder"),
        "case_id": case_id,
        "subject_id": row.get("subject_id"),
        "trial_id": row.get("trial_id"),
        "activity_id": f"{int(row.get('subject_id'))}_{int(row.get('trial_id'))}",
        "rows_input": len(result),
        "rows_matched": int(result["route_dist_m"].notna().sum()),
        "match_ratio": float(result["route_dist_m"].notna().mean()),
        "old_route_dist_jump_count": jump_count(old) if old is not None and not old.empty else np.nan,
        "new_route_dist_jump_count": jump_count(result),
        "old_speed_impossible_jump_count": impossible_speed_count(old) if old is not None and not old.empty else np.nan,
        "new_speed_impossible_jump_count": impossible_speed_count(result),
        "old_offset_m_mean": old_offset_mean,
        "new_offset_m_mean": new_offset_mean,
        "old_offset_m_p95": old_offset_p95,
        "new_offset_m_p95": new_offset_p95,
        "offset_mean_delta_m": new_offset_mean - old_offset_mean if np.isfinite(old_offset_mean) else np.nan,
        "offset_p95_delta_m": new_offset_p95 - old_offset_p95 if np.isfinite(old_offset_p95) else np.nan,
        "sequence_jump_guard_count": int(result["sequence_jump_guard_flag"].sum()),
        "sequence_branch_ambiguity_count": int(result["sequence_branch_ambiguity_flag"].sum()),
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
        case_id = ROUTE_CASE_MAP.get(route_folder)
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
