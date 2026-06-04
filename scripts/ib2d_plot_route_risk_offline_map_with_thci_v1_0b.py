# -*- coding: utf-8 -*-
"""Build IB2D x THCI integrated offline visualizations.

The script wraps existing IB2D/IB1E visual evidence with a THCI radar panel.
It never reruns IA1/IB0/IB1/IB2D and never recalculates THCI scores. THCI v1.0c
is the default/current recommended display version; v1.0b remains available as
the preserved previous baseline.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import os
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(r"C:\mountain_work\115_osm")

IB2D_ROOT = PROJECT_ROOT / "outputs" / "ib2d_route_risk_offline_map_v1_3b_contract_qa"
IB1E_TERRAIN_RISK_HTML_ROOT = PROJECT_ROOT / "outputs" / "ib1e_osm_nlsc_terrain_risk_plot_v1_3b_contract_qa"
IB1E_ROUTE_PROFILE_ROOT = PROJECT_ROOT / "outputs" / "ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa"
DEFAULT_OUT_ROOT = PROJECT_ROOT / "outputs" / "ib2d_thci_radar_v1_0c"
DEFAULT_MAP_ONLY_OUT_ROOT = PROJECT_ROOT / "outputs" / "ib2d_map_only_v1_3b_contract_qa"

LEFT_PANEL_LAYOUT = "map_top_elevation_bottom"
HYDRO_TOPO_REVIEW_STATUS = "WEATHER_CALIBRATION_ESTABLISHED_WITH_HYDROLOGY_TOPOGRAPHY_REVIEW"

THCI_CONTEXTS = {
    "v1_0b": {
        "suffix": "v1_0b",
        "scoring_version": "v1.0b",
        "title": "THCI v1.0b",
        "subtitle": "navigation semantics calibrated",
        "axis_root": PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_0b",
        "radar_root": PROJECT_ROOT / "outputs" / "thci_radar_v1_0b",
        "radar_source_stage": "THCI_V1_0B_RADAR",
        "current_recommended_display_version": False,
        "previous_recommended_version": "",
    },
    "v1_0c": {
        "suffix": "v1_0c",
        "scoring_version": "v1.0c",
        "title": "THCI v1.0c",
        "subtitle": "weather semantics calibrated",
        "axis_root": PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_0c",
        "radar_root": PROJECT_ROOT / "outputs" / "thci_radar_v1_0c",
        "radar_source_stage": "THCI_V1_0C_RADAR",
        "current_recommended_display_version": True,
        "previous_recommended_version": "v1.0b",
    },
}

CASES = [
    "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b",
    "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b",
    "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b",
    "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b",
    "qixing_lengshuikeng_xiaoyoukeng_gpx_osmrefresh_v1_3b",
]

AXIS_ORDER = [
    ("physical_difficulty_score", "體力難度"),
    ("technical_difficulty_score", "技術難度"),
    ("baseline_hazard_score", "基礎危害"),
    ("navigation_risk_score", "迷航風險"),
    ("support_difficulty_score", "支援不易"),
    ("weather_impact_score", "天候影響"),
]

RISK_COLOR = {
    "low": "#4CAF50",
    "moderate": "#F2C037",
    "high": "#F57C00",
    "very_high": "#D93A3A",
    "unknown": "#9E9E9E",
}

RISK_LEVEL = {"unknown": 0, "low": 1, "moderate": 2, "high": 3, "very_high": 4}


def _read_csv_first_row(path: Path) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            return dict(row)
    raise ValueError(f"CSV is empty: {path}")


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _relpath_for_html(target: Path, html_path: Path) -> str:
    rel = os.path.relpath(str(target.resolve()), start=str(html_path.parent.resolve()))
    return Path(rel).as_posix()


def _project_path(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def norm_band(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "veryhigh": "very_high",
        "very_high": "very_high",
        "high": "high",
        "moderate": "moderate",
        "medium": "moderate",
        "low": "low",
        "flat": "low",
        "gentle": "low",
        "steep": "high",
        "very_steep": "very_high",
    }
    return aliases.get(text, "unknown")


def _score_to_band(value: Any) -> str:
    score = _float_or_none(value)
    if score is None:
        return "unknown"
    if score >= 0.75:
        return "very_high"
    if score >= 0.50:
        return "high"
    if score >= 0.25:
        return "moderate"
    return "low"


def _slope_pct_to_band(value: Any) -> str:
    slope = _float_or_none(value)
    if slope is None:
        return "unknown"
    slope = abs(slope)
    if slope >= 35:
        return "very_high"
    if slope >= 20:
        return "high"
    if slope >= 10:
        return "moderate"
    return "low"


def pick_band(row_a: dict[str, Any], row_b: dict[str, Any]) -> tuple[str, str]:
    band_cols = ["risk_band", "osm_terrain_combined_risk_band", "slope_band"]
    for col in band_cols:
        bands = [norm_band(row_a.get(col)), norm_band(row_b.get(col))]
        if any(band != "unknown" for band in bands):
            return max(bands, key=lambda item: RISK_LEVEL.get(item, 0)), col

    score_cols = ["risk_score", "osm_terrain_combined_risk_score"]
    for col in score_cols:
        bands = [_score_to_band(row_a.get(col)), _score_to_band(row_b.get(col))]
        if any(band != "unknown" for band in bands):
            return max(bands, key=lambda item: RISK_LEVEL.get(item, 0)), col

    bands = [_slope_pct_to_band(row_a.get("slope_pct")), _slope_pct_to_band(row_b.get("slope_pct"))]
    if any(band != "unknown" for band in bands):
        return max(bands, key=lambda item: RISK_LEVEL.get(item, 0)), "slope_pct"
    return "unknown", "missing"


def _find_newest(paths: list[Path]) -> Path | None:
    existing = [path for path in paths if path.exists()]
    if not existing:
        return None
    return max(existing, key=lambda path: path.stat().st_mtime)


def _find_ib2d_formal_html(case_id: str) -> Path | None:
    case_dir = IB2D_ROOT / case_id
    return _find_newest(list(case_dir.glob("*.html"))) if case_dir.exists() else None


def _find_ib1e_formal_html(case_id: str) -> Path | None:
    case_dir = IB1E_TERRAIN_RISK_HTML_ROOT / case_id
    return _find_newest(list(case_dir.glob("*.html"))) if case_dir.exists() else None


def _find_ib2d_formal_png(case_id: str) -> Path | None:
    case_dir = IB2D_ROOT / case_id
    if not case_dir.exists():
        return None

    excluded_tokens = ["with_radar", "radar", "challenge_radar", "route_challenge"]
    exact = case_dir / f"{case_id}_route_risk_offline_map.png"
    if exact.exists():
        return exact

    candidates = []
    for path in case_dir.glob("*.png"):
        name = path.name.lower()
        if any(token in name for token in excluded_tokens):
            continue
        if "route_risk_offline_map" in name:
            score = 100
        elif all(token in name for token in ["risk", "map"]):
            score = 60
        elif any(token in name for token in ["ib2d", "route", "risk", "map"]):
            score = 30
        else:
            score = 0
        if score > 0:
            candidates.append((score, path.stat().st_mtime, path))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (item[0], item[1]), reverse=True)[0][2]


def find_left_map_visual_source(case_id: str, left_map_mode: str) -> dict[str, Any]:
    ib2d_html = _find_ib2d_formal_html(case_id)
    ib1e_html = _find_ib1e_formal_html(case_id)
    ib2d_png = _find_ib2d_formal_png(case_id)

    base = {
        "ib2d_formal_html": ib2d_html,
        "ib1e_formal_html": ib1e_html,
        "ib2d_formal_png": ib2d_png,
    }

    if left_map_mode == "ib1e-html":
        if ib1e_html:
            return {
                **base,
                "left_map_visual_source_type": "ib1e_html",
                "left_map_source_stage": "IB1E_OSM_NLSC_TERRAIN_RISK_PLOT",
                "left_map_visual_source_path": ib1e_html,
                "integration_mode": "wrapper_iframe_ib1e_html",
                "note": "left-map-mode=ib1e-html uses IB1E formal terrain risk HTML as left map visual source.",
            }
        return {
            **base,
            "left_map_visual_source_type": "missing",
            "left_map_source_stage": "",
            "left_map_visual_source_path": None,
            "integration_mode": "missing",
            "missing_status": "FAIL_missing_ib1e_html",
            "note": "left-map-mode=ib1e-html requires IB1E formal terrain risk HTML; no fallback was applied.",
        }

    if left_map_mode == "ib2d-png":
        if ib2d_png:
            return {
                **base,
                "left_map_visual_source_type": "ib2d_png",
                "left_map_source_stage": "IB2D_ROUTE_RISK_OFFLINE_MAP",
                "left_map_visual_source_path": ib2d_png,
                "integration_mode": "static_png_wrapper_ib2d",
                "note": "left-map-mode=ib2d-png uses pure IB2D route risk offline map PNG as left map visual source.",
            }
        return {
            **base,
            "left_map_visual_source_type": "missing",
            "left_map_source_stage": "",
            "left_map_visual_source_path": None,
            "integration_mode": "missing",
            "missing_status": "FAIL_missing_ib2d_png",
            "note": "left-map-mode=ib2d-png requires IB2D PNG; no fallback was applied.",
        }

    if ib2d_html:
        return {
            **base,
            "left_map_visual_source_type": "ib2d_html",
            "left_map_source_stage": "IB2D_ROUTE_RISK_OFFLINE_MAP",
            "left_map_visual_source_path": ib2d_html,
            "integration_mode": "wrapper_iframe_ib2d_html",
            "note": "Using IB2D formal HTML as left map visual source.",
        }
    if ib1e_html:
        return {
            **base,
            "left_map_visual_source_type": "ib1e_html",
            "left_map_source_stage": "IB1E_OSM_NLSC_TERRAIN_RISK_PLOT",
            "left_map_visual_source_path": ib1e_html,
            "integration_mode": "wrapper_iframe_ib1e_html",
            "note": "IB2D formal HTML not available; using IB1E formal terrain risk HTML as left map visual source.",
        }
    if ib2d_png:
        return {
            **base,
            "left_map_visual_source_type": "ib2d_png",
            "left_map_source_stage": "IB2D_ROUTE_RISK_OFFLINE_MAP",
            "left_map_visual_source_path": ib2d_png,
            "integration_mode": "static_png_wrapper_ib2d",
            "note": "IB2D/IB1E HTML not available; using pure IB2D route risk offline map PNG.",
        }
    return {
        **base,
        "left_map_visual_source_type": "missing",
        "left_map_source_stage": "",
        "left_map_visual_source_path": None,
        "integration_mode": "missing",
        "missing_status": "FAIL_missing_left_map_visual_source",
        "note": "No IB2D HTML, IB1E HTML, or eligible pure IB2D PNG was found.",
    }


def load_route_profile_for_elevation_plot(case_id: str) -> dict[str, Any]:
    source_csv = (
        IB1E_ROUTE_PROFILE_ROOT
        / case_id
        / f"{case_id}_route_profile_contour_window_terrain_enriched.csv"
    )
    result: dict[str, Any] = {
        "source_csv": source_csv,
        "exists": source_csv.exists(),
        "points": [],
        "elevation_column": "missing",
        "elevation_color_source": "missing",
    }
    if not source_csv.exists():
        return result

    rows = _read_csv_rows(source_csv)
    elevation_column = "ele_smooth" if any(row.get("ele_smooth") not in {None, ""} for row in rows) else "ele_gpx_m"
    points = []
    color_sources: list[str] = []
    for row in rows:
        dist = _float_or_none(row.get("dist_m"))
        ele = _float_or_none(row.get(elevation_column))
        if dist is None or ele is None:
            continue
        points.append({"dist_m": dist, "ele_m": ele, "row": row})
    for idx in range(max(0, len(points) - 1)):
        _band, source = pick_band(points[idx]["row"], points[idx + 1]["row"])
        if source != "missing":
            color_sources.append(source)
    result["points"] = points
    result["elevation_column"] = elevation_column if points else "missing"
    result["elevation_color_source"] = color_sources[0] if color_sources else "missing"
    return result


def build_risk_colored_elevation_profile_html(profile: dict[str, Any]) -> str:
    points = profile.get("points") or []
    if len(points) < 2:
        return '<div class="elevation-empty">Elevation profile source is missing or insufficient.</div>'

    width, height = 980, 250
    pad_l, pad_r, pad_t, pad_b = 54, 20, 18, 36
    min_x, max_x = min(p["dist_m"] for p in points), max(p["dist_m"] for p in points)
    min_y, max_y = min(p["ele_m"] for p in points), max(p["ele_m"] for p in points)
    if max_x <= min_x:
        max_x = min_x + 1
    if max_y <= min_y:
        max_y = min_y + 1

    def sx(value: float) -> float:
        return pad_l + (value - min_x) / (max_x - min_x) * (width - pad_l - pad_r)

    def sy(value: float) -> float:
        return height - pad_b - (value - min_y) / (max_y - min_y) * (height - pad_t - pad_b)

    segments = []
    for idx in range(len(points) - 1):
        a, b = points[idx], points[idx + 1]
        band, _source = pick_band(a["row"], b["row"])
        color = RISK_COLOR.get(band, RISK_COLOR["unknown"])
        segments.append(
            f'<line x1="{sx(a["dist_m"]):.2f}" y1="{sy(a["ele_m"]):.2f}" '
            f'x2="{sx(b["dist_m"]):.2f}" y2="{sy(b["ele_m"]):.2f}" '
            f'stroke="{color}" stroke-width="2.4" stroke-linecap="round" />'
        )
    axis = (
        f'<line x1="{pad_l}" y1="{height-pad_b}" x2="{width-pad_r}" y2="{height-pad_b}" stroke="#8f99a5" />'
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{height-pad_b}" stroke="#8f99a5" />'
        f'<text x="{pad_l}" y="{height-10}" font-size="11" fill="#5f6b7a">0 m</text>'
        f'<text x="{width-pad_r-72}" y="{height-10}" font-size="11" fill="#5f6b7a">{max_x:.0f} m</text>'
        f'<text x="8" y="{sy(max_y)+4:.2f}" font-size="11" fill="#5f6b7a">{max_y:.0f} m</text>'
        f'<text x="8" y="{sy(min_y)+4:.2f}" font-size="11" fill="#5f6b7a">{min_y:.0f} m</text>'
    )
    legend = "".join(
        f'<span><i style="background:{color}"></i>{html.escape(label)}</span>'
        for label, color in RISK_COLOR.items()
    )
    return f"""
      <section class="elevation-profile">
        <div class="elevation-header">
          <h2>Risk-colored elevation profile</h2>
          <div>{html.escape(str(profile.get("elevation_color_source", "")))} / {html.escape(str(profile.get("elevation_column", "")))}</div>
        </div>
        <svg viewBox="0 0 {width} {height}" role="img" aria-label="Risk-colored elevation profile">
          {axis}
          {''.join(segments)}
        </svg>
        <div class="legend">{legend}</div>
      </section>
    """


def load_thci_axis_scores(case_id: str, ctx: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    suffix = ctx["suffix"]
    path = ctx["axis_root"] / case_id / f"{case_id}_thci_axis_scores_{suffix}.csv"
    row = _read_csv_first_row(path)
    row["axis_scores"] = {axis: _float_or_none(row.get(axis)) for axis, _label in AXIS_ORDER}
    return row, path


def load_thci_radar_summary(case_id: str, ctx: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    suffix = ctx["suffix"]
    path = ctx["radar_root"] / case_id / f"{case_id}_thci_radar_summary_{suffix}.json"
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle), path


def _find_thci_radar_png(case_id: str, ctx: dict[str, Any]) -> Path:
    suffix = ctx["suffix"]
    return ctx["radar_root"] / case_id / f"{case_id}_thci_radar_{suffix}.png"


def _axis_score_table(axis_scores: dict[str, float | None]) -> str:
    rows = []
    for axis, label in AXIS_ORDER:
        value = axis_scores.get(axis)
        rows.append(
            "<tr>"
            f"<th>{html.escape(label)}</th>"
            f"<td><code>{html.escape(axis)}</code></td>"
            f"<td>{'' if value is None else f'{value:.4f}'}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def build_calibration_metrics_html(axis_scores: dict[str, float | None], radar_summary: dict[str, Any], ctx: dict[str, Any]) -> str:
    if ctx["suffix"] == "v1_0c":
        previous_weather = radar_summary.get("previous_v1_0b_weather_impact_score")
        v10c_weather = radar_summary.get("v1_0c_weather_impact_score", axis_scores.get("weather_impact_score"))
        delta = radar_summary.get("weather_delta_v1_0c_minus_v1_0b")
        if delta is None and _float_or_none(previous_weather) is not None and _float_or_none(v10c_weather) is not None:
            delta = float(v10c_weather) - float(previous_weather)
        return f"""
          <section>
            <h2>Weather calibration</h2>
            <dl class="metrics">
              <div><dt>previous_v1_0b_weather_impact_score</dt><dd>{html.escape(str(previous_weather))}</dd></div>
              <div><dt>v1_0c_weather_impact_score</dt><dd>{html.escape(str(v10c_weather))}</dd></div>
              <div><dt>weather_delta_v1_0c_minus_v1_0b</dt><dd>{html.escape('' if delta is None else f'{float(delta):+.4f}')}</dd></div>
              <div><dt>scoring_version</dt><dd>v1.0c</dd></div>
              <div><dt>weather_semantics_calibrated</dt><dd>true</dd></div>
              <div><dt>current_recommended_display_version</dt><dd>true</dd></div>
              <div><dt>previous_recommended_version</dt><dd>v1.0b</dd></div>
              <div><dt>hydrology_topography_review_status</dt><dd>{HYDRO_TOPO_REVIEW_STATUS}</dd></div>
              <div><dt>runtime_llm_allowed</dt><dd>false</dd></div>
            </dl>
          </section>
        """

    previous_nav = radar_summary.get("previous_v1_0a_navigation_risk_score")
    v10b_nav = radar_summary.get("v1_0b_navigation_risk_score", axis_scores.get("navigation_risk_score"))
    nav_delta = ""
    if _float_or_none(previous_nav) is not None and _float_or_none(v10b_nav) is not None:
        nav_delta = f"{float(v10b_nav) - float(previous_nav):+.4f}"
    return f"""
      <section>
        <h2>Navigation calibration</h2>
        <dl class="metrics">
          <div><dt>previous_v1_0a_navigation_risk_score</dt><dd>{html.escape(str(previous_nav))}</dd></div>
          <div><dt>v1_0b_navigation_risk_score</dt><dd>{html.escape(str(v10b_nav))}</dd></div>
          <div><dt>navigation_delta</dt><dd>{html.escape(nav_delta)}</dd></div>
          <div><dt>scoring_version</dt><dd>v1.0b</dd></div>
          <div><dt>navigation_semantics_calibrated</dt><dd>{html.escape(str(radar_summary.get("navigation_semantics_calibrated")).lower())}</dd></div>
          <div><dt>runtime_llm_allowed</dt><dd>false</dd></div>
        </dl>
      </section>
    """


def build_thci_panel_html(
    case_id: str,
    axis_scores: dict[str, float | None],
    radar_png: Path,
    radar_summary: dict[str, Any],
    output_html: Path,
    ctx: dict[str, Any],
) -> str:
    radar_src = _relpath_for_html(radar_png, output_html)
    radar_project_path = _project_path(radar_png)
    metrics_html = build_calibration_metrics_html(axis_scores, radar_summary, ctx)
    return f"""
      <aside class="thci-panel">
        <div class="panel-kicker">Downstream calibrated interpretation layer</div>
        <h1>{html.escape(ctx["title"])}</h1>
        <p class="subtitle">{html.escape(ctx["subtitle"])}</p>
        <div class="radar-caption">{html.escape(ctx["title"])} radar chart for {html.escape(case_id)}</div>
        <img class="radar" src="{html.escape(radar_src)}" alt="{html.escape(ctx["title"])} radar chart for {html.escape(case_id)}" data-radar-source-stage="{ctx["radar_source_stage"]}" data-thci-radar-png="{html.escape(radar_project_path)}">
        <section>
          <h2>Six-axis scores</h2>
          <table>
            <thead><tr><th>Axis</th><th>ID</th><th>Score</th></tr></thead>
            <tbody>{_axis_score_table(axis_scores)}</tbody>
          </table>
        </section>
        <section>
          <h2>Radar source</h2>
          <dl class="metrics">
            <div><dt>radar_source_stage</dt><dd>{ctx["radar_source_stage"]}</dd></div>
            <div><dt>thci_radar_png</dt><dd><code>{html.escape(radar_project_path)}</code></dd></div>
          </dl>
        </section>
        {metrics_html}
        <section class="boundary">
          <h2>Boundary</h2>
          <p>IB2D was not rerun. The original IB2D output remains the baseline route-risk visualization layer. THCI is shown as a downstream calibrated six-axis interpretation layer.</p>
          <p>For v1.0c, the hydrology-topography review provides evidence that weather risk should account for water proximity, low terrain overlap, and crossing surge potential.</p>
        </section>
      </aside>
    """


def _build_left_map_html(case_id: str, left_source: dict[str, Any], output_html: Path, issues: list[str]) -> str:
    source_path = left_source.get("left_map_visual_source_path")
    source_type = left_source.get("left_map_visual_source_type")
    if source_path is not None and source_type in {"ib2d_html", "ib1e_html"}:
        iframe_src = _relpath_for_html(source_path, output_html)
        title = "IB2D route-risk map" if source_type == "ib2d_html" else "IB1E formal terrain risk map"
        return f'<iframe class="map-frame" src="{html.escape(iframe_src)}" title="{html.escape(title)}"></iframe>'
    if source_path is not None and source_type == "ib2d_png":
        png_src = _relpath_for_html(source_path, output_html)
        return f'<div class="static-map-wrap"><img class="static-map" src="{html.escape(png_src)}" alt="IB2D formal route-risk PNG for {html.escape(case_id)}"></div>'
    issue_items = "".join(f"<li>{html.escape(issue)}</li>" for issue in issues)
    return f'<div class="missing-source"><h1>Left map visual source missing</h1><ul>{issue_items}</ul></div>'


def build_left_panel_layout_html(
    case_id: str,
    left_source: dict[str, Any],
    elevation_profile_html: str,
    output_html: Path,
    issues: list[str],
) -> str:
    map_html = _build_left_map_html(case_id, left_source, output_html, issues)
    return f"""
      <section class="left-panel">
        <div class="map-pane">{map_html}</div>
        <div class="elevation-pane">{elevation_profile_html}</div>
      </section>
    """


def build_integrated_wrapper_html(
    case_id: str,
    left_panel_html: str,
    thci_panel_html: str,
    integrated_status: str,
    integration_mode: str,
    ctx: dict[str, Any],
) -> str:
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(case_id)} IB2D x {html.escape(ctx["title"])}</title>
  <style>
    :root {{ color-scheme: light; --ink: #17202a; --muted: #5f6b7a; --line: #d9e0e7; --panel: #f7f9fb; --accent: #355f8c; --warn: #a44200; }}
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; height: 100%; font-family: "Microsoft JhengHei", "Noto Sans CJK TC", Arial, sans-serif; color: var(--ink); }}
    body {{ background: #fff; }}
    .shell {{ display: grid; grid-template-columns: minmax(0, 65%) minmax(360px, 30%); min-height: 100vh; }}
    .left-panel {{ display: grid; grid-template-rows: 70vh 30vh; min-width: 0; border-right: 1px solid var(--line); background: #eef2f6; }}
    .map-pane {{ min-height: 0; border-bottom: 1px solid var(--line); background: #fff; }}
    .map-frame {{ width: 100%; height: 100%; border: 0; display: block; background: white; }}
    .static-map-wrap {{ height: 100%; overflow: auto; padding: 14px; }}
    .static-map {{ display: block; max-width: 100%; height: auto; margin: 0 auto; background: white; border: 1px solid var(--line); }}
    .elevation-pane {{ min-height: 0; overflow: hidden; background: white; }}
    .elevation-profile {{ height: 100%; padding: 10px 14px; }}
    .elevation-header {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; color: var(--muted); }}
    .elevation-header h2 {{ margin: 0; color: var(--ink); font-size: 15px; }}
    .elevation-profile svg {{ width: 100%; height: calc(100% - 42px); display: block; }}
    .legend {{ display: flex; gap: 10px; flex-wrap: wrap; font-size: 12px; color: var(--muted); }}
    .legend i {{ display: inline-block; width: 10px; height: 10px; margin-right: 4px; vertical-align: -1px; border-radius: 2px; }}
    .elevation-empty, .missing-source {{ padding: 16px; color: var(--warn); }}
    .thci-panel {{ padding: 22px; overflow-y: auto; max-height: 100vh; background: var(--panel); }}
    .panel-kicker {{ color: var(--accent); font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; }}
    h1 {{ margin: 6px 0 0; font-size: 28px; }}
    h2 {{ margin: 22px 0 10px; font-size: 16px; }}
    .subtitle {{ margin: 2px 0 16px; color: var(--muted); }}
    .radar {{ width: 100%; height: auto; background: white; border: 1px solid var(--line); }}
    table {{ width: 100%; border-collapse: collapse; background: white; }}
    th, td {{ border: 1px solid var(--line); padding: 8px; font-size: 13px; text-align: left; vertical-align: top; }}
    thead th {{ background: #eaf0f6; }}
    code {{ font-size: 12px; word-break: break-word; }}
    .metrics {{ margin: 0; background: white; border: 1px solid var(--line); }}
    .metrics div {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 12px; padding: 8px 10px; border-bottom: 1px solid var(--line); }}
    .metrics div:last-child {{ border-bottom: 0; }}
    dt {{ color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }}
    dd {{ margin: 0; font-weight: 700; text-align: right; overflow-wrap: anywhere; }}
    .boundary {{ color: var(--muted); font-size: 13px; line-height: 1.55; }}
    .status {{ position: fixed; left: 12px; bottom: 12px; padding: 8px 10px; background: white; border: 1px solid var(--line); font-size: 12px; }}
    @media (max-width: 980px) {{ .shell {{ grid-template-columns: 1fr; }} .left-panel {{ grid-template-rows: 65vh 35vh; }} .thci-panel {{ max-height: none; }} }}
  </style>
</head>
<body>
  <main class="shell">
    {left_panel_html}
    {thci_panel_html}
  </main>
  <div class="status">integrated_status={html.escape(integrated_status)}; integration_mode={html.escape(integration_mode)}</div>
</body>
</html>
"""


