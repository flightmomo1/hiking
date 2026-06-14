from __future__ import annotations

import csv
import html
import math
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import median


SCHEMA_VERSION = "ib3w_codis_weather_profile_report_v1"

IN_ROOT = Path("outputs/ib3w_codis_merged_context_weather_distribution_v1")
PROFILE_CSV = IN_ROOT / "activity_weather_profile_wide.csv"
VARIABLE_SUMMARY_CSV = IN_ROOT / "weather_variable_distribution_summary.csv"
ACTIVITY_SUMMARY_CSV = IN_ROOT / "activity_weather_distribution_summary.csv"

OUT_ROOT = Path("outputs/ib3w_codis_weather_profile_report_v1")
REPORT_HTML = OUT_ROOT / "ib3w_codis_weather_profile_report.html"
REPORT_TABLE_CSV = OUT_ROOT / "activity_weather_profile_report_table.csv"
REPORT_SUMMARY_CSV = OUT_ROOT / "weather_profile_report_summary.csv"

TAIWAN_TZ = timezone(timedelta(hours=8))

PROFILE_VARIABLES = [
    "temperature_c",
    "relative_humidity_pct",
    "pressure_hpa",
    "wind_speed_ms",
    "wind_gust_ms",
    "wind_direction_deg",
    "precipitation_mm",
    "sunshine_duration_min",
    "uv_index",
]

LABELS = {
    "temperature_c": "氣溫 °C",
    "relative_humidity_pct": "相對濕度 %",
    "pressure_hpa": "測站氣壓 hPa",
    "wind_speed_ms": "平均風速 m/s",
    "wind_gust_ms": "最大陣風 m/s",
    "wind_direction_deg": "風向 °",
    "precipitation_mm": "降雨量 mm",
    "sunshine_duration_min": "日照分鐘",
    "uv_index": "UV 指數",
}

NO_SCORING_TEXT = (
    "IB3W CODiS weather profile report is descriptive evidence only. "
    "It does not authorize THCI scoring, radar scoring, or final hiking risk scoring."
)


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def as_float(value: object) -> float | None:
    text = str(value).strip()
    if not text:
        return None
    try:
        value_float = float(text)
    except ValueError:
        return None
    if math.isnan(value_float):
        return None
    return value_float


def fmt(value: object, digits: int = 1) -> str:
    v = as_float(value)
    if v is None:
        return ""
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.{digits}f}".rstrip("0").rstrip(".")


def parse_bool(value: object) -> bool | None:
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return None


def parse_dt(value: object) -> datetime | None:
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(TAIWAN_TZ)


def local_time_text(value: object) -> str:
    dt = parse_dt(value)
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M")


def local_date_text(value: object) -> str:
    dt = parse_dt(value)
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d")


def activity_short_id(activity_id: str) -> str:
    return activity_id.replace("qixing_lengshuikeng_", "").replace("_biji_gpx", "")


def make_tags(row: dict[str, str]) -> list[str]:
    tags: list[str] = []

    rain = parse_bool(row.get("rain_observed", ""))
    high_humidity = parse_bool(row.get("high_humidity_observed", ""))
    wind_gust = parse_bool(row.get("wind_gust_observed", ""))

    precipitation = as_float(row.get("precipitation_mm", ""))
    rh = as_float(row.get("relative_humidity_pct", ""))
    wind_gust_value = as_float(row.get("wind_gust_ms", ""))
    sunshine = as_float(row.get("sunshine_duration_min", ""))
    uv = as_float(row.get("uv_index", ""))

    if rain is True:
        tags.append("有觀測降雨")
    elif rain is False:
        tags.append("無觀測降雨")

    if high_humidity is True:
        tags.append("高濕 ≥90%")
    elif rh is not None:
        tags.append("濕度 <90%")

    if wind_gust is True:
        tags.append("有陣風觀測")

    if wind_gust_value is not None and wind_gust_value >= 10:
        tags.append("陣風 ≥10 m/s")

    if precipitation is not None and precipitation >= 5:
        tags.append("累積降雨 ≥5 mm")

    if sunshine is not None and sunshine == 0:
        tags.append("無日照")
    elif sunshine is not None and sunshine >= 60:
        tags.append("日照 ≥60 分")

    if uv is not None and uv >= 6:
        tags.append("UV ≥6")

    return tags


