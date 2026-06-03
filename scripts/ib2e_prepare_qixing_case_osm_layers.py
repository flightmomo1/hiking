# -*- coding: utf-8 -*-
from pathlib import Path
import shutil

import geopandas as gpd
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_OSM_DATASET_ID = "qixing_lengshuikeng_xiaoyoukeng_v1_2_success_20260511"
SOURCE_OSM_DIR = PROJECT_ROOT / "osm_raw_output" / SOURCE_OSM_DATASET_ID
METRIC_CRS = "EPSG:32651"
ROUTE_BUFFER_M = 800.0

CASES = [
    {
        "case_id": "qixing_xiaoyoukeng_main_peak_20260315",
        "case_name": "小油坑七星山主峰 20260315",
    },
    {
        "case_id": "qixing_lengshuikeng_main_peak_20260523",
        "case_name": "冷水坑到七星山主峰 20260523",
    },
]


def ensure_exists(path: Path):
    if not path.exists():
        raise FileNotFoundError(path)


def load_route_buffer(case_id: str):
    route_fp = (
        PROJECT_ROOT
        / "outputs"
        / "ib0d_trimmed_mainline"
        / case_id
        / f"{case_id}_mainline_ordered_path_trimmed.geojson"
    )
    ensure_exists(route_fp)
    route = gpd.read_file(route_fp)
    if route.crs is None:
        route = route.set_crs("EPSG:4326")
    route_metric = route.to_crs(METRIC_CRS)
    return route_metric.geometry.union_all().buffer(ROUTE_BUFFER_M)


def clip_geojson_layer(src_fp: Path, out_fp: Path, route_buffer):
    try:
        gdf = gpd.read_file(src_fp)
    except Exception as exc:
        return {
            "layer": src_fp.name,
            "status": "read_failed",
            "source_features": 0,
            "output_features": 0,
            "note": str(exc),
        }

    if gdf.empty:
        gdf.to_file(out_fp, driver="GeoJSON")
        return {
            "layer": src_fp.name,
            "status": "empty",
            "source_features": 0,
            "output_features": 0,
            "note": "",
        }

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")

    gdf_metric = gdf.to_crs(METRIC_CRS)
    mask = gdf_metric.intersects(route_buffer)
    clipped = gdf.loc[mask.values].copy()

    if clipped.empty:
        clipped = gdf.iloc[0:0].copy()

    clipped.to_file(out_fp, driver="GeoJSON")
    return {
        "layer": src_fp.name,
        "status": "ok",
        "source_features": int(len(gdf)),
        "output_features": int(len(clipped)),
        "note": f"clipped_from={SOURCE_OSM_DATASET_ID};buffer_m={ROUTE_BUFFER_M}",
    }


def copy_non_geojson(src_fp: Path, out_fp: Path):
    shutil.copy2(src_fp, out_fp)
    return {
        "layer": src_fp.name,
        "status": "copied",
        "source_features": "",
        "output_features": "",
        "note": f"copied_from={SOURCE_OSM_DATASET_ID}",
    }


def process_case(case):
    ensure_exists(SOURCE_OSM_DIR)
    case_id = case["case_id"]
    out_dir = PROJECT_ROOT / "osm_raw_output" / case_id
    out_dir.mkdir(parents=True, exist_ok=True)

    route_buffer = load_route_buffer(case_id)
    rows = []

    for src_fp in sorted(SOURCE_OSM_DIR.iterdir()):
        if src_fp.is_dir():
            continue

        out_fp = out_dir / src_fp.name

        if src_fp.suffix.lower() == ".geojson":
            rows.append(clip_geojson_layer(src_fp, out_fp, route_buffer))
        elif src_fp.suffix.lower() in {".csv", ".html"}:
            rows.append(copy_non_geojson(src_fp, out_fp))

    manifest = pd.DataFrame(rows)
    manifest.insert(0, "case_id", case_id)
    manifest.insert(1, "case_name", case["case_name"])
    manifest.insert(2, "source_osm_dataset_id", SOURCE_OSM_DATASET_ID)
    manifest.to_csv(out_dir / f"{case_id}_osm_case_layer_manifest.csv", index=False, encoding="utf-8-sig")

    summary = pd.DataFrame(
        [
            {
                "case_id": case_id,
                "case_name": case["case_name"],
                "source_osm_dataset_id": SOURCE_OSM_DATASET_ID,
                "route_buffer_m": ROUTE_BUFFER_M,
                "layers_total": int(len(manifest)),
                "geojson_layers_ok": int((manifest["status"] == "ok").sum()),
                "geojson_output_features_total": int(
                    pd.to_numeric(manifest["output_features"], errors="coerce").fillna(0).sum()
                ),
            }
        ]
    )
    summary.to_csv(out_dir / f"{case_id}_osm_case_layer_summary.csv", index=False, encoding="utf-8-sig")

    print(
        f"{case_id}: wrote {len(manifest)} layers to {out_dir}; "
        f"features={summary['geojson_output_features_total'].iloc[0]}"
    )


def main():
    for case in CASES:
        process_case(case)


if __name__ == "__main__":
    main()
