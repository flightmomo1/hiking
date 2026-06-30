# -*- coding: utf-8 -*-
"""
IB0A-QA: Project route definition control points / via points to OSM candidate ways.

Purpose
-------
Before rebuilding a constrained mainline, verify that route-definition points
(e.g. start / ascent_via / turnaround / descent_via / end) project to OSM
candidate ways/edges.

IB0A is a projection QA stage. It does not build the ordered mainline.
IB0B uses the IB0A top-k CSV to enforce required_way controls when requested.

Inputs
------
--route-definition-fp:
    Global CSV that may contain multiple cases. If a case_id column exists, rows
    are filtered by --case-id. Recommended columns:
    case_id, control_id, control_role, phase, name, lat, lon, required, order,
    route_action, note

--control-points-fp:
    Backward-compatible per-case CSV. Supported columns:
    control_id, control_role, name, lat, lon, required, order
    Optional columns: phase, route_action, note

--osm-fp:
    Candidate / matched OSM line GeoJSON.
    Recommended first tests:
    - outputs/ib0_route_match/<case_id>/<...matched...>.geojson
    - outputs/ib0a_prune/<case_id>/<...pruned...>.geojson
    - outputs/ib0b_mainline/<case_id>/<case_id>_mainline_ib0_matched.geojson

Outputs
-------
<case_id>_control_points_projected_to_osm_topk.csv
<case_id>_control_points_projected_to_osm_summary.txt
<case_id>_control_points_projected_to_osm_map.html
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path

import geopandas as gpd
import pandas as pd
from pyproj import CRS
from shapely.geometry import LineString, MultiLineString, Point


PROJECT_ROOT = Path(r"D:\mountain_work\115_osm")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument(
        "--route-definition-fp",
        type=Path,
        default=None,
        help=(
            "Global route definition control-points CSV. If provided, rows are "
            "filtered by --case-id when a case_id column exists."
        ),
    )
    parser.add_argument(
        "--control-points-fp",
        type=Path,
        default=None,
        help="Backward-compatible per-case control-points CSV.",
    )
    parser.add_argument("--osm-fp", type=Path, required=True, help="OSM candidate/matched/pruned line GeoJSON")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("outputs/ib0a_control_points_osm_projection"),
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-offset-ok-m", type=float, default=10.0)
    parser.add_argument("--metric-crs", default=None, help="Metric CRS, e.g. EPSG:32651. If omitted, infer UTM.")
    parser.add_argument("--no-map", action="store_true")
    return parser.parse_args()


def resolve_path(p: Path) -> Path:
    if p.is_absolute():
        return p
    return PROJECT_ROOT / p


def require_file(path: Path, label: str) -> Path:
    path = resolve_path(path)
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path.resolve()}")
    return path


def infer_metric_crs(lon: float, lat: float) -> CRS:
    zone = int((lon + 180.0) // 6.0) + 1
    epsg = 32600 + zone if lat >= 0 else 32700 + zone
    return CRS.from_epsg(epsg)


def normalize_bool_text(value, default="false") -> str:
    if pd.isna(value):
        return default
    s = str(value).strip().lower()
    if s in {"true", "1", "yes", "y"}:
        return "true"
    if s in {"false", "0", "no", "n", ""}:
        return "false"
    return s


def normalize_route_action(value, required_value="false") -> str:
    if pd.isna(value) or str(value).strip() == "":
        return "required_way" if normalize_bool_text(required_value) == "true" else "anchor_only"
    return str(value).strip()


def read_control_points(fp: Path, case_id: str | None = None) -> pd.DataFrame:
    df = pd.read_csv(fp)

    if "case_id" in df.columns and case_id:
        df = df[df["case_id"].astype(str) == str(case_id)].copy()
        if df.empty:
            raise ValueError(f"No control point rows found for case_id={case_id} in {fp}")

    required = {"control_id", "control_role", "lat", "lon", "order"}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(f"control points CSV missing columns: {sorted(missing)}")

    out = df.copy()

    # Backward-compatible defaults.
    if "case_id" not in out.columns:
        out["case_id"] = case_id or ""
    if "name" not in out.columns:
        out["name"] = ""
    if "required" not in out.columns:
        out["required"] = "false"
    if "phase" not in out.columns:
        out["phase"] = out["control_role"].astype(str)
    if "route_action" not in out.columns:
        out["route_action"] = ""
    if "note" not in out.columns:
        out["note"] = ""

    out["lat"] = pd.to_numeric(out["lat"], errors="coerce")
    out["lon"] = pd.to_numeric(out["lon"], errors="coerce")
    out["order"] = pd.to_numeric(out["order"], errors="coerce")
    out = out.dropna(subset=["lat", "lon", "order"]).copy()

    out["required"] = out["required"].apply(normalize_bool_text)
    out["route_action"] = [
        normalize_route_action(action, required)
        for action, required in zip(out["route_action"], out["required"])
    ]

    # Keep a stable canonical column order for downstream QA.
    preferred = [
        "case_id",
        "control_id",
        "control_role",
        "phase",
        "name",
        "lat",
        "lon",
        "required",
        "order",
        "route_action",
        "note",
    ]
    rest = [c for c in out.columns if c not in preferred]
    out = out[preferred + rest]
    out = out.sort_values("order").reset_index(drop=True)
    return out


def normalize_osm_lines(osm_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    rows = []
    for feat_idx, row in osm_gdf.reset_index(drop=True).iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        geoms = []
        if isinstance(geom, LineString):
            geoms = [geom]
        elif isinstance(geom, MultiLineString):
            geoms = list(geom.geoms)
        else:
            continue

        props = row.drop(labels=["geometry"]).to_dict()
        for part_idx, line in enumerate(geoms):
            item = props.copy()
            item["feature_index"] = int(feat_idx)
            item["part_index"] = int(part_idx)
            item["geometry"] = line
            rows.append(item)

    if not rows:
        raise ValueError("No LineString/MultiLineString features found in OSM GeoJSON.")

    return gpd.GeoDataFrame(rows, geometry="geometry", crs=osm_gdf.crs)


def pick_id(row: pd.Series) -> tuple[str, str]:
    id_cols = [
        "way_id",
        "osm_id",
        "id",
        "@id",
        "osmid",
        "osm_way_id",
        "edge_id",
        "u",
        "v",
        "key",
    ]
    parts = []
    for c in id_cols:
        if c in row.index and pd.notna(row[c]) and str(row[c]) != "":
            parts.append(f"{c}={row[c]}")
    if not parts:
        parts.append(f"feature_index={row.get('feature_index')}")
    return ";".join(parts), ",".join([c.split("=")[0] for c in parts])


def project_control_points(
    cps: pd.DataFrame,
    osm_lines_m: gpd.GeoDataFrame,
    metric_crs: CRS,
    top_k: int,
    max_offset_ok_m: float,
) -> pd.DataFrame:
    cp_gdf = gpd.GeoDataFrame(
        cps.copy(),
        geometry=[Point(lon, lat) for lon, lat in zip(cps["lon"], cps["lat"])],
        crs="EPSG:4326",
    ).to_crs(metric_crs)

    rows = []
    sindex = osm_lines_m.sindex

    for _, cp in cp_gdf.iterrows():
        pt = cp.geometry

        # Expand search radius until enough candidates are found.
        candidate_indices = set()
        for radius in [20, 50, 100, 200, 500]:
            candidate_indices.update(sindex.intersection(pt.buffer(radius).bounds))
            if len(candidate_indices) >= top_k:
                break
        if not candidate_indices:
            candidate_indices = set(range(len(osm_lines_m)))

        scored = []
        for idx in candidate_indices:
            line_row = osm_lines_m.iloc[int(idx)]
            line = line_row.geometry
            d_along = float(line.project(pt))
            proj_pt = line.interpolate(d_along)
            offset = float(pt.distance(proj_pt))
            scored.append((offset, int(idx), d_along, proj_pt, line_row))

        scored = sorted(scored, key=lambda x: x[0])[:top_k]

        for rank, (offset, idx, d_along, proj_pt, line_row) in enumerate(scored, start=1):
            line_wgs = gpd.GeoSeries([proj_pt], crs=metric_crs).to_crs("EPSG:4326").iloc[0]
            id_text, id_cols = pick_id(line_row)

            rows.append(
                {
                    "control_id": cp["control_id"],
                    "control_role": cp["control_role"],
                    "phase": cp.get("phase", ""),
                    "name": cp.get("name", ""),
                    "required": cp.get("required", "false"),
                    "route_action": cp.get("route_action", "anchor_only"),
                    "note": cp.get("note", ""),
                    "order": cp["order"],
                    "lat": cp["lat"],
                    "lon": cp["lon"],
                    "candidate_rank": rank,
                    "offset_to_osm_m": offset,
                    "projection_ok": bool(offset <= max_offset_ok_m),
                    "matched_id_text": id_text,
                    "matched_id_cols": id_cols,
                    "feature_index": int(line_row.get("feature_index", idx)),
                    "part_index": int(line_row.get("part_index", 0)),
                    "projected_dist_on_feature_m": d_along,
                    "projected_lat": line_wgs.y,
                    "projected_lon": line_wgs.x,
                    "highway": line_row.get("highway", ""),
                    "name_osm": line_row.get("name", ""),
                    "route_role": line_row.get("route_role", ""),
                    "selected": line_row.get("selected", ""),
                    "match_score": line_row.get("match_score", ""),
                    "overlap_ratio": line_row.get("overlap_ratio", ""),
                    "min_dist_m": line_row.get("min_dist_m", ""),
                }
            )

    return pd.DataFrame(rows)


def write_summary(out_fp: Path, args: argparse.Namespace, topk: pd.DataFrame) -> None:
    lines = [
        "IB0A control point to OSM candidate projection QA",
        f"case_id: {args.case_id}",
        f"route_definition_fp: {resolve_path(args.route_definition_fp) if args.route_definition_fp else ''}",
        f"control_points_fp: {resolve_path(args.control_points_fp) if args.control_points_fp else ''}",
        f"osm_fp: {resolve_path(args.osm_fp)}",
        f"top_k: {args.top_k}",
        f"max_offset_ok_m: {args.max_offset_ok_m}",
        "",
        "nearest candidate per control point:",
    ]

    nearest = topk[topk["candidate_rank"] == 1].copy()
    for _, r in nearest.sort_values("order").iterrows():
        lines.append(
            f"- {r['control_id']} ({r['control_role']}; phase={r.get('phase','')}; "
            f"action={r.get('route_action','')}; required={r.get('required','')}): "
            f"offset={float(r['offset_to_osm_m']):.2f}m; "
            f"projection_ok={r['projection_ok']}; "
            f"matched={r['matched_id_text']}; "
            f"highway={r.get('highway','')}; name={r.get('name_osm','')}"
        )

    via_rows = nearest[nearest["control_role"].astype(str).str.contains("via", case=False, na=False)]
    if len(via_rows) >= 2:
        ids = via_rows["matched_id_text"].astype(str).tolist()
        lines.append("")
        lines.append(f"via_nearest_ids: {' | '.join(ids)}")
        lines.append(f"via_points_have_distinct_nearest_ids: {len(set(ids)) == len(ids)}")

    required_way_rows = nearest[nearest["route_action"].astype(str).str.lower() == "required_way"]
    if len(required_way_rows) > 0:
        lines.append("")
        lines.append("required_way controls:")
        for _, r in required_way_rows.sort_values("order").iterrows():
            lines.append(
                f"- {r['control_id']} ({r['control_role']}): "
                f"projection_ok={r['projection_ok']}; offset={float(r['offset_to_osm_m']):.2f}m; "
                f"matched={r['matched_id_text']}"
            )

    out_fp.write_text("\n".join(lines), encoding="utf-8")


def write_map(out_fp: Path, cps: pd.DataFrame, osm_gdf: gpd.GeoDataFrame, topk: pd.DataFrame) -> None:
    try:
        import folium
    except ImportError:
        print("folium not installed; skip map")
        return

    center = [float(cps["lat"].mean()), float(cps["lon"].mean())]
    m = folium.Map(location=center, zoom_start=17, tiles="OpenStreetMap")

    osm_wgs = osm_gdf.to_crs("EPSG:4326")
    for _, r in osm_wgs.iterrows():
        geom = r.geometry
        if geom is None or geom.is_empty:
            continue
        geoms = [geom] if geom.geom_type == "LineString" else list(geom.geoms) if geom.geom_type == "MultiLineString" else []
        for line in geoms:
            coords = [(lat, lon) for lon, lat in line.coords]
            folium.PolyLine(coords, color="#64748b", weight=2, opacity=0.35).add_to(m)

    colors = {
        "start": "#2563eb",
        "start_anchor": "#2563eb",
        "ascent_via": "#16a34a",
        "turnaround": "#7c3aed",
        "summit_anchor": "#7c3aed",
        "descent_via": "#dc2626",
        "end": "#2563eb",
        "end_anchor": "#2563eb",
    }

    for _, cp in cps.iterrows():
        role = str(cp["control_role"])
        color = colors.get(role, "#f97316")
        popup = "<br>".join(
            [
                f"control_id: {html.escape(str(cp['control_id']))}",
                f"role: {html.escape(role)}",
                f"phase: {html.escape(str(cp.get('phase','')))}",
                f"required: {html.escape(str(cp.get('required','')))}",
                f"route_action: {html.escape(str(cp.get('route_action','')))}",
                f"name: {html.escape(str(cp.get('name','')))}",
                f"lat/lon: {cp['lat']}, {cp['lon']}",
            ]
        )
        folium.CircleMarker(
            [float(cp["lat"]), float(cp["lon"])],
            radius=7,
            color=color,
            fill=True,
            fill_opacity=0.9,
            popup=popup,
        ).add_to(m)

    # projected nearest points
    nearest = topk[topk["candidate_rank"] == 1]
    for _, r in nearest.iterrows():
        color = colors.get(str(r["control_role"]), "#f97316")
        folium.CircleMarker(
            [float(r["projected_lat"]), float(r["projected_lon"])],
            radius=4,
            color=color,
            fill=True,
            fill_opacity=0.6,
            popup=f"{html.escape(str(r['control_id']))} projected<br>offset {float(r['offset_to_osm_m']):.2f}m<br>{html.escape(str(r['matched_id_text']))}",
        ).add_to(m)
        folium.PolyLine(
            [(float(r["lat"]), float(r["lon"])), (float(r["projected_lat"]), float(r["projected_lon"]))],
            color=color,
            weight=2,
            opacity=0.8,
            dash_array="5,5",
        ).add_to(m)

    m.save(out_fp)


def main() -> None:
    args = parse_args()

    if args.route_definition_fp is None and args.control_points_fp is None:
        raise ValueError("Either --route-definition-fp or --control-points-fp is required.")

    if args.route_definition_fp is not None:
        control_fp = require_file(args.route_definition_fp, "route definition CSV")
        control_source_mode = "route_definition_fp"
    else:
        control_fp = require_file(args.control_points_fp, "control points CSV")
        control_source_mode = "control_points_fp"

    osm_fp = require_file(args.osm_fp, "OSM candidate/matched GeoJSON")

    out_dir = resolve_path(args.out_dir) / args.case_id
    out_dir.mkdir(parents=True, exist_ok=True)

    cps = read_control_points(control_fp, case_id=args.case_id)

    osm = gpd.read_file(osm_fp)
    if osm.crs is None:
        osm = osm.set_crs("EPSG:4326")
    osm = normalize_osm_lines(osm)

    # infer metric CRS from control points unless provided
    metric_crs = CRS.from_user_input(args.metric_crs) if args.metric_crs else infer_metric_crs(float(cps["lon"].mean()), float(cps["lat"].mean()))
    osm_m = osm.to_crs(metric_crs)

    topk = project_control_points(
        cps,
        osm_m,
        metric_crs=metric_crs,
        top_k=args.top_k,
        max_offset_ok_m=args.max_offset_ok_m,
    )

    out_topk = out_dir / f"{args.case_id}_control_points_projected_to_osm_topk.csv"
    out_summary = out_dir / f"{args.case_id}_control_points_projected_to_osm_summary.txt"
    out_map = out_dir / f"{args.case_id}_control_points_projected_to_osm_map.html"
    out_controls = out_dir / f"{args.case_id}_control_points_used.csv"

    cps.to_csv(out_controls, index=False, encoding="utf-8-sig")
    topk.to_csv(out_topk, index=False, encoding="utf-8-sig")
    write_summary(out_summary, args, topk)
    if not args.no_map:
        write_map(out_map, cps, osm, topk)

    print("control point projection QA written")
    print(f"metric CRS: {metric_crs.to_string()}")
    print(f"control source mode: {control_source_mode}")
    print(f"control points: {control_fp.resolve()}")
    print(f"control points used CSV: {out_controls.resolve()}")
    print(f"osm input: {osm_fp.resolve()}")
    print(f"top-k CSV: {out_topk.resolve()}")
    print(f"summary TXT: {out_summary.resolve()}")
    if not args.no_map:
        print(f"map HTML: {out_map.resolve()}")

    print("")
    print(topk[topk["candidate_rank"] == 1][[
        "control_id",
        "control_role",
        "phase",
        "required",
        "route_action",
        "offset_to_osm_m",
        "projection_ok",
        "matched_id_text",
        "highway",
        "name_osm",
    ]].to_string(index=False))


if __name__ == "__main__":
    main()
