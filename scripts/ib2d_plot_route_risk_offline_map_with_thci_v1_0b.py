# -*- coding: utf-8 -*-
"""Build IB2D x THCI v1.0b integrated offline visualization.

This script does not rerun IA1/IB0/IB1/IB2D, does not recalculate THCI scores,
and does not overwrite the original IB2D, IB1E, or THCI roots.
"""

from __future__ import annotations

import csv
import html
import argparse
import json
import math
import os
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(r"C:\mountain_work\115_osm")

IB2D_ROOT = PROJECT_ROOT / "outputs" / "ib2d_route_risk_offline_map_v1_3b_contract_qa"
IB1E_TERRAIN_RISK_HTML_ROOT = (
    PROJECT_ROOT / "outputs" / "ib1e_osm_nlsc_terrain_risk_plot_v1_3b_contract_qa"
)
IB1E_ROUTE_PROFILE_ROOT = (
    PROJECT_ROOT / "outputs" / "ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa"
)
THCI_AXIS_SCORE_ROOT = PROJECT_ROOT / "outputs" / "thci_axis_scores_v1_0b"
THCI_RADAR_ROOT = PROJECT_ROOT / "outputs" / "thci_radar_v1_0b"
THCI_VERSION_COMPARISON_ROOT = PROJECT_ROOT / "outputs" / "thci_version_comparison"
DEFAULT_OUT_ROOT = PROJECT_ROOT / "outputs" / "ib2d_thci_radar_v1_0b"
DEFAULT_MAP_ONLY_OUT_ROOT = PROJECT_ROOT / "outputs" / "ib2d_map_only_v1_3b_contract_qa"

SCORING_VERSION = "v1.0b"
LEFT_PANEL_LAYOUT = "map_top_elevation_bottom"
RADAR_SOURCE_STAGE = "THCI_V1_0B_RADAR"

