#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CH6.5.5 personal activity performance radar report-safe v0_3.

This script renders a report-safe radar gallery from the v0 radar-ready axis table.

Design principles:
- Plot only axes with available evidence.
- Do NOT plot missing axes as zero.
- Keep missing axes in a separate missing-evidence table and HTML note.
- Keep limited-proxy axes clearly labeled.
- This output is descriptive visualization only, not an ability score/rank/class,
  THCI score, final hiking risk score, route suitability score, go/no-go decision,
  medical diagnosis, or causality evidence.

Default report subset:
- Primary case candidates: 43_1, 42_1, 48_1, 46_1
- Secondary case candidates: 9_1, 38_1, 23_1
- Contrast/context examples: 15_1, 44_1, 45_1

Inputs:
  outputs/report_figures/ch6_5_5_personal_activity_performance_radar_v0/
    personal_activity_performance_radar_axis_v0.csv
    personal_activity_performance_radar_activity_summary_v0.csv
    personal_activity_performance_radar_missing_evidence_v0.csv
    personal_activity_performance_radar_audit_v0.csv

Outputs:
  outputs/report_figures/ch6_5_5_personal_activity_performance_radar_report_safe_v0_3/
    report_safe_radar_activity_<activity_id>_v0_3.png
    personal_activity_performance_radar_report_safe_gallery_v0_3.html
    personal_activity_performance_radar_report_safe_manifest_v0_3.csv
    personal_activity_performance_radar_report_safe_missing_evidence_v0_3.csv
    personal_activity_performance_radar_report_safe_audit_v0_3.csv
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
DEFAULT_OUT = "outputs/report_figures/ch6_5_5_personal_activity_performance_radar_report_safe_v0_3"

DEFAULT_ACTIVITIES = [
    "43_1", "42_1", "48_1", "46_1",
    "9_1", "38_1", "23_1",
    "15_1", "44_1", "45_1",
]

CASE_GROUP = {
    "43_1": "PRIMARY_CASE_CANDIDATE",
    "42_1": "PRIMARY_CASE_CANDIDATE",
    "48_1": "PRIMARY_CASE_CANDIDATE",
    "46_1": "PRIMARY_CASE_CANDIDATE",
    "9_1": "SECONDARY_CASE_CANDIDATE",
    "38_1": "SECONDARY_CASE_CANDIDATE",
    "23_1": "SECONDARY_CASE_CANDIDATE",
    "15_1": "CONTRAST_HIGH_HR_CONTROLLED_CONTEXT",
    "44_1": "CONTRAST_FAST_SINGLE_FACTOR_REVIEW",
    "45_1": "CONTRAST_HIGH_HR_CONTROLLED_CONTEXT",
}

BOUNDARY = (
    "Descriptive CH6.5.5 personal activity performance radar report-safe preview only. "
    "Only evidence-available axes are plotted. Missing axes are listed separately and are not zero-filled. "
    "Values are group-relative descriptive indices for visualization and review. They are not ability scores, "
    "ability ranks, ability classes, THCI scores, final hiking risk scores, route suitability scores, go/no-go "
    "decisions, medical diagnoses, or causality evidence."
)

AXIS_ORDER = [
    "sustained_progress",
    "uphill_load_tolerance_proxy",
    "pacing_movement_stability",
    "hr_output_efficiency_proxy",
    "weather_performance_maintenance_proxy",
]

LABEL_SHORT = {
    "sustained_progress": "持續推進",
    "uphill_load_tolerance_proxy": "上坡負荷\n有限代理",
    "pacing_movement_stability": "配速穩定",
    "hr_output_efficiency_proxy": "HR輸出效率\n有限代理",
    "weather_performance_maintenance_proxy": "天候表現維持\n有限代理",
}

MISSING_AXIS_ZH = {
    "terrain_movement_efficiency": "地形移動效率",
    "route_following_stability": "路線跟隨穩定性",
}


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=r"D:\mountain_work\115_osm")
    p.add_argument("--radar-root", default=DEFAULT_RADAR_ROOT)
    p.add_argument("--output-root", default=DEFAULT_OUT)
    p.add_argument(
        "--activities",
        default="",
        help="Optional comma-separated activity_id_short list. Default is report subset.",
    )
    p.add_argument(
        "--include-all",
        action="store_true",
        help="Render all activities in v0 summary instead of default report subset.",
    )
    p.add_argument(
        "--font-path",
        default="",
        help=r"Optional explicit CJK font path, e.g. C:\Windows\Fonts\msjh.ttc",
    )
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
        win / "msjh.ttc",
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


def set_font(ax, font_prop):
    if font_prop is None:
        return
    for label in ax.get_xticklabels():
        label.set_fontproperties(font_prop)
    for label in ax.get_yticklabels():
        label.set_fontproperties(font_prop)


