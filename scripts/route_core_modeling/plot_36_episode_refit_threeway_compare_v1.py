import argparse
import csv
import json
import math
from pathlib import Path

import folium


def fnum(x):
    if x is None:
        return None
    s = str(x).strip()
    if s == "":
        return None
    try:
        return float(s)
    except Exception:
        return None


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def load_route_coords(route_geojson_fp):
    data = json.loads(Path(route_geojson_fp).read_text(encoding="utf-8"))
    coords = []

    def add_geom(geom):
        if not geom:
            return
        gtype = geom.get("type")
        gc = geom.get("coordinates")
        if gtype == "LineString":
            for lon, lat, *rest in gc:
                coords.append((float(lat), float(lon)))
        elif gtype == "MultiLineString":
            for line in gc:
                for lon, lat, *rest in line:
                    coords.append((float(lat), float(lon)))

    if data.get("type") == "FeatureCollection":
        for feat in data.get("features", []):
            add_geom(feat.get("geometry"))
    elif data.get("type") == "Feature":
        add_geom(data.get("geometry"))
    else:
        add_geom(data)

    if len(coords) < 2:
        raise ValueError("route geojson has fewer than 2 coordinates")

    cum = [0.0]
    for i in range(1, len(coords)):
        lat1, lon1 = coords[i - 1]
        lat2, lon2 = coords[i]
        cum.append(cum[-1] + haversine_m(lat1, lon1, lat2, lon2))

    return coords, cum


def interpolate_route(coords, cum, dist_m):
    if dist_m is None:
        return None

    if dist_m <= cum[0]:
        return coords[0]
    if dist_m >= cum[-1]:
        return coords[-1]

    lo, hi = 0, len(cum) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if cum[mid] < dist_m:
            lo = mid + 1
        else:
            hi = mid

    i = max(1, lo)
    d0 = cum[i - 1]
    d1 = cum[i]
    lat0, lon0 = coords[i - 1]
    lat1, lon1 = coords[i]

    if d1 == d0:
        return lat0, lon0

    t = (dist_m - d0) / (d1 - d0)
    return lat0 + t * (lat1 - lat0), lon0 + t * (lon1 - lon0)


