import argparse
import csv
import math
from pathlib import Path


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


def read_csv(fp):
    with Path(fp).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(fp, rows):
    fp = Path(fp)
    fp.parent.mkdir(parents=True, exist_ok=True)

    keys = []
    seen = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                keys.append(k)

    with fp.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def route_dist_from_row(row):
    for col in [
        "route_dist_refit_m_v1h",
        "route_dist_refit_m_v1g",
        "reliable_route_dist_m",
        "projected_route_dist_m",
        "nearest_route_dist_m",
    ]:
        v = fnum(row.get(col))
        if v is not None:
            return v, col
    return None, ""


def is_usable_anchor(row):
    usable_h = str(row.get("route_context_model_usable_v1h", "")).lower() == "true"
    usable_g = str(row.get("route_context_model_usable_v1g", "")).lower() == "true"
    status_h = str(row.get("route_context_model_status_v1h", ""))
    status_g = str(row.get("route_context_model_status_v1g", ""))

    return (
        usable_h
        or usable_g
        or status_h.startswith("matched_core_clean")
        or status_h.startswith("matched_core_refit")
        or status_h.startswith("matched_core_recovered")
        or status_g.startswith("matched_core_clean")
        or status_g.startswith("matched_core_refit")
        or status_g.startswith("matched_core_recovered")
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--activity-csv", required=True)
    ap.add_argument("--activity-id", required=True)
    ap.add_argument("--start-elapsed", type=float, required=True)
    ap.add_argument("--end-elapsed", type=float, required=True)
    ap.add_argument("--out-csv", required=True)

    # 這裡故意比前一版 max-step 8m 更激進，避免漂移造成假移動距離
    ap.add_argument("--max-step-m", type=float, default=2.0)
    ap.add_argument("--min-step-m", type=float, default=0.3)
    args = ap.parse_args()

    rows_all = read_csv(args.activity_csv)

    for r in rows_all:
        r["_elapsed"] = fnum(r.get("elapsed_sec"))
        r["_lat"] = fnum(r.get("lat"))
        r["_lon"] = fnum(r.get("lon"))
        rd, rd_col = route_dist_from_row(r)
        r["_route_dist"] = rd
        r["_route_dist_source"] = rd_col

    rows_all = [r for r in rows_all if r["_elapsed"] is not None]
    rows_all.sort(key=lambda r: r["_elapsed"])

    start = args.start_elapsed
    end = args.end_elapsed

    candidate_statuses = {
        "matched_low_confidence_offset",
        "no_activity_route_dist",
    }

    episode_rows = []
    for r in rows_all:
        if not (start <= r["_elapsed"] <= end):
            continue
        status = r.get("route_context_model_status_v1h") or r.get("route_context_model_status_v1g")
        if status in candidate_statuses:
            episode_rows.append(r)

    before_anchors = [
        r for r in rows_all
        if r["_elapsed"] < start and is_usable_anchor(r) and r["_route_dist"] is not None
    ]

    after_anchors = [
        r for r in rows_all
        if r["_elapsed"] > end and is_usable_anchor(r) and r["_route_dist"] is not None
    ]

    if not episode_rows:
        raise RuntimeError("No candidate episode rows found in range.")
    if not before_anchors:
        raise RuntimeError("No before anchor found.")
    if not after_anchors:
        raise RuntimeError("No after anchor found.")

    before_anchor = before_anchors[-1]
    after_anchor = after_anchors[0]

    start_route_dist = before_anchor["_route_dist"]
    end_route_dist = after_anchor["_route_dist"]
    route_span = end_route_dist - start_route_dist

    # aggressive capped-step cumulative progress
    cum = 0.0
    prev = None
    work = []

    for r in episode_rows:
        raw_step = 0.0
        used_step = 0.0
        note = "first_row"

        if prev is not None:
            if all(v is not None for v in [prev["_lat"], prev["_lon"], r["_lat"], r["_lon"]]):
                raw_step = haversine_m(prev["_lat"], prev["_lon"], r["_lat"], r["_lon"])
                if raw_step < args.min_step_m:
                    used_step = 0.0
                    note = "below_min_step_stationary"
                elif raw_step > args.max_step_m:
                    used_step = args.max_step_m
                    note = "aggressive_step_clipped"
                else:
                    used_step = raw_step
                    note = "step_used"

        cum += used_step
        r2 = dict(r)
        r2["_raw_step_m"] = raw_step
        r2["_used_step_m"] = used_step
        r2["_raw_cum_m"] = cum
        r2["_step_note"] = note
        work.append(r2)
        prev = r

    total_cum = work[-1]["_raw_cum_m"] if work else 0.0

    out_rows = []
    for r in work:
        elapsed = r["_elapsed"]

        time_ratio = (elapsed - start) / max(1e-9, end - start)
        time_ratio = max(0.0, min(1.0, time_ratio))

        if total_cum > 0:
            capped_step_ratio = r["_raw_cum_m"] / total_cum
        else:
            capped_step_ratio = time_ratio

        time_linear_target = start_route_dist + time_ratio * route_span
        capped_step_target = start_route_dist + capped_step_ratio * route_span

        projected = fnum(r.get("projected_route_dist_m"))

        out_rows.append({
            "activity_id": args.activity_id,
            "elapsed_sec": r.get("elapsed_sec", ""),
            "lat": r.get("lat", ""),
            "lon": r.get("lon", ""),
            "status_v1g": r.get("route_context_model_status_v1g", ""),
            "status_v1h": r.get("route_context_model_status_v1h", ""),
            "offset_m": r.get("offset_m", ""),

            "before_anchor_elapsed_sec": before_anchor.get("elapsed_sec", ""),
            "before_anchor_route_dist_m": start_route_dist,
            "before_anchor_route_dist_source": before_anchor["_route_dist_source"],
            "after_anchor_elapsed_sec": after_anchor.get("elapsed_sec", ""),
            "after_anchor_route_dist_m": end_route_dist,
            "after_anchor_route_dist_source": after_anchor["_route_dist_source"],
            "route_span_m": route_span,

            "raw_step_m": r["_raw_step_m"],
            "aggressive_used_step_m": r["_used_step_m"],
            "aggressive_cum_m": r["_raw_cum_m"],
            "aggressive_total_used_m": total_cum,
            "step_note": r["_step_note"],

            "time_ratio": time_ratio,
            "capped_step_ratio": capped_step_ratio,

            "time_linear_target_route_dist_m": time_linear_target,
            "aggressive_capped_step_target_route_dist_m": capped_step_target,

            "current_projected_route_dist_m": projected if projected is not None else "",
            "delta_time_linear_vs_projected_m": (time_linear_target - projected) if projected is not None else "",
            "delta_capped_step_vs_projected_m": (capped_step_target - projected) if projected is not None else "",

            "dryrun_recommendation": "aggressive_monotonic_mainline_corridor_refit_candidate",
        })

    write_csv(args.out_csv, out_rows)

    print("wrote:", args.out_csv)
    print("activity_id:", args.activity_id)
    print("episode rows:", len(out_rows))
    print("before anchor elapsed:", before_anchor.get("elapsed_sec"), "route_dist:", start_route_dist, "source:", before_anchor["_route_dist_source"])
    print("after anchor elapsed:", after_anchor.get("elapsed_sec"), "route_dist:", end_route_dist, "source:", after_anchor["_route_dist_source"])
    print("route span:", route_span)
    print("aggressive total used movement:", total_cum)


if __name__ == "__main__":
    main()
