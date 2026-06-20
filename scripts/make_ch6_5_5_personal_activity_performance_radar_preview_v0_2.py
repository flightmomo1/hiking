#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CH6.5.5 personal activity performance radar preview v0_2.

Fixes CJK text rendering in matplotlib PNGs.

Inputs:
  outputs/report_figures/ch6_5_5_personal_activity_performance_radar_v0/
    personal_activity_performance_radar_axis_v0.csv
    personal_activity_performance_radar_activity_summary_v0.csv
    personal_activity_performance_radar_audit_v0.csv

Outputs:
  outputs/report_figures/ch6_5_5_personal_activity_performance_radar_preview_v0_2/
    radar_preview_activity_<activity_id>_v0_2.png
    personal_activity_performance_radar_preview_index_v0_2.html
    personal_activity_performance_radar_preview_audit_v0_2.csv
    personal_activity_performance_radar_preview_manifest_v0_2.csv

Boundary:
Missing axes are rendered as missing and are not zero-filled. This is a
descriptive preview only, not an ability score/rank/class or go/no-go decision.
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path
import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.font_manager import FontProperties


DEFAULT_RADAR_ROOT = "outputs/report_figures/ch6_5_5_personal_activity_performance_radar_v0"
DEFAULT_OUT = "outputs/report_figures/ch6_5_5_personal_activity_performance_radar_preview_v0_2"

BOUNDARY = (
    "Descriptive CH6.5.5 personal activity performance radar preview only. "
    "Axis values are group-relative descriptive indices for visualization and review. "
    "They are not ability scores, ability ranks, ability classes, THCI scores, final hiking "
    "risk scores, route suitability scores, go/no-go decisions, medical diagnoses, or causality "
    "evidence. Missing axes are not zero-filled."
)

AXIS_ORDER = [
    "sustained_progress",
    "uphill_load_tolerance_proxy",
    "pacing_movement_stability",
    "hr_output_efficiency_proxy",
    "weather_performance_maintenance_proxy",
    "terrain_movement_efficiency",
    "route_following_stability",
]

LABEL_SHORT = {
    "sustained_progress": "持續推進",
    "uphill_load_tolerance_proxy": "上坡負荷\n有限代理",
    "pacing_movement_stability": "配速穩定",
    "hr_output_efficiency_proxy": "HR輸出效率\n有限代理",
    "weather_performance_maintenance_proxy": "天候表現維持\n有限代理",
    "terrain_movement_efficiency": "地形移動效率\n資料不足",
    "route_following_stability": "路線跟隨穩定\n資料不足",
}


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=r"D:\mountain_work\115_osm")
    p.add_argument("--radar-root", default=DEFAULT_RADAR_ROOT)
    p.add_argument("--output-root", default=DEFAULT_OUT)
    p.add_argument("--activities", default="", help="Optional comma-separated activity_id_short list.")
    p.add_argument("--max-activities", type=int, default=0, help="Optional cap; 0 means all selected activities.")
    p.add_argument("--font-path", default="", help=r"Optional explicit CJK font path, e.g. C:\Windows\Fonts\msjh.ttc")
    return p.parse_args()


