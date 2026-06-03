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

    def add_coords_from_geom(geom):
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
            add_coords_from_geom(feat.get("geometry"))
    elif data.get("type") == "Feature":
        add_coords_from_geom(data.get("geometry"))
    else:
        add_coords_from_geom(data)

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


def choose_target_dist(row):
    # V1H candidate 尚未真正 recovery 時，route_dist_refit_m_v1g 可能仍空或不可靠。
    # 優先使用 projected_route_dist_m；若空，再用 route_dist_refit_m_v1g / nearest_route_dist_m。
    for col in ["projected_route_dist_m", "route_dist_refit_m_v1g", "nearest_route_dist_m", "reliable_route_dist_m"]:
        v = fnum(row.get(col))
        if v is not None:
            return v, col
    return None, ""


def is_candidate(row):
    return row.get("route_context_model_status_v1g") in {
        "matched_low_confidence_offset",
        "no_activity_route_dist",
    }


def is_usable(row):
    if str(row.get("route_context_model_usable_v1g", "")).lower() == "true":
        return True
    status = row.get("route_context_model_status_v1g", "")
    return status.startswith("matched_core_clean") or status.startswith("matched_core_refit") or status.startswith("matched_core_recovered")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--route-folder", required=True)
    ap.add_argument("--activity-id", required=True)
    ap.add_argument("--cluster-id", required=True)
    ap.add_argument("--activity-csv", required=True)
    ap.add_argument("--clusters-csv", required=True)
    ap.add_argument("--route-geojson-fp", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--context-sec", type=float, default=60.0)
    ap.add_argument("--max-dashed-lines", type=int, default=120)
    ap.add_argument("--max-anchor-dashed-lines", type=int, default=80)
    args = ap.parse_args()

    activity_fp = Path(args.activity_csv)
    clusters_fp = Path(args.clusters_csv)
    out_dir = Path(args.out_dir) / args.route_folder / args.activity_id
    out_dir.mkdir(parents=True, exist_ok=True)

    with clusters_fp.open("r", encoding="utf-8-sig", newline="") as f:
        clusters = list(csv.DictReader(f))

    cluster = None
    for c in clusters:
        if c.get("activity_id") == args.activity_id and str(c.get("cluster_id")) == str(args.cluster_id):
            cluster = c
            break

    if cluster is None:
        raise ValueError(f"cluster not found: {args.activity_id} cluster {args.cluster_id}")

    c_start = fnum(cluster["start_elapsed_sec"])
    c_end = fnum(cluster["end_elapsed_sec"])
    start = c_start - args.context_sec
    end = c_end + args.context_sec

    with activity_fp.open("r", encoding="utf-8-sig", newline="") as f:
        all_rows = list(csv.DictReader(f))

    rows = []
    for r in all_rows:
        e = fnum(r.get("elapsed_sec"))
        if e is not None and start <= e <= end:
            rows.append(r)

    if not rows:
        raise ValueError("no rows in cluster context window")

    route_coords, route_cum = load_route_coords(args.route_geojson_fp)

    lats = [fnum(r.get("lat")) for r in rows if fnum(r.get("lat")) is not None]
    lons = [fnum(r.get("lon")) for r in rows if fnum(r.get("lon")) is not None]

    center = [sum(lats) / len(lats), sum(lons) / len(lons)] if lats and lons else [route_coords[0][0], route_coords[0][1]]
    m = folium.Map(location=center, zoom_start=17, control_scale=True, tiles="OpenStreetMap")

    folium.PolyLine(
        locations=route_coords,
        color="black",
        weight=4,
        opacity=0.8,
        tooltip="official mainline route",
    ).add_to(m)

    candidate_rows = [r for r in rows if is_candidate(r)]
    usable_rows = [r for r in rows if is_usable(r)]

    # context usable anchors
    for r in usable_rows:
        lat = fnum(r.get("lat"))
        lon = fnum(r.get("lon"))
        if lat is None or lon is None:
            continue
        e = r.get("elapsed_sec")
        rd = r.get("route_dist_refit_m_v1g") or r.get("reliable_route_dist_m") or r.get("projected_route_dist_m")
        folium.CircleMarker(
            location=[lat, lon],
            radius=3,
            color="#1f77b4",
            fill=True,
            fill_opacity=0.75,
            tooltip=f"usable anchor elapsed={e}, route_dist={rd}, status={r.get('route_context_model_status_v1g')}",
        ).add_to(m)

    # usable anchor original GPS -> mainline target dashed lines
    # 目的：確認前後藍色 usable anchors 雖然 raw GPS 偏離黑線，
    # 但仍可依 route_dist 對齊回 OSM official mainline。
    anchor_step = max(1, math.ceil(len(usable_rows) / max(1, args.max_anchor_dashed_lines)))

    for r in usable_rows[::anchor_step]:
        lat = fnum(r.get("lat"))
        lon = fnum(r.get("lon"))
        if lat is None or lon is None:
            continue

        anchor_dist, anchor_src = choose_target_dist(r)
        anchor_target = interpolate_route(route_coords, route_cum, anchor_dist)
        if anchor_target is None:
            continue

        tlat, tlon = anchor_target

        folium.PolyLine(
            locations=[[lat, lon], [tlat, tlon]],
            color="#9ecae1",
            weight=1,
            opacity=0.45,
            dash_array="3,7",
            tooltip=f"usable anchor GPS → target elapsed={r.get('elapsed_sec')}, {anchor_src}={anchor_dist}",
        ).add_to(m)

        folium.CircleMarker(
            location=[tlat, tlon],
            radius=2,
            color="#08519c",
            fill=True,
            fill_opacity=0.75,
            tooltip=f"usable anchor target on mainline elapsed={r.get('elapsed_sec')}, {anchor_src}={anchor_dist}",
        ).add_to(m)

    # candidate orange points
    for r in candidate_rows:
        lat = fnum(r.get("lat"))
        lon = fnum(r.get("lon"))
        if lat is None or lon is None:
            continue
        e = fnum(r.get("elapsed_sec"))
        in_cluster = c_start <= e <= c_end
        color = "#ff7f0e" if in_cluster else "#fdbf6f"
        radius = 5 if in_cluster else 3

        target_dist, target_src = choose_target_dist(r)
        tooltip = (
            f"candidate elapsed={r.get('elapsed_sec')}<br>"
            f"status={r.get('route_context_model_status_v1g')}<br>"
            f"offset={r.get('offset_m')}<br>"
            f"target_dist={target_dist} ({target_src})"
        )

        folium.CircleMarker(
            location=[lat, lon],
            radius=radius,
            color=color,
            fill=True,
            fill_opacity=0.9,
            tooltip=tooltip,
        ).add_to(m)

    # dashed lines for in-cluster candidate rows, sampled
    in_cluster_candidates = []
    for r in candidate_rows:
        e = fnum(r.get("elapsed_sec"))
        if e is not None and c_start <= e <= c_end:
            in_cluster_candidates.append(r)

    step = max(1, math.ceil(len(in_cluster_candidates) / max(1, args.max_dashed_lines)))

    for r in in_cluster_candidates[::step]:
        lat = fnum(r.get("lat"))
        lon = fnum(r.get("lon"))
        if lat is None or lon is None:
            continue

        target_dist, target_src = choose_target_dist(r)
        target = interpolate_route(route_coords, route_cum, target_dist)
        if target is None:
            continue

        tlat, tlon = target

        folium.PolyLine(
            locations=[[lat, lon], [tlat, tlon]],
            color="#00bcd4",
            weight=2,
            opacity=0.65,
            dash_array="6,6",
            tooltip=f"GPS → target elapsed={r.get('elapsed_sec')}, {target_src}={target_dist}",
        ).add_to(m)

        folium.CircleMarker(
            location=[tlat, tlon],
            radius=3,
            color="#08306b",
            fill=True,
            fill_opacity=0.9,
            tooltip=f"target on mainline elapsed={r.get('elapsed_sec')}, {target_src}={target_dist}",
        ).add_to(m)

    # cluster start / end markers
    start_rows = sorted(in_cluster_candidates, key=lambda r: abs((fnum(r.get("elapsed_sec")) or 0) - c_start))
    end_rows = sorted(in_cluster_candidates, key=lambda r: abs((fnum(r.get("elapsed_sec")) or 0) - c_end))

    if start_rows:
        r = start_rows[0]
        lat = fnum(r.get("lat"))
        lon = fnum(r.get("lon"))
        if lat is not None and lon is not None:
            folium.Marker(
                [lat, lon],
                popup=f"cluster start {args.activity_id} cluster {args.cluster_id}, elapsed={r.get('elapsed_sec')}",
                icon=folium.Icon(color="green", icon="play"),
            ).add_to(m)

    if end_rows:
        r = end_rows[0]
        lat = fnum(r.get("lat"))
        lon = fnum(r.get("lon"))
        if lat is not None and lon is not None:
            folium.Marker(
                [lat, lon],
                popup=f"cluster end {args.activity_id} cluster {args.cluster_id}, elapsed={r.get('elapsed_sec')}",
                icon=folium.Icon(color="red", icon="stop"),
            ).add_to(m)

    title_html = f"""
    <div style="position: fixed; top: 10px; left: 50px; z-index: 9999;
                background: white; padding: 12px; border: 2px solid #333;
                font-family: Arial; font-size: 14px; max-width: 760px;">
      <b>V1H cluster-focused refit target QA</b><br>
      route_folder: {args.route_folder}<br>
      activity_id: {args.activity_id}<br>
      cluster_id: {args.cluster_id}<br>
      elapsed: {c_start}–{c_end}, context: {start}–{end}<br>
      rows in context: {len(rows)}, candidate rows in cluster: {len(in_cluster_candidates)}<br>
      rows_total: {cluster.get("rows_total")}, block_count: {cluster.get("block_count")}<br>
      offset median range: {cluster.get("offset_median_min")}–{cluster.get("offset_median_max")}<br>
      action_mix: {cluster.get("action_mix")}<br>
      Cyan dashed lines: V1H candidate GPS point → interpolated mainline target.<br>
      Light-blue dashed lines: usable anchor GPS point → interpolated mainline target.
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    out_html = out_dir / f"{args.route_folder}_{args.activity_id}_cluster{args.cluster_id}_v1h_cluster_focused_refit_target_qa.html"
    m.save(out_html)

    print("wrote:", out_html)
    print("context rows:", len(rows))
    print("candidate rows in cluster:", len(in_cluster_candidates))


if __name__ == "__main__":
    main()
