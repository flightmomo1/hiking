from __future__ import annotations

import csv
import html
import math
from pathlib import Path
from statistics import median

SCHEMA_VERSION = "ib3_baseline_hiking_performance_weather_numeric_reattach_v1"

COMPARISON_CSV = Path(
    "outputs/ib3_baseline_hiking_performance_route_normalized_comparison_smoke_v1/"
    "activity_route_normalized_comparison_smoke.csv"
)
COMPARISON_AUDIT_CSV = Path(
    "outputs/ib3_baseline_hiking_performance_route_normalized_comparison_smoke_v1/"
    "route_normalized_comparison_smoke_audit.csv"
)
JOIN_CSV = Path(
    "outputs/ib3w_activity_weather_performance_join_v1/"
    "activity_weather_performance_join.csv"
)

OUT_ROOT = Path("outputs/ib3_baseline_hiking_performance_weather_numeric_reattach_v1")
OUT_COMPARISON_CSV = OUT_ROOT / "activity_route_normalized_comparison_weather_reattached.csv"
OUT_GAIN_SANITY_CSV = OUT_ROOT / "weather_numeric_reattach_gain_rate_sanity.csv"
OUT_AUDIT_CSV = OUT_ROOT / "weather_numeric_reattach_audit.csv"
OUT_REPORT_HTML = OUT_ROOT / "weather_numeric_reattach_report.html"

WEATHER_FIELDS = [
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
]

