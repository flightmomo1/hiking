#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
IB0D Route Axis Finalizer v2.0.1

Changes from v2.0
-----------------
- No routing / trimming / threshold / contract logic changes.
- KEEP FULL behavior is unchanged.
- Adds human QA HTML output.
- Optional --gpx-fp overlays the original GPX for visual comparison.

HTML layers
-----------
- Original GPX (optional)
- IB0B Global Traversal
- IB0D Final Route Axis
- GPX start / end markers (optional)

Machine authority remains CSV / GeoJSON / contract checks.
The HTML is human QA only.
"""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point

VERSION = "v2.0.1-keep-full-traversal-contract-html"

REQUIRED_FIELDS = [
    "traversal_order",
    "edge_id",
    "edge_occurrence",
    "direction",
    "osm_type",
    "osm_id",
    "osm_way_id",
]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="IB0D traversal-aware Route Axis finalizer v2.0.1"
    )
    ap.add_argument("--case-id", required=True)
    ap.add_argument("--traversal-edges-fp", required=True)
    ap.add_argument("--global-traversal-fp", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--mode", default="keep-full", choices=["keep-full"])
    ap.add_argument(
        "--gpx-fp",
        default=None,
        help="Optional original GPX. Used only for human QA HTML overlay.",
    )
    return ap.parse_args()


def norm_id(v) -> str:
    if pd.isna(v):
        return ""
    s = str(v).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def require_file(fp: Path, label: str) -> Path:
    if not fp.exists():
        raise FileNotFoundError(f"Missing {label}: {fp.resolve()}")
    return fp


def require_columns(df: pd.DataFrame, cols: list[str]) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise RuntimeError(f"IB0D_INPUT_CONTRACT_FAIL missing columns: {missing}")


def parse_gpx_line(gpx_fp: Path):
    tree = ET.parse(gpx_fp)
    root = tree.getroot()

    if root.tag.startswith("{"):
        uri = root.tag.split("}")[0].strip("{")
        ns = {"gpx": uri}
        xpath = ".//gpx:trkpt"
    else:
        ns = {}
        xpath = ".//trkpt"

    coords = []
    for trkpt in root.findall(xpath, ns):
        lat = float(trkpt.attrib["lat"])
        lon = float(trkpt.attrib["lon"])
        coords.append((lon, lat))

    if len(coords) < 2:
        raise ValueError(f"GPX has fewer than 2 track points: {gpx_fp}")

    return LineString(coords)


def add_fixed_legend(m: folium.Map, has_gpx: bool) -> None:
    gpx_row = (
        '<div><span style="display:inline-block;width:28px;border-top:4px solid black;'
        'margin-right:8px;"></span>Original GPX</div>'
        if has_gpx
        else ""
    )

    html = f"""
    <div style="
        position: fixed;
        bottom: 35px;
        left: 35px;
        z-index: 9999;
        background: white;
        border: 1px solid #888;
        border-radius: 4px;
        padding: 10px 12px;
        font-size: 13px;
        line-height: 1.65;
        box-shadow: 0 1px 4px rgba(0,0,0,.25);
    ">
      <b>IB0D Route Axis QA</b><br>
      {gpx_row}
      <div><span style="display:inline-block;width:28px;border-top:6px dashed #3388ff;
      margin-right:8px;"></span>IB0B Global Traversal</div>
      <div><span style="display:inline-block;width:28px;border-top:3px solid #d62728;
      margin-right:8px;"></span>IB0D Final Route Axis</div>
      <div style="margin-top:5px;color:#666;">HTML = human QA only</div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(html))


