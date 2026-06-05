"""Diagnose possible false on-route segment in qixing 37_1 descent.

This diagnostic is read-only. It inspects existing IB3A sequence, IB3A2 labels,
IB3F features, route profile, and route risk outputs to find a candidate segment
where descent activity points may be visually off-branch while still labeled as
usable/on-route.
"""

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
SUMMIT_DIST_M = 1919.0

SEQUENCE_CSV = Path(
    "outputs/ib3a_sequence_mapmatched_activity_v1_3b_qixing_via_corridor_repair_candidate"
) / ROUTE_FOLDER / f"{ACTIVITY_ID}_mapmatched.csv"
LABELED_CSV = Path(
    "outputs/ib3a2_on_route_activity_filter_v1_3b_qixing_via_corridor_repair_candidate"
) / ROUTE_FOLDER / f"{ROUTE_FOLDER}_{ACTIVITY_ID}_mapmatched_activity_labeled.csv"
FEATURE_CSV = Path(
    "outputs/ib3f_activity_route_features_v1_3b_qixing_repaired_review"
) / ROUTE_FOLDER / f"{ROUTE_FOLDER}_{ACTIVITY_ID}_activity_features.csv"
ROUTE_PROFILE_CSV = Path(
    "outputs/ib1_route_profile_v1_3b_qixing_via_corridor_repair_candidate"
) / CASE_ID / f"{CASE_ID}_route_profile.csv"
ROUTE_RISK_CSV = Path(
    "outputs/ib2_v2_route_risk_v1_3b_contract_qa"
) / CASE_ID / f"{CASE_ID}_route_risk_v2.csv"

OUT_ROOT = Path(
    "outputs/ib3f_activity_route_features_v1_3b_qixing_repaired_review/_diagnostics_37_1_wrong_branch"
)
SUSPICIOUS_ROWS_CSV = OUT_ROOT / "qixing_37_1_descent_wrong_branch_candidate_rows.csv"
SEGMENT_SUMMARY_CSV = OUT_ROOT / "qixing_37_1_descent_wrong_branch_candidate_segment_summary.csv"
SUMMARY_JSON = OUT_ROOT / "qixing_37_1_descent_wrong_branch_candidate_summary.json"
DIAGNOSTIC_HTML = OUT_ROOT / "qixing_37_1_descent_wrong_branch_candidate_local_review.html"


def require_file(path: Path, label: str) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    return path


def read_csv(path: Path, label: str) -> list[dict[str, str]]:
    require_file(path, label)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: list[str] = []
        for row in rows:
            for key in row.keys():
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
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


def project_points(items: list[dict[str, Any]]) -> None:
    coords = [(to_float(p.get("lat")), to_float(p.get("lon"))) for p in items]
    coords = [(lat, lon) for lat, lon in coords if lat is not None and lon is not None]
    if not coords:
        return
    lat0 = sum(lat for lat, _ in coords) / len(coords)
    lon0 = sum(lon for _, lon in coords) / len(coords)
    cos_lat = math.cos(math.radians(lat0))
    for p in items:
        lat = to_float(p.get("lat"))
        lon = to_float(p.get("lon"))
        if lat is None or lon is None:
            p["x"] = None
            p["y"] = None
            continue
        p["x"] = (lon - lon0) * 111_320.0 * cos_lat
        p["y"] = -(lat - lat0) * 110_540.0


def interpolate_route_xy(route: list[dict[str, Any]], dist: float | None) -> tuple[float | None, float | None]:
    if dist is None or not route:
        return None, None
    if dist <= route[0]["dist_m"]:
        return route[0].get("x"), route[0].get("y")
    if dist >= route[-1]["dist_m"]:
        return route[-1].get("x"), route[-1].get("y")
    dists = [p["dist_m"] for p in route]
    idx = bisect.bisect_left(dists, dist)
    a = route[max(0, idx - 1)]
    b = route[min(len(route) - 1, idx)]
    span = b["dist_m"] - a["dist_m"]
    if span <= 0:
        return a.get("x"), a.get("y")
    t = (dist - a["dist_m"]) / span
    ax, ay, bx, by = a.get("x"), a.get("y"), b.get("x"), b.get("y")
    if ax is None or ay is None or bx is None or by is None:
        return None, None
    return ax + (bx - ax) * t, ay + (by - ay) * t


