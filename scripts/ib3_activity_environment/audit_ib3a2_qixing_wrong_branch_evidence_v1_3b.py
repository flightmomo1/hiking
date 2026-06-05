"""Wrong-branch evidence audit for qixing 37_1 repaired IB3A2 segment."""

from __future__ import annotations

import bisect
import csv
import html
import json
import math
from pathlib import Path
from statistics import median
from typing import Any


CASE_ID = "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b"
ROUTE_FOLDER = "qixing_lengshuikeng"
ACTIVITY_ID = "37_1"
TARGET_ELAPSED_MIN_START = 39.32
TARGET_ELAPSED_MIN_END = 42.80
TARGET_ROUTE_DIST_START_M = 2403.0
TARGET_ROUTE_DIST_END_M = 2493.0

SEQUENCE_CSV = Path(
    "outputs/ib3a_sequence_mapmatched_activity_v1_3b_qixing_via_corridor_repair_candidate"
) / ROUTE_FOLDER / f"{ACTIVITY_ID}_mapmatched.csv"
LABELED_CSV = Path(
    "outputs/ib3a2_on_route_activity_filter_v1_3b_qixing_via_corridor_repair_candidate"
) / ROUTE_FOLDER / f"{ROUTE_FOLDER}_{ACTIVITY_ID}_mapmatched_activity_labeled.csv"
ROUTE_PROFILE_CSV = Path(
    "outputs/ib1_route_profile_v1_3b_qixing_via_corridor_repair_candidate"
) / CASE_ID / f"{CASE_ID}_route_profile.csv"

OUT_ROOT = Path("outputs/ib3a2_qixing_wrong_branch_evidence_v1_3b")
EVIDENCE_CSV = OUT_ROOT / "qixing_37_1_wrong_branch_target_segment_evidence.csv"
SUMMARY_JSON = OUT_ROOT / "qixing_37_1_wrong_branch_target_segment_summary.json"
REVIEW_HTML = OUT_ROOT / "qixing_37_1_wrong_branch_target_segment_review.html"


def require_file(path: Path, label: str) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    return path


