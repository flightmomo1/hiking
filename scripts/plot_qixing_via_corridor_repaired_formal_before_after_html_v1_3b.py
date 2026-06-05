from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd


CASE_ID = "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b"
ROUTE_FOLDER = "qixing_lengshuikeng"
ACTIVITY_IDS = ["37_1", "33_1", "15_1"]

VIA_UP = {"label": "via_up", "lat": 25.165082087184047, "lon": 121.55966911100028}
VIA_DOWN = {"label": "via_down", "lat": 25.16487469519971, "lon": 121.55963745345083}
CORRIDOR_START_M = 305.0
CORRIDOR_END_M = 3721.0
ORDER_MARKER_INTERVAL_M = 250.0

PREVIOUS_PROFILE = Path("outputs/ib1_route_profile_v1_3b_contract_qa") / CASE_ID / f"{CASE_ID}_route_profile.csv"
REPAIRED_PROFILE = Path("outputs/ib1_route_profile_v1_3b_qixing_via_corridor_repaired_formal") / CASE_ID / f"{CASE_ID}_route_profile.csv"
CANDIDATE_PROFILE = Path("outputs/ib1_route_profile_v1_3b_qixing_via_corridor_repair_candidate") / CASE_ID / f"{CASE_ID}_route_profile.csv"

PREVIOUS_SEQUENCE_ROOT = Path("outputs/ib3a_sequence_mapmatched_activity_v1_3b_thci_v1_0c") / ROUTE_FOLDER
PREVIOUS_A2_ROOT = Path("outputs/ib3a2_on_route_activity_filter_v1_3b_thci_v1_0c") / ROUTE_FOLDER
REPAIRED_SEQUENCE_ROOT = Path("outputs/ib3a_sequence_mapmatched_activity_v1_3b_qixing_via_corridor_repaired_formal") / ROUTE_FOLDER
REPAIRED_A2_ROOT = Path("outputs/ib3a2_on_route_activity_filter_v1_3b_qixing_via_corridor_repaired_formal") / ROUTE_FOLDER
CANDIDATE_SEQUENCE_ROOT = Path("outputs/ib3a_sequence_mapmatched_activity_v1_3b_qixing_via_corridor_repair_candidate") / ROUTE_FOLDER
CANDIDATE_A2_ROOT = Path("outputs/ib3a2_on_route_activity_filter_v1_3b_qixing_via_corridor_repair_candidate") / ROUTE_FOLDER

PROMOTION_SUMMARY = Path("outputs/qixing_via_corridor_repair_promotion_gate_v1_3b/qixing_via_corridor_repair_promotion_gate_summary.json")
PRUNING_SUMMARY = Path("outputs/ib0d_trimmed_mainline_v1_3b_qixing_via_corridor_repair_candidate") / CASE_ID / "qixing_via_corridor_pruning_summary.json"
RAWDATA_SUMMARY = Path("outputs/qixing_via_corridor_pruning_activity_rawdata_safety_audit_v1_3b/qixing_pruning_activity_rawdata_safety_summary.json")

OUT_ROOT = Path("outputs/qixing_via_corridor_repaired_formal_visual_review_v1_3b")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def resolve_file(preferred: Path, fallback: Path) -> tuple[Path, str]:
    if preferred.exists():
        return preferred, "repaired_formal"
    if fallback.exists():
        return fallback, "repair_candidate_fallback"
    return preferred, "missing"