def _validate_thci_inputs(
    axis_row: dict[str, Any] | None,
    axis_scores: dict[str, float | None],
    radar_png: Path,
    radar_summary: dict[str, Any] | None,
    ctx: dict[str, Any],
) -> list[str]:
    issues: list[str] = []
    if axis_row is None:
        issues.append("FAIL_missing_thci_axis_score_csv")
    else:
        if axis_row.get("scoring_version") != ctx["scoring_version"]:
            issues.append("FAIL_thci_axis_score_scoring_version")
        for axis, _label in AXIS_ORDER:
            value = axis_scores.get(axis)
            if value is None or value < 0.0 or value > 1.0:
                issues.append(f"FAIL_invalid_thci_axis_score:{axis}")
    if not radar_png.exists():
        issues.append("FAIL_missing_thci_radar_png")
    if radar_summary is None:
        issues.append("FAIL_missing_thci_radar_summary_json")
    else:
        if radar_summary.get("scoring_version") != ctx["scoring_version"]:
            issues.append("FAIL_thci_radar_summary_scoring_version")
        if radar_summary.get("runtime_llm_allowed") is not False:
            issues.append("FAIL_runtime_llm_allowed_not_false")
        if ctx["suffix"] == "v1_0b" and radar_summary.get("navigation_semantics_calibrated") is not True:
            issues.append("FAIL_navigation_semantics_calibrated_not_true")
        if ctx["suffix"] == "v1_0c":
            if radar_summary.get("weather_semantics_calibrated") is not True:
                issues.append("FAIL_weather_semantics_calibrated_not_true")
            if radar_summary.get("current_recommended_display_version") is not True:
                issues.append("FAIL_current_recommended_display_version_not_true")
            if radar_summary.get("previous_recommended_version") != "v1.0b":
                issues.append("FAIL_previous_recommended_version_not_v1_0b")
    return issues


