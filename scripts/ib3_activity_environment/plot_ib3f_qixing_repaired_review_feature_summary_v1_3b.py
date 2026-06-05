"""Build a read-only IB3F qixing repaired review feature summary HTML."""

from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd


ROOT = Path("outputs/ib3f_activity_route_features_v1_3b_qixing_repaired_review")
BATCH_DIR = ROOT / "_batch_summary"
FEATURE_SUMMARY_CSV = BATCH_DIR / "ib3f_activity_route_features_summary.csv"
SMOKE_DECISION_CSV = BATCH_DIR / "ib3f_qixing_repaired_review_smoke_decision.csv"
SMOKE_SUMMARY_JSON = BATCH_DIR / "ib3f_qixing_repaired_review_smoke_summary.json"
OUT_HTML = BATCH_DIR / "ib3f_qixing_repaired_review_feature_summary.html"

DISPLAY_COLUMNS = [
    "activity_id",
    "activity_quality_flag",
    "on_route_ratio",
    "speed_available",
    "hr_available",
    "moderate_risk_ratio",
    "high_risk_ratio",
    "route_risk_join_coverage_ratio",
    "route_choice_review_required",
    "remap_review_note",
]


def require_file(path: Path, label: str) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    return path


def fmt(value: object, digits: int = 4) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def read_inputs() -> tuple[pd.DataFrame, dict[str, object], dict[str, object]]:
    require_file(FEATURE_SUMMARY_CSV, "IB3F feature summary CSV")
    require_file(SMOKE_DECISION_CSV, "IB3F smoke decision CSV")
    require_file(SMOKE_SUMMARY_JSON, "IB3F smoke summary JSON")
    summary = pd.read_csv(FEATURE_SUMMARY_CSV)
    decision_df = pd.read_csv(SMOKE_DECISION_CSV)
    decision = decision_df.iloc[0].to_dict() if not decision_df.empty else {}
    smoke_summary = json.loads(SMOKE_SUMMARY_JSON.read_text(encoding="utf-8-sig"))
    return summary, decision, smoke_summary


def quality_class(value: object) -> str:
    text = str(value)
    if text == "PASS_REVIEW_READY":
        return "pass"
    if text.startswith("REVIEW_REQUIRED"):
        return "warn"
    return "neutral"


def build_table(df: pd.DataFrame) -> str:
    missing = [col for col in DISPLAY_COLUMNS if col not in df.columns]
    if missing:
        raise KeyError(f"Feature summary missing columns: {missing}")
    header = "".join(f"<th>{html.escape(col)}</th>" for col in DISPLAY_COLUMNS)
    rows = []
    for _, row in df.iterrows():
        cells = []
        for col in DISPLAY_COLUMNS:
            value = row[col]
            if col.endswith("_ratio"):
                rendered = fmt(value)
            else:
                rendered = str(value)
            cls = quality_class(value) if col == "activity_quality_flag" else ""
            cells.append(f'<td class="{cls}">{html.escape(rendered)}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def bar_width(value: object) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, v)) * 100.0


def build_bar_chart(df: pd.DataFrame) -> str:
    metrics = [
        ("on_route_ratio", "On-route ratio", "#2563eb"),
        ("moderate_risk_ratio", "Moderate risk ratio", "#d97706"),
        ("high_risk_ratio", "High risk ratio", "#dc2626"),
    ]
    parts = ['<section class="bars">']
    for _, row in df.iterrows():
        parts.append(f"<h3>{html.escape(str(row.get('activity_id', '')))}</h3>")
        for col, label, color in metrics:
            width = bar_width(row.get(col, 0))
            parts.append(
                '<div class="bar-row">'
                f'<span class="bar-label">{html.escape(label)}</span>'
                '<div class="bar-track">'
                f'<div class="bar-fill" style="width:{width:.2f}%; background:{color};"></div>'
                "</div>"
                f'<span class="bar-value">{fmt(row.get(col, 0))}</span>'
                "</div>"
            )
    parts.append("</section>")
    return "\n".join(parts)


def build_html(df: pd.DataFrame, decision: dict[str, object], smoke_summary: dict[str, object]) -> str:
    status = str(
        decision.get(
            "ib3f_qixing_repaired_review_smoke_status",
            smoke_summary.get("ib3f_qixing_repaired_review_smoke_status", ""),
        )
    )
    table = build_table(df)
    bars = build_bar_chart(df)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>IB3F qixing repaired review feature summary</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #172033; background: #f8fafc; }}
    h1 {{ margin-bottom: 4px; }}
    .status {{ display: inline-block; padding: 6px 10px; border-radius: 6px; background: #e0f2fe; color: #075985; font-weight: 700; }}
    .note {{ max-width: 980px; line-height: 1.5; color: #334155; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 18px; background: white; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 7px 8px; font-size: 13px; vertical-align: top; }}
    th {{ background: #e2e8f0; text-align: left; }}
    td.pass {{ color: #166534; font-weight: 700; }}
    td.warn {{ color: #92400e; font-weight: 700; }}
    .bars {{ margin-top: 28px; max-width: 900px; }}
    .bars h3 {{ margin: 18px 0 8px; }}
    .bar-row {{ display: grid; grid-template-columns: 170px 1fr 70px; align-items: center; gap: 10px; margin: 6px 0; }}
    .bar-track {{ height: 16px; background: #e5e7eb; border-radius: 4px; overflow: hidden; }}
    .bar-fill {{ height: 16px; }}
    .bar-value {{ font-variant-numeric: tabular-nums; }}
    code {{ background: #e2e8f0; padding: 2px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>IB3F qixing repaired review feature summary</h1>
  <p class="status">IB3F_QIXING_REPAIRED_REVIEW_SMOKE_STATUS = {html.escape(status)}</p>
  <p class="note">
    37_1 / 33_1 = <code>PASS_REVIEW_READY</code>.
    15_1 = <code>REVIEW_REQUIRED_LOW_ON_ROUTE_RATIO</code>.
    Route-choice is not forced. This page is for feature extraction review, not route-choice classification.
  </p>
  <p class="note">
    Inputs are existing IB3F outputs only. This HTML does not rerun IB3A, IB3A2, IB3B, IB3R, or THCI.
  </p>
  <h2>Activity summary table</h2>
  {table}
  <h2>Ratio overview</h2>
  {bars}
</body>
</html>
"""


def main() -> int:
    df, decision, smoke_summary = read_inputs()
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(build_html(df, decision, smoke_summary), encoding="utf-8")
    print(f"HTML: {OUT_HTML.resolve()}")
    print(
        "status:",
        decision.get(
            "ib3f_qixing_repaired_review_smoke_status",
            smoke_summary.get("ib3f_qixing_repaired_review_smoke_status", ""),
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