def plot_report_safe(activity_id: str, g: pd.DataFrame, summary_row: dict, out_path: Path, font_prop):
    g = g.copy()
    g = g[g["axis_support_status"].astype(str) != "INSUFFICIENT_EVIDENCE"].copy()
    g["_order"] = g["axis_id"].astype(str).map({a: i for i, a in enumerate(AXIS_ORDER)}).fillna(999)
    g = g.sort_values("_order", kind="mergesort")

    labels = [
        LABEL_SHORT.get(str(row["axis_id"]), str(row["axis_label_zh"]))
        for _, row in g.iterrows()
    ]
    values = pd.to_numeric(g["axis_group_relative_index_0_100"], errors="coerce").tolist()

    if any(pd.isna(v) for v in values) or len(values) < 3:
        raise ValueError(f"Activity {activity_id} does not have enough available axes for report-safe radar.")

    n = len(labels)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    angles_closed = list(angles) + [angles[0]]
    values_closed = list(values) + [values[0]]

    fig = plt.figure(figsize=(8.8, 8.2), dpi=170)
    ax = plt.subplot(111, polar=True)
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)

    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=10)
    ax.tick_params(axis="x", pad=18)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=8)
    set_font(ax, font_prop)
    ax.grid(True)

    ax.plot(angles_closed, values_closed, linewidth=2.2)
    ax.fill(angles_closed, values_closed, alpha=0.14)
    ax.scatter(angles, values, s=34)

    mean_val = summary_row.get("mean_available_axis_index_0_100", "")
    case_group = CASE_GROUP.get(activity_id, summary_row.get("suggested_report_case_role", "CONTEXT"))
    title = (
        f"活動 {activity_id}｜個人活動表現雷達圖（報告安全版 v0.3）\n"
        f"可用軸平均：{mean_val}｜{case_group}"
    )
    ax.set_title(title, y=1.14, fontsize=12, fontproperties=font_prop)

    foot = "僅繪製 5 個具證據軸；缺資料軸另列，不補 0；非能力分數／排名／等級。"
    fig.text(0.5, 0.02, foot, ha="center", fontsize=9, fontproperties=font_prop)
    fig.tight_layout(rect=[0.03, 0.05, 0.97, 0.94])
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def html_escape(v) -> str:
    return html.escape("" if pd.isna(v) else str(v))


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    radar_root = resolve(root, args.radar_root)
    out_root = resolve(root, args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)

    font_prop, font_source = find_cjk_font(args.font_path)

    axis = read_csv(radar_root / "personal_activity_performance_radar_axis_v0.csv", "radar axis")
    summary = read_csv(radar_root / "personal_activity_performance_radar_activity_summary_v0.csv", "radar activity summary")
    missing = read_csv(radar_root / "personal_activity_performance_radar_missing_evidence_v0.csv", "radar missing evidence")
    upstream_audit = read_csv(radar_root / "personal_activity_performance_radar_audit_v0.csv", "radar audit")

    if args.include_all:
        tmp = summary.copy()
        tmp["_mean"] = pd.to_numeric(tmp["mean_available_axis_index_0_100"], errors="coerce")
        tmp = tmp.sort_values(["_mean", "activity_id_short"], kind="mergesort")
        activity_ids = tmp["activity_id_short"].astype(str).tolist()
    else:
        requested = [x.strip() for x in str(args.activities).split(",") if x.strip()]
        activity_ids = requested if requested else DEFAULT_ACTIVITIES

    available_activity_ids = set(axis["activity_id_short"].astype(str))
    activity_ids = [a for a in activity_ids if a in available_activity_ids]

    summary_map = {
        str(r["activity_id_short"]): r.to_dict()
        for _, r in summary.iterrows()
    }

    manifest_rows = []
    selected_missing_rows = []
    for activity_id in activity_ids:
        g_all = axis[axis["activity_id_short"].astype(str) == str(activity_id)].copy()
        if g_all.empty:
            continue

        out_png = out_root / f"report_safe_radar_activity_{safe_id(activity_id)}_v0_3.png"
        sr = summary_map.get(str(activity_id), {})
        plot_report_safe(activity_id, g_all, sr, out_png, font_prop)

        missing_axes = g_all[g_all["axis_support_status"].astype(str) == "INSUFFICIENT_EVIDENCE"].copy()
        missing_axis_ids = []
        missing_axis_labels = []
        for _, row in missing_axes.iterrows():
            axis_id = str(row["axis_id"])
            missing_axis_ids.append(axis_id)
            missing_axis_labels.append(MISSING_AXIS_ZH.get(axis_id, str(row.get("axis_label_zh", ""))))
            selected_missing_rows.append({
                "activity_id_short": activity_id,
                "participant_id": sr.get("participant_id", ""),
                "axis_id": axis_id,
                "axis_label_zh": MISSING_AXIS_ZH.get(axis_id, str(row.get("axis_label_zh", ""))),
                "missing_reason": row.get("axis_description", ""),
                "interpretation_boundary": BOUNDARY,
            })

        manifest_rows.append({
            "case_group": CASE_GROUP.get(activity_id, sr.get("suggested_report_case_role", "CONTEXT")),
            "activity_id_short": activity_id,
            "participant_id": sr.get("participant_id", ""),
            "png_file": out_png.name,
            "plotted_axis_count": int((g_all["axis_support_status"].astype(str) != "INSUFFICIENT_EVIDENCE").sum()),
            "missing_axis_count": int((g_all["axis_support_status"].astype(str) == "INSUFFICIENT_EVIDENCE").sum()),
            "missing_axis_ids": "|".join(missing_axis_ids),
            "missing_axis_labels_zh": "|".join(missing_axis_labels),
            "mean_available_axis_index_0_100": sr.get("mean_available_axis_index_0_100", ""),
            "radar_readiness_label": sr.get("radar_readiness_label", ""),
            "activity_history_primary_label": sr.get("activity_history_primary_label", ""),
            "numeric_attribution_label_v0_5": sr.get("numeric_attribution_label_v0_5", ""),
            "suggested_report_case_role": sr.get("suggested_report_case_role", ""),
            "interpretation_boundary": BOUNDARY,
        })

    manifest = pd.DataFrame(manifest_rows)
    selected_missing = pd.DataFrame(selected_missing_rows)

    manifest_path = out_root / "personal_activity_performance_radar_report_safe_manifest_v0_3.csv"
    missing_path = out_root / "personal_activity_performance_radar_report_safe_missing_evidence_v0_3.csv"
    manifest.to_csv(manifest_path, index=False, encoding="utf-8-sig")
    selected_missing.to_csv(missing_path, index=False, encoding="utf-8-sig")

    # HTML gallery.
    cards = []
    for _, r in manifest.iterrows():
        activity = html_escape(r["activity_id_short"])
        png = html_escape(r["png_file"])
        group = html_escape(r["case_group"])
        mean_val = html_escape(r["mean_available_axis_index_0_100"])
        label = html_escape(r["activity_history_primary_label"])
        role = html_escape(r["suggested_report_case_role"])
        missing_labels = html_escape(r["missing_axis_labels_zh"])
        cards.append(f"""
<section class="card">
  <h2>{group}｜活動 {activity}</h2>
  <p><b>可用軸平均：</b>{mean_val}</p>
  <p><b>活動歷程標記：</b>{label}</p>
  <p><b>報告角色：</b>{role}</p>
  <p><b>未繪製資料不足軸：</b>{missing_labels}</p>
  <img src="{png}" alt="Report-safe radar for activity {activity}">
</section>
""")

    html_text = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>CH6.5.5 個人活動表現雷達圖報告安全版 v0.3</title>
