# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from shapely.geometry import LineString, MultiLineString

DPI = 150
DEFAULT_MAX_REVIEW_DIST_M = 3000.0
DEFAULT_SCORE_DIST_M = 1000.0
DEFAULT_REVIEW_DIST_M = 1500.0

mpl.rcParams["font.sans-serif"] = [
    "Microsoft JhengHei",
    "Microsoft YaHei",
    "Noto Sans CJK TC",
    "Arial Unicode MS",
    "DejaVu Sans",
]
mpl.rcParams["axes.unicode_minus"] = False


def find_project_root() -> Path:
    here = Path(__file__).resolve()
    for p in [here.parent, *here.parents]:
        if (p / "outputs").exists() or (p / "activity_input").exists() or (p / "nlsc_raw").exists():
            return p
    # common layout: <root>/scripts/<file>.py
    if here.parent.name.lower() == "scripts":
        return here.parent.parent
    return here.parents[1]


PROJECT_ROOT = find_project_root()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Review-only map for distant NLSC collapse-mask features around a route. "
            "This does not modify IB1G3/IB2 scoring."
        )
    )
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--case-name", default=None)
    parser.add_argument("--hazard-csv", default=None)
    parser.add_argument("--hazard-geojson", default=None)
    parser.add_argument("--collapse-mask-fp", default=None)
    parser.add_argument("--contour-fp", default=None)
    parser.add_argument("--watercourse-fp", default=None)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--score-distance-m", type=float, default=DEFAULT_SCORE_DIST_M)
    parser.add_argument("--review-distance-m", type=float, default=DEFAULT_REVIEW_DIST_M)
    parser.add_argument("--max-distance-m", type=float, default=DEFAULT_MAX_REVIEW_DIST_M)
    parser.add_argument(
        "--assume-layer-crs",
        default="EPSG:3826",
        help="CRS to assign when an input SHP/GeoJSON has no CRS. Default: EPSG:3826.",
    )
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def default_hazard_dir(case_id: str) -> Path:
    return PROJECT_ROOT / "outputs" / "ib1g3_upslope_contributing_area_hazard_proxy" / case_id


def default_hazard_csv(case_id: str) -> Path:
    return default_hazard_dir(case_id) / f"{case_id}_upslope_contributing_area_hazard_proxy.csv"


def default_hazard_geojson(case_id: str) -> Path:
    return default_hazard_dir(case_id) / f"{case_id}_upslope_contributing_area_hazard_proxy.geojson"


def default_out_dir(case_id: str) -> Path:
    return PROJECT_ROOT / "outputs" / "ib1g3_distant_collapse_mask_review" / case_id


def safe_union(geoms):
    try:
        return geoms.union_all()
    except Exception:
        return geoms.unary_union


def read_layer(path: Path | None, metric_crs, assume_layer_crs: str) -> gpd.GeoDataFrame:
    if path is None or not path.exists():
        return gpd.GeoDataFrame(geometry=[], crs=metric_crs)
    try:
        gdf = gpd.read_file(path)
    except Exception as exc:
        print(f"WARNING: failed to read layer: {path} | {exc}")
        return gpd.GeoDataFrame(geometry=[], crs=metric_crs)
    if gdf.empty:
        return gpd.GeoDataFrame(geometry=[], crs=metric_crs)
    if gdf.crs is None:
        gdf = gdf.set_crs(assume_layer_crs)
    return gdf.to_crs(metric_crs)


def load_route(hazard_geojson: Path):
    if not hazard_geojson.exists():
        raise FileNotFoundError(f"Missing hazard GeoJSON: {hazard_geojson}")
    route = gpd.read_file(hazard_geojson)
    if route.empty:
        raise ValueError(f"Hazard GeoJSON is empty: {hazard_geojson}")
    if route.crs is None:
        route = route.set_crs("EPSG:4326")
    metric_crs = route.estimate_utm_crs()
    route_m = route.to_crs(metric_crs)
    route_union = safe_union(route_m.geometry)
    return route_m, route_union, metric_crs


