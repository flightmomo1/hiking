# -*- coding: utf-8 -*-
"""
Create a read-only IB0D-level qixing via-corridor local-loop pruning candidate.

The script does not overwrite formal v1.3b IB0D/IB1/IB1E/THCI/IB3 outputs. It writes
only a candidate root for review.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import folium
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pyproj import Geod


CASE_ID = "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b"
VIA_UP = {"lat": 25.165082087184047, "lon": 121.55966911100028}
VIA_DOWN = {"lat": 25.16487469519971, "lon": 121.55963745345083}

FORMAL_IB0D_ROOT = Path("outputs/ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa") / CASE_ID
REPAIR_PLAN_ROOT = Path("outputs/qixing_lengshuikeng_via_corridor_repair_plan_v1_3b")
OUT_ROOT = (
    Path("outputs/ib0d_trimmed_mainline_v1_3b_qixing_via_corridor_repair_candidate")
    / CASE_ID
)

# Deliberately do not prune the whole evidence ranges. Preserve via_up/via_down
# passages and only remove repeated connector bounce after each required pass.
PRUNE_RANGES = [
    {
        "start_dist_m": 626.0,
        "end_dist_m": 788.0,
        "source_problem_range": "579-788m control_point_bounce_near_sequence",
        "reason": "Preserve first via_up pass at 579-625m; remove repeated via_up connector bounce at 663-788m.",
    },
    {
        "start_dist_m": 3442.0,
        "end_dist_m": 3608.0,
        "source_problem_range": "3417-3608m via_down/via_up connector bounce",
        "reason": "Preserve via_down pass at 3401-3441m; remove repeated via_up/down connector bounce after via_down.",
    },
]

GEOMETRY_CONTINUITY_MAX_GAP_M = 25.0
VIA_MAX_DISTANCE_M = 10.0
MAX_REASONABLE_LENGTH_REDUCTION_RATIO = 0.15
BEARING_REVERSAL_DEG = 150.0
SPATIAL_REVISIT_DISTANCE_M = 10.0
SPATIAL_REVISIT_ROUTE_GAP_M = 30.0
GEOD = Geod(ellps="WGS84")


def geodesic_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    _, _, dist = GEOD.inv(float(lon1), float(lat1), float(lon2), float(lat2))
    return float(dist)


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    az12, _, _ = GEOD.inv(float(lon1), float(lat1), float(lon2), float(lat2))
    return float((az12 + 360.0) % 360.0)


def angle_delta(a: float, b: float) -> float:
    if pd.isna(a) or pd.isna(b):
        return np.nan
    return abs((float(a) - float(b) + 180.0) % 360.0 - 180.0)


def load_route_points() -> pd.DataFrame:
    fp = FORMAL_IB0D_ROOT / "route_points.csv"
    if not fp.exists():
        raise FileNotFoundError(f"Missing formal IB0D route points: {fp}")
    df = pd.read_csv(fp)
    required = {"route_dist_m", "lat", "lon"}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(f"route_points.csv missing columns: {sorted(missing)}")
    df = df.copy()
    df["route_dist_m"] = pd.to_numeric(df["route_dist_m"], errors="coerce")
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df = df.dropna(subset=["route_dist_m", "lat", "lon"])
    return df.sort_values("route_dist_m").reset_index(drop=True)


def add_geometry_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy().reset_index(drop=True)
    seg_len = [0.0]
    bearings = [np.nan]
    for prev, cur in zip(df.iloc[:-1].itertuples(index=False), df.iloc[1:].itertuples(index=False)):
        seg_len.append(geodesic_distance_m(prev.lat, prev.lon, cur.lat, cur.lon))
        bearings.append(bearing_deg(prev.lat, prev.lon, cur.lat, cur.lon))
    df["segment_len_m"] = seg_len
    df["candidate_route_dist_m"] = np.cumsum(seg_len)
    df["bearing_deg"] = bearings
    df["bearing_change_deg"] = [np.nan] + [angle_delta(bearings[i], bearings[i - 1]) for i in range(1, len(bearings))]
    return df


def nearest_via_distance(df: pd.DataFrame, via: dict[str, float]) -> tuple[float, float]:
    distances = [
        geodesic_distance_m(via["lat"], via["lon"], row.lat, row.lon)
        for row in df[["lat", "lon"]].itertuples(index=False)
    ]
    idx = int(np.argmin(distances))
    dist_col = "candidate_route_dist_m" if "candidate_route_dist_m" in df.columns else "route_dist_m"
    return float(distances[idx]), float(df.iloc[idx][dist_col])


def remove_prune_ranges(original: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    keep = pd.Series(True, index=original.index)
    removed_rows = []
    for pr in PRUNE_RANGES:
        mask = original["route_dist_m"].between(pr["start_dist_m"], pr["end_dist_m"], inclusive="both")
        removed = original[mask].copy()
        removed["prune_start_dist_m"] = pr["start_dist_m"]
        removed["prune_end_dist_m"] = pr["end_dist_m"]
        removed["prune_reason"] = pr["reason"]
        removed["source_problem_range"] = pr["source_problem_range"]
        removed_rows.append(removed)
        keep = keep & ~mask
    pruned = original[keep].copy().reset_index(drop=True)
    removed_df = pd.concat(removed_rows, ignore_index=True) if removed_rows else pd.DataFrame()
    pruned["original_route_dist_m"] = pruned["route_dist_m"]
    pruned = add_geometry_metrics(pruned)
    pruned["route_point_index"] = np.arange(len(pruned), dtype=int)
    pruned["route_dist_m"] = pruned["candidate_route_dist_m"]
    return pruned, removed_df


def continuity_gaps(original: pd.DataFrame) -> list[dict[str, Any]]:
    gaps = []
    for pr in PRUNE_RANGES:
        before = original[original["route_dist_m"] < pr["start_dist_m"]].iloc[-1]
        after = original[original["route_dist_m"] > pr["end_dist_m"]].iloc[0]
        gap = geodesic_distance_m(before.lat, before.lon, after.lat, after.lon)
        gaps.append(
            {
                "prune_start_dist_m": pr["start_dist_m"],
                "prune_end_dist_m": pr["end_dist_m"],
                "before_route_dist_m": float(before["route_dist_m"]),
                "after_route_dist_m": float(after["route_dist_m"]),
                "connector_gap_m": gap,
                "geometry_continuous": gap <= GEOMETRY_CONTINUITY_MAX_GAP_M,
            }
        )
    return gaps


def near_sequence_bounce(df: pd.DataFrame) -> tuple[bool, list[dict[str, Any]]]:
    work = df.copy()
    work["distance_to_via_up_m"] = [
        geodesic_distance_m(VIA_UP["lat"], VIA_UP["lon"], row.lat, row.lon)
        for row in work[["lat", "lon"]].itertuples(index=False)
    ]
    work["distance_to_via_down_m"] = [
        geodesic_distance_m(VIA_DOWN["lat"], VIA_DOWN["lon"], row.lat, row.lon)
        for row in work[["lat", "lon"]].itertuples(index=False)
    ]
    work["near_via_up_flag"] = work["distance_to_via_up_m"] <= 20.0
    work["near_via_down_flag"] = work["distance_to_via_down_m"] <= 20.0
    labels = []
    dist_col = "candidate_route_dist_m" if "candidate_route_dist_m" in work.columns else "route_dist_m"
    for row in work.itertuples(index=False):
        if row.near_via_up_flag and row.near_via_down_flag:
            # via_up and via_down are spatially close. Treat overlap as continuity
            # with the previous via neighborhood, not as a new bounce state.
            previous_non_away = next((x["label"] for x in reversed(labels) if x["label"] != "away"), "")
            label = previous_non_away if previous_non_away in {"via_up", "via_down"} else "via_down"
        elif row.near_via_up_flag:
            label = "via_up"
        elif row.near_via_down_flag:
            label = "via_down"
        else:
            label = "away"
        dist = float(getattr(row, dist_col))
        if not labels or labels[-1]["label"] != label:
            labels.append({"label": label, "start_dist_m": dist, "end_dist_m": dist, "points_n": 1})
        else:
            labels[-1]["end_dist_m"] = dist
            labels[-1]["points_n"] += 1
    non_away = [x["label"] for x in labels if x["label"] != "away"]
    repeats = sum(1 for a, b in zip(non_away, non_away[1:]) if a == b)
    alternations = sum(1 for a, b in zip(non_away, non_away[1:]) if a != b)
    return bool(repeats > 0 or alternations > 2), labels


def spatial_revisit_pairs_n(df: pd.DataFrame) -> int:
    work = df.copy().reset_index(drop=True)
    dist_col = "candidate_route_dist_m" if "candidate_route_dist_m" in work.columns else "route_dist_m"
    start = min(605.0, 3421.0) - 300.0
    end = max(605.0, 3421.0) + 300.0
    work = work[pd.to_numeric(work[dist_col], errors="coerce").between(start, end)].reset_index(drop=True)
    if work.empty:
        return 0
    lat0_rad = math.radians(float(work["lat"].mean()))
    x = work["lon"].astype(float).to_numpy() * 111_320.0 * math.cos(lat0_rad)
    y = work["lat"].astype(float).to_numpy() * 110_540.0
    dists = work[dist_col].astype(float).to_numpy()
    count = 0
    for i in range(len(work)):
        route_gaps = np.abs(dists[i + 1 :] - dists[i])
        if len(route_gaps) == 0:
            continue
        spatial = np.hypot(x[i + 1 :] - x[i], y[i + 1 :] - y[i])
        count += int(((route_gaps >= SPATIAL_REVISIT_ROUTE_GAP_M) & (spatial <= SPATIAL_REVISIT_DISTANCE_M)).sum())
    return count


def metrics(df: pd.DataFrame) -> dict[str, Any]:
    work = add_geometry_metrics(df) if "candidate_route_dist_m" not in df.columns else df.copy()
    via_up_dist_m, via_up_axis_m = nearest_via_distance(work, VIA_UP)
    via_down_dist_m, via_down_axis_m = nearest_via_distance(work, VIA_DOWN)
    # Exclude the same-entry summit/mirror reversal zone from via-corridor local-loop evaluation.
    dist_col = "candidate_route_dist_m" if "candidate_route_dist_m" in work.columns else "route_dist_m"
    non_summit = work[~pd.to_numeric(work[dist_col], errors="coerce").between(1950.0, 2250.0)]
    bearing_reversal_count = int((pd.to_numeric(non_summit["bearing_change_deg"], errors="coerce") >= BEARING_REVERSAL_DEG).sum())
    bounce, seq = near_sequence_bounce(work)
    revisit_n = spatial_revisit_pairs_n(work)
    local_osc = bool(bounce or bearing_reversal_count >= 2)
    return {
        "route_length_m": float(work[dist_col].max()),
        "points_n": int(len(work)),
        "via_up_nearest_distance_m": via_up_dist_m,
        "via_up_route_dist_m": via_up_axis_m,
        "via_down_nearest_distance_m": via_down_dist_m,
        "via_down_route_dist_m": via_down_axis_m,
        "bearing_reversal_count": bearing_reversal_count,
        "spatial_revisit_pairs_n": int(revisit_n),
        "control_point_bounce_detected": bounce,
        "near_via_sequence": seq,
        "local_oscillation_detected": local_osc,
        "max_segment_len_m": float(pd.to_numeric(work["segment_len_m"], errors="coerce").max()),
    }


def build_geojson(df: pd.DataFrame, summary: dict[str, Any]) -> dict[str, Any]:
    coords = [[float(row.lon), float(row.lat)] for row in df.itertuples(index=False)]
    props = {
        "source": "ib0d_qixing_via_corridor_local_loop_pruning_candidate_v1_3b",
        "case_id": CASE_ID,
        "candidate_status": summary["final_candidate_decision"],
        "original_route_length_m": summary["original_route_length_m"],
        "pruned_route_length_m": summary["pruned_route_length_m"],
        "removed_dist_m": summary["removed_dist_m"],
        "formal_outputs_overwritten": False,
    }
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": props,
                "geometry": {"type": "LineString", "coordinates": coords},
            }
        ],
    }


def write_diagnostics(original: pd.DataFrame, pruned: pd.DataFrame, removed: pd.DataFrame) -> None:
    out_png = OUT_ROOT / "qixing_via_corridor_pruning_before_after_diagnostic.png"
    fig, ax = plt.subplots(figsize=(9, 7))
    ax.plot(original["lon"], original["lat"], color="#94a3b8", linewidth=2, label="original")
    ax.plot(pruned["lon"], pruned["lat"], color="#2563eb", linewidth=2, label="pruned candidate")
    if not removed.empty:
        ax.scatter(removed["lon"], removed["lat"], color="#dc2626", s=8, label="removed candidate points")
    ax.scatter([VIA_UP["lon"]], [VIA_UP["lat"]], color="#16a34a", s=70, label="via_up")
    ax.scatter([VIA_DOWN["lon"]], [VIA_DOWN["lat"]], color="#f97316", s=70, label="via_down")
    ax.set_title("IB0D qixing via corridor pruning candidate")
    ax.set_xlabel("lon")
    ax.set_ylabel("lat")
    ax.grid(alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(out_png, dpi=160)
    plt.close(fig)

    center = [float(original["lat"].mean()), float(original["lon"].mean())]
    m = folium.Map(location=center, zoom_start=16, tiles="OpenStreetMap")
    folium.PolyLine(original[["lat", "lon"]].values.tolist(), color="#94a3b8", weight=4, tooltip="original IB0D").add_to(m)
    folium.PolyLine(pruned[["lat", "lon"]].values.tolist(), color="#2563eb", weight=4, tooltip="pruned candidate").add_to(m)
    if not removed.empty:
        for row in removed.iloc[:: max(1, len(removed) // 200)].itertuples(index=False):
            folium.CircleMarker([row.lat, row.lon], radius=2, color="#dc2626", fill=True, tooltip="removed candidate").add_to(m)
    folium.Marker([VIA_UP["lat"], VIA_UP["lon"]], tooltip="via_up", icon=folium.Icon(color="green")).add_to(m)
    folium.Marker([VIA_DOWN["lat"], VIA_DOWN["lon"]], tooltip="via_down", icon=folium.Icon(color="orange")).add_to(m)
    m.save(str(OUT_ROOT / "qixing_via_corridor_pruning_before_after_diagnostic.html"))


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    original = load_route_points()
    original_metrics = metrics(original)
    pruned, removed = remove_prune_ranges(original)
    pruned_metrics = metrics(pruned)
    gaps = continuity_gaps(original)

    original_route_dist_max = float(pd.to_numeric(original["route_dist_m"], errors="coerce").max())
    original_geometry_len = original_metrics["route_length_m"]
    pruned_len = pruned_metrics["route_length_m"]
    removed_dist = original_geometry_len - pruned_len
    length_reduction_ratio = removed_dist / original_geometry_len if original_geometry_len else np.nan

    geometry_continuous = all(g["geometry_continuous"] for g in gaps)
    via_ok = (
        pruned_metrics["via_up_nearest_distance_m"] <= VIA_MAX_DISTANCE_M
        and pruned_metrics["via_down_nearest_distance_m"] <= VIA_MAX_DISTANCE_M
    )
    route_monotonic = bool(pd.to_numeric(pruned["route_dist_m"], errors="coerce").is_monotonic_increasing)
    length_ok = bool(length_reduction_ratio <= MAX_REASONABLE_LENGTH_REDUCTION_RATIO)
    reversal_reduced = pruned_metrics["bearing_reversal_count"] < original_metrics["bearing_reversal_count"]
    oscillation_reduced = (not pruned_metrics["local_oscillation_detected"]) or (
        pruned_metrics["spatial_revisit_pairs_n"] < original_metrics["spatial_revisit_pairs_n"]
    )

    candidate_pass = bool(geometry_continuous and via_ok and route_monotonic and length_ok and reversal_reduced and oscillation_reduced)
    final_decision = (
        "IB0D_QIXING_VIA_CORRIDOR_PRUNING_CANDIDATE_STATUS = CANDIDATE_PASS"
        if candidate_pass
        else "IB0D_QIXING_VIA_CORRIDOR_PRUNING_CANDIDATE_STATUS = FAIL_REVIEW_REQUIRED"
    )

    summary = {
        "case_id": CASE_ID,
        "final_candidate_decision": final_decision,
        "formal_outputs_overwritten": False,
        "prune_ranges_applied": PRUNE_RANGES,
        "original_route_length_m": original_route_dist_max,
        "original_route_dist_max_m": original_route_dist_max,
        "original_recomputed_geometry_length_m": original_geometry_len,
        "pruned_route_length_m": pruned_len,
        "pruned_recomputed_geometry_length_m": pruned_len,
        "removed_dist_m": removed_dist,
        "removed_points_n": int(len(removed)),
        "length_reduction_ratio": length_reduction_ratio,
        "via_up_nearest_distance_before_m": original_metrics["via_up_nearest_distance_m"],
        "via_up_nearest_distance_after_m": pruned_metrics["via_up_nearest_distance_m"],
        "via_down_nearest_distance_before_m": original_metrics["via_down_nearest_distance_m"],
        "via_down_nearest_distance_after_m": pruned_metrics["via_down_nearest_distance_m"],
        "via_up_route_dist_before_m": original_metrics["via_up_route_dist_m"],
        "via_up_route_dist_after_m": pruned_metrics["via_up_route_dist_m"],
        "via_down_route_dist_before_m": original_metrics["via_down_route_dist_m"],
        "via_down_route_dist_after_m": pruned_metrics["via_down_route_dist_m"],
        "bearing_reversal_count_before": original_metrics["bearing_reversal_count"],
        "bearing_reversal_count_after": pruned_metrics["bearing_reversal_count"],
        "spatial_revisit_pairs_n_before": original_metrics["spatial_revisit_pairs_n"],
        "spatial_revisit_pairs_n_after": pruned_metrics["spatial_revisit_pairs_n"],
        "local_oscillation_detected_before": original_metrics["local_oscillation_detected"],
        "local_oscillation_detected_after": pruned_metrics["local_oscillation_detected"],
        "control_point_bounce_detected_before": original_metrics["control_point_bounce_detected"],
        "control_point_bounce_detected_after": pruned_metrics["control_point_bounce_detected"],
        "geometry_continuous": geometry_continuous,
        "route_dist_monotonic": route_monotonic,
        "length_ok": length_ok,
        "via_distance_ok": via_ok,
        "connector_gaps": gaps,
        "recommend_ib1a_ib1e_revalidation": candidate_pass,
        "next_action": (
            "Use this candidate as an isolated repair branch/root and rerun IB1A/IB1E validation against the candidate route only."
            if candidate_pass
            else "Review candidate manually before any downstream validation."
        ),
        "input_roots": {
            "formal_ib0d_root": str(FORMAL_IB0D_ROOT),
            "repair_plan_root": str(REPAIR_PLAN_ROOT),
        },
        "output_root": str(OUT_ROOT),
        "runtime_llm_allowed": False,
        "note": "This is a candidate artifact only. Formal v1.3b outputs were not overwritten.",
    }

    pruned_out = pruned.copy()
    pruned_out.to_csv(OUT_ROOT / "route_points_pruned_candidate.csv", index=False, encoding="utf-8-sig")
    removed.to_csv(OUT_ROOT / "removed_route_points_pruned_candidate.csv", index=False, encoding="utf-8-sig")
    decision_df = pd.DataFrame(
        [
            {
                "case_id": CASE_ID,
                "final_candidate_decision": final_decision,
                "geometry_continuous": geometry_continuous,
                "route_dist_monotonic": route_monotonic,
                "via_distance_ok": via_ok,
                "length_ok": length_ok,
                "reversal_reduced": reversal_reduced,
                "oscillation_reduced": oscillation_reduced,
                "removed_points_n": len(removed),
                "removed_dist_m": removed_dist,
                "recommend_ib1a_ib1e_revalidation": candidate_pass,
            }
        ]
    )
    decision_df.to_csv(OUT_ROOT / "qixing_via_corridor_pruning_decision.csv", index=False, encoding="utf-8-sig")
    (OUT_ROOT / "qixing_via_corridor_pruning_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUT_ROOT / "mainline_ordered_path_trimmed_pruned_candidate.geojson").write_text(
        json.dumps(build_geojson(pruned, summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_diagnostics(original, pruned, removed)

    print("IB0D qixing via corridor local loop pruning candidate complete")
    print(f"final_candidate_decision: {final_decision}")
    print(f"original_route_length_m: {original_route_dist_max:.6f}")
    print(f"original_recomputed_geometry_length_m: {original_geometry_len:.6f}")
    print(f"pruned_route_length_m: {pruned_len:.6f}")
    print(f"removed_dist_m: {removed_dist:.6f}")
    print(f"removed_points_n: {len(removed)}")
    print(f"via_up_nearest_distance_before_m: {original_metrics['via_up_nearest_distance_m']:.6f}")
    print(f"via_up_nearest_distance_after_m: {pruned_metrics['via_up_nearest_distance_m']:.6f}")
    print(f"via_down_nearest_distance_before_m: {original_metrics['via_down_nearest_distance_m']:.6f}")
    print(f"via_down_nearest_distance_after_m: {pruned_metrics['via_down_nearest_distance_m']:.6f}")
    print(f"bearing_reversal_count_before: {original_metrics['bearing_reversal_count']}")
    print(f"bearing_reversal_count_after: {pruned_metrics['bearing_reversal_count']}")
    print(f"local_oscillation_detected_before: {original_metrics['local_oscillation_detected']}")
    print(f"local_oscillation_detected_after: {pruned_metrics['local_oscillation_detected']}")
    print(f"recommend_ib1a_ib1e_revalidation: {candidate_pass}")
    print(f"output_root: {OUT_ROOT}")


if __name__ == "__main__":
    main()