def load_route() -> list[dict[str, Any]]:
    route_rows = read_csv(ROUTE_PROFILE_CSV, "route profile CSV")
    route = []
    for row in route_rows:
        lat = to_float(row.get("lat"))
        lon = to_float(row.get("lon"))
        dist = to_float(row.get("dist_m"))
        if lat is None or lon is None or dist is None:
            continue
        route.append({"lat": lat, "lon": lon, "dist_m": dist})
    route.sort(key=lambda r: r["dist_m"])
    return route


def enrich_labeled_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    enriched = []
    for i, row in enumerate(rows):
        route_dist = to_float(row.get("route_dist_m"))
        offset = to_float(row.get("offset_m"), 0.0)
        elapsed = to_float(row.get("elapsed_sec"))
        state = row.get("route_progress_state", "")
        usable = to_bool(row.get("usable_on_route"))
        phase = row.get("candidate_phase", "")
        route_delta = to_float(row.get("route_dist_delta_m"), 0.0)
        reliable_delta = to_float(row.get("reliable_route_dist_delta_m"), 0.0)
        is_descent_after_summit = phase == "descent" and route_dist is not None and route_dist > SUMMIT_DIST_M
        enriched.append(
            {
                **row,
                "_row_n": i,
                "_route_dist_m": route_dist,
                "_offset_m": offset,
                "_elapsed_sec": elapsed,
                "_elapsed_min": elapsed / 60.0 if elapsed is not None else None,
                "_route_progress_state": state,
                "_usable_on_route": usable,
                "_candidate_phase": phase,
                "_route_dist_delta_m": route_delta,
                "_reliable_route_dist_delta_m": reliable_delta,
                "_descent_after_summit": is_descent_after_summit,
            }
        )
    return enriched


def mark_suspicious(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], float, float]:
    descent_offsets = [
        r["_offset_m"]
        for r in rows
        if r["_descent_after_summit"] and r["_offset_m"] is not None
    ]
    p90 = quantile(descent_offsets, 0.90) or 0.0
    p95 = quantile(descent_offsets, 0.95) or 0.0
    high_offset_threshold = max(12.0, p95)
    jump_threshold = 30.0
    suspicious = []
    for r in rows:
        if not r["_descent_after_summit"]:
            continue
        high_offset = (r["_offset_m"] or 0.0) >= high_offset_threshold
        jump_or_reversal = (
            (r["_route_dist_delta_m"] or 0.0) < -5.0
            or abs(r["_route_dist_delta_m"] or 0.0) >= jump_threshold
            or (r["_reliable_route_dist_delta_m"] or 0.0) < -5.0
        )
        still_green = r["_usable_on_route"] or r["_route_progress_state"] == "on_route_reliable"
        if still_green and (high_offset or jump_or_reversal):
            rr = dict(r)
            reasons = []
            if high_offset:
                reasons.append("high_offset_usable_on_route")
            if jump_or_reversal:
                reasons.append("route_dist_delta_suspicious")
            rr["suspicious_reason"] = "|".join(reasons)
            suspicious.append(rr)
    if not suspicious:
        top = sorted(
            [r for r in rows if r["_descent_after_summit"]],
            key=lambda r: r["_offset_m"] or -1,
            reverse=True,
        )[:50]
        suspicious = [dict(r, suspicious_reason="top_descent_offset_review") for r in top]
    return suspicious, p90, high_offset_threshold