def build_qa_html(
    case_id: str,
    ib0b_global: gpd.GeoDataFrame,
    ib0d_axis: gpd.GeoDataFrame,
    out_html: Path,
    route_len_m,
    traversal_n: int,
    gpx_fp: Path | None,
) -> None:
    ib0b_wgs = ib0b_global.to_crs("EPSG:4326")
    axis_wgs = ib0d_axis.to_crs("EPSG:4326")

    bounds = axis_wgs.total_bounds
    minx, miny, maxx, maxy = bounds
    center = [(miny + maxy) / 2.0, (minx + maxx) / 2.0]

    m = folium.Map(
        location=center,
        zoom_start=15,
        tiles="CartoDB positron",
        control_scale=True,
        width="100%",
        height="850px",
    )

    # Optional GPX
    has_gpx = False
    if gpx_fp is not None:
        gpx_line = parse_gpx_line(gpx_fp)
        has_gpx = True

        gpx_coords_latlon = [(lat, lon) for lon, lat in gpx_line.coords]
        folium.PolyLine(
            gpx_coords_latlon,
            name="Original GPX",
            color="black",
            weight=3,
            opacity=0.65,
            tooltip="Original GPX",
        ).add_to(m)

        start_lon, start_lat = gpx_line.coords[0]
        end_lon, end_lat = gpx_line.coords[-1]

        folium.CircleMarker(
            location=[start_lat, start_lon],
            radius=6,
            color="green",
            fill=True,
            fill_opacity=1.0,
            tooltip="GPX START",
        ).add_to(m)

        folium.CircleMarker(
            location=[end_lat, end_lon],
            radius=6,
            color="red",
            fill=True,
            fill_opacity=1.0,
            tooltip="GPX END",
        ).add_to(m)

    # IB0B first, deliberately wider/dashed so it remains visible below IB0D.
    folium.GeoJson(
        ib0b_wgs,
        name="IB0B Global Traversal",
        style_function=lambda _: {
            "color": "#3388ff",
            "weight": 7,
            "opacity": 0.55,
            "dashArray": "9,7",
        },
        tooltip=folium.GeoJsonTooltip(
            fields=[
                c
                for c in [
                    "pipeline_stage",
                    "case_id",
                    "traversal_occurrence_n",
                ]
                if c in ib0b_wgs.columns
            ],
            aliases=[
                c
                for c in [
                    "pipeline_stage",
                    "case_id",
                    "traversal_occurrence_n",
                ]
                if c in ib0b_wgs.columns
            ],
        )
        if any(
            c in ib0b_wgs.columns
            for c in ["pipeline_stage", "case_id", "traversal_occurrence_n"]
        )
        else None,
    ).add_to(m)

    # IB0D axis overlaid as thinner solid line.
    folium.GeoJson(
        axis_wgs,
        name="IB0D Final Route Axis",
        style_function=lambda _: {
            "color": "#d62728",
            "weight": 3,
            "opacity": 0.95,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=[
                c
                for c in [
                    "case_id",
                    "route_axis_mode",
                    "traversal_occurrence_n",
                    "route_axis_length_m",
                ]
                if c in axis_wgs.columns
            ],
            aliases=[
                c
                for c in [
                    "case_id",
                    "route_axis_mode",
                    "traversal_occurrence_n",
                    "route_axis_length_m",
                ]
                if c in axis_wgs.columns
            ],
        ),
    ).add_to(m)

    # QA summary box
    length_text = "NA" if route_len_m is None else f"{route_len_m:.2f} m"
    summary_html = f"""
    <div style="
        position: fixed;
        top: 18px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 9999;
        background: rgba(255,255,255,.94);
        border: 1px solid #888;
        border-radius: 4px;
        padding: 8px 14px;
        font-size: 13px;
        box-shadow: 0 1px 4px rgba(0,0,0,.20);
        white-space: nowrap;
    ">
      <b>{case_id}</b>
      &nbsp; | &nbsp; Route Axis: {length_text}
      &nbsp; | &nbsp; Traversal occurrences: {traversal_n}
      &nbsp; | &nbsp; Mode: KEEP FULL
    </div>
    """
    m.get_root().html.add_child(folium.Element(summary_html))

    add_fixed_legend(m, has_gpx)

    # Fit to route + optional GPX bounds.
    all_bounds = [[miny, minx], [maxy, maxx]]
    if has_gpx:
        xs = [p[0] for p in gpx_line.coords]
        ys = [p[1] for p in gpx_line.coords]
        all_bounds = [
            [min(miny, min(ys)), min(minx, min(xs))],
            [max(maxy, max(ys)), max(maxx, max(xs))],
        ]

    m.fit_bounds(all_bounds, padding=(25, 25))
    folium.LayerControl(collapsed=False).add_to(m)
    m.save(out_html)


