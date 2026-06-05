from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd


ROUTE_FOLDER = "qixing_lengshuikeng"
CASE_ID = "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b"
ACTIVITY_IDS = ["37_1", "33_1", "15_1"]

STANDARDIZED_ROOT = Path("outputs/activity_standardized")
SEQUENCE_ROOT = Path("outputs/ib3a_sequence_mapmatched_activity_v1_3b_qixing_via_corridor_repair_candidate")
IB3A2_ROOT = Path("outputs/ib3a2_on_route_activity_filter_v1_3b_qixing_via_corridor_repair_candidate")
ROUTE_PROFILE_ROOT = Path("outputs/ib1_route_profile_v1_3b_qixing_via_corridor_repair_candidate")
CORRIDOR_CSV = Path("configs/risk_semantics/qixing_branch_corridor_definition_v1_3b.csv")
OUT_ROOT = Path("outputs/ib3_raw_gps_vs_projected_route_choice_qa_v1_3b_qixing_repaired_review")

VIA_UP = {"label": "via_up", "lat": 25.165082087184047, "lon": 121.55966911100028}
VIA_DOWN = {"label": "via_down", "lat": 25.16487469519971, "lon": 121.55963745345083}
SUMMIT = {"label": "summit", "lat": 25.17069791627356, "lon": 121.5534529370406, "dist_m": 1919.0}

ROUTE_ORDER_MARKER_INTERVAL_M = 250
PASS_RADIUS_STRICT_M = 30
PASS_RADIUS_REVIEW_M = 50

CORRIDOR_COLOR = {
    "via_up_corridor": "#1b9e77",
    "via_down_corridor": "#d95f02",
    "summit_shared_ascent": "#7570b3",
    "summit_shared_descent": "#66a61e",
    "via_up_ambiguous_window": "#e7298a",
    "via_down_ambiguous_window": "#a6761d",
}


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False)


def haversine_m(lat1: pd.Series, lon1: pd.Series, lat2: float, lon2: float) -> pd.Series:
    r = 6371008.8
    lat1r = pd.to_numeric(lat1, errors="coerce").map(math.radians)
    lon1r = pd.to_numeric(lon1, errors="coerce").map(math.radians)
    lat2r = math.radians(lat2)
    lon2r = math.radians(lon2)
    dlat = lat2r - lat1r
    dlon = lon2r - lon1r
    a = (dlat / 2).map(lambda x: math.sin(x) ** 2) + lat1r.map(math.cos) * math.cos(lat2r) * (dlon / 2).map(lambda x: math.sin(x) ** 2)
    return 2 * r * a.map(lambda x: math.asin(math.sqrt(x)) if pd.notna(x) else math.nan)


def activity_paths(activity_id: str) -> dict[str, Path]:
    return {
        "standardized": STANDARDIZED_ROOT / ROUTE_FOLDER / f"{activity_id}_standardized.csv",
        "sequence": SEQUENCE_ROOT / ROUTE_FOLDER / f"{activity_id}_mapmatched.csv",
        "labeled": IB3A2_ROOT / ROUTE_FOLDER / f"{ROUTE_FOLDER}_{activity_id}_mapmatched_activity_labeled.csv",
    }


def route_profile_path() -> Path:
    return ROUTE_PROFILE_ROOT / CASE_ID / f"{CASE_ID}_route_profile.csv"


def sort_time(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in ["elapsed_sec", "timestamp_s", "source_row_index", "row_index"] if c in df.columns]
    return df.sort_values(cols, kind="stable").copy() if cols else df.copy()


def route_points_for_sequence(seq: pd.DataFrame, route: pd.DataFrame) -> pd.DataFrame:
    route_dist = pd.to_numeric(route["dist_m"], errors="coerce")
    out_rows = []
    for _, row in sort_time(seq).iterrows():
        dist = row.get("route_dist_m", row.get("reliable_route_dist_m", None))
        if pd.isna(dist):
            continue
        idx = (route_dist - float(dist)).abs().idxmin()
        r = route.loc[idx]
        merged = row.to_dict()
        merged["projected_lat"] = r["lat"]
        merged["projected_lon"] = r["lon"]
        merged["projected_route_profile_dist_m"] = r["dist_m"]
        out_rows.append(merged)
    return pd.DataFrame(out_rows)


