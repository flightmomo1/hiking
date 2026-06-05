# -*- coding: utf-8 -*-
"""
Audit qixing_lengshuikeng via corridor route-axis oscillation on the current v1.3b baseline.

This diagnostic is read-only with respect to the formal route/activity pipeline:
it does not rerun IB0/IB1/IB2D/THCI/IB3 and only writes a separate audit root.
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

IB0D_ROOT = Path("outputs/ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa")
IB1_PROFILE_ROOT = Path("outputs/ib1_route_profile_v1_3b_contract_qa")
IB1E_ROOT = Path("outputs/ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa")
IB3_SEQUENCE_ROOT = Path("outputs/ib3a_sequence_mapmatched_activity_v1_3b_thci_v1_0c")
OUT_ROOT = Path("outputs/qixing_lengshuikeng_via_corridor_route_axis_oscillation_audit_v1_3b")

ACTIVITY_IDS = ["37_1", "33_1", "15_1"]
LOCAL_WINDOW_M = 250.0
CORRIDOR_WINDOW_M = 300.0
NEAR_VIA_M = 20.0
SPATIAL_REVISIT_DISTANCE_M = 10.0
SPATIAL_REVISIT_ROUTE_GAP_M = 30.0
BEARING_REVERSAL_DEG = 150.0

GEOD = Geod(ellps="WGS84")


def clip_angle_delta(delta: float) -> float:
    if pd.isna(delta):
        return np.nan
    return abs((delta + 180.0) % 360.0 - 180.0)


def geodesic_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    _, _, dist = GEOD.inv(float(lon1), float(lat1), float(lon2), float(lat2))
    return float(dist)


def geodesic_bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    az12, _, _ = GEOD.inv(float(lon1), float(lat1), float(lon2), float(lat2))
    return float((az12 + 360.0) % 360.0)


def load_route() -> tuple[pd.DataFrame, dict[str, str]]:
    ib1e_csv = (
        IB1E_ROOT
        / CASE_ID
        / f"{CASE_ID}_route_profile_contour_window_terrain_enriched.csv"
    )
    ib1_csv = IB1_PROFILE_ROOT / CASE_ID / f"{CASE_ID}_route_profile.csv"
    ib0d_route_points_csv = IB0D_ROOT / CASE_ID / "route_points.csv"
    selected = ib1e_csv if ib1e_csv.exists() else ib1_csv
    if not selected.exists():
        raise FileNotFoundError(f"Missing route CSV: {selected}")

    route = pd.read_csv(selected)
    if "dist_m" not in route.columns or not {"lat", "lon"}.issubset(route.columns):
        raise KeyError("Route CSV must contain dist_m, lat, lon")
    route = route.copy()
    route["route_dist_m"] = pd.to_numeric(route["dist_m"], errors="coerce")
    route["lat"] = pd.to_numeric(route["lat"], errors="coerce")
    route["lon"] = pd.to_numeric(route["lon"], errors="coerce")
    route = route.dropna(subset=["route_dist_m", "lat", "lon"])
    route = route.sort_values("route_dist_m").drop_duplicates("route_dist_m").reset_index(drop=True)

    source_files = {
        "ib1e_route_context_csv": str(ib1e_csv),
        "ib1_route_profile_csv": str(ib1_csv),
        "ib0d_route_points_csv": str(ib0d_route_points_csv),
        "selected_route_csv": str(selected),
    }
    return route, source_files


def project_via_to_route(route: pd.DataFrame, via: dict[str, float], prefix: str) -> dict[str, Any]:
    distances = [
        geodesic_distance_m(via["lat"], via["lon"], row.lat, row.lon)
        for row in route[["lat", "lon"]].itertuples(index=False)
    ]
    nearest_idx = int(np.nanargmin(distances))
    nearest = route.iloc[nearest_idx]
    return {
        f"{prefix}_lat": via["lat"],
        f"{prefix}_lon": via["lon"],
        f"{prefix}_route_dist_m": float(nearest["route_dist_m"]),
        f"{prefix}_nearest_route_lat": float(nearest["lat"]),
        f"{prefix}_nearest_route_lon": float(nearest["lon"]),
        f"{prefix}_nearest_route_distance_m": float(distances[nearest_idx]),
        f"{prefix}_nearest_route_index": nearest_idx,
    }


def enrich_route_window(route: pd.DataFrame, via_up_dist: float, via_down_dist: float) -> pd.DataFrame:
    route = route.copy()
    route["distance_to_via_up_m"] = [
        geodesic_distance_m(VIA_UP["lat"], VIA_UP["lon"], row.lat, row.lon)
        for row in route[["lat", "lon"]].itertuples(index=False)
    ]
    route["distance_to_via_down_m"] = [
        geodesic_distance_m(VIA_DOWN["lat"], VIA_DOWN["lon"], row.lat, row.lon)
        for row in route[["lat", "lon"]].itertuples(index=False)
    ]
    route["near_via_up_flag"] = route["distance_to_via_up_m"] <= NEAR_VIA_M
    route["near_via_down_flag"] = route["distance_to_via_down_m"] <= NEAR_VIA_M

    seg_len = [np.nan]
    bearing = [np.nan]
    for prev, cur in zip(route.iloc[:-1].itertuples(index=False), route.iloc[1:].itertuples(index=False)):
        seg_len.append(geodesic_distance_m(prev.lat, prev.lon, cur.lat, cur.lon))
        bearing.append(geodesic_bearing_deg(prev.lat, prev.lon, cur.lat, cur.lon))
    route["segment_len_m"] = seg_len
    route["bearing_deg"] = bearing
    route["bearing_change_deg"] = route["bearing_deg"].diff().map(clip_angle_delta)

    start = max(0.0, min(via_up_dist, via_down_dist) - CORRIDOR_WINDOW_M)
    end = min(float(route["route_dist_m"].max()), max(via_up_dist, via_down_dist) + CORRIDOR_WINDOW_M)
    corridor = route[(route["route_dist_m"] >= start) & (route["route_dist_m"] <= end)].copy()
    corridor["cumulative_local_distance_m"] = corridor["segment_len_m"].fillna(0).cumsum()
    return corridor


def select_window(route: pd.DataFrame, center_dist: float, radius_m: float) -> pd.DataFrame:
    start = center_dist - radius_m
    end = center_dist + radius_m
    return route[(route["route_dist_m"] >= start) & (route["route_dist_m"] <= end)].copy()


def detect_bearing_reversals(corridor: pd.DataFrame) -> pd.DataFrame:
    out = corridor[pd.to_numeric(corridor["bearing_change_deg"], errors="coerce") >= BEARING_REVERSAL_DEG].copy()
    return out


def detect_spatial_revisits(corridor: pd.DataFrame) -> pd.DataFrame:
    rows = []
    coords = corridor[["route_dist_m", "lat", "lon"]].reset_index(drop=True).copy()
    lat0_rad = math.radians(float(coords["lat"].mean()))
    coords["x_m"] = coords["lon"].astype(float) * 111_320.0 * math.cos(lat0_rad)
    coords["y_m"] = coords["lat"].astype(float) * 110_540.0
    for i in range(len(coords)):
        a = coords.iloc[i]
        for j in range(i + 1, len(coords)):
            b = coords.iloc[j]
            route_gap = abs(float(b["route_dist_m"]) - float(a["route_dist_m"]))
            if route_gap < SPATIAL_REVISIT_ROUTE_GAP_M:
                continue
            spatial_dist = math.hypot(float(a["x_m"]) - float(b["x_m"]), float(a["y_m"]) - float(b["y_m"]))
            if spatial_dist <= SPATIAL_REVISIT_DISTANCE_M:
                rows.append(
                    {
                        "route_dist_m_a": float(a["route_dist_m"]),
                        "route_dist_m_b": float(b["route_dist_m"]),
                        "route_dist_gap_m": route_gap,
                        "spatial_distance_m": spatial_dist,
                        "lat_a": float(a["lat"]),
                        "lon_a": float(a["lon"]),
                        "lat_b": float(b["lat"]),
                        "lon_b": float(b["lon"]),
                    }
                )
    return pd.DataFrame(rows)


def detect_repeated_edges(corridor: pd.DataFrame) -> pd.DataFrame:
    rows = []
    id_cols = [
        c
        for c in [
            "osm_way_id",
            "osm_id",
            "edge_id",
            "node_id",
            "source_edge_id",
            "way_id",
        ]
        if c in corridor.columns
    ]
    for col in id_cols:
        work = corridor[["route_dist_m", col]].dropna().copy()
        work[col] = work[col].astype(str)
        for value, grp in work.groupby(col):
            if len(grp) < 2:
                continue
            dist_min = float(grp["route_dist_m"].min())
            dist_max = float(grp["route_dist_m"].max())
            if dist_max - dist_min >= SPATIAL_REVISIT_ROUTE_GAP_M:
                rows.append(
                    {
                        "id_column": col,
                        "id_value": value,
                        "points_n": int(len(grp)),
                        "route_dist_min_m": dist_min,
                        "route_dist_max_m": dist_max,
                        "route_dist_span_m": dist_max - dist_min,
                    }
                )
    return pd.DataFrame(rows)


def compact_near_sequence(corridor: pd.DataFrame) -> list[dict[str, Any]]:
    labels = []
    for row in corridor.itertuples(index=False):
        if row.near_via_up_flag and row.near_via_down_flag:
            label = "both"
        elif row.near_via_up_flag:
            label = "via_up"
        elif row.near_via_down_flag:
            label = "via_down"
        else:
            label = "away"
        if not labels or labels[-1]["label"] != label:
            labels.append(
                {
                    "label": label,
                    "start_dist_m": float(row.route_dist_m),
                    "end_dist_m": float(row.route_dist_m),
                    "points_n": 1,
                }
            )
        else:
            labels[-1]["end_dist_m"] = float(row.route_dist_m)
            labels[-1]["points_n"] += 1
    return labels


def detect_control_point_bounce(corridor: pd.DataFrame) -> tuple[bool, list[dict[str, Any]]]:
    sequence = compact_near_sequence(corridor)
    labels = [x["label"] for x in sequence]
    meaningful = [x for x in labels if x != "away"]
    alternations = sum(
        1
        for a, b in zip(meaningful, meaningful[1:])
        if a != b and {"via_up", "via_down"}.issubset({a, b})
    )
    repeats_after_away = any(labels[i] == labels[i + 2] and labels[i + 1] == "away" and labels[i] != "away" for i in range(len(labels) - 2))
    return bool(alternations >= 2 or repeats_after_away), sequence


def summarize_activity_overlay(corridor_start: float, corridor_end: float) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    rows = []
    details = []
    for activity_id in ACTIVITY_IDS:
        fp = IB3_SEQUENCE_ROOT / "qixing_lengshuikeng" / f"{activity_id}_mapmatched.csv"
        if not fp.exists():
            rows.append(
                {
                    "activity_id": activity_id,
                    "sequence_csv_exists": False,
                    "blocking_issue": f"missing sequence CSV: {fp}",
                }
            )
            continue
        df = pd.read_csv(fp)
        df["route_dist_m"] = pd.to_numeric(df["route_dist_m"], errors="coerce")
        w = df[(df["route_dist_m"] >= corridor_start) & (df["route_dist_m"] <= corridor_end)].copy()
        phase_transitions = 0
        if "candidate_phase" in w.columns and len(w) > 1:
            phase_transitions = int((w["candidate_phase"].astype(str) != w["candidate_phase"].astype(str).shift()).sum() - 1)
        sign_changes = 0
        if "route_dist_delta_m" in w.columns:
            delta = pd.to_numeric(w["route_dist_delta_m"], errors="coerce").dropna()
            signs = np.sign(delta[delta.abs() >= 1.0])
            if len(signs) > 1:
                sign_changes = int((signs != signs.shift()).sum() - 1)
        state_counts = w["route_progress_state"].value_counts(dropna=False).to_dict() if "route_progress_state" in w.columns else {}
        phase_counts = w["candidate_phase"].value_counts(dropna=False).to_dict() if "candidate_phase" in w.columns else {}
        rows.append(
            {
                "activity_id": activity_id,
                "sequence_csv_exists": True,
                "sequence_csv": str(fp),
                "corridor_rows_n": int(len(w)),
                "corridor_route_dist_min_m": float(w["route_dist_m"].min()) if not w.empty else np.nan,
                "corridor_route_dist_max_m": float(w["route_dist_m"].max()) if not w.empty else np.nan,
                "route_dist_projection_reversal_n": sign_changes,
                "candidate_phase_transition_n": phase_transitions,
                "branch_ambiguous_projection_rows": int((w.get("route_progress_state", pd.Series(dtype=str)).astype(str) == "branch_ambiguous_projection").sum()),
                "off_route_projection_only_rows": int((w.get("route_progress_state", pd.Series(dtype=str)).astype(str) == "off_route_projection_only").sum()),
                "near_route_low_confidence_rows": int((w.get("route_progress_state", pd.Series(dtype=str)).astype(str) == "near_route_low_confidence").sum()),
                "sequence_branch_ambiguity_flag_rows": int(w.get("sequence_branch_ambiguity_flag", pd.Series(dtype=bool)).astype(str).str.lower().isin(["true", "1"]).sum()),
                "candidate_phase_counts": json.dumps(phase_counts, ensure_ascii=False, sort_keys=True),
                "route_progress_state_counts": json.dumps(state_counts, ensure_ascii=False, sort_keys=True),
                "blocking_issue": "",
            }
        )
        detail_cols = [c for c in ["activity_id", "row_index", "elapsed_sec", "lat", "lon", "route_dist_m", "route_dist_delta_m", "route_progress_state", "candidate_phase", "match_quality", "offset_m"] if c in w.columns]
        details.extend(w[detail_cols].head(500).to_dict("records"))
    return pd.DataFrame(rows), details


def build_map(corridor: pd.DataFrame, reversals: pd.DataFrame, revisits: pd.DataFrame, out_html: Path) -> None:
    center = [float(corridor["lat"].mean()), float(corridor["lon"].mean())]
    m = folium.Map(location=center, zoom_start=17, tiles="OpenStreetMap")
    folium.PolyLine(corridor[["lat", "lon"]].values.tolist(), color="#2563eb", weight=4, tooltip="corridor route order").add_to(m)
    folium.Marker([VIA_UP["lat"], VIA_UP["lon"]], tooltip="via_up", icon=folium.Icon(color="green")).add_to(m)
    folium.Marker([VIA_DOWN["lat"], VIA_DOWN["lon"]], tooltip="via_down", icon=folium.Icon(color="red")).add_to(m)
    for row in reversals.itertuples(index=False):
        folium.CircleMarker([row.lat, row.lon], radius=5, color="#f59e0b", fill=True, tooltip=f"bearing reversal {row.route_dist_m:.1f}m").add_to(m)
    for row in revisits.head(100).itertuples(index=False):
        folium.PolyLine([[row.lat_a, row.lon_a], [row.lat_b, row.lon_b]], color="#7c3aed", weight=2, opacity=0.5, tooltip="spatial revisit pair").add_to(m)
    m.save(str(out_html))


def build_png(corridor: pd.DataFrame, reversals: pd.DataFrame, out_png: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(corridor["lon"], corridor["lat"], color="#2563eb", linewidth=2, label="corridor route")
    ax.scatter([VIA_UP["lon"]], [VIA_UP["lat"]], color="#16a34a", s=80, label="via_up", zorder=3)
    ax.scatter([VIA_DOWN["lon"]], [VIA_DOWN["lat"]], color="#dc2626", s=80, label="via_down", zorder=3)
    if not reversals.empty:
        ax.scatter(reversals["lon"], reversals["lat"], color="#f59e0b", s=30, label="bearing reversal", zorder=2)
    ax.set_title("Qixing via corridor route-axis oscillation diagnostic")
    ax.set_xlabel("lon")
    ax.set_ylabel("lat")
    ax.legend(loc="best")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_png, dpi=160)
    plt.close(fig)


def write_outputs(
    corridor: pd.DataFrame,
    via_up_window: pd.DataFrame,
    via_down_window: pd.DataFrame,
    revisits: pd.DataFrame,
    reversals: pd.DataFrame,
    repeated_edges: pd.DataFrame,
    activity_summary: pd.DataFrame,
    summary: dict[str, Any],
) -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    corridor.to_csv(OUT_ROOT / "qixing_lengshuikeng_via_corridor_route_window.csv", index=False, encoding="utf-8-sig")
    via_up_window.to_csv(OUT_ROOT / "qixing_lengshuikeng_via_up_local_route_window.csv", index=False, encoding="utf-8-sig")
    via_down_window.to_csv(OUT_ROOT / "qixing_lengshuikeng_via_down_local_route_window.csv", index=False, encoding="utf-8-sig")
    revisits.to_csv(OUT_ROOT / "qixing_lengshuikeng_via_corridor_spatial_revisit_pairs.csv", index=False, encoding="utf-8-sig")
    reversals.to_csv(OUT_ROOT / "qixing_lengshuikeng_via_corridor_bearing_reversals.csv", index=False, encoding="utf-8-sig")
    repeated_edges.to_csv(OUT_ROOT / "qixing_lengshuikeng_via_corridor_repeated_edges.csv", index=False, encoding="utf-8-sig")
    activity_summary.to_csv(OUT_ROOT / "qixing_lengshuikeng_via_corridor_activity_overlay_summary.csv", index=False, encoding="utf-8-sig")
    (OUT_ROOT / "qixing_lengshuikeng_via_corridor_route_axis_oscillation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    route, source_files = load_route()
    up = project_via_to_route(route, VIA_UP, "via_up")
    down = project_via_to_route(route, VIA_DOWN, "via_down")
    via_up_dist = float(up["via_up_route_dist_m"])
    via_down_dist = float(down["via_down_route_dist_m"])
    via_dist_gap = abs(via_down_dist - via_up_dist)

    enriched = enrich_route_window(route, via_up_dist, via_down_dist)
    corridor_start = float(enriched["route_dist_m"].min()) if not enriched.empty else np.nan
    corridor_end = float(enriched["route_dist_m"].max()) if not enriched.empty else np.nan
    via_up_window = select_window(enriched, via_up_dist, LOCAL_WINDOW_M)
    via_down_window = select_window(enriched, via_down_dist, LOCAL_WINDOW_M)

    reversals = detect_bearing_reversals(enriched)
    revisits = detect_spatial_revisits(enriched)
    repeated_edges = detect_repeated_edges(enriched)
    control_bounce, near_sequence = detect_control_point_bounce(enriched)

    bearing_reversal_count = int(len(reversals))
    spatial_revisit_pairs_n = int(len(revisits))
    repeated_way_ids_n = int(len(repeated_edges[repeated_edges["id_column"].eq("osm_way_id")])) if not repeated_edges.empty else 0
    repeated_edges_n = int(len(repeated_edges))
    forward_back_forward = bool(bearing_reversal_count > 0 and (spatial_revisit_pairs_n > 0 or control_bounce))
    local_oscillation = bool(control_bounce or forward_back_forward or (bearing_reversal_count > 0 and spatial_revisit_pairs_n > 0))

    activity_summary, _ = summarize_activity_overlay(corridor_start, corridor_end)
    activity_overlay_checked = bool(activity_summary["sequence_csv_exists"].fillna(False).all()) if not activity_summary.empty else False

    activity_route_axis_signals = {}
    if not activity_summary.empty:
        activity_route_axis_signals = {
            "total_corridor_rows_n": int(activity_summary["corridor_rows_n"].fillna(0).sum()),
            "total_branch_ambiguous_projection_rows": int(activity_summary["branch_ambiguous_projection_rows"].fillna(0).sum()),
            "total_off_route_projection_only_rows": int(activity_summary["off_route_projection_only_rows"].fillna(0).sum()),
            "total_near_route_low_confidence_rows": int(activity_summary["near_route_low_confidence_rows"].fillna(0).sum()),
            "total_route_dist_projection_reversal_n": int(activity_summary["route_dist_projection_reversal_n"].fillna(0).sum()),
        }

    route_axis_issue_suspected = bool(local_oscillation or activity_route_axis_signals.get("total_branch_ambiguous_projection_rows", 0) > 0)
    if local_oscillation or control_bounce:
        final_decision = "ROUTE_AXIS_VIA_CORRIDOR_OSCILLATION_STATUS = SUSPECTED_ROUTE_BASELINE_ISSUE"
        blocking_recommendation = "Review IB0B/IB0D route baseline around via_up/via_down corridor before treating activity oscillation as user behavior."
    elif activity_route_axis_signals.get("total_branch_ambiguous_projection_rows", 0) > 0:
        final_decision = "ROUTE_AXIS_VIA_CORRIDOR_OSCILLATION_STATUS = ACTIVITY_MAPMATCH_ONLY_REVIEW"
        blocking_recommendation = "Route axis did not show local oscillation, but activity mapmatch has corridor ambiguity signals."
    else:
        final_decision = "ROUTE_AXIS_VIA_CORRIDOR_OSCILLATION_STATUS = PASS_NO_LOCAL_OSCILLATION_DETECTED"
        blocking_recommendation = "No route-axis blocking issue detected in via corridor diagnostic."

    summary = {
        "case_id": CASE_ID,
        "via_up_lat": VIA_UP["lat"],
        "via_up_lon": VIA_UP["lon"],
        "via_down_lat": VIA_DOWN["lat"],
        "via_down_lon": VIA_DOWN["lon"],
        **up,
        **down,
        "via_dist_gap_m": via_dist_gap,
        "corridor_window_start_m": corridor_start,
        "corridor_window_end_m": corridor_end,
        "corridor_points_n": int(len(enriched)),
        "via_up_window_points_n": int(len(via_up_window)),
        "via_down_window_points_n": int(len(via_down_window)),
        "bearing_reversal_count": bearing_reversal_count,
        "spatial_revisit_pairs_n": spatial_revisit_pairs_n,
        "repeated_way_ids_n": repeated_way_ids_n,
        "repeated_edges_n": repeated_edges_n,
        "control_point_bounce_detected": control_bounce,
        "near_via_sequence": near_sequence,
        "forward_back_forward_detected": forward_back_forward,
        "local_oscillation_detected": local_oscillation,
        "route_axis_issue_suspected": route_axis_issue_suspected,
        "activity_overlay_checked": activity_overlay_checked,
        "qixing_activity_overlay_summary": activity_route_axis_signals,
        "source_files": source_files,
        "output_root": str(OUT_ROOT),
        "blocking_recommendation": blocking_recommendation,
        "final_diagnostic_decision": final_decision,
        "runtime_llm_allowed": False,
        "note": "Read-only diagnostic. IB0/IB1/IB2D/THCI/IB3 were not rerun; current v1.3b route baseline and existing qixing smoke activity mapmatch outputs were inspected.",
    }

    write_outputs(enriched, via_up_window, via_down_window, revisits, reversals, repeated_edges, activity_summary, summary)
    build_png(enriched, reversals, OUT_ROOT / "qixing_lengshuikeng_via_corridor_route_axis_oscillation_diagnostic.png")
    build_map(enriched, reversals, revisits, OUT_ROOT / "qixing_lengshuikeng_via_corridor_route_axis_oscillation_diagnostic.html")

    print("qixing via corridor route-axis oscillation audit complete")
    print(f"final_diagnostic_decision: {final_decision}")
    print(f"via_up_route_dist_m: {via_up_dist:.3f}")
    print(f"via_down_route_dist_m: {via_down_dist:.3f}")
    print(f"via_dist_gap_m: {via_dist_gap:.3f}")
    print(f"local_oscillation_detected: {local_oscillation}")
    print(f"control_point_bounce_detected: {control_bounce}")
    print(f"forward_back_forward_detected: {forward_back_forward}")
    print(f"bearing_reversal_count: {bearing_reversal_count}")
    print(f"spatial_revisit_pairs_n: {spatial_revisit_pairs_n}")
    print(f"repeated_way_ids_n: {repeated_way_ids_n}")
    print(f"repeated_edges_n: {repeated_edges_n}")
    print(f"activity_overlay_checked: {activity_overlay_checked}")
    print(f"activity_route_axis_signals: {json.dumps(activity_route_axis_signals, ensure_ascii=False, sort_keys=True)}")
    print(f"blocking_recommendation: {blocking_recommendation}")
    print(f"output_root: {OUT_ROOT}")


if __name__ == "__main__":
    main()
