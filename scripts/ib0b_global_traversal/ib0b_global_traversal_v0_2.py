#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
IB0B Global Traversal Prototype v0.2 — P1 observation evidence

Purpose
-------
Build and QA the data foundation for a future global GPX -> OSM traversal
inference engine.

P1 deliberately DOES NOT perform route inference yet. It extends P0 with transparent observation evidence and ranking:
1) validates canonical OSM identity;
2) loads the full IB0 candidate set (not matched-only);
3) builds a topology graph from OSM LineString vertices;
4) creates directed edge states for every OSM graph segment;
5) samples the GPX into observations;
6) generates nearby directed candidate states;
7) emits regression QA, especially for ways 1273335252 and 631600007.

Important topology rule
-----------------------
This prototype connects ways only when they share the same source coordinate
vertex. It intentionally does NOT "node" arbitrary geometric line crossings,
because doing so can create false OSM connectivity at bridges/overpasses or
other non-connected crossings when original OSM node IDs are unavailable.

This file is intentionally independent from the legacy IB0B implementation.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import geopandas as gpd
import networkx as nx
import pandas as pd
from shapely.geometry import LineString, Point


VERSION = "v0.2-p1-observation-evidence"

REGRESSION_WAYS = ("1273335252", "631600007")
JUNCTION_REGRESSION_WAY = "631600007"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="IB0B Global Traversal v0.1 P0 foundation / QA"
    )
    p.add_argument("--case-id", required=True)
    p.add_argument("--activity-fp", required=True)
    p.add_argument("--candidate-fp", required=True)
    p.add_argument("--out-dir", required=True)

    p.add_argument(
        "--gpx-role",
        choices=("recorded_track", "planned_route"),
        default="recorded_track",
        help="Semantic role of the GPX. P0 records this only; it does not alter scoring yet.",
    )
    p.add_argument(
        "--observation-spacing-m",
        type=float,
        default=20.0,
        help="GPX observation sampling interval. This is NOT a match threshold.",
    )
    p.add_argument(
        "--candidate-search-radius-m",
        type=float,
        default=100.0,
        help="Search boundary for observation candidate states. NOT an acceptance threshold.",
    )
    p.add_argument(
        "--top-k",
        type=int,
        default=0,
        help="Optional maximum number of physical edge candidates per observation. 0 = keep all.",
    )

    # P1 observation-evidence parameters.
    # These are diagnostic cost scales, NOT acceptance thresholds.
    p.add_argument(
        "--distance-sigma-m",
        type=float,
        default=15.0,
        help="Scale for robust distance cost log1p((d/sigma)^2). Not a cutoff.",
    )
    p.add_argument(
        "--heading-weight",
        type=float,
        default=0.5,
        help="Weight for directed-edge heading disagreement cost.",
    )
    p.add_argument(
        "--semantic-weight",
        type=float,
        default=0.1,
        help="Weak prior weight for legacy semantic_score. Set 0 to disable.",
    )
    return p.parse_args()


def norm_id(v) -> str:
    if v is None:
        return ""
    s = str(v)
    if s.endswith(".0"):
        s = s[:-2]
    return s


def lonlat_key(coord: Tuple[float, float], ndigits: int = 9) -> Tuple[float, float]:
    """
    Stable topology key based on source WGS84 coordinates.
    Rounding is only to absorb serialization noise; it is not a spatial snap.
    1e-9 degree is far below centimeter scale.
    """
    return (round(float(coord[0]), ndigits), round(float(coord[1]), ndigits))


def load_gpx_linestring(fp: str) -> LineString:
    tree = ET.parse(fp)
    root = tree.getroot()

    if root.tag.startswith("{"):
        uri = root.tag.split("}")[0].strip("{")
        ns = {"gpx": uri}
        paths = (".//gpx:trkpt", ".//gpx:rtept")
    else:
        ns = {}
        paths = (".//trkpt", ".//rtept")

    pts = []
    for xp in paths:
        elems = root.findall(xp, ns)
        if elems:
            pts = [
                (float(e.attrib["lon"]), float(e.attrib["lat"]))
                for e in elems
            ]
            break

    if len(pts) < 2:
        raise RuntimeError(f"GPX has fewer than 2 usable points: {fp}")

    return LineString(pts)


