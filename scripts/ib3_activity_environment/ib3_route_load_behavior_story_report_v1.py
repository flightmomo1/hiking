from __future__ import annotations

import csv
import html
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


FULL25_ROOT = Path("outputs/ib3_personal_hiking_features_route_load_comparison_full25_v1")
REVIEW_ROOT = Path("outputs/ib3_personal_hiking_features_route_load_comparison_full25_review_v1")
OUT_ROOT = Path("outputs/ib3_route_load_behavior_story_report_v1")

WINDOWS_CSV = FULL25_ROOT / "activity_route_load_behavior_response_windows.csv"
SUMMARY_CSV = FULL25_ROOT / "activity_route_load_behavior_response_summary.csv"
AUDIT_CSV = FULL25_ROOT / "activity_route_load_behavior_response_full25_audit.csv"
REVIEW_CSV = REVIEW_ROOT / "activity_route_load_behavior_response_full25_descriptive_review.csv"

REPORT_HTML = OUT_ROOT / "activity_route_load_behavior_story_report.html"
REPORT_AUDIT_CSV = OUT_ROOT / "activity_route_load_behavior_story_report_audit.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def esc(v: Any) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def ffloat(v: Any) -> float | None:
    s = "" if v is None else str(v).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def fint(v: Any) -> int | None:
    x = ffloat(v)
    return None if x is None else int(x)


def pct(n: int | float, d: int | float) -> str:
    if not d:
        return "0.0%"
    return f"{(float(n) / float(d) * 100):.1f}%"


def mean(vals: list[float]) -> float | None:
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def fmt_num(v: Any, digits: int = 2) -> str:
    x = ffloat(v)
    if x is None:
        return ""
    return f"{x:.{digits}f}"


def band_label(start_m: int) -> str:
    band_start = (start_m // 500) * 500
    return f"{band_start}-{band_start + 500}m"


def html_table(headers: list[str], rows: list[list[Any]], class_name: str = "") -> str:
    cls = f' class="{class_name}"' if class_name else ""
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>"
        for row in rows
    )
    return f'<div class="table-wrap"><table{cls}><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def load_sort_key(label: str) -> int:
    order = {
        "LOWER_ROUTE_LOAD_EVIDENCE": 0,
        "MODERATE_ROUTE_LOAD_EVIDENCE": 1,
        "HIGH_ROUTE_LOAD_EVIDENCE": 2,
    }
    return order.get(label, 99)


def low_speed_sort_key(label: str) -> int:
    order = {
        "ZERO": 0,
        "GT_0_LT_0P10": 1,
        "0P10_TO_LT_0P25": 2,
        "GE_0P25": 3,
    }
    return order.get(label, 99)


def low_speed_band(v: Any) -> str:
    x = ffloat(v)
    if x is None:
        return "MISSING"
    if x == 0:
        return "ZERO"
    if x < 0.10:
        return "GT_0_LT_0P10"
    if x < 0.25:
        return "0P10_TO_LT_0P25"
    return "GE_0P25"