def stat_values(rows: list[dict[str, str]], key: str) -> dict[str, str]:
    values = [as_float(row.get(key, "")) for row in rows]
    nums = [v for v in values if v is not None]
    if not nums:
        return {"min": "", "median": "", "mean": "", "max": ""}
    return {
        "min": fmt(min(nums)),
        "median": fmt(median(nums)),
        "mean": fmt(sum(nums) / len(nums)),
        "max": fmt(max(nums)),
    }


def max_row(rows: list[dict[str, str]], key: str) -> dict[str, str] | None:
    best = None
    best_value = None
    for row in rows:
        value = as_float(row.get(key, ""))
        if value is None:
            continue
        if best is None or value > best_value:
            best = row
            best_value = value
    return best


def min_row(rows: list[dict[str, str]], key: str) -> dict[str, str] | None:
    best = None
    best_value = None
    for row in rows:
        value = as_float(row.get(key, ""))
        if value is None:
            continue
        if best is None or value < best_value:
            best = row
            best_value = value
    return best


def esc(value: object) -> str:
    return html.escape(str(value))


def render_metric_card(title: str, value: str, subtitle: str = "") -> str:
    return (
        '<div class="metric-card">'
        f'<div class="metric-title">{esc(title)}</div>'
        f'<div class="metric-value">{esc(value)}</div>'
        f'<div class="metric-subtitle">{esc(subtitle)}</div>'
        '</div>'
    )


def render_activity_table(rows: list[dict[str, object]]) -> str:
    cols = [
        ("activity_date_taiwan", "日期"),
        ("activity_id_short", "活動"),
        ("observed_context_source_type", "來源"),
        ("temperature_c", "氣溫"),
        ("relative_humidity_pct", "濕度"),
        ("pressure_hpa", "氣壓"),
        ("wind_speed_ms", "風速"),
        ("wind_gust_ms", "陣風"),
        ("precipitation_mm", "降雨"),
        ("sunshine_duration_min", "日照"),
        ("uv_index", "UV"),
        ("descriptive_tags", "描述標籤"),
    ]

    head = "".join(f"<th>{esc(label)}</th>" for _, label in cols)
    body_parts = []
    for row in rows:
        body_parts.append("<tr>" + "".join(f"<td>{esc(row.get(key, ''))}</td>" for key, _ in cols) + "</tr>")

    return (
        '<div class="table-wrap">'
        '<table>'
        f"<thead><tr>{head}</tr></thead>"
        f"<tbody>{''.join(body_parts)}</tbody>"
        "</table>"
        "</div>"
    )


def render_variable_table(rows: list[dict[str, str]]) -> str:
    wanted = [
        "temperature_c",
        "relative_humidity_pct",
        "pressure_hpa",
        "wind_speed_ms",
        "wind_gust_ms",
        "precipitation_mm",
        "sunshine_duration_min",
        "uv_index",
    ]
    lookup = {row.get("target_variable", ""): row for row in rows}
    head = "<tr><th>變數</th><th>觀測數</th><th>缺值數</th><th>最小</th><th>中位數</th><th>平均</th><th>最大</th></tr>"
    body = []
    for key in wanted:
        row = lookup.get(key, {})
        body.append(
            "<tr>"
            f"<td>{esc(LABELS.get(key, key))}</td>"
            f"<td>{esc(row.get('numeric_observed_count', ''))}</td>"
            f"<td>{esc(row.get('missing_count', ''))}</td>"
            f"<td>{esc(fmt(row.get('min', '')))}</td>"
            f"<td>{esc(fmt(row.get('median', '')))}</td>"
            f"<td>{esc(fmt(row.get('mean', '')))}</td>"
            f"<td>{esc(fmt(row.get('max', '')))}</td>"
            "</tr>"
        )
    return '<div class="table-wrap"><table><thead>' + head + "</thead><tbody>" + "".join(body) + "</tbody></table></div>"