def resolve(root: Path, value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else root / p


def read_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def safe_id(s) -> str:
    return str(s).replace("/", "_").replace("\\", "_").replace(":", "_").replace(" ", "_")


def find_cjk_font(explicit: str = "") -> tuple[FontProperties | None, str]:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))

    win = Path(r"C:\Windows\Fonts")
    candidates.extend([
        win / "msjh.ttc",       # Microsoft JhengHei
        win / "msjhbd.ttc",
        win / "mingliu.ttc",
        win / "kaiu.ttf",
        win / "msyh.ttc",
        win / "simhei.ttf",
        win / "simsun.ttc",
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("/System/Library/Fonts/STHeiti Light.ttc"),
        Path("/System/Library/Fonts/STHeiti Medium.ttc"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJKtc-Regular.otf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/arphic/uming.ttc"),
    ])

    for path in candidates:
        if path.exists():
            try:
                fm.fontManager.addfont(str(path))
                prop = FontProperties(fname=str(path))
                plt.rcParams["font.family"] = prop.get_name()
                plt.rcParams["axes.unicode_minus"] = False
                return prop, str(path)
            except Exception:
                pass

    fallback_names = [
        "Microsoft JhengHei",
        "Microsoft YaHei",
        "Noto Sans CJK TC",
        "Noto Sans CJK SC",
        "Noto Sans TC",
        "PingFang TC",
        "SimHei",
        "Arial Unicode MS",
    ]
    installed = {f.name for f in fm.fontManager.ttflist}
    for name in fallback_names:
        if name in installed:
            plt.rcParams["font.family"] = name
            plt.rcParams["axes.unicode_minus"] = False
            return FontProperties(family=name), f"installed:{name}"

    plt.rcParams["axes.unicode_minus"] = False
    return None, "NOT_FOUND_FALLBACK_DEFAULT_FONT"


def axis_label(axis_id: str, original: str, support_status: str) -> str:
    if axis_id in LABEL_SHORT:
        return LABEL_SHORT[axis_id]
    label = str(original)
    if support_status == "INSUFFICIENT_EVIDENCE":
        return f"{label}\n資料不足"
    if str(support_status).startswith("LIMITED"):
        return f"{label}\n有限代理"
    return label


def set_font_for_ticklabels(ax, font_prop):
    if font_prop is None:
        return
    for label in ax.get_xticklabels():
        label.set_fontproperties(font_prop)
    for label in ax.get_yticklabels():
        label.set_fontproperties(font_prop)


def plot_activity(activity_id: str, g: pd.DataFrame, summary_row: dict, out_path: Path, font_prop: FontProperties | None):
    g = g.copy()
    if "axis_id" in g.columns:
        g["_order"] = g["axis_id"].astype(str).map({a: i for i, a in enumerate(AXIS_ORDER)}).fillna(999)
        g = g.sort_values("_order", kind="mergesort")

    labels = [
        axis_label(row["axis_id"], row["axis_label_zh"], row["axis_support_status"])
        for _, row in g.iterrows()
    ]
    values_raw = pd.to_numeric(g["axis_group_relative_index_0_100"], errors="coerce").tolist()

    n = len(labels)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    available = [not pd.isna(v) for v in values_raw]
    angles_avail = [a for a, ok in zip(angles, available) if ok]
    values_avail = [v for v, ok in zip(values_raw, available) if ok]

    fig = plt.figure(figsize=(9.5, 8.5), dpi=160)
    ax = plt.subplot(111, polar=True)
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)

    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=9)
    ax.tick_params(axis="x", pad=18)
    set_font_for_ticklabels(ax, font_prop)

    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=8)
    set_font_for_ticklabels(ax, font_prop)
    ax.grid(True)

    if len(values_avail) >= 3:
        ax.plot(angles_avail + [angles_avail[0]], values_avail + [values_avail[0]], linewidth=2)
        ax.fill(angles_avail + [angles_avail[0]], values_avail + [values_avail[0]], alpha=0.15)
    elif len(values_avail) > 0:
        ax.scatter(angles_avail, values_avail, s=35)

    for a, v, ok in zip(angles, values_raw, available):
        if ok:
            ax.scatter([a], [v], s=28)
        else:
            ax.text(a, 8, "缺", ha="center", va="center", fontsize=9, fontproperties=font_prop)

    mean_val = summary_row.get("mean_available_axis_index_0_100", "")
    readiness = summary_row.get("radar_readiness_label", "")
    title = (
        f"活動 {activity_id}｜個人活動表現雷達圖預覽 v0.2\n"
        f"可用軸平均：{mean_val}｜{readiness}"
    )
    ax.set_title(title, y=1.13, fontsize=12, fontproperties=font_prop)

    foot = "邊界：描述性群組相對預覽；缺資料軸未補 0；非能力分數／排名／等級，亦非 go/no-go 判斷。"
    fig.text(0.5, 0.018, foot, ha="center", fontsize=9, fontproperties=font_prop)
    fig.tight_layout(rect=[0.03, 0.05, 0.97, 0.94])
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    radar_root = resolve(root, args.radar_root)
    out_root = resolve(root, args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)

    font_prop, font_source = find_cjk_font(args.font_path)

    axis = read_csv(radar_root / "personal_activity_performance_radar_axis_v0.csv", "radar axis")
    summary = read_csv(radar_root / "personal_activity_performance_radar_activity_summary_v0.csv", "radar activity summary")
    upstream_audit = read_csv(radar_root / "personal_activity_performance_radar_audit_v0.csv", "radar audit")

    requested = [x.strip() for x in str(args.activities).split(",") if x.strip()]
    if requested:
        activity_ids = [a for a in requested if a in set(axis["activity_id_short"].astype(str))]
    else:
        tmp = summary.copy()
        tmp["_mean"] = pd.to_numeric(tmp["mean_available_axis_index_0_100"], errors="coerce")
        tmp = tmp.sort_values(["_mean", "activity_id_short"], kind="mergesort")
        activity_ids = tmp["activity_id_short"].astype(str).tolist()

    if args.max_activities and args.max_activities > 0:
        activity_ids = activity_ids[:args.max_activities]

    summary_map = {
        str(r["activity_id_short"]): r.to_dict()
        for _, r in summary.iterrows()
    }

    manifest_rows = []
    for activity_id in activity_ids:
        g = axis[axis["activity_id_short"].astype(str) == str(activity_id)].copy()
        if g.empty:
            continue
        out_png = out_root / f"radar_preview_activity_{safe_id(activity_id)}_v0_2.png"
        plot_activity(activity_id, g, summary_map.get(str(activity_id), {}), out_png, font_prop)
        sr = summary_map.get(str(activity_id), {})
        manifest_rows.append({
            "activity_id_short": activity_id,
            "participant_id": sr.get("participant_id", ""),
            "png_file": out_png.name,
            "mean_available_axis_index_0_100": sr.get("mean_available_axis_index_0_100", ""),
            "supported_axis_count": sr.get("supported_axis_count", ""),
            "limited_proxy_axis_count": sr.get("limited_proxy_axis_count", ""),
            "insufficient_evidence_axis_count": sr.get("insufficient_evidence_axis_count", ""),
            "radar_readiness_label": sr.get("radar_readiness_label", ""),
            "activity_history_primary_label": sr.get("activity_history_primary_label", ""),
            "numeric_attribution_label_v0_5": sr.get("numeric_attribution_label_v0_5", ""),
            "suggested_report_case_role": sr.get("suggested_report_case_role", ""),
            "interpretation_boundary": BOUNDARY,
        })

    manifest = pd.DataFrame(manifest_rows)
    manifest_path = out_root / "personal_activity_performance_radar_preview_manifest_v0_2.csv"
    manifest.to_csv(manifest_path, index=False, encoding="utf-8-sig")

    cards = []
    for _, r in manifest.iterrows():
        png = html.escape(str(r["png_file"]))
        activity = html.escape(str(r["activity_id_short"]))
        role = html.escape(str(r.get("suggested_report_case_role", "")))
        readiness = html.escape(str(r.get("radar_readiness_label", "")))
        mean = html.escape(str(r.get("mean_available_axis_index_0_100", "")))
        label = html.escape(str(r.get("activity_history_primary_label", "")))
        cards.append(f"""
<section class="card">
  <h2>活動 {activity}</h2>
  <p><b>Readiness:</b> {readiness}</p>
  <p><b>Available-axis mean:</b> {mean}</p>
  <p><b>Activity-history label:</b> {label}</p>
  <p><b>Report role:</b> {role}</p>
  <img src="{png}" alt="Radar preview for activity {activity}">
</section>
""")

    html_text = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>CH6.5.5 個人活動表現雷達圖預覽 v0.2</title>
