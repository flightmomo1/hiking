import argparse
import csv
from pathlib import Path


CANDIDATE_STATUSES = {
    "matched_low_confidence_offset",
    "no_activity_route_dist",
}


def bool_like_true(x):
    return str(x).strip().lower() in {"true", "1", "yes", "y"}


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


def read_csv(fp):
    with Path(fp).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(fp, rows, fieldnames=None):
    fp = Path(fp)
    fp.parent.mkdir(parents=True, exist_ok=True)

    if fieldnames is None:
        keys = []
        seen = set()
        for r in rows:
            for k in r.keys():
                if k not in seen:
                    seen.add(k)
                    keys.append(k)
        fieldnames = keys

    with fp.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def in_elapsed_range(row, start, end):
    e = fnum(row.get("elapsed_sec"))
    return e is not None and start <= e <= end


def build_exclusion_lookup(exclusion_rows):
    lookup = {}
    for ex in exclusion_rows:
        if not bool_like_true(ex.get("exclude_from_v1h_recovery", "false")):
            continue

        aid = ex.get("activity_id", "")
        start = fnum(ex.get("elapsed_start_sec"))
        end = fnum(ex.get("elapsed_end_sec"))
        if not aid or start is None or end is None:
            continue

        lookup.setdefault(aid, []).append((start, end, ex))
    return lookup


def is_excluded(row, activity_id, exclusion_lookup):
    e = fnum(row.get("elapsed_sec"))
    if e is None:
        return False, None

    for start, end, ex in exclusion_lookup.get(activity_id, []):
        if start <= e <= end:
            return True, ex
    return False, None


def add_v1h_schema_passthrough(row):
    # 對所有 rows 補齊 V1H schema；預設沿用 V1G。
    row["route_context_model_status_v1h"] = row.get("route_context_model_status_v1g", "")
    row["route_context_model_usable_v1h"] = row.get("route_context_model_usable_v1g", "")
    row["route_context_model_reason_v1h"] = row.get("route_context_model_reason_v1g", "")

    row["route_dist_refit_m_v1h"] = row.get("route_dist_refit_m_v1g", "")
    row["route_dist_refit_method_v1h"] = row.get("route_dist_refit_method_v1g", "")

    row["v1h_recovery_applied"] = "False"
    row["v1h_recovery_rule"] = ""
    row["v1h_recovery_reviewed_unit_type"] = ""
    row["v1h_recovery_cluster_ids"] = ""
    row["v1h_recovery_episode_ids"] = ""
    row["v1h_recovery_reason"] = ""
    row["v1h_recovery_source"] = ""
    row["v1h_recovery_block_reason"] = ""
    return row


