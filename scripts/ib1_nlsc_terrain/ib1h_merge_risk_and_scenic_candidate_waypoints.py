"""
ib1h_merge_risk_and_scenic_candidate_waypoints.py

Purpose
-------
Merge Prototype A risk-zone candidate waypoints with Ia1 v1.3 OSM scenic /
destination candidate waypoints.

This script is designed for:
- case_id: juansi_waterfall_fitcsv_20260503
- model_version: prototype_A_terrain_dominant_v1

Inputs
------
1. Risk-zone candidate waypoints by distance:
   outputs/prototype_A_terrain_dominant/{CASE_ID}/
   {CASE_ID}_prototype_A_candidate_waypoints_by_distance.csv

2. Scenic / destination candidate waypoints by distance:
   outputs/prototype_A_terrain_dominant/{CASE_ID}/
   {CASE_ID}_prototype_A_scenic_candidate_waypoints_by_distance.csv

Outputs
-------
1. Combined waypoint CSV:
   {CASE_ID}_prototype_A_candidate_waypoints_combined_by_distance.csv

2. Combined waypoint GeoJSON:
   {CASE_ID}_prototype_A_candidate_waypoints_combined.geojson

3. Summary TXT:
   {CASE_ID}_prototype_A_candidate_waypoints_combined_summary.txt

Method
------
- Normalize risk/scenic waypoint schemas.
- Sort by target_dist_m.
- Merge waypoints whose target_dist_m are within MERGE_DISTANCE_M.
- Preserve risk semantics first.
- Preserve destination / viewpoint / guide-map semantic tags as supplemental
  waypoint purpose.
- Keep destination_stop and viewpoint_stop even when merged into a nearby
  risk waypoint.

Notes
-----
This script does not project waypoints onto the route again. It expects both
input CSVs to already contain target_dist_m or route_dist_m / dist_m fields.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point


# =========================================================
# 0. Settings
# =========================================================

PROJECT_ROOT = Path(r"C:\mountain_work\115_osm")

CASE_ID = "juansi_waterfall_fitcsv_20260503"
MODEL_VERSION = "prototype_A_terrain_dominant_v1"
OUTPUT_STAGE = "prototype_A_terrain_dominant"

OUTDIR = PROJECT_ROOT / "outputs" / OUTPUT_STAGE / CASE_ID

RISK_WAYPOINT_CSV = (
    OUTDIR / f"{CASE_ID}_prototype_A_candidate_waypoints_by_distance.csv"
)

SCENIC_WAYPOINT_CSV = (
    OUTDIR / f"{CASE_ID}_prototype_A_scenic_candidate_waypoints_by_distance.csv"
)

COMBINED_CSV = (
    OUTDIR / f"{CASE_ID}_prototype_A_candidate_waypoints_combined_by_distance.csv"
)

COMBINED_GEOJSON = (
    OUTDIR / f"{CASE_ID}_prototype_A_candidate_waypoints_combined.geojson"
)

SUMMARY_TXT = (
    OUTDIR / f"{CASE_ID}_prototype_A_candidate_waypoints_combined_summary.txt"
)

MERGE_DISTANCE_M = 30.0

# Type priority: smaller means keep as primary representative when merging.
WAYPOINT_TYPE_PRIORITY = {
    "start_precheck": 10,
    "recovery_decision": 20,
    "recovery": 30,
    "conditional_check": 40,
    "conditional_check|pacing": 45,
    "pacing": 50,
    "rest_candidate": 60,
    "final_push": 70,
    "destination_stop": 80,
    "viewpoint_stop": 90,
    "guide_map_stop": 100,
    "scenic_stop": 110,
    "tourism_stop": 120,
}


# =========================================================
# 1. Helpers
# =========================================================

def first_existing_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def split_types(value: Any) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    parts = []
    for token in text.replace(",", "|").split("|"):
        token = token.strip()
        if token and token not in parts:
            parts.append(token)
    return parts


def join_unique(values: list[Any], sep: str = "|") -> str:
    out: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, list):
            tokens = value
        else:
            tokens = str(value).replace(",", sep).split(sep)
        for token in tokens:
            token = str(token).strip()
            if token and token.lower() not in {"nan", "none", "<na>"}:
                if token not in out:
                    out.append(token)
    return sep.join(out)


def waypoint_priority(waypoint_type: Any) -> int:
    types = split_types(waypoint_type)
    if not types:
        return 999
    return min(WAYPOINT_TYPE_PRIORITY.get(t, 900) for t in types)


def ensure_target_dist(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "target_dist_m" in df.columns:
        df["target_dist_m"] = pd.to_numeric(df["target_dist_m"], errors="coerce")
        return df

    dist_col = first_existing_col(
        df,
        [
            "route_dist_m",
            "dist_m",
            "waypoint_dist_m",
            "projected_dist_m",
            "nearest_route_dist_m",
        ],
    )

    if dist_col is None:
        raise ValueError(
            "Input waypoint CSV does not contain target_dist_m, route_dist_m, "
            "dist_m, waypoint_dist_m, projected_dist_m, or nearest_route_dist_m."
        )

    df["target_dist_m"] = pd.to_numeric(df[dist_col], errors="coerce")
    return df


def normalize_waypoint_schema(df: pd.DataFrame, source_kind: str) -> pd.DataFrame:
    df = ensure_target_dist(df)

    df = df.copy()
    df["source_kind"] = source_kind

    if "case_id" not in df.columns:
        df["case_id"] = CASE_ID
    if "model_version" not in df.columns:
        df["model_version"] = MODEL_VERSION

    if "waypoint_type" not in df.columns:
        df["waypoint_type"] = source_kind

    if "waypoint_id" not in df.columns:
        prefix = "RWP" if source_kind == "risk" else "SWP"
        df["waypoint_id"] = [
            f"{prefix}{i + 1:02d}"
            for i in range(len(df))
        ]

    # Normalize name fields.
    name_col = first_existing_col(
        df,
        ["name", "source_name", "poi_name", "label", "waypoint_name"],
    )
    if name_col is None:
        df["name"] = ""
    elif name_col != "name":
        df["name"] = df[name_col]

    # Normalize reason / source fields.
    reason_col = first_existing_col(
        df,
        ["reason", "waypoint_reason", "source_reason", "scenic_reason"],
    )
    if reason_col is None:
        df["reason"] = ""
    elif reason_col != "reason":
        df["reason"] = df[reason_col]

    source_layer_col = first_existing_col(
        df,
        ["source_layer", "osm_layer", "layer_name"],
    )
    if source_layer_col is None:
        df["source_layer"] = source_kind
    elif source_layer_col != "source_layer":
        df["source_layer"] = df[source_layer_col]

    offset_col = first_existing_col(
        df,
        ["nearest_route_offset_m", "offset_to_route_m", "offset_m"],
    )
    if offset_col is not None and offset_col != "nearest_route_offset_m":
        df["nearest_route_offset_m"] = df[offset_col]
    if "nearest_route_offset_m" not in df.columns:
        df["nearest_route_offset_m"] = pd.NA

    confidence_col = first_existing_col(
        df,
        ["confidence", "source_confidence", "match_confidence"],
    )
    if confidence_col is None:
        df["confidence"] = ""
    elif confidence_col != "confidence":
        df["confidence"] = df[confidence_col]

    # Coordinates, if available.
    lat_col = first_existing_col(df, ["lat", "raw_lat", "matched_lat", "y"])
    lon_col = first_existing_col(df, ["lon", "raw_lon", "matched_lon", "x"])

    if lat_col is not None and lat_col != "lat":
        df["lat"] = df[lat_col]
    if lon_col is not None and lon_col != "lon":
        df["lon"] = df[lon_col]

    if "lat" not in df.columns:
        df["lat"] = pd.NA
    if "lon" not in df.columns:
        df["lon"] = pd.NA

    df["target_dist_m"] = pd.to_numeric(df["target_dist_m"], errors="coerce")

    return df


def load_waypoint_csv(path: Path, source_kind: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing {source_kind} waypoint CSV: {path}")

    df = pd.read_csv(path, encoding="utf-8-sig")
    df = normalize_waypoint_schema(df, source_kind)
    df = df.dropna(subset=["target_dist_m"]).copy()

    return df


def pick_representative(group: pd.DataFrame) -> pd.Series:
    temp = group.copy()
    temp["_priority"] = temp["waypoint_type"].apply(waypoint_priority)
    temp["_source_sort"] = temp["source_kind"].map({"risk": 0, "scenic": 1}).fillna(9)

    temp = temp.sort_values(
        ["_priority", "_source_sort", "target_dist_m"],
        ascending=[True, True, True],
    )

    return temp.iloc[0].copy()


def merge_group(group_id: int, group: pd.DataFrame) -> dict[str, Any]:
    rep = pick_representative(group)

    risk_rows = group[group["source_kind"] == "risk"]
    scenic_rows = group[group["source_kind"] == "scenic"]

    all_types = join_unique(group["waypoint_type"].tolist())
    risk_types = join_unique(risk_rows["waypoint_type"].tolist()) if not risk_rows.empty else ""
    scenic_types = join_unique(scenic_rows["waypoint_type"].tolist()) if not scenic_rows.empty else ""

    names = join_unique(group["name"].tolist(), sep="; ")
    reasons = join_unique(group["reason"].tolist(), sep="; ")
    source_layers = join_unique(group["source_layer"].tolist())

    offset_vals = pd.to_numeric(
        group.get("nearest_route_offset_m", pd.Series(dtype=float)),
        errors="coerce",
    ).dropna()
    min_offset = float(offset_vals.min()) if not offset_vals.empty else pd.NA

    # Prefer risk distance if available; otherwise representative distance.
    if not risk_rows.empty:
        target_dist_m = float(risk_rows["target_dist_m"].median())
    else:
        target_dist_m = float(rep["target_dist_m"])

    lat_vals = pd.to_numeric(group.get("lat", pd.Series(dtype=float)), errors="coerce").dropna()
    lon_vals = pd.to_numeric(group.get("lon", pd.Series(dtype=float)), errors="coerce").dropna()

    lat = float(lat_vals.iloc[0]) if not lat_vals.empty else pd.NA
    lon = float(lon_vals.iloc[0]) if not lon_vals.empty else pd.NA

    out = {
        "case_id": CASE_ID,
        "model_version": MODEL_VERSION,
        "combined_waypoint_id": f"CWP{group_id:02d}",
        "primary_waypoint_id": rep.get("waypoint_id", ""),
        "primary_source_kind": rep.get("source_kind", ""),
        "target_dist_m": round(target_dist_m, 3),
        "waypoint_type": all_types,
        "risk_waypoint_type": risk_types,
        "scenic_waypoint_type": scenic_types,
        "name": names,
        "reason": reasons,
        "source_layers": source_layers,
        "nearest_route_offset_m": min_offset,
        "contains_risk_waypoint": int(not risk_rows.empty),
        "contains_scenic_waypoint": int(not scenic_rows.empty),
        "merged_source_count": int(len(group)),
        "source_waypoint_ids": join_unique(group["waypoint_id"].tolist()),
        "lat": lat,
        "lon": lon,
    }

    # Preserve all source records as compact JSON for traceability.
    trace_cols = [
        c for c in [
            "waypoint_id",
            "source_kind",
            "waypoint_type",
            "target_dist_m",
            "name",
            "reason",
            "source_layer",
            "nearest_route_offset_m",
            "confidence",
        ]
        if c in group.columns
    ]
    out["source_records_json"] = json.dumps(
        group[trace_cols].to_dict(orient="records"),
        ensure_ascii=False,
    )

    return out


def assign_merge_groups(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("target_dist_m").reset_index(drop=True).copy()

    group_ids: list[int] = []
    current_group = 1
    group_start_dist: float | None = None

    for _, row in df.iterrows():
        dist = float(row["target_dist_m"])

        if group_start_dist is None:
            group_start_dist = dist
            group_ids.append(current_group)
            continue

        if abs(dist - group_start_dist) <= MERGE_DISTANCE_M:
            group_ids.append(current_group)
        else:
            current_group += 1
            group_start_dist = dist
            group_ids.append(current_group)

    df["merge_group_id"] = group_ids
    return df


def export_geojson(df: pd.DataFrame, out_fp: Path) -> None:
    valid = df.dropna(subset=["lat", "lon"]).copy()

    if valid.empty:
        print("No lat/lon columns available; skip combined GeoJSON.")
        return

    valid["lat"] = pd.to_numeric(valid["lat"], errors="coerce")
    valid["lon"] = pd.to_numeric(valid["lon"], errors="coerce")
    valid = valid.dropna(subset=["lat", "lon"])

    if valid.empty:
        print("No valid lat/lon values; skip combined GeoJSON.")
        return

    gdf = gpd.GeoDataFrame(
        valid,
        geometry=[
            Point(lon, lat)
            for lon, lat in zip(valid["lon"], valid["lat"])
        ],
        crs="EPSG:4326",
    )

    gdf.to_file(out_fp, driver="GeoJSON")
    print(f"combined GeoJSON: {out_fp}")


def write_summary(
    risk_df: pd.DataFrame,
    scenic_df: pd.DataFrame,
    combined_df: pd.DataFrame,
    out_fp: Path,
) -> None:
    lines: list[str] = []

    lines.append(f"case: {CASE_ID}")
    lines.append(f"model_version: {MODEL_VERSION}")
    lines.append(f"merge_distance_m: {MERGE_DISTANCE_M}")
    lines.append("")
    lines.append("--- input counts ---")
    lines.append(f"risk waypoints: {len(risk_df)}")
    lines.append(f"scenic waypoints: {len(scenic_df)}")
    lines.append(f"combined waypoints: {len(combined_df)}")
    lines.append("")
    lines.append("--- combined waypoint type ---")
    if "waypoint_type" in combined_df.columns:
        vc = combined_df["waypoint_type"].value_counts(dropna=False)
        lines.extend([f"{idx}: {cnt}" for idx, cnt in vc.items()])
    lines.append("")
    lines.append("--- source mix ---")
    lines.append(f"risk only: {int(((combined_df['contains_risk_waypoint'] == 1) & (combined_df['contains_scenic_waypoint'] == 0)).sum())}")
    lines.append(f"scenic only: {int(((combined_df['contains_risk_waypoint'] == 0) & (combined_df['contains_scenic_waypoint'] == 1)).sum())}")
    lines.append(f"risk + scenic: {int(((combined_df['contains_risk_waypoint'] == 1) & (combined_df['contains_scenic_waypoint'] == 1)).sum())}")

    out_fp.write_text("\n".join(lines), encoding="utf-8")
    print(f"summary TXT: {out_fp}")


# =========================================================
# 2. Main
# =========================================================

def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)

    print(f"case: {CASE_ID}")
    print(f"model_version: {MODEL_VERSION}")
    print(f"risk waypoint CSV: {RISK_WAYPOINT_CSV}")
    print(f"scenic waypoint CSV: {SCENIC_WAYPOINT_CSV}")

    risk_df = load_waypoint_csv(RISK_WAYPOINT_CSV, "risk")
    scenic_df = load_waypoint_csv(SCENIC_WAYPOINT_CSV, "scenic")

    all_df = pd.concat([risk_df, scenic_df], ignore_index=True)
    all_df = all_df.dropna(subset=["target_dist_m"]).copy()

    grouped_input = assign_merge_groups(all_df)

    rows = []
    for group_id, group in grouped_input.groupby("merge_group_id", sort=True):
        rows.append(merge_group(int(group_id), group))

    combined_df = pd.DataFrame(rows)
    combined_df = combined_df.sort_values("target_dist_m").reset_index(drop=True)

    # Re-number after sorting.
    combined_df["combined_waypoint_id"] = [
        f"CWP{i + 1:02d}"
        for i in range(len(combined_df))
    ]

    combined_df.to_csv(COMBINED_CSV, index=False, encoding="utf-8-sig")
    print(f"combined CSV: {COMBINED_CSV}")

    export_geojson(combined_df, COMBINED_GEOJSON)

    write_summary(risk_df, scenic_df, combined_df, SUMMARY_TXT)

    print("")
    print("完成！")
    print(f"combined waypoints: {len(combined_df)}")
    print("")
    print("--- source mix ---")
    print(
        combined_df[
            [
                "combined_waypoint_id",
                "target_dist_m",
                "waypoint_type",
                "name",
                "contains_risk_waypoint",
                "contains_scenic_waypoint",
                "merged_source_count",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