def read_profile(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    if "dist_m" not in df.columns:
        raise ValueError(f"Missing dist_m in {path}")
    if not {"lat", "lon"}.issubset(df.columns):
        raise ValueError(f"Missing lat/lon in {path}")
    return df


def read_sequence(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    if not {"lat", "lon", "route_dist_m"}.issubset(df.columns):
        raise ValueError(f"Missing required sequence columns in {path}")
    return df


def read_labeled(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path, low_memory=False)
    return pd.DataFrame()


def labeled_path(root: Path, activity_id: str) -> Path:
    return root / f"{ROUTE_FOLDER}_{activity_id}_mapmatched_activity_labeled.csv"


def sequence_path(root: Path, activity_id: str) -> Path:
    return root / f"{activity_id}_mapmatched.csv"


def bounds_from_frames(frames: list[pd.DataFrame], extra_points: list[dict[str, float]]) -> tuple[float, float, float, float]:
    lats: list[float] = []
    lons: list[float] = []
    for df in frames:
        if df is None or df.empty:
            continue
        lats.extend(pd.to_numeric(df["lat"], errors="coerce").dropna().tolist())
        lons.extend(pd.to_numeric(df["lon"], errors="coerce").dropna().tolist())
    for p in extra_points:
        lats.append(float(p["lat"]))
        lons.append(float(p["lon"]))
    if not lats or not lons:
        raise ValueError("No coordinates available")
    return min(lats), min(lons), max(lats), max(lons)


class SvgProjector:
    def __init__(self, bounds: tuple[float, float, float, float], width: int = 1200, height: int = 880, pad: int = 40):
        min_lat, min_lon, max_lat, max_lon = bounds
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

    def points(self, df: pd.DataFrame) -> str:
        coords = []
        for lat, lon in zip(pd.to_numeric(df["lat"], errors="coerce"), pd.to_numeric(df["lon"], errors="coerce")):
            if pd.isna(lat) or pd.isna(lon):
                continue
            x, y = self.xy(float(lat), float(lon))
            coords.append(f"{x:.2f},{y:.2f}")
        return " ".join(coords)


def tooltip_row(row: pd.Series, fields: list[str]) -> str:
    parts = []
    for field in fields:
        if field in row.index:
            val = row[field]
            if pd.notna(val):
                parts.append(f"{field}: {val}")
    return html.escape("\n".join(parts))


def route_order_markers(df: pd.DataFrame, projector: SvgProjector, cls: str, label_prefix: str) -> str:
    pieces = []
    dist = pd.to_numeric(df["dist_m"], errors="coerce")
    max_dist = float(dist.max())
    targets = list(range(0, int(max_dist) + 1, int(ORDER_MARKER_INTERVAL_M)))
    for target in targets:
        idx = (dist - target).abs().idxmin()
        row = df.loc[idx]
        x, y = projector.xy(float(row["lat"]), float(row["lon"]))
        label = f"{label_prefix} {target}m"
        pieces.append(
            f'<g class="{cls} order-marker"><circle cx="{x:.2f}" cy="{y:.2f}" r="4"><title>{html.escape(label)}</title></circle>'
            f'<text x="{x + 5:.2f}" y="{y - 5:.2f}">{target}</text></g>'
        )
    return "\n".join(pieces)


def route_segment_by_dist(df: pd.DataFrame, start_m: float, end_m: float) -> pd.DataFrame:
    dist = pd.to_numeric(df["dist_m"], errors="coerce")
    return df[dist.between(start_m, end_m, inclusive="both")].copy()


def status_color(state: str) -> str:
    mapping = {
        "on_route_reliable": "#1b9e77",
        "branch_ambiguous_projection": "#d95f02",
        "near_route_low_confidence": "#7570b3",
        "off_route_projection_only": "#d73027",
    }
    return mapping.get(str(state), "#444")


def activity_points(seq: pd.DataFrame, labeled: pd.DataFrame, projector: SvgProjector, cls: str, suffix: str) -> str:
    work = seq.copy()
    if not labeled.empty and "row_index" in work.columns and "row_index" in labeled.columns:
        cols = [c for c in ["row_index", "usable_on_route", "excluded_reason"] if c in labeled.columns]
        work = work.merge(labeled[cols], on="row_index", how="left")
    step = max(1, math.ceil(len(work) / 1600))
    fields = [
        "timestamp_s",
        "route_dist_m",
        "reliable_route_dist_m",
        "route_progress_state",
        "candidate_phase",
        "usable_on_route",
        "offset_m",
    ]
    pieces = []
    for _, row in work.iloc[::step].iterrows():
        lat = pd.to_numeric(row.get("lat"), errors="coerce")
        lon = pd.to_numeric(row.get("lon"), errors="coerce")
        if pd.isna(lat) or pd.isna(lon):
            continue
        x, y = projector.xy(float(lat), float(lon))
        color = status_color(row.get("route_progress_state", ""))
        title = tooltip_row(row, fields)
        pieces.append(
            f'<circle class="{cls} activity-point" cx="{x:.2f}" cy="{y:.2f}" r="2.4" fill="{color}" fill-opacity="0.72">'
            f"<title>{html.escape(suffix)}\n{title}</title></circle>"
        )
    return "\n".join(pieces)


def html_shell(title: str, body: str, summary_panel: str) -> str:
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <title>{html.escape(title)}</title>
  <style>
    body {{ margin: 0; font-family: Arial, 'Microsoft JhengHei', sans-serif; color: #1f2933; background: #f7f8fa; }}
    header {{ padding: 14px 18px; background: #17202a; color: white; }}
    h1 {{ margin: 0; font-size: 20px; font-weight: 650; }}
    .layout {{ display: grid; grid-template-columns: 1fr 360px; gap: 0; min-height: calc(100vh - 54px); }}
    .canvas-wrap {{ padding: 12px; overflow: auto; }}
    .panel {{ padding: 14px; background: white; border-left: 1px solid #d9dee5; overflow: auto; }}
    .panel h2 {{ font-size: 15px; margin: 14px 0 6px; }}
    .panel table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
    .panel td, .panel th {{ border-bottom: 1px solid #edf0f4; padding: 5px 4px; text-align: left; vertical-align: top; }}
    svg {{ background: white; border: 1px solid #d9dee5; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
    .previous-route {{ fill: none; stroke: #d73027; stroke-width: 3.2; stroke-opacity: .8; }}
    .repaired-route {{ fill: none; stroke: #1a9850; stroke-width: 3.0; stroke-opacity: .85; }}
    .removed-segment {{ fill: none; stroke: #7b3294; stroke-width: 7; stroke-opacity: .65; stroke-linecap: round; }}
    .corridor-window {{ fill: #fee08b; fill-opacity: .18; stroke: #fdae61; stroke-dasharray: 6 4; }}
    .marker-start {{ fill: #2c7bb6; }}
    .marker-end {{ fill: #000; }}
    .marker-via-up {{ fill: #fdae61; stroke: #6b3d00; stroke-width: 2; }}
    .marker-via-down {{ fill: #abd9e9; stroke: #13506b; stroke-width: 2; }}
    .order-marker circle {{ fill: white; stroke-width: 2; }}
    .previous-order circle {{ stroke: #d73027; }}
    .repaired-order circle {{ stroke: #1a9850; }}
    .order-marker text {{ font-size: 10px; paint-order: stroke; stroke: white; stroke-width: 3px; fill: #111; }}
    .activity-line-before {{ fill: none; stroke: #984ea3; stroke-width: 1.4; stroke-opacity: .5; }}
    .activity-line-after {{ fill: none; stroke: #ff7f00; stroke-width: 1.4; stroke-opacity: .45; }}
    .activity-point {{ stroke: white; stroke-width: .5; }}
    .legend {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }}
    .legend span {{ display: inline-flex; align-items: center; gap: 4px; font-size: 12px; }}
    .swatch {{ width: 12px; height: 12px; display: inline-block; border-radius: 2px; }}
    label {{ display: block; font-size: 12px; margin: 4px 0; }}
    code {{ font-size: 11px; word-break: break-all; }}
    .small {{ font-size: 12px; line-height: 1.45; }}
  </style>
</head>
<body>
  <header><h1>{html.escape(title)}</h1></header>
  <div class="layout">
    <main class="canvas-wrap">
      {body}
    </main>
    <aside class="panel">
      {summary_panel}
    </aside>
  </div>
  <script>
    function toggleLayer(cls, checked) {{
      document.querySelectorAll('.' + cls).forEach(el => el.style.display = checked ? '' : 'none');
    }}
  </script>
</body>
</html>"""


def marker(projector: SvgProjector, point: dict[str, Any], cls: str) -> str:
    x, y = projector.xy(float(point["lat"]), float(point["lon"]))
    label = point["label"]
    return (
        f'<g class="{cls}"><circle cx="{x:.2f}" cy="{y:.2f}" r="7"><title>{html.escape(label)}</title></circle>'
        f'<text x="{x + 8:.2f}" y="{y - 8:.2f}" style="font-size:13px;fill:#111;paint-order:stroke;stroke:white;stroke-width:3px">{html.escape(label)}</text></g>'
    )


def summary_table(rows: list[tuple[str, Any]]) -> str:
    trs = "\n".join(f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>" for k, v in rows)
    return f"<table>{trs}</table>"


def make_route_review(previous: pd.DataFrame, repaired: pd.DataFrame, promotion: dict[str, Any], pruning: dict[str, Any], repaired_source: str) -> Path:
    corridor_prev = route_segment_by_dist(previous, CORRIDOR_START_M, CORRIDOR_END_M)
    corridor_rep = route_segment_by_dist(repaired, CORRIDOR_START_M, min(CORRIDOR_END_M, float(repaired["dist_m"].max())))
    projector = SvgProjector(bounds_from_frames([previous, repaired], [VIA_UP, VIA_DOWN]))

    corridor_bounds = bounds_from_frames([corridor_prev, corridor_rep], [VIA_UP, VIA_DOWN])
    min_lat, min_lon, max_lat, max_lon = corridor_bounds
    x1, y1 = projector.xy(max_lat, min_lon)
    x2, y2 = projector.xy(min_lat, max_lon)
    rect = f'<rect class="corridor-window" x="{min(x1,x2):.2f}" y="{min(y1,y2):.2f}" width="{abs(x2-x1):.2f}" height="{abs(y2-y1):.2f}"><title>corridor window {CORRIDOR_START_M}-{CORRIDOR_END_M}m</title></rect>'

    removed_svg = []
    for r in pruning.get("prune_ranges_applied", []):
        seg = route_segment_by_dist(previous, float(r["start_dist_m"]), float(r["end_dist_m"]))
        if not seg.empty:
            removed_svg.append(f'<polyline class="removed-segment" points="{projector.points(seg)}"><title>removed {r["start_dist_m"]}-{r["end_dist_m"]}m</title></polyline>')

    start_prev = previous.iloc[0].to_dict() | {"label": "previous start"}
    end_prev = previous.iloc[-1].to_dict() | {"label": "previous end"}
    start_rep = repaired.iloc[0].to_dict() | {"label": "repaired start"}
    end_rep = repaired.iloc[-1].to_dict() | {"label": "repaired end"}

    svg = f"""
<div class="legend">
  <span><i class="swatch" style="background:#d73027"></i>previous formal route</span>
  <span><i class="swatch" style="background:#1a9850"></i>repaired formal route</span>
  <span><i class="swatch" style="background:#7b3294"></i>removed/pruned segment</span>
  <span><i class="swatch" style="background:#fee08b;border:1px solid #fdae61"></i>via corridor window</span>
</div>
<svg viewBox="0 0 {projector.width} {projector.height}" width="{projector.width}" height="{projector.height}" role="img">
  {rect}
  <polyline class="previous-route previous-layer" points="{projector.points(previous)}"><title>previous formal route axis</title></polyline>
  <polyline class="repaired-route repaired-layer" points="{projector.points(repaired)}"><title>repaired formal route axis</title></polyline>
  {' '.join(removed_svg)}
  {marker(projector, VIA_UP, "marker-via-up")}
  {marker(projector, VIA_DOWN, "marker-via-down")}
  {marker(projector, start_prev, "marker-start previous-layer")}
  {marker(projector, end_prev, "marker-end previous-layer")}
  {marker(projector, start_rep, "marker-start repaired-layer")}
  {marker(projector, end_rep, "marker-end repaired-layer")}
  {route_order_markers(previous, projector, "previous-order previous-layer", "previous")}
  {route_order_markers(repaired, projector, "repaired-order repaired-layer", "repaired")}
</svg>"""
    panel = "<h2>Layers</h2>" + "\n".join(
        [
            '<label><input type="checkbox" checked onchange="toggleLayer(\'previous-layer\', this.checked)"> previous formal route</label>',
            '<label><input type="checkbox" checked onchange="toggleLayer(\'repaired-layer\', this.checked)"> repaired formal route</label>',
        ]
    )
    panel += "<h2>Summary</h2>" + summary_table(
        [
            ("previous_route_dist_max_m", f"{float(previous['dist_m'].max()):.6f}"),
            ("repaired_route_dist_max_m", f"{float(repaired['dist_m'].max()):.6f}"),
            ("removed_dist_m", pruning.get("removed_dist_m", "")),
            ("promotion_gate_status", promotion.get("promotion_gate_status", "")),
            ("remap_review_note", promotion.get("remap_review_note", "")),
            ("repaired_source", repaired_source),
            ("thci_recompute_status", "pending"),
        ]
    )
    panel += '<p class="small">Hover route markers and sampled order labels to inspect route order. Purple segments are the pruned ranges from the previous formal axis.</p>'
    path = OUT_ROOT / "qixing_via_corridor_route_before_after_review.html"
    path.write_text(html_shell("Qixing via corridor route before/after review", svg, panel), encoding="utf-8")
    return path


def make_activity_review(activity_id: str, previous: pd.DataFrame, repaired: pd.DataFrame, promotion: dict[str, Any], repaired_source: str) -> Path:
    repaired_seq_path, seq_source = resolve_file(sequence_path(REPAIRED_SEQUENCE_ROOT, activity_id), sequence_path(CANDIDATE_SEQUENCE_ROOT, activity_id))
    repaired_labeled_path, a2_source = resolve_file(labeled_path(REPAIRED_A2_ROOT, activity_id), labeled_path(CANDIDATE_A2_ROOT, activity_id))
    previous_seq_path = sequence_path(PREVIOUS_SEQUENCE_ROOT, activity_id)
    previous_labeled_path = labeled_path(PREVIOUS_A2_ROOT, activity_id)
    prev_seq = read_sequence(previous_seq_path)
    rep_seq = read_sequence(repaired_seq_path)
    prev_labeled = read_labeled(previous_labeled_path)
    rep_labeled = read_labeled(repaired_labeled_path)

    projector = SvgProjector(bounds_from_frames([previous, repaired, prev_seq, rep_seq], [VIA_UP, VIA_DOWN]))
    corridor = route_segment_by_dist(previous, CORRIDOR_START_M, CORRIDOR_END_M)
    min_lat, min_lon, max_lat, max_lon = bounds_from_frames([corridor], [VIA_UP, VIA_DOWN])
    x1, y1 = projector.xy(max_lat, min_lon)
    x2, y2 = projector.xy(min_lat, max_lon)
    rect = f'<rect class="corridor-window" x="{min(x1,x2):.2f}" y="{min(y1,y2):.2f}" width="{abs(x2-x1):.2f}" height="{abs(y2-y1):.2f}"><title>corridor window</title></rect>'

    svg = f"""
<div class="legend">
  <span><i class="swatch" style="background:#d73027"></i>previous route</span>
  <span><i class="swatch" style="background:#1a9850"></i>repaired route</span>
  <span><i class="swatch" style="background:#984ea3"></i>before activity line</span>
  <span><i class="swatch" style="background:#ff7f00"></i>after activity line</span>
  <span><i class="swatch" style="background:#1b9e77"></i>on_route_reliable</span>
  <span><i class="swatch" style="background:#d95f02"></i>branch_ambiguous</span>
  <span><i class="swatch" style="background:#7570b3"></i>near_route_low_confidence</span>
  <span><i class="swatch" style="background:#d73027"></i>off_route_projection_only</span>
</div>
<svg viewBox="0 0 {projector.width} {projector.height}" width="{projector.width}" height="{projector.height}" role="img">
  {rect}
  <polyline class="previous-route previous-layer" points="{projector.points(previous)}"><title>previous formal route</title></polyline>
  <polyline class="repaired-route repaired-layer" points="{projector.points(repaired)}"><title>repaired route</title></polyline>
  <polyline class="activity-line-before before-activity-layer" points="{projector.points(prev_seq)}"><title>before activity raw GPS line</title></polyline>
  <polyline class="activity-line-after after-activity-layer" points="{projector.points(rep_seq)}"><title>after activity raw GPS line</title></polyline>
  {activity_points(prev_seq, prev_labeled, projector, "before-activity-layer", "before")}
  {activity_points(rep_seq, rep_labeled, projector, "after-activity-layer", "after")}
  {marker(projector, VIA_UP, "marker-via-up")}
  {marker(projector, VIA_DOWN, "marker-via-down")}
  {route_order_markers(previous, projector, "previous-order previous-layer", "previous")}
  {route_order_markers(repaired, projector, "repaired-order repaired-layer", "repaired")}
</svg>"""
    panel = "<h2>Layers</h2>" + "\n".join(
        [
            '<label><input type="checkbox" checked onchange="toggleLayer(\'previous-layer\', this.checked)"> previous route/order</label>',
            '<label><input type="checkbox" checked onchange="toggleLayer(\'repaired-layer\', this.checked)"> repaired route/order</label>',
            '<label><input type="checkbox" checked onchange="toggleLayer(\'before-activity-layer\', this.checked)"> before activity projection</label>',
            '<label><input type="checkbox" checked onchange="toggleLayer(\'after-activity-layer\', this.checked)"> after repaired projection</label>',
        ]
    )
    panel += "<h2>Inputs</h2>" + summary_table(
        [
            ("activity_id", activity_id),
            ("previous_sequence_csv", previous_seq_path),
            ("repaired_sequence_csv", repaired_seq_path),
            ("repaired_sequence_source", seq_source),
            ("repaired_a2_source", a2_source),
            ("promotion_gate_status", promotion.get("promotion_gate_status", "")),
            ("remap_review_note", promotion.get("remap_review_note", "")),
            ("repaired_route_source", repaired_source),
        ]
    )
    panel += '<p class="small">Hover sampled activity points to inspect timestamp, route_dist_m, reliable_route_dist_m, route_progress_state, candidate_phase, and usable_on_route.</p>'
    path = OUT_ROOT / f"qixing_via_corridor_activity_{activity_id}_before_after_review.html"
    path.write_text(html_shell(f"Qixing activity {activity_id} before/after projection review", svg, panel), encoding="utf-8")
    return path


def make_projection_summary(rawdata: dict[str, Any], promotion: dict[str, Any]) -> Path:
    projections = rawdata.get("projection_summaries", [])
    raw_audits = {r.get("activity_id"): r for r in rawdata.get("raw_audits", [])}
    rows = []
    for p in projections:
        activity_id = p.get("activity_id")
        raw = raw_audits.get(activity_id, {})
        rows.append(
            f"<tr><td>{html.escape(str(activity_id))}</td>"
            f"<td>{raw.get('sequence_rows_before')}</td><td>{raw.get('sequence_rows_after')}</td>"
            f"<td>{p.get('on_route_rows_before')}</td><td>{p.get('on_route_rows_after')}</td>"
            f"<td>{p.get('branch_ambiguous_before_rows')}</td><td>{p.get('branch_ambiguous_after_rows')}</td>"
            f"<td>{p.get('off_route_projection_before_rows')}</td><td>{p.get('off_route_projection_after_rows')}</td>"
            f"<td>{p.get('near_route_low_confidence_before_rows')}</td><td>{p.get('near_route_low_confidence_after_rows')}</td>"
            f"<td>{p.get('route_dist_projection_reversal_before_n')}</td><td>{p.get('route_dist_projection_reversal_after_n')}</td>"
            f"<td>{p.get('corridor_reversal_before_n')}</td><td>{p.get('corridor_reversal_after_n')}</td></tr>"
        )
    table = f"""
<table>
  <thead><tr>
    <th>activity</th><th>seq before</th><th>seq after</th><th>on_route before</th><th>on_route after</th>
    <th>branch before</th><th>branch after</th><th>off_route before</th><th>off_route after</th>
    <th>low_conf before</th><th>low_conf after</th><th>total reversal before</th><th>total reversal after</th>
    <th>corridor reversal before</th><th>corridor reversal after</th>
  </tr></thead><tbody>{''.join(rows)}</tbody>
</table>"""
    body = f"""
<section style="background:white;border:1px solid #d9dee5;padding:18px;max-width:1280px">
  <h2>Activity projection before/after summary</h2>
  {table}
  <h2>Decision context</h2>
  {summary_table([
      ("rawdata_safety_status", rawdata.get("final_decision", "")),
      ("promotion_gate_status", promotion.get("promotion_gate_status", "")),
      ("remap_review_note", promotion.get("remap_review_note", "")),
      ("manual_review_required", True),
      ("thci_recompute_status", "pending"),
  ])}
</section>"""
    page = html_shell("Qixing via corridor activity projection summary review", body, "<p class='small'>This summary is read-only visual QA context.</p>")
    path = OUT_ROOT / "qixing_via_corridor_activity_projection_summary_review.html"
    path.write_text(page, encoding="utf-8")
    return path


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    promotion = read_json(PROMOTION_SUMMARY)
    pruning = read_json(PRUNING_SUMMARY)
    rawdata = read_json(RAWDATA_SUMMARY)

    repaired_profile_path, repaired_source = resolve_file(REPAIRED_PROFILE, CANDIDATE_PROFILE)
    previous = read_profile(PREVIOUS_PROFILE)
    repaired = read_profile(repaired_profile_path)

    route_html = make_route_review(previous, repaired, promotion, pruning, repaired_source)
    activity_html_files = []
    for activity_id in ACTIVITY_IDS:
        activity_html_files.append(make_activity_review(activity_id, previous, repaired, promotion, repaired_source))
    summary_html = make_projection_summary(rawdata, promotion)

    summary = {
        "html_files_created": [str(route_html), *[str(p) for p in activity_html_files], str(summary_html)],
        "route_before_after_html": str(route_html),
        "activity_html_files": {activity_id: str(path) for activity_id, path in zip(ACTIVITY_IDS, activity_html_files)},
        "summary_html": str(summary_html),
        "previous_route_dist_max_m": float(previous["dist_m"].max()),
        "repaired_route_dist_max_m": float(repaired["dist_m"].max()),
        "promotion_gate_status": promotion.get("promotion_gate_status", ""),
        "remap_review_note": promotion.get("remap_review_note", ""),
        "thci_recompute_status": "pending",
        "manual_review_required": True,
        "previous_profile_csv": str(PREVIOUS_PROFILE),
        "repaired_profile_csv": str(repaired_profile_path),
        "repaired_profile_source": repaired_source,
        "note": "Read-only before/after visual QA. Existing formal, repaired formal, THCI, raw activity, and standardized roots were not modified.",
        "runtime_llm_allowed": False,
    }
    summary_path = OUT_ROOT / "qixing_via_corridor_repaired_formal_visual_review_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("route_before_after_html=" + str(route_html))
    for activity_id, path in zip(ACTIVITY_IDS, activity_html_files):
        print(f"activity_{activity_id}_html={path}")
    print("summary_html=" + str(summary_html))
    print("summary_json=" + str(summary_path))
    print(f"previous_route_dist_max_m={summary['previous_route_dist_max_m']:.6f}")
    print(f"repaired_route_dist_max_m={summary['repaired_route_dist_max_m']:.6f}")
    print(f"promotion_gate_status={summary['promotion_gate_status']}")
    print(f"repaired_profile_source={repaired_source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