def render_extreme_line(label: str, row: dict[str, str] | None, key: str, suffix: str) -> str:
    if row is None:
        return f"<li><strong>{esc(label)}：</strong>無資料</li>"
    return (
        f"<li><strong>{esc(label)}：</strong>"
        f"{esc(local_date_text(row.get('activity_start_time_utc', '')))}，"
        f"{esc(activity_short_id(row.get('activity_id', '')))}，"
        f"{esc(fmt(row.get(key, '')))} {esc(suffix)}</li>"
    )


def main() -> None:
    _, profile_rows_raw = read_csv(PROFILE_CSV)
    _, variable_rows = read_csv(VARIABLE_SUMMARY_CSV)
    _, activity_rows_raw = read_csv(ACTIVITY_SUMMARY_CSV)

    if not profile_rows_raw:
        raise RuntimeError("activity weather profile is empty")

    report_rows: list[dict[str, object]] = []
    for row in profile_rows_raw:
        tags = make_tags(row)
        report_row = {
            "schema_version": SCHEMA_VERSION,
            "activity_id": row.get("activity_id", ""),
            "activity_id_short": activity_short_id(row.get("activity_id", "")),
            "activity_date_taiwan": local_date_text(row.get("activity_start_time_utc", "")),
            "activity_start_taiwan": local_time_text(row.get("activity_start_time_utc", "")),
            "activity_end_taiwan": local_time_text(row.get("activity_end_time_utc", "")),
            "observed_context_source_type": row.get("observed_context_source_type", ""),
            "observed_variable_count": row.get("observed_variable_count", ""),
            "unavailable_variable_count": row.get("unavailable_variable_count", ""),
            "temperature_c": fmt(row.get("temperature_c", "")),
            "relative_humidity_pct": fmt(row.get("relative_humidity_pct", "")),
            "pressure_hpa": fmt(row.get("pressure_hpa", "")),
            "wind_speed_ms": fmt(row.get("wind_speed_ms", "")),
            "wind_gust_ms": fmt(row.get("wind_gust_ms", "")),
            "wind_direction_deg": fmt(row.get("wind_direction_deg", "")),
            "precipitation_mm": fmt(row.get("precipitation_mm", "")),
            "sunshine_duration_min": fmt(row.get("sunshine_duration_min", "")),
            "uv_index": fmt(row.get("uv_index", "")),
            "rain_observed": row.get("rain_observed", ""),
            "high_humidity_observed": row.get("high_humidity_observed", ""),
            "wind_gust_observed": row.get("wind_gust_observed", ""),
            "descriptive_tags": "、".join(tags),
            "codis_selected_station_names": row.get("codis_selected_station_names", ""),
            "thci_scoring_authorized": "False",
            "radar_scoring_authorized": "False",
            "final_hiking_risk_scoring_authorized": "False",
            "authorization_reason": NO_SCORING_TEXT,
        }
        report_rows.append(report_row)

    report_rows.sort(key=lambda r: (str(r["activity_date_taiwan"]), str(r["activity_start_taiwan"]), str(r["activity_id"])))

    activity_count = len(report_rows)
    observed_row_count = sum(int(str(row.get("observed_variable_count", "0")) or "0") for row in report_rows)

    high_humidity_count = sum(1 for row in report_rows if parse_bool(row.get("high_humidity_observed")) is True)
    rain_observed_count = sum(1 for row in report_rows if parse_bool(row.get("rain_observed")) is True)
    no_rain_observed_count = sum(1 for row in report_rows if parse_bool(row.get("rain_observed")) is False)

    direct_or_mixed_count = sum(
        1 for row in report_rows
        if "DIRECT" in str(row.get("observed_context_source_type", ""))
        or "MIXED" in str(row.get("observed_context_source_type", ""))
    )
    codis_only_count = sum(
        1 for row in report_rows
        if str(row.get("observed_context_source_type", "")) == "OBSERVED_HISTORICAL_CODIS"
    )

    warmest = max_row(profile_rows_raw, "temperature_c")
    most_humid = max_row(profile_rows_raw, "relative_humidity_pct")
    strongest_gust = max_row(profile_rows_raw, "wind_gust_ms")
    wettest = max_row(profile_rows_raw, "precipitation_mm")
    least_sunshine = min_row(profile_rows_raw, "sunshine_duration_min")
    highest_uv = max_row(profile_rows_raw, "uv_index")

    variable_stats = {key: stat_values(profile_rows_raw, key) for key in PROFILE_VARIABLES}

    summary_rows = [
        {
            "schema_version": SCHEMA_VERSION,
            "activity_count": activity_count,
            "observed_weather_value_count": observed_row_count,
            "codis_only_activity_count": codis_only_count,
            "direct_or_mixed_activity_count": direct_or_mixed_count,
            "high_humidity_activity_count": high_humidity_count,
            "rain_observed_activity_count": rain_observed_count,
            "no_rain_observed_activity_count": no_rain_observed_count,
            "max_temperature_c": variable_stats["temperature_c"]["max"],
            "median_temperature_c": variable_stats["temperature_c"]["median"],
            "max_relative_humidity_pct": variable_stats["relative_humidity_pct"]["max"],
            "median_relative_humidity_pct": variable_stats["relative_humidity_pct"]["median"],
            "max_wind_gust_ms": variable_stats["wind_gust_ms"]["max"],
            "median_wind_gust_ms": variable_stats["wind_gust_ms"]["median"],
            "max_precipitation_mm": variable_stats["precipitation_mm"]["max"],
            "median_precipitation_mm": variable_stats["precipitation_mm"]["median"],
            "max_uv_index": variable_stats["uv_index"]["max"],
            "median_uv_index": variable_stats["uv_index"]["median"],
            "zero_fallback_used": "False",
            "thci_scoring_authorized": "False",
            "radar_scoring_authorized": "False",
            "final_hiking_risk_scoring_authorized": "False",
            "report_conclusion": "PASS_DESCRIPTIVE_EVIDENCE_REPORT_ONLY",
        }
    ]

    report_fields = [
        "schema_version",
        "activity_id",
        "activity_id_short",
        "activity_date_taiwan",
        "activity_start_taiwan",
        "activity_end_taiwan",
        "observed_context_source_type",
        "observed_variable_count",
        "unavailable_variable_count",
        "temperature_c",
        "relative_humidity_pct",
        "pressure_hpa",
        "wind_speed_ms",
        "wind_gust_ms",
        "wind_direction_deg",
        "precipitation_mm",
        "sunshine_duration_min",
        "uv_index",
        "rain_observed",
        "high_humidity_observed",
        "wind_gust_observed",
        "descriptive_tags",
        "codis_selected_station_names",
        "thci_scoring_authorized",
        "radar_scoring_authorized",
        "final_hiking_risk_scoring_authorized",
        "authorization_reason",
    ]

    summary_fields = list(summary_rows[0].keys())

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    write_csv(REPORT_TABLE_CSV, report_fields, report_rows)
    write_csv(REPORT_SUMMARY_CSV, summary_fields, summary_rows)

    html_text = f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <title>IB3W CODiS Weather Profile Report v1</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans TC", Arial, sans-serif;
      margin: 28px;
      color: #1f2937;
      background: #f8fafc;
    }}
    h1, h2, h3 {{ color: #0f172a; }}
    .note {{
      padding: 12px 16px;
      background: #fff7ed;
      border-left: 5px solid #f97316;
      margin: 18px 0;
      line-height: 1.6;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 12px;
      margin: 18px 0 26px;
    }}
    .metric-card {{
      background: white;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 14px 16px;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
    }}
    .metric-title {{
      font-size: 13px;
      color: #64748b;
      margin-bottom: 8px;
    }}
    .metric-value {{
      font-size: 26px;
      font-weight: 700;
      color: #0f172a;
    }}
    .metric-subtitle {{
      font-size: 12px;
      color: #64748b;
      margin-top: 6px;
    }}
    .table-wrap {{
      overflow-x: auto;
      background: white;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      margin: 12px 0 28px;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      min-width: 960px;
      font-size: 13px;
    }}
    th, td {{
      border-bottom: 1px solid #e2e8f0;
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
      white-space: nowrap;
    }}
    th {{
      background: #f1f5f9;
      color: #334155;
      font-weight: 700;
      position: sticky;
      top: 0;
    }}
    tr:hover td {{ background: #f8fafc; }}
    ul {{ line-height: 1.8; }}
    .small {{ color: #64748b; font-size: 12px; }}
    .footer {{ margin-top: 30px; color: #64748b; font-size: 12px; }}
  </style>
</head>
<body>
  <h1>IB3W CODiS Weather Profile Report v1</h1>
  <div class="note">
    <strong>邊界：</strong>{esc(NO_SCORING_TEXT)}
    本報告只將 IB3W CODiS merged context 轉成可讀的天候輪廓；描述標籤不是風險分數。
  </div>

  <h2>總覽</h2>
  <div class="cards">
    {render_metric_card("活動數", str(activity_count), "27 activities")}
    {render_metric_card("觀測天候值", str(observed_row_count), "27 × 9 variables")}
    {render_metric_card("CODiS-only 活動", str(codis_only_count), "2024 historical")}
    {render_metric_card("Direct/Mixed 活動", str(direct_or_mixed_count), "2026 direct + CODiS")}
    {render_metric_card("高濕活動", str(high_humidity_count), "RH ≥ 90%")}
    {render_metric_card("有降雨活動", str(rain_observed_count), "precipitation > 0")}
    {render_metric_card("無降雨活動", str(no_rain_observed_count), "precipitation = 0")}
    {render_metric_card("最大陣風", variable_stats["wind_gust_ms"]["max"] + " m/s", "descriptive only")}
  </div>

  <h2>天候變數分布</h2>
  {render_variable_table(variable_rows)}

  <h2>極值摘要</h2>
  <ul>
    {render_extreme_line("最高氣溫", warmest, "temperature_c", "°C")}
    {render_extreme_line("最高濕度", most_humid, "relative_humidity_pct", "%")}
    {render_extreme_line("最大陣風", strongest_gust, "wind_gust_ms", "m/s")}
    {render_extreme_line("最大降雨量", wettest, "precipitation_mm", "mm")}
    {render_extreme_line("最低日照", least_sunshine, "sunshine_duration_min", "min")}
    {render_extreme_line("最高 UV", highest_uv, "uv_index", "")}
  </ul>

  <h2>活動天候摘要表</h2>
  {render_activity_table(report_rows)}

  <div class="footer">
    Generated by {esc(SCHEMA_VERSION)}.
    Inputs: {esc(str(PROFILE_CSV))}, {esc(str(VARIABLE_SUMMARY_CSV))}, {esc(str(ACTIVITY_SUMMARY_CSV))}.
  </div>
</body>
</html>
"""

    REPORT_HTML.write_text(html_text, encoding="utf-8")

    print("IB3W CODiS weather profile report v1")
    print(f"report_html: {REPORT_HTML}")
    print(f"report_table_csv: {REPORT_TABLE_CSV}")
    print(f"report_summary_csv: {REPORT_SUMMARY_CSV}")
    print(f"activity_count: {activity_count}")
    print(f"observed_weather_value_count: {observed_row_count}")
    print(f"high_humidity_activity_count: {high_humidity_count}")
    print(f"rain_observed_activity_count: {rain_observed_count}")
    print(f"no_rain_observed_activity_count: {no_rain_observed_count}")
    print(f"max_wind_gust_ms: {variable_stats['wind_gust_ms']['max']}")
    print("report_conclusion: PASS_DESCRIPTIVE_EVIDENCE_REPORT_ONLY")


if __name__ == "__main__":
    main()
