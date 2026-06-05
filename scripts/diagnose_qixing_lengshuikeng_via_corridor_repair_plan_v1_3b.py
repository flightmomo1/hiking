# -*- coding: utf-8 -*-
"""
Build a read-only repair plan for the qixing_lengshuikeng via corridor route-axis issue.

This script does not modify IB0B/IB0D/IB3 outputs and does not rerun any pipeline.
It consumes the via corridor oscillation audit evidence plus current v1.3b route
baseline files, then separates legitimate spatial revisits from suspected local
bounce / micro-loop / repeated connector behavior.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import folium
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


CASE_ID = "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b"
AUDIT_ROOT = Path("outputs/qixing_lengshuikeng_via_corridor_route_axis_oscillation_audit_v1_3b")
IB0D_ROOT = Path("outputs/ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa") / CASE_ID
IB1_ROOT = Path("outputs/ib1_route_profile_v1_3b_contract_qa") / CASE_ID
IB1E_ROOT = Path("outputs/ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa") / CASE_ID
OUT_ROOT = Path("outputs/qixing_lengshuikeng_via_corridor_repair_plan_v1_3b")

PROBLEM_SEGMENT_PAD_M = 25.0
NEAR_SEQUENCE_MIN_REPEAT_N = 2
HIGH_SPATIAL_REVISIT_PAIR_N = 100
HIGH_ACTIVITY_REVERSAL_N = 20


def read_csv_or_empty(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 5:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def load_inputs() -> dict[str, Any]:
    summary_path = AUDIT_ROOT / "qixing_lengshuikeng_via_corridor_route_axis_oscillation_summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"Missing oscillation summary JSON: {summary_path}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    route_window = read_csv_or_empty(AUDIT_ROOT / "qixing_lengshuikeng_via_corridor_route_window.csv")
    reversals = read_csv_or_empty(AUDIT_ROOT / "qixing_lengshuikeng_via_corridor_bearing_reversals.csv")
    revisits = read_csv_or_empty(AUDIT_ROOT / "qixing_lengshuikeng_via_corridor_spatial_revisit_pairs.csv")
    repeated_edges = read_csv_or_empty(AUDIT_ROOT / "qixing_lengshuikeng_via_corridor_repeated_edges.csv")
    activity_overlay = read_csv_or_empty(AUDIT_ROOT / "qixing_lengshuikeng_via_corridor_activity_overlay_summary.csv")
    return {
        "summary": summary,
        "route_window": route_window,
        "reversals": reversals,
        "revisits": revisits,
        "repeated_edges": repeated_edges,
        "activity_overlay": activity_overlay,
    }


def add_segment(segments: list[dict[str, Any]], start: float, end: float, issue_type: str, severity: str, reason: str) -> None:
    segments.append(
        {
            "case_id": CASE_ID,
            "start_dist_m": round(float(start), 3),
            "end_dist_m": round(float(end), 3),
            "segment_len_m": round(max(0.0, float(end) - float(start)), 3),
            "issue_type": issue_type,
            "severity": severity,
            "reason": reason,
        }
    )


def detect_bounce_segments(summary: dict[str, Any]) -> list[dict[str, Any]]:
    sequence = summary.get("near_via_sequence", [])
    segments: list[dict[str, Any]] = []
    if not sequence:
        return segments

    # Repeated visits to the same via label separated by a short away interval
    # are treated as suspected local bounce. A legitimate ascent/descent revisit
    # is expected to have a large route_dist gap and should not be collapsed here.
    for label in ["via_up", "via_down"]:
        idxs = [i for i, item in enumerate(sequence) if item.get("label") == label]
        if len(idxs) < NEAR_SEQUENCE_MIN_REPEAT_N:
            continue
        cluster: list[int] = []
        for idx in idxs:
            if not cluster:
                cluster = [idx]
                continue
            prev = cluster[-1]
            intervening = sequence[prev + 1 : idx]
            gap = float(sequence[idx]["start_dist_m"]) - float(sequence[prev]["end_dist_m"])
            has_only_away_or_both = all(x.get("label") in ["away", "both"] for x in intervening)
            if gap <= 250.0 and has_only_away_or_both:
                cluster.append(idx)
            else:
                if len(cluster) >= NEAR_SEQUENCE_MIN_REPEAT_N:
                    start = sequence[cluster[0]]["start_dist_m"]
                    end = sequence[cluster[-1]]["end_dist_m"]
                    add_segment(
                        segments,
                        start,
                        end,
                        "control_point_bounce_near_sequence",
                        "high",
                        f"{label} appears {len(cluster)} times with short away gaps in route order.",
                    )
                cluster = [idx]
        if len(cluster) >= NEAR_SEQUENCE_MIN_REPEAT_N:
            start = sequence[cluster[0]]["start_dist_m"]
            end = sequence[cluster[-1]]["end_dist_m"]
            add_segment(
                segments,
                start,
                end,
                "control_point_bounce_near_sequence",
                "high",
                f"{label} appears {len(cluster)} times with short away gaps in route order.",
            )

    # Alternation between via_down and via_up near the descent corridor is a
    # stronger connector-bounce signal because the two control points are spatially close.
    labels = [x.get("label") for x in sequence]
    for i in range(len(sequence) - 2):
        window = labels[i : i + 3]
        if "via_down" in window and "via_up" in window and "away" in window:
            start = sequence[i]["start_dist_m"]
            end = sequence[i + 2]["end_dist_m"]
            if end - start <= 250.0:
                add_segment(
                    segments,
                    start,
                    end,
                    "via_up_via_down_connector_bounce",
                    "high",
                    "route order alternates between spatially close via_down/via_up neighborhoods over a short route-axis interval.",
                )
    return segments


def detect_bearing_segments(reversals: pd.DataFrame) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    if reversals.empty or "route_dist_m" not in reversals.columns:
        return segments
    for row in reversals.itertuples(index=False):
        dist = float(getattr(row, "route_dist_m"))
        bearing_change = float(getattr(row, "bearing_change_deg", np.nan))
        add_segment(
            segments,
            dist - PROBLEM_SEGMENT_PAD_M,
            dist + PROBLEM_SEGMENT_PAD_M,
            "bearing_reversal",
            "medium",
            f"bearing_change_deg={bearing_change:.1f} suggests local forward/back/forward geometry.",
        )
    return segments


def summarize_revisit_density(revisits: pd.DataFrame, segments: list[dict[str, Any]]) -> None:
    if revisits.empty:
        return
    for seg in segments:
        start = float(seg["start_dist_m"])
        end = float(seg["end_dist_m"])
        mask_a = pd.to_numeric(revisits["route_dist_m_a"], errors="coerce").between(start, end)
        mask_b = pd.to_numeric(revisits["route_dist_m_b"], errors="coerce").between(start, end)
        pairs_n = int((mask_a | mask_b).sum())
        seg["spatial_revisit_pairs_touching_segment_n"] = pairs_n
        if pairs_n >= HIGH_SPATIAL_REVISIT_PAIR_N and seg["severity"] == "medium":
            seg["severity"] = "high"
            seg["reason"] += f" Spatial revisit density is also high in/near this segment ({pairs_n} pairs)."


def add_activity_signal_segment(activity_overlay: pd.DataFrame, summary: dict[str, Any], segments: list[dict[str, Any]]) -> None:
    if activity_overlay.empty:
        return
    reversal_n = int(pd.to_numeric(activity_overlay.get("route_dist_projection_reversal_n", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    branch_n = int(pd.to_numeric(activity_overlay.get("branch_ambiguous_projection_rows", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    if reversal_n >= HIGH_ACTIVITY_REVERSAL_N or branch_n > 0:
        start = float(summary.get("corridor_window_start_m", np.nan))
        end = float(summary.get("corridor_window_end_m", np.nan))
        add_segment(
            segments,
            start,
            end,
            "activity_overlay_route_axis_reversal_signal",
            "medium",
            f"Existing sequence mapmatch overlay has route_dist_projection_reversal_n={reversal_n} and branch_ambiguous_projection_rows={branch_n}; use as supporting evidence only.",
        )


def merge_problem_segments(segments: list[dict[str, Any]]) -> pd.DataFrame:
    if not segments:
        return pd.DataFrame(
            columns=["case_id", "start_dist_m", "end_dist_m", "segment_len_m", "issue_type", "severity", "reason"]
        )
    df = pd.DataFrame(segments)
    df["start_dist_m"] = pd.to_numeric(df["start_dist_m"], errors="coerce").clip(lower=0)
    df["end_dist_m"] = pd.to_numeric(df["end_dist_m"], errors="coerce")
    df["segment_len_m"] = df["end_dist_m"] - df["start_dist_m"]
    return df.sort_values(["start_dist_m", "end_dist_m", "issue_type"]).reset_index(drop=True)


def choose_repair_strategy(problem_segments: pd.DataFrame, summary: dict[str, Any], activity_overlay: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    local_oscillation = bool(summary.get("local_oscillation_detected"))
    control_bounce = bool(summary.get("control_point_bounce_detected"))
    via_gap = float(summary.get("via_dist_gap_m", 0.0))
    legitimate_revisit_expected = via_gap > 500.0 and int(summary.get("spatial_revisit_pairs_n", 0)) > 0
    micro_bounce_suspected = bool(control_bounce or not problem_segments[problem_segments["issue_type"].str.contains("bounce|bearing", regex=True)].empty)

    if local_oscillation and micro_bounce_suspected:
        recommended = "IB0D local loop pruning"
        ib0d = True
        ib0b = True
        ib3_only = False
        repair_needed = True
        reason = (
            "Spatial revisit is expected because via_up/via_down are close in space but far on route axis; "
            "however repeated near-via sequence plus bearing reversals indicate suspected local bounce/micro-loop."
        )
    elif not local_oscillation and not activity_overlay.empty:
        recommended = "IB3 mapmatch compensation only"
        ib0d = False
        ib0b = False
        ib3_only = True
        repair_needed = False
        reason = "Route baseline does not show strong local oscillation; activity ambiguity can be reviewed in IB3 only."
    else:
        recommended = "no repair needed"
        ib0d = False
        ib0b = False
        ib3_only = False
        repair_needed = False
        reason = "No blocking route-axis repair signal was found."

    route_dist_max_after = "may decrease if artifact loops are pruned; should be recomputed from repaired axis while preserving summit/descent continuity"
    candidates = [
        {
            "candidate_strategy": "A. IB0B route assembly repair",
            "recommended": ib0b,
            "priority": "secondary" if ib0d and ib0b else ("primary" if ib0b else "not_recommended"),
            "rationale": "Inspect required-way stitching and control-point constrained route assembly if IB0D pruning cannot preserve continuity or if repeated connector comes from source edge ordering.",
            "source_edges_or_way_ids_to_check": collect_source_edge_hints(),
            "expected_route_dist_max_change": "unknown until route is reassembled",
        },
        {
            "candidate_strategy": "B. IB0D local loop pruning",
            "recommended": ib0d,
            "priority": "primary" if ib0d else "not_recommended",
            "rationale": "Prune only short local bounce ranges, keep legitimate via_up/via_down ascent/descent revisit and summit/descent phases intact.",
            "prune_route_dist_ranges": json.dumps(problem_segments[problem_segments["issue_type"].str.contains("bounce|bearing", regex=True)][["start_dist_m", "end_dist_m", "issue_type", "severity"]].to_dict("records"), ensure_ascii=False),
            "preserve_route_dist_continuity": True,
            "must_preserve_summit_descent_phase": True,
            "must_not_collapse_legitimate_revisit": True,
            "expected_route_dist_max_change": route_dist_max_after,
        },
        {
            "candidate_strategy": "C. IB3 mapmatch compensation only",
            "recommended": ib3_only,
            "priority": "not_recommended" if repair_needed else "fallback",
            "rationale": "Not sufficient when current route-axis evidence itself shows bounce/reversal.",
            "expected_route_dist_max_change": "none",
        },
        {
            "candidate_strategy": "D. no repair needed",
            "recommended": not repair_needed,
            "priority": "not_recommended" if repair_needed else "primary",
            "rationale": "Rejected when local bounce and bearing reversal are present.",
            "expected_route_dist_max_change": "none",
        },
    ]
    decision = {
        "repair_needed": repair_needed,
        "recommended_repair_layer": recommended,
        "reason": reason,
        "legitimate_revisit_expected": legitimate_revisit_expected,
        "micro_bounce_suspected": micro_bounce_suspected,
        "ib0b_repair_recommended": ib0b,
        "ib0d_pruning_recommended": ib0d,
        "ib3_only_review_recommended": ib3_only,
    }
    return pd.DataFrame(candidates), decision


def collect_source_edge_hints() -> str:
    path = AUDIT_ROOT / "qixing_lengshuikeng_via_corridor_route_window.csv"
    route = read_csv_or_empty(path)
    if route.empty:
        return "No route window available."
    hint_cols = [c for c in ["osm_way_id", "osm_way_name", "osm_highway", "osm_surface", "osm_incline"] if c in route.columns]
    if not hint_cols:
        return "No OSM way/source edge columns available in corridor route window."
    chunks = []
    for col in hint_cols:
        vals = route[col].dropna().astype(str)
        vals = vals[vals.str.strip() != ""].unique().tolist()[:20]
        chunks.append(f"{col}: {vals if vals else 'none'}")
    return " | ".join(chunks)


def build_png(route: pd.DataFrame, problem_segments: pd.DataFrame, out_png: Path) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    axes[0].plot(route["route_dist_m"], route["bearing_deg"], color="#2563eb", linewidth=1)
    axes[0].scatter(route.loc[pd.to_numeric(route["bearing_change_deg"], errors="coerce") >= 150, "route_dist_m"],
                    route.loc[pd.to_numeric(route["bearing_change_deg"], errors="coerce") >= 150, "bearing_deg"],
                    color="#dc2626", label="bearing reversal")
    axes[0].set_ylabel("bearing_deg")
    axes[0].legend(loc="best")
    axes[1].plot(route["route_dist_m"], route["distance_to_via_up_m"], label="distance_to_via_up_m", color="#16a34a")
    axes[1].plot(route["route_dist_m"], route["distance_to_via_down_m"], label="distance_to_via_down_m", color="#f97316")
    for seg in problem_segments.itertuples(index=False):
        color = "#fee2e2" if seg.severity == "high" else "#fef3c7"
        for ax in axes:
            ax.axvspan(float(seg.start_dist_m), float(seg.end_dist_m), color=color, alpha=0.5)
    axes[1].set_xlabel("route_dist_m")
    axes[1].set_ylabel("distance to via (m)")
    axes[1].legend(loc="best")
    fig.suptitle("Qixing via corridor repair planning diagnostic")
    fig.tight_layout()
    fig.savefig(out_png, dpi=160)
    plt.close(fig)


def build_html(route: pd.DataFrame, problem_segments: pd.DataFrame, out_html: Path) -> None:
    center = [float(route["lat"].mean()), float(route["lon"].mean())]
    m = folium.Map(location=center, zoom_start=16, tiles="OpenStreetMap")
    folium.PolyLine(route[["lat", "lon"]].values.tolist(), color="#2563eb", weight=4, tooltip="corridor route").add_to(m)
    for seg in problem_segments.itertuples(index=False):
        w = route[pd.to_numeric(route["route_dist_m"], errors="coerce").between(float(seg.start_dist_m), float(seg.end_dist_m))]
        if w.empty:
            continue
        color = "#dc2626" if seg.severity == "high" else "#f59e0b"
        folium.PolyLine(
            w[["lat", "lon"]].values.tolist(),
            color=color,
            weight=6,
            tooltip=f"{seg.issue_type}: {seg.start_dist_m}-{seg.end_dist_m}m",
        ).add_to(m)
    m.save(str(out_html))


def main() -> None:
    inputs = load_inputs()
    summary = inputs["summary"]
    route = inputs["route_window"]
    reversals = inputs["reversals"]
    revisits = inputs["revisits"]
    activity_overlay = inputs["activity_overlay"]

    if route.empty:
        raise RuntimeError("Route corridor window is empty; cannot build repair plan.")

    segments: list[dict[str, Any]] = []
    segments.extend(detect_bounce_segments(summary))
    segments.extend(detect_bearing_segments(reversals))
    add_activity_signal_segment(activity_overlay, summary, segments)
    summarize_revisit_density(revisits, segments)
    problem_segments = merge_problem_segments(segments)

    repair_candidates, decision = choose_repair_strategy(problem_segments, summary, activity_overlay)

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    problem_segments.to_csv(OUT_ROOT / "qixing_lengshuikeng_via_corridor_problem_segments.csv", index=False, encoding="utf-8-sig")
    repair_candidates.to_csv(OUT_ROOT / "qixing_lengshuikeng_via_corridor_repair_candidates.csv", index=False, encoding="utf-8-sig")

    summary_json = {
        "case_id": CASE_ID,
        **decision,
        "suspected_problem_segments_n": int(len(problem_segments)),
        "spatial_revisit_pairs_n": int(summary.get("spatial_revisit_pairs_n", 0)),
        "bearing_reversal_count": int(summary.get("bearing_reversal_count", 0)),
        "control_point_bounce_detected": bool(summary.get("control_point_bounce_detected")),
        "forward_back_forward_detected": bool(summary.get("forward_back_forward_detected")),
        "via_up_route_dist_m": summary.get("via_up_route_dist_m"),
        "via_down_route_dist_m": summary.get("via_down_route_dist_m"),
        "via_dist_gap_m": summary.get("via_dist_gap_m"),
        "problem_segments_csv": str(OUT_ROOT / "qixing_lengshuikeng_via_corridor_problem_segments.csv"),
        "repair_candidates_csv": str(OUT_ROOT / "qixing_lengshuikeng_via_corridor_repair_candidates.csv"),
        "diagnostic_png": str(OUT_ROOT / "qixing_lengshuikeng_via_corridor_repair_plan_diagnostic.png"),
        "diagnostic_html": str(OUT_ROOT / "qixing_lengshuikeng_via_corridor_repair_plan_diagnostic.html"),
        "input_roots": {
            "via_corridor_audit_root": str(AUDIT_ROOT),
            "ib0d_root": str(IB0D_ROOT),
            "ib1_route_profile_root": str(IB1_ROOT),
            "ib1e_route_context_root": str(IB1E_ROOT),
        },
        "next_action": (
            "Plan a constrained IB0D local-loop pruning experiment on a separate output root; "
            "inspect IB0B source edge ordering if pruning cannot preserve route continuity."
        )
        if decision["repair_needed"]
        else "No baseline repair experiment recommended at this stage.",
        "note": (
            "Spatial revisit alone is treated as expected for close via_up/via_down locations with a large route-axis gap. "
            "Suspected problem segments require bounce/reversal/activity overlay evidence."
        ),
        "runtime_llm_allowed": False,
    }
    (OUT_ROOT / "qixing_lengshuikeng_via_corridor_repair_plan_summary.json").write_text(
        json.dumps(summary_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    build_png(route, problem_segments, OUT_ROOT / "qixing_lengshuikeng_via_corridor_repair_plan_diagnostic.png")
    build_html(route, problem_segments, OUT_ROOT / "qixing_lengshuikeng_via_corridor_repair_plan_diagnostic.html")

    print("qixing via corridor repair plan diagnostic complete")
    print(f"repair_needed: {decision['repair_needed']}")
    print(f"recommended_repair_layer: {decision['recommended_repair_layer']}")
    print(f"suspected_problem_segments_n: {len(problem_segments)}")
    print(f"legitimate_revisit_expected: {decision['legitimate_revisit_expected']}")
    print(f"micro_bounce_suspected: {decision['micro_bounce_suspected']}")
    print(f"ib0b_repair_recommended: {decision['ib0b_repair_recommended']}")
    print(f"ib0d_pruning_recommended: {decision['ib0d_pruning_recommended']}")
    print(f"ib3_only_review_recommended: {decision['ib3_only_review_recommended']}")
    print(f"reason: {decision['reason']}")
    print(f"output_root: {OUT_ROOT}")


if __name__ == "__main__":
    main()