def validate_candidate_schema(gdf: gpd.GeoDataFrame) -> None:
    required = {
        "osm_element_type",
        "osm_id",
        "osm_way_id",
        "geometry",
    }
    missing = sorted(required - set(gdf.columns))
    if missing:
        raise RuntimeError(f"Missing required candidate columns: {missing}")

    if gdf.crs is None:
        raise RuntimeError("Candidate GeoJSON has no CRS")

    bad_geom = ~gdf.geometry.geom_type.isin(["LineString", "MultiLineString"])
    if bool(bad_geom.any()):
        counts = gdf.loc[bad_geom].geometry.geom_type.value_counts(dropna=False)
        raise RuntimeError(
            "Unsupported candidate geometry types:\n" + counts.to_string()
        )

    element_types = (
        gdf["osm_element_type"]
        .astype("string")
        .str.lower()
        .dropna()
        .unique()
        .tolist()
    )
    if any(t != "way" for t in element_types):
        raise RuntimeError(
            f"P0 expects OSM ways as route graph input; found: {element_types}"
        )

    if bool(gdf["osm_id"].isna().any()):
        raise RuntimeError("Canonical osm_id contains null values")

    if bool(gdf["osm_way_id"].isna().any()):
        raise RuntimeError("osm_way_id contains null values")

    osm_id = gdf["osm_id"].map(norm_id)
    way_id = gdf["osm_way_id"].map(norm_id)

    mismatch = osm_id != way_id
    if bool(mismatch.any()):
        sample = gdf.loc[mismatch, ["osm_id", "osm_way_id"]].head(10)
        raise RuntimeError(
            "Expected osm_id == osm_way_id for way inputs. Sample:\n"
            + sample.to_string(index=False)
        )


def iter_line_parts(geom) -> Iterable[LineString]:
    if geom is None or geom.is_empty:
        return
    if geom.geom_type == "LineString":
        yield geom
    elif geom.geom_type == "MultiLineString":
        for part in geom.geoms:
            if part is not None and not part.is_empty:
                yield part


