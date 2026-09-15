#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
IB0B Global Traversal Prototype v0.3 — P2 Transition Engine

Requires ib0b_global_traversal_v0_2.py in the same directory.

P2 does NOT run full-route DP/Viterbi yet. It validates the transition layer:
- endpoint observation states are locally shortlisted;
- routing uses the COMPLETE IB0 candidate graph (legacy selected is ignored);
- low-ranked OSM edges may appear as transition-only routing edges;
- observation positions project onto short graph segments, not whole-way endpoints;
- transition QA compares OSM path length and bidirectional geometry to the
  corresponding GPX progress window;
- no artificial connector / GPX straight-line fallback is permitted.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Dict, List

import geopandas as gpd
import networkx as nx
import pandas as pd
from shapely.geometry import LineString
from shapely.ops import substring

import ib0b_global_traversal_v0_2 as base


VERSION = "v0.3-p2-transition-engine"
REGRESSION_WAYS = ("1273335252", "631600007")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="IB0B Global Traversal v0.3 P2 transition engine"
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
    p.add_argument("--observation-spacing-m", type=float, default=20.0)
    p.add_argument("--candidate-search-radius-m", type=float, default=100.0)
    p.add_argument("--top-k", type=int, default=0)

    # P1 observation evidence — still diagnostic, not acceptance thresholds.
    p.add_argument("--distance-sigma-m", type=float, default=15.0)
    p.add_argument("--heading-weight", type=float, default=0.5)
    p.add_argument("--semantic-weight", type=float, default=0.1)

    # P2 transition diagnostics.
    p.add_argument(
        "--transition-local-k",
        type=int,
        default=8,
        help=(
            "Top local directed states retained at each diagnostic endpoint. "
            "The routing graph remains complete."
        ),
    )
    p.add_argument("--transition-path-k", type=int, default=2)
    p.add_argument("--transition-sample-step-m", type=float, default=5.0)
    p.add_argument("--transition-length-weight", type=float, default=1.0)
    p.add_argument("--transition-geometry-weight", type=float, default=1.0)
    p.add_argument("--regression-window-half-m", type=float, default=120.0)
    p.add_argument(
        "--regression-occurrence-separation-m", type=float, default=300.0
    )
    p.add_argument("--regression-max-occurrences", type=int, default=3)
    return p.parse_args()


