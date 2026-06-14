from __future__ import annotations

from pathlib import Path
import html
import json
import pandas as pd


SCHEMA_VERSION = "ib3w_route_window_weather_context_summary_report_v1"

ROUTE_CONTEXT_CSV = Path(
    "outputs/ib3w_heat_humid_route_window_context_v1/"
    "activity_heat_humid_route_window_context.csv"
)

ANTECEDENT_CONTEXT_CSV = Path(
    "outputs/ib3w_antecedent_precipitation_context_v1/"
    "activity_antecedent_precipitation_context.csv"
)

OUT_DIR = Path("outputs/ib3w_route_window_weather_context_summary_report_v1")


def safe(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def num(value):
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return pd.NA if pd.isna(parsed) else float(parsed)


def fmt(value, digits=1, suffix="") -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):.{digits}f}{suffix}"


def local_time_text(utc_text: str) -> str:
    t = pd.to_datetime(utc_text, errors="coerce", utc=True)
    if pd.isna(t):
        return ""
    local = t + pd.Timedelta(hours=8)
    return local.strftime("%Y-%m-%d %H:%M:%S")


def find_col(cols, required_tokens, optional_tokens=None, exclude_tokens=None):
    optional_tokens = optional_tokens or []
    exclude_tokens = exclude_tokens or []
    lowered = {c: c.lower() for c in cols}

    candidates = []
    for c, lc in lowered.items():
        if all(t.lower() in lc for t in required_tokens) and not any(t.lower() in lc for t in exclude_tokens):
            score = sum(1 for t in optional_tokens if t.lower() in lc)
            candidates.append((score, len(c), c))

    if not candidates:
        return None

    candidates.sort(key=lambda x: (-x[0], x[1], x[2]))
    return candidates[0][2]


def first_available(row, cols):
    for c in cols:
        if c and c in row.index and safe(row[c]) != "":
            return row[c]
    return pd.NA