def read_csv(fp):
    with Path(fp).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--distance-dryrun-csv", required=True)
    ap.add_argument("--monotonic-dryrun-csv", required=True)
    ap.add_argument("--route-geojson-fp", required=True)
    ap.add_argument("--route-folder", required=True)
    ap.add_argument("--activity-id", required=True)
    ap.add_argument("--cluster-id", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--max-lines", type=int, default=180)
    args = ap.parse_args()

    dist_rows = read_csv(args.distance_dryrun_csv)
    mono_rows = read_csv(args.monotonic_dryrun_csv)

    mono_by_elapsed = {str(r.get("elapsed_sec")): r for r in mono_rows}

    rows = []
    for r in dist_rows:
        e = str(r.get("elapsed_sec"))
        m = mono_by_elapsed.get(e, {})
        rr = dict(r)
        rr["time_linear_target_route_dist_m"] = m.get("time_linear_target_route_dist_m", "")
        rr["aggressive_capped_step_target_route_dist_m"] = m.get("aggressive_capped_step_target_route_dist_m", "")
        rows.append(rr)

    route_coords, route_cum = load_route_coords(args.route_geojson_fp)

    valid = [
        r for r in rows
        if fnum(r.get("lat")) is not None and fnum(r.get("lon")) is not None
    ]

    if not valid:
        raise RuntimeError("No valid rows to plot.")

    lats = [fnum(r["lat"]) for r in valid]
    lons = [fnum(r["lon"]) for r in valid]
    center = [sum(lats) / len(lats), sum(lons) / len(lons)]

    m = folium.Map(location=center, zoom_start=17, control_scale=True, tiles="OpenStreetMap")

    folium.PolyLine(
        route_coords,
        color="black",
        weight=4,
        opacity=0.85,
        tooltip="official mainline",
    ).add_to(m)

    raw_track = [[fnum(r["lat"]), fnum(r["lon"])] for r in valid]
    folium.PolyLine(
        raw_track,
        color="#ff7f0e",
        weight=3,
        opacity=0.65,
        tooltip="raw GPS drift track",
    ).add_to(m)

    projected_targets = []
    distance_targets = []
    time_linear_targets = []

    for r in valid:
        prj = interpolate_route(route_coords, route_cum, fnum(r.get("current_projected_route_dist_m")))
        dst = interpolate_route(route_coords, route_cum, fnum(r.get("episode_distance_preserving_target_route_dist_m")))
        tln = interpolate_route(route_coords, route_cum, fnum(r.get("time_linear_target_route_dist_m")))

        if prj:
            projected_targets.append(prj)
        if dst:
            distance_targets.append(dst)
        if tln:
            time_linear_targets.append(tln)

    if projected_targets:
        folium.PolyLine(
            projected_targets,
            color="#00bcd4",
            weight=4,
            opacity=0.85,
            tooltip="point-level projected target sequence",
        ).add_to(m)

    if distance_targets:
        folium.PolyLine(
            distance_targets,
            color="#9467bd",
            weight=4,
            opacity=0.85,
            tooltip="distance-preserving target sequence",
        ).add_to(m)

    if time_linear_targets:
        folium.PolyLine(
            time_linear_targets,
            color="#d62728",
            weight=5,
            opacity=0.9,
            tooltip="time-linear monotonic target sequence",
        ).add_to(m)

    step = max(1, math.ceil(len(valid) / max(1, args.max_lines)))

    for r in valid[::step]:
        lat = fnum(r.get("lat"))
        lon = fnum(r.get("lon"))
        if lat is None or lon is None:
            continue

        prj_dist = fnum(r.get("current_projected_route_dist_m"))
        dst_dist = fnum(r.get("episode_distance_preserving_target_route_dist_m"))
        tln_dist = fnum(r.get("time_linear_target_route_dist_m"))

        prj = interpolate_route(route_coords, route_cum, prj_dist)
        dst = interpolate_route(route_coords, route_cum, dst_dist)
        tln = interpolate_route(route_coords, route_cum, tln_dist)

        folium.CircleMarker(
            [lat, lon],
            radius=3,
            color="#ff7f0e",
            fill=True,
            fill_opacity=0.75,
            tooltip=(
                f"raw elapsed={r.get('elapsed_sec')}<br>"
                f"offset={r.get('offset_m')}<br>"
                f"projected={prj_dist}<br>"
                f"distance_preserving={dst_dist}<br>"
                f"time_linear={tln_dist}"
            ),
        ).add_to(m)

        if prj:
            folium.PolyLine(
                [[lat, lon], [prj[0], prj[1]]],
                color="#00bcd4",
                weight=1,
                opacity=0.25,
                dash_array="5,7",
            ).add_to(m)

        if dst:
            folium.PolyLine(
                [[lat, lon], [dst[0], dst[1]]],
                color="#9467bd",
                weight=1,
                opacity=0.35,
                dash_array="7,6",
            ).add_to(m)

        if tln:
            folium.PolyLine(
                [[lat, lon], [tln[0], tln[1]]],
                color="#d62728",
                weight=2,
                opacity=0.45,
                dash_array="8,5",
            ).add_to(m)

    first = valid[0]
    last = valid[-1]

    title_html = f"""
    <div style="position: fixed; top: 10px; left: 50px; z-index: 9999;
                background: white; padding: 12px; border: 2px solid #333;
                font-family: Arial; font-size: 14px; max-width: 850px;">
      <b>36_1 cluster2 three-way episode refit comparison</b><br>
      route_folder: {args.route_folder}<br>
      activity_id: {args.activity_id}, cluster_id: {args.cluster_id}<br>
      elapsed: {first.get('elapsed_sec')}–{last.get('elapsed_sec')}<br>
      rows: {len(valid)}<br>
      anchor route_dist: {first.get('before_anchor_route_dist_m')} → {first.get('after_anchor_route_dist_m')}<br>
      route_span_m: {first.get('route_span_m')}<br><br>
      <span style="color:black;">━━</span> official mainline<br>
      <span style="color:#ff7f0e;">━━</span> raw GPS drift track<br>
      <span style="color:#00bcd4;">━━</span> point-level projected target<br>
      <span style="color:#9467bd;">━━</span> distance-preserving target<br>
      <span style="color:#d62728;">━━</span> time-linear monotonic target<br><br>
      Dry-run only. CSV remains the source of truth.
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    out_base = Path(args.out_dir)
    if not out_base.is_absolute():
        out_base = Path.cwd() / out_base

    out_dir = (out_base / args.route_folder / args.activity_id).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    out_fp = out_dir / f"{args.activity_id}_c{args.cluster_id}_threeway_refit_compare.html"

    print("debug out_dir:", out_dir)
    print("debug out_dir exists:", out_dir.exists())
    print("debug out_fp:", out_fp)

    m.save(str(out_fp))

    print("wrote:", out_fp)
    print("rows:", len(valid))


if __name__ == "__main__":
    main()
