"""Review-only threshold sensitivity audit for qixing repaired IB3A2 labels."""

from __future__ import annotations

import csv
import html
import json
from pathlib import Path
from statistics import median
from typing import Any


CASE_ID = "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b"
ROUTE_FOLDER = "qixing_lengshuikeng"
ACTIVITY_IDS = ["37_1", "33_1", "15_1"]

SEQUENCE_ROOT = Path("outputs/ib3a_sequence_mapmatched_activity_v1_3b_qixing_via_corridor_repair_candidate")
IB3A2_ROOT = Path("outputs/ib3a2_on_route_activity_filter_v1_3b_qixing_via_corridor_repair_candidate")
ROUTE_PROFILE_ROOT = Path("outputs/ib1_route_profile_v1_3b_qixing_via_corridor_repair_candidate")
OUT_ROOT = Path("outputs/ib3a2_qixing_repaired_threshold_sensitivity_v1_3b")

SUMMARY_CSV = OUT_ROOT / "ib3a2_qixing_threshold_sensitivity_summary.csv"
LOCAL_37_CSV = OUT_ROOT / "ib3a2_qixing_threshold_sensitivity_37_1_local_segment.csv"
SUMMARY_JSON = OUT_ROOT / "ib3a2_qixing_threshold_sensitivity_summary.json"
HTML_OUT = OUT_ROOT / "ib3a2_qixing_threshold_sensitivity_review.html"

STRICT_5M = 5.0
STRICT_3M = 3.0
LOCAL_CLUSTER_THRESHOLD_M = 5.0
LOCAL_CLUSTER_MIN_ROWS = 5
LOCAL_CLUSTER_MAX_GAP_SEC = 10.0


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
    return str(value).lower() in {"true", "1", "yes", "y"}


def quality_flag(on_route_ratio: float) -> str:
    if on_route_ratio >= 0.6:
        return "PASS_REVIEW_READY"
    return "REVIEW_REQUIRED_LOW_ON_ROUTE_RATIO"


