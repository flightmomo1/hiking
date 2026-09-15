#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
IB0B Global Traversal Prototype v0.5 — P3 Identity Contract / Generic Gates

Requires, in the same directory:
- ib0b_global_traversal_v0_2.py
- ib0b_global_traversal_v0_3.py

P3 goal
-------
Infer one complete ordered OSM traversal for the full GPX by combining:
- local observation evidence at sparse DP keyframes;
- transition routing over the FULL IB0 candidate graph;
- transition length consistency;
- bidirectional transition-vs-GPX geometry evidence.

Important architecture rules
----------------------------
1. Local top-K limits only DP ENDPOINT states.
2. The transition routing graph remains complete; legacy selected=0 ways are
   still routable and may appear as transition-only edges.
3. No artificial connector, GPX straight-line fallback, or target-way whitelist.
4. Repeated directed OSM edges are legal and preserved as separate occurrences.
5. Canonical OSM identity is preserved; edge_id never replaces osm_id/osm_way_id.
6. P3 is a prototype. Cost scales are diagnostic defaults, not product thresholds.
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point

import ib0b_global_traversal_v0_2 as base
import ib0b_global_traversal_v0_3 as p2


VERSION = "v0.5.1-p3-regression-gate-fix"
IDENTITY_CONTRACT = "canonical_osm_type_id_v1"
REGRESSION_WAYS = ("1273335252", "631600007")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="IB0B Global Traversal v0.5.1 P3 regression gate fix"
    )
    p.add_argument("--case-id", required=True)
    p.add_argument("--activity-fp", required=True)
    p.add_argument("--candidate-fp", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument(
        "--gpx-role",
        choices=("recorded_track", "planned_route"),
        default="recorded_track",
    )

    # P0/P1 evidence inputs.
    p.add_argument("--observation-spacing-m", type=float, default=20.0)
    p.add_argument("--candidate-search-radius-m", type=float, default=100.0)
    p.add_argument("--top-k", type=int, default=0)
    p.add_argument("--distance-sigma-m", type=float, default=15.0)
    p.add_argument("--heading-weight", type=float, default=0.5)
    p.add_argument("--semantic-weight", type=float, default=0.1)

    # P2 transition engine.
    p.add_argument("--transition-path-k", type=int, default=2)
    p.add_argument("--transition-sample-step-m", type=float, default=5.0)
    p.add_argument("--transition-length-weight", type=float, default=1.0)
    p.add_argument("--transition-geometry-weight", type=float, default=1.0)

    # P3 DP.
    p.add_argument(
        "--dp-keyframe-spacing-m",
        type=float,
        default=120.0,
        help=(
            "Approximate GPX progress interval between DP layers. Intermediate "
            "GPX geometry is still used by transition scoring."
        ),
    )
    p.add_argument(
        "--dp-local-k",
        type=int,
        default=8,
        help=(
            "Top local directed endpoint states per DP layer. This does NOT "
            "prune the transition routing graph."
        ),
    )
    p.add_argument(
        "--dp-observation-weight",
        type=float,
        default=1.0,
    )
    p.add_argument(
        "--dp-transition-weight",
        type=float,
        default=1.0,
    )
    p.add_argument(
        "--regression-profile",
        choices=("none", "muzhishan-v1"),
        default="none",
        help=(
            "Optional testcase regression profile. Production gates remain "
            "generic; testcase-specific expectations are evaluated separately."
        ),
    )
    return p.parse_args()


def normalize_candidates(cand: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Canonical osm_type + osm_id, with legacy osm_element_type fallback."""
    if cand.crs is None:
        raise RuntimeError("Candidate GeoJSON has no CRS")

    required = {"osm_id", "osm_way_id", "geometry"}
    missing = sorted(required - set(cand.columns))
    if missing:
        raise RuntimeError(f"Missing required candidate columns: {missing}")

    has_canonical = "osm_type" in cand.columns
    has_legacy = "osm_element_type" in cand.columns
    if not has_canonical and not has_legacy:
        raise RuntimeError(
            "Missing OSM type identity: expected osm_type or osm_element_type"
        )

    out = cand.copy()
    canonical = (
        out["osm_type"].astype("string").str.lower()
        if has_canonical
        else pd.Series(pd.NA, index=out.index, dtype="string")
    )
    legacy = (
        out["osm_element_type"].astype("string").str.lower()
        if has_legacy
        else pd.Series(pd.NA, index=out.index, dtype="string")
    )

    if has_canonical and has_legacy:
        mismatch = canonical.notna() & legacy.notna() & canonical.ne(legacy)
        if bool(mismatch.any()):
            cols = [c for c in ["osm_type", "osm_element_type", "osm_id", "osm_way_id"] if c in out.columns]
            raise RuntimeError(
                "IB0B_IDENTITY_CONTRACT_FAIL: osm_type / osm_element_type mismatch. Sample:\n"
                + out.loc[mismatch, cols].head(10).to_string(index=False)
            )

    out["osm_type"] = canonical.fillna(legacy)
    out["osm_element_type"] = out["osm_type"]
    out["osm_id"] = out["osm_id"].map(base.norm_id)
    out["osm_way_id"] = out["osm_way_id"].map(base.norm_id)

    if "geometry_source" in out.columns:
        non_osm = ~out["geometry_source"].astype("string").eq("osm")
        non_osm = non_osm.fillna(True)
        if bool(non_osm.any()):
            cols = [c for c in ["geometry_source", "evidence_id", "osm_type", "osm_id"] if c in out.columns]
            raise RuntimeError(
                "IB0B graph input must contain OSM evidence only; activity/GPX fallback rows "
                "cannot become OSM graph edges. Sample:\n"
                + out.loc[non_osm, cols].head(10).to_string(index=False)
            )

    base.validate_candidate_schema(out)

    canonical_ok = (
        out["osm_type"].astype("string").eq("way")
        & out["osm_id"].astype("string").ne("")
        & out["osm_way_id"].astype("string").ne("")
        & out["osm_id"].astype("string").eq(out["osm_way_id"].astype("string"))
    )
    if not bool(canonical_ok.all()):
        raise RuntimeError(
            "IB0B_IDENTITY_CONTRACT_FAIL: canonical way identity is incomplete"
        )

    return out


def nearest_observation_index(
    observations: gpd.GeoDataFrame,
    progress_m: float,
) -> int:
    idx = (
        observations["gpx_progress_m"] - float(progress_m)
    ).abs().idxmin()
    return int(observations.loc[idx, "observation_index"])


def build_keyframe_indices(
    observations: gpd.GeoDataFrame,
    gpx_length_m: float,
    spacing_m: float,
) -> List[int]:
    if spacing_m <= 0:
        raise ValueError("--dp-keyframe-spacing-m must be > 0")

    targets = []
    d = 0.0
    while d < gpx_length_m:
        targets.append(d)
        d += spacing_m
    targets.append(float(gpx_length_m))

    indices = []
    for target in targets:
        oi = nearest_observation_index(observations, target)
        if not indices or oi != indices[-1]:
            indices.append(oi)

    first_idx = int(observations.iloc[0]["observation_index"])
    last_idx = int(observations.iloc[-1]["observation_index"])

    if not indices or indices[0] != first_idx:
        indices.insert(0, first_idx)
    if indices[-1] != last_idx:
        indices.append(last_idx)

    return indices


def build_layer_pools(
    scored: pd.DataFrame,
    keyframe_indices: List[int],
    local_k: int,
) -> Dict[int, pd.DataFrame]:
    if local_k <= 0:
        raise ValueError("--dp-local-k must be > 0")

    pools = {}
    for layer_idx, obs_idx in enumerate(keyframe_indices):
        pool = (
            scored[scored["observation_index"] == obs_idx]
            .sort_values(
                ["observation_cost", "distance_m", "edge_id"]
            )
            .head(local_k)
            .copy()
        )
        if pool.empty:
            raise RuntimeError(
                f"No endpoint candidate states for keyframe layer {layer_idx}, "
                f"observation {obs_idx}"
            )
        pools[layer_idx] = pool
    return pools


def best_transition_between(
    a: pd.Series,
    b: pd.Series,
    state_by_id: Dict[str, pd.Series],
    route_graph,
    gpx_m: LineString,
    args,
):
    variants = p2.evaluate_transition_pair(
        a,
        b,
        state_by_id,
        route_graph,
        gpx_m,
        args,
    )
    if not variants:
        return None

    # P3 chooses among P2 path variants using transition evidence only.
    # Observation costs are handled once by the DP recurrence.
    variants = sorted(
        variants,
        key=lambda tr: (
            float(tr["transition_cost"]),
            abs(float(tr["length_delta_m"])),
            float(tr["osm_path_length_m"]),
        ),
    )
    return variants[0]


def run_global_dp(
    keyframe_indices: List[int],
    pools: Dict[int, pd.DataFrame],
    states: gpd.GeoDataFrame,
    route_graph,
    gpx_m: LineString,
    args,
):
    state_by_id = {
        str(r["edge_id"]): r
        for _, r in states.iterrows()
    }

    # dp[layer][edge_id] = accumulated cost
    dp: List[Dict[str, float]] = []
    back: List[Dict[str, dict]] = []
    layer_rows = []

    first_pool = pools[0]
    first_costs = {}
    first_back = {}

    for _, row in first_pool.iterrows():
        eid = str(row["edge_id"])
        first_costs[eid] = (
            float(args.dp_observation_weight)
            * float(row["observation_cost"])
        )
        first_back[eid] = {
            "prev_edge_id": None,
            "transition": None,
            "candidate": row,
        }

    dp.append(first_costs)
    back.append(first_back)

    layer_rows.append(
        {
            "layer_index": 0,
            "observation_index": int(keyframe_indices[0]),
            "pool_n": int(len(first_pool)),
            "reachable_state_n": int(len(first_costs)),
            "evaluated_pair_n": 0,
            "valid_transition_variant_n": 0,
            "best_cumulative_cost": float(min(first_costs.values())),
            "status": "START",
        }
    )

    failed_layer = None

    for layer_idx in range(1, len(keyframe_indices)):
        prev_pool = pools[layer_idx - 1]
        curr_pool = pools[layer_idx]

        prev_rows = {
            str(r["edge_id"]): r
            for _, r in prev_pool.iterrows()
        }
        curr_rows = {
            str(r["edge_id"]): r
            for _, r in curr_pool.iterrows()
        }

        curr_costs: Dict[str, float] = {}
        curr_back: Dict[str, dict] = {}

        evaluated_pair_n = 0
        valid_variant_n = 0

        for curr_eid, b in curr_rows.items():
            best_cost = math.inf
            best_prev = None
            best_tr = None

            for prev_eid, prev_acc in dp[layer_idx - 1].items():
                a = prev_rows.get(prev_eid)
                if a is None:
                    continue

                evaluated_pair_n += 1
                tr = best_transition_between(
                    a,
                    b,
                    state_by_id,
                    route_graph,
                    gpx_m,
                    args,
                )
                if tr is None:
                    continue

                valid_variant_n += 1

                step_cost = (
                    float(args.dp_transition_weight)
                    * float(tr["transition_cost"])
                    + float(args.dp_observation_weight)
                    * float(b["observation_cost"])
                )
                total = float(prev_acc) + step_cost

                if total < best_cost:
                    best_cost = total
                    best_prev = prev_eid
                    best_tr = tr

            if best_prev is not None:
                curr_costs[curr_eid] = best_cost
                curr_back[curr_eid] = {
                    "prev_edge_id": best_prev,
                    "transition": best_tr,
                    "candidate": b,
                }

        dp.append(curr_costs)
        back.append(curr_back)

        if curr_costs:
            layer_rows.append(
                {
                    "layer_index": layer_idx,
                    "observation_index": int(keyframe_indices[layer_idx]),
                    "pool_n": int(len(curr_pool)),
                    "reachable_state_n": int(len(curr_costs)),
                    "evaluated_pair_n": int(evaluated_pair_n),
                    "valid_transition_variant_n": int(valid_variant_n),
                    "best_cumulative_cost": float(min(curr_costs.values())),
                    "status": "PASS",
                }
            )
        else:
            failed_layer = layer_idx
            layer_rows.append(
                {
                    "layer_index": layer_idx,
                    "observation_index": int(keyframe_indices[layer_idx]),
                    "pool_n": int(len(curr_pool)),
                    "reachable_state_n": 0,
                    "evaluated_pair_n": int(evaluated_pair_n),
                    "valid_transition_variant_n": int(valid_variant_n),
                    "best_cumulative_cost": float("nan"),
                    "status": "NO_VALID_TRANSITION",
                }
            )
            break

    if failed_layer is not None:
        return {
            "complete": False,
            "failed_layer": failed_layer,
            "layer_rows": layer_rows,
            "selected_states": [],
            "selected_transitions": [],
            "total_cost": None,
        }

    final_layer = len(keyframe_indices) - 1
    final_eid = min(dp[final_layer], key=dp[final_layer].get)
    total_cost = float(dp[final_layer][final_eid])

    selected_states_rev = []
    selected_transitions_rev = []
    eid = final_eid

    for layer_idx in range(final_layer, -1, -1):
        info = back[layer_idx][eid]
        cand = info["candidate"]
        selected_states_rev.append(
            {
                "layer_index": layer_idx,
                "observation_index": int(cand["observation_index"]),
                "gpx_progress_m": float(cand["gpx_progress_m"]),
                "edge_id": str(cand["edge_id"]),
                "osm_type": str(cand.get("osm_type", cand["osm_element_type"])),
                "osm_id": str(cand["osm_id"]),
                "osm_way_id": str(cand["osm_way_id"]),
                "direction": str(cand["direction"]),
                "distance_m": float(cand["distance_m"]),
                "observation_cost": float(cand["observation_cost"]),
                "observation_rank": int(cand["observation_rank"]),
                "edge_projection_m": float(cand["edge_projection_m"]),
                "edge_projection_fraction": float(cand["edge_projection_fraction"]),
                "cumulative_cost": float(dp[layer_idx][eid]),
            }
        )

        if layer_idx > 0:
            tr = info["transition"]
            tr_copy = dict(tr)
            tr_copy["transition_index"] = layer_idx - 1
            selected_transitions_rev.append(tr_copy)
            eid = str(info["prev_edge_id"])

    selected_states = list(reversed(selected_states_rev))
    selected_transitions = list(reversed(selected_transitions_rev))

    return {
        "complete": True,
        "failed_layer": None,
        "layer_rows": layer_rows,
        "selected_states": selected_states,
        "selected_transitions": selected_transitions,
        "total_cost": total_cost,
    }


def strict_merge_transition_geometries(
    transitions: List[dict],
    tolerance_m: float = 1e-5,
) -> LineString:
    coords = []

    for idx, tr in enumerate(transitions):
        geom = tr["route_geom"]
        if geom is None or geom.is_empty or geom.geom_type != "LineString":
            raise RuntimeError(
                f"Transition {idx} has invalid route geometry"
            )

        c = list(geom.coords)
        if len(c) < 2:
            raise RuntimeError(
                f"Transition {idx} has fewer than two coordinates"
            )

        if not coords:
            coords.extend(c)
            continue

        gap = Point(coords[-1]).distance(Point(c[0]))
        if gap > tolerance_m:
            raise RuntimeError(
                "Non-contiguous chosen transitions; refusing to create an "
                f"artificial connector. transition={idx}, gap_m={gap:.9f}"
            )

        coords.extend(c[1:])

    if len(coords) < 2:
        raise RuntimeError("Global traversal geometry is empty")

    return LineString(coords)


def expand_traversal_edges(
    selected_states: List[dict],
    selected_transitions: List[dict],
    states: gpd.GeoDataFrame,
) -> pd.DataFrame:
    state_by_id = {
        str(r["edge_id"]): r
        for _, r in states.iterrows()
    }

    # Lookup the exact selected keyframe state at each layer.
    selected_by_layer = {
        int(r["layer_index"]): r
        for r in selected_states
    }

    rows = []
    occurrence_counter = Counter()
    traversal_order = 0

    def append_occurrence(
        edge_id: str,
        transition_index: int,
        entry_fraction: float,
        exit_fraction: float,
        endpoint_role: str,
    ):
        nonlocal traversal_order
        state = state_by_id[str(edge_id)]

        entry_fraction = max(0.0, min(1.0, float(entry_fraction)))
        exit_fraction = max(0.0, min(1.0, float(exit_fraction)))

        if exit_fraction < entry_fraction:
            return

        fraction = exit_fraction - entry_fraction
        if fraction <= 1e-12:
            return

        occurrence_counter[str(edge_id)] += 1
        traversal_order += 1

        rows.append(
            {
                "traversal_order": traversal_order,
                "transition_index": int(transition_index),
                "edge_id": str(edge_id),
                "edge_occurrence": int(occurrence_counter[str(edge_id)]),
                "osm_type": str(state.get("osm_type", state["osm_element_type"])),
                "osm_element_type": str(state["osm_element_type"]),
                "osm_id": str(state["osm_id"]),
                "osm_way_id": str(state["osm_way_id"]),
                "edge_index": int(state["edge_index"]),
                "direction": str(state["direction"]),
                "name": state.get("name", ""),
                "highway_norm": state.get("highway_norm", ""),
                "route_role": state.get("route_role", ""),
                "legacy_selected": state.get("selected", None),
                "entry_fraction": float(entry_fraction),
                "exit_fraction": float(exit_fraction),
                "traversed_fraction": float(fraction),
                "edge_length_m": float(state["edge_length_m"]),
                "traversed_length_m": float(state["edge_length_m"]) * fraction,
                "endpoint_role": endpoint_role,
            }
        )

    for tr_idx, tr in enumerate(selected_transitions):
        edge_ids = [x for x in str(tr["path_edge_ids"]).split(";") if x]
        if not edge_ids:
            continue

        from_state = selected_by_layer[tr_idx]
        to_state = selected_by_layer[tr_idx + 1]

        from_frac = float(from_state["edge_projection_fraction"])
        to_frac = float(to_state["edge_projection_fraction"])

        if tr["path_variant"] == "same_directed_edge":
            append_occurrence(
                edge_ids[0],
                tr_idx,
                from_frac,
                to_frac,
                "both_endpoints",
            )
            continue

        if len(edge_ids) == 1:
            # General graph route can theoretically leave the end of an edge,
            # return to its start node, and then re-enter the same directed edge.
            append_occurrence(
                edge_ids[0],
                tr_idx,
                from_frac,
                1.0,
                "from_endpoint",
            )
            append_occurrence(
                edge_ids[0],
                tr_idx,
                0.0,
                to_frac,
                "to_endpoint",
            )
            continue

        append_occurrence(
            edge_ids[0],
            tr_idx,
            from_frac,
            1.0,
            "from_endpoint",
        )

        for edge_id in edge_ids[1:-1]:
            append_occurrence(
                edge_id,
                tr_idx,
                0.0,
                1.0,
                "transition_only",
            )

        append_occurrence(
            edge_ids[-1],
            tr_idx,
            0.0,
            to_frac,
            "to_endpoint",
        )

    return pd.DataFrame(rows)


def transition_summary_rows(selected_transitions: List[dict]) -> pd.DataFrame:
    rows = []
    for tr in selected_transitions:
        rows.append(
            {
                k: v
                for k, v in tr.items()
                if k != "route_geom"
            }
        )
    return pd.DataFrame(rows)


def target_way_transition_report(
    selected_transitions: List[dict],
    target_way_id: str,
) -> dict:
    matched = []
    for tr in selected_transitions:
        ways = {x for x in str(tr["path_way_ids"]).split(";") if x}
        if str(target_way_id) in ways:
            matched.append(tr)

    if not matched:
        return {
            "transition_n": 0,
            "gpx_to_osm_p95_max_m": None,
            "osm_to_gpx_p95_max_m": None,
            "osm_to_gpx_max_max_m": None,
        }

    return {
        "transition_n": len(matched),
        "gpx_to_osm_p95_max_m": max(
            float(x["gpx_to_osm_p95_m"]) for x in matched
        ),
        "osm_to_gpx_p95_max_m": max(
            float(x["osm_to_gpx_p95_m"]) for x in matched
        ),
        "osm_to_gpx_max_max_m": max(
            float(x["osm_to_gpx_max_m"]) for x in matched
        ),
    }


def write_failure_summary(
    out_dir: Path,
    prefix: str,
    summary: dict,
    layer_rows: List[dict],
):
    pd.DataFrame(layer_rows).to_csv(
        out_dir / f"{prefix}_p3_dp_layers.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame([summary]).to_csv(
        out_dir / f"{prefix}_p3_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------
    # Reuse frozen P0/P1/P2 contracts.
    # ---------------------------------------------------------
    raw_cand = gpd.read_file(args.candidate_fp)
    identity_input_source = (
        "osm_type" if "osm_type" in raw_cand.columns
        else "osm_element_type_legacy_alias"
    )
    cand = normalize_candidates(raw_cand)
    cand_wgs = (
        cand.to_crs("EPSG:4326")
        if cand.crs.to_epsg() != 4326
        else cand.copy()
    )

    metric_crs = cand_wgs.estimate_utm_crs()
    if metric_crs is None:
        raise RuntimeError("Could not estimate metric CRS")
    cand_m = cand_wgs.to_crs(metric_crs)

    gpx_wgs = gpd.GeoSeries(
        [base.load_gpx_linestring(args.activity_fp)],
        crs="EPSG:4326",
    )
    gpx_m = gpx_wgs.to_crs(metric_crs).iloc[0]

    G_u, G_d, states, node_xy, node_way_membership = (
        base.build_graph_and_states(cand_wgs, cand_m)
    )

    # Frozen v0.2 emits the legacy alias. Re-establish canonical osm_type here.
    states = states.copy()
    states["osm_type"] = states["osm_element_type"].astype("string").str.lower()

    route_graph = p2.make_route_graph(states)

    candidate_way_ids = set(cand_wgs["osm_way_id"].astype(str))
    state_way_ids = set(states["osm_way_id"].astype(str))
    full_candidate_graph_pass = (
        bool(candidate_way_ids) and candidate_way_ids.issubset(state_way_ids)
    )
    canonical_identity_pass = bool(
        cand_wgs["osm_type"].astype("string").eq("way").all()
        and cand_wgs["osm_id"].astype("string").ne("").all()
        and cand_wgs["osm_way_id"].astype("string").ne("").all()
        and cand_wgs["osm_id"].astype("string")
            .eq(cand_wgs["osm_way_id"].astype("string")).all()
    )

    observations = base.sample_observations(
        gpx_m,
        args.observation_spacing_m,
    ).set_crs(metric_crs)

    obs_candidates = base.build_observation_candidates(
        observations,
        states,
        args.candidate_search_radius_m,
        args.top_k,
    )
    obs_candidates = obs_candidates.copy()
    if not obs_candidates.empty:
        obs_candidates["osm_type"] = (
            obs_candidates["osm_element_type"].astype("string").str.lower()
        )

    scored = base.score_observation_candidates(
        obs_candidates,
        args.distance_sigma_m,
        args.heading_weight,
        args.semantic_weight,
    )
    scored = p2.add_edge_projection(scored, observations, states)

    keyframes = build_keyframe_indices(
        observations,
        float(gpx_m.length),
        args.dp_keyframe_spacing_m,
    )
    pools = build_layer_pools(
        scored,
        keyframes,
        args.dp_local_k,
    )

    print("=" * 60)
    print("IB0B GLOBAL TRAVERSAL v0.5.1 — P3 REGRESSION GATE FIX")
    print("=" * 60)
    print("prototype version:", VERSION)
    print("case:", args.case_id)
    print("gpx_role:", args.gpx_role)
    print("metric CRS:", metric_crs)
    print()
    print("=== INPUT / GRAPH ===")
    print("candidate features:", len(cand_wgs))
    print("identity contract:", IDENTITY_CONTRACT)
    print("identity input source:", identity_input_source)
    print("canonical identity:", "PASS" if canonical_identity_pass else "FAIL")
    print(
        "full candidate graph identity coverage:",
        f"{len(candidate_way_ids & state_way_ids)}/{len(candidate_way_ids)}",
    )
    print("routing graph nodes:", route_graph.number_of_nodes())
    print("routing graph edges:", route_graph.number_of_edges())
    print("routing graph source: FULL IB0 candidate graph")
    print("artificial connectors:", 0)
    print()
    print("=== GPX / DP LAYERS ===")
    print("GPX length m:", round(float(gpx_m.length), 2))
    print("observation spacing m:", args.observation_spacing_m)
    print("observations:", len(observations))
    print("DP keyframe spacing m:", args.dp_keyframe_spacing_m)
    print("DP layers:", len(keyframes))
    print("DP local endpoint K:", args.dp_local_k)
    print("transition path K:", args.transition_path_k)

    result = run_global_dp(
        keyframes,
        pools,
        states,
        route_graph,
        gpx_m,
        args,
    )

    prefix = args.case_id
    layers_fp = out_dir / f"{prefix}_p3_dp_layers.csv"
    states_fp = out_dir / f"{prefix}_p3_selected_keyframe_states.csv"
    transitions_fp = out_dir / f"{prefix}_p3_selected_transitions.csv"
    edges_fp = out_dir / f"{prefix}_p3_traversal_edges.csv"
    route_fp = out_dir / f"{prefix}_p3_global_traversal.geojson"
    summary_fp = out_dir / f"{prefix}_p3_summary.csv"

    pd.DataFrame(result["layer_rows"]).to_csv(
        layers_fp,
        index=False,
        encoding="utf-8-sig",
    )

    if not result["complete"]:
        summary = {
            "prototype_version": VERSION,
            "case_id": args.case_id,
            "gpx_role": args.gpx_role,
            "dp_complete": False,
            "failed_layer": result["failed_layer"],
            "candidate_feature_n": len(cand_wgs),
            "routing_graph_node_n": route_graph.number_of_nodes(),
            "routing_graph_edge_n": route_graph.number_of_edges(),
            "observation_n": len(observations),
            "dp_layer_n": len(keyframes),
            "dp_local_k": args.dp_local_k,
            "artificial_connector_n": 0,
        }
        pd.DataFrame([summary]).to_csv(
            summary_fp,
            index=False,
            encoding="utf-8-sig",
        )

        print()
        print("=== P3 RESULT ===")
        print("DP complete: FAIL")
        print("failed layer:", result["failed_layer"])
        print("No fallback connector was created.")
        print("OVERALL P3: FAIL")
        print()
        print("Outputs:")
        print(" DP layers:", layers_fp)
        print(" summary:", summary_fp)
        return 2

    selected_states = result["selected_states"]
    selected_transitions = result["selected_transitions"]

    global_route = strict_merge_transition_geometries(
        selected_transitions
    )

    traversal_edges = expand_traversal_edges(
        selected_states,
        selected_transitions,
        states,
    )

    selected_states_df = pd.DataFrame(selected_states)
    selected_transitions_df = transition_summary_rows(
        selected_transitions
    )

    selected_states_df.to_csv(
        states_fp,
        index=False,
        encoding="utf-8-sig",
    )
    selected_transitions_df.to_csv(
        transitions_fp,
        index=False,
        encoding="utf-8-sig",
    )
    traversal_edges.to_csv(
        edges_fp,
        index=False,
        encoding="utf-8-sig",
    )

    route_props = {
        "case_id": args.case_id,
        "pipeline_stage": "ib0b_global_traversal_p3_v0_5",
        "prototype_version": VERSION,
        "gpx_role": args.gpx_role,
        "geometry_source": "osm_graph_traversal",
        "artificial_connector_n": 0,
        "total_cost": float(result["total_cost"]),
    }
    route_gdf = gpd.GeoDataFrame(
        [route_props],
        geometry=[global_route],
        crs=metric_crs,
    ).to_crs("EPSG:4326")
    route_gdf.to_file(route_fp, driver="GeoJSON")

    global_geom = p2.geometry_metrics(
        global_route,
        gpx_m,
        args.transition_sample_step_m,
    )

    traversal_length_m = float(global_route.length)
    gpx_length_m = float(gpx_m.length)
    length_ratio = traversal_length_m / max(gpx_length_m, 1.0)

    way_counts = Counter(
        traversal_edges["osm_way_id"].astype(str)
        if not traversal_edges.empty
        else []
    )
    edge_counts = Counter(
        traversal_edges["edge_id"].astype(str)
        if not traversal_edges.empty
        else []
    )

    selected_endpoint_ways = {
        str(x["osm_way_id"])
        for x in selected_states
    }
    traversed_ways = set(way_counts.keys())

    r1_present = "1273335252" in traversed_ways
    r1_transition_only = (
        r1_present
        and "1273335252" not in selected_endpoint_ways
    )
    r2_present = "631600007" in traversed_ways

    r1_report = target_way_transition_report(
        selected_transitions,
        "1273335252",
    )
    r2_report = target_way_transition_report(
        selected_transitions,
        "631600007",
    )

    repeated_edge_n = sum(
        1 for n in edge_counts.values() if n > 1
    )
    repeated_way_n = sum(
        1 for n in way_counts.values() if n > 1
    )

    max_trans_o2g_p95 = max(
        float(x["osm_to_gpx_p95_m"])
        for x in selected_transitions
    )
    max_trans_g2o_p95 = max(
        float(x["gpx_to_osm_p95_m"])
        for x in selected_transitions
    )

    summary = {
        "prototype_version": VERSION,
        "case_id": args.case_id,
        "gpx_role": args.gpx_role,
        "metric_crs": str(metric_crs),
        "dp_complete": True,
        "failed_layer": None,
        "candidate_feature_n": int(len(cand_wgs)),
        "routing_graph_node_n": int(route_graph.number_of_nodes()),
        "routing_graph_edge_n": int(route_graph.number_of_edges()),
        "observation_n": int(len(observations)),
        "dp_layer_n": int(len(keyframes)),
        "dp_local_k": int(args.dp_local_k),
        "transition_path_k": int(args.transition_path_k),
        "total_cost": float(result["total_cost"]),
        "gpx_length_m": gpx_length_m,
        "traversal_length_m": traversal_length_m,
        "length_ratio": length_ratio,
        "gpx_to_osm_mean_m": global_geom["gpx_to_osm_mean_m"],
        "gpx_to_osm_p95_m": global_geom["gpx_to_osm_p95_m"],
        "gpx_to_osm_max_m": global_geom["gpx_to_osm_max_m"],
        "osm_to_gpx_mean_m": global_geom["osm_to_gpx_mean_m"],
        "osm_to_gpx_p95_m": global_geom["osm_to_gpx_p95_m"],
        "osm_to_gpx_max_m": global_geom["osm_to_gpx_max_m"],
        "max_selected_transition_gpx_to_osm_p95_m": max_trans_g2o_p95,
        "max_selected_transition_osm_to_gpx_p95_m": max_trans_o2g_p95,
        "traversal_edge_occurrence_n": int(len(traversal_edges)),
        "unique_traversal_edge_n": int(len(edge_counts)),
        "unique_traversal_way_n": int(len(way_counts)),
        "repeated_edge_n": int(repeated_edge_n),
        "repeated_way_n": int(repeated_way_n),
        "way_1273335252_present": bool(r1_present),
        "way_1273335252_transition_only": bool(r1_transition_only),
        "way_1273335252_transition_n": int(r1_report["transition_n"]),
        "way_631600007_present": bool(r2_present),
        "way_631600007_transition_n": int(r2_report["transition_n"]),
        "way_631600007_osm_to_gpx_p95_max_m": r2_report[
            "osm_to_gpx_p95_max_m"
        ],
        "way_631600007_osm_to_gpx_max_max_m": r2_report[
            "osm_to_gpx_max_max_m"
        ],
        "identity_contract": IDENTITY_CONTRACT,
        "identity_input_source": identity_input_source,
        "canonical_identity_pass": bool(canonical_identity_pass),
        "full_candidate_graph_pass": bool(full_candidate_graph_pass),
        "regression_profile": args.regression_profile,
        "artificial_connector_n": 0,
    }

    pd.DataFrame([summary]).to_csv(
        summary_fp,
        index=False,
        encoding="utf-8-sig",
    )

    # ---------------------------------------------------------
    # Console QA
    # ---------------------------------------------------------
    print()
    print("=== P3 GLOBAL RESULT ===")
    print("DP complete: PASS")
    print("selected keyframe states:", len(selected_states))
    print("selected transitions:", len(selected_transitions))
    print("total cost:", round(float(result["total_cost"]), 4))
    print("GPX length m:", round(gpx_length_m, 2))
    print("traversal length m:", round(traversal_length_m, 2))
    print("length ratio:", round(length_ratio, 4))
    print(
        "global GPX->OSM mean/p95/max m:",
        round(global_geom["gpx_to_osm_mean_m"], 2),
        round(global_geom["gpx_to_osm_p95_m"], 2),
        round(global_geom["gpx_to_osm_max_m"], 2),
    )
    print(
        "global OSM->GPX mean/p95/max m:",
        round(global_geom["osm_to_gpx_mean_m"], 2),
        round(global_geom["osm_to_gpx_p95_m"], 2),
        round(global_geom["osm_to_gpx_max_m"], 2),
    )
    print(
        "max selected transition GPX->OSM p95 m:",
        round(max_trans_g2o_p95, 2),
    )
    print(
        "max selected transition OSM->GPX p95 m:",
        round(max_trans_o2g_p95, 2),
    )
    print("traversal edge occurrences:", len(traversal_edges))
    print("unique traversal edges:", len(edge_counts))
    print("unique traversal ways:", len(way_counts))
    print("repeated edges:", repeated_edge_n)
    print("repeated ways:", repeated_way_n)

    print()
    print("=== REGRESSION WAYS IN GLOBAL TRAVERSAL ===")
    print(
        "1273335252 present:",
        r1_present,
        "| transition_only:",
        r1_transition_only,
        "| transition_n:",
        r1_report["transition_n"],
    )
    print(
        "631600007 present:",
        r2_present,
        "| transition_n:",
        r2_report["transition_n"],
        "| OSM->GPX p95 max m:",
        r2_report["osm_to_gpx_p95_max_m"],
        "| OSM->GPX max max m:",
        r2_report["osm_to_gpx_max_max_m"],
    )

    # v0.5 separates route-independent production gates from testcase regression.
    production_gates = {
        "canonical_identity": bool(canonical_identity_pass),
        "full_candidate_graph": bool(full_candidate_graph_pass),
        "dp_complete_start_to_end": True,
        "global_geometry_contiguous": True,
        "no_artificial_connectors": True,
        "ordered_edge_traversal_emitted": not traversal_edges.empty,
    }

    regression_gates = {}
    if args.regression_profile == "muzhishan-v1":
        # Normal-P3 regression expectations only.
        # 1273335252 is a P3B counterfactual target and remains diagnostic only.
        regression_gates = {
            "muzhishan_candidate_count_167": int(len(cand_wgs)) == 167,
            "muzhishan_631600007_in_global_traversal": bool(r2_present),
        }
    print()
    print("=" * 60)
    print("P3 PRODUCTION GATE SUMMARY")
    print("=" * 60)
    for name, ok in production_gates.items():
        print(f"{name}: {'PASS' if ok else 'FAIL'}")

    production_overall = all(production_gates.values())
    print("OVERALL P3 PRODUCTION:", "PASS" if production_overall else "FAIL")

    regression_overall = True
    if regression_gates:
        print()
        print("=" * 60)
        print("P3 TESTCASE REGRESSION GATE SUMMARY:", args.regression_profile)
        print("=" * 60)
        for name, ok in regression_gates.items():
            print(f"{name}: {'PASS' if ok else 'FAIL'}")
        regression_overall = all(regression_gates.values())
        print("OVERALL P3 REGRESSION:", "PASS" if regression_overall else "FAIL")
    else:
        print()
        print("P3 testcase regression profile: none")

    overall = production_overall and regression_overall
    print("OVERALL P3:", "PASS" if overall else "FAIL")

    print()
    print("Outputs:")
    print(" DP layers:", layers_fp)
    print(" selected keyframe states:", states_fp)
    print(" selected transitions:", transitions_fp)
    print(" ordered traversal edges:", edges_fp)
    print(" global traversal geometry:", route_fp)
    print(" summary:", summary_fp)

    return 0 if overall else 2


if __name__ == "__main__":
    sys.exit(main())