def read_csv(path: Path, label: str) -> list[dict[str, str]]:
    require_file(path, label)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def to_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def to_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float | None:
    if lat1 == lat2 and lon1 == lon2:
        return None
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    y = math.sin(dlon) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def angular_diff(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return abs((a - b + 180.0) % 360.0 - 180.0)


def quantile(values: list[float], q: float) -> float | None:
    clean = sorted(v for v in values if v is not None and not math.isnan(v))
    if not clean:
        return None
    pos = (len(clean) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return float(clean[lo])
    return float(clean[lo] * (hi - pos) + clean[hi] * (pos - lo))


def median_or_none(values: list[float]) -> float | None:
    clean = [v for v in values if v is not None and not math.isnan(v)]
    if not clean:
        return None
    return float(median(clean))


def load_route() -> list[dict[str, Any]]:
    rows = read_csv(ROUTE_PROFILE_CSV, "route profile CSV")
    route = []
    for row in rows:
        dist = to_float(row.get("dist_m"))
        lat = to_float(row.get("lat"))
        lon = to_float(row.get("lon"))
        if dist is None or lat is None or lon is None:
            continue
        route.append({"dist_m": dist, "lat": lat, "lon": lon})
    route.sort(key=lambda r: r["dist_m"])
    return route


def route_bearing_at(route: list[dict[str, Any]], dist_m: float | None, window_m: float = 8.0) -> float | None:
    if dist_m is None or len(route) < 2:
        return None
    dists = [r["dist_m"] for r in route]
    left_dist = max(dists[0], dist_m - window_m)
    right_dist = min(dists[-1], dist_m + window_m)
    li = max(0, bisect.bisect_left(dists, left_dist))
    ri = min(len(route) - 1, bisect.bisect_right(dists, right_dist) - 1)
    if ri <= li:
        li = max(0, bisect.bisect_left(dists, dist_m) - 1)
        ri = min(len(route) - 1, li + 1)
    a = route[li]
    b = route[ri]
    return bearing_deg(a["lat"], a["lon"], b["lat"], b["lon"])


def select_target_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out = []
    for idx, row in enumerate(rows):
        elapsed_sec = to_float(row.get("elapsed_sec"))
        elapsed_min = elapsed_sec / 60.0 if elapsed_sec is not None else None
        route_dist = to_float(row.get("route_dist_m"))
        phase = row.get("candidate_phase", "")
        in_elapsed = elapsed_min is not None and TARGET_ELAPSED_MIN_START <= elapsed_min <= TARGET_ELAPSED_MIN_END
        in_route_dist = route_dist is not None and TARGET_ROUTE_DIST_START_M <= route_dist <= TARGET_ROUTE_DIST_END_M
        if phase == "descent" and (in_elapsed or in_route_dist):
            out.append(
                {
                    **row,
                    "_row_n": idx,
                    "elapsed_min": elapsed_min,
                    "route_dist_m_num": route_dist,
                    "lat_num": to_float(row.get("lat")),
                    "lon_num": to_float(row.get("lon")),
                    "offset_m_num": to_float(row.get("offset_m")),
                    "speed_mps_num": to_float(row.get("implied_route_speed_mps")),
                    "route_dist_delta_m_num": to_float(row.get("route_dist_delta_m"), 0.0),
                    "reliable_route_dist_delta_m_num": to_float(row.get("reliable_route_dist_delta_m"), 0.0),
                    "usable_bool": to_bool(row.get("usable_on_route")),
                    "branch_ambiguity_bool": to_bool(row.get("sequence_branch_ambiguity_flag")),
                }
            )
    out.sort(key=lambda r: (r.get("elapsed_sec") is None, to_float(r.get("elapsed_sec"), 0.0) or 0.0))
    return out


def add_heading_evidence(rows: list[dict[str, Any]], route: list[dict[str, Any]]) -> None:
    for i, row in enumerate(rows):
        raw_heading = None
        if i + 1 < len(rows):
            nxt = rows[i + 1]
            if row["lat_num"] is not None and row["lon_num"] is not None and nxt["lat_num"] is not None and nxt["lon_num"] is not None:
                raw_heading = bearing_deg(row["lat_num"], row["lon_num"], nxt["lat_num"], nxt["lon_num"])
        elif i > 0:
            prev = rows[i - 1]
            if prev["lat_num"] is not None and prev["lon_num"] is not None and row["lat_num"] is not None and row["lon_num"] is not None:
                raw_heading = bearing_deg(prev["lat_num"], prev["lon_num"], row["lat_num"], row["lon_num"])
        route_heading = route_bearing_at(route, row["route_dist_m_num"])
        row["raw_gps_heading_deg"] = raw_heading
        row["route_axis_heading_deg"] = route_heading
        row["heading_diff_deg"] = angular_diff(raw_heading, route_heading)
        if i > 0:
            row["raw_heading_delta_deg"] = angular_diff(rows[i - 1].get("raw_gps_heading_deg"), raw_heading)
        else:
            row["raw_heading_delta_deg"] = None


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    offsets = [r["offset_m_num"] for r in rows if r["offset_m_num"] is not None]
    heading_diffs = [r["heading_diff_deg"] for r in rows if r["heading_diff_deg"] is not None]
    speeds = [r["speed_mps_num"] for r in rows if r["speed_mps_num"] is not None]
    route_delta = [r["route_dist_delta_m_num"] or 0.0 for r in rows]
    reliable_delta = [r["reliable_route_dist_delta_m_num"] or 0.0 for r in rows]
    state_counts: dict[str, int] = {}
    usable_counts = {"true": 0, "false": 0}
    ambiguity_counts = {"true": 0, "false": 0}
    for r in rows:
        state_counts[r.get("route_progress_state", "")] = state_counts.get(r.get("route_progress_state", ""), 0) + 1
        usable_counts["true" if r["usable_bool"] else "false"] += 1
        ambiguity_counts["true" if r["branch_ambiguity_bool"] else "false"] += 1

    reversal_count = sum(1 for d in route_delta if d < -2.0) + sum(1 for d in reliable_delta if d < -2.0)
    stall_count = sum(1 for d in route_delta if abs(d) < 0.5)
    jump_count = sum(1 for d in route_delta if abs(d) > 20.0)
    low_speed_rows = sum(1 for s in speeds if s < 0.3)
    stop_like_rows = sum(1 for s in speeds if s < 0.2)
    heading_reversal_rows = sum(1 for r in rows if (r.get("raw_heading_delta_deg") or 0.0) >= 150.0)

    heading_median = median_or_none(heading_diffs)
    heading_p90 = quantile(heading_diffs, 0.90)
    offset_median = median_or_none(offsets)
    offset_p90 = quantile(offsets, 0.90)
    max_offset = max(offsets) if offsets else None
    speed_median = median_or_none(speeds)
    speed_p25 = quantile(speeds, 0.25)
    speed_p75 = quantile(speeds, 0.75)

    offset_low = (offset_p90 or 999.0) < 5.0
    heading_low = (heading_p90 or 999.0) < 45.0
    heading_high = (heading_median or 0.0) > 75.0 or (heading_p90 or 0.0) > 120.0
    progression_abnormal = reversal_count > 0 or jump_count > 0
    evidence_insufficient = not rows or heading_median is None

    if evidence_insufficient:
        status = "NEEDS_MANUAL_REVIEW"
    elif offset_low and heading_low and not progression_abnormal:
        status = "NO_EVIDENCE_OF_WRONG_BRANCH"
    elif offset_low and (heading_high or progression_abnormal):
        status = "POSSIBLE_WRONG_BRANCH_REVIEW"
    elif (max_offset or 0.0) >= 10.0 and heading_high and progression_abnormal:
        status = "LIKELY_WRONG_BRANCH"
    else:
        status = "NEEDS_MANUAL_REVIEW"

    return {
        "wrong_branch_evidence_status": status,
        "rows_n": len(rows),
        "elapsed_min_start": min((r["elapsed_min"] for r in rows if r["elapsed_min"] is not None), default=None),
        "elapsed_min_end": max((r["elapsed_min"] for r in rows if r["elapsed_min"] is not None), default=None),
        "route_dist_m_start": min((r["route_dist_m_num"] for r in rows if r["route_dist_m_num"] is not None), default=None),
        "route_dist_m_end": max((r["route_dist_m_num"] for r in rows if r["route_dist_m_num"] is not None), default=None),
        "heading_diff_median": heading_median,
        "heading_diff_p90": heading_p90,
        "route_dist_reversal_count": reversal_count,
        "route_dist_stall_count": stall_count,
        "route_dist_jump_count": jump_count,
        "speed_median": speed_median,
        "speed_p25": speed_p25,
        "speed_p75": speed_p75,
        "low_speed_rows": low_speed_rows,
        "stop_like_rows": stop_like_rows,
        "heading_reversal_rows": heading_reversal_rows,
        "route_progress_state_counts": state_counts,
        "usable_on_route_counts": usable_counts,
        "sequence_branch_ambiguity_flag_counts": ambiguity_counts,
        "offset_median": offset_median,
        "offset_p90": offset_p90,
        "max_offset_m": max_offset,
        "supports_changing_ib3a2_threshold": False,
        "supports_review_only_wrong_branch_flag": status in {"POSSIBLE_WRONG_BRANCH_REVIEW", "NEEDS_MANUAL_REVIEW"},
        "recommended_next_action": (
            "Keep IB3A2 threshold unchanged; add review-only wrong_branch flag only if manual review still suspects branch mismatch."
            if status == "NO_EVIDENCE_OF_WRONG_BRANCH"
            else "Use review-only wrong_branch flag; do not change formal IB3A2 threshold from this evidence alone."
        ),
        "inputs": {
            "sequence_csv": str(SEQUENCE_CSV),
            "labeled_csv": str(LABELED_CSV),
            "route_profile_csv": str(ROUTE_PROFILE_CSV),
        },
        "outputs": {
            "evidence_csv": str(EVIDENCE_CSV),
            "summary_json": str(SUMMARY_JSON),
            "review_html": str(REVIEW_HTML),
        },
        "runtime_llm_allowed": False,
    }


def make_html(rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    cols = [
        "elapsed_min",
        "route_dist_m_num",
        "offset_m_num",
        "raw_gps_heading_deg",
        "route_axis_heading_deg",
        "heading_diff_deg",
        "route_dist_delta_m_num",
        "reliable_route_dist_delta_m_num",
        "speed_mps_num",
        "route_progress_state",
        "usable_on_route",
        "sequence_branch_ambiguity_flag",
    ]
    head = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(r.get(c, '')))}</td>" for c in cols) + "</tr>"
        for r in rows
    )
    summary_rows = "".join(
        f"<tr><td>{html.escape(str(k))}</td><td>{html.escape(str(v))}</td></tr>"
        for k, v in summary.items()
        if k not in {"inputs", "outputs"}
    )
    REVIEW_HTML.write_text(
        f"""<!doctype html><html><head><meta charset="utf-8"><title>Wrong branch evidence 37_1</title>
<style>body{{font-family:Arial,sans-serif;margin:22px}}table{{border-collapse:collapse;font-size:12px}}td,th{{border:1px solid #cbd5e1;padding:4px 6px}}th{{background:#e2e8f0}}</style>
</head><body><h1>37_1 wrong-branch evidence audit</h1>
<h2>Summary</h2><table>{summary_rows}</table>
<h2>Target segment rows</h2><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>
</body></html>""",
        encoding="utf-8",
    )


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    _sequence = require_file(SEQUENCE_CSV, "sequence CSV")
    labeled = read_csv(LABELED_CSV, "IB3A2 labeled CSV")
    route = load_route()
    rows = select_target_rows(labeled)
    add_heading_evidence(rows, route)
    summary = summarize(rows)
    write_csv(EVIDENCE_CSV, rows)
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    make_html(rows, summary)

    print(f"WRONG_BRANCH_EVIDENCE_STATUS={summary['wrong_branch_evidence_status']}")
    print(f"heading_diff_median={summary['heading_diff_median']}")
    print(f"heading_diff_p90={summary['heading_diff_p90']}")
    print(f"route_dist_reversal_count={summary['route_dist_reversal_count']}")
    print(f"route_dist_stall_count={summary['route_dist_stall_count']}")
    print(f"speed_median={summary['speed_median']}")
    print(f"low_speed_rows={summary['low_speed_rows']}")
    print(f"offset_median={summary['offset_median']}")
    print(f"offset_p90={summary['offset_p90']}")
    print(f"max_offset_m={summary['max_offset_m']}")
    print(f"supports_changing_ib3a2_threshold={summary['supports_changing_ib3a2_threshold']}")
    print(f"supports_review_only_wrong_branch_flag={summary['supports_review_only_wrong_branch_flag']}")
    print(f"evidence_csv={EVIDENCE_CSV}")
    print(f"summary_json={SUMMARY_JSON}")
    print(f"review_html={REVIEW_HTML}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
