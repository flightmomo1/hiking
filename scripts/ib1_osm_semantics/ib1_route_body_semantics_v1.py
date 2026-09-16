#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import math
import pandas as pd
import geopandas as gpd

OUTPUT_TAGS_V1 = [
    "highway",
    "highway_norm",
    "name",
    "surface",
    "tracktype",
    "smoothness",
    "sac_scale",
    "trail_visibility",
    "trailblazed",
    "trailblazed:visibility",
    "width",
    "est_width",
    "incline",
    "step_count",
    "step_count_raw",
    "is_steps",
    "bridge",
    "ford",
    "handrail",
    "handrail:left",
    "handrail:right",
    "handrail:center",
    "safety_rope",
    "safety_rope_side",
    "assisted_trail",
    "rungs",
    "via_ferrata_scale",
    "tunnel",
    "covered",
    "embankment",
    "cutting",
    "lit",
    "informal",
    "access",
    "foot",
    "access:conditional",
    "foot:conditional",
    "barrier",
    "locked",
    "oneway",
    "route_class_raw",
    "highway_family",
    "walk_relevance",
    "route_role",
    "matching_semantic_score",
    "trail_difficulty_hint",
]


def norm_id(v):
    if pd.isna(v):
        return ""
    s = str(v).strip()
    if s.endswith(".0"):
        head = s[:-2]
        if head.replace("-", "", 1).isdigit():
            s = head
    return s


NULL_LITERALS = {
    "",
    "<na>",
    "nan",
    "none",
    "null",
    "nat",
}


def clean(v):
    if pd.isna(v):
        return ""

    s = str(v).strip()

    if s.lower() in NULL_LITERALS:
        return ""

    return s


def truthy_present(v):
    return clean(v) != ""


def flip_side(v):
    s = clean(v).lower()
    if s == "left":
        return "right"
    if s == "right":
        return "left"
    return clean(v)


def normalize_incline(v, reverse):
    s = clean(v)
    if not s or not reverse:
        return s
    low = s.lower()
    if low == "up":
        return "down"
    if low == "down":
        return "up"
    stripped = low.replace("%", "").strip()
    try:
        x = float(stripped)
        x = -x
        if "%" in s:
            return f"{x:g}%"
        return f"{x:g}"
    except Exception:
        return s