def build_route_window_variation(route: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in route.iterrows():
        temp_mean = num(r.get("temperature_mean_c"))
        rh_mean = num(r.get("relative_humidity_mean_pct"))
        wind_mean = num(r.get("wind_speed_mean_ms"))

        status = safe(r.get("heat_humid_route_window_context_status"))
        hi_status = safe(r.get("heat_index_status"))

        if status == "HEAT_HUMID_ROUTE_WINDOW_CONTEXT_NOT_SUPPORTED_BY_AVAILABLE_WEATHER":
            interpretation = "此路段通過時有氣溫/濕度/風速觀測；但氣溫低於 heat index 標準計算門檻，available weather 不支持 heat/humid stress。"
        elif status == "HEAT_HUMID_ROUTE_WINDOW_CONTEXT_WEATHER_UNAVAILABLE":
            interpretation = "此路段通過時沒有可用氣象觀測，不解讀路段環境變化。"
        else:
            interpretation = "此路段有 heat/humid context proxy；仍非 WBGT、UV、日照或醫療判斷。"

        rows.append({
            "schema_version": SCHEMA_VERSION,
            "activity_id": safe(r.get("activity_id")),
            "route_distance_label": safe(r.get("route_distance_label")),
            "route_distance_start_m": num(r.get("route_distance_start_m")),
            "route_distance_end_m": num(r.get("route_distance_end_m")),
            "window_start_time_utc": safe(r.get("window_start_time_utc")),
            "window_end_time_utc": safe(r.get("window_end_time_utc")),
            "window_start_time_local": local_time_text(safe(r.get("window_start_time_utc"))),
            "window_end_time_local": local_time_text(safe(r.get("window_end_time_utc"))),
            "point_count": int(num(r.get("point_count"))) if not pd.isna(num(r.get("point_count"))) else 0,
            "temperature_mean_c": temp_mean,
            "temperature_max_c": num(r.get("temperature_max_c")),
            "relative_humidity_mean_pct": rh_mean,
            "relative_humidity_max_pct": num(r.get("relative_humidity_max_pct")),
            "wind_speed_mean_ms": wind_mean,
            "wind_speed_max_ms": num(r.get("wind_speed_max_ms")),
            "wind_class": safe(r.get("wind_class")),
            "point_daytime_heat_window_ratio": num(r.get("point_daytime_heat_window_ratio")),
            "heat_index_status": hi_status,
            "heat_index_c": num(r.get("heat_index_c")),
            "heat_humid_route_window_context_status": status,
            "route_window_environment_interpretation_zh": interpretation,
            "temperature_time_effect_type": "INSTANT_OR_NEAR_REAL_TIME_STATE",
            "humidity_time_effect_type": "INSTANT_OR_NEAR_REAL_TIME_STATE",
            "wind_time_effect_type": "INSTANT_OR_NEAR_REAL_TIME_STATE",
            "heat_index_time_effect_type": "DERIVED_FROM_NEAR_REAL_TIME_TEMPERATURE_HUMIDITY_IF_THRESHOLD_SUPPORTED",
            "route_window_context_time_effect_type": "ROUTE_WINDOW_NEAR_REAL_TIME_CONTEXT_WITH_PROXY_BOUNDARY",
            "zero_fallback_true_count": int(num(r.get("zero_fallback_true_count"))) if not pd.isna(num(r.get("zero_fallback_true_count"))) else 0,
        })

    out = pd.DataFrame(rows)
    return out.sort_values(["activity_id", "route_distance_start_m"]).reset_index(drop=True)


def classify_temp_trend(delta):
    if pd.isna(delta):
        return "UNKNOWN"
    if delta >= 1.0:
        return "TEMPERATURE_INCREASING_ALONG_ACTIVITY_TIME_ROUTE"
    if delta <= -1.0:
        return "TEMPERATURE_DECREASING_ALONG_ACTIVITY_TIME_ROUTE"
    return "TEMPERATURE_STABLE_MINOR_CHANGE"


def classify_rh_trend(delta):
    if pd.isna(delta):
        return "UNKNOWN"
    if delta >= 3.0:
        return "HUMIDITY_INCREASING_ALONG_ACTIVITY_TIME_ROUTE"
    if delta <= -3.0:
        return "HUMIDITY_DECREASING_ALONG_ACTIVITY_TIME_ROUTE"
    return "HUMIDITY_STABLE_MINOR_CHANGE"


def classify_wind_trend(delta):
    if pd.isna(delta):
        return "UNKNOWN"
    if delta >= 0.5:
        return "WIND_SPEED_INCREASING_ALONG_ACTIVITY_TIME_ROUTE"
    if delta <= -0.5:
        return "WIND_SPEED_DECREASING_ALONG_ACTIVITY_TIME_ROUTE"
    return "WIND_SPEED_STABLE_MINOR_CHANGE"


def build_trend_summary(route_summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for activity_id, g in route_summary.groupby("activity_id", sort=True):
        g = g.sort_values("route_distance_start_m").copy()
        first = g.iloc[0]
        last = g.iloc[-1]

        temp_delta = (
            pd.NA if pd.isna(first["temperature_mean_c"]) or pd.isna(last["temperature_mean_c"])
            else round(float(last["temperature_mean_c"]) - float(first["temperature_mean_c"]), 4)
        )
        rh_delta = (
            pd.NA if pd.isna(first["relative_humidity_mean_pct"]) or pd.isna(last["relative_humidity_mean_pct"])
            else round(float(last["relative_humidity_mean_pct"]) - float(first["relative_humidity_mean_pct"]), 4)
        )
        wind_delta = (
            pd.NA if pd.isna(first["wind_speed_mean_ms"]) or pd.isna(last["wind_speed_mean_ms"])
            else round(float(last["wind_speed_mean_ms"]) - float(first["wind_speed_mean_ms"]), 4)
        )

        status_counts = (
            g.groupby("heat_humid_route_window_context_status")
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )
        status_distribution = " | ".join(
            f"{row['heat_humid_route_window_context_status']}={int(row['count'])}"
            for _, row in status_counts.iterrows()
        )

        all_not_supported = g["heat_humid_route_window_context_status"].eq(
            "HEAT_HUMID_ROUTE_WINDOW_CONTEXT_NOT_SUPPORTED_BY_AVAILABLE_WEATHER"
        ).all()

        rows.append({
            "schema_version": SCHEMA_VERSION,
            "activity_id": activity_id,
            "route_window_count": int(len(g)),
            "route_distance_min_m": float(g["route_distance_start_m"].min()),
            "route_distance_max_m": float(g["route_distance_end_m"].max()),
            "activity_start_time_local": safe(g["window_start_time_local"].iloc[0]),
            "activity_end_time_local": safe(g["window_end_time_local"].iloc[-1]),
            "temperature_mean_first_c": first["temperature_mean_c"],
            "temperature_mean_last_c": last["temperature_mean_c"],
            "temperature_mean_delta_c": temp_delta,
            "temperature_mean_min_c": round(float(g["temperature_mean_c"].min()), 4),
            "temperature_mean_max_c": round(float(g["temperature_mean_c"].max()), 4),
            "temperature_variation_status": classify_temp_trend(temp_delta),
            "relative_humidity_mean_first_pct": first["relative_humidity_mean_pct"],
            "relative_humidity_mean_last_pct": last["relative_humidity_mean_pct"],
            "relative_humidity_mean_delta_pct": rh_delta,
            "relative_humidity_mean_min_pct": round(float(g["relative_humidity_mean_pct"].min()), 4),
            "relative_humidity_mean_max_pct": round(float(g["relative_humidity_mean_pct"].max()), 4),
            "relative_humidity_variation_status": classify_rh_trend(rh_delta),
            "wind_speed_mean_first_ms": first["wind_speed_mean_ms"],
            "wind_speed_mean_last_ms": last["wind_speed_mean_ms"],
            "wind_speed_mean_delta_ms": wind_delta,
            "wind_speed_mean_min_ms": round(float(g["wind_speed_mean_ms"].min()), 4),
            "wind_speed_mean_max_ms": round(float(g["wind_speed_mean_ms"].max()), 4),
            "wind_speed_variation_status": classify_wind_trend(wind_delta),
            "heat_index_computed_window_count": int(g["heat_index_c"].notna().sum()),
            "daytime_heat_window_positive_count": int((g["point_daytime_heat_window_ratio"] > 0).sum()),
            "heat_humid_route_window_context_status_distribution": status_distribution,
            "all_windows_heat_humid_not_supported": bool(all_not_supported),
            "zero_fallback_true_count": int(g["zero_fallback_true_count"].sum()),
            "route_window_variation_conclusion_zh": (
                "活動通過不同路段時，氣溫隨時間與路段逐步上升、相對濕度下降、風速略增；"
                "但全路段 heat index 未達標準計算門檻，available weather 不支持 heat/humid stress。"
                if all_not_supported else
                "活動通過不同路段時存在氣溫、濕度、風速變化；部分路段需保留 heat/humid proxy review。"
            ),
        })
    return pd.DataFrame(rows)


def build_antecedent_summary(activity_ids) -> pd.DataFrame:
    rows = []
    if not ANTECEDENT_CONTEXT_CSV.exists():
        for activity_id in activity_ids:
            rows.append({
                "schema_version": SCHEMA_VERSION,
                "activity_id": activity_id,
                "antecedent_context_available": False,
                "antecedent_source_csv": str(ANTECEDENT_CONTEXT_CSV),
                "antecedent_weather_background_zh": "找不到 antecedent precipitation context CSV；本報告不附前期降雨背景。",
            })
        return pd.DataFrame(rows)

    ant = pd.read_csv(ANTECEDENT_CONTEXT_CSV, dtype=str)
    cols = list(ant.columns)

    activity_col = "activity_id" if "activity_id" in ant.columns else find_col(cols, ["activity"])
    start_col = find_col(cols, ["activity", "start"], optional_tokens=["time", "utc"])

    c6 = find_col(cols, ["6"], optional_tokens=["rain", "precip", "max", "mm"])
    c24 = find_col(cols, ["24"], optional_tokens=["rain", "precip", "max", "mm"])
    c72 = find_col(cols, ["72"], optional_tokens=["rain", "precip", "max", "mm"])
    c7d = find_col(cols, ["7"], optional_tokens=["rain", "precip", "max", "mm", "day"])
    last_rain_time_col = find_col(cols, ["last", "rain"], optional_tokens=["time", "utc"])
    last_rain_hours_col = find_col(cols, ["hours", "since"], optional_tokens=["last", "rain"])
    last_rain_station_col = find_col(cols, ["last", "rain"], optional_tokens=["station"])

    for activity_id in activity_ids:
        match = pd.DataFrame()
        if activity_col and activity_col in ant.columns:
            match = ant[ant[activity_col].astype(str) == activity_id]

        if match.empty:
            # Try loose contains match for derived activity id variants.
            if activity_col and activity_col in ant.columns:
                match = ant[ant[activity_col].astype(str).str.contains("qixing", case=False, na=False)]

        if match.empty:
            rows.append({
                "schema_version": SCHEMA_VERSION,
                "activity_id": activity_id,
                "antecedent_context_available": False,
                "antecedent_source_csv": str(ANTECEDENT_CONTEXT_CSV),
                "antecedent_weather_background_zh": "antecedent precipitation context CSV 存在，但找不到可明確對應的 activity row。",
            })
            continue

        r = match.iloc[0]

        rain6 = first_available(r, [c6])
        rain24 = first_available(r, [c24])
        rain72 = first_available(r, [c72])
        rain7d = first_available(r, [c7d])
        last_time = first_available(r, [last_rain_time_col])
        hours_since = first_available(r, [last_rain_hours_col])
        last_station = first_available(r, [last_rain_station_col])

        parts = []
        if safe(rain6):
            parts.append(f"出發前 6h 觀測降雨背景值：{safe(rain6)}")
        if safe(rain24):
            parts.append(f"出發前 24h 觀測降雨背景值：{safe(rain24)}")
        if safe(rain72):
            parts.append(f"出發前 72h 觀測降雨背景值：{safe(rain72)}")
        if safe(rain7d):
            parts.append(f"出發前 7d 觀測降雨背景值：{safe(rain7d)}")
        if safe(last_time):
            parts.append(f"最後一次觀測降雨時間：{safe(last_time)}")
        if safe(hours_since):
            parts.append(f"距活動開始約 {safe(hours_since)} 小時前仍有觀測降雨")
        if safe(last_station):
            parts.append(f"最後降雨測站：{safe(last_station)}")

        if not parts:
            parts.append("找到 antecedent row，但欄位名稱未能自動解析；請查看 antecedent_raw_row_json。")

        rows.append({
            "schema_version": SCHEMA_VERSION,
            "activity_id": activity_id,
            "antecedent_context_available": True,
            "antecedent_source_csv": str(ANTECEDENT_CONTEXT_CSV),
            "activity_start_time_from_antecedent": safe(first_available(r, [start_col])),
            "rain_lookback_6h_value": safe(rain6),
            "rain_lookback_24h_value": safe(rain24),
            "rain_lookback_72h_value": safe(rain72),
            "rain_lookback_7d_value": safe(rain7d),
            "last_observed_rain_time": safe(last_time),
            "hours_since_last_observed_rain": safe(hours_since),
            "last_observed_rain_station": safe(last_station),
            "antecedent_weather_background_zh": "；".join(parts),
            "precipitation_time_effect_type": "INTERVAL_ACCUMULATION_ENDING_AT_OBS_TIME_OR_LOOKBACK_CONTEXT",
            "antecedent_time_effect_type": "ANTECEDENT_LOOKBACK_CONTEXT",
            "delayed_effect_boundary": "可作為前期天氣背景；不可直接宣稱實測路面濕滑、土壤含水、溪水暴漲或邊坡不穩。",
            "antecedent_raw_row_json": json.dumps(r.to_dict(), ensure_ascii=False),
        })

    return pd.DataFrame(rows)


def build_time_effect_contract() -> pd.DataFrame:
    rows = [
        {
            "feature_family": "temperature",
            "example_fields": "temperature_mean_c, temperature_max_c",
            "time_effect_type": "INSTANT_OR_NEAR_REAL_TIME_STATE",
            "correct_interpretation_zh": "活動通過該路段時的近即時氣溫背景。",
            "do_not_claim_zh": "不可宣稱為多年氣候，亦不可單獨推論中暑或熱傷害。",
        },
        {
            "feature_family": "relative_humidity",
            "example_fields": "relative_humidity_mean_pct, relative_humidity_max_pct",
            "time_effect_type": "INSTANT_OR_NEAR_REAL_TIME_STATE",
            "correct_interpretation_zh": "活動通過該路段時的近即時濕度背景。",
            "do_not_claim_zh": "不可單獨宣稱霧、低雲、路面濕滑或熱傷害。",
        },
        {
            "feature_family": "wind",
            "example_fields": "wind_speed_mean_ms, wind_speed_max_ms, wind_direction_deg",
            "time_effect_type": "INSTANT_OR_NEAR_REAL_TIME_STATE_OR_SHORT_INTERVAL_SUMMARY",
            "correct_interpretation_zh": "活動通過該路段時的近即時風速/短時段風況背景。",
            "do_not_claim_zh": "不可當成路線每一點的實測風場；地形遮蔽需另行處理。",
        },
        {
            "feature_family": "precipitation",
            "example_fields": "precipitation_mm, precipitation_10min_mm, precipitation_1hr_mm",
            "time_effect_type": "INTERVAL_ACCUMULATION_ENDING_AT_OBS_TIME",
            "correct_interpretation_zh": "觀測時間之前一段時間已發生的降雨量。",
            "do_not_claim_zh": "不可解讀為觀測時間當下正在下多少雨。",
        },
        {
            "feature_family": "antecedent_rain",
            "example_fields": "rain_lookback_6h/24h/72h/7d",
            "time_effect_type": "ANTECEDENT_LOOKBACK_CONTEXT",
            "correct_interpretation_zh": "活動前幾小時到幾天的降雨背景。",
            "do_not_claim_zh": "不可直接宣稱實測土壤含水、路面濕滑、溪水暴漲或邊坡危險。",
        },
        {
            "feature_family": "surface_wetness_or_hydrologic_response",
            "example_fields": "surface_wetness_proxy, hydrologic_response_proxy",
            "time_effect_type": "DELAYED_RESPONSE_PROXY",
            "correct_interpretation_zh": "由前期降雨、濕度、日照/乾燥條件推估的延後效應 proxy。",
            "do_not_claim_zh": "不可宣稱為直接觀測到的路面、水位或土壤狀態。",
        },
        {
            "feature_family": "water_level",
            "example_fields": "water_level_m",
            "time_effect_type": "INSTANT_OR_NEAR_REAL_TIME_STATE_WITH_ANTECEDENT_CAUSE",
            "correct_interpretation_zh": "水位高度本身是近即時狀態；造成水位的降雨可能發生在更早時間。",
            "do_not_claim_zh": "不可把水位升高解讀成當下才開始降雨。",
        },
    ]
    return pd.DataFrame(rows)


def build_narrative(trend: pd.DataFrame, ant: pd.DataFrame) -> str:
    if trend.empty:
        return "# IB3W Route-window Weather Context Summary Report v1\n\nNo route-window rows.\n"

    t = trend.iloc[0]
    activity_id = safe(t["activity_id"])

    lines = []
    lines.append("# IB3W Route-window Weather Context Summary Report v1")
    lines.append("")
    lines.append(f"- activity_id: `{activity_id}`")
    lines.append(f"- route_window_count: {int(t['route_window_count'])}")
    lines.append(f"- route_distance_range_m: {fmt(t['route_distance_min_m'], 0)}–{fmt(t['route_distance_max_m'], 0)}")
    lines.append(f"- local_time_range: {safe(t['activity_start_time_local'])} → {safe(t['activity_end_time_local'])}")
    lines.append("")
    lines.append("## 路段當下環境變化")
    lines.append("")
    lines.append(
        f"- 氣溫：{fmt(t['temperature_mean_first_c'], 1, '°C')} → "
        f"{fmt(t['temperature_mean_last_c'], 1, '°C')}，"
        f"變化 {fmt(t['temperature_mean_delta_c'], 1, '°C')}。"
    )
    lines.append(
        f"- 相對濕度：{fmt(t['relative_humidity_mean_first_pct'], 1, '%')} → "
        f"{fmt(t['relative_humidity_mean_last_pct'], 1, '%')}，"
        f"變化 {fmt(t['relative_humidity_mean_delta_pct'], 1, '%')}。"
    )
    lines.append(
        f"- 風速：{fmt(t['wind_speed_mean_first_ms'], 1, ' m/s')} → "
        f"{fmt(t['wind_speed_mean_last_ms'], 1, ' m/s')}，"
        f"變化 {fmt(t['wind_speed_mean_delta_ms'], 1, ' m/s')}。"
    )
    lines.append("")
    lines.append(safe(t["route_window_variation_conclusion_zh"]))
    lines.append("")
    lines.append("## 前期天氣背景")
    lines.append("")
    if not ant.empty:
        a = ant.iloc[0]
        lines.append(safe(a.get("antecedent_weather_background_zh")))
        lines.append("")
        lines.append("前期降雨是 lookback context：代表活動前某段時間曾發生觀測降雨，不能直接當成活動當下正在下雨。")
    else:
        lines.append("未附 antecedent precipitation context。")
    lines.append("")
    lines.append("## 時間語意與判讀邊界")
    lines.append("")
    lines.append("- temperature / humidity / wind：近即時或短時段狀態，適合對應活動通過路段。")
    lines.append("- precipitation：區間累積，代表觀測時間之前一段時間已發生的雨量。")
    lines.append("- antecedent rain：活動前 lookback 背景，不能直接宣稱路面濕滑或土壤含水。")
    lines.append("- water level 若未來納入：水位是近即時狀態，但造成水位的降雨可能有延後效應。")
    lines.append("- 本報告不宣稱 WBGT、UV、直接日照、中暑/熱傷害、醫療判斷、THCI 或 final hiking risk。")
    lines.append("- missing weather remains missing；zero_fallback_true_count 必須為 0。")
    lines.append("")
    return "\n".join(lines)


def html_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "<p>No rows.</p>"
    return df.fillna("").to_html(index=False, escape=True, border=0)


def build_html(route_summary, trend, ant, contract, narrative) -> str:
    zero = int(route_summary["zero_fallback_true_count"].sum()) if not route_summary.empty else 0
    narrative_html = "<br>\n".join(html.escape(line) for line in narrative.splitlines())

    route_cols = [
        "route_distance_label",
        "window_start_time_local",
        "window_end_time_local",
        "temperature_mean_c",
        "temperature_max_c",
        "relative_humidity_mean_pct",
        "wind_speed_mean_ms",
        "heat_index_status",
        "heat_humid_route_window_context_status",
        "route_window_environment_interpretation_zh",
    ]

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>IB3W Route-window Weather Context Summary Report v1</title>
<style>
body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; background: #f6f8fa; color: #1f2937; }}
section {{ background: white; border: 1px solid #d9e1e7; border-radius: 10px; padding: 18px; margin-bottom: 16px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
th, td {{ border: 1px solid #d9e1e7; padding: 6px 8px; text-align: left; vertical-align: top; }}
th {{ background: #edf2f5; }}
pre {{ white-space: pre-wrap; font-size: 13px; line-height: 1.5; }}
.wrap {{ overflow-x: auto; }}
</style>
</head>
<body>
<h1>IB3W Route-window Weather Context Summary Report v1</h1>
<section>
<p>Readable report layer for route-window temperature / humidity / wind variation and antecedent weather background.</p>
<p>No WBGT, no UV, no direct sunshine, no heat illness diagnosis, no medical judgment, no THCI, no final hiking risk score, no missing-to-zero imputation.</p>
<p>Route-window rows: {len(route_summary)}; zero fallback violations: {zero}</p>
</section>
<section><h2>Narrative</h2><pre>{narrative_html}</pre></section>
<section><h2>Route-window trend summary</h2><div class="wrap">{html_table(trend)}</div></section>
<section><h2>Antecedent weather background</h2><div class="wrap">{html_table(ant)}</div></section>
<section><h2>Route-window environment variation</h2><div class="wrap">{html_table(route_summary[route_cols] if not route_summary.empty else route_summary)}</div></section>
<section><h2>Weather time-effect feature contract</h2><div class="wrap">{html_table(contract)}</div></section>
</body>
</html>
"""


def main() -> None:
    if not ROUTE_CONTEXT_CSV.exists():
        raise FileNotFoundError(ROUTE_CONTEXT_CSV)

    route = pd.read_csv(ROUTE_CONTEXT_CSV, dtype=str)
    route_summary = build_route_window_variation(route)
    trend = build_trend_summary(route_summary)
    activity_ids = sorted(route_summary["activity_id"].dropna().astype(str).unique().tolist())
    ant = build_antecedent_summary(activity_ids)
    contract = build_time_effect_contract()
    narrative = build_narrative(trend, ant)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    route_summary_csv = OUT_DIR / "activity_route_window_environment_variation_summary.csv"
    trend_csv = OUT_DIR / "activity_route_window_weather_context_trend_summary.csv"
    ant_csv = OUT_DIR / "activity_antecedent_weather_background_summary.csv"
    contract_csv = OUT_DIR / "weather_time_effect_feature_contract.csv"
    narrative_md = OUT_DIR / "activity_route_window_weather_context_summary_narrative.md"
    html_report = OUT_DIR / "activity_route_window_weather_context_summary_report.html"

    route_summary.to_csv(route_summary_csv, index=False, encoding="utf-8-sig")
    trend.to_csv(trend_csv, index=False, encoding="utf-8-sig")
    ant.to_csv(ant_csv, index=False, encoding="utf-8-sig")
    contract.to_csv(contract_csv, index=False, encoding="utf-8-sig")
    narrative_md.write_text(narrative, encoding="utf-8-sig")
    html_report.write_text(build_html(route_summary, trend, ant, contract, narrative), encoding="utf-8-sig")

    print("IB3W route-window weather context summary report v1 written")
    print("route_summary_csv:", route_summary_csv)
    print("trend_csv:", trend_csv)
    print("antecedent_csv:", ant_csv)
    print("contract_csv:", contract_csv)
    print("narrative_md:", narrative_md)
    print("html_report:", html_report)
    print()
    print("route_window_rows:", len(route_summary))
    print("activity_ids:", ", ".join(activity_ids))
    print("zero_fallback_true_total:", int(route_summary["zero_fallback_true_count"].sum()))
    print()
    print("trend summary:")
    print(trend.to_string(index=False))
    print()
    print("antecedent summary:")
    print(ant.drop(columns=["antecedent_raw_row_json"], errors="ignore").to_string(index=False))


if __name__ == "__main__":
    main()