class Projector:
    def __init__(self, frames: list[pd.DataFrame], points: list[dict[str, Any]], width: int = 1200, height: int = 860, pad: int = 42):
        lats: list[float] = []
        lons: list[float] = []
        for df in frames:
            for lat_col, lon_col in [("lat", "lon"), ("projected_lat", "projected_lon")]:
                if {lat_col, lon_col}.issubset(df.columns):
                    lats.extend(pd.to_numeric(df[lat_col], errors="coerce").dropna().tolist())
                    lons.extend(pd.to_numeric(df[lon_col], errors="coerce").dropna().tolist())
        for p in points:
            lats.append(float(p["lat"]))
            lons.append(float(p["lon"]))
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        lat_pad = max((max_lat - min_lat) * 0.08, 0.0001)
        lon_pad = max((max_lon - min_lon) * 0.08, 0.0001)
        self.min_lat = min_lat - lat_pad
        self.max_lat = max_lat + lat_pad
        self.min_lon = min_lon - lon_pad
        self.max_lon = max_lon + lon_pad
        self.width = width
        self.height = height
        self.pad = pad

    def xy(self, lat: float, lon: float) -> tuple[float, float]:
        x = self.pad + (lon - self.min_lon) / (self.max_lon - self.min_lon) * (self.width - 2 * self.pad)
        y = self.pad + (self.max_lat - lat) / (self.max_lat - self.min_lat) * (self.height - 2 * self.pad)
        return x, y

    def points(self, df: pd.DataFrame, lat_col: str = "lat", lon_col: str = "lon") -> str:
        pts = []
        for lat, lon in zip(pd.to_numeric(df[lat_col], errors="coerce"), pd.to_numeric(df[lon_col], errors="coerce")):
            if pd.isna(lat) or pd.isna(lon):
                continue
            x, y = self.xy(float(lat), float(lon))
            pts.append(f"{x:.2f},{y:.2f}")
        return " ".join(pts)


def svg_marker(projector: Projector, point: dict[str, Any], cls: str) -> str:
    x, y = projector.xy(float(point["lat"]), float(point["lon"]))
    label = html.escape(str(point["label"]))
    return f'<g class="{cls}"><circle cx="{x:.2f}" cy="{y:.2f}" r="7"><title>{label}</title></circle><text x="{x+9:.2f}" y="{y-8:.2f}">{label}</text></g>'


def tooltip(row: pd.Series) -> str:
    fields = [
        "timestamp_s",
        "elapsed_sec",
        "lat",
        "lon",
        "route_dist_m",
        "reliable_route_dist_m",
        "route_progress_state",
        "candidate_phase",
        "offset_m",
        "nearest_corridor",
    ]
    return html.escape("\n".join(f"{f}: {row[f]}" for f in fields if f in row.index and pd.notna(row[f])))


def classify_nearest_corridor(seq: pd.DataFrame) -> pd.DataFrame:
    out = seq.copy()
    out["dist_to_via_up_m"] = haversine_m(out["lat"], out["lon"], VIA_UP["lat"], VIA_UP["lon"])
    out["dist_to_via_down_m"] = haversine_m(out["lat"], out["lon"], VIA_DOWN["lat"], VIA_DOWN["lon"])
    out["dist_to_summit_m"] = haversine_m(out["lat"], out["lon"], SUMMIT["lat"], SUMMIT["lon"])
    out["nearest_corridor"] = "none"
    out.loc[out["dist_to_via_up_m"] < out["dist_to_via_down_m"], "nearest_corridor"] = "via_up"
    out.loc[out["dist_to_via_down_m"] <= out["dist_to_via_up_m"], "nearest_corridor"] = "via_down"
    return out


