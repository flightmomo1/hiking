# -*- coding: utf-8 -*-
"""QA route-axis ordering around qixing_lengshuikeng 37_1 route_dist 2.00-2.45 km."""

from __future__ import annotations

import math
from pathlib import Path

import folium
import numpy as np
import pandas as pd
from pyproj import Geod


CASE_ID = "qixing_lengshuikeng_main_peak_20260523"
ROUTE_PROFILE = Path(
    "outputs/ib1_route_profile/qixing_lengshuikeng_main_peak_20260523/"
    "qixing_lengshuikeng_main_peak_20260523_route_profile.csv"
)
ACTIVITY_LABELED = Path(
    "outputs/ib3a2_on_route_activity_filter/qixing_lengshuikeng/"
    "qixing_lengshuikeng_37_1_mapmatched_activity_labeled.csv"
)
OUT_DIR = Path("outputs/ib3b2_activity_profile_1d_2d/qixing_lengshuikeng/37_1/qa_route_axis_2p00_2p45km")
OUT_CSV = OUT_DIR / "qixing_lengshuikeng_37_1_route_axis_2p00_2p45km_qa_points.csv"
OUT_SUMMARY = OUT_DIR / "qixing_lengshuikeng_37_1_route_axis_2p00_2p45km_qa_summary.txt"
OUT_HTML = OUT_DIR / "qixing_lengshuikeng_37_1_route_axis_2p00_2p45km_debug_map.html"

WINDOW_START_M = 2000.0
WINDOW_END_M = 2450.0
MARK_A_M = 2101.0
MARK_B_M = 2380.0
GEOD = Geod(ellps="WGS84")


def bearing_and_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float]:
    az12, _, dist = GEOD.inv(lon1, lat1, lon2, lat2)
    return (az12 + 360.0) % 360.0, dist


def nearest_route_row(route: pd.DataFrame, dist_m: float) -> pd.Series:
    idx = (route["dist_m"] - dist_m).abs().idxmin()
    return route.loc[idx]


def add_marker(m: folium.Map, row: pd.Series, label: str, color: str) -> None:
    folium.Marker(
        [float(row["lat"]), float(row["lon"])],
        tooltip=label,
        popup=folium.Popup(
            f"{label}<br>dist_m={float(row['dist_m']):.1f}<br>"
            f"lat={float(row['lat']):.7f}<br>lon={float(row['lon']):.7f}",
            max_width=320,
        ),
        icon=folium.Icon(color=color, icon="info-sign"),
    ).add_to(m)


def add_route_labels(m: folium.Map, route_win: pd.DataFrame) -> None:
    for d in np.arange(WINDOW_START_M, WINDOW_END_M + 1, 50.0):
        r = nearest_route_row(route_win, d)
        folium.CircleMarker(
            [float(r["lat"]), float(r["lon"])],
            radius=4,
            color="#111827",
            fill=True,
            fill_color="#ffffff",
            fill_opacity=0.95,
            tooltip=f"{float(r['dist_m']) / 1000:.3f} km",
        ).add_to(m)
        folium.Marker(
            [float(r["lat"]), float(r["lon"])],
            icon=folium.DivIcon(
                html=(
                    '<div style="font-size:11px;font-weight:700;color:#111827;'
                    'text-shadow:0 0 3px white;white-space:nowrap;">'
                    f"{float(r['dist_m']) / 1000:.2f} km</div>"
                )
            ),
        ).add_to(m)


def build_route_qa(route: pd.DataFrame) -> pd.DataFrame:
    route = route.sort_values("dist_m").reset_index(drop=True).copy()
    route["point_index"] = route.index

    bearings = []
    seglens = []
    for i, row in route.iterrows():
        if i == len(route) - 1:
            bearings.append(np.nan)
            seglens.append(np.nan)
            continue
        nxt = route.iloc[i + 1]
        b, d = bearing_and_distance(row["lat"], row["lon"], nxt["lat"], nxt["lon"])
        bearings.append(b)
        seglens.append(d)

    route["bearing_to_next"] = bearings
    route["segment_length_to_next"] = seglens
    route["cumulative_route_dist_m"] = route["dist_m"]
    route["route_dist_m"] = route["dist_m"]
    route["ele_m"] = route["ele_smooth"] if "ele_smooth" in route.columns else route.get("ele_gpx_m", np.nan)
    return route