CASES = [
    "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b",
    "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b",
    "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b",
    "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b",
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

RISK_LEVEL = {
    "unknown": 0,
    "low": 1,
    "moderate": 2,
    "high": 3,
    "very_high": 4,
}


def _read_csv_first_row(path: Path) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
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
    if slope >= 30:
        return "very_high"
    if slope >= 20:
        return "high"
    if slope >= 10:
        return "moderate"
    return "low"


def pick_band(*bands: Any) -> str:
    best = "unknown"
    best_level = -1
    for band in bands:
        normalized = norm_band(band)
        level = RISK_LEVEL.get(normalized, 0)
        if level > best_level:
            best = normalized
            best_level = level
    return best


def find_original_ib2d_html(case_id: str) -> Path | None:
    """Find the formal IB2D HTML for a case, if available."""
    case_dir = IB2D_ROOT / case_id
    if not case_dir.exists():
        return None
    for pattern in [
        f"{case_id}_route_risk_offline_map_with_radar.html",
        f"{case_id}_route_risk_offline_map.html",
        "*route_risk_offline_map_with_radar*.html",
        "*route_risk_offline_map*.html",
        "*.html",
    ]:
        matches = sorted(case_dir.glob(pattern))
        if matches:
            return matches[0]
    return None


def _find_ib1e_formal_html(case_id: str) -> Path | None:
    case_dir = IB1E_TERRAIN_RISK_HTML_ROOT / case_id
    if not case_dir.exists():
        return None
    for pattern in [f"{case_id}_osm_nlsc_terrain_risk_map.html", "*_osm_nlsc_terrain_risk_map.html", "*.html"]:
        matches = sorted(case_dir.glob(pattern))
        if matches:
            return matches[0]
    return None


def _find_ib2d_formal_png(case_id: str) -> Path | None:
    case_dir = IB2D_ROOT / case_id
    if not case_dir.exists():
        return None
    excluded_tokens = ["with_radar", "radar", "challenge_radar", "route_challenge"]

    exact = case_dir / f"{case_id}_route_risk_offline_map.png"
    if exact.exists() and not any(token in exact.name.lower() for token in excluded_tokens):
        return exact

    candidates = []
    for path in case_dir.glob("*.png"):
        name = path.name.lower()
        if any(token in name for token in excluded_tokens):
            continue
        if "route_risk_offline_map" in name:
            candidates.append(path)

    if not candidates:
        return None

    return sorted(candidates, key=lambda path: -path.stat().st_mtime)[0]


def find_left_map_visual_source(case_id: str, left_map_mode: str = "auto") -> dict[str, Any]:
    """Resolve the left map visual source in formal fallback order."""
    ib2d_html = find_original_ib2d_html(case_id)
    ib1e_html = _find_ib1e_formal_html(case_id)
    ib2d_png = _find_ib2d_formal_png(case_id)

    if left_map_mode == "ib1e-html":
        if ib1e_html:
            return {
                "ib2d_formal_html": ib2d_html,
                "ib1e_formal_html": ib1e_html,
                "ib2d_formal_png": ib2d_png,
                "left_map_visual_source_type": "ib1e_html",
                "left_map_source_stage": "IB1E_OSM_NLSC_TERRAIN_RISK_PLOT",
                "left_map_visual_source_path": ib1e_html,
                "integration_mode": "wrapper_iframe_ib1e_html",
                "note": "left-map-mode=ib1e-html uses IB1E formal terrain risk HTML as left map visual source.",
                "missing_status": "",
            }
        return {
            "ib2d_formal_html": ib2d_html,
            "ib1e_formal_html": ib1e_html,
            "ib2d_formal_png": ib2d_png,
            "left_map_visual_source_type": "missing",
            "left_map_source_stage": "",
            "left_map_visual_source_path": None,
            "integration_mode": "fail",
            "note": "left-map-mode=ib1e-html requires IB1E formal terrain risk HTML; no fallback was applied.",
            "missing_status": "FAIL_missing_ib1e_html",
        }

    if left_map_mode == "ib2d-png":
        if ib2d_png:
            return {
                "ib2d_formal_html": ib2d_html,
                "ib1e_formal_html": ib1e_html,
                "ib2d_formal_png": ib2d_png,
                "left_map_visual_source_type": "ib2d_png",
                "left_map_source_stage": "IB2D_ROUTE_RISK_OFFLINE_MAP",
                "left_map_visual_source_path": ib2d_png,
                "integration_mode": "static_png_wrapper_ib2d",
                "note": "left-map-mode=ib2d-png uses IB2D route risk offline map PNG as left map visual source.",
                "missing_status": "",
            }
        return {
            "ib2d_formal_html": ib2d_html,
            "ib1e_formal_html": ib1e_html,
            "ib2d_formal_png": ib2d_png,
            "left_map_visual_source_type": "missing",
            "left_map_source_stage": "",
            "left_map_visual_source_path": None,
            "integration_mode": "fail",
            "note": "left-map-mode=ib2d-png requires IB2D PNG; no fallback was applied.",
            "missing_status": "FAIL_missing_ib2d_png",
        }

    if ib2d_html:
        source_type = "ib2d_html"
        return {
            "ib2d_formal_html": ib2d_html,
            "ib1e_formal_html": ib1e_html,
            "ib2d_formal_png": ib2d_png,
            "left_map_visual_source_type": source_type,
            "left_map_source_stage": "IB2D_ROUTE_RISK_OFFLINE_MAP",
            "left_map_visual_source_path": ib2d_html,
            "integration_mode": "wrapper_iframe_ib2d_html",
            "note": "Using IB2D formal HTML as left map visual source.",
            "missing_status": "",
        }
    if ib1e_html:
        return {
            "ib2d_formal_html": ib2d_html,
            "ib1e_formal_html": ib1e_html,
            "ib2d_formal_png": ib2d_png,
            "left_map_visual_source_type": "ib1e_html",
            "left_map_source_stage": "IB1E_OSM_NLSC_TERRAIN_RISK_PLOT",
            "left_map_visual_source_path": ib1e_html,
            "integration_mode": "wrapper_iframe_ib1e_html",
            "note": "IB2D formal HTML not available; using IB1E formal terrain risk HTML as left map visual source.",
            "missing_status": "",
        }
    if ib2d_png:
        return {
            "ib2d_formal_html": ib2d_html,
            "ib1e_formal_html": ib1e_html,
            "ib2d_formal_png": ib2d_png,
            "left_map_visual_source_type": "ib2d_png",
            "left_map_source_stage": "IB2D_ROUTE_RISK_OFFLINE_MAP",
            "left_map_visual_source_path": ib2d_png,
            "integration_mode": "static_png_wrapper",
            "note": "IB2D formal HTML and IB1E formal terrain risk HTML not available; using IB2D formal PNG as static left visual source.",
            "missing_status": "",
        }
    return {
        "ib2d_formal_html": ib2d_html,
        "ib1e_formal_html": ib1e_html,
        "ib2d_formal_png": ib2d_png,
        "left_map_visual_source_type": "missing",
        "left_map_source_stage": "",
        "left_map_visual_source_path": None,
        "integration_mode": "fail",
        "note": "No IB2D formal HTML, IB1E formal terrain risk HTML, or IB2D formal PNG is available.",
        "missing_status": "FAIL_missing_left_map_visual_source",
    }


def find_ib1e_route_profile_csv(case_id: str) -> Path | None:
    """Find IB1E enriched route profile CSV for elevation plotting."""
    case_dir = IB1E_ROUTE_PROFILE_ROOT / case_id
    if not case_dir.exists():
        return None
    for pattern in [
        f"{case_id}_route_profile_contour_window_terrain_enriched.csv",
        "*_route_profile_contour_window_terrain_enriched.csv",
        "*.csv",
    ]:
        matches = sorted(case_dir.glob(pattern))
        if matches:
            return matches[0]
    return None


def _choose_elevation_column(rows: list[dict[str, str]]) -> str:
    for col in ["ele_smooth", "ele_gpx_m"]:
        if any(_float_or_none(row.get(col)) is not None for row in rows):
            return col
    return "missing"


def _derive_band(row: dict[str, str]) -> tuple[str, str]:
    if row.get("risk_band"):
        return norm_band(row.get("risk_band")), "risk_band"
    if row.get("osm_terrain_combined_risk_band"):
        return norm_band(row.get("osm_terrain_combined_risk_band")), "osm_terrain_combined_risk_band"
    if row.get("risk_score"):
        return _score_to_band(row.get("risk_score")), "risk_score"
    if row.get("osm_terrain_combined_risk_score"):
        return _score_to_band(row.get("osm_terrain_combined_risk_score")), "osm_terrain_combined_risk_score"
    if row.get("slope_band"):
        return norm_band(row.get("slope_band")), "slope_band"
    if row.get("slope_pct"):
        return _slope_pct_to_band(row.get("slope_pct")), "slope_pct"
    return "unknown", "missing"


def load_route_profile_for_elevation_plot(case_id: str) -> dict[str, Any]:
    """Load route profile data and derive per-point color bands."""
    source_csv = find_ib1e_route_profile_csv(case_id)
    if source_csv is None:
        return {
            "source_csv": None,
            "exists": False,
            "points": [],
            "elevation_column": "missing",
            "elevation_color_source": "missing",
            "error": "FAIL_missing_elevation_profile_csv",
        }

    rows = _read_csv_rows(source_csv)
    elevation_col = _choose_elevation_column(rows)
    if elevation_col == "missing":
        return {
            "source_csv": source_csv,
            "exists": True,
            "points": [],
            "elevation_column": "missing",
            "elevation_color_source": "missing",
            "error": "FAIL_missing_elevation_column",
        }

    points: list[dict[str, Any]] = []
    color_sources: list[str] = []
    for row in rows:
        dist = _float_or_none(row.get("dist_m"))
        ele = _float_or_none(row.get(elevation_col))
        if dist is None or ele is None:
            continue
        band, source = _derive_band(row)
        color_sources.append(source)
        points.append(
            {
                "dist_m": dist,
                "elevation": ele,
                "band": band,
                "risk_score": row.get("risk_score") or row.get("osm_terrain_combined_risk_score") or "",
                "slope_pct": row.get("slope_pct") or "",
                "slope_band": row.get("slope_band") or "",
                "risk_band": row.get("risk_band") or row.get("osm_terrain_combined_risk_band") or band,
                "color_source": source,
            }
        )

    if len(points) < 2:
        return {
            "source_csv": source_csv,
            "exists": True,
            "points": points,
            "elevation_column": elevation_col,
            "elevation_color_source": "missing",
            "error": "FAIL_missing_elevation_color_source",
        }

    source_priority = [
        "risk_band",
        "osm_terrain_combined_risk_band",
        "risk_score",
        "osm_terrain_combined_risk_score",
        "slope_band",
        "slope_pct",
    ]
    elevation_color_source = next((src for src in source_priority if src in color_sources), "missing")
    if elevation_color_source == "missing":
        error = "FAIL_missing_elevation_color_source"
    else:
        error = ""

    return {
        "source_csv": source_csv,
        "exists": True,
        "points": points,
        "elevation_column": elevation_col,
        "elevation_color_source": elevation_color_source,
        "error": error,
    }


def build_risk_colored_elevation_profile_html(profile: dict[str, Any]) -> str:
    """Build an inline SVG risk-colored elevation profile with hover titles."""
    points = profile.get("points", [])
    if len(points) < 2:
        return """
        <div class="elevation-empty">
          <h2>Risk-colored elevation profile</h2>
          <p>Elevation profile source is missing or incomplete.</p>
        </div>
        """

    width = 1200
    height = 330
    pad_l, pad_r, pad_t, pad_b = 62, 18, 22, 48
    min_dist = min(p["dist_m"] for p in points)
    max_dist = max(p["dist_m"] for p in points)
    min_ele = min(p["elevation"] for p in points)
    max_ele = max(p["elevation"] for p in points)
    if max_dist <= min_dist:
        max_dist = min_dist + 1
    if max_ele <= min_ele:
        max_ele = min_ele + 1

    def x_scale(value: float) -> float:
        return pad_l + (value - min_dist) / (max_dist - min_dist) * (width - pad_l - pad_r)

    def y_scale(value: float) -> float:
        return height - pad_b - (value - min_ele) / (max_ele - min_ele) * (height - pad_t - pad_b)

    segments = []
    for prev, curr in zip(points[:-1], points[1:]):
        band = pick_band(prev["band"], curr["band"])
        color = RISK_COLOR.get(band, RISK_COLOR["unknown"])
        title = (
            f"dist_m: {prev['dist_m']:.1f}-{curr['dist_m']:.1f}\n"
            f"elevation: {prev['elevation']:.1f}-{curr['elevation']:.1f}\n"
            f"slope_pct: {prev['slope_pct']}\n"
            f"slope_band: {prev['slope_band']}\n"
            f"risk_band: {prev['risk_band']}\n"
            f"risk_score: {prev['risk_score']}\n"
            f"color_source: {prev['color_source']}"
        )
        segments.append(
            f'<line x1="{x_scale(prev["dist_m"]):.2f}" y1="{y_scale(prev["elevation"]):.2f}" '
            f'x2="{x_scale(curr["dist_m"]):.2f}" y2="{y_scale(curr["elevation"]):.2f}" '
            f'stroke="{color}" stroke-width="3.2" stroke-linecap="round"><title>{html.escape(title)}</title></line>'
        )

    axis = f"""
      <line x1="{pad_l}" y1="{height - pad_b}" x2="{width - pad_r}" y2="{height - pad_b}" stroke="#9aa5b1" />
      <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{height - pad_b}" stroke="#9aa5b1" />
      <text x="{pad_l}" y="{height - 14}" font-size="12" fill="#5f6b7a">{min_dist:.0f} m</text>
      <text x="{width - pad_r - 70}" y="{height - 14}" font-size="12" fill="#5f6b7a">{max_dist:.0f} m</text>
      <text x="8" y="{y_scale(min_ele):.0f}" font-size="12" fill="#5f6b7a">{min_ele:.0f} m</text>
      <text x="8" y="{y_scale(max_ele):.0f}" font-size="12" fill="#5f6b7a">{max_ele:.0f} m</text>
    """
    legend = "".join(
        f'<span><i style="background:{color}"></i>{label}</span>'
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


def load_thci_axis_scores(case_id: str) -> tuple[dict[str, Any], Path]:
    """Load precomputed THCI v1.0b axis scores without recalculation."""
    path = THCI_AXIS_SCORE_ROOT / case_id / f"{case_id}_thci_axis_scores_v1_0b.csv"
    row = _read_csv_first_row(path)
    axis_scores: dict[str, float | None] = {}
    for axis, _label in AXIS_ORDER:
        axis_scores[axis] = _float_or_none(row.get(axis))
    row["axis_scores"] = axis_scores
    return row, path


def load_thci_radar_summary(case_id: str) -> tuple[dict[str, Any], Path]:
    """Load THCI v1.0b radar summary JSON."""
    path = THCI_RADAR_ROOT / case_id / f"{case_id}_thci_radar_summary_v1_0b.json"
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle), path


def _find_thci_radar_png(case_id: str) -> Path:
    return THCI_RADAR_ROOT / case_id / f"{case_id}_thci_radar_v1_0b.png"


def _axis_score_table(axis_scores: dict[str, float | None]) -> str:
    rows = []
    for axis, label in AXIS_ORDER:
        value = axis_scores.get(axis)
        display_value = "" if value is None else f"{value:.4f}"
        rows.append(
            "<tr>"
            f"<th>{html.escape(label)}</th>"
            f"<td><code>{html.escape(axis)}</code></td>"
            f"<td>{html.escape(display_value)}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def build_thci_panel_html(
    case_id: str,
    axis_scores: dict[str, float | None],
    radar_png: Path,
    radar_summary: dict[str, Any],
    output_html: Path,
) -> str:
    """Build the right-side THCI v1.0b panel HTML."""
    radar_src = _relpath_for_html(radar_png, output_html)
    radar_project_path = radar_png.relative_to(PROJECT_ROOT).as_posix()
    previous_nav = radar_summary.get("previous_v1_0a_navigation_risk_score")
    v10b_nav = radar_summary.get("v1_0b_navigation_risk_score")
    scoring_version = radar_summary.get("scoring_version", "")
    calibrated = radar_summary.get("calibrated_from_v1_0a", True)
    navigation_calibrated = radar_summary.get("navigation_semantics_calibrated")
    nav_delta = ""
    if _float_or_none(previous_nav) is not None and _float_or_none(v10b_nav) is not None:
        nav_delta = f"{float(v10b_nav) - float(previous_nav):+.4f}"

    return f"""
      <aside class="thci-panel">
        <div class="panel-kicker">Downstream calibrated interpretation layer</div>
        <h1>THCI v1.0b</h1>
        <p class="subtitle">navigation semantics calibrated</p>
        <div class="radar-caption">THCI v1.0b radar chart for {html.escape(case_id)}</div>
        <img class="radar" src="{html.escape(radar_src)}" alt="THCI v1.0b radar chart for {html.escape(case_id)}" data-radar-source-stage="{RADAR_SOURCE_STAGE}" data-thci-radar-png="{html.escape(radar_project_path)}">

        <section>
          <h2>Six-axis scores</h2>
          <table>
            <thead><tr><th>Axis</th><th>ID</th><th>Score</th></tr></thead>
            <tbody>{_axis_score_table(axis_scores)}</tbody>
          </table>
        </section>

        <section>
          <h2>Navigation calibration</h2>
          <dl class="metrics">
            <div><dt>previous_v1_0a_navigation_risk_score</dt><dd>{html.escape(str(previous_nav))}</dd></div>
            <div><dt>v1_0b_navigation_risk_score</dt><dd>{html.escape(str(v10b_nav))}</dd></div>
            <div><dt>navigation_delta</dt><dd>{html.escape(nav_delta)}</dd></div>
            <div><dt>scoring_version</dt><dd>{html.escape(str(scoring_version))}</dd></div>
            <div><dt>radar_source_stage</dt><dd>{RADAR_SOURCE_STAGE}</dd></div>
            <div><dt>thci_radar_png</dt><dd><code>{html.escape(radar_project_path)}</code></dd></div>
            <div><dt>calibrated_from_v1_0a</dt><dd>{html.escape(str(calibrated).lower())}</dd></div>
            <div><dt>navigation_semantics_calibrated</dt><dd>{html.escape(str(navigation_calibrated).lower())}</dd></div>
            <div><dt>runtime_llm_allowed</dt><dd>false</dd></div>
          </dl>
        </section>

        <section class="boundary">
          <h2>Boundary</h2>
          <p>IB2D was not rerun. The original IB2D output remains the baseline route-risk visualization layer. THCI v1.0b is shown as a downstream calibrated six-axis interpretation layer.</p>
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
    """Build the left panel: map on top, risk-colored elevation below."""
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
    output_html: Path,
    integrated_status: str,
    integration_mode: str,
) -> str:
    """Build final local offline HTML wrapper."""
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(case_id)} IB2D x THCI v1.0b</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #17202a;
      --muted: #5f6b7a;
      --line: #d9e0e7;
      --panel: #f7f9fb;
      --accent: #355f8c;
      --warn: #a44200;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; height: 100%; font-family: "Microsoft JhengHei", "Noto Sans CJK TC", Arial, sans-serif; color: var(--ink); }}
    body {{ background: #fff; }}
    .shell {{ display: grid; grid-template-columns: minmax(0, 65%) minmax(360px, 30%); gap: 0; min-height: 100vh; }}
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
    .elevation-empty {{ padding: 16px; color: var(--warn); }}
    .missing-source {{ padding: 28px; color: var(--warn); }}
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
    .metrics div {{ display: grid; grid-template-columns: 1fr auto; gap: 12px; padding: 8px 10px; border-bottom: 1px solid var(--line); }}
    .metrics div:last-child {{ border-bottom: 0; }}
    dt {{ color: var(--muted); font-size: 12px; }}
    dd {{ margin: 0; font-weight: 700; }}
    .boundary {{ color: var(--muted); font-size: 13px; line-height: 1.55; }}
    .status {{ position: fixed; left: 12px; bottom: 12px; padding: 8px 10px; background: white; border: 1px solid var(--line); font-size: 12px; }}
    @media (max-width: 980px) {{
      .shell {{ grid-template-columns: 1fr; }}
      .left-panel {{ grid-template-rows: 65vh 35vh; }}
      .thci-panel {{ max-height: none; }}
    }}
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


def _validate_thci_inputs(axis_row: dict[str, Any] | None, axis_scores: dict[str, float | None], radar_png: Path, radar_summary: dict[str, Any] | None) -> list[str]:
    issues: list[str] = []
    if axis_row is None:
        issues.append("FAIL_missing_thci_axis_score_csv")
    else:
        if axis_row.get("scoring_version") != SCORING_VERSION:
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
        if radar_summary.get("scoring_version") != SCORING_VERSION:
            issues.append("FAIL_thci_radar_summary_scoring_version")
        if radar_summary.get("navigation_semantics_calibrated") is not True:
            issues.append("FAIL_navigation_semantics_calibrated_not_true")
        if radar_summary.get("runtime_llm_allowed") is not False:
            issues.append("FAIL_runtime_llm_allowed_not_false")
    return issues


def write_case_outputs(case_id: str, out_root: Path, left_map_mode: str) -> dict[str, Any]:
    """Write one integrated HTML and summary JSON."""
    out_dir = out_root / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    output_html = out_dir / f"{case_id}_ib2d_thci_v1_0b_integrated_map.html"
    output_summary_json = out_dir / f"{case_id}_ib2d_thci_v1_0b_integrated_summary.json"

    left_source = find_left_map_visual_source(case_id, left_map_mode)
    elevation_profile = load_route_profile_for_elevation_plot(case_id)
    elevation_html = build_risk_colored_elevation_profile_html(elevation_profile)

    radar_png = _find_thci_radar_png(case_id)
    axis_csv_path = THCI_AXIS_SCORE_ROOT / case_id / f"{case_id}_thci_axis_scores_v1_0b.csv"
    radar_summary_path = THCI_RADAR_ROOT / case_id / f"{case_id}_thci_radar_summary_v1_0b.json"

    axis_row: dict[str, Any] | None = None
    axis_scores = {axis: None for axis, _label in AXIS_ORDER}
    radar_summary: dict[str, Any] | None = None
    blocking_issues: list[str] = []

    try:
        axis_row, axis_csv_path = load_thci_axis_scores(case_id)
        axis_scores = axis_row["axis_scores"]
    except Exception as exc:
        blocking_issues.append(f"FAIL_load_thci_axis_scores:{exc}")

    try:
        radar_summary, radar_summary_path = load_thci_radar_summary(case_id)
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
    blocking_issues.extend(_validate_thci_inputs(axis_row, axis_scores, radar_png, radar_summary))

    integrated_status = "PASS" if not blocking_issues else (blocking_issues[0] if blocking_issues else "FAIL")

    panel_summary = radar_summary or {
        "previous_v1_0a_navigation_risk_score": None,
        "v1_0b_navigation_risk_score": axis_scores.get("navigation_risk_score"),
        "scoring_version": axis_row.get("scoring_version") if axis_row else "",
        "calibrated_from_v1_0a": _bool(axis_row.get("calibrated_from_v1_0a")) if axis_row else False,
        "navigation_semantics_calibrated": _bool(axis_row.get("navigation_semantics_calibrated")) if axis_row else False,
    }

    left_panel_html = build_left_panel_layout_html(case_id, left_source, elevation_html, output_html, blocking_issues)
    thci_panel_html = build_thci_panel_html(case_id, axis_scores, radar_png, panel_summary, output_html)
    wrapper = build_integrated_wrapper_html(
        case_id,
        left_panel_html,
        thci_panel_html,
        output_html,
        integrated_status,
        left_source["integration_mode"],
    )
    output_html.write_text(wrapper, encoding="utf-8")

    previous_nav = panel_summary.get("previous_v1_0a_navigation_risk_score")
    v10b_nav = panel_summary.get("v1_0b_navigation_risk_score")
    navigation_calibrated = bool(panel_summary.get("navigation_semantics_calibrated"))
    note = (
        f"{left_source['note']} Original IB2D remains the baseline route-risk visualization. "
        "THCI v1.0b is a downstream calibrated six-axis interpretation layer. This script does "
        "not rerun or overwrite IA1/IB0/IB1/IB2D outputs."
    )

    summary = {
        "case_id": case_id,
        "integrated_status": integrated_status,
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
        "thci_radar_png": str(radar_png),
        "thci_radar_png_exists": radar_png.exists(),
        "radar_source_stage": RADAR_SOURCE_STAGE,
        "thci_radar_summary_json": str(radar_summary_path),
        "output_html": str(output_html),
        "output_root": str(out_root),
        "output_summary_json": str(output_summary_json),
        "scoring_version": SCORING_VERSION,
        "navigation_semantics_calibrated": navigation_calibrated,
        "previous_v1_0a_navigation_risk_score": previous_nav,
        "v1_0b_navigation_risk_score": v10b_nav,
        "axis_scores": axis_scores,
        "runtime_llm_allowed": False,
        "input_roots": {
            "ib2d": str(IB2D_ROOT),
            "ib1e_terrain_risk_html": str(IB1E_TERRAIN_RISK_HTML_ROOT),
            "ib1e_route_profile": str(IB1E_ROUTE_PROFILE_ROOT),
            "thci_axis_scores_v1_0b": str(THCI_AXIS_SCORE_ROOT),
            "thci_radar_v1_0b": str(THCI_RADAR_ROOT),
            "thci_version_comparison": str(THCI_VERSION_COMPARISON_ROOT),
        },
        "blocking_issues": blocking_issues,
    }
    output_summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "case_id": case_id,
        "integrated_status": integrated_status,
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
        "radar_source_stage": RADAR_SOURCE_STAGE,
        "thci_radar_summary_json_exists": radar_summary_path.exists(),
        "scoring_version": SCORING_VERSION,
        "navigation_semantics_calibrated": navigation_calibrated,
        "previous_v1_0a_navigation_risk_score": previous_nav,
        "v1_0b_navigation_risk_score": v10b_nav,
    }


def write_batch_summary(case_rows: list[dict[str, Any]], out_root: Path, merge_existing: bool = False) -> None:
    """Write integrated visualization batch summary CSV."""
    batch_dir = out_root / "_batch_summary"
    batch_dir.mkdir(parents=True, exist_ok=True)
    out_fp = batch_dir / "ib2d_thci_v1_0b_integrated_case_summary.csv"
    fieldnames = [
        "case_id",
        "integrated_status",
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
        "navigation_semantics_calibrated",
        "previous_v1_0a_navigation_risk_score",
        "v1_0b_navigation_risk_score",
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
    """Build a local offline HTML review page that displays only the IB2D PNG."""
    png_src = _relpath_for_html(source_png, output_html)
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(case_id)} IB2D map-only review</title>
  <style>
    html, body {{
      margin: 0;
      min-height: 100%;
      background: #f3f5f7;
      font-family: "Microsoft JhengHei", "Noto Sans CJK TC", Arial, sans-serif;
      color: #17202a;
    }}
    main {{
      width: 100%;
      min-height: 100vh;
      display: flex;
      align-items: flex-start;
      justify-content: center;
      padding: 16px;
    }}
    img {{
      display: block;
      max-width: 100%;
      height: auto;
      background: white;
      border: 1px solid #d9e0e7;
      box-shadow: 0 4px 18px rgba(23, 32, 42, 0.12);
    }}
  </style>
</head>
<body>
  <main>
    <img src="{html.escape(png_src)}" alt="IB2D route risk offline map PNG for {html.escape(case_id)}">
  </main>
</body>
</html>
"""


def write_map_only_case_outputs(case_id: str, out_root: Path) -> dict[str, Any]:
    """Write one map-only IB2D PNG review HTML and summary JSON."""
    out_dir = out_root / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    output_html = out_dir / f"{case_id}_ib2d_map_only_review.html"
    output_summary_json = out_dir / f"{case_id}_ib2d_map_only_review_summary.json"

    source_png = _find_ib2d_formal_png(case_id)
    status = "PASS" if source_png is not None else "FAIL_missing_ib2d_png"

    if source_png is not None:
        output_html.write_text(build_map_only_html(case_id, source_png, output_html), encoding="utf-8")

    output_html_exists = output_html.exists()
    if status == "PASS" and not output_html_exists:
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
        "note": (
            "Map-only mode wraps an existing IB2D route risk offline map PNG. "
            "It does not read THCI outputs, does not read elevation profile CSV, "
            "does not rerun IB2D, and does not overwrite original IB2D roots."
        ),
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
        "output_html_exists": output_html_exists,
        "output_html": str(output_html),
        "thci_embedded": False,
        "elevation_profile_embedded": False,
    }