def first_existing_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns and df[col].dropna().astype(str).str.len().gt(0).any():
            return col
    return None


def infer_layer_fp(df: pd.DataFrame, arg_value: str | None, candidates: list[str]) -> Path | None:
    if arg_value:
        return resolve_path(arg_value)
    col = first_existing_col(df, candidates)
    if col is None:
        return None
    values = df[col].dropna().astype(str)
    values = values[values.str.len() > 0]
    if values.empty:
        return None
    return resolve_path(values.iloc[0])


def classify_distance(distance_m: float, score_distance_m: float, review_distance_m: float, max_distance_m: float) -> str:
    if distance_m <= score_distance_m:
        return "score_zone_0_1000m"
    if distance_m <= review_distance_m:
        return "near_review_1000_1500m"
    if distance_m <= max_distance_m:
        return "distant_context_1500_3000m"
    return "outside_review_distance"


def compute_review_table(
    collapse_m: gpd.GeoDataFrame,
    route_union,
    score_distance_m: float,
    review_distance_m: float,
    max_distance_m: float,
) -> gpd.GeoDataFrame:
    if collapse_m.empty:
        return gpd.GeoDataFrame(geometry=[], crs=collapse_m.crs)

    out = collapse_m.copy()
    out["distance_to_route_m"] = out.geometry.distance(route_union)
    out["distance_band"] = out["distance_to_route_m"].map(
        lambda x: classify_distance(float(x), score_distance_m, review_distance_m, max_distance_m)
    )
    out["within_score_distance"] = out["distance_to_route_m"] <= score_distance_m
    out["within_near_review_distance"] = out["distance_to_route_m"] <= review_distance_m
    out["within_max_review_distance"] = out["distance_to_route_m"] <= max_distance_m
    out = out.sort_values("distance_to_route_m").reset_index(drop=True)
    out["review_rank"] = np.arange(1, len(out) + 1)
    return out


def summarize(review: gpd.GeoDataFrame, max_distance_m: float) -> dict:
    summary = {
        "collapse_mask_raw_count": int(len(review)),
        "collapse_mask_within_max_review_distance_count": 0,
        "min_distance_to_route_m": np.nan,
        "within_200m": 0,
        "within_350m": 0,
        "within_500m": 0,
        "within_1000m": 0,
        "within_1500m": 0,
        "within_2000m": 0,
        "within_3000m": 0,
        "nearest_distance_band": "none",
        "nearest_review_flag": "NO_COLLAPSE_MASK_FEATURES",
    }
    if review.empty:
        return summary
    d = pd.to_numeric(review["distance_to_route_m"], errors="coerce")
    summary["min_distance_to_route_m"] = float(d.min())
    summary["collapse_mask_within_max_review_distance_count"] = int((d <= max_distance_m).sum())
    for dist in [200, 350, 500, 1000, 1500, 2000, 3000]:
        summary[f"within_{dist}m"] = int((d <= dist).sum())
    nearest = review.iloc[0]
    summary["nearest_distance_band"] = str(nearest["distance_band"])
    if float(nearest["distance_to_route_m"]) <= 1000:
        summary["nearest_review_flag"] = "COLLAPSE_MASK_WITHIN_SCORE_DISTANCE_RECHECK_SCORING"
    elif float(nearest["distance_to_route_m"]) <= 1500:
        summary["nearest_review_flag"] = "REVIEW_DISTANT_COLLAPSE_MASK_1000_1500M"
    elif float(nearest["distance_to_route_m"]) <= max_distance_m:
        summary["nearest_review_flag"] = "BACKGROUND_DISTANT_COLLAPSE_MASK_1500_3000M"
    else:
        summary["nearest_review_flag"] = "NO_COLLAPSE_MASK_WITHIN_REVIEW_DISTANCE"
    return summary


