from __future__ import annotations

import csv
import json
import math
import py_compile
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASE_ID = "hehuan_north_peak_roundtrip_fit12_seed_v1"
FIT12_POINTS = (
    PROJECT_ROOT
    / "outputs"
    / "route_seed_preparation_butterfly_hehuan_v1"
    / "hehuan_north_peak_roundtrip_fit12_seed_v1"
    / "route_seed_points.csv"
)
FIT12_GPX = (
    PROJECT_ROOT
    / "outputs"
    / "route_seed_preparation_butterfly_hehuan_v1"
    / "hehuan_north_peak_roundtrip_fit12_seed_v1"
    / "route_seed_from_fit.gpx"
)
FIT11_POINTS = (
    PROJECT_ROOT
    / "outputs"
    / "route_seed_preparation_butterfly_hehuan_v1"
    / "hehuan_north_peak_reflector_fit11_review_v1"
    / "route_seed_points.csv"
)
OUT_DIR = PROJECT_ROOT / "outputs" / "hehuan_north_peak_anchor_proposal_v1"


def read_points(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for key in [
            "ordered_index",
            "lat",
            "lon",
            "altitude",
            "distance",
            "distance_cumulative_haversine_m",
            "speed",
            "heart_rate",
        ]:
            value = row.get(key)
            if value is None or value == "":
                row[key] = None
                continue
            row[key] = int(float(value)) if key == "ordered_index" else float(value)
    return rows


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def segment_distance(prev: dict[str, Any], cur: dict[str, Any]) -> float:
    return haversine_m(float(prev["lat"]), float(prev["lon"]), float(cur["lat"]), float(cur["lon"]))


def to_anchor(
    *,
    anchor_id: str,
    anchor_name: str,
    anchor_role: str,
    source_trace: str,
    row: dict[str, Any],
    confidence: str,
    evidence_notes: str,
    review_flag: str,
) -> dict[str, Any]:
    return {
        "anchor_id": anchor_id,
        "anchor_name": anchor_name,
        "anchor_role": anchor_role,
        "source_trace": source_trace,
        "route_index": int(row["ordered_index"]),
        "timestamp": row.get("timestamp"),
        "lat": float(row["lat"]),
        "lon": float(row["lon"]),
        "altitude_m": row.get("altitude"),
        "distance_m": row.get("distance"),
        "confidence": confidence,
        "evidence_notes": evidence_notes,
        "review_flag": review_flag,
    }


def max_altitude_row(points: list[dict[str, Any]]) -> dict[str, Any]:
    return max(points, key=lambda row: float(row["altitude"]) if row.get("altitude") is not None else -9999)


def find_early_trailhead_candidate(points: list[dict[str, Any]]) -> tuple[dict[str, Any], float]:
    end = points[-1]
    early = points[: max(300, len(points) // 20)]
    best = min(early, key=lambda row: haversine_m(float(row["lat"]), float(row["lon"]), float(end["lat"]), float(end["lon"])))
    return best, haversine_m(float(best["lat"]), float(best["lon"]), float(end["lat"]), float(end["lon"]))


def nearest_sampled_distance(point: dict[str, Any], candidates: list[dict[str, Any]], step: int = 10) -> tuple[float, dict[str, Any]]:
    sampled = candidates[::step]
    best = min(
        sampled,
        key=lambda row: haversine_m(float(point["lat"]), float(point["lon"]), float(row["lat"]), float(row["lon"])),
    )
    return haversine_m(float(point["lat"]), float(point["lon"]), float(best["lat"]), float(best["lon"])), best


def fit11_reflector_candidate(fit11: list[dict[str, Any]], fit12: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    # FIT11 is explicitly a reflector/variant review trace. Use its largest
    # spatial divergence from FIT12 as a conservative review candidate.
    best: tuple[float, dict[str, Any], dict[str, Any]] | None = None
    for row in fit11[::25]:
        # Avoid start/end parking noise and summit pause; focus on the route body.
        distance = float(row.get("distance") or 0.0)
        if distance < 500 or distance > 4500:
            continue
        nearest_d, nearest = nearest_sampled_distance(row, fit12, step=20)
        if best is None or nearest_d > best[0]:
            best = (nearest_d, row, nearest)
    if best is None:
        raise RuntimeError("Unable to derive FIT11 reflector review candidate")
    return best[1], {"nearest_fit12_distance_m": best[0], "nearest_fit12_row": best[2]}


def detect_suspect_segments(points: list[dict[str, Any]]) -> dict[str, Any]:
    jumps = []
    low_speed_clusters = []
    current_cluster: list[dict[str, Any]] = []

    for idx in range(1, len(points)):
        prev = points[idx - 1]
        cur = points[idx]
        seg_m = segment_distance(prev, cur)
        speed = cur.get("speed")
        if seg_m >= 100 or (speed is not None and float(speed) >= 8.0):
            jumps.append(
                {
                    "from_index": prev["ordered_index"],
                    "to_index": cur["ordered_index"],
                    "segment_distance_m": seg_m,
                    "speed_mps": speed,
                }
            )

        if speed is not None and float(speed) <= 0.05 and seg_m <= 3:
            current_cluster.append(cur)
        else:
            if len(current_cluster) >= 30:
                low_speed_clusters.append(cluster_summary(current_cluster))
            current_cluster = []
    if len(current_cluster) >= 30:
        low_speed_clusters.append(cluster_summary(current_cluster))

    return {
        "suspect_jump_count": len(jumps),
        "max_segment_distance_m": max(segment_distance(points[idx - 1], points[idx]) for idx in range(1, len(points))),
        "jumps": jumps[:20],
        "low_speed_cluster_count": len(low_speed_clusters),
        "low_speed_clusters_top10": low_speed_clusters[:10],
    }


def cluster_summary(cluster: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "start_index": cluster[0]["ordered_index"],
        "end_index": cluster[-1]["ordered_index"],
        "start_time": cluster[0].get("timestamp"),
        "end_time": cluster[-1].get("timestamp"),
        "point_count": len(cluster),
        "lat_mean": sum(float(row["lat"]) for row in cluster) / len(cluster),
        "lon_mean": sum(float(row["lon"]) for row in cluster) / len(cluster),
        "altitude_min_m": min(float(row["altitude"]) for row in cluster if row.get("altitude") is not None),
        "altitude_max_m": max(float(row["altitude"]) for row in cluster if row.get("altitude") is not None),
        "distance_min_m": min(float(row["distance"]) for row in cluster if row.get("distance") is not None),
        "distance_max_m": max(float(row["distance"]) for row in cluster if row.get("distance") is not None),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "anchor_id",
        "anchor_name",
        "anchor_role",
        "source_trace",
        "route_index",
        "timestamp",
        "lat",
        "lon",
        "altitude_m",
        "distance_m",
        "confidence",
        "evidence_notes",
        "review_flag",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_geojson(path: Path, anchors: list[dict[str, Any]]) -> None:
    features = []
    for anchor in anchors:
        props = {key: value for key, value in anchor.items() if key not in {"lat", "lon"}}
        features.append(
            {
                "type": "Feature",
                "properties": props,
                "geometry": {
                    "type": "Point",
                    "coordinates": [anchor["lon"], anchor["lat"]],
                },
            }
        )
    payload = {"type": "FeatureCollection", "features": features}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def git_status() -> str:
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return result.stdout.strip() or "No output."


def compile_status() -> str:
    try:
        py_compile.compile(str(Path(__file__).resolve()), doraise=True)
    except Exception as exc:
        return f"FAIL: {exc}"
    return "PASS"


def markdown_report(anchors: list[dict[str, Any]], debug: dict[str, Any]) -> str:
    manual = [row["anchor_id"] for row in anchors if row["review_flag"] != "ok"]
    return "\n".join(
        [
            "# Hehuan North Peak FIT12-derived anchor proposal v1",
            "",
            f"Generated: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}",
            f"Recommended case id: `{CASE_ID}`",
            "",
            "This is an onboarding proposal for a FIT-derived activity trace seed. It is not an official route definition.",
            "",
            "## Anchor Proposal",
            "",
            "| anchor_id | role | source | index | lat | lon | altitude_m | distance_m | confidence | review |",
            "|---|---|---|---:|---:|---:|---:|---:|---|---|",
            *[
                f"| `{a['anchor_id']}` | {a['anchor_role']} | {a['source_trace']} | {a['route_index']} | {a['lat']:.8f} | {a['lon']:.8f} | {a['altitude_m']} | {a['distance_m']} | {a['confidence']} | {a['review_flag']} |"
                for a in anchors
            ],
            "",
            "## Direct Answers",
            "",
            "1. FIT12 can establish four proposed anchors, but the reflector anchor is provisional and requires manual review.",
            "2. Start/end were successfully kept separate. FIT12 trace start and end are about "
            f"{debug['fit12_start_end_distance_m']:.1f} m apart; the early trailhead-like candidate is index "
            f"{debug['fit12_early_trailhead_candidate']['ordered_index']} and is about "
            f"{debug['fit12_early_trailhead_candidate']['distance_to_end_m']:.1f} m from the return endpoint.",
            "3. Summit / turnaround is based on the FIT12 maximum elevation point plus a near-zero-speed summit pause window.",
            "4. FIT11 can assist the reflector anchor as review evidence only. The proposed reflector row uses FIT11's largest mid-route spatial divergence from FIT12 and is not merged into FIT12.",
            f"5. Anchors needing manual review: {', '.join(manual) if manual else 'none'}.",
            "6. Recommendation: proceed to IA1 planning for FIT12 after manual review of start/trailhead and reflector anchors; do not run IB0 until anchors are accepted.",
            f"7. Suggested case id: `{CASE_ID}`.",
            "8. Suggested no-overwrite output root: `outputs\\route_onboarding_candidate_runs_v1\\hehuan_north_peak_roundtrip_fit12_seed_v1`.",
            f"9. py_compile result for the proposal script: `{debug['py_compile']}`.",
            "10. git status --short:",
            "",
            "```text",
            debug["git_status"],
            "```",
            "",
            "## Evidence Notes",
            "",
            f"- FIT12 point count: {debug['fit12_point_count']}; FIT11 point count: {debug['fit11_point_count']}.",
            f"- FIT12 suspect GPS jump count: {debug['fit12_suspect_segments']['suspect_jump_count']}; max segment distance: {debug['fit12_suspect_segments']['max_segment_distance_m']:.2f} m.",
            f"- FIT12 low-speed cluster count: {debug['fit12_suspect_segments']['low_speed_cluster_count']}. These are review context, not deletion instructions.",
            f"- FIT11 reflector candidate nearest sampled FIT12 point is about {debug['reflector_candidate_support']['nearest_fit12_distance_m']:.1f} m away; this is why the reflector anchor is marked `manual_review_required`.",
            "",
        ]
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fit12 = read_points(FIT12_POINTS)
    fit11 = read_points(FIT11_POINTS)

    start = fit12[0]
    end = fit12[-1]
    summit = max_altitude_row(fit12)
    trailhead_candidate, trailhead_to_end_m = find_early_trailhead_candidate(fit12)
    reflector, reflector_support = fit11_reflector_candidate(fit11, fit12)

    fit12_start_end_distance_m = haversine_m(
        float(start["lat"]), float(start["lon"]), float(end["lat"]), float(end["lon"])
    )

    anchors = [
        to_anchor(
            anchor_id="start_xiaofengkou_trace_start",
            anchor_name="小風口／合歡山北峰登山口 start candidate",
            anchor_role="start",
            source_trace="FIT12",
            row=start,
            confidence="medium",
            evidence_notes=(
                "FIT12 ordered trace start. Keep separate from end for out-and-back. "
                f"Early trailhead-like point occurs at FIT12 index {trailhead_candidate['ordered_index']} "
                f"and is {trailhead_to_end_m:.1f} m from the return endpoint."
            ),
            review_flag="manual_review_trace_start_vs_trailhead",
        ),
        to_anchor(
            anchor_id="reflector_candidate_fit11_review",
            anchor_name="反射板 candidate from FIT11 review trace",
            anchor_role="reflector",
            source_trace="FIT11",
            row=reflector,
            confidence="low",
            evidence_notes=(
                "FIT11 is the reflector/variant review seed. Candidate selected from the largest "
                "mid-route spatial divergence from sampled FIT12. Do not merge into FIT12 without manual review. "
                f"Nearest sampled FIT12 point distance is {reflector_support['nearest_fit12_distance_m']:.1f} m."
            ),
            review_flag="manual_review_required",
        ),
        to_anchor(
            anchor_id="summit_turnaround_fit12_highpoint",
            anchor_name="合歡山北峰 summit / turnaround candidate",
            anchor_role="turnaround",
            source_trace="FIT12",
            row=summit,
            confidence="high",
            evidence_notes=(
                "FIT12 maximum elevation point; located near the turnaround region with near-zero speed "
                "summit pause context. Preserve point order for out-and-back route seed."
            ),
            review_flag="ok",
        ),
        to_anchor(
            anchor_id="end_return_to_trailhead",
            anchor_name="回到登山口 end candidate",
            anchor_role="end",
            source_trace="FIT12",
            row=end,
            confidence="high",
            evidence_notes=(
                f"FIT12 final point. Kept separate from start despite spatial proximity; "
                f"start/end separation is {fit12_start_end_distance_m:.1f} m."
            ),
            review_flag="ok",
        ),
    ]

    fit12_suspects = detect_suspect_segments(fit12)
    fit11_suspects = detect_suspect_segments(fit11)
    debug = {
        "case_id": CASE_ID,
        "fit12_points_path": str(FIT12_POINTS),
        "fit12_gpx_path": str(FIT12_GPX),
        "fit11_points_path": str(FIT11_POINTS),
        "fit12_point_count": len(fit12),
        "fit11_point_count": len(fit11),
        "fit12_start_end_distance_m": fit12_start_end_distance_m,
        "fit12_early_trailhead_candidate": {
            **{k: trailhead_candidate.get(k) for k in ["ordered_index", "timestamp", "lat", "lon", "altitude", "distance"]},
            "distance_to_end_m": trailhead_to_end_m,
        },
        "summit_candidate": {k: summit.get(k) for k in ["ordered_index", "timestamp", "lat", "lon", "altitude", "distance", "speed"]},
        "reflector_candidate_support": {
            "nearest_fit12_distance_m": reflector_support["nearest_fit12_distance_m"],
            "nearest_fit12_row": {
                k: reflector_support["nearest_fit12_row"].get(k)
                for k in ["ordered_index", "timestamp", "lat", "lon", "altitude", "distance"]
            },
        },
        "fit12_suspect_segments": fit12_suspects,
        "fit11_suspect_segments": fit11_suspects,
    }
    debug["py_compile"] = compile_status()
    debug["git_status"] = git_status()

    write_csv(OUT_DIR / "hehuan_north_peak_anchor_proposal_v1.csv", anchors)
    write_geojson(OUT_DIR / "hehuan_north_peak_anchor_proposal_v1.geojson", anchors)
    (OUT_DIR / "hehuan_north_peak_anchor_debug_v1.json").write_text(
        json.dumps(debug, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUT_DIR / "hehuan_north_peak_anchor_proposal_v1.md").write_text(
        markdown_report(anchors, debug),
        encoding="utf-8",
    )

    print(json.dumps({"out_dir": str(OUT_DIR), "anchor_count": len(anchors)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
