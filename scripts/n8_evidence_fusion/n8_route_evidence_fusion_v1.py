#!/usr/bin/env python3
"""Build the N8 v1.1 route-evidence alignment tables.

N8 aligns already-produced IB1 evidence to fixed Route Axis terrain segments.
It does not calculate a risk score.  Route-body evidence and nearby-feature
evidence remain separate throughout the output contract.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


VERSION = "v1.1"
EPS = 1e-9
ROUTE_LENGTH_TOLERANCE_M = 1e-6

SEMANTIC_FIELDS = [
    "highway",
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
    "is_steps",
    "bridge",
    "ford",
    "handrail",
    "safety_rope",
    "assisted_trail",
    "rungs",
    "tunnel",
    "embankment",
    "lit",
    "informal",
    "access",
    "foot",
    "route_handrail_left",
    "route_handrail_right",
    "route_safety_rope_side",
    "route_incline",
    "route_width_raw",
    "route_width_source",
]

UNKNOWN_TOKENS = {
    "",
    "unknown",
    "<na>",
    "nan",
    "none",
    "null",
    "nat",
}

NEARBY_LINK_COLUMNS = [
    "case_id",
    "segment_id",
    "nearby_feature_id",
    "segment_feature_link_id",
    "seg_id",
    "segment_start_m",
    "segment_end_m",
    "overlap_start_m",
    "overlap_end_m",
    "overlap_m",
    "osm_type",
    "osm_id",
    "natural",
    "feature_length_m",
    "feature_interval_min_distance_m",
    "source_interval_start_m",
    "source_interval_end_m",
    "evidence_class",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Align IB1 terrain, Route Body, nearby-feature, and elevation "
            "evidence to N8 Route Axis segments. No risk score is produced."
        )
    )
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--terrain-evidence", required=True)
    parser.add_argument("--route-body-semantics", required=True)
    parser.add_argument("--nearby-feature-intervals", required=True)
    parser.add_argument("--elevation-profile", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--signed-grade-source",
        default="ib1_route_profile_ele_smooth",
        help="Provenance label stored in the frozen v1.1 backbone contract.",
    )
    parser.add_argument(
        "--absolute-elevation-source",
        default="nlsc_anchor_gpx_shape_v1",
        help="Provenance label stored in the frozen v1.1 backbone contract.",
    )
    return parser.parse_args()


def require_columns(frame: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise RuntimeError(f"{label} missing required columns: {missing}")


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def is_unknown(value: object) -> bool:
    return clean_text(value).lower() in UNKNOWN_TOKENS


def validate_case_id(frame: pd.DataFrame, case_id: str, label: str) -> None:
    if "case_id" not in frame.columns:
        return
    values = {
        clean_text(value)
        for value in frame["case_id"]
        if clean_text(value)
    }
    if values and values != {case_id}:
        raise RuntimeError(
            f"{label} case_id mismatch: expected {case_id!r}, got {sorted(values)!r}"
        )


def load_inputs(args: argparse.Namespace) -> tuple[pd.DataFrame, ...]:
    terrain = pd.read_csv(args.terrain_evidence).sort_values("dist_start").reset_index(drop=True)
    body = pd.read_csv(args.route_body_semantics).sort_values(
        "traversal_order"
    ).reset_index(drop=True)
    nearby = pd.read_csv(args.nearby_feature_intervals).sort_values(
        "route_start_m"
    ).reset_index(drop=True)
    elevation = pd.read_csv(args.elevation_profile).sort_values("dist_m").reset_index(drop=True)

    require_columns(
        terrain,
        [
            "seg_id",
            "dist_start",
            "dist_end",
            "seg_len_axis_m",
            "map_evidence_status",
            "relief_evidence_status",
            "local_relief_m",
            "terrain_relief_ratio",
            "contour_feature_count_window",
        ],
        "terrain evidence",
    )
    require_columns(
        body,
        [
            "traversal_order",
            "route_axis_order",
            "edge_id",
            "edge_occurrence",
            "osm_type",
            "osm_id",
            "direction",
            "route_start_m",
            "route_end_m",
        ] + SEMANTIC_FIELDS,
        "Route Body semantics",
    )
    require_columns(
        nearby,
        [
            "osm_type",
            "osm_id",
            "natural",
            "min_distance_to_axis_m",
            "route_start_m",
            "route_end_m",
        ],
        "nearby-feature intervals",
    )
    if not {
        "feature_length_m",
        "feature_length_or_perimeter_m",
    }.intersection(nearby.columns):
        raise RuntimeError(
            "nearby-feature intervals require feature_length_m or "
            "feature_length_or_perimeter_m"
        )
    require_columns(
        elevation,
        ["dist_m", "ele_smooth", "ele_gpx_shape_m", "ele_fused_m"],
        "elevation profile",
    )

    for frame, label in [
        (terrain, "terrain evidence"),
        (body, "Route Body semantics"),
        (elevation, "elevation profile"),
    ]:
        validate_case_id(frame, args.case_id, label)

    if terrain.empty:
        raise RuntimeError("terrain evidence is empty")
    if body.empty:
        raise RuntimeError("Route Body semantics is empty")
    if elevation.empty:
        raise RuntimeError("elevation profile is empty")
    if terrain["seg_id"].duplicated().any():
        raise RuntimeError("terrain seg_id must be unique")
    if body["traversal_order"].duplicated().any():
        raise RuntimeError("Route Body traversal_order must be unique")
    if not terrain["dist_start"].is_monotonic_increasing:
        raise RuntimeError("terrain dist_start must be monotonic")
    if not elevation["dist_m"].is_monotonic_increasing:
        raise RuntimeError("elevation dist_m must be monotonic")
    if elevation["dist_m"].duplicated().any():
        raise RuntimeError("elevation dist_m must be unique")

    route_length = float(terrain["dist_end"].iloc[-1])
    elevation_length = float(elevation["dist_m"].iloc[-1])
    if abs(route_length - elevation_length) > ROUTE_LENGTH_TOLERANCE_M:
        raise RuntimeError(
            "elevation/terrain route length mismatch: "
            f"{elevation_length} vs {route_length}"
        )
    if (terrain["seg_len_axis_m"] <= 0).any():
        raise RuntimeError("terrain segment lengths must be positive")

    return terrain, body, nearby, elevation


def build_evidence_tables(
    case_id: str,
    terrain: pd.DataFrame,
    body: pd.DataFrame,
    nearby: pd.DataFrame,
    elevation: pd.DataFrame,
    signed_grade_source: str,
    absolute_elevation_source: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    profile_distance = elevation["dist_m"].to_numpy(float)
    profile_elevation = elevation["ele_smooth"].to_numpy(float)
    shape_elevation = elevation["ele_gpx_shape_m"].to_numpy(float)
    fused_elevation = elevation["ele_fused_m"].to_numpy(float)

    segment_rows: list[dict[str, object]] = []
    body_link_rows: list[dict[str, object]] = []
    nearby_link_rows: list[dict[str, object]] = []

    feature_length_column = (
        "feature_length_m"
        if "feature_length_m" in nearby.columns
        else "feature_length_or_perimeter_m"
    )

    for segment in terrain.itertuples(index=False):
        seg_id = int(segment.seg_id)
        start = float(segment.dist_start)
        end = float(segment.dist_end)
        segment_length = float(segment.seg_len_axis_m)

        route_elevation_start = float(np.interp(start, profile_distance, profile_elevation))
        route_elevation_end = float(np.interp(end, profile_distance, profile_elevation))
        shape_start = float(np.interp(start, profile_distance, shape_elevation))
        shape_end = float(np.interp(end, profile_distance, shape_elevation))
        fused_start = float(np.interp(start, profile_distance, fused_elevation))
        fused_end = float(np.interp(end, profile_distance, fused_elevation))

        overlapping_body = body[
            (body["route_end_m"] > start + EPS)
            & (body["route_start_m"] < end - EPS)
        ]
        body_overlap_sum = 0.0
        dominant: dict[str, object] | None = None

        for _, occurrence in overlapping_body.iterrows():
            overlap_start = max(start, float(occurrence["route_start_m"]))
            overlap_end = min(end, float(occurrence["route_end_m"]))
            overlap = overlap_end - overlap_start
            if overlap <= EPS:
                continue

            body_overlap_sum += overlap
            traversal_order = int(occurrence["traversal_order"])
            record: dict[str, object] = {
                "case_id": case_id,
                "segment_id": f"{case_id}:{seg_id}",
                "route_occurrence_id": f"{case_id}:{traversal_order}",
                "segment_route_body_link_id": f"{case_id}:{seg_id}:{traversal_order}",
                "seg_id": seg_id,
                "segment_start_m": start,
                "segment_end_m": end,
                "overlap_start_m": overlap_start,
                "overlap_end_m": overlap_end,
                "overlap_m": overlap,
                "overlap_fraction_segment": overlap / segment_length,
                "traversal_order": traversal_order,
                "route_axis_order": int(occurrence["route_axis_order"]),
                "edge_id": occurrence["edge_id"],
                "edge_occurrence": occurrence["edge_occurrence"],
                "osm_type": occurrence["osm_type"],
                "osm_id": occurrence["osm_id"],
                "direction": occurrence["direction"],
                "occurrence_route_start_m": occurrence["route_start_m"],
                "occurrence_route_end_m": occurrence["route_end_m"],
                "semantic_source": occurrence.get("semantic_source", ""),
                "evidence_class": "ROUTE_BODY_CANONICAL",
            }
            for field in SEMANTIC_FIELDS:
                record[field] = occurrence[field]
            body_link_rows.append(record)

            if dominant is None or overlap > float(dominant["overlap_m"]):
                dominant = {
                    "overlap_m": overlap,
                    "traversal_order": traversal_order,
                    "osm_type": occurrence["osm_type"],
                    "osm_id": occurrence["osm_id"],
                    "direction": occurrence["direction"],
                }

        overlapping_nearby = nearby[
            (nearby["route_end_m"] > start + EPS)
            & (nearby["route_start_m"] < end - EPS)
        ]
        nearby_overlap_sum = 0.0

        for _, feature in overlapping_nearby.iterrows():
            overlap_start = max(start, float(feature["route_start_m"]))
            overlap_end = min(end, float(feature["route_end_m"]))
            overlap = overlap_end - overlap_start
            if overlap <= EPS:
                continue

            nearby_overlap_sum += overlap
            osm_type = clean_text(feature["osm_type"])
            osm_id = int(feature["osm_id"])
            nearby_link_rows.append({
                "case_id": case_id,
                "segment_id": f"{case_id}:{seg_id}",
                "nearby_feature_id": f"{osm_type}:{osm_id}",
                "segment_feature_link_id": f"{case_id}:{seg_id}:{osm_type}:{osm_id}",
                "seg_id": seg_id,
                "segment_start_m": start,
                "segment_end_m": end,
                "overlap_start_m": overlap_start,
                "overlap_end_m": overlap_end,
                "overlap_m": overlap,
                "osm_type": osm_type,
                "osm_id": osm_id,
                "natural": feature["natural"],
                "feature_length_m": feature[feature_length_column],
                "feature_interval_min_distance_m": feature["min_distance_to_axis_m"],
                "source_interval_start_m": feature["route_start_m"],
                "source_interval_end_m": feature["route_end_m"],
                "evidence_class": "NEARBY_FEATURE_INTERVAL",
            })

        backbone_record: dict[str, object] = {
            "case_id": case_id,
            "segment_id": f"{case_id}:{seg_id}",
            "seg_id": seg_id,
            "route_start_m": start,
            "route_end_m": end,
            "seg_len_axis_m": segment_length,
            "route_ele_start_m": route_elevation_start,
            "route_ele_end_m": route_elevation_end,
            "route_net_ele_change_m": route_elevation_end - route_elevation_start,
            "route_net_grade_pct": (
                100.0 * (route_elevation_end - route_elevation_start) / segment_length
            ),
            "signed_grade_source": signed_grade_source,
            "gpx_shape_start_m": shape_start,
            "gpx_shape_end_m": shape_end,
            "gpx_shape_change_m": shape_end - shape_start,
            "gpx_shape_scale_m": 50.0,
            "fused_ele_start_m": fused_start,
            "fused_ele_end_m": fused_end,
            "fused_ele_change_m": fused_end - fused_start,
            "absolute_elevation_source": absolute_elevation_source,
            "map_evidence_status": segment.map_evidence_status,
            "relief_evidence_status": segment.relief_evidence_status,
            "local_relief_m": segment.local_relief_m,
            "terrain_relief_ratio": segment.terrain_relief_ratio,
            "contour_feature_count_window": segment.contour_feature_count_window,
            "route_body_link_count": int(len(overlapping_body)),
            "route_body_overlap_sum_m": body_overlap_sum,
            "nearby_cliff_link_count": int(len(overlapping_nearby)),
            "nearby_cliff_interval_overlap_sum_m": nearby_overlap_sum,
        }
        if dominant is None:
            backbone_record.update({
                "dominant_traversal_order": np.nan,
                "dominant_osm_type": np.nan,
                "dominant_osm_id": np.nan,
                "dominant_direction": np.nan,
                "dominant_route_body_overlap_m": np.nan,
                "dominant_route_body_fraction": np.nan,
            })
        else:
            backbone_record.update({
                "dominant_traversal_order": dominant["traversal_order"],
                "dominant_osm_type": dominant["osm_type"],
                "dominant_osm_id": dominant["osm_id"],
                "dominant_direction": dominant["direction"],
                "dominant_route_body_overlap_m": dominant["overlap_m"],
                "dominant_route_body_fraction": (
                    float(dominant["overlap_m"]) / segment_length
                ),
            })
        segment_rows.append(backbone_record)

    return (
        pd.DataFrame(segment_rows),
        pd.DataFrame(body_link_rows),
        pd.DataFrame(nearby_link_rows, columns=NEARBY_LINK_COLUMNS),
    )


def build_semantic_composition(
    case_id: str,
    backbone: pd.DataFrame,
    body_links: pd.DataFrame,
) -> pd.DataFrame:
    links_by_segment = {
        int(seg_id): group
        for seg_id, group in body_links.groupby("seg_id", sort=False)
    }
    rows: list[dict[str, object]] = []

    for segment in backbone.itertuples(index=False):
        seg_id = int(segment.seg_id)
        segment_length = float(segment.seg_len_axis_m)
        links = links_by_segment.get(seg_id)
        if links is None or links.empty:
            raise RuntimeError(f"segment {seg_id} has no Route Body link")

        for field in SEMANTIC_FIELDS:
            normalized = links[field].map(clean_text)
            unknown_mask = normalized.map(is_unknown)
            known = links.loc[~unknown_mask].assign(_value=normalized[~unknown_mask])
            unknown = links.loc[unknown_mask]

            if known.empty:
                value_lengths = pd.Series(dtype=float)
            else:
                value_lengths = (
                    known.groupby("_value", sort=False)["overlap_m"]
                    .sum()
                    .sort_values(ascending=False)
                )

            known_overlap = float(known["overlap_m"].sum())
            unknown_overlap = float(unknown["overlap_m"].sum())
            distinct_known_values = int(len(value_lengths))

            if known_overlap <= EPS:
                status = "FULL_UNKNOWN"
            elif unknown_overlap <= EPS:
                status = (
                    "FULL_KNOWN_SINGLE"
                    if distinct_known_values == 1
                    else "FULL_KNOWN_MIXED"
                )
            else:
                status = (
                    "PARTIAL_KNOWN_SINGLE"
                    if distinct_known_values == 1
                    else "PARTIAL_KNOWN_MIXED"
                )

            if value_lengths.empty:
                dominant_value = ""
                dominant_overlap = 0.0
                composition = ""
            else:
                dominant_value = clean_text(value_lengths.index[0])
                dominant_overlap = float(value_lengths.iloc[0])
                composition = " | ".join(
                    f"{clean_text(value)}:{float(overlap):.3f}m"
                    for value, overlap in value_lengths.items()
                )

            rows.append({
                "case_id": case_id,
                "segment_id": f"{case_id}:{seg_id}",
                "seg_id": seg_id,
                "route_start_m": segment.route_start_m,
                "route_end_m": segment.route_end_m,
                "field": field,
                "semantic_status": status,
                "known_overlap_m": known_overlap,
                "unknown_overlap_m": unknown_overlap,
                "known_fraction": known_overlap / segment_length,
                "unknown_fraction": unknown_overlap / segment_length,
                "distinct_known_values": distinct_known_values,
                "dominant_known_value": dominant_value,
                "dominant_known_overlap_m": dominant_overlap,
                "dominant_known_fraction_segment": dominant_overlap / segment_length,
                "value_composition": composition,
            })

    return pd.DataFrame(rows)


def build_route_coverage(
    case_id: str,
    composition: pd.DataFrame,
    route_length: float,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for field, group in composition.groupby("field"):
        statuses = group["semantic_status"].astype(str)
        known_route = float(group["known_overlap_m"].sum())
        unknown_route = float(group["unknown_overlap_m"].sum())
        rows.append({
            "case_id": case_id,
            "field": field,
            "known_route_m": known_route,
            "unknown_route_m": unknown_route,
            "known_route_pct": 100.0 * known_route / route_length,
            "full_unknown_segments": int((statuses == "FULL_UNKNOWN").sum()),
            "partial_segments": int(statuses.str.startswith("PARTIAL_").sum()),
            "mixed_segments": int(statuses.str.endswith("_MIXED").sum()),
            "full_single_segments": int((statuses == "FULL_KNOWN_SINGLE").sum()),
        })
    return (
        pd.DataFrame(rows)
        .sort_values("known_route_pct", ascending=False)
        .reset_index(drop=True)
    )


def serialized_null_literal_count(frame: pd.DataFrame) -> int:
    text = frame.map(clean_text).apply(lambda column: column.str.lower())
    return int(text.isin(UNKNOWN_TOKENS - {"", "unknown"}).sum().sum())


def validate_outputs(
    terrain: pd.DataFrame,
    backbone: pd.DataFrame,
    body_links: pd.DataFrame,
    nearby_links: pd.DataFrame,
    composition: pd.DataFrame,
    coverage: pd.DataFrame,
) -> dict[str, object]:
    segment_ids = set(backbone["segment_id"])
    semantic_field_count = len(SEMANTIC_FIELDS)
    body_coverage_delta = (
        backbone["route_body_overlap_sum_m"] - backbone["seg_len_axis_m"]
    ).abs()
    checks = {
        "segment_count_matches_terrain": len(backbone) == len(terrain),
        "segment_id_unique": backbone["segment_id"].is_unique,
        "route_body_link_id_unique": body_links["segment_route_body_link_id"].is_unique,
        "route_body_segment_fk_valid": set(body_links["segment_id"]).issubset(segment_ids),
        "route_body_all_segments_represented": set(body_links["segment_id"]) == segment_ids,
        "route_body_full_coverage_1e_6m": bool((body_coverage_delta <= 1e-6).all()),
        "nearby_feature_link_id_unique": nearby_links.empty
        or nearby_links["segment_feature_link_id"].is_unique,
        "nearby_feature_segment_fk_valid": nearby_links.empty
        or set(nearby_links["segment_id"]).issubset(segment_ids),
        "semantic_key_unique": not composition.duplicated(["segment_id", "field"]).any(),
        "semantic_full_matrix": len(composition) == len(backbone) * semantic_field_count,
        "semantic_segment_fk_valid": set(composition["segment_id"]) == segment_ids,
        "coverage_field_unique": coverage["field"].is_unique,
        "coverage_fields_complete": set(coverage["field"]) == set(SEMANTIC_FIELDS),
        "serialized_null_literal_cells_zero": sum(
            serialized_null_literal_count(frame)
            for frame in [backbone, body_links, nearby_links, composition, coverage]
        ) == 0,
    }
    failures = [name for name, passed in checks.items() if not passed]
    if failures:
        raise RuntimeError(f"N8 output contract failed: {failures}")
    return checks


def write_outputs(
    output_dir: Path,
    backbone: pd.DataFrame,
    body_links: pd.DataFrame,
    nearby_links: pd.DataFrame,
    composition: pd.DataFrame,
    coverage: pd.DataFrame,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "backbone": output_dir / "n8_segment_backbone_v1_1.csv",
        "route_body_links": output_dir / "n8_segment_route_body_links_v1_1.csv",
        "nearby_feature_links": output_dir / "n8_segment_cliff_links_v1_1.csv",
        "semantic_composition": output_dir / "n8_segment_semantic_composition_v1_1.csv",
        "semantic_coverage": output_dir / "n8_route_semantic_coverage_v1_1.csv",
    }
    for key, frame in [
        ("backbone", backbone),
        ("route_body_links", body_links),
        ("nearby_feature_links", nearby_links),
        ("semantic_composition", composition),
        ("semantic_coverage", coverage),
    ]:
        frame.to_csv(paths[key], index=False, encoding="utf-8-sig")
    return paths


def main() -> None:
    args = parse_args()
    terrain, body, nearby, elevation = load_inputs(args)
    backbone, body_links, nearby_links = build_evidence_tables(
        args.case_id,
        terrain,
        body,
        nearby,
        elevation,
        args.signed_grade_source,
        args.absolute_elevation_source,
    )
    composition = build_semantic_composition(args.case_id, backbone, body_links)
    route_length = float(backbone["route_end_m"].iloc[-1])
    coverage = build_route_coverage(args.case_id, composition, route_length)
    checks = validate_outputs(
        terrain,
        backbone,
        body_links,
        nearby_links,
        composition,
        coverage,
    )
    output_dir = Path(args.output_dir)
    paths = write_outputs(
        output_dir,
        backbone,
        body_links,
        nearby_links,
        composition,
        coverage,
    )

    vertical_references = (
        sorted({clean_text(value) for value in elevation["absolute_vertical_reference"] if clean_text(value)})
        if "absolute_vertical_reference" in elevation.columns
        else []
    )
    summary = {
        "case_id": args.case_id,
        "n8_version": VERSION,
        "role": "evidence_alignment_no_numeric_risk_score",
        "route_length_m": route_length,
        "segment_n": len(backbone),
        "route_body_link_n": len(body_links),
        "nearby_feature_link_n": len(nearby_links),
        "nearby_unique_feature_n": int(nearby_links["nearby_feature_id"].nunique())
        if not nearby_links.empty
        else 0,
        "semantic_field_n": len(coverage),
        "semantic_composition_n": len(composition),
        "absolute_vertical_references_in_profile": vertical_references,
        "checks": checks,
        "overall_pass": True,
        "outputs": {key: str(path) for key, path in paths.items()},
    }
    summary_path = output_dir / "n8_evidence_fusion_summary_v1_1.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=" * 88)
    print("N8 ROUTE EVIDENCE FUSION", VERSION)
    print("=" * 88)
    print("case_id:", args.case_id)
    print("role: evidence alignment; no numeric risk score")
    print("route_length_m:", route_length)
    print("segments:", len(backbone))
    print("route_body_links:", len(body_links))
    print("nearby_feature_links:", len(nearby_links))
    print("nearby_unique_features:", summary["nearby_unique_feature_n"])
    print("semantic_matrix:", f"{len(backbone)} x {len(coverage)} = {len(composition)}")
    print("overall_pass: True")
    print("output_dir:", output_dir)


if __name__ == "__main__":
    main()