def choose_segment(suspicious: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not suspicious:
        return []
    ordered = sorted(suspicious, key=lambda r: (r["_elapsed_sec"] is None, r["_elapsed_sec"] or 0.0))
    clusters: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    prev_elapsed = None
    for row in ordered:
        elapsed = row["_elapsed_sec"]
        if prev_elapsed is None or elapsed is None or elapsed - prev_elapsed <= 60.0:
            current.append(row)
        else:
            clusters.append(current)
            current = [row]
        prev_elapsed = elapsed
    if current:
        clusters.append(current)

    def score(cluster: list[dict[str, Any]]) -> tuple[int, float]:
        offsets = [r["_offset_m"] or 0.0 for r in cluster]
        return len(cluster), median_or_none(offsets) or 0.0

    return max(clusters, key=score)


def summarize_segment(segment: list[dict[str, Any]], feature_rows: list[dict[str, str]]) -> dict[str, Any]:
    offsets = [r["_offset_m"] for r in segment if r["_offset_m"] is not None]
    elapsed_vals = [r["_elapsed_min"] for r in segment if r["_elapsed_min"] is not None]
    route_vals = [r["_route_dist_m"] for r in segment if r["_route_dist_m"] is not None]
    usable_n = sum(1 for r in segment if r["_usable_on_route"])
    on_route_n = sum(1 for r in segment if r["_route_progress_state"] == "on_route_reliable")
    rows_n = len(segment)
    offset_median = median_or_none(offsets)
    offset_p90 = quantile(offsets, 0.90)
    max_offset = max(offsets) if offsets else None
    usable_ratio = usable_n / rows_n if rows_n else 0.0
    on_route_ratio = on_route_n / rows_n if rows_n else 0.0
    feature = feature_rows[0] if feature_rows else {}

    if rows_n >= 10 and usable_ratio >= 0.8 and on_route_ratio >= 0.8 and (
        (offset_median or 0.0) >= 12.0 or (offset_p90 or 0.0) >= 20.0
    ):
        status = "POSSIBLE_IB3A2_FALSE_ON_ROUTE_SEGMENT"
        may_overestimate = True
        next_action = "Review this local segment in the story map before changing IB3A2; consider adding an IB3F review flag for suspicious green descent cluster."
    elif (max_offset or 0.0) < 10.0 and (offset_p90 or 0.0) < 6.0:
        status = "VISUAL_ONLY_NO_EVIDENCE_OF_FALSE_ON_ROUTE"
        may_overestimate = False
        next_action = "No IB3A2 adjustment recommended from offset evidence; keep visual review note if needed."
    else:
        status = "NEEDS_MANUAL_LOCAL_REVIEW"
        may_overestimate = True if usable_ratio >= 0.8 and on_route_ratio >= 0.8 else False
        next_action = "Use the diagnostic HTML to inspect whether the candidate is an actual wrong branch or only a visual overlap artifact."

    return {
        "diagnostic_status": status,
        "suspicious_segment_detected": bool(rows_n),
        "segment_start_elapsed_min": min(elapsed_vals) if elapsed_vals else None,
        "segment_end_elapsed_min": max(elapsed_vals) if elapsed_vals else None,
        "segment_start_route_dist_m": min(route_vals) if route_vals else None,
        "segment_end_route_dist_m": max(route_vals) if route_vals else None,
        "rows_n": rows_n,
        "usable_on_route_rows_n": usable_n,
        "on_route_reliable_rows_n": on_route_n,
        "offset_median": offset_median,
        "offset_p90": offset_p90,
        "max_offset_m": max_offset,
        "ib3f_activity_quality_flag": feature.get("activity_quality_flag", ""),
        "ib3f_on_route_ratio": feature.get("on_route_ratio", ""),
        "recommended_interpretation": status,
        "whether_IB3F_on_route_ratio_may_be_overestimated": may_overestimate,
        "recommended_next_action": next_action,
    }


def make_local_html(rows: list[dict[str, Any]], route: list[dict[str, Any]], segment_summary: dict[str, Any]) -> None:
    if not rows:
        DIAGNOSTIC_HTML.write_text("<html><body>No suspicious rows.</body></html>", encoding="utf-8")
        return
    route_min = min((r["_route_dist_m"] or SUMMIT_DIST_M) for r in rows) - 120
    route_max = max((r["_route_dist_m"] or SUMMIT_DIST_M) for r in rows) + 120
    route_local = [r for r in route if route_min <= r["dist_m"] <= route_max]
    all_items: list[dict[str, Any]] = []
    all_items.extend(route_local)
    all_items.extend(rows)
    project_points(all_items)
    for r in rows:
        px, py = interpolate_route_xy(route, r["_route_dist_m"])
        r["projected_x"] = px
        r["projected_y"] = py
    xs = [p["x"] for p in all_items if p.get("x") is not None] + [p["projected_x"] for p in rows if p.get("projected_x") is not None]
    ys = [p["y"] for p in all_items if p.get("y") is not None] + [p["projected_y"] for p in rows if p.get("projected_y") is not None]
    min_x, max_x = min(xs, default=0), max(xs, default=1)
    min_y, max_y = min(ys, default=0), max(ys, default=1)
    pad = 40

    def poly(points: list[dict[str, Any]], x_key: str = "x", y_key: str = "y") -> str:
        return " ".join(
            f"{p[x_key]},{p[y_key]}" for p in points if p.get(x_key) is not None and p.get(y_key) is not None
        )

    circles = []
    for r in rows:
        color = "#16a34a" if r["_route_progress_state"] == "on_route_reliable" else "#f59e0b"
        title = "\n".join(
            [
                f"elapsed_min={r.get('_elapsed_min'):.2f}" if r.get("_elapsed_min") is not None else "",
                f"route_dist_m={r.get('_route_dist_m')}",
                f"offset_m={r.get('_offset_m')}",
                f"state={r.get('_route_progress_state')}",
                f"usable={r.get('_usable_on_route')}",
                f"phase={r.get('_candidate_phase')}",
            ]
        )
        circles.append(
            f'<circle cx="{r.get("x")}" cy="{r.get("y")}" r="3" fill="{color}" opacity="0.85">'
            f"<title>{html.escape(title)}</title></circle>"
        )
        if r.get("projected_x") is not None:
            circles.append(
                f'<circle cx="{r.get("projected_x")}" cy="{r.get("projected_y")}" r="2.2" fill="#0284c7" opacity="0.65" />'
            )

    body = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>37_1 descent wrong-branch diagnostic</title>
<style>body{{font-family:Arial,sans-serif;margin:20px;color:#172033}} svg{{width:100%;height:72vh;border:1px solid #cbd5e1;background:#fff}} table{{border-collapse:collapse}}td{{border:1px solid #cbd5e1;padding:4px 6px}}</style>
</head><body>
<h1>37_1 descent wrong-branch candidate diagnostic</h1>
<p>Status: <b>{html.escape(str(segment_summary['diagnostic_status']))}</b></p>
<p>Green points are raw GPS rows still labeled on_route_reliable. Blue points are projected route positions. Dark line is repaired route axis.</p>
<svg viewBox="{min_x-pad} {min_y-pad} {max_x-min_x+pad*2} {max_y-min_y+pad*2}">
<polyline points="{poly(route_local)}" fill="none" stroke="#0f172a" stroke-width="2" opacity="0.75"/>
<polyline points="{poly(rows)}" fill="none" stroke="#334155" stroke-width="1.4" opacity="0.55"/>
<polyline points="{poly(rows, 'projected_x', 'projected_y')}" fill="none" stroke="#0284c7" stroke-width="1.4" stroke-dasharray="6 4" opacity="0.75"/>
{''.join(circles)}
</svg>
<h2>Segment summary</h2>
<table>
{''.join(f'<tr><td>{html.escape(str(k))}</td><td>{html.escape(str(v))}</td></tr>' for k, v in segment_summary.items())}
</table>
</body></html>"""
    DIAGNOSTIC_HTML.write_text(body, encoding="utf-8")


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    _sequence_rows = read_csv(SEQUENCE_CSV, "IB3A sequence CSV")
    labeled_rows = enrich_labeled_rows(read_csv(LABELED_CSV, "IB3A2 labeled CSV"))
    feature_rows = read_csv(FEATURE_CSV, "IB3F feature CSV")
    route = load_route()
    project_points(route)
    _risk_rows = read_csv(ROUTE_RISK_CSV, "route risk CSV")

    suspicious, descent_offset_p90, high_offset_threshold = mark_suspicious(labeled_rows)
    top50 = sorted(
        [r for r in labeled_rows if r["_descent_after_summit"]],
        key=lambda r: r["_offset_m"] or -1,
        reverse=True,
    )[:50]
    top50 = [dict(r, suspicious_reason=r.get("suspicious_reason", "top_descent_offset_review")) for r in top50]
    segment = choose_segment(suspicious)
    segment_summary = summarize_segment(segment, feature_rows)
    segment_summary["descent_offset_p90_all_rows"] = descent_offset_p90
    segment_summary["high_offset_threshold_used"] = high_offset_threshold
    segment_summary["inputs"] = {
        "sequence_csv": str(SEQUENCE_CSV),
        "labeled_csv": str(LABELED_CSV),
        "feature_csv": str(FEATURE_CSV),
        "route_profile_csv": str(ROUTE_PROFILE_CSV),
        "route_risk_csv": str(ROUTE_RISK_CSV),
    }
    segment_summary["outputs"] = {
        "candidate_suspicious_rows_csv": str(SUSPICIOUS_ROWS_CSV),
        "segment_summary_csv": str(SEGMENT_SUMMARY_CSV),
        "summary_json": str(SUMMARY_JSON),
        "diagnostic_html": str(DIAGNOSTIC_HTML),
    }
    segment_summary["runtime_llm_allowed"] = False

    output_rows = suspicious if suspicious else top50
    write_csv(SUSPICIOUS_ROWS_CSV, output_rows)
    write_csv(SEGMENT_SUMMARY_CSV, [segment_summary])
    SUMMARY_JSON.write_text(json.dumps(segment_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    make_local_html(segment if segment else top50[:50], route, segment_summary)

    print(f"diagnostic_status={segment_summary['diagnostic_status']}")
    print(f"suspicious_segment_detected={segment_summary['suspicious_segment_detected']}")
    print(f"elapsed_min_range={segment_summary['segment_start_elapsed_min']}..{segment_summary['segment_end_elapsed_min']}")
    print(f"route_dist_m_range={segment_summary['segment_start_route_dist_m']}..{segment_summary['segment_end_route_dist_m']}")
    print(f"usable_on_route_rows_n={segment_summary['usable_on_route_rows_n']}")
    print(f"on_route_reliable_rows_n={segment_summary['on_route_reliable_rows_n']}")
    print(
        "offset_median_p90_max="
        f"{segment_summary['offset_median']},"
        f"{segment_summary['offset_p90']},"
        f"{segment_summary['max_offset_m']}"
    )
    print(
        "whether_IB3F_on_route_ratio_may_be_overestimated="
        f"{segment_summary['whether_IB3F_on_route_ratio_may_be_overestimated']}"
    )
    print(f"recommended_next_action={segment_summary['recommended_next_action']}")
    print(f"suspicious_rows_csv={SUSPICIOUS_ROWS_CSV}")
    print(f"segment_summary_csv={SEGMENT_SUMMARY_CSV}")
    print(f"summary_json={SUMMARY_JSON}")
    print(f"diagnostic_html={DIAGNOSTIC_HTML}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