def sampled_points(seq: pd.DataFrame, projector: Projector, cls: str, lat_col: str, lon_col: str, title_prefix: str) -> str:
    step = max(1, math.ceil(len(seq) / 1500))
    pieces = []
    for _, row in seq.iloc[::step].iterrows():
        lat = pd.to_numeric(row.get(lat_col), errors="coerce")
        lon = pd.to_numeric(row.get(lon_col), errors="coerce")
        if pd.isna(lat) or pd.isna(lon):
            continue
        x, y = projector.xy(float(lat), float(lon))
        pieces.append(f'<circle class="{cls}" cx="{x:.2f}" cy="{y:.2f}" r="2.3"><title>{html.escape(title_prefix)}\n{tooltip(row)}</title></circle>')
    return "\n".join(pieces)


def route_order_markers(route: pd.DataFrame, projector: Projector) -> str:
    dist = pd.to_numeric(route["dist_m"], errors="coerce")
    pieces = []
    for target in range(0, int(dist.max()) + 1, ROUTE_ORDER_MARKER_INTERVAL_M):
        idx = (dist - target).abs().idxmin()
        row = route.loc[idx]
        x, y = projector.xy(float(row["lat"]), float(row["lon"]))
        pieces.append(f'<g class="order-marker"><circle cx="{x:.2f}" cy="{y:.2f}" r="4"><title>route_dist_m {target}</title></circle><text x="{x+5:.2f}" y="{y-5:.2f}">{target}</text></g>')
    return "\n".join(pieces)


def corridor_overlays(route: pd.DataFrame, corridors: pd.DataFrame, projector: Projector) -> str:
    dist = pd.to_numeric(route["dist_m"], errors="coerce")
    pieces = []
    for _, corr in corridors.iterrows():
        seg = route[dist.between(float(corr["start_dist_m"]), float(corr["end_dist_m"]), inclusive="both")].copy()
        if seg.empty:
            continue
        color = CORRIDOR_COLOR.get(str(corr["corridor_id"]), "#333")
        dash = ' stroke-dasharray="8 5"' if corr["corridor_role"] != "branch_corridor" else ""
        width = 7 if corr["corridor_role"] == "branch_corridor" else 4
        opacity = 0.85 if corr["corridor_role"] == "branch_corridor" else 0.45
        title = html.escape(f"{corr['corridor_id']}\n{corr['corridor_role']}\n{corr['start_dist_m']}-{corr['end_dist_m']}m\n{corr['review_note']}")
        pieces.append(f'<polyline class="corridor" points="{projector.points(seg)}" fill="none" stroke="{color}" stroke-width="{width}" opacity="{opacity}" stroke-linecap="round"{dash}><title>{title}</title></polyline>')
    return "\n".join(pieces)


def pass_order(df: pd.DataFrame, radius_m: float) -> tuple[bool, list[str]]:
    ordered = sort_time(df)
    events = []
    state = {"via_up": False, "summit": False, "via_down": False}
    for _, row in ordered.iterrows():
        if not state["via_up"] and row.get("dist_to_via_up_m", 1e9) <= radius_m:
            events.append("via_up")
            state["via_up"] = True
        if not state["summit"] and row.get("dist_to_summit_m", 1e9) <= radius_m:
            events.append("summit")
            state["summit"] = True
        if not state["via_down"] and row.get("dist_to_via_down_m", 1e9) <= radius_m:
            events.append("via_down")
            state["via_down"] = True
    canonical = False
    if all(k in events for k in ["via_up", "summit", "via_down"]):
        canonical = events.index("via_up") < events.index("summit") < events.index("via_down")
    return canonical, events