def main():
    ap = argparse.ArgumentParser(description="IB1 Route Body Semantics v1 - canonical Route Axis identity contract")
    ap.add_argument("--route-axis-edges", required=True)
    ap.add_argument("--osm-highway", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--case-id", default="")
    args = ap.parse_args()

    edges_fp = Path(args.route_axis_edges)
    osm_fp = Path(args.osm_highway)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    edges = pd.read_csv(edges_fp, low_memory=False)
    osm = gpd.read_file(osm_fp)

    required_edges = {"osm_type", "osm_id", "traversed_length_m"}
    missing = required_edges - set(edges.columns)
    if missing:
        raise SystemExit(f"Missing Route Axis edge columns: {sorted(missing)}")

    order_col = "route_axis_order" if "route_axis_order" in edges.columns else (
        "traversal_order" if "traversal_order" in edges.columns else None
    )
    if order_col is None:
        raise SystemExit("Need route_axis_order or traversal_order")

    edges = edges.copy()
    edges["osm_type_key"] = edges["osm_type"].map(clean)
    edges["osm_id_key"] = edges["osm_id"].map(norm_id)
    edges["_order"] = pd.to_numeric(edges[order_col], errors="coerce")
    edges["_len"] = pd.to_numeric(edges["traversed_length_m"], errors="coerce")
    if edges["_order"].isna().any() or edges["_len"].isna().any():
        raise SystemExit("Non-numeric order or traversed_length_m in Route Axis edges")
    if (edges["_len"] < -1e-9).any():
        raise SystemExit("Negative traversed_length_m found")

    edges = edges.sort_values("_order", kind="stable").reset_index(drop=True)
    edges["route_start_m"] = edges["_len"].cumsum().shift(fill_value=0.0)
    edges["route_end_m"] = edges["route_start_m"] + edges["_len"]

    if "osm_type" not in osm.columns or "osm_id" not in osm.columns:
        raise SystemExit("OSM highway layer must contain osm_type and osm_id")

    osm = osm.copy()
    osm["osm_type_key"] = osm["osm_type"].map(clean)
    osm["osm_id_key"] = osm["osm_id"].map(norm_id)
    dup = osm.duplicated(["osm_type_key", "osm_id_key"], keep=False)
    duplicate_identity_n = int(dup.sum())
    osm_attr = osm.drop(columns="geometry", errors="ignore").drop_duplicates(
        ["osm_type_key", "osm_id_key"], keep="first"
    )

    # Production schema contract:
    # Every declared semantic tag must exist in output even when the
    # current IA1 source layer does not contain that column.
    # Missing source columns remain UNKNOWN; schema must not drift.
    for col in OUTPUT_TAGS_V1:
        if col not in osm_attr.columns:
            osm_attr[col] = pd.NA

    keep = ["osm_type_key", "osm_id_key"] + OUTPUT_TAGS_V1
    osm_attr = osm_attr[keep]

    merged = edges.merge(osm_attr, on=["osm_type_key", "osm_id_key"], how="left", suffixes=("", "_osm"), indicator=True)
    merged["semantic_source"] = merged["_merge"].map({"both": "canonical_identity", "left_only": "unmatched", "right_only": "unexpected"})
    merged.drop(columns=["_merge"], inplace=True)

    reverse = merged.get("direction", pd.Series([""] * len(merged))).astype(str).str.lower().eq("reverse")

    # Preserve raw directional values and add Route-Axis-relative interpretations.
    for col in ["handrail:left", "handrail:right"]:
        if col not in merged.columns:
            merged[col] = ""
    left_raw = merged["handrail:left"].map(clean)
    right_raw = merged["handrail:right"].map(clean)
    merged["route_handrail_left"] = [r if not rev else rr for r, rr, rev in zip(left_raw, right_raw, reverse)]
    merged["route_handrail_right"] = [rr if not rev else r for r, rr, rev in zip(left_raw, right_raw, reverse)]

    if "safety_rope_side" not in merged.columns:
        merged["safety_rope_side"] = ""
    merged["route_safety_rope_side"] = [flip_side(v) if rev else clean(v) for v, rev in zip(merged["safety_rope_side"], reverse)]

    if "incline" not in merged.columns:
        merged["incline"] = ""
    merged["route_incline"] = [normalize_incline(v, rev) for v, rev in zip(merged["incline"], reverse)]

    width = merged.get("width", pd.Series([""] * len(merged))).map(clean)
    est_width = merged.get("est_width", pd.Series([""] * len(merged))).map(clean)
    merged["route_width_raw"] = [w if w else ew for w, ew in zip(width, est_width)]
    merged["route_width_source"] = ["width" if w else ("est_width" if ew else "unknown") for w, ew in zip(width, est_width)]

    # Coverage summary by occurrence count and Route Axis length.
    total_len = float(merged["_len"].sum())
    cov_rows = []
    for tag in OUTPUT_TAGS_V1:
        if tag not in merged.columns:
            continue
        present = merged[tag].map(truthy_present)
        occ_n = int(present.sum())
        length_m = float(merged.loc[present, "_len"].sum())
        cov_rows.append({
            "tag": tag,
            "occurrence_populated_n": occ_n,
            "occurrence_total_n": int(len(merged)),
            "occurrence_coverage_rate": occ_n / len(merged) if len(merged) else math.nan,
            "route_length_populated_m": length_m,
            "route_length_total_m": total_len,
            "route_length_coverage_rate": length_m / total_len if total_len > 0 else math.nan,
        })
    coverage = pd.DataFrame(cov_rows)

    case_id = args.case_id or (clean(merged["case_id"].iloc[0]) if "case_id" in merged.columns and len(merged) else "")
    summary = {
        "case_id": case_id,
        "route_occurrence_n": int(len(merged)),
        "route_length_m": total_len,
        "unique_route_osm_identity_n": int(merged[["osm_type_key", "osm_id_key"]].drop_duplicates().shape[0]),
        "identity_matched_occurrence_n": int((merged["semantic_source"] == "canonical_identity").sum()),
        "identity_match_rate": float((merged["semantic_source"] == "canonical_identity").mean()) if len(merged) else None,
        "duplicate_osm_identity_rows_in_source_n": duplicate_identity_n,
        "unknown_width_occurrence_n": int((merged["route_width_source"] == "unknown").sum()),
    }

    out_occ = out_dir / "route_body_semantics.csv"
    out_cov = out_dir / "route_body_tag_coverage.csv"
    out_summary = out_dir / "route_body_semantics_summary.json"

    merged.drop(columns=["_order", "_len"], errors="ignore").to_csv(out_occ, index=False, encoding="utf-8-sig")
    coverage.to_csv(out_cov, index=False, encoding="utf-8-sig")
    out_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("ROUTE BODY SEMANTIC AUDIT")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("outputs:")
    print(out_occ)
    print(out_cov)
    print(out_summary)


if __name__ == "__main__":
    main()