def enrich(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out = []
    for i, row in enumerate(rows):
        offset = to_float(row.get("offset_m"), 0.0) or 0.0
        state = row.get("route_progress_state", "")
        usable = to_bool(row.get("usable_on_route"))
        elapsed = to_float(row.get("elapsed_sec"))
        route_dist = to_float(row.get("route_dist_m"))
        strict_5 = offset > STRICT_5M
        strict_3 = offset > STRICT_3M
        out.append(
            {
                **row,
                "_row_n": i,
                "_offset_m": offset,
                "_elapsed_sec": elapsed,
                "_elapsed_min": elapsed / 60.0 if elapsed is not None else None,
                "_route_dist_m": route_dist,
                "_route_progress_state": state,
                "_usable_on_route": usable,
                "strict_5m_review_required": strict_5,
                "strict_3m_review_required": strict_3,
                "possible_false_on_route_review": usable and strict_5,
                "possible_overconfident_projection": state == "on_route_reliable" and strict_5,
            }
        )
    return out


def find_local_clusters(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [
        r
        for r in rows
        if r["_usable_on_route"]
        and r["_route_progress_state"] == "on_route_reliable"
        and r["_offset_m"] > LOCAL_CLUSTER_THRESHOLD_M
    ]
    candidates.sort(key=lambda r: (r["_elapsed_sec"] is None, r["_elapsed_sec"] or 0.0))
    clusters: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    prev = None
    for row in candidates:
        elapsed = row["_elapsed_sec"]
        if prev is None or elapsed is None or elapsed - prev <= LOCAL_CLUSTER_MAX_GAP_SEC:
            current.append(row)
        else:
            if len(current) >= LOCAL_CLUSTER_MIN_ROWS:
                clusters.append(current)
            current = [row]
        prev = elapsed
    if len(current) >= LOCAL_CLUSTER_MIN_ROWS:
        clusters.append(current)

    out = []
    for idx, cluster in enumerate(clusters, start=1):
        offsets = [r["_offset_m"] for r in cluster]
        elapsed = [r["_elapsed_min"] for r in cluster if r["_elapsed_min"] is not None]
        route_dist = [r["_route_dist_m"] for r in cluster if r["_route_dist_m"] is not None]
        out.append(
            {
                "cluster_id": idx,
                "rows_n": len(cluster),
                "start_elapsed_min": min(elapsed) if elapsed else None,
                "end_elapsed_min": max(elapsed) if elapsed else None,
                "start_route_dist_m": min(route_dist) if route_dist else None,
                "end_route_dist_m": max(route_dist) if route_dist else None,
                "offset_median": median(offsets) if offsets else None,
                "offset_max": max(offsets) if offsets else None,
            }
        )
    return out


def summarize_activity(activity_id: str, rows: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    total = len(rows)
    current_on_route = sum(1 for r in rows if r["_route_progress_state"] == "on_route_reliable")
    strict_5_review = sum(1 for r in rows if r["strict_5m_review_required"])
    strict_3_review = sum(1 for r in rows if r["strict_3m_review_required"])
    possible_false = sum(1 for r in rows if r["possible_false_on_route_review"])
    possible_overconf = sum(1 for r in rows if r["possible_overconfident_projection"])
    strict_5_on_route = sum(
        1 for r in rows if r["_route_progress_state"] == "on_route_reliable" and not r["strict_5m_review_required"]
    )
    strict_3_on_route = sum(
        1 for r in rows if r["_route_progress_state"] == "on_route_reliable" and not r["strict_3m_review_required"]
    )
    clusters = find_local_clusters(rows)
    current_ratio = current_on_route / total if total else 0.0
    strict_5_ratio = strict_5_on_route / total if total else 0.0
    strict_3_ratio = strict_3_on_route / total if total else 0.0
    return (
        {
            "activity_id": activity_id,
            "current_on_route_rows": current_on_route,
            "current_on_route_ratio": current_ratio,
            "strict_5m_review_rows": strict_5_review,
            "strict_3m_review_rows": strict_3_review,
            "possible_false_on_route_rows": possible_false,
            "possible_overconfident_projection_rows": possible_overconf,
            "local_cluster_review_segments_n": len(clusters),
            "on_route_ratio_if_strict_5m_excluded": strict_5_ratio,
            "on_route_ratio_if_strict_3m_excluded": strict_3_ratio,
            "quality_flag_current": quality_flag(current_ratio),
            "quality_flag_strict_5m": quality_flag(strict_5_ratio),
            "quality_flag_strict_3m": quality_flag(strict_3_ratio),
        },
        clusters,
    )


def extract_37_local(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    local = []
    for row in rows:
        elapsed = row["_elapsed_min"]
        route_dist = row["_route_dist_m"]
        in_elapsed = elapsed is not None and 39.32 <= elapsed <= 42.80
        in_route = route_dist is not None and 2403 <= route_dist <= 2493
        if in_elapsed or in_route:
            local.append(
                {
                    "activity_id": "37_1",
                    "row_n": row["_row_n"],
                    "elapsed_min": elapsed,
                    "route_dist_m": route_dist,
                    "candidate_phase": row.get("candidate_phase", ""),
                    "route_progress_state": row.get("route_progress_state", ""),
                    "usable_on_route": row["_usable_on_route"],
                    "offset_m": row["_offset_m"],
                    "strict_5m_review_required": row["strict_5m_review_required"],
                    "strict_3m_review_required": row["strict_3m_review_required"],
                    "possible_false_on_route_review": row["possible_false_on_route_review"],
                    "possible_overconfident_projection": row["possible_overconfident_projection"],
                }
            )
    return local


def decide(summary_rows: list[dict[str, Any]], local37: list[dict[str, Any]]) -> tuple[str, str]:
    local_flagged_5 = sum(1 for r in local37 if r["strict_5m_review_required"])
    local_flagged_3 = sum(1 for r in local37 if r["strict_3m_review_required"])
    ratio_drops_5 = [
        r["current_on_route_ratio"] - r["on_route_ratio_if_strict_5m_excluded"] for r in summary_rows
    ]
    ratio_drops_3 = [
        r["current_on_route_ratio"] - r["on_route_ratio_if_strict_3m_excluded"] for r in summary_rows
    ]
    cluster_total = sum(int(r["local_cluster_review_segments_n"]) for r in summary_rows)
    max_drop_5 = max(ratio_drops_5) if ratio_drops_5 else 0.0
    max_drop_3 = max(ratio_drops_3) if ratio_drops_3 else 0.0
    many_affected = sum(1 for d in ratio_drops_5 if d > 0.05) >= 2

    if local_flagged_5 == 0 and local_flagged_3 == 0 and max_drop_5 < 0.02:
        return (
            "KEEP_CURRENT_THRESHOLD",
            "37_1 local visual-suspect segment is not flagged by stricter offset rules; current green segment appears low-offset.",
        )
    if cluster_total > 0 and not many_affected and max_drop_5 < 0.08:
        return (
            "ADD_REVIEW_ONLY_STRICT_FLAG",
            "Strict rules identify review clusters without broadly damaging on-route ratios; add review-only flag rather than changing formal threshold.",
        )
    if many_affected or max_drop_3 > 0.15:
        return (
            "CONSIDER_FORMAL_THRESHOLD_UPDATE",
            "Multiple activities show large on-route ratio changes under strict thresholds.",
        )
    return (
        "ADD_REVIEW_ONLY_STRICT_FLAG",
        "Strict thresholds produce some useful review signal, but evidence is not strong enough for formal threshold update.",
    )


def write_html(summary_rows: list[dict[str, Any]], local37: list[dict[str, Any]], status: str) -> None:
    def table(rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "<p>No rows.</p>"
        cols = list(rows[0].keys())
        head = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
        body = "".join(
            "<tr>" + "".join(f"<td>{html.escape(str(r.get(c, '')))}</td>" for c in cols) + "</tr>"
            for r in rows
        )
        return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"

    HTML_OUT.write_text(
        f"""<!doctype html><html><head><meta charset="utf-8"><title>IB3A2 threshold sensitivity</title>
<style>body{{font-family:Arial,sans-serif;margin:22px}}table{{border-collapse:collapse;font-size:13px}}td,th{{border:1px solid #cbd5e1;padding:5px 7px}}th{{background:#e2e8f0}}</style>
</head><body><h1>IB3A2 qixing repaired threshold sensitivity</h1>
<p>Final recommendation: <b>{html.escape(status)}</b></p>
<h2>Activity summary</h2>{table(summary_rows)}
<h2>37_1 local segment 39.32-42.80 min / 2403-2493 m</h2>{table(local37)}
</body></html>""",
        encoding="utf-8",
    )


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    _route_exists = require_file(ROUTE_PROFILE_ROOT / CASE_ID / f"{CASE_ID}_route_profile.csv", "route profile CSV")
    summary_rows = []
    cluster_rows = []
    local37: list[dict[str, Any]] = []
    for activity_id in ACTIVITY_IDS:
        _sequence = require_file(SEQUENCE_ROOT / ROUTE_FOLDER / f"{activity_id}_mapmatched.csv", "sequence CSV")
        labeled_csv = IB3A2_ROOT / ROUTE_FOLDER / f"{ROUTE_FOLDER}_{activity_id}_mapmatched_activity_labeled.csv"
        rows = enrich(read_csv(labeled_csv, "IB3A2 labeled CSV"))
        summary, clusters = summarize_activity(activity_id, rows)
        summary_rows.append(summary)
        for c in clusters:
            cluster_rows.append({"activity_id": activity_id, **c})
        if activity_id == "37_1":
            local37 = extract_37_local(rows)

    status, reason = decide(summary_rows, local37)
    write_csv(SUMMARY_CSV, summary_rows)
    write_csv(LOCAL_37_CSV, local37)
    summary_json = {
        "ib3a2_threshold_review_status": status,
        "reason": reason,
        "activities_n": len(ACTIVITY_IDS),
        "activity_summary": summary_rows,
        "local_cluster_review_segments": cluster_rows,
        "37_1_local_segment_rows_n": len(local37),
        "37_1_local_segment_strict_5m_review_rows": sum(1 for r in local37 if r["strict_5m_review_required"]),
        "37_1_local_segment_strict_3m_review_rows": sum(1 for r in local37 if r["strict_3m_review_required"]),
        "recommend_formal_ib3a2_threshold_update": status == "CONSIDER_FORMAL_THRESHOLD_UPDATE",
        "recommend_review_only_strict_flag": status == "ADD_REVIEW_ONLY_STRICT_FLAG",
        "outputs": {
            "summary_csv": str(SUMMARY_CSV),
            "local_37_csv": str(LOCAL_37_CSV),
            "summary_json": str(SUMMARY_JSON),
            "html": str(HTML_OUT),
        },
        "runtime_llm_allowed": False,
    }
    SUMMARY_JSON.write_text(json.dumps(summary_json, ensure_ascii=False, indent=2), encoding="utf-8")
    write_html(summary_rows, local37, status)

    print(f"IB3A2_THRESHOLD_REVIEW_STATUS={status}")
    print(f"reason={reason}")
    for row in summary_rows:
        print(
            f"{row['activity_id']}: current={row['current_on_route_ratio']:.4f} "
            f"strict5={row['on_route_ratio_if_strict_5m_excluded']:.4f} "
            f"strict3={row['on_route_ratio_if_strict_3m_excluded']:.4f} "
            f"clusters={row['local_cluster_review_segments_n']}"
        )
    print(
        "37_1_local_segment_flags="
        f"strict5:{summary_json['37_1_local_segment_strict_5m_review_rows']} "
        f"strict3:{summary_json['37_1_local_segment_strict_3m_review_rows']} "
        f"rows:{len(local37)}"
    )
    print(f"summary_csv={SUMMARY_CSV}")
    print(f"local_37_csv={LOCAL_37_CSV}")
    print(f"summary_json={SUMMARY_JSON}")
    print(f"html={HTML_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