def main() -> int:
    args = parse_args()

    traversal_fp = require_file(
        Path(args.traversal_edges_fp), "IB0B traversal edges CSV"
    )
    global_fp = require_file(
        Path(args.global_traversal_fp), "IB0B global traversal GeoJSON"
    )

    gpx_fp = None
    if args.gpx_fp:
        gpx_fp = require_file(Path(args.gpx_fp), "original GPX")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    out_axis = out_dir / f"{args.case_id}_route_axis.geojson"
    out_edges = out_dir / f"{args.case_id}_route_axis_edges.csv"
    out_summary_csv = out_dir / f"{args.case_id}_route_axis_summary.csv"
    out_summary_json = out_dir / f"{args.case_id}_route_axis_summary.json"
    out_html = out_dir / f"{args.case_id}_route_axis_qa.html"

    trav = pd.read_csv(traversal_fp, low_memory=False)
    global_gdf = gpd.read_file(global_fp)

    require_columns(trav, REQUIRED_FIELDS)

    failures = []

    traversal_order = pd.to_numeric(trav["traversal_order"], errors="coerce")
    order_populated = bool(traversal_order.notna().all())
    order_unique = bool((~traversal_order.duplicated()).all())
    order_monotonic = bool(traversal_order.is_monotonic_increasing)

    edge_populated = bool(
        trav["edge_id"].astype("string").fillna("").str.strip().ne("").all()
    )

    occurrence_num = pd.to_numeric(trav["edge_occurrence"], errors="coerce")
    occurrence_positive = bool(
        (occurrence_num.notna() & (occurrence_num >= 1)).all()
    )

    temp_pairs = pd.DataFrame(
        {
            "edge_id": trav["edge_id"].astype(str),
            "edge_occurrence": occurrence_num,
        }
    )
    pair_unique = bool((~temp_pairs.duplicated()).all())

    direction_populated = bool(
        trav["direction"].astype("string").fillna("").str.strip().ne("").all()
    )

    osm_type = (
        trav["osm_type"].astype("string").fillna("").str.strip().str.lower()
    )
    osm_id = trav["osm_id"].map(norm_id)
    identity_populated = bool((osm_type.ne("") & osm_id.ne("")).all())

    osm_way_id = trav["osm_way_id"].map(norm_id)
    way_mask = osm_type.eq("way")
    way_identity_match = bool(
        ((~way_mask) | (osm_way_id.ne("") & osm_way_id.eq(osm_id))).all()
    )

    if not order_populated:
        failures.append("traversal_order incomplete")
    if not order_unique:
        failures.append("traversal_order not unique")
    if not order_monotonic:
        failures.append("traversal_order not monotonic")
    if not edge_populated:
        failures.append("edge_id incomplete")
    if not occurrence_positive:
        failures.append("edge_occurrence invalid")
    if not pair_unique:
        failures.append("(edge_id, edge_occurrence) not unique")
    if not direction_populated:
        failures.append("direction incomplete")
    if not identity_populated:
        failures.append("canonical OSM identity incomplete")
    if not way_identity_match:
        failures.append("way osm_way_id != osm_id")

    if global_gdf.empty:
        geometry_nonempty = False
        geometry_valid = False
        route_len_m = None
        metric_crs = None
        failures.append("global traversal GeoJSON empty")
    else:
        geometry_nonempty = bool(
            global_gdf.geometry.notna().all()
            and (~global_gdf.geometry.is_empty).all()
        )
        geometry_valid = bool(global_gdf.geometry.is_valid.all())

        if not geometry_nonempty:
            failures.append("global traversal geometry empty")
        if not geometry_valid:
            failures.append("global traversal geometry invalid")

        if global_gdf.crs is None:
            global_gdf = global_gdf.set_crs("EPSG:4326")

        metric_crs = global_gdf.estimate_utm_crs()
        if metric_crs is None:
            route_len_m = None
            failures.append("cannot estimate metric CRS")
        else:
            route_len_m = float(
                global_gdf.to_crs(metric_crs).geometry.length.sum()
            )

    # KEEP FULL. No traversal modification.
    route_edges = trav.copy()
    route_edges["ib0d_version"] = VERSION
    route_edges["route_axis_mode"] = "keep_full_ib0b_traversal"
    route_edges["route_axis_included"] = True
    route_edges["route_axis_order"] = traversal_order

    row_count_preserved = len(route_edges) == len(trav)
    if not row_count_preserved:
        failures.append("route-axis traversal row count changed")

    axis_gdf = global_gdf.copy()
    axis_gdf["pipeline_stage"] = "ib0d_route_axis_finalize"
    axis_gdf["ib0d_version"] = VERSION
    axis_gdf["case_id"] = args.case_id
    axis_gdf["route_axis_mode"] = "keep_full_ib0b_traversal"
    axis_gdf["source_traversal_edges"] = str(traversal_fp)
    axis_gdf["source_global_traversal"] = str(global_fp)
    axis_gdf["source_gpx"] = "" if gpx_fp is None else str(gpx_fp)
    axis_gdf["traversal_occurrence_n"] = int(len(route_edges))
    axis_gdf["route_axis_length_m"] = route_len_m

    overall = len(failures) == 0

    summary = {
        "case_id": args.case_id,
        "ib0d_version": VERSION,
        "mode": "keep_full_ib0b_traversal",
        "input_traversal_edges_fp": str(traversal_fp),
        "input_global_traversal_fp": str(global_fp),
        "input_gpx_fp": "" if gpx_fp is None else str(gpx_fp),
        "input_traversal_occurrence_n": int(len(trav)),
        "output_traversal_occurrence_n": int(len(route_edges)),
        "route_axis_length_m": route_len_m,
        "metric_crs": None if metric_crs is None else str(metric_crs),
        "traversal_order_populated_pass": order_populated,
        "traversal_order_unique_pass": order_unique,
        "traversal_order_monotonic_pass": order_monotonic,
        "edge_id_populated_pass": edge_populated,
        "edge_occurrence_positive_pass": occurrence_positive,
        "edge_occurrence_unique_per_edge_pass": pair_unique,
        "direction_populated_pass": direction_populated,
        "canonical_identity_populated_pass": identity_populated,
        "osm_way_id_match_pass": way_identity_match,
        "global_geometry_nonempty_pass": geometry_nonempty,
        "global_geometry_valid_pass": geometry_valid,
        "row_count_preserved_pass": row_count_preserved,
        "overall_pass": overall,
        "failures": " | ".join(failures),
        "qa_html": str(out_html),
    }

    print("=" * 72)
    print("IB0D ROUTE AXIS FINALIZER", VERSION)
    print("=" * 72)
    print("case_id:", args.case_id)
    print("mode: keep_full_ib0b_traversal")
    print("input traversal occurrences:", len(trav))
    print(
        "route axis length m:",
        "NA" if route_len_m is None else f"{route_len_m:.2f}",
    )

    print("\n=== TRAVERSAL CONTRACT ===")
    checks = [
        ("traversal_order populated", order_populated),
        ("traversal_order unique", order_unique),
        ("traversal_order monotonic", order_monotonic),
        ("edge_id populated", edge_populated),
        ("edge_occurrence positive", occurrence_positive),
        ("(edge_id, occurrence) unique", pair_unique),
        ("direction populated", direction_populated),
        ("canonical OSM identity populated", identity_populated),
        ("way osm_way_id == osm_id", way_identity_match),
        ("row count preserved", row_count_preserved),
    ]
    for name, ok in checks:
        print(f"{name}: {'PASS' if ok else 'FAIL'}")

    print("\n=== ROUTE AXIS GEOMETRY ===")
    print("geometry non-empty:", "PASS" if geometry_nonempty else "FAIL")
    print("geometry valid:", "PASS" if geometry_valid else "FAIL")

    print("\nOVERALL IB0D:", "PASS" if overall else "FAIL")

    if failures:
        print("Failures:")
        for x in failures:
            print(" -", x)
        return 1

    route_edges.to_csv(out_edges, index=False, encoding="utf-8-sig")
    axis_gdf.to_file(out_axis, driver="GeoJSON")
    pd.DataFrame([summary]).to_csv(
        out_summary_csv, index=False, encoding="utf-8-sig"
    )
    out_summary_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    build_qa_html(
        case_id=args.case_id,
        ib0b_global=global_gdf,
        ib0d_axis=axis_gdf,
        out_html=out_html,
        route_len_m=route_len_m,
        traversal_n=len(route_edges),
        gpx_fp=gpx_fp,
    )

    print("\nOutputs")
    print("route axis:", out_axis.resolve())
    print("route axis edges:", out_edges.resolve())
    print("summary CSV:", out_summary_csv.resolve())
    print("summary JSON:", out_summary_json.resolve())
    print("QA HTML:", out_html.resolve())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
