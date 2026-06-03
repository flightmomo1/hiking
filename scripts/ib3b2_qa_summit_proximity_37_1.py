# -*- coding: utf-8 -*-
"""QA raw GPS summit proximity for qixing_lengshuikeng 37_1 row 4201-5156."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Geod


GEOD = Geod(ellps="WGS84")
CASE_ID = "qixing_lengshuikeng_main_peak_20260523"
ROUTE_FOLDER = "qixing_lengshuikeng"
ACTIVITY_ID = "37_1"
EVENT_START = 4201
EVENT_END = 5156
SEGMENT_SEC = 30

ROUTE_FP = Path(
    "outputs/ib1e_route_profile_contour_window_terrain/"
    f"{CASE_ID}/{CASE_ID}_route_profile_contour_window_terrain_enriched.csv"
)
ACTIVITY_FP = Path(
    "outputs/ib3a2_on_route_activity_filter/"
    f"{ROUTE_FOLDER}/{ROUTE_FOLDER}_{ACTIVITY_ID}_mapmatched_activity_labeled.csv"
)
OUT_DIR = Path(
    "outputs/ib3b2_activity_profile_1d_2d/"
    f"{ROUTE_FOLDER}/{ACTIVITY_ID}/event_qa_4201_5156"
)
OUT_CSV = OUT_DIR / f"{ROUTE_FOLDER}_{ACTIVITY_ID}_event_4201_5156_summit_proximity_qa.csv"
OUT_SUMMARY = OUT_DIR / f"{ROUTE_FOLDER}_{ACTIVITY_ID}_event_4201_5156_summit_proximity_summary.txt"


def fmt(value, digits=3) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, (bool, np.bool_)):
        return str(bool(value))
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        return f"{float(value):.{digits}f}"
    return str(value)


def bearing_and_distance(lon1, lat1, lon2, lat2):
    az12, _, dist = GEOD.inv(lon1, lat1, lon2, lat2)
    return (az12 + 360.0) % 360.0, dist


def load_summit(route: pd.DataFrame) -> pd.Series:
    ele_col = "ele_smooth" if route["ele_smooth"].notna().any() else "ele_gpx_m"
    idx = pd.to_numeric(route[ele_col], errors="coerce").idxmax()
    summit = route.loc[idx].copy()
    summit["summit_ele_m"] = summit[ele_col]
    return summit


def add_raw_metrics(event: pd.DataFrame, summit: pd.Series) -> pd.DataFrame:
    event = event.sort_values("row_index").copy()
    summit_lat = float(summit["lat"])
    summit_lon = float(summit["lon"])

    bearings_to_summit = []
    distances_to_summit = []
    bearings_to_next = []
    segment_lengths = []

    rows = event.reset_index(drop=True)
    for i, row in rows.iterrows():
        lat = float(row["lat"])
        lon = float(row["lon"])
        b_sum, d_sum = bearing_and_distance(lon, lat, summit_lon, summit_lat)
        bearings_to_summit.append(b_sum)
        distances_to_summit.append(d_sum)
        if i == len(rows) - 1:
            bearings_to_next.append(np.nan)
            segment_lengths.append(np.nan)
        else:
            nxt = rows.iloc[i + 1]
            b_next, d_next = bearing_and_distance(
                lon,
                lat,
                float(nxt["lon"]),
                float(nxt["lat"]),
            )
            bearings_to_next.append(b_next)
            segment_lengths.append(d_next)

    event["raw_distance_to_summit_m"] = distances_to_summit
    event["raw_delta_distance_to_summit_m"] = event["raw_distance_to_summit_m"].diff()
    event["raw_moving_toward_summit"] = event["raw_delta_distance_to_summit_m"] < 0
    event["raw_bearing_to_summit_deg"] = bearings_to_summit
    event["raw_bearing_to_next_deg"] = bearings_to_next
    event["raw_segment_length_to_next_m"] = segment_lengths
    return event


def make_segment_summary(event: pd.DataFrame) -> pd.DataFrame:
    start_t = float(event["elapsed_sec"].min())
    seg = event.copy()
    seg["time_segment_id"] = np.floor((seg["elapsed_sec"] - start_t) / SEGMENT_SEC).astype(int)
    grouped = []
    for seg_id, g in seg.groupby("time_segment_id"):
        grouped.append(
            {
                "time_segment_id": int(seg_id),
                "segment_start_elapsed_sec": float(g["elapsed_sec"].min()),
                "segment_end_elapsed_sec": float(g["elapsed_sec"].max()),
                "segment_start_row": int(g["row_index"].iloc[0]),
                "segment_end_row": int(g["row_index"].iloc[-1]),
                "mean_raw_lat": float(g["lat"].mean()),
                "mean_raw_lon": float(g["lon"].mean()),
                "mean_distance_to_summit_m": float(g["raw_distance_to_summit_m"].mean()),
                "min_distance_to_summit_m": float(g["raw_distance_to_summit_m"].min()),
                "max_distance_to_summit_m": float(g["raw_distance_to_summit_m"].max()),
                "distance_start_to_end_delta_m": float(
                    g["raw_distance_to_summit_m"].iloc[-1] - g["raw_distance_to_summit_m"].iloc[0]
                ),
                "toward_summit_fraction": float(g["raw_moving_toward_summit"].mean()),
                "median_raw_bearing_to_next_deg": float(g["raw_bearing_to_next_deg"].median()),
                "median_raw_bearing_to_summit_deg": float(g["raw_bearing_to_summit_deg"].median()),
                "route_dist_m_median": float(g["route_dist_m"].median()),
                "nearest_route_dist_m_median": float(g["nearest_route_dist_m"].median()),
                "offset_m_mean": float(g["offset_m"].mean()),
                "offset_m_max": float(g["offset_m"].max()),
            }
        )
    return pd.DataFrame(grouped)


def classify(event: pd.DataFrame, seg: pd.DataFrame) -> tuple[str, str, str]:
    d = event["raw_distance_to_summit_m"]
    start_d = float(d.iloc[0])
    min_d = float(d.min())
    max_d = float(d.max())
    end_d = float(d.iloc[-1])
    min_pos = int(d.idxmin())
    max_pos = int(d.idxmax())
    min_row = int(event.loc[min_pos, "row_index"])
    min_elapsed = float(event.loc[min_pos, "elapsed_sec"])
    max_row = int(event.loc[max_pos, "row_index"])
    max_elapsed = float(event.loc[max_pos, "elapsed_sec"])

    first_half = event[event["elapsed_sec"] <= event["elapsed_sec"].median()]
    second_half = event[event["elapsed_sec"] > event["elapsed_sec"].median()]
    first_toward = float(first_half["raw_moving_toward_summit"].mean())
    second_toward = float(second_half["raw_moving_toward_summit"].mean())
    approached = (start_d - min_d) >= 20.0 and min_elapsed < float(event["elapsed_sec"].max()) - 30.0
    departed_after_min = (end_d - min_d) >= 20.0
    returned_toward_from_max = (max_d - end_d) >= 50.0 and max_elapsed < float(event["elapsed_sec"].max()) - 30.0
    end_closer_than_start = end_d < start_d - 20.0

    if approached and departed_after_min:
        judgement = "raw_gps_shows_approach_then_depart_from_summit"
        note = (
            "raw GPS distance to summit decreases materially before increasing again; "
            "there is some evidence of movement toward the summit, followed by movement away."
        )
    elif returned_toward_from_max and second_toward > 0.6:
        judgement = "raw_gps_shows_away_then_return_toward_summit_area"
        note = (
            "raw GPS first moves away from the summit area, then the return leg moves geographically "
            "toward the summit area. However, the closest point to the summit is still the event start, "
            "so this is not evidence that the hiker became closer to the summit than where the event began."
        )
    elif end_closer_than_start or first_toward > 0.6:
        judgement = "raw_gps_shows_partial_movement_toward_summit"
        note = (
            "raw GPS distance to summit trends closer over part of the event, but does not clearly form "
            "a full approach-then-depart pattern."
        )
    else:
        judgement = "no_clear_raw_gps_movement_toward_summit"
        note = (
            "raw GPS distance to summit does not show a clear sustained approach; route_dist changes are "
            "more likely dominated by self-near mapmatching branch jumps."
        )

    if judgement == "raw_gps_shows_approach_then_depart_from_summit":
        recommendation = (
            "manual_note may mention possible movement toward summit during return, but phrase as GPS-based "
            "and uncertain; do not base it on matched route_dist alone."
        )
    elif judgement == "raw_gps_shows_away_then_return_toward_summit_area":
        recommendation = (
            "do not use the strong wording 「返回主幹路線過程中疑似再次往主峰方向移動」. Prefer: "
            "返回主幹路線過程中 raw GPS 與主峰距離由最遠點逐步縮短，但全段最近點在事件起點；山頂附近 self-near geometry "
            "與 mapmatching branch jump 使 matched route_dist 不宜作為方向判讀依據。"
        )
    elif judgement == "raw_gps_shows_partial_movement_toward_summit":
        recommendation = (
            "avoid changing note to a strong statement; if needed, use: "
            "返回主幹路線過程中 raw GPS 與主峰距離曾短暫縮短，但山頂附近 self-near geometry 使方向判讀需保守。"
        )
    else:
        recommendation = (
            "do not change manual_note to 「返回主幹路線過程中疑似再次往主峰方向移動」; keep wording focused on "
            "wrong-branch/return and self-near mapmatching ambiguity."
        )

    details = (
        f"first_half_toward_summit_fraction={first_toward:.3f}; "
        f"second_half_toward_summit_fraction={second_toward:.3f}; "
        f"min_distance_row_index={min_row}; min_distance_elapsed_sec={min_elapsed:.1f}; "
        f"max_distance_row_index={max_row}; max_distance_elapsed_sec={max_elapsed:.1f}; "
        f"start_min_delta_m={start_d - min_d:.1f}; end_min_delta_m={end_d - min_d:.1f}."
    )
    return judgement, note + " " + details, recommendation


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    route = pd.read_csv(ROUTE_FP)
    activity = pd.read_csv(ACTIVITY_FP)

    summit = load_summit(route)
    event = activity[activity["row_index"].between(EVENT_START, EVENT_END)].copy()
    event = add_raw_metrics(event, summit)
    seg = make_segment_summary(event)

    judgement, note, recommendation = classify(event, seg)
    d = event["raw_distance_to_summit_m"]
    min_idx = d.idxmin()

    row_cols = [
        "row_index",
        "point_index",
        "elapsed_sec",
        "lat",
        "lon",
        "route_dist_m",
        "nearest_route_dist_m",
        "offset_m",
        "match_quality",
        "usable_on_route",
        "manual_label",
        "manual_interpretation",
        "excluded_reason",
        "manual_event_id",
        "raw_distance_to_summit_m",
        "raw_delta_distance_to_summit_m",
        "raw_moving_toward_summit",
        "raw_bearing_to_summit_deg",
        "raw_bearing_to_next_deg",
        "raw_segment_length_to_next_m",
    ]
    out_rows = event[row_cols].copy()
    out_rows["record_type"] = "raw_gps_row"
    out_seg = seg.copy()
    out_seg["record_type"] = "segment_30s_summary"
    combined = pd.concat([out_rows, out_seg], ignore_index=True, sort=False)
    combined.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    lines = [
        "qixing_lengshuikeng_37_1_event_4201_5156_summit_proximity_summary",
        "",
        "summit_marker",
        f"summit_route_dist_m: {fmt(summit.get('dist_m'), 3)}",
        f"summit_lat: {fmt(summit.get('lat'), 8)}",
        f"summit_lon: {fmt(summit.get('lon'), 8)}",
        f"summit_ele_m: {fmt(summit.get('summit_ele_m'), 3)}",
        "",
        "raw_distance_to_summit_m",
        f"start: {fmt(d.iloc[0], 3)}",
        f"min: {fmt(d.min(), 3)}",
        f"median: {fmt(d.median(), 3)}",
        f"max: {fmt(d.max(), 3)}",
        f"end: {fmt(d.iloc[-1], 3)}",
        f"min_distance_to_summit_row_index: {fmt(event.loc[min_idx, 'row_index'], 0)}",
        f"min_distance_to_summit_elapsed_sec: {fmt(event.loc[min_idx, 'elapsed_sec'], 1)}",
        f"max_distance_to_summit_row_index: {fmt(event.loc[d.idxmax(), 'row_index'], 0)}",
        f"max_distance_to_summit_elapsed_sec: {fmt(event.loc[d.idxmax(), 'elapsed_sec'], 1)}",
        f"max_to_end_distance_decrease_m: {fmt(d.max() - d.iloc[-1], 3)}",
        "",
        "raw_bearing_progression",
        f"raw_bearing_to_next_start_deg: {fmt(event['raw_bearing_to_next_deg'].iloc[0], 1)}",
        f"raw_bearing_to_next_median_deg: {fmt(event['raw_bearing_to_next_deg'].median(), 1)}",
        f"raw_bearing_to_next_end_deg: {fmt(event['raw_bearing_to_next_deg'].dropna().iloc[-1], 1)}",
        f"raw_bearing_to_summit_start_deg: {fmt(event['raw_bearing_to_summit_deg'].iloc[0], 1)}",
        f"raw_bearing_to_summit_median_deg: {fmt(event['raw_bearing_to_summit_deg'].median(), 1)}",
        f"raw_bearing_to_summit_end_deg: {fmt(event['raw_bearing_to_summit_deg'].iloc[-1], 1)}",
        f"moving_toward_summit_fraction: {fmt(event['raw_moving_toward_summit'].mean(), 3)}",
        "",
        "segment_summary",
        f"segment_seconds: {SEGMENT_SEC}",
        f"segment_count: {len(seg)}",
        f"segment_mean_distance_to_summit_min_m: {fmt(seg['mean_distance_to_summit_m'].min(), 3)}",
        f"segment_mean_distance_to_summit_max_m: {fmt(seg['mean_distance_to_summit_m'].max(), 3)}",
        "",
        "judgement",
        f"raw_path_pattern: {judgement}",
        f"raw_path_approach_then_depart: {judgement == 'raw_gps_shows_approach_then_depart_from_summit'}",
        f"raw_path_away_then_return_toward_summit_area: {judgement == 'raw_gps_shows_away_then_return_toward_summit_area'}",
        f"is_matched_route_dist_only_artifact: {judgement == 'no_clear_raw_gps_movement_toward_summit'}",
        f"interpretation: {note}",
        f"manual_note_recommendation: {recommendation}",
        "",
        "outputs",
        f"csv: {OUT_CSV.as_posix()}",
        f"summary: {OUT_SUMMARY.as_posix()}",
    ]
    OUT_SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT_CSV.resolve())
    print(OUT_SUMMARY.resolve())
    print(judgement)


if __name__ == "__main__":
    main()
