#!/usr/bin/env python3
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point, LineString, MultiLineString, MultiPoint, GeometryCollection


def local(tag):
    return tag.split("}")[-1]


def extract_points(g):
    if g is None or g.is_empty:
        return []
    if isinstance(g, Point):
        return [g]
    if isinstance(g, MultiPoint):
        return list(g.geoms)
    if isinstance(g, GeometryCollection):
        out = []
        for part in g.geoms:
            out.extend(extract_points(part))
        return out
    return []


def parse_gpx(fp):
    root = ET.parse(fp).getroot()
    for kind in ("trkpt", "rtept"):
        pts = []
        for e in root.iter():
            if local(e.tag) != kind:
                continue
            ele = None
            for c in e:
                if local(c.tag) == "ele":
                    try:
                        ele = float(c.text)
                    except Exception:
                        pass
            if ele is not None:
                pts.append((float(e.attrib["lon"]), float(e.attrib["lat"]), ele))
        if len(pts) >= 2:
            return pts
    raise RuntimeError("No GPX track/route with at least two elevation points")


def main():
    ap = argparse.ArgumentParser(description="Build direct GPX x contour elevation anchors and map them to Route Axis chainage.")
    ap.add_argument("--gpx", required=True)
    ap.add_argument("--route-axis", required=True)
    ap.add_argument("--contour", required=True)
    ap.add_argument("--elevation-field", default="zv2")
    ap.add_argument("--analysis-crs", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    pts = parse_gpx(args.gpx)
    pg = gpd.GeoDataFrame(
        pd.DataFrame(pts, columns=["lon", "lat", "ele_gpx_m"]),
        geometry=[Point(lon, lat) for lon, lat, _ in pts],
        crs="EPSG:4326",
    ).to_crs(args.analysis_crs)

    xy = np.array([[g.x, g.y] for g in pg.geometry])
    seg = np.sqrt(np.sum(np.diff(xy, axis=0) ** 2, axis=1))
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    gpx_line = LineString([(g.x, g.y) for g in pg.geometry])
    gpx_ele = pg["ele_gpx_m"].to_numpy(float)

    route = gpd.read_file(args.route_axis).to_crs(args.analysis_crs)
    if len(route) != 1:
        raise RuntimeError(f"Expected one Route Axis feature, got {len(route)}")
    route_line = route.geometry.iloc[0]

    contour = gpd.read_file(args.contour).to_crs(args.analysis_crs).copy()
    if args.elevation_field not in contour.columns:
        raise RuntimeError(f"Missing contour elevation field: {args.elevation_field}")
    contour["_z"] = pd.to_numeric(contour[args.elevation_field], errors="coerce")

    idx = list(contour.sindex.intersection(gpx_line.bounds))
    cand = contour.iloc[idx]
    cand = cand[cand.intersects(gpx_line)]

    rows = []
    for source_idx, row in cand.iterrows():
        if pd.isna(row["_z"]):
            continue
        inter = row.geometry.intersection(gpx_line)
        if isinstance(inter, (LineString, MultiLineString)):
            continue
        for pt in extract_points(inter):
            gd = float(gpx_line.project(pt))
            rd = float(route_line.project(pt))
            ele = float(np.interp(gd, cum, gpx_ele))
            rows.append({
                "source_contour_idx": int(source_idx),
                "gpx_dist_m": gd,
                "route_dist_m": rd,
                "gpx_to_route_axis_m": float(pt.distance(route_line)),
                "contour_z_m": float(row["_z"]),
                "gpx_ele_interp_m": ele,
                "nlsc_minus_gpx_m": float(row["_z"]) - ele,
            })

    x = pd.DataFrame(rows)
    if x.empty:
        raise RuntimeError("No direct GPX-contour point crossings found")
    x = x.sort_values(["gpx_dist_m", "contour_z_m"]).reset_index(drop=True)

    keep = []
    last_d = last_z = None
    for i, r in x.iterrows():
        d = float(r["gpx_dist_m"])
        z = float(r["contour_z_m"])
        dup = last_d is not None and abs(d - last_d) <= 0.5 and abs(z - last_z) <= 1e-9
        if not dup:
            keep.append(i)
            last_d, last_z = d, z
    x = x.loc[keep].sort_values("route_dist_m").reset_index(drop=True)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    x.to_csv(out, index=False, encoding="utf-8-sig")
    print("anchors:", len(x))
    print("median_nlsc_minus_gpx_m:", float(x["nlsc_minus_gpx_m"].median()))
    print("median_gpx_to_route_axis_m:", float(x["gpx_to_route_axis_m"].median()))
    print("output:", out)


if __name__ == "__main__":
    main()