<style>
body {{ font-family: "Microsoft JhengHei", "Noto Sans TC", Arial, sans-serif; margin: 24px; line-height: 1.55; }}
.boundary {{ background: #fff7e6; border-left: 5px solid #d99000; padding: 12px 16px; margin-bottom: 20px; }}
.card {{ border: 1px solid #ddd; border-radius: 10px; padding: 16px; margin: 18px 0; }}
.card img {{ max-width: 950px; width: 100%; height: auto; }}
code {{ background: #f4f4f4; padding: 2px 4px; border-radius: 4px; }}
</style>
</head>
<body>
<h1>CH6.5.5 個人活動表現雷達圖預覽 v0.2</h1>
<div class="boundary"><b>Interpretation boundary:</b> {html.escape(BOUNDARY)}</div>
<p>Generated activities: {len(manifest)}</p>
<p>CJK font source: <code>{html.escape(font_source)}</code></p>
<p>Input root: <code>{html.escape(str(radar_root))}</code></p>
{''.join(cards)}
</body>
</html>
"""
    html_path = out_root / "personal_activity_performance_radar_preview_index_v0_2.html"
    html_path.write_text(html_text, encoding="utf-8")

    audit = pd.DataFrame([{
        "radar_root": str(radar_root),
        "output_root": str(out_root),
        "activity_count_requested_or_selected": int(len(activity_ids)),
        "preview_png_count": int(len(manifest)),
        "zero_fill_used": False,
        "missing_axes_rendered_as_missing": True,
        "cjk_font_source": font_source,
        "upstream_audit_conclusion": upstream_audit.iloc[0].get("audit_conclusion", "") if not upstream_audit.empty else "",
        "audit_conclusion": "PASS_CH6_5_5_PERSONAL_ACTIVITY_PERFORMANCE_RADAR_PREVIEW_V0_2_DESCRIPTIVE_ONLY",
        "interpretation_boundary": BOUNDARY,
    }])
    audit_path = out_root / "personal_activity_performance_radar_preview_audit_v0_2.csv"
    audit.to_csv(audit_path, index=False, encoding="utf-8-sig")

    print({
        "output_root": str(out_root),
        "preview_png_count": int(len(manifest)),
        "html_index": str(html_path),
        "manifest": str(manifest_path),
        "zero_fill_used": False,
        "cjk_font_source": font_source,
        "audit_conclusion": "PASS_CH6_5_5_PERSONAL_ACTIVITY_PERFORMANCE_RADAR_PREVIEW_V0_2_DESCRIPTIVE_ONLY",
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