def add_activity_layers(m: folium.Map, activity: pd.DataFrame) -> None:
    activity = activity.copy()
    activity["usable_on_route"] = activity["usable_on_route"].astype(str).str.lower().isin(["true", "1", "yes"])
    near = activity[
        activity["route_dist_m"].between(WINDOW_START_M - 300, WINDOW_END_M + 300)
        | (~activity["usable_on_route"])
    ].copy()

    raw_coords = near[["lat", "lon"]].dropna().values.tolist()
    if raw_coords:
        folium.PolyLine(raw_coords, color="#64748b", weight=2, opacity=0.45, tooltip="37_1 raw GPS trajectory").add_to(m)

    for interp, g in near[~near["usable_on_route"]].groupby("manual_interpretation", dropna=False):
        coords = g[["lat", "lon"]].dropna().values.tolist()
        if len(coords) < 2:
            continue
        color = {
            "route_variant": "#f59e0b",
            "wrong_route": "#dc2626",
            "post_route": "#64748b",
        }.get(str(interp), "#7c3aed")
        folium.PolyLine(
            coords,
            color=color,
            weight=5,
            opacity=0.78,
            tooltip=f"excluded/manual: {interp or 'unlabeled'}",
        ).add_to(m)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    route_raw = pd.read_csv(ROUTE_PROFILE)
    activity = pd.read_csv(ACTIVITY_LABELED)

    route = build_route_qa(route_raw)
    route_win = route[route["dist_m"].between(WINDOW_START_M, WINDOW_END_M)].copy()
    route_win[
        [
            "point_index",
            "route_dist_m",
            "lat",
            "lon",
            "ele_m",
            "bearing_to_next",
            "segment_length_to_next",
            "cumulative_route_dist_m",
        ]
    ].to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    jumps = route_win[route_win["segment_length_to_next"] > 5.0]
    dist_delta = route_win["dist_m"].diff()
    nonmono = route_win[dist_delta <= 0]
    a = nearest_route_row(route, MARK_A_M)
    b = nearest_route_row(route, MARK_B_M)
    bearing_ab, geod_ab = bearing_and_distance(a["lat"], a["lon"], b["lat"], b["lon"])
    route_gap_ab = float(b["dist_m"] - a["dist_m"])

    summary = [
        "route_axis_window_qa",
        f"case_id: {CASE_ID}",
        f"window_m: {WINDOW_START_M:.0f}-{WINDOW_END_M:.0f}",
        f"route_points_in_window: {len(route_win)}",
        f"dist_monotonic_nonpositive_count: {len(nonmono)}",
        f"segment_length_gt_5m_count: {len(jumps)}",
        f"max_segment_length_to_next_m: {float(route_win['segment_length_to_next'].max()):.3f}",
        f"median_segment_length_to_next_m: {float(route_win['segment_length_to_next'].median()):.3f}",
        "",
        f"mark_2p101_nearest_dist_m: {float(a['dist_m']):.3f}",
        f"mark_2p101_lat_lon: {float(a['lat']):.8f}, {float(a['lon']):.8f}",
        f"mark_2p380_nearest_dist_m: {float(b['dist_m']):.3f}",
        f"mark_2p380_lat_lon: {float(b['lat']):.8f}, {float(b['lon']):.8f}",
        f"route_gap_2p101_to_2p380_m: {route_gap_ab:.3f}",
        f"straight_distance_2p101_to_2p380_m: {geod_ab:.3f}",
        f"bearing_2p101_to_2p380_deg: {bearing_ab:.1f}",
        "",
        "large_jumps_gt_5m:",
        jumps[["point_index", "dist_m", "segment_length_to_next", "bearing_to_next"]].head(20).to_string(index=False),
    ]
    OUT_SUMMARY.write_text("\n".join(summary) + "\n", encoding="utf-8")

    center = [float(route_win["lat"].mean()), float(route_win["lon"].mean())]
    m = folium.Map(location=center, zoom_start=17, tiles="OpenStreetMap")

    coords = route_win[["lat", "lon"]].values.tolist()
    folium.PolyLine(coords, color="#2563eb", weight=7, opacity=0.85, tooltip="route axis 2.00-2.45 km").add_to(m)
    folium.PolyLine(coords, color="#ffffff", weight=2, opacity=0.85).add_to(m)

    # Direction ticks every ~25 route meters.
    for d in np.arange(WINDOW_START_M + 25, WINDOW_END_M, 25):
        r = nearest_route_row(route_win, d)
        folium.CircleMarker(
            [float(r["lat"]), float(r["lon"])],
            radius=2.5,
            color="#2563eb",
            fill=True,
            fill_color="#2563eb",
            tooltip=f"direction point {float(r['dist_m']):.1f} m",
        ).add_to(m)

    add_route_labels(m, route_win)
    add_marker(m, a, "2.101 km route cursor check", "orange")
    add_marker(m, b, "2.380 km route cursor check", "red")
    add_activity_layers(m, activity)

    folium.LayerControl(collapsed=False).add_to(m)
    m.save(OUT_HTML)

    print(f"CSV: {OUT_CSV.resolve()}")
    print(f"summary: {OUT_SUMMARY.resolve()}")
    print(f"HTML: {OUT_HTML.resolve()}")
    print("\n".join(summary))


if __name__ == "__main__":
    main()