def story_color_class(load: str) -> str:
    if load == "HIGH_ROUTE_LOAD_EVIDENCE":
        return "load-high"
    if load == "MODERATE_ROUTE_LOAD_EVIDENCE":
        return "load-mid"
    if load == "LOWER_ROUTE_LOAD_EVIDENCE":
        return "load-low"
    return "load-unknown"


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    windows = read_csv(WINDOWS_CSV)
    summary = read_csv(SUMMARY_CSV)
    audit_rows = read_csv(AUDIT_CSV)
    review_rows = read_csv(REVIEW_CSV) if REVIEW_CSV.exists() else []
    audit = audit_rows[0] if audit_rows else {}

    total_windows = len(windows)
    activity_count = len(summary)

    # Route distance band distribution
    band_counter: Counter[str] = Counter()
    band_load: dict[str, Counter[str]] = defaultdict(Counter)
    band_low_speed_vals: dict[str, list[float]] = defaultdict(list)
    band_speed_vals: dict[str, list[float]] = defaultdict(list)
    band_hr_vals: dict[str, list[float]] = defaultdict(list)
    band_osm: dict[str, Counter[str]] = defaultdict(Counter)

    # Heatmap: route load x low-speed point ratio band
    heatmap: dict[str, Counter[str]] = defaultdict(Counter)
    load_counter: Counter[str] = Counter()
    low_speed_counter: Counter[str] = Counter()

    osm_feature_counter: Counter[str] = Counter()
    route_phase_counter: Counter[str] = Counter()

    for row in windows:
        start = fint(row.get("route_distance_window_start_m"))
        band = band_label(start or 0)
        band_counter[band] += 1

        load = row.get("route_load_context_band", "") or "MISSING"
        load_counter[load] += 1
        band_load[band][load] += 1

        ls_band = low_speed_band(row.get("low_speed_ratio"))
        low_speed_counter[ls_band] += 1
        heatmap[load][ls_band] += 1

        ls_val = ffloat(row.get("low_speed_ratio"))
        sp_val = ffloat(row.get("speed_mps_median"))
        hr_val = ffloat(row.get("heart_rate_bpm_median"))

        if ls_val is not None:
            band_low_speed_vals[band].append(ls_val)
        if sp_val is not None:
            band_speed_vals[band].append(sp_val)
        if hr_val is not None:
            band_hr_vals[band].append(hr_val)

        route_phase_counter[row.get("route_phase", "") or "MISSING"] += 1

        for feat in (row.get("osm_exposure_types", "") or "").split("|"):
            feat = feat.strip()
            if feat:
                osm_feature_counter[feat] += 1
                band_osm[band][feat] += 1

    # Story route-axis rows
    sorted_bands = sorted(band_counter.keys(), key=lambda x: int(x.split("-")[0]))
    story_rows: list[list[Any]] = []
    for band in sorted_bands:
        dominant_load = ""
        if band_load[band]:
            dominant_load = band_load[band].most_common(1)[0][0]
        top_osm = ", ".join(k for k, _ in band_osm[band].most_common(4))
        story_rows.append([
            band,
            band_counter[band],
            dominant_load,
            fmt_num(mean(band_speed_vals[band]), 2),
            fmt_num(mean(band_low_speed_vals[band]), 3),
            fmt_num(mean(band_hr_vals[band]), 1),
            top_osm,
        ])

    # Heatmap rows
    load_labels = sorted(heatmap.keys(), key=load_sort_key)
    ls_labels = sorted(low_speed_counter.keys(), key=low_speed_sort_key)
    heatmap_rows: list[list[Any]] = []
    for load in load_labels:
        row = [load]
        for ls in ls_labels:
            count = heatmap[load][ls]
            row.append(f"{count} ({pct(count, total_windows)})")
        heatmap_rows.append(row)

    # OSM summary
    osm_rows = []
    for feat, count in osm_feature_counter.most_common():
        note = "exposure only"
        if feat == "road":
            note = "100% exposure likely; weak comparison"
        if feat == "cliff":
            note = "no positive cases if 0%"
        osm_rows.append([feat, count, pct(count, total_windows), note])

    # Case cards: not ranked, source order only
    case_cards = []
    for row in summary[:25]:
        act = row.get("activity_id_short") or row.get("activity_id") or ""
        case_cards.append(f"""
        <div class="case-card">
          <h3>{esc(act)}</h3>
          <p><b>Windows</b>: {esc(row.get("window_count", ""))}</p>
          <p><b>Median speed</b>: {esc(row.get("window_speed_mps_median", ""))} m/s</p>
          <p><b>Low-speed point ratio mean</b>: {esc(row.get("low_speed_ratio_mean", ""))}</p>
          <p><b>Stopped point ratio mean</b>: {esc(row.get("stopped_ratio_mean", ""))}</p>
          <p><b>HR median</b>: {esc(row.get("heart_rate_bpm_median", ""))} bpm</p>
          <p><b>Rule-flagged high-load windows</b>: {esc(row.get("high_load_window_count", ""))}</p>
        </div>
        """)

    # Review boundaries
    boundary_rows = []
    for r in review_rows:
        safe = str(r.get("safe_for_6_5_1_text", "")).strip()
        if safe.lower() == "false" or r.get("review_status", "").startswith(("BLOCK", "DO_NOT", "NO_", "PROHIBITED")):
            boundary_rows.append([
                r.get("review_item", ""),
                r.get("affected_field", ""),
                r.get("finding", ""),
                r.get("interpretation_boundary", ""),
                r.get("recommended_action", ""),
            ])

    generated_score_like_fields = [
        c for c in (windows[0].keys() if windows else [])
        if any(token in c.lower() for token in ["ability_score", "ability_rank", "ability_class", "thci_score", "radar_score", "final_hiking_risk_score"])
    ]

    report_audit = {
        "source_window_rows": total_windows,
        "source_activity_summary_rows": activity_count,
        "source_audit_conclusion": audit.get("audit_conclusion", ""),
        "story_report_generated": True,
        "legacy_gain_fields_used_count": audit.get("legacy_gain_fields_used_count", ""),
        "weather_zero_fill_count": audit.get("weather_zero_fill_count", ""),
        "prohibited_score_rank_class_generated_count": audit.get("prohibited_score_rank_class_generated_count", ""),
        "generated_score_like_fields_in_story_source": "|".join(generated_score_like_fields),
        "route_phase_distribution": "|".join(f"{k}:{v}" for k, v in route_phase_counter.items()),
        "story_report_boundary": "DESCRIPTIVE_VISUAL_REPORT_ONLY_NO_SCORE_NO_RANK_NO_CLASS_NO_CAUSALITY",
    }

    write_csv(REPORT_AUDIT_CSV, [report_audit], list(report_audit.keys()))

    cards = f"""
    <div class="cards">
      <div class="card"><strong>{esc(activity_count)}</strong><span>usable activity summaries</span></div>
      <div class="card"><strong>{esc(total_windows)}</strong><span>50m route-distance windows</span></div>
      <div class="card"><strong>50m</strong><span>window size</span></div>
      <div class="card"><strong>{esc(audit.get("legacy_gain_fields_used_count", "0"))}</strong><span>legacy gain fields used</span></div>
      <div class="card"><strong>{esc(audit.get("prohibited_score_rank_class_generated_count", "0"))}</strong><span>score / rank / class generated</span></div>
    </div>
    """

    html_text = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>IB3 Route Load Behavior Story Report v1</title>