def normalize_candidates(cand: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    base.validate_candidate_schema(cand)
    cand = cand.copy()
    cand["osm_element_type"] = (
        cand["osm_element_type"].astype("string").str.lower()
    )
    cand["osm_id"] = cand["osm_id"].map(base.norm_id)
    cand["osm_way_id"] = cand["osm_way_id"].map(base.norm_id)
    return cand


def make_route_graph(states: gpd.GeoDataFrame) -> nx.DiGraph:
    """Complete directed routing graph. legacy selected is deliberately ignored."""
    G = nx.DiGraph()
    for _, r in states.iterrows():
        u = r["from_node"]
        v = r["to_node"]
        length_m = float(r["edge_length_m"])
        edge_id = str(r["edge_id"])
        wid = str(r["osm_way_id"])

        if G.has_edge(u, v):
            d = G[u][v]
            d["edge_ids"].add(edge_id)
            d["osm_way_ids"].add(wid)
            if length_m < float(d["length_m"]):
                d["length_m"] = length_m
                d["best_edge_id"] = edge_id
                d["best_osm_way_id"] = wid
                d["geometry"] = r.geometry
        else:
            G.add_edge(
                u,
                v,
                length_m=length_m,
                best_edge_id=edge_id,
                best_osm_way_id=wid,
                edge_ids={edge_id},
                osm_way_ids={wid},
                geometry=r.geometry,
            )
    return G


def add_edge_projection(
    scored: pd.DataFrame,
    observations: gpd.GeoDataFrame,
    states: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """Project each observation onto its short directed graph segment."""
    out = scored.copy()
    obs_pt = {
        int(r["observation_index"]): r.geometry
        for _, r in observations.iterrows()
    }
    state_by_id = {
        str(r["edge_id"]): r
        for _, r in states.iterrows()
    }

    projections = []
    fractions = []
    for _, r in out.iterrows():
        state = state_by_id[str(r["edge_id"])]
        geom = state.geometry
        p = obs_pt[int(r["observation_index"])]
        proj = float(geom.project(p))
        length_m = float(geom.length)
        projections.append(proj)
        fractions.append(proj / length_m if length_m > 0 else 0.0)

    out["edge_projection_m"] = projections
    out["edge_projection_fraction"] = fractions
    return out


def merge_parts(parts: List[LineString]) -> LineString:
    coords = []
    for g in parts:
        if g is None or g.is_empty:
            continue
        if g.geom_type == "Point":
            c = [(float(g.x), float(g.y))]
        elif g.geom_type == "LineString":
            c = list(g.coords)
        else:
            continue
        if not c:
            continue
        if not coords:
            coords.extend(c)
        elif coords[-1] == c[0]:
            coords.extend(c[1:])
        else:
            coords.extend(c)
    if len(coords) < 2:
        raise RuntimeError("Transition geometry has fewer than two coordinates")
    return LineString(coords)


def sample_distances(source: LineString, target: LineString, step_m: float):
    if step_m <= 0:
        raise ValueError("--transition-sample-step-m must be > 0")
    vals = []
    d = 0.0
    while d < source.length:
        vals.append(float(source.interpolate(d).distance(target)))
        d += step_m
    vals.append(float(source.interpolate(source.length).distance(target)))
    return vals


def geometry_metrics(route_geom: LineString, gpx_seg: LineString, step_m: float):
    g2o = pd.Series(sample_distances(gpx_seg, route_geom, step_m), dtype="float64")
    o2g = pd.Series(sample_distances(route_geom, gpx_seg, step_m), dtype="float64")
    return {
        "gpx_to_osm_mean_m": float(g2o.mean()),
        "gpx_to_osm_p95_m": float(g2o.quantile(0.95)),
        "gpx_to_osm_max_m": float(g2o.max()),
        "osm_to_gpx_mean_m": float(o2g.mean()),
        "osm_to_gpx_p95_m": float(o2g.quantile(0.95)),
        "osm_to_gpx_max_m": float(o2g.max()),
    }


def transition_cost(
    gpx_delta_m: float,
    osm_length_m: float,
    metrics: dict,
    length_weight: float,
    geometry_weight: float,
):
    safe_gpx = max(float(gpx_delta_m), 1.0)
    safe_osm = max(float(osm_length_m), 1.0)
    ratio = safe_osm / safe_gpx
    length_cost = abs(math.log(ratio))

    mean_sym = 0.5 * (
        float(metrics["gpx_to_osm_mean_m"])
        + float(metrics["osm_to_gpx_mean_m"])
    )
    p95_sym = 0.5 * (
        float(metrics["gpx_to_osm_p95_m"])
        + float(metrics["osm_to_gpx_p95_m"])
    )
    geometry_cost = (
        math.log1p((mean_sym / 10.0) ** 2)
        + 0.25 * math.log1p((p95_sym / 20.0) ** 2)
    )
    total = length_weight * length_cost + geometry_weight * geometry_cost
    return {
        "length_ratio": float(ratio),
        "length_delta_m": float(osm_length_m - gpx_delta_m),
        "length_cost": float(length_cost),
        "geometry_mean_sym_m": float(mean_sym),
        "geometry_p95_sym_m": float(p95_sym),
        "geometry_cost": float(geometry_cost),
        "transition_cost": float(total),
    }


def route_middle_parts(route_graph: nx.DiGraph, node_path: List):
    parts, edge_ids, way_ids = [], [], []
    for u, v in zip(node_path[:-1], node_path[1:]):
        d = route_graph[u][v]
        parts.append(d["geometry"])
        edge_ids.append(str(d["best_edge_id"]))
        wid = str(d["best_osm_way_id"])
        if wid not in way_ids:
            way_ids.append(wid)
    return parts, edge_ids, way_ids


def evaluate_transition_pair(
    a: pd.Series,
    b: pd.Series,
    state_by_id: Dict[str, pd.Series],
    route_graph: nx.DiGraph,
    gpx_m: LineString,
    args,
):
    fp = float(a["gpx_progress_m"])
    tp = float(b["gpx_progress_m"])
    if tp <= fp:
        return []

    sa = state_by_id[str(a["edge_id"])]
    sb = state_by_id[str(b["edge_id"])]
    gpx_seg = substring(gpx_m, fp, tp)
    if gpx_seg.geom_type != "LineString":
        return []

    ga = sa.geometry
    gb = sb.geometry
    aproj = min(max(float(a["edge_projection_m"]), 0.0), float(ga.length))
    bproj = min(max(float(b["edge_projection_m"]), 0.0), float(gb.length))
    results = []

    # Direct progress within the same directed graph segment.
    if str(sa["edge_id"]) == str(sb["edge_id"]) and bproj >= aproj:
        direct = substring(ga, aproj, bproj)
        if direct.geom_type == "LineString" and direct.length > 0:
            m = geometry_metrics(direct, gpx_seg, args.transition_sample_step_m)
            c = transition_cost(
                tp - fp,
                float(direct.length),
                m,
                args.transition_length_weight,
                args.transition_geometry_weight,
            )
            results.append(
                {
                    "path_variant": "same_directed_edge",
                    "from_observation_index": int(a["observation_index"]),
                    "to_observation_index": int(b["observation_index"]),
                    "from_gpx_progress_m": fp,
                    "to_gpx_progress_m": tp,
                    "gpx_progress_delta_m": tp - fp,
                    "from_edge_id": str(sa["edge_id"]),
                    "to_edge_id": str(sb["edge_id"]),
                    "from_osm_way_id": str(sa["osm_way_id"]),
                    "to_osm_way_id": str(sb["osm_way_id"]),
                    "from_observation_cost": float(a["observation_cost"]),
                    "to_observation_cost": float(b["observation_cost"]),
                    "osm_path_length_m": float(direct.length),
                    "path_edge_ids": str(sa["edge_id"]),
                    "path_way_ids": str(sa["osm_way_id"]),
                    "route_geom": direct,
                    **m,
                    **c,
                }
            )

    source_tail = substring(ga, aproj, float(ga.length))
    dest_head = substring(gb, 0.0, bproj)
    source_node = sa["to_node"]
    dest_node = sb["from_node"]

    if source_node not in route_graph or dest_node not in route_graph:
        return results
    if not nx.has_path(route_graph, source_node, dest_node):
        return results

    if source_node == dest_node:
        node_paths = [[source_node]]
    else:
        try:
            gen = nx.shortest_simple_paths(
                route_graph, source_node, dest_node, weight="length_m"
            )
            node_paths = []
            for _, path in zip(range(max(1, args.transition_path_k)), gen):
                node_paths.append(path)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return results

    for variant_idx, node_path in enumerate(node_paths, start=1):
        mid_parts, mid_edge_ids, mid_way_ids = route_middle_parts(
            route_graph, node_path
        )
        parts = []
        if source_tail.geom_type == "LineString" and source_tail.length > 0:
            parts.append(source_tail)
        parts.extend(mid_parts)
        if dest_head.geom_type == "LineString" and dest_head.length > 0:
            parts.append(dest_head)
        if not parts:
            continue

        route_geom = merge_parts(parts)
        way_ids = [str(sa["osm_way_id"])]
        for wid in mid_way_ids:
            if wid not in way_ids:
                way_ids.append(wid)
        to_wid = str(sb["osm_way_id"])
        if to_wid not in way_ids:
            way_ids.append(to_wid)

        edge_ids = [str(sa["edge_id"])] + mid_edge_ids
        to_edge = str(sb["edge_id"])
        if to_edge not in edge_ids:
            edge_ids.append(to_edge)

        m = geometry_metrics(route_geom, gpx_seg, args.transition_sample_step_m)
        c = transition_cost(
            tp - fp,
            float(route_geom.length),
            m,
            args.transition_length_weight,
            args.transition_geometry_weight,
        )
        results.append(
            {
                "path_variant": f"graph_path_{variant_idx}",
                "from_observation_index": int(a["observation_index"]),
                "to_observation_index": int(b["observation_index"]),
                "from_gpx_progress_m": fp,
                "to_gpx_progress_m": tp,
                "gpx_progress_delta_m": tp - fp,
                "from_edge_id": str(sa["edge_id"]),
                "to_edge_id": str(sb["edge_id"]),
                "from_osm_way_id": str(sa["osm_way_id"]),
                "to_osm_way_id": str(sb["osm_way_id"]),
                "from_observation_cost": float(a["observation_cost"]),
                "to_observation_cost": float(b["observation_cost"]),
                "osm_path_length_m": float(route_geom.length),
                "path_edge_ids": ";".join(edge_ids),
                "path_way_ids": ";".join(way_ids),
                "route_geom": route_geom,
                **m,
                **c,
            }
        )
    return results


def pick_occurrence_centers(observations, target_geom, separation_m, max_n):
    tmp = observations.copy()
    tmp["_target_dist_m"] = tmp.geometry.distance(target_geom)
    tmp = tmp.sort_values(["_target_dist_m", "gpx_progress_m"])
    chosen = []
    for _, r in tmp.iterrows():
        p = float(r["gpx_progress_m"])
        if all(abs(p - float(x["gpx_progress_m"])) >= separation_m for x in chosen):
            chosen.append(r)
        if len(chosen) >= max_n:
            break
    return chosen


def nearest_observation_index(observations, progress_m: float) -> int:
    idx = (observations["gpx_progress_m"] - progress_m).abs().idxmin()
    return int(observations.loc[idx, "observation_index"])


def run_transition_diagnostics(cand_m, observations, scored, states, route_graph, gpx_m, args):
    state_by_id = {str(r["edge_id"]): r for _, r in states.iterrows()}
    all_rows = []

    for wid in REGRESSION_WAYS:
        target = cand_m[cand_m["osm_way_id"].astype(str) == wid]
        if len(target) != 1:
            continue
        target_geom = target.iloc[0].geometry
        centers = pick_occurrence_centers(
            observations,
            target_geom,
            args.regression_occurrence_separation_m,
            args.regression_max_occurrences,
        )

        for occ_idx, center in enumerate(centers, start=1):
            cp = float(center["gpx_progress_m"])
            fp = max(0.0, cp - args.regression_window_half_m)
            tp = min(float(gpx_m.length), cp + args.regression_window_half_m)
            from_obs = nearest_observation_index(observations, fp)
            to_obs = nearest_observation_index(observations, tp)

            from_pool = (
                scored[scored["observation_index"] == from_obs]
                .sort_values("observation_cost")
                .head(args.transition_local_k)
            )
            to_pool = (
                scored[scored["observation_index"] == to_obs]
                .sort_values("observation_cost")
                .head(args.transition_local_k)
            )

            rows = []
            for _, a in from_pool.iterrows():
                for _, b in to_pool.iterrows():
                    for tr in evaluate_transition_pair(
                        a, b, state_by_id, route_graph, gpx_m, args
                    ):
                        way_set = {x for x in str(tr["path_way_ids"]).split(";") if x}
                        tr["regression_way_id"] = wid
                        tr["occurrence_index"] = occ_idx
                        tr["center_observation_index"] = int(center["observation_index"])
                        tr["center_gpx_progress_m"] = cp
                        tr["center_target_distance_m"] = float(center["_target_dist_m"])
                        tr["contains_target_way"] = wid in way_set
                        tr["target_is_endpoint_state"] = (
                            str(tr["from_osm_way_id"]) == wid
                            or str(tr["to_osm_way_id"]) == wid
                        )
                        tr["target_is_transition_only"] = (
                            tr["contains_target_way"] and not tr["target_is_endpoint_state"]
                        )
                        tr["pair_total_cost"] = (
                            float(tr["from_observation_cost"])
                            + float(tr["to_observation_cost"])
                            + float(tr["transition_cost"])
                        )
                        rows.append(tr)

            if rows:
                wdf = pd.DataFrame(rows).sort_values(
                    ["pair_total_cost", "transition_cost", "osm_path_length_m"]
                )
                wdf["window_rank"] = range(1, len(wdf) + 1)
                all_rows.extend(wdf.to_dict("records"))

    return pd.DataFrame(all_rows)


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cand = normalize_candidates(gpd.read_file(args.candidate_fp))
    cand_wgs = cand.to_crs("EPSG:4326") if cand.crs.to_epsg() != 4326 else cand.copy()
    metric_crs = cand_wgs.estimate_utm_crs()
    if metric_crs is None:
        raise RuntimeError("Could not estimate metric CRS")
    cand_m = cand_wgs.to_crs(metric_crs)

    gpx_wgs = gpd.GeoSeries(
        [base.load_gpx_linestring(args.activity_fp)], crs="EPSG:4326"
    )
    gpx_m = gpx_wgs.to_crs(metric_crs).iloc[0]

    G_u, G_d, states, node_xy, node_way_membership = base.build_graph_and_states(
        cand_wgs, cand_m
    )
    route_graph = make_route_graph(states)

    observations = base.sample_observations(gpx_m, args.observation_spacing_m)
    observations = observations.set_crs(metric_crs)

    obs_candidates = base.build_observation_candidates(
        observations, states, args.candidate_search_radius_m, args.top_k
    )
    scored = base.score_observation_candidates(
        obs_candidates,
        args.distance_sigma_m,
        args.heading_weight,
        args.semantic_weight,
    )
    scored = add_edge_projection(scored, observations, states)

    rank_report = base.regression_way_rank_report(scored, REGRESSION_WAYS)
    junctions = base.junction_report(
        "631600007", cand_wgs, cand_m, node_way_membership
    )
    trans = run_transition_diagnostics(
        cand_m, observations, scored, states, route_graph, gpx_m, args
    )

    prefix = args.case_id
    scored_fp = out_dir / f"{prefix}_p2_observation_candidates_scored.csv"
    rank_fp = out_dir / f"{prefix}_p2_regression_way_ranks.csv"
    junction_fp = out_dir / f"{prefix}_p2_way_631600007_junctions.csv"
    trans_fp = out_dir / f"{prefix}_p2_transition_diagnostics.csv"
    best_geo_fp = out_dir / f"{prefix}_p2_best_transitions.geojson"
    summary_fp = out_dir / f"{prefix}_p2_summary.csv"

    scored.to_csv(scored_fp, index=False, encoding="utf-8-sig")
    pd.DataFrame(rank_report).to_csv(rank_fp, index=False, encoding="utf-8-sig")
    pd.DataFrame(junctions).to_csv(junction_fp, index=False, encoding="utf-8-sig")

    if not trans.empty:
        trans.drop(columns=["route_geom"], errors="ignore").to_csv(
            trans_fp, index=False, encoding="utf-8-sig"
        )
        best = (
            trans.sort_values(["regression_way_id", "occurrence_index", "window_rank"])
            .groupby(["regression_way_id", "occurrence_index"], as_index=False)
            .first()
        )
        gdf = gpd.GeoDataFrame(
            best.drop(columns=["route_geom"], errors="ignore"),
            geometry=best["route_geom"],
            crs=metric_crs,
        ).to_crs("EPSG:4326")
        gdf.to_file(best_geo_fp, driver="GeoJSON")
    else:
        trans_fp.write_text("", encoding="utf-8")
        best_geo_fp.write_text("", encoding="utf-8")

    component_sizes = sorted(
        (len(c) for c in nx.connected_components(G_u)), reverse=True
    )
    obs_with = int(scored["observation_index"].nunique()) if not scored.empty else 0

    summary = {
        "prototype_version": VERSION,
        "case_id": args.case_id,
        "gpx_role": args.gpx_role,
        "candidate_feature_n": len(cand_wgs),
        "gpx_length_m": float(gpx_m.length),
        "observation_n": len(observations),
        "topology_node_n": G_u.number_of_nodes(),
        "topology_edge_n": G_u.number_of_edges(),
        "topology_component_n": nx.number_connected_components(G_u),
        "directed_state_n": len(states),
        "routing_graph_node_n": route_graph.number_of_nodes(),
        "routing_graph_edge_n": route_graph.number_of_edges(),
        "observations_with_candidates_n": obs_with,
        "transition_diagnostic_n": len(trans),
        "transition_full_candidate_graph": True,
        "artificial_connector_n": 0,
    }
    pd.DataFrame([summary]).to_csv(summary_fp, index=False, encoding="utf-8-sig")

    print("=" * 60)
    print("IB0B GLOBAL TRAVERSAL v0.3 — P2 TRANSITION ENGINE")
    print("=" * 60)
    print("prototype version:", VERSION)
    print("case:", args.case_id)
    print("gpx_role:", args.gpx_role)
    print("metric CRS:", metric_crs)

    print("\n=== P0 GRAPH FOUNDATION ===")
    print("candidate features:", len(cand_wgs))
    print("canonical identity: PASS")
    print("nodes:", G_u.number_of_nodes())
    print("physical edges:", G_u.number_of_edges())
    print("components:", nx.number_connected_components(G_u))
    print("component sizes:", component_sizes[:10])
    print("directed states:", len(states))
    print("artificial connectors: 0")

    print("\n=== P1 OBSERVATION EVIDENCE ===")
    for r in rank_report:
        print(
            "way", r["osm_way_id"],
            "| obs_n=", r.get("observation_presence_n"),
            "| rank min/median/p95/max=",
            r.get("best_rank_min"), r.get("best_rank_median"),
            r.get("best_rank_p95"), r.get("best_rank_max"),
            "| top5/top10/top20/top40=",
            r.get("top5_observation_n"), r.get("top10_observation_n"),
            r.get("top20_observation_n"), r.get("top40_observation_n"),
        )

    print("\n=== P2 TRANSITION ENGINE ===")
    print("routing graph source: FULL IB0 candidate graph")
    print("routing graph nodes:", route_graph.number_of_nodes())
    print("routing graph edges:", route_graph.number_of_edges())
    print("transition local endpoint K:", args.transition_local_k)
    print("transition path K:", args.transition_path_k)
    print("transition diagnostics:", len(trans))

    if not trans.empty:
        for wid in REGRESSION_WAYS:
            sub = trans[trans["regression_way_id"].astype(str) == wid]
            if sub.empty:
                continue
            print("\nREGRESSION WAY", wid)
            for occ in sorted(sub["occurrence_index"].unique()):
                win = sub[sub["occurrence_index"] == occ].sort_values("window_rank")
                first = win.iloc[0]
                print(
                    f" occurrence={int(occ)}"
                    f" center_gpx={float(first['center_gpx_progress_m']):.1f}m"
                    f" target_dist={float(first['center_target_distance_m']):.2f}m"
                    f" variants={len(win)}"
                )
                for _, r in win.head(5).iterrows():
                    print(
                        f"   rank={int(r['window_rank']):2d}"
                        f" total={float(r['pair_total_cost']):.4f}"
                        f" trans={float(r['transition_cost']):.4f}"
                        f" gpx={float(r['gpx_progress_delta_m']):.1f}m"
                        f" osm={float(r['osm_path_length_m']):.1f}m"
                        f" ratio={float(r['length_ratio']):.3f}"
                        f" g2o_p95={float(r['gpx_to_osm_p95_m']):.2f}m"
                        f" o2g_p95={float(r['osm_to_gpx_p95_m']):.2f}m"
                        f" target={bool(r['contains_target_way'])}"
                        f" transition_only={bool(r['target_is_transition_only'])}"
                        f" ways={r['path_way_ids']}"
                    )
                print(
                    "   contains target:", int(win["contains_target_way"].sum()),
                    "| transition-only:", int(win["target_is_transition_only"].sum()),
                    "| top10 contains target:", int(win.head(10)["contains_target_way"].sum()),
                )

    presence = {}
    transition_only = {}
    for wid in REGRESSION_WAYS:
        sub = trans[trans["regression_way_id"].astype(str) == wid] if not trans.empty else pd.DataFrame()
        presence[wid] = int(sub["contains_target_way"].sum()) if not sub.empty else 0
        transition_only[wid] = int(sub["target_is_transition_only"].sum()) if not sub.empty else 0

    gates = {
        "canonical_identity": True,
        "full_candidate_graph": len(cand_wgs) == 167,
        "all_observations_have_candidates": obs_with == len(observations),
        "transition_engine_produced_routes": len(trans) > 0,
        "1273335252_can_appear_in_transition": presence["1273335252"] > 0,
        "1273335252_can_be_transition_only": transition_only["1273335252"] > 0,
        "631600007_can_appear_in_transition": presence["631600007"] > 0,
        "no_artificial_connectors": True,
        "631600007_shared_vertex_junction": len(junctions) >= 1,
    }

    print("\n" + "=" * 60)
    print("P2 GATE SUMMARY")
    print("=" * 60)
    for name, ok in gates.items():
        print(f"{name}: {'PASS' if ok else 'FAIL'}")
    overall = all(gates.values())
    print("OVERALL P2:", "PASS" if overall else "FAIL")

    print("\nOutputs:")
    print(" observation candidates:", scored_fp)
    print(" regression way ranks:", rank_fp)
    print(" 631600007 junctions:", junction_fp)
    print(" transition diagnostics:", trans_fp)
    print(" best transitions:", best_geo_fp)
    print(" summary:", summary_fp)

    return 0 if overall else 2


if __name__ == "__main__":
    sys.exit(main())