def write_map_only_batch_summary(case_rows: list[dict[str, Any]], out_root: Path, merge_existing: bool = False) -> None:
    """Write map-only batch summary CSV."""
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
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


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
    parser = argparse.ArgumentParser(
        description="Build IB2D x THCI v1.0b integrated offline visualization."
    )
    parser.add_argument(
        "--layout-mode",
        choices=["integrated", "map-only"],
        default="integrated",
        help="Output layout mode.",
    )
    parser.add_argument(
        "--left-map-mode",
        choices=["auto", "ib1e-html", "ib2d-png"],
        default="auto",
        help="Left map visual source mode.",
    )
    parser.add_argument(
        "--out-root",
        default=str(DEFAULT_OUT_ROOT.relative_to(PROJECT_ROOT)),
        help="Output root. Relative paths are resolved from the project root.",
    )
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--case-list", default=None)
    args = parser.parse_args()

    out_root = _resolve_out_root(args.out_root)
    cases, is_cli_extension = _resolve_cases(args.case_id, args.case_list)
    if args.layout_mode == "map-only":
        if args.left_map_mode != "ib2d-png":
            print("ERROR: --layout-mode map-only must be used with --left-map-mode ib2d-png")
            return 2
        case_rows: list[dict[str, Any]] = []
        for case_id in cases:
            row = write_map_only_case_outputs(case_id, out_root)
            case_rows.append(row)
            print(
                f"{case_id}: {row['status']} "
                f"layout_mode={row['layout_mode']} "
                f"left_map_mode={row['left_map_mode']} "
                f"source_type={row['source_type']} "
                f"output_html={row['output_html']}"
            )
        write_map_only_batch_summary(case_rows, out_root, merge_existing=is_cli_extension)
        print("batch summary:", out_root / "_batch_summary" / "ib2d_map_only_review_case_summary.csv")
        return 1 if any(row["status"] != "PASS" for row in case_rows) else 0

    case_rows: list[dict[str, Any]] = []
    for case_id in cases:
        row = write_case_outputs(case_id, out_root, args.left_map_mode)
        case_rows.append(row)
        print(
            f"{case_id}: {row['integrated_status']} "
            f"left_map_mode={row['left_map_mode']} "
            f"mode={row['integration_mode']} "
            f"left_source={row['left_map_visual_source_type']} "
            f"elevation_color_source={row['elevation_color_source']} "
            f"elevation_column={row['elevation_column']} "
            f"output_html={row['output_html']}"
        )
    write_batch_summary(case_rows, out_root, merge_existing=is_cli_extension)
    print("batch summary:", out_root / "_batch_summary" / "ib2d_thci_v1_0b_integrated_case_summary.csv")
    return 1 if any(row["integrated_status"] != "PASS" for row in case_rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