def projected_order(seq: pd.DataFrame, radius_m: float = 50.0) -> tuple[bool, list[str]]:
    ordered = sort_time(seq)
    events = []
    state = {"via_up": False, "summit": False, "via_down": False}
    route_dist = pd.to_numeric(ordered["route_dist_m"], errors="coerce")
    checks = [
        ("via_up", 603.0815753050034),
        ("summit", SUMMIT["dist_m"]),
        ("via_down", 3232.3280006859845),
    ]
    for _, row in ordered.assign(_route_dist=route_dist).iterrows():
        for label, dist_m in checks:
            if not state[label] and pd.notna(row["_route_dist"]) and abs(float(row["_route_dist"]) - dist_m) <= radius_m:
                events.append(label)
                state[label] = True
    canonical = False
    if all(k in events for k in ["via_up", "summit", "via_down"]):
        canonical = events.index("via_up") < events.index("summit") < events.index("via_down")
    return canonical, events


def make_html(activity_id: str, raw: pd.DataFrame, seq: pd.DataFrame, projected: pd.DataFrame, route: pd.DataFrame, corridors: pd.DataFrame, summary: dict[str, Any], out_html: Path) -> None:
    projector = Projector([raw, seq, projected, route], [VIA_UP, VIA_DOWN, SUMMIT])
    raw_sorted = sort_time(raw)
    seq_sorted = sort_time(seq)
    projected_sorted = sort_time(projected)

    raw_start = raw_sorted.iloc[0].to_dict() | {"label": "raw_start"}
    raw_end = raw_sorted.iloc[-1].to_dict() | {"label": "raw_end"}
    proj_start = {"label": "projected_start", "lat": projected_sorted.iloc[0]["projected_lat"], "lon": projected_sorted.iloc[0]["projected_lon"]}
    proj_end = {"label": "projected_end", "lat": projected_sorted.iloc[-1]["projected_lat"], "lon": projected_sorted.iloc[-1]["projected_lon"]}

    panel_rows = "".join(f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>" for k, v in summary.items())
    body = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>Qixing raw GPS vs projected route QA {html.escape(activity_id)}</title>
<style>
body {{ margin:0; font-family:Arial,'Microsoft JhengHei',sans-serif; background:#f7f8fb; color:#1f2933; }}
header {{ background:#17202a; color:white; padding:14px 18px; }}
.layout {{ display:grid; grid-template-columns:1fr 380px; min-height:calc(100vh - 54px); }}
.canvas {{ padding:12px; overflow:auto; }}
.panel {{ background:white; border-left:1px solid #d9dee5; padding:14px; overflow:auto; }}
svg {{ background:white; border:1px solid #d9dee5; box-shadow:0 1px 3px rgba(0,0,0,.08); }}
.route-axis {{ fill:none; stroke:#111827; stroke-width:2; stroke-opacity:.45; }}
.raw-line {{ fill:none; stroke:#2563eb; stroke-width:2.2; stroke-opacity:.75; }}
.projected-line {{ fill:none; stroke:#f97316; stroke-width:2.2; stroke-opacity:.75; }}
.raw-point {{ fill:#2563eb; fill-opacity:.55; stroke:white; stroke-width:.5; }}
.projected-point {{ fill:#f97316; fill-opacity:.5; stroke:white; stroke-width:.5; }}
.marker circle {{ stroke:#111; stroke-width:1.5; }}
.via-up circle {{ fill:#1b9e77; }}
.via-down circle {{ fill:#d95f02; }}
.summit circle {{ fill:#7570b3; }}
.raw-start circle {{ fill:#16a34a; }}
.raw-end circle {{ fill:#dc2626; }}
.projected-start circle {{ fill:#a7f3d0; }}
.projected-end circle {{ fill:#fecaca; }}
.marker text,.order-marker text {{ font-size:11px; fill:#111; paint-order:stroke; stroke:white; stroke-width:3px; }}
.order-marker circle {{ fill:white; stroke:#111; stroke-width:1.3; }}
table {{ width:100%; border-collapse:collapse; font-size:12px; }}
th,td {{ border-bottom:1px solid #edf0f4; padding:5px 4px; text-align:left; vertical-align:top; }}
.legend span {{ display:inline-flex; align-items:center; gap:4px; margin:3px 8px 3px 0; font-size:12px; }}
.swatch {{ width:12px; height:12px; display:inline-block; }}
</style>
</head>
<body>
<header><h1>Qixing raw GPS vs projected route-choice QA - {html.escape(activity_id)}</h1></header>
<div class="layout">
<main class="canvas">
<div class="legend">
<span><i class="swatch" style="background:#2563eb"></i>raw GPS timestamp line</span>
<span><i class="swatch" style="background:#f97316"></i>projected route-profile line</span>
<span><i class="swatch" style="background:#111827"></i>repaired candidate route axis</span>
</div>
<svg viewBox="0 0 {projector.width} {projector.height}" width="{projector.width}" height="{projector.height}">
<polyline class="route-axis" points="{projector.points(route)}"><title>repaired candidate route axis</title></polyline>
{corridor_overlays(route, corridors, projector)}
<polyline class="raw-line" points="{projector.points(raw_sorted)}"><title>raw GPS trajectory in timestamp order</title></polyline>
<polyline class="projected-line" points="{projector.points(projected_sorted, 'projected_lat', 'projected_lon')}"><title>projected/mapmatched trajectory by timestamp order on route profile</title></polyline>
{sampled_points(seq_sorted, projector, 'raw-point', 'lat', 'lon', 'raw GPS')}
{sampled_points(projected_sorted.rename(columns={'projected_lat':'_plat','projected_lon':'_plon'}), projector, 'projected-point', '_plat', '_plon', 'projected')}
{route_order_markers(route, projector)}
{svg_marker(projector, VIA_UP, 'marker via-up')}
{svg_marker(projector, VIA_DOWN, 'marker via-down')}
{svg_marker(projector, SUMMIT, 'marker summit')}
{svg_marker(projector, raw_start, 'marker raw-start')}
{svg_marker(projector, raw_end, 'marker raw-end')}
{svg_marker(projector, proj_start, 'marker projected-start')}
{svg_marker(projector, proj_end, 'marker projected-end')}
</svg>
</main>
<aside class="panel">
<h2>Summary</h2>
<table>{panel_rows}</table>
<p>Review goal: confirm whether raw GPS itself follows canonical via_up → summit → via_down order, or whether projection/mapmatch imposes that route order.</p>
</aside>
</div>
</body>
</html>"""
    out_html.write_text(body, encoding="utf-8")


def analyze_activity(activity_id: str, route: pd.DataFrame, corridors: pd.DataFrame) -> tuple[dict[str, Any], Path]:
    paths = activity_paths(activity_id)
    raw = classify_nearest_corridor(read_csv(paths["standardized"]))
    seq = classify_nearest_corridor(read_csv(paths["sequence"]))
    projected = route_points_for_sequence(seq, route)

    raw_canonical, raw_events = pass_order(raw, PASS_RADIUS_REVIEW_M)
    projection_canonical, projection_events = projected_order(seq, PASS_RADIUS_REVIEW_M)
    raw_via_up_30 = int((raw["dist_to_via_up_m"] <= PASS_RADIUS_STRICT_M).sum())
    raw_via_down_30 = int((raw["dist_to_via_down_m"] <= PASS_RADIUS_STRICT_M).sum())
    raw_via_up_50 = int((raw["dist_to_via_up_m"] <= PASS_RADIUS_REVIEW_M).sum())
    raw_via_down_50 = int((raw["dist_to_via_down_m"] <= PASS_RADIUS_REVIEW_M).sum())
    raw_summit_50 = int((raw["dist_to_summit_m"] <= PASS_RADIUS_REVIEW_M).sum())

    offset = pd.to_numeric(seq.get("offset_m"), errors="coerce")
    raw_passes_required = raw_via_up_50 > 0 and raw_via_down_50 > 0 and raw_summit_50 > 0
    raw_projection_order_mismatch = bool((not raw_passes_required or not raw_canonical) and projection_canonical)
    review_required = bool(raw_projection_order_mismatch or not raw_canonical or not projection_canonical)
    summary = {
        "activity_id": activity_id,
        "raw_points_n": int(len(raw)),
        "projected_points_n": int(len(projected)),
        "raw_start_lat": float(raw.iloc[0]["lat"]),
        "raw_start_lon": float(raw.iloc[0]["lon"]),
        "raw_end_lat": float(raw.iloc[-1]["lat"]),
        "raw_end_lon": float(raw.iloc[-1]["lon"]),
        "projected_route_dist_max_m": float(pd.to_numeric(seq["route_dist_m"], errors="coerce").max()),
        "raw_to_projected_offset_median": float(offset.median()) if offset.notna().any() else None,
        "raw_to_projected_offset_p90": float(offset.quantile(0.90)) if offset.notna().any() else None,
        "raw_gps_passes_via_up_30m": raw_via_up_30,
        "raw_gps_passes_via_down_30m": raw_via_down_30,
        "raw_gps_passes_via_up_50m": raw_via_up_50,
        "raw_gps_passes_via_down_50m": raw_via_down_50,
        "raw_gps_passes_summit_50m": raw_summit_50,
        "raw_gps_canonical_order_detected": raw_canonical,
        "projection_canonical_order_detected": projection_canonical,
        "raw_projection_order_mismatch_flag": raw_projection_order_mismatch,
        "review_required": review_required,
        "raw_order_events": " -> ".join(raw_events),
        "projection_order_events": " -> ".join(projection_events),
    }
    out_html = OUT_ROOT / f"qixing_raw_vs_projected_{activity_id}.html"
    make_html(activity_id, raw, seq, projected, route, corridors, summary, out_html)
    return summary, out_html


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    route = read_csv(route_profile_path())
    corridors = read_csv(CORRIDOR_CSV)
    rows = []
    html_files = {}
    for activity_id in ACTIVITY_IDS:
        summary, out_html = analyze_activity(activity_id, route, corridors)
        rows.append(summary)
        html_files[activity_id] = str(out_html)

    summary_csv = OUT_ROOT / "qixing_raw_vs_projected_route_choice_summary.csv"
    summary_json = OUT_ROOT / "qixing_raw_vs_projected_route_choice_qa_summary.json"
    pd.DataFrame(rows).to_csv(summary_csv, index=False, encoding="utf-8-sig")
    payload = {
        "case_id": CASE_ID,
        "route_folder": ROUTE_FOLDER,
        "activity_ids": ACTIVITY_IDS,
        "input_roots": {
            "standardized_root": str(STANDARDIZED_ROOT),
            "sequence_root": str(SEQUENCE_ROOT),
            "ib3a2_root": str(IB3A2_ROOT),
            "route_profile_root": str(ROUTE_PROFILE_ROOT),
            "corridor_definition_csv": str(CORRIDOR_CSV),
        },
        "html_files": html_files,
        "summary_csv": str(summary_csv),
        "control_points": {"via_up": VIA_UP, "via_down": VIA_DOWN, "summit": SUMMIT},
        "summary_rows": rows,
        "note": "Visual QA only. This does not run v2 inference and does not modify route baseline, repaired roots, raw data, THCI, IB0/IB1/IB2D.",
        "runtime_llm_allowed": False,
    }
    summary_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"summary_csv={summary_csv}")
    print(f"summary_json={summary_json}")
    for activity_id, html_path in html_files.items():
        row = next(r for r in rows if r["activity_id"] == activity_id)
        print(
            f"{activity_id}: html={html_path}; raw_canonical={row['raw_gps_canonical_order_detected']}; "
            f"projection_canonical={row['projection_canonical_order_detected']}; "
            f"mismatch={row['raw_projection_order_mismatch_flag']}; review_required={row['review_required']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