def choose_recovery_route_dist(row):
    # V1H 第一版：用 projected_route_dist_m 作為 refit 目標。
    # 若 projected 缺失，才 fallback 到 route_dist_refit_m_v1g / nearest / reliable。
    for col in [
        "projected_route_dist_m",
        "route_dist_refit_m_v1g",
        "nearest_route_dist_m",
        "reliable_route_dist_m",
    ]:
        v = row.get(col, "")
        if fnum(v) is not None:
            return v, col
    return "", ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-root", required=True, help="V1G final consolidated route folder root")
    ap.add_argument("--review-list-csv", required=True)
    ap.add_argument("--route-folder", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--local-exclusion-csv", default="")
    args = ap.parse_args()

    input_root = Path(args.input_root)
    out_root = Path(args.out_dir) / args.route_folder
    review_rows_all = read_csv(args.review_list_csv)

    review_rows = [
        r for r in review_rows_all
        if r.get("v1h_review_decision") == "recover_candidate"
        and bool_like_true(r.get("recovery_allowed", "false"))
    ]

    exclusion_rows = []
    if args.local_exclusion_csv and Path(args.local_exclusion_csv).exists():
        exclusion_rows = read_csv(args.local_exclusion_csv)
    exclusion_lookup = build_exclusion_lookup(exclusion_rows)

    activity_files = sorted(input_root.rglob("*_activity_points_osm_nlsc_corrected_v1g.csv"))

    applied_rows_all = []
    source_summary = []

    reviews_by_activity = {}
    for r in review_rows:
        reviews_by_activity.setdefault(r.get("activity_id", ""), []).append(r)

    for fp in activity_files:
        activity_id = fp.parent.name
        out_dir = out_root / activity_id
        out_fp = out_dir / f"{args.route_folder}_{activity_id}_activity_points_osm_nlsc_corrected_v1h.csv"

        rows = read_csv(fp)
        rows = [add_v1h_schema_passthrough(dict(r)) for r in rows]

        activity_reviews = reviews_by_activity.get(activity_id, [])
        applied_count = 0
        blocked_count = 0

        for rv in activity_reviews:
            start = fnum(rv.get("elapsed_start_sec"))
            end = fnum(rv.get("elapsed_end_sec"))
            if start is None or end is None:
                continue

            apply_only_unusable = bool_like_true(rv.get("apply_only_unusable_v1g", "true"))
            rule = rv.get("v1h_recovery_rule_candidate", "")
            reason = rv.get("review_reason", "")

            for row in rows:
                if not in_elapsed_range(row, start, end):
                    continue

                original_status = row.get("route_context_model_status_v1g", "")
                original_usable = row.get("route_context_model_usable_v1g", "")
                is_candidate = original_status in CANDIDATE_STATUSES

                if apply_only_unusable and not is_candidate:
                    # 不改 clean / anchor rows；只留下 block reason 供 QA。
                    if not row.get("v1h_recovery_block_reason"):
                        row["v1h_recovery_block_reason"] = "skip_clean_or_non_candidate_row_apply_only_unusable_v1g"
                    blocked_count += 1
                    continue

                excluded, ex = is_excluded(row, activity_id, exclusion_lookup)
                if excluded:
                    row["v1h_recovery_block_reason"] = "skip_local_exclusion_reviewed"
                    row["v1h_recovery_reason"] = ex.get("exclusion_reason", "")
                    blocked_count += 1
                    continue

                target_dist, source_col = choose_recovery_route_dist(row)
                if target_dist == "":
                    row["v1h_recovery_block_reason"] = "missing_recovery_target_route_dist"
                    blocked_count += 1
                    continue

                row["route_context_model_status_v1h"] = "matched_core_recovered_from_v1h_reviewed_mainline_corridor"
                row["route_context_model_usable_v1h"] = "True"
                row["route_context_model_reason_v1h"] = reason

                row["route_dist_refit_m_v1h"] = target_dist
                row["route_dist_refit_method_v1h"] = f"v1h_reviewed_recovery_from_{source_col}"

                row["v1h_recovery_applied"] = "True"
                row["v1h_recovery_rule"] = rule
                row["v1h_recovery_reviewed_unit_type"] = rv.get("reviewed_unit_type", "")
                row["v1h_recovery_cluster_ids"] = rv.get("cluster_ids", "")
                row["v1h_recovery_episode_ids"] = rv.get("episode_ids", "")
                row["v1h_recovery_reason"] = reason
                row["v1h_recovery_source"] = source_col
                row["v1h_recovery_block_reason"] = ""

                applied_count += 1

                applied_rows_all.append({
                    "activity_id": activity_id,
                    "elapsed_sec": row.get("elapsed_sec", ""),
                    "original_status_v1g": original_status,
                    "original_usable_v1g": original_usable,
                    "new_status_v1h": row["route_context_model_status_v1h"],
                    "new_usable_v1h": row["route_context_model_usable_v1h"],
                    "offset_m": row.get("offset_m", ""),
                    "target_route_dist_m": target_dist,
                    "target_route_dist_source": source_col,
                    "v1h_recovery_rule": rule,
                    "reviewed_unit_type": rv.get("reviewed_unit_type", ""),
                    "cluster_ids": rv.get("cluster_ids", ""),
                    "episode_ids": rv.get("episode_ids", ""),
                    "review_reason": reason,
                })

        write_csv(out_fp, rows)

        source_summary.append({
            "activity_id": activity_id,
            "source": "v1h_reviewed_recovery" if applied_count > 0 else "v1g_passthrough_with_v1h_schema",
            "input_fp": str(fp),
            "output_fp": str(out_fp),
            "review_rows": len(activity_reviews),
            "applied_rows": applied_count,
            "blocked_rows": blocked_count,
        })

        if applied_count > 0 or activity_reviews:
            print("=" * 100)
            print("V1H reviewed recovery:", activity_id)
            print("output:", out_fp)
            print("review rows:", len(activity_reviews))
            print("applied rows:", applied_count)
            print("blocked rows:", blocked_count)

    summary_fp = out_root / f"{args.route_folder}_v1h_reviewed_recovery_source_summary.csv"
    applied_fp = out_root / f"{args.route_folder}_v1h_reviewed_recovery_applied_rows_all.csv"

    write_csv(summary_fp, source_summary)
    write_csv(applied_fp, applied_rows_all)

    print("=" * 100)
    print("V1H reviewed recovery completed")
    print("review rows:", len(review_rows))
    print("applied rows total:", len(applied_rows_all))
    print("summary:", summary_fp)
    print("applied rows:", applied_fp)
    print("=" * 100)


if __name__ == "__main__":
    main()
