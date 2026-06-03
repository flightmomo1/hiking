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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dryrun-csv", required=True)
    ap.add_argument("--route-geojson-fp", required=True)
    ap.add_argument("--route-folder", required=True)
    ap.add_argument("--activity-id", required=True)
    ap.add_argument("--cluster-id", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--max-lines", type=int, default=220)
    args = ap.parse_args()

    with Path(args.dryrun_csv).open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        raise RuntimeError("dryrun csv is empty")

    route_coords, route_cum = load_route_coords(args.route_geojson_fp)

    valid = [
        r for r in rows
        if fnum(r.get("lat")) is not None and fnum(r.get("lon")) is not None
    ]

    lats = [fnum(r["lat"]) for r in valid]
    lons = [fnum(r["lon"]) for r in valid]
    center = [sum(lats) / len(lats), sum(lons) / len(lons)]

    m = folium.Map(location=center, zoom_start=17, control_scale=True, tiles="OpenStreetMap")

    folium.PolyLine(
        route_coords,
        color="black",
        weight=4,
        opacity=0.85,
        tooltip="official mainline route",
    ).add_to(m)

    # Raw GPS track
    raw_track = [[fnum(r["lat"]), fnum(r["lon"])] for r in valid]
    folium.PolyLine(
        raw_track,
        color="#ff7f0e",
        weight=3,
        opacity=0.7,
        tooltip="raw GPS drift track",
    ).add_to(m)

    for r in valid:
        lat = fnum(r.get("lat"))
        lon = fnum(r.get("lon"))
        folium.CircleMarker(
            [lat, lon],
            radius=4,
            color="#ff7f0e",
            fill=True,
            fill_opacity=0.8,
            tooltip=(
                f"raw GPS elapsed={r.get('elapsed_sec')}<br>"
                f"offset={r.get('offset_m')}<br>"
                f"progress={r.get('raw_progress_ratio')}<br>"
                f"used_step={r.get('used_step_m')}<br>"
                f"target_dist_episode={r.get('episode_distance_preserving_target_route_dist_m')}<br>"
                f"projected_dist={r.get('current_projected_route_dist_m')}"
            ),
        ).add_to(m)

    step = max(1, math.ceil(len(valid) / max(1, args.max_lines)))

    episode_targets = []
    projected_targets = []

    for r in valid:
        ep_dist = fnum(r.get("episode_distance_preserving_target_route_dist_m"))
        prj_dist = fnum(r.get("current_projected_route_dist_m"))

        ep_target = interpolate_route(route_coords, route_cum, ep_dist)
        prj_target = interpolate_route(route_coords, route_cum, prj_dist)

        if ep_target:
            episode_targets.append(ep_target)
        if prj_target:
            projected_targets.append(prj_target)

    if projected_targets:
        folium.PolyLine(
            projected_targets,
            color="#00bcd4",
            weight=4,
            opacity=0.8,
            tooltip="point-level projected target sequence",
        ).add_to(m)

    if episode_targets:
        folium.PolyLine(
            episode_targets,
            color="#9467bd",
            weight=5,
            opacity=0.85,
            tooltip="episode-level distance-preserving target sequence",
        ).add_to(m)

    for r in valid[::step]:
        lat = fnum(r.get("lat"))
        lon = fnum(r.get("lon"))

        ep_dist = fnum(r.get("episode_distance_preserving_target_route_dist_m"))
        prj_dist = fnum(r.get("current_projected_route_dist_m"))

        ep_target = interpolate_route(route_coords, route_cum, ep_dist)
        prj_target = interpolate_route(route_coords, route_cum, prj_dist)

        if prj_target:
            folium.PolyLine(
                [[lat, lon], [prj_target[0], prj_target[1]]],
                color="#00bcd4",
                weight=2,
                opacity=0.35,
                dash_array="5,7",
                tooltip=f"raw GPS → point-level projected target elapsed={r.get('elapsed_sec')}",
            ).add_to(m)
            folium.CircleMarker(
                [prj_target[0], prj_target[1]],
                radius=3,
                color="#006d75",
                fill=True,
                fill_opacity=0.8,
                tooltip=f"point-level projected target elapsed={r.get('elapsed_sec')}, dist={prj_dist}",
            ).add_to(m)

        if ep_target:
            folium.PolyLine(
                [[lat, lon], [ep_target[0], ep_target[1]]],
                color="#9467bd",
                weight=2,
                opacity=0.55,
                dash_array="8,5",
                tooltip=f"raw GPS → episode-level target elapsed={r.get('elapsed_sec')}",
            ).add_to(m)
            folium.CircleMarker(
                [ep_target[0], ep_target[1]],
                radius=3,
                color="#4a1486",
                fill=True,
                fill_opacity=0.9,
                tooltip=f"episode-level target elapsed={r.get('elapsed_sec')}, dist={ep_dist}",
            ).add_to(m)

    first = rows[0]
    last = rows[-1]

    title_html = f"""
    <div style="position: fixed; top: 10px; left: 50px; z-index: 9999;
                background: white; padding: 12px; border: 2px solid #333;
                font-family: Arial; font-size: 14px; max-width: 820px;">
      <b>Episode-level distance-preserving refit dry-run comparison</b><br>
      route_folder: {args.route_folder}<br>
      activity_id: {args.activity_id}, cluster_id: {args.cluster_id}<br>
      elapsed: {first.get('elapsed_sec')}–{last.get('elapsed_sec')}<br>
      rows: {len(rows)}<br>
      anchor route_dist: {first.get('before_anchor_route_dist_m')} → {first.get('after_anchor_route_dist_m')}<br>
      route_span_m: {first.get('route_span_m')}<br>
      episode_total_used_m: {first.get('episode_total_used_m')}<br><br>
      <span style="color:black;">━━</span> official mainline<br>
      <span style="color:#ff7f0e;">━━</span> raw GPS drift track<br>
      <span style="color:#00bcd4;">━━</span> point-level projected target sequence<br>
      <span style="color:#9467bd;">━━</span> episode-level distance-preserving target sequence<br>
      Cyan dashed: raw GPS → point-level target<br>
      Purple dashed: raw GPS → episode-level target<br>
      Dry-run only. CSV remains the source of truth.
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    out_base = Path(args.out_dir)
    if not out_base.is_absolute():
        out_base = Path.cwd() / out_base

    out_dir = (out_base / args.route_folder / args.activity_id).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    out_fp = out_dir / f"{args.route_folder}_{args.activity_id}_cluster{args.cluster_id}_episode_level_distance_preserving_refit_compare.html"

    print("debug out_dir:", out_dir)
    print("debug out_dir exists:", out_dir.exists())
    print("debug out_fp:", out_fp)

    m.save(str(out_fp))

    print("wrote:", out_fp)
    print("rows:", len(rows))


if __name__ == "__main__":
    main()