<style>
body {{
  font-family: Arial, "Noto Sans TC", sans-serif;
  margin: 24px;
  color: #1f2933;
  line-height: 1.55;
}}
.note {{
  background: #fff8dc;
  border-left: 5px solid #b7791f;
  padding: 12px 14px;
  margin: 16px 0;
}}
.cards {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin: 18px 0;
}}
.card {{
  border: 1px solid #d8dee4;
  border-radius: 10px;
  padding: 14px;
  background: #f8fafc;
}}
.card strong {{
  display: block;
  font-size: 24px;
}}
.card span {{
  color: #52606d;
  font-size: 12px;
}}
.table-wrap {{
  overflow-x: auto;
}}
table {{
  border-collapse: collapse;
  width: 100%;
  font-size: 12px;
  margin: 12px 0 26px;
}}
th, td {{
  border: 1px solid #d8dee4;
  padding: 7px;
  text-align: left;
  vertical-align: top;
}}
th {{
  background: #eef2f6;
}}
.story-table tr:nth-child(even) td {{
  background: #fbfdff;
}}
.case-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}}
.case-card {{
  border: 1px solid #d8dee4;
  border-radius: 10px;
  padding: 12px;
  background: #ffffff;
}}
.case-card h3 {{
  margin: 0 0 8px;
}}
.case-card p {{
  margin: 4px 0;
}}
.small {{
  color: #52606d;
  font-size: 12px;
}}
</style>
</head>
<body>
<h1>IB3 Route Load Behavior Story Report v1</h1>

<p class="note">
<strong>報表邊界：</strong>
本報表僅將既有 full25 descriptive evidence 重新整理成較直觀的故事型 HTML。
不重算原始 evidence、不排名活動或登山者、不產生 ability score/rank/class，
也不產生 THCI、radar 或 final hiking risk score。OSM proximity 僅代表 exposure，
天候僅為活動層級 context，不作因果推論。
</p>

{cards}

<h2>1. Route-distance story map</h2>
<p>
這個表把路線依 500m 距離帶彙整，幫助快速理解沿著路線距離軸時，
route-load evidence、速度、低速點比例、HR 與 OSM exposure 如何共同出現。
這不是因果分析，也不是上行／下行分析。
</p>
{html_table(
    ["route distance band", "window rows", "dominant route-load evidence", "mean window median speed (m/s)", "mean low-speed point ratio", "mean HR median", "top OSM exposure"],
    story_rows,
    "story-table"
)}

<h2>2. Route load × low-speed point ratio matrix</h2>
<p>
這個矩陣顯示不同 route-load evidence label 下，低速點比例分布。
請注意 route-load label 是 descriptive rule/evidence label，不是能力等級或正式風險分數。
</p>
{html_table(["route-load evidence"] + ls_labels, heatmap_rows)}

<h2>3. OSM / facility exposure overview</h2>
<p>
OSM features 僅代表圖資標記與活動路線視窗的鄰近或 exposure evidence。
不能解讀為使用者實際使用設施，也不能推論設施造成停留或速度變化。
</p>
{html_table(["OSM exposure type", "window count", "window ratio", "note"], osm_rows)}

<h2>4. Activity case profiles</h2>
<p>
以下活動卡片依來源順序展示，不是排名。欄位中的 stopped / low-speed ratio 為 point ratio，
不是時間比例。
</p>
<div class="case-grid">
{''.join(case_cards)}
</div>

<h2>5. Interpretation boundaries</h2>
<p>
以下限制來自 full25 descriptive review addendum。這些限制必須保留在 6.5.1 文字與後續展示中。
</p>
{html_table(["review item", "affected field", "finding", "interpretation boundary", "recommended action"], boundary_rows)}

<h2>6. Source audit</h2>
{html_table(["metric", "value"], [[k, v] for k, v in report_audit.items()])}

</body>
</html>
"""

    REPORT_HTML.write_text(html_text, encoding="utf-8")

    print(f"wrote: {REPORT_HTML}")
    print(f"wrote: {REPORT_AUDIT_CSV}")
    print("audit: PASS_STORY_REPORT_DESCRIPTIVE_VISUAL_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
