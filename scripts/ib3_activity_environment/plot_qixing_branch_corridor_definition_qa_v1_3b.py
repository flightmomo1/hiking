from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd


CASE_ID = "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b"
CONFIG_CSV = Path("configs/risk_semantics/qixing_branch_corridor_definition_v1_3b.csv")
ROUTE_PROFILE_CSV = (
    Path("outputs/ib1_route_profile_v1_3b_qixing_via_corridor_repair_candidate")
    / CASE_ID
    / f"{CASE_ID}_route_profile.csv"
)
SEMANTIC_CSV = (
    Path("outputs/ib1c_route_profile_semantics_v1_3b_qixing_via_corridor_repair_candidate")
    / CASE_ID
    / f"{CASE_ID}_route_profile_semantic_enriched.csv"
)
OUT_ROOT = Path("outputs/ib3_route_choice_inference_v2_geometry_qixing_repaired_formal_review/corridor_definition_qa")

VIA_UP = {"label": "via_up", "lat": 25.165082087184047, "lon": 121.55966911100028}
VIA_DOWN = {"label": "via_down", "lat": 25.16487469519971, "lon": 121.55963745345083}
SUMMIT_DIST_M = 1919.0
SUMMIT = {"label": "summit", "dist_m": 1919.0, "lat": 25.17069791627356, "lon": 121.5534529370406}
ORDER_MARKER_INTERVAL_M = 250

COLORS = {
    "via_up_corridor": "#1b9e77",
    "via_down_corridor": "#d95f02",
    "summit_shared_ascent": "#7570b3",
    "summit_shared_descent": "#66a61e",
    "via_up_ambiguous_window": "#e7298a",
    "via_down_ambiguous_window": "#a6761d",
}
ROLE_STYLES = {
    "branch_corridor": {"stroke_width": 7, "opacity": 0.9, "dash": ""},
    "shared_corridor": {"stroke_width": 5, "opacity": 0.55, "dash": "8 5"},
    "ambiguous_corridor": {"stroke_width": 12, "opacity": 0.25, "dash": "3 5"},
}


class Projector:
    def __init__(self, df: pd.DataFrame, width: int = 1200, height: int = 880, pad: int = 42):
        min_lat, max_lat = float(df["lat"].min()), float(df["lat"].max())
        min_lon, max_lon = float(df["lon"].min()), float(df["lon"].max())
        for p in [VIA_UP, VIA_DOWN, SUMMIT]:
            min_lat = min(min_lat, float(p["lat"]))
            max_lat = max(max_lat, float(p["lat"]))
            min_lon = min(min_lon, float(p["lon"]))
            max_lon = max(max_lon, float(p["lon"]))
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

    def polyline_points(self, df: pd.DataFrame) -> str:
        pts = []
        for lat, lon in zip(df["lat"], df["lon"]):
            x, y = self.xy(float(lat), float(lon))
            pts.append(f"{x:.2f},{y:.2f}")
        return " ".join(pts)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None]:
    config = pd.read_csv(CONFIG_CSV)
    profile = pd.read_csv(ROUTE_PROFILE_CSV, low_memory=False)
    semantic = pd.read_csv(SEMANTIC_CSV, low_memory=False) if SEMANTIC_CSV.exists() else None
    return config, profile, semantic


def expand_corridors(config: pd.DataFrame, profile: pd.DataFrame, semantic: pd.DataFrame | None) -> pd.DataFrame:
    rows = []
    for _, corr in config.iterrows():
        segment = profile[
            pd.to_numeric(profile["dist_m"], errors="coerce").between(
                float(corr["start_dist_m"]), float(corr["end_dist_m"]), inclusive="both"
            )
        ].copy()
        if semantic is not None:
            keep_cols = [
                c
                for c in ["dist_m", "osm_way_name", "osm_way_id", "osm_highway", "osm_surface", "osm_trail_visibility"]
                if c in semantic.columns
            ]
            if "dist_m" in keep_cols:
                segment = segment.merge(semantic[keep_cols], on="dist_m", how="left")
        for _, point in segment.iterrows():
            row = {
                "case_id": corr["case_id"],
                "corridor_id": corr["corridor_id"],
                "corridor_role": corr["corridor_role"],
                "start_dist_m": corr["start_dist_m"],
                "end_dist_m": corr["end_dist_m"],
                "include_for_ascent": corr["include_for_ascent"],
                "include_for_descent": corr["include_for_descent"],
                "weight": corr["weight"],
                "threshold_m": corr["threshold_m"],
                "review_note": corr["review_note"],
                "dist_m": point["dist_m"],
                "lat": point["lat"],
                "lon": point["lon"],
            }
            for c in ["osm_way_name", "osm_way_id", "osm_highway", "osm_surface", "osm_trail_visibility"]:
                if c in point.index:
                    row[c] = point[c]
            rows.append(row)
    return pd.DataFrame(rows)