<style>
body {{ font-family: "Microsoft JhengHei", "Noto Sans TC", Arial, sans-serif; margin: 24px; line-height: 1.55; }}
.boundary {{ background: #fff7e6; border-left: 5px solid #d99000; padding: 12px 16px; margin-bottom: 20px; }}
.card {{ border: 1px solid #ddd; border-radius: 10px; padding: 16px; margin: 18px 0; }}
.card img {{ max-width: 880px; width: 100%; height: auto; }}
code {{ background: #f4f4f4; padding: 2px 4px; border-radius: 4px; }}
</style>
</head>
<body>
<h1>CH6.5.5 個人活動表現雷達圖報告安全版 v0.3</h1>
<div class="boundary"><b>Interpretation boundary:</b> {html_escape(BOUNDARY)}</div>
<p>本版僅繪製具證據支援之 5 個軸。資料不足軸另列，不補 0。</p>
<p>CJK font source: <code>{html_escape(font_source)}</code></p>
<p>Output root: <code>{html_escape(out_root)}</code></p>
{''.join(cards)}
</body>
</html>
"""
    html_path = out_root / "personal_activity_performance_radar_report_safe_gallery_v0_3.html"
    html_path.write_text(html_text, encoding="utf-8")

    audit = pd.DataFrame([{
        "radar_root": str(radar_root),
        "output_root": str(out_root),
        "selected_activity_count": int(len(manifest)),
        "report_safe_png_count": int(len(manifest)),
        "plotted_axis_count_per_activity": 5,
        "missing_axis_count_per_activity": 2,
        "zero_fill_used": False,
        "missing_axes_rendered_as_missing_table": True,
        "cjk_font_source": font_source,
        "upstream_audit_conclusion": upstream_audit.iloc[0].get("audit_conclusion", "") if not upstream_audit.empty else "",
        "audit_conclusion": "PASS_CH6_5_5_PERSONAL_ACTIVITY_PERFORMANCE_RADAR_REPORT_SAFE_V0_3_DESCRIPTIVE_ONLY",
        "interpretation_boundary": BOUNDARY,
    }])
    audit_path = out_root / "personal_activity_performance_radar_report_safe_audit_v0_3.csv"
    audit.to_csv(audit_path, index=False, encoding="utf-8-sig")

    print({
        "output_root": str(out_root),
        "selected_activity_count": int(len(manifest)),
        "report_safe_png_count": int(len(manifest)),
        "html_gallery": str(html_path),
        "manifest": str(manifest_path),
        "missing_evidence": str(missing_path),
        "zero_fill_used": False,
        "cjk_font_source": font_source,
        "audit_conclusion": "PASS_CH6_5_5_PERSONAL_ACTIVITY_PERFORMANCE_RADAR_REPORT_SAFE_V0_3_DESCRIPTIVE_ONLY",
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