CORE_WEATHER_NUMERIC_FIELDS = [
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

AUTHORIZATION_NOTE = (
    "Weather numeric reattach is descriptive evidence only. It does not compute or authorize "
    "ability scores, ability ranks, ability classes, THCI scores, radar scores, or final hiking risk scores."
)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        seen: list[str] = []
        for row in rows:
            for key in row.keys():
                if key not in seen:
                    seen.append(key)
        fieldnames = seen
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def as_float(value: object) -> float | None:
    text = str(value).strip()
    if not text:
        return None
    try:
        v = float(text)
    except ValueError:
        return None
    if math.isnan(v):
        return None
    return v


def fmt(value: object, digits: int = 6) -> str:
    v = as_float(value)
    if v is None:
        return ""
    text = f"{v:.{digits}f}".rstrip("0").rstrip(".")
    return text if text else "0"


def pctile(values: list[float], q: float) -> float | None:
    vals = sorted(v for v in values if v is not None and not math.isnan(v))
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return vals[lo]
    frac = pos - lo
    return vals[lo] * (1 - frac) + vals[hi] * frac


def truthy(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def esc(value: object) -> str:
    return html.escape(str(value))


def dist(values: list[str]) -> str:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value).strip() or "BLANK"
        counts[key] = counts.get(key, 0) + 1
    return "|".join(f"{k}:{counts[k]}" for k in sorted(counts))


def derive_weather_flags(row: dict[str, str]) -> str:
    flags: list[str] = []
    rh = as_float(row.get("relative_humidity_pct", ""))
    rain = as_float(row.get("precipitation_mm", ""))
    gust = as_float(row.get("wind_gust_ms", ""))
    uv = as_float(row.get("uv_index", ""))

    if rh is not None and rh >= 90:
        flags.append("HIGH_HUMIDITY_CONTEXT")
    if rain is not None and rain > 0:
        flags.append("RAIN_OBSERVED_CONTEXT")
    if rain is not None and rain == 0:
        flags.append("NO_RAIN_CONTEXT")
    if gust is not None:
        flags.append("WIND_GUST_OBSERVED_CONTEXT")
    if gust is not None and gust >= 10:
        flags.append("STRONG_GUST_CONTEXT")
    if uv is not None and uv >= 6:
        flags.append("HIGH_UV_CONTEXT")
    return "|".join(flags)


def gain_sanity_flag(row: dict[str, str]) -> str:
    gain_rate = as_float(row.get("candidate_gain_rate_m_per_hour", ""))
    gain_per_km = as_float(row.get("candidate_gain_m_per_km", ""))
    flags: list[str] = []

    if gain_rate is None:
        flags.append("GAIN_RATE_MISSING")
    elif gain_rate < 50:
        flags.append("GAIN_RATE_LOW_REVIEW")
    elif gain_rate > 600:
        flags.append("GAIN_RATE_HIGH_REVIEW")
    else:
        flags.append("GAIN_RATE_PLAUSIBILITY_UNREVIEWED")

    if gain_per_km is None:
        flags.append("GAIN_PER_KM_MISSING")
    elif gain_per_km < 30:
        flags.append("GAIN_PER_KM_LOW_REVIEW")
    elif gain_per_km > 300:
        flags.append("GAIN_PER_KM_HIGH_REVIEW")
    else:
        flags.append("GAIN_PER_KM_PLAUSIBILITY_UNREVIEWED")

    return "|".join(flags)


def render_table(rows: list[dict[str, object]], cols: list[tuple[str, str]], limit: int | None = None) -> str:
    display = rows if limit is None else rows[:limit]
    head = "".join(f"<th>{esc(label)}</th>" for _, label in cols)
    body = []
    for row in display:
        body.append("<tr>" + "".join(f"<td>{esc(row.get(key, ''))}</td>" for key, _ in cols) + "</tr>")
    return (
        '<div class="table-wrap"><table><thead><tr>'
        + head
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></div>"
    )


def main() -> None:
    comparison_rows = read_csv(COMPARISON_CSV)
    join_rows = read_csv(JOIN_CSV)
    comparison_audit_rows = read_csv(COMPARISON_AUDIT_CSV)

    join_by_short = {row.get("activity_id_short", "").strip(): row for row in join_rows if row.get("activity_id_short", "").strip()}

    out_rows: list[dict[str, object]] = []
    gain_rows: list[dict[str, object]] = []

    missing_join_ids: list[str] = []
    full_numeric_count = 0
    partial_numeric_count = 0

    for row in comparison_rows:
        out = dict(row)
        short_id = str(row.get("activity_id_short", "")).strip()
        join = join_by_short.get(short_id)

        out["schema_version"] = SCHEMA_VERSION

        if join is None:
            out["weather_numeric_reattach_status"] = "WEATHER_JOIN_NOT_FOUND"
            missing_join_ids.append(short_id)
        else:
            attached_nonempty = 0
            for field in WEATHER_FIELDS:
                value = join.get(field, "")
                out[field] = value
                if field in CORE_WEATHER_NUMERIC_FIELDS and str(value).strip() != "":
                    attached_nonempty += 1

            if attached_nonempty == len(CORE_WEATHER_NUMERIC_FIELDS):
                out["weather_numeric_reattach_status"] = "MATCHED_WEATHER_NUMERIC_ATTACHED"
                full_numeric_count += 1
            else:
                out["weather_numeric_reattach_status"] = "MATCHED_WEATHER_NUMERIC_PARTIAL"
                partial_numeric_count += 1

            out["candidate_weather_context_flags_reattached"] = derive_weather_flags({k: str(out.get(k, "")) for k in out.keys()})

        out["ability_score_generated"] = "False"
        out["ability_rank_generated"] = "False"
        out["ability_class_generated"] = "False"
        out["thci_scoring_authorized"] = "False"
        out["radar_scoring_authorized"] = "False"
        out["final_hiking_risk_scoring_authorized"] = "False"
        out["authorization_note"] = AUTHORIZATION_NOTE

        gain_rate = as_float(out.get("candidate_gain_rate_m_per_hour", ""))
        gain_per_km = as_float(out.get("candidate_gain_m_per_km", ""))
        route_km = as_float(out.get("route_dist_covered_km", ""))
        duration_min = as_float(out.get("duration_min", ""))
        derived_gain_m = None
        if gain_per_km is not None and route_km is not None:
            derived_gain_m = gain_per_km * route_km

        sanity = gain_sanity_flag({k: str(out.get(k, "")) for k in out.keys()})
        out["gain_rate_sanity_flag"] = sanity

        gain_rows.append({
            "schema_version": SCHEMA_VERSION,
            "activity_id_short": short_id,
            "route_dist_covered_km": fmt(route_km),
            "duration_min": fmt(duration_min),
            "candidate_gain_m_per_km": fmt(gain_per_km),
            "candidate_gain_rate_m_per_hour": fmt(gain_rate),
            "derived_gain_m_from_gain_per_km": fmt(derived_gain_m),
            "gain_rate_sanity_flag": sanity,
            "sanity_note": (
                "Review-only plausibility flag. This is not ability scoring. Low gain-rate may reflect "
                "conservative calibrated gain, total-duration denominator, or route/elevation aggregation semantics."
            ),
        })

        out_rows.append(out)

    gain_rates = [as_float(r.get("candidate_gain_rate_m_per_hour", "")) for r in out_rows]
    gain_rates_clean = [v for v in gain_rates if v is not None]
    gain_per_km_vals = [as_float(r.get("candidate_gain_m_per_km", "")) for r in out_rows]
    gain_per_km_clean = [v for v in gain_per_km_vals if v is not None]

    reattach_status_distribution = dist([str(r.get("weather_numeric_reattach_status", "")) for r in out_rows])
    gain_sanity_distribution = dist([str(r.get("gain_rate_sanity_flag", "")) for r in gain_rows])

    audit_conclusion = "PASS_WEATHER_NUMERIC_REATTACH_DESCRIPTIVE_ONLY"
    if missing_join_ids:
        audit_conclusion = "FAIL_WEATHER_JOIN_MISSING_FOR_COMPARISON_ROWS"
    if len(out_rows) != len(comparison_rows):
        audit_conclusion = "FAIL_ROW_COUNT_MISMATCH"

    audit_rows = [{
        "schema_version": SCHEMA_VERSION,
        "input_comparison_csv": str(COMPARISON_CSV),
        "input_comparison_audit_csv": str(COMPARISON_AUDIT_CSV),
        "input_join_csv": str(JOIN_CSV),
        "input_comparison_row_count": len(comparison_rows),
        "input_join_row_count": len(join_rows),
        "output_row_count": len(out_rows),
        "matched_weather_numeric_reattach_count": full_numeric_count,
        "partial_weather_numeric_reattach_count": partial_numeric_count,
        "missing_join_count": len(missing_join_ids),
        "missing_join_activity_ids": "|".join(missing_join_ids),
        "reattach_status_distribution": reattach_status_distribution,
        "gain_rate_m_per_hour_min": fmt(pctile(gain_rates_clean, 0.0)),
        "gain_rate_m_per_hour_p25": fmt(pctile(gain_rates_clean, 0.25)),
        "gain_rate_m_per_hour_median": fmt(pctile(gain_rates_clean, 0.5)),
        "gain_rate_m_per_hour_p75": fmt(pctile(gain_rates_clean, 0.75)),
        "gain_rate_m_per_hour_max": fmt(pctile(gain_rates_clean, 1.0)),
        "gain_m_per_km_min": fmt(pctile(gain_per_km_clean, 0.0)),
        "gain_m_per_km_p25": fmt(pctile(gain_per_km_clean, 0.25)),
        "gain_m_per_km_median": fmt(pctile(gain_per_km_clean, 0.5)),
        "gain_m_per_km_p75": fmt(pctile(gain_per_km_clean, 0.75)),
        "gain_m_per_km_max": fmt(pctile(gain_per_km_clean, 1.0)),
        "gain_rate_sanity_distribution": gain_sanity_distribution,
        "weather_numeric_reattach_performed": "True",
        "gain_rate_sanity_check_performed": "True",
        "ability_score_generated": "False",
        "ability_rank_generated": "False",
        "ability_class_generated": "False",
        "thci_scoring_authorized": "False",
        "radar_scoring_authorized": "False",
        "final_hiking_risk_scoring_authorized": "False",
        "zero_fallback_used": "False",
        "audit_conclusion": audit_conclusion,
    }]

    base_fields: list[str] = []
    for row in out_rows:
        for key in row.keys():
            if key not in base_fields:
                base_fields.append(key)

    write_csv(OUT_COMPARISON_CSV, out_rows, base_fields)
    write_csv(OUT_GAIN_SANITY_CSV, gain_rows)
    write_csv(OUT_AUDIT_CSV, audit_rows)

    overview = audit_rows[0]
    cards = [
        ("comparison rows", overview["input_comparison_row_count"]),
        ("weather join rows", overview["input_join_row_count"]),
        ("reattached full numeric", overview["matched_weather_numeric_reattach_count"]),
        ("missing join", overview["missing_join_count"]),
        ("gain rate median", overview["gain_rate_m_per_hour_median"]),
        ("gain m/km median", overview["gain_m_per_km_median"]),
    ]

    card_html = "".join(
        f'<div class="card"><strong>{esc(v)}</strong><span>{esc(k)}</span></div>'
        for k, v in cards
    )

    table_cols = [
        ("activity_id_short", "activity"),
        ("candidate_duration_min_per_km", "min/km"),
        ("candidate_median_speed_kmh", "speed km/h"),
        ("candidate_gain_rate_m_per_hour", "gain m/h"),
        ("gain_rate_sanity_flag", "gain sanity"),
        ("relative_humidity_pct", "RH %"),
        ("precipitation_mm", "rain mm"),
        ("wind_gust_ms", "gust m/s"),
        ("uv_index", "UV"),
        ("candidate_weather_context_flags_reattached", "weather flags"),
        ("weather_numeric_reattach_status", "reattach status"),
    ]

    gain_cols = [
        ("activity_id_short", "activity"),
        ("route_dist_covered_km", "route km"),
        ("duration_min", "duration min"),
        ("candidate_gain_m_per_km", "gain m/km"),
        ("candidate_gain_rate_m_per_hour", "gain m/h"),
        ("derived_gain_m_from_gain_per_km", "derived gain m"),
        ("gain_rate_sanity_flag", "sanity flag"),
    ]

    html_text = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>IB3 Weather Numeric Reattach and Gain-Rate Sanity Check</title>
<style>
body {{ font-family: Arial, "Noto Sans TC", sans-serif; margin: 24px; color: #1f2933; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin: 16px 0; }}
.card {{ border: 1px solid #d8dee4; border-radius: 8px; padding: 12px; background: #f8fafc; }}
.card strong {{ display: block; font-size: 24px; }}
.card span {{ color: #52606d; font-size: 12px; }}
.note {{ background: #fff8dc; border-left: 4px solid #d4a72c; padding: 12px; line-height: 1.6; }}
.table-wrap {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; font-size: 12px; margin-top: 12px; }}
th, td {{ border: 1px solid #d8dee4; padding: 6px; text-align: right; white-space: nowrap; }}
th:first-child, td:first-child, th:nth-last-child(-n+3), td:nth-last-child(-n+3) {{ text-align: left; }}
th {{ background: #eef2f6; position: sticky; top: 0; }}
</style>
</head>
<body>
<h1>IB3 Weather Numeric Reattach and Gain-Rate Sanity Check</h1>
<p class="note"><strong>邊界：</strong>{esc(AUTHORIZATION_NOTE)}<br>
本報告只把 weather numeric context 重新接回 route-normalized comparison smoke，並對 gain-rate 做 sanity flag。這些 flag 不是山力分數、不是能力排名、不是風險分數。</p>
<div class="cards">{card_html}</div>
<h2>Audit conclusion</h2>
<p><strong>{esc(audit_conclusion)}</strong></p>
<h2>Reattached comparison table</h2>
{render_table(out_rows, table_cols)}
<h2>Gain-rate sanity table</h2>
{render_table(gain_rows, gain_cols)}
</body>
</html>
"""
    OUT_REPORT_HTML.write_text(html_text, encoding="utf-8")

    print("IB3 weather numeric reattach v1")
    print(f"comparison_rows={len(comparison_rows)}")
    print(f"join_rows={len(join_rows)}")
    print(f"output_rows={len(out_rows)}")
    print(f"matched_weather_numeric_reattach_count={full_numeric_count}")
    print(f"partial_weather_numeric_reattach_count={partial_numeric_count}")
    print(f"missing_join_count={len(missing_join_ids)}")
    print(f"reattach_status_distribution={reattach_status_distribution}")
    print(f"gain_rate_m_per_hour_median={overview['gain_rate_m_per_hour_median']}")
    print(f"gain_m_per_km_median={overview['gain_m_per_km_median']}")
    print(f"gain_rate_sanity_distribution={gain_sanity_distribution}")
    print(f"audit_conclusion={audit_conclusion}")
    print(f"wrote={OUT_COMPARISON_CSV}")
    print(f"wrote={OUT_GAIN_SANITY_CSV}")
    print(f"wrote={OUT_AUDIT_CSV}")
    print(f"wrote={OUT_REPORT_HTML}")


if __name__ == "__main__":
    main()