def tooltip_text(row: pd.Series) -> str:
    fields = [
        "corridor_id",
        "corridor_role",
        "dist_m",
        "lat",
        "lon",
        "osm_way_name",
        "osm_highway",
        "review_note",
    ]
    return html.escape("\n".join(f"{f}: {row[f]}" for f in fields if f in row.index and pd.notna(row[f])))


def route_order_markers(profile: pd.DataFrame, projector: Projector) -> str:
    route_dist = pd.to_numeric(profile["dist_m"], errors="coerce")
    max_dist = int(route_dist.max())
    pieces = []
    for target in range(0, max_dist + 1, ORDER_MARKER_INTERVAL_M):
        idx = (route_dist - target).abs().idxmin()
        row = profile.loc[idx]
        x, y = projector.xy(float(row["lat"]), float(row["lon"]))
        pieces.append(
            f'<g class="order-marker"><circle cx="{x:.2f}" cy="{y:.2f}" r="4"><title>route_dist_m {target}</title></circle>'
            f'<text x="{x + 5:.2f}" y="{y - 5:.2f}">{target}</text></g>'
        )
    return "\n".join(pieces)


def marker(point: dict[str, Any], projector: Projector, cls: str) -> str:
    x, y = projector.xy(float(point["lat"]), float(point["lon"]))
    return (
        f'<g class="{cls}"><circle cx="{x:.2f}" cy="{y:.2f}" r="7"><title>{html.escape(point["label"])}</title></circle>'
        f'<text x="{x + 9:.2f}" y="{y - 8:.2f}">{html.escape(point["label"])}</text></g>'
    )


def corridor_polyline(corridor_id: str, points: pd.DataFrame, projector: Projector) -> str:
    if points.empty:
        return ""
    role = str(points["corridor_role"].iloc[0])
    color = COLORS.get(corridor_id, "#333")
    style = ROLE_STYLES.get(role, ROLE_STYLES["branch_corridor"])
    dash = f' stroke-dasharray="{style["dash"]}"' if style["dash"] else ""
    title = html.escape(
        f"{corridor_id}\nrole: {role}\ndist: {points['dist_m'].min()}-{points['dist_m'].max()}m\n{points['review_note'].iloc[0]}"
    )
    return (
        f'<polyline class="corridor-layer {html.escape(corridor_id)}" points="{projector.polyline_points(points)}" '
        f'fill="none" stroke="{color}" stroke-width="{style["stroke_width"]}" stroke-opacity="{style["opacity"]}"{dash}>'
        f"<title>{title}</title></polyline>"
    )


def corridor_endpoint_labels(config: pd.DataFrame, profile: pd.DataFrame, projector: Projector) -> str:
    pieces = []
    route_dist = pd.to_numeric(profile["dist_m"], errors="coerce")
    for _, corr in config.iterrows():
        for label, dist in [("start", float(corr["start_dist_m"])), ("end", float(corr["end_dist_m"]))]:
            idx = (route_dist - dist).abs().idxmin()
            row = profile.loc[idx]
            x, y = projector.xy(float(row["lat"]), float(row["lon"]))
            text = f"{corr['corridor_id']} {label} {dist:g}m"
            pieces.append(
                f'<g class="corridor-end-label"><circle cx="{x:.2f}" cy="{y:.2f}" r="3"><title>{html.escape(text)}</title></circle>'
                f'<text x="{x + 6:.2f}" y="{y + 12:.2f}">{html.escape(text)}</text></g>'
            )
    return "\n".join(pieces)


