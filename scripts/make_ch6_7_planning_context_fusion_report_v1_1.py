#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build Chapter 6.7 planning context fusion v1.1 display report.

This is a presentation/reporting layer for the already generated v1.1
planning-context evidence. It reads the v1.1 CSV/MD outputs and writes an HTML
report plus a PNG summary figure. It does not recompute planning context,
route-load evidence, THCI, radar, final hiking risk, or ability scores.
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path

import matplotlib
import matplotlib.font_manager

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
import numpy as np
import pandas as pd


DEFAULT_INPUT_ROOT = "outputs/report_figures/ch6_7_planning_context_fusion_v1_1"
DEFAULT_OUTPUT_ROOT = "outputs/report_figures/ch6_7_planning_context_fusion_report_v1_1"

WINDOWS_CSV = "planning_context_route_windows_v1_1.csv"
ACTIVITY_SUMMARY_CSV = "planning_context_activity_summary_v1_1.csv"
SEGMENTS_CSV = "planning_caution_segments_v1_1.csv"
AUDIT_CSV = "planning_context_fusion_audit_v1_1.csv"
RUN_REPORT_MD = "planning_context_fusion_run_report_v1_1.md"

PNG_NAME = "planning_context_fusion_report_v1_1.png"
HTML_NAME = "planning_context_fusion_report_v1_1.html"
HEATMAP_PNG_NAME = "planning_caution_activity_route_heatmap_v1_1.png"
PROFILE_3_PNG_NAME = "planning_caution_profile_3_1_v1_1.png"
PROFILE_37_PNG_NAME = "planning_caution_profile_37_1_v1_1.png"

LEVEL_ORDER = [
    "ROUTINE_PLANNING_CONTEXT",
    "REVIEW_FOR_CONSERVATIVE_PLANNING",
    "CONSERVATIVE_PLANNING_RECOMMENDED",
    "TURNAROUND_CONDITION_REVIEW_RECOMMENDED",
]

BAND_ORDER = [
    "LOWER_ROUTE_LOAD_CONTEXT",
    "MODERATE_ROUTE_LOAD_CONTEXT",
    "HIGH_ROUTE_LOAD_CONTEXT",
    "VERY_HIGH_ROUTE_LOAD_CONTEXT",
]

LEVEL_COLORS = {
    "ROUTINE_PLANNING_CONTEXT": "#2E7D32",
    "REVIEW_FOR_CONSERVATIVE_PLANNING": "#F59E0B",
    "CONSERVATIVE_PLANNING_RECOMMENDED": "#DC2626",
    "TURNAROUND_CONDITION_REVIEW_RECOMMENDED": "#7C2D12",
}


LEVEL_LABELS_ZH = {
    "ROUTINE_PLANNING_CONTEXT": "例行規劃",
    "REVIEW_FOR_CONSERVATIVE_PLANNING": "保守檢核",
    "CONSERVATIVE_PLANNING_RECOMMENDED": "建議保守規劃",
    "TURNAROUND_CONDITION_REVIEW_RECOMMENDED": "折返條件檢核建議",
}

BAND_LABELS_ZH = {
    "LOWER_ROUTE_LOAD_CONTEXT": "較低負荷",
    "MODERATE_ROUTE_LOAD_CONTEXT": "中等負荷",
    "HIGH_ROUTE_LOAD_CONTEXT": "高負荷",
    "VERY_HIGH_ROUTE_LOAD_CONTEXT": "非常高負荷",
}

FORBIDDEN_OUTPUT_COLUMNS = {
    "ability_score",
    "ability_rank",
    "ability_class",
    "thci_score",
    "radar_score",
    "final_hiking_risk_score",
    "route_suitability_score",
    "personal_fitness_score",
}

BOUNDARY_TEXT = (
    "本報表為描述性行程規劃脈絡展示層，不產生能力分數、能力排名、能力等級、"
    "THCI 分數、雷達分數、最終登山風險分數、路線適合度分數或個人體能分數。"
    "天候資料除非具備安全的 route-window 對應來源，否則僅作為 activity-level 背景。"
    "IB3D 事件僅為註解證據，不作因果判定。OSM proximity 不代表實際設施使用。"
)