def add_scale_bar(ax, length_m=500) -> None:
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    x0 = xlim[0] + (xlim[1] - xlim[0]) * 0.06
    y0 = ylim[0] + (ylim[1] - ylim[0]) * 0.06
    ax.plot([x0, x0 + length_m], [y0, y0], color="black", lw=3, zorder=30)
    ax.plot([x0, x0], [y0 - 20, y0 + 20], color="black", lw=2, zorder=30)
    ax.plot([x0 + length_m, x0 + length_m], [y0 - 20, y0 + 20], color="black", lw=2, zorder=30)
    ax.text(x0 + length_m / 2, y0 + 35, f"{length_m} m", ha="center", va="bottom", fontsize=9)


def add_north_arrow(ax) -> None:
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    x = xlim[0] + (xlim[1] - xlim[0]) * 0.06
    y = ylim[1] - (ylim[1] - ylim[0]) * 0.12
    ax.annotate(
        "N",
        xy=(x, y + 160),
        xytext=(x, y),
        ha="center",
        fontsize=14,
        arrowprops=dict(arrowstyle="-|>", lw=1.8, color="black"),
    )


def plot_review_map(
    case_name: str,
    route_m: gpd.GeoDataFrame,
    route_union,
    contours: gpd.GeoDataFrame,
    watercourse: gpd.GeoDataFrame,
    review: gpd.GeoDataFrame,
    score_distance_m: float,
    review_distance_m: float,
    max_distance_m: float,
    out_fp: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(13.5, 11), dpi=DPI)

    max_buffer = route_union.buffer(max_distance_m)
    score_buffer = route_union.buffer(score_distance_m)
    near_buffer = route_union.buffer(review_distance_m)

    # Context layers clipped to max review area.
    if not contours.empty:
        sub = contours[contours.intersects(max_buffer)].copy()
        if not sub.empty:
            sub.plot(ax=ax, color="#C4C4C4", linewidth=0.35, alpha=0.55, zorder=1)
            elev_col = next((c for c in ["zv2", "elev", "elevation", "height", "ELEV", "Z"] if c in sub.columns), None)
            if elev_col:
                elev = pd.to_numeric(sub[elev_col], errors="coerce")
                major = sub[elev.fillna(-99999) % 50 == 0]
                if not major.empty:
                    major.plot(ax=ax, color="#8B8B8B", linewidth=0.65, alpha=0.85, zorder=2)

    if not watercourse.empty:
        sub = watercourse[watercourse.intersects(max_buffer)].copy()
        if not sub.empty:
            sub.plot(ax=ax, color="#1976D2", linewidth=1.3, alpha=0.85, zorder=3)

    # Buffer rings.
    gpd.GeoSeries([max_buffer], crs=route_m.crs).boundary.plot(ax=ax, color="#777777", linewidth=1.1, linestyle="--", zorder=4)
    gpd.GeoSeries([near_buffer], crs=route_m.crs).boundary.plot(ax=ax, color="#B26A00", linewidth=1.3, linestyle="--", zorder=5)
    gpd.GeoSeries([score_buffer], crs=route_m.crs).boundary.plot(ax=ax, color="#555555", linewidth=1.3, linestyle=":", zorder=6)

    # Route.
    route_m.plot(ax=ax, color="#1B1B1B", linewidth=3.5, zorder=8)

    # Collapse masks.
    if not review.empty:
        for band, face, edge, alpha in [
            ("score_zone_0_1000m", "#C9252D", "#6E0015", 0.55),
            ("near_review_1000_1500m", "#F28E2B", "#9B4D00", 0.48),
            ("distant_context_1500_3000m", "#8D5A2B", "#5D3218", 0.30),
            ("outside_review_distance", "#BDBDBD", "#777777", 0.15),
        ]:
            sub = review[review["distance_band"] == band]
            if not sub.empty:
                sub.plot(ax=ax, facecolor=face, edgecolor=edge, alpha=alpha, linewidth=0.8, zorder=7)

        # Label nearest few features within max distance.
        label_rows = review[review["distance_to_route_m"] <= max_distance_m].head(5)
        for _, row in label_rows.iterrows():
            pt = row.geometry.representative_point()
            ax.text(
                pt.x,
                pt.y,
                f"#{int(row['review_rank'])}\n{float(row['distance_to_route_m']):.0f}m",
                fontsize=8,
                ha="center",
                va="center",
                color="#3A2112",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#9B4D00", alpha=0.75),
                zorder=10,
            )

    minx, miny, maxx, maxy = max_buffer.bounds
    padx = max((maxx - minx) * 0.03, 120)
    pady = max((maxy - miny) * 0.03, 120)
    ax.set_xlim(minx - padx, maxx + padx)
    ax.set_ylim(miny - pady, maxy + pady)
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(
        f"{case_name}\nDistant collapse-mask review-only map",
        fontsize=16,
        weight="bold",
    )
    ax.set_xlabel("Metric coordinate")
    ax.set_ylabel("Metric coordinate")
    ax.grid(color="#ECECEC", linewidth=0.6)
    add_scale_bar(ax, length_m=500)
    add_north_arrow(ax)

    handles = [
        Line2D([0], [0], color="#1B1B1B", lw=3.5, label="route"),
        Line2D([0], [0], color="#1976D2", lw=1.8, label="watercourse"),
        Line2D([0], [0], color="#8B8B8B", lw=1.0, label="NLSC contours"),
        Line2D([0], [0], color="#555555", lw=1.3, linestyle=":", label=f"score distance {score_distance_m:.0f}m"),
        Line2D([0], [0], color="#B26A00", lw=1.3, linestyle="--", label=f"near review {review_distance_m:.0f}m"),
        Line2D([0], [0], color="#777777", lw=1.1, linestyle="--", label=f"max review {max_distance_m:.0f}m"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor="#C9252D", markeredgecolor="#6E0015", markersize=10, label="collapse mask <= score distance"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor="#F28E2B", markeredgecolor="#9B4D00", markersize=10, label="collapse mask near review"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor="#8D5A2B", markeredgecolor="#5D3218", markersize=10, label="collapse mask distant context"),
    ]
    ax.legend(handles=handles, loc="upper right", fontsize=8, frameon=True)

    fig.savefig(out_fp, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def write_markdown(case_name: str, summary: dict, review_near: pd.DataFrame, out_fp: Path) -> None:
    lines = [
        f"# {case_name} distant collapse-mask review",
        "",
        "This is a review-only diagnostic. It does not modify IB1G3 or IB2D risk scores.",
        "",
        "## Summary",
        "",
        f"- Collapse mask raw features: {summary['collapse_mask_raw_count']}",
        f"- Minimum distance to route: {summary['min_distance_to_route_m']:.2f} m" if pd.notna(summary['min_distance_to_route_m']) else "- Minimum distance to route: n/a",
        f"- Within 1000 m: {summary['within_1000m']}",
        f"- Within 1500 m: {summary['within_1500m']}",
        f"- Within 3000 m: {summary['within_3000m']}",
        f"- Nearest review flag: `{summary['nearest_review_flag']}`",
        "",
        "## Nearest collapse-mask features within review distance",
        "",
    ]
    if review_near.empty:
        lines.append("No collapse-mask features within the configured review distance.")
    else:
        lines.append("| rank | distance to route m | distance band |")
        lines.append("|---:|---:|---|")
        for _, row in review_near.iterrows():
            lines.append(
                f"| {int(row['review_rank'])} | {float(row['distance_to_route_m']):.2f} | {row['distance_band']} |"
            )
    out_fp.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    case_id = args.case_id
    case_name = args.case_name or case_id

    hazard_csv = resolve_path(args.hazard_csv) if args.hazard_csv else default_hazard_csv(case_id)
    hazard_geojson = resolve_path(args.hazard_geojson) if args.hazard_geojson else default_hazard_geojson(case_id)
    out_dir = resolve_path(args.out_dir) if args.out_dir else default_out_dir(case_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not hazard_csv.exists():
        raise FileNotFoundError(f"Missing hazard CSV: {hazard_csv}")
    if not hazard_geojson.exists():
        raise FileNotFoundError(f"Missing hazard GeoJSON: {hazard_geojson}")

    df = pd.read_csv(hazard_csv, low_memory=False, encoding="utf-8-sig")
    route_m, route_union, metric_crs = load_route(hazard_geojson)

    collapse_fp = infer_layer_fp(df, args.collapse_mask_fp, ["collapse_mask_fp", "landslide_mask_fp"])
    contour_fp = infer_layer_fp(df, args.contour_fp, ["contour_fp", "nlsc_contour_fp"])
    watercourse_fp = infer_layer_fp(df, args.watercourse_fp, ["watercourse_fp", "watrcrs_fp", "watercourse_l_fp"])

    if collapse_fp is None:
        raise KeyError("Cannot infer collapse mask path. Pass --collapse-mask-fp explicitly.")

    collapse_m = read_layer(collapse_fp, metric_crs, args.assume_layer_crs)
    contours = read_layer(contour_fp, metric_crs, args.assume_layer_crs) if contour_fp else gpd.GeoDataFrame(geometry=[], crs=metric_crs)
    watercourse = read_layer(watercourse_fp, metric_crs, args.assume_layer_crs) if watercourse_fp else gpd.GeoDataFrame(geometry=[], crs=metric_crs)

    review = compute_review_table(
        collapse_m,
        route_union,
        args.score_distance_m,
        args.review_distance_m,
        args.max_distance_m,
    )
    summary = summarize(review, args.max_distance_m)
    summary.update(
        {
            "case_id": case_id,
            "case_name": case_name,
            "project_root": str(PROJECT_ROOT),
            "metric_crs": str(metric_crs),
            "hazard_csv": str(hazard_csv),
            "hazard_geojson": str(hazard_geojson),
            "collapse_mask_fp": str(collapse_fp),
            "contour_fp": str(contour_fp) if contour_fp else "",
            "watercourse_fp": str(watercourse_fp) if watercourse_fp else "",
            "score_distance_m": args.score_distance_m,
            "review_distance_m": args.review_distance_m,
            "max_distance_m": args.max_distance_m,
        }
    )

    # Export all features with distance, plus within-max subset for easy review.
    out_all_geojson = out_dir / f"{case_id}_distant_collapse_mask_review_all.geojson"
    out_near_geojson = out_dir / f"{case_id}_distant_collapse_mask_review_within_{int(args.max_distance_m)}m.geojson"
    out_csv = out_dir / f"{case_id}_distant_collapse_mask_review.csv"
    out_summary_csv = out_dir / f"{case_id}_distant_collapse_mask_review_summary.csv"
    out_md = out_dir / f"{case_id}_distant_collapse_mask_review.md"
    out_png = out_dir / f"{case_id}_distant_collapse_mask_review_map.png"

    if not review.empty:
        review.to_file(out_all_geojson, driver="GeoJSON")
        review_near = review[review["distance_to_route_m"] <= args.max_distance_m].copy()
        review_near.to_file(out_near_geojson, driver="GeoJSON")
        review.drop(columns="geometry").to_csv(out_csv, index=False, encoding="utf-8-sig")
    else:
        review_near = review.copy()
        pd.DataFrame().to_csv(out_csv, index=False, encoding="utf-8-sig")

    pd.DataFrame([summary]).to_csv(out_summary_csv, index=False, encoding="utf-8-sig")
    write_markdown(case_name, summary, review_near.drop(columns="geometry") if not review_near.empty else pd.DataFrame(), out_md)
    plot_review_map(
        case_name,
        route_m,
        route_union,
        contours,
        watercourse,
        review,
        args.score_distance_m,
        args.review_distance_m,
        args.max_distance_m,
        out_png,
    )

    print("DONE")
    for key, value in summary.items():
        print(f"{key}: {value}")
    print(f"review_count_within_{int(args.max_distance_m)}m: {len(review_near)}")
    print("review_csv:", out_csv)
    print("review_md:", out_md)
    print("review_map_png:", out_png)
    print("review_all_geojson:", out_all_geojson if not review.empty else "")
    print("review_near_geojson:", out_near_geojson if not review_near.empty else "")
    print("summary_csv:", out_summary_csv)


if __name__ == "__main__":
    main()