def bearing_deg(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    if dx == 0.0 and dy == 0.0:
        return float("nan")
    # 0 = north, 90 = east
    return (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0


def build_graph_and_states(
    src_wgs: gpd.GeoDataFrame,
    src_metric: gpd.GeoDataFrame,
):
    """
    Build:
      - undirected topology graph keyed by WGS84 coordinate vertices;
      - directed routing graph;
      - directed edge-state table.

    No artificial spatial snapping and no geometric crossing noding.
    """
    G_u = nx.Graph()
    G_d = nx.MultiDiGraph()

    node_xy: Dict[Tuple[float, float], Tuple[float, float]] = {}
    node_way_membership: Dict[Tuple[float, float], set] = defaultdict(set)
    state_rows: List[dict] = []

    for row_pos in range(len(src_wgs)):
        row_wgs = src_wgs.iloc[row_pos]
        row_m = src_metric.iloc[row_pos]

        wid = norm_id(row_wgs.get("osm_way_id"))
        oid = norm_id(row_wgs.get("osm_id"))
        otype = str(row_wgs.get("osm_element_type", "")).lower()

        attrs = {
            "osm_element_type": otype,
            "osm_id": oid,
            "osm_way_id": wid,
            "name": row_wgs.get("name", ""),
            "highway": row_wgs.get("highway", ""),
            "highway_norm": row_wgs.get("highway_norm", ""),
            "route_role": row_wgs.get("route_role", ""),
            "distance_to_activity_m": row_wgs.get("distance_to_activity_m", None),
            "overlap_ratio": row_wgs.get("overlap_ratio", None),
            "semantic_score": row_wgs.get("semantic_score", None),
            "distance_score": row_wgs.get("distance_score", None),
            "match_score": row_wgs.get("match_score", None),
            "selected": row_wgs.get("selected", None),
        }

        parts_wgs = list(iter_line_parts(row_wgs.geometry))
        parts_m = list(iter_line_parts(row_m.geometry))

        if len(parts_wgs) != len(parts_m):
            raise RuntimeError(
                f"Geometry part mismatch for OSM way {wid}: "
                f"{len(parts_wgs)} vs {len(parts_m)}"
            )

        seg_global_idx = 0

        for part_idx, (lw, lm) in enumerate(zip(parts_wgs, parts_m)):
            cw = list(lw.coords)
            cm = list(lm.coords)

            if len(cw) != len(cm):
                raise RuntimeError(
                    f"Coordinate count mismatch after reprojection for way {wid}"
                )

            for local_idx, ((wa, wb), (ma, mb)) in enumerate(
                zip(zip(cw[:-1], cw[1:]), zip(cm[:-1], cm[1:]))
            ):
                na = lonlat_key(wa)
                nb = lonlat_key(wb)

                if na == nb:
                    continue

                ma_xy = (float(ma[0]), float(ma[1]))
                mb_xy = (float(mb[0]), float(mb[1]))

                seg_geom = LineString([ma_xy, mb_xy])
                length_m = float(seg_geom.length)
                if length_m <= 0:
                    continue

                node_xy.setdefault(na, ma_xy)
                node_xy.setdefault(nb, mb_xy)
                node_way_membership[na].add(wid)
                node_way_membership[nb].add(wid)

                G_u.add_node(na, x=ma_xy[0], y=ma_xy[1])
                G_u.add_node(nb, x=mb_xy[0], y=mb_xy[1])

                # A simple undirected graph is enough for connected-component QA.
                # Keep all participating way IDs on a shared physical edge.
                if G_u.has_edge(na, nb):
                    G_u[na][nb]["way_ids"].add(wid)
                    G_u[na][nb]["length_m"] = min(
                        G_u[na][nb]["length_m"], length_m
                    )
                else:
                    G_u.add_edge(
                        na,
                        nb,
                        length_m=length_m,
                        way_ids={wid},
                    )

                base = f"way:{wid}:part:{part_idx}:seg:{seg_global_idx}"

                for direction, u, v, ux, vx, geom in (
                    (
                        "forward",
                        na,
                        nb,
                        ma_xy,
                        mb_xy,
                        LineString([ma_xy, mb_xy]),
                    ),
                    (
                        "reverse",
                        nb,
                        na,
                        mb_xy,
                        ma_xy,
                        LineString([mb_xy, ma_xy]),
                    ),
                ):
                    edge_id = f"{base}:{direction}"
                    heading = bearing_deg(ux, vx)

                    edge_attrs = dict(attrs)
                    edge_attrs.update(
                        {
                            "edge_id": edge_id,
                            "edge_base_id": base,
                            "edge_index": seg_global_idx,
                            "part_index": part_idx,
                            "direction": direction,
                            "from_node": u,
                            "to_node": v,
                            "from_x": ux[0],
                            "from_y": ux[1],
                            "to_x": vx[0],
                            "to_y": vx[1],
                            "edge_length_m": length_m,
                            "edge_heading_deg": heading,
                            "geometry": geom,
                        }
                    )

                    G_d.add_edge(
                        u,
                        v,
                        key=edge_id,
                        edge_id=edge_id,
                        osm_way_id=wid,
                        osm_id=oid,
                        osm_element_type=otype,
                        length_m=length_m,
                        direction=direction,
                    )

                    state_rows.append(edge_attrs)

                seg_global_idx += 1

    states = gpd.GeoDataFrame(
        state_rows,
        geometry="geometry",
        crs=src_metric.crs,
    )

    return G_u, G_d, states, node_xy, node_way_membership


def sample_observations(
    gpx_metric: LineString,
    spacing_m: float,
) -> gpd.GeoDataFrame:
    if spacing_m <= 0:
        raise ValueError("--observation-spacing-m must be > 0")

    rows = []
    d = 0.0
    idx = 0

    while d < gpx_metric.length:
        p = gpx_metric.interpolate(d)

        # Heading from a local +/-5m window.
        lo = max(0.0, d - 5.0)
        hi = min(gpx_metric.length, d + 5.0)
        pa = gpx_metric.interpolate(lo)
        pb = gpx_metric.interpolate(hi)

        rows.append(
            {
                "observation_index": idx,
                "gpx_progress_m": float(d),
                "heading_deg": bearing_deg((pa.x, pa.y), (pb.x, pb.y)),
                "observation_confidence": 1.0,
                "geometry": p,
            }
        )

        idx += 1
        d += spacing_m

    # Always include exact end point.
    p = gpx_metric.interpolate(gpx_metric.length)
    lo = max(0.0, gpx_metric.length - 10.0)
    pa = gpx_metric.interpolate(lo)

    rows.append(
        {
            "observation_index": idx,
            "gpx_progress_m": float(gpx_metric.length),
            "heading_deg": bearing_deg((pa.x, pa.y), (p.x, p.y)),
            "observation_confidence": 1.0,
            "geometry": p,
        }
    )

    return gpd.GeoDataFrame(rows, geometry="geometry")


def circular_heading_delta(a: float, b: float) -> float:
    if pd.isna(a) or pd.isna(b):
        return float("nan")
    d = abs(float(a) - float(b)) % 360.0
    return min(d, 360.0 - d)


def build_observation_candidates(
    observations: gpd.GeoDataFrame,
    states: gpd.GeoDataFrame,
    radius_m: float,
    top_k: int,
) -> pd.DataFrame:
    if radius_m <= 0:
        raise ValueError("--candidate-search-radius-m must be > 0")

    # Search physical segment once, then emit its two directed states.
    # forward/reverse pairs share edge_base_id.
    physical = states[states["direction"] == "forward"].copy()

    rows = []

    for _, obs in observations.iterrows():
        p = obs.geometry

        # P0 size is small enough for an explicit distance calculation and this
        # keeps behavior transparent across GeoPandas/Shapely versions.
        dists = physical.geometry.distance(p)
        mask = dists <= radius_m

        nearby = physical.loc[mask].copy()
        nearby["_distance_m"] = dists.loc[mask]

        nearby = nearby.sort_values(
            ["_distance_m", "osm_way_id", "edge_index"]
        )

        if top_k > 0:
            nearby = nearby.head(top_k)

        for _, base_row in nearby.iterrows():
            base_id = base_row["edge_base_id"]
            pair = states[states["edge_base_id"] == base_id]

            for _, state in pair.iterrows():
                rows.append(
                    {
                        "observation_index": int(obs["observation_index"]),
                        "gpx_progress_m": float(obs["gpx_progress_m"]),
                        "observation_heading_deg": float(obs["heading_deg"]),
                        "observation_confidence": float(
                            obs["observation_confidence"]
                        ),
                        "edge_id": state["edge_id"],
                        "edge_base_id": state["edge_base_id"],
                        "osm_element_type": state["osm_element_type"],
                        "osm_id": state["osm_id"],
                        "osm_way_id": state["osm_way_id"],
                        "edge_index": int(state["edge_index"]),
                        "direction": state["direction"],
                        "edge_length_m": float(state["edge_length_m"]),
                        "edge_heading_deg": float(state["edge_heading_deg"]),
                        "heading_delta_deg": circular_heading_delta(
                            obs["heading_deg"],
                            state["edge_heading_deg"],
                        ),
                        "distance_m": float(base_row["_distance_m"]),
                        "name": state.get("name", ""),
                        "highway_norm": state.get("highway_norm", ""),
                        "route_role": state.get("route_role", ""),
                        "semantic_score": state.get("semantic_score", None),
                        "legacy_match_score": state.get("match_score", None),
                        "legacy_selected": state.get("selected", None),
                    }
                )

    return pd.DataFrame(rows)



def score_observation_candidates(
    df: pd.DataFrame,
    distance_sigma_m: float,
    heading_weight: float,
    semantic_weight: float,
) -> pd.DataFrame:
    """
    P1 diagnostic observation evidence.

    Important:
    - No row is accepted/rejected here.
    - No legacy selected flag is used as a hard filter.
    - local geometry/path-shape agreement is intentionally deferred to the
      transition model, where a candidate graph path can be compared against
      the corresponding GPX progress window.
    """
    if distance_sigma_m <= 0:
        raise ValueError("--distance-sigma-m must be > 0")

    out = df.copy()
    if out.empty:
        return out

    d = pd.to_numeric(out["distance_m"], errors="coerce")
    h = pd.to_numeric(out["heading_delta_deg"], errors="coerce")

    semantic = pd.to_numeric(
        out["legacy_match_score"] * 0 + 0.5,
        errors="coerce",
    )

    # Prefer the explicit semantic_score if available in the source-state
    # pipeline. P0 candidate rows expose legacy_match_score but not
    # semantic_score yet, so derive from source data later when present.
    if "semantic_score" in out.columns:
        semantic = pd.to_numeric(
            out["semantic_score"],
            errors="coerce",
        )

    semantic = semantic.fillna(0.5).clip(0.0, 1.0)

    # Robust continuous distance penalty: no hard 20m/30m cutoff.
    out["distance_cost"] = (
        ((d / float(distance_sigma_m)) ** 2)
        .map(math.log1p)
    )

    # Directed heading disagreement:
    # 0 deg -> 0 cost, 90 deg -> 0.5, 180 deg -> 1.
    out["heading_cost"] = (
        0.5 * (1.0 - h.map(lambda x: math.cos(math.radians(float(x)))))
    )

    out["semantic_score_p1"] = semantic
    out["semantic_cost"] = 1.0 - semantic

    out["observation_cost"] = (
        out["distance_cost"]
        + float(heading_weight) * out["heading_cost"]
        + float(semantic_weight) * out["semantic_cost"]
    )

    # Rank directed states independently at each observation.
    out["observation_rank"] = (
        out.groupby("observation_index")["observation_cost"]
        .rank(method="first", ascending=True)
        .astype(int)
    )

    return out


def regression_way_rank_report(
    scored: pd.DataFrame,
    way_ids: Iterable[str],
) -> List[dict]:
    rows = []

    for wid in way_ids:
        sub = scored[scored["osm_way_id"].astype(str) == str(wid)].copy()

        if sub.empty:
            rows.append(
                {
                    "osm_way_id": wid,
                    "observation_presence_n": 0,
                    "best_rank_min": None,
                    "best_rank_median": None,
                    "best_rank_p95": None,
                    "best_rank_max": None,
                    "best_distance_min_m": None,
                    "best_distance_median_m": None,
                    "best_distance_max_m": None,
                    "top5_observation_n": 0,
                    "top10_observation_n": 0,
                    "top20_observation_n": 0,
                    "top40_observation_n": 0,
                }
            )
            continue

        # Same OSM way can contribute several graph segments and both
        # directions. For each observation, retain the best state belonging
        # to this way.
        best = (
            sub.sort_values(
                ["observation_index", "observation_rank", "distance_m"]
            )
            .groupby("observation_index", as_index=False)
            .first()
        )

        rank = pd.to_numeric(best["observation_rank"], errors="coerce")
        dist = pd.to_numeric(best["distance_m"], errors="coerce")

        rows.append(
            {
                "osm_way_id": wid,
                "observation_presence_n": int(len(best)),
                "best_rank_min": int(rank.min()),
                "best_rank_median": float(rank.median()),
                "best_rank_p95": float(rank.quantile(0.95)),
                "best_rank_max": int(rank.max()),
                "best_distance_min_m": float(dist.min()),
                "best_distance_median_m": float(dist.median()),
                "best_distance_max_m": float(dist.max()),
                "top5_observation_n": int((rank <= 5).sum()),
                "top10_observation_n": int((rank <= 10).sum()),
                "top20_observation_n": int((rank <= 20).sum()),
                "top40_observation_n": int((rank <= 40).sum()),
            }
        )

    return rows


def junction_report(
    way_id: str,
    src_wgs: gpd.GeoDataFrame,
    src_metric: gpd.GeoDataFrame,
    node_way_membership: Dict[Tuple[float, float], set],
) -> List[dict]:
    mask = src_wgs["osm_way_id"].map(norm_id) == way_id
    idxs = list(src_wgs.index[mask])

    if len(idxs) != 1:
        return []

    idx = idxs[0]
    gw = src_wgs.loc[idx].geometry
    gm = src_metric.loc[idx].geometry

    if gw.geom_type != "LineString" or gm.geom_type != "LineString":
        return []

    cw = list(gw.coords)
    cm = list(gm.coords)

    rows = []
    cumulative = 0.0

    for i, (wc, mc) in enumerate(zip(cw, cm)):
        if i > 0:
            cumulative += Point(cm[i - 1]).distance(Point(mc))

        nk = lonlat_key(wc)
        ext = sorted(
            x for x in node_way_membership.get(nk, set())
            if x != way_id
        )

        if ext:
            rows.append(
                {
                    "target_progress_m": cumulative,
                    "node_key": nk,
                    "x": float(mc[0]),
                    "y": float(mc[1]),
                    "external_way_ids": ";".join(ext),
                }
            )

    return rows


def write_csv(path: Path, rows: List[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def main() -> int:
    args = parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cand = gpd.read_file(args.candidate_fp)
    validate_candidate_schema(cand)

    # Normalize identity columns as strings without changing their meaning.
    cand = cand.copy()
    cand["osm_element_type"] = (
        cand["osm_element_type"].astype("string").str.lower()
    )
    cand["osm_id"] = cand["osm_id"].map(norm_id)
    cand["osm_way_id"] = cand["osm_way_id"].map(norm_id)

    gpx_wgs_geom = load_gpx_linestring(args.activity_fp)
    gpx_wgs = gpd.GeoSeries([gpx_wgs_geom], crs="EPSG:4326")

    if cand.crs.to_epsg() != 4326:
        cand_wgs = cand.to_crs("EPSG:4326")
    else:
        cand_wgs = cand.copy()

    metric_crs = cand_wgs.estimate_utm_crs()
    if metric_crs is None:
        raise RuntimeError("Could not estimate metric CRS")

    cand_m = cand_wgs.to_crs(metric_crs)
    gpx_m = gpx_wgs.to_crs(metric_crs).iloc[0]

    G_u, G_d, states, node_xy, node_way_membership = build_graph_and_states(
        cand_wgs,
        cand_m,
    )

    observations = sample_observations(
        gpx_m,
        args.observation_spacing_m,
    )
    observations = observations.set_crs(metric_crs)

    obs_candidates = build_observation_candidates(
        observations,
        states,
        args.candidate_search_radius_m,
        args.top_k,
    )

    obs_candidates = score_observation_candidates(
        obs_candidates,
        args.distance_sigma_m,
        args.heading_weight,
        args.semantic_weight,
    )

    regression_ranks = regression_way_rank_report(
        obs_candidates,
        REGRESSION_WAYS,
    )

    # ---------------------------------------------------------
    # Outputs
    # ---------------------------------------------------------
    obs_fp = out_dir / f"{args.case_id}_p1_observations.geojson"
    states_fp = out_dir / f"{args.case_id}_p1_directed_edge_states.geojson"
    candidates_fp = out_dir / f"{args.case_id}_p1_observation_candidates_scored.csv"
    junction_fp = out_dir / f"{args.case_id}_p1_way_631600007_junctions.csv"
    regression_fp = out_dir / f"{args.case_id}_p1_regression_way_ranks.csv"
    summary_fp = out_dir / f"{args.case_id}_p1_summary.csv"

    observations.to_crs("EPSG:4326").to_file(obs_fp, driver="GeoJSON")
    states.to_crs("EPSG:4326").to_file(states_fp, driver="GeoJSON")
    obs_candidates.to_csv(
        candidates_fp,
        index=False,
        encoding="utf-8-sig",
    )

    junctions = junction_report(
        JUNCTION_REGRESSION_WAY,
        cand_wgs,
        cand_m,
        node_way_membership,
    )
    write_csv(junction_fp, junctions)
    write_csv(regression_fp, regression_ranks)

    comp_sizes = sorted(
        (len(c) for c in nx.connected_components(G_u)),
        reverse=True,
    )

    grouped = (
        obs_candidates.groupby("observation_index")
        if not obs_candidates.empty
        else None
    )

    obs_with_candidates = (
        int(grouped.ngroups) if grouped is not None else 0
    )

    min_candidate_count = 0
    median_candidate_count = 0.0
    max_candidate_count = 0

    nearest_mean = float("nan")
    nearest_p95 = float("nan")
    nearest_max = float("nan")

    if grouped is not None:
        # directed state counts
        counts = grouped.size()
        min_candidate_count = int(counts.min())
        median_candidate_count = float(counts.median())
        max_candidate_count = int(counts.max())

        nearest = grouped["distance_m"].min()
        nearest_mean = float(nearest.mean())
        nearest_p95 = float(nearest.quantile(0.95))
        nearest_max = float(nearest.max())

    regression_presence = {
        wid: bool((cand_wgs["osm_way_id"] == wid).any())
        for wid in REGRESSION_WAYS
    }

    summary = {
        "prototype_version": VERSION,
        "case_id": args.case_id,
        "gpx_role": args.gpx_role,
        "metric_crs": str(metric_crs),
        "candidate_feature_n": int(len(cand_wgs)),
        "canonical_identity_pass": True,
        "gpx_length_m": float(gpx_m.length),
        "observation_spacing_m": float(args.observation_spacing_m),
        "observation_n": int(len(observations)),
        "candidate_search_radius_m": float(args.candidate_search_radius_m),
        "top_k_physical_edges": int(args.top_k),
        "topology_node_n": int(G_u.number_of_nodes()),
        "topology_edge_n": int(G_u.number_of_edges()),
        "topology_component_n": int(nx.number_connected_components(G_u)),
        "largest_component_n": int(comp_sizes[0]) if comp_sizes else 0,
        "directed_state_n": int(len(states)),
        "directed_graph_edge_n": int(G_d.number_of_edges()),
        "observations_with_candidates_n": obs_with_candidates,
        "observations_without_candidates_n": int(
            len(observations) - obs_with_candidates
        ),
        "candidate_state_count_min": min_candidate_count,
        "candidate_state_count_median": median_candidate_count,
        "candidate_state_count_max": max_candidate_count,
        "nearest_candidate_distance_mean_m": nearest_mean,
        "nearest_candidate_distance_p95_m": nearest_p95,
        "nearest_candidate_distance_max_m": nearest_max,
        "way_1273335252_present": regression_presence["1273335252"],
        "way_631600007_present": regression_presence["631600007"],
        "artificial_connector_n": 0,
        "distance_sigma_m": float(args.distance_sigma_m),
        "heading_weight": float(args.heading_weight),
        "semantic_weight": float(args.semantic_weight),
        "local_geometry_cost_status": "deferred_to_transition_model",
    }

    pd.DataFrame([summary]).to_csv(
        summary_fp,
        index=False,
        encoding="utf-8-sig",
    )

    # ---------------------------------------------------------
    # Console QA
    # ---------------------------------------------------------
    print("=" * 60)
    print("IB0B GLOBAL TRAVERSAL v0.1 — P0")
    print("=" * 60)
    print("prototype version:", VERSION)
    print("case:", args.case_id)
    print("gpx_role:", args.gpx_role)
    print("metric CRS:", metric_crs)

    print()
    print("=== INPUT / IDENTITY ===")
    print("candidate features:", len(cand_wgs))
    print("canonical identity: PASS")
    print("1273335252 present:", regression_presence["1273335252"])
    print("631600007 present:", regression_presence["631600007"])

    print()
    print("=== GPX OBSERVATIONS ===")
    print("GPX length m:", round(gpx_m.length, 2))
    print("observation spacing m:", args.observation_spacing_m)
    print("observations:", len(observations))

    print()
    print("=== TOPOLOGY GRAPH ===")
    print("nodes:", G_u.number_of_nodes())
    print("physical edges:", G_u.number_of_edges())
    print("components:", nx.number_connected_components(G_u))
    print("component sizes:", comp_sizes[:10])
    print("directed edge states:", len(states))
    print("artificial connectors:", 0)

    print()
    print("=== OBSERVATION CANDIDATES ===")
    print("search radius m:", args.candidate_search_radius_m)
    print("top_k physical edges:", args.top_k)
    print("observations with candidates:", obs_with_candidates)
    print(
        "observations without candidates:",
        len(observations) - obs_with_candidates,
    )

    if grouped is not None:
        print(
            "directed states / observation min/median/max:",
            min_candidate_count,
            round(median_candidate_count, 2),
            max_candidate_count,
        )
        print(
            "nearest candidate distance mean/p95/max m:",
            round(nearest_mean, 2),
            round(nearest_p95, 2),
            round(nearest_max, 2),
        )

    print()
    print("=" * 60)
    print("WAY 631600007 JUNCTION REGRESSION")
    print("=" * 60)

    target = cand_m[cand_wgs["osm_way_id"] == JUNCTION_REGRESSION_WAY]
    if len(target) == 1:
        print("target length m:", round(float(target.iloc[0].geometry.length), 2))
    else:
        print("target row count:", len(target))

    if junctions:
        for j in junctions:
            print(
                "target_progress_m=",
                round(j["target_progress_m"], 2),
                "| external ways=",
                j["external_way_ids"],
                "| node=",
                j["node_key"],
            )
    else:
        print("No external shared-vertex junctions found.")

    print()
    print("=" * 60)
    print("P1 OBSERVATION EVIDENCE")
    print("=" * 60)
    print("distance sigma m:", args.distance_sigma_m)
    print("heading weight:", args.heading_weight)
    print("semantic weight:", args.semantic_weight)
    print("local geometry cost: deferred to transition model")

    if not obs_candidates.empty:
        print(
            "observation cost min/median/p95/max:",
            round(float(obs_candidates["observation_cost"].min()), 4),
            round(float(obs_candidates["observation_cost"].median()), 4),
            round(float(obs_candidates["observation_cost"].quantile(0.95)), 4),
            round(float(obs_candidates["observation_cost"].max()), 4),
        )

    print()
    print("REGRESSION WAY LOCAL-RANK DIAGNOSTIC")
    for r in regression_ranks:
        print(
            "way", r["osm_way_id"],
            "| obs_n=", r["observation_presence_n"],
            "| rank min/median/p95/max=",
            r["best_rank_min"],
            r["best_rank_median"],
            r["best_rank_p95"],
            r["best_rank_max"],
            "| top5/top10/top20/top40=",
            r["top5_observation_n"],
            r["top10_observation_n"],
            r["top20_observation_n"],
            r["top40_observation_n"],
            "| distance min/median/max m=",
            r["best_distance_min_m"],
            r["best_distance_median_m"],
            r["best_distance_max_m"],
        )

    # P1 regression hints, deliberately tolerant rather than hardcoded exact rank gates.
    print()
    print("=" * 60)
    print("P1 GATE SUMMARY")
    print("=" * 60)

    regression_presence_map = {
        str(r["osm_way_id"]): int(r["observation_presence_n"])
        for r in regression_ranks
    }

    finite_costs = (
        (not obs_candidates.empty)
        and bool(
            pd.to_numeric(
                obs_candidates["observation_cost"],
                errors="coerce",
            ).notna().all()
        )
    )

    gates = {
        "canonical_identity": True,
        "candidate_input_nonempty": len(cand_wgs) > 0,
        "1273335252_present": regression_presence["1273335252"],
        "631600007_present": regression_presence["631600007"],
        "all_observations_have_candidates":
            obs_with_candidates == len(observations),
        "all_candidate_states_have_observation_cost": finite_costs,
        "1273335252_appears_in_observation_candidates":
            regression_presence_map.get("1273335252", 0) > 0,
        "631600007_appears_in_observation_candidates":
            regression_presence_map.get("631600007", 0) > 0,
        "no_artificial_connectors": True,
        "631600007_has_shared_vertex_junction":
            len(junctions) >= 1,
    }

    for k, v in gates.items():
        print(f"{k}: {'PASS' if v else 'FAIL'}")

    overall = all(gates.values())
    print("OVERALL P1:", "PASS" if overall else "FAIL")

    print()
    print("Outputs:")
    print(" observations:", obs_fp)
    print(" directed states:", states_fp)
    print(" observation candidates:", candidates_fp)
    print(" 631600007 junctions:", junction_fp)
    print(" regression way ranks:", regression_fp)
    print(" summary:", summary_fp)

    return 0 if overall else 2


if __name__ == "__main__":
    sys.exit(main())
