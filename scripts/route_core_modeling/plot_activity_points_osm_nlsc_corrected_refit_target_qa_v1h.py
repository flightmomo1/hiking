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
    d0, d1 = cum[i - 1], cum[i]
    lat0, lon0 = coords[i - 1]
    lat1, lon1 = coords[i]

    if d1 == d0:
        return lat0, lon0

    t = (dist_m - d0) / (d1 - d0)
    return lat0 + t * (lat1 - lat0), lon0 + t * (lon1 - lon0)


def choose_target_dist(row):
    for col in [
        "route_dist_refit_m_v1h",
        "projected_route_dist_m",
        "route_dist_refit_m_v1g",
        "nearest_route_dist_m",
        "reliable_route_dist_m",
    ]:
        v = fnum(row.get(col))
        if v is not None:
            return v, col
    return None, ""


def status_color(row):
    status = row.get("route_context_model_status_v1h", "")
    applied = str(row.get("v1h_recovery_applied", "")).lower() == "true"

    if applied:
        return "#d62728", 5, "v1h reviewed recovery"

    if status == "matched_core_clean":
        return "#1f77b4", 3, "matched_core_clean"

    if status.startswith("matched_core_refit"):
        return "#17becf", 4, status

    if status.startswith("matched_core_recovered_from_v1h"):
        return "#d62728", 5, status

    if status.startswith("matched_core_recovered"):
        return "#2ca02c", 4, status

    if status == "matched_low_confidence_offset":
        return "#fdbf6f", 4, "remaining low confidence"

    if status == "no_activity_route_dist":
        return "#ff7f0e", 4, "remaining no activity route dist"

    return "#7f7f7f", 3, status or "unknown"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--route-folder", required=True)
    ap.add_argument("--activity-id", required=True)
    ap.add_argument("--corrected-fp", required=True)
    ap.add_argument("--route-geojson-fp", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--max-route-points", type=int, default=3000)
    ap.add_argument("--max-sample-points", type=int, default=3000)
    ap.add_argument("--max-refit-lines", type=int, default=500)
    args = ap.parse_args()

    with Path(args.corrected_fp).open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    route_coords, route_cum = load_route_coords(args.route_geojson_fp)

    # route sampling
    route_step = max(1, math.ceil(len(route_coords) / args.max_route_points))
    route_plot = route_coords[::route_step]

    valid_rows = [r for r in rows if fnum(r.get("lat")) is not None and fnum(r.get("lon")) is not None]
    sample_step = max(1, math.ceil(len(valid_rows) / args.max_sample_points))
    sampled_rows = valid_rows[::sample_step]

    lats = [fnum(r.get("lat")) for r in sampled_rows if fnum(r.get("lat")) is not None]
    lons = [fnum(r.get("lon")) for r in sampled_rows if fnum(r.get("lon")) is not None]
    center = [sum(lats) / len(lats), sum(lons) / len(lons)] if lats and lons else [route_coords[0][0], route_coords[0][1]]

    m = folium.Map(location=center, zoom_start=15, control_scale=True, tiles="OpenStreetMap")

    folium.PolyLine(
        route_plot,
        color="black",
        weight=4,
        opacity=0.8,
        tooltip="official mainline route",
    ).add_to(m)

    counts = {}
    for r in rows:
        s = r.get("route_context_model_status_v1h", "")
        counts[s] = counts.get(s, 0) + 1

    v1h_recovered = [r for r in valid_rows if str(r.get("v1h_recovery_applied", "")).lower() == "true"]
    remaining_orange = [
        r for r in valid_rows
        if r.get("route_context_model_status_v1h") in {"matched_low_confidence_offset", "no_activity_route_dist"}
    ]

    # Draw sampled points
    for r in sampled_rows:
        lat = fnum(r.get("lat"))
        lon = fnum(r.get("lon"))
        if lat is None or lon is None:
            continue

        color, radius, layer = status_color(r)
        tooltip = (
            f"elapsed={r.get('elapsed_sec')}<br>"
            f"v1g={r.get('route_context_model_status_v1g')}<br>"
            f"v1h={r.get('route_context_model_status_v1h')}<br>"
            f"v1h_applied={r.get('v1h_recovery_applied')}<br>"
            f"offset={r.get('offset_m')}<br>"
            f"route_dist_v1h={r.get('route_dist_refit_m_v1h')}<br>"
            f"method_v1h={r.get('route_dist_refit_method_v1h')}<br>"
            f"rule={r.get('v1h_recovery_rule')}"
        )

        folium.CircleMarker(
            [lat, lon],
            radius=radius,
            color=color,
            fill=True,
            fill_opacity=0.8,
            tooltip=tooltip,
        ).add_to(m)

    # Draw V1H recovered dashed lines
    refit_rows = v1h_recovered
    line_step = max(1, math.ceil(len(refit_rows) / max(1, args.max_refit_lines)))

    for r in refit_rows[::line_step]:
        lat = fnum(r.get("lat"))
        lon = fnum(r.get("lon"))
        if lat is None or lon is None:
            continue

        dist, src = choose_target_dist(r)
        target = interpolate_route(route_coords, route_cum, dist)
        if target is None:
            continue

        tlat, tlon = target

        folium.PolyLine(
            [[lat, lon], [tlat, tlon]],
            color="#d62728",
            weight=2,
            opacity=0.65,
            dash_array="6,6",
            tooltip=f"V1H recovered GPS → target elapsed={r.get('elapsed_sec')}, {src}={dist}",
        ).add_to(m)

        folium.CircleMarker(
            [tlat, tlon],
            radius=3,
            color="#67000d",
            fill=True,
            fill_opacity=0.9,
            tooltip=f"V1H target on mainline elapsed={r.get('elapsed_sec')}, {src}={dist}",
        ).add_to(m)

    legend_html = f"""
    <div style="background:white; padding:16px; border:1px solid #ccc; font-family:Arial; font-size:16px;">
      <h2>V1H Refit target QA: original GPS point → fitted mainline target</h2>
      <b>route_folder:</b> {args.route_folder}<br>
      <b>activity_id:</b> {args.activity_id}<br>
      <b>source_rows:</b> {len(rows)}<br>
      <b>sampled_records:</b> {len(sampled_rows)}<br>
      <b>v1h recovered rows:</b> {len(v1h_recovered)}<br>
      <b>remaining orange rows:</b> {len(remaining_orange)}<br><br>
      <span style="color:#d62728;">●</span> v1h reviewed mainline corridor recovery<br>
      <span style="color:#67000d;">●</span> v1h recovery target on mainline<br>
      <span style="color:#1f77b4;">●</span> matched_core_clean raw GPS<br>
      <span style="color:#17becf;">●</span> anchor/refit raw GPS<br>
      <span style="color:#2ca02c;">●</span> earlier recovered raw GPS<br>
      <span style="color:#fdbf6f;">●</span> remaining low confidence not recovered<br>
      <span style="color:#ff7f0e;">●</span> remaining no activity route dist<br>
      <span style="color:#d62728;">- - -</span> V1H recovered original GPS → mainline target<br><br>
      CSV remains the source of truth.
    </div>
    """

    m.get_root().html.add_child(folium.Element(legend_html))

    out_dir = Path(args.out_dir) / args.route_folder / args.activity_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_fp = out_dir / f"{args.route_folder}_{args.activity_id}_activity_points_osm_nlsc_corrected_refit_target_qa_v1h.html"

    m.save(out_fp)

    print("V1H refit target QA written")
    print("HTML:", out_fp)
    print("source rows:", len(rows))
    print("sampled records:", len(sampled_rows))
    print("v1h recovered rows:", len(v1h_recovered))
    print("remaining orange rows:", len(remaining_orange))


if __name__ == "__main__":
    main()