def setup_matplotlib_font() -> None:
    preferred_fonts = [
        "Microsoft JhengHei",
        "Noto Sans CJK TC",
        "Noto Sans TC",
        "SimHei",
        "Arial Unicode MS",
    ]
    available = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
    for font in preferred_fonts:
        if font in available:
            plt.rcParams["font.family"] = font
            break
    plt.rcParams["axes.unicode_minus"] = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=r"D:\mountain_work\115_osm")
    parser.add_argument("--input-root", default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def read_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [str(col).strip() for col in df.columns]
    return df


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def parse_distribution(text: object) -> dict[str, int]:
    if pd.isna(text):
        return {}
    out: dict[str, int] = {}
    for part in str(text).split("|"):
        if ":" not in part:
            continue
        key, value = part.strip().rsplit(":", 1)
        try:
            out[key.strip()] = int(float(value.strip()))
        except ValueError:
            continue
    return out


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def html_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    view = df.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    return view.to_html(index=False, escape=True, border=0, classes="data-table")


def pct(value: float) -> str:
    if pd.isna(value):
        return ""
    return f"{value:.1%}"


def build_png(
    windows: pd.DataFrame,
    activity_summary: pd.DataFrame,
    segments: pd.DataFrame,
    audit: pd.DataFrame,
    png_path: Path,
) -> None:
    audit_row = audit.iloc[0]
    v1_dist = parse_distribution(audit_row.get("v1_planning_caution_level_distribution", ""))
    v11_dist = parse_distribution(audit_row.get("planning_caution_level_distribution", ""))

    fig, axes = plt.subplots(2, 2, figsize=(15, 10), constrained_layout=True)
    
    fig.suptitle(
        "第 6.7 節 路線規劃脈絡整合 v1.1\n"
        "描述性行程規劃證據，不作為能力或風險評分",
        fontsize=15,
        fontweight="bold",
    )

    # Panel 1: v1 vs v1.1 distribution.
    ax = axes[0, 0]
    x = np.arange(len(LEVEL_ORDER))
    width = 0.36
    ax.bar(
        x - width / 2,
        [v1_dist.get(level, 0) for level in LEVEL_ORDER],
        width,
        label="v1",
        color="#CBD5E1",
        edgecolor="#64748B",
    )
    ax.bar(
        x + width / 2,
        [v11_dist.get(level, 0) for level in LEVEL_ORDER],
        width,
        label="v1.1",
        color=[LEVEL_COLORS[level] for level in LEVEL_ORDER],
        edgecolor="#334155",
    )

    ax.set_title("規劃提醒等級分布")
    ax.set_ylabel("50 公尺視窗數")
    ax.set_xticks(x)
    ax.set_xticklabels(
        ["例行規劃", "保守檢核", "建議保守\n規劃", "折返條件\n檢核建議"], rotation=0
    )
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.25)

    # Panel 2: route-load band x caution level.
    ax = axes[0, 1]
    cross = pd.crosstab(windows["route_load_context_band"], windows["planning_caution_level"])
    cross = cross.reindex(index=BAND_ORDER, columns=LEVEL_ORDER, fill_value=0)
    bottom = np.zeros(len(cross))
    for level in LEVEL_ORDER:
        values = cross[level].to_numpy()
        ax.bar(
            np.arange(len(cross)),
            values,
            bottom=bottom,
            label=LEVEL_LABELS_ZH.get(level, level),
            color=LEVEL_COLORS[level],
            edgecolor="white",
            linewidth=0.4,
        )
        bottom += values
    ax.set_title("路線負荷背景 × 規劃提醒等級")
    ax.set_ylabel("50 公尺視窗數")
    ax.set_xticks(np.arange(len(cross)))
    ax.set_xticklabels(["較低負荷", "中等負荷", "高負荷", "非常高負荷"], rotation=0)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False, fontsize=8)

    # Panel 3: activity-level stacked caution composition.
    ax = axes[1, 0]
    stack_cols = [
        "routine_planning_context_windows_n",
        "review_for_conservative_planning_windows_n",
        "conservative_planning_recommended_windows_n",
        "turnaround_condition_review_windows_n",
    ]
    plot_df = activity_summary.copy()
    for col in stack_cols:
        plot_df[col] = numeric(plot_df[col]).fillna(0)

    plot_df["non_routine_ratio"] = 1 - (
        plot_df["routine_planning_context_windows_n"]
        / numeric(plot_df["windows_n"]).replace(0, np.nan)
    )

    top = plot_df.sort_values("non_routine_ratio", ascending=False).head(12)
    y = np.arange(len(top))
    left = np.zeros(len(top))

    col_to_level = {
        "routine_planning_context_windows_n": "ROUTINE_PLANNING_CONTEXT",
        "review_for_conservative_planning_windows_n": "REVIEW_FOR_CONSERVATIVE_PLANNING",
        "conservative_planning_recommended_windows_n": "CONSERVATIVE_PLANNING_RECOMMENDED",
        "turnaround_condition_review_windows_n": "TURNAROUND_CONDITION_REVIEW_RECOMMENDED",
    }

    for col in stack_cols:
        level = col_to_level[col]
        values = top[col].to_numpy()
        ax.barh(
            y,
            values,
            left=left,
            color=LEVEL_COLORS[level],
            edgecolor="white",
            linewidth=0.4,
            label=LEVEL_LABELS_ZH[level],
        )
        left += values

    ax.set_yticks(y)
    ax.set_yticklabels(top["activity_id_short"].astype(str))
    ax.invert_yaxis()
    ax.set_title("各活動規劃提醒等級組成（前 12 筆）")
    ax.set_xlabel("50 公尺視窗數")
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax.grid(axis="x", alpha=0.25)

    # Panel 4: segment length by caution level.
    ax = axes[1, 1]
    seg = segments.copy()
    seg["segment_length_m"] = numeric(seg["segment_end_m"]) - numeric(seg["segment_start_m"])
    box_data = [
        seg.loc[seg["dominant_planning_caution_level"].eq(level), "segment_length_m"].dropna()
        for level in LEVEL_ORDER
    ]
    labels = ["例行規劃", "保守檢核", "建議保守\n規劃", "折返條件\n檢核建議"]
    bp = ax.boxplot(box_data, tick_labels=labels, patch_artist=True, showfliers=False)
    for patch, level in zip(bp["boxes"], LEVEL_ORDER):
        patch.set_facecolor(LEVEL_COLORS[level])
        patch.set_alpha(0.75)
    ax.set_title("規劃提醒區段長度分布")
    ax.set_ylabel("區段長度（m）")
    ax.grid(axis="y", alpha=0.25)

    fig.text(0.01, 0.01, BOUNDARY_TEXT, fontsize=8, color="#334155")
    fig.savefig(png_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def build_heatmap_png(windows: pd.DataFrame, png_path: Path) -> None:
    df = windows.copy()
    df["route_distance_km"] = numeric(df["route_distance_window_start_m"]) / 1000.0
    df["level_code"] = df["planning_caution_level"].map(
        {
            "ROUTINE_PLANNING_CONTEXT": 0,
            "REVIEW_FOR_CONSERVATIVE_PLANNING": 1,
            "CONSERVATIVE_PLANNING_RECOMMENDED": 2,
            "TURNAROUND_CONDITION_REVIEW_RECOMMENDED": 3,
        }
    )

    pivot = df.pivot_table(
        index="activity_id_short",
        columns="route_distance_km",
        values="level_code",
        aggfunc="max",
    ).sort_index()

    cmap = ListedColormap([LEVEL_COLORS[level] for level in LEVEL_ORDER])
    norm = BoundaryNorm([-0.5, 0.5, 1.5, 2.5, 3.5], cmap.N)

    fig, ax = plt.subplots(figsize=(14, 8))
    im = ax.imshow(pivot.to_numpy(), aspect="auto", interpolation="nearest", cmap=cmap, norm=norm)

    ax.set_title("活動 × 路線距離 規劃提醒熱圖 v1.1")
    ax.set_xlabel("路線距離（km）")
    ax.set_ylabel("活動 ID")

    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index.astype(str), fontsize=8)

    step = max(1, len(pivot.columns) // 10)
    xticks = np.arange(0, len(pivot.columns), step)
    ax.set_xticks(xticks)
    ax.set_xticklabels([f"{pivot.columns[i]:.1f}" for i in xticks])

    cbar = fig.colorbar(im, ax=ax, ticks=[0, 1, 2, 3])
    cbar.ax.set_yticklabels([LEVEL_LABELS_ZH[level] for level in LEVEL_ORDER])

    fig.text(0.01, 0.01, "描述性行程規劃證據，不作為能力或風險評分。", fontsize=8, color="#334155")
    fig.savefig(png_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def build_activity_profile_png(windows: pd.DataFrame, activity_id: str, png_path: Path) -> None:
    df = windows[windows["activity_id_short"].astype(str).eq(activity_id)].copy()
    if df.empty:
        return

    df = df.sort_values("route_distance_window_start_m")
    x0 = numeric(df["route_distance_window_start_m"]) / 1000.0
    x1 = numeric(df["route_distance_window_end_m"]) / 1000.0
    levels = df["planning_caution_level"].astype(str)

    fig, ax = plt.subplots(figsize=(14, 3.8))

    for start, end, level in zip(x0, x1, levels):
        ax.axvspan(
            start,
            end,
            color=LEVEL_COLORS.get(level, "#CBD5E1"),
            alpha=0.85,
        )

    if "route_load_context_index_0_100" in df.columns:
        ax2 = ax.twinx()
        ax2.plot(
            (x0 + x1) / 2,
            numeric(df["route_load_context_index_0_100"]),
            linewidth=1.2,
            color="black",
            alpha=0.75,
            label="路線負荷背景指標",
        )
        ax2.set_ylabel("路線負荷背景指標")
        ax2.set_ylim(0, 105)

    if "is_route_load_behavior_candidate" in df.columns:
        cand = df[df["is_route_load_behavior_candidate"].astype(str).str.lower().isin(["true", "1", "yes"])]
        if not cand.empty:
            cx = (numeric(cand["route_distance_window_start_m"]) + numeric(cand["route_distance_window_end_m"])) / 2000.0
            ax.scatter(cx, [0.5] * len(cx), marker="|", s=120, color="black", label="可能吃力候選視窗")

    if "event_annotation_flags" in df.columns:
        ev = df[~df["event_annotation_flags"].astype(str).isin(["", "NONE", "nan"])]
        if not ev.empty:
            ex = (numeric(ev["route_distance_window_start_m"]) + numeric(ev["route_distance_window_end_m"])) / 2000.0
            ax.scatter(ex, [0.8] * len(ex), marker="v", s=24, color="#111827", label="事件註解")

    ax.set_title(f"活動 {activity_id} 規劃提醒剖面 v1.1")
    ax.set_xlabel("路線距離（km）")
    ax.set_yticks([])
    ax.set_xlim(float(x0.min()), float(x1.max()))

    handles = [
        plt.Line2D([0], [0], color=LEVEL_COLORS[level], lw=8, label=LEVEL_LABELS_ZH[level])
        for level in LEVEL_ORDER
    ]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=4, frameon=False)

    fig.text(0.01, 0.01, "背景帶為 planning caution level；黑線為路線負荷背景指標。", fontsize=8, color="#334155")
    fig.savefig(png_path, dpi=220, bbox_inches="tight")
    plt.close(fig)



def build_html(
    windows: pd.DataFrame,
    activity_summary: pd.DataFrame,
    segments: pd.DataFrame,
    audit: pd.DataFrame,
    run_report_text: str,
    png_path: Path,
    html_path: Path,
) -> None:
    audit_row = audit.iloc[0]
    forbidden_present = sorted(
        FORBIDDEN_OUTPUT_COLUMNS
        & (set(windows.columns) | set(activity_summary.columns) | set(segments.columns))
    )

    level_dist = (
        windows["planning_caution_level"]
        .value_counts()
        .reindex(LEVEL_ORDER, fill_value=0)
        .rename_axis("planning_caution_level")
        .reset_index(name="window_count")
    )
    band_level = pd.crosstab(
        windows["route_load_context_band"], windows["planning_caution_level"]
    ).reindex(index=BAND_ORDER, columns=LEVEL_ORDER, fill_value=0).reset_index()

    activity_view = activity_summary.copy()
    activity_view["planning_caution_window_ratio"] = numeric(
        activity_view["planning_caution_window_ratio"]
    ).map(pct)
    activity_view["turnaround_condition_review_window_ratio"] = numeric(
        activity_view["turnaround_condition_review_window_ratio"]
    ).map(pct)
    activity_view = activity_view[
        [
            "activity_id_short",
            "windows_n",
            "candidate_windows_n",
            "routine_planning_context_windows_n",
            "review_for_conservative_planning_windows_n",
            "conservative_planning_recommended_windows_n",
            "turnaround_condition_review_windows_n",
            "planning_caution_window_ratio",
            "turnaround_condition_review_window_ratio",
            "event_annotation_windows_n",
        ]
    ]

    seg_view = segments.copy()
    seg_view["segment_length_m"] = numeric(seg_view["segment_end_m"]) - numeric(
        seg_view["segment_start_m"]
    )
    seg_view = seg_view.sort_values(
        ["dominant_planning_caution_level", "segment_length_m"],
        ascending=[True, False],
    )[
        [
            "activity_id_short",
            "segment_start_m",
            "segment_end_m",
            "segment_length_m",
            "dominant_planning_caution_level",
            "dominant_route_load_context_band",
            "planning_caution_reason_flags_merged",
        ]
    ]

    four_layer_table = pd.DataFrame(
        [
            {
                "層級": "A. 路線負荷證據",
                "系統使用方式": "作為規劃提醒主線，描述坡度、高程、階梯、地形、支援、暴露與路線敏感脈絡。",
                "是否可單獨提高提醒等級": "可以",
                "說明": "但仍屬描述性規劃證據，不是最終風險分數。",
            },
            {
                "層級": "B. 天候情境",
                "系統使用方式": "描述活動當日或預報時段之溫度、濕度、降雨、風速、陣風與 UV。",
                "是否可單獨提高提醒等級": "不可以",
                "說明": "只能在路線負荷或強 route context 存在時，加強保守規劃理由。",
            },
            {
                "層級": "C. 活動行為反應",
                "系統使用方式": "比對使用者在類似高負荷區段是否有低速、停留或高心率反應。",
                "是否可單獨提高提醒等級": "不可以",
                "說明": "它是反應證據，不回頭定義路線負荷。",
            },
            {
                "層級": "D. 事件註解",
                "系統使用方式": "標註 high-HR recovery、short pause、off-route rest 等事件。",
                "是否可單獨提高提醒等級": "不可以",
                "說明": "只作註解，不作因果判定。",
            },
        ]
    )

    css = """
    body { font-family: "Segoe UI", Arial, sans-serif; margin: 28px; color: #0f172a; }
    h1, h2 { color: #1e293b; }
    .note { background: #f8fafc; border-left: 5px solid #64748b; padding: 12px 16px; margin: 16px 0; }
    .pass { color: #166534; font-weight: 700; }
    .warn { color: #b45309; font-weight: 700; }
    .data-table { border-collapse: collapse; font-size: 12px; width: 100%; margin: 12px 0 24px; }
    .data-table th { background: #e2e8f0; text-align: left; padding: 7px; }
    .data-table td { border-bottom: 1px solid #e2e8f0; padding: 6px; vertical-align: top; }
    .metric-grid { display: grid; grid-template-columns: repeat(4, minmax(160px, 1fr)); gap: 10px; }
    .metric { background: #f1f5f9; padding: 10px 12px; border-radius: 8px; }
    .metric .label { color: #475569; font-size: 12px; }
    .metric .value { font-size: 19px; font-weight: 700; margin-top: 4px; }
    img { max-width: 100%; border: 1px solid #e2e8f0; border-radius: 8px; }
    code { background: #f1f5f9; padding: 1px 4px; border-radius: 4px; }
    """
    metrics = [
        ("route windows", audit_row.get("route_window_row_count", "")),
        ("activities", audit_row.get("activity_summary_row_count", "")),
        ("caution segments", audit_row.get("caution_segment_row_count", "")),
        ("candidate joins", audit_row.get("candidate_join_count", "")),
        ("routine windows", audit_row.get("routine_planning_context_count", "")),
        ("weather-only escalation", audit_row.get("lower_or_moderate_escalated_by_weather_only_count", "")),
        ("event-only escalation", audit_row.get("event_only_escalation_count", "")),
        ("forbidden columns", "NONE" if not forbidden_present else ", ".join(forbidden_present)),
    ]
    metric_html = "\n".join(
        f'<div class="metric"><div class="label">{html.escape(str(label))}</div>'
        f'<div class="value">{html.escape(str(value))}</div></div>'
        for label, value in metrics
    )

    rel_png = png_path.name
    rel_heatmap_png = HEATMAP_PNG_NAME
    rel_profile_3_png = PROFILE_3_PNG_NAME
    rel_profile_37_png = PROFILE_37_PNG_NAME
    run_report_excerpt = "\n".join(run_report_text.splitlines()[:80])
    status_class = (
        "pass"
        if str(audit_row.get("audit_conclusion", "")).startswith("PASS")
        and not forbidden_present
        else "warn"
    )

    page = f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <title>第 6.7 節 路線規劃脈絡整合 v1.1 報表</title>
  <style>{css}</style>
</head>
<body>
  <h1>第 6.7 節 路線規劃脈絡整合 v1.1 報表</h1>
  <p class="{status_class}">Audit: {html.escape(str(audit_row.get("audit_conclusion", "")))}</p>
  <div class="note">{html.escape(BOUNDARY_TEXT)}</div>

  <h2>Summary Metrics</h2>
  <div class="metric-grid">{metric_html}</div>

  <h2>PNG Summary Figure</h2>
  <p>Standalone PNG: <code>{html.escape(str(png_path))}</code></p>
  <img src="{html.escape(rel_png)}" alt="CH6.7 planning context fusion v1.1 summary figure">
 
  <h2>Activity × Route Distance Heatmap</h2>
  <p>顯示不同活動在標準路線距離軸上的 planning caution level 分布。</p>
  <img src="{html.escape(rel_heatmap_png)}" alt="activity route distance planning caution heatmap">

  <h2>Representative Activity Profiles</h2>
  <p>背景帶為 planning caution level，黑線為路線負荷背景指標；此圖用於說明注意區段如何落在標準路線距離軸上。</p>
  <img src="{html.escape(rel_profile_3_png)}" alt="planning caution profile 3_1">
  <br><br>
  <img src="{html.escape(rel_profile_37_png)}" alt="planning caution profile 37_1">

  <h2>Planning Caution Level Distribution</h2>
  {html_table(level_dist)}

  <h2>Route-Load Band x Planning Caution</h2>
  {html_table(band_level)}

  <h2>四層規劃脈絡架構</h2>
  {html_table(four_layer_table)}

  <h2>Activity Summary</h2>
  {html_table(activity_view)}

  <h2>Representative Planning Caution Segments</h2>
  <p>Sorted by caution level and segment length. These are descriptive planning-review segments, not risk scores.</p>
  {html_table(seg_view, max_rows=40)}

  <h2>Audit Fields</h2>
  {html_table(audit)}

  <h2>Run Report Excerpt</h2>
  <pre>{html.escape(run_report_excerpt)}</pre>
</body>
</html>
"""
    html_path.write_text(page, encoding="utf-8")


def main() -> None:
    setup_matplotlib_font()
    args = parse_args()
    root = Path(args.root)
    input_root = resolve(root, args.input_root)
    output_root = resolve(root, args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    paths = {
        "windows": input_root / WINDOWS_CSV,
        "activity_summary": input_root / ACTIVITY_SUMMARY_CSV,
        "segments": input_root / SEGMENTS_CSV,
        "audit": input_root / AUDIT_CSV,
        "run_report": input_root / RUN_REPORT_MD,
    }

    windows = read_csv(paths["windows"], "planning route windows")
    activity_summary = read_csv(paths["activity_summary"], "planning activity summary")
    segments = read_csv(paths["segments"], "planning caution segments")
    audit = read_csv(paths["audit"], "planning fusion audit")
    run_report_text = read_text(paths["run_report"])

    png_path = output_root / PNG_NAME
    heatmap_png_path = output_root / HEATMAP_PNG_NAME
    profile_3_png_path = output_root / PROFILE_3_PNG_NAME
    profile_37_png_path = output_root / PROFILE_37_PNG_NAME
    html_path = output_root / HTML_NAME

    build_png(windows, activity_summary, segments, audit, png_path)
    build_heatmap_png(windows, heatmap_png_path)
    build_activity_profile_png(windows, "3_1", profile_3_png_path)
    build_activity_profile_png(windows, "37_1", profile_37_png_path)
    build_html(windows, activity_summary, segments, audit, run_report_text, png_path, html_path)

    generated_cols = set(windows.columns) | set(activity_summary.columns) | set(segments.columns)
    forbidden_present = sorted(FORBIDDEN_OUTPUT_COLUMNS & generated_cols)
    result = {
        "script_path": str(Path(__file__).resolve()),
        "output_root": str(output_root),
        "html_report": str(html_path),
        "png_report": str(png_path),
        "heatmap_png": str(heatmap_png_path),
        "profile_3_png": str(profile_3_png_path),
        "profile_37_png": str(profile_37_png_path),
        "route_window_row_count": int(len(windows)),
        "activity_summary_row_count": int(len(activity_summary)),
        "caution_segment_row_count": int(len(segments)),
        "audit_conclusion": str(audit.iloc[0].get("audit_conclusion", "")),
        "forbidden_output_columns_present": "|".join(forbidden_present) if forbidden_present else "NONE",
    }
    print(result)


if __name__ == "__main__":
    main()
