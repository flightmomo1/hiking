# -*- coding: utf-8 -*-
"""
IB0A-2 route-axis anchor component QA.

Purpose:
Check whether route definition control points are connected inside
the IB0 / IB0 candidate graph before running IB0B route-axis extraction.

Inputs:
- --case-id
- --osm-fp
- --control-points-fp

Outputs:
- <case_id>_ib0a2_route_axis_anchor_component_qa.csv
- <case_id>_ib0a2_route_axis_anchor_component_qa_summary.txt
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import networkx as nx
import pandas as pd
from shapely.geometry import LineString, Point


PROJECT_ROOT = Path(r"C:\mountain_work\115_osm")


def resolve_path(value):
    p = Path(value)
    if p.is_absolute():
        return p
    return PROJECT_ROOT / p


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--case-id", required=True)
    ap.add_argument("--osm-fp", required=True)
    ap.add_argument("--control-points-fp", required=True)
    ap.add_argument("--out-dir", default="outputs/ib0a2_route_axis_anchor_component_qa")
    ap.add_argument("--snap-tolerance-m", type=float, default=20.0)
    ap.add_argument("--snap-link-weight", type=float, default=0.30)
    return ap.parse_args()


def split_line_to_segments(line):
    coords = list(line.coords)
    return [LineString([coords[i], coords[i + 1]]) for i in range(len(coords) - 1)]


def node_distance(a, b):
    return Point(a).distance(Point(b))


def nearest_segment_node(gdf_m, pt_m):
    min_dist = float("inf")
    best_idx = None

    for idx, row in gdf_m.iterrows():
        d = row.geometry.distance(pt_m)
        if d < min_dist:
            min_dist = d
            best_idx = idx

    geom = gdf_m.loc[best_idx].geometry
    if geom.geom_type == "MultiLineString":
        geom = list(geom.geoms)[0]

    coords = list(geom.coords)
    n1 = tuple(coords[0])
    n2 = tuple(coords[-1])
    node = n1 if Point(n1).distance(pt_m) < Point(n2).distance(pt_m) else n2

    return node, best_idx, min_dist, gdf_m.loc[best_idx]


def row_way_id(row):
    for col in ["osm_way_id", "way_id", "osm_id", "id"]:
        if col in row.index and pd.notna(row.get(col)):
            s = str(row.get(col)).strip()
            if s.endswith(".0"):
                s = s[:-2]
            return s
    return ""


def main():
    args = parse_args()

    case_id = args.case_id
    osm_fp = resolve_path(args.osm_fp)
    cp_fp = resolve_path(args.control_points_fp)
    out_dir = resolve_path(args.out_dir) / case_id
    out_dir.mkdir(parents=True, exist_ok=True)

    if not osm_fp.exists():
        raise FileNotFoundError(osm_fp)
    if not cp_fp.exists():
        raise FileNotFoundError(cp_fp)

    gdf = gpd.read_file(osm_fp).to_crs(epsg=4326)
    metric_crs = gdf.estimate_utm_crs()
    gdf_m = gdf.to_crs(metric_crs)

    G = nx.Graph()

    for idx, row in gdf_m.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        lines = list(geom.geoms) if geom.geom_type == "MultiLineString" else [geom]
        for line in lines:
            for seg in split_line_to_segments(line):
                coords = list(seg.coords)
                start = tuple(coords[0])
                end = tuple(coords[1])
                G.add_edge(start, end, weight=1.0, idx=idx, snap_link=0)

    components_before = nx.number_connected_components(G)
    nodes = list(G.nodes)

    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            d = node_distance(nodes[i], nodes[j])
            if d <= args.snap_tolerance_m and not G.has_edge(nodes[i], nodes[j]):
                G.add_edge(
                    nodes[i],
                    nodes[j],
                    weight=args.snap_link_weight,
                    idx=-1,
                    snap_link=1,
                )

    components = list(nx.connected_components(G))
    comp_id_by_node = {}
    for i, comp in enumerate(components):
        for node in comp:
            comp_id_by_node[node] = i

    cp = pd.read_csv(cp_fp).sort_values("order").reset_index(drop=True)

    rows = []

    for _, r in cp.iterrows():
        pt_wgs = gpd.GeoSeries(
            [Point(float(r["lon"]), float(r["lat"]))],
            crs="EPSG:4326",
        )
        pt_m = pt_wgs.to_crs(metric_crs).iloc[0]

        node, seg_idx, dist_m, seg_row = nearest_segment_node(gdf_m, pt_m)
        comp_id = comp_id_by_node.get(node, None)

        rows.append({
            "case_id": case_id,
            "control_id": r.get("control_id", ""),
            "control_role": r.get("control_role", ""),
            "phase": r.get("phase", ""),
            "name": r.get("name", ""),
            "order": r.get("order", ""),
            "lat": r.get("lat", ""),
            "lon": r.get("lon", ""),
            "nearest_seg_idx": seg_idx,
            "nearest_node_dist_m": dist_m,
            "component_id": comp_id,
            "component_size": len(components[comp_id]) if comp_id is not None else "",
            "way_id": row_way_id(seg_row),
            "highway": seg_row.get("highway", seg_row.get("highway_norm", "")),
            "highway_norm": seg_row.get("highway_norm", ""),
            "name_osm": seg_row.get("name", ""),
            "route_role": seg_row.get("route_role", ""),
        })

    df = pd.DataFrame(rows)

    pair_rows = []
    for a, b in zip(rows[:-1], rows[1:]):
        same_component = a["component_id"] == b["component_id"]

        nearest_inter_component_dist_m = ""
        if not same_component and a["component_id"] is not None and b["component_id"] is not None:
            nodes_a = list(components[a["component_id"]])
            nodes_b = list(components[b["component_id"]])
            best = None
            for na in nodes_a:
                pa = Point(na)
                for nb in nodes_b:
                    d = pa.distance(Point(nb))
                    if best is None or d < best:
                        best = d
            nearest_inter_component_dist_m = best

        pair_rows.append({
            "from_control_id": a["control_id"],
            "to_control_id": b["control_id"],
            "from_component_id": a["component_id"],
            "to_component_id": b["component_id"],
            "same_component": same_component,
            "nearest_inter_component_dist_m": nearest_inter_component_dist_m,
        })

    pair_df = pd.DataFrame(pair_rows)

    all_pairs_connected = bool(pair_df["same_component"].all()) if not pair_df.empty else False
    unique_anchor_components = sorted(set(df["component_id"].dropna().astype(int).tolist()))

    status = "PASS" if all_pairs_connected else "FAIL"
    if not all_pairs_connected:
        max_gap = pd.to_numeric(pair_df["nearest_inter_component_dist_m"], errors="coerce").max()
        if pd.notna(max_gap) and max_gap <= args.snap_tolerance_m * 2:
            status = "WARN"

    out_csv = out_dir / f"{case_id}_ib0a2_route_axis_anchor_component_qa.csv"
    out_pairs_csv = out_dir / f"{case_id}_ib0a2_route_axis_anchor_component_pairs.csv"
    out_txt = out_dir / f"{case_id}_ib0a2_route_axis_anchor_component_qa_summary.txt"

    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    pair_df.to_csv(out_pairs_csv, index=False, encoding="utf-8-sig")

    lines = [
        "IB0A-2 route-axis anchor component QA",
        f"case_id: {case_id}",
        f"osm_fp: {osm_fp}",
        f"control_points_fp: {cp_fp}",
        f"snap_tolerance_m: {args.snap_tolerance_m}",
        f"nodes: {len(G.nodes)}",
        f"edges_after_snap: {len(G.edges)}",
        f"components_before_snap: {components_before}",
        f"components_after_snap: {len(components)}",
        f"largest_component_sizes: {sorted([len(c) for c in components], reverse=True)[:10]}",
        f"anchor_component_ids: {','.join(map(str, unique_anchor_components))}",
        f"all_adjacent_control_pairs_connected: {all_pairs_connected}",
        f"status: {status}",
        "",
        "--- anchors ---",
    ]

    for _, row in df.iterrows():
        lines.append(
            f"- order={row['order']} {row['control_id']} ({row['phase']} / {row['control_role']}): "
            f"comp={row['component_id']}; size={row['component_size']}; "
            f"node_dist={float(row['nearest_node_dist_m']):.2f}m; "
            f"way={row['way_id']}; highway={row['highway']}; name_osm={row['name_osm']}; route_role={row['route_role']}"
        )

    lines.append("")
    lines.append("--- adjacent pairs ---")
    for _, row in pair_df.iterrows():
        lines.append(
            f"- {row['from_control_id']} -> {row['to_control_id']}: "
            f"same_component={row['same_component']}; "
            f"gap_m={row['nearest_inter_component_dist_m']}"
        )

    out_txt.write_text("\n".join(lines), encoding="utf-8-sig")

    print("\n".join(lines))
    print("")
    print("wrote:", out_csv)
    print("wrote:", out_pairs_csv)
    print("wrote:", out_txt)


if __name__ == "__main__":
    main()
