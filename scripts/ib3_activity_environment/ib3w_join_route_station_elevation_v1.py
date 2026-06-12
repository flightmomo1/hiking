#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IB3W route-scoped station elevation join v1.

Purpose:
- Join historical qixing weather-station NLSC contour IDW elevation prototype
  back into route-scoped weather station candidates.
- Compute elevation_delta_m between station elevation and nearest route elevation.
- Preserve contour/elevation provenance.
- Do NOT perform weather fusion.
- Do NOT modify station registry, route risk, radar, THCI, or formal adapter outputs.

Scope:
- v1 is weather-candidate focused.
- v1 uses station_id join.
- v1 treats qixing_weather_station_elevation_from_nslc.csv as route-scoped prototype evidence,
  not as a formal global station elevation registry.
"""

from __future__ import annotations

import argparse
import csv
import html
from pathlib import Path
from typing import Dict, List, Optional


def parse_float(value: object) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        if text.lower() in {"nan", "none", "null"}:
            return None
        return float(text)
    except ValueError:
        return None


def load_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: List[Dict[str, object]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_elevation_index(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    index: Dict[str, Dict[str, str]] = {}
    duplicates: Dict[str, int] = {}

    for row in rows:
        station_id = str(row.get("station_id", "")).strip()
        if not station_id:
            continue
        if station_id in index:
            duplicates[station_id] = duplicates.get(station_id, 1) + 1
            continue
        index[station_id] = row

    if duplicates:
        dup_text = ", ".join(f"{k}x{v}" for k, v in sorted(duplicates.items()))
        raise ValueError(f"Duplicate station_id in elevation CSV: {dup_text}")

    return index


def join_rows(
    candidate_rows: List[Dict[str, str]],
    elevation_index: Dict[str, Dict[str, str]],
) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []

    for row in candidate_rows:
        joined: Dict[str, object] = dict(row)
        station_id = str(row.get("station_id", "")).strip()
        elev = elevation_index.get(station_id)

        route_ele = parse_float(row.get("route_nearest_elevation_m"))

        # Default: keep original missing state.
        joined["prototype_elevation_join_status"] = "NO_MATCH"
        joined["prototype_elevation_source_file_scope"] = "qixing_route_scoped_weather_station_prototype"
        joined["prototype_station_name"] = ""
        joined["prototype_station_lat"] = ""
        joined["prototype_station_lon"] = ""
        joined["prototype_dist_to_route_center_km"] = ""
        joined["prototype_station_quadrant"] = ""
        joined["prototype_elevation_source"] = ""
        joined["prototype_elevation_confidence"] = ""
        joined["prototype_elevation_search_radius_m"] = ""
        joined["prototype_n_contours_used"] = ""
        joined["prototype_nearest_contour_distance_m"] = ""
        joined["prototype_nearest_contour_elevation_m"] = ""
        joined["prototype_contour_elevation_min_m"] = ""
        joined["prototype_contour_elevation_max_m"] = ""
        joined["prototype_contour_elevation_std_m"] = ""
        joined["prototype_contour_elevation_field"] = ""
        joined["prototype_contour_shp_original_path"] = ""

        if elev is not None:
            station_ele = parse_float(elev.get("station_elevation_m"))
            joined["prototype_elevation_join_status"] = "JOINED"
            joined["prototype_station_name"] = elev.get("station_name", "")
            joined["prototype_station_lat"] = elev.get("station_lat", "")
            joined["prototype_station_lon"] = elev.get("station_lon", "")
            joined["prototype_dist_to_route_center_km"] = elev.get("dist_to_route_center_km", "")
            joined["prototype_station_quadrant"] = elev.get("station_quadrant", "")
            joined["prototype_elevation_source"] = elev.get("elevation_source", "")
            joined["prototype_elevation_confidence"] = elev.get("elevation_confidence", "")
            joined["prototype_elevation_search_radius_m"] = elev.get("elevation_search_radius_m", "")
            joined["prototype_n_contours_used"] = elev.get("n_contours_used", "")
            joined["prototype_nearest_contour_distance_m"] = elev.get("nearest_contour_distance_m", "")
            joined["prototype_nearest_contour_elevation_m"] = elev.get("nearest_contour_elevation_m", "")
            joined["prototype_contour_elevation_min_m"] = elev.get("contour_elevation_min_m", "")
            joined["prototype_contour_elevation_max_m"] = elev.get("contour_elevation_max_m", "")
            joined["prototype_contour_elevation_std_m"] = elev.get("contour_elevation_std_m", "")
            joined["prototype_contour_elevation_field"] = elev.get("contour_elevation_field", "")
            joined["prototype_contour_shp_original_path"] = elev.get("contour_shp", "")

            if station_ele is not None:
                joined["station_elevation_m"] = station_ele
                joined["station_elevation_source"] = elev.get("elevation_source", "nslc_contour_idw")
                joined["station_elevation_status"] = "AVAILABLE_PROTOTYPE"
                joined["elevation_lookup_status"] = "JOINED_FROM_QIXING_NLSC_PROTOTYPE"
                joined["needs_terrain_lookup"] = "false_for_joined_prototype"

                if route_ele is not None:
                    signed_delta = station_ele - route_ele
                    joined["elevation_delta_m"] = abs(signed_delta)
                    joined["elevation_delta_signed_m"] = signed_delta
                    joined["elevation_delta_status"] = "AVAILABLE_PROTOTYPE"
                else:
                    joined["elevation_delta_m"] = ""
                    joined["elevation_delta_signed_m"] = ""
                    joined["elevation_delta_status"] = "ROUTE_ELEVATION_MISSING"
            else:
                joined["elevation_delta_signed_m"] = ""
                joined["elevation_delta_status"] = "PROTOTYPE_ELEVATION_NULL"
        else:
            joined["elevation_delta_signed_m"] = ""

        out.append(joined)

    return out


def summarize(rows: List[Dict[str, object]], route_id: str) -> List[Dict[str, object]]:
    groups: Dict[str, Dict[str, object]] = {}

    for row in rows:
        status = str(row.get("prototype_elevation_join_status", "UNKNOWN"))
        g = groups.setdefault(
            status,
            {
                "route_id": route_id,
                "prototype_elevation_join_status": status,
                "candidate_count": 0,
                "min_candidate_rank": None,
                "max_candidate_rank": None,
                "min_distance_to_route_m": None,
                "max_distance_to_route_m": None,
            },
        )
        g["candidate_count"] = int(g["candidate_count"]) + 1

        rank = parse_float(row.get("candidate_rank"))
        if rank is not None:
            if g["min_candidate_rank"] is None or rank < float(g["min_candidate_rank"]):
                g["min_candidate_rank"] = int(rank)
            if g["max_candidate_rank"] is None or rank > float(g["max_candidate_rank"]):
                g["max_candidate_rank"] = int(rank)

        dist = parse_float(row.get("distance_to_route_m"))
        if dist is not None:
            if g["min_distance_to_route_m"] is None or dist < float(g["min_distance_to_route_m"]):
                g["min_distance_to_route_m"] = dist
            if g["max_distance_to_route_m"] is None or dist > float(g["max_distance_to_route_m"]):
                g["max_distance_to_route_m"] = dist

    return sorted(groups.values(), key=lambda r: str(r["prototype_elevation_join_status"]))


def write_html(path: Path, title: str, summary_rows: List[Dict[str, object]], top_rows: List[Dict[str, object]]) -> None:
    def table(rows: List[Dict[str, object]], cols: List[str]) -> str:
        head = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
        body = []
        for row in rows:
            tds = "".join(f"<td>{html.escape('' if row.get(c) is None else str(row.get(c)))}</td>" for c in cols)
            body.append(f"<tr>{tds}</tr>")
        return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"

    summary_cols = [
        "route_id",
        "prototype_elevation_join_status",
        "candidate_count",
        "min_candidate_rank",
        "max_candidate_rank",
        "min_distance_to_route_m",
        "max_distance_to_route_m",
    ]
    top_cols = [
        "candidate_rank",
        "candidate_role",
        "station_id",
        "station_name",
        "distance_to_route_m",
        "route_nearest_elevation_m",
        "station_elevation_m",
        "station_elevation_status",
        "elevation_delta_m",
        "elevation_delta_signed_m",
        "prototype_elevation_confidence",
        "prototype_elevation_join_status",
    ]

    doc = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; }}
table {{ border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 13px; }}
th, td {{ border: 1px solid #ddd; padding: 6px 8px; vertical-align: top; }}
th {{ background: #f4f4f4; text-align: left; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<p>IB3W route-scoped station elevation join v1. This is not weather fusion.</p>
<h2>Join summary</h2>
{table(summary_rows, summary_cols)}
<h2>Top weather candidates</h2>
{table(top_rows, top_cols)}
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Join route-scoped weather candidates with prototype station elevation.")
    parser.add_argument("--weather-candidates-csv", required=True)
    parser.add_argument("--station-elevation-csv", required=True)
    parser.add_argument("--route-id", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    weather_csv = Path(args.weather_candidates_csv)
    elevation_csv = Path(args.station_elevation_csv)
    out_dir = Path(args.out_dir) / args.route_id
    out_dir.mkdir(parents=True, exist_ok=True)

    weather_rows = load_csv_rows(weather_csv)
    elevation_rows = load_csv_rows(elevation_csv)
    elevation_index = build_elevation_index(elevation_rows)

    joined_rows = join_rows(weather_rows, elevation_index)
    summary_rows = summarize(joined_rows, args.route_id)

    base_fields = list(weather_rows[0].keys()) if weather_rows else []
    extra_fields = [
        "elevation_delta_signed_m",
        "prototype_elevation_join_status",
        "prototype_elevation_source_file_scope",
        "prototype_station_name",
        "prototype_station_lat",
        "prototype_station_lon",
        "prototype_dist_to_route_center_km",
        "prototype_station_quadrant",
        "prototype_elevation_source",
        "prototype_elevation_confidence",
        "prototype_elevation_search_radius_m",
        "prototype_n_contours_used",
        "prototype_nearest_contour_distance_m",
        "prototype_nearest_contour_elevation_m",
        "prototype_contour_elevation_min_m",
        "prototype_contour_elevation_max_m",
        "prototype_contour_elevation_std_m",
        "prototype_contour_elevation_field",
        "prototype_contour_shp_original_path",
    ]
    fieldnames = base_fields + [f for f in extra_fields if f not in base_fields]

    write_csv(out_dir / "weather_station_candidates_elevation_joined.csv", joined_rows, fieldnames)

    summary_fields = [
        "route_id",
        "prototype_elevation_join_status",
        "candidate_count",
        "min_candidate_rank",
        "max_candidate_rank",
        "min_distance_to_route_m",
        "max_distance_to_route_m",
    ]
    write_csv(out_dir / "weather_station_elevation_join_summary.csv", summary_rows, summary_fields)

    write_html(
        out_dir / "weather_station_elevation_join_summary.html",
        f"IB3W weather station elevation join: {args.route_id}",
        summary_rows,
        joined_rows[:20],
    )

    joined_n = sum(1 for r in joined_rows if r.get("prototype_elevation_join_status") == "JOINED")
    no_match_n = sum(1 for r in joined_rows if r.get("prototype_elevation_join_status") == "NO_MATCH")

    print("IB3W route-scoped station elevation join written")
    print(f"route_id: {args.route_id}")
    print(f"weather_candidates: {len(weather_rows)}")
    print(f"station_elevation_rows: {len(elevation_rows)}")
    print(f"joined: {joined_n}")
    print(f"no_match: {no_match_n}")
    print(f"out_dir: {out_dir}")


if __name__ == "__main__":
    main()