def write_case_outputs(case_id: str, out_root: Path, left_map_mode: str, ctx: dict[str, Any]) -> dict[str, Any]:
    suffix = ctx["suffix"]
    out_dir = out_root / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    output_html = out_dir / f"{case_id}_ib2d_thci_{suffix}_integrated_map.html"
    output_summary_json = out_dir / f"{case_id}_ib2d_thci_{suffix}_integrated_summary.json"

    left_source = find_left_map_visual_source(case_id, left_map_mode)
    elevation_profile = load_route_profile_for_elevation_plot(case_id)
    elevation_html = build_risk_colored_elevation_profile_html(elevation_profile)

    radar_png = _find_thci_radar_png(case_id, ctx)
    axis_csv_path = ctx["axis_root"] / case_id / f"{case_id}_thci_axis_scores_{suffix}.csv"
    radar_summary_path = ctx["radar_root"] / case_id / f"{case_id}_thci_radar_summary_{suffix}.json"
    axis_row: dict[str, Any] | None = None
    axis_scores = {axis: None for axis, _label in AXIS_ORDER}
    radar_summary: dict[str, Any] | None = None
    blocking_issues: list[str] = []

    try:
        axis_row, axis_csv_path = load_thci_axis_scores(case_id, ctx)
        axis_scores = axis_row["axis_scores"]
    except Exception as exc:
        blocking_issues.append(f"FAIL_load_thci_axis_scores:{exc}")

    try:
        radar_summary, radar_summary_path = load_thci_radar_summary(case_id, ctx)
    except Exception as exc:
        blocking_issues.append(f"FAIL_load_thci_radar_summary:{exc}")

    if left_source["left_map_visual_source_type"] == "missing":
        blocking_issues.append(left_source.get("missing_status") or "FAIL_missing_left_map_visual_source")
    if not elevation_profile["exists"]:
        blocking_issues.append("FAIL_missing_elevation_profile_csv")
    if elevation_profile["elevation_column"] == "missing":
        blocking_issues.append("FAIL_missing_elevation_column")
    if elevation_profile["elevation_color_source"] == "missing":
        blocking_issues.append("FAIL_missing_elevation_color_source")
    blocking_issues.extend(_validate_thci_inputs(axis_row, axis_scores, radar_png, radar_summary, ctx))

    integrated_status = "PASS" if not blocking_issues else blocking_issues[0]
    panel_summary = radar_summary or {}
    if not panel_summary and axis_row:
        panel_summary = dict(axis_row)

    left_panel_html = build_left_panel_layout_html(case_id, left_source, elevation_html, output_html, blocking_issues)
    thci_panel_html = build_thci_panel_html(case_id, axis_scores, radar_png, panel_summary, output_html, ctx)
    output_html.write_text(
        build_integrated_wrapper_html(
            case_id,
            left_panel_html,
            thci_panel_html,
            integrated_status,
            left_source["integration_mode"],
            ctx,
        ),
        encoding="utf-8",
    )

    previous_nav = panel_summary.get("previous_v1_0a_navigation_risk_score")
    v10b_nav = panel_summary.get("v1_0b_navigation_risk_score", axis_scores.get("navigation_risk_score"))
    previous_weather = panel_summary.get("previous_v1_0b_weather_impact_score")
    v10c_weather = panel_summary.get("v1_0c_weather_impact_score", axis_scores.get("weather_impact_score"))
    weather_delta = panel_summary.get("weather_delta_v1_0c_minus_v1_0b")

    note = (
        f"{left_source['note']} Original IB2D remains the baseline route-risk visualization. "
        f"{ctx['title']} is a downstream calibrated six-axis interpretation layer. "
        "This script does not rerun or overwrite IA1/IB0/IB1/IB2D outputs."
    )
    if suffix == "v1_0c":
        note += " THCI v1.0c is the current recommended display/scoring version, promoted from weather calibration review evidence."

    summary = {
        "case_id": case_id,
        "integrated_status": integrated_status,
        "thci_version": suffix,
        "left_map_mode": left_map_mode,
        "original_ib2d_html": str(left_source["ib2d_formal_html"]) if left_source["ib2d_formal_html"] else None,
        "ib2d_formal_html_exists": left_source["ib2d_formal_html"] is not None,
        "ib1e_formal_html_exists": left_source["ib1e_formal_html"] is not None,
        "ib2d_formal_png_exists": left_source["ib2d_formal_png"] is not None,
        "left_map_visual_source_type": left_source["left_map_visual_source_type"],
        "left_map_source_stage": left_source["left_map_source_stage"],
        "left_map_visual_source_path": str(left_source["left_map_visual_source_path"]) if left_source["left_map_visual_source_path"] else None,
        "integration_mode": left_source["integration_mode"],
        "note": note,
        "elevation_profile_source_csv": str(elevation_profile["source_csv"]) if elevation_profile["source_csv"] else None,
        "elevation_profile_exists": elevation_profile["exists"],
        "elevation_profile_html_embedded": len(elevation_profile.get("points", [])) >= 2,
        "elevation_color_source": elevation_profile["elevation_color_source"],
        "elevation_column": elevation_profile["elevation_column"],
        "left_panel_layout": LEFT_PANEL_LAYOUT,
        "thci_axis_score_csv": str(axis_csv_path),
        "thci_axis_score_csv_exists": axis_csv_path.exists(),
        "thci_radar_png": str(radar_png),
        "thci_radar_png_exists": radar_png.exists(),
        "radar_source_stage": ctx["radar_source_stage"],
        "thci_radar_summary_json": str(radar_summary_path),
        "thci_radar_summary_json_exists": radar_summary_path.exists(),
        "output_html": str(output_html),
        "output_root": str(out_root),
        "output_summary_json": str(output_summary_json),
        "scoring_version": ctx["scoring_version"],
        "calibrated_from_v1_0a": _bool(panel_summary.get("calibrated_from_v1_0a")),
        "navigation_semantics_calibrated": _bool(panel_summary.get("navigation_semantics_calibrated")),
        "calibrated_from_v1_0b": _bool(panel_summary.get("calibrated_from_v1_0b")),
        "weather_semantics_calibrated": _bool(panel_summary.get("weather_semantics_calibrated")),
        "current_recommended_display_version": bool(ctx["current_recommended_display_version"]),
        "previous_recommended_version": ctx["previous_recommended_version"],
        "previous_v1_0a_navigation_risk_score": previous_nav,
        "v1_0b_navigation_risk_score": v10b_nav,
        "previous_v1_0b_weather_impact_score": previous_weather,
        "v1_0c_weather_impact_score": v10c_weather,
        "weather_delta_v1_0c_minus_v1_0b": weather_delta,
        "hydrology_topography_review_status": HYDRO_TOPO_REVIEW_STATUS if suffix == "v1_0c" else "",
        "axis_scores": axis_scores,
        "runtime_llm_allowed": False,
        "input_roots": {
            "ib2d": str(IB2D_ROOT),
            "ib1e_terrain_risk_html": str(IB1E_TERRAIN_RISK_HTML_ROOT),
            "ib1e_route_profile": str(IB1E_ROUTE_PROFILE_ROOT),
            f"thci_axis_scores_{suffix}": str(ctx["axis_root"]),
            f"thci_radar_{suffix}": str(ctx["radar_root"]),
        },
        "blocking_issues": blocking_issues,
    }
    output_summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "case_id": case_id,
        "integrated_status": integrated_status,
        "thci_version": suffix,
        "left_map_mode": left_map_mode,
        "output_html_exists": output_html.exists(),
        "output_html": str(output_html),
        "ib2d_formal_html_exists": left_source["ib2d_formal_html"] is not None,
        "ib1e_formal_html_exists": left_source["ib1e_formal_html"] is not None,
        "ib2d_formal_png_exists": left_source["ib2d_formal_png"] is not None,
        "left_map_visual_source_type": left_source["left_map_visual_source_type"],
        "left_map_source_stage": left_source["left_map_source_stage"],
        "left_map_visual_source_path": str(left_source["left_map_visual_source_path"]) if left_source["left_map_visual_source_path"] else "",
        "integration_mode": left_source["integration_mode"],
        "elevation_profile_exists": elevation_profile["exists"],
        "elevation_profile_source_csv": str(elevation_profile["source_csv"]) if elevation_profile["source_csv"] else "",
        "elevation_color_source": elevation_profile["elevation_color_source"],
        "elevation_column": elevation_profile["elevation_column"],
        "left_panel_layout": LEFT_PANEL_LAYOUT,
        "thci_axis_score_csv_exists": axis_csv_path.exists(),
        "thci_radar_png_exists": radar_png.exists(),
        "radar_source_stage": ctx["radar_source_stage"],
        "thci_radar_summary_json_exists": radar_summary_path.exists(),
        "scoring_version": ctx["scoring_version"],
        "calibrated_from_v1_0b": _bool(panel_summary.get("calibrated_from_v1_0b")),
        "weather_semantics_calibrated": _bool(panel_summary.get("weather_semantics_calibrated")),
        "current_recommended_display_version": bool(ctx["current_recommended_display_version"]),
        "previous_recommended_version": ctx["previous_recommended_version"],
        "previous_v1_0b_weather_impact_score": previous_weather,
        "v1_0c_weather_impact_score": v10c_weather,
        "weather_delta_v1_0c_minus_v1_0b": weather_delta,
    }