def make_html(config: pd.DataFrame, profile: pd.DataFrame, expanded: pd.DataFrame, out_html: Path) -> None:
    projector = Projector(profile)
    corridor_svgs = []
    for corridor_id, points in expanded.groupby("corridor_id", sort=False):
        corridor_svgs.append(corridor_polyline(str(corridor_id), points.sort_values("dist_m"), projector))

    legend_rows = []
    for _, corr in config.iterrows():
        color = COLORS.get(corr["corridor_id"], "#333")
        legend_rows.append(
            f'<label><input type="checkbox" checked onchange="toggleLayer(\'{html.escape(str(corr["corridor_id"]))}\', this.checked)"> '
            f'<span class="swatch" style="background:{color}"></span> {html.escape(str(corr["corridor_id"]))} '
            f'({html.escape(str(corr["corridor_role"]))})</label>'
        )

    table_rows = []
    for _, corr in config.iterrows():
        table_rows.append(
            "<tr>"
            + "".join(
                f"<td>{html.escape(str(corr[c]))}</td>"
                for c in [
                    "corridor_id",
                    "corridor_role",
                    "start_dist_m",
                    "end_dist_m",
                    "include_for_ascent",
                    "include_for_descent",
                    "weight",
                    "threshold_m",
                    "review_note",
                ]
            )
            + "</tr>"
        )

    html_text = f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <title>Qixing branch corridor definition QA</title>
  <style>
    body {{ margin:0; font-family: Arial, 'Microsoft JhengHei', sans-serif; color:#1f2933; background:#f6f8fb; }}
    header {{ padding:14px 18px; background:#17202a; color:white; }}
    h1 {{ margin:0; font-size:20px; }}
    .layout {{ display:grid; grid-template-columns: 1fr 380px; min-height:calc(100vh - 54px); }}
    .canvas {{ padding:12px; overflow:auto; }}
    .panel {{ background:white; border-left:1px solid #d9dee5; padding:14px; overflow:auto; }}
    svg {{ background:white; border:1px solid #d9dee5; box-shadow:0 1px 3px rgba(0,0,0,.08); }}
    .route-axis {{ fill:none; stroke:#111827; stroke-width:2; stroke-opacity:.45; }}
    .marker circle {{ stroke:#111; stroke-width:1.5; }}
    .via-up circle {{ fill:#1b9e77; }}
    .via-down circle {{ fill:#d95f02; }}
    .summit circle {{ fill:#7570b3; }}
    .start circle {{ fill:#2c7bb6; }}
    .end circle {{ fill:#000; }}
    .marker text, .corridor-end-label text, .order-marker text {{ font-size:11px; fill:#111; paint-order:stroke; stroke:white; stroke-width:3px; }}
    .corridor-end-label circle {{ fill:white; stroke:#111; stroke-width:1; }}
    .order-marker circle {{ fill:white; stroke:#111; stroke-width:1.5; }}
    .swatch {{ display:inline-block; width:12px; height:12px; margin-right:5px; vertical-align:middle; }}
    label {{ display:block; margin:5px 0; font-size:12px; }}
    table {{ width:100%; border-collapse:collapse; font-size:12px; }}
    th, td {{ border-bottom:1px solid #edf0f4; padding:5px 4px; text-align:left; vertical-align:top; }}
    .note {{ padding:8px; background:#fff8db; border:1px solid #f3d36b; font-size:12px; line-height:1.45; }}
  </style>
</head>
<body>
  <header><h1>Qixing branch corridor definition QA</h1></header>
  <div class="layout">
    <main class="canvas">
      <svg viewBox="0 0 {projector.width} {projector.height}" width="{projector.width}" height="{projector.height}">
        <polyline class="route-axis" points="{projector.polyline_points(profile)}"><title>repaired candidate route axis</title></polyline>
        {' '.join(corridor_svgs)}
        {marker({"label": "start", "lat": profile.iloc[0]["lat"], "lon": profile.iloc[0]["lon"]}, projector, "marker start")}
        {marker({"label": "end", "lat": profile.iloc[-1]["lat"], "lon": profile.iloc[-1]["lon"]}, projector, "marker end")}
        {marker(VIA_UP, projector, "marker via-up")}
        {marker(VIA_DOWN, projector, "marker via-down")}
        {marker(SUMMIT, projector, "marker summit")}
        {route_order_markers(profile, projector)}
        {corridor_endpoint_labels(config, profile, projector)}
      </svg>
    </main>
    <aside class="panel">
      <div class="note">Manual review required. Branch corridors are primary discriminators; shared corridors are low-weight context; ambiguous windows are review aids.</div>
      <h2>Layers</h2>
      {''.join(legend_rows)}
      <h2>Corridor Definition</h2>
      <table>
        <thead><tr><th>id</th><th>role</th><th>start</th><th>end</th><th>asc</th><th>desc</th><th>w</th><th>thr</th><th>note</th></tr></thead>
        <tbody>{''.join(table_rows)}</tbody>
      </table>
    </aside>
  </div>
  <script>
    function toggleLayer(cls, checked) {{
      document.querySelectorAll('.' + cls).forEach(el => el.style.display = checked ? '' : 'none');
    }}
  </script>
</body>
</html>"""
    out_html.write_text(html_text, encoding="utf-8")


def make_png(config: pd.DataFrame, profile: pd.DataFrame, expanded: pd.DataFrame, out_png: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 8), dpi=160)
    ax.plot(profile["lon"], profile["lat"], color="#333333", linewidth=1.2, alpha=0.5, label="route axis")
    for corridor_id, points in expanded.groupby("corridor_id", sort=False):
        corr = config[config["corridor_id"] == corridor_id].iloc[0]
        role = corr["corridor_role"]
        linestyle = "--" if role == "shared_corridor" else ":" if role == "ambiguous_corridor" else "-"
        linewidth = 3.5 if role == "branch_corridor" else 2.5
        ax.plot(points["lon"], points["lat"], color=COLORS.get(corridor_id, "#333"), linewidth=linewidth, linestyle=linestyle, label=corrridor_label(corr))
    ax.scatter([VIA_UP["lon"]], [VIA_UP["lat"]], color=COLORS["via_up_corridor"], s=45, label="via_up")
    ax.scatter([VIA_DOWN["lon"]], [VIA_DOWN["lat"]], color=COLORS["via_down_corridor"], s=45, label="via_down")
    ax.scatter([SUMMIT["lon"]], [SUMMIT["lat"]], color=COLORS["summit_shared_ascent"], s=45, label="summit")
    ax.set_title("Qixing branch corridor definition QA")
    ax.set_xlabel("lon")
    ax.set_ylabel("lat")
    ax.axis("equal")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7, loc="best")
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def corrridor_label(corr: pd.Series) -> str:
    return f"{corr['corridor_id']} ({corr['start_dist_m']}-{corr['end_dist_m']}m)"


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    config, profile, semantic = load_inputs()
    expanded = expand_corridors(config, profile, semantic)

    expanded_csv = OUT_ROOT / "qixing_branch_corridor_definition_expanded_points.csv"
    out_html = OUT_ROOT / "qixing_branch_corridor_definition_qa.html"
    out_png = OUT_ROOT / "qixing_branch_corridor_definition_qa.png"
    summary_json = OUT_ROOT / "qixing_branch_corridor_definition_qa_summary.json"

    expanded.to_csv(expanded_csv, index=False, encoding="utf-8-sig")
    make_html(config, profile, expanded, out_html)
    make_png(config, profile, expanded, out_png)

    role_counts = config["corridor_role"].value_counts().to_dict()
    via_up = config[config["corridor_id"] == "via_up_corridor"].iloc[0]
    via_down = config[config["corridor_id"] == "via_down_corridor"].iloc[0]
    summary = {
        "case_id": CASE_ID,
        "corridor_definition_csv": str(CONFIG_CSV),
        "route_profile_csv": str(ROUTE_PROFILE_CSV),
        "semantic_csv": str(SEMANTIC_CSV) if SEMANTIC_CSV.exists() else None,
        "route_dist_max_m": float(pd.to_numeric(profile["dist_m"], errors="coerce").max()),
        "summit_dist_m": SUMMIT_DIST_M,
        "corridors_n": int(len(config)),
        "branch_corridors_n": int(role_counts.get("branch_corridor", 0)),
        "shared_corridors_n": int(role_counts.get("shared_corridor", 0)),
        "ambiguous_corridors_n": int(role_counts.get("ambiguous_corridor", 0)),
        "via_up_corridor_dist_range": [float(via_up["start_dist_m"]), float(via_up["end_dist_m"])],
        "via_down_corridor_dist_range": [float(via_down["start_dist_m"]), float(via_down["end_dist_m"])],
        "manual_review_required": True,
        "ready_for_v2_inference": False,
        "outputs": {
            "qa_html": str(out_html),
            "qa_png": str(out_png),
            "expanded_points_csv": str(expanded_csv),
            "summary_json": str(summary_json),
        },
        "note": "This is a QA artifact for manual review of branch corridor dist ranges. It does not run route-choice inference.",
        "runtime_llm_allowed": False,
    }
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"config_csv={CONFIG_CSV}")
    print(f"qa_html={out_html}")
    print(f"qa_png={out_png}")
    print(f"expanded_points_csv={expanded_csv}")
    print(f"summary_json={summary_json}")
    print(f"route_dist_max_m={summary['route_dist_max_m']:.6f}")
    print(f"summit_dist_m={SUMMIT_DIST_M:.6f}")
    print("manual_review_required=True")
    print("ready_for_v2_inference=False")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