def write_batch_summary(case_rows: list[dict[str, Any]], out_root: Path, ctx: dict[str, Any], merge_existing: bool = False) -> None:
    batch_dir = out_root / "_batch_summary"
    batch_dir.mkdir(parents=True, exist_ok=True)
    out_fp = batch_dir / f"ib2d_thci_{ctx['suffix']}_integrated_case_summary.csv"
    fieldnames = [
        "case_id",
        "integrated_status",
        "thci_version",
        "left_map_mode",
        "output_html_exists",
        "output_html",
        "ib2d_formal_html_exists",
        "ib1e_formal_html_exists",
        "ib2d_formal_png_exists",
        "left_map_visual_source_type",
        "left_map_source_stage",
        "left_map_visual_source_path",
        "integration_mode",
        "elevation_profile_exists",
        "elevation_profile_source_csv",
        "elevation_color_source",
        "elevation_column",
        "left_panel_layout",
        "thci_axis_score_csv_exists",
        "thci_radar_png_exists",
        "radar_source_stage",
        "thci_radar_summary_json_exists",
        "scoring_version",
        "calibrated_from_v1_0b",
        "weather_semantics_calibrated",
        "current_recommended_display_version",
        "previous_recommended_version",
        "previous_v1_0b_weather_impact_score",
        "v1_0c_weather_impact_score",
        "weather_delta_v1_0c_minus_v1_0b",
    ]
    rows = list(case_rows)
    if merge_existing and out_fp.exists():
        with out_fp.open("r", encoding="utf-8-sig", newline="") as handle:
            existing = list(csv.DictReader(handle))
        new_case_ids = {str(row.get("case_id", "")) for row in rows}
        rows = [row for row in existing if str(row.get("case_id", "")) not in new_case_ids] + rows
    with out_fp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_map_only_html(case_id: str, source_png: Path, output_html: Path) -> str:
    png_src = _relpath_for_html(source_png, output_html)
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(case_id)} IB2D map-only review</title>
  <style>
    html, body {{ margin: 0; min-height: 100%; background: #f3f5f7; font-family: "Microsoft JhengHei", "Noto Sans CJK TC", Arial, sans-serif; color: #17202a; }}
    main {{ width: 100%; min-height: 100vh; display: flex; align-items: flex-start; justify-content: center; padding: 16px; }}
    img {{ display: block; max-width: 100%; height: auto; background: white; border: 1px solid #d9e0e7; box-shadow: 0 4px 18px rgba(23, 32, 42, 0.12); }}
  </style>
</head>
<body><main><img src="{html.escape(png_src)}" alt="IB2D route risk offline map PNG for {html.escape(case_id)}"></main></body>
</html>
"""


def write_map_only_case_outputs(case_id: str, out_root: Path) -> dict[str, Any]:
    out_dir = out_root / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    output_html = out_dir / f"{case_id}_ib2d_map_only_review.html"
    output_summary_json = out_dir / f"{case_id}_ib2d_map_only_review_summary.json"
    source_png = _find_ib2d_formal_png(case_id)
    status = "PASS" if source_png is not None else "FAIL_missing_ib2d_png"
    if source_png is not None:
        output_html.write_text(build_map_only_html(case_id, source_png, output_html), encoding="utf-8")
    if status == "PASS" and not output_html.exists():
        status = "FAIL_output_html_missing"
    summary = {
        "case_id": case_id,
        "layout_mode": "map_only",
        "left_map_mode": "ib2d-png",
        "source_type": "ib2d_png" if source_png else "missing",
        "source_stage": "IB2D_ROUTE_RISK_OFFLINE_MAP" if source_png else "",
        "source_png_path": str(source_png) if source_png else None,
        "output_html": str(output_html),
        "thci_embedded": False,
        "elevation_profile_embedded": False,
        "status": status,
        "note": "Map-only mode wraps an existing pure IB2D route risk offline map PNG. It does not read THCI outputs or elevation profile CSV.",
    }
    output_summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "case_id": case_id,
        "status": status,
        "layout_mode": "map_only",
        "left_map_mode": "ib2d-png",
        "source_type": "ib2d_png" if source_png else "missing",
        "source_stage": "IB2D_ROUTE_RISK_OFFLINE_MAP" if source_png else "",
        "source_png_path": str(source_png) if source_png else "",
        "output_html_exists": output_html.exists(),
        "output_html": str(output_html),
        "thci_embedded": False,
        "elevation_profile_embedded": False,
    }


def write_map_only_batch_summary(case_rows: list[dict[str, Any]], out_root: Path, merge_existing: bool = False) -> None:
    batch_dir = out_root / "_batch_summary"
    batch_dir.mkdir(parents=True, exist_ok=True)
    out_fp = batch_dir / "ib2d_map_only_review_case_summary.csv"
    fieldnames = [
        "case_id",
        "status",
        "layout_mode",
        "left_map_mode",
        "source_type",
        "source_stage",
        "source_png_path",
        "output_html_exists",
        "output_html",
        "thci_embedded",
        "elevation_profile_embedded",
    ]
    rows = list(case_rows)
    if merge_existing and out_fp.exists():
        with out_fp.open("r", encoding="utf-8-sig", newline="") as handle:
            existing = list(csv.DictReader(handle))
        new_case_ids = {str(row.get("case_id", "")) for row in rows}
        rows = [row for row in existing if str(row.get("case_id", "")) not in new_case_ids] + rows
    with out_fp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _resolve_out_root(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _resolve_cases(case_ids: list[str], case_list: str | None) -> tuple[list[str], bool]:
    cases = list(case_ids or [])
    if case_list:
        fp = Path(case_list)
        if not fp.is_absolute():
            fp = PROJECT_ROOT / fp
        with fp.open("r", encoding="utf-8") as handle:
            for line in handle:
                item = line.strip()
                if item and not item.startswith("#"):
                    cases.append(item)
    if not cases:
        return list(CASES), False
    return list(dict.fromkeys(cases)), True


def main() -> int:
    parser = argparse.ArgumentParser(description="Build IB2D x THCI integrated offline visualization.")
    parser.add_argument("--thci-version", choices=["v1_0b", "v1_0c"], default="v1_0c")
    parser.add_argument("--layout-mode", choices=["integrated", "map-only"], default="integrated")
    parser.add_argument("--left-map-mode", choices=["auto", "ib1e-html", "ib2d-png"], default="auto")
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT.relative_to(PROJECT_ROOT)))
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--case-list", default=None)
    args = parser.parse_args()

    out_root = _resolve_out_root(args.out_root)
    cases, is_cli_extension = _resolve_cases(args.case_id, args.case_list)
    if args.layout_mode == "map-only":
        if args.left_map_mode != "ib2d-png":
            print("ERROR: --layout-mode map-only must be used with --left-map-mode ib2d-png")
            return 2
        rows = []
        for case_id in cases:
            row = write_map_only_case_outputs(case_id, out_root)
            rows.append(row)
            print(
                f"{case_id}: {row['status']} layout_mode={row['layout_mode']} "
                f"left_map_mode={row['left_map_mode']} source_type={row['source_type']} "
                f"output_html={row['output_html']}"
            )
        write_map_only_batch_summary(rows, out_root, merge_existing=is_cli_extension)
        print("batch summary:", out_root / "_batch_summary" / "ib2d_map_only_review_case_summary.csv")
        return 1 if any(row["status"] != "PASS" for row in rows) else 0

    ctx = THCI_CONTEXTS[args.thci_version]
    rows = []
    for case_id in cases:
        row = write_case_outputs(case_id, out_root, args.left_map_mode, ctx)
        rows.append(row)
        print(
            f"{case_id}: {row['integrated_status']} "
            f"thci_version={row['thci_version']} "
            f"left_map_mode={row['left_map_mode']} "
            f"mode={row['integration_mode']} "
            f"left_source={row['left_map_visual_source_type']} "
            f"weather_v1_0c={row['v1_0c_weather_impact_score']} "
            f"output_html={row['output_html']}"
        )
    write_batch_summary(rows, out_root, ctx, merge_existing=is_cli_extension)
    print("batch summary:", out_root / "_batch_summary" / f"ib2d_thci_{ctx['suffix']}_integrated_case_summary.csv")
    return 1 if any(row["integrated_status"] != "PASS" for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
